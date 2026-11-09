r"""Create the manufacturing drawing for the transgear arm (MHA-PD-18).

The principal view is ``*Front``, looking at the REAR face: the outline (the
pivot radius, the tip station and the end-face width), the pivot bore, the
MHA-PD-23 pin's reamed press bore, the plate-tap callout with its transfer
line (the taps are spotted and drilled through MHA-PD-19's screw holes at
assembly, so they carry no frame and their stations print as references),
and the hole stations from the pivot (the blanked ``StationReference``
sketch, shown in this view only). The plate-tap stations follow the
reducer's knob bore through ``pd_transgear_arm_geometry``; neither their
imported dimensions nor the annotation picks fix a previous centre.
Section A-A cuts it on the centreline -- through the pivot, every hole and the
latch-pin hole -- so the rear spot face's diameter, its floor from the FRONT
face (the pivot head's end play), the latch-pin hole's depth and the pin
bore's position and perpendicularity frames print on solid cut edges.  The
end view (``*Right``, the square end) carries the thickness (the ground
stock's, printed as a reference to it) and the latch-pin hole's reamed size,
its height and the press of the pin to the hole floor.  The matched locating
holes run through from the rear face the front view looks at, so their
stations and size print there, and section B-B, which cuts them on their
axes, carries one position frame for the 2X group.  No frame carries a
projected zone (delegated ruling 2026-11-07, rule 26).  Sheet 2's section
D-D cuts the pin bore on its axis: the rear mouth's chamfer leg with its
band.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    dimension_name,
    place_view,
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
from _drawing_annotation_extent import (
    move_annotation,
    require_inside,
    sheet_region,
)
from _drawing_dimensions import (
    assert_imported_precision,
    offset_dimension_text,
    set_arc_endpoints_to_max,
    set_dimension_callouts,
    set_reference_dimension,
    set_reference_dimensions,
)
from _drawing_edge_dimensions import add_edge_dimension
from _drawing_edges import visible_view_entities
from _drawing_gdt import PmiDrawingPlacement, project_part_pmi
import _drawing_hidden_sketches as hidden_sketches
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view, model_points_in_view
from _part_properties import part_drawing_unit
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_sheets import create_blank_drawing_sheets
from _drawing_view_display import set_hidden_lines_removed
from _hole_spec import blind_cut_dia_mm
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from pd_transgear_arm_geometry import (
    LOCATOR_SITES_MM,
    LOCATOR_HOLE_DIA_MM,
    PIN_BORE_DIA,
    PIN_HOLE_DEPTH,
    PIN_MOUTH_CHAMFER,
    PIN_STATION,
    PIVOT_END_R,
    PLATE_TAP_SPEC,
    PLATE_TAP_STATIONS,
    THICKNESS,
    TIP_STATION,
    edge_half_width,
)
from pd_transgear_arm_spec import (
    GEOMETRIC_CONTROLS,
    PART_DATUMS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    ISO_VIEW_SCALE,
    OVERALL_LENGTH,
    STOCK_TEXT_PREFIX,
    STOCK_TEXT_SUFFIX,
)
from pd_transgear_arm_notes import (
    DIMENSION_CALLOUTS,
    NOTES_TEXT,
    PIN_MOUTH_CALLOUT,
    PLATE_TAP_QUALIFIER,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["pd_transgear_arm"]
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

# The arm is 141 mm long: 2:1 spans 0.283 m of the landscape sheet, with the
# section A-A under it and the end view and isometric to its right, clear of
# the title block (x > 0.216 below y 0.066).  The front view's box centres
# at x 0.189 so the section's floor-depth text, hanging left of its
# dimension line under the pivot end, keeps inside the left border
# (machinist reviews of 19e33c6c2 and 8b5e1f354: at 0.178 it reached x 1.5
# mm).  The end view moves 2 mm with it, so the 14.0 keeps clear of it.
SHEET_SCALE = (2.0, 1.0)
VIEW_SCALE = (2, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
FRONT_CENTER = (0.189, 0.205)
# Low enough that the counterbore callout's two lines above its value clear
# the overall-length reference under the station stack.
SECTION_CENTER = (FRONT_CENTER[0], 0.090)
END_CENTER = (0.357, FRONT_CENTER[1])
# On sheet 2, right of section D-D in its open field, its label over it.
# On sheet 1 under section A-A it crowded A-A's frames, the floor
# depth's text and A-A's caption (machinist review of 67d749fb4, run
# 20261028T000748086Z, gating clarity).
ISO_CENTER = (0.330, 0.125)
ISO_NOTE_XY = (0.300, 0.157)
# Under the end view's pin callout and on its axis; its label clears the
# title block and section A-A's 8.50.  The socket mouths face right, and the
# column right of them holds the sockets' position frames inside the border.
LOCATOR_SECTION_CENTER = (END_CENTER[0], 0.120)
# The front view centres on the outline's bounding box (x -R .. tip).
_BBOX_CENTER_X = (TIP_STATION - PIVOT_END_R) / 2.0


def _front_x(model_x_mm: float) -> float:
    """Sheet X of a model-X station in the front view and section A-A."""
    return FRONT_CENTER[0] + (model_x_mm - _BBOX_CENTER_X) * _S / 1000.0


def _front_y(model_y_mm: float) -> float:
    """Sheet Y of a model-Y offset in the front view."""
    return FRONT_CENTER[1] + model_y_mm * _S / 1000.0


def _end_x(model_z_mm: float) -> float:
    """Sheet X of a model-Z height in the end view (*Right: sheet right = -Z)."""
    return END_CENTER[0] - (model_z_mm - THICKNESS / 2.0) * _S / 1000.0


def _end_y(model_y_mm: float) -> float:
    return END_CENTER[1] + model_y_mm * _S / 1000.0


# Across the front view on the centreline: the cut is the Top plane, the
# plane of the spot-face profile, through every hole.
SECTION_LINE_OVERRUN = 0.005
_PIN_SECTION_LOWER_OVERRUN = 0.009
SECTION_LINE = (
    (_front_x(-PIVOT_END_R) - SECTION_LINE_OVERRUN, FRONT_CENTER[1]),
    (_front_x(TIP_STATION) + SECTION_LINE_OVERRUN, FRONT_CENTER[1]),
)

# Per-view survivors of the marked-dimension import.  The stations stack
# under the front view, nearest first, the overall reference under them;
# the callouts stand above it, the pin bore's below right.
_UNDER_FRONT = _front_y(-PIVOT_END_R)
STATION_PITCH = 0.009


def _station_row(index: int) -> float:
    return _UNDER_FRONT - 0.010 - index * STATION_PITCH


_LOCATOR_X = _front_x(LOCATOR_SITES_MM[0][0])
# Midway between plate tap 1's and the sockets' station witness lines.
_LOCATOR_OFFSET_X = (_front_x(PLATE_TAP_STATIONS[0]) + _LOCATOR_X) / 2.0
# Below the arm, every station witness line runs down through the text's
# height, and each 6.850 (with its shoulder, 14.5 mm) hangs LEFT of its
# dimension line: the lower one's line stands left of plate tap 1's hole,
# so its text stands clear of every witness line (runs 20261027T124240514Z
# and 20261027T124924064Z: between tap 1's and the sockets' witness lines
# the text or its shoulder was struck).
_LOWER_OFFSET_X = _front_x(PLATE_TAP_STATIONS[0]) - 0.005
FRONT_KEEP = {
    # Lower left of the pivot round, clear of datum B's tag above it.
    "PivotEndR": (0.025, FRONT_CENTER[1] + 0.010),
    "PivotBoreDia": (0.060, _front_y(PIVOT_END_R) + 0.021),
    # The pin bore's Ø and its callout lines stand below right of the arm,
    # right of the station stack; the upper band holds the tap and locator
    # callouts.
    "PinBoreDia": (_front_x(PIN_STATION) + 0.056, _UNDER_FRONT - 0.024),
    "EndWidth": (_front_x(TIP_STATION) + 0.012, FRONT_CENTER[1]),
    # Mid-line, or further left: it keeps 12 mm between its centre and the
    # lower 6.850's box, which hangs left of tap 1 (since #2034 moved K, tap 1
    # stands 6.2 nearer the pivot and mid-line came within 7 mm of it).
    "PlateTapStation1": (
        min(_front_x(PLATE_TAP_STATIONS[0] / 2.0), _LOWER_OFFSET_X - 0.0145 - 0.012),
        _station_row(0),
    ),
    "LocatorX1": (_front_x(LOCATOR_SITES_MM[0][0] / 2.0), _station_row(1)),
    "PlateTapStation2": (_front_x(PLATE_TAP_STATIONS[1] / 2.0), _station_row(2)),
    "PinStation": (_front_x(PIN_STATION / 2.0), _station_row(3)),
    "TipStation": (_front_x(TIP_STATION / 2.0), _station_row(4)),
    # The socket offsets' texts stand outside the arm: above its top edge,
    # under the tap callout's shelf, and below its bottom edge, left of
    # plate tap 1's witness line (machinist review: inside the silhouette
    # they crowded the sockets and line B).
    "LocatorY1": (_LOCATOR_OFFSET_X, _front_y(PIVOT_END_R) + 0.0045),
    "LocatorY2": (_LOWER_OFFSET_X, _front_y(-PIVOT_END_R) - 0.0045),
    # Five callout lines under the stacked-band value (six ran the block
    # from the border to the arm's top edge: machinist review of
    # 2cb922430). SOLIDWORKS centres the block on this point, so the dropped
    # line frees about 1.4 mm at each end; 0.5 mm lower splits it, about
    # 1.9 mm under the border and 0.9 mm over the edge.
    "LocatorDia1": (0.262, _front_y(PIVOT_END_R) + 0.0144),
}
# The true overall (review of 19e33c6c2: the 128.90 from the bore axis read
# as one), a reference under the stations: picked on the pivot round's upper
# flank and re-anchored to its far extreme, and on the square end.
OVERALL_TEXT_XY = (FRONT_CENTER[0], _station_row(5))
_FLANK = PIVOT_END_R * math.sqrt(0.5)
OVERALL_PICKS = (
    (_front_x(-_FLANK), _front_y(_FLANK)),
    (_front_x(TIP_STATION), _front_y(3.0)),
)
# The floor depth's dimension line runs 4 mm off the section's pivot end,
# outside its witness lines. Its text, which names the spring it preloads,
# is wider than the 31 mm between that line and the left border, so it
# stands off the line on a leader (the stock text's idiom) under the
# section, RIGHT of the line: the leader runs from the line to the near
# (left) end of the text's underline, outside the text. Left of the line,
# it ran to the underline's right end up through the text (run
# 20261027T223014650Z, layout audit extension-through-own-text, 3.3 mm).
# 4 mm, not 2: the leader then passes the pivot end's lower corner clear.
# The spot face's callout stands right of its extension lines, above the
# section (machinist review: between them, the lines struck its text; an
# above-the-value callout prints one line only), clear of the overall
# reference above it.
SECTION_KEEP = {
    # Half a millimetre higher than 0.019: an arrow on face A ran under its
    # last line at 0.019 (run 20261027T180656347Z: 1.9 mm, under the 2.0
    # arrow clearance).
    "SpotFaceDia": (0.1295, SECTION_CENTER[1] + 0.0196),
    "FloorDepth": (_front_x(-PIVOT_END_R) - 0.004, SECTION_CENTER[1] - 0.022),
    # 4 mm higher than 0.020: its dimension line stood 1.8 mm over the
    # title block (review of 2ac1bdb28).
    "PinHoleDepth": (
        _front_x(TIP_STATION - PIN_HOLE_DEPTH / 2.0),
        SECTION_CENTER[1] - 0.016,
    ),
}
# Its left edge stands ~12 mm right of the line.  SOLIDWORKS centres its two
# lines (the value, and the link to note 4 on sheet 2) on this point; 6 mm
# right of 0.075 since the link names the notes' sheet (round 4).
FLOOR_TEXT_XY = (0.081, 0.059)
# Section A-A's column right of the stud bore, where both its frames stand.
_STUD_FRAME_X = _front_x(PIN_STATION) + 0.012
END_KEEP = {
    "Depth": (END_CENTER[0], _end_y(PIVOT_END_R) + 0.017),
    # Between the end view and the stock text, right of the front face.
    "PinHoleZ": (_end_x(0.0) + 0.017, _end_y(PIVOT_END_R) + 0.006),
    # Below the end view, above section B-B: the text's left end just right
    # of the hole's axis (END_CENTER x), so the leader rises from it straight
    # up to the hole and crosses no text (round 3: from x 0.372 it ran up-left
    # through the "B" of BLIND), its right end ~3 mm inside the border.
    "PinHoleDia": (0.387, 0.1593),
}
# The stock text is far wider than the 15.9 between its extension lines,
# which ran up into the "7" and the "O" of GROUND, with the dimension line
# along the text's foot (machinist review r3, rule 14). The text stands
# offset 9 mm above its dimension line, under the top border, on a leader.
STOCK_TEXT_XY = (END_CENTER[0], END_KEEP["Depth"][1] + 0.009)

# Section D-D, on its own sheet: a plan at the sheet's 2:1, on sheet 1's plan
# centre, carries cutting line D-D across the pin bore's axis, and section
# D-D, cut faces only, also 2:1, stands under it with clear air on all
# sides; it looks toward the pivot, so forward reads to the right. D, not C:
# datum C is this bore.
SHEET_NAMES = ("Arm", "Pin bore section")
PIN_SECTION_LABEL = "D"
# The middle of section D-D's cut face: under the sheet-2 plan's bottom edge
# (y 0.180) by 36 mm, over the title block (top 0.065) by 41 mm with the
# caption between.
PIN_SECTION_CENTER = (FRONT_CENTER[0], 0.125)
# The rear mouth's chamfer leg, imported into D-D with its native band
# (#2174): D-D cuts on the plane of its revolved profile, the rear face on the
# cut face's left, +Y up.  Its dimension line stands 6 mm left of the rear
# face, beside the mouth on the bore's upper wall, and its text stands off it
# on a leader in the open field left of the section, the shoulder at the
# mouth's height (section A-A's floor-depth idiom).  In A-A the mouth sits
# under the stud's frames, with no lane for the text.
PIN_SECTION_REAR_X = PIN_SECTION_CENTER[0] - THICKNESS * _S / 2000.0
_PIN_MOUTH_Y = PIN_SECTION_CENTER[1] + (
    PIN_BORE_DIA / 2.0 + PIN_MOUTH_CHAMFER / 2.0
) * _S / 1000.0
PIN_SECTION_KEEP = {"PinMouthChamfer": (PIN_SECTION_REAR_X - 0.006, _PIN_MOUTH_Y)}
# Each import phase proves the precision of exactly the dimensions its views
# import: sheet 1's front, A-A and end views every marked dimension but the
# rear mouth's leg, which only section D-D on sheet 2 imports (run
# 20261105T023327427Z: the whole-package map failed sheet 1 on
# PinMouthChamfer before D-D existed).  Together they cover the package.
PIN_SECTION_PRECISION = {name: DRAWING_PRECISION_BY_NAME[name] for name in PIN_SECTION_KEEP}
ARM_SHEET_PRECISION = {
    name: places
    for name, places in DRAWING_PRECISION_BY_NAME.items()
    if name not in PIN_SECTION_KEEP
}
# The value and its two callout lines (~14 mm tall, ~84 mm wide), the
# block's right end 10 mm short of the dimension line's stand-off.
PIN_MOUTH_TEXT_XY = (PIN_SECTION_REAR_X - 0.010 - 0.042, _PIN_MOUTH_Y + 0.006)
# The caption's top stands this far under the cut face.
_PIN_CAPTION_GAP_M = 0.006
# Half a millimetre: run 20261027T212717523Z's four moves left it 0.26 mm
# off at 0.2 (a native caption's extent does not follow a move exactly).
_CAPTION_SETTLE_M = 5e-4
_CAPTION_MOVES = 4
# Every section is drawn at the sheet's 2:1, so its caption is the name line
# alone (ASME Y14.3, rule 9: a scale equal to the sheet's restates the title
# block; draw_mg_magnifying_wheel's form).  One line is ~7 mm tall.
SECTION_CAPTION_TEXT = "<VLNAME> <VLLABEL>"
_CAPTION_ONE_LINE_MIN_M = 0.004


def dowel_group_frames() -> tuple[str, tuple[str, ...], str]:
    """The 2X dowel group's one printed frame: the key whose frame prints,
    the keys whose identical frames are hidden, and the count text above it.

    Machinist screen (clarity): identical frames were repeated on each hole
    instead of given once for the 2X group.  Every locating-hole control
    must be the same control at its own site, or one frame cannot speak for
    them all.
    """
    group = [c for c in GEOMETRIC_CONTROLS if c.key.startswith("arm_locator_")]
    if len(group) != len(LOCATOR_SITES_MM) or len(group) < 2:
        raise AssertionError("MHA-PD-18's dowel group is not one control per locating hole")
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
    return shown.key, tuple(other.key for other in hidden), f"{len(group)}X"


_ANNOTATION_VISIBLE = 1  # swAnnotationVisibilityState_e.swAnnotationVisible
_ANNOTATION_HIDDEN = 3  # swAnnotationVisibilityState_e.swAnnotationHidden
_GTOL_CALLOUT_ABOVE = 3  # swGTolTextParts_e.swGTolTextCalloutAbove


NOTE_HEIGHT = 0.0025
# Sheet 2's open lower-left field (top-left corner): under section D-D's
# caption, left of the title block, above the lower border.  Sheet 1 has no
# field the eight lines fit (round 1: they ran through its lower border).
NOTES_XY = (0.016, 0.090)


# Native tap callout: arrow on the rear entry break's own edge, text above
# the view with its top inside the upper border.  The title block's edge
# break governs the tap mouths (no band is tightened to rescue a thread):
# transgear_hanger_joints pays both at the title block's .010 and the plate
# screw still engages 1.5D, so the callout states neither break nor
# engagement.  The taps carry no frame: they are spotted and drilled through
# MHA-PD-19's screw holes at assembly with the plate doweled on (PD-19's
# holes are the master; delegated ruling 2026-11-07), and the callout's
# last line says so.
_PLATE_DRILL_R = blind_cut_dia_mm(PLATE_TAP_SPEC) / 2.0
_CALLOUT_Y = _front_y(PIVOT_END_R) + 0.0232
# Between the pivot bore's callout and the locator's, above section label B.
PLATE_CALLOUT_XY = (0.160, _CALLOUT_Y)
# Their stations print as references: the plate's holes set them.
TAP_STATION_REFERENCES = ("PlateTapStation1", "PlateTapStation2")
# The latch-pin hole's depth is its callout's (round 2: a depth is never
# deferred to a view); section A-A keeps the .33 as a reference.
LINEAR_REFERENCES = (*TAP_STATION_REFERENCES, "PinHoleDepth")
TAP_CALLOUTS = (
    (
        "plate taps",
        PLATE_TAP_STATIONS[0],
        _PLATE_DRILL_R,
        PLATE_CALLOUT_XY,
        PLATE_TAP_QUALIFIER,
    ),
)


def _overall_reference(adapter: Any, front: Any) -> None:
    overall = add_edge_dimension(
        adapter,
        front,
        p0=OVERALL_PICKS[0],
        p1=OVERALL_PICKS[1],
        text_xy=OVERALL_TEXT_XY,
        label="overall length reference",
        orientation="horizontal",
    )
    set_arc_endpoints_to_max(adapter, overall, label="overall length reference")
    display = _early_bound(overall, "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    measured_mm = abs(float(dimension.SystemValue) * 1000.0)
    if abs(measured_mm - OVERALL_LENGTH) > 1e-5:
        raise RuntimeError(
            f"overall length reference measured {measured_mm:g}, "
            f"expected {OVERALL_LENGTH:g} mm"
        )
    set_reference_dimension(
        adapter, display.GetAnnotation(), label="overall length reference"
    )
    display.SetPrecision3(DRAWING_REFERENCE_PRECISION, -1, -1, -1)
    if int(display.GetPrimaryPrecision2()) != DRAWING_REFERENCE_PRECISION:
        raise RuntimeError("overall length reference precision did not persist")


def _rear_rim(view: Any, *, radius_mm: float, station_mm: float, label: str, offset_mm: float = 0.0) -> Any:
    """The tap-drill rim nearest the rear face, by radius and station.

    Looking down a through hole both drill rims project to one circle; the
    rear one (largest z) is the one the viewer sees at the mouth's foot.
    """
    rims: list[tuple[float, Any]] = []
    nearest_miss = float("inf")
    for raw_edge in visible_view_entities(view, 1, label=f"{label} rims"):
        edge = _early_bound(raw_edge, "IEdge")
        curve = edge.GetCurve()
        if curve is None:
            continue
        curve = _early_bound(curve, "ICurve")
        if not curve.IsCircle():
            continue
        raw_params = curve.CircleParams
        if raw_params is None:
            raise RuntimeError(f"{label}: native circle parameters are NULL")
        params = tuple(float(value) * 1000.0 for value in raw_params)
        if len(params) != 7 or not all(map(math.isfinite, params)):
            raise RuntimeError(f"{label}: native circle parameters are not seven finite values")
        miss = abs(params[6] - radius_mm) + abs(params[0] - station_mm) + abs(params[1] - offset_mm)
        nearest_miss = min(nearest_miss, miss)
        if miss <= 0.02:
            rims.append((params[2], edge))
    if not rims:
        raise RuntimeError(
            f"{label}: no drill rim R{radius_mm:.3f} at x {station_mm:.3f}; "
            f"nearest circle misses by {nearest_miss:.3f} mm"
        )
    return max(rims, key=lambda item: item[0])[1]


def _rim_point(
    adapter: Any, view: Any, *, station_mm: float, radius_mm: float,
    bearing_deg: float, label: str, offset_mm: float = 0.0,
) -> tuple[float, float]:
    """Sheet point on a bore's rear rim at a model bearing."""
    angle = math.radians(bearing_deg)
    return model_point_in_view(
        adapter, view,
        (
            (station_mm + radius_mm * math.cos(angle)) / 1000.0,
            (offset_mm + radius_mm * math.sin(angle)) / 1000.0,
            THICKNESS / 1000.0,
        ),
        label=label,
    )


