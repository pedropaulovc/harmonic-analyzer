r"""Create the manufacturing drawing for the transgear arm plate (MHA-PD-19).

Two sheets.  Sheet 1 (REAR FACE): the plan is ``*Front``, labelled REAR VIEW,
looking at the rear face: the outline from the bore axis K (the end radius,
the top corners, the kink), the reamed bore with its finish, both screw
holes, the locating holes, and the BASIC hole positions from the bore, with
the overall height as a reference.  One hole callout on the drill Ø
(leading to the -X hole from the upper left) carries the countersink in
symbol form; the locating holes' callout points at the numbered sheet note
under the plan for their match-drilling.  The isometric stands upper right.

Sheet 2 (FACE A): the back view (``*Back``), labelled FRONT VIEW (FACE A),
looks at the mounting face A.  It carries the notch face's two corner
heights (the only view where that edge is a solid line), the side edges
from K and the overall width as a reference, the locator heights, datums B
and C and every feature control frame, one frame for each 2X group.
Section A-A cuts it on the bore axis along Y -- the plane of the
revolved hub and boss -- so the thickness over the arm, the notch depth and
the hub face's station (a baseline from face A), the hub-to-boss length and
both diameters print on solid cut edges; datum A tags face A, and the
thrust faces carry their finish with what each one runs against.  Every
frame is plain (rule 26 bars the projected-zone modifier); the section is
drawn at the sheet's scale, so its caption carries no scale.

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
from collections.abc import Callable
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    dimension_name,
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
from _drawing_attachment import _assert_attached_to
from _drawing_dimensions import (
    assert_imported_precision,
    set_arc_endpoints_to_max,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_edge_dimensions import add_edge_dimension, assert_dimension_measures
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
from _paths import CAD_ROOT
from _part_properties import part_drawing_unit
from _session import run_build
from _surface_finish import surface_finish_by_key
from _section_axis import position_section_caption
import _telemetry
from pd_transgear_arm_plate_notes import (
    HOLE_COUNT_CALLOUT,
    HUB_STATION_CALLOUT,
    LOCATOR_CALLOUT,
    LOCATOR_COUNT_CALLOUT,
    LOCATOR_NOTE,
    SCREW_HOLE_CALLOUT,
)
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
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    FINISH_CAPTIONS,
    FRONT_VIEW_LABEL,
    GEOMETRIC_CONTROLS,
    HUB_TO_BOSS_CALLOUT,
    ISO_VIEW_SCALE,
    OVERALL_HEIGHT_MM,
    OVERALL_WIDTH_MM,
    PART_DATUMS,
    REAR_VIEW_LABEL,
    SHEET_NAMES,
    SURFACE_FINISHES,
    THICKNESS_CALLOUT,
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
# left with its callouts above and beside it, the isometric upper right.
# Sheet 2: the face-A view on the left under its three rows of frames,
# section A-A to its right with its hub diameter clear of the view's
# right-hand heights.  A view's centre is its outline's; K stands
# (_TOP + _BOTTOM) / 2 below it in both face views.
SHEET_SCALE = (2.0, 1.0)
VIEW_SCALE = (2, 1)
# Section A-A stands at the sheet's scale, so its native caption drops the
# scale line the title block already states (ASME Y14.3; machinist review
# of the fan-out screen, run 20261107T081227004Z).
if VIEW_SCALE[0] / VIEW_SCALE[1] != SHEET_SCALE[0] / SHEET_SCALE[1]:
    raise AssertionError("the section's caption assumes it shares the sheet's scale")
# 6 mm lower since #2034 (the plate 6.4 longer, 12.8 on the sheet): on the
# old centre the locating-hole callout's top line crossed the upper border
# (preview run 20261028T064655627Z).
PLAN_CENTER = (0.105, 0.126)
ISO_CENTER = (0.320, 0.200)
ISO_NOTE_XY = (0.285, 0.252)
REAR_LABEL_XY = (0.093, 0.032)
# Section A-A stands 5 mm under its old line since #2034: there the
# hub-to-boss text crossed the upper border by 3.7 (preview run
# 20261028T064655627Z); its row cannot drop, its callout lines would meet
# the hub-face station's value (run 20261028T070651235Z at a 1 mm lower row:
# 1.3 mm air).  The face-A view drops to it (BACK_CENTER below), so the
# section's bore axis, boss and plate edges project straight across from the
# view (machinist review, run 20261103T155747207Z: they stood 4.2 mm apart).
KNOB_SECTION_CENTER = (0.298, 0.148)
# Section A-A's native caption, its annotation position: SOLIDWORKS hangs
# it 17 mm under the section, on the title block since #2034 (same run);
# here it stands 6 mm under the thrust-face captions, 3 mm over the title
# block, its box centred near the section's middle and clear of the ring's
# thrust-face caption (at x 0.279 the box centred at 0.260, under that
# caption: run 20261028T070651235Z).
KNOB_SECTION_CAPTION_XY = (0.309, 0.0835)

_TOP = TOP_LEFT[1]  # the plate's highest point (the top edge's -X corner)
_SECTION_TOP = arm_upper_edge_y(0.0)
_BOTTOM = -END_R
# The face-A view centres its outline, _BOTTOM.._TOP about K; section A-A's
# cuts the top edge at x = 0, _SECTION_TOP, lower than the corner.  The view
# stands that half-difference above the section's centre, so K is level in
# both; its label stands under the overall width (OVERALL_WIDTH_TEXT_XY).
BACK_CENTER = (
    0.135,
    KNOB_SECTION_CENTER[1] + (_TOP - _SECTION_TOP) / 2.0 * SHEET_SCALE[0] / 1000.0,
)
_Z_PLAN = BOSS_FACE_Z
_SCREW_Y = SCREW_HOLES[0][1]

# The cutting line, past the plate's ends: A-A runs down the face-A view on
# the bore axis (its arrows point at the view's +X side, the hub then stands
# left in the section).  Section D-D through a screw hole carried only the
# hole's projected-zone height; with plain frames (fan-out Q2-A) the hole
# callout defines the countersink and the sheet has no D-D.
SECTION_LINE_OVERRUN_MM = 3.0
KNOB_SECTION_LINE_MODEL = (
    (0.0, _SECTION_TOP + SECTION_LINE_OVERRUN_MM, 0.0),
    (0.0, _BOTTOM - SECTION_LINE_OVERRUN_MM, 0.0),
)

# Per-view survivors of the marked-dimension import, each at the MODEL point
# (mm) its text stands on.  Plan: the locator and +X hole positions stack
# above the top edge, nearest first; the -X hole's stands above them all,
# over the reamed-hole callout's leader start, so that leader runs from the
# upper left to locator 1 with no dimension line or text in its way
# (machinist review, run 20261027T152452686Z: in the rows the leader passes,
# it struck the 10.875 text).  Rule 14 keeps it off the plate (codjiflo on
# 9704957a3: inside, between locator 2 and the boss, it read on the part);
# the leader then crosses only hole 1's witness line, which rule 14 calls
# conventional.  The heights from K stand
# outboard of each side, the hole height's wide toleranced text wholly
# right of the edge.  Rows 4 apart (8 mm on the sheet: 4.4 mm air between
# 3.6 mm texts) keep the locator's witness lines under the locator
# diameter's shoulder (at 5 apart a top row rose through it: farm run
# 20261009T224545531Z, shoulder-crosses-line).  The width stands under the
# face-A view instead: across the top it was the one dimension line the
# reamed-hole leader had to cross (machinist review of the r3 sheets).
PLAN_ROWS = tuple(_SECTION_TOP + 8.0 + 4.0 * row for row in range(3))
# Three rows over the top one: 7 mm over the leader's start (r18 sheet, run
# 20261027T192628995Z: its shelf ends 20.8 over the section top).
_OVER_LEADER_ROW = _SECTION_TOP + 8.0 + 4.0 * 5
PLAN_KEEP: dict[str, tuple[float, float, float]] = {
    # Text outboard of hole 2's witness line: between it and K, the bore
    # axis's witness line struck the 4.125 (machinist review, run
    # 20261027T165127867Z).
    "ScrewHoleX2": (SCREW_HOLES[1][0] + 5.5, PLAN_ROWS[0], _Z_PLAN),
    "ScrewHoleX1": (SCREW_HOLES[0][0] / 2.0, _OVER_LEADER_ROW, _Z_PLAN),
    "KinkY": (EDGE_MINUS_X - 5.0, KINK[1] / 2.0, _Z_PLAN),
    "TopLeftY": (EDGE_MINUS_X - 11.0, TOP_LEFT[1] / 2.0, _Z_PLAN),
    "KinkRightY": (EDGE_PLUS_X + 5.0, KINK_RIGHT[1] / 2.0, _Z_PLAN),
    "ScrewHoleY": (EDGE_PLUS_X + 9.5, _SCREW_Y / 2.0, _Z_PLAN),
    "EndR": (0.7071 * END_R + 6.0, -0.7071 * END_R - 6.0, _Z_PLAN),
    # Low enough that its top line stands clear under the overall height's
    # lower witness line, which runs left from the end round's extreme.
    "BoreDia": (EDGE_MINUS_X - 4.0, _BOTTOM - 9.0, _Z_PLAN),
    # Its three short lines end left of hole 1's witness line (the .4281's:
    # at 24 characters a line from EDGE_MINUS_X - 6 that line ran through
    # the 82° and the screw's number, fan-out round 2), its shelf above the
    # overall height's upper witness line at the top corner.
    "ScrewHoleDia": (EDGE_MINUS_X - 7.45, _TOP + 11.0, _Z_PLAN),
    # Text right of K's witness line, which struck it between the two; the
    # reamed-hole leader runs on the left.
    "LocatorX1": (4.5, PLAN_ROWS[2], _Z_PLAN),
    # Under the border and high enough that its lines clear the screw-hole
    # callout; far enough left that its leader runs down to locator 1 left
    # of every location dimension line, with air to the left border (run
    # 20261027T165127867Z: its shelf met the border).  Its shelf, under the
    # whole block, ends left of hole 1's witness line (LOCATOR_SHELF_*
    # below; round 1 layout audit on 41ad5cf: the 27-character fit line's
    # shelf ran across that line, shoulder-crosses-line).
    "LocatorDia1": (EDGE_MINUS_X - 9.3, _TOP + 31.0, _Z_PLAN),
}
# Face-A view: the notch face's corner heights and the locator heights,
# outboard, the +X top corner's height outside them, and both side edges
# from K below the end round.  The corner height stands here, not on the
# plan: there its witness line ran through section D-D's letter (run
# 20261027T130144223Z).
BACK_KEEP: dict[str, tuple[float, float, float]] = {
    # Low on its line: mid-height it would sit beside the raised 18.078.
    "TopRightY": (EDGE_PLUS_X + 15.0, 5.0, 0.0),
    "EdgeLeftX": (EDGE_MINUS_X / 2.0, _BOTTOM - 7.0, 0.0),
    "EdgeRightX": (EDGE_PLUS_X / 2.0, _BOTTOM - 7.0, 0.0),
    "NotchLeftY": (EDGE_MINUS_X - 4.0, NOTCH_LEFT[1] / 2.0, FRONT_FACE_Z),
    "NotchRightY": (EDGE_PLUS_X + 4.0, NOTCH_RIGHT[1] / 2.0, FRONT_FACE_Z),
    "LocatorY1": (EDGE_MINUS_X - 8.0, LOCATOR_SITES_MM[0][1] / 2.0, 0.0),
    # Above the notch corner's height, whose line ran along its box at mid
    # height (machinist review, run 20261027T165127867Z).
    "LocatorY2": (
        EDGE_PLUS_X + 8.0, (NOTCH_RIGHT[1] + LOCATOR_SITES_MM[1][1]) / 2.0, 0.0,
    ),
}
# Section A-A (x = 0): the stations along Z are a baseline from face A,
# stacked above the plate nearest first -- the rear face, the front face, the
# hub face -- and the hub-to-boss length stands above them all; the last two
# carry what they set on two short lines under their values, between their
# witness lines (SOLIDWORKS prints no callout above a linear dimension: run
# 20261027T130144223Z; below the view, the hub-to-boss lines met the view's
# caption).  The hub diameter stands 25.5 out from the hub face, its
# text above the axis: below it, datum B's tag (face-A view) sat on it and
# read as naming the hub (machinist review, run 20261027T152452686Z); its
# witness lines stop short of the hub face, not on through the hatched hub
# to the profile line's far end at the rear face (run 20261027T180704579Z).
# The boss diameter stands beyond the boss face's caption.  The over-arm
# thickness's value and its two-line callout (16 characters, about 21 mm of
# model wide at 2:1) stand centred 16 mm right of the boss face, so the whole
# block clears the hub-to-boss dimension's boss-face witness line by about
# 5 mm of model, as the three 12-character lines did at +13 (at +6 that line
# ran through the text: machinist review of ae9ed661a), in the open sheet above
# the boss; between the plate's own witness lines they would cross face A's.
# The hub station's callout takes two lines.  SOLIDWORKS centres the
# value-and-callout block on its position, so each line raises the value
# half a line: with three, at +19.5 the hub-to-boss dimension line ran
# through it (run 20261028T111221004Z, layout audit text-on-line).  At +17.9
# the value clears that line and the block's foot clears the front face's
# value.
HUB_DIA_TEXT_STANDOFF_MM = 25.5
HUB_DIA_WITNESS_MAX_M = (HUB_DIA_TEXT_STANDOFF_MM * SHEET_SCALE[0] - 1.0) / 1000.0
SECTION_KEEP: dict[str, tuple[float, float, float]] = {
    "ThicknessOverArm": (0.0, _SECTION_TOP + 5.0, BOSS_FACE_Z + 16.0),
    "NotchDepth": (0.0, _SECTION_TOP + 10.0, FRONT_FACE_Z / 2.0),
    "HubFaceToMounting": (0.0, _SECTION_TOP + 17.9, HUB_FACE_Z / 2.0),
    "HubToBoss": (0.0, _SECTION_TOP + 28.0, (HUB_FACE_Z + BOSS_FACE_Z) / 2.0),
    "HubDia": (0.0, 11.0, HUB_FACE_Z - HUB_DIA_TEXT_STANDOFF_MM),
    "BossDia": (0.0, 0.0, BOSS_FACE_Z + 27.5),
}


def _cap_witness_lines(
    adapter: Any, annotations: list[Any], name: str, length_m: float
) -> None:
    """Cap the named dimension's witness lines at ``length_m`` (sheet) from
    its dimension line, read back."""
    found = [
        annotation for annotation in annotations
        if dimension_name(adapter, annotation) == name
    ]
    if len(found) != 1:
        raise RuntimeError(f"expected one {name} to cap its witness lines, found {len(found)}")
    display = _early_bound(
        _early_bound(found[0], "IAnnotation").GetSpecificAnnotation(), "IDisplayDimension"
    )
    display.MaxWitnessLineLength = length_m
    rebuild_drawing(adapter, label=f"{name} witness cap")
    if abs(float(display.MaxWitnessLineLength) - length_m) > 1e-9:
        raise RuntimeError(f"{name}: maximum witness-line length did not persist")


_DIM_ARROWS_INSIDE = 0  # swDimensionArrowsSide_e.swDimArrowsInside
_DIM_ARROWS_OUTSIDE = 1  # swDimensionArrowsSide_e.swDimArrowsOutside
# Outside, the -X hole's arrows ran 1.2 mm from the locator callout's line
# ends (run 20261028T000816580Z, layout audit arrow-near-text); its 21.8 mm
# span holds both arrows under its value.
PLAN_ARROW_SIDES = {"ScrewHoleX1": _DIM_ARROWS_INSIDE}
# Inside, the 18.078's upper arrowhead struck its boxed text, which stands
# between locator 2 and the notch corner's height (machinist review of
# 848ba5637, run 20261028T003904510Z, gating clarity); outside, the arrows
# point in at both witness lines and none crosses the box.
BACK_ARROW_SIDES = {"LocatorY2": _DIM_ARROWS_OUTSIDE}


def _set_arrow_sides(adapter: Any, annotations: list[Any], sides: dict[str, int]) -> None:
    """Draw each named dimension's arrows on its side of its witness lines
    (swDimensionArrowsSide_e), read back."""
    for name, side in sides.items():
        found = [
            annotation for annotation in annotations
            if dimension_name(adapter, annotation) == name
        ]
        if len(found) != 1:
            raise RuntimeError(f"expected one {name} to set its arrow side, found {len(found)}")
        display = _early_bound(
            _early_bound(found[0], "IAnnotation").GetSpecificAnnotation(), "IDisplayDimension"
        )
        display.ArrowSide = side
        if int(display.ArrowSide) != side:
            raise RuntimeError(f"{name} did not keep its arrows on side {side}")


@_telemetry.traced("drawing.transgear_arm_plate.group_frames")
def _one_frame_per_group(adapter: Any, frames: dict[str, Any]) -> None:
    """One frame for each 2X group (``frame_groups``): the other holes'
    identical frames are hidden on the sheet (``IAnnotation::Visible`` =
    swAnnotationHidden, drawing-local), and the shown frame carries the
    count above it (``IGtol::SetText(swGTolTextCalloutAbove)``).  After one
    rebuild each is read back: hidden frames hidden, each shown frame
    visible with its count; anything else fails the build."""
    groups = []
    for shown_key, hidden_keys, count in frame_groups():
        hidden = {key: _early_bound(frames[key], "IAnnotation") for key in hidden_keys}
        for annotation in hidden.values():
            annotation.Visible = _ANNOTATION_HIDDEN
        shown = _early_bound(frames[shown_key], "IAnnotation")
        gtol = _early_bound(shown.GetSpecificAnnotation(), "IGtol")
        if not gtol.SetText(_GTOL_CALLOUT_ABOVE, count):
            raise RuntimeError(f"{shown_key}: the group's {count} was refused")
        groups.append((shown_key, shown, gtol, hidden, count))
    rebuild_drawing(adapter, label="2X group frames")
    for shown_key, shown, gtol, hidden, count in groups:
        for key, annotation in hidden.items():
            if int(annotation.Visible) != _ANNOTATION_HIDDEN:
                raise RuntimeError(f"{key}: the repeated frame did not stay hidden")
        above = str(gtol.GetText(_GTOL_CALLOUT_ABOVE) or "")
        if int(shown.Visible) != _ANNOTATION_VISIBLE or above != count:
            raise RuntimeError(
                f"{shown_key}: the group's frame reads visible={shown.Visible!r}, "
                f"above={above!r}, not {count!r}"
            )
        _telemetry.info(f"2X group: {shown_key} prints {count}; hidden {sorted(hidden)}")


@_telemetry.traced("drawing.transgear_arm_plate.overall_reference", label_param="label")
def _overall_reference(
    adapter: Any,
    view: Any,
    *,
    name: str,
    label: str,
    entities: tuple[Any, Any],
    entity_types: tuple[str, str],
    picks: tuple[tuple[float, float], tuple[float, float]],
    text_xy: tuple[float, float],
    orientation: str,
    expected_mm: float,
    to_arc_extreme: bool = False,
) -> None:
    """A native overall dimension across two named view entities, measured
    (attached entities and value, after any arc end moves to the round's
    extreme), then parenthesised as a reference at the spec's places."""
    dimension = add_edge_dimension(
        adapter, view, p0=picks[0], p1=picks[1], text_xy=text_xy, label=label,
        orientation=orientation, entities=entities, entity_types=entity_types,
    )
    if to_arc_extreme:
        set_arc_endpoints_to_max(adapter, dimension, label=label)
    display = _early_bound(dimension, "IDisplayDimension")
    assert_dimension_measures(
        adapter, display, expected_mm=expected_mm, label=label,
        entities=entities, entity_types=entity_types,
    )
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    if annotation is None:
        raise RuntimeError(f"{label} has no native annotation")
    display = _early_bound(
        set_reference_dimension(adapter, annotation, label=label), "IDisplayDimension"
    )
    display.SetPrecision3(DRAWING_REFERENCE_PRECISION[name], -1, -1, -1)
    applied = int(display.GetPrimaryPrecision2())
    if applied != DRAWING_REFERENCE_PRECISION[name]:
        raise RuntimeError(
            f"{label} prints {applied} decimal places, not {DRAWING_REFERENCE_PRECISION[name]}"
        )



