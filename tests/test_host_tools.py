"""Task interfaces reuse public business functions; fixtures are not CFD validation."""

import json
from pathlib import Path

import pytest

from cfdpaper import host_tools
from cfdpaper.analysis_suggestions import compile_analysis
from cfdpaper.publication.table_evidence import resolve_table_result


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


@pytest.fixture
def analysis_package(tmp_path):
    source = tmp_path / "materials"
    source.mkdir()
    (source / "regions.csv").write_text(
        "case,region,area [m2],rate [W]\nA,inner,2,10\nA,outer,3,15\nB,inner,4,12\nB,outer,6,18\n",
        encoding="utf-8",
    )
    (source / "method.md").write_text(
        "Regions inner and outer are disjoint and cover the stated wall.\n"
        "area [m2] is area; rate [W] is integrated heat rate on each region.\n"
        "Cases A and B share boundary conditions; only geometry differs.\n",
        encoding="utf-8",
    )
    result = host_tools.prepare_analysis_task(
        source, tmp_path / "package", question="Rate or flux?"
    )
    package = Path(result["root"])
    proposal = read(package / "proposal-example.json")
    calculation = proposal["candidates"][0]["calculations"][0]
    calculation.update(
        domain="inner and outer wall regions, integrated rate and area",
        comparison={"status": "supported", "scope": "A and B at fixed boundary conditions"},
        missing_questions=[],
        expected_members=[["inner"], ["outer"]],
        expected_groups=["A", "B"],
    )
    proposal_path = tmp_path / "proposal.json"
    proposal_path.write_text(json.dumps(proposal), encoding="utf-8")
    return source, package, proposal_path


def test_material_inspection_keeps_sources_and_missing_definition_explicit(tmp_path):
    source = tmp_path / "materials"
    source.mkdir()
    path = source / "method.py"
    path.write_text("def mean(values):\n    return sum(values) / len(values)\n", encoding="utf-8")
    original = path.read_bytes()
    profile = host_tools.inspect_materials(source, paths=[Path("method.py")])
    assert profile["task"] == "materials-profile"
    assert profile["context"]["documents"][0]["path"] == "method.py"
    found = host_tools.inspect_materials(source, find=["def mean"])
    assert found["context"]["matches"]
    definition = host_tools.inspect_materials(
        source, paths=[Path("method.py")], definitions=["missing"]
    )
    assert definition["missing_items"] == definition["context"]["issues"]
    assert definition["missing_items"]
    assert path.read_bytes() == original


def test_analysis_prepare_keeps_long_records_in_artifacts_and_reports_missing_table(tmp_path):
    source = tmp_path / "materials"
    source.mkdir()
    original = "Observed method, not inferred. " * 500
    (source / "method.md").write_text(original, encoding="utf-8")

    result = host_tools.prepare_analysis_task(
        source, tmp_path / "package", question="Read this method"
    )
    full = read(result["artifacts"]["materials"])
    document = result["context"]["documents"][0]

    assert "excerpt" not in document
    assert document["source_record"] == {
        "path": result["artifacts"]["materials"],
        "json_pointer": "/documents/0",
    }
    assert full["documents"][0]["excerpt"]
    assert "Observed method" not in json.dumps(result)
    assert result["context"]["material_counts"]["documents"] == 1
    assert any(item["code"] == "no-analysis-table" for item in result["missing_items"])
    assert (source / "method.md").read_text(encoding="utf-8") == original


def test_analysis_prepare_retains_columns_units_and_exact_profile_location(tmp_path):
    source = tmp_path / "materials"
    source.mkdir()
    (source / "pressure.csv").write_text("case,pressure [Pa]\nA,2\nB,4\n", encoding="utf-8")

    result = host_tools.prepare_analysis_task(source, tmp_path / "package")
    table = result["context"]["tables"][0]
    full = read(result["artifacts"]["materials"])["tables"][0]

    assert table["columns"] == full["columns"]
    assert table["path"] == full["path"]
    assert table["source_record"]["json_pointer"] == "/tables/0"
    assert "preview" not in table and "preview_rows" not in table
    assert result["missing_items"] == []


