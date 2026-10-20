"""Recover a generated author DOCX into an isolated, continuing manuscript.

The return is merged with a current scientific candidate, not pasted over its
resolved numbers. Conflicts and ordinary comments remain actionable for the host.
"""

from __future__ import annotations

import shutil
import tempfile
from collections import defaultdict
from copy import deepcopy
from pathlib import Path

from cfdpaper.publication.document_blocks import (
    apply_author_edits,
    build_document,
    paragraph_identity,
    source_definition_state,
)
from cfdpaper.publication.section import _read, _stage, _write


def _current_document(directory, profile):
    data = _read(directory / "section.json")
    document = build_document(data, profile=profile)
    if (directory / "author-edits.json").is_file():
        apply_author_edits(document, _read(directory / "author-edits.json"))
    return document


def _continuing_copy(candidate, destination):
    """Restore legacy copied-asset locators from exact retained figure identities."""
    working = Path(shutil.copytree(candidate, destination))
    for source in _draft_locations(working).values():
        local = source.parent
        data = _read(local / "input.json")
        copied = {f["id"]: f["path"] for f in _read(local / "section.json")["figures"]}
        changed = False
        for figure in data["figures"]:
            if not (local / figure["path"]).is_file():
                target = copied.get(figure["id"])
                if target and (local / target).is_file():
                    figure["path"] = target
                    changed = True
        if changed:
            _write(local / "input.json", data)
    return working


def prepare_author_manuscript(
    candidate_dir: Path, output_dir: Path, *, profile="research", template_path=None
) -> Path:
    """Upgrade stable source IDs in a new copy and produce the author's Word file."""
    from cfdpaper.publication.formal_export import export_formal_manuscript
    from cfdpaper.publication.manuscript import _copy_workflow_skills, assemble_manuscript

    candidate_dir, output_dir = map(Path, (candidate_dir, output_dir))
    if output_dir.resolve().is_relative_to(candidate_dir.resolve()):
        raise ValueError("Author workspace must be outside its source candidate")
    with tempfile.TemporaryDirectory(prefix="cfdpaper-author-") as temporary:
        root = Path(temporary)
        source = _continuing_copy(candidate_dir, root / "source")
        data = _read(source / "section.json")
        missing = any(
            "source_text" not in p for p in data["paragraphs"] if "section_heading" not in p
        )
        current = (
            assemble_manuscript(source, source / "drafts.json", root / "normalized")
            if missing
            else source
        )
        document = _current_document(current, profile)
        working = Path(shutil.copytree(current, root / "working"))
        _apply_blocks(working, document["blocks"])
        candidate = assemble_manuscript(working, working / "drafts.json", root / "candidate")
        with _stage(output_dir) as staged:
            shutil.copytree(candidate, staged / "candidate")
            _copy_workflow_skills(staged)
            export_formal_manuscript(
                staged / "candidate",
                staged / "manuscript.docx",
                profile=profile,
                template_path=template_path,
            )
            export_formal_manuscript(
                staged / "candidate", staged / "manuscript.md", profile=profile
            )
            (staged / "READ_ME.md").write_text(
                "# Author manuscript\n\nEdit manuscript.docx in Word; keep its original here "
                "and save your return under a new name. Normal prose, captions, bold/italic "
                "and comments are supported. Numerical bindings, formulas and image contents "
                "are reconciled with source definitions rather than silently changed. "
                "The candidate/ directory keeps the "
                "continuing source drafts and stable identities.\n\n"
                "For host instructions read "
                "skills/cfd-evidence-writing/references/author-word.md.\n\n"
                "Return with cfdpaper author --package candidate "
                "--return-docx YOUR_RETURN.docx --output NEW_RETURN. "
                "If source data have changed, pass the newly assembled candidate as --package.\n",
                encoding="utf-8",
            )
    return output_dir


def _definitions(state):
    """Use the existing writing-state facts, not inferred semantics or embeddings."""
    state = source_definition_state(state)
    sections = {}
    for sid, item in state.get("sections", {}).items():
        sections[sid] = {
            "calculations": item.get("input", {}).get("table_calculations", []),
            "comparisons": item.get("input", {}).get("result_comparisons", []),
            "scientific": item.get("scientific_context", {}),
            "bindings": item.get("bindings", {}),
            "evidence": item.get("evidence", {}),
        }
    return {
        "sections": sections,
        "terms": state.get("terms", {}),
        "context": state.get("context", ""),
    }


