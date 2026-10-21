"""Portable copies preserve the author's files; no solver or Word replay is needed."""

import json
import shutil

import numpy as np
import pytest

from cfdpaper.publication.table_evidence import calculate_declared_table
from cfdpaper.workbench_portability import (
    export_workbench,
    inspect_workbench,
    restore_workbench,
)


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def workspace(root):
    root.mkdir()
    (root / "data.csv").write_text("case,value\nA,3\n", encoding="utf-8")
    (root / "plot.py").write_text("# Author's precise visual choices.\n", encoding="utf-8")
    write(root / "draft.json", {"text": "Author wording and {{value:temperature}}."})
    write(root / "input.json", {"source": str(root / "data.csv")})
    write(root / "drafts.json", {"results": "draft.json"})
    write(
        root / "outline.json",
        {"sections": [{"input": str(root / "input.json")}], "source": str(root / "data.csv")},
    )
    write(root / "figure-recipes.json", [{"script": "plot.py", "inputs": ["data.csv"]}])
    return root


def test_export_relocates_declarations_and_preserves_authors_and_sources(tmp_path):
    source = workspace(tmp_path / "current")
    baseline, author = tmp_path / "baseline", tmp_path / "author"
    baseline.mkdir()
    author.mkdir()
    write(baseline / "outline.json", {"source": str(source / "data.csv")})
    write(author / "author-edits.json", {"comments": [{"text": "Keep this qualification."}]})
    (author / "author-original.docx").write_bytes(b"unchanged original and comments")
    write(
        source / "draft.json",
        {"text": str(source / "data.csv"), "unknown_asset": str(source / "plot.py")},
    )
    write(source / "input.json", {"unknown_asset": str(source / "plot.py")})
    before = {p.relative_to(source): p.read_bytes() for p in source.rglob("*") if p.is_file()}

    bundle = export_workbench(
        source,
        tmp_path / "bundle",
        baseline_dir=baseline,
        author_dir=author,
        task="Compare the declared observations.",
        next_action="Check the sign convention.",
    )

    assert bundle == tmp_path / "bundle"
    assert read(bundle / "workspace/outline.json")["source"] == "data.csv"
    assert read(bundle / "workspace/outline.json")["sections"][0]["input"] == "input.json"
    assert read(bundle / "baseline/outline.json")["source"] == "../workspace/data.csv"
    assert read(bundle / "workspace/draft.json") == read(source / "draft.json")
    assert (bundle / "workspace/plot.py").read_bytes() == (source / "plot.py").read_bytes()
    assert (bundle / "author/author-original.docx").read_bytes() == (
        author / "author-original.docx"
    ).read_bytes()
    assert read(bundle / "author/author-edits.json") == read(author / "author-edits.json")
    assert "Compare the declared observations." in (bundle / "TASK.md").read_text(encoding="utf-8")
    assert "Check the sign convention." in (bundle / "CONTINUE.md").read_text(encoding="utf-8")
    assert before == {
        p.relative_to(source): p.read_bytes() for p in source.rglob("*") if p.is_file()
    }
    status = inspect_workbench(bundle)
    assert status["workspace"] == str(bundle / "workspace")
    assert status["baseline"] == str(bundle / "baseline")
    assert status["author"] == str(bundle / "author")
    assert status["unresolved_paths"][0]["pointer"] == "/unknown_asset"


def test_copy_is_usable_after_source_and_bundle_move(tmp_path):
    source = workspace(tmp_path / "current")
    bundle = export_workbench(source, tmp_path / "bundle")
    shutil.rmtree(source)
    moved = tmp_path / "other-directory/moved"
    moved.parent.mkdir()
    shutil.move(bundle, moved)
    state = inspect_workbench(moved)
    assert state["missing"] == []
    outline = moved / "workspace/outline.json"
    data = read(outline)
    assert (outline.parent / data["sections"][0]["input"]).is_file()
    assert (outline.parent / data["source"]).read_text(encoding="utf-8").endswith("A,3\n")


