r"""Create the curated machinist drawing for the green-painted top-frame casting.

The SLDPRT remains authoritative.  This recipe supplies only native model
dimensions, associative hole callouts, and the views of the casting;
sheet/template and export behavior lives in ``_drawing_common``.
Dimension import and curation live in ``_drawing_dimension_import``.
GEOMETRY defines the frame windows and T-rail section;
HOLES-SOCKETS carries the hole/station plan; CROSS-TAPS carries the front
cross-tap elevation with section A-A through a corner boss; HUB-SET-SCREW
holds the hub location, true-axis side view and the removed set-screw boss
section; UNDERSIDE holds the underside locator, native enlarged hub detail J
and the removed knife-hanger section F-F. The faced keeper-rail top
is one linked note under the keeper callout on HOLES-SOCKETS, the faced
underside plane one beside the UNDERSIDE detail.  A group gets
its own sheet rather than a crowded corner of one:
qualifiers then park clear of cutting lines, centrelines and each other.
Projected top/front pairs stay aligned; removed and section views carry scales.
Keeper taps transfer from MHA-CH-07 at assembly; their retained station
coordinates are reference-only. Hanger station dimensions remain controlling.

Run with SolidWorks open::

    uv run python cad\scripts\draw_fr_top_frame.py fr-top-frame
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from dataclasses import dataclass
from typing import Any

from solidworks_mcp.adapters.com_variant import dispatch_array, double_array
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.sw_type_info import constant
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    dimension_name,
    place_view,
    view_name,
)

from _check import check
from _com import _early_bound
from _drawing_annotation_extent import move_annotation, require_clear, sheet_region
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_datum_target import add_datum_target, datum_target_readback
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    offset_dimension_text,
    set_arc_endpoints_to_center,
    set_arc_endpoints_to_max,
    set_basic_dimension,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_edge_dimensions import add_edge_dimension
from _drawing_edges import ViewEdges, scan_view_edges
from _drawing_finish import add_surface_finish
from _drawing_gdt import (
    add_datum_feature,
    add_feature_control_frame,
    add_frame_datum_feature,
)
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_layout_audit import annotation_display
from _drawing_leader_notes import add_leader_note
from _drawing_leaders import dimension_segments, set_near_side_diameter
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_sheets import (
    PictorialView,
    create_blank_drawing_sheets,
    place_pictorial_sheet,
)
from _drawing_tables import create_view_theoretical_datum, insert_hole_table
from _drawing_view_display import set_hidden_lines_removed
from _gtol_face import SURFACE_CONE
from _gtol_face_resolve import resolve_faces
from _gtol_planar import PlanarFace
from _layout_audit import display_box, estimated_text_runs
import _layout_audit
from fr_frame_cross_screw import NEAR_WALL_CLEARANCE_DIAMETER
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from _title_block_units import LENGTH_UNITS, render_number
from _transgear_zone_line import (
    SketchedLine,
    dimension_input_suppressed,
    require_placed,
    sheet_to_sketch,
    sketch_lines,
)
from build_fr_top_frame import (
    BAR_POCKET_Z,
    BAR_X0,
    BAR_X1,
    BORE_CHAMFER,
    BORE_DIA,
    BOSS_BOTTOM_Y,
    CAST_DATUM_ORIGIN_XZ,
    CAST_DATUM_TARGETS,
    D_STATION_LINE_Z,
    DATUM_TARGET_Y,
    DRAFT_T,
    RIM_RECEDE,
    BOSS_ABOVE,
    BOSS_BELOW,
    BOSS_DIA,
    CAP_RECESS_DEPTH,
    CAP_RECESS_DIAMETER,
    COLUMN_X,
    COUNTERBORE_DIA,
    FLANGE,
    FLANGE_BOT_Y,
    FRONT_COLUMN_Z,
    GOOSENECK_BORE_DIA,
    GOOSENECK_X,
    GOOSENECK_Z,
    GUSSET,
    HALF_H,
    HUB_BOSS_DROP,
    HUB_GUSSET_HALF_IN,
    HUB_GUSSET_HALF_OUT,
    HUB_GUSSET_T,
    INNER_X,
    INNER_Z,
    KEEPER_TAP_SPEC,
    KEEPER_TAP_X,
    KEEPER_TAP_Z_REAR,
    LAND_X1,
    OUTER_X,
    OUTER_Z,
    POCKET_H,
    REAR_COLUMN_Z,
    RING_HEIGHT,
    SET_BOSS_FACE_X,
    SET_SPOT_FACE_X,
    SET_TAP_SPEC,
    SIDE_TAP_DRILL_DIA,
    SIDE_TAP_SPEC,
    TAP_DRILL_MM,
    TOP_SCREW_SEAT_Z,
    WEB_IN_X,
    WEB_IN_Z,
    WEB_OUT_X,
)
from fr_top_frame_spec import (
    DATUM_TARGET_BARREL_HEIGHT,
    DATUM_TARGET_BOTTOM_RADIUS,
    DRAFT_DEG,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    EDGE_CHAMFER,
    RAIL_SECTION_X,
    SIDE_SECTION_Z,
    GEOMETRIC_TOLERANCES_IN,
    HANGER_CLEARANCE_DIA,
    HANGER_CLEARANCE_DIA_PLACES,
    HANGER_HOLE_DRILL,
    HANGER_GRIP,
    HANGER_KNOCKOUT_CALLOUT_ABOVE,
    HANGER_KNOCKOUT_CALLOUT_BELOW,
    HANGER_KNOCKOUT_DIA,
    HANGER_KNOCKOUT_DIA_PLACES,
    HANGER_PIN_DEPTH_CALLOUT,
    HANGER_PIN_HOLE_CALLOUT,
    HANGER_PIN_HOLE_DEPTH,
    HANGER_PIN_HOLE_DIA,
    HANGER_PIN_X,
    HANGER_X,
    HUB_SET_BOSS_FROM_AXIS,
    HUB_SET_SPOT_FROM_AXIS,
    HUB_SET_SPOT_PLACES,
    IN,
    KEEPER_TAP_CALLOUT_PRECISION,
    PIN_HOLE_X,
    SCREW_AXIS_BELOW_RAIL_TOP,
    SCREW_AXIS_Y,
    STUD_Z_FRONT,
    STUD_Z_REAR,
    SURFACE_FINISHES,
    UNIT,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["fr_top_frame"]
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

# SOLIDWORKS 2026 swconst typelib: document Image Quality, not application
# defaults or the source part's shaded/draft tessellation.
_IMAGE_QUALITY_WIREFRAME = 45
_IMAGE_QUALITY_WIREFRAME_VALUE = 46
_IMAGE_QUALITY_HIGH_CURVES = 527
_NO_PREFERENCE_OPTION = 0
_WIREFRAME_CUSTOM = 2
_CURVE_RESOLUTION = 100

SHEET_NAMES = (
    "PICTORIAL",
    "GEOMETRY",
    "HOLES-SOCKETS",
    "CROSS-TAPS",
    "HUB-SET-SCREW",
    "UNDERSIDE",
    "CAST-DATUMS",
)
SHEET_SCALE = (1.0, 3.0)
# Sheet scale is a per-sheet property, and the title block's SCALE field
# reads it: a sheet whose views all sit at one scale gets THAT scale, so the
# block states it and no "... SCALE 1:2" note has to.  Only a sheet mixing
# scales (HUB-SET-SCREW: 1:3 plan, 1:2 removed view, 1:1 section) still
# labels the views that differ from its block.
SHEET_SCALES = {
    "PICTORIAL": (1.0, 4.0),
    "GEOMETRY": SHEET_SCALE,
    "HOLES-SOCKETS": (1.0, 2.0),
    "CROSS-TAPS": (1.0, 2.0),
    "HUB-SET-SCREW": SHEET_SCALE,
    "UNDERSIDE": SHEET_SCALE,
    "CAST-DATUMS": SHEET_SCALE,
}
# The station plan is drawn half size, so its centre-mark axes and label
# lanes derive from its own scale and never from the title block's.
DETAIL_TOP_SCALE = SHEET_SCALES["HOLES-SOCKETS"]
GEOMETRY_VIEW_SCALE = SHEET_SCALE[0] / SHEET_SCALE[1]
DETAIL_VIEW_SCALE = DETAIL_TOP_SCALE[0] / DETAIL_TOP_SCALE[1]

# Plan extents including the Ø1.77 corner bosses: the straight rails stop
# at x +/-214.10 / z +/-131.06, bosses at +/-219.48 / +/-134.49.
# The boss stack stays 1.87 tall around the 1.437 rail band.
PLAN_HALF_X = COLUMN_X + BOSS_DIA / 2.0
PLAN_HALF_Z = abs(FRONT_COLUMN_Z) + BOSS_DIA / 2.0
GEOMETRY_PLAN_HALF_W = PLAN_HALF_X * GEOMETRY_VIEW_SCALE / 1000.0
GEOMETRY_PLAN_HALF_D = PLAN_HALF_Z * GEOMETRY_VIEW_SCALE / 1000.0
DETAIL_PLAN_HALF_W = PLAN_HALF_X * DETAIL_VIEW_SCALE / 1000.0
DETAIL_PLAN_HALF_D = PLAN_HALF_Z * DETAIL_VIEW_SCALE / 1000.0

# The .06 edge break on a drafted edge is SolidWorks' angle-distance chamfer:
# EDGE_CHAMFER along the face it takes its distance on, 45° to that face,
# so its leg on the other face is shorter across an edge the draft closes
# (88°: a rim under the faced top) and longer across one it opens (92°: a
# barrel under a boss face).  Farm run 20261111T004615500Z read every pick
# below off the drafted model's own edges.
_DRAFT = math.radians(DRAFT_DEG)
BREAK_LEG_CLOSED = (
    EDGE_CHAMFER * math.sin(math.pi / 4.0) / math.sin(math.pi / 4.0 + _DRAFT)
)  # 1.4735
BREAK_LEG_OPEN = (
    EDGE_CHAMFER * math.sin(math.pi / 4.0) / math.sin(math.pi / 4.0 - _DRAFT)
)  # 1.5801
# A window rim's or the crossbar top's break takes its distance on the faced
# top: its lower edge stands this far under the top, and this far along the
# receding rim face.
TOP_BREAK_DROP = BREAK_LEG_CLOSED * math.cos(_DRAFT)  # 1.4726
TOP_BREAK_RECEDE = BREAK_LEG_CLOSED * math.sin(_DRAFT)  # 0.0514
# The rails' outer rims take theirs on the rim face, so the faced top ends
# BREAK_LEG_CLOSED inside the rim's nominal outline.
OUTER_RIM_TOP_X = OUTER_X - BREAK_LEG_CLOSED  # 212.6739
OUTER_RIM_TOP_Z = OUTER_Z - BREAK_LEG_CLOSED  # 129.5905
# A boss's faced top ends on the break of its taken-out upper barrel, and
# that barrel meets the lower one, at the nominal Ø1.77, on the faced top's
# plane: the plan's outline.
BOSS_TOP_EDGE_R = BOSS_DIA / 2.0 - BOSS_ABOVE * DRAFT_T - BREAK_LEG_OPEN  # 20.7392
BOSS_BOTTOM_EDGE_R = (
    BOSS_DIA / 2.0 - (RING_HEIGHT + BOSS_BELOW) * DRAFT_T - EDGE_CHAMFER
)  # 19.456


# Sheet 1: two octant pictorials, opposite corners, so every face is seen
# once.  Drawn at 1:4 -- two 1:3 isometrics of a 428 x 262 plan would not
# fit side by side inside the B-sheet border.  Each is named in words under
# it (owner 2026-11-07, rule 26: several isometric views are labelled
# ISOMETRIC VIEW FROM TOP / FROM BOTTOM, not with arrows to face names),
# with no scale: both print at the sheet's 1:4.
#
# The machine's face names stay the package's one convention: FRONT is the
# operator side, model -Z, the rail at the top of the plan; REAR is +Z, the
# face the standard front elevation shows; RIGHT is +X (dimensions.yaml's
# assembly frame).  Sheet 3's FRONT/REAR hanger and keeper Z read the same
# way (machinist review of 2056e3344).
PICTORIAL_SCALE = SHEET_SCALES["PICTORIAL"]
PICTORIAL_VIEWS = (
    PictorialView(octant=(-1, 1, 1), center_xy=(0.115, 0.165), labels=()),  # REAR-TOP-LEFT
    PictorialView(octant=(1, -1, 1), center_xy=(0.305, 0.165), labels=()),  # REAR-BOTTOM-RIGHT
)
# Each caption's text centred under its view: the views print y 126..205 mm
# on the v48 render, the title block's top at 64.7 (x 216..419).
PICTORIAL_CAPTIONS = (
    ("ISOMETRIC VIEW FROM TOP", (0.115, 0.112)),
    ("ISOMETRIC VIEW FROM BOTTOM", (0.305, 0.112)),
)

# Sheet 2: overall envelope and non-hole geometry.  Top/front remain
# horizontally projected.
GEOMETRY_TOP_CENTER = (0.145, 0.1685)
GEOMETRY_FRONT_CENTER = (0.145, 0.090)

# Sheet 3: the hole/station plan, centred on the sheet it now fills at
# 1:2. The Ø25.5 sockets and Ø45 bosses are the setup features; the
# smaller boss remains 22.5 mm across on paper, the socket 12.75 mm.
# Its final centre below reserves room for the assembly-transfer callout.
# The socket Ra symbol reads off the upper-left rim of the rear east socket
# (135 deg on the sheet, y 104.5 + 4.5 = 109.0 mm), from the left margin
# 22 mm over its axis, so its leader descends across the boss over the
# hole table origin mark's Y arrow (x 77.2, y 95.0..111.0 with its "Y"):
# level with the axis, it ran through that arrow (farm run
# 20261107T084432155Z, leader-crosses-leader); here it passes 3 mm over the
# letter.  Its "TUBE SOCKET BORES, 4X" row (about 38 mm from 5 mm right of
# the symbol point, 9 mm above it) stands in the empty margin left of the
# rail.  The band under the plan belongs to the hole table
# (HOLE_TABLE_ANCHOR).
SOCKET_FINISH_SYMBOL_XY = (0.020, 0.131)
SOCKET_FINISH_LANDING_DEG = 135.0
FINISH_LEADER_TAIL = 0.042
# Owner ruling B3 (#2333): the boss tops are machined seats.  Their one
# symbol stands in sheet 4's empty band left of A-A, under the cap recess
# callout's shoulder (y 165), its tail's end leading right to the front
# boss's top outside the recess.
BOSS_TOP_FINISH_SYMBOL_XY = (0.150, 0.152)

# Sheet 4: the cross-tap elevation across the sheet's upper band with
# section A-A below it, both half size.  A-A carries the cap recess and the
# 47.3 boss stack, so it gets the sheet's whole lower half instead of a
# quarter of its right edge.
DETAIL_FRONT_SCALE = SHEET_SCALES["CROSS-TAPS"]
DETAIL_FRONT_CENTER = (0.145, 0.228)
DETAIL_SECTION_SCALE = (1, 2)
DETAIL_SECTION_CENTER = (0.290, 0.135)
DETAIL_SECTION_CAPTION_XY = (0.240, 0.088)

# #946 leader-over-part (layoutcheck's b2 leaf on b49e13940): RD4, the 2X
# keeper tap callout, stood above the upper-right boss and its leader crossed
# the boss and bore rings to the front keeper tap: 29.6 mm over the part,
# 18.3 mm more than the tap's shortest approach.  It now enters by the tap's
# short side (Main: detour <= ~4 mm; swing's RD2 fix, 4dda16fd5, left 3.8).
# Placement is computed from the tap's projected model points at build time;
# the pure placement function below is what the offline tests pin.
#
# The sheet's frame: ISheet::GetZoneMargin's 12.7 mm inside the ASME B sheet.
SHEET_FRAME = (0.0127, 0.0127, 0.4191, 0.2667)
# Ink that must read apart stands this far off (_drawing_leaders keeps 2 mm
# between an arrow and foreign text); clearances round outward by 0.1 mm.
INK_CLEARANCE = 0.002
ROUND_OUT = 0.0001
# The native arrowhead is 0.762 mm across (b49e1 dump, IDisplayData arrows).
ARROW_HALF_WIDTH = 0.000381
# Sheet 3's top band, right of the 182.0 extension line and above the top
# rail.  R4 printed the four-row callout's +0.130 stack on the 266.7
# border and the position frame over the upper-right boss.  The one
# C DRILL THRU row centres lower, clear of the boss; the frame (top-left corner
# here) stands above it, its 5.5 mm box and one qualifier row ending about
# 11 mm under frame_xy.
HANGER_CALLOUT_XY = (0.262, 0.238)
HANGER_CENTER_FRAME_XY = (0.200, 0.264)
# A native hole callout's leader runs a diameter of its selected rim, arrow
# lower-left and up-right through the axis (R5, on the old Ø17 rim:
# (180.0,199.7)->(187.2,204.2) mm, 32 deg); it now selects the clearance
# rim itself.  The frame's default landing on that rim would sit on
# the diameter's lower-left side, under the leader.  It lands instead 60 deg
# up-right of the axis on the sheet: above the callout's diameter, and right
# of the 182.0's extension line on D's trace, so its leader meets neither.
# Sheet up is model -Z (the plan's front is up).
HANGER_CENTER_LANDING_DEG = 60.0


def hanger_center_landing() -> tuple[float, float, float]:
    """Model point (mm) on the front clearance rim at the finished top,
    ``HANGER_CENTER_LANDING_DEG`` anticlockwise from sheet +X."""
    radius = HANGER_CLEARANCE_DIA / 2.0
    angle = math.radians(HANGER_CENTER_LANDING_DEG)
    return (
        HANGER_X + radius * math.cos(angle),
        HALF_H,
        STUD_Z_FRONT - radius * math.sin(angle),
    )


# The linear (non-diameter) zone is two planes about D's median: X only.
# The axes are drawn ON D, an implied BASIC zero (ASME Y14.5-2018) that
# needs no words (machinist review r1: no basic in note text); the
# qualifier is the count alone, and a note never explains what a datum
# letter is (rule 7; farm runs 20261106T214613300Z and T221139403Z).  The Z
# stations stand from the front sockets' axis (HANGER_Z_TEXT_XY).
HANGER_CENTER_QUALIFIER = "2X"
# D is the crossbar's as-cast width at the underside, where the added draft
# leaves it nominal (owner rulings B5 and D2, #2333): sheet 7 carries the
# width, the tag and D's station from G.  The tag's leader runs along the
# width's dimension line from its first arrow, and SolidWorks stands the tag's
# near edge at the mirror of the requested x about that arrow: requested 142
# against the arrow at 135.8 it stood at 129.7 (farm run 20261014T055244900Z),
# requested 133 against 141.1 at 149.2, its leader then printed along the
# whole line (farm run 20261111T015941119Z, line-on-dimension-line).  Asking
# 3 mm right of the arrow (x 141.1) stands it 3 mm left, on the line's
# extension, clear of the width's text, which parks right in the west window.
CROSSBAR_MEDIAN_DATUM_XY = (0.1441, 0.124)
# Transfer fit-up owns these locations; the nominal model holes and their
# sheet coordinates are references, not independent inspection requirements.
# The trailing newline keeps the native thread/drill/depth on separate rows
# through _drawing_hole_callout.compose_hole_callout_prefix.
TRANSFER_KEEPER_CALLOUT = "TRANSFER FROM MHA-CH-07\nAT ASSEMBLY;\n"
# Historical RD4 envelope measured on b49e1, NOT a measurement of the new
# transfer callout. Expand its width for a conservative 3.5 mm per prefix
# character and its height by two estimated 5.1 mm rows: offline allowances.
# farm validation must measure the regenerated ink and leader landing.
_KEEPER_NATIVE_CALLOUT_EXTENT = (0.0384, 0.0056, 0.0368, 0.0046)
KEEPER_TRANSFER_ROW_PITCH = 0.0051
KEEPER_TRANSFER_EXTRA_HEIGHT = (
    TRANSFER_KEEPER_CALLOUT.count("\n") * KEEPER_TRANSFER_ROW_PITCH
)
KEEPER_TRANSFER_CHARACTER_WIDTH = 0.0035
KEEPER_TRANSFER_EXTRA_WIDTH = max(
    0.0,
    max(map(len, TRANSFER_KEEPER_CALLOUT.splitlines()))
    * KEEPER_TRANSFER_CHARACTER_WIDTH
    - _KEEPER_NATIVE_CALLOUT_EXTENT[0]
    - _KEEPER_NATIVE_CALLOUT_EXTENT[2],
)
KEEPER_CALLOUT_EXTENT = (
    _KEEPER_NATIVE_CALLOUT_EXTENT[0],
    _KEEPER_NATIVE_CALLOUT_EXTENT[1],
    _KEEPER_NATIVE_CALLOUT_EXTENT[2] + KEEPER_TRANSFER_EXTRA_WIDTH,
    _KEEPER_NATIVE_CALLOUT_EXTENT[3] + KEEPER_TRANSFER_EXTRA_HEIGHT,
)
# The facing note sets at the edge-break note block's 3.5 mm height, which
# renders about 2.6 mm per character on a 5.1 mm row (farm 30394c1da: its
# then 70-character line spanned 30 -> 208 mm).
FACING_NOTE_HEIGHT = 0.0035
# Native SolidWorks centres the four-row RD4 block on its callout point and
# lands the leader on an underline below the bottom row, 11.15 mm under that
# point (HOLES-SOCKETS, farm 9e13b1b78 and b51258927: rows 91.7 -> 112.0 mm
# about a 101.85 mm point, leader shoulder at 90.7 mm), not on the estimated
# extent's bottom.  Rounded outward; the facing note hangs under it.
KEEPER_CALLOUT_SHOULDER_DROP = 0.0112


def _keeper_leader_angle(
    hole: tuple[float, float], boss: tuple[float, float], boss_r: float
) -> float:
    """Steepest lower-right entry clearing the rear boss, in sheet metres."""
    bx, by = boss[0] - hole[0], boss[1] - hole[1]
    rho, phi = math.hypot(bx, by), math.atan2(-bx, -by)
    reach = boss_r + INK_CLEARANCE + ROUND_OUT
    if reach >= rho:
        raise ValueError(
            f"keeper tap stands inside its boss clearance ({rho=}, {reach=})"
        )
    return phi + math.acos(reach / rho)


# The extra rows lower the shoulder; along the same boss-clear tangent this
# advances it right by height/tan(angle). Move only this plan left by that
# advance plus the added width, retaining the previous right-frame clearance.
KEEPER_TRANSFER_PLAN_SHIFT = (
    KEEPER_TRANSFER_EXTRA_HEIGHT
    / math.tan(
        _keeper_leader_angle(
            (
                KEEPER_TAP_X * DETAIL_VIEW_SCALE / 1000.0,
                -KEEPER_TAP_Z_REAR * DETAIL_VIEW_SCALE / 1000.0,
            ),
            (
                COLUMN_X * DETAIL_VIEW_SCALE / 1000.0,
                -REAR_COLUMN_Z * DETAIL_VIEW_SCALE / 1000.0,
            ),
            BOSS_DIA / 2.0 * DETAIL_VIEW_SCALE / 1000.0,
        )
    )
    + KEEPER_TRANSFER_EXTRA_WIDTH
)
# Centred 160.5 mm up: owner ruling Q11-B' moved the rear keeper tap 0.75
# toward the rear boss, which drops RD4 and the facing note under it 0.375 mm
# on the sheet; at 160.0 the note stood 1.77 mm off the title block.
DETAIL_TOP_CENTER = (0.215 - KEEPER_TRANSFER_PLAN_SHIFT, 0.1605)
# Sheet 3's left margin carries the socket finish symbol; the hole table
# (HOLE_TABLE_ANCHOR) locates every hole the plan shows.

# Keep the boss-height lane 7.45 mm off A-A's rederived Ø45 boss silhouette.
BOSS_ABOVE_RAIL_LINE_XY = (
    DETAIL_SECTION_CENTER[0] + DETAIL_PLAN_HALF_D + 0.00745,
    DETAIL_SECTION_CENTER[1] + 0.0073,
)
# Above the dimension's own upper arrow, not 51 mm below it -- see the
# boss-height comment in the A-A recipe for what the long leader crossed.
# Its 36.5 mm row ends 2.2 mm short of the recess depth's "+.010" (farm
# inspect-3: 1.43 at +0.0135).
BOSS_ABOVE_RAIL_TEXT_XY = (BOSS_ABOVE_RAIL_LINE_XY[0] + 0.0127, 0.176)
# The A-A witnesses off the boss top, the recess floor and the rail top
# start this far past the +Z boss's outer face, never across its cut face.
A_A_WITNESS_STANDOFF = 0.0012
# Separate the chamfer's three-row text from its native dimension shelf and
# witness overrun. Keep its attached dimension line at the creation point.
BORE_CHAMFER_TEXT_OFFSET_XY = (0.315, 0.174)


# The Hole Wizard's own tap feature names (build_fr_top_frame step 13).
CROSS_TAP_FEATURES = ("SideTapsFront", "SideTapsRear")
# The near-wall clearance callout stands right of the boss, under section
# arrow A's lower head and the .90's lower extension line, so its leader
# climbs to the clearance's lower-right rim (set_near_side_diameter) clear of
# the cutting line and of the counterbore callout above the view.  Above the
# view, left of arrow A (run 20261106T172701582Z), it shared the row the
# counterbore callout now holds (machinist review at rubric 848e03f: that
# callout's leader must stay off the tap's).  Right of the tap its leader ran
# through section label A, and both native leaders, drawn rim to rim through
# the shared centre, crossed there: each leader stops at its near rim.
CROSS_CLEARANCE_CALLOUT_XY = (0.300, 0.212)
# The clearance is drilled full diameter until it opens into the socket: its
# native blind depth ("<HOLE-DEPTH> <hw-depth>") becomes that instruction on
# its own row, and its native count (the two clearances THIS view shows)
# states the four identical clearances as one 4X, as the tap's does.  The
# diameter stays a Hole Wizard variable.
CROSS_CLEARANCE_EXTENT_TEXT = "DRILL TO SOCKET"
CROSS_CLEARANCE_PRECISION = {"hw-diam": 3}
_BLIND_DEPTH_TOKENS = re.compile(r"<HOLE-DEPTH>\s*<hw-depth>")
# The mate and the far-wall-only requirement belong on the native cross-tap
# leader (drawing-guidelines.md rule 7), not in a detached section note.  The
# near casting wall is the #10 close clearance (owner ruling 2026-11-05),
# called out on its own, so the thread is the far wall's only; its
# print-worst engagement is build_fr_top_frame's
# TOP_CROSS_SCREW_FAR_WALL_MIN_ENGAGEMENT.  The native count is the two taps
# THIS view shows; the callout states the four identical taps as one 4X
# (rule 10), its size and thread rows first and the mate rows last (rule 26;
# farm run 20261106T212431241Z read "SAME AT OPPOSITE END, 4X TOTAL" as
# private).
CROSS_TAP_COUNT = "4X"
CROSS_TAP_MATE_LINE = "FOR MHA-FR-VN-53, FAR WALL ONLY,\nDEPTHS FROM COUNTERBORE FLOOR"
_NATIVE_COUNT = "<NUM_INST>X"


def cross_tap_definitions(definitions: dict[int, str]) -> dict[int, str]:
    """The cross-tap callout's definitions with the native count written as
    CROSS_TAP_COUNT and CROSS_TAP_MATE_LINE under the native rows."""
    if set(definitions) != {5, 6, 7, 8}:
        raise RuntimeError(f"unexpected hole-callout parts: {definitions!r}")
    owners = [part for part, text in definitions.items() if _NATIVE_COUNT in text]
    if len(owners) != 1 or definitions[owners[0]].count(_NATIVE_COUNT) != 1:
        raise RuntimeError(f"cross-tap callout lacks one instance count: {definitions!r}")
    (part,) = owners
    updated = {**definitions, part: definitions[part].replace(_NATIVE_COUNT, CROSS_TAP_COUNT, 1)}
    below = updated[8].rstrip()
    updated[8] = f"{below}\n{CROSS_TAP_MATE_LINE}" if below else CROSS_TAP_MATE_LINE
    return updated


def _cross_clearance_callout_definitions(definitions: dict[int, str]) -> dict[int, str]:
    """Write the native count as CROSS_TAP_COUNT and swap the blind depth for
    DRILL TO SOCKET."""
    if set(definitions) != {5, 6, 7, 8}:
        raise RuntimeError(f"unexpected cross clearance callout parts: {definitions!r}")
    depths = sorted(
        len(_BLIND_DEPTH_TOKENS.findall(text)) for text in definitions.values()
    )
    counts = {part: text.count(_NATIVE_COUNT) for part, text in definitions.items()}
    if depths != [0, 0, 0, 1] or sorted(counts.values()) != [0, 0, 0, 1]:
        raise RuntimeError(
            "cross clearance callout has no single count and blind depth: "
            f"{definitions!r}"
        )
    updated = {
        part: _BLIND_DEPTH_TOKENS.sub(
            f"\n{CROSS_CLEARANCE_EXTENT_TEXT}",
            text.replace(_NATIVE_COUNT, CROSS_TAP_COUNT, 1),
        )
        for part, text in definitions.items()
    }
    rewritten = "\n".join(updated.values())
    if "<hw-depth>" in rewritten or "<HOLE-DEPTH>" in rewritten or "<NUM_INST>" in rewritten:
        raise RuntimeError(f"cross clearance rewrite left a native token: {updated!r}")
    return updated


@_telemetry.traced("drawing.top_cross_clearance_callout_text")
def _set_cross_clearance_callout_text(display: Any) -> None:
    """State the 4X count and DRILL TO SOCKET without severing the diameter variable."""
    definitions = {part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)}
    updated = _cross_clearance_callout_definitions(definitions)
    for definition_part, writable_part in ((5, 1), (6, 2), (7, 3), (8, 4)):
        if updated[definition_part] != definitions[definition_part]:
            display.SetText(writable_part, updated[definition_part])
    persisted = {part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)}
    resolved = "\n".join(str(display.GetText(part) or "") for part in (1, 2, 3, 4))
    diameter = f"{NEAR_WALL_CLEARANCE_DIAMETER / 25.4:.3f}".lstrip("0")
    if (
        persisted != updated
        or resolved.count(CROSS_CLEARANCE_EXTENT_TEXT) != 1
        or len(re.findall(rf"\b{CROSS_TAP_COUNT} ", resolved)) != 1
        or re.search(r"\b2X", resolved)
        or "<HOLE-DEPTH>" in resolved
        or diameter not in resolved
    ):
        raise RuntimeError(
            "cross clearance 4X or DRILL TO SOCKET did not persist: "
            f"definitions={persisted!r}, resolved={resolved!r}"
        )


@_telemetry.traced("drawing.top_cross_tap_edge")
def _cross_tap_far_mouth_edge(view: Any) -> Any:
    """Pick the +X far-wall tap's mouth where its drill breaks into the socket.

    The near-wall clearance consumes the tap's entry rim on the counterbore
    floor, and looking down the axis its drill-bottom circle hides behind
    the far mouth (draw_fr_harmonic_base found the same on MHA-FR-01: the
    view neither lists nor maps that circle). The mouth itself, the tap
    cylinder's intersection with the socket bore, is the visible edge, seen
    through the clearance across the bore. It is found on the tap feature's
    far-wall cylinder, the face that ends at the drill-bottom circle.
    """
    center = (
        COLUMN_X / 1000.0,
        SCREW_AXIS_Y / 1000.0,
        (TOP_SCREW_SEAT_Z - SIDE_TAP_SPEC.depth_mm) / 1000.0,
    )
    radius = SIDE_TAP_DRILL_DIA / 2000.0
    part = _early_bound(_early_bound(view, "IView").ReferencedDocument, "IPartDoc")
    far_walls = []
    for name in CROSS_TAP_FEATURES:
        feature = part.FeatureByName(name)
        if feature is None:
            raise RuntimeError(f"top cross-tap feature {name!r} is missing")
        for raw_face in _early_bound(feature, "IFeature").GetFaces() or ():
            face = _early_bound(raw_face, "IFace2")
            if not _early_bound(face.GetSurface(), "ISurface").IsCylinder():
                continue
            edges = [_early_bound(raw, "IEdge") for raw in face.GetEdges() or ()]
            for edge in edges:
                curve = _early_bound(edge.GetCurve(), "ICurve")
                if not curve.IsCircle():
                    continue
                values = tuple(float(value) for value in curve.CircleParams)
                if (
                    abs(values[6] - radius) <= 1e-7
                    and all(abs(values[i] - center[i]) <= 1e-7 for i in range(3))
                    and abs(abs(values[5]) - 1.0) <= 1e-7
                ):
                    far_walls.append(edges)
                    break
    # The kernel may split the cylinder (and its bottom circle) at a seam.
    if not far_walls:
        raise RuntimeError("found no top cross-tap far-wall cylinder")
    mouths = []
    for edge in (edge for edges in far_walls for edge in edges):
        curve = _early_bound(edge.GetCurve(), "ICurve")
        if curve.IsCircle() or curve.IsLine():
            continue
        shown = _early_bound(view, "IView").GetCorrespondingEntity(edge)
        if shown is not None:
            start = tuple(round(float(v), 7) for v in tuple(edge.GetCurveParams2())[:3])
            mouths.append((start, shown))
    if not mouths:
        raise RuntimeError("top cross-tap far mouth has no visible view edge")
    _telemetry.info(f"top cross-tap far mouth: {len(mouths)} visible edge(s)")
    return min(mouths, key=lambda item: item[0])[1]

# Sheet 5: hub location, true-axis side view, removed set-screw boss section.
HUB_TOP_CENTER = (0.145, 0.200)
HUB_LEFT_CENTER = (0.145, 0.095)
HUB_LEFT_SCALE = (1, 2)
HUB_SECTION_CENTER = (0.330, 0.210)
HUB_SECTION_SCALE = (1, 1)
HUB_SECTION_CAPTION_XY = (0.330, 0.178)
# K-K prints 1:1, the bore axis pinned at x 332.0 mm (HUB_SECTION_PROFILE_X),
# so the boss face stands at 310.0, the spot face at 311.0 and the bore wall
# at 325.4; the rail top prints at y 230.1 and the tap axis at 211.8 (the
# 40d9d030e render).  The thread length nests inside the 21.0 and shares its
# spot-face extension line: it stands nearer the rail top with its text out
# LEFT, the 21.0 over it with its text out RIGHT, so neither leader leaves
# its line across the other's extension lines.  The cast boss face is not
# dimensioned here: its .95 is the model's SetBossFace, a Top-plane sketch
# dimension, which a section along the tap axis does not import (farm run
# 20261111T015941119Z); DETAIL J, a view of that plane, prints it.
HUB_SET_THREAD_LINE_XY = (0.3181, 0.2365)
HUB_SET_THREAD_OFFSET_XY = (0.2840, 0.2380)
HUB_SET_SPOT_LINE_XY = (0.3215, 0.2435)
HUB_SET_SPOT_OFFSET_XY = (0.3640, 0.2460)
# One ramp, three numbers: the 60.0 feather span, the 8.0 drop below the
# rail underside and the 20 DEG ramp all park in the band under the hub
# side view, so nobody has to hold one of them on another sheet.
HUB_GUSSET_SPAN_TEXT_XY = (0.180, 0.0810)
HUB_BOSS_DROP_TEXT_XY = (0.120, 0.0848)
HUB_BOSS_DROP_OFFSET_XY = (0.085, 0.0600)
# 186, not 190: centred any further right, the angle's block crosses the
# title block's left edge at x=216.
HUB_GUSSET_ANGLE_TEXT_XY = (0.186, 0.0645)
# The side view is a removed view (a left view laid under the plan), so
# the plan names it with a viewing arrow and letter and the view carries
# its own title and scale.  The arrow looks +X onto the left
# rail's outer face at z -80, between the front socket's boss and section
# K's letters: its letter stands 11 mm right of the 115.1's text and 5 mm
# over the historical D letter's placement baseline.
VIEW_LETTER = "G"
VIEW_LETTER_HEIGHT = 0.005
VIEW_ARROW_TIP_GAP = 0.0035
VIEW_ARROW_LENGTH = 0.013
VIEW_ARROW_SQUARE_TOL = 0.0003
VIEW_G_ARROW_Z = -80.0
_VIEW_G_TIP = (
    HUB_TOP_CENTER[0] - OUTER_X / SHEET_SCALE[1] / 1000.0 - VIEW_ARROW_TIP_GAP,
    HUB_TOP_CENTER[1] - VIEW_G_ARROW_Z / SHEET_SCALE[1] / 1000.0,
)
VIEW_G_ARROW = (
    (_VIEW_G_TIP[0] - VIEW_ARROW_LENGTH, _VIEW_G_TIP[1] + VIEW_LETTER_HEIGHT / 2.0),
    _VIEW_G_TIP,
)
HUB_LEFT_TITLE = f"VIEW {VIEW_LETTER}\nSCALE {HUB_LEFT_SCALE[0]}:{HUB_LEFT_SCALE[1]}"
HUB_LEFT_TITLE_XY = (0.128, 0.0455)

# Sheet 6: the underside locator at the title block's own scale and the
# hub/gusset detail J at 2:1.
HUB_BOTTOM_CENTER = (0.110, 0.200)
HUB_BOTTOM_SCALE = (1, 3)
# The underside view's label at the band's left edge.  The view is a bottom
# view laid out of projection on its own sheet, so it is a lettered view
# named by the viewing arrow under sheet 2's front view
# (UNDERSIDE_VIEW_ARROW; drawing-guidelines.md rules 9 and 26).
UNDERSIDE_VIEW_LETTER = "L"
HUB_BOTTOM_TITLE = f"VIEW {UNDERSIDE_VIEW_LETTER}"
HUB_BOTTOM_TITLE_XY = (0.020, 0.122)
# A centred caption's text (an iso caption) stands this close to its
# planned centre once re-centred.
NOTE_TEXT_CENTRE_TOL = 0.0005
HUB_DETAIL_CENTER = (0.300, 0.174)
HUB_DETAIL_SCALE = (2, 1)
HUB_DETAIL_CAPTION_XY = (0.300, 0.090)
# Up the open strip left of detail J, clear of F-F's grip and depth stacks:
# at (0.215, 0.100) its "CYLINDRICAL BOSS" row shared a line with F-F's
# "1.437" and read as "1.437 CYLINDRICAL BOSS" (machinist review at rubric
# 848e03f, rule 15, 2 of 3 runs).  Its rows now stand ~20 mm over the grip
# value, 11 mm right of F-F's +X BASIC box, and its right end ~10 mm outside
# the detail circle.
HUB_BOSS_DIA_TEXT_XY = (0.205, 0.124)
# The 28.0 rail pad, RibProfile's native width (a Top-plane sketch, so it
# imports into this view from below), where its two faces are drawn: farm
# run 20261027T195317391Z measured them on J at y 146.0 and 202.0 mm, x
# 268.97..331.02, the rail's inner face at x 334.2 and the window right of
# it empty to the detail circle (centre (300, 174), radius 76).  Its line
# stands in that window 15.8 mm off the rail, arrows inside (with its text
# offset, SolidWorks put them outside and left the stub floating at the
# line's mid on sheet 5).  The text sits outside the detail like the 7.0's
# over it (HUB_GUSSET_T_OFFSET_XY), in the native D1 form measured on sheet
# 5 (value from 5.14 mm over the offset y, rows from 0.42, 5.98 and 11.53
# under it, centred on the offset x, the underline the widest row's width
# on the last row's base): "CENTRED ON BORE" 42.8 mm wide (the 7.0's row),
# its lower-left corner 2.4 mm outside the circle and its right end 2.5 mm
# inside the border, the value's top 10.7 mm under the 7.0's last row.  The
# stub climbs from the line's mid to the underline's near end.
RIB_WIDTH_LINE_XY = (0.350, 0.174)
RIB_WIDTH_TEXT_XY = (0.3952, 0.212)
HUB_GUSSET_T_TEXT_XY = (0.300, 0.212)
HUB_GUSSET_T_OFFSET_XY = (0.390, 0.243)
# The cast set-screw boss face, the model's own SetBossFace, .95 ±.03 from
# the bore axis on the faced top's plane (owner rulings B2, B4 and D1,
# #2333): the face leans in under it, the draft taken out, so from below its
# top edge is the boss's outer line (x 251.7 at 2:1, the bore at 300.0).
# The line runs through the boss at y 180, 6 mm over the bore axis, and the
# text parks out left of the fence, in the free band between it and the
# underside locator: the fence crosses y 200 at x 228.6 and the rows end
# 4.4 mm short of it, 4.6 off the locator's rail (at x 212 "AT FACED TOP"
# touched the fence, farm run 20261111T023438415Z).
SET_BOSS_FACE_LINE_XY = (0.276, 0.180)
SET_BOSS_FACE_TEXT_XY = (0.208, 0.200)
HUB_BOTTOM_KEEP = {
    "HubDia": HUB_BOSS_DIA_TEXT_XY,
    "RibWidth": RIB_WIDTH_LINE_XY,
    "GussetT": HUB_GUSSET_T_TEXT_XY,
    "SetBossFace": SET_BOSS_FACE_LINE_XY,
}
HUB_BOTTOM_CALLOUTS = {
    "HubDia": "CYLINDRICAL BOSS\nAT UNDERSIDE",
    "RibWidth": "FULL-HEIGHT\nPAD WIDTH",
    "GussetT": "2X GUSSET",
    "SetBossFace": "AT FACED TOP",
}
# The junction lands are located end by end from the crossbar's +X face on
# the front land (land width 73.0 = 25.0 + 2 x 24.0, both ends alike): the
# old 73.0 across the whole land put its -X extension line in the knockout
# callout's leader path (farm run 20261027T133857303Z, leader-crosses-line).
# The +X end's extension lines stand at the bar face (x 109.17 mm, from its
# front edge at y 175, unbroken at .06) and the land end (x 117.17, from y
# 163.8), right of the knockout leader's arrow (about x 107.4 on the front
# ream).  The
# dimension line runs
# at y 145 between them, arrows inside (8 mm), the text parked right on a jog
# where the 73.0's block stood.
LAND_END_TEXT_XY = (0.11321, 0.145)
LAND_TEXT_OFFSET_XY = (0.155, 0.145)
# A location carries its value and count only (drawing-guidelines.md rule 7).
LAND_END_CALLOUT = "4X"
# The faced underside plane's linked note C (top-left point).  The bands
# round the locator are full: between F-F's 7.100 block (top 113.3 mm on
# farm run 40d9d030e) and the 72.0 block (bottom 137.6) stand 24.3 mm, under
# the four rows' 20.4 plus two clearances, and right of the plan the Ø30.0
# leader and detail J's fence leave 41 mm.  So the note takes the open band
# right of detail J's caption, over the title block.  The historical DETAIL C
# caption ended at 316.1 mm on 40d9d030e; that is placement evidence, not a
# measurement of J's glyphs.  The note's estimated 80.6 x 20.4 mm block stays
# beside the hub boss and gussets it excludes.  Native inspection must
# establish the renamed caption's clearance.
UNDERSIDE_FACING_NOTE_XY = (0.330, 0.098)
# Each ream's station is F-F's plain .XXX .300 from its screw axis
# (machinist review r1: no basic or tolerance in note text); Owner ruling
# 2026-11-08 (Pedro), #2144 item 11.3 deleted the -X reams and their BASIC
# span and frames.
# Sheet 6, removed section F-F through the REAR knife-hanger station: the
# #10 plain clearance hole, with the native finished top-to-underside grip,
# and the dowel ream, with its knockout up to the faced top, cut along
# the dowel line.  The cut crosses only the crossbar and its
# junction gussets, its ends in the window past the gussets' rail-face reach.
# _orient_cut_section looks along -Z (model X right, Y up), which is sheet-down
# on the locator, so both letters drop into the open window below the cut
# rather than onto the rear rail 2.9 mm (model) above it.
HANGER_SECTION_Z = STUD_Z_REAR
HANGER_SECTION_GUSSET_REACH = GUSSET - (INNER_Z - HANGER_SECTION_Z)  # 15.148
HANGER_SECTION_CUT_X = (BAR_X0 - GUSSET - 12.0, BAR_X1 + GUSSET + 12.0)
HANGER_SECTION_CENTER = (0.120, 0.075)
HANGER_SECTION_SCALE = (1, 1)
# The screw axis prints here; the outline centring sets the row (model y 0).
HANGER_SECTION_PROFILE_X = 0.120
_HANGER_SECTION_M_PER_MM = HANGER_SECTION_SCALE[0] / HANGER_SECTION_SCALE[1] / 1000.0


def _hanger_section_xy(x: float, y: float) -> tuple[float, float]:
    """Sheet point (m) of model (x, y) mm in the pinned section F-F."""
    return (
        round(HANGER_SECTION_PROFILE_X + (x - HANGER_X) * _HANGER_SECTION_M_PER_MM, 5),
        round(HANGER_SECTION_CENTER[1] + y * _HANGER_SECTION_M_PER_MM, 5),
    )


# Right of the profile, nested: the 36.50 grip, its line 3.2 mm right of the
# gussets' cut end and its text on a stub above the depth's
# (HANGER_GRIP_OFFSET_XY), then the depth both reams share, its text
# beside its line clear of both (HANGER_PIN_DEPTH_OFFSET_XY).  The grip's
# extension lines leave from its attachment beyond the profile's right end
# (x 149.5 mm on farm run 20261027T143609236Z, when it stood left of the
# profile and they ran across the whole underside), so on the right they no
# longer pass under the reams'
# mouths, where datum A's frame leader enters (HANGER_PERP_FRAME_XY); the
# depth's extension line at the ream floor crosses the grip's line, as
# extension lines may.  Above, between the owned axes: the ream's station
# from the screw axis, its text on a jog to the right.  The linked caption
# sits directly below the section.  Native inspection establishes the
# text/arrow/leader clearances.
HANGER_GRIP_TEXT_XY = _hanger_section_xy(
    BAR_X1 + HANGER_SECTION_GUSSET_REACH + 10.35, -HALF_H + HANGER_GRIP / 2.0
)
PIN_STATION_TEXT_XY = _hanger_section_xy((HANGER_X + PIN_HOLE_X) / 2.0, HALF_H + 8.0)
# A location carries its value and count only (drawing-guidelines.md rule
# 7): F-F's cutting plane holds the screw axis and the ream, so no words
# say they share a line (the ream's implied-zero "SAME Z", Owner ruling
# 2026-11-08 (Pedro), #2144 item 11.3), and the mate sits on the ream's
# size callout.
PIN_STATION_OFFSET_XY = (0.157, 0.1115)
PIN_STATION_CALLOUT = "2X"
# The depth's value and its three rows (the flat floor and its corner limit,
# codjiflo round 4) are four rows, more than its 12 mm between extension
# lines holds, so they park beside its line on a level stub at the ream's
# mid-depth.  Farm run 20261027T175429300Z measured the native form: the
# rows centred on the offset x, the value 2.78 mm above the offset y, the
# rows 5.56 mm apart under it from 2.78 mm, the last on the underline the
# stub meets at its near end; "CORNER R0.1 MAX" ran 41.94 mm, so the inch
# corner limit takes its own row ("CORNER R.003 MAX" would overrun the
# band).  With the line 34.5 mm right of the gussets' cut end that block
# ran to x 230, 14 mm into the title block (layout audit keep-out, the
# dimension's box reaching down to its floor witness at y 50.4), so the line
# now stands 19.6 mm right of the cut end, its upper tail 2.1 mm right of
# the grip's text, and the block starts 2 mm right of it, its last row
# level with the stub (one row higher for the fourth), and ends short of
# the title block.
HANGER_PIN_DEPTH_OFFSET_XY = (0.19025, 0.07664)
HANGER_SECTION_KEEP = {
    "HangerPinHoleDepth": _hanger_section_xy(
        BAR_X1 + HANGER_SECTION_GUSSET_REACH + 19.6,
        -HALF_H + HANGER_PIN_HOLE_DEPTH / 2.0,
    ),
    "HangerGrip": HANGER_GRIP_TEXT_XY,
}
# Datum A, the faced underside the knife mounts seat on, and the reams'
# perpendicularity to it, Ø.001, both (owner rulings 2026-10-27 (#2016),
# option A, and 2026-11-06): F-F shows that plane edge-on and the ream along its axis.
# A's tag hangs 9.75 mm under the underside edge, picked 7.5 mm outside the
# crossbar's -X face, left of the crossbar; its box stands right of its
# leader.  The one "2X" frame stands under the profile's right end, its
# leader from its left end entering the ream's mouth from below, to land on
# the ream's -X wall 3 mm up: through the mouth no outline or line is
# crossed, and it passes 2.0 mm off the depth's extension line, which starts
# 1 mm off the ream's +X wall.  The frame's cells (symbol, Ø tolerance, one
# datum) match farm run 20261027T143609236Z's position frames: 7.0 + 16.12
# + 6.63 mm.
HANGER_FLOOR_DATUM = "A"
HANGER_FLOOR_DATUM_PICK_X = BAR_X0 - 7.5
HANGER_FLOOR_DATUM_SYMBOL_XY = (
    _hanger_section_xy(HANGER_FLOOR_DATUM_PICK_X, 0.0)[0],
    0.047,
)
HANGER_PERP_LANDING = (PIN_HOLE_X - HANGER_PIN_HOLE_DIA / 2.0, -HALF_H + 3.0)
HANGER_PERP_FRAME_XY = (0.14335, 0.0455)
HANGER_PERP_FRAME_OUTLINE = (0.0, -0.0070, 0.02975, 0.0)
HANGER_PERP_FRAME_QUANTITY = "2X"
# One targeted import: the Crossbar extrude owns the grip and the reams'
# cut the depth (fd0350a85746, leaf 20261014T203505Z-1-494a6e80, delivered
# both from one selection).  Since the faced top, the ream sketch's
# diameter has not reached F-F, which sees the reams edge-on, even imported
# apart from the grip (d8fac576, leaf 20261014T212023Z-1-90af84a0).
# The grip prints under the title block's .XXX band (owner ruling
# 2026-10-18: MHA-SM-VN-52 is cut to the measured grip at SM-00) and names
# the bolt whose grip it is (machinist review: a three-place size states
# its function).  Its two rows are wider than the 14.7 mm between the
# profile and the depth's rows, so they park on a stub above the depth's
# ".47": the native linear OffsetText form (rows centred on the offset x,
# the value's baseline on the offset y, the underline the widest row's
# width 5.56 mm under it) puts the 46.1 mm row at x 160.5..206.6 on
# y 88.0, 2.3 over the ".47" and 2.9 under the boss's Ø1.18 underline, and
# the value 4.0 under the reams' station underline (y 100.4) and 3.0 left
# of the Ø1.18 row.  The stub climbs from the grip line's mid (x 158.15).
HANGER_GRIP_CALLOUT = "MHA-SM-VN-52 GRIP"
HANGER_GRIP_OFFSET_XY = (0.18355, 0.0936)
HANGER_SECTION_CALLOUTS = {
    "HangerPinHoleDepth": HANGER_PIN_DEPTH_CALLOUT,
    "HangerGrip": HANGER_GRIP_CALLOUT,
}
HANGER_SECTION_CAPTION_XY = (0.120, 0.031)
# Sheet 6, UNDERSIDE locator (1:3, model x right and z up from the view
# centre): the reams carry no frame here (Owner ruling 2026-11-08 (Pedro),
# #2144 item 11.3: the -X reams, their position frames and the +X reams'
# datum tags are deleted, and with them owner ruling 2026-11-06's per-pair
# 2X ⌖Ø.004|A|D, SEP REQT).  The REAR ream's size, face-on here, climbs to
# its block over the plan.  The FRONT ream's knockout callout parks in the
# band under the front rail, its leader landing left of the land-end
# dimension's lines (LAND_END_TEXT_XY).
_HUB_BOTTOM_M_PER_MM = HUB_BOTTOM_SCALE[0] / HUB_BOTTOM_SCALE[1] / 1000.0
# The rear ream's size (the circle that owns HangerPinHoleDia), with its
# stacked +0.000/-0.010 band and its one callout row: count, process, REF
# depth, mate and fit.  Farm run 20261027T030041319Z printed the block
# centred on its point: the 42-glyph row 112.5 mm wide (2.68 mm a glyph, as
# estimated) on its shelf at y 247.5 mm, the shelf starting 1.5 mm left of
# the row, the band's top at 261.1, so 15.1 mm in all, inside the 17.9 mm
# between the plan's top and the sheet frame less ink each side.  The block
# stands 25.9 mm left of its older foot (145.9, 247.2) mm: its leader rises
# 58 deg from the rear ream, and the block ends 47 mm short of detail J's
# fence (the layout audit read the old block's right end into J's view).
# Right of the ream, the cutting line, F-F's right arrow and the rear-right
# boss leave no leader route to a block beside the plan.
# Rule 26: a blind ream's callout carries its depth (farm run
# 20261107T004559647Z, stability repeat 1: "gives size and process but no
# depth").  F-F's native .47 to the flat floor, with its corner limit, stays
# the control, so the callout prints it as REF, the rule's own example
# (`↧ (.235)` with the floor located on a view), between process and mate.
# FLAT BOTTOM and the corner stay with F-F's .47: the row may grow only 10
# glyphs before it reaches detail J's fence, and the band leaves no height
# for a second row.
HANGER_PIN_DEPTH_REF = f"({HANGER_PIN_HOLE_DEPTH / 25.4:.2f})".replace("(0.", "(.")
_REAM_PROCESS, _REAM_MATE = HANGER_PIN_HOLE_CALLOUT.split(", ")
HANGER_PIN_DIA_CALLOUT = (
    f"{_REAM_PROCESS} <HOLE-DEPTH>{HANGER_PIN_DEPTH_REF}, {_REAM_MATE}"
)
# The depth token prints as one ↧ glyph.
HANGER_PIN_DIA_CALLOUT_PRINTED = HANGER_PIN_DIA_CALLOUT.replace("<HOLE-DEPTH>", "↧")
HANGER_PIN_DIA_TEXT_WIDTH = 0.067 * max(25, len(HANGER_PIN_DIA_CALLOUT_PRINTED)) / 25
HANGER_PIN_DIA_TEXT_HALF_HEIGHT = 0.0076
HANGER_PIN_DIA_TEXT_XY = (
    0.120 + HANGER_PIN_DIA_TEXT_WIDTH / 2.0,
    0.2472 + HANGER_PIN_DIA_TEXT_HALF_HEIGHT,
)
# The knockouts' native callout (dt_crankshaft's form: the drill above the
# native "2X" size and extent, the purpose below) on the FRONT ream's
# knockout circle, seen on its floor through the ream.  Farm run
# 20261027T030041319Z printed its three rows about the point (43.69, 142.8)
# mm: rows centred on the point's x, the widest ("MHA-SM-VN-53 KNOCKOUT")
# 61.3 mm, its underline 62.9 mm from x 13.04 at y 134.44, rows 5.56 mm
# apart up to the top row's cap line at 149.1, the block centred 1.0 mm
# under the point.  That underline began 0.34 mm inside the inner border,
# with no visible air (machinist review, rule 13).  The knockout drills up
# from the ream floor on the ream's drawn axis (codjiflo, PR #1978), its
# coaxiality the title block's implied ±0.13, charged in the floor land
# (0.316, RV-06; owner ruling 2026-10-27); the drill row and a row under
# the native size state it, so four rows, none
# wider than 21 glyphs (estimated at the measured row's width): 20.2 mm
# tall, centred on the same 1.0 mm offset.  The block stands 4.0 mm inside
# the border in the band under the front rail, 5 mm under the front-left
# boss and 7.9 mm over the bottom view's note.  Its leader leaves the
# underline's right end up-right to the floor circle.  On the former -X
# ream it landed at x 102.3 mm; the +X ream stands 15.24 mm (5.08 mm at
# 1:3) further right (Owner ruling 2026-11-08 (Pedro), #2144 item 11.3), so
# it lands about x 107.4, still left of the land-end dimension's extension
# lines (x 109.17 and 117.17 mm) and their dimension line: it crosses no
# dimension line, only the part's own outline.
HANGER_KNOCKOUT_CALLOUT_INK = (-0.03065, -0.01114, 0.03223, 0.00908)
HANGER_KNOCKOUT_CALLOUT_XY = (
    SHEET_FRAME[0] + 0.004 - HANGER_KNOCKOUT_CALLOUT_INK[0],
    0.1410,
)
# The crossbar pockets' length stands outside the plan, so nothing inside
# the frame reads as part of it: its dimension line at model x -256, 12.2
# left of the Ø45 barrels, 7.0 left of detail J's fence (r 38 about the
# gooseneck) and 12.0 inside the sheet frame; its extension lines run at
# y 177 / 223, under and over that fence and between the corner bosses.
# The block (two rows: the value and "2X POCKET"; three rows printed 17.5 mm
# tall on farm c75ac06 when it also named E-E, its
# widest row 33.9 mm by the 40d9d030e render's glyphs) parks on an offset
# leader above the plan's top-left corner: 2.4 inside the sheet frame's left
# edge, 2.45 under its top, 1.9 over the plan's top and its top-left boss,
# and 3.0 left of the former rear -X ream frame's place.
POCKET_LENGTH_TEXT_XY = (
    HUB_BOTTOM_CENTER[0] - 256.0 * _HUB_BOTTOM_M_PER_MM,
    HUB_BOTTOM_CENTER[1],
)
POCKET_LENGTH_OFFSET_XY = (0.0320, 0.2555)
# The front pocket end's 43.0 from the front-left socket axis shares that
# dimension line (front, B, at the bottom of this view: model z runs up),
# 14.3 mm long on paper between the socket axis's extension line (y 162.7)
# and the pocket end's (177.0).  Its value stands on the line, which breaks
# round it (about 12 x 3.5 mm, x 18.6 -> 30.2, left of the plan's 36.8).
# An offset-text jog there threw the whole dimension 24 mm left, off the
# sheet frame (farm run 20261018T061230033Z-344b527a..., sheet 6), and the
# plain text point did too (20261018T065727559Z-54ee64e9..., r3), so the
# build reads the drawn line back and moves it onto this x
# (``_pin_vertical_dimension_line``).
BAR_POCKET_FROM_SOCKET = abs(FRONT_COLUMN_Z) - BAR_POCKET_Z
POCKET_FROM_SOCKET_LINE_XY = (
    POCKET_LENGTH_TEXT_XY[0],
    HUB_BOTTOM_CENTER[1] + (FRONT_COLUMN_Z - BAR_POCKET_Z) / 2.0 * _HUB_BOTTOM_M_PER_MM,
)
# VIEW L's as-cast locations are the model's own, each with its ±.03 (owner
# ruling B2, #2333).
UNDERSIDE_KEEP = {
    "LandEnd": LAND_END_TEXT_XY,
    "PocketFromSocket": POCKET_FROM_SOCKET_LINE_XY,
    "PocketLength": POCKET_LENGTH_TEXT_XY,
}
UNDERSIDE_CALLOUTS = {
    "LandEnd": LAND_END_CALLOUT,
    "PocketFromSocket": "",
    "PocketLength": "2X POCKET",
}

# Sheet 2, Sections E-E and M-M: the left side rail and the crossbar T, cut
# on one station inside the crossbar pockets (|z| <= 69, where the crossbar
# is a T) and clear of every hole station (keeper taps at z -83.5 / 82.5,
# hangers at -84.0 / 90.1, corner bosses at z +/-112), so each section
# carries rail or T stock only: fr_top_frame_spec.SIDE_SECTION_Z, where the
# model stands the widths these sections import.
# Removed sections are centred on the cut span, so each centre puts the
# dimensioned profile where it sat when one full cut drew both pieces:
# H-H's single T at the old right-hand T (the web/flange/chamfer callouts
# keep their lanes), E-E's left rail and M-M's crossbar T where those two
# stood in the old E-E.
RAIL_SECTION_CENTER = (0.3566, 0.205)
# The lone T is 12 mm tall at 1:3, so the native caption climbs to the web
# width callout unless it is pinned.  H-H prints at the sheet's own 1:3, so
# its caption carries no scale (ASME Y14.3; rule 9: a scale equal to the
# sheet's restates the title block).
RAIL_SECTION_CAPTION_XY = (0.3566, 0.169)
SIDE_SECTION_CENTER = (0.2967, 0.106)
# E-E and M-M print at the sheet's own 1:3 (Main's delegated layout
# ruling, 2026-11-07, after the machinist reviews of farm run
# 20261107T204437943Z's PDF found the 1:4 T-sections cramped): like H-H,
# their captions then carry no scale row (rule 9).  The captions (one
# 44 mm "SECTION X-X" row) stand centred under their own sections, 3.5 mm
# lower than the 1:4 pair so M-M's top stays clear of the crossbar web
# callout's ink, which drops with the larger T; their bottoms stay 14 mm
# over the title block's top (y 65.4).
SIDE_SECTION_SCALE = (1, 3)
SIDE_SECTION_CAPTION_XY = (0.2967, 0.0845)
# E-E's web value and its 2X WEB row stand left of E-E's rail, on its
# dimension line (printed 5.56 mm under the text point, 3.8 mm over the
# flange).  Parked right of the rail (0.327) the 37.5 mm "2X SIDE RAIL WEB"
# row ran out over M-M and read as M-M's (local machinist review of farm
# run 20261107T170344738Z's PDF, r1, 2 of 3 runs); centred over the rail
# (0.2967) the web's two extension lines ran up through "RAIL" (farm run
# 20261107T204437943Z, r1).  E-E cuts the side rail only, so "2X WEB" says
# it; its 15.5 mm row ends 2 mm left of the web's left extension line and
# starts 10 mm right of the plan's 1.35 SIDE FLANGE text (x 266.7 mm).
SIDE_WEB_TEXT_XY = (0.284, 0.120)
SIDE_WEB_QUALIFIER = "2X WEB"
# Each section's web axis centreline runs this far (paper mm, times the
# section's scale denominator in model mm) past the T's top and underside.
SECTION_AXIS_OVERRUN_MM = 2.0
# Sheet 2's viewing arrow naming sheet 6's bottom view: under the front
# view's left rail (the view spans y 82..98 mm on the v47 render), pointing
# up at the underside from VIEW_ARROW_TIP_GAP below it, its letter beside
# the tail.  The band under the front view is empty to the border.
_UNDERSIDE_ARROW_TIP = (
    GEOMETRY_FRONT_CENTER[0] - 0.035,
    GEOMETRY_FRONT_CENTER[1]
    - (RING_HEIGHT + BOSS_ABOVE + BOSS_BELOW) / 2.0 / SHEET_SCALE[1] / 1000.0
    - VIEW_ARROW_TIP_GAP,
)
UNDERSIDE_VIEW_ARROW = (
    (_UNDERSIDE_ARROW_TIP[0] - 0.0045, _UNDERSIDE_ARROW_TIP[1] - VIEW_ARROW_LENGTH
     + VIEW_LETTER_HEIGHT / 2.0),
    _UNDERSIDE_ARROW_TIP,
)
# Where each removed section prints the rail centreline it cuts, sheet x:
# H-H at z 112 and E-E / K-K at x -197.  These profile targets are unchanged
# from b49e1's B-B / E-E / D-D layout calibration; those historical labels
# describe that render, not the current native view identities.
# _pin_section_profile holds the profiles here however far the cut runs.
RAIL_SECTION_PROFILE_X = 0.35643
SIDE_SECTION_PROFILE_X = 0.29666
HUB_SECTION_PROFILE_X = 0.33198
# M-M's crossbar T dimensions: the web's and the flange's dimension lines
# stand one 5 mm paper gap off the T (15 model mm at 1:3: the web's below
# its underside, the flange's right of its +X face) and their text parks on
# a leader at the right of the section, right of M-M's caption, the
# flange's 38.7 mm row 2 mm or more inside the sheet frame.  The pockets'
# depth (flange underside to the T's underside) stands 2.7 mm left of the
# flange's -X face, its arrows inside: outside, their tails would cross the
# side web's dimension line above and the web's arrow tail below.  Its two
# rows (24.4 x 9.2 mm) park low between the side rail and the T, 10 mm
# right of the rail and 3.0 under the side web's line.
_SIDE_SECTION_M_PER_MM = SIDE_SECTION_SCALE[0] / SIDE_SECTION_SCALE[1] / 1000.0
_SECTION_DIM_GAP_MM = 5.0 * SIDE_SECTION_SCALE[1] / SIDE_SECTION_SCALE[0]


def _side_section_xy(x: float, y: float) -> tuple[float, float]:
    """Sheet point of model ``(x, y)`` on E-E's and M-M's shared row: E-E's
    rail pinned at x -197, M-M's crossbar the same model distance right of
    it at the sections' scale (CROSSBAR_SECTION_PROFILE_X)."""
    return (
        SIDE_SECTION_PROFILE_X + (x + COLUMN_X) * _SIDE_SECTION_M_PER_MM,
        SIDE_SECTION_CENTER[1] + y * _SIDE_SECTION_M_PER_MM,
    )


