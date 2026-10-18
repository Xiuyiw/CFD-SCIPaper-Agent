import csv

import numpy as np
import pytest

from cfdpaper.publication.field_diagnostics import (
    calculate_field_diagnostic,
    resolve_field_result,
)


def declaration(operation="field_integral", **extra):
    return {
        "id": "heat",
        "source": "source.npz",
        "domain": "physical faces",
        "operation": operation,
        "columns": {"value": "q", "measure": "area"},
        "units": {"value": "W/m2", "measure": "m2"},
        "field_options": {"association": "face", "integrand": "density"},
        **extra,
    }


def summary(report, group="all"):
    return next(item["result"] for item in report["groups"] if item["group"] == group)


def test_unequal_areas_and_signed_cancellation_keep_physical_power(tmp_path):
    path = tmp_path / "field.npz"
    np.savez(path, q=[10.0, -4.0], area=[2.0, 3.0])
    report = calculate_field_diagnostic(path, declaration())
    assert summary(report)["net"] == 8
    assert summary(report)["positive"] == 20
    assert summary(report)["negative"] == -12
    assert summary(report)["absolute"] == 32
    ref = resolve_field_result(report, "all", "net", 2)
    assert ref["value"] == "8.00"
    assert ref["unit"] == "W"
    assert ref["array_indices"] == [0, 1]


def test_orientation_reverses_signed_terms_without_changing_measure_or_source(tmp_path):
    path = tmp_path / "field.npz"
    np.savez(path, q=[10.0, -4.0], area=[2.0, 3.0])
    calc = declaration()
    calc["field_options"]["orientation"] = -1
    report = calculate_field_diagnostic(path, calc)
    result = summary(report)
    assert result["net"] == -8
    assert result["positive"] == 12
    assert result["negative"] == -20
    assert result["absolute"] == 32
    assert result["measure"] == 5
    assert report["field_options"]["orientation"] == -1
    assert "-1" in report["sign_convention"]
    with np.load(path, allow_pickle=False) as archive:
        assert archive["q"].tolist() == [10.0, -4.0]


@pytest.mark.parametrize("orientation", [0, 2, True, "-1"])
def test_orientation_accepts_only_explicit_numeric_sign(tmp_path, orientation):
    path = tmp_path / "field.npz"
    np.savez(path, q=[1.0], area=[1.0])
    calc = declaration()
    calc["field_options"]["orientation"] = orientation
    with pytest.raises(ValueError, match="orientation"):
        calculate_field_diagnostic(path, calc)


def test_orientation_cannot_invert_temperature(tmp_path):
    path = tmp_path / "field.npz"
    np.savez(path, temperature=[300.0], area=[1.0])
    calc = declaration(
        columns={"value": "temperature", "measure": "area"},
        units={"value": "K", "measure": "m2"},
        field_options={"association": "face", "integrand": "weighted_mean", "orientation": -1},
    )
    with pytest.raises(ValueError, match="temperature"):
        calculate_field_diagnostic(path, calc)


@pytest.mark.parametrize(
    "association,measure,unit", [("cell", "volume", "m3"), ("face", "area", "m2")]
)
def test_element_totals_never_multiply_measure_again(tmp_path, association, measure, unit):
    path = tmp_path / "field.npz"
    np.savez(path, power=[2.0, 7.0], measure=[100.0, 200.0])
    calc = declaration(
        columns={"value": "power", "measure": "measure"},
        units={"value": "W", "measure": unit},
        field_options={
            "association": association,
            "integrand": "element_total",
            "measure_kind": measure,
        },
    )
    assert summary(calculate_field_diagnostic(path, calc))["net"] == 9


def test_volume_density_uses_cell_volume(tmp_path):
    path = tmp_path / "field.npz"
    np.savez(path, q=[2.0, 3.0], volume=[4.0, 5.0])
    calc = declaration(
        columns={"value": "q", "measure": "volume"},
        units={"value": "W/m3", "measure": "m3"},
        field_options={"association": "cell", "integrand": "density", "measure_kind": "volume"},
    )
    assert summary(calculate_field_diagnostic(path, calc))["net"] == 23


