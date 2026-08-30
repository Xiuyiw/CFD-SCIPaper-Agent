"""Paper-spine and section-level content contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PublicationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class SectionContract(PublicationModel):
    section_id: str = Field(min_length=1)
    role: Literal[
        "abstract",
        "introduction",
        "methods",
        "results",
        "discussion",
        "conclusion",
        "other",
    ]
    title: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    required_claim_ids: list[str] = Field(default_factory=list)
    required_figure_ids: list[str] = Field(default_factory=list)
    prohibited_content: list[str] = Field(default_factory=list)


class PaperSpine(PublicationModel):
    topic_id: str = Field(min_length=1)
    central_claim_id: str = Field(min_length=1)
    sections: list[SectionContract] = Field(min_length=1)

    @model_validator(mode="after")
    def section_ids_are_unique(self) -> PaperSpine:
        section_ids = [section.section_id for section in self.sections]
        if len(section_ids) != len(set(section_ids)):
            raise ValueError("section IDs must be unique")
        return self


class SpineValidationResult(PublicationModel):
    valid: bool
    issues: list[str] = Field(default_factory=list)


def validate_spine(
    spine: PaperSpine,
    *,
    available_claim_ids: set[str],
    available_figure_ids: set[str],
    section_content: dict[str, str] | None = None,
) -> SpineValidationResult:
    """Resolve every section dependency before manuscript assembly begins."""

    issues: list[str] = []
    if spine.central_claim_id not in available_claim_ids:
        issues.append(f"spine missing central claim:{spine.central_claim_id}")
    if not any(spine.central_claim_id in section.required_claim_ids for section in spine.sections):
        issues.append(f"spine central claim is not used by any section:{spine.central_claim_id}")

    for section in spine.sections:
        for claim_id in section.required_claim_ids:
            if claim_id not in available_claim_ids:
                issues.append(f"section:{section.section_id} missing claim:{claim_id}")
        for figure_id in section.required_figure_ids:
            if figure_id not in available_figure_ids:
                issues.append(f"section:{section.section_id} missing figure:{figure_id}")
        if section.prohibited_content:
            content = (section_content or {}).get(section.section_id)
            if content is None:
                issues.append(
                    f"section:{section.section_id} content unavailable for prohibited-content check"
                )
            else:
                lowered_content = content.casefold()
                for prohibited in section.prohibited_content:
                    if prohibited.casefold() in lowered_content:
                        issues.append(
                            f"section:{section.section_id} contains prohibited content:{prohibited}"
                        )

    return SpineValidationResult(valid=not issues, issues=issues)
