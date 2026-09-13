"""Synthetic selected advice on the public seven-section manuscript example."""

import json
import runpy
import shutil
from pathlib import Path

import pytest

from cfdpaper.publication.manuscript import assemble_manuscript, prepare_manuscript
from cfdpaper.publication.manuscript_review import (
    import_manuscript_review,
    prepare_manuscript_review,
)
from cfdpaper.publication.manuscript_revision import prepare_manuscript_revision


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def files(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


@pytest.fixture(scope="module")
def review_return(tmp_path_factory):
    root = tmp_path_factory.mktemp("selected-review")
    script = (
        Path(__file__).resolve().parents[2] / "examples/literature-manuscript/prepare_example.py"
    )
    source = root / "source"
    runpy.run_path(str(script))["prepare"](source)
    prepared = prepare_manuscript(source / "manuscript-input.json", root / "prepared")
    candidate = assemble_manuscript(prepared, source / "drafts.json", root / "candidate")
    (candidate / "manuscript.pdf").write_bytes(b"%PDF-synthetic-historical-preview")
    prepare_manuscript_review(candidate, root / "review")
    report = root / "完整报告.md"
    report.write_bytes(
        b"\xef\xbb\xbf# Synthetic software test report, not external review\r\n"
        + ("未选取的完整讨论也必须保留。\r\n" * 30).encode()
        + b"Clarify the hydraulic explanation.\r\nDo not add an unsupported claim.\r\n"
        + b"Defer new simulations.\r\n"
    )
    import_manuscript_review(root / "review", report, root / "returned")
    return root / "returned"


@pytest.fixture
def mapping(review_return):
    paragraph = next(
        p
        for p in read(review_return / "snapshot/locators.json")["paragraphs"]
        if p["section_id"] == "hydraulics" and p["paragraph"] == 1
    )
    return {
        "package_id": read(review_return / "review-return.json")["package_id"],
        "actions": [
            {
                "id": "clarity",
                "decision": "accept",
                "report_quote": "Clarify the hydraulic explanation.",
                "rationale": "Synthetic wording test; retain the analytical meaning.",
                "instruction": "Reconsider this explanation without changing the bound values.",
                "targets": [
                    {"section_id": "hydraulics", "paragraph": 1, "quote": paragraph["text"]}
                ],
                "related_sections": {"discussion": "Check the connected interpretation."},
            },
            {
                "id": "unsupported",
                "decision": "reject",
                "report_quote": "Do not add an unsupported claim.",
                "rationale": "Existing scope already explains the limit.",
                "instruction": "THIS MUST NOT BECOME AN ACTIVE TASK",
                "targets": [{"section_id": "not-mapped"}],
            },
            {
                "id": "simulations",
                "decision": "defer",
                "report_quote": "Defer new simulations.",
                "rationale": "Additional evidence is not available.",
            },
        ],
    }


def prepare(review_return, mapping, tmp_path):
    actions = tmp_path / "actions.json"
    write(actions, mapping)
    task = tmp_path / "task"
    return prepare_manuscript_revision(review_return, actions, task), task


def test_full_return_raw_mapping_and_working_copy_preserved(review_return, mapping, tmp_path):
    before = files(review_return)
    result, task = prepare(review_return, mapping, tmp_path)
    assert result == read(task / "revision-task.json")
    assert result["package_id"] == mapping["package_id"]
    assert files(task / "reference") == before
    assert files(review_return) == before
    assert (task / "selected-actions.json").read_bytes() == (tmp_path / "actions.json").read_bytes()
    assert (task / result["raw_report"]).read_bytes().startswith(b"\xef\xbb\xbf")
    original = files(review_return / "snapshot/manuscript")
    assert files(task / "working") == {
        name: data for name, data in original.items() if name != "manuscript.pdf"
    }
    text = (task / "TASK.md").read_text(encoding="utf-8")
    selected = mapping["actions"][0]
    assert selected["report_quote"] in text
    assert selected["targets"][0]["quote"] in text
    assert "Related section discussion: Check the connected interpretation." in text
    assert "working/sections/discussion/draft.json" in text
    assert "historical reading aids" in text
    assert "THIS MUST NOT BECOME AN ACTIVE TASK" not in text
    assert all(a["resolved_targets"] == [] for a in result["actions"][1:])
    skill = Path(__file__).resolve().parents[2] / "skills/cfd-evidence-writing"
    assert files(task / "skills/cfd-evidence-writing") == files(skill)
    assert (task / "skills/cfd-evidence-writing/SKILL.md").is_file()
    assert (task / "skills/cfd-evidence-writing/references/manuscript-review.md").is_file()
    assert "[CFD evidence writing](skills/cfd-evidence-writing/SKILL.md)" in text
    assert "(skills/cfd-evidence-writing/references/manuscript-review.md)" in text


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ("package", "package_id"),
        ("report_quote", "report_quote is absent"),
        ("stale_quote", "stale or ambiguous paragraph quote"),
        ("missing_paragraph", "paragraph target"),
        ("bool_paragraph", "1-based integer"),
        ("unknown_section", "Unknown target section"),
        ("unknown_related", "Unknown related section"),
        ("empty_reason", "empty reason"),
        ("no_targets", "at least one target"),
        ("no_instruction", "instruction"),
        ("duplicate_id", "Duplicate action id"),
        ("unknown_object", "object target"),
        ("unknown_kind", "Unknown target object kind"),
    ],
)
def test_invalid_mapping_has_no_output(review_return, mapping, tmp_path, change, message):
    action = mapping["actions"][0]
    target = action["targets"][0]
    if change == "package":
        mapping["package_id"] = "older-package"
    elif change == "report_quote":
        action["report_quote"] = "Not in this report"
    elif change == "stale_quote":
        target["quote"] = "An older manuscript passage."
    elif change == "missing_paragraph":
        target["paragraph"] = 1000
    elif change == "bool_paragraph":
        target["paragraph"] = True
    elif change == "unknown_section":
        target["section_id"] = "unknown"
    elif change == "unknown_related":
        action["related_sections"] = {"unknown": "A reason"}
    elif change == "empty_reason":
        action["related_sections"] = {"discussion": " "}
    elif change == "no_targets":
        action["targets"] = []
    elif change == "no_instruction":
        action["instruction"] = " "
    elif change == "duplicate_id":
        mapping["actions"][1]["id"] = action["id"]
    elif change == "unknown_object":
        action["targets"] = [{"section_id": "hydraulics", "kind": "figure", "global_number": 99}]
    else:
        action["targets"] = [{"section_id": "hydraulics", "kind": "unknown", "global_number": 1}]
    with pytest.raises(ValueError, match=message):
        prepare(review_return, mapping, tmp_path)
    assert not (tmp_path / "task").exists()


