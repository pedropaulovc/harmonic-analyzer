r"""Pure-data dimensional contract shared by the pen rod and drawing."""

from __future__ import annotations

from _gtol_spec import GeometricControl, PartDatum
from _surface_finish import SurfaceFinishControl


ROD_SECTION = 5.0  # DIMENSIONS.md ch24: square section (low)
ROD_LENGTH = 150.0  # ch30 p002 / v4_t00603: the rod runs from the hanger guide
# down to the v-block at paper mid-height (was 120 with the block grounded)
WIRE_HOLE_Y = 145.0  # wire tie-off near the top (build_pen_assembly imports this)
WIRE_HOLE_DRILL = "#47"  # number drill (see _holes.NUMBER_DRILL_MM)
WIRE_HOLE_DIA = 1.994

# No geometric controls: the rod is a length of drawn square bar whose faces
# are accepted as received. The empty typed tuples keep build_pen_rod's
# author_part_pmi call shape unchanged.
PART_DATUMS: tuple[PartDatum, ...] = ()
GEOMETRIC_CONTROLS: tuple[GeometricControl, ...] = ()
# No roughness callouts either (machinist review 2026-09-02): the rod slides
# in the v-block on its drawn-bar faces, which the note passes as received --
# an Ra 1.6 on one of them contradicted that licence, and the block's Ra 3.2
# covers a drawn brass face anyway (rule 5).
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = ()

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RodProfile": {"Length"},
}

# Notes: part-specific process facts only, never a tolerance, never the
# title block (drawing-simplicity-policy.md rule 6). The #47 drill rides the
# wire-hole callout itself.
DRAWING_NOTES = "5 SQ DRAWN BRASS BAR FACES OK AS RECEIVED."
TOP_VIEW_NOTE = "TOP VIEW SCALE 4:1"
