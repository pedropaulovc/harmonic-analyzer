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
MHA-DT-32 head (Ø6) sets the pocket's matched fit.  Owner ruling B on #1375
enlarges the body to retain a 1.5 pocket wall at the smallest body and largest
pocket, with the existing +/-0.10 body band.  PR1694 option 2 retains that
geometry and adds a pocket-side floor-hole mouth chamfer to clear the screw's
concave under-head fillet throughout the handle's axial float.

The pocket is bored to suit the MHA-DT-32 head; the handle's end play is fitted
on the screw shoulder at assembly, so no length here is a stack term.  The
body diameter keeps a +/-0.10 band because it sets the pocket wall and the
MHA-DT-08 counterbore bored to suit it (that handle's butt wall); the pocket
depth keeps one because it sets how far the head sits below the face (Codex P2
on #1139, user ruling 2026-09-30).

Local frame: the axis is local +X and the origin plane is the cup's outer
face; the body and floor run toward -X (into the handle).  In the handle's
frame the face sits at the handle's basic overall length, so the drive train
places the cup with the handle's own orientation.

PURE DATA, no SolidWorks/COM imports.
"""

from __future__ import annotations

import math

WALL_FLOOR_MM = 1.5
BODY_DIA_TOL = 0.10
# Every axial size reads from the outer face, the one faced end (MHA-DT-35
# re-review): overall and pocket depth.  The floor is what remains, so the
# overall carries enough that its .X worst case, over the deepest banded
# pocket, still leaves 1.5.
OVERALL_LENGTH = 8.1
# Deep enough that the longest banded MHA-DT-32 head, at the widest fitted end
# play, still sits below the face (Codex P2 on #1139: at 5.0 .X against a 4.0
# .X head it could stand 1.6 proud).  User ruling 2026-09-30.
POCKET_DEPTH = 5.5
POCKET_DEPTH_TOL = 0.10
# Bored to suit the MHA-DT-32 head (reference size); POCKET_CLEARANCE is the
# diametral clearance the note asks for, and POCKET_DIA_MAX its hard limit
# (the largest head plus the widest clearance).
POCKET_DIA = 6.3
POCKET_CLEARANCE = (0.2, 0.4)
POCKET_DIA_MAX = 6.5
# Owner ruling B on #1375: the cup grows around the unchanged head and pocket,
# rather than retaining a sub-floor wall or tightening the body band.
POCKET_WALL_FLOOR_MM = WALL_FLOOR_MM
BODY_DIA = round(POCKET_DIA_MAX + 2.0 * POCKET_WALL_FLOOR_MM + BODY_DIA_TOL, 6)
# The floor-to-wall corner protrudes into the head pocket.  Its original
# R0.1 MAX remains; the mating screw's minimum outer chamfer clears it even
# when eccentric float consumes the pocket's radial clearance.
POCKET_FLOOR_CORNER_R_MAX = POCKET_CLEARANCE[0] / 2.0
POCKET_FLOOR_CORNER_R_BAND = (0.0, -POCKET_FLOOR_CORNER_R_MAX)  # (upper, lower)
POCKET_FLOOR_CORNER_R_TOL_TYPE = 6  # swTolType_e.swTolMAX: nominal is the limit
# The floor hole passes the MHA-DT-32 shoulder: a drilled hole under the title
# block's DRILLED HOLES band (+0.10/0).
FLOOR_HOLE_DIA = 4.2
FLOOR_HOLE_DIA_MIN = FLOOR_HOLE_DIA
FLOOR_HOLE_DIA_MAX = round(FLOOR_HOLE_DIA + 0.10, 6)
# Explicit acceptance REQUIREMENTS on MHA-DT-32, not its actual design inputs.
# The screw spec imports these and independently checks its own geometry.
# This module must remain lower-level pure data: never import ScrewSpec.
MATING_SCREW_UNDER_HEAD_FILLET_MAX = 0.1
MATING_SCREW_HEAD_DIA_MIN = 5.9
MATING_SCREW_SHOULDER_DIA_MIN = 3.92
MATING_SCREW_HEAD_EDGE_BREAK_MIN = 0.11
MATING_SCREW_HEAD_EDGE_BREAK_MAX = 0.26
MATING_SCREW_HEAD_BEARING_FLOOR = 0.1
MATING_SCREW_SEATED_GAP_MIN = 0.25
# Native LIMIT at the maximum model leg; both orthogonal legs share one
# global so the bevel is genuinely 45 degrees, not a typed drawing value.
FLOOR_HOLE_MOUTH_CHAMFER = 0.25
FLOOR_HOLE_MOUTH_CHAMFER_BAND = (0.0, -0.14)  # (upper, lower)
FLOOR_HOLE_MOUTH_CHAMFER_TOL_TYPE = 3  # swTolType_e.swTolLIMIT
FLOOR_HOLE_MOUTH_CHAMFER_MIN = round(
    FLOOR_HOLE_MOUTH_CHAMFER + FLOOR_HOLE_MOUTH_CHAMFER_BAND[1], 6
)
FLOOR_HOLE_MOUTH_CHAMFER_MAX = round(
    FLOOR_HOLE_MOUTH_CHAMFER + FLOOR_HOLE_MOUTH_CHAMFER_BAND[0], 6
)
# The body's bottom edge, broken 45 degrees (owner ruling A on #1661): the
# MHA-DT-08 counterbore floor's corner is rounded up to R0.3, so the leg's
# lower limit clears it and the cup still seats on the floor, face flush.
# Modelled at the middle; printed as BODY_CHAMFER +/- its tolerance.
BODY_CHAMFER = 0.4
BODY_CHAMFER_TOL = 0.1
BODY_CHAMFER_MIN = round(BODY_CHAMFER - BODY_CHAMFER_TOL, 6)
BODY_CHAMFER_MAX = round(BODY_CHAMFER + BODY_CHAMFER_TOL, 6)

FLOOR_THICKNESS = OVERALL_LENGTH - POCKET_DEPTH

GENERAL_1PL_MM = 0.8
FLOOR_THICKNESS_MIN = round(FLOOR_THICKNESS - GENERAL_1PL_MM - POCKET_DEPTH_TOL, 6)
POCKET_WALL_MIN = round(((BODY_DIA - BODY_DIA_TOL) - POCKET_DIA_MAX) / 2.0, 6)
# Correlated worst state: hole 4.30, shaft 3.92, offset .19 (not .20 with
# those same sizes).  Every physical pair satisfies e <= (hole-shaft)/2.
HEAD_RUNNING_OFFSET_MAX = round(
    min(
        POCKET_CLEARANCE[1] / 2.0,
        (FLOOR_HOLE_DIA_MAX - MATING_SCREW_SHOULDER_DIA_MIN) / 2.0,
    ),
    6,
)
HEAD_BEARING_RADIAL_CONCENTRIC_MIN = round(
    MATING_SCREW_HEAD_DIA_MIN / 2.0
    - MATING_SCREW_HEAD_EDGE_BREAK_MAX
    - FLOOR_HOLE_DIA_MAX / 2.0
    - FLOOR_HOLE_MOUTH_CHAMFER_MAX,
    6,
)
HEAD_BEARING_RADIAL_MIN = round(
    HEAD_BEARING_RADIAL_CONCENTRIC_MIN - HEAD_RUNNING_OFFSET_MAX, 6
)
# E is a seated gap with the ferrule against the arm, not a running lower
# bound: either complete corner envelope must clear at instantaneous gap 0.
UNDER_HEAD_INNER_NORMAL_AIR_MIN = (
    FLOOR_HOLE_MOUTH_CHAMFER_MIN - MATING_SCREW_UNDER_HEAD_FILLET_MAX
) / math.sqrt(2.0)
UNDER_HEAD_OUTER_NORMAL_AIR_MIN = (
    MATING_SCREW_HEAD_EDGE_BREAK_MIN - POCKET_FLOOR_CORNER_R_MAX
) / math.sqrt(2.0)
UNDER_HEAD_INNER_SEATED_AXIAL_AIR_MIN = (
    MATING_SCREW_SEATED_GAP_MIN - MATING_SCREW_UNDER_HEAD_FILLET_MAX
)
UNDER_HEAD_OUTER_SEATED_AXIAL_AIR_MIN = (
    MATING_SCREW_SEATED_GAP_MIN - POCKET_FLOOR_CORNER_R_MAX
)
FLOOR_HOLE_STRAIGHT_LENGTH_MIN = round(
    FLOOR_THICKNESS_MIN - FLOOR_HOLE_MOUTH_CHAMFER_MAX, 6
)
FLOOR_ROOT_RADIAL_MIN = round(
    (BODY_DIA - BODY_DIA_TOL) / 2.0 - BODY_CHAMFER_MAX - FLOOR_HOLE_DIA_MAX / 2.0,
    6,
)
# Owner ruling B on #1375: 1/2-in cold-finished rod leaves a cleanup cut over
# the largest body.
STOCK_DIA = 0.5 * 25.4

for _ok, _what in (
    (FLOOR_THICKNESS_MIN >= WALL_FLOOR_MM, "cup floor is under 1.5 at .X"),
    (
        POCKET_WALL_MIN >= POCKET_WALL_FLOOR_MM,
        "pocket wall is under 1.5 at its limits (owner ruling B on #1375)",
    ),
    (FLOOR_HOLE_DIA < POCKET_DIA, "floor hole leaves no floor"),
    (
        0.0 < MATING_SCREW_SHOULDER_DIA_MIN < FLOOR_HOLE_DIA_MIN
        and MATING_SCREW_HEAD_DIA_MIN > FLOOR_HOLE_DIA_MAX
        and 0.0 < MATING_SCREW_UNDER_HEAD_FILLET_MAX,
        "invalid mating screw head, shoulder or inner-fillet requirements",
    ),
    (
        0.0
        < FLOOR_HOLE_MOUTH_CHAMFER_MIN
        <= FLOOR_HOLE_MOUTH_CHAMFER_MAX
        == FLOOR_HOLE_MOUTH_CHAMFER
        and FLOOR_HOLE_MOUTH_CHAMFER_BAND[0] == 0.0
        and FLOOR_HOLE_MOUTH_CHAMFER_BAND[1] < 0.0
        and FLOOR_HOLE_MOUTH_CHAMFER_TOL_TYPE == 3,
        "invalid native floor-hole mouth chamfer limits",
    ),
    (
        0.0
        < MATING_SCREW_HEAD_EDGE_BREAK_MIN
        <= MATING_SCREW_HEAD_EDGE_BREAK_MAX
        < MATING_SCREW_HEAD_DIA_MIN / 2.0,
        "invalid mating screw outer chamfer requirements",
    ),
    (
        UNDER_HEAD_INNER_NORMAL_AIR_MIN > 0.0,
        "inner corner has no positive zero-gap air",
    ),
    (
        UNDER_HEAD_OUTER_NORMAL_AIR_MIN > 0.0,
        "outer corner has no positive zero-gap air",
    ),
    (
        UNDER_HEAD_INNER_SEATED_AXIAL_AIR_MIN > 0.0
        and UNDER_HEAD_OUTER_SEATED_AXIAL_AIR_MIN > 0.0,
        "seated gap does not clear both complete corner envelopes",
    ),
    (
        0.0 <= HEAD_RUNNING_OFFSET_MAX <= POCKET_CLEARANCE[1] / 2.0,
        "invalid physically available eccentric float",
    ),
    (
        HEAD_BEARING_RADIAL_MIN >= MATING_SCREW_HEAD_BEARING_FLOOR > 0.0,
        "under 0.1 of flat bearing annulus (not a strength proof)",
    ),
    (FLOOR_HOLE_STRAIGHT_LENGTH_MIN > 0.0, "mouth chamfer consumes the floor hole"),
    (FLOOR_ROOT_RADIAL_MIN >= WALL_FLOOR_MM, "bottom chamfer consumes the floor root"),
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
        "FloorHoleMouthChamfer",
        "PocketFloorRadius",
    },
}
# Decimal places are the tolerance (drawing-guidelines.md rule 3 (decimal places carry the tolerance)): the body diameter and the
# pocket depth print their bands at two places; every other size is routine
# (.X).
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "CupProfile": {
        "BodyDia": 2,
        "OverallLength": 1,
        "PocketDepth": 2,
        "BodyChamfer": 1,
        "FloorHoleMouthChamfer": 2,
        "PocketDia": 1,
        "FloorHoleDia": 1,
        "PocketFloorRadius": 1,
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
