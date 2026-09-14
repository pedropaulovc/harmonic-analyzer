r"""Create the curated machinist drawing for the green-painted top-frame casting.

The SLDPRT remains authoritative.  This recipe supplies only native model
dimensions, associative hole callouts, and the views of the casting; shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.  The top view carries the ring, web, boss, socket, and
crossbar dimensions.  Section A-A carries the recessed cap-seat dimensions and
the cross-tap callout.

The sheet is split into two columns that never share ink: graphics on the left
(plan on top, front elevation beneath it, section beside it, and the pictorial
isometric in the lower corner) with short view labels and one concise part
fact in the right column.

Run with SolidWorks open::

    uv run python cad\scripts\draw_top_frame.py top-frame
"""

from __future__ import annotations

import argparse
import sys
from typing import Any


import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_native_hole_callout,
    add_property_linked_note,
    create_section_view,
    curate_view_dimensions,
    finalize_drawing,
    model_point_in_view,
    _select_view_entity,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    visible_view_entities,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from build_top_frame import (
    BAR_X0,
    BOSS_DIA,
    COLUMN_X,
    FRONT_COLUMN_Z,
    GOOSENECK_BORE_DIA,
    GOOSENECK_X,
    GOOSENECK_Z,
    HALF_H,
    KEEPER_TAP_SPEC,
    KEEPER_TAP_X,
    KEEPER_TAP_Z_FRONT,
    OUTER_X,
    SET_POCKET_DEPTH,
    SET_TAP_SPEC,
    SIDE_TAP_DRILL_DIA,
    STUD_HOLE_DIA,
    STUD_Z_FRONT,
    TAP_DRILL_MM,
    TOP_SCREW_SEAT_Z,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    place_view,
)

SPEC = DRAWINGS_BY_NAME["top_frame"]
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

SHEET_SCALE = (1.0, 3.0)  # 1:3 whole sheet; leave air for section/detail views
VIEW_SCALE = SHEET_SCALE[0] / SHEET_SCALE[1]  # 0.333333

# Plan extents including the proud corner bosses (the straight rails alone
# stop at x +/-214.1 / z +/-131.0): x +/-223.1 -> 446.2 and z +/-138.1 ->
# 276.2 envelope; the boss stack is 47.3 tall around the 36.5 rail band.
PLAN_HALF_X = COLUMN_X + BOSS_DIA / 2.0  # 223.1
PLAN_HALF_Z = abs(FRONT_COLUMN_Z) + BOSS_DIA / 2.0  # 138.1


PLAN_HALF_W = PLAN_HALF_X * VIEW_SCALE / 1000.0  # 0.11155 sheet metres
PLAN_HALF_D = PLAN_HALF_Z * VIEW_SCALE / 1000.0  # 0.06905 sheet metres

# The note column starts beyond the plan and its right-side leaders. Dense
# 2 mm lettering keeps the longest prescribed line inside the inner border.
NOTE_COLUMN_X = 0.308
NOTE_CHAR_HEIGHT = 0.002

# Views. The plan defines the outside profile and hole pattern; the front
# elevation establishes the cutting plane through one complete corner stack.
TOP_CENTER = (0.145, 0.215)
FRONT_CENTER = (0.145, 0.103)
SECTION_CENTER = (0.340, 0.205)
ISO_CENTER = (0.055, 0.040)
ISO_SCALE = (1, 10)
LEFT_CENTER = (0.225, 0.040)
LEFT_SCALE = (1, 4)

TOP_VIEW_NOTE_XY = (0.225, 0.158)
FRONT_VIEW_NOTE_XY = (0.145, 0.067)
ISO_VIEW_NOTE_XY = (0.028, 0.022)

# Note column, read top to bottom.
MANUFACTURING_NOTES_XY = (NOTE_COLUMN_X, 0.263)


