"""CFD-Paper-Agent command-line interface."""

from collections.abc import Callable
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from cfdpaper.indexing import ProjectIndexer
from cfdpaper.planning import PlanningError, run_plan
from cfdpaper.state import initialize_project, read_status
from cfdpaper.storage import ProjectStore

app = typer.Typer(no_args_is_help=True, help="Author-in-the-loop CFD paper workflow")
console = Console()


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
) -> None:
    """Rank author-supplied topics against a fast-refreshed evidence snapshot."""

    try:
        execution = run_plan(
            root,
            candidates_path=candidates,
            approve_topic=approve_topic,
            author=author,
        )
    except (FileNotFoundError, PlanningError, RuntimeError) as error:
        raise typer.BadParameter(str(error)) from error
    report = execution.report
    inspection = execution.current_inspection
    console.print(
        f"Plan complete: outcome={report.ranking.outcome}; "
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
    console.print(f"report {execution.report_path}", markup=False, soft_wrap=True)


def _placeholder(name: str) -> None:
    console.print(f"{name}: not implemented in this milestone")
    raise typer.Exit(code=2)


def _placeholder_command(name: str) -> Callable[[], None]:
    def command() -> None:
        _placeholder(name)

    command.__name__ = f"{name}_command"
    return command


for _command_name in (
    "analyze",
    "figure",
    "write",
    "review",
    "revise",
    "export",
):
    app.command(
        _command_name,
        help="Roadmap command; not available in v0.1.0.",
    )(_placeholder_command(_command_name))
