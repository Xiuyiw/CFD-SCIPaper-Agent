"""Task-sized host calls over the existing business APIs, without an AI transport.

Inputs identify their workspace explicitly. Returned paths identify existing artifacts;
large source-record lists stay in the full reports, not in the host response. These
functions do not infer physical definitions or certify scientific interpretations.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _existing(root: Path, names: dict[str, str]) -> dict[str, str]:
    return {
        key: str((root / name).resolve()) for key, name in names.items() if (root / name).exists()
    }


def _response(
    task: str, root: Path, artifacts: dict, context: dict, missing=None
) -> dict[str, Any]:
    return {
        "task": task,
        "root": str(root.resolve()),
        "artifacts": artifacts,
        "context": context,
        "missing_items": missing or [],
    }


def _scalar_context(result: dict) -> dict:
    """Keep physical/scalar fields; full row/face provenance remains at its artifact."""
    records = {"array_indices", "csv_records", "reference_array_indices", "reference_csv_records"}
    return {
        key: [_scalar_context(parent) for parent in value] if key == "supporting_results" else value
        for key, value in result.items()
        if key not in records
    }


def inspect_materials(
    root: Path,
    *,
    paths: list[Path] | None = None,
    find: list[str] | None = None,
    definitions: list[str] | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Read bounded material profiles, literal matches, or exact Python definitions.

    Source files are read, never executed. A definition read requires selected
    Python paths; missing definitions and unsupported files remain explicit issues.
    """
    from cfdpaper.material_search import search_materials
    from cfdpaper.materials import profile_materials, read_material_definitions

    root = Path(root)
    if find is not None and definitions is not None:
        raise ValueError("Choose literal find or exact definitions, not both")
    if definitions is not None:
        if not paths:
            raise ValueError("Exact definitions require selected Python paths")
        context = read_material_definitions(root, definitions, paths=paths)
        task = "materials-definitions"
    elif find is not None:
        context = search_materials(root, find, paths=paths, limit=limit)
        task = "materials-search"
    else:
        context = profile_materials(root, paths=paths)
        task = "materials-profile"
    return _response(task, root, {}, context, context.get("issues", []))


def prepare_analysis_task(
    root: Path, output: Path, *, question: str = "", paths: list[Path] | None = None
) -> dict[str, Any]:
    """Prepare the existing portable material task; the host chooses the analysis.

    Only selected/bounded materials are copied. The question is not a supplied
    scientific answer, and no solver, model provider, or source script is run.
    Returned profiles retain columns/units and exact full-record pointers; source
    excerpts and row previews stay in artifacts.materials rather than the tool chat.
    """
    from cfdpaper.analysis_suggestions import prepare_analysis

    result = prepare_analysis(Path(root), Path(output), question=question, paths=paths)
    materials = _read(result)
    context = {
        key: value
        for key, value in materials.items()
        if key not in {"tables", "documents", "figures", "arrays"}
    }
    context["material_counts"] = {}
    for category in ("tables", "documents", "figures", "arrays"):
        records = materials.get(category, [])
        context["material_counts"][category] = len(records)
        context[category] = [
            {
                **{
                    key: value
                    for key, value in record.items()
                    if key not in {"excerpt", "preview", "preview_rows"}
                },
                "source_record": {
                    "path": str(result.resolve()),
                    "json_pointer": f"/{category}/{i}",
                },
            }
            if isinstance(record, dict)
            else record
            for i, record in enumerate(records)
        ]
    missing = list(materials.get("issues", []))
    if not materials.get("tables") and not materials.get("arrays"):
        missing.append(
            {
                "code": "no-analysis-table",
                "message": "No readable CSV/NPZ table was selected. Read the located raw "
                "records and create a tabular projection with a source-reading recipe, explicit "
                "units/support and file/key provenance, or select an existing export; "
                "no new solver run is required.",
            }
        )
    artifacts = _existing(
        result.parent,
        {
            "materials": "materials.json",
            "task": "host-task.md",
            "proposal_example": "proposal-example.json",
            "proposal_schema": "proposal-schema.json",
        },
    )
    return _response("analysis-prepare", result.parent, artifacts, context, missing)


