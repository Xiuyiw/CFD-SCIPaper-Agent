"""Create a source-bound response figure and editable Word research-note example.

All numbers and example author prose are constructed for this installation demo.
No CFD solver, model API, private project or checkout-relative data is required.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cfdpaper.host_tools import report_task


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _example_drafts(workspace: Path) -> None:
    """Supply example author prose using the same drafts that a host would fill."""
    texts = {
        "methods": (
            "This constructed single-phase cooling example compares three prescribed inlet "
            "velocities while declaring the geometry, inlet temperature and imposed heat input "
            "unchanged. Interface mean and facet-maximum temperatures are distinct observations "
            "on the same interface surface. Each pressure difference is inlet minus outlet of "
            "the same pressure variable, using area-weighted section means at fixed inlet and "
            "outlet supports. Temperature is reported in kelvin; the pressure reports are read "
            "in pascals and converted to kilopascals. Figure lines join the discrete constructed "
            "cases and are not fitted curves."
        ),
        "results": (
            "In {{figure:1}}, the interface area mean decreases from {{value:mean_S1}} "
            "to {{value:mean_S3}}, while the facet maximum decreases from {{value:peak_S1}} "
            "to {{value:peak_S3}}. The mean and maximum remain separate series rather than "
            "being treated as interchangeable wall-temperature definitions. Over the same "
            "case sequence, the area-weighted static-pressure difference increases from "
            "{{value:static_S1}} to {{value:static_S3}} and the corresponding total-pressure "
            "difference increases from {{value:total_S1}} to {{value:total_S3}}. "
            "{{table:report_values}} retains the readings and their declared operators."
        ),
        "discussion": (
            "The paired panels organize a thermal response together with its hydraulic "
            "counterpart: the constructed higher-velocity cases have lower interface "
            "temperatures but larger pressure differences. These scalar observations alone "
            "do not identify a local heat-transfer mechanism or establish pumping power. "
            "In a real study, the host and author would inspect the available flow and thermal "
            "fields, matching conditions and appropriate energy or flow-rate information "
            "before explaining this relation or ranking designs. The present synthetic values "
            "demonstrate the report-to-figure-to-writing connection, not a validated device."
        ),
    }
    for section, name in _read(workspace / "drafts.json").items():
        path = workspace / name
        draft = _read(path)
        paragraph = draft["paragraphs"][0]
        paragraph["text"] = texts[section]
        if section != "results":
            paragraph["evidence_ids"] = ["report_question"]
        else:
            paragraph["figure_ids"] = ["1"]
            draft["image_observations"]["1"] = "author-provided"
            draft["observation_notes"]["1"] = (
                "The example author supplies two decreasing temperature series and two "
                "increasing pressure-difference series, with three discrete cases per series. "
                "Inspect the actual preview before using it in a research interpretation."
            )
        _write(path, draft)


def run(output: Path) -> Path:
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    raw = output / "raw"
    raw.mkdir()
    for case, speed, mean, peak, static, total in (
        ("S1", 0.8, 330.0, 336.0, 600.0, 1000.0),
        ("S2", 1.2, 326.0, 331.0, 1300.0, 2200.0),
        ("S3", 1.6, 323.0, 328.0, 2200.0, 3800.0),
    ):
        _write(
            raw / f"{case}.json",
            {
                "source_kind": "constructed installation-example readings",
                "inlet": {"velocity": speed, "temperature": 300.0},
                "interface": {"area_mean": mean, "facet_maximum": peak},
                "static_pressure": {"inlet": static + 50.0, "outlet": 50.0},
                "total_pressure": {"inlet": total + 70.0, "outlet": 70.0},
            },
        )
    (raw / "method.md").write_text(
        "Constructed steady single-phase reports; not a CFD simulation or experiment.\n"
        "Shared declared geometry, inlet temperature 300 K and heat input 100 W.\n"
        "Interface temperature: fixed interface, area mean and facet maximum.\n"
        "Pressure: area-weighted inlet and outlet section means of the same variable.\n"
        "Difference = inlet minus outlet; source Pa, displayed kPa.\n"
        "Connecting straight segments are guides between prescribed cases, not a fit.\n",
        encoding="utf-8",
    )
    quantities = [
        {
            "id": "speed",
            "label": "Prescribed inlet velocity",
            "unit": "m/s",
            "domain": "prescribed inlet velocity magnitude",
            "pointer": "/inlet/velocity",
            "table": False,
        },
        *[
            {
                "id": identifier,
                "label": label,
                "unit": "K",
                "domain": "fixed interface surface; " + operator,
                "quantity_kind": "absolute-temperature",
                "pointer": pointer,
            }
            for identifier, label, operator, pointer in (
                ("mean", "Interface area mean", "area mean", "/interface/area_mean"),
                ("peak", "Interface facet maximum", "facet maximum", "/interface/facet_maximum"),
            )
        ],
        *[
            {
                "id": identifier,
                "label": label,
                "unit": "Pa",
                "output_unit": "kPa",
                "domain": "fixed inlet/outlet sections, area-weighted " + variable,
                "reference": f"/{variable}/outlet",
                "comparison": f"/{variable}/inlet",
            }
            for identifier, label, variable in (
                ("static", "Static-pressure difference", "static_pressure"),
                ("total", "Total-pressure difference", "total_pressure"),
            )
        ],
    ]
    caption = (
        "Constructed thermal and hydraulic responses at three prescribed inlet velocities. "
        "(a) Area-mean and facet-maximum temperatures on the same interface; "
        "(b) inlet-minus-outlet differences of area-weighted static and total pressure. "
        "The declared geometry, inlet temperature and heat input are unchanged. "
        "Straight segments guide the eye between discrete illustrative values; they are "
        "not fitted predictions. These synthetic readings do not establish a physical mechanism."
    )
    report_task(
        output / "prepared",
        root=raw,
        cases=[{"id": case, "source": f"{case}.json"} for case in ("S1", "S2", "S3")],
        quantities=quantities,
        title="Constructed interface-temperature and pressure-response example",
        question="How are the declared thermal and hydraulic responses organized together?",
        context="Synthetic installation example, not real CFD or independent validation.",
        support_files=[Path("method.md")],
        figure_plan={
            "columns": 2,
            "style": {
                "width_mm": 180,
                "height_mm": 88,
                "font_family": "DejaVu Serif",
                "font_pt": 10,
                "axis_label_pt": 10,
                "title_pt": 10,
                "tick_pt": 9,
                "legend_pt": 9,
                "annotation_pt": 9,
            },
            "caption": caption,
            "panels": [
                {
                    "kind": "response",
                    "title": "Interface temperature",
                    "x_label": "Inlet velocity",
                    "y_label": "Temperature",
                    "x_calculation_id": "speed",
                    "series": [
                        {"calculation_id": "mean", "label": "Area mean"},
                        {"calculation_id": "peak", "label": "Facet maximum"},
                    ],
                    "connect": True,
                },
                {
                    "kind": "response",
                    "title": "Inlet–outlet pressure",
                    "x_label": "Inlet velocity",
                    "y_label": "Pressure difference",
                    "x_calculation_id": "speed",
                    "series": [
                        {"calculation_id": "static", "field": "difference", "label": "Static"},
                        {"calculation_id": "total", "field": "difference", "label": "Total"},
                    ],
                    "connect": True,
                },
            ],
        },
    )
    workspace = output / "prepared/workspace"
    _example_drafts(workspace)
    built = report_task(
        output / "candidate", workspace=output / "prepared", drafts=workspace / "drafts.json"
    )
    return Path(built["artifacts"]["docx"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New output directory (absolute or relative)")
    print(run(parser.parse_args().output))
