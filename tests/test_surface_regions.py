import numpy as np
import pytest

pytest.importorskip("shapely")

from cfdpaper.publication.surface_regions import (
    polygon_partition_fractions,
    polygon_region_fractions,
)


def write_surface(path, vertices, faces):
    packed, starts = [], []
    for face in faces:
        starts.append(len(packed))
        packed.extend([len(face), *face])
    np.savez(
        path,
        vertices_m=np.asarray(vertices, dtype=float),
        faces_connectivity=np.asarray(packed),
        face_starts=np.asarray(starts),
    )


def test_real_overlap_keeps_unequal_faces_and_partial_boundaries(tmp_path):
    path = tmp_path / "faces.npz"
    write_surface(
        path,
        [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0], [4, 0, 0], [4, 1, 0]],
        [[0, 1, 2, 3], [1, 4, 5, 2]],
    )
    original = path.read_bytes()
    fractions = polygon_region_fractions(path, {"x": [0.5, 2], "y": [0, 1]})
    assert fractions.tolist() == pytest.approx([0.5, 1 / 3])
    assert np.dot(fractions, [1.0, 3.0]) == pytest.approx(1.5)
    assert path.read_bytes() == original


def test_triangles_many_sided_and_tilted_planar_faces_keep_area_ratio(tmp_path):
    path = tmp_path / "tilted.npz"
    # All vertices lie on z=x+y; projection has constant area scaling.
    write_surface(path, [[0, 0, 0], [2, 0, 2], [0, 2, 2]], [[0, 1, 2]])
    assert polygon_region_fractions(path, {"x": [0, 1], "y": [0, 1]})[0] == pytest.approx(0.5)
    write_surface(path, [[0, 0, 0], [2, 0, 0], [2, 1, 0], [1, 2, 0], [0, 1, 0]], [[0, 1, 2, 3, 4]])
    assert polygon_region_fractions(path, {"x": [-1, 3], "y": [-1, 3]})[0] == 1
    assert polygon_region_fractions(path, {"x": [5, 6], "y": [5, 6]})[0] == 0


@pytest.mark.parametrize(
    "vertices,faces,error",
    [
        ([[0, 0, 0], [1, 0, 0], [2, 0, 0]], [[0, 1, 2]], "degenerate"),
        ([[0, 0, 0], [1, 0, 0], [1, 1, 0.1], [0, 1, 0]], [[0, 1, 2, 3]], "planar"),
        ([[0, 0, 0], [1, 1, 0], [0, 1, 0], [1, 0, 0]], [[0, 1, 2, 3]], "valid"),
        ([[0, 0, 0], [0, 1, 0], [0, 1, 1], [0, 0, 1]], [[0, 1, 2, 3]], "projection"),
    ],
)
def test_degenerate_nonplanar_self_crossing_and_edge_on_are_rejected(
    tmp_path, vertices, faces, error
):
    path = tmp_path / "invalid.npz"
    write_surface(path, vertices, faces)
    with pytest.raises(ValueError, match=error):
        polygon_region_fractions(path, {"x": [0, 1], "y": [0, 1]})


def test_piecewise_planar_curved_surface_is_not_projected_as_one_plane(tmp_path):
    path = tmp_path / "curved.npz"
    write_surface(
        path,
        [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0], [2, 0, 1], [2, 1, 1]],
        [[0, 1, 2, 3], [1, 4, 5, 2]],
    )
    with pytest.raises(ValueError, match="planar"):
        polygon_region_fractions(path, {"x": [0, 2], "y": [0, 1]})


def test_other_projection_axes_and_invalid_box(tmp_path):
    path = tmp_path / "yz.npz"
    write_surface(path, [[0, 0, 0], [0, 1, 0], [0, 1, 1], [0, 0, 1]], [[0, 1, 2, 3]])
    assert polygon_region_fractions(path, {"y": [0, 0.5], "z": [0, 1]}, axes=(1, 2))[0] == 0.5
    with pytest.raises(ValueError, match="bounds"):
        polygon_region_fractions(path, {"x": [0, 1], "y": [1, 0]})


def test_partition_checks_actual_overlap_even_when_fraction_sum_is_one(tmp_path):
    path = tmp_path / "square.npz"
    write_surface(path, [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], [[0, 1, 2, 3]])
    left = {"x": [0, 0.5], "y": [0, 1]}
    with pytest.raises(ValueError, match="overlap"):
        polygon_partition_fractions(path, [{"bounds": left}, {"bounds": left}])


def test_partition_complement_and_two_disjoint_boxes_cover_actual_geometry(tmp_path):
    path = tmp_path / "square.npz"
    write_surface(path, [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], [[0, 1, 2, 3]])
    left = {"x": [0, 0.5], "y": [0, 1]}
    complemented = polygon_partition_fractions(
        path, [{"bounds": left}, {"bounds": left, "complement": True}]
    )
    assert [values.tolist() for values in complemented] == [[0.5], [0.5]]
    split = polygon_partition_fractions(
        path, [{"bounds": left}, {"bounds": {"x": [0.5, 1], "y": [0, 1]}}]
    )
    assert [values.tolist() for values in split] == [[0.5], [0.5]]
    with pytest.raises(ValueError, match="cover"):
        polygon_partition_fractions(path, [{"bounds": left}])


def test_partition_detects_overlap_for_complement_regions(tmp_path):
    path = tmp_path / "square.npz"
    write_surface(path, [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], [[0, 1, 2, 3]])
    excluded_right = {"x": [0.75, 1], "y": [0, 1]}
    excluded_left = {"x": [0, 0.25], "y": [0, 1]}
    with pytest.raises(ValueError, match="overlap"):
        polygon_partition_fractions(
            path,
            [
                {"bounds": excluded_right, "complement": True},
                {"bounds": excluded_left, "complement": True},
            ],
        )
