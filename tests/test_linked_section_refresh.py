"""A source change must follow the reader's actual figure and prose, not every object."""

import csv
import json
import shutil
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from zipfile import ZipFile

import pytest
from typer.testing import CliRunner

from cfdpaper.cli import app
from cfdpaper.publication.linked_section import _patch_table, refresh_section


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    example = (
        Path(__file__).resolve().parents[1] / "examples/material-analysis/run_linked_refresh.py"
    )
    spec = spec_from_file_location("linked_example", example)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    root = tmp_path_factory.mktemp("linked") / "example"
    module.run(root)
    return root


def test_source_reaches_only_its_local_script_caption_and_paragraph(demo):
    after, before = demo / "after", demo / "before"
    report = read(after / "refresh.json")
    assert {(s["recipe_id"], s["status"]) for s in report["figure_recipes"]} == {
        ("rate", "executed"),
        ("area", "unchanged"),
    }
    assert set(report["changed_results"]) == {"rate-Modified"}
    assert report["changed_images"] == ["1"]
    assert {(r["kind"], r["id"]) for r in report["readers_to_review"]} == {
        ("caption", "1"),
        ("paragraph", "rate"),
    }
    for relative in ["comparison.png", "comparison.svg", "display.csv", "plot.py"]:
        assert (after / "workspace/area" / relative).read_bytes() == (
            before / "workspace/area" / relative
        ).read_bytes()
    assert (after / "workspace/rate/plot.py").read_bytes() == (
        demo / "edited/rate/plot.py"
    ).read_bytes()
    assert "#a65338" in (after / "workspace/rate/comparison.svg").read_text(encoding="utf-8")
    out = read(after / "section/section.json")
    assert "75.0 W" in out["paragraphs"][0]["text"] and "75.0 W" in out["figures"][0]["caption"]
    assert out["paragraphs"][1]["text"].endswith(
        "Both values refer to the same declared wall partition."
    )
    assert "70.0 W" in (before / "section/section.md").read_text(encoding="utf-8")
    with (after / "workspace/rate/display.csv").open(encoding="utf-8", newline="") as f:
        assert [(r["case"], float(r["reading"]), r["author_label"]) for r in csv.DictReader(f)] == [
            ("Modified", 75, "Modified layout"),
            ("Reference", 50, "Reference layout"),
        ]
    with ZipFile(after / "section.docx") as z:
        images = [z.read(n) for n in z.namelist() if n.startswith("word/media/")]
        assert (after / "workspace/rate/comparison.png").read_bytes() in images
        assert (before / "workspace/area/comparison.png").read_bytes() in images
        assert b"75.0" in z.read("word/document.xml")


def test_cli_prose_only_change_does_not_launch_a_recipe(demo, tmp_path):
    old = demo / "after"
    work = tmp_path / "work"
    shutil.copytree(old / "workspace", work)
    draft = read(work / "draft.json")
    draft["captions"]["2"] += " Author clarification."
    draft["image_observations"]["2"] = "viewed"
    draft.setdefault("observation_notes", {})["2"] = "The two saved areas can be distinguished."
    (work / "draft.json").write_text(json.dumps(draft), encoding="utf-8")
    out = tmp_path / "candidate"
    run = CliRunner().invoke(
        app, ["refresh-section", str(work), "--baseline", str(old), "--output", str(out)]
    )
    assert run.exit_code == 0, run.output
    statuses = read(out / "refresh.json")
    assert statuses["calculation"] == "reused"
    assert not statuses["changed_results"] and not statuses["readers_to_review"]
    assert all(r["status"] == "unchanged" for r in statuses["figure_recipes"])
    assert (out / "workspace/draft.json").read_bytes() == (work / "draft.json").read_bytes()
    assert read(out / "section/section.json")["figures"][1]["caption"].endswith(
        "Author clarification."
    )


def test_reversed_reading_stops_at_exact_author_object(demo, tmp_path):
    work = tmp_path / "work"
    shutil.copytree(demo / "after/workspace", work)
    src = work / "sources/regions.csv"
    src.write_text(src.read_text().replace("Modified,upper,6,42", "Modified,upper,6,1"))
    with pytest.raises(ValueError, match="Revise paragraph 'rate'"):
        refresh_section(work, tmp_path / "blocked", baseline=demo / "after")
    assert not (tmp_path / "blocked").exists()
    assert "greater" in read(work / "draft.json")["paragraphs"][0]["text"]


def test_display_change_redraws_just_its_figure_without_new_scientific_values(demo, tmp_path):
    base = demo / "before"
    work = tmp_path / "current"
    shutil.copytree(base / "workspace", work)
    panel = {
        "figure_id": "1",
        "panel": "local",
        "source": "rate/display.csv",
        "values": "reading",
        "quantity": "heat rate",
        "unit": "W",
        "source_kind": "reduced-table",
        "use": "visual-reading",
        "scale": {
            "knots": [0, 100],
            "positions": [0, 1],
            "colors": ["white", "blue"],
            "clipping": "forbid",
        },
    }
    path = work / "display-evidence.json"
    path.write_text(json.dumps([panel]), encoding="utf-8")
    first = tmp_path / "display"
    out = refresh_section(work, first, baseline=base)
    assert out["calculation"] == "reused" and not out["changed_results"]
    assert [(r["recipe_id"], r["status"]) for r in out["figure_recipes"]] == [
        ("rate", "executed"),
        ("area", "unchanged"),
    ]
    assert out["changed_panel_readings"] == [{"figure_id": "1", "panel": "local"}]
    returned = refresh_section(first / "workspace", tmp_path / "unchanged", baseline=first)
    assert not returned["readers_to_review"] and not returned["changed_panel_readings"]


