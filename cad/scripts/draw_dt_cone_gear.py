r"""Create the complete cone-gear batch drawing package (MHA-DT-03).

Every configured family member T006..T120 by six receives a standalone sheet.
Each sheet selects its own part configuration, imports the native model-owned
blank diameter, bore (T006..T024 a D: diameter, across-flat and flat clock;
T030..T120 round with a hub keyway: diameter, keyway width, T and clock), face
width, driving circular-tooth-thickness requirement and functional
root-envelope limits, plus the actual finite cutter recipe and bounded
carrying-contact data.
The native imported bands remain model-owned. A last sheet defines the T006
tooth space point by point beside its outline (the custom DT6-FORM1 tool is
ground to it); the exact equations stay in the model's "Cutter Profile"
property.

There are no datums, feature-control frames or finish symbols: the bore is a
D or keyed fit that does not run (drawing-guidelines.md rule 6).  Hidden lines
communicate no additional manufacturing fact on these through-bored spur
gears, so every view remains hidden-lines-removed.  The side view stays in
projection with the front view's bore axis; its
face width hangs below it, clear of the Gear Data block. The circular pitch
thickness uses a construction inspection witness of the actual arc size, not
an ideal chord oracle; root MIN/MAX use the actual radial-envelope witness.
The bore prints in an enlarged bore view, DETAIL A, a cropped *Front model
view at a scale that renders every bore at least ``BORE_VIEW_BORE_MIN``
across (its flat is 0.13 deep on T006 and T012); its lettered boundary rings
the bore on the front view, and both views centre-mark the bore. Sheet 21's
plot is DETAIL B, lettered on the T006 front view. Numbered notes name each
mate once: note 1 the bore's sliding fit on MHA-DT-04 (and the MHA-DT-VN-71
key, T030..T120), note 2 the mesh with MHA-DT-12. The part saves both
construction sketches hidden; only the front view, which dimensions them,
shows them.
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    curate_dimensions,
    dimension_name,
    place_view,
    view_name,
)

import _config
from _check import check
from _com import _early_bound, _read_member
from _cone_gear_readback import assert_saved_configuration_topology
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_annotation_extent import callout_ink, move_annotation
from _drawing_dimension_import import _INSERT_DIMS_MARKED, delete_unnamed_imports
from _drawing_dimensions import (
    assert_imported_precision,
    offset_dimension_text,
    set_dimension_callouts,
)
from _drawing_edges import visible_view_entities
import _drawing_hidden_sketches as hidden_sketches
from _drawing_layout_collect import check_drawing_layout
from _drawing_leaders import (
    ARROW_TEXT_CLEARANCE,
    dimension_segments,
    set_near_side_diameter,
)
from _drawing_leader_notes import add_leader_note
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sheets import create_blank_drawing_sheets
from _drawing_view_display import set_hidden_lines_removed
from _fit_deviations import deviations
from _layout_audit import arc_segments
from _layout_geometry import Box, Segment, segment_box_distance
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _pdf_ink import PageInk, read_pdf_ink
from _session import run_build
import _telemetry
import cone_land_key
from cone_shaft_land_bands import FLAT_AF_BAND, SECTION_DIA_BANDS
from dt_cone_gear_notes import (
    CUTTER_DETAIL_SHEET,
    DRAWING_DIMENSIONS,
    T006_NUMBER,
    TOOTH_EDGE_NOTE,
)
from dt_cone_gear_spec import (
    BORE_AF_BAND,
    BORE_AF_PLACES,
    BORE_BAND_PLACES,
    BORE_DIA_BAND,
    BORE_SKETCH,
    CUSTOM_SIX_FORM_TOLERANCE_NOTE,
    CONFIGURATION_TEETH,
    DRAWING_PRECISION_BY_NAME,
    FACE_WIDTH,
    FORM_PLACES,
    KEYED_BORE_SKETCH,
    WEB_REFERENCE_ANGLE_DEG,
    WEB_REFERENCE_TEETH,
    bore_clock_offset_mm,
    bore_dia_mm,
    bore_reach_mm,
    blank_dia_band,
    inch_text,
    tooth_thickness_band,
    bore_flat_af_mm,
    floor_limits_mm,
    gap_floor_deviations_mm,
    keyed,
    outside_dia_mm,
    land_section,
    tooth_thickness_mm,
    custom_six_form_points_mm,
    custom_six_gap_half_angle_rad,
    stock_form_profile,
)
import dt_cone_gear_spec

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE


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
} | {CUTTER_DETAIL_SHEET: (1.0, 1.0)}
SHEET_SCALE = SHEET_SCALES[SHEET_NAMES[0]]

FRONT_CENTER = (0.105, 0.150)
# Projection-aligned with the front view's bore axis (codex, 2026-09-23: the
# 0.140 offset that cleared FaceWidth from Gear Data broke the alignment).
RIGHT_CENTER = (0.245, FRONT_CENTER[1])
ISO_CENTER = (0.355, 0.150)
# The D-bore prints in its own enlarged view: a *Front model view of the
# sheet's configuration, cropped by a circle round the bore (the MHA-DT-VN-61
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
# Gear body kept round the bore inside the crop circle, sheet metres. The
# crop prints no outline (``_crop_bore_view``): drawn, its circle stood 3 mm
# outside the bore and the diameter's outside arrow spanned exactly that
# ring, so the Ø read as landing on the unlabelled circle (ENFORCE round 1
# of #971). Unprinted, the ring only spaces the bore from the clock text:
# 1.5 mm keeps the clock's three-line block's arc (its radius grows with the
# crop) clear of the front view on T114.
BORE_VIEW_CROP_MARGIN = 0.0015
# The view's title stands this far under the crop circle, below the
# across-flat callout's dimension line, the block's bottom edge. The block is
# centred on its SetPosition point (as the clock's is, below), ~5.3 mm a
# row; the flag's line under BORE ACROSS FLAT adds one, so the point drops
# half a row less than the 5 mm it stood at and the bottom stays put.
BORE_VIEW_AF_DROP = 0.0025
BORE_VIEW_LABEL_DROP = 0.016
# A keyway's T text stands right of the title, so the title rises under T's
# dimension line instead of under its text: the larger crop circle (the
# keyway's corners) would otherwise push it into the sheet's zone band.
KEYED_BORE_VIEW_LABEL_DROP = 0.0135
# The diameter's text stands this far above the crop circle (6 mm with the
# value alone): the block is centred there, and the lines under the value
# (two with the mate, one with the note flag) would lower the leader
# shoulder under it ~2.7 mm a line, onto the bore.
BORE_VIEW_DIA_LIFT = 0.0115
# The across-flat text stands OUTSIDE its witnesses, right of the flat's, as
# MHA-DT-07's does. Centred between them, its lines (~2.65 mm a character in
# the #1128 full-5 render) ran wider than the 29-35 mm witness span on every
# sheet, so both witness lines crossed the callout, and its tolerance stack
# sat on the diameter leader's lower end (machinist review of full-5).
# BORE_VIEW_AF_HALF_WIDTH is half the widest line it was sized for, the
# 20-character SLIDES ON MHA-DT-04 (now in note 1), rounded up; the narrower
# BORE ACROSS FLAT keeps more air. The text's left edge clears the flat's
# witness by BORE_VIEW_AF_GAP.
BORE_VIEW_AF_GAP = 0.004
BORE_VIEW_AF_HALF_WIDTH = 0.027
# The flat clock's text, measured with two lines ("90° ±0.25°" over TO TOOTH
# CENTERLINE) in the run-20261010T051729717Z T006 PDF: x 69.8-119.9 mm, y
# 60.0-72.0 mm round its SetPosition point (94.9, 66.0) mm, so the point is
# the block's centre. Its arc ends on the bore's +X axis line with an
# arrowhead at radius |text - vertex|, i.e. under the text: there the axis
# line and arrow ran through the C of CENTERLINE (eye pass of that run). The
# arrowhead (3.6 mm long on that PDF; the document's 6.35 mm arrow-length
# preference is not what this arc end draws) now ends ARROW_TEXT_CLEARANCE
# under the block, and the block's left edge stands CLEAR_GAP_M right of the
# bore view's crop circle. The flag's line over the value makes the block
# three lines, ~18 mm tall; the flag is shorter than TO TOOTH CENTERLINE, so
# the measured width still bounds the block. A
# wider half-width would swing the arc into the front view's box on T114
# (test_bore_view_enlarges_every_d_bore_clear_of_its_neighbours). The native
# readback still refuses an arc sweep under CLOCK_MIN_SWEEP_DEG.
BORE_CLOCK_TEXT_HALF_WIDTH = 0.025
BORE_CLOCK_TEXT_HALF_HEIGHT = 0.009
BORE_CLOCK_TEXT_GAP = 0.002
BORE_CLOCK_ARROW_LENGTH = 0.0036
# swDimensionArrowsSide_e.swDimArrowsInside, set rather than left to the
# document's smart arrows (main's draw_dt_cone_tip_block form). Left smart,
# the clock read whole at the sweep (0-14.6 and 24.2-90 deg about the
# vertex at 35.0 mm) but the settling rebuild drew it with its arrows
# outside on every sheet whose arc is that short (T018-T120, run
# 20261010T073917031Z): two 10 deg stubs beyond the legs, no arc between
# them. At 46.4 mm (T006/T012) smart arrows stayed inside.
ARROWS_INSIDE = 0
# A settled clock's arcs reach both legs within this, and sweep at least
# CLOCK_MIN_SWEEP_DEG between them (the text gap is the rest; T006 swept
# 0-11 and 18-90 deg in that run, 83 deg).
CLOCK_LEG_TOL_DEG = 1.0
CLOCK_MIN_SWEEP_DEG = 45.0
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
# Top-aligned with the numbered notes: the 14-line block (header + 13
# rows) measured 49.1 mm tall natively (e91d2581 layout audit), 3.51 mm a
# line; the 15-line block ends ~52.6 mm down, still above the largest side
# view (top 0.197) with FaceWidth below it.
# The tooth-space sheet keeps the T006 form table out of these dimension/view
# lanes.
GEAR_DATA_POS = (0.215, 0.263)
# Rendered height budget of the Gear Data block, for the layout test.
GEAR_DATA_HEIGHT = 0.056
# The numbered notes (``sheet_notes``) are the sheet's only notes, top-left,
# above the front view's dimensions; their ~100 characters (1.79 mm each at
# 2.5 mm) end left of Gear Data. The part's "Manufacturing Notes" property
# (QTY and the sheet-21 pointer) is not printed: on sheets 2-20 it pointed at
# another part and made five note lines (rule 7, round 4 of the fan-out);
# sheet 1's GEAR DATA already sends the cutter and the relief to sheet 21,
# whose table opens with T006's number, and the title block gives quantity.
NUMBERED_NOTES_POS = (0.015, 0.263)
# Sheet 21 (round 6 of the fan-out, rule 7: the form was a 29-line free-text
# block, its 17 rows unruled and untagged): a one-line title, the points in a
# native general table (POINT | R | X | Y) under it, and two note lines under
# the table, all at the gear sheets' 2.5 mm note height.
FORM_TEXT_HEIGHT = 0.0025
FORM_TITLE_POS = (0.015, 0.263)
FORM_TABLE_POS = (0.015, 0.257)
FORM_TABLE_HEADINGS = ("POINT", "R", "X", "Y")
FORM_TABLE_COLUMN_WIDTHS = (0.013, 0.015, 0.015, 0.015)
FORM_TABLE_ROW_HEIGHT = 0.0045
FORM_NOTES_GAP = 0.004
# swBOMConfigurationAnchorType_e.swBOMConfigurationAnchor_TopLeft: the anchor
# is the table's top-left corner, as the layout audit boxes tables
# (_drawing_layout_collect._table_element).
_TABLE_ANCHOR_TOP_LEFT = 1
_TABLE_HEADER_TOP = 1  # swTableHeaderPosition_e.swTableHeader_Top
_TABLE_SIZE_CAN_CHANGE = 0  # swTableRowColSizeChangeBehavior_e
# Where the tooth-space sheet's hidden title-block source view stands (see
# build): clear of the table, inside the border.
CUTTER_SOURCE_VIEW_CENTER = (0.325, 0.155)
# The tooth-space plot beside the table (ENFORCE round 4 of #971: a table
# alone left the sheet bunched in one corner, rule 15). The table governs; the
# plot draws the same rows at FORM_PLOT_SCALE with P1 (X0 Y0) on the CL at
# FORM_PLOT_ORIGIN. At 75:1 the space spans x 0.207-0.353 and y 0.139-0.202,
# right of the table (x <= 0.073) and above the title block (y 0.064).
FORM_PLOT_SCALE = 75.0
FORM_PLOT_ORIGIN = (0.280, 0.140)
# The CL runs this far below Y0 and above the blank OD; the X axis this far
# right of the CL.
FORM_PLOT_CL_OVERRUN = 0.008
FORM_PLOT_X_AXIS_LENGTH = 0.085
# The R stations are drawn left of the CL only, out to these |X| (mm), so
# their labels stand clear of the X axis.
FORM_PLOT_STATION_REACH_MM = {"junction": 1.10, "blank": 1.25}
FORM_PLOT_INVOLUTE_SAMPLES = 16
FORM_PLOT_TITLE_POS = (0.205, 0.240)
# A station label's top-left, from its arc's left end: wholly left of the end,
# where the arc only rises away to the right.
FORM_PLOT_STATION_LABEL_OFFSET = (-0.019, 0.002)


def form_plot_xy(x_mm: float, y_mm: float) -> tuple[float, float]:
    """Sheet position (m) of table point (X, Y) mm on the tooth-space plot."""
    return (
        FORM_PLOT_ORIGIN[0] + x_mm * FORM_PLOT_SCALE / 1000.0,
        FORM_PLOT_ORIGIN[1] + y_mm * FORM_PLOT_SCALE / 1000.0,
    )


def form_plot_flank_mm() -> list[tuple[float, float]]:
    """One flank (+X) of the T006 space as table (X, Y), root arc end up.

    Straight lines row to row from where the relief leaves the root arc to the
    junction (the table's own rule), then the involute sampled to the blank.
    """
    points = custom_six_form_points_mm()
    template = stock_form_profile(6).template
    root = template.root_radius_mm
    junction = template.relief_junction_radius_mm
    blank = points[-1][0]
    flank = [(x, y) for radius, x, y in points[1:] if radius <= junction + 1e-9]
    for index in range(1, FORM_PLOT_INVOLUTE_SAMPLES + 1):
        radius = junction + (blank - junction) * index / FORM_PLOT_INVOLUTE_SAMPLES
        half = custom_six_gap_half_angle_rad(radius)
        flank.append((radius * math.sin(half), radius * math.cos(half) - root))
    return flank


def form_plot_station_mm(radius_mm: float, reach_mm: float) -> tuple[float, float]:
    """Table (X, Y) where the station arc of ``radius_mm`` stops, left of CL."""
    root = stock_form_profile(6).template.root_radius_mm
    return (-reach_mm, math.sqrt(radius_mm**2 - reach_mm**2) - root)


def form_plot_labels() -> list[tuple[str, tuple[float, float]]]:
    """(text, top-left sheet position) of the plot's notes."""
    template = stock_form_profile(6).template
    blank = custom_six_form_points_mm()[-1][0]
    junction = template.relief_junction_radius_mm
    top = form_plot_xy(0.0, custom_six_form_points_mm()[-1][2])[1]
    labels = [
        # A lettered detail of the T006 sheet's 12 o'clock space (rule 9;
        # the prose title "T006 TOOTH SPACE PLOTTED 75:1 FROM THE TABLE"
        # named it only in words). It draws the table's own rows, and the
        # title block's DO NOT SCALE covers scaling off it, so the old
        # "(TABLE GOVERNS)" goes with the prose title.
        (form_plot_label(), FORM_PLOT_TITLE_POS),
        ("CL", (FORM_PLOT_ORIGIN[0] - 0.003, top + FORM_PLOT_CL_OVERRUN + 0.006)),
        (
            "+X",
            (FORM_PLOT_ORIGIN[0] + FORM_PLOT_X_AXIS_LENGTH + 0.002,
             FORM_PLOT_ORIGIN[1] + 0.002),
        ),
    ]
    for key, radius in (("junction", junction), ("blank", blank)):
        x, y = form_plot_xy(
            *form_plot_station_mm(radius, FORM_PLOT_STATION_REACH_MM[key])
        )
        labels.append((
            f"R{inch_text(radius, 4)}",
            (x + FORM_PLOT_STATION_LABEL_OFFSET[0], y + FORM_PLOT_STATION_LABEL_OFFSET[1]),
        ))
    return labels


# Each tag's text top-left from the point its leader lands on (sheet m). The
# root and relief rows P3-P11 stand 1.3-7.7 mm apart at 75:1, too close to
# tag one by one; their zone label names them (P2-P12). A tag's native box
# spans its text AND its leader's landing (round 7 of the fan-out: P1/P2,
# P12/P13 and P15/P16 overlapped by 1.3-7.7 mm), so neighbours alternate
# sides: P1 down-right of the origin and P2 right of it, under the X axis;
# P12, P14, P15 and P17 inside the space, up-left of the flank; P13 and P16
# outside it, down-right.
FORM_TAG_TEXT_OFFSETS = {
    1: (0.004, -0.009),
    2: (0.002, -0.0037),
    12: (-0.011, 0.005),
    13: (0.0047, -0.0014),
    14: (-0.012, 0.007),
    15: (-0.0085, 0.0069),
    16: (0.0048, -0.0008),
    17: (-0.011, 0.0075),
}
# The zone labels' text top-left from their leaders' landings: the root arc's
# on the -X half (the +X half carries P1's and P2's tags), the straight lines'
# right of the relief, the involute's right of and below its flank.
FORM_ZONE_TEXT_OFFSETS = {
    "root": (-0.0466, -0.0049),
    "straight": (0.0123, 0.0007),
    "involute": (0.011, -0.007),
}


def form_point_tags() -> list[tuple[str, tuple[float, float], tuple[float, float]]]:
    """(text, text top-left, leader landing) of each point tag on DETAIL B."""
    points = custom_six_form_points_mm()
    tags = []
    for number, (dx, dy) in FORM_TAG_TEXT_OFFSETS.items():
        _radius, x, y = points[number - 1]
        tip = form_plot_xy(x, y)
        text = f"P{number}"
        tags.append((text, (tip[0] + dx, tip[1] + dy), tip))
    return tags


def form_zones() -> tuple[int, int]:
    """(last root-arc point, junction point), 1-based: the root arc runs
    P1-P2, straight lines row to row up to the junction row (the row at the
    junction radius, rounded outward a fraction of a print step), then the
    involute to the blank OD."""
    points = custom_six_form_points_mm()
    junction = stock_form_profile(6).template.relief_junction_radius_mm
    nearest = min(
        range(len(points)), key=lambda index: abs(points[index][0] - junction)
    )
    return 2, nearest + 1


def form_zone_labels() -> list[tuple[str, tuple[float, float], tuple[float, float]]]:
    """(text, text top-left, leader landing) of DETAIL B's three zone labels."""
    template = stock_form_profile(6).template
    root = template.root_radius_mm
    points = custom_six_form_points_mm()
    root_end, straight_end = form_zones()
    # Half way round the root arc from P1 to P2, on the -X half.
    _r, x2, y2 = points[root_end - 1]
    half = math.atan2(x2, y2 + root) / 2.0
    root_tip = form_plot_xy(-root * math.sin(half), root * math.cos(half) - root)
    # Half way along the relief's straight lines, on a row-to-row line.
    middle = (root_end + straight_end) // 2
    (_ra, xa, ya), (_rb, xb, yb) = points[middle - 1], points[middle]
    straight_tip = form_plot_xy((xa + xb) / 2.0, (ya + yb) / 2.0)
    # On the involute half way up it.
    radius = (points[straight_end - 1][0] + points[-1][0]) / 2.0
    angle = custom_six_gap_half_angle_rad(radius)
    involute_tip = form_plot_xy(radius * math.sin(angle), radius * math.cos(angle) - root)
    zones = (
        ("root", f"ROOT ARC R{inch_text(root, FORM_PLACES)}, P1-P{root_end}", root_tip),
        ("straight", f"STRAIGHT LINES P{root_end}-P{straight_end}", straight_tip),
        (
            "involute",
            f"INVOLUTE, BASE R{inch_text(template.base_radius_mm, FORM_PLACES)}, "
            f"P{straight_end}-P{len(points)}",
            involute_tip,
        ),
    )
    labels = []
    for key, text, tip in zones:
        dx, dy = FORM_ZONE_TEXT_OFFSETS[key]
        labels.append((text, (tip[0] + dx, tip[1] + dy), tip))
    return labels


def _draw_form_plot(adapter: Any) -> None:
    """Sketch the tooth-space plot on the active sheet and label it.

    Sheet sketch lines carry no dimensions: the sizes stay in the table.
    """
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    draw.ClearSelection2(True)
    ddoc.EditSheet()
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    root = stock_form_profile(6).template.root_radius_mm
    axis = form_plot_xy(0.0, -root)
    flank = form_plot_flank_mm()
    created = []
    previous_add_to_db = bool(manager.AddToDB)
    manager.AddToDB = True
    try:
        for side in (1.0, -1.0):
            sheet_points = [form_plot_xy(side * x, y) for x, y in flank]
            for start, end in zip(sheet_points, sheet_points[1:]):
                created.append(("flank", manager.CreateLine(*start, 0.0, *end, 0.0)))
        root_right = form_plot_xy(*flank[0])
        root_left = form_plot_xy(-flank[0][0], flank[0][1])
        # +1: counter-clockwise from the right end over the CL to the left.
        created.append((
            "root arc",
            manager.CreateArc(*axis, 0.0, *root_right, 0.0, *root_left, 0.0, 1),
        ))
        top = form_plot_xy(0.0, custom_six_form_points_mm()[-1][2])[1]
        created.append((
            "CL",
            manager.CreateCenterLine(
                FORM_PLOT_ORIGIN[0], FORM_PLOT_ORIGIN[1] - FORM_PLOT_CL_OVERRUN, 0.0,
                FORM_PLOT_ORIGIN[0], top + FORM_PLOT_CL_OVERRUN, 0.0,
            ),
        ))
        created.append((
            "X axis",
            manager.CreateCenterLine(
                *FORM_PLOT_ORIGIN, 0.0,
                FORM_PLOT_ORIGIN[0] + FORM_PLOT_X_AXIS_LENGTH, FORM_PLOT_ORIGIN[1], 0.0,
            ),
        ))
        template = stock_form_profile(6).template
        blank = custom_six_form_points_mm()[-1][0]
        for key, radius in (
            ("junction", template.relief_junction_radius_mm), ("blank", blank)
        ):
            start = form_plot_xy(0.0, radius - root)
            end = form_plot_xy(
                *form_plot_station_mm(radius, FORM_PLOT_STATION_REACH_MM[key])
            )
            arc = manager.CreateArc(*axis, 0.0, *start, 0.0, *end, 0.0, 1)
            created.append((f"R{inch_text(radius, 4)} station", arc))
            if arc is not None:
                _early_bound(arc, "ISketchSegment").ConstructionGeometry = True
    finally:
        manager.AddToDB = previous_add_to_db
    missing = sorted({label for label, segment in created if segment is None})
    if missing:
        raise RuntimeError(f"failed to sketch the tooth-space plot's {missing}")
    draw.ClearSelection2(True)
    for text, position in form_plot_labels():
        if add_note(adapter, text, *position) is None:
            raise RuntimeError(f"failed to add the tooth-space plot note {text!r}")
    # Point tags and zone labels: pointers to the plot's sheet geometry, not
    # attachments (the plot's lines are sheet sketch entities).
    for text, text_xy, tip in (*form_point_tags(), *form_zone_labels()):
        note = add_leader_note(
            adapter, text, text_xy=text_xy, attach_xy=tip, label=f"DETAIL B {text}"
        )
        _set_note_height(note, FORM_TEXT_HEIGHT, label=f"DETAIL B {text}")
    _telemetry.info(
        f"T006 tooth-space plot: {len(created)} sheet sketch entities at "
        f"{FORM_PLOT_SCALE:.0f}:1, P1 at "
        f"{tuple(round(value * 1000, 1) for value in FORM_PLOT_ORIGIN)} mm"
    )


def form_table_rows() -> list[tuple[str, str, str, str]]:
    """The T006 tooth space, point by point: the heading, then P1-P17.

    The sheet once printed the part's "Cutter Profile" property: parametric
    equations with 17-digit floats, which no shop grinds to (eye pass of
    run 20261010T051729717Z). Then it printed reference chords, which left
    the relief undefined (machinist review of the stack build), then the rows
    as a 29-line free-text block (round 6 of the fan-out, rule 7). It gives
    the form point by point at four inch places in a native table, read from
    the same profile the native cut uses
    (dt_cone_gear_spec.custom_six_form_points_mm); DETAIL B's zone labels say
    how the points connect (the round-2 review: points alone let templates
    differ between them).

    It is T006 geometry, not a tool drawing: as "DT6-FORM1 GROUND FORM
    TOOL" it carried the gear's title block (part, number, brass) and no tool
    material, and told the shop how to inspect the tool (ENFORCE round 1 of
    #971; #1427). T006 cuts at T=0 on a spur (helix 0) gear, so its tooth
    space IS the custom cutter's edge: the shop grinds its own tool to this
    space, in whatever tool steel it uses, and accepts the cut gear by sheet
    1's note 2.
    """
    profile = stock_form_profile(6)
    template = profile.template
    if template.cutter_number is not None or template.name != CUTTER_DETAIL_SHEET:
        raise ValueError("T006 must use the specified DT6-FORM1 custom cutter")
    if profile.radial_translation_mm != 0.0 or profile.helix_angle_deg != 0.0:
        raise ValueError("the T006 tooth space is DT6-FORM1's form only at T=0, helix 0")
    return [
        FORM_TABLE_HEADINGS,
        *(
            (
                f"P{number}",
                inch_text(radius, FORM_PLACES),
                inch_text(x, FORM_PLACES),
                inch_text(y, FORM_PLACES),
            )
            for number, (radius, x, y) in enumerate(custom_six_form_points_mm(), 1)
        ),
    ]


def form_sheet_title() -> str:
    """The one line over the table: whose space this is, in which unit."""
    return (
        f"{T006_NUMBER} TOOTH SPACE, INCH "
        f"(CONTINUED FROM SHEET {SHEET_NAMES.index('T006') + 1})"
    )


def form_sheet_notes() -> str:
    """The two lines under the table: what R, X and Y are measured from, and
    the form band with its route to the mate. The band's mesh and acceptance
    are sheet 1's note 2; no second copy here (rule 4: a mate once)."""
    return "\n".join((
        "R FROM GEAR AXIS; X FROM CL, EACH SIDE; Y ALONG CL FROM P1.",
        f"{CUSTOM_SIX_FORM_TOLERANCE_NOTE}, SEE SHEET "
        f"{SHEET_NAMES.index('T006') + 1} NOTE {TEETH_NOTE_NUMBER}.",
    ))


def form_notes_pos(table_height: float | None = None) -> tuple[float, float]:
    """Top-left of the notes under the table: under the rows as set, or as
    the seat measured them (a row grows to fit its text)."""
    if table_height is None:
        table_height = len(form_table_rows()) * FORM_TABLE_ROW_HEIGHT
    return (FORM_TABLE_POS[0], FORM_TABLE_POS[1] - table_height - FORM_NOTES_GAP)


def _insert_form_table(adapter: Any) -> Any:
    """The P1-P17 table: a native general table (IDrawingDoc
    InsertTableAnnotation2, no template), top-left anchored at
    FORM_TABLE_POS, one heading row, read back cell by cell."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    rows = form_table_rows()
    columns = len(FORM_TABLE_HEADINGS)
    draw.ClearSelection2(True)
    raw = ddoc.InsertTableAnnotation2(
        False, *FORM_TABLE_POS, _TABLE_ANCHOR_TOP_LEFT, "", len(rows), columns
    )
    if raw is None:
        raise RuntimeError("InsertTableAnnotation2 refused the T006 point table")
    # Indexed COM properties (Text2) need the generated early-bound wrapper
    # (_drawing_tables.insert_hole_table).
    table = _sw_type_info.early_bound(raw, "ITableAnnotation")
    if not _sw_type_info.is_early_bound(table, "ITableAnnotation"):
        raise RuntimeError("ITableAnnotation early-bound wrapper is unavailable")
    shape = (int(table.RowCount), int(table.ColumnCount))
    if shape != (len(rows), columns):
        raise RuntimeError(f"T006 point table is {shape}, expected {(len(rows), columns)}")
    if int(table.GetHeaderCount()) != 1:
        table.SetHeader(_TABLE_HEADER_TOP, 1)
        if int(table.GetHeaderCount()) != 1:
            raise RuntimeError("T006 point table refused its one heading row")
    text_format = _early_bound(table.GetTextFormat(), "ITextFormat")
    text_format.CharHeight = FORM_TEXT_HEIGHT
    if table.SetTextFormat(False, text_format) is not True:
        raise RuntimeError("T006 point table refused its text height")
    for row, cells in enumerate(rows):
        for column, text in enumerate(cells):
            table.SetText2(row, column, False, text)
    for column, width in enumerate(FORM_TABLE_COLUMN_WIDTHS):
        actual = float(table.SetColumnWidth(column, width, _TABLE_SIZE_CAN_CHANGE))
        if abs(actual - width) > 1e-6:
            raise RuntimeError(f"T006 point table column {column} width reads {actual!r}")
    for row in range(len(rows)):
        table.SetRowHeight(row, FORM_TABLE_ROW_HEIGHT, _TABLE_SIZE_CAN_CHANGE)
    rebuild_drawing(adapter, label="T006 point table")
    printed = [
        tuple(str(table.DisplayedText2(row, column, False) or "") for column in range(columns))
        for row in range(len(rows))
    ]
    if printed != [tuple(cells) for cells in rows]:
        raise RuntimeError(f"T006 point table reads {printed!r}, expected {rows!r}")
    heights = [float(table.GetRowHeight(row)) for row in range(len(rows))]
    if any(height < FORM_TABLE_ROW_HEIGHT - 1e-4 for height in heights):
        raise RuntimeError(f"T006 point table row heights read {heights!r}")
    annotation = _early_bound(table.GetAnnotation(), "IAnnotation")
    position = tuple(float(value) for value in (annotation.GetPosition() or ()))
    if len(position) < 2 or math.dist(position[:2], FORM_TABLE_POS) > 1e-4:
        raise RuntimeError(f"T006 point table anchor reads {position!r}")
    draw.ClearSelection2(True)
    _telemetry.success(f"T006 point table: {len(rows) - 1} points, {columns} columns")
    return table


# Each tight band names its mate and fit (drawing-guidelines rule 4; ENFORCE
# round 1 of #971 found them only in Gear Data, or nowhere). A mate serving
# several dimensions is named once, in one numbered note those dimensions
# flag (rule 4; screen of f21dfcdd2ba7: SLIDES ON MHA-DT-04 printed on both
# the bore's diameter and its across-flat, MHA-DT-12 on the tip, thickness
# and root): note 1 holds the bore's fit on MHA-DT-04 (and, on the keyed
# T030..T120, the MHA-DT-VN-71 key's), note 2 the teeth's mesh with
# MHA-DT-12 (``sheet_notes``).
SHAFT_MATE = "MHA-DT-04"
# A matched pair names its mate by name and number (rule 4; round-1 review
# of the fan-out: note 1 named MHA-DT-04 by number only, and no land).
SHAFT_NAME = str(_config.parts("dt-cone-gear-shaft")["title"]).upper()
CYLINDER_MATE = "MHA-DT-12"
# Land 1's key (owner decision 2026-11-09, C1 keyed, PR #1992), named by
# number like the shaft.
KEY_MATE = "MHA-DT-VN-71"
BORE_NOTE_NUMBER = 1
TEETH_NOTE_NUMBER = 2
BORE_NOTE_FLAG = f"SEE NOTE {BORE_NOTE_NUMBER}"
TEETH_NOTE_FLAG = f"SEE NOTE {TEETH_NOTE_NUMBER}"
DIMENSION_CALLOUTS = {
    # No process word: a reamer would cut away the flat, and the dimensions
    # define the D-profile (user ruling 2026-09-29, machinist review of the
    # #1128 full build). The flag hangs under the value in rows as narrow as
    # the value: on T006/T012 the flat's witness for the clock rises ~3 mm
    # right of it, and a wider block's shoulder crosses that witness.
    "BoreCutDia": f"THRU\n{BORE_NOTE_FLAG}",
    # The value is the gear bore's own; naming the bore, not the shaft it
    # slides on, keeps it from reading as MHA-DT-04's across-flat.
    "BoreAF": f"BORE ACROSS FLAT\n{BORE_NOTE_FLAG}",
    # The flat's normal runs through the bore axis and the +X tooth's centre;
    # the bore view crops the teeth off, so the callout names the reference
    # its centre-mark line stands for.
    "BoreFlatClock": "TO TOOTH CENTERLINE",
    # The keyed bore (T030..T120) is round, so it takes the fit bore's REAM
    # (rule 7); its keyway's width band is the requirement, with no process
    # word.  T names what it reaches, the D's BoreAF form.
    "KeyedBoreDia": f"REAM THRU\n{BORE_NOTE_FLAG}",
    "KeywayWidth": BORE_NOTE_FLAG,
    "KeywayT": f"KEYWAY TO FAR SIDE\n{BORE_NOTE_FLAG}",
    "KeywayClock": "TO TOOTH CENTERLINE",
    # The text is the same on every sheet: offset (OffsetText), the imported
    # model dimension printed the LAST sheet's below-text on all of them (T006
    # printed T120's "ON PITCH CIRCLE Ø63.500", farm runs of 746809f62 and
    # 5000ea76b), so no per-configuration size can ride on it. The name
    # stands over the value (CALLOUTS_ABOVE) and GEAR DATA prints the pitch
    # diameter it is measured on: the callout keeps two lines of words
    # (rule 7; screen of f21dfcdd2ba7 counted three). The short flag is the
    # bottom row, so the shelf's leader closes on the block clear of it.
    "ToothThickness": TEETH_NOTE_FLAG,
    # The origin circle is an inspection witness, not the off-centre root arc.
    "FloorDia": f"ROOT ENVELOPE\n{TEETH_NOTE_FLAG}",
    # The cone set is a solid stack on the shaft; each gear's width sets the
    # stations (user ruling 2026-09-28, spec FACE_WIDTH).
    "FaceWidth": f"20-GEAR STACK\nON {SHAFT_MATE}",
    # RV-03's accepted T012 web (cad/config/parts/dt-cone-gear.yaml): what the
    # single limit bounds, at the value.
    "WebMin": "WEB, BORE TO ROOT",
}


# Text over the value. One line each: SOLIDWORKS drops a multi-line callout
# above a value from the print (ENFORCE round 2 of #971: every two-line one
# went unmatched in the PDF; draw_ch_amplitude_bar r1).
CALLOUTS_ABOVE = {
    "ToothThickness": "CIRCULAR TOOTH THICKNESS",
    "BlankDia": TEETH_NOTE_FLAG,
    "BoreFlatClock": BORE_NOTE_FLAG,
    "KeywayClock": BORE_NOTE_FLAG,
}
if any("\n" in text for text in CALLOUTS_ABOVE.values()):
    raise AssertionError("an above-callout with a line break does not print")


def _inch_limits(lower_mm: float, upper_mm: float) -> str:
    return f"{inch_text(lower_mm, 4)}-{inch_text(upper_mm, 4)}"


def bore_clearances_mm(teeth: int) -> tuple[tuple[float, float], tuple[float, float]]:
    """((min, max) round, (min, max) across-flat or keyway-to-key) clearance
    of the sheet's bore on its MHA-DT-04 land, from the parts' printed limits.

    Bore and land share their nominals (gear_seat_fit), so each round or
    across-flat clearance is the bore's deviation less the land's; a keyway's
    is its width's against the key's (cone_land_key).
    """
    land_upper, land_lower = SECTION_DIA_BANDS[land_section(teeth)]
    bore_upper, bore_lower = BORE_DIA_BAND
    round_fit = (bore_lower - land_upper, bore_upper - land_lower)
    if keyed(teeth):
        return round_fit, cone_land_key.KEYWAY_SIDE_CLEARANCE_MM
    flat_upper, flat_lower = FLAT_AF_BAND
    af_upper, af_lower = BORE_AF_BAND
    return round_fit, (af_lower - flat_upper, af_upper - flat_lower)


def sheet_notes(teeth: int) -> str:
    """The sheet's numbered notes, flagged from the bore and teeth callouts.

    Note 1 is the bore's matched fit (rule 4): its bands are narrower than
    the shop's turned and milled rows, so the bore is made to the measured
    land, with the clearance the parts' limits give as REF; a keyed bore
    names the key its keyway slides on. Note 2 names the mesh and the fit
    route of the tip, thickness and root bands: the over-pins and assembly
    backlash acceptances in GEAR DATA; it carries the teeth's do-not-cut,
    flagged to them rather than in a general block.
    """
    (round_min, round_max), (second_min, second_max) = bore_clearances_mm(teeth)
    land = f"\u00d8{inch_text(bore_dia_mm(teeth), BORE_BAND_PLACES)} LAND"
    if keyed(teeth):
        fit = (
            f"{BORE_NOTE_NUMBER}. SLIDING FIT ON {SHAFT_NAME} {SHAFT_MATE}, {land}, "
            f"AND KEY {KEY_MATE}:",
            "   BORE MADE TO THE MEASURED LAND "
            f"(CLEARANCE {_inch_limits(round_min, round_max)} ON \u00d8, "
            f"{_inch_limits(second_min, second_max)} KEYWAY TO KEY).",
        )
    else:
        land += f", {inch_text(bore_flat_af_mm(teeth), BORE_AF_PLACES)} ACROSS FLAT"
        fit = (
            f"{BORE_NOTE_NUMBER}. SLIDING FIT ON {SHAFT_NAME} {SHAFT_MATE}, {land}:",
            "   BORE AND FLAT MADE TO THE MEASURED LAND "
            f"(CLEARANCE {_inch_limits(round_min, round_max)} ON \u00d8, "
            f"{_inch_limits(second_min, second_max)} ACROSS FLAT).",
        )
    return "\n".join((
        *fit,
        f"{TEETH_NOTE_NUMBER}. TEETH MESH WITH {CYLINDER_MATE}: ACCEPT OVER PINS, "
        "THEN BY BACKLASH AT ASSEMBLY,",
        f"   PER GEAR DATA. {TOOTH_EDGE_NOTE}",
    ))


def sheet_dimension_names(teeth: int) -> set[str]:
    """The model dimensions the sheet prints: every marked one but the other
    bore's, and RV-03's web on the T012 sheet only."""
    other = dt_cone_gear_spec.DRAWING_DIMENSIONS[
        BORE_SKETCH if keyed(teeth) else KEYED_BORE_SKETCH
    ]
    names = set().union(*DRAWING_DIMENSIONS.values()) - other
    if teeth != WEB_REFERENCE_TEETH:
        names.discard("WebMin")
    return names


def rendered_half_od(teeth: int) -> float:
    numerator, denominator = _SCALE_BY_TEETH[teeth]
    return outside_dia_mm(teeth) * numerator / (denominator * 2000.0)


def rendered_half_face_width(teeth: int) -> float:
    numerator, denominator = _SCALE_BY_TEETH[teeth]
    return FACE_WIDTH * numerator / (denominator * 2000.0)


# The functional root-envelope stack stands right of the tip circle,
# above the thickness witness and the thickness text's shelf
# (``tooth_thickness_shelf``), and clear of the side
# view (left edge >= 0.219 on every sheet). The gap was sized for a mate's row
# ~4 chars wider than the label (centred block); the note flag under the label
# is narrower, so the block's left edge stands farther from the teeth.
FLOOR_DIA_GAP_X = 0.0215
# The shelf's rise above 0.6 of the tip radius: 6 mm with the three-row stack;
# the row under the label (centred block) would lower it ~2.8 mm.
FLOOR_DIA_RISE = 0.009
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
# The limit stack hangs ~11 mm from its anchor down to the shelf line (four
# rows, the label and the mate under the limits, at the ~5.7 mm pitch of the
# ENFORCE round-1 T084 render's three-row block), rounded outward; it is
# centred on the anchor, so the same half-height bounds its top.
FLOOR_STACK_HALF_HEIGHT = 0.0115
# The thickness text stands on its own shelf right of the +X tooth, under the
# root-envelope stack. Hung off its dimension line (horizontal text outside
# the witnesses), the block started AT that line, so the line dropping from
# the 3 o'clock tooth ran down the C of CIRCULAR, 0.19 mm of air on every
# sheet (machinist review of 2056e3344, rule 14). The text is offset
# (OffsetText): the line stays at the tooth, and its leader leaves the line's
# midpoint for the shelf's near end, closing on the block's lower-left
# corner from up-left. This gap keeps that leader 2.7 mm off the C on the
# steepest sheet (T012), and the block's right end 3.2 mm left of the side
# view on the tightest (T084), replayed on that run's printed ink.
TOOTH_THICKNESS_TEXT_GAP = 0.0065
# The shelf stands this far under the root-envelope anchor: the block's ink,
# 24.7 mm from shelf to top row on every sheet of run 20261024T091056564Z,
# then tops out 3.3 mm under that stack's shelf, which printed 10.1 mm under
# its anchor.
TOOTH_THICKNESS_SHELF_DROP = 0.038
# Offset text is centred on its position (_drawing_annotation_extent). The
# seed puts that centre half the 64.2 mm shelf right of, and 12.9 mm above,
# the shelf's start (run 20261024T091056564Z); the measured shelf then
# corrects it to within the tolerance.
TOOTH_THICKNESS_SEED = (0.0321, 0.0129)
TOOTH_THICKNESS_PLACE_TOL = 0.0002
# Printed air the exported PDF must keep between the callout's glyphs and
# every line but its own shelf: the fleet's arrow-to-text clearance.
TOOTH_THICKNESS_TEXT_AIR = ARROW_TEXT_CLEARANCE


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


# RV-03's T012 web text sits on its own dimension line, carried outboard past
# the tip circle by this much (sheet metres).  Offset square to the line
# (r3, r4 reviews), the extension lines ran through the text.
WEB_MIN_TEXT_OUTBOARD = 0.012


def web_min_text_xy() -> tuple[float, float]:
    """Sheet point of the T012 web text: on its radial line, outside the teeth."""
    reach = rendered_half_od(WEB_REFERENCE_TEETH) + WEB_MIN_TEXT_OUTBOARD
    angle = math.radians(WEB_REFERENCE_ANGLE_DEG)
    return (
        FRONT_CENTER[0] + reach * math.cos(angle),
        FRONT_CENTER[1] + reach * math.sin(angle),
    )


def front_keep(teeth: int) -> dict[str, tuple[float, float]]:
    half_od = rendered_half_od(teeth)
    keep = {
        "FloorDia": (FRONT_CENTER[0] + half_od + FLOOR_DIA_GAP_X, floor_dia_y(teeth)),
        # Vertical dimension on the +X tooth: the anchor's x places its
        # line just right of the tip circle. Its y is where the import first
        # hangs the text, below the gear; the text then leaves the line for
        # its own shelf (``_shelve_tooth_thickness``).
        "ToothThickness": (
            FRONT_CENTER[0] + half_od + 0.014,
            FRONT_CENTER[1] - half_od - 0.0225,
        ),
    }
    # Only the T012 sheet states RV-03's web; no other sheet shows its sketch.
    if teeth == WEB_REFERENCE_TEETH:
        keep["WebMin"] = web_min_text_xy()
    return keep


def tooth_thickness_shelf(teeth: int) -> tuple[float, float]:
    """Sheet point where the thickness text's shelf starts: the text gap
    right of its dimension line, the shelf drop under the root-envelope
    stack's anchor."""
    line_x = front_keep(teeth)["ToothThickness"][0]
    shelf_y = floor_dia_y(teeth) - TOOTH_THICKNESS_SHELF_DROP
    return line_x + TOOTH_THICKNESS_TEXT_GAP, shelf_y


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
    """Sheet radius of the bore view's crop circle round the bore axis: the
    bore's reach (a keyway's top corners) plus the margin."""
    return bore_reach_mm(teeth) * _bore_view_ratio(teeth) / 1000.0 + BORE_VIEW_CROP_MARGIN


def clock_dimension_name(teeth: int) -> str:
    """The sheet's clock: the D's flat or the keyway's top to the centreline."""
    return "KeywayClock" if keyed(teeth) else "BoreFlatClock"


def bore_clock_vertex(teeth: int) -> tuple[float, float]:
    """Sheet point where the flat (keyway top) crosses the bore's horizontal
    centreline: the clock dimension's vertex."""
    flat = bore_clock_offset_mm(teeth) * _bore_view_ratio(teeth) / 1000.0
    return BORE_VIEW_CENTER[0] + flat, BORE_VIEW_CENTER[1]


# The keyway's width (T030..T120) prints right of the crop circle under the
# axis, the clock's mirror: its dimension line stands at the text, its
# witnesses run right from the keyway top's corners. Its block (value and
# band over the note flag, two rows) is sized like the clock's lines; T's
# text then stands right of it, so T's dimension line runs on under it.
KEYWAY_WIDTH_TEXT_HALF_WIDTH = 0.014
KEYWAY_WIDTH_TEXT_HALF_HEIGHT = 0.006


def bore_view_keep(teeth: int) -> dict[str, tuple[float, float]]:
    """Text positions of the bore dimensions round the bore view.

    The diameter's leader runs in from upper left; the across-flat's (T's)
    dimension line hangs under the crop circle between its witnesses (the
    arc's -X point and the flat or keyway top) and runs on right to its
    text, which stands outside that witness (and, keyed, right of the
    keyway width's block); the clock's arc sweeps the quadrant between the
    flat's (keyway top's) upper half and the +X centre-mark line
    (``_sweep_clock_right_of_flat``), its text right of the circle and
    raised clear of the axis line and the arc's arrowhead on it
    (BORE_CLOCK_TEXT_*). The keyway width's text mirrors the clock's under
    the axis.
    """
    ratio = _bore_view_ratio(teeth)
    flat = bore_clock_offset_mm(teeth) * ratio / 1000.0
    crop = bore_view_crop_radius(teeth)
    x, y = BORE_VIEW_CENTER
    # 3 mm right of x - 0.022: the inch seat band (+0.04572/+0.0254)
    # ran the text 1.6 mm past the left inner border (#290 batch 0).
    diameter = (x - 0.019, y + crop + BORE_VIEW_DIA_LIFT)
    clock = (
        x + crop + BORE_CLOCK_TEXT_GAP + BORE_CLOCK_TEXT_HALF_WIDTH,
        y + BORE_CLOCK_ARROW_LENGTH + ARROW_TEXT_CLEARANCE + BORE_CLOCK_TEXT_HALF_HEIGHT,
    )
    if not keyed(teeth):
        return {
            "BoreCutDia": diameter,
            "BoreAF": (
                x + flat + BORE_VIEW_AF_GAP + BORE_VIEW_AF_HALF_WIDTH,
                y - crop - BORE_VIEW_AF_DROP,
            ),
            "BoreFlatClock": clock,
        }
    width_right = x + crop + BORE_CLOCK_TEXT_GAP + 2.0 * KEYWAY_WIDTH_TEXT_HALF_WIDTH
    half_width = dt_cone_gear_spec.KEYWAY_HALF_WIDTH_MM * ratio / 1000.0
    return {
        "KeyedBoreDia": diameter,
        # Under the lower witness and the arrow that ends on it.
        "KeywayWidth": (
            width_right - KEYWAY_WIDTH_TEXT_HALF_WIDTH,
            y - half_width - BORE_CLOCK_ARROW_LENGTH - ARROW_TEXT_CLEARANCE
            - KEYWAY_WIDTH_TEXT_HALF_HEIGHT,
        ),
        "KeywayT": (
            max(x + flat, width_right) + BORE_VIEW_AF_GAP + BORE_VIEW_AF_HALF_WIDTH,
            y - crop - BORE_VIEW_AF_DROP,
        ),
        "KeywayClock": clock,
    }


# Rule 9: an enlarged view carries a letter, and its boundary, with the same
# letter, sits on its parent (screen of f21dfcdd2ba7: "BORE PROFILE" and the
# sheet-21 plot were named in prose only). DETAIL A is the bore view, its
# boundary ringing the bore on the front view; DETAIL B is sheet 21's plot
# of the T006 tooth space, its boundary ringing the 12 o'clock space on the
# T006 front view, upright as the plot draws it.
BORE_DETAIL_LETTER = "A"
FORM_DETAIL_LETTER = "B"
FORM_DETAIL_TEETH = 6


def bore_view_label(teeth: int) -> str:
    numerator, denominator = bore_view_scale(teeth)
    return f"DETAIL {BORE_DETAIL_LETTER}\nSCALE {numerator:g} : {denominator:g}"


def bore_view_label_top(teeth: int) -> float:
    drop = KEYED_BORE_VIEW_LABEL_DROP if keyed(teeth) else BORE_VIEW_LABEL_DROP
    return BORE_VIEW_CENTER[1] - bore_view_crop_radius(teeth) - drop


def form_plot_label() -> str:
    """Sheet 21's title: DETAIL B of the T006 sheet, at the plot's scale."""
    return (
        f"DETAIL {FORM_DETAIL_LETTER} (SHEET {SHEET_NAMES.index('T006') + 1})\n"
        f"SCALE {FORM_PLOT_SCALE:g} : 1"
    )


@dataclass(frozen=True)
class FrontDetail:
    """A detail boundary on a sheet's front view and where its letter stands.

    ``centre_mm`` and ``radius_mm`` are model millimetres in the front view's
    plane (gear axis at the origin, tooth zero on +X); the letter's centre
    stands ``letter_reach`` (sheet metres) outside the boundary at
    ``letter_angle_deg`` round the boundary's centre.
    """

    letter: str
    centre_mm: tuple[float, float]
    radius_mm: float
    letter_angle_deg: float
    letter_reach: float


# A's boundary stands this far outside the bore on paper, inside the web. A
# keyed bore's ring clears the keyway's corners by less: at .8 mm T030's
# letter (3:1) would not fit the web between that ring and the root envelope.
BORE_DETAIL_MARGIN = 0.0008
KEYED_BORE_DETAIL_MARGIN = 0.0006
# The letters print at the notes' height: at the default 3.5 mm, A's would
# not fit the T006 web between its boundary and the root envelope.
DETAIL_LETTER_HEIGHT = 0.0025
# Letter centre beyond its boundary: half the letter's ~2.6 mm diagonal
# extent plus ~1 mm of air.
DETAIL_LETTER_REACH = 0.0025
# A's letter stands down and right of the bore, the one diagonal no front-
# view line takes: the centre mark runs square, the root envelope's
# near-side leader comes in from the upper right, T012's web runs down left
# (WEB_REFERENCE_ANGLE_DEG) and the thickness witnesses run right from the
# 3 o'clock tooth. Where the web is narrower than the letter's reach (T006),
# the letter centres in the web.
BORE_LETTER_ANGLE_DEG = -45.0
# B rings the 12 o'clock space (a gap: T006 has teeth every 60 deg from
# +X): its centre this far up the space's centreline, model mm, and its
# radius the farther tip corner of the space plus FORM_DETAIL_MARGIN_MM, so
# the boundary takes the whole space and stands clear of A's ring. Its
# letter stands up and right, under the root envelope's text.
FORM_DETAIL_CENTRE_MM = 1.80
FORM_DETAIL_MARGIN_MM = 0.10
FORM_LETTER_ANGLE_DEG = 45.0


def _front_ratio(teeth: int) -> float:
    numerator, denominator = _SCALE_BY_TEETH[teeth]
    return numerator / denominator


def front_details(teeth: int) -> tuple[FrontDetail, ...]:
    """The detail boundaries the sheet's front view carries."""
    ratio = _front_ratio(teeth)
    margin = KEYED_BORE_DETAIL_MARGIN if keyed(teeth) else BORE_DETAIL_MARGIN
    bore_radius_mm = bore_reach_mm(teeth) + margin * 1000.0 / ratio
    web_mm = floor_limits_mm(teeth)[0] / 2.0 - bore_radius_mm
    details = [
        FrontDetail(
            BORE_DETAIL_LETTER,
            (0.0, 0.0),
            bore_radius_mm,
            BORE_LETTER_ANGLE_DEG,
            min(DETAIL_LETTER_REACH, web_mm * ratio / 2000.0),
        )
    ]
    if teeth == FORM_DETAIL_TEETH:
        if not math.isclose((90.0 * teeth / 360.0) % 1.0, 0.5):
            raise AssertionError("DETAIL B's 12 o'clock station is not a tooth space")
        root = stock_form_profile(teeth).template.root_radius_mm
        _radius, corner_x, corner_y = custom_six_form_points_mm()[-1]
        reach = math.hypot(corner_x, corner_y + root - FORM_DETAIL_CENTRE_MM)
        details.append(
            FrontDetail(
                FORM_DETAIL_LETTER,
                (0.0, FORM_DETAIL_CENTRE_MM),
                reach + FORM_DETAIL_MARGIN_MM,
                FORM_LETTER_ANGLE_DEG,
                DETAIL_LETTER_REACH,
            )
        )
    return tuple(details)


def detail_letter_xy(
    detail: FrontDetail, centre: tuple[float, float], radius: float
) -> tuple[float, float]:
    """Sheet centre of ``detail``'s letter round a boundary drawn at sheet
    ``centre`` with sheet ``radius``."""
    angle = math.radians(detail.letter_angle_deg)
    reach = radius + detail.letter_reach
    return centre[0] + reach * math.cos(angle), centre[1] + reach * math.sin(angle)


def front_detail_on_sheet(
    teeth: int, detail: FrontDetail
) -> tuple[tuple[float, float], float]:
    """Nominal sheet centre and radius of ``detail``'s boundary, the gear axis
    on FRONT_CENTER (the build projects the model points instead)."""
    ratio = _front_ratio(teeth)
    return (
        (
            FRONT_CENTER[0] + detail.centre_mm[0] * ratio / 1000.0,
            FRONT_CENTER[1] + detail.centre_mm[1] * ratio / 1000.0,
        ),
        detail.radius_mm * ratio / 1000.0,
    )


# Sheet width of the face-width text block: the stack's "20-GEAR STACK" row
# is wider than the banded value, 36.0 mm on every sheet of the ENFORCE
# round-3 render. Where the face spans less than the text plus a clearance
# each side, the text crowds its extension lines (#834 machinist review,
# sheets 5-20; ENFORCE round 3, sheets 3-20, with the 29 mm the value alone
# had measured): the text then stands outside, right of the view, on the
# extended dimension line.
FACE_WIDTH_TEXT_WIDTH = 0.036
FACE_WIDTH_TEXT_CLEARANCE = 0.002


def face_width_text_inside(teeth: int) -> bool:
    return (
        2.0 * rendered_half_face_width(teeth)
        >= FACE_WIDTH_TEXT_WIDTH + 2.0 * FACE_WIDTH_TEXT_CLEARANCE
    )


# The face width's block is centred on its point, 12 mm under the side view
# with the value alone (T084, ENFORCE round-1 render: block y 88-99 mm, view
# bottom 104.5 mm). The stack's two lines under the value would raise its top
# ~5 mm, onto the view, so the point drops by as much.
FACE_WIDTH_DROP = 0.017
# The tip diameter goes across the side view, beside the face width (rule 11;
# repeat review of 218c85b6: a leader on the end view). Its extension lines
# leave the front face at the tip radius; the text stands right of the view
# at mid-height, between the arrows, the dimension line through it. The
# block -- SEE NOTE 2 over the value and its band, 31 mm wide on the round-2
# T120 ink -- clears the face by the gap and the iso view by 20 mm or more.
BLANK_DIA_TEXT_HALF_WIDTH = 0.016
BLANK_DIA_TEXT_GAP = 0.004


def right_keep(teeth: int) -> dict[str, tuple[float, float]]:
    blank_dia = (
        RIGHT_CENTER[0]
        + rendered_half_face_width(teeth)
        + BLANK_DIA_TEXT_GAP
        + BLANK_DIA_TEXT_HALF_WIDTH,
        RIGHT_CENTER[1],
    )
    y = RIGHT_CENTER[1] - rendered_half_od(teeth) - FACE_WIDTH_DROP
    if face_width_text_inside(teeth):
        return {"FaceWidth": (RIGHT_CENTER[0], y), "BlankDia": blank_dia}
    x = (
        RIGHT_CENTER[0]
        + rendered_half_face_width(teeth)
        + FACE_WIDTH_TEXT_CLEARANCE
        + FACE_WIDTH_TEXT_WIDTH / 2.0
    )
    return {"FaceWidth": (x, y), "BlankDia": blank_dia}


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


def _hide_tangent_edges(view: Any, configuration: str) -> None:
    """Drop the end view's tangent edges, and prove they went.

    ENFORCE round 4 of #971: a grey circle at the root radius crossed every
    tooth base, an edge between smooth faces that reads as a hub step or a
    reference circle (draw_dt_crank_drive_gear does the same).
    """
    view.SetDisplayTangentEdges2(0)  # swTangentEdgesHidden
    if int(view.GetDisplayTangentEdges2()) != 0:
        raise RuntimeError(f"failed to hide the {configuration} front view's tangent edges")
    view.UpdateViewDisplayGeometry()


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


def _hide_title_block_source(adapter: Any, view: Any) -> None:
    """Hide the tooth-space sheet's T006 view; its title block still reads it.

    ``IView.SetVisible`` returns nothing, so ``GetVisible`` proves the hide
    (draw_mg_magnifier_assembly's BOM reference view).
    """
    bound = _early_bound(view, "IView")
    bound.SetVisible(False, False)
    rebuild_drawing(adapter, label="hide T006 tooth-space title-block source")
    if bool(bound.GetVisible()):
        raise RuntimeError("the tooth-space sheet's T006 view still reads visible")


def _sketch_view_circle(
    adapter: Any,
    view: Any,
    center: tuple[float, float],
    radius: float,
    *,
    add_to_db: bool,
    label: str,
) -> Any:
    """Sketch a circle in the ACTIVE ``view``'s own sketch from sheet points,
    through the view sketch's ModelToSketchTransform (draw_ch_amplitude_bar's
    ``_sketch_circle``). Without ``add_to_db`` the circle is left selected,
    which is what Crop2 consumes."""
    sketch = _early_bound(_early_bound(view, "IView").GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (center, (center[0] + radius, center[1])):
        point = _early_bound(utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint")
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(adapter.currentModel.SketchManager, "ISketchManager")
    previous_add_to_db = bool(manager.AddToDB)
    manager.AddToDB = add_to_db
    try:
        circle = manager.CreateCircle(*points[0], *points[1])
    finally:
        manager.AddToDB = previous_add_to_db
    if circle is None:
        raise RuntimeError(f"failed to sketch the {label} circle")
    return circle


def _crop_bore_view(
    adapter: Any, view: Any, configuration: str, teeth: int, kept: set[str]
) -> None:
    """Crop to a native circle round the bore, read back its outline and
    dimensions; it prints no crop outline (BORE_VIEW_CROP_MARGIN)."""
    draw = adapter.currentModel
    view = _early_bound(view, "IView")
    label = f"{configuration} bore view"
    uncropped = tuple(float(value) for value in view.GetOutline())
    name = _activate_view(adapter, view, label=label)
    _sketch_view_circle(
        adapter,
        view,
        BORE_VIEW_CENTER,
        bore_view_crop_radius(teeth),
        add_to_db=False,
        label=f"{label} crop",
    )
    status = int(view.Crop2(False, True, 1))
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
    # The jagged-outline accessor is invalid without an outline
    # (_drawing_detail_crop), so only the no-outline flag is read back.
    if not bool(view.CropViewNoOutline):
        raise RuntimeError(f"{label}'s crop prints an outline; expected none")
    lost = sorted(kept - after)
    if lost:
        raise RuntimeError(f"{label} lost {lost} to its crop; it holds {sorted(after)}")


def clock_arc_faults(
    arcs: list[tuple[tuple[float, float], list[tuple[float, float]]]],
    vertex: tuple[float, float],
) -> list[str]:
    """Why a flat clock's drawn arcs do not read as one 90 deg arc between
    its legs: centred on the flat/axis crossing, inside the quadrant right of
    the flat and above the axis, reaching both legs and sweeping most of the
    way between them. Empty when they do."""
    if not arcs:
        return ["no arc"]
    faults = []
    angles = []
    for centre, points in arcs:
        if math.dist(centre, vertex) > CLOCK_ARC_CENTRE_TOL:
            faults.append(f"arc centred {math.dist(centre, vertex) * 1000:.2f} mm off the vertex")
        ends = [
            math.degrees(math.atan2(py - vertex[1], px - vertex[0]))
            for px, py in (points[0], points[-1])
        ]
        angles.append((min(ends), max(ends)))
    stray = [
        point
        for _centre, points in arcs
        for point in points
        if point[0] < vertex[0] - CLOCK_ARC_OVERRUN or point[1] < vertex[1] - CLOCK_ARC_OVERRUN
    ]
    if stray:
        faults.append(f"{len(stray)} point(s) outside the quadrant")
    low = min(a for a, _b in angles)
    high = max(b for _a, b in angles)
    if abs(low) > CLOCK_LEG_TOL_DEG or abs(high - 90.0) > CLOCK_LEG_TOL_DEG:
        faults.append(f"arcs end at {low:.1f}..{high:.1f} deg, not on the legs")
    swept = sum(b - a for a, b in angles)
    if swept < CLOCK_MIN_SWEEP_DEG:
        faults.append(f"arcs sweep {swept:.1f} deg")
    return faults


def _assert_settled_clocks(adapter: Any, clocks: list[tuple[str, Any, int]]) -> None:
    """After finalize's settling rebuild, every sheet's flat clock still draws
    one arc between its legs (run 20261010T073917031Z: read whole at the
    sweep, drawn as two outside stubs in the PDF on T018-T120)."""
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    faults = []
    for configuration, display, teeth in clocks:
        if not ddoc.ActivateSheet(configuration):
            raise RuntimeError(f"failed to activate {configuration} for its settled clock")
        found = clock_arc_faults(_clock_arcs(display), bore_clock_vertex(teeth))
        if found:
            faults.append(f"{configuration}: {'; '.join(found)}")
    if faults:
        raise RuntimeError("flat clock arcs after the settling rebuild:\n" + "\n".join(faults))


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
) -> Any:
    """Flip the imported flat clock until its arc sweeps only the quadrant
    right of the flat and above the axis, then re-seat its text there.

    The flips act on the selected dimension (the API's own example selects
    it first), so each one runs with the clock alone selected in its active
    view. Every flip is read back from the drawn arcs and the measured value;
    a clock that ends anywhere else raises with the stray points.
    """
    clock_name = clock_dimension_name(teeth)
    clocks = [
        _early_bound(annotation, "IAnnotation")
        for annotation in annotations
        if dimension_name(adapter, _early_bound(annotation, "IAnnotation")) == clock_name
    ]
    if len(clocks) != 1:
        raise RuntimeError(f"{label}: expected one {clock_name}, found {len(clocks)}")
    annotation = clocks[0]
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    display.ArrowSide = ARROWS_INSIDE
    if int(display.ArrowSide) != ARROWS_INSIDE:
        raise RuntimeError(f"{label}: the flat clock did not keep its arrows inside")
    selection_name = str(display.GetNameForSelection() or "")
    if not selection_name:
        raise RuntimeError(f"{label}: the flat clock has no selection name")
    model = adapter.currentModel
    drawing = _early_bound(model, "IDrawingDoc")
    vertex = bore_clock_vertex(teeth)
    text_xy = bore_view_keep(teeth)[clock_name]
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
            if int(display.ArrowSide) != ARROWS_INSIDE:
                raise RuntimeError(f"{label}: {flips} put the clock's arrows outside")
            return display
    raise RuntimeError(
        f"{label}: flat clock arc still leaves the quadrant right of the flat and "
        f"above the axis after {flips}; first stray points "
        f"{[tuple(round(v * 1000, 1) for v in p) for p in stray[:3]]} mm"
    )


def _shelve_tooth_thickness(
    adapter: Any, annotations: list[Any], teeth: int, *, label: str
) -> None:
    """Offset the thickness text onto its own shelf (``tooth_thickness_shelf``)
    and prove the shelf landed there while the line stayed at the tooth.

    The line keeps the pre-offset anchor's x (the oblique jig's handoff in
    solidworks-drawing-layout-tuning.md); the text is seeded from the last
    print's block, then moved by what its own native shelf reads.
    """
    matches = [
        _early_bound(annotation, "IAnnotation")
        for annotation in annotations
        if dimension_name(adapter, annotation) == "ToothThickness"
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"{label}: expected one ToothThickness, found {len(matches)}"
        )
    annotation = matches[0]
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    line_x = front_keep(teeth)["ToothThickness"][0]
    target = tooth_thickness_shelf(teeth)
    seed = (target[0] + TOOTH_THICKNESS_SEED[0], target[1] + TOOTH_THICKNESS_SEED[1])
    offset_dimension_text(adapter, [annotation], {"ToothThickness": seed})
    ink = callout_ink(adapter, annotation, label=label)
    dx, dy = target[0] - ink.text[0], target[1] - ink.text[1]
    if max(abs(dx), abs(dy)) > TOOTH_THICKNESS_PLACE_TOL:
        move_annotation(adapter, annotation, dx, dy, label=label)
        ink = callout_ink(adapter, annotation, label=label)
    error = (ink.text[0] - target[0], ink.text[1] - target[1])
    stations = sorted(
        round(start[0], 6)
        for start, end in dimension_segments(annotation)
        if abs(start[0] - end[0]) < 1e-7
    )
    _telemetry.info(
        f"{label}: thickness shelf starts ({ink.text[0] * 1000:.2f}, "
        f"{ink.text[1] * 1000:.2f}) mm for ({target[0] * 1000:.2f}, "
        f"{target[1] * 1000:.2f}); vertical lines at "
        f"{[round(x * 1000, 2) for x in stations]} mm, line anchor {line_x * 1000:.2f}",
        offset_text=bool(display.OffsetText),
    )
    if not bool(display.OffsetText):
        raise RuntimeError(f"{label}: the thickness text did not stay offset")
    if max(map(abs, error)) > TOOTH_THICKNESS_PLACE_TOL:
        raise RuntimeError(
            f"{label}: thickness shelf starts {error[0] * 1000:.2f}, "
            f"{error[1] * 1000:.2f} mm off its place"
        )
    strayed = [x for x in stations if abs(x - line_x) > TOOTH_THICKNESS_PLACE_TOL]
    if not stations or strayed:
        raise RuntimeError(
            f"{label}: the thickness line left the tooth: vertical lines at "
            f"{[round(x * 1000, 2) for x in stations]} mm, anchor {line_x * 1000:.2f}"
        )


# The thickness callout's printed rows other than the value, top down.
TOOTH_THICKNESS_ROWS = (
    CALLOUTS_ABOVE["ToothThickness"],
    *DIMENSION_CALLOUTS["ToothThickness"].splitlines(),
)


# How far round the callout's text block a line is still measured; anything
# farther is reported at this distance.
_TEXT_AIR_WINDOW = 0.010


def tooth_thickness_text_air(page: PageInk, teeth: int) -> tuple[float, str]:
    """The smallest printed air between the thickness callout's glyphs and
    any line on ``page`` other than the shelf the text stands on, with the
    nearest line.

    The callout is its printed rows (one PDF text run each) and every run
    inside their joint box (the value and its tolerance). Its name over the
    value prints once a page; its "SEE NOTE 2" flag also prints on the tip
    diameter and on the root envelope (whose block stands just above this
    one), so the flag is the nearest such run under the name. Its shelf is
    the horizontal line under that box spanning it. Air is the glyph-box to
    line distance less half the stroke width.
    """
    def printed(row: str) -> list[Any]:
        key = "".join(row.split())
        return [span for span in page.spans if "".join(span.text.split()) == key]

    name_row, *lower_rows = TOOTH_THICKNESS_ROWS
    names = printed(name_row)
    if len(names) != 1:
        alike = [span.text for span in page.spans if span.text[:6] == name_row[:6]]
        raise ValueError(
            f"T{teeth:03d}: thickness row {name_row!r} printed {len(names)} times "
            f"(runs starting alike: {alike})"
        )
    name = names[0]
    name_x = (name.xmin + name.xmax) / 2.0
    runs = [name]
    for row in lower_rows:
        found = [span for span in printed(row) if span.ymax <= name.ymin]
        if not found:
            raise ValueError(
                f"T{teeth:03d}: thickness row {row!r} printed 0 times under {name_row!r}"
            )
        runs.append(min(
            found,
            key=lambda span: math.hypot((span.xmin + span.xmax) / 2.0 - name_x, name.ymin - span.ymax),
        ))
    block = Box(
        min(span.xmin for span in runs),
        min(span.ymin for span in runs),
        max(span.xmax for span in runs),
        max(span.ymax for span in runs),
    )
    hair = 0.0001
    glyphs = [
        Box(glyph.xmin, glyph.ymin, glyph.xmax, glyph.ymax)
        for span in page.spans
        if block.xmin - hair <= span.xmin
        and span.xmax <= block.xmax + hair
        and block.ymin - hair <= span.ymin
        and span.ymax <= block.ymax + hair
        for glyph in span.glyphs
    ]
    near = Box(
        block.xmin - _TEXT_AIR_WINDOW,
        block.ymin - _TEXT_AIR_WINDOW,
        block.xmax + _TEXT_AIR_WINDOW,
        block.ymax + _TEXT_AIR_WINDOW,
    )
    shelves = 0
    air, nearest = _TEXT_AIR_WINDOW, "no line within reach"
    for stroke in page.strokes:
        if not (stroke.stroked or stroke.filled):
            continue
        segment = Segment(stroke.x0, stroke.y0, stroke.x1, stroke.y1)
        if segment.length == 0.0 or segment_box_distance(segment, near) > 0.0:
            continue
        if (
            abs(stroke.y0 - stroke.y1) < 1e-7
            and block.ymin - 0.0025 <= stroke.y0 <= block.ymin
            and min(stroke.x0, stroke.x1) <= block.xmin + 0.0005
            and max(stroke.x0, stroke.x1) >= block.xmax - 0.0005
        ):
            shelves += 1
            continue
        pen = stroke.width / 2.0 if stroke.stroked else 0.0
        for glyph in glyphs:
            gap = segment_box_distance(segment, glyph) - pen
            if gap < air:
                air = gap
                nearest = (
                    f"{gap * 1000:.2f} mm from line {segment.format_mm()} to glyph "
                    f"{glyph.format_mm()}"
                )
    if not shelves:
        raise ValueError(
            f"T{teeth:03d}: no shelf under the thickness text {block.format_mm()}"
        )
    return air, nearest


def assert_tooth_thickness_text_air(pdf: Path) -> None:
    """Refuse the export when any line comes nearer the thickness callout's
    text than ``TOOTH_THICKNESS_TEXT_AIR`` on any gear sheet (the printed
    ink, as the machinist reads it)."""
    pages = read_pdf_ink(Path(pdf))
    if len(pages) != len(SHEET_NAMES):
        raise RuntimeError(
            f"{pdf} prints {len(pages)} pages, expected {len(SHEET_NAMES)}"
        )
    airs = {}
    faults = []
    for name, teeth, page in zip(GEAR_SHEET_NAMES, CONFIGURATION_TEETH, pages):
        air, nearest = tooth_thickness_text_air(page, teeth)
        airs[name] = round(air * 1000, 2)
        if air < TOOTH_THICKNESS_TEXT_AIR:
            faults.append(f"{name}: {nearest}")
    _telemetry.info(f"thickness text air by sheet (mm): {airs}")
    if faults:
        raise RuntimeError(
            f"a line strikes the thickness text (under "
            f"{TOOTH_THICKNESS_TEXT_AIR * 1000:.1f} mm of air):\n" + "\n".join(faults)
        )


def _check_exported_pdf(phase: str) -> None:
    if phase == "after_pdf_save":
        assert_tooth_thickness_text_air(PDF)


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


def _set_note_height(note: Any, height: float, *, label: str) -> None:
    """Set a note's character height (add_property_linked_note's form)."""
    annotation = _early_bound(_early_bound(note, "INote").GetAnnotation(), "IAnnotation")
    text_format = annotation.GetTextFormat(0)
    if text_format is None:
        raise RuntimeError(f"{label}: note has no text format")
    text_format.CharHeight = float(height)
    if annotation.SetTextFormat(0, False, text_format) is not True:
        raise RuntimeError(f"{label}: failed to set the note's text height")


def _centred_view_note(
    adapter: Any,
    view: Any,
    text: str,
    *,
    center_x: float,
    top: float | None = None,
    center_y: float | None = None,
    height: float | None = None,
    label: str,
) -> None:
    """Insert a note ``view`` owns, centred on ``center_x`` by its extent;
    ``top`` pins its top edge, ``center_y`` its middle (draw_ch_amplitude_bar's
    ``_centred_view_note``). A note that does not centre, or lands in another
    view, raises."""
    if (top is None) == (center_y is None):
        raise ValueError(f"{label}: give the note a top edge or a centre height")
    _activate_view(adapter, view, label=label)
    raw = add_note(adapter, text, center_x, top if top is not None else center_y)
    if raw is None:
        raise RuntimeError(f"failed to add the {label} note")
    note = _early_bound(raw, "INote")
    if height is not None:
        _set_note_height(note, height, label=label)
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")

    def error_of(box: tuple[float, float, float, float]) -> tuple[float, float]:
        if top is not None:
            return (box[0] + box[2]) / 2.0 - center_x, box[3] - top
        return (box[0] + box[2]) / 2.0 - center_x, (box[1] + box[3]) / 2.0 - center_y

    for _ in range(2):
        error = error_of(_note_box(note, label=label))
        if max(abs(error[0]), abs(error[1])) <= NOTE_CENTRING_TOL_M / 10.0:
            break
        position = tuple(float(value) for value in annotation.GetPosition())
        if not annotation.SetPosition2(position[0] - error[0], position[1] - error[1], 0.0):
            raise RuntimeError(f"failed to centre the {label} note")
        rebuild_drawing(adapter, label=f"{label} note")
    error = error_of(_note_box(note, label=label))
    if max(abs(error[0]), abs(error[1])) > NOTE_CENTRING_TOL_M:
        raise RuntimeError(
            f"{label} note did not centre: off by ({error[0] * 1000:.2f}, "
            f"{error[1] * 1000:.2f}) mm"
        )
    first_words = text.split("\n")[0].split()
    owned = [
        str(_early_bound(found, "INote").GetText() or "").split()
        for found in (_early_bound(view, "IView").GetNotes() or ())
    ]
    if sum(words[: len(first_words)] == first_words for words in owned) != 1:
        raise RuntimeError(f"{label} note did not land in its view: {owned!r}")


def _label_bore_view(adapter: Any, view: Any, teeth: int, *, label: str) -> None:
    """Title the bore view DETAIL A under its crop circle: a note the view
    owns, centred on the bore axis by its extent, its top edge on
    ``bore_view_label_top``."""
    _centred_view_note(
        adapter,
        view,
        bore_view_label(teeth),
        center_x=BORE_VIEW_CENTER[0],
        top=bore_view_label_top(teeth),
        label=f"{label} title",
    )


def _mark_front_details(adapter: Any, front: Any, teeth: int, *, label: str) -> None:
    """Draw each of the sheet's detail boundaries on the front view (a plain
    view-sketch circle in the outline's black, draw_ch_amplitude_bar's
    detail mark) and letter it outside, both owned by the view."""
    for detail in front_details(teeth):
        detail_label = f"{label} detail {detail.letter}"
        _activate_view(adapter, front, label=detail_label)
        x_mm, y_mm = detail.centre_mm
        centre, rim = (
            model_point_in_view(
                adapter, front, (x / 1000.0, y_mm / 1000.0, 0.0), label=f"{detail_label} {name}"
            )
            for x, name in ((x_mm, "centre"), (x_mm + detail.radius_mm, "rim"))
        )
        radius = math.dist(centre, rim)
        circle = _sketch_view_circle(
            adapter, front, centre, radius, add_to_db=True, label=f"{detail_label} boundary"
        )
        segment = _early_bound(circle, "ISketchSegment")
        segment.Color = 0  # COLORREF black, not the under-defined sketch blue.
        if int(segment.Color) != 0:
            raise RuntimeError(f"{detail_label} boundary colour did not persist")
        adapter.currentModel.ClearSelection2(True)
        rebuild_drawing(adapter, label=f"{detail_label} boundary")
        letter_x, letter_y = detail_letter_xy(detail, centre, radius)
        _centred_view_note(
            adapter,
            front,
            detail.letter,
            center_x=letter_x,
            center_y=letter_y,
            height=DETAIL_LETTER_HEIGHT,
            label=f"{detail_label} letter",
        )
        _telemetry.info(
            f"{detail_label}: boundary at ({centre[0] * 1000:.2f}, {centre[1] * 1000:.2f}) mm, "
            f"radius {radius * 1000:.2f} mm; letter at ({letter_x * 1000:.2f}, "
            f"{letter_y * 1000:.2f}) mm"
        )


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
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit("dt-cone-gear"),
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

    clocks: list[tuple[str, Any, int]] = []
    for teeth in CONFIGURATION_TEETH:
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
        _hide_tangent_edges(front, configuration)
        _assert_tooth_geometry(front, configuration, teeth)
        _center_bore_view(adapter, bore_view, configuration)

        # The bore view imports FIRST, while it is uncropped: a model
        # dimension already on the sheet is not imported again, and no other
        # view keeps the bore sketch's dimensions.  The sketch (BoreProfile,
        # or KeyedBoreProfile on T030..T120) is consumed by its cut, so it
        # imports without being shown (_drawing_hidden_sketches r21).
        bore_keep = bore_view_keep(teeth)
        bore_annotations = hidden_sketches.curate_view_dimensions(
            adapter,
            bore_view,
            keep=bore_keep,
            view_label=f"{configuration} bore",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        )
        clock = _sweep_clock_right_of_flat(
            adapter, bore_view, bore_annotations, teeth, label=f"{configuration} bore view"
        )
        clocks.append((configuration, clock, teeth))
        _crop_bore_view(adapter, bore_view, configuration, teeth, set(bore_keep))
        # The part saves its authoring sketches hidden; the front view shows
        # the tooth and floor ones again for their dimensions, the side view
        # the tip-diameter witness (the iso view shows the part as saved).
        # The targeted import still delivers the dimensions on every sheet
        # after the first (probe 834-gapfloor-c301).
        front_annotations = hidden_sketches.curate_view_dimensions(
            adapter,
            front,
            keep=front_keep(teeth),
            view_label=f"{configuration} front",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        )
        # ENFORCE round 4 of #971: the root envelope's dimension line crossed
        # the centre and the bore; its leader stops on its near rim. Through
        # the centre it also crossed T012's web dimension line (screen of
        # f21dfcdd2ba7, rule 14) and ran through DETAIL A's boundary.
        found = [
            item for item in front_annotations
            if dimension_name(adapter, item) == "FloorDia"
        ]
        if len(found) != 1:
            raise RuntimeError(
                f"{configuration}: expected one FloorDia dimension, found {len(found)}"
            )
        set_near_side_diameter(found[0], f"{configuration} FloorDia")
        rebuild_drawing(adapter, label=f"{configuration} near-side diameter leader")
        # The face width first: the whole-model import deletes whatever it
        # does not keep, the witness's BlankDia included, which the targeted
        # import then brings in with its sketch shown in this view.
        side_keep = right_keep(teeth)
        right_annotations = _curate_repeated_dimensions(
            adapter,
            right,
            keep={"FaceWidth": side_keep["FaceWidth"]},
            view_label=f"{configuration} right",
        )
        right_annotations += hidden_sketches.curate_view_dimensions(
            adapter,
            right,
            keep={"BlankDia": side_keep["BlankDia"]},
            view_label=f"{configuration} side",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        )
        _assert_sheet_bands(
            adapter, [*front_annotations, *right_annotations], configuration, teeth
        )
        annotations = [*bore_annotations, *front_annotations, *right_annotations]
        # The sheet's own bore, and RV-03's web on T012 only (front_keep).
        printed = sheet_dimension_names(teeth)
        callouts = {
            name: text for name, text in DIMENSION_CALLOUTS.items() if name in printed
        }
        set_dimension_callouts(adapter, annotations, callouts)
        set_dimension_callouts(adapter, annotations, {
            name: text for name, text in CALLOUTS_ABOVE.items() if name in printed
        }, location="above")
        assert_imported_precision(adapter, annotations, {
            name: places for name, places in DRAWING_PRECISION_BY_NAME.items()
            if name in printed
        })
        _center_mark_bore(adapter, front, teeth, label=f"{configuration} front")
        _center_mark_bore(adapter, bore_view, teeth, label=f"{configuration} bore view")
        sheet = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
        if not sheet.SetScale(*view_scale, False, False):
            raise RuntimeError(f"failed to pin the {configuration} sheet scale")
        _shelve_tooth_thickness(
            adapter, front_annotations, teeth, label=f"{configuration} thickness text"
        )
        _mark_front_details(adapter, front, teeth, label=configuration)
        # Last, as before: the sheet's notes below land while the bore view
        # is active.
        _label_bore_view(adapter, bore_view, teeth, label=f"{configuration} bore view")

        add_property_linked_note(
            adapter, "Gear Data", *GEAR_DATA_POS, char_height=0.0025
        )
        numbered = add_note(adapter, sheet_notes(teeth), *NUMBERED_NOTES_POS)
        if numbered is None:
            raise RuntimeError(f"failed to add the {configuration} numbered notes")
        _set_note_height(numbered, 0.0025, label=f"{configuration} numbered notes")
        rebuild_drawing(adapter, label=f"{configuration} layout audit")
        check_drawing_layout(
            adapter, layout=SPEC.layout, stem=f"cone-gear {configuration}"
        )

    if not ddoc.ActivateSheet(CUTTER_DETAIL_SHEET):
        raise RuntimeError("failed to activate the T006 tooth-space sheet")
    # The title block reads the T006 part, number and alloy through this
    # view, so it stays on the sheet, hidden (_hide_title_block_source).
    source_view = place_view(
        adapter, str(SOURCE), "*Front", *CUTTER_SOURCE_VIEW_CENTER,
        scale=SHEET_SCALES[CUTTER_DETAIL_SHEET],
    )
    _configure_views(adapter, "T006", (source_view,))
    _hide_title_block_source(adapter, source_view)
    # The plot first: it puts the sheet in edit mode (EditSheet), so the
    # table and notes below belong to the sheet, not the hidden source view.
    _draw_form_plot(adapter)
    # The form table, not the model's "Cutter Profile" equations (see
    # form_table_rows), between its title and its two notes.
    table = _insert_form_table(adapter)
    table_height = sum(
        float(table.GetRowHeight(row)) for row in range(int(table.RowCount))
    )
    notes_xy = form_notes_pos(table_height)
    if notes_xy[1] - len(form_sheet_notes().splitlines()) * 0.00351 < 0.100:
        raise RuntimeError(f"T006 point table runs {table_height * 1000:.1f} mm tall")
    for text, position, label in (
        (form_sheet_title(), FORM_TITLE_POS, "T006 tooth-space title"),
        (form_sheet_notes(), notes_xy, "T006 tooth-space notes"),
    ):
        note = add_note(adapter, text, *position)
        if note is None:
            raise RuntimeError(f"failed to add the {label}")
        _set_note_height(note, FORM_TEXT_HEIGHT, label=label)
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
        settled_checks=(lambda: _assert_settled_clocks(adapter, clocks),),
        checkpoint=_check_exported_pdf,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
