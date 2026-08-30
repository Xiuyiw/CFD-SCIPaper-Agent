import json
from pathlib import Path

from cfdpaper.schema_export import PUBLIC_CONTRACTS, export_json_schemas


def test_export_json_schemas_writes_every_public_contract(tmp_path: Path) -> None:
    written = export_json_schemas(tmp_path)

    assert {path.stem for path in written} == set(PUBLIC_CONTRACTS)
    for path in written:
        schema = json.loads(path.read_text(encoding="utf-8"))
        assert schema["title"] == path.stem
        assert schema["additionalProperties"] is False


def test_tracked_schemas_match_controller_models() -> None:
    tracked = Path(__file__).parents[1] / "schemas"

    for name, model in PUBLIC_CONTRACTS.items():
        actual = json.loads((tracked / f"{name}.json").read_text(encoding="utf-8"))
        assert actual == model.model_json_schema()
