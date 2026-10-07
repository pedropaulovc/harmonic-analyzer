"""Pure-data drawing contract for the rocker-arm support.

Split from ``fr_rocker_arm_support_spec`` on purpose: that module is the WORLD
PLACEMENT contract ``build_fr_frame_assembly`` and ``build_fr_harmonic_base`` import,
so product-definition prose living there would send both down the ~500 s full
rebuild on a finish edit (the codex #354 lesson for connecting-rod). This module
is imported only by the part build (native finish, machining property and face
witness) and its drawing. The new pickup machining requirement adds no Ra or
dimensional tolerance: it qualifies the existing end/tapered faces, not an
invented perpendicular side or a relocated table origin.
"""

from __future__ import annotations

import math

from _gtol_spec import PlanarFace
from _surface_finish import SEAT_UM, SurfaceFinishControl
from fr_rocker_arm_support_section_spec import BOSS_DEPTH, HALF_Y, NARROW, WIDE

# The mounting face retains its already-authoritative seat roughness. The user's
# casting-plus-machined-pickups decision adds machining, NOT a new Ra or band.
# PlanarFace offsets run along the UNIT outward normal (point . normal).
_TAPER_SLOPE = (WIDE - NARROW) / (2.0 * HALF_Y)
_TAPER_NORMAL_LENGTH = math.hypot(_TAPER_SLOPE, 1.0)
TABLE_PICKUP_FACES = {
    "table_pickup_end": PlanarFace((-1, 0, 0), BOSS_DEPTH / 2.0),
    "table_pickup_taper": PlanarFace(
        (0, _TAPER_SLOPE / _TAPER_NORMAL_LENGTH, -1.0 / _TAPER_NORMAL_LENGTH),
        (WIDE + NARROW) / (2.0 * _TAPER_NORMAL_LENGTH),
    ),
}

# The unchanged table corner is the intersection of these two physical faces
# with the existing -Y mounting plane, extended past the rim chamfers. There is
# no perpendicular z=-WIDE face: the lower side of the bottom view is tapered.
TABLE_PICKUP_PROCESS_PROPERTY = "Table Pickup Process"
TABLE_PICKUP_PROCESS = (
    "CASTING: MACHINE MOUNTING FACE, BOTTOM-VIEW LEFT END\n"
    "AND LOWER TAPERED SIDE BEFORE HOLE LOCATION OR INSPECTION.\n"
    "TABLE ORIGIN IS THE THEORETICAL SHARP INTERSECTION\n"
    "OF THESE FINISHED FACES."
)
SURFACE_FINISHES = (
    SurfaceFinishControl("mounting_face", SEAT_UM, PlanarFace((0, -1, 0), HALF_Y)),
)
