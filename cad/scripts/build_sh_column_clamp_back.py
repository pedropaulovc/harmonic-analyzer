r"""Reproduction script: column clamp, BACK semi-arc (book ch. 21/22, ch30).

The rear half of the two-piece black collar clamping the platen support bar
to each front column (ch30 p005 quarter view): its relief wraps the column's
back half and its two #8-32 tapped ear holes take the clamp-screw threads (the
screw stack is bar -> front arc -> this shell). Depth .610 spans the
column-axis plane to the back face, a .106 back wall past the Ø1.008 bore;
the mating face stops .020 short of the column axis so the clamp grips
(user ruling 2026-10-14; sh_column_clamp_fit).
Geometry: _clamp_arc.py; layout: memory/paper-drive-rework.md E2.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_sh_column_clamp_back.py
"""

from __future__ import annotations

import sys

from _clamp_arc import EAR_HEIGHT_DIMENSION, EAR_HEIGHT_REFERENCE, build_arc
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import apply_drawing_precision
from _drawing_tolerances import set_dimension_symmetric_tolerance
from _part_save import save_part_and_images
from _session import run_build
from sh_column_clamp_back_spec import (
    DEPTH,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    EAR_HEIGHT_BAND,
    EAR_STATION_BAND,
    EAR_STATION_DIMENSIONS,
    GRIP_OFFSET,
    GRIP_OFFSET_BAND,
    HOLE_SPEC,
    ISOMETRIC_VIEW_NOTE,
    UNIT,
)

PART_NAME = "sh-column-clamp-back"


async def build(adapter) -> dict[str, str]:
    await build_arc(
        adapter,
        part_name=PART_NAME,
        depth=DEPTH,
        front=False,
        hole_spec=HOLE_SPEC,
        grip_offset=GRIP_OFFSET,
    )
    # Manufacturing drawing support, applied to the unsaved model the shared
    # builder leaves behind and saved ONCE below: the explicit bands (the grip
    # offset, the ear stations and the ears' height, sh_column_clamp_fit) and
    # every printed dimension's places live on the model, then mark exactly
    # the print's dimensions and stamp the make-critical title-block properties.
    set_dimension_symmetric_tolerance(
        adapter, "BlockProfile", "GripOffset", GRIP_OFFSET_BAND, display_unit=UNIT
    )
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
        adapter, PART_NAME, {"Isometric View Note": ISOMETRIC_VIEW_NOTE}
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
