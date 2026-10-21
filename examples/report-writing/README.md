# Constructed reports to bound writing and source refresh

This small installation example creates synthetic JSON pressure reports, inlet parameters,
constructed reference readings and a method note. It is not real CFD, an experiment, independent
validation or autonomous scientific writing. No model API or solver is invoked.

Install the matching wheel with Word support, copy this directory anywhere writable, then run:

```text
python -m pip install "PATH_TO_MATCHING_WHEEL[docs]"
python /absolute/path/to/report-writing/run_example.py /absolute/path/to/new-output
```

The output directory must not already exist. Relative output paths are also supported. The script
uses installed product APIs; it needs no checkout assets or repository path on `PYTHONPATH`.

Open `new-output/refreshed/manuscript.docx`. The example calls the same `report_task` used by
CLI/MCP: exact JSON endpoint pointers, named setup/reference sources and a case-specific reference
pointer map prepare Methods, Results and Discussion. Supplied example prose uses bound values,
a native Results table and `{{math:ratio}}`, exported as an editable Word fraction.

Both initial pressure differences are 20.00% above their constructed reference readings. Relative
excess explicitly uses the reference as denominator and retains the declared endpoint support
domain. The separate inlet intensity is a saved parameter, not an inferred flow result.

`raw/` and `first/` remain unchanged. In an independent `receiving/current/` copy, the script changes
case A's reference from 100 to 80 Pa and inlet intensity from 0.06 to 0.09, then calls `report_task`
again. The refreshed prose/table show 50.00% for A and retain 20.00% for B, the native fraction and
the example author's wording. `example-result.json` summarizes initial and refreshed values.

This demonstrates numerical binding and installation portability, not automatic interpretation
revision. For actual research, the host/author must choose physically comparable supports, write
the scientific argument and inspect newly exported pages. See the
[report and host-tool guide](../../docs/portable-workbench.md#saved-reports-to-writing-in-two-calls).
