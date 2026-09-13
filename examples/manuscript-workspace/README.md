# Manuscript workspace tutorial

Development tutorial for the v0.7 manuscript workspace, which is not yet released. Use the
current `workstream/v07-writing-figures` checkout; the published v0.6.0 package does not contain
this workflow. The example uses a public analytical pipe reference and three supplied sample
drafts. The CLI prepares writing tasks, assembles drafts and exports Word; a host AI and the
author supply scientific prose when using your own evidence.

## Install and prepare the example

Use a Python 3.10–3.12 environment. From the repository root, install this checkout with the
`docs` extra and check that the manuscript option is present:

```text
python -m pip install ".[docs]"
cfdpaper write --help
```

This is a normal, non-editable installation built from the checkout. An installed wheel built
from the same development code also works; editable installation is not required. Keep both
`examples/manuscript-workspace/` and `examples/section-writing/` available for the preparation
script, which reuses the latter's public reference generator. Examples are not inside the wheel.

Run the following from the repository root. `my-source` and every `--output` path must not
already exist; choose new names to repeat the tutorial.

```text
python examples/manuscript-workspace/prepare_example.py my-source
cfdpaper write my-source --artifact manuscript --manuscript-input my-source/manuscript-input.json --output my-package
```

`my-source` contains the source CSV, two figures, section inputs and sample drafts.
`my-package/TASK.md` is the whole-manuscript writing entry point; section-specific instructions
are at `my-package/sections/methods/TASK.md`, `sections/hydraulics/TASK.md` and
`sections/thermal/TASK.md` (the latter two paths are also relative to `my-package`). Each section
includes its writing Skill, evidence and shared manuscript context.

## Assemble the three-section draft

Use the supplied drafts for this runnable demonstration:

```text
cfdpaper write my-source --artifact manuscript --package my-package --draft my-source/drafts.json --output my-manuscript
cfdpaper write my-source --artifact manuscript --package my-manuscript --docx --layout near-reference --output my-manuscript.docx
```

Read `my-manuscript/manuscript.md` or open `my-manuscript.docx`. The Word draft contains Methods,
Hydraulic response and Thermal response sections, with one native table, one equation and two
figures. Add `--pdf-preview` to the export command if LibreOffice is installed.

For host-written prose instead, give the host `my-package/TASK.md` and the section tasks.
Have it create each `my-package/sections/SECTION_ID/draft.json`; then use
`--draft my-package/drafts-template.json` in the assembly command. That mapping lists draft
paths relative to itself. The supplied drafts are examples of the required JSON structure.

The manifest binds a Methods section and two Results sections to a shared paper spine. Methods
has a native table and equation. Results reuse the existing tutorial figures. Figure and table
references use supported tokens and are numbered globally in spine order. Reorder the spine
and assemble to a different directory to inspect `numbering.json`; literal numbers in free prose
are deliberately not rewritten. Assembly recomputes bound values from the package's source CSVs,
not from the earlier `my-source` directory. The host must reconsider associated trend statements,
interpretations and figures when data change.

To refer to this Methods equation from Results, use `{{equation:methods/1}}`.
The same `section_id/local_id` qualification works for table and figure tokens, including forward
references. Use IDs from the input/draft, not the numbers of an earlier assembled version.

This demonstrates organization, source-bound numbers and editable document structure. The simple
reference plots are not examples of complex mechanism graphics, and the short tutorial is not
a publication-ready full manuscript. Its DOCX style uses the project's default two-character body
indent and zero paragraph spacing; figure captions, tables, equations and headings are separate.

## Continue after moving the workspace

Copy the entire assembled `my-manuscript` directory to a new location named `working-copy`,
keeping the original candidate unchanged. On a new computer, install the same development
code with the `docs` extra first; copying the manuscript does not install the CLI.

Read `working-copy/CONTINUE.md`, `manuscript.md` and `manuscript-input.json`. Before editing,
read `working-copy/sections/SECTION_ID/TASK.md`, its `manuscript-context.json`, Skill,
`input.json` and `draft.json`, plus the adjacent sections. The assembled candidate's entry point
is `CONTINUE.md`, not a root `TASK.md`.

For example, revise only `working-copy/sections/thermal/draft.json`, leaving the Methods and
Hydraulics drafts unchanged. From the directory containing `working-copy`, run:

```text
cfdpaper write . --artifact manuscript --package working-copy --draft working-copy/drafts.json --output next-manuscript
cfdpaper write . --artifact manuscript --package next-manuscript --docx --layout near-reference --output next-manuscript.docx
```

The original source directory and preparation package are no longer required. Sources, local
identities, writing instructions and shared context travel with the candidate. Reordering the
spine in `working-copy/manuscript-input.json` updates numbering and the next section tasks on
assembly. Use `drafts.json`, not the historical `author-drafts.json` mapping. Edit the local-ID
drafts, not the generated `manuscript.md` or `section.json`; reconcile any Word-only edits into
the corresponding draft before re-exporting. The CLI does not import Word edits, rewrite
scientific interpretations, or infer author approval.
