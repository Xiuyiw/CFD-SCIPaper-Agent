"""Thin orchestration for the executable V0.3 evidence workflow."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from cfdpaper.contracts import StageResult
from cfdpaper.planning import PlanApproval, PlanReport, run_plan
from cfdpaper.publication.render_figure import FigureDelivery, build_figure_delivery
from cfdpaper.publication.results_paragraph import (
    ParagraphRenderError,
    render_results_paragraph,
)
from cfdpaper.publication.results_paragraph import (
    _validate_inputs as validate_results_paragraph_inputs,
)
from cfdpaper.storage import ProjectStore
from cfdpaper.topic_generation.canonical import canonical_sha256

from .artifacts import (
    ArtifactInputMismatch,
    load_json_model,
    mark_json_artifacts_stale,
    require_current_input,
    write_json_atomic,
)
from .claims import (
    assess_v03_claim_ceiling,
    build_candidate_figure_contract,
    lock_figure_contract,
)
from .comparison import propose_qoi_contract, qualify_comparison
from .models import (
    AuthorApproval,
    CandidateFigureContract,
    CandidateQoIContract,
    CaseDifference,
    ClaimCeilingDecision,
    ConservationObservation,
    ConvergenceObservation,
    LockedQoIContract,
    ObservationTable,
    ParagraphDelivery,
    QoIAnalysis,
    QoIProposal,
    QualificationReport,
    ThresholdBasis,
    VNVStatus,
)
from .observations import (
    ObservationInputError,
    load_observations,
    validate_expected_membership,
)
from .qoi import analyze_qoi, lock_qoi_contract
from .records import GuidedRecords, load_guided_records, persist_guided_records


class WorkflowInputError(ValueError):
    """The requested workflow action lacks a required author or input binding."""


class ScientificEvidenceError(ValueError):
    """The supplied evidence cannot support the requested downstream action."""

    def __init__(self, message: str, issue_code: str = "insufficient-scientific-evidence") -> None:
        super().__init__(message)
        self.issue_code = issue_code


class StaleArtifactError(ValueError):
    """A generated artifact no longer matches its scientific input."""

    def __init__(self, dependency: str, rerun_command: str) -> None:
        super().__init__(f"{dependency} changed; rerun `{rerun_command}` first")
        self.dependency = dependency
        self.rerun_command = rerun_command


class _Question(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    question_id: str
    proposal: QoIProposal


@dataclass(frozen=True)
class QualificationExecution:
    report: QualificationReport
    candidate: CandidateQoIContract
    locked_contract: LockedQoIContract | None = None


@dataclass(frozen=True)
class AnalysisExecution:
    analysis: QoIAnalysis
    ceiling: ClaimCeilingDecision
    candidate_figure: CandidateFigureContract


@dataclass(frozen=True)
class FigureExecution:
    figure_delivery: FigureDelivery


@dataclass(frozen=True)
class ParagraphExecution:
    paragraph_delivery: ParagraphDelivery


def _plan_approval(root: Path) -> PlanApproval:
    path = root / ".cfdpaper" / "outputs" / "plan" / "topic-ranking.json"
    try:
        report = PlanReport.model_validate_json(path.read_bytes())
    except (OSError, ValueError) as error:
        raise WorkflowInputError(
            "Run `cfdpaper plan` and approve a manuscript topic first."
        ) from error
    if report.approval is None or report.approval.scope != "manuscript-topic":
        raise WorkflowInputError("A manuscript-topic approval is required for this action.")
    return report.approval


def _stage_outputs(store: ProjectStore, stage: str) -> dict[str, Any]:
    with store.connect() as connection:
        row = connection.execute(
            "SELECT status, outputs_json FROM stages WHERE stage = ?", (stage,)
        ).fetchone()
    if row is None:
        raise WorkflowInputError(f"Complete the {stage} prerequisite first.")
    try:
        payload = json.loads(str(row["outputs_json"]))
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Stored {stage} state is unreadable.") from error
    if not isinstance(payload, dict):
        raise RuntimeError(f"Stored {stage} state is unreadable.")
    payload["_stage_status"] = str(row["status"])
    return payload


def _save_transition(
    store: ProjectStore,
    *,
    stage: str,
    status: str,
    project_stage: str,
    outputs: dict[str, Any],
    author: str | None = None,
) -> None:
    payload = {key: value for key, value in outputs.items() if key != "_stage_status"}
    identity = canonical_sha256(
        {"stage": stage, "status": status, "outputs": payload, "author": author},
        domain=b"cfdpaper-v03-workflow-checkpoint",
    )
    store.save_workflow_transition(
        StageResult(
            stage=stage,
            status=status,
            outputs=payload,
            approved_by=author,
        ),
        project_stage=project_stage,
        checkpoint_id=f"v03-{stage}-{identity[:20]}",
        checkpoint_stage=f"v03-{stage}",
        checkpoint_payload=payload,
    )


def _status_from_models(records: GuidedRecords, kind: str) -> VNVStatus:
    states = [getattr(model, f"{kind}_status") for model in records.models]
    if not states:
        return VNVStatus(state="not-demonstrated", summary=f"{kind} evidence is unavailable")
    priority = {"demonstrated": 0, "not-applicable": 1, "partial": 2, "not-demonstrated": 3}
    state = max(states, key=priority.__getitem__)
    matching = [model for model in records.models if getattr(model, f"{kind}_status") == state]
    located = state in {"demonstrated", "partial"}
    return VNVStatus(
        state=state,
        summary=f"{kind} is {state} for the declared comparison",
        evidence_ids=(tuple(f"{kind}-{model.model_id}" for model in matching) if located else ()),
        basis="; ".join(getattr(model, f"{kind}_basis") for model in matching) or None,
        source_locator=" | ".join(getattr(model, f"{kind}_locator") for model in matching) or None,
        intended_use_supported=state == "demonstrated",
    )


def _differences(records: GuidedRecords) -> tuple[CaseDifference, ...]:
    values: list[CaseDifference] = []
    for item in records.boundaries:
        name = str(item.values.get("name", item.boundary_type))
        reference = str(item.values.get("reference", "declared reference"))
        candidate = str(item.values.get("candidate", "declared candidate"))
        values.append(
            CaseDifference(
                name=name,
                reference=reference,
                candidate=candidate,
                role=item.comparison_role,
                basis=item.basis,
                source_locator=item.locator if item.basis else None,
            )
        )
    for item in records.models:
        values.append(
            CaseDifference(
                name=f"model for {item.case_id}",
                reference=item.description,
                candidate=item.description,
                role=item.comparison_role,
                basis=item.basis,
                source_locator=item.locator if item.basis else None,
            )
        )
    return tuple(values)


def _assessments(
    records: tuple[Any, ...], model_type: type[ConvergenceObservation]
) -> tuple[ConvergenceObservation, ...]:
    return tuple(
        model_type(
            metric=item.metric,
            observed_value=item.observed_value,
            unit=item.unit,
            threshold=ThresholdBasis(
                metric=item.metric,
                operator=item.operator,
                value=item.threshold_value,
                unit=item.unit,
                basis=item.basis,
                source_locator=item.locator,
                consequence=item.consequence,
            ),
            evidence_id=item.evidence_id,
            source_locator=item.locator,
        )
        for item in records
    )


def _load_material(
    records_path: Path, observations_path: Path, question_path: Path, topic_fingerprint: str
) -> tuple[GuidedRecords, ObservationTable, _Question, QualificationReport, CandidateQoIContract]:
    records = load_guided_records(records_path)
    observations = load_observations(observations_path)
    question = _Question.model_validate_json(question_path.read_bytes())
    validate_expected_membership(observations.rows, question.proposal.expected_members)
    report = qualify_comparison(
        differences=_differences(records),
        verification=_status_from_models(records, "verification"),
        validation=_status_from_models(records, "validation"),
        convergence=_assessments(records.convergence, ConvergenceObservation),
        conservation=_assessments(records.conservation, ConservationObservation),
        observation_table=observations,
    )
    if report.status == "insufficient":
        raise ScientificEvidenceError(
            "The declared comparison is insufficient for QoI analysis.",
            issue_code="failed-blocking-threshold",
        )
    candidate = propose_qoi_contract(
        question_id=question.question_id,
        topic_fingerprint=topic_fingerprint,
        qualification=report,
        observations=observations,
        proposal=question.proposal,
    )
    return records, observations, question, report, candidate


def _input_paths(root: Path) -> tuple[Path, Path, Path, PlanApproval]:
    outputs = _stage_outputs(ProjectStore.open(root), "qualify")
    return (
        Path(outputs["records_path"]),
        Path(outputs["observations_path"]),
        Path(outputs["question_path"]),
        _plan_approval(root),
    )


def _mark_stale(root: Path, dependency: str, rerun_command: str) -> None:
    mark_json_artifacts_stale(
        root,
        (
            "qoi-results.json",
            "claim-ceiling.json",
            "candidate-figure-contract.json",
            "paragraph-duty.json",
            "figure-approval.json",
            "figure-delivery.json",
        ),
        dependency=dependency,
        rerun_command=rerun_command,
    )


def _write_current_json(root: Path, artifact_name: str, value: Any) -> None:
    write_json_atomic(root, artifact_name, value, artifact_status="current")


def _require_current_sources(
    store: ProjectStore,
    records: GuidedRecords,
    *,
    ignore_paths: frozenset[Path] = frozenset(),
) -> None:
    for declared in records.sources:
        try:
            stored = store.get_source(declared.source_uri)
        except KeyError as error:
            raise StaleArtifactError("source files", f'cfdpaper inspect "{store.root}"') from error
        source_path = Path(declared.source_uri)
        if not source_path.is_absolute():
            source_path = store.root / source_path
        source_path = source_path.resolve()
        if source_path in ignore_paths:
            continue
        try:
            stat = source_path.stat()
        except OSError as error:
            raise StaleArtifactError("source files", f'cfdpaper inspect "{store.root}"') from error
        if (
            stored.stale
            or stored.sha256 != declared.sha256
            or stored.size_bytes != declared.size_bytes
            or stat.st_size != stored.size_bytes
            or stat.st_mtime_ns != stored.mtime_ns
        ):
            raise StaleArtifactError("source files", f'cfdpaper inspect "{store.root}"')


def _qualify_rerun(root: Path) -> str:
    outputs = _stage_outputs(ProjectStore.open(root), "qualify")
    return (
        f'cfdpaper qualify "{root}" --records "{outputs["records_path"]}" '
        f'--observations "{outputs["observations_path"]}" '
        f'--question "{outputs["question_path"]}"'
    )


def _changed_dependency(
    stored: CandidateQoIContract,
    current: CandidateQoIContract,
    stored_report: QualificationReport,
    current_report: QualificationReport,
) -> str:
    if stored.observation_input_fingerprint != current.observation_input_fingerprint:
        return "observations"
    if stored.expected_members != current.expected_members:
        return "expected membership"
    if stored.topic_fingerprint != current.topic_fingerprint:
        return "manuscript topic"
    if stored_report.model_dump(exclude={"input_fingerprint"}) != current_report.model_dump(
        exclude={"input_fingerprint"}
    ):
        return "scientific records"
    return "unit definitions"


def _current_material(
    root: Path,
) -> tuple[ObservationTable, QualificationReport, CandidateQoIContract, PlanApproval]:
    records_path, observations_path, question_path, approval = _input_paths(root)
    try:
        _require_current_sources(
            ProjectStore.open(root),
            load_guided_records(records_path),
            ignore_paths=frozenset({observations_path.resolve()}),
        )
    except StaleArtifactError as error:
        _mark_stale(root, error.dependency, error.rerun_command)
        raise
    try:
        _, observations, _, report, candidate = _load_material(
            records_path, observations_path, question_path, approval.plan_fingerprint
        )
    except ObservationInputError as error:
        dependency = (
            "expected membership"
            if error.issue_code
            in {
                "missing-expected-member",
                "duplicate-expected-member",
                "unexpected-member",
            }
            else "observations"
        )
        rerun = _qualify_rerun(root)
        _mark_stale(root, dependency, rerun)
        raise StaleArtifactError(dependency, rerun) from error
    stored = load_json_model(root, "candidate-qoi-contract.json", CandidateQoIContract)
    if candidate != stored:
        stored_report = load_json_model(root, "qualification-report.json", QualificationReport)
        dependency = _changed_dependency(stored, candidate, stored_report, report)
        rerun = _qualify_rerun(root)
        _mark_stale(root, dependency, rerun)
        raise StaleArtifactError(dependency, rerun)
    return observations, report, candidate, approval


def run_qualify(
    root: Path,
    *,
    records_path: Path,
    observations_path: Path,
    question_path: Path,
) -> QualificationExecution:
    root = Path(root).resolve()
    store = ProjectStore.open(root)
    resolved_records = Path(records_path).resolve()
    resolved_observations = Path(observations_path).resolve()
    resolved_question = Path(question_path).resolve()
    records = load_guided_records(resolved_records)
    try:
        _require_current_sources(store, records)
    except StaleArtifactError as error:
        _mark_stale(root, error.dependency, error.rerun_command)
        raise
    persist_guided_records(store, records)
    plan = run_plan(root)
    records, _, _, report, candidate = _load_material(
        resolved_records,
        resolved_observations,
        resolved_question,
        plan.report.plan_fingerprint,
    )
    _write_current_json(root, "qualification-report.json", report)
    _write_current_json(root, "candidate-qoi-contract.json", candidate)
    outputs = {
        "records_path": str(resolved_records),
        "observations_path": str(resolved_observations),
        "question_path": str(resolved_question),
        "qualification_report": str(root / ".cfdpaper/outputs/qualify/qualification-report.json"),
        "candidate_contract": str(root / ".cfdpaper/outputs/qualify/candidate-qoi-contract.json"),
    }
    _save_transition(
        store,
        stage="qualify",
        status="complete",
        project_stage="qualified",
        outputs=outputs,
    )
    return QualificationExecution(report=report, candidate=candidate)


def approve_qoi_contract(root: Path, *, contract_id: str, author: str) -> QualificationExecution:
    root = Path(root).resolve()
    records_path, observations_path, question_path, topic_approval = _input_paths(root)
    if author != topic_approval.author:
        raise WorkflowInputError("The approving author must match the manuscript-topic approval.")
    _, observations, _, report, candidate = _load_material(
        records_path, observations_path, question_path, topic_approval.plan_fingerprint
    )
    stored = load_json_model(root, "candidate-qoi-contract.json", CandidateQoIContract)
    if contract_id != stored.qoi_contract_id:
        raise WorkflowInputError("--approve-contract must identify the current candidate contract.")
    excluded = {
        "qoi_contract_id",
        "topic_fingerprint",
        "scientific_input_fingerprint",
        "fingerprint",
    }
    if stored.model_dump(exclude=excluded) != candidate.model_dump(exclude=excluded):
        dependency = _changed_dependency(
            stored,
            candidate,
            load_json_model(root, "qualification-report.json", QualificationReport),
            report,
        )
        rerun = _qualify_rerun(root)
        _mark_stale(root, dependency, rerun)
        raise StaleArtifactError(dependency, rerun)
    locked = lock_qoi_contract(
        candidate,
        candidate_fingerprint=candidate.fingerprint,
        current_input_fingerprint=candidate.scientific_input_fingerprint,
        topic_approval=topic_approval,
        author=author,
        approved_at=datetime.now(timezone.utc),
    )
    _write_current_json(root, "candidate-qoi-contract.json", candidate)
    _write_current_json(root, "locked-qoi-contract.json", locked)
    store = ProjectStore.open(root)
    outputs = _stage_outputs(store, "qualify")
    outputs["locked_contract"] = str(root / ".cfdpaper/outputs/qualify/locked-qoi-contract.json")
    _save_transition(
        store,
        stage="qualify",
        status="approved",
        project_stage="qoi-approved",
        outputs=outputs,
        author=author,
    )
    return QualificationExecution(report=report, candidate=candidate, locked_contract=locked)


def run_analyze(root: Path) -> AnalysisExecution:
    root = Path(root).resolve()
    store = ProjectStore.open(root)
    if _stage_outputs(store, "qualify").get("_stage_status") != "approved":
        raise WorkflowInputError("Approve the QoI contract before analysis.")
    observations, report, candidate, _ = _current_material(root)
    try:
        locked = load_json_model(root, "locked-qoi-contract.json", LockedQoIContract)
        analysis = analyze_qoi(locked, observations, report)
    except ValueError as error:
        approval = _plan_approval(root)
        rerun = (
            f'cfdpaper qualify "{root}" --approve-qoi-contract '
            f'{candidate.qoi_contract_id} --author "{approval.author}"'
        )
        _mark_stale(root, "locked QoI contract", rerun)
        raise StaleArtifactError("locked QoI contract", rerun) from error
    ceiling = assess_v03_claim_ceiling(report, analysis)
    candidate_figure = build_candidate_figure_contract(
        analysis=analysis,
        qualification=report,
        ceiling=ceiling,
        figure_id="fig-1",
        author=locked.approval.author,
    )
    _write_current_json(root, "qoi-results.json", analysis)
    _write_current_json(root, "claim-ceiling.json", ceiling)
    _write_current_json(root, "candidate-figure-contract.json", candidate_figure)
    _write_current_json(root, "paragraph-duty.json", candidate_figure.paragraph_duty)
    outputs = {
        "analysis": str(root / ".cfdpaper/outputs/qualify/qoi-results.json"),
        "ceiling": str(root / ".cfdpaper/outputs/qualify/claim-ceiling.json"),
        "figure_candidate": str(root / ".cfdpaper/outputs/qualify/candidate-figure-contract.json"),
    }
    _save_transition(
        store,
        stage="analyze",
        status="complete",
        project_stage="analyzed",
        outputs=outputs,
    )
    return AnalysisExecution(analysis=analysis, ceiling=ceiling, candidate_figure=candidate_figure)


def approve_and_render_figure(root: Path, *, contract_id: str, author: str) -> FigureExecution:
    root = Path(root).resolve()
    observations, report, _, topic_approval = _current_material(root)
    analysis = load_json_model(root, "qoi-results.json", QoIAnalysis)
    ceiling = load_json_model(root, "claim-ceiling.json", ClaimCeilingDecision)
    candidate = load_json_model(root, "candidate-figure-contract.json", CandidateFigureContract)
    if contract_id != candidate.figure_id:
        raise WorkflowInputError("--approve-contract must identify the current figure candidate.")
    if author != topic_approval.author:
        raise WorkflowInputError("The approving author must match the manuscript-topic approval.")
    approval = AuthorApproval(
        author=author,
        object_id=candidate.figure_id,
        object_fingerprint=candidate.fingerprint,
        approved_at=datetime.now(timezone.utc),
    )
    contract = lock_figure_contract(
        candidate,
        approval=approval,
        current_qualification=report,
        current_analysis=analysis,
        current_input_fingerprint=analysis.scientific_input_fingerprint,
        source_data_uri=f".cfdpaper/outputs/figure/{candidate.figure_id}/source-data.csv",
    )
    delivery = build_figure_delivery(
        root=root,
        contract=contract,
        candidate=candidate,
        analysis=analysis,
        approval=approval,
    )
    _write_current_json(root, "figure-approval.json", approval)
    _write_current_json(root, "figure-delivery.json", delivery)
    _save_transition(
        ProjectStore.open(root),
        stage="figure",
        status="approved",
        project_stage="figure-approved",
        outputs={"figure_delivery": str(root / ".cfdpaper/outputs/qualify/figure-delivery.json")},
        author=author,
    )
    if ceiling.ceiling.value == "no-numerical-claim" or not observations.rows:
        raise ScientificEvidenceError("The current evidence cannot support a figure.")
    return FigureExecution(figure_delivery=delivery)


def run_write(root: Path, *, artifact: str) -> ParagraphExecution:
    root = Path(root).resolve()
    if artifact != "results-paragraph":
        raise WorkflowInputError("Only --artifact results-paragraph is available in V0.3.")
    _stage_outputs(ProjectStore.open(root), "figure")
    _current_material(root)
    analysis = load_json_model(root, "qoi-results.json", QoIAnalysis)
    ceiling = load_json_model(root, "claim-ceiling.json", ClaimCeilingDecision)
    candidate = load_json_model(root, "candidate-figure-contract.json", CandidateFigureContract)
    delivery = load_json_model(root, "figure-delivery.json", FigureDelivery)
    paragraph = render_results_paragraph(
        duty=candidate.paragraph_duty,
        analysis=analysis,
        ceiling=ceiling,
        candidate=candidate,
        figure_delivery=delivery,
    )
    _save_transition(
        ProjectStore.open(root),
        stage="write",
        status="complete",
        project_stage="written",
        outputs={"artifact": artifact},
    )
    return ParagraphExecution(paragraph_delivery=paragraph)


def approve_final_artifact(root: Path, *, artifact: str, author: str) -> ParagraphExecution:
    root = Path(root).resolve()
    if artifact != "results-paragraph":
        raise WorkflowInputError("Only results-paragraph can be approved in V0.3.")
    topic_approval = _plan_approval(root)
    if author != topic_approval.author:
        raise WorkflowInputError("The approving author must match the manuscript-topic approval.")
    store = ProjectStore.open(root)
    _stage_outputs(store, "write")
    _, _, _, _ = _current_material(root)
    analysis = load_json_model(root, "qoi-results.json", QoIAnalysis)
    ceiling = load_json_model(root, "claim-ceiling.json", ClaimCeilingDecision)
    candidate = load_json_model(root, "candidate-figure-contract.json", CandidateFigureContract)
    figure_delivery = load_json_model(root, "figure-delivery.json", FigureDelivery)
    path = root / ".cfdpaper" / "outputs" / "write" / "delivery.json"
    paragraph = ParagraphDelivery.model_validate_json(path.read_bytes())
    rerun = f'cfdpaper write "{root}" --artifact results-paragraph'
    try:
        require_current_input(
            artifact_name="results paragraph",
            consumed_fingerprint=paragraph.scientific_input_fingerprint,
            current_fingerprint=analysis.scientific_input_fingerprint,
            rerun_command=rerun,
        )
        validate_results_paragraph_inputs(
            duty=candidate.paragraph_duty,
            analysis=analysis,
            ceiling=ceiling,
            candidate=candidate,
            figure_delivery=figure_delivery,
        )
    except (ArtifactInputMismatch, ParagraphRenderError) as error:
        _mark_stale(root, "results paragraph", rerun)
        raise StaleArtifactError("results paragraph", rerun) from error
    _save_transition(
        ProjectStore.open(root),
        stage="write",
        status="approved",
        project_stage="artifact-approved",
        outputs={"artifact": artifact},
        author=author,
    )
    return ParagraphExecution(paragraph_delivery=paragraph)
