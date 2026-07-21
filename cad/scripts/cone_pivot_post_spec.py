r"""Pure-data dimensional contract shared by the cone pivot post and drawing."""

from __future__ import annotations


MM_PER_IN = 25.4

# Round green casting standing on the swing platform: the cone shaft's big-end
# journal bore (along Z at BORE_HEIGHT) and the crank pedestal's oblique crank
# bore (at CRANK_BORE_HEIGHT, tipped INCLINE_DEG off vertical, offset east). See
# build_cone_pivot_post.py for the derivation; this module is only the drawing's
# single source of the marked dimensions.
BLOCK_DIA = 24.0  # round column outside diameter
BLOCK_HEIGHT = 100.5  # column height, foot (platform seat) to top
BORE_DIA = 9.550  # 9.545..9.555 finished bore over shaft max 9.525
BORE_HEIGHT = 47.65  # journal-bore axis above the foot
CRANK_SHAFT_MAX_DIA = 9.525
CRANK_BORE_DIA = CRANK_SHAFT_MAX_DIA + 0.5  # 10.025: 0.25 radial clearance
CRANK_BORE_HEIGHT = 85.835  # crank-bore axis above the foot
CRANK_BORE_OFFSET = 0.95  # crank-bore axis east of the column axis
INCLINE_DEG = 12.5182  # crank bore tips this far off the column's vertical axis

# The oblique, offset crank bore is a running-clearance feature on a cast column
# and is fully specified by basic height, angle, and normal offset plus a native
# position control.  The angled bore projects as an ellipse in every square
# view, so the basic geometry is stated next to the view instead of pretending
# an ellipse edge is a linear dimension endpoint.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BlockProfile": {"BlockDia"},
    "Block": {"BlockHt"},
    "BoreProfile": {"BoreDia", "BoreZ"},
}

DRAWING_NOTES = "\n".join(
    (
        "MACHINE FROM CONTINUOUS-CAST ROUND STOCK; REMOVE AS-CAST SKIN.",
        "DATUM A IS FOOT SEAT; B IS COLUMN OD; C IS JOURNAL-BORE AXIS.",
        "JOURNAL BORE LIMITS DIA 9.545-9.555; FINISH RA 1.6;",
        "AXIS BASICALLY INTERSECTS DATUM AXIS B AT BOXED 47.65 ABOVE A.",
        "MATING SHAFT LIMITS DIA 9.505-9.525.",
        "CRANK BORE DIA 10.025 +/-0.025 THRU; AXIS BASIC 85.835 ABOVE A.",
        "BASIC ACUTE ANGLE TO DATUM AXIS C IS 12.52 DEG.",
        "IN UPPER PLAN VIEW CRANK AXIS SLOPES DOWN-LEFT; ITS BASIC",
        "SHORTEST DISTANCE FROM B IS 0.950 TOWARD SHEET RIGHT/DOWN.",
        "JOURNAL IS LOWER CIRCLE; CRANK BORE IS UPPER ELLIPSE IN FRONT VIEW.",
        "PLAN CENTER MARKS DEFINE B; BORE CENTERLINES DEFINE AXIS DIRECTIONS.",
    )
)