def run_analysis_task(
    package: Path, proposal: Path, candidate_id: str, output: Path
) -> dict[str, Any]:
    """Compute the selected analysis and prepare its figures and host-writing package.

    Return exact metric values/units and declared definitions, with full source
    records located in table_results. This is not a scientific approval decision.
    Adapt prepare_analysis_task's proposal_example/schema, then select its ID here.
    Use the returned writing_package/input.json and draft_template for writing;
    they already carry calculated result_ref bindings. Do not retype the values.
    """
    from cfdpaper.analysis_suggestions import compile_analysis
    from cfdpaper.publication.analysis_section import build_analysis_section
    from cfdpaper.publication.section import _stage
    from cfdpaper.publication.table_evidence import resolve_table_result

    output = Path(output)
    with _stage(output) as staged:
        compiled = compile_analysis(
            Path(package), Path(proposal), candidate_id, staged / "compiled"
        )
        build_analysis_section(compiled, staged / "section-input")
    result = output / "compiled" / "analysis-input.json"
    payload = _read(result)
    reports_path = result.parent / "table-results.json"
    reports = _read(reports_path)
    artifacts = _existing(
        output,
        {
            "analysis_input": "compiled/analysis-input.json",
            "table_results": "compiled/table-results.json",
            "selected_analysis": "compiled/selected-analysis.json",
            "compiled": "compiled",
            "section_input": "section-input/input.json",
            "writing_package": "section-input/writing",
            "writing_task": "section-input/writing/TASK.md",
            "draft_template": "section-input/writing/draft-template.json",
            "figures": "section-input/figures",
            "plot_script": "section-input/plot_analysis.py",
        },
    )
    metrics = []
    for evidence in payload["evidence"]:
        reference = evidence.get("result_ref")
        if reference is None:
            continue
        resolved = resolve_table_result(reports, **reference)
        index = next(
            i for i, report in enumerate(reports) if report["id"] == reference["calculation_id"]
        )
        metrics.append(
            {
                "id": evidence["id"],
                "text": evidence["text"],
                "resolved": _scalar_context(resolved),
                "result_details": {
                    "path": str(reports_path.resolve()),
                    "json_pointer": f"/{index}",
                },
            }
        )
    selected = _read(result.parent / "selected-analysis.json")
    return _response(
        "analysis-run",
        output,
        artifacts,
        {
            "selected_analysis": selected,
            "metrics": metrics,
            "source_files": payload["source_files"],
            "source_root": str(result.parent.resolve()),
            "writing_input": _read(output / "section-input/input.json"),
        },
        selected.get("missing_questions", []),
    )


def _report_context(writing: dict) -> dict:
    keys = {
        "evidence_id",
        "case_id",
        "quantity",
        "label",
        "operation",
        "value",
        "raw_value",
        "unit",
        "domain",
        "comparison_scope",
        "definition",
        "reference_evidence_id",
        "comparison_evidence_id",
        "denominator",
    }
    compact = []
    for index, metric in enumerate(writing["metrics"]):
        row = {key: value for key, value in metric.items() if key in keys}
        if "parent_support" in metric:
            row["parent_support"] = [
                {key: value for key, value in parent.items() if key != "original_sources"}
                for parent in metric["parent_support"]
            ]
        row["details_pointer"] = f"/metrics/{index}"
        compact.append(row)
    return {**writing, "metrics": compact}


