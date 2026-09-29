r"""Pure-data contract for MHA-153, the crank handle's steel butt cup.

User ruling 2026-09-29 (ch11 p.14 and p.15 photographs): the butt of the
ebonized handle carries a bright steel cup, and the slotted head of the pivot
screw MHA-139 sits recessed inside it with a visible ring of clearance.  The
cup is a flanged ferrule: the flange covers the oak's end grain at the butt,
the body is epoxied into a counterbore in the oak, and the screw head bears on
the cup's floor, steel on steel, instead of on end-grain wood.

After the MHA-153 machinist review (user rulings 2026-09-29): every section
holds 1.5 mm at its worst case, which grew the handle's butt; the pocket is
bored to suit the MHA-139 head; and the handle's end play is fitted on the
screw shoulder at assembly, so no length here is a stack term and all but the
body diameter are routine (.X) sizes.  The body diameter keeps a +/-0.10 band
because it sets the pocket wall.

Local frame: the axis is local +X and the origin plane is the flange's outer
face; the flange, body and floor run toward -X (into the handle).  In the
handle's frame the flange face sits at the handle's basic overall length, so
the drive train places the cup with the handle's own orientation.

PURE DATA, no SolidWorks/COM imports.
"""

from __future__ import annotations

# The flange matches the oak's diameter at the butt trim face (the handle
# spec asserts it); it is a free outer surface.
FLANGE_DIA = 13.5
FLANGE_THICKNESS = 2.3
# Holds the pocket wall at 1.5 (the screw spec asserts it against the bored
# pocket's largest size).
BODY_DIA = 11.6
BODY_DIA_TOL = 0.10
OVERALL_LENGTH = 7.3
FLOOR_THICKNESS = 2.3
# Bored to suit the MHA-139 head (reference size); POCKET_CLEARANCE is the
# diametral clearance the callout asks for.
POCKET_DIA = 8.3
POCKET_CLEARANCE = (0.2, 0.4)
# The floor hole passes the MHA-139 shoulder: a drilled hole under the title
# block's DRILLED HOLES band (+0.10/0).
FLOOR_HOLE_DIA = 6.2

POCKET_DEPTH = OVERALL_LENGTH - FLOOR_THICKNESS
BODY_LENGTH = OVERALL_LENGTH - FLANGE_THICKNESS

GENERAL_1PL_MM = 0.8
WALL_FLOOR_MM = 1.5
BODY_LENGTH_MAX = (OVERALL_LENGTH + GENERAL_1PL_MM) - (FLANGE_THICKNESS - GENERAL_1PL_MM)

for _ok, _what in (
    (FLANGE_DIA > BODY_DIA + BODY_DIA_TOL, "flange does not overhang the body"),
    (
        round(FLANGE_THICKNESS - GENERAL_1PL_MM, 6) >= WALL_FLOOR_MM,
        "flange is under 1.5 at .X",
    ),
    (
        round(FLOOR_THICKNESS - GENERAL_1PL_MM, 6) >= WALL_FLOOR_MM,
        "cup floor is under 1.5 at .X",
    ),
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
        "FloorThickness",
        "PocketDia",
        "FloorHoleDia",
    },
}
# Decimal places are the tolerance (policy rule 2): the body diameter prints
# its band at two places; every other size is routine (.X).
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "CupProfile": {
        "FlangeDia": 1,
        "FlangeThickness": 1,
        "BodyDia": 2,
        "OverallLength": 1,
        "FloorThickness": 1,
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
    raise AssertionError("every marked MHA-153 dimension needs authored places")
REFERENCE_DIMENSIONS = frozenset({"PocketDia"})

# The mating parts, quoted only to identify them (rule 6); the offline test
# checks them against the registry.
HANDLE_NUMBER = "MHA-022"
HANDLE_NAME = "CRANK HANDLE"
SCREW_NUMBER = "MHA-139"
SCREW_NAME = "CRANK HANDLE PIVOT SCREW"
FLOOR_HOLE_CALLOUT = "DRILL THRU"
DRAWING_NOTES = "\n".join(
    (
        f"BORE THE POCKET TO SUIT THE {SCREW_NUMBER} {SCREW_NAME} HEAD FOR",
        f"  {POCKET_CLEARANCE[0]:.1f}-{POCKET_CLEARANCE[1]:.1f} DIAMETRAL CLEARANCE;"
        " THE HEAD BEARS ON THE FLOOR.",
        f"THE <MOD-DIAM>{BODY_DIA:.2f} BAND HOLDS THE 1.5 POCKET WALL.",
        f"EPOXY IN THE {HANDLE_NUMBER} {HANDLE_NAME} BUTT COUNTERBORE, FLANGE SEATED.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 4:1"
