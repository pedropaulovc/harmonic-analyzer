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
# Outside free-foot rounds stay at the title block's .010 edge break; the
# unloaded inside X-root (-X neck face to -Z foot underside, opposite the
# flat +Z MHA-SM-03 seat; #3742) permits R.02 MAX so .015 corner-radius 3/8
# and 1/2 in carbide end mills cover every steel pass. Modeled at the limit;
# swTolMAX prints "R.02 MAX".
FOOT_CORNER_R = edge_break_radius_mm(unit=UNIT)
INSIDE_ROOT_R_PLACES = 2
INSIDE_ROOT_R_MAX = 0.02 * 25.4
INSIDE_ROOT_R_BAND = (0.0, -INSIDE_ROOT_R_MAX)  # (upper, lower)
INSIDE_ROOT_R_TOL_TYPE = 6  # swTolType_e.swTolMAX: prints "R.02 MAX"
DRAWING_DIMENSIONS = {
    "NeckProfile": {"NoseR", "SeatToAxis"},
    "Neck": {"NeckThickness"},
    "FlangeProfile": {"FlangeWidth", "FlangeDepth"},
    "Flange": {"FlangeHeight"},
    "RootAndFootRounds": {"InsideRootRadius"},
    "MountingCoordinates": {"MountingX0", "MountingX1", "MountingY0"},
    "TapCoordinates": {"TapFromTip", "TapFromSide"},
}
# Inch places. Three on the +/-.002 head and mounting controls and the foot
# grip; two on the neck (thread engagement), the foot length and width
# (mounting walls), the seat-to-axis reach and the R.02 MAX inside X-root.
DRAWING_PRECISION = {
    "NeckProfile": {"NoseR": 3, "SeatToAxis": 2},
    "Neck": {"NeckThickness": 2},
    "FlangeProfile": {"FlangeWidth": 2, "FlangeDepth": 3},
    "Flange": {"FlangeHeight": 2},
    "RootAndFootRounds": {"InsideRootRadius": INSIDE_ROOT_R_PLACES},
    "MountingCoordinates": {"MountingX0": 3, "MountingX1": 3, "MountingY0": 3},
    "TapCoordinates": {"TapFromTip": 3, "TapFromSide": 3},
}
# Owner decision: preserve geometry and explain these structural controls.
# They retain tap material, not a profile fit.
HEAD_MATERIAL_TOL = 0.0508  # +/-.002
# The screw-grip stack reads the foot thickness's printed .XXX title-block
# band; the sheet carries no explicit tolerance for it.
FOOT_GRIP_TOL = printed_band_mm(
    DRAWING_PRECISION["FlangeProfile"]["FlangeDepth"], unit=UNIT
)
DIMENSION_CALLOUTS = {
    "NeckProfile": {"NoseR": "RETAINS TAP WALL"},
    "TapCoordinates": {
        "TapFromTip": "RETAINS TAP WALL",
        "TapFromSide": "RETAINS TAP WALL",
    },
    "FlangeProfile": {"FlangeDepth": "MHA-MG-VN-53\nSCREW GRIP"},
}
DRAWING_REFERENCE_PRECISION = {"OverallHeight": 2}
# Every native Hole Wizard drill size prints .XXX.
MOUNTING_HOLE_PRECISION = {"hw-diam": 3}
TAP_HOLE_PRECISION = {"hw-thrutapdrldia": 3}
TAP_PROCESS = "MATES MHA-MG-03 LEVER"
# The foot holes drill to the title block's .XXX row; the MHA-SM-03 taps are
# spotted through them at assembly (owner ruling 2026-11-08, #2144 item 11.1).
MOUNTING_HOLE_PROCESS = "MATES MHA-SM-03 TAPPED HOLES"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
