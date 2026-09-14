"""Run a synthetic review and one explicit host edit on an existing tutorial candidate."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


def run(candidate: Path, output: Path) -> None:
    candidate, output = candidate.resolve(), output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    original = (candidate / "manuscript.md").read_bytes()

    def cli(*args: str | Path) -> None:
        subprocess.run(
            [
                sys.executable,
                "-c",
                "from cfdpaper.cli import app; app()",
                *(str(arg) for arg in args),
            ],
            cwd=output,
            check=True,
        )

    review, returned, task = output / "review", output / "returned", output / "editing-task"
    cli("review", output, "--package", candidate, "--output", review)
    packet = json.loads((review / "review-package.json").read_text(encoding="utf-8"))
    report = output / "synthetic-review.md"
    report_quote = "Check the pressure comparison and its uses in the summary sections."
    payload = f"# Synthetic software example, not an external assessment\n\n{report_quote}\n"
    report.write_text(payload, encoding="utf-8")
    cli("review", output, "--package", review, "--report", report, "--output", returned)
    actions = output / "actions.json"
    quote = "the analytical pressure drop increases"
    actions.write_text(
        json.dumps(
            {
                "package_id": packet["package_id"],
                "actions": [
                    {
                        "id": "example-pressure",
                        "decision": "accept",
                        "report_quote": report_quote,
                        "rationale": "Exercise shared evidence locations using analytical data.",
                        "instruction": "Read shared evidence uses and demonstrate a wording edit.",
                        "trace_evidence": True,
                        "targets": [{"section_id": "hydraulics", "paragraph": 1, "quote": quote}],
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    cli("review", output, "--package", returned, "--actions", actions, "--output", task)
    moved = output / "relocated-task"
    shutil.move(task, moved)
    result = json.loads((moved / "revision-task.json").read_text(encoding="utf-8"))
    sections = {item["section_id"] for item in result["actions"][0]["evidence_uses"]}
    assert {"hydraulics", "abstract", "discussion", "conclusion"} <= sections, sections
    assert (moved / "reference/raw-report/synthetic-review.md").read_bytes() == report.read_bytes()
    assert (moved / "skills/cfd-evidence-writing/references/manuscript-review.md").is_file()

    working = moved / "working"
    mapping = json.loads((working / "drafts.json").read_text(encoding="utf-8"))
    before = {sid: (working / path).read_bytes() for sid, path in mapping.items()}
    draft_path = working / mapping["hydraulics"]
    draft = json.loads(before["hydraulics"])
    # Explicit authored example edit, not automatic scientific revision.
    draft["paragraphs"][0]["text"] = draft["paragraphs"][0]["text"].replace(
        quote, "the analytical pressure drop rises"
    )
    draft_path.write_text(json.dumps(draft, indent=2), encoding="utf-8")
    revised = output / "revised-manuscript"
    cli(
        "write",
        output,
        "--artifact",
        "manuscript",
        "--package",
        working,
        "--draft",
        working / "drafts.json",
        "--output",
        revised,
    )
    assert "the analytical pressure drop rises" in (revised / "manuscript.md").read_text(
        encoding="utf-8"
    )
    for sid, path in mapping.items():
        if sid != "hydraulics":
            assert (working / path).read_bytes() == before[sid]
            assert json.loads((revised / path).read_text(encoding="utf-8")) == json.loads(
                before[sid]
            )
    assert (candidate / "manuscript.md").read_bytes() == original
    print(f"Review round trip complete; {len(sections)} sections share the selected evidence.")


if __name__ == "__main__":
    run(Path(sys.argv[1]), Path(sys.argv[2]))
