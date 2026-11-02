"""Apply explicit host wording to existing research objects in a fresh workspace.

The host supplies scientific interpretation. This module only resolves existing
object identities, evidence ownership and author-text conflicts; it does not
infer prose, approve claims, reorder blocks or modify source results.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from cfdpaper.publication.document_blocks import paragraph_identity
from cfdpaper.publication.figure_tasks import _asset
from cfdpaper.publication.manuscript import _cross_references, _inputs, _object_numbers
from cfdpaper.publication.section import _Draft, _read, _references, _stage, _write


def _text(record, key):
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Revision requires nonblank {key}")
    return value


def _evidence_ids(refs, sid, entries, loaded):
    if not isinstance(refs, list) or any(not isinstance(ref, str) for ref in refs):
        raise ValueError("evidence_refs must list explicit owner/evidence references")
    result = []
    entry = entries[sid]
    bindings = entry.setdefault("evidence_bindings", {})
    current = {record.id for record in loaded[sid][1].evidence}
    for ref in refs:
        parts = ref.split("/")
        if len(parts) != 2 or parts[0] not in loaded:
            raise ValueError(f"Unknown evidence owner/reference: {ref}")
        owner, key = parts
        record = next((e for e in loaded[owner][1].evidence if e.id == key), None)
        if record is None:
            raise ValueError(f"Unknown evidence: {ref}")
        if owner == sid:
            alias = key
        else:
            if record.kind == "literature":
                raise ValueError("Use section-specific literature support, not borrowed citations")
            existing = [alias for alias, target in bindings.items() if target == ref]
            if key in existing:
                alias = key
            elif len(existing) == 1:
                alias = existing[0]
            elif existing:
                raise ValueError(f"Ambiguous evidence aliases for {ref} in section {sid}")
            else:
                alias = key
                if alias in current or (alias in bindings and bindings[alias] != ref):
                    raise ValueError(
                        f"Cannot replace author-owned local evidence or binding: {sid}/{alias}"
                    )
                bindings[alias] = ref
        if alias in result:
            raise ValueError(f"Duplicate evidence reference in section {sid}: {ref}")
        result.append(alias)
    return result


def _validate_tokens(text, *, evidence, allowed, figures, tables, equations, maths, numbers):
    # Qualified object tokens use the same resolver as whole-manuscript assembly.
    resolved, _ = _cross_references({"text": text}, numbers)
    text = resolved["text"]

    def check(match):
        kind, key = match.groups()
        names = {
            "value": allowed,
            "cite": allowed,
            "figure": figures,
            "table": tables,
            "equation": equations,
            "math": maths,
        }[kind]
        if key not in names:
            raise ValueError(f"Unknown or undeclared {kind}: {key}")
        if kind in {"value", "cite"}:
            record = evidence[key]
            if kind == "cite" and record.kind != "literature":
                raise ValueError(f"Citation {key} must be literature evidence")
            if kind == "value" and (
                record.result_ref is None
                and record.json_value_ref is None
                and (record.value is None or not record.value.strip())
            ):
                raise ValueError(f"Missing value for {key}")
        return ""

    remainder = re.sub(
        r"\{\{(value|cite|figure|table|equation|math):([A-Za-z0-9_.-]+)\}\}", check, text
    )
    if "{{" in remainder or "}}" in remainder:
        raise ValueError("Unknown or malformed draft token")


def _validate_draft(sid, raw, manifest, loaded, numbers):
    draft = _Draft.model_validate(raw)
    evidence = {e.id: e for e in loaded[sid][1].evidence}
    figures = {f.id for f in loaded[sid][1].figures}
    tables = {t.table_id for t in draft.tables}
    equations = {e.equation_id for e in draft.equations}
    if set(draft.captions) != figures or set(draft.image_observations) != figures:
        raise ValueError(f"Every figure requires a caption and image observation in {sid}")
    used_evidence, used_figures = set(), set()
    for paragraph in draft.paragraphs:
        _references(paragraph.evidence_ids, evidence)
        _references(paragraph.figure_ids, figures)
        used_evidence.update(paragraph.evidence_ids)
        used_figures.update(paragraph.figure_ids)
        _validate_tokens(
            paragraph.text,
            evidence=evidence,
            allowed=paragraph.evidence_ids,
            figures=paragraph.figure_ids,
            tables=tables,
            equations=equations,
            maths=paragraph.inline_math,
            numbers=numbers,
        )
    for caption in draft.captions.values():
        _validate_tokens(
            caption,
            evidence=evidence,
            allowed=evidence,
            figures=figures,
            tables=tables,
            equations=equations,
            maths={},
            numbers=numbers,
        )
    contract = next(c for c in manifest.spine.sections if c.section_id == sid)
    if not set(contract.required_claim_ids) <= used_evidence:
        raise ValueError(f"Required claim coverage missing in section {sid}")
    if not set(contract.required_figure_ids) <= used_figures:
        raise ValueError(f"Required figure coverage missing in section {sid}")


def apply_research_revision(workspace_dir: Path, proposal: dict, output_dir: Path) -> Path:
    """Write host-provided paragraph/caption replacements without replacing author files.

    ``paragraphs`` items require section_id, paragraph_id, before and text. Optional
    evidence_refs replace the paragraph's complete evidence list using explicit
    ``owner/evidence`` references; existing aliases are retained. Optional
    figure_ids replace its local figure list. Without those options the original
    lists stay unchanged. Cross-section figure/table/equation tokens retain their
    normal manuscript syntax.

    ``captions`` items require section_id, figure_id, before and text, with optional
    image_observation and observation_note. Every target must already exist and
    ``before`` must exactly equal its current source text. The fresh output is a
    continuing authoring workspace; the normal research build exports it.
    """
    root, output = Path(workspace_dir).resolve(), Path(output_dir).resolve()
    if output.is_relative_to(root) or root.is_relative_to(output):
        raise ValueError("Use a fresh output outside the source workspace")
    if not isinstance(proposal, dict) or set(proposal) - {"paragraphs", "captions"}:
        raise ValueError("Revision accepts only paragraphs and captions")
    patches = {key: proposal.get(key, []) for key in ("paragraphs", "captions")}
    if any(not isinstance(items, list) for items in patches.values()) or not any(patches.values()):
        raise ValueError("Revision requires nonempty paragraph or caption replacements")
    path = root / "manuscript-input.json"
    _, loaded, _, _, _ = _inputs(path)
    manifest = _read(path)
    entries = {entry["section_id"]: entry for entry in manifest["sections"]}
    mapping = _read(_asset(root, "drafts.json"))
    drafts = {sid: _read(_asset(root, name)) for sid, name in mapping.items()}
    for draft in drafts.values():
        occurrences = {}
        for paragraph in draft["paragraphs"]:
            text = paragraph["text"]
            paragraph.setdefault("paragraph_id", paragraph_identity(text, occurrences.get(text, 0)))
            occurrences[text] = occurrences.get(text, 0) + 1
    changed, seen = set(), set()
    for kind, items in patches.items():
        for patch in items:
            if not isinstance(patch, dict):
                raise ValueError("Each revision must be an object")
            allowed = {"section_id", "before", "text"} | (
                {"paragraph_id", "evidence_refs", "figure_ids", "inline_math"}
                if kind == "paragraphs"
                else {"figure_id", "image_observation", "observation_note"}
            )
            if set(patch) - allowed:
                raise ValueError(f"Unknown revision fields: {sorted(set(patch) - allowed)}")
            sid = _text(patch, "section_id")
            if sid not in entries or sid not in drafts:
                raise ValueError(f"Unknown section: {sid}")
            identity = _text(patch, "paragraph_id" if kind == "paragraphs" else "figure_id")
            target = (kind, sid, identity)
            if target in seen:
                raise ValueError(f"Duplicate revision target: {sid}/{identity}")
            seen.add(target)
            draft = drafts[sid]
            if kind == "paragraphs":
                matches = [p for p in draft["paragraphs"] if p.get("paragraph_id") == identity]
                if len(matches) != 1:
                    raise ValueError(f"Unknown or ambiguous paragraph: {sid}/{identity}")
                paragraph = matches[0]
                current = paragraph["text"]
            else:
                if identity not in draft["captions"]:
                    raise ValueError(f"Unknown figure caption: {sid}/{identity}")
                current = draft["captions"][identity]
            if _text(patch, "before") != current:
                raise ValueError(
                    f"Current text changed for {sid}/{identity}; reconcile author edits"
                )
            text = _text(patch, "text")
            if kind == "paragraphs":
                paragraph["text"] = text
                if "evidence_refs" in patch:
                    paragraph["evidence_ids"] = _evidence_ids(
                        patch["evidence_refs"], sid, entries, loaded
                    )
                if "figure_ids" in patch:
                    paragraph["figure_ids"] = patch["figure_ids"]
                if "inline_math" in patch:
                    if not isinstance(patch["inline_math"], dict):
                        raise ValueError("inline_math must map names to explicit math expressions")
                    for name, expression in patch["inline_math"].items():
                        prior = paragraph.get("inline_math", {}).get(name)
                        if prior is not None and prior != expression:
                            raise ValueError(
                                f"Existing author formula differs: {sid}/{identity}/{name}"
                            )
                    paragraph["inline_math"] = {
                        **paragraph.get("inline_math", {}),
                        **patch["inline_math"],
                    }
            else:
                draft["captions"][identity] = text
                if "image_observation" in patch:
                    draft["image_observations"][identity] = patch["image_observation"]
                if "observation_note" in patch:
                    draft.setdefault("observation_notes", {})[identity] = _text(
                        patch, "observation_note"
                    )
            changed.add(sid)
    # Stage only after all target/conflict checks. A failed reference check leaves
    # neither a partial output nor a changed author workspace.
    with _stage(output) as staged:
        shutil.copytree(root, staged, dirs_exist_ok=True)
        _write(staged / "manuscript-input.json", manifest)
        for sid in changed:
            _write(staged / mapping[sid], drafts[sid])
        validated, loaded, _, _, _ = _inputs(staged / "manuscript-input.json")
        numbers = _object_numbers(validated.spine, loaded, drafts)
        for sid in changed:
            _validate_draft(sid, drafts[sid], validated, loaded, numbers)
    return output