def test_analysis_values_definitions_and_sources_equal_direct_business_api(
    analysis_package, tmp_path
):
    source, package, proposal = analysis_package
    before = (source / "regions.csv").read_bytes()
    direct = compile_analysis(package, proposal, "regional-transport", tmp_path / "direct")
    result = host_tools.run_analysis_task(
        package, proposal, "regional-transport", tmp_path / "host"
    )
    payload = read(direct)
    reports = read(direct.parent / "table-results.json")
    assert read(result["artifacts"]["analysis_input"]) == payload
    assert read(result["artifacts"]["table_results"]) == reports
    assert result["root"] == str((tmp_path / "host").resolve())
    assert Path(result["artifacts"]["writing_package"]).is_dir()
    assert Path(result["artifacts"]["plot_script"]).is_file()
    assert result["context"]["writing_input"]["table_calculations"] == payload["table_calculations"]
    assert result["context"]["writing_input"]["figures"]
    assert all(
        metric["result_details"]["path"]
        == str((tmp_path / "host/compiled/table-results.json").resolve())
        for metric in result["context"]["metrics"]
    )
    for figure in result["context"]["writing_input"]["figures"]:
        image = Path(result["artifacts"]["section_input"]).parent / figure["path"]
        assert all(
            image.with_suffix("." + suffix).is_file() for suffix in ("png", "svg", "pdf", "tiff")
        )
    metrics = result["context"]["metrics"]
    assert len(metrics) == len(payload["evidence"])
    for evidence in payload["evidence"]:
        expected = resolve_table_result(reports, **evidence["result_ref"])
        actual = next(metric for metric in metrics if metric["id"] == evidence["id"])
        for key in ("value", "raw_value", "unit", "source", "domain", "group", "operation"):
            if key in expected:
                assert actual["resolved"][key] == expected[key]
        assert actual["result_details"]["path"] == result["artifacts"]["table_results"]
    assert result["context"]["selected_analysis"]["interpretation_limits"]
    assert result["missing_items"] == []
    assert (source / "regions.csv").read_bytes() == before
    with pytest.raises(FileExistsError):
        host_tools.run_analysis_task(package, proposal, "regional-transport", tmp_path / "host")


def test_analysis_task_failure_does_not_publish_half_a_writing_package(
    analysis_package, tmp_path, monkeypatch
):
    from cfdpaper.publication import analysis_section

    _, package, proposal = analysis_package

    def fail(*args):
        raise RuntimeError("writing fixture failure")

    monkeypatch.setattr(analysis_section, "build_analysis_section", fail)
    output = tmp_path / "failed"
    with pytest.raises(RuntimeError, match="writing fixture failure"):
        host_tools.run_analysis_task(package, proposal, "regional-transport", output)
    assert not output.exists()


def test_analysis_cli_and_python_use_same_values_definitions_and_source_records(
    analysis_package, tmp_path
):
    from typer.testing import CliRunner

    from cfdpaper.cli import app

    source, package, proposal = analysis_package
    data = read(proposal)
    data["candidates"][0]["presentation"] = "prose"
    proposal.write_text(json.dumps(data), encoding="utf-8")
    direct = host_tools.run_analysis_task(
        package, proposal, "regional-transport", tmp_path / "python"
    )
    output = tmp_path / "cli"
    invoked = CliRunner().invoke(
        app,
        [
            "plan",
            str(source),
            "--artifact",
            "analysis",
            "--package",
            str(package),
            "--proposal",
            str(proposal),
            "--select",
            "regional-transport",
            "--output",
            str(output),
        ],
    )
    assert invoked.exit_code == 0, invoked.output
    assert read(output / "compiled/analysis-input.json") == read(
        direct["artifacts"]["analysis_input"]
    )
    assert read(output / "compiled/table-results.json") == read(
        direct["artifacts"]["table_results"]
    )


