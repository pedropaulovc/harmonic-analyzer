r"""Pure-data dimensional contract shared by the pen rod and drawing."""

from __future__ import annotations


ROD_SECTION = 5.0  # DIMENSIONS.md ch24: square section (low)
ROD_LENGTH = 120.0  # DIMENSIONS.md ch24: p.64 inset (low)
WIRE_HOLE_Y = 115.0  # wire tie-off near the top (build_pen_assembly imports this)
WIRE_HOLE_DRILL = "#47"  # number drill (see _holes.NUMBER_DRILL_MM)
WIRE_HOLE_DIA = 1.994

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RodProfile": {"Section", "Length"},
    "Rod": {"Depth"},
}

DRAWING_NOTES = "\n".join(
    (
        "UOS, DIMENSIONS IN MM: SECTION +/-0.05; LENGTHS +/-0.25. DEBURR; "
        "BREAK EDGES 0.15 MAX.",
        "USE DRAWN SQUARE BRASS BAR; KEEP FACES STRAIGHT AND SMOOTH - THE "
        "ROD SLIDES IN THE V-BLOCK GUIDE.",
        "DRILL WIRE HOLE #47 THRU; DEBURR BOTH FACES.",
    )
)
TOP_VIEW_NOTE = "TOP VIEW SCALE 4:1"
