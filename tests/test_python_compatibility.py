from pathlib import Path


def test_controller_contracts_do_not_use_python311_only_strenum() -> None:
    source = (Path(__file__).parents[1] / "src" / "cfdpaper" / "contracts.py").read_text(
        encoding="utf-8"
    )

    assert "StrEnum" not in source
