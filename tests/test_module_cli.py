"""A common host invocation must reach the installed CLI from another directory."""

import subprocess
import sys


def test_module_cli_is_usable_outside_repository(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "cfdpaper", "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "inspect" in result.stdout and "write" in result.stdout
