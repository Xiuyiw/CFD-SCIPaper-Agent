# Limitations

CFD-Paper-Agent v0.3.1 is not a CFD solver and does not validate a model merely because result files
exist. It cannot replace domain expertise, experimental validation, source-literature verification,
or author responsibility.

The public CLI supports `init`, `status`, `inspect`, `plan`, `qualify`, `analyze`, `figure`, and
`write`. The implemented scientific path expects structured case records, located scalar
observations, a declared comparison, and a proposed QoI. It does not convert arbitrary Fluent,
STAR-CCM+, or other native solver files into complete scientific records. Guided intake is
experimental and still requires the author to supply the scientific meaning of the data.

Qualification can reject incomplete membership, unknown units, incompatible cases, missing source
locations, or inadequate convergence, conservation, verification, and validation evidence. Passing
these checks bounds what the software may report; it does not make a physical interpretation true.

Analysis is limited to the declared observations and discrete cases. The current release does not
construct undeclared spatial or temporal integrals, infer missing values, smooth sparse cases,
identify a continuous optimum, quantify a general uncertainty envelope, or perform general
three-dimensional field analysis.

Figure production delivers one evidence-bound panel with source data, a runnable Matplotlib script,
SVG and PNG output, a caption, and focused QA records. It is not yet a general contour, profile,
multi-panel, TIFF, or manuscript-assembly system. Writing produces one results paragraph with
numeric backlinks; it does not yet create a full manuscript, manage literature, or export DOCX or
LaTeX submission packages.

The `review`, `revise`, and `export` commands remain unavailable. Reviewer-response work must be
triggered by real reviewer comments, and journal submission remains an author action.

Discrete CFD screening must not be presented as an experimental operating window, continuous
optimum, safety boundary, or validation claim. Author approval selects a reporting direction within
the available evidence; it cannot override missing or failed scientific support.
