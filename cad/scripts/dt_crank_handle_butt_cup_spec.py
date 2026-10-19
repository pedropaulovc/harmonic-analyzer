r"""Pure-data contract for MHA-DT-035, the crank handle's steel butt cup.

User ruling 2026-09-29 (ch11 p.14 and p.15 photographs): the butt of the
ebonized handle carries a bright steel cup, and the slotted head of the pivot
screw MHA-DT-032 sits recessed inside it with a visible ring of clearance.  The
body is epoxied into a counterbore in the oak, and the screw head bears on
the cup's floor, steel on steel, instead of on end-grain wood.

User rulings 2026-09-30 (ch30 eight-views-4 side view, approved CadQuery
concept v4): the cup is a plain cup, no flange, seated flush with the oak's
end; after the epoxy cures the handle's end round is turned on the oak, clear of the
cup, whose face stays flat (local review of fbf82ad96).  Formerly: turned across the oak and
the cup together, so wood and steel read as one rounded butt.  The smaller
MHA-DT-032 head (Ø6) lets the cup shrink to the photographed size, and the pocket
wall is thin -- 0.8 at its worst case, under the 1.5 floor; the sheet states
it and the owner ruling is pending (#1375): the wall carries no load (the head
bears on the floor, and the oak round the bonded body backs it), and a 1.5
wall would push the butt to Ø13.4 against the photograph's ~Ø10.

The pocket is bored to suit the MHA-DT-032 head; the handle's end play is fitted
on the screw shoulder at assembly, so no length here is a stack term.  The
body diameter keeps a +/-0.10 band because it sets the pocket wall and the
MHA-DT-008 counterbore bored to suit it (that handle's butt wall); the pocket
depth keeps one because it sets how far the head sits below the face (Codex P2
on #1139, user ruling 2026-09-30).

Local frame: the axis is local +X and the origin plane is the cup's outer
face; the body and floor run toward -X (into the handle).  In the handle's
frame the face sits at the handle's basic overall length, so the drive train
places the cup with the handle's own orientation.

PURE DATA, no SolidWorks/COM imports.
"""

from __future__ import annotations

BODY_DIA = 8.2
BODY_DIA_TOL = 0.10
# Every axial size reads from the outer face, the one faced end (MHA-DT-035
# re-review): overall and pocket depth.  The floor is what remains, so the
# overall carries enough that its .X worst case, over the deepest banded
# pocket, still leaves 1.5.
OVERALL_LENGTH = 8.1
# Deep enough that the longest banded MHA-DT-032 head, at the widest fitted end
# play, still sits below the face (Codex P2 on #1139: at 5.0 .X against a 4.0
# .X head it could stand 1.6 proud).  User ruling 2026-09-30.
POCKET_DEPTH = 5.5
POCKET_DEPTH_TOL = 0.10
# Bored to suit the MHA-DT-032 head (reference size); POCKET_CLEARANCE is the
# diametral clearance the note asks for, and POCKET_DIA_MAX its hard limit
# (the largest head plus the widest clearance).
POCKET_DIA = 6.3
POCKET_CLEARANCE = (0.2, 0.4)
POCKET_DIA_MAX = 6.5
# The head bears on the floor: the floor-to-wall corner may round no more than
# the tightest radial clearance, so a sharp-edged, centred head still seats on
# the flat (rule 16: the largest radius acceptable; MHA-DT-035 r1 finding 5).
POCKET_FLOOR_CORNER_R_MAX = POCKET_CLEARANCE[0] / 2.0
# The floor hole passes the MHA-DT-032 shoulder: a drilled hole under the title
# block's DRILLED HOLES band (+0.10/0).
FLOOR_HOLE_DIA = 4.2

FLOOR_THICKNESS = OVERALL_LENGTH - POCKET_DEPTH

GENERAL_1PL_MM = 0.8
WALL_FLOOR_MM = 1.5
# The pocket wall falls short of the 1.5 floor; the sheet states it (rule 20)
# pending the owner's ruling (#1375).  The floor still holds 1.5.
POCKET_WALL_FLOOR_MM = 0.8
FLOOR_THICKNESS_MIN = round(FLOOR_THICKNESS - GENERAL_1PL_MM - POCKET_DEPTH_TOL, 6)
POCKET_WALL_MIN = round(((BODY_DIA - BODY_DIA_TOL) - POCKET_DIA_MAX) / 2.0, 6)
# Turned from 3/8-in cold-finished rod: the largest body plus a cleanup cut.
STOCK_DIA = 0.375 * 25.4

for _ok, _what in (
    (FLOOR_THICKNESS_MIN >= WALL_FLOOR_MM, "cup floor is under 1.5 at .X"),
    (
        POCKET_WALL_MIN >= POCKET_WALL_FLOOR_MM,
        "pocket wall is under the 0.8 baseline pending ruling #1375 at its limits",
    ),
    (FLOOR_HOLE_DIA < POCKET_DIA, "floor hole leaves no floor"),
    (BODY_DIA + BODY_DIA_TOL < STOCK_DIA - 0.2, "body is not turnable from 3/8-in rod"),
):
    if not _ok:
        raise AssertionError(f"MHA-DT-035: {_what}")

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "CupProfile": {
        "BodyDia",
        "OverallLength",
        "PocketDepth",
        "PocketDia",
        "FloorHoleDia",
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
        "PocketDia": 1,
        "FloorHoleDia": 1,
    },
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked MHA-DT-035 dimension needs authored places")
REFERENCE_DIMENSIONS = frozenset({"PocketDia"})
