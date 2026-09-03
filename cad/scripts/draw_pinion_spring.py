r"""Create the curated machinist drawing for the pinion return leaf spring.

NOT a coil spring: a bent brass leaf.  A 0.8 x 4.0 half-hard brass strip formed
as a flat screw-down foot (28 long, with a #4 foot-screw clearance hole), an R2
bend up to a blade following the parked strap lean, then a subtle R1.5 kink
(~20 deg back) to a short free flat.  The profile sketches on the Front plane so
every marked dimension (foot length, both bend radii) imports into the front
profile view; the top view shows the 4.0-wide foot and locates the screw hole.

The front view dimensions the blade directly (machinist review 2026-09-02):
its straight tangent-to-tangent length beside the blade and the interior
foot-to-blade angle inside the L; the top view locates the foot hole from the
free end and from a side face.  Each bend radius sits on a ray through its
arc's own span, so no leader crosses the foot or an extension line.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): a
formed brass leaf carries no datums, frames, roughness symbols or explicit
bands; the note is the one form fact a maker cannot read off the views.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pinion_spring.py pinion-spring
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_attached_note,
    add_edge_dimension,
    add_native_hole_callout,
    add_property_linked_note,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_arc_endpoints_to_center,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from build_pinion_spring import (
    BEND_EXIT,
    FLAT_TIP,
    FOOT_END,
    FOOT_TAN,
    FOOT_Y,
    HOLE_DIA,
    HOLE_FROM_END,
    KINK_EXIT,
    KINK_START,
    WIDTH,
)
from pinion_spring_spec import TERMINAL_CALLOUT
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pinion_spring"]
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
_S = SHEET_SCALE[0] / SHEET_SCALE[1]  # sheet-mm per model-mm (2.0)

# Front view (XY): the checkmark profile -- the foot runs along the bottom, the
# blade rises to the upper right.  Centre it on the profile's y midspan.
FRONT_BBOX_CX = (FOOT_END[0] + max(BEND_EXIT[0], KINK_START[0], FLAT_TIP[0])) / 2.0
FRONT_BBOX_CY = (FOOT_Y + FLAT_TIP[1]) / 2.0
FRONT_CENTER = (0.130, 0.150)
# Put the narrow top view in the open right-hand field, above the title block
# and clear of the lower-left manufacturing-note band.
TOP_CENTER = (0.300, 0.100)
ISO_CENTER = (0.320, 0.190)


def _front_x(model_x_mm: float) -> float:
    return FRONT_CENTER[0] + (model_x_mm - FRONT_BBOX_CX) * _S / 1000.0


def _front_y(model_y_mm: float) -> float:
    return FRONT_CENTER[1] + (model_y_mm - FRONT_BBOX_CY) * _S / 1000.0


def _front_xy(model_x_mm: float, model_y_mm: float) -> tuple[float, float]:
    return (_front_x(model_x_mm), _front_y(model_y_mm))


def _top_xy(model_x_mm: float, model_z_mm: float) -> tuple[float, float]:
    """Sheet (x, y) of a model (X, Z) point in the top view (2:1).

    The strip is symmetric about Z = 0, so the view's Z mirror cannot matter.
    """
    return (
        _front_x(model_x_mm) + (TOP_CENTER[0] - FRONT_CENTER[0]),
        TOP_CENTER[1] + model_z_mm * _S / 1000.0,
    )


_FOOT_MID_X = (FOOT_END[0] + FOOT_TAN[0]) / 2.0
# An imported radius draws its leader on the ray from the text to the arc
# centre, so each radius text sits on a ray that crosses its arc's own span:
# the R2 bend spans -90..-8 deg about its centre (text below-right of the
# bend, clear of the foot and of the 28.00 stack); the R1.5 kink's concave
# side faces west (text above-left of the crest).
FRONT_KEEP = {
    "FootLen": (_front_x(_FOOT_MID_X), 0.088),
    "BendR": _front_xy(6.4, -7.9),
    "KinkR": (0.112, 0.200),
}
TOP_KEEP: dict[str, tuple[float, float]] = {}
DIMENSION_CALLOUTS: dict[str, str] = {
    "FootLen": "TRUE LENGTH\nFREE END TO BEND TANGENCY",
    "BendR": "INSIDE RADIUS",
    "KinkR": "INSIDE RADIUS",
}

# Blade: its straight length between the two tangent points (the path line is
# always one face of the one-sided thin wall, so both are drawing VERTICES),
# dimension line east of the blade; the foot-to-blade interior angle from the
# foot's path line and the blade's path line, text inside the L so the arc
# sits between them and needs no extension lines.
BLADE_MID = ((BEND_EXIT[0] + KINK_START[0]) / 2.0, (BEND_EXIT[1] + KINK_START[1]) / 2.0)
BLADE_LENGTH_TEXT_XY = _front_xy(9.2, 14.4)
FOOT_PICK_XY = _front_xy(_FOOT_MID_X, FOOT_Y)
BLADE_PICK_XY = _front_xy(*BLADE_MID)
BLADE_ANGLE_TEXT_XY = _front_xy(-6.0, 4.5)
TERMINAL_NOTE_XY = (0.215, 0.215)

# Top view: the foot hole from the free end and from a side face, both to
# the hole rim re-anchored at its centre; the callout below-right so its
# leader meets the rim without crossing either location.
_HOLE_CENTER_X = FOOT_END[0] + HOLE_FROM_END
_HOLE_R_SHEET = HOLE_DIA * _S / 2000.0
HOLE_END_PICK_XY = _top_xy(FOOT_END[0], 0.0)
HOLE_END_RIM_XY = (_top_xy(_HOLE_CENTER_X, 0.0)[0] - _HOLE_R_SHEET, TOP_CENTER[1])
HOLE_END_TEXT_XY = (_top_xy((FOOT_END[0] + _HOLE_CENTER_X) / 2.0, 0.0)[0], 0.114)
HOLE_SIDE_PICK_XY = _top_xy(FOOT_END[0] + 0.9, WIDTH / 2.0)
HOLE_SIDE_RIM_XY = (_top_xy(_HOLE_CENTER_X, 0.0)[0] + _HOLE_R_SHEET, TOP_CENTER[1])
HOLE_SIDE_TEXT_XY = (_top_xy(FOOT_END[0], 0.0)[0] - 0.008, TOP_CENTER[1] + 0.002)
HOLE_CALLOUT_XY = (0.292, 0.088)
FRONT_LABEL_XY = (0.085, 0.078)
TOP_LABEL_XY = (0.245, 0.070)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pinion-spring source", await adapter.open_model(str(SOURCE)))
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
            0: "Pinion Return Leaf Spring Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pinion return spring; bent brass leaf; formed strip",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    set_hidden_lines_removed(adapter, iso)
    for view in (front, top):
        set_hidden_lines_visible(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    curate_view_dimensions(adapter, top, keep=TOP_KEEP, view_label="top")
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)

    # The blade on the view: straight length and the interior angle.
    add_edge_dimension(
        adapter,
        front,
        p0=_front_xy(*BEND_EXIT),
        p1=_front_xy(*KINK_START),
        text_xy=BLADE_LENGTH_TEXT_XY,
        label="blade straight length",
        entity_types=("VERTEX", "VERTEX"),
    )
    add_edge_dimension(
        adapter,
        front,
        p0=FOOT_PICK_XY,
        p1=BLADE_PICK_XY,
        text_xy=BLADE_ANGLE_TEXT_XY,
        label="foot to blade angle",
    )

    terminal_mid = (
        (KINK_EXIT[0] + FLAT_TIP[0]) / 2.0,
        (KINK_EXIT[1] + FLAT_TIP[1]) / 2.0,
    )
    add_attached_note(
        adapter,
        front,
        text=TERMINAL_CALLOUT,
        entity_xy=_front_xy(*terminal_mid),
        note_xy=TERMINAL_NOTE_XY,
        label="spring short terminal inside edge",
    )
    if not auto_center_marks(adapter, top, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to top view")

    # Foot hole location on the top view: from the free end and from a side
    # face, each to the rim re-anchored at the hole centre.
    hole_from_end = add_edge_dimension(
        adapter,
        top,
        p0=HOLE_END_PICK_XY,
        p1=HOLE_END_RIM_XY,
        text_xy=HOLE_END_TEXT_XY,
        label="foot hole from free end",
        orientation="horizontal",
    )
    set_arc_endpoints_to_center(adapter, hole_from_end, label="foot hole from free end")
    hole_from_side = add_edge_dimension(
        adapter,
        top,
        p0=HOLE_SIDE_PICK_XY,
        p1=HOLE_SIDE_RIM_XY,
        text_xy=HOLE_SIDE_TEXT_XY,
        label="foot hole from side face",
        orientation="vertical",
    )
    set_arc_endpoints_to_center(adapter, hole_from_side, label="foot hole from side face")

    add_native_hole_callout(
        adapter,
        top,
        edge_xy=HOLE_SIDE_RIM_XY,
        callout_xy=HOLE_CALLOUT_XY,
        label="spring foot clearance hole",
        process="DRILL",
    )
    if add_note(adapter, "FORMED PROFILE - FRONT VIEW SCALE 2:1", *FRONT_LABEL_XY) is None:
        raise RuntimeError("failed to label spring front view")
    if (
        add_note(
            adapter,
            "TOP VIEW - LOOKING AT SCREW-DOWN FOOT BROAD FACE - SCALE 2:1",
            *TOP_LABEL_XY,
        )
        is None
    ):
        raise RuntimeError("failed to label spring top view")

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.062)
    add_property_linked_note(adapter, "Isometric View Note", 0.300, 0.164)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pinion Return Leaf Spring Manufacturing Drawing",
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
