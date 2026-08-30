"""Evidence maturity and defensible claim ceilings."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .conservation import ConservationAssessment
from .convergence import ConvergenceAssessment, ConvergenceGrade
from .qoi import QoICheck
from .trends import TrendAssessment, TrendKind


class EvidenceMaturity(str, Enum):
    RAW = "raw"
    SCREENED = "screened"
    VERIFIED = "verified"
    AUTHOR_APPROVED = "author-approved"


class ClaimCeiling(str, Enum):
    OBSERVATION = "observation"
    ASSOCIATION = "association"
    MECHANISM = "mechanism"
    VALIDATION = "validation"
    ENGINEERING = "engineering"


_CEILING_ORDER = {
    ClaimCeiling.OBSERVATION: 0,
    ClaimCeiling.ASSOCIATION: 1,
    ClaimCeiling.MECHANISM: 2,
    ClaimCeiling.VALIDATION: 3,
    ClaimCeiling.ENGINEERING: 4,
}


@dataclass(frozen=True, slots=True)
class MaturityAssessment:
    level: EvidenceMaturity
    blockers: tuple[str, ...]
    approval_rejected: bool = False
    approved_by: str | None = None
    trend_contradiction: bool = False
    trend_claim_blocked: bool = False


@dataclass(frozen=True, slots=True)
class ClaimCeilingAssessment:
    ceiling: ClaimCeiling
    reasons: tuple[str, ...]

    def allows(self, requested: ClaimCeiling) -> bool:
        return _CEILING_ORDER[requested] <= _CEILING_ORDER[self.ceiling]


def assess_evidence_maturity(
    *,
    has_provenance: bool,
    comparable: bool,
    convergence: ConvergenceAssessment,
    conservation: ConservationAssessment,
    qoi: QoICheck,
    trend: TrendAssessment | None = None,
    claimed_trend: str | None = None,
    approved_by: str | None = None,
) -> MaturityAssessment:
    """Advance maturity only when all scientific prerequisites are present."""

    if approved_by is not None:
        if not isinstance(approved_by, str) or not approved_by.strip():
            raise ValueError("author identity must be a non-empty string for approval")
        approved_by = approved_by.strip()
    blockers: list[str] = []
    if not has_provenance:
        blockers.append("source provenance is missing")
    if not comparable:
        blockers.append("case comparability is not established")
    if convergence.grade != ConvergenceGrade.STRONG:
        blockers.append("convergence evidence is not strong")
    if not conservation.passes:
        blockers.append("conservation closure is not demonstrated")
    if not qoi.valid:
        blockers.append("QoI definition is incomplete")
    trend_claim_blocked = False
    trend_contradiction = False
    if claimed_trend is not None:
        try:
            claimed_kind = TrendKind(claimed_trend)
        except ValueError:
            blockers.append(f"invalid claimed trend: {claimed_trend}")
            trend_claim_blocked = True
        else:
            if trend is None:
                blockers.append(f"claimed trend {claimed_kind.value} requires trend evidence")
                trend_claim_blocked = True
            elif not trend.supports(claimed_kind):
                blockers.append(
                    f"detected trend {trend.kind.value} does not support {claimed_kind.value}"
                )
                trend_claim_blocked = True
                trend_contradiction = trend.contradicts(claimed_kind)
    verified = not blockers
    if verified:
        level = (
            EvidenceMaturity.AUTHOR_APPROVED
            if approved_by is not None
            else EvidenceMaturity.VERIFIED
        )
    elif has_provenance:
        level = EvidenceMaturity.SCREENED
    else:
        level = EvidenceMaturity.RAW
    return MaturityAssessment(
        level,
        tuple(blockers),
        approval_rejected=approved_by is not None and not verified,
        approved_by=approved_by if verified else None,
        trend_contradiction=trend_contradiction,
        trend_claim_blocked=trend_claim_blocked,
    )


def assess_claim_ceiling(
    *,
    maturity: MaturityAssessment,
    independent_validation: bool,
    engineering_evidence: bool = False,
) -> ClaimCeilingAssessment:
    """Compute the highest claim class supported by the available evidence."""

    reasons: list[str] = []
    if maturity.level == EvidenceMaturity.RAW:
        ceiling = ClaimCeiling.OBSERVATION
        reasons.append("raw evidence supports observation only")
    elif maturity.level == EvidenceMaturity.SCREENED:
        ceiling = ClaimCeiling.ASSOCIATION
        reasons.append("screened evidence does not establish a mechanism")
    else:
        ceiling = ClaimCeiling.MECHANISM
    if independent_validation and maturity.level in {
        EvidenceMaturity.VERIFIED,
        EvidenceMaturity.AUTHOR_APPROVED,
    }:
        ceiling = ClaimCeiling.VALIDATION
    elif not independent_validation:
        reasons.append("independent validation evidence is absent")
    engineering_ready = (
        engineering_evidence
        and independent_validation
        and maturity.level == EvidenceMaturity.AUTHOR_APPROVED
    )
    if engineering_ready:
        ceiling = ClaimCeiling.ENGINEERING
    elif engineering_evidence:
        reasons.append("engineering claim prerequisites are incomplete")
    ceiling_exceeds_association = _CEILING_ORDER[ceiling] > _CEILING_ORDER[ClaimCeiling.ASSOCIATION]
    trend_blocked = maturity.trend_claim_blocked or maturity.trend_contradiction
    if trend_blocked and ceiling_exceeds_association:
        ceiling = ClaimCeiling.ASSOCIATION
        reasons.append("the claimed trend is unsupported or lacks valid trend evidence")
    return ClaimCeilingAssessment(ceiling, tuple(reasons))
