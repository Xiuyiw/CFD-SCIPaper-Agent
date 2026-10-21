"""The public report replay needs only its script and installed product APIs."""

import json
import os
import runpy
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/report-writing/run_example.py"


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_report_example_runs_outside_checkout_and_refreshes_bound_author_draft():
    pytest.importorskip("docx")
    with tempfile.TemporaryDirectory(prefix="cfdreport-") as temporary:
        outside = Path(temporary)
        script = outside / "run_example.py"
        shutil.copyfile(EXAMPLE, script)
        output = outside / "output"
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        result = subprocess.run(
            [sys.executable, str(script), str(output)],
            cwd=outside,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert str(output / "refreshed/manuscript.docx") in result.stdout
        summary = _read(output / "example-result.json")
        assert summary["scenario"] == "constructed-report-writing-and-refresh"
        before, after = summary["first_values"], summary["refreshed_values"]
        assert before["excess_A"] == {"value": "20.00", "unit": "%"}
        assert after["excess_A"] == {"value": "50.00", "unit": "%"}
        assert before["intensity_A"]["value"] == "0.060"
        assert after["intensity_A"]["value"] == "0.090"
        for eid in ("drop_A", "drop_B", "reference_B", "intensity_B", "excess_B"):
            assert before[eid] == after[eid]
        assert _read(output / "raw/reference.json") == {"readings": [100, 120]}
        assert _read(output / "raw/A-setup.json") == {"inlet": {"intensity": 0.06}}
        assert _read(output / "raw/A.json")["pressure"]["inlet"] == 120
        first = output / "first"
        refreshed = output / "refreshed"
        assert _read(first / "projection/sources/records/A/reference.json")["readings"][0] == 100
        assert _read(refreshed / "projection/sources/records/A/reference.json")["readings"][0] == 80
        first_md = (first / "manuscript/manuscript.md").read_text(encoding="utf-8")
        fresh_md = (refreshed / "manuscript/manuscript.md").read_text(encoding="utf-8")
        assert "50.00 %" not in first_md and "20.00 %" in first_md
        assert "50.00 %" in fresh_md and "20.00 %" in fresh_md and "0.090" in fresh_md
        assert "Author wording retained" in fresh_md and "not a physical-loss budget" in fresh_md
        drafts = _read(first / "workspace/drafts.json")
        assert list(drafts) == ["methods", "results", "discussion"]
        for name in drafts.values():
            assert (first / "workspace" / name).read_bytes() == (
                refreshed / "workspace" / name
            ).read_bytes()
        writing = _read(refreshed / "workspace/report-writing.json")
        excess = next(item for item in writing["metrics"] if item["evidence_id"] == "excess_A")
        assert excess["denominator"]["evidence_id"] == "reference_A"
        assert all(parent["domain"] == excess["domain"] for parent in excess["parent_support"])
        assert "not validation" in excess["comparison_scope"]
        with ZipFile(refreshed / "manuscript.docx") as archive:
            xml = archive.read("word/document.xml")
        document = ElementTree.fromstring(xml)
        tables = document.findall(
            ".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tbl"
        )
        assert len(tables) == 1
        table_text = " ".join(tables[0].itertext())
        assert "50.00" in table_text and "20.00" in table_text
        assert b"<m:f>" in xml


def test_report_example_refuses_existing_output(tmp_path):
    example = runpy.run_path(str(EXAMPLE))
    output = tmp_path / "existing"
    output.mkdir()
    sentinel = output / "author.txt"
    sentinel.write_text("Keep the author original.", encoding="utf-8")
    with pytest.raises(FileExistsError):
        example["run"](output)
    assert sentinel.read_text(encoding="utf-8") == "Keep the author original."
