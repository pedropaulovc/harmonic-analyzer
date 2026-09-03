r"""Create the curated machinist drawing for the knife-mount bearing block.

A machined, heat-treated steel block (24 wide x ~29.4 tall x 14 deep) with a
single Ø12 bore.  The bore is the knife-edge bearing: the summing-lever
trunnion's top vertex rides its upper inner wall in line contact (ch18 p.42:
unpainted hardened steel, close bore -- 2026-09-02 user re-read).  Every face
and the bore are real edges, so
the block dimensions ride the auto-imported profile marks (block + bore) with the
depth added across the right-view section.

The knife mount is on the GD&T allowlist (cad/docs/drawing-simplicity-policy.md
rule 3, knife-edge system): the print keeps exactly ONE position frame on the
bore to the top-seat datum A, the BASIC bore height that feeds it, the ground
finish on the bore, and nothing else.  The 1/2-13 hanger-stud tap is a native
hole callout on the top view.

Run with SolidWorks open::

    uv run python cad\scripts\draw_knife_mount.py knife-mount
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from knife_mount_spec import GEOMETRIC_TOLERANCES_MM

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
    set_arc_endpoints_to_center,
    set_basic_dimension,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from knife_mount_spec import (
    BLK_BOT,
    BLK_HALF_X,
    BLK_TOP,
    BORE_CY,
    R_BORE,
    STUD_TAP_DRILL_DIA,
    SUPPORT_Z_THICK,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["knife_mount"]
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
_BLOCK_CY = (BLK_TOP + BLK_BOT) / 2.0  # block centre height (model mm)

FRONT_CENTER = (0.115, 0.140)
RIGHT_CENTER = (0.220, 0.140)
TOP_CENTER = (0.115, 0.235)
ISO_CENTER = (0.345, 0.210)


def _front_y(model_y_mm: float) -> float:
    return FRONT_CENTER[1] + (model_y_mm - _BLOCK_CY) * SHEET_SCALE[0] / 1000.0


FRONT_KEEP = {
    "BlockWidth": (FRONT_CENTER[0], _front_y(BLK_BOT) - 0.016),
    "BlockHeight": (FRONT_CENTER[0] - 0.052, FRONT_CENTER[1]),
    # Right of the block, between the position frame above and the Ra symbol
    # below: the left side carries the stacked block-height + basic bore-height
    # dimensions, and a leader there would cross the inner dimension line.
    "BoreDia": (FRONT_CENTER[0] + 0.037, _front_y(BORE_CY) + 0.021),
}
# Vertical basic dimension (bore centre to the datum-A top seat) stacked
# inside the block-height dimension: 13 mm off the block's left edge, the
# block-height line a further 15 mm out (smaller span nearest the geometry).
BORE_HEIGHT_TEXT = (
    FRONT_CENTER[0] - BLK_HALF_X * SHEET_SCALE[0] / 1000.0 - 0.013,
    (_front_y(BORE_CY) + _front_y(BLK_TOP)) / 2.0,
)
RIGHT_KEEP: dict[str, tuple[float, float]] = {}
DIMENSION_CALLOUTS = {
    "BoreDia": "THRU",
}

RIGHT_HALF_Z = SUPPORT_Z_THICK / 2.0 * SHEET_SCALE[0] / 1000.0
RIGHT_HALF_Y = (BLK_TOP - BLK_BOT) / 2.0 * SHEET_SCALE[0] / 1000.0


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open knife-mount source", await adapter.open_model(str(SOURCE)))
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
            0: "Knife-Mount Bearing Block Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "knife mount; hardened steel bearing block; knife-edge bore",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(2, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    # The bore only reads in the front view; show it dashed in the projected
    # right/top views so the orthographic set carries the thru-hole the
    # isometric implies (blind-review finding: HLR left them empty rectangles).
    set_hidden_lines_removed(adapter, iso)
    for view in (front, right, top):
        set_hidden_lines_visible(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    curate_view_dimensions(adapter, right, keep=RIGHT_KEEP, view_label="right")
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to knife bore")

    # Block depth (14): dimension the right view's flat front/back faces.
    add_edge_dimension(
        adapter,
        right,
        p0=(RIGHT_CENTER[0] - RIGHT_HALF_Z, RIGHT_CENTER[1]),
        p1=(RIGHT_CENTER[0] + RIGHT_HALF_Z, RIGHT_CENTER[1]),
        text_xy=(RIGHT_CENTER[0], RIGHT_CENTER[1] - RIGHT_HALF_Y - 0.014),
        label="block-depth overall",
    )

    # The one allowlisted frame: bore position to datum A, the block top seat
    # the hanger stud hangs it from.  Ra 0.8 on the bore's working upper wall,
    # tagged on the bore rim (a real circular edge).
    add_datum_feature(
        adapter,
        front,
        edge_xy=(FRONT_CENTER[0], _front_y(BLK_TOP)),
        symbol_xy=(FRONT_CENTER[0], _front_y(BLK_TOP) + 0.018),
        datum="A",
        label="block top seat",
    )
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=(FRONT_CENTER[0], _front_y(BORE_CY) + R_BORE * SHEET_SCALE[0] / 1000.0),
        frame_xy=(FRONT_CENTER[0] + 0.032, _front_y(BORE_CY) + 0.040),
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_MM["knife-bore position"],
        datums=("A",),
        diameter=True,
        label="knife-bore position",
    )
    add_surface_finish(
        adapter,
        front,
        edge_xy=(FRONT_CENTER[0] + R_BORE * SHEET_SCALE[0] / 1000.0, _front_y(BORE_CY)),
        symbol_xy=(FRONT_CENTER[0] + 0.052, _front_y(BORE_CY) - 0.020),
        control=surface_finish_by_key(SURFACE_FINISHES, "knife_bore"),
        label="knife bore finish",
    )
    # The basic dimension the position frame needs: bore centre to the datum-A
    # top seat, vertical.  The seat edge is picked 9 mm left of centre, clear
    # of the datum tag's pick and of the tap's hidden lines (x = +/-5.4 mm);
    # the bore is picked at 12 o'clock (the frame's own attachment) and the
    # endpoint is moved to the centre, then the value is boxed.
    bore_height = add_edge_dimension(
        adapter,
        front,
        p0=(FRONT_CENTER[0] - 0.018, _front_y(BLK_TOP)),
        p1=(FRONT_CENTER[0], _front_y(BORE_CY) + R_BORE * SHEET_SCALE[0] / 1000.0),
        text_xy=BORE_HEIGHT_TEXT,
        label="knife-bore height from datum A",
        orientation="vertical",
        entity_types=("EDGE", "EDGE"),
    )
    set_arc_endpoints_to_center(
        adapter, bore_height, label="knife-bore height from datum A"
    )
    set_basic_dimension(adapter, bore_height, label="knife-bore height from datum A")
    # The 1/2-13 hanger-stud tap: a native Hole Wizard callout picked on its
    # drawn tap-drill circle in the top view.  The tap sits on the block's X
    # centreline at mid-depth, so the circle is centred on the top view (a
    # Ø21 circle at 2:1).  Text to the right of the view, clear of the front
    # view's dimensions below it.
    add_native_hole_callout(
        adapter,
        top,
        edge_xy=(
            TOP_CENTER[0] + STUD_TAP_DRILL_DIA * SHEET_SCALE[0] / 2000.0,
            TOP_CENTER[1],
        ),
        callout_xy=(0.165, 0.255),
        label="hanger-stud tap",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.070)
    add_property_linked_note(adapter, "Isometric View Note", 0.330, 0.175)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Knife-Mount Bearing Block Manufacturing Drawing",
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
