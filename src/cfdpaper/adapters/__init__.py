"""Read-only input adapters."""

from .base import (
    Adapter,
    AdapterError,
    ExtractedRecord,
    ExtractionRequest,
    Inventory,
    ProbeResult,
    SourceChangedError,
    UnsupportedExtractionError,
)
from .csv import CSVAdapter
from .native import FluentAdapter, StarCCMAdapter
from .vtk import VTKAdapter

__all__ = [
    "Adapter",
    "AdapterError",
    "CSVAdapter",
    "ExtractedRecord",
    "ExtractionRequest",
    "FluentAdapter",
    "Inventory",
    "ProbeResult",
    "SourceChangedError",
    "StarCCMAdapter",
    "UnsupportedExtractionError",
    "VTKAdapter",
]
