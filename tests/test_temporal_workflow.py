"""Temporal proposals use the normal analysis/section path, not a parallel script."""

import json

import pytest

from cfdpaper.analysis_suggestions import compile_analysis, prepare_analysis
from cfdpaper.publication.analysis_section import build_analysis_section
from cfdpaper.publication.section import _TableCalculation, assemble_section


def test_temporal_proposal_to_bound_section(tmp_path):
    root = tmp_path / "raw"
    root.mkdir()
    (root / "history.csv").write_text("t,q\n0,2\n1,4\n3,8\n", encoding="utf-8")
    (root / "method.md").write_text(
        "Saved heat rate in W on the same wall; seconds 0 to 3.\n", encoding="utf-8"
    )
    package = tmp_path / "analysis"
    prepare_analysis(root, package, question="What heat input is reconstructed?")
    proposal = {
        "candidates": [
            {
                "id": "heat",
                "question": "What is the time-mean rate?",
                "rationale": "Actual nonuniform intervals",
                "presentation": "prose",
                "presentation_reason": "One scalar does not need a full-width plot",
                "calculations": [
                    {
                        "id": "rate",
                        "source": "sources/history.csv",
                        "operation": "temporal",
                        "columns": {"time": "t", "value": "q"},
                        "units": {"time": "s", "value": "W"},
                        "time_window": [0, 3],
                        "domain": "wall, 0-3 s",
                        "member_id": ["t"],
                        "definition_source": {"path": "sources/method.md", "locator": "L1"},
                        "comparison": {"status": "supported", "scope": "Single saved history"},
                        "interpretation_limits": [
                            "Saved-rate integral, not an independent energy balance"
                        ],
                    }
                ],
                "interpretation_limits": ["No spatial mechanism inferred"],
            }
        ],
        "gaps": [],
    }
    path = package / "proposal.json"
    path.write_text(json.dumps(proposal), encoding="utf-8")
    analysis = compile_analysis(package, path, "heat", tmp_path / "compiled")
    payload = json.loads(analysis.read_text(encoding="utf-8"))
    assert payload["table_calculations"][0]["time_window"] == [0, 3]
    assert "time_mean" in {e["result_ref"]["field"] for e in payload["evidence"]}
    writing = build_analysis_section(analysis, tmp_path / "writing")
    data = json.loads((writing / "input.json").read_text(encoding="utf-8"))
    metric = next(e for e in data["evidence"] if e["result_ref"]["field"] == "time_mean")
    draft = {
        "title": data["title"],
        "paragraphs": [
            {
                "text": f"The time-mean wall rate is {{{{value:{metric['id']}}}}}.",
                "evidence_ids": [e["id"] for e in data["evidence"]],
                "figure_ids": [],
            }
        ],
        "captions": {},
        "image_observations": {},
        "evidence_notes": [],
    }
    draft_path = tmp_path / "draft.json"
    draft_path.write_text(json.dumps(draft), encoding="utf-8")
    out = assemble_section(writing, draft_path, tmp_path / "section")
    assert "5.000 W" in (out / "section.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("window", ([0, float("inf")], [2, 1]))
def test_temporal_window_validation_in_schema(window):
    with pytest.raises(ValueError):
        _TableCalculation.model_validate(
            {
                "id": "q",
                "source": "sources/q.csv",
                "operation": "temporal",
                "time_window": window,
                "columns": {"time": "t", "value": "q"},
                "units": {"time": "s", "value": "W"},
                "domain": "wall",
            }
        )