# Per-view survivors of the marked-dimension import.  The top view owns the
# plan envelope, web, boss/socket, and crossbar geometry.  Section A-A owns the
# recessed cap seat because it is internal in both ordinary orthographic views.
TOP_KEEP = {
    # Plan envelope and web depths live in clear outside lanes.
    "Width": (TOP_CENTER[0], TOP_CENTER[1] + PLAN_HALF_D + 0.004),
    "Depth": (0.030, TOP_CENTER[1]),
    "WinWidth": (TOP_CENTER[0], TOP_CENTER[1] + PLAN_HALF_D + 0.001),
    "WinDepth": (0.050, TOP_CENTER[1] + 0.032),
    "WebOuterWidth": (TOP_CENTER[0], TOP_CENTER[1] - PLAN_HALF_D - 0.005),
    "WebOuterDepth": (0.030, TOP_CENTER[1] - 0.020),
    "WebInnerWidth": (TOP_CENTER[0], TOP_CENTER[1] - PLAN_HALF_D - 0.013),
    "WebInnerDepth": (0.050, TOP_CENTER[1] - 0.034),
    # Socket, hub, pocket, and gooseneck locations use a right-hand station
    # lane outside the plan, one feature per line.
    "B0X": (0.244, TOP_CENTER[1] + 0.037),
    "B0Z": (0.244, TOP_CENTER[1] + 0.025),
    "C0Dia": (0.244, TOP_CENTER[1] + 0.013),
    "B0Dia": (0.244, TOP_CENTER[1] + 0.001),
    "HubDia": (0.244, TOP_CENTER[1] - 0.011),
    "RibWidth": (0.244, TOP_CENTER[1] - 0.023),
    "PocketRun": (0.244, TOP_CENTER[1] - 0.035),
    "SetTapZ": (0.244, TOP_CENTER[1] - 0.047),
    "GnX": (0.244, TOP_CENTER[1] - 0.059),
    "GnZ": (0.244, TOP_CENTER[1] - 0.071),
    # Crossbar envelope and junction features use the lower outside lane.
    "BarFootSpan": (0.120, TOP_CENTER[1] - PLAN_HALF_D - 0.005),
    "GussetRunE": (0.120, TOP_CENTER[1] - PLAN_HALF_D - 0.013),
    "BarSideE": (0.120, TOP_CENTER[1] - PLAN_HALF_D - 0.021),
    # Four station labels use one left/right pair of outside lanes.
    "StudFrontX": (0.030, TOP_CENTER[1] + 0.020),
    "StudFrontZ": (0.030, TOP_CENTER[1] + 0.008),
    "StudRearX": (0.030, TOP_CENTER[1] - 0.004),
    "StudRearZ": (0.030, TOP_CENTER[1] - 0.016),
    "KeeperFrontX": (0.270, TOP_CENTER[1] + 0.020),
    "KeeperFrontZ": (0.270, TOP_CENTER[1] + 0.008),
    "KeeperRearX": (0.270, TOP_CENTER[1] - 0.004),
    "KeeperRearZ": (0.270, TOP_CENTER[1] - 0.016),
}
FRONT_KEEP = {
    "PocketRise": (FRONT_CENTER[0] + PLAN_HALF_W + 0.010, FRONT_CENTER[1]),
}
SECTION_KEEP = {
    "BossTopExtent": (SECTION_CENTER[0] + 0.060, SECTION_CENTER[1] + 0.032),
    "BossBottomExtent": (SECTION_CENTER[0] + 0.060, SECTION_CENTER[1] - 0.032),
    "HubBossExtent": (SECTION_CENTER[0] - 0.060, SECTION_CENTER[1] - 0.032),
    "RingHeight": (SECTION_CENTER[0] + 0.040, SECTION_CENTER[1] - 0.012),
    "CapRecessDia": (SECTION_CENTER[0] - 0.040, SECTION_CENTER[1] + 0.020),
    "CapRecessDepth": (SECTION_CENTER[0] + 0.040, SECTION_CENTER[1] + 0.010),
}
DIMENSION_CALLOUTS = {
    "B0X": "4X SOCKET CENTRES",
    "B0Z": "4X SOCKET CENTRES",
    "C0Dia": "4X",
    "B0Dia": "4X SOCKET; FIT MHA-083 TUBE; SLIP BY HAND",
    "GussetRunE": "4X",
    "BossTopExtent": "4X",
    "BossBottomExtent": "4X",
    "CapRecessDia": ("4X CAP RECESS; FIT MHA-133 / 9275K141 CAP; SLIP BY HAND"),
    "CapRecessDepth": "4X CAP SEAT",
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")
    check("open top-frame source", await adapter.open_model(str(SOURCE)))
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
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Top Frame Ring Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "top frame; webbed gray iron ring casting; column bores",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    extension = _early_bound(drawing_model.Extension, "IModelDocExtension")
    if not extension.SetUserPreferenceInteger(542, 0, 1):
        raise RuntimeError("failed to set end-only section cutting line")
    if extension.GetUserPreferenceInteger(542, 0) != 1:
        raise RuntimeError("section cutting-line style did not persist")

    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(1, 2))
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 2))
    cut_x = model_point_in_view(
        adapter,
        front,
        (COLUMN_X / 1000.0, 0.0, 0.0),
        label="top-frame corner-section axis",
    )[0]
    section = create_section_view(
        adapter,
        front,
        line_start=(cut_x, FRONT_CENTER[1] - 0.030),
        line_end=(cut_x, FRONT_CENTER[1] + 0.030),
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=(1, 4),
        label="top-frame corner section",
    )
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    left = place_view(adapter, str(SOURCE), "*Left", *LEFT_CENTER, scale=LEFT_SCALE)
    for view in (top, front):
        set_hidden_lines_visible(adapter, view)
    for view in (section, iso, left):
        set_hidden_lines_removed(adapter, view)

    top_dimensions = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    front_dimensions = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    section_dimensions = curate_view_dimensions(
        adapter, section, keep=SECTION_KEEP, view_label="section A-A"
    )
    dimension_annotations = [*top_dimensions, *front_dimensions, *section_dimensions]
    # A prior generated drawing may have stored below-callout text on a model
    # dimension.  Clear every retained lane before applying this recipe's
    # concise manufacturing facts, otherwise removed labels survive import.
    dimension_callouts = {name: "" for name in (*TOP_KEEP, *FRONT_KEEP, *SECTION_KEEP)}
    dimension_callouts.update(DIMENSION_CALLOUTS)
    set_dimension_callouts(adapter, dimension_annotations, dimension_callouts)
    if not auto_center_marks(adapter, top, holes=True, size=0.0025):
        raise RuntimeError(
            "failed to add ASME center marks to the ring bores and stud holes"
        )

    front_tap_edge = model_point_in_view(
        adapter,
        front,
        (
            COLUMN_X / 1000.0,
            SIDE_TAP_DRILL_DIA / 2000.0,
            -TOP_SCREW_SEAT_Z / 1000.0,
        ),
        label="top-frame front column-retention tap edge",
    )
    add_native_hole_callout(
        adapter,
        front,
        edge_xy=front_tap_edge,
        callout_xy=(
            FRONT_CENTER[0] + PLAN_HALF_W + 0.012,
            FRONT_CENTER[1] + 0.010,
        ),
        label="front/rear column-retention bottoming taps",
        process="BOTTOMING TAP",
    )
    stud_edge = model_point_in_view(
        adapter,
        top,
        (
            (BAR_X0 + 11.0) / 1000.0,
            HALF_H / 1000.0,
            (STUD_Z_FRONT + STUD_HOLE_DIA / 2.0) / 1000.0,
        ),
        label="top-frame hanger-stud hole edge",
    )
    add_native_hole_callout(
        adapter,
        top,
        edge_xy=stud_edge,
        callout_xy=(TOP_CENTER[0] - 0.092, TOP_CENTER[1] - 0.047),
        label="2X hanger-stud clearance holes",
        process="DRILL",
    )
    keeper_edge = model_point_in_view(
        adapter,
        top,
        (
            KEEPER_TAP_X / 1000.0,
            HALF_H / 1000.0,
            (KEEPER_TAP_Z_FRONT + TAP_DRILL_MM[KEEPER_TAP_SPEC.size] / 2.0) / 1000.0,
        ),
        label="top-frame fulcrum-keeper tap edge",
    )
    add_native_hole_callout(
        adapter,
        top,
        edge_xy=keeper_edge,
        callout_xy=(TOP_CENTER[0] + 0.085, TOP_CENTER[1] + 0.045),
        label="2X fulcrum-keeper blind taps",
        process="TAP",
    )
    bore_candidates: list[tuple[float, float, Any]] = []
    for raw_edge in visible_view_entities(
        top, 1, label="top gooseneck clearance-bore circles"
    ):
        edge = _early_bound(raw_edge, "IEdge")
        curve = edge.GetCurve()
        if curve is None:
            continue
        curve = _early_bound(curve, "ICurve")
        if not curve.IsCircle():
            continue
        params = tuple(float(value) * 1000.0 for value in curve.CircleParams)
        radius_error = abs(params[6] - GOOSENECK_BORE_DIA / 2.0)
        center_error = abs(params[0] - GOOSENECK_X) + abs(params[2] - GOOSENECK_Z)
        bore_candidates.append((radius_error, center_error, edge))
    if not bore_candidates:
        raise RuntimeError("top view has no gooseneck clearance-bore circles")
    bore_error, center_error, gooseneck_edge = min(
        bore_candidates, key=lambda item: item[0] + item[1]
    )
    if bore_error > 0.01 or center_error > 0.02:
        raise RuntimeError(
            "top view has no gooseneck clearance-bore circle at "
            f"({GOOSENECK_X:g}, {GOOSENECK_Z:g}) mm with "
            f"{GOOSENECK_BORE_DIA / 2.0:g} mm radius"
        )
    _select_view_entity(
        adapter,
        top,
        "EDGE",
        None,
        label="gooseneck clearance-bore diameter",
        entity=gooseneck_edge,
    )
    diameter_xy = (TOP_CENTER[0] - 0.105, TOP_CENTER[1] + 0.040)
    draw = adapter.currentModel
    display = draw.AddDiameterDimension2(diameter_xy[0], diameter_xy[1], 0.0)
    if display is None:
        raise RuntimeError("failed to add gooseneck clearance-bore diameter")
    display = _early_bound(display, "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    measured_mm = abs(float(dimension.SystemValue)) * 1000.0
    if abs(measured_mm - GOOSENECK_BORE_DIA) > 1e-6:
        raise RuntimeError(
            "gooseneck clearance-bore diameter readback "
            f"{measured_mm:g} mm != {GOOSENECK_BORE_DIA:g} mm"
        )
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    if not annotation.SetPosition2(diameter_xy[0], diameter_xy[1], 0.0):
        raise RuntimeError("failed to position gooseneck clearance-bore diameter")
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    set_hidden_lines_visible(adapter, left)
    tap_candidates: list[tuple[float, float, float, Any]] = []
    tap_x = -(OUTER_X - SET_POCKET_DEPTH)
    tap_radius = TAP_DRILL_MM[SET_TAP_SPEC.size] / 2.0
    for raw_edge in visible_view_entities(
        left, 1, label="left gooseneck set-tap circles"
    ):
        edge = _early_bound(raw_edge, "IEdge")
        curve = edge.GetCurve()
        if curve is None:
            continue
        curve = _early_bound(curve, "ICurve")
        if not curve.IsCircle():
            continue
        raw_params = tuple(float(value) for value in curve.CircleParams)
        params = tuple(value * 1000.0 for value in raw_params)
        radius_error = abs(params[6] - tap_radius)
        center_error = (
            abs(params[0] - tap_x) + abs(params[1]) + abs(params[2] - GOOSENECK_Z)
        )
        normal_error = (
            abs(raw_params[3] + 1.0) + abs(raw_params[4]) + abs(raw_params[5])
        )
        tap_candidates.append((radius_error, center_error, normal_error, edge))
    if not tap_candidates:
        raise RuntimeError("left view has no set-tap circular edges")
    radius_error, center_error, normal_error, set_tap_edge = min(
        tap_candidates, key=lambda item: item[0] + item[1] + item[2]
    )
    if radius_error > 0.01 or center_error > 0.02 or normal_error > 0.02:
        raise RuntimeError(
            f"left view has no exact set-tap edge at ({tap_x:g}, 0, {GOOSENECK_Z:g}) mm"
        )
    add_native_hole_callout(
        adapter,
        left,
        edge=set_tap_edge,
        callout_xy=(LEFT_CENTER[0] + 0.043, LEFT_CENTER[1] + 0.022),
        label="gooseneck set-screw blind tap",
        process="TAP",
    )
    set_hidden_lines_removed(adapter, left)

    add_property_linked_note(
        adapter,
        "Manufacturing Notes",
        *MANUFACTURING_NOTES_XY,
        char_height=NOTE_CHAR_HEIGHT,
    )
    top_note = add_note(adapter, "PLAN VIEW SCALE 1:3", *TOP_VIEW_NOTE_XY)
    front_note = add_note(adapter, "FRONT VIEW SCALE 1:3", *FRONT_VIEW_NOTE_XY)
    if top_note is None or front_note is None:
        raise RuntimeError("failed to label top/front view scales")
    iso_note = add_note(
        adapter,
        f"ISOMETRIC VIEW SCALE {ISO_SCALE[0]:g}:{ISO_SCALE[1]:g}",
        *ISO_VIEW_NOTE_XY,
    )
    if iso_note is None:
        raise RuntimeError("failed to label isometric view scale")
    left_note = add_note(
        adapter,
        "LEFT VIEW - SET-SCREW TAP (SCALE 1:4)",
        LEFT_CENTER[0] - 0.034,
        LEFT_CENTER[1] - 0.016,
    )
    if left_note is None:
        raise RuntimeError("failed to label left set-screw-tap view")
    # Hole callouts, center marks, and linked notes can invalidate an earlier
    # HLV transition.  Reassert the orthographic display state after curation.
    for view in (top, front):
        set_hidden_lines_visible(adapter, view)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Top Frame Ring Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
