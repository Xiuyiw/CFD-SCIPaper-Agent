# Continue a research task on another host

Use the installed CFD-Paper-Agent package and the current task workspace. Read
its `TASK.md`, `RESEARCH.md` or `CONTINUE.md` as applicable, then the definitions
and selected sources needed for the question. Do not reconstruct facts from the
old chat or load unrelated project history.

## Choose the available tool route

An ordinary terminal host can keep using the documented CLI or Python business
functions. An MCP host can launch `python -m cfdpaper.mcp_server` after installing
the `mcp` extra. The server uses local stdio; it does not supply an AI model or
start a solver. It calls the same analysis, writing and author-return functions.

The task-sized tools are:

- `inspect_materials` and `prepare_analysis_task`: locate actual records and
  prepare the existing material/skill package, without running source scripts.
- `run_analysis_task`: compute a supported host-selected comparison and prepare
  its source-bound writing input. Read its returned artifact paths and current
  physical definitions; do not type its values into a second evidence list.
- `report_task`: for saved JSON scalar reports, select exact pointers and physical
  definitions once; the tool projects the records, calculates bound quantities
  and prepares Methods/Results/Discussion drafts with a native Results table.
- `research_task`: use the existing surface workspace for supported field
  analysis, attached diagnostics/figures and targeted refresh. Do not transform
  unrelated tabular or transient studies into fictitious surface fields.
- `writing_context` and `manuscript_task`: obtain current section context,
  assemble host-written drafts and export the same scientific content formally.
- `author_task`: prepare a managed Word copy or recover an actual Word return.
- `workbench_task`: export, inspect or restore a selected research workbench.

Choose the few tools the current task needs, not a fixed sequence through all
of them. Numerical definitions and provenance remain available in the located
full reports. Large arrays and element indices stay in files.

For raw JSON reports, prefer `report_task` over manufacturing a generic proposal.
Supply `root`, case IDs and relative JSON paths, and quantities with `id`, `label`,
`unit`, `domain`, plus either `pointer` or the pair `reference` and `comparison`.
A pair means comparison minus reference; optional `output_unit` performs unit
conversion. Selected pointers must identify the same physical quantity in all cases.
Use `case.sources` to name additional JSON records and `quantity.source_key` to
select one; without it the primary case source is read. A scalar pointer or either
paired endpoint may instead be an exact case-ID map containing every case. For
dimensionless method inputs use `unit: ""`; `table: false` retains their bound
evidence without filling the Results table with method parameters.

Optional `derived` entries compare existing base evidence IDs (`QUANTITY_CASE`),
not other derived entries. Select `field` from `difference`, `ratio`,
`relative_change` or `relative_reduction`; these mean comparison−reference,
comparison/reference, (comparison−reference)/reference and
(reference−comparison)/reference, respectively. Declare the reference denominator,
`domain`, `comparison_scope` and `definition_source` as `file:Lx-Ly`; use
`percentage: true` only when the selected relative result should display as percent.
This is a bounded comparison route, not arbitrary formulas or a chained DAG.
Both parent domains and the derived domain must match for this calculation.
A shared numerical-comparison domain does not establish equivalent physical
observation operators; retain their differences in labels and comparison scope.

Optional `formulas` maps IDs to `source` plus an `expression` using the existing
`MathNode` structure. Write `{{math:ID}}` directly in the paragraph: report assembly
supplies native editable Word math, while the author's paragraph-local
`inline_math` takes priority. No TeX parsing or manual AST copying into each draft
is needed. The [Python/CLI example](../../../docs/portable-workbench.md#saved-reports-to-writing-in-two-calls)
shows these declarations together.

Read the returned `writing_task` and compact `metrics`, fill its three `draft.json`
files, and call `report_task(workspace=PREPARED, drafts=PREPARED/workspace/drafts.json,
output=FRESH)`. That call rereads retained JSON and assembles DOCX/Markdown using
the supplied prose. Keep the bound table; do not retype its numbers. A value token
already includes its unit. Original records and method/support files remain in
the prepared workspace. This narrow route does not infer solver definitions,
reconstruct absent fields, or prove a mechanism from endpoint differences.
After source values or definitions change, re-read the affected physical
interpretation; token refresh alone does not update that reasoning.

For an existing CSV/NPZ comparison, `prepare_analysis_task` returns a proposal
example and schema. Adapt them to the actual columns and physical definitions,
then call `run_analysis_task` for the chosen candidate. Its `writing_package`
already contains computed evidence IDs, `result_ref` bindings, copied sources
and a draft template. Use that section input in the manuscript; do not retype
its results as fixed `metric.value` entries. Read the generated templates before
reading implementation modules to discover document schemas. The writing skill
explains native math and `shared_unit`; a value token normally includes its unit.

## Move the current work, not the whole computer

`cfdpaper portable --workspace CURRENT --output COPY` copies the selected
workspace. Optional `--baseline` and `--author` include the actual generation
baseline and author companion needed to continue. Keep the author's local
figure scripts and Word originals; do not replace them with installed templates.

At the destination, install the matching package and read `COPY/CONTINUE.md`.
`cfdpaper portable --inspect COPY` reports current entries and exact missing
references. When an external results root has moved, use `--restore COPY
--output NEW_COPY --external-roots roots.json`; the JSON maps original absolute
roots to the actual new roots. Do not guess another same-name source.

This copy contains selected research/manuscript state, not an arbitrary old
SQLite project, Python environment or complete native solver archive. Read the
reported missing item and continue independent work. Do not silently substitute
old results or ask the author to prefill all models, QoI and scientific answers.

## Resume the scientific work

New source-reading and plotting recipes should derive internal paths from their
own location or accept explicit input/output arguments, not hard-code the current
machine's working directory. Existing author scripts stay unchanged in the copy;
report their external path assumptions before running them on another machine.

Use the retained current drafts, definitions, local scripts and actual baseline.
An author's recovered candidate contributes wording and presentation, not new
raw numerical facts. With a research workspace, `research --author-candidate`
continues that wording against current science. Preserve unresolved comments.

After a value or definition changes, inspect the affected figures and wording;
refreshing tokens is not revising a physical explanation. Check new images at
their manuscript size and new DOCX/PDF pages. A host without a renderer can
produce an editable candidate but must not report that it inspected the pages.

Keep the first output before feedback. A different model name, Python process
or chat is not evidence of a second tool-using host. A resumed task containing
the author's current draft is a continuation, not an independent blind writing
trial. Report actual outcomes and leave unavailable evidence unavailable.
