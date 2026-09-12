"""Host-AI section writing: portable inputs, declared evidence, and editable output.

Validation checks references and asset readability, not the truth of free prose.
"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal

from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator, model_validator

from cfdpaper.publication.elements import MathNode, SectionEquation, SectionTable, math_text
from cfdpaper.publication.style import FigureSizing, PublicationStyle, figure_placement


class _Record(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="after")
    @classmethod
    def reject_blank_required_text(cls, value, info):
        if isinstance(value, str) and info.field_name not in {"context", "unit"}:
            if not value.strip():
                raise ValueError(f"{info.field_name} must not be blank")
        return value


class _Figure(_Record):
    id: str = Field(pattern=r"^[A-Za-z0-9_.-]+$")
    path: str = Field(min_length=1)
    caption: str = Field(min_length=1)
    description: str = Field(min_length=1)
    sizing: FigureSizing = Field(default_factory=FigureSizing)


class _ResultRef(_Record):
    calculation_id: StrictStr
    group: StrictStr
    field: Literal[
        "count", "sum", "mean", "cv", "area", "rate", "mean_flux", "regional_flux", "shares"
    ]
    source_record: int | None = Field(default=None, strict=True, ge=2)
    places: int = Field(default=3, strict=True, ge=0, le=12)
    percentage: bool = Field(default=False, strict=True)


class _Evidence(_Record):
    id: str = Field(pattern=r"^[A-Za-z0-9_.-]+$")
    text: str = Field(min_length=1)
    source: str = Field(min_length=1)
    kind: Literal["observation", "metric", "interpretation", "literature"]
    value: StrictStr | None = None
    unit: StrictStr = ""
    result_ref: _ResultRef | None = None

    @model_validator(mode="after")
    def finite_metric(self):
        if self.result_ref is not None:
            if self.value is not None or self.unit or self.kind != "metric":
                raise ValueError("result_ref requires metric evidence without manual value or unit")
        if self.kind == "metric" and self.value is not None:
            try:
                valid = Decimal(self.value).is_finite()
            except InvalidOperation:
                valid = False
            if not valid:
                raise ValueError("Metric value must be a finite numeric string")
        return self


class _Duty(_Record):
    purpose: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    figure_ids: list[str] = Field(min_length=1)


class _TableCalculation(_Record):
    id: str = Field(pattern=r"^[A-Za-z0-9_.-]+$")
    source: str
    operation: Literal["population", "partition"]
    columns: dict[str, StrictStr]
    units: dict[str, StrictStr]
    domain: str
    group_by: str | None = None

    @model_validator(mode="after")
    def explicit_definition(self):
        required = {"value"} if self.operation == "population" else {"area", "rate"}
        if set(self.columns) != required or set(self.units) != required:
            raise ValueError("Calculation columns and units must match its operation")
        if any(not c.strip() for c in self.columns.values()):
            raise ValueError("Calculation columns must not be blank")
        return self


class _Input(_Record):
    section_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    question: str = Field(min_length=1)
    figures: list[_Figure] = Field(min_length=1)
    evidence: list[_Evidence] = Field(min_length=1)
    duties: list[_Duty] = Field(min_length=1)
    context: str = ""
    source_files: list[str] = Field(default_factory=list)
    table_calculations: list[_TableCalculation] = Field(default_factory=list)
    style: PublicationStyle = Field(default_factory=PublicationStyle)


class _Paragraph(_Record):
    text: str = Field(min_length=1)
    evidence_ids: list[str]
    figure_ids: list[str]
    inline_math: dict[str, MathNode] = Field(default_factory=dict)


class _Draft(_Record):
    title: str = Field(min_length=1)
    paragraphs: list[_Paragraph] = Field(min_length=1)
    captions: dict[str, str]
    evidence_notes: list[StrictStr]
    image_observations: dict[str, Literal["viewed", "author-provided", "not-viewed"]]
    observation_notes: dict[str, StrictStr] = Field(default_factory=dict)
    tables: list[SectionTable] = Field(default_factory=list)
    equations: list[SectionEquation] = Field(default_factory=list)

    @field_validator("captions")
    @classmethod
    def nonempty_captions(cls, value):
        if any(not text.strip() for text in value.values()):
            raise ValueError("Every figure requires a nonempty caption")
        return value


def _read(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _fresh(path: Path):
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite author-owned output: {path}")


@contextmanager
def _stage(output: Path):
    _fresh(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".section-", dir=output.parent) as temp:
        staged = Path(temp) / "result"
        staged.mkdir()
        yield staged
        _fresh(output)
        staged.rename(output)


def _load_input(path: Path) -> _Input:
    data = _Input.model_validate(_read(path))
    calc_ids = [c.id for c in data.table_calculations]
    if len(calc_ids) != len(set(calc_ids)):
        raise ValueError("Calculation IDs must be unique")
    for calculation in data.table_calculations:
        if calculation.source not in data.source_files:
            data.source_files.append(calculation.source)
    asset_ids = [figure.id.casefold() for figure in data.figures]
    if len(asset_ids) != len(set(asset_ids)):
        raise ValueError("Figure IDs must be unique on case-insensitive filesystems")
    for records in (data.figures, data.evidence):
        ids = [item.id for item in records]
        if len(ids) != len(set(ids)):
            raise ValueError("Record IDs must be unique")
    evidence = {item.id for item in data.evidence}
    figures = {item.id for item in data.figures}
    for duty in data.duties:
        _references(duty.evidence_ids, evidence)
        _references(duty.figure_ids, figures)
    for figure in data.figures:
        image_path = (path.parent / figure.path).resolve()
        if image_path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
            raise ValueError("Section figures must be PNG, JPEG or TIFF")
        try:
            with Image.open(image_path) as image:
                image.verify()
            with Image.open(image_path) as image:
                image.load()
        except (OSError, ValueError) as exc:
            raise ValueError(f"Unreadable figure {figure.id}: {image_path}") from exc
    return data


def _references(ids, allowed):
    unknown = set(ids) - set(allowed)
    if unknown:
        raise ValueError(f"Unresolved IDs: {sorted(unknown)}")


def _copy_figures(data: _Input, source_dir: Path, output: Path):
    (output / "figures").mkdir()
    for figure in data.figures:
        source = (source_dir / figure.path).resolve()
        relative = Path("figures") / (figure.id + source.suffix.lower())
        shutil.copyfile(source, output / relative)
        figure.path = relative.as_posix()


def _copy_sources(data: _Input, source_dir: Path, output: Path):
    """Copy only explicitly supplied small review materials, preserving relative locators."""
    for name in data.source_files:
        relative = Path(name)
        if (
            not relative.parts
            or relative.is_absolute()
            or ".." in relative.parts
            or relative.parts[0] != "sources"
        ):
            raise ValueError("source_files must use relative sources/ paths")
        source = source_dir / relative
        if not source.is_file():
            raise ValueError(f"Missing source file: {name}")
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)


def _calculate_sources(data: _Input, output: Path, *, write=True):
    """Compute on copied source tables, before the host begins drafting."""
    from cfdpaper.publication.table_evidence import calculate_table

    results = []
    for item in data.table_calculations:
        relative = Path(item.source)
        if relative.is_absolute() or ".." in relative.parts or relative.parts[:1] != ("sources",):
            raise ValueError("Calculation sources must use relative sources/ paths")
        result = calculate_table(
            output / item.source,
            operation=item.operation,
            columns=item.columns,
            group_by=item.group_by,
        )
        results.append({**item.model_dump(), **result})
    if results and write:
        _write(output / "table-results.json", results)
    return results


TASK = """# Write a figure-grounded subsection with the host AI

