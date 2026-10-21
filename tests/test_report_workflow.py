"""The direct report route reuses bindings and refreshes raw retained JSON."""

import json
import shutil
import zipfile
from pathlib import Path

import pytest

from cfdpaper.host_tools import report_task


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    Path(path).write_text(json.dumps(value), encoding="utf-8")


def prepare(root, output):
    root.mkdir()
    write(root / "A.json", {"pressure": {"in": 3500, "out": 500}})
    (root / "method.md").write_text("Matched pressure operator and supports.\n", encoding="utf-8")
    return report_task(
        output,
        root=root,
        cases=[{"id": "A", "source": "A.json"}],
        quantities=[
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
        title="Saved pressure report comparison",
        question="What does the supported drop show?",
        support_files=[Path("method.md")],
    )


def fill_drafts(prepared):
    workspace = Path(prepared["artifacts"]["workspace"])
    for sid, name in read(workspace / "drafts.json").items():
        path = workspace / name
        draft = read(path)
        data = read(path.parent / "input.json")
        ids = [e["id"] for e in data["evidence"]]
        metric = next(e["id"] for e in data["evidence"] if e.get("result_ref"))
        draft["paragraphs"] = [
            {
                "text": f"Author wording preserved in {sid}: supported drop "
                + "{{value:"
                + metric
                + "}}.",
                "evidence_ids": ids,
                "figure_ids": [],
            }
        ]
        write(path, draft)
    return workspace / "drafts.json"


def test_report_task_moves_and_refreshes_raw_values_without_retyping_or_overwrite(tmp_path):
    original = tmp_path / "original"
    first = tmp_path / "first"
    prepared = prepare(original, first)
    original_bytes = (original / "A.json").read_bytes()
    drafts = fill_drafts(prepared)
    draft_before = {
        p.parent.name: p.read_bytes() for p in drafts.parent.glob("sections/*/draft.json")
    }
    moved = tmp_path / "moved"
    shutil.move(first, moved)
    raw_path = moved / "projection/sources/records/A.json"
    raw = read(raw_path)
    raw["pressure"]["in"] = 4500
    write(raw_path, raw)

    result = report_task(
        tmp_path / "updated", workspace=moved, drafts=moved / "workspace/drafts.json"
    )

    markdown = Path(result["artifacts"]["manuscript"]).read_text(encoding="utf-8")
    assert "4.000 kPa" in markdown
    assert "3.000 kPa" not in markdown
    assert "Author wording preserved" in markdown
    assert (original / "A.json").read_bytes() == original_bytes
    for p in (moved / "workspace").glob("sections/*/draft.json"):
        assert p.read_bytes() == draft_before[p.parent.name]
    recipe = read(result["artifacts"]["recipe"])
    assert recipe["cases"][0]["source"] == "projection/sources/records/A.json"
    assert str(tmp_path) not in json.dumps(recipe)
    assert (tmp_path / "updated/projection/sources/support/0/method.md").is_file()
    with zipfile.ZipFile(result["artifacts"]["docx"]) as archive:
        assert b"<w:tbl>" in archive.read("word/document.xml")
    candidate = tmp_path / "updated"
    for p in (candidate / "workspace").glob("sections/*/draft.json"):
        assert p.read_bytes() == draft_before[p.parent.name]
    assert read(candidate / "workspace/report-writing.json")["pending_sections"] == []
    next_raw = candidate / "projection/sources/records/A.json"
    raw["pressure"]["in"] = 5500
    write(next_raw, raw)
    # A stale intermediate table must not replace the currently retained JSON.
    stale_csv = candidate / "projection/sources/report-values.csv"
    stale_csv.write_text(stale_csv.read_text().replace("4.5", "99.5"), encoding="utf-8")
    again = report_task(
        tmp_path / "continued", workspace=candidate, drafts=candidate / "workspace/drafts.json"
    )
    current = Path(again["artifacts"]["manuscript"]).read_text(encoding="utf-8")
    assert "5.000 kPa" in current
    assert "4.000 kPa" not in current
    assert "Author wording preserved" in current


def test_report_task_rejects_mixed_new_and_resume_inputs_without_an_output(tmp_path):
    output = tmp_path / "new"
    with pytest.raises(ValueError, match="Choose workspace"):
        report_task(output, root=tmp_path, workspace=tmp_path)
    assert not output.exists()
