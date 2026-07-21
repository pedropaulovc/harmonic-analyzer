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
BORE_DIA = 0.375 * MM_PER_IN  # 9.525: cone shaft big-end journal
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
        "CAST, THEN MACHINE THE BORES,",
        "THE FOOT SEAT AND THE OD.",
        "BORE HEIGHTS ARE AXIS-TO-FOOT (PLATFORM SEAT FACE = DATUM A).",
        "JOURNAL BORE DIA 9.525: REAM STRAIGHT TO A CLOSE RUNNING",
        "FIT ON THE CONE SHAFT, 0.02-0.05 DIAMETRAL CLEARANCE.",
        "CRANK BORE DIA 10.025 THRU: AXIS 85.835 ABOVE THE FOOT,",
        "IN THE FRONT-VIEW PLANE, TIPPED 12.52 DEG FROM THE COLUMN",
        "AXIS AND OFFSET 0.95 TOWARD VIEW-RIGHT -- A CAST RUNNING",
        "CLEARANCE (0.25/SIDE, INTENTIONAL) OVER THE DIA 9.525 CRANKSHAFT.",
    )
)