def _wall_point(
    adapter: Any, view: Any, *, x_mm: float, z_mm: float, label: str
) -> tuple[float, float]:
    """Sheet point on a centreline hole's wall in section A-A."""
    return model_point_in_view(
        adapter, view, (x_mm / 1000.0, 0.0, z_mm / 1000.0), label=label
    )


# The dowel group's position frame stands in section B-B, which cuts both
# sockets on their axes, right of the socket mouths on its socket's side of
# the arm's centre (machinist review: in the front view frames sat inside
# the silhouette).  Its leader enters its socket's mouth and lands on the
# wall nearer the centre 1 mm in, as the stud's frames do in section A-A.
# Each socket keeps a placement (``project_part_pmi`` projects every
# control); the second's frame is hidden (``_one_frame_per_dowel_group``).
_LOCATOR_MOUTH_X = LOCATOR_SECTION_CENTER[0] + THICKNESS / 2.0 * _S / 1000.0
_LOCATOR_FRAME_GAP = 0.006
_LOCATOR_FRAME_RISE = 0.0025
_FRAME_HALF_HEIGHT = 0.00345


def _locator_frame_xy(offset_mm: float) -> tuple[float, float]:
    """Top-left of a socket's position frame in section B-B."""
    side = math.copysign(1.0, offset_mm)
    centre_y = (
        LOCATOR_SECTION_CENTER[1] + offset_mm * _S / 1000.0 + side * _LOCATOR_FRAME_RISE
    )
    return (_LOCATOR_MOUTH_X + _LOCATOR_FRAME_GAP, centre_y + _FRAME_HALF_HEIGHT)


