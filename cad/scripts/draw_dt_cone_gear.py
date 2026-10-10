r"""Create the complete cone-gear batch drawing package (MHA-DT-003).

Every configured family member T006..T120 by six receives a standalone sheet.
Each sheet selects its own part configuration, imports the native model-owned
blank diameter, D-bore (diameter, across-flat and flat clock), face width,
driving circular-tooth-thickness requirement and functional root-envelope
limits, plus the actual finite cutter recipe and bounded carrying-contact data.
The native imported bands remain model-owned. A separate DT6-FORM1 sheet
defines the complete custom tool grind from model-stamped core equations.

There are no datums or feature-control frames.  Hidden lines communicate no
additional manufacturing fact on these through-bored spur gears, so every view
remains hidden-lines-removed.  The one finish symbol belongs to the fitted
bore.  The side view stays in projection with the front view's bore axis; its
face width hangs below it, clear of the Gear Data block. The circular pitch
thickness uses a construction inspection witness of the actual arc size, not
an ideal chord oracle; root MIN/MAX use the actual radial-envelope witness.
The D-bore prints in an enlarged bore view, a cropped *Front model view at a
scale that renders every bore at least ``BORE_VIEW_BORE_MIN`` across (its flat
is 0.13 deep on T006 and T012); both views centre-mark the bore.  The part
saves both construction sketches hidden; only the front view, which
dimensions them, shows them.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _drawing_hidden_sketches as hidden_sketches
import _telemetry
from _common import CAD_ROOT, _early_bound, _read_member, check, run_build
from _drawing_leaders import ARROW_TEXT_CLEARANCE
from _drawing_common import (
    _INSERT_DIMS_MARKED,
    DrawingOutputs,
    add_note,
    add_property_linked_note,
    add_surface_finish,
    assert_imported_precision,
    check_drawing_layout,
    create_blank_drawing_sheets,
    curate_dimensions,
    delete_unnamed_imports,
    dimension_name,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
    view_name,
    visible_view_entities,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _fit_limits import deviations
from _layout_audit import arc_segments
from _surface_finish import surface_finish_by_key
from build_dt_cone_gear import (
    assert_saved_configuration_topology,
    gap_floor_deviations_mm,
)
from dt_cone_gear_notes import CUTTER_DETAIL_SHEET
from dt_cone_gear_spec import (
    BORE_SURFACE_FINISHES,
    CONFIGURATION_TEETH,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FACE_WIDTH,
    bore_dia_mm,
    blank_dia_band,
    tooth_thickness_band,
    bore_flat_offset_mm,
    floor_limits_mm,
    outside_dia_mm,
    tooth_thickness_mm,
    stock_form_profile,
)
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import place_view


SPEC = DRAWINGS_BY_NAME["dt_cone_gear"]
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

GEAR_SHEET_NAMES = tuple(f"T{teeth:03d}" for teeth in CONFIGURATION_TEETH)
SHEET_NAMES = (*GEAR_SHEET_NAMES, CUTTER_DETAIL_SHEET)
# Discrete standard ratios keep both the tip and common face width legible.
# The enlarged T120 blank takes 1:1 so its view stays in the existing lanes.
_SCALE_BY_TEETH = {
    6: (8.0, 1.0),
    12: (6.0, 1.0),
    18: (5.0, 1.0),
    24: (4.0, 1.0),
    30: (3.0, 1.0),
    36: (3.0, 1.0),
    42: (3.0, 1.0),
    48: (5.0, 2.0),
    54: (5.0, 2.0),
    60: (2.0, 1.0),
    66: (2.0, 1.0),
    72: (2.0, 1.0),
    78: (2.0, 1.0),
    84: (2.0, 1.0),
    90: (3.0, 2.0),
    96: (3.0, 2.0),
    102: (3.0, 2.0),
    108: (3.0, 2.0),
    114: (3.0, 2.0),
    120: (1.0, 1.0),
}
SHEET_SCALES = {
    f"T{teeth:03d}": _SCALE_BY_TEETH[teeth] for teeth in CONFIGURATION_TEETH
} | {CUTTER_DETAIL_SHEET: (20.0, 1.0)}
SHEET_SCALE = SHEET_SCALES[SHEET_NAMES[0]]

FRONT_CENTER = (0.105, 0.150)
# Projection-aligned with the front view's bore axis (codex, 2026-09-23: the
# 0.140 offset that cleared FaceWidth from Gear Data broke the alignment).
RIGHT_CENTER = (0.245, FRONT_CENTER[1])
ISO_CENTER = (0.355, 0.150)
# The D-bore prints in its own enlarged view: a *Front model view of the
# sheet's configuration, cropped by a circle round the bore (the MHA-VN-031
# pattern of draw_amplitude_bar and draw_pinion_arbor; their native detail
# views would not take moved or imported dimensions).  At sheet scale the
# flat is 0.76-2.3 mm deep, 1.02 mm on T006's 8:1; enlarged, 2.5-3.1 mm.
# The view sits lower left, under the front view and left of the thickness
# callout, and carries every bore dimension: diameter, across-flat, clock.
# The layout audit compares view OUTLINES, not circles: GetOutline pads the
# front view ~5.5 mm and a cropped view 10.1-10.75 mm past its crop circle
# (farm run 20260929T061328212Z at 70d2e52: T084's front box [54.8, 99.8, 155.2,
# 200.2] met this view's [15.2, 29.2, 88.8, 102.8] when it stood at y 0.066
# with a 7 mm margin). At y 0.060 with 3 mm the box clears T120's, the
# largest tip circle on the set, by ~4 mm and the title stays above the
# 12.7 mm zone band.
BORE_VIEW_CENTER = (0.052, 0.060)
# Each sheet takes the smallest useful ladder ratio above its own, reading the
# current web-qualified terminal land rather than assuming the old 1/16 seat.
BORE_VIEW_BORE_MIN = 0.028
BORE_VIEW_SCALE_LADDER = (
    (4.0, 1.0), (5.0, 1.0), (10.0, 1.0), (20.0, 1.0), (40.0, 1.0),
)
# Gear body kept round the bore inside the crop circle, sheet metres.
BORE_VIEW_CROP_MARGIN = 0.003
# The view's title stands this far under the crop circle, below the
# across-flat value and its dimension line, which hang BORE_VIEW_AF_DROP under
# it.
BORE_VIEW_AF_DROP = 0.005
BORE_VIEW_LABEL_DROP = 0.016
# The across-flat text stands OUTSIDE its witnesses, right of the flat's, as
# MHA-DT-007's does. Centred between them, its lines (~2.65 mm a character in
# the #1128 full-5 render) ran wider than the 29-35 mm witness span on every
# sheet, so both witness lines crossed the callout, and its tolerance stack
# sat on the diameter leader's lower end (machinist review of full-5).
# BORE_VIEW_AF_HALF_WIDTH is half the widest line, BORE ACROSS FLAT, rounded
# up; the text's left edge clears the flat's witness by BORE_VIEW_AF_GAP.
BORE_VIEW_AF_GAP = 0.004
BORE_VIEW_AF_HALF_WIDTH = 0.022
# The bore axis must land within 0.1 mm of BORE_VIEW_CENTER after the move
# (draw_amplitude_bar's detail tolerance), and the title within 1 mm.
BORE_VIEW_POSITION_TOL_M = 1e-4
NOTE_CENTRING_TOL_M = 0.001
CROP_NO_ERROR = 1  # swCropViewErrors_e.swCropViewErrors_NoError
CENTER_MARK_SINGLE = 2  # swCenterMarkStyle_e.swCenterMark_Single
# Imported, the flat clock keeps its sketch's quadrant (between the flat's
# upper half and the -X centreline) wherever its text goes. Its arc then
# swept the diameter's upper-left leader lane, and on the 4:1 sheets it
# crossed that leader's shoulder (T030-T120, run 20260929T064504232Z).
# ``_sweep_clock_right_of_flat`` flips it into the quadrant right of the
# flat and above the axis. Its arc may overrun the flat or the axis by
# CLOCK_ARC_OVERRUN and must centre on the flat/axis crossing within
# CLOCK_ARC_CENTRE_TOL (sheet metres).
CLOCK_ARC_OVERRUN = 0.0003
CLOCK_ARC_CENTRE_TOL = 0.0005
CLOCK_FLIPS = ("SupplementaryAngle", "VerticallyOppositeAngle", "SupplementaryAngle")
# Fifteen compact data lines retain the measured 3.51 mm line-height budget.
# The dedicated custom-tool sheet keeps exact grinding equations out of these
# dimension/view lanes.
GEAR_DATA_POS = (0.215, 0.263)
# Rendered height/width budget of the Gear Data block, for the layout test.
GEAR_DATA_HEIGHT = 0.056
GEAR_DATA_MAX_LINE_CHARS = 66
MANUFACTURING_NOTES_POS = (0.015, 0.263)
SHEET_COUNT_POS = (0.350, 0.263)
CUTTER_DETAIL_POS = (0.015, 0.263)
CUTTER_DETAIL_VIEW_CENTER = (0.325, 0.155)


def cutter_detail_window_mm() -> tuple[float, float, float]:
    """Bound the installed T006 material-facing gap for its native cropped view."""
    profile = stock_form_profile(6)
    radial_midpoint = (profile.root_radius_min_mm + profile.blank_radius_mm) / 2.0
    phase = math.pi / profile.teeth
    cosine, sine = math.cos(phase), math.sin(phase)
    center = radial_midpoint, 0.0
    samples = 32
    radius = 0.0
    for segment in profile.gap_segments():
        if segment.kind == "tip_arc":
            continue
        # Core's second-derivative bound pays the unsampled chord sagitta.
        deviation = segment.second_derivative_bound_mm / (8.0 * samples**2)
        radius = max(radius, max(
            math.dist(center, segment.point(index / samples))
            for index in range(samples + 1)
        ) + deviation + profile.geometry_error_bound_mm)
    return cosine * radial_midpoint, sine * radial_midpoint, radius + 0.15


DIMENSION_CALLOUTS = {
    # No process word: a reamer would cut away the flat, and the dimensions
    # define the D-profile (user ruling 2026-09-29, machinist review of the
    # #1128 full build).
    "BoreCutDia": "THRU",
    # The value is the gear bore's own; naming the bore, not the shaft it
    # slides on, keeps it from reading as MHA-DT-004's across-flat.
    "BoreAF": "BORE ACROSS FLAT",
    # The flat's normal runs through the bore axis and the +X tooth's centre;
    # the bore view crops the teeth off, so the callout names the reference
    # its centre-mark line stands for.
    "BoreFlatClock": "TO TOOTH CENTERLINE",
    # Pitch diameter, backlash and mate already live in the Gear Data block.
    # Repeating them here made the long suffix collide with the bore callout.
    "ToothThickness": "CIRCULAR TOOTH THICKNESS",
    # The origin circle is an inspection witness, not the off-centre root arc.
    "FloorDia": "ROOT ENVELOPE",
}


def rendered_half_od(teeth: int) -> float:
    numerator, denominator = _SCALE_BY_TEETH[teeth]
    return outside_dia_mm(teeth) * numerator / (denominator * 2000.0)


def rendered_half_face_width(teeth: int) -> float:
    numerator, denominator = _SCALE_BY_TEETH[teeth]
    return FACE_WIDTH * numerator / (denominator * 2000.0)


# BlankDia's value stands this far above the tip circle.  At 0.012 the T006
# value (8:1) sat on the vertical centre-mark line, which reaches 26.3 mm
# above the bore axis on that sheet (layout audit, 0.82 mm overlap); 0.0145
# clears it, and no other text on any sheet is within 36 mm above the value.
BLANK_DIA_LIFT = 0.0145
# The functional root-envelope stack stands right of the tip circle,
# above the thickness witness: in the same lane as the thickness
# dimension line, which runs DOWN from the +X tooth, and clear of the side
# view (left edge >= 0.219 on every sheet).
FLOOR_DIA_GAP_X = 0.016
FLOOR_DIA_RISE = 0.006
# The thickness dimension's arrows stand outside its witnesses, so the upper
# arrow's tail runs UP the stack's lane: on the 834-fix-6927 T006 sheet (8:1)
# it crossed the shelf under "GAP FLOOR" by ~1 mm.  The shelf therefore rises
# per sheet to clear that tail (``floor_dia_y``).
#
# swUserPreferenceDoubleValue_e.swDetailingArrowLength (swconst.tlb R2026x),
# read with swDetailingNoOptionSpecified: how far the dimension line runs past
# an outside arrow's tip, head and tail together.
_PREF_ARROW_LENGTH = 26
_PREF_OPT_NONE = 0
# The project DRWDOT's value (0.25 in).  The 834-fix-6927 T006 sheet prints
# the thickness arrow 6.35 mm from tip to tail end; build() reads the live
# preference and refuses a template that differs.
DIMENSION_ARROW_LENGTH = 0.00635
# The limit stack hangs 7.2 mm from its anchor down to the shelf line (three
# rows at a ~4.9 mm pitch, same sheet), rounded outward; it is centred on the
# anchor, so the same half-height bounds its top.
FLOOR_STACK_HALF_HEIGHT = 0.0075


def thickness_arrow_reach_y(teeth: int) -> float:
    """Sheet y where the thickness dimension's upper arrow tail ends.

    The upper witness stands half the tooth thickness above the bore axis at
    sheet scale (the arc thickness, an upper bound on the pitch chord it
    witnesses), and one outside arrow runs on past it.
    """
    numerator, denominator = _SCALE_BY_TEETH[teeth]
    half_thickness = tooth_thickness_mm(teeth) * numerator / (denominator * 2000.0)
    return FRONT_CENTER[1] + half_thickness + DIMENSION_ARROW_LENGTH


def floor_dia_y(teeth: int) -> float:
    """Anchor y of the gap-floor stack: its usual place above the thickness
    witness, raised where that would put the shelf within the fleet's
    arrow-to-text clearance of the thickness arrow's tail."""
    usual = FRONT_CENTER[1] + 0.6 * rendered_half_od(teeth) + FLOOR_DIA_RISE
    lowest = thickness_arrow_reach_y(teeth) + ARROW_TEXT_CLEARANCE + FLOOR_STACK_HALF_HEIGHT
    return max(usual, lowest)


