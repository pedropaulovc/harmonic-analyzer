"""Native dimensional and print contract for the approved simple L bracket."""

from __future__ import annotations


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
    "Neck": {"NeckThickness": 2},
    "FlangeProfile": {"FlangeWidth": 2, "FlangeDepth": 3},
    "Flange": {"FlangeHeight": 2},
    "MountingCoordinates": {"MountingX0": 2, "MountingX1": 2, "MountingY0": 2},
    "TapCoordinates": {"TapFromTip": 2, "TapFromSide": 2},
}
DRAWING_EDGE_PRECISION = {"NeckToFootSide": 2}
DRAWING_REFERENCE_PRECISION = {"OverallHeight": 2}
TAP_PROCESS = "MATES MHA-MG-03 LEVER"
MOUNTING_HOLE_PROCESS = "MATES MHA-SM-03 TAPPED HOLES"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
SURFACE_FINISHES = ()
