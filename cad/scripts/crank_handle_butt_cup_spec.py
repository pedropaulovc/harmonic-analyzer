r"""Pure-data contract for MHA-153, the crank handle's steel butt cup.

User ruling 2026-09-29 (ch11 p.14 and p.15 photographs): the butt of the
ebonized handle carries a bright steel cup, and the slotted head of the pivot
screw MHA-139 sits recessed inside it with a visible ring of clearance.  The
cup is a flanged ferrule: the flange covers the oak's end grain at the butt,
the body is epoxied into a counterbore in the oak, and the screw head bears on
the cup's floor, steel on steel, instead of on end-grain wood.

Local frame: the axis is local +X and the origin plane is the flange's outer
face; the flange, body and floor run toward -X (into the handle).  In the
handle's frame the flange face sits at the handle's basic overall length, so
the drive train places the cup with the handle's own transform.

PURE DATA, no SolidWorks/COM imports.
"""

from __future__ import annotations

# The flange matches the oak's diameter at the butt trim face (the handle
# spec asserts it); it is a free outer surface.
FLANGE_DIA = 10.8
# The flange and the pocket depth are the two cup terms of the handle's
# end-play stack (crank_handle_pivot_screw_spec): +/- on each.
FLANGE_THICKNESS = 0.80
FLANGE_THICKNESS_TOL = 0.05
# The body slips into the oak counterbore for an epoxy line.
BODY_DIA = 9.40
BODY_DIA_TOL = 0.02
# Overall length from the flange face to the floor's underside.  Banded so the
# body never bottoms in the oak counterbore before the flange seats.
OVERALL_LENGTH = 4.60
OVERALL_LENGTH_TOL = 0.10
# The pocket takes MHA-139's slotted head with a visible ring of clearance
# (the photographs).  (upper, lower) deviations.
POCKET_DIA = 8.2
POCKET_DIA_BAND = (0.10, 0.0)
POCKET_DEPTH = 3.60
POCKET_DEPTH_TOL = 0.05
# The floor hole passes MHA-139's shoulder.  It is a drilled hole under the
# title block's DRILLED HOLES band (+0.10/0).
FLOOR_HOLE_DIA = 6.2

FLOOR_THICKNESS = OVERALL_LENGTH - POCKET_DEPTH
BODY_LENGTH = OVERALL_LENGTH - FLANGE_THICKNESS
POCKET_WALL = (BODY_DIA - POCKET_DIA) / 2.0

for _ok, _what in (
    (FLANGE_DIA > BODY_DIA, "flange does not overhang the body"),
    (POCKET_DIA < BODY_DIA, "pocket breaks through the body"),
    (POCKET_WALL >= 0.5, "pocket wall is under 0.5"),
    (FLOOR_THICKNESS >= 0.8, "cup floor is under 0.8"),
    (FLOOR_HOLE_DIA < POCKET_DIA, "floor hole leaves no floor"),
    (POCKET_DEPTH > FLANGE_THICKNESS, "pocket does not reach past the flange"),
):
    if not _ok:
        raise AssertionError(f"MHA-153: {_what}")

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "CupProfile": {
        "FlangeDia",
        "FlangeThickness",
        "BodyDia",
        "OverallLength",
        "PocketDia",
        "PocketDepth",
        "FloorHoleDia",
    },
}
# Decimal places are the tolerance (policy rule 2): the stack and fit sizes
# print their bands at two places; the flange OD, the pocket and the drilled
# floor hole are one-place sizes (the pocket carries its own +0.10/0 band).
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "CupProfile": {
        "FlangeDia": 1,
        "FlangeThickness": 2,
        "BodyDia": 2,
        "OverallLength": 2,
        "PocketDia": 1,
        "PocketDepth": 2,
        "FloorHoleDia": 1,
    },
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked MHA-153 dimension needs authored places")

# The mating part, quoted only to identify it (rule 6); the offline test checks
# it against the registry.
HANDLE_NUMBER = "MHA-022"
DRAWING_NOTES = f"EPOXY IN THE {HANDLE_NUMBER} BUTT COUNTERBORE, FLANGE SEATED."
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 4:1"
