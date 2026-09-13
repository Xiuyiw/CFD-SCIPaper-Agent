# Manuscript workspace tutorial

Development example for the v0.7 workspace. Install the repository in editable mode with the
`docs` extra. This reuses the public analytical pipe reference, not private P04 or company data.
The three sample drafts are authored tutorial fixtures; the CLI assembles them and does not
claim to have autonomously written a scientific paper.

```text
python examples/manuscript-workspace/prepare_example.py my-source
cfdpaper write my-source --artifact manuscript --manuscript-input my-source/manuscript-input.json --output my-package
cfdpaper write my-source --artifact manuscript --package my-package --draft my-source/drafts.json --output my-manuscript
cfdpaper write my-source --artifact manuscript --package my-manuscript --docx --layout near-reference --output my-manuscript.docx
```

Add `--pdf-preview` to the final command if LibreOffice is installed. Every output must be a new
path. Read `my-package/TASK.md` and the section tasks when supplying your own host-written drafts.

The manifest binds a Methods section and two Results sections to a shared paper spine. Methods
has a native table and equation. Results reuse the existing tutorial figures. Figure and table
references use supported tokens and are numbered globally in spine order. Reorder the spine
and assemble to a different directory to inspect `numbering.json`; literal numbers in free prose
are deliberately not rewritten. Editing source CSVs triggers recomputation of bound result values,
but the host must reconsider associated trend statements and interpretations.

To refer to a Methods equation from Results, use `{{equation:methods/local-equation-id}}`.
The same `section_id/local_id` qualification works for table and figure tokens, including forward
references. Use IDs from the input/draft, not the numbers of an earlier assembled version.

This demonstrates organization, source-bound numbers and editable document structure. The simple
reference plots are not examples of complex mechanism graphics, and the short tutorial is not
a publication-ready full manuscript. Its DOCX style uses the project's default two-character body
indent and zero paragraph spacing; figure captions, tables, equations and headings are separate.

## Continue after moving the workspace

Copy the entire assembled `my-manuscript` directory to a working location and read its
`CONTINUE.md`. Edit the intended `sections/SECTION_ID/draft.json`, leaving unrelated drafts
unchanged, then run:

```text
cfdpaper write . --artifact manuscript --package working-copy --draft working-copy/drafts.json --output next-manuscript
```

The original source directory and preparation package are no longer required. Sources, local
identities, writing instructions and shared context travel with the candidate. Reordering the
spine updates numbering and the next section tasks. The CLI does not import edits made only in
Word, rewrite scientific interpretations, or infer author approval.
