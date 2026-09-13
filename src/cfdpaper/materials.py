"""Bounded, read-only profiles of exported research materials.

Column names and categorical examples remain verbatim: profiles are hints for
author-led analysis, not declarations of physical meaning or validated grouping.
"""

from __future__ import annotations

import csv
import math
import os
import re
import stat
from pathlib import Path
from typing import Any

from .adapters import CSVAdapter, ExtractionRequest, SourceChangedError
from .adapters.csv import source_sha256

MAX_FILES = 100
MAX_ENTRIES = 2000
MAX_DEPTH = 8
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024
MAX_EXCERPT_LINES = 120
MAX_EXCERPT_CHARS = 8000
_DOCUMENTS = {".md", ".txt", ".json"}
_FIGURES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".svg", ".webp", ".gif"}
_EXCLUDED = {
    ".git",
    ".cfdpaper",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".worktrees",
    "build",
    "dist",
    "output",
    "outputs",
    "archive",
    "archives",
    "private",
    "private-fixtures",
    "local",
    "quality_reports",
}
_LEADING_ZERO = re.compile(r"^[+-]?0\d+$")


def _issue(issues: list[dict], path: str, code: str, message: str) -> None:
    issues.append({"path": path, "code": code, "message": message})


def _is_link(path: Path) -> bool:
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )


def _excluded(name: str) -> bool:
    name = name.casefold()
    return name in _EXCLUDED or name.startswith(("_local", "private-", "private_"))


def _discover(root: Path, issues: list[dict]) -> list[Path]:
    found: list[Path] = []
    pending = [(root, 0)]
    entries_seen = 0
    while pending:
        directory, depth = pending.pop()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    entries_seen += 1
                    if entries_seen > MAX_ENTRIES:
                        _issue(
                            issues,
                            ".",
                            "discovery_limit",
                            "Directory-entry limit reached; "
                            "additional materials may be omitted. Select explicit paths.",
                        )
                        return sorted(found)
                    path = Path(entry.path)
                    relative = path.relative_to(root).as_posix()
                    try:
                        if _is_link(path):
                            _issue(issues, relative, "skipped_link", "Link not followed.")
                        elif entry.is_dir(follow_symlinks=False):
                            if _excluded(entry.name):
                                _issue(
                                    issues,
                                    relative,
                                    "excluded_directory",
                                    "Directory omitted from default discovery.",
                                )
                            elif depth >= MAX_DEPTH:
                                _issue(
                                    issues,
                                    relative,
                                    "depth_limit",
                                    "Directory omitted at discovery depth limit.",
                                )
                            else:
                                pending.append((path, depth + 1))
                        elif entry.is_file(follow_symlinks=False):
                            if path.suffix.lower() in _DOCUMENTS | _FIGURES | {".csv"}:
                                found.append(path)
                                if len(found) >= MAX_FILES:
                                    _issue(
                                        issues,
                                        ".",
                                        "discovery_limit",
                                        "Material-file limit "
                                        "reached; additional materials may be omitted. "
                                        "Select explicit paths.",
                                    )
                                    return sorted(found)
                    except OSError as exc:
                        _issue(issues, relative, "unreadable", str(exc))
        except OSError as exc:
            _issue(issues, directory.relative_to(root).as_posix(), "unreadable", str(exc))
    return sorted(found)


