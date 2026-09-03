r"""Reproduction script: column clamp, FRONT semi-arc (book ch. 21/22, ch30).

The bar-side half of the two-piece black collar clamping the platen support
bar to each front column (ch30 p005 quarter view): its front face carries the
bar's back face, its relief wraps the column's front half, and the two O4.4
ear holes pass the clamp screws whose heads show on the bar front (ch30
p002). Depth 17.9 spans bar back (machine z -129.9) to the column-axis plane
(z -112). Geometry: _clamp_arc.py; layout: memory/paper-drive-rework.md E2.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_column_clamp_front.py
"""

from __future__ import annotations

import sys

from _clamp_arc import build_arc
from _common import run_build, save_part_and_images
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
)
from _fit_limits import deviations
from _holes import HoleSpec
from column_clamp_front_spec import (
    ARC_DEPTH,
    COLUMN_BORE_BAND,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    ISOMETRIC_VIEW_NOTE,
)

PART_NAME = "column-clamp-front"

DEPTH = ARC_DEPTH  # bar back face to the column-axis plane
# The O3.9 clamp-screw shanks PASS THROUGH here (front arc = bar side):
# #8 clearance (normal fit Ø4.978; nearest UNC to the ~Ø4 screw).
HOLE_SPEC = HoleSpec("clearance", "#8")


async def build(adapter) -> dict[str, str]:
    await build_arc(
        adapter, part_name=PART_NAME, depth=DEPTH, front=True, hole_spec=HOLE_SPEC
    )
    # Manufacturing drawing support, applied AFTER the shared builder's gated
    # save (the marks and the relief band live only in this front arc, so the
    # shared _clamp_arc stays untouched and the back arc's recipe digest never
    # moves): band the slip-fit relief on its model dimension, mark exactly
    # the print's dimensions, stamp the make-critical title-block properties,
    # then re-save so the shipped SLDPRT carries all of it.
    set_dimension_bilateral_tolerance(
        adapter, "BoreProfile", "BoreDia", *deviations(COLUMN_BORE_BAND)
    )
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
