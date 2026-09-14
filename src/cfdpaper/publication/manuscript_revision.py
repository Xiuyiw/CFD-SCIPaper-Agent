"""Prepare selected-review editing tasks without applying manuscript changes."""

from __future__ import annotations

from pathlib import Path

from cfdpaper.publication.elements import MathNode, math_text
from cfdpaper.publication.manuscript import assert_manuscript_current
from cfdpaper.publication.manuscript_review import (
    _copy_file,
    _copy_tree,
    _inside,
    _locators,
    _output,
)
from cfdpaper.publication.section import _read, _stage, _write


def _text(record: dict, field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Action {field} must be a nonempty string")
    return value


def _target(target: dict, locators: dict, drafts: dict, manuscript: dict) -> dict:
    if not isinstance(target, dict):
        raise ValueError("Each accepted target must be an object")
    sid = target.get("section_id")
    if not isinstance(sid, str) or sid not in drafts:
        raise ValueError(f"Unknown target section: {sid}")
    common = {"section_id": sid, "draft_path": f"working/{drafts[sid]}"}
    if "paragraph" in target:
        position = target["paragraph"]
        if type(position) is not int or position < 1 or "kind" in target:
            raise ValueError("Paragraph target requires a 1-based integer and no object kind")
        quote = _text(target, "quote")
        matches = [
            item
            for item in locators["paragraphs"]
            if item["section_id"] == sid and item["paragraph"] == position
        ]
        if len(matches) != 1:
            raise ValueError(f"Absent or ambiguous paragraph target: {sid}/{position}")
        if matches[0]["text"].count(quote) != 1:
            raise ValueError(f"Absent, stale or ambiguous paragraph quote: {sid}/{position}")
        return {
            **common,
            "kind": "paragraph",
            "paragraph": position,
            "quote": quote,
            "reviewed_text": matches[0]["text"],
            "draft_pointer": f"/paragraphs/{position - 1}/text",
        }
    kind, number = target.get("kind"), target.get("global_number")
    if kind not in {"figure", "table", "equation", "reference"}:
        raise ValueError(f"Unknown target object kind: {kind}")
    if not isinstance(number, (str, int)) or isinstance(number, bool) or not str(number):
        raise ValueError("Object target requires a global_number")
    matches = [
        item
        for item in locators["objects"]
        if item["section_id"] == sid
        and item["kind"] == kind
        and str(item["global_number"]) == str(number)
        and ("local_id" not in target or item["local_id"] == target["local_id"])
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Absent or ambiguous object target: {sid}/{kind}/{number}; "
            "specify local_id from the review locator index"
        )
    item = matches[0]
    field, key = {
        "figure": ("figures", "id"),
        "table": ("tables", "table_id"),
        "equation": ("equations", "equation_id"),
        "reference": ("references", "number"),
    }[kind]
    record = next(row for row in manuscript[field] if str(row[key]) == str(number))
    quote = (
        math_text(MathNode.model_validate(record["expression"]))
        if kind == "equation"
        else record.get("caption") or record.get("source")
    )
    return {
        **common,
        "kind": kind,
        "global_number": item["global_number"],
        "local_id": item["local_id"],
        "local_number": item["local_number"],
        "quote": quote,
        "reviewed_object": record,
        "input_path": f"working/sections/{sid}/input.json",
    }


def _evidence_links(root: Path, targets: list[dict], drafts: dict, locators: dict) -> list[dict]:
    """Find declared uses of targeted evidence, not inferred scientific dependencies."""
    entries = _read(root / "manuscript-input.json")["sections"]
    numbering = _read(root / "numbering.json")["sections"]
    locations = {(p["section_id"], p["paragraph"]): p for p in locators["paragraphs"]}
    records, selected = [], set()
    for entry in entries:
        sid = entry["section_id"]
        draft = _read(_inside(root, drafts[sid]))
        bindings = entry.get("evidence_bindings", {})

        def owner(eid, bindings=bindings, sid=sid):
            return bindings.get(eid, f"{sid}/{eid}")

        own_targets = [t for t in targets if t["section_id"] == sid]
        for target in own_targets:
            if target["kind"] == "reference":
                selected.add(owner(target["local_id"]))
        for kind, field in (
            ("paragraph", "paragraphs"),
            ("table", "tables"),
            ("equation", "equations"),
        ):
            for index, item in enumerate(draft.get(field, [])):
                ids = sorted(set(item.get("evidence_ids", [])))
                record = {
                    "section_id": sid,
                    "kind": kind,
                    "draft_path": f"working/{drafts[sid]}",
                    "draft_pointer": f"/{field}/{index}",
                    "evidence_ids": ids,
                    "owner_evidence": [owner(eid) for eid in ids],
                }
                if kind == "paragraph":
                    record.update(paragraph=index + 1, text=locations[sid, index + 1]["text"])
                    matched = any(
                        (t["kind"] == kind and t["paragraph"] == index + 1)
                        or (t["kind"] == "figure" and t["local_id"] in item.get("figure_ids", []))
                        for t in own_targets
                    )
                else:
                    local = item[f"{kind}_id"]
                    record.update(local_id=local, global_number=numbering[sid][kind][local])
                    matched = any(t["kind"] == kind and t["local_id"] == local for t in own_targets)
                if matched:
                    selected.update(record["owner_evidence"])
                records.append(record)
    uses = []
    for record in records:
        pairs = [
            (eid, owner)
            for eid, owner in zip(record["evidence_ids"], record["owner_evidence"], strict=True)
            if owner in selected
        ]
        if pairs:
            uses.append(
                {
                    **record,
                    "evidence_ids": [eid for eid, _ in pairs],
                    "owner_evidence": sorted({owner for _, owner in pairs}),
                }
            )
    return uses


def _task(result: dict) -> str:
    lines = [
        "# Selected manuscript editing task",
        "",
        f"Reviewed package: {result['package_id']}",
        "",
        f"Read the COMPLETE report: {result['readable_report']}. The original report and "
        "reviewed snapshot are retained under reference/. Read selected-actions.json for "
        "all decisions and revision-task.json for resolved targets.",
        "",
        "Before editing, read [CFD evidence writing](skills/cfd-evidence-writing/SKILL.md) "
        "and its [whole-manuscript review guidance]"
        "(skills/cfd-evidence-writing/references/manuscript-review.md). "
        "Follow the Skill's section-specific references for the selected work.",
        "",
        "Edit the existing inputs/drafts in working/ only for accepted actions where justified. "
        "Read each target in context and assess the recommendation against its evidence. "
        "A matching quotation does not establish scientific validity. Preserve value/citation "
        "tokens and local or section-qualified object tokens; do not replace them with typed "
        "numbers. Leave unrelated drafts untouched. Related sections are explicit requests "
        "to reconsider connected prose, not blanket instructions to rewrite them.",
        "",
        "No prose or numerical edits have been applied. The working/ reading views still "
        "describe the reviewed manuscript; edit authoring JSON, not generated manuscript.md "
        "or section.json. Previews in reference/ are historical reading aids, never revised "
        "output. If a later author candidate exists, reconcile it against this reviewed "
        "snapshot first; this task does not merge into that candidate.",
        "",
    ]
    for action in result["actions"]:
        if action["decision"] != "accept":
            continue
        lines += [f"## Accepted action: {action['id']}", "", "Exact report quotation:", ""]
        lines += ["> " + line for line in action["report_quote"].splitlines()]
        lines += ["", f"Rationale: {action['rationale']}", "", action["instruction"], ""]
        for target in action["resolved_targets"]:
            label = (
                f"paragraph {target['paragraph']}"
                if target["kind"] == "paragraph"
                else f"{target['kind']} {target['global_number']} (local {target['local_id']})"
            )
            lines += [
                f"Target: {target['section_id']}, {label}; draft: {target['draft_path']}",
                "",
            ]
            if "input_path" in target:
                lines += [f"Object definitions: {target['input_path']}", ""]
            if target.get("quote"):
                lines += ["Exact reviewed manuscript quotation:", ""]
                lines += ["> " + line for line in target["quote"].splitlines()]
                lines.append("")
        for sid, reason in action.get("related_sections", {}).items():
            lines += [f"Related section {sid}: {reason}", f"Draft: {result['drafts'][sid]}", ""]
        if "evidence_uses" in action:
            lines += [
                "### Declared evidence links — reread, not automatic edits",
                "",
                "These locations share an explicitly bound evidence source with this target. "
                "They are not proof of scientific dependence or evidence sufficiency. "
                "Assess which interpretations require narrowing or new evidence; preserve "
                "unaffected prose. Undeclared dependencies and free-text copies are not detected.",
                "",
            ]
            for use in action["evidence_uses"]:
                label = (
                    f"paragraph {use['paragraph']}"
                    if use["kind"] == "paragraph"
                    else f"{use['kind']} {use['global_number']} (local {use['local_id']})"
                )
                lines += [
                    f"- {use['section_id']}, {label}: {', '.join(use['owner_evidence'])}; "
                    f"{use['draft_path']} {use['draft_pointer']}",
                ]
            if not action["evidence_uses"]:
                lines.append("No declared evidence uses found; inspect the target in context.")
            lines.append("")
    inactive = [a for a in result["actions"] if a["decision"] != "accept"]
    if inactive:
        lines += ["## Rejected/deferred decisions (not editing instructions)", ""]
        lines += [f"- {a['id']}: {a['decision']} — {a['rationale']}" for a in inactive]
        lines.append("")
    lines += [
        "## Assemble a new candidate",
        "",
        "From this task directory, use ordinary manuscript assembly after host editing:",
        "",
        "```text",
        "cfdpaper write . --artifact manuscript --package working --draft working/drafts.json "
        "--output NEW_CANDIDATE",
        "cfdpaper write . --artifact manuscript --package NEW_CANDIDATE --docx "
        "--layout near-reference --output NEW_MANUSCRIPT.docx",
        "```",
        "",
        "Use a fresh output path, inspect CHANGES.md and the new manuscript, and render/check "
        "new previews separately. Add --pdf-preview when LibreOffice is available.",
    ]
    return "\n".join(lines) + "\n"


def prepare_manuscript_revision(
    review_return_dir: Path, actions_path: Path, output_dir: Path
) -> dict:
    """Resolve selected advice into a portable workspace; never alter author prose."""
    review_return_dir, actions_path, output_dir = map(
        Path, (review_return_dir, actions_path, output_dir)
    )
    _output(review_return_dir, output_dir)
    returned = _read(review_return_dir / "review-return.json")
    if returned.get("kind") != "manuscript-review-return":
        raise ValueError("Expected a whole-manuscript review return")
    mapping = _read(actions_path)
    if not isinstance(mapping, dict) or mapping.get("package_id") != returned["package_id"]:
        raise ValueError("Selected actions package_id must match the review return")
    actions = mapping.get("actions")
    if not isinstance(actions, list):
        raise ValueError("Selected actions must contain an actions list")
    readable = returned.get("readable_report")
    if not readable:
        raise ValueError("Readable report extraction is required; the host must complete it first")
    report = _inside(review_return_dir, readable).read_text(encoding="utf-8-sig")
    snapshot = _inside(review_return_dir, returned["snapshot"]).parent
    package = _read(snapshot / "review-package.json")
    if (
        package.get("kind") != "manuscript-review"
        or package.get("package_id") != mapping["package_id"]
    ):
        raise ValueError("Reviewed snapshot package_id does not match the review return")
    manuscript = snapshot / "manuscript"
    combined = _read(manuscript / "section.json")
    locators = _read(_inside(snapshot, package["locators"]))
    expected = _locators(manuscript, combined, _read(manuscript / "numbering.json"))
    if locators != expected:
        raise ValueError("Stale or ambiguous review locators; reconcile the reviewed snapshot")
    drafts = _read(manuscript / "drafts.json")
    resolved, seen = [], set()
    for action in actions:
        if not isinstance(action, dict):
            raise ValueError("Each action must be an object")
        identity = _text(action, "id")
        if identity in seen:
            raise ValueError(f"Duplicate action id: {identity}")
        seen.add(identity)
        decision = action.get("decision")
        if decision not in {"accept", "reject", "defer"}:
            raise ValueError(f"Unknown action decision: {decision}")
        trace = action.get("trace_evidence", False)
        if type(trace) is not bool:
            raise ValueError("trace_evidence must be a boolean")
        quote = _text(action, "report_quote")
        _text(action, "rationale")
        if quote not in report:
            raise ValueError(f"Action {identity} report_quote is absent from the complete report")
        related = action.get("related_sections", {})
        if not isinstance(related, dict):
            raise ValueError("related_sections must map section IDs to nonempty reasons")
        for sid, reason in related.items():
            if sid not in drafts or not isinstance(reason, str) or not reason.strip():
                raise ValueError(f"Unknown related section or empty reason: {sid}")
        targets = []
        if decision == "accept":
            _text(action, "instruction")
            requested = action.get("targets")
            if not isinstance(requested, list) or not requested:
                raise ValueError("Accepted action requires at least one target")
            targets = [_target(t, locators, drafts, combined) for t in requested]
        item = {**action, "resolved_targets": targets}
        if decision == "accept" and trace:
            item["evidence_uses"] = _evidence_links(manuscript, targets, drafts, locators)
        else:
            # Output-only links must be computed, not inherited from a supplied action.
            item.pop("evidence_uses", None)
        resolved.append(item)
    assert_manuscript_current(manuscript)
    result = {
        "kind": "manuscript-revision-task",
        "package_id": mapping["package_id"],
        "status": "ready-for-host-editing",
        "reference": "reference/review-return.json",
        "raw_report": "reference/" + returned["raw_report"],
        "readable_report": "reference/" + readable,
        "selected_actions": "selected-actions.json",
        "working": "working",
        "task": "TASK.md",
        "drafts": {sid: f"working/{path}" for sid, path in drafts.items()},
        "actions": resolved,
    }
    with _stage(output_dir) as staged:
        _copy_tree(review_return_dir, staged / "reference")
        _copy_file(actions_path, staged / "selected-actions.json")
        _copy_tree(manuscript, staged / "working")
        skill = Path(__file__).resolve().parents[1] / "skills/cfd-evidence-writing"
        if not skill.is_dir():
            skill = Path(__file__).resolve().parents[3] / "skills/cfd-evidence-writing"
        _copy_tree(skill, staged / "skills/cfd-evidence-writing")
        for suffix in ("pdf", "docx"):
            (staged / "working" / f"manuscript.{suffix}").unlink(missing_ok=True)
        _write(staged / "revision-task.json", result)
        (staged / "TASK.md").write_text(_task(result), encoding="utf-8")
    return result
