"""Locate method and evidence passages beyond the initial material preview."""

from __future__ import annotations

import os
import re
from pathlib import Path

from cfdpaper.materials import (
    _DOCUMENTS,
    MAX_FILE_BYTES,
    MAX_TOTAL_BYTES,
    _discover,
    _is_link,
    _issue,
)


def search_materials(
    root: Path,
    terms: list[str],
    *,
    paths: list[Path] | None = None,
    limit: int = 50,
) -> dict:
    """Case-insensitive literal OR search; matches are locations, not interpretations.

    Text, JSON, Python definitions and CSVs are read but never executed. Results
    retain source line numbers, and long lines expose their actual column offset.
    Explicit files use the same root/link boundary as the material profiler.
    """
    if not terms or any(not isinstance(t, str) or not t.strip() for t in terms):
        raise ValueError("Provide at least one nonempty search term")
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError("Search limit must be between 1 and 1000")
    terms = list(dict.fromkeys(t.strip() for t in terms))
    patterns = [(term, re.compile(re.escape(term), re.IGNORECASE)) for term in terms]
    root = Path(os.path.abspath(root))
    if not root.is_dir() or any(_is_link(p) for p in [root, *root.parents]):
        raise ValueError("Material root must be a directory without links")
    result = {"terms": terms, "matches": [], "searched_files": [], "issues": [], "truncated": False}
    issues = result["issues"]
    candidates = _discover(root, issues) if paths is None else paths
    seen, total = set(), 0
    for selected in candidates:
        path = Path(os.path.abspath(root / selected))
        try:
            relative = path.relative_to(root)
        except ValueError:
            _issue(issues, str(selected), "outside_root", "Selected file is outside material root")
            continue
        if path in seen:
            continue
        seen.add(path)
        name = relative.as_posix()
        try:
            if any(
                _is_link(root.joinpath(*relative.parts[:i]))
                for i in range(1, len(relative.parts) + 1)
            ):
                _issue(issues, name, "skipped_link", "Link not followed")
                continue
            if path.suffix.lower() not in _DOCUMENTS | {".csv"}:
                _issue(issues, name, "not_text", "Search accepts exported text and CSV files")
                continue
            size = path.stat().st_size
            if size > MAX_FILE_BYTES or total + size > MAX_TOTAL_BYTES:
                _issue(
                    issues,
                    name,
                    "size_limit",
                    "Select a smaller exported file or narrower directory",
                )
                continue
            total += size
            lines = path.read_text(encoding="utf-8-sig").splitlines()
            result["searched_files"].append(name)
            for index, line in enumerate(lines):
                hits = [(term, pattern.search(line)) for term, pattern in patterns]
                matched = [term for term, hit in hits if hit is not None]
                if not matched:
                    continue
                if len(result["matches"]) == limit:
                    result["truncated"] = True
                    _issue(
                        issues,
                        name,
                        "match_limit",
                        "More matches exist; narrow terms or increase limit",
                    )
                    return result
                context = []
                for position in range(max(0, index - 2), min(len(lines), index + 3)):
                    text = lines[position]
                    start = 0
                    if position == index and len(text) > 2000:
                        # Keep the first match visible even in one-line JSON exports.
                        first = min(hit.start() for _, hit in hits if hit is not None)
                        start = max(0, first - 200)
                    context.append(
                        {
                            "line": position + 1,
                            "column_start": start + 1,
                            "text": text[start : start + 2000],
                            "truncated": start > 0 or len(text) > start + 2000,
                        }
                    )
                result["matches"].append(
                    {
                        "path": name,
                        "line": index + 1,
                        "terms": matched,
                        "locator": f"L{index + 1}",
                        "context": context,
                    }
                )
        except (OSError, UnicodeError) as exc:
            _issue(issues, name, "unreadable", str(exc))
    return result
