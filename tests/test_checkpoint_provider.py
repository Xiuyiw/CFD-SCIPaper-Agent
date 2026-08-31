import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from cfdpaper.cache import ContentAddressedCache
from cfdpaper.contracts import EvidenceRecord
from cfdpaper.indexing import ProjectIndexer
from cfdpaper.planning import PlanningWriteError, run_plan
from cfdpaper.providers import ProviderConfig, ProviderUnavailable, create_provider
from cfdpaper.retrieval import HybridRetriever, TaskContextBuilder
from cfdpaper.state import initialize_project
from cfdpaper.storage import ProjectStore
from cfdpaper.topic_generation.artifacts import recover_generation_bundle
from cfdpaper.topic_generation.canonical import canonical_sha256
from cfdpaper.topic_generation.service import TopicGenerationDependencies
from cfdpaper.topic_generation.snapshot import ScientificRecordSnapshot
from tests.topic_generation.factories import populated_scientific_store
from tests.topic_generation.test_opportunities import synthetic_snapshot
from tests.topic_generation.test_service import Counters, FakeProvider, _valid_provider_response


def _generated_snapshot(store: ProjectStore) -> ScientificRecordSnapshot:
    raw = synthetic_snapshot(values=(1.0, 2.0, 3.0)).model_dump(mode="python")
    raw["project_id"] = store.status().project_id
    raw["aggregate_sha256"] = canonical_sha256(
        {"project_id": raw["project_id"], "component_hashes": raw["component_hashes"]},
        domain=b"cfdpaper-scientific-snapshot-v1",
    )
    return ScientificRecordSnapshot.model_validate(raw)


def _generated_dependencies(
    store: ProjectStore,
    *,
    snapshot: ScientificRecordSnapshot | None = None,
    provider: FakeProvider | None = None,
) -> TopicGenerationDependencies:
    scientific_snapshot = snapshot or _generated_snapshot(store)
    return TopicGenerationDependencies(
        store=store,
        cache=ContentAddressedCache(store.root),
        context_builder=TaskContextBuilder(HybridRetriever(store)),
        provider=provider,
        provider_name=None if provider is None else provider.name,
        provider_model=None if provider is None else provider.model,
        snapshot_loader=lambda _store: scientific_snapshot,
        assert_plan_lock_held=lambda: True,
    )


