"""Move and continue the existing public analytical author-collaboration replay.

Run author-collaboration/run_example.py first, then pass its output directory.
This script consumes installed product APIs; it contains no analysis or renderer.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from cfdpaper.host_tools import manuscript_task, workbench_task


def _ready(response: dict) -> dict:
    context = response["context"]
    if context["status"] != "ready":
        raise RuntimeError(f"Resolve the workbench declarations before continuing: {context}")
    return context


def run(author_output: Path, output: Path) -> Path:
    author_output, output = Path(author_output).resolve(), Path(output).resolve()
    current = author_output / "recovered/candidate"
    baseline = author_output / "baseline"
    author = author_output / "recovered"
    for required in (
        current / "manuscript-input.json",
        current / "drafts.json",
        baseline / "manuscript-input.json",
        author / "manuscript.docx",
    ):
        if not required.is_file():
            raise FileNotFoundError(
                f"Run author-collaboration/run_example.py first; missing {required}"
            )
    output.mkdir(parents=True, exist_ok=False)

    transfer = output / "transfer"
    workbench_task(
        "export",
        current,
        output=transfer,
        baseline=baseline,
        author_dir=author,
        task="Continue the analytical pipe manuscript with its current values and author edits.",
        next_action="Reassemble the restored workspace and retain the unresolved author comment.",
    )
    moved = output / "receiving-machine/workbench"
    moved.parent.mkdir()
    shutil.move(str(transfer), str(moved))
    inspection = _ready(workbench_task("inspect", moved))

    restored = workbench_task("restore", moved, output=output / "restored")
    restored_inspection = _ready(restored)
    workspace = Path(restored["artifacts"]["workspace"])
    continued = output / "continued"
    manuscript_task(continued, package=workspace, drafts=workspace / "drafts.json")
    docx = output / "continued.docx"
    exported = manuscript_task(docx, package=continued, export_format="docx")
    (output / "example-result.json").write_text(
        json.dumps(
            {
                "scenario": "analytical-automation-portability",
                "inspection": inspection,
                "restored_inspection": restored_inspection,
                "current_values": exported["context"]["resolved_values"],
                "continued_manuscript": "continued.docx",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return docx


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("author_output", type=Path, help="Existing author-collaboration output")
    parser.add_argument("output", type=Path, help="New output directory")
    args = parser.parse_args()
    print(run(args.author_output, args.output))
