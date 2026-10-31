"""Native dimensional and print contract for the approved simple L bracket.

Issue #290: the sheet prints decimal inch (``drawing_unit: in``). The neck,
nose and foot keep their millimetre nominals because the shared
magnifying_bracket_joint_layout (the MHA-SM-03 receiver joint) and the lever
frame consume them; each prints rounded at its inch places and is judged at
those printed limits.
"""

from __future__ import annotations

import _config
from _package_units import drawing_unit
from _printed_tolerance import edge_break_radius_mm, printed_band_mm

UNIT = drawing_unit(
    "parts/mg-magnifying-bracket", _config.parts("mg-magnifying-bracket")
)

# The matched-width foot has no lateral ledge or axial bridge fillet.
# The inside X-root and free-foot rounds are the title block's edge break.
FOOT_CORNER_R = edge_break_radius_mm(unit=UNIT)
DRAWING_DIMENSIONS = {
    "NeckProfile": {"NoseR", "SeatToAxis"},
    "Neck": {"NeckThickness"},
    "FlangeProfile": {"FlangeWidth", "FlangeDepth"},
    "Flange": {"FlangeHeight"},
    "MountingCoordinates": {"MountingX0", "MountingX1", "MountingY0"},
    "TapCoordinates": {"TapFromTip", "TapFromSide"},
}
# Inch places. Three on the +/-.002 head and mounting controls, the foot grip
# and the foot width (flush with the +/-.002 nose); two on the neck (thread
# engagement), the foot length (mounting walls) and the seat-to-axis reach.
DRAWING_PRECISION = {
    "NeckProfile": {"NoseR": 3, "SeatToAxis": 2},
    "Neck": {"NeckThickness": 2},
    "FlangeProfile": {"FlangeWidth": 2, "FlangeDepth": 3},
    "Flange": {"FlangeHeight": 3},
    "MountingCoordinates": {"MountingX0": 3, "MountingX1": 3, "MountingY0": 3},
    "TapCoordinates": {"TapFromTip": 3, "TapFromSide": 3},
}
# Owner decision: preserve geometry and explain these structural controls.
# They retain tap material and the real screw-grip stack, not a profile fit.
HEAD_MATERIAL_TOL = 0.0508  # +/-.002
FOOT_GRIP_TOL = printed_band_mm(
    DRAWING_PRECISION["FlangeProfile"]["FlangeDepth"], unit=UNIT
)
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
DRAWING_REFERENCE_PRECISION = {"OverallHeight": 2}
# Every native Hole Wizard drill size prints .XXX.
MOUNTING_HOLE_PRECISION = {"hw-diam": 3}
TAP_HOLE_PRECISION = {"hw-thrutapdrldia": 3}
TAP_PROCESS = "MATES MHA-MG-03 LEVER"
MOUNTING_HOLE_PROCESS = f"{MOUNTING_MATE_FLAG} MATES MHA-SM-03 TAPPED HOLES"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