def describe_author_refresh(baseline, current, *, current_source_state=None):
    """Distinguish mechanical display refresh from interpretation work."""
    previous = {b["id"]: b for b in baseline["blocks"]}
    changes = []
    definitions = _definitions(baseline.get("source_state", {}))
    now_definitions = _definitions(current_source_state or {})
    changed_sections = {
        sid
        for sid in set(definitions["sections"]) | set(now_definitions["sections"])
        if definitions["sections"].get(sid) != now_definitions["sections"].get(sid)
    }
    shared_changed = any(definitions[k] != now_definitions[k] for k in ("terms", "context"))
    for block in current["blocks"]:
        old = previous.get(block["id"])
        if old is None:
            changes.append(
                {
                    "block_id": block["id"],
                    "section_id": block["section_id"],
                    "category": "new-content",
                }
            )
            continue
        definition_change = shared_changed or block["section_id"] in changed_sections

        def canonical(text):
            return text.replace("\u00a0", " ").replace("\u2060", "").replace("−", "-")

        before = {s["token"]: canonical(s["text"]) for s in old.get("spans", [])}
        after = {s["token"]: canonical(s["text"]) for s in block.get("spans", [])}
        if definition_change:
            category = "definition"
        elif old["text"] != block["text"]:
            category = "text"
        elif before != after:
            category = "numeric-display"
        elif old.get("content") != block.get("content"):
            category = "object-or-format"
        else:
            continue
        changes.append(
            {
                "block_id": block["id"],
                "section_id": block["section_id"],
                "category": category,
                "before": before,
                "after": after,
                "interpretation_required": category in {"definition", "text", "numeric-display"},
            }
        )
    return changes


def _draft_locations(candidate):
    mapping = _read(candidate / "drafts.json")
    root = candidate.resolve()
    locations = {}
    for sid, name in mapping.items():
        path = (root / name).resolve()
        if not path.is_relative_to(root):
            raise ValueError("Draft path must stay in its manuscript directory")
        locations[sid] = path
    return locations


def _apply_blocks(working, blocks):
    locations = _draft_locations(working)
    drafts = {sid: _read(path) for sid, path in locations.items()}
    for draft in drafts.values():
        counts = defaultdict(int)
        for paragraph in draft["paragraphs"]:
            text = paragraph["text"]
            paragraph.setdefault("paragraph_id", paragraph_identity(text, counts[text]))
            counts[text] += 1
    compiled = _read(working / "section.json")
    by_source = {}
    for p in compiled["paragraphs"]:
        if "section_heading" in p:
            continue
        by_source[p["section_id"], p["paragraph_id"]] = p
    ordered = defaultdict(list)
    edits = {}
    manifest = _read(working / "manuscript-input.json")
    for block in blocks:
        sid, kind, local_id = block["section_id"], block["kind"], block["local_id"]
        if kind == "keywords":
            manifest["keywords"] = [
                part.strip() for part in block["text"].split(";") if part.strip()
            ]
        if sid not in drafts:
            continue
        draft = drafts[sid]
        if kind == "paragraph":
            original = by_source.get((sid, local_id), {})
            record = {
                "paragraph_id": local_id,
                "text": block["text"],
                "evidence_ids": list(original.get("evidence_ids", [])),
                "figure_ids": list(original.get("figure_ids", [])),
                "inline_math": deepcopy(original.get("inline_math", {})),
            }
            # Combined evidence/figure IDs are display identities. Source IDs come
            # from the retained local draft, indexed by its persisted identity.
            local_original = next(
                (p for p in draft["paragraphs"] if p.get("paragraph_id") == local_id), None
            )
            if local_original is not None:
                record = {
                    **deepcopy(local_original),
                    "paragraph_id": local_id,
                    "text": block["text"],
                }
            elif original:
                matches = [p for p in draft["paragraphs"] if p["text"] == original["source_text"]]
                if len(matches) == 1:
                    record = {
                        **deepcopy(matches[0]),
                        "paragraph_id": local_id,
                        "text": block["text"],
                    }
                else:
                    raise ValueError(f"No unique retained source paragraph for {local_id}")
            ordered[sid].append(record)
        elif kind == "heading":
            draft["title"] = block["text"]
        elif kind == "caption":
            draft["captions"][local_id] = block["text"]
        elif kind == "table":
            table = next(t for t in draft["tables"] if t["table_id"] == local_id)
            compiled_table = next(
                t for t in compiled["tables"] if t["table_id"] == block["content"]["table_id"]
            )
            if block["content"]["columns"] != compiled_table["columns"]:
                if any("{{" in column for column in table["columns"]):
                    raise ValueError(
                        "A bound table heading must be edited in its source definition"
                    )
                table["columns"] = block["content"]["columns"]
        visual = {
            key: deepcopy(block[key])
            for key in ("formatting", "paragraph_format", "layout")
            if key in block
        }
        if visual:
            visual["formatting_source_text"] = block.get(
                "formatting_source_text", block.get("rendered_text", "")
            )
            edits[block["id"]] = visual
    for sid, draft in drafts.items():
        draft["paragraphs"] = ordered[sid]
        draft["block_order"] = [
            f"{b['kind']}:{b['local_id']}"
            for b in blocks
            if b["section_id"] == sid and b["kind"] in {"paragraph", "figure", "equation", "table"}
        ]
        _write(locations[sid], draft)
    _write(working / "manuscript-input.json", manifest)
    return edits