def tap_callout_definitions(definitions: dict[int, str], qualifier: str) -> dict[int, str]:
    """Drop the title-block thread class from the thread compartment and put
    the qualifier line under it; every other compartment and every
    associative Hole Wizard variable stays."""
    if set(definitions) != {5, 6, 7, 8}:
        raise RuntimeError(f"unexpected tap callout parts: {definitions!r}")
    thread_parts = [
        part for part, text in definitions.items() if "<hw-threadclass>" in text.lower()
    ]
    if len(thread_parts) != 1:
        raise RuntimeError(
            f"tap thread line is not in one callout part: {definitions!r}"
        )
    part = thread_parts[0]
    without_class = re.sub(
        r"\s*(?:-\s*)?<hw-threadclass>\s*", " ", definitions[part], flags=re.IGNORECASE
    )
    without_class = re.sub(r" {2,}", " ", without_class).rstrip()
    updated = dict(definitions)
    updated[part] = f"{without_class}\n{qualifier}"
    return updated


def _set_tap_callout_text(display: Any, qualifier: str, *, label: str) -> None:
    """Write the callout's definitions; IDisplayDimension::SetText is void,
    so the definitions read back (parts 5-8) and the resolved text (parts
    1-4) ending in the qualifier prove it took."""
    native = _early_bound(display, "IDisplayDimension")
    definitions = {part: str(native.GetText(part) or "") for part in (5, 6, 7, 8)}
    updated = tap_callout_definitions(definitions, qualifier)
    for definition_part, writable_part in ((5, 1), (6, 2), (7, 3), (8, 4)):
        if updated[definition_part] != definitions[definition_part]:
            native.SetText(writable_part, updated[definition_part])
    persisted = {part: str(native.GetText(part) or "") for part in (5, 6, 7, 8)}
    resolved = {part: str(native.GetText(part) or "") for part in (1, 2, 3, 4)}
    if persisted != updated or not any(
        text.rstrip().endswith(qualifier) for text in resolved.values()
    ):
        raise RuntimeError(
            f"{label} callout text did not persist: "
            f"definitions={persisted!r}, resolved={resolved!r}"
        )


