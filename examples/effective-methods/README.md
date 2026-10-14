# Effective methods and saved temperature contrasts

This recorded tutorial uses invented histories, a static illustrative model definition and
explicitly synthetic reference metadata. It demonstrates the SDK, not a validated physical
model, real literature or AI writing quality. Do not execute or import `inputs/model.py`.

```powershell
python examples/effective-methods/run_example.py output-effective-methods
```

Use a fresh output directory. The actual materials definition reader locates
`TutorialBalance.front_rate` and `TutorialBalance.contrast`, with exact source lines.
It does not infer that these methods generated the independently chosen CSV records.
The analysis proposal is compiled and passed to `build_analysis_section`; three declarations
read the same CSV: front temperature, rear temperature and same-record front-minus-rear
`temporal_difference`. The original columns and all 12 records remain intact. Temperature
differences are in K; time-weighted means use the declared 0–5 s window. No solver event,
transport coefficient or causal mechanism is inferred.

An original-front-temperature profile and a same-record front-minus-rear contrast profile
are exported at 160 × 130 mm with unchanged readable fonts and no smoothing. Both original
readings remain in the contrast source data; endpoint states and contrasts appear in prose
and a compact native table.
The local `analysis/figures/plot.py`, source data, SVG/PDF/PNG/TIFF and layout checks are retained
for inspection and author editing. The Results figure is explicitly placed at its section end;
other figures would retain their default layout behavior.

The four-section Word document has a native table, editable equation, two-character body
indentation and zero body paragraph spacing. A `json_value_ref` binds the illustrative heat
capacity. Optional `citation_record` provides a bibliography label without inserting the
supporting claim into References, and requires no global literature library or web search.
The synthetic record is labelled as such, not presented as an actual publication.

Copy `manuscript/` to continue elsewhere and reassemble using its `drafts.json`. Updating
`sections/methods/sources/config.json` refreshes the bound capacity. Updating a saved-temperature
CSV and reassembling refreshes bound numerical text; regenerate the figure from the updated
analysis input as well before a new export. Reassembly alone does not rerun the model or
silently change author-written interpretation. Inspect rendered Word pages before publication use.
