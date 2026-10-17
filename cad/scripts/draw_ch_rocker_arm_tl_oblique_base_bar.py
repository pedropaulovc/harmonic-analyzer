r"""Create the drawing for the oblique trammel's base bar (MHA-CH-006-TL-20).

One part, one configuration, two off (the title block's quantity); the
second bar is the same part turned over. Its plan (the *Front view, looking
down on the top face) carries the bar's length and stock width, the rail
holes' baseline stations and the row's lateral station from the -Y edge
under one native tap callout, the end brackets' four counterbored
holes (stations from the end face, rows from the -Y edge, one native callout
naming the far-side counterbores and the TL-28 mate), and both slots'
stations, rises, width and centre-to-centre run (slot centre marks); the end
view, projected right of the plan on its centreline, carries the stock
thickness; the shaded isometric rides bottom left under the plan's stack.

Run with SolidWorks open::

    uv run python cad\scripts\draw_ch_rocker_arm_tl_oblique_base_bar.py ch-rocker-arm-tl-oblique-base-bar
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
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
    stamp_drawing_summary,
)
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _hole_callout_thread_class import omit_title_block_thread_class
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
import ch_rocker_arm_tl_oblique_base_bar_spec as part_spec
from _feature_requirements import part_metadata, requirement
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _printed_limits import limits
from _printed_tolerance import drilled_oversize_mm
from ch_rocker_arm_tl_oblique_base_bar_spec import (
    BAR_LENGTH,
    BRACKET_CALLOUT_PRECISION,
    BRACKET_CALLOUT_PROCESS,
    BRACKET_HOLE_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FAR_SLOT_DROP,
    FAR_SLOT_X,
    FAR_SLOT_Y,
    HALF_WIDTH,
    NEAR_SLOT_RISE,
    NEAR_SLOT_X,
    RAIL_HOLE_X,
    RAIL_MATE_CALLOUT,
    RAIL_ROW_CALLOUT,
    SLOT_RUN,
    STOCK_DIMENSIONS,
    TAP_DRILL,
    TAP_SPEC,
)
import ch_rocker_arm_tl_oblique_leadscrew_spec as leadscrew

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_oblique_base_bar"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# A 440 x 101.6 x 12.7 bar: 1:2 puts the 220-wide plan on the B sheet, its end
# view projected right of it on the same centreline (third angle). The
# vertical budget: the rail-hole stack tops out at about 262 under the 267
# border. The plan sits right of centre so the three side lanes (the row's
# three-line callout the widest) and the stock width's text clear the left
# border (about 12); r3 moved plan and end view 8 right, r4 another 3.5 (the
# row's block measured wider than estimated). C4: the bracket
# holes' callout takes the bottom-right corner under the end view, so the
# 1:5 iso (about 64 x 53) and its note move to the free bottom-left corner,
# under the plan's six-lane stack (lowest text about 121) and left of the
# title block (x from about 216).
SHEET_SCALE = (1.0, 2.0)
VIEW_SCALE = (1, 2)
ISO_SCALE = (1, 5)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
FRONT_CENTER = (0.1835, 0.1835)
END_CENTER = (0.3365, FRONT_CENTER[1])
ISO_CENTER = (0.090, 0.072)
ISO_NOTE_XY = (0.060, 0.038)
ISO_HALF = (0.033, 0.027)  # measured on the r3 sheet


def _sheet_x(center: tuple[float, float], model_x_mm: float) -> float:
    """Sheet X of a model-X point in a plan view (bbox-centred)."""
    return center[0] + (model_x_mm - BAR_LENGTH / 2.0) * _S / 1000.0


def _sheet_y(center: tuple[float, float], model_y_mm: float) -> float:
    """Sheet Y of a model-Y point in a plan view (the bar is centred on y 0)."""
    return center[1] + model_y_mm * _S / 1000.0


_HALF_W_SHEET = HALF_WIDTH * _S / 1000.0
_HALF_L_SHEET = BAR_LENGTH * _S / 2000.0
_TOP = FRONT_CENTER[1] + _HALF_W_SHEET
_BOTTOM = FRONT_CENTER[1] - _HALF_W_SHEET
_LEFT = FRONT_CENTER[0] - _HALF_L_SHEET
_RIGHT = FRONT_CENTER[0] + _HALF_L_SHEET
TAP_R_SHEET = TAP_DRILL * _S / 2000.0
BRACKET_R_SHEET = BRACKET_HOLE_DIA * _S / 2000.0
# The leadscrew layout's bracket holes: (near, far) pairs, inner row first.
BRACKET_HOLES = leadscrew.BASE_BAR_HOLES
BRACKET_NEAR_X, BRACKET_INNER_Y = BRACKET_HOLES[0]
BRACKET_FAR_X, BRACKET_OUTER_Y = BRACKET_HOLES[3]
LANE = 0.008  # one side-dimension lane
# Stacked dimensions (the rail-hole baselines above the plan, the stations
# and length below it): first dimension line STACK_FIRST off the part, then
# STACK_LANE apart (ASME Y14.5's 6 mm spacing). The curation keep point is the
# text block's centre; SolidWorks hangs the dimension line about TEXT_DROP
# below a one-line block and TWO_LINE_DROP below a two-line one.
STACK_FIRST = 0.008
STACK_LANE = 0.006
TEXT_DROP = 0.0027
TWO_LINE_DROP = 0.0056


def _above_line(k: int) -> float:
    """Sheet Y of the k-th (from 0) dimension line above the plan."""
    return _TOP + STACK_FIRST + k * STACK_LANE


def _below_line(k: int) -> float:
    """Sheet Y of the k-th (from 0) dimension line below the plan."""
    return _BOTTOM - STACK_FIRST - k * STACK_LANE


# The plan: the rail-hole stations stack above it from the end face, nearest
# first (DRO absolutes), each in its own lane; the outermost (400.00) carries
# the mate on a second line, the only lane no extension line crosses. The
# 40.00 span is shorter than its text, so its text sits outside it, between
# holes 1 and 2, clear of the end face's extension line (r1 printed it across
# that line).
#
# Below it, nearest first: the near slot's width (its extension lines then
# cross no other dimension), the near slot's station, the near bracket pair's
# station, the far slot's, the far pair's, the length. A span shorter than
# its text prints the text beside it, clear of both extension lines (r2
# struck "2X 13.50" and "20.9" with their own lines): the near station's
# right of the slot's centre line; the near pair's station sits at its
# span's right end, clear of the slot's lines. The width's "2X 13.50 THRU"
# (r5: the slots' depth) sits right of the near pair's extension line, which
# runs down through lane 0 too close to the slot for the text to fit
# between them (Y14.5 lets an extension line cross a dimension line).
#
# Left of it, shortest nearest: the near rise, the rail row's lateral station
# (50.80, from the -Y edge to the row's centreline, its function on two
# callout lines under it; r3), the stock width, whose text rides above the
# centreline so the row's upper extension line ends short of it. The row's
# three-line block sits above the near rise's text and extension line.
# Right of it: the bracket rows from the -Y edge (the outer row's 6.800
# below the bar, its span too short, its text right of its line on a
# shoulder; the inner row's 24.800 mid-span, its line far enough out that
# its outside arrow under the bar's edge clears the 6.800's text: c4-r2
# struck the "8" and bunched the two lines), the far slot's run (2X; the far
# slot so the dimension lands off the part), its text below the 3 mm span
# (r2 struck "2X 6.00" with its arrows; c4-r2's drop puts the bar's top edge
# line where the text sat above), then the far slot's drop from the +Y edge
# (c4-r2: located from the -Y edge, its wall to the +Y edge carried the stock
# width's band). The bracket callout's leader leaves the far outer hole down
# and right, crossing only the length's extension line, to a block in the
# bottom-right corner.
_TEXT_GAP = 0.0025  # a text's clearance from the line it sits beside
# Half text widths (sheet m, measured on the r2 sheet's 3.5 mm text).
_SLOT_WIDTH_TEXT_HALF = 0.017  # "2X 13.50 THRU", 13 glyphs at r4's 2.6
_NEAR_SLOT_X_TEXT_HALF = 0.0045  # "20.9"
_SLOT_RUN_TEXT_HALF = 0.008  # "2X 6.00"
# "FOR HGR15R RAIL", its widest line (15 glyphs): 38.8 wide on the r4 sheet.
_RAIL_ROW_TEXT_HALF = 0.0195
_BAR_WIDTH_TEXT_HALF = 0.0074  # "101.6" over "STOCK": 14.8 wide on r4
_BRACKET_NEAR_X_TEXT_HALF = 0.0066  # "57.000"
_BRACKET_ROW_TEXT_HALF = 0.0066  # "24.800"
_BRACKET_OUTER_TEXT_BELOW = 0.004  # "6.800"'s centre under the bar's -Y edge
# SolidWorks sets an outside text right of its own line on a shoulder: the
# 6.800 spans from about 1.5 to 14.2 right of its line (c4-r2 sheet).
_SHOULDER_TEXT_SPAN = (0.0015, 0.0142)
_SLOT_RUN_TEXT_LOW = 0.0055  # text centre below the run's lower line
# The row's block: three lines, about 17 tall; its bottom line clears the
# near rise's "10.3" (top about 4.5 above the bar's -Y edge) and its upper
# extension line (5.2 above).
_RAIL_ROW_TEXT_HALF_HIGH = 0.0085
_RAIL_ROW_TEXT_FLOOR = 0.006  # block bottom above the bar's -Y edge
# Side lanes (sheet m off the plan's end). The row's text clears the near
# rise's line by 2.5 (r4: the 10.3's outside arrow and its tail struck the
# block's last "L"); the stock width's line clears the row's text by 2.
_RAIL_ROW_LANE = LANE + 0.0025 + _RAIL_ROW_TEXT_HALF
_BAR_WIDTH_LANE = _RAIL_ROW_LANE + _RAIL_ROW_TEXT_HALF + 0.002
_SLOT_RUN_LANE = 0.011  # its text's left end clears the bar's end face
_BRACKET_OUTER_LANE = LANE
# The 24.800's line clears the 6.800's shouldered text by 3.8.
_BRACKET_INNER_LANE = LANE + _SHOULDER_TEXT_SPAN[1] + 0.0038  # 0.026
_FAR_DROP_LANE = 0.021  # above the bracket rows' texts, clear of the end view
_LAST_HOLE = len(RAIL_HOLE_X)
_HOLE_TEXT_X = (
    (RAIL_HOLE_X[0] + RAIL_HOLE_X[1]) / 2.0,
    *(x / 2.0 for x in RAIL_HOLE_X[1:]),
)
FRONT_KEEP = {
    **{
        f"RailHole{k}X": (
            _sheet_x(FRONT_CENTER, text_x),
            _above_line(k - 1) + (TWO_LINE_DROP if k == _LAST_HOLE else TEXT_DROP),
        )
        for k, text_x in enumerate(_HOLE_TEXT_X, start=1)
    },
    "BarLength": (FRONT_CENTER[0], _below_line(5) + TEXT_DROP),
    "BarWidth": (_LEFT - _BAR_WIDTH_LANE, FRONT_CENTER[1] + 0.010),
    "RailRowY": (
        _LEFT - _RAIL_ROW_LANE,
        _BOTTOM + _RAIL_ROW_TEXT_FLOOR + _RAIL_ROW_TEXT_HALF_HIGH,
    ),
    "SlotWidth": (
        _sheet_x(FRONT_CENTER, BRACKET_NEAR_X) + _TEXT_GAP + _SLOT_WIDTH_TEXT_HALF,
        _below_line(0) + TEXT_DROP,
    ),
    "NearSlotX": (
        _sheet_x(FRONT_CENTER, NEAR_SLOT_X) + _TEXT_GAP + _NEAR_SLOT_X_TEXT_HALF,
        _below_line(1) + TEXT_DROP,
    ),
    "BracketHole1X": (
        _sheet_x(FRONT_CENTER, BRACKET_NEAR_X) - _TEXT_GAP - _BRACKET_NEAR_X_TEXT_HALF,
        _below_line(2) + TEXT_DROP,
    ),
    "FarSlotX": (_sheet_x(FRONT_CENTER, FAR_SLOT_X / 2.0), _below_line(3) + TEXT_DROP),
    "BracketHole3X": (
        _sheet_x(FRONT_CENTER, BRACKET_FAR_X / 2.0),
        _below_line(4) + TEXT_DROP,
    ),
    "BracketRowOuterY": (
        _RIGHT + _BRACKET_OUTER_LANE,
        _BOTTOM - _BRACKET_OUTER_TEXT_BELOW,
    ),
    "BracketRowInnerY": (
        _RIGHT + _BRACKET_INNER_LANE,
        _sheet_y(FRONT_CENTER, (-HALF_WIDTH + BRACKET_INNER_Y) / 2.0),
    ),
    "SlotRun": (
        _RIGHT + _SLOT_RUN_LANE,
        _sheet_y(FRONT_CENTER, FAR_SLOT_Y - SLOT_RUN / 2.0) - _SLOT_RUN_TEXT_LOW,
    ),
    "NearSlotRise": (
        _LEFT - LANE,
        _sheet_y(FRONT_CENTER, -HALF_WIDTH + NEAR_SLOT_RISE / 2.0),
    ),
    "FarSlotDrop": (
        _RIGHT + _FAR_DROP_LANE,
        _sheet_y(FRONT_CENTER, HALF_WIDTH - FAR_SLOT_DROP / 2.0),
    ),
}
END_KEEP = {
    "BarThick": (END_CENTER[0] + _HALF_W_SHEET + LANE, END_CENTER[1]),
}
# One slot's sizes count both slots; the width says they go through (r5).
DIMENSION_TEXT = {"SlotWidth": ("2X ", " THRU"), "SlotRun": ("2X ", "")}
# The width and thickness are the bar as bought (the feed lever's STOCK); the
# rail-hole stations' tight band names its mate under the outermost station,
# the row's names what it buys (r3: every hole in line with the rail's row).
CALLOUTS_BELOW = dict.fromkeys(sorted(STOCK_DIMENSIONS), "STOCK") | {
    f"RailHole{_LAST_HOLE}X": RAIL_MATE_CALLOUT,
    "RailRowY": RAIL_ROW_CALLOUT,
}
# The tap callout's two lines, centred about here, clear the 267 border by
# about 6 (r3 printed its first line touching it).
TAP_CALLOUT_XY = (0.318, 0.256)
# The bracket callout's four lines (two process, two native), centred about
# here: right of the length's extension line, under the end view, above the
# title block.
BRACKET_CALLOUT_XY = (0.335, 0.125)

part_metadata(precision_sources=("DRAWING_PRECISION_BY_NAME",))

_INTO_BAR = ([0.0, 0.0, -1.0], ("__frame__",))
_TAP_DRILL_PRINTED = round(part_spec.TAP_DRILL, 2)
_DRILLED = (drilled_oversize_mm(), 0.0)
_PLACES = part_spec.RAIL_HOLE_PLACES
_BAND = (part_spec.RAIL_HOLE_BAND, -part_spec.RAIL_HOLE_BAND)
_FROM_LOW_SIDE = (
    "bar_low_side",
    (("draw_ch_rocker_arm_tl_oblique_base_bar", "build"),),
)

# The faced -Y side: the datum the row's lateral station and the slot rises
# measure from.
requirement(
    "bar_low_side",
    kind="face",
    faces=(PlanarFace((0.0, -1.0, 0.0), part_spec.HALF_WIDTH),),
    requirements=(),
    fields={
        "normal": ([0.0, -1.0, 0.0], ("__frame__",)),
        "plane": (
            {"frame": "model", "axis": "y", "value": -part_spec.HALF_WIDTH},
            ("HALF_WIDTH",),
        ),
    },
)

for _index, _x in enumerate(part_spec.RAIL_HOLE_X, start=1):
    # Baseline from the spindle-end face (the frame's x 0) and from the faced
    # -Y side: DRO absolutes, each in the rail screws' clearance band.
    _station: dict[str, tuple[Any, tuple[Any, ...]]] = {
        "station": (
            limits(_x, _PLACES, _BAND),
            ("RAIL_HOLE_X", "RAIL_HOLE_BAND"),
        ),
        "station_nominal": (_x, ("RAIL_HOLE_X",)),
        "height": (
            limits(part_spec.RAIL_ROW_Y, _PLACES, _BAND),
            ("RAIL_ROW_Y", "RAIL_HOLE_BAND"),
        ),
        "height_nominal": (part_spec.RAIL_ROW_Y, ("RAIL_ROW_Y",)),
        "height_from": _FROM_LOW_SIDE,
    }
    requirement(
        f"rail_hole_{_index}",
        kind="hole",
        faces=(CylinderFace(part_spec.TAP_DRILL, contains_x_mm=_x),),
        requirements=("thread", "dia", "station", "height", "thru", "note"),
        fields={
            "at": ([_x, 0.0, part_spec.BAR_THICK], ("RAIL_HOLE_X", "BAR_THICK")),
            "axis": _INTO_BAR,
            "thread": (
                f"{part_spec.RAIL_SCREW} UNC-{part_spec.TAP_SPEC.thread_class}",
                ("TAP_SPEC", "RAIL_SCREW"),
            ),
            "tap_drill_mm": (part_spec.TAP_DRILL, ("TAP_SPEC",)),
            "dia": (
                limits(_TAP_DRILL_PRINTED, 2, _DRILLED),
                ("TAP_SPEC", "TAP_DRILL"),
            ),
            "nominal_dia": (_TAP_DRILL_PRINTED, ("TAP_DRILL",)),
            "thru": (True, ("TAP_SPEC",)),
            **_station,
            # The matched-fit callout names the mate (RAIL_MATE_CALLOUT).
            "note": (
                RAIL_MATE_CALLOUT,
                ("RAIL_MATE_CALLOUT", "RAIL_SCREW_CLEARANCE", "RAIL_HOLE_BAND"),
            ),
        },
        precision={"dia": 2, "station": _PLACES, "height": _PLACES},
    )

_BRACKET_PLACES = part_spec.BRACKET_HOLE_PLACES
_CBORE_PLACES = part_spec.BRACKET_CBORE_PLACES
_BRACKET_DIA_PRINTED = round(BRACKET_HOLE_DIA, 2)
_FROM_UNDERSIDE = ([0.0, 0.0, 1.0], ("__frame__",))
_BRACKET_SOURCE = (("ch_rocker_arm_tl_oblique_leadscrew_spec", "BASE_BAR_HOLES"),)
for _index, (_x, _y) in enumerate(BRACKET_HOLES, start=1):
    # Stations from the spindle-end face, rows from the faced -Y side, at
    # .XXX: each pair holds TL-28's tapped pair inside the screws' float.
    requirement(
        f"bracket_hole_{_index}",
        kind="hole",
        faces=(CylinderFace(BRACKET_HOLE_DIA, contains_x_mm=_x, contains_y_mm=_y),),
        requirements=("station", "height", "dia", "thru", "note"),
        fields={
            "at": ([_x, _y, 0.0], _BRACKET_SOURCE),
            "axis": _FROM_UNDERSIDE,
            "station": (
                limits(_x, _BRACKET_PLACES),
                (*_BRACKET_SOURCE, "BRACKET_HOLE_PLACES"),
            ),
            "station_nominal": (_x, _BRACKET_SOURCE),
            "height": (
                limits(part_spec.HALF_WIDTH + _y, _BRACKET_PLACES),
                (*_BRACKET_SOURCE, "HALF_WIDTH", "BRACKET_HOLE_PLACES"),
            ),
            "height_nominal": (
                part_spec.HALF_WIDTH + _y,
                (*_BRACKET_SOURCE, "HALF_WIDTH"),
            ),
            "height_from": _FROM_LOW_SIDE,
            "dia": (
                limits(_BRACKET_DIA_PRINTED, 2, _DRILLED),
                ("BRACKET_HOLE_DIA", "BRACKET_HOLE_SPEC"),
            ),
            "dia_nominal": (_BRACKET_DIA_PRINTED, ("BRACKET_HOLE_DIA",)),
            "thru": (True, ("BRACKET_HOLE_SPEC",)),
            # The pattern's tight band names its mate; the counterbores open
            # on the face the plan does not show.
            "note": (
                " ".join(BRACKET_CALLOUT_PROCESS.split("\n")).strip(),
                ("BRACKET_CALLOUT_PROCESS", "BRACKET_MATE"),
            ),
        },
        precision={"station": _BRACKET_PLACES, "height": _BRACKET_PLACES, "dia": 2},
    )
    requirement(
        f"bracket_hole_{_index}_counterbore",
        kind="counterbore",
        faces=(
            CylinderFace(
                part_spec.BRACKET_CBORE_DIA, contains_x_mm=_x, contains_y_mm=_y
            ),
        ),
        requirements=("dia", "depth"),
        fields={
            "parent": (
                f"bracket_hole_{_index}",
                (
                    "BRACKET_HOLE_DIA",
                    ("draw_ch_rocker_arm_tl_oblique_base_bar", "build"),
                ),
            ),
            "dia": (
                limits(part_spec.BRACKET_CBORE_DIA, _CBORE_PLACES),
                ("BRACKET_CBORE_DIA", "BRACKET_SCREW_HEAD_DIA"),
            ),
            "dia_nominal": (part_spec.BRACKET_CBORE_DIA, ("BRACKET_CBORE_DIA",)),
            "depth": (
                limits(part_spec.BRACKET_CBORE_DEPTH, _CBORE_PLACES),
                ("BRACKET_CBORE_DEPTH", "BRACKET_SCREW_HEAD_HEIGHT"),
            ),
            "depth_ref": (part_spec.BRACKET_CBORE_DEPTH, ("BRACKET_CBORE_DEPTH",)),
        },
        precision={"dia": _CBORE_PLACES, "depth": _CBORE_PLACES},
    )


def _set_dimension_text(
    adapter: Any, annotations: list[Any], texts: dict[str, tuple[str, str]]
) -> None:
    """Write a native prefix/suffix on named imported dimensions; read back."""
    remaining = dict(texts)
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        text = remaining.pop(dimension_name(adapter, annotation), None)
        if text is None:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.SetText(1, text[0])  # swDimensionTextPrefix
        display.SetText(2, text[1])  # swDimensionTextSuffix
        got = (str(display.GetText(1) or ""), str(display.GetText(2) or ""))
        if got != text:
            raise RuntimeError(f"dimension text {text!r} did not persist: {got!r}")
    if remaining:
        raise RuntimeError(f"dimension texts not applied: {sorted(remaining)}")


def _omit_tap_thread_class(display: Any) -> None:
    """The title block's THREADS row owns the class (rule 2): the tap row
    reads ``7X 8-32 UNC THRU ALL``, not ``... - 2B ...``."""
    omit_title_block_thread_class(display, label="rail screw taps")
    native = _early_bound(display, "IDisplayDimension")
    resolved = [str(native.GetText(part) or "") for part in (1, 2, 3, 4)]
    if any(TAP_SPEC.thread_class in text for text in resolved):
        raise RuntimeError(
            f"rail screw taps: callout still prints its class: {resolved!r}"
        )


def _activate_view(adapter: Any, view: Any, *, label: str) -> None:
    """Make ``view`` the active view (a note lands in the active view)."""
    name = view_name(adapter, view)
    if not _early_bound(adapter.currentModel, "IDrawingDoc").ActivateView(name):
        raise RuntimeError(f"failed to activate the {label} view {name!r}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open base bar source", await adapter.open_model(str(SOURCE)))
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Isometric View Note",
    )
    read_required_properties(
        adapter.currentModel, ("Revision", "Title", *required), required=required
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rocker Oblique Trammel Base Bar Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker oblique trammel base bar; 6061-T6; MHA-CH-006-TL-20",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it. The end view
    # shares the plan's centre height: projected right of it (r2 hung it low).
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    end = place_view(adapter, str(SOURCE), "*Right", *END_CENTER, scale=VIEW_SCALE)
    # finalize_drawing shades the pictorial isometric with edges.
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (front, end, iso):
        set_hidden_lines_removed(adapter, view)

    # The plan shows the hidden RailRowReference and BracketRowReference
    # sketches, whose 50.80, 24.800 and 6.800 it prints.
    annotations = [
        *curate_view_dimensions(
            adapter,
            front,
            keep=FRONT_KEEP,
            view_label="plan",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            end,
            keep=END_KEEP,
            view_label="end view",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    # Places (and so each dimension's tolerance) are authored on the part; the
    # sheet only proves the import kept them, then marks the slot counts and
    # writes the STOCK and mate callouts.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _set_dimension_text(adapter, annotations, DIMENSION_TEXT)
    set_dimension_callouts(adapter, annotations, CALLOUTS_BELOW)

    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the plan")
    # One mark on each slot's round ends (draw_ch_rocker_arm_tl_outline_template):
    # the rises and the 2X 6.00 run land on them, so the run reads as
    # centre-to-centre (rule 12) and not as the slot's overall length.
    if not auto_center_marks(adapter, front, holes=False, slots=True, size=0.0025):
        raise RuntimeError("failed to add the slot center marks to the plan")
    tap_callout = add_native_hole_callout(
        adapter,
        front,
        edge_xy=(
            _sheet_x(FRONT_CENTER, RAIL_HOLE_X[-1]) + 0.6 * TAP_R_SHEET,
            _sheet_y(FRONT_CENTER, 0.0) + 0.8 * TAP_R_SHEET,
        ),
        callout_xy=TAP_CALLOUT_XY,
        label="rail screw taps",
    )
    _omit_tap_thread_class(tap_callout)
    # The far outer hole's edge, down and right of its centre: the leader
    # leaves away from the far pair's station line.
    bracket_callout = add_native_hole_callout(
        adapter,
        front,
        edge_xy=(
            _sheet_x(FRONT_CENTER, BRACKET_FAR_X) + 0.6 * BRACKET_R_SHEET,
            _sheet_y(FRONT_CENTER, BRACKET_OUTER_Y) - 0.8 * BRACKET_R_SHEET,
        ),
        callout_xy=BRACKET_CALLOUT_XY,
        label="end bracket holes",
        process=BRACKET_CALLOUT_PROCESS,
    )
    set_hole_callout_precision(
        bracket_callout, BRACKET_CALLOUT_PRECISION, label="end bracket holes"
    )

    # The property-linked blocks land in the active view: the plan.
    _activate_view(adapter, front, label="plan")
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Oblique Trammel Base Bar Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        # SolidWorks pins its own "#8-32 Tapped Hole" note to the plan once
        # the tap carries a hole callout; the callout already states it.
        redundant_note_substrings=("Tapped Hole",),
        expected_redundant_notes=1,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
