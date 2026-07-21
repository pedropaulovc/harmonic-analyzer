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
CRANK_BORE_DIA = BORE_DIA + 0.5  # 10.025: running clearance over the crankshaft
CRANK_BORE_HEIGHT = 85.835  # crank-bore axis above the foot
CRANK_BORE_OFFSET = 0.95  # crank-bore axis east of the column axis
INCLINE_DEG = 12.5182  # crank bore tips this far off the column's vertical axis

# The oblique, offset crank bore is a running-clearance feature on a cast column
# and is fully specified by the general note (dia, height, tip, offset) rather
# than an orthographic dimension -- an angled bore projects as an ellipse in
# every square view, so a note is the honest, unambiguous callout.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BlockProfile": {"BlockDia"},
    "Block": {"BlockHt"},
    "BoreProfile": {"BoreDia", "BoreZ"},
}

DRAWING_NOTES = "\n".join(
    (
        "MACHINE ALL SURFACES SHOWN FROM CONTINUOUS-CAST ROUND STOCK.",
        "DATUM A IS THE FINISHED FOOT SEAT; DATUM B IS THE JOURNAL AXIS.",
        "JOURNAL BORE LIMITS DIA 9.545-9.555; AXIS HEIGHT 47.65 +/-0.05",
        "ABOVE A. MATING SHAFT LIMITS DIA 9.505-9.525.",
        "CRANK BORE DIA 10.025 +/-0.025 THRU; AXIS PARALLEL TO A",
        "WITHIN 0.10 AND 85.835 +/-0.05 ABOVE A.",
        "IN THE UPPER PLAN VIEW, CRANK AXIS IS 12.52 +/-0.10 DEG",
        "CLOCKWISE FROM B; SHORTEST PLAN DISTANCE BETWEEN AXES IS",
        "0.95 +/-0.05, WITH THE CRANK AXIS ON THE SIDE SHOWN.",
        "BREAK EDGES 0.25 MAX.",
    )
)
