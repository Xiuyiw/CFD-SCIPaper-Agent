"""Area-based temperature composition, not independent transport evidence."""

from copy import deepcopy

import numpy as np
import pytest

from cfdpaper.publication.field_diagnostics import calculate_field_diagnostic
from cfdpaper.publication.table_evidence import calculate_declared_table, resolve_table_result


def surface(path, values, widths=(1.0, 3.0), *, z=0.0, areas=None):
    vertices, connectivity, starts = [], [], []
    x = 0.0
    for width in widths:
        start = len(vertices)
        vertices.extend([[x, 0, z], [x + width, 0, z], [x + width, 1, z], [x, 1, z]])
        starts.append(len(connectivity))
        connectivity.extend([4, start, start + 1, start + 2, start + 3])
        x += width
    np.savez(
        path,
        vertices_m=np.array(vertices),
        faces_connectivity=np.array(connectivity),
        face_starts=np.array(starts),
        area=np.array(widths if areas is None else areas),
        temperature=np.array(values),
    )


def declaration(**options):
    box = {"x": [0, 1], "y": [0, 1]}
    return {
        "id": "regional-change",
        "operation": "partition_change",
        "source": "comparison.npz",
        "domain": "same physical wall",
        "quantity_kind": "absolute-temperature",
        "columns": {"value": "temperature", "measure": "area"},
        "units": {"value": "K", "measure": "m2"},
        "field_options": {
            "association": "face",
            "integrand": "weighted_mean",
            "region_assignment": "polygon-clip",
            "partition_complete": True,
            "regions": [
                {"id": "hot", "bounds": box},
                {"id": "rest", "bounds": box, "complement": True},
            ],
            "reference_source": "reference.npz",
            "support_mode": "fixed",
            "common_support": "complete 4 by 1 m wall at z=0; same saved steady support",
            **options,
        },
    }


def group(report, name="all"):
    return next(item for item in report["groups"] if item["group"] == name)


def test_unequal_physical_areas_account_for_opposing_regional_changes(tmp_path):
    surface(tmp_path / "reference.npz", [320.0, 300.0])
    surface(tmp_path / "comparison.npz", [316.0, 302.0])
    report = calculate_declared_table(tmp_path / "comparison.npz", declaration())
    assert group(report)["result"]["reference_mean"] == 305
    assert group(report)["result"]["comparison_mean"] == 305.5
    assert group(report, "hot")["result"]["reference_weight"] == 0.25
    assert group(report, "rest")["result"]["comparison_weight"] == 0.75
    assert group(report, "hot")["result"]["contribution"] == -1
    assert group(report, "rest")["result"]["contribution"] == 1.5
    assert group(report)["result"]["difference_mean"] == 0.5
    assert report["contribution_sum"] == 0.5
    assert report["closure_error"] == pytest.approx(0, abs=1e-12)
    result = resolve_table_result(
        [report], calculation_id="regional-change", group="hot", field="contribution", places=3
    )
    assert result["unit"] == "K"
    assert result["value"] == "-1.000"
    assert result["array_indices"] == [0]
    assert result["reference_array_indices"] == [0]
    assert report["evidence_role"] == "same-solution-temperature-composition"


def test_common_wall_allows_different_original_meshes_without_point_subtraction(tmp_path):
    surface(tmp_path / "reference.npz", [320.0, 300.0])
    surface(tmp_path / "comparison.npz", [316.0, 302.0, 302.0], widths=(1.0, 1.0, 2.0))
    report = calculate_field_diagnostic(tmp_path / "comparison.npz", declaration())
    assert group(report)["result"]["difference_mean"] == 0.5
    assert group(report, "rest")["array_indices"] == [1, 2]
    assert group(report, "rest")["reference_array_indices"] == [1]


def test_moving_support_has_its_own_reference_region_and_semantics(tmp_path):
    surface(tmp_path / "reference.npz", [320, 300, 300, 300], widths=(1, 1, 1, 1))
    surface(tmp_path / "comparison.npz", [302, 302, 302, 318], widths=(1, 1, 1, 1))
    calc = declaration(support_mode="moving")
    calc["field_options"]["reference_regions"] = deepcopy(calc["field_options"]["regions"])
    for region in calc["field_options"]["regions"]:
        region["bounds"]["x"] = [3, 4]
    report = calculate_field_diagnostic(tmp_path / "comparison.npz", calc)
    assert group(report, "hot")["result"]["difference_mean"] == -2
    assert group(report, "hot")["result"]["contribution"] == -0.5
    assert group(report, "rest")["result"]["contribution"] == 1.5
    assert report["support_mode"] == "moving"
    assert "same physical location" in report["interpretation"]
    assert group(report, "hot")["array_indices"] == [3]
    assert group(report, "hot")["reference_array_indices"] == [0]


