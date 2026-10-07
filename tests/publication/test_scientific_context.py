"""Synthetic source relationships test location/scope, not physical truth."""

import copy
import json
import shutil

import pytest

from cfdpaper.publication.scientific_context import (
    copy_scientific_context,
    load_scientific_context,
    read_source_parameters,
    render_scientific_context,
    select_scientific_context,
)


def fixture(tmp_path):
    (tmp_path / "methods.md").write_bytes(
        b"Synthetic methods\r\nA: final steady stage; solver version 1.\r\n"
        b"B: report uses the outlet mass-weighted total pressure.\r\n"
        b"B: earlier report uses the outlet area-weighted static pressure.\r\n"
    )
    data = {
        "cases": [{"id": "A", "name": "Control"}, {"id": "B"}],
        "facts": [
            {
                "id": "A-stage",
                "case_ids": ["A"],
                "section_ids": ["methods"],
                "kind": "solver-setting",
                "name": "Recorded version and stage",
                "text": "Version 1 is recorded only for A's final steady stage.",
                "stage": "final steady stage",
                "source": {
                    "path": "methods.md",
                    "locator": "L2-L2",
                    "excerpt": "A: final steady stage; solver version 1.",
                },
            },
            {
                "id": "B-operator",
                "case_ids": ["B"],
                "section_ids": ["results"],
                "kind": "report-definition",
                "name": "Outlet report",
                "text": "B uses mass-weighted total pressure at the outlet.",
                "domain": "outlet",
                "operator": "mass-weighted total pressure",
                "source": {
                    "path": "methods.md",
                    "locator": "L3",
                    "excerpt": "B: report uses the outlet mass-weighted total pressure.",
                },
            },
        ],
        "comparisons": [
            {
                "id": "A-B",
                "case_ids": ["A", "B"],
                "section_ids": ["discussion"],
                "fact_ids": ["A-stage", "B-operator"],
                "text": "The supplied records address different aspects of these cases.",
                "status": "unknown",
            }
        ],
        "note": "Keep host interpretation separate from exact source checks.",
    }
    return data


def save(tmp_path, data):
    path = tmp_path / "scientific.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def test_exact_source_case_stage_operator_and_read_only(tmp_path):
    data = fixture(tmp_path)
    path = save(tmp_path, data)
    original = path.read_bytes(), (tmp_path / "methods.md").read_bytes()
    loaded = load_scientific_context(path, ["methods", "results", "discussion"])
    assert loaded["facts"][0]["source"]["path"] == "methods.md"
    assert loaded["facts"][0]["stage"] == "final steady stage"
    assert loaded["facts"][0]["case_ids"] == ["A"]
    assert "stage" not in loaded["facts"][1]
    assert loaded["facts"][1]["operator"] == "mass-weighted total pressure"
    assert loaded["note"] == data["note"]
    assert original == (path.read_bytes(), (tmp_path / "methods.md").read_bytes())


@pytest.mark.parametrize(
    ("locator", "excerpt", "message"),
    [
        ("L3", "A: final steady stage; solver version 1.", "does not match exact lines"),
        ("L2-L3", "A: final steady stage; solver version 1.", "does not match exact lines"),
        ("L2", "A: final steady stage; solver version 1", "does not match exact lines"),
        ("L0", "x", "source.locator"),
        ("line:2", "x", "source.locator"),
        ("L3-L2", "x", "out of bounds"),
        ("L2-L999", "x", "out of bounds"),
    ],
)
def test_excerpt_must_match_declared_line_range(tmp_path, locator, excerpt, message):
    data = fixture(tmp_path)
    data["facts"][0]["source"].update(locator=locator, excerpt=excerpt)
    with pytest.raises(ValueError, match=message):
        load_scientific_context(save(tmp_path, data))


