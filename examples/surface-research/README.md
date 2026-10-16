# Connected synthetic surface research example

This example exercises the **v0.21.0 surface research workflow**. Use the matching source
checkout/archive and install it with `python -m pip install ".[docs]"` on CPython 3.10–3.12.
The example files are in the source distribution, not the wheel. Then, from the repository
root, one command creates the inputs and complete short draft:

```console
python examples/surface-research/run_example.py output/surface-demo
```

Choose a new output directory on each run. The script generates six unequal rectangular
faces and two **prescribed synthetic temperature fields**, then calls the existing
`prepare_surface_workspace` and `build_research_workspace` APIs. It does not run a
solver, read private data, invoke a model or calculate a separate set of report metrics.
The fixed example-host prose is replayed with source-bound values, not newly authored
or independently discovered on each run.

Open `output/surface-demo/candidate/manuscript.docx`. It contains Methods, Results,
Discussion and Conclusions, a native Word summary table and two complementary figures:
the original-face field map and exact area-exceedance distribution. The example shows
why a lower mean need not imply a lower spatial spread; it makes no physical design claim.

## Inputs and authoring entry points

- `materials/study.json` declares domain, units, face association, thresholds and support.
  `materials/sources/` holds the generated NPZ files and complete synthetic definition.
  The product preserves these source files and copies selected inputs into the workspace.
- `candidate/workspace/` is the portable continuation folder. Read `RESEARCH.md` and
  `TASK.md`; edit `sections/SECTION/draft.json` for prose and Results captions.
- `candidate/workspace/sections/results/figures/plot.py` is the **author-local plotting
  entry point**. Its edits survive refresh. Adjacent SVG/PDF files remain editable;
  PNG/TIFF previews and CSV source data are also supplied. Inspect both actual previews
  at print size and the rendered Word pages before using a candidate.

The supplied areas are exact rectangle areas, not projected-area estimates or face counts.
Strict exceedance excludes equality. Thresholds of 335 and 350 K are distribution
diagnostics, not safety limits. Both figures describe the same field, not independent
evidence for a mechanism. No image-generation service is needed for this quantitative path.

For fresh host writing, run the same command with `--prepare-only`. It returns a workspace
with empty drafts. The host reads the inputs, calculation results and figure previews,
chooses the argument, updates the provisional spine and fills all four drafts. It then runs:

```console
cfdpaper research --workspace output/surface-demo/workspace --output output/surface-draft
```

For real research, replace the synthetic source contract with actual aligned face values,
physical areas, vertices/connectivity, the documented quantity and common case/domain/time
support. The host supplies scientific interpretation and missing-model/validation context;
neither this example nor the product infers them from an NPZ filename.

To add separately prepared mechanism artwork, use the documented
[`research --attach-figure` route](../../docs/research-workspace.md#add-a-mechanism-figure-without-rebuilding-the-quantitative-figures).
It connects an imported figure, caption and body reference to a new workspace while retaining
the quantitative figures and author scripts. Studio-guided conceptual arrows require host review;
they are not calculated heat-flux evidence. The synthetic example itself needs no such artwork.

## Relocate, edit and refresh

Copy the entire `candidate/workspace` folder to a new location; retain the first candidate.
For example in PowerShell:

```powershell
Copy-Item -LiteralPath output/surface-demo/candidate/workspace -Destination output/surface-working -Recurse
```

In the copied `output/surface-working/sections/results/study.json`, change the first
threshold from `335.0` to `340.0`, leaving the other threshold and relation unchanged.
Then use the existing product command, not the generation script:

```console
cfdpaper research --workspace output/surface-working --output output/surface-refreshed --baseline output/surface-demo/candidate
```

The table header, bound prose/caption values, exceedance results and affected figures
refresh together. Read `output/surface-refreshed/CHANGES.md`: interpretation review is
required, while the original draft text and local plotting script are preserved.
The unaffected mean and spatial SD remain the same. A changed threshold may invalidate
the supplied wording about opposing comparisons; the host must revise that wording.

For a **source-value software exercise**, start from a separate copy of the original
workspace and change only that copy's `sections/results/sources/A.npz` `face_value`
array, retaining areas and geometry. For example, adding 2 K to all six A values must
raise its bound mean by 2 K while leaving its spatial SD unchanged. Build to another
new directory with the same baseline command. Such a perturbation is a refresh test,
not a new simulation or physical result. Original `materials/` and earlier candidates
remain unchanged. Do not rerun the generator over an author-edited workspace.

On another computer, install the matching package and `docs` extra before building.
Word-only edits are not imported by this path: reconcile them into the local drafts
before the next build. Continue from the newest candidate's `workspace/`, not its
generated `manuscript/` reading view.
