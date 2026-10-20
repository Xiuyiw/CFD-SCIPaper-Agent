import json
import re
import sys
from pathlib import Path
from types import ModuleType

import numpy as np
import pytest
from typer.testing import CliRunner

from cfdpaper.cli import app

runner = CliRunner()


@pytest.fixture
def workspace_backend(monkeypatch):
    backend = ModuleType("cfdpaper.publication.research_workspace")
    calls = []

    def prepare(study_path, output_dir):
        calls.append(("prepare", study_path, output_dir))

    def build(workspace_dir, output_dir, baseline_dir=None, **kwargs):
        calls.append(("build", workspace_dir, output_dir, baseline_dir, kwargs))

    def attach(workspace_dir, imported_dir, output_dir, **kwargs):
        calls.append(("attach", workspace_dir, imported_dir, output_dir, kwargs))

    def diagnostics(workspace_dir, config, output_dir):
        calls.append(("diagnostics", workspace_dir, config, output_dir))

    backend.prepare_surface_workspace = prepare
    backend.build_research_workspace = build
    backend.attach_imported_figure = attach
    backend.attach_research_diagnostics = diagnostics
    monkeypatch.setitem(sys.modules, backend.__name__, backend)
    return backend, calls


def test_diagnostic_attachment_forwards_without_building(tmp_path, workspace_backend):
    _, calls = workspace_backend
    workspace, config, output = (
        tmp_path / name for name in ("workspace", "diagnostics.json", "out")
    )
    result = runner.invoke(
        app,
        [
            "research",
            "--workspace",
            str(workspace),
            "--diagnostics",
            str(config),
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert calls == [("diagnostics", workspace, config, output)]
    assert "physical diagnostics ready" in result.stdout


@pytest.mark.parametrize("other", [["--baseline", "old"], ["--attach-figure", "figure"]])
def test_diagnostic_attachment_rejects_combined_actions(other, workspace_backend):
    _, calls = workspace_backend
    result = runner.invoke(
        app,
        [
            "research",
            "--workspace",
            "work",
            "--diagnostics",
            "config.json",
            "--output",
            "out",
            *other,
        ],
    )
    assert result.exit_code == 2
    assert calls == []


def test_prepare_thin_entrypoint_explains_host_writing(tmp_path, workspace_backend):
    _, calls = workspace_backend
    study, output = tmp_path / "study.json", tmp_path / "workspace[author]"
    result = runner.invoke(app, ["research", "--study", str(study), "--output", str(output)])
    assert result.exit_code == 0, result.stdout + result.stderr
    assert calls == [("prepare", study, output)]
    assert "Research workspace ready" in result.stdout
    assert "Host writing required" in result.stdout and "drafts.json" in result.stdout
    assert "[author]" in result.stdout  # User paths are not Rich markup.


@pytest.mark.parametrize("use_baseline", [False, True])
def test_build_thin_entrypoint_forwards_optional_baseline(
    tmp_path, workspace_backend, use_baseline
):
    _, calls = workspace_backend
    workspace, output = tmp_path / "workspace", tmp_path / "build"
    baseline = tmp_path / "previous" if use_baseline else None
    args = ["research", "--workspace", str(workspace), "--output", str(output)]
    if baseline:
        args.extend(["--baseline", str(baseline)])
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.stdout + result.stderr
    assert calls == [("build", workspace, output, baseline, {})]
    assert "Research candidate assembled" in result.stdout
    assert "approved" not in result.stdout.lower()


def test_research_build_forwards_recovered_author_candidate(tmp_path, workspace_backend):
    _, calls = workspace_backend
    workspace, output, author = (tmp_path / p for p in ("workspace", "build", "author"))
    result = runner.invoke(
        app,
        [
            "research",
            "--workspace",
            str(workspace),
            "--output",
            str(output),
            "--author-candidate",
            str(author),
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert calls == [("build", workspace, output, None, {"author_candidate": author})]


def test_author_candidate_does_not_get_ignored_in_prepare(workspace_backend):
    _, calls = workspace_backend
    result = runner.invoke(
        app,
        ["research", "--study", "study.json", "--author-candidate", "author", "--output", "out"],
    )
    assert result.exit_code == 2
    assert "--author-candidate requires" in result.stdout
    assert calls == []


@pytest.mark.parametrize("viewed", [False, True])
def test_attach_figure_forwards_host_choices_without_building(tmp_path, workspace_backend, viewed):
    _, calls = workspace_backend
    work, imported, output = (tmp_path / name for name in ("workspace", "imported", "attached"))
    args = [
        "research",
        "--workspace",
        str(work),
        "--attach-figure",
        str(imported),
        "--section",
        "discussion",
        "--evidence",
        "observation-A",
        "--evidence",
        "method",
        "--paragraph-index",
        "1",
        "--output",
        str(output),
    ]
    if viewed:
        args.extend(["--viewed", "--observation-note", "Read labels and directional arrows."])
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.stdout + result.stderr
    assert calls == [
        (
            "attach",
            work,
            imported,
            output,
            {
                "section_id": "discussion",
                "evidence_ids": ["observation-A", "method"],
                "paragraph_index": 1,
                "image_observation": "viewed" if viewed else "not-viewed",
                "observation_note": "Read labels and directional arrows." if viewed else "",
            },
        )
    ]
    assert "Research workspace with figure ready" in result.stdout
    assert "approved" not in result.stdout.lower()


@pytest.mark.parametrize(
    "options,detail",
    [
        (["--study", "study.json", "--attach-figure", "figure"], "requires --workspace"),
        (["--workspace", "work", "--attach-figure", "figure"], "requires --section"),
        (
            [
                "--workspace",
                "work",
                "--attach-figure",
                "figure",
                "--section",
                "results",
                "--baseline",
                "old",
            ],
            "separate build",
        ),
        (["--workspace", "work", "--section", "results"], "require --attach-figure"),
        (["--workspace", "work", "--evidence", "a"], "require --attach-figure"),
        (["--workspace", "work", "--viewed"], "require --attach-figure"),
        (["--workspace", "work", "--paragraph-index", "0"], "require --attach-figure"),
        (["--workspace", "work", "--observation-note", "read"], "require --attach-figure"),
    ],
)
def test_attach_options_reject_ignored_arguments(options, detail, workspace_backend):
    _, calls = workspace_backend
    result = runner.invoke(app, ["research", *options, "--output", "out"])
    assert result.exit_code == 2
    plain = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout + result.stderr)
    assert detail in plain
    assert calls == []


@pytest.mark.parametrize(
    "options,detail",
    [
        (["--output", "out"], "exactly one"),
        (["--study", "study.json", "--workspace", "workspace", "--output", "out"], "exactly one"),
        (["--study", "study.json", "--baseline", "old", "--output", "out"], "--baseline requires"),
        (["--study", "study.json"], "--output"),
    ],
)
def test_research_options_reject_ambiguity_before_backend(options, detail, workspace_backend):
    _, calls = workspace_backend
    result = runner.invoke(app, ["research", *options])
    assert result.exit_code == 2
    plain = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout + result.stderr)
    assert detail in plain
    assert calls == []


@pytest.mark.parametrize(
    "error,code",
    [
        (FileNotFoundError("missing study"), 2),
        (ValueError("incompatible surface domains"), 3),
        (RuntimeError("author plot failed"), 1),
    ],
)
def test_research_uses_existing_error_exit_codes(error, code, workspace_backend):
    backend, _ = workspace_backend

    def fail(*args):
        raise error

    backend.prepare_surface_workspace = fail
    result = runner.invoke(app, ["research", "--study", "study.json", "--output", "out"])
    assert result.exit_code == code
    assert str(error) in result.stdout
    assert "Traceback" not in result.stdout + result.stderr


def test_research_help_exposes_only_bounded_actions():
    result = runner.invoke(app, ["research", "--help"], terminal_width=160)
    assert result.exit_code == 0
    plain = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
    for option in ("--study", "--workspace", "--output", "--baseline"):
        assert option in plain
    assert "NPZ" in plain and "host-written" in plain


def test_research_documentation_has_both_user_actions():
    document = Path(__file__).resolve().parents[1] / "docs/research-workspace.md"
    text = document.read_text(encoding="utf-8")
    assert "cfdpaper research --study" in text
    assert "cfdpaper research --workspace" in text
    assert "drafts.json" in text and "NPZ" in text


def test_documented_surface_study_runs_prepare_and_build_through_cli(tmp_path):
    pytest.importorskip("docx")
    document = Path(__file__).resolve().parents[1] / "docs/research-workspace.md"
    study = json.loads(
        re.search(r"```json\n(.*?)\n```", document.read_text(encoding="utf-8"), flags=re.DOTALL)[1]
    )
    materials = tmp_path / "materials"
    (materials / "sources").mkdir(parents=True)
    (materials / "sources/definition.md").write_text(
        "Synthetic software fixture: face temperatures and supplied areas on a common wall.\n",
        encoding="utf-8",
    )
    vertices = [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0], [4, 0, 0], [4, 1, 0]]
    for index, case in enumerate(study["cases"]):
        np.savez(
            materials / case["source"],
            face_value=[300.0 + index * 10, 400.0 + index * 10],
            area_m2=[1.0, 3.0],
            vertices_m=vertices,
            faces_connectivity=[4, 0, 1, 2, 3, 4, 1, 4, 5, 2],
            face_starts=[0, 5],
        )
    source_bytes = (materials / "sources/A.npz").read_bytes()
    study_path = materials / "study.json"
    study_path.write_text(json.dumps(study), encoding="utf-8")
    workspace, build = tmp_path / "workspace", tmp_path / "build"
    prepared = runner.invoke(
        app, ["research", "--study", str(study_path), "--output", str(workspace)]
    )
    assert prepared.exit_code == 0, prepared.stdout + prepared.stderr
    drafts = json.loads((workspace / "drafts.json").read_text(encoding="utf-8"))
    assert set(drafts) == {"methods", "results", "discussion", "conclusion"}
    for draft_name in drafts.values():
        draft_path = workspace / draft_name
        draft = json.loads(draft_path.read_text(encoding="utf-8"))
        section = json.loads((draft_path.parent / "input.json").read_text(encoding="utf-8"))
        assert all(not paragraph["text"] for paragraph in draft["paragraphs"])
        figures = section["figures"]
        draft["paragraphs"] = [
            {
                "text": "Synthetic integration fixture. "
                + " ".join(
                    "{{value:" + evidence["id"] + "}}"
                    for evidence in section["evidence"]
                    if evidence["kind"] == "metric"
                )
                + " "
                + " ".join("{{figure:" + figure["id"] + "}}" for figure in figures),
                "evidence_ids": [evidence["id"] for evidence in section["evidence"]],
                "figure_ids": [figure["id"] for figure in figures],
            }
        ]
        draft["captions"] = {figure["id"]: figure["caption"] for figure in figures}
        draft["image_observations"] = {figure["id"]: "author-provided" for figure in figures}
        draft_path.write_text(json.dumps(draft), encoding="utf-8")
    built = runner.invoke(app, ["research", "--workspace", str(workspace), "--output", str(build)])
    assert built.exit_code == 0, built.stdout + built.stderr
    assert (build / "manuscript.docx").is_file()
    assert (build / "manuscript/section.json").is_file()
    assert (build / "workspace/sections/results/figures/field.svg").is_file()
    assert (materials / "sources/A.npz").read_bytes() == source_bytes
