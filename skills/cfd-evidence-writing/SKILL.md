---
name: cfd-evidence-writing
description: Write evidence-linked CFD sections or coordinate a host-authored manuscript with a paper spine, shared terminology and global references.
---

# CFD evidence writing

## Trigger

Use after checkpoint 2 when a current figure delivery has passing QA and a matching paragraph duty.
Alternatively, use the results-section path for one or several supplied figures with declared
evidence and writing duties; it does not require the legacy checkpoint pipeline.

## Do not trigger

Do not claim autonomous full-paper generation, independent literature synthesis, invented numbers
or unsupported mechanisms. The legacy paragraph path must not introduce new case comparisons or rewrite a failed
or stale figure into a plausible narrative. Section comparisons must stay within supplied evidence.

## Inputs

- `PROJECT_ROOT` with checkpoint 2 and current figure, analysis, ceiling, and paragraph-duty
  artifacts.
- The author identity only when recording final acceptance.
- For sections: JSON with `section_id`, `title`, `question`, `figures`, `evidence`, `duties`, and
  optional `context`; relative image paths resolve from that input file. Use PNG, JPEG or TIFF.
- For CSV exports: optional `table_calculations` declares operation, column roles, units,
  physical domain and grouping. Select these from the actual source and method description;
  ask the author only when an unresolved definition would change the interpretation.

## Outputs

- `results-paragraph.txt`, `numeric-backlinks.json`, and `delivery.json` under
  `.cfdpaper/outputs/write/`.
- Checkpoint 3 after final author acceptance, without changing the paragraph or backlink files.
- Sections: a portable writing package, assembled Markdown/JSON, separate evidence notes, a
  self-contained review packet, editable DOCX, and separately imported reviewer suggestions.

## Prerequisites

Complete `cfd-figure-production`. Figure delivery and all QA results must remain current and bound to
the same candidate, analysis, ceiling, and scientific inputs for the legacy paragraph path.
For sections, supply readable figures, exact source locators and resolvable evidence/figure IDs.
Install the optional `docs` extra for DOCX. The host AI, not the CLI, writes the scientific prose.

## Workflow

### Existing results-paragraph path

1. Render the bounded results paragraph:

   ```text
   cfdpaper write PROJECT_ROOT --artifact results-paragraph
   ```

2. Check that every number has a backlink and that the prose does not exceed the approved duty or
   claim ceiling.
3. After the author accepts the unchanged artifact, record checkpoint 3:

   ```text
   cfdpaper write PROJECT_ROOT --artifact results-paragraph --approve-final --author "AUTHOR_NAME"
   ```

### Results-section: four CLI actions with host writing between them

`PROJECT_ROOT` is an existing directory. Every `--output` must be a fresh path; retain earlier
author edits. For section writing, first read [mechanism-subsections.md](references/mechanism-subsections.md)
in full; it guides single-figure reasoning and multi-evidence synthesis without canned prose.

