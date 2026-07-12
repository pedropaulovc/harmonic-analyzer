r"""Pure-data dimensional contract shared by the top crossbar and drawing."""

from __future__ import annotations


BAR_HALF_X = 11.0
BAR_HEIGHT = 41.0
BAR_HALF_Z = 101.0

BAR_WIDTH = 2.0 * BAR_HALF_X
BAR_LENGTH = 2.0 * BAR_HALF_Z

STUD_HOLE_SIZE = "5/16"
STUD_HOLE_FIT = "close"
STUD_HOLE_DIA = 8.331

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BarProfile": {"Width", "Height"},
    "Bar": {"Depth"},
}
