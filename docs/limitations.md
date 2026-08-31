# Limitations

CFD-Paper-Agent v0.2.0 is not a CFD solver and does not validate a model merely because result
files exist. It cannot replace domain expertise, experimental validation, source-literature
verification, or author responsibility.

The public CLI supports `init`, `status`, `inspect`, and `plan`. `plan` can rank author-supplied
candidates or generate provisional candidates when mature structured scientific records already
exist. Inspection creates a source index, not verified scientific evidence, and v0.2.0 has no
general CLI that converts arbitrary CFD or CSV files into complete case, boundary, convergence,
conservation, QoI-definition, and QoI records.

Generated candidates are limited by current comparability, units, convergence, conservation,
QoI definitions, provenance, and claim ceilings. Missing evidence yields a missing-data result;
author approval cannot override a failed scientific gate. Generated JSON artifacts are recoverable
project state, not a stable public interchange contract.

The `analyze` through `export` commands remain roadmap placeholders. They exit non-zero and do not
produce completed workflow artifacts. Native Fluent, STAR-CCM+, or other solver integration is not
a general v0.2.0 capability; optional adapters and provider interfaces remain extension points.

Discrete CFD screening must not be presented as an experimental operating window, continuous
optimum, safety boundary, or validation claim. Topic approval remains an author action and does
not authorize manuscript production, journal submission, appeals, or external communication.