# Under the plan, right of the view label and the bore's finish symbol,
# left of the title block, above the border.
LOCATOR_NOTE_XY = (0.125, 0.045)

PLAN_CALLOUTS = {
    "BoreDia": BORE_CALLOUT,
    "ScrewHoleDia": SCREW_HOLE_CALLOUT,
    "LocatorDia1": LOCATOR_CALLOUT,
}
PLAN_CALLOUTS_ABOVE = {
    "ScrewHoleDia": HOLE_COUNT_CALLOUT,
    "LocatorDia1": LOCATOR_COUNT_CALLOUT,
}


def two_lines_of_words(caption: str) -> str:
    """The spec caption's words, in order, on two lines broken where the
    longer line is shortest.

    Rule 7 allows a callout at most two lines of words; the spec holds the
    thickness callout and the thrust-face captions as three (machinist
    review, run 20261112T153723793Z).  The wrap stays here until the next
    change that re-keys the part moves it into the spec (#2657).
    """
    words = caption.split()
    cut = min(
        range(1, len(words)),
        key=lambda i: max(len(" ".join(words[:i])), len(" ".join(words[i:]))),
    )
    return f"{' '.join(words[:cut])}\n{' '.join(words[cut:])}"


SECTION_CALLOUTS = {
    "ThicknessOverArm": two_lines_of_words(THICKNESS_CALLOUT),
    "HubFaceToMounting": HUB_STATION_CALLOUT,
    "HubToBoss": HUB_TO_BOSS_CALLOUT,
}
DIMENSION_CALLOUTS = {**PLAN_CALLOUTS, **SECTION_CALLOUTS}
CALLOUTS_ABOVE = PLAN_CALLOUTS_ABOVE
# The bore finish symbol stands below the end round, just right of the bore
# axis: clear of the bore callout (lower left) and the end radius (lower
# right); left of the axis its leader crossed the bore callout's (run
# 20261027T130144223Z).  Its leader lands on the bore facing the symbol,
# apart from the bore callout's landing: left to SOLIDWORKS, the two
# landed together and crossed (machinist review, run 20261027T152452686Z).
BORE_FINISH_MODEL = (3.0, _BOTTOM - 9.5, _Z_PLAN)
FINISH_CHAR_HEIGHT = 0.0025
# Position frames, sheet metres, offsets from the face-A view's K. A frame's
# xy is its top-left corner; a position frame is about 44 mm wide (59 mm it
# was with the projected zone, which rule 26 bars), and its leader leaves
# the end nearer the feature through a 6.3 mm shoulder (measured on run
# 20261009T214031408Z). The hole and locator frames stand in three rows
# above the view, which mirrors X, so its hole frames sit outboard of their
# own holes (no crossing) and the two through-bore locator leaders drop
# between the hole leaders; hole 2's frame stands far enough left that its
# leader passes left of the A-A cutting line's top letter (run
# 20261027T125555391Z). The knob bore's frame stands left of the end round,
# its leader under the side heights' witness lines; datum B's tag right of
# it.  The frames left of their features keep their right ends (and so their
# leaders) where the wider projected-zone frames had them: 15 mm right.
# K on the sheet: the view centres the outline, which spans _BOTTOM.._TOP
# about K (a fixed 0.1286 put K 6 mm off once #2034 lengthened the plate).
_BACK_K = (
    BACK_CENTER[0],
    BACK_CENTER[1] - (_TOP + _BOTTOM) / 2.0 * SHEET_SCALE[0] / 1000.0,
)
# Each 2X group prints one frame (``frame_groups``): the shown locator frame
# stands on the top row low enough that the count above it stays inside
# the upper border, the shown hole frame on the bottom row with its count
# under the locator frame.  The hidden frames keep their old rows: a
# projected frame needs a placement, and hidden it prints nothing.
FRAME_ROWS = (0.256, 0.247, 0.238)
_PROJECTED_CELL_WIDTH = 0.015
FRAME_XY = {
    "plate_hole_1_position": (_BACK_K[0] + 0.02875, FRAME_ROWS[2]),
    "plate_hole_2_position": (_BACK_K[0] - 0.10185 + _PROJECTED_CELL_WIDTH, FRAME_ROWS[2]),
    "plate_locator_1_position": (_BACK_K[0] + 0.01055, FRAME_ROWS[0]),
    "plate_locator_2_position": (_BACK_K[0] + 0.01905, FRAME_ROWS[1]),
    "knob_axis_perpendicularity": (
        _BACK_K[0] - 0.115 + _PROJECTED_CELL_WIDTH, _BACK_K[1] - 0.008,
    ),
}
# The overall references (pd_transgear_arm_plate_spec.OVERALL_*_MM).  The
# width stands under the face-A view's side widths, one 12 mm row lower,
# across the two side edges; the view's label under it.  The height stands
# on the plan left of the top corner's height (1.67), from the -X top
# corner to the end round's extreme below K, its text clear of the left
# border; its lower witness line runs over the bore callout's block.
OVERALL_WIDTH_TEXT_XY = (
    _BACK_K[0], _BACK_K[1] + (_BOTTOM - 13.0) * SHEET_SCALE[0] / 1000.0,
)
FRONT_LABEL_XY = (0.110, OVERALL_WIDTH_TEXT_XY[1] - 0.008)
# Model points on the face-A view's face A (z = 0): each side edge between
# the top corner and the notch face's corner (datum C's edge on +X).
OVERALL_WIDTH_EDGES_MODEL = (
    (EDGE_PLUS_X, (TOP_RIGHT[1] + NOTCH_RIGHT[1]) / 2.0, 0.0),
    (EDGE_MINUS_X, (TOP_LEFT[1] + NOTCH_LEFT[1]) / 2.0, 0.0),
)
OVERALL_HEIGHT_TEXT_MODEL = (EDGE_MINUS_X - 21.0, (_TOP + _BOTTOM) / 2.0, _Z_PLAN)
# The plan looks at the rear face: its -X top corner and the end round.
OVERALL_HEIGHT_CORNER_MODEL = (EDGE_MINUS_X, _TOP, REAR_FACE_Z)
OVERALL_HEIGHT_ROUND_MODEL = ((0.0, 0.0, REAR_FACE_Z), END_R)


