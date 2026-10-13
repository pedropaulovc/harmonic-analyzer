r"""Create the curated machinist drawing for the pen hanger.

The SLDPRT remains authoritative.  This recipe supplies only the hanger's views,
the placement of its imported model dimensions, the hanger-screw callout, and
the property-linked notes; sheet/template and export behavior lives in
``_drawing_common``.  Dimension import and curation live in
``_drawing_dimension_import``; places and bands are authored on the part.

The pen hanger is a black tapered steel strap (3 thick, 16 -> 10 wide, 170
tall) with two open U guide plates brazed across its front face; the pen rod
hangs in both slots.  The front view (1:1) carries the strap outline, the tap
station and the upper plate's drop and thickness; the top view (2:1) looks
down on the upper plate's U and carries its slot; the shaded isometric sits
right.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pn_pen_hanger.py pn-pen-hanger
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
from _holes import TAP_DRILL_MM
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from pn_pen_hanger_spec import (
    DIMENSION_CALLOUTS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    GUIDE_PLATE_T,
    GUIDE_PLATE_WIDTH,
    GUIDE_PLATE_YS,
    PLATE_FRONT_Z,
    SCREW_HOLE_XY,
    SCREW_TAP_SPEC,
    SLOT_BOTTOM_Z,
    STRAP_BOT_X,
    STRAP_BOT_Y,
    STRAP_TOP_X,
    STRAP_Z,
)


SPEC = DRAWINGS_BY_NAME["pn_pen_hanger"]
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

SHEET_SCALE = (1.0, 1.0)  # the 170-tall strap fits the sheet at full size
FRONT_SCALE = (1, 1)
TOP_SCALE = (2, 1)  # the slot's 0.05 band needs room
ISO_SCALE = (1, 2)

# Model extents (local mm) of the front (X-Y) and top (X-Z) silhouettes.
_X = (min(STRAP_TOP_X[0], STRAP_BOT_X[0]), max(STRAP_TOP_X[1], GUIDE_PLATE_WIDTH / 2.0))
_Y = (STRAP_BOT_Y, 0.0)
_Z = (PLATE_FRONT_Z, STRAP_Z[1])
_CX = (_X[0] + _X[1]) / 2.0
_CY = (_Y[0] + _Y[1]) / 2.0
_CZ = (_Z[0] + _Z[1]) / 2.0

# Sheet layout (meters).  The tall front view hugs the left margin (its
# stacked top dimensions under the border); the tap callout sits in the gap
# between it and the top view; the notes under the top view; the isometric to
# the right.
FRONT_CENTER = (0.075, 0.140)
TOP_CENTER = (0.205, 0.215)
ISO_CENTER = (0.330, 0.175)
NOTES_XY = (0.130, 0.140)
CALLOUT_XY = (0.118, 0.200)
TOP_NOTE_XY = (0.185, 0.262)


def _fx(model_x_mm: float) -> float:
    return (
        FRONT_CENTER[0] + (model_x_mm - _CX) * FRONT_SCALE[0] / FRONT_SCALE[1] / 1000.0
    )


def _fy(model_y_mm: float) -> float:
    return (
        FRONT_CENTER[1] + (model_y_mm - _CY) * FRONT_SCALE[0] / FRONT_SCALE[1] / 1000.0
    )


def _tx(model_x_mm: float) -> float:
    return TOP_CENTER[0] + (model_x_mm - _CX) * TOP_SCALE[0] / TOP_SCALE[1] / 1000.0


def _tz(model_z_mm: float) -> float:
    # Third-angle top view: the part's front (-Z) faces the sheet bottom.
    return TOP_CENTER[1] + (model_z_mm - _CZ) * TOP_SCALE[0] / TOP_SCALE[1] / 1000.0


_UPPER_TOP_Y = GUIDE_PLATE_YS[1] + GUIDE_PLATE_T

# Front view: the strap outline around the view, the tap station above it from
# the origin corner, the upper plate's drop/thickness to the right.
FRONT_KEEP = {
    "StrapTopRun": (_fx((STRAP_TOP_X[0] + STRAP_TOP_X[1]) / 2.0), _fy(0.0) + 0.010),
    "StrapTaperDx": (_fx((STRAP_TOP_X[0] + STRAP_BOT_X[0]) / 2.0), _fy(0.0) + 0.020),
    "ScrewX": (_fx(SCREW_HOLE_XY[0] / 2.0), _fy(0.0) + 0.030),
    "ScrewY": (_fx(_X[1]) + 0.008, _fy(SCREW_HOLE_XY[1] / 2.0)),
    "StrapRise": (_fx(_X[0]) - 0.012, _fy(_CY)),
    "UpperPlateDrop": (_fx(_X[1]) + 0.020, _fy(_UPPER_TOP_Y / 2.0)),
    "PlateThick": (_fx(_X[1]) + 0.008, _fy(_UPPER_TOP_Y - GUIDE_PLATE_T / 2.0)),
    "StrapBotWidth": (_fx(0.0), _fy(STRAP_BOT_Y) - 0.010),
}
# Top view: the U's widths below the plate, its depths to the right, the strap
# stock thickness left.
TOP_KEEP = {
    "SlotWidth": (_tx(0.0), _tz(PLATE_FRONT_Z) - 0.010),
    "PlateWidth": (_tx(0.0), _tz(PLATE_FRONT_Z) - 0.030),
    "ArmWidth": (_tx(_X[0]), _tz(PLATE_FRONT_Z) + 0.004),
    "PlateReach": (_tx(_X[1]) + 0.010, _tz((STRAP_Z[0] + PLATE_FRONT_Z) / 2.0)),
    "SlotBottom": (_tx(_X[1]) + 0.026, _tz(SLOT_BOTTOM_Z / 2.0)),
    "StrapThick": (_tx(_X[0]) - 0.010, _tz((STRAP_Z[0] + STRAP_Z[1]) / 2.0)),
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pen-hanger source", await adapter.open_model(str(SOURCE)))
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
            "Front View Note",
            "Top View Note",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Front View Note",
            "Top View Note",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pen Hanger Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pen hanger; tapered strap; two open U pen-rod guide plates",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=FRONT_SCALE)
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=TOP_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    # The iso too: a new view already reads Shaded With Edges, so
    # finalize_drawing's SetDisplayMode4 is a no-op that leaves its cosmetic
    # threads at draft quality (farm c0b95549c readback cosmetic_threads=False).
    # From HLR the shading call really changes the mode and takes precision.
    for view in (front, top, iso):
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
    ]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    # Places (and so each dimension's tolerance) are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the hanger-screw hole")

    # Pick the tap-drill rim, not the cosmetic thread or the hole centre.
    add_native_hole_callout(
        adapter,
        front,
        edge_xy=(
            _fx(SCREW_HOLE_XY[0] + TAP_DRILL_MM[SCREW_TAP_SPEC.size] / 2.0),
            _fy(SCREW_HOLE_XY[1]),
        ),
        callout_xy=CALLOUT_XY,
        label="hanger-screw through tap",
        process="TAP",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Front View Note", 0.030, 0.036)
    add_property_linked_note(adapter, "Top View Note", *TOP_NOTE_XY)
    add_property_linked_note(adapter, "Isometric View Note", 0.290, 0.104)

    # Materialize the iso's cosmetic thread before the strict final note cleanup;
    # otherwise its descriptive label first appears during the native drawing save.
    import_cosmetic_threads(adapter, iso)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pen Hanger Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        redundant_note_substrings=("#8-32 Tapped Hole",),
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