def test_external_roots_are_exact_explicit_and_restored_only_in_a_new_copy(tmp_path):
    source = workspace(tmp_path / "current")
    old_root = tmp_path / "original-native"
    old_root.mkdir()
    (old_root / "saved.cas.h5").write_bytes(b"native read-only")
    write(source / "input.json", {"source": str(old_root / "saved.cas.h5")})
    bundle = export_workbench(source, tmp_path / "bundle")
    new_root = tmp_path / "new-native"
    shutil.move(old_root, new_root)
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    (unrelated / "saved.cas.h5").write_bytes(b"wrong same-name file")
    assert len(inspect_workbench(bundle)["missing"]) == 1
    remap = {str(old_root): new_root}
    assert inspect_workbench(bundle, external_roots=remap)["missing"] == []
    original = (bundle / "workspace/input.json").read_bytes()

    restored = restore_workbench(bundle, tmp_path / "restored", external_roots=remap)

    assert read(restored / "workspace/input.json")["source"] == str(new_root / "saved.cas.h5")
    assert inspect_workbench(restored)["missing"] == []
    assert (bundle / "workspace/input.json").read_bytes() == original
    assert (new_root / "saved.cas.h5").read_bytes() == b"native read-only"
    assert not (restored / "workspace/saved.cas.h5").exists()


def test_excludes_environment_secrets_history_and_native_files(tmp_path):
    source = workspace(tmp_path / "current")
    for name in (
        ".venv/bin/python",
        ".git/config",
        "__pycache__/old.pyc",
        ".cfdpaper/project.db",
        "_local_archive/old.md",
    ):
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"excluded")
    for name in (".env", "credentials.json", "private.key", "saved.cas.h5"):
        (source / name).write_bytes(b"excluded")
    write(source / "input.json", {"source": "saved.cas.h5"})

    bundle = export_workbench(source, tmp_path / "bundle")

    assert sorted(p.name for p in (bundle / "workspace").iterdir()) == [
        "data.csv",
        "draft.json",
        "drafts.json",
        "figure-recipes.json",
        "input.json",
        "outline.json",
        "plot.py",
    ]
    state = inspect_workbench(bundle)
    assert state["external_sources"][0]["original"] == str(source / "saved.cas.h5")
    assert state["project_state"] == "not-included"


def test_unmapped_unknown_absolute_path_is_reported_not_rewritten(tmp_path):
    source = workspace(tmp_path / "current")
    write(source / "input.json", {"custom_loader": "/machine/not-present/data.csv"})
    bundle = export_workbench(source, tmp_path / "bundle")
    assert read(bundle / "workspace/input.json")["custom_loader"] == "/machine/not-present/data.csv"
    issue = inspect_workbench(bundle)["unresolved_paths"][0]
    assert issue["file"] == "workspace/input.json"
    assert issue["pointer"] == "/custom_loader"


def test_generated_identity_snapshots_and_skill_examples_are_not_path_declarations(tmp_path):
    source = workspace(tmp_path / "current")
    snapshots = {
        "writing-state.json": {"source": str(source / "data.csv"), "pointer": "/blocks/1"},
        "section.json": {"evidence": [{"source": "report.csv; other.csv"}]},
        "author-edits.json": {"comments": [{"text": "Preserve this.", "path": "/blocks/1"}]},
        "skills/example/input.json": {"input": "/an/example/not-the-current-task.json"},
    }
    for name, data in snapshots.items():
        write(source / name, data)
    bundle = export_workbench(source, tmp_path / "bundle")
    for name in snapshots:
        assert (bundle / "workspace" / name).read_bytes() == (source / name).read_bytes()
    assert inspect_workbench(bundle)["missing"] == []
    assert inspect_workbench(bundle)["unresolved_paths"] == []