def frame_groups() -> tuple[tuple[str, tuple[str, ...], str], ...]:
    """Each 2X group's one printed frame: the key whose frame prints, the
    keys whose identical frames are hidden, and the count text above it.

    Machinist screen (clarity, fan-out round 2): identical frames were
    repeated on each dowel ream and each screw hole instead of given once
    for the 2X group.  Every member must be the same control at its own
    site, or one frame cannot speak for them all.
    """
    groups = []
    for prefix, sites in (
        ("plate_locator_", LOCATOR_SITES_MM),
        ("plate_hole_", SCREW_HOLES),
    ):
        group = [c for c in GEOMETRIC_CONTROLS if c.key.startswith(prefix)]
        if len(group) != len(sites) or len(group) < 2:
            raise AssertionError(f"MHA-PD-19's {prefix}* group is not one control per hole")
        shown, *hidden = group
        for other in hidden:
            if (
                other.characteristic, other.tolerance, other.datums, other.tolerance_zone,
                other.projected_zone_height_mm, other.face.diameter_mm,
            ) != (
                shown.characteristic, shown.tolerance, shown.datums, shown.tolerance_zone,
                shown.projected_zone_height_mm, shown.face.diameter_mm,
            ):
                raise AssertionError(f"{other.key} is not {shown.key}'s control at its own site")
        groups.append((shown.key, tuple(other.key for other in hidden), f"{len(group)}X"))
    return tuple(groups)


