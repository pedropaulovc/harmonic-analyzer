r"""Create the manufacturing drawing for the transgear arm (MHA-PD-18).

The principal view is ``*Front``, looking at the REAR face: the outline (the
pivot radius, the tip station and the end-face width), the pivot bore, the
MHA-PD-23 pin's reamed press bore, the plate-tap callout with its qualifier
lines, and the hole stations from the pivot (the blanked
``StationReference`` sketch, shown in this view only). The plate-tap stations
follow the reducer's knob bore through ``pd_transgear_arm_geometry``; neither
their imported dimensions nor the annotation picks fix a previous centre.
Section A-A cuts it on the centreline -- through the pivot, every hole and the
latch-pin hole -- so the rear spot face's diameter, its floor from the FRONT
face (the pivot head's end play) and the latch-pin hole's depth print on
solid cut edges.  The end view (``*Right``, the square end) carries the
thickness (the ground stock's, printed as a reference to it) and the
latch-pin hole's reamed size, its height and the press of the pin to the
hole floor.  The matched locating holes run through from the rear face the
front view looks at, so their stations, size and position frames print there
and in section B-B, which cuts them on their axes.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from dataclasses import dataclass
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
)

import _config
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
from _native_projected_zone import require_saved_projected_gtols
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
import _transgear_zone_line as zone_lines
from pd_transgear_arm_geometry import (
    LOCATOR_SITES_MM,
    LOCATOR_HOLE_DIA_MM,
    PIN_HOLE_DEPTH,
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
    FLOOR_DEPTH_CALLOUT,
    ISO_VIEW_SCALE,
    OVERALL_LENGTH,
    PIN_BORE_CALLOUT,
    LOCATOR_CALLOUT,
    PIN_HOLE_CALLOUT,
    PIVOT_BORE_CALLOUT,
    PLATE_TAP_EDGE_BREAK_CALLOUT,
    PROJECTED_ZONE_DIRECTION,
    SPOT_FACE_CALLOUT,
    STOCK_TEXT_PREFIX,
    STOCK_TEXT_SUFFIX,
    engagement_line,
)
import transgear_hanger_joints as joints
from pd_paper_drive_assembly_steps import knob_setting_ref


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
# On sheet 1 under section A-A it crowded A-A's zone frames, the floor
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
    # Six callout lines under the value: the block centres low enough that
    # its top stays inside the upper border, right of the tap callout.
    "LocatorDia1": (0.262, _front_y(PIVOT_END_R) + 0.0157),
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
    # Half a millimetre higher than 0.019: the plate taps' 14.7 height
    # arrow ends on face A under its last line (run
    # 20261027T180656347Z: 1.9 mm, under the 2.0 arrow clearance).
    "SpotFaceDia": (0.1295, SECTION_CENTER[1] + 0.0196),
    "FloorDepth": (_front_x(-PIVOT_END_R) - 0.004, SECTION_CENTER[1] - 0.022),
    # 4 mm higher than 0.020: its dimension line stood 1.8 mm over the
    # title block (review of 2ac1bdb28).
    "PinHoleDepth": (
        _front_x(TIP_STATION - PIN_HOLE_DEPTH / 2.0),
        SECTION_CENTER[1] - 0.016,
    ),
}
# Its left edge stands 12 mm right of the line, so the leader keeps 2 mm
# off "SETS PRELOAD OF", the widest line; its top 2.7 mm under the plate
# tap's frame (both 3 mm lower than before run 20261028T134941938Z).
FLOOR_TEXT_XY = (0.075, 0.052)
# The top of both plate-tap frames in section A-A, 4.4 mm under its rear
# face: the counterbore's extension lines run to its revolved profile's end,
# 2 mm past that face, and at 1.5 mm under it they ran into tap 1's frame
# (machinist review of eecbf880d, r1/r2 gating clarity: one struck its
# "Ø0.050 (P)" cell). Now 2.5 mm under their ends.
_TAP_FRAME_TOP_Y = SECTION_CENTER[1] - 0.0124
# Section A-A's column right of the stud bore, where both its frames stand.
_STUD_FRAME_X = _front_x(PIN_STATION) + 0.012
END_KEEP = {
    "Depth": (END_CENTER[0], _end_y(PIVOT_END_R) + 0.017),
    # Between the end view and the stock text, right of the front face.
    "PinHoleZ": (_end_x(0.0) + 0.017, _end_y(PIVOT_END_R) + 0.006),
    # Below the end view, above section B-B, right edge inside the border;
    # half a line lower than the 4-line block so its top stays put with the
    # ligament fact as a fifth line.
    "PinHoleDia": (0.384, 0.1593),
}
# The stock text is far wider than the 15.9 between its extension lines,
# which ran up into the "7" and the "O" of GROUND, with the dimension line
# along the text's foot (machinist review r3, rule 14). The text stands
# offset 9 mm above its dimension line, under the top border, on a leader.
STOCK_TEXT_XY = (END_CENTER[0], END_KEEP["Depth"][1] + 0.009)

# Each projected zone's heavy chain line, from front face A (z = 0) through
# its height on the side ``PROJECTED_ZONE_DIRECTION`` names, in the view
# that shows its hole cut on the axis.
#
# The plate taps' zones run rearward, down section A-A, on their axes
# through the holes' open cut; each tap frame's leader lands on the near
# wall at the mouth, so none crosses its line. Both are one height the same
# way, so one dimension carries both ("2X"). Its dimension line runs inside
# tap 1's hole beside the chain line, so both of its arrows sit on the
# zone's own ends, face A and the far end (review of d5d1298b0, r3: between
# the taps the line started in the hatch and the zone read as starting at the
# rear face); its value stands below the section, between the taps, on a
# leader.
#
# The pin bore's zone runs forward 32.6 (65 mm at 2:1): up section A-A it
# crossed the plan's 68.815, 128.90 and (141.4) dimension lines (review of
# d5d1298b0, gating, r1/r2), and at 1:1 in sheet 1's lower-left corner it
# read as shrunk to fit (review of 2ac1bdb28, gating, rule 15). It has its
# own sheet: a plan at the sheet's 2:1, on sheet 1's plan centre, carries
# cutting line D-D across the bore's axis, and section D-D, cut faces only,
# also 2:1, stands under it with clear air on all sides; it looks toward
# the pivot, so forward reads to the right. D, not C: datum C is this bore.
@dataclass(frozen=True)
class ZoneChain:
    view: str  # "A-A" or "D-D"
    x_mm: float  # model X of the line, on the hole's axis
    # Sheet offset of the height's dimension line from the chain's midpoint;
    # None: another zone's dimension carries this one ("2X").
    dimension: tuple[float, float] | None
    # Where the value stands off its dimension line on a leader, if it does.
    text_xy: tuple[float, float] | None = None


PROJECTED_ZONE_CHAINS: dict[str, ZoneChain] = {
    "plate_tap_1_position": ZoneChain(
        "A-A", PLATE_TAP_STATIONS[0], (0.0015, 0.0),
        (
            (_front_x(PLATE_TAP_STATIONS[0]) + _front_x(PLATE_TAP_STATIONS[1])) / 2.0,
            # Beside tap 1's frame shoulder (y SECTION_CENTER - 0.0159),
            # which ends left of the tap's hole, 9 mm short of the text's
            # left end; the text stands right of the hole (since #2034 moved
            # the taps 12 mm left on the sheet, the old shoulder reached over
            # the text's left end: run 20261028T064655627Z, leader-through-text).
            SECTION_CENTER[1] - 0.0165,
        ),
    ),
    "plate_tap_2_position": ZoneChain("A-A", PLATE_TAP_STATIONS[1], None),
    "feed_stud_projected_axis": ZoneChain("D-D", PIN_STATION, (0.0, 0.008)),
}
SHEET_NAMES = ("Arm", "Pin bore projected zone")
PIN_SECTION_LABEL = "D"
# The middle of section D-D's cut face and the pin bore's chain line
# together: under the sheet-2 plan's bottom edge (y 0.180) by 36 mm, over the
# title block (top 0.065) by 41 mm with the caption between.
PIN_SECTION_ZONE_CENTER = (FRONT_CENTER[0], 0.125)
# The caption's top stands this far under the cut face.
_PIN_CAPTION_GAP_M = 0.006
# Half a millimetre: run 20261027T212717523Z's four moves left it 0.26 mm
# off at 0.2 (a native caption's extent does not follow a move exactly).
_CAPTION_SETTLE_M = 5e-4
_CAPTION_MOVES = 4
# A two-line caption (name over scale) is 16.2 mm tall; one line is ~7.
_CAPTION_TWO_LINES_M = 0.012


def projected_zone_count(key: str) -> int:
    """How many drawn zones ``key``'s height dimension carries: its own and
    every undimensioned zone of the same height run the same way."""
    height = {c.key: c.projected_zone_height_mm for c in GEOMETRIC_CONTROLS}

    def same(other: str) -> bool:
        return (
            height[other] == height[key]
            and PROJECTED_ZONE_DIRECTION[other] == PROJECTED_ZONE_DIRECTION[key]
        )

    return 1 + sum(
        1 for other, chain in PROJECTED_ZONE_CHAINS.items()
        if chain.dimension is None and same(other)
    )


_SW_TEXT_PREFIX = 1  # swDimensionTextPrefix
_SW_TEXT_SUFFIX = 2  # swDimensionTextSuffix
_SW_DIMENSION_DRIVEN = 1  # swDimensionDrivenState_e.swDimensionDriven


# The match-drill rides the locating holes' own callout, pointing at the
# assembly view whose native S-K dimension sets the pair's centres; the
# callout carries no value of its own (rule 7; #1388 policy).
_PLATE = _config.parts("pd-transgear-arm-plate")
LOCATOR_CALLOUT_TEXT = "\n".join((
    LOCATOR_CALLOUT,
    f"MATCH-DRILL WITH ARM PLATE {_PLATE['number']}",
    f"AT ASSEMBLY, {knob_setting_ref()}",
))

DIMENSION_CALLOUTS = {
    "PivotBoreDia": PIVOT_BORE_CALLOUT,
    "PinBoreDia": PIN_BORE_CALLOUT,
    "SpotFaceDia": SPOT_FACE_CALLOUT,
    "FloorDepth": FLOOR_DEPTH_CALLOUT,
    "PinHoleDia": PIN_HOLE_CALLOUT,
    "LocatorDia1": LOCATOR_CALLOUT_TEXT,
}

# Native tap callout: arrow on the rear entry break's own edge, text above
# the view with its top inside the upper border. It carries the ordinary
# entry/exit edge-break limit and the mating cut screw's worst-case full-
# thread engagement. The joint source pays entry loss and the overlapping
# exit/cut-end loss separately; screws do not locate or centre this joint.
_PLATE_DRILL_R = blind_cut_dia_mm(PLATE_TAP_SPEC) / 2.0
_CALLOUT_Y = _front_y(PIVOT_END_R) + 0.0232
# Between the pivot bore's callout and the locator's, above section label B.
PLATE_CALLOUT_XY = (0.160, _CALLOUT_Y)
PLATE_TAP_QUALIFIER = "\n".join(
    (
        PLATE_TAP_EDGE_BREAK_CALLOUT,
        engagement_line(
            joints.PLATE_SCREW_ENGAGEMENT_WORST, joints.PLATE_SCREW_ENGAGEMENT_WORST_D
        ),
    )
)
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


# Position frames on the locating sockets stand in section B-B, which cuts
# both on their axes, right of the socket mouths and each on its socket's side
# of the arm's centre (machinist review: in the front view they sat inside
# the silhouette).  Each leader enters its socket's mouth and lands on the
# wall nearer the centre 1 mm in, as section A-A's tap frames do.
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


def tap_callout_definitions(
    definitions: dict[int, str], qualifier: str
) -> dict[int, str]:
    """Drop the title-block thread class from the thread compartment and
    append the qualifier lines under it; every other compartment and every
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
            f"{label} qualifier lines did not persist: "
            f"definitions={persisted!r}, resolved={resolved!r}"
        )


