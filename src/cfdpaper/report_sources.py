"""Project explicitly selected JSON report numbers into a portable source table."""

from __future__ import annotations

import csv
import json
import math
import re
from copy import deepcopy
from pathlib import Path

from cfdpaper.publication.parameter_evidence import _pointer
from cfdpaper.publication.section import _stage
from cfdpaper.scientific.units import convert_value


def _identities(records, kind):
    if not isinstance(records, list) or not records:
        raise ValueError(f"{kind} must be a nonempty list")
    seen = set()
    for record in records:
        identity = record.get("id") if isinstance(record, dict) else None
        if not isinstance(identity, str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_.-]*", identity
        ):
            raise ValueError(f"{kind} ID must be a simple portable identifier: {identity!r}")
        if identity.casefold() in seen:
            raise ValueError(f"Duplicate {kind} ID: {identity!r}")
        seen.add(identity.casefold())


def _members(quantity):
    identity = quantity["id"]
    for key in ("label", "unit", "domain"):
        if not isinstance(quantity.get(key), str) or not quantity[key].strip():
            raise ValueError(f"Quantity {identity!r} requires a nonblank {key}")
    target = quantity.get("output_unit", quantity["unit"])
    if not isinstance(target, str) or not target.strip():
        raise ValueError(f"Quantity {identity!r} requires a nonblank output_unit")
    kind = quantity.get("quantity_kind", "ordinary")
    if kind not in {"ordinary", "absolute-temperature", "temperature-difference"}:
        raise ValueError(f"Quantity {identity!r}: unknown quantity_kind {kind!r}")
    if kind == "temperature-difference" and (quantity["unit"] != "K" or target != "K"):
        raise ValueError(f"Quantity {identity!r}: temperature-difference requires Kelvin units")
    if kind == "absolute-temperature" and (
        quantity["unit"] not in {"K", "degC", "°C", "C"} or target not in {"K", "degC", "°C", "C"}
    ):
        raise ValueError(f"Quantity {identity!r}: absolute-temperature requires Celsius or Kelvin")
    if "pointer" in quantity and not {"reference", "comparison"} & quantity.keys():
        members = [("value", quantity["pointer"])]
    elif "pointer" not in quantity and {"reference", "comparison"} <= quantity.keys():
        members = [(member, quantity[member]) for member in ("reference", "comparison")]
    else:
        raise ValueError(f"Quantity {identity!r} requires pointer or reference and comparison")
    return members, target


def project_reports(root: Path, cases: list[dict], quantities: list[dict], output: Path) -> dict:
    """Copy selected reports and expose finite exact-pointer numbers as CSV rows.

    ``pointer`` selects a scalar, while ``reference`` and ``comparison`` select
    paired endpoints. The existing paired-change engine owns comparison minus
    reference; this function does not calculate differences or infer units.
    All pointers apply identically to every case. Returned paths are relative
    to the fresh output directory, including each row's copied JSON source.
    """
    root = Path(root).resolve()
    output = Path(output)
    with _stage(output) as staged:
        _identities(cases, "Case")
        _identities(quantities, "Quantity")
        selections = [(quantity, *_members(quantity)) for quantity in quantities]
        records = staged / "sources/records"
        records.mkdir(parents=True)
        rows = []
        source_files = ["sources/report-values.csv"]
        for case in cases:
            source = case.get("source")
            context = f"case {case['id']!r}, file {source!r}"
            if not isinstance(source, str) or not source.strip():
                raise ValueError(f"{context}: source must be a relative JSON file")
            relative = Path(source)
            path = (root / relative).resolve()
            if (
                relative.is_absolute()
                or ".." in relative.parts
                or relative.suffix.lower() != ".json"
                or not path.is_relative_to(root)
                or not path.is_file()
            ):
                raise ValueError(
                    f"{context}: source must be an existing relative JSON file in root"
                )
            try:
                raw = path.read_bytes()
                document = json.loads(raw.decode("utf-8-sig"))
            except (OSError, ValueError, UnicodeError) as exc:
                raise ValueError(
                    f"{context}, pointer '<document>': unreadable JSON report"
                ) from exc
            copied = f"sources/records/{case['id']}.json"
            (staged / copied).write_bytes(raw)
            source_files.append(copied)
            for quantity, members, target in selections:
                for member, pointer in members:
                    location = f"{context}, pointer {pointer!r}"
                    try:
                        value = _pointer(document, pointer)
                        if type(value) not in {int, float} or not math.isfinite(value):
                            raise ValueError(
                                "value must be a finite native number, not bool or text"
                            )
                        if quantity["unit"] != target:
                            value = convert_value(value, quantity["unit"], target)
                        if not math.isfinite(value):
                            raise ValueError("converted value must be finite")
                    except (ValueError, OverflowError) as exc:
                        raise ValueError(f"{location}: {exc}") from exc
                    rows.append(
                        {
                            "case_id": case["id"],
                            "quantity": quantity["id"],
                            "member": member,
                            "value": value,
                            "unit": target,
                            "source": copied,
                            "pointer": pointer,
                        }
                    )
        with (staged / source_files[0]).open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=["case_id", "quantity", "member", "value", "unit", "source", "pointer"],
            )
            writer.writeheader()
            writer.writerows(rows)
    return {
        "source": source_files[0],
        "source_files": source_files,
        "cases": [case["id"] for case in cases],
        "quantities": deepcopy(quantities),
        "row_count": len(rows),
    }
