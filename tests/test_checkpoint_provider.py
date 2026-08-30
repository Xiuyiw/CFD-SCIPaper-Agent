import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from cfdpaper.contracts import EvidenceRecord
from cfdpaper.indexing import ProjectIndexer
from cfdpaper.providers import ProviderConfig, ProviderUnavailable, create_provider
from cfdpaper.state import initialize_project
from cfdpaper.storage import ProjectStore


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
