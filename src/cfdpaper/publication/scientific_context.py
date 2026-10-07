"""Located, case-scoped scientific facts for existing manuscript contexts.

The host supplies the interpretations and comparison status. This module checks
identity, scope and exact source lines, not physical validity. Project Python
files are read only as UTF-8 text and are never imported or executed.
"""

from __future__ import annotations

import copy
import json
import re
import shutil
from pathlib import Path

from ..materials import MAX_FILE_BYTES, MAX_TOTAL_BYTES
from .literature import _nonblank, _relative_file

_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_LINES = re.compile(r"^L([1-9][0-9]*)(?:-L([1-9][0-9]*))?$")
_TEXT_SUFFIXES = {".md", ".txt", ".json", ".csv", ".py"}
_STATUSES = {"recorded", "conflict", "unknown"}
_METHOD_FIELDS = {
    "materials": 0,
    "material_properties": 0,
    "boundary_conditions": 1,
    "operating_conditions": 1,
    "cell_zone_conditions": 2,
    "geometry": 3,
    "dimensions": 3,
    "models": 4,
    "solver": 5,
    "solver_settings": 5,
    "numerical_settings": 6,
    "numerics": 6,
    "solution_methods": 6,
    "solution_controls": 6,
    "discretization": 6,
}


def _id(value, field):
    value = _nonblank(value, field)
    if not _TOKEN.fullmatch(value):
        raise ValueError(f"{field} must be a safe token ID")
    return value


def _ids(value, field, *, nonempty=True):
    if not isinstance(value, list) or (nonempty and not value):
        raise ValueError(f"{field} must be a {'nonempty ' if nonempty else ''}list of IDs")
    for item in value:
        _id(item, field)
    if len(set(value)) != len(value):
        raise ValueError(f"{field} contains duplicate IDs")
    return value


def _records(data, key):
    records = data.get(key, [])
    if not isinstance(records, list):
        raise ValueError(f"{key} must be a list")
    indexed = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError(f"Each {key} entry must be an object")
        rid = _id(record.get("id"), f"{key} id")
        if rid in indexed:
            raise ValueError(f"Duplicate {key} id: {rid}")
        indexed[rid] = record
    data[key] = records
    return indexed


def _scope(record, cases, allowed_sections):
    for case in _ids(record.get("case_ids"), "case_ids"):
        if case not in cases:
            raise ValueError(f"Unknown case ID {case!r} in {record['id']!r}")
    sections = _ids(record.get("section_ids"), "section_ids")
    if allowed_sections is not None:
        unknown = set(sections) - allowed_sections
        if unknown:
            raise ValueError(f"Unknown section IDs in {record['id']!r}: {sorted(unknown)}")
    status = record.setdefault("status", "recorded")
    _nonblank(status, "status")
    if status not in _STATUSES:
        raise ValueError("status must be recorded, conflict or unknown")
    _nonblank(record.get("text"), "text")


def _section_set(value):
    if isinstance(value, str):
        raise ValueError("section IDs must be a collection, not a string")
    sections = set(value)
    for section in sections:
        _id(section, "section ID")
    return sections


