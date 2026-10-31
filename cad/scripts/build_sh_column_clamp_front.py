r"""Reproduction script: column clamp, FRONT semi-arc (book ch. 21/22, ch30).

The bar-side half of the two-piece black collar clamping the platen support
bar to each front column (ch30 p005 quarter view): its front face carries the
bar's back face, its relief wraps the column's front half, and the two Ø.196
ear holes pass the clamp screws whose heads show on the bar front (ch30
p002). Depth .685 spans the bar back face to the column-axis plane. Geometry:
_clamp_arc.py; layout: memory/paper-drive-rework.md E2.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_sh_column_clamp_front.py
"""

from __future__ import annotations

import sys

from _clamp_arc import EAR_HEIGHT_DIMENSION, EAR_HEIGHT_REFERENCE, build_arc
from _part_save import save_part_and_images
from _session import run_build
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import apply_drawing_precision
from _drawing_tolerances import set_dimension_symmetric_tolerance
from _column_clamp_interface import ARC_DEPTH
from sh_column_clamp_front_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    EAR_HOLE_SPEC,
    EAR_HEIGHT_BAND,
    EAR_STATION_BAND,
    EAR_STATION_DIMENSIONS,
    ISOMETRIC_VIEW_NOTE,
    UNIT,
)

PART_NAME = "sh-column-clamp-front"

DEPTH = ARC_DEPTH  # bar back face to the column-axis plane
# The Ø.164 clamp-screw shanks PASS THROUGH here (front arc = bar side):
# #8 clearance (normal fit Ø.196; nearest UNC to the ~Ø4 screw).


async def build(adapter) -> dict[str, str]:
    await build_arc(
        adapter,
        part_name=PART_NAME,
        depth=DEPTH,
        front=True,
        hole_spec=EAR_HOLE_SPEC,
    )
    # Manufacturing drawing support, applied to the unsaved model the shared
    # builder leaves behind and saved ONCE below (as build_sh_column_clamp_back
    # does): the ear stations' and the ears' height bands (sh_column_clamp_fit)
    # and every printed dimension's places live on the model, then mark exactly
    # the print's dimensions and stamp the make-critical title-block properties.
    for dimension_name in EAR_STATION_DIMENSIONS:
        set_dimension_symmetric_tolerance(
            adapter, "EarHoles", dimension_name, EAR_STATION_BAND, display_unit=UNIT
        )
    set_dimension_symmetric_tolerance(
        adapter,
        EAR_HEIGHT_REFERENCE,
        EAR_HEIGHT_DIMENSION,
        EAR_HEIGHT_BAND,
        display_unit=UNIT,
    )
    apply_drawing_precision(adapter, DRAWING_PRECISION)
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
