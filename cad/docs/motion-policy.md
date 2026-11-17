# Motion & simulation policy

## Solver: mate-driven kinematics — no Motion study

The model is validated by mate-driven kinematics only: the saved assemblies keep their
operational DOF free, and `verify:kinematics` / `verify:soundness` drive and gate them. No
SolidWorks Motion study (Basic Motion or Motion Analysis) is built or required to build, open,
inspect, or validate the release; the hand-run Basic Motion study scripts were retired with
#2887 (none was wired into `doit`). The **Motion Analysis** add-in is also unavailable on the
Makers seat.

No simulation result is trusted for crank torque, contact/spring force, friction, dynamic
vibration, gear-tooth or cam stress, or tolerance stackup under load.

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
installed by `build_pn_pen_assembly.py`):

- a manual **`CrankDeg`** global in `pn-pen.SLDASM` is the curve's phase input (a standalone
  global, deliberately *not* coupled to the drive-train crank — the summation is computed, so
  the pen need not be mechanically slaved to the train, and `pn-pen.SLDASM` stays testable in
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
  opens `pn-pen.SLDASM`, sweeps
  `CrankDeg` over a full period, and asserts the sampled pen-marker tip traces
  `truth_model.pen_y` (to the mapped half-stroke) within tolerance — the geometry realises the
  computed curve.

## Where contact *is* tested

Local cam/follower and spring/lever contact is exercised only in **small isolated
subassemblies** — the interference/health gates of `verify:soundness` open every
(sub)assembly standalone (the former `verify:subsystems` suite is retired; its one
unique gate, channel-independence, is folded into soundness). The full 21-spring
equilibrium is never solved in the top-level assembly.
