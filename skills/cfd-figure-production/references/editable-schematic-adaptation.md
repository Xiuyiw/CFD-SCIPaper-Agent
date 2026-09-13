# Editable schematic: CFD-Paper-Agent adaptation

Adapted from Pengqian Han's `codex-paper-figure-skill` version 0.0.1 (MIT):
https://github.com/pengqianhan/codex-paper-figure-skill
Upstream file: `codex-paper-figure-skill/SKILL.md`, inspected 2026-09-13.
The upstream notice is included in [codex-paper-figure-MIT.txt](codex-paper-figure-MIT.txt).
This is a modified instruction subset, not an unchanged upstream installation.

## Procedure

1. Extract named entities, required labels and source-supported relations from
   task.json. Sketch their topology before arranging the page; maintain branches
   and feedback directions. Mark hypotheses distinctly from measured observations.
2. Build native SVG text/shapes/connectors, or uncompressed draw.io mxGraphModel
   XML. Keep scientific labels editable. For draw.io include root cells 0 and 1,
   unique element IDs and edge geometry; ordinary objects belong to parent 1.
3. Arrange elements with readable spacing; route connectors outside labels.
   Prefer restrained contrast and a clear reading direction to decorative icons.
4. Export a real PNG/TIFF preview using an available local SVG or draw.io exporter.
   With draw.io Desktop the host can explicitly run
   `drawio -x -f png -o figure.png figure.drawio`.
   If no exporter exists, report that missing artifact rather than substituting
   an invented preview. Reopen the source and inspect the exported result.

## Deliberate changes

- Native SVG is accepted alongside draw.io; no custom canvas implementation.
- Image generation is optional composition exploration, never mandatory or a
  quantitative source. No generated CFD field, reconstructed measurement or
  changed colorbar is permitted.
- Icon sourcing and model-specific steps are omitted. Optional external assets
  need their own license/attribution; this MIT notice does not license those assets.
- One targeted author edit preserves all other topology, labels and style.
- Return files through the local delivery contract. File import is not scientific
  acceptance and never executes returned code.
