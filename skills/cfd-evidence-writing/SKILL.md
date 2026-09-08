---
name: cfd-evidence-writing
description: Use when writing a bounded CFD results paragraph from an approved figure delivery, or a host-AI results subsection from supplied figures and structured evidence.
---

# CFD evidence writing

## Trigger

Use after checkpoint 2 when a current figure delivery has passing QA and a matching paragraph duty.
Alternatively, use the results-section path for one or several supplied figures with declared
evidence and writing duties; it does not require the legacy checkpoint pipeline.

## Do not trigger

Do not use for a full manuscript, independent literature synthesis, invented numbers or unsupported
mechanisms. The legacy paragraph path must not introduce new case comparisons or rewrite a failed
or stale figure into a plausible narrative. Section comparisons must stay within supplied evidence.

## Inputs

- `PROJECT_ROOT` with checkpoint 2 and current figure, analysis, ceiling, and paragraph-duty
  artifacts.
- The author identity only when recording final acceptance.
- For sections: JSON with `section_id`, `title`, `question`, `figures`, `evidence`, `duties`, and
  optional `context`; relative image paths resolve from that input file. Use PNG, JPEG or TIFF.

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
are retained, and reader-facing prose is separate from review notes. Supplied source data files are
not copied or independently verified; only structured evidence and figures enter the package.
