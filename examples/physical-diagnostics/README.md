# Regional and signed-transfer research example

Install the matching source checkout with its document and planar-geometry extras:

```console
python -m pip install ".[docs,geometry]"
python examples/physical-diagnostics/run_example.py output/physical-demo
```

Open `output/physical-demo/candidate/manuscript.docx`. The short research draft contains
Methods, Results, Discussion and Conclusions, two native Word tables, the original-face
temperature map and distribution, and three complementary diagnostic figures. Every
reported number is bound to a product calculation. The prose is a disclosed, recorded
example-host input, replayed by the script; it is not a fresh AI scientific evaluation.

The six unequal-area faces and their temperatures and signed fluxes are constructed
examples, not CFD or experimental data. They deliberately show a lower temperature in
one fixed region together with a higher whole-domain mean, and a lower net transfer
despite unchanged positive-direction transfer. The separate budget includes nonzero
storage; it does not validate or close the prescribed surface fields.

The left-region boundary crosses original faces. Shapely calculates actual polygon
overlaps on the common planar surface; the product retains each original face's
constant value and uses physical area. Region support is therefore neither a count
of face centers nor an interpolated temperature field. Curved surfaces cannot use
this planar clipping route. Positive flux denotes heat entering the illustrated solid.

## Continue with a host AI or author edits

`candidate/workspace/` is the portable continuation folder. Read `RESEARCH.md`,
`research-context.json`, `sections/results/study.json`, `diagnostics.json`, the definition
material and current table results. Use `--prepare-only` for empty draft templates
instead of replaying the recorded prose. The tool calculates and supplies evidence;
the host chooses and writes the argument.

The diagnostic declarations reference original NPZ/CSV sources rather than hand-entered
final metrics. Results, captions and tables can use generated IDs such as
`region-A-left-weighted_mean`, `flux-A-all-negative` and `paired-all-difference_mean`.
Their source records, physical definitions and units remain available in the exported
source-data CSVs. A temperature-area integral is not treated as heat.

Edit the current author-local scripts for graphical style:

- `sections/results/figures/plot.py` controls the original temperature figures.
- `sections/results/figures/diagnostics/plot.py` controls the physical diagnostics.

SVG/PDF preserve editable text; PNG/TIFF support previewing at the declared 160 mm width.
Inspect actual previews and rendered manuscript pages before using the draft. The
script records neither automatic visual approval nor a model validation claim.

## Source-driven refresh

Copy the entire latest candidate workspace to a new working location. Modify only
that copy's inputs or local script, then build into a fresh output folder:

```console
cfdpaper research --workspace output/physical-working --output output/physical-refreshed --baseline output/physical-demo/candidate
```

For a software exercise, changing Case A's prescribed face temperatures by +2 K updates
the global and regional means, matched difference, figures and bound prose. The original
materials and the author's draft/script edits are retained. Read `CHANGES.md` and revise
affected interpretation; successful replacement of numbers does not establish that the
old argument remains true. Geometry and region-definition changes recompute polygon
fractions from the current geometry. Do not rerun the generator over author-edited work.

For an existing surface workspace, attach a separately authored diagnostic configuration
through the product API `attach_research_diagnostics(workspace, config, fresh_output)` or
the corresponding `research --diagnostics` CLI option. Actual research requires aligned
fields, physical sign/domain/time definitions and the relevant model evidence; these
cannot be supplied by renaming this example's arrays.
