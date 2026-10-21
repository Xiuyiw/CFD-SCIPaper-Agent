"""Copy a selected research workspace and its author/baseline companions.

This is not a SQLite project migration. Only declared JSON file paths are
adjusted; author prose, comments, DOCX files and local scripts stay verbatim.
"""

from __future__ import annotations

import os
import platform
import re
import shutil
from copy import deepcopy
from pathlib import Path, PurePosixPath, PureWindowsPath

from cfdpaper import __version__
from cfdpaper.publication.section import _read, _stage, _write

_FORMAT = "cfdpaper-workbench"
_PATH_FIELDS = {
    "input",
    "source",
    "path",
    "script",
    "source_files",
    "inputs",
    "outputs",
    "package_path",
    "reference_source",
    "template_path",
    "case_file",
    "data_file",
    "solver_case_file",
    "solver_data_file",
    "output_dir",
    "root",
}
_TEXT_FIELDS = {
    "text",
    "title",
    "caption",
    "context",
    "description",
    "question",
    "rationale",
    "comment",
    "next_action",
    "task",
    "pointer",
    "json_pointer",
    "dataset",
}
_EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".cache",
    ".tox",
    "node_modules",
    ".cfdpaper",
    "_local_archive",
    "_archive",
    ".ssh",
    ".aws",
}
_NATIVE_SUFFIXES = (".cas", ".cas.h5", ".dat.h5", ".msh", ".msh.h5", ".mph", ".sim", ".odb")
_ENTRY_NAMES = (
    "manuscript-input.json",
    "outline.json",
    "figure-recipes.json",
    "drafts.json",
    "study.json",
    "diagnostics.json",
    "input.json",
    "analysis-input.json",
)


def _absolute(value):
    return PureWindowsPath(value).is_absolute() or PurePosixPath(value).is_absolute()


def _relative_under(value, root):
    windows = PureWindowsPath(value).is_absolute()
    cls = PureWindowsPath if windows else PurePosixPath
    if windows != PureWindowsPath(str(root)).is_absolute():
        return None
    try:
        return cls(value).relative_to(cls(str(root))).as_posix()
    except ValueError:
        return None


def _split_locator(value):
    match = re.search(r"(?:#.*|:L[1-9]\d*(?:-L?[1-9]\d*)?|;.*|:[ \t]+.*)$", value)
    return (value[: match.start()], match.group()) if match else (value, "")


def _pointer(keys):
    return "/" + "/".join(str(k).replace("~", "~0").replace("/", "~1") for k in keys)


def _references(data, *, drafts=False, keys=(), declared=False):
    if isinstance(data, dict):
        for key, value in data.items():
            if key in _TEXT_FIELDS:
                continue
            yield from _references(
                value, keys=(*keys, key), declared=key in _PATH_FIELDS or (drafts and not keys)
            )
    elif isinstance(data, list):
        for index, value in enumerate(data):
            yield from _references(value, keys=(*keys, index), declared=declared)
    elif isinstance(data, str) and data.strip():
        name, suffix = _split_locator(data)
        scheme = re.match(r"^([A-Za-z][A-Za-z0-9+.-]*):", name)
        if scheme and len(scheme.group(1)) > 1:
            return  # Semantic IDs and URIs are not files; Windows drive letters remain paths.
        if _absolute(name) or (declared and ("/" in name or "\\" in name or Path(name).suffix)):
            yield keys, data, name, suffix, declared


def _get(data, pointer):
    for key in pointer.lstrip("/").split("/"):
        key = key.replace("~1", "/").replace("~0", "~")
        data = data[int(key)] if isinstance(data, list) else data[key]
    return data


def _set(data, keys, value):
    target = data
    for key in keys[:-1]:
        target = target[key]
    target[keys[-1]] = value


def _copy_tree(source, target):
    def ignore(directory, names):
        excluded = []
        for name in names:
            path, lower = Path(directory) / name, name.casefold()
            if (
                path.is_symlink()
                or (path.is_dir() and lower in _EXCLUDED_DIRS)
                or lower in {".env", "credentials.json", "credentials.toml", "secrets.json"}
                or lower.startswith(("id_rsa", "id_ed25519"))
                or lower.endswith((".key", ".pem", *_NATIVE_SUFFIXES))
            ):
                excluded.append(name)
        return excluded

    shutil.copytree(source, target, ignore=ignore, dirs_exist_ok=True)


def _outside(output, sources):
    for source in sources:
        if output.is_relative_to(source) or source.is_relative_to(output):
            raise ValueError("Use a fresh output outside every selected source directory")


def _entries(root, manifest):
    if manifest.get("format") != _FORMAT:
        raise ValueError("Not a CFD-Paper-Agent workbench copy")
    result = {}
    for component in ("workspace", "baseline", "author"):
        name = manifest.get(component)
        if name is None and component != "workspace":
            continue
        if not isinstance(name, str) or not name or _absolute(name):
            raise ValueError("Workbench entries must stay inside the bundle")
        path = (root / name).resolve()
        if not path.is_relative_to(root) or path == root:
            raise ValueError("Workbench entries must stay inside the bundle")
        result[component] = path
    return result


