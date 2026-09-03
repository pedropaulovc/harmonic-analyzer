r"""Create the curated machinist drawing for the magnifying-lever clamp block.

A prismatic brass block (20 x 26 x 12) carrying two skew slip bores -- the lever
bore Ø6.2 along the depth, the vertical-rod bore Ø5.2 along the height -- and a
#4-40 thumb-screw tapped from the top into the lever bore.  Every face is flat,
so the block dimensions ride the auto-imported profile marks (FRONT: block +
lever bore; TOP: rod bore, its width AND depth stations) with the lever bore's
width station drawing-added from the side face and the depth added across the
right view.

The print is plain (cad/docs/drawing-simplicity-policy.md): a thumb-screwed
clamp block is not on the GD&T allowlist, so it carries no datum, no frame,
no roughness symbol and no basic dimension -- the block tolerances govern, the
bores are DRILL callouts and the #4-40 tap is a native hole callout carrying
the tap-from-the-top instruction.

Run with SolidWorks open::

    uv run python cad\scripts\draw_magnifying_clamp.py magnifying-clamp
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_edge_dimension,
    add_native_hole_callout,
    add_property_linked_note,
    curate_view_dimensions,
    finalize_drawing,
    find_edge_near,
    new_project_drawing,
    read_required_properties,
    set_arc_endpoints_to_center,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from magnifying_clamp_spec import (
    BLOCK_DEPTH,
    BLOCK_HEIGHT,
    BLOCK_WIDTH,
    LEVER_BORE_DIA,
    LEVER_BORE_Y,
    ROD_BORE_X,
    THUMB_SCREW_TAP_DRILL_DIA,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["magnifying_clamp"]
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

SHEET_SCALE = (4.0, 1.0)
_S = SHEET_SCALE[0] / 1000.0  # sheet metres per model mm

FRONT_CENTER = (0.120, 0.120)
TOP_CENTER = (0.120, 0.215)
# Right view left of the title block, which starts at x ~0.218 below y 0.070
# (the 48 x 104 mm section's bottom edge sits just above it).
RIGHT_CENTER = (0.225, 0.120)
ISO_CENTER = (0.350, 0.215)


def _front_x(model_x_mm: float) -> float:
    return FRONT_CENTER[0] + model_x_mm * _S


def _front_y(model_y_mm: float) -> float:
    return FRONT_CENTER[1] + (model_y_mm - BLOCK_HEIGHT / 2.0) * _S


# Front view: the two stations from the side faces stack UNDER the view
# (shorter nearest), the height stands left, the bore height right, and the
# bore callout leads up-left, 10 mm above the top face so its shoulder never
# rides the outline.
FRONT_KEEP = {
    "Width": (FRONT_CENTER[0], _front_y(0.0) - 0.020),
    "Height": (_front_x(-BLOCK_WIDTH / 2.0) - 0.022, FRONT_CENTER[1]),
    "LeverBoreYDim": (_front_x(BLOCK_WIDTH / 2.0) + 0.020, _front_y(LEVER_BORE_Y / 2.0)),
    "LeverBoreDiaDim": (_front_x(-11.0), _front_y(BLOCK_HEIGHT) + 0.010),
}
# Top view: the rod-bore width station sits nearest the view in the gap under
# it (nothing else crosses that gap now that the 20.00 hangs under the front
# view); the depth station stands right; the bore callout leads up-right, 17 mm
# above the top outline.
TOP_KEEP = {
    "RodBoreXDim": (_front_x(ROD_BORE_X / 2.0), TOP_CENTER[1] - BLOCK_DEPTH / 2.0 * _S - 0.007),
    "RodBoreZ": (_front_x(BLOCK_WIDTH / 2.0) + 0.016, TOP_CENTER[1] - BLOCK_DEPTH / 4.0 * _S),
    "RodBoreDiaDim": (_front_x(ROD_BORE_X) + 0.040, TOP_CENTER[1] + BLOCK_DEPTH / 2.0 * _S + 0.017),
}
RIGHT_KEEP: dict[str, tuple[float, float]] = {}

# Process only (the DRILLED HOLES title-block row governs the drilled bores).
DIMENSION_CALLOUTS = {
    "LeverBoreDiaDim": "DRILL THRU",
    "RodBoreDiaDim": "DRILL THRU",
}
# The tap direction and breakthrough ride the hole callout itself (rule 6:
# important process facts are flagged from the view, not buried in a note).
THUMB_SCREW_PROCESS = "TAP FROM THE TOP FACE INTO THE LEVER BORE:"

RIGHT_HALF_Z = BLOCK_DEPTH / 2.0 * _S
RIGHT_HALF_Y = BLOCK_HEIGHT / 2.0 * _S

# Lever-bore width station: the left side face (picked well below the bore,
# clear of every hidden line) to the bore axis, 10.00 nearest under the view.
SIDE_FACE_PICK = (_front_x(-BLOCK_WIDTH / 2.0), _front_y(6.0))
LEVER_BORE_RIM = (_front_x(0.0), _front_y(LEVER_BORE_Y) + LEVER_BORE_DIA * _S / 2.0)
LEVER_BORE_X_TEXT = (_front_x(-BLOCK_WIDTH / 4.0), _front_y(0.0) - 0.010)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open magnifying-clamp source", await adapter.open_model(str(SOURCE)))
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
            0: "Magnifying Clamp Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "magnifying clamp; brass block; skew slip bores",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(4, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(4, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(4, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2, 1))
    set_hidden_lines_removed(adapter, iso)
    # Hidden lines ON in every orthographic view (policy rule 7): front carries
    # the vertical-rod + screw hidden bores, top the lever bore under the tap,
    # right the lever bore through the depth.
    for view in (front, top, right):
        set_hidden_lines_visible(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    curate_view_dimensions(adapter, right, keep=RIGHT_KEEP, view_label="right")
    set_dimension_callouts(
        adapter, [*front_annotations, *top_annotations], DIMENSION_CALLOUTS
    )
    for view, label in ((front, "front"), (top, "top")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center marks to {label} view")

    # Lever-bore width station (10): side face -> bore axis, re-anchored to the
    # arc CENTRE so the value locates the axis the tap shares, not the rim.
    station = add_edge_dimension(
        adapter,
        front,
        p0=SIDE_FACE_PICK,
        p1=find_edge_near(
            adapter, front, LEVER_BORE_RIM, axis="y", label="lever bore rim"
        ),
        text_xy=LEVER_BORE_X_TEXT,
        label="lever-bore width station",
        orientation="horizontal",
    )
    set_arc_endpoints_to_center(adapter, station, label="lever-bore width station")

    # Block depth (12): dimension the right view's flat front/back silhouette
    # faces (a prism section, so the edges are pickable); text ABOVE the view,
    # clear of the title block under it.
    add_edge_dimension(
        adapter,
        right,
        p0=(RIGHT_CENTER[0] - RIGHT_HALF_Z, RIGHT_CENTER[1]),
        p1=(RIGHT_CENTER[0] + RIGHT_HALF_Z, RIGHT_CENTER[1]),
        text_xy=(RIGHT_CENTER[0], RIGHT_CENTER[1] + RIGHT_HALF_Y + 0.012),
        label="block-depth overall",
    )

    # The #4-40 thumb-screw tap: a native Hole Wizard callout picked on its
    # drawn tap-drill circle in the top view.  The hole sits on the block's X
    # centreline at mid-depth, so the circle is centred on the top view; at 4:1
    # the Ø2.261 drill draws as a Ø9 circle.  The tap-from-the-top instruction
    # is the callout's process prefix; text up-left of the view, clear of the
    # rod bore callout on the right.
    add_native_hole_callout(
        adapter,
        top,
        edge_xy=(
            TOP_CENTER[0],
            TOP_CENTER[1] + THUMB_SCREW_TAP_DRILL_DIA * _S / 2.0,
        ),
        callout_xy=(0.062, 0.254),
        label="thumb-screw tap",
        process=THUMB_SCREW_PROCESS,
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.032)
    add_property_linked_note(adapter, "Isometric View Note", 0.330, 0.180)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Magnifying Clamp Manufacturing Drawing",
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