def test_external_reference_needs_a_file_not_a_same_name_directory(tmp_path):
    source = workspace(tmp_path / "current")
    external = tmp_path / "external"
    external.mkdir()
    (external / "saved.cas.h5").mkdir()
    write(source / "input.json", {"source": str(external / "saved.cas.h5")})
    bundle = export_workbench(source, tmp_path / "bundle")
    state = inspect_workbench(bundle)
    assert not state["external_sources"][0]["available"]
    assert len(state["missing"]) == 1


@pytest.mark.parametrize("selector", ["; case=A; value", ": case A"])
def test_evidence_selectors_and_hdf_dataset_locators_are_not_missing_files(tmp_path, selector):
    source = workspace(tmp_path / "current")
    write(
        source / "input.json",
        {"evidence": [{"source": str(source / "data.csv") + selector}]},
    )
    write(source / "geometry.json", {"dataset": "/meshes/1/nodes/coords/40"})
    bundle = export_workbench(source, tmp_path / "bundle")
    assert read(bundle / "workspace/input.json")["evidence"][0]["source"] == "data.csv" + selector
    state = inspect_workbench(bundle)
    assert state["missing"] == []
    assert state["unresolved_paths"] == []


def test_raw_material_records_are_not_executable_path_declarations(tmp_path):
    source = workspace(tmp_path / "current")
    records = {
        "materials/Q3p73-conditions.json": {
            "source_case": "D:/old-native/completed.cas.h5",
            "source_data": "D:/old-native/completed.dat.h5",
            "setup_differences": [
                {"path": "/boundary_conditions/inlet/mass_flow", "old": 1, "new": 2}
            ],
        },
        "materials/native_zone_volumes.json": {
            "source": "solver.trn native check_oil_volume report after completed extraction"
        },
        "sources/retained-metadata.json": {"path": "/boundary_conditions/outlet/pressure"},
    }
    for name, data in records.items():
        write(source / name, data)
    write(
        source / "input.json",
        {"source_files": list(records), "source": "materials/Q3p73-conditions.json"},
    )

    bundle = export_workbench(source, tmp_path / "bundle")

    for name in records:
        assert (bundle / "workspace" / name).read_bytes() == (source / name).read_bytes()
    state = inspect_workbench(bundle)
    assert state["missing"] == []
    assert state["unresolved_paths"] == []
    assert state["external_sources"] == []
    (bundle / "workspace/materials/Q3p73-conditions.json").unlink()
    assert inspect_workbench(bundle)["missing"]  # The actual input reference is still checked.


def test_namespaced_evidence_and_uris_are_not_files_but_file_sources_still_are(tmp_path):
    source = workspace(tmp_path / "current")
    references = [
        "manuscript:results/temperature-area-mean",
        "https://example.org/methods/source.csv",
        "doi:10.1234/physical.method",
        "urn:research:evidence:temperature",
    ]
    write(
        source / "input.json",
        {"evidence": [{"source": value} for value in [*references, "missing.csv"]]},
    )

    bundle = export_workbench(source, tmp_path / "bundle")
    state = inspect_workbench(bundle)

    assert read(bundle / "workspace/input.json") == read(source / "input.json")
    assert len(state["missing"]) == 1
    assert state["missing"][0]["pointer"] == "/evidence/4/source"
    assert state["missing"][0]["path"].endswith("missing.csv")
    assert state["external_sources"] == []
    assert state["unresolved_paths"] == []


