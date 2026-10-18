"""Physical reductions on declared original elements and compatible paired fields.

Region boxes either assign centroids or clip original planar polygons. An explicit
fraction column may contain externally calculated clipped element fractions.
All modes preserve the declared element-constant field values.
"""

import math
import re
from pathlib import Path

from cfdpaper.publication.table_evidence import format_value, read_source_records


def _number(row, key):
    value = row[key]
    if value is None or not str(value).strip():
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid numeric field {key}: {value!r}") from exc
    if not math.isfinite(number):
        raise ValueError(f"Nonfinite field {key}")
    return number


def _locations(path, indices, prefix=""):
    return {
        prefix + ("array_indices" if path.suffix.lower() == ".npz" else "csv_records"): [
            i if path.suffix.lower() == ".npz" else i + 2 for i in indices
        ]
    }


def _measure_unit(options):
    kind = options.get("measure_kind", "volume" if options.get("association") == "cell" else "area")
    if kind not in {"area", "volume"}:
        raise ValueError("measure_kind must be area or volume")
    if (
        options.get("association") in {"face", "cell"}
        and kind != {"face": "area", "cell": "volume"}[options["association"]]
    ):
        raise ValueError("Element measure_kind must match face or cell association")
    return kind, "m2" if kind == "area" else "m3"


def _unit(unit):
    return (
        unit.replace("²", "2").replace("³", "3").replace("^", "") if isinstance(unit, str) else unit
    )


def _regions(path, rows, columns, options):
    result = [("all", [1.0] * len(rows))]
    regions = options.get("regions", [])
    polygon_partition = None
    if options.get("partition_complete") and options.get("region_assignment") == "polygon-clip":
        from cfdpaper.publication.surface_regions import polygon_partition_fractions

        first_bounds = regions[0].get("bounds", {}) if regions else {}
        axes = tuple(index for index, name in enumerate(("x", "y", "z")) if name in first_bounds)
        polygon_partition = polygon_partition_fractions(path, regions, axes=axes)
    names = {"all"}
    for region_index, region in enumerate(regions):
        name = region.get("id")
        if not isinstance(name, str) or not name.strip() or name in names:
            raise ValueError("Each region requires a unique nonempty id other than all")
        names.add(name)
        if "fraction" in region:
            fractions = [_number(row, region["fraction"]) for row in rows]
            if any(v is None or not 0 <= v <= 1 for v in fractions):
                raise ValueError("Region fractions must be finite and between zero and one")
            if region.get("complement", False):
                fractions = [1 - v for v in fractions]
        elif options.get("region_assignment") == "polygon-clip":
            from cfdpaper.publication.surface_regions import polygon_region_fractions

            bounds = region.get("bounds")
            if (
                not isinstance(bounds, dict)
                or len(bounds) != 2
                or not set(bounds) <= {"x", "y", "z"}
            ):
                raise ValueError("Polygon clipping requires bounds on two named coordinate axes")
            axes = tuple(index for index, name in enumerate(("x", "y", "z")) if name in bounds)
            fractions = (
                list(polygon_partition[region_index])
                if polygon_partition is not None
                else list(polygon_region_fractions(path, bounds, axes=axes))
            )
            if len(fractions) != len(rows) or any(
                not math.isfinite(value) or not 0 <= value <= 1 for value in fractions
            ):
                raise ValueError("Clipped fractions must match physical elements")
            if polygon_partition is None and region.get("complement", False):
                fractions = [1 - value for value in fractions]
        else:
            bounds = region.get("bounds")
            if (
                options.get("region_assignment") != "centroid"
                or not isinstance(bounds, dict)
                or not bounds
            ):
                raise ValueError("Bounds require explicit centroid region_assignment")
            for axis, limits in bounds.items():
                if (
                    axis not in {"x", "y", "z"}
                    or axis not in columns
                    or not isinstance(limits, list)
                    or len(limits) != 2
                    or not all(type(v) in (int, float) and math.isfinite(v) for v in limits)
                    or limits[0] >= limits[1]
                ):
                    raise ValueError(
                        "Region bounds require available coordinates and increasing finite limits"
                    )
            fractions = []
            for row in rows:
                inside = True
                for axis, (lower, upper) in bounds.items():
                    value = _number(row, columns[axis])
                    if value is None:
                        raise ValueError("Region coordinate is missing")
                    inside = inside and lower <= value < upper
                fractions.append(float(inside))
        result.append((name, fractions))
    if options.get("partition_complete"):
        if not regions:
            raise ValueError("Complete partition requires regions")
        sums = [math.fsum(fractions[i] for _, fractions in result[1:]) for i in range(len(rows))]
        if any(value > 1 + 1e-12 for value in sums):
            raise ValueError("Declared partition regions overlap")
        if any(abs(value - 1) > 1e-12 for value in sums):
            raise ValueError("Declared partition regions do not cover all elements")
    return result


