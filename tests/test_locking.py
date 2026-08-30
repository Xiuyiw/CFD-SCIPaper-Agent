import math
import os
import time
from pathlib import Path

import pytest

from cfdpaper.locking import (
    ProcessFileLockReleaseError,
    ProcessFileLockTimeoutError,
    process_file_lock,
)


@pytest.mark.parametrize(
    ("timeout_seconds", "poll_seconds", "message"),
    [
        (math.nan, 0.01, "process file lock timeout must be positive"),
        (math.inf, 0.01, "process file lock timeout must be positive"),
        (-math.inf, 0.01, "process file lock timeout must be positive"),
        (0.0, 0.01, "process file lock timeout must be positive"),
        (-1.0, 0.01, "process file lock timeout must be positive"),
        (30.0, math.nan, "process file lock poll interval must be positive"),
        (30.0, math.inf, "process file lock poll interval must be positive"),
        (30.0, -math.inf, "process file lock poll interval must be positive"),
        (30.0, 0.0, "process file lock poll interval must be positive"),
        (30.0, -1.0, "process file lock poll interval must be positive"),
    ],
)
def test_process_file_lock_rejects_non_finite_or_non_positive_wait_parameters(
    tmp_path: Path,
    timeout_seconds: float,
    poll_seconds: float,
    message: str,
) -> None:
    started = time.monotonic()

    with pytest.raises(ValueError) as captured:
        with process_file_lock(
            tmp_path / "resource.lock",
            timeout_seconds=timeout_seconds,
            poll_seconds=poll_seconds,
        ):
            pass

    assert time.monotonic() - started < 1
    assert str(captured.value) == message


def test_process_file_lock_retries_open_and_leaves_persistent_empty_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lock_path = tmp_path / "nested" / "resource.lock"
    original_open = os.open
    attempts = 0

    def transiently_denied_open(path: os.PathLike[str] | str, flags: int) -> int:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise PermissionError("simulated transient open denial")
        return original_open(path, flags)

    monkeypatch.setattr("cfdpaper.locking.os.open", transiently_denied_open)

    with process_file_lock(lock_path, timeout_seconds=0.5):
        assert lock_path.exists()

    assert attempts == 2
    assert lock_path.exists()
    assert lock_path.stat().st_size == 0


def test_process_file_lock_acquisition_timeout_is_bounded(tmp_path: Path) -> None:
    lock_path = tmp_path / "resource.lock"

    def permanently_denied_lock(descriptor: int) -> None:
        raise PermissionError("simulated permanent lock denial")

    started = time.monotonic()
    with pytest.raises(ProcessFileLockTimeoutError, match="timed out"):
        with process_file_lock(lock_path, timeout_seconds=0.05, try_lock=permanently_denied_lock):
            pytest.fail("lock body must not run")

    assert time.monotonic() - started < 1


def test_process_file_lock_reports_close_failure_after_successful_body(tmp_path: Path) -> None:
    lock_path = tmp_path / "resource.lock"
    descriptor: int | None = None

    def capture_open(path: os.PathLike[str] | str, flags: int) -> int:
        nonlocal descriptor
        descriptor = os.open(path, flags)
        return descriptor

    def close_then_fail(open_descriptor: int) -> None:
        os.close(open_descriptor)
        raise PermissionError("simulated close failure")

    with pytest.raises(ProcessFileLockReleaseError, match="release failed"):
        with process_file_lock(lock_path, open_file=capture_open, close_file=close_then_fail):
            pass

    assert descriptor is not None
    with pytest.raises(OSError):
        os.fstat(descriptor)


def test_process_file_lock_close_failure_does_not_hide_body_error(tmp_path: Path) -> None:
    lock_path = tmp_path / "resource.lock"

    def close_then_fail(descriptor: int) -> None:
        os.close(descriptor)
        raise PermissionError("simulated close failure")

    with pytest.raises(ValueError, match="body failure"):
        with process_file_lock(lock_path, close_file=close_then_fail):
            raise ValueError("body failure")
