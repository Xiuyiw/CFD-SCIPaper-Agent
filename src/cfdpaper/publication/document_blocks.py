"""One ordered, editable projection of the existing manuscript facts.

Source paragraphs retain evidence tokens; compiled content retains their current
display. This is a document view, not a second scientific database.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter
from uuid import NAMESPACE_URL, uuid5

from cfdpaper.publication.style import PublicationStyle


def paragraph_identity(text: str, occurrence: int = 0) -> str:
    """Upgrade an unlabelled legacy paragraph once; returned drafts persist the ID."""
    return "p-" + uuid5(NAMESPACE_URL, f"cfdpaper:paragraph:{occurrence}:{text}").hex[:20]


def stable_block_id(section_id: str, kind: str, local_id: str) -> str:
    return json.dumps([section_id, kind, local_id], ensure_ascii=False, separators=(",", ":"))


def source_runs(text: str, resolved_runs: list[dict], cross_references=()) -> list[dict]:
    """Retain source tokens, including forward cross-section object references."""
    resolved = {r["token"]: r for r in resolved_runs if r.get("token")}
    for item in cross_references:
        token = "{{" + item["kind"] + ":" + item["section_id"] + "/" + item["id"] + "}}"
        resolved[token] = {"text": f"{item['kind'].title()} {item['number']}"}
    result, cursor, counts = [], 0, Counter()
    for match in re.finditer(
        r"\{\{(?:value|figure|cite|table|equation|math):[A-Za-z0-9_./-]+\}\}", text
    ):
        if match.start() > cursor:
            result.append({"text": text[cursor : match.start()]})
        token = match.group(0)
        if token not in resolved:
            raise ValueError(f"No compiled display for source token {token}")
        record = {
            **resolved[token],
            "token": token,
            "span_id": f"span-{len(result)}-{counts[token]}",
        }
        counts[token] += 1
        result.append(record)
        cursor = match.end()
    if cursor < len(text):
        result.append({"text": text[cursor:]})
    return result


def apply_author_edits(document: dict, edits: dict) -> dict:
    """Overlay presentation and unresolved comments, never numerical facts."""
    ids = {block["id"] for block in document["blocks"]}
    document["unmatched_comments"] = [
        c for c in edits.get("comments", []) if c.get("block_id") not in ids
    ]
    for block in document["blocks"]:
        visual = edits.get("blocks", {}).get(block["id"], {})
        for key in ("formatting", "paragraph_format", "layout", "formatting_source_text"):
            if key in visual:
                block[key] = copy.deepcopy(visual[key])
        comments = [c for c in edits.get("comments", []) if c.get("block_id") == block["id"]]
        if comments:
            block["comments"] = copy.deepcopy(comments)
    return document


def source_definition_state(state: dict) -> dict:
    """Small author-return context; never embed raw field rows inside DOCX XML."""
    sections = {}
    for sid, entry in state.get("sections", {}).items():
        source = entry.get("input", {})
        evidence = {
            key: {
                k: record.get(k)
                for k in ("kind", "unit", "result_ref", "json_value_ref", "evidence_role")
            }
            for key, record in entry.get("evidence", {}).items()
        }
        sections[sid] = {
            "input": {k: source.get(k, []) for k in ("table_calculations", "result_comparisons")},
            "scientific_context": copy.deepcopy(entry.get("scientific_context", {})),
            "bindings": copy.deepcopy(entry.get("bindings", {})),
            "evidence": evidence,
        }
    return {
        "sections": sections,
        "terms": copy.deepcopy(state.get("terms", {})),
        "context": state.get("context", ""),
    }


def _block(kind, section_id, local_id, content, *, text=None, rendered=None):
    text = content.get("source_text", content.get("text", "")) if text is None else text
    rendered = content.get("text", text) if rendered is None else rendered
    spans = [
        {"id": run["span_id"], "token": run["token"], "text": run.get("text", "")}
        for run in content.get("semantic_runs", [])
        if run.get("token") and "span_id" in run
    ]
    result = {
        "id": stable_block_id(section_id, kind, local_id),
        "kind": kind,
        "section_id": section_id,
        "local_id": local_id,
        "text": text,
        "rendered_text": rendered,
        "spans": spans,
        "content": copy.deepcopy(content),
    }
    for field in ("formatting", "paragraph_format", "layout", "comments"):
        if field in content:
            result[field] = copy.deepcopy(content[field])
    return result


def build_document(data: dict, *, profile="research", layout="near-reference") -> dict:
    """Project an assembled section/manuscript into a single ordered block list.

    An explicit section order uses ``paragraph:ID``, ``figure:ID``,
    ``table:ID`` and ``equation:ID`` local identities. It must list every object
    exactly once. Figure captions travel with their figure. Legacy inputs retain
    their previous near-reference or after-text ordering until an author sets it.
    """
    if profile not in {"research", "report", "conference"}:
        raise ValueError("Unknown manuscript profile")
    if layout not in {"near-reference", "after-text"}:
        raise ValueError("Unknown manuscript layout")
    style = PublicationStyle.model_validate(data.get("style", {})).model_dump()
    if profile == "report":
        style.update(body_pt=12, heading_pt=13)
    elif profile == "conference":
        style.update(body_pt=10, heading_pt=11, caption_pt=9, reference_pt=9)
    groups = {}
    headings = {}
    current = data.get("section_id", "manuscript")
    occurrences = Counter()
    for paragraph in data.get("paragraphs", []):
        if "section_heading" in paragraph:
            current = paragraph["section_id"]
            headings[current] = paragraph
            groups.setdefault(current, [])
            continue
        sid = paragraph.get("section_id", current)
        text = paragraph.get("source_text", paragraph["text"])
        local_id = paragraph.get("paragraph_id") or paragraph_identity(text, occurrences[sid, text])
        occurrences[sid, text] += 1
        groups.setdefault(sid, []).append(_block("paragraph", sid, local_id, paragraph))
    origins = data.get("object_origins", {})
    objects = {sid: [] for sid in groups}
    for kind, field, key in (
        ("equation", "equations", "equation_id"),
        ("table", "tables", "table_id"),
        ("figure", "figures", "id"),
    ):
        for item in data.get(field, []):
            identity = str(item[key])
            owner = origins.get(kind, {}).get(identity)
            if owner:
                sid, local_id = owner["section_id"], owner["local_id"]
            else:
                sid = next(
                    (
                        s
                        for s, obj in data.get("section_objects", {}).items()
                        if identity in obj.get("figure_ids" if kind == "figure" else field, [])
                    ),
                    data.get("section_id", current),
                )
                local_id = identity
            groups.setdefault(sid, [])
            objects.setdefault(sid, [])
            label = item.get("caption", "")
            if kind == "equation":
                from cfdpaper.publication.elements import MathNode, math_text

                label = math_text(MathNode.model_validate(item["expression"]))
            objects[sid].append(_block(kind, sid, local_id, item, text=label, rendered=label))
    blocks = []
    for sid, paragraphs in groups.items():
        if sid in headings:
            heading = headings[sid]
            blocks.append(
                _block(
                    "heading",
                    sid,
                    "heading",
                    heading,
                    text=heading["section_heading"],
                    rendered=heading["section_heading"],
                )
            )
        remaining = objects.get(sid, [])[:]
        order = data.get("section_orders", {}).get(sid, data.get("block_order", []))
        if order:
            lookup = {f"{b['kind']}:{b['local_id']}": b for b in paragraphs + remaining}
            if len(lookup) != len(paragraphs + remaining):
                raise ValueError("Duplicate block identity")
            if len(order) != len(set(order)) or set(order) != set(lookup):
                raise ValueError(f"Section {sid} block order must list every object exactly once")
            sequence = [lookup[key] for key in order]
        elif layout == "after-text":
            sequence = paragraphs + remaining
        else:
            sequence = []
            for paragraph in paragraphs:
                sequence.append(paragraph)
                mentioned = set(paragraph["content"].get("figure_ids", []))
                placed = [
                    b
                    for b in remaining
                    if b["kind"] == "figure"
                    and b["content"]["id"] in mentioned
                    and b["content"].get("placement") != "section-end"
                ]
                sequence.extend(placed)
                remaining = [b for b in remaining if b not in placed]
            sequence.extend(remaining)
        for block in sequence:
            blocks.append(block)
            if block["kind"] == "figure":
                content = block["content"]
                caption_content = {**content, "semantic_runs": content.get("caption_runs", [])}
                blocks.append(
                    _block(
                        "caption",
                        sid,
                        block["local_id"],
                        caption_content,
                        text=content.get("source_caption", content["caption"]),
                        rendered=content["caption"],
                    )
                )
        if data.get("section_objects", {}).get(sid, {}).get("role") == "abstract" and data.get(
            "keywords"
        ):
            value = "; ".join(data["keywords"])
            blocks.append(_block("keywords", sid, "keywords", {}, text=value, rendered=value))
    for record in data.get("references", []):
        reference_id = (
            "ref-"
            + uuid5(NAMESPACE_URL, record.get("source", record["text"]).strip().casefold()).hex[:20]
        )
        blocks.append(
            _block(
                "reference",
                "bibliography",
                reference_id,
                record,
                text=record["text"],
                rendered=record["text"],
            )
        )
    ids = [block["id"] for block in blocks]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate block identity")
    payload = {
        "schema_version": 1,
        "title": data["title"],
        "profile": profile,
        "style": style,
        "blocks": blocks,
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload["baseline_id"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return payload
