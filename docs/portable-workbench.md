# Portable research and host tools

The workbench copies a selected current research/manuscript workspace and its
optional baseline and author companion. It reuses existing sources, recipes,
stable document identities and refresh. It is not a second project database or
an AI model runtime.

The [portable workbench example](../examples/portable-workbench/README.md) moves
an existing analytical author manuscript, restores it outside the checkout and
exports its retained wording, comments, native equation and current values.

## Copy and continue

```console
cfdpaper portable --workspace current/workspace --baseline current --author returned --task "Continue the current comparison" --output transfer
cfdpaper portable --inspect transfer
```

Choose the smallest current directories that contain the research and author
state needed for this task. The output contains `workspace/`, optional
`baseline/` and `author/`, and `workbench.json`, `TASK.md`, `CONTINUE.md`.
Declared internal paths become relative in the copy; author prose, comments,
Word files and local plotting scripts remain unchanged. Originals are not
overwritten. Copying does not execute recipes or certify the research.

Move this directory and install the matching non-editable package on the other
computer or environment. Read `CONTINUE.md` and inspect before continuing.
The copy excludes Python environments/caches, credentials and native solver
archives. Large external results remain references. Its environment record
identifies the package and Python version; available fonts, renderers and
native extraction backends still depend on the receiving machine.

If external results also moved, prepare a JSON object mapping each actual old
absolute root to its new absolute root. Restore into a new candidate:

```console
cfdpaper portable --restore transfer --external-roots roots.json --output relocated
cfdpaper portable --inspect relocated
```

Mappings act on located declarations, not a disk-wide name search. Missing
sources and unknown absolute references are reported specifically. Text and
script strings are not rewritten by path heuristics. Whole-project SQLite
migration is not provided by this research-copy route.

## Use the same tools from a host

Terminal hosts continue to use CLI/Python. For an MCP host, install the optional
SDK and launch the local stdio server:

```console
python -m pip install "PATH_TO_WHEEL[mcp,docs]"
python -m cfdpaper.mcp_server
```

Replace `PATH_TO_WHEEL` with the matching candidate/release wheel, not an older
release lacking these tools. Use the actual installed Python executable in host settings. A minimal MCP
configuration is:

```json
{"mcpServers":{"cfdpaper":{"command":"PYTHON_EXECUTABLE","args":["-m","cfdpaper.mcp_server"]}}}
```

