r"""Pure-data dimensional contract shared by the top crossbar and drawing."""

from __future__ import annotations

from cone_pivot_post_installation import (
    FRAME_COLUMN_Z_CENTER,
    FRAME_FRONT_COLUMN_Z,
    FRAME_REAR_COLUMN_Z,
    SUMMING_Z,
)


BAR_HALF_X = 11.0
BAR_HEIGHT = 41.0
RAIL_WIDTH = 22.0
BAR_FRONT_Z = FRAME_FRONT_COLUMN_Z + RAIL_WIDTH / 2.0
BAR_REAR_Z = FRAME_REAR_COLUMN_Z - RAIL_WIDTH / 2.0
BAR_CENTER_Z = FRAME_COLUMN_Z_CENTER
BAR_HALF_Z = (BAR_REAR_Z - BAR_FRONT_Z) / 2.0
STUD_HOLE_Z = SUMMING_Z - BAR_CENTER_Z

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
        "1. GRAY-IRON CASTING; AS-CAST SURFACES +/-0.8.",
        "2. MAY BE MACHINED FROM SOLID ASTM A48 CLASS 30 BAR; "
        "NO DRAFT MODELLED.",
        "3. STUD HOLE FOR 5/16 STUD, CLOSE FIT.",
    )
)
TOP_VIEW_NOTE = "TOP VIEW SCALE 1:2"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
