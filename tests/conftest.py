"""Shared release expectation from the package's declared version."""

import re
from pathlib import Path

import pytest


@pytest.fixture
def release_version():
    config = (Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"$', config, re.MULTILINE)
    assert match is not None, "The project must declare its release version"
    return match[1]