def test_only_current_declared_sections_are_read_not_historical_generated_json(tmp_path):
    source = workspace(tmp_path / "current")
    baseline = tmp_path / "build"
    baseline.mkdir()
    workspace(baseline / "workspace")
    write(
        source / "sections/results/input.json",
        {"source": "sources/value.csv"},
    )
    (source / "sections/results/sources").mkdir()
    (source / "sections/results/sources/value.csv").write_text("value\n3\n")
    write(
        source / "manuscript-input.json", {"sections": [{"input": "sections/results/input.json"}]}
    )
    for name in (
        "changes.json",
        "sections/results/review-packet/bound-evidence.json",
        "historical/output/input.json",
        "unrelated.json",
    ):
        write(source / name, {"source": str(source / "not-an-execution-dependency.csv")})
    write(baseline / "manuscript/changes.json", {"path": "missing-rendered-figure.png"})

    bundle = export_workbench(source, tmp_path / "bundle", baseline_dir=baseline)
    state = inspect_workbench(bundle)

    assert state["missing"] == []
    assert state["unresolved_paths"] == []
    assert "workspace/sections/results/input.json" in state["checked_declarations"]
    assert not any(
        "review-packet" in name or "historical" in name or "changes.json" in name
        for name in state["checked_declarations"]
    )
    assert read(bundle / "workspace/unrelated.json") == read(source / "unrelated.json")


@pytest.mark.parametrize("absolute_source", [False, True])
def test_reference_source_uses_calculation_source_directory_like_table_consumer(
    tmp_path, absolute_source
):
    source = workspace(tmp_path / "current")
    arrays = source / "sources"
    arrays.mkdir()
    np.savez(arrays / "new.npz", t=[320.0], x=[0.0], y=[0.0], z=[0.0])
    np.savez(arrays / "old.npz", t=[300.0], x=[0.0], y=[0.0], z=[0.0])
    calculation = {
        "id": "difference",
        "source": str(arrays / "new.npz") if absolute_source else "sources/new.npz",
        "operation": "field_difference",
        "domain": "one retained point",
        "columns": {"value": "t", "x": "x", "y": "y", "z": "z"},
        "units": {"value": "K", "x": "m", "y": "m", "z": "m"},
        "field_options": {"association": "point", "reference_source": "old.npz"},
    }
    write(source / "input.json", {"table_calculations": [calculation]})
    expected = calculate_declared_table(arrays / "new.npz", calculation)

    bundle = export_workbench(source, tmp_path / "bundle")
    copied = read(bundle / "workspace/input.json")["table_calculations"][0]

    assert copied["source"] == "sources/new.npz"
    assert copied["field_options"]["reference_source"] == "old.npz"
    assert inspect_workbench(bundle)["missing"] == []
    actual = calculate_declared_table(bundle / "workspace" / copied["source"], copied)
    assert actual["groups"] == expected["groups"]
    assert actual["result_units"] == expected["result_units"]


def test_unknown_workspace_entry_is_reported_without_reading_arbitrary_json(tmp_path):
    source = tmp_path / "unknown"
    source.mkdir()
    write(source / "custom.json", {"source": "/do/not/follow/this.csv"})
    bundle = export_workbench(source, tmp_path / "bundle")
    state = inspect_workbench(bundle)
    assert state["checked_declarations"] == []
    assert state["unresolved_paths"][0]["code"] == "unknown-entrypoint"


def test_export_does_not_follow_symlinks(tmp_path):
    source = workspace(tmp_path / "current")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_bytes(b"not selected")
    try:
        (source / "linked").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Creating symlinks requires permission on this platform")
    bundle = export_workbench(source, tmp_path / "bundle")
    assert not (bundle / "workspace/linked").exists()


@pytest.mark.parametrize("operation", ["export", "restore"])
def test_never_overwrites_or_nests_inside_an_input(tmp_path, operation):
    source = workspace(tmp_path / "current")
    if operation == "restore":
        source = export_workbench(source, tmp_path / "bundle")
    function = export_workbench if operation == "export" else restore_workbench
    with pytest.raises(ValueError, match="outside"):
        function(source, source / "nested")
    output = tmp_path / "existing"
    output.mkdir()
    (output / "author.txt").write_bytes(b"keep")
    with pytest.raises(FileExistsError):
        function(source, output)
    assert (output / "author.txt").read_bytes() == b"keep"


def test_inspect_rejects_manifest_entries_outside_bundle(tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    write(bundle / "workbench.json", {"format": "cfdpaper-workbench", "workspace": "../outside"})
    with pytest.raises(ValueError, match="inside"):
        inspect_workbench(bundle)
