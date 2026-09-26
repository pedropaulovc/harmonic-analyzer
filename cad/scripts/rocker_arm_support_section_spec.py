"""Rocker-arm-support casting section nominals.

PURE DATA, no imports: the trapezoid half-height, the window square half and
the foot thickness they leave. The part build authors the casting from these,
the drawing spec pins the foot-seat finish control to ``HALF_Y``, and
``harmonic_base_fasteners`` sizes the hold-down engagement from
``FOOT_THICKNESS`` without importing the builder, whose sketch, drawing-mark
and PMI recipe would otherwise ride the base's cache key (#880). Kept apart
from ``rocker_arm_support_spec`` (the world-placement contract, which reads the
machine anchors) so a placement edit does not re-key the casting.
"""

from __future__ import annotations

HALF_Y = 88.9  # trapezoid half-height (Y); the foot is the -Y face at y = -HALF_Y
BIG = 82.55  # 165.1 mm square half (Cut-Extrude3/4)
FOOT_THICKNESS = HALF_Y - BIG