Replace `PYTHON_EXECUTABLE` with that environment's executable. No model API key
is needed by the server; the host supplies its own research intelligence.
SDK 1.x is optional and constrained to `<2` to retain the package's Python
3.10–3.12 support. See the [official maintained SDK documentation](https://py.sdk.modelcontextprotocol.io/v1/).

The nine task functions in `cfdpaper.host_tools` are also usable directly:

| Task | Function |
|---|---|
| Locate definitions and records | `inspect_materials` |
| Prepare portable analysis inputs and skills | `prepare_analysis_task` |
| Compute a selected analysis and continue to writing inputs | `run_analysis_task` |
| Saved JSON reports to bound calculations and three-section writing | `report_task` |
| Surface research, diagnostics, figures and refresh | `research_task` |
| Current section context | `writing_context` |
| Manuscript preparation, assembly and formal export | `manuscript_task` |
| Managed Word preparation and return | `author_task` |
| Copy, inspect and restore selected research state | `workbench_task` |

They return the task, output root, existing artifact paths, current context and
specific missing items. Large records remain in the located source reports.
Analysis preparation returns column/unit summaries and precise pointers to full
profiles instead of repeating document excerpts in the tool chat. A selection
containing only method text is not yet an executable numeric table. For saved
JSON scalar reports, use the direct route below instead of constructing a generic
proposal; other materials may require an existing CSV/NPZ export.
MCP and CLI use existing business functions, not separate calculations. Choose
the path suited to the materials; not every study is a surface-field study.

## Saved reports to writing in two calls

Read the original reports and method definitions before selecting quantities.
Then call `report_task` with case IDs, relative source paths and exact JSON
pointers. This example expects native reports with `/pressure/inlet` and
`/pressure/outlet` in Pa, setup records with `/inlet/intensity`, and a shared
`reference.json` with approximate pressure readings at `/figure/A` and `/figure/B`
in Pa. `method.md` defines the endpoint difference and the numerical reference
comparison; its pressure operator need not be assumed equivalent to the reference.

```python
from pathlib import Path
from cfdpaper.host_tools import report_task

prepared = report_task(
    output=Path("prepared"), root=Path("raw"),
    title="Pressure-report comparison",
    question="How do the saved pressure differences compare with the supplied readings?",
    cases=[
        {"id": "A", "source": "A.json",
         "sources": {"setup": "A-setup.json", "reference": "reference.json"}},
        {"id": "B", "source": "B.json",
         "sources": {"setup": "B-setup.json", "reference": "reference.json"}},
    ],
    quantities=[
        {"id": "dp", "label": "Area-weighted static-pressure difference", "unit": "Pa",
         "output_unit": "kPa", "domain": "numerical pressure comparison at declared states",
         "comparison": "/pressure/inlet", "reference": "/pressure/outlet"},
        {"id": "intensity", "label": "Prescribed inlet turbulence intensity", "unit": "",
         "domain": "saved inlet specification", "source_key": "setup",
         "pointer": "/inlet/intensity", "table": False},
        {"id": "figure", "label": "Approximate reading; pressure operator unspecified", "unit": "Pa",
         "output_unit": "kPa", "domain": "numerical pressure comparison at declared states",
         "source_key": "reference",
         "pointer": {"A": "/figure/A", "B": "/figure/B"}, "table": False},
    ],
    derived=[{
        "id": "excess_A", "label": "Relative excess over the reference reading",
        "reference": "figure_A", "comparison": "dp_A", "field": "relative_change",
        "percentage": True, "places": 2,
        "domain": "numerical pressure comparison at declared states",
        "comparison_scope": "Reference pressure operator unspecified; not direct validation",
        "definition_source": "method.md:L1-L3",
    }],
    formulas={"pressure_difference": {
        "source": "method.md:L1",
        "expression": {"kind": "row", "children": [
            {"kind": "symbol", "text": "Δp"}, {"kind": "text", "text": " = "},
            {"kind": "sub", "children": [
                {"kind": "symbol", "text": "p"}, {"kind": "text", "text": "in"}]},
            {"kind": "text", "text": " − "},
            {"kind": "sub", "children": [
                {"kind": "symbol", "text": "p"}, {"kind": "text", "text": "out"}]},
        ]},
    }},
)
# Fill the three draft.json files named by workspace/drafts.json.
# Use e.g. {{value:dp_A}}, {{value:excess_A}} and {{math:pressure_difference}}.
candidate = report_task(output=Path("candidate"), workspace=Path("prepared"),
    drafts=Path("prepared/workspace/drafts.json"))
```

The CLI uses the same function. Put the title, question, case/quantity declarations
and optional `context`, `support_files`, `derived` and `formulas` in `study.json`
(source paths are relative to `--root`), then run:

```console
cfdpaper report --study study.json --root raw --output prepared
cfdpaper report --workspace prepared --drafts prepared/workspace/drafts.json --output candidate
```

A scalar uses `pointer` instead of the endpoint pair; a pair means comparison
minus reference. `case.sources` declares named extra JSON records and
`quantity.source_key` selects one; omitting it uses the primary case source.
A pointer or either endpoint can be an exact case-ID map, with an entry for every
case; it is not a key search or fallback rule. The selected physical quantity
must remain consistent across cases. Unit conversion is explicit, not inferred
from the file name. Dimensionless method parameters use `unit: ""`;
`table: false` keeps their evidence available without adding Results-table rows.

Base evidence IDs are `QUANTITY_CASE`, such as `dp_A`. `derived` selects two
existing base evidence IDs, not other derived entries or arbitrary expressions.
Its four `field` choices are `difference` (comparison minus reference), `ratio`
(comparison/reference), `relative_change` ((comparison−reference)/reference),
and `relative_reduction` ((reference−comparison)/reference). The declared
`reference` is the denominator for the latter three; `percentage: true` displays
a relative result as percent once. Supply `domain`, `comparison_scope` and a
located `definition_source` (`file:Lx-Ly`) for the physical meaning, not just a
label. The comparison engine requires both parent domains and the declared
derived domain to match. Here they share a numerical-comparison domain; the
different observation definitions still belong in labels and `comparison_scope`,
not an assertion that the reference pressure operator is equivalent. The compact
result retains that denominator and both parent supports; no chained calculation
DAG is implied.

Each `formulas` entry supplies `source` and an existing structured `MathNode`
`expression`, not a TeX string. Both definition and formula source files are
retained automatically. A paragraph's `{{math:pressure_difference}}` token is
connected to native editable Word mathematics during the second call; an
author's existing paragraph-local `inline_math` entry takes priority.

The tool retains raw JSON, exact pointers and method files, calculates through
the existing table engine and provides an editable, bound Results table.
The host writes the science in the prepared Methods/Results/Discussion drafts.
The second call rereads retained JSON before assembly: current source values
drive text tokens and table cells together, while author prose is kept.
It does not automatically revise interpretations after a definition or value changes.
No scientific prose, convergence proof or approval is generated by preparation.

## What still requires research judgment

The host reads methods, chooses useful comparisons and explains the evidence.
The tools cannot infer an unrecorded pressure definition, establish convergence
from a status flag, or turn a computed difference into independent validation.
Current source values and physical definitions drive refresh; Word contributes
author wording and presentation. Keep author comments and local figure scripts.
Inspect newly produced figures and document pages in the receiving environment.

An actual second-host task must include real analysis and writing, not merely
tool discovery. Interface compatibility, scientific effects and author effort
are separate outcomes. Existing analytical examples can test installation;
they do not replace heterogeneous real CFD results.
