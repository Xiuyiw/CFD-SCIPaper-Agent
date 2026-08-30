"""Minimal external-AI review packages with no approval authority."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from cfdpaper.contracts import ClaimRecord, EvidenceRecord


class PublicationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class ManuscriptExcerpt(PublicationModel):
    section_id: str = Field(min_length=1)
    text: str = Field(min_length=1)


class ExternalReviewPackage(PublicationModel):
    package_id: str = Field(min_length=1)
    manuscript_excerpts: list[ManuscriptExcerpt] = Field(min_length=1)
    claims: list[ClaimRecord] = Field(default_factory=list)
    evidence: list[EvidenceRecord] = Field(default_factory=list)
    questions: list[str] = Field(min_length=1)
    exclusions: list[str] = Field(default_factory=list)


class ExternalReviewFinding(PublicationModel):
    finding_id: str = Field(min_length=1)
    severity: Literal["minor", "major", "critical"]
    target: str = Field(min_length=1)
    comment: str = Field(min_length=1)
    suggested_action: str | None = None


class ExternalAIReview(PublicationModel):
    package_id: str = Field(min_length=1)
    reviewer_model: str = Field(min_length=1)
    findings: list[ExternalReviewFinding] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    disposition: Literal["advisory-only"] = "advisory-only"
    approval_granted: Literal[False] = False


class ReviewImportError(ValueError):
    """Raised when an external review is invalid or exceeds advisory authority."""


def export_external_review_package(
    package: ExternalReviewPackage,
    output_path: Path,
) -> Path:
    """Write only bounded excerpts, claims, locators, questions, and exclusions."""

    resolved = output_path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(package.model_dump_json(indent=2), encoding="utf-8")
    return resolved


def import_external_ai_review(
    review_path: Path,
    *,
    expected_package_id: str,
) -> ExternalAIReview:
    """Import advisory findings while rejecting any synthetic approval claim."""

    try:
        raw_text = review_path.expanduser().resolve().read_text(encoding="utf-8")
        raw_payload = json.loads(raw_text)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ReviewImportError(f"external review cannot be read: {error}") from error

    if not isinstance(raw_payload, dict):
        raise ReviewImportError("external review must be a JSON object")

    if "approval_granted" in raw_payload and raw_payload["approval_granted"] is not False:
        raise ReviewImportError("external AI review cannot grant approval")

    try:
        review = ExternalAIReview.model_validate(raw_payload)
    except ValidationError as error:
        raise ReviewImportError(f"external review schema is invalid: {error}") from error

    if review.package_id != expected_package_id:
        raise ReviewImportError(
            f"external review package mismatch:{review.package_id}!={expected_package_id}"
        )
    return review
