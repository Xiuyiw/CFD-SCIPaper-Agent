import json

import pytest
from typer.testing import CliRunner

from cfdpaper.cli import app

runner = CliRunner()


@pytest.mark.parametrize("presentation", ["prose", "table", "custom"])
def test_presentation_choice_does_not_force_a_plot(tmp_path, presentation):
    root = study(tmp_path)
    package = tmp_path / "materials"
    run = runner.invoke(
        app, ["plan", str(root), "--artifact", "analysis", "--output", str(package)]
    )
    assert run.exit_code == 0, run.output
    for skill in ("cfd-qoi-physics", "cfd-figure-production"):
        assert (package / "skills" / skill / "SKILL.md").is_file()
    data = host_proposal()
    data["candidates"][0].update(
        presentation=presentation,
        presentation_reason="Integrated transfer and mean intensity answer different questions.",
        style={"body_first_line_indent_chars": 1, "body_space_after_pt": 3},
    )
    proposal = tmp_path / "proposal.json"
    proposal.write_text(json.dumps(data), encoding="utf-8")
    output = tmp_path / "selection"
    run = runner.invoke(
        app,
        [
            "plan",
            str(root),
            "--artifact",
            "analysis",
            "--package",
            str(package),
            "--proposal",
            str(proposal),
            "--select",
            "area-flux",
            "--output",
            str(output),
        ],
    )
    assert run.exit_code == 0, run.output
    writing = output / "section-input/writing"
    section = json.loads((writing / "input.json").read_text(encoding="utf-8"))
    assert section["figures"] == []
    assert section["style"]["body_first_line_indent_chars"] == 1
    assert section["style"]["body_space_after_pt"] == 3
    assert section["evidence"]
    assert (writing / "table-results.json").is_file()
    assert not list(output.rglob("*.png"))
    assert not list(output.rglob("plot_analysis.py"))
    if presentation == "custom":
        assert "pending" in section["context"]


def study(tmp_path):
    root = tmp_path / "study"
    root.mkdir()
    (root / "regions.csv").write_text(
        "case,region,area [m2],rate [W]\n"
        "Reference,lower,2,20\nReference,upper,3,30\n"
        "Modified,lower,4,28\nModified,upper,6,42\n",
        encoding="utf-8",
    )
    (root / "method.md").write_text(
        "Lower and upper are a disjoint, exhaustive partition of the wetted wall.\n"
        "area [m2] is face area; rate [W] is outward heat integrated over each region.\n"
        "The two geometries have the same inlet state and wall boundary condition.\n",
        encoding="utf-8",
    )
    return root


def host_proposal():
    return {
        "candidates": [
            {
                "id": "area-flux",
                "title": "Area and heat-rate response",
                "question": "Does larger heat rate imply larger mean flux?",
                "rationale": "Separate total transfer from intensity per area.",
                "calculations": [
                    {
                        "id": "wall",
                        "source": "sources/regions.csv",
                        "operation": "partition",
                        "columns": {"area": "area [m2]", "rate": "rate [W]"},
                        "units": {"area": "m2", "rate": "W"},
                        "group_by": "case",
                        "domain": "Disjoint full wetted wall partition, outward heat rate",
                        "definition_source": {"path": "sources/method.md", "locator": "L1-L3"},
                        "member_id": ["region"],
                        "expected_members": [["lower"], ["upper"]],
                        "expected_groups": ["Reference", "Modified"],
                        "comparison": {
                            "status": "supported",
                            "scope": "Geometry at fixed boundaries",
                        },
                        "interpretation_limits": [
                            "Q/area identity does not prove a mixing mechanism."
                        ],
                    }
                ],
                "metrics": [
                    {
                        "id": f"{field}-{group}",
                        "text": f"{field} for {group}",
                        "result_ref": {
                            "calculation_id": "wall",
                            "group": group,
                            "field": field,
                            "places": 2,
                        },
                    }
                    for field in ("rate", "mean_flux")
                    for group in ("Reference", "Modified")
                ],
                "interpretation_limits": [
                    "This is a synthetic comparison, not experimental validation."
                ],
            }
        ],
        "recommended_id": "area-flux",
        "gaps": [],
    }


