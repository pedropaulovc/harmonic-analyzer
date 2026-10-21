"""Native dimensional and print contract for the approved simple L bracket."""

from __future__ import annotations

import math
import _config
from mg_lever_thread_joint import THREAD_ROOT_ENVELOPE, WALL_MIN

ROOT_R = 0.25
FOOT_CORNER_R = 0.25
DRAWING_DIMENSIONS = {
    "NeckProfile": {"NoseR", "SeatToAxis"},
    "Neck": {"NeckThickness"},
    "FlangeProfile": {"FlangeWidth", "FlangeDepth"},
    "Flange": {"FlangeHeight"},
    "MountingCoordinates": {"MountingX0", "MountingX1", "MountingY0"},
    "TapCoordinates": {"TapFromTip", "TapFromSide"},
    "ThreadEnvelope": {"ThreadRootEnvelope"},
    "RootRounds": {"RootR"},
}
DRAWING_PRECISION = {
    "NeckProfile": {"NoseR": 2, "SeatToAxis": 2},
    "Neck": {"NeckThickness": 2},
    "FlangeProfile": {"FlangeWidth": 2, "FlangeDepth": 3},
    "Flange": {"FlangeHeight": 2},
    "MountingCoordinates": {"MountingX0": 2, "MountingX1": 2, "MountingY0": 2},
    "TapCoordinates": {"TapFromTip": 2, "TapFromSide": 2},
    "ThreadEnvelope": {"ThreadRootEnvelope": 2},
    "RootRounds": {"RootR": 2},
}
SINGLE_LIMITS = {
    ("RootRounds", "RootR"): (ROOT_R, 6),
    ("FootCorners", "FootCornerR"): (FOOT_CORNER_R, 6),
    ("ThreadEnvelope", "ThreadRootEnvelope"): (THREAD_ROOT_ENVELOPE, 6),
}
# Drawing-derived separation of the real neck side and foot outside face.
# Width is already controlled by the tangent semicircle and parallel sides.
DRAWING_EDGE_PRECISION = {"NeckToFootSide": 2}
SCREW_NUMBER = _config.parts("mg-vn-magnifying-bracket-screw")["number"]
FLANGE_DEPTH_CALLOUT = f"{SCREW_NUMBER} SCREW GRIP"
NECK_THICKNESS_CALLOUT = "MHA-MG-03 FULL THREAD ENGAGEMENT"
THREAD_ENVELOPE_CALLOUT = "INTERNAL THREAD ROOT ENVELOPE"
ROOT_CALLOUT = "ALL NECK / FOOT INSIDE CORNERS"
TAP_PROCESS = "MATES MHA-MG-03 LEVER\n45° MOUTH CHAMFERS BOTH ENDS"
MOUNTING_HOLE_PROCESS = "MATES MHA-SM-03 TAPPED HOLES"
# Package RV-01 declares this approved sub-target wall; print only its fact.
# Actual ordinary-dimensional stack, not the conditional sketch's 1.925.
WALL_CALLOUT = f"THREAD-MOUTH WALL {math.floor(WALL_MIN * 1000.0) / 1000.0:.3f} MIN"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
SURFACE_FINISHES = ()