def _reference_linear_dimensions(adapter: Any, annotations: list[Any]) -> None:
    """Print the plate-tap stations and the latch-pin hole's depth in
    parentheses, as references: the taps are transferred from MHA-PD-19's
    holes, so the stations control nothing, and the depth is the hole
    callout's.  Linear dimensions, so no diameter glyph
    (``set_reference_dimension``)."""
    found = set()
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name in LINEAR_REFERENCES:
            set_reference_dimension(adapter, annotation, label=name)
            found.add(name)
    missing = set(LINEAR_REFERENCES) - found
    if missing:
        raise RuntimeError(f"linear references never reached the sheet: {sorted(missing)}")


@_telemetry.traced("drawing.transgear_arm.dowel_group_frame")
def _one_frame_per_dowel_group(adapter: Any, frames: dict[str, Any]) -> None:
    """One frame for the 2X dowel group (``dowel_group_frames``): the other
    sockets' identical frames are hidden on the sheet
    (``IAnnotation::Visible`` = swAnnotationHidden, drawing-local), and the
    shown frame carries the count above it
    (``IGtol::SetText(swGTolTextCalloutAbove)``).  After a rebuild each is
    read back: hidden frames hidden, the shown frame visible with its count;
    anything else fails the build."""
    shown_key, hidden_keys, count = dowel_group_frames()
    hidden = {key: _early_bound(frames[key], "IAnnotation") for key in hidden_keys}
    for annotation in hidden.values():
        annotation.Visible = _ANNOTATION_HIDDEN
    shown = _early_bound(frames[shown_key], "IAnnotation")
    gtol = _early_bound(shown.GetSpecificAnnotation(), "IGtol")
    if not gtol.SetText(_GTOL_CALLOUT_ABOVE, count):
        raise RuntimeError(f"{shown_key}: the dowel group's {count} was refused")
    rebuild_drawing(adapter, label="dowel group frame")
    for key, annotation in hidden.items():
        if int(annotation.Visible) != _ANNOTATION_HIDDEN:
            raise RuntimeError(f"{key}: the repeated dowel frame did not stay hidden")
    above = str(gtol.GetText(_GTOL_CALLOUT_ABOVE) or "")
    if int(shown.Visible) != _ANNOTATION_VISIBLE or above != count:
        raise RuntimeError(
            f"{shown_key}: the dowel group's frame reads visible={shown.Visible!r}, "
            f"above={above!r}, not {count!r}"
        )
    _telemetry.info(f"dowel group: {shown_key} prints {count}; hidden {sorted(hidden)}")


