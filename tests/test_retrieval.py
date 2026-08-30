import sqlite3
from contextlib import contextmanager
from pathlib import Path

import pytest

from cfdpaper.contracts import ClaimRecord, EvidenceRecord
from cfdpaper.indexing import ProjectIndexer
from cfdpaper.retrieval import (
    ContextBudgetExceeded,
    HybridRetriever,
    SearchFilters,
    TaskContextBuilder,
    Utf8ByteTokenCounter,
    estimate_packet_tokens,
)
from cfdpaper.state import initialize_project
from cfdpaper.storage import ProjectStore


class SemanticSpy:
    enabled = True

    def __init__(self) -> None:
        self.candidate_ids: list[str] = []

    def search(self, query: str, candidate_ids: list[str], limit: int) -> dict[str, float]:
        self.candidate_ids = candidate_ids
        return {candidate_id: 0.2 for candidate_id in candidate_ids[:limit]}


class UnboundedSemanticBackend:
    enabled = True

    def search(self, query: str, candidate_ids: list[str], limit: int) -> dict[str, float]:
        return {
            candidate_id: score
            for candidate_id, score in zip(candidate_ids[:limit], (10.0, 100.0), strict=False)
        }


class CharacterTokenCounter:
    def count(self, text: str) -> int:
        return len(text)


def _indexed_store(tmp_path: Path) -> ProjectStore:
    initialize_project(tmp_path, "demo")
    (tmp_path / "authoritative.md").write_text(
        "Verified pressure drop decreases at the L10 condition.", encoding="utf-8"
    )
    (tmp_path / "unrelated.md").write_text("Mesh count is 1000 cells.", encoding="utf-8")
    store = ProjectStore.open(tmp_path)
    ProjectIndexer(store).inspect()
    store.set_source_authority("authoritative.md", 1.0)
    store.set_source_authority("unrelated.md", 0.1)
    return store


def test_hybrid_retrieval_uses_fts_and_source_filters_before_semantic(tmp_path: Path) -> None:
    store = _indexed_store(tmp_path)
    semantic = SemanticSpy()
    retriever = HybridRetriever(store, semantic_backend=semantic)

    hits = retriever.search(
        "pressure drop",
        filters=SearchFilters(source_uris=["authoritative.md"]),
        limit=5,
    )

    assert [hit.source_uri for hit in hits] == ["authoritative.md"]
    assert semantic.candidate_ids == [hits[0].chunk_id]
    assert hits[0].locator.startswith("lines:")


def test_default_retrieval_is_complete_without_semantic_dependencies(tmp_path: Path) -> None:
    store = _indexed_store(tmp_path)

    hits = HybridRetriever(store).search("pressure", limit=5)

    assert hits
    assert hits[0].source_uri == "authoritative.md"


def test_fts_ranks_higher_term_frequency_as_more_relevant(tmp_path: Path) -> None:
    initialize_project(tmp_path, "demo")
    (tmp_path / "frequent.md").write_text(
        "pressure pressure pressure pressure pressure combustion mesh flow", encoding="utf-8"
    )
    (tmp_path / "sparse.md").write_text(
        "pressure temperature velocity combustion reaction mesh flow outlet", encoding="utf-8"
    )
    store = ProjectStore.open(tmp_path)
    ProjectIndexer(store).inspect()

    hits = HybridRetriever(store).search("pressure", limit=2)

    assert [hit.source_uri for hit in hits] == ["frequent.md", "sparse.md"]


def test_retrieval_components_are_normalized_and_relevance_is_not_drowned(
    tmp_path: Path,
) -> None:
    initialize_project(tmp_path, "demo")
    (tmp_path / "relevant.md").write_text("pressure " * 20 + "mesh flow outlet", encoding="utf-8")
    (tmp_path / "weak.md").write_text(
        "pressure mesh temperature velocity reaction flow outlet", encoding="utf-8"
    )
    store = ProjectStore.open(tmp_path)
    ProjectIndexer(store).inspect()
    store.set_source_authority("relevant.md", 0.0)
    store.set_source_authority("weak.md", 1.0)

    hits = HybridRetriever(store).search("pressure", limit=2)

    assert hits[0].source_uri == "relevant.md"
    for hit in hits:
        assert 0.0 <= hit.fts_score <= 1.0
        assert 0.0 <= hit.semantic_score <= 1.0
        assert 0.0 <= hit.authority <= 1.0
        assert 0.0 <= hit.freshness <= 1.0
        assert 0.0 <= hit.score <= 1.0


def test_fts_handles_more_than_sqlite_default_candidate_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initialize_project(tmp_path, "demo")
    store = ProjectStore.open(tmp_path)
    store.index_source(
        uri="bulk.txt",
        locator="bulk.txt",
        sha256="a" * 64,
        mtime_ns=1,
        size_bytes=1,
        media_type="text/plain",
        chunks=[],
    )
    source_id = store.get_source("bulk.txt").source_id
    count = 33_000
    rows = [
        (
            f"chunk-{index}",
            source_id,
            index,
            "needle" if index == count - 1 else "hay",
            f"line:{index}",
            1,
        )
        for index in range(count)
    ]
    with store.connect() as connection:
        connection.executemany("INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?)", rows)
        connection.executemany(
            "INSERT INTO chunks_fts(chunk_id, source_id, content, locator) VALUES (?, ?, ?, ?)",
            [(row[0], row[1], row[3], row[4]) for row in rows],
        )
    original_connect = store.connect

    @contextmanager
    def limited_connection():
        with original_connect() as connection:
            setlimit = getattr(connection, "setlimit", None)
            if setlimit is not None:
                setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, 999)
            yield connection

    monkeypatch.setattr(store, "connect", limited_connection)

    hits = HybridRetriever(store).search("needle", limit=1)

    assert hits[0].chunk_id == f"chunk-{count - 1}"


