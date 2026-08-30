from pathlib import Path

import pytest
from pydantic import ValidationError

from cfdpaper.contracts import (
    ClaimRecord,
    EvidenceRecord,
    ProjectManifest,
    StageResult,
    TaskContextPacket,
)


def test_project_manifest_requires_existing_project_root(tmp_path: Path) -> None:
    manifest = ProjectManifest(project_id="demo", root=tmp_path)

    assert manifest.root == tmp_path.resolve()
    assert manifest.author_checkpoints == 3


def test_project_manifest_rejects_missing_root(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="project root does not exist"):
        ProjectManifest(project_id="demo", root=tmp_path / "missing")


def test_claim_cannot_be_supported_without_evidence() -> None:
    with pytest.raises(ValidationError, match="supported claim requires evidence"):
        ClaimRecord(
            claim_id="claim-1",
            text="Pressure drop decreases monotonically.",
            status="supported",
            evidence_ids=[],
        )


def test_context_packet_enforces_token_budget_and_keeps_locators() -> None:
    evidence = EvidenceRecord(
        evidence_id="ev-1",
        source_uri="results/cases.csv",
        locator="row:4",
        kind="qoi",
        summary="Pressure drop at case A",
    )
    packet = TaskContextPacket(
        task="compare cases",
        token_budget=500,
        evidence=[evidence],
        exclusions=["stale sources"],
    )

    assert packet.evidence[0].locator == "row:4"
    assert packet.token_budget == 500


def test_stage_result_cannot_report_approval_without_author_identity() -> None:
    with pytest.raises(ValidationError, match="author approval requires author identity"):
        StageResult(stage="topic", status="approved", approved_by=None)
