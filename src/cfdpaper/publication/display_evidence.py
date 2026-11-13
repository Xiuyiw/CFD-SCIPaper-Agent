"""Separate how a panel was drawn from what its source can be used to compare."""

from __future__ import annotations

import csv
import math
from pathlib import Path

import numpy as np
from PIL import ImageColor

from cfdpaper.publication.figure_tasks import _asset
from cfdpaper.publication.section import _read
from cfdpaper.scientific.units import convert_value


def _label(record, key):
    text = record.get(key)
    if not isinstance(text, str) or not text.strip():
        raise ValueError(f"Display evidence requires a nonblank {key}")
    return text


def _scale(record):
    def numbers(key):
        raw = record.get(key)
        if (
            not isinstance(raw, list)
            or len(raw) < 2
            or any(type(x) not in (int, float) or not math.isfinite(x) for x in raw)
        ):
            raise ValueError(f"Scale {key} must contain finite numbers")
        if any(a >= b for a, b in zip(raw, raw[1:], strict=False)):
            raise ValueError(f"Scale {key} must increase")
        return raw

    knots, positions = numbers("knots"), numbers("positions")
    colors = record.get("colors")
    if (
        positions[0] != 0
        or positions[-1] != 1
        or len(knots) != len(positions)
        or not isinstance(colors, list)
        or len(colors) != len(knots)
        or any(not isinstance(c, str) for c in colors)
    ):
        raise ValueError("Color anchors must match physical knots and positions spanning 0–1")
    clipping = record.get("clipping")
    if clipping not in {"forbid", "show-ends"}:
        raise ValueError("Declare whether clipped values are forbidden or shown at scale ends")
    return {
        "knots": knots,
        "positions": positions,
        "colors": [list(ImageColor.getcolor(c, "RGBA")) for c in colors],
        "clipping": clipping,
    }


def shared_reference_scale(reference, weights, cases, *, fractions, positions, colors, lower=None):
    """A single physical scale for several fields, calibrated on a named reference.

    Weighted inverse CDF: the first observed value whose cumulative measure reaches
    q times the total reference measure. Calibration and plotted populations can be
    different (e.g. whole wall for calibration, cropped panels for display). Values
    below an imposed lower bound or coincident quantile knots are not silently clipped
    or displaced. Adjust the chosen scale if it does not distinguish these data.
    """

    def vector(raw):
        arr = np.asarray(raw)
        if (
            arr.ndim != 1
            or not arr.size
            or arr.dtype.kind not in "fiu"
            or not np.isfinite(arr).all()
        ):
            raise ValueError("Scale fields and weights require nonempty finite numeric vectors")
        return arr.astype(float, copy=False)

    ref, w = vector(reference), vector(weights)
    if ref.shape != w.shape or np.any(w <= 0):
        raise ValueError("Reference values and positive physical weights must be aligned")
    sources = [vector(x) for x in cases]
    if not sources:
        raise ValueError("Specify the compared fields; do not guess the scale from a single panel")
    q = vector(fractions)
    if np.any(q <= 0) or np.any(q >= 1) or np.any(np.diff(q) <= 0):
        raise ValueError("Reference quantile fractions must increase strictly within (0, 1)")
    lo = min(float(x.min()) for x in (ref, *sources))
    hi = max(float(x.max()) for x in (ref, *sources))
    if lower is not None:
        if type(lower) not in (float, int) or not math.isfinite(lower) or lower > lo:
            raise ValueError("Specified lower limit clips field values")
        lo = lower
    order = np.argsort(ref)
    cum = np.cumsum(w[order], dtype=float)
    if not np.isfinite(cum[-1]):
        raise ValueError("Reference weight sum overflow")
    values = ref[order][np.searchsorted(cum, q * cum[-1], side="left")]
    scale = {
        "knots": [lo, *map(float, values), hi],
        "positions": list(positions),
        "colors": list(colors),
        "clipping": "forbid",
    }
    _scale(scale)
    return scale


def _values(path, field):
    if path.suffix.lower() == ".npz":
        with np.load(path, allow_pickle=False) as material:
            if field not in material.files:
                raise ValueError(f"Missing figure source array {field}")
            values = material[field]
            if values.dtype.kind not in "fiu":
                raise ValueError(f"Non-numeric figure source {field}")
    elif path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, strict=True)
            names = reader.fieldnames or []
            if names.count(field) != 1:
                raise ValueError(f"Missing or ambiguous figure source column {field}")
            try:
                values = np.asarray([float(row[field]) for row in reader])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Non-numeric display value in {path.name}/{field}") from exc
    else:
        raise ValueError("Use an actual CSV column or NPZ field for a quantitative panel")
    if not values.size or not np.isfinite(values).all():
        raise ValueError(f"Empty or nonfinite figure source: {path.name}/{field}")
    return values


def _converted_values(root, panel, path, raw):
    source_unit, target_unit = _label(panel, "source_unit"), _label(panel, "unit")
    zero = convert_value(0.0, source_unit, target_unit)
    if zero and panel.get("temperature_kind") != "absolute":
        raise ValueError("An offset conversion requires absolute temperature, not a difference")
    # Convert the actual values, not just the axis label, keeping the original extent.
    vals = np.array([convert_value(float(x), source_unit, target_unit) for x in raw.flat]).reshape(
        raw.shape
    )
    if not np.isfinite(vals).all():
        raise ValueError("Nonfinite converted display value")
    shown = panel.get("displayed")
    if not isinstance(shown, dict):
        raise ValueError("Locate the numerical displayed column/array to check the unit conversion")
    display_path = _asset(root, _label(shown, "source"))
    field = _label(shown, "values")
    if path.samefile(display_path) and field == panel["values"]:
        raise ValueError("Check the converted values against a distinct displayed column")
    printed = _values(display_path, field)
    if vals.shape != printed.shape or not np.allclose(vals, printed, rtol=1e-12, atol=1e-12):
        raise ValueError("Displayed numbers do not reproduce the declared unit conversion")
    return vals, {
        "source_unit": source_unit,
        "raw_source_range": [float(raw.min()), float(raw.max())],
        "displayed": {"source": shown["source"], "values": field},
        "temperature_kind": panel.get("temperature_kind"),
    }