def test_ambiguous_quote_within_target_paragraph_rejected(review_return, mapping, tmp_path):
    mapping["actions"][0]["targets"][0]["quote"] = "the "
    with pytest.raises(ValueError, match="ambiguous paragraph quote"):
        prepare(review_return, mapping, tmp_path)


def test_duplicate_locator_not_silently_resolved(review_return, mapping, tmp_path):
    returned = tmp_path / "returned"
    shutil.copytree(review_return, returned)
    path = returned / "snapshot/locators.json"
    index = read(path)
    index["paragraphs"].append(index["paragraphs"][0])
    write(path, index)
    with pytest.raises(ValueError, match="ambiguous review locators"):
        prepare(returned, mapping, tmp_path)


def test_object_identities_and_exact_reading_quotes(review_return, mapping, tmp_path):
    index = read(review_return / "snapshot/locators.json")
    objects = [
        next(
            obj
            for obj in index["objects"]
            if obj["kind"] == kind
            and sum(
                other["kind"] == kind
                and other["section_id"] == obj["section_id"]
                and other["global_number"] == obj["global_number"]
                for other in index["objects"]
            )
            == 1
        )
        for kind in ("figure", "table", "equation", "reference")
    ]
    mapping["actions"][0]["targets"] = [
        {key: obj[key] for key in ("section_id", "kind", "global_number")} for obj in objects
    ]
    result, task = prepare(review_return, mapping, tmp_path)
    targets = result["actions"][0]["resolved_targets"]
    assert [t["local_id"] for t in targets] == [obj["local_id"] for obj in objects]
    text = (task / "TASK.md").read_text(encoding="utf-8")
    for target in targets:
        assert isinstance(target["quote"], str) and target["quote"] in text
        assert (task / target["draft_path"]).is_file()