1. Prepare supplied inputs:

   ```text
   cfdpaper write PROJECT_ROOT --artifact results-section --section-input section-input.json --output writing-package
   ```

   Read `writing-package/TASK.md` and `input.json`; open the actual images. The host AI writes a
   fresh `draft.json` matching `draft-template.json`, including paragraphs, captions, evidence notes
   and truthful image-observation status. Preparation does not generate this scientific draft.
   If present, read `table-results.json` before writing. Bind calculated metric evidence with
   `result_ref`, omitting manual `value` and `unit`; use `{{value:ID}}` in paragraphs and captions.
   Assembly recomputes these values from the package CSVs. Population CV uses
   equal record weights; partition sums refer to supplied regions, not automatically the full
   physical surface. Use the offline [table example](references/mechanism-subsections.md#exported-table-example)
   for declarations, source records and numeric selection.

2. Assemble the host-authored draft:

   ```text
   cfdpaper write PROJECT_ROOT --artifact results-section --package writing-package --draft draft.json --output section-v1
   ```

3. Export editable text, figures and captions:

   ```text
   cfdpaper write PROJECT_ROOT --artifact results-section --package section-v1 --docx --output section-v1.docx
   ```

4. Give `section-v1/review-packet/` to the external reviewer; follow its review prompt. Import the
   returned JSON suggestions separately:

   ```text
   cfdpaper write PROJECT_ROOT --artifact results-section --package section-v1 --review review.json --output review-suggestions.json
   ```

Section assembly checks references, tokens, assets and declared duty coverage, not semantic truth.
It neither creates checkpoint 3 nor accepts `--approve-final`. Review import does not revise or
approve the manuscript; apply author-selected revisions in a new draft and fresh output.

## Multi-section manuscript workspace

Use `--artifact manuscript` to organize supplied sections under an existing `PaperSpine`:

```text
cfdpaper write PROJECT_ROOT --artifact manuscript --manuscript-input manuscript-input.json --output manuscript-package
cfdpaper write PROJECT_ROOT --artifact manuscript --package manuscript-package --draft drafts.json --output manuscript-candidate
cfdpaper write PROJECT_ROOT --artifact manuscript --package manuscript-candidate --docx --layout near-reference --output manuscript.docx
```

The manifest supplies `title`, `spine`, and `sections` mapping each `section_id` to its section
input path; optional `context` and `terms` carry the whole-paper question and shared terminology.
Read the workspace TASK and each section's TASK. Write to the section's purpose and role, not a
repeated results-paragraph template. For Methods read
[methods-sections.md](references/methods-sections.md); for Results read the mechanism subsection
reference. Keep missing physical definitions in notes, not invented prose. The drafts JSON maps
every section ID to its host-authored draft path. Preserve drafts and inputs; assembling existing
text does not demonstrate independent scientific writing.

Use supported figure/table/equation/citation tokens for cross-references. Workspace assembly
rebinds them to global numbering in spine order; local free-text numbers are not silently rewritten.
For an object in another section, qualify its ID, for example
`{{equation:methods/resistance}}`, `{{table:methods/design}}` or
`{{figure:results/heat-partition}}`. These three object types support forward references as well.
Keep ordinary local tokens unchanged; cross-section citation/value tokens are not supported.
Inspect `numbering.json` and the rendered pages after reordering. This path coordinates sections and
exports an editable candidate, not a finished or author-approved full paper.

### Continue an existing manuscript

An assembled workspace includes `CONTINUE.md`, portable `drafts.json`, each section's
`input.json`, local-ID `draft.json`, sources, Skill and current manuscript context. Copy the whole
workspace to resume with another host. Preserve the current version, edit only the intended draft
in a working copy, and assemble that copy to a fresh directory using its own `drafts.json`.
`author-drafts.json` retains historical paths and is not the continuation entry point.

Read the current manuscript and adjacent sections before editing. Methods must introduce the
domains, operators and comparisons used in Results; Results should not repeatedly restate those
definitions. Keep the shared spine/terms current. Source or definition changes require a fresh
scientific reading of dependent claims, not only numeric replacement. Word-only edits are not
automatically imported: reconcile them with the authoring draft before exporting again.

## Manuscript paragraph and page formatting

Use the author's requested format first, or the target venue's supplied template; do not present
one house style as a universal SCI requirement. For this project's requested manuscript style,
body paragraphs use a two-character first-line indent and 0 pt before/after spacing. Implement
indentation as paragraph formatting, not inserted spaces, tabs or blank paragraphs. Keep line
spacing separate from paragraph spacing. Explicit venue/author overrides must remain possible.
The input style fields are body_first_line_indent_chars, body_space_before_pt and
body_space_after_pt; the exporter applies them only to body paragraphs. A zero-figure section is
valid when prose or a native table carries the argument; do not create a placeholder image.
In the single-section path, table/equation IDs are displayed literally; assign labels (1, 2, S1 as
appropriate) rather than internal slugs, and use the same IDs in tokens. Do not manually renumber
only the caption or only a cross-reference.

Scope body formatting to body paragraphs: headings, captions, table cells, references, equations
and image anchor paragraphs have their own alignment, indentation and spacing. A generic Word
Normal style or exporter default must not silently decide manuscript typography.

Verify the actual paragraph properties and the rendered pages, including indentation, before/after
spacing, readable figure size, caption proximity and page breaks. No clipping alone is not a format
pass. If the exporter cannot implement a required property, report the specific implementation gap;
do not mark formatting complete or quietly substitute manual repair for an Agent capability.
When the user requests rule/skill improvements, update those instructions and record implementation
follow-up without editing their example document or redrawing its figures.

## Stop conditions

- Legacy paragraph: stop when the figure delivery is missing, failed, or stale.
- Legacy paragraph: stop on exit code 4 and run the earliest rerun command printed by the CLI.
- Legacy paragraph: stop when a number lacks a backlink or an interpretation exceeds the claim ceiling.
- For sections, stop on missing/corrupt figures, unresolved tokens/IDs, absent required captions or
  duty coverage, and existing output paths. Repair the input or draft; do not override validation.

## Fallback

For the legacy paragraph, return to figure production when QA or delivery files changed, or to
analysis when scientific inputs changed. If no author-approved physical interpretation exists, keep the paragraph to the supported
observation instead of adding a generic explanation.
For sections, attribute unviewed images to the author description rather than claiming to have seen
them. Put unsupported mechanism questions in `evidence_notes` until evidence becomes available.

## Public fixture reference

The positive paragraph and backlinks must match `examples/steady_laminar_pipe/oracle.json`. The
`negative/` variants must not create text after a blocking defect. Adversarial requests for inferred
area integrals, smoothing, continuous optima, mechanism escalation, or approval override must not
appear in the delivered paragraph.

## Success criteria

The paragraph is natural scientific prose, every value is traceable to the current analysis, and
checkpoint 3 records author acceptance without changing delivered bytes. Running this Skill alone is
not scientific or author approval.
For sections, the host-authored argument remains reviewable, source records and exact token values
are retained, and reader-facing prose is separate from review notes. Explicit `source_files` with
relative `sources/` paths are copied into writing/review packages. They are not automatically
scientifically verified. Declared table calculations run during preparation and again during
assembly; the result, source records, units and definitions travel to the reviewer. These
calculations support reasoning; they do not automatically establish causality, resolve a
wall-temperature definition conflict, or check every number in free prose.
