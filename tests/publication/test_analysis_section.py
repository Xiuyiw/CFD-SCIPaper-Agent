import json
import runpy
import zipfile

import pytest

from cfdpaper.publication.analysis_section import build_analysis_section, render_analysis_figures
from cfdpaper.publication.render_figure import PlotStyle
from cfdpaper.publication.section import assemble_section, export_section_docx


def payload(tmp_path):
    (tmp_path / "sources").mkdir()
    (tmp_path / "sources/flow.csv").write_text(
        "case,outlet,flow\nA,1,1\nA,2,3\nB,1,2\nB,2,2\n", encoding="utf-8"
    )
    data = {
        "section_id": "flow",
        "title": "Outlet distribution",
        "question": "How does spread vary?",
        "context": "Equal independent outlet observations, not a spatial temperature metric.",
        "source_files": ["sources/flow.csv"],
        "table_calculations": [
            {
                "id": "spread",
                "source": "sources/flow.csv",
                "operation": "population",
                "columns": {"value": "flow"},
                "units": {"value": "kg/s"},
                "group_by": "case",
                "domain": "Two complete outlet sets, equal observations",
            }
        ],
        "evidence": [
            {
                "id": key,
                "text": f"Outlet-flow CV for {group}",
                "source": "sources/flow.csv",
                "kind": "metric",
                "result_ref": {
                    "calculation_id": "spread",
                    "group": group,
                    "field": "cv",
                    "places": 3,
                },
            }
            for key, group in (("cv-a", "A"), ("cv-b", "B"))
        ],
        "figure_plan": {
            "metric_ids": ["cv-a", "cv-b"],
            "title": "Outlet-flow spread",
            "y_label": "Population CV",
        },
    }
    path = tmp_path / "analysis-input.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_plot_writing_numbers_and_editable_artifacts(tmp_path):
    pytest.importorskip("docx")
    path = payload(tmp_path)
    package = build_analysis_section(path, tmp_path / "output")
    root = package.parent
    for ext in ("svg", "pdf", "png", "tiff"):
        assert (root / f"figures/analysis-1.{ext}").stat().st_size > 0
    assert "<text" in (root / "figures/analysis-1.svg").read_text(encoding="utf-8")
    data = json.loads((package / "input.json").read_text())
    assert data["figures"][0]["sizing"]["source_width_mm"] == 160
    assert data["figures"][0]["sizing"]["minimum_source_font_pt"] >= 8
    draft = {
        "title": data["title"],
        "paragraphs": [
            {
                "text": "The outlet CV changes from {{value:cv-a}} to {{value:cv-b}} "
                "in {{figure:1}}. This is a flow-distribution comparison.",
                "evidence_ids": ["cv-a", "cv-b"],
                "figure_ids": ["1"],
            }
        ],
        "captions": {"1": "Equal-observation outlet-flow spread."},
        "evidence_notes": [],
        "image_observations": {"1": "not-viewed"},
    }
    draft_path = tmp_path / "draft.json"
    draft_path.write_text(json.dumps(draft), encoding="utf-8")
    section = assemble_section(package, draft_path, tmp_path / "section")
    assert "0.500 to 0.000" in (section / "section.md").read_text()
    docx = export_section_docx(section, tmp_path / "section.docx")
    with zipfile.ZipFile(docx) as archive:
        assert any(name.startswith("word/media/") for name in archive.namelist())
    with pytest.raises(FileExistsError):
        build_analysis_section(path, root)


def test_plot_script_recomputes_raw_values_without_overwriting_script(tmp_path):
    path = payload(tmp_path)
    package = build_analysis_section(path, tmp_path / "output")
    root = package.parent
    script = root / "plot_analysis.py"
    original_script = script.read_text()
    (root / "sources/flow.csv").write_text(
        "case,outlet,flow\nA,1,1\nA,2,1\nB,1,2\nB,2,2\n", encoding="utf-8"
    )
    runpy.run_path(str(script))
    assert script.read_text() == original_script
    import csv

    with (root / "figures/analysis-1-source-data.csv").open() as stream:
        assert [float(r["raw_value"]) for r in csv.DictReader(stream)] == [0, 0]


def test_independent_units_are_never_combined(tmp_path):
    path = payload(tmp_path)
    data = json.loads(path.read_text())
    data["figure_plan"] = None
    data["evidence"][1]["result_ref"]["field"] = "mean"
    path.write_text(json.dumps(data))
    figs = render_analysis_figures(path, style=PlotStyle(font_family="DejaVu Serif"))
    assert len(figs) == 2


def test_unknown_metric_stops_before_rendering(tmp_path):
    path = payload(tmp_path)
    data = json.loads(path.read_text())
    data["figure_plan"]["metric_ids"] = ["invented"]
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="metric IDs"):
        render_analysis_figures(path)


def test_physical_category_labels_do_not_change_values(tmp_path):
    path = payload(tmp_path)
    data = json.loads(path.read_text())
    data["figure_plan"].update(
        x_label="Configuration", category_labels={"cv-a": "Reference", "cv-b": "Modified"}
    )
    path.write_text(json.dumps(data))
    render_analysis_figures(path)
    svg = (tmp_path / "figures/analysis-1.svg").read_text(encoding="utf-8")
    assert all(label in svg for label in ("Configuration", "Reference", "Modified"))
    data["figure_plan"]["category_labels"] = {"cv-a": "Same", "cv-b": "Same"}
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Repeated group labels"):
        render_analysis_figures(path)


def test_display_unit_changes_typography_not_scale():
    from cfdpaper.publication.table_evidence import display_unit

    assert display_unit("(W)/(m2)") == "W m⁻²"
    assert display_unit("(kW)/(cm^2)") == "kW cm⁻²"
    assert display_unit("kg/s") == "kg/s"
    assert display_unit("m2") == "m²"
    assert display_unit("cm^2") == "cm²"
    assert display_unit("degC") == "°C"
    assert display_unit("°C") == "°C"
    assert display_unit("K") == "K"


def test_docx_keeps_percentage_with_number(tmp_path):
    docx_module = pytest.importorskip("docx")
    (tmp_path / "section.json").write_text(
        json.dumps(
            {
                "title": "Heat allocation",
                "paragraphs": [{"text": "The share is 57.74 %.", "figure_ids": []}],
                "figures": [],
                "references": [],
            }
        ),
        encoding="utf-8",
    )
    output = export_section_docx(tmp_path, tmp_path / "section.docx")
    assert "57.74\u00a0%" in docx_module.Document(output).paragraphs[1].text


def test_existing_field_image_and_observation_survive_section_preparation(tmp_path):
    from PIL import Image

    path = payload(tmp_path)
    Image.new("RGB", (600, 300), "white").save(tmp_path / "sources/field.png")
    data = json.loads(path.read_text())
    data["source_files"].append("sources/field.png")
    data["figures"] = [
        {
            "id": "field",
            "path": "sources/field.png",
            "caption": "Supplied field image.",
            "description": "Author observation.",
        }
    ]
    data["evidence"].append(
        {
            "id": "obs",
            "kind": "observation",
            "text": "Author field observation",
            "source": "sources/field.png",
        }
    )
    path.write_text(json.dumps(data))
    package = build_analysis_section(path, tmp_path / "output")
    prepared = json.loads((package / "input.json").read_text())
    assert {f["id"] for f in prepared["figures"]} == {"field", "1"}
    assert prepared["evidence"][-1]["id"] == "obs"
    assert (package / "figures/field.png").read_bytes() == (
        tmp_path / "sources/field.png"
    ).read_bytes()