def _requested(columns, options):
    return list(
        dict.fromkeys(
            [
                *columns.values(),
                *(
                    region["fraction"]
                    for region in options.get("regions", [])
                    if "fraction" in region
                ),
            ]
        )
    )


def _records(path, requested):
    selectors = {key: re.fullmatch(r"(.+)\[([012])\]", key) for key in requested}
    selectors = {key: match for key, match in selectors.items() if match}
    if path.suffix.lower() != ".npz" or not selectors:
        return read_source_records(path, requested)
    import numpy as np

    plain = [key for key in requested if key not in selectors]
    rows = read_source_records(path, plain)
    with np.load(path, allow_pickle=False) as archive:
        for key, match in selectors.items():
            array = archive[match[1]]
            if array.ndim != 2 or array.shape != (len(rows), 3) or array.dtype.kind not in "biuf":
                raise ValueError("NPZ component selector requires an aligned numeric N by 3 array")
            for index, row in enumerate(rows):
                row[key] = str(array[index, int(match[2])].item())
    return rows


def _native_polygon_spec(path):
    if path.suffix.lower() != ".npz":
        return None
    import numpy as np

    specification = {
        "vertices": "vertices_m",
        "connectivity": "faces_connectivity",
        "starts": "face_starts",
    }
    with np.load(path, allow_pickle=False) as archive:
        return specification if set(specification.values()) <= set(archive.files) else None


def _polygons(path, specification, count):
    """Read explicitly named native count-prefixed face connectivity."""
    import numpy as np

    if path.suffix.lower() != ".npz" or set(specification) != {
        "vertices",
        "connectivity",
        "starts",
    }:
        raise ValueError("Polygon geometry requires NPZ vertices/connectivity/starts keys")
    with np.load(path, allow_pickle=False) as archive:
        vertices = np.asarray(archive[specification["vertices"]], dtype=float)
        connectivity = archive[specification["connectivity"]]
        starts = archive[specification["starts"]]
        if (
            vertices.ndim != 2
            or vertices.shape[1] != 3
            or not np.isfinite(vertices).all()
            or connectivity.ndim != 1
            or connectivity.dtype.kind not in "iu"
            or starts.ndim != 1
            or starts.dtype.kind not in "iu"
            or len(starts) != count
        ):
            raise ValueError("Invalid original polygon geometry arrays")
        polygons = []
        ends = [*starts[1:], len(connectivity)]
        for start, end in zip(starts, ends, strict=True):
            if not 0 <= start < end <= len(connectivity):
                raise ValueError("Invalid polygon connectivity offsets")
            length = int(connectivity[start])
            ids = connectivity[start + 1 : end]
            if length < 3 or len(ids) != length or np.any(ids < 0) or np.any(ids >= len(vertices)):
                raise ValueError("Invalid polygon vertex indices")
            polygon = vertices[ids]
            polygons.append(polygon[np.lexsort((polygon[:, 2], polygon[:, 1], polygon[:, 0]))])
    return polygons