def _set_stock_text(adapter: Any, annotations: list[Any]) -> None:
    """Print the thickness as the stock's: "5/16 (.3125) GROUND STOCK REF".

    The arm is cut from 5/16 ground flat stock with its faces as supplied, so
    the stock's tolerance governs the thickness, not the .XX row.  Prefix and
    suffix, not a whole-text override: the value between them stays the
    model's dimension at its model-owned places, and the parentheses mark it
    as reference (the rocker thrust washer's idiom). The text stands off its
    dimension line on a leader (``STOCK_TEXT_XY``), clear of both extension
    lines.
    """
    for annotation in annotations:
        if dimension_name(adapter, annotation) != "Depth":
            continue
        annotation = _early_bound(annotation, "IAnnotation")
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        if abs(float(dimension.SystemValue) - THICKNESS / 1000.0) > 1e-9:
            raise RuntimeError(
                f"arm thickness {float(dimension.SystemValue)!r} m "
                f"is not the stock's {THICKNESS} mm"
            )
        display.SetText(1, STOCK_TEXT_PREFIX)  # swDimensionTextPrefix
        display.SetText(2, STOCK_TEXT_SUFFIX)  # swDimensionTextSuffix
        readback = (str(display.GetText(1) or ""), str(display.GetText(2) or ""))
        if readback != (STOCK_TEXT_PREFIX, STOCK_TEXT_SUFFIX):
            raise RuntimeError(f"arm stock text did not persist: {readback!r}")
        offset_dimension_text(adapter, [annotation], {"Depth": STOCK_TEXT_XY})
        return
    raise RuntimeError("arm end view has no Depth dimension to label")


