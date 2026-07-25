r"""Transgear-stud nominal geometry -- the drawing-FREE constant block shared by
the part build, its ``_spec`` (drawing contract) and ``build_paper_drive_assembly``
(which needs the seat/collar stack to seat the reducer disc on the stud).

PURE DATA, no SolidWorks/COM and no drawing imports (the
``column_clamp_front_geom`` precedent): the assembly depends -- via
``_buildgraph.module_deps_of`` -- on whatever module it imports a constant from,
so the drawing contract must NOT live here. ``transgear_stub_spec`` re-exports
these and adds the sheet data.

Split out 2026-07-24: the assembly had the disc's z as a bare literal, which the
upper-frame re-anchor left behind when the stud (bracket -> support bar ->
column clamp -> column) moved 5.5 forward and the disc did not -- 4 interferences,
the worst 5.6 cm^3 of disc buried in the platen.
"""

from __future__ import annotations


MM_PER_IN = 25.4

BASE_DIA = 0.375 * MM_PER_IN  # 9.525 machine-standard stock (low)
BASE_LEN = 9.1  # bracket plate (4) + gap + latch big hub
SEAT_DIA = 5.0  # turned-down gear seat (feed pinion + disc bores)
SEAT_LEN = 13.8  # feed pinion 9.5 + disc 3 + slack
COLLAR_DIA = 14.0
COLLAR_LEN = 4.0

# Stud-local station of the seat/collar step, measured from the stud's base end
# (the bracket face). The stud is placed Rx(-90), so machine z = STUB_Z0 - this.
SEAT_END = BASE_LEN + SEAT_LEN  # 22.9
