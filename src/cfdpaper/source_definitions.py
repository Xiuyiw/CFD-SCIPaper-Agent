"""Static, bounded reads of explicitly named Python source definitions.

Qualified names describe lexical nesting only. They do not resolve inheritance,
aliases, callers, decorators, or which declaration is active at runtime.
"""

from __future__ import annotations

import ast
import re
from collections import Counter
from pathlib import Path
from typing import Any


class SourceDefinitionError(ValueError):
    """An explicit source-read failure, with candidates for ambiguous names."""

    def __init__(
        self, code: str, message: str, *, candidates: list[dict[str, Any]] | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.candidates = candidates or []


class _DefinitionVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.scope: list[tuple[str, str]] = []
        self.definitions: list[dict[str, Any]] = []

    def _definition(self, node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        if isinstance(node, ast.ClassDef):
            kind = "class"
        else:
            kind = "method" if self.scope and self.scope[-1][1] == "class" else "function"
            if isinstance(node, ast.AsyncFunctionDef):
                kind = f"async_{kind}"
        self.definitions.append(
            {
                "qualified_name": ".".join([name for name, _ in self.scope] + [node.name]),
                "name": node.name,
                "kind": kind,
                "start_line": min([node.lineno] + [item.lineno for item in node.decorator_list]),
                "end_line": node.end_lineno,
            }
        )
        self.scope.append((node.name, kind))
        self.generic_visit(node)
        self.scope.pop()

    visit_ClassDef = _definition
    visit_FunctionDef = _definition
    visit_AsyncFunctionDef = _definition


def python_definition_index(text: str) -> list[dict[str, Any]]:
    """Index named classes and functions in source order, without execution.

    Lines are one-based and include decorators. Every occurrence is retained;
    repeated lexical names are marked ambiguous rather than selecting an
    override or a conditional branch. Syntax must be supported by this runtime.
    """
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError) as exc:
        raise SourceDefinitionError("syntax_error", f"Cannot parse Python source: {exc}") from exc
    visitor = _DefinitionVisitor()
    visitor.visit(tree)
    definitions = sorted(visitor.definitions, key=lambda item: item["start_line"])
    counts = Counter(item["qualified_name"] for item in definitions)
    for definition in definitions:
        definition["ambiguous"] = counts[definition["qualified_name"]] > 1
    return definitions


def _physical_lines(text: str) -> list[str]:
    # Python physical lines use CR/LF, not splitlines()'s formfeed/vertical-tab
    # separators. Keep endings verbatim so returned text is an exact substring.
    return re.findall(r"[^\r\n]*(?:\r\n|\r|\n|$)", text)[:-1]


def read_python_definition(
    path: Path | str, qualified_name: str, *, max_chars: int | None = None
) -> dict[str, Any]:
    """Read one exact lexical definition from an explicit UTF-8 ``.py`` file.

    ``max_chars=None`` reuses the existing materials excerpt budget. File size
    also uses that module's per-file limit. A truncated result is an exact
    character prefix, never an apparently complete or reconstructed definition.
    UTF-8 BOMs are accepted as encoding markers. No source code is imported.
    """
    # Resolve shared limits at call time to permit materials to use this reader
    # without an import cycle or a second, drifting set of size constants.
    from . import materials

    if max_chars is None:
        max_chars = materials.MAX_EXCERPT_CHARS
    if isinstance(max_chars, bool) or not isinstance(max_chars, int) or max_chars < 1:
        raise SourceDefinitionError("invalid_limit", "max_chars must be a positive integer")
    source_path = Path(path)
    if source_path.suffix.lower() != ".py":
        raise SourceDefinitionError("unsupported_extension", "Select a UTF-8 .py source file")
    try:
        if source_path.stat().st_size > materials.MAX_FILE_BYTES:
            raise SourceDefinitionError(
                "size_limit", "Python source exceeds material file-size limit"
            )
        with source_path.open("rb") as stream:
            payload = stream.read(materials.MAX_FILE_BYTES + 1)
    except OSError as exc:
        raise SourceDefinitionError(
            "unreadable_source", f"Cannot read Python source {source_path}: {exc}"
        ) from exc
    if len(payload) > materials.MAX_FILE_BYTES:
        raise SourceDefinitionError("size_limit", "Python source exceeds material file-size limit")
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeError as exc:
        raise SourceDefinitionError(
            "unsupported_encoding", f"Python source must be UTF-8: {exc}"
        ) from exc
    matches = [
        item for item in python_definition_index(text) if item["qualified_name"] == qualified_name
    ]
    if not matches:
        raise SourceDefinitionError(
            "missing_definition", f"Python definition not found: {qualified_name}"
        )
    if len(matches) != 1:
        raise SourceDefinitionError(
            "ambiguous_definition",
            f"Python definition is ambiguous: {qualified_name} ({len(matches)} occurrences)",
            candidates=matches,
        )
    definition = matches[0]
    start, end = definition["start_line"], definition["end_line"]
    original = "".join(_physical_lines(text)[start - 1 : end])
    excerpt = original[:max_chars]
    excerpt_lines = _physical_lines(excerpt)
    truncated = len(excerpt) < len(original)
    last_line_partial = truncated and (
        not excerpt.endswith(("\n", "\r"))
        or (excerpt.endswith("\r") and original[len(excerpt) :].startswith("\n"))
    )
    return {
        **definition,
        "text": excerpt,
        "excerpt_start_line": start,
        "excerpt_end_line": start + len(excerpt_lines) - 1,
        "definition_chars": len(original),
        "returned_chars": len(excerpt),
        "complete": not truncated,
        "truncated": truncated,
        "last_line_partial": last_line_partial,
        "truncation_note": (
            f"Definition exceeds max_chars={max_chars}; only an exact source prefix is returned"
            + (" and the final returned line is partial." if last_line_partial else ".")
            if truncated
            else None
        ),
        "source": {
            "path": source_path.as_posix(),
            "locator": f"line:{start}-line:{end}",
        },
    }
