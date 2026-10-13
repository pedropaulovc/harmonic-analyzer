r"""Create the curated machinist drawing for the pen square rod.

The SLDPRT remains authoritative.  This recipe supplies only the rod's views,
the placement of its imported model dimensions, the stud-tap callout and the
property-linked notes; sheet/template and export behavior lives in
``_drawing_common``.  Places, bands and mate callouts are authored on the part
(``pn_pen_rod_spec``).

The front view (1:1) carries the square's width and length and the pivot
length; the top view (4:1) looks down on the tapped top face and carries the
square's depth and the native Hole Wizard callout of the #0-80 stud tap; the
bottom view (4:1) shows the turned pivot end-on inside the square and carries
its banded diameter; the shaded isometric sits right.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pn_pen_rod.py pn-pen-rod
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)

from _check import check
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions, import_cosmetic_threads
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_hole_callout import add_native_hole_callout
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from pn_pen_rod_spec import (
    DIMENSION_CALLOUTS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    PIVOT_LENGTH,
    ROD_SECTION,
    SQUARE_LENGTH,
    STUD_TAP_DRILL_DIA,
    STUD_TAP_SPEC,
)


SPEC = DRAWINGS_BY_NAME["pn_pen_rod"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

SHEET_SCALE = (1.0, 1.0)  # the 122.5-long rod fits the sheet at full size
FRONT_SCALE = (1, 1)
END_SCALE = (4, 1)  # the 5 mm square's ends: tap callout and pivot band need room
ISO_SCALE = (1, 1)

# Front-view model extents (local mm): the square's width in X, pivot end to
# top face in Y.  The top and bottom views are centred on the rod axis.
_CY = (SQUARE_LENGTH - PIVOT_LENGTH) / 2.0

# Sheet layout (meters).  The tall front view hugs the left margin; the two
# 4:1 end views stack to its right (top face above, pivot end below), each
# with its scale note under it; the isometric to the right.
FRONT_CENTER = (0.070, 0.150)
TOP_CENTER = (0.200, 0.215)
BOTTOM_CENTER = (0.200, 0.140)
ISO_CENTER = (0.340, 0.180)
NOTES_XY = (0.015, 0.058)
TOP_NOTE_XY = (0.180, 0.198)
BOTTOM_NOTE_XY = (0.180, 0.123)
TAP_CALLOUT_XY = (0.222, 0.248)


def _fx(model_x_mm: float) -> float:
    return FRONT_CENTER[0] + model_x_mm * FRONT_SCALE[0] / FRONT_SCALE[1] / 1000.0


def _fy(model_y_mm: float) -> float:
    return (
        FRONT_CENTER[1] + (model_y_mm - _CY) * FRONT_SCALE[0] / FRONT_SCALE[1] / 1000.0
    )


def _end_x(center: tuple[float, float], model_x_mm: float) -> float:
    return center[0] + model_x_mm * END_SCALE[0] / END_SCALE[1] / 1000.0


_HALF = ROD_SECTION / 2.0
_END_HALF_M = _HALF * END_SCALE[0] / END_SCALE[1] / 1000.0

# Front view: the length left of the square, the pivot length right of the
# pivot, the banded width (and its mate callout) above the top face, offset
# right so neither extension line runs through the toleranced text.
FRONT_KEEP = {
    "Length": (_fx(-_HALF) - 0.012, _fy(SQUARE_LENGTH / 2.0)),
    "PivotLength": (_fx(_HALF) + 0.012, _fy(-PIVOT_LENGTH / 2.0)),
    "Section": (_fx(0.0) + 0.040, _fy(SQUARE_LENGTH) + 0.010),
}
# Top view: the banded depth (and its mate callout) right of the square.
TOP_KEEP = {
    "Depth": (TOP_CENTER[0] + _END_HALF_M + 0.035, TOP_CENTER[1]),
}
# Bottom view: the pivot's banded diameter (and its mate callout) out to the
# right of the square.
BOTTOM_KEEP = {
    "PivotDia": (BOTTOM_CENTER[0] + _END_HALF_M + 0.035, BOTTOM_CENTER[1] + 0.008),
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pen-rod source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Top View Note",
            "Bottom View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Top View Note",
            "Bottom View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pen Rod Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pen rod; square brass slide rod; turned pivot end; tapped top",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=FRONT_SCALE)
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=END_SCALE)
    bottom = place_view(
        adapter, str(SOURCE), "*Bottom", *BOTTOM_CENTER, scale=END_SCALE
    )
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    # The iso too: a new view already reads Shaded With Edges, so
    # finalize_drawing's SetDisplayMode4 is a no-op that leaves its cosmetic
    # threads at draft quality (farm c0b95549c readback cosmetic_threads=False).
    # From HLR the shading call really changes the mode and takes precision.
    for view in (front, top, bottom, iso):
        set_hidden_lines_removed(adapter, view)

    annotations = [
        *curate_view_dimensions(
            adapter,
            front,
            keep=FRONT_KEEP,
            view_label="front",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            top,
            keep=TOP_KEEP,
            view_label="top",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            bottom,
            keep=BOTTOM_KEEP,
            view_label="bottom",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    # Places (and so each dimension's tolerance) are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    if not auto_center_marks(adapter, top, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the stud tap")

    # Pick the tap-drill rim, not the cosmetic thread or the hole centre.
    add_native_hole_callout(
        adapter,
        top,
        edge_xy=(_end_x(TOP_CENTER, STUD_TAP_DRILL_DIA / 2.0), TOP_CENTER[1]),
        callout_xy=TAP_CALLOUT_XY,
        label="adjuster stud blind tap",
        process="TAP",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Top View Note", *TOP_NOTE_XY)
    add_property_linked_note(adapter, "Bottom View Note", *BOTTOM_NOTE_XY)

    # Materialize the iso's cosmetic thread before the strict final note cleanup;
    # otherwise its descriptive label first appears during the native drawing save.
    import_cosmetic_threads(adapter, iso)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pen Rod Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        redundant_note_substrings=(f"{STUD_TAP_SPEC.size} Tapped Hole",),
        expected_redundant_notes=1,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
