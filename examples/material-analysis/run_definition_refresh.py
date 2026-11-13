"""Continue the synthetic linked example under an explicitly different spatial definition."""

import argparse
import json
import shutil
from pathlib import Path

from cfdpaper.publication.linked_section import refresh_section


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def run(previous, output):
    # No earlier analysis is repeated: start from the author-edited output of run_linked_refresh.
    previous, output = Path(previous).resolve(), Path(output).resolve()
    if output.is_relative_to(previous) or previous.is_relative_to(output):
        raise ValueError("Use a fresh output outside the previous build")
    output.mkdir(parents=True, exist_ok=False)
    work = output / "current"
    shutil.copytree(previous / "workspace", work)
    new = read(work / "input.json")
    new["table_calculations"][0].update(domain="Lower region only", row_filters={"region": "lower"})
    write(work / "input.json", new)
    refresh_section(work, output / "inspection", baseline=previous, inspect_change=True)
    plan = read(output / "inspection/reconcile.json")
    # These explicit edits represent the host's changed interpretation, never an automatic rule.
    for item in plan["figures"]:
        item["reading"] = "The plot now represents only the selected lower region."
    paras = {
        "rate": (
            "The lower region transfers {{value:rate-Modified}} in the modified case, "
            "compared with {{value:rate-Reference}} in the reference case."
        ),
        "area": (
            "The lower-region areas differ ({{value:area-Reference}} and "
            "{{value:area-Modified}}). These local integrals do not describe the upper region."
        ),
    }
    for item in plan["readers"]:
        if item["kind"] == "caption":
            item["after"] = "Lower region. " + item["before"]
        else:
            item["after"] = paras[item["id"]]
    write(output / "host-revision.json", plan)
    refresh_section(work, output / "candidate", baseline=previous, reconciliation=plan, docx=True)
    actual = read(output / "candidate/section/section.json")
    assert {k: v["raw_value"] for k, v in actual["resolved_values"].items()} == {
        "rate-Reference": 20,
        "rate-Modified": 33,
        "area-Reference": 2,
        "area-Modified": 4,
    }
    assert (output / "candidate/section.docx").is_file()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("previous", type=Path, help="The 'after' build of run_linked_refresh.py")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    run(args.previous, args.output)