def test_manuscript_context_assembly_and_formal_export_reuse_same_values(tmp_path):
    from tests.publication.test_manuscript import fixture

    source, drafts = fixture(tmp_path)
    prepared = host_tools.manuscript_task(tmp_path / "prepared", manuscript_input=source)
    package = Path(prepared["root"])
    context = host_tools.writing_context(package, "methods", tmp_path / "context")
    assert context["context"] == read(context["artifacts"]["context"])
    built = host_tools.manuscript_task(tmp_path / "candidate", package=package, drafts=drafts)
    assert built["context"]["resolved_values"]
    exported = host_tools.manuscript_task(
        tmp_path / "manuscript.md", package=Path(built["root"]), export_format="md"
    )
    assert Path(exported["artifacts"]["manuscript"]).is_file()
    assert "2.00 K" in Path(exported["artifacts"]["manuscript"]).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({}, "Choose exactly one"),
        ({"study": Path("study"), "workspace": Path("workspace")}, "Choose exactly one"),
        ({"study": Path("study"), "baseline": Path("base")}, "baseline"),
        ({"workspace": Path("workspace"), "attach_figure": Path("figure")}, "section_id"),
        ({"workspace": Path("workspace"), "section_id": "results"}, "attachment"),
    ],
)
def test_research_invalid_combinations_fail_before_any_output(tmp_path, kwargs, message):
    output = tmp_path / "output"
    with pytest.raises(ValueError, match=message):
        host_tools.research_task(output, **kwargs)
    assert not output.exists()


def test_research_diagnostics_and_attachment_delegate_existing_public_apis(tmp_path, monkeypatch):
    from cfdpaper.publication import research_workspace

    calls = []

    def diagnostics(workspace, config, output):
        calls.append(("diagnostics", workspace, config, output))
        output.mkdir()
        return output

    def attach(workspace, figure, output, **kwargs):
        calls.append(("attach", workspace, figure, output, kwargs))
        output.mkdir()
        return output

    monkeypatch.setattr(research_workspace, "attach_research_diagnostics", diagnostics)
    monkeypatch.setattr(research_workspace, "attach_imported_figure", attach)
    workspace, config, figure = (tmp_path / name for name in ("workspace", "config", "figure"))
    host_tools.research_task(tmp_path / "diagnostic", workspace=workspace, diagnostics=config)
    host_tools.research_task(
        tmp_path / "attached",
        workspace=workspace,
        attach_figure=figure,
        section_id="results",
        evidence_ids=["existing"],
        paragraph_index=2,
        image_observation="viewed",
        observation_note="Actual host observation",
    )
    assert calls[0][0:3] == ("diagnostics", workspace, config)
    assert calls[1][-1] == {
        "section_id": "results",
        "evidence_ids": ["existing"],
        "paragraph_index": 2,
        "image_observation": "viewed",
        "observation_note": "Actual host observation",
    }


def test_author_return_summary_preserves_real_conflicts(tmp_path, monkeypatch):
    from cfdpaper.publication import author_workspace

    def import_return(author, current, output):
        assert author == tmp_path / "author.docx"
        assert current == tmp_path / "candidate"
        output.mkdir()
        (output / "merge.json").write_text(
            json.dumps({"status": "needs-resolution", "conflicts": [{"block_id": "p1"}]}),
            encoding="utf-8",
        )
        return output

    monkeypatch.setattr(author_workspace, "import_author_manuscript", import_return)
    result = host_tools.author_task(
        tmp_path / "candidate", tmp_path / "returned", return_docx=tmp_path / "author.docx"
    )
    assert result["context"]["merge"]["status"] == "needs-resolution"
    assert result["missing_items"] == [{"block_id": "p1"}]


