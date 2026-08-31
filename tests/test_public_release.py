from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts import check_public_release as checker
from scripts import export_public_snapshot as exporter
from scripts.check_public_release import ReleaseBoundaryError, check_public_release
from scripts.export_public_snapshot import MANIFEST_NAME, export_public_snapshot


def _write(path: Path, content: str = "public\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _synthetic_source(root: Path) -> Path:
    for relative in (
        "README.md",
        "LICENSE",
        "NOTICE",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "CITATION.cff",
        "LIMITATIONS.md",
        ".gitignore",
        "pyproject.toml",
        "scripts/export_public_snapshot.py",
        "scripts/check_public_release.py",
        "schemas/ProjectManifest.json",
        "src/cfdpaper/__init__.py",
        "tests/test_synthetic.py",
        ".github/workflows/ci.yml",
        "docs/ROADMAP.md",
        "docs/architecture/overview.md",
        "docs/releases/v0.2.0.md",
        "docs/releases/v0.1.0.md",
    ):
        _write(root / relative, f"content for {relative}\n")
    return root


def test_exporter_copies_only_allowlisted_files_and_writes_manifest(tmp_path: Path) -> None:
    source = _synthetic_source(tmp_path / "source")
    _write(source / "private-notes.txt", "must not leave the repository\n")
    output = tmp_path / "public"

    manifest_path = export_public_snapshot(source, output)

    assert manifest_path == output / MANIFEST_NAME
    assert not (output / "private-notes.txt").exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    paths = [item["path"] for item in manifest["files"]]
    assert paths == sorted(paths)
    assert "src/cfdpaper/__init__.py" in paths
    assert "schemas/ProjectManifest.json" in paths
    assert "scripts/check_public_release.py" in paths
    assert ".gitignore" in paths
    assert MANIFEST_NAME not in paths
    for item in manifest["files"]:
        payload = (output / item["path"]).read_bytes()
        assert item["size"] == len(payload)
        assert item["sha256"] == hashlib.sha256(payload).hexdigest()


@pytest.mark.parametrize(
    "relative",
    (
        "tests/private/case.json",
        "tests/private_manifest.json",
        "src/cfdpaper/__pycache__/module.pyc",
        "src/cfdpaper/.pytest_cache/state",
        "src/cfdpaper/.env",
        "src/cfdpaper/solver.cas.h5",
        "src/cfdpaper/solver.dat",
        "src/cfdpaper/solver.res",
        "src/cfdpaper/solver.sim",
    ),
)
def test_exporter_excludes_private_solver_environment_and_cache_files(
    tmp_path: Path, relative: str
) -> None:
    source = _synthetic_source(tmp_path / "source")
    _write(source / relative, "sensitive\n")
    output = tmp_path / "public"

    export_public_snapshot(source, output)

    assert not (output / relative).exists()


def test_exporter_rejects_allowlist_path_escape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _synthetic_source(tmp_path / "source")
    _write(tmp_path / "outside.txt")
    monkeypatch.setattr(exporter, "REQUIRED_PUBLIC_FILES", ("../outside.txt",))

    with pytest.raises(ValueError, match="allowlist path escapes"):
        export_public_snapshot(source, tmp_path / "public")


def test_exporter_rejects_output_inside_source(tmp_path: Path) -> None:
    source = _synthetic_source(tmp_path / "source")

    with pytest.raises(ValueError, match="outside the source repository"):
        export_public_snapshot(source, source / "public")


def test_exporter_rejects_symlink_input(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = _synthetic_source(tmp_path / "source")
    target = tmp_path / "outside.txt"
    _write(target)
    link = source / "src" / "linked.txt"
    try:
        link.symlink_to(target)
    except OSError:
        _write(link)
        original_is_symlink = Path.is_symlink

        def report_synthetic_link(path: Path) -> bool:
            return path == link or original_is_symlink(path)

        monkeypatch.setattr(Path, "is_symlink", report_synthetic_link)

    with pytest.raises(ValueError, match="symlink"):
        export_public_snapshot(source, tmp_path / "public")


def test_exporter_rejects_nonempty_destination_without_modifying_it(tmp_path: Path) -> None:
    source = _synthetic_source(tmp_path / "source")
    output = tmp_path / "public"
    sentinel = output / "keep.txt"
    _write(sentinel, "keep me\n")

    with pytest.raises(ValueError, match="destination must be empty"):
        export_public_snapshot(source, output)

    assert sentinel.read_text(encoding="utf-8") == "keep me\n"


def test_exporter_rejects_missing_required_file(tmp_path: Path) -> None:
    source = _synthetic_source(tmp_path / "source")
    (source / "LICENSE").unlink()

    with pytest.raises(FileNotFoundError, match="required public file is missing: LICENSE"):
        export_public_snapshot(source, tmp_path / "public")


def _tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_repeated_exports_are_byte_identical(tmp_path: Path) -> None:
    source = _synthetic_source(tmp_path / "source")
    first = tmp_path / "first"
    second = tmp_path / "second"

    first_manifest = export_public_snapshot(source, first)
    second_manifest = export_public_snapshot(source, second)

    assert first_manifest.read_bytes() == second_manifest.read_bytes()
    assert _tree_hashes(first) == _tree_hashes(second)


def _write_snapshot_manifest(root: Path) -> None:
    records = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        if path.is_file() and path.name != MANIFEST_NAME:
            payload = path.read_bytes()
            records.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "size": len(payload),
                }
            )
    _write(
        root / MANIFEST_NAME,
        json.dumps(
            {"algorithm": "sha256", "files": records, "schema_version": 1},
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )


def _valid_public_tree(root: Path) -> Path:
    valid_link = "See [" + "the guide]" + "(docs/guide.md).\n"
    _write(root / "README.md", valid_link)
    _write(root / "docs/guide.md", "Synthetic public guidance.\n")
    _write(root / "pyproject.toml", "[project]\nname = 'synthetic'\n")
    _write(root / "src/package/__init__.py", "__version__ = '0.1.0'\n")
    binary = root / "assets/logo.png"
    binary.parent.mkdir(parents=True, exist_ok=True)
    binary.write_bytes(b"\x89PNG\r\n\x1a\n\xff\x00synthetic")
    _write_snapshot_manifest(root)
    return root


def test_release_checker_accepts_valid_synthetic_tree_without_decoding_binary(
    tmp_path: Path,
) -> None:
    root = _valid_public_tree(tmp_path / "public")

    check_public_release(root)


def test_release_checker_rejects_missing_manifest(tmp_path: Path) -> None:
    root = tmp_path / "public"
    _write(root / "README.md")

    with pytest.raises(ReleaseBoundaryError, match="snapshot manifest is missing"):
        check_public_release(root)


def _tree_with_file(root: Path, relative: str, payload: str | bytes) -> Path:
    _valid_public_tree(root)
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_bytes(payload)
    _write_snapshot_manifest(root)
    return root


@pytest.mark.parametrize(
    ("relative", "reason"),
    (
        ("results/case.cas.h5", "native solver result"),
        ("results/case.dat", "native solver result"),
        ("tests/private_manifest.json", "private manifest"),
        (".env", "environment file"),
        ("config/.env.release", "environment file"),
    ),
)
def test_release_checker_rejects_forbidden_file_classes(
    tmp_path: Path, relative: str, reason: str
) -> None:
    root = _tree_with_file(tmp_path / "public", relative, b"synthetic")

    with pytest.raises(ReleaseBoundaryError, match=reason):
        check_public_release(root)


@pytest.mark.parametrize(
    ("content", "reason"),
    (
        ("local checkout: " + "C:" + "\\Users\\Synthetic\\project", "absolute user path"),
        ("local checkout: " + "/" + "home/synthetic/project", "absolute user path"),
        ("token = " + "sk-" + "a" * 32, "API key"),
        ("internal case " + "P" + "04", "private project marker"),
        ("internal gate " + "Gate" + " 5", "private project marker"),
        ("internal model " + "SG_" + "Baffle", "private project marker"),
    ),
)
def test_release_checker_rejects_text_leaks(tmp_path: Path, content: str, reason: str) -> None:
    root = _tree_with_file(tmp_path / "public", "docs/leak.md", content)

    with pytest.raises(ReleaseBoundaryError, match=reason):
        check_public_release(root)


def test_release_checker_rejects_private_project_marker_in_path(tmp_path: Path) -> None:
    relative = "tests/test_" + "sg_" + "baffle_negative.py"
    root = _tree_with_file(tmp_path / "public", relative, "synthetic public test\n")

    with pytest.raises(ReleaseBoundaryError, match="private project marker in path"):
        check_public_release(root)


def test_release_checker_rejects_oversized_binary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(checker, "MAX_BINARY_BYTES", 16)
    root = _tree_with_file(tmp_path / "public", "assets/result.bin", b"\x00" * 17)

    with pytest.raises(ReleaseBoundaryError, match="oversized binary"):
        check_public_release(root)


def test_release_checker_rejects_broken_relative_markdown_link(tmp_path: Path) -> None:
    root = _valid_public_tree(tmp_path / "public")
    broken_link = "See [" + "missing documentation]" + "(docs/missing.md).\n"
    _write(root / "README.md", broken_link)
    _write_snapshot_manifest(root)

    with pytest.raises(ReleaseBoundaryError, match="broken relative link"):
        check_public_release(root)


def test_release_checker_rejects_file_absent_from_manifest(tmp_path: Path) -> None:
    root = _valid_public_tree(tmp_path / "public")
    _write(root / "src/package/unmanifested.py")

    with pytest.raises(ReleaseBoundaryError, match="absent from snapshot manifest"):
        check_public_release(root)


def test_release_checker_ignores_git_metadata(tmp_path: Path) -> None:
    root = _valid_public_tree(tmp_path / "public")
    _write(root / ".git/config", "[core]\n\trepositoryformatversion = 0\n")

    check_public_release(root)


def test_release_checker_ignores_standard_generated_artifacts(tmp_path: Path) -> None:
    root = _valid_public_tree(tmp_path / "public")
    _write(root / ".pytest_cache/v/cache/nodeids", "[]\n")
    _write(root / "dist/package-0.1.0.whl", "generated wheel\n")
    _write(root / "src/package/__pycache__/module.cpython-312.pyc", "cache\n")
    _write(root / "src/package.egg-info/PKG-INFO", "generated metadata\n")

    check_public_release(root)


def test_release_checker_rejects_symlink_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _valid_public_tree(tmp_path / "public")
    target = tmp_path / "outside.txt"
    _write(target)
    link = root / "docs" / "linked.md"
    try:
        link.symlink_to(target)
    except OSError:
        _write(link)
        original_is_symlink = Path.is_symlink

        def report_synthetic_link(path: Path) -> bool:
            return path == link or original_is_symlink(path)

        monkeypatch.setattr(Path, "is_symlink", report_synthetic_link)
    _write_snapshot_manifest(root)

    with pytest.raises(ReleaseBoundaryError, match="symlink is forbidden"):
        check_public_release(root)
