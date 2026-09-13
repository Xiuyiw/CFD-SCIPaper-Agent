"""Pure, explicit-dependency change suggestions; no prose interpretation or edits."""

from __future__ import annotations

_NOTICE = (
    "Targeted host review suggestions; bound values may recompute but prose meaning "
    "is not automatically revised."
)


def _small(value, depth=0):
    if isinstance(value, str):
        return value if len(value) <= 160 else value[:157] + "..."
    if isinstance(value, dict):
        if depth >= 2:
            return {"field_count": len(value)}
        keys = sorted(value)[:8]
        result = {key: _small(value[key], depth + 1) for key in keys}
        if len(value) > len(keys):
            result["omitted_field_count"] = len(value) - len(keys)
        return result
    if isinstance(value, list):
        if len(value) <= 8 and all(not isinstance(item, (dict, list)) for item in value):
            return [_small(item) for item in value]
        return {"item_count": len(value)}
    return value


def _fields(before, after):
    if isinstance(before, dict) and isinstance(after, dict):
        return sorted(
            key
            for key in before.keys() | after.keys()
            if key not in before or key not in after or before[key] != after[key]
        )
    return []


def compare_manuscript_states(previous: dict | None, current: dict) -> dict:
    """Compare portable snapshots and follow only declared section/evidence links.

    The caller validates snapshots and dependencies. Evidence maps contain full
    definitions, so their duplicate raw-input evidence list is not counted as a
    second, section-wide definition change. No baseline means no unchanged claim.
    """
    report = {
        "baseline_available": previous is not None,
        "changes": [],
        "affected_sections": {},
        "unchanged_sections": [],
        "notice": _NOTICE,
    }
    if previous is None:
        return report
    old, new = previous.get("sections", {}), current.get("sections", {})
    affected = report["affected_sections"]
    evidence_changed, broad = set(), set()

    def affect(sid, reason):
        if sid in new and reason not in affected.setdefault(sid, []):
            affected[sid].append(reason)

    def change(category, reference, before, after, sid=None, present=(True, True)):
        status = "added" if not present[0] else "removed" if not present[1] else "changed"
        item = {"category": category, "reference": reference, "status": status}
        fields = _fields(before, after)
        if fields:
            item["fields"] = fields
        if category in {"source", "context", "draft", "section"}:
            item["before"] = {"present": present[0] and before is not None}
            item["after"] = {"present": present[1] and after is not None}
            if category in {"source", "context"}:
                item["before"]["characters"] = len(before or "")
                item["after"]["characters"] = len(after or "")
        else:
            for label, value in (("before", before), ("after", after)):
                selected = {key: value[key] for key in fields if key in value} if fields else value
                item[label] = _small(selected)
        reason = f"{category.capitalize()} '{reference}' {status}."
        if sid is not None:
            item["section_id"] = sid
            affect(sid, reason)
        else:
            for candidate in sorted(new):
                affect(candidate, f"Shared {reason[0].lower() + reason[1:]}")
        report["changes"].append(item)

    terms_before, terms_after = previous.get("terms", {}), current.get("terms", {})
    for term in sorted(terms_before.keys() | terms_after.keys()):
        if (
            term not in terms_before
            or term not in terms_after
            or terms_before[term] != terms_after[term]
        ):
            change(
                "term",
                term,
                terms_before.get(term),
                terms_after.get(term),
                present=(term in terms_before, term in terms_after),
            )
    if previous.get("context", "") != current.get("context", ""):
        change("context", "context", previous.get("context", ""), current.get("context", ""))
    for sid in sorted(old.keys() | new.keys()):
        before, after = old.get(sid, {}), new.get(sid, {})
        if sid not in old or sid not in new:
            change("section", sid, before, after, sid, (sid in old, sid in new))
            broad.add(sid)
            continue
        for category, key in (
            ("evidence", "evidence"),
            ("source", "sources"),
            ("literature", "literature"),
            ("binding", "bindings"),
        ):
            left, right = before.get(key, {}), after.get(key, {})
            for reference in sorted(left.keys() | right.keys()):
                if reference in left and reference in right and left[reference] == right[reference]:
                    continue
                change(
                    category,
                    reference,
                    left.get(reference),
                    right.get(reference),
                    sid,
                    (reference in left, reference in right),
                )
                if category == "source":
                    broad.add(sid)
                else:
                    evidence_changed.add((sid, reference))
        left = {key: value for key, value in before.get("input", {}).items() if key != "evidence"}
        right = {key: value for key, value in after.get("input", {}).items() if key != "evidence"}
        if left != right:
            change("input", "definition", left, right, sid)
            broad.add(sid)
        for key in ("role", "draft", "depends_on"):
            if before.get(key) != after.get(key):
                change(key, key, before.get(key), after.get(key), sid)

    # A fixed point also handles binding chains and terminates for dependency
    # cycles; schema/unknown-dependency diagnostics belong to the caller.
    while True:
        count = (len(affected), len(evidence_changed))
        for sid in sorted(new):
            before, after = old.get(sid, {}), new[sid]
            bindings = set(before.get("bindings", {}).items()) | set(
                after.get("bindings", {}).items()
            )
            for local, target in sorted(bindings):
                owner, separator, eid = target.partition("/")
                if separator and (owner in broad or (owner, eid) in evidence_changed):
                    cause = (
                        "owner source/input/section changed"
                        if owner in broad
                        else "evidence changed"
                    )
                    affect(sid, f"Bound evidence '{local}' uses '{target}': {cause}.")
                    evidence_changed.add((sid, local))
            dependencies = set(before.get("depends_on", [])) | set(after.get("depends_on", []))
            for dependency in sorted(dependencies):
                if dependency in affected or dependency in broad:
                    affect(
                        sid, f"Declared section dependency '{dependency}' changed or is affected."
                    )
        if count == (len(affected), len(evidence_changed)):
            break
    report["affected_sections"] = {sid: affected[sid] for sid in sorted(affected)}
    report["unchanged_sections"] = sorted(new.keys() - affected.keys())
    return report