def report_task(
    output: Path,
    *,
    root: Path | None = None,
    cases: list[dict[str, Any]] | None = None,
    quantities: list[dict[str, Any]] | None = None,
    title: str = "",
    question: str = "",
    context: str = "",
    support_files: list[Path] | None = None,
    derived: list[dict[str, Any]] | None = None,
    formulas: dict[str, Any] | None = None,
    workspace: Path | None = None,
    drafts: Path | None = None,
) -> dict[str, Any]:
    """Read JSON reports and prepare bound Methods/Results/Discussion; no proposal needed.

    New task: root plus cases [{"id":"A","source":"A.json"}] and quantities.
    Select a scalar: {"id":"T","label":"Mean temperature","unit":"K",
    "domain":"wall area-weighted report","pointer":"/mean"}.
    Select a difference: {"id":"dp","label":"Inlet minus outlet","unit":"Pa",
    "output_unit":"kPa","domain":"same static-pressure/area-average operator",
    "comparison":"/pressure/inlet","reference":"/pressure/outlet"}.
    Pointers address actual JSON numbers. The host chooses their physical meaning.
    Cases may supply named sources (e.g. setup); a quantity selects source_key.
    A pointer may map case IDs to exact paths in a shared reference JSON.
    Optional derived compares base evidence IDs via reference/comparison, field
    (difference, ratio, relative_change or relative_reduction), domain,
    comparison_scope and definition_source (relative file:Lx-Ly). percentage=true
    multiplies relative change by 100 once, using reference as denominator.
    Optional formulas maps IDs to {expression: existing MathNode, source: locator};
    use {{math:ID}} in prose and the builder supplies native Word mathematics.

    The result supplies tokens, a native table and three editable draft files.
    Fill those files, then call report_task with workspace=the previous output,
    drafts=its workspace/drafts.json and a fresh output. Continuation re-reads
    retained JSON, recalculates and exports DOCX through existing manuscript APIs.
    Do not read the general proposal schema or retype values. Support files keep
    located methods/settings. No solver, automatic mechanism or approval is run.
    """
    from cfdpaper.report_workflow import report_workflow

    result = report_workflow(
        output,
        root=root,
        cases=cases,
        quantities=quantities,
        title=title,
        question=question,
        context=context,
        support_files=support_files,
        derived=derived,
        formulas=formulas,
        workspace=workspace,
        drafts=drafts,
    )
    metrics_path = result / "workspace/report-writing.json"
    return _response(
        "report-build" if drafts is not None else "report-prepare",
        result,
        _existing(
            result,
            {
                "recipe": "report.json",
                "continue": "CONTINUE.md",
                "workspace": "workspace",
                "writing_task": "workspace/TASK.md",
                "drafts": "workspace/drafts.json",
                "metrics": "workspace/report-writing.json",
                "manuscript": "manuscript/manuscript.md",
                "docx": "manuscript.docx",
            },
        ),
        _report_context(_read(metrics_path)),
    )


def _research_response(task: str, root: Path) -> dict[str, Any]:
    workspace = root / "workspace" if (root / "workspace").is_dir() else root
    context_path = workspace / "research-context.json"
    context = _read(context_path) if context_path.is_file() else {}
    artifacts = _existing(
        root,
        {
            "workspace": "workspace",
            "manuscript": "manuscript",
            "docx": "manuscript.docx",
            "refresh": "refresh.json",
            "changes": "CHANGES.md",
        },
    )
    artifacts.update(
        _existing(
            workspace,
            {
                "research_context": "research-context.json",
                "task": "TASK.md",
                "research": "RESEARCH.md",
                "drafts": "drafts.json",
                "manuscript_input": "manuscript-input.json",
                "figure_recipes": "figure-recipes.json",
            },
        )
    )
    if (workspace / "figure-recipes.json").is_file():
        for recipe in _read(workspace / "figure-recipes.json"):
            for name in (recipe["script"], *recipe["outputs"]):
                artifacts.update(_existing(workspace, {name: name}))
    if (root / "refresh.json").is_file():
        refresh = _read(root / "refresh.json")
        context["refresh"] = {
            key: value for key, value in refresh.items() if key != "observation_definition"
        }
    return _response(task, root, artifacts, context)


def research_task(
    output: Path,
    *,
    study: Path | None = None,
    workspace: Path | None = None,
    baseline: Path | None = None,
    author_candidate: Path | None = None,
    diagnostics: Path | None = None,
    attach_figure: Path | None = None,
    section_id: str | None = None,
    evidence_ids: list[str] | None = None,
    paragraph_index: int | None = None,
    image_observation: Literal["viewed", "not-viewed"] = "not-viewed",
    observation_note: str = "",
) -> dict[str, Any]:
    """Prepare, attach diagnostics/artwork, or build/refresh an existing research workspace.

    Choose study for preparation or workspace for other operations. Builds use
    current local figure scripts and drafts, preserve inputs, and require fresh
    output. baseline enables targeted refresh; prose interpretation is host-owned.
    """
    from cfdpaper.publication.research_workspace import (
        attach_imported_figure,
        attach_research_diagnostics,
        build_research_workspace,
        prepare_surface_workspace,
    )

    output = Path(output)
    if (study is None) == (workspace is None):
        raise ValueError("Choose exactly one of study or workspace")
    if baseline is not None and workspace is None:
        raise ValueError("baseline requires workspace")
    if author_candidate is not None and (
        workspace is None or diagnostics is not None or attach_figure is not None
    ):
        raise ValueError("author_candidate requires a separate workspace build")
    if diagnostics is not None and (
        workspace is None or baseline is not None or attach_figure is not None
    ):
        raise ValueError("diagnostics requires a separate workspace copy")
    if attach_figure is not None:
        if workspace is None or baseline is not None:
            raise ValueError("Figure attachment requires workspace without baseline")
        if section_id is None:
            raise ValueError("Figure attachment requires section_id")
    elif (
        section_id is not None
        or evidence_ids
        or paragraph_index is not None
        or image_observation != "not-viewed"
        or observation_note
    ):
        raise ValueError("Figure attachment options require attach_figure")
    if diagnostics is not None:
        result = attach_research_diagnostics(Path(workspace), Path(diagnostics), output)
        task = "research-diagnostics"
    elif attach_figure is not None:
        result = attach_imported_figure(
            Path(workspace),
            Path(attach_figure),
            output,
            section_id=section_id,
            evidence_ids=evidence_ids or [],
            paragraph_index=paragraph_index,
            image_observation=image_observation,
            observation_note=observation_note,
        )
        task = "research-attach-figure"
    elif study is not None:
        result = prepare_surface_workspace(Path(study), output)
        task = "research-prepare"
    else:
        result = build_research_workspace(
            Path(workspace),
            output,
            baseline_dir=Path(baseline) if baseline is not None else None,
            author_candidate=Path(author_candidate) if author_candidate is not None else None,
        )
        task = "research-build"
    return _research_response(task, result)


