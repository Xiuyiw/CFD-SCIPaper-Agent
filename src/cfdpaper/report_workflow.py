"""A small JSON-report route into the existing source-bound manuscript workspace."""

from __future__ import annotations

import shutil
from copy import deepcopy
from pathlib import Path

from cfdpaper.publication.section import _read, _stage, _write


def report_workflow(
    output: Path,
    *,
    root: Path | None = None,
    cases: list[dict] | None = None,
    quantities: list[dict] | None = None,
    title: str = "",
    question: str = "",
    context: str = "",
    support_files: list[Path] | None = None,
    derived: list[dict] | None = None,
    formulas: dict | None = None,
    workspace: Path | None = None,
    drafts: Path | None = None,
) -> Path:
    """Prepare once; on continuation reproject the retained raw JSON before assembly."""
    from cfdpaper.publication.report_writing import prepare_report_writing, report_context
    from cfdpaper.report_sources import project_reports

    if workspace is not None:
        if (
            root is not None
            or cases is not None
            or quantities is not None
            or support_files
            or derived is not None
            or formulas is not None
        ):
            raise ValueError("Choose workspace continuation or new root/cases/quantities")
        root = Path(workspace).resolve()
        recipe = _read(root / "report.json")
        cases, quantities = recipe["cases"], recipe["quantities"]
        title, question, context = recipe["title"], recipe["question"], recipe["context"]
        support_files = [Path(name) for name in recipe["support_files"]]
        derived, formulas = recipe.get("derived", []), recipe.get("formulas", {})
    elif root is None or not cases or not quantities:
        raise ValueError("A new report task requires root, cases and quantities")
    if not title.strip() or not question.strip():
        raise ValueError("Declare the report task title and research question")
    root, output = Path(root).resolve(), Path(output)
    derived, formulas = deepcopy(derived or []), deepcopy(formulas or {})

    # These are explicit file locators, not prose/path heuristics.
    def split_locator(value):
        for separator in (":L", "#"):
            if separator in value:
                path, tail = value.rsplit(separator, 1)
                return path, separator + tail
        return value, ""

    selected_support = [str(name) for name in support_files or []]
    selected_support += [split_locator(item["definition_source"])[0] for item in derived]
    selected_support += [split_locator(item["source"])[0] for item in formulas.values()]
    with _stage(output) as staged:
        projection_dir = staged / "projection"
        projection = project_reports(root, cases, quantities, projection_dir)
        retained_support = []
        support_map = {}
        for index, name in enumerate(dict.fromkeys(selected_support)):
            source = (root / name).resolve()
            if not source.is_relative_to(root) or not source.is_file():
                raise ValueError(f"Support file is missing or outside the selected root: {name}")
            relative = Path("sources/support") / str(index) / source.name
            destination = projection_dir / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            projection["source_files"].append(relative.as_posix())
            support_map[name] = relative.as_posix()
            retained_support.append((Path("projection") / relative).as_posix())
        for item in derived:
            name, suffix = split_locator(item["definition_source"])
            item["definition_source"] = support_map[name] + suffix
        for item in formulas.values():
            name, suffix = split_locator(item["source"])
            item["source"] = support_map[name] + suffix
        projection.update(derived=derived, formulas=formulas)
        retained_cases = deepcopy(projection["retained_cases"])
        for case in retained_cases:
            case["source"] = "projection/" + case["source"]
            case["sources"] = {
                key: "projection/" + name for key, name in case.get("sources", {}).items()
            }
        retained_derived, retained_formulas = deepcopy(derived), deepcopy(formulas)
        for item in retained_derived:
            item["definition_source"] = "projection/" + item["definition_source"]
        for item in retained_formulas.values():
            item["source"] = "projection/" + item["source"]
        _write(
            staged / "report.json",
            {
                "title": title,
                "question": question,
                "context": context,
                "cases": retained_cases,
                "quantities": quantities,
                "support_files": retained_support,
                "derived": retained_derived,
                "formulas": retained_formulas,
            },
        )
        prepared = prepare_report_writing(
            projection_dir,
            projection,
            staged / "workspace",
            title=title,
            question=question,
            context=context,
        )
        if drafts is not None:
            from cfdpaper.publication.formal_export import export_formal_manuscript
            from cfdpaper.publication.manuscript import _relative, assemble_manuscript
            from cfdpaper.publication.report_math import apply_report_formulas

            draft_map = _read(Path(drafts))
            current_map = _read(prepared / "drafts.json")
            if not isinstance(draft_map, dict) or draft_map.keys() != current_map.keys():
                raise ValueError("Draft section IDs must exactly match the report sections")
            for sid, name in draft_map.items():
                source_draft = _relative(Path(drafts).parent, name)
                original = _read(source_draft)
                amended = apply_report_formulas(original, formulas)
                if amended == original:
                    shutil.copyfile(source_draft, prepared / current_map[sid])
                else:
                    _write(prepared / current_map[sid], amended)
            manuscript = assemble_manuscript(
                prepared, prepared / "drafts.json", staged / "manuscript"
            )
            export_formal_manuscript(manuscript, staged / "manuscript.docx")
            for sid, name in _read(prepared / "drafts.json").items():
                shutil.copyfile(manuscript / "sections" / sid / "draft.json", prepared / name)
            writing = _read(prepared / "report-writing.json")
            writing["pending_sections"] = []
            _write(prepared / "report-writing.json", writing)
        _write(
            prepared / "report-context.json",
            report_context(_read(prepared / "report-writing.json")),
        )
        (staged / "CONTINUE.md").write_text(
            "# Continue this report task\n\n"
            "Read workspace/report-context.json first, then workspace/TASK.md and report.json. "
            "Full metric details remain in workspace/report-writing.json; retained raw reports "
            "are under projection/sources/.\n"
            "Fill workspace/sections/{methods,results,discussion}/draft.json using its existing "
            "template and tokens; workspace/drafts.json maps the three sections.\n\n"
            "Continue with report_task(workspace=THIS_DIRECTORY, drafts=THIS_DIRECTORY/"
            "workspace/drafts.json, output=A_FRESH_DIRECTORY). This re-reads retained JSON, "
            "recomputes the bound values and exports the supplied prose. Do not repeat the "
            "old proposal workflow or hard-code metric values. Source changes may require "
            "revising the interpretation, not only its numbers. Keep author originals.\n",
            encoding="utf-8",
        )
    return output