def test_regenerate_retry_integrates_committed_revision_before_creating_next(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = populated_scientific_store(tmp_path)
    dependencies = _generated_dependencies(store)
    first = run_plan(tmp_path, provider_mode="offline", generation_dependencies=dependencies)
    original_transition = ProjectStore.save_workflow_transition

    def crash_after_report_before_sqlite(
        _store: ProjectStore, *_args: object, **_kwargs: object
    ) -> None:
        raise RuntimeError("injected after generation report before SQLite integration")

    monkeypatch.setattr(
        ProjectStore,
        "save_workflow_transition",
        crash_after_report_before_sqlite,
    )
    with pytest.raises(PlanningWriteError, match="injected after generation report"):
        run_plan(
            tmp_path,
            provider_mode="offline",
            regenerate=True,
            generation_dependencies=dependencies,
        )
    marker = recover_generation_bundle(
        project_root=tmp_path,
        expected_project_id=store.status().project_id,
    )
    assert marker is not None
    marker_revision = marker.report.generation_revision
    assert marker_revision == first.generation.report.generation_revision + 1

    monkeypatch.setattr(ProjectStore, "save_workflow_transition", original_transition)
    recovered = run_plan(
        tmp_path,
        provider_mode="offline",
        regenerate=True,
        generation_dependencies=dependencies,
    )
    next_revision = run_plan(
        tmp_path,
        provider_mode="offline",
        regenerate=True,
        generation_dependencies=dependencies,
    )

    assert recovered.generation.report.generation_revision == marker_revision
    assert next_revision.generation.report.generation_revision == marker_revision + 1


def test_regenerate_retry_reuses_committed_auto_revision_without_second_provider_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = populated_scientific_store(tmp_path)
    snapshot = _generated_snapshot(store)
    counters = Counters()
    provider = FakeProvider(_valid_provider_response(snapshot), counters)
    dependencies = _generated_dependencies(store, snapshot=snapshot, provider=provider)
    first = run_plan(tmp_path, provider_mode="offline", generation_dependencies=dependencies)
    original_transition = ProjectStore.save_workflow_transition

    def crash_after_report_before_sqlite(
        _store: ProjectStore, *_args: object, **_kwargs: object
    ) -> None:
        raise RuntimeError("injected after generation report before SQLite integration")

    monkeypatch.setattr(ProjectStore, "save_workflow_transition", crash_after_report_before_sqlite)
    with pytest.raises(PlanningWriteError, match="injected after generation report"):
        run_plan(
            tmp_path,
            provider_mode="auto",
            regenerate=True,
            generation_dependencies=dependencies,
        )
    marker = recover_generation_bundle(
        project_root=tmp_path,
        expected_project_id=store.status().project_id,
    )
    assert marker is not None
    assert marker.report.generation_revision == first.generation.report.generation_revision + 1
    assert counters.provider_calls == 1

    monkeypatch.setattr(ProjectStore, "save_workflow_transition", original_transition)
    recovered = run_plan(
        tmp_path,
        provider_mode="auto",
        regenerate=True,
        generation_dependencies=dependencies,
    )
    assert recovered.generation.reused is True
    assert recovered.generation.report.generation_revision == marker.report.generation_revision
    assert counters.provider_calls == 1

    next_revision = run_plan(
        tmp_path,
        provider_mode="auto",
        regenerate=True,
        generation_dependencies=dependencies,
    )

    assert (
        next_revision.generation.report.generation_revision == marker.report.generation_revision + 1
    )
    assert counters.provider_calls == 2


def test_checkpoint_resumes_in_a_new_process(tmp_path: Path) -> None:
    initialize_project(tmp_path, "demo")
    project_src = str(Path(__file__).parents[1] / "src")
    environment = {**os.environ, "PYTHONPATH": project_src}
    save_script = (
        "from pathlib import Path; from cfdpaper.storage import ProjectStore; "
        f"print(ProjectStore.open(Path({str(tmp_path)!r}))."
        "save_checkpoint('inspect', {'indexed': 4}))"
    )
    checkpoint_id = subprocess.run(
        [sys.executable, "-c", save_script],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    ).stdout.strip()
    resume_script = (
        "import json; from pathlib import Path; from cfdpaper.storage import ProjectStore; "
        f"c=ProjectStore.open(Path({str(tmp_path)!r})).resume_checkpoint(); "
        "print(json.dumps({'id': c.checkpoint_id, 'stage': c.stage, "
        "'payload': c.payload}))"
    )
    resumed = json.loads(
        subprocess.run(
            [sys.executable, "-c", resume_script],
            check=True,
            capture_output=True,
            text=True,
            env=environment,
        ).stdout
    )

    assert resumed == {
        "id": checkpoint_id,
        "stage": "inspect",
        "payload": {"indexed": 4},
    }


def test_plan_checkpoint_resumes_in_a_new_process(tmp_path: Path) -> None:
    initialize_project(tmp_path, "demo")
    source = tmp_path / "results.csv"
    source.write_text("case,dp\nA,12\n", encoding="utf-8")
    store = ProjectStore.open(tmp_path)
    ProjectIndexer(store).inspect()
    stored = store.get_source("results.csv")
    store.save_evidence(
        EvidenceRecord(
            evidence_id="ev-01",
            source_uri="results.csv",
            locator="row:2",
            source_hash=stored.sha256,
            kind="qoi",
            summary="pressure loss",
            maturity="verified",
        )
    )
    candidates = tmp_path / ".cfdpaper" / "inputs" / "topic_candidates.json"
    candidates.parent.mkdir(parents=True)
    candidates.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "candidates": [
                    {
                        "topic_id": "topic-01",
                        "title": "Pressure-loss comparison",
                        "research_question": ("How does configuration affect pressure loss?"),
                        "supporting_evidence_ids": ["ev-01"],
                        "required_evidence_kinds": ["qoi"],
                        "required_maturity": "verified",
                        "minimum_verified_evidence": 1,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    project_src = str(Path(__file__).parents[1] / "src")
    environment = {**os.environ, "PYTHONPATH": project_src}
    plan_script = (
        "import pathlib; import cfdpaper; "
        f"project_src=pathlib.Path({project_src!r}).resolve(); "
        "assert pathlib.Path(cfdpaper.__file__).resolve().is_relative_to(project_src); "
        "from pathlib import Path; from cfdpaper.planning import run_plan; "
        f"print(run_plan(Path({str(tmp_path)!r})).checkpoint_id)"
    )
    checkpoint_id = subprocess.run(
        [sys.executable, "-c", plan_script],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    ).stdout.strip()
    resume_script = (
        "import json; import pathlib; import cfdpaper; "
        f"project_src=pathlib.Path({project_src!r}).resolve(); "
        "assert pathlib.Path(cfdpaper.__file__).resolve().is_relative_to(project_src); "
        "from pathlib import Path; from cfdpaper.storage import ProjectStore; "
        f"s=ProjectStore.open(Path({str(tmp_path)!r})); "
        f"c=s.resume_checkpoint({checkpoint_id!r}); "
        "print(json.dumps({'stage': c.stage, 'payload': c.payload, "
        "'project_stage': s.status().stage}))"
    )
    resumed = json.loads(
        subprocess.run(
            [sys.executable, "-c", resume_script],
            check=True,
            capture_output=True,
            text=True,
            env=environment,
        ).stdout
    )

    assert resumed["stage"] == "plan"
    assert resumed["payload"]["inspection"]["mode"] == "fast"
    assert resumed["payload"]["plan_fingerprint"]
    assert resumed["payload"]["report_path"].endswith("topic-ranking.json")
    assert resumed["project_stage"] == "planned"


@pytest.mark.parametrize(
    ("name", "class_name"),
    [
        ("openai", "OpenAIProvider"),
        ("deepseek", "DeepSeekProvider"),
        ("gemini", "GeminiProvider"),
        ("claude", "ClaudeProvider"),
        ("local", "LocalProvider"),
    ],
)
def test_provider_placeholders_do_not_require_keys_until_generation(
    name: str, class_name: str
) -> None:
    provider = create_provider(ProviderConfig(name=name, api_key=None))

    assert type(provider).__name__ == class_name
    assert provider.available is False
    with pytest.raises(ProviderUnavailable):
        provider.generate("hello")


def test_configured_placeholder_provider_does_not_claim_availability() -> None:
    provider = create_provider(ProviderConfig(name="openai", api_key="configured-key"))

    assert provider.configured is True
    assert provider.available is False
    with pytest.raises(ProviderUnavailable, match="placeholder"):
        provider.generate("hello")