def load_scientific_context(path, allowed_sections=None) -> dict:
    """Read facts/comparisons and verify their exact line-range excerpts.

    Input source paths are relative to the context JSON, without traversal, as
    in the existing literature workspace. Returned source paths remain relative
    to this JSON; use ``copy_scientific_context`` for transport.
    Unknown facts may omit their source. Stage/domain/operator are optional
    descriptions, never defaults inferred from another case or a filename.
    """
    path = Path(path)
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("Scientific context exceeds the material file size limit")
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("Scientific context must be an object")
    sections = None if allowed_sections is None else _section_set(allowed_sections)
    cases = _records(data, "cases")
    facts = _records(data, "facts")
    comparisons = _records(data, "comparisons")
    for case in cases.values():
        if "name" in case:
            _nonblank(case["name"], "case name")
    sources = {}
    total_bytes = 0
    for fact in facts.values():
        _scope(fact, cases, sections)
        for key in ("kind", "name"):
            _nonblank(fact.get(key), key)
        for key in ("stage", "domain", "operator"):
            if key in fact:
                _nonblank(fact[key], key)
        source = fact.get("source")
        if source is None and fact["status"] == "unknown":
            continue
        if not isinstance(source, dict):
            raise ValueError(f"Fact {fact['id']!r} requires a located source")
        source_path = _relative_file(path.parent, source.get("path"), "source.path")
        if source_path.suffix.lower() not in _TEXT_SUFFIXES:
            raise ValueError("Scientific sources must be UTF-8 text, Markdown, JSON, CSV or Python")
        if source_path not in sources:
            size = source_path.stat().st_size
            if size > MAX_FILE_BYTES or total_bytes + size > MAX_TOTAL_BYTES:
                raise ValueError("Scientific sources exceed the material size limits")
            total_bytes += size
            try:
                sources[source_path] = source_path.read_text(encoding="utf-8-sig").splitlines()
            except UnicodeError as exc:
                raise ValueError(f"Scientific source is not UTF-8 text: {source['path']}") from exc
        locator = _nonblank(source.get("locator"), "source.locator")
        match = _LINES.fullmatch(locator)
        if not match:
            raise ValueError("source.locator must be Lx or Lx-Ly (one-based source lines)")
        start, end = int(match[1]), int(match[2] or match[1])
        lines = sources[source_path]
        if end < start or end > len(lines):
            raise ValueError(f"Source line range out of bounds: {source['path']}:{locator}")
        excerpt = _nonblank(source.get("excerpt"), "source.excerpt")
        if excerpt.replace("\r\n", "\n") != "\n".join(lines[start - 1 : end]):
            raise ValueError(
                f"Source excerpt does not match exact lines: {source['path']}:{locator}"
            )
    for comparison in comparisons.values():
        _scope(comparison, cases, sections)
        fact_ids = _ids(comparison.get("fact_ids"), "fact_ids")
        linked_cases = set()
        for fid in fact_ids:
            if fid not in facts:
                raise ValueError(f"Unknown comparison fact ID: {fid}")
            linked_cases.update(facts[fid]["case_ids"])
            if comparison["status"] == "recorded" and facts[fid]["status"] != "recorded":
                raise ValueError("A recorded comparison cannot upgrade conflict or unknown facts")
        if linked_cases != set(comparison["case_ids"]):
            raise ValueError("Comparison case_ids must match its linked facts' case scope")
    return data


