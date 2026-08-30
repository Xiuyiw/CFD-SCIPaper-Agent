"""Structured, FTS5, and optional semantic retrieval with bounded context output."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol

from cfdpaper.contracts import ClaimRecord, EvidenceRecord, TaskContextPacket
from cfdpaper.storage import ProjectStore


class ContextBudgetExceeded(ValueError):
    """Raised when non-optional packet fields already exceed the token budget."""


class TokenCounter(Protocol):
    """Provider/tokenizer-specific counter for a complete serialized packet."""

    def count(self, text: str) -> int: ...


class Utf8ByteTokenCounter:
    """Dependency-free upper bound that charges one token for every UTF-8 byte."""

    def count(self, text: str) -> int:
        return len(text.encode("utf-8"))


@dataclass(frozen=True)
class SearchFilters:
    source_uris: list[str] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)
    case_ids: list[str] = field(default_factory=list)
    evidence_kinds: list[str] = field(default_factory=list)
    include_stale: bool = False


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    source_id: str
    source_uri: str
    source_hash: str
    locator: str
    content: str
    token_count: int
    fts_score: float
    semantic_score: float
    authority: float
    freshness: float
    score: float


class SemanticBackend(Protocol):
    enabled: bool

    def search(self, query: str, candidate_ids: list[str], limit: int) -> dict[str, float]: ...


class DisabledSemanticBackend:
    enabled = False

    def search(self, query: str, candidate_ids: list[str], limit: int) -> dict[str, float]:
        return {}


class HybridRetriever:
    """Apply structured filters, FTS, optional semantic recall, then evidence reranking."""

    def __init__(
        self, store: ProjectStore, semantic_backend: SemanticBackend | None = None
    ) -> None:
        self.store = store
        self.semantic_backend = semantic_backend or DisabledSemanticBackend()

    def search(
        self,
        query: str,
        *,
        filters: SearchFilters | None = None,
        limit: int = 10,
    ) -> list[RetrievedChunk]:
        if limit < 1:
            return []
        selected = filters or SearchFilters()
        candidates = self._structured_candidates(selected)
        if not candidates:
            return []
        candidate_ids = [str(row["chunk_id"]) for row in candidates]
        fts_scores = self._fts_scores(query, candidate_ids)
        semantic_scores = (
            self.semantic_backend.search(query, candidate_ids, limit)
            if self.semantic_backend.enabled
            else {}
        )
        semantic_scores = _normalize_scores(semantic_scores)
        eligible = set(fts_scores) | set(semantic_scores)
        if not query.strip():
            eligible = set(candidate_ids)
        hits: list[RetrievedChunk] = []
        for row in candidates:
            chunk_id = str(row["chunk_id"])
            if chunk_id not in eligible:
                continue
            authority = float(row["authority"])
            freshness = 0.0 if bool(row["stale"]) else 1.0
            fts_score = fts_scores.get(chunk_id, 0.0)
            semantic_score = semantic_scores.get(chunk_id, 0.0)
            score = 0.65 * fts_score + 0.15 * semantic_score + 0.10 * authority + 0.10 * freshness
            hits.append(
                RetrievedChunk(
                    chunk_id=chunk_id,
                    source_id=str(row["source_id"]),
                    source_uri=str(row["uri"]),
                    source_hash=str(row["sha256"]),
                    locator=str(row["locator"]),
                    content=str(row["content"]),
                    token_count=int(row["token_count"]),
                    fts_score=fts_score,
                    semantic_score=semantic_score,
                    authority=authority,
                    freshness=freshness,
                    score=score,
                )
            )
        return sorted(hits, key=lambda hit: (-hit.score, hit.source_uri, hit.locator))[:limit]

    def _structured_candidates(self, filters: SearchFilters):
        clauses = [] if filters.include_stale else ["s.stale = 0"]
        parameters: list[str] = []
        if filters.source_uris:
            clauses.append(f"s.uri IN ({_placeholders(filters.source_uris)})")
            parameters.extend(filters.source_uris)
        if filters.source_ids:
            clauses.append(f"s.source_id IN ({_placeholders(filters.source_ids)})")
            parameters.extend(filters.source_ids)
        if filters.case_ids:
            clauses.append(
                "EXISTS (SELECT 1 FROM cases ca WHERE ca.source_id=s.source_id "
                f"AND ca.case_id IN ({_placeholders(filters.case_ids)}))"
            )
            parameters.extend(filters.case_ids)
        if filters.evidence_kinds:
            clauses.append(
                "EXISTS (SELECT 1 FROM evidence e WHERE e.source_id=s.source_id "
                f"AND e.kind IN ({_placeholders(filters.evidence_kinds)}))"
            )
            parameters.extend(filters.evidence_kinds)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self.store.connect() as connection:
            return connection.execute(
                "SELECT c.*, s.uri, s.sha256, s.stale, s.authority "
                "FROM chunks c JOIN sources s USING(source_id)" + where,
                parameters,
            ).fetchall()

    def _fts_scores(self, query: str, candidate_ids: list[str]) -> dict[str, float]:
        terms = re.findall(r"[\w]+", query, flags=re.UNICODE)
        if not terms:
            return {}
        expression = " AND ".join(f'"{term}"' for term in terms)
        with self.store.connect() as connection:
            connection.execute(
                "CREATE TEMP TABLE retrieval_candidates (chunk_id TEXT PRIMARY KEY) WITHOUT ROWID"
            )
            try:
                connection.executemany(
                    "INSERT INTO retrieval_candidates(chunk_id) VALUES (?)",
                    ((candidate_id,) for candidate_id in candidate_ids),
                )
                rows = connection.execute(
                    "SELECT chunks_fts.chunk_id, bm25(chunks_fts) AS rank "
                    "FROM chunks_fts JOIN retrieval_candidates rc "
                    "ON rc.chunk_id=chunks_fts.chunk_id WHERE chunks_fts MATCH ?",
                    (expression,),
                ).fetchall()
            finally:
                connection.execute("DROP TABLE retrieval_candidates")
        # FTS5 bm25 is negative: a more negative value is a better match.
        raw = {str(row["chunk_id"]): max(0.0, -float(row["rank"])) for row in rows}
        return _normalize_scores(raw)


def _normalize_scores(scores: dict[str, float]) -> dict[str, float]:
    if not scores:
        return {}
    minimum = min(scores.values())
    maximum = max(scores.values())
    if maximum == minimum:
        normalized = 1.0 if maximum != 0.0 else 0.0
        return {key: normalized for key in scores}
    scale = maximum - minimum
    return {key: (value - minimum) / scale for key, value in scores.items()}


class TaskContextBuilder:
    def __init__(
        self,
        retriever: HybridRetriever,
        *,
        token_counter: TokenCounter | None = None,
    ) -> None:
        self.retriever = retriever
        self.token_counter = token_counter or Utf8ByteTokenCounter()

    def build(
        self,
        *,
        task: str,
        query: str,
        token_budget: int,
        constraints: list[str] | None = None,
        exclusions: list[str] | None = None,
        filters: SearchFilters | None = None,
    ) -> TaskContextPacket:
        constraints = constraints or []
        exclusions = exclusions or []
        evidence: list[EvidenceRecord] = []
        claims: list[ClaimRecord] = []
        self._validate_fixed_fields(task, token_budget, constraints, exclusions)
        hits = self.retriever.search(query, filters=filters, limit=50)
        source_ids = list(dict.fromkeys(hit.source_id for hit in hits))
        structured_evidence = (
            self.retriever.store.list_evidence(source_ids=source_ids) if source_ids else []
        )
        for record in structured_evidence:
            minimal_record = record.model_copy(update={"summary": ""})
            minimal_packet = _make_packet(
                task,
                token_budget,
                [minimal_record],
                [],
                constraints,
                exclusions,
            )
            if estimate_packet_tokens(minimal_packet, self.token_counter) > token_budget:
                locator_free = minimal_record.model_copy(update={"locator": ""})
                locator_free_packet = _make_packet(
                    task, token_budget, [locator_free], [], constraints, exclusions
                )
                if estimate_packet_tokens(locator_free_packet, self.token_counter) <= token_budget:
                    raise ContextBudgetExceeded(
                        f"evidence locator exceeds token budget: {record.evidence_id}"
                    )
                continue
            candidate = _make_packet(
                task, token_budget, [*evidence, record], claims, constraints, exclusions
            )
            if estimate_packet_tokens(candidate, self.token_counter) <= token_budget:
                evidence.append(record)

        included_evidence_ids = {record.evidence_id for record in evidence}
        linked_claims = (
            self.retriever.store.list_claims(source_ids=source_ids) if source_ids else []
        )
        for claim in linked_claims:
            if not set(claim.evidence_ids).issubset(included_evidence_ids):
                continue
            candidate = _make_packet(
                task, token_budget, evidence, [*claims, claim], constraints, exclusions
            )
            if estimate_packet_tokens(candidate, self.token_counter) <= token_budget:
                claims.append(claim)

        for hit in hits:
            record = _fit_chunk_evidence(
                hit,
                task=task,
                token_budget=token_budget,
                evidence=evidence,
                claims=claims,
                constraints=constraints,
                exclusions=exclusions,
                token_counter=self.token_counter,
            )
            if record is None:
                continue
            evidence.append(record)
        packet = _make_packet(task, token_budget, evidence, claims, constraints, exclusions)
        if estimate_packet_tokens(packet, self.token_counter) > token_budget:
            raise RuntimeError("TaskContextPacket budget invariant violated")
        return packet

    def _validate_fixed_fields(
        self,
        task: str,
        token_budget: int,
        constraints: list[str],
        exclusions: list[str],
    ) -> None:
        packet = _make_packet(task, token_budget, [], [], [], [])
        if estimate_packet_tokens(packet, self.token_counter) > token_budget:
            raise ContextBudgetExceeded("fixed field exceeds token budget: task")
        accepted_constraints: list[str] = []
        for index, value in enumerate(constraints):
            accepted_constraints.append(value)
            packet = _make_packet(task, token_budget, [], [], accepted_constraints, [])
            if estimate_packet_tokens(packet, self.token_counter) > token_budget:
                raise ContextBudgetExceeded(
                    f"fixed field exceeds token budget: constraints[{index}]"
                )
        accepted_exclusions: list[str] = []
        for index, value in enumerate(exclusions):
            accepted_exclusions.append(value)
            packet = _make_packet(
                task,
                token_budget,
                [],
                [],
                accepted_constraints,
                accepted_exclusions,
            )
            if estimate_packet_tokens(packet, self.token_counter) > token_budget:
                raise ContextBudgetExceeded(
                    f"fixed field exceeds token budget: exclusions[{index}]"
                )


def _placeholders(values: list[str]) -> str:
    return ",".join("?" for _ in values)


def estimate_packet_tokens(
    packet: TaskContextPacket, token_counter: TokenCounter | None = None
) -> int:
    """Count a serialized packet using an injected tokenizer or UTF-8 byte upper bound."""

    counter = token_counter or Utf8ByteTokenCounter()
    return max(1, counter.count(packet.model_dump_json()))


def _make_packet(
    task: str,
    token_budget: int,
    evidence: list[EvidenceRecord],
    claims: list[ClaimRecord],
    constraints: list[str],
    exclusions: list[str],
) -> TaskContextPacket:
    return TaskContextPacket(
        task=task,
        token_budget=token_budget,
        evidence=evidence,
        claims=claims,
        constraints=constraints,
        exclusions=exclusions,
    )


def _fit_chunk_evidence(
    hit: RetrievedChunk,
    *,
    task: str,
    token_budget: int,
    evidence: list[EvidenceRecord],
    claims: list[ClaimRecord],
    constraints: list[str],
    exclusions: list[str],
    token_counter: TokenCounter,
) -> EvidenceRecord | None:
    def record_with_summary(summary: str) -> EvidenceRecord:
        return EvidenceRecord(
            evidence_id=f"chunk:{hit.chunk_id}",
            source_uri=hit.source_uri,
            locator=hit.locator,
            source_hash=hit.source_hash,
            stale=hit.freshness == 0.0,
            kind="other",
            summary=summary,
            maturity="raw",
        )

    content = hit.content.strip()
    minimal_record = record_with_summary("")
    minimal_packet = _make_packet(
        task,
        token_budget,
        [minimal_record],
        [],
        constraints,
        exclusions,
    )
    if estimate_packet_tokens(minimal_packet, token_counter) > token_budget:
        locator_free = minimal_record.model_copy(update={"locator": ""})
        locator_free_packet = _make_packet(
            task, token_budget, [locator_free], [], constraints, exclusions
        )
        if estimate_packet_tokens(locator_free_packet, token_counter) <= token_budget:
            raise ContextBudgetExceeded(
                f"evidence locator exceeds token budget: chunk:{hit.chunk_id}"
            )
        return None
    low, high = 1, len(content)
    best: EvidenceRecord | None = None
    while low <= high:
        middle = (low + high) // 2
        candidate_record = record_with_summary(content[:middle].rstrip())
        candidate_packet = _make_packet(
            task,
            token_budget,
            [*evidence, candidate_record],
            claims,
            constraints,
            exclusions,
        )
        if (
            candidate_record.summary
            and estimate_packet_tokens(candidate_packet, token_counter) <= token_budget
        ):
            best = candidate_record
            low = middle + 1
        else:
            high = middle - 1
    return best