def _set_stock_text(adapter: Any, annotations: list[Any]) -> None:
    """Print the thickness as the stock's: "5/16 ±.001 (.3125) GROUND STOCK REF".

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


@_telemetry.traced("drawing.transgear_arm.projected_zone_chains", label_param="label")
def _add_projected_zone_chains(adapter: Any, view: Any, label: str) -> None:
    """Every projected zone drawn in ``view`` (section ``label``) at its
    feature: a heavy chain line from front face A along the zone's direction
    for its height, and, when its ``ZoneChain`` carries one, the height's
    dimension on that line, prefixed with the count of zones it carries
    ("2X") and printed as the frames print it.

    The ends are model points projected through the view in one frame, so
    each line is its zone's own extent at true length and on its own side of
    face A. The lines are authored together in the view's sketch, straight
    to the database (``_transgear_zone_line``, shared with the plate), the
    drawing rebuilds once, and their fonts and endpoints are read back
    settled; each dimension measures its line itself.
    """
    chains = [(key, chain) for key, chain in PROJECTED_ZONE_CHAINS.items() if chain.view == label]
    controls = {c.key: c for c in GEOMETRIC_CONTROLS}
    heights = {key: controls[key].projected_zone_height_mm for key, _chain in chains}
    native = _early_bound(view, "IView")
    native.UpdateViewDisplayGeometry()
    ratio = tuple(float(value) for value in native.ScaleRatio)
    projected = model_points_in_view(
        adapter, view,
        [
            (chain.x_mm / 1000.0, 0.0, z / 1000.0)
            for key, chain in chains
            for z in (0.0, PROJECTED_ZONE_DIRECTION[key] * heights[key])
        ],
        label=f"section {label} projected zones",
        names=[f"{key} {end}" for key, _chain in chains for end in ("face A", "far end")],
    )
    ends = {key: projected[2 * index : 2 * index + 2] for index, (key, _chain) in enumerate(chains)}
    for key, (start, end) in ends.items():
        dx, dy = end[0] - start[0], end[1] - start[1]
        if min(abs(dx), abs(dy)) > 1e-6 or abs(
            math.hypot(dx, dy) - heights[key] * ratio[0] / ratio[1] / 1000.0
        ) > 1e-6:
            raise RuntimeError(f"{key} projected zone projects as {(start, end)!r} at {ratio!r}")
    sketched = zone_lines.sketch_lines(
        adapter, view, {key: (start, end) for key, (start, end) in ends.items()},
        style=zone_lines.CHAIN_LINE_STYLE, width=zone_lines.CHAIN_LINE_WEIGHT,
        label=f"section {label} projected-zone chain",
    )
    rebuild_drawing(adapter, label=f"section {label} projected-zone chain lines")
    zone_lines.require_placed(
        adapter, sketched,
        style=zone_lines.CHAIN_LINE_STYLE, width=zone_lines.CHAIN_LINE_WEIGHT,
        label=f"section {label} projected-zone chain", stage="settled",
    )
    offsets = []
    with zone_lines.dimension_input_suppressed(adapter):
        for key, chain in chains:
            if chain.dimension is None:
                _telemetry.info(f"{key} projected zone: chain {ends[key]!r}")
                continue
            start, end = ends[key]
            at = (
                (start[0] + end[0]) / 2.0 + chain.dimension[0],
                (start[1] + end[1]) / 2.0 + chain.dimension[1],
            )
            dimension = zone_lines.dimension_line(
                adapter, view, sketched[key].segment,
                vertical=abs(end[0] - start[0]) <= 1e-6, at=at,
                label=f"{key} projected height",
            )
            measured = abs(float(_early_bound(dimension.GetDimension2(0), "IDimension").SystemValue))
            if abs(measured * 1000.0 - heights[key]) > 1e-6:
                raise RuntimeError(
                    f"{key} height measures {measured * 1000.0:g}, not {heights[key]:g} mm"
                )
            # The frame's Ⓟ height is the control; the chain line's
            # dimension repeats it, so it prints as a reference (codjiflo on
            # 40288f27f, rule 3): driven, bracketed as the plate's zone
            # heights are (set_reference_dimension's form), the count first.
            model_dimension = _early_bound(dimension.GetDimension2(0), "IDimension")
            model_dimension.DrivenState = _SW_DIMENSION_DRIVEN
            dimension.SetPrecision3(DRAWING_REFERENCE_PRECISION, -1, -1, -1)
            count = projected_zone_count(key)
            prefix = f"{count}X (" if count > 1 else "("
            dimension.ShowParenthesis = False
            dimension.SetText(_SW_TEXT_PREFIX, prefix)
            dimension.SetText(_SW_TEXT_SUFFIX, ")")
            applied = (
                int(model_dimension.DrivenState),
                int(dimension.GetPrimaryPrecision2()),
                bool(dimension.ShowParenthesis),
                str(dimension.GetText(_SW_TEXT_PREFIX) or ""),
                str(dimension.GetText(_SW_TEXT_SUFFIX) or ""),
            )
            wanted = (_SW_DIMENSION_DRIVEN, DRAWING_REFERENCE_PRECISION, False, prefix, ")")
            if applied != wanted:
                raise RuntimeError(f"{key} reference height reads {applied}, not {wanted}")
            if chain.text_xy is not None:
                # The value stands off its dimension line on a leader; the
                # line and its arrows stay on the zone's ends (the stock
                # text's idiom).
                annotation = _early_bound(dimension.GetAnnotation(), "IAnnotation")
                dimension.OffsetText = True
                if not annotation.SetPosition2(chain.text_xy[0], chain.text_xy[1], 0.0):
                    raise RuntimeError(f"failed to offset {key}'s height text")
                offsets.append((key, annotation, chain.text_xy))
            _telemetry.info(
                f"{key} projected zone: chain {ends[key]!r}, height "
                f"{prefix}{measured * 1000.0:.4f} on {at!r}, text {chain.text_xy!r}"
            )
    if offsets:
        rebuild_drawing(adapter, label=f"section {label} projected height texts")
    for key, annotation, text_xy in offsets:
        position = tuple(float(value) for value in annotation.GetPosition())
        if math.dist(position[:2], text_xy) > 1e-6:
            raise RuntimeError(f"{key} height text stayed at {position!r}")


@_telemetry.traced("drawing.transgear_arm.pin_zone_section")
def _pin_zone_section(adapter: Any, plan: Any) -> Any:
    """Section D-D on its own sheet: the arm cut across the pin bore's axis
    in that sheet's plan, cut faces only, at the sheet's 2:1, looking toward
    the pivot; the cut face and the bore's forward chain line together centre
    on ``PIN_SECTION_ZONE_CENTER``."""
    pin_x = _front_x(PIN_STATION)
    half = edge_half_width(PIN_STATION)
    section = create_section_view(
        adapter, plan,
        line_start=(pin_x, _front_y(half) + SECTION_LINE_OVERRUN),
        # Further out below: there the arm's lower edge falls toward the
        # pivot, under the letter left of the arrow (run 20261027T201320296Z:
        # it crossed the D at 5 mm).
        line_end=(pin_x, _front_y(-half) - _PIN_SECTION_LOWER_OVERRUN),
        view_xy=PIN_SECTION_ZONE_CENTER, section_label=PIN_SECTION_LABEL,
        scale=VIEW_SCALE, label="pin bore projected-zone section",
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
    (control,) = (c for c in GEOMETRIC_CONTROLS if c.key == "feed_stud_projected_axis")
    far_z = PROJECTED_ZONE_DIRECTION[control.key] * control.projected_zone_height_mm
    for attempt in range(4):
        native.UpdateViewDisplayGeometry()
        rear, front_face, far = model_points_in_view(
            adapter, section,
            tuple((PIN_STATION / 1000.0, 0.0, z / 1000.0) for z in (THICKNESS, 0.0, far_z)),
            label=f"section D-D zone extent, pass {attempt}",
            names=("rear face", "face A", "zone end"),
        )
        xs = (rear[0], front_face[0], far[0])
        centre = ((min(xs) + max(xs)) / 2.0, front_face[1])
        miss = (PIN_SECTION_ZONE_CENTER[0] - centre[0], PIN_SECTION_ZONE_CENTER[1] - centre[1])
        if math.hypot(*miss) <= 1e-4:
            break
        position = tuple(float(value) for value in native.Position)
        if not native.SetViewPosition(
            double_array([position[0] + miss[0], position[1] + miss[1]]), False
        ):
            raise RuntimeError("failed to re-centre section D-D")
        rebuild_drawing(adapter, label="section D-D re-centred")
    else:
        raise RuntimeError(f"section D-D zone centred at {centre!r}, not {PIN_SECTION_ZONE_CENTER!r}")
    # Looking toward the pivot, forward (-Z) reads to the right of face A.
    if not rear[0] < front_face[0] < far[0]:
        raise RuntimeError(f"section D-D does not read forward to the right: {xs!r}")
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


@_telemetry.traced("drawing.transgear_arm.pin_section_caption_fields")
def _match_pin_section_caption(adapter: Any, section: Any, section_a: Any) -> None:
    """Give section D-D's native caption section A-A's linked view-label
    fields, scale included, so the two sections' captions read alike (run
    20261027T201320296Z: D-D's native caption carried no scale)."""
    note, linked_text = _section_caption(section, "D-D")
    _note_a, linked_a = _section_caption(section_a, "A-A")
    if "<VLSCALEV>" not in linked_a:
        raise RuntimeError(f"section A-A caption carries no scale field: {linked_a!r}")
    if linked_text != linked_a:
        note.PropertyLinkedText = linked_a
        rebuild_drawing(adapter, label="section D-D caption fields")
        if str(note.PropertyLinkedText or "") != linked_a:
            raise RuntimeError("section D-D caption fields did not persist")


