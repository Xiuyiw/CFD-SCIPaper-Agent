# Invented thermal histories for a software tutorial

All values are invented. They are neither CFD outputs nor measurements and do not represent a
battery, a material intervention or a validated physical model. A and B are two illustrative
records on the same observation window, time origin and nonuniform saved grid: 0, 1, 3, 6, 8, 12 s.

temperature_K is an illustrative domain-maximum absolute temperature. heat_rate_W is a positive
instantaneous, domain-integrated heat-input rate. cumulative_heat_J is a separately invented
cumulative heat-input ledger on the same domain, not calculated from the saved-rate column.
It is deliberately close to, but different from, the trapezoidal rate reconstruction. Neither
channel supplies storage, heat loss or a complete energy balance.

Compare A and B only on the observed 0–12 s window. Temperature maxima and their earliest saved
times describe this window. The 400 K threshold is a tutorial reporting level; the first saved
sample at or above it is not a native event, ignition threshold or safety limit. Nonuniform
trapezoidal integration joins adjacent instantaneous samples linearly for quadrature only.
Plot lines guide the eye between saved samples; they add no measurements or native event times.

Figure contract: (a) temperature histories show timing and magnitude together; (b) saved heat-input
rates show the differing rate histories; (c) independently supplied cumulative ledgers are read
alongside saved-rate cumulative trapezoidal reconstructions. The comparison demonstrates why
equal reconstructed input does not determine the ordering of the invented temperature peaks.
No causal attribution is available because no transport/storage model was supplied.
