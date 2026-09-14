"""Portable host-assisted analysis choices backed by existing table calculations.

The host and author establish scientific meaning; this module checks executable
mappings and source locations, not whether a method passage proves the proposal.
"""

from __future__ import annotations

import csv
import json
import re
import shutil
from pathlib import Path
from typing import Literal

from pydantic import Field, StrictStr, model_validator

from cfdpaper.adapters.csv import CSVAdapter, _split_header
from cfdpaper.publication.section import (
    _Evidence,
    _Figure,
    _Record,
    _ResultRef,
    _stage,
    _TableCalculation,
    _write,
)
from cfdpaper.publication.style import PublicationStyle
from cfdpaper.publication.table_evidence import calculate_table, resolve_table_result


class _Definition(_Record):
    path: str
    locator: str = Field(pattern=r"^L[1-9]\d*(?:-L?[1-9]\d*)?$")


class _Comparison(_Record):
    status: Literal["supported", "unknown", "not-comparable"]
    scope: str


class _Calculation(_Record):
    # Proposal comparison is a scientific qualification, not a paired-row selector.
    id: str = Field(pattern=r"^[A-Za-z0-9_.-]+$")
    source: str
    operation: Literal["population", "partition"]
    columns: dict[str, StrictStr]
    units: dict[str, StrictStr]
    domain: str
    group_by: str | None = None
    definition_source: _Definition
    comparison: _Comparison
    member_id: list[StrictStr] = Field(min_length=1)
    expected_members: list[list[StrictStr]] | None = None
    expected_groups: list[StrictStr] | None = None
    interpretation_limits: list[StrictStr] = Field(min_length=1)
    missing_questions: list[StrictStr] = Field(default_factory=list)

    def table_calculation(self) -> _TableCalculation:
        return _TableCalculation.model_validate(
            self.model_dump(include=set(_TableCalculation.model_fields) - {"comparison"})
        )

    @model_validator(mode="after")
    def explicit_definition(self):
        self.table_calculation()
        return self


class _Metric(_Record):
    id: str = Field(pattern=r"^[A-Za-z0-9_.-]+$")
    text: str
    result_ref: _ResultRef


class _FigurePlan(_Record):
    metric_ids: list[StrictStr] = Field(min_length=1)
    title: str
    y_label: str
    x_label: str = "Group"
    category_labels: dict[str, StrictStr] = Field(default_factory=dict)


class _Candidate(_Record):
    id: str = Field(pattern=r"^[A-Za-z0-9_.-]+$")
    question: str
    rationale: str
    title: str | None = None
    presentation: Literal["plot", "prose", "table", "custom"] = "plot"
    presentation_reason: str | None = None
    style: PublicationStyle = Field(default_factory=PublicationStyle)
    calculations: list[_Calculation] = Field(min_length=1)
    metrics: list[_Metric] = Field(default_factory=list)
    figures: list[_Figure] = Field(default_factory=list)
    supporting_evidence: list[_Evidence] = Field(default_factory=list)
    figure_plan: _FigurePlan | None = None
    interpretation_limits: list[StrictStr] = Field(min_length=1)
    missing_questions: list[StrictStr] = Field(default_factory=list)


