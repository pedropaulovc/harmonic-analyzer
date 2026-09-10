"""Pure-data drawing contract for the rocker-arm support.

Split from ``rocker_arm_support_spec`` on purpose: that module is the WORLD
PLACEMENT contract ``build_frame_assembly`` and ``build_harmonic_base`` import,
so product-definition prose living there would send both down the ~500 s full
rebuild on a finish edit (the codex #354 lesson for connecting-rod). This module
is imported only by the part build (which authors the PMI) and its drawing.
"""

from __future__ import annotations

from _gtol_spec import PlanarFace
from _surface_finish import SEAT_UM, SurfaceFinishControl

HALF_Y = 88.9  # trapezoid half-height (Y); the foot is the -Y face at y = -HALF_Y

# The foot seats on harmonic-base: the one face that MUST be cut on a part the
# title block otherwise leaves CAST/MACHINED, so it carries the seat grade.
# PlanarFace offsets run ALONG the outward normal (point . normal), so the -Y
# face at y = -HALF_Y sits at +HALF_Y.
SURFACE_FINISHES = (
    SurfaceFinishControl("mounting_face", SEAT_UM, PlanarFace((0, -1, 0), HALF_Y)),
)
