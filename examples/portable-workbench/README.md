# Move a workbench and continue its author manuscript

This example consumes the existing public `author-collaboration` output. It exports the current
manuscript candidate with its baseline and author companion, moves the bundle, inspects and restores
it, then reassembles and exports the existing author manuscript through installed product APIs.
The pipe values are analytical and the author changes are scripted automation, not real CFD results
or a human review. No model or solver is invoked.

## Run anywhere

Install the matching wheel with the `docs` extra. A pre-portability release is not sufficient.
Copy `author-collaboration/` and `portable-workbench/` from the public examples ZIP anywhere writable;
neither script needs the checkout or repository paths on `PYTHONPATH`.

```text
python -m pip install "PATH_TO_MATCHING_WHEEL[docs]"
python /path/to/examples/author-collaboration/run_example.py /path/to/author-output
python /path/to/examples/portable-workbench/run_example.py /path/to/author-output /path/to/portable-output
```

Replace the wheel placeholder with the actual wheel path. Skip the second command if you already
have that example's completed output. Each output directory must be new; inputs are not overwritten.
The portable script only requires the existing output, so the prerequisite script need not remain
beside it. Relative command-line paths are resolved from the current working directory.

## Continue from the moved state

`portable-output/receiving-machine/workbench/` is the moved transfer, with `TASK.md`, `CONTINUE.md`,
`workspace/`, `baseline/` and `author/`. `restored/` is a fresh restored copy. The script uses its
`workspace/` and `drafts.json` to reassemble the manuscript; it does not regenerate the supplied prose
or repeat the source correction. There are no external source roots to remap in this small example.

Open `portable-output/continued.docx`. It retains the existing “Across the prescribed cases” wording,
the unresolved **Automation example** comment and the native Word equation. The current endpoint
values remain **7.04 and 21.12 Pa**, rather than the baseline's 6.40 and 19.20 Pa.
`example-result.json` records both inspections and the continued bound values.

For an actual transfer, move the bundle to the receiving environment and install the matching
non-editable package there. Read its continuation notes and inspect before continuing:

```text
cfdpaper portable --inspect /path/to/moved/workbench
cfdpaper portable --restore /path/to/moved/workbench --output /path/to/new-restored
```

See [the portable-workbench guide](../../docs/portable-workbench.md) for explicit external-root
mapping. Inspection checks declarations, not scientific validity or Word page layout; inspect the
resulting pages in the receiving environment before delivery.
