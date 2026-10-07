# Scientific context for manuscript writing

Scientific context keeps located method facts attached to the cases, solution stages and
reported quantities that they describe. The writing host prepares it from existing study
records. The author reviews the scientific meaning rather than transcribing a complete CFD
questionnaire or maintaining another project registry.

Use it when a comparison depends on settings spread across setup files, execution records,
report definitions and numerical controls. The host first reads those files with material
search and existing document tools, then records the small set of facts needed by the paper.
It does not infer a solver version, physical model or report definition from a filename.
Project Python files are read as definition text; they are never executed by this feature.

## Input

Add the optional `scientific_context` path to an existing manuscript outline or input.
The outline accepts absolute or relative paths, as it does for section inputs. A prepared
manuscript uses portable relative paths. Existing inputs without this field still work.

For a `method.txt` containing this exact first line:

```text
A used an energy-only warm start followed by a coupled check.
```

the host can prepare:

```json
{
  "cases": [{"id": "A"}],
  "facts": [{
    "id": "A-procedure",
    "case_ids": ["A"],
    "section_ids": ["methods", "discussion"],
    "kind": "solution-stage",
    "name": "Solution procedure",
    "text": "An energy-only warm start preceded the coupled check for A.",
    "stage": "warm start then coupled check",
    "source": {
      "path": "method.txt",
      "locator": "L1",
      "excerpt": "A used an energy-only warm start followed by a coupled check."
    }
  }],
  "comparisons": []
}
```

Source paths resolve beside this JSON. The excerpt must match its complete one-based line
range exactly (`L1` or `L1-L3`). Files can be UTF-8 text, Markdown, JSON, CSV or Python text.
Facts have explicit case and section scopes; optional `stage`, `domain` and `operator`
describe the quantity only where the record supports them. A single control case's software
version is not silently assigned to other cases.

A comparison has `id`, `case_ids`, `section_ids`, `fact_ids` and `text`. Its case scope must
match its linked facts. Explicit `status` is `recorded`, `conflict` or `unknown`, with
`recorded` as the default. An unknown fact can omit its source. A recorded comparison cannot
promote linked conflict/unknown facts. These labels organize the host's assessment; exact
source matching proves location, not physical validity or independent verification.

## Use the existing writing route

```powershell
cfdpaper write . --artifact manuscript --outline outline.json --output writing
cfdpaper write . --artifact manuscript --package writing --context-for methods --output methods-task
```

The package root and relevant section tasks contain `scientific-context.md` for reading,
`scientific-context/context.json` for relationships, and `scientific-context/sources/` for
the copied records. A comparison's supporting facts travel with it even if originally
assigned to another section; their original case/stage scope remains visible.

The readable context also lists literal parameters from linked JSON records with exact
JSON Pointers. It prioritizes material, boundary, geometry and solver fields, with a visible
limit of 200 primitive values. This helps the host retain numerical inputs that a short fact
summary might omit. Source parameters remain file records; the host checks their case and
stage applicability. Unreadable JSON keeps its located text and an explicit issue, while
other readable records remain available. `read_source_parameters` can select sections and
change the limit for a focused task.

Write concise Methods from these records, connect Results and Discussion to their actual
operators and controls, and retain unresolved definitions in working notes. The feature
does not insert the source inventory into the published paper or rewrite author prose.
When facts or their source text change, reassembly includes affected sections and dependent
passages in the existing change report. Whole-paper and standalone section review packages
carry the same readable records. Copy the whole manuscript directory to resume elsewhere.

The CLI can also be invoked as `python -m cfdpaper`; both forms use the same commands.

## Runnable example

```powershell
python examples/material-analysis/run_scientific_context.py --output C:/Temp/wall-context
```

This reuses the invented wall-partition tutorial's existing calculations, native table and
editable equation. It produces a prepared workspace, a current Results task, an assembled
candidate and `manuscript.docx`. The example is a recorded software replay, not an AI writing
benchmark or CFD validation. Use a fresh output directory.
