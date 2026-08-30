# Limitations

CFD-Paper-Agent v0.1.0 is not a CFD solver and does not validate a model merely because result
files exist. It cannot replace domain expertise, experimental validation, source-literature
verification, or author responsibility.

The public CLI currently supports only `init`, `status`, `inspect`, and ranking of
author-supplied candidates with `plan`. Inspection creates a source index, not verified scientific
evidence. The `analyze` through `export` commands are roadmap placeholders; they exit non-zero and
do not produce completed workflow artifacts.

Native solver support is also roadmap work, not a general v0.1.0 capability. The public
Quickstart uses synthetic neutral files. Optional retrieval and adapter extension points do not
establish support for a solver, file format, turbulence model, physical domain, or validation
standard.

Scientific interpretation must stop at an evidence-maturity report when case comparability,
convergence, conservation, units, QoI definitions, or provenance are insufficient. Discrete CFD
screening must not be presented as an experimental operating window, optimum, safety boundary, or
validation claim.

Topic approval remains an author action. It records a bounded research direction or topic scope;
it does not authorize or execute analysis, manuscript production, journal submission, appeals, or
external communication.
