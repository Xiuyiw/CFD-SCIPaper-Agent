# Surface and physical-diagnostics research workspace

The `research` command connects supplied surface results, reproducible figures and a
host-written manuscript candidate. It currently supports a concrete reference path:
two to four cases with original face values, actual face areas and polygon geometry
in NPZ files. Optional physical diagnostics add regional integrals, signed transfer,
matched field differences and defined control-volume budgets to the same working draft.
The research command consumes declared exports; the optional native adapter below provides
a separate saved-results extraction step when those exports are unavailable.

The author provides the research goal and existing materials. The host AI reads those
materials, locates case and quantity definitions, prepares the study declaration and
writes the argument. The author does **not** need to prefill scientific conclusions to
use this workflow. Ask the author only for consequential information that cannot be
established from the supplied sources.

For a complete runnable example without private data or an AI API, start with the
[synthetic surface study](../examples/surface-research/README.md). Its fixed sample
prose demonstrates assembly; a real task still needs the host's scientific reading.

The v0.26 [research-expression example](../examples/research-expression/README.md)
adds an original-array regional comparison, a complementary budget panel, ordered native tables
and a source-driven refresh. Its prose is supplied by the example author; the software binds the
calculations and figures rather than discovering the interpretation. Use the matching v0.26.0 package;
the older v0.25.0 wheel does not contain these additions.

## Read saved native results when necessary

The optional Fluent reference path was exercised on Windows with Fluent 2023 R1 and
PyFluent 0.20. It reads a saved CASE/DATA pair, original boundary polygons, face-associated
temperature/heat flux and native surface integrals. Install the `fluent` extra in the Python
environment that has access to the licensed solver. Core installation and neutral-field
analysis do not require it. STAR-CCM+ currently provides native-file recognition and neutral
export guidance rather than this extraction path.

```python
from pathlib import Path
from cfdpaper.adapters import ExtractionRequest
from cfdpaper.adapters.fluent_backend import export_fluent_surfaces

request = ExtractionRequest(
    Path("inputs/reference.cas.h5"),
    variables=("temperature", "heat-flux"),
    options={
        "data_file": Path("inputs/reference.dat.h5"),
        "output_dir": Path("derived/reference-native"),
        "surfaces": {"wall": "heated-wall"},
    },
)
manifest_path = export_fluent_surfaces(request)
```

`heated-wall` is illustrative: select the actual case zone from its setup/method records.
`FluentAdapter.extract(request)` uses the same export and returns the existing
`ExtractedRecord` objects for the native whole-surface reports. The manifest retains the
actual field/surface inventory, report files, source pair and per-surface NPZ paths.
`probe()` detects the optional Python backend without consuming a license; extraction
establishes whether the saved case and actual backend work. A missing backend returns the
minimum neutral-export recommendation rather than values.

The NPZ includes `temperature` (K), `heat_flux` (W/m²), `face_area_m2`, `vertices_m`,
`faces_connectivity`, `face_starts`, `centroid_m` and separate centroid coordinate arrays.
Geometry is original, not reconstructed from an image; face ordinals are local to the export,
not solver-global identities. Native heat-flow reports retain the selected boundary's sign.
Define the physical positive direction in the calculation; do not automatically add wall
and shadow or interpret a native normal array as a declared oriented area vector.

For native coordinate clipping, an option such as
`region_bounds={"selected": {"axes": {"x": [0.0, 0.01], "y": [0.0, 0.01]}}}`
adds original-wall coordinate clips in m, followed by native area, area-weighted temperature
and heat-flux integrals. Its values and report paths appear in `surfaces[].regions`.
The bounds are illustrative, not a recommended physical region. `export_fields=False` keeps
these native reports without re-exporting large full-wall arrays. This route also handles
nonplanar wall sets that cannot use the planar polygon-clipping operator below.