@_telemetry.traced("drawing.transgear_arm.pin_section_caption_settled")
def _pin_section_caption_settled(adapter: Any, section: Any) -> None:
    """After finalize_drawing's last sheet-scale reset and rebuild: hang
    section D-D's caption, centred, under its cut face (bounded measured
    moves, then one final check of the resolved extent), inside the sheet,
    with its linked name and scale lines. ``INote.GetText`` reads the linked
    fields blank even here (run 20261027T215106763Z: ' \\r\\n '), so the
    resolved text is evidenced by its extent: two lines, as A-A's."""
    if not _early_bound(adapter.currentModel, "IDrawingDoc").ActivateSheet(SHEET_NAMES[1]):
        raise RuntimeError("cannot activate the pin-bore zone sheet")
    note, linked_text = _section_caption(section, "D-D")
    half = edge_half_width(PIN_STATION) * _S / 1000.0
    target = (
        PIN_SECTION_ZONE_CENTER[0],
        PIN_SECTION_ZONE_CENTER[1] - half - _PIN_CAPTION_GAP_M,
    )

    def miss() -> tuple[tuple[float, ...], tuple[float, float]]:
        extent = tuple(float(value) for value in note.GetExtent())
        return extent, (target[0] - (extent[0] + extent[3]) / 2.0, target[1] - extent[4])

    for move in range(_CAPTION_MOVES):
        extent, error = miss()
        _telemetry.info(f"section D-D caption move {move}: extent {extent}, off {error}")
        if max(map(abs, error)) < _CAPTION_SETTLE_M:
            break
        move_annotation(adapter, note.GetAnnotation(), *error, label="section D-D caption")
    extent, error = miss()
    if max(map(abs, error)) >= _CAPTION_SETTLE_M:
        raise RuntimeError(f"section D-D caption stands at {extent}, its top centre asked at {target}")
    require_inside("section D-D caption", (extent[0], extent[1], extent[3], extent[4]), sheet_region(adapter))
    if str(note.PropertyLinkedText or "") != linked_text or extent[4] - extent[1] < _CAPTION_TWO_LINES_M:
        raise RuntimeError(f"section D-D caption {linked_text!r} resolved to {extent}")
    _telemetry.info(f"section D-D caption at {extent}")


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
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    set_reference_dimensions(adapter, annotations, ("PivotBoreDia",))
    _set_stock_text(adapter, annotations)
    _end_radius_to_arc(adapter, annotations)
    offset_dimension_text(adapter, annotations, {"FloorDepth": FLOOR_TEXT_XY})
    # Model-owned circular zones and actual feature datums. BASIC stations
    # are imported from the part; no drawing-only coordinate tolerances.
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
        # The projected-zone frames stand in section A-A on the side their
        # zone projects to (the plate taps' rear, the stud's front). Each
        # tap frame's leader climbs to the hole's NEAR wall at the rear
        # mouth, so it never crosses the tap's chain line on its axis; each
        # frame stands far enough out that its 6 mm shoulder ends short of
        # the hole (run 20261027T180656347Z: the shoulders ran across the
        # chain lines). Each keeps its offset from its tap's axis: a fixed
        # sheet x put tap 1's frame on its chain line once #2034 moved the
        # taps 12 mm left (preview run 20261028T070651235Z).
        "plate_tap_1_position": PmiDrawingPlacement(
            section, (_front_x(PLATE_TAP_STATIONS[0]) - 0.07196, _TAP_FRAME_TOP_Y),
            attachment_xy=_wall_point(
                adapter, section, x_mm=PLATE_TAP_STATIONS[0] - _PLATE_DRILL_R,
                z_mm=THICKNESS - 0.5, label="plate tap 1 wall",
            ),
        ),
        "plate_tap_2_position": PmiDrawingPlacement(
            section, (_front_x(PLATE_TAP_STATIONS[1]) + 0.01104, _TAP_FRAME_TOP_Y),
            attachment_xy=_wall_point(
                adapter, section, x_mm=PLATE_TAP_STATIONS[1] + _PLATE_DRILL_R,
                z_mm=THICKNESS - 0.5, label="plate tap 2 wall",
            ),
        ),
        "feed_stud_projected_axis": PmiDrawingPlacement(
            section, (_STUD_FRAME_X, SECTION_CENTER[1] + 0.0195),
            attachment_xy=_wall_point(
                adapter, section, x_mm=PIN_STATION - pin_r, z_mm=2.5,
                label="feed stud projected axis pin bore wall",
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
    project_part_pmi(
        adapter, placements=placements, datums=PART_DATUMS,
        controls=GEOMETRIC_CONTROLS, label="transgear arm locating frame",
    )
    _add_projected_zone_chains(adapter, section, "A-A")
    _overall_reference(adapter, front)
    for view, label in ((front, "front"), (end, "end")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME centre marks to the {label} view")

    # Thread and tap drill ride the native callouts; the class is the title
    # block's; the countersink and engagement lines are the qualifiers'.
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

    # Sheet 2: the pin bore's projected zone in section D-D, cut from a plan
    # on sheet 1's plan centre (rule 15: its own sheet, not a shrunk view).
    if not ddoc.ActivateSheet(SHEET_NAMES[1]):
        raise RuntimeError("cannot activate the pin-bore zone sheet")
    pin_plan = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    set_hidden_lines_removed(adapter, pin_plan)
    pin_section = _pin_zone_section(adapter, pin_plan)
    set_hidden_lines_removed(adapter, pin_section)
    _add_projected_zone_chains(adapter, pin_section, "D-D")
    _match_pin_section_caption(adapter, pin_section, section)
    if not auto_center_marks(adapter, pin_plan, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME centre marks to the pin-bore zone plan")
    iso = place_view(
        adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_VIEW_SCALE
    )
    set_hidden_lines_removed(adapter, iso)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
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
        settled_checks=(lambda: _pin_section_caption_settled(adapter, pin_section),),
    )
    require_saved_projected_gtols(
        adapter, artefacts["drawing"], GEOMETRIC_CONTROLS,
        label="saved transgear arm drawing projected axes",
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
