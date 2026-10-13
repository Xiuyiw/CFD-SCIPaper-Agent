"""Read a declared numeric JSON field; do not infer active settings or execute project code."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

from cfdpaper.materials import MAX_FILE_BYTES
from cfdpaper.publication.table_evidence import format_value


def _pointer(document, pointer: str):
    if not isinstance(pointer, str) or (pointer and not pointer.startswith("/")):
        raise ValueError("JSON pointer must be empty or start with /")
    value = document
    for raw in pointer.split("/")[1:]:
        if re.search(r"~(?![01])", raw):
            raise ValueError("Invalid JSON pointer escape")
        key = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(value, dict):
            if key not in value:
                raise ValueError(f"Missing JSON pointer: {pointer}")
            value = value[key]
        elif isinstance(value, list):
            if not re.fullmatch(r"0|[1-9][0-9]*", key) or int(key) >= len(value):
                raise ValueError(f"Invalid array index in JSON pointer: {pointer}")
            value = value[int(key)]
        else:
            raise ValueError(f"JSON pointer traverses a scalar: {pointer}")
    return value


def resolve_json_value(
    root: Path,
    *,
    source: str,
    pointer: str,
    unit: str,
    places: int = 3,
    unit_pointer: str | None = None,
) -> dict:
    """Resolve one finite native number with a source locator and declared display units.

    JSON unit strings may be checked at an explicit pointer. There is no unit conversion,
    expression evaluation, default guessing, case/stage inference or scientific approval.
    """
    root = Path(root).resolve()
    relative = Path(source)
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or relative.parts[:1] != ("sources",)
        or relative.suffix.lower() != ".json"
    ):
        raise ValueError("JSON parameter source must use a relative sources/ JSON path")
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("JSON parameter source is missing or outside the package")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("JSON parameter source exceeds the material file size limit")
    if not isinstance(unit, str):
        raise ValueError("Parameter unit must be a string, empty only for dimensionless values")
    try:
        document = json.loads(path.read_text(encoding="utf-8-sig"))
    except (ValueError, UnicodeError) as exc:
        raise ValueError(f"Unreadable JSON parameter source: {source}") from exc
    value = _pointer(document, pointer)
    if type(value) not in {int, float} or not math.isfinite(value):
        raise ValueError("JSON parameter must be a finite native number, not bool or numeric text")
    if unit_pointer is not None and _pointer(document, unit_pointer) != unit:
        raise ValueError("Declared parameter unit does not match the located source unit")
    if type(places) is not int or not 0 <= places <= 12:
        raise ValueError("Parameter places must be an integer from 0 to 12")
    return {
        "raw_value": value,
        "value": format_value(value, places),
        "unit": unit,
        "operation": "json_value_ref",
        "field": "value",
        "source": relative.as_posix(),
        "json_pointer": pointer,
        **({"unit_pointer": unit_pointer} if unit_pointer is not None else {}),
    }