def _assert_dimension_arrow_length(drawing: Any) -> None:
    """Refuse a template whose arrow length is not the one the layout assumes."""
    extension = _early_bound(
        _early_bound(drawing, "IModelDoc2").Extension, "IModelDocExtension"
    )
    live = float(extension.GetUserPreferenceDouble(_PREF_ARROW_LENGTH, _PREF_OPT_NONE))
    if abs(live - DIMENSION_ARROW_LENGTH) > 1e-6:
        raise RuntimeError(
            f"drawing arrow length reads {live * 1000.0:.3f} mm; the gap-floor "
            f"stack is placed for {DIMENSION_ARROW_LENGTH * 1000.0:.3f} mm"
        )
    _telemetry.info(f"drawing arrow length {live * 1000.0:.3f} mm")


def front_keep(teeth: int) -> dict[str, tuple[float, float]]:
    half_od = rendered_half_od(teeth)
    return {
        "FloorDia": (FRONT_CENTER[0] + half_od + FLOOR_DIA_GAP_X, floor_dia_y(teeth)),
        "BlankDia": (FRONT_CENTER[0], FRONT_CENTER[1] + half_od + BLANK_DIA_LIFT),
        # Vertical dimension on the +X tooth: its line stands at the text x,
        # just right of the tip circle, and runs down to the text below the
        # gear's lowest point (the ~65 mm callout stays left of the side view).
        "ToothThickness": (
            FRONT_CENTER[0] + half_od + 0.014,
            FRONT_CENTER[1] - half_od - 0.025,
        ),
    }


