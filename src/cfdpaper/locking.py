"""Cross-platform process file locking with bounded acquisition."""

from __future__ import annotations

import math
import os
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path


class ProcessFileLockTimeoutError(TimeoutError):
    """Raised when a process file lock cannot be acquired within its wait bound."""


class ProcessFileLockReleaseError(RuntimeError):
    """Raised when a process file lock cannot be released after a successful body."""


def try_os_file_lock(descriptor: int) -> None:
    """Attempt to acquire an OS-owned, non-blocking exclusive file lock."""
    if os.name == "nt":
        import msvcrt

        os.lseek(descriptor, 0, os.SEEK_SET)
        msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
        return

    import fcntl

    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)


@contextmanager
def process_file_lock(
    path: Path,
    timeout_seconds: float = 30,
    poll_seconds: float = 0.01,
    open_file: Callable[[os.PathLike[str] | str, int], int] | None = None,
    try_lock: Callable[[int], None] | None = None,
    close_file: Callable[[int], None] | None = None,
) -> Iterator[None]:
    """Hold an OS-owned lock on a persistent file for the duration of the body."""
    if not (math.isfinite(timeout_seconds) and timeout_seconds > 0):
        raise ValueError("process file lock timeout must be positive")
    if not (math.isfinite(poll_seconds) and poll_seconds > 0):
        raise ValueError("process file lock poll interval must be positive")

    lock_path = Path(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    open_descriptor = open_file or os.open
    acquire_lock = try_lock or try_os_file_lock
    close_descriptor = close_file or os.close
    deadline = time.monotonic() + timeout_seconds
    descriptor: int | None = None

    while descriptor is None:
        try:
            descriptor = open_descriptor(lock_path, os.O_CREAT | os.O_RDWR)
        except OSError as error:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ProcessFileLockTimeoutError(
                    f"process file lock timed out: {lock_path}"
                ) from error
            time.sleep(min(poll_seconds, remaining))

    try:
        while True:
            try:
                acquire_lock(descriptor)
                break
            except OSError as error:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ProcessFileLockTimeoutError(
                        f"process file lock timed out: {lock_path}"
                    ) from error
                time.sleep(min(poll_seconds, remaining))
    except BaseException:
        try:
            close_descriptor(descriptor)
        except OSError:
            pass
        raise

    try:
        yield
    except BaseException:
        try:
            close_descriptor(descriptor)
        except OSError:
            pass
        raise
    else:
        try:
            close_descriptor(descriptor)
        except OSError as error:
            raise ProcessFileLockReleaseError(
                f"process file lock release failed: {lock_path}"
            ) from error
