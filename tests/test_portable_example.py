"""The public portable example consumes the existing analytical author replay."""

import json
import os
import runpy
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import pytest

from cfdpaper.publication.word_return import read_word_return

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/portable-workbench/run_example.py"


@pytest.fixture
def short_tmp_path():
    # Nested manuscript skill copies need room below Windows' default path limit.
    with tempfile.TemporaryDirectory(prefix="cfdportable-") as directory:
        yield Path(directory)


def test_portable_example_continues_author_state_outside_checkout(short_tmp_path):
    tmp_path = short_tmp_path
    author = runpy.run_path(str(ROOT / "examples/author-collaboration/run_example.py"))
    source = tmp_path / "author-output"
    author["run"](source)
    original_docx = (source / "recovered/manuscript.docx").read_bytes()
    original_drafts = (source / "recovered/candidate/drafts.json").read_bytes()
    outside = tmp_path / "outside-checkout"
    outside.mkdir()
    script = outside / "run_example.py"
    shutil.copyfile(EXAMPLE, script)
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    result = subprocess.run(
        [sys.executable, str(script), "../author-output", "continued-output"],
        cwd=outside,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    output = outside / "continued-output"
    report = json.loads((output / "example-result.json").read_text(encoding="utf-8"))
    assert str(output / "continued.docx") in result.stdout
    assert not (output / "transfer").exists()
    assert (output / "receiving-machine/workbench/workbench.json").is_file()
    assert report["inspection"]["status"] == "ready"
    assert report["inspection"]["external_sources"] == []
    assert report["restored_inspection"]["status"] == "ready"
    assert report["restored_inspection"]["external_sources"] == []
    assert report["scenario"] == "analytical-automation-portability"
    final = read_word_return(output / "continued.docx")
    assert final["conflicts"] == []
    assert len(final["comments"]) == 1
    original = read_word_return(source / "recovered/manuscript.docx")
    assert final["comments"][0]["text"] == original["comments"][0]["text"]
    response = next(
        b for b in final["blocks"] if b["kind"] == "paragraph" and b["section_id"] == "response"
    )
    assert "Across the prescribed cases" in response["rendered_text"]
    assert "7.04" in response["rendered_text"]
    assert "21.12" in response["rendered_text"]
    assert "6.40" not in response["rendered_text"]
    with zipfile.ZipFile(output / "continued.docx") as archive:
        assert b"<m:oMath" in archive.read("word/document.xml")
    assert (source / "recovered/manuscript.docx").read_bytes() == original_docx
    assert (source / "recovered/candidate/drafts.json").read_bytes() == original_drafts
    assert (output / "restored/author/manuscript.docx").read_bytes() == original_docx


def test_portable_example_requires_existing_author_replay(tmp_path):
    example = runpy.run_path(str(EXAMPLE))
    output = tmp_path / "new-output"

    with pytest.raises(FileNotFoundError, match="author-collaboration"):
        example["run"](tmp_path / "not-generated", output)

    assert not output.exists()