def bore_view_scale(teeth: int) -> tuple[float, float]:
    """The bore view's ratio: the smallest ladder ratio above the sheet's own
    that renders the bore at least ``BORE_VIEW_BORE_MIN`` across."""
    sheet_numerator, sheet_denominator = _SCALE_BY_TEETH[teeth]
    sheet_ratio = sheet_numerator / sheet_denominator
    for numerator, denominator in BORE_VIEW_SCALE_LADDER:
        ratio = numerator / denominator
        if ratio > sheet_ratio and bore_dia_mm(teeth) * ratio / 1000.0 >= BORE_VIEW_BORE_MIN:
            return numerator, denominator
    raise ValueError(f"no bore-view scale renders the T{teeth:03d} bore legibly")


def _bore_view_ratio(teeth: int) -> float:
    numerator, denominator = bore_view_scale(teeth)
    return numerator / denominator


def bore_view_crop_radius(teeth: int) -> float:
    """Sheet radius of the bore view's crop circle round the bore axis."""
    return bore_dia_mm(teeth) * _bore_view_ratio(teeth) / 2000.0 + BORE_VIEW_CROP_MARGIN


def bore_flat_vertex(teeth: int) -> tuple[float, float]:
    """Sheet point where the flat crosses the bore's horizontal centreline:
    the clock dimension's vertex."""
    flat = bore_flat_offset_mm(teeth) * _bore_view_ratio(teeth) / 1000.0
    return BORE_VIEW_CENTER[0] + flat, BORE_VIEW_CENTER[1]


def bore_view_keep(teeth: int) -> dict[str, tuple[float, float]]:
    """Text positions of the three bore dimensions round the bore view.

    The diameter's leader runs in from upper left; the across-flat's
    dimension line hangs under the crop circle between its witnesses (the
    arc's -X point and the flat) and runs on right to its text, which stands
    outside the flat's witness; the clock's arc sweeps the quadrant between
    the flat's upper half and the +X centre-mark line
    (``_sweep_clock_right_of_flat``), its text right of the circle and just
    above the axis, where the front view's thickness callout (above right,
    x 134-164 y 78-108 mm) never reaches.
    """
    ratio = _bore_view_ratio(teeth)
    flat = bore_flat_offset_mm(teeth) * ratio / 1000.0
    crop = bore_view_crop_radius(teeth)
    x, y = BORE_VIEW_CENTER
    return {
        "BoreCutDia": (x - 0.022, y + crop + 0.006),
        "BoreAF": (
            x + flat + BORE_VIEW_AF_GAP + BORE_VIEW_AF_HALF_WIDTH,
            y - crop - BORE_VIEW_AF_DROP,
        ),
        "BoreFlatClock": (x + crop + 0.024, y + 0.006),
    }