_ARROWS_OUTSIDE = 1  # swDimensionArrowsSide_e.swDimArrowsOutside


def _end_radius_to_arc(adapter: Any, annotations: list[Any]) -> None:
    """R.49's leader runs from its text to the end round and stops there.

    Machinist review r3 (clarity): left to the document's style, its line
    ran on to the pivot centre and met the Ø.1935 bore's diameter leader
    there.  Arrow outside, no solid leader (draw_dt_crank_handle's radius
    style), so it never reaches the bore.
    """
    for annotation in annotations:
        if dimension_name(adapter, annotation) != "PivotEndR":
            continue
        display = _early_bound(
            _early_bound(annotation, "IAnnotation").GetSpecificAnnotation(), "IDisplayDimension"
        )
        display.ArcExtensionLineOrOppositeSide = False
        display.ArrowSide = _ARROWS_OUTSIDE
        display.SolidLeader = False
        if (
            bool(display.Diametric)
            or bool(display.ArcExtensionLineOrOppositeSide)
            or int(display.ArrowSide) != _ARROWS_OUTSIDE
            or bool(display.SolidLeader)
        ):
            raise RuntimeError("PivotEndR kept its leader to the pivot centre")
        return
    raise RuntimeError("arm plan view has no PivotEndR dimension to style")


@_telemetry.traced("drawing.transgear_arm.pin_bore_section")
def _pin_bore_section(adapter: Any, plan: Any) -> Any:
    """Section D-D on its own sheet: the arm cut across the pin bore's axis
    in that sheet's plan, cut faces only, at the sheet's 2:1, looking toward
    the pivot; its cut face centres on ``PIN_SECTION_CENTER``."""
    pin_x = _front_x(PIN_STATION)
    half = edge_half_width(PIN_STATION)
    section = create_section_view(
        adapter, plan,
        line_start=(pin_x, _front_y(half) + SECTION_LINE_OVERRUN),
        # Further out below: there the arm's lower edge falls toward the
        # pivot, under the letter left of the arrow (run 20261027T201320296Z:
        # it crossed the D at 5 mm).
        line_end=(pin_x, _front_y(-half) - _PIN_SECTION_LOWER_OVERRUN),
        view_xy=PIN_SECTION_CENTER, section_label=PIN_SECTION_LABEL,
        scale=VIEW_SCALE, label="pin bore section",
    )
    native = _early_bound(section, "IView")
    cut = _early_bound(native.GetSection(), "IDrSection")
    # R2026x declares SetDisplayOnlySurfaceCut as a void setter; only its
    # dedicated bool getter may be truth-tested.
    cut.SetDisplayOnlySurfaceCut(True)
    rebuild_drawing(adapter, label="section D-D cut face")
    ratio = tuple(float(value) for value in native.ScaleRatio)
    if not bool(cut.GetDisplayOnlySurfaceCut()) or ratio != tuple(
        float(value) for value in VIEW_SCALE
    ):
        raise RuntimeError(f"section D-D is not a {VIEW_SCALE!r} cut-face section: {ratio!r}")
    for attempt in range(4):
        native.UpdateViewDisplayGeometry()
        rear, front_face = model_points_in_view(
            adapter, section,
            tuple((PIN_STATION / 1000.0, 0.0, z / 1000.0) for z in (THICKNESS, 0.0)),
            label=f"section D-D cut face, pass {attempt}",
            names=("rear face", "face A"),
        )
        centre = ((rear[0] + front_face[0]) / 2.0, front_face[1])
        miss = (PIN_SECTION_CENTER[0] - centre[0], PIN_SECTION_CENTER[1] - centre[1])
        if math.hypot(*miss) <= 1e-4:
            break
        position = tuple(float(value) for value in native.Position)
        if not native.SetViewPosition(
            double_array([position[0] + miss[0], position[1] + miss[1]]), False
        ):
            raise RuntimeError("failed to re-centre section D-D")
        rebuild_drawing(adapter, label="section D-D re-centred")
    else:
        raise RuntimeError(f"section D-D cut face centred at {centre!r}, not {PIN_SECTION_CENTER!r}")
    # Looking toward the pivot, the rear face reads left of face A, where
    # PIN_SECTION_KEEP stands the mouth's leg.
    if not rear[0] < front_face[0]:
        raise RuntimeError(f"section D-D does not read rear-left: {rear!r}, {front_face!r}")
    return section


def _section_caption(view: Any, label: str) -> tuple[Any, str]:
    """A section's native caption note and its linked view-label fields."""
    captions = []
    for raw_note in _early_bound(view, "IView").GetNotes() or ():
        note = _early_bound(raw_note, "INote")
        linked_text = str(note.PropertyLinkedText or "")
        if all(token in linked_text for token in ("<VLNAME>", "<VLLABEL>")):
            captions.append((note, linked_text))
    if len(captions) != 1:
        raise RuntimeError(f"expected one native section {label} caption, found {len(captions)}")
    return captions[0]


@_telemetry.traced("drawing.transgear_arm.section_captions_without_scale")
def _section_captions_without_scale(adapter: Any, sections: dict[str, Any]) -> None:
    """Give each section's native caption its name and letters only (its
    scale is the sheet's), so A-A, B-B and D-D read alike; B-B stacks them
    (SECTION_CAPTION_TEXTS).  Line breaks read back as CR LF."""
    for label, view in sections.items():
        note, linked_text = _section_caption(view, label)
        if linked_text.replace("\r", "") != SECTION_CAPTION_TEXTS[label]:
            note.PropertyLinkedText = SECTION_CAPTION_TEXTS[label]
    rebuild_drawing(adapter, label="section captions without scale")
    for label, view in sections.items():
        if _section_caption(view, label)[1].replace("\r", "") != SECTION_CAPTION_TEXTS[label]:
            raise RuntimeError(f"section {label} caption without scale did not persist")


