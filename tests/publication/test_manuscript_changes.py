"""Synthetic snapshots establish targeted suggestions, not automatic prose revision."""

from copy import deepcopy

from cfdpaper.publication.manuscript_changes import compare_manuscript_states


def section(**extra):
    return {
        "role": "results",
        "input": {"question": "What changed?", "evidence": []},
        "draft": {"paragraphs": [{"text": "Author's manually edited sentence."}]},
        "evidence": {
            "q": {"id": "q", "source": "values.csv", "units": "K", "resolved": {"value": 3}},
            "r": {"id": "r", "source": "other.csv", "resolved": {"value": 8}},
        },
        "sources": {"values.csv": "value\n1\n5\n"},
        "literature": {},
        "bindings": {},
        "depends_on": [],
        **extra,
    }


def state():
    return {
        "sections": {
            "results": section(),
            "abstract": section(role="abstract", bindings={"summary": "results/q"}),
            "other": section(),
        },
        "terms": {"QoI": "quantity of interest"},
        "context": "Synthetic study",
    }


def test_first_snapshot_has_no_fabricated_comparison():
    report = compare_manuscript_states(None, state())
    assert report["baseline_available"] is False
    assert report["changes"] == []
    assert report["affected_sections"] == {}
    assert report["unchanged_sections"] == []
    assert report["notice"] == (
        "Targeted host review suggestions; bound values may recompute but prose meaning "
        "is not automatically revised."
    )


def test_identical_snapshot_has_no_changes_or_autoapproval():
    original = state()
    report = compare_manuscript_states(original, deepcopy(original))
    assert report["baseline_available"] is True
    assert report["changes"] == []
    assert report["affected_sections"] == {}
    assert report["unchanged_sections"] == ["abstract", "other", "results"]
    assert "approved" not in report


def test_evidence_change_only_reaches_exact_binding_and_does_not_mutate():
    before = state()
    after = deepcopy(before)
    after["sections"]["results"]["evidence"]["q"]["resolved"]["value"] = 4
    original_before, original_after = deepcopy(before), deepcopy(after)
    report = compare_manuscript_states(before, after)
    assert set(report["affected_sections"]) == {"results", "abstract"}
    assert report["unchanged_sections"] == ["other"]
    assert report["changes"][0]["reference"] == "q"
    assert report["changes"][0]["before"] == {"resolved": {"value": 3}}
    assert "results/q" in " ".join(report["affected_sections"]["abstract"])
    assert before == original_before and after == original_after
    report["changes"][0]["after"]["resolved"]["value"] = 999
    assert after == original_after


def test_unmatched_evidence_change_does_not_notify_other_binding():
    before, after = state(), state()
    after["sections"]["results"]["evidence"]["r"]["resolved"]["value"] = 9
    # The raw input duplicates evidence; this is still an r-only change.
    before["sections"]["results"]["input"]["evidence"] = list(
        before["sections"]["results"]["evidence"].values()
    )
    after["sections"]["results"]["input"]["evidence"] = list(
        after["sections"]["results"]["evidence"].values()
    )
    report = compare_manuscript_states(before, after)
    assert set(report["affected_sections"]) == {"results"}
    assert [item["category"] for item in report["changes"]] == ["evidence"]


def test_manual_draft_edit_preserves_other_sections_and_text():
    before, after = state(), state()
    after["sections"]["results"]["draft"]["paragraphs"][0]["text"] = "Reworded by author."
    draft = deepcopy(after["sections"]["results"]["draft"])
    report = compare_manuscript_states(before, after)
    assert set(report["affected_sections"]) == {"results"}
    assert report["changes"][0]["category"] == "draft"
    assert "Reworded" not in str(report)
    assert after["sections"]["results"]["draft"] == draft


def test_source_changed_even_when_bound_result_unchanged():
    before, after = state(), state()
    after["sections"]["results"]["sources"]["values.csv"] = "value\n2\n4\n"
    report = compare_manuscript_states(before, after)
    assert set(report["affected_sections"]) == {"results", "abstract"}
    change = report["changes"][0]
    assert change["category"] == "source"
    assert change["reference"] == "values.csv"
    assert change["before"]["characters"] == change["after"]["characters"]
    assert "owner source/input/section changed" in " ".join(report["affected_sections"]["abstract"])
    assert before["sections"]["results"]["evidence"] == after["sections"]["results"]["evidence"]


