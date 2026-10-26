"""Prepare ordinary manuscript tasks from an explicit report projection."""

from __future__ import annotations

import csv
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from cfdpaper.publication.manuscript import prepare_manuscript
from cfdpaper.publication.parameter_evidence import resolve_json_value
from cfdpaper.publication.report_derivations import compile_report_derivations
from cfdpaper.publication.report_math import normalize_report_formulas
from cfdpaper.publication.section import (
    _copy_sources,
    _fresh,
    _read,
    _stage,
    _TableCalculation,
    _write,
)
from cfdpaper.publication.table_evidence import calculate_declared_table, resolve_table_result

_RESPONSIBILITIES = {
    "methods": "Describe the read variables, declared selection or comparison operator, units, "
    "and spatial/statistical support domain. Do not infer an upstream solver method.",
    "results": "Compare the declared case results and paired changes using the bound evidence "
    "and native table. State observed differences without assigning a physical cause.",
    "discussion": "Distinguish the observed numerical comparisons from physical explanations. "
    "Assess interpretation against the supplied support domains and missing controls.",
}
_DEFINITION = "sources/report-writing-definition.json"


def _figure_source_units(path):
    """Read the actual response-axis scales before reusing an author's local script."""
    units = {}
    with path.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if row.get("kind") == "response":
                for axis in ("x", "y"):
                    units.setdefault((row["panel"], axis), set()).add(row[f"{axis}_unit"])
    return units


def _report_figure(root, calculations, evidence, plan, author_plot):
    """Use existing bound calculations, retaining the author's actual refresh script."""
    if plan is None:
        return [], []
    if not isinstance(plan, dict) or set(plan) - {"panels", "columns", "style", "caption"}:
        raise ValueError("Report figure_plan accepts panels, columns, style and caption")
    from cfdpaper.publication.evidence_panels import render_evidence_panels
    from cfdpaper.publication.render_figure import PlotStyle, _run_script

    path = root / "report-figure-input.json"
    _write(path, {"table_calculations": calculations, "evidence": evidence})
    output = root / "sources/report-figure"
    figure = render_evidence_panels(
        path,
        plan.get("panels", []),
        output,
        columns=plan.get("columns", 1),
        style=PlotStyle.model_validate(plan["style"]) if "style" in plan else None,
    )
    if author_plot is not None:
        previous_units = _figure_source_units(
            author_plot.parent / "evidence-panels-source-data.csv"
        )
        current_units = _figure_source_units(output / "evidence-panels-source-data.csv")
        if previous_units != current_units:
            changes = []
            for key in sorted(previous_units.keys() | current_units.keys()):
                before, after = previous_units.get(key, set()), current_units.get(key, set())
                if before != after:
                    old = ", ".join(unit or "dimensionless" for unit in sorted(before)) or "missing"
                    new = ", ".join(unit or "dimensionless" for unit in sorted(after)) or "missing"
                    changes.append(f"panel {key[0]} {key[1]}: {old} -> {new}")
            raise ValueError(
                "Figure source units changed (" + "; ".join(changes) + "). "
                "Regenerate a new figure plan with current physical units, then migrate "
                "the author styling. The retained author plot.py was not changed."
            )
        shutil.copyfile(author_plot, output / "plot.py")
        # Never let an author script's no-op reuse the template's provisional render.
        for name in [
            *(f"evidence-panels.{ext}" for ext in ("png", "svg", "pdf", "tiff")),
            "layout-checks.json",
        ]:
            (output / name).unlink()
        _run_script(output / "plot.py")
        for ext in ("png", "svg", "pdf", "tiff"):
            if not (output / f"evidence-panels.{ext}").is_file():
                raise ValueError(f"Retained author plot did not regenerate {ext}")
        checks = _read(output / "layout-checks.json")
        figure["sizing"] = {key: checks[key] for key in figure["sizing"]}
    if "caption" in plan:
        if not isinstance(plan["caption"], str) or not plan["caption"].strip():
            raise ValueError("Report figure caption must be nonblank text")
        figure["caption"] = figure["description"] = plan["caption"]
    summary = _read(output / "figure-summary.json")
    summary["figures"] = [figure]
    if author_plot is not None:
        summary.update(checks=checks, author_script_retained=True)
    _write(output / "figure-summary.json", summary)
    files = [path.relative_to(root).as_posix() for path in output.iterdir() if path.is_file()]
    return [figure], files


def report_context(writing: dict) -> dict:
    """Derive the same compact report view for file, CLI and host consumers."""
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


