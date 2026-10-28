"""Explicit execution of registered author-local figure recipes in a working copy."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from cfdpaper.publication.figure_tasks import _asset, _check_preview

_REGISTRY = "figure-recipes.json"
_LOG_LIMIT = 4000
_FIELDS = {"id", "script", "inputs", "outputs", "args", "section_id", "figure_id"}


def _relative_name(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Recipe file paths must be nonblank relative strings")
    path = Path(value.replace("\\", "/"))
    if path.anchor or not path.parts or ".." in path.parts or ":" in value:
        raise ValueError(f"Recipe file path must stay relative to its workspace: {value}")
    return path.as_posix()


def _definitions(recipes):
    if not isinstance(recipes, list):
        raise ValueError("Figure recipes must be a list of recipe records")
    result, ids = [], set()
    for recipe in recipes:
        if not isinstance(recipe, dict) or recipe.keys() - _FIELDS:
            raise ValueError("Figure recipe has unknown fields or is not a record")
        if not {"id", "script", "inputs", "outputs"} <= recipe.keys():
            raise ValueError("Figure recipe requires id, script, inputs and outputs")
        identity = recipe["id"]
        if not isinstance(identity, str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_.-]*", identity
        ):
            raise ValueError("Figure recipe id must be a nonblank portable identifier")
        if identity.casefold() in ids:
            raise ValueError(f"Duplicate figure recipe id: {identity}")
        ids.add(identity.casefold())
        item = {"id": identity, "script": _relative_name(recipe["script"])}
        if Path(item["script"]).suffix.lower() != ".py":
            raise ValueError("Figure recipe script must be an explicit relative .py file")
        for field in ("inputs", "outputs"):
            if not isinstance(recipe[field], list):
                raise ValueError(f"Figure recipe {field} must be a list of relative file paths")
            item[field] = [_relative_name(value) for value in recipe[field]]
            if len({name.casefold() for name in item[field]}) != len(item[field]):
                raise ValueError(f"Duplicate figure recipe {field}")
        if not item["outputs"]:
            raise ValueError("Figure recipe must declare at least one output")
        args = recipe.get("args", [])
        if not isinstance(args, list) or any(not isinstance(value, str) for value in args):
            raise ValueError("Figure recipe args must be a list of strings")
        item["args"] = list(args)
        for field in ("section_id", "figure_id"):
            if field in recipe:
                if not isinstance(recipe[field], str) or not recipe[field].strip():
                    raise ValueError(f"Figure recipe {field} must be a nonblank string")
                item[field] = recipe[field]
        result.append(item)
    return result


def _path(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"Recipe asset resolves outside its workspace: {name}")
    return path


def _bounded(text):
    if len(text) <= _LOG_LIMIT:
        return text
    half = _LOG_LIMIT // 2
    return text[:half] + "\n[truncated]\n" + text[-half:]


def _check_output(root, name):
    path = _asset(root, name)
    suffix = path.suffix.lower()
    if suffix in {".png", ".tif", ".tiff"}:
        # Only decoding/nonblank checks are consumed here, not placement metadata.
        _check_preview(path, 160)
    elif suffix == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as stream:
            rows = csv.reader(stream, strict=True)
            header, first = next(rows, None), next(rows, None)
            if not header or not first or len(first) != len(header):
                raise ValueError(f"Generated CSV needs a header and data rows: {name}")
            if any(len(row) != len(header) for row in rows):
                raise ValueError(f"Generated CSV has inconsistent row widths: {name}")
    elif suffix == ".json":
        json.loads(path.read_text(encoding="utf-8-sig"))


def execute_figure_recipes(working_root, recipes, *, baseline_root=None, baseline_states=None):
    """Run only changed registered recipes, using the CURRENT local script verbatim.

    Paths are relative to ``working_root``; the script runs with that root as cwd.
    ``inputs`` names raw data and helpers, and ``outputs`` names generated source
    data, previews and exports. The script itself is an implicit input. Baseline
    definitions are read from its ``figure-recipes.json`` list. Missing baseline,
    changed definitions/dependency bytes, or a missing output cause execution.

    The caller supplies an isolated working copy and publishes it atomically only
    after manuscript assembly succeeds. This function is explicit trusted-code
    execution, not a sandbox; it never discovers scripts in document text and is
    not called by figure imports. It does not edit scripts or register recipes.
    """
    working_root = Path(working_root).resolve()
    baseline_root = Path(baseline_root).resolve() if baseline_root is not None else None
    if not working_root.is_dir():
        raise ValueError("Figure recipe working root must be an existing directory")
    if baseline_root is not None:
        if not baseline_root.is_dir() or baseline_root == working_root:
            raise ValueError("Figure recipe baseline must be a separate existing directory")
    definitions = _definitions(recipes)
    old = {}
    if baseline_root is not None and (baseline_root / _REGISTRY).is_file():
        old = {
            item["id"]: item
            for item in _definitions(
                json.loads((baseline_root / _REGISTRY).read_text(encoding="utf-8-sig"))
            )
        }

    # Validate the whole batch before executing or removing any generated files.
    inputs, outputs = set(), set()
    for recipe in definitions:
        for name in [recipe["script"], *recipe["inputs"]]:
            inputs.add(_asset(working_root, name))
        for name in recipe["outputs"]:
            path = _path(working_root, name)
            if path in outputs or any(str(path).casefold() == str(p).casefold() for p in outputs):
                raise ValueError(f"Figure recipes must not share an output: {name}")
            if path.exists() and not path.is_file():
                raise ValueError(f"Figure recipe output must be a file: {name}")
            outputs.add(path)
    for output in outputs:
        if any(
            str(output).casefold() == str(source).casefold()
            or (output.exists() and output.samefile(source))
            for source in inputs
        ):
            raise ValueError(f"Figure recipe output must not alias an input or script: {output}")
        if output == working_root / _REGISTRY:
            raise ValueError("Figure recipe output must not replace its registry")

    statuses = []
    saved_states = {item["recipe_id"]: item for item in (baseline_states or [])}
    for recipe in definitions:
        changed = old.get(recipe["id"]) != recipe
        current_inputs = {
            name: hashlib.sha256(_asset(working_root, name).read_bytes()).hexdigest()
            for name in dict.fromkeys([recipe["script"], *recipe["inputs"]])
        }
        saved = saved_states.get(recipe["id"], {}).get("input_fingerprints")
        if saved is not None:
            # The author may edit baseline/workspace in place after a build. Its
            # saved render inputs, rather than today's mutable files, are the baseline.
            changed = changed or saved != current_inputs
        if not changed:
            for name in [] if saved is not None else [recipe["script"], *recipe["inputs"]]:
                before = _path(baseline_root, name)
                if (
                    not before.is_file()
                    or before.read_bytes() != _asset(working_root, name).read_bytes()
                ):
                    changed = True
                    break
        changed = changed or any(
            not _path(working_root, name).is_file() for name in recipe["outputs"]
        )
        status = {
            "recipe_id": recipe["id"],
            "status": "executed" if changed else "unchanged",
            "outputs": list(recipe["outputs"]),
            "input_fingerprints": current_inputs,
            **{key: recipe[key] for key in ("section_id", "figure_id") if key in recipe},
        }
        if changed:
            # Remove only declared generated files in this isolated working copy.
            # Otherwise a successful no-op script could falsely reuse stale output.
            for name in recipe["outputs"]:
                output = _path(working_root, name)
                output.unlink(missing_ok=True)
                output.parent.mkdir(parents=True, exist_ok=True)
            # A copied timestamp-based .pyc can hide same-size helper edits.
            # Read current source without changing the author's cached files.
            with TemporaryDirectory(prefix="cfdpaper-figure-cache-") as cache:
                completed = subprocess.run(
                    [
                        sys.executable,
                        "-B",
                        "-X",
                        f"pycache_prefix={cache}",
                        str(_asset(working_root, recipe["script"])),
                        *recipe["args"],
                    ],
                    cwd=working_root,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                )
            status.update(stdout=_bounded(completed.stdout), stderr=_bounded(completed.stderr))
            if completed.returncode:
                raise RuntimeError(
                    f"Figure recipe '{recipe['id']}' failed (exit {completed.returncode}): "
                    + (status["stderr"] or status["stdout"])
                )
        for name in recipe["outputs"]:
            try:
                _check_output(working_root, name)
            except (ValueError, OSError, csv.Error) as exc:
                raise ValueError(
                    f"Figure recipe '{recipe['id']}' has unusable output '{name}': {exc}"
                ) from exc
        statuses.append(status)
    return statuses