Use the optional `executable` setting when the solver cannot be located. For older Windows
Fluent versions that cannot read Unicode absolute paths, `solver_case_file` and
`solver_data_file` may reference existing ASCII aliases of the same source files; the adapter
checks that they resolve to the original pair. It does not create a new source copy or run
iterations. Derived files remain in the isolated output directory. Native reports and neutral
polygon reductions are distinct postprocessing results and retain their physical definitions.

## Prepare the workspace

Use an environment with CFD-Paper-Agent and its `docs` extra installed; the build step
exports an editable Word document. Each output directory must be fresh and outside the
input material or workspace directory.

```console
cfdpaper research --study materials/study.json --output research-workspace
```

`--study` and `--workspace` select alternative actions; `--output` is always required.
Preparation creates the working inputs and host-writing entry point. Read `TASK.md` and
`RESEARCH.md` before drafting: successful preparation is not a completed paper. Keep the
source exports unchanged; work on the copies and author-editable script in the workspace.

The study declaration names the question, common support and definition source as well
as the physical domain, quantity, units, thresholds, cases and array names. For example:

```json
{
  "study_id": "wall-comparison",
  "title": "Heated-wall temperature comparison",
  "question": "How does the wall-temperature distribution differ between the two cases?",
  "time_support": "Supplied converged steady results",
  "common_conditions": ["Same heated wall and imposed heat input"],
  "definition": {
    "source": "sources/definition.md",
    "text": "Temperature is the face-associated wall value; weights are actual face areas."
  },
  "domain": "common heated wall",
  "quantity": "Temperature",
  "unit": "K",
  "coordinate_unit": "m",
  "projection_axes": [0, 1],
  "thresholds": [340, 350, 360],
  "exceedance_relation": "above",
  "arrays": {
    "values": "face_value",
    "weights": "area_m2",
    "vertices": "vertices_m",
    "connectivity": "faces_connectivity",
    "starts": "face_starts"
  },
  "cases": [
    {"id": "A", "label": "Reference", "source": "sources/A.npz"},
    {"id": "B", "label": "Modified", "source": "sources/B.npz"}
  ]
}
```

The named files, including `sources/definition.md`, must exist relative to `study.json`.
Optional `selected_figures` selects `field` and/or `distribution` in the requested initial manuscript
order. Omission keeps both; `[]` starts without either figure while retaining their calculated data
and output files. An existing author's chosen figure set is preserved during refresh.
This example illustrates the data contract, not an assertion that new cases are physically
comparable or converged. The host fills support and definition fields from the actual
study materials, retaining any limits or missing evidence rather than copying these claims.

Each NPZ contains aligned one-dimensional face values, positive areas in m² and face
start offsets; vertices have shape `N × 3` in m. Connectivity is packed as a vertex
count followed by that face's vertex indices. A start offset points to the count.
For two quadrilaterals it can be `[4, 0, 1, 2, 3, 4, 1, 4, 5, 2]` with starts `[0, 5]`.
Area is supplied physical face area, not inferred from centroids or projected polygons.

The renderer draws the original polygons on a shared color scale and shared coordinate
limits. It retains the declared value unit: Kelvin is not silently converted to Celsius.
Area-exceedance curves retain the exact empirical steps at distinct face values.
`above` means strictly greater than the threshold; `at-or-above` includes equality.
The same calculation supplies numerical evidence and curves; raw fractions remain in
`[0, 1]`, while the plotted ordinate displays percent. Threshold markers are diagnostic
readings, not automatically stability limits or acceptable operating bounds.

## Write, inspect and build

The prepared workspace has these main entries:

```text
research-workspace/
  TASK.md, RESEARCH.md
  manuscript-input.json, figure-recipes.json, drafts.json
  sections/
    methods/draft.json
    results/draft.json
    results/study.json
    results/sources/
    results/figures/plot.py
    discussion/draft.json
    conclusion/draft.json
```

