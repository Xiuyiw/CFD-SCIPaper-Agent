"""Minimum defensibility checks for CFD evidence and claims."""

from .comparability import CaseDefinition, ComparabilityResult, check_case_comparability
from .conservation import ConservationAssessment, assess_conservation
from .convergence import ConvergenceAssessment, ConvergenceGrade, grade_convergence
from .evidence import (
    ClaimCeiling,
    ClaimCeilingAssessment,
    EvidenceMaturity,
    MaturityAssessment,
    assess_claim_ceiling,
    assess_evidence_maturity,
)
from .qoi import QoICheck, QoIDefinition, check_qoi_definition
from .trends import TrendAssessment, TrendKind, detect_trend
from .units import convert_value, unit_is_known, units_compatible

__all__ = [
    "CaseDefinition",
    "ClaimCeiling",
    "ClaimCeilingAssessment",
    "ComparabilityResult",
    "ConservationAssessment",
    "ConvergenceAssessment",
    "ConvergenceGrade",
    "EvidenceMaturity",
    "MaturityAssessment",
    "QoICheck",
    "QoIDefinition",
    "TrendAssessment",
    "TrendKind",
    "assess_claim_ceiling",
    "assess_conservation",
    "assess_evidence_maturity",
    "check_case_comparability",
    "check_qoi_definition",
    "convert_value",
    "detect_trend",
    "grade_convergence",
    "unit_is_known",
    "units_compatible",
]
