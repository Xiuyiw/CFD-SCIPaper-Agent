# Two figures to an editable scientific subsection

Install with `python -m pip install -e ".[docs]"` from the repository root.
The following commands create fresh directories relative to your current directory:

```text
python examples/section-writing/prepare_example.py demo-source
cfdpaper write demo-source --artifact results-section --section-input demo-source/input.json --output demo-package
```

Give `demo-package/TASK.md` and its entire folder to your host AI, with the installed
`cfd-evidence-writing` skill. It reads the supplied images and evidence, answers the
scientific question, and writes a JSON draft. For a reproducible tutorial instead,
the next command uses the provided, explicitly authored `sample-draft.json`:

```text
cfdpaper write demo-source --artifact results-section --package demo-package --draft demo-source/sample-draft.json --output demo-section
cfdpaper write demo-source --artifact results-section --package demo-section --docx --output demo-section.docx
```

The source is an analytical laminar pipe reference, **not CFD validation data**.
It compares pressure drop with fully developed Nusselt number under fixed properties
and uniform wall heat flux. The script supplies CSV, runnable source, SVG/PDF and
PNG/TIFF. Existing files are not overwritten; choose a new output for each revision.

## Your own results

Use the example `input.json` as the format reference. Supply a question, one or more
PNG/JPEG/TIFF figures, evidence with exact source locations, and subsection duties.
Evidence can be observations, metrics, interpretations, or verified literature.
Multiple figure and evidence records can come from different analyses. Define the
comparison, normalization, sampling and control volume before inferring mechanisms.
The adapter does not read arbitrary solver data or verify declared source files.

In the host draft, `{{value:ID}}` preserves the metric's declared numeric string and
unit; `{{figure:ID}}` resolves a figure reference; `{{cite:ID}}` numbers supplied
literature in first-use order. Unknown tokens or missing declared coverage are
rejected. Free prose still needs scientific reading: structural checks do not
prove a mechanism or verify a manually typed number. No literature is invented.

## Review and editing

`demo-section/section.md` and DOCX contain prose and captions. Unresolved methodology
questions belong in `evidence-notes.md`. `review-packet/` contains the manuscript,
images, structured inputs, draft and review prompt for a separate external AI.
Source-data files themselves must be supplied separately if needed by that reviewer.

Import its response in this format:

```json
{"suggestions": [{"target": "paragraph 1", "comment": "Clarify the comparison", "recommendation": "State the fixed geometry"}]}
```

```text
cfdpaper write demo-source --artifact results-section --package demo-section --review review.json --output suggestions.json
```

Importing suggestions neither revises nor approves the manuscript. Apply useful
suggestions in a new draft and assemble a new output. Author edits to an exported
DOCX are not round-tripped automatically: keep that file as the author version.
The preview is an editable subsection, not a journal-specific typesetting template.
