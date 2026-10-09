# Transient response and saved-sample timing

Read the time origin, saved cadence, quantity definition, spatial support, control volume and
comparison controls before interpreting a transient plot. Solver time steps and saved times are
different. A peak of a spatial maximum, a probe temperature and a volume mean do not describe
the same response. Use the existing case/stage/operator context rather than introducing a new
registry. Preserve incomplete windows and unavailable channels as evidence gaps.

## Select the window and operator

Use a common observed window for case comparisons. `temporal` maps exactly `time` and `value`
columns with explicit units (`time` is seconds), grouping and `time_window: [lo, hi]`. Both
endpoints must occur in every selected group. Unique, strictly increasing saved times are
required; do not silently sort, smooth, fill missing samples or infer an event between records.
The nonuniform intervals, not the number of rows, determine time weighting.

For `temporal_value_kind: "instantaneous"`, time_mean equals the nonuniform trapezoidal integral
divided by duration. Supported rate units have explicit integral labels (for example W → J);
other units retain a value-unit × seconds expression. No source-value scale conversion is performed.
The integral of absolute
temperature is a temperature-time exposure, not heat or energy. An arithmetic sample mean can
overweight densely saved intervals and must not replace the time-weighted mean.

For `"cumulative"`, use change = end_value minus start_value. Integrating that series again would
produce energy-time, not total energy. If the source contains a solver/exported cumulative heat
ledger, retain it independently of a saved-rate reconstruction. A difference between those two
quantities tests the declared reconstruction; it is not experimental validation or a complete
control-volume closure. Storage, imposed heating, internal sources and boundary transport must
be identified before calling anything an energy balance.

Both kinds expose sample_count, duration, start_value, end_value, change, minimum, maximum and
peak_time. Peak_time is the earliest saved time attaining the maximum in the selected window,
not a continuous peak. Bind useful outputs with `result_ref` and `{{value:ID}}`; assembly
recalculates from the copied sources. Do not hand-transcribe rounded intermediate numbers.

## Timing and thermal response answer different questions

`threshold` and crossing_direction `at-or-above` / `at-or-below` report first_crossing_time at
the first saved sample satisfying that condition in the selected window. If the first sample
already satisfies it, that sample is the answer, not proof of an onset at the window boundary.
Null means no qualifying saved sample, not zero time. Do not bind null as a number or infer the
unsaved crossing by interpolation. Native event records, where separately supplied, retain their
own definition and numerical resolution; do not relabel a sampled threshold time as a native event.

A later threshold sample need not imply a lower peak or lower cumulative heat. Show complementary
thermal metrics where they discriminate the actual question, and explain tension rather than
choosing the convenient ranking. Temporal order alone does not prove a transport or triggering
mechanism. Matched forcing, materials, boundary conditions and suitable spatial/budget evidence
are needed to distinguish alternatives. A truncated trajectory cannot establish absence of a
later event; compare only the shared observed interval.

## Write and deliver

State the decisive finding first; define the sampled timing once in Methods or a concise caption.
Separate saved-rate integration from independent cumulative records. Keep causal explanations
bounded by the supplied controls. Do not turn every operator output into a plotted panel or
repeat the full table in prose. Captions explain units, saved samples, line reconstruction and
threshold definitions; reviewer questions and missing analyses belong in evidence_notes.

Use the actual prepare_section → host draft → assemble_section → export_section_docx chain.
Carry TASK.md, input.json, sources/, table-results.json and packaged skills/ together to another
host. A local-tool host can run calculations and export DOCX; a file-reading web chat can inspect
the supplied evidence and return draft JSON, but cannot be presumed to have run local commands,
opened images or exported Word. Set image_observations according to actual access. Provider names
do not establish capabilities or scientific quality. Author selection remains necessary.

Preserve Times New Roman, two-character body indentation and 0 pt paragraph spacing for this
project unless the author supplies another style. Check actual DOCX body properties and embedded
figure readability. A portable package or a passing assembly is not a multi-model writing-quality
evaluation.
