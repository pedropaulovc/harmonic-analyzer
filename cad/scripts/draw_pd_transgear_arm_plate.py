r"""Create the manufacturing drawing for the transgear arm plate (MHA-PD-19).

Two sheets.  Sheet 1 (REAR FACE): the plan is ``*Front``, labelled REAR VIEW,
looking at the rear face: the outline from the bore axis K (the end radius,
the top corners, the kink), the reamed bore with its finish, both screw
holes with their countersinks, the locating holes, and the BASIC hole
positions from the bore (the countersink Ø from the blanked
``CountersinkReference`` sketch round the +X hole, shown in this view only:
the drill callout leads to the -X hole from the upper left, the countersink
callout to the +X hole from the upper right).  Section D-D cuts the plan
through both screw holes; a chain line in each hole draws its projected
tolerance zone from face A with the zone's height.  The isometric stands
above it.

Sheet 2 (FACE A): the back view (``*Back``), labelled FRONT VIEW (FACE A),
looks at the mounting face A.  It carries the notch face's two corner
heights (the only view where that edge is a solid line), the side edges
from K, the locator heights, datums B and C and every feature control
frame.  Section A-A cuts it on the bore axis along Y -- the plane of the
revolved hub and boss -- so the thickness over the arm, the notch depth and
the hub face's station (a baseline from face A), the hub-to-boss length and
both diameters print on solid cut edges; datum A tags face A, the thrust
faces carry their finish with what each one runs against, and a chain line
on the axis draws the knob bore's projected zone from face A toward the hub.

Every kept dimension's text point is a model point (mm) projected through
its view, so the placement holds whichever way SolidWorks orients the
section.

The knob bore is the plate origin; screw stations, top corners and notch
corners come from ``pd_transgear_arm_plate_geometry`` at the current reducer
centre. The print imports those model dimensions rather than restating a
historical bore offset.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    place_view,
    view_name,
)

from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_edges import scan_view_edges
from _drawing_finish import add_surface_finish
from _drawing_gdt import PmiDrawingPlacement, project_part_pmi
import _drawing_hidden_sketches as hidden_sketches
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_sheets import create_blank_drawing_sheets
from _drawing_view_display import set_hidden_lines_removed
from _gear_drawing_entities import visible_circle_edge
from _machinist_review_mode import MachinistReviewMode
from _native_projected_zone import require_saved_projected_gtols
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
import pd_paper_drive_assembly_steps as assembly_steps
from pd_transgear_arm_plate_geometry import (
    LOCATOR_SITES_MM,
    LOCATOR_HOLE_DIA_MM,
    BORE_DIA,
    BOSS_DIA,
    BOSS_FACE_Z,
    EDGE_MINUS_X,
    EDGE_PLUS_X,
    END_R,
    FRONT_FACE_Z,
    HUB_DIA,
    HUB_FACE_Z,
    KINK,
    KINK_RIGHT,
    NOTCH_LEFT,
    NOTCH_RIGHT,
    REAR_FACE_Z,
    SCREW_HOLE_DIA,
    SCREW_HOLES,
    TOP_LEFT,
    TOP_RIGHT,
    arm_upper_edge_y,
)
from pd_transgear_arm_plate_spec import (
    BORE_CALLOUT,
    CSK_CALLOUT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    FINISH_CAPTIONS,
    FRONT_VIEW_LABEL,
    GEOMETRIC_CONTROLS,
    HOLE_COUNT_CALLOUT,
    HUB_STATION_CALLOUT,
    HUB_TO_BOSS_CALLOUT,
    ISO_VIEW_SCALE,
    KNOB_ZONE_HEIGHT,
    LOCATOR_CALLOUT,
    PART_DATUMS,
    REAR_VIEW_LABEL,
    SCREW_HOLE_CALLOUT,
    SCREW_ZONE_HEIGHT,
    SHEET_NAMES,
    SURFACE_FINISHES,
)

# Machinist review gates this sheet: the build fails on a FIX verdict.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["pd_transgear_arm_plate"]
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

# The plate is 56 x 38 in plan and 29 deep, drawn at 2:1 on two B sheets
# (the title block fills x > 0.216 below y 0.066).  Sheet 1: the plan on the
# left with its callouts above and beside it, the isometric upper right and
# section D-D under it.  Sheet 2: the face-A view on the left under its three
# rows of frames, section A-A to its right with its hub-side zone line and
# hub diameter clear of the view's right-hand heights.  A view's centre is
# its outline's; K stands 24.4 mm below it in both face views.
SHEET_SCALE = (2.0, 1.0)
VIEW_SCALE = (2, 1)
PLAN_CENTER = (0.105, 0.132)
ISO_CENTER = (0.320, 0.200)
ISO_NOTE_XY = (0.285, 0.252)
SCREW_SECTION_CENTER = (0.305, 0.110)
REAR_LABEL_XY = (0.093, 0.038)
BACK_CENTER = (0.135, 0.153)
KNOB_SECTION_CENTER = (0.298, BACK_CENTER[1])
FRONT_LABEL_XY = (0.110, 0.081)

_TOP = TOP_LEFT[1]  # the plate's highest point (the top edge's -X corner)
_SECTION_TOP = arm_upper_edge_y(0.0)
_BOTTOM = -END_R
_Z_PLAN = BOSS_FACE_Z
_SCREW_Y = SCREW_HOLES[0][1]

# The cutting lines, past both ends of the plate.  A-A runs down the face-A
# view on the bore axis (its arrows point at the view's +X side, the hub
# then stands left in the section); D-D runs across the plan through both
# screw-hole axes, right to left (its arrows point up the plan).
SECTION_LINE_OVERRUN_MM = 3.0
KNOB_SECTION_LINE_MODEL = (
    (0.0, _SECTION_TOP + SECTION_LINE_OVERRUN_MM, 0.0),
    (0.0, _BOTTOM - SECTION_LINE_OVERRUN_MM, 0.0),
)
SCREW_SECTION_LINE_MODEL = (
    (EDGE_PLUS_X + SECTION_LINE_OVERRUN_MM, _SCREW_Y, _Z_PLAN),
    (EDGE_MINUS_X - SECTION_LINE_OVERRUN_MM, _SCREW_Y, _Z_PLAN),
)

# Per-view survivors of the marked-dimension import, each at the MODEL point
# (mm) its text stands on.  Plan: positions stack above the top edge,
# nearest first; the heights from K stand outboard of each side, the hole
# height's wide toleranced text wholly right of the edge.  Rows 4 apart (8
# mm on the sheet: 4.4 mm air between 3.6 mm texts) keep the locator's
# witness lines under the locator
# diameter's shoulder (at 5 apart a top row rose through it: farm run
# 20261009T224545531Z, shoulder-crosses-line).  The width stands under the
# face-A view instead: across the top it was the one dimension line the
# reamed-hole leader had to cross (machinist review of the r3 sheets).
PLAN_ROWS = tuple(_SECTION_TOP + 8.0 + 4.0 * row for row in range(3))
PLAN_KEEP: dict[str, tuple[float, float, float]] = {
    "ScrewHoleX2": (SCREW_HOLES[1][0] / 2.0, PLAN_ROWS[0], _Z_PLAN),
    "ScrewHoleX1": (SCREW_HOLES[0][0] / 2.0, PLAN_ROWS[1], _Z_PLAN),
    "KinkY": (EDGE_MINUS_X - 5.0, KINK[1] / 2.0, _Z_PLAN),
    "TopLeftY": (EDGE_MINUS_X - 11.0, TOP_LEFT[1] / 2.0, _Z_PLAN),
    "KinkRightY": (EDGE_PLUS_X + 5.0, KINK_RIGHT[1] / 2.0, _Z_PLAN),
    "ScrewHoleY": (EDGE_PLUS_X + 9.5, _SCREW_Y / 2.0, _Z_PLAN),
    "EndR": (0.7071 * END_R + 6.0, -0.7071 * END_R - 6.0, _Z_PLAN),
    "BoreDia": (EDGE_MINUS_X - 4.0, _BOTTOM - 6.0, _Z_PLAN),
    "ScrewHoleDia": (EDGE_MINUS_X - 6.0, _TOP + 8.0, _Z_PLAN),
    # 2.5 under the drill callout's height since #2034: with the taller plate
    # its "2X" reached hole 2's position frame (FRAME_ROWS[2]) above it.
    "CskDia": (EDGE_PLUS_X + 8.0, _TOP + 5.5, _Z_PLAN),
    "LocatorX1": (LOCATOR_SITES_MM[0][0] / 2.0, PLAN_ROWS[2], _Z_PLAN),
    # Under the border and high enough that its six lines clear the
    # screw-hole callout; far enough left that its leader runs down to
    # locator 1 left of every location dimension line.
    "LocatorDia1": (EDGE_MINUS_X - 10.8, _TOP + 31.0, _Z_PLAN),
}
# Face-A view: the notch face's corner heights and the locator heights,
# outboard, the +X top corner's height outside them, and both side edges
# from K below the end round.  The corner height stands here, not on the
# plan: there its witness line ran through section D-D's letter (run
# 20261027T130144223Z).
BACK_KEEP: dict[str, tuple[float, float, float]] = {
    "TopRightY": (EDGE_PLUS_X + 15.0, TOP_RIGHT[1] / 2.0, 0.0),
    "EdgeLeftX": (EDGE_MINUS_X / 2.0, _BOTTOM - 7.0, 0.0),
    "EdgeRightX": (EDGE_PLUS_X / 2.0, _BOTTOM - 7.0, 0.0),
    "NotchLeftY": (EDGE_MINUS_X - 4.0, NOTCH_LEFT[1] / 2.0, FRONT_FACE_Z),
    "NotchRightY": (EDGE_PLUS_X + 4.0, NOTCH_RIGHT[1] / 2.0, FRONT_FACE_Z),
    "LocatorY1": (EDGE_MINUS_X - 8.0, LOCATOR_SITES_MM[0][1] / 2.0, 0.0),
    "LocatorY2": (EDGE_PLUS_X + 8.0, LOCATOR_SITES_MM[1][1] / 2.0, 0.0),
}
# Section A-A (x = 0): the stations along Z are a baseline from face A,
# stacked above the plate nearest first -- the rear face, the front face, the
# hub face -- and the hub-to-boss length stands above them all; the last two
# carry what they set on two short lines under their values, between their
# witness lines (SOLIDWORKS prints no callout above a linear dimension: run
# 20261027T130144223Z; below the view, the hub-to-boss lines met the view's
# caption).  The hub diameter stands beyond the knob zone's chain line, its
# text below the axis; the boss diameter beyond the boss face's caption.
SECTION_KEEP: dict[str, tuple[float, float, float]] = {
    "ThicknessOverArm": (0.0, _SECTION_TOP + 5.0, REAR_FACE_Z / 2.0),
    "NotchDepth": (0.0, _SECTION_TOP + 10.0, FRONT_FACE_Z / 2.0),
    "HubFaceToMounting": (0.0, _SECTION_TOP + 19.0, HUB_FACE_Z / 2.0),
    "HubToBoss": (0.0, _SECTION_TOP + 28.0, (HUB_FACE_Z + BOSS_FACE_Z) / 2.0),
    "HubDia": (0.0, -11.0, HUB_FACE_Z - 25.5),
    "BossDia": (0.0, 0.0, BOSS_FACE_Z + 27.5),
}


def _locator_callout() -> str:
    """The locating holes' callout, citing the MHA-PD-00 match-drill steps."""
    located = assembly_steps.step_number("arm-plate-located")
    fitted = assembly_steps.step_number("arm-plate-fitted")
    if fitted != located + 1:
        raise AssertionError("the match-drill pointer cites two consecutive steps")
    return LOCATOR_CALLOUT.format(
        assembly=assembly_steps.DRAWING_NUMBER, located=located, fitted=fitted
    )


