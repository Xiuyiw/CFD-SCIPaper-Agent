from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from cfdpaper.adapters import (
    CSVAdapter,
    ExtractionRequest,
    FluentAdapter,
    Inventory,
    SourceChangedError,
    StarCCMAdapter,
    UnsupportedExtractionError,
    VTKAdapter,
)
from cfdpaper.adapters.vtk import _shallow_variable_scan

FIXTURES = Path(__file__).parent / "fixtures" / "synthetic"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_csv_extract_preserves_missing_rows_units_locators_and_source() -> None:
    source = FIXTURES / "screening.csv"
    before = _sha256(source)

    adapter = CSVAdapter()
    probe = adapter.probe(source)
    inventory = adapter.inventory(source)
    records = adapter.extract(ExtractionRequest(source=source))

    assert probe.supported and probe.available
    assert inventory.variables == ("case", "temperature", "pressure_drop")
    assert inventory.units == {"case": None, "temperature": "K", "pressure_drop": "Pa"}
    assert inventory.row_count == 2
    assert records[1].values["temperature"] is None
    assert records[1].locator == "row:3"
    assert records[1].source_uri == source.resolve().as_uri()
    assert records[1].source_hash == before
    assert _sha256(source) == before


def test_csv_extract_can_select_variables_without_losing_missing_values(tmp_path: Path) -> None:
    source = tmp_path / "qoi.csv"
    source.write_text("case,CO [ppm]\nA,\n", encoding="utf-8")

    records = CSVAdapter().extract(ExtractionRequest(source=source, variables=("case", "CO")))

    assert records[0].values == {"case": "A", "CO": None}
    assert records[0].units == {"case": None, "CO": "ppm"}


