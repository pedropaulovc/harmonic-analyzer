---
name: amplification-wires
description: The two magnifying-wheel wires and how the Motion study (Phase F) must model them
metadata: 
  node_type: memory
  type: project
  originSessionId: ba03bcc4-d81e-4e71-bbc7-7926c9a87d29
---

The harmonic analyzer's output amplification runs through TWO inextensible
steel WIRES at the magnifying wheel — both crucial for the Motion study, both
kinematic couplings (NOT springs). User flagged this explicitly 2026-06-13.

Topology (DIMENSIONS.md ch20 pp.46-49, ch21 pp.50-53, strongest-sourced):
`20 channels → summing-lever → magnifying-lever (rotates; adjustable ≤4× set by
the CLAMP position on the Ø-rod) → clamp+vertical-rod+OUTPUT-FIXTURE ride the
lever → WIRE 1 hooks the output-fixture (its mostly-vertical travel) and wraps
wheel hub Ø20 → magnifying-wheel → WIRE 2 leaves wheel rim Ø100 → pen-rod
(vertical travel)`. Wheel ratio Ø100/Ø20 = 5× (annotated). WIRE 1 attaches to
the output-fixture/vertical-rod (ch20 p.48: "the output fixture rides on it and
the wire to the magnifying wheel hooks below"), NOT the lever body directly. In
Phase D these 4 input-linkage parts are LOCKED to the magnifying-lever (clamped
at the set radius) so they rotate with it.

Neither wire is modeled as geometry (flexible — same convention as the drive
bead-chain's "connecting wire not modeled"). In **artifact A** (fully-defined
SLDASM) the wires are the compliant-chain SNAPSHOT dims (wheel rock snapshot +
pen-rod Y-travel snapshot). In **artifact B** (Motion study, Phase F) the two
snapshots are SUPPRESSED and replaced by:
- WIRE 1 = output-fixture VERTICAL travel → wheel hub rotation. Either a
  rack_pinion (fixture/vertical-rod linear ↔ wheel pitch dia = hub Ø20) or a
  gear `Axis1@magnifying-lever` ↔ `Axis1@magnifying-wheel` at ratio
  r_clamp : R_hub (the lever's adjustable part). Fixture rides the lever.
- WIRE 2 = rack_pinion mate, `Axis1@magnifying-wheel` (pitch dia = rim Ø100)
  ↔ `Axis1@pen-rod` slide axis (pen travel = 50·θ_wheel).

The named part axes added in Phase D (magnifying-lever, magnifying-wheel,
pen-rod slide axis) are exactly the refs these couplings select — Phase D is
the groundwork. `rack_pinion_mate` helper already in _common.py. See
[[harmonic-analyzer-project]].