def _json_documents(entries):
    """Read current executable entrypoints, never discover generated JSON recursively."""
    documents, unknown, pending = {}, [], []
    for component, directory in entries.items():
        if not directory.is_dir():
            continue
        current = directory
        if not any((current / name).is_file() for name in _ENTRY_NAMES):
            wrapper = "candidate" if component == "author" else "workspace"
            if (current / wrapper).is_dir():
                current /= wrapper
        seeds = [current / name for name in _ENTRY_NAMES if (current / name).is_file()]
        if not seeds and not (
            component == "author"
            and any(
                (directory / name).is_file()
                for name in (
                    "author-edits.json",
                    "author-return.json",
                    "author-original.docx",
                    "manuscript.docx",
                )
            )
        ):
            unknown.append(directory)
        pending.extend(seeds)
    while pending:
        path = pending.pop(0).resolve()
        if path in documents or not path.is_file():
            continue
        if not any(path.is_relative_to(directory) for directory in entries.values()):
            continue  # An external section remains an explicit missing/relocatable reference.
        data = documents[path] = _read(path)
        sections = data.get("sections", []) if isinstance(data, dict) else []
        for section in sections:
            if isinstance(section, dict) and isinstance(section.get("input"), str):
                target = (path.parent / section["input"]).resolve()
                pending.append(target)
                pending.extend(target.parent / name for name in ("study.json", "diagnostics.json"))
        if path.name == "drafts.json" and isinstance(data, dict):
            for name in data.values():
                if isinstance(name, str):
                    section_dir = (path.parent / name).resolve().parent
                    pending.extend(
                        section_dir / entry
                        for entry in ("input.json", "study.json", "diagnostics.json")
                    )
    return documents, unknown


def _reference_directory(data, keys, directory):
    if len(keys) >= 2 and keys[-2:] == ("field_options", "reference_source"):
        calculation = data
        for key in keys[:-2]:
            calculation = calculation[key]
        source, _ = _split_locator(calculation["source"])
        return (directory / source).resolve().parent
    return directory


def _copied_location(original, sources, staged):
    for owner, old_root in sorted(sources.items(), key=lambda p: len(str(p[1])), reverse=True):
        relative = _relative_under(str(original), old_root)
        if relative is not None:
            return staged / owner / relative
    return None


def _mapped_external(name, external_roots):
    for old, new in sorted(
        (external_roots or {}).items(), key=lambda p: len(str(p[0])), reverse=True
    ):
        if not _absolute(str(old)) or not _absolute(str(new)):
            raise ValueError("External root mappings must use explicit absolute roots")
        relative = _relative_under(name, old)
        if relative is not None:
            return str(Path(new) / relative)
    return name


def export_workbench(
    workspace_dir: Path,
    output_dir: Path,
    *,
    baseline_dir=None,
    author_dir=None,
    task=None,
    next_action=None,
) -> Path:
    """Export selected current files, without running recipes or touching inputs."""
    sources = {"workspace": Path(workspace_dir).expanduser().resolve()}
    for name, value in (("baseline", baseline_dir), ("author", author_dir)):
        if value is not None:
            sources[name] = Path(value).expanduser().resolve()
    if any(not path.is_dir() for path in sources.values()):
        raise ValueError("Every selected workbench component must be an existing directory")
    output = Path(output_dir).expanduser().resolve()
    _outside(output, sources.values())
    with _stage(output) as staged:
        for component, source in sources.items():
            _copy_tree(source, staged / component)
        external = []
        documents, _unknown = _json_documents(sources)
        for original_json, original_data in documents.items():
            path = _copied_location(original_json, sources, staged)
            data, changed = deepcopy(original_data), False
            for keys, value, name, suffix, declared in _references(
                original_data, drafts=path.name == "drafts.json"
            ):
                if not declared:
                    continue
                original_base = _reference_directory(original_data, keys, original_json.parent)
                original = name if _absolute(name) else str((original_base / name).resolve())
                copied = _copied_location(original, sources, staged)
                copied_base = _copied_location(original_base, sources, staged)
                if (
                    copied is not None
                    and (copied.exists() or "outputs" in keys or "output_dir" in keys)
                    and copied_base is not None
                ):
                    replacement = Path(os.path.relpath(copied, copied_base)).as_posix() + suffix
                    if replacement != value:
                        _set(data, keys, replacement)
                        changed = True
                elif _absolute(name) or copied is None or Path(original).exists():
                    external.append(
                        {
                            "file": path.relative_to(staged).as_posix(),
                            "pointer": _pointer(keys),
                            "original": original,
                            "value": value,
                        }
                    )
            if changed:
                _write(path, data)
        manifest = {
            "format": _FORMAT,
            "workspace": "workspace",
            "baseline": "baseline" if "baseline" in sources else None,
            "author": "author" if "author" in sources else None,
            "task": task or "Continue the current declared research task.",
            "next_action": next_action
            or "Read the current workspace context and resolve its open questions.",
            "external_sources": external,
            "environment": {"cfd-paper-agent": __version__, "python": platform.python_version()},
            "project_state": "not-included",
        }
        _write(staged / "workbench.json", manifest)
        (staged / "TASK.md").write_text(
            f"# Current research task\n\n{manifest['task']}\n\n"
            "Current scientific workspace: workspace/. Read its existing research/material and "
            "manuscript context; source definitions remain authoritative. Selected baseline and "
            "author companions, when present, are listed in workbench.json.\n",
            encoding="utf-8",
        )
        (staged / "CONTINUE.md").write_text(
            f"# Continue here\n\n{manifest['next_action']}\n\n"
            "Start with TASK.md and inspect_workbench(bundle_dir). Use workspace/ as the current "
            "science input and the explicitly selected baseline/author paths for continuation. "
            "Keep author scripts and edits. Restore external sources only by an explicit old-root "
            "to new-root mapping; do not search for same-name files. restore_workbench writes a "
            "new copy. This bundle excludes SQLite project state, environments, caches, "
            "credentials and native solver files. Install a non-editable package in the "
            "destination environment. Package/Python versions are recorded, not a test of "
            "fonts, renderers or solver availability.\n",
            encoding="utf-8",
        )
    return output


