"""Registered local recipe execution; synthetic figures do not validate CFD."""

import json
import os
import py_compile
import shutil

import pytest
from PIL import Image

from cfdpaper.publication.figure_recipes import execute_figure_recipes


def test_bounded_recipe_log_keeps_failure_after_repeated_warnings():
    from cfdpaper.publication.figure_recipes import _bounded

    text = "font fallback warning\n" * 500 + "ValueError: actual rendering failure\n"
    output = _bounded(text)
    assert output.startswith("font fallback warning")
    assert output.endswith("ValueError: actual rendering failure\n")
    assert "truncated" in output
    assert len(output) <= 4020


def recipe(root, identity="one", color="purple"):
    folder = root / identity
    folder.mkdir(parents=True)
    (folder / "raw.csv").write_text("x,y\n0,2\n1,4\n", encoding="utf-8")
    (folder / "helper.py").write_text("FACTOR = 2\n", encoding="utf-8")
    (folder / "plot.py").write_text(
        "import csv, json, sys\n"
        "from pathlib import Path\n"
        "from PIL import Image, ImageDraw\n"
        "from helper import FACTOR\n"
        f"COLOR = {color!r}  # Current author's chosen style.\n"
        "ROOT = Path(__file__).resolve().parent\n"
        "with (ROOT / 'raw.csv').open(newline='') as stream:\n"
        "    rows = list(csv.DictReader(stream))\n"
        "with (ROOT / 'source.csv').open('w', newline='') as stream:\n"
        "    writer = csv.writer(stream)\n"
        "    writer.writerow(['x', 'y'])\n"
        "    writer.writerows((r['x'], float(r['y']) * FACTOR) for r in rows)\n"
        "image = Image.new('RGB', (64, 40), 'white')\n"
        "draw = ImageDraw.Draw(image)\n"
        "draw.rectangle((3, 3, 20, int(float(rows[-1]['y']) * FACTOR)), fill=COLOR)\n"
        "image.save(ROOT / 'plot.png')\n"
        "(ROOT / 'style.json').write_text(json.dumps({'color': COLOR, 'args': sys.argv[1:]}))\n"
        "print('rendered current local script')\n",
        encoding="utf-8",
    )
    return {
        "id": identity,
        "script": f"{identity}/plot.py",
        "inputs": [f"{identity}/raw.csv", f"{identity}/helper.py"],
        "outputs": [f"{identity}/source.csv", f"{identity}/plot.png", f"{identity}/style.json"],
        "section_id": "results",
        "figure_id": identity,
    }


def baseline(tmp_path, count=1):
    root = tmp_path / "baseline"
    recipes = [recipe(root, identity) for identity in ("one", "two")[:count]]
    execute_figure_recipes(root, recipes)
    (root / "figure-recipes.json").write_text(json.dumps(recipes), encoding="utf-8")
    return root, recipes


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_source_change_executes_only_related_recipe_and_preserves_author_assets(tmp_path):
    old, recipes = baseline(tmp_path, 2)
    original = snapshot(old)
    work = tmp_path / "working"
    shutil.copytree(old, work)
    (work / "one/raw.csv").write_text("x,y\n0,2\n1,8\n", encoding="utf-8")
    # An unrelated manually refined preview is not regenerated from its script.
    with Image.open(work / "two/plot.png") as image:
        image.putpixel((0, 0), (12, 34, 56))
        image.save(work / "two/plot.png")
    untouched = (work / "two/plot.png").read_bytes()
    scripts = [(work / r["script"]).read_bytes() for r in recipes]
    result = execute_figure_recipes(work, recipes, baseline_root=old)
    assert [r["status"] for r in result] == ["executed", "unchanged"]
    assert result[0]["recipe_id"] == "one"
    assert result[0]["section_id"] == "results"
    assert result[0]["stdout"].strip() == "rendered current local script"
    assert (work / "one/plot.png").read_bytes() != original["one/plot.png"]
    assert "1,16.0" in (work / "one/source.csv").read_text()
    assert (work / "two/plot.png").read_bytes() == untouched
    assert [(work / r["script"]).read_bytes() for r in recipes] == scripts
    assert snapshot(old) == original


def test_current_author_script_change_runs_verbatim_not_a_template(tmp_path):
    old, recipes = baseline(tmp_path)
    work = tmp_path / "working"
    shutil.copytree(old, work)
    script = work / recipes[0]["script"]
    script.write_text(script.read_text().replace("'purple'", "'orange'"), encoding="utf-8")
    edited = script.read_bytes()
    assert execute_figure_recipes(work, recipes, baseline_root=old)[0]["status"] == "executed"
    assert json.loads((work / "one/style.json").read_text())["color"] == "orange"
    assert script.read_bytes() == edited
    assert "'purple'" in (old / recipes[0]["script"]).read_text()