PLAN_CALLOUTS = {
    "BoreDia": BORE_CALLOUT,
    "ScrewHoleDia": SCREW_HOLE_CALLOUT,
    "CskDia": CSK_CALLOUT,
    "LocatorDia1": _locator_callout(),
}
PLAN_CALLOUTS_ABOVE = {
    "ScrewHoleDia": HOLE_COUNT_CALLOUT,
    "CskDia": HOLE_COUNT_CALLOUT,
}
SECTION_CALLOUTS = {
    "HubFaceToMounting": HUB_STATION_CALLOUT,
    "HubToBoss": HUB_TO_BOSS_CALLOUT,
}
DIMENSION_CALLOUTS = {**PLAN_CALLOUTS, **SECTION_CALLOUTS}
CALLOUTS_ABOVE = PLAN_CALLOUTS_ABOVE
# The bore finish symbol stands below the end round, just right of the bore
# axis: clear of the bore callout (lower left) and the end radius (lower
# right); left of the axis its leader crossed the bore callout's (run
# 20261027T130144223Z).
BORE_FINISH_MODEL = (3.0, _BOTTOM - 9.5, _Z_PLAN)
FINISH_CHAR_HEIGHT = 0.0025
# Position frames, sheet metres, offsets from the face-A view's K. A frame's
# xy is its top-left corner; it is about 59 mm wide with a projected zone
# (44 mm without), and its leader leaves the end nearer the feature through
# a 6.3 mm shoulder (measured on run 20261009T214031408Z). The hole and
# locator frames stand in three rows above the view, which mirrors X, so
# its hole frames sit outboard of their own holes (no crossing) and the two
# through-bore locator leaders drop between the hole leaders; hole 2's
# frame stands far enough left that its leader passes left of the A-A
# cutting line's top letter (run 20261027T125555391Z). The knob
# bore's frame stands left of the end round, its leader under the side
# heights' witness lines; datum B's tag right of it.
_BACK_K = (BACK_CENTER[0], 0.1286)
FRAME_ROWS = (0.262, 0.250, 0.238)
FRAME_XY = {
    "plate_hole_1_position": (_BACK_K[0] + 0.02875, FRAME_ROWS[2]),
    "plate_hole_2_position": (_BACK_K[0] - 0.10185, FRAME_ROWS[2]),
    "plate_locator_1_position": (_BACK_K[0] + 0.01055, FRAME_ROWS[0]),
    "plate_locator_2_position": (_BACK_K[0] + 0.01905, FRAME_ROWS[1]),
    "knob_projected_axis": (_BACK_K[0] - 0.115, _BACK_K[1] - 0.008),
}
DATUM_B_XY = (_BACK_K[0] + 0.058, _BACK_K[1] - 0.014)
# C is the vertical +X side face (sheet left in the face-A view), square to
# the X hole coordinates.  The tag stands well below the top corner so its
# horizontal leader lands on that side face, not on the sloping top edge
# (machinist review 2026-10-11 read the corner landing as the sloped face).
DATUM_C_MODEL_Y = (TOP_RIGHT[1] + NOTCH_RIGHT[1]) / 2.0
DATUM_C_XY = (_BACK_K[0] - 0.055, _BACK_K[1] + DATUM_C_MODEL_Y / 500.0)
# Datum A tags face A's cut edge in section A-A, its tag left of the face
# between the front face's and the hub face's witness lines. Model mm.
DATUM_A_MODEL = (0.0, _SCREW_Y, -14.0)
# The thrust faces' finish symbols, on section A-A where each face is
# edge-on: the pick lands on the face's own cut edge, midway across the
# annulus between the bore and the face's diameter, below the axis, and the
# symbol stands level with it beyond the face, inside the diameter's witness
# lines (under them, its leader crossed the hub's: run 20261027T130144223Z).
# The hub face's caption stands under the hub diameter's lower witness line;
# the boss face's above its symbol.  Each caption's xy is its top-left
# corner. Model points, mm.
_ModelPoint = tuple[float, float, float]


