r"""Four-sheet manufacturing package for the unchanged graduated brass stick.

BAR gives the envelope, the 10 tick's land from the end face nearest the 10
as a reference (that face bears on the amplitude bar, #2434) and the
numbered notes its dimensions link. GRADUATIONS tables every graduation's
station from that face and enlarges a decade with its pitches as references; TICK LENGTHS
gives groove width and each length a local detail without cross-strip
extension lines. ENGRAVING separates numeral dimensions (detail F at the 0,
detail H at the 10) from the open-edge Top detail for the V graduations'
groove depth. Each detail's parent on sheets 2-4 is a reduced copy of a
sheet 1 view, labelled with that view's name and scale. Section G-G cuts the
whole .315 x .125 bar across both strokes of the zero numeral, so the true V
grooves read in profile, and imports NumeralDepth there; its callout names
the V angle. Native probes import TickDepth in Top but not in a removed
cut-only section, so G-G is a full section (with hidden lines removed only
the cut face shows). All sizes, bands and places come from the part; scale
is never shrunk to fit. Part-spec coordinates are millimetres; model-point
projection takes metres. Drawing-sheet positions and projected fence
coordinates are also metres.

This replaces draw_ha_measuring_stick without a legacy entry point: its
split-common check, path and session imports live here, while ruled-face
orientation, source-linked notes and native dimensions retain the current
four-sheet manufacturing contract.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
import ms_stick_callouts as callouts
import ms_stick_spec as part
from _check import check
from _com import _early_bound
from _paths import CAD_ROOT
from _session import run_build
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
    view_name,
)
from _drawing_detail_crop import native_circle_geometry
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_sections import create_section_view
from _drawing_sheets import create_blank_drawing_sheets
from _drawing_view_display import set_hidden_lines_removed
from _feature_requirements import part_metadata, requirement
from _gtol_planar import PlanarFace
from _printed_limits import limits
from _printed_tolerance import printed_deviations
from _drawing_hidden_sketches import curate_view_dimensions, part_sketches_shown
from _drawing_registry import DRAWINGS_BY_NAME
from _named_views import octant_view_name
from _machinist_review_mode import MachinistReviewMode
from _ms_drawing_contract import assert_manufacturing_dimensions
from _part_properties import part_drawing_unit
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import add_note, dimension_name, place_view

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ms_stick"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"])
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png
SHEET_NAMES = ("BAR", "GRADUATIONS", "TICK LENGTHS", "ENGRAVING")
SHEET_SCALE = (1.0, 1.0)
FRONT_CENTER = (0.155, 0.175)
TOP_CENTER = (FRONT_CENTER[0], 0.110)
# r2-r3 sheet 1: the 8.00 dimension line's tail touched the isometric at x 0.335.
ISO_CENTER = (0.355, 0.145)
# Upper-left of sheet 1's numbered notes: under the bottom view and the
# isometric label, the four lines ending above the title block.
NOTES_XY = (0.020, 0.092)
# Each detail's parent on sheets 2-4 is a 1:2 copy of a sheet 1 view: its
# label's upper-left sits this far left of and below the copy's centre, so
# the label centres under the bar, clear of its edge (rule 9).
PARENT_LABEL_OFFSET = (-0.024, -0.004)
# A detail letter's centre stands this far above whichever is higher, its
# fence or the copy's upper edge, so it reads as the fence's letter (the
# letters print about 7 mm tall).
DETAIL_LETTER_GAP = 0.0045
DETAIL_PARENT_CENTER = (0.230, 0.245)
DETAIL_CENTER = (0.180, 0.140)
DETAIL_SCALE = (6.0, 1.0)
DETAIL_RADIUS_MM = 9.0
# r1-r3 sheet 4: at 6:1 the 0.40 x 0.50 groove could not be read; 15:1 can.
DEPTH_CENTER = (0.375, 0.120)
DEPTH_SCALE = (15.0, 1.0)
DEPTH_RADIUS_MM = 1.6
NUMERAL_PARENT_CENTER = (0.130, 0.210)
# Third-angle bottom view of sheet 4's front copy: straight below it (rule
# 15; run 20261111T180258983Z-3467590b flagged it beside the front copy), its
# B letter under the front copy's label and its own label above detail F's
# NUMERAL HEIGHT dimension line. At 0.192 the letter sat 1.33 mm under that
# label (layout audit needs 1.78; run 20261111T185346013Z-fd4d7b02).
DEPTH_PARENT_CENTER = (NUMERAL_PARENT_CENTER[0], 0.1895)
# r4 sheet 4: full-tick-end callout starts 62 mm left of its placement.
# The detail/dimension group sits as far left as its 10X/11X texts allow, so
# the NUMERALS V callout fits between its circle and G-G.
NUMERAL_CENTER = (0.153, 0.135)
# The fence includes the real full-tick endpoint and both numeral gap anchors.
NUMERAL_RADIUS_MM = 7.0
# Detail H, on the same parent: the 10 sits on the -X side of the last full
# tick, so its tick-edge gap gets its own detail (rule 26: a location is a
# dimension). The fence holds the whole 10, the tick's end and the gap; the
# detail sits in the free corner under detail F's dimensions, its SCALE line
# clear of the border (round 1 put it on the border).
NUMERAL_10_MODEL_CENTER = (
    part.SCALE_START_X + part.SCALE_SPAN - 1.2,
    part.BODY_WIDTH - part.TICK_LENGTH - part.NUMERAL_GAP_MM - 0.6,
)
NUMERAL_10_RADIUS_MM = 2.6
NUMERAL_10_CENTER = (0.060, 0.074)
NUMERAL_10_KEEP = {"Numeral10XGap": (0.050, 0.100)}
# A 1:1 parent spreads the across-the-bar cutting line (and its two arrows)
# over a readable 11 mm instead of a 1:2 nick.
NUMERAL_PROFILE_PARENT_CENTER = (0.200, 0.250)
# Upper-left of its label: right of the bar's end, clear of the G letters.
SECTION_PARENT_NOTE_XY = (0.310, 0.257)
# 3 mm right of the mm sheet's 0.280: the inch floor row (STOCK UNDER .080
# MIN) is one character wider between detail F and the section.
NUMERAL_PROFILE_CENTER = (0.283, 0.125)
# The .016 V must read as a profile; 10:1 keeps the full bar section on sheet.
NUMERAL_PROFILE_SCALE = (10.0, 1.0)
# Through the zero's two straight side strokes (they cross the cut square),
# clear of every tick: midway between the first minor tick's far wall and
# where the zero's sides turn into its end facets (gen_ms_stick_numerals_dxf
# ends them at 0.84 of the stroke-centre height). At the zero's mid-height the
# cut ran 0.10 off that tick wall and read as lying on it, with no tick in
# G-G (machinist review, run 20261031T070419538Z-20ea55fe).
_MINOR_TICK_FAR_WALL = part.SCALE_START_X + part.MINOR_SPACING + part.TICK_WIDTH / 2.0
_ZERO_SIDE_END = (part.SCALE_START_X + part.TICK_WIDTH / 2.0 + part.NUMERAL_GAP_MM
                  + part.NUMERAL_STROKE_WIDTH_MM / 2.0
                  + 0.84 * (part.NUMERAL_HEIGHT_MM - part.NUMERAL_STROKE_WIDTH_MM))
NUMERAL_SECTION_X = (_MINOR_TICK_FAR_WALL + _ZERO_SIDE_END) / 2.0
# r1-r3 sheet 4: at 1.5 mm the G letters sat on their arrows and the outline.
# Each G prints from 1.4 mm below to 5.0 mm above its arrow (308 sheet 4, as
# pd_support_bar's r7 letters): past the ruled edge (sheet top on the unturned
# parent) 4.0 leaves the upper G 2.6 mm clear; 6.5 below the bar leaves the
# lower G 1.5 mm clear of the bar's edge.
NUMERAL_SECTION_OVERSHOOT_MM = 4.0
NUMERAL_SECTION_FOOT_OVERSHOOT_MM = 6.5
# The 10 tick's land (reference) from the end face nearest the 10: arrows
# outside the 3.4 mm span, the text right of them, between the bar's end and
# the isometric.
FRONT_KEEP = {
    "BodyLength": (0.155, 0.205), "BodyWidth": (0.305, 0.215),
    "Tick10FromEnd": (0.274, 0.150),
}
TOP_KEEP = {"BodyThickness": (0.275, 0.130)}
# Detail A shows a decade's pitches as references; the station table locates.
DETAIL_KEEP = {
    "FullTickPitch": (0.180, 0.218),
    "MinorTickPitch": (0.075, 0.085),
}
# Sheet 2's station table, right of detail A and under the parent's label:
# the title's upper-left, then one note per column (upper-left corners),
# all columns starting on the same line so their rows align. Round 3 printed
# NUMERAL against +0 at 22 mm: the heading prints about 3.1 mm a character,
# so the first value column starts a clear 3 mm past it.
STATION_TITLE_XY = (0.245, 0.232)
STATION_COLUMNS_TOP = 0.212
STATION_NUMERAL_COLUMN_X = 0.245
STATION_HEADING_CHAR_WIDTH = 0.0031
STATION_FIRST_VALUE_X = 0.271
STATION_COLUMN_PITCH = 0.0145
# Local fences keep extension lines beside their tick. D sits between the
# first two minor ticks, 0.7 inside the ruled edge, model radius 1.8: both
# minor ticks and a plain stretch of edge show, and tick zero and the next
# tick stay outside. It is authored exactly (EXACT_FENCES): with sketch
# inference its fence snapped to the tick profile corner and shrank,
# clipping tick zero and leaving the edge a stub (machinist review run
# 20261024T101144897Z-358edb75; measured from that run's PDF vectors).
LENGTH_DETAILS = (
    ("C", (0.100, 0.245), (0.105, 0.155),
     (part.SCALE_START_X, part.BODY_WIDTH - part.TICK_LENGTH / 2.0),
     {"FullTickLength": (0.075, 0.180), "Tick0Width": (0.075, 0.215)}, 4.0),
    ("D", (0.215, 0.245), (0.220, 0.155),
     (part.SCALE_START_X + 1.5 * part.MINOR_SPACING, part.BODY_WIDTH - 0.7),
     {"MinorTickLength": (0.190, 0.180)}, 1.8),
    ("E", (0.330, 0.245), (0.335, 0.155),
     (part.SCALE_START_X + part.DIVISION_SPACING / 2.0, part.BODY_WIDTH - part.HALF_TICK_LENGTH / 2.0),
     {"HalfTickLength": (0.300, 0.185)}, 4.0),
)
EXACT_FENCES = frozenset({"D", "H"})
NUMERAL_KEEP = {
    "NumeralHeight": (0.203, 0.183),
    "NumeralXGap": (0.088, 0.170),
    "NumeralYGap": (0.088, 0.155),
}
# Text centre high enough that the shoulder under its last line clears the
# top of SECTION G-G (machinist review, run 20261023T231808846Z-1d2625e9).
# The V groove's depth dimension runs its callout block right from this
# point (run 20261111T180258983Z-3467590b: 0.380 put it 35 mm past the
# border), so the point sits one block width inside the right border.
DEPTH_KEEP = {"TickDepth": (0.330, 0.188)}
# Text centre: the block ends left of G-G, its underside dimension line at the V.
NUMERAL_DEPTH_KEEP = {"NumeralDepth": (0.229, 0.138)}

# The sheet's notes (ms_stick_callouts), for the feature export: declared on
# the drawing, so the part's recipe does not re-key on them.
DRAWING_NOTES = callouts.DRAWING_NOTES

# Feature-export declarations (export_features; cad/docs/pipeline/
# features-travelers.md): what the four sheets print, in the part frame
# (build_ms_stick: the bar along +X from the end nearest the 0, x = 0, to the
# end face nearest the 10, x = BODY_LENGTH, the graduations' datum; Y across
# the width, the ticks hanging from the ruled edge at y = BODY_WIDTH; Z
# through the thickness, the ruled face at z = 0, engraved into +Z). The
# graduations are one feature: 101 V grooves whose floors all lie at the
# tick depth, tick i at SCALE_START_X + i * MINOR_SPACING, each station from
# the datum end at +/-.002 (the station table, note 2); the numerals another,
# their single-stroke floors at the numeral depth. The declarations print
# nothing.
_P = part.DRAWING_PRECISION_BY_NAME
_SELF = "draw_ms_stick"
_GEOM = "ms_stick_geom"
_FRAME = ("BODY_LENGTH", "BODY_WIDTH", "BODY_THICKNESS")
_UNIT = part.UNIT
_TABLE = ((_SELF, "STATION_TITLE_XY"), ("ms_stick_callouts", "STATION_TABLE_TITLE"))
_TICK_COUNT = (part.DIVISION_COUNT - 1) * part.MINOR_PER_DIVISION + 1
_ZERO_STATION = part.BODY_LENGTH - part.SCALE_START_X
_TEN_STATION = part.BODY_LENGTH - part.SCALE_START_X - part.SCALE_SPAN
_STATION_TOL = part.GRADUATION_POSITION_TOLERANCE_MM


def _plane(axis: str, value: float) -> dict[str, Any]:
    return {"frame": "model", "axis": axis, "value": value}


def _station_band(station: float) -> list[float]:
    """A station-table row's +/-.002 about its printed .XXX value, in mm."""
    low, high = printed_deviations(station, 3, (-_STATION_TOL, _STATION_TOL), unit=_UNIT)
    return [round(station + low, 12), round(station + high, 12)]


