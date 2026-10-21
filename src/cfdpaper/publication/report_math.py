"""Connect declared report formulas to the existing native manuscript math tree."""

from __future__ import annotations

import copy
import re
from pathlib import PurePosixPath, PureWindowsPath

from cfdpaper.publication.elements import MathNode

_IDENTIFIER = re.compile(r"[A-Za-z0-9_.-]+")
_MATH_TOKEN = re.compile(r"\{\{math:([A-Za-z0-9_.-]+)\}\}")


def normalize_report_formulas(formulas: dict | None) -> dict:
    """Validate expression trees and relative source locators, without reading files.

    Source copying and path remapping belong to the report package. A ``#`` or
    ``:Lx-Ly`` suffix locates a definition in the file and is retained unchanged.
    """
    if formulas is None:
        return {}
    if not isinstance(formulas, dict):
        raise ValueError("Report formulas must be a dictionary keyed by formula ID")
    result = {}
    for identifier, declaration in formulas.items():
        if not isinstance(identifier, str) or not _IDENTIFIER.fullmatch(identifier):
            raise ValueError("Report formula ID must use only letters, digits, _, . or -")
        if not isinstance(declaration, dict) or set(declaration) != {"expression", "source"}:
            raise ValueError(
                f"Report formula {identifier!r} requires exactly expression and source"
            )
        expression, source = declaration["expression"], declaration["source"]
        if not isinstance(expression, dict):
            raise ValueError(
                f"Report formula {identifier!r} expression must be a MathNode dictionary"
            )
        try:
            node = MathNode.model_validate(expression)
        except ValueError as exc:
            raise ValueError(f"Report formula {identifier!r} expression: {exc}") from exc
        if not isinstance(source, str) or not source.strip():
            raise ValueError(
                f"Report formula {identifier!r} source must be a nonempty relative file locator"
            )
        filename = source.partition("#")[0].replace("\\", "/")
        line_locator = re.fullmatch(r"(.+):L[1-9]\d*(?:-L?[1-9]\d*)?", filename)
        if line_locator:
            filename = line_locator[1]
        path, windows = PurePosixPath(filename), PureWindowsPath(filename)
        if (
            not path.parts
            or path.is_absolute()
            or windows.drive
            or windows.root
            or ".." in path.parts
            or ":" in filename
        ):
            raise ValueError(
                f"Report formula {identifier!r} source must be a relative file locator "
                "without parent traversal"
            )
        result[identifier] = {"expression": node.model_dump(), "source": source}
    return result


def apply_report_formulas(draft: dict, formulas: dict) -> dict:
    """Fill referenced missing inline math in a deep copy; author declarations win.

    Ordinary prose is never parsed as TeX or rewritten, and unused library entries
    are not added to the draft. Downstream manuscript validation owns draft schema.
    """
    if not isinstance(draft, dict):
        raise ValueError("Report draft must be a dictionary")
    declarations = normalize_report_formulas(formulas)
    result = copy.deepcopy(draft)
    paragraphs = result.get("paragraphs", [])
    if not isinstance(paragraphs, list):
        raise ValueError("Report draft paragraphs must be a list")
    for index, paragraph in enumerate(paragraphs):
        if not isinstance(paragraph, dict) or not isinstance(paragraph.get("text", ""), str):
            raise ValueError(f"Report draft paragraphs[{index}] must have a text string")
        identifiers = _MATH_TOKEN.findall(paragraph.get("text", ""))
        if not identifiers:
            continue
        inline_math = paragraph.setdefault("inline_math", {})
        if not isinstance(inline_math, dict):
            raise ValueError(f"Report draft paragraphs[{index}].inline_math must be a dictionary")
        for identifier in identifiers:
            if identifier in inline_math:
                continue
            if identifier not in declarations:
                raise ValueError(
                    f"Report draft paragraphs[{index}] references unknown formula {identifier!r}; "
                    f"add formulas[{identifier!r}] with expression/source, or declare "
                    f"paragraphs[{index}].inline_math[{identifier!r}]"
                )
            inline_math[identifier] = copy.deepcopy(declarations[identifier]["expression"])
    return result
