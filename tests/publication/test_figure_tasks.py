import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from cfdpaper.publication.figure_tasks import import_figure_task, prepare_figure_task
from cfdpaper.publication.style import FigureSizing, PublicationStyle, figure_placement


def write_json(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def make_task(tmp_path, kind="data"):
    (tmp_path / "data.csv").write_text("case,x,y\nA,1,2\nB,2,3\n", encoding="utf-8")
    return {
        "figure_id": "f1",
        "kind": kind,
        "purpose": "Compare paired observations and their mechanism hypothesis",
        "claim_ceiling": "Discrete observations only; no causal proof",
        "sources": [
            {"id": "raw", "path": "data.csv", "role": "data", "description": "Paired rows"}
        ],
        "labels": [{"text": "Mass flow", "unit": "kg/s"}],
        "relationships": [
            {"from": "Inlet", "to": "Outlet", "meaning": "Flow direction", "status": "method"}
        ],
    }


def prepare(tmp_path, kind="data"):
    data = make_task(tmp_path, kind)
    path = write_json(tmp_path / "input.json", data)
    return prepare_figure_task(path, tmp_path / "package")


def delivery(tmp_path, kind="data"):
    root = tmp_path / "returned"
    root.mkdir()
    (root / "plot.py").write_text(
        "from pathlib import Path\nPath('EXECUTED').touch()\n", encoding="utf-8"
    )
    (root / "figure.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
        '<text x="10" y="20">Flow</text></svg>',
        encoding="utf-8",
    )
    image = Image.new("RGB", (100, 60), "white")
    ImageDraw.Draw(image).line((10, 20, 80, 40), fill="black", width=2)
    image.save(root / "preview.png")
    return write_json(
        root / "return.json",
        {
            "figure_id": "f1",
            "editable_sources": ["figure.svg" if kind == "schematic" else "plot.py"],
            "preview": "preview.png",
            "caption": "Discrete source observations; arrow is a method relation.",
            "notes": ["Preview inspected separately by the host"],
        },
    )


@pytest.mark.parametrize("kind", ["data", "schematic", "hybrid"])
def test_portable_task_and_candidate_delivery(tmp_path, kind):
    package = prepare(tmp_path, kind)
    task = json.loads((package / "task.json").read_text())
    assert task["sources"][0]["original_path"] == "data.csv"
    copied = package / task["sources"][0]["path"]
    assert copied.read_bytes() == (tmp_path / "data.csv").read_bytes()
    assert task["labels"] == [{"text": "Mass flow", "unit": "kg/s"}]
    refs = package / "skills/cfd-figure-production/references"
    assert "Deliberate changes" in (refs / "editable-schematic-adaptation.md").read_text()
    assert "Copyright (c) 2026" in (refs / "codex-paper-figure-MIT.txt").read_text()
    assert "never ask an image" in (package / "prompt.md").read_text()
    returned = delivery(tmp_path, kind)
    result = import_figure_task(package, returned, tmp_path / "imported")
    record = json.loads((result / "delivery.json").read_text())
    assert record["status"] == "imported_candidate"
    assert record["scientific_approval"] is False
    assert (result / "sources/data.csv").read_bytes() == (tmp_path / "data.csv").read_bytes()
    assert (result / record["editable_sources"][0]).read_bytes() == (
        returned.parent / record["editable_sources"][0]
    ).read_bytes()
    assert not (Path.cwd() / "EXECUTED").exists()
    assert not (returned.parent / "EXECUTED").exists()


def test_schematic_allows_readonly_field_reference(tmp_path):
    data = make_task(tmp_path, "schematic")
    data["sources"][0]["role"] = "field_image"
    data["labels"][0]["unit"] = ""
    package = prepare_figure_task(write_json(tmp_path / "input.json", data), tmp_path / "package")
    assert "read-only real field" in (package / "prompt.md").read_text()


@pytest.mark.parametrize("kind", ["data", "hybrid"])
def test_quantitative_route_needs_data_and_units(tmp_path, kind):
    data = make_task(tmp_path, kind)
    data["sources"][0]["role"] = "context"
    with pytest.raises(ValueError, match="require a data source"):
        prepare_figure_task(write_json(tmp_path / "input.json", data), tmp_path / "package")
    data["sources"][0]["role"] = "data"
    data["labels"][0]["unit"] = ""
    with pytest.raises(ValueError, match="explicit units"):
        prepare_figure_task(write_json(tmp_path / "input.json", data), tmp_path / "package")
    assert not (tmp_path / "package").exists()


@pytest.mark.parametrize("name", ["missing.csv", "../data.csv"])
def test_missing_or_escaping_input_source(tmp_path, name):
    data = make_task(tmp_path)
    data["sources"][0]["path"] = name
    with pytest.raises(ValueError):
        prepare_figure_task(write_json(tmp_path / "input.json", data), tmp_path / "package")
    assert not (tmp_path / "package").exists()


@pytest.mark.parametrize("id_", ["..", "."])
def test_source_id_cannot_escape(tmp_path, id_):
    data = make_task(tmp_path)
    data["sources"][0]["id"] = id_
    with pytest.raises(ValueError):
        prepare_figure_task(write_json(tmp_path / "input.json", data), tmp_path / "package")


@pytest.mark.parametrize("missing", ["plot.py", "preview.png"])
def test_return_requires_existing_editable_and_preview(tmp_path, missing):
    package = prepare(tmp_path)
    returned = delivery(tmp_path)
    (returned.parent / missing).unlink()
    with pytest.raises(ValueError, match="Missing"):
        import_figure_task(package, returned, tmp_path / "imported")
    assert not (tmp_path / "imported").exists()


@pytest.mark.parametrize("defect", ["blank", "broken", "raster_only", "wrong_id", "no_script"])
def test_reject_unusable_or_mismatched_delivery(tmp_path, defect):
    package = prepare(tmp_path)
    returned = delivery(tmp_path)
    record = json.loads(returned.read_text())
    if defect == "blank":
        Image.new("RGB", (100, 60), "white").save(returned.parent / "preview.png")
    elif defect == "broken":
        (returned.parent / "plot.py").write_text("if broken!", encoding="utf-8")
    elif defect == "raster_only":
        (returned.parent / "figure.svg").write_text('<svg><image href="x.png"/></svg>')
        record["editable_sources"] = ["figure.svg"]
    elif defect == "wrong_id":
        record["figure_id"] = "other"
    else:
        record["editable_sources"] = ["figure.svg"]
    write_json(returned, record)
    with pytest.raises((ValueError, SyntaxError)):
        import_figure_task(package, returned, tmp_path / "imported")
    assert not (tmp_path / "imported").exists()


def test_schematic_rejects_python_without_editable_diagram(tmp_path):
    package = prepare(tmp_path, "schematic")
    returned = delivery(tmp_path)
    with pytest.raises(ValueError, match="Schematic deliveries require"):
        import_figure_task(package, returned, tmp_path / "imported")


def test_existing_outputs_and_author_edits_are_preserved(tmp_path):
    package = prepare(tmp_path)
    marker = package / "author-edit.svg"
    marker.write_text("keep local labels", encoding="utf-8")
    with pytest.raises(FileExistsError):
        prepare_figure_task(tmp_path / "input.json", package)
    assert marker.read_text() == "keep local labels"
    returned = delivery(tmp_path)
    result = import_figure_task(package, returned, tmp_path / "imported")
    (result / "plot.py").write_text("# author edit", encoding="utf-8")
    with pytest.raises(FileExistsError):
        import_figure_task(package, returned, result)
    assert (result / "plot.py").read_text() == "# author edit"


def test_return_cannot_replace_task_sources(tmp_path):
    package = prepare(tmp_path)
    returned = delivery(tmp_path)
    (returned.parent / "sources").mkdir()
    (returned.parent / "sources/edit.py").write_text("print('replacement')", encoding="utf-8")
    record = json.loads(returned.read_text())
    record["editable_sources"] = ["sources/edit.py"]
    write_json(returned, record)
    with pytest.raises(ValueError, match="replace preserved"):
        import_figure_task(package, returned, tmp_path / "imported")


def test_return_source_provenance_required_even_if_preview_exists(tmp_path):
    package = prepare(tmp_path)
    returned = delivery(tmp_path)
    (package / "sources/data.csv").unlink()
    with pytest.raises(ValueError, match="Missing"):
        import_figure_task(package, returned, tmp_path / "imported")


def test_nested_dependencies_execute_after_task_and_delivery_relocation(tmp_path):
    original = tmp_path / "original"
    original.mkdir()
    data = make_task(original)
    (original / "scripts").mkdir()
    (original / "fields").mkdir()
    (original / "fields/value.csv").write_text("2,3\n", encoding="utf-8")
    (original / "scripts/helper.py").write_text(
        "def total(text):\n    return sum(int(x) for x in text.strip().split(','))\n",
        encoding="utf-8",
    )
    (original / "scripts/read.py").write_text(
        "from pathlib import Path\nfrom helper import total\n"
        "print(total((Path(__file__).resolve().parents[1] / 'fields/value.csv').read_text()))\n",
        encoding="utf-8",
    )
    data["sources"] = [
        {"id": "field", "path": "fields/value.csv", "role": "data", "description": "Values"},
        {
            "id": "reader",
            "path": "scripts/read.py",
            "role": "editable_source",
            "description": "Reader",
        },
        {
            "id": "helper",
            "path": "scripts/helper.py",
            "role": "editable_source",
            "description": "Helper",
        },
    ]
    package = prepare_figure_task(write_json(original / "input.json", data), tmp_path / "task")
    moved = tmp_path / "moved task"
    shutil.move(package, moved)
    shutil.rmtree(original)
    script = moved / "sources/scripts/read.py"
    result = subprocess.run(
        [sys.executable, str(script)], cwd=tmp_path, capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "5"
    returned = delivery(tmp_path)
    imported = import_figure_task(moved, returned, tmp_path / "candidate")
    relocated = tmp_path / "relocated candidate"
    shutil.move(imported, relocated)
    shutil.rmtree(moved)
    result = subprocess.run(
        [sys.executable, str(relocated / "sources/scripts/read.py")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "5"


def test_preview_resolution_uses_pixels_and_final_width_not_image_dpi(tmp_path):
    package = prepare(tmp_path)
    returned = delivery(tmp_path)
    preview = returned.parent / "preview.png"
    with Image.open(preview) as image:
        image.save(preview, dpi=(1200, 1200))
    candidate = import_figure_task(package, returned, tmp_path / "candidate")
    record = json.loads((candidate / "delivery.json").read_text())
    geometry = record["preview_geometry"]
    assert geometry["width_px"] == 100
    assert geometry["height_px"] == 60
    assert geometry["final_width_mm"] == 160
    assert geometry["final_height_mm"] == 96
    assert geometry["effective_ppi"] == pytest.approx(100 * 25.4 / 160)
    assert record["scientific_approval"] is False


def test_existing_id_based_task_can_still_be_imported(tmp_path):
    package = prepare(tmp_path)
    task = json.loads((package / "task.json").read_text())
    source = task["sources"][0]
    old_path = package / "sources/raw/data.csv"
    old_path.parent.mkdir()
    shutil.move(package / source["path"], old_path)
    source["path"] = "sources/raw/data.csv"
    write_json(package / "task.json", task)
    returned = delivery(tmp_path)
    candidate = import_figure_task(package, returned, tmp_path / "candidate")
    assert (candidate / source["path"]).read_bytes() == (tmp_path / "data.csv").read_bytes()


def test_declared_sizing_is_reusable_for_word_placement(tmp_path):
    task = make_task(tmp_path)
    task["final_width_mm"] = 100
    package = prepare_figure_task(write_json(tmp_path / "input.json", task), tmp_path / "package")
    returned = delivery(tmp_path)
    record = json.loads(returned.read_text())
    record["sizing"] = {
        "source_width_mm": 200,
        "target_width_mm": 100,
        "minimum_source_font_pt": 16,
    }
    write_json(returned, record)
    candidate = import_figure_task(package, returned, tmp_path / "candidate")
    imported = json.loads((candidate / "delivery.json").read_text())
    assert imported["sizing"] == record["sizing"]
    assert imported["placement"]["width_mm"] == 100
    assert imported["placement"]["minimum_font_pt"] == 8
    assert imported["placement"]["scale"] == 0.5
    assert imported["font_size_basis"] == "declared_source_metadata"
    assert imported["placement"] == figure_placement(
        pixels=(100, 60),
        caption=f"Figure f1. {record['caption']}",
        sizing=FigureSizing.model_validate(imported["sizing"]),
        style=PublicationStyle.model_validate(imported["placement_style"]),
    )


@pytest.mark.parametrize(
    ("sizing", "message"),
    [
        ({"source_width_mm": 200, "minimum_source_font_pt": 8}, "below 8 pt"),
        ({"minimum_source_font_pt": 12}, "requires actual source_width_mm"),
        ({"target_width_mm": 100}, "conflicts with task final_width_mm"),
        ({"source_width_mm": -1}, "greater than 0"),
        ({"minimum_source_font_pt": float("nan")}, "finite number"),
    ],
)
def test_invalid_sizing_fails_before_copying(tmp_path, sizing, message):
    package = prepare(tmp_path)
    returned = delivery(tmp_path)
    record = json.loads(returned.read_text())
    record["sizing"] = sizing
    write_json(returned, record)
    with pytest.raises(ValueError, match=message):
        import_figure_task(package, returned, tmp_path / "candidate")
    assert not (tmp_path / "candidate").exists()


@pytest.mark.parametrize("sizing", [None, {"source_width_mm": 200}])
def test_unknown_font_stays_unknown_including_legacy_deliveries(tmp_path, sizing):
    package = prepare(tmp_path)
    returned = delivery(tmp_path)
    if sizing is not None:
        record = json.loads(returned.read_text())
        record["sizing"] = sizing
        write_json(returned, record)
    candidate = import_figure_task(package, returned, tmp_path / "candidate")
    imported = json.loads((candidate / "delivery.json").read_text())
    assert imported["sizing"]["target_width_mm"] == 160
    assert imported["sizing"]["minimum_source_font_pt"] is None
    assert imported["placement"]["minimum_font_pt"] is None
    assert imported["font_size_basis"] == "unknown"


def test_final_size_report_and_font_check_use_page_clamped_width(tmp_path):
    package = prepare(tmp_path)
    returned = delivery(tmp_path)
    record = json.loads(returned.read_text())
    record["sizing"] = {"source_width_mm": 200, "minimum_source_font_pt": 16}
    write_json(returned, record)
    style = PublicationStyle(margin_mm=55)  # 100 mm of usable page width.
    candidate = import_figure_task(package, returned, tmp_path / "candidate", style=style)
    imported = json.loads((candidate / "delivery.json").read_text())
    assert imported["sizing"]["target_width_mm"] == 160
    assert imported["placement"]["width_mm"] == 100
    assert imported["placement"]["minimum_font_pt"] == 8
    assert imported["preview_geometry"]["final_width_mm"] == 100
    assert imported["preview_geometry"]["effective_ppi"] == 25.4
    with pytest.raises(ValueError, match="7.20 pt, below 8 pt"):
        import_figure_task(
            package, returned, tmp_path / "too-narrow", style=PublicationStyle(margin_mm=60)
        )


def test_tall_image_font_check_uses_actual_height_limited_scale(tmp_path):
    package = prepare(tmp_path)
    returned = delivery(tmp_path)
    image = Image.new("RGB", (100, 600), "white")
    ImageDraw.Draw(image).line((10, 20, 80, 400), fill="black", width=2)
    image.save(returned.parent / "preview.png")
    record = json.loads(returned.read_text())
    record["sizing"] = {"source_width_mm": 160, "minimum_source_font_pt": 16}
    write_json(returned, record)
    with pytest.raises(ValueError, match="below 8 pt"):
        import_figure_task(package, returned, tmp_path / "candidate")
    assert not (tmp_path / "candidate").exists()