def test_redefined_domain_with_identical_numbers_needs_new_figure_reading(demo, tmp_path):
    work = tmp_path / "work"
    shutil.copytree(demo / "before/workspace", work)
    data = read(work / "input.json")
    data["table_calculations"][0]["domain"] = "Different selected wall"
    (work / "input.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="physical definition changed"):
        refresh_section(work, tmp_path / "new", baseline=demo / "before")
    assert not (tmp_path / "new").exists()


def test_reconcile_selected_region_updates_actual_figure_caption_and_text(demo, tmp_path):
    """An upper-region comparison is not a new value of the whole-wall integral."""
    work = tmp_path / "current"
    base = demo / "before"
    shutil.copytree(base / "workspace", work)
    data = read(work / "input.json")
    data["table_calculations"][0].update(row_filters={"region": "upper"}, domain="Upper patch only")
    data["mechanism_questions"] = [
        {
            "question": "Did local heat transport change with area?",
            "diagnostics": ["rate-Reference", "area-Reference"],
        }
    ]
    (work / "input.json").write_text(json.dumps(data), encoding="utf-8")
    draft = read(work / "draft.json")
    draft["paragraphs"].append(
        {
            "paragraph_id": "note",
            "text": "Author correction outside this comparison.",
            "figure_ids": [],
            "evidence_ids": [],
        }
    )
    (work / "draft.json").write_text(json.dumps(draft), encoding="utf-8")
    plan = refresh_section(work, tmp_path / "inspect", baseline=base, inspect_change=True)
    assert [p.name for p in (tmp_path / "inspect").iterdir()] == ["reconcile.json"]
    assert plan["basis"]["results"]["rate-Modified"]["after"]["raw_value"] == 42
    assert plan["basis"]["results"]["rate-Modified"]["before"]["raw_value"] == 70
    context = plan["mechanism_questions"][0]["located_results"]
    assert context["area-Reference"]["domains"] == ["Upper patch only"]
    assert context["rate-Reference"]["value"] == "30.0"
    for f in plan["figures"]:
        f["reading"] = "The two markers refer only to the upper patch, not the whole wall."
    for item in plan["readers"]:
        item["after"] = "On the upper patch: " + item["before"]
    assert not any(item["id"] == "note" for item in plan["readers"])
    import copy

    partial = copy.deepcopy(plan)
    partial["readers"].pop()
    with pytest.raises(ValueError, match="Incomplete"):
        refresh_section(work, tmp_path / "partial", baseline=base, reconciliation=partial)
    # An intervening edit to a targeted sentence must survive rather than being overwritten.
    altered = copy.deepcopy(draft)
    altered["paragraphs"][0]["text"] += " Author's late addition."
    (work / "draft.json").write_text(json.dumps(altered), encoding="utf-8")
    with pytest.raises(ValueError, match="target changed"):
        refresh_section(work, tmp_path / "conflict", baseline=base, reconciliation=plan)
    assert not (tmp_path / "conflict").exists()
    (work / "draft.json").write_text(json.dumps(draft), encoding="utf-8")
    out = tmp_path / "revised"
    refresh_section(work, out, baseline=base, reconciliation=plan, docx=True)
    result = read(out / "section/section.json")
    assert result["paragraphs"][0]["text"].startswith("On the upper patch:")
    assert "42.0 W" in result["figures"][0]["caption"]
    assert result["paragraphs"][-1]["text"] == "Author correction outside this comparison."
    assert (out / "workspace/rate/plot.py").read_bytes() == (work / "rate/plot.py").read_bytes()
    assert result["image_observations"] == {"1": "not-viewed", "2": "not-viewed"}
    baseline_render = (base / "section/section.md").read_text(encoding="utf-8")
    assert "70.0 W" in baseline_render and "On the upper patch:" not in baseline_render


def test_percent_conversion_is_explicit_full_precision_not_formatting_or_unit_guess(tmp_path):
    path = tmp_path / "plot.csv"
    path.write_text("case,v,extra\nb,0,keep\na,0,other\n", encoding="utf-8")
    binding = {
        "row_key": "case",
        "columns": {"v": {"unit": "%", "by_row": {"a": "frac", "b": "native"}}},
    }
    metrics = {
        "frac": {"unit": "%", "raw_value": 0.075321, "value": "7.5", "ref": {"percentage": True}},
        "native": {"unit": "%", "raw_value": 41.5, "value": "41.5", "ref": {"percentage": False}},
    }
    _patch_table(path, binding, metrics)
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert [float(r["v"]) for r in rows] == pytest.approx([41.5, 7.5321])
    assert rows[1]["extra"] == "other"
    binding["columns"]["v"]["by_row"] = {"not-present": "frac"}
    with pytest.raises(ValueError, match="Missing author table keys"):
        _patch_table(path, binding, metrics)
    binding["columns"]["v"] = {"unit": "Pa", "by_row": {"a": "frac", "b": "native"}}
    with pytest.raises(ValueError, match="unit mismatch"):
        _patch_table(path, binding, metrics)
    binding["columns"]["v"] = {"unit": "%", "by_row": {"a": "frac"}, "fixed": {"b": 41.5}}
    _patch_table(path, binding, metrics)
    binding["columns"]["v"]["fixed"]["b"] = 0
    with pytest.raises(ValueError, match="Fixed author cell differs"):
        _patch_table(path, binding, metrics)
