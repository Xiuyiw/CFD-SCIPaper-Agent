from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Sequence
from pathlib import Path
from urllib.parse import unquote, urlsplit

MANIFEST_NAME = "PUBLIC_SNAPSHOT_MANIFEST.json"
MAX_BINARY_BYTES = 5 * 1024 * 1024

NATIVE_SOLVER_SUFFIXES = (
    ".cas",
    ".cas.gz",
    ".cas.h5",
    ".ccm",
    ".dat",
    ".dat.gz",
    ".dat.h5",
    ".h5",
    ".plt",
    ".res",
    ".sim",
    ".trn",
)
TEXT_SUFFIXES = frozenset(
    {
        ".cff",
        ".cfg",
        ".css",
        ".csv",
        ".html",
        ".ini",
        ".js",
        ".json",
        ".md",
        ".py",
        ".rst",
        ".svg",
        ".toml",
        ".ts",
        ".txt",
        ".xml",
        ".yaml",
        ".yml",
    }
)
TEXT_FILENAMES = frozenset({".gitignore", "LICENSE", "NOTICE"})
IGNORED_GENERATED_DIRECTORY_NAMES = frozenset(
    {
        ".cfdpaper",
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        ".worktrees",
        "__pycache__",
        "build",
        "dist",
    }
)
PRIVATE_PROJECT_MARKERS = (
    "".join(("P", "04")),
    "".join(("Gate", " 5")),
    "".join(("SG_", "Baffle")),
)
ABSOLUTE_USER_PATH_PATTERNS = (
    re.compile(r"(?i)\b[A-Z]:[\\/]+(?:Users|Documents and Settings)[\\/]+[^\s'\"<>]+"),
    re.compile(r"/(?:home|Users)/[^/\s'\"<>]+(?:/[^\s'\"<>]*)?"),
    re.compile("".join((r"/", "root", r"(?:/[^\s'\"<>]*)?"))),
)
API_KEY_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{16,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
)
MARKDOWN_LINK_PATTERN = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+[^)]*)?\)")


class ReleaseBoundaryError(ValueError):
    """Raised when an exported tree violates the public-release boundary."""


