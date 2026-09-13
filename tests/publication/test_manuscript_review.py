"""Whole-paper review uses the actual public seven-section analytical example."""

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


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def files(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


@pytest.fixture(scope="module")
def public_candidate(tmp_path_factory):
    root = tmp_path_factory.mktemp("whole-review")
    script = (
        Path(__file__).resolve().parents[2] / "examples/literature-manuscript/prepare_example.py"
    )
    source = root / "source"
    runpy.run_path(str(script))["prepare"](source)
    prepared = prepare_manuscript(source / "manuscript-input.json", root / "prepared")
    return assemble_manuscript(prepared, source / "drafts.json", root / "candidate")


def test_complete_public_manuscript_locators_and_relocatable_sources(public_candidate, tmp_path):
    candidate = tmp_path / "candidate"
    shutil.copytree(public_candidate, candidate)
    (candidate / "unrelated-private-note.txt").write_text("not relevant")
    (tmp_path / "outside-project-secret.txt").write_text("not relevant")
    before = files(candidate)
    package = tmp_path / "review"
    result = prepare_manuscript_review(candidate, package)
    assert files(candidate) == before
    assert result == read(package / "review-package.json")
    assert result["previews"]["pdf"]["status"] == "not-available"
    assert not any("secret" in name or "private-note" in name for name in result["files"])
    assert len(read(package / "manuscript/numbering.json")["sections"]) == 7
    assert (package / result["manuscript"]).read_bytes() == (
        candidate / "manuscript.md"
    ).read_bytes()
    assert (package / "manuscript/CHANGES.md").read_bytes() == (
        candidate / "CHANGES.md"
    ).read_bytes()
    index = read(package / result["locators"])
    combined = read(package / "manuscript/section.json")
    for paragraph in index["paragraphs"]:
        ordinal = int(paragraph["json_pointer"].split("/")[2])
        assert paragraph["text"] == combined["paragraphs"][ordinal]["text"]
        assert paragraph["text"].startswith(paragraph["text_excerpt"])
        assert paragraph["paragraph"] >= 1
    figures = [obj for obj in index["objects"] if obj["kind"] == "figure"]
    assert len(figures) == 2
    references = [obj for obj in index["objects"] if obj["kind"] == "reference"]
    assert len({obj["section_id"] for obj in references}) > 1
    assert len({obj["global_number"] for obj in references}) == 1
    abstract = read(package / "manuscript/sections/abstract/review-packet/bound-evidence.json")
    assert abstract
    moved = tmp_path / "elsewhere" / "review"
    moved.parent.mkdir()
    shutil.move(package, moved)
    for entry in read(moved / "manuscript/manuscript-input.json")["sections"]:
        section = moved / "manuscript" / entry["input"]
        packet = section.parent / "review-packet"
        data = read(packet / "input.json")
        for name in data.get("source_files", []):
            assert (packet / name).is_file()
        for figure in data["figures"]:
            assert (packet / figure["path"]).is_file()
        support_path = packet / "literature-support.json"
        if support_path.exists():
            support = read(support_path)
            for record in support["supports"]:
                assert record["excerpt"] in (packet / record["source"]).read_text(encoding="utf-8")
    report = tmp_path / "report.md"
    report.write_text("A report on the moved snapshot.", encoding="utf-8")
    returned = import_manuscript_review(moved, report, tmp_path / "returned")
    assert returned["package_id"] == result["package_id"]


@pytest.mark.parametrize("mutation", ["source", "draft", "reading", "figure"])
def test_changed_candidate_requires_reassembly(public_candidate, tmp_path, mutation):
    candidate = tmp_path / "candidate"
    shutil.copytree(public_candidate, candidate)
    if mutation == "source":
        source = next((candidate / "sections/hydraulics/sources").glob("*.csv"))
        source.write_bytes(source.read_bytes() + b"\n")
    elif mutation == "draft":
        source = candidate / "sections/hydraulics/draft.json"
        data = read(source)
        data["paragraphs"][0]["text"] += " Author changed this paragraph."
        write(source, data)
    elif mutation == "reading":
        source = candidate / "manuscript.md"
        source.write_text(
            source.read_text(encoding="utf-8") + "Changed reading text.\n", encoding="utf-8"
        )
    else:
        source = next((candidate / "figures").glob("*.png"))
        source.write_bytes(source.read_bytes() + b"changed")
    before = files(candidate)
    with pytest.raises(ValueError, match="[Rr]eassembl"):
        prepare_manuscript_review(candidate, tmp_path / "review")
    assert not (tmp_path / "review").exists()
    assert files(candidate) == before


def test_candidate_can_be_moved_before_review(public_candidate, tmp_path):
    candidate = tmp_path / "moved-candidate"
    shutil.copytree(public_candidate, candidate)
    result = prepare_manuscript_review(candidate, tmp_path / "review")
    assert result["status"] == "ready-for-external-review"


def test_global_numbers_are_distinct_from_section_local_numbers(public_candidate, tmp_path):
    working = tmp_path / "working"
    shutil.copytree(public_candidate, working)
    manifest = read(working / "manuscript-input.json")
    sections = manifest["spine"]["sections"]
    sections[3], sections[4] = sections[4], sections[3]
    write(working / "manuscript-input.json", manifest)
    candidate = assemble_manuscript(working, working / "drafts.json", tmp_path / "candidate")
    package = tmp_path / "review"
    prepare_manuscript_review(candidate, package)
    figures = [obj for obj in read(package / "locators.json")["objects"] if obj["kind"] == "figure"]
    assert {(obj["section_id"], obj["local_id"], obj["global_number"]) for obj in figures} == {
        ("thermal", "2", "1"),
        ("hydraulics", "1", "2"),
    }
    prompt = (package / "review-prompt.md").read_text(encoding="utf-8")
    assert "LOCAL numbering" in prompt and "global numbers" in prompt


@pytest.mark.parametrize("suffix", [".txt", ".md", ".json", ".pdf", ".docx"])
def test_full_raw_report_retained_without_manuscript_mutation(public_candidate, tmp_path, suffix):
    package = tmp_path / "review"
    exported = prepare_manuscript_review(public_candidate, package)
    before = files(package)
    report = tmp_path / ("完整评阅" + suffix)
    text = "完整评阅：保留此处的长段落，不在简短 finding list 中。\r\n" * 40
    raw = (
        json.dumps({"findings": [], "complete_report": text}, ensure_ascii=False).encode("utf-8")
        if suffix == ".json"
        else text.encode("utf-8")
    )
    if suffix in {".pdf", ".docx"}:
        raw = b"\x00\xffsynthetic-binary-retention-fixture\r\n" + raw
    report.write_bytes(raw)
    output = tmp_path / "returned"
    result = import_manuscript_review(package, report, output)
    assert (output / result["raw_report"]).read_bytes() == raw
    assert result == read(output / "review-return.json")
    assert result["package_id"] == exported["package_id"]
    assert result["approval_granted"] is False
    assert result["actions"] == "unmapped-pending-host-review"
    assert files(package) == before
    assert files(output / "snapshot") == before
    assert result["extraction_status"] == (
        "required" if suffix in {".pdf", ".docx"} else "not-required"
    )
    task = (output / "TASK.md").read_text(encoding="utf-8")
    assert "older paragraph" in task and "keep it unresolved" in task
    assert "original quotations" in task


def test_host_extraction_retained_alongside_binary_original(public_candidate, tmp_path):
    package = tmp_path / "review"
    prepare_manuscript_review(public_candidate, package)
    report = tmp_path / "report.pdf"
    report.write_bytes(b"%PDF-synthetic-retention-fixture\x00\xff")
    extraction = tmp_path / "report.pdf.md"
    extraction.write_bytes("宿主完整提取\r\n仍需与原件比较。".encode())
    output = tmp_path / "returned"
    result = import_manuscript_review(package, report, output)
    assert (output / result["readable_report"]).read_bytes() == extraction.read_bytes()
    assert (output / result["raw_report"]).read_bytes() == report.read_bytes()
    assert result["extraction_status"] == "host-provided-unverified"


def test_preserves_supplied_preview_without_claiming_visual_review(public_candidate, tmp_path):
    candidate = tmp_path / "candidate"
    shutil.copytree(public_candidate, candidate)
    (candidate / "manuscript.pdf").write_bytes(b"%PDF-supplied-preview-fixture")
    package = tmp_path / "review"
    result = prepare_manuscript_review(candidate, package)
    assert result["previews"]["pdf"]["status"] == "supplied-not-yet-visually-reviewed"
    assert (package / result["previews"]["pdf"]["path"]).read_bytes() == (
        candidate / "manuscript.pdf"
    ).read_bytes()


def test_fresh_output_and_non_manuscript_rejection(public_candidate, tmp_path):
    with pytest.raises(ValueError, match="outside"):
        prepare_manuscript_review(public_candidate, public_candidate / "review")
    with pytest.raises(FileExistsError):
        prepare_manuscript_review(public_candidate, tmp_path)
    empty = tmp_path / "not-assembled"
    empty.mkdir()
    with pytest.raises((ValueError, FileNotFoundError)):
        prepare_manuscript_review(empty, tmp_path / "review")
    assert not (tmp_path / "review").exists()