def _annulus_mid_y(face_dia: float) -> float:
    """Below the axis, midway across a thrust face's annulus."""
    return -(BORE_DIA + face_dia) / 4.0


FACE_FINISHES: dict[str, tuple[_ModelPoint, _ModelPoint, _ModelPoint]] = {
    "hub_face": (
        (0.0, _annulus_mid_y(HUB_DIA), HUB_FACE_Z),
        (0.0, _annulus_mid_y(HUB_DIA), HUB_FACE_Z - 9.5),
        (0.0, -HUB_DIA / 2.0 - 1.5, HUB_FACE_Z - 17.5),
    ),
    "boss_face": (
        (0.0, _annulus_mid_y(BOSS_DIA), BOSS_FACE_Z),
        (0.0, _annulus_mid_y(BOSS_DIA), BOSS_FACE_Z + 4.0),
        (0.0, 4.0, BOSS_FACE_Z + 3.0),
    ),
}
# Each projected zone: a chain line from face A along its feature's axis,
# just off it, for the zone's height, dimensioned as a reference (the frame
# states the height).  (start, end, dimension text) model points, mm.  The
# knob bore's runs out of A toward the hub in section A-A, its height above
# it beyond the hub face (the hub face's finish symbol stands below it);
# each screw hole's runs through the plate in section D-D past the rear
# face, its height beside the hole beyond the zone's end (beyond A it met
# the view's caption: run 20261027T130144223Z).
CHAIN_LINE_OFFSET_MM = 1.2
CHAIN_LINE_STYLE = 3  # swLineStyles_e.swLineCHAIN
CHAIN_LINE_WEIGHT = 2  # swLineWeights_e.swLW_THICK
KNOB_ZONE = (
    (0.0, CHAIN_LINE_OFFSET_MM, 0.0),
    (0.0, CHAIN_LINE_OFFSET_MM, -KNOB_ZONE_HEIGHT),
    (0.0, 4.0, -0.75 * KNOB_ZONE_HEIGHT),
)
SCREW_ZONES = tuple(
    (
        (x + CHAIN_LINE_OFFSET_MM, _SCREW_Y, 0.0),
        (x + CHAIN_LINE_OFFSET_MM, _SCREW_Y, SCREW_ZONE_HEIGHT),
        (x - 1.5, _SCREW_Y, SCREW_ZONE_HEIGHT + 3.5),
    )
    for x, _y in SCREW_HOLES
)
ZONE_LENGTH_TOL_M = 1e-7


