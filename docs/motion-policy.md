# Motion & simulation policy

## Solver: Basic Motion only — never Motion Analysis

The model is validated with SolidWorks **Basic Motion** (physical simulation) and mate-driven
kinematics. The **Motion Analysis** add-in is deliberately **not** used and is **not required**
to build, open, inspect, or validate the release. (It is also unavailable on the Makers seat.)

Basic Motion is treated as a **kinematic / visual smoke-test layer**, validating:

- the mechanism moves and the channels **decohere** (each runs at its own harmonic);
- gear ratios hold (cone `j` ↔ cylinder 120; crank 16:64);
- rockers oscillate at the correct **relative** frequencies;
- amplitude bars stay constrained, springs stay within their travel envelope;
- no catastrophic interference across a crank revolution.

It is **not** trusted for: crank torque, contact/spring force, friction, dynamic vibration,
gear-tooth or cam stress, or tolerance stackup under load.

## The summation is computed, not simulated

The summing lever's position is a **static force equilibrium** among 20 channel springs + 1
counter spring, magnified ~4× to the pen. This cannot be faithfully simulated here:

- mate-driven animation has no forces, so it cannot sum at all;
- Basic Motion *has* springs, but a 20-spring stiff equilibrium feeding a 4× magnifier is
  exactly the convergence-hostile case its approximate solver handles worst.

**Resolution — compute it.** The math is known:

```
pen Y(θ) = magnify · Σ aⱼ · cos(j·θ)      (aⱼ = amplitude-bar positions)
```

`cad/scripts/truth_model.py` computes `Y(θ)` deterministically, and the pen is driven
**kinematically** off that math — no force solver. Concretely (`cad/scripts/pen_driver.py`,
installed by `build_output_assembly.py`):

- a manual **`CrankDeg`** global in `output.SLDASM` is the curve's phase input (a standalone
  global, deliberately *not* coupled to the drive-train crank — the summation is computed, so
  the pen need not be mechanically slaved to the train, and `output.SLDASM` stays testable in
  isolation);
- the Fourier sum is accumulated through a chain of partial-sum globals `S1..S20`
  (`Sₖ = Sₖ₋₁ + aₖ·cos(k·CrankDeg + φₖ)`) — SW's equation manager rejects a single 20-term
  expression, so it is chained — then `PenY = Magnify · S20`;
- the **pen-rod travel mate** dimension is equation-linked to `PenY`, mapped onto a physical
  half-stroke (`machine.yaml output.pen_trace_half_mm`) since the demo coefficients are
  dimensionless. At `output.pen_rest_crank_deg` the equation subtracts `pen_y(rest)` (via a
  `PenRest` global) so the pen sits at its build datum and the saved render pose is unchanged.

This is acceptable because the machine is slow and equilibrium-dominated (inertia negligible) —
it is reproduced **numerically**, not dynamically.

**Secondary cost:** no force/torque results from the sim, so crank effort and spring-rate
sizing are done **analytically** (external spring calculations), not read off a study.

## How the summation is verified

- **Numerically** (no SolidWorks): `verify.py --suite math` (doit: `check:math`) proves
  `truth_model` is a correct band-limited synthesiser — per-channel single-term traces,
  superposition, the canonical square/sawtooth/fundamental presets against their analytic targets.
- **Kinematically** (in SolidWorks): `verify.py --suite kinematics` (doit: `verify:kinematics`)
  opens `output.SLDASM`, sweeps
  `CrankDeg` over a full period, and asserts the sampled pen-marker tip traces
  `truth_model.pen_y` (to the mapped half-stroke) within tolerance — the geometry realises the
  computed curve.

## Where contact *is* tested

Local cam/follower and spring/lever contact is exercised only in **small isolated
subassemblies** (see `verify.py --suite subsystems`, doit: `verify:subsystems`). The full
21-spring equilibrium is never
solved in the top-level assembly.