def _integral(path, declaration):
    columns, units, options = (
        declaration["columns"],
        declaration["units"],
        declaration["field_options"],
    )
    integrand = options.get("integrand", "density")
    orientation = options.get("orientation", 1)
    if type(orientation) not in (int, float) or orientation not in {-1, 1}:
        raise ValueError("orientation must be +1 or -1")
    signed_totals = integrand == "signed_totals"
    associations = (
        {"face", "cell", "region", "integrated_region"} if signed_totals else {"face", "cell"}
    )
    if options.get("association") not in associations:
        raise ValueError("Physical integration requires declared face or cell association")
    _, measure_unit = _measure_unit(options)
    vector = integrand == "vector_flux"
    if signed_totals:
        if not {"positive", "negative"} <= columns.keys():
            raise ValueError("Signed totals require positive and negative contribution columns")
        integrated_unit = units.get("positive")
        if integrated_unit not in {"W", "kW", "MW"} or units.get("negative") != integrated_unit:
            raise ValueError("Signed totals require identical positive/negative power units")
        if "measure" in columns:
            measure_unit = _unit(units.get("measure"))
            if measure_unit not in {"m2", "cm2", "mm2", "m3", "cm3", "mm3"}:
                raise ValueError("Signed totals measure requires an explicit area or volume unit")
        value_unit = integrated_unit + "/" + measure_unit
    elif vector:
        required = {"qx", "qy", "qz", "ax", "ay", "az"}
        if not required <= columns.keys() or options.get("association") != "face":
            raise ValueError("Vector flux requires qx/qy/qz and oriented ax/ay/az on faces")
        if any(_unit(units.get(key)) != "W/m2" for key in ("qx", "qy", "qz")) or any(
            _unit(units.get(key)) != "m2" for key in ("ax", "ay", "az")
        ):
            raise ValueError("Vector flux units must be W/m2 and oriented m2")
        integrated_unit, value_unit = "W", "W/m2"
    else:
        if "value" not in columns or integrand not in {"element_total", "density", "weighted_mean"}:
            raise ValueError("Scalar integral requires value and a supported integrand")
        value_unit = _unit(units.get("value"))
        if value_unit in {"K", "degC"} and orientation != 1:
            raise ValueError("orientation cannot reverse an absolute temperature field")
        if integrand == "element_total":
            if value_unit not in {"W", "kW", "MW"}:
                raise ValueError("Element total requires W, kW or MW units")
            integrated_unit = value_unit
        else:
            if "measure" not in columns:
                raise ValueError("Density or weighted mean requires element measure")
            densities = {
                "W/" + measure_unit: "W",
                "kW/" + measure_unit: "kW",
                "MW/" + measure_unit: "MW",
            }
            if value_unit in densities:
                integrated_unit = densities[value_unit]
            elif value_unit in {"K", "degC"} and integrand == "weighted_mean":
                integrated_unit = value_unit + "·" + measure_unit
            else:
                raise ValueError(
                    "Value unit does not match measure unit; temperature requires weighted_mean"
                )
        if "measure" in columns and _unit(units.get("measure")) != measure_unit:
            raise ValueError("Element measure unit does not match area/volume definition")
    filters = options.get("row_filters", {})
    if not isinstance(filters, dict) or any(
        not isinstance(key, str) or not isinstance(value, str) for key, value in filters.items()
    ):
        raise ValueError("row_filters must contain exact column/string values")
    if filters and path.suffix.lower() != ".csv":
        raise ValueError("row_filters require a CSV source")
    original_rows = _records(path, list(dict.fromkeys([*_requested(columns, options), *filters])))
    source_indices = [
        i
        for i, row in enumerate(original_rows)
        if all(row[key] == value for key, value in filters.items())
    ]
    rows = [original_rows[i] for i in source_indices]
    measures, values, terms, positive_terms, negative_terms = [], [], [], [], []
    for row in rows:
        if signed_totals:
            positive = _number(row, columns["positive"])
            negative = _number(row, columns["negative"])
            if (positive is not None and positive < 0) or (negative is not None and negative > 0):
                raise ValueError("Signed totals require positive >= 0 and negative <= 0")
            positive_terms.append(
                positive if orientation == 1 else None if negative is None else -negative
            )
            negative_terms.append(
                negative if orientation == 1 else None if positive is None else -positive
            )
            value = None
            term = None if positive is None or negative is None else positive + negative
            measure = _number(row, columns["measure"]) if "measure" in columns else None
        elif vector:
            q = [_number(row, columns[k]) for k in ("qx", "qy", "qz")]
            area = [_number(row, columns[k]) for k in ("ax", "ay", "az")]
            measure = None if None in area else math.sqrt(math.fsum(v * v for v in area))
            term = (
                None
                if None in q or None in area
                else math.fsum(a * b for a, b in zip(q, area, strict=True))
            )
            value = None if term is None or not measure else term / measure
        else:
            value = _number(row, columns["value"])
            measure = _number(row, columns["measure"]) if "measure" in columns else None
            term = (
                value
                if integrand == "element_total"
                else None
                if value is None or measure is None
                else value * measure
            )
        if measure is not None and measure <= 0:
            raise ValueError("Physical element measure must be positive")
        measures.append(measure)
        values.append(value)
        terms.append(None if term is None else orientation * term)
    groups = []
    for name, fractions in _regions(path, rows, columns, options):
        selected = [i for i, fraction in enumerate(fractions) if fraction > 0]
        location = _locations(path, [source_indices[i] for i in selected])
        if not selected or any(terms[i] is None for i in selected):
            groups.append(
                {
                    "group": name,
                    "status": "empty" if not selected else "missing",
                    "result": None,
                    **location,
                }
            )
            continue
        contributions = [terms[i] * fractions[i] for i in selected]
        measure = (
            None
            if any(measures[i] is None for i in selected)
            else math.fsum(measures[i] * fractions[i] for i in selected)
        )
        net = math.fsum(contributions)
        result = {
            "net": net,
            "positive": math.fsum(v for v in contributions if v > 0),
            "negative": math.fsum(v for v in contributions if v < 0),
            "absolute": math.fsum(abs(v) for v in contributions),
            "measure": measure,
            "count": len(selected),
            "weighted_mean": net / measure if measure else None,
        }
        if signed_totals:
            result["positive"] = math.fsum(positive_terms[i] * fractions[i] for i in selected)
            result["negative"] = math.fsum(negative_terms[i] * fractions[i] for i in selected)
            result["absolute"] = result["positive"] - result["negative"]
        groups.append({"group": name, "status": "computed", "result": result, **location})
    mean_unit = value_unit if integrand != "element_total" else integrated_unit + "/" + measure_unit
    return {
        "groups": groups,
        "result_units": {
            **dict.fromkeys(["net", "positive", "negative", "absolute"], integrated_unit),
            "weighted_mean": mean_unit,
            "measure": measure_unit,
            "count": "",
        },
        "region_assignment": "polygon-clip"
        if options.get("region_assignment") == "polygon-clip"
        else "explicit-fraction-or-centroid-half-open"
        if any("fraction" in r for r in options.get("regions", []))
        else "centroid-half-open",
        "partition": {
            "complete": bool(options.get("partition_complete")),
            "verification": "original-polygon-overlap-and-union"
            if options.get("partition_complete")
            and options.get("region_assignment") == "polygon-clip"
            else "per-element-fraction-sum; external fraction geometry not checked"
            if any("fraction" in region for region in options.get("regions", []))
            else "centroid-membership; no subface geometric coverage claim",
        },
        "evidence_role": "same-solution-complementary-diagnostic",
        "sign_convention": (
            f"Stored element contributions multiplied by {orientation:+g}; "
            "positive and negative contributions use this reported orientation."
        ),
    }