def _sheet_xy(
    adapter: Any, view: Any, point_mm: _ModelPoint, label: str
) -> tuple[float, float]:
    """Project a model point (mm) onto the sheet through ``view``."""
    return model_point_in_view(
        adapter, view, tuple(value / 1000.0 for value in point_mm), label=label
    )


def _sheet_keep(
    adapter: Any, view: Any, keep: dict[str, _ModelPoint], label: str
) -> dict[str, tuple[float, float]]:
    """Project each kept dimension's model text point onto the sheet."""
    return {
        name: _sheet_xy(adapter, view, point, f"{label} {name}")
        for name, point in keep.items()
    }


def _bore_landing(
    adapter: Any, view: Any, toward: tuple[float, float]
) -> tuple[float, float]:
    """The point on the bore's circle in ``view`` facing ``toward`` (sheet m).

    A datum tag on a circle keeps a radial leader through its pick: the
    tag only moves along that ray, so the pick must face the tag (run
    20261027T124743046Z: picked by entity, B's tag stayed at its default
    drop on the far side of the bore, 82 mm from its request).
    """
    centre = _sheet_xy(adapter, view, (0.0, 0.0, 0.0), "bore centre")
    dx, dy = toward[0] - centre[0], toward[1] - centre[1]
    scale = BORE_DIA / 2.0 * SHEET_SCALE[0] / 1000.0 / math.hypot(dx, dy)
    return centre[0] + dx * scale, centre[1] + dy * scale


