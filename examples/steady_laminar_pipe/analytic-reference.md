# Analytic reference

## Model and geometry

The comparison represents steady, incompressible, fully developed laminar flow of a Newtonian fluid through a straight circular pipe with a no-slip wall. The pipe diameter is 0.010 m. The pressure difference is evaluated over a 1.000 m fully developed pressure-tap span. The fluid density and dynamic viscosity are fixed at 1000 kg m^-3 and 1.000e-3 Pa s, respectively.

## Numerical-verification reference

For this model, the Hagen-Poiseuille relation gives

```text
Delta p = 32 mu U L / D^2
Re = rho U D / mu
```

The prescribed velocities 0.050, 0.100, and 0.150 m s^-1 therefore give Reynolds numbers 500, 1000, and 1500 and pressure drops 16, 32, and 48 Pa.

## Validation boundary

The analytic solution verifies the numerical pressure-drop calculation for the stated model. It is not external validation: this example contains no independent experimental or field measurement.
