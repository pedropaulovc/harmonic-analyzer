r"""Create the manufacturing drawing for the transgear thumbnut (MHA-PD-13).

The nut lies as it sits in the lathe, axis horizontal (drawing-guidelines.md
rule 11; machinist review round 4).  The face view is the ``*Top``
orientation turned a quarter, looking at the dished front face: it carries
the native #8-32 UNC-2B through-thread callout and the cutting line, and
stands left of section A-A on one horizontal centreline, the rim end's view
beside the rim end (third angle; knob-cup layout). Both entry cones print as one
countersink callout in symbol form (``⌵ Ø.18 MAX X 90°  BOTH ENDS``,
rule 26): the model-owned MAX diameter and the included angle.
Section A-A uses the Front plane through the axis and two knurl crests, so the
knurl diameter, the head, waist and flange, the overall length and the
flange length from the seat face (the waist is their remainder) and the
dish's rim and floor diameters and its depth to the floor print
on solid cut edges.  No roughness symbol: the seat face clamps the wheel
(drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates)).
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
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
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
)
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _gear_drawing_entities import visible_circle_edge
from _hole_callout_thread_class import omit_title_block_thread_class
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _part_properties import part_drawing_unit
from _section_axis import position_section_caption
from _session import run_build
import _telemetry
from pd_transgear_thumbnut_spec import (
    CSK_DIA_SUFFIX,
    CSK_INCLUDED_ANGLE_DEG,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FLANGE_DIA,
    FLANGE_LENGTH,
    HEAD_DIA,
    HEAD_REAR_Y,
    KNURL_CALLOUT,
    KNURL_DIA_SUFFIX,
    OVERALL_LENGTH,
    TAP_DRILL_DIA,
    TAP_SPEC,
    THREAD,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE


SPEC = DRAWINGS_BY_NAME["pd_transgear_thumbnut"]
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

# A Ø.81 × .63 nut: 3:1 leaves room round the section for its nine
# dimensions and the knurl callout on the landscape sheet.
SHEET_SCALE = (3.0, 1.0)
VIEW_SCALE = (3, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
# Rule 11: the nut lies as it sits in the lathe, axis horizontal.  The face
# view (``*Top``, the dished rim face) stands left of section A-A on one
# horizontal centreline: third angle, the left view shows the left end, so
# the rim is A-A's left end and the seat face its right (machinist review
# round 4 of run 20261107T201806645Z; the draw_pd_transgear_knob_cup
# layout).  The isometric keeps its place right of them.
FACE_CENTER = (0.066, 0.150)
SECTION_CENTER = (0.209, FACE_CENTER[1])
ISO_CENTER = (0.345, 0.165)
# Half the knurl diameter on the sheet, and the cutting line's overrun past it.
HALF_HEAD = HEAD_DIA * _S / 2000.0
SECTION_LINE_OVERRUN = 0.005
# The face view turned a quarter: sheet Y is then model X, so a vertical cut
# on the nut axis is the Front plane, the plane of the turned profiles, and
# A-A projects to the right with the axis horizontal.
FACE_VIEW_ANGLE = math.pi / 2.0
SECTION_LINE = (
    (FACE_CENTER[0], FACE_CENTER[1] - HALF_HEAD - SECTION_LINE_OVERRUN),
    (FACE_CENTER[0], FACE_CENTER[1] + HALF_HEAD + SECTION_LINE_OVERRUN),
)


def _section_x(station_mm: float) -> float:
    """Sheet X of a model-Y station (from the seat face) on the section,
    seat face right."""
    return SECTION_CENTER[0] + (OVERALL_LENGTH / 2.0 - station_mm) * _S / 1000.0


def _section_y(radius_mm: float) -> float:
    """Sheet Y of a model-X offset from the axis on the section."""
    return SECTION_CENTER[1] + radius_mm * _S / 1000.0


SEAT_X = _section_x(0.0)
RIM_X = _section_x(OVERALL_LENGTH)
HEAD_TOP = _section_y(HEAD_DIA / 2.0)
HEAD_BOTTOM = _section_y(-HEAD_DIA / 2.0)

# A horizontal dimension's line prints this far below its text anchor (run
# 20261101T070124857Z: the then-horizontal Ø.43 and Ø.49 lines printed 3.0
# and 2.8 mm under their anchors), so a length's anchor stands that much
# above the lane its line should take.
DIM_LINE_BELOW_TEXT = 0.0029
# The baseline lengths' lines above the knurl, from the seat face: flange
# (inner), the head's rear face, the overall length (outer).
LENGTH_LANES = (0.009, 0.019, 0.029)


def _length_anchor(station_mm: float, lane: float) -> tuple[float, float]:
    """Text anchor of a seat-face length to ``station_mm``, its text mid-span
    and its line ``lane`` above the knurl."""
    return (
        (SEAT_X + _section_x(station_mm)) / 2.0,
        HEAD_TOP + lane + DIM_LINE_BELOW_TEXT,
    )


# The rim's diameters stand left of the rim, the knurl outermost, so each
# one's extension lines stay inside the next one's; the knurl's two-row
# text sits inside its own span, left of the dish's lines, and the dish's
# two values stagger about the axis.  A vertical diameter's line runs
# through its text's centre (the .63 on run 20261107T201806645Z).  The
# flange and the waist are dimensioned across their own cut, each line at its
# feature's middle and its text below the part: an extension line run past
# the seat or the head would cross another feature's hatching.  The cone
# diameter's line stands just right of the seat face, its text below the
# waist's; the dish depth hangs under the rim.
HEAD_DIA_LINE_X = RIM_X - 0.054
DISH_DIA_LINE_X = RIM_X - 0.018
DISH_FLOOR_DIA_LINE_X = RIM_X - 0.008
FLANGE_TEXT_Y = _section_y(-FLANGE_DIA / 2.0) - 0.010
WAIST_TEXT_Y = HEAD_BOTTOM - 0.010
CSK_LINE_X = SEAT_X + 0.008
CSK_TEXT_Y = HEAD_BOTTOM - 0.021


def _stem_dia_anchor(lo_mm: float, hi_mm: float, text_y: float) -> tuple[float, float]:
    """Text anchor whose vertical dimension line runs mid-way along a stem
    feature, its text below the part at ``text_y``."""
    return (_section_x((lo_mm + hi_mm) / 2.0), text_y)


# Section A-A's caption hangs under the cone diameter's two rows.
CAPTION_BELOW_HEAD = 0.035


SECTION_KEEP = {
    "HeadDia": (HEAD_DIA_LINE_X, SECTION_CENTER[1]),
    "DishDia": (DISH_DIA_LINE_X, SECTION_CENTER[1] - 0.006),
    "DishFloorDia": (DISH_FLOOR_DIA_LINE_X, SECTION_CENTER[1] + 0.006),
    "DishDepth": (RIM_X - 0.004, HEAD_BOTTOM - 0.016),
    "FlangeLength": _length_anchor(FLANGE_LENGTH, LENGTH_LANES[0]),
    "HeadRearY": _length_anchor(HEAD_REAR_Y, LENGTH_LANES[1]),
    "OverallLength": _length_anchor(OVERALL_LENGTH, LENGTH_LANES[2]),
    "FlangeDia": _stem_dia_anchor(0.0, FLANGE_LENGTH, FLANGE_TEXT_Y),
    "WaistDia": _stem_dia_anchor(FLANGE_LENGTH, HEAD_REAR_Y, WAIST_TEXT_Y),
    "CountersinkDia": (CSK_LINE_X, CSK_TEXT_Y),
}
# The baseline lengths' spans hold their text and arrows: inside, so no
# arrow hangs past the seat face (run 20261024T025840809Z).  The knurl
# diameter's too: arrows outside, its line ran on past the extension line
# under the wide knurl callout (machinist review round 3); the Ø.81 span
# holds its arrows.
ARROWS_INSIDE = ("FlangeLength", "HeadRearY", "HeadDia")
_DIM_ARROWS_INSIDE = 0  # swDimensionArrowsSide_e.swDimArrowsInside
# The native caption's top centre, under the countersink callout.
SECTION_CAPTION_XY = (SECTION_CENTER[0], HEAD_BOTTOM - CAPTION_BELOW_HEAD)
# The face view prints only the native thread callout.
FACE_KEEP: dict[str, tuple[float, float]] = {}
# Above the knurl diameter's value: one row of the knurl designation.
# "OVER KNURL" is the value's suffix.
DIMENSION_CALLOUTS_ABOVE = {"HeadDia": KNURL_CALLOUT}
# The countersink in symbol form (rule 26): size, then the included angle;
# the cone half-angle the part marks is not printed separately.  A custom
# prefix replaces the native Ø glyph, so it carries SolidWorks' own token.
DIMENSION_CALLOUTS_BELOW = {"CountersinkDia": "BOTH ENDS"}
DIMENSION_PREFIXES = {"CountersinkDia": "<HOLE-SINK><MOD-DIAM>"}
DIMENSION_SUFFIXES = {
    "HeadDia": KNURL_DIA_SUFFIX,
    "CountersinkDia": f"{CSK_DIA_SUFFIX} X {CSK_INCLUDED_ANGLE_DEG:.0f}°",
}
_DIMENSION_TEXT_PREFIX = 1  # swDimensionTextParts_e.swDimensionTextPrefix
_DIMENSION_TEXT_SUFFIX = 2  # swDimensionTextParts_e.swDimensionTextSuffix


def _printable_above_callouts(callouts: dict[str, str]) -> dict[str, str]:
    """Refuse an above-callout SolidWorks would keep but not print.

    A line break in the above compartment is stored (``GetDisplayData`` reads
    it back) yet nothing of the callout reaches the PDF: the two-line knurl
    designation over Ø20.5 (run 20261001T154021634Z) and the drive collar's
    two-line slot callout (run 20261001T151531763Z) both went unprinted,
    while one-line above callouts ("2X") print.
    """
    broken = sorted(name for name, text in callouts.items() if "\n" in text)
    if broken:
        raise RuntimeError(f"above-callouts with a line break do not print: {broken}")
    return callouts


# Up and left of the face view, so its leader runs in diagonally to the hole
# rather than along the vertical cutting line (machinist review round 2), and
# its widest line stays inside the left border.
THREAD_CALLOUT_XY = (FACE_CENTER[0] - 0.020, FACE_CENTER[1] + 0.062)
# How far the section's axis centreline runs past the seat face and the rim
# (model mm).
AXIS_OVERSHOOT_MM = 1.0
_SW_LINE_CENTER = 4  # swLineStyles_e.swLineCENTER

# How far A-A's axis may sit from where SECTION_KEEP assumes it, or off
# level, before it is moved or refused (sheet metres).
_SECTION_POSITION_TOL = 1e-4


def _turn_face_view(adapter: Any, face: Any) -> None:
    """Turn the face view a quarter so the cut on its vertical centreline is
    the Front plane (``FACE_VIEW_ANGLE``; draw_pd_transgear_knob_cup)."""
    native = _early_bound(face, "IView")
    native.Angle = FACE_VIEW_ANGLE
    if abs(math.remainder(float(native.Angle) - FACE_VIEW_ANGLE, 2.0 * math.pi)) > 1e-9:
        raise RuntimeError("failed to turn the thumbnut face view a quarter")
    rebuild_drawing(adapter, label="thumbnut face view turned")


def _axis_turn(seat: tuple[float, float], rim: tuple[float, float]) -> float:
    """The sheet angle of the rim-to-seat direction: 0 when the axis lies
    horizontal with the seat face right."""
    return math.atan2(seat[1] - rim[1], seat[0] - rim[0])


def _orient_section(adapter: Any, section: Any) -> None:
    """Lay A-A axis-horizontal, seat face right, its axis on SECTION_CENTER.

    Cut from the quarter-turned face view, A-A lies axis-horizontal; which
    end the seat takes is read, not assumed, and a half turn (no change to a
    solid of revolution's section) puts it on the right.  Any other turn
    means the cut is not the expected projection: refuse it.  The view is
    then moved by the axis's miss from where SECTION_KEEP puts it:
    ``SetViewPosition`` moves the ink by the difference from the Position it
    reads (run 20261001T142942518Z), so each pass moves by the measured miss
    and re-reads.
    """
    native = _early_bound(section, "IView")
    seat, rim = _seat_and_rim(adapter, native)
    turn = _axis_turn(seat, rim)
    if abs(turn) > 1e-6:
        if abs(abs(turn) - math.pi) > 1e-6:
            raise RuntimeError(
                f"thumbnut A-A axis runs {math.degrees(turn):.3f} deg off the "
                f"sheet's horizontal (seat {seat}, rim {rim})"
            )
        native.Angle = float(native.Angle) - turn
        rebuild_drawing(adapter, label="thumbnut section turned")
        seat, rim = _seat_and_rim(adapter, native)
    expected = ((SEAT_X, SECTION_CENTER[1]), (RIM_X, SECTION_CENTER[1]))
    for attempt in range(4):
        if all(
            math.dist(actual, wanted) <= _SECTION_POSITION_TOL
            for actual, wanted in zip((seat, rim), expected, strict=True)
        ):
            break
        middle = ((seat[0] + rim[0]) / 2.0, (seat[1] + rim[1]) / 2.0)
        position = tuple(float(value) for value in native.Position)
        moved = [
            position[axis] + SECTION_CENTER[axis] - middle[axis] for axis in (0, 1)
        ]
        _telemetry.info(
            f"thumbnut section pass {attempt}: position={position} seat={seat} rim={rim}"
        )
        if not native.SetViewPosition(double_array(moved), False):
            raise RuntimeError("failed to centre thumbnut section A-A")
        rebuild_drawing(adapter, label="thumbnut section centred")
        seat, rim = _seat_and_rim(adapter, native)
    else:
        raise RuntimeError(
            f"thumbnut A-A axis ends at seat {seat}, rim {rim}; wanted {expected}"
        )
    _telemetry.info(
        f"thumbnut A-A axis horizontal: angle={float(native.Angle):.6f} rad, "
        f"turn={turn:.6f}, seat={seat}, rim={rim}"
    )


def _seat_and_rim(
    adapter: Any, view: Any
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Sheet points of the seat face and the rim on the nut axis."""
    seat = model_point_in_view(adapter, view, (0.0, 0.0, 0.0), label="thumbnut seat")
    rim = model_point_in_view(
        adapter, view, (0.0, OVERALL_LENGTH / 1000.0, 0.0), label="thumbnut rim"
    )
    return seat, rim


def _assert_native_thread(display: Any) -> None:
    """Read the real Hole Wizard callout; never substitute typed dimensions."""
    display = _early_bound(display, "IDisplayDimension")
    texts = [display.GetText(part) for part in (1, 2, 3, 4)]
    if any(not isinstance(text, str) for text in texts):
        raise RuntimeError("thumbnut native thread callout has an invalid readback")
    resolved = "".join(texts).replace(" ", "").replace("#", "").upper()
    if THREAD.replace("#", "") not in resolved or "UNC" not in resolved or "2B" not in resolved:
        raise RuntimeError(f"thumbnut native thread callout does not carry the source thread: {texts!r}")


@_telemetry.traced("drawing.thumbnut.tap_callout_thread_class")
def _omit_thread_class(display: Any) -> None:
    """Rule 2: the title block's THREADS row owns class 2B; the native tap
    variables stay live (draw_dt_cone_swing_platform's pattern).  Run
    20261024T041438788Z's review gated on the callout restating it."""
    if TAP_SPEC.thread_class != "2B":
        raise RuntimeError(
            "thumbnut tap: only the title block's default class 2B may be "
            f"omitted, got {TAP_SPEC.thread_class!r}"
        )
    omit_title_block_thread_class(display, label="thumbnut #8-32 tap")
    native = _early_bound(display, "IDisplayDimension")
    resolved = [str(native.GetText(part) or "") for part in (1, 2, 3, 4)]
    if any(TAP_SPEC.thread_class in text for text in resolved):
        raise RuntimeError(f"thumbnut tap callout still prints its class: {resolved!r}")


def _set_dimension_affixes(adapter: Any, annotations: list[Any]) -> None:
    """Write each DIMENSION_PREFIXES / DIMENSION_SUFFIXES text, read back."""
    remaining = {
        (name, part): text
        for part, texts in (
            (_DIMENSION_TEXT_PREFIX, DIMENSION_PREFIXES),
            (_DIMENSION_TEXT_SUFFIX, DIMENSION_SUFFIXES),
        )
        for name, text in texts.items()
    }
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        name = dimension_name(adapter, annotation)
        for key in [key for key in remaining if key[0] == name]:
            text = remaining.pop(key)
            display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
            display.SetText(key[1], text)
            if str(display.GetText(key[1]) or "") != text:
                raise RuntimeError(f"thumbnut {name} text {text!r} did not persist")
    if remaining:
        raise RuntimeError(f"no thumbnut dimension for affixes: {sorted(remaining)}")


def _pin_sheet_scale(adapter: Any) -> None:
    """Hold the sheet at its printed 3:1 before section A-A is cut.

    Placing a model view drifts the sheet scale, and a native section caption
    carries a scale field when its view's scale differs from the sheet's at
    creation (draw_fr_top_frame._pin_sheet_scale): the screen review read
    SECTION A-A's "SCALE 3 : 1" as restating the title block (rule 9).
    """
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    sheet = adapter._get_attr_or_call(ddoc, "GetCurrentSheet")
    if sheet is None:
        raise RuntimeError("no active thumbnut sheet to pin before section A-A")
    if not sheet.SetScale(SHEET_SCALE[0], SHEET_SCALE[1], False, False):
        raise RuntimeError("failed to pin the thumbnut sheet at 3:1")
    properties = list(adapter._get_attr_or_call(sheet, "GetProperties2") or [])
    if len(properties) < 4 or (float(properties[2]), float(properties[3])) != SHEET_SCALE:
        raise RuntimeError(f"thumbnut sheet scale did not persist: {properties!r}")


@_telemetry.traced("drawing.thumbnut.arrows_inside")
def _set_arrows_inside(adapter: Any, annotations: list[Any]) -> None:
    """Stand each ARROWS_INSIDE dimension's arrows inside its extension lines,
    read back (draw_mg_magnifying_wheel's _set_arrows_inside)."""
    remaining = set(ARROWS_INSIDE)
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        name = dimension_name(adapter, annotation)
        if name not in remaining:
            continue
        remaining.discard(name)
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.ArrowSide = _DIM_ARROWS_INSIDE
        if int(display.ArrowSide) != _DIM_ARROWS_INSIDE:
            raise RuntimeError(f"thumbnut {name} did not keep its arrows inside")
    if remaining:
        raise RuntimeError(f"no thumbnut dimension to set arrows inside: {sorted(remaining)}")


def _sheet_sketch_point(sheet_xy: tuple[float, float]) -> tuple[float, float]:
    """Sheet-sketch coordinates of a printed sheet point on this 3:1 sheet.

    The sheet sketch draws at the sheet scale: run 20261101T054343686Z
    passed the projected axis (x 0.110) straight in, and the line printed at
    x 0.330, three times out, from the top border down onto the isometric
    (machinist review round 3, the gating finding)."""
    return (sheet_xy[0] / _S, sheet_xy[1] / _S)


@_telemetry.traced("drawing.thumbnut.section_axis")
def _add_section_axis(adapter: Any, section: Any) -> None:
    """Draw the nut's axis through section A-A, past the seat and the rim.

    A short stub of the countersink sketch's axis left the reader to infer
    the cone's reference (machinist review round 2).  The ends are the model
    axis projected through the section's own transform
    (draw_dt_cone_pivot_post's section axis), so the line is the axis itself
    whichever way the section was turned to lie seat right.
    """
    overshoot = AXIS_OVERSHOOT_MM / 1000.0
    ends = [
        model_point_in_view(adapter, section, (0.0, y, 0.0), label=f"thumbnut axis {name}")
        for name, y in (
            ("past the seat", -overshoot),
            ("past the rim", OVERALL_LENGTH / 1000.0 + overshoot),
        )
    ]
    if abs(ends[0][1] - ends[1][1]) > 1e-6 or ends[0][0] <= ends[1][0]:
        raise RuntimeError(f"thumbnut section axis is not horizontal seat right: {ends!r}")
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    # EditSheet makes the line sheet-owned.
    drawing.EditSheet()
    sketch_manager = _early_bound(adapter.currentModel.SketchManager, "ISketchManager")
    (x0, y0), (x1, y1) = (_sheet_sketch_point(end) for end in ends)
    centerline = sketch_manager.CreateCenterLine(x0, y0, 0.0, x1, y1, 0.0)
    if centerline is None:
        raise RuntimeError("failed to create the thumbnut axis in section A-A")
    # A sheet sketch line otherwise prints in the under-defined sketch blue.
    segment = _early_bound(centerline, "ISketchSegment")
    segment.Color = 0  # COLORREF black
    segment.Style = _SW_LINE_CENTER
    adapter.currentModel.ClearSelection2(True)
    rebuild_drawing(adapter, label="thumbnut section axis")
    if int(segment.Color) != 0 or int(segment.Style) != _SW_LINE_CENTER:
        raise RuntimeError(
            "thumbnut section axis did not keep black centerline font: "
            f"color={int(segment.Color)}, style={int(segment.Style)}"
        )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open thumbnut source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
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
            0: "Transgear Thumbnut Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "transgear thumbnut; turned and knurled brass",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    face = place_view(adapter, str(SOURCE), "*Top", *FACE_CENTER, scale=VIEW_SCALE)
    _turn_face_view(adapter, face)
    _pin_sheet_scale(adapter)
    section = create_section_view(
        adapter,
        face,
        line_start=SECTION_LINE[0],
        line_end=SECTION_LINE[1],
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=VIEW_SCALE,
        label="thumbnut axial section",
    )
    _orient_section(adapter, section)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (face, section, iso):
        set_hidden_lines_removed(adapter, view)

    face_annotations = curate_view_dimensions(
        adapter,
        face,
        keep=FACE_KEEP,
        view_label="face",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    section_annotations = curate_view_dimensions(
        adapter,
        section,
        keep=SECTION_KEEP,
        view_label="axial section",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Decimal places (and so the general-tolerance row each dimension claims)
    # are authored on the part; the sheet only proves the import kept them
    # on the dimensions it prints (the half angle is curated away: the
    # countersink callout states its 90°).
    assert_imported_precision(
        adapter,
        [*face_annotations, *section_annotations],
        {
            name: places
            for name, places in DRAWING_PRECISION_BY_NAME.items()
            if name in FACE_KEEP or name in SECTION_KEEP
        },
    )
    set_dimension_callouts(
        adapter,
        section_annotations,
        _printable_above_callouts(DIMENSION_CALLOUTS_ABOVE),
        location="above",
    )
    set_dimension_callouts(
        adapter, section_annotations, DIMENSION_CALLOUTS_BELOW, location="below"
    )
    _set_dimension_affixes(adapter, section_annotations)
    _set_arrows_inside(adapter, section_annotations)
    position_section_caption(
        adapter, section, SECTION_CAPTION_XY, label="thumbnut section A-A"
    )
    if not auto_center_marks(adapter, face, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the thumbnut face view")
    _add_section_axis(adapter, section)
    # The tap-drill edge under the front countersink: the one visible circle
    # of the Hole Wizard feature from the front.
    thread_callout = add_native_hole_callout(
        adapter,
        face,
        edge=visible_circle_edge(adapter, face, TAP_DRILL_DIA),
        callout_xy=THREAD_CALLOUT_XY,
        label=f"{THREAD} UNC-2B through thread",
    )
    _assert_native_thread(thread_callout)
    _omit_thread_class(thread_callout)
    set_hole_callout_precision(
        thread_callout, {"hw-thrutapdrldia": 3}, label=f"{THREAD} through thread"
    )

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Transgear Thumbnut Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        # SolidWorks pins its own tapped-hole note to the face view once the
        # real native callout exists; it repeats the thread the callout
        # states, and it sat on the tap drill, so the callout's radial leader
        # crossed it (run 20261001T151531763Z).  finalize removes it before
        # its layout audit.
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