def test_fixed_support_cannot_silently_change_region_location(tmp_path):
    surface(tmp_path / "reference.npz", [320, 300])
    surface(tmp_path / "comparison.npz", [316, 302])
    calc = declaration()
    calc["field_options"]["reference_regions"] = deepcopy(calc["field_options"]["regions"])
    calc["field_options"]["reference_regions"][0]["bounds"]["x"] = [1, 2]
    with pytest.raises(ValueError, match="fixed.*region"):
        calculate_field_diagnostic(tmp_path / "comparison.npz", calc)


@pytest.mark.parametrize("fault", ["overlap", "missing", "empty", "weights"])
def test_invalid_partition_or_changing_area_weights_is_rejected(tmp_path, fault):
    surface(tmp_path / "reference.npz", [320, 300])
    surface(tmp_path / "comparison.npz", [316, 302])
    calc = declaration()
    regions = calc["field_options"]["regions"]
    if fault == "overlap":
        regions[1].pop("complement")
        pattern = "overlap"
    elif fault == "missing":
        calc["field_options"]["regions"] = regions[:1]
        pattern = "cover"
    elif fault == "empty":
        for region in regions:
            region["bounds"]["x"] = [5, 6]
        pattern = "empty"
    else:
        calc["field_options"]["support_mode"] = "moving"
        calc["field_options"]["reference_regions"] = deepcopy(regions)
        for region in regions:
            region["bounds"]["x"] = [0, 2]
        pattern = "weights"
    with pytest.raises(ValueError, match=pattern):
        calculate_field_diagnostic(tmp_path / "comparison.npz", calc)


@pytest.mark.parametrize("fault", ["domain", "plane", "missing-temperature"])
def test_same_area_does_not_prove_same_domain_and_missing_values_stay_unavailable(tmp_path, fault):
    surface(tmp_path / "reference.npz", [320, 300])
    surface(
        tmp_path / "comparison.npz",
        [float("nan"), 302] if fault == "missing-temperature" else [316, 302],
        widths=(2, 2) if fault == "domain" else (1, 3),
        z=1 if fault == "plane" else 0,
    )
    calc = declaration()
    if fault == "domain":
        # Shifted support has the same area but is not the same wall.
        with np.load(tmp_path / "comparison.npz") as data:
            values = {key: data[key] for key in data.files}
        values["vertices_m"][:, 0] += 1
        np.savez(tmp_path / "comparison.npz", **values)
    with pytest.raises(ValueError, match="support|plane|Nonfinite"):
        calculate_field_diagnostic(tmp_path / "comparison.npz", calc)


@pytest.mark.parametrize("unit", ["degC", "K"])
def test_temperature_origin_does_not_change_contribution_unit(tmp_path, unit):
    surface(tmp_path / "reference.npz", [20, 0])
    surface(tmp_path / "comparison.npz", [16, 2])
    calc = declaration()
    calc["units"]["value"] = unit
    report = calculate_field_diagnostic(tmp_path / "comparison.npz", calc)
    assert report["result_units"]["reference_mean"] == unit
    assert report["result_units"]["difference_mean"] == "K"
    assert report["result_units"]["contribution"] == "K"


@pytest.mark.parametrize(
    "patch,pattern",
    [
        ({"common_support": ""}, "common_support"),
        ({"support_mode": "arbitrary"}, "support_mode"),
        ({"partition_complete": False}, "complete"),
        ({"association": "point"}, "face"),
    ],
)
def test_required_physical_definitions(tmp_path, patch, pattern):
    surface(tmp_path / "reference.npz", [320, 300])
    surface(tmp_path / "comparison.npz", [316, 302])
    with pytest.raises(ValueError, match=pattern):
        calculate_field_diagnostic(tmp_path / "comparison.npz", declaration(**patch))