def test_fresh_materials_to_analysis_to_docx_and_updated_source(tmp_path):
    pytest.importorskip("docx")
    root = study(tmp_path)
    package = tmp_path / "materials"
    run = runner.invoke(
        app,
        [
            "plan",
            str(root),
            "--artifact",
            "analysis",
            "--question",
            "Understand heat transfer",
            "--output",
            str(package),
        ],
    )
    assert run.exit_code == 0, run.output
    assert (package / "host-task.md").is_file()
    assert not (root / ".cfdpaper").exists()  # No shadow topic approval/state.
    proposal = tmp_path / "proposal.json"
    proposal.write_text(json.dumps(host_proposal()), encoding="utf-8")
    for iteration, expected in (("first", "50.00 W"), ("changed", "55.00 W")):
        if iteration == "changed":
            raw = package / "sources/regions.csv"
            raw.write_text(raw.read_text().replace("Reference,lower,2,20", "Reference,lower,2,25"))
        out = tmp_path / iteration
        run = runner.invoke(
            app,
            [
                "plan",
                str(root),
                "--artifact",
                "analysis",
                "--package",
                str(package),
                "--proposal",
                str(proposal),
                "--select",
                "area-flux",
                "--output",
                str(out),
            ],
        )
        assert run.exit_code == 0, run.output
        writing = out / "section-input/writing"
        data = json.loads((writing / "input.json").read_text())
        fig_ids = [f["id"] for f in data["figures"]]
        assert len(fig_ids) == 2
        draft = {
            "title": data["title"],
            "paragraphs": [
                {
                    "text": "The heat rate changes from {{value:rate-Reference}} to "
                    "{{value:rate-Modified}}, while the area-averaged flux changes from "
                    "{{value:mean_flux-Reference}} to {{value:mean_flux-Modified}}. "
                    "These are different quantities ({{figure:1}}, "
                    "{{figure:2}}).",
                    "evidence_ids": [e["id"] for e in data["evidence"]],
                    "figure_ids": fig_ids,
                }
            ],
            "captions": {f["id"]: f["caption"] for f in data["figures"]},
            "evidence_notes": [],
            "image_observations": dict.fromkeys(fig_ids, "not-viewed"),
        }
        dpath = out / "draft.json"
        dpath.write_text(json.dumps(draft), encoding="utf-8")
        base = ["write", str(root), "--artifact", "results-section"]
        section = out / "section"
        run = runner.invoke(
            app, [*base, "--package", str(writing), "--draft", str(dpath), "--output", str(section)]
        )
        assert run.exit_code == 0, run.output
        assert expected in (section / "section.md").read_text(encoding="utf-8")
        run = runner.invoke(
            app, [*base, "--package", str(section), "--docx", "--output", str(out / "section.docx")]
        )
        assert run.exit_code == 0, run.output
        assert (out / "section.docx").stat().st_size > 0


def test_inspect_profile_does_not_require_prearranged_project_records(tmp_path):
    root = study(tmp_path)
    output = tmp_path / "profile"
    result = runner.invoke(app, ["inspect", str(root), "--materials", "--output", str(output)])
    assert result.exit_code == 0, result.output
    summary = json.loads((output / "materials.json").read_text())
    assert summary["tables"][0]["row_count"] == 4


@pytest.mark.parametrize(
    "args",
    [
        ["--artifact", "analysis"],
        ["--question", "raw materials"],
        ["--artifact", "analysis", "--approve-topic", "x", "--output", "new"],
        ["--artifact", "analysis", "--select", "x", "--output", "new"],
        ["--artifact", "fiction"],
    ],
)
def test_analysis_and_topic_paths_do_not_mix(tmp_path, args):
    result = runner.invoke(app, ["plan", str(tmp_path), *args])
    assert result.exit_code != 0
    assert not (tmp_path / ".cfdpaper").exists()