def test_shared_reference_roles_are_an_ambiguous_local_target(review_return, mapping, tmp_path):
    mapping["actions"][0]["targets"] = [
        {"section_id": "introduction", "kind": "reference", "global_number": 1}
    ]
    with pytest.raises(ValueError, match="ambiguous object target.*specify local_id"):
        prepare(review_return, mapping, tmp_path)


@pytest.mark.parametrize("role_index", [0, 1])
def test_local_id_disambiguates_shared_reference_roles(
    review_return, mapping, tmp_path, role_index
):
    roles = [
        obj
        for obj in read(review_return / "snapshot/locators.json")["objects"]
        if obj["section_id"] == "introduction"
        and obj["kind"] == "reference"
        and obj["global_number"] == 1
    ]
    target = {
        "section_id": "introduction",
        "kind": "reference",
        "global_number": 1,
        "local_id": roles[role_index]["local_id"],
    }
    mapping["actions"][0]["targets"] = [target]
    result, _ = prepare(review_return, mapping, tmp_path)
    resolved = result["actions"][0]["resolved_targets"][0]
    assert resolved["local_id"] == target["local_id"]
    assert resolved["local_number"] == roles[role_index]["local_number"]


def test_wrong_local_reference_id_does_not_retarget(review_return, mapping, tmp_path):
    mapping["actions"][0]["targets"] = [
        {
            "section_id": "introduction",
            "kind": "reference",
            "global_number": 1,
            "local_id": "not-an-existing-role",
        }
    ]
    with pytest.raises(ValueError, match="object target.*specify local_id"):
        prepare(review_return, mapping, tmp_path)
    assert not (tmp_path / "task").exists()


def test_missing_extraction_and_wrong_return_kind(review_return, mapping, tmp_path):
    returned = tmp_path / "returned"
    shutil.copytree(review_return, returned)
    path = returned / "review-return.json"
    record = read(path)
    record["readable_report"] = None
    write(path, record)
    with pytest.raises(ValueError, match="extraction is required"):
        prepare(returned, mapping, tmp_path)
    record["kind"] = "not-a-review-return"
    write(path, record)
    with pytest.raises(ValueError, match="review return"):
        prepare(returned, mapping, tmp_path)


def test_changed_snapshot_requires_reassembly(review_return, mapping, tmp_path):
    returned = tmp_path / "returned"
    shutil.copytree(review_return, returned)
    path = returned / "snapshot/manuscript/sections/hydraulics/draft.json"
    draft = read(path)
    draft["paragraphs"][0]["text"] += " Later author edit."
    write(path, draft)
    with pytest.raises(ValueError, match="Reassemble"):
        prepare(returned, mapping, tmp_path)


def test_moved_task_ordinary_assembly_keeps_unrelated_drafts(review_return, mapping, tmp_path):
    _, task = prepare(review_return, mapping, tmp_path)
    moved = tmp_path / "elsewhere/task"
    moved.parent.mkdir()
    shutil.move(task, moved)
    working = moved / "working"
    originals = {
        sid: (working / name).read_bytes() for sid, name in read(working / "drafts.json").items()
    }
    path = working / "sections/hydraulics/draft.json"
    draft = read(path)
    draft["paragraphs"][0]["text"] += " This explanation remains specific to the analytical model."
    write(path, draft)
    candidate = assemble_manuscript(working, working / "drafts.json", moved / "new-candidate")
    for sid, before in originals.items():
        if sid != "hydraulics":
            assert (candidate / f"sections/{sid}/draft.json").read_bytes() == before
    assert "This explanation remains specific" in (candidate / "manuscript.md").read_text(
        encoding="utf-8"
    )
    with pytest.raises(FileExistsError):
        prepare_manuscript_revision(review_return, tmp_path / "actions.json", moved)