def test_multiline_excerpt_preserves_whitespace(tmp_path):
    data = fixture(tmp_path)
    data["facts"][0]["source"].update(
        locator="L1-L2", excerpt="Synthetic methods\r\nA: final steady stage; solver version 1."
    )
    assert load_scientific_context(save(tmp_path, data))["facts"][0]["source"]["locator"] == "L1-L2"
    data["facts"][0]["source"]["excerpt"] = (
        "Synthetic methods\n A: final steady stage; solver version 1."
    )
    with pytest.raises(ValueError, match="exact lines"):
        load_scientific_context(save(tmp_path, data))


@pytest.mark.parametrize("suffix", [".txt", ".md", ".json", ".csv", ".py"])
def test_supported_sources_are_only_read_as_text(tmp_path, suffix):
    data = fixture(tmp_path)
    source = tmp_path / ("source" + suffix)
    source.write_text("raise RuntimeError('this source must never execute')", encoding="utf-8")
    data["facts"][0]["source"].update(
        path=source.name, locator="L1", excerpt=source.read_text(encoding="utf-8")
    )
    loaded = load_scientific_context(save(tmp_path, data))
    assert "RuntimeError" in loaded["facts"][0]["source"]["excerpt"]


@pytest.mark.parametrize("bad_path", ["../methods.md", "C:/methods.md", "/methods.md"])
def test_input_paths_follow_existing_local_source_rules(tmp_path, bad_path):
    data = fixture(tmp_path)
    data["facts"][0]["source"]["path"] = bad_path
    with pytest.raises(ValueError, match="relative path"):
        load_scientific_context(save(tmp_path, data))


def test_missing_source_unsupported_source_and_non_utf8(tmp_path):
    data = fixture(tmp_path)
    source = data["facts"][0]["source"]
    source["path"] = "missing.md"
    with pytest.raises(ValueError, match="file not found"):
        load_scientific_context(save(tmp_path, data))
    (tmp_path / "case.cas").write_bytes(b"binary")
    source["path"] = "case.cas"
    with pytest.raises(ValueError, match="UTF-8 text"):
        load_scientific_context(save(tmp_path, data))
    (tmp_path / "bad.txt").write_bytes(b"\xff\xfe")
    source["path"] = "bad.txt"
    with pytest.raises(ValueError, match="not UTF-8"):
        load_scientific_context(save(tmp_path, data))


def test_section_selection_retains_comparison_dependencies_without_widening(tmp_path):
    loaded = load_scientific_context(save(tmp_path, fixture(tmp_path)))
    before = copy.deepcopy(loaded)
    methods = select_scientific_context(loaded, ["methods"])
    assert [fact["id"] for fact in methods["facts"]] == ["A-stage"]
    assert methods["comparisons"] == []
    assert [case["id"] for case in methods["cases"]] == ["A"]
    discussion = select_scientific_context(loaded, ["discussion"])
    assert len(discussion["facts"]) == 2
    assert discussion["facts"][0]["section_ids"] == ["methods"]
    assert discussion["facts"][0]["case_ids"] == ["A"]
    assert discussion["comparisons"][0]["status"] == "unknown"
    assert select_scientific_context(loaded, ["intro"])["facts"] == []
    assert loaded == before


def test_copy_relocate_and_reload_preserves_bytes_and_originals(tmp_path):
    source_dir = tmp_path / "original"
    source_dir.mkdir()
    path = save(source_dir, fixture(source_dir))
    original_json = path.read_bytes()
    original_source = (source_dir / "methods.md").read_bytes()
    output = tmp_path / "package"
    copied = copy_scientific_context(path, output)
    assert not copied["facts"][0]["source"]["path"].startswith(str(tmp_path))
    assert copied["facts"][0]["source"]["path"] == copied["facts"][1]["source"]["path"]
    assert len(list((output / "sources").iterdir())) == 1
    assert (output / copied["facts"][0]["source"]["path"]).read_bytes() == original_source
    assert path.read_bytes() == original_json
    assert (source_dir / "methods.md").read_bytes() == original_source
    relocated = tmp_path / "moved" / "package"
    relocated.parent.mkdir()
    shutil.move(output, relocated)
    # No original files remain available to the relocated loader.
    path.unlink()
    (source_dir / "methods.md").unlink()
    loaded = load_scientific_context(relocated / "context.json")
    assert loaded["facts"][0]["source"]["path"] == copied["facts"][0]["source"]["path"]
    text = render_scientific_context(select_scientific_context(loaded, ["discussion"]))
    assert "cases: A; sections: methods" in text
    assert "stage: final steady stage" in text
    assert "operator: mass-weighted total pressure" in text
    assert "L2-L2" in text and "A-B [unknown]" in text


