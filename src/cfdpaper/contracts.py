"""Controller-owned public data contracts.

Workstreams may consume these models but changes require controller review.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RecordModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class ProjectManifest(RecordModel):
    project_id: str = Field(min_length=1)
    root: Path
    author_checkpoints: Literal[3] = 3
    created_at: datetime = Field(default_factory=_utc_now)

    @field_validator("root")
    @classmethod
    def validate_root(cls, value: Path) -> Path:
        resolved = value.expanduser().resolve()
        if not resolved.is_dir():
            raise ValueError("project root does not exist or is not a directory")
        return resolved


class SourceRecord(RecordModel):
    source_uri: str = Field(min_length=1)
    locator: str = Field(min_length=1)
    source_hash: str | None = None
    stale: bool = False


class CaseRecord(SourceRecord):
    case_id: str = Field(min_length=1)
    solver: str | None = None
    solver_version: str | None = None
    state: Literal["discovered", "extracted", "validated", "insufficient"] = "discovered"


class BoundaryRecord(SourceRecord):
    boundary_id: str
    case_id: str
    boundary_type: str
    values: dict[str, float | str | None] = Field(default_factory=dict)
    units: dict[str, str] = Field(default_factory=dict)


class MeshRecord(SourceRecord):
    mesh_id: str
    case_id: str
    cell_count: int | None = Field(default=None, ge=0)
    node_count: int | None = Field(default=None, ge=0)
    quality: dict[str, float | None] = Field(default_factory=dict)


class FieldRecord(SourceRecord):
    field_id: str
    case_id: str
    variable: str
    unit: str | None = None
    location: str | None = None


class QoIRecord(SourceRecord):
    qoi_id: str
    case_id: str
    name: str
    value: float | None = None
    unit: str | None = None
    definition: str
    status: Literal["reported", "derived", "missing", "invalid"] = "reported"


class EvidenceRecord(SourceRecord):
    evidence_id: str
    kind: Literal[
        "case",
        "boundary",
        "mesh",
        "field",
        "qoi",
        "convergence",
        "conservation",
        "literature",
        "decision",
        "other",
    ]
    summary: str
    maturity: Literal["raw", "screened", "verified", "author-approved"] = "raw"


class ClaimStatus(str, Enum):
    DRAFT = "draft"
    SUPPORTED = "supported"
    REJECTED = "rejected"
    NEEDS_EVIDENCE = "needs-evidence"


class ClaimRecord(RecordModel):
    claim_id: str
    text: str
    status: ClaimStatus = ClaimStatus.DRAFT
    evidence_ids: list[str] = Field(default_factory=list)
    ceiling: Literal["observation", "association", "mechanism", "validation", "engineering"] = (
        "observation"
    )

    @model_validator(mode="after")
    def supported_claim_has_evidence(self) -> ClaimRecord:
        if self.status == ClaimStatus.SUPPORTED and not self.evidence_ids:
            raise ValueError("supported claim requires evidence")
        return self


class FigureContract(RecordModel):
    figure_id: str
    primary_claim_id: str
    evidence_ids: list[str] = Field(min_length=1)
    panels: list[str] = Field(min_length=1)
    source_data_uri: str
    prohibited_inferences: list[str] = Field(default_factory=list)


class TaskContextPacket(RecordModel):
    task: str
    token_budget: int = Field(ge=128, le=200_000)
    evidence: list[EvidenceRecord] = Field(default_factory=list)
    claims: list[ClaimRecord] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)


class StageResult(RecordModel):
    stage: str
    status: Literal["pending", "running", "blocked", "complete", "approved"]
    outputs: dict[str, Any] = Field(default_factory=dict)
    approved_by: str | None = None
    completed_at: datetime | None = None

    @model_validator(mode="after")
    def approval_is_real(self) -> StageResult:
        if self.status == "approved" and not self.approved_by:
            raise ValueError("author approval requires author identity")
        return self
