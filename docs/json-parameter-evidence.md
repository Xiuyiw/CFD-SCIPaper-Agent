# Source bound numerical methods

Use `json_value_ref` for a numeric method parameter in a copied JSON configuration, instead of
hand-copying its display value into manuscript paragraphs and tables.

```json
{
  "id": "maximum-step",
  "kind": "metric",
  "text": "Maximum internal step for the selected run",
  "source": "Run configuration",
  "json_value_ref": {
    "source": "sources/config.json",
    "pointer": "/solver/max_step_s",
    "unit": "s",
    "places": 2
  }
}
```

The source resolves beside the section input. It is copied automatically by section preparation
and manuscript seeding. `pointer` uses JSON Pointer escapes `~1` for `/` and `~0` for `~`;
zero-based array indices must be exact. Optional `unit_pointer` checks a source field holding
the declared unit string. Numbers remain in the original scale: no conversion is inferred.

The selected value must be a finite native JSON number, not a Boolean, numeric string, object,
array or null. The evidence omits a manual `value`/`unit` and cannot also declare `result_ref`.
An explicit empty unit denotes a dimensionless parameter. Strings such as solver names belong
in located methods prose, not this numeric binding. No source Python code is executed.

Use `{{value:maximum-step}}` in a paragraph, native table or equation. Preparation supplies
`parameter-results.json`; assembly reads the current copied source again. Dependent sections
can borrow the same evidence through the existing manuscript `evidence_bindings` mapping.
Moving the complete manuscript preserves these sources and subsequent reassembly.

The host still determines which setting is effective for the selected case and solution stage.
A stored default is not necessarily the active override. Source changes update numeric displays
and the existing manuscript change report; they do not rewrite an old physical interpretation.

See the [paired-observations example](../examples/paired-observations/README.md) for a four-section
replay with native tables, a reference-envelope figure and an editable Word equation.
