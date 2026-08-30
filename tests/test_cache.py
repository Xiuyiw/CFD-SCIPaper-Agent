import hashlib
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

import cfdpaper.cache as cache_module
from cfdpaper.cache import (
    CacheIntegrityError,
    CacheLockTimeoutError,
    ContentAddressedCache,
)
from cfdpaper.locking import ProcessFileLockReleaseError, ProcessFileLockTimeoutError

_SUBPROCESS_CACHE_WRITER = r"""
import os
import sys
import time
from pathlib import Path

import cfdpaper.cache as cache_module
from cfdpaper.cache import ContentAddressedCache

project = Path(sys.argv[1])
operation = sys.argv[2]
source = Path(sys.argv[3])
start = Path(sys.argv[4])
ready = Path(sys.argv[5])
replace_guard = Path(sys.argv[6])
payload = b"cross-process immutable CFD evidence"
original_replace = os.replace


def windows_contentious_replace(source_path, destination_path):
    try:
        descriptor = os.open(replace_guard, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise PermissionError("simulated Windows cross-process replace contention") from error
    try:
        time.sleep(0.2)
        original_replace(source_path, destination_path)
    finally:
        os.close(descriptor)
        replace_guard.unlink(missing_ok=True)


cache_module.os.replace = windows_contentious_replace
ready.mkdir(parents=True, exist_ok=True)
(ready / str(os.getpid())).touch()
deadline = time.monotonic() + 20
while not start.exists():
    if time.monotonic() >= deadline:
        raise TimeoutError("subprocess start barrier timed out")
    time.sleep(0.005)

cache = ContentAddressedCache(project)
for _ in range(3):
    if operation == "put_bytes":
        result = cache.put_bytes(payload)
    else:
        result = cache.put_file(source)
print(result)
"""

_SUBPROCESS_LOCK_HOLDER = r"""
import hashlib
import os
import sys
import time
from pathlib import Path

from cfdpaper.cache import ContentAddressedCache

project = Path(sys.argv[1])
ready = Path(sys.argv[2])
release = Path(sys.argv[3])
crash = Path(sys.argv[4])
digest = hashlib.sha256(b"live owner").hexdigest()
cache = ContentAddressedCache(project)
with cache._process_digest_lock(digest):
    ready.touch()
    deadline = time.monotonic() + 20
    while not release.exists():
        if crash.exists():
            os._exit(0)
        if time.monotonic() >= deadline:
            raise TimeoutError("lock-holder release barrier timed out")
        time.sleep(0.005)
"""


def test_content_cache_uses_hash_path_atomic_write_and_reuse(tmp_path: Path) -> None:
    cache = ContentAddressedCache(tmp_path)

    first = cache.put_bytes(b"immutable evidence")
    second = cache.put_bytes(b"immutable evidence")

    assert first == second
    assert first.parent.name == first.name[:2]
    assert cache.read_bytes(first.name) == b"immutable evidence"
    assert not list((tmp_path / ".cfdpaper" / "cache").rglob("*.tmp"))


def test_content_cache_rejects_corruption(tmp_path: Path) -> None:
    cache = ContentAddressedCache(tmp_path)
    path = cache.put_bytes(b"trusted")
    path.write_bytes(b"tampered")

    with pytest.raises(CacheIntegrityError, match="integrity"):
        cache.read_bytes(path.name)


def test_put_rejects_an_existing_corrupt_target(tmp_path: Path) -> None:
    payload = b"trusted"
    digest = hashlib.sha256(payload).hexdigest()
    cache = ContentAddressedCache(tmp_path)
    destination = cache.path_for(digest)
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"tampered")

    with pytest.raises(CacheIntegrityError, match="integrity"):
        cache.put_bytes(payload)


