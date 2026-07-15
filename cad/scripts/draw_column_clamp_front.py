r"""Create the curated machinist drawing for the column clamp, front arc.

The SLDPRT remains authoritative.  This recipe supplies only the front-arc
views, dimension layout, hole callouts, and manufacturing notes; every shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The sheet runs at 2:1 (the arc is 48 mm ear tip to ear tip); the isometric
carries an explicit 1:1 override so it stays clear of the title block.  Third
angle: the top view (the 17.9 x 48 plan carrying the column-relief arc) sits
above the front view; the right view (the 48 x 16 bar face carrying the two
ear holes) sits to its right.

Run with SolidWorks open::

    uv run python cad\scripts\draw_column_clamp_front.py column-clamp-front
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_datum_feature,
    add_edge_dimension,
    add_feature_control_frame,
    add_native_hole_callout,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_basic_dimension,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from column_clamp_front_spec import (
    ARC_DEPTH,
    ARC_HEIGHT,
    BORE_RADIUS,
    EAR_HOLE_DIA,
    EAR_HOLE_Z,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["column_clamp_front"]
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

SHEET_SCALE = (2.0, 1.0)

# Sheet layout (meters).  The model bbox runs 0..17.9 in X (depth), +/-8 in Y
# (height) and +/-24 in Z (width); at 2:1 the front view is 35.8 x 32 mm, the
# top view 35.8 x 96 mm, the right view 96 x 32 mm.
FRONT_CENTER = (0.105, 0.125)
TOP_CENTER = (0.105, 0.205)
RIGHT_CENTER = (0.250, 0.125)
ISO_CENTER = (0.355, 0.205)

_M = SHEET_SCALE[0] / 1000.0  # model mm -> sheet meters


def _plan_x(model_x_mm: float) -> float:
    """Sheet X of a model-X point in the front/top views (2:1, bbox-centred)."""
    return FRONT_CENTER[0] + (model_x_mm - ARC_DEPTH / 2.0) * _M


# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position.  All three live on the top view (their sketches lie on the part's
# Top plane): the depth chain above the view, the width chain to its left, the
# bore diameter leadered off the relief arc.
TOP_KEEP = {
    "Depth": (0.105, 0.261),
    "Width": (0.058, 0.205),
    "BoreDia": (0.158, 0.243),
}
FRONT_KEEP = {}
RIGHT_KEEP = {}
DIMENSION_CALLOUTS = {
    "BoreDia": "THRU\nSLIP FIT ON <MOD-DIAM>25.4 COLUMN",
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open column-clamp-front source", await adapter.open_model(str(SOURCE)))
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
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
    )
    drawing_model, sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Column Clamp Front Arc Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "column clamp; front arc; gray iron casting; manufacturing drawing",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(2, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    for view in (right, iso):
        set_hidden_lines_removed(adapter, view)
    # The front view shows the relief depth profile and the ear drills edge-on;
    # the top view carries the hidden ear-hole rectangles beside the open arc.
    for view in (front, top):
        set_hidden_lines_visible(adapter, view)

    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    right_annotations = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="right"
    )
    set_dimension_callouts(
        adapter,
        [*top_annotations, *front_annotations, *right_annotations],
        DIMENSION_CALLOUTS,
    )
    # The relief is a 25.6 single-decimal fit bore (the notes cite 25.6 on
    # 25.4); two decimals would read as false precision against the note.
    set_dimension_precision(
        adapter,
        [*top_annotations, *front_annotations, *right_annotations],
        {"BoreDia": 1},
    )

    # Collar height (16): dimension the front view's flat top/bottom faces.
    add_edge_dimension(
        adapter,
        front,
        p0=(FRONT_CENTER[0], FRONT_CENTER[1] - ARC_HEIGHT / 2.0 * _M),
        p1=(FRONT_CENTER[0], FRONT_CENTER[1] + ARC_HEIGHT / 2.0 * _M),
        text_xy=(FRONT_CENTER[0] - 0.033, FRONT_CENTER[1]),
        label="collar-height overall",
    )

    if not auto_center_marks(adapter, right, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the right view")

    # Ear-hole span (35 c-c), BASIC: the position FCF below carries the
    # tolerance.  Both ears show round in the right view.
    ear_top = EAR_HOLE_DIA / 2.0 * _M
    ear_spacing = add_edge_dimension(
        adapter,
        right,
        p0=(RIGHT_CENTER[0] - EAR_HOLE_Z * _M, RIGHT_CENTER[1] + ear_top),
        p1=(RIGHT_CENTER[0] + EAR_HOLE_Z * _M, RIGHT_CENTER[1] + ear_top),
        text_xy=(RIGHT_CENTER[0], RIGHT_CENTER[1] + 0.028),
        label="ear-hole spacing",
    )
    set_basic_dimension(adapter, ear_spacing, label="ear-hole spacing")

    # Native datum/GD&T/surface annotations.  Datum A is the bar-seat face
    # (the full-depth flat at x = 17.9 the support bar clamps against); datum
    # B is the column-relief bore.
    add_datum_feature(
        adapter,
        top,
        edge_xy=(_plan_x(ARC_DEPTH), TOP_CENTER[1] - 0.035),
        symbol_xy=(0.150, TOP_CENTER[1] - 0.035),
        datum="A",
        label="bar-seat face",
    )
    add_datum_feature(
        adapter,
        top,
        edge_xy=(_plan_x(BORE_RADIUS), TOP_CENTER[1]),
        symbol_xy=(0.150, TOP_CENTER[1]),
        datum="B",
        label="column-relief bore",
    )
    add_feature_control_frame(
        adapter,
        right,
        edge_xy=(
            RIGHT_CENTER[0] + EAR_HOLE_Z * _M,
            RIGHT_CENTER[1] - ear_top,
        ),
        frame_xy=(0.297, 0.108),
        characteristic="position",
        tolerance="0.25",
        datums=("A", "B"),
        diameter=True,
        quantity="2X",
        label="ear-hole position",
    )
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=(_plan_x(0.0), FRONT_CENTER[1]),
        frame_xy=(0.040, 0.096),
        characteristic="parallelism",
        tolerance="0.10",
        datums=("A",),
        label="mating-face parallelism",
    )
    bore_45 = BORE_RADIUS / 2.0**0.5
    add_surface_finish(
        adapter,
        top,
        edge_xy=(_plan_x(bore_45), TOP_CENTER[1] - bore_45 * _M),
        symbol_xy=(0.138, 0.162),
        roughness_ra="3.2",
        label="column-relief bore finish",
    )
    add_native_hole_callout(
        adapter,
        right,
        edge_xy=(
            RIGHT_CENTER[0] - EAR_HOLE_Z * _M,
            RIGHT_CENTER[1] - ear_top,
        ),
        callout_xy=(0.170, 0.093),
        label="ear holes",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.014, 0.060)
    add_property_linked_note(adapter, "Isometric View Note", 0.330, 0.168)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Column Clamp Front Arc Manufacturing Drawing",
        scale=SHEET_SCALE,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
