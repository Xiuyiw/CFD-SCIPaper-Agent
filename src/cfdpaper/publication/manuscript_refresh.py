"""Explicitly rebuild reading views from unchanged reviewed authoring material."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

from cfdpaper.publication.manuscript import assemble_manuscript
from cfdpaper.publication.manuscript_review import _copy_tree, _inside, _output
from cfdpaper.publication.section import _read, _stage


def _without_result_display(value):
    """Only computed result `value` is display; raw values and units stay exact."""
    if isinstance(value, list):
        return [_without_result_display(item) for item in value]
    if isinstance(value, dict):
        computed = "raw_value" in value and "calculation_id" in value
        return {
            key: _without_result_display(item)
            for key, item in value.items()
            if not (computed and key == "value")
        }
    return value


def _same(left, right, name):
    if left != right:
        raise ValueError(
            f"Display refresh requires unchanged authoring material: {name}. "
            "Reassemble changed sources/drafts separately and reconcile the review targets."
        )


def _calculated_bindings(state, sid):
    identities = set()
    for eid, target in state["sections"][sid]["bindings"].items():
        owner, key = target.split("/")
        record = state["sections"][owner]["evidence"][key]
        if record.get("result_ref") is not None:
            identities.add(eid)
    return identities


def _without_generated_display(record, identities, literature):
    result = deepcopy(record)
    evidence = result.get("evidence", [])
    records = evidence.values() if isinstance(evidence, dict) else evidence
    for item in records:
        if item["id"] in identities:
            item.pop("value", None)
            item.pop("unit", None)
        if item["id"] in literature:
            # Shared bibliography text is generated from the separately retained
            # reference metadata, support and source. Those remain exact below.
            item.pop("text", None)
    return result


def _authoring_state(state):
    result = _without_result_display(state)
    for sid, section in result["sections"].items():
        identities = _calculated_bindings(state, sid)
        literature = set(section["literature"])
        section["input"] = _without_generated_display(section["input"], identities, literature)
        section["evidence"] = _without_generated_display(section, identities, literature)[
            "evidence"
        ]
    return result


def _validate_refresh(old: Path, new: Path) -> None:
    old_state = _read(old / "writing-state.json")
    for name in ("writing-state.json", "numbering.json"):
        left, right = _read(old / name), _read(new / name)
        if name == "writing-state.json":
            left, right = map(_authoring_state, (left, right))
        _same(left, right, name)
    before, after = _read(old / "section.json"), _read(new / "section.json")
    for key in ("title", "keywords", "style", "section_objects"):
        _same(before.get(key), after.get(key), key)
    _same(
        _without_result_display(before["resolved_values"]),
        _without_result_display(after["resolved_values"]),
        "resolved raw values, units and sources",
    )
    names = set()
    manifest = _read(old / "manuscript-input.json")
    for entry in manifest["sections"]:
        sid = entry["section_id"]
        context = f"sections/{sid}/manuscript-context.json"
        _same(_read(old / context), _read(new / context), context)
        packet = Path("sections") / sid / "review-packet"
        # Historical packet copies detect changed figures and literature source text
        # even when the current authoring file has been modified in place.
        for member in (new / packet).rglob("*"):
            if not member.is_file():
                continue
            relative = member.relative_to(new).as_posix()
            if member.name in {"section.md", "review-prompt.md"}:
                continue
            if member.name == "input.json":
                identities = _calculated_bindings(old_state, sid)
                literature = set(old_state["sections"][sid]["literature"])
                _same(
                    _without_generated_display(
                        _read(_inside(old, relative)), identities, literature
                    ),
                    _without_generated_display(_read(member), identities, literature),
                    relative,
                )
            elif member.name == "bound-evidence.json":
                _same(
                    _without_result_display(_read(_inside(old, relative))),
                    _without_result_display(_read(member)),
                    relative,
                )
            else:
                names.add(relative)
    for folder in ("figures", "literature"):
        names.update(
            p.relative_to(new).as_posix() for p in (new / folder).rglob("*") if p.is_file()
        )
    if manifest.get("citation_style"):
        names.add(manifest["citation_style"])
        # A CSL change must not silently replace a reviewed bibliography.
        _same(before["references"], after["references"], "CSL bibliography")
    for name in sorted(names):
        _same(_inside(old, name).read_bytes(), _inside(new, name).read_bytes(), name)


def refresh_manuscript_display(candidate_dir: Path, output_dir: Path) -> Path:
    """Create a fresh reading copy, retaining inputs, raw results and target identities.

    This regenerates derived views; it does not merge later author edits or certify
    the scientific meaning of a formatter change. The reviewed candidate is untouched.
    """
    candidate_dir, output_dir = Path(candidate_dir), Path(output_dir)
    _output(candidate_dir, output_dir)
    with TemporaryDirectory(prefix="cfdpaper-display-") as temporary:
        rebuilt = assemble_manuscript(
            candidate_dir, candidate_dir / "drafts.json", Path(temporary) / "candidate"
        )
        _validate_refresh(candidate_dir, rebuilt)
        with _stage(output_dir) as staged:
            _copy_tree(rebuilt, staged)
    return output_dir
