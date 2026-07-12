r"""Pure-data dimensional contract shared by the top crossbar and drawing."""

from __future__ import annotations


BAR_HALF_X = 11.0
BAR_HEIGHT = 41.0
BAR_HALF_Z = 101.0

BAR_WIDTH = 2.0 * BAR_HALF_X
BAR_LENGTH = 2.0 * BAR_HALF_Z

STUD_HOLE_SIZE = "5/16"
STUD_HOLE_FIT = "close"
STUD_HOLE_DRILL = "21/64"
STUD_HOLE_DIA = 8.33

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BarProfile": {"Width", "Height"},
    "Bar": {"Depth"},
}

DRAWING_NOTES = "\n".join(
    (
        "UNLESS OTHERWISE SPECIFIED:",
        "1. GRAY-IRON CASTING: AS-CAST +/-0.8; MACHINED +/-0.25. "
        "REMOVE BURRS; BREAK SHARP EDGES 0.3 MAX.",
        "2. MAY BE MACHINED FROM SOLID ASTM A48 CLASS 30 BAR; "
        "NO DRAFT MODELLED.",
    )
)
HOLE_CALLOUT = (
    f"O{STUD_HOLE_DIA:.2f} ({STUD_HOLE_DRILL}) THRU; "
    f"FOR {STUD_HOLE_SIZE} STUD, {STUD_HOLE_FIT.upper()} FIT"
)
TOP_VIEW_NOTE = "TOP VIEW SCALE 1:2"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
