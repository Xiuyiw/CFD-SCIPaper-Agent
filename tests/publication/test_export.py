import hashlib
import re
from collections import Counter
from pathlib import Path

from cfdpaper.publication.export import (
    ManuscriptDocument,
    ManuscriptFigure,
    ManuscriptSection,
    ManuscriptTable,
    export_manuscript,
)


def parse_commonmark_images(text: str) -> list[tuple[str, str]]:
    pattern = re.compile(r"!\[((?:\\.|[^\]])*)\]\(<([^>]*)>\)")

    def unescape(value: str) -> str:
        return re.sub(r"\\(.)", r"\1", value)

    return [(destination, unescape(caption)) for caption, destination in pattern.findall(text)]


def document_with_figure(figure_path: Path) -> ManuscriptDocument:
    return ManuscriptDocument(
        title="Generic CFD response across sampled settings",
        sections=[
            ManuscriptSection(
                section_id="results",
                title="Results",
                body="The sampled cases show a bounded response trend.",
            )
        ],
        figures=[
            ManuscriptFigure(
                figure_id="fig-1",
                path=figure_path,
                caption="Velocity distribution for the sampled cases",
                after_section_id="results",
            )
        ],
        tables=[
            ManuscriptTable(
                table_id="table-1",
                caption="Sampled response values",
                columns=["Case", "Response (-)"],
                rows=[["A", "0.81"], ["B", "0.94"]],
                after_section_id="results",
            )
        ],
    )


def latex_structure_is_balanced(text: str) -> bool:
    depth = 0
    for index, character in enumerate(text):
        escaped = index > 0 and text[index - 1] == "\\"
        if character == "{" and not escaped:
            depth += 1
        elif character == "}" and not escaped:
            depth -= 1
            if depth < 0:
                return False
    begins = Counter(re.findall(r"\\begin\{([^}]+)\}", text))
    ends = Counter(re.findall(r"\\end\{([^}]+)\}", text))
    return depth == 0 and begins == ends


def test_markdown_export_embeds_existing_figure_and_table(tmp_path: Path) -> None:
    figure = tmp_path / "response.svg"
    figure.write_text("<svg><text>response</text></svg>", encoding="utf-8")
    output = tmp_path / "manuscript.md"

    result = export_manuscript(
        document_with_figure(figure),
        output,
        output_format="markdown",
    )
    text = output.read_text(encoding="utf-8")

    assert result.status == "complete"
    assert result.output_path == output.resolve()
    assert f"![Velocity distribution for the sampled cases]({figure.name})" in text
    assert "| Case | Response (-) |" in text
    assert all(item.status == "pass" for item in result.checklist)


def test_latex_export_embeds_existing_figure_and_table(tmp_path: Path) -> None:
    figure_dir = tmp_path / "figure assets"
    figure_dir.mkdir()
    figure = figure_dir / "response #50% (mean).pdf"
    figure.write_bytes(b"%PDF-1.4\nsynthetic fixture\n%%EOF")
    output = tmp_path / "assembled paper" / "manuscript.tex"
    document = document_with_figure(figure)
    document.title = "Response ^ and ~ diagnostics"
    document.sections[0].body = "Reserved # % & _ { } and \\ characters."
    document.figures[0].caption = "Response ^ ~ #50%"

    result = export_manuscript(
        document,
        output,
        output_format="latex",
    )
    text = output.read_text(encoding="utf-8")
    asset_name = f"fig-1-{hashlib.sha256(figure.read_bytes()).hexdigest()[:16]}.pdf"

    assert result.status == "complete"
    assert "\\usepackage{graphicx}" in text
    assert f"\\includegraphics[width=\\linewidth]{{assets/{asset_name}}}" in text
    assert (output.parent / "assets" / asset_name).is_file()
    assert "\\textasciicircum{}" in text
    assert "\\textasciitilde{}" in text
    assert "\\begin{tabular}" in text
    assert latex_structure_is_balanced(text)


def test_export_fails_explicitly_without_writing_when_figure_is_missing(
    tmp_path: Path,
) -> None:
    missing_figure = tmp_path / "missing.svg"
    output = tmp_path / "manuscript.md"

    result = export_manuscript(
        document_with_figure(missing_figure),
        output,
        output_format="markdown",
    )

    assert result.status == "failed"
    assert output.exists() is False
    assert [item.detail for item in result.checklist if item.status == "fail"] == [
        f"figure file is missing or empty:{missing_figure}"
    ]