def copy_scientific_context(path, output_dir, *, section_ids=None) -> dict:
    """Save context.json and byte-identical sources in a new portable directory.

    The returned dictionary has source paths relative to ``output_dir``. Existing
    output directories are not overwritten; originals are never changed. With
    ``section_ids``, only selected facts/comparisons and their source files travel.
    """
    path = Path(path)
    data = load_scientific_context(path)
    if section_ids is not None:
        data = select_scientific_context(data, section_ids)
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise ValueError(f"Scientific context output directory already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    sources_dir = output_dir / "sources"
    sources_dir.mkdir()
    copied = {}
    for fact in data["facts"]:
        source = fact.get("source")
        if source is None:
            continue
        original = _relative_file(path.parent, source["path"], "source.path")
        if original not in copied:
            target = Path("sources") / f"source-{len(copied) + 1:04d}{original.suffix.lower()}"
            shutil.copyfile(original, output_dir / target)
            copied[original] = target.as_posix()
        source["path"] = copied[original]
    (output_dir / "context.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return data


def select_scientific_context(data, section_ids) -> dict:
    """Select section facts and comparisons, retaining located comparison inputs.

    Comparison dependencies can originate in another section; their original
    case and section scope remains visible and is never widened.
    """
    sections = _section_set(section_ids)
    selected = copy.deepcopy(data)
    comparisons = [
        item for item in selected["comparisons"] if sections.intersection(item["section_ids"])
    ]
    required = {fid for item in comparisons for fid in item["fact_ids"]}
    facts = [
        item
        for item in selected["facts"]
        if item["id"] in required or sections.intersection(item["section_ids"])
    ]
    case_ids = {cid for item in facts + comparisons for cid in item["case_ids"]}
    selected.update(
        facts=facts,
        comparisons=comparisons,
        cases=[item for item in selected["cases"] if item["id"] in case_ids],
    )
    return selected


def _parameter_entries(value, pointer=""):
    if isinstance(value, dict):
        for key, child in value.items():
            token = key.replace("~", "~0").replace("/", "~1")
            yield from _parameter_entries(child, pointer + "/" + token)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _parameter_entries(child, pointer + "/" + str(index))
    else:
        yield {"pointer": pointer, "value": value}


def _parameter_order(entry):
    pointer = entry["pointer"]
    fields = [re.sub(r"[^a-z0-9]+", "_", part.casefold()) for part in pointer.split("/")]
    priority = min(
        (_METHOD_FIELDS[field] for field in fields if field in _METHOD_FIELDS), default=7
    )
    natural = tuple(
        (0, int(part)) if part.isdigit() else (1, part.casefold())
        for part in re.split(r"([0-9]+)", pointer)
    )
    return priority, natural


def read_source_parameters(path, *, section_ids=None, limit=200) -> dict:
    """Read literal primitive leaves from JSON files linked by selected facts.

    JSON Pointers locate the exact recorded values, including array indices and
    escaped keys. Linked fact IDs identify why a file is present, not which of
    its parameters apply to each case. The host must check that applicability.
    The global leaf limit prioritizes named method fields, then natural path
    order; other fields are retained unless the explicit limit truncates them.
    A source that is valid located text but not parseable JSON remains listed
    with an explicit issue and no parameter entries; other sources continue.
    """
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
        raise ValueError("limit must be a nonnegative integer")
    path = Path(path)
    data = load_scientific_context(path)
    if section_ids is not None:
        data = select_scientific_context(data, section_ids)
    sources = []
    indexed = {}
    candidates = []
    for fact in data["facts"]:
        source = fact.get("source")
        if source is None or Path(source["path"]).suffix.lower() != ".json":
            continue
        source_path = _relative_file(path.parent, source["path"], "source.path")
        if source_path not in indexed:
            index = len(sources)
            indexed[source_path] = index
            issues = []
            try:
                recorded = json.loads(source_path.read_text(encoding="utf-8-sig"))
                entries = list(_parameter_entries(recorded))
            except json.JSONDecodeError as exc:
                entries = []
                issues.append(
                    {
                        "code": "invalid-json",
                        "message": (
                            f"JSON parameters unavailable: {exc.msg} "
                            f"at line {exc.lineno}, column {exc.colno}. "
                            "Located source text remains available."
                        ),
                    }
                )
            sources.append(
                {
                    "path": source["path"],
                    "linked_fact_ids": [],
                    "entries": [],
                    "truncated": False,
                    "issues": issues,
                }
            )
            candidates.extend((index, entry) for entry in entries)
        sources[indexed[source_path]]["linked_fact_ids"].append(fact["id"])
    candidates.sort(key=lambda item: (*_parameter_order(item[1]), item[0]))
    for index, entry in candidates[:limit]:
        sources[index]["entries"].append(entry)
    for index, _ in candidates[limit:]:
        sources[index]["truncated"] = True
    return {
        "sources": sources,
        "truncated": len(candidates) > limit,
        "scope_note": (
            "File-recorded values only. Linked fact IDs locate the source file; they do not "
            "assign all file parameters to those facts' cases or establish scientific validity."
        ),
    }


def render_scientific_context(data) -> str:
    """Render host-readable facts and comparisons with explicit scopes/locations."""
    lines = ["# Scientific context", ""]
    parameters = data.get("source_parameters")
    if parameters and parameters["sources"]:
        lines.extend(["## Recorded source parameters", "", parameters["scope_note"], ""])
        for source in parameters["sources"]:
            lines.append(
                f"### {source['path']} (linked facts: {', '.join(source['linked_fact_ids'])})"
            )
            lines.append("")
            for entry in source["entries"]:
                value = json.dumps(entry["value"], ensure_ascii=False)
                lines.append(f"- `{entry['pointer']}`: {value}")
            if source["truncated"]:
                lines.append(
                    "- Additional values exist; open the source for relevant omitted fields."
                )
            for issue in source["issues"]:
                lines.append("- " + issue["message"])
            lines.append("")
    lines.extend(["## Located facts", ""])
    for fact in data["facts"]:
        scope = f"cases: {', '.join(fact['case_ids'])}; sections: {', '.join(fact['section_ids'])}"
        lines.append(
            f"- {fact['id']} [{fact.get('status', 'recorded')}] "
            f"{fact['kind']} / {fact['name']} ({scope}): {fact['text']}"
        )
        details = [f"{key}: {fact[key]}" for key in ("stage", "domain", "operator") if key in fact]
        if details:
            lines.append("  " + "; ".join(details))
        source = fact.get("source")
        if source:
            lines.append(f"  Source: {source['path']}:{source['locator']}")
            lines.extend("  > " + line for line in source["excerpt"].splitlines())
        else:
            lines.append("  Source: not recorded (unknown fact)")
    lines.extend(["", "## Comparisons", ""])
    for item in data["comparisons"]:
        lines.append(
            f"- {item['id']} [{item.get('status', 'recorded')}] "
            f"cases: {', '.join(item['case_ids'])}; sections: {', '.join(item['section_ids'])}; "
            f"facts: {', '.join(item['fact_ids'])}: {item['text']}"
        )
    return "\n".join(lines) + "\n"
