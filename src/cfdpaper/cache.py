"""Content-addressed local cache with atomic writes and integrity checks."""

from __future__ import annotations

import hashlib
import os
import re
import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4
from weakref import WeakValueDictionary

from cfdpaper.locking import (
    ProcessFileLockReleaseError,
    ProcessFileLockTimeoutError,
    process_file_lock,
    try_os_file_lock,
)

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_DEFAULT_LOCK_TIMEOUT_SECONDS = 30.0
_LOCKS_GUARD = threading.Lock()
_DIGEST_LOCKS: WeakValueDictionary[str, threading.Lock] = WeakValueDictionary()


def _lock_for_digest(digest: str) -> threading.Lock:
    with _LOCKS_GUARD:
        lock = _DIGEST_LOCKS.get(digest)
        if lock is None:
            lock = threading.Lock()
            _DIGEST_LOCKS[digest] = lock
        return lock


class CacheIntegrityError(RuntimeError):
    """Raised when cached bytes do not match their content address."""


class CacheLockTimeoutError(TimeoutError):
    """Raised when another process holds a digest lock beyond the wait bound."""


class ContentAddressedCache:
    def __init__(
        self,
        project_root: Path,
        *,
        lock_timeout_seconds: float = _DEFAULT_LOCK_TIMEOUT_SECONDS,
    ) -> None:
        if lock_timeout_seconds <= 0:
            raise ValueError("cache lock timeout must be positive")
        self.root = project_root.expanduser().resolve() / ".cfdpaper" / "cache"
        self.lock_timeout_seconds = lock_timeout_seconds
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, digest: str) -> Path:
        if not _SHA256_PATTERN.fullmatch(digest):
            raise ValueError("cache digest must be a lowercase SHA-256 hex string")
        return self.root / digest[:2] / digest

    def put_bytes(self, content: bytes) -> Path:
        digest = hashlib.sha256(content).hexdigest()
        destination = self.path_for(digest)
        with self._digest_lock(digest):
            if destination.exists():
                self._verify_path(destination, digest)
                return destination
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.parent / f".{digest}.{uuid4().hex}.tmp"
            try:
                with temporary.open("xb") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, destination)
            finally:
                temporary.unlink(missing_ok=True)
        return destination

    def put_file(self, source: Path, *, expected_hash: str | None = None) -> Path:
        if expected_hash is not None:
            destination = self.path_for(expected_hash)
            with self._digest_lock(expected_hash):
                if destination.exists():
                    self._verify_path(destination, expected_hash)
                    return destination
        else:
            destination = None

        staging = self.root / f".staging.{uuid4().hex}.tmp"
        digest = hashlib.sha256()
        try:
            with source.open("rb") as reader, staging.open("xb") as writer:
                for block in iter(lambda: reader.read(1024 * 1024), b""):
                    digest.update(block)
                    writer.write(block)
                writer.flush()
                os.fsync(writer.fileno())
            actual_hash = digest.hexdigest()
            if expected_hash is not None and actual_hash != expected_hash:
                raise CacheIntegrityError("source changed while populating content cache")
            destination = self.path_for(actual_hash)
            with self._digest_lock(actual_hash):
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.exists():
                    self._verify_path(destination, actual_hash)
                else:
                    os.replace(staging, destination)
            return destination
        finally:
            staging.unlink(missing_ok=True)

    def read_bytes(self, digest: str) -> bytes:
        path = self.path_for(digest)
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != digest:
            raise CacheIntegrityError(f"cache integrity check failed: {digest}")
        return content

    def is_valid(self, digest: str) -> bool:
        path = self.path_for(digest)
        if not path.is_file():
            return False
        try:
            self._verify_path(path, digest)
        except CacheIntegrityError:
            return False
        return True

    @staticmethod
    def digest_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def _verify_path(path: Path, digest: str) -> None:
        if ContentAddressedCache.digest_file(path) != digest:
            raise CacheIntegrityError(f"cache integrity check failed: {digest}")

    @contextmanager
    def _digest_lock(self, digest: str) -> Iterator[None]:
        with _lock_for_digest(digest), self._process_digest_lock(digest):
            yield

    @contextmanager
    def _process_digest_lock(self, digest: str) -> Iterator[None]:
        lock_path = self.root / ".locks" / digest[:2] / f"{digest}.lock"
        try:
            lock_context = process_file_lock(
                lock_path,
                timeout_seconds=self.lock_timeout_seconds,
                open_file=lambda path, flags: os.open(path, flags),
                try_lock=self._try_process_lock,
                close_file=self._close_process_lock,
            )
            lock_context.__enter__()
        except ProcessFileLockTimeoutError as error:
            raise CacheLockTimeoutError(f"cache lock timed out for digest {digest}") from error
        except ProcessFileLockReleaseError as error:
            raise CacheLockTimeoutError(f"cache lock release failed for digest {digest}") from error

        try:
            yield
        except BaseException:
            if not lock_context.__exit__(*sys.exc_info()):
                raise
        else:
            try:
                lock_context.__exit__(None, None, None)
            except ProcessFileLockTimeoutError as error:
                raise CacheLockTimeoutError(f"cache lock timed out for digest {digest}") from error
            except ProcessFileLockReleaseError as error:
                raise CacheLockTimeoutError(
                    f"cache lock release failed for digest {digest}"
                ) from error

    @staticmethod
    def _try_process_lock(descriptor: int) -> None:
        try_os_file_lock(descriptor)

    @staticmethod
    def _close_process_lock(descriptor: int) -> None:
        os.close(descriptor)