HOST_PROMPT = """# Propose a small, useful scientific analysis

Read skills/cfd-qoi-physics/SKILL.md and skills/cfd-figure-production/SKILL.md
for analysis and visual-evidence selection; their legacy CLI applies only to that route.
Read materials.json and the actual method/definition files under sources/. The
summary is a reading aid, not physical semantics. Read the full source when its
excerpt is truncated. Actually view relevant images if your host can; otherwise
say they were not viewed. Do not claim quantitative image measurements from sight.

Write proposal.json using proposal-example.json and proposal-schema.json. Propose
1–3 grounded analysis candidates, or zero plus specific minimum gaps if none is
supported. Recommend one by physical value, not by how many statistics can be
computed. Respect the author's question when supplied. The author chooses a
candidate ID or answers only material ambiguities; do not ask them to hand-write
JSON. This is subsection analysis, not a replacement manuscript-topic approval.

For every proposed calculation map the exact raw CSV headers, explicit units,
statistical/spatial domain, group column and member identity columns. Cite a real
method passage with definition_source {path, locator: "L2-L5"}. Explain comparison
scope and status (supported, unknown, not-comparable). Names, headers, existence of
a locator and your own prose do NOT prove domain, weighting, comparability or
causality. Inspect boundary conditions and definition consistency in the supplied
methods before calling a comparison supported. Unknown or not-comparable selected
calculations cannot run. Keep independent supported candidates available.

Only population (equal-record count/sum/mean/population CV, ddof=0) and partition
(sum of area and already-integrated rate, mean_flux=rate/area, regional flux and
shares) are executable. No inferred integrals, unit conversion, excluded rows,
solver execution or arbitrary code. A partition requires method-backed disjoint
regions and a stated coverage; a supplied subset is not silently the full domain.
List expected_members/expected_groups when the method declares the full set so
missing records can be detected. Units must be explicit; use "1" for dimensionless.

Separate existing observations, calculable relationships, and interpretations
requiring extra evidence. An identity/decomposition is not causal proof. Do not
treat a larger metric as universally better, local species as global performance,
nonuniform sampled-section sums as conserved fractions, or discrete cases as a
continuous optimum or stability boundary. Keep these limits specific and useful.

Prefer a few explicit metrics with result_ref for the selected question. Omitting
metrics generates scalar anchors for available groups; these are a selection pool,
not instructions to quote every number. Optional figure_plan is {metric_ids,
title,y_label}; avoid mixing unlike quantities on one axis. It defines the figure's
role, not fabricated observations. Do not generate publication claims by template.
Optional x_label and category_labels (metric ID to nonblank physical category name)
provide publication-ready labels rather than internal CSV record identifiers.
These labels change display only, not the metric's numerical mapping or provenance.
Choose presentation explicitly: plot for the implemented discrete comparison renderer,
prose for a concise numerical contrast, table for a small native table in the host draft,
or custom when the scientific relationship needs a figure beyond the current renderer.
State presentation_reason: what the reader needs to see and why this form is useful.
The code does not automatically implement a custom design or write the table/prose.
Do not use a full-width plot solely because two values exist. Conversely do not impose
a minimum point count, add decorative panels, or discard a useful sparse comparison.
For opposing metric responses, decomposition or spatial redistribution, select the
complementary evidence needed to show that relationship; do not leave its decisive half
in prose merely because the default renderer is convenient. Keep unlike units on separate
axes/panels. An unsupported visual design should remain a specific figure task, not be
silently replaced by a different chart. Existing author-approved images are not redesigned.
Use the optional style object for explicit author/venue formatting. Body defaults use
body_first_line_indent_chars=2, body_space_before_pt=0, body_space_after_pt=0;
these are editable house defaults, not a universal journal requirement. Body settings
are separate from caption spacing and line_spacing. Do not insert spaces to indent text.
Preserve useful existing raster figures in optional figures using {id, path,
caption, description}, with path under sources/. Use optional supporting_evidence
for located observations, interpretations or literature, not manually supplied
metrics. Each item uses {id,text,source,kind}; source is a real sources/ image path
or a text source with a line locator such as sources/method.md:L2-L5. Existing
images and their descriptions complement computed metrics; they do not prove you
viewed an image or validate an interpretation. Numeric values must use result_ref.
Return proposals and minimum gaps; do not claim author approval or validation.
"""


def _source(root: Path, relative: str, *, packaged: bool) -> Path:
    path = Path(relative)
    if (
        not path.parts
        or path.is_absolute()
        or ".." in path.parts
        or (packaged and path.parts[0] != "sources")
    ):
        raise ValueError(f"Expected a relative {'sources/ ' if packaged else ''}path: {relative}")
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
        raise ValueError(f"Missing or external source: {relative}")
    return resolved


