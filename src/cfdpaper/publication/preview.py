"""Optional LibreOffice preview of a newly exported document."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def preview_docx(path: Path) -> Path:
    """Convert an isolated copy; leave the source document and existing PDFs untouched."""
    path = Path(path).resolve()
    if path.suffix.lower() != ".docx" or not path.is_file():
        raise ValueError("PDF preview requires an existing DOCX")
    output = path.with_suffix(".pdf")
    if output.exists():
        raise FileExistsError(f"Preserving existing PDF: {output}")
    executable = shutil.which("soffice") or shutil.which("libreoffice")
    if executable is None:
        raise RuntimeError("LibreOffice was not found; DOCX is ready. Export its PDF in Word.")
    with tempfile.TemporaryDirectory(prefix="cfdpaper-preview-") as directory:
        root = Path(directory)
        source = root / path.name
        shutil.copyfile(path, source)
        target = root / "pdf"
        target.mkdir()
        result = subprocess.run(
            [
                executable,
                f"-env:UserInstallation={(root / 'profile').as_uri()}",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(target),
                str(source),
            ],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=120,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        pdf = target / output.name
        if result.returncode or not pdf.is_file() or not pdf.read_bytes().startswith(b"%PDF-"):
            raise RuntimeError(f"LibreOffice preview failed: {result.stdout} {result.stderr}")
        # Exclusive destination creation also preserves author files created during conversion.
        with output.open("xb") as destination, pdf.open("rb") as stream:
            shutil.copyfileobj(stream, destination)
    return output
