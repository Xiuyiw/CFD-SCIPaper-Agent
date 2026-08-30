"""Explicit claim-to-evidence mapping and evidence ceiling enforcement."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from cfdpaper.contracts import ClaimRecord

ClaimCeiling = Literal["observation", "association", "mechanism", "validation", "engineering"]
CEILING_ORDER: dict[str, int] = {
    "observation": 0,
    "association": 1,
    "mechanism": 2,
    "validation": 3,
    "engineering": 4,
}


class PublicationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class EvidenceLink(PublicationModel):
    evidence_id: str = Field(min_length=1)
    role: Literal["supports", "context", "contradicts"]
    note: str | None = None


class ClaimEvidenceMapping(PublicationModel):
    claim_id: str = Field(min_length=1)
    links: list[EvidenceLink] = Field(min_length=1)


class EvidenceCeiling(PublicationModel):
    evidence_id: str = Field(min_length=1)
    ceiling: ClaimCeiling
    rationale: str | None = None


class ClaimCeilingResult(PublicationModel):
    allowed: bool
    declared_ceiling: ClaimCeiling
    effective_ceiling: ClaimCeiling | None = None
    issues: list[str] = Field(default_factory=list)


def check_claim_ceiling(
    claim: ClaimRecord,
    mapping: ClaimEvidenceMapping,
    assessments: list[EvidenceCeiling],
) -> ClaimCeilingResult:
    """Reject claims that exceed their strongest explicitly supporting evidence."""

    issues: list[str] = []
    if mapping.claim_id != claim.claim_id:
        issues.append(f"claim mapping mismatch:{mapping.claim_id}!={claim.claim_id}")

    mapped_ids = {link.evidence_id for link in mapping.links}
    for evidence_id in claim.evidence_ids:
        if evidence_id not in mapped_ids:
            issues.append(f"claim evidence is not mapped:{evidence_id}")

    assessments_by_id = {item.evidence_id: item for item in assessments}
    supporting_links = [link for link in mapping.links if link.role == "supports"]
    if not supporting_links:
        issues.append("claim has no supporting evidence")

    supporting_ceilings: list[ClaimCeiling] = []
    for link in supporting_links:
        if link.evidence_id not in claim.evidence_ids:
            issues.append(f"supporting evidence is absent from claim record:{link.evidence_id}")
            continue
        assessment = assessments_by_id.get(link.evidence_id)
        if assessment is None:
            issues.append(f"missing evidence ceiling:{link.evidence_id}")
        else:
            supporting_ceilings.append(assessment.ceiling)

    effective_ceiling = (
        max(supporting_ceilings, key=lambda item: CEILING_ORDER[item])
        if supporting_ceilings
        else None
    )
    if (
        effective_ceiling is not None
        and CEILING_ORDER[claim.ceiling] > CEILING_ORDER[effective_ceiling]
    ):
        issues.append(
            f"claim ceiling {claim.ceiling} exceeds supporting evidence ceiling {effective_ceiling}"
        )

    return ClaimCeilingResult(
        allowed=not issues,
        declared_ceiling=claim.ceiling,
        effective_ceiling=effective_ceiling,
        issues=issues,
    )
