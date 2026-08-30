import importlib.metadata
import importlib.util
from pathlib import Path
from types import ModuleType


def test_source_tree_version_fallback_matches_release(monkeypatch) -> None:
    def distribution_is_not_installed(_distribution_name: str) -> str:
        raise importlib.metadata.PackageNotFoundError

    monkeypatch.setattr(importlib.metadata, "version", distribution_is_not_installed)
    source = Path(__file__).parents[1] / "src" / "cfdpaper" / "__init__.py"
    spec = importlib.util.spec_from_file_location("cfdpaper_source_version_test", source)
    assert spec is not None and spec.loader is not None
    module = ModuleType(spec.name)
    module.__spec__ = spec
    spec.loader.exec_module(module)

    assert module.__version__ == "0.1.0"
