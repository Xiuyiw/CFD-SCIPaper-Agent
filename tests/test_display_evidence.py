import json
from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pytest

from cfdpaper.publication.display_evidence import review_display_evidence, shared_reference_scale


def read(root, records):
    (root / "display-evidence.json").write_text(json.dumps(records), encoding="utf-8")
    data = SimpleNamespace(figures=[SimpleNamespace(id="F")])
    return review_display_evidence(root, data, {"captions": {"F": "Original panels"}})


@pytest.fixture
def p(tmp_path):
    np.savez(tmp_path / "faces.npz", temp=[1.0, 3.0, 7.0])
    return {
        "figure_id": "F",
        "panel": "a",
        "source": "faces.npz",
        "source_kind": "native-field",
        "operations": ["node-interpolation"],
        "use": "visual-reading",
        "quantity": "temperature",
        "unit": "K",
        "comparison_group": "wall",
        "values": "temp",
        "scale": {
            "knots": [1.0, 4.0, 7.0],
            "positions": [0.0, 0.5, 1.0],
            "colors": ["white", "blue", "black"],
            "clipping": "forbid",
        },
    }


def test_absent_optional_file(tmp_path):
    assert review_display_evidence(tmp_path, None, None) == []


def test_reference_weighted_knots_use_all_case_extrema_and_preserve_values():
    ref = [0, 3, 6, 9]
    weights = [1, 7, 1, 1]
    kw = dict(fractions=[0.5], positions=[0, 0.68, 1], colors=["navy", "white", "maroon"])
    scale = shared_reference_scale(ref, weights, [ref, [2, 5, 12]], **kw)
    assert scale["knots"] == [0, 3, 12] and scale["positions"] == [0, 0.68, 1]
    assert ref == [0, 3, 6, 9]
    with pytest.raises(ValueError, match="clips"):
        shared_reference_scale(ref, weights, [ref], lower=1, **kw)
    with pytest.raises(ValueError, match="aligned"):
        shared_reference_scale(ref, [1, 0, 1, 1], [ref], **kw)
    with pytest.raises(ValueError, match="increase"):
        shared_reference_scale([3, 3], [2, 1], [[3, 3]], **kw)


def test_common_mapping_and_actual_range(tmp_path, p):
    other = deepcopy(p)
    other["panel"] = "b"
    got = read(tmp_path, [p, other])
    assert got[1]["source_range"] == [1, 7] and got[1]["outside_scale"] == 0
    other["scale"]["knots"][1] = 5
    with pytest.raises(ValueError, match="mapping"):
        read(tmp_path, [p, other])
    p["scale"]["knots"][-1] = 6.0
    with pytest.raises(ValueError, match="outside"):
        read(tmp_path, [p])
    p["scale"]["clipping"] = "show-ends"
    assert read(tmp_path, [p])[0]["outside_scale"] == 1


@pytest.mark.parametrize(
    "op", ["node-interpolation", "smoothing", "gap-compression", "raster-cache"]
)
def test_never_upgrade_displayed_data(tmp_path, p, op):
    p.update(operations=[op], use="quantitative-reading")
    with pytest.raises(ValueError, match="unmodified"):
        read(tmp_path, [p])


def test_separate_statistics_owned_by_source_not_cached_image(tmp_path, p):
    (tmp_path / "raster.png").write_bytes(b"nonempty local artifact")
    cache = {
        "figure_id": "F",
        "panel": "map",
        "source": "raster.png",
        "source_kind": "cached-image",
        "use": "visual-reading",
    }
    p.update(operations=[], use="quantitative-reading")
    assert read(tmp_path, [cache, p])[1]["samples"] == 3
    p["use"] = "validation-comparison"
    with pytest.raises(ValueError, match="independent"):
        read(tmp_path, [p])


def test_unit_conversion_checks_displayed_series_and_common_scale(tmp_path, p):
    p.update(
        source="temperature.csv",
        values="K",
        source_kind="reduced-table",
        operations=["unit-conversion"],
        source_unit="K",
        temperature_kind="absolute",
        unit="degC",
        use="quantitative-reading",
        displayed={"source": "temperature.csv", "values": "degC"},
    )
    (tmp_path / "temperature.csv").write_text(
        "K,degC\n274.15,1\n276.15,3\n280.15,7\n", encoding="utf8"
    )
    assert read(tmp_path, [p])[0]["source_range"] == [1.0, 7.0]
    (tmp_path / "temperature.csv").write_text("K,degC\n274.15,274.15\n", encoding="utf8")
    with pytest.raises(ValueError, match="do not reproduce"):
        read(tmp_path, [p])
    p["temperature_kind"] = "difference"
    with pytest.raises(ValueError, match="absolute"):
        read(tmp_path, [p])


def test_observations_and_predictions_require_matching_inputs(tmp_path):
    (tmp_path / "obs.csv").write_text("z,value\n1,11\n2,14\n", encoding="utf8")
    (tmp_path / "prediction.csv").write_text("z,T\n1,12\n2,13.5\n", encoding="utf8")
    common = {"quantity": "temperature", "unit": "K", "support": "Two supplied samples on line A"}
    r = {
        "figure_id": "F",
        "panel": "compare",
        "source": "obs.csv",
        "source_kind": "measurement",
        "use": "validation-comparison",
        "values": "value",
        "coordinates": "z",
        "prediction": {"source": "prediction.csv", "values": "T", "coordinates": "z", **common},
        **common,
    }
    assert "not validation proof" in read(tmp_path, [r])[0]["qualification"]
    (tmp_path / "prediction.csv").write_text("z,T\n1,12\n3,13.5\n", encoding="utf8")
    with pytest.raises(ValueError, match="coordinates"):
        read(tmp_path, [r])
    r["prediction"]["source"] = "obs.csv"
    with pytest.raises(ValueError, match="distinct"):
        read(tmp_path, [r])