_ANNOTATION_VISIBLE = 1  # swAnnotationVisibilityState_e.swAnnotationVisible
_ANNOTATION_HIDDEN = 3  # swAnnotationVisibilityState_e.swAnnotationHidden
_GTOL_CALLOUT_ABOVE = 3  # swGTolTextParts_e.swGTolTextCalloutAbove
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
# Each face's caption stands directly over its own symbol, on the symbol's
# side of every witness line (inside the face diameter's), so it reads as
# the symbol's words: under the hub diameter's lower witness line, the hub
# caption read as loose text or a note on the diameter (machinist review,
# run 20261112T165728270Z; that placement was main's).  The hub caption's
# widest line (the second, 14 characters) ends short of the face.  Each
# caption's xy is its top-left corner. Model points, mm.
FACE_FINISH_CAPTIONS = {
    key: two_lines_of_words(caption) for key, caption in FINISH_CAPTIONS.items()
}
_ModelPoint = tuple[float, float, float]


def _annulus_mid_y(face_dia: float) -> float:
    """Below the axis, midway across a thrust face's annulus."""
    return -(BORE_DIA + face_dia) / 4.0


# On the run 20261112T165728270Z sheet the Ra symbol stands 3.5 mm of model
# over its pick, and a two-line caption's block (the note's top pad, two
# lines at their pitch) is 4.2 tall; each caption's foot stands
# _CAPTION_FOOT_GAP over its symbol, less than one caption text height.
FINISH_SYMBOL_HEIGHT = 3.5
CAPTION_BLOCK_HEIGHT = 4.2
_CAPTION_FOOT_GAP = 0.7
_CAPTION_OVER_PICK = FINISH_SYMBOL_HEIGHT + _CAPTION_FOOT_GAP + CAPTION_BLOCK_HEIGHT