def test_digest_lock_acquisition_retries_a_transient_permission_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = b"transient Windows lock acquisition conflict"
    digest = hashlib.sha256(payload).hexdigest()
    cache = ContentAddressedCache(tmp_path, lock_timeout_seconds=0.5)
    lock_path = cache.root / ".locks" / digest[:2] / f"{digest}.lock"
    original_open = os.open
    lock_open_attempts = 0

    def transiently_block_lock_acquisition(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
    ) -> int:
        nonlocal lock_open_attempts
        if Path(path) == lock_path:
            lock_open_attempts += 1
            if lock_open_attempts == 1:
                raise PermissionError("simulated Windows lock acquisition conflict")
        return original_open(path, flags, mode)

    monkeypatch.setattr(cache_module.os, "open", transiently_block_lock_acquisition)

    result = cache.put_bytes(payload)

    assert cache.read_bytes(result.name) == payload
    assert lock_open_attempts == 2
    assert lock_path.exists()


def test_digest_lock_acquisition_failure_is_bounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = b"permanent lock acquisition failure"
    digest = hashlib.sha256(payload).hexdigest()
    cache = ContentAddressedCache(tmp_path, lock_timeout_seconds=0.05)
    lock_path = cache.root / ".locks" / digest[:2] / f"{digest}.lock"
    original_open = os.open

    def permanently_block_lock_acquisition(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
    ) -> int:
        if Path(path) == lock_path:
            raise PermissionError("simulated permanent lock acquisition failure")
        return original_open(path, flags, mode)

    monkeypatch.setattr(cache_module.os, "open", permanently_block_lock_acquisition)

    started = time.monotonic()
    with pytest.raises(CacheLockTimeoutError, match="timed out"):
        cache.put_bytes(payload)

    assert time.monotonic() - started < 1


def test_shared_process_lock_timeout_maps_to_cache_lock_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def shared_lock_timeout(*args: object, **kwargs: object) -> None:
        raise ProcessFileLockTimeoutError("simulated shared lock timeout")

    monkeypatch.setattr(cache_module, "process_file_lock", shared_lock_timeout, raising=False)
    cache = ContentAddressedCache(tmp_path)

    with pytest.raises(CacheLockTimeoutError, match="timed out"):
        cache.put_bytes(b"shared lock timeout")


@pytest.mark.parametrize(
    "body_error_type",
    [ProcessFileLockTimeoutError, ProcessFileLockReleaseError],
)
def test_process_digest_lock_preserves_shared_exception_raised_by_body(
    tmp_path: Path, body_error_type: type[Exception]
) -> None:
    cache = ContentAddressedCache(tmp_path)
    digest = hashlib.sha256(b"body exception transparency").hexdigest()

    with pytest.raises(body_error_type, match="body sentinel"):
        with cache._process_digest_lock(digest):
            raise body_error_type("body sentinel")


@pytest.mark.parametrize("suppress", [True, False])
def test_process_digest_lock_honors_body_exception_suppression(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, suppress: bool
) -> None:
    class FakeLockContext:
        exit_arguments: tuple[object, object, object] | None = None
        active_exception: tuple[object, object, object] | None = None

        def __enter__(self) -> None:
            return None

        def __exit__(self, exception_type: object, exception: object, traceback: object) -> bool:
            self.exit_arguments = (exception_type, exception, traceback)
            self.active_exception = sys.exc_info()
            return suppress

    lock_context = FakeLockContext()
    monkeypatch.setattr(cache_module, "process_file_lock", lambda *args, **kwargs: lock_context)
    cache = ContentAddressedCache(tmp_path)
    digest = hashlib.sha256(b"body exception suppression").hexdigest()
    body_error = ValueError("body sentinel")

    if suppress:
        with cache._process_digest_lock(digest):
            raise body_error
    else:
        with pytest.raises(ValueError, match="body sentinel") as captured:
            with cache._process_digest_lock(digest):
                raise body_error
        assert captured.value is body_error

    assert lock_context.exit_arguments is not None
    assert lock_context.active_exception is not None
    assert all(
        received is active
        for received, active in zip(
            lock_context.exit_arguments, lock_context.active_exception, strict=True
        )
    )