def writing_context(
    package: Path, section_id: str, output: Path, *, drafts: Path | None = None
) -> dict[str, Any]:
    """Gather current section evidence, definitions and dependency drafts for host writing.

    Reuses the existing compact context with exact pointers to full source records.
    Missing dependency drafts are not silently treated as complete manuscript prose.
    """
    from cfdpaper.publication.manuscript import prepare_writing_context

    result = prepare_writing_context(
        Path(package),
        section_id,
        Path(output),
        drafts_path=Path(drafts) if drafts is not None else None,
    )
    context = _read(result / "context.json")
    return _response(
        "writing-context",
        result,
        _existing(result, {"context": "context.json", "task": "TASK.md"}),
        context,
        context.get("missing_dependency_drafts", []),
    )


def _manuscript_context(root: Path) -> dict:
    if (root / "section.json").is_file():
        data = _read(root / "section.json")
        return {
            "title": data["title"],
            "resolved_values": {
                key: _scalar_context(value)
                for key, value in data.get("resolved_values", {}).items()
            },
            "full_values": {
                "path": str((root / "section.json").resolve()),
                "json_pointer": "/resolved_values",
            },
            "figures": data.get("figures", []),
        }
    manifest = root / "manuscript-input.json"
    return _read(manifest) if manifest.is_file() else {}


def manuscript_task(
    output: Path,
    *,
    outline: Path | None = None,
    manuscript_input: Path | None = None,
    package: Path | None = None,
    drafts: Path | None = None,
    export_format: Literal["docx", "md", "tex"] | None = None,
    profile: Literal["research", "report", "conference"] = "research",
    template: Path | None = None,
) -> dict[str, Any]:
    """Prepare from declared inputs, assemble host prose, or export a formal manuscript.

    Select one action via outline, manuscript_input, drafts, or export_format.
    Preparation returns drafts_template and per-section TASK/draft-template.json;
    use those schemas before reading implementation code. An analysis-run writing
    input can be a manifest section directly, preserving its computed bindings.
    Formal export uses the shared research/report/conference renderer; this does
    not claim a Word/PDF page has been visually inspected or TeX compiled.
    """
    from cfdpaper.publication.formal_export import export_formal_manuscript
    from cfdpaper.publication.manuscript import assemble_manuscript, prepare_manuscript
    from cfdpaper.publication.manuscript_seed import prepare_manuscript_seed

    output = Path(output)
    if sum(value is not None for value in (outline, manuscript_input, drafts, export_format)) != 1:
        raise ValueError("Choose exactly one of outline, manuscript_input, drafts or export_format")
    if outline is not None or manuscript_input is not None:
        if package is not None:
            raise ValueError("package is not used with outline or manuscript_input")
    elif package is None:
        raise ValueError("package is required for assembly or export")
    if export_format is None and (template is not None or profile != "research"):
        raise ValueError("profile and template apply only to formal export")
    if outline is not None:
        result = prepare_manuscript_seed(Path(outline), output)
        task = "manuscript-seed"
    elif manuscript_input is not None:
        result = prepare_manuscript(Path(manuscript_input), output)
        task = "manuscript-prepare"
    elif drafts is not None:
        result = assemble_manuscript(Path(package), Path(drafts), output)
        task = "manuscript-assemble"
    else:
        if output.suffix.lower() != "." + export_format:
            raise ValueError("export_format must match the output suffix")
        result = export_formal_manuscript(
            Path(package),
            output,
            profile=profile,
            template_path=Path(template) if template is not None else None,
        )
        artifacts = {"manuscript": str(result.resolve())}
        if result.with_suffix(".layout.json").is_file():
            artifacts["layout"] = str(result.with_suffix(".layout.json").resolve())
        return _response(
            "manuscript-export", Path(package), artifacts, _manuscript_context(Path(package))
        )
    return _response(
        task,
        result,
        _existing(
            result,
            {
                "input": "manuscript-input.json",
                "drafts": "drafts.json",
                "drafts_template": "drafts-template.json",
                "task": "TASK.md",
                "section": "section.json",
                "manuscript": "manuscript.md",
                "changes": "changes.json",
            },
        ),
        _manuscript_context(result),
    )