# Each section's caption hangs centred under its cut, its top this far below
# the cut face (round 4: SolidWorks left B-B's caption 17 mm under its view,
# pressed against section A-A's right end beside A-A's (.33), and A-A's
# caption down against the title block's top edge).  B-B's caption stacks its
# name over its letters, narrow enough to stand ~11 mm clear of A-A's end.
_SECTION_CAPTION_GAP_M = {"A-A": 0.004, "B-B": 0.004, "D-D": _PIN_CAPTION_GAP_M}
SECTION_CAPTION_TEXTS = {
    "A-A": SECTION_CAPTION_TEXT,
    "B-B": "<VLNAME>\n<VLLABEL>",
    "D-D": SECTION_CAPTION_TEXT,
}


def section_caption_targets() -> dict[str, tuple[int, tuple[float, float]]]:
    """Each section's sheet index and its caption's top-centre target."""
    halves = {
        "A-A": (0, SECTION_CENTER, THICKNESS / 2.0),
        "B-B": (0, LOCATOR_SECTION_CENTER, edge_half_width(LOCATOR_SITES_MM[0][0])),
        "D-D": (1, PIN_SECTION_CENTER, edge_half_width(PIN_STATION)),
    }
    return {
        label: (
            sheet,
            (centre[0], centre[1] - half_mm * _S / 1000.0 - _SECTION_CAPTION_GAP_M[label]),
        )
        for label, (sheet, centre, half_mm) in halves.items()
    }


