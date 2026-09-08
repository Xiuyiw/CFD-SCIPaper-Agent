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


class _Evidence(_Record):
    id: str = Field(pattern=r"^[A-Za-z0-9_.-]+$")
    text: str = Field(min_length=1)
    source: str = Field(min_length=1)
    kind: Literal["observation", "metric", "interpretation", "literature"]
    value: StrictStr | None = None
    unit: StrictStr = ""

    @model_validator(mode="after")
    def finite_metric(self):
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


class _Input(_Record):
    section_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    question: str = Field(min_length=1)
    figures: list[_Figure] = Field(min_length=1)
    evidence: list[_Evidence] = Field(min_length=1)
    duties: list[_Duty] = Field(min_length=1)
    context: str = ""


class _Paragraph(_Record):
    text: str = Field(min_length=1)
    evidence_ids: list[str]
    figure_ids: list[str]


class _Draft(_Record):
    title: str = Field(min_length=1)
    paragraphs: list[_Paragraph] = Field(min_length=1)
    captions: dict[str, str]
    evidence_notes: list[StrictStr]
    image_observations: dict[str, Literal["viewed", "author-provided", "not-viewed"]]

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
the package has not independently verified the source or the physics. Source data files are
not copied: only the declared structured evidence records and figure assets are included.
Check units, boundary conditions, comparison basis and numerical limitations. A sum of
cell-integrated heat rates is not a sum of per-volume heat-release rates: the latter requires
cell-volume weighting. Keep all compared quantities on a consistent control-volume basis.

Token syntax inside paragraph text and captions:
- {{value:evidence_id}} inserts the exact supplied value string plus a space and unit, if any.
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
    used_evidence, used_figures, citations = set(), set(), []

    def resolve(text, declared_evidence, declared_figures):
        def replace(match):
            kind, identifier = match.group(1), match.group(2)
            if kind == "figure":
                _references([identifier], declared_figures)
                return f"Figure {identifier}"
            _references([identifier], declared_evidence)
            record = evidence[identifier]
            if kind == "value":
                if record.value is None or not record.value.strip():
                    raise ValueError(f"Missing value for {identifier}")
                return record.value + (f" {record.unit}" if record.unit else "")
            if record.kind != "literature":
                raise ValueError(f"Citation {identifier} must be literature evidence")
            if identifier not in citations:
                citations.append(identifier)
            return f"[{citations.index(identifier) + 1}]"

        resolved = re.sub(r"\{\{(value|figure|cite):([A-Za-z0-9_.-]+)\}\}", replace, text)
        if "{{" in resolved or "}}" in resolved:
            raise ValueError("Unknown or malformed draft token")
        return resolved

    paragraphs = []
    for paragraph in draft.paragraphs:
        _references(paragraph.evidence_ids, evidence)
        _references(paragraph.figure_ids, figures)
        used_evidence.update(paragraph.evidence_ids)
        used_figures.update(paragraph.figure_ids)
        paragraphs.append(
            {
                **paragraph.model_dump(),
                "text": resolve(paragraph.text, paragraph.evidence_ids, paragraph.figure_ids),
            }
        )
    for duty in data.duties:
        if not set(duty.evidence_ids) <= used_evidence or not set(duty.figure_ids) <= used_figures:
            raise ValueError(f"Missing paragraph coverage for duty: {duty.purpose}")
    captions = {key: resolve(value, evidence, figures) for key, value in draft.captions.items()}
    references = [{"number": n, **evidence[key].model_dump()} for n, key in enumerate(citations, 1)]
    with _stage(output_dir) as staged:
        _copy_figures(data, package_dir, staged)
        result = {
            "section_id": data.section_id,
            "title": draft.title,
            "paragraphs": paragraphs,
            "figures": [{**f.model_dump(), "caption": captions[f.id]} for f in data.figures],
            "evidence": [e.model_dump() for e in data.evidence],
            "references": references,
            "image_observations": draft.image_observations,
        }
        _write(staged / "section.json", result)
        lines = [f"## {draft.title}", *[p["text"] for p in paragraphs]]
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
        for name in ("section.md", "review-prompt.md", "evidence-notes.md"):
            shutil.copyfile(staged / name, packet / name)
    return output_dir


def export_section_docx(section_dir: Path, output_path: Path) -> Path:
    """Export editable manuscript text with proportionally bounded embedded images."""
    section_dir, output_path = Path(section_dir), Path(output_path)
    _fresh(output_path)
    if output_path.suffix.lower() != ".docx":
        raise ValueError("DOCX output path must end in .docx")
    try:
        from docx import Document
        from docx.shared import Pt, RGBColor
    except ImportError as exc:
        raise RuntimeError(
            "DOCX export requires python-docx; install cfd-paper-agent[docs]"
        ) from exc
    data = _read(section_dir / "section.json")
    document = Document()
    document.styles["Normal"].font.name = "Times New Roman"
    document.styles["Normal"].font.size = Pt(11)
    document.styles["Title"].font.color.rgb = RGBColor(0, 0, 0)
    document.styles["Title"].font.name = "Times New Roman"
    document.styles["Caption"].font.color.rgb = RGBColor(0, 0, 0)
    document.styles["Caption"].font.name = "Times New Roman"
    document.styles["Caption"].font.size = Pt(10)
    document.add_paragraph(data["title"], style="Title")
    for paragraph in data["paragraphs"]:
        document.add_paragraph(paragraph["text"])
    page = document.sections[0]
    width = page.page_width - page.left_margin - page.right_margin
    height = (page.page_height - page.top_margin - page.bottom_margin) * 0.7
    for figure in data["figures"]:
        path = section_dir / figure["path"]
        with Image.open(path) as picture:
            ratio = picture.height / picture.width
        actual_width = min(width, height / ratio)
        document.add_picture(str(path), width=int(actual_width), height=int(actual_width * ratio))
        document.paragraphs[-1].paragraph_format.keep_with_next = True
        document.add_paragraph(f"Figure {figure['id']}. {figure['caption']}", style="Caption")
    if data["references"]:
        document.add_heading("References", level=2)
        for record in data["references"]:
            document.add_paragraph(f"[{record['number']}] {record['text']} — {record['source']}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".section-", dir=output_path.parent) as temp:
        staged = Path(temp) / "section.docx"
        document.save(staged)
        _fresh(output_path)
        staged.rename(output_path)
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
