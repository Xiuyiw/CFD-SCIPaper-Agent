import hashlib
import json
import os
from pathlib import Path

import pytest

from cfdpaper.cache import ContentAddressedCache
from cfdpaper.indexing import ConcurrentModificationError, ProjectIndexer
from cfdpaper.retrieval import HybridRetriever
from cfdpaper.state import initialize_project
from cfdpaper.storage import SCHEMA_VERSION, ProjectStore


def test_incremental_index_tracks_hash_version_and_deleted_staleness(tmp_path: Path) -> None:
    initialize_project(tmp_path, "demo")
    source = tmp_path / "results.md"
    source.write_text("pressure drop is 12 Pa\n", encoding="utf-8")
    store = ProjectStore.open(tmp_path)
    indexer = ProjectIndexer(store)

    first = indexer.inspect()
    original = store.get_source("results.md")
    second = indexer.inspect()

    assert first.added == 1
    assert second.unchanged == 1
    assert original.sha256
    assert original.version == 1

    source.write_text("pressure drop is 10 Pa\n", encoding="utf-8")
    changed_stat = source.stat()
    os.utime(source, ns=(changed_stat.st_atime_ns, original.mtime_ns + 1_000_000))
    changed = indexer.inspect()
    current = store.get_source("results.md")

    assert changed.updated == 1
    assert current.version == 2
    assert current.sha256 != original.sha256
    assert store.source_version_count(current.source_id) == 2

    source.unlink()
    deleted = indexer.inspect()

    assert deleted.stale == 1
    assert store.get_source("results.md").stale is True


def test_indexer_chunks_text_and_only_records_binary_metadata(tmp_path: Path) -> None:
    initialize_project(tmp_path, "demo")
    (tmp_path / "notes.txt").write_text("alpha beta gamma", encoding="utf-8")
    (tmp_path / "case.cas.h5").write_bytes(b"\x00\x01\x02")
    store = ProjectStore.open(tmp_path)

    result = ProjectIndexer(store).inspect()

    assert result.discovered == 2
    assert store.chunk_count("notes.txt") == 1
    assert store.chunk_count("case.cas.h5") == 0


def test_manifest_version_matches_database_schema_and_index_populates_cache(tmp_path: Path) -> None:
    initialize_project(tmp_path, "demo")
    source = tmp_path / "notes.txt"
    source.write_text("cache this evidence", encoding="utf-8")
    store = ProjectStore.open(tmp_path)

    ProjectIndexer(store).inspect()

    manifest = json.loads(
        (tmp_path / ".cfdpaper" / "index_manifest.json").read_text(encoding="utf-8")
    )
    digest = store.get_source("notes.txt").sha256
    assert manifest["schema_version"] == SCHEMA_VERSION == store.schema_version
    assert ContentAddressedCache(tmp_path).read_bytes(digest) == b"cache this evidence"


def test_strict_hash_detects_same_size_same_mtime_tampering(tmp_path: Path) -> None:
    initialize_project(tmp_path, "demo")
    source = tmp_path / "results.txt"
    source.write_text("value=12", encoding="utf-8")
    store = ProjectStore.open(tmp_path)
    ProjectIndexer(store).inspect()
    original = store.get_source("results.txt")

    source.write_text("value=10", encoding="utf-8")
    stat = source.stat()
    os.utime(source, ns=(stat.st_atime_ns, original.mtime_ns))

    assert ProjectIndexer(store, strict_hash=False).inspect().unchanged == 1
    assert ProjectIndexer(store, strict_hash=True).inspect().updated == 1
    assert store.get_source("results.txt").version == 2


def test_scientific_and_publication_stages_default_to_strict_hash(tmp_path: Path) -> None:
    initialize_project(tmp_path, "demo")
    source = tmp_path / "results.txt"
    source.write_text("value=12", encoding="utf-8")
    store = ProjectStore.open(tmp_path)
    ProjectIndexer(store).inspect()
    original = store.get_source("results.txt")
    source.write_text("value=10", encoding="utf-8")
    stat = source.stat()
    os.utime(source, ns=(stat.st_atime_ns, original.mtime_ns))
    store.set_stage("write")

    result = ProjectIndexer(store).inspect()

    assert result.updated == 1


def test_strict_index_retries_and_chunks_the_same_cache_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initialize_project(tmp_path, "demo")
    source = tmp_path / "results.txt"
    source.write_text("phase=old", encoding="utf-8")
    store = ProjectStore.open(tmp_path)
    indexer = ProjectIndexer(store, strict_hash=True)
    original_put = indexer.cache.put_file
    calls = 0

    def mutate_after_first_snapshot(path: Path, *, expected_hash: str | None = None) -> Path:
        nonlocal calls
        snapshot = original_put(path, expected_hash=expected_hash)
        calls += 1
        if calls == 1:
            source.write_text("phase=new", encoding="utf-8")
        return snapshot

    monkeypatch.setattr(indexer.cache, "put_file", mutate_after_first_snapshot)

    result = indexer.inspect()
    stored = store.get_source("results.txt")
    hits = HybridRetriever(store).search("new")

    assert result.added == 1
    assert calls == 2
    assert stored.sha256 == hashlib.sha256(b"phase=new").hexdigest()
    assert hits and hits[0].content == "phase=new"


def test_strict_index_rejects_source_that_changes_during_both_attempts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initialize_project(tmp_path, "demo")
    source = tmp_path / "results.txt"
    source.write_text("phase=000", encoding="utf-8")
    store = ProjectStore.open(tmp_path)
    indexer = ProjectIndexer(store, strict_hash=True)
    original_put = indexer.cache.put_file
    calls = 0

    def mutate_every_snapshot(path: Path, *, expected_hash: str | None = None) -> Path:
        nonlocal calls
        snapshot = original_put(path, expected_hash=expected_hash)
        calls += 1
        source.write_text(f"phase={calls:03d}", encoding="utf-8")
        return snapshot

    monkeypatch.setattr(indexer.cache, "put_file", mutate_every_snapshot)

    with pytest.raises(ConcurrentModificationError, match="results.txt"):
        indexer.inspect()
    with pytest.raises(KeyError):
        store.get_source("results.txt")