Read input.json, then actually open every figure when image viewing is available.
Figure descriptions are author-provided observations, not proof that you viewed an image.
Record each figure as viewed, author-provided, or not-viewed in image_observations.
Produce a fresh JSON draft following draft-template.json; do not overwrite author edits.
Use a coherent subsection answering question and every duty, not one isolated caption per figure.
Compare cases, connect observations to defensible transport/source/geometry physics, and distinguish
observations, derived metrics, interpretations and literature. Do not invent measurements,
quantities, citations, boundary conditions, causal proof, or missing image observations.
Keep uncertainty about assumptions, source quality, normalization, and review questions in
evidence_notes, separate from reader-facing manuscript prose. Qualify scientific claims in prose
where the qualification is necessary to interpret them. Source locators are declared inputs;
the package has not independently verified the source or the physics. Explicit source_files
are copied under sources/. Read the actual tables before deriving claims; use table_evidence
helpers for equal-observation CV, partition identities and conditional temperature checks.
Document statistical domain, weighting, units and applicable cases in the evidence descriptions.
Record concrete visible features in observation_notes, keyed by figure ID; a viewed flag alone
does not describe what the image establishes. Never manufacture an observation.
If table-results.json exists, read its source definitions, units, groups and all results before
drafting. These were calculated from the copied CSVs. Missing groups remain missing; use supported
groups and report the specific gap separately. Population CV uses equal records and ddof=0;
partition results describe the supplied rows, not proof of exhaustive or disjoint physical regions.
No unit conversion or causal interpretation is performed. Resolve any conflict with supplied
metric JSON before quoting it; do not favor whichever number makes the narrative stronger.
Check free numbers in prose and captions against source values, not only token expansion.
Round each display directly from the original number. Different decimal places can both be valid.
Design plots at their final physical size with common scales and readable labels; source pixels
alone do not ensure document readability. DOCX is a general review layout, not a journal template;
render and inspect every page, reporting the actual renderer and any font substitution separately.
Check units, boundary conditions, comparison basis and numerical limitations. A sum of
cell-integrated heat rates is not a sum of per-volume heat-release rates: the latter requires
cell-volume weighting. Keep all compared quantities on a consistent control-volume basis.