FACE_FINISHES: dict[str, tuple[_ModelPoint, _ModelPoint, _ModelPoint]] = {
    "hub_face": (
        (0.0, _annulus_mid_y(HUB_DIA), HUB_FACE_Z),
        (0.0, _annulus_mid_y(HUB_DIA), HUB_FACE_Z - 9.5),
        (0.0, _annulus_mid_y(HUB_DIA) + _CAPTION_OVER_PICK, HUB_FACE_Z - 20.5),
    ),
    "boss_face": (
        (0.0, _annulus_mid_y(BOSS_DIA), BOSS_FACE_Z),
        (0.0, _annulus_mid_y(BOSS_DIA), BOSS_FACE_Z + 4.0),
        (0.0, _annulus_mid_y(BOSS_DIA) + _CAPTION_OVER_PICK, BOSS_FACE_Z + 3.0),
    ),
}
# A placed note reads back its own SetPosition point; a refused move leaves
# it at the default drop, centimetres away.
NOTE_POSITION_TOL_M = 1e-5


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


def _assert_datum_b_on_bore(
    adapter: Any, projected: dict[str, Any], bore_edge: Any
) -> None:
    """Datum B is picked at its landing point (``_bore_landing``), so the
    helper's own check only proves the tag sits on what that hit-test
    returned; prove that entity IS the bore's edge, not the concentric hub
    outline within the pick aperture."""
    _assert_attached_to(
        adapter, projected["datum:B"], bore_edge, entity_type="EDGE",
        what="datum B", label="plate running bore", expected_leaders=0,
    )


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


