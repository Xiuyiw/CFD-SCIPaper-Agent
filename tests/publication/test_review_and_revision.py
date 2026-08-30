import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from cfdpaper.contracts import ClaimRecord, EvidenceRecord
from cfdpaper.publication.review import (
    ExternalAIReview,
    ExternalReviewFinding,
    ExternalReviewPackage,
    ManuscriptExcerpt,
    ReviewImportError,
    export_external_review_package,
    import_external_ai_review,
)
from cfdpaper.publication.revision import ReviewEvent, start_revision


def test_external_review_package_exports_minimal_traceable_context(tmp_path: Path) -> None:
    package = ExternalReviewPackage(
        package_id="review-1",
        manuscript_excerpts=[
            ManuscriptExcerpt(section_id="results", text="A sampled trend was observed.")
        ],
        claims=[
            ClaimRecord(
                claim_id="claim-1",
                text="A sampled trend was observed.",
                evidence_ids=["ev-1"],
                ceiling="observation",
            )
        ],
        evidence=[
            EvidenceRecord(
                evidence_id="ev-1",
                source_uri="synthetic/qoi.csv",
                locator="row:2",
                kind="qoi",
                summary="Sampled response",
                maturity="verified",
            )
        ],
        questions=["Does the wording stay within the evidence ceiling?"],
        exclusions=["Do not infer unsampled operating behavior."],
    )
    output = tmp_path / "external-review-package.json"

    exported = export_external_review_package(package, output)
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert exported == output.resolve()
    assert payload["package_id"] == "review-1"
    assert payload["evidence"][0]["locator"] == "row:2"
    assert "approved_by" not in output.read_text(encoding="utf-8")


def test_external_ai_review_import_is_advisory_only(tmp_path: Path) -> None:
    review_path = tmp_path / "external-review.json"
    review_path.write_text(
        json.dumps(
            {
                "package_id": "review-1",
                "reviewer_model": "external-model",
                "findings": [
                    {
                        "finding_id": "finding-1",
                        "severity": "major",
                        "target": "claim-1",
                        "comment": "The causal wording exceeds the supplied evidence.",
                        "suggested_action": "Use association wording.",
                    }
                ],
                "limitations": ["No access to native solver files."],
                "disposition": "advisory-only",
                "approval_granted": False,
            }
        ),
        encoding="utf-8",
    )

    review = import_external_ai_review(review_path, expected_package_id="review-1")

    assert review.disposition == "advisory-only"
    assert review.approval_granted is False