@pytest.mark.parametrize(
    "change", ["helper", "definition", "missing-output", "missing-baseline-file"]
)
def test_declared_dependencies_definition_and_outputs_trigger_execution(tmp_path, change):
    old, recipes = baseline(tmp_path)
    work = tmp_path / "working"
    shutil.copytree(old, work)
    if change == "helper":
        helper = work / "one/helper.py"
        original = helper.stat()
        py_compile.compile(str(helper), doraise=True)
        helper.write_text("FACTOR = 3\n", encoding="utf-8")
        os.utime(helper, ns=(original.st_atime_ns, original.st_mtime_ns))
    elif change == "definition":
        recipes[0]["args"] = ["literal;not-a-shell-command"]
    elif change == "missing-output":
        (work / "one/source.csv").unlink()
    else:
        (old / "one/helper.py").unlink()
    assert execute_figure_recipes(work, recipes, baseline_root=old)[0]["status"] == "executed"
    if change == "helper":
        assert "1,12.0" in (work / "one/source.csv").read_text()
    if change == "definition":
        assert json.loads((work / "one/style.json").read_text())["args"] == recipes[0]["args"]


def test_relocated_workspace_keeps_relative_recipe_and_sources(tmp_path, monkeypatch):
    old, recipes = baseline(tmp_path)
    work = tmp_path / "relocated author workspace"
    shutil.copytree(old, work)
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    monkeypatch.chdir(unrelated)
    assert execute_figure_recipes(work, recipes, baseline_root=old)[0]["status"] == "unchanged"
    (work / "one/raw.csv").write_text("x,y\n0,1\n1,6\n", encoding="utf-8")
    assert execute_figure_recipes(work, recipes, baseline_root=old)[0]["status"] == "executed"
    assert "1,12.0" in (work / "one/source.csv").read_text()


def test_script_failure_reports_diagnostic_and_does_not_return_stale_success(tmp_path):
    old, recipes = baseline(tmp_path)
    original = snapshot(old)
    work = tmp_path / "working"
    shutil.copytree(old, work)
    (work / "one/plot.py").write_text("raise RuntimeError('intentional failure')\n")
    with pytest.raises(RuntimeError, match="Figure recipe 'one' failed.*exit 1"):
        execute_figure_recipes(work, recipes, baseline_root=old)
    assert not (work / "one/plot.png").exists()
    assert snapshot(old) == original


def test_zero_exit_cannot_reuse_old_output_that_was_not_regenerated(tmp_path):
    old, recipes = baseline(tmp_path)
    work = tmp_path / "working"
    shutil.copytree(old, work)
    (work / "one/plot.py").write_text("print('no new artifacts')\n")
    with pytest.raises(ValueError, match="unusable output 'one/source.csv'"):
        execute_figure_recipes(work, recipes, baseline_root=old)
    assert not (work / "one/source.csv").exists()


def test_missing_input_is_rejected_before_existing_outputs_are_removed(tmp_path):
    old, recipes = baseline(tmp_path)
    work = tmp_path / "working"
    shutil.copytree(old, work)
    preview = (work / "one/plot.png").read_bytes()
    (work / "one/raw.csv").unlink()
    with pytest.raises(ValueError, match="Missing or out-of-package asset"):
        execute_figure_recipes(work, recipes, baseline_root=old)
    assert (work / "one/plot.png").read_bytes() == preview


@pytest.mark.parametrize("target", ["one/raw.csv", "one/plot.py", "one/helper.py"])
def test_outputs_cannot_alias_inputs_or_current_script(tmp_path, target):
    old, recipes = baseline(tmp_path)
    work = tmp_path / "working"
    shutil.copytree(old, work)
    original = snapshot(work)
    recipes[0]["outputs"].append(target)
    with pytest.raises(ValueError, match="must not alias"):
        execute_figure_recipes(work, recipes, baseline_root=old)
    assert snapshot(work) == original


@pytest.mark.parametrize("bad", ["../outside.py", "/outside.py", "C:/outside.py", "one/plot.cmd"])
def test_only_explicit_relative_python_script_is_supported(tmp_path, bad):
    root = tmp_path / "working"
    item = recipe(root)
    item["script"] = bad
    with pytest.raises(ValueError, match="relative|.py file"):
        execute_figure_recipes(root, [item])


@pytest.mark.parametrize("invalid", ["blank-preview", "header-only", "malformed-json"])
def test_declared_preview_and_source_data_must_be_usable(tmp_path, invalid):
    old, recipes = baseline(tmp_path)
    work = tmp_path / "working"
    shutil.copytree(old, work)
    if invalid == "blank-preview":
        Image.new("RGB", (64, 40), "white").save(work / "one/plot.png")
    elif invalid == "header-only":
        (work / "one/source.csv").write_text("x,y\n")
    else:
        (work / "one/style.json").write_text("not JSON")
    with pytest.raises(ValueError, match="unusable output"):
        execute_figure_recipes(work, recipes, baseline_root=old)


def test_execution_is_explicit_and_baseline_cannot_be_the_working_copy(tmp_path):
    old, recipes = baseline(tmp_path)
    original = snapshot(old)
    with pytest.raises(ValueError, match="separate existing directory"):
        execute_figure_recipes(old, recipes, baseline_root=old)
    assert snapshot(old) == original
