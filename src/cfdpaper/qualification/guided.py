"""Prompt-adapter-driven scientific intake for researchers."""

from __future__ import annotations

from typing import Protocol

from .records import GuidedRecords


class PromptAdapter(Protocol):
    def ask(self, key: str, message: str) -> str | None: ...


class GuidedIntakeCancelled(ValueError):
    """Raised when a required scientific answer is cancelled or omitted."""


def _required(prompt: PromptAdapter, key: str, message: str) -> str:
    value = prompt.ask(key, message)
    if value is None or not value.strip():
        raise GuidedIntakeCancelled(f"Guided intake stopped before {key} was completed.")
    return value.strip()


def build_guided_records(prompt: PromptAdapter) -> GuidedRecords:
    """Ask scientific questions and return the same strict envelope used by file intake."""

    ask = lambda key, message: _required(prompt, key, message)  # noqa: E731
    case_id = ask("case_id", "Case identifier")
    coordinate_name = ask("coordinate_name", "Study coordinate name")
    coordinate_value = ask("coordinate_value", "Coordinate value for this case")
    coordinate_unit = ask("coordinate_unit", "Coordinate unit")

    boundary_name = ask("boundary_name", "Boundary difference name")
    boundary_reference = ask("boundary_reference", "Reference boundary value")
    boundary_candidate = ask("boundary_candidate", "Candidate boundary value")
    boundary_role = ask("boundary_role", "Scientific role of this boundary difference")
    boundary_basis = ask("boundary_basis", "Basis for the boundary classification")
    boundary_locator = ask("boundary_locator", "Source locator for the boundary evidence")

    model_name = ask("model_name", "Model difference name")
    model_reference = ask("model_reference", "Reference model value")
    model_candidate = ask("model_candidate", "Candidate model value")
    model_role = ask("model_role", "Scientific role of this model difference")
    model_basis = ask("model_basis", "Basis for the model classification")
    model_locator = ask("model_locator", "Source locator for the model evidence")

    convergence_metric = ask("convergence_metric", "Observed convergence metric")
    convergence_observed = ask("convergence_observed", "Observed convergence value")
    convergence_unit = ask("convergence_unit", "Convergence metric unit")
    convergence_threshold = ask("convergence_threshold", "Declared convergence threshold")
    convergence_operator = ask("convergence_operator", "Convergence threshold operator")
    convergence_consequence = ask(
        "convergence_consequence", "Consequence when the convergence threshold is exceeded"
    )
    convergence_basis = ask("convergence_basis", "Scientific basis for the convergence threshold")
    convergence_locator = ask("convergence_locator", "Source locator for convergence evidence")

    conservation_metric = ask("conservation_metric", "Observed conservation metric")
    conservation_observed = ask("conservation_observed", "Observed conservation value")
    conservation_unit = ask("conservation_unit", "Conservation metric unit")
    conservation_threshold = ask("conservation_threshold", "Declared conservation threshold")
    conservation_operator = ask("conservation_operator", "Conservation threshold operator")
    conservation_consequence = ask(
        "conservation_consequence", "Consequence when the conservation threshold is exceeded"
    )
    conservation_basis = ask("conservation_basis", "Scientific basis for the threshold")
    conservation_locator = ask("conservation_locator", "Source locator for conservation evidence")

    verification_status = ask("verification_status", "Numerical verification status")
    verification_basis = ask("verification_basis", "Basis for the verification status")
    verification_locator = ask("verification_locator", "Source locator for verification evidence")
    validation_status = ask("validation_status", "External validation status")
    validation_basis = ask("validation_basis", "Basis for the validation status")
    validation_locator = ask("validation_locator", "Source locator for validation evidence")

    source_uri = ask("source_uri", "Source file identifier")
    source_locator = ask("source_locator", "Source file locator")
    source_sha256 = ask("source_sha256", "Source file SHA-256")
    source_mtime_ns = ask("source_mtime_ns", "Source modification time in nanoseconds")
    source_size_bytes = ask("source_size_bytes", "Source size in bytes")

    return GuidedRecords.model_validate(
        {
            "cases": [
                {
                    "case_id": case_id,
                    "source_uri": source_uri,
                    "locator": f"{source_locator}#case={case_id}",
                    "state": "extracted",
                }
            ],
            "boundaries": [
                {
                    "boundary_id": f"boundary-{case_id}",
                    "case_id": case_id,
                    "source_uri": source_uri,
                    "locator": boundary_locator,
                    "boundary_type": "comparison-difference",
                    "values": {
                        "name": boundary_name,
                        "reference": boundary_reference,
                        "candidate": boundary_candidate,
                        coordinate_name: float(coordinate_value),
                    },
                    "units": {coordinate_name: coordinate_unit},
                    "comparison_role": boundary_role,
                    "basis": boundary_basis,
                }
            ],
            "models": [
                {
                    "model_id": f"model-{case_id}",
                    "case_id": case_id,
                    "source_uri": source_uri,
                    "locator": model_locator,
                    "description": f"{model_name}: {model_reference} -> {model_candidate}",
                    "comparison_role": model_role,
                    "basis": model_basis,
                    "verification_status": verification_status,
                    "verification_basis": verification_basis,
                    "verification_locator": verification_locator,
                    "validation_status": validation_status,
                    "validation_basis": validation_basis,
                    "validation_locator": validation_locator,
                }
            ],
            "convergence": [
                {
                    "evidence_id": f"conv-{case_id}",
                    "case_id": case_id,
                    "source_uri": source_uri,
                    "locator": convergence_locator,
                    "metric": convergence_metric,
                    "observed_value": float(convergence_observed),
                    "unit": convergence_unit,
                    "threshold_value": float(convergence_threshold),
                    "operator": convergence_operator,
                    "consequence": convergence_consequence,
                    "basis": convergence_basis,
                }
            ],
            "conservation": [
                {
                    "evidence_id": f"cons-{case_id}",
                    "case_id": case_id,
                    "source_uri": source_uri,
                    "locator": conservation_locator,
                    "metric": conservation_metric,
                    "observed_value": float(conservation_observed),
                    "unit": conservation_unit,
                    "threshold_value": float(conservation_threshold),
                    "operator": conservation_operator,
                    "consequence": conservation_consequence,
                    "basis": conservation_basis,
                }
            ],
            "sources": [
                {
                    "source_uri": source_uri,
                    "locator": source_locator,
                    "sha256": source_sha256,
                    "mtime_ns": int(source_mtime_ns),
                    "size_bytes": int(source_size_bytes),
                    "media_type": "text/csv",
                }
            ],
        }
    )
