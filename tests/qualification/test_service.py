from __future__ import annotations

import hashlib
import json
from pathlib import Path

from cfdpaper.indexing import ProjectIndexer
from cfdpaper.planning import run_plan
from cfdpaper.qualification.models import V03ClaimCeiling
from cfdpaper.qualification.service import (
    approve_and_render_figure,
    approve_final_artifact,
    approve_qoi_contract,
    run_analyze,
    run_qualify,
    run_write,
)
from cfdpaper.state import initialize_project
from cfdpaper.storage import ProjectStore


def _write_inputs(root: Path) -> tuple[Path, Path, Path]:
    observations = root / "observations.csv"
    observations.write_text(
        "case_id,coordinate_name,coordinate_value,coordinate_unit,variable,value,"
        "value_role,unit,scope,source_locator,aggregation,statistical_window,note\n"
        "P1,mean_velocity,0.05,m/s,pressure_drop,16,precomputed-qoi,Pa,"
        "pressure-tap span,observations.csv#row=2,,,\n"
        "P2,mean_velocity,0.10,m/s,pressure_drop,32,precomputed-qoi,Pa,"
        "pressure-tap span,observations.csv#row=3,,,\n"
        "P3,mean_velocity,0.15,m/s,pressure_drop,48,precomputed-qoi,Pa,"
        "pressure-tap span,observations.csv#row=4,,,\n",
        encoding="utf-8",
    )
    digest = hashlib.sha256(observations.read_bytes()).hexdigest()
    stat = observations.stat()
    records = root / "project-records.json"
    records.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": case,
                        "source_uri": "observations.csv",
                        "locator": f"observations.csv#case={case}",
                        "solver": "reference-data",
                        "solver_version": "1",
                        "state": "validated",
                    }
                    for case in ("P1", "P2", "P3")
                ],
                "boundaries": [
                    {
                        "boundary_id": "velocity-sequence",
                        "case_id": "P1",
                        "source_uri": "observations.csv",
                        "locator": "project-records.json#/boundaries/0",
                        "boundary_type": "comparison-difference",
                        "values": {
                            "name": "mean velocity",
                            "reference": "0.05 m/s",
                            "candidate": "0.15 m/s",
                        },
                        "units": {"mean_velocity": "m/s"},
                        "comparison_role": "intended-study-factor",
                        "basis": "prescribed velocity sequence",
                    }
                ],
                "models": [
                    {
                        "model_id": f"pipe-{case}",
                        "case_id": case,
                        "source_uri": "observations.csv",
                        "locator": f"project-records.json#/models/{index}",
                        "description": "steady incompressible laminar pipe flow",
                        "comparison_role": "demonstrated-equivalent-or-immaterial",
                        "basis": "identical geometry, fluid and model",
                        "verification_status": "demonstrated",
                        "verification_basis": "Hagen-Poiseuille pressure-drop reference",
                        "verification_locator": "verification.md#analytic-reference",
                        "validation_status": "not-demonstrated",
                        "validation_basis": "no external measurement supplied",
                        "validation_locator": "verification.md#validation-boundary",
                    }
                    for index, case in enumerate(("P1", "P2", "P3"))
                ],
                "convergence": [
                    {
                        "evidence_id": f"conv-{case}",
                        "case_id": case,
                        "source_uri": "observations.csv",
                        "locator": f"project-records.json#/convergence/{index}",
                        "metric": f"residual-{case}",
                        "observed_value": 1e-7,
                        "unit": "1",
                        "threshold_value": 1e-5,
                        "operator": "<=",
                        "consequence": "blocking",
                        "basis": "declared numerical convergence criterion",
                    }
                    for index, case in enumerate(("P1", "P2", "P3"))
                ],
                "conservation": [
                    {
                        "evidence_id": f"mass-{case}",
                        "case_id": case,
                        "source_uri": "observations.csv",
                        "locator": f"project-records.json#/conservation/{index}",
                        "metric": f"mass-imbalance-{case}",
                        "observed_value": 1e-8,
                        "unit": "1",
                        "threshold_value": 1e-5,
                        "operator": "<=",
                        "consequence": "blocking",
                        "basis": "declared conservation criterion",
                    }
                    for index, case in enumerate(("P1", "P2", "P3"))
                ],
                "sources": [
                    {
                        "source_uri": "observations.csv",
                        "locator": "observations.csv",
                        "sha256": digest,
                        "mtime_ns": stat.st_mtime_ns,
                        "size_bytes": stat.st_size,
                        "media_type": "text/csv",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    question = root / "question.json"
    question.write_text(
        json.dumps(
            {
                "question_id": "pipe-pressure-response",
                "proposal": {
                    "qoi_name": "Pressure drop",
                    "scientific_definition": "pressure difference over the 1 m tap span",
                    "operator": "identity",
                    "operands": [
                        {
                            "name": "pressure drop",
                            "variable": "pressure_drop",
                            "value_role": "precomputed-qoi",
                            "unit": "Pa",
                            "scope": "pressure-tap span",
                            "locator_policy": "one located scalar per expected member",
                        }
                    ],
                    "output_unit": "Pa",
                    "expected_members": [
                        {
                            "case_id": case,
                            "coordinate_name": "mean_velocity",
                            "coordinate_value": velocity,
                            "coordinate_unit": "m/s",
                            "variable": "pressure_drop",
                            "unit": "Pa",
                            "scope": "pressure-tap span",
                        }
                        for case, velocity in (("P1", 0.05), ("P2", 0.10), ("P3", 0.15))
                    ],
                    "trend_tolerance": 0.0,
                    "missing_data_policy": "reject",
                    "allow_quantitative_reporting": True,
                },
            }
        ),
        encoding="utf-8",
    )
    return records, observations, question


def _initialize_project(root: Path) -> None:
    initialize_project(root, "pipe-demo")
    ProjectIndexer(ProjectStore.open(root)).inspect()
    candidates = root / ".cfdpaper" / "inputs" / "topic_candidates.json"
    candidates.parent.mkdir(parents=True, exist_ok=True)
    candidates.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "candidates": [
                    {
                        "topic_id": "pipe-topic",
                        "title": "Laminar pipe pressure-drop verification",
                        "research_question": "How does pressure drop vary with mean velocity?",
                        "supporting_evidence_ids": ["verification-pipe-P1"],
                        "required_evidence_kinds": ["other"],
                        "required_maturity": "verified",
                        "minimum_verified_evidence": 1,
                        "significance": 0.6,
                        "novelty": 0.3,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_service_runs_three_checkpoint_evidence_workflow(tmp_path: Path) -> None:
    _initialize_project(tmp_path)
    records, observations, question = _write_inputs(tmp_path)

    qualified = run_qualify(
        tmp_path,
        records_path=records,
        observations_path=observations,
        question_path=question,
    )
    assert qualified.report.status == "restricted"
    assert qualified.report.validation.state == "not-demonstrated"
    evidence = {item.evidence_id: item for item in ProjectStore.open(tmp_path).list_evidence()}
    assert evidence["verification-pipe-P1"].maturity == "verified"
    run_plan(tmp_path, approve_topic="pipe-topic", author="Author")
    locked = approve_qoi_contract(
        tmp_path,
        contract_id=qualified.candidate.qoi_contract_id,
        author="Author",
    )
    analyzed = run_analyze(tmp_path)
    assert analyzed.ceiling.ceiling == V03ClaimCeiling.QUALIFIED_NUMERICAL_OBSERVATION
    assert [value.value for value in analyzed.analysis.values] == [16.0, 32.0, 48.0]

    figured = approve_and_render_figure(
        tmp_path,
        contract_id=analyzed.candidate_figure.figure_id,
        author="Author",
    )
    written = run_write(tmp_path, artifact="results-paragraph")
    before = {
        path.name: path.read_bytes()
        for path in (tmp_path / ".cfdpaper" / "outputs" / "write").iterdir()
    }
    final = approve_final_artifact(
        tmp_path,
        artifact="results-paragraph",
        author="Author",
    )

    assert locked.locked_contract.approval.author == "Author"
    assert figured.figure_delivery.validation.valid
    assert "16, 32, and 48 Pa" in written.paragraph_delivery.paragraph
    assert final.paragraph_delivery == written.paragraph_delivery
    assert {
        path.name: path.read_bytes()
        for path in (tmp_path / ".cfdpaper" / "outputs" / "write").iterdir()
    } == before
    assert ProjectStore.open(tmp_path).status().stage == "artifact-approved"