def test_external_ai_review_cannot_import_a_manufactured_approval(tmp_path: Path) -> None:
    review_path = tmp_path / "external-review.json"
    review_path.write_text(
        json.dumps(
            {
                "package_id": "review-1",
                "reviewer_model": "external-model",
                "findings": [],
                "limitations": [],
                "disposition": "advisory-only",
                "approval_granted": True,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ReviewImportError, match="cannot grant approval"):
        import_external_ai_review(review_path, expected_package_id="review-1")


def test_external_ai_review_defaults_to_no_approval_when_field_is_omitted(
    tmp_path: Path,
) -> None:
    review_path = tmp_path / "external-review.json"
    review_path.write_text(
        json.dumps(
            {
                "package_id": "review-1",
                "reviewer_model": "external-model",
                "findings": [],
                "limitations": [],
            }
        ),
        encoding="utf-8",
    )

    review = import_external_ai_review(review_path, expected_package_id="review-1")

    assert review.approval_granted is False


def test_external_ai_review_rejects_non_object_json(tmp_path: Path) -> None:
    review_path = tmp_path / "external-review.json"
    review_path.write_text("[]", encoding="utf-8")

    with pytest.raises(ReviewImportError, match="must be a JSON object"):
        import_external_ai_review(review_path, expected_package_id="review-1")


def test_external_ai_review_wraps_non_utf8_input(tmp_path: Path) -> None:
    review_path = tmp_path / "external-review.json"
    review_path.write_bytes(b"\xff\xfe\x00")

    with pytest.raises(ReviewImportError, match="external review cannot be read"):
        import_external_ai_review(review_path, expected_package_id="review-1")


def test_revision_is_blocked_without_real_editorial_or_reviewer_input() -> None:
    result = start_revision([])

    assert result.status == "blocked"
    assert result.matrix is None
    assert "real editorial decision or reviewer report" in result.reason


def test_external_ai_review_does_not_start_revision() -> None:
    ai_review = ExternalAIReview(
        package_id="review-1",
        reviewer_model="external-model",
        findings=[
            ExternalReviewFinding(
                finding_id="finding-1",
                severity="minor",
                target="results",
                comment="Clarify the sampling scope.",
            )
        ],
    )

    result = start_revision([ai_review])

    assert result.status == "blocked"
    assert result.matrix is None


def test_real_reviewer_event_starts_traceable_revision_matrix(tmp_path: Path) -> None:
    reviewer_input = "Please quantify sensitivity to the sampled inlet settings."
    source = tmp_path / "reviewer-1.txt"
    source.write_text(reviewer_input, encoding="utf-8")
    event = ReviewEvent(
        event_id="event-1",
        event_kind="reviewer-report",
        received_at=datetime(2026, 8, 29, tzinfo=timezone.utc),
        source_uri=str(source),
        locator="comment:2",
        source_hash=hashlib.sha256(source.read_bytes()).hexdigest(),
        input_text=reviewer_input,
    )

    result = start_revision([event])

    assert result.status == "ready"
    assert result.matrix is not None
    assert result.matrix.entries[0].event_id == "event-1"
    assert result.matrix.entries[0].reviewer_input == event.input_text
    assert result.matrix.entries[0].source_locator == "comment:2"
    assert result.matrix.entries[0].status == "open"
    assert event.received_at == datetime(2026, 8, 29, tzinfo=timezone.utc)


def test_review_event_rejects_nonexistent_source(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="review source does not exist"):
        ReviewEvent(
            event_id="event-1",
            event_kind="reviewer-report",
            received_at=datetime(2026, 8, 29, tzinfo=timezone.utc),
            source_uri=str(tmp_path / "missing.txt"),
            locator="comment:1",
            source_hash="a" * 64,
            input_text="A reviewer comment.",
        )


def test_review_event_rejects_arbitrary_hash(tmp_path: Path) -> None:
    source = tmp_path / "reviewer.txt"
    source.write_text("A reviewer comment.", encoding="utf-8")

    with pytest.raises(ValidationError, match="review source hash does not match"):
        ReviewEvent(
            event_id="event-1",
            event_kind="reviewer-report",
            received_at=datetime(2026, 8, 29, tzinfo=timezone.utc),
            source_uri=str(source),
            locator="comment:1",
            source_hash="a" * 64,
            input_text="A reviewer comment.",
        )


def test_review_event_rejects_empty_source_file(tmp_path: Path) -> None:
    source = tmp_path / "reviewer.txt"
    source.write_bytes(b"")

    with pytest.raises(ValidationError, match="review source is empty"):
        ReviewEvent(
            event_id="event-1",
            event_kind="reviewer-report",
            received_at=datetime(2026, 8, 29, tzinfo=timezone.utc),
            source_uri=str(source),
            locator="comment:1",
            source_hash=hashlib.sha256(b"").hexdigest(),
            input_text="A reviewer comment.",
        )


def test_review_event_rejects_input_not_present_in_source(tmp_path: Path) -> None:
    source = tmp_path / "reviewer.txt"
    source.write_text("The recorded reviewer comment.", encoding="utf-8")

    with pytest.raises(ValidationError, match="review input is not present in source"):
        ReviewEvent(
            event_id="event-1",
            event_kind="reviewer-report",
            received_at=datetime(2026, 8, 29, tzinfo=timezone.utc),
            source_uri=str(source),
            locator="comment:1",
            source_hash=hashlib.sha256(source.read_bytes()).hexdigest(),
            input_text="A fabricated reviewer comment.",
        )


def test_review_event_rejects_whitespace_only_source(tmp_path: Path) -> None:
    source = tmp_path / "reviewer.txt"
    source.write_text("  \n\t", encoding="utf-8")

    with pytest.raises(ValidationError, match="review source has no substantive content"):
        ReviewEvent(
            event_id="event-1",
            event_kind="reviewer-report",
            received_at=datetime(2026, 8, 29, tzinfo=timezone.utc),
            source_uri=str(source),
            locator="comment:1",
            source_hash=hashlib.sha256(source.read_bytes()).hexdigest(),
            input_text="A reviewer comment.",
        )


def test_start_revision_revalidates_source_after_event_creation(tmp_path: Path) -> None:
    reviewer_input = "A recorded reviewer comment."
    source = tmp_path / "reviewer.txt"
    source.write_text(reviewer_input, encoding="utf-8")
    event = ReviewEvent(
        event_id="event-1",
        event_kind="reviewer-report",
        received_at=datetime(2026, 8, 29, tzinfo=timezone.utc),
        source_uri=str(source),
        locator="comment:1",
        source_hash=hashlib.sha256(source.read_bytes()).hexdigest(),
        input_text=reviewer_input,
    )
    source.write_text("tampered after event creation", encoding="utf-8")

    result = start_revision([event])

    assert result.status == "blocked"
    assert result.matrix is None
    assert "failed source revalidation" in result.reason


def test_start_revision_rejects_duplicate_event_ids(tmp_path: Path) -> None:
    reviewer_input = "A recorded reviewer comment."
    source = tmp_path / "reviewer.txt"
    source.write_text(reviewer_input, encoding="utf-8")
    event = ReviewEvent(
        event_id="event-1",
        event_kind="reviewer-report",
        received_at=datetime(2026, 8, 29, tzinfo=timezone.utc),
        source_uri=str(source),
        locator="comment:1",
        source_hash=hashlib.sha256(source.read_bytes()).hexdigest(),
        input_text=reviewer_input,
    )

    result = start_revision([event, event])

    assert result.status == "blocked"
    assert result.matrix is None
    assert "duplicate review event ID:event-1" in result.reason