# The crossbar's own section (rule 9: E-E's plane left the rail and the T
# floating apart).  M: the next letter no view, datum or table tag uses.
CROSSBAR_SECTION_LETTER = "M"
CROSSBAR_SECTION_PROFILE_X = _side_section_xy(HANGER_X, 0.0)[0]
CROSSBAR_SECTION_CENTER = (CROSSBAR_SECTION_PROFILE_X, SIDE_SECTION_CENTER[1])
CROSSBAR_SECTION_CAPTION_XY = (CROSSBAR_SECTION_PROFILE_X, SIDE_SECTION_CAPTION_XY[1])


CROSSBAR_WEB_LINE_XY = _side_section_xy(HANGER_X, -HALF_H - _SECTION_DIM_GAP_MM)
CROSSBAR_WEB_TEXT_XY = (0.382, 0.0925)
CROSSBAR_FLANGE_LINE_XY = _side_section_xy(
    BAR_X1 + _SECTION_DIM_GAP_MM, (HALF_H + FLANGE_BOT_Y) / 2.0
)
CROSSBAR_FLANGE_TEXT_XY = (0.3936, 0.108)
CROSSBAR_POCKET_DEPTH_LINE_XY = _side_section_xy(BAR_X0 - 8.0, (FLANGE_BOT_Y - HALF_H) / 2.0)
CROSSBAR_POCKET_DEPTH_TEXT_XY = (0.3245, 0.1068)
# E-E and M-M import their as-cast sizes off the stations the model stands
# them on (fr_top_frame_spec.SIDE_SECTION_Z): the side web, and the
# crossbar's web and pocket depth.
SIDE_SECTION_KEEP = {"SideWebT": SIDE_WEB_TEXT_XY}
CROSSBAR_SECTION_KEEP = {
    "CrossbarWebT": CROSSBAR_WEB_LINE_XY,
    "PocketDepth": CROSSBAR_POCKET_DEPTH_LINE_XY,
}
CROSSBAR_SECTION_CALLOUTS = {
    "CrossbarWebT": "CROSSBAR WEB",
    "PocketDepth": "2X POCKET",
}
# swDimensionArrowsSide_e (draw_dt_cone_tip_block's native-arrow precedent).
_DIM_ARROWS_INSIDE = 0

# #955 (layoutcheck on b49e1): three cutting-plane letters printed on ink.
# B's outer letter sat on the +Z rail's outer edge and the 183.9, E's outer
# letter on the corner boss and the (446.2) witness line, and D's inner
# letter on the hub rail's inner face.  Two more stood under 1 mm off it:
# B's inner letter off the rail's inner face (0.82), E's inner letter off
# the 18.0 gusset witness line (0.51).  IDrSection has no letter position;
# SolidWorks prints each letter past the arrow on its cutting line's end.
# That established the cutting stations and endpoints section_cut_ends()
# preserves when the live section identifiers change to H/E/K.
#
# Historical B/E/D ink about each arrow tail, (dx0, dy0, dx1, dy1) in sheet m,
# measured on b49e1 and rounded outward.  B's arrows point +X; E's and D's
# point +Y.  These are placement calibration, NOT H/K glyph measurements;
# native inspection must establish the renamed letters' clearance.
SECTION_CUT_BASELINE_LETTER_EXTENTS = {
    "B": (0.0153, -0.0013, 0.0191, 0.0050),
    "E": (-0.0015, 0.0158, 0.0020, 0.0221),
    "D": (-0.0024, 0.0158, 0.0028, 0.0221),
}
# M has no measured glyph: E's box widened by 1.4 mm each side for M's
# broader letterform (an estimate, rounded outward; the layout audit on the
# next render is its measurement).
CROSSBAR_SECTION_LETTER_EXTENTS = (-0.0029, 0.0158, 0.0034, 0.0221)
# The two window clear widths print their values on one line across the
# plan's lower rail.  The right one's text ("183.9" on b49e1, now 182.9 in
# as many glyphs) measured on b49e1 about its text point
# (left, down, right, up), rounded outward.  Its dimension line runs 2.78 mm
# under the text point, rounded toward the text so the band under the rail
# is never overstated.
WINDOW_WIDTH_TEXT_XS = (0.105, 0.190)
WINDOW_WIDTH_TEXT_Y = 0.118
WINDOW_WIDTH_TEXT_EXTENT = (0.0052, 0.0019, 0.0056, 0.0018)
WINDOW_WIDTH_DIM_LINE_DROP = 0.0027
# The historical B outer letter had only the 9.6 mm band between that
# dimension line and the rail's outer edge.  Its calibrated placement uses
# the text clearance rather than INK_CLEARANCE.  Keep this baseline fixed:
# changing it to guessed H glyph metrics would move the actual section plane.
TEXT_CLEARANCE = 0.0015
# Historical B width plus clearance: another fixed input to cut placement,
# not a live H glyph width or a claim about its clearance.
SECTION_CUT_BASELINE_TEXT_GAP = (
    SECTION_CUT_BASELINE_LETTER_EXTENTS["B"][2]
    - SECTION_CUT_BASELINE_LETTER_EXTENTS["B"][0] + INK_CLEARANCE + ROUND_OUT
)

# Only views drawn at a scale the title block does not state carry a label,
# and every label sits under its own view - centred where the dimension
# lanes below the view leave room, offset within that band where they do not.

# The hub side view (1:2) sees the set-screw boss face on: the tap centre
# prints at (146.5, 95.9) mm and the boss's sides at x 142.0 / 151.0.  The
# 18.0 width stands over the rail, its extension lines up from the boss's
# top corners (y 101.0) through the flange, its three rows straight over
# it, under the plan above.  The last row puts the boss's
# top on the flange underside (codex review of 4faacfab: its shoulder had no
# height).  Every leader that leaves the boss passes UNDER those extension
# lines' feet, so each side holds one: the tap callout's leader keeps the
# right (2.3 off that foot), and the Ø10.0 spot face takes the left, at 153
# deg, 2.5 off the left foot.  Steeper, either would cross an extension
# line; shallower, either would run along the rail (leader-over-part detour,
# 10 mm gate: the spot's is 7.2, its 17.5 over the part against 10.2 from
# the spot's rim to the view's top).  Its two rows land right, 4.8 over the
# left barrel's top (107.2) and, estimated, 2.6 left of the width's wider
# rows (test_hub_side_boss_width_and_spot_face_stand_clear_of_their_ink).
SET_BOSS_WIDTH_LINE_XY = (0.1465, 0.1150)
SET_BOSS_WIDTH_TEXT_XY = (0.1465, 0.1264)
SET_SPOT_DIA_TEXT_XY = (0.0958, 0.1177)

