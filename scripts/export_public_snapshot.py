from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections.abc import Sequence
from pathlib import Path

MANIFEST_NAME = "PUBLIC_SNAPSHOT_MANIFEST.json"

REQUIRED_PUBLIC_ROOTS = ("src", "tests", ".github", "schemas")
OPTIONAL_PUBLIC_ROOTS = ("examples",)
PUBLIC_ROOTS = REQUIRED_PUBLIC_ROOTS + OPTIONAL_PUBLIC_ROOTS

REQUIRED_PUBLIC_FILES = (
    ".gitignore",
    "README.md",
    "LICENSE",
    "NOTICE",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "CITATION.cff",
    "LIMITATIONS.md",
    "pyproject.toml",
    "scripts/export_public_snapshot.py",
    "scripts/check_public_release.py",
    "docs/ROADMAP.md",
    "docs/architecture/overview.md",
    "docs/releases/v0.1.0.md",
)
OPTIONAL_PUBLIC_FILES: tuple[str, ...] = ()
PUBLIC_FILES = REQUIRED_PUBLIC_FILES + OPTIONAL_PUBLIC_FILES

PUBLIC_EXCLUDES = (
    "tests/private",
    "docs/superpowers",
    "quality_reports",
    ".cfdpaper",
    ".worktrees",
)

EXCLUDED_COMPONENTS = frozenset(
    {
        ".cfdpaper",
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        ".worktrees",
        "__pycache__",
        "node_modules",
        "private",
        "private-fixtures",
        "quality_reports",
        "venv",
    }
)
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


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _is_public_file(relative: Path) -> bool:
    relative_text = relative.as_posix()
    if any(
        relative_text == excluded or relative_text.startswith(f"{excluded}/")
        for excluded in PUBLIC_EXCLUDES
    ):
        return False
    lowered_parts = tuple(part.lower() for part in relative.parts)
    if any(part in EXCLUDED_COMPONENTS for part in lowered_parts):
        return False
    name = relative.name.lower()
    if name == ".env" or name.startswith(".env."):
        return False
    if "private_manifest" in name or "private-manifest" in name:
        return False
    return not name.endswith(NATIVE_SOLVER_SUFFIXES)


def _allowlisted_source_path(source_root: Path, relative_text: str) -> Path:
    relative = Path(relative_text)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise ValueError(f"allowlist path escapes source repository: {relative_text}")
    candidate = source_root.joinpath(relative)
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(source_root):
        raise ValueError(f"allowlist path escapes source repository: {relative_text}")
    return candidate


def _collect_root_files(root: Path, source_root: Path) -> set[Path]:
    selected: set[Path] = set()
    for child in sorted(root.iterdir(), key=lambda item: item.name):
        relative = child.relative_to(source_root)
        if not _is_public_file(relative):
            continue
        if child.is_symlink():
            raise ValueError(f"symlink input is forbidden: {relative.as_posix()}")
        if child.is_dir():
            selected.update(_collect_root_files(child, source_root))
        elif child.is_file():
            selected.add(child)
    return selected


def export_public_snapshot(source_root: Path, output_root: Path) -> Path:
    unresolved_source = Path(source_root)
    if unresolved_source.is_symlink():
        raise ValueError("source repository must not be a symlink")
    source_root = unresolved_source.resolve(strict=True)
    unresolved_output = Path(output_root)
    output_root = unresolved_output.resolve(strict=False)
    if output_root == source_root or output_root.is_relative_to(source_root):
        raise ValueError("snapshot destination must be outside the source repository")
    if output_root.exists():
        if not output_root.is_dir() or any(output_root.iterdir()):
            raise ValueError("snapshot destination must be empty")

    selected: set[Path] = set()
    for relative_root in REQUIRED_PUBLIC_ROOTS:
        root = _allowlisted_source_path(source_root, relative_root)
        if not root.is_dir():
            raise FileNotFoundError(f"required public root is missing: {relative_root}")
        if root.is_symlink():
            raise ValueError(f"symlink input is forbidden: {relative_root}")
        selected.update(_collect_root_files(root, source_root))
    for relative_root in OPTIONAL_PUBLIC_ROOTS:
        root = _allowlisted_source_path(source_root, relative_root)
        if root.is_dir():
            if root.is_symlink():
                raise ValueError(f"symlink input is forbidden: {relative_root}")
            selected.update(_collect_root_files(root, source_root))

    for relative_file in REQUIRED_PUBLIC_FILES:
        path = _allowlisted_source_path(source_root, relative_file)
        if not path.is_file():
            raise FileNotFoundError(f"required public file is missing: {relative_file}")
        if path.is_symlink():
            raise ValueError(f"symlink input is forbidden: {relative_file}")
        selected.add(path)
    for relative_file in OPTIONAL_PUBLIC_FILES:
        path = _allowlisted_source_path(source_root, relative_file)
        if path.is_file():
            if path.is_symlink():
                raise ValueError(f"symlink input is forbidden: {relative_file}")
            selected.add(path)

    output_root.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    for source in sorted(selected, key=lambda item: item.relative_to(source_root).as_posix()):
        relative = source.relative_to(source_root)
        destination = output_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        payload = destination.read_bytes()
        records.append(
            {
                "path": relative.as_posix(),
                "sha256": _sha256(payload),
                "size": len(payload),
            }
        )

    manifest_path = output_root / MANIFEST_NAME
    manifest_path.write_text(
        json.dumps(
            {"algorithm": "sha256", "files": records, "schema_version": 1},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest_path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export the curated CFD-Paper-Agent public tree.")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--source",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help=argparse.SUPPRESS,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    manifest = export_public_snapshot(args.source, args.output)
    print(manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