`drafts.json` maps section IDs to their draft files. The host reads the current section
tasks, context and calculation results, inspects the field and distribution previews,
and fills the referenced `draft.json` files using the existing evidence and figure references.
Write methods from the actual model and observation definitions, then distinguish observed
changes from physical interpretations. A temperature map and its area distribution are
complementary views of the same field, not two independent proofs of a causal mechanism.

For dependent sections, the existing `write --context-for` route supplies current drafts,
values and definitions. Large source-index lists are represented by their count and an
exact JSON Pointer into the retained full report. Follow the referenced detail only when
needed; do not load every face index into the host's writing context. The full calculation
records remain unchanged. This projection does not remove scientific arrays or prose.

```console
cfdpaper research --workspace research-workspace --output build-01
```

Building executes the current `sections/results/figures/plot.py` and assembles the completed drafts.
Run it only for a workspace whose script you intend to execute. The author-local script
is the working source for style and re-export; do not replace it with a fresh template
after manual edits. Inspect the generated vector/raster figures at the declared print
size and the manuscript output, not just command success. A build contains:

- `workspace/`: the current portable authoring snapshot;
- `manuscript/`: assembled manuscript with its writing state and change information;
- `manuscript.docx` and its layout report;
- `refresh.json` and `CHANGES.md`: refreshed items and change summary.

When data, definitions or author text change, build into a new directory and optionally
compare with the earlier build:

```console
cfdpaper research --workspace research-workspace --output build-02 --baseline build-01
```

`--baseline` applies only to `--workspace` and names a previous build, not the original
materials directory. The comparison identifies affected content; the host still revisits
interpretations when their supporting values change. Preserve previous builds and current
author edits. This command does not alter the existing `write` or refresh interfaces.

## Attach regional, transfer and budget diagnostics

Use an existing workspace and a host-prepared diagnostic configuration:

```console
cfdpaper research --workspace research-workspace --diagnostics materials/diagnostics.json --output research-with-diagnostics
cfdpaper research --workspace research-with-diagnostics --output diagnostic-candidate
```

Attachment and build are separate actions. A diagnostic configuration contains
`field_calculations` and selected `panels`; `mechanism_questions` optionally links a concrete
question to the diagnostics that could distinguish its explanations. Sources use relative
`sources/` paths beside the configuration. The operation copies needed inputs into a new
workspace, adds calculations and bound evidence to the existing Results input, makes the
same evidence available to the other sections, and retains author prose and existing figures.
The host reads the resulting context and completes the argument.

For a composed diagnostic figure, the Python API exposes the renderer's existing selection and style:

```python
from cfdpaper.publication.research_workspace import attach_research_diagnostics

attach_research_diagnostics(
    "research-workspace",
    "materials/diagnostics.json",
    "research-with-diagnostics",
    combine=True,
    figure_id="regional-budget",
    panel_ids=["regional-change", "local-budget"],
)
```

Those panel IDs must exist in the supplied configuration; they are not inferred from a case name.
Omit `panel_ids` to render all declared panels. Calculations remain available to writing even when
their panel is not selected. The returned workspace retains its local `plot.py` and relative source
configuration as the next build's recipe. Do not substitute a copied static PNG for that recipe.
An optional `style` uses the existing `PlotStyle` settings.

For native tables, `column_units` declares one shared display unit or `null` per column; units must
match bound values and appear in the header. Choose precision in the evidence `result_ref`, not by
rounding the source. Explicit draft `paragraph_id` and `block_order` arrange prose, figures and tables
through the formal Word exporter. Subsequent refresh preserves display precision for unchanged bound
identities, author captions, drafts and the current plotting script. Inspect the resulting pages and
revisit interpretations when changed evidence affects the argument.
`research-context.json.result_summary` gives compact current scalar results and exact pointers
into the full result reports; source element/record lists remain there instead of flooding
the reading context. Attachment refreshes those reports and cross-section evidence bindings
before writing, without requiring a preliminary manuscript build or manual recalculation.

The supported operations use the ordinary table declaration and `result_ref` format:

| Operation | Required physical choice | Useful reading |
|---|---|---|
| `field_integral` | Face/cell association; density, element total, vector flux or weighted mean; physical measure and sign | Regional level/area or positive, negative and net transfer |
| `field_difference` | Compatible physical coordinates, element measures and original polygons when supplied | Both original means and comparison-minus-reference |
| `energy_budget` | Independent input, output, source and storage terms for the stated control volume | Terms and `input + source - output - storage` residual |

For power, a density in W/m² or W/m³ is multiplied by physical area or volume once. A supplied
W-per-element total is summed directly. Vector flux requires a dot product with oriented area;
temperature-area sums are not heat. A steady-state storage omission needs an actual method basis.
The [physical diagnostic reference](../skills/cfd-evidence-writing/references/mechanism-subsections.md#original-fields-regions-signed-transfer-and-budgets)
gives the supported declaration and interpretation details.

Regions may use explicit overlap fractions, a declared centroid mask, or exact polygon overlap
on a common planar original-face surface. Polygon clipping requires the `geometry` extra.
It retains piecewise-constant original face values and actual area, including partial faces;
it does not interpolate a new temperature field. Fixed-coordinate and source-following regions
answer different questions. Keep complete complementary coverage when explaining redistribution.
Different meshes require a valid common support; equal row counts cannot justify subtraction.

The built-in diagnostic panels are `regional`, `signed_flux`, `budget` and
`matched_difference`. They consume selected calculations, not manually copied final metrics.
A signed-flux panel requires a reader-visible `sign_convention`. Source data, a standalone
author-local `plot.py`, editable SVG/PDF and PNG/TIFF are produced under
`sections/results/figures/diagnostics/`. The workspace uses the same computed quantities for
its numeric evidence and writing context. For example, generated IDs can be used as
`{{value:flux-A-all-net}}` in prose/captions/native tables, with an ordinary figure token
such as `{{figure:transfers}}`. Current table results retain source positions and definitions.

Continue from `candidate/workspace/`. Edit its `sections/results/diagnostics.json`, copied
sources or current diagnostic `plot.py`, then build to a fresh directory with the previous
candidate as `--baseline`. A definition or numeric change recomputes the diagnostics and bound
values. The host reviews affected captions and mechanism interpretations; the build does not
replace author reasoning or silently merge independent Word edits.

The complete public [physical-diagnostics example](../examples/physical-diagnostics/README.md)
can be run with `python examples/physical-diagnostics/run_example.py NEW_OUTPUT`. It combines
unequal-area original faces, a boundary crossing partial faces, opposing signed fluxes,
matched original states and a separate budget, then assembles four manuscript sections and
complementary figures. Its arrays are constructed and its prose is a disclosed recorded host
input. `--prepare-only` leaves draft templates for a host to write instead. It demonstrates
the calculation-to-figure-to-document route without claiming a CFD mechanism was validated.

## Keep comparisons and interpretations on their stated support

An observation's optional `support` retains case identity, association, spatial domain,
operator, named conditions with value/unit, and time state/origin/window. Result comparisons
can declare `support_purpose` and `fixed_conditions`. The supported purposes are `same-state`,
`event-relative` and `event-timing`: an event-relative comparison may use different physical
times, whereas a same-state comparison must have the needed common time/window. Native-event
and saved-sample crossing times remain different observations. Only conditions claimed fixed
are matched; different design variables are allowed. Compatibility checks supplied definitions,
not whether the underlying model is validated.

Use the existing evidence roles: `algebraic`, `same-solution-diagnostic`, `condition-contrast`,
`model-contrast` and `independent-validation`. A regional budget remainder and a reconstructed
gradient integral from one numerical solution may cross-check postprocessing, but their agreement
does not become independent experimental evidence. State the actual physical finding from the
discriminating diagnostics and compare relevant method differences at that effect's scale.
The host keeps the hypothesis, alternative explanation and missing observation in current
`mechanism_questions`/evidence notes, and writes natural scientific prose rather than an execution log.

## Add a mechanism figure without rebuilding the quantitative figures

Prepare and import the artwork through the existing `figure --task-input` and
`figure --package ... --delivery ...` route described in
[figure-task reference](../skills/cfd-figure-production/references/external-backends.md). For schematic/hybrid tasks the package includes the
paper-framework Studio guidance. Real field maps and numerical plots stay data-driven;
conceptual artwork explains source-supported relationships, not new simulated evidence.

The returned `delivery.json` carries a caption and a `body_reference` containing the
local figure token, for example `{{figure:heat-path}}`. Attach the imported candidate:

```console
cfdpaper research --workspace research-workspace --attach-figure imported-figure --section discussion --evidence location-observation --paragraph-index 2 --output workspace-with-mechanism
cfdpaper research --workspace workspace-with-mechanism --baseline build-01 --output build-with-mechanism
```

Use an evidence ID that actually exists in the target section; repeat `--evidence`
for multiple supporting records. The paragraph index is zero-based and inserts before
that paragraph; omit it to append. The operation creates a new workspace and keeps
the existing prose, sources and local plotting scripts. The normal build handles the
global figure number, caption bindings and Word placement. It skips unchanged drawing
recipes when the baseline is supplied.

The imported preview starts as `not-viewed`. After inspecting it, the host can pass
`--viewed --observation-note "..."` during attachment, describing actual observations.
This records an inspection, not author approval. Review the actual Word/PDF layout as
well. A later definition or source change lists affected mechanisms and captions for
host reconsideration; it does not automatically redraw conceptual arrows. Explicit
`raster_concept` output is schematic-only and remains raster, not editable SVG.

The result is an editable research candidate for author review. It does not establish
solver convergence, physical comparability, experimental validation or publication readiness
by itself; those judgments use the supplied study evidence and the actual rendered pages.

### Read evidence for a specific mechanism question

Select existing evidence IDs; the tool does not guess an explanation from the question:

```console
cfdpaper research --workspace current-build/workspace --section discussion --evidence mean-change --evidence method-definition --question-context "Does local cooling imply stronger lateral export?" --output question-reading
```

`question-reading/question-context.json` contains current recalculated readings, their owning
definitions and source locators, bounded text excerpts where available, and related passages and
figures in the target and owning sections. Large arrays are not copied into this view. Paths refer
to the supplied workspace; keep that workspace with the reading view. Python exposes the same
`research_question_context(workspace, question=..., section_id=..., evidence_ids=[...])` action.
Reading does not revise drafts or create a scientific conclusion. Assess the explanation and its
relevant alternative from the selected observations, then write the argument with the host.

### Update imported artwork without changing its figure number

After the host revises the actual drawing through the figure-task route:

```console
cfdpaper research --workspace current-build/workspace --attach-figure revised-import --replace-figure --section discussion --evidence heat-path --output updated-workspace
cfdpaper research --workspace updated-workspace --baseline current-build --output updated-build
```

Replacement is explicit and applies only to an imported figure with the exact same ID. Its position
and paragraphs remain; there is no second inserted introduction. New artwork and sources are stored
in `sources/figure-tasks/ID-update-N`, beside the previous author sources. The incoming caption replaces
this figure's caption; inspect it with the artwork. Inspection defaults to `not-viewed` for the new
preview. Pass `--viewed` only after viewing that actual image.

Body interpretation is not overwritten by the new delivery's `body_reference`. Read the located
affected passages and revise scientific wording explicitly in the new workspace. For comparable
differences, `difference_sign_changed` identifies crossing zero, including `difference_mean`;
a changed domain, operator, baseline or unit is a definition change rather than an ordinary reversal.
The [mechanism continuation example](../examples/mechanism-continuation/README.md) demonstrates
the complete host action instead of treating a review prompt as a finished scientific revision.