def bore_view_label(teeth: int) -> str:
    numerator, denominator = bore_view_scale(teeth)
    return f"BORE PROFILE\nSCALE {numerator:g} : {denominator:g}"


def bore_view_label_top(teeth: int) -> float:
    return BORE_VIEW_CENTER[1] - bore_view_crop_radius(teeth) - BORE_VIEW_LABEL_DROP


def bore_finish_xy(teeth: int) -> tuple[tuple[float, float], tuple[float, float]]:
    """(bore edge pick, symbol anchor) for the upper-left bore finish.

    The +X tooth carries the thickness witness and the flat faces +X, so the
    finish leader lands on the bore's 135 deg arc point from a symbol
    above-left of the gear.
    """
    numerator, denominator = _SCALE_BY_TEETH[teeth]
    bore_radius = bore_dia_mm(teeth) * numerator / (denominator * 2000.0)
    half_od = rendered_half_od(teeth)
    diagonal = 0.5 ** 0.5
    edge = (
        FRONT_CENTER[0] - bore_radius * diagonal,
        FRONT_CENTER[1] + bore_radius * diagonal,
    )
    symbol = (
        FRONT_CENTER[0] - half_od * diagonal - 0.030,
        FRONT_CENTER[1] + half_od * diagonal + 0.006,
    )
    return edge, symbol


# Sheet width of the face-width text with its stacked band.  "6.00" over
# "+0.1/-0.1" measured ~19.4 mm on the conegear-834b render; "6.8887" over
# "+0.025/-0.025" has half as many characters again, so ~29 mm (scaled, not
# yet measured).  Where the face spans less than the text plus a clearance
# each side, the #834 machinist review found the text crowding its extension
# lines (sheets 5-20, 3:1 and below): the text then stands outside, right of
# the view, on the extended dimension line.
FACE_WIDTH_TEXT_WIDTH = 0.029
FACE_WIDTH_TEXT_CLEARANCE = 0.002


def face_width_text_inside(teeth: int) -> bool:
    return (
        2.0 * rendered_half_face_width(teeth)
        >= FACE_WIDTH_TEXT_WIDTH + 2.0 * FACE_WIDTH_TEXT_CLEARANCE
    )


def right_keep(teeth: int) -> dict[str, tuple[float, float]]:
    y = RIGHT_CENTER[1] - rendered_half_od(teeth) - 0.012
    if face_width_text_inside(teeth):
        return {"FaceWidth": (RIGHT_CENTER[0], y)}
    x = (
        RIGHT_CENTER[0]
        + rendered_half_face_width(teeth)
        + FACE_WIDTH_TEXT_CLEARANCE
        + FACE_WIDTH_TEXT_WIDTH / 2.0
    )
    return {"FaceWidth": (x, y)}


_TOL_LIMIT = 3  # swTolType_e.swTolLIMIT


def _assert_sheet_bands(
    adapter: Any, annotations: list[Any], configuration: str, teeth: int
) -> None:
    """Prove the sheet's gap-floor, blank and tooth-thickness dimensions carry
    THIS configuration's bands.

    One model dimension holds twenty LIMIT bands; the imported display
    dimension reads the band of its view's referenced configuration from the
    saved part, so this is the per-configuration readback after save and
    reopen.
    """
    floor = [a for a in annotations if dimension_name(adapter, a) == "FloorDia"]
    if len(floor) != 1:
        raise RuntimeError(
            f"{configuration}: expected one FloorDia on the sheet, found {len(floor)}"
        )
    display = _early_bound(
        _early_bound(floor[0], "IAnnotation").GetSpecificAnnotation(),
        "IDisplayDimension",
    )
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    kind = int(tolerance.Type)
    observed = (
        float(tolerance.GetMinValue()) * 1000.0,
        float(tolerance.GetMaxValue()) * 1000.0,
    )
    expected = gap_floor_deviations_mm(teeth)
    drifted = any(abs(o - e) > 1e-6 for o, e in zip(observed, expected))
    if kind != _TOL_LIMIT or drifted:
        raise RuntimeError(
            f"{configuration}: sheet FloorDia reads type {kind} {observed} mm, "
            f"expected LIMIT {expected} mm ({floor_limits_mm(teeth)})"
        )
    _telemetry.success(
        f"{configuration}: sheet gap-floor limits {floor_limits_mm(teeth)} mm"
    )
    # T006 carries its own blank and tooth-thickness bands in its
    # configuration only; every sheet reads its own back the same way.
    for name, band in (
        ("BlankDia", blank_dia_band(teeth)),
        ("ToothThickness", tooth_thickness_band(teeth)),
    ):
        matches = [a for a in annotations if dimension_name(adapter, a) == name]
        if len(matches) != 1:
            raise RuntimeError(
                f"{configuration}: expected one {name} on the sheet, found {len(matches)}"
            )
        display = _early_bound(
            _early_bound(matches[0], "IAnnotation").GetSpecificAnnotation(),
            "IDisplayDimension",
        )
        tolerance = _early_bound(
            _early_bound(display.GetDimension2(0), "IDimension").Tolerance,
            "IDimensionTolerance",
        )
        observed = (
            float(tolerance.GetMinValue()) * 1000.0,
            float(tolerance.GetMaxValue()) * 1000.0,
        )
        expected = deviations(band)
        if any(abs(o - e) > 1e-6 for o, e in zip(observed, expected)):
            raise RuntimeError(
                f"{configuration}: sheet {name} reads {observed} mm, expected {expected} mm"
            )
    _telemetry.success(
        f"{configuration}: sheet blank {blank_dia_band(teeth)} and tooth-thickness "
        f"{tooth_thickness_band(teeth)} bands"
    )


