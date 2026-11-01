r"""Create the complete cone-gear batch drawing package (MHA-DT-03).

Every configured family member T006..T120 by six receives a standalone sheet.
Each sheet selects its own part configuration, imports the native model-owned
blank diameter, D-bore (diameter, across-flat and flat clock), face width,
driving circular-tooth-thickness requirement and functional root-envelope
limits, plus the actual finite cutter recipe and bounded carrying-contact data.
The native imported bands remain model-owned. A last sheet defines the T006
tooth space point by point beside its outline (the custom DT6-FORM1 tool is
ground to it); the exact equations stay in the model's "Cutter Profile"
property.

There are no datums, feature-control frames or finish symbols: the bore is a
fixed D-fit that does not run (drawing-guidelines.md rule 6).  Hidden lines
communicate no additional manufacturing fact on these through-bored spur
gears, so every view remains hidden-lines-removed.  The side view stays in
projection with the front view's bore axis; its
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
from pathlib import Path
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    curate_dimensions,
    dimension_name,
    place_view,
    view_name,
)

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
from dt_cone_gear_notes import CUTTER_DETAIL_SHEET
from dt_cone_gear_spec import (
    CUSTOM_SIX_FORM_TOLERANCE_NOTE,
    CONFIGURATION_TEETH,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FACE_WIDTH,
    FORM_PLACES,
    WEB_REFERENCE_ANGLE_DEG,
    WEB_REFERENCE_TEETH,
    bore_dia_mm,
    blank_dia_band,
    inch_text,
    tooth_thickness_band,
    bore_flat_offset_mm,
    floor_limits_mm,
    gap_floor_deviations_mm,
    outside_dia_mm,
    tooth_thickness_mm,
    custom_six_form_points_mm,
    custom_six_gap_half_angle_rad,
    stock_form_profile,
    web_reference_mm,
)

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
# row; the mate's line under BORE ACROSS FLAT adds one, so the point drops
# half a row less than the 5 mm it stood at and the bottom stays put.
BORE_VIEW_AF_DROP = 0.0025
BORE_VIEW_LABEL_DROP = 0.016
# The diameter's text stands this far above the crop circle (6 mm with the
# value alone): the block is centred there, and the mate's two lines under
# THRU would lower the leader shoulder under it ~5.3 mm, onto the bore.
BORE_VIEW_DIA_LIFT = 0.0115
# The across-flat text stands OUTSIDE its witnesses, right of the flat's, as
# MHA-DT-07's does. Centred between them, its lines (~2.65 mm a character in
# the #1128 full-5 render) ran wider than the 29-35 mm witness span on every
# sheet, so both witness lines crossed the callout, and its tolerance stack
# sat on the diameter leader's lower end (machinist review of full-5).
# BORE_VIEW_AF_HALF_WIDTH is half the widest line, the mate's 20-character
# SLIDES ON MHA-DT-04, rounded up; the text's left edge clears the flat's
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
# bore view's crop circle. The mate's line over the value makes the block
# three lines, ~18 mm tall; at 20 characters, one more than CENTERLINE's
# line, it overhangs the measured width ~1.3 mm a side, inside that gap. A
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
# Top-aligned with the manufacturing notes: the 14-line block (header + 13
# rows) measured 49.1 mm tall natively (e91d2581 layout audit), 3.51 mm a
# line; the 15-line block ends ~52.6 mm down, still above the largest side
# view (top 0.197) with FaceWidth below it.
# The tooth-space sheet keeps the T006 form table out of these dimension/view
# lanes.
GEAR_DATA_POS = (0.215, 0.263)
# Rendered height budget of the Gear Data block, for the layout test.
GEAR_DATA_HEIGHT = 0.056
MANUFACTURING_NOTES_POS = (0.015, 0.263)
CUTTER_DETAIL_POS = (0.015, 0.263)
# Where the tooth-space sheet's hidden title-block source view stands (see
# build): clear of the table, inside the border.
CUTTER_SOURCE_VIEW_CENTER = (0.325, 0.155)
# The tooth-space plot beside the table (ENFORCE round 4 of #971: a table
# alone left the sheet bunched in one corner, rule 15). The table governs; the
# plot draws the same rows at FORM_PLOT_SCALE with Y0 on the CL at
# FORM_PLOT_ORIGIN. At 75:1 the space spans x 0.207-0.353 and y 0.139-0.202,
# right of the table (x <= ~0.125) and above the title block (y 0.064).
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
FORM_PLOT_ORIGIN_NOTE_OFFSET = (0.004, -0.008)
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
        (
            f"T006 TOOTH SPACE PLOTTED {FORM_PLOT_SCALE:.0f}:1 FROM THE TABLE "
            "(TABLE GOVERNS)",
            FORM_PLOT_TITLE_POS,
        ),
        ("CL", (FORM_PLOT_ORIGIN[0] - 0.003, top + FORM_PLOT_CL_OVERRUN + 0.006)),
        (
            "+X",
            (FORM_PLOT_ORIGIN[0] + FORM_PLOT_X_AXIS_LENGTH + 0.002,
             FORM_PLOT_ORIGIN[1] + 0.002),
        ),
        (
            f"X0 Y0 ON CL AT ROOT R{inch_text(template.root_radius_mm, 4)}\n"
            f"GEAR AXIS {inch_text(template.root_radius_mm, 4)} BELOW Y0 ON CL",
            (FORM_PLOT_ORIGIN[0] + FORM_PLOT_ORIGIN_NOTE_OFFSET[0],
             FORM_PLOT_ORIGIN[1] + FORM_PLOT_ORIGIN_NOTE_OFFSET[1]),
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
    _telemetry.info(
        f"T006 tooth-space plot: {len(created)} sheet sketch entities at "
        f"{FORM_PLOT_SCALE:.0f}:1, Y0 at "
        f"{tuple(round(value * 1000, 1) for value in FORM_PLOT_ORIGIN)} mm"
    )




def cutter_grind_data() -> str:
    """The T006 tooth space, point by point, and how the cut gear is accepted.

    The sheet once printed the part's "Cutter Profile" property: parametric
    equations with 17-digit floats, which no shop grinds to (eye pass of
    run 20261010T051729717Z). Then it printed reference chords, which left
    the relief undefined (machinist review of the stack build). It gives the
    form point by point at four inch places, read from the same profile the native
    cut uses (dt_cone_gear_spec.custom_six_form_points_mm), says how the
    points connect (the round-2 review: points alone let templates differ
    between them), and gives a one-sided form tolerance.

    It is T006 geometry, not a tool drawing: as "DT6-FORM1 GROUND FORM
    TOOL" it carried the gear's title block (part, number, brass) and no tool
    material, and told the shop how to inspect the tool (ENFORCE round 1 of
    #971; #1427). T006 cuts at T=0 on a spur (helix 0) gear, so its tooth
    space IS the custom cutter's edge: the shop grinds its own tool to this
    space, in whatever tool steel it uses, and accepts the cut gear over pins
    on the T006 sheet. The form tolerance names what it sets (rule 4,
    ENFORCE round 3).
    """
    profile = stock_form_profile(6)
    template = profile.template
    if template.cutter_number is not None or template.name != CUTTER_DETAIL_SHEET:
        raise ValueError("T006 must use the specified DT6-FORM1 custom cutter")
    if profile.radial_translation_mm != 0.0 or profile.helix_angle_deg != 0.0:
        raise ValueError("the T006 tooth space is DT6-FORM1's form only at T=0, helix 0")
    root = template.root_radius_mm
    junction = template.relief_junction_radius_mm
    return "\n".join((
        "T006 TOOTH SPACE FORM, INCH",
        "SYMMETRIC ABOUT THE SPACE CENTERLINE (CL):",
        "X ACROSS CL, Y ALONG CL FROM THE ROOT,",
        "AT RADIUS R FROM THE GEAR AXIS",
        *(
            f"R{inch_text(radius, FORM_PLACES)}   X{inch_text(x, FORM_PLACES)}"
            f"   Y{inch_text(y, FORM_PLACES)}"
            for radius, x, y in custom_six_form_points_mm()
        ),
        f"ROOT: ARC R{inch_text(root, FORM_PLACES)} ABOUT GEAR AXIS",
        f"ROOT ARC TO R{inch_text(junction, FORM_PLACES)}: STRAIGHT LINES ROW TO ROW",
        f"ABOVE R{inch_text(junction, FORM_PLACES)}: INVOLUTE, "
        f"BASE R{inch_text(template.base_radius_mm, FORM_PLACES)}",
        CUSTOM_SIX_FORM_TOLERANCE_NOTE,
        f"WIDE ONLY: SETS BACKLASH WITH {CYLINDER_MATE}",
        # The space depth is the root and blank rows' difference, and Gear
        # Data prints it as the plunge; no third copy here.
        f"ACCEPT OVER PINS PER SHEET {SHEET_NAMES.index('T006') + 1} (T006 GEAR DATA)",
    ))


# Each tight band names its mate and fit at its callout (drawing-guidelines
# rule 4; ENFORCE round 1 of #971 found them only in Gear Data, or nowhere).
SHAFT_MATE = "MHA-DT-04"
CYLINDER_MATE = "MHA-DT-12"
DIMENSION_CALLOUTS = {
    # No process word: a reamer would cut away the flat, and the dimensions
    # define the D-profile (user ruling 2026-09-29, machinist review of the
    # #1128 full build). The mate hangs under the value in rows as narrow as
    # the value: on T006/T012 the flat's witness for the clock rises ~3 mm
    # right of it, and a wider block's shoulder crosses that witness.
    "BoreCutDia": f"THRU\nSLIDES ON\n{SHAFT_MATE}",
    # The value is the gear bore's own; naming the bore, not the shaft it
    # slides on, keeps it from reading as MHA-DT-04's across-flat.
    "BoreAF": f"BORE ACROSS FLAT\nSLIDES ON {SHAFT_MATE}",
    # The flat's normal runs through the bore axis and the +X tooth's centre;
    # the bore view crops the teeth off, so the callout names the reference
    # its centre-mark line stands for.
    "BoreFlatClock": "TO TOOTH CENTERLINE",
    # The circle the arc is measured on: its witnesses are straight lines, so
    # without the circle it read as unmeasurable (machinist review of the
    # round-2 build). The mesh it sets goes over the value (CALLOUTS_ABOVE).
    # The text is the same on every sheet: offset (OffsetText), the imported
    # model dimension printed the LAST sheet's below-text on all of them (T006
    # printed T120's "ON PITCH CIRCLE Ø63.500", farm runs of 746809f62 and
    # 5000ea76b), so no per-configuration size can ride on it. GEAR DATA
    # gives the teeth and diametral pitch that size the circle.
    "ToothThickness": "CIRCULAR TOOTH THICKNESS\nON PITCH CIRCLE",
    # The origin circle is an inspection witness, not the off-centre root arc.
    "FloorDia": f"ROOT ENVELOPE\nCLEARS {CYLINDER_MATE}",
    # The cone set is a solid stack on the shaft; each gear's width sets the
    # stations (user ruling 2026-09-28, spec FACE_WIDTH).
    "FaceWidth": f"20-GEAR STACK\nON {SHAFT_MATE}",
    # RV-03's accepted T012 web (cad/config/parts/dt-cone-gear.yaml): what the
    # single limit bounds, at the value.
    "WebMin": "WEB, BORE TO ROOT",
}


# Text over the value: the mates. One line each: SOLIDWORKS drops a
# multi-line callout above a value from the print (ENFORCE round 2 of #971:
# every two-line one went unmatched in the PDF; draw_ch_amplitude_bar r1).
CALLOUTS_ABOVE = {
    "ToothThickness": f"BACKLASH WITH {CYLINDER_MATE}",
    "BlankDia": f"MESHES WITH {CYLINDER_MATE}",
    "BoreFlatClock": f"PHASED TO {SHAFT_MATE}",
}
if any("\n" in text for text in CALLOUTS_ABOVE.values()):
    raise AssertionError("an above-callout with a line break does not print")


def rendered_half_od(teeth: int) -> float:
    numerator, denominator = _SCALE_BY_TEETH[teeth]
    return outside_dia_mm(teeth) * numerator / (denominator * 2000.0)


def rendered_half_face_width(teeth: int) -> float:
    numerator, denominator = _SCALE_BY_TEETH[teeth]
    return FACE_WIDTH * numerator / (denominator * 2000.0)


# BlankDia's value stands this far above the tip circle.  At 0.012 the T006
# value (8:1) sat on the vertical centre-mark line, which reaches 26.3 mm
# above the bore axis on that sheet (layout audit, 0.82 mm overlap); 0.0145
# cleared it with the value alone. The block is centred on its point, so the
# mate's line over the value lowers the shoulder ~2.5 mm: 0.0175 restores it.
BLANK_DIA_LIFT = 0.0175
# ...and this far left of the bore axis, so its leader drops from the
# block's right end nearly straight onto the tip circle. Centred over the
# axis (ENFORCE round 3, T006) the leader ran diagonally from x 134 mm down
# through the root envelope's block, whose left edge stands at 121 mm.
BLANK_DIA_SHIFT_X = 0.020
# The functional root-envelope stack stands right of the tip circle,
# above the thickness witness and the thickness text's shelf
# (``tooth_thickness_shelf``), and clear of the side
# view (left edge >= 0.219 on every sheet). The mate's row is ~4 chars wider
# than the label (centred block), so the gap grows ~5.5 mm over the label-only
# 0.016 to hold the block's left edge where it cleared the teeth.
FLOOR_DIA_GAP_X = 0.0215
# The shelf's rise above 0.6 of the tip radius: 6 mm with the three-row stack;
# the mate's row under the label (centred block) would lower it ~2.8 mm.
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


# RV-03's T012 web text stands this far off its dimension line, square to it
# on the side away from the teeth's +X dimensions: clear of the tip circle.
WEB_MIN_TEXT_OFFSET = 0.026


def web_min_text_xy() -> tuple[float, float]:
    """Sheet point of the T012 web text: off the middle of its radial line."""
    numerator, denominator = _SCALE_BY_TEETH[WEB_REFERENCE_TEETH]
    start, web, _band = web_reference_mm()
    middle = (start + web / 2.0) * numerator / (denominator * 1000.0)
    angle = math.radians(WEB_REFERENCE_ANGLE_DEG)
    across = angle - math.pi / 2.0
    return (
        FRONT_CENTER[0] + middle * math.cos(angle) + WEB_MIN_TEXT_OFFSET * math.cos(across),
        FRONT_CENTER[1] + middle * math.sin(angle) + WEB_MIN_TEXT_OFFSET * math.sin(across),
    )


def front_keep(teeth: int) -> dict[str, tuple[float, float]]:
    half_od = rendered_half_od(teeth)
    keep = {
        "FloorDia": (FRONT_CENTER[0] + half_od + FLOOR_DIA_GAP_X, floor_dia_y(teeth)),
        "BlankDia": (
            FRONT_CENTER[0] - BLANK_DIA_SHIFT_X,
            FRONT_CENTER[1] + half_od + BLANK_DIA_LIFT,
        ),
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
    (``_sweep_clock_right_of_flat``), its text right of the circle and
    raised clear of the axis line and the arc's arrowhead on it
    (BORE_CLOCK_TEXT_*).
    """
    ratio = _bore_view_ratio(teeth)
    flat = bore_flat_offset_mm(teeth) * ratio / 1000.0
    crop = bore_view_crop_radius(teeth)
    x, y = BORE_VIEW_CENTER
    return {
        # 3 mm right of x - 0.022: the inch seat band (+0.04572/+0.0254)
        # ran the text 1.6 mm past the left inner border (#290 batch 0).
        "BoreCutDia": (x - 0.019, y + crop + BORE_VIEW_DIA_LIFT),
        "BoreAF": (
            x + flat + BORE_VIEW_AF_GAP + BORE_VIEW_AF_HALF_WIDTH,
            y - crop - BORE_VIEW_AF_DROP,
        ),
        "BoreFlatClock": (
            x + crop + BORE_CLOCK_TEXT_GAP + BORE_CLOCK_TEXT_HALF_WIDTH,
            y + BORE_CLOCK_ARROW_LENGTH + ARROW_TEXT_CLEARANCE + BORE_CLOCK_TEXT_HALF_HEIGHT,
        ),
    }


def bore_view_label(teeth: int) -> str:
    numerator, denominator = bore_view_scale(teeth)
    return f"BORE PROFILE\nSCALE {numerator:g} : {denominator:g}"


def bore_view_label_top(teeth: int) -> float:
    return BORE_VIEW_CENTER[1] - bore_view_crop_radius(teeth) - BORE_VIEW_LABEL_DROP


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


def right_keep(teeth: int) -> dict[str, tuple[float, float]]:
    y = RIGHT_CENTER[1] - rendered_half_od(teeth) - FACE_WIDTH_DROP
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
    sketch = _early_bound(view.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    radius = bore_view_crop_radius(teeth)
    center = BORE_VIEW_CENTER
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
        found = clock_arc_faults(_clock_arcs(display), bore_flat_vertex(teeth))
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
    display.ArrowSide = ARROWS_INSIDE
    if int(display.ArrowSide) != ARROWS_INSIDE:
        raise RuntimeError(f"{label}: the flat clock did not keep its arrows inside")
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
    inside their joint box (the value and its tolerance). Its shelf is the
    horizontal line under that box spanning it. Air is the glyph-box to
    line distance less half the stroke width.
    """
    runs = []
    for row in TOOTH_THICKNESS_ROWS:
        key = "".join(row.split())
        found = [span for span in page.spans if "".join(span.text.split()) == key]
        if len(found) != 1:
            alike = [span.text for span in page.spans if span.text[:6] == key[:6]]
            raise ValueError(
                f"T{teeth:03d}: thickness row {row!r} printed {len(found)} times "
                f"(runs starting alike: {alike})"
            )
        runs.append(found[0])
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
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
            "Manufacturing Notes",
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
        clock = _sweep_clock_right_of_flat(
            adapter, bore_view, bore_annotations, teeth, label=f"{configuration} bore view"
        )
        clocks.append((configuration, clock, teeth))
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
        # ENFORCE round 4 of #971: the OD's and the root envelope's
        # dimension lines crossed at the centre and over the bore; the OD
        # leader now stops on its near rim.
        blank_dia = [
            item for item in front_annotations
            if dimension_name(adapter, item) == "BlankDia"
        ]
        if len(blank_dia) != 1:
            raise RuntimeError(
                f"{configuration}: expected one BlankDia dimension, found {len(blank_dia)}"
            )
        set_near_side_diameter(blank_dia[0], f"{configuration} blank diameter")
        rebuild_drawing(adapter, label=f"{configuration} blank diameter near-side leader")
        right_annotations = _curate_repeated_dimensions(
            adapter,
            right,
            keep=right_keep(teeth),
            view_label=f"{configuration} right",
        )
        annotations = [*bore_annotations, *front_annotations, *right_annotations]
        # RV-03's web dimension shows on the T012 sheet only (front_keep).
        callouts = {
            name: text for name, text in DIMENSION_CALLOUTS.items()
            if name != "WebMin" or teeth == WEB_REFERENCE_TEETH
        }
        set_dimension_callouts(adapter, annotations, callouts)
        set_dimension_callouts(adapter, annotations, CALLOUTS_ABOVE, location="above")
        assert_imported_precision(adapter, annotations, {
            name: places for name, places in DRAWING_PRECISION_BY_NAME.items()
            if name != "WebMin" or teeth == WEB_REFERENCE_TEETH
        })
        _center_mark_bore(adapter, front, teeth, label=f"{configuration} front")
        _center_mark_bore(adapter, bore_view, teeth, label=f"{configuration} bore view")
        sheet = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
        if not sheet.SetScale(*view_scale, False, False):
            raise RuntimeError(f"failed to pin the {configuration} sheet scale")
        _shelve_tooth_thickness(
            adapter, front_annotations, teeth, label=f"{configuration} thickness text"
        )
        _label_bore_view(adapter, bore_view, teeth, label=f"{configuration} bore view")

        add_property_linked_note(
            adapter, "Gear Data", *GEAR_DATA_POS, char_height=0.0025
        )
        add_property_linked_note(
            adapter, "Manufacturing Notes", *MANUFACTURING_NOTES_POS,
            char_height=0.0025,
        )
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
    # The form table, not the model's "Cutter Profile" equations (see
    # cutter_grind_data).
    if add_note(adapter, cutter_grind_data(), *CUTTER_DETAIL_POS) is None:
        raise RuntimeError("failed to add the T006 tooth-space table")
    _draw_form_plot(adapter)
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