def prepare_analysis(root: Path, output_dir: Path, *, question: str = "") -> Path:
    """Copy profiled small sources and host instructions into a fresh portable package."""
    from cfdpaper.materials import profile_materials

    root, output_dir = Path(root).resolve(), Path(output_dir)
    materials = profile_materials(root)
    included = []
    with _stage(output_dir) as staged:
        for category in ("tables", "documents", "figures"):
            for item in materials.get(category, []):
                original = item if isinstance(item, str) else item["path"]
                source = _source(root, original, packaged=False)
                if source.stat().st_size > 20 * 1024 * 1024:
                    materials.setdefault("issues", []).append(
                        {"path": original, "message": "Not copied: exceeds 20 MiB package limit"}
                    )
                    continue
                relative = (Path("sources") / original).as_posix()
                destination = staged / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
                included.append(relative)
                if isinstance(item, dict):
                    item["package_path"] = relative
        materials["question"] = question
        materials["source_files"] = included
        _write(staged / "materials.json", materials)
        (staged / "host-task.md").write_text(HOST_PROMPT, encoding="utf-8")
        for name in ("cfd-qoi-physics", "cfd-figure-production"):
            # Wheels include these skills; source checkouts keep them at repository root.
            skill = Path(__file__).parent / "skills" / name / "SKILL.md"
            if not skill.is_file():
                skill = Path(__file__).resolve().parents[2] / "skills" / name / "SKILL.md"
            destination = staged / "skills" / name / "SKILL.md"
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(skill, destination)
        _write(staged / "proposal-example.json", _example())
        schema = {
            "type": "object",
            "required": ["candidates"],
            "properties": {
                "candidates": {
                    "type": "array",
                    "maxItems": 3,
                    "items": _Candidate.model_json_schema(),
                },
                "recommended_id": {"type": ["string", "null"]},
                "gaps": {"type": "array", "items": {"type": "string"}},
            },
        }
        # Nested Pydantic references resolve at the document root in JSON Schema.
        schema["$defs"] = schema["properties"]["candidates"]["items"].pop("$defs")
        _write(staged / "proposal-schema.json", schema)
    return output_dir / "materials.json"


def _example() -> dict:
    return {
        "candidates": [
            {
                "id": "regional-transport",
                "question": "How do integrated transport and mean flux differ across the cases?",
                "rationale": "Replace this example with analysis grounded in the supplied methods.",
                "calculations": [
                    {
                        "id": "transport",
                        "source": "sources/regions.csv",
                        "operation": "partition",
                        "columns": {"area": "area [m2]", "rate": "rate [W]"},
                        "units": {"area": "m2", "rate": "W"},
                        "domain": "Replace with the method-defined region set and coverage.",
                        "group_by": "case",
                        "member_id": ["region"],
                        "definition_source": {"path": "sources/method.md", "locator": "L1-L3"},
                        "comparison": {
                            "status": "unknown",
                            "scope": "Confirm the comparison basis.",
                        },
                        "interpretation_limits": [
                            "An algebraic decomposition is not causal proof."
                        ],
                        "missing_questions": ["Replace with concrete gaps, or [] when supported."],
                    }
                ],
                "metrics": [],
                "interpretation_limits": ["Use the declared sampled domain only."],
                "missing_questions": [],
            }
        ],
        "recommended_id": None,
        "gaps": [],
    }