_CAPTION_SCALE_FIELDS = ("<VLSCALE>", "<VLSCALEV>")
_CAPTION_NAME_FIELDS = ("<VLNAME>", "<VLLABEL>")


def _caption_without_scale(linked_text: str) -> str:
    """A native view caption's linked text less its scale: a line holding
    only the scale (its word and value fields) goes; scale fields sharing
    the name line go alone."""
    kept = []
    for line in linked_text.splitlines(keepends=True):
        if not any(field in line for field in _CAPTION_SCALE_FIELDS):
            kept.append(line)
        elif any(field in line for field in _CAPTION_NAME_FIELDS):
            for field in _CAPTION_SCALE_FIELDS:
                line = line.replace(field, "")
            kept.append(line)
    return "".join(kept).rstrip("\r\n")


@_telemetry.traced("drawing.plate_section_caption_scale", label_param="label")
def _drop_caption_scale(adapter: Any, view: Any, label: str) -> Callable[[], None]:
    """Drop the scale from a section's native caption: the section stands at
    the sheet's scale, which the title block states (machinist review of the
    fan-out screen, run 20261107T081227004Z: both captions printed SCALE
    2 : 1 under a 2:1 title block).  The caption is found by its label field
    (``_section_axis.position_section_caption``); its linked text is read
    back, and the returned check re-proves it after the finalizer's
    settling rebuild and sheet-scale reset."""
    bound = _early_bound(view, "IView")
    ratio = tuple(float(value) for value in bound.ScaleRatio)
    if not math.isclose(ratio[0] / ratio[1], SHEET_SCALE[0] / SHEET_SCALE[1]):
        raise RuntimeError(f"{label} stands at {ratio!r}, not the sheet's scale")
    captions = [
        note for note in (_early_bound(raw, "INote") for raw in (bound.GetNotes() or ()))
        if "<VLLABEL>" in str(note.PropertyLinkedText or "")
    ]
    if len(captions) != 1:
        raise RuntimeError(f"{label}: expected one native linked caption, found {len(captions)}")
    note = captions[0]
    linked_text = str(note.PropertyLinkedText or "")
    wanted = _caption_without_scale(linked_text)
    if "<VLLABEL>" not in wanted:
        raise RuntimeError(f"{label}: caption {linked_text!r} lost its label dropping the scale")
    if wanted != linked_text:
        note.PropertyLinkedText = wanted
        rebuild_drawing(adapter, label=f"{label} caption scale")
    _telemetry.info(f"{label} caption {linked_text!r} -> {wanted!r}")

    def settled() -> None:
        reads = str(note.PropertyLinkedText or "")
        if reads != wanted or any(field in reads for field in _CAPTION_SCALE_FIELDS):
            raise RuntimeError(f"{label} caption reads {reads!r}, not {wanted!r}")

    settled()
    return settled


