# Paper-grounded mechanism figure studio

Adapted from the locally supplied `paper-framework-figure-studio-pro` 3.1.4a
(local entry dated 2026-09-09), under MIT-0. This is a modified, portable subset,
not the full upstream installation. The supplied license is retained in
[paper-framework-studio-MIT-0.txt](paper-framework-studio-MIT-0.txt).

## Use and route

Use for a paper framework, physical mechanism, method schematic or the conceptual
layer of a hybrid figure. If `paper-framework-figure-studio-pro` is installed,
use it with the current task, supplied sources and these CFD-specific boundaries.
Otherwise follow this procedure directly; no particular host, API or service is
required. The existing `figure --task-input` package includes this reference.

Start from the author's current artwork or local script when one exists. Preserve
accepted data, style and geometry during a targeted edit. For a new figure, produce
one complete candidate by default. Offer alternatives only for a consequential
scientific choice or when asked; do not launch a gallery or eight approval stages.

## 1. Understand the paper before arranging boxes

Read the supplied manuscript or method notes, definitions and figure evidence,
including the actual caption and relevant equations. A task title or a list of
labels is not enough to recover a mechanism. Recover only what is available:

- The reader's question and the specific contribution this figure explains.
- Physical entities, domains, inputs, transformations, outputs and assumptions.
- The ordered method or proposed physical sequence, including branches/feedback.
- The source location for each important relation and its status: observed,
  method/process, or hypothesis. A process arrow does not prove physical causality.
- What must be visible in the figure, what the caption can define, and what is unknown.

Keep this brief in existing figure notes or one `figure-brief.md` included in
`exports`; do not create a second evidence registry. Missing evidence should leave
a specific gap, not be filled with plausible geometry, equations or mechanisms.
Proceed with supported parts. A style reference supplies layout, never paper facts.

## 2. Make the core mechanism visible

Choose a reading order that explains the scientific relationship rather than
mirroring every subsection. Put the central mechanism in the main visual field;
show its essential source-supported steps inside the module or in a connected
detail inset. A large box labelled "coupling", "optimization" or "mechanism" is
not an explanation. Conversely, do not add decorative equations or microscopic
detail that the sources cannot support.

Keep arrow meanings consistent and stated. Separate material/energy transport,
method sequence, comparison and hypothetical influence; do not draw quantitative
flux widths without the actual flux definition and values. Use restrained colors,
clear labels and line/shape distinctions, not color alone. Icons are secondary to
physical relationships. Reuse supplied symbols and units consistently.

For hybrid figures, assign real fields/curves and conceptual explanations distinct
roles. Keep original CFD fields, mesh values, colorbars and numerical labels intact.
Never ask an image model to invent a temperature/velocity field, change a measured
trend, repair a colorbar or turn a hypothesis into simulated evidence.

## 3. Draw with the available tool, then write with the actual figure

- `output_mode: editable` (default): use native SVG text/shapes or draw.io for a
  schematic. Image generation may inform composition, but a bitmap wrapped in SVG
  is not editable. The existing
  [editable schematic procedure](editable-schematic-adaptation.md) supplies this fallback.
- `output_mode: raster_concept`: explicit opt-in, **schematic only**. Use the host's
  image-generation tool for final conceptual artwork when appropriate. Return an
  actual PNG/TIFF; leave `editable_sources` empty if no genuine editable source
  exists. State this in `notes`; a PDF export does not make the bitmap editable.
- Data and hybrid tasks retain the numerical plotting script, source records and
  required dependencies. A hybrid may include a disclosed raster conceptual layer,
  but the quantitative layers must still be computed from real source data.

Build title, legend, caption and a short body-reference sentence together with the
artwork. Put them in `delivery.json` (`caption` required; `title`, `legend` and
`body_reference` optional). These fields accompany the figure; they are not an
automatic replacement of author manuscript text. The caption should identify the
scientific reading, define panels/arrows/colors/abbreviations and state a relevant
boundary once. It cannot rescue a missing core mechanism or claim unseen results.

For an existing research workspace, use the product bridge after figure import:

```python
from cfdpaper.publication.research_workspace import (
    attach_imported_figure,
    build_research_workspace,
)

attached = attach_imported_figure(
    workspace_dir,
    imported_dir,
    new_workspace_dir,
    section_id="discussion",
    evidence_ids=source_evidence_ids,
    image_observation="viewed",
    observation_note=actual_preview_findings,
    paragraph_index=insertion_position,
)
build_research_workspace(attached, new_candidate_dir, baseline_dir=previous_build)
```

Use the figure's local `{{figure:ID}}` token in `body_reference`; the assembly resolves
its global number. Select the insertion position from the actual section argument.
This inserts the figure/caption/reference into a new workspace, retaining existing
prose and author drawing scripts. Declare `viewed` only after inspecting the image;
otherwise leave the default `not-viewed`. Inspect the resulting Word/PDF too, since
a good standalone preview may have small labels or a detached caption on the page.
If underlying results change, conceptual response arrows and interpretations need
host review; a preserved raster is not an automatically updated scientific diagram.

Image prompting should carry the actual physical entities and relationships,
required labels, panel reading order, output size and the distinction between
observed evidence and a proposed explanation. Do not replace this with generic
"publication quality" adjectives. Use source images only for their declared role.

## 4. Check and return one usable figure

Inspect the actual generated preview at final manuscript size together with its
caption and source brief. Check source fidelity, core visibility, arrow meaning,
panel references, symbol/unit consistency, readable text, overlap and caption
alignment. Repair concrete defects; do not restart a full design cycle for every
label change. For data/hybrid layers, also compare the plotted values and domains
with their original records. A source that cannot be opened remains unverified.

Keep the real editable sources where available, PNG/TIFF preview, exports and all
required dependencies. Follow `delivery-template.json`; list new brief/helper files
in `exports`. Unknown font measurements remain unknown. Reopen the final image;
do not report scientific or visual success based only on successful file creation.
The importer checks file structure and sizing, not mechanism validity or author
approval. Do not create fictitious independent reviews or automatic acceptance.

## Deliberate integration choices

This adaptation retains paper deep reading, core-module visibility and figure–caption
joint design. It omits the upstream optional S0–S7 project state, multi-candidate
campaigns, repeated formal review reports and cleanup of previous outputs. Original
sources and author refinements remain protected. The host supplies research judgment
and drawing tools; CFD-Paper-Agent supplies the portable task and reusable delivery.