part_metadata(
    model_sources=_FRAME,
    precision_sources=("DRAWING_PRECISION", "DRAWING_PRECISION_BY_NAME"),
)
# The end face nearest the 10: the graduations' datum (note 2; #2434).
requirement(
    "datum_end",
    kind="face",
    faces=(PlanarFace((1.0, 0.0, 0.0), part.BODY_LENGTH),),
    requirements=("plane",),
    fields={"plane": (_plane("x", part.BODY_LENGTH), _FRAME)},
)
# The length 7.95 (FRONT_KEEP "BodyLength").
requirement(
    "zero_end",
    kind="face",
    faces=(PlanarFace((-1.0, 0.0, 0.0), 0.0),),
    requirements=("length",),
    fields={
        "plane": (_plane("x", 0.0), _FRAME),
        "length": (
            limits(part.BODY_LENGTH, _P["BodyLength"], unit=_UNIT),
            ("BODY_LENGTH", "BODY_LENGTH_TOLERANCE_MM", (_SELF, "FRONT_KEEP")),
        ),
        "length_nominal": (part.BODY_LENGTH, ("BODY_LENGTH",)),
        "length_from": ("datum_end", ((_SELF, "FRONT_KEEP"),)),
    },
    precision={"length": _P["BodyLength"]},
)
requirement(
    "plain_edge",
    kind="face",
    faces=(PlanarFace((0.0, -1.0, 0.0), 0.0),),
    requirements=("plane",),
    fields={"plane": (_plane("y", 0.0), _FRAME)},
)
# The width .315 at .XXX, SEE NOTE 1: the sliding fit in the MHA-MS-02 stop
# block's rebate, note 1 giving its acceptance (STICK SLIDES FULL LENGTH;
# rule 4) (FRONT_KEEP "BodyWidth").
requirement(
    "ruled_edge",
    kind="face",
    faces=(PlanarFace((0.0, 1.0, 0.0), part.BODY_WIDTH),),
    requirements=("width",),
    fields={
        "plane": (_plane("y", part.BODY_WIDTH), ("BODY_WIDTH",)),
        "width": (
            limits(part.BODY_WIDTH, _P["BodyWidth"], unit=_UNIT),
            ("BODY_WIDTH", "BODY_FIT_TOLERANCE_MM", (_SELF, "FRONT_KEEP")),
        ),
        "width_nominal": (part.BODY_WIDTH, ("BODY_WIDTH",)),
        "width_from": ("plain_edge", ((_SELF, "FRONT_KEEP"),)),
        "callout": (callouts.REBATE_LINK, (("ms_stick_callouts", "REBATE_LINK"),)),
    },
    precision={"width": _P["BodyWidth"]},
)
# The ruled face (z = 0): every graduation and numeral is engraved into it.
requirement(
    "ruled_face",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), 0.0),),
    requirements=("plane",),
    fields={"plane": (_plane("z", 0.0), _FRAME)},
)
# The thickness (.125) as a reference over 1/8 FLAT AS SUPPLIED, SEE NOTE 1:
# the 1/8 flat as supplied (owner ruling 2026-11-20, #2441; rule 4, stock
# that is good enough stays stock; TOP_KEEP "BodyThickness"). The limits are
# the receiving gate, the title block's .XXX standing in for the mill's band.
requirement(
    "back_face",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, 1.0), part.BODY_THICKNESS),),
    requirements=("thickness",),
    fields={
        "plane": (_plane("z", part.BODY_THICKNESS), ("BODY_THICKNESS",)),
        "thickness": (
            limits(part.BODY_THICKNESS, _P["BodyThickness"], unit=_UNIT),
            ("BODY_THICKNESS", "BODY_FIT_TOLERANCE_MM", (_SELF, "TOP_KEEP")),
        ),
        "thickness_nominal": (part.BODY_THICKNESS, ("BODY_THICKNESS",)),
        "thickness_from": ("ruled_face", ((_SELF, "TOP_KEEP"),)),
        "as_supplied": (
            True,
            ("BODY_THICKNESS", ("ms_stick_callouts", "THICKNESS_STOCK")),
        ),
        "dimension_type": (
            "reference",
            (("ms_stick_callouts", "PREFIXES"), ("ms_stick_callouts", "SUFFIXES")),
        ),
        "callout": (
            callouts.CALLOUTS["BodyThickness"],
            (
                ("ms_stick_callouts", "THICKNESS_STOCK"),
                ("ms_stick_callouts", "REBATE_LINK"),
            ),
        ),
    },
    precision={"thickness": _P["BodyThickness"]},
)
# The graduations: 101 30-degree V grooves into the ruled face, hanging from
# the ruled edge, .016 MIN wide at the face (.024 MAX), .020 MIN deep with
# .080 MIN stock under them (DETAIL_KEEP, LENGTH_DETAILS, DEPTH_KEEP); full
# ticks .12, half-division .16, minor .07 long (.XX); each station from the
# datum end +/-.002 (the station table): tick 0 at the 0, tick 100 at the
# 10, the 10's .135 a reference (FRONT_KEEP "Tick10FromEnd").
requirement(
    "graduations",
    kind="notch",
    faces=(PlanarFace((0.0, 0.0, -1.0), -part.TICK_DEPTH),),
    requirements=(
        "width",
        "depth_min",
        "zero_station",
        "full_length",
        "half_length",
        "minor_length",
    ),
    fields={
        "open_to": ("ruled_edge", _FRAME),
        "axis": ([0.0, 0.0, 1.0], _FRAME),
        "v_angle_deg": (part.ENGRAVING_V_INCLUDED_ANGLE_DEG, ("ENGRAVING_V_INCLUDED_ANGLE_DEG",)),
        "width": (
            [part.TICK_WIDTH, part.GRADUATION_WIDTH_MAX_MM],
            ("TICK_WIDTH", "GRADUATION_WIDTH_MAX_MM", "MIN_LIMIT_DEVIATIONS_MM", (_SELF, "LENGTH_DETAILS")),
        ),
        "width_callout": (part.GRADUATION_WIDTH_CALLOUT, ("GRADUATION_WIDTH_CALLOUT",)),
        "depth_min": (part.TICK_DEPTH, ("TICK_DEPTH", "MIN_LIMIT_DEVIATIONS_MM", (_SELF, "DEPTH_KEEP"))),
        "floor_min": (part.GRADUATION_FLOOR_MIN_MM, ("GRADUATION_FLOOR_MIN_MM", "GRADUATION_FLOOR_CALLOUT")),
        "count": (_TICK_COUNT, ((_GEOM, "DIVISION_COUNT"), (_GEOM, "MINOR_PER_DIVISION"))),
        "per_division": (part.MINOR_PER_DIVISION, ((_GEOM, "MINOR_PER_DIVISION"),)),
        "minor_pitch": (part.MINOR_SPACING, ((_GEOM, "MINOR_SPACING"), (_SELF, "DETAIL_KEEP"))),
        "zero_station": (
            _station_band(_ZERO_STATION),
            ("BODY_LENGTH", "SCALE_START_X", "GRADUATION_POSITION_TOLERANCE_MM", *_TABLE),
        ),
        "zero_station_nominal": (_ZERO_STATION, ("BODY_LENGTH", "SCALE_START_X")),
        "zero_station_from": ("datum_end", _TABLE),
        "ten_station_ref": (_TEN_STATION, ("SCALE_END_MARGIN", (_SELF, "FRONT_KEEP"))),
        "station_tolerance": (_STATION_TOL, ("GRADUATION_POSITION_TOLERANCE_MM", *_TABLE)),
        "station_note": (callouts.STATION_LINK, (("ms_stick_callouts", "STATION_LINK"),)),
        "full_length": (
            limits(part.TICK_LENGTH, _P["FullTickLength"], unit=_UNIT),
            ("TICK_LENGTH", (_SELF, "LENGTH_DETAILS")),
        ),
        "full_length_nominal": (part.TICK_LENGTH, ("TICK_LENGTH",)),
        "half_length": (
            limits(part.HALF_TICK_LENGTH, _P["HalfTickLength"], unit=_UNIT),
            ("HALF_TICK_LENGTH", (_SELF, "LENGTH_DETAILS")),
        ),
        "half_length_nominal": (part.HALF_TICK_LENGTH, ("HALF_TICK_LENGTH",)),
        "minor_length": (
            limits(part.MINOR_TICK_LENGTH, _P["MinorTickLength"], unit=_UNIT),
            ("MINOR_TICK_LENGTH", (_SELF, "LENGTH_DETAILS")),
        ),
        "minor_length_nominal": (part.MINOR_TICK_LENGTH, ("MINOR_TICK_LENGTH",)),
    },
    precision={
        "width": 3,
        "zero_station": 3,
        "full_length": _P["FullTickLength"],
        "half_length": _P["HalfTickLength"],
        "minor_length": _P["MinorTickLength"],
    },
)
# The numerals 0-10: single-stroke sans (note 3), V-engraved with the same
# 30-degree bit, .016 MIN deep with .080 MIN stock under them, .08 tall
# (NUMERAL_KEEP, NUMERAL_DEPTH_KEEP); the stroke paths are the generated
# layer DXFs the model is cut from.
requirement(
    "numerals",
    kind="profile",
    faces=(PlanarFace((0.0, 0.0, -1.0), -part.NUMERAL_DEPTH),),
    requirements=("depth_min", "height"),
    fields={
        "axis": ([0.0, 0.0, 1.0], _FRAME),
        "v_angle_deg": (part.ENGRAVING_V_INCLUDED_ANGLE_DEG, ("ENGRAVING_V_INCLUDED_ANGLE_DEG",)),
        "depth_min": (part.NUMERAL_DEPTH, ("NUMERAL_DEPTH", "MIN_LIMIT_DEVIATIONS_MM", (_SELF, "NUMERAL_DEPTH_KEEP"))),
        "floor_min": (part.GRADUATION_FLOOR_MIN_MM, ("GRADUATION_FLOOR_MIN_MM", "NUMERAL_FLOOR_CALLOUT")),
        "height": (
            limits(part.NUMERAL_HEIGHT_MM, _P["NumeralHeight"], unit=_UNIT),
            ("NUMERAL_HEIGHT_MM", (_SELF, "NUMERAL_KEEP")),
        ),
        "height_nominal": (part.NUMERAL_HEIGHT_MM, ("NUMERAL_HEIGHT_MM",)),
        "stroke_layers": (
            [path.name for path in part.NUMERAL_LAYER_DXFS],
            ("NUMERAL_LAYER_DXFS",),
        ),
        # The numerals' ink box on the ruled face: x then y, each [low, high] mm.
        "x_span": ([part.NUMERALS_BBOX[0], part.NUMERALS_BBOX[2]], ("NUMERALS_BBOX",)),
        "y_span": ([part.NUMERALS_BBOX[1], part.NUMERALS_BBOX[3]], ("NUMERALS_BBOX",)),
        "font_note": (callouts.DRAWING_NOTES.splitlines()[-1].strip(), (("ms_stick_callouts", "DRAWING_NOTES"),)),
    },
    precision={"height": _P["NumeralHeight"]},
)


