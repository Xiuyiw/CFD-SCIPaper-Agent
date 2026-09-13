"""Portable multi-section writing, using the existing section evidence pipeline.

Spine order is publication order. Local object IDs remain in each section;
``numbering.json`` maps them to manuscript labels. Only supported draft tokens
are rebound: a literal ``Figure 1`` or ``[1]`` in author prose is never rewritten.
"""

from __future__ import annotations

import copy
import json
import re
import shutil
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from cfdpaper.publication.elements import SectionEquation, SectionTable, math_text
from cfdpaper.publication.section import (
    _Draft,
    _fresh,
    _load_input,
    _read,
    _stage,
    _write,
    assemble_section,
    prepare_section,
)
from cfdpaper.publication.spine import PaperSpine


class _SectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    section_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    input: str


class _ManuscriptInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1)
    spine: PaperSpine
    sections: list[_SectionInput] = Field(min_length=1)
    context: str = ""
    terms: dict[str, str] = Field(default_factory=dict)


def _relative(base: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise ValueError("Input and draft paths must be relative without parent traversal")
    return base / path


def _inputs(path: Path):
    data = _ManuscriptInput.model_validate(_read(path))
    if not data.title.strip():
        raise ValueError("Manuscript title must not be blank")
    ids = [item.section_id for item in data.sections]
    if len(ids) != len(set(item.casefold() for item in ids)):
        raise ValueError("Section IDs must be unique on case-insensitive filesystems")
    if set(ids) != {item.section_id for item in data.spine.sections}:
        raise ValueError("Section inputs must exactly match the spine sections")
    entries = {item.section_id: item for item in data.sections}
    loaded = {}
    for contract in data.spine.sections:
        source = _relative(path.parent, entries[contract.section_id].input)
        section = _load_input(source)
        if section.section_id != contract.section_id:
            raise ValueError(f"Section input identity mismatch: {contract.section_id}")
        if not set(contract.required_claim_ids) <= {e.id for e in section.evidence}:
            raise ValueError(f"Required claims must belong to section {contract.section_id}")
        if not set(contract.required_figure_ids) <= {f.id for f in section.figures}:
            raise ValueError(f"Required figures must belong to section {contract.section_id}")
        loaded[contract.section_id] = (source, section)
    central = data.spine.central_claim_id
    if not any(central in item.required_claim_ids for item in data.spine.sections):
        raise ValueError(f"Central claim must be assigned to a section: {central}")
    return data, loaded


def prepare_manuscript(input_path: Path, output_dir: Path) -> Path:
    """Prepare one portable host task per spine section; never overwrite output.

    Input: title, an existing PaperSpine, sections [{section_id, input}], and
    optional shared context/terms. All paths are relative to the input JSON.
    """
    input_path, output_dir = Path(input_path), Path(output_dir)
    _fresh(output_dir)
    data, loaded = _inputs(input_path)
    with _stage(output_dir) as staged:
        entries = []
        for contract in data.spine.sections:
            sid = contract.section_id
            source, _ = loaded[sid]
            package = prepare_section(source, staged / "sections" / sid)
            shutil.copyfile(source, package / "author-input.json")
            section = _read(package / "input.json")
            # Make spine duties enforceable by the existing assembly coverage check.
            if contract.required_claim_ids:
                section["duties"].append(
                    {
                        "purpose": contract.purpose,
                        "evidence_ids": contract.required_claim_ids,
                        "figure_ids": contract.required_figure_ids,
                    }
                )
            _write(package / "input.json", section)
            route = (
                "Read skills/cfd-evidence-writing/references/methods-sections.md before "
                "drafting this Methods section. Its method-specific route takes precedence "
                "over the generic mechanism-subsection narrative.\n"
                if contract.role == "methods"
                else ""
            )
            shared = {
                "title": data.title,
                "context": data.context,
                "terms": data.terms,
                "spine": data.spine.model_dump(),
                "section": contract.model_dump(),
            }
            _write(package / "manuscript-context.json", shared)
            task = package / "TASK.md"
            task.write_text(
                f"# Manuscript section: {contract.title}\n\n"
                f"Role: {contract.role}\n\nPurpose: {contract.purpose}\n\n"
                "Read manuscript-context.json for the central question, shared terminology, "
                "all section responsibilities and this section's prohibited content. "
                "Develop this section's assigned argument without duplicating other sections.\n"
                + route
                + "\n"
                + task.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            entries.append({"section_id": sid, "input": f"sections/{sid}/input.json"})
        manifest = {**data.model_dump(), "sections": entries}
        _write(staged / "manuscript-input.json", manifest)
        shutil.copyfile(input_path, staged / "author-input.json")
        _write(
            staged / "drafts-template.json",
            {
                item.section_id: f"sections/{item.section_id}/draft.json"
                for item in data.spine.sections
            },
        )
        (staged / "TASK.md").write_text(
            "# Prepare the manuscript with the host AI\n\n"
            "Read manuscript-input.json and follow the PaperSpine order. Read every section's "
            "TASK.md, packaged Skill and manuscript-context.json before drafting. Produce "
            "one fresh draft JSON for each section; use drafts-template.json to list the "
            "draft paths relative to that mapping file. Do not invent missing evidence. "
            "Keep source and author edits unchanged; assemble into a new output directory. "
            "Use supported figure/table/equation/cite tokens for automatic global numbering. "
            "For an object in another section use {{equation:section_id/local_id}}, "
            "{{table:section_id/local_id}} or {{figure:section_id/local_id}}; "
            "unqualified IDs refer to the current section. "
            "Literal reference labels in prose are not renumbered.\n",
            encoding="utf-8",
        )
    return output_dir


def _strings(value, transform):
    if isinstance(value, str):
        return transform(value)
    if isinstance(value, list):
        return [_strings(item, transform) for item in value]
    if isinstance(value, dict):
        return {key: _strings(item, transform) for key, item in value.items()}
    return value


def _mark_draft(draft):
    """Tag reference-token expansions, not free prose or quantitative value tokens."""
    prefix = f"\ue000{uuid4().hex}:"
    markers = {}

    def mark(text):
        def replace(match):
            key = (match[1], match[2])
            marker = f"{prefix}{len(markers)}\ue001"
            markers[marker] = key
            return marker + match[0]

        return re.sub(r"\{\{(figure|table|equation|cite):([A-Za-z0-9_.-]+)\}\}", replace, text)

    result = copy.deepcopy(draft)
    for paragraph in result["paragraphs"]:
        paragraph["text"] = mark(paragraph["text"])
        paragraph["inline_math"] = _strings(paragraph.get("inline_math", {}), mark)
    result["captions"] = _strings(result["captions"], mark)
    for table in result.get("tables", []):
        for field in ("caption", "note", "columns", "rows"):
            if field in table:
                table[field] = _strings(table[field], mark)
    for equation in result.get("equations", []):
        equation["expression"] = _strings(equation["expression"], mark)
    return result, markers


def _markdown(data):
    from cfdpaper.publication.export import _markdown_table

    lines = [f"# {data['title']}"]
    placed = {"equations": set(), "tables": set(), "figures": set()}

    def append_objects(ownership, figure_ids):
        for equation in data["equations"]:
            key = equation["equation_id"]
            if key in ownership.get("equations", []) and key not in placed["equations"]:
                model = SectionEquation.model_validate(equation)
                lines.append(f"{math_text(model.expression)}   ({model.equation_id})")
                placed["equations"].add(key)
        for table in data["tables"]:
            key = table["table_id"]
            if key in ownership.get("tables", []) and key not in placed["tables"]:
                lines.append(f"Table {key}.")
                lines.append(_markdown_table(SectionTable.model_validate(table)))
                if table["note"]:
                    lines.append(table["note"])
                placed["tables"].add(key)
        for figure in data["figures"]:
            key = figure["id"]
            if key in figure_ids and key not in placed["figures"]:
                lines.extend(
                    [f"![Figure {key}]({figure['path']})", f"Figure {key}. {figure['caption']}"]
                )
                placed["figures"].add(key)

    owner, figure_ids = {}, set()
    for paragraph in data["paragraphs"]:
        if "section_heading" in paragraph:
            append_objects(owner, figure_ids)
            owner = data.get("section_objects", {}).get(paragraph.get("section_id"), {})
            figure_ids = set()
        else:
            figure_ids.update(paragraph.get("figure_ids", []))
        lines.append(
            f"## {paragraph['section_heading']}"
            if "section_heading" in paragraph
            else paragraph["text"]
        )
    append_objects(owner, figure_ids)
    append_objects(
        {
            "tables": [t["table_id"] for t in data["tables"]],
            "equations": [e["equation_id"] for e in data["equations"]],
        },
        {f["id"] for f in data["figures"]},
    )
    if data["references"]:
        lines.extend(
            [
                "## References",
                *[
                    f"[{record['number']}] {record['text']} — {record['source']}"
                    for record in data["references"]
                ],
            ]
        )
    return "\n\n".join(lines) + "\n"


def _object_numbers(spine, loaded, raw_drafts):
    """Index declared objects once so forward cross-section references are also stable."""
    counters = {"figure": 0, "table": 0, "equation": 0}
    numbers = {}
    for contract in spine.sections:
        sid = contract.section_id
        draft = _Draft.model_validate(raw_drafts[sid])
        _, section = loaded[sid]
        for kind, ids in (
            ("figure", [f.id for f in section.figures]),
            ("table", [t.table_id for t in draft.tables]),
            ("equation", [e.equation_id for e in draft.equations]),
        ):
            if len(ids) != len(set(ids)):
                raise ValueError(f"Duplicate {kind} IDs in section {sid}")
            for identifier in ids:
                counters[kind] += 1
                numbers[(kind, sid, identifier)] = str(counters[kind])
    return numbers


def _cross_references(raw, numbers):
    used = []

    def resolve(text):
        def replace(match):
            kind, sid, identifier = match.groups()
            key = (kind, sid, identifier)
            if key not in numbers:
                raise ValueError(f"Unknown cross-section {kind}: {sid}/{identifier}")
            record = {"kind": kind, "section_id": sid, "id": identifier, "number": numbers[key]}
            if record not in used:
                used.append(record)
            return f"{kind.title()} {numbers[key]}"

        return re.sub(
            r"\{\{(figure|table|equation):([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)\}\}",
            replace,
            text,
        )

    return _strings(raw, resolve), used


def assemble_manuscript(package_dir: Path, drafts_path: Path, output_dir: Path) -> Path:
    """Assemble existing host drafts through section validation and source recomputation.

    ``drafts_path`` is {section_id: relative-draft-path}; its keys must exactly
    match the spine. The returned directory contains a renderer-compatible
    section.json, manuscript.md, numbering.json and independently editable local
    section outputs. No author file or previous output is updated in place.
    """
    package_dir, drafts_path, output_dir = map(Path, (package_dir, drafts_path, output_dir))
    _fresh(output_dir)
    data, loaded = _inputs(package_dir / "manuscript-input.json")
    drafts = _read(drafts_path)
    if not isinstance(drafts, dict) or set(drafts) != set(loaded):
        raise ValueError("Draft section IDs must exactly match the spine sections")
    if any(not isinstance(value, str) for value in drafts.values()):
        raise ValueError("Draft mapping values must be relative JSON paths")
    raw_drafts = {sid: _read(_relative(drafts_path.parent, path)) for sid, path in drafts.items()}
    object_numbers = _object_numbers(data.spine, loaded, raw_drafts)
    numbering = {"sections": {}, "references": []}
    reference_sources = {}
    combined = {
        "section_id": "manuscript",
        "title": data.title,
        "paragraphs": [],
        "figures": [],
        "tables": [],
        "equations": [],
        "references": [],
        "evidence": [],
        "resolved_values": {},
        "image_observations": {},
        "observation_notes": {},
        "section_objects": {},
    }
    with _stage(output_dir) as staged:
        notes = staged / "notes"
        notes.mkdir()
        for contract in data.spine.sections:
            sid = contract.section_id
            draft_path = _relative(drafts_path.parent, drafts[sid])
            raw, cross_references = _cross_references(raw_drafts[sid], object_numbers)
            draft = _Draft.model_validate(raw)
            if contract.role == "methods":
                body = "\n".join(p.text for p in draft.paragraphs)
                for table in draft.tables:
                    if "{{table:" + table.table_id + "}}" not in body:
                        raise ValueError(
                            f"Methods table {table.table_id} needs a paragraph reference"
                        )
            claims = {key for paragraph in draft.paragraphs for key in paragraph.evidence_ids}
            figures = {key for paragraph in draft.paragraphs for key in paragraph.figure_ids}
            if not set(contract.required_claim_ids) <= claims:
                raise ValueError(f"Required claim coverage missing in section {sid}")
            if not set(contract.required_figure_ids) <= figures:
                raise ValueError(f"Required figure coverage missing in section {sid}")
            marked, markers = _mark_draft(raw)
            marked_path = staged / "marked-draft.json"
            _write(marked_path, marked)
            source, _ = loaded[sid]
            local = assemble_section(source.parent, marked_path, staged / "sections" / sid)
            marked_path.unlink()
            result = _read(local / "section.json")
            mapping = {"figure": {}, "table": {}, "equation": {}, "cite": {}, "evidence": {}}
            mapping["cross_references"] = cross_references
            for kind, field, id_field in (
                ("figure", "figures", "id"),
                ("table", "tables", "table_id"),
                ("equation", "equations", "equation_id"),
            ):
                for item in result[field]:
                    mapping[kind][item[id_field]] = object_numbers[(kind, sid, item[id_field])]
            for record in result["references"]:
                identity = record["source"].strip().casefold()
                if identity not in reference_sources:
                    number = len(reference_sources) + 1
                    reference_sources[identity] = number
                    combined["references"].append(
                        {**record, "number": number, "id": f"ref-{number}"}
                    )
                    numbering["references"].append({"number": number, "source": record["source"]})
                mapping["cite"][record["id"]] = reference_sources[identity]
            citation_locals = {r["id"]: r["number"] for r in result["references"]}

            def unmark(text, markers=markers):
                for marker in markers:
                    text = text.replace(marker, "")
                return text

            def rebind(text, markers=markers, citation_locals=citation_locals, mapping=mapping):
                for marker, (kind, identifier) in markers.items():
                    if marker not in text:
                        continue
                    # Unused inline_math entries remain original token source, not output runs.
                    token = "{{" + kind + ":" + identifier + "}}"
                    text = text.replace(marker + token, token)
                    if marker not in text:
                        continue
                    old = (
                        f"[{citation_locals[identifier]}]"
                        if kind == "cite"
                        else f"{kind.title()} {identifier}"
                    )
                    new = (
                        f"[{mapping[kind][identifier]}]"
                        if kind == "cite"
                        else f"{kind.title()} {mapping[kind][identifier]}"
                    )
                    text = text.replace(marker + old, new)
                return text

            global_section = _strings(result, rebind)
            # Remove temporary token locators from independently usable local outputs.
            for name in ("section.json", "section.md", "review-packet/section.md"):
                path = local / name
                path.write_text(unmark(path.read_text(encoding="utf-8")), encoding="utf-8")
            shutil.copyfile(draft_path, local / "draft.json")
            shutil.copyfile(draft_path, local / "review-packet" / "draft.json")
            shutil.copyfile(local / "evidence-notes.md", notes / f"{sid}.md")
            if "style" not in combined:
                combined["style"] = global_section["style"]
            elif combined["style"] != global_section["style"]:
                raise ValueError("Manuscript sections must use a consistent publication style")
            content = "\n".join(p["text"] for p in global_section["paragraphs"])
            for prohibited in contract.prohibited_content:
                if prohibited.casefold() in content.casefold():
                    raise ValueError(f"Section {sid} contains prohibited content: {prohibited}")
            combined["paragraphs"].append(
                {"section_heading": draft.title, "level": 1, "section_id": sid}
            )
            combined["section_objects"][sid] = {
                "tables": list(mapping["table"].values()),
                "equations": list(mapping["equation"].values()),
            }
            for record in global_section["evidence"]:
                key = record["id"]
                # A pair represented as JSON cannot alias s.a/b with s/a.b.
                identity = json.dumps([sid, key], separators=(",", ":"))
                mapping["evidence"][key] = identity
                combined["evidence"].append({**record, "id": identity})
            for paragraph in global_section["paragraphs"]:
                paragraph["figure_ids"] = [
                    mapping["figure"][key] for key in paragraph["figure_ids"]
                ]
                paragraph["evidence_ids"] = [
                    mapping["evidence"][key] for key in paragraph["evidence_ids"]
                ]
                # inline_math retains the author token source; runs contain resolved native math.
                combined["paragraphs"].append(paragraph)
            for kind, field, id_field in (
                ("figure", "figures", "id"),
                ("table", "tables", "table_id"),
                ("equation", "equations", "equation_id"),
            ):
                for item in global_section[field]:
                    original = item[id_field]
                    item[id_field] = mapping[kind][original]
                    if "evidence_ids" in item:
                        item["evidence_ids"] = [
                            mapping["evidence"][key] for key in item["evidence_ids"]
                        ]
                    if kind == "figure":
                        asset = Path("figures") / (item["id"] + Path(item["path"]).suffix)
                        (staged / "figures").mkdir(exist_ok=True)
                        shutil.copyfile(local / item["path"], staged / asset)
                        item["path"] = asset.as_posix()
                    combined[field].append(item)
            for key, value in global_section["resolved_values"].items():
                value["source"] = (Path("sections") / sid / value["source"]).as_posix()
                combined["resolved_values"][mapping["evidence"][key]] = value
            for field in ("image_observations", "observation_notes"):
                combined[field].update(
                    {mapping["figure"][key]: value for key, value in global_section[field].items()}
                )
            numbering["sections"][sid] = mapping
        _write(staged / "section.json", combined)
        _write(staged / "numbering.json", numbering)
        _write(staged / "manuscript-input.json", data.model_dump())
        shutil.copyfile(drafts_path, staged / "author-drafts.json")
        (staged / "manuscript.md").write_text(_markdown(combined), encoding="utf-8")
    return output_dir