def _activate_sheet(adapter: Any, name: str) -> None:
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    if not drawing.ActivateSheet(name):
        raise RuntimeError(f"failed to activate arm-plate sheet {name!r}")


def _curated(
    adapter: Any, views: tuple[tuple[Any, dict[str, _ModelPoint], str], ...]
) -> list[Any]:
    """Each view keeps exactly its marked dimensions, at their text points."""
    return [
        annotation
        for view, keep, label in views
        for annotation in hidden_sketches.curate_view_dimensions(
            adapter,
            view,
            keep=_sheet_keep(adapter, view, keep, label),
            view_label=label,
            dimensions_by_feature=DRAWING_DIMENSIONS,
        )
    ]


def _cut(
    adapter: Any,
    parent: Any,
    line_model: tuple[_ModelPoint, _ModelPoint],
    view_xy: tuple[float, float],
    letter: str,
    label: str,
) -> Any:
    line = [_sheet_xy(adapter, parent, point, f"{label} line") for point in line_model]
    return create_section_view(
        adapter,
        parent,
        line_start=line[0],
        line_end=line[1],
        view_xy=view_xy,
        section_label=letter,
        scale=VIEW_SCALE,
        label=label,
    )


def _add_note(adapter: Any, text: str, xy: tuple[float, float], label: str) -> None:
    if add_note(adapter, text, *xy) is None:
        raise RuntimeError(f"failed to add the plate's {label}")