def author_task(
    package: Path,
    output: Path,
    *,
    return_docx: Path | None = None,
    profile: Literal["research", "report", "conference"] = "research",
    template: Path | None = None,
) -> dict[str, Any]:
    """Create an author Word workspace or reconcile a returned Word manuscript.

    Originals stay unchanged. Returned conflicts/comments and scientific changes
    remain author/host actions rather than automatic approvals or mechanism edits.
    """
    from cfdpaper.publication.author_workspace import (
        import_author_manuscript,
        prepare_author_manuscript,
    )

    if return_docx is not None:
        if template is not None or profile != "research":
            raise ValueError("A Word return uses its saved profile and cannot take a new template")
        result = import_author_manuscript(Path(return_docx), Path(package), Path(output))
        task = "author-return"
    else:
        result = prepare_author_manuscript(
            Path(package),
            Path(output),
            profile=profile,
            template_path=Path(template) if template is not None else None,
        )
        task = "author-prepare"
    context = {}
    for name in ("merge", "comments"):
        if (result / f"{name}.json").is_file():
            context[name] = _read(result / f"{name}.json")
    if (result / "candidate").is_dir():
        context["manuscript"] = _manuscript_context(result / "candidate")
    return _response(
        task,
        result,
        _existing(
            result,
            {
                "candidate": "candidate",
                "docx": "manuscript.docx",
                "manuscript": "manuscript.md",
                "original": "author-original.docx",
                "merge": "merge.json",
                "comments": "comments.json",
                "continue": "CONTINUE.md",
                "read_me": "READ_ME.md",
            },
        ),
        context,
        context.get("merge", {}).get("conflicts", []),
    )


def workbench_task(
    action: Literal["export", "inspect", "restore"],
    workspace: Path,
    *,
    output: Path | None = None,
    baseline: Path | None = None,
    author_dir: Path | None = None,
    task: str | None = None,
    next_action: str | None = None,
    external_roots: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Export, inspect or restore the existing portable workbench and author state.

    External source remapping is explicit; no unrelated drives are searched and
    no original solver data are modified. Delegates to workbench_portability.
    """
    from cfdpaper.workbench_portability import (
        export_workbench,
        inspect_workbench,
        restore_workbench,
    )

    workspace = Path(workspace)
    if action not in {"export", "inspect", "restore"}:
        raise ValueError("action must be export, inspect or restore")
    if action == "export":
        if output is None:
            raise ValueError("export requires output")
        if external_roots is not None:
            raise ValueError("external_roots applies to inspect or restore")
        result = export_workbench(
            workspace,
            Path(output),
            baseline_dir=Path(baseline) if baseline is not None else None,
            author_dir=Path(author_dir) if author_dir is not None else None,
            task=task,
            next_action=next_action,
        )
    else:
        if (
            baseline is not None
            or author_dir is not None
            or task is not None
            or next_action is not None
        ):
            raise ValueError("baseline, author_dir, task and next_action apply only to export")
        if action == "inspect":
            if output is not None:
                raise ValueError("inspect does not write output")
            result = workspace
        else:
            if output is None:
                raise ValueError("restore requires output")
            result = restore_workbench(workspace, Path(output), external_roots=external_roots)
    context = inspect_workbench(result, external_roots=external_roots)
    artifacts = _existing(
        result,
        {
            "workbench": "workbench.json",
            "task": "TASK.md",
            "continue": "CONTINUE.md",
            "workspace": "workspace",
            "baseline": "baseline",
            "author": "author",
        },
    )
    return _response(
        f"workbench-{action}",
        result,
        artifacts,
        context,
        [*context.get("missing", []), *context.get("unresolved_paths", [])],
    )
