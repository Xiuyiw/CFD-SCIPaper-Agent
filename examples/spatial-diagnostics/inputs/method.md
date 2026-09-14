# Analytical fields for a spatial-statistics example

These prescribed piecewise-constant fields are synthetic, not results from a CFD solver or experiment.
wall.csv defines two temperature fields on the same rectangular wall, x=0 to 10 mm and y=0 to 1 mm.
The six facets per case are disjoint, cover the full rectangle and extend across its full y width.
Each facet has constant absolute temperature T [degC]; area [mm2] is its exact physical area.
The x0/x1 coordinates are the facet boundaries. No interpolation or within-facet variation is implied.
Reference and Modified are field labels, not claims about particular heat-sink geometries.
Only temperature is prescribed. Heat input, flow, transport coefficients and pumping work are not given.
The task is to compare wall thermal exposure and spatial distribution, not infer a cooling mechanism.

volume.csv is a separate three-cell example on the same complete volume for its two field labels.
Cell identity is 1, 2, 3 in each case; positive volumes [mm3] are exact and cells do not overlap.
The scalar concentration [1] is constant within each cell. No spatial coordinates are specified.
Use this second dataset to exercise volume-weighted statistics, not as evidence about the wall above.
Neither dataset contains repeated trials, time samples, mesh studies or an uncertainty estimate.