def test_vector_flux_uses_dot_product_and_normal_reversal(tmp_path):
    path = tmp_path / "field.npz"
    np.savez(
        path,
        qx=[2.0, 2.0],
        qy=[3.0, 3.0],
        qz=[0.0, 0.0],
        ax=[1.0, -1.0],
        ay=[0.0, 0.0],
        az=[0.0, 0.0],
    )
    calc = declaration(
        columns={key: key for key in ("qx", "qy", "qz", "ax", "ay", "az")},
        units={"qx": "W/m2", "qy": "W/m2", "qz": "W/m2", "ax": "m2", "ay": "m2", "az": "m2"},
        field_options={"association": "face", "integrand": "vector_flux"},
    )
    result = summary(calculate_field_diagnostic(path, calc))
    assert result["net"] == 0
    assert result["positive"] == 2
    assert result["negative"] == -2
    calc["field_options"]["orientation"] = -1
    np.savez(
        path,
        qx=[2.0, 5.0],
        qy=[3.0, 3.0],
        qz=[0.0, 0.0],
        ax=[1.0, -1.0],
        ay=[0.0, 0.0],
        az=[0.0, 0.0],
    )
    reversed_result = summary(calculate_field_diagnostic(path, calc))
    assert reversed_result["net"] == 3
    assert reversed_result["positive"] == 5
    assert reversed_result["negative"] == -2
    assert reversed_result["measure"] == result["measure"]


def test_centroid_regions_report_assignment_and_partition_boundary(tmp_path):
    path = tmp_path / "field.npz"
    np.savez(path, q=[1.0, 2.0, 3.0], area=[2.0, 3.0, 4.0], x=[0.0, 1.0, 2.0])
    calc = declaration(
        columns={"value": "q", "measure": "area", "x": "x"},
        units={"value": "W/m2", "measure": "m2", "x": "m"},
        field_options={
            "association": "face",
            "integrand": "density",
            "region_assignment": "centroid",
            "regions": [
                {"id": "left", "bounds": {"x": [0, 1]}},
                {"id": "right", "bounds": {"x": [1, 3]}},
            ],
            "partition_complete": True,
        },
    )
    report = calculate_field_diagnostic(path, calc)
    assert summary(report, "left")["net"] == 2
    assert summary(report, "right")["net"] == 18
    assert report["region_assignment"] == "centroid-half-open"
    assert report["partition"]["complete"] is True
    assert summary(report)["net"] == 20


def test_partition_rejects_overlap_and_incomplete_coverage(tmp_path):
    path = tmp_path / "field.npz"
    np.savez(path, q=[1.0, 2.0], area=[1.0, 1.0], x=[0.0, 1.0])
    calc = declaration(
        columns={"value": "q", "measure": "area", "x": "x"},
        units={"value": "W/m2", "measure": "m2", "x": "m"},
    )
    calc["field_options"].update(
        region_assignment="centroid",
        partition_complete=True,
        regions=[{"id": "a", "bounds": {"x": [0, 0.5]}}],
    )
    with pytest.raises(ValueError, match="cover"):
        calculate_field_diagnostic(path, calc)
    calc["field_options"]["regions"] = [
        {"id": "a", "bounds": {"x": [0, 2]}},
        {"id": "b", "bounds": {"x": [0, 1]}},
    ]
    with pytest.raises(ValueError, match="overlap"):
        calculate_field_diagnostic(path, calc)


def test_missing_values_remain_unavailable_not_zero(tmp_path):
    path = tmp_path / "field.csv"
    path.write_text("q,area\n,1\n2,3\n", encoding="utf-8")
    report = calculate_field_diagnostic(path, declaration())
    assert report["groups"][0]["status"] == "missing"
    with pytest.raises(ValueError, match="unavailable"):
        resolve_field_result(report, "all", "net", 2)


def test_dimension_mismatch_is_not_silently_integrated(tmp_path):
    path = tmp_path / "field.npz"
    np.savez(path, q=[1.0], area=[1.0])
    with pytest.raises(ValueError, match="unit"):
        calculate_field_diagnostic(path, declaration(units={"value": "W/m3", "measure": "m2"}))
    with pytest.raises(ValueError, match="association"):
        calculate_field_diagnostic(
            path,
            declaration(
                field_options={
                    "association": "face",
                    "integrand": "density",
                    "measure_kind": "volume",
                },
                units={"value": "W/m3", "measure": "m3"},
            ),
        )


