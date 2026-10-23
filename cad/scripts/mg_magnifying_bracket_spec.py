"""Native dimensional and print contract for the approved simple L bracket."""

from __future__ import annotations

from _printed_tolerance import printed_band_mm


# Nominal tangent root geometry; the title block owns inside R1.0 MAX.
# R0.60 plus the ordinary R0.25 outer edge round fills the 0.85 side offset.
ROOT_R = 0.60
FOOT_CORNER_R = 0.25
DRAWING_DIMENSIONS = {
    "NeckProfile": {"NoseR", "SeatToAxis"},
    "Neck": {"NeckThickness"},
    "FlangeProfile": {"FlangeWidth", "FlangeDepth"},
    "Flange": {"FlangeHeight"},
    "MountingCoordinates": {"MountingX0", "MountingX1", "MountingY0"},
    "TapCoordinates": {"TapFromTip", "TapFromSide"},
}
DRAWING_PRECISION = {
    "NeckProfile": {"NoseR": 2, "SeatToAxis": 2},
    "Neck": {"NeckThickness": 1},
    "FlangeProfile": {"FlangeWidth": 1, "FlangeDepth": 3},
    "Flange": {"FlangeHeight": 1},
    "MountingCoordinates": {"MountingX0": 2, "MountingX1": 2, "MountingY0": 2},
    "TapCoordinates": {"TapFromTip": 2, "TapFromSide": 2},
}
# Owner decision: preserve geometry and explain these structural controls.
# They retain tap material and the real screw-grip stack, not a profile fit.
HEAD_MATERIAL_TOL = 0.05
FOOT_GRIP_TOL = printed_band_mm(DRAWING_PRECISION["FlangeProfile"]["FlangeDepth"])
MOUNTING_MATE_FLAG = "[1]"
DIMENSION_CALLOUTS = {
    "NeckProfile": {"NoseR": "RETAINS TAP WALL"},
    "TapCoordinates": {
        "TapFromTip": "RETAINS TAP WALL",
        "TapFromSide": "RETAINS TAP WALL",
    },
    "FlangeProfile": {"FlangeDepth": "MHA-MG-VN-53\nSCREW GRIP"},
    "MountingCoordinates": {
        "MountingX0": MOUNTING_MATE_FLAG,
        "MountingX1": MOUNTING_MATE_FLAG,
        "MountingY0": MOUNTING_MATE_FLAG,
    },
}
DRAWING_EDGE_PRECISION = {"NeckToFootSide": 2}
DRAWING_REFERENCE_PRECISION = {"OverallHeight": 2}
TAP_PROCESS = "MATES MHA-MG-03 LEVER"
MOUNTING_HOLE_PROCESS = f"{MOUNTING_MATE_FLAG} MATES MHA-SM-03 TAPPED HOLES"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
SURFACE_FINISHES = ()
