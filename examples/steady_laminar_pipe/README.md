# Steady laminar pipe-flow example

This public example exercises the V0.3 evidence workflow with a transparent numerical-verification problem. It uses steady, incompressible, fully developed laminar flow of a Newtonian fluid through a circular pipe.

## Fixed definition

- Pipe diameter: `D = 0.010 m`
- Pressure-tap spacing: `L = 1.000 m`
- Dynamic viscosity: `mu = 1.000e-3 Pa s`
- Density: `rho = 1000 kg m^-3`
- Wall condition: no slip
- Prescribed mean velocities: `0.050`, `0.100`, and `0.150 m s^-1`

The analytic verification reference is

```text
Delta p = 32 mu U L / D^2
Re = rho U D / mu
```

The three Reynolds numbers are 500, 1000, and 1500. The corresponding pressure drops are 16, 32, and 48 Pa. All cases are within the laminar range.

Hagen-Poiseuille flow is used only as a numerical-verification reference. No experimental or field measurement is supplied, so external validation remains not demonstrated. The maximum reporting level is therefore a qualified numerical observation, not a supported physical interpretation.

`observations.csv` contains the reported pressure-drop values. `project-records.json` defines the cases, controlled quantities, numerical checks, and source locations. `question.json` defines the candidate pressure-drop quantity of interest. `topic-candidates.json` provides the author-facing topic candidate after scientific records have been imported. `oracle.json` states the expected results. The files in `negative/` each introduce one defect only.
