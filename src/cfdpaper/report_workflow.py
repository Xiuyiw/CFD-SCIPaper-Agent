"""A small JSON-report route into the existing source-bound manuscript workspace."""

from __future__ import annotations

import shutil
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
    workspace: Path | None = None,
    drafts: Path | None = None,
) -> Path:
    """Prepare once; on continuation reproject the retained raw JSON before assembly."""
    from cfdpaper.publication.report_writing import prepare_report_writing
    from cfdpaper.report_sources import project_reports

    if workspace is not None:
        if root is not None or cases is not None or quantities is not None or support_files:
            raise ValueError("Choose workspace continuation or new root/cases/quantities")
        root = Path(workspace).resolve()
        recipe = _read(root / "report.json")
        cases, quantities = recipe["cases"], recipe["quantities"]
        title, question, context = recipe["title"], recipe["question"], recipe["context"]
        support_files = [Path(name) for name in recipe["support_files"]]
    elif root is None or not cases or not quantities:
        raise ValueError("A new report task requires root, cases and quantities")
    if not title.strip() or not question.strip():
        raise ValueError("Declare the report task title and research question")
    root, output = Path(root).resolve(), Path(output)
    with _stage(output) as staged:
        projection_dir = staged / "projection"
        projection = project_reports(root, cases, quantities, projection_dir)
        retained_support = []
        for index, name in enumerate(support_files or []):
            source = (root / name).resolve()
            if not source.is_relative_to(root) or not source.is_file():
                raise ValueError(f"Support file is missing or outside the selected root: {name}")
            relative = Path("sources/support") / str(index) / source.name
            destination = projection_dir / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            projection["source_files"].append(relative.as_posix())
            retained_support.append((Path("projection") / relative).as_posix())
        _write(
            staged / "report.json",
            {
                "title": title,
                "question": question,
                "context": context,
                "cases": [
                    {"id": item["id"], "source": f"projection/sources/records/{item['id']}.json"}
                    for item in cases
                ],
                "quantities": quantities,
                "support_files": retained_support,
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
            from cfdpaper.publication.manuscript import assemble_manuscript

            manuscript = assemble_manuscript(prepared, Path(drafts), staged / "manuscript")
            export_formal_manuscript(manuscript, staged / "manuscript.docx")
            for sid, name in _read(prepared / "drafts.json").items():
                shutil.copyfile(manuscript / "sections" / sid / "draft.json", prepared / name)
            writing = _read(prepared / "report-writing.json")
            writing["pending_sections"] = []
            _write(prepared / "report-writing.json", writing)
        (staged / "CONTINUE.md").write_text(
            "# Continue this report task\n\n"
            "Read report.json, workspace/TASK.md and the retained raw reports "
            "under projection/sources/.\n"
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