def inspect_workbench(bundle_dir: Path, *, external_roots=None) -> dict:
    """Read current entry points and exact missing references; never search disks."""
    root = Path(bundle_dir).expanduser().resolve()
    manifest = _read(root / "workbench.json")
    entries = _entries(root, manifest)
    missing, unresolved, external = [], [], []
    declared_external = {
        (item["file"], item["pointer"]): item for item in manifest.get("external_sources", [])
    }
    for name, path in entries.items():
        if not path.is_dir():
            missing.append({"file": manifest[name], "pointer": "", "path": str(path)})
    documents, unknown = _json_documents(entries)
    unresolved.extend(
        {
            "file": path.relative_to(root).as_posix(),
            "pointer": "",
            "code": "unknown-entrypoint",
            "message": "No known execution entrypoint; arbitrary JSON was not inspected.",
        }
        for path in unknown
    )
    for path, data in documents.items():
        filename = path.relative_to(root).as_posix()
        for keys, value, name, _suffix, declared in _references(
            data, drafts=path.name == "drafts.json"
        ):
            record = {"file": filename, "pointer": _pointer(keys)}
            if not declared:
                unresolved.append({**record, "value": value})
                continue
            selected = declared_external.get((filename, record["pointer"]))
            external_reference = bool(selected) or _absolute(name)
            if selected and selected["value"] == value:
                original = selected["original"]
                resolved = _mapped_external(original, external_roots)
                external.append(
                    {
                        **record,
                        "original": original,
                        "path": resolved,
                        "available": Path(resolved).is_file(),
                    }
                )
            elif _absolute(name):
                resolved = _mapped_external(name, external_roots)
                external.append(
                    {
                        **record,
                        "original": name,
                        "path": resolved,
                        "available": Path(resolved).is_file(),
                    }
                )
            else:
                base = _reference_directory(data, keys, path.parent)
                resolved = str((base / name).resolve())
            available = Path(resolved).is_file() if external_reference else Path(resolved).exists()
            if "outputs" not in keys and "output_dir" not in keys and not available:
                missing.append({**record, "path": resolved})
    return {
        "bundle": str(root),
        **{key: str(value) for key, value in entries.items()},
        "task": manifest.get("task"),
        "next_action": manifest.get("next_action"),
        "environment": manifest.get("environment", {}),
        "project_state": "not-included",
        "external_sources": external,
        "missing": missing,
        "unresolved_paths": unresolved,
        "checked_declarations": [path.relative_to(root).as_posix() for path in documents],
        "status": "needs-attention" if missing or unresolved else "ready",
    }


def restore_workbench(bundle_dir: Path, output_dir: Path, *, external_roots=None) -> Path:
    """Restore to a new directory and precisely relocate declared external roots."""
    root, output = Path(bundle_dir).expanduser().resolve(), Path(output_dir).expanduser().resolve()
    manifest = _read(root / "workbench.json")
    _entries(root, manifest)
    _outside(output, [root])
    with _stage(output) as staged:
        _copy_tree(root, staged)
        for item in manifest.get("external_sources", []):
            path = (staged / item["file"]).resolve()
            if not path.is_relative_to(staged):
                raise ValueError("External source declarations must stay inside the bundle")
            data = _read(path)
            if _get(data, item["pointer"]) != item["value"]:
                continue  # A subsequent author path edit is not overwritten.
            relocated = _mapped_external(item["original"], external_roots)
            if relocated == item["original"]:
                continue
            _, suffix = _split_locator(item["value"])
            replacement = relocated + suffix
            keys = tuple(
                key.replace("~1", "/").replace("~0", "~")
                for key in item["pointer"].lstrip("/").split("/")
            )
            # Convert list indices without changing dictionary keys that look numeric.
            target = data
            for key in keys[:-1]:
                target = target[int(key)] if isinstance(target, list) else target[key]
            key = int(keys[-1]) if isinstance(target, list) else keys[-1]
            target[key] = replacement
            _write(path, data)
            item.update(original=relocated, value=replacement)
        _write(staged / "workbench.json", manifest)
    return output
