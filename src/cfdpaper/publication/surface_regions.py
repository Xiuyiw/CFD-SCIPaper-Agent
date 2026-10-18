"""Exact box-overlap fractions for exported polygons on one planar surface."""

from __future__ import annotations

from pathlib import Path

import numpy as np


def _geometry(path):
    with np.load(Path(path), allow_pickle=False) as bundle:
        vertices = np.array(bundle["vertices_m"], copy=True)
        connectivity = np.array(bundle["faces_connectivity"], copy=True)
        starts = np.array(bundle["face_starts"], copy=True)
    if (
        vertices.ndim != 2
        or vertices.shape[1] != 3
        or not np.issubdtype(vertices.dtype, np.number)
        or np.iscomplexobj(vertices)
        or not np.isfinite(vertices).all()
        or connectivity.ndim != 1
        or starts.ndim != 1
        or not len(starts)
        or not np.issubdtype(connectivity.dtype, np.integer)
        or not np.issubdtype(starts.dtype, np.integer)
    ):
        raise ValueError("Surface geometry needs finite 3-D vertices and integer packed faces")
    faces, cursor = [], 0
    for start in starts:
        if int(start) != cursor or cursor >= len(connectivity):
            raise ValueError("Face starts must exactly partition packed connectivity")
        count = int(connectivity[cursor])
        stop = cursor + count + 1
        if count < 3 or stop > len(connectivity):
            raise ValueError("Each polygon requires at least three vertices")
        indices = connectivity[cursor + 1 : stop]
        if (
            (indices < 0).any()
            or (indices >= len(vertices)).any()
            or len(np.unique(indices)) != len(indices)
        ):
            raise ValueError("Polygon connectivity contains invalid or repeated indices")
        faces.append(indices)
        cursor = stop
    if cursor != len(connectivity):
        raise ValueError("Face starts do not cover packed connectivity")
    return vertices.astype(float), faces


def _region_box(bounds, axes):
    try:
        from shapely.geometry import box
    except ImportError as exc:
        raise ImportError(
            "Polygon clipping requires Shapely; install cfd-paper-agent[geometry]"
        ) from exc

    if (
        not isinstance(axes, (tuple, list))
        or len(axes) != 2
        or any(type(axis) is not int or axis not in (0, 1, 2) for axis in axes)
        or axes[0] == axes[1]
    ):
        raise ValueError("Projection axes must select two different coordinates")
    names = ["xyz"[axis] for axis in axes]
    if (
        not isinstance(bounds, dict)
        or set(bounds) != set(names)
        or any(
            not isinstance(bounds[name], (tuple, list))
            or len(bounds[name]) != 2
            or any(
                type(value) not in (int, float) or not np.isfinite(value) for value in bounds[name]
            )
            or bounds[name][0] >= bounds[name][1]
            for name in names
        )
    ):
        raise ValueError(
            "Region bounds must give finite increasing limits for both projection axes"
        )
    return box(bounds[names[0]][0], bounds[names[1]][0], bounds[names[0]][1], bounds[names[1]][1])


def _projected_polygons(npz_path, axes):
    from shapely.geometry import Polygon

    vertices, faces = _geometry(npz_path)
    used = vertices[np.unique(np.concatenate(faces))]
    centered = used - used[0]
    extent = float(np.linalg.norm(np.ptp(used, axis=0)))
    if extent == 0:
        raise ValueError("Surface polygons are degenerate")
    _, singular, vectors = np.linalg.svd(centered, full_matrices=False)
    tolerance = extent * 1e-10 + float(np.abs(used).max()) * np.finfo(float).eps * 64
    if len(singular) < 2 or singular[1] <= tolerance:
        raise ValueError("Surface polygons are degenerate")
    if np.max(np.abs(centered @ vectors[-1])) > tolerance:
        raise ValueError("Polygon clipping requires one planar surface, not a curved surface")
    omitted_axis = next(axis for axis in range(3) if axis not in axes)
    if abs(vectors[-1][omitted_axis]) <= np.finfo(float).eps * 64:
        raise ValueError("Planar surface has degenerate projection on the selected axes")
    polygons = []
    for indices in faces:
        polygon = Polygon(vertices[indices][:, axes])
        if not polygon.is_valid:
            raise ValueError("Every original face must be a valid non-self-crossing polygon")
        if polygon.is_empty or polygon.area <= extent * extent * np.finfo(float).eps:
            raise ValueError("Original polygon has degenerate projection on the selected axes")
        polygons.append(polygon)
    return polygons


def polygon_region_fractions(npz_path, bounds, axes=(0, 1)) -> np.ndarray:
    """Return original planar-face overlap fractions for a coordinate box.

    Projected and physical areas have the same constant ratio on the common
    plane. Field values remain constant over each original face. This function
    checks one region only; it does not certify a collection as a partition.
    """
    region = _region_box(bounds, axes)
    return np.asarray(
        [
            min(1.0, max(0.0, float(polygon.intersection(region).area / polygon.area)))
            for polygon in _projected_polygons(npz_path, axes)
        ],
        dtype=float,
    )


def polygon_partition_fractions(npz_path, regions, axes=(0, 1)) -> list[np.ndarray]:
    """Clip actual faces and verify geometric exclusivity and complete coverage.

    A complement is taken inside each original face. Equal area fractions alone
    cannot establish that different regions occupy different parts of a face.
    """
    from shapely.ops import unary_union

    if not isinstance(regions, list) or not regions:
        raise ValueError("A polygon partition requires geometric regions")
    if any("fraction" in region for region in regions):
        raise ValueError("Polygon partition geometry cannot be proven from external fractions")
    boxes = [_region_box(region.get("bounds"), axes) for region in regions]
    fractions = [[] for _ in regions]
    for polygon in _projected_polygons(npz_path, axes):
        pieces = [
            polygon.difference(box)
            if region.get("complement", False)
            else polygon.intersection(box)
            for box, region in zip(boxes, regions, strict=True)
        ]
        union = unary_union(pieces)
        tolerance = polygon.area * 1e-12
        if sum(piece.area for piece in pieces) - union.area > tolerance:
            raise ValueError("Declared polygon partition regions overlap within an original face")
        if polygon.difference(union).area > tolerance:
            raise ValueError("Declared polygon partition regions do not cover an original face")
        for values, piece in zip(fractions, pieces, strict=True):
            values.append(min(1.0, max(0.0, float(piece.area / polygon.area))))
    return [np.asarray(values, dtype=float) for values in fractions]
