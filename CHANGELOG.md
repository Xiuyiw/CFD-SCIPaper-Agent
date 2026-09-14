# Changelog

## [Unreleased]

## [0.9.0] — 2026-09-14

### Added

- Whole-manuscript review packages with global paragraph/object locations and complete
  report return, followed by selected host-editing tasks that preserve the reviewed original.
- Optional shared-evidence locations for scientific revisions across Results, Discussion,
  Abstract and Conclusions. Links identify passages to reread, not automatic edits.
- `scalar_select` and exact `paired_change` calculations in section inputs, including
  explicit temperature-rise references for relative changes of absolute temperatures.
- Portable figure-source directory trees and preview resolution at the intended printed width.
- A runnable synthetic whole-paper review/edit/reassembly example using the installed CLI.

### Fixed

- Native equation grouping and subscripts, short-table pagination, and Celsius display labels.
- Material-analysis proposal comparison qualifications remain distinct from paired-record
  selectors; existing population/partition proposals retain their format and validation.

The v0.9 candidate supports host-led scientific review and revision. Model adequacy, literature
support and submission readiness still require evidence-specific author assessment.

## [0.8.0] — 2026-09-13

### Added

- Shared CSL JSON bibliographies and optional Pandoc BibTeX import, with DOI deduplication,
  claim-specific source excerpts and section writing guidance for literature and summaries.
- Cross-section evidence bindings, keywords and targeted change reports for source data,
  definitions, references and author drafts. Bound values resolve from their current owner.
- Optional Pandoc CSL formatting for first-citation-order numeric bibliographies, retaining
  bold and italic runs in Word. Detached review packets carry relevant source excerpts.
- A seven-section analytical manuscript tutorial, including shared citations and summary updates.

Scientific interpretation remains host/author work; an excerpt match or formatted bibliography
does not establish that a source supports the manuscript claim.

## [0.7.0] — 2026-09-13

### Added

- Multi-section manuscript workspaces with a shared paper spine, terminology and
  Methods-specific writing guidance. Section-qualified figure, table and equation
  references follow the current chapter order.
- Portable continued writing: assembled candidates retain local inputs, source
  files, drafts and Skills, with a continuation guide and relative draft paths.
- Host drawing tasks for data figures and conceptual diagrams, with external-tool
  guidance and import of editable artwork and previews. Returned artwork is not
  automatically treated as scientifically approved.
- A three-section analytical manuscript tutorial and installed-wheel CI coverage.

### Fixed

- Editable dotted and overbar math expressions and table-note pagination in Word.

The manuscript workspace organizes host-authored sections; whole-paper literature
reasoning and autonomous publication-quality drafting remain outside this update.

## [0.6.0] — 2026-09-13

### Added

- Material profiling and portable host-assisted analysis proposals from exported CSVs,
  readable method notes and existing figures, connected to deterministic table calculations
  and results-subsection writing.
- Explicit plot, prose, table or custom presentation choices; non-plot choices no longer
  require placeholder images. Custom artwork is not automatically generated.
- Analysis and writing skills travel with their respective task packages, including
  the writing reference for physical interpretation and editable tables/equations.
- A reproducible synthetic material-analysis example with an optional plot route.

### Fixed

- Body paragraphs use configurable first-line indentation and before/after spacing,
  independently of captions, headings, tables and references.
- Area and compound flux units use readable scientific display notation without changing values.

## [0.5.0] — 2026-09-12

### Added

- Declared CSV population and partition calculations, with `result_ref` bindings
  that resolve current values, units and source records into subsection text.
- SVG/PDF/PNG/TIFF delivery with configurable physical plot dimensions and font sizes.
- Manuscript-scale figure sizing, near-reference or after-text placement, and an
  optional PDF preview using an installed LibreOffice.
- Native editable Word tables, display equations and inline mathematics through
  a finite structured expression format.
- A portable tutorial with original tables, four-format figures, table/equation
  examples and both Word layouts; expanded offline writing-skill examples.

