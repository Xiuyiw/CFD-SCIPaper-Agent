# Surface research workspace

The `research` command connects supplied surface results, reproducible figures and a
host-written manuscript candidate. It currently supports a concrete reference path:
two to four cases with original face values, actual face areas and polygon geometry
in NPZ files. It is not an arbitrary native-solver reader and does not start a solver.

The author provides the research goal and existing materials. The host AI reads those
materials, locates case and quantity definitions, prepares the study declaration and
writes the argument. The author does **not** need to prefill scientific conclusions to
use this workflow. Ask the author only for consequential information that cannot be
established from the supplied sources.

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

The result is an editable research candidate for author review. It does not establish
solver convergence, physical comparability, experimental validation or publication readiness
by itself; those judgments use the supplied study evidence and the actual rendered pages.