def _is_generated_artifact(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    return any(
        part in IGNORED_GENERATED_DIRECTORY_NAMES or part.endswith(".egg-info")
        for part in relative.parts
    ) or path.suffix in {".pyc", ".pyo"}


def _raise_issues(issues: list[str]) -> None:
    if issues:
        raise ReleaseBoundaryError("public release check failed:\n- " + "\n- ".join(issues))


def _load_manifest(root: Path) -> list[dict[str, object]]:
    manifest_path = root / MANIFEST_NAME
    if not manifest_path.is_file():
        raise ReleaseBoundaryError(f"snapshot manifest is missing: {MANIFEST_NAME}")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ReleaseBoundaryError(f"snapshot manifest is invalid: {error}") from error
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ReleaseBoundaryError("snapshot manifest has an unsupported schema")
    if payload.get("algorithm") != "sha256" or not isinstance(payload.get("files"), list):
        raise ReleaseBoundaryError("snapshot manifest must contain a SHA-256 file list")
    return payload["files"]


def _is_text_file(path: Path) -> bool:
    return path.name in TEXT_FILENAMES or path.suffix.lower() in TEXT_SUFFIXES


def _scan_text(path: Path, relative_text: str, root: Path, issues: list[str]) -> None:
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        issues.append(f"text file is not valid UTF-8: {relative_text}: {error}")
        return
    if any(pattern.search(content) for pattern in ABSOLUTE_USER_PATH_PATTERNS):
        issues.append(f"absolute user path found: {relative_text}")
    if any(pattern.search(content) for pattern in API_KEY_PATTERNS):
        issues.append(f"API key pattern found: {relative_text}")
    lowered = content.casefold()
    if any(marker.casefold() in lowered for marker in PRIVATE_PROJECT_MARKERS):
        issues.append(f"private project marker found: {relative_text}")
    if path.suffix.lower() != ".md" and path.name != "README.md":
        return
    for match in MARKDOWN_LINK_PATTERN.finditer(content):
        raw_target = match.group(1).strip("<>")
        parsed = urlsplit(raw_target)
        if parsed.scheme or parsed.netloc or raw_target.startswith("#"):
            continue
        target_text = unquote(parsed.path)
        if not target_text:
            continue
        target = (path.parent / target_text).resolve(strict=False)
        if not target.is_relative_to(root) or not target.exists():
            issues.append(f"broken relative link in {relative_text}: {raw_target}")


def _scan_file_class(path: Path, relative_text: str, issues: list[str]) -> None:
    name = path.name.lower()
    lowered_path = relative_text.casefold()
    if any(marker.casefold() in lowered_path for marker in PRIVATE_PROJECT_MARKERS):
        issues.append(f"private project marker in path: {relative_text}")
    if name.endswith(NATIVE_SOLVER_SUFFIXES):
        issues.append(f"native solver result is forbidden: {relative_text}")
    if ("private" in name and "manifest" in name) or ("regression" in name and "manifest" in name):
        issues.append(f"private manifest is forbidden: {relative_text}")
    if name == ".env" or name.startswith(".env."):
        issues.append(f"environment file is forbidden: {relative_text}")
    if not _is_text_file(path) and path.stat().st_size > MAX_BINARY_BYTES:
        issues.append(f"oversized binary is forbidden: {relative_text}")


def check_public_release(snapshot_root: Path) -> None:
    unresolved_root = Path(snapshot_root)
    if unresolved_root.is_symlink():
        raise ReleaseBoundaryError("snapshot root symlink is forbidden")
    root = unresolved_root.resolve(strict=True)
    if (root / MANIFEST_NAME).is_symlink():
        raise ReleaseBoundaryError("snapshot manifest symlink is forbidden")
    records = _load_manifest(root)
    issues: list[str] = []
    declared: dict[str, dict[str, object]] = {}
    for record in records:
        if not isinstance(record, dict):
            issues.append("manifest contains a non-object file record")
            continue
        relative_text = record.get("path")
        if not isinstance(relative_text, str):
            issues.append("manifest file record has no string path")
            continue
        relative = Path(relative_text)
        candidate = (root / relative).resolve(strict=False)
        if relative.is_absolute() or ".." in relative.parts or not candidate.is_relative_to(root):
            issues.append(f"manifest path escapes snapshot root: {relative_text}")
            continue
        if relative_text in declared:
            issues.append(f"manifest path is duplicated: {relative_text}")
            continue
        declared[relative_text] = record

    if list(declared) != sorted(declared):
        issues.append("manifest paths are not sorted deterministically")

    discovered = tuple(path for path in root.rglob("*") if not _is_generated_artifact(path, root))
    for path in discovered:
        if path.is_symlink():
            issues.append(f"symlink is forbidden: {path.relative_to(root).as_posix()}")
    actual = {
        path.relative_to(root).as_posix(): path
        for path in discovered
        if path.is_file() and path.name != MANIFEST_NAME
    }
    for relative_text in sorted(set(actual) - set(declared)):
        issues.append(f"file is absent from snapshot manifest: {relative_text}")
    for relative_text in sorted(set(declared) - set(actual)):
        issues.append(f"manifest entry is absent from snapshot: {relative_text}")
    for relative_text in sorted(set(actual) & set(declared)):
        path = actual[relative_text]
        payload = path.read_bytes()
        record = declared[relative_text]
        if record.get("size") != len(payload):
            issues.append(f"manifest size mismatch: {relative_text}")
        if record.get("sha256") != hashlib.sha256(payload).hexdigest():
            issues.append(f"manifest SHA-256 mismatch: {relative_text}")
        _scan_file_class(path, relative_text, issues)
        if _is_text_file(path):
            _scan_text(path, relative_text, root, issues)

    _raise_issues(issues)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check a curated public release snapshot.")
    parser.add_argument("snapshot_root", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        check_public_release(args.snapshot_root)
    except (OSError, ReleaseBoundaryError) as error:
        print(error)
        return 1
    print(f"public release check passed: {args.snapshot_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