@_telemetry.traced("drawing.ms_ruled_face")
def _rotate_ruled_face(adapter: Any, view: Any) -> None:
    """Keep the existing -Z read: scale zero left, graduations at lower edge."""
    view = _early_bound(view, "IView")
    view.Angle = math.pi
    if abs(abs(float(view.Angle)) - math.pi) > 1e-9:
        raise RuntimeError("failed to rotate measuring-stick ruled face")
    adapter.currentModel.EditRebuild3()


def _label_parent(adapter: Any, center: tuple[float, float], *,
                  property_name: str = "Parent View Note") -> None:
    """Name a reduced detail parent under its centre: view name and scale."""
    add_property_linked_note(adapter, property_name, center[0] + PARENT_LABEL_OFFSET[0],
                             center[1] + PARENT_LABEL_OFFSET[1])


@_telemetry.traced("drawing.ms_engraving_detail", label_param="detail_label")
def _engraving_detail(
    adapter: Any, parent: Any, *, model_center: tuple[float, float, float],
    view_xy: tuple[float, float], radius_mm: float, detail_label: str,
    letter_clear_mm: float, scale: tuple[float, float] = DETAIL_SCALE, exact: bool = False,
) -> Any:
    """Fence a useful-scale detail and set its parent letter just above it.

    The fence's sheet radius is ``radius_mm / 2`` mm. With ``exact`` the
    circle is authored straight to the sketch database (no sketch inference,
    which otherwise snaps the centre and rim to nearby view-sketch points at a
    screen-pixel tolerance), read back, and selected for the detail, as in
    draw_ch_rocker_arm._create_detail; the fence then sits exactly on
    ``model_center`` with model radius ``radius_mm`` at the 1:2 parents.
    ``letter_clear_mm`` is the model distance from the centre up to the
    parent's upper edge: the letter clears both that edge and the fence.
    """
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    parent = _early_bound(parent, "IView")
    if not ddoc.ActivateView(view_name(adapter, parent)):
        raise RuntimeError(f"cannot activate engraving detail {detail_label} parent")
    draw.ClearSelection2(True)
    center = model_point_in_view(
        adapter, parent, model_center, label=f"engraving detail {detail_label} centre")
    sketch = _early_bound(parent.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    radius = radius_mm * 0.5 / 1000.0
    for x, y in (center, (center[0] + radius, center[1])):
        point = _early_bound(utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint")
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    if exact:
        previous = bool(manager.AddToDB)
        manager.AddToDB = True
        try:
            circle = manager.CreateCircle(*points[0], *points[1])
        finally:
            manager.AddToDB = previous
        if circle is None:
            raise RuntimeError(f"failed to draw engraving detail {detail_label} fence")
        actual_centre, actual_radius = native_circle_geometry(
            circle, label=f"engraving detail {detail_label} fence")
        asked_radius = math.dist(points[0], points[1])
        _telemetry.info(f"engraving detail {detail_label} fence: centre {actual_centre} (asked {points[0]}), "
                        f"radius {actual_radius} (asked {asked_radius})")
        if math.dist(actual_centre, points[0]) > 1e-7 or abs(actual_radius - asked_radius) > 1e-7:
            raise RuntimeError(f"engraving detail {detail_label}: the authored fence moved or changed radius")
        selection = _early_bound(draw.SelectionManager, "ISelectionMgr")
        data = _early_bound(selection.CreateSelectData(), "ISelectData")
        data.View = parent
        if _early_bound(circle, "ISketchSegment").Select4(False, data) is not True:
            raise RuntimeError(f"engraving detail {detail_label}: cannot select its fence")
    elif manager.CreateCircle(*points[0], *points[1]) is None:
        raise RuntimeError(f"failed to draw engraving detail {detail_label} fence")
    detail = ddoc.CreateDetailViewAt4(*view_xy, 0.0, 0, *scale,
                                    detail_label, 1, True, False, False, 5)
    if detail is None:
        raise RuntimeError(f"failed to create engraving detail {detail_label}")
    detail = _early_bound(detail, "IView")
    detail.ScaleRatio = double_array(list(scale))
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    circles = tuple(parent.GetDetailCircles() or ())
    matching = [
        _early_bound(circle, "IDetailCircle") for circle in circles
        if _early_bound(circle, "IDetailCircle").GetLabel() == detail_label
    ]
    if len(matching) != 1:
        raise RuntimeError(f"detail {detail_label}: expected one matching parent circle")
    letter_xy = (center[0], center[1] + max(radius_mm, letter_clear_mm) * 0.5 / 1000.0
                 + DETAIL_LETTER_GAP)
    matching[0].SetLabelPosition(*letter_xy)
    rebuild_drawing(adapter, label=f"place detail {detail_label} parent letter")
    actual = tuple(float(value) for value in matching[0].GetLabelPosition())
    if len(actual) != 2 or math.dist(actual, letter_xy) > 1e-8:
        raise RuntimeError(f"detail {detail_label}: parent letter placement rejected: {actual}")
    return detail


def _numeral_profile(adapter: Any, parent: Any) -> Any:
    """Whole-bar full section across both straight side strokes of the zero numeral."""
    endpoints = tuple(
        model_point_in_view(
            adapter, parent, (NUMERAL_SECTION_X / 1000.0, y / 1000.0, 0.0),
            label="numeral stroke section endpoint",
        )
        for y in (-NUMERAL_SECTION_FOOT_OVERSHOOT_MM, part.BODY_WIDTH + NUMERAL_SECTION_OVERSHOOT_MM)
    )
    section = create_section_view(
        adapter, parent, line_start=endpoints[0], line_end=endpoints[1],
        view_xy=NUMERAL_PROFILE_CENTER, section_label="G", scale=NUMERAL_PROFILE_SCALE,
        label="numeral V G-G",
    )
    section = _early_bound(section, "IView")
    section.UseParentScale = False
    section.ScaleRatio = double_array(list(NUMERAL_PROFILE_SCALE))
    definition = _early_bound(section.GetSection(), "IDrSection")
    definition.SetDisplayOnlySurfaceCut(False)
    rebuild_drawing(adapter, label="numeral G-G full section")
    if bool(definition.GetDisplayOnlySurfaceCut()) or bool(definition.GetPartialSection()):
        raise RuntimeError("numeral G-G must be a full section of the whole bar")
    # The ruled-face turn the parent no longer takes: G-G reads as before.
    _rotate_ruled_face(adapter, section)
    set_hidden_lines_removed(adapter, section)
    if bool(section.UseParentScale) or tuple(float(value) for value in section.ScaleRatio) != NUMERAL_PROFILE_SCALE:
        raise RuntimeError("numeral G-G must retain its independent 10:1 scale")
    model_center = (
        NUMERAL_SECTION_X / 1000.0, part.BODY_WIDTH / 2000.0, part.BODY_THICKNESS / 2000.0,
    )
    actual = model_point_in_view(adapter, section, model_center, label="numeral G-G profile centre")
    if math.dist(actual, NUMERAL_PROFILE_CENTER) > 1e-8:
        position = tuple(float(value) for value in section.Position)
        target = [position[index] + NUMERAL_PROFILE_CENTER[index] - actual[index] for index in range(2)]
        if not section.SetViewPosition(double_array(target), False):
            raise RuntimeError("numeral G-G profile could not be centred")
        rebuild_drawing(adapter, label="centre numeral G-G profile")
        actual = model_point_in_view(adapter, section, model_center, label="numeral G-G placed centre")
        if math.dist(actual, NUMERAL_PROFILE_CENTER) > 1e-6:
            raise RuntimeError(f"numeral G-G profile centre drifted: {actual}")
    return section


def _assert_numeral_depth_owner(annotation: Any) -> None:
    """The imported depth must attach to Numerals, never to a graduation."""
    annotation = _early_bound(annotation, "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    if str(dimension.FullName).split("@")[:2] != ["NumeralDepth", "Numerals"]:
        raise RuntimeError(f"numeral depth imported from wrong feature: {dimension.FullName}")
    if abs(float(dimension.SystemValue) * 1000.0 - part.NUMERAL_DEPTH) > 1e-6:
        raise RuntimeError("numeral depth import does not read its V-engraved cut")


@_telemetry.traced("drawing.ms_stick.imported_text_and_limits")
def _assert_imported_text_and_limits(adapter: Any, annotations: list[Any]) -> None:
    """Every imported dimension prints the callout, prefix and suffix its part
    authored, and each MIN-limit size still prints as a single MIN limit. The
    width ceiling and the stock under the grooves print nowhere else, so a
    lost row or a changed tolerance type must fail the drawing; the part, not
    the drawing, writes the text (#1942)."""
    names = {*callouts.FEATURE_OF, *part.MIN_LIMIT_DEVIATIONS_MM}
    displays: dict[str, list[Any]] = {name: [] for name in names}
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name in displays:
            annotation = _early_bound(annotation, "IAnnotation")
            displays[name].append(_early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension"))
    missing = sorted(name for name, found in displays.items() if not found)
    if missing:
        raise RuntimeError(f"imported dimensions missing from the sheet: {missing}")
    wrong = {
        (name, part_id): printed
        for part_id, texts in callouts.LANES
        for name, text in texts.items()
        for display in displays[name]
        if callouts.callout_rows(printed := str(display.GetText(part_id) or ""))
        != callouts.callout_rows(text)
    }
    if wrong:
        raise RuntimeError(f"imported callouts differ from the part's: {wrong!r}")
    types = {
        name: int(_early_bound(_early_bound(display.GetDimension2(0), "IDimension").Tolerance,
                               "IDimensionTolerance").Type)
        for name in part.MIN_LIMIT_DEVIATIONS_MM
        for display in displays[name]
    }
    if any(kind != part.MIN_LIMIT_TOL_TYPE for kind in types.values()):
        raise RuntimeError(
            f"MIN-limit dimensions must print tolerance type {part.MIN_LIMIT_TOL_TYPE}: {types}"
        )


def _assert_dimension_contract(adapter: Any, annotations: list[Any]) -> None:
    """Text, limits, values, bands, precision, attachment and visibility of
    every imported dimension: run after import and again once the drawing has
    settled, so a later rebuild cannot hide, detach or rewrite one unseen."""
    hidden = [dimension_name(adapter, annotation) for annotation in annotations
              if int(_early_bound(annotation, "IAnnotation").Visible) != 1]
    if hidden:
        raise RuntimeError(f"imported manufacturing dimensions are hidden: {hidden}")
    _assert_imported_text_and_limits(adapter, annotations)
    assert_manufacturing_dimensions(
        adapter, annotations, part.DRAWING_VALUES_BY_NAME, part.DRAWING_PRECISION_BY_NAME,
        bands={**{name: (-tolerance, tolerance) for name, tolerance in part.DRAWING_TOLERANCES.items()},
               **part.MIN_LIMIT_DEVIATIONS_MM},
    )


@_telemetry.traced("drawing.ms_stick.station_table")
def _station_table(adapter: Any) -> None:
    """Sheet 2's graduation stations: a title, then one note per column."""
    columns = callouts.station_table_columns()
    xs = (STATION_NUMERAL_COLUMN_X,
          *(STATION_FIRST_VALUE_X + index * STATION_COLUMN_PITCH for index in range(len(columns) - 1)))
    for text, x, y in ((callouts.STATION_TABLE_TITLE, *STATION_TITLE_XY),
                       *((column, x, STATION_COLUMNS_TOP) for column, x in zip(columns, xs, strict=True))):
        if add_note(adapter, text, x, y) is None:
            raise RuntimeError(f"failed to add station table note {text.splitlines()[0]!r}")


def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source measuring stick missing: {SOURCE}")
    check("open measuring stick", adapter.open_model(str(SOURCE)))
    source_model = adapter.currentModel
    properties = ("Number", "Revision", "Title", "Material Specification", "Finish",
                  "Quantity", "Manufacturing Notes", "Isometric View Note", "Parent View Note",
                  "Bottom Parent View Note", "Section Parent View Note")
    read_required_properties(source_model, properties, required=properties)
    drawing, _sheet = new_project_drawing(adapter, property_view=PART_STEM,
                                        scale=SHEET_SCALE, layout=SPEC.layout,
                                        unit=part_drawing_unit(PART_STEM))
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="measuring stick manufacturing package")
    stamp_drawing_summary(adapter, drawing, {
        0: "Measuring Stick Manufacturing Drawing",
        1: "Harmonic Analyzer hobby-machinist book drawing",
        2: "Harmonic Analyzer Project", 3: "graduated brass gauge; envelope and engraving",
        4: "Generated from the project-owned ASME B drawing standard",
    })
    ddoc = _early_bound(drawing, "IDrawingDoc")
    if not ddoc.ActivateSheet(SHEET_NAMES[0]):
        raise RuntimeError("failed to activate stick envelope sheet")
    front = place_view(adapter, str(SOURCE), "*Back", *FRONT_CENTER, scale=SHEET_SCALE)
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=SHEET_SCALE)
    # Built-in *Isometric showed only the plain back face (machinist review,
    # run 20261027T054106110Z-752837f3): place the part's ruled-face octant
    # and turn it like the front view so ticks and numerals read.
    iso = place_view(adapter, str(SOURCE), octant_view_name(*callouts.RULED_FACE_ISOMETRIC_OCTANT),
                     *ISO_CENTER, scale=(1.0, 2.0))
    _rotate_ruled_face(adapter, front)
    _rotate_ruled_face(adapter, iso)
    for view in (front, top, iso):
        set_hidden_lines_removed(adapter, view)
    annotations = []
    for view, keep, label in ((front, FRONT_KEEP, "ruled bar"), (top, TOP_KEEP, "bar edge")):
        annotations += curate_view_dimensions(adapter, view, keep=keep, view_label=label,
                                               dimensions_by_feature=part.DRAWING_DIMENSIONS)
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", 0.285, 0.095)

    if not ddoc.ActivateSheet(SHEET_NAMES[1]):
        raise RuntimeError("failed to activate engraving sheet")
    parent = place_view(adapter, str(SOURCE), "*Back", *DETAIL_PARENT_CENTER, scale=(1.0, 2.0))
    _rotate_ruled_face(adapter, parent)
    set_hidden_lines_removed(adapter, parent)
    _label_parent(adapter, DETAIL_PARENT_CENTER)
    owners = tuple(feature for feature, names in part.DRAWING_DIMENSIONS.items()
                   if feature in part.REFERENCE_DIMENSIONS and names & set(DETAIL_KEEP))
    with part_sketches_shown(adapter, source_model, owners,
                            label="graduation dimensions", base_view=parent):
        detail = _engraving_detail(
            adapter, parent,
            model_center=((part.SCALE_START_X + part.DIVISION_SPACING / 2.0) / 1000.0,
                          part.BODY_WIDTH / 2000.0, 0.0),
            view_xy=DETAIL_CENTER, radius_mm=DETAIL_RADIUS_MM, detail_label="A",
            letter_clear_mm=part.BODY_WIDTH / 2.0)
        set_hidden_lines_removed(adapter, detail)
        annotations += curate_view_dimensions(adapter, detail, keep=DETAIL_KEEP,
                                               view_label="graduation detail",
                                               dimensions_by_feature=part.DRAWING_DIMENSIONS)
    _station_table(adapter)

    if not ddoc.ActivateSheet(SHEET_NAMES[2]):
        raise RuntimeError("failed to activate tick lengths sheet")
    for label, parent_xy, detail_xy, model_xy, keep, radius_mm in LENGTH_DETAILS:
        length_parent = place_view(adapter, str(SOURCE), "*Back", *parent_xy, scale=(1.0, 2.0))
        _rotate_ruled_face(adapter, length_parent)
        set_hidden_lines_removed(adapter, length_parent)
        _label_parent(adapter, parent_xy)
        owners = tuple(feature for feature, names in part.DRAWING_DIMENSIONS.items()
                       if feature in part.REFERENCE_DIMENSIONS and names & set(keep))
        with part_sketches_shown(adapter, source_model, owners,
                                label=f"tick length {label}", base_view=length_parent):
            length_detail = _engraving_detail(
                adapter, length_parent,
                model_center=(model_xy[0] / 1000.0, model_xy[1] / 1000.0, 0.0),
                view_xy=detail_xy, radius_mm=radius_mm, detail_label=label,
                letter_clear_mm=model_xy[1], exact=label in EXACT_FENCES)
            set_hidden_lines_removed(adapter, length_detail)
            annotations += curate_view_dimensions(
                adapter, length_detail, keep=keep, view_label=f"tick length {label}",
                dimensions_by_feature=part.DRAWING_DIMENSIONS)

    if not ddoc.ActivateSheet(SHEET_NAMES[3]):
        raise RuntimeError("failed to activate engraving sheet")
    numeral_parent = place_view(
        adapter, str(SOURCE), "*Back", *NUMERAL_PARENT_CENTER, scale=(1.0, 2.0))
    _rotate_ruled_face(adapter, numeral_parent)
    set_hidden_lines_removed(adapter, numeral_parent)
    _label_parent(adapter, NUMERAL_PARENT_CENTER)
    owners = tuple(feature for feature, names in part.DRAWING_DIMENSIONS.items()
                   if feature in part.REFERENCE_DIMENSIONS
                   and names & {*NUMERAL_KEEP, *NUMERAL_10_KEEP})
    with part_sketches_shown(adapter, source_model, owners,
                            label="numeral dimensions", base_view=numeral_parent):
        numeral_y = part.BODY_WIDTH - part.TICK_LENGTH - part.NUMERAL_GAP_MM
        numeral = _engraving_detail(
            adapter, numeral_parent,
            model_center=((part.SCALE_START_X + part.TICK_WIDTH / 2.0
                           + part.NUMERAL_GAP_MM + part.NUMERAL_HEIGHT_MM / 2.0) / 1000.0,
                          numeral_y / 1000.0, 0.0),
            view_xy=NUMERAL_CENTER, radius_mm=NUMERAL_RADIUS_MM, detail_label="F",
            letter_clear_mm=numeral_y)
        set_hidden_lines_removed(adapter, numeral)
        annotations += curate_view_dimensions(
            adapter, numeral, keep=NUMERAL_KEEP, view_label="numeral detail",
            dimensions_by_feature=part.DRAWING_DIMENSIONS)
        numeral_10 = _engraving_detail(
            adapter, numeral_parent,
            model_center=(NUMERAL_10_MODEL_CENTER[0] / 1000.0, NUMERAL_10_MODEL_CENTER[1] / 1000.0, 0.0),
            view_xy=NUMERAL_10_CENTER, radius_mm=NUMERAL_10_RADIUS_MM, detail_label="H",
            letter_clear_mm=NUMERAL_10_MODEL_CENTER[1], exact="H" in EXACT_FENCES)
        set_hidden_lines_removed(adapter, numeral_10)
        annotations += curate_view_dimensions(
            adapter, numeral_10, keep=NUMERAL_10_KEEP, view_label="numeral 10 detail",
            dimensions_by_feature=part.DRAWING_DIMENSIONS)
    # Unturned, unlike the other ruled-face parents: SolidWorks lays the
    # cutting-line letters out in the parent's own frame, so turned 180 degrees
    # each G printed back across its own arrowhead (v46 and 308 sheet 4).
    profile_parent = place_view(
        adapter, str(SOURCE), "*Back", *NUMERAL_PROFILE_PARENT_CENTER, scale=SHEET_SCALE)
    set_hidden_lines_removed(adapter, profile_parent)
    add_property_linked_note(adapter, "Section Parent View Note", *SECTION_PARENT_NOTE_XY)
    profile = _numeral_profile(adapter, profile_parent)
    numeral_depth_annotations = curate_view_dimensions(
        adapter, profile, keep=NUMERAL_DEPTH_KEEP, view_label="numeral V section",
        dimensions_by_feature=part.DRAWING_DIMENSIONS,
    )
    if len(numeral_depth_annotations) != 1:
        raise RuntimeError("expected one own model-linked numeral depth")
    _assert_numeral_depth_owner(numeral_depth_annotations[0])
    annotations += numeral_depth_annotations
    depth_parent = place_view(
        adapter, str(SOURCE), "*Top", *DEPTH_PARENT_CENTER, scale=(1.0, 2.0))
    set_hidden_lines_removed(adapter, depth_parent)
    _label_parent(adapter, DEPTH_PARENT_CENTER, property_name="Bottom Parent View Note")
    depth = _engraving_detail(
        adapter, depth_parent,
        model_center=(part.SCALE_START_X / 1000.0, part.BODY_WIDTH / 1000.0,
                      part.BODY_THICKNESS / 2000.0),
        view_xy=DEPTH_CENTER, radius_mm=DEPTH_RADIUS_MM, detail_label="B",
        letter_clear_mm=part.BODY_THICKNESS / 2.0, scale=DEPTH_SCALE)
    set_hidden_lines_removed(adapter, depth)
    annotations += curate_view_dimensions(adapter, depth, keep=DEPTH_KEEP,
                                           view_label="engraving depth detail",
                                           dimensions_by_feature=part.DRAWING_DIMENSIONS)
    _assert_dimension_contract(adapter, annotations)
    for view in (parent, detail, depth_parent, depth):
        set_hidden_lines_removed(adapter, view)
    return finalize_drawing(adapter, OUTPUTS, pdf_title="Measuring Stick Manufacturing Drawing",
                                  scale=SHEET_SCALE, layout=SPEC.layout,
                                  expected_sheet_names=SHEET_NAMES,
                                  sheet_layouts={name: SPEC.layout for name in SHEET_NAMES},
                                  settled_checks=(lambda: _assert_dimension_contract(adapter, annotations),))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
