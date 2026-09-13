# Limitations

CFD-Paper-Agent v0.8.0 is not a CFD solver and does not validate a model merely because result files
exist. It cannot replace domain expertise, experimental validation, source-literature verification,
or author responsibility.

The public CLI supports `init`, `status`, `inspect`, `plan`, `qualify`, `analyze`, `figure`, and
`write`. The implemented scientific path expects structured case records, located scalar
observations, a declared comparison, and a proposed QoI. It does not convert arbitrary Fluent,
STAR-CCM+, or other native solver files into complete scientific records. Guided intake is
experimental and still requires the author to supply the scientific meaning of the data.

The v0.6 material-analysis route can also start directly from exported CSVs and method notes,
without the structured topic-planning sequence. A host proposes the analysis and the author
selects it; population and partition calculations still need explicit definitions and support.

The manuscript workspace assembles host-authored sections with shared paper-spine context,
terminology and section duties. Its writing guidance covers Introduction, Methods, Results,
Discussion, Abstract and Conclusions; keywords appear after the Abstract. Supported tokens receive
global figure, table, equation and citation numbers. Guidance organizes supplied evidence but
does not supply missing model, mesh, validation or literature evidence.

Cross-section bindings refer directly to owning evidence. Declared table calculations are
recomputed when assembling a new candidate, and explicit section dependencies guide the change
report. `CHANGES.md` identifies sections and paragraph positions to reconsider; it does not infer
undeclared dependencies or verify the meaning of the prose. Literal numbers, interpretations and
figures are not automatically rewritten or regenerated.

An assembled candidate carries local drafts, sources and instructions for continued editing after
moving it. The destination needs a compatible CLI installation. Word-only edits must be reconciled
into the local drafts before re-export; there is no automatic Word-edit merge.

The local literature workspace preserves CSL JSON metadata and claim-specific support records.
It normalizes DOI identities, keeps aliases, and checks supplied excerpts against UTF-8 text files.
Without a DOI, only unambiguous complete title–author–year matches are merged; incomplete records
remain distinct and conflicting metadata requires correction. An excerpt match establishes
location, not scientific support. `supported`, `unsupported` and `needs-review` are author/host
decisions; only supported records can be cited. The software does not search or independently
verify full texts, fill missing metadata, or determine novelty and causal relevance.

Optional BibLaTeX import and numeric CSL formatting require an existing Pandoc installation.
Journal formatting needs shared metadata for every cited reference and a standalone local CSL
file. Supported styles use bracketed numeric citations in first-citation order and a leading
numeric bibliography label. Author–date, superscript, reordered numbering and unsupported
formatting are rejected rather than approximated. References remain static text, not Zotero
fields. Without a selected CSL style, the bibliography uses supplied metadata labels.

Qualification can reject incomplete membership, unknown units, incompatible cases, missing source
locations, or inadequate convergence, conservation, verification, and validation evidence. Passing
these checks bounds what the software may report; it does not make a physical interpretation true.

Analysis is limited to the declared observations and discrete cases. The software does not
construct undeclared spatial or temporal integrals, infer missing values, smooth sparse cases,
identify a continuous optimum, quantify a general uncertainty envelope, or perform general
three-dimensional field analysis.

Built-in evidence figure production delivers one panel with source data, a runnable Matplotlib script,
SVG/PDF/PNG/TIFF output, a caption, and focused QA records. It is not yet a general contour, profile,
multi-panel or general field-analysis renderer. The v0.7 external drawing-task route instead
packages data, conceptual or hybrid tasks for the host's tools and returns editable Python, SVG
or uncompressed draw.io sources, previews and listed dependencies. Import does not execute returned
scripts, verify physical meaning or grant author approval. Limited host-produced diagram and
data-combination examples do not establish automatic complex mechanism-figure production.

The subsection and manuscript paths accept supplied
PNG/JPEG/TIFF figures and host-authored prose, resolve evidence tokens, and export Markdown
and editable DOCX with native tables and finite structured mathematics. Declared raw-table
calculations can supply current numeric tokens; they do not determine which operator or population
is scientifically appropriate. Known source font sizes are checked after figure scaling; unknown
font sizes remain unknown. PDF preview requires an existing LibreOffice installation.
The workflow does not independently validate free prose, source files, literature,
or actual image viewing. It is not a complete-paper reasoning or LaTeX submission system.
Public analytical examples demonstrate software behavior; known-case trials do not establish
general scientific validity across heterogeneous projects or native solver formats.

The v0.9 development checkout adds root `review` for whole-manuscript package export and complete
report retention, plus exact-location editing tasks from host-selected actions. Tasks preserve
the original report and create a separate ordinary authoring workspace; the host still edits
the intended drafts and reassembles. It does not apply recommendations, reconcile Word edits or grant approval;
the published v0.8 release does not include this root route. Root `revise` and `export` remain unavailable; subsection DOCX
and review-suggestion import are options of `write --artifact results-section`, and multi-section
DOCX is available through `write --artifact manuscript`.
Reviewer-response work must be
triggered by real reviewer comments, and journal submission remains an author action.

Discrete CFD screening must not be presented as an experimental operating window, continuous
optimum, safety boundary, or validation claim. Author approval selects a reporting direction within
the available evidence; it cannot override missing or failed scientific support.