def test_clipped_fraction_temperature_regions_use_actual_fraction_and_area(tmp_path):
    path = tmp_path / "field.npz"
    np.savez(path, temperature=[300.0, 320.0], area=[1.0, 3.0], fraction=[1.0, 0.25])
    calc = declaration(
        columns={"value": "temperature", "measure": "area"},
        units={"value": "K", "measure": "m2"},
        field_options={
            "association": "face",
            "integrand": "weighted_mean",
            "regions": [
                {"id": "hot", "fraction": "fraction"},
                {"id": "rest", "fraction": "fraction", "complement": True},
            ],
            "partition_complete": True,
        },
    )
    report = calculate_field_diagnostic(path, calc)
    assert summary(report, "hot")["measure"] == 1.75
    assert summary(report, "hot")["weighted_mean"] == pytest.approx(540 / 1.75)
    assert summary(report, "rest")["weighted_mean"] == 320
    assert report["result_units"]["net"] == "K·m2"
    assert report["result_units"]["weighted_mean"] == "K"
    with pytest.raises(ValueError, match="Percentage"):
        resolve_field_result(report, "all", "weighted_mean", 2, True)


def test_duplicate_comparison_geometry_cannot_duplicate_reference_elements(tmp_path):
    path = tmp_path / "new.npz"
    reference = tmp_path / "old.npz"
    np.savez(path, t=[320.0, 300.0], x=[0.0, 0.0], y=[0.0, 0.0], z=[0.0, 0.0])
    np.savez(reference, t=[290.0, 310.0], x=[0.0, 1.0], y=[0.0, 0.0], z=[0.0, 0.0])
    calc = declaration(
        operation="field_difference",
        columns={"value": "t", "x": "x", "y": "y", "z": "z"},
        units={"value": "K", "x": "m", "y": "m", "z": "m"},
        field_options={"association": "point", "reference_source": "old.npz"},
    )
    with pytest.raises(ValueError, match="unique|ambiguous|one-to-one"):
        calculate_field_diagnostic(path, calc)


def test_difference_matches_spatial_identity_even_when_source_order_differs(tmp_path):
    path = tmp_path / "new.npz"
    reference = tmp_path / "old.npz"
    np.savez(
        path,
        t=[320.0, 300.0],
        area=[3.0, 1.0],
        x=[1.0, 0.0],
        y=[0.0, 0.0],
        z=[0.0, 0.0],
        id=["b", "a"],
    )
    np.savez(
        reference,
        t=[290.0, 310.0],
        area=[1.0, 3.0],
        x=[0.0, 1.0],
        y=[0.0, 0.0],
        z=[0.0, 0.0],
        id=["a", "b"],
    )
    calc = declaration(
        operation="field_difference",
        columns={"value": "t", "measure": "area", "x": "x", "y": "y", "z": "z", "element_id": "id"},
        units={"value": "K", "measure": "m2", "x": "m", "y": "m", "z": "m"},
        field_options={"association": "face", "reference_source": "old.npz"},
    )
    report = calculate_field_diagnostic(path, calc)
    assert summary(report)["weighted_mean"] == 10
    assert summary(report)["minimum"] == 10
    assert report["groups"][0]["reference_array_indices"] == [1, 0]
    assert report["elements"][0]["difference"] == 10


def test_difference_rejects_equal_length_different_geometry(tmp_path):
    path = tmp_path / "field.npz"
    np.savez(path, t=[300.0], old=[290.0], x=[0.0], y=[0.0], z=[0.0], rx=[1.0], ry=[0.0], rz=[0.0])
    calc = declaration(
        operation="field_difference",
        columns={
            "comparison": "t",
            "reference": "old",
            "x": "x",
            "y": "y",
            "z": "z",
            "reference_x": "rx",
            "reference_y": "ry",
            "reference_z": "rz",
        },
        units={
            "comparison": "K",
            "reference": "K",
            "x": "m",
            "y": "m",
            "z": "m",
            "reference_x": "m",
            "reference_y": "m",
            "reference_z": "m",
        },
        field_options={"association": "point"},
    )
    with pytest.raises(ValueError, match="geometry|geometr"):
        calculate_field_diagnostic(path, calc)