def test_copy_rejects_existing_output_without_overwriting(tmp_path):
    path = save(tmp_path, fixture(tmp_path))
    output = tmp_path / "package"
    output.mkdir()
    sentinel = output / "context.json"
    sentinel.write_text("author edits", encoding="utf-8")
    with pytest.raises(ValueError, match="already exists"):
        copy_scientific_context(path, output)
    assert sentinel.read_text(encoding="utf-8") == "author edits"


def test_copy_selected_sections_only_carries_referenced_sources(tmp_path):
    data = fixture(tmp_path)
    (tmp_path / "stage.txt").write_text("A's separately recorded stage.", encoding="utf-8")
    data["facts"][0]["source"].update(
        path="stage.txt", locator="L1", excerpt="A's separately recorded stage."
    )
    path = save(tmp_path, data)
    output = tmp_path / "section" / "scientific-context"
    copied = copy_scientific_context(path, output, section_ids=["results"])
    assert [fact["id"] for fact in copied["facts"]] == ["B-operator"]
    assert [case["id"] for case in copied["cases"]] == ["B"]
    assert copied["comparisons"] == []
    assert len(list((output / "sources").iterdir())) == 1
    assert (output / copied["facts"][0]["source"]["path"]).read_bytes() == (
        tmp_path / "methods.md"
    ).read_bytes()
    assert load_scientific_context(output / "context.json") == copied


def test_explicit_conflict_keeps_both_sources_and_unrelated_work(tmp_path):
    data = fixture(tmp_path)
    conflicting = copy.deepcopy(data["facts"][1])
    conflicting.update(id="B-earlier", text="Earlier definition differs.", status="conflict")
    conflicting["source"].update(
        locator="L4", excerpt="B: earlier report uses the outlet area-weighted static pressure."
    )
    data["facts"].append(conflicting)
    data["comparisons"].append(
        {
            "id": "B-definition-conflict",
            "case_ids": ["B"],
            "section_ids": ["methods"],
            "fact_ids": ["B-operator", "B-earlier"],
            "text": "Definition conflict requires resolution before a dependent comparison.",
            "status": "conflict",
        }
    )
    loaded = load_scientific_context(save(tmp_path, data))
    selected = select_scientific_context(loaded, ["methods"])
    assert selected["facts"][0]["status"] == "recorded"
    assert len(selected["facts"]) == 3
    text = render_scientific_context(selected)
    assert "L3" in text and "L4" in text and "[conflict]" in text
    assert "[recorded]" in text


