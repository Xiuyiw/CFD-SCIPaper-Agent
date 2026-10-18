from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from cfdpaper.adapters import ExtractionRequest, FluentAdapter
from cfdpaper.adapters.fluent_backend import export_fluent_surfaces


class FakeSession:
    def __init__(self):
        self.reads = []
        self.closed = False
        self.report_calls = []
        self.clips = []
        self.tui = SimpleNamespace(
            surface=SimpleNamespace(iso_clip=lambda *args: self.clips.append(args))
        )
        self.transcript = SimpleNamespace(start=self.start_transcript, stop=lambda: None)
        self.file = SimpleNamespace(read=lambda **kw: self.reads.append(kw))
        self.field_info = SimpleNamespace(
            get_surfaces_info=lambda: {"interface": {"surface_id": [7], "zone_id": 12}},
            get_scalar_fields_info=lambda: {"temperature": {}, "heat-flux": {}},
        )
        self.field_data = SimpleNamespace(new_transaction=lambda: self)
        self.results = SimpleNamespace(report=SimpleNamespace(surface_integrals=self.report))

    def get_fluent_version(self):
        return "23.1.0"

    def report(self, **kw):
        self.report_calls.append(kw)
        values = {"area": 1.0, "integral": -25.0, "area-weighted-avg": 350.0}
        target = Path(kw["file_name"]) if kw["write_to_file"] else self.transcript_path
        with target.open("a") as stream:
            stream.write(f"{kw['surface_id'][0]} {values[kw['report_type']]}\n")

    def start_transcript(self, **kw):
        assert [item["file_type"] for item in self.reads] == ["case", "data"]
        self.transcript_path = Path(kw["file_name"])
        self.transcript_path.write_text("")

    def add_surfaces_request(self, **kw):
        pass

    def add_scalar_fields_request(self, **kw):
        pass

    def get_fields(self):
        return {
            "geometry": {
                7: {
                    "vertices": np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]]),
                    "faces": np.array([4, 0, 1, 2, 3]),
                    "centroid": np.array([[0.5, 0.5, 0]]),
                    "face-normal": np.array([[0, 0, 1]]),
                }
            },
            "fields": {7: {"temperature": np.array([350.0]), "heat-flux": np.array([-25.0])}},
        }

    def exit(self):
        self.closed = True


def request(tmp_path, **options):
    case = tmp_path / "model.cas.h5"
    data = tmp_path / "model.dat.h5"
    case.write_bytes(b"case")
    data.write_bytes(b"data")
    return ExtractionRequest(
        case,
        ("temperature", "heat-flux"),
        {
            "data_file": data,
            "output_dir": tmp_path / "export",
            "surfaces": {"wall": "interface"},
            **options,
        },
    )


def test_native_extract_preserves_faces_and_native_reports(tmp_path):
    import json

    session = FakeSession()
    req = request(tmp_path)
    adapter = FluentAdapter(session_factory=lambda **kw: session)
    records = adapter.extract(req)
    assert session.closed
    assert all(not call["write_to_file"] for call in session.report_calls)
    assert [r["file_type"] for r in session.reads] == ["case", "data"]
    assert records[0].values["heat_flow"] == -25
    assert records[0].units["heat_flow"] == "W"
    assert records[0].values["temperature_area_mean"] == 350
    manifest = json.loads((tmp_path / "export" / "manifest.json").read_text())
    face = manifest["surfaces"][0]
    with np.load(tmp_path / "export" / face["path"]) as arrays:
        assert arrays["face_area"].tolist() == [1.0]
        assert arrays["heat_flux"].tolist() == [-25.0]
        assert arrays["faces"].tolist() == [4, 0, 1, 2, 3]
        assert arrays["face_area_m2"].tolist() == [1.0]
        assert arrays["centroid_x_m"].tolist() == [0.5]
    assert face["association"] == "face"
    assert face["node_value"] is False
    assert manifest["iterations_performed"] == 0
    assert req.source.read_bytes() == b"case"


def test_missing_zone_closes_session_without_manufactured_values(tmp_path):
    session = FakeSession()
    with pytest.raises(ValueError, match="missing.*surface"):
        export_fluent_surfaces(
            request(tmp_path, surfaces={"unknown": "absent"}), session_factory=lambda **kw: session
        )
    assert session.closed
    assert not (tmp_path / "export" / "manifest.json").exists()


def test_unknown_units_fail_before_launch(tmp_path):
    req = request(tmp_path)
    req = ExtractionRequest(req.source, ("unfamiliar",), req.options)
    with pytest.raises(ValueError, match="unit"):
        export_fluent_surfaces(req, session_factory=lambda **kw: pytest.fail("must not launch"))


def test_existing_output_is_not_overwritten(tmp_path):
    req = request(tmp_path)
    out = tmp_path / "export"
    out.mkdir()
    (out / "manifest.json").write_text("author material")
    with pytest.raises(FileExistsError):
        export_fluent_surfaces(req, session_factory=lambda **kw: pytest.fail("must not launch"))
    assert (out / "manifest.json").read_text() == "author material"


def test_output_must_not_be_the_native_source_directory(tmp_path):
    req = request(tmp_path, output_dir=tmp_path)
    with pytest.raises(ValueError, match="source directory"):
        export_fluent_surfaces(req, session_factory=lambda **kw: pytest.fail("must not launch"))


def test_native_si_units_cannot_be_relabelled(tmp_path):
    req = request(tmp_path, field_units={"heat-flux": "W/mm^2"})
    with pytest.raises(ValueError, match="SI field definition"):
        export_fluent_surfaces(req, session_factory=lambda **kw: pytest.fail("must not launch"))


def test_solver_alias_cannot_select_different_results(tmp_path):
    other = tmp_path / "different.cas.h5"
    other.write_bytes(b"other")
    req = request(tmp_path, solver_case_file=other)
    with pytest.raises(ValueError, match="same CASE/DATA"):
        export_fluent_surfaces(req, session_factory=lambda **kw: pytest.fail("must not launch"))


def test_failed_field_extraction_closes_session(tmp_path):
    session = FakeSession()
    session.get_fields = lambda: {"fields": {7: {"temperature": np.array([float("nan")])}}}
    with pytest.raises(KeyError):
        export_fluent_surfaces(request(tmp_path), session_factory=lambda **kw: session)
    assert session.closed
    assert not (tmp_path / "export" / "manifest.json").exists()


def test_native_regions_use_coordinate_clips_and_can_skip_large_field_export(tmp_path):
    import json

    session = FakeSession()
    session.field_data = SimpleNamespace(new_transaction=lambda: pytest.fail("no NPZ requested"))
    req = request(
        tmp_path,
        export_fields=False,
        region_bounds={"hot": {"axes": {"x": [0.0, 0.5], "y": [0.0, 0.5]}}},
    )
    path = export_fluent_surfaces(req, session_factory=lambda **kw: session)
    content = json.loads(path.read_text(encoding="utf-8"))
    assert [clip[0] for clip in session.clips] == ["x-coordinate", "y-coordinate"]
    assert session.clips[1][2] == session.clips[0][1]
    assert content["surfaces"][0]["regions"]["hot"]["native_reports"]["heat_flow_W"] == -25
    assert not list((tmp_path / "export").glob("*.npz"))
    assert session.closed


def test_invalid_region_bounds_are_rejected_before_launch(tmp_path):
    req = request(tmp_path, region_bounds={"bad": {"axes": {"x": [1.0, -1.0]}}})
    with pytest.raises(ValueError, match="increasing"):
        export_fluent_surfaces(req, session_factory=lambda **kw: pytest.fail("must not launch"))