def _require_note_in_view(
    note: Any, view: Any, xy: tuple[float, float], label: str
) -> None:
    """The note sits where it was placed and belongs to ``view``: a note
    inserts into whichever view is active, and a label owned by another
    view moves or disappears with it."""
    if note is None:
        raise RuntimeError(f"failed to add the plate's {label}")
    annotation = _early_bound(note, "INote").GetAnnotation()
    if not annotation:
        raise RuntimeError(f"the plate's {label} has no annotation")
    annotation = _early_bound(annotation, "IAnnotation")
    position = annotation.GetPosition()
    if not position or math.hypot(
        float(position[0]) - xy[0], float(position[1]) - xy[1]
    ) > NOTE_POSITION_TOL_M:
        raise RuntimeError(f"the plate's {label} is not at {xy}: reads {position}")
    owner = annotation.Owner
    wanted = str(_early_bound(view, "IView").GetName2())
    actual = str(_early_bound(owner, "IView").GetName2()) if owner else None
    if actual != wanted:
        raise RuntimeError(f"the plate's {label} belongs to {actual!r}, not {wanted!r}")


def _activate_view(adapter: Any, view: Any, label: str) -> None:
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, view)):
        raise RuntimeError(f"failed to activate the view for the plate's {label}")


@_telemetry.traced("drawing.plate_note", label_param="label")
def _add_note(
    adapter: Any, view: Any, text: str, xy: tuple[float, float], label: str
) -> None:
    _activate_view(adapter, view, label)
    _require_note_in_view(add_note(adapter, text, *xy), view, xy, label)


