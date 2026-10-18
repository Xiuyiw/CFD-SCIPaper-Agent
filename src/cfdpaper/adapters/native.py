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

    def __init__(self, *, executable=None, session_factory=None):
        self.executable = executable
        self.session_factory = session_factory

    def probe(self, source: Path) -> ProbeResult:
        result = super().probe(source)
        if not result.supported:
            return result
        from .fluent_backend import pyfluent_available

        available = self.session_factory is not None or pyfluent_available()
        return ProbeResult(
            self.name,
            result.source,
            True,
            available,
            "available" if available else "unsupported",
            "PyFluent backend available; license and saved CASE/DATA checked on extraction"
            if available
            else result.reason,
            self.export_instruction,
        )

    def extract(self, request: ExtractionRequest) -> list:
        if not request.options.get("data_file"):
            raise UnsupportedExtractionError(
                "Fluent read-only extraction needs data_file, output_dir and surfaces; "
                + self.export_instruction
            )
        from .fluent_backend import extract_fluent_records

        options = dict(request.options)
        if self.executable is not None:
            options.setdefault("executable", self.executable)
        return extract_fluent_records(
            ExtractionRequest(request.source, request.variables, options),
            session_factory=self.session_factory,
        )

    def inventory(self, source: Path) -> Inventory:
        inventory = super().inventory(source)
        if not self.probe(source).available:
            return inventory
        return Inventory(
            self.name,
            inventory.source,
            "requires-extraction",
            source_hash=inventory.source_hash,
            companions=inventory.companions,
            recommendation=(
                "Read the saved CASE/DATA pair with output_dir and exact surfaces; "
                "extraction records the available native fields and surface inventory."
            ),
            metadata={
                "read_only": True,
                "python_backend_available": True,
                "native_license_verified": False,
            },
        )


class StarCCMAdapter(_NativeSolverAdapter):
    name = "star-ccm+"
    suffixes = (".sim",)
    export_instruction = (
        "Use STAR-CCM+ to export a read-only CSV or VTK file containing coordinates, fields, "
        "units, case ID, and region/location."
    )