def _difference(path, declaration):
    columns, units, options = (
        declaration["columns"],
        declaration["units"],
        declaration["field_options"],
    )
    association = options.get("association")
    if association not in {"point", "face", "cell"}:
        raise ValueError("Difference requires explicit point, face or cell association")
    separate = "reference_source" in options
    value_key = "value" if separate else "comparison"
    required = {value_key, "x", "y", "z"}
    if association in {"face", "cell"}:
        required.add("measure")
    if not separate:
        required |= {"reference", "reference_x", "reference_y", "reference_z"}
        if association != "point":
            required.add("reference_measure")
    if not required <= columns.keys():
        raise ValueError(
            "Difference requires actual geometry coordinates and matching element measures"
        )
    value_unit = _unit(units.get(value_key))
    if not isinstance(value_unit, str) or not value_unit:
        raise ValueError("Difference requires declared value units")
    if not separate and _unit(units.get("reference")) != value_unit:
        raise ValueError("Difference value units must match")
    for axis in ("x", "y", "z"):
        if _unit(units.get(axis)) != "m" or (
            not separate and _unit(units.get("reference_" + axis)) != "m"
        ):
            raise ValueError("Geometry coordinate units must be m")
    _, measure_unit = _measure_unit(options)
    if association != "point" and (
        _unit(units.get("measure")) != measure_unit
        or (not separate and _unit(units.get("reference_measure")) != measure_unit)
    ):
        raise ValueError("Difference measure units must match association")
    rows = _records(path, _requested(columns, options))
    reference_path = path.parent / options["reference_source"] if separate else path
    reference_columns = (
        options.get("reference_columns", columns)
        if separate
        else {
            "value": columns["reference"],
            **{axis: columns["reference_" + axis] for axis in ("x", "y", "z")},
            **({"measure": columns["reference_measure"]} if association != "point" else {}),
        }
    )
    if separate and not required <= reference_columns.keys():
        raise ValueError("Reference columns do not provide matching geometry")
    reference_rows = (
        _records(reference_path, list(dict.fromkeys(reference_columns.values())))
        if separate
        else rows
    )
    if len(reference_rows) != len(rows):
        raise ValueError(
            "Different geometry requires common physical regions; no pointwise subtraction"
        )
    identity = (
        "element_id"
        if separate and "element_id" in columns and "element_id" in reference_columns
        else None
    )

    def key(row, mapping):
        return (
            row[mapping[identity]]
            if identity
            else tuple(_number(row, mapping[axis]) for axis in ("x", "y", "z"))
        )

    lookup = {}
    for i, row in enumerate(reference_rows):
        identity_key = key(row, reference_columns)
        if identity_key in lookup:
            raise ValueError("Geometry match is ambiguous; provide unique element_id")
        lookup[identity_key] = i
    tolerance = options.get("geometry_tolerance", 0.0)
    if type(tolerance) not in (int, float) or not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("Geometry tolerance must be finite and nonnegative")
    mapping, differences, baseline, current, measures = [], [], [], [], []
    matched_indices = set()
    polygon_spec = options.get("polygon_geometry") or _native_polygon_spec(path)
    reference_polygon_spec = (
        options.get("reference_polygon_geometry")
        or options.get("polygon_geometry")
        or _native_polygon_spec(reference_path)
    )
    if bool(polygon_spec) != bool(reference_polygon_spec):
        raise ValueError("Original polygon geometry must be available for both paired fields")
    polygons = _polygons(path, polygon_spec, len(rows)) if polygon_spec else None
    reference_polygons = (
        _polygons(
            reference_path,
            reference_polygon_spec,
            len(reference_rows),
        )
        if polygon_spec
        else None
    )
    extra_geometry = options.get("geometry_columns", [])
    for row in rows:
        identity_key = key(row, columns)
        if identity_key not in lookup:
            raise ValueError(
                "Different geometry requires common physical regions; geometry identity differs"
            )
        index = lookup[identity_key]
        if index in matched_indices:
            raise ValueError("Comparison geometry must have unique one-to-one element identities")
        matched_indices.add(index)
        reference_row = reference_rows[index]
        if polygons is not None:
            import numpy as np

            if polygons[len(mapping)].shape != reference_polygons[index].shape or not np.allclose(
                polygons[len(mapping)], reference_polygons[index], atol=tolerance, rtol=0
            ):
                raise ValueError("Original polygon geometry differs; use common physical regions")
        for role in [
            "x",
            "y",
            "z",
            *(["measure"] if association != "point" else []),
            *extra_geometry,
        ]:
            if role not in columns or role not in reference_columns:
                raise ValueError("Declared geometry columns must exist in both fields")
            actual, original = (
                _number(row, columns[role]),
                _number(reference_row, reference_columns[role]),
            )
            if (
                actual is None
                or original is None
                or not math.isclose(actual, original, rel_tol=0, abs_tol=tolerance)
            ):
                raise ValueError("Field geometry/association differs; use common regions instead")
        a, b = _number(reference_row, reference_columns["value"]), _number(row, columns[value_key])
        weight = 1.0 if association == "point" else _number(row, columns["measure"])
        if weight is None or weight <= 0:
            raise ValueError("Difference requires positive physical measures")
        mapping.append(index)
        differences.append(None if a is None or b is None else b - a)
        baseline.append(a)
        current.append(b)
        measures.append(weight)
    groups = []
    for name, fractions in _regions(path, rows, columns, options):
        indices = [i for i, fraction in enumerate(fractions) if fraction > 0]
        locations = {
            **_locations(path, indices),
            **_locations(reference_path, [mapping[i] for i in indices], "reference_"),
        }
        if not indices or any(differences[i] is None for i in indices):
            groups.append(
                {
                    "group": name,
                    "status": "empty" if not indices else "missing",
                    "result": None,
                    **locations,
                }
            )
            continue
        measure = math.fsum(measures[i] * fractions[i] for i in indices)
        result = {
            "weighted_mean": math.fsum(differences[i] * measures[i] * fractions[i] for i in indices)
            / measure,
            "reference_weighted_mean": math.fsum(
                baseline[i] * measures[i] * fractions[i] for i in indices
            )
            / measure,
            "comparison_weighted_mean": math.fsum(
                current[i] * measures[i] * fractions[i] for i in indices
            )
            / measure,
            "minimum": min(differences[i] for i in indices),
            "maximum": max(differences[i] for i in indices),
            "measure": measure,
            "count": len(indices),
        }
        result.update(
            reference_mean=result["reference_weighted_mean"],
            comparison_mean=result["comparison_weighted_mean"],
            difference_mean=result["weighted_mean"],
        )
        groups.append({"group": name, "status": "computed", "result": result, **locations})
    result_unit = "K" if value_unit == "degC" else value_unit
    return {
        "groups": groups,
        "reference_source": (
            Path(declaration["source"]).parent / options["reference_source"]
        ).as_posix()
        if separate
        else declaration["source"],
        "result_units": {
            **dict.fromkeys(["weighted_mean", "minimum", "maximum"], result_unit),
            "reference_weighted_mean": value_unit,
            "comparison_weighted_mean": value_unit,
            "reference_mean": value_unit,
            "comparison_mean": value_unit,
            "difference_mean": result_unit,
            "measure": "" if association == "point" else measure_unit,
            "count": "",
        },
        "elements": [
            {
                "index": i,
                "reference_index": mapping[i],
                "reference": baseline[i],
                "comparison": current[i],
                "difference": differences[i],
                "measure": measures[i],
                **{axis: _number(row, columns[axis]) for axis in ("x", "y", "z")},
            }
            for i, row in enumerate(rows)
        ],
        "evidence_role": "same-solution-matched-difference",
        "geometry_support": [
            "x",
            "y",
            "z",
            *(["measure"] if association != "point" else []),
            *extra_geometry,
            *(["original-polygon-vertices"] if polygon_spec else []),
        ],
    }


