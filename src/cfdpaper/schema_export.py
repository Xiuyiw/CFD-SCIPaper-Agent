"""Export stable JSON Schemas for public CFD-Paper-Agent contracts."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from cfdpaper.contracts import (
    BoundaryRecord,
    CaseRecord,
    ClaimRecord,
    EvidenceRecord,
    FieldRecord,
    FigureContract,
    MeshRecord,
    ProjectManifest,
    QoIRecord,
    StageResult,
    TaskContextPacket,
)

PUBLIC_CONTRACTS: dict[str, type[BaseModel]] = {
    model.__name__: model
    for model in (
        ProjectManifest,
        CaseRecord,
        BoundaryRecord,
        MeshRecord,
        FieldRecord,
        QoIRecord,
        EvidenceRecord,
        ClaimRecord,
        FigureContract,
        TaskContextPacket,
        StageResult,
    )
}


def export_json_schemas(output_dir: Path) -> list[Path]:
    """Write deterministic JSON Schemas and return their paths."""

    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, model in PUBLIC_CONTRACTS.items():
        path = output_dir / f"{name}.json"
        path.write_text(
            json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        written.append(path)
    return written
