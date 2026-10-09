# Saved transient data to a portable results subsection

The public [transient-writing example](../../examples/transient-writing/README.md) uses invented
thermal records to exercise the real prepare_section → host draft → assemble_section →
export_section_docx pipeline. It includes a nonuniform time grid, instantaneous rates, separately
supplied cumulative ledgers and a shared observed window. No physical model or validation is implied.

Declare a saved temperature calculation as follows inside an ordinary section input:

```json
{
  "id": "temperature", "source": "sources/history.csv", "operation": "temporal",
  "columns": {"time": "time_s", "value": "temperature_K"},
  "units": {"time": "s", "value": "K"}, "quantity_kind": "absolute-temperature",
  "domain": "Declared spatial maximum over the same domain", "group_by": "case",
  "time_window": [0, 12], "temporal_value_kind": "instantaneous",
  "threshold": 400, "crossing_direction": "at-or-above"
}
```

Window endpoints must be exact saved samples in each group; times must be finite, unique and
strictly increasing. The operator does not sort or interpolate. Choose the shared observed window
from source coverage, not a desired outcome. A threshold crossing is the first qualifying saved
sample in that window, not a solver-native event or an inferred sub-step onset.

Use `result_ref: {"calculation_id": "temperature", "group": "A", "field": "maximum",
"places": 1}` on metric evidence, omitting manual `value` and `unit`. Bind it in the host draft
with `{{value:ID}}`. Other outputs include sample_count, duration, start_value, end_value,
change, minimum, peak_time and first_crossing_time. Peak time is the earliest saved maximum;
a missing threshold crossing stays null and cannot become a numeric zero.

Instantaneous series support integral and time_mean using actual interval lengths and trapezoids.
Heat rate in W integrates to J; no source-value scale conversion is performed. Temperature-time
integration is not energy. For cumulative energy use `temporal_value_kind: "cumulative"` and
bind change, never integrate the ledger again. An independently exported ledger and saved-rate
reconstruction have distinct provenance even when they are close. Their agreement alone is not
an energy balance or physical validation.

Run the example or its prepare-only mode:

```text
python examples/transient-writing/run_example.py OUTPUT
python examples/transient-writing/run_example.py FRESH --prepare-only
```

Use fresh output paths. The prepare-only package carries TASK/input/sources/skills/results and a
scientific figure, without the recorded answer. A local-tool host may calculate, assemble and
export; a web/file-review host can read its attachments and return draft JSON, with actual tool
access determining whether it can view images or run commands. Move the full package unchanged
between hosts. Follow the example README for actual assembly/export commands; no provider adapter
or SDK is needed for file portability. Portable execution does not establish cross-model quality.

Read the packaged temporal writing reference before drafting. Compare thermal magnitude and timing
together rather than treating delay as a complete performance ranking. Preserve source definitions,
matched controls and limitations that change interpretation. The example's Word export retains
Times New Roman, two-character body first-line indentation and 0 pt paragraph-before/after spacing.
