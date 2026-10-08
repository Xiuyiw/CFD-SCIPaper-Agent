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


@pytest.fixture
def controlled_lock_clock(monkeypatch):
    import cfdpaper.locking as locking_module

    class Clock:
        tick = 0.001

        def __init__(self):
            self.now = 0.0
            self.sleeps = []

        def monotonic(self):
            value = self.now
            self.now += self.tick
            return value

        def sleep(self, delay):
            assert delay > 0, "Lock retry must use a positive remaining wait"
            assert len(self.sleeps) < 1000, "Lock retry failed to stop at its deadline"
            self.sleeps.append(delay)
            self.now += delay

    clock = Clock()
    # Replace this module's time reference, not the process-wide time functions.
    monkeypatch.setattr(locking_module, "time", clock)
    return clock
