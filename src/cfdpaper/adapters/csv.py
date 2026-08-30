"""Generic, read-only CSV adapter with row-level provenance."""

from __future__ import annotations

import csv
import hashlib
import re
from pathlib import Path
from typing import TextIO

from .base import (
    ExtractedRecord,
    ExtractionRequest,
    Inventory,
    ProbeResult,
    Scalar,
    SourceChangedError,
)

_HEADER_UNIT = re.compile(r"^\s*(.*?)\s*(?:\[([^\]]+)\]|\(([^()]+)\))\s*$")


def source_sha256(source: Path) -> str:
    digest = hashlib.sha256()
    with source.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _split_header(header: str) -> tuple[str, str | None]:
    match = _HEADER_UNIT.match(header)
    if match:
        name = match.group(1).strip()
        unit = (match.group(2) or match.group(3)).strip()
        return name, unit
    return header.strip(), None


def _coerce(value: str | None) -> Scalar:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    try:
        number = float(stripped)
    except ValueError:
        return value
    if number.is_integer() and not any(token in stripped.lower() for token in (".", "e")):
        return int(number)
    return number


def _validate_row(
    row: dict[str | None, str | list[str] | None], headers: list[str], line: int
) -> None:
    extras = row.get(None)
    extra_count = len(extras) if isinstance(extras, list) else 0
    missing_count = sum(row.get(header) is None for header in headers)
    if extra_count or missing_count:
        actual = len(headers) + extra_count - missing_count
        raise ValueError(f"CSV row {line} has {actual} columns; expected {len(headers)}")


class CSVAdapter:
    name = "csv"

    def probe(self, source: Path) -> ProbeResult:
        source = Path(source).resolve()
        if not source.is_file():
            return ProbeResult(self.name, source, False, False, "missing", "source file is missing")
        supported = source.suffix.lower() == ".csv"
        return ProbeResult(
            self.name,
            source,
            supported,
            supported,
            "supported" if supported else "unsupported",
            "CSV source recognized" if supported else "expected a .csv file",
        )

    def _reader(self, source: Path, encoding: str, delimiter: str) -> tuple[TextIO, csv.DictReader]:
        stream = source.open("r", encoding=encoding, newline="")
        return stream, csv.DictReader(stream, delimiter=delimiter)

    def inventory(self, source: Path) -> Inventory:
        source = Path(source).resolve()
        probe = self.probe(source)
        if not probe.supported:
            return Inventory(self.name, source, probe.status, recommendation=probe.reason)
        before = source_sha256(source)
        stream, reader = self._reader(source, "utf-8-sig", ",")
        with stream:
            headers = reader.fieldnames or []
            parsed = [_split_header(header) for header in headers]
            names = [name for name, _ in parsed]
            if len(set(names)) != len(names):
                raise ValueError("CSV headers are ambiguous after unit parsing")
            row_count = 0
            for line_number, row in enumerate(reader, start=2):
                _validate_row(row, headers, line_number)
                row_count += 1
        after = source_sha256(source)
        if before != after:
            raise SourceChangedError(f"source changed during inventory: {source}")
        return Inventory(
            self.name,
            source,
            "supported",
            tuple(names),
            dict(parsed),
            row_count,
            before,
        )

    def extract(self, request: ExtractionRequest) -> list[ExtractedRecord]:
        source = request.source.resolve()
        probe = self.probe(source)
        if not probe.supported:
            raise ValueError(probe.reason)
        encoding = str(request.options.get("encoding", "utf-8-sig"))
        delimiter = str(request.options.get("delimiter", ","))
        before = source_sha256(source)
        stream, reader = self._reader(source, encoding, delimiter)
        records: list[ExtractedRecord] = []
        with stream:
            headers = reader.fieldnames or []
            parsed = [_split_header(header) for header in headers]
            names = [name for name, _ in parsed]
            if len(set(names)) != len(names):
                raise ValueError("CSV headers are ambiguous after unit parsing")
            units = dict(parsed)
            selected = request.variables or tuple(names)
            unknown = [name for name in selected if name not in names]
            if unknown:
                raise ValueError(f"unknown CSV variables: {', '.join(unknown)}")
            raw_by_name = dict(zip(names, headers, strict=True))
            for line_number, row in enumerate(reader, start=2):
                _validate_row(row, headers, line_number)
                values = {name: _coerce(row.get(raw_by_name[name], "")) for name in selected}
                records.append(
                    ExtractedRecord(
                        source_uri=source.as_uri(),
                        locator=f"row:{line_number}",
                        source_hash=before,
                        values=values,
                        units={name: units[name] for name in selected},
                    )
                )
        after = source_sha256(source)
        if before != after:
            raise SourceChangedError(f"source changed during extraction: {source}")
        return records