def import_author_manuscript(author_path: Path, current_dir: Path, output_dir: Path) -> Path:
    """Create an editable new candidate and localized conflict/host action records.

    The original DOCX and current scientific candidate are never modified. A
    conflicted object retains the current scientific version; its author version
    remains in the preserved original and in ``author-return.json``.
    """
    from cfdpaper.publication.manuscript import _copy_workflow_skills, assemble_manuscript
    from cfdpaper.publication.word_return import merge_word_blocks, read_word_return

    author_path, current_dir, output_dir = map(Path, (author_path, current_dir, output_dir))
    if output_dir.resolve().is_relative_to(current_dir.resolve()):
        raise ValueError("Author output must be outside the current candidate")
    returned = read_word_return(author_path)
    baseline = returned["state"]
    with tempfile.TemporaryDirectory(prefix="cfdpaper-author-") as temporary:
        workroot = Path(temporary)
        # Older assembled candidates can be upgraded once without changing their
        # retained source files. No native solver or source result is written.
        source = _continuing_copy(current_dir, workroot / "source")
        data = _read(source / "section.json")
        needs_upgrade = any(
            "source_text" not in p for p in data["paragraphs"] if "section_heading" not in p
        )
        normalized = (
            assemble_manuscript(source, source / "drafts.json", workroot / "normalized")
            if needs_upgrade
            else source
        )
        current = _current_document(normalized, baseline.get("profile", "research"))
        if baseline["title"] != current["title"]:
            raise ValueError("Author DOCX title does not match this manuscript")
        base_sections = {b["section_id"] for b in baseline["blocks"] if b["kind"] == "heading"}
        now_sections = {b["section_id"] for b in current["blocks"] if b["kind"] == "heading"}
        if base_sections != now_sections:
            raise ValueError("Author DOCX section identities do not match this manuscript")
        author_blocks = returned["blocks"][:]
        present = {b["id"] for b in author_blocks}
        # An accidentally removed SDT is unresolved, not permission to delete prose.
        author_blocks.extend(b for b in baseline["blocks"] if b["id"] not in present)
        merged = merge_word_blocks(baseline["blocks"], author_blocks, current["blocks"])
        conflicts = returned["conflicts"] + merged["conflicts"]
        base_map = {b["id"]: b for b in baseline["blocks"]}
        for block in author_blocks:
            if (
                block["kind"] == "reference"
                and block["id"] in base_map
                and block["text"] != base_map[block["id"]]["text"]
            ):
                conflicts.append(
                    {
                        "type": "bibliography_source_edit_required",
                        "block_id": block["id"],
                        "author": block["text"],
                        "baseline": base_map[block["id"]]["text"],
                    }
                )
        blocked = {c["block_id"] for c in conflicts if c.get("block_id")}
        current_map = {b["id"]: b for b in current["blocks"]}
        merged_blocks = [
            deepcopy(current_map.get(b["id"], b)) if b["id"] in blocked else b
            for b in merged["blocks"]
        ]
        working = Path(shutil.copytree(normalized, workroot / "working"))
        visual = _apply_blocks(working, merged_blocks)
        assembled = assemble_manuscript(working, working / "drafts.json", workroot / "candidate")
        current_source = _read(normalized / "writing-state.json")
        changes = describe_author_refresh(baseline, current, current_source_state=current_source)
        with _stage(output_dir) as staged:
            shutil.copytree(assembled, staged / "candidate")
            _copy_workflow_skills(staged)
            shutil.copyfile(author_path, staged / "author-original.docx")
            _write(staged / "author-return.json", returned)
            _write(
                staged / "merge.json",
                {
                    "baseline_id": returned["baseline_id"],
                    "conflicts": conflicts,
                    "scientific_changes": changes,
                    "status": "needs-resolution" if conflicts else "merged-candidate",
                },
            )
            comments = returned["comments"]
            _write(
                staged / "candidate" / "author-edits.json", {"blocks": visual, "comments": comments}
            )
            _write(staged / "comments.json", comments)
            from cfdpaper.publication.formal_export import export_formal_manuscript

            export_formal_manuscript(
                staged / "candidate",
                staged / "manuscript.docx",
                profile=baseline.get("profile", "research"),
            )
            export_formal_manuscript(
                staged / "candidate",
                staged / "manuscript.md",
                profile=baseline.get("profile", "research"),
            )
            lines = [
                "# Author manuscript return",
                "",
                "The original author DOCX is preserved. "
                "A new scientific candidate is in candidate/.",
                "",
            ]
            if conflicts:
                lines += [
                    "## Resolve these objects before final export",
                    "",
                    *[f"- {c.get('block_id') or 'document'}: {c['type']}" for c in conflicts],
                    "",
                ]
            if changes:
                lines += [
                    "## Revisit the affected interpretation",
                    "",
                    *[f"- {c['section_id']}: {c['category']} ({c['block_id']})" for c in changes],
                    "",
                ]
            if comments:
                lines += [
                    "## Author comments",
                    "",
                    *[f"- {c.get('block_id') or 'document'}: {c['text']}" for c in comments],
                    "",
                ]
            lines += [
                "Comments are unresolved suggestions, not approvals. Source changes may require "
                "host revisions to Methods, captions, abstract and conclusions; "
                "numerical rebinding is not a rewritten mechanism.",
                "",
            ]
            (staged / "CONTINUE.md").write_text("\n".join(lines), encoding="utf-8")
    return output_dir