def test_scientific_definition_change_propagates_conservatively():
    before, after = state(), state()
    after["sections"]["results"]["input"]["sampling_domain"] = "Changed domain"
    report = compare_manuscript_states(before, after)
    assert set(report["affected_sections"]) == {"results", "abstract"}
    assert report["changes"][0]["fields"] == ["sampling_domain"]


def test_evidence_unit_definition_change_targets_binding():
    before, after = state(), state()
    after["sections"]["results"]["evidence"]["q"]["units"] = "degC"
    report = compare_manuscript_states(before, after)
    assert set(report["affected_sections"]) == {"results", "abstract"}
    assert report["changes"][0]["before"] == {"units": "K"}


def test_literature_withdrawal_propagates_to_matching_citation():
    before = state()
    before["sections"]["results"]["literature"]["ref"] = {
        "status": "supported",
        "reference": {"id": "paper", "title": "Synthetic reference"},
    }
    before["sections"]["abstract"]["bindings"] = {"prior": "results/ref"}
    after = deepcopy(before)
    after["sections"]["results"]["literature"]["ref"]["status"] = "unsupported"
    report = compare_manuscript_states(before, after)
    assert set(report["affected_sections"]) == {"results", "abstract"}
    assert report["changes"][0]["category"] == "literature"
    assert report["changes"][0]["after"] == {"status": "unsupported"}


def test_declared_dependencies_and_binding_chains_propagate():
    before = state()
    before["sections"]["discussion"] = section(depends_on=["abstract"])
    before["sections"]["conclusions"] = section(depends_on=["discussion"])
    before["sections"]["methods"] = section(bindings={"quoted": "abstract/summary"})
    after = deepcopy(before)
    after["sections"]["results"]["evidence"]["q"]["resolved"]["value"] = 4
    report = compare_manuscript_states(before, after)
    assert set(report["affected_sections"]) == {
        "results",
        "abstract",
        "discussion",
        "conclusions",
        "methods",
    }
    assert report["unchanged_sections"] == ["other"]


def test_dependency_cycles_terminate_without_prose_inference():
    before = state()
    before["sections"]["abstract"]["depends_on"] = ["results"]
    before["sections"]["results"]["depends_on"] = ["abstract"]
    after = deepcopy(before)
    after["sections"]["results"]["draft"] = {"text": "Changed author wording"}
    report = compare_manuscript_states(before, after)
    assert set(report["affected_sections"]) == {"results", "abstract"}


def test_shared_terms_and_context_are_precise_global_changes():
    before, after = state(), state()
    after["terms"]["QoI"] = "quantity of engineering interest"
    after["context"] = "Revised synthetic study"
    report = compare_manuscript_states(before, after)
    assert set(report["affected_sections"]) == set(after["sections"])
    assert [(item["category"], item["reference"]) for item in report["changes"]] == [
        ("term", "QoI"),
        ("context", "context"),
    ]
    assert "QoI" in " ".join(report["affected_sections"]["other"])


def test_added_removed_sections_and_missing_bound_evidence():
    before, after = state(), state()
    del after["sections"]["results"]
    after["sections"]["new-section"] = section()
    report = compare_manuscript_states(before, after)
    assert set(report["affected_sections"]) == {"abstract", "new-section"}
    assert report["unchanged_sections"] == ["other"]
    assert {item["status"] for item in report["changes"]} == {"added", "removed"}


def test_removed_evidence_reaches_bound_consumer():
    before, after = state(), state()
    del after["sections"]["results"]["evidence"]["q"]
    report = compare_manuscript_states(before, after)
    assert set(report["affected_sections"]) == {"results", "abstract"}
    assert report["changes"][0]["status"] == "removed"


def test_binding_change_marks_local_and_downstream_binding():
    before = state()
    before["sections"]["other"]["bindings"] = {"final": "abstract/summary"}
    after = deepcopy(before)
    after["sections"]["abstract"]["bindings"]["summary"] = "results/r"
    report = compare_manuscript_states(before, after)
    assert set(report["affected_sections"]) == {"abstract", "other"}
    assert report["changes"][0]["category"] == "binding"


def test_large_sources_and_record_text_do_not_bloat_report():
    before, after = state(), state()
    after["sections"]["results"]["sources"]["values.csv"] = "a" * 100_000
    after["sections"]["results"]["evidence"]["q"]["text"] = "z" * 100_000
    report = compare_manuscript_states(before, after)
    assert len(str(report)) < 3000
    assert "a" * 200 not in str(report)
    assert "z" * 200 not in str(report)
