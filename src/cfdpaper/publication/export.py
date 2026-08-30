"""Minimal Markdown/LaTeX manuscript assembly with explicit asset checks."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field, model_validator

SUPPORTED_FIGURE_SUFFIXES = {
    "markdown": frozenset({".png", ".jpg", ".jpeg", ".gif", ".svg"}),
    "latex": frozenset({".png", ".jpg", ".jpeg", ".pdf", ".eps"}),
}


class PublicationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class ManuscriptSection(PublicationModel):
    section_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)


class ManuscriptFigure(PublicationModel):
    figure_id: str = Field(min_length=1)
    path: Path
    caption: str = Field(min_length=1)
    after_section_id: str = Field(min_length=1)


class ManuscriptTable(PublicationModel):
    table_id: str = Field(min_length=1)
    caption: str = Field(min_length=1)
    columns: list[str] = Field(min_length=1)
    rows: list[list[str]] = Field(min_length=1)
    after_section_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def rows_match_columns(self) -> ManuscriptTable:
        width = len(self.columns)
        if any(len(row) != width for row in self.rows):
            raise ValueError("every table row must match the declared column count")
        return self


class ManuscriptDocument(PublicationModel):
    title: str = Field(min_length=1)
    sections: list[ManuscriptSection] = Field(min_length=1)
    figures: list[ManuscriptFigure] = Field(default_factory=list)
    tables: list[ManuscriptTable] = Field(default_factory=list)

    @model_validator(mode="after")
    def record_ids_are_unique(self) -> ManuscriptDocument:
        for label, identifiers in (
            ("section", [item.section_id for item in self.sections]),
            ("figure", [item.figure_id for item in self.figures]),
            ("table", [item.table_id for item in self.tables]),
        ):
            if len(identifiers) != len(set(identifiers)):
                raise ValueError(f"{label} IDs must be unique")
        return self


class AssemblyCheckItem(PublicationModel):
    check_id: str = Field(min_length=1)
    status: Literal["pass", "fail"]
    detail: str = Field(min_length=1)


class DocumentAssemblyResult(PublicationModel):
    status: Literal["complete", "failed"]
    output_format: Literal["markdown", "latex"]
    output_path: Path
    checklist: list[AssemblyCheckItem]


def _nonempty(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def _relative_asset_path(path: Path, output_path: Path) -> str:
    return Path(os.path.relpath(path.resolve(), output_path.parent)).as_posix()


def _markdown_destination(relative_path: str) -> str:
    encoded = quote(relative_path, safe="/._~-")
    return f"<{encoded}>" if encoded != relative_path else relative_path


def _markdown_escape_alt(value: str) -> str:
    return value.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def _markdown_table(table: ManuscriptTable) -> str:
    def cell(value: str) -> str:
        return value.replace("|", "\\|").replace("\n", " ")

    header = "| " + " | ".join(cell(item) for item in table.columns) + " |"
    divider = "| " + " | ".join("---" for _ in table.columns) + " |"
    rows = ["| " + " | ".join(cell(item) for item in row) + " |" for row in table.rows]
    return "\n".join([f"**{table.caption}**", "", header, divider, *rows])


def _latex_escape(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "^": r"\textasciicircum{}",
        "~": r"\textasciitilde{}",
    }
    return "".join(replacements.get(character, character) for character in value)


def _latex_table(table: ManuscriptTable) -> str:
    column_spec = "l" * len(table.columns)
    header = " & ".join(_latex_escape(item) for item in table.columns) + r" \\"
    rows = [" & ".join(_latex_escape(item) for item in row) + r" \\" for row in table.rows]
    return "\n".join(
        [
            r"\begin{table}[htbp]",
            r"\centering",
            f"\\caption{{{_latex_escape(table.caption)}}}",
            f"\\begin{{tabular}}{{{column_spec}}}",
            header,
            r"\hline",
            *rows,
            r"\end{tabular}",
            r"\end{table}",
        ]
    )


def _validate_assembly(
    document: ManuscriptDocument,
    output_path: Path,
    output_format: Literal["markdown", "latex"],
) -> list[AssemblyCheckItem]:
    checks = [
        AssemblyCheckItem(
            check_id="sections",
            status="pass",
            detail=f"{len(document.sections)} manuscript section(s) supplied",
        )
    ]
    expected_suffix = ".md" if output_format == "markdown" else ".tex"
    checks.append(
        AssemblyCheckItem(
            check_id="output-format",
            status="pass" if output_path.suffix.lower() == expected_suffix else "fail",
            detail=(
                f"output suffix matches {output_format}"
                if output_path.suffix.lower() == expected_suffix
                else f"{output_format} output requires {expected_suffix} suffix"
            ),
        )
    )

    section_ids = {section.section_id for section in document.sections}
    for figure in document.figures:
        if not _nonempty(figure.path):
            checks.append(
                AssemblyCheckItem(
                    check_id=f"figure-file:{figure.figure_id}",
                    status="fail",
                    detail=f"figure file is missing or empty:{figure.path}",
                )
            )
        else:
            checks.append(
                AssemblyCheckItem(
                    check_id=f"figure-file:{figure.figure_id}",
                    status="pass",
                    detail=f"figure file is nonempty:{figure.path}",
                )
            )
        if figure.path.suffix.lower() not in SUPPORTED_FIGURE_SUFFIXES[output_format]:
            checks.append(
                AssemblyCheckItem(
                    check_id=f"figure-format:{figure.figure_id}",
                    status="fail",
                    detail=(
                        f"figure:{figure.figure_id} format {figure.path.suffix.lower()} "
                        f"is not supported by {output_format}"
                    ),
                )
            )
        if figure.after_section_id not in section_ids:
            checks.append(
                AssemblyCheckItem(
                    check_id=f"figure-placement:{figure.figure_id}",
                    status="fail",
                    detail=(
                        f"figure:{figure.figure_id} targets missing section:"
                        f"{figure.after_section_id}"
                    ),
                )
            )

    for table in document.tables:
        checks.append(
            AssemblyCheckItem(
                check_id=f"table-placement:{table.table_id}",
                status="pass" if table.after_section_id in section_ids else "fail",
                detail=(
                    f"table:{table.table_id} has a valid section target"
                    if table.after_section_id in section_ids
                    else f"table:{table.table_id} targets missing section:{table.after_section_id}"
                ),
            )
        )
    return checks


def _render_markdown(document: ManuscriptDocument, output_path: Path) -> str:
    parts = [f"# {document.title}"]
    for section in document.sections:
        parts.extend([f"## {section.title}", section.body])
        for figure in document.figures:
            if figure.after_section_id == section.section_id:
                relative_path = _relative_asset_path(figure.path, output_path)
                destination = _markdown_destination(relative_path)
                caption = _markdown_escape_alt(figure.caption)
                parts.append(f"![{caption}]({destination})")
        for table in document.tables:
            if table.after_section_id == section.section_id:
                parts.append(_markdown_table(table))
    return "\n\n".join(parts) + "\n"


def _render_latex(
    document: ManuscriptDocument,
    latex_assets: dict[str, str],
) -> str:
    parts = [
        r"\documentclass{article}",
        r"\usepackage{graphicx}",
        f"\\title{{{_latex_escape(document.title)}}}",
        r"\begin{document}",
        r"\maketitle",
    ]
    for section in document.sections:
        parts.extend(
            [
                f"\\section{{{_latex_escape(section.title)}}}",
                _latex_escape(section.body),
            ]
        )
        for figure in document.figures:
            if figure.after_section_id == section.section_id:
                parts.extend(
                    [
                        r"\begin{figure}[htbp]",
                        r"\centering",
                        f"\\includegraphics[width=\\linewidth]{{{latex_assets[figure.figure_id]}}}",
                        f"\\caption{{{_latex_escape(figure.caption)}}}",
                        r"\end{figure}",
                    ]
                )
        for table in document.tables:
            if table.after_section_id == section.section_id:
                parts.append(_latex_table(table))
    parts.append(r"\end{document}")
    return "\n\n".join(parts) + "\n"


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_asset_stem(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-.")
    return sanitized or "figure"


def _prepare_latex_assets(
    document: ManuscriptDocument,
    output_path: Path,
) -> dict[str, str]:
    assets_directory = output_path.parent / "assets"
    assets_directory.mkdir(parents=True, exist_ok=True)
    prepared: dict[str, str] = {}
    for figure in document.figures:
        digest = _file_sha256(figure.path)
        filename = f"{_safe_asset_stem(figure.figure_id)}-{digest[:16]}{figure.path.suffix.lower()}"
        destination = assets_directory / filename
        if not destination.is_file() or _file_sha256(destination) != digest:
            temporary_path: Path | None = None
            try:
                with (
                    figure.path.open("rb") as source,
                    tempfile.NamedTemporaryFile(
                        mode="wb",
                        dir=assets_directory,
                        prefix=f".{filename}.",
                        suffix=".tmp",
                        delete=False,
                    ) as temporary,
                ):
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        temporary.write(chunk)
                    temporary.flush()
                    os.fsync(temporary.fileno())
                    temporary_path = Path(temporary.name)
                if _file_sha256(temporary_path) != digest:
                    raise OSError(f"copied figure hash mismatch:{figure.path}")
                os.replace(temporary_path, destination)
            except OSError:
                if temporary_path is not None:
                    temporary_path.unlink(missing_ok=True)
                raise
        prepared[figure.figure_id] = f"assets/{filename}"
    return prepared


def export_manuscript(
    document: ManuscriptDocument,
    output_path: Path,
    *,
    output_format: Literal["markdown", "latex"],
) -> DocumentAssemblyResult:
    """Assemble a manuscript or return a failed checklist without writing it."""

    resolved_output = output_path.expanduser().resolve()
    checklist = _validate_assembly(document, resolved_output, output_format)
    if any(item.status == "fail" for item in checklist):
        return DocumentAssemblyResult(
            status="failed",
            output_format=output_format,
            output_path=resolved_output,
            checklist=checklist,
        )

    temporary_path: Path | None = None
    try:
        resolved_output.parent.mkdir(parents=True, exist_ok=True)
        rendered = (
            _render_markdown(document, resolved_output)
            if output_format == "markdown"
            else _render_latex(
                document,
                _prepare_latex_assets(document, resolved_output),
            )
        )
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=resolved_output.parent,
            prefix=f".{resolved_output.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(rendered)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        if not _nonempty(temporary_path):
            raise OSError("temporary output is missing or empty")
        os.replace(temporary_path, resolved_output)
    except (OSError, ValueError) as error:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        checklist.append(
            AssemblyCheckItem(
                check_id="output-write",
                status="fail",
                detail=f"output write failed:{error}",
            )
        )
        return DocumentAssemblyResult(
            status="failed",
            output_format=output_format,
            output_path=resolved_output,
            checklist=checklist,
        )

    checklist.append(
        AssemblyCheckItem(
            check_id="output-written",
            status="pass" if _nonempty(resolved_output) else "fail",
            detail=f"assembled output is nonempty:{resolved_output}",
        )
    )
    status: Literal["complete", "failed"] = (
        "complete" if checklist[-1].status == "pass" else "failed"
    )
    return DocumentAssemblyResult(
        status=status,
        output_format=output_format,
        output_path=resolved_output,
        checklist=checklist,
    )