def _projection_evidence(root: Path, projection: dict):
    source = projection["source"]
    cases = projection["cases"]
    quantities = projection["quantities"]
    if (
        not cases
        or any(not isinstance(case, str) or not case.strip() for case in cases)
        or len(set(cases)) != len(cases)
        or not quantities
    ):
        raise ValueError("Report writing requires distinct case IDs and declared quantities")
    with (root / source).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"case_id", "quantity", "member", "value", "unit", "source", "pointer"}
        if not required <= set(reader.fieldnames or []):
            raise ValueError("Report projection is missing required CSV columns")
        rows = list(reader)
    calculations, reports, evidence, metrics, table_rows = [], [], [], [], []
    seen = {"report_question"}
    quantity_ids = set()
    for quantity in quantities:
        qid = quantity["id"]
        if qid in quantity_ids:
            raise ValueError(f"Duplicate report quantity: {qid}")
        quantity_ids.add(qid)
        paired = "reference" in quantity or "comparison" in quantity
        if paired and not {"reference", "comparison"} <= quantity.keys():
            raise ValueError(f"Paired quantity {qid} requires reference and comparison pointers")
        unit = quantity.get("output_unit", quantity["unit"])
        calculation = _TableCalculation(
            id=qid,
            source=source,
            operation="paired_change" if paired else "scalar_select",
            columns={"value": "value"},
            units={"value": unit},
            domain=quantity["domain"],
            group_by="case_id",
            row_filters={"quantity": qid},
            unit_column="unit",
            quantity_kind=quantity.get("quantity_kind", "ordinary"),
            **(
                {"pair_by": "member", "reference": "reference", "comparison": "comparison"}
                if paired
                else {}
            ),
        ).model_dump()
        report = {**calculation, **calculate_declared_table(root / source, calculation)}
        if {group["group"] for group in report["groups"]} != set(cases):
            raise ValueError(f"Quantity {qid} does not have exactly the declared case groups")
        calculations.append(calculation)
        reports.append(report)
        for case in cases:
            eid = f"{qid}_{case}"
            if eid in seen:
                raise ValueError(f"Report evidence IDs collide: {eid}")
            seen.add(eid)
            reference = {
                "calculation_id": qid,
                "group": case,
                "field": "difference" if paired else "value",
                "places": quantity.get("places", 3),
            }
            resolved = resolve_table_result(reports, **reference)
            locators = []
            for record in resolved["csv_records"]:
                row = rows[record - 2]
                if row["source"] not in projection["source_files"]:
                    raise ValueError(f"Undeclared original report source: {row['source']}")
                resolve_json_value(
                    root, source=row["source"], pointer=row["pointer"], unit=quantity["unit"]
                )
                locators.append({"source": row["source"], "pointer": row["pointer"]})
            locator_text = "; ".join(f"{item['source']}#{item['pointer']}" for item in locators)
            operation = "comparison minus reference" if paired else "selected scalar"
            evidence.append(
                {
                    "id": eid,
                    "kind": "metric",
                    "text": f"{quantity['label']}, case {case}: {operation}; "
                    f"support: {quantity['domain']}.",
                    "source": f"{source}:records "
                    + ",".join(str(record) for record in resolved["csv_records"])
                    + "; "
                    + locator_text,
                    "result_ref": reference,
                }
            )
            metrics.append(
                {
                    "evidence_id": eid,
                    "case_id": case,
                    "quantity": qid,
                    "label": quantity["label"],
                    "domain": quantity["domain"],
                    "operation": calculation["operation"],
                    **resolved,
                    "original_sources": locators,
                }
            )
            if quantity.get("table", True):
                table_rows.append([case, quantity["label"], operation, "{{value:" + eid + "}}"])
    return calculations, reports, evidence, metrics, table_rows, len(rows)


