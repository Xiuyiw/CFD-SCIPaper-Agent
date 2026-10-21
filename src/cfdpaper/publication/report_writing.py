"""Prepare ordinary manuscript tasks from an explicit report projection."""

from __future__ import annotations

import csv
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from cfdpaper.publication.manuscript import prepare_manuscript
from cfdpaper.publication.parameter_evidence import resolve_json_value
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
                "places": 3,
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
                    "operation": calculation["operation"],
                    **resolved,
                    "original_sources": locators,
                }
            )
            table_rows.append([case, quantity["label"], operation, "{{value:" + eid + "}}"])
    return calculations, evidence, metrics, table_rows, len(rows)


def _task(question: str) -> str:
    return (
        "# Write the prepared report\n\n"
        f"Question: {question}\n\n"
        "This is an unfilled ordinary manuscript workspace, not a completed report. "
        "Fill sections/methods/draft.json, sections/results/draft.json, and "
        "sections/discussion/draft.json; drafts.json already maps those paths. "
        "Use the returned metric summary (also in report-writing.json). The three "
        "sections share one evidence set and draft interface: read one input/template "
        "to learn it, then consult full input.json or table-results.json only for "
        "needed definitions or detailed calculations. The original JSON files and "
        "the calculated projection are retained under each section's sources/.\n\n"
        + "\n".join(f"- {sid.title()}: {purpose}" for sid, purpose in _RESPONSIBILITIES.items())
        + "\n\nKeep or edit the native Results table already in draft.json; do not retype "
        "its numbers. Use {{value:evidence_id}} with an exact local evidence ID. "
        "A value token includes its unit, so do not append that unit again. "
        "Use {{table:report_values}} to refer to the supplied table. Cover the duties "
        "through paragraph evidence_ids; Methods and Discussion need not repeat every value. "
        "Split the initial evidence_ids between paragraphs when useful. "
        "report_question records the supplied question, not a numerical finding.\n\n"
        "Additional ratios or relative errors need an explicit calculation and reference "
        "denominator. Numbers typed into prose are not automatically refreshed merely "
        "because nearby value tokens are bound; reconsider them after source changes.\n\n"
        "For editable inline math, put {{math:quantity}} in a paragraph and add this "
        "object to that paragraph (not a TeX string):\n\n"
        '```json\n{"inline_math": {"quantity": {"kind": "sub", "children": '
        '[{"kind": "symbol", "text": "q"}, {"kind": "text", "text": "ref"}]}}}\n```\n\n'
        "Leave evidence_notes for concrete gaps or review questions. Do not invent "
        "missing conditions, measurements, causal proof, or automatic approval. "
        "After filling the drafts, use the existing manuscript assembly and formal export.\n"
    )


def prepare_report_writing(
    projection_dir: Path,
    projection: dict,
    output: Path,
    *,
    title: str,
    question: str,
    context: str = "",
) -> Path:
    """Prepare Methods/Results/Discussion without generating scientific prose.

    The returned directory is a normal ``prepare_manuscript`` workspace. Its
    ``drafts.json`` maps three intentionally unfilled drafts; the Results draft
    already contains an editable, result-bound table. ``report-writing.json``
    exposes the current calculated metrics for a host's compact response.
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
        calculations, evidence, metrics, rows, row_count = _projection_evidence(root, projection)
        _write(root / _DEFINITION, {"question": question, "quantities": projection["quantities"]})
        files.append(_DEFINITION)
        evidence.append(
            {
                "id": "report_question",
                "kind": "observation",
                "text": question,
                "source": _DEFINITION + "#/question",
            }
        )
        evidence_ids = [item["id"] for item in evidence]
        contracts, sections = [], []
        for sid, purpose in _RESPONSIBILITIES.items():
            required = evidence_ids if sid == "results" else ["report_question"]
            _write(
                root / f"{sid}.json",
                {
                    "section_id": sid,
                    "title": sid.title(),
                    "question": question,
                    "context": context,
                    "figures": [],
                    "source_files": files,
                    "table_calculations": calculations,
                    "evidence": evidence,
                    "duties": [{"purpose": purpose, "evidence_ids": required, "figure_ids": []}],
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
                    "required_figure_ids": [],
                }
            )
        _write(
            root / "manuscript-input.json",
            {
                "title": title,
                "context": question + ("\n\n" + context if context else ""),
                "spine": {
                    "topic_id": "report",
                    "central_claim_id": "report_question",
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
                    evidence_ids if sid == "results" else ["report_question"]
                )
                if sid == "results":
                    draft["tables"] = [
                        {
                            "table_id": "report_values",
                            "caption": "Declared case metrics and paired changes",
                            "columns": ["Case", "Quantity", "Operator", "Result"],
                            "rows": rows,
                            "after_section_id": "results",
                            "evidence_ids": [
                                item["id"] for item in evidence if item["kind"] == "metric"
                            ],
                            "numeric_columns": [3],
                        }
                    ]
                _write(section / "draft-template.json", draft)
                _write(section / "draft.json", draft)
                (section / "TASK.md").write_text(
                    f"# {sid.title()}\n\n{purpose}\n\n"
                    "Use the common manuscript TASK.md and compact report-writing.json. "
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
                    "cases": projection["cases"],
                    "quantities": [item["id"] for item in projection["quantities"]],
                    "row_count": row_count,
                    "evidence_count": len(metrics),
                    "metrics": metrics,
                    "drafts": "drafts.json",
                    "pending_sections": list(_RESPONSIBILITIES),
                },
            )
            (workspace / "TASK.md").write_text(_task(question), encoding="utf-8")
            for child in workspace.iterdir():
                shutil.move(str(child), str(staged / child.name))
            workspace.rmdir()
    return output
