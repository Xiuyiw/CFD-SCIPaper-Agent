"""Incremental filesystem discovery and content indexing."""

from __future__ import annotations

import json
import mimetypes
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from cfdpaper.cache import ContentAddressedCache
from cfdpaper.storage import ProjectStore

TEXT_SUFFIXES = {
    ".csv",
    ".dat",
    ".json",
    ".log",
    ".md",
    ".rst",
    ".tex",
    ".tsv",
    ".txt",
    ".yaml",
    ".yml",
}
EXCLUDED_DIRECTORIES = {".cfdpaper", ".git", ".hg", ".svn", ".venv", "__pycache__"}
STRICT_HASH_STAGE_PREFIXES = ("analy", "figur", "writ", "review", "revis", "export", "publish")


@dataclass(frozen=True)
class InspectionResult:
    discovered: int = 0
    added: int = 0
    updated: int = 0
    unchanged: int = 0
    stale: int = 0


class ConcurrentModificationError(RuntimeError):
    """Raised when a source cannot be snapshotted consistently after one retry."""


class ProjectIndexer:
    def __init__(
        self,
        store: ProjectStore,
        *,
        chunk_chars: int = 2_000,
        strict_hash: bool | None = None,
    ) -> None:
        self.store = store
        self.chunk_chars = chunk_chars
        self.cache = ContentAddressedCache(store.root)
        stage = store.status().stage.casefold()
        self.strict_hash = (
            strict_hash if strict_hash is not None else stage.startswith(STRICT_HASH_STAGE_PREFIXES)
        )

    def discover(self) -> list[Path]:
        files: list[Path] = []
        for path in self.store.root.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(self.store.root)
            if any(part in EXCLUDED_DIRECTORIES for part in relative.parts):
                continue
            files.append(path)
        return sorted(files, key=lambda value: value.as_posix().casefold())

    def inspect(self) -> InspectionResult:
        files = self.discover()
        existing = {source.uri: source for source in self.store.list_sources()}
        seen: set[str] = set()
        added = updated = unchanged = 0
        for path in files:
            uri = path.relative_to(self.store.root).as_posix()
            seen.add(uri)
            stat = path.stat()
            previous = existing.get(uri)
            if (
                previous is not None
                and not previous.stale
                and previous.mtime_ns == stat.st_mtime_ns
                and previous.size_bytes == stat.st_size
                and not self.strict_hash
            ):
                if not self.cache.is_valid(previous.sha256):
                    self.cache.put_file(path, expected_hash=previous.sha256)
                unchanged += 1
                continue

            snapshot, stable_stat = self._stable_snapshot(path, uri)
            digest = snapshot.name
            chunks = self._chunks(snapshot) if path.suffix.casefold() in TEXT_SUFFIXES else []
            outcome = self.store.index_source(
                uri=uri,
                locator=uri,
                sha256=digest,
                mtime_ns=stable_stat.st_mtime_ns,
                size_bytes=stable_stat.st_size,
                media_type=mimetypes.guess_type(path.name)[0],
                chunks=chunks,
            )
            if outcome == "added":
                added += 1
            elif outcome == "updated":
                updated += 1
            else:
                unchanged += 1
        stale = self.store.mark_stale_except(seen)
        result = InspectionResult(len(files), added, updated, unchanged, stale)
        self._write_manifest(result)
        return result

    def _stable_snapshot(self, path: Path, uri: str) -> tuple[Path, os.stat_result]:
        for _attempt in range(2):
            try:
                before = path.stat()
                snapshot = self.cache.put_file(path)
                after_snapshot = path.stat()
                final_hash = self.cache.digest_file(path)
                after_hash = path.stat()
            except FileNotFoundError:
                continue
            stats_stable = _same_file_state(before, after_snapshot, after_hash)
            if stats_stable and final_hash == snapshot.name:
                return snapshot, after_hash
        raise ConcurrentModificationError(
            f"source changed while creating an immutable index snapshot: {uri}"
        )

    def _chunks(self, path: Path) -> list[tuple[str, str, int]]:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return []
        lines = text.splitlines()
        if not lines and text:
            lines = [text]
        chunks: list[tuple[str, str, int]] = []
        start = 0
        while start < len(lines):
            end = start
            size = 0
            while end < len(lines) and (
                size == 0 or size + len(lines[end]) + 1 <= self.chunk_chars
            ):
                size += len(lines[end]) + 1
                end += 1
            content = "\n".join(lines[start:end])
            if content.strip():
                chunks.append((content, f"lines:{start + 1}-{end}", _estimate_tokens(content)))
            start = end
        return chunks

    def _write_manifest(self, result: InspectionResult) -> None:
        manifest = {
            "schema_version": self.store.schema_version,
            "project_id": self.store.status().project_id,
            "inspection": asdict(result),
            "files": {
                source.uri: {
                    "sha256": source.sha256,
                    "mtime_ns": source.mtime_ns,
                    "size_bytes": source.size_bytes,
                    "version": source.version,
                    "stale": source.stale,
                }
                for source in self.store.list_sources()
            },
        }
        target = self.store.root / ".cfdpaper" / "index_manifest.json"
        target.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")


def _estimate_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4)


def _same_file_state(*stats: os.stat_result) -> bool:
    states = {(value.st_mtime_ns, value.st_size) for value in stats}
    return len(states) == 1