def _task(question: str) -> str:
    return (
        "# Write the prepared report\n\n"
        f"Question: {question}\n\n"
        "This is an unfilled ordinary manuscript workspace, not a completed report. "
        "Fill sections/methods/draft.json, sections/results/draft.json, and "
        "sections/discussion/draft.json; drafts.json already maps those paths. "
        "Read report-context.json first for compact values, support domains, explicit "
        "denominators and formula tokens. It is a derived view, not another source of facts. "
        "Its details_pointer entries locate full metrics in report-writing.json. The three "
        "sections share one evidence set and draft interface: read one input/template "
        "to learn it, then consult full report-writing.json, input.json or table-results.json "
        "only for needed definitions or detailed calculations. The original JSON files and "
        "the calculated projection are retained under each section's sources/.\n\n"
        + "\n".join(f"- {sid.title()}: {purpose}" for sid, purpose in _RESPONSIBILITIES.items())
        + "\n\nKeep or edit the native Results table already in draft.json; do not retype "
        "its numbers. Use {{value:evidence_id}} with an exact local evidence ID. "
        "A value token includes its unit, so do not append that unit again. "
        "Use {{table:report_values}} to refer to the supplied table. Cover the duties "
        "through paragraph evidence_ids; Methods and Discussion bind only the evidence they use. "
        "Split the initial evidence_ids between paragraphs when useful. "
        "report_question is available as question metadata, not a numerical finding or "
        "a required paragraph citation.\n\n"
        "Methods must report available numerical boundary conditions, material assignments "
        "and source prescriptions needed to understand this comparison, with their exact "
        "source locations. Do not replace those values with script paths or vague statements "
        "that conditions were unchanged. If a dimensionless input is a fraction, identify "
        "that convention rather than silently presenting it as a percentage. Missing method "
        "values remain explicit gaps, not invented defaults.\n\n"
        "Additional ratios or relative errors need an explicit calculation and reference "
        "denominator. Numbers typed into prose are not automatically refreshed merely "
        "because nearby value tokens are bound; reconsider them after source changes.\n\n"
        "The metric summary retains each observation's domain and exact sources. A derived "
        "comparison also names its reference denominator and both parent supports. A relation "
        "at one location, operator or time support does not establish it elsewhere. Read a "
        "nonzero identity residual as a diagnostic result, not a closed physical budget.\n\n"
        "If report-context.json lists a formula ID, use {{math:ID}} directly. The report "
        "builder supplies that declared native expression automatically; paragraph-local "
        "author mathematics takes priority. Do not rewrite it as Re^(...) text.\n\n"
        "For editable inline math, put {{math:quantity}} in a paragraph and add this "
        "object to that paragraph (not a TeX string):\n\n"
        '```json\n{"inline_math": {"quantity": {"kind": "sub", "children": '
        '[{"kind": "symbol", "text": "q"}, {"kind": "text", "text": "ref"}]}}}\n```\n\n'
        "Leave evidence_notes for concrete gaps or review questions. Do not invent "
        "missing conditions, measurements, causal proof, or automatic approval. "
        "After filling the drafts, use the existing manuscript assembly and formal export.\n"
        "When report-context.json includes figures, open their preview before interpretation. "
        'Use {{figure:1}} in Results with figure_ids=["1"]; retain or revise the supplied '
        "caption and record actual visible features in observation_notes. A computed source "
        "binding alone does not show that the image displays the relationship discussed.\n"
    )


