r"""Create the curated machinist drawing for the fulcrum-shaft end keeper.

The SLDPRT remains authoritative.  This recipe supplies only the keeper's
views, dimension layout, hole callout, and manufacturing notes; every shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The sheet runs at 2:1 (the bracket is ~26 x 32 x 14 with the proud ball);
the isometric carries an explicit 1:1 override so it stays clear of the
title block.  Five views: the side profile (front), the plan (top, which
carries the counterbored screw-hole callout and the hole's location), the
lug end view (right, which carries the width / shaft-axis-height / crown
stack), an axial lug section for the ball seat and shaft bore, and the
isometric.

Machinist review 2026-09-02: every number is on a view.  The side view adds
the pad height, the relief height (native), the lug thickness, a vertical
ball-mid-plane centerline, a "TO BALL C/L" callout on the foot reach and a
(REF) overall to the ball's proud edge; the plan locates the screw hole; the
end view carries circumference leaders for the crown, ball seat (with its
press band on the model dimension), and reamed shaft bore, plus the complete
bore/press/ream sequence flagged from the seat.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): a
screwed-down shaft-end bracket carries no datums, no feature-control frames
and no roughness symbols; the block tolerances govern.

Run with SolidWorks open::

    uv run python cad\scripts\draw_fulcrum_keeper.py fulcrum-keeper
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_attached_note,
    add_edge_dimension,
    add_native_hole_callout,
    add_property_linked_note,
    create_section_view,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    model_point_in_view,
    read_required_properties,
    set_arc_endpoints_to_center,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    set_reference_dimension,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from fulcrum_keeper_spec import (
    BALL_CALLOUT,
    BALL_DIA,
    BALL_EDGE_X,
    CBORE_DIA_MM,
    CROWN_DIA,
    FOOT_H,
    FOOT_REACH,
    KEEPER_WIDTH,
    LUG_HALF_T,
    RELIEF_H,
    SCREW_X,
    SHAFT_AXIS_H,
)
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["fulcrum_keeper"]
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

# Sheet layout (meters).  The front (side-profile) view's model bbox is
# X -23..+3.46 (the ball's bored-through proud edge) by Y 0..32.2; at 2:1
# that is ~53 x 64 mm.  Third angle: the plan (top view) rides above the
# front, the end view (right) sits to its right, the isometric top-right.
FRONT_CENTER = (0.110, 0.130)
TOP_CENTER = (0.110, 0.228)
RIGHT_CENTER = (0.225, 0.130)
SECTION_CENTER = (0.330, 0.112)
ISO_CENTER = (0.335, 0.215)

# Model bbox centre the projected views are laid out around.
_X_MID = (-FOOT_REACH + BALL_EDGE_X) / 2.0  # -9.77
_Y_MID = (SHAFT_AXIS_H + CROWN_DIA / 2.0) / 2.0  # 16.1


def _front_x(model_x_mm: float) -> float:
    """Sheet X of a model-X point in the front view (2:1, bbox-centred)."""
    return FRONT_CENTER[0] + (model_x_mm - _X_MID) * _S / 1000.0


def _front_y(model_y_mm: float) -> float:
    """Sheet Y of a model-Y point in the front view (2:1, bbox-centred)."""
    return FRONT_CENTER[1] + (model_y_mm - _Y_MID) * _S / 1000.0


def _front_xy(model_x_mm: float, model_y_mm: float) -> tuple[float, float]:
    return (_front_x(model_x_mm), _front_y(model_y_mm))


def _top_xy(model_x_mm: float, model_z_mm: float) -> tuple[float, float]:
    """Sheet (x, y) of a model (X, Z) point in the plan view (2:1).

    The keeper is symmetric about Z = 0, so the view's Z mirror cannot matter.
    """
    return (_front_x(model_x_mm), TOP_CENTER[1] + model_z_mm * _S / 1000.0)


def _right_xy(model_z_mm: float, model_y_mm: float) -> tuple[float, float]:
    """Sheet (x, y) of a model (Z, Y) point in the lug end view (2:1)."""
    return (RIGHT_CENTER[0] + model_z_mm * _S / 1000.0, _front_y(model_y_mm))


# Handy picks derived from the layout above.
HOLE_X_SHEET = _front_x(SCREW_X)  # screw-hole station, shared by the top view
CBORE_R_SHEET = CBORE_DIA_MM * _S / 2000.0

# Per-view survivors of the marked-dimension import: parametric name ->
# sheet position.  The profile pair stacks below the front view (each text
# centred on its span, the shorter nearer the view), the relief height sits
# right of the lug; the end view carries the width / shaft-axis / crown stack,
# while section A-A carries the two fitted bores.
FRONT_KEEP = {
    "PadLen": (_front_x(SCREW_X), 0.088),
    "FootReach": (_front_x(-FOOT_REACH / 2.0), 0.078),
    "ReliefRise": (0.152, _front_y(RELIEF_H / 2.0)),
}
RIGHT_KEEP = {
    "Depth": (RIGHT_CENTER[0], 0.172),
    "ShaftAxisH": (0.196, 0.126),
    "CrownDia": (0.262, 0.166),
}
SECTION_KEEP = {
    "SocketDia": (0.370, 0.125),
    "BoreDia": (0.370, 0.103),
}
FRONT_CALLOUTS = {"FootReach": "TO BALL C/L"}
SECTION_CALLOUTS = {"SocketDia": "BALL SEAT", "BoreDia": "REAM THRU"}
# The two fitted bores print three decimals (their bands ride the model
# dimensions); everything else two.
SECTION_PRECISION = {"SocketDia": 3, "BoreDia": 3}
RIGHT_DIAMETER_LEADERS_TO_RIM = ("CrownDia",)
SECTION_DIAMETER_LEADERS_TO_RIM = ("SocketDia", "BoreDia")

# Side view sheet dimensions.
PAD_HEIGHT_PICK_X = -21.0  # clear of the counterbore's hidden lines
PAD_HEIGHT_TEXT_XY = (0.072, _front_y(FOOT_H / 2.0))
LUG_PICK_Y = 15.0  # on the lug faces, below the socket
LUG_THICKNESS_TEXT_XY = (
    _front_x(0.0),
    _front_y(SHAFT_AXIS_H + CROWN_DIA / 2.0) + 0.012,
)
OVERALL_TEXT_XY = (_front_x(_X_MID), 0.068)

# Plan view: the screw hole located from the pad's inboard end and from a
# side face (centre conditions on the counterbore rim picks).
HOLE_END_PICK_XY = _top_xy(-FOOT_REACH, 3.0)
HOLE_END_RIM_XY = (HOLE_X_SHEET - CBORE_R_SHEET, TOP_CENTER[1])
HOLE_END_TEXT_XY = (_front_x((-FOOT_REACH + SCREW_X) / 2.0), 0.204)
HOLE_SIDE_PICK_XY = _top_xy(-9.0, -KEEPER_WIDTH / 2.0)
HOLE_SIDE_RIM_XY = (HOLE_X_SHEET, TOP_CENTER[1] - CBORE_R_SHEET)
HOLE_SIDE_TEXT_XY = (0.070, TOP_CENTER[1] - 0.007)
HOLE_CALLOUT_RIM_XY = (HOLE_X_SHEET, TOP_CENTER[1] + CBORE_R_SHEET)
HOLE_CALLOUT_XY = (0.150, 0.252)
# The section line cuts vertically through the lug/ball axis in the end view,
# yielding the longitudinal X-Y section where both concentric bores are cut
# edges rather than hidden lines.
SECTION_LINE = (
    _right_xy(0.0, -1.0),
    _right_xy(0.0, SHAFT_AXIS_H + CROWN_DIA / 2.0 + 1.0),
)
# Seven short lines occupy the clear lane left of section A-A and finish above
# the title block.  The leader still terminates on the visible ball-seat edge.
BALL_NOTE_XY = (0.235, 0.112)

_ARROWS_OUTSIDE = 1  # swDimensionArrowsSide_e.swDimArrowsOutside
_BROKEN_LEADER_HORIZONTAL = 2  # swDisplayDimensionLeaderText_e


def _leaders_to_circumference(
    adapter: Any,
    annotations: list[Any],
    names: tuple[str, ...],
    *,
    label: str,
    broken_horizontal: bool = False,
) -> None:
    """End each named diameter leader at the nearest circumference.

    SolidWorks' default runs a diameter dimension line across the circle
    through its centre; with the arrows OUTSIDE the leader stops at the rim it
    names (drawing-simplicity-policy.md rule 7: never through a bore).
    ``broken_horizontal`` cuts the leader around horizontal value/callout text
    so the vertical section dimensions cannot print through their own labels.
    """
    remaining = set(names)
    for annotation in annotations:
        annotation = _sw_type_info.early_bound_or_flag(
            annotation, "IAnnotation", "GetSpecificAnnotation"
        )
        name = dimension_name(adapter, annotation)
        if name not in remaining:
            continue
        display = _sw_type_info.early_bound_or_flag(
            annotation.GetSpecificAnnotation(),
            "IDisplayDimension",
            "ArrowSide",
            "SetBrokenLeader2",
            "GetBrokenLeader2",
        )
        display.ArrowSide = _ARROWS_OUTSIDE
        if int(display.ArrowSide) != _ARROWS_OUTSIDE:
            raise RuntimeError(f"{label}: {name} arrows did not move outside")
        if broken_horizontal:
            status = int(
                display.SetBrokenLeader2(False, _BROKEN_LEADER_HORIZONTAL)
            )
            if status != 0:
                raise RuntimeError(
                    f"{label}: {name} broken-leader status {status}"
                )
            if int(display.GetBrokenLeader2()) != _BROKEN_LEADER_HORIZONTAL:
                raise RuntimeError(
                    f"{label}: {name} leader did not break around its text"
                )
        remaining.discard(name)
    if remaining:
        raise RuntimeError(f"{label}: diameter leaders not found: {sorted(remaining)}")
    adapter.currentModel.EditRebuild3()


def _add_ball_midplane_centerline(adapter: Any) -> None:
    """Draw the vertical ball/lug mid-plane named by the 23.00 dimension."""
    x = _front_x(0.0)
    margin = 0.003
    y0 = _front_y(SHAFT_AXIS_H - CROWN_DIA / 2.0) - margin
    y1 = _front_y(SHAFT_AXIS_H + CROWN_DIA / 2.0) + margin
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    drawing.EditSheet()
    sketch_manager = _early_bound(adapter.currentModel.SketchManager, "ISketchManager")
    centerline = sketch_manager.CreateCenterLine(x, y0, 0.0, x, y1, 0.0)
    if centerline is None:
        raise RuntimeError("failed to create fulcrum-keeper ball mid-plane centerline")
    adapter.currentModel.ClearSelection2(True)
    adapter.currentModel.EditRebuild3()


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open fulcrum-keeper source", await adapter.open_model(str(SOURCE)))
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
            0: "Fulcrum Keeper Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "fulcrum keeper; shaft end bracket; manufacturing drawing",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(2, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(2, 1))
    section = create_section_view(
        adapter,
        right,
        line_start=SECTION_LINE[0],
        line_end=SECTION_LINE[1],
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=(2, 1),
        label="lug axial section",
    )
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    for view in (front, top, right, section):
        set_hidden_lines_visible(adapter, view)
    set_hidden_lines_removed(adapter, iso)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    right_annotations = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="right"
    )
    section_annotations = curate_view_dimensions(
        adapter, section, keep=SECTION_KEEP, view_label="section A-A"
    )
    # The 23.00 ends at the lug/ball mid-plane, not the part's end: say so.
    set_dimension_callouts(adapter, front_annotations, FRONT_CALLOUTS)
    set_dimension_callouts(adapter, section_annotations, SECTION_CALLOUTS)
    set_dimension_precision(adapter, section_annotations, SECTION_PRECISION)
    _leaders_to_circumference(
        adapter,
        right_annotations,
        RIGHT_DIAMETER_LEADERS_TO_RIM,
        label="lug crown",
    )
    _leaders_to_circumference(
        adapter,
        section_annotations,
        SECTION_DIAMETER_LEADERS_TO_RIM,
        label="sectioned lug bores",
        broken_horizontal=True,
    )
    _add_ball_midplane_centerline(adapter)
    if not auto_center_marks(adapter, top, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to top view")

    # Side view: the pad height from the seat (left), the lug thickness
    # across its two faces (above the crown) and the (REF) overall from the
    # foot's inboard end to the ball's proud edge -- the bore/sphere
    # intersection circle, an edge-on EDGE outboard of the lug face.
    add_edge_dimension(
        adapter,
        front,
        p0=_front_xy(PAD_HEIGHT_PICK_X, 0.0),
        p1=_front_xy(PAD_HEIGHT_PICK_X, FOOT_H),
        text_xy=PAD_HEIGHT_TEXT_XY,
        label="pad height",
        orientation="vertical",
    )
    add_edge_dimension(
        adapter,
        front,
        p0=_front_xy(-LUG_HALF_T, LUG_PICK_Y),
        p1=_front_xy(LUG_HALF_T, LUG_PICK_Y),
        text_xy=LUG_THICKNESS_TEXT_XY,
        label="lug thickness",
        orientation="horizontal",
    )
    overall = add_edge_dimension(
        adapter,
        front,
        p0=_front_xy(-FOOT_REACH, FOOT_H / 2.0),
        p1=_front_xy(BALL_EDGE_X, SHAFT_AXIS_H),
        text_xy=OVERALL_TEXT_XY,
        label="overall length",
        orientation="horizontal",
    )
    set_reference_dimension(
        adapter,
        _early_bound(overall, "IDisplayDimension").GetAnnotation(),
        label="overall length",
    )

    # Plan view: the screw hole's axis from the pad's inboard end and from a
    # side face, each to the counterbore rim re-anchored at its centre.
    hole_from_end = add_edge_dimension(
        adapter,
        top,
        p0=HOLE_END_PICK_XY,
        p1=HOLE_END_RIM_XY,
        text_xy=HOLE_END_TEXT_XY,
        label="screw hole from pad end",
        orientation="horizontal",
    )
    set_arc_endpoints_to_center(adapter, hole_from_end, label="screw hole from pad end")
    hole_from_side = add_edge_dimension(
        adapter,
        top,
        p0=HOLE_SIDE_PICK_XY,
        p1=HOLE_SIDE_RIM_XY,
        text_xy=HOLE_SIDE_TEXT_XY,
        label="screw hole from side face",
        orientation="vertical",
    )
    set_arc_endpoints_to_center(adapter, hole_from_side, label="screw hole from side face")

    # Counterbored screw hole ships as the native wizard callout on the plan
    # view, where it projects as true circles.  The semicolon makes the two
    # operations explicit: DRILL applies only to the through hole, while the
    # counterbore is flat-bottomed.
    add_native_hole_callout(
        adapter,
        top,
        edge_xy=HOLE_CALLOUT_RIM_XY,
        callout_xy=HOLE_CALLOUT_XY,
        label="keeper foot screw hole",
        process="#7 DRILL THRU; FLAT-BOTTOM COUNTERBORE",
    )

    # Axial section: the complete bore/press/ream sequence, flagged from the
    # visible ball-seat cut edge rather than a hidden end-view circle.
    ball_seat = model_point_in_view(
        adapter,
        section,
        (
            -LUG_HALF_T / 1000.0,
            (SHAFT_AXIS_H - BALL_DIA / 2.0) / 1000.0,
            0.0,
        ),
        label="sectioned ball seat",
    )
    add_attached_note(
        adapter,
        section,
        text=BALL_CALLOUT,
        entity_xy=ball_seat,
        note_xy=BALL_NOTE_XY,
        label="ball callout",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.050)
    add_property_linked_note(adapter, "Isometric View Note", 0.315, 0.170)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Fulcrum Keeper Manufacturing Drawing",
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
