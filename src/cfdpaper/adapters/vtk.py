"""Conservative VTK inventory and optional meshio extraction."""

from __future__ import annotations

import importlib
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .base import (
    ExtractedRecord,
    ExtractionRequest,
    Inventory,
    ProbeResult,
    SourceChangedError,
    UnsupportedExtractionError,
)
from .csv import source_sha256

_VTK_SUFFIXES = {".vtk", ".vtu", ".vtp", ".vts", ".vtr", ".vti"}
_PARALLEL_VTK_SUFFIXES = {".pvtu", ".pvtp"}
_SHALLOW_SCAN_BYTES = 2 * 1024 * 1024
_MANUAL_EXPORT = (
    "Install the optional 'vtk' dependencies, or export the minimum CSV evidence: "
    "point/cell coordinates, variable names, values, units, case ID, and zone/location."
)


def _default_meshio_loader() -> Any | None:
    try:
        return importlib.import_module("meshio")
    except ImportError:
        return None


def _shallow_variable_scan(source: Path) -> tuple[str, ...]:
    with source.open("rb") as stream:
        raw = stream.read(_SHALLOW_SCAN_BYTES)
    text = raw.decode("latin-1", errors="ignore")
    names: list[str] = []
    patterns = (
        r"(?mi)^\s*(?:SCALARS|VECTORS|TENSORS|NORMALS)\s+([^\s]+)",
        r"(?i)<DataArray\b[^>]*\bName=[\"']([^\"']+)[\"']",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            name = match.group(1)
            if name not in names:
                names.append(name)
    return tuple(names)


class VTKAdapter:
    name = "vtk"

    def __init__(self, meshio_loader: Callable[[], Any | None] | None = None) -> None:
        self._meshio_loader = meshio_loader or _default_meshio_loader

    def probe(self, source: Path) -> ProbeResult:
        source = Path(source).resolve()
        if not source.is_file():
            return ProbeResult(self.name, source, False, False, "missing", "source file is missing")
        if source.suffix.lower() in _PARALLEL_VTK_SUFFIXES:
            return ProbeResult(
                self.name,
                source,
                False,
                False,
                "unsupported",
                "parallel VTK coordinators are unsupported without dependency-closure hashing",
                "Export a serial VTK file or component-wise CSV data.",
            )
        if source.suffix.lower() not in _VTK_SUFFIXES:
            return ProbeResult(self.name, source, False, False, "unsupported", "not a VTK file")
        available = self._meshio_loader() is not None
        return ProbeResult(
            self.name,
            source,
            True,
            available,
            "supported" if available else "missing-dependency",
            "VTK source recognized",
            "" if available else _MANUAL_EXPORT,
        )

    def inventory(self, source: Path) -> Inventory:
        source = Path(source).resolve()
        probe = self.probe(source)
        if not probe.supported:
            return Inventory(self.name, source, probe.status, recommendation=probe.reason)
        before = source_sha256(source)
        variables = _shallow_variable_scan(source)
        meshio = self._meshio_loader()
        metadata: dict[str, Any] = {}
        if meshio is not None:
            mesh = meshio.read(source)
            variables = tuple(dict.fromkeys((*mesh.point_data.keys(), *mesh.cell_data.keys())))
            metadata = {
                "point_count": len(mesh.points),
                "cell_block_count": len(mesh.cells),
            }
        if source_sha256(source) != before:
            raise SourceChangedError(f"source changed during inventory: {source}")
        return Inventory(
            self.name,
            source,
            probe.status,
            variables,
            {name: None for name in variables},
            source_hash=before,
            recommendation=probe.recommendation,
            metadata=metadata,
        )

    def extract(self, request: ExtractionRequest) -> list[ExtractedRecord]:
        source = request.source.resolve()
        probe = self.probe(source)
        if not probe.supported:
            if source.suffix.lower() in _PARALLEL_VTK_SUFFIXES:
                raise UnsupportedExtractionError(probe.reason)
            raise ValueError(probe.reason)
        meshio = self._meshio_loader()
        if meshio is None:
            raise UnsupportedExtractionError(_MANUAL_EXPORT)
        before = source_sha256(source)
        mesh = meshio.read(source)
        selected = set(request.variables)
        available = set(mesh.point_data) | set(mesh.cell_data)
        unknown = selected - available
        if unknown:
            raise ValueError(f"unknown VTK variables: {', '.join(sorted(unknown))}")
        selected_cell_data = set(mesh.cell_data) if not selected else selected & set(mesh.cell_data)
        if selected_cell_data:
            raise UnsupportedExtractionError(
                "VTK cell data extraction is unsupported; export component-wise cell CSV data"
            )
        records: list[ExtractedRecord] = []
        for location, datasets in (("point", mesh.point_data),):
            for name, array in datasets.items():
                if selected and name not in selected:
                    continue
                values = array.tolist() if hasattr(array, "tolist") else list(array)
                for index, value in enumerate(values):
                    if isinstance(value, (list, tuple, dict)):
                        raise UnsupportedExtractionError(
                            "VTK vector/tensor extraction is unsupported; "
                            "export component-wise CSV data"
                        )
                    if not isinstance(value, (float, int, str, bool)):
                        raise UnsupportedExtractionError(
                            f"unsupported VTK scalar type for {name}: {type(value).__name__}"
                        )
                    scalar = value
                    records.append(
                        ExtractedRecord(
                            source.as_uri(),
                            f"{location}-data:{name}:index:{index}",
                            before,
                            {name: scalar},
                            {name: None},
                            {"location": location},
                        )
                    )
        if source_sha256(source) != before:
            raise SourceChangedError(f"source changed during extraction: {source}")
        return records
