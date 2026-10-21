"""Replay constructed JSON reports through bound writing and source refresh.

This installation example uses no CFD results, model API or solver. It calls the
installed report_task API and supplies clearly labelled example author prose.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from cfdpaper.host_tools import report_task


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _fill_drafts(workspace: Path) -> None:
    texts = {
        "methods": (
            "Constructed installation example: the endpoint reports use the same declared "
            "area-weighted static-pressure supports. The prescribed inlet intensity in case A "
            "is {{value:intensity_A}}. The normalized pressure difference is R={{math:ratio}}; "
            "relative excess is 100 times (R minus 1), using the reference as denominator."
        ),
        "results": (
            "Across these prescribed cases, the endpoint differences are {{value:drop_A}} "
            "and {{value:drop_B}}. Relative excesses over the constructed references are "
            "{{value:excess_A}} and {{value:excess_B}}. {{table:report_values}} retains the "
            "source-bound readings and comparisons."
        ),
        "discussion": (
            "Author wording retained: these numerical contrasts describe only the declared "
            "endpoint supports. Case A exceeds its constructed reference by "
            "{{value:excess_A}}. This is not a physical-loss budget or independent validation."
        ),
    }
    for sid, name in _read(workspace / "drafts.json").items():
        path = workspace / name
        draft = _read(path)
        paragraph = draft["paragraphs"][0]
        paragraph["text"] = texts[sid]
        if sid == "methods":
            paragraph["evidence_ids"] = ["report_question", "intensity_A"]
        elif sid == "discussion":
            paragraph["evidence_ids"] = ["report_question", "excess_A"]
        _write(path, draft)


def _values(response: dict) -> dict:
    return {
        item["evidence_id"]: {"value": item["value"], "unit": item["unit"]}
        for item in response["context"]["metrics"]
    }


def run(output: Path) -> Path:
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    raw = output / "raw"
    raw.mkdir()
    for case, pressure in (("A", 120), ("B", 144)):
        _write(raw / f"{case}.json", {"pressure": {"inlet": pressure, "outlet": 0}})
        _write(raw / f"{case}-setup.json", {"inlet": {"intensity": 0.06}})
    _write(raw / "reference.json", {"readings": [100, 120]})
    (raw / "method.md").write_text(
        "Constructed reports share fixed inlet/outlet static-pressure supports in Pa.\n"
        "R = (p_in - p_out) / p_ref; relative excess = 100 * (R - 1) percent.\n"
        "The constructed reference is the denominator, not an independent measurement.\n",
        encoding="utf-8",
    )
    domain = "constructed endpoint pressure comparison at fixed declared supports"
    prepared = output / "prepared"
    report_task(
        prepared,
        root=raw,
        title="Constructed pressure-report installation example",
        question="How do declared endpoint differences compare with constructed references?",
        context="Synthetic installation replay, not real CFD or scientific validation.",
        cases=[
            {
                "id": case,
                "source": f"{case}.json",
                "sources": {"setup": f"{case}-setup.json", "reference": "reference.json"},
            }
            for case in ("A", "B")
        ],
        quantities=[
            {
                "id": "drop",
                "label": "Declared static-pressure difference",
                "unit": "Pa",
                "domain": domain,
                "reference": "/pressure/outlet",
                "comparison": "/pressure/inlet",
            },
            {
                "id": "reference",
                "label": "Constructed reference reading",
                "unit": "Pa",
                "domain": domain,
                "source_key": "reference",
                "pointer": {"A": "/readings/0", "B": "/readings/1"},
            },
            {
                "id": "intensity",
                "label": "Prescribed inlet turbulence intensity",
                "unit": "",
                "domain": "saved inlet specification",
                "source_key": "setup",
                "pointer": "/inlet/intensity",
                "table": False,
            },
        ],
        derived=[
            {
                "id": f"excess_{case}",
                "label": "Relative excess over the constructed reference",
                "reference": f"reference_{case}",
                "comparison": f"drop_{case}",
                "field": "relative_change",
                "percentage": True,
                "places": 2,
                "table": True,
                "domain": domain,
                "comparison_scope": "Constructed numerical contrast only, not validation",
                "definition_source": "method.md:L2-L3",
            }
            for case in ("A", "B")
        ],
        formulas={
            "ratio": {
                "source": "method.md:L2",
                "expression": {
                    "kind": "fraction",
                    "children": [
                        {"kind": "text", "text": "inlet pressure − outlet pressure"},
                        {"kind": "text", "text": "reference pressure"},
                    ],
                },
            }
        },
    )
    _fill_drafts(prepared / "workspace")
    first = report_task(
        output / "first", workspace=prepared, drafts=prepared / "workspace/drafts.json"
    )

    # Only the independent receiving copy is changed; raw and first stay intact.
    moved = output / "receiving/current"
    shutil.copytree(output / "first", moved)
    _write(moved / "projection/sources/records/A/reference.json", {"readings": [80, 120]})
    _write(moved / "projection/sources/records/A/setup.json", {"inlet": {"intensity": 0.09}})
    refreshed = report_task(
        output / "refreshed", workspace=moved, drafts=moved / "workspace/drafts.json"
    )
    _write(
        output / "example-result.json",
        {
            "scenario": "constructed-report-writing-and-refresh",
            "first_values": _values(first),
            "refreshed_values": _values(refreshed),
            "first_manuscript": "first/manuscript.docx",
            "refreshed_manuscript": "refreshed/manuscript.docx",
        },
    )
    return Path(refreshed["artifacts"]["docx"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New output directory (absolute or relative)")
    print(run(parser.parse_args().output))