def _check_calculation(package: Path, calc: _Calculation) -> dict:
    if calc.comparison.status != "supported":
        raise ValueError(f"{calc.id}: comparison is {calc.comparison.status}")
    if calc.missing_questions:
        raise ValueError(
            f"{calc.id}: resolve selected calculation questions: {calc.missing_questions}"
        )
    if any(not unit.strip() for unit in calc.units.values()):
        raise ValueError(f"{calc.id}: explicit units required (use '1' for dimensionless)")
    definition = _source(package, calc.definition_source.path, packaged=True)
    lines = definition.read_text(encoding="utf-8-sig").splitlines()
    bounds = [int(number) for number in re.findall(r"\d+", calc.definition_source.locator)]
    if bounds[0] > bounds[-1] or bounds[-1] > len(lines):
        raise ValueError(f"{calc.id}: definition locator is outside source lines")
    if not "\n".join(lines[bounds[0] - 1 : bounds[-1]]).strip():
        raise ValueError(f"{calc.id}: definition locator contains no text")
    source = _source(package, calc.source, packaged=True)
    CSVAdapter().inventory(source)  # Existing header and row-shape checks.
    with source.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        headers = reader.fieldnames or []
        required = set(calc.columns.values()) | set(calc.member_id)
        if calc.group_by:
            required.add(calc.group_by)
        if not required <= set(headers):
            raise ValueError(f"{calc.id}: missing columns {sorted(required - set(headers))}")
        if len(set(calc.member_id)) != len(calc.member_id) or any(
            not name.strip() for name in calc.member_id
        ):
            raise ValueError(f"{calc.id}: member_id columns must be unique and nonblank")
        for role, header in calc.columns.items():
            _, unit = _split_header(header)
            if unit is not None and unit != calc.units[role]:
                raise ValueError(f"{calc.id}: declared unit conflicts with header {header!r}")
        members: dict[str, set[tuple[str, ...]]] = {}
        for line, row in enumerate(reader, 2):
            identity = tuple((row[name] or "").strip() for name in calc.member_id)
            group = (row[calc.group_by] or "") if calc.group_by else "all"
            if not group.strip() or any(not value for value in identity):
                raise ValueError(f"{calc.id}: missing group/member identity at CSV record {line}")
            group_members = members.setdefault(group, set())
            if identity in group_members:
                raise ValueError(f"{calc.id}: duplicate member {identity} in group {group}")
            group_members.add(identity)
    if calc.expected_groups is not None and set(calc.expected_groups) != set(members):
        raise ValueError(f"{calc.id}: expected groups do not match observed groups")
    if calc.expected_members is not None:
        expected = {tuple(member) for member in calc.expected_members}
        if not expected or any(len(member) != len(calc.member_id) for member in expected):
            raise ValueError(f"{calc.id}: invalid expected member identities")
        if any(actual != expected for actual in members.values()):
            raise ValueError(f"{calc.id}: missing or unexpected members in declared groups")
    base = calc.table_calculation().model_dump()
    result = calculate_table(
        source, operation=calc.operation, columns=calc.columns, group_by=calc.group_by
    )
    if any(group["status"] != "computed" for group in result["groups"]):
        raise ValueError(f"{calc.id}: selected calculation has missing numeric values")
    return {**base, **result}