@_telemetry.traced("drawing.plate_note", label_param="label")
def _add_linked_note(
    adapter: Any, view: Any, property_name: str, xy: tuple[float, float], label: str
) -> None:
    _activate_view(adapter, view, label)
    _require_note_in_view(
        add_property_linked_note(adapter, property_name, *xy), view, xy, label
    )


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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout,
        unit=part_drawing_unit(PART_STEM),
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

    # --- Sheet 1: the rear face and the isometric. ----------------------------
    _activate_sheet(adapter, SHEET_NAMES[0])
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    plan = place_view(adapter, str(SOURCE), "*Front", *PLAN_CENTER, scale=VIEW_SCALE)
    iso = place_view(
        adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_VIEW_SCALE
    )
    for view in (plan, iso):
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
    _set_arrow_sides(adapter, plan_annotations, PLAN_ARROW_SIDES)
    if not auto_center_marks(adapter, plan, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME centre marks to the plan view")
    bore_finish_xy = _sheet_xy(adapter, plan, BORE_FINISH_MODEL, "bore finish symbol")
    add_surface_finish(
        adapter,
        plan,
        symbol_xy=bore_finish_xy,
        control=surface_finish_by_key(SURFACE_FINISHES, "transgear_arm_plate_bore"),
        label="arm-plate bore finish",
        entity=visible_circle_edge(adapter, plan, BORE_DIA),
        char_height=FINISH_CHAR_HEIGHT,
        leader_attach_xy=_bore_landing(adapter, plan, bore_finish_xy),
    )
    # The overall height, a reference: the -X top corner to the end round's
    # extreme below K, both on the rear face the plan looks at.
    plan_edges = scan_view_edges(plan, label="plate rear-face outline")
    round_centre, round_radius = OVERALL_HEIGHT_ROUND_MODEL
    height_entities = (
        plan_edges.exact_vertex_at(OVERALL_HEIGHT_CORNER_MODEL, label="plate -X top corner"),
        plan_edges.circle_at(
            round_centre, round_radius, axis=(0.0, 0.0, 1.0), label="plate end round",
        ).edge,
    )
    _overall_reference(
        adapter, plan, name="OverallHeight", label="overall height reference",
        entities=height_entities, entity_types=("VERTEX", "EDGE"),
        picks=(
            _sheet_xy(adapter, plan, OVERALL_HEIGHT_CORNER_MODEL, "plate -X top corner"),
            _sheet_xy(adapter, plan, (0.0, _BOTTOM, REAR_FACE_Z), "plate end round extreme"),
        ),
        text_xy=_sheet_xy(adapter, plan, OVERALL_HEIGHT_TEXT_MODEL, "overall height text"),
        orientation="vertical", expected_mm=OVERALL_HEIGHT_MM, to_arc_extreme=True,
    )
    _add_note(adapter, plan, LOCATOR_NOTE, LOCATOR_NOTE_XY, "locating-hole note")
    _add_note(adapter, plan, REAR_VIEW_LABEL, REAR_LABEL_XY, "rear view label")
    _add_linked_note(
        adapter, iso, "Isometric View Note", ISO_NOTE_XY, "isometric view note"
    )

    # --- Sheet 2: face A, its frames and datums, and the knob-bore section. --
    _activate_sheet(adapter, SHEET_NAMES[1])
    back = place_view(adapter, str(SOURCE), "*Back", *BACK_CENTER, scale=VIEW_SCALE)
    knob_section = _cut(
        adapter, back, KNOB_SECTION_LINE_MODEL, KNOB_SECTION_CENTER, "A",
        "plate section on the bore axis",
    )
    for view in (back, knob_section):
        set_hidden_lines_removed(adapter, view)
    caption_check = _drop_caption_scale(adapter, knob_section, "plate section A-A")
    position_section_caption(
        adapter, knob_section, KNOB_SECTION_CAPTION_XY, label="plate section A-A"
    )
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
    _cap_witness_lines(adapter, face_annotations, "HubDia", HUB_DIA_WITNESS_MAX_M)
    _set_arrow_sides(adapter, face_annotations, BACK_ARROW_SIDES)
    # These are the same native feature datums and circular zones authored
    # on the part, not +/- positions retyped on a drawing. The drill mouths,
    # the through locator bores' rims and the +X side face's edge on the
    # Front sketch (z = 0) are visible in *Back.
    back_edges = scan_view_edges(back, label="plate mounting-face PMI")
    # The bore's hub-face rim, from the scan just taken (no second sweep).
    bore_edge = back_edges.circle_at(
        (0.0, 0.0, HUB_FACE_Z), BORE_DIA / 2.0, axis=(0.0, 0.0, 1.0),
        label="plate running bore rim",
    ).edge
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
        "knob_axis_perpendicularity": PmiDrawingPlacement(
            back, FRAME_XY["knob_axis_perpendicularity"], edge_entity=bore_edge,
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
    projected = project_part_pmi(
        adapter, placements=placements, datums=PART_DATUMS,
        controls=GEOMETRIC_CONTROLS, label="plate actual-bore locating frame",
    )
    _assert_datum_b_on_bore(adapter, projected, bore_edge)
    _one_frame_per_group(adapter, projected)
    # The overall width, a reference: across the side edges on face A.
    _overall_reference(
        adapter, back, name="OverallWidth", label="overall width reference",
        entities=tuple(
            back_edges.exact_line_through(point, label=f"plate side edge {index}").edge
            for index, point in enumerate(OVERALL_WIDTH_EDGES_MODEL, 1)
        ),
        entity_types=("EDGE", "EDGE"),
        picks=tuple(
            _sheet_xy(adapter, back, point, f"plate side edge {index}")
            for index, point in enumerate(OVERALL_WIDTH_EDGES_MODEL, 1)
        ),
        text_xy=OVERALL_WIDTH_TEXT_XY,
        orientation="horizontal", expected_mm=OVERALL_WIDTH_MM,
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
            adapter, knob_section, FACE_FINISH_CAPTIONS[key],
            _sheet_xy(adapter, knob_section, caption, f"{label} caption"),
            f"{label} caption",
        )
    _add_note(adapter, back, FRONT_VIEW_LABEL, FRONT_LABEL_XY, "front view label")

    artefacts = await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Transgear Arm Plate Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        expected_sheet_names=SHEET_NAMES,
        sheet_scales={name: SHEET_SCALE for name in SHEET_NAMES},
        settled_checks=(caption_check,),
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
