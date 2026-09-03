r"""Pure-data dimensional contract shared by the cone swing platform and drawing.

PURE DATA, no SolidWorks/COM imports.  ``build_cone_swing_platform`` imports the
marked-dimension NAME map + notes from here; ``draw_cone_swing_platform`` keeps
exactly ``DRAWING_DIMENSIONS`` and imports the plate's plan geometry from
``build_cone_swing_platform`` for its view math.
"""

from __future__ import annotations

import math

from cone_pivot_post_spec import BORE_HEIGHT as POST_CONE_BORE_HEIGHT
from crank_drive_gear_spec import OUTSIDE_DIA as CRANK_GEAR_OUTSIDE_DIA


PLATE_THICKNESS = 6.35

# The recentered DP25.731 gear is smaller than the intermediate DP24.74 gear;
# its complete swept OD now clears the platform top, so the obsolete scallop is
# removed and the plate remains full thickness beneath the mesh.
CRANK_GEAR_PLATFORM_CLEARANCE = (
    POST_CONE_BORE_HEIGHT - CRANK_GEAR_OUTSIDE_DIA / 2.0
)
if CRANK_GEAR_PLATFORM_CLEARANCE < 0.5:
    raise AssertionError("recentered crank gear has under 0.5 mm platform air")


# Lock notch: the engaged stud seat (closed, full-radius end) in the part-local
# plan frame (+x = west, +z = north, origin = the swing pivot).  The notch runs
# from here OUT through the west edge along the pivot's swing chord, so its
# axis points west and slightly north.  build_cone_swing_platform cuts the
# notch from these; the print states the angle (one place, title-block +/-1
# degree) beside the natively dimensioned closed end.
LOCK_NOTCH_SEAT_X = 27.5
LOCK_NOTCH_SEAT_Z = -175.0
LOCK_NOTCH_ANGLE_DEG = math.degrees(math.atan2(LOCK_NOTCH_SEAT_X, -LOCK_NOTCH_SEAT_Z))


# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  The wedge outline is its own sketch dimensions from the pivot
# (the sketch origin): the north-east corner from the pivot, the north edge,
# the west taper's run, the axial length and the south edge.  The lock
# notch's closed end is its cap circle (centre from the pivot, both ways, and
# full-radius diameter); the four corner fillets and the plate thickness are
# feature dimensions.  The two post-mount taps and the pivot hole are Hole
# Wizard features: their sizes are native callouts, their stations entity
# dimensions from the pivot rim (a wizard placement dimension does not
# import reliably, and a hole table anchors only on a vertex). ---
POST_MOUNT_THREAD = "1/4-20"


DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PlateProfile": {
        "NorthHalfW",
        "NorthOverhangDim",
        "NorthEdge",
        "WestTaperDx",
        "PlateLenDim",
        "SouthEdge",
    },
    "Plate": {"PlateT"},
    # The cap centre from the pivot both ways: CapECz is a VERTICAL dimension
    # (its witness lines run across the plate, a few millimetres), CapECx a
    # horizontal one whose pivot witness rides the cone-axis centreline.
    "LockNotchCapEProfile": {"CapECx", "CapECz", "CapEDia"},
    "CornerNE": {"CornerNER"},
    "CornerNW": {"CornerNWR"},
    "CornerSW": {"CornerSWR"},
    "CornerSE": {"CornerSER"},
}

# Notes: part-specific process facts only, never a tolerance, never the
# title block (drawing-simplicity-policy.md rule 6).  Every station, offset
# and radius is a native dimension on the plan; the notes orient the reader
# and give the one value the sketch does not dimension, the notch axis angle.
DRAWING_NOTES = "\n".join(
    (
        "PIVOT END IS NORTH; NOTCH SIDE IS WEST. STATIONS ARE FROM THE PIVOT HOLE ALONG THE CONE AXIS.",
        f"LOCK NOTCH AXIS {LOCK_NOTCH_ANGLE_DEG:.1f} DEG NORTH OF WEST FROM ITS CLOSED END, OPEN THROUGH THE WEST EDGE.",
    )
)
PLAN_VIEW_NOTE = "PLAN VIEW SCALE 1:2"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:3"
END_VIEW_NOTE = "END VIEW SCALE 1:2"
