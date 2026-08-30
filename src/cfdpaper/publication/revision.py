"""Event-driven revision records and revision-matrix initialization."""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)


class PublicationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class ReviewEvent(PublicationModel):
    """A traceable editorial decision or reviewer report received by the author."""

    event_id: str = Field(min_length=1)
    event_kind: Literal["editorial-decision", "reviewer-report"]
    received_at: datetime
    source_uri: str = Field(min_length=1)
    locator: str = Field(min_length=1)
    source_hash: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
    input_text: str = Field(min_length=1)
    decision: str | None = None

    @field_validator("received_at")
    @classmethod
    def received_at_is_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("review event timestamp must be timezone-aware")
        return value

    @model_validator(mode="after")
    def source_is_real_and_hash_matches(self) -> ReviewEvent:
        source = Path(self.source_uri).expanduser().resolve()
        if not source.is_file():
            raise ValueError("review source does not exist or is not a file")
        if source.stat().st_size == 0:
            raise ValueError("review source is empty")
        actual_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        if actual_hash != self.source_hash.lower():
            raise ValueError("review source hash does not match source_uri")
        try:
            source_text = source.read_text(encoding="utf-8")
        except UnicodeError as error:
            raise ValueError("review source must be UTF-8 text") from error
        if not source_text.strip():
            raise ValueError("review source has no substantive content")
        reviewer_input = self.input_text.strip()
        if not reviewer_input:
            raise ValueError("review input is empty")
        if reviewer_input not in source_text:
            raise ValueError("review input is not present in source")
        return self


class RevisionMatrixEntry(PublicationModel):
    issue_id: str = Field(min_length=1)
    event_id: str = Field(min_length=1)
    reviewer_input: str = Field(min_length=1)
    source_locator: str = Field(min_length=1)
    response: str | None = None
    manuscript_changes: list[str] = Field(default_factory=list)
    manuscript_locations: list[str] = Field(default_factory=list)
    status: Literal["open", "addressed", "declined", "verified"] = "open"


class RevisionMatrix(PublicationModel):
    event_ids: list[str] = Field(min_length=1)
    entries: list[RevisionMatrixEntry] = Field(min_length=1)


class RevisionStartResult(PublicationModel):
    status: Literal["blocked", "ready"]
    reason: str
    matrix: RevisionMatrix | None = None


def start_revision(events: list[object]) -> RevisionStartResult:
    """Start revision only from real, source-traceable editorial/reviewer events."""

    real_events: list[ReviewEvent] = []
    for event in events:
        if not isinstance(event, ReviewEvent):
            continue
        try:
            revalidated = ReviewEvent.model_validate(event.model_dump())
        except ValidationError:
            return RevisionStartResult(
                status="blocked",
                reason="A review event failed source revalidation.",
            )
        real_events.append(revalidated)
    event_ids = [event.event_id for event in real_events]
    duplicate_event_ids = sorted(
        event_id for event_id in set(event_ids) if event_ids.count(event_id) > 1
    )
    if duplicate_event_ids:
        return RevisionStartResult(
            status="blocked",
            reason=f"duplicate review event ID:{duplicate_event_ids[0]}",
        )
    if not real_events:
        return RevisionStartResult(
            status="blocked",
            reason=(
                "Revision requires a real editorial decision or reviewer report; "
                "advisory or generated reviews are insufficient."
            ),
        )

    entries = [
        RevisionMatrixEntry(
            issue_id=f"issue-{index}",
            event_id=event.event_id,
            reviewer_input=event.input_text,
            source_locator=event.locator,
        )
        for index, event in enumerate(real_events, start=1)
    ]
    matrix = RevisionMatrix(
        event_ids=[event.event_id for event in real_events],
        entries=entries,
    )
    return RevisionStartResult(
        status="ready",
        reason="Traceable editorial or reviewer input is available.",
        matrix=matrix,
    )