def test_real_missing_fact_is_retained_unknown_not_completed_from_other_case(tmp_path):
    data = fixture(tmp_path)
    unknown = copy.deepcopy(data["facts"][0])
    unknown.update(
        id="B-stage", case_ids=["B"], status="unknown", text="B's stage is not recorded."
    )
    unknown.pop("source")
    unknown.pop("stage")
    data["facts"].append(unknown)
    loaded = load_scientific_context(save(tmp_path, data))
    saved_unknown = loaded["facts"][-1]
    assert saved_unknown["status"] == "unknown"
    assert "stage" not in saved_unknown and "source" not in saved_unknown
    assert "Source: not recorded (unknown fact)" in render_scientific_context(loaded)
    data["comparisons"][0].update(fact_ids=["A-stage", "B-stage"], status="recorded")
    with pytest.raises(ValueError, match="cannot upgrade"):
        load_scientific_context(save(tmp_path, data))


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda data: data["facts"][0].update(case_ids=["missing"]), "Unknown case"),
        (lambda data: data["facts"][0].update(case_ids=[]), "nonempty"),
        (lambda data: data["facts"][0].update(section_ids=[]), "nonempty"),
        (lambda data: data["facts"][0].update(status="validated"), "status must"),
        (lambda data: data["facts"][0].pop("source"), "requires a located source"),
        (lambda data: data["facts"].append(copy.deepcopy(data["facts"][0])), "Duplicate facts"),
        (lambda data: data["comparisons"][0].update(fact_ids=["missing"]), "Unknown comparison"),
        (lambda data: data["comparisons"][0].update(case_ids=["A"]), "case scope"),
        (lambda data: data["facts"][0].update(case_ids=["A", "A"]), "duplicate IDs"),
    ],
)
def test_invalid_identity_scope_and_missing_recorded_source(tmp_path, mutation, message):
    data = fixture(tmp_path)
    mutation(data)
    with pytest.raises(ValueError, match=message):
        load_scientific_context(save(tmp_path, data))


def test_allowed_section_validation_and_not_character_iteration(tmp_path):
    path = save(tmp_path, fixture(tmp_path))
    with pytest.raises(ValueError, match="Unknown section"):
        load_scientific_context(path, ["methods"])
    with pytest.raises(ValueError, match="collection, not a string"):
        load_scientific_context(path, "methods")


def test_same_name_different_stages_do_not_imply_conflict(tmp_path):
    data = fixture(tmp_path)
    earlier = copy.deepcopy(data["facts"][0])
    earlier.update(id="A-initial", stage="initial stage", text="Host interpretation of the source.")
    earlier["source"].update(locator="L1", excerpt="Synthetic methods")
    data["facts"].append(earlier)
    loaded = load_scientific_context(save(tmp_path, data))
    same_names = [fact for fact in loaded["facts"] if fact["name"] == earlier["name"]]
    assert [fact["stage"] for fact in same_names] == ["final steady stage", "initial stage"]
    assert all(fact["status"] == "recorded" for fact in same_names)


def test_comparison_cannot_broaden_declared_fact_scope(tmp_path):
    data = fixture(tmp_path)
    data["cases"].append({"id": "C"})
    data["comparisons"][0]["case_ids"].append("C")
    with pytest.raises(ValueError, match="case scope"):
        load_scientific_context(save(tmp_path, data))
    data["comparisons"][0]["case_ids"] = ["A", "B"]
    loaded = load_scientific_context(save(tmp_path, data))
    selected = select_scientific_context(loaded, ["discussion"])
    assert [case["id"] for case in selected["cases"]] == ["A", "B"]
    assert selected["facts"][0]["case_ids"] == ["A"]
    assert selected["facts"][0]["section_ids"] == ["methods"]
    assert selected["facts"][1]["case_ids"] == ["B"]
    assert selected["facts"][1]["section_ids"] == ["results"]


def test_conflicting_fact_cannot_enter_recorded_comparison(tmp_path):
    data = fixture(tmp_path)
    data["facts"][1]["status"] = "conflict"
    data["comparisons"][0]["status"] = "recorded"
    with pytest.raises(ValueError, match="cannot upgrade"):
        load_scientific_context(save(tmp_path, data))


def test_context_and_sources_reuse_existing_material_size_limits(tmp_path, monkeypatch):
    from cfdpaper.publication import scientific_context

    path = save(tmp_path, fixture(tmp_path))
    monkeypatch.setattr(scientific_context, "MAX_FILE_BYTES", path.stat().st_size - 1)
    with pytest.raises(ValueError, match="file size limit"):
        load_scientific_context(path)
    monkeypatch.setattr(scientific_context, "MAX_FILE_BYTES", 8 * 1024 * 1024)
    monkeypatch.setattr(scientific_context, "MAX_TOTAL_BYTES", 1)
    with pytest.raises(ValueError, match="material size limits"):
        load_scientific_context(path)