@_telemetry.traced("drawing.transgear_arm.section_caption_settled", label_param="label")
def _section_caption_settled(adapter: Any, section: Any, *, label: str) -> None:
    """After finalize_drawing's last sheet-scale reset and rebuild: hang a
    section's caption, centred, under its cut face (bounded measured moves,
    then one final check of the resolved extent), inside the sheet, with its
    linked name line. ``INote.GetText`` reads the linked fields blank even
    here (run 20261027T215106763Z: ' \\r\\n '), so the resolved text is
    evidenced by its extent: at least one line tall."""
    sheet, target = section_caption_targets()[label]
    if not _early_bound(adapter.currentModel, "IDrawingDoc").ActivateSheet(SHEET_NAMES[sheet]):
        raise RuntimeError(f"cannot activate section {label}'s sheet")
    note, linked_text = _section_caption(section, label)

    def miss() -> tuple[tuple[float, ...], tuple[float, float]]:
        extent = tuple(float(value) for value in note.GetExtent())
        return extent, (target[0] - (extent[0] + extent[3]) / 2.0, target[1] - extent[4])

    for move in range(_CAPTION_MOVES):
        extent, error = miss()
        _telemetry.info(f"section {label} caption move {move}: extent {extent}, off {error}")
        if max(map(abs, error)) < _CAPTION_SETTLE_M:
            break
        move_annotation(adapter, note.GetAnnotation(), *error, label=f"section {label} caption")
    extent, error = miss()
    if max(map(abs, error)) >= _CAPTION_SETTLE_M:
        raise RuntimeError(f"section {label} caption stands at {extent}, its top centre asked at {target}")
    require_inside(f"section {label} caption", (extent[0], extent[1], extent[3], extent[4]), sheet_region(adapter))
    if str(note.PropertyLinkedText or "") != linked_text or extent[4] - extent[1] < _CAPTION_ONE_LINE_MIN_M:
        raise RuntimeError(f"section {label} caption {linked_text!r} resolved to {extent}")
    _telemetry.info(f"section {label} caption at {extent}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open transgear-arm source", await adapter.open_model(str(SOURCE)))
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
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="transgear arm package")
    ddoc = _early_bound(drawing_model, "IDrawingDoc")
    if not ddoc.ActivateSheet(SHEET_NAMES[0]):
        raise RuntimeError("cannot activate the arm sheet")
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Transgear Arm Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "transgear arm; machined steel bar",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    section = create_section_view(
        adapter,
        front,
        line_start=SECTION_LINE[0],
        line_end=SECTION_LINE[1],
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=VIEW_SCALE,
        label="arm centreline section",
    )
    locator_x = _front_x(LOCATOR_SITES_MM[0][0])
    locator_section = create_section_view(
        adapter, front,
        line_start=(locator_x, _front_y(-PIVOT_END_R) - SECTION_LINE_OVERRUN),
        line_end=(locator_x, _front_y(PIVOT_END_R) + SECTION_LINE_OVERRUN),
        view_xy=LOCATOR_SECTION_CENTER, section_label="B", scale=VIEW_SCALE,
        label="matched locating sockets transverse section",
    )
    end = place_view(adapter, str(SOURCE), "*Right", *END_CENTER, scale=VIEW_SCALE)
    for view in (front, section, locator_section, end):
        set_hidden_lines_removed(adapter, view)

    annotations = [
        *hidden_sketches.curate_view_dimensions(
            adapter,
            front,
            keep=FRONT_KEEP,
            view_label="front",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *hidden_sketches.curate_view_dimensions(
            adapter,
            section,
            keep=SECTION_KEEP,
            view_label="section A-A",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *hidden_sketches.curate_view_dimensions(
            adapter,
            end,
            keep=END_KEEP,
            view_label="end",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    # Decimal places and the explicit bands are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, ARM_SHEET_PRECISION)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    set_reference_dimensions(adapter, annotations, ("PivotBoreDia",))
    _reference_linear_dimensions(adapter, annotations)
    _set_stock_text(adapter, annotations)
    _end_radius_to_arc(adapter, annotations)
    offset_dimension_text(adapter, annotations, {"FloorDepth": FLOOR_TEXT_XY})
    # Model-owned circular zones and actual feature datums. BASIC stations
    # are imported from the part; no drawing-only coordinate tolerances, and
    # no projected zone (delegated ruling 2026-11-07, rule 26).
    bore_dia = {
        datum.letter: datum.face.diameter_mm
        for datum in PART_DATUMS if datum.letter != "A"
    }
    pin_r = bore_dia["C"] / 2.0
    placements = {
        # Between the counterbore's callout and the stud's frames.
        "datum:A": PmiDrawingPlacement(
            section, (_front_x(56.0), SECTION_CENTER[1] + 0.018),
            attachment_xy=model_point_in_view(
                adapter, section, (0.056, 0.0, 0.0), label="arm front datum",
            ),
        ),
        # Datum tags on a bore are picked by a SHEET POINT on the rim
        # (solidworks-drawing-layout-tuning.md section h): an edge-object
        # pick leaves the tag at its default drop beside the bore, and run 5
        # read datum B 35.5 mm from its request.  The point is projected
        # from the rim's model position, on the bearing toward the tag.
        "datum:B": PmiDrawingPlacement(
            front, (_front_x(0.0) - 0.024, FRONT_CENTER[1] + 0.020),
            attachment_xy=_rim_point(
                adapter, front, station_mm=0.0, radius_mm=bore_dia["B"] / 2.0,
                bearing_deg=135.0, label="datum B pivot bore rim",
            ),
        ),
        "datum:C": PmiDrawingPlacement(
            front, (_front_x(PIN_STATION) + 0.018, FRONT_CENTER[1] - 0.009),
            attachment_xy=_rim_point(
                adapter, front, station_mm=PIN_STATION, radius_mm=bore_dia["C"] / 2.0,
                bearing_deg=-27.0, label="datum C pin bore rim",
            ),
        ),
        # The stud's two frames stand stacked in section A-A right of its
        # bore, the locating holes' callout filling the front view's band
        # above the arm.  Both leaders enter the bore's mouth from the right
        # and land on its far wall, the upper frame's higher, so they never
        # cross.
        "feed_stud_position": PmiDrawingPlacement(
            section, (_STUD_FRAME_X, SECTION_CENTER[1] + 0.028),
            attachment_xy=_wall_point(
                adapter, section, x_mm=PIN_STATION - pin_r, z_mm=1.0,
                label="feed stud position pin bore wall",
            ),
        ),
        # Plain ⊥ Ø.001 to A over the bore, under the position frame.
        "feed_stud_perpendicularity": PmiDrawingPlacement(
            section, (_STUD_FRAME_X, SECTION_CENTER[1] + 0.0195),
            attachment_xy=_wall_point(
                adapter, section, x_mm=PIN_STATION - pin_r, z_mm=2.5,
                label="feed stud perpendicularity pin bore wall",
            ),
        ),
        **{
            f"arm_locator_{index}_position": PmiDrawingPlacement(
                locator_section, _locator_frame_xy(y),
                attachment_xy=model_point_in_view(
                    adapter, locator_section,
                    (
                        x / 1000.0,
                        (y - math.copysign(LOCATOR_HOLE_DIA_MM / 2.0, y)) / 1000.0,
                        (THICKNESS - 1.0) / 1000.0,
                    ),
                    label=f"arm locator {index} inner wall",
                ),
            ) for index, (x, y) in enumerate(LOCATOR_SITES_MM, 1)
        },
    }
    frames = project_part_pmi(
        adapter, placements=placements, datums=PART_DATUMS,
        controls=GEOMETRIC_CONTROLS, label="transgear arm locating frame",
    )
    _one_frame_per_dowel_group(adapter, frames)
    _overall_reference(adapter, front)
    for view, label in ((front, "front"), (end, "end")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME centre marks to the {label} view")

    # Thread and tap drill ride the native callouts; the class is the title
    # block's; the last line says the taps are transferred from MHA-PD-19.
    for label, station, radius, callout_xy, qualifier in TAP_CALLOUTS:
        callout = add_native_hole_callout(
            adapter,
            front,
            edge=_rear_rim(front, radius_mm=radius, station_mm=station, label=label),
            callout_xy=callout_xy,
            label=label,
        )
        _set_tap_callout_text(callout, qualifier, label=label)
        set_hole_callout_precision(callout, {"hw-thrutapdrldia": 3}, label=label)

    # Sheet 2: the pin bore's rear mouth in section D-D, cut from a plan on
    # sheet 1's plan centre.
    if not ddoc.ActivateSheet(SHEET_NAMES[1]):
        raise RuntimeError("cannot activate the pin-bore section sheet")
    pin_plan = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    set_hidden_lines_removed(adapter, pin_plan)
    pin_section = _pin_bore_section(adapter, pin_plan)
    set_hidden_lines_removed(adapter, pin_section)
    mouth = hidden_sketches.curate_view_dimensions(
        adapter,
        pin_section,
        keep=PIN_SECTION_KEEP,
        view_label="section D-D",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    assert_imported_precision(adapter, mouth, PIN_SECTION_PRECISION)
    set_dimension_callouts(adapter, mouth, {"PinMouthChamfer": PIN_MOUTH_CALLOUT})
    offset_dimension_text(adapter, mouth, {"PinMouthChamfer": PIN_MOUTH_TEXT_XY})
    _section_captions_without_scale(
        adapter, {"A-A": section, "B-B": locator_section, "D-D": pin_section}
    )
    if not auto_center_marks(adapter, pin_plan, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME centre marks to the pin-bore section plan")
    iso = place_view(
        adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_VIEW_SCALE
    )
    set_hidden_lines_removed(adapter, iso)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    # The fit notes the callouts link to, on sheet 2's open lower-left field
    # (round 1: on sheet 1 they ran through the lower border).
    ddoc.ActivateView("")
    if add_note(adapter, NOTES_TEXT, *NOTES_XY, height=NOTE_HEIGHT) is None:
        raise RuntimeError("failed to add the arm's fit notes")
    if not ddoc.ActivateSheet(SHEET_NAMES[0]):
        raise RuntimeError("cannot return to the arm sheet")

    artefacts = await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Transgear Arm Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        expected_sheet_names=SHEET_NAMES,
        sheet_layouts={name: SPEC.layout for name in SHEET_NAMES},
        sheet_scales={name: SHEET_SCALE for name in SHEET_NAMES},
        # SolidWorks pins its own "... Tapped Hole" note to each plan (sheet
        # 1's and sheet 2's: run 20261027T210532641Z removed 2) once a tap
        # carries a hole callout; the plate-tap callout already states the
        # thread and drill.
        redundant_note_substrings=("Tapped Hole",),
        expected_redundant_notes=len(TAP_CALLOUTS) * len(SHEET_NAMES),
        settled_checks=tuple(
            lambda view=view, label=label: _section_caption_settled(adapter, view, label=label)
            for label, view in (("A-A", section), ("B-B", locator_section), ("D-D", pin_section))
        ),
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