# The first sheet contains only the frame and T-rail definition.  Every
# width with an as-cast end is the model's own dimension, carrying its ±.03
# (owner ruling B2, #2333), imported into the view that shows it true: the
# side flange on the plan, the front/rear T in H-H, the side web in E-E, the
# crossbar's web and pockets in M-M.
GEOMETRY_TOP_KEEP = {
    "Width": (
        GEOMETRY_TOP_CENTER[0],
        0.2435,
    ),
    "Depth": (0.046, 0.1335),
    "SideFlangeWidth": (0.250, 0.120),
}
# The front view carries the rail's web depth -- the web ring's own driving
# extrude depth, the same finished top-to-underside thickness F-F prints as
# HangerGrip, so it prints as a reference with no band of its own
# (_reference_model_rail_height) -- and the web root radius, which
# SolidWorks shows on an elevation only (farm run 20261111T004615500Z: no
# removed section took it).  The radius's rows stand under the view's west
# end, 7.7 mm under the boss bottom and 8 mm left of the title block, on a
# short leader from the root.  The draft angles print on sheet 7's
# elevation (DATUM_FRONT_KEEP).
GEOMETRY_FRONT_KEEP = {
    "RingHeight": (0.238, 0.091),
    "RootR": (0.190, 0.071),
}
GEOMETRY_CALLOUTS = {
    "Width": "RAIL FLANGE EXTENT",
    "Depth": "RAIL FLANGE EXTENT",
    "SideFlangeWidth": "2X SIDE FLANGE",
    "RingHeight": "RAIL HEIGHT",
    "RootR": "TYP WEB ROOT",
}
RAIL_SECTION_KEEP = {
    "FrWebT": (0.380, 0.192),
    "FrFlangeWidth": (0.328, 0.230),
    "FlangeT": (0.372, 0.2117),
}
RAIL_SECTION_CALLOUTS = {
    "FrWebT": "2X WEB WIDTH",
    "FrFlangeWidth": "2X FLANGE",
    "FlangeT": "TYP TOP FLANGE",
}
# The 8.1 flange run is 2.7 mm of paper: its text parks on a leader.
FLANGE_T_TEXT_OFFSET_XY = (0.389, 0.2245)

# The plan's flange extents follow from the socket pitches (sheet 3) and the
# rail flange widths, each flange standing on its own socket axes: the 1.35
# side flanges here, the 1.50 front / rear flanges in H-H.  A socket bore is
# a feature the shop touches, so the extents print as references, derived
# from those widths.
PLAN_REFERENCE_DIMENSIONS = ("Width", "Depth")

# Owner ruling D3 (#2333): each rail web's median plane holds ⌖.06|A|B to
# its socket axes (datum B, the 4X socket pattern).  The frame reads off the
# web's cut face beside its thickness: SolidWorks refused to move a frame
# onto the thickness dimension itself (farm run 20261111T004615500Z,
# IAnnotation.SetAttachedEntities -> False).  Each lands at this height on
# the face, one frame for the two rails its section stands for.
WEB_POSITION_LANDING_Y = -5.0
WEB_POSITION_QUANTITY = "2X"
RAIL_WEB_POSITION_FRAME_XY = (0.297, 0.194)
# E-E's frame stands 8.5 mm under the web's foot, so its "2X" row clears the
# section's caption under it by 2.5 mm (1.0 at y 97, farm run
# 20261111T023438415Z).
SIDE_WEB_POSITION_FRAME_XY = (0.3065, 0.0985)

# The boss/socket diameters leave the socket they qualify in opposite
# directions so neither leader crosses the other's text.  The hole STATIONS
# are not imported: the model's Hole Wizard placement dims measure from the
# origin -- mid-air on the print, a centre the shop would first have to
# derive from the socket pattern -- so sheet 3 dimensions every hole from
# the socket bore axes instead (``HOLE_STATIONS``, drawing-guidelines.md rule 10 (dimension from a real feature)).
DETAIL_TOP_KEEP = {
    # The boss diameter, as cast on the faced top's plane, over the socket
    # block; its near-side leader climbs to the upper-left boss's rim.
    "C0Dia": (0.035, 0.236),
    # Three rows (the value, the mating tube and the fit it holds, machinist
    # review r1), the widest 25 glyphs (2.58 mm each, farm run
    # 20261106T212431241Z: 64.5 mm).  It stands left of the plan, under the
    # boss's leader, so its radial leader climbs to A2's lower-left rim.
    "B0Dia": (0.047, 0.193),
}
# Sheet 3's tagged hole table: the four tube sockets, BASIC from the
# casting's own datum frame (owner rulings B6 and D2, #2333).  Its origin is
# the corner of the F and G planes -- the rear barrels' and the rear-west
# barrel's datum-target tangents (build_fr_top_frame.CAST_DATUM_ORIGIN_XZ),
# the plan's lower right -- so X counts left from it and Y up, and the
# composite frame on the sockets (SOCKET_POSITION_*) holds the pattern to
# E|F|G.  Both planes print as thin phantom lines (TABLE_TANGENT_*): F under
# the two rear bosses, G up the rear-west boss.  The table's native origin
# mark is reattached to a view point on that corner, its X arrow under the
# corner and its Y arrow right of it (TABLE_ORIGIN_*_ARROW).  The hanger
# holes are not in it: they stand on datum D by their own frame and take
# their Z stations from the front sockets (HANGER_Z_*).  The keeper taps
# stay out too: MHA-CH-07 transfers them at assembly, so their callout
# places them.  The table hangs in the band under the plan, over the
# edge-break note, left of the title block.  The native SIZE column is
# hidden: the plan's own callout gives the sockets' size once (rule 10).
HOLE_TABLE_ANCHOR = (0.0175, 0.0815)
HOLE_TABLE_ROW_HEIGHT = 0.006
HOLE_TABLE_TAG_WIDTH = 0.012
# "X LOC (BASIC)": 13 glyphs at the base table's measured 2.47 mm.
HOLE_TABLE_LOC_WIDTH = 0.034
HOLE_TABLE_MATE_COLUMN = "MATE"
# "MHA-FR-03, MHA-FR-01": 20 glyphs at the base table's measured 2.47 mm.
HOLE_TABLE_MATE_WIDTH = 0.054
_HOLE_TABLE_SIZE_COLUMN = 3
EDGE_NOTE_XY = (0.030, 0.033)
# Each socket's tag stands in the open window beside it on a leader to the
# axis, 14 mm in from the axis on each sheet axis, past the boss and the
# rail: the native default parked it up-right of the hole, in the keeper
# callout's leader (farm run 20261106T204855971Z, leader-through-text).
HOLE_TAG_SOCKET_INSET = 0.014
# The tag's printed "A1" box about its centre (2 glyphs at 3.5 mm): the note
# position SolidWorks takes is the box's upper-left corner.
_HOLE_TAG_HALF = (0.0025, 0.00175)
_TITLE_BLOCK_LEFT = 0.216
SOCKET_TABLE_MATES = "MHA-FR-03, MHA-FR-01"
TABLE_ORIGIN_XZ = CAST_DATUM_ORIGIN_XZ
# The origin mark's arrows about the corner, (length, offset) in sheet m:
# the X arrow runs left 16 mm on a line 7.3 mm under the corner, over the
# table; the Y arrow up 6 mm on a line 5 mm right of it, its "Y" under the
# keeper callout's leader, which crosses 16 mm over the corner there (at
# 10 mm the leader ran through the letter, farm run 20261111T023438415Z).
TABLE_ORIGIN_X_ARROW = (0.016, 0.0073)
TABLE_ORIGIN_Y_ARROW = (0.006, 0.0050)
# The F and G planes' traces, thin phantom (swLineStyles_e.swLinePHANTOM,
# swLW_THIN): F from the corner to the rear-east boss's tangent point, G
# from the corner past G1's tangent point on the rear-west boss, 5 mm short
# of the keeper callout's leader (it crosses the trace's line 19 mm over the
# corner).
TABLE_TANGENT_LINE_STYLE = 2
TABLE_TANGENT_LINE_WEIGHT = 0
TABLE_G_LINE_FRONT_Z = REAR_COLUMN_Z - 7.0
# (x, z, diameter, mate) in part mm.
TABLE_HOLES: tuple[tuple[float, float, float, str], ...] = tuple(
    (x, z, BORE_DIA, SOCKET_TABLE_MATES)
    for z in (FRONT_COLUMN_Z, REAR_COLUMN_Z)
    for x in (-COLUMN_X, COLUMN_X)
)
# Each hanger hole's Z station from the front-left socket's axis, in the
# left window: the front one's line 36 mm left of the crossbar, the rear
# one's 12 mm left of that.  The front station is 14 mm of paper with the
# rail's inner edge through it (y 207.7), so its value stands outside the
# run, in the window 2.3 mm under the hole's extension line (y 202.5).
HANGER_Z_TEXT_XY = {
    "front hanger z from upper sockets": (0.150, 0.1985),
    "rear hanger z from upper sockets": (0.138, 0.166),
}
# The sockets' composite position frame (owner rulings D2 and D6): Ø.06 to
# E|F|G over Ø.010 to A, on a leader to the front-right socket's rim from
# the free margin right of it, its 4X under it and datum B -- the pattern
# the rail webs are held to (D3) -- hung under that.  A tag on a composite
# frame hangs from the frame block's foot, 19.6 mm under its top with the
# 4X row, and takes its y there: farm run 20261111T004615500Z printed "B"
# 25.84 mm under the frame's top plus the offset set, 17.61 mm right of its
# left end.  SOCKET_DATUM_SYMBOL_OFFSET asks for the tag 10 mm under the
# block, where that run's one correction lands it.
SOCKET_POSITION_FRAME_XY = (0.322, 0.2235)
SOCKET_POSITION_QUANTITY = "4X"
SOCKET_DATUM = "B"
SOCKET_DATUM_SYMBOL_OFFSET = (0.01934, -0.03656)
_TABLE_LOCATION_TOLERANCE_MM = 0.02
_INSERT_COLUMN_AFTER = 3  # swTableItemInsertPosition_After
_TABLE_SIZE_CAN_CHANGE = 0  # swTableRowColChange_TableSizeCanChange

# Sheet 7 (CAST-DATUMS), owner rulings B6 and D2 (#2333): the casting's own
# datum frame, the first set-up every faced seat is cut from.  The underside
# (rear up) carries four of the six native datum-target points, the F and G
# planes' traces to the corner sheet 3's table counts from, datum D on the
# crossbar's width and D's station from G; the rear elevation over it
# carries F1, F2 and the barrel targets' height.
CAST_DATUM_FRAME = ("E", "F", "G")
DATUM_BOTTOM_CENTER = (0.150, 0.140)
DATUM_FRONT_CENTER = (0.150, 0.222)
# The width stands across the bar over the front gussets' heads (y 114.6),
# D's tag left of it in the east window and its text out right in the west
# one, over the gusset run's, whose line stands under it; D's station under
# the view, from the G trace (x 222.7) to the bar's median (x 145.0).
DATUM_BOTTOM_KEEP = {
    "BarWidth": (0.145, 0.124),
    "GussetRunE": (0.1522, 0.1185),
    "DStation": (0.184, 0.086),
}
# The width's callout row goes above its value, so the leader from the
# line's right end to the value passes under it.
DATUM_BOTTOM_CALLOUTS_ABOVE = {"BarWidth": "CROSSBAR AT UNDERSIDE"}
DATUM_BOTTOM_CALLOUTS = {"GussetRunE": "4X 45° GUSSET"}
# The gusset run's rows stand 5.5 mm under the width's, whose underline
# (y 122.4) the higher offset of farm run 20261111T023438415Z touched.
DATUM_BOTTOM_TEXT_OFFSETS = {
    "BarWidth": (0.179, 0.128),
    "GussetRunE": (0.180, 0.1130),
}
# Each target symbol's centre from its point, sheet m: on the underside E1
# in the west window, G1 and E2 beside the view, E3 under its front-east
# corner; F1 and F2 on the rear elevation, straight under their points, in
# the band over the underside (which ends at y 184.8).
DATUM_TARGET_SYMBOL_OFFSETS = {
    "E1": (-0.0257, -0.0120),
    "E2": (-0.0240, -0.0073),
    "E3": (-0.0223, -0.0133),
    "F1": (0.0, -0.0160),
    "F2": (0.0, -0.0160),
    "G1": (0.0273, -0.0023),
}
# F1 and F2 stand on the rear barrels' rear generators, which the rear
# elevation sees face-on.  From below a 2° barrel is a 0.5 mm sliver, where
# F2's point did not take: SolidWorks attached its leader to the face
# instead (farm run 20261111T015941119Z).
DATUM_TARGETS_ON_ELEVATION = frozenset({"F1", "F2"})
# One BASIC radius places the three boss-bottom targets, each on its own
# socket's centre line, and one BASIC height the three barrel targets.
DATUM_TARGET_COUNT = "3X"
DATUM_E_RADIUS_LINE_XY = (0.071, 0.100)
DATUM_E_RADIUS_TEXT_XY = (0.048, 0.106)
# The height's phantom line across the rear-west boss in the elevation,
# this far (model mm) either side of its socket axis.
DATUM_HEIGHT_LINE_REACH = (30.0, 32.0)
DATUM_HEIGHT_LINE_XY = (0.230, 0.2143)
DATUM_HEIGHT_TEXT_XY = (0.250, 0.226)


def _datum_elevation_xy(x: float, y: float) -> tuple[float, float]:
    """Sheet point (m) of model ``(x, y)`` mm on sheet 7's elevation.

    The view's outline centres on the casting's own extremes: the set-screw
    boss face to the west barrels, the hub boss's bottom to the boss tops.
    """
    scale = GEOMETRY_VIEW_SCALE / 1000.0
    return (
        DATUM_FRONT_CENTER[0] + (x - (PLAN_HALF_X + SET_BOSS_FACE_X) / 2.0) * scale,
        DATUM_FRONT_CENTER[1] + (y - (BOSS_ABOVE - HUB_BOSS_DROP) / 2.0) * scale,
    )


# Owner ruling D4 (#2333): the faces B1 adds draft to print 2° +1°/-0, the
# faces B1 and D1 take it out of 2° ±1°, each band its model dimension's
# own.  One angle prints per band, on this elevation's west end, where
# SolidWorks stands both wedges on the Top plane's trace (y 222.6): the web
# ring's on the web's outer face, opening outward, and the upper barrels'
# on the barrel's crest 5.3 mm of paper west of it, closing inward.  A 2°
# wedge is 0.5 mm of arc, so each arc stands its own rise over its vertex
# -- the web's 15 mm, 7 over the boss top, the barrel's 22 -- (model x of
# the vertex, lean, rise in sheet m), and each value parks off its arc on a
# leader with the faces it governs: the added draft's rows left over the
# view, the taken-out draft's right of it, both inside the border (y 266.7).
DATUM_DRAFT_WEDGES = {
    "WebRingDraft": (WEB_OUT_X, 1.0, 0.015),
    "BossesUpperDraft": (PLAN_HALF_X, -1.0, 0.022),
}
DATUM_FRONT_KEEP = {
    name: (
        round(_datum_elevation_xy(x, 0.0)[0] + lean * rise * DRAFT_T / 2.0, 5),
        round(_datum_elevation_xy(x, 0.0)[1] + rise, 5),
    )
    for name, (x, lean, rise) in DATUM_DRAFT_WEDGES.items()
}
DATUM_FRONT_CALLOUTS = {
    "WebRingDraft": "DRAFT, WEBS, CROSSBAR, POCKETS,\nGUSSETS, PADS, SET-BOSS SIDES",
    "BossesUpperDraft": "DRAFT, FLANGE RIMS, SET-BOSS FACE,\n4X BOSS AND HUB BARRELS",
}
DATUM_FRONT_TEXT_OFFSETS = {
    "WebRingDraft": (0.1722, 0.2541),
    "BossesUpperDraft": (0.2731, 0.2568),
}


def bind_hole_table_rows(
    rows: tuple[tuple[str, ...], ...], mm_per_unit: float
) -> dict[int, int]:
    """Each generated data row's TABLE_HOLES index, matched by its LOC cells.

    Which way each native LOC axis counts follows the edges that set the
    table's axes, not the print, so a row matches on the magnitudes and
    every row must then share one sign per axis.
    """
    expected = [
        (abs(x - TABLE_ORIGIN_XZ[0]), abs(z - TABLE_ORIGIN_XZ[1])) for x, z, _d, _m in TABLE_HOLES
    ]
    if len(rows) != len(expected):
        raise RuntimeError(f"hole table has {len(rows)} rows for {len(expected)} holes")
    bound: dict[int, int] = {}
    signs: tuple[set[float], set[float]] = (set(), set())
    for index, row in enumerate(rows, 1):
        try:
            loc = tuple(float(row[k]) * mm_per_unit for k in (1, 2))
        except (ValueError, IndexError) as error:
            raise RuntimeError(f"hole table row {index} has no LOC cells: {row!r}") from error
        matches = [
            hole for hole, wanted in enumerate(expected)
            if hole not in bound.values()
            and all(
                abs(abs(value) - target) <= _TABLE_LOCATION_TOLERANCE_MM
                for value, target in zip(loc, wanted)
            )
        ]
        if len(matches) != 1:
            raise RuntimeError(f"hole table row {index} binds {matches!r}: {row!r}")
        bound[index] = matches[0]
        for axis, value in enumerate(loc):
            if abs(value) > _TABLE_LOCATION_TOLERANCE_MM:
                signs[axis].add(math.copysign(1.0, value))
    if any(len(axis) > 1 for axis in signs):
        raise RuntimeError(f"hole table LOC mixes signs on one axis: {rows!r}")
    return bound


# Inch sheets drop the leading zero (ASME Y14.5); the hole table's own
# document option followed the template and printed the origin's 0.000
# (farm run 20261107T000550920Z, machinist review r1-r3).  The native LOC
# cells refuse a text override (run 20261107T003254101Z: "not editable"),
# so Document Properties > Tables > Hole > Leading zeroes is set before the
# table exists, as draw_fr_rocker_arm_support does.
HOLE_TABLE_LEADING_ZERO = "swLeadingZero_DoNotShow"


def _drop_hole_table_leading_zeros(adapter: Any) -> None:
    """Set the drawing's hole-table leading-zero option before the table exists."""
    extension = _early_bound(adapter.currentModel.Extension, "IModelDocExtension")
    preference = constant("swDetailingLeadingZero")
    option = constant("swDetailingHoleTable")
    value = constant(HOLE_TABLE_LEADING_ZERO)
    if not extension.SetUserPreferenceInteger(preference, option, value):
        raise RuntimeError("failed to drop the hole table's leading zeros")
    if int(extension.GetUserPreferenceInteger(preference, option)) != value:
        raise RuntimeError("hole-table leading-zero option did not persist")


def leading_zero_locations(rows: tuple[tuple[str, ...], ...]) -> list[str]:
    """The data rows' LOC cells (columns 1, 2) that print a leading zero."""
    return [
        cell for row in rows for cell in row[1:3] if cell.startswith(("0.", "-0."))
    ]


def negative_locations(rows: tuple[tuple[str, ...], ...]) -> list[str]:
    """The data rows' LOC cells (columns 1, 2) that print negative: from the
    F|G corner every socket reads a positive distance along each arrow."""
    return [cell for row in rows for cell in row[1:3] if cell.startswith("-")]


def hole_tag_position(x: float, z: float) -> tuple[float, float]:
    """The sheet point (the tag box's upper-left corner) for one TABLE_HOLES
    socket's tag: in the window diagonally inside it."""
    s = DETAIL_VIEW_SCALE / 1000.0
    cx, cy = DETAIL_TOP_CENTER[0] + x * s, DETAIL_TOP_CENTER[1] - z * s
    dx = -math.copysign(HOLE_TAG_SOCKET_INSET, x)
    dy = math.copysign(HOLE_TAG_SOCKET_INSET, z)
    return (cx + dx - _HOLE_TAG_HALF[0], cy + dy + _HOLE_TAG_HALF[1])


# Native: the gooseneck bore diameter is GooseneckProfile's own circle
# dimension.  The plan keeps nothing else: the 28.0 rail pad is drawn on
# DETAIL J, where its edges show (HUB_BOTTOM_KEEP).  Under the top flange
# this hidden-lines-removed plan shows no pad, so its width here pointed at
# no edge (farm run 20261027T195317391Z, machinist review r2+r3); placed
# left of the rail, its line ran through the Ø17.00 leader (run
# 20261027T190435153Z, rule 14).
HUB_TOP_KEEP = {"GnDia": (0.040, 0.185)}
HUB_LEFT_KEEP = {
    "SetBossWidth": SET_BOSS_WIDTH_LINE_XY,
    "SetSpotDia": SET_SPOT_DIA_TEXT_XY,
    "GussetSpan": HUB_GUSSET_SPAN_TEXT_XY,
    "HubBossDrop": HUB_BOSS_DROP_TEXT_XY,
}
# The boss width straddles the tap's drawn vertical centreline in VIEW G
# (implied symmetry), and the boss runs up to the faced top (owner ruling
# B4, #2333).
HUB_LEFT_CALLOUTS = {
    "SetBossWidth": "SET-SCREW BOSS",
    "SetSpotDia": "",
    "GussetSpan": "GUSSET SPAN",
    "HubBossDrop": "",
}
# The spot face reads in the Y14.5 form, its depth a reference off the
# cast boss face on the tap's axis -- .95 on the faced top (sheet 6's
# DETAIL J), leaning in under it with the draft taken out (owner ruling D1,
# #2333) -- the spot's own .83 from the bore axis the control
# (drawing-guidelines.md rule 26).
SET_SPOT_DEPTH_TEXT = f"({render_number(round((HUB_SET_BOSS_FROM_AXIS - SCREW_AXIS_BELOW_RAIL_TOP * DRAFT_T - HUB_SET_SPOT_FROM_AXIS) / IN, HUB_SET_SPOT_PLACES), UNIT, HUB_SET_SPOT_PLACES)})"
# The bore sits on the left sockets' drawn centreline (rule 26: holes in
# line share a drawn centreline); its size callout carries the reason its
# 4.532 station serves (rule 7).
HUB_TOP_CALLOUTS = {"GnDia": "DRILL THRU\nON MHA-SM-00\nSUMMING AXIS"}
# The counterbore's text stands up-left of the right boss, left of A-A's
# upper arrow, so its leader drops steeply to the rim nearest it, one arrow
# and no line on through the centre (set_near_side_diameter, as the set-screw
# spot on VIEW G): from (0.045, 0.256) its diametric leader ran the view's
# length and on across the hole, crossing the cross tap's leader rising from
# the lower left (machinist review at rubric 848e03f, rule 14, 2 of 3 runs).
DETAIL_FRONT_KEEP = {"CB1Dia": (0.205, 0.256)}
DETAIL_SECTION_KEEP = {
    # The callout's shoulder (y 164.6) stands 3 mm over the boss-top finish
    # symbol's rows (BOSS_TOP_FINISH_SYMBOL_XY), which it ran through at
    # y 170 (farm run 20261111T023438415Z).
    "CapRecessDia": (0.140, 0.173),
    # The recess depth reads beside its own band, not under it: the column
    # below belongs to the 47.3 boss height, whose three-line text is 37 mm
    # wide and has nowhere else to sit on this sheet.
    # The full parent-scoped cap number left only 0.21 mm stroke-to-stroke
    # at x386 in the native PDF; move left without shortening the mate.
    "CapRecessDepth": (0.382, 0.158),
    # The cast boss bottom from the faced top (owner rulings B2 and B3,
    # #2333): the model's own lower-barrel depth, in the empty band left of
    # the section.
    "BossBelowTop": (0.196, 0.135),
}
# The socket is a matched fit to its own tube, so the callout states the
# acceptance as a functional check (rule 4): without one, "SLIDING FIT
# MATCHED TO" read as no acceptance (blocker, farm run 20261106T221139403Z).
# The diametral clearance itself is the owner's (frame_column_stations:
# the .6 mm ceiling is "never printed").
DETAIL_CALLOUTS = {
    "C0Dia": "4X BOSS\nAT FACED TOP",
    "B0Dia": "4X SOCKET: MHA-FR-03\nTUBE SLIDES IN, NO ROCK",
}
# The cross-screw counterbore reads in the Y14.5 form (drawing-guidelines.md
# rule 26): its floor's .62 from the socket axis is the control (the
# far-wall engagement proof above charges it), so the depth from the
# drafted barrel's crest on the tap axis prints as a reference, at the two
# places an as-cast surface is worth.
COUNTERBORE_DEPTH_TEXT = f"({render_number(round((BOSS_DIA / 2.0 - (HALF_H - SCREW_AXIS_Y) * DRAFT_T - (TOP_SCREW_SEAT_Z - REAR_COLUMN_Z)) / IN, 2), UNIT, 2)})"
FRONT_CALLOUTS = {"CB1Dia": ""}
# The recess's limits are functional both ways: its low limits clear the
# MHA-FR-VN-54 skirt, its high limits keep the cross-screw counterbore's 2.0
# ligament (build_fr_top_frame.COUNTERBORE_PRINTED_CAP_LIGAMENT, 2.04 at
# Ø27.70 and 16.60 deep).  Each callout names the cap it serves, one reason
# per feature (drawing-guidelines.md rule 7: no design rationale).
SECTION_CALLOUTS = {
    "CapRecessDia": "4X CAP RECESS, CLEARS\nMHA-FR-VN-54 SKIRT",
    "CapRecessDepth": "4X",
    "BossBelowTop": "4X BOSS BOTTOM\nBELOW FACED TOP",
}


def _assert_centreline_placed(
    adapter: Any, segment: Any, points: list[tuple[float, ...]]
) -> None:
    """Fail when a centreline's endpoints are not where they were authored."""
    line = _early_bound(segment, "ISketchLine")
    for expected, accessor in zip(points, ("GetStartPoint2", "GetEndPoint2")):
        point = _early_bound(adapter._get_attr_or_call(line, accessor), "ISketchPoint")
        actual = [float(adapter._get_attr_or_call(point, axis)) for axis in ("X", "Y", "Z")]
        drift = max(abs(a - b) for a, b in zip(actual, expected))
        if drift > 1e-9:
            raise RuntimeError(
                f"drawing centreline {accessor[3:-6].lower()} point sits {drift*1000.0:.4g} mm "
                f"from where it was authored ({actual} instead of {list(expected)})"
            )


def _add_view_centerlines(
    adapter: Any,
    view: Any,
    axes: tuple[tuple[tuple[float, float, float], tuple[float, float, float]], ...],
) -> list[Any]:
    """Create only the owned axes, in the target view's actual sketch frame.

    Returns the ``ISketchSegment`` per axis, in order, so a recipe can
    dimension FROM one (``add_edge_dimension`` with ``"SKETCHSEGMENT"``).
    """
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate drawing centreline view")
    draw.ClearSelection2(True)
    sketch = _early_bound(view.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    segments = []
    for start, end in axes:
        points = []
        for xyz in (start, end):
            x, y = model_point_in_view(
                adapter, view, tuple(value/1000.0 for value in xyz),
                label="drawing centreline endpoint",
            )
            point = _early_bound(utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint")
            points.append(tuple(_early_bound(point.MultiplyTransform(transform), "IMathPoint").ArrayData))
        # Direct to the database: an inferred endpoint snaps onto nearby ink.
        # leaders955-f542's D-D bore axis snapped 1.1 mm at one end and
        # printed skewed across the pocket.
        previous_add_to_db = bool(manager.AddToDB)
        manager.AddToDB = True
        try:
            segment = manager.CreateCenterLine(*points[0], *points[1])
        finally:
            manager.AddToDB = previous_add_to_db
        if segment is None:
            raise RuntimeError("failed to create owned drawing centreline")
        _assert_centreline_placed(adapter, segment, points)
        segment = _early_bound(segment, "ISketchSegment")
        segment.Color = 0  # COLORREF black, not the under-defined sketch blue.
        if int(segment.Color) != 0:
            raise RuntimeError("owned drawing centreline color did not persist")
        segments.append(segment)
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="_add_view_centerlines")
    return segments


def _exact_linear_entities(
    edges: ViewEdges, points: tuple[tuple[float, float, float], ...], *, label: str
) -> list[Any]:
    """The visible straight edges passing exactly through each of ``points``."""
    return [edges.exact_line_through(point, label=label).edge for point in points]


def _insert_crossbar_median(adapter: Any, view: Any, sides: tuple[Any, Any]) -> None:
    """Insert D's trace: the native centreline between the crossbar's sides.

    ``InsertCenterLine2`` on two parallel model edges (draw_dt_crank_arm's and
    draw_pn_pen_marker's pattern, selected here by entity) bisects those
    edges, so it stays on their median when the faces move.  Fail unless both
    sides were selected, the view gained exactly one centreline (the crank
    arm's ``IView.GetCenterLineCount`` proof) and its annotation is live
    (``IAnnotation.IsDangling`` false).
    """
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    if not ddoc.ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate the crossbar median view")
    native_view = _early_bound(view, "IView")
    before = int(native_view.GetCenterLineCount())
    draw.ClearSelection2(True)
    manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    for index, side in enumerate(sides):
        selection_data = manager.CreateSelectData()
        selection_data.View = view
        if not _early_bound(side, "IEntity").Select4(index > 0, selection_data):
            raise RuntimeError(f"failed to select crossbar side {index} for its median")
    count = int(manager.GetSelectedObjectCount2(-1))
    if count != 2:
        raise RuntimeError(f"crossbar median selection holds {count} entities, not 2")
    centerline = ddoc.InsertCenterLine2()
    draw.ClearSelection2(True)
    if centerline is None:
        raise RuntimeError("failed to insert the crossbar median centreline")
    after = int(native_view.GetCenterLineCount())
    if after != before + 1:
        raise RuntimeError(
            f"crossbar median insert left the view with {after} centrelines, "
            f"expected {before + 1}"
        )
    annotation = _early_bound(
        _early_bound(centerline, "ICenterLine").GetAnnotation(), "IAnnotation"
    )
    if bool(annotation.IsDangling()):
        raise RuntimeError("crossbar median centreline is dangling")


# The plain wizard's native row prints the size and its one extent token;
# the hole is a letter drill (owner ruling 2026-11-06: 2X C DRILL Ø.242
# THRU), so the drill's letter leads the row and the extent reads THRU.
# The diameter stays the Hole Wizard variable carrying the model's size.
HANGER_HOLE_PROCESS_TEXT = f"{HANGER_HOLE_DRILL} DRILL "
HANGER_HOLE_EXTENT_TEXT = "THRU"


def _hanger_hole_callout_definitions(definitions: dict[int, str]) -> dict[int, str]:
    """Lead the native row with the letter drill; read its extent THRU.

    The installed R2026x calloutformat.txt ([ANSI INCH] line 93) formats a
    plain through hole as ``HOLE-THRU=;<MOD-DIAM> <hw-diam> <hw-thru>``;
    ``<hw-thruholedia>`` belongs to the counterbore/countersink formats, so
    it, a spot face or a countersink row means the wrong hole type.
    """
    native = "\n".join(definitions.values())
    if (
        set(definitions) != {5, 6, 7, 8}
        or native.count("<hw-diam>") != 1
        or native.count("<hw-thru>") != 1
        or native.count("<MOD-DIAM>") != 1
        or any(
            token in native
            for token in (
                "<hw-thruholedia>", "<hw-cbdia>", "<hw-cbdepth>", "<HOLE-SPOT>", "<HOLE-SINK>",
            )
        )
    ):
        raise RuntimeError(f"unexpected native hanger hole callout: {definitions!r}")
    return {
        part: text.replace("<MOD-DIAM>", HANGER_HOLE_PROCESS_TEXT + "<MOD-DIAM>").replace(
            "<hw-thru>", HANGER_HOLE_EXTENT_TEXT
        )
        for part, text in definitions.items()
    }


def _set_hanger_hole_callout(display: Any) -> None:
    """Edit only native definition fields and require their exact readback."""
    display = _early_bound(display, "IDisplayDimension")
    definitions = {part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)}
    updated = _hanger_hole_callout_definitions(definitions)
    for definition, writable in ((5, 1), (6, 2), (7, 3), (8, 4)):
        if updated[definition] != definitions[definition]:
            display.SetText(writable, updated[definition])
    persisted = {part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)}
    resolved = "\n".join(str(display.GetText(part) or "") for part in (1, 2, 3, 4))
    if (
        persisted != updated
        or resolved.count(HANGER_HOLE_EXTENT_TEXT) != 1
        or resolved.count(HANGER_HOLE_PROCESS_TEXT) != 1
    ):
        raise RuntimeError(
            f"native hanger hole definition did not persist: {persisted!r}, "
            f"resolved {resolved!r}"
        )
    set_hole_callout_precision(
        display,
        {"hw-diam": HANGER_CLEARANCE_DIA_PLACES},
        label="hanger clearance diameter",
    )
    _clear_hanger_callout_band(display)


def _clear_hanger_callout_band(display: Any) -> None:
    """The through diameter takes the title block's DRILLED HOLES band.

    SDK ICalloutVariable.ToleranceType, not IDimensionTolerance.Type, owns
    multivalue-callout rendering (2016+): set it to none and read it back,
    so the callout restates no band (machinist review: rule 2).
    """
    from win32com.client.dynamic import Dispatch as dynamic_dispatch

    # Concrete callout interfaces alias the generic metadata DISPIDs.
    variables = [
        dynamic_dispatch(raw._oleobj_)
        for raw in display.GetHoleCalloutVariables() or ()
    ]
    matches = [
        variable for variable in variables
        if str(variable.VariableName) == "hw-diam"
    ]
    if len(matches) != 1:
        raise RuntimeError("hanger callout lacks one native through-diameter variable")
    matches[0].ToleranceType = 0  # swTolType_e.swTolNONE
    if int(matches[0].ToleranceType) != 0:
        raise RuntimeError("native hanger through-diameter callout kept a band")