def _configure_views(
    adapter: Any, configuration: str, views: tuple[Any, ...]
) -> None:
    """Select one source configuration and verify every view's exact readback."""
    bound_views = tuple(_early_bound(view, "IView") for view in views)
    for view in bound_views:
        view.ReferencedConfiguration = configuration
    # The common drawing chokepoint deliberately does not treat EditRebuild3's
    # BOOL as the sole health signal.  Exact configuration readback is followed
    # by model-dimension import and configuration-qualified native bore-edge
    # validation below.  IView.GetOutline cannot validate nominal geometry: the
    # adapter contract records that SolidWorks pads that box with whitespace.
    rebuild_drawing(adapter, label=f"{configuration} view configuration")
    for view in bound_views:
        observed = str(view.ReferencedConfiguration)
        if observed != configuration:
            raise RuntimeError(
                f"view configuration readback {observed!r} != {configuration!r}"
            )


def _assert_tooth_geometry(front: Any, configuration: str, teeth: int) -> None:
    """Prove the view exposes patterned body edges, not a smooth bored blank."""
    edge_count = len(
        visible_view_entities(
            front, 1, label=f"{configuration} front tooth topology"
        )
    )
    minimum = 2 * teeth + 2
    if edge_count < minimum:
        raise RuntimeError(
            f"{configuration} front view exposes {edge_count} model-body edges; "
            f"expected at least {minimum} for {teeth} visible teeth"
        )
    _telemetry.success(
        f"{configuration} drawing tooth topology: {edge_count} visible body edges"
    )


def _activate_view(adapter: Any, view: Any, *, label: str) -> str:
    """Make ``view`` the active view (sketch entities and notes land in it)."""
    name = view_name(adapter, view)
    if not _early_bound(adapter.currentModel, "IDrawingDoc").ActivateView(name):
        raise RuntimeError(f"failed to activate the {label} {name!r}")
    adapter.currentModel.ClearSelection2(True)
    return name


def _center_bore_view(adapter: Any, view: Any, configuration: str) -> None:
    """Move the configured bore view so the bore axis lands on BORE_VIEW_CENTER."""
    view = _early_bound(view, "IView")
    label = f"{configuration} bore view axis"
    axis = model_point_in_view(adapter, view, (0.0, 0.0, 0.0), label=label)
    position = tuple(float(value) for value in view.Position)
    target = [position[i] + BORE_VIEW_CENTER[i] - axis[i] for i in range(2)]
    if not view.SetViewPosition(double_array(target), False):
        raise RuntimeError(f"failed to move the {configuration} bore view")
    rebuild_drawing(adapter, label=f"{configuration} place bore view")
    axis = model_point_in_view(adapter, view, (0.0, 0.0, 0.0), label=label)
    if math.dist(axis, BORE_VIEW_CENTER) > BORE_VIEW_POSITION_TOL_M:
        raise RuntimeError(
            f"{configuration} bore axis sits at {axis!r}, not {BORE_VIEW_CENTER!r}"
        )


