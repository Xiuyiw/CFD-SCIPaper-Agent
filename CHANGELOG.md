# Changelog

## [Unreleased]

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
