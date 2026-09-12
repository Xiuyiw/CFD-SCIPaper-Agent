from pathlib import Path
from types import SimpleNamespace

import pytest

from cfdpaper.publication.preview import preview_docx


def test_preview_uses_isolated_copy_and_preserves_docx(tmp_path, monkeypatch):
    source = tmp_path / "paper.docx"
    source.write_bytes(b"test-source")
    monkeypatch.setattr("cfdpaper.publication.preview.shutil.which", lambda _: "soffice")

    def convert(command, **kwargs):
        assert Path(command[-1]) != source
        assert Path(command[-1]).read_bytes() == source.read_bytes()
        assert "--headless" in command
        (Path(command[-2]) / "paper.pdf").write_bytes(b"%PDF-preview")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("cfdpaper.publication.preview.subprocess.run", convert)
    output = preview_docx(source)
    assert output.read_bytes().startswith(b"%PDF-")
    assert source.read_bytes() == b"test-source"
    with pytest.raises(FileExistsError):
        preview_docx(source)


def test_absent_backend_retains_docx(tmp_path, monkeypatch):
    source = tmp_path / "paper.docx"
    source.write_bytes(b"source")
    monkeypatch.setattr("cfdpaper.publication.preview.shutil.which", lambda _: None)
    with pytest.raises(RuntimeError, match="Export its PDF in Word"):
        preview_docx(source)
    assert source.read_bytes() == b"source"
