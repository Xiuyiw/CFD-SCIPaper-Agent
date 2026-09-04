"""Render one evidence-bound discrete figure and its three QA traces."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import textwrap
import warnings
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any
from xml.etree import ElementTree

from pydantic import ConfigDict, Field, ValidationError

from cfdpaper.contracts import FigureContract
from cfdpaper.qualification.artifacts import figure_output_dir
from cfdpaper.qualification.models import (
    AuthorApproval,
    CandidateFigureContract,
    QoIAnalysis,
)
from cfdpaper.topic_generation.canonical import canonical_sha256

from .figures import (
    FigureArtifact,
    FigureComputedCheck,
    FigureDeliveryValidation,
    PublicationModel,
    QAAssetBinding,
    QAFinding,
    QAResult,
    SourceDataEntry,
    SourceDataManifest,
    source_data_manifest_hash,
    validate_figure_delivery,
)

_SOURCE_FIELDS = (
    "order",
    "case_id",
    "coordinate_name",
    "coordinate_value",
    "coordinate_unit",
    "qoi_contract_id",
    "qoi_name",
    "qoi_value",
    "qoi_unit",
    "result_id",
    "evidence_id",
    "source_locator",
    "trend",
)
_QA_FILES = {
    "data": "qa-data.json",
    "narrative": "qa-narrative.json",
    "visual": "qa-visual.json",
}
_MIN_PNG_WIDTH = 1500
_MIN_PNG_HEIGHT = 900


class FigureRenderError(RuntimeError):
    """Raised when a figure cannot be rendered as the approved candidate."""


class FigureDeliveryManifest(PublicationModel):
    """Build-time identity and hashes for one deterministic figure delivery."""

    figure_id: str = Field(min_length=1)
    contract: FigureContract
    candidate_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    analysis_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    scientific_input_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    files: dict[str, str]


class FigureDelivery(PublicationModel):
    """Materialized V0.3 figure bundle and its computed validation result."""

    model_config = ConfigDict(
        extra="forbid", validate_assignment=True, arbitrary_types_allowed=True
    )

    output_dir: Path
    source_data_path: Path
    script_path: Path
    svg_path: Path
    png_path: Path
    caption_path: Path
    delivery_path: Path
    qa_paths: tuple[Path, Path, Path]
    contract: FigureContract
    manifest: SourceDataManifest
    delivery_manifest: FigureDeliveryManifest
    artifacts: tuple[FigureArtifact, FigureArtifact]
    qa_results: tuple[QAResult, QAResult, QAResult]
    validation: FigureDeliveryValidation


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _expected_source_rows(
    candidate: CandidateFigureContract,
    analysis: QoIAnalysis,
) -> list[dict[str, str]]:
    trend = analysis.trend.value if analysis.trend is not None else "insufficient"
    return [
        {
            "order": str(index),
            "case_id": value.case_id,
            "coordinate_name": analysis.coordinate_name,
            "coordinate_value": format(value.coordinate_value, ".17g"),
            "coordinate_unit": value.coordinate_unit,
            "qoi_contract_id": analysis.qoi_contract_id,
            "qoi_name": analysis.qoi_name,
            "qoi_value": format(value.value, ".17g"),
            "qoi_unit": value.unit,
            "result_id": value.result_id,
            "evidence_id": value.evidence_id,
            "source_locator": value.source_locator,
            "trend": trend,
        }
        for index, value in enumerate(analysis.values, start=1)
    ]


def _verify_inputs(
    *,
    contract: FigureContract,
    candidate: CandidateFigureContract,
    analysis: QoIAnalysis,
    approval: AuthorApproval,
) -> None:
    expected_candidate_fingerprint = canonical_sha256(
        candidate.model_dump(mode="python", exclude={"fingerprint"}),
        domain=b"cfdpaper-v03-candidate-figure-contract",
    )
    if candidate.fingerprint != expected_candidate_fingerprint:
        raise FigureRenderError("candidate content does not match its fingerprint")
    if (
        approval.author != candidate.author
        or approval.object_id != candidate.figure_id
        or approval.object_fingerprint != candidate.fingerprint
    ):
        raise FigureRenderError("approval is not bound to the figure candidate")
    analysis_fingerprint = canonical_sha256(analysis, domain=b"cfdpaper-v03-qoi-analysis")
    if candidate.analysis_fingerprint != analysis_fingerprint:
        raise FigureRenderError("candidate does not match the current QoI analysis")
    if candidate.scientific_input_fingerprint != analysis.scientific_input_fingerprint:
        raise FigureRenderError("candidate scientific input is stale")
    panel = candidate.panels[0]
    if panel.case_order != tuple(value.case_id for value in analysis.values):
        raise FigureRenderError("candidate case order does not match the locked QoI")
    if panel.x_values != tuple(value.coordinate_value for value in analysis.values):
        raise FigureRenderError("candidate coordinates do not match the locked QoI")
    expected_source_uri = f".cfdpaper/outputs/figure/{candidate.figure_id}/source-data.csv"
    if contract.source_data_uri != expected_source_uri:
        raise FigureRenderError("figure contract source-data path is not deterministic")
    if (
        contract.figure_id != candidate.figure_id
        or contract.primary_claim_id != candidate.primary_claim.claim_id
        or contract.evidence_ids != list(candidate.evidence_ids)
        or contract.panels != [panel.panel_id]
        or contract.prohibited_inferences != list(candidate.prohibited_inferences)
    ):
        raise FigureRenderError("figure contract does not match the approved candidate")


def _write_source_data(path: Path, rows: list[dict[str, str]]) -> None:
    temporary = path.with_suffix(".csv.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=_SOURCE_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _script_text(figure_id: str) -> str:
    return textwrap.dedent(
        f'''\
        """Standalone discrete figure generated by CFD-Paper-Agent."""

        from __future__ import annotations

        import csv
        from pathlib import Path

        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt


        SOURCE_DATA = Path(__file__).with_name("source-data.csv")
        FIGURE_ID = {figure_id!r}
        FIGURE_SIZE = (6.5, 4.2)
        DPI = 300
        MARKER_STYLE = "o"
        MARKER_SIZE = 38
        LINE_STYLE = "-"
        LINE_WIDTH = 0.9
        CASE_LABEL_OFFSET = 8


        def load_source_data() -> list[dict[str, str]]:
            with SOURCE_DATA.open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            return sorted(rows, key=lambda row: int(row["order"]))


        def create_figure(rows: list[dict[str, str]]):
            if not rows:
                raise ValueError("source-data.csv contains no plotted rows")
            x_values = [float(row["coordinate_value"]) for row in rows]
            y_values = [float(row["qoi_value"]) for row in rows]

            plt.rcParams.update({{
                "font.family": "serif",
                "font.serif": ["DejaVu Serif", "Times New Roman"],
                "font.size": 10,
                "axes.labelsize": 11,
                "axes.titlesize": 11,
                "xtick.labelsize": 9,
                "ytick.labelsize": 9,
                "legend.fontsize": 9,
                "svg.fonttype": "none",
                "svg.hashsalt": "cfdpaper-v03",
            }})
            fig, ax = plt.subplots(figsize=FIGURE_SIZE, constrained_layout=True)
            ax.plot(
                x_values,
                y_values,
                color="#64748B",
                linestyle=LINE_STYLE,
                linewidth=LINE_WIDTH,
                alpha=0.65,
                zorder=1,
                label="Observed discrete values",
            )
            ax.scatter(
                x_values,
                y_values,
                s=MARKER_SIZE,
                marker=MARKER_STYLE,
                facecolor="white",
                edgecolor="#1F4E79",
                linewidth=1.2,
                zorder=2,
            )
            annotations = [
                ax.annotate(
                    row["case_id"],
                    (x_value, y_value),
                    xytext=(0, CASE_LABEL_OFFSET),
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                    fontsize=8.5,
                    clip_on=False,
                )
                for row, x_value, y_value in zip(rows, x_values, y_values, strict=True)
            ]
            ax.set_xlabel(f'{{rows[0]["coordinate_name"]}} ({{rows[0]["coordinate_unit"]}})')
            ax.set_ylabel(f'{{rows[0]["qoi_name"]}} ({{rows[0]["qoi_unit"]}})')
            ax.set_title(rows[0]["qoi_name"])
            ax.margins(x=0.08, y=0.18)
            x_ticks = ax.get_xticks()
            lower_ticks = [tick for tick in x_ticks if tick <= min(x_values)]
            upper_ticks = [tick for tick in x_ticks if tick >= max(x_values)]
            if lower_ticks and upper_ticks:
                ax.set_xlim(max(lower_ticks), min(upper_ticks))
            ax.grid(True, which="major", color="#D9DEE5", linewidth=0.55, alpha=0.75)
            ax.set_axisbelow(True)
            legend = ax.legend(frameon=False, loc="best")
            return fig, ax, annotations, legend


        def main() -> None:
            rows = load_source_data()
            fig, _, _, _ = create_figure(rows)
            destination = Path(__file__).parent
            fig.savefig(
                destination / f"{{FIGURE_ID}}.svg",
                format="svg",
                bbox_inches="tight",
                pad_inches=0.04,
                metadata={{"Date": None}},
            )
            fig.savefig(
                destination / f"{{FIGURE_ID}}.png",
                format="png",
                dpi=DPI,
                bbox_inches="tight",
                pad_inches=0.04,
                facecolor="white",
                metadata={{"Software": "CFD-Paper-Agent"}},
            )
            plt.close(fig)


        if __name__ == "__main__":
            main()
        '''
    )


def _write_script(path: Path, figure_id: str) -> None:
    path.write_text(_script_text(figure_id), encoding="utf-8")


def _bundle_paths(output: Path, figure_id: str) -> dict[str, Path]:
    return {
        "source-data.csv": output / "source-data.csv",
        f"plot_{figure_id}.py": output / f"plot_{figure_id}.py",
        f"{figure_id}.svg": output / f"{figure_id}.svg",
        f"{figure_id}.png": output / f"{figure_id}.png",
        "caption.txt": output / "caption.txt",
        "qa-data.json": output / "qa-data.json",
        "qa-narrative.json": output / "qa-narrative.json",
        "qa-visual.json": output / "qa-visual.json",
        "delivery.json": output / "delivery.json",
    }


def _caption_text(candidate: CandidateFigureContract) -> str:
    panel = candidate.panels[0]
    return (
        f"{panel.y_variable} versus {panel.x_variable} for the observed discrete cases. "
        "Markers denote the reported values; the line is a visual guide only.\n"
    )


def _write_delivery_manifest(path: Path, manifest: FigureDeliveryManifest) -> None:
    path.write_text(
        json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _run_script(script_path: Path) -> None:
    environment = os.environ.copy()
    environment["MPLBACKEND"] = "Agg"
    completed = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=script_path.parent,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown error"
        raise FigureRenderError(f"standalone figure script failed: {detail}")


def _read_source_data(path: Path) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    try:
        with path.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            fields = tuple(reader.fieldnames or ())
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error):
        return (), []
    return fields, rows


def _png_dimensions(path: Path) -> tuple[int, int] | None:
    try:
        content = path.read_bytes()
    except OSError:
        return None
    if len(content) < 24 or not content.startswith(b"\x89PNG\r\n\x1a\n"):
        return None
    return int.from_bytes(content[16:20], "big"), int.from_bytes(content[20:24], "big")


def _svg_text(path: Path) -> str | None:
    try:
        root = ElementTree.parse(path).getroot()
    except (ElementTree.ParseError, OSError):
        return None
    if root.tag.rsplit("}", maxsplit=1)[-1] != "svg":
        return None
    return " ".join(root.itertext())


def _load_plot_module(script_path: Path) -> ModuleType:
    name = f"_cfdpaper_figure_{hashlib.sha256(str(script_path).encode()).hexdigest()[:12]}"
    module = ModuleType(name)
    module.__file__ = str(script_path)
    source = script_path.read_text(encoding="utf-8")
    exec(compile(source, script_path, "exec"), module.__dict__)
    return module


def _layout_is_inside_figure(script_path: Path) -> bool:
    try:
        module = _load_plot_module(script_path)
        rows = module.load_source_data()
        figure, axis, annotations, legend = module.create_figure(rows)
        with warnings.catch_warnings(record=True) as layout_warnings:
            warnings.simplefilter("always")
            figure.canvas.draw()
        renderer = figure.canvas.get_renderer()
        figure_bounds = figure.bbox
        fixed_artists = [
            axis,
            axis.title,
            axis.xaxis.label,
            axis.yaxis.label,
            legend,
            *annotations,
        ]
        tick_artists = [*axis.get_xticklabels(), *axis.get_yticklabels()]

        def fully_inside(artist: Any) -> bool:
            bounds = artist.get_window_extent(renderer)
            lower_left, upper_right = bounds.get_points()
            return figure_bounds.contains(*lower_left) and figure_bounds.contains(*upper_right)

        layout_failed = any(
            "constrained_layout not applied" in str(item.message) for item in layout_warnings
        )
        inside = (
            not layout_failed
            and all(
                fully_inside(artist)
                for artist in fixed_artists
                if artist is not None and artist.get_visible()
            )
            and all(
                fully_inside(artist)
                for artist in tick_artists
                if artist.get_visible()
                and artist.get_window_extent(renderer).overlaps(figure_bounds)
            )
        )
        module.plt.close(figure)
        return inside
    except Exception:
        return False


def _check(check_id: str, passed: bool, success: str, failure: str) -> FigureComputedCheck:
    return FigureComputedCheck(
        check_id=check_id,
        status="pass" if passed else "fail",
        detail=success if passed else failure,
    )


def _qa_result(
    *,
    dimension: str,
    checks: list[FigureComputedCheck],
    findings: list[QAFinding],
    script_path: Path,
    source_binding: QAAssetBinding,
    artifact_bindings: list[QAAssetBinding],
    manifest: SourceDataManifest,
) -> QAResult:
    return QAResult(
        dimension=dimension,
        computed_checks=checks,
        findings=findings,
        executor="cfdpaper",
        tool="v0.3-figure-qa",
        timestamp=datetime.now(timezone.utc),
        source=script_path,
        source_hash=_sha256(script_path),
        source_data_bindings=[source_binding],
        artifact_bindings=artifact_bindings,
        manifest_hash=source_data_manifest_hash(manifest),
    )


def _build_data_qa(
    *,
    path: Path,
    expected_rows: list[dict[str, str]],
    script_path: Path,
    source_binding: QAAssetBinding,
    artifact_bindings: list[QAAssetBinding],
    manifest: SourceDataManifest,
) -> QAResult:
    fields, rows = _read_source_data(path)
    columns_match = fields == _SOURCE_FIELDS
    rows_match = rows == expected_rows
    checks = [
        _check(
            "source-columns",
            columns_match,
            "source-data columns match the locked figure schema",
            "source-data columns differ from the locked figure schema",
        ),
        _check(
            "source-rows",
            rows_match,
            "source-data rows preserve locked order, values, units, and locators",
            "source-data rows differ from the locked order, values, units, or locators",
        ),
    ]
    findings = []
    if not columns_match or not rows_match:
        findings.append(
            QAFinding(
                finding_id="data-binding-mismatch",
                severity="blocking",
                detail="Plotted source data no longer matches the locked QoI analysis.",
            )
        )
    return _qa_result(
        dimension="data",
        checks=checks,
        findings=findings,
        script_path=script_path,
        source_binding=source_binding,
        artifact_bindings=artifact_bindings,
        manifest=manifest,
    )


def _narrative_numbers_are_bound(candidate: CandidateFigureContract, analysis: QoIAnalysis) -> bool:
    text = candidate.primary_claim.text
    numeric_tokens = []
    current = ""
    for character in text:
        if character.isdigit() or character in ".-+eE":
            current += character
        elif current:
            try:
                numeric_tokens.append(float(current))
            except ValueError:
                pass
            current = ""
    if current:
        try:
            numeric_tokens.append(float(current))
        except ValueError:
            pass
    known_values = {value.value for value in analysis.values}
    return all(number in known_values for number in numeric_tokens) and set(
        candidate.numeric_backlink_ids
    ).issuperset(value.result_id for value in analysis.values)


def _build_narrative_qa(
    *,
    candidate: CandidateFigureContract,
    analysis: QoIAnalysis,
    caption_text: str,
    script_path: Path,
    source_binding: QAAssetBinding,
    artifact_bindings: list[QAAssetBinding],
    manifest: SourceDataManifest,
) -> QAResult:
    text = " ".join((candidate.primary_claim.text, candidate.caption_duty, caption_text)).casefold()
    prohibited = [phrase for phrase in candidate.prohibited_inferences if phrase in text]
    if "continuous" in text and re.search(r"\boptim(?:al|um)\b", text):
        prohibited.append("continuous optimum")
    if re.search(r"\b(?:safe|operating|operational)\s+boundar(?:y|ies)\b", text):
        prohibited.append("operating boundary")
    upward = re.search(
        r"\b(?:increase(?:d|s|ing)?|rise|rises|rose|risen|rising|grew|grows|growing)\b",
        text,
    )
    downward = re.search(
        r"\b(?:decrease(?:d|s|ing)?|fall|falls|fell|fallen|falling|decline(?:d|s|ing)?)\b",
        text,
    )
    first_value = analysis.values[0].value
    last_value = analysis.values[-1].value
    direction_matches = not (
        (last_value > first_value and downward)
        or (last_value < first_value and upward)
        or (last_value == first_value and (upward or downward))
    )
    numbers_bound = _narrative_numbers_are_bound(candidate, analysis)
    claim_bound = candidate.primary_claim.claim_id == candidate.paragraph_duty.claim_id
    checks = [
        _check(
            "claim-boundary",
            claim_bound,
            "claim and paragraph duty remain bound",
            "claim and paragraph duty are not bound",
        ),
        _check(
            "trend-wording",
            direction_matches,
            "trend wording matches the locked discrete trend",
            "trend wording contradicts the locked discrete trend",
        ),
        _check(
            "prohibited-inference",
            not prohibited,
            "no prohibited continuous or boundary inference is present",
            "prohibited inference wording is present",
        ),
        _check(
            "numeric-backlinks",
            numbers_bound,
            "reported numbers are bound to locked QoI results",
            "a reported number lacks a locked QoI backlink",
        ),
    ]
    findings = []
    if not all(check.status == "pass" for check in checks):
        findings.append(
            QAFinding(
                finding_id="narrative-boundary-failure",
                severity="blocking",
                detail="Figure wording exceeds or contradicts its locked evidence boundary.",
            )
        )
    return _qa_result(
        dimension="narrative",
        checks=checks,
        findings=findings,
        script_path=script_path,
        source_binding=source_binding,
        artifact_bindings=artifact_bindings,
        manifest=manifest,
    )


def _build_visual_qa(
    *,
    candidate: CandidateFigureContract,
    svg_path: Path,
    png_path: Path,
    script_path: Path,
    source_binding: QAAssetBinding,
    artifact_bindings: list[QAAssetBinding],
    manifest: SourceDataManifest,
) -> QAResult:
    panel = candidate.panels[0]
    svg_text = _svg_text(svg_path)
    dimensions = _png_dimensions(png_path)
    expected_text = (
        panel.x_variable,
        panel.x_unit,
        panel.y_variable,
        panel.y_unit,
        *panel.case_order,
    )
    labels_present = svg_text is not None and all(item in svg_text for item in expected_text)
    dimensions_pass = dimensions is not None and (
        dimensions[0] >= _MIN_PNG_WIDTH and dimensions[1] >= _MIN_PNG_HEIGHT
    )
    script_text = script_path.read_text(encoding="utf-8") if script_path.is_file() else ""
    semantics_present = all(
        token in script_text for token in ("MARKER_STYLE", "LINE_STYLE", "ax.plot", "ax.scatter")
    )
    layout_pass = _layout_is_inside_figure(script_path)
    checks = [
        _check(
            "svg-text",
            labels_present,
            "SVG reopens with all labels, units, and cases",
            "SVG is invalid or is missing a required label, unit, or case",
        ),
        _check(
            "png-dimensions",
            dimensions_pass,
            "PNG reopens at the required publication-preview dimensions",
            "PNG is invalid or smaller than the required preview dimensions",
        ),
        _check(
            "marker-line-semantics",
            semantics_present,
            "script declares separate discrete-marker and light-line semantics",
            "script does not declare the required marker and line semantics",
        ),
        _check(
            "artist-bounds",
            layout_pass,
            "drawn title, axes, ticks, legend, and annotations remain inside the figure",
            "a drawn title, axis, tick, legend, or annotation is clipped",
        ),
    ]
    findings = []
    if not all(check.status == "pass" for check in checks):
        findings.append(
            QAFinding(
                finding_id="visual-structure-failure",
                severity="blocking",
                detail="A rendered label or annotation is clipped or structurally invalid.",
            )
        )
    else:
        findings.append(
            QAFinding(
                finding_id="author-visual-review",
                severity="info",
                detail="Automated structural QA does not replace author aesthetic review.",
            )
        )
    return _qa_result(
        dimension="visual",
        checks=checks,
        findings=findings,
        script_path=script_path,
        source_binding=source_binding,
        artifact_bindings=artifact_bindings,
        manifest=manifest,
    )


def _write_qa(path: Path, result: QAResult) -> None:
    path.write_text(
        json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _required_file_validation(paths: dict[str, Path]) -> FigureDeliveryValidation | None:
    checks = []
    issues = []
    for name, path in paths.items():
        present = path.is_file() and path.stat().st_size > 0
        checks.append(
            _check(
                f"delivery-file:{name}",
                present,
                f"required delivery file is present:{name}",
                f"required delivery file is missing or empty:{name}",
            )
        )
        if not present:
            issues.append(f"required delivery file is missing or empty:{name}")
    if not issues:
        return None
    return FigureDeliveryValidation(
        valid=False,
        issues=issues,
        computed_checks=checks,
        qa_results=[],
    )


def _bundle_components(
    *,
    root: Path,
    candidate: CandidateFigureContract,
    analysis: QoIAnalysis,
) -> tuple[
    SourceDataManifest,
    tuple[FigureArtifact, FigureArtifact],
    tuple[QAResult, QAResult, QAResult],
]:
    output = figure_output_dir(root, candidate.figure_id, create=False)
    paths = _bundle_paths(output, candidate.figure_id)
    source_path = paths["source-data.csv"]
    script_path = paths[f"plot_{candidate.figure_id}.py"]
    svg_path = paths[f"{candidate.figure_id}.svg"]
    png_path = paths[f"{candidate.figure_id}.png"]
    _, rows = _read_source_data(source_path)
    manifest = SourceDataManifest(
        figure_id=candidate.figure_id,
        entries=[
            SourceDataEntry(
                data_id=candidate.panels[0].panel_id,
                path=source_path,
                evidence_ids=list(candidate.evidence_ids),
                row_count=len(rows),
                sha256=_sha256(source_path),
            )
        ],
    )
    artifacts = (
        FigureArtifact(path=svg_path, role="editable"),
        FigureArtifact(path=png_path, role="preview"),
    )
    source_binding = QAAssetBinding(uri=source_path, sha256=_sha256(source_path))
    artifact_bindings = [
        QAAssetBinding(uri=artifact.path, sha256=_sha256(artifact.path)) for artifact in artifacts
    ]
    expected_rows = _expected_source_rows(candidate, analysis)
    caption_text = paths["caption.txt"].read_text(encoding="utf-8")
    qa_results = (
        _build_data_qa(
            path=source_path,
            expected_rows=expected_rows,
            script_path=script_path,
            source_binding=source_binding,
            artifact_bindings=artifact_bindings,
            manifest=manifest,
        ),
        _build_narrative_qa(
            candidate=candidate,
            analysis=analysis,
            caption_text=caption_text,
            script_path=script_path,
            source_binding=source_binding,
            artifact_bindings=artifact_bindings,
            manifest=manifest,
        ),
        _build_visual_qa(
            candidate=candidate,
            svg_path=svg_path,
            png_path=png_path,
            script_path=script_path,
            source_binding=source_binding,
            artifact_bindings=artifact_bindings,
            manifest=manifest,
        ),
    )
    return manifest, artifacts, qa_results


def _delivery_manifest_issues(
    *,
    delivery: FigureDeliveryManifest,
    paths: dict[str, Path],
    contract: FigureContract,
    candidate: CandidateFigureContract,
    analysis: QoIAnalysis,
) -> list[str]:
    issues = []
    if delivery.figure_id != candidate.figure_id:
        issues.append("delivery figure ID does not match the current candidate")
    if delivery.contract != contract:
        issues.append("delivery contract does not match the locked contract")
    if delivery.candidate_fingerprint != candidate.fingerprint:
        issues.append("delivery candidate fingerprint does not match")
    expected_analysis = canonical_sha256(analysis, domain=b"cfdpaper-v03-qoi-analysis")
    if delivery.analysis_fingerprint != expected_analysis:
        issues.append("delivery QoI analysis fingerprint does not match")
    if delivery.scientific_input_fingerprint != analysis.scientific_input_fingerprint:
        issues.append("delivery scientific input fingerprint does not match")
    expected_names = set(paths) - {"delivery.json"}
    if set(delivery.files) != expected_names:
        issues.append("delivery file list does not match the required figure bundle")
    for name in sorted(expected_names & set(delivery.files)):
        if _sha256(paths[name]) != delivery.files[name]:
            issues.append(f"delivery file hash mismatch:{name}")
    return issues


def validate_rendered_figure(
    *,
    root: Path,
    contract: FigureContract,
    candidate: CandidateFigureContract,
    analysis: QoIAnalysis,
) -> FigureDeliveryValidation:
    """Reopen and validate a materialized figure against its locked QoI inputs."""

    output = figure_output_dir(root, candidate.figure_id, create=False)
    paths = _bundle_paths(output, candidate.figure_id)
    missing = _required_file_validation(paths)
    if missing is not None:
        return missing
    try:
        delivery_manifest = FigureDeliveryManifest.model_validate_json(
            paths["delivery.json"].read_bytes()
        )
    except (OSError, ValidationError, ValueError) as error:
        return FigureDeliveryValidation(
            valid=False,
            issues=[f"delivery manifest cannot be reopened:{error}"],
        )
    issues = _delivery_manifest_issues(
        delivery=delivery_manifest,
        paths=paths,
        contract=contract,
        candidate=candidate,
        analysis=analysis,
    )
    try:
        persisted_qa = tuple(
            QAResult.model_validate_json(paths[name].read_bytes())
            for name in ("qa-data.json", "qa-narrative.json", "qa-visual.json")
        )
    except (OSError, ValidationError, ValueError) as error:
        persisted_qa = ()
        issues.append(f"QA trace cannot be reopened:{error}")
    manifest, artifacts, current_qa = _bundle_components(
        root=root,
        candidate=candidate,
        analysis=analysis,
    )
    public_validation = validate_figure_delivery(
        contract,
        manifest,
        list(artifacts),
        list(persisted_qa),
    )
    issues.extend(public_validation.issues)
    issues.extend(
        f"current {result.dimension} QA did not pass"
        for result in current_qa
        if result.status != "pass"
    )
    return FigureDeliveryValidation(
        valid=not issues,
        issues=issues,
        computed_checks=public_validation.computed_checks,
        qa_results=list(current_qa),
    )


def build_figure_delivery(
    *,
    root: Path,
    contract: FigureContract,
    candidate: CandidateFigureContract,
    analysis: QoIAnalysis,
    approval: AuthorApproval,
) -> FigureDelivery:
    """Write the minimal V0.3 figure bundle after exact approval binding."""

    _verify_inputs(
        contract=contract,
        candidate=candidate,
        analysis=analysis,
        approval=approval,
    )
    output = figure_output_dir(root, candidate.figure_id, create=True)
    paths = _bundle_paths(output, candidate.figure_id)
    source_path = paths["source-data.csv"]
    script_path = paths[f"plot_{candidate.figure_id}.py"]
    svg_path = paths[f"{candidate.figure_id}.svg"]
    png_path = paths[f"{candidate.figure_id}.png"]
    _write_source_data(source_path, _expected_source_rows(candidate, analysis))
    _write_script(script_path, candidate.figure_id)
    paths["caption.txt"].write_text(_caption_text(candidate), encoding="utf-8")
    _run_script(script_path)
    manifest, artifacts, qa_results = _bundle_components(
        root=root,
        candidate=candidate,
        analysis=analysis,
    )
    qa_paths = tuple(paths[_QA_FILES[result.dimension]] for result in qa_results)
    for path, result in zip(qa_paths, qa_results, strict=True):
        _write_qa(path, result)
    reloaded_qa = tuple(QAResult.model_validate_json(path.read_bytes()) for path in qa_paths)
    delivery_manifest = FigureDeliveryManifest(
        figure_id=candidate.figure_id,
        contract=contract,
        candidate_fingerprint=candidate.fingerprint,
        analysis_fingerprint=canonical_sha256(analysis, domain=b"cfdpaper-v03-qoi-analysis"),
        scientific_input_fingerprint=analysis.scientific_input_fingerprint,
        files={name: _sha256(path) for name, path in paths.items() if name != "delivery.json"},
    )
    _write_delivery_manifest(paths["delivery.json"], delivery_manifest)
    validation = validate_rendered_figure(
        root=root,
        contract=contract,
        candidate=candidate,
        analysis=analysis,
    )
    if not validation.valid:
        raise FigureRenderError("; ".join(validation.issues))
    return FigureDelivery(
        output_dir=output,
        source_data_path=source_path,
        script_path=script_path,
        svg_path=svg_path,
        png_path=png_path,
        caption_path=paths["caption.txt"],
        delivery_path=paths["delivery.json"],
        qa_paths=qa_paths,
        contract=contract,
        manifest=manifest,
        delivery_manifest=delivery_manifest,
        artifacts=artifacts,
        qa_results=reloaded_qa,
        validation=validation,
    )