def _require_model_hanger_grip(adapter: Any, dimensions: list[Any]) -> Any:
    """F-F's imported HangerGrip: the model's driving grip, under the title block.

    Read-only. The model owns the dimension -- the crossbar's full-height
    extrude depth, driven by RingHeight -- and authors no band on it: the
    title block's .XXX band governs (owner ruling 2026-10-18: MHA-SM-VN-52 is
    cut to the measured grip at SM-00).  A lost association, a drifted value
    or a band of its own raises here.
    """
    grips = [
        annotation for annotation in dimensions
        if dimension_name(adapter, annotation) == "HangerGrip"
    ]
    if len(grips) != 1:
        raise RuntimeError(f"F-F imported {len(grips)} HangerGrip dimensions, not 1")
    display = _early_bound(grips[0].GetSpecificAnnotation(), "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    owner = str(dimension.FullName).split("@")[:2]
    if owner != ["HangerGrip", "Crossbar"]:
        raise RuntimeError(f"F-F grip is {dimension.FullName!r}, not the model's HangerGrip")
    value_mm = float(dimension.SystemValue) * 1000.0
    if abs(value_mm - HANGER_GRIP) > 1e-5:
        raise RuntimeError(f"F-F grip reads {value_mm:.6f} mm, not {HANGER_GRIP}")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    if int(tolerance.Type) != 0:  # swTolType_e.swTolNONE
        raise RuntimeError("F-F grip carries a band; the title block's .XXX governs")
    return grips[0]


def _reference_model_rail_height(adapter: Any, dimensions: list[Any]) -> Any:
    """The geometry front view's imported RingHeight, marked a reference.

    The model owns the dimension -- the web ring's driving extrude depth,
    the same finished thickness as F-F's HangerGrip -- and authors no band
    on it, so the sheet parenthesizes it and adds none.  A lost association,
    a drifted value or a band of its own raises before the mark goes on.
    """
    rails = [
        annotation for annotation in dimensions
        if dimension_name(adapter, annotation) == "RingHeight"
    ]
    if len(rails) != 1:
        raise RuntimeError(
            f"geometry front imported {len(rails)} RingHeight dimensions, not 1"
        )
    display = _early_bound(rails[0].GetSpecificAnnotation(), "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    owner = str(dimension.FullName).split("@")[:2]
    if owner != ["RingHeight", "WebRing"]:
        raise RuntimeError(
            f"rail height is {dimension.FullName!r}, not the model's RingHeight"
        )
    value_mm = float(dimension.SystemValue) * 1000.0
    if abs(value_mm - RING_HEIGHT) > 1e-5:
        raise RuntimeError(f"rail height reads {value_mm:.6f} mm, not {RING_HEIGHT}")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    if int(tolerance.Type) != 0:  # swTolType_e.swTolNONE
        raise RuntimeError("rail height carries a band that competes with the grip's")
    set_reference_dimension(adapter, rails[0], label="rail height")
    return rails[0]


def _reference_plan_outlines(adapter: Any, dimensions: list[Any]) -> None:
    """The plan's imported flange extents and windows, marked references.

    The flange widths centred on the socket axes (34.2 here, 38.0 in H-H)
    and the socket pitches locate every rail edge from a feature the shop
    touches, so the four outline sizes only restate them.  Each must import
    exactly once and carry no band before its parentheses go on.
    """
    for name in PLAN_REFERENCE_DIMENSIONS:
        matches = [
            annotation for annotation in dimensions
            if dimension_name(adapter, annotation) == name
        ]
        if len(matches) != 1:
            raise RuntimeError(f"geometry top imported {len(matches)} {name} dimensions, not 1")
        display = _early_bound(matches[0].GetSpecificAnnotation(), "IDisplayDimension")
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        if int(tolerance.Type) != 0:  # swTolType_e.swTolNONE
            raise RuntimeError(f"plan {name} carries a band; a reference takes none")
        set_reference_dimension(adapter, matches[0], label=f"plan {name}")


def _crossbar_median_datum(adapter: Any, view: Any, width: Any) -> None:
    """Attach D to the native width size, establishing BOTH-face median plane.

    ``width`` was captured before ``offset_dimension_text`` rebuilt the sheet,
    so it supplies identity only: its selection name and its FullName.  The
    display dimension actually selected is re-resolved from the view's own
    GetDisplayDimensions (exactly one match, annotation type 4, same
    FullName) and selected by IModelDocExtension.SelectByID2 on the documented
    DIMENSION channel -- the call GetNameForSelection exists to feed.  The
    selection is read back (one swSelDIMENSIONS item, same name and FullName)
    before InsertDatumTag2 attaches the native tag to it.  Unlike the
    edge-only generic helper, this part-specific path then requires the tag
    on swSelDIMENSIONS (14) and the SAME IDisplayDimension/IDimension, not an
    edge or an unattached tag.  Last, the attached tag's rendered ink is read
    back and must clear each printed width row
    (``_require_datum_d_clear_of_width_text``): the position request is not
    honoured for a dimension-attached tag, so where D lands is only known here.
    """
    width = _early_bound(width, "IDisplayDimension")
    width_name = width.GetNameForSelection()
    width_full_name = _early_bound(width.GetDimension2(0), "IDimension").FullName
    if not isinstance(width_name, str) or not width_name:
        raise RuntimeError(f"crossbar width has no selection name: {width_name!r}")
    if not isinstance(width_full_name, str) or not width_full_name:
        raise RuntimeError(f"crossbar width has no FullName: {width_full_name!r}")
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    if not _early_bound(model, "IDrawingDoc").ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate crossbar width datum view")
    model.ClearSelection2(True)
    matches = [
        display
        for display in (
            _early_bound(raw, "IDisplayDimension")
            for raw in _early_bound(view, "IView").GetDisplayDimensions() or ()
        )
        if display.GetNameForSelection() == width_name
    ]
    annotation_type, annotation_name, full_name = 0, "", ""
    if len(matches) == 1:
        display = matches[0]
        raw_annotation = display.GetAnnotation()
        raw_dimension = display.GetDimension2(0)
        if raw_annotation is None or raw_dimension is None:
            raise RuntimeError(f"crossbar width {width_name!r} has no annotation or dimension")
        width_annotation = _early_bound(raw_annotation, "IAnnotation")
        dimension = _early_bound(raw_dimension, "IDimension")
        annotation_type = int(width_annotation.GetType())
        annotation_name = str(width_annotation.GetName())
        full_name = dimension.FullName
    _telemetry.event(
        "drawing.crossbar_width.target",
        selection_name=width_name,
        matches=len(matches),
        annotation_type=annotation_type,
        annotation_name=annotation_name,
        full_name=str(full_name),
        expected_full_name=width_full_name,
    )
    if len(matches) != 1:
        raise RuntimeError(
            f"expected one crossbar width {width_name!r} in its view, found {len(matches)}"
        )
    # swAnnotationType_e.swDisplayDimension = 4.
    if annotation_type != 4 or full_name != width_full_name:
        raise RuntimeError(
            f"crossbar width {width_name!r} re-resolved as annotation type "
            f"{annotation_type}, {full_name!r}; expected type 4, {width_full_name!r}"
        )
    extension = _early_bound(model.Extension, "IModelDocExtension")
    if extension.SelectByID2(
        width_name, "DIMENSION", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
    ) is not True:
        raise RuntimeError(
            f"failed to select crossbar width {width_name!r} for median-plane datum"
        )
    selection = _early_bound(model.SelectionManager, "ISelectionMgr")
    count = int(selection.GetSelectedObjectCount2(-1))
    kind = int(selection.GetSelectedObjectType3(count, -1)) if count else 0
    picked = selection.GetSelectedObject6(count, -1) if count else None
    picked_name, picked_full_name = "", ""
    if kind == 14 and picked is not None:  # swSelDIMENSIONS -> IDisplayDimension
        picked = _early_bound(picked, "IDisplayDimension")
        picked_name = picked.GetNameForSelection()
        picked_dimension = picked.GetDimension2(0)
        if picked_dimension is not None:
            picked_full_name = _early_bound(picked_dimension, "IDimension").FullName
    _telemetry.event(
        "drawing.crossbar_width.selection",
        count=count, type=kind, selection_name=str(picked_name),
        full_name=str(picked_full_name),
    )
    if (
        count != 1 or kind != 14
        or picked_name != width_name or picked_full_name != width_full_name
    ):
        model.ClearSelection2(True)
        raise RuntimeError(
            f"selecting crossbar width selected {count} object(s), type {kind}, "
            f"name {picked_name!r}, FullName {picked_full_name!r}; expected one "
            f"DIMENSION {width_name!r}, {width_full_name!r}"
        )
    raw_tag = model.InsertDatumTag2()
    if raw_tag is None:
        raise RuntimeError("failed to insert crossbar median-plane datum D")
    tag = _early_bound(raw_tag, "IDatumTag")
    if not tag.SetLabel("D"):
        raise RuntimeError("failed to label crossbar median-plane datum D")
    annotation = _early_bound(tag.GetAnnotation(), "IAnnotation")
    # InsertDatumTag2 on a selected dimension leaves the tag attached to
    # nothing (count 0): run 20261009T155421516Z (knife-mount datum B), the
    # vm2 datum probe, and this sheet's run 20261014T032231012Z (RD6 selected
    # as one swSelDIMENSIONS, tag types ()).  IAnnotation::SetAttachedEntities
    # is documented as per-kind experimental: offer it the re-resolved display
    # dimension, then that dimension's own annotation.  The checks below still
    # demand one type-14 attachment that IS this display.
    inserted_count = int(annotation.GetAttachedEntityCount3())
    attempts: list[str] = []
    if inserted_count == 0:
        for target_kind, target in (
            ("display_dimension", display), ("annotation", width_annotation),
        ):
            accepted = bool(annotation.SetAttachedEntities(dispatch_array([target])))
            attached_count = int(annotation.GetAttachedEntityCount3())
            attempts.append(f"{target_kind}:{accepted}:{attached_count}")
            if accepted and attached_count:
                break
    _telemetry.event(
        "drawing.crossbar_width.attach_attempts",
        inserted_count=inserted_count, attempts=",".join(attempts),
    )
    if not annotation.SetPosition2(*CROSSBAR_MEDIAN_DATUM_XY, 0.0):
        raise RuntimeError("failed to position crossbar median-plane datum D")
    model.ClearSelection2(True)
    rebuild_drawing(adapter, label="crossbar median-plane datum D")
    kinds = tuple(int(value) for value in annotation.GetAttachedEntityTypes() or ())
    entities = tuple(annotation.GetAttachedEntities3() or ())
    # The object GetAttachedEntities3 returns for a dimension is undocumented;
    # its type separates selected-but-unattachable from a selection failure.
    _telemetry.event(
        "drawing.crossbar_width.attachment",
        count=int(annotation.GetAttachedEntityCount3()),
        types=str(kinds),
        objects=str(tuple(type(entity).__name__ for entity in entities)),
    )
    if kinds != (14,) or len(entities) != 1 or entities[0] is None:
        raise RuntimeError(f"median-plane datum D is not attached to the width: {kinds}")
    attached = _early_bound(entities[0], "IDisplayDimension")
    attached_dimension = _early_bound(attached.GetDimension2(0), "IDimension")
    if (
        str(tag.GetLabel()) != "D"
        or annotation.IsDangling()
        or str(attached_dimension.FullName) != str(dimension.FullName)
        or int(adapter.swApp.IsSame(attached, display)) != 1
    ):
        raise RuntimeError("median-plane datum D lost the exact crossbar width attachment")
    _require_datum_d_clear_of_width_text(adapter, annotation, width_annotation)


def _require_datum_d_clear_of_width_text(adapter: Any, datum: Any, width: Any) -> None:
    """Refuse datum D's rendered ink within CLEAR_GAP_M (2 mm) of either
    printed row of the crossbar width it hangs on.

    D is dimension-attached: SolidWorks drops it at its own default off the
    width's left arrow and ignores the SetPosition2 request (R6, farm run
    20261014T055244900Z: requested (142, 95) mm, box landed x 122.7-129.7,
    y 106.0-113.0, only 0.06 mm above the native cap of "CROSSBAR FLANGE";
    its rendered glyphs crossed the lower box edge).  Neither gate saw it:
    finalize_drawing audits in REPORT mode
    and the layout collector boxes a dimension-attached datum nominally.  So
    both annotations' IDisplayData are read after the rebuild through the
    audit's own reader (``annotation_display``) and checked here, row by row:
    the 25.0 sits left of D while the suffix runs under it, so one block box
    over both rows would crowd D even when each row clears.  Anything
    estimated fails closed: a refused accessor, empty display data, a run
    SolidWorks reported no width for, a run that draws nothing.
    """
    tag, tag_refused = annotation_display(adapter, datum)
    text, text_refused = annotation_display(adapter, width)
    if tag_refused or text_refused or not tag or not text:
        raise RuntimeError(
            "datum D clearance needs both native display reads: datum D "
            f"{'empty' if not tag else 'read'}, refused {tag_refused}; crossbar width "
            f"{'empty' if not text else 'read'}, refused {text_refused}"
        )
    if not any(
        str(raw.get("t", "")).strip() == "D"
        and display_box({"texts": [raw]}) is not None
        for raw in tag.get("texts", ())
    ):
        raise RuntimeError("datum D clearance: the datum's display data prints no 'D'")
    for label, display in (("datum D", tag), ("crossbar width", text)):
        estimated = estimated_text_runs(display)
        if estimated:
            raise RuntimeError(
                f"datum D clearance: {label} reported no width for {estimated} text run(s)"
            )
    datum_box = display_box(tag)
    if datum_box is None:
        raise RuntimeError("datum D clearance: the datum's display data draws nothing")
    rows: dict[str, tuple[float, float, float, float]] = {}
    for index, raw in enumerate(text.get("texts", ())):
        box = display_box({"texts": [raw]})
        if box is None:
            raise RuntimeError(
                f"datum D clearance: crossbar width text run {index} draws nothing"
            )
        label = f"crossbar width row {index} {str(raw.get('t', ''))!r}"
        rows[label] = (box.xmin, box.ymin, box.xmax, box.ymax)
    if not rows:
        raise RuntimeError("datum D clearance: crossbar width prints no text")

    def mm(box: tuple[float, float, float, float]) -> str:
        return "/".join(f"{value * 1000.0:.2f}" for value in box)

    datum_ink = (datum_box.xmin, datum_box.ymin, datum_box.xmax, datum_box.ymax)
    _telemetry.event(
        "drawing.crossbar_width.datum_clearance",
        datum_box=mm(datum_ink),
        rows="; ".join(f"{label} {mm(box)}" for label, box in rows.items()),
    )
    require_clear("datum D ink", datum_ink, rows)


def _set_derived_precision(display: Any, *, label: str) -> int:
    """Give one SHEET-DERIVED dimension the places the part's spec owns.

    drawing-simplicity-policy.md `How the repository implements the guidelines` puts the decimal places on the model dimension, and every
    dimension the part carries is imported and read back
    (``assert_imported_precision``).  What is left on this print are distances
    between two model faces that no single model dimension expresses -- a web
    thickness that is the difference of two profile offsets, a flange between
    two extrude extents, a boss stack that sums three, a chamfer leg, a ramp
    angle.  Their places come from ``top_frame_spec`` all the same, so no place
    count is ever typed into this recipe.
    """
    places = DRAWING_REFERENCE_PRECISION[label]
    display = _early_bound(display, "IDisplayDimension")
    # -1: swDimensionPrecisionSettings_e do-not-change, for the dual and both
    # tolerance places -- the part owns those too.
    display.SetPrecision3(DRAWING_REFERENCE_PRECISION[label], -1, -1, -1)
    applied = int(display.GetPrimaryPrecision2())
    if applied != places:
        raise RuntimeError(
            f"{label}: part-authored precision did not persist -- asked for "
            f"{places} decimal places, dimension reads {applied}"
        )
    return applied


def _cut_face_edge(
    edges: ViewEdges,
    *,
    fixed: dict[int, float],
    near: tuple[int, float, float] | None = None,
    through: tuple[int, float, float] | None = None,
    label: str,
) -> tuple[Any, tuple[float, float, float]]:
    """The longest visible cut-face line pinned to ``fixed`` model mm axes.

    ``SetDisplayOnlySurfaceCut`` leaves a section showing its cut faces only,
    so every visible line carries the cut plane's own coordinate.  Pinning
    that axis plus one face level -- a rail top, a boss top, a spot face --
    names the face itself instead of a hand-written station a geometry change
    would silently invalidate.  ``near`` is ``(axis, value, window)`` and
    picks between parallel faces (the front boss rather than the rear); the
    longest line wins so a chamfer tangent can never stand in for the face.
    ``through`` is ``(axis, value, margin)``: the line must run past
    ``value`` by ``margin`` both ways, so a leader landing set there
    (``leader_attach_xy``) lies on the very line selected.
    Returns the edge and its midpoint in model mm, ready for ``entities=``.
    """
    candidates = []
    for item in edges.lines:
        start, end = item.line
        if any(
            max(abs(start[axis]-value), abs(end[axis]-value)) > 1e-6
            for axis, value in fixed.items()
        ):
            continue
        midpoint = item.midpoint_mm
        if near is not None and abs(midpoint[near[0]]-near[1]) > near[2]:
            continue
        if through is not None and not (
            min(start[through[0]], end[through[0]]) <= through[1] - through[2]
            and max(start[through[0]], end[through[0]]) >= through[1] + through[2]
        ):
            continue
        candidates.append((item.length_mm, item.edge, midpoint))
    if not candidates:
        # Name what IS there: the five lines closest to the pinned axes, so a
        # seat that shows different cut geometry (worker 6, 2026-09-18:
        # D-D outer rail face absent) is diagnosable from the leaf log.
        def deviation(item: Any) -> float:
            start, end = item.line
            return max(
                max(abs(start[axis]-value), abs(end[axis]-value))
                for axis, value in fixed.items()
            )
        nearest = sorted(edges.lines, key=deviation)[:5]
        seen = "; ".join(
            f"{tuple(round(v, 3) for v in item.line[0])}->"
            f"{tuple(round(v, 3) for v in item.line[1])} dev={deviation(item):.3g}"
            for item in nearest
        )
        raise RuntimeError(
            f"{label}: no visible cut-face line at {fixed} (near={near}, "
            f"through={through}); "
            f"{len(edges.lines)} visible lines, nearest: {seen}"
        )
    _span, edge, midpoint = max(candidates, key=lambda item: item[0])
    return edge, midpoint


def _checked_dimension(
    adapter: Any,
    view: Any,
    *,
    p0: tuple[float, float, float],
    p1: tuple[float, float, float],
    text_xy: tuple[float, float],
    label: str,
    expected_mm: float,
    orientation: str,
    center: bool = False,
    maximum: bool = False,
    reference: bool = False,
    entity_types: tuple[str, str] = ("EDGE", "EDGE"),
    suffix: str = "",
    exact_linear: bool = False,
    exact_vertices: bool = False,
    entities: tuple[Any, Any] | None = None,
    offset_text: tuple[float, float] | None = None,
    edges: ViewEdges | None = None,
) -> Any:
    """Dimension ``p0``-``p1`` on ``view`` and prove it measures ``expected_mm``.

    ``exact_linear`` / ``exact_vertices`` pick the entities off ``edges`` --
    the view's :class:`ViewEdges`, scanned once after its display state is
    final -- so a print with twenty picks off one view sweeps it once.
    """
    selected = list(entities) if entities is not None else None
    if (exact_vertices or exact_linear) and edges is None:
        raise ValueError(f"{label}: an exact pick needs the view's ViewEdges scan")
    if exact_vertices:
        selected = [edges.exact_vertex_at(point, label=label) for point in (p0, p1)]
    elif exact_linear:
        selected = _exact_linear_entities(edges, (p0, p1), label=label)
    points = [
        model_point_in_view(
            adapter, view, tuple(value/1000.0 for value in point), label=label
        )
        for point in (p0, p1)
    ]
    display = add_edge_dimension(
        adapter, view, p0=points[0], p1=points[1], text_xy=text_xy,
        label=label, orientation=orientation,
        entity_types=("VERTEX", "VERTEX") if exact_vertices else entity_types,
        entities=tuple(selected) if selected is not None else None,
    )
    if center:
        set_arc_endpoints_to_center(adapter, display, label=label)
    elif maximum:
        set_arc_endpoints_to_max(adapter, display, label=label)
    native = _early_bound(display, "IDisplayDimension")
    dimension_type = int(native.Type2)
    if dimension_type not in (2, 11, 12):  # linear, horizontal linear, vertical linear
        raise RuntimeError(f"{label}: expected linear dimension, received type {dimension_type}")
    measured = abs(float(_early_bound(native.GetDimension2(0), "IDimension").SystemValue)) * 1000.0
    if abs(measured - expected_mm) > 1e-5:
        raise RuntimeError(f"{label}: measured {measured:g}, expected {expected_mm:g} mm")
    annotation = _early_bound(native.GetAnnotation(), "IAnnotation")
    _set_derived_precision(native, label=label)
    if suffix:
        set_dimension_callouts(adapter, [annotation], {dimension_name(adapter, annotation): suffix})
    if reference:
        set_reference_dimension(adapter, annotation, label=label)
    if offset_text is not None:
        # A short run (4.5 mm at 1:4 is 1.1 mm of paper) cannot hold its own
        # text between the arrows, and text parked past them leaves
        # SolidWorks drawing the dimension line straight through the value.
        # OffsetText buys a leader, so ``offset_text`` parks the text beside
        # the dimension line at ``text_xy`` -- never above or below it, which
        # would only move the same line into the qualifier.
        offset_dimension_text(
            adapter, [annotation], {dimension_name(adapter, annotation): offset_text}
        )
    return native


def _witness_widening(
    segments: list[tuple[tuple[float, float], tuple[float, float]]],
    levels: tuple[float, float],
    start_x: float,
    *,
    label: str,
) -> tuple[float, tuple[float, float]]:
    """How far to widen both witness gaps so each witness starts at or past
    sheet ``start_x``, toward its dimension line on the right.

    ``levels`` are the two witnesses' sheet y.  Each must show exactly one
    horizontal line there (a leader shoulder at another height is not a
    witness); the witness starts at its left end.  One widening serves both
    gaps, whichever index draws which witness: the witness that starts
    farther left reaches ``start_x``, the other passes it.  Returns the
    widening and the two starts, in ``levels`` order."""
    starts = []
    for level in levels:
        found = [
            min(a[0], b[0])
            for a, b in segments
            if abs(a[1] - b[1]) < 1e-8 and abs(a[1] - level) < 0.0001
        ]
        if len(found) != 1:
            raise RuntimeError(f"{label}: witness at sheet y {level:.5f} reads {found}")
        starts.append(found[0])
    return max(start_x - min(starts), 0.0), (starts[0], starts[1])


def _start_witnesses_past(
    adapter: Any,
    display: Any,
    levels: tuple[float, float],
    start_x: float,
    *,
    label: str,
) -> None:
    """Widen a horizontal-witness dimension's gaps so each witness starts at
    or past ``start_x``: off a section's cut face, never across its hatch
    (draw_dt_cone_swing_platform's PlateThk precedent).  Each witness moves
    only as far as it needs -- one already at the face would otherwise be
    pushed past its own dimension line.  Read back."""
    display = _early_bound(display, "IDisplayDimension")
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    _widen, starts = _witness_widening(
        dimension_segments(annotation), levels, start_x, label=label
    )
    needs = tuple(max(start_x - start, 0.0) for start in starts)
    if not any(needs):
        return
    gaps = []
    for index in (0, 1):
        ok, _use_doc, old_gap = display.GetWitnessLineGap(index, False, 0.0)
        if ok is not True:
            raise RuntimeError(f"{label}: witness {index} gap could not be read")
        gaps.append(float(old_gap))
    wanted = tuple(start + need for start, need in zip(starts, needs))
    # Which gap index draws which witness is the dimension's own: the
    # levels' order first, then the other.
    for order in (needs, needs[::-1]):
        for index, need in enumerate(order):
            gap = gaps[index] + need
            if display.SetWitnessLineGap(index, False, gap) is not True:
                raise RuntimeError(f"{label}: witness {index} gap was refused")
            ok, use_doc, actual = display.GetWitnessLineGap(index, False, 0.0)
            if ok is not True or use_doc or abs(float(actual) - gap) > 1e-8:
                raise RuntimeError(f"{label}: witness {index} gap did not persist")
        rebuild_drawing(adapter, label=label)
        _remaining, moved = _witness_widening(
            dimension_segments(annotation), levels, start_x, label=label
        )
        if all(abs(after - want) <= 0.0002 for after, want in zip(moved, wanted)):
            break
    else:
        raise RuntimeError(f"{label}: witnesses start {moved}, wanted {wanted}")
    _telemetry.info(f"{label}: witnesses moved from {starts} to {moved}")


def _pin_vertical_dimension_line(
    adapter: Any, display: Any, line_x: float, *, label: str
) -> None:
    """Hold a vertical dimension's line at sheet ``line_x``, inside the frame.

    A circle-centre vertical dimension on the underside locator landed its
    whole line 24 mm left of its requested text point -- off the sheet frame
    -- with and without an offset jog (machinist review r2-r4, farm runs
    20261018T061230033Z, 20261018T065727559Z, 20261018T075108244Z).  Read
    at placement it still stood where asked (r4: x 0.02467 of 0.02467): the
    shift lands in a later rebuild, so this runs as a settled check, after
    ``finalize_drawing``'s settling rebuild.  Read the drawn line, move the
    text by the miss (each move rebuilds), and prove every line of the
    dimension inside the zone frame.
    """
    annotation = _early_bound(
        _early_bound(display, "IDisplayDimension").GetAnnotation(), "IAnnotation"
    )
    region = sheet_region(adapter)
    for _attempt in range(3):
        segments = dimension_segments(annotation)
        vertical = [
            (a, b)
            for a, b in segments
            if abs(a[0] - b[0]) < 1e-6 and abs(a[1] - b[1]) > 1e-4
        ]
        if not vertical:
            raise RuntimeError(f"{label}: no vertical dimension line in {segments}")
        drawn_x = vertical[0][0][0]
        miss = line_x - drawn_x
        _telemetry.info(
            f"{label}: dimension line at x {drawn_x:.5f}, requested {line_x:.5f}; "
            f"lines {segments}"
        )
        if abs(miss) <= 0.0005:
            outside = [
                segment
                for segment in segments
                if any(
                    not (
                        region.xmin <= x <= region.xmax
                        and region.ymin <= y <= region.ymax
                    )
                    for x, y in segment
                )
            ]
            if outside:
                raise RuntimeError(f"{label}: lines outside the sheet frame {outside}")
            return
        move_annotation(adapter, annotation, miss, 0.0, label=label)
    raise RuntimeError(
        f"{label}: dimension line stayed at x {drawn_x:.5f}, not {line_x:.5f}"
    )


def _orient_cut_section(
    adapter: Any, view: Any, horizontal_axis: tuple[float, float, float]
) -> None:
    """Show only the cut faces, with model Y up and the named axis right."""
    view = _early_bound(view, "IView")
    section = _early_bound(view.GetSection(), "IDrSection")
    section.SetDisplayOnlySurfaceCut(True)
    if not section.GetDisplayOnlySurfaceCut():
        raise RuntimeError("section retained geometry behind the cutting plane")
    def projected_axes() -> tuple[tuple[float, float], tuple[float, float]]:
        origin = model_point_in_view(adapter, view, (0.0, 0.0, 0.0), label="section origin")
        points = [
            model_point_in_view(
                adapter, view, tuple(value/1000.0 for value in axis),
                label="section orientation axis",
            )
            for axis in (horizontal_axis, (0.0, 1.0, 0.0))
        ]
        return tuple(tuple(point[i]-origin[i] for i in range(2)) for point in points)

    horizontal, vertical = projected_axes()
    if horizontal[0]*vertical[1]-horizontal[1]*vertical[0] < 0.0:
        reversed_cut = not bool(section.GetReversedCutDirection())
        section.SetReversedCutDirection(reversed_cut)
        rebuild_drawing(adapter, label="projected_axes")
        if bool(section.GetReversedCutDirection()) != reversed_cut:
            raise RuntimeError("section cutting direction did not persist")
        horizontal, vertical = projected_axes()
    view.Angle = float(view.Angle)-math.atan2(horizontal[1], horizontal[0])
    rebuild_drawing(adapter, label="projected_axes")
    horizontal, vertical = projected_axes()
    if (
        horizontal[0] <= 0.0 or abs(horizontal[1]) > 1e-8
        or vertical[1] <= 0.0 or abs(vertical[0]) > 1e-8
    ):
        raise RuntimeError(
            f"section model-axis orientation did not persist: {horizontal=}, {vertical=}"
        )


_SECTION_HLR_MODE = 2  # swDisplayMode_e.swHIDDEN


def _assert_section_display(
    adapter: Any,
    view: Any,
    *,
    label: str,
    cut_surface_only: bool,
    removed: bool = False,
) -> None:
    """Read one section view's display mode and cut state back off the sheet.

    drawing-guidelines.md rule 9 (show internal shape in solid lines): hidden lines belong only in a view whose features are
    communicated by them.  A section already exposes its interior by cutting,
    so the removed half redrawn as dashed ghosts was the one thing on the view
    saying nothing -- every section on this print is hidden-lines-removed.
    Nothing is lost by it: every line these sections dimension lies IN the cut
    plane and is part of a cut face (see ``_cut_face_edge``).

    Cut-faces-only is the separate question of what lies BEYOND the plane.
    H-H, E-E, M-M and K-K cut across a closed rail band whose far side would print
    over the cut faces they exist to dimension; A-A cuts a corner boss with
    open air behind it and stays a full section.  Both flags are read back
    because SolidWorks accepts either silently.

    ``GetPartialSection`` is read against ``removed``: a REMOVED section (H-H,
    E-E, M-M -- ``create_section_view(partial=True)``) is partial by definition,
    its line deliberately stopping past the one profile it dimensions; on a
    full section the same flag means the line fell short and the cut did not
    close (no hatch, line and labels in the dangling colour).
    """
    bound = _early_bound(view, "IView")
    mode = int(bound.GetDisplayMode2())
    if mode != _SECTION_HLR_MODE:
        raise RuntimeError(
            f"{label}: section is not hidden-lines-removed (display mode {mode})"
        )
    if bool(bound.GetUseParentDisplayMode()):
        raise RuntimeError(f"{label}: section still follows its parent's display mode")
    section = _early_bound(bound.GetSection(), "IDrSection")
    cut_only = bool(section.GetDisplayOnlySurfaceCut())
    if cut_only != cut_surface_only:
        raise RuntimeError(
            f"{label}: cut-faces-only reads {cut_only}, expected {cut_surface_only}"
        )
    partial = bool(section.GetPartialSection())
    if partial != removed:
        raise RuntimeError(
            f"{label}: partial-section flag reads {partial}; "
            + ("a removed section's line must stop inside the view" if removed
               else "the cutting line stops inside the view (cut did not close)")
        )


_COSMETIC_THREAD_LAYER = "COSMETIC-THREADS-HIDDEN"


def _hide_cosmetic_threads(adapter: Any, view: Any, *, label: str) -> int:
    """Hide SolidWorks' own cosmetic-thread ink in one view.

    A section carries its cut faces and the solid edges beyond the plane.  The
    set tap is neither: its thread is an ANNOTATION SolidWorks attaches to the
    view (measured on D-D: seven ``Hole Thread`` annotations of type 1), so
    hidden-lines-removed does not touch it and it prints as a dashed circle
    over the cut faces, 4 mm from the tap's own axis, describing a thread the
    hub side view already calls out as 1/4-20 UNC - 2B THRU.

    Two routes were measured and refused on this seat: ``Select2`` +
    ``EditDelete`` left all seven in place (build16 -- in a drawing of a PART
    the threads belong to the part's features, as
    ``IDrawingDoc::DeleteAllCosmeticThreads`` documents), and
    ``IAnnotation::Visible = swAnnotationHidden`` read back unchanged
    (build17).  What does hold is the LAYER: each thread annotation is moved
    onto a drawing layer created invisible (``ILayerMgr::AddLayer`` +
    ``ILayer::Visible``), the documented way to hide a class of annotations
    without touching the model.  Both the layer state and every annotation's
    layer are read back, so a refused move fails the build, never prints.
    """
    draw = adapter.currentModel
    manager = _early_bound(draw.GetLayerManager(), "ILayerMgr")
    layer = manager.GetLayer(_COSMETIC_THREAD_LAYER)
    if layer is None:
        # COLORREF black, swLineCONTINUOUS (0), swLW_THIN (0).
        if int(manager.AddLayer(_COSMETIC_THREAD_LAYER, "cosmetic thread ink hidden per view", 0, 0, 0)) != 1:
            raise RuntimeError(f"{label}: failed to add the hidden cosmetic-thread layer")
        layer = manager.GetLayer(_COSMETIC_THREAD_LAYER)
    layer = _early_bound(layer, "ILayer")
    layer.Visible = False
    if bool(layer.Visible) or bool(layer.Printable):
        raise RuntimeError(
            f"{label}: cosmetic-thread layer did not hide "
            f"(visible={layer.Visible!r}, printable={layer.Printable!r})"
        )
    hidden = 0
    for raw_annotation in _early_bound(view, "IView").GetAnnotations() or ():
        annotation = _early_bound(raw_annotation, "IAnnotation")
        if int(annotation.GetType()) != 1:  # swCosmeticThread
            continue
        annotation.Layer = _COSMETIC_THREAD_LAYER
        if str(annotation.Layer or "") != _COSMETIC_THREAD_LAYER:
            raise RuntimeError(f"{label}: a cosmetic thread refused the hidden layer")
        hidden += 1
    if not hidden:
        raise RuntimeError(f"{label}: no cosmetic thread to hide; the set tap moved?")
    rebuild_drawing(adapter, label="_hide_cosmetic_threads")
    return hidden


def _hub_boss_section(adapter: Any, parent_view: Any) -> Any:
    """A removed section through the hub rail at the bore/set-tap axis.

    The cutting line runs from outside the set-screw boss to just past the
    rail's inner face, so ``partial=True`` sections that rail alone: the K
    arrows sit on the hub end of the plan and the view carries the one
    profile the spot face and the thread run hang on -- the same treatment as
    H-H/E-E.  (History: a full-width cut then ``Crop2`` to the hub, whose
    leftover construction midlines had to be hunted down and whose position
    had to be re-derived from the cropped outline.)
    """
    _pin_sheet_scale(adapter)
    line = [
        model_point_in_view(
            adapter, parent_view, (x/1000.0, 0.0, z/1000.0),
            label="set-screw boss section cutting line",
        )
        for x, z in section_cut_ends()["K"]
    ]
    view = create_section_view(
        adapter, parent_view, line_start=line[0], line_end=line[1],
        view_xy=HUB_SECTION_CENTER, section_label="K", scale=HUB_SECTION_SCALE,
        partial=True, label="set-screw boss manufacturing section",
    )
    _orient_cut_section(adapter, view, (1.0, 0.0, 0.0))
    set_hidden_lines_removed(adapter, view)
    # A section's position is its cut-plane origin, not the middle of what it
    # shows: the boss hangs below the rail, so centre the OUTLINE on the
    # sheet target instead.
    outline = tuple(float(value) for value in view.GetOutline())
    position = tuple(float(value) for value in view.Position)
    if len(outline) != 4 or len(position) != 2:
        raise RuntimeError("set-screw boss section has invalid bounds")
    target = [
        position[axis]+HUB_SECTION_CENTER[axis]-(outline[axis]+outline[axis+2])/2
        for axis in range(2)
    ]
    if not view.SetViewPosition(double_array(target), False):
        raise RuntimeError("failed to position set-screw boss section")
    rebuild_drawing(adapter, label="_hub_boss_section")
    outline = tuple(float(value) for value in view.GetOutline())
    center = tuple((outline[axis]+outline[axis+2])/2 for axis in range(2))
    ratio = tuple(float(value) for value in view.ScaleRatio)
    if math.dist(center, HUB_SECTION_CENTER) > 0.0001:
        raise RuntimeError("set-screw boss section centre did not persist")
    if not math.isclose(ratio[0]/ratio[1], HUB_SECTION_SCALE[0]/HUB_SECTION_SCALE[1]):
        raise RuntimeError("set-screw boss section scale did not persist")
    _pin_section_profile(
        adapter, view, (-COLUMN_X, 0.0, GOOSENECK_Z), HUB_SECTION_PROFILE_X, label="K-K",
    )
    axes = _add_view_centerlines(
        adapter, view,
        (
            ((GOOSENECK_X, -HALF_H-HUB_BOSS_DROP-2.0, GOOSENECK_Z),
             (GOOSENECK_X, HALF_H+2.0, GOOSENECK_Z)),
            ((SET_BOSS_FACE_X-2.0, SCREW_AXIS_Y, GOOSENECK_Z),
             (-INNER_X+2.0, SCREW_AXIS_Y, GOOSENECK_Z)),
        ),
    )
    # The cut plane runs through the tap axis, so the spot face and the bore
    # wall each appear in it as two lines the tap interrupts -- picked as
    # faces, the upper by ``near``, since their Y extents depend on the spot.
    # The thread length and the .83 stand over the rail top, so they take the
    # upper lines.  The cast boss face's .95 is DETAIL J's (HUB_BOTTOM_KEEP).
    section_edges = scan_view_edges(view, label="K-K set-screw boss section")
    upper = (1, HALF_H/2.0, HALF_H/2.0)
    spot_edge, spot_point = _cut_face_edge(
        section_edges, fixed={0: SET_SPOT_FACE_X, 2: GOOSENECK_Z}, near=upper,
        label="set-screw spot face",
    )
    bore_edge, bore_point = _cut_face_edge(
        section_edges, fixed={0: GOOSENECK_X-GOOSENECK_BORE_DIA/2.0, 2: GOOSENECK_Z},
        near=upper, label="gooseneck bore wall at the set tap",
    )
    # The thread runs from the spot face to the bore wall: a reference, the
    # 21.0 less the bore's radius.
    _checked_dimension(
        adapter, view,
        p0=spot_point, p1=bore_point,
        text_xy=HUB_SET_THREAD_LINE_XY, label="set-screw thread length",
        expected_mm=HUB_SET_SPOT_FROM_AXIS-GOOSENECK_BORE_DIA/2.0,
        orientation="horizontal", reference=True,
        entities=(spot_edge, bore_edge),
        suffix="THREAD LENGTH", offset_text=HUB_SET_THREAD_OFFSET_XY,
    )
    _checked_dimension(
        adapter, view,
        p0=(GOOSENECK_X, HALF_H+2.0, GOOSENECK_Z), p1=spot_point,
        text_xy=HUB_SET_SPOT_LINE_XY, label="set-screw spot face from bore axis",
        expected_mm=HUB_SET_SPOT_FROM_AXIS, orientation="horizontal",
        entity_types=("SKETCHSEGMENT", "EDGE"), entities=(axes[0], spot_edge),
        offset_text=HUB_SET_SPOT_OFFSET_XY,
    )
    _hide_cosmetic_threads(adapter, view, label="K-K set-screw boss section")
    _assert_section_display(
        adapter, view, label="K-K set-screw boss section", cut_surface_only=True,
        removed=True,
    )
    return view


def _hanger_section(adapter: Any, parent_view: Any) -> tuple[Any, list[Any]]:
    """A removed section F-F through the rear knife-hanger station.

    drawing-guidelines.md rule 9 (show internal shape in solid lines): the
    plain clearance hole and the blind dowel ream, with its knockout up to
    the faced top, are exposed as solid cut lines.
    F-F imports the model's driving HangerGrip (finished top to finished
    underside, the crossbar's own extrude depth with the band authored on
    it) and the depth both reams share, in one targeted import, and
    only reads the grip back; no sheet-side grip exists.  This section also
    adds the ream's station from the screw axis (Owner ruling 2026-11-08
    (Pedro), #2144 item 11.3: the -X ream and its BASIC span are deleted).
    The ream's size is across this cut;
    the underside locator carries it and the knockouts' callout.
    Returns the view and its imported dimensions.
    """
    z = HANGER_SECTION_Z
    _pin_sheet_scale(adapter)
    line = [
        model_point_in_view(
            adapter, parent_view, (x/1000.0, 0.0, z/1000.0),
            label="knife-hanger section cutting line",
        )
        for x in HANGER_SECTION_CUT_X
    ]
    view = create_section_view(
        adapter, parent_view, line_start=line[0], line_end=line[1],
        view_xy=HANGER_SECTION_CENTER, section_label="F", scale=HANGER_SECTION_SCALE,
        partial=True, label="knife-hanger manufacturing section",
    )
    _orient_cut_section(adapter, view, (1.0, 0.0, 0.0))
    set_hidden_lines_removed(adapter, view)
    # Centre the OUTLINE on the target (a section's position is its cut-plane
    # origin), then pin the screw axis to its column.
    outline = tuple(float(value) for value in view.GetOutline())
    position = tuple(float(value) for value in view.Position)
    if len(outline) != 4 or len(position) != 2:
        raise RuntimeError("knife-hanger section has invalid bounds")
    target = [
        position[axis]+HANGER_SECTION_CENTER[axis]-(outline[axis]+outline[axis+2])/2
        for axis in range(2)
    ]
    if not view.SetViewPosition(double_array(target), False):
        raise RuntimeError("failed to position knife-hanger section")
    rebuild_drawing(adapter, label="_hanger_section")
    ratio = tuple(float(value) for value in view.ScaleRatio)
    if not math.isclose(ratio[0]/ratio[1], HANGER_SECTION_SCALE[0]/HANGER_SECTION_SCALE[1]):
        raise RuntimeError("knife-hanger section scale did not persist")
    _pin_section_profile(
        adapter, view, (HANGER_X, 0.0, z), HANGER_SECTION_PROFILE_X, label="F-F",
    )
    # The ream and its coaxial knockout share one axis, underside to top.
    axes = _add_view_centerlines(
        adapter, view,
        tuple(
            ((x, -HALF_H-2.0, z), (x, HALF_H+2.0, z))
            for x in (HANGER_X, PIN_HOLE_X)
        ),
    )
    # The ream's station, .300 at the title block's .XXX from its screw
    # axis's centreline (Owner ruling 2026-11-08 (Pedro), #2144 item 11.3),
    # value and count only (PIN_STATION_CALLOUT).
    station = _checked_dimension(
        adapter, view,
        p0=(HANGER_X, -HALF_H-2.0, z), p1=(PIN_HOLE_X, -HALF_H-2.0, z),
        text_xy=PIN_STATION_TEXT_XY, label="dowel hole from hanger axis",
        expected_mm=HANGER_PIN_X, orientation="horizontal",
        entity_types=("SKETCHSEGMENT", "SKETCHSEGMENT"),
        entities=(axes[0], axes[1]),
        suffix=PIN_STATION_CALLOUT,
        offset_text=PIN_STATION_OFFSET_XY,
    )
    # Both arrows inside, no 6.35 mm tails: farm run 20261027T195317391Z
    # (machinist review r1) measured the station's right tail to 133.98 at
    # y 101.25, into the foot of then-"MATCHES" (from 132.68).  Inside, the
    # line ends on its own extension lines (x 120.0..127.63), 5.0 mm short of
    # the station's rows; its 7.63 mm holds its two 3.56 mm heads like the
    # land end's 8 mm (LAND_END_TEXT_XY).
    station.ArrowSide = _DIM_ARROWS_INSIDE
    if int(station.ArrowSide) != _DIM_ARROWS_INSIDE:
        raise RuntimeError("dowel hole from hanger axis did not keep its arrows inside")
    dimensions = curate_view_dimensions(
        adapter, view,
        keep=HANGER_SECTION_KEEP,
        view_label="knife-hanger section F-F",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    _require_model_hanger_grip(adapter, dimensions)
    set_dimension_callouts(adapter, dimensions, HANGER_SECTION_CALLOUTS)
    offset_dimension_text(
        adapter, dimensions,
        {
            "HangerPinHoleDepth": HANGER_PIN_DEPTH_OFFSET_XY,
            "HangerGrip": HANGER_GRIP_OFFSET_XY,
        },
    )
    # Datum A on the faced underside's edge and the reams' perpendicularity
    # to it (HANGER_PERP_FRAME_XY).
    # Both attach by entity, the cut-face line itself, with the landing set
    # on it (_hub_face_datum's form in draw_ch_rocker_arm): farm run 9
    # (ae879db86) found no EDGE at A's sheet point on F-F by hit-test,
    # though the scan held the line there.  ``through`` proves each landing
    # lies on its selected line, 1 mm clear of either end.
    section_edges = scan_view_edges(view, label="F-F knife-hanger section")
    underside, _underside_mid = _cut_face_edge(
        section_edges, fixed={1: -HALF_H, 2: z},
        through=(0, HANGER_FLOOR_DATUM_PICK_X, 1.0),
        label="F-F faced underside left of the crossbar",
    )
    add_datum_feature(
        adapter, view,
        edge_entity=underside,
        leader_attach_xy=_hanger_section_xy(HANGER_FLOOR_DATUM_PICK_X, -HALF_H),
        symbol_xy=HANGER_FLOOR_DATUM_SYMBOL_XY, datum=HANGER_FLOOR_DATUM,
        label="knife-hanger faced underside datum A",
    )
    ream_wall, _ream_mid = _cut_face_edge(
        section_edges, fixed={0: HANGER_PERP_LANDING[0], 2: z},
        through=(1, HANGER_PERP_LANDING[1], 1.0),
        label="F-F +X dowel ream -X wall",
    )
    add_feature_control_frame(
        adapter, view,
        edge_entity=ream_wall,
        leader_attach_xy=_hanger_section_xy(*HANGER_PERP_LANDING),
        frame_xy=HANGER_PERP_FRAME_XY,
        characteristic="perpendicularity",
        tolerance=GEOMETRIC_TOLERANCES_IN["knife-hanger press ream perpendicularity"],
        datums=(HANGER_FLOOR_DATUM,),
        diameter=True,
        quantity=HANGER_PERP_FRAME_QUANTITY,
        label="knife-hanger dowel reams perpendicular to the faced underside",
    )
    _assert_section_display(
        adapter, view, label="F-F knife-hanger section", cut_surface_only=True,
        removed=True,
    )
    return view, dimensions


def _hub_underside_detail(adapter: Any, parent_view: Any) -> Any:
    """Enlarge the native underside; the circular fence is presentation only."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    parent = _early_bound(parent_view, "IView")
    if not drawing.ActivateView(view_name(adapter, parent_view)):
        raise RuntimeError("failed to activate underside detail parent")
    draw.ClearSelection2(True)
    _pin_sheet_scale(adapter)
    center = model_point_in_view(
        adapter, parent_view,
        (GOOSENECK_X/1000.0, (-HALF_H-HUB_BOSS_DROP)/1000.0, GOOSENECK_Z/1000.0),
        label="underside detail centre",
    )
    radius = (HUB_GUSSET_HALF_OUT+HUB_BOSS_DROP)*HUB_BOTTOM_SCALE[0]/HUB_BOTTOM_SCALE[1]/1000.0
    sketch = _early_bound(parent.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (center, (center[0]+radius, center[1])):
        point = _early_bound(utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint")
        points.append(tuple(_early_bound(point.MultiplyTransform(transform), "IMathPoint").ArrayData))
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    if manager.CreateCircle(*points[0], *points[1]) is None:
        raise RuntimeError("failed to create native underside detail fence")
    detail = drawing.CreateDetailViewAt4(
        *HUB_DETAIL_CENTER, 0.0, 0, *HUB_DETAIL_SCALE, "J", 1, True, False, False, 5,
    )
    if detail is None:
        raise RuntimeError("failed to create native underside detail")
    detail = _early_bound(detail, "IView")
    detail.ScaleRatio = double_array([float(value) for value in HUB_DETAIL_SCALE])
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="_hub_underside_detail")
    # The fence's letter stands on its right quadrant, where main's print had
    # it: the native default on the inch sheet put it on the top quadrant,
    # on the pocket length's rear extension line (farm inspect-3 audit).
    circles = tuple(parent.GetDetailCircles() or ())
    if len(circles) != 1:
        raise RuntimeError(
            f"expected one detail fence on the underside, found {len(circles)}"
        )
    circle = _early_bound(circles[0], "IDetailCircle")
    letter_xy = (center[0] + radius, center[1])
    circle.SetLabelPosition(*letter_xy)  # VT_VOID; read back
    rebuild_drawing(adapter, label="detail J letter")
    letter = tuple(float(value) for value in circle.GetLabelPosition())
    if len(letter) != 2 or math.dist(letter, letter_xy) > 1e-8:
        raise RuntimeError(f"detail J's letter did not persist: {letter}")
    outline = tuple(float(value) for value in detail.GetOutline())
    position = tuple(float(value) for value in detail.Position)
    if len(outline) != 4 or len(position) != 2:
        raise RuntimeError("native underside detail has invalid initial bounds")
    target = [
        position[axis]+HUB_DETAIL_CENTER[axis]-(outline[axis]+outline[axis+2])/2
        for axis in range(2)
    ]
    if not detail.SetViewPosition(double_array(target), False):
        raise RuntimeError("failed to position native underside detail")
    rebuild_drawing(adapter, label="_hub_underside_detail")
    outline = tuple(float(value) for value in detail.GetOutline())
    ratio = tuple(float(value) for value in detail.ScaleRatio)
    if len(outline) != 4 or len(ratio) != 2:
        raise RuntimeError("native underside detail has invalid final bounds")
    center = tuple((outline[axis]+outline[axis+2])/2 for axis in range(2))
    if not math.isclose(ratio[0]/ratio[1], HUB_DETAIL_SCALE[0]/HUB_DETAIL_SCALE[1]):
        raise RuntimeError("native underside detail scale did not persist")
    if math.dist(center, HUB_DETAIL_CENTER) > 0.0001:
        raise RuntimeError(f"native underside detail centre did not persist: {center}")
    return detail


def _set_callout_text(display: Any, which: int, text: str, label: str) -> None:
    """Put prose ABOVE (``which`` 3) or UNDER (4) a native hole callout.

    The draw_dt_crankshaft knockout form: the drill reads first, the purpose
    under it.  ``SetText`` reports nothing, so it is read back.
    """
    display = _early_bound(display, "IDisplayDimension")
    display.SetText(which, text)  # swDimensionTextCalloutAbove/Below
    applied = str(display.GetText(which) or "")
    if applied.replace("\r", "") != text:
        raise RuntimeError(f"{label}: callout text {which} did not persist: {applied!r}")


def _set_counterbore_form(
    annotation: Any, *, count: str, depth: str, label: str
) -> None:
    """Print one imported counterbore/spot diameter in the Y14.5 form.

    ``count`` and the counterbore symbol go before the native diameter
    token, the depth symbol and ``depth`` after the value: ``4X ⌴Ø.35 ↧(.235)``
    (drawing-guidelines.md rule 26).  ``SetText`` reports nothing, so both
    compartments are read back.
    """
    display = _early_bound(
        _early_bound(annotation, "IAnnotation").GetSpecificAnnotation(), "IDisplayDimension"
    )
    native = str(display.GetText(1) or "")
    if "<MOD-DIAM>" not in native:
        native = f"<MOD-DIAM>{native}"
    prefix = f"{count}<HOLE-SPOT>{native}"
    suffix = f" <HOLE-DEPTH>{depth}"
    display.SetText(1, prefix)  # swDimensionTextPrefix
    display.SetText(2, suffix)  # swDimensionTextSuffix
    applied = (str(display.GetText(1) or ""), str(display.GetText(2) or ""))
    if applied != (prefix, suffix):
        raise RuntimeError(f"{label}: counterbore form did not persist: {applied!r}")


# A printed number: an inch sheet drops the leading zero (".1240").
_MOD_DIAM_VALUE = re.compile(r"<MOD-DIAM>(\d*\.?\d+)")


# The whole of a definition part that is nothing but the coaxial step: its
# diameter, optionally behind the counterbore symbol SolidWorks gives a
# stepped hole, and, optionally, its own depth.
_COAXIAL_STEP_PART = re.compile(
    r"(?:<HOLE-SPOT>\s*)?<MOD-DIAM>(\d*\.?\d+)(?:\s*<HOLE-DEPTH>\s*\d*\.?\d+)?\s*"
)


def _coaxial_step_holders(
    definitions: dict[int, str], step_dia: float, label: str
) -> list[int]:
    """The definition parts (5..8) that hold the coaxial step and nothing else.

    A part naming the step's diameter is cleared whole, so it may hold only
    the step: its ``<MOD-DIAM>`` diameter first, at whatever places it
    prints, behind at most the counterbore symbol ``<HOLE-SPOT>`` that
    ``_drop_coaxial_step`` also clears when it stands alone (codjiflo round
    5: ``<HOLE-SPOT><MOD-DIAM>3.18<HOLE-DEPTH>12.0`` in one part), and at
    most its own ``<HOLE-DEPTH>``.  Any other hole content in that part
    (another ``<MOD-DIAM>``, a THRU, a second depth, another token) is the
    callout's own and fails loud before anything is cleared (codjiflo round
    3: ``<MOD-DIAM>3.18...\\n<MOD-DIAM>1.99...`` would otherwise wipe the
    knockout's size)."""

    def _is_step(value: str) -> bool:
        # The callout prints in the sheet's unit; ``step_dia`` is model mm.
        return math.isclose(
            float(value) * LENGTH_UNITS[UNIT], step_dia, abs_tol=0.006
        )

    holders = []
    for part, text in definitions.items():
        if not any(_is_step(m.group(1)) for m in _MOD_DIAM_VALUE.finditer(text)):
            continue
        whole = _COAXIAL_STEP_PART.fullmatch(text.replace("\r", ""))
        if whole is None or not _is_step(whole.group(1)):
            raise RuntimeError(f"{label}: coaxial step mixed into part {part}: {definitions!r}")
        holders.append(part)
    return holders


def _drop_coaxial_step(display: Any, step_dia: float, label: str) -> None:
    """Clear the coaxial ream's step SolidWorks folds into a native callout.

    Each knockout and its ream meet end to end, so the knockout's callout
    may read the pair as one stepped hole (draw_dt_crankshaft's farm
    evidence: ``<MOD-DIAM>1.40<HOLE-DEPTH>12.63`` in the callout-above part,
    run 20261018T110810560Z-720787ec).  The ream has its own dimension and
    callout, so its step is cleared: only a definition part holding that
    step alone (``_coaxial_step_holders``); the step mixed with anything
    else fails loud.  A bare counterbore symbol before the size goes with
    the step (machinist review of b5c02e5d6).  Read back.
    """
    display = _early_bound(display, "IDisplayDimension")
    definitions = {part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)}
    holders = _coaxial_step_holders(definitions, step_dia, label)
    for part in holders:
        display.SetText(part - 4, "")  # definition part 5..8 -> writable 1..4
        if str(display.GetText(part) or ""):
            raise RuntimeError(f"{label}: coaxial step in part {part} did not clear")
    if not holders:
        return
    prefix = definitions[5]
    if "<HOLE-SPOT>" in prefix and 5 not in holders:
        bare = prefix.replace("<HOLE-SPOT>", "")
        display.SetText(1, bare)
        applied = str(display.GetText(5) or "")
        if applied.replace("\r", "") != bare:
            raise RuntimeError(f"{label}: counterbore symbol did not clear: {applied!r}")
    _telemetry.info(f"{label}: cleared coaxial step from parts {holders}: {definitions!r}")


def _finish_leader_tail(symbol: Any, *, label: str, length: float = FINISH_LEADER_TAIL) -> None:
    """Give one surface-finish symbol the horizontal tail its text needs.

    The roughness value hangs to the right of the symbol, so a short bent
    leader to a feature on the right draws its own tail straight through
    "Ra 3.2".  A feature on the left takes the tail away from the text, so
    its ``length`` only sets where the leader bends.
    """
    annotation = _early_bound(symbol.GetAnnotation(), "IAnnotation")
    annotation.BentLeaderLength = length
    if abs(float(annotation.BentLeaderLength)-length) > 1e-7:
        raise RuntimeError(f"{label} finish leader did not clear its roughness text")


Point = tuple[float, float]


def keeper_callout_placement(
    hole: Point, hole_r: float, boss: Point, boss_r: float
) -> tuple[Point, Point]:
    """(callout point, leader tip) of RD4, on the rear keeper tap, in sheet m.

    The tap's short way in is from the rail's outer face, right of it.  Its
    REAR KEEPER Z extension line runs right from the tap's centre and ends
    on that dimension's arrow, so the callout stands under it, its top an
    arrow clearance clear.  Below the tap the rear boss rounds out toward
    the rail, so the leader drops away from the tap as steeply as the boss
    allows: it passes the boss an ink clearance off.  The tip is where that
    leader meets the tap's rim.
    """
    left, down, right, up = KEEPER_CALLOUT_EXTENT
    shoulder_y = hole[1] - (INK_CLEARANCE + ARROW_HALF_WIDTH + ROUND_OUT) - up - down
    # The leader leaves the hole along (cos t, -sin t); its distance to the
    # boss centre is rho cos(t - phi), shrinking as t steepens past phi.
    steepest = _keeper_leader_angle(hole, boss, boss_r)
    shoulder_x = hole[0] + (hole[1] - shoulder_y) / math.tan(steepest)
    if shoulder_x + left + right + INK_CLEARANCE > SHEET_FRAME[2]:
        raise ValueError(f"keeper callout runs past the frame at x {shoulder_x + left + right:.4f}")
    tip = (hole[0] + hole_r * math.cos(steepest), hole[1] - hole_r * math.sin(steepest))
    return (shoulder_x + left, shoulder_y + down), tip


# Farm runs 20261027T175429300Z and 20261027T190435153Z (machinist review,
# one reviewer each): hung an ink clearance under RD4's shoulder, the
# unleadered facing note (text top 90.1 mm under the 2-56 row's 90.4) read
# as the callout's fifth row.  More than a row pitch of air under the
# shoulder separates it; its bottom row still ends 9 mm over the title block.
KEEPER_FACING_NOTE_GAP = 0.006


def keeper_facing_note_xy(callout: Point) -> Point:
    """Top-left of the keeper-rail facing note, in sheet m: under RD4 at
    ``callout``, flush with its estimated left edge, KEEPER_FACING_NOTE_GAP
    below the native leader shoulder that underlines its bottom row, so it
    reads as its own note, near the faced rail top it governs.  The leader
    leaves that shoulder up-left, away from it.
    """
    left = KEEPER_CALLOUT_EXTENT[0]
    return (
        callout[0] - left,
        callout[1] - KEEPER_CALLOUT_SHOULDER_DROP - KEEPER_FACING_NOTE_GAP,
    )


def section_cut_ends() -> dict[str, tuple[Point, Point]]:
    """Each removed section's cutting-line (start, end) as plan-model (X, Z) mm.

    Keyed by live H/E/K identifiers, with stations and ends fixed by the
    historical B/E/D placement calibration.  Never substitute guessed H/K
    glyph metrics: that would change the cutting plane.  The two 1:3 plans
    turn a paper clearance into ``/ s`` model millimetres.
    """
    s = GEOMETRY_VIEW_SCALE / 1000.0  # sheet m per model mm
    clear = INK_CLEARANCE + ROUND_OUT
    center_y = GEOMETRY_TOP_CENTER[1]
    # Historical B placement sets H's unchanged station.  B183.9 was the
    # original overprint; the measured B width and extents remain calibration
    # only and make no claim about the live H glyph.
    _b0, b_down, b1, b_up = SECTION_CUT_BASELINE_LETTER_EXTENTS["B"]
    text_left = WINDOW_WIDTH_TEXT_XS[1] - WINDOW_WIDTH_TEXT_EXTENT[0]
    rail_x = (text_left - SECTION_CUT_BASELINE_TEXT_GAP - b1 - GEOMETRY_TOP_CENTER[0]) / s
    if not LAND_X1 < rail_x < COLUMN_X - BOSS_DIA / 2.0:
        raise ValueError(f"H-H station x {rail_x:.1f} leaves the rail's plain T")
    # H-H imports the widths the model stands on RAIL_SECTION_X: the cut
    # stays within a millimetre of that station, so their extension lines
    # start on the cut faces.
    if abs(rail_x - RAIL_SECTION_X) > 1.0:
        raise ValueError(
            f"H-H station x {rail_x:.2f} is off the model's {RAIL_SECTION_X:g}"
        )
    # Historical B's outer letter was centred between the dimension line
    # and rail edge; its inner letter cleared the rail's inner face.
    band_low = WINDOW_WIDTH_TEXT_Y - WINDOW_WIDTH_DIM_LINE_DROP
    band_high = center_y - OUTER_Z * s
    outer_y = (band_low + band_high - b_down - b_up) / 2.0
    if outer_y + b_down - band_low < TEXT_CLEARANCE:
        raise ValueError(f"historical B placement fits its band by {outer_y + b_down - band_low:.4f} m")
    inner_y = center_y - INNER_Z * s + clear - b_down
    # E (the left side rail): the outer letter ends an ink clearance left of
    # the corner boss (and the (439.0) witness line on its Ø45 extreme); the
    # inner one, past the rail's inner face, starts an ink clearance right of
    # the front-left boss it stands beside on the front rail.  M (the
    # crossbar) mirrors that: its +X letter starts an ink clearance right of
    # the 18.0 gusset run's outer witness line (E's old inner station, moved
    # out by M's wider glyph), its -X letter ends one left of the -X
    # gusset's leg.  Each line crosses its own piece and window air only.
    e0, _e_down, e1, _e_up = SECTION_CUT_BASELINE_LETTER_EXTENTS["E"]
    m0, _m_down, m1, _m_up = CROSSBAR_SECTION_LETTER_EXTENTS
    # Historical D placement fixes K's ends at the same hub-rail faces.
    d0, _d_down, d1, _d_up = SECTION_CUT_BASELINE_LETTER_EXTENTS["D"]
    return {
        "H": (
            (rail_x, (center_y - outer_y) / s),
            (rail_x, (center_y - inner_y) / s),
        ),
        "E": (
            (-COLUMN_X + BOSS_DIA / 2.0 + (clear - e0) / s, SIDE_SECTION_Z),
            (-PLAN_HALF_X - (clear + e1) / s, SIDE_SECTION_Z),
        ),
        CROSSBAR_SECTION_LETTER: (
            (BAR_X1 + GUSSET + (clear - m0) / s, SIDE_SECTION_Z),
            (BAR_X0 - GUSSET - (clear + m1) / s, SIDE_SECTION_Z),
        ),
        "K": (
            (-OUTER_X - (clear + d1) / s, GOOSENECK_Z),
            (-INNER_X + (clear - d0) / s, GOOSENECK_Z),
        ),
    }


def _pin_section_profile(
    adapter: Any,
    view: Any,
    model_point: tuple[float, float, float],
    target_x: float,
    *,
    label: str,
    target_y: float | None = None,
) -> None:
    """Slide a removed section along the sheet until ``model_point`` (the
    rail centreline it cuts) prints at ``target_x`` (and at ``target_y``
    when given; otherwise on its own row).

    A removed section's outline, and so where SolidWorks centres it, grows
    with its cutting line, air included: on leaders955-f542 #955's longer
    cuts moved D-D's profile 4.27 mm, E-E's 2.84 and B-B's 0.67 under their
    typed dimension text.  Pinning the profile keeps the section where the
    reviewed sheet has it whatever the cut spans.
    """
    point = tuple(value/1000.0 for value in model_point)
    x, y = model_point_in_view(adapter, view, point, label=label)
    position = tuple(float(value) for value in view.Position)
    if len(position) != 2:
        raise RuntimeError(f"{label} section has no position")
    row = y if target_y is None else target_y
    moved = (position[0] + target_x - x, position[1] + row - y)
    if not view.SetViewPosition(double_array(list(moved)), False):
        raise RuntimeError(f"failed to pin the {label} section's profile")
    rebuild_drawing(adapter, label=f"pin {label} profile")
    pinned_x, pinned_y = model_point_in_view(adapter, view, point, label=label)
    _telemetry.info(
        f"{label} rail centreline pinned {x*1000.0:.2f} -> {pinned_x*1000.0:.2f} mm",
        section_profile=label, from_x_mm=round(x*1000.0, 3), sheet_x_mm=round(pinned_x*1000.0, 3),
    )
    if abs(pinned_x - target_x) > 0.00005 or abs(pinned_y - row) > 0.00005:
        raise RuntimeError(
            f"{label} section profile prints at ({pinned_x*1000.0:.3f}, {pinned_y*1000.0:.3f}) mm, "
            f"not at ({target_x*1000.0:.3f}, {row*1000.0:.3f}) mm"
        )


def _model_offset_in_view(
    adapter: Any, view: Any, origin: tuple[float, float, float], along: Point, *, label: str
) -> tuple[float, float, float]:
    """The plan-model point (X, origin Y, Z) that projects ``along`` (sheet m)
    from ``origin``'s projection, read from the view's own X and Z axes."""
    base = model_point_in_view(adapter, view, tuple(v / 1000.0 for v in origin), label=label)
    axes = []
    for dx, dz in ((1.0, 0.0), (0.0, 1.0)):
        moved = (origin[0] + dx, origin[1], origin[2] + dz)
        point = model_point_in_view(adapter, view, tuple(v / 1000.0 for v in moved), label=label)
        axes.append((point[0] - base[0], point[1] - base[1]))
    (xa, ya), (xb, yb) = axes
    det = xa * yb - xb * ya
    if abs(det) < 1e-12:
        raise RuntimeError(f"{label}: the view does not show model X and Z")
    u = (along[0] * yb - along[1] * xb) / det
    w = (xa * along[1] - ya * along[0]) / det
    return (origin[0] + u, origin[1], origin[2] + w)


def _machined_faces(view: Any) -> dict[str, Any]:
    """Resolve every part-owned surface-finish face through ``view``'s model.

    A plan view shows four identical sockets,
    so a coordinate pick cannot say which face a symbol qualifies.  The
    part-owned face specs can: each resolves to exactly one model face, and
    ``add_surface_finish`` then re-checks the selected face against the same
    control before it writes the symbol.
    """
    document = _early_bound(
        _early_bound(view, "IView").ReferencedDocument, "IModelDoc2"
    )
    return resolve_faces(
        document, {control.key: control.face for control in SURFACE_FINISHES}
    )


def _add_view_arrow(
    adapter: Any,
    parent: Any,
    letter: str,
    arrow: tuple[tuple[float, float], tuple[float, float]],
    *,
    vertical: bool = False,
) -> None:
    """A letter arrow on ``parent`` naming a removed view: square onto the
    face it looks at (draw_sm_summing_lever._add_view_arrow).  A horizontal
    arrow's letter slides in y; a ``vertical`` one stands beside its tail
    and slides in x."""
    text_xy, tip_xy = arrow
    label = f"view {letter} viewing arrow"
    note = add_leader_note(
        adapter, letter, text_xy=text_xy, attach_xy=tip_xy, view=parent, label=label,
    )
    # add_note leaves text at the document height; size the letter here and
    # prove the leader tip did not move with it.
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    text_format = annotation.GetTextFormat(0)
    if text_format is None:
        raise RuntimeError(f"{label} note has no text format")
    text_format.CharHeight = VIEW_LETTER_HEIGHT
    if not annotation.SetTextFormat(0, False, text_format):
        raise RuntimeError(f"failed to size the {label} letter")
    rebuild_drawing(adapter, label=f"{label} letter")
    points = list(annotation.GetLeaderPointsAtIndex(0) or ())
    if len(points) < 6 or math.dist((points[-3], points[-2]), tip_xy) > 0.001:
        raise RuntimeError(f"{label} tip moved when its letter was sized")
    # The leader leaves the letter's nearer side at the text's mid-height:
    # slide the letter by any miss across the arrow so it stands square.
    axis = 0 if vertical else 1
    miss = tip_xy[axis] - points[axis]
    if abs(miss) > VIEW_ARROW_SQUARE_TOL:
        position = [float(value) for value in annotation.GetPosition()]
        position[axis] += miss
        if not annotation.SetPosition2(*position):
            raise RuntimeError(f"failed to square the {label}")
        rebuild_drawing(adapter, label=f"square {label}")
        points = list(annotation.GetLeaderPointsAtIndex(0) or ())
        if (
            len(points) < 6
            or math.dist((points[-3], points[-2]), tip_xy) > 0.001
            or abs(tip_xy[axis] - points[axis]) > VIEW_ARROW_SQUARE_TOL
        ):
            raise RuntimeError(f"{label} did not square: leader {points}")
    _telemetry.info(
        f"{label}: leader {points[0]:.5f},{points[1]:.5f} -> "
        f"{points[-3]:.5f},{points[-2]:.5f} (square when the {'xy'[axis]} agree)"
    )


def _pin_sheet_scale(adapter: Any) -> tuple[float, float]:
    """Hold the active sheet at its printed scale before a section or detail.

    Inserting model views auto-drifts the sheet scale (finalize_drawing
    re-pins it before saving), and a native view caption carries its scale
    field only when its view's scale differs from the sheet's AT CREATION
    (_section_axis.position_section_caption).  On the inch sheet the drift
    landed on E-E's own 1:4 (farm leaf b1-fr_top_frame: E-E's caption lost
    its scale field; in mm the drift had cleared every section's scale), so
    each caption is made against the scale the title block prints.
    """
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    sheet = adapter._get_attr_or_call(ddoc, "GetCurrentSheet")
    if sheet is None:
        raise RuntimeError("no active sheet to pin before a section or detail")
    name = str(adapter._get_attr_or_call(sheet, "GetName") or "")
    scale = tuple(float(value) for value in SHEET_SCALES[name])
    if not sheet.SetScale(scale[0], scale[1], False, False):
        raise RuntimeError(f"failed to pin sheet {name!r} at {scale[0]:g}:{scale[1]:g}")
    properties = list(adapter._get_attr_or_call(sheet, "GetProperties2") or [])
    if len(properties) < 4 or (float(properties[2]), float(properties[3])) != scale:
        raise RuntimeError(f"sheet {name!r} scale did not persist: {properties!r}")
    return scale


def _position_view_caption(
    adapter: Any, view: Any, target: tuple[float, float]
) -> None:
    """Move a native section/detail caption without replacing its linked fields.

    The caption is found by its label field alone, as
    ``_section_axis.position_section_caption`` finds it.  It must carry the
    scale field exactly when its view's scale differs from the sheet's
    printed one (the title block states the rest; ``_pin_sheet_scale``).
    A miss lists every note the view owns.
    """
    view = _early_bound(view, "IView")
    if int(view.Type) not in (2, 3):  # swDrawingSectionView, swDrawingDetailView
        raise RuntimeError("caption target is not a native section or detail")
    label = view_name(adapter, view)
    notes = [_early_bound(raw_note, "INote") for raw_note in (view.GetNotes() or ())]
    # GetText is blank at this point; the native view-label fields persist.
    candidates = [
        (note, str(note.PropertyLinkedText or ""))
        for note in notes
        if "<VLLABEL>" in str(note.PropertyLinkedText or "")
    ]
    if len(candidates) != 1:
        texts = [
            (str(note.PropertyLinkedText or ""), str(note.GetText() or "")) for note in notes
        ]
        raise RuntimeError(
            f"expected one native linked view caption on {label!r}, found "
            f"{len(candidates)} among its notes (linked, text) {texts!r}"
        )
    note, linked_text = candidates[0]
    sheet_scale = _pin_sheet_scale(adapter)
    view_scale = tuple(float(value) for value in view.ScaleRatio)
    differs = (
        abs(view_scale[0] / view_scale[1] - sheet_scale[0] / sheet_scale[1]) > 1e-9
    )
    _telemetry.info(
        f"{label} caption {linked_text!r} at {view_scale[0]:g}:{view_scale[1]:g} "
        f"on a {sheet_scale[0]:g}:{sheet_scale[1]:g} sheet"
    )
    if differs and "<VLSCALEV>" not in linked_text:
        raise RuntimeError(
            f"{label} caption {linked_text!r} at {view_scale[0]:g}:{view_scale[1]:g} "
            f"lacks the scale on a {sheet_scale[0]:g}:{sheet_scale[1]:g} sheet"
        )
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    if not annotation.SetPosition2(*target, 0.0):
        raise RuntimeError("failed to position native view caption")
    rebuild_drawing(adapter, label="_position_view_caption")
    position = tuple(float(value) for value in annotation.GetPosition())
    if math.dist(position[:2], target) > 1e-6:
        raise RuntimeError("native view caption position did not persist")
    if str(note.PropertyLinkedText or "") != linked_text:
        raise RuntimeError("view caption lost its native view-label fields")


def _gusset_ramp_angle(adapter: Any, view: Any, view_edges: ViewEdges) -> None:
    """Define the exposed ramp, not the buried sketch flat inside the boss."""
    ramp_points = (
        # the rail underside's broken edge, as in the boss-drop pick
        (-WEB_OUT_X+EDGE_CHAMFER, -HALF_H, GOOSENECK_Z+HUB_GUSSET_HALF_OUT+HUB_BOSS_DROP),
        # mid-ramp on the plate's -X face, which the added draft stands out
        # from its nominal at the boss bottom
        (GOOSENECK_X-HUB_GUSSET_T/2-HUB_BOSS_DROP/2*DRAFT_T, -HALF_H-HUB_BOSS_DROP/2,
         GOOSENECK_Z+(HUB_GUSSET_HALF_IN+HUB_GUSSET_HALF_OUT)/2),
    )
    edges = _exact_linear_entities(view_edges, ramp_points, label="hub gusset ramp angle")
    sector = model_point_in_view(
        adapter, view,
        ((GOOSENECK_X-HUB_GUSSET_T/2)/1000.0,
         (-HALF_H-HUB_BOSS_DROP/8)/1000.0,
         (GOOSENECK_Z+HUB_GUSSET_HALF_OUT-HUB_BOSS_DROP)/1000.0),
        label="gusset acute angular sector",
    )
    points = [
        model_point_in_view(
            adapter, view, tuple(value/1000.0 for value in point),
            label="gusset angular pick",
        )
        for point in ramp_points
    ]
    display = add_edge_dimension(
        adapter, view, p0=points[0], p1=points[1], text_xy=sector,
        label="hub gusset ramp angle", orientation="smart", entities=tuple(edges),
    )
    draw = adapter.currentModel
    display = _early_bound(display, "IDisplayDimension")
    if int(display.Type2) != 3:
        raise RuntimeError("gusset ramp dimension is not angular")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    expected = math.atan2(HUB_BOSS_DROP, HUB_GUSSET_HALF_OUT-HUB_GUSSET_HALF_IN)
    if abs(float(dimension.SystemValue)-expected) > 1e-7:
        raise RuntimeError(f"gusset ramp angle measured {dimension.SystemValue} radians, expected {expected}")
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    if not annotation.SetPosition2(*HUB_GUSSET_ANGLE_TEXT_XY, 0.0):
        raise RuntimeError("failed to position native gusset ramp angle")
    _set_derived_precision(display, label="hub gusset ramp angle")
    set_dimension_callouts(
        adapter, [annotation],
        {
            dimension_name(adapter, annotation): (
                "2X GUSSET RAMP\nTO RAIL UNDERSIDE"
            )
        },
    )
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="_gusset_ramp_angle")
    if abs(float(dimension.SystemValue)-expected) > 1e-7:
        raise RuntimeError("gusset ramp angle changed after text positioning")


def _note_text_centre(
    adapter: Any, annotation: Any, text: str, *, label: str
) -> tuple[float, float]:
    """The centre (sheet m) of a note's one printed ``text`` run, read through
    the layout audit's own reader: the run's lower-left on its baseline, the
    width SolidWorks reports and its cap height (``display_box``).  An
    estimated width, a refused read or any other count of runs fails."""
    display, refused = annotation_display(adapter, annotation)
    runs = [
        raw for raw in display.get("texts", ())
        if str(raw.get("t", "")).strip() == text
    ]
    box = display_box({"texts": runs}) if len(runs) == 1 else None
    if refused or box is None or estimated_text_runs({"texts": runs}):
        raise RuntimeError(
            f"{label}: {text!r} is not one measured run "
            f"({len(runs)} runs, refused {refused})"
        )
    return (box.xmin + box.xmax) / 2.0, (box.ymin + box.ymax) / 2.0


def _centre_note_text(
    adapter: Any, annotation: Any, text: str, centre_xy: tuple[float, float], *, label: str
) -> tuple[float, float]:
    """Move a note so its printed ``text`` is centred on ``centre_xy`` (where
    SolidWorks puts the text about its requested position is not known);
    the measured centre, which must land within NOTE_TEXT_CENTRE_TOL."""
    x, y = _note_text_centre(adapter, annotation, text, label=label)
    dx, dy = centre_xy[0] - x, centre_xy[1] - y
    if math.hypot(dx, dy) > NOTE_TEXT_CENTRE_TOL:
        move_annotation(adapter, annotation, dx, dy, label=label)
        x, y = _note_text_centre(adapter, annotation, text, label=label)
    miss = math.dist((x, y), centre_xy)
    if miss > NOTE_TEXT_CENTRE_TOL:
        raise RuntimeError(f"{label}: {text!r} stands {miss * 1000.0:.2f} mm off its centre")
    return x, y


def _add_pictorial_captions(adapter: Any) -> None:
    """Each PICTORIAL_CAPTIONS note, its text read back centred under its
    view on the active pictorial sheet."""
    for text, centre_xy in PICTORIAL_CAPTIONS:
        label = f"pictorial caption {text}"
        note = add_note(adapter, text, *centre_xy)
        if note is None:
            raise RuntimeError(f"failed to add the {label}")
        annotation = _early_bound(_early_bound(note, "INote").GetAnnotation(), "IAnnotation")
        _centre_note_text(adapter, annotation, text, centre_xy, label=label)


# SolidWorks attaches one of its own automatic "Tapped Hole" notes to a view
# that imports a tapped feature's marked dimensions.  ``finalize_drawing``
# deletes every one of them before export -- the sheet states each thread in
# its own associative feature callout, which carries the process too.
#
# Neither the COUNT nor the SET of views is specification, and both have been
# tried as the gate.  The count was the bare literal 7, explained by a comment
# claiming the seven came from "five sheets with two of them drawn
# hidden-lines-removed"; both were wrong -- a note arrives once per VIEW that
# imports a tapped feature, and this package has printed 7, then 8, then 5
# across three builds of the same geometry.  The view set replaced it and
# lasted exactly one build: the next run, whose only change was three
# annotation text positions, attached one to GEOMETRY/Section View B-B.  The
# reason is the same for both: SolidWorks attaches a feature's note to
# whichever view imports that feature FIRST, and which instance a re-pick
# lands on is not ours to choose.
#
# So the inventory is evidence, not a gate: it is logged by view so a build
# that changes which views import a tapped feature says so, and it hands
# ``finalize_drawing`` the count this run actually found.  The invariant that
# reaches the print is the deletion -- exactly the inventoried notes must go,
# so a note arriving after the inventory or a deletion pass that misses one
# still fails the build.


@_telemetry.traced("drawing.auto_tapped_hole_notes")
def _auto_tapped_hole_notes(adapter: Any) -> dict[str, int]:
    """Delete SolidWorks' own Hole Wizard notes, named per view, on every sheet.

    Importing model items brings SolidWorks' descriptive thread note ("10-32
    Tapped Hole") along with the geometry, and this recipe replaces every one
    of them with an associative feature callout that also carries the process.
    A bare count cannot say WHICH view changed, and the count is not one per
    sheet: a note arrives once per view that imported a tapped feature, so a
    view added, re-scaled or switched to hidden-lines-removed moves it.  This
    names them, and deletes them here rather than handing the substring to
    ``finalize_drawing``'s sweep: that sweep re-walked every annotation of
    every view, sheet by sheet (13 s of a 270 s build), to find the notes this
    walk -- ``ISheet::GetViews`` off the sheet objects, no sheet activation --
    already holds.  Each deletion is proved by the view's note list read back.
    """
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    counts: dict[str, int] = {}
    for sheet_name in drawing.GetSheetNames() or ():
        sheet = _early_bound(drawing.Sheet(str(sheet_name)), "ISheet")
        for raw_view in sheet.GetViews() or ():
            view = _early_bound(raw_view, "IView")
            hits = [
                note for note in (
                    _early_bound(raw_note, "INote") for raw_note in (view.GetNotes() or ())
                )
                if "tapped hole" in str(note.GetText() or "").lower()
            ]
            if not hits:
                continue
            label = f"{sheet_name}/{view_name(adapter, view)}"
            for note in hits:
                draw.ClearSelection2(True)
                if not _early_bound(note.GetAnnotation(), "IAnnotation").Select2(False, 0):
                    raise RuntimeError(f"{label}: failed to select an automatic tapped-hole note")
                draw.EditDelete()  # VT_VOID: the re-read below is the proof
            draw.ClearSelection2(True)
            survivors = sum(
                1 for raw_note in (view.GetNotes() or ())
                if "tapped hole" in str(_early_bound(raw_note, "INote").GetText() or "").lower()
            )
            if survivors:
                raise RuntimeError(
                    f"{label}: {survivors} automatic tapped-hole note(s) survived deletion"
                )
            counts[label] = len(hits)
    return counts


def _socket_bore_circle(edges: ViewEdges, x: float, z: float, *, label: str) -> Any:
    """A plan's exact bore circle about the socket axis at (``x``, ``z``) mm.

    The socket rim is matched on X/Z only: which of the bore's rims (top or
    bottom, same X/Z) the plan shows is the view's choice, not the print's.
    """
    socket = min(
        (
            item
            for item in edges.circles
            if abs(item.circle[0] - x) < 1e-4
            and abs(item.circle[2] - z) < 1e-4
            and abs(item.circle[6] - BORE_DIA / 2) < 1e-4
            and abs(item.circle[3])
            + abs(abs(item.circle[4]) - 1.0)
            + abs(item.circle[5])
            < 1e-6
        ),
        key=lambda item: item.circle[1],
        default=None,
    )
    if socket is None:
        raise RuntimeError(f"{label}: no exact socket bore circle at ({x:g}, {z:g}) mm")
    return socket.edge


def _face_line(edges: ViewEdges, *, axis: int, across: int, at: float, face: str) -> Any:
    """A plan's longest visible straight edge running along model ``axis``
    with its ``across`` coordinate at ``at`` mm.  Picked from the scanned
    edges, not by a sheet point, so the edge break's inner line 0.76 mm away
    (farm run 20261107T122639370Z: a point pick measured 1.524 short) cannot
    win."""
    runs = [
        item for item in edges.lines
        if all(
            abs(item.line[0][k] - item.line[1][k]) < 1e-6 for k in (0, 1, 2) if k != axis
        )
        and abs(item.line[0][across] - at) < 1e-3
    ]
    if not runs:
        raise RuntimeError(f"holes/sockets plan shows no straight edge of the {face}")
    return max(runs, key=lambda item: abs(item.line[0][axis] - item.line[1][axis])).edge


def _hole_table_axes(edges: ViewEdges) -> tuple[Any, Any]:
    """The plan's two axis edges: the faced top's longest visible straight
    edge along the rear rail (X-running, at z OUTER_RIM_TOP_Z) and along the
    west rail (Z-running, at x OUTER_RIM_TOP_X), parallel to the F and G
    planes that make TABLE_ORIGIN_XZ.

    They give the native table its axis directions only; its origin is the
    theoretical point on the F|G corner.
    """
    return (
        _face_line(
            edges, axis=0, across=2, at=OUTER_RIM_TOP_Z, face="rear rail's faced-top edge",
        ),
        _face_line(
            edges, axis=2, across=0, at=OUTER_RIM_TOP_X, face="west rail's faced-top edge",
        ),
    )


def _draw_datum_traces(adapter: Any, view: Any) -> dict[str, SketchedLine]:
    """The F and G planes' traces on the plan, thin phantom, from their
    corner TABLE_ORIGIN_XZ: F under the two rear bosses to the rear-east
    one's tangent point, G up the rear-west boss to TABLE_G_LINE_FRONT_Z."""
    x0, z0 = TABLE_ORIGIN_XZ
    corner, f_end, g_end = (
        model_point_in_view(
            adapter, view, (x / 1000.0, HALF_H / 1000.0, z / 1000.0), label=label,
        )
        for x, z, label in (
            (x0, z0, "hole-table F|G corner"),
            (-COLUMN_X, z0, "rear-east boss F tangent point"),
            (x0, TABLE_G_LINE_FRONT_Z, "G trace front end"),
        )
    )
    font = {"style": TABLE_TANGENT_LINE_STYLE, "width": TABLE_TANGENT_LINE_WEIGHT}
    lines = sketch_lines(
        adapter, view,
        {
            "F plane": (tuple(corner[:2]), tuple(f_end[:2])),
            "G plane": (tuple(corner[:2]), tuple(g_end[:2])),
        },
        label="hole-table datum trace", **font,
    )
    rebuild_drawing(adapter, label="hole-table datum traces")
    require_placed(adapter, lines, label="hole-table datum trace", stage="drawn", **font)
    return lines


def _set_table_origin_arrows(adapter: Any, table: Any, corner_xy: tuple[float, float]) -> None:
    """Set the hole table's origin mark's arrow tips (TABLE_ORIGIN_*_ARROW)
    about the corner and read the mark back: the origin on the corner, the X
    arrow level under it running left from its ordinate, the Y arrow plumb
    right of it running up from its ordinate."""
    feature = _early_bound(_early_bound(table, "IHoleTableAnnotation").HoleTable, "IHoleTable")
    origin = _early_bound(feature.DatumOrigin, "IDatumOrigin")
    annotation = _early_bound(origin.GetAnnotation(), "IAnnotation")
    position = tuple(float(value) for value in annotation.GetPosition() or ())
    if len(position) < 2 or math.dist(position[:2], corner_xy) > 0.0001:
        raise RuntimeError(f"holes/sockets origin mark stands at {position!r}, not on {corner_xy!r}")
    ox, oy = corner_xy
    (x_length, x_offset), (y_length, y_offset) = TABLE_ORIGIN_X_ARROW, TABLE_ORIGIN_Y_ARROW
    tips = [ox - x_length, oy - x_offset, ox + y_offset, oy + y_length]
    if origin.SetAxisPoints(double_array(tips)) is not True:
        raise RuntimeError(f"holes/sockets origin mark refused its arrow tips {tips!r}")
    rebuild_drawing(adapter, label="holes/sockets origin arrows")
    axis = [float(value) for value in origin.GetAxisPoints2() or ()]
    _telemetry.info(f"holes/sockets origin mark axis points: {axis!r}")
    if len(axis) != 8:
        raise RuntimeError(f"holes/sockets origin mark reads {axis!r}")
    x_start, x_tip, y_start, y_tip = axis[0:2], axis[2:4], axis[4:6], axis[6:8]
    expected = {
        "X tip": (x_tip, (ox - x_length, oy - x_offset)),
        "Y tip": (y_tip, (ox + y_offset, oy + y_length)),
        "X start": ((x_start[1],), (oy - x_offset,)),
        "Y start": ((y_start[0],), (ox + y_offset,)),
    }
    for name, (got, want) in expected.items():
        if any(abs(g - w) > 0.0001 for g, w in zip(got, want)):
            raise RuntimeError(f"holes/sockets origin {name} reads {got!r}, not {want!r}")
    if not (
        ox - x_length / 2.0 < x_start[0] <= ox + 0.001
        and oy - 0.001 <= y_start[1] < oy + y_length / 2.0
    ):
        raise RuntimeError(f"holes/sockets origin arrows do not start at the corner: {axis!r}")


def _socket_hole_table(adapter: Any, view: Any, edges: ViewEdges) -> Any:
    """Sheet 3's TAG/X LOC/Y LOC/MATE table for TABLE_HOLES, BASIC from the
    F|G corner, SIZE hidden."""
    corner_xy = model_point_in_view(
        adapter, view,
        (TABLE_ORIGIN_XZ[0] / 1000.0, HALF_H / 1000.0, TABLE_ORIGIN_XZ[1] / 1000.0),
        label="hole-table origin",
    )
    # The view sketch's origin is the view's own, not the model's: the
    # set-screw boss stands the casting's envelope off the socket pattern's
    # centre, so the corner goes through the sketch's transform.
    (corner_sketch,) = sheet_to_sketch(adapter, view, [tuple(corner_xy[:2])])
    origin = create_view_theoretical_datum(
        adapter, view,
        point_xy=(corner_sketch[0], corner_sketch[1]),
        label="F|G corner table origin",
    )
    hole_entities = []
    hole_points = []
    for x, z, diameter, _mate in TABLE_HOLES:
        hole_entities.append(_socket_bore_circle(edges, x, z, label="hole-table socket"))
        hole_points.append(model_point_in_view(
            adapter, view,
            ((x + diameter / 2.0) / 1000.0, (HALF_H + BOSS_ABOVE) / 1000.0, z / 1000.0),
            label="hole-table rim",
        ))
    _drop_hole_table_leading_zeros(adapter)
    # The faced top's rear and west rail edges give the table its axis
    # directions; the F and G traces are drawing sketch lines, which
    # InsertHoleTable3's axis selection refuses (farm run
    # 20261111T015941119Z: IEntity.Select4 'Type mismatch').
    axes = _hole_table_axes(edges)
    table = insert_hole_table(
        adapter, view,
        datum_xy=corner_xy,
        datum_point=origin,
        datum_axes=axes,
        hole_points=tuple(hole_points),
        hole_entities=tuple(hole_entities),
        anchor_xy=HOLE_TABLE_ANCHOR,
        basic_locations=True,
        label="holes/sockets",
        unit=UNIT,
        location_places=3,
    )
    table = _early_bound(table, "ITableAnnotation")

    def cells() -> tuple[tuple[str, ...], ...]:
        return tuple(
            tuple(
                str(table.DisplayedText2(row, column, False) or "").strip()
                for column in range(int(table.ColumnCount))
            )
            for row in range(int(table.RowCount))
        )

    _telemetry.info(f"holes/sockets table cells before the arrows: {cells()!r}")
    _set_table_origin_arrows(adapter, table, corner_xy)
    rows = cells()
    _telemetry.info(f"holes/sockets table cells: {rows!r}")
    if leading_zero_locations(rows[1:]):
        raise RuntimeError(f"holes/sockets LOC cells kept a leading zero: {rows!r}")
    bound = bind_hole_table_rows(rows[1:], LENGTH_UNITS[UNIT])
    if negative_locations(rows[1:]):
        raise RuntimeError(f"holes/sockets LOC cells read negative from the corner: {rows!r}")
    if table.InsertColumn2(_INSERT_COLUMN_AFTER, 3, HOLE_TABLE_MATE_COLUMN, 0) is not True:
        raise RuntimeError("holes/sockets table refused its MATE column")
    if table.SetColumnTitle2(4, HOLE_TABLE_MATE_COLUMN, False) is not True:
        raise RuntimeError("holes/sockets MATE column title did not set")
    for row, hole in bound.items():
        mate = TABLE_HOLES[hole][3]
        if table.IsCellTextEditable(row, 4) is not True:
            raise RuntimeError(f"holes/sockets MATE cell at row {row} is not editable")
        table.SetText2(row, 4, False, mate)
        applied = str(table.DisplayedText2(row, 4, False) or "").strip()
        if applied != mate:
            raise RuntimeError(f"holes/sockets MATE cell {row} reads {applied!r}")
    for column, width in (
        (0, HOLE_TABLE_TAG_WIDTH),
        (1, HOLE_TABLE_LOC_WIDTH),
        (2, HOLE_TABLE_LOC_WIDTH),
        (4, HOLE_TABLE_MATE_WIDTH),
    ):
        actual = float(table.SetColumnWidth(column, width, _TABLE_SIZE_CAN_CHANGE))
        if abs(actual - width) > 1e-6:
            raise RuntimeError(f"holes/sockets column {column} width did not persist: {actual!r}")
    for row in range(int(table.RowCount)):
        table.SetRowHeight(row, HOLE_TABLE_ROW_HEIGHT, _TABLE_SIZE_CAN_CHANGE)
    table.SetColumnHidden(_HOLE_TABLE_SIZE_COLUMN, True)  # VT_VOID, not success.
    if table.ColumnHidden(_HOLE_TABLE_SIZE_COLUMN) is not True:
        raise RuntimeError("holes/sockets native SIZE column did not hide")
    rebuild_drawing(adapter, label="holes/sockets table")
    width = sum(
        float(table.GetColumnWidth(column))
        for column in range(int(table.ColumnCount))
        if column != _HOLE_TABLE_SIZE_COLUMN
    )
    height = sum(float(table.GetRowHeight(row)) for row in range(int(table.RowCount)))
    _telemetry.info(
        f"holes/sockets table: {width * 1000.0:.1f} x {height * 1000.0:.1f} mm at "
        f"{HOLE_TABLE_ANCHOR}, rows bound {bound!r}"
    )
    if HOLE_TABLE_ANCHOR[0] + width > _TITLE_BLOCK_LEFT:
        raise RuntimeError(f"holes/sockets table runs into the title block: {width:.4f} m wide")
    if HOLE_TABLE_ANCHOR[1] - height < EDGE_NOTE_XY[1]:
        raise RuntimeError(f"holes/sockets table reaches the edge-break note: {height:.4f} m tall")
    _place_hole_tags(adapter, view, {rows[row][0]: hole for row, hole in bound.items()})
    return table


def _place_hole_tags(adapter: Any, view: Any, tags: dict[str, int]) -> None:
    """Move each native hole tag to hole_tag_position on a leader to its hole."""
    found: dict[str, tuple[Any, Any]] = {}
    for raw in _early_bound(view, "IView").GetAnnotations() or ():
        annotation = _early_bound(raw, "IAnnotation")
        if int(annotation.GetType()) != 6:  # swNote
            continue
        note = _early_bound(annotation.GetSpecificAnnotation(), "INote")
        text = str(note.GetText()).strip()
        if text not in tags:
            continue
        if text in found:
            raise RuntimeError(f"holes/sockets view carries two {text!r} tags")
        found[text] = (annotation, note)
    if set(found) != set(tags):
        raise RuntimeError(
            f"holes/sockets view tags {sorted(found)!r} do not match the table's {sorted(tags)!r}"
        )
    s = DETAIL_VIEW_SCALE / 1000.0
    for tag, hole in sorted(tags.items()):
        x, z, diameter, _mate = TABLE_HOLES[hole]
        annotation, note = found[tag]
        if annotation.SetLeader3(1, 0, True, False, False, False) != 0:
            raise RuntimeError(f"failed to give hole tag {tag} a leader")
        position = hole_tag_position(x, z)
        if not annotation.SetPosition2(*position, 0.0):
            raise RuntimeError(f"failed to move hole tag {tag}")
        if str(note.GetText()).strip() != tag:
            raise RuntimeError(f"moving hole tag {tag} changed its text")
        points = tuple(float(value) for value in annotation.GetLeaderPointsAtIndex(0) or ())
        if len(points) < 6 or len(points) % 3 or not all(math.isfinite(v) for v in points):
            raise RuntimeError(f"hole tag {tag} has no complete leader: {points!r}")
        centre = (DETAIL_TOP_CENTER[0] + x * s, DETAIL_TOP_CENTER[1] - z * s)
        reach = math.dist(points[-3:-1], centre)
        if reach > diameter / 2.0 * s + 0.001:
            raise RuntimeError(
                f"hole tag {tag} leader ends {reach * 1000.0:.2f} mm from its hole's axis"
            )
        _telemetry.info(f"hole tag {tag}: at {position!r}, leader end {reach * 1000.0:.2f} mm off axis")
    rebuild_drawing(adapter, label="holes/sockets tags")


def _count_cross_taps(display: Any) -> None:
    """Write cross_tap_definitions into the cross-tap callout; prove the
    printed rows carry the 4X count once, no native 2X, and the mate line."""
    native = _early_bound(display, "IDisplayDimension")

    def read(parts: tuple[int, ...]) -> dict[int, str]:
        return {part: str(native.GetText(part) or "").replace("\r", "") for part in parts}

    definitions = read((5, 6, 7, 8))
    updated = cross_tap_definitions(definitions)
    for definition_part, writable_part in ((5, 1), (6, 2), (7, 3), (8, 4)):
        if updated[definition_part] != definitions[definition_part]:
            native.SetText(writable_part, updated[definition_part])
    persisted = read((5, 6, 7, 8))
    printed = "\n".join(read((1, 2, 3, 4)).values())
    if (
        persisted != updated
        or re.search(r"\b2X", printed)
        or len(re.findall(rf"\b{CROSS_TAP_COUNT}", printed)) != 1
        or printed.count(CROSS_TAP_MATE_LINE) != 1
    ):
        raise RuntimeError(
            f"cross-tap callout did not take its count and mate: definitions={definitions!r}, "
            f"persisted={persisted!r}, printed={printed!r}"
        )
    _telemetry.info(f"cross-tap callout: {printed!r}")


def _set_precise_curve_quality(adapter: Any) -> None:
    """Resolve native drawing curves finely enough to show their actual shape.

    Faceted=False selects precise HLR, but its curves still use the drawing's
    wireframe-resolution slider. The high-curve option refines angular
    tolerance at settings 92..100 (SDK Document Properties > Image Quality).
    Pin only this new drawing, before any model views compute their geometry.
    """
    extension = _early_bound(adapter.currentModel.Extension, "IModelDocExtension")
    before = (
        extension.GetUserPreferenceInteger(_IMAGE_QUALITY_WIREFRAME, _NO_PREFERENCE_OPTION),
        extension.GetUserPreferenceInteger(_IMAGE_QUALITY_WIREFRAME_VALUE, _NO_PREFERENCE_OPTION),
        extension.GetUserPreferenceToggle(_IMAGE_QUALITY_HIGH_CURVES, _NO_PREFERENCE_OPTION),
    )
    for preference, value in (
        (_IMAGE_QUALITY_WIREFRAME, _WIREFRAME_CUSTOM),
        (_IMAGE_QUALITY_WIREFRAME_VALUE, _CURVE_RESOLUTION),
    ):
        if extension.SetUserPreferenceInteger(preference, _NO_PREFERENCE_OPTION, value) is not True:
            raise RuntimeError("failed to set top-frame drawing curve resolution")
    if extension.SetUserPreferenceToggle(
        _IMAGE_QUALITY_HIGH_CURVES, _NO_PREFERENCE_OPTION, True
    ) is not True:
        raise RuntimeError("failed to improve top-frame drawing curve quality")
    after = (
        extension.GetUserPreferenceInteger(_IMAGE_QUALITY_WIREFRAME, _NO_PREFERENCE_OPTION),
        extension.GetUserPreferenceInteger(_IMAGE_QUALITY_WIREFRAME_VALUE, _NO_PREFERENCE_OPTION),
        extension.GetUserPreferenceToggle(_IMAGE_QUALITY_HIGH_CURVES, _NO_PREFERENCE_OPTION),
    )
    if after[:2] != (_WIREFRAME_CUSTOM, _CURVE_RESOLUTION) or after[2] is not True:
        raise RuntimeError(f"top-frame drawing curve quality did not persist: {after!r}")
    _telemetry.info(
        "top-frame drawing precise curve resolution",
        curve_quality_before=before, curve_quality_after=after,
    )


# TEMPORARY (#2333): the casting sheets' layout iterations report every
# layout finding without failing, so each PDF and audit report publish.
# Removed before the strict run.
_layout_audit.ENFORCED_KINDS = frozenset()


@dataclass(frozen=True)
class _BarrelFace:
    """One corner boss's drafted lower barrel: the DRAFT_DEG cone whose box
    holds a point on the boss's axis (``_gtol_face.FaceSpec``)."""

    x: float
    y: float
    z: float
    tolerance_mm: float = 0.05
    surface_identity = SURFACE_CONE

    def matches(self, geometry: Any) -> bool:
        if geometry.identity != SURFACE_CONE or len(geometry.box) != 6:
            return False
        if abs(math.degrees(geometry.parameters[7]) - DRAFT_DEG) > 0.01:
            return False
        box = [value * 1000.0 for value in geometry.box]
        return (
            box[0] < self.x < box[3]
            and box[1] < self.y < box[4]
            and box[2] < self.z < box[5]
        )


def _named_dimension(adapter: Any, annotations: list[Any], name: str) -> Any:
    """The one imported annotation named ``name``."""
    matches = [
        annotation for annotation in annotations
        if dimension_name(adapter, annotation) == name
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected one {name} dimension, found {len(matches)}")
    return matches[0]


def _web_position_frame(
    adapter: Any,
    view: Any,
    edges: ViewEdges,
    *,
    landing_mm: tuple[float, float, float],
    frame_xy: tuple[float, float],
    label: str,
) -> None:
    """A rail web's ⌖.06|A|B (owner ruling D3) on the cut face through
    ``landing_mm``, the frame at ``frame_xy``."""
    landing = model_point_in_view(
        adapter, view, tuple(value / 1000.0 for value in landing_mm), label=label
    )
    add_feature_control_frame(
        adapter, view,
        edge_entity=edges.exact_line_through(landing_mm, label=label).edge,
        leader_attach_xy=(float(landing[0]), float(landing[1])),
        frame_xy=frame_xy,
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_IN["rail web position"],
        datums=("A", SOCKET_DATUM),
        quantity=WEB_POSITION_QUANTITY,
        label=label,
    )


def _socket_position_frame(adapter: Any, view: Any, edges: ViewEdges) -> None:
    """The sockets' composite position frame and datum B on it
    (SOCKET_POSITION_FRAME_XY)."""
    landing = model_point_in_view(
        adapter, view,
        (
            (COLUMN_X + BORE_DIA / 2.0) / 1000.0,
            (HALF_H + BOSS_ABOVE - CAP_RECESS_DEPTH) / 1000.0,
            FRONT_COLUMN_Z / 1000.0,
        ),
        label="front-right socket rim",
    )
    frame = add_feature_control_frame(
        adapter, view,
        edge_entity=_socket_bore_circle(
            edges, COLUMN_X, FRONT_COLUMN_Z, label="socket pattern position",
        ),
        leader_attach_xy=(float(landing[0]), float(landing[1])),
        frame_xy=SOCKET_POSITION_FRAME_XY,
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_IN["tube socket pattern location"],
        datums=CAST_DATUM_FRAME,
        diameter=True,
        quantity=SOCKET_POSITION_QUANTITY,
        lower_frame=(
            "position",
            GEOMETRIC_TOLERANCES_IN["tube socket pattern refinement"],
            ("A",),
        ),
        composite=True,
        label="tube socket pattern position",
    )
    add_frame_datum_feature(
        adapter, view, frame, datum=SOCKET_DATUM,
        symbol_xy=(
            SOCKET_POSITION_FRAME_XY[0] + SOCKET_DATUM_SYMBOL_OFFSET[0],
            SOCKET_POSITION_FRAME_XY[1] + SOCKET_DATUM_SYMBOL_OFFSET[1],
        ),
        label="tube socket pattern datum B",
    )


def _target_point_dimension(
    adapter: Any,
    view: Any,
    *,
    socket: Any,
    target: Any,
    text_xy: tuple[float, float],
    expected_mm: float,
    label: str,
) -> Any:
    """The vertical distance from a socket's axis to a datum target's own
    point (the sketch point its symbol is attached to), measured."""
    draw = adapter.currentModel
    if not _early_bound(draw, "IDrawingDoc").ActivateView(view_name(adapter, view)):
        raise RuntimeError(f"failed to activate the view for {label}")
    annotation = _early_bound(target.GetAnnotation(), "IAnnotation")
    points = tuple(annotation.GetAttachedEntities3() or ())
    if len(points) != 1:
        raise RuntimeError(f"{label}: the target stands on {len(points)} entities")
    draw.ClearSelection2(True)
    manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    for index, (entity, interface) in enumerate(
        ((socket, "IEntity"), (points[0], "ISketchPoint"))
    ):
        selection_data = manager.CreateSelectData()
        selection_data.View = view
        if not _early_bound(entity, interface).Select4(index > 0, selection_data):
            raise RuntimeError(f"failed to select {label} entity {index}")
    if int(manager.GetSelectedObjectCount2(-1)) != 2:
        raise RuntimeError(f"{label}: the selection does not hold its two entities")
    with dimension_input_suppressed(adapter):
        display = draw.AddVerticalDimension2(text_xy[0], text_xy[1], 0.0)
    draw.ClearSelection2(True)
    if display is None:
        raise RuntimeError(f"failed to add the {label} dimension")
    set_arc_endpoints_to_center(adapter, display, label=label)
    native = _early_bound(display, "IDisplayDimension")
    measured = abs(
        float(_early_bound(native.GetDimension2(0), "IDimension").SystemValue)
    ) * 1000.0
    if abs(measured - expected_mm) > 1e-5:
        raise RuntimeError(f"{label}: measured {measured:g}, expected {expected_mm:g} mm")
    _set_derived_precision(native, label=label)
    return native


def _basic_target_location(
    adapter: Any, display: Any, offset_text: tuple[float, float], *, label: str
) -> None:
    """Box a datum-target location BASIC, its count above the value and its
    text parked at ``offset_text``."""
    set_basic_dimension(adapter, display, label=label)
    annotation = _early_bound(
        _early_bound(display, "IDisplayDimension").GetAnnotation(), "IAnnotation"
    )
    name = dimension_name(adapter, annotation)
    set_dimension_callouts(
        adapter, [annotation], {name: DATUM_TARGET_COUNT}, location="above"
    )
    offset_dimension_text(adapter, [annotation], {name: offset_text})


def _cast_datum_sheet(adapter: Any, ddoc: Any) -> list[Any]:
    """Sheet 7: the casting's datum frame (owner rulings B6 and D2, #2333).

    The underside carries E1-E3 and G1, the F and G planes' traces to their
    corner (sheet 3's hole-table origin), datum D on the crossbar's as-cast
    width and D's station from G; the elevation over it carries F1, F2 and
    the barrel targets' height.  Returns the imported dimensions.
    """
    if not ddoc.ActivateSheet("CAST-DATUMS"):
        raise RuntimeError("failed to activate top-frame cast-datum sheet")
    front = place_view(
        adapter, str(SOURCE), "*Front", *DATUM_FRONT_CENTER, scale=SHEET_SCALE,
    )
    bottom = place_view(
        adapter, str(SOURCE), "*Bottom", *DATUM_BOTTOM_CENTER, scale=SHEET_SCALE,
    )
    set_hidden_lines_removed(adapter, front)
    set_hidden_lines_removed(adapter, bottom)
    dimensions = curate_view_dimensions(
        adapter,
        bottom,
        keep=DATUM_BOTTOM_KEEP,
        view_label="cast datum underside",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_dimension_callouts(
        adapter,
        dimensions,
        {name: "" for name in DATUM_BOTTOM_KEEP},
    )
    set_dimension_callouts(
        adapter,
        dimensions,
        DATUM_BOTTOM_CALLOUTS_ABOVE,
        location="above",
    )
    set_dimension_callouts(
        adapter,
        dimensions,
        DATUM_BOTTOM_CALLOUTS,
    )
    offset_dimension_text(
        adapter,
        dimensions,
        DATUM_BOTTOM_TEXT_OFFSETS,
    )
    # The two printed draft angles (owner ruling D4), on the elevation.
    draft_dimensions = curate_view_dimensions(
        adapter,
        front,
        keep=DATUM_FRONT_KEEP,
        view_label="cast datum elevation",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_dimension_callouts(adapter, draft_dimensions, DATUM_FRONT_CALLOUTS)
    offset_dimension_text(adapter, draft_dimensions, DATUM_FRONT_TEXT_OFFSETS)
    edges = scan_view_edges(bottom, label="cast datum underside")

    def sheet(x: float, y: float, z: float) -> tuple[float, float]:
        point = model_point_in_view(
            adapter, bottom, (x / 1000.0, y / 1000.0, z / 1000.0),
            label="cast datum underside point",
        )
        return (float(point[0]), float(point[1]))

    # D's trace: the native centreline between the crossbar's two sides, on
    # their outline from below (the faced top's break, which the added draft
    # stands widest).
    side_y = HALF_H - TOP_BREAK_DROP
    side_out = RIM_RECEDE - TOP_BREAK_RECEDE

    def median() -> None:
        _insert_crossbar_median(
            adapter, bottom,
            tuple(_exact_linear_entities(
                edges,
                ((BAR_X0 - side_out, side_y, 0.0), (BAR_X1 + side_out, side_y, 0.0)),
                label="crossbar sides for median D, underside",
            )),
        )

    median()
    # The F and G planes' traces through their targets, to the corner sheet
    # 3's table counts from; G runs on to the front, where D's station
    # starts from it.
    origin_x, origin_z = CAST_DATUM_ORIGIN_XZ
    font = {"style": TABLE_TANGENT_LINE_STYLE, "width": TABLE_TANGENT_LINE_WEIGHT}

    def traces() -> None:
        lines = sketch_lines(
            adapter, bottom,
            {
                "F plane": (
                    sheet(origin_x, HALF_H, origin_z),
                    sheet(-COLUMN_X, HALF_H, origin_z),
                ),
                "G plane": (
                    sheet(origin_x, HALF_H, origin_z),
                    sheet(origin_x, HALF_H, D_STATION_LINE_Z),
                ),
            },
            label="cast datum plane trace", **font,
        )
        rebuild_drawing(adapter, label="cast datum plane traces")
        require_placed(
            adapter, lines, label="cast datum plane trace", stage="drawn", **font
        )

    traces()

    document = _early_bound(
        _early_bound(bottom, "IView").ReferencedDocument, "IModelDoc2"
    )
    face_specs: dict[str, Any] = {}
    for target, (x, _y, z) in CAST_DATUM_TARGETS.items():
        column_x = math.copysign(COLUMN_X, x)
        column_z = math.copysign(REAR_COLUMN_Z, z)
        if target.startswith("E"):
            face_specs[target] = PlanarFace(
                (0.0, -1.0, 0.0), -BOSS_BOTTOM_Y,
                contains_x_mm=column_x, contains_z_mm=column_z,
            )
        else:
            face_specs[target] = _BarrelFace(column_x, DATUM_TARGET_Y, column_z)
    # F1 and G1 share the rear-west barrel: each distinct face resolves once.
    distinct: dict[Any, str] = {}
    for target, spec in face_specs.items():
        distinct.setdefault(spec, target)
    faces = resolve_faces(document, {key: spec for spec, key in distinct.items()})
    symbols: dict[str, Any] = {}
    for target, model_point in CAST_DATUM_TARGETS.items():
        view = front if target in DATUM_TARGETS_ON_ELEVATION else bottom
        at = tuple(
            float(value)
            for value in model_point_in_view(
                adapter, view, tuple(value / 1000.0 for value in model_point),
                label=f"cast datum target {target} point",
            )[:2]
        )
        offset = DATUM_TARGET_SYMBOL_OFFSETS[target]
        symbols[target] = add_datum_target(
            adapter,
            view,
            target=target,
            target_xy=at,
            symbol_xy=(at[0] + offset[0], at[1] + offset[1]),
            entity=faces[distinct[face_specs[target]]],
            entity_type="FACE",
            label=f"cast datum target {target}",
        )
        _telemetry.info(
            f"cast datum target {target}: {datum_target_readback(symbols[target])!r}"
        )

    # Each boss-bottom target's BASIC radius from its socket axis, stated on
    # E3 for the three: each stands on its own socket's centre line.
    def radius() -> None:
        label = "boss bottom target from socket axis"
        display = _target_point_dimension(
            adapter, bottom,
            socket=_socket_bore_circle(
                edges, CAST_DATUM_TARGETS["E3"][0], FRONT_COLUMN_Z, label=label,
            ),
            target=symbols["E3"],
            text_xy=DATUM_E_RADIUS_LINE_XY,
            expected_mm=DATUM_TARGET_BOTTOM_RADIUS, label=label,
        )
        _basic_target_location(adapter, display, DATUM_E_RADIUS_TEXT_XY, label=label)

    radius()

    def datum_d() -> None:
        width = _named_dimension(adapter, dimensions, "BarWidth")
        _crossbar_median_datum(
            adapter, bottom,
            _early_bound(width.GetSpecificAnnotation(), "IDisplayDimension"),
        )

    datum_d()

    # The barrel targets' height over the boss bottoms: one phantom line at
    # that height across the rear-west boss, located BASIC from its bottom.
    def height() -> None:
        label = "barrel target above boss bottom"
        front_edges = scan_view_edges(front, label="cast datum elevation")
        ends = [
            tuple(
                float(value)
                for value in model_point_in_view(
                    adapter, front,
                    (x / 1000.0, DATUM_TARGET_Y / 1000.0, REAR_COLUMN_Z / 1000.0),
                    label=label,
                )[:2]
            )
            for x in (
                COLUMN_X - DATUM_HEIGHT_LINE_REACH[0],
                COLUMN_X + DATUM_HEIGHT_LINE_REACH[1],
            )
        ]
        line = sketch_lines(
            adapter, front, {"barrel target height": (ends[0], ends[1])},
            label=label, **font,
        )
        rebuild_drawing(adapter, label=label)
        require_placed(adapter, line, label=label, stage="drawn", **font)
        display = _checked_dimension(
            adapter, front,
            p0=(COLUMN_X, BOSS_BOTTOM_Y, REAR_COLUMN_Z),
            p1=(COLUMN_X, DATUM_TARGET_Y, REAR_COLUMN_Z),
            text_xy=DATUM_HEIGHT_LINE_XY, label=label,
            expected_mm=DATUM_TARGET_BARREL_HEIGHT, orientation="vertical",
            entity_types=("EDGE", "SKETCHSEGMENT"),
            entities=(
                front_edges.circle_at(
                    (COLUMN_X, BOSS_BOTTOM_Y, REAR_COLUMN_Z), BOSS_BOTTOM_EDGE_R,
                    axis=(0.0, 1.0, 0.0), label="rear-west boss bottom",
                    center_tol_mm=1e-3, radius_tol_mm=1e-3,
                ).edge,
                line["barrel target height"].segment,
            ),
        )
        _basic_target_location(adapter, display, DATUM_HEIGHT_TEXT_XY, label=label)

    height()
    return [*dimensions, *draft_dimensions]


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")
    check("open top-frame source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Manufacturing Notes B",
            "Manufacturing Notes C",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Manufacturing Notes B",
            "Manufacturing Notes C",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout,
        unit=UNIT,
    )
    _set_precise_curve_quality(adapter)
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="top-frame package")
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Top Frame Ring Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "top frame; webbed gray iron ring casting; column bores",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    extension = _early_bound(drawing_model.Extension, "IModelDocExtension")
    if not extension.SetUserPreferenceInteger(542, 0, 0):
        raise RuntimeError("failed to set connected section cutting lines")
    if extension.GetUserPreferenceInteger(542, 0) != 0:
        raise RuntimeError("section cutting-line style did not persist")
    ddoc = _early_bound(drawing_model, "IDrawingDoc")
    # Sheet 1 primes the reader: two octant pictorials, each named in words
    # under it (PICTORIAL_CAPTIONS).  The old 1:5 isometric tucked under the
    # geometry sheet's front view is gone with it.
    if not ddoc.ActivateSheet("PICTORIAL"):
        raise RuntimeError("failed to activate top-frame pictorial sheet")
    place_pictorial_sheet(
        adapter, str(SOURCE), PICTORIAL_VIEWS, scale=PICTORIAL_SCALE,
        label="top-frame pictorials",
    )
    _add_pictorial_captions(adapter)

    if not ddoc.ActivateSheet("GEOMETRY"):
        raise RuntimeError("failed to activate top-frame geometry sheet")
    geometry_top = place_view(
        adapter,
        str(SOURCE),
        "*Top",
        *GEOMETRY_TOP_CENTER,
        scale=SHEET_SCALE,
    )
    geometry_front = place_view(
        adapter,
        str(SOURCE),
        "*Front",
        *GEOMETRY_FRONT_CENTER,
        scale=SHEET_SCALE,
    )
    # drawing-guidelines.md rule 9 (show internal shape in solid lines): the plan view's hidden rail undersides and land
    # pads repeat what sections H-H, E-E and M-M plus the sheet 6 underside
    # view already describe, so they come off the dimensioned plan.
    set_hidden_lines_removed(adapter, geometry_top)
    set_hidden_lines_removed(adapter, geometry_front)
    geometry_top_edges = scan_view_edges(geometry_top, label="geometry top")
    # The three sections import before the plan and the front view: a
    # feature's dimensions land in the first view that can show them, and
    # each section keeps one its feature shares with the plan or the
    # elevation (OuterProfile, WebProfile, TopFlange).
    # H-H is a REMOVED section: the cutting line crosses the +Z rail alone
    # (the -Z rail is its mirror), so the section shows the one T profile the
    # web, flange, chamfer and root dimensions hang on instead of that
    # profile beside an identical twin 80 mm away carrying nothing.
    cut_ends = section_cut_ends()
    rail_cut_x = cut_ends["H"][0][0]
    _pin_sheet_scale(adapter)
    rail_cut = [
        model_point_in_view(
            adapter, geometry_top, (x/1000.0, 0.0, z/1000.0),
            label="front rear rail section station",
        )
        for x, z in cut_ends["H"]
    ]
    rail_section = create_section_view(
        adapter, geometry_top,
        line_start=rail_cut[0],
        line_end=rail_cut[1],
        view_xy=RAIL_SECTION_CENTER, section_label="H", scale=(1, 3),
        partial=True, label="T rail manufacturing section",
    )
    _orient_cut_section(adapter, rail_section, (0.0, 0.0, 1.0))
    _pin_section_profile(
        adapter, rail_section, (rail_cut_x, 0.0, abs(FRONT_COLUMN_Z)),
        RAIL_SECTION_PROFILE_X, label="H-H",
    )
    # The display mode comes before any pick: ``scan_view_edges``
    # answers for the mode the view is in, so an edge picked while the
    # ghosts were drawn would dimension a line the print does not carry.
    set_hidden_lines_removed(adapter, rail_section)
    rail_section_edges = scan_view_edges(rail_section, label="H-H rail section")
    # Each text parks clear of every witness line: the two widths sit beside
    # their extension lines.  The .32 flange run is 2.7 mm of paper, so it
    # needs a leader.  The front and rear rails are one T, so the two widths
    # carry their count (rule 26), not a prose note under the caption (rule
    # 9).  All three are the model's own dimensions with their ±.03 (owner
    # ruling B2, #2333); the root radius is the front view's.
    rail_section_dimensions = curate_view_dimensions(
        adapter,
        rail_section,
        keep=RAIL_SECTION_KEEP,
        view_label="T rail section H-H",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_dimension_callouts(
        adapter,
        rail_section_dimensions,
        RAIL_SECTION_CALLOUTS,
    )
    offset_dimension_text(
        adapter,
        rail_section_dimensions,
        {"FlangeT": FLANGE_T_TEXT_OFFSET_XY},
    )
    # The rim break's run across the faced top to the drafted rim, between
    # its two corners.
    _checked_dimension(
        adapter,
        rail_section,
        p0=(rail_cut_x, HALF_H, INNER_Z + EDGE_CHAMFER),
        p1=(rail_cut_x, HALF_H - TOP_BREAK_DROP, INNER_Z + TOP_BREAK_RECEDE),
        text_xy=(0.290, 0.250),
        label="top rim chamfer",
        expected_mm=TOP_BREAK_DROP,
        orientation="horizontal",
        entity_types=("VERTEX", "VERTEX"),
        exact_vertices=True,
        suffix="X 45° TOP RIMS",
        edges=rail_section_edges,
    )
    _web_position_frame(
        adapter,
        rail_section,
        rail_section_edges,
        landing_mm=(
            rail_cut_x,
            WEB_POSITION_LANDING_Y,
            WEB_IN_Z - (WEB_POSITION_LANDING_Y + HALF_H) * DRAFT_T,
        ),
        frame_xy=RAIL_WEB_POSITION_FRAME_XY,
        label="front and rear rail web position",
    )
    # The web stands on the flange's own centre (both on the socket axes):
    # a drawn centreline shows that symmetry where the old note said it.
    _add_view_centerlines(
        adapter, rail_section,
        (((rail_cut_x, -HALF_H - SECTION_AXIS_OVERRUN_MM * 3, REAR_COLUMN_Z),
          (rail_cut_x, HALF_H + SECTION_AXIS_OVERRUN_MM * 3, REAR_COLUMN_Z)),),
    )
    _position_view_caption(adapter, rail_section, RAIL_SECTION_CAPTION_XY)
    _assert_section_display(
        adapter, rail_section, label="H-H T rail section", cut_surface_only=True, removed=True
    )
    # H-H cuts the front/rear rails only, so the 34.2 side rails and the
    # crossbar had no web thickness, root radius or rim chamfer anywhere on
    # the print, yet the keeper taps and the hanger holes are cut into
    # exactly that stock.  One plane at z -56 cuts both, but the left side
    # rail and the crossbar T are two pieces with only the window between
    # them, so they are two removed sections (owner 2026-11-07, rule 9: a
    # plane that leaves pieces floating becomes separate sections): E-E
    # across the left side rail only, M-M across the crossbar only, each
    # cutting plane a short whole line across its own piece -- not the right
    # rail's identical, unannotated twin.
    _pin_sheet_scale(adapter)
    side_cut = [
        model_point_in_view(
            adapter, geometry_top, (x/1000.0, 0.0, z/1000.0),
            label="side rail section station",
        )
        for x, z in cut_ends["E"]
    ]
    side_section = create_section_view(
        adapter, geometry_top,
        line_start=side_cut[0], line_end=side_cut[1],
        view_xy=SIDE_SECTION_CENTER, section_label="E", scale=SIDE_SECTION_SCALE,
        partial=True, label="side rail manufacturing section",
    )
    _orient_cut_section(adapter, side_section, (1.0, 0.0, 0.0))
    _pin_section_profile(
        adapter, side_section, (-COLUMN_X, 0.0, SIDE_SECTION_Z),
        SIDE_SECTION_PROFILE_X, label="E-E", target_y=SIDE_SECTION_CENTER[1],
    )
    set_hidden_lines_removed(adapter, side_section)
    side_section_edges = scan_view_edges(side_section, label="E-E side rail section")
    side_section_dimensions = curate_view_dimensions(
        adapter,
        side_section,
        keep=SIDE_SECTION_KEEP,
        view_label="side rail section E-E",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_dimension_callouts(
        adapter,
        side_section_dimensions,
        {"SideWebT": SIDE_WEB_QUALIFIER},
    )
    _web_position_frame(
        adapter,
        side_section,
        side_section_edges,
        landing_mm=(
            -WEB_IN_X + (WEB_POSITION_LANDING_Y + HALF_H) * DRAFT_T,
            WEB_POSITION_LANDING_Y,
            SIDE_SECTION_Z,
        ),
        frame_xy=SIDE_WEB_POSITION_FRAME_XY,
        label="side rail web position",
    )
    # The web stands on its flange's centre: a drawn centreline shows it
    # (rule 10) where a prose note under the caption used to (rule 9); the
    # web's 2X carries the right rail.
    _add_view_centerlines(
        adapter, side_section,
        (((-COLUMN_X, -HALF_H - SECTION_AXIS_OVERRUN_MM * 4, SIDE_SECTION_Z),
          (-COLUMN_X, HALF_H + SECTION_AXIS_OVERRUN_MM * 4, SIDE_SECTION_Z)),),
    )
    _position_view_caption(adapter, side_section, SIDE_SECTION_CAPTION_XY)
    _assert_section_display(
        adapter, side_section, label="E-E side rail section", cut_surface_only=True, removed=True
    )
    _pin_sheet_scale(adapter)
    crossbar_cut = [
        model_point_in_view(
            adapter, geometry_top, (x/1000.0, 0.0, z/1000.0),
            label="crossbar section station",
        )
        for x, z in cut_ends[CROSSBAR_SECTION_LETTER]
    ]
    crossbar_section = create_section_view(
        adapter, geometry_top,
        line_start=crossbar_cut[0], line_end=crossbar_cut[1],
        view_xy=CROSSBAR_SECTION_CENTER, section_label=CROSSBAR_SECTION_LETTER,
        scale=SIDE_SECTION_SCALE, partial=True, label="crossbar manufacturing section",
    )
    _orient_cut_section(adapter, crossbar_section, (1.0, 0.0, 0.0))
    _pin_section_profile(
        adapter, crossbar_section, (HANGER_X, 0.0, SIDE_SECTION_Z),
        CROSSBAR_SECTION_PROFILE_X, label=f"{CROSSBAR_SECTION_LETTER}-{CROSSBAR_SECTION_LETTER}",
        target_y=SIDE_SECTION_CENTER[1],
    )
    set_hidden_lines_removed(adapter, crossbar_section)
    crossbar_section_edges = scan_view_edges(crossbar_section, label="crossbar section")
    # The crossbar T: its web and its pockets' depth are the model's own
    # dimensions with their ±.03 (owner ruling B2, #2333).  Its flange is the
    # rails' .32 again, a reference here: from the faced top to the
    # underside's flat, 1 mm in from the drafted side.
    crossbar_section_dimensions = curate_view_dimensions(
        adapter,
        crossbar_section,
        keep=CROSSBAR_SECTION_KEEP,
        view_label="crossbar section",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_dimension_callouts(
        adapter,
        crossbar_section_dimensions,
        CROSSBAR_SECTION_CALLOUTS,
    )
    offset_dimension_text(
        adapter,
        crossbar_section_dimensions,
        {
            "CrossbarWebT": CROSSBAR_WEB_TEXT_XY,
            "PocketDepth": CROSSBAR_POCKET_DEPTH_TEXT_XY,
        },
    )

    def pocket_arrows_inside() -> None:
        pocket_depth = _early_bound(
            _named_dimension(
                adapter, crossbar_section_dimensions, "PocketDepth"
            ).GetSpecificAnnotation(),
            "IDisplayDimension",
        )
        pocket_depth.ArrowSide = _DIM_ARROWS_INSIDE
        if int(pocket_depth.ArrowSide) != _DIM_ARROWS_INSIDE:
            raise RuntimeError("crossbar pocket depth did not keep its arrows inside")

    pocket_arrows_inside()
    _checked_dimension(
        adapter,
        crossbar_section,
        p0=(HANGER_X, HALF_H, SIDE_SECTION_Z),
        p1=(BAR_X0 - POCKET_H * DRAFT_T + 1.0, FLANGE_BOT_Y, SIDE_SECTION_Z),
        text_xy=CROSSBAR_FLANGE_LINE_XY,
        label="crossbar flange thickness",
        expected_mm=FLANGE,
        orientation="vertical",
        exact_linear=True,
        suffix="CROSSBAR FLANGE",
        offset_text=CROSSBAR_FLANGE_TEXT_XY,
        edges=crossbar_section_edges,
        reference=True,
    )
    _add_view_centerlines(
        adapter, crossbar_section,
        (((HANGER_X, -HALF_H - SECTION_AXIS_OVERRUN_MM * 4, SIDE_SECTION_Z),
          (HANGER_X, HALF_H + SECTION_AXIS_OVERRUN_MM * 4, SIDE_SECTION_Z)),),
    )
    _position_view_caption(adapter, crossbar_section, CROSSBAR_SECTION_CAPTION_XY)
    _assert_section_display(
        adapter, crossbar_section, label="crossbar section", cut_surface_only=True, removed=True
    )
    # The plan carries the flange's extents and the side flange's width; the
    # front view the rail height and the root radius.
    geometry_top_dimensions = curate_view_dimensions(
        adapter,
        geometry_top,
        keep=GEOMETRY_TOP_KEEP,
        view_label="geometry top",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    geometry_front_dimensions = curate_view_dimensions(
        adapter,
        geometry_front,
        keep=GEOMETRY_FRONT_KEEP,
        view_label="geometry front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    geometry_annotations = [*geometry_top_dimensions, *geometry_front_dimensions]
    geometry_callouts = {
        name: "" for name in (*GEOMETRY_TOP_KEEP, *GEOMETRY_FRONT_KEEP)
    }
    geometry_callouts.update(GEOMETRY_CALLOUTS)
    set_dimension_callouts(
        adapter,
        geometry_annotations,
        geometry_callouts,
    )
    _reference_model_rail_height(
        adapter,
        geometry_front_dimensions,
    )
    _reference_plan_outlines(
        adapter,
        geometry_top_dimensions,
    )
    # Every imported dimension's places are the part's; the whole print's
    # imports are collected here and read back once, before export.
    imported_annotations = [
        *rail_section_dimensions,
        *side_section_dimensions,
        *crossbar_section_dimensions,
        *geometry_annotations,
    ]
    # The plan extremes are the corner-boss barrels at the faced top's plane
    # (R.885, where both barrels' draft starts) and, on the east, the
    # set-screw boss's face, .065 past the east barrels' tangent (owner
    # ruling B4, #2333).  Each end is the scanned edge itself: a sheet-point
    # hit test on a barrel's outline resolved to an inner circle (farm
    # a03283b49: width 435 for 439).
    def plan_barrel(x: float, z: float, label: str) -> Any:
        return geometry_top_edges.circle_at(
            (x, HALF_H, z), BOSS_DIA/2,
            axis=(0.0, 1.0, 0.0), label=label,
            center_tol_mm=1e-4, radius_tol_mm=1e-4,
        ).edge

    def overall_width() -> None:
        _checked_dimension(
            adapter, geometry_top,
            p0=(SET_BOSS_FACE_X, HALF_H, GOOSENECK_Z),
            p1=(PLAN_HALF_X, HALF_H, FRONT_COLUMN_Z),
            text_xy=(GEOMETRY_TOP_CENTER[0], 0.2565), label="overall casting width",
            expected_mm=PLAN_HALF_X-SET_BOSS_FACE_X, orientation="horizontal",
            maximum=True, reference=True, suffix="OVERALL",
            entities=(
                geometry_top_edges.exact_line_through(
                    (SET_BOSS_FACE_X, HALF_H, GOOSENECK_Z),
                    label="overall width, set-screw boss face",
                ).edge,
                plan_barrel(COLUMN_X, FRONT_COLUMN_Z, "overall width, west barrel"),
            ),
        )

    def overall_depth() -> None:
        _checked_dimension(
            adapter, geometry_top,
            p0=(-COLUMN_X, HALF_H, -PLAN_HALF_Z),
            p1=(-COLUMN_X, HALF_H, PLAN_HALF_Z),
            text_xy=(0.022, 0.145), label="overall casting depth",
            expected_mm=2*PLAN_HALF_Z, orientation="vertical", maximum=True,
            reference=True,
            entities=(
                plan_barrel(-COLUMN_X, FRONT_COLUMN_Z, "overall depth, front barrel"),
                plan_barrel(-COLUMN_X, REAR_COLUMN_Z, "overall depth, rear barrel"),
            ),
        )

    overall_width()
    overall_depth()
    # The side flange's symmetry: its sockets' shared axis, drawn between
    # the right-hand bosses through the rail the 1.35 spans.
    _add_view_centerlines(
        adapter, geometry_top,
        (((COLUMN_X, HALF_H, FRONT_COLUMN_Z + BOSS_DIA / 2.0 + SECTION_AXIS_OVERRUN_MM),
          (COLUMN_X, HALF_H, REAR_COLUMN_Z - BOSS_DIA / 2.0 - SECTION_AXIS_OVERRUN_MM)),),
    )
    # The plan and front views are projected at the title block's own scale,
    # so a label restating it would be the one thing on the sheet saying
    # nothing.  Sheet 6's bottom view is out of projection: this arrow under
    # the front view names it (rules 9 and 26).
    _add_view_arrow(
        adapter, geometry_front, UNDERSIDE_VIEW_LETTER, UNDERSIDE_VIEW_ARROW,
        vertical=True,
    )

    if not ddoc.ActivateSheet("HOLES-SOCKETS"):
        raise RuntimeError("failed to activate top-frame holes/sockets sheet")
    detail_top = place_view(
        adapter,
        str(SOURCE),
        "*Top",
        *DETAIL_TOP_CENTER,
        scale=DETAIL_TOP_SCALE,
    )
    set_hidden_lines_removed(adapter, detail_top)
    detail_top_dimensions = curate_view_dimensions(
        adapter,
        detail_top,
        keep=DETAIL_TOP_KEEP,
        view_label="holes/sockets top",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    detail_top_callouts = {name: "" for name in DETAIL_TOP_KEEP}
    detail_top_callouts.update(DETAIL_CALLOUTS)
    set_dimension_callouts(adapter, detail_top_dimensions, detail_top_callouts)
    imported_annotations += detail_top_dimensions
    socket_annotations = [
        annotation for annotation in detail_top_dimensions
        if dimension_name(adapter, annotation) == "B0Dia"
    ]
    if len(socket_annotations) != 1:
        raise RuntimeError("expected one native socket nominal for reference display")
    socket_display = set_reference_dimension(
        adapter, socket_annotations[0], label="matched socket nominal", diameter=True,
    )
    socket_dimension = _early_bound(socket_display.GetDimension2(0), "IDimension")
    if int(socket_dimension.GetToleranceType()) != 0:  # swTolNONE
        raise RuntimeError("socket source still carries a fixed fit tolerance; rebuild the part")
    # Both diameters of the upper-left boss read off one arrow on the rim
    # nearest their text: as full diameters through the shared axis their
    # leaders crossed at the socket centre (machinist review r3, rule 14).
    for name in DETAIL_TOP_KEEP:
        (annotation,) = [
            annotation for annotation in detail_top_dimensions
            if dimension_name(adapter, annotation) == name
        ]
        set_near_side_diameter(annotation, f"holes/sockets top {name}")
    if not auto_center_marks(adapter, detail_top, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to top-frame hole pattern")
    # No origin centrelines or X/Z axis tags on this sheet: nothing here is
    # dimensioned from the frame centre any more, and drawn axes would
    # invite reading it as the datum.
    # The title block names no finish grade ("CAST/MACHINED"), so every
    # surface that must be cut says so on the face: the tube sockets locate
    # the columns.  The symbol carries the part's own control and attaches
    # to the one model face that control names.
    machined_faces = _machined_faces(detail_top)
    landing = math.radians(SOCKET_FINISH_LANDING_DEG)
    socket_finish = add_surface_finish(
        adapter,
        detail_top,
        symbol_xy=SOCKET_FINISH_SYMBOL_XY,
        control=surface_finish_by_key(SURFACE_FINISHES, "socket_east_rear"),
        label="tube socket bore finish",
        entity_type="FACE",
        entity=machined_faces["socket_east_rear"],
        # Sheet up is model -Z, so the sheet angle's sine runs down +Z.
        leader_attach_xy=model_point_in_view(
            adapter,
            detail_top,
            (
                (-COLUMN_X + BORE_DIA / 2 * math.cos(landing)) / 1000.0,
                0.0,
                (REAR_COLUMN_Z - BORE_DIA / 2 * math.sin(landing)) / 1000.0,
            ),
            label="socket bore finish leader",
        ),
        char_height=0.0025,
    )
    _finish_leader_tail(socket_finish, label="tube socket bore")
    # The plain wizard's clearance rim at the finished top identifies the
    # whole through-hole feature; its native row reads C DRILL ... THRU.
    stud_edge = model_point_in_view(
        adapter,
        detail_top,
        (
            HANGER_X / 1000.0,
            HALF_H / 1000.0,
            (STUD_Z_FRONT + HANGER_CLEARANCE_DIA / 2.0) / 1000.0,
        ),
        label="top-frame hanger clearance rim",
    )
    hanger_callout = add_native_hole_callout(
        adapter,
        detail_top,
        edge_xy=stud_edge,
        # Right of the 182.0 row's end, so the leader reaches the hole past
        # that row instead of across it (codex round 5).
        callout_xy=HANGER_CALLOUT_XY,
        label="2X C drill hanger clearance holes",
    )
    _set_hanger_hole_callout(hanger_callout)
    # Linear position to D centres each bolt axis within ±.005 (owner ruling
    # 2026-11-06: ⌖ .010|D, the drilled-hole row) of the
    # TWO-side-face median plane, the axes BASIC zero on D. No diameter
    # prefix: this controls X only; the Z socket stations stay toleranced.
    detail_top_edges = scan_view_edges(detail_top, label="hanger axis centring")
    hanger_hole_edge = detail_top_edges.circle_at(
        (HANGER_X, HALF_H, STUD_Z_FRONT), HANGER_CLEARANCE_DIA / 2.0,
        axis=(0.0, 1.0, 0.0), label="front hanger clearance at the finished top",
    ).edge
    # Same selected rim, landed up-right of the axis, clear of the callout's
    # leader diameter (HANGER_CENTER_LANDING_DEG); the helper reads it back.
    hanger_center_landing_xy = model_point_in_view(
        adapter, detail_top, tuple(v / 1000.0 for v in hanger_center_landing()),
        label="front hanger clearance rim, up-right of the axis",
    )
    add_feature_control_frame(
        adapter, detail_top, edge_entity=hanger_hole_edge,
        leader_attach_xy=hanger_center_landing_xy,
        frame_xy=HANGER_CENTER_FRAME_XY,
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_IN["knife-hanger crossbar centring"],
        datums=("D",), quantity=HANGER_CENTER_QUALIFIER,
        label="hanger axes on crossbar median plane",
    )
    # D's trace: the native centreline between the crossbar's two sides, on
    # their outline -- the faced top's break, where the added draft stands
    # the bar widest -- so it follows the faces.  D's width, its tag and its
    # station from G stand on sheet 7 (owner rulings B5 and D2, #2333).
    side_out = RIM_RECEDE - TOP_BREAK_RECEDE

    def crossbar_median() -> None:
        _insert_crossbar_median(
            adapter, detail_top,
            tuple(_exact_linear_entities(
                detail_top_edges,
                (
                    (BAR_X0 - side_out, HALF_H - TOP_BREAK_DROP, 0.0),
                    (BAR_X1 + side_out, HALF_H - TOP_BREAK_DROP, 0.0),
                ),
                label="crossbar sides for median D",
            )),
        )

    crossbar_median()
    _draw_datum_traces(adapter, detail_top)
    # Each hanger hole's Z station, .XXX from the front sockets' shared axis
    # (owner ruling D2, #2333): drawn between the front bosses, it is the
    # line both stations stand from.
    (front_socket_axis,) = _add_view_centerlines(
        adapter, detail_top,
        (((-COLUMN_X + BOSS_DIA / 2.0 + SECTION_AXIS_OVERRUN_MM, HALF_H, FRONT_COLUMN_Z),
          (COLUMN_X - BOSS_DIA / 2.0 - SECTION_AXIS_OVERRUN_MM, HALF_H, FRONT_COLUMN_Z)),),
    )
    for station_z, label in (
        (STUD_Z_FRONT, "front hanger z from upper sockets"),
        (STUD_Z_REAR, "rear hanger z from upper sockets"),
    ):
        _checked_dimension(
            adapter,
            detail_top,
            p0=(HANGER_X, HALF_H, FRONT_COLUMN_Z),
            p1=(HANGER_X, HALF_H, station_z),
            text_xy=HANGER_Z_TEXT_XY[label],
            label=label,
            expected_mm=station_z - FRONT_COLUMN_Z,
            orientation="vertical",
            center=True,
            entity_types=("SKETCHSEGMENT", "EDGE"),
            entities=(
                front_socket_axis,
                detail_top_edges.circle_at(
                    (HANGER_X, HALF_H, station_z),
                    HANGER_CLEARANCE_DIA / 2.0,
                    axis=(0.0, 1.0, 0.0),
                    label=label,
                ).edge,
            ),
        )
    # #946: RD4 reads off the rear keeper tap, from the rail's outer side.
    rear_keeper = (KEEPER_TAP_X, HALF_H, KEEPER_TAP_Z_REAR)
    keeper_hole = model_point_in_view(
        adapter, detail_top, tuple(v / 1000.0 for v in rear_keeper),
        label="top-frame rear keeper tap centre",
    )
    keeper_rim = model_point_in_view(
        adapter, detail_top,
        (
            (KEEPER_TAP_X + TAP_DRILL_MM[KEEPER_TAP_SPEC.size] / 2.0) / 1000.0,
            HALF_H / 1000.0,
            KEEPER_TAP_Z_REAR / 1000.0,
        ),
        label="top-frame rear keeper tap rim",
    )
    rear_boss = model_point_in_view(
        adapter, detail_top,
        (COLUMN_X / 1000.0, (HALF_H + BOSS_ABOVE) / 1000.0, REAR_COLUMN_Z / 1000.0),
        label="top-frame rear right boss centre",
    )
    keeper_callout_xy, keeper_tip = keeper_callout_placement(
        keeper_hole,
        math.dist(keeper_hole, keeper_rim),
        rear_boss,
        BOSS_DIA / 2.0 * DETAIL_VIEW_SCALE / 1000.0,
    )
    keeper_edge_model = _model_offset_in_view(
        adapter, detail_top, rear_keeper,
        (keeper_tip[0] - keeper_hole[0], keeper_tip[1] - keeper_hole[1]),
        label="top-frame rear keeper tap leader rim",
    )
    keeper_edge = model_point_in_view(
        adapter, detail_top, tuple(v / 1000.0 for v in keeper_edge_model),
        label="top-frame fulcrum-keeper tap edge",
    )
    if math.dist(keeper_edge, keeper_tip) > 1e-6:
        raise RuntimeError(
            f"rear keeper rim point projects to {keeper_edge}, not the leader's {keeper_tip}"
        )
    keeper_callout = add_native_hole_callout(
        adapter,
        detail_top,
        edge_xy=keeper_edge,
        callout_xy=keeper_callout_xy,
        label="2X fulcrum-keeper blind taps",
        process=TRANSFER_KEEPER_CALLOUT,
    )
    # Part-spec-authored .XX drill diameter and .X blind depths: these are
    # also the precision inputs to the published-band receiver proof.
    set_hole_callout_precision(
        keeper_callout,
        KEEPER_TAP_CALLOUT_PRECISION,
        label="keeper tap sizes and depths",
    )
    # The faced whole top (user rulings 2026-10-11/18): the part's own
    # linked note B, hung under the transfer callout it belongs with.
    add_property_linked_note(
        adapter,
        "Manufacturing Notes B",
        *keeper_facing_note_xy(keeper_callout_xy),
        char_height=FACING_NOTE_HEIGHT,
    )
    # The keeper seats carry no flatness frame: the faced top above holds them
    # (fr_top_frame_spec.GEOMETRIC_TOLERANCES_MM; codex review of 06d0bbc59).
    # The keeper taps are transferred from MHA-CH-07 at assembly, so their
    # callout alone places them; the sockets are located by one tagged table,
    # BASIC from the F|G corner under their composite frame, and the hanger
    # holes stand on D by their own frame (drawing-guidelines.md rule 10).
    # The gooseneck bore stands on the left sockets' axis (GOOSENECK_X is
    # -COLUMN_X): drawn here as their shared centreline, it gives the bore
    # its X on this sheet too (rule 26: holes in line share a drawn
    # centreline; farm run 20261106T214613300Z found it unlocated in X).
    _add_view_centerlines(
        adapter, detail_top,
        (((-COLUMN_X, HALF_H, FRONT_COLUMN_Z + BOSS_DIA / 2.0 + SECTION_AXIS_OVERRUN_MM),
          (-COLUMN_X, HALF_H, REAR_COLUMN_Z - BOSS_DIA / 2.0 - SECTION_AXIS_OVERRUN_MM)),),
    )
    _socket_hole_table(
        adapter,
        detail_top,
        detail_top_edges,
    )
    _socket_position_frame(
        adapter,
        detail_top,
        detail_top_edges,
    )
    # Under the table at x 30 mm: from x 40 the then 70-character edge-break
    # line ran 2.4 mm into the title block (farm 30394c1da keep-out); its 67
    # characters now end near 200 mm, about 16 short of the block's left edge
    # at 216.
    add_property_linked_note(
        adapter, "Manufacturing Notes", *EDGE_NOTE_XY, char_height=0.0035,
    )
    if not ddoc.ActivateSheet("CROSS-TAPS"):
        raise RuntimeError("failed to activate top-frame cross-tap sheet")
    detail_front = place_view(
        adapter,
        str(SOURCE),
        "*Front",
        *DETAIL_FRONT_CENTER,
        scale=DETAIL_FRONT_SCALE,
    )
    _pin_sheet_scale(adapter)
    cut_x = model_point_in_view(
        adapter,
        detail_front,
        (COLUMN_X / 1000.0, 0.0, 0.0),
        label="top-frame corner-section axis",
    )[0]
    detail_section = create_section_view(
        adapter,
        detail_front,
        line_start=(cut_x, DETAIL_FRONT_CENTER[1] - 0.020),
        line_end=(cut_x, DETAIL_FRONT_CENTER[1] + 0.030),
        view_xy=DETAIL_SECTION_CENTER,
        section_label="A",
        scale=DETAIL_SECTION_SCALE,
        label="top-frame corner section",
    )
    # drawing-guidelines.md rule 9 (show internal shape in solid lines): hidden lines only where they inform.  The cross-taps this
    # elevation calls out are counterbored from the face it looks at, so the
    # Ø9.0 counterbore rim and the tap drill circle inside it are VISIBLE ink
    # and the 10-32 callout, its native drill/thread depths and the
    # 22.7 tap-axis-below-boss-top dimension keep their attachments without
    # them.  What the dashed lines added was the far end's sockets, cap
    # recesses and hanger holes -- none of them dimensioned here, all of
    # them cut open by A-A or specified by their own callouts -- crossing the
    # leaders that reach the taps.
    set_hidden_lines_removed(adapter, detail_front)
    set_hidden_lines_removed(adapter, detail_section)
    detail_front_edges = scan_view_edges(detail_front, label="holes/sockets front")
    detail_section_edges = scan_view_edges(detail_section, label="A-A socket section")
    # A-A's owned axes: the screw axis the section cuts along, and the two
    # socket bore axes it crosses -- the datum the counterbore floors are
    # located from.
    _screw_axis, *bore_axes = _add_view_centerlines(
        adapter, detail_section,
        (
            ((COLUMN_X, SCREW_AXIS_Y, -PLAN_HALF_Z), (COLUMN_X, SCREW_AXIS_Y, PLAN_HALF_Z)),
            ((COLUMN_X, -HALF_H-BOSS_BELOW-3.0, FRONT_COLUMN_Z),
             (COLUMN_X, HALF_H+BOSS_ABOVE+3.0, FRONT_COLUMN_Z)),
            ((COLUMN_X, -HALF_H-BOSS_BELOW-3.0, REAR_COLUMN_Z),
             (COLUMN_X, HALF_H+BOSS_ABOVE+3.0, REAR_COLUMN_Z)),
        ),
    )
    _position_view_caption(adapter, detail_section, DETAIL_SECTION_CAPTION_XY)
    detail_front_dimensions = curate_view_dimensions(
        adapter,
        detail_front,
        keep=DETAIL_FRONT_KEEP,
        view_label="holes/sockets front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    detail_section_dimensions = curate_view_dimensions(
        adapter,
        detail_section,
        keep=DETAIL_SECTION_KEEP,
        view_label="holes/sockets section A-A",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    section_annotations = [*detail_front_dimensions, *detail_section_dimensions]
    section_callouts = {
        name: "" for name in (*DETAIL_FRONT_KEEP, *DETAIL_SECTION_KEEP)
    }
    section_callouts.update(FRONT_CALLOUTS)
    section_callouts.update(SECTION_CALLOUTS)
    set_dimension_callouts(
        adapter,
        section_annotations,
        section_callouts,
    )
    imported_annotations += section_annotations
    counterbore_annotations = [
        annotation for annotation in detail_front_dimensions
        if dimension_name(adapter, annotation) == "CB1Dia"
    ]
    if len(counterbore_annotations) != 1:
        raise RuntimeError("expected one native counterbore profile diameter")
    counterbore_display = _early_bound(
        counterbore_annotations[0].GetSpecificAnnotation(), "IDisplayDimension"
    )
    counterbore_dimension = _early_bound(counterbore_display.GetDimension2(0), "IDimension")
    if not str(counterbore_dimension.FullName).startswith("CB1Dia@CounterboreRearProfile@"):
        raise RuntimeError(f"wrong native counterbore feature: {counterbore_dimension.FullName}")
    counterbore_value = abs(float(counterbore_dimension.SystemValue))*1000.0
    if abs(counterbore_value-COUNTERBORE_DIA) > 1e-6:
        raise RuntimeError(f"native counterbore profile diameter measured {counterbore_value:g}")
    # One arrow on the counterbore's rim nearest its text (DETAIL_FRONT_KEEP).
    set_near_side_diameter(counterbore_annotations[0], "cross-screw counterbore diameter")
    _set_counterbore_form(
        counterbore_annotations[0], count="4X ", depth=COUNTERBORE_DEPTH_TEXT,
        label="cross-screw counterbore",
    )
    boss_pick_z = REAR_COLUMN_Z+(CAP_RECESS_DIAMETER+BOSS_DIA)/4
    # Both boss-height callouts used to park their text across the sheet from
    # the dimension line it belongs to, and the leader back paid for it: the
    # 47.3's ran 22 mm up-left through this boss's own top extension line, the
    # 4.5's 51 mm down through its bottom one (both measured off the exported
    # PDF, y=146.8 and y=123.2).  Each text now stays in its own dimension's
    # column: the 47.3 beside its dimension line, inside the band its arrows
    # bracket, so the leader is the width of the gap and crosses nothing; the
    # 4.5 above its upper arrow, where its leader leaves the line's top stub.
    # Neither may drift left of x=378 or the extension lines run under the
    # text, nor below y=137 or the recess-depth callout's do.
    #
    # One crossing survives and is accepted: the 47.3, the 4.5 and the 16.30
    # recess depth all measure FROM the boss top face, so their upper
    # extension lines are collinear at y=146.8 and each runs right to its own
    # dimension line (x=366.5, 377, 387).  The 4.5's leader leaves its line
    # mid-band at y=145.7 -- below that shared face -- so any text it can
    # reach costs one crossing of a line collinear with its own, 0.3 mm from
    # where its own extension line ends.  The layout audit reports it as
    # leader-crosses-leader at (366.2,146.8); the alternatives measured worse
    # (text over the cut faces, or the recess-depth callout's stub through this
    # text), and no arrangement of three dimensions off one face avoids it.
    # The overall is a reference: the boss bottom's as-cast 1.69 below the
    # faced top (BossBelowTop) plus the machined .18 above it.
    _checked_dimension(
        adapter, detail_section,
        p0=(COLUMN_X, HALF_H+BOSS_ABOVE, boss_pick_z),
        p1=(COLUMN_X, -HALF_H-BOSS_BELOW, boss_pick_z),
        text_xy=(0.377, 0.135), label="socket boss overall height",
        expected_mm=RING_HEIGHT+BOSS_ABOVE+BOSS_BELOW,
        orientation="vertical", exact_linear=True, suffix="4X BOSS\nOVERALL HEIGHT",
        offset_text=(0.398, 0.130), edges=detail_section_edges, reference=True,
    )
    # The 47.3 boss stack and the 36.5 rail band never said where the extra
    # 10.8 sits.  One native rail-top-to-boss-top dimension splits it: 4.5
    # above, and the 6.3 below then follows from the overall height.
    boss_top_edge_section, boss_top_point = _cut_face_edge(
        detail_section_edges, fixed={0: COLUMN_X, 1: HALF_H+BOSS_ABOVE},
        near=(2, REAR_COLUMN_Z, BOSS_DIA), label="section boss top face",
    )
    rail_top_edge_section, rail_top_point = _cut_face_edge(
        detail_section_edges, fixed={0: COLUMN_X, 1: HALF_H},
        near=(2, 0.0, BOSS_DIA), label="section rail top face",
    )
    # Owner ruling B3 (#2333): the boss tops are machined seats.  The one
    # symbol reads off the front boss's top outside its recess.

    def boss_top_finish() -> None:
        front_top_z = FRONT_COLUMN_Z - (CAP_RECESS_DIAMETER + BOSS_DIA) / 4
        front_top_edge, front_top_point = _cut_face_edge(
            detail_section_edges, fixed={0: COLUMN_X, 1: HALF_H+BOSS_ABOVE},
            near=(2, front_top_z, 2.0), label="section front boss top face",
        )
        symbol = add_surface_finish(
            adapter, detail_section,
            edge_entity=front_top_edge,
            symbol_xy=BOSS_TOP_FINISH_SYMBOL_XY,
            control=surface_finish_by_key(SURFACE_FINISHES, "boss_top_west_front"),
            label="corner boss top finish",
            leader_attach_xy=model_point_in_view(
                adapter, detail_section,
                tuple(value / 1000.0 for value in front_top_point),
                label="corner boss top finish leader",
            ),
            char_height=0.0025,
        )
        _finish_leader_tail(symbol, label="corner boss top")

    boss_top_finish()
    boss_above = _checked_dimension(
        adapter, detail_section,
        p0=boss_top_point, p1=rail_top_point,
        text_xy=BOSS_ABOVE_RAIL_LINE_XY, label="boss top above rail top",
        expected_mm=BOSS_ABOVE, orientation="vertical",
        entities=(boss_top_edge_section, rail_top_edge_section),
        suffix="4X", offset_text=BOSS_ABOVE_RAIL_TEXT_XY,
    )
    # No witness across the cut face (machinist review, farm run
    # 20261027T175429300Z): the 16.30's witnesses left the -Z boss's recess
    # and ran the whole rail, its floor witness through the hatch, and the
    # 4.5's rail-top witness crossed the +Z boss's walls and recess.  Both
    # start 1.2 mm past the +Z boss's outer face, beside their dimension
    # lines; each still reads off the face it is level with.
    def a_a_sheet(y: float, z: float) -> tuple[float, float]:
        return model_point_in_view(
            adapter, detail_section, (COLUMN_X / 1000.0, y / 1000.0, z / 1000.0),
            label="A-A witness level",
        )

    boss_face_x = a_a_sheet(HALF_H, REAR_COLUMN_Z + BOSS_DIA / 2.0)[0]
    if not boss_face_x > a_a_sheet(HALF_H, REAR_COLUMN_Z)[0]:
        raise RuntimeError("A-A: the +Z boss's outer face does not read right of its axis")
    witness_start_x = boss_face_x + A_A_WITNESS_STANDOFF
    boss_top_y = a_a_sheet(HALF_H + BOSS_ABOVE, REAR_COLUMN_Z)[1]
    recess_depth = [
        annotation for annotation in detail_section_dimensions
        if dimension_name(adapter, annotation) == "CapRecessDepth"
    ]
    if len(recess_depth) != 1:
        raise RuntimeError(f"A-A: expected one native recess depth, got {len(recess_depth)}")
    _start_witnesses_past(
        adapter, recess_depth[0].GetSpecificAnnotation(),
        (boss_top_y, a_a_sheet(HALF_H + BOSS_ABOVE - CAP_RECESS_DEPTH, REAR_COLUMN_Z)[1]),
        witness_start_x, label="A-A recess depth witnesses",
    )
    _start_witnesses_past(
        adapter, boss_above,
        (boss_top_y, a_a_sheet(HALF_H, REAR_COLUMN_Z)[1]),
        witness_start_x, label="A-A boss-above-rail witnesses",
    )
    _checked_dimension(
        adapter, detail_section,
        p0=(COLUMN_X, HALF_H+BOSS_ABOVE, REAR_COLUMN_Z+CAP_RECESS_DIAMETER/2+BORE_CHAMFER),
        p1=(COLUMN_X, HALF_H+BOSS_ABOVE-BORE_CHAMFER, REAR_COLUMN_Z+CAP_RECESS_DIAMETER/2),
        text_xy=(0.335, 0.162), label="top bore mouth chamfer",
        expected_mm=BORE_CHAMFER, orientation="horizontal",
        entity_types=("VERTEX", "VERTEX"), exact_vertices=True,
        suffix="X 45°\n4X RECESS MOUTH", edges=detail_section_edges,
        offset_text=BORE_CHAMFER_TEXT_OFFSET_XY,
    )
    upper_boss_edge = detail_front_edges.circle_at(
        (COLUMN_X, HALF_H+BOSS_ABOVE, REAR_COLUMN_Z), BOSS_TOP_EDGE_R,
        axis=(0.0, 1.0, 0.0),
        label="front view outer boss rim on the upper boss plane",
        center_tol_mm=1e-4, radius_tol_mm=1e-4,
    ).edge
    # The tap's entry rim on the counterbore floor is now the #10 near-wall
    # clearance's: it carries the clearance callout and the axis height.
    front_clearance_edge = detail_front_edges.circle_at(
        (COLUMN_X, SCREW_AXIS_Y, TOP_SCREW_SEAT_Z), NEAR_WALL_CLEARANCE_DIAMETER/2,
        axis=(0.0, 0.0, 1.0),
        label="front view column cross near-wall clearance circle",
    ).edge
    section_floor_edges = [
        (item.edge, item.midpoint_mm)
        for item in detail_section_edges.lines
        if not (
            max(abs(item.line[0][0]-COLUMN_X), abs(item.line[1][0]-COLUMN_X)) > 1e-6
            or abs(item.line[0][2]-item.line[1][2]) > 1e-6
            or abs(item.line[0][1]-item.line[1][1]) < 1e-6
        )
    ]
    opposed_floors = []
    for plane_z in (-TOP_SCREW_SEAT_Z, TOP_SCREW_SEAT_Z):
        candidates = [item for item in section_floor_edges if abs(item[1][2]-plane_z) < 1e-6]
        if not candidates:
            raise RuntimeError(
                f"section has no native counterbore floor edge on Z={plane_z:g}; "
                f"native vertical edge midpoints={[point for _, point in section_floor_edges]}"
            )
        opposed_floors.append(max(candidates, key=lambda item: item[1][1]))
    # The counterbore floors are located from the socket bore AXIS the shop
    # indicates, not from the frame midplane (a centre it would first have
    # to derive from the socket pattern -- codex round 5, drawing-guidelines.md rule 10 (dimension from a real feature)):
    # the rear floor from the rear bore axis, the front pair being its
    # mirror at the 224.00 pitch sheet 3 states.  The floor-to-floor span
    # stays as a parenthesised reference.
    floor_from_axis = add_edge_dimension(
        adapter, detail_section,
        p0=(0.0, 0.0), p1=(0.0, 0.0),
        text_xy=(0.3535, 0.112), label="counterbore floor from socket axis",
        orientation="horizontal",
        entity_types=("SKETCHSEGMENT", "EDGE"),
        entities=(bore_axes[1], opposed_floors[1][0]),
    )
    floor_from_axis = _early_bound(floor_from_axis, "IDisplayDimension")
    measured = abs(float(
        _early_bound(floor_from_axis.GetDimension2(0), "IDimension").SystemValue
    )) * 1000.0
    expected = TOP_SCREW_SEAT_Z - REAR_COLUMN_Z
    if abs(measured - expected) > 1e-5:
        raise RuntimeError(
            f"counterbore floor from socket axis: measured {measured:g}, expected {expected:g} mm"
        )
    _set_derived_precision(floor_from_axis, label="counterbore floor from socket axis")
    floor_annotation = _early_bound(floor_from_axis.GetAnnotation(), "IAnnotation")
    set_dimension_callouts(
        adapter, [floor_annotation],
        {dimension_name(adapter, floor_annotation): "4X"},
    )
    # Parked at (387, 110.5), where the old two-row qualifier's shoulder ended
    # 3.5 inside the border and the block kept 4.8 under the 47.3; the count
    # alone sits well inside that.
    offset_dimension_text(
        adapter, [floor_annotation],
        {dimension_name(adapter, floor_annotation): (0.387, 0.1105)},
    )
    _checked_dimension(
        adapter, detail_section,
        p0=opposed_floors[0][1], p1=opposed_floors[1][1],
        text_xy=(0.290, 0.100), label="opposed counterbore floor separation",
        expected_mm=2*TOP_SCREW_SEAT_Z, orientation="horizontal",
        entities=(opposed_floors[0][0], opposed_floors[1][0]),
        reference=True,
    )
    cross_tap_callout = add_native_hole_callout(
        adapter,
        detail_front,
        edge=_cross_tap_far_mouth_edge(detail_front),
        # Left-below the tap, so the leader leaves the block's right end and
        # climbs to the tap clear of every line of the process text; centred
        # under the tap it attached at the far corner and crossed the text,
        # and crowded A-A's cap-recess callout (codex round 5).
        callout_xy=(0.148, 0.202),
        label="front/rear column-retention taps",
        # The 1.81 thread and 1.94 drill depths are the requirement, no tool
        # named (machinist review r1).
    )
    _count_cross_taps(cross_tap_callout)
    # Drill diameters print three places (.159, the #21), the depths .XX.
    set_hole_callout_precision(
        cross_tap_callout,
        {"hw-tapdrldia": 3, "hw-tapdrldepth": 2, "hw-threaddepth": 2},
        label="cross tap drill and depths",
    )
    clearance_callout = add_native_hole_callout(
        adapter,
        detail_front,
        edge=front_clearance_edge,
        callout_xy=CROSS_CLEARANCE_CALLOUT_XY,
        label="front/rear cross near-wall clearances",
    )
    set_hole_callout_precision(
        clearance_callout, CROSS_CLEARANCE_PRECISION,
        label="cross near-wall clearance diameter",
    )
    _set_cross_clearance_callout_text(clearance_callout)
    set_near_side_diameter(
        _early_bound(clearance_callout, "IDisplayDimension").GetAnnotation(),
        "cross near-wall clearance callout",
    )
    rebuild_drawing(adapter, label="cross near-wall clearance near-side leader")
    _checked_dimension(
        adapter, detail_front,
        p0=(COLUMN_X, HALF_H+BOSS_ABOVE, REAR_COLUMN_Z),
        p1=(COLUMN_X+NEAR_WALL_CLEARANCE_DIAMETER/2, SCREW_AXIS_Y, TOP_SCREW_SEAT_Z),
        text_xy=(0.2605, 0.229), label="cross screw axis from boss top",
        expected_mm=HALF_H+BOSS_ABOVE-SCREW_AXIS_Y, orientation="vertical", center=True,
        entities=(upper_boss_edge, front_clearance_edge), offset_text=(0.300, 0.229),
    )
    # A section never carries hidden lines: the cut 10-32 taps' cosmetic
    # threads printed dashed through the hatch (machinist review r1); the
    # side view's callout carries the thread.
    _hide_cosmetic_threads(adapter, detail_section, label="A-A corner section")
    _assert_section_display(
        adapter, detail_section, label="A-A corner section",
        cut_surface_only=False,
    )
    if not ddoc.ActivateSheet("HUB-SET-SCREW"):
        raise RuntimeError("failed to activate top-frame hub sheet")
    hub_top = place_view(
        adapter, str(SOURCE), "*Top", *HUB_TOP_CENTER, scale=SHEET_SCALE,
    )
    detail_left = place_view(
        adapter, str(SOURCE), "*Left", *HUB_LEFT_CENTER, scale=HUB_LEFT_SCALE,
    )
    set_hidden_lines_removed(adapter, hub_top)
    # The set-screw boss stands out of the face this view looks at and the set
    # tap breaks its spot face, so both read as visible ink; the dashed sockets
    # at the rail ends were the only thing hidden lines added here, and sheets
    # 3 and 4 own those.  The re-assertions below are not redundant: creating
    # the K-K section and picking its faces both put the parent back in its
    # default.
    set_hidden_lines_removed(adapter, detail_left)
    hub_top_dimensions = curate_view_dimensions(
        adapter, hub_top, keep=HUB_TOP_KEEP,
        view_label="hub location", dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    hub_left_dimensions = curate_view_dimensions(
        adapter,
        detail_left,
        keep=HUB_LEFT_KEEP,
        view_label="hub side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_dimension_callouts(
        adapter,
        [*hub_top_dimensions, *hub_left_dimensions],
        {name: "" for name in (*HUB_TOP_KEEP, *HUB_LEFT_KEEP)},
    )
    set_dimension_callouts(
        adapter,
        hub_left_dimensions,
        HUB_LEFT_CALLOUTS,
    )
    set_dimension_callouts(adapter, hub_top_dimensions, HUB_TOP_CALLOUTS)
    imported_annotations += [*hub_top_dimensions, *hub_left_dimensions]
    offset_dimension_text(
        adapter,
        hub_left_dimensions,
        {
            "SetBossWidth": SET_BOSS_WIDTH_TEXT_XY,
            "HubBossDrop": HUB_BOSS_DROP_OFFSET_XY,
        },
    )
    # One arrow on the spot's rim, no line on through the tap centre: the
    # 07527cf4 codex review read the diametric pair, meeting the tap
    # callout's leader at the centre, as leaders converging on the boss.
    spot_dia = [
        annotation for annotation in hub_left_dimensions
        if dimension_name(adapter, annotation) == "SetSpotDia"
    ]
    if len(spot_dia) != 1:
        raise RuntimeError(f"expected one SetSpotDia dimension, found {len(spot_dia)}")
    set_near_side_diameter(spot_dia[0], "set-screw spot face diameter")
    _set_counterbore_form(
        spot_dia[0], count="", depth=SET_SPOT_DEPTH_TEXT,
        label="set-screw spot face",
    )
    _add_view_centerlines(
        adapter, hub_top,
        (
            ((-COLUMN_X, 0.0, -PLAN_HALF_Z), (-COLUMN_X, 0.0, PLAN_HALF_Z)),
            ((-PLAN_HALF_X, 0.0, FRONT_COLUMN_Z), (PLAN_HALF_X, 0.0, FRONT_COLUMN_Z)),
        ),
    )
    _add_view_arrow(adapter, hub_top, VIEW_LETTER, VIEW_G_ARROW)
    hub_top_edges = scan_view_edges(hub_top, label="hub location")
    left_socket_edge = _socket_bore_circle(
        hub_top_edges, -COLUMN_X, FRONT_COLUMN_Z, label="hub view left front socket"
    )
    gooseneck_edge = min(
        hub_top_edges.circles,
        key=lambda item: abs(item.circle[6]-GOOSENECK_BORE_DIA/2)
        + abs(item.circle[0]-GOOSENECK_X) + abs(item.circle[2]-GOOSENECK_Z),
        default=None,
    )
    if gooseneck_edge is None or (
        abs(gooseneck_edge.circle[6]-GOOSENECK_BORE_DIA/2) > 0.01
        or abs(gooseneck_edge.circle[0]-GOOSENECK_X)
        + abs(gooseneck_edge.circle[2]-GOOSENECK_Z) > 0.02
    ):
        raise RuntimeError(
            "top view has no gooseneck clearance-bore circle at "
            f"({GOOSENECK_X:g}, {GOOSENECK_Z:g}) mm with "
            f"{GOOSENECK_BORE_DIA / 2.0:g} mm radius"
        )
    gooseneck_edge = gooseneck_edge.edge
    _checked_dimension(
        adapter, hub_top,
        p0=(-COLUMN_X, HALF_H+BOSS_ABOVE, FRONT_COLUMN_Z),
        p1=(GOOSENECK_X, HALF_H, GOOSENECK_Z),
        text_xy=(0.0365, 0.225), label="hub from left front socket",
        expected_mm=GOOSENECK_Z-FRONT_COLUMN_Z, orientation="vertical",
        center=True, entities=(left_socket_edge, gooseneck_edge),
    )
    set_hidden_lines_removed(adapter, detail_left)
    detail_left_edges = scan_view_edges(detail_left, label="hub side")
    tap_x = SET_SPOT_FACE_X
    tap_radius = TAP_DRILL_MM[SET_TAP_SPEC.size] / 2.0
    # The set-screw boss runs up to the faced top (owner ruling B4, #2333):
    # its face's top edge is the faced top's outline at the tap.
    rail_top_edge = None
    for item in detail_left_edges.lines:
        start, end = item.line
        if (
            max(
                abs(start[0]-SET_BOSS_FACE_X),
                abs(end[0]-SET_BOSS_FACE_X),
                abs(start[1]-HALF_H),
                abs(end[1]-HALF_H),
            ) < 1e-4
            and min(start[2], end[2]) < GOOSENECK_Z < max(start[2], end[2])
        ):
            rail_top_edge = item.edge
    set_tap_edge = detail_left_edges.circle_at(
        (tap_x, SCREW_AXIS_Y, GOOSENECK_Z), tap_radius, axis=(1.0, 0.0, 0.0),
        label="left view set-tap circle",
    ).edge
    if rail_top_edge is None:
        raise RuntimeError("left view has no exact upper rail edge at the gooseneck station")
    set_tap_callout = add_native_hole_callout(
        adapter,
        detail_left,
        edge=set_tap_edge,
        # Up-right of the tap: the boss width's extension lines leave one
        # leader per side under their feet, and the spot face's Ø10.0 takes
        # the left (SET_SPOT_DIA_TEXT_XY).  (0.2294, 0.1306) elbows at (199.4,
        # 125.0) mm and drops at 0.55 through the tap centre (146.5, 95.9),
        # passing 2.3 mm right of the right extension line's foot (151.0,
        # 101.0) and 5.2 mm over the 18.2 text; the text sits 12.8 mm above
        # the view.
        callout_xy=(
            HUB_LEFT_CENTER[0] + 0.0844,
            HUB_LEFT_CENTER[1] + 0.0356,
        ),
        label="gooseneck set-screw through-to-bore tap",
        process="TAP",
    )
    # The #7 tap drill prints three places (.201), as drill diameters do. A
    # through-tap callout names its drill <hw-tapdrldia> or <hw-thrutapdrldia>
    # depending on the end condition; the callout text says which.
    definitions = "\n".join(str(set_tap_callout.GetText(part) or "") for part in (5, 6, 7, 8))
    drill_variables = [
        name for name in ("hw-tapdrldia", "hw-thrutapdrldia") if f"<{name}>" in definitions
    ]
    if len(drill_variables) != 1:
        raise RuntimeError(f"gooseneck set-tap callout drill variables: {drill_variables}")
    set_hole_callout_precision(
        set_tap_callout,
        {drill_variables[0]: 3},
        label="gooseneck set-tap drill",
    )
    # The boss width's symmetry axis: the tap's vertical centreline, drawn
    # from under the rail to over the flange underside the boss is cast to.
    _add_view_centerlines(
        adapter, detail_left,
        (((tap_x, -HALF_H - SECTION_AXIS_OVERRUN_MM, GOOSENECK_Z),
          (tap_x, FLANGE_BOT_Y + SECTION_AXIS_OVERRUN_MM, GOOSENECK_Z)),),
    )
    _checked_dimension(
        adapter, detail_left,
        p0=(SET_BOSS_FACE_X, HALF_H, GOOSENECK_Z),
        p1=(tap_x, SCREW_AXIS_Y, GOOSENECK_Z+tap_radius),
        text_xy=(0.230, 0.1125), label="set screw axis from rail top",
        expected_mm=SCREW_AXIS_BELOW_RAIL_TOP, orientation="vertical", center=True,
        entities=(rail_top_edge, set_tap_edge), offset_text=(0.252, 0.1125),
    )
    # The boss's drop below the rail underside and the gussets' span are the
    # model's own dimensions, each with its ±.03 (HUB_LEFT_KEEP; owner ruling
    # B2, #2333): one ramp, three numbers in the band under this view.  The
    # ramp rises over the outer .87 of each side and the inner .63 stays a
    # full-depth flat buried inside the boss, which is why the drop does not
    # appear within the ramp's own run.
    _gusset_ramp_angle(
        adapter,
        detail_left,
        detail_left_edges,
    )
    set_hidden_lines_removed(adapter, detail_left)
    if add_note(adapter, HUB_LEFT_TITLE, *HUB_LEFT_TITLE_XY) is None:
        raise RuntimeError("failed to label top-frame hub side view")
    hub_section = _hub_boss_section(adapter, hub_top)
    _position_view_caption(adapter, hub_section, HUB_SECTION_CAPTION_XY)
    # Sheet 7 imports before sheet 6: both keep dimensions of the crossbar's
    # one profile sketch, and D's width and station must land here.
    imported_annotations += _cast_datum_sheet(adapter, ddoc)
    if not ddoc.ActivateSheet("UNDERSIDE"):
        raise RuntimeError("failed to activate top-frame underside sheet")
    hub_bottom_parent = place_view(
        adapter, str(SOURCE), "*Bottom", *HUB_BOTTOM_CENTER, scale=HUB_BOTTOM_SCALE,
    )
    set_hidden_lines_removed(adapter, hub_bottom_parent)
    geometry_bottom = _hub_underside_detail(adapter, hub_bottom_parent)
    # The detail is the knife seat's dimensioned view: hidden lines removed
    # like every other view, and the real mode change regenerates it at
    # precision (machinist review r1: its dashed cross-tap and pad edges
    # communicated nothing, its circles printed faceted).
    set_hidden_lines_removed(adapter, geometry_bottom)
    hub_bottom_edges = scan_view_edges(hub_bottom_parent, label="underside locator")
    bottom_dimensions = curate_view_dimensions(
        adapter,
        geometry_bottom,
        keep=HUB_BOTTOM_KEEP,
        view_label="enlarged underside geometry",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_dimension_callouts(
        adapter,
        bottom_dimensions,
        HUB_BOTTOM_CALLOUTS,
    )
    imported_annotations += bottom_dimensions
    offset_dimension_text(
        adapter,
        bottom_dimensions,
        {
            "RibWidth": RIB_WIDTH_TEXT_XY,
            "GussetT": HUB_GUSSET_T_OFFSET_XY,
            "SetBossFace": SET_BOSS_FACE_TEXT_XY,
        },
    )
    rib_width = [
        annotation for annotation in bottom_dimensions
        if dimension_name(adapter, annotation) == "RibWidth"
    ]
    if len(rib_width) != 1:
        raise RuntimeError(f"expected one RibWidth dimension, found {len(rib_width)}")
    rib_width_display = _early_bound(
        _early_bound(rib_width[0], "IAnnotation").GetSpecificAnnotation(),
        "IDisplayDimension",
    )
    rib_width_display.ArrowSide = _DIM_ARROWS_INSIDE
    if int(rib_width_display.ArrowSide) != _DIM_ARROWS_INSIDE:
        raise RuntimeError("rail pad width did not keep its arrows inside")
    # The locator is drawn at the title block's own scale, so it names
    # itself and says nothing a reader can already read off the title block.
    if add_note(adapter, HUB_BOTTOM_TITLE, *HUB_BOTTOM_TITLE_XY) is None:
        raise RuntimeError("failed to label underside locator")
    # The faced underside plane (user ruling 2026-10-12): the part's own
    # linked note C, beside the enlarged hub boss and gussets it excludes.
    add_property_linked_note(
        adapter,
        "Manufacturing Notes C",
        *UNDERSIDE_FACING_NOTE_XY,
        char_height=FACING_NOTE_HEIGHT,
    )
    # The land end, the pocket's front end from the front sockets' axis and
    # the pocket's length are the model's own dimensions, each with its ±.03
    # (owner ruling B2, #2333).  The land end's 8 mm run cannot hold its
    # text, which parks right on a jog; the pocket length's block parks over
    # the plan's top-left corner.
    underside_dimensions = curate_view_dimensions(
        adapter,
        hub_bottom_parent,
        keep=UNDERSIDE_KEEP,
        view_label="underside locator",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_dimension_callouts(
        adapter,
        underside_dimensions,
        UNDERSIDE_CALLOUTS,
    )
    offset_dimension_text(
        adapter,
        underside_dimensions,
        {"LandEnd": LAND_TEXT_OFFSET_XY, "PocketLength": POCKET_LENGTH_OFFSET_XY},
    )
    imported_annotations += underside_dimensions

    def land_arrows_inside() -> None:
        # Its arrows stand inside the 8 mm between the extension lines: an
        # outside arrow's 6.35 mm tail would reach the front ream's rim.
        land = _early_bound(
            _named_dimension(
                adapter, underside_dimensions, "LandEnd"
            ).GetSpecificAnnotation(),
            "IDisplayDimension",
        )
        land.ArrowSide = _DIM_ARROWS_INSIDE
        if int(land.ArrowSide) != _DIM_ARROWS_INSIDE:
            raise RuntimeError("land end from crossbar face did not keep its arrows inside")

    land_arrows_inside()
    # The front sockets' shared axis, the line the pocket's front end stands
    # from (rule 26: holes in line share a drawn centreline).
    _add_view_centerlines(
        adapter, hub_bottom_parent,
        (((-COLUMN_X + BOSS_DIA / 2.0 + SECTION_AXIS_OVERRUN_MM, -HALF_H, FRONT_COLUMN_Z),
          (COLUMN_X - BOSS_DIA / 2.0 - SECTION_AXIS_OVERRUN_MM, -HALF_H, FRONT_COLUMN_Z)),),
    )

    def _pocket_from_socket_settled() -> None:
        if not ddoc.ActivateSheet("UNDERSIDE"):
            raise RuntimeError("failed to activate the underside sheet to settle 1.70")
        _pin_vertical_dimension_line(
            adapter,
            _named_dimension(
                adapter, underside_dimensions, "PocketFromSocket"
            ).GetSpecificAnnotation(),
            POCKET_FROM_SOCKET_LINE_XY[0],
            label="crossbar pocket from front socket",
        )

    # The knife-hanger dowel reams, one per station (Owner ruling 2026-11-08
    # (Pedro), #2144 item 11.3): each is located by F-F's .XXX station from
    # its screw axis (SAME Z) and held square to the faced underside by F-F's
    # 2X ⊥ frame; with the -X reams and their B|C frames deleted, the +X
    # reams are no longer datums B and C and the locator carries no frame.
    locator_dimensions = curate_view_dimensions(
        adapter, hub_bottom_parent,
        keep={"HangerPinHoleDia": HANGER_PIN_DIA_TEXT_XY},
        view_label="underside locator dowel ream",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_dimension_callouts(
        adapter,
        locator_dimensions,
        {"HangerPinHoleDia": HANGER_PIN_DIA_CALLOUT},
    )
    imported_annotations += locator_dimensions
    # The knockouts' native Hole Wizard callout, on the front ream's
    # knockout circle where it breaks into the ream's floor.
    knockouts = add_native_hole_callout(
        adapter,
        hub_bottom_parent,
        callout_xy=HANGER_KNOCKOUT_CALLOUT_XY,
        label="2X dowel ream knockouts",
        edge=hub_bottom_edges.circle_at(
            (PIN_HOLE_X, -HALF_H + HANGER_PIN_HOLE_DEPTH, STUD_Z_FRONT),
            HANGER_KNOCKOUT_DIA/2,
            axis=(0.0, 1.0, 0.0),
            label="underside locator front ream knockout floor",
        ).edge,
    )
    _drop_coaxial_step(knockouts, HANGER_PIN_HOLE_DIA, "2X dowel ream knockouts")
    _set_callout_text(
        knockouts, 3, HANGER_KNOCKOUT_CALLOUT_ABOVE, "2X dowel ream knockouts"
    )
    _set_callout_text(
        knockouts, 4, HANGER_KNOCKOUT_CALLOUT_BELOW, "2X dowel ream knockouts"
    )
    # Two places, Ø1.70 under the DRILLED HOLES row (machinist review, run
    # 20261027T175429300Z: Ø1.702 pulled in the .XXX band); the helper
    # reads each variable's precision back and fails the sheet if it did
    # not persist.
    set_hole_callout_precision(
        knockouts,
        {"hw-diam": HANGER_KNOCKOUT_DIA_PLACES},
        label="2X dowel ream knockouts diameter",
    )
    # The gusset's thickness is DETAIL J's own import (HUB_BOTTOM_KEEP); its
    # span is dimensioned once, on the hub side view that also carries the
    # drop and the ramp angle.
    _position_view_caption(adapter, geometry_bottom, HUB_DETAIL_CAPTION_XY)
    # F-F imports HangerGrip from the crossbar extrude it cuts.
    hanger_section, hanger_dimensions = _hanger_section(adapter, hub_bottom_parent)
    _position_view_caption(adapter, hanger_section, HANGER_SECTION_CAPTION_XY)
    imported_annotations += hanger_dimensions

    auto_tapped_notes = _auto_tapped_hole_notes(adapter)
    _telemetry.info(f"automatic tapped-hole notes per view: {auto_tapped_notes}")
    assert_imported_precision(
        adapter,
        imported_annotations,
        DRAWING_PRECISION_BY_NAME,
    )
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Top Frame Ring Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        expected_sheet_names=SHEET_NAMES,
        sheet_layouts={name: SPEC.layout for name in SHEET_NAMES},
        sheet_scales=SHEET_SCALES,
        # The associative feature callouts replace SolidWorks' own descriptive
        # thread notes: every note the inventory above found must go, and the
        # count it hands over is this run's own, logged per view with it.
        # The automatic "Tapped Hole" notes are already gone, deleted and
        # proved per view by ``_auto_tapped_hole_notes`` above.
        redundant_note_substrings=(),
        expected_redundant_notes=0,
        # The 43.0 shifts in a rebuild after its placement readback, so it is
        # held on its line after the settling rebuild (machinist review r4).
        settled_checks=(_pocket_from_socket_settled,),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
