"""Rocker-arm-support casting section nominals.

PURE DATA, no imports: the trapezoid's half-extents, the window square half
and the foot thickness they leave. The part build authors the casting from
these, the drawing spec pins the foot-seat finish control to ``HALF_Y``,
``fr_harmonic_base_fasteners`` sizes the hold-down engagement from
``FOOT_THICKNESS``, and the frame, the drive train and the rocker-bracket seat
layout read the foot and wall -- all without importing the builder, whose
sketch, drawing-mark and PMI recipe would otherwise ride their cache keys
(#880, #743). Kept apart from ``fr_rocker_arm_support_spec`` (the world-placement
contract, which reads the machine anchors) so a placement edit does not re-key
the casting.

Local frame, as build_fr_rocker_arm_support draws it on the Right plane: Y is the
height with the foot at -HALF_Y, Z the wall thickness.
"""

from __future__ import annotations

WIDE = 31.75  # foot half-width (local Z) at y = -HALF_Y
NARROW = 8.4665  # top half-width (local Z) at y = +HALF_Y
HALF_Y = 88.9  # trapezoid half-height (Y); the foot is the -Y face at y = -HALF_Y
BIG = 82.55  # 165.1 mm square half (Cut-Extrude3/4)
FOOT_THICKNESS = HALF_Y - BIG