def _table(path: Path, relative: str) -> dict[str, Any]:
    adapter = CSVAdapter()
    inventory = adapter.inventory(path)
    records = adapter.extract(ExtractionRequest(source=path))
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        headers = reader.fieldnames or []
        raw_rows = list(reader)
    if source_sha256(path) != inventory.source_hash or any(
        record.source_hash != inventory.source_hash for record in records
    ):
        raise SourceChangedError("CSV changed while building its material profile")
    if not headers or any(not label for label in inventory.variables):
        raise ValueError("CSV requires nonempty column headers")
    columns = []
    groups = []
    for index, (header, label) in enumerate(zip(headers, inventory.variables, strict=True), 1):
        raw = [row[header] for row in raw_rows]
        values = [record.values[label] for record in records]
        present = [(i, value) for i, value in enumerate(raw) if value and value.strip()]
        examples: list[str] = []
        locators: list[str] = []
        unique = {value for _, value in present}
        for i, value in present:
            if value not in examples and len(examples) < 5:
                examples.append(value)
                locators.append(records[i].locator)
        numeric = [value for value in values if isinstance(value, (float, int))]
        finite = [value for value in numeric if math.isfinite(value)]
        zero_codes = any(_LEADING_ZERO.fullmatch(value.strip()) for _, value in present)
        if not present:
            kind = "empty"
        elif zero_codes or not numeric:
            kind = "string"
        elif len(numeric) == len(present):
            kind = "number"
        else:
            kind = "mixed"
        column: dict[str, Any] = {
            "name": header,
            "label": label,
            "unit": inventory.units[label],
            "type": kind,
            "missing_count": len(raw) - len(present),
            "nonfinite_count": len(numeric) - len(finite),
            "unique_count": len(unique),
            "examples": examples,
            "example_locators": locators,
            "source": {"path": relative, "locator": "row:1", "column": index},
        }
        if kind == "number" and finite:
            column.update(minimum=min(finite), maximum=max(finite))
        columns.append(column)
        if (
            present
            and inventory.units[label] is None
            and (kind == "string" or 1 < len(unique) <= min(20, len(present) // 2))
        ):
            groups.append(header)
    return {
        "path": relative,
        "row_count": inventory.row_count,
        "columns": columns,
        "candidate_group_columns": groups,
        "source": {
            "path": relative,
            "header_locator": "row:1",
            "data_locator": f"row:2-row:{len(records) + 1}" if records else None,
            "source_hash": inventory.source_hash,
        },
    }


def _document(path: Path, relative: str) -> dict[str, Any]:
    # JSON is deliberately supplied as source text, never evaluated as instructions.
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    excerpt: list[str] = []
    remaining = MAX_EXCERPT_CHARS
    truncated = False
    for number, line in enumerate(lines[:MAX_EXCERPT_LINES], 1):
        rendered = f"{number}: {line}"
        if len(rendered) + 1 > remaining:
            if remaining > 0:
                excerpt.append(rendered[:remaining])
            truncated = True
            break
        excerpt.append(rendered)
        remaining -= len(rendered) + 1
    truncated = truncated or len(excerpt) < len(lines)
    return {
        "path": relative,
        "excerpt": "\n".join(excerpt),
        "truncated": truncated,
        "line_count": len(lines),
        "source": {"path": relative, "locator": f"line:1-line:{len(excerpt)}" if excerpt else None},
    }


def profile_materials(root: Path, *, paths: list[Path] | None = None) -> dict[str, Any]:
    """Profile small exported files without changing originals or inferring physics.

    Relative explicit paths are rooted at ``root``. Explicit selection bypasses
    default directory exclusions, but never root containment, links or read-size
    limits. CSV statistics cover all rows in each accepted file. Issues report
    unreadable files and omissions instead of silently presenting partial coverage.
    """
    root = Path(root).absolute()
    result: dict[str, Any] = {"tables": [], "documents": [], "figures": [], "issues": []}
    issues = result["issues"]
    try:
        if any(_is_link(part) for part in [root, *root.parents]):
            raise ValueError("Material root must not traverse links")
        if not root.is_dir():
            raise ValueError("Material root is not a directory")
    except (OSError, ValueError) as exc:
        _issue(issues, ".", "invalid_root", str(exc))
        return result
    candidates = _discover(root, issues) if paths is None else paths
    seen: set[Path] = set()
    total_bytes = 0
    for selected in candidates:
        path = Path(selected)
        path = path if path.is_absolute() else root / path
        # Normalize '..' lexically before checking scope, without following links.
        path = Path(os.path.abspath(path))
        try:
            relative_path = path.relative_to(root)
        except ValueError:
            _issue(issues, str(selected), "outside_root", "Selected path is outside material root.")
            continue
        relative = relative_path.as_posix()
        if path in seen:
            continue
        seen.add(path)
        try:
            if any(
                _is_link(root.joinpath(*relative_path.parts[:i]))
                for i in range(1, len(relative_path.parts) + 1)
            ):
                _issue(issues, relative, "skipped_link", "Link not followed.")
                continue
            if not path.is_file():
                raise ValueError("Selected material is not a file")
            suffix = path.suffix.lower()
            if suffix in _FIGURES:
                result["figures"].append({"path": relative})
                continue
            if suffix not in _DOCUMENTS | {".csv"}:
                _issue(
                    issues, relative, "unsupported", "Select CSV, Markdown, text, JSON or images."
                )
                continue
            size = path.stat().st_size
            if size > MAX_FILE_BYTES or total_bytes + size > MAX_TOTAL_BYTES:
                _issue(
                    issues,
                    relative,
                    "size_limit",
                    "File omitted because read-size limit "
                    "would be exceeded; provide a smaller exported material selection.",
                )
                continue
            total_bytes += size
            if suffix == ".csv":
                result["tables"].append(_table(path, relative))
            else:
                result["documents"].append(_document(path, relative))
        except (OSError, UnicodeError, ValueError, csv.Error, SourceChangedError) as exc:
            _issue(issues, relative, "unreadable", str(exc))
    return result
