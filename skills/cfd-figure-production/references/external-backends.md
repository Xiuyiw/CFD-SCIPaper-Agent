# Host figure integration

These are task instructions, not a new renderer or an automatically invoked service.
Use the task's exact purpose, labels, units, sources and claim ceiling. The `kind`
selects the layers to produce, not the scientific interpretation.

## Data and hybrid layers

Use the installed scientific data-plotting Skill with Matplotlib, or the existing
`cfdpaper.publication.analysis_section.render_analysis_figures` route when its
input is already an analysis-section JSON. `task.json` is not an analysis-section
input: for other tables the host supplies a focused local Matplotlib script.
Read x/y/case values from the same row together; never filter columns independently.
Keep missing values explicit, the declared statistical domain, units and original
case mapping. Do not smooth discrete CFD cases or invent uncertainty.

Choose panels from the relationship: composition for defined additive terms,
aligned axes for unlike units, category matrices for discrete cases, or a small
table when a plot contributes no useful relationship. Hybrid figures may combine
data with conceptual layers, existing field images, or both; no field image is
required. Preserve real field images and their colorbars. A schematic may include
one as a read-only reference but must not replace it with a generated field.

Retain a Python source, original table dependencies and preview. Prefer SVG/PDF
with live text and high-resolution PNG/TIFF as additional exports. A Python file
accepted by import has only been parsed, not executed or scientifically checked.

## Conceptual layers

Read [editable-schematic-adaptation.md](editable-schematic-adaptation.md).
If installed, invoke `codex-paper-figure-skill` with that adaptation and task.json;
otherwise its adapted executable host procedure is included locally. No API key,
image service, icon download or framework installation is required. Existing SVG
or draw.io tools are sufficient. Import never launches a returned script or CLI.

## Return and local edits

Use `delivery-template.json`. Artifact paths are relative to delivery.json and are
preserved on import. Keep unchanged input files in `sources/`; the importer copies
them automatically. List any new supporting file in `exports`. A figure script
should resolve its source paths relative to its own location, not the shell cwd.
Unlisted files are not imported. For an author label edit, work from their editable
source and change only the named text; compare source data and other geometry with
the supplied version. Record raster components honestly in delivery notes.

Inspect the actual preview at final manuscript width. Check label/unit fidelity,
arrow meaning, legend and marker consistency, and overlap. Import checks readable
editing formats and preview pixels, not these scientific or visual relationships.
Its result is always a candidate, never author approval.