def test_process_lock_close_failure_is_reported_after_a_successful_body(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = ContentAddressedCache(tmp_path)
    original_close = ContentAddressedCache._close_process_lock

    def close_then_fail(descriptor: int) -> None:
        original_close(descriptor)
        raise PermissionError("simulated close failure")

    monkeypatch.setattr(ContentAddressedCache, "_close_process_lock", staticmethod(close_then_fail))

    with pytest.raises(CacheLockTimeoutError, match="release failed"):
        cache.put_bytes(b"successful cache body")


def test_process_lock_close_failure_does_not_hide_the_body_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = ContentAddressedCache(tmp_path)
    original_close = ContentAddressedCache._close_process_lock

    def close_then_fail(descriptor: int) -> None:
        original_close(descriptor)
        raise PermissionError("simulated close failure")

    monkeypatch.setattr(ContentAddressedCache, "_close_process_lock", staticmethod(close_then_fail))

    with pytest.raises(CacheIntegrityError, match="body failure"):
        with cache._process_digest_lock(hashlib.sha256(b"body failure").hexdigest()):
            raise CacheIntegrityError("body failure")


def test_aged_lock_is_not_reclaimed_while_owner_is_alive(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    ready = tmp_path / "ready"
    release = tmp_path / "release"
    crash = tmp_path / "crash"
    digest = hashlib.sha256(b"live owner").hexdigest()
    lock_path = project / ".cfdpaper" / "cache" / ".locks" / digest[:2] / f"{digest}.lock"
    environment = os.environ.copy()
    source_root = str(Path(__file__).parents[1] / "src")
    environment["PYTHONPATH"] = os.pathsep.join(
        item for item in (source_root, environment.get("PYTHONPATH")) if item
    )
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            _SUBPROCESS_LOCK_HOLDER,
            str(project),
            str(ready),
            str(release),
            str(crash),
        ],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 10
        while not ready.exists():
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                pytest.fail(f"lock holder exited early: {stdout!r}, {stderr!r}")
            if time.monotonic() >= deadline:
                pytest.fail("lock-holder ready barrier timed out")
            time.sleep(0.005)
        old_time = time.time() - 600
        os.utime(lock_path, (old_time, old_time))
        contender = ContentAddressedCache(project, lock_timeout_seconds=0.05)

        with pytest.raises(CacheLockTimeoutError, match="timed out"):
            contender.put_bytes(b"live owner")
    finally:
        release.touch()
        stdout, stderr = process.communicate(timeout=10)

    assert process.returncode == 0, (stdout, stderr)


def test_process_lock_is_released_when_the_holder_exits(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    ready = tmp_path / "ready"
    release = tmp_path / "release"
    crash = tmp_path / "crash"
    environment = os.environ.copy()
    source_root = str(Path(__file__).parents[1] / "src")
    environment["PYTHONPATH"] = os.pathsep.join(
        item for item in (source_root, environment.get("PYTHONPATH")) if item
    )
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            _SUBPROCESS_LOCK_HOLDER,
            str(project),
            str(ready),
            str(release),
            str(crash),
        ],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 10
        while not ready.exists():
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                pytest.fail(f"lock holder exited early: {stdout!r}, {stderr!r}")
            if time.monotonic() >= deadline:
                pytest.fail("lock-holder ready barrier timed out")
            time.sleep(0.005)
        crash.touch()
        stdout, stderr = process.communicate(timeout=10)
    finally:
        if process.poll() is None:
            release.touch()
            process.kill()
            stdout, stderr = process.communicate(timeout=10)

    assert process.returncode == 0, (stdout, stderr)
    cache = ContentAddressedCache(project, lock_timeout_seconds=0.5)
    result = cache.put_bytes(b"live owner")
    assert cache.read_bytes(result.name) == b"live owner"


def test_process_lock_file_persists_for_os_owned_lock_reuse(tmp_path: Path) -> None:
    cache = ContentAddressedCache(tmp_path)
    digest = hashlib.sha256(b"persistent OS lock").hexdigest()
    lock_path = cache.root / ".locks" / digest[:2] / f"{digest}.lock"

    with cache._process_digest_lock(digest):
        assert lock_path.stat().st_size == 0
        first_identity = lock_path.stat().st_ino

    assert lock_path.exists()
    with cache._process_digest_lock(digest):
        second_identity = lock_path.stat().st_ino

    assert second_identity == first_identity


def test_same_digest_writes_are_serialized_across_sixteen_writers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = b"shared immutable CFD evidence"
    barrier = threading.Barrier(16)
    counter_lock = threading.Lock()
    active_replaces = 0
    maximum_replaces = 0
    original_replace = os.replace

    def guarded_replace(source: Path, destination: Path) -> None:
        nonlocal active_replaces, maximum_replaces
        with counter_lock:
            active_replaces += 1
            maximum_replaces = max(maximum_replaces, active_replaces)
            concurrent = active_replaces
        try:
            time.sleep(0.005)
            if concurrent > 1:
                raise PermissionError("simulated Windows concurrent replace contention")
            original_replace(source, destination)
        finally:
            with counter_lock:
                active_replaces -= 1

    monkeypatch.setattr(cache_module.os, "replace", guarded_replace)

    def write_many_times() -> set[Path]:
        cache = ContentAddressedCache(tmp_path)
        barrier.wait()
        return {cache.put_bytes(payload) for _ in range(8)}

    with ThreadPoolExecutor(max_workers=16) as executor:
        results = list(executor.map(lambda _: write_many_times(), range(16)))

    paths = set().union(*results)
    assert len(paths) == 1
    assert maximum_replaces == 1
    digest = next(iter(paths)).name
    assert ContentAddressedCache(tmp_path).read_bytes(digest) == payload


@pytest.mark.parametrize("operation", ["put_bytes", "put_file"])
def test_same_digest_writes_are_safe_across_sixteen_processes(
    tmp_path: Path, operation: str
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    source = tmp_path / "source.bin"
    source.write_bytes(b"cross-process immutable CFD evidence")
    start = tmp_path / "start"
    ready = tmp_path / "ready"
    replace_guard = tmp_path / "replace.guard"
    environment = os.environ.copy()
    source_root = str(Path(__file__).parents[1] / "src")
    environment["PYTHONPATH"] = os.pathsep.join(
        item for item in (source_root, environment.get("PYTHONPATH")) if item
    )
    command = [
        sys.executable,
        "-c",
        _SUBPROCESS_CACHE_WRITER,
        str(project),
        operation,
        str(source),
        str(start),
        str(ready),
        str(replace_guard),
    ]
    output_dir = tmp_path / "process-output"
    output_dir.mkdir()
    processes: list[subprocess.Popen[bytes]] = []
    output_paths: list[tuple[Path, Path]] = []
    for index in range(16):
        stdout_path = output_dir / f"{index:02d}.stdout"
        stderr_path = output_dir / f"{index:02d}.stderr"
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            processes.append(
                subprocess.Popen(
                    command,
                    env=environment,
                    stdout=stdout,
                    stderr=stderr,
                )
            )
        output_paths.append((stdout_path, stderr_path))
    timed_out: list[int] = []
    try:
        deadline = time.monotonic() + 20
        while len(list(ready.glob("*"))) < len(processes):
            if time.monotonic() >= deadline:
                pytest.fail("subprocess ready barrier timed out")
            time.sleep(0.01)
        start.touch()
        deadline = time.monotonic() + 30
        while any(process.poll() is None for process in processes):
            if time.monotonic() >= deadline:
                timed_out = [process.pid for process in processes if process.poll() is None]
                break
            time.sleep(0.01)
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
            process.wait()

    outputs = [
        (
            process.pid,
            process.returncode,
            stdout_path.read_text(encoding="utf-8", errors="replace"),
            stderr_path.read_text(encoding="utf-8", errors="replace"),
        )
        for process, (stdout_path, stderr_path) in zip(processes, output_paths, strict=True)
    ]
    assert not timed_out, outputs
    assert all(returncode == 0 for _, returncode, _, _ in outputs), outputs
    paths = {stdout.strip() for _, _, stdout, _ in outputs}
    assert len(paths) == 1
    digest = Path(paths.pop()).name
    assert ContentAddressedCache(project).read_bytes(digest) == source.read_bytes()