def review_display_evidence(root, data, draft):
    """Check declared panel uses against materials; never infer raw values from pixels.

    A common map is checked numerically, including interior colour knots and the
    actual source extent. It does not prove a third-party renderer drew this map.
    'validation-comparison' identifies supplied measurement data and a separate
    prediction on declared matching support, not independent scientific approval.
    """
    root = Path(root).resolve()
    manifest = root / "display-evidence.json"
    if not manifest.exists():
        return []
    rows = _read(_asset(root, "display-evidence.json"))
    if not isinstance(rows, list) or not rows:
        raise ValueError("display-evidence.json requires a list of panel records")
    figures = {f.id for f in data.figures}
    groups, seen, reports = {}, {}, []
    for r in rows:
        fid, panel, name, kind, use = (
            _label(r, k) for k in ("figure_id", "panel", "source", "source_kind", "use")
        )
        if fid not in figures or fid not in draft["captions"] or (fid, panel) in seen:
            raise ValueError(f"Unknown figure or duplicated display panel: {fid}/{panel}")
        seen[fid, panel] = True
        path = _asset(root, name)
        if kind not in {
            "native-field",
            "reduced-table",
            "cached-image",
            "processed-table",
            "measurement",
        }:
            raise ValueError("Unknown panel source kind")
        ops = r.get("operations", [])
        allowed = {
            "node-interpolation",
            "smoothing",
            "raster-cache",
            "gap-compression",
            "unit-conversion",
            "display-normalization",
        }
        if not isinstance(ops, list) or any(
            not isinstance(op, str) or op not in allowed for op in ops
        ):
            raise ValueError("Unknown display operation")
        if use not in {"visual-reading", "quantitative-reading", "validation-comparison"}:
            raise ValueError(f"Unknown panel use: {use}")
        display_only = bool(
            set(ops)
            & {
                "smoothing",
                "node-interpolation",
                "raster-cache",
                "gap-compression",
                "display-normalization",
            }
        ) or kind in {"cached-image", "processed-table"}
        if display_only and use != "visual-reading":
            raise ValueError(
                f"{fid}/{panel}: only visual reading; locate unmodified values "
                "for a separate quantitative comparison"
            )
        out = {
            "figure_id": fid,
            "panel": panel,
            "source": name,
            "source_kind": kind,
            "operations": ops,
            "use": use,
        }
        group = r.get("comparison_group")
        if group is not None:
            group = _label(r, "comparison_group")
        scale = _scale(r["scale"]) if "scale" in r else None
        if group and scale is None:
            raise ValueError("Comparative field maps need a shared scale")
        if use != "visual-reading" or scale or "values" in r:
            out["quantity"], out["unit"] = _label(r, "quantity"), _label(r, "unit")
        if use != "visual-reading" or "values" in r or "unit-conversion" in ops:
            if kind == "cached-image":
                raise ValueError("Do not derive numerical values from cached artwork")
            field = _label(r, "values")
            vals = _values(path, field)
            if "unit-conversion" in ops:
                vals, conversion = _converted_values(root, r, path, vals)
                out["conversion"] = conversion
            out.update(
                values=field,
                source_range=[float(vals.min()), float(vals.max())],
                samples=int(vals.size),
            )
            if scale:
                outside = int(((vals < scale["knots"][0]) | (vals > scale["knots"][-1])).sum())
                if outside and scale["clipping"] == "forbid":
                    raise ValueError(
                        f"{fid}/{panel}: {outside} source values outside the declared common scale"
                    )
                out["outside_scale"] = outside
        if scale:
            out["scale"] = scale
            if "values" not in out:
                out["range_check"] = "source range unavailable; declared scale only"
        if group:
            identity = (out["quantity"], out["unit"], scale)
            if groups.setdefault(group, identity) != identity:
                raise ValueError(
                    f"{group}: quantities, units and the entire color mapping must match"
                )
            out["comparison_group"] = group
        if use == "validation-comparison":
            if kind != "measurement":
                raise ValueError("A same-solution diagnostic is not an independent measurement")
            pred = r.get("prediction")
            if not isinstance(pred, dict):
                raise ValueError("Locate the corresponding prediction and matching support")
            pr = _asset(root, _label(pred, "source"))
            if pr.samefile(path) or (
                _label(pred, "quantity"),
                _label(pred, "unit"),
                _label(pred, "support"),
            ) != (out["quantity"], out["unit"], _label(r, "support")):
                raise ValueError(
                    "Validation comparison needs distinct sources and matching physical support"
                )
            v = _values(pr, _label(pred, "values"))
            x = _values(path, _label(r, "coordinates"))
            xp = _values(pr, _label(pred, "coordinates"))
            if (
                v.shape != vals.shape
                or x.shape != vals.shape
                or xp.shape != v.shape
                or not np.array_equal(x, xp)
                or len(np.unique(x)) != x.size
            ):
                raise ValueError("Measurement and prediction sample coordinates must match exactly")
            out.update(
                prediction=pred,
                qualification="declared measurement comparison, not validation proof",
            )
        reports.append(out)
    return reports
