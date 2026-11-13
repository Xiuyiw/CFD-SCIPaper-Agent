"""Public synthetic example. Change one heat-rate observation, keep the area figure and its text."""

import argparse
import csv
import json
import shutil
from pathlib import Path

from cfdpaper.publication.linked_section import refresh_section


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def workspace(root):
    here = Path(__file__).parent
    shutil.copytree(here / "inputs", root / "sources")
    cases = ["Reference", "Modified"]
    figures, evidence, duties, recipes, paragraphs = [], [], [], [], []
    captions = {}
    for fid, field, unit, label in [
        ("1", "rate", "W", "Integrated heat rate (W)"),
        ("2", "area", "m2", "Wetted area (m²)"),
    ]:
        folder = root / field
        folder.mkdir()
        shutil.copyfile(here / "plot_bound_table.py", folder / "plot.py")
        with (folder / "display.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["case", "reading", "author_label"])
            for case in reversed(cases):
                writer.writerow([case, "", case + " layout"])
        ids = {case: f"{field}-{case}" for case in cases}
        evidence.extend(
            {
                "id": eid,
                "kind": "metric",
                "text": label,
                "source": "sources/regions.csv",
                "result_ref": {
                    "calculation_id": "wall",
                    "group": case,
                    "field": field,
                    "places": 1,
                },
            }
            for case, eid in ids.items()
        )
        preview = f"{field}/comparison.png"
        captions[fid] = (
            f"{label.split(' (')[0]}: reference {{{{value:{ids['Reference']}}}}}; "
            f"modified {{{{value:{ids['Modified']}}}}}."
        )
        figures.append({"id": fid, "path": preview, "caption": label, "description": label})
        duties.append({"purpose": label, "figure_ids": [fid], "evidence_ids": list(ids.values())})
        body = (
            "Heat entering the coolant is greater in the modified configuration "
            "({{value:rate-Modified}} versus {{value:rate-Reference}})."
            if field == "rate"
            else "The integrated rates span different wetted areas: {{value:area-Reference}} "
            "and {{value:area-Modified}}. The integral alone does not measure local intensity."
        )
        paragraphs.append(
            {
                "paragraph_id": field,
                "text": body,
                "evidence_ids": list(ids.values()),
                "figure_ids": [fid],
            }
        )
        table = f"{field}/display.csv"
        recipes.append(
            {
                "id": field,
                "section_id": "wall",
                "figure_id": fid,
                "script": f"{field}/plot.py",
                "inputs": [table],
                "outputs": [preview, f"{field}/comparison.svg"],
                "args": [label],
                "result_tables": [
                    {
                        "path": table,
                        "row_key": "case",
                        "columns": {"reading": {"unit": unit, "by_row": ids}},
                    }
                ],
            }
        )
    save(
        root / "input.json",
        {
            "section_id": "wall",
            "title": "Wall transport",
            "question": "How does area affect interpretation of total heat rate?",
            "source_files": ["sources/regions.csv", "sources/method.md"],
            "figures": figures,
            "evidence": evidence,
            "duties": duties,
            "table_calculations": [
                {
                    "id": "wall",
                    "source": "sources/regions.csv",
                    "operation": "partition",
                    "columns": {"area": "area [m2]", "rate": "rate [W]"},
                    "units": {"area": "m2", "rate": "W"},
                    "domain": "Complete selected wall",
                    "group_by": "case",
                }
            ],
        },
    )
    save(
        root / "draft.json",
        {
            "title": "Wall transport",
            "paragraphs": paragraphs,
            "captions": captions,
            "evidence_notes": [],
            "image_observations": dict.fromkeys(captions, "not-viewed"),
        },
    )
    save(root / "figure-recipes.json", recipes)
    save(
        root / "reading-relations.json",
        [
            {
                "kind": "paragraph",
                "id": "rate",
                "left": "rate-Modified",
                "op": ">",
                "right": "rate-Reference",
            }
        ],
    )


def run(dest):
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=False)
    workspace(dest / "inputs")
    refresh_section(dest / "inputs", dest / "before", docx=True)
    working = dest / "edited"
    shutil.copytree(dest / "before/workspace", working)
    # An author keeps a local design and adds a clarification between builds.
    script = working / "rate/plot.py"
    script.write_text(
        script.read_text(encoding="utf-8").replace("#166b70", "#a65338"), encoding="utf-8"
    )
    draft = json.loads((working / "draft.json").read_text(encoding="utf-8"))
    draft["paragraphs"][1]["text"] += " Both values refer to the same declared wall partition."
    save(working / "draft.json", draft)
    src = working / "sources/regions.csv"
    src.write_text(
        src.read_text(encoding="utf-8").replace("Modified,lower,4,28", "Modified,lower,4,33"),
        encoding="utf-8",
    )
    return refresh_section(working, dest / "after", baseline=dest / "before", docx=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = run(args.output)
    print([(s["recipe_id"], s["status"]) for s in result["figure_recipes"]])