def _budget(path, declaration):
    columns, units, options = (
        declaration["columns"],
        declaration["units"],
        declaration["field_options"],
    )
    required = {"input", "output", "source"}
    if not required <= columns.keys() or (
        "storage" not in columns and options.get("steady_state") is not True
    ):
        raise ValueError(
            "Budget requires input, output, source and storage or explicit steady_state"
        )
    if set(columns) - {"input", "output", "source", "storage"}:
        raise ValueError("Budget accepts only independent input/output/source/storage terms")
    value_unit = units.get("input")
    if value_unit not in {"W", "kW", "MW"} or any(
        units.get(role) != value_unit for role in columns
    ):
        raise ValueError("Budget terms require identical power units")
    rows = _records(path, list(columns.values()))
    values = {role: [_number(row, column) for row in rows] for role, column in columns.items()}
    if any(
        value < 0 for role in ("input", "output") for value in values[role] if value is not None
    ):
        raise ValueError(
            "Budget input/output magnitudes must be nonnegative; source/storage may be signed"
        )
    locations = _locations(path, list(range(len(rows))))
    result = None
    status = (
        "missing"
        if any(value is None for series in values.values() for value in series)
        else "empty"
        if not rows
        else "computed"
    )
    if status == "computed":
        result = {role: math.fsum(series) for role, series in values.items()}
        result.setdefault("storage", 0.0)
        result["residual"] = (
            result["input"] + result["source"] - result["output"] - result["storage"]
        )
        scale = max(
            abs(result["input"]) + abs(result["source"]),
            abs(result["output"]) + abs(result["storage"]),
        )
        result["relative_residual"] = result["residual"] / scale if scale else None
        result["count"] = len(rows)
    return {
        "groups": [{"group": "all", "status": status, "result": result, **locations}],
        "result_units": {
            **dict.fromkeys(["input", "output", "source", "storage", "residual"], value_unit),
            "relative_residual": "",
            "count": "",
        },
        "evidence_role": "same-solution-budget",
        "residual_definition": "input + source - output - storage",
        "residual_scale": "max(abs(input)+abs(source), abs(output)+abs(storage))",
    }


