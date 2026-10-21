"""Connect selected report results through the existing comparison engine."""

from __future__ import annotations

import re

from cfdpaper.publication.section import _ResultComparison
from cfdpaper.publication.table_evidence import calculate_result_comparison, resolve_table_result


def compile_report_derivations(declarations: list[dict], metrics: list[dict], reports: list[dict]):
    """Return comparisons, evidence, compact results and optional bound table rows.

    Parents are existing report metrics, not expressions or independently validated
    observations. In a relative change the declared reference is the denominator.
    The host supplies the physical domain, comparison scope and located definition.
    """
    parents = {item["evidence_id"]: item for item in metrics}
    seen = set(parents)
    comparisons, evidence, summaries, rows = [], [], [], []
    definitions = {
        "difference": "comparison minus reference",
        "ratio": "comparison divided by reference",
        "relative_change": "(comparison minus reference) divided by reference",
        "relative_reduction": "(reference minus comparison) divided by reference",
    }
    for item in declarations:
        identity = item["id"]
        if not isinstance(identity, str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_.-]*", identity
        ):
            raise ValueError("Derived metric requires a portable ID")
        if identity in seen:
            raise ValueError(f"Duplicate report evidence ID: {identity}")
        seen.add(identity)
        if not isinstance(item.get("label"), str) or not item["label"].strip():
            raise ValueError(f"Derived metric {identity}: label is required")
        field = item["field"]
        if field not in definitions:
            raise ValueError(f"Derived metric {identity}: unsupported field {field!r}")
        try:
            selected = {role: parents[item[role]] for role in ("reference", "comparison")}
        except KeyError as exc:
            raise ValueError(
                f"Derived metric {identity}: select an existing base evidence ID"
            ) from exc
        references = {
            role: {key: record[key] for key in ("calculation_id", "group", "field")}
            for role, record in selected.items()
        }
        comparison = _ResultComparison(
            id=identity,
            **references,
            domain=item["domain"],
            comparison_scope=item["comparison_scope"],
            definition_source=item["definition_source"],
            status="supported",
            temperature_reference=item.get("temperature_reference"),
        )
        report = calculate_result_comparison(reports, **comparison.engine_arguments())
        binding = {
            "calculation_id": identity,
            "group": "all",
            "field": field,
            "places": item.get("places", 3),
            "percentage": item.get("percentage", False),
        }
        resolved = resolve_table_result([*reports, report], **binding)
        denominator = {
            "evidence_id": item["reference"],
            "raw_value": selected["reference"]["raw_value"],
            "unit": selected["reference"]["unit"],
        }
        if report.get("temperature_reference") is not None:
            denominator.update(
                source_raw_value=denominator["raw_value"],
                source_unit=denominator["unit"],
                origin=report["temperature_reference"],
                raw_value=denominator["raw_value"] - report["temperature_reference"],
                unit="K",
            )
        # This is an algebraic comparison, never an automatic scientific approval.
        evidence.append(
            {
                "id": identity,
                "kind": "metric",
                "evidence_role": "algebraic",
                "text": f"{item['label']}: {definitions[field]}; "
                f"scope: {item['comparison_scope']}; support: {item['domain']}.",
                "source": item["definition_source"],
                "result_ref": binding,
            }
        )
        summaries.append(
            {
                "evidence_id": identity,
                "quantity": identity,
                "label": item["label"],
                "operation": "result_comparison",
                "domain": item["domain"],
                "comparison_scope": item["comparison_scope"],
                "definition": definitions[field],
                "reference_evidence_id": item["reference"],
                "comparison_evidence_id": item["comparison"],
                "denominator": denominator if field != "difference" else None,
                "parent_support": [
                    {
                        "role": role,
                        "evidence_id": item[role],
                        "case_id": selected[role].get("case_id"),
                        "domain": selected[role].get("domain"),
                        "original_sources": selected[role]["original_sources"],
                    }
                    for role in ("reference", "comparison")
                ],
                **resolved,
            }
        )
        if item.get("table", False):
            rows.append([identity, item["label"], definitions[field], "{{value:" + identity + "}}"])
        comparisons.append(comparison.model_dump())
    return comparisons, evidence, summaries, rows