def test_workbench_task_only_delegates_portability_actions(tmp_path, monkeypatch):
    import sys
    from types import ModuleType

    module = ModuleType("cfdpaper.workbench_portability")
    calls = []

    def export(workspace, output, **kwargs):
        calls.append(("export", workspace, output, kwargs))
        return output

    def inspect(workspace, **kwargs):
        calls.append(("inspect", workspace, kwargs))
        return {"missing": ["external source"], "question": "Current task"}

    def restore(workspace, output, **kwargs):
        calls.append(("restore", workspace, output, kwargs))
        return output

    module.export_workbench = export
    module.inspect_workbench = inspect
    module.restore_workbench = restore
    monkeypatch.setitem(sys.modules, "cfdpaper.workbench_portability", module)
    bundle, moved, output = (tmp_path / name for name in ("bundle", "moved", "output"))
    exported = host_tools.workbench_task("export", bundle, output=output, task="Compare cases")
    assert exported["root"] == str(output.resolve())
    inspected = host_tools.workbench_task("inspect", bundle)
    assert inspected["missing_items"] == ["external source"]
    host_tools.workbench_task(
        "restore", bundle, output=moved, external_roots={"native": "elsewhere"}
    )
    assert calls[-2] == ("restore", bundle, moved, {"external_roots": {"native": "elsewhere"}})
    with pytest.raises(ValueError, match="requires output"):
        host_tools.workbench_task("restore", bundle)


def test_workbench_real_round_trip_exposes_current_entries_and_exact_missing_paths(tmp_path):
    from tests.test_workbench_portability import workspace

    source = workspace(tmp_path / "current")
    # Check an execution declaration, not an arbitrary generated/record JSON.
    missing = source / "input.json"
    missing.write_text(json.dumps({"source": "not-present.csv"}), encoding="utf-8")
    exported = host_tools.workbench_task(
        "export",
        source,
        output=tmp_path / "bundle",
        task="Current comparison",
        next_action="Read the definitions",
    )
    assert exported["context"]["task"] == "Current comparison"
    assert exported["missing_items"] == exported["context"]["missing"]
    assert exported["missing_items"][0]["pointer"] == "/source"
    assert Path(exported["artifacts"]["workbench"]).is_file()
    restored = host_tools.workbench_task(
        "restore", Path(exported["root"]), output=tmp_path / "moved"
    )
    assert restored["context"]["next_action"] == "Read the definitions"
    assert (Path(restored["artifacts"]["workspace"]) / "plot.py").read_bytes() == (
        source / "plot.py"
    ).read_bytes()


def test_analysis_host_response_keeps_long_source_rows_in_located_report(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "regions.csv").write_text(
        "case,region,area [m2],rate [W]\n" + "".join(f"A,r{i},1,2\n" for i in range(100)),
        encoding="utf-8",
    )
    (source / "method.md").write_text(
        "Declared disjoint regions.\nIntegrated W and m2.\nFixed case.\n", encoding="utf-8"
    )
    package = Path(host_tools.prepare_analysis_task(source, tmp_path / "package")["root"])
    proposal = read(package / "proposal-example.json")
    proposal["candidates"][0]["calculations"][0].update(
        domain="100 disjoint regions",
        comparison={"status": "supported", "scope": "same case"},
        missing_questions=[],
        expected_members=[[f"r{i}"] for i in range(100)],
        expected_groups=["A"],
    )
    proposal_path = tmp_path / "proposal.json"
    proposal_path.write_text(json.dumps(proposal), encoding="utf-8")
    result = host_tools.run_analysis_task(
        package, proposal_path, "regional-transport", tmp_path / "run"
    )
    metrics = result["context"]["metrics"]
    assert "csv_records" not in json.dumps(metrics)
    pointer = metrics[0]["result_details"]
    report = read(pointer["path"])[int(pointer["json_pointer"].lstrip("/"))]
    assert len(report["groups"][0]["csv_records"]) == 100