def parameter_fixture(tmp_path):
    data = fixture(tmp_path)
    recorded = {
        "elapsed_s": [index for index in range(220)],
        "timestamp": "synthetic recorded time",
        "materials": {
            "solid": {"thermal_conductivity": {"value": 16.3, "unit": "W/(m K)"}},
            "water": {"density_kg_m3": 998.2},
        },
        "boundary_conditions": {
            "inlet": {"mass_flow_kg_s": 0.012, "temperature_K": 298.15},
            "heated_wall": {"heat_flux_W_m2": 120000},
        },
        "cell_zone_conditions": {"solid": {"energy": True, "source_W_m3": 0}},
        "geometry": {"size_m": [0.04, 0.02, 0.005]},
        "models": {"energy": True, "turbulence": "recorded model"},
        "solver": {"stage": "final stage", "pressure_velocity": "recorded scheme"},
        "numerical_settings": {"residual_target": 1e-6},
        "labels": {"a/b~c": None},
    }
    (tmp_path / "parameters.json").write_text(json.dumps(recorded, indent=2), encoding="utf-8")
    for fact in data["facts"]:
        fact["source"].update(path="parameters.json", locator="L1", excerpt="{")
    return save(tmp_path, data), recorded


def test_parameter_view_reads_real_method_values_and_exact_json_pointers(tmp_path):
    path, recorded = parameter_fixture(tmp_path)
    original = (tmp_path / "parameters.json").read_bytes()
    view = read_source_parameters(path, limit=500)
    assert len(view["sources"]) == 1
    source = view["sources"][0]
    assert source["path"] == "parameters.json"
    assert source["linked_fact_ids"] == ["A-stage", "B-operator"]
    entries = {entry["pointer"]: entry["value"] for entry in source["entries"]}
    assert entries["/materials/solid/thermal_conductivity/value"] == 16.3
    assert entries["/boundary_conditions/inlet/mass_flow_kg_s"] == 0.012
    assert entries["/boundary_conditions/heated_wall/heat_flux_W_m2"] == 120000
    assert entries["/cell_zone_conditions/solid/energy"] is True
    assert entries["/geometry/size_m/2"] == recorded["geometry"]["size_m"][2]
    assert entries["/labels/a~1b~0c"] is None
    assert entries["/elapsed_s/219"] == 219
    assert not source["truncated"] and not view["truncated"]
    assert "do not assign all file parameters" in view["scope_note"]
    assert "case_ids" not in source
    assert (tmp_path / "parameters.json").read_bytes() == original


def test_parameter_limit_prioritizes_methods_and_declares_global_truncation(tmp_path):
    path, _ = parameter_fixture(tmp_path)
    view = read_source_parameters(path, limit=6)
    source = view["sources"][0]
    assert len(source["entries"]) == 6
    assert source["truncated"] and view["truncated"]
    assert all(
        entry["pointer"].startswith(("/materials/", "/boundary_conditions/"))
        for entry in source["entries"]
    )
    assert any(entry["value"] == 16.3 for entry in source["entries"])
    assert any(entry["value"] == 0.012 for entry in source["entries"])
    empty = read_source_parameters(path, limit=0)
    assert empty["sources"][0]["entries"] == []
    assert empty["truncated"]


def test_parameter_selection_uses_fact_scope_without_inferred_case_assignment(tmp_path):
    path, _ = parameter_fixture(tmp_path)
    view = read_source_parameters(path, section_ids=["methods"])
    assert view["sources"][0]["linked_fact_ids"] == ["A-stage"]
    assert view["sources"][0]["path"] == "parameters.json"
    # Values describe the file, not a new case-scoped fact generated by this helper.
    assert "case_ids" not in view["sources"][0]
    assert read_source_parameters(path, section_ids=["intro"])["sources"] == []
    dependency = read_source_parameters(path, section_ids=["discussion"])
    assert dependency["sources"][0]["linked_fact_ids"] == ["A-stage", "B-operator"]