def test_energy_budget_keeps_storage_and_residual_definition(tmp_path):
    path = tmp_path / "budget.csv"
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["incoming", "outgoing", "source", "storage"])
        writer.writerow([100, 70, 5, 30])
    calc = declaration(
        operation="energy_budget",
        columns={
            "input": "incoming",
            "output": "outgoing",
            "source": "source",
            "storage": "storage",
        },
        units=dict.fromkeys(["input", "output", "source", "storage"], "W"),
        field_options={"association": "control_volume"},
    )
    report = calculate_field_diagnostic(path, calc)
    assert summary(report)["residual"] == 5
    assert summary(report)["relative_residual"] == pytest.approx(5 / 105)
    assert report["evidence_role"] == "same-solution-budget"
    assert report["groups"][0]["csv_records"] == [2]
    assert resolve_field_result(report, "all", "relative_residual", 2, True)["value"] == "4.76"


def test_budget_requires_storage_or_explicit_steady_state(tmp_path):
    path = tmp_path / "budget.csv"
    path.write_text("incoming,outgoing,source\n100,100,0\n", encoding="utf-8")
    calc = declaration(
        operation="energy_budget",
        columns={"input": "incoming", "output": "outgoing", "source": "source"},
        units=dict.fromkeys(["input", "output", "source"], "W"),
        field_options={"association": "control_volume"},
    )
    with pytest.raises(ValueError, match="storage|steady"):
        calculate_field_diagnostic(path, calc)
    calc["field_options"]["steady_state"] = True
    assert summary(calculate_field_diagnostic(path, calc))["residual"] == 0


def test_equal_face_centers_and_areas_do_not_hide_polygon_change(tmp_path):
    path = tmp_path / "new.npz"
    reference = tmp_path / "old.npz"
    common = dict(
        t=[300.0], area=[1.0], x=[0.0], y=[0.0], z=[0.0], faces=[4, 0, 1, 2, 3], starts=[0]
    )
    np.savez(
        path, **common, vertices=[[-0.5, -0.5, 0], [0.5, -0.5, 0], [0.5, 0.5, 0], [-0.5, 0.5, 0]]
    )
    np.savez(
        reference, **common, vertices=[[-1, -0.25, 0], [1, -0.25, 0], [1, 0.25, 0], [-1, 0.25, 0]]
    )
    calc = declaration(
        operation="field_difference",
        columns={"value": "t", "measure": "area", "x": "x", "y": "y", "z": "z"},
        units={"value": "K", "measure": "m2", "x": "m", "y": "m", "z": "m"},
        field_options={
            "association": "face",
            "reference_source": "old.npz",
            "polygon_geometry": {
                "vertices": "vertices",
                "connectivity": "faces",
                "starts": "starts",
            },
        },
    )
    with pytest.raises(ValueError, match="polygon"):
        calculate_field_diagnostic(path, calc)


def test_original_npz_component_selector_preserves_face_locations(tmp_path):
    path = tmp_path / "field.npz"
    np.savez(path, q=[2.0, 3.0], area=[1.0, 2.0], centroid_m=[[0.0, 1.0, 0.0], [2.0, 1.0, 0.0]])
    calc = declaration(
        columns={"value": "q", "measure": "area", "x": "centroid_m[0]"},
        units={"value": "W/m2", "measure": "m2", "x": "m"},
        field_options={
            "association": "face",
            "integrand": "density",
            "region_assignment": "centroid",
            "regions": [{"id": "left", "bounds": {"x": [-1, 1]}}],
        },
    )
    report = calculate_field_diagnostic(path, calc)
    assert summary(report, "left")["net"] == 2
    assert report["groups"][1]["array_indices"] == [0]


