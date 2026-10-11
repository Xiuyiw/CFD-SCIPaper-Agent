# Build an argument from complementary observations

Use this reference when several observations constrain one physical interpretation. Read the
actual methods and all relevant observation classes before choosing a convenient scalar.
Reuse the manuscript spine and scientific context; no extra approval registry is needed.

## Decide what distinguishes explanations

Identify the question each observation answers: timing, spatial distribution, source intensity,
transport, storage, conversion or an integrated outcome. Equal units do not make those roles
interchangeable. Name the observable's operator, domain and solution/measurement stage. A variable
called propagation may mean a two-surface interval, not spread through a device or system.

For a proposed mechanism, ask what pattern it predicts across these observations, what matched
contrast supports it and what opposing observation would weaken it. Make that comparison visible.
A source increase with weaker transported feedback, or a close event time with a mismatched
thermal state, is a scientific finding to explain rather than a result to hide. An algebraic
decomposition identifies conditional responses but does not locate an unmeasured transport path.

Separate a physically supported explanation from a plausible alternative. Link each alternative
to a concrete discriminating observation, parameter contrast or budget term. Do not conclude only
that more research is needed, nor list every conceivable mechanism. Model mismatch can support
a useful diagnostic study; it is not a reason to abandon supported writing.

## Read comparisons at their actual strength

Keep parameter estimation, a known reference holdout, numerical verification and independent
physical validation separate. Apparatus-adjusted parameters are not measured material properties.
Read which settings actually govern the coupled calculation: an inactive component default must
not replace an effective override simply because it appears in the configuration file.

Check forcing, geometry, material, sensor/location and time alignment against the reference.
Methods should preserve the supplied quantities that affect the selected interpretation, such as
thermal resistance dimensions or imposed heating, rather than copying the entire solver inventory.
Numerically similar diagnostics do not resolve an unknown observation definition.
When a point reference actually covers a time window and a compatible history is available, test
whether the modeled variation over that window could explain the discrepancy. Use observed sample
endpoints and keep the checked cases explicit; do not turn this into an inferred uncertainty band.

The `reference_range` calculation maps value/reference/lower/upper or value/reference/half_width.
Declare identical role units and reference_kind: reported-range, figure-reading-envelope or
declared-bound. It computes difference and signed outside_distance from original inputs; a zero
outside_distance means this value lies in the supplied interval, not that the whole model passes.
For absolute temperature the difference is in K. A missing interval remains unavailable, not zero.
Do not use precomputed error/within columns as the only numerical evidence when raw inputs exist.

Printed variation and digitization envelopes must keep their source meaning. Do not turn either
into a 95% confidence interval or a universal tolerance. A pooled cross-case peak summary is not
a separate measurement for every case. Do not average unlike observables into one accuracy score.

## Make the figure and prose tell the same argument

Show complementary evidence together only when it improves the reader's decision. The finite
evidence_panels route supports temporal profiles and supplied reference ranges; choose fields,
groups and panel titles from the scientific question. Preserve original observations and units.
Straight segments on sampled profiles do not establish an interpolated event. Keep different
measurement domains explicit even when they can share a legend or variable name.

Methods defines the comparison and the essential numerical assumptions once. Results describes
the visible pattern and a small set of decisive quantitative anchors. Discussion uses physical
reasoning and relevant literature to explain what the joint observations support or contradict.
Conclusions states that supported contribution, without escalating it to a system guarantee.
Use current cross-section numeric bindings; do not manually repeat rounded numbers in each part.

Connect literature to the specific explanation: report the similar observation or mechanism,
then the relevant differences in forcing, geometry, model or observable. Read the cited passage,
not just its title or DOI. A precedent establishes neither this model's validity nor the
uniqueness of fitted parameters. Keep unavailable literature support as a specific task note.

Put data-selection bookkeeping, unanswered procedural questions and verification logs in
evidence_notes. Necessary limitations stay at the point where they change interpretation, not
in every paragraph. Prefer a concise supported inference to repeated declarations of caution.
Scientific depth comes from discriminating explanations, not word count, metric count or caveats.
Reference tokens already include their Figure/Table/Equation labels; do not prepend the same
literal label. Reader-facing bibliography entries use publication metadata or stable identifiers;
keep local file/line locators in the literature support records or notes, not the citation label.