def test_parameter_multiple_sources_share_one_global_limit(tmp_path):
    path, _ = parameter_fixture(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    (tmp_path / "other.json").write_text('{"timestamp": "other recorded time"}', encoding="utf-8")
    data["facts"][0]["source"].update(
        path="other.json", locator="L1", excerpt='{"timestamp": "other recorded time"}'
    )
    view = read_source_parameters(save(tmp_path, data), limit=1)
    assert len(view["sources"]) == 2
    assert sum(len(source["entries"]) for source in view["sources"]) == 1
    assert view["sources"][1]["entries"][0]["pointer"].startswith("/materials/")
    assert all(source["truncated"] for source in view["sources"])


def test_parameter_array_order_is_natural_and_sources_are_deduplicated(tmp_path):
    path, _ = parameter_fixture(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["facts"][1]["source"]["path"] = "./parameters.json"
    view = read_source_parameters(save(tmp_path, data), limit=500)
    assert len(view["sources"]) == 1
    elapsed = [
        entry["pointer"]
        for entry in view["sources"][0]["entries"]
        if entry["pointer"].startswith("/elapsed_s/")
    ]
    assert elapsed.index("/elapsed_s/2") < elapsed.index("/elapsed_s/10")


def test_parameter_view_relocates_with_source_context(tmp_path):
    path, _ = parameter_fixture(tmp_path)
    package = tmp_path / "package"
    copy_scientific_context(path, package, section_ids=["methods"])
    view = read_source_parameters(package / "context.json", section_ids=["methods"])
    assert view["sources"][0]["path"] == "sources/source-0001.json"
    assert view["sources"][0]["linked_fact_ids"] == ["A-stage"]
    assert any(entry["value"] == 16.3 for entry in view["sources"][0]["entries"])


@pytest.mark.parametrize("limit", [-1, True, 1.5, "200"])
def test_parameter_limit_requires_nonnegative_integer(tmp_path, limit):
    path, _ = parameter_fixture(tmp_path)
    with pytest.raises(ValueError, match="nonnegative integer"):
        read_source_parameters(path, limit=limit)


def test_parameter_view_ignores_non_json_and_keeps_malformed_json_as_missing(tmp_path):
    path = save(tmp_path, fixture(tmp_path))
    assert read_source_parameters(path)["sources"] == []
    data = json.loads(path.read_text(encoding="utf-8"))
    (tmp_path / "invalid.json").write_text("not valid JSON", encoding="utf-8")
    data["facts"][0]["source"].update(path="invalid.json", locator="L1", excerpt="not valid JSON")
    view = read_source_parameters(save(tmp_path, data))
    assert len(view["sources"]) == 1
    source = view["sources"][0]
    assert source["path"] == "invalid.json"
    assert source["linked_fact_ids"] == ["A-stage"]
    assert source["entries"] == []
    assert source["issues"][0]["code"] == "invalid-json"
    assert "parameters unavailable" in source["issues"][0]["message"]
    assert not source["truncated"] and not view["truncated"]


def test_parameter_view_continues_valid_source_after_malformed_json(tmp_path):
    data = fixture(tmp_path)
    (tmp_path / "invalid.json").write_text("not valid JSON", encoding="utf-8")
    data["facts"][0]["source"].update(path="invalid.json", locator="L1", excerpt="not valid JSON")
    valid = '{"materials": {"solid": {"conductivity_W_mK": 16.3}}}'
    (tmp_path / "valid.json").write_text(valid, encoding="utf-8")
    data["facts"][1]["source"].update(path="valid.json", locator="L1", excerpt=valid)
    view = read_source_parameters(save(tmp_path, data))
    invalid_source, valid_source = view["sources"]
    assert invalid_source["entries"] == []
    assert invalid_source["issues"][0]["code"] == "invalid-json"
    assert valid_source["path"] == "valid.json"
    assert valid_source["linked_fact_ids"] == ["B-operator"]
    assert valid_source["issues"] == []
    assert valid_source["entries"] == [
        {"pointer": "/materials/solid/conductivity_W_mK", "value": 16.3}
    ]