def calculate_field_diagnostic(path: Path, declaration: dict) -> dict:
    """Calculate a declared physical operation with original source locations."""
    path = Path(path)
    operation = declaration.get("operation")
    if operation not in {"field_integral", "field_difference", "energy_budget"}:
        raise ValueError("Unsupported field diagnostic operation")
    for key in ("id", "source", "domain"):
        if not isinstance(declaration.get(key), str) or not declaration[key].strip():
            raise ValueError(f"Field diagnostic requires {key}")
    if (
        not isinstance(declaration.get("columns"), dict)
        or not isinstance(declaration.get("units"), dict)
        or not isinstance(declaration.get("field_options"), dict)
    ):
        raise ValueError("Field diagnostic requires columns, units and field_options")
    calculation = {
        "field_integral": _integral,
        "field_difference": _difference,
        "energy_budget": _budget,
    }[operation](path, declaration)
    return {
        **{key: declaration[key] for key in ("operation", "id", "source", "domain", "units")},
        **(
            {"quantity_kind": declaration["quantity_kind"]}
            if "quantity_kind" in declaration
            else {}
        ),
        "field_options": declaration["field_options"],
        "columns": declaration["columns"],
        **calculation,
    }


def resolve_field_result(report, group, field, places=3, percentage=False):
    """Bind one scalar while retaining exact zero-based NPZ or CSV record locations."""
    if type(places) is not int or not 0 <= places <= 12 or type(percentage) is not bool:
        raise ValueError("Field result requires 0–12 places and boolean percentage")
    groups = [item for item in report.get("groups", []) if item.get("group") == group]
    if len(groups) != 1 or groups[0].get("status") != "computed":
        raise ValueError("Field result unavailable for the exact selected group")
    selected = groups[0]
    value = selected["result"].get(field)
    unit = report.get("result_units", {}).get(field)
    if type(value) not in (int, float) or not math.isfinite(value) or not isinstance(unit, str):
        raise ValueError("Field result is missing, nonfinite or lacks declared unit")
    if percentage and field != "relative_residual":
        raise ValueError("Percentage is supported only for relative_residual")
    locations = {
        key: selected[key]
        for key in (
            "array_indices",
            "csv_records",
            "reference_array_indices",
            "reference_csv_records",
        )
        if key in selected
    }
    return {
        "calculation_id": report["id"],
        "operation": report["operation"],
        "group": group,
        "field": field,
        "source": report["source"],
        "source_columns": report.get("columns", {}),
        "domain": report["domain"],
        "raw_value": value,
        "unit": "%" if percentage else unit,
        "value": format_value(value * 100 if percentage else value, places),
        **locations,
        **(
            {"reference_source": report["reference_source"]} if "reference_source" in report else {}
        ),
    }