def prepare_report_writing(
    projection_dir: Path,
    projection: dict,
    output: Path,
    *,
    title: str,
    question: str,
    context: str = "",
    figure_plan: dict | None = None,
    author_plot: Path | None = None,
) -> Path:
    """Prepare Methods/Results/Discussion without generating scientific prose.

    The returned directory is a normal ``prepare_manuscript`` workspace. Its
    ``drafts.json`` maps three intentionally unfilled drafts; the Results draft
    already contains an editable, result-bound table. ``report-writing.json``
    retains the complete metric details; the report workflow also publishes a
    compact ``report-context.json`` read view.
    """
    projection_dir, output = Path(projection_dir), Path(output)
    _fresh(output)
    if not title.strip() or not question.strip():
        raise ValueError("Report title and question must not be blank")
    files = list(dict.fromkeys([projection["source"], *projection["source_files"]]))
    if _DEFINITION in files:
        raise ValueError(f"Report projection uses reserved source path: {_DEFINITION}")
    with TemporaryDirectory(prefix="cfdpaper-report-writing-") as temporary:
        root = Path(temporary)
        _copy_sources(SimpleNamespace(source_files=files), projection_dir, root)
        calculations, reports, evidence, metrics, rows, row_count = _projection_evidence(
            root, projection
        )
        comparisons, derived_evidence, derived_metrics, derived_rows = compile_report_derivations(
            projection.get("derived", []), metrics, reports
        )
        evidence.extend(derived_evidence)
        metrics.extend(derived_metrics)
        rows.extend(derived_rows)
        formulas = normalize_report_formulas(projection.get("formulas"))
        figures, figure_files = _report_figure(
            root, calculations, evidence, figure_plan, author_plot
        )
        _write(
            root / _DEFINITION,
            {
                "question": question,
                "quantities": projection["quantities"],
                "derived": projection.get("derived", []),
                "formulas": formulas,
            },
        )
        files.append(_DEFINITION)
        evidence.append(
            {
                "id": "report_question",
                "kind": "observation",
                "text": question,
                "source": _DEFINITION + "#/question",
            }
        )
        table_ids = [row[-1][8:-2] for row in rows]
        central_claim = table_ids[0] if table_ids else metrics[0]["evidence_id"]
        contracts, sections = [], []
        for sid, purpose in _RESPONSIBILITIES.items():
            required = (table_ids or [central_claim]) if sid == "results" else []
            current_figures = figures if sid == "results" else []
            figure_ids = [figure["id"] for figure in current_figures]
            _write(
                root / f"{sid}.json",
                {
                    "section_id": sid,
                    "title": sid.title(),
                    "question": question,
                    "context": context,
                    "figures": [
                        {key: value for key, value in figure.items() if key != "evidence_ids"}
                        for figure in current_figures
                    ],
                    "source_files": files + (figure_files if current_figures else []),
                    "table_calculations": calculations,
                    "result_comparisons": comparisons,
                    "evidence": evidence,
                    "duties": [
                        {"purpose": purpose, "evidence_ids": required, "figure_ids": figure_ids}
                    ],
                },
            )
            sections.append({"section_id": sid, "input": f"{sid}.json"})
            contracts.append(
                {
                    "section_id": sid,
                    "role": sid,
                    "title": sid.title(),
                    "purpose": purpose,
                    "required_claim_ids": required,
                    "required_figure_ids": figure_ids,
                }
            )
        _write(
            root / "manuscript-input.json",
            {
                "title": title,
                "context": question + ("\n\n" + context if context else ""),
                "spine": {
                    "topic_id": "report",
                    "central_claim_id": central_claim,
                    "sections": contracts,
                },
                "sections": sections,
            },
        )
        with _stage(output) as staged:
            workspace = prepare_manuscript(root / "manuscript-input.json", root / "prepared")
            for sid, purpose in _RESPONSIBILITIES.items():
                section = workspace / "sections" / sid
                draft = _read(section / "draft-template.json")
                draft["paragraphs"][0]["evidence_ids"] = (
                    (table_ids or [central_claim]) if sid == "results" else []
                )
                if sid == "results":
                    draft["paragraphs"][0]["figure_ids"] = [figure["id"] for figure in figures]
                if sid == "results" and rows:
                    draft["tables"] = [
                        {
                            "table_id": "report_values",
                            "caption": "Declared case metrics and paired changes",
                            "columns": ["Case", "Quantity", "Operator", "Result"],
                            "rows": rows,
                            "after_section_id": "results",
                            "evidence_ids": table_ids,
                            "numeric_columns": [3],
                        }
                    ]
                _write(section / "draft-template.json", draft)
                _write(section / "draft.json", draft)
                (section / "TASK.md").write_text(
                    f"# {sid.title()}\n\n{purpose}\n\n"
                    "Read report-context.json first and use the common manuscript TASK.md. "
                    "The three sections share the same evidence definitions. Consult input.json "
                    "for exact operators/support/source locators and table-results.json for "
                    "calculation details when needed; do not reread identical reports per section. "
                    "Fill the blank draft.json using the manuscript TASK.md token guidance.\n",
                    encoding="utf-8",
                )
            _write(workspace / "drafts.json", _read(workspace / "drafts-template.json"))
            _write(
                workspace / "report-writing.json",
                {
                    "question": question,
                    "cases": projection["cases"],
                    "quantities": [item["id"] for item in projection["quantities"]],
                    "row_count": row_count,
                    "evidence_count": len(metrics),
                    "metrics": metrics,
                    "formulas": [
                        {"id": key, "source": value["source"], "token": "{{math:" + key + "}}"}
                        for key, value in formulas.items()
                    ],
                    "drafts": "drafts.json",
                    "pending_sections": list(_RESPONSIBILITIES),
                    **(
                        {
                            "figures": [
                                {
                                    **figure,
                                    "section_id": "results",
                                    "path": f"sections/results/figures/{figure['id']}.png",
                                    "script": "sections/results/sources/report-figure/plot.py",
                                }
                                for figure in figures
                            ]
                        }
                        if figures
                        else {}
                    ),
                },
            )
            (workspace / "TASK.md").write_text(_task(question), encoding="utf-8")
            for child in workspace.iterdir():
                shutil.move(str(child), str(staged / child.name))
            workspace.rmdir()
    return output
