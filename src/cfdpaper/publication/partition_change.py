"""Compose temperature-mean changes from complete original-face partitions.

This finite recipe compares independently clipped regions on a common planar
surface; it does not subtract values on unmatched meshes or infer heat routes.
"""

from __future__ import annotations

import math
from copy import deepcopy
from pathlib import Path

import numpy as np


def _common_surface(path, reference, regions):
    from shapely.ops import unary_union

    from .surface_regions import _geometry, _projected_polygons

    if path.suffix.lower() != ".npz" or reference.suffix.lower() != ".npz":
        raise ValueError("Partition change requires original planar face NPZ geometry")
    bounds = regions[0].get("bounds", {}) if regions else {}
    axes = tuple(i for i, name in enumerate("xyz") if name in bounds)
    if len(axes) != 2:
        raise ValueError("Partition change requires geometric regions on two coordinate axes")
    vertices, faces = _geometry(path)
    old_vertices, old_faces = _geometry(reference)
    used = vertices[np.unique(np.concatenate(faces))]
    old_used = old_vertices[np.unique(np.concatenate(old_faces))]
    extent = float(np.linalg.norm(np.ptp(used, axis=0)))
    if not extent:
        raise ValueError("Common surface support is degenerate")
    origin = used[0]
    _, _, vectors = np.linalg.svd(used - origin, full_matrices=False)
    tolerance = extent * 1e-8 + float(np.abs(used).max()) * np.finfo(float).eps * 64
    if float(np.max(np.abs((old_used - origin) @ vectors[-1]))) > tolerance:
        raise ValueError("Partition reference and comparison must occupy the same physical plane")
    actual = unary_union(_projected_polygons(path, axes))
    original = unary_union(_projected_polygons(reference, axes))
    if actual.symmetric_difference(original).area > max(actual.area, original.area) * 1e-9:
        raise ValueError("Partition reference and comparison have different physical support")


def calculate_partition_change(path: Path, declaration: dict) -> dict:
    """Reduce both original fields and return fixed-weight temperature contributions.

    ``regions`` belongs to the comparison; ``reference_regions`` defaults to it.
    ``support_mode=moving`` explicitly permits differently located regions with
    the same physical-area fractions. Changed fractions are not silently folded
    into a fixed-weight identity: this recipe reports that prerequisite failure.
    """
    from .field_diagnostics import _integral

    options = declaration["field_options"]
    if options.get("association") != "face":
        raise ValueError("Partition change requires face association and physical face areas")
    if options.get("region_assignment") != "polygon-clip":
        raise ValueError("Partition change requires polygon-clip geometric partitions")
    if options.get("partition_complete") is not True:
        raise ValueError("Partition change requires a complete, mutually exclusive partition")
    mode = options.get("support_mode")
    if mode not in {"fixed", "moving"}:
        raise ValueError("Partition change requires support_mode fixed or moving")
    common = options.get("common_support")
    if not isinstance(common, str) or not common.strip():
        raise ValueError("Partition change requires a nonblank common_support definition")
    if declaration["units"].get("value") not in {"K", "degC"}:
        raise ValueError("Partition change requires absolute temperature in K or degC")
    if declaration.get("quantity_kind") != "absolute-temperature":
        raise ValueError("Partition change requires quantity_kind absolute-temperature")
    if declaration["units"].get("measure") != "m2":
        raise ValueError("Partition change requires physical face area units m2")
    if options.get("integrand", "weighted_mean") != "weighted_mean":
        raise ValueError("Partition change requires weighted_mean, not a heat integral")
    name = options.get("reference_source")
    if not isinstance(name, str) or not name.strip() or Path(name).is_absolute():
        raise ValueError("Partition change requires a relative reference_source")
    reference = path.parent / name
    regions = options.get("regions")
    reference_regions = options.get("reference_regions", regions)
    if not isinstance(regions, list) or not regions or not isinstance(reference_regions, list):
        raise ValueError("Partition change requires nonempty reference and comparison regions")
    if mode == "fixed" and reference_regions != regions:
        raise ValueError("Partition change fixed support requires identical region definitions")
    if [r.get("id") for r in regions] != [r.get("id") for r in reference_regions]:
        raise ValueError("Partition reference and comparison region IDs must match in order")
    _common_surface(path, reference, regions)
    current_definition = deepcopy(declaration)
    current_definition["field_options"]["integrand"] = "weighted_mean"
    old_definition = deepcopy(current_definition)
    old_definition["field_options"]["regions"] = reference_regions
    if "reference_columns" in options:
        old_definition["columns"] = options["reference_columns"]
    current = _integral(path, current_definition)
    old = _integral(reference, old_definition)
    old_groups = {g["group"]: g for g in old["groups"]}
    for label, report in (("reference", old), ("comparison", current)):
        for item in report["groups"]:
            if item["status"] != "computed":
                raise ValueError(
                    f"Partition {label} region {item['group']!r} is {item['status']}; "
                    "the temperature contribution is unavailable"
                )
    a_total = old_groups["all"]["result"]["measure"]
    b_total = current["groups"][0]["result"]["measure"]
    if not math.isclose(a_total, b_total, rel_tol=1e-6, abs_tol=0):
        raise ValueError("Partition physical support has unequal total face areas")
    groups = []
    for item in current["groups"]:
        previous = old_groups[item["group"]]
        a, b = previous["result"], item["result"]
        wa, wb = a["measure"] / a_total, b["measure"] / b_total
        if not math.isclose(wa, wb, rel_tol=1e-6, abs_tol=1e-12):
            raise ValueError(
                f"Partition region {item['group']!r} area weights changed; "
                "the fixed-weight temperature decomposition is inapplicable"
            )
        difference = b["weighted_mean"] - a["weighted_mean"]
        # Reference-area weighting is explicit. Floating-point geometry can make
        # equal nominal supports differ very slightly; both weights are retained.
        contribution = wa * difference
        locations = {key: value for key, value in item.items() if key.endswith("indices")}
        locations.update(
            {
                "reference_" + key: value
                for key, value in previous.items()
                if key.endswith("indices")
            }
        )
        groups.append(
            {
                "group": item["group"],
                "status": "computed",
                "result": {
                    "reference_mean": a["weighted_mean"],
                    "comparison_mean": b["weighted_mean"],
                    "difference_mean": difference,
                    "reference_weight": wa,
                    "comparison_weight": wb,
                    "contribution": contribution,
                    "measure": b["measure"],
                },
                **locations,
            }
        )
    contribution_sum = math.fsum(item["result"]["contribution"] for item in groups[1:])
    overall = groups[0]["result"]["difference_mean"]
    return {
        "groups": groups,
        "result_units": {
            "reference_mean": declaration["units"]["value"],
            "comparison_mean": declaration["units"]["value"],
            "difference_mean": "K",
            "contribution": "K",
            "reference_weight": "",
            "comparison_weight": "",
            "measure": "m2",
        },
        "reference_source": name,
        "support_mode": mode,
        "common_support": common,
        "contribution_sum": contribution_sum,
        "closure_error": contribution_sum - overall,
        "partition": current["partition"],
        "weight_basis": "reference physical area; equal regional area fractions checked",
        "evidence_role": "same-solution-temperature-composition",
        "interpretation": (
            "Moving regions follow the source and do not represent the same physical location. "
            if mode == "moving"
            else "Fixed regions refer to the same physical location on the common surface. "
        )
        + "Contributions in K compose an area-weighted temperature change, not heat or causality.",
    }
