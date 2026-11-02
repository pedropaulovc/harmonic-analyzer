r"""Pure-data contract for MHA-DT-35, the crank handle's steel butt cup.

User ruling 2026-09-29 (ch11 p.14 and p.15 photographs): the butt of the
ebonized handle carries a bright steel cup, and the slotted head of the pivot
screw MHA-DT-32 sits recessed inside it with a visible ring of clearance.  The
body is epoxied into a counterbore in the oak, and the screw head bears on
the cup's floor, steel on steel, instead of on end-grain wood.

User rulings 2026-09-30 (ch30 eight-views-4 side view, approved CadQuery
concept v4): the cup is a plain cup, no flange, seated flush with the oak's
end; after the epoxy cures the handle's end round is turned on the oak, clear of the
cup, whose face stays flat (local review of fbf82ad96).  Formerly: turned across the oak and
the cup together, so wood and steel read as one rounded butt.  The smaller
MHA-DT-32 head sets the pocket's matched fit.  Owner ruling B on #1375
enlarges the body to retain the rule-17 floor as the pocket wall at the
smallest body and largest pocket.

The pocket is bored to suit the MHA-DT-32 head; the handle's end play is fitted
on the screw shoulder at assembly, so no length here is a stack term.  The
body diameter prints at .XXX because it sets the pocket wall and the
MHA-DT-08 counterbore bored to suit it (that handle's butt wall); the pocket
depth does because it sets how far the head sits below the face (Codex P2
on #1139, user ruling 2026-09-30).

Local frame: the axis is local +X and the origin plane is the cup's outer
face; the body and floor run toward -X (into the handle).  In the handle's
frame the face sits at the handle's basic overall length, so the drive train
places the cup with the handle's own orientation.

PURE DATA, no SolidWorks/COM imports.

Issue #290: the sheet prints decimal inch (``drawing_unit: in``).  Lengths
stay physical millimetres, each the exact decimal of its printed inch value,
and the walls are judged at the inch title block's bands.
"""

from __future__ import annotations

import _config
from _inch_wall_limits import WALL_FLOOR_MM
from _package_units import drawing_unit
from _printed_tolerance import printed_band_mm

UNIT = drawing_unit(
    "parts/dt-crank-handle-butt-cup", _config.parts("dt-crank-handle-butt-cup")
)
# The body and pocket depth print at .XXX, inside the title block's +/-.005.
BODY_DIA_TOL = printed_band_mm(3, unit=UNIT)
# Every axial size reads from the outer face, the one faced end (MHA-DT-35
# re-review): overall and pocket depth.  The floor is what remains, so the
# overall carries enough that its .XX worst case, over the deepest banded
# pocket, still leaves the rule-17 target.
OVERALL_LENGTH = 8.128  # .32
# Deep enough that the longest banded MHA-DT-32 head, at the widest fitted end
# play, still sits below the face (Codex P2 on #1139).  User ruling 2026-09-30.
POCKET_DEPTH = 5.5118  # .217
POCKET_DEPTH_TOL = printed_band_mm(3, unit=UNIT)
# Bored to suit the MHA-DT-32 head (reference size); POCKET_CLEARANCE is the
# diametral clearance the note asks for, and POCKET_DIA_MAX its hard limit
# (the largest head plus the widest clearance).
POCKET_DIA = 6.2992  # .248
POCKET_CLEARANCE = (0.2032, 0.4064)  # .008-.016
POCKET_DIA_MAX = 6.5278  # .257
# Owner ruling B on #1375: the cup grows around the unchanged head and pocket,
# rather than retaining a sub-floor wall or tightening the body band.
POCKET_WALL_FLOOR_MM = WALL_FLOOR_MM
BODY_DIA = 9.7028  # .382: the largest pocket, two .060 walls and the band
# The head bears on the floor: the floor-to-wall corner may round no more than
# the tightest radial clearance, so a sharp-edged, centred head still seats on
# the flat (rule 16: the largest radius acceptable; MHA-DT-35 r1 finding 5).
POCKET_FLOOR_CORNER_R_MAX = POCKET_CLEARANCE[0] / 2.0
POCKET_FLOOR_CORNER_R_BAND = (0.0, -POCKET_FLOOR_CORNER_R_MAX)  # (upper, lower)
POCKET_FLOOR_CORNER_R_TOL_TYPE = 6  # swTolType_e.swTolMAX: nominal is the limit
# The floor hole passes the MHA-DT-32 shoulder: a #20 drill (.161) under the
# title block's DRILLED HOLES band, small enough that the head keeps its
# bearing annulus round it when it floats in the pocket.
FLOOR_HOLE_DIA = 4.0894  # .161
# The body's bottom edge, broken 45 degrees (owner ruling A on #1661): the
# MHA-DT-08 counterbore floor's corner is rounded up to R.012, so the leg's
# lower limit clears it and the cup still seats on the floor, face flush.
# Modelled at the middle; printed as BODY_CHAMFER +/- its tolerance.
BODY_CHAMFER = 0.4064  # .016
BODY_CHAMFER_TOL = 0.1016  # .004
BODY_CHAMFER_MIN = round(BODY_CHAMFER - BODY_CHAMFER_TOL, 6)
BODY_CHAMFER_MAX = round(BODY_CHAMFER + BODY_CHAMFER_TOL, 6)

FLOOR_THICKNESS = OVERALL_LENGTH - POCKET_DEPTH

GENERAL_2PL_MM = printed_band_mm(2, unit=UNIT)
FLOOR_THICKNESS_MIN = round(FLOOR_THICKNESS - GENERAL_2PL_MM - POCKET_DEPTH_TOL, 6)
POCKET_WALL_MIN = round(((BODY_DIA - BODY_DIA_TOL) - POCKET_DIA_MAX) / 2.0, 6)
# Owner ruling B on #1375: 1/2-in cold-finished rod leaves a cleanup cut over
# the largest body.
STOCK_DIA = 0.5 * 25.4

for _ok, _what in (
    (FLOOR_THICKNESS_MIN >= WALL_FLOOR_MM, "cup floor is under .060 at its limits"),
    (
        POCKET_WALL_MIN >= POCKET_WALL_FLOOR_MM,
        "pocket wall is under .060 at its limits (owner ruling B on #1375)",
    ),
    (FLOOR_HOLE_DIA < POCKET_DIA, "floor hole leaves no floor"),
    (BODY_DIA + BODY_DIA_TOL < STOCK_DIA - 0.2, "body is not turnable from 1/2-in rod"),
):
    if not _ok:
        raise AssertionError(f"MHA-DT-35: {_what}")

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "CupProfile": {
        "BodyDia",
        "OverallLength",
        "PocketDepth",
        "PocketDia",
        "FloorHoleDia",
        "BodyChamfer",
        "PocketFloorRadius",
    },
}
# Decimal places are the tolerance (drawing-guidelines.md rule 3 (decimal
# places carry the tolerance)): the body diameter, the pocket depth, the
# drilled floor hole and the small chamfer and corner limits print at .XXX;
# the overall length is routine (.XX).
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "CupProfile": {
        "BodyDia": 3,
        "OverallLength": 2,
        "PocketDepth": 3,
        "BodyChamfer": 3,
        "PocketDia": 3,
        "FloorHoleDia": 3,
        "PocketFloorRadius": 3,
    },
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked MHA-DT-35 dimension needs authored places")
REFERENCE_DIMENSIONS = frozenset({"PocketDia"})
