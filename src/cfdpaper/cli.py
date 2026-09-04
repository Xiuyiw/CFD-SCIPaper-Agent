"""CFD-Paper-Agent command-line interface."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError
from rich.console import Console

from cfdpaper.indexing import ProjectIndexer
from cfdpaper.planning import PlanningError, run_plan
from cfdpaper.qualification.guided import (
    GuidedIntakeCancelled,
    PromptAdapter,
    build_guided_records,
)
from cfdpaper.qualification.records import write_guided_records
from cfdpaper.qualification.service import (
    ScientificEvidenceError,
    StaleArtifactError,
    WorkflowInputError,
    approve_and_render_figure,
    approve_final_artifact,
    approve_qoi_contract,
    run_analyze,
    run_qualify,
    run_write,
)
from cfdpaper.state import initialize_project, read_status
from cfdpaper.storage import ProjectStore
from cfdpaper.topic_generation.artifacts import generation_report_path

app = typer.Typer(no_args_is_help=True, help="Author-in-the-loop CFD paper workflow")
console = Console()


class _TyperPromptAdapter(PromptAdapter):
    def ask(self, key: str, message: str) -> str | None:
        del key
        return typer.prompt(message)


def _workflow_error(error: Exception) -> None:
    issue_code = getattr(error, "issue_code", None)
    message = f"{issue_code}: {error}" if issue_code else str(error)
    console.print(message, markup=False, soft_wrap=True)
    if isinstance(error, StaleArtifactError):
        raise typer.Exit(code=4) from error
    if isinstance(error, ScientificEvidenceError):
        raise typer.Exit(code=3) from error
    if isinstance(error, (json.JSONDecodeError, OSError, UnicodeError)):
        raise typer.Exit(code=2) from error
    if isinstance(
        error,
        (WorkflowInputError, GuidedIntakeCancelled, FileNotFoundError, ValidationError),
    ):
        raise typer.Exit(code=2) from error
    if isinstance(error, ValueError):
        raise typer.Exit(code=3) from error
    raise typer.Exit(code=1) from error


@app.command("init")
def init_project(
    root: Annotated[Path, typer.Argument(exists=True, file_okay=False, resolve_path=True)],
    project_id: Annotated[str, typer.Option("--project-id", help="Stable project identifier")],
) -> None:
    """Initialize local project state without requiring an AI provider."""

    try:
        manifest = initialize_project(root, project_id)
    except (ValueError, RuntimeError) as error:
        raise typer.BadParameter(str(error)) from error
    console.print(f"Initialized [bold]{manifest.project_id}[/bold] at {manifest.root}")


@app.command("status")
def status_project(
    root: Annotated[Path, typer.Argument(exists=True, file_okay=False, resolve_path=True)],
) -> None:
    """Show the resumable project stage."""

    try:
        project_id, stage = read_status(root)
        details = ProjectStore.open(root).status()
    except (FileNotFoundError, RuntimeError) as error:
        raise typer.BadParameter(str(error)) from error
    console.print(
        f"Project [bold]{project_id}[/bold]: {stage}; "
        f"{details.source_count} sources, {details.stale_count} stale, "
        f"{details.chunk_count} chunks; schema v{details.schema_version}"
    )
    console.print(f"checkpoint {details.latest_checkpoint or 'none'}")


@app.command("inspect")
def inspect_project(
    root: Annotated[Path, typer.Argument(exists=True, file_okay=False, resolve_path=True)],
    strict_hash: Annotated[
        bool | None,
        typer.Option(
            "--strict-hash/--fast-hash",
            help="Hash every file; defaults to strict in scientific/publication stages",
        ),
    ] = None,
) -> None:
    """Discover project files and incrementally refresh the offline index."""

    try:
        store = ProjectStore.open(root)
    except (FileNotFoundError, RuntimeError) as error:
        raise typer.BadParameter(str(error)) from error
    indexer = ProjectIndexer(store, strict_hash=strict_hash)
    result = indexer.inspect()
    outputs = {
        "discovered": result.discovered,
        "added": result.added,
        "updated": result.updated,
        "unchanged": result.unchanged,
        "stale": result.stale,
        "strict_hash": indexer.strict_hash,
    }
    store.set_stage("inspected", outputs)
    store.save_checkpoint("inspect", outputs)
    console.print(
        f"Inspection complete: {result.discovered} discovered, {result.added} added, "
        f"{result.updated} updated, {result.unchanged} unchanged, {result.stale} stale"
    )


@app.command("plan")
def plan_project(
    root: Annotated[Path, typer.Argument(exists=True, file_okay=False, resolve_path=True)],
    candidates: Annotated[
        Path | None,
        typer.Option("--candidates", exists=True, dir_okay=False, resolve_path=True),
    ] = None,
    approve_topic: Annotated[str | None, typer.Option("--approve-topic")] = None,
    author: Annotated[str | None, typer.Option("--author")] = None,
    provider: Annotated[str, typer.Option("--provider")] = "offline",
    regenerate: Annotated[bool, typer.Option("--regenerate")] = False,
) -> None:
    """Rank author inputs or evidence-bounded generated topics after a fast inspection."""

    try:
        execution = run_plan(
            root,
            candidates_path=candidates,
            approve_topic=approve_topic,
            author=author,
            provider_mode=provider,
            regenerate=regenerate,
        )
    except (FileNotFoundError, PlanningError, RuntimeError) as error:
        raise typer.BadParameter(str(error)) from error
    report = execution.report
    inspection = execution.current_inspection
    console.print(
        f"Plan complete: source={execution.candidate_source_kind}; "
        f"outcome={report.ranking.outcome}; "
        f"leading={report.leading_topic_id or 'none'}; "
        f"gaps={len(report.ranking.missing_evidence)}; "
        f"approval={report.approval.scope if report.approval else 'none'}",
        markup=False,
    )
    console.print(
        f"inspection=fast: {inspection.discovered} discovered, {inspection.added} added, "
        f"{inspection.updated} updated, {inspection.unchanged} unchanged, "
        f"{inspection.stale} stale; not a strict full hash",
        markup=False,
        soft_wrap=True,
    )
    if execution.approval_invalidated:
        console.print("Previous approval invalidated by project, candidate, or evidence change")
    if execution.generation is not None:
        console.print(
            f"generation={execution.generation.mode}; "
            f"reused={execution.generation.reused}; "
            f"revision={execution.generation.report.generation_revision}; "
            f"candidates={len(execution.generation.candidate_input.candidates)}",
            markup=False,
        )
        if execution.generation.minimum_missing_data:
            console.print(
                "generation-gaps=" + ", ".join(execution.generation.minimum_missing_data),
                markup=False,
                soft_wrap=True,
            )
        console.print(
            f"generation-report {generation_report_path(root)}",
            markup=False,
            soft_wrap=True,
        )
    console.print(f"report {execution.report_path}", markup=False, soft_wrap=True)


@app.command("qualify")
def qualify_project(
    root: Annotated[Path, typer.Argument(exists=True, file_okay=False, resolve_path=True)],
    records: Annotated[Path | None, typer.Option("--records", dir_okay=False)] = None,
    observations: Annotated[Path | None, typer.Option("--observations", dir_okay=False)] = None,
    question: Annotated[Path | None, typer.Option("--question", dir_okay=False)] = None,
    guided: Annotated[bool, typer.Option("--guided")] = False,
    approve_contract: Annotated[str | None, typer.Option("--approve-qoi-contract")] = None,
    author: Annotated[str | None, typer.Option("--author")] = None,
) -> None:
    """Qualify a scientific comparison and approve its QoI contract."""

    try:
        if (approve_contract is None) != (author is None):
            raise WorkflowInputError(
                "--approve-qoi-contract and --author must be supplied together."
            )
        if approve_contract is not None:
            if records is not None or observations is not None or question is not None or guided:
                raise WorkflowInputError(
                    "Contract approval cannot be combined with intake options."
                )
            execution = approve_qoi_contract(
                root, contract_id=approve_contract, author=author or ""
            )
            console.print(
                f"QoI contract approved: {execution.locked_contract.candidate.qoi_contract_id}",
                markup=False,
            )
            return
        if guided and records is not None:
            raise WorkflowInputError("Choose either --records or --guided, not both.")
        if observations is None or question is None:
            raise WorkflowInputError("--observations and --question are required for intake.")
        if guided:
            generated_records = build_guided_records(_TyperPromptAdapter())
            records = root / ".cfdpaper" / "inputs" / "project-records.json"
            write_guided_records(records, generated_records)
        elif records is None:
            raise WorkflowInputError("Choose --records or --guided for scientific intake.")
        execution = run_qualify(
            root,
            records_path=records,
            observations_path=observations,
            question_path=question,
        )
    except Exception as error:
        _workflow_error(error)
    console.print(
        f"Qualification {execution.report.status}; QoI candidate "
        f"{execution.candidate.qoi_contract_id}",
        markup=False,
    )


@app.command("analyze")
def analyze_project(
    root: Annotated[Path, typer.Argument(exists=True, file_okay=False, resolve_path=True)],
) -> None:
    """Analyze the approved QoI over the declared discrete cases."""

    try:
        execution = run_analyze(root)
    except Exception as error:
        _workflow_error(error)
    console.print(
        f"Analysis complete: {execution.analysis.qoi_name}; "
        f"ceiling={execution.ceiling.ceiling.value}; "
        f"figure candidate={execution.candidate_figure.figure_id}",
        markup=False,
    )


@app.command("figure")
def figure_project(
    root: Annotated[Path, typer.Argument(exists=True, file_okay=False, resolve_path=True)],
    contract_id: Annotated[str, typer.Option("--approve-contract")],
    author: Annotated[str, typer.Option("--author")],
) -> None:
    """Approve the current figure contract and render its evidence bundle."""

    try:
        execution = approve_and_render_figure(root, contract_id=contract_id, author=author)
    except Exception as error:
        _workflow_error(error)
    console.print(
        f"Figure ready: {execution.figure_delivery.contract.figure_id}",
        markup=False,
    )


@app.command("write")
def write_project(
    root: Annotated[Path, typer.Argument(exists=True, file_okay=False, resolve_path=True)],
    artifact: Annotated[str, typer.Option("--artifact")] = "results-paragraph",
    approve_final: Annotated[bool, typer.Option("--approve-final")] = False,
    author: Annotated[str | None, typer.Option("--author")] = None,
) -> None:
    """Write or approve the numerically backlinked results paragraph."""

    try:
        if approve_final:
            if author is None:
                raise WorkflowInputError("--approve-final requires --author.")
            execution = approve_final_artifact(root, artifact=artifact, author=author)
            console.print("Final results paragraph approved", markup=False)
            return
        if author is not None:
            raise WorkflowInputError("--author is used only with --approve-final.")
        execution = run_write(root, artifact=artifact)
    except Exception as error:
        _workflow_error(error)
    console.print(
        f"Results paragraph ready for {execution.paragraph_delivery.figure_id}",
        markup=False,
    )


def _placeholder(name: str) -> None:
    console.print(f"{name}: not implemented in this milestone")
    raise typer.Exit(code=2)


def _placeholder_command(name: str) -> Callable[[], None]:
    def command() -> None:
        _placeholder(name)

    command.__name__ = f"{name}_command"
    return command


for _command_name in (
    "review",
    "revise",
    "export",
):
    app.command(
        _command_name,
        help="Roadmap command; not available in v0.3.0.",
    )(_placeholder_command(_command_name))
