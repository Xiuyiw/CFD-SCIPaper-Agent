import csv
import json
import runpy
import shutil
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from cfdpaper.publication.manuscript import assemble_manuscript

EXAMPLE = Path(__file__).resolve().parents[2] / "examples/multi-observation/run_example.py"


def test_connected_proposal_numbers_moved_reassembly_and_native_word(tmp_path):
    pytest.importorskip("docx")
    output = tmp_path / "tutorial"
    docx = runpy.run_path(str(EXAMPLE))["run"](output)
    assert docx.is_file()
    proposal = json.loads((output / "recorded-proposal.json").read_text(encoding="utf-8"))
    assert [p["kind"] for p in proposal["candidates"][0]["evidence_panels"]] == [
        "profile",
        "reference_range",
        "reference_range",
    ]
    result = json.loads((output / "manuscript/section.json").read_text(encoding="utf-8"))
    numbers = {
        (r["calculation_id"], r["group"], r["field"]): r["raw_value"]
        for r in result["resolved_values"].values()
        if "calculation_id" in r
    }
    assert numbers["history", "A", "time_mean"] == 356
    assert numbers["history", "B", "time_mean"] == 371.5
    assert numbers["timing", "A", "difference"] == -0.5
    assert numbers["temperature", "B", "difference"] == 25
    assert numbers["temperature", "B", "outside_distance"] == 15
    text = (output / "manuscript/manuscript.md").read_text(encoding="utf-8")
    assert all(number in text for number in ("356.0 K", "371.5 K", "25.0 K", "15.0 K"))
    with (output / "analysis/figures/evidence-panels-source-data.csv").open(
        encoding="utf-8"
    ) as stream:
        rows = list(csv.DictReader(stream))
    profiles = [row for row in rows if row["kind"] == "profile"]
    assert len(profiles) == 6 and max(float(r["time"]) for r in profiles) == 5
    assert {r["source_locator"] for r in profiles} == {
        "csv_records:2",
        "csv_records:3",
        "csv_records:4",
        "csv_records:6",
        "csv_records:7",
        "csv_records:8",
    }
    assert all(json.loads(r["time_window"]) == [0, 5] for r in profiles)
    assert [float(r["difference"]) for r in rows if r["calculation_id"] == "temperature"] == [
        -10,
        25,
    ]
    local = output / "analysis/figures/plot.py"
    original = local.read_bytes()
    runpy.run_path(str(local))
    assert local.read_bytes() == original
    moved = tmp_path / "moved"
    shutil.copytree(output / "manuscript", moved)
    reassembled = assemble_manuscript(moved, moved / "drafts.json", tmp_path / "reassembled")
    assert (reassembled / "manuscript.md").read_text(encoding="utf-8") == text
    with zipfile.ZipFile(docx) as archive:
        xml = ET.fromstring(archive.read("word/document.xml"))
        assert any(name.startswith("word/media/") for name in archive.namelist())
    ns = {
        "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
        "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    }
    assert xml.findall(".//m:oMath", ns)
    body = [
        p for p in xml.findall(".//w:body/w:p", ns) if "We use invented" in "".join(p.itertext())
    ]
    assert len(body) == 1
    props = body[0].find("w:pPr", ns)
    assert props.find("w:ind", ns).get(f"{{{ns['w']}}}firstLine") == "440"
    spacing = props.find("w:spacing", ns)
    assert spacing.get(f"{{{ns['w']}}}before") == spacing.get(f"{{{ns['w']}}}after") == "0"