### Fixed

- Protected locally refined plotting scripts from automatic template replacement.
- Kept endpoint markers visible without changing the plotted data or axis limits.
- Removed source-checkout dependencies from packaged writing examples.

## [0.4.0] — 2026-09-08

### Added

- Host-AI figure-grounded subsection packages and multi-evidence paragraph duties.
- Exact evidence tokens, Markdown assembly, editable DOCX with embedded figures,
  and external-review packets with separate suggestion import.
- A two-figure analytical tutorial with source data and SVG/PDF/PNG/TIFF outputs.
- On-demand mechanism-writing guidance in the existing writing skill; all four
  skills are now included in installed wheels.

### Fixed

- Prevented case-insensitive figure-ID collisions from replacing images on Windows.
- Excluded local archives and workspace-only instructions from source distributions.

### Changed

- Updated the GitHub Actions checkout, Python setup, and artifact upload steps to their Node.js 24
  releases.

## [0.3.1] — 2026-09-04

### Fixed

- Made CLI help assertions deterministic when continuous-integration terminals emit ANSI styling.
- Corrected a line-ending-sensitive stale-source regression so Linux and Windows test the same
  scientific-input change.
- Updated release-package formatting and version checks so the wheel smoke test runs consistently
  across the supported matrix.

### Documentation

- Aligned the README, architecture, limitations, roadmap, release notes, and documentation index
  with the evidence-to-figure-and-paragraph workflow delivered in v0.3.

## [0.3.0] — 2026-09-04

### Added

- Strict scientific intake for declared CFD cases, observations, units, source locators, comparison
  roles, convergence, conservation, verification, and validation.
- Author-locked QoI analysis over observed discrete cases with evidence-bounded reporting ceilings.
- Reproducible figure delivery with source data, a runnable plotting script, SVG and PNG outputs,
  caption, and data, narrative, and visual QA results.
- One results paragraph with exact numeric backlinks and unchanged final author approval.
- Four thin workflow Skills and a public steady-laminar-pipe example with positive, negative, and
  adversarial expectations.

### Changed

- Consolidated public documentation under `docs/` and added a documentation index.
- Simplified release CI to test, build, install, and smoke-test the public repository directly.
- Removed internal snapshot-export artifacts from the public source tree.

### Boundaries

- Inputs must use the documented structured records, observation, question, and topic contracts;
  arbitrary native solver cases are not ingested.
- Analysis remains discrete and evidence-bounded; no interpolation, smoothing, continuous optimum,
  full manuscript, reference workflow, or submission document export is claimed.
- `review`, `revise`, and `export` remain unavailable roadmap commands.

## [0.2.0] — 2026-08-31

### Added

- Evidence-bounded offline generation of two to four provisional paper-topic candidates from
  mature structured scientific records.
- Explicit QoI-definition assessments and case-level convergence, conservation, and evidence
  bindings in the local SQLite project state.
- Recoverable opportunity, candidate, provenance, and generation-report artifacts.
- Deterministic reuse, explicit regeneration, author-file precedence, and provider fallback
  boundaries.
- Public positive and negative end-to-end regressions for defensible and incomplete evidence.

### Boundaries

- Ordinary indexed files are not automatically promoted to mature scientific records.
- Generated artifacts are project-local formats rather than stable public interchange schemas.
- Analysis, figure production, writing, review, revision, export, and native solver ingestion
  remain outside this release.

## [0.1.0] — 2026-08-30

### Added

- Initial public CLI for project initialization, status, inspection, and author-supplied topic
  ranking.
- Project-local SQLite state, incremental source indexing, checkpoints, and planning reports.
- Non-sensitive copied-directory Quickstart with synthetic data.
- Public architecture, roadmap, limitations, contribution guidance, release notes, and citation
  metadata.

### Known limitations

- Analysis, figure, writing, review, revision, export, and general solver-native extraction remain
  roadmap work.
- Indexed files are not automatically promoted to verified scientific evidence.
