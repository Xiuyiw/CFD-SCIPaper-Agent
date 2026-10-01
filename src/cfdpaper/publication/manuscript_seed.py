"""Thin path-and-draft bridge from selected section inputs to manuscript writing."""

from __future__ import annotations

import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from pydantic import Field

from cfdpaper.publication.literature import copy_literature
from cfdpaper.publication.manuscript import (
    _dependencies,
    _ManuscriptInput,
    _SectionInput,
    prepare_manuscript,
)
from cfdpaper.publication.section import (
    _check_comparison_definition,
    _copy_figures,
    _copy_sources,
    _Draft,
    _Figure,
    _fresh,
    _read,
    _stage,
    _write,
)


class _SeedSection(_SectionInput):
    draft: str | None = None


class _SeedInput(_ManuscriptInput):
    sections: list[_SeedSection] = Field(min_length=1)


def _source(base: Path, value: str) -> Path:
    """Only outline entry paths are flexible; existing section contracts stay intact."""
    if not value.strip():
        raise ValueError("Outline paths must not be blank")
    path = (base / value).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Outline dependency not found: {path}")
    return path


def _copy_section_input(source: Path, destination: Path):
    """Copy declared dependencies without prematurely resolving manuscript aliases."""
    raw = _read(source)
    source_files = list(raw.get("source_files", []))
    source_files.extend(item["source"] for item in raw.get("table_calculations", []))
    source_files.extend(
        _check_comparison_definition(source.parent, item["definition_source"])
        for item in raw.get("result_comparisons", [])
    )
    resources = SimpleNamespace(
        source_files=list(dict.fromkeys(source_files)),
        figures=[_Figure.model_validate(item) for item in raw.get("figures", [])],
    )
    destination.mkdir(parents=True)
    _copy_sources(resources, source.parent, destination)
    _copy_figures(resources, source.parent, destination)
    # Preserve the supplied objects and all result IDs; only asset paths change.
    raw["source_files"] = resources.source_files
    for original, copied in zip(raw.get("figures", []), resources.figures, strict=True):
        original["path"] = copied.path
    _write(destination / "input.json", raw)
    # Existing prepared inputs use these to identify injected evidence correctly.
    for name in ("manuscript-context.json", "literature-support.json"):
        if (source.parent / name).is_file():
            shutil.copyfile(source.parent / name, destination / name)


def prepare_manuscript_seed(outline_path: Path, output_dir: Path) -> Path:
    """Prepare an existing-format manuscript workspace, never manuscript prose.

    The outline has the existing manuscript-input fields, plus optional ``draft``
    on each section. ``input``, ``draft``, ``literature`` and ``citation_style``
    paths are absolute or relative to the outline (including parent paths).
    Dependencies inside section/literature inputs retain their existing formats.
    ``drafts.json`` maps only supplied drafts; ``drafts-template.json`` gives all
    target paths. Missing drafts remain pending and are not fabricated.
    """
    outline_path, output_dir = Path(outline_path), Path(output_dir)
    _fresh(output_dir)
    data = _SeedInput.model_validate(_read(outline_path))
    ids = [entry.section_id for entry in data.sections]
    seen = set()
    for index, sid in enumerate(ids):
        if sid.casefold() in seen:
            raise ValueError(f"Duplicate section ID at sections[{index}]: {sid}")
        seen.add(sid.casefold())
    _dependencies({entry.section_id: entry for entry in data.sections})
    base = outline_path.parent
    sources = {entry.section_id: _source(base, entry.input) for entry in data.sections}
    drafts = {
        entry.section_id: _source(base, entry.draft)
        for entry in data.sections
        if entry.draft is not None
    }
    for source in drafts.values():
        _Draft.model_validate(_read(source))

    with TemporaryDirectory(prefix="cfdpaper-seed-") as temporary:
        root = Path(temporary)
        manifest = data.model_dump(exclude={"sections"})
        entries = []
        for entry in data.sections:
            relative = f"inputs/{entry.section_id}/input.json"
            _copy_section_input(sources[entry.section_id], (root / relative).parent)
            entries.append({**entry.model_dump(exclude={"draft"}), "input": relative})
        manifest["sections"] = entries
        if data.literature:
            copy_literature(_source(base, data.literature), root / "literature")
            manifest["literature"] = "literature/literature.json"
        if data.citation_style:
            shutil.copyfile(_source(base, data.citation_style), root / "citation-style.csl")
            manifest["citation_style"] = "citation-style.csl"
        source = root / "manuscript-input.json"
        _write(source, manifest)
        with _stage(output_dir) as staged:
            workspace = prepare_manuscript(source, staged / "workspace")
            mapping = {}
            for sid, draft in drafts.items():
                relative = f"sections/{sid}/draft.json"
                shutil.copyfile(draft, workspace / relative)
                mapping[sid] = relative
            _write(workspace / "drafts.json", mapping)
            pending = [sid for sid in ids if sid not in drafts]
            task = workspace / "TASK.md"
            task.write_text(
                task.read_text(encoding="utf-8")
                + "\n## Seed draft status\n\n"
                + "drafts.json contains only supplied drafts, preserved without rewriting. "
                + "Use it with the existing writing-context command. Add each completed "
                + "section to that map before assembly.\n\n"
                + (
                    "Pending host writing: " + ", ".join(pending) + ".\n"
                    if pending
                    else "All sections have supplied drafts; assembly and review remain.\n"
                ),
                encoding="utf-8",
            )
            for child in workspace.iterdir():
                child.rename(staged / child.name)
            workspace.rmdir()
    return output_dir
