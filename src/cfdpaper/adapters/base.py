"""Read-only adapter contracts shared by solver and interchange formats."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Protocol, runtime_checkable

Scalar = float | int | str | bool | None


class AdapterError(RuntimeError):
    """Base error for adapter operations."""


class UnsupportedExtractionError(AdapterError):
    """Raised when a source is recognized but cannot be extracted safely."""


class SourceChangedError(AdapterError):
    """Raised if a source changes while a read-only extraction is in progress."""


@dataclass(frozen=True, slots=True)
class ProbeResult:
    adapter: str
    source: Path
    supported: bool
    available: bool
    status: str
    reason: str
    recommendation: str = ""


@dataclass(frozen=True, slots=True)
class Inventory:
    adapter: str
    source: Path
    status: str
    variables: tuple[str, ...] = ()
    units: Mapping[str, str | None] = field(default_factory=dict)
    row_count: int | None = None
    source_hash: str | None = None
    companions: tuple[Path, ...] = ()
    recommendation: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "source", Path(self.source))
        object.__setattr__(self, "variables", tuple(self.variables))
        object.__setattr__(self, "units", MappingProxyType(dict(self.units)))
        object.__setattr__(self, "companions", tuple(Path(path) for path in self.companions))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ExtractionRequest:
    source: Path
    variables: tuple[str, ...] = ()
    options: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "source", Path(self.source))
        object.__setattr__(self, "variables", tuple(self.variables))
        object.__setattr__(self, "options", MappingProxyType(dict(self.options)))


@dataclass(frozen=True, slots=True)
class ExtractedRecord:
    source_uri: str
    locator: str
    source_hash: str
    values: Mapping[str, Scalar]
    units: Mapping[str, str | None] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))
        object.__setattr__(self, "units", MappingProxyType(dict(self.units)))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@runtime_checkable
class Adapter(Protocol):
    """The common, deliberately read-only source adapter protocol."""

    name: str

    def probe(self, source: Path) -> ProbeResult: ...

    def inventory(self, source: Path) -> Inventory: ...

    def extract(self, request: ExtractionRequest) -> list[ExtractedRecord]: ...