Token syntax inside paragraph text and captions:
- {{value:evidence_id}} inserts the supplied value, or resolves result_ref from the current
  source table with its declared precision and computed unit. Do not duplicate it as a manual value.
- {{math:local_id}} inserts a paragraph's declared inline_math expression as editable Word math.
  Use explicit sub/sup/fraction nodes for scientific notation, not underscore strings in prose.
- Optional tables/equations use the finite structures in the packaged writing reference.
  {{table:ID}} and {{equation:ID}} reference their identifiers; these are not inline expressions.
- {{figure:figure_id}} inserts Figure followed by the declared figure ID.
- {{cite:evidence_id}} inserts a numbered literature citation; kind must be literature.
Use these tokens for supplied quantitative values, figure references and literature citations.
List every paragraph's evidence_ids and figure_ids; tokens must be declared in those lists.
All duty evidence and figures must be covered by paragraph declarations. Supply all captions.
Free scientific prose is allowed; successful structural validation is not semantic approval.
Return only the JSON draft, with no approval claim. A human reviews the assembled section.
"""


def prepare_section(input_path: Path, output_dir: Path) -> Path:
    """Copy declared inputs and valid raster figures into a fresh writing package."""
    input_path, output_dir = Path(input_path), Path(output_dir)
    _fresh(output_dir)
    data = _load_input(input_path)
    with _stage(output_dir) as staged:
        _copy_figures(data, input_path.parent, staged)
        _copy_sources(data, input_path.parent, staged)
        _calculate_sources(data, staged)
        _write(staged / "input.json", data.model_dump())
        (staged / "TASK.md").write_text(TASK, encoding="utf-8")
        _write(
            staged / "draft-template.json",
            {
                "title": data.title,
                "paragraphs": [{"text": "", "evidence_ids": [], "figure_ids": []}],
                "captions": {f.id: f.caption for f in data.figures},
                "evidence_notes": [],
                "image_observations": {f.id: "not-viewed" for f in data.figures},
                "observation_notes": {},
                "tables": [],
                "equations": [],
            },
        )
    return output_dir


def assemble_section(package_dir: Path, draft_path: Path, output_dir: Path) -> Path:
    """Resolve declared references without synthesizing or approving the draft prose."""
    package_dir, draft_path, output_dir = map(Path, (package_dir, draft_path, output_dir))
    _fresh(output_dir)
    data = _load_input(package_dir / "input.json")
    draft = _Draft.model_validate(_read(draft_path))
    evidence = {e.id: e for e in data.evidence}
    figures = {f.id for f in data.figures}
    if set(draft.captions) != figures or set(draft.image_observations) != figures:
        raise ValueError("Every figure requires a caption and image observation status")
    _references(draft.observation_notes, figures)
    if any(not text.strip() for text in draft.observation_notes.values()):
        raise ValueError("Observation notes must not be blank")
    used_evidence, used_figures, citations = set(), set(), []
    reports = _calculate_sources(data, package_dir, write=False)
    resolved_values = {}
    table_ids = [t.table_id for t in draft.tables]
    equation_ids = [e.equation_id for e in draft.equations]
    for ids in (table_ids, equation_ids):
        if len(ids) != len(set(ids)) or any(not re.fullmatch(r"[A-Za-z0-9_.-]+", i) for i in ids):
            raise ValueError("Table and equation IDs must be unique simple identifiers")

    def resolve(text, declared_evidence, declared_figures):
        def replace(match):
            kind, identifier = match.group(1), match.group(2)
            if kind in {"table", "equation"}:
                _references([identifier], table_ids if kind == "table" else equation_ids)
                return f"{kind.title()} {identifier}"
            if kind == "figure":
                _references([identifier], declared_figures)
                return f"Figure {identifier}"
            _references([identifier], declared_evidence)
            record = evidence[identifier]
            if kind == "value":
                if record.result_ref is not None:
                    from cfdpaper.publication.table_evidence import resolve_table_result

                    try:
                        resolved = resolve_table_result(reports, **record.result_ref.model_dump())
                    except ValueError as exc:
                        raise ValueError(f"Evidence {identifier}: {exc}") from exc
                    resolved_values[identifier] = resolved
                    return resolved["value"] + (f" {resolved['unit']}" if resolved["unit"] else "")
                if record.value is None or not record.value.strip():
                    raise ValueError(f"Missing value for {identifier}")
                return record.value + (f" {record.unit}" if record.unit else "")
            if record.kind != "literature":
                raise ValueError(f"Citation {identifier} must be literature evidence")
            if identifier not in citations:
                citations.append(identifier)
            return f"[{citations.index(identifier) + 1}]"

        resolved = re.sub(
            r"\{\{(value|figure|cite|table|equation):([A-Za-z0-9_.-]+)\}\}", replace, text
        )
        if "{{" in resolved or "}}" in resolved:
            raise ValueError("Unknown or malformed draft token")
        return resolved

    paragraphs = []
    for paragraph in draft.paragraphs:
        _references(paragraph.evidence_ids, evidence)
        _references(paragraph.figure_ids, figures)
        used_evidence.update(paragraph.evidence_ids)
        used_figures.update(paragraph.figure_ids)
        runs = []
        cursor = 0
        for match in re.finditer(r"\{\{math:([A-Za-z0-9_.-]+)\}\}", paragraph.text):
            runs.append(
                {
                    "text": resolve(
                        paragraph.text[cursor : match.start()],
                        paragraph.evidence_ids,
                        paragraph.figure_ids,
                    )
                }
            )
            identifier = match.group(1)
            _references([identifier], paragraph.inline_math)
            expression = paragraph.inline_math[identifier].model_dump()

            def resolve_inline(node, allowed=paragraph.evidence_ids, images=paragraph.figure_ids):
                if node["text"] is not None:
                    node["text"] = resolve(node["text"], allowed, images)
                for child in node["children"]:
                    resolve_inline(child, allowed, images)

            resolve_inline(expression)
            runs.append({"math": expression})
            cursor = match.end()
        runs.append(
            {"text": resolve(paragraph.text[cursor:], paragraph.evidence_ids, paragraph.figure_ids)}
        )
        text = "".join(
            run["text"] if "text" in run else math_text(MathNode.model_validate(run["math"]))
            for run in runs
        )
        paragraphs.append({**paragraph.model_dump(), "text": text, "runs": runs})
    for duty in data.duties:
        if not set(duty.evidence_ids) <= used_evidence or not set(duty.figure_ids) <= used_figures:
            raise ValueError(f"Missing paragraph coverage for duty: {duty.purpose}")
    captions = {key: resolve(value, evidence, figures) for key, value in draft.captions.items()}
    tables = []
    for table in draft.tables:
        if table.after_section_id != data.section_id:
            raise ValueError(f"Table {table.table_id} targets a different section")
        _references(table.evidence_ids, evidence)
        content = table.model_dump()
        content["caption"] = resolve(table.caption, table.evidence_ids, figures)
        content["note"] = resolve(table.note, table.evidence_ids, figures)
        content["columns"] = [resolve(c, table.evidence_ids, figures) for c in table.columns]
        content["rows"] = [
            [resolve(c, table.evidence_ids, figures) for c in row] for row in table.rows
        ]
        tables.append(content)
    equations = []
    for equation in draft.equations:
        _references(equation.evidence_ids, evidence)
        content = equation.model_dump()

        def resolve_node(node, allowed=equation.evidence_ids):
            if node["text"] is not None:
                node["text"] = resolve(node["text"], allowed, figures)
            for child in node["children"]:
                resolve_node(child, allowed)

        resolve_node(content["expression"])
        equations.append(content)
    references = [{"number": n, **evidence[key].model_dump()} for n, key in enumerate(citations, 1)]
    with _stage(output_dir) as staged:
        _copy_figures(data, package_dir, staged)
        _copy_sources(data, package_dir, staged)
        if reports:
            _write(staged / "table-results.json", reports)
        result = {
            "section_id": data.section_id,
            "title": draft.title,
            "paragraphs": paragraphs,
            "figures": [{**f.model_dump(), "caption": captions[f.id]} for f in data.figures],
            "evidence": [e.model_dump() for e in data.evidence],
            "resolved_values": resolved_values,
            "style": data.style.model_dump(),
            "tables": tables,
            "equations": equations,
            "references": references,
            "image_observations": draft.image_observations,
            "observation_notes": draft.observation_notes,
        }
        _write(staged / "section.json", result)
        lines = [f"## {draft.title}", *[p["text"] for p in paragraphs]]
        for equation in equations:
            model = SectionEquation.model_validate(equation)
            lines.append(f"{math_text(model.expression)}   ({model.equation_id})")
        for table in tables:
            from cfdpaper.publication.export import _markdown_table

            lines.append(_markdown_table(SectionTable.model_validate(table)))
            if table["note"]:
                lines.append(table["note"])
        for figure in result["figures"]:
            lines.extend(
                [
                    f"![Figure {figure['id']}]({figure['path']})",
                    f"Figure {figure['id']}. {figure['caption']}",
                ]
            )
        if references:
            lines.extend(
                [
                    "### References",
                    *[f"[{r['number']}] {r['text']} — {r['source']}" for r in references],
                ]
            )
        (staged / "section.md").write_text("\n\n".join(lines) + "\n", encoding="utf-8")
        (staged / "evidence-notes.md").write_text(
            "# Evidence and review notes\n\n" + "\n\n".join(draft.evidence_notes) + "\n",
            encoding="utf-8",
        )
        prompt = (
            "Use the self-contained review-packet directory: review section.md against "
            "input.json, draft.json and figures within that directory. "
            "When supplied, read sources/ and table-results.json; distinguish computed "
            "identities from physical interpretations and check any quoted value "
            "against its source. "
            "Open the images; check coverage, units, normalization and physical inference. "
            'Return JSON {"suggestions": [{"target": "paragraph or figure", '
            '"comment": "finding", "recommendation": "suggested change"}]}. '
            "Suggestions are separate from author decisions; do not claim approval.\n"
        )
        (staged / "review-prompt.md").write_text(prompt, encoding="utf-8")
        packet = staged / "review-packet"
        packet.mkdir()
        _write(packet / "input.json", data.model_dump())
        _write(packet / "draft.json", draft.model_dump())
        shutil.copytree(staged / "figures", packet / "figures")
        _copy_sources(data, staged, packet)
        if (staged / "table-results.json").exists():
            shutil.copyfile(staged / "table-results.json", packet / "table-results.json")
        for name in ("section.md", "review-prompt.md", "evidence-notes.md"):
            shutil.copyfile(staged / name, packet / name)
    return output_dir


def export_section_docx(section_dir: Path, output_path: Path, *, layout="after-text") -> Path:
    """Export editable manuscript text with proportionally bounded embedded images."""
    section_dir, output_path = Path(section_dir), Path(output_path)
    _fresh(output_path)
    if output_path.suffix.lower() != ".docx":
        raise ValueError("DOCX output path must end in .docx")
    if layout not in {"after-text", "near-reference"}:
        raise ValueError("Layout must be after-text or near-reference")
    try:
        from docx import Document
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml.ns import qn
        from docx.shared import Mm, Pt, RGBColor
    except ImportError as exc:
        raise RuntimeError(
            "DOCX export requires python-docx; install cfd-paper-agent[docs]"
        ) from exc
    data = _read(section_dir / "section.json")
    config = PublicationStyle.model_validate(data.get("style", {}))
    report_path = output_path.with_suffix(".layout.json")
    _fresh(report_path)
    document = Document()
    for name, size in (
        ("Normal", config.body_pt),
        ("Title", config.title_pt),
        ("Caption", config.caption_pt),
        ("Heading 2", config.heading_pt),
    ):
        style = document.styles[name]
        style.font.name = config.font_family
        style.font.size = Pt(size)
        style.font.color.rgb = RGBColor(0, 0, 0)
        fonts = style.element.get_or_add_rPr().get_or_add_rFonts()
        for attribute in list(fonts.attrib):
            if "theme" in attribute.lower():
                del fonts.attrib[attribute]
        fonts.set(qn("w:eastAsia"), config.font_family)
        for border in style.element.xpath("./w:pPr/w:pBdr"):
            border.getparent().remove(border)
        style.paragraph_format.widow_control = True
    document.styles["Caption"].font.bold = False
    document.styles["Caption"].font.italic = False
    document.styles["Caption"].paragraph_format.keep_together = True
    document.styles["Normal"].paragraph_format.line_spacing = config.line_spacing
    document.styles["Normal"].paragraph_format.space_after = Pt(config.space_after_pt)
    document.styles["Caption"].paragraph_format.line_spacing = 1.2
    document.styles["Caption"].paragraph_format.space_after = Pt(config.space_after_pt)
    page = document.sections[0]
    page.page_width, page.page_height = Mm(config.page_width_mm), Mm(config.page_height_mm)
    page.left_margin = page.right_margin = Mm(config.margin_mm)
    page.top_margin = page.bottom_margin = Mm(config.margin_mm)
    document.add_paragraph(data["title"], style="Title")
    placements = []

    def add_figure(figure):
        path = section_dir / figure["path"]
        caption = f"Figure {figure['id']}. {figure['caption']}"
        with Image.open(path) as picture:
            try:
                placement = figure_placement(
                    pixels=picture.size,
                    caption=caption,
                    sizing=FigureSizing.model_validate(figure.get("sizing", {})),
                    style=config,
                )
            except ValueError as exc:
                raise ValueError(f"Figure {figure['id']}: {exc}") from exc
        placements.append({"id": figure["id"], **placement})
        document.add_picture(
            str(path), width=Mm(placement["width_mm"]), height=Mm(placement["height_mm"])
        )
        document.paragraphs[-1].paragraph_format.keep_with_next = True
        document.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        if layout == "after-text":
            document.paragraphs[-1].paragraph_format.page_break_before = True
        document.add_paragraph(caption, style="Caption")

    placed = set()
    for paragraph in data["paragraphs"]:
        p = document.add_paragraph()
        for run in paragraph.get("runs", [{"text": paragraph["text"]}]):
            if "text" in run:
                p.add_run(run["text"])
            else:
                from docx.oxml import OxmlElement

                from cfdpaper.publication.elements import math_xml

                formula = OxmlElement("m:oMath")
                formula.extend(math_xml(MathNode.model_validate(run["math"])))
                p._p.append(formula)
        p.paragraph_format.keep_together = False
        p.paragraph_format.widow_control = True
        if layout == "near-reference":
            for figure in data["figures"]:
                if figure["id"] in paragraph["figure_ids"] and figure["id"] not in placed:
                    add_figure(figure)
                    placed.add(figure["id"])
    from cfdpaper.publication.elements import add_equation, add_table

    for equation in data.get("equations", []):
        add_equation(document, SectionEquation.model_validate(equation))
    for table in data.get("tables", []):
        add_table(document, SectionTable.model_validate(table), config)
    for figure in data["figures"]:
        if figure["id"] not in placed:
            add_figure(figure)
    if data["references"]:
        document.add_heading("References", level=2)
        for record in data["references"]:
            p = document.add_paragraph(
                f"[{record['number']}] {record['text']} — {record['source']}"
            )
            for run in p.runs:
                run.font.size = Pt(config.reference_pt)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".section-", dir=output_path.parent) as temp:
        staged = Path(temp) / "section.docx"
        document.save(staged)
        staged_report = Path(temp) / "layout.json"
        _write(
            staged_report, {"layout": layout, "style": config.model_dump(), "figures": placements}
        )
        _fresh(output_path)
        _fresh(report_path)
        staged.rename(output_path)
        staged_report.rename(report_path)
    return output_path


def import_section_review(section_dir: Path, review_path: Path, output_path: Path) -> Path:
    """Store reviewer suggestions separately; never revise or approve the manuscript."""
    section_dir, review_path, output_path = map(Path, (section_dir, review_path, output_path))
    _fresh(output_path)
    _read(section_dir / "section.json")
    review = _read(review_path)
    if not isinstance(review, dict) or set(review) != {"suggestions"}:
        raise ValueError("Review must contain only a suggestions array")
    if not isinstance(review["suggestions"], list):
        raise ValueError("suggestions must be an array")
    for suggestion in review["suggestions"]:
        if (
            not isinstance(suggestion, dict)
            or set(suggestion) != {"target", "comment", "recommendation"}
            or any(not isinstance(v, str) or not v.strip() for v in suggestion.values())
        ):
            raise ValueError("Each suggestion requires target, comment and recommendation strings")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", encoding="utf-8") as stream:
        json.dump(review, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return output_path