@_telemetry.traced("drawing.projected_zone_line", label_param="label")
def _add_zone_line(
    adapter: Any,
    view: Any,
    zone: tuple[_ModelPoint, _ModelPoint, _ModelPoint],
    *,
    height_mm: float,
    precision_key: str,
    label: str,
) -> None:
    """A thick chain line in ``view``'s sketch along a projected zone, and its
    height as a reference dimension; endpoints, style and length read back.

    Direct-to-DB, as the cutting lines are (_drawing_sections): an inferred
    endpoint would snap onto the hole wall or face A and change the length.
    """
    start, end, text = (
        _sheet_xy(adapter, view, point, f"{label} {role}")
        for point, role in zip(zone, ("start", "end", "height text"), strict=True)
    )
    model = adapter.currentModel
    drawing = _early_bound(model, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, view)):
        raise RuntimeError(f"failed to activate the view for {label}")
    model.ClearSelection2(True)
    sketch = _early_bound(_early_bound(view, "IView").GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    ends = []
    for x, y in (start, end):
        point = _early_bound(utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint")
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        ends.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(model.SketchManager, "ISketchManager")
    previous = bool(manager.AddToDB)
    manager.AddToDB = True
    try:
        segment = manager.CreateLine(*ends[0], *ends[1])
    finally:
        manager.AddToDB = previous
    if segment is None:
        raise RuntimeError(f"failed to sketch the {label} chain line")
    line = _early_bound(segment, "ISketchLine")
    for expected, accessor in ((ends[0], "GetStartPoint2"), (ends[1], "GetEndPoint2")):
        point = _early_bound(getattr(line, accessor)(), "ISketchPoint")
        actual = (float(point.X), float(point.Y), float(point.Z))
        if max(abs(a - b) for a, b in zip(actual, expected)) > 1e-9:
            raise RuntimeError(f"{label}: chain line end snapped to {actual}")
    segment = _early_bound(segment, "ISketchSegment")
    segment.Style = CHAIN_LINE_STYLE
    segment.Width = CHAIN_LINE_WEIGHT
    selection_manager = _early_bound(model.SelectionManager, "ISelectionMgr")
    selection = selection_manager.CreateSelectData()
    selection.View = view
    if not segment.Select4(False, selection):
        raise RuntimeError(f"failed to select the {label} chain line")
    across = abs(end[0] - start[0]) >= abs(end[1] - start[1])
    add = model.AddHorizontalDimension2 if across else model.AddVerticalDimension2
    display = add(text[0], text[1], 0.0)
    model.ClearSelection2(True)
    if display is None:
        raise RuntimeError(f"failed to dimension the {label} chain line")
    display = _early_bound(display, "IDisplayDimension")
    display.SetPrecision3(DRAWING_REFERENCE_PRECISION[precision_key], -1, -1, -1)
    display.SetText(1, "(")  # swDimensionTextPrefix: a reference height
    display.SetText(2, ")")  # swDimensionTextSuffix
    rebuild_drawing(adapter, label=label)
    length = float(_early_bound(display.GetDimension2(0), "IDimension").SystemValue)
    applied = (
        int(segment.Style),
        int(segment.Width),
        int(display.GetPrimaryPrecision2()),
        str(display.GetText(1) or ""),
        str(display.GetText(2) or ""),
    )
    wanted = (
        CHAIN_LINE_STYLE,
        CHAIN_LINE_WEIGHT,
        DRAWING_REFERENCE_PRECISION[precision_key],
        "(",
        ")",
    )
    if applied != wanted or not math.isclose(
        length, height_mm / 1000.0, abs_tol=ZONE_LENGTH_TOL_M
    ):
        raise RuntimeError(
            f"{label}: reads {applied} over {length * 1000.0:.4f} mm, "
            f"not {wanted} over {height_mm:.4f} mm"
        )
    _telemetry.info(f"{label}: chain {start!r} -> {end!r}, height text at {text!r}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open transgear-arm-plate source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
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
            0: "Transgear Arm Plate Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "transgear arm plate; machined steel bar",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="arm-plate sheets")

    # --- Sheet 1: the rear face, its screw-hole section and the isometric. --
    _activate_sheet(adapter, SHEET_NAMES[0])
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    plan = place_view(adapter, str(SOURCE), "*Front", *PLAN_CENTER, scale=VIEW_SCALE)
    screw_section = _cut(
        adapter, plan, SCREW_SECTION_LINE_MODEL, SCREW_SECTION_CENTER, "D",
        "plate section through the screw holes",
    )
    iso = place_view(
        adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_VIEW_SCALE
    )
    for view in (plan, screw_section, iso):
        set_hidden_lines_removed(adapter, view)
    plan_annotations = _curated(adapter, ((plan, PLAN_KEEP, "plan"),))
    # Decimal places and the explicit bands are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(
        adapter, plan_annotations,
        {name: DRAWING_PRECISION_BY_NAME[name] for name in PLAN_KEEP},
    )
    set_dimension_callouts(adapter, plan_annotations, PLAN_CALLOUTS)
    set_dimension_callouts(
        adapter, plan_annotations, PLAN_CALLOUTS_ABOVE, location="above"
    )
    if not auto_center_marks(adapter, plan, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME centre marks to the plan view")
    add_surface_finish(
        adapter,
        plan,
        symbol_xy=_sheet_xy(adapter, plan, BORE_FINISH_MODEL, "bore finish symbol"),
        control=surface_finish_by_key(SURFACE_FINISHES, "transgear_arm_plate_bore"),
        label="arm-plate bore finish",
        entity=visible_circle_edge(adapter, plan, BORE_DIA),
        char_height=FINISH_CHAR_HEIGHT,
    )
    for index, zone in enumerate(SCREW_ZONES, 1):
        _add_zone_line(
            adapter, screw_section, zone, height_mm=SCREW_ZONE_HEIGHT,
            precision_key="ScrewZone", label=f"screw hole {index} projected zone",
        )
    _add_note(adapter, REAR_VIEW_LABEL, REAR_LABEL_XY, "rear view label")
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    # --- Sheet 2: face A, its frames and datums, and the knob-bore section. --
    _activate_sheet(adapter, SHEET_NAMES[1])
    back = place_view(adapter, str(SOURCE), "*Back", *BACK_CENTER, scale=VIEW_SCALE)
    knob_section = _cut(
        adapter, back, KNOB_SECTION_LINE_MODEL, KNOB_SECTION_CENTER, "A",
        "plate section on the bore axis",
    )
    for view in (back, knob_section):
        set_hidden_lines_removed(adapter, view)
    face_annotations = _curated(
        adapter,
        (
            (back, BACK_KEEP, "face A view"),
            (knob_section, SECTION_KEEP, "section A-A"),
        ),
    )
    assert_imported_precision(
        adapter, face_annotations,
        {name: DRAWING_PRECISION_BY_NAME[name] for name in (*BACK_KEEP, *SECTION_KEEP)},
    )
    set_dimension_callouts(adapter, face_annotations, SECTION_CALLOUTS)
    # These are the same native feature datums and circular zones authored
    # on the part, not +/- positions retyped on a drawing. The drill mouths,
    # the through locator bores' rims and the +X side face's edge on the
    # Front sketch (z = 0) are visible in *Back.
    back_edges = scan_view_edges(back, label="plate mounting-face PMI")
    bore_edge = visible_circle_edge(adapter, back, BORE_DIA)
    placements = {
        "datum:A": PmiDrawingPlacement(
            knob_section,
            _sheet_xy(adapter, knob_section, DATUM_A_MODEL, "plate mounting datum tag"),
            attachment_xy=_sheet_xy(
                adapter, knob_section, (0.0, _SCREW_Y, 0.0), "plate mounting datum",
            ),
        ),
        "datum:B": PmiDrawingPlacement(
            back, DATUM_B_XY, attachment_xy=_bore_landing(adapter, back, DATUM_B_XY),
        ),
        "datum:C": PmiDrawingPlacement(
            back, DATUM_C_XY,
            edge_entity=back_edges.exact_line_through(
                (EDGE_PLUS_X, DATUM_C_MODEL_Y, 0.0), label="plate +X clock edge",
            ).edge,
        ),
        **{
            f"plate_hole_{index}_position": PmiDrawingPlacement(
                back, FRAME_XY[f"plate_hole_{index}_position"],
                edge_entity=back_edges.circle_at(
                    (x, y, 0.0), SCREW_HOLE_DIA / 2.0,
                    axis=(0.0, 0.0, 1.0), label=f"plate hole {index} position",
                ).edge,
            )
            for index, (x, y) in enumerate(SCREW_HOLES, 1)
        },
        "knob_projected_axis": PmiDrawingPlacement(
            back, FRAME_XY["knob_projected_axis"], edge_entity=bore_edge,
        ),
        **{
            f"plate_locator_{index}_position": PmiDrawingPlacement(
                back, FRAME_XY[f"plate_locator_{index}_position"],
                edge_entity=back_edges.circle_at(
                    (x, y, 0.0), LOCATOR_HOLE_DIA_MM / 2.0,
                    axis=(0.0, 0.0, 1.0), label=f"plate locator {index} position",
                ).edge,
            ) for index, (x, y) in enumerate(LOCATOR_SITES_MM, 1)
        },
    }
    project_part_pmi(
        adapter, placements=placements, datums=PART_DATUMS,
        controls=GEOMETRIC_CONTROLS, label="plate actual-bore locating frame",
    )
    if not auto_center_marks(adapter, back, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME centre marks to the face A view")
    for key, label in (
        ("hub_face", "arm-plate hub face finish"),
        ("boss_face", "arm-plate boss face finish"),
    ):
        pick, symbol, caption = FACE_FINISHES[key]
        add_surface_finish(
            adapter,
            knob_section,
            edge_xy=_sheet_xy(adapter, knob_section, pick, f"{label} pick"),
            symbol_xy=_sheet_xy(adapter, knob_section, symbol, f"{label} symbol"),
            control=surface_finish_by_key(SURFACE_FINISHES, key),
            label=label,
            char_height=FINISH_CHAR_HEIGHT,
        )
        _add_note(
            adapter, FINISH_CAPTIONS[key],
            _sheet_xy(adapter, knob_section, caption, f"{label} caption"),
            f"{label} caption",
        )
    _add_zone_line(
        adapter, knob_section, KNOB_ZONE, height_mm=KNOB_ZONE_HEIGHT,
        precision_key="KnobZone", label="knob bore projected zone",
    )
    _add_note(adapter, FRONT_VIEW_LABEL, FRONT_LABEL_XY, "front view label")

    artefacts = await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Transgear Arm Plate Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        expected_sheet_names=SHEET_NAMES,
        sheet_scales={name: SHEET_SCALE for name in SHEET_NAMES},
    )
    require_saved_projected_gtols(
        adapter, artefacts["drawing"], GEOMETRIC_CONTROLS,
        label="saved transgear arm plate drawing projected axes",
    )
    return artefacts


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