def test_semantic_recall_receives_all_structured_candidates_after_fts(tmp_path: Path) -> None:
    store = _indexed_store(tmp_path)
    semantic = SemanticSpy()

    HybridRetriever(store, semantic_backend=semantic).search("pressure", limit=5)

    assert len(semantic.candidate_ids) == 2


def test_semantic_backend_scores_are_normalized_to_unit_interval(tmp_path: Path) -> None:
    store = _indexed_store(tmp_path)

    hits = HybridRetriever(store, semantic_backend=UnboundedSemanticBackend()).search(
        "pressure", limit=2
    )

    assert sorted(hit.semantic_score for hit in hits) == [0.0, 1.0]


def test_context_packet_honors_budget_locators_constraints_and_exclusions(tmp_path: Path) -> None:
    store = _indexed_store(tmp_path)
    builder = TaskContextBuilder(HybridRetriever(store))

    packet = builder.build(
        task="Compare pressure drop",
        query="pressure drop",
        token_budget=1_024,
        constraints=["Only report verified values"],
        exclusions=["stale sources"],
    )

    assert packet.token_budget == 1_024
    assert packet.constraints == ["Only report verified values"]
    assert packet.exclusions == ["stale sources"]
    assert packet.evidence
    assert packet.evidence[0].source_uri == "authoritative.md"
    assert packet.evidence[0].locator.startswith("lines:")


def test_context_packet_blocks_when_fixed_fields_exceed_budget(tmp_path: Path) -> None:
    store = _indexed_store(tmp_path)
    builder = TaskContextBuilder(HybridRetriever(store))

    with pytest.raises(ContextBudgetExceeded, match=r"constraints\[0\]"):
        builder.build(
            task="Compare pressure drop",
            query="pressure drop",
            token_budget=1_024,
            constraints=["x" * 1_200],
        )


def test_context_packet_blocks_when_locator_alone_exceeds_budget(tmp_path: Path) -> None:
    store = _indexed_store(tmp_path)
    store.save_evidence(
        EvidenceRecord(
            evidence_id="long-locator",
            source_uri="authoritative.md",
            locator="cell:" + "x" * 2_000,
            kind="qoi",
            summary="Pressure drop record.",
        )
    )

    with pytest.raises(ContextBudgetExceeded, match="locator"):
        TaskContextBuilder(HybridRetriever(store)).build(
            task="Compare pressure drop",
            query="pressure drop",
            token_budget=1_024,
        )


def test_context_packet_serialized_content_never_exceeds_budget(tmp_path: Path) -> None:
    store = _indexed_store(tmp_path)

    packet = TaskContextBuilder(HybridRetriever(store)).build(
        task="Compare pressure drop",
        query="pressure drop",
        token_budget=128,
    )
    assert estimate_packet_tokens(packet) <= packet.token_budget


def test_default_counter_uses_utf8_byte_upper_bound_for_mixed_text(tmp_path: Path) -> None:
    store = _indexed_store(tmp_path)
    packet = TaskContextBuilder(HybridRetriever(store)).build(
        task="比较压降 12.5 Pa：工况A/B！",
        query="pressure",
        token_budget=1_024,
    )
    serialized = packet.model_dump_json()

    assert Utf8ByteTokenCounter().count(serialized) == len(serialized.encode("utf-8"))
    assert estimate_packet_tokens(packet) == len(serialized.encode("utf-8"))
    assert estimate_packet_tokens(packet) <= packet.token_budget


def test_context_builder_uses_injected_provider_token_counter(tmp_path: Path) -> None:
    store = _indexed_store(tmp_path)
    counter = CharacterTokenCounter()

    packet = TaskContextBuilder(HybridRetriever(store), token_counter=counter).build(
        task="比较压降 12.5 Pa：工况A/B！",
        query="pressure",
        token_budget=128,
    )

    assert estimate_packet_tokens(packet, counter) <= packet.token_budget


def test_context_packet_includes_linked_structured_evidence_and_claims(tmp_path: Path) -> None:
    store = _indexed_store(tmp_path)
    store.save_evidence(
        EvidenceRecord(
            evidence_id="ev-pressure",
            source_uri="authoritative.md",
            locator="lines:1-1",
            kind="qoi",
            summary="Verified pressure-drop record.",
        )
    )
    store.save_claim(
        ClaimRecord(
            claim_id="claim-pressure",
            text="Pressure drop decreases at L10.",
            status="supported",
            evidence_ids=["ev-pressure"],
        )
    )

    packet = TaskContextBuilder(HybridRetriever(store)).build(
        task="Compare pressure drop",
        query="pressure drop",
        token_budget=1_024,
    )

    assert "ev-pressure" in {record.evidence_id for record in packet.evidence}
    assert packet.claims == [
        ClaimRecord(
            claim_id="claim-pressure",
            text="Pressure drop decreases at L10.",
            status="supported",
            evidence_ids=["ev-pressure"],
        )
    ]

    no_match = TaskContextBuilder(HybridRetriever(store)).build(
        task="Find absent evidence",
        query="nonexistent-term",
        token_budget=256,
    )
    assert no_match.evidence == []
    assert no_match.claims == []