def test_export_fails_when_figure_is_not_assigned_to_a_real_section(
    tmp_path: Path,
) -> None:
    figure = tmp_path / "response.svg"
    figure.write_text("<svg/>", encoding="utf-8")
    document = document_with_figure(figure)
    document.figures[0].after_section_id = "absent-section"
    output = tmp_path / "manuscript.md"

    result = export_manuscript(document, output, output_format="markdown")

    assert result.status == "failed"
    assert output.exists() is False
    assert [item.detail for item in result.checklist if item.status == "fail"] == [
        "figure:fig-1 targets missing section:absent-section"
    ]


def test_export_rejects_unsupported_figure_format(tmp_path: Path) -> None:
    figure = tmp_path / "response.txt"
    figure.write_text("not an embeddable image", encoding="utf-8")
    output = tmp_path / "manuscript.md"

    result = export_manuscript(
        document_with_figure(figure),
        output,
        output_format="markdown",
    )

    assert result.status == "failed"
    assert output.exists() is False
    assert [item.detail for item in result.checklist if item.status == "fail"] == [
        "figure:fig-1 format .txt is not supported by markdown"
    ]


def test_failed_export_preserves_previous_success_output(tmp_path: Path) -> None:
    output = tmp_path / "manuscript.md"
    previous = "previous successful manuscript"
    output.write_text(previous, encoding="utf-8")

    result = export_manuscript(
        document_with_figure(tmp_path / "missing.svg"),
        output,
        output_format="markdown",
    )

    assert result.status == "failed"
    assert output.read_text(encoding="utf-8") == previous


def test_successful_export_replaces_previous_output(tmp_path: Path) -> None:
    figure = tmp_path / "response.svg"
    figure.write_text("<svg/>", encoding="utf-8")
    output = tmp_path / "manuscript.md"
    output.write_text("previous successful manuscript", encoding="utf-8")

    result = export_manuscript(
        document_with_figure(figure),
        output,
        output_format="markdown",
    )

    assert result.status == "complete"
    assert output.read_text(encoding="utf-8").startswith("# Generic CFD response")


def test_atomic_replace_failure_preserves_previous_output(
    tmp_path: Path,
    monkeypatch,
) -> None:
    figure = tmp_path / "response.svg"
    figure.write_text("<svg/>", encoding="utf-8")
    output = tmp_path / "manuscript.md"
    previous = "previous successful manuscript"
    output.write_text(previous, encoding="utf-8")

    def deny_replace(source, destination) -> None:
        raise PermissionError(f"replace denied:{source}->{destination}")

    monkeypatch.setattr("cfdpaper.publication.export.os.replace", deny_replace)

    result = export_manuscript(
        document_with_figure(figure),
        output,
        output_format="markdown",
    )

    assert result.status == "failed"
    assert output.read_text(encoding="utf-8") == previous
    assert not list(tmp_path.glob(".manuscript.md.*.tmp"))
    assert any(item.check_id == "output-write" for item in result.checklist)


def test_export_returns_failed_checklist_for_invalid_output_parent(tmp_path: Path) -> None:
    figure = tmp_path / "response.svg"
    figure.write_text("<svg/>", encoding="utf-8")
    parent_file = tmp_path / "not-a-directory"
    parent_file.write_text("blocking file", encoding="utf-8")
    output = parent_file / "manuscript.md"

    result = export_manuscript(
        document_with_figure(figure),
        output,
        output_format="markdown",
    )

    assert result.status == "failed"
    assert any(
        item.check_id == "output-write" and item.status == "fail" for item in result.checklist
    )


def test_export_handles_paths_with_spaces(tmp_path: Path) -> None:
    output_dir = tmp_path / "assembled paper"
    figure_dir = tmp_path / "figure assets"
    figure_dir.mkdir()
    figure = figure_dir / "response (field)#50%.svg"
    figure.write_text("<svg/>", encoding="utf-8")
    output = output_dir / "manuscript draft.md"
    document = document_with_figure(figure)
    caption = r"Velocity [mean] (50%) #1 \ trace"
    document.figures[0].caption = caption

    result = export_manuscript(
        document,
        output,
        output_format="markdown",
    )

    assert result.status == "complete"
    assert output.is_file()
    text = output.read_text(encoding="utf-8")
    expected_src = "../figure%20assets/response%20%28field%29%2350%25.svg"
    assert f"(<{expected_src}>)" in text
    image_tokens = parse_commonmark_images(text)
    assert image_tokens == [(expected_src, caption)]
