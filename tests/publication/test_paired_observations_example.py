import json
import runpy
import shutil
from pathlib import Path

import pytest

from cfdpaper.analysis_suggestions import compile_analysis, prepare_analysis
from cfdpaper.publication.manuscript import assemble_manuscript

EXAMPLE = Path(__file__).resolve().parents[2] / "examples/paired-observations/run_example.py"


def test_public_analysis_seed_native_word_and_json_source_refresh(tmp_path):
    output = tmp_path / "tutorial"
    docx = runpy.run_path(str(EXAMPLE))["run"](output)
    assert docx.is_file()
    data = json.loads((output / "manuscript/section.json").read_text(encoding="utf-8"))
    values = list(data["resolved_values"].values())
    assert any(
        v["raw_value"] == 0.25 and v.get("json_pointer") == "/solver/max_step_s" for v in values
    )
    assert any(v["raw_value"] == -15 and v.get("field") == "outside_distance" for v in values)
    assert len(data["tables"]) == 2 and len(data["figures"]) == 1
    text = (output / "manuscript/manuscript.md").read_text(encoding="utf-8")
    assert "0.25 s" in text and "Table temperatures" not in text and "{{" not in text
    moved = tmp_path / "relocated"
    shutil.copytree(output / "manuscript", moved)
    config = moved / "sections/methods/sources/config.json"
    recorded = json.loads(config.read_text(encoding="utf-8"))
    recorded["solver"]["max_step_s"] = 0.5
    config.write_text(json.dumps(recorded), encoding="utf-8")
    refreshed = assemble_manuscript(moved, moved / "drafts.json", tmp_path / "refreshed")
    assert "0.50 s" in (refreshed / "manuscript.md").read_text(encoding="utf-8")
    assert "0.25 s" in (output / "manuscript/manuscript.md").read_text(encoding="utf-8")


def test_missing_paired_range_has_no_fabricated_numeric_anchor(tmp_path):
    api = runpy.run_path(str(EXAMPLE))
    inputs = tmp_path / "inputs"
    shutil.copytree(EXAMPLE.parent / "inputs", inputs)
    csv = inputs / "temperatures.csv"
    csv.write_text(csv.read_text().replace("355,325,322,328", "355,325,,328"))
    package = prepare_analysis(inputs, tmp_path / "materials").parent
    proposal = api["proposal"]()
    c = proposal["candidates"][0]
    c["calculations"] = [c["calculations"][1]]
    c["metrics"] = []
    c["presentation"] = "prose"
    c.pop("evidence_panels")
    path = tmp_path / "proposal.json"
    path.write_text(json.dumps(proposal), encoding="utf-8")
    with pytest.raises(ValueError, match="missing numeric"):
        compile_analysis(package, path, "paired", tmp_path / "compiled")
    assert not (tmp_path / "compiled").exists()
