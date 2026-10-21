"""The report CLI uses the source-bound prepare and continuation workflow."""

import json
import re
import zipfile
from xml.etree import ElementTree

import pytest
from typer.testing import CliRunner

from cfdpaper.cli import app

runner = CliRunner()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.fixture
def report_inputs(tmp_path):
    root = tmp_path / "raw"
    (root / "records").mkdir(parents=True)
    write(root / "records/A.json", {"pressure": {"in": 3500, "out": 500}})
    (root / "method.md").write_text("Matched inlet/outlet pressure supports.\n", encoding="utf-8")
    study = tmp_path / "study.json"
    write(
        study,
        {
            "title": "Saved pressure report",
            "question": "What does the declared pressure difference show?",
            "context": "Synthetic software fixture with matched pressure supports.",
            "cases": [{"id": "A", "source": "records/A.json"}],
            "quantities": [
                {
                    "id": "drop",
                    "label": "Pressure difference",
                    "unit": "Pa",
                    "output_unit": "kPa",
                    "domain": "same pressure variable and area-weighted inlet/outlet supports",
                    "reference": "/pressure/out",
                    "comparison": "/pressure/in",
                }
            ],
            "support_files": ["method.md"],
        },
    )
    return root, study


def prepare(report_inputs, output):
    root, study = report_inputs
    result = runner.invoke(
        app,
        ["report", "--study", str(study), "--root", str(root), "--output", str(output)],
    )
    assert result.exit_code == 0, result.output
    return result


def test_report_prepares_real_bound_values_and_unfilled_templates(tmp_path, report_inputs):
    root, _ = report_inputs
    original = (root / "records/A.json").read_bytes()
    output = tmp_path / "prepared[author]"

    result = prepare(report_inputs, output)

    assert "Report workspace ready" in result.output
    assert "prepared[author]" in result.output
    assert "workspace/drafts.json" in result.output
    summary = read(output / "workspace/report-writing.json")
    assert summary["row_count"] == 2
    assert summary["metrics"][0]["raw_value"] == 3
    assert summary["metrics"][0]["unit"] == "kPa"
    for sid in ("methods", "results", "discussion"):
        section = read(output / f"workspace/sections/{sid}/input.json")
        metric = next(item for item in section["evidence"] if item.get("result_ref"))
        assert metric["id"] == "drop_A"
        assert metric["result_ref"]["field"] == "difference"
        draft = read(output / f"workspace/sections/{sid}/draft.json")
        assert draft["paragraphs"][0]["text"] == ""
    table = read(output / "workspace/sections/results/draft.json")["tables"][0]
    assert table["rows"][0][-1] == "{{value:drop_A}}"
    assert (output / "projection/sources/support/0/method.md").read_bytes() == (
        root / "method.md"
    ).read_bytes()
    assert (root / "records/A.json").read_bytes() == original


def test_report_continues_actual_drafts_to_refreshed_markdown_and_docx(tmp_path, report_inputs):
    pytest.importorskip("docx")
    prepared = tmp_path / "prepared"
    prepare(report_inputs, prepared)
    workspace = prepared / "workspace"
    originals = {}
    for sid, name in read(workspace / "drafts.json").items():
        path = workspace / name
        draft = read(path)
        draft["paragraphs"][0]["text"] = (
            f"Author wording in {sid}: supported drop {{{{value:drop_A}}}}."
        )
        draft["paragraphs"][0]["evidence_ids"] = list(
            dict.fromkeys([*draft["paragraphs"][0]["evidence_ids"], "drop_A"])
        )
        write(path, draft)
        originals[name] = path.read_bytes()
    write(prepared / "projection/sources/records/A.json", {"pressure": {"in": 4500, "out": 500}})
    output = tmp_path / "continued"

    result = runner.invoke(
        app,
        [
            "report",
            "--workspace",
            str(prepared),
            "--drafts",
            str(workspace / "drafts.json"),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Report candidate assembled" in result.output
    markdown = (output / "manuscript/manuscript.md").read_text(encoding="utf-8")
    assert "Author wording in results" in markdown
    assert "4.000 kPa" in markdown and "3.000 kPa" not in markdown
    with zipfile.ZipFile(output / "manuscript.docx") as archive:
        xml = archive.read("word/document.xml").decode("utf-8")
    text = "".join(ElementTree.fromstring(xml).itertext()).replace("\xa0", " ")
    assert "4.000 kPa" in text and "<w:tbl>" in xml
    assert all((workspace / name).read_bytes() == content for name, content in originals.items())


@pytest.mark.parametrize(
    "options,detail",
    [
        (["--study", "study", "--workspace", "workspace"], "exactly one"),
        (["--study", "study"], "--study requires --root"),
        (["--workspace", "workspace", "--root", "root"], "--root requires --study"),
        (["--study", "study", "--root", "root", "--drafts", "drafts"], "--drafts requires"),
        (["--workspace", "workspace"], "--workspace requires --drafts"),
    ],
)
def test_report_rejects_mixed_or_incomplete_actions_readably(tmp_path, options, detail):
    (tmp_path / "study").write_text("{}", encoding="utf-8")
    (tmp_path / "drafts").write_text("{}", encoding="utf-8")
    (tmp_path / "workspace").mkdir()
    (tmp_path / "root").mkdir()
    output = tmp_path / "fresh"
    paths = [str(tmp_path / value) if not value.startswith("--") else value for value in options]

    result = runner.invoke(app, ["report", *paths, "--output", str(output)])

    assert result.exit_code == 2, result.output
    plain = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
    assert detail in plain
    assert "Traceback" not in plain
    assert not output.exists()