def test_csv_extract_rejects_unknown_variable(tmp_path: Path) -> None:
    source = tmp_path / "qoi.csv"
    source.write_text("case,value [Pa]\nA,1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="unknown CSV variables.*missing"):
        CSVAdapter().extract(ExtractionRequest(source=source, variables=("missing",)))


@pytest.mark.parametrize("row", ["A", "A,1,unexpected"])
@pytest.mark.parametrize("operation", ["inventory", "extract"])
def test_csv_rejects_rows_with_wrong_column_count(tmp_path: Path, row: str, operation: str) -> None:
    source = tmp_path / "malformed.csv"
    source.write_text(f"case,value [Pa]\n{row}\n", encoding="utf-8")
    adapter = CSVAdapter()

    with pytest.raises(ValueError, match="CSV row 2 has .* columns; expected 2"):
        if operation == "inventory":
            adapter.inventory(source)
        else:
            adapter.extract(ExtractionRequest(source=source))


def test_vtk_probe_and_inventory_explain_minimum_manual_export_without_meshio() -> None:
    source = FIXTURES / "field.vtk"
    adapter = VTKAdapter(meshio_loader=lambda: None)

    probe = adapter.probe(source)
    inventory = adapter.inventory(source)

    assert probe.supported
    assert not probe.available
    assert inventory.variables == ("temperature",)
    assert inventory.status == "missing-dependency"
    assert "CSV" in inventory.recommendation
    assert "coordinates" in inventory.recommendation
    assert "units" in inventory.recommendation


class _FakeArray:
    def __init__(self, values: list) -> None:
        self._values = values

    def tolist(self) -> list:
        return self._values


class _FakeMeshIO:
    def __init__(
        self,
        *,
        point_data: dict | None = None,
        cell_data: dict | None = None,
        on_read: object | None = None,
    ) -> None:
        class Mesh:
            points = [(0.0, 0.0, 0.0)]
            cells = []

        self.mesh = Mesh()
        self.mesh.point_data = point_data or {}
        self.mesh.cell_data = cell_data or {}
        self.on_read = on_read

    def read(self, source: Path) -> object:
        if callable(self.on_read):
            self.on_read(source)
        return self.mesh


def test_vtk_extract_rejects_vector_data_instead_of_stringifying(tmp_path: Path) -> None:
    source = tmp_path / "vector.vtu"
    source.write_text("synthetic", encoding="ascii")
    meshio = _FakeMeshIO(point_data={"velocity": _FakeArray([[1.0, 2.0, 3.0]])})

    with pytest.raises(UnsupportedExtractionError, match="vector.*component-wise"):
        VTKAdapter(meshio_loader=lambda: meshio).extract(ExtractionRequest(source=source))


def test_vtk_extract_rejects_cell_data_instead_of_stringifying(tmp_path: Path) -> None:
    source = tmp_path / "cell.vtu"
    source.write_text("synthetic", encoding="ascii")
    meshio = _FakeMeshIO(cell_data={"temperature": [_FakeArray([1200.0])]})

    with pytest.raises(UnsupportedExtractionError, match="cell data"):
        VTKAdapter(meshio_loader=lambda: meshio).extract(ExtractionRequest(source=source))


@pytest.mark.parametrize("suffix", [".pvtu", ".pvtp"])
def test_parallel_vtk_coordinator_is_explicitly_unsupported(tmp_path: Path, suffix: str) -> None:
    source = tmp_path / f"parallel{suffix}"
    source.write_text("synthetic coordinator", encoding="ascii")
    adapter = VTKAdapter(meshio_loader=lambda: _FakeMeshIO())

    probe = adapter.probe(source)
    inventory = adapter.inventory(source)

    assert not probe.supported
    assert probe.status == "unsupported"
    assert inventory.status == "unsupported"
    assert inventory.source_hash is None
    with pytest.raises(UnsupportedExtractionError, match="parallel VTK"):
        adapter.extract(ExtractionRequest(source=source))


def test_vtk_inventory_detects_source_change_during_meshio_read(tmp_path: Path) -> None:
    source = tmp_path / "changing.vtu"
    source.write_text("before", encoding="ascii")

    def mutate(path: Path) -> None:
        path.write_text("after", encoding="ascii")

    adapter = VTKAdapter(meshio_loader=lambda: _FakeMeshIO(on_read=mutate))

    with pytest.raises(SourceChangedError, match="inventory"):
        adapter.inventory(source)


def test_vtk_shallow_scan_reads_only_the_first_two_mib(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "large.vtk"
    source.write_bytes(
        b"# vtk DataFile Version 3.0\nSCALARS temperature float 1\n" + b"0" * (3 * 1024 * 1024)
    )
    original_open = Path.open
    read_sizes: list[int] = []

    class ReadSpy:
        def __init__(self, stream: object) -> None:
            self.stream = stream

        def __enter__(self) -> ReadSpy:
            return self

        def __exit__(self, *args: object) -> None:
            self.stream.close()  # type: ignore[attr-defined]

        def read(self, size: int = -1) -> bytes:
            read_sizes.append(size)
            return self.stream.read(size)  # type: ignore[attr-defined,no-any-return]

    def spy_open(path: Path, *args: object, **kwargs: object) -> object:
        stream = original_open(path, *args, **kwargs)  # type: ignore[arg-type]
        return ReadSpy(stream) if path == source else stream

    monkeypatch.setattr(Path, "open", spy_open)

    variables = _shallow_variable_scan(source)

    assert variables == ("temperature",)
    assert read_sizes == [2 * 1024 * 1024]


@pytest.mark.parametrize(
    ("adapter", "filename"),
    [(FluentAdapter(), "case.cas.h5"), (StarCCMAdapter(), "case.sim")],
)
def test_native_solver_adapters_are_read_only_and_discover_companion_exports(
    tmp_path: Path, adapter: FluentAdapter | StarCCMAdapter, filename: str
) -> None:
    native = tmp_path / filename
    native.write_bytes(b"synthetic native placeholder")
    export = tmp_path / "case.csv"
    export.write_text("x [m],temperature [K]\n0,1000\n", encoding="utf-8")
    before = _sha256(native)

    probe = adapter.probe(native)
    inventory = adapter.inventory(native)

    assert probe.supported
    assert not probe.available
    assert export.resolve() in inventory.companions
    assert inventory.status == "unsupported"
    assert "export" in inventory.recommendation.lower()
    with pytest.raises(UnsupportedExtractionError, match="read-only.*export"):
        adapter.extract(ExtractionRequest(source=native))
    assert _sha256(native) == before


def test_missing_native_solver_file_is_reported_explicitly(tmp_path: Path) -> None:
    source = tmp_path / "missing.cas"

    probe = FluentAdapter().probe(source)
    inventory = FluentAdapter().inventory(source)

    assert not probe.supported
    assert probe.status == "missing"
    assert inventory.status == "missing"


def test_native_solver_inventory_marks_missing_companion_export(tmp_path: Path) -> None:
    source = tmp_path / "case.sim"
    source.write_bytes(b"synthetic native placeholder")

    inventory = StarCCMAdapter().inventory(source)

    assert inventory.status == "missing-export"
    assert inventory.companions == ()


def test_native_solver_companion_discovery_does_not_match_old_case_prefix(
    tmp_path: Path,
) -> None:
    source = tmp_path / "case.sim"
    source.write_bytes(b"synthetic native placeholder")
    exact = tmp_path / "case.csv"
    exact.write_text("x [m]\n0\n", encoding="utf-8")
    stale = tmp_path / "case_old.csv"
    stale.write_text("x [m]\n1\n", encoding="utf-8")

    inventory = StarCCMAdapter().inventory(source)

    assert inventory.companions == (exact.resolve(),)


def test_adapter_record_mappings_are_defensive_and_immutable(tmp_path: Path) -> None:
    source_units = {"temperature": "K"}
    source_metadata = {"location": "point"}
    inventory = Inventory(
        adapter="fixture",
        source=tmp_path / "source",
        status="supported",
        units=source_units,
        metadata=source_metadata,
    )
    source_units["temperature"] = "degC"
    source_metadata["location"] = "cell"

    assert inventory.units["temperature"] == "K"
    assert inventory.metadata["location"] == "point"
    with pytest.raises(TypeError):
        inventory.units["temperature"] = "degC"  # type: ignore[index]


def test_csv_extracted_values_cannot_be_mutated(tmp_path: Path) -> None:
    source = tmp_path / "immutable.csv"
    source.write_text("case,value [Pa]\nA,1\n", encoding="utf-8")
    record = CSVAdapter().extract(ExtractionRequest(source=source))[0]

    with pytest.raises(TypeError):
        record.values["case"] = "B"  # type: ignore[index]
