import json
import sys
from types import SimpleNamespace

from typer.testing import CliRunner

from cfdpaper.cli import app

runner = CliRunner()


def test_portable_export_calls_existing_workbench_api(tmp_path, monkeypatch):
    calls = []
    workspace = tmp_path / "source"
    workspace.mkdir()
    output = tmp_path / "portable"
    module = SimpleNamespace(
        export_workbench=lambda source, target, **options: (
            calls.append((source, target, options)) or target
        ),
    )
    monkeypatch.setitem(sys.modules, "cfdpaper.workbench_portability", module)
    result = runner.invoke(
        app, ["portable", "--workspace", str(workspace), "--output", str(output)]
    )
    assert result.exit_code == 0, result.output
    assert calls[0][:2] == (workspace, output)
    assert "Portable workbench" in result.output


def test_portable_inspect_returns_real_missing_items(tmp_path, monkeypatch):
    module = SimpleNamespace(
        inspect_workbench=lambda root, **kwargs: {
            "workspace": str(root / "workspace"),
            "missing_items": ["external/result.npz"],
        }
    )
    monkeypatch.setitem(sys.modules, "cfdpaper.workbench_portability", module)
    result = runner.invoke(app, ["portable", "--inspect", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["missing_items"] == ["external/result.npz"]


def test_portable_restore_forwards_exact_root_map(tmp_path, monkeypatch):
    calls = []
    module = SimpleNamespace(
        restore_workbench=lambda source, target, **kwargs: (
            calls.append((source, target, kwargs)) or target
        )
    )
    monkeypatch.setitem(sys.modules, "cfdpaper.workbench_portability", module)
    mapping = tmp_path / "roots.json"
    mapping.write_text(json.dumps({"old=source": "new=source"}), encoding="utf-8")
    output = tmp_path / "restored"
    result = runner.invoke(
        app,
        [
            "portable",
            "--restore",
            str(tmp_path),
            "--output",
            str(output),
            "--external-roots",
            str(mapping),
        ],
    )
    assert result.exit_code == 0, result.output
    assert calls == [(tmp_path, output, {"external_roots": {"old=source": "new=source"}})]


def test_portable_rejects_conflicting_actions(tmp_path):
    result = runner.invoke(
        app, ["portable", "--workspace", str(tmp_path), "--inspect", str(tmp_path)]
    )
    assert result.exit_code == 2
    assert "exactly one" in result.output


def test_mcp_command_uses_optional_stdio_entry(monkeypatch):
    calls = []
    monkeypatch.setitem(
        sys.modules, "cfdpaper.mcp_server", SimpleNamespace(main=lambda: calls.append(1))
    )
    result = runner.invoke(app, ["mcp"])
    assert result.exit_code == 0, result.output
    assert calls == [1]


def test_portable_rejects_nonmapping_external_roots(tmp_path):
    mapping = tmp_path / "roots.json"
    mapping.write_text('["not-a-mapping"]', encoding="utf-8")
    result = runner.invoke(
        app, ["portable", "--inspect", str(tmp_path), "--external-roots", str(mapping)]
    )
    assert result.exit_code == 2
    assert "JSON object" in result.output