def _crop_bore_view(
    adapter: Any, view: Any, configuration: str, teeth: int, kept: set[str],
    *, center: tuple[float, float] = BORE_VIEW_CENTER, radius: float | None = None,
) -> None:
    """Crop to a native circle, read back its boundary, outline and dimensions."""
    draw = adapter.currentModel
    view = _early_bound(view, "IView")
    label = f"{configuration} bore view"
    uncropped = tuple(float(value) for value in view.GetOutline())
    name = _activate_view(adapter, view, label=label)
    sketch = _early_bound(view.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    radius = bore_view_crop_radius(teeth) if radius is None else radius
    points = []
    for x, y in (center, (center[0] + radius, center[1])):
        point = _early_bound(utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint")
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous_add_to_db = bool(manager.AddToDB)
    manager.AddToDB = False
    try:
        circle = manager.CreateCircle(*points[0], *points[1])
    finally:
        manager.AddToDB = previous_add_to_db
    if circle is None:
        raise RuntimeError(f"failed to sketch the {label} crop circle")
    status = int(view.Crop2(False, False, 1))
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label=f"{label} crop")
    view.UpdateViewDisplayGeometry()
    cropped = bool(view.IsCropped())
    outline = tuple(float(value) for value in view.GetOutline())
    after = {
        dimension_name(adapter, _early_bound(annotation, "IAnnotation"))
        for annotation in (view.GetAnnotations() or ())
    }
    _telemetry.info(
        f"{label} {name!r}: Crop2 status {status}, IsCropped {cropped}, outline "
        f"{tuple(round(value * 1000, 1) for value in outline)} mm, uncropped "
        f"{tuple(round(value * 1000, 1) for value in uncropped)} mm, "
        f"dimensions {sorted(item for item in after if item)}",
        crop_status=status,
        cropped=cropped,
    )
    if status != CROP_NO_ERROR or not cropped:
        raise RuntimeError(
            f"{label} is not cropped: Crop2 status {status}, IsCropped {cropped}"
        )
    if (
        len(outline) != 4
        or len(uncropped) != 4
        or outline[2] - outline[0] >= uncropped[2] - uncropped[0]
    ):
        raise RuntimeError(
            f"{label} crop did not take: outline {outline!r}, before {uncropped!r}"
        )
    boundary = (bool(view.CropViewJaggedOutline), bool(view.CropViewNoOutline))
    if boundary != (False, False):
        raise RuntimeError(
            f"{label}'s crop boundary is not its plain circle: jagged, "
            f"no-outline {boundary!r}"
        )
    lost = sorted(kept - after)
    if lost:
        raise RuntimeError(f"{label} lost {lost} to its crop; it holds {sorted(after)}")


def _clock_arcs(display: Any) -> list[tuple[tuple[float, float], list[tuple[float, float]]]]:
    """The clock dimension's drawn arcs as (centre, tessellated points), in
    sheet metres, read the way the layout audit reads them."""
    data = _early_bound(display.GetDisplayData(), "IDisplayData")
    arcs = []
    for index in range(int(data.GetArcCount())):
        raw = tuple(float(value) for value in (data.GetArcAtIndex2(index) or ()))
        segments = arc_segments(raw)
        if not segments:
            continue
        points = [(segments[0].x0, segments[0].y0), *((s.x1, s.y1) for s in segments)]
        arcs.append(((raw[10], raw[11]), points))
    return arcs


def _sweep_clock_right_of_flat(
    adapter: Any, view: Any, annotations: list[Any], teeth: int, *, label: str
) -> None:
    """Flip the imported flat clock until its arc sweeps only the quadrant
    right of the flat and above the axis, then re-seat its text there.

    The flips act on the selected dimension (the API's own example selects
    it first), so each one runs with the clock alone selected in its active
    view. Every flip is read back from the drawn arcs and the measured value;
    a clock that ends anywhere else raises with the stray points.
    """
    clocks = [
        _early_bound(annotation, "IAnnotation")
        for annotation in annotations
        if dimension_name(adapter, _early_bound(annotation, "IAnnotation")) == "BoreFlatClock"
    ]
    if len(clocks) != 1:
        raise RuntimeError(f"{label}: expected one BoreFlatClock, found {len(clocks)}")
    annotation = clocks[0]
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    selection_name = str(display.GetNameForSelection() or "")
    if not selection_name:
        raise RuntimeError(f"{label}: the flat clock has no selection name")
    model = adapter.currentModel
    drawing = _early_bound(model, "IDrawingDoc")
    vertex = bore_flat_vertex(teeth)
    text_xy = bore_view_keep(teeth)["BoreFlatClock"]
    imported = float(_read_member(dimension, "SystemValue"))
    flips: list[str] = []
    stray: list[tuple[float, float]] = []
    for flip in ("", *CLOCK_FLIPS):
        if flip:
            if not drawing.ActivateView(view.GetName2()):
                raise RuntimeError(f"{label}: failed to activate the bore view")
            model.ClearSelection2(True)
            if not model.Extension.SelectByID2(
                selection_name, "DIMENSION", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
            ):
                raise RuntimeError(f"{label}: failed to select the flat clock {selection_name!r}")
            flipped = getattr(display, flip)()
            model.ClearSelection2(True)
            if not flipped:
                raise RuntimeError(f"{label}: {flip} refused on the flat clock")
            flips.append(flip)
            if not annotation.SetPosition2(*text_xy, 0.0):
                raise RuntimeError(f"{label}: failed to re-seat the flat clock text")
            rebuild_drawing(adapter, label=f"{label} clock {flip}")
        arcs = _clock_arcs(display)
        if not arcs:
            raise RuntimeError(f"{label}: the flat clock draws no arc")
        for centre, points in arcs:
            if math.dist(centre, vertex) > CLOCK_ARC_CENTRE_TOL:
                raise RuntimeError(
                    f"{label}: flat clock arc centred at "
                    f"{tuple(round(v * 1000, 2) for v in centre)} mm, not the "
                    f"flat/axis crossing {tuple(round(v * 1000, 2) for v in vertex)} mm"
                )
        stray = [
            point
            for _centre, points in arcs
            for point in points
            if point[0] < vertex[0] - CLOCK_ARC_OVERRUN or point[1] < vertex[1] - CLOCK_ARC_OVERRUN
        ]
        radii = sorted({round(math.dist(centre, points[0]) * 1000, 2) for centre, points in arcs})
        spans = [
            tuple(
                round(math.degrees(math.atan2(y - vertex[1], x - vertex[0])), 1)
                for x, y in (points[0], points[-1])
            )
            for _centre, points in arcs
        ]
        measured = float(_read_member(dimension, "SystemValue"))
        _telemetry.info(
            f"{label}: flat clock after {flips or ['import']}: reads "
            f"{math.degrees(measured):.4f} deg, {len(arcs)} arc(s) spanning {spans} "
            f"deg about the flat/axis crossing, radius {radii} mm, {len(stray)} "
            "point(s) outside the quadrant right of the flat and above the axis",
            clock_flips=len(flips),
            clock_stray_points=len(stray),
            clock_measured_deg=math.degrees(measured),
        )
        if abs(measured - imported) > 1e-9:
            raise RuntimeError(
                f"{label}: {flips[-1]} changed the clock from "
                f"{math.degrees(imported):.4f} to {math.degrees(measured):.4f} deg"
            )
        if not stray:
            return
    raise RuntimeError(
        f"{label}: flat clock arc still leaves the quadrant right of the flat and "
        f"above the axis after {flips}; first stray points "
        f"{[tuple(round(v * 1000, 1) for v in p) for p in stray[:3]]} mm"
    )


def _center_mark_bore(adapter: Any, view: Any, teeth: int, *, label: str) -> None:
    """Centre-mark the D-bore on its arc.  ``IView.AutoInsertCenterMarks2``
    looks for round holes; the D is an arc and a flat, so the arc's -X point
    is picked and marked directly (the draw_channel_lever R3 recipe)."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    _activate_view(adapter, view, label=label)
    pick = model_point_in_view(
        adapter,
        view,
        (-bore_dia_mm(teeth) / 2000.0, 0.0, 0.0),
        label=f"{label} bore arc -X point",
    )
    extension = _early_bound(draw.Extension, "IModelDocExtension")
    if not extension.SelectByID2(
        "", "EDGE", pick[0], pick[1], 0.0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(f"failed to select the {label} bore arc")
    mark = ddoc.InsertCenterMark3(CENTER_MARK_SINGLE, False, False)
    draw.ClearSelection2(True)
    if mark is None:
        raise RuntimeError(f"failed to centre-mark the {label} bore")


def _note_box(note: Any, *, label: str) -> tuple[float, float, float, float]:
    """``INote.GetExtent``'s lower-left and upper-right corners, sheet metres."""
    values = tuple(float(value) for value in (note.GetExtent() or ()))
    if len(values) != 6 or not all(map(math.isfinite, values)):
        raise RuntimeError(f"{label}: invalid note extent {values!r}")
    box = (values[0], values[1], values[3], values[4])
    if box[0] >= box[2] or box[1] >= box[3]:
        raise RuntimeError(f"{label}: empty note extent {values!r}")
    return box


def _label_bore_view(adapter: Any, view: Any, teeth: int, *, label: str) -> None:
    """Title the bore view under its crop circle: a note the view owns,
    centred on the bore axis by its extent, its top edge on
    ``bore_view_label_top``."""
    _activate_view(adapter, view, label=label)
    text = bore_view_label(teeth)
    center_x, top = BORE_VIEW_CENTER[0], bore_view_label_top(teeth)
    raw = add_note(adapter, text, center_x, top)
    if raw is None:
        raise RuntimeError(f"failed to add the {label} title")
    note = _early_bound(raw, "INote")
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    for _ in range(2):
        box = _note_box(note, label=label)
        error = ((box[0] + box[2]) / 2.0 - center_x, box[3] - top)
        if max(abs(error[0]), abs(error[1])) <= NOTE_CENTRING_TOL_M / 10.0:
            break
        position = tuple(float(value) for value in annotation.GetPosition())
        if not annotation.SetPosition2(position[0] - error[0], position[1] - error[1], 0.0):
            raise RuntimeError(f"failed to centre the {label} title")
        rebuild_drawing(adapter, label=f"{label} title")
    box = _note_box(note, label=label)
    error = ((box[0] + box[2]) / 2.0 - center_x, box[3] - top)
    if max(abs(error[0]), abs(error[1])) > NOTE_CENTRING_TOL_M:
        raise RuntimeError(
            f"{label} title did not centre: off by ({error[0] * 1000:.2f}, "
            f"{error[1] * 1000:.2f}) mm"
        )
    first_line = text.split("\n")[0]
    owned = [
        " ".join(str(_early_bound(found, "INote").GetText() or "").split())
        for found in (_early_bound(view, "IView").GetNotes() or ())
    ]
    if sum(found.startswith(first_line) for found in owned) != 1:
        raise RuntimeError(f"{label} title did not land in its view: {owned!r}")


def _curate_repeated_dimensions(
    adapter: Any,
    view: Any,
    *,
    keep: dict[str, tuple[float, float]],
    view_label: str,
) -> list[Any]:
    """Import a complete sheet's model dimensions, allowing cross-sheet copies.

    ``InsertModelAnnotations3``'s ``DuplicateDims`` flag means *eliminate*
    duplicates when true.  The standard curator uses true because ordinary
    drawings place each model dimension once.  This configured-family package
    must print the same driving dimensions on all twenty standalone sheets, so
    it deliberately passes false and then curates only the returned objects.
    """
    declared = set().union(*DRAWING_DIMENSIONS.values())
    unknown = sorted(set(keep) - declared)
    if unknown:
        raise RuntimeError(f"{view_label} keeps undeclared dimensions: {unknown}")

    drawing = _early_bound(adapter.currentModel, "IModelDoc2")
    ddoc = _early_bound(drawing, "IDrawingDoc")
    name = view_name(adapter, view)
    if not bool(ddoc.ActivateView(name)):
        raise RuntimeError(f"failed to activate drawing view {name!r}")
    drawing.ClearSelection2(True)
    extension = _early_bound(drawing.Extension, "IModelDocExtension")
    if not bool(
        extension.SelectByID2(
            name, "DRAWINGVIEW", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
        )
    ):
        raise RuntimeError(f"failed to select drawing view {name!r}")
    result = adapter._attempt(
        lambda: ddoc.InsertModelAnnotations3(
            0,  # swImportModelItemsFromEntireModel
            _INSERT_DIMS_MARKED,
            False,  # selected view only
            False,  # allow the same model dimensions on every package sheet
            True,  # include dimensions on construction/hidden features
            False,
        ),
        default=None,
    )
    drawing.ClearSelection2(True)
    if not result or isinstance(result, str):
        raise RuntimeError(f"{view_label} imported no marked model dimensions")
    annotations = delete_unnamed_imports(adapter, list(result))
    names = {dimension_name(adapter, annotation) for annotation in annotations}
    delete = tuple(sorted(name for name in names if name and name not in keep))
    curated = curate_dimensions(
        adapter, annotations, delete=delete, reposition=dict(keep)
    )
    present = {dimension_name(adapter, annotation) for annotation in curated}
    missing = sorted(set(keep) - present)
    if missing:
        raise RuntimeError(
            f"{view_label} is missing model dimensions {missing}; "
            f"available={sorted(present)}"
        )
    return curate_dimensions(adapter, curated, reposition=dict(keep))


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cone-gear source", await adapter.open_model(str(SOURCE)))
    await assert_saved_configuration_topology(adapter, phase="drawing source")
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
            "Manufacturing Notes",
            "Cutter Profile",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
            "Manufacturing Notes",
            "Cutter Profile",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    _assert_dimension_arrow_length(drawing_model)
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="cone-gear batch")
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Cone Gear Batch Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cone gear; configured T006 through T120 by six",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    ddoc = _early_bound(drawing_model, "IDrawingDoc")

    for sheet_index, teeth in enumerate(CONFIGURATION_TEETH, start=1):
        configuration = f"T{teeth:03d}"
        view_scale = SHEET_SCALES[configuration]
        if not ddoc.ActivateSheet(configuration):
            raise RuntimeError(f"failed to activate cone-gear sheet {configuration}")

        front = place_view(
            adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=view_scale
        )
        right = place_view(
            adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=view_scale
        )
        iso = place_view(
            adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=view_scale
        )
        bore_view = place_view(
            adapter,
            str(SOURCE),
            "*Front",
            *BORE_VIEW_CENTER,
            scale=bore_view_scale(teeth),
        )
        views = (front, right, iso, bore_view)
        _configure_views(adapter, configuration, views)
        for view in views:
            set_hidden_lines_removed(adapter, view)
        _assert_tooth_geometry(front, configuration, teeth)
        _center_bore_view(adapter, bore_view, configuration)

        # The bore view imports FIRST, while it is uncropped: a model
        # dimension already on the sheet is not imported again, and no other
        # view keeps BoreProfile's three.  BoreProfile is consumed by BoreCut,
        # so it imports without being shown (_drawing_hidden_sketches r21).
        bore_keep = bore_view_keep(teeth)
        bore_annotations = hidden_sketches.curate_view_dimensions(
            adapter,
            bore_view,
            keep=bore_keep,
            view_label=f"{configuration} bore",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        )
        _sweep_clock_right_of_flat(
            adapter, bore_view, bore_annotations, teeth, label=f"{configuration} bore view"
        )
        _crop_bore_view(adapter, bore_view, configuration, teeth, set(bore_keep))
        # The part saves both authoring sketches hidden; the front view shows
        # them again for their dimensions (the side and iso views show the
        # part as saved).  The targeted import still delivers the dimensions
        # on every sheet after the first (probe 834-gapfloor-c301).
        front_annotations = hidden_sketches.curate_view_dimensions(
            adapter,
            front,
            keep=front_keep(teeth),
            view_label=f"{configuration} front",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        )
        _assert_sheet_bands(adapter, front_annotations, configuration, teeth)
        right_annotations = _curate_repeated_dimensions(
            adapter,
            right,
            keep=right_keep(teeth),
            view_label=f"{configuration} right",
        )
        annotations = [*bore_annotations, *front_annotations, *right_annotations]
        set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
        assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
        _center_mark_bore(adapter, front, teeth, label=f"{configuration} front")
        _center_mark_bore(adapter, bore_view, teeth, label=f"{configuration} bore view")
        sheet = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
        if not sheet.SetScale(*view_scale, False, False):
            raise RuntimeError(f"failed to pin the {configuration} sheet scale")
        _label_bore_view(adapter, bore_view, teeth, label=f"{configuration} bore view")

        finish_edge, finish_symbol = bore_finish_xy(teeth)
        # This sheet's configuration-owned finish rows (part spec).
        SURFACE_FINISHES = BORE_SURFACE_FINISHES[teeth]  # noqa: N806
        add_surface_finish(
            adapter,
            front,
            edge_xy=finish_edge,
            symbol_xy=finish_symbol,
            control=surface_finish_by_key(SURFACE_FINISHES, "cone_gear_bore"),
            label=f"{configuration} cone-gear bore finish",
            char_height=0.0025,
        )

        add_property_linked_note(
            adapter, "Gear Data", *GEAR_DATA_POS, char_height=0.0025
        )
        add_property_linked_note(
            adapter, "Manufacturing Notes", *MANUFACTURING_NOTES_POS,
            char_height=0.0025,
        )
        if (
            add_note(
                adapter,
                f"SHEET {sheet_index} OF {len(SHEET_NAMES)}",
                *SHEET_COUNT_POS,
            )
            is None
        ):
            raise RuntimeError(f"failed to stamp sheet count on {configuration}")
        rebuild_drawing(adapter, label=f"{configuration} layout audit")
        check_drawing_layout(
            adapter, layout=SPEC.layout, stem=f"cone-gear {configuration}"
        )

    if not ddoc.ActivateSheet(CUTTER_DETAIL_SHEET):
        raise RuntimeError("failed to activate the DT6-FORM1 tool detail sheet")
    detail = place_view(
        adapter, str(SOURCE), "*Front", *CUTTER_DETAIL_VIEW_CENTER,
        scale=SHEET_SCALES[CUTTER_DETAIL_SHEET],
    )
    _configure_views(adapter, "T006", (detail,))
    center_x, center_y, radius_mm = cutter_detail_window_mm()
    projected = model_point_in_view(
        adapter, detail, (center_x / 1000.0, center_y / 1000.0, 0.0),
        label="DT6-FORM1 installed gap centre",
    )
    detail = _early_bound(detail, "IView")
    position = tuple(float(value) for value in detail.Position)
    if not detail.SetViewPosition(double_array([
        position[i] + CUTTER_DETAIL_VIEW_CENTER[i] - projected[i] for i in range(2)
    ]), False):
        raise RuntimeError("failed to position the DT6-FORM1 installed gap crop")
    rebuild_drawing(adapter, label="DT6-FORM1 crop centre")
    projected = model_point_in_view(
        adapter, detail, (center_x / 1000.0, center_y / 1000.0, 0.0),
        label="DT6-FORM1 installed gap centre readback",
    )
    if math.dist(projected, CUTTER_DETAIL_VIEW_CENTER) > BORE_VIEW_POSITION_TOL_M:
        raise RuntimeError("DT6-FORM1 installed gap crop centre did not persist")
    numerator, denominator = SHEET_SCALES[CUTTER_DETAIL_SHEET]
    _crop_bore_view(
        adapter, detail, "DT6-FORM1", 6, set(),
        center=CUTTER_DETAIL_VIEW_CENTER,
        radius=radius_mm * numerator / denominator / 1000.0,
    )
    set_hidden_lines_removed(adapter, detail)
    add_property_linked_note(
        adapter, "Cutter Profile", *CUTTER_DETAIL_POS, char_height=0.0025
    )
    if add_note(
        adapter, "T006 INSTALLED GAP - SEE T006 FOR FINISHED GEAR",
        0.230, 0.092,
    ) is None:
        raise RuntimeError("failed to label the installed gap on the cutter detail")
    sheet = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
    if not sheet.SetScale(*SHEET_SCALES[CUTTER_DETAIL_SHEET], False, False):
        raise RuntimeError("failed to pin the DT6-FORM1 detail sheet scale")
    rebuild_drawing(adapter, label="DT6-FORM1 detail layout audit")
    check_drawing_layout(adapter, layout=SPEC.layout, stem="cone-gear DT6-FORM1")

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Gear Batch Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        expected_sheet_names=SHEET_NAMES,
        sheet_layouts={name: SPEC.layout for name in SHEET_NAMES},
        sheet_scales=SHEET_SCALES,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