def test_polygon_clip_recomputes_true_partial_face_fraction_from_current_geometry(tmp_path):
    path = tmp_path / "field.npz"

    def save(width):
        np.savez(
            path,
            face_value=[10.0],
            area_m2=[width],
            vertices_m=[[0.0, 0.0, 0.0], [width, 0.0, 0.0], [width, 1.0, 0.0], [0.0, 1.0, 0.0]],
            faces_connectivity=[4, 0, 1, 2, 3],
            face_starts=[0],
        )

    save(1.0)
    bounds = {"x": [0.0, 0.5], "y": [0.0, 1.0]}
    calc = declaration(
        columns={"value": "face_value", "measure": "area_m2"},
        units={"value": "W/m2", "measure": "m2"},
        field_options={
            "association": "face",
            "integrand": "density",
            "region_assignment": "polygon-clip",
            "regions": [
                {"id": "hot", "bounds": bounds},
                {"id": "rest", "bounds": bounds, "complement": True},
            ],
            "partition_complete": True,
        },
    )
    first = calculate_field_diagnostic(path, calc)
    assert summary(first, "hot")["net"] == 5
    assert summary(first, "rest")["net"] == 5
    assert first["region_assignment"] == "polygon-clip"
    save(2.0)
    updated = calculate_field_diagnostic(path, calc)
    assert summary(updated, "hot")["net"] == 5
    assert summary(updated, "rest")["net"] == 15
    assert updated["partition"]["verification"] == "original-polygon-overlap-and-union"
    calc["field_options"]["regions"][1].pop("complement")
    # The same left region repeated covers half the face twice. Scalar
    # fractions still add to one at width=1, but geometry is not a partition.
    save(1.0)
    with pytest.raises(ValueError, match="overlap"):
        calculate_field_diagnostic(path, calc)


def test_signed_totals_keep_internal_cancellation_and_original_filtered_records(tmp_path):
    path = tmp_path / "paths.csv"
    path.write_text(
        "geometry,positive,negative,area\nA,10,-7,2\nB,999,-1,4\nB,2,-1,5\nA,6,-8,3\n",
        encoding="utf-8",
    )
    calc = declaration(
        columns={"positive": "positive", "negative": "negative", "measure": "area"},
        units={"positive": "W", "negative": "W", "measure": "m2"},
        field_options={
            "association": "integrated_region",
            "integrand": "signed_totals",
            "row_filters": {"geometry": "A"},
        },
    )
    report = calculate_field_diagnostic(path, calc)
    result = summary(report)
    assert result["net"] == 1
    assert result["positive"] == 16
    assert result["negative"] == -15
    assert result["absolute"] == 31
    assert result["measure"] == 5
    assert report["groups"][0]["csv_records"] == [2, 5]
    calc["field_options"]["orientation"] = -1
    reverse = summary(calculate_field_diagnostic(path, calc))
    assert reverse["positive"] == 15
    assert reverse["negative"] == -16
    assert reverse["net"] == -1


@pytest.mark.parametrize("positive,negative", [("", "-2"), ("2", "")])
def test_signed_totals_missing_components_remain_missing(tmp_path, positive, negative):
    path = tmp_path / "paths.csv"
    path.write_text(f"positive,negative\n{positive},{negative}\n", encoding="utf-8")
    calc = declaration(
        columns={"positive": "positive", "negative": "negative"},
        units={"positive": "W", "negative": "W"},
        field_options={"association": "integrated_region", "integrand": "signed_totals"},
    )
    report = calculate_field_diagnostic(path, calc)
    assert report["groups"][0]["status"] == "missing"


@pytest.mark.parametrize("positive,negative", [(-1, -2), (1, 2)])
def test_signed_totals_validate_reported_positive_negative_conventions(
    tmp_path, positive, negative
):
    path = tmp_path / "paths.csv"
    path.write_text(f"positive,negative\n{positive},{negative}\n", encoding="utf-8")
    calc = declaration(
        columns={"positive": "positive", "negative": "negative"},
        units={"positive": "W", "negative": "W"},
        field_options={"association": "integrated_region", "integrand": "signed_totals"},
    )
    with pytest.raises(ValueError, match="positive|negative"):
        calculate_field_diagnostic(path, calc)
