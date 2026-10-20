# Recover Word edits alongside a source update

This small analytical pipe example demonstrates the managed manuscript route in v0.23.
It starts with ordinary CSV source rows and supplied Methods/Results prose, produces a Word
manuscript with an editable equation and table, and recovers a wording edit and comment while
rebinding the current pressure values. It uses the installed public APIs, not test fixtures.

## Run

Install the release wheel or source package with the `docs` extra. Copy this directory anywhere
writable; the script does not need the repository on `PYTHONPATH` or a particular working directory.

```text
python -m pip install "cfd_paper_agent-0.23.0-py3-none-any.whl[docs]"
python /path/to/author-collaboration/run_example.py /path/to/new-output
```

In a source checkout, the second command can instead be:

```text
python examples/author-collaboration/run_example.py output/author-demo
```

Open `new-output/recovered/manuscript.docx`. The generated baseline is kept under `author/`;
`automation-return.docx` is the scripted demonstration return, not an actual person's review.
The sample supplies its scientific prose. No model, solver or external review is invoked.

## What the replay does

1. Compute analytical pressure rows for a fully developed laminar pipe and bind the endpoint
   pressures into prose and a native Word table. The Methods section retains a native equation.
2. Prepare a managed author copy with stable paragraph/object identities.
3. Script one ordinary prose change and an anchored comment, explicitly attributed to
   **Automation example**. The comment remains unresolved.
4. Regenerate the pressure rows with a corrected viscosity input, separately from the author
   return. Endpoint pressures change from 6.40/19.20 Pa to 7.04/21.12 Pa.
5. Recover the wording change against that current candidate. The script checks the wording,
   current values and comment, then exports research Markdown, report Word and conference TeX.

`recovered/merge.json` separates numerical-display changes from definition changes and conflicts.
`recovered/CONTINUE.md` gives the host the relevant follow-up. A changed region, operator, weight
or time support is a different change from replacing a value; the host must reconsider the
affected explanation. This example's operator and domain do not change.

`conference.tex` is source output, not proof of a successful TeX build or conference compliance.
Open actual Word/PDF pages and compile the TeX file with your chosen template before delivery.

## Use your own edits

Starting from any already assembled manuscript candidate:

```text
cfdpaper author --package CANDIDATE --output AUTHOR_WORKSPACE
```

Edit `AUTHOR_WORKSPACE/manuscript.docx` in Word and save it under a new name. Return against
the current scientific candidate (which may have been updated while you were editing):

```text
cfdpaper author --package CURRENT_CANDIDATE --return-docx AUTHOR_RETURN.docx --output NEW_RETURN
cfdpaper author --package NEW_RETURN/candidate --format docx --profile research --output paper.docx
cfdpaper author --package NEW_RETURN/candidate --format tex --profile conference --output paper.tex
```

Ordinary prose, captions, supported character/paragraph formatting, local Figure/Fig. aliases,
within-section moves and anchored comments can be recovered. Bound numbers, fields, formulas,
changed image contents and overlapping edits need local reconciliation. Keep the whole author
workspace; a detached arbitrary Word file has no generated baseline to merge against.

The reader preserves the original return and produces a new continuing candidate. It does not
decide whether a revised physical interpretation is justified. Profiles change presentation,
not evidence or results; journal-specific requirements still take precedence.
