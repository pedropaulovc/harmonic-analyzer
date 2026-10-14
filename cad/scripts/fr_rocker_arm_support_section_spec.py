"""Rocker-arm-support casting section nominals.

PURE DATA, no imports beyond ``_inch``: the trapezoid's half-extents, the window square half
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

from _inch import inch

WIDE = inch(1.25)  # 31.75: foot half-width (local Z) at y = -HALF_Y (2-1/2 in foot)
# Top half-width (local Z) at y = +HALF_Y: the apex span 2*NARROW snapped to
# 11/16 in (17.4625; was the source's 16.933, half 8.4665).
NARROW = inch(11, 32)
HALF_Y = inch(3.5)  # 88.9: trapezoid half-height (Y); the foot is the -Y face at y = -HALF_Y
BIG = inch(3.25)  # 82.55: 6-1/2 in (165.1 mm) window square half (Cut-Extrude3/4)
FOOT_THICKNESS = HALF_Y - BIG  # 1/4 in (6.35)