def compile_analysis(
    package_dir: Path, proposal_path: Path, candidate_id: str, output_dir: Path
) -> Path:
    """Validate the selected host proposal and emit inputs for section assembly.

    The returned analysis-input.json is an assembly payload, not yet a full section:
    the caller supplies actual figures and paragraph duties via the existing path.
    """
    package, output_dir = Path(package_dir).resolve(), Path(output_dir)
    proposal = json.loads(Path(proposal_path).read_text(encoding="utf-8"))
    candidates = proposal.get("candidates")
    if not isinstance(candidates, list) or len(candidates) > 3:
        raise ValueError("Proposal must contain zero to three candidates")
    ids = [candidate.get("id") for candidate in candidates if isinstance(candidate, dict)]
    if (
        len(ids) != len(candidates)
        or any(not isinstance(value, str) or not value.strip() for value in ids)
        or len(ids) != len(set(ids))
    ):
        raise ValueError("Candidate IDs must be unique")
    if candidate_id not in ids:
        raise ValueError(
            f"Candidate {candidate_id!r} is unavailable; gaps: {proposal.get('gaps', [])}"
        )
    chosen = _Candidate.model_validate(candidates[ids.index(candidate_id)])
    if chosen.missing_questions:
        raise ValueError(f"Resolve selected candidate questions: {chosen.missing_questions}")
    calc_ids = [calc.id for calc in chosen.calculations]
    if len(calc_ids) != len(set(calc_ids)):
        raise ValueError("Calculation IDs must be unique")
    reports = [_check_calculation(package, calc) for calc in chosen.calculations]
    metrics = chosen.metrics or _automatic_metrics(reports)
    if len({metric.id for metric in metrics}) != len(metrics):
        raise ValueError("Metric IDs must be unique")
    evidence = []
    for metric in metrics:
        resolved = resolve_table_result(reports, **metric.result_ref.model_dump())
        evidence.append(
            _Evidence(
                id=metric.id,
                text=metric.text,
                source=resolved["source"],
                kind="metric",
                result_ref=metric.result_ref,
            ).model_dump(exclude_none=True)
        )
    if chosen.figure_plan and not set(chosen.figure_plan.metric_ids) <= {m.id for m in metrics}:
        raise ValueError("Figure plan references unknown metric IDs")
    if chosen.figure_plan:
        labels = chosen.figure_plan.category_labels
        if not set(labels) <= {m.id for m in metrics}:
            raise ValueError("Figure category labels reference unknown metric IDs")
        if any(not label.strip() for label in labels.values()):
            raise ValueError("Figure category labels must not be blank")
    figure_ids = [figure.id.casefold() for figure in chosen.figures]
    if len(figure_ids) != len(set(figure_ids)):
        raise ValueError("Figure IDs must be unique on case-insensitive filesystems")
    supporting_sources = set()
    for figure in chosen.figures:
        if Path(figure.path).suffix.lower() not in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
            raise ValueError("Existing section figures must use raster image paths")
        supporting_sources.add(_check_supporting_source(package, figure.path))
    for item in chosen.supporting_evidence:
        if item.kind == "metric" or item.value is not None or item.result_ref is not None:
            raise ValueError("Supporting evidence cannot supply metrics; use metrics/result_ref")
        supporting_sources.add(_check_supporting_source(package, item.source))
        evidence.append(item.model_dump(exclude_none=True))
    if len({item["id"] for item in evidence}) != len(evidence):
        raise ValueError("Evidence IDs must be unique across metrics and supporting evidence")
    sources = sorted(
        {
            path
            for calc in chosen.calculations
            for path in (calc.source, calc.definition_source.path)
        }
        | supporting_sources
    )
    payload = {
        "section_id": chosen.id,
        "title": chosen.title or chosen.question,
        "question": chosen.question,
        "context": "\n".join(
            [
                chosen.rationale,
                *chosen.interpretation_limits,
                *(
                    f"{calc.id}: {calc.comparison.scope}; definition "
                    f"{calc.definition_source.path}:{calc.definition_source.locator}; "
                    + "; ".join(calc.interpretation_limits)
                    for calc in chosen.calculations
                ),
            ]
        ),
        "source_files": sources,
        "table_calculations": [
            calc.table_calculation().model_dump() for calc in chosen.calculations
        ],
        "evidence": evidence,
        "figures": [figure.model_dump() for figure in chosen.figures],
        "presentation": chosen.presentation,
        "presentation_reason": chosen.presentation_reason,
        "style": chosen.style.model_dump(),
        "figure_plan": chosen.figure_plan.model_dump() if chosen.figure_plan else None,
    }
    with _stage(output_dir) as staged:
        for name in sources:
            destination = staged / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(_source(package, name, packaged=True), destination)
        _write(staged / "analysis-input.json", payload)
        _write(staged / "table-results.json", reports)
        _write(staged / "selected-analysis.json", chosen.model_dump())
    return output_dir / "analysis-input.json"


def _check_supporting_source(package: Path, source: str) -> str:
    """Check that a locator is readable; do not certify the associated prose."""
    from PIL import Image

    match = re.fullmatch(r"(.+):(L[1-9]\d*(?:-L?[1-9]\d*)?)", source)
    if match:
        name, locator = match.groups()
        path = _source(package, name, packaged=True)
        lines = path.read_text(encoding="utf-8-sig").splitlines()
        bounds = [int(number) for number in re.findall(r"\d+", locator)]
        if bounds[0] > bounds[-1] or bounds[-1] > len(lines):
            raise ValueError(f"Supporting evidence locator is outside source lines: {source}")
        if not "\n".join(lines[bounds[0] - 1 : bounds[-1]]).strip():
            raise ValueError(f"Supporting evidence locator contains no text: {source}")
        return name
    path = _source(package, source, packaged=True)
    if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
        raise ValueError("Supporting text evidence requires a source line locator")
    with Image.open(path) as image:
        image.verify()
    return source


def _automatic_metrics(reports: list[dict]) -> list[_Metric]:
    metrics = []
    for report in reports:
        fields = (
            ("mean", "cv") if report["operation"] == "population" else ("area", "rate", "mean_flux")
        )
        for number, group in enumerate(report["groups"], 1):
            for field in fields:
                if group["result"].get(field) is None:
                    continue  # Undefined CV for zero mean remains unavailable, not zero.
                metrics.append(
                    _Metric(
                        id=f"{report['id']}-{number}-{field}",
                        text=f"{field} for {group['group']}; domain: {report['domain']}",
                        result_ref=_ResultRef(
                            calculation_id=report["id"],
                            group=group["group"],
                            field=field,
                        ),
                    )
                )
    return metrics
