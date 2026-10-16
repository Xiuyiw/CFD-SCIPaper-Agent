import json
import shutil
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from cfdpaper.publication.figure_tasks import import_figure_task, prepare_figure_task


def _write_json(path, record):
    path.write_text(json.dumps(record), encoding="utf-8")
    return path


def _prepare(tmp_path, kind="schematic", output_mode=None):
    (tmp_path / "source.csv").write_text("case,value\nA,2\nB,3\n", encoding="utf-8")
    task = {
        "figure_id": "studio-example",
        "kind": kind,
        "purpose": "Show the declared comparison and its conceptual interpretation",
        "claim_ceiling": "Illustration of a hypothesis, not causal validation",
        "sources": [
            {"id": "values", "path": "source.csv", "role": "data", "description": "Two cases"}
        ],
        "labels": [{"text": "Value", "unit": "1"}],
    }
    if output_mode is not None:
        task["output_mode"] = output_mode
    return prepare_figure_task(_write_json(tmp_path / "input.json", task), tmp_path / "package")


def _delivery(tmp_path, editable_sources):
    returned = tmp_path / "returned"
    returned.mkdir()
    (returned / "plot.py").write_text("values = [2, 3]\n", encoding="utf-8")
    (returned / "figure.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><text x="2" y="12">Hypothesis</text></svg>',
        encoding="utf-8",
    )
    preview = Image.new("RGB", (320, 160), "white")
    ImageDraw.Draw(preview).line((20, 80, 300, 80), fill="black", width=3)
    preview.save(returned / "figure.png")
    return _write_json(
        returned / "delivery.json",
        {
            "figure_id": "studio-example",
            "editable_sources": editable_sources,
            "preview": "figure.png",
            "caption": "Conceptual interpretation of the two declared cases.",
        },
    )


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("kind", ["data", "schematic", "hybrid"])
def test_legacy_task_and_delivery_keep_editable_default(tmp_path, kind):
    package = _prepare(tmp_path, kind)
    task = _read_json(package / "task.json")
    template = _read_json(package / "delivery-template.json")
    assert task["output_mode"] == "editable"
    assert template["editable_sources"]
    source = "figure.svg" if kind == "schematic" else "plot.py"
    returned = _delivery(tmp_path, [source])
    candidate = import_figure_task(package, returned, tmp_path / "candidate")
    record = _read_json(candidate / "delivery.json")
    assert record["editable_available"] is True
    assert record["checks"]["editable_syntax"] is True
    assert record["scientific_approval"] is False
    assert all(record[name] == "" for name in ("title", "legend", "body_reference"))


def test_raster_concept_opt_in_reports_no_editable_source(tmp_path):
    package = _prepare(tmp_path, output_mode="raster_concept")
    assert _read_json(package / "delivery-template.json")["editable_sources"] == []
    returned = _delivery(tmp_path, [])
    candidate = import_figure_task(package, returned, tmp_path / "candidate")
    record = _read_json(candidate / "delivery.json")
    assert record["editable_sources"] == []
    assert record["editable_available"] is False
    assert record["checks"]["editable_syntax"] is False
    assert record["checks"]["preview_decoded_nonblank"] is True
    assert record["status"] == "imported_candidate"
    assert record["scientific_approval"] is False
    assert (candidate / "figure.png").read_bytes() == (returned.parent / "figure.png").read_bytes()
    assert (candidate / "sources/source.csv").read_bytes() == (tmp_path / "source.csv").read_bytes()
    assert not (candidate / "figure.svg").exists()
    assert not (candidate / "plot.py").exists()


@pytest.mark.parametrize("kind", ["data", "hybrid"])
def test_quantitative_tasks_reject_raster_concept_mode(tmp_path, kind):
    with pytest.raises(ValueError):
        _prepare(tmp_path, kind, output_mode="raster_concept")
    assert not (tmp_path / "package").exists()


@pytest.mark.parametrize("kind", ["data", "schematic", "hybrid"])
def test_default_editable_mode_rejects_empty_editable_sources(tmp_path, kind):
    package = _prepare(tmp_path, kind)
    returned = _delivery(tmp_path, [])
    with pytest.raises(ValueError):
        import_figure_task(package, returned, tmp_path / "candidate")
    assert not (tmp_path / "candidate").exists()


def test_hybrid_sources_and_companion_text_are_preserved(tmp_path):
    package = _prepare(tmp_path, "hybrid")
    returned = _delivery(tmp_path, ["plot.py", "figure.svg"])
    companion_text = {
        "title": "Paired comparison and proposed mechanism",
        "legend": "Solid values: source observations; arrow: mechanism hypothesis.",
        "body_reference": "Figure 1 distinguishes measured values from a proposed relation.",
        "caption": "Two source cases; the conceptual relation remains a hypothesis.",
    }
    _write_json(returned, {**_read_json(returned), **companion_text})
    candidate = import_figure_task(package, returned, tmp_path / "candidate")
    record = _read_json(candidate / "delivery.json")
    for name, text in companion_text.items():
        assert record[name] == text
    for name in ("plot.py", "figure.svg"):
        assert (candidate / name).read_bytes() == (returned.parent / name).read_bytes()
    assert record["editable_available"] is True
    assert record["scientific_approval"] is False


@pytest.mark.parametrize("kind", ["schematic", "hybrid"])
def test_studio_guidance_and_license_remain_portable(tmp_path, kind):
    package = _prepare(tmp_path, kind)
    relocated = tmp_path / "relocated figure package"
    shutil.move(package, relocated)
    relative_reference = Path("skills/cfd-figure-production/references/paper-framework-studio.md")
    reference = relocated / relative_reference
    notice = reference.with_name("paper-framework-studio-MIT-0.txt")
    prompt = (relocated / "prompt.md").read_text(encoding="utf-8")
    assert relative_reference.as_posix() in prompt
    assert "paper-framework-figure-studio-pro" in prompt
    assert reference.is_file() and reference.stat().st_size > 0
    assert notice.is_file() and notice.stat().st_size > 0
    assert "MIT" in notice.read_text(encoding="utf-8")
    task = _read_json(relocated / "task.json")
    assert all((relocated / source["path"]).is_file() for source in task["sources"])
