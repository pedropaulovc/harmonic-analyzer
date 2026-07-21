r"""Create the curated machinist drawing for the summing lever.

The SLDPRT remains authoritative.  This recipe supplies only the summing-lever
views, dimension layout, hole callouts, and manufacturing notes; every shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

A large green cast-iron first-class lever hung on hex knife-edge trunnions (no
bore): a coefficients plate on the +X arm carrying the 20 channel-spring holes,
a solid pivot cylinder (152.4 long, along Z), and a summation arm reaching to
the counter-spring anchor eye on the -X arm.  The print shows a 1:2 front
profile (pivot Ø), a 1:2 top plan (plate width/length + anchor eye), and a 1:4
isometric.  The sheet runs at 1:2.

Run with SolidWorks open::

    uv run python cad\scripts\draw_summing_lever.py summing-lever
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
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from summing_lever_spec import (
    ANCHOR_BORE_R,
    ANCHOR_R,
    CHANNEL_PITCH,
    HEX_DEPTH,
    HOLE_DIA,
    HOLE_X,
    HOLE_Z_FIRST,
    PLATE_L,
    PLATE_W,
    TIP_X,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    place_view,
)


SPEC = DRAWINGS_BY_NAME["summing_lever"]
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

SHEET_SCALE = (1.0, 2.0)  # 1:2
_S = SHEET_SCALE[0] / SHEET_SCALE[1]  # sheet-mm per model-mm (0.5)

# Front (down -Z) and top (down -Y) share the same X extent: anchor eye
# (TIP_X - ANCHOR_R) on the left to the plate right edge (PLATE_W).
_BBOX_CX = (TIP_X - ANCHOR_R + PLATE_W) / 2.0

FRONT_CENTER = (0.155, 0.205)
TOP_CENTER = (0.155, 0.105)  # third-angle: plan below the front profile
ISO_CENTER = (0.335, 0.195)


def _front_xy(mx: float, my: float) -> tuple[float, float]:
    """Sheet (x, y) of a model (X, Y) point in the front profile view (1:2)."""
    return (
        FRONT_CENTER[0] + (mx - _BBOX_CX) * _S / 1000.0,
        FRONT_CENTER[1] + my * _S / 1000.0,
    )


def _top_xy(mx: float, mz: float) -> tuple[float, float]:
    """Sheet (x, y) of a model (X, Z) point in the top plan view (1:2)."""
    return (
        TOP_CENTER[0] + (mx - _BBOX_CX) * _S / 1000.0,
        TOP_CENTER[1] + mz * _S / 1000.0,
    )


FRONT_KEEP = {
    "CylDia": (0.075, 0.230),
}
TOP_KEEP = {
    "PlateWidth": (0.230, 0.135),
    "PlateLength": (0.245, TOP_CENTER[1]),
    "AnchorOuterDia": (0.055, 0.070),
}
RIGHT_KEEP: dict[str, tuple[float, float]] = {}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open summing-lever source", await adapter.open_model(str(SOURCE)))
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
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Summing Lever Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "summing lever; gray iron; knife-edge first-class lever",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 2))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(1, 2))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 4))
    for view in (top, iso):
        set_hidden_lines_removed(adapter, view)

    curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front")
    curate_view_dimensions(adapter, top, keep=TOP_KEEP, view_label="top")

    # Anchor bore (Ø3.0) native callout in the top plan.  Pick a point on the
    # bore rim (not its centre) so SolidWorks catches the circular edge.
    anchor_bore_edge = _top_xy(TIP_X, ANCHOR_BORE_R)
    add_native_hole_callout(
        adapter,
        top,
        edge_xy=anchor_bore_edge,
        callout_xy=(0.060, 0.125),
        label="anchor bore",
    )

    # Datum A is the actual knife-edge pivot ridge, not the merged cylinder
    # silhouette hidden by the ribs in the front view.  Use the -Z ridge for
    # the datum and the opposite +Z ridge for Ra so their leaders stay distinct.
    knife_edge_datum = _top_xy(0.0, -(PLATE_L / 2.0 + HEX_DEPTH / 2.0))
    add_datum_feature(
        adapter,
        top,
        edge_xy=knife_edge_datum,
        symbol_xy=(knife_edge_datum[0] + 0.020, knife_edge_datum[1] - 0.012),
        datum="A",
        label="knife-edge pivot axis",
    )
    knife_edge = _top_xy(0.0, PLATE_L / 2.0 + HEX_DEPTH / 2.0)
    add_surface_finish(
        adapter,
        top,
        edge_xy=knife_edge,
        symbol_xy=(knife_edge[0] + 0.015, knife_edge[1] + 0.015),
        roughness_ra="1.6",
        label="knife-edge ridge finish",
    )
    # Use a separate point on the bore rim so the position-frame leader does
    # not stack on the hole-callout leader at the bore's 12-o'clock point.
    anchor_bore_fcf_edge = _top_xy(TIP_X - ANCHOR_BORE_R, 0.0)
    add_feature_control_frame(
        adapter,
        top,
        edge_xy=anchor_bore_fcf_edge,
        frame_xy=(
            anchor_bore_fcf_edge[0] - 0.010,
            anchor_bore_fcf_edge[1] + 0.026,
        ),
        characteristic="position",
        tolerance="0.30",
        datums=("A",),
        diameter=True,
        label="summation anchor position",
    )
    # BASIC X coordinate backing the anchor position frame: knife-edge pivot
    # axis (datum A, the -Z trunnion ridge line) to the anchor bore centre.
    ridge_dim_edge = _top_xy(0.0, -(PLATE_L / 2.0 + 0.3 * HEX_DEPTH))
    anchor_bore_bottom = _top_xy(TIP_X, -ANCHOR_BORE_R)
    anchor_location = add_edge_dimension(
        adapter,
        top,
        p0=ridge_dim_edge,
        p1=anchor_bore_bottom,
        text_xy=(0.146, 0.050),
        label="anchor bore X location",
        orientation="horizontal",
    )
    set_basic_dimension(adapter, anchor_location, label="anchor bore X location")

    # Spring-hole pattern control: datum B on the -Z plate end, BASIC row-X /
    # start-Z / pitch coordinates off A|B, a native #47 callout, and a 20X
    # position frame -- the inspectable pattern definition (the notes no longer
    # carry these numbers as prose).
    # Pick B toward the plate's -X side and hang its tag down-LEFT: the seed
    # hole's callout leader sweeps down-right from the hole and crossed a
    # right-hung tag (layout audit).
    plate_end_edge = _top_xy(10.0, -PLATE_L / 2.0)
    add_datum_feature(
        adapter,
        top,
        edge_xy=plate_end_edge,
        symbol_xy=(plate_end_edge[0] - 0.013, plate_end_edge[1] - 0.011),
        datum="B",
        label="plate -Z end face",
    )
    seed_rim_right = _top_xy(HOLE_X + HOLE_DIA / 2.0, HOLE_Z_FIRST)
    row_x = add_edge_dimension(
        adapter,
        top,
        p0=ridge_dim_edge,
        p1=seed_rim_right,
        text_xy=(0.178, 0.042),
        label="spring-hole row X",
        orientation="horizontal",
    )
    set_basic_dimension(adapter, row_x, label="spring-hole row X")
    seed_rim_top = _top_xy(HOLE_X, HOLE_Z_FIRST + HOLE_DIA / 2.0)
    start_z = add_edge_dimension(
        adapter,
        top,
        p0=plate_end_edge,
        p1=seed_rim_top,
        text_xy=(0.196, 0.069),
        label="spring-hole start Z",
        orientation="vertical",
    )
    set_basic_dimension(adapter, start_z, label="spring-hole start Z")
    second_rim_bottom = _top_xy(HOLE_X, HOLE_Z_FIRST + CHANNEL_PITCH - HOLE_DIA / 2.0)
    pitch = add_edge_dimension(
        adapter,
        top,
        p0=seed_rim_top,
        p1=second_rim_bottom,
        text_xy=(0.205, 0.0765),
        label="spring-hole pitch",
        orientation="vertical",
    )
    set_basic_dimension(adapter, pitch, label="spring-hole pitch")
    seed_rim_bottom = _top_xy(HOLE_X, HOLE_Z_FIRST - HOLE_DIA / 2.0)
    add_native_hole_callout(
        adapter,
        top,
        edge_xy=seed_rim_bottom,
        callout_xy=(0.222, 0.052),
        label="spring-hole seed",
    )
    seed_rim_left = _top_xy(HOLE_X - HOLE_DIA / 2.0, HOLE_Z_FIRST)
    add_feature_control_frame(
        adapter,
        top,
        edge_xy=seed_rim_left,
        frame_xy=(0.222, 0.088),
        characteristic="position",
        tolerance="0.30",
        datums=("A", "B"),
        diameter=True,
        quantity="20X",
        label="spring-hole pattern position",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.075)
    add_property_linked_note(adapter, "Isometric View Note", 0.305, 0.150)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Summing Lever Manufacturing Drawing",
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
