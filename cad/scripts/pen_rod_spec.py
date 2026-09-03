r"""Pure-data dimensional contract shared by the pen rod and drawing."""

from __future__ import annotations

from _gtol_spec import GeometricControl, PartDatum, PlanarFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl


ROD_SECTION = 5.0  # DIMENSIONS.md ch24: square section (low)
ROD_LENGTH = 150.0  # ch30 p002 / v4_t00603: the rod runs from the hanger guide
# down to the v-block at paper mid-height (was 120 with the block grounded)
SECTION_BAND = (0.00, -0.05)
WIRE_HOLE_Y = 145.0  # wire tie-off near the top (build_pen_assembly imports this)
WIRE_HOLE_DRILL = "#47"  # number drill (see _holes.NUMBER_DRILL_MM)
WIRE_HOLE_DIA = 1.994

# No geometric controls: the rod is a length of drawn square bar whose slide
# fit is the band on the model section (cad/docs/drawing-simplicity-policy.md
# rule 3). The typed tuples stay so build_pen_rod's author_part_pmi call shape
# is unchanged.
PART_DATUMS: tuple[PartDatum, ...] = ()
GEOMETRIC_CONTROLS: tuple[GeometricControl, ...] = ()
# The -X slide face is the one running surface: the rod slides in the v-block
# guide (rule 5).
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "slide_face", MACHINED_UM, PlanarFace((-1, 0, 0), ROD_SECTION / 2.0)
    ),
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RodProfile": {"Section", "Length"},
    "Rod": {"Depth"},
}

# Notes: part-specific process facts only, never a tolerance, never the
# title block (drawing-simplicity-policy.md rule 6). The #47 drill rides the
# wire-hole callout itself.
DRAWING_NOTES = "5 SQ DRAWN BRASS BAR FACES OK AS RECEIVED."
TOP_VIEW_NOTE = "TOP VIEW SCALE 4:1"
