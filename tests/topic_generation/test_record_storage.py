from pathlib import Path

from cfdpaper.contracts import BoundaryRecord, FieldRecord, MeshRecord, QoIRecord
from cfdpaper.indexing import ProjectIndexer
from cfdpaper.state import initialize_project
from cfdpaper.storage import ProjectStore


def _indexed_store(tmp_path: Path) -> tuple[ProjectStore, Path, str]:
    source = tmp_path / "structured-source.json"
    source.write_text('{"pressure_drop_pa": 12.0}\n', encoding="utf-8")
    initialize_project(tmp_path, "structured-records")
    store = ProjectStore.open(tmp_path)
    ProjectIndexer(store).inspect()
    return store, source, store.get_source(source.name).sha256


def test_scientific_records_survive_reopen_and_are_sorted_by_record_id(
    tmp_path: Path,
) -> None:
    store, source, source_hash = _indexed_store(tmp_path)
    for boundary_id in ("boundary-z", "boundary-a"):
        store.save_boundary(
            BoundaryRecord(
                boundary_id=boundary_id,
                case_id="case-a",
                boundary_type="mass-flow-inlet",
                values={"temperature": 300.0, "phase": "gas"},
                units={"temperature": "K"},
                source_uri=source.name,
                locator="$.boundaries[0]",
            )
        )
    for mesh_id in ("mesh-z", "mesh-a"):
        store.save_mesh(
            MeshRecord(
                mesh_id=mesh_id,
                case_id="case-a",
                cell_count=125_000,
                node_count=130_000,
                quality={"minimum_orthogonal_quality": 0.18},
                source_uri=source.name,
                locator="$.mesh",
            )
        )
    for field_id in ("field-z", "field-a"):
        store.save_field(
            FieldRecord(
                field_id=field_id,
                case_id="case-a",
                variable="static-pressure",
                unit="Pa",
                location="outlet",
                source_uri=source.name,
                locator="$.fields.pressure",
            )
        )
    for qoi_id in ("qoi-z", "qoi-a"):
        store.save_qoi(
            QoIRecord(
                qoi_id=qoi_id,
                case_id="case-a",
                name="pressure drop",
                value=12.0,
                unit="Pa",
                definition="area-weighted inlet pressure minus outlet pressure",
                status="derived",
                source_uri=source.name,
                locator="$.pressure_drop_pa",
            )
        )

    reopened = ProjectStore.open(tmp_path)

    boundaries = reopened.list_boundaries()
    meshes = reopened.list_meshes()
    fields = reopened.list_fields()
    qois = reopened.list_qois()
    assert [record.boundary_id for record in boundaries] == ["boundary-a", "boundary-z"]
    assert [record.mesh_id for record in meshes] == ["mesh-a", "mesh-z"]
    assert [record.field_id for record in fields] == ["field-a", "field-z"]
    assert [record.qoi_id for record in qois] == ["qoi-a", "qoi-z"]
    assert {record.source_hash for record in [*boundaries, *meshes, *fields, *qois]} == {
        source_hash
    }
    assert boundaries[0].values == {"phase": "gas", "temperature": 300.0}
    assert meshes[0].quality == {"minimum_orthogonal_quality": 0.18}
    assert fields[0].location == "outlet"
    assert qois[0].definition == "area-weighted inlet pressure minus outlet pressure"


def test_missing_record_hash_is_pinned_to_current_source_version(tmp_path: Path) -> None:
    store, source, current_hash = _indexed_store(tmp_path)
    store.save_qoi(
        QoIRecord(
            qoi_id="qoi-pressure-drop",
            case_id="case-a",
            name="pressure drop",
            value=12.0,
            unit="Pa",
            definition="area-weighted inlet pressure minus outlet pressure",
            source_uri=source.name,
            locator="$.pressure_drop_pa",
            source_hash=None,
        )
    )

    [record] = ProjectStore.open(tmp_path).list_qois()

    assert record.source_hash == current_hash
    assert record.stale is False


def test_changed_source_marks_record_stale_but_retains_saved_version_hash(
    tmp_path: Path,
) -> None:
    store, source, saved_hash = _indexed_store(tmp_path)
    store.save_field(
        FieldRecord(
            field_id="field-pressure",
            case_id="case-a",
            variable="static-pressure",
            unit="Pa",
            location="outlet",
            source_uri=source.name,
            locator="$.pressure_drop_pa",
        )
    )
    source.write_text('{"pressure_drop_pa": 10.0}\n', encoding="utf-8")
    ProjectIndexer(store, strict_hash=True).inspect()
    current_hash = store.get_source(source.name).sha256

    [record] = ProjectStore.open(tmp_path).list_fields()

    assert current_hash != saved_hash
    assert record.source_hash == saved_hash
    assert record.source_hash != current_hash
    assert record.stale is True
