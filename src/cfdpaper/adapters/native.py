"""Read-only reference probes for native Fluent and STAR-CCM+ files."""

from __future__ import annotations

from pathlib import Path

from .base import ExtractionRequest, Inventory, ProbeResult, UnsupportedExtractionError
from .csv import source_sha256

_EXPORT_SUFFIXES = (".csv", ".vtk", ".vtu", ".vtp")
_EXPORT_STEM_SUFFIXES = ("", "_export", "-export", ".export", "_fields", "-fields")


class _NativeSolverAdapter:
    name = "native"
    suffixes: tuple[str, ...] = ()
    export_instruction = "Export CSV or VTK data from the solver."

    def _recognizes(self, source: Path) -> bool:
        name = source.name.lower()
        return any(name.endswith(suffix) for suffix in self.suffixes)

    def _base_name(self, source: Path) -> str:
        lowered = source.name.lower()
        suffix = max((item for item in self.suffixes if lowered.endswith(item)), key=len)
        return source.name[: -len(suffix)]

    def _companions(self, source: Path) -> tuple[Path, ...]:
        base = self._base_name(source).lower()
        allowed_stems = {f"{base}{suffix}" for suffix in _EXPORT_STEM_SUFFIXES}
        found = {
            path.resolve()
            for path in source.parent.iterdir()
            if path.is_file()
            and path.suffix.lower() in _EXPORT_SUFFIXES
            and path.stem.lower() in allowed_stems
        }
        return tuple(sorted(found))

    def probe(self, source: Path) -> ProbeResult:
        source = Path(source).resolve()
        if not source.is_file():
            return ProbeResult(self.name, source, False, False, "missing", "source file is missing")
        if not self._recognizes(source):
            return ProbeResult(
                self.name,
                source,
                False,
                False,
                "unsupported",
                "native file extension not recognized",
            )
        return ProbeResult(
            self.name,
            source,
            True,
            False,
            "unsupported",
            "native solver file detected; direct extraction is intentionally unsupported",
            self.export_instruction,
        )

    def inventory(self, source: Path) -> Inventory:
        source = Path(source).resolve()
        probe = self.probe(source)
        if probe.status == "missing":
            return Inventory(self.name, source, "missing", recommendation=probe.reason)
        if not probe.supported:
            return Inventory(self.name, source, "unsupported", recommendation=probe.reason)
        companions = self._companions(source)
        return Inventory(
            self.name,
            source,
            "unsupported" if companions else "missing-export",
            source_hash=source_sha256(source),
            companions=companions,
            recommendation=self.export_instruction,
            metadata={"read_only": True},
        )

    def extract(self, request: ExtractionRequest) -> list:
        raise UnsupportedExtractionError(
            f"{self.name} native access is read-only; {self.export_instruction}"
        )


class FluentAdapter(_NativeSolverAdapter):
    name = "fluent"
    suffixes = (".cas.h5", ".dat.h5", ".cas", ".dat")
    export_instruction = (
        "Use Fluent to export a read-only CSV or VTK file containing coordinates, fields, units, "
        "case ID, and zone/location."
    )


class StarCCMAdapter(_NativeSolverAdapter):
    name = "star-ccm+"
    suffixes = (".sim",)
    export_instruction = (
        "Use STAR-CCM+ to export a read-only CSV or VTK file containing coordinates, fields, "
        "units, case ID, and region/location."
    )
