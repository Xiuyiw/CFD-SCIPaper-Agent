# Formal manuscript and Word author return

Use this mode for an already assembled whole-manuscript candidate. Keep its
scientific question, current figures and source definitions; do not repeat intake
or ask the author to retype their edits into JSON. This is bounded collaboration
with a generated Word file, not arbitrary DOCX reconstruction.

## Give the author an editable file

```text
cfdpaper author --package CURRENT_CANDIDATE --output AUTHOR_WORKSPACE
```

The new directory contains `manuscript.docx`, its Markdown view, and a continuing
`candidate/` with stable source paragraph identities. Preserve that whole directory.
The source candidate remains unchanged. Word controls are editable, not locked or
mapped to automatically replacing XML. A Word save may split runs or localize style
IDs; stable object identity does not depend on those implementation details.

Ask for one concentrated review: ordinary body/caption wording, local bold/italic
or superscript/subscript, paragraph formatting, and anchored comments. Do not
require the author to understand object IDs or metadata. Bound values, units,
formula and citation fields and picture contents stay connected to sources;
editing their visible content produces a localized conflict, not a new result.
An ambiguously removed anchor is not an instruction to delete its scientific text.
Use a clear author comment for deletion when ordinary deletion removes the anchor.

## Recover against the current scientific candidate

```text
cfdpaper author --package CURRENT_CANDIDATE --return-docx AUTHOR_RETURN.docx --output NEW_RETURN
```

If evidence changed while the author was editing, `CURRENT_CANDIDATE` is the newly
assembled candidate from the continuing source workspace, not the old reading copy.
Stable IDs must be retained in source drafts. The tool uses the generated baseline,
author return and current candidate to combine non-overlapping edits. It saves the
original return, `candidate/`, new Word/Markdown, ordinary comments and `merge.json`.
Read `CONTINUE.md` and unresolved conflicts before presenting the result as final.

- Different-block text edits can merge. An overlapping edit retains both versions
  in the conflict record and keeps current scientific content in the candidate.
- New ordinary paragraphs receive stable identities. A move within a section is
  supported; cross-section moves and unsupported structures require reconciliation.
- Simple table column labels can be recovered. Numerical cells, table geometry,
  formula/field changes and unknown objects are not silently flattened.
- A local `Figure`/`Fig.` abbreviation keeps the same bound object and follows later
  renumbering. It does not rename unrelated blocks or permit changing an object's number.
- Deleting an entire bound sentence/clause can be recovered when its removal is
  unambiguous from the saved baseline. An orphaned anchor or a changed numerical
  value is still a localized conflict, not permission to infer a replacement.
- Comments remain suggestions, not approval. Inspect their actual anchor after
  export; ambiguous placement is listed in the layout report.
- An unaccepted tracked change remains unresolved. Do not accept it implicitly.
- Ordinary proportional image sizing is presentation; crop/content/aspect changes
  require explicit reconciliation. The author-local plotting script remains the
  source for future figure refreshes, not an older generated template.

The three-way operation does not decide whether a new mechanism statement is
scientifically justified. Review changed interpretations using current evidence.
Separate numerical display updates from region/operator/weight/time-support changes.
A definition change can require revising Methods, captions, abstract and conclusions
even when the resulting number happens to stay the same. Conversely, Word's unit
spacing, minus glyph or localized style ID is not a new scientific observation.

For a research workspace with executable local figure recipes, preserve recovered
drafts and presentation while rebuilding current observations:

```text
cfdpaper research --workspace RESEARCH_WORKSPACE --baseline PREVIOUS_BUILD --author-candidate RETURN/candidate --output NEW_BUILD
```

The recovered candidate supplies local-ID drafts and presentation, not copied
scientific numbers. The research workspace still supplies current inputs, region
definitions and author-local plotting scripts. Its isolated new copy is retained
under `NEW_BUILD/workspace/` for the next iteration. Do not paste compiled prose
over those source drafts or replace the local script with an older template.

## One scientific content, ordered views

Source drafts may give paragraphs persistent `paragraph_id` values and an explicit
`block_order`, for example:

```json
["paragraph:definition", "equation:balance", "paragraph:interpretation", "table:properties"]
```

An explicit order lists every local paragraph/figure/equation/table once. A figure
caption travels with its figure. Reordering does not change object identity or
manually assigned scientific values. Do not invent a second numbering or facts file.

```text
cfdpaper author --package CANDIDATE --format docx --profile research --output paper.docx
cfdpaper author --package CANDIDATE --format md --profile report --output report.md
cfdpaper author --package CANDIDATE --format tex --profile conference --output conference.tex
```

Profiles change presentation, not scientific findings or included evidence.
Research defaults use a two-character body indent and zero before/after spacing;
headings, captions, equations and tables have their own styles. An explicit template
takes precedence. Word template import currently uses its styles and final-section
geometry, not arbitrary multi-section title/author layouts. LaTeX templates use one
`%%CFDPAPER_BODY%%` marker and an optional `%%CFDPAPER_TITLE%%`; retain needed packages.
Do not describe this as complete compliance with every journal/conference template.

Check real Word/PDF pages and actual LaTeX compilation. Source creation, successful
JSON parsing or an environment skip does not establish manuscript readiness.
