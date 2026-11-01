r"""Create the eight-sheet paper-drive assembly drawing (MHA-PD-00).

Sheet 1 keeps the Front/Right/Isometric views of the whole paper drive and
balloons the chain and the spare sprocket on the isometric. Sheet 2 carries
a ballooned isometric of the transgear (the hanger, the latch, the disc cluster
and the knob stack) and the hanger pivot's section. Sheet 3 draws the hanger,
the disc cluster and the knob stack apart along their axes on
PAPER_DRIVE_EXPLODED, seen from above, and balloons every part it shows.
Sheet 4 balloons the bar, its clamps and the platen group on
PAPER_DRIVE_EXPLODED and prints their steps. Sheet 5 prints the transgear's
assembly steps and VIEW K, the plate's knob-bore setting from the arm's pin bore as the
assembly's own model dimensions; sheet 6 continues the steps; sheet 7 prints the chain fit-up
(CONTRACT-paper-drive.md §13.2). Sheet 8 carries the complete native BOM,
split horizontally into two pieces at measured row heights, and an assembly
reference. The BOM identifies the current inch
reducer, finite stock-form integral pinions and rack/backer; sheet 1 gives the
selected chain ratio's reference paper travel. Gear cutting data stays on the
gear sheets. The chain fit-up includes the actual loaded collar/disc overlap
inspection with the trial platen removed and the operating latch pose held;
nominal model clearance does not replace that shop inspection. Engaged feed
uses the source-qualified inward-rounded cut-end operating window, not
unbounded platen travel or nominal first-gap phasing. Build-time formatting
reads the verified frozen isolated-feed-datum report, then guards the complete
located paper sweep; imports require no packet and never run a proof. This
conditional MODEL scope is not whole-unit SHAKE/I+B or shop-hardware admission.
Every step is numbered by ``pd_paper_drive_assembly_steps``; values retain
their owning specs and actual critical gear/seat/load inspections remain required.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import json
import math
import sys
import textwrap
from typing import Any, Callable, Iterable, Sequence

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    dimension_name,
    place_view,
    view_name,
)

import _chain as chain
from _check import check
from _com import _early_bound
from _component_references import component_identity
from sh_vn_chain_link_spec import (
    INNER_LINK_BOM_DESCRIPTION,
    INNER_LINK_CONFIGURATION,
    OUTER_LINK_BOM_DESCRIPTION,
    OUTER_LINK_CONFIGURATION,
)
import _config
from _drawing_balloon_display import rendered_balloon_circle
from _drawing_balloons import (
    BalloonAnchor,
    BalloonLanding,
    _anchor_model_points,
    _shown_instances,
    _view_component_leaves,
    _view_explode_offsets,
    add_component_bom_balloons,
    assert_balloon_landings,
    isolate_drawing_view_components,
)
from _drawing_common import (
    _SW_SHADED_EDGES,
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_high_quality_shaded_with_edges,
)
from _drawing_layout_check import LeaderSegment, find_leader_leader_crossings
from _drawing_leader_notes import add_leader_note
from _drawing_projection import model_points_in_view
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME, DrawingLayout
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision
from _drawing_hidden_sketches import _show_base_view_sketches
from _drawing_sections import create_section_view
from _drawing_sheets import create_blank_drawing_sheets
from _drawing_tables import (
    BomSnapshot,
    _bom_column_hidden_at,
    _bom_physical_columns,
    _bom_mutable_visibility_index,
    bom_row_identities,
    insert_bom_table,
    validate_bom_number_property,
)
from _drawing_view_configuration import (
    SIMPLIFIED_VIEW_CONFIGURATION,
    ViewRole,
    apply_view_configuration,
    assert_full_detail_view,
    set_view_exploded_state,
    view_configuration,
)
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _pd_paper_drive_explode import exploded_view_name
from _section_axis import position_section_caption
from _session import run_build
import _telemetry
from _column_clamp_interface import BAR_DEPTH
import pd_latch_hook_geometry as hook_geometry
import paper_drive_rack_setup as rack_setup
import pd_paper_drive_assembly_steps as steps
import pd_paper_drive_knob_setting_spec as knob_setting
import pd_paper_drive_cluster_float_spec as cluster_float
import pd_paper_drive_explode_spec as explode
import pd_platen_guide_spec as platen_guide
import pd_platen_spec as platen
import pd_support_bar_spec as support_bar
import pd_transgear_arm_geometry as arm_geometry
import pd_transgear_disc_hub_geometry as hub_geometry
import pd_transgear_disc_hub_spec as hub
import pd_transgear_drive_collar_spec as collar
import pd_transgear_knob_cup_spec as knob_cup
import pd_transgear_knob_shaft_spec as knob_shaft
import pd_transgear_removable_spec as sprocket
import _sprocket_seat_geometry as seat_geometry
import transgear_cluster_fit as cluster_fit
import transgear_hanger_joints as joints
import pd_vn_transgear_arm_plate_screw_spec as plate_screw
import pd_vn_transgear_disc_screw_spec as disc_screw
import pd_vn_transgear_knob_cup_pin_spec as cup_pin
import pd_vn_transgear_knob_drive_pin_spec as drive_pin
import pd_vn_transgear_pivot_screw_spec as pivot_screw
import pd_vn_transgear_pivot_spring_spec as spring
import _gear_quality as quality
import pd_rack_pinion_spec as disc
import pd_transgear_feed_pinion_spec as feed_pinion
import pd_vn_transgear_arm_plate_locating_pin_spec as plate_locating_pin
import _transgear_arm_plate_locating_interface as plate_locating_interface
from paper_drive_rack_travel import OPERATING_LIMIT_PLACES, RackOperatingDomain


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["pd_paper_drive_assembly"]
ARTIFACT_STEM = SPEC.artifact_stem
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

# Native balloon membership is independent of the simplified rendered reference.
BOM_CONFIGURATION = "Default"

SHEET_NAMES = (
    "ASSEMBLED VIEWS",
    "TRANSGEAR VIEWS",
    "TRANSGEAR EXPLODED",
    "PLATEN AND SUPPORT",
    "ASSEMBLY AND FIT-UP",
    "ASSEMBLY AND FIT-UP (CONT.)",
    "CHAIN FIT-UP",
    "BILL OF MATERIALS",
)
if SPEC.layout is not DrawingLayout.LANDSCAPE:
    raise AssertionError("the paper-drive sheet coordinates are landscape")
SHEET_LAYOUTS = {name: DrawingLayout.LANDSCAPE for name in SHEET_NAMES}

# --- sheet 1: the whole paper drive, front, right and isometric -------------
# Farm run 20261001T142942518Z placed the isometric at 1:3 and read its
# outline 187.7 mm tall (ring 221.7 > the 198.0 room); its width passed. The
# outline is the model's projected box, about 1.4x the ink the 1:5 render
# showed, and SolidWorks pads it by a fixed sheet-space margin, so a rescale
# is read back, never predicted (step_down_to_fit). At 1:4 the content alone
# is 140.8 tall, its ring 174.8 inside the room. The front and right views
# (1:5 ink 94 x 59 and 14 x 58 mm) grow to 118 x 74 and 18 x 73 above the
# free lower-left field, the isometric right of them over the title block.
ASSEMBLED_SCALE = (1.0, 4.0)
FRONT_CENTER = (0.095, 0.190)
RIGHT_CENTER = (0.205, 0.190)
ISO_CENTER = (0.330, 0.170)
# The isometric steps down to 1:5 if its native ring overflows at 1:4. It is
# the full-detail view, which references Default at every scale.
ISO_SCALE_LADDER = (ASSEMBLED_SCALE, (1.0, 5.0))
# The isometric's balloon ring: left of it the right view, below it the
# title block (top 0.066), the sheet's drawing border round the rest.
ISO_RING_LIMITS = (0.235, 0.069, 0.418, 0.267)
ASSEMBLED_CAPTION_XY = (0.018, 0.120)

# --- sheet 8: full qualified Numbers and two native BOM pieces ---------------
# f353's 22 mm Number column wrapped the identities: the native audit measured
# the unsplit table 437.2384 mm high, not the requested rows' nominal height.
# Use the drive-train's proven column widths without changing table text size;
# choose the split only after text, widths and row heights have rebuilt.
BOM_COLUMN_WIDTHS = {
    "item": 0.012,
    "part": 0.048,
    "description": 0.118,
    "quantity": 0.012,
}
BOM_DESCRIPTION_MAX_CHARS = 41
BOM_ROW_HEIGHT = 0.0055
BOM_ANCHOR = (0.018, 0.262)
BOM_SECOND_ANCHOR = (
    BOM_ANCHOR[0] + sum(BOM_COLUMN_WIDTHS.values()) + 0.008,
    BOM_ANCHOR[1],
)
BOM_REFERENCE_SCALE = (1.0, 10.0)
BOM_REFERENCE_CENTER = (0.060, 0.065)
BOM_REFERENCE_LIMITS = (0.018, 0.028, 0.095, 0.104)
BOM_REFERENCE_CAPTION_XY = (0.100, 0.088)
BOM_REFERENCE_CAPTION = (
    "REFERENCE 1:10\n"
    f"BALLOONS: SHEETS 1-{SHEET_NAMES.index('PLATEN AND SUPPORT') + 1}\n"
    f"ASSEMBLY: SHEETS {SHEET_NAMES.index('PLATEN AND SUPPORT') + 1}-"
    f"{SHEET_NAMES.index('CHAIN FIT-UP') + 1}"
)
# The ASME B landscape sheet's inner border, bottom edge, and the clearance
# the BOM keeps above it.
SHEET_INNER_BORDER_BOTTOM = 0.0127
BOM_BORDER_CLEARANCE = 0.003
# The transgear alone at 2:3, above the title block. The v40 sheet 2
# (594749aec's layout) printed its outline at x 285.3 to 396.6, y 111.2 to
# 244.8 mm: a ring top of 261.8 in the 262.0 limit. The one-piece MHA-PD-14
# hook's ear stands at machine x 77.6, 17.6 further +X than the bracket's
# flap. The isometric looks along (-1, +1, -1), so sheet up is 0.408 x and
# sheet right -0.707 x, and the outline grew to x 278.5 and y 248.8 (farm run
# of 9055bc155: ring top 265.8). The view is 137.6 mm tall, so its ring of
# 171.6 fits the field's 172.0 only when it is centred: transgear_view_shift
# moves it down.
TRANSGEAR_VIEW_SCALE = (2.0, 3.0)
TRANSGEAR_VIEW_CENTER = (0.346, 0.170)
BALLOON_MARGIN = 0.012
TRANSGEAR_CAPTION_XY = (0.222, 0.082)
# Sheet 2 retains the established model fields when the BOM moves to sheet 8.
# Its balloon circles still clear the drawing border and caption fields.
SHEET_TWO_RING_LIMITS = (0.185, 0.090, 0.415, 0.262)
BALLOON_RING_REACH = BALLOON_MARGIN + 0.005
# The hanger pivot (step 13, rules 9 and 22) in sheet 2's empty left field,
# clear of the isometric's field (SHEET_TWO_RING_LIMITS[0]). A 1:1 *Top
# locator, cropped to a circle on the MHA-PD-VN-57 axis and showing only the
# pivot stack, carries cutting line A-A along that axis. SECTION A-A at 2:1
# shows every part of the stack cut (the spring under the head and the arm
# too, so no hidden lines are needed) and balloons each part. It is cropped
# to a circle in the same way. A *Top view puts machine -Z (the bar's front face) down
# the sheet, so the cutting line runs vertically through the circle's centre.
# Points are in the screw's part frame (mm): the head's underside at y 0, the
# shoulder down -Y seated on the bar's back face, so the bar's front face is
# SHOULDER_LEN + BAR_DEPTH down.
PIVOT_VIEW_ORIENTATION = "*Top"
# Model mm about the stack's midpoint that frame the head to the front face.
PIVOT_FRAME_RADIUS_MM = 15.0
PIVOT_LOCATOR_SCALE = (1.0, 1.0)
PIVOT_LOCATOR_CENTER = (0.150, 0.228)
PIVOT_LOCATOR_RADIUS = (
    (PIVOT_FRAME_RADIUS_MM + 1.0) * PIVOT_LOCATOR_SCALE[0] / PIVOT_LOCATOR_SCALE[1]
) / 1000.0
# The cutting line's half-length on the sheet: at least 1 mm past the stack
# each way along the axis (a full section's line must span the parts it cuts),
# inside the locator's circle.
PIVOT_CUT_HALF = (
    PIVOT_FRAME_RADIUS_MM * PIVOT_LOCATOR_SCALE[0] / PIVOT_LOCATOR_SCALE[1] / 1000.0
)
PIVOT_SECTION_LABEL = "A"
PIVOT_SECTION_SCALE = (2, 1)
PIVOT_SECTION_CENTER = (0.095, 0.120)
PIVOT_SECTION_RADIUS = (
    PIVOT_FRAME_RADIUS_MM * PIVOT_SECTION_SCALE[0] / PIVOT_SECTION_SCALE[1] / 1000.0
)
# The native "SECTION A-A" caption goes under the section and its balloons.
PIVOT_SECTION_CAPTION_XY = (
    PIVOT_SECTION_CENTER[0],
    PIVOT_SECTION_CENTER[1] - PIVOT_SECTION_RADIUS - BALLOON_RING_REACH - 0.010,
)
PIVOT_SCREW_INSTANCE = "pd-vn-transgear-pivot-screw-1"
PIVOT_VIEW_INSTANCES = frozenset(
    {
        "pd-support-bar-1",
        PIVOT_SCREW_INSTANCE,
        "pd-vn-transgear-pivot-spring-1",
        "pd-transgear-pivot-spacer-1",
        "pd-transgear-arm-1",
    }
)
PIVOT_FRONT_FACE_Y = -(pivot_screw.SHOULDER_LEN + BAR_DEPTH)
PIVOT_VIEW_CENTRE_MM = (0.0, (pivot_screw.HEAD_H + PIVOT_FRONT_FACE_Y) / 2.0, 0.0)
if (pivot_screw.HEAD_H - PIVOT_FRONT_FACE_Y) / 2.0 + 1.0 > PIVOT_FRAME_RADIUS_MM:
    raise AssertionError("the pivot circles must frame head to front face")
# The section's balloons. Farm run 20261015T101105899Z: in this assembly
# section, IView lists no edges for the cut components, and no hit test at the
# support bar's extreme points found its ink. So add_component_bom_balloons
# cannot attach to the section. Each part's item number from the validated BOM
# is instead a circular-balloon pointer note (add_leader_note) whose tip lies
# inside that part's own cut face. The stack is coaxial, so every tip is
# written in the screw's part frame (mm), (y along the axis, r off it), on the
# section plane:
# head underside y 0; spring (a cone from its ID rim under the head to its OD
# rim on the spot-face floor); the arm from that floor to its front face on the
# spacer; the spacer on the shoulder; and the bar from its back face at
# -SHOULDER_LEN to its front face. Sides alternate down the stack, so each
# column's leaders are in the same order as their tips. The bar's balloon
# stays left, clear of the stake note right of the axis at the front face.
_PIVOT_FLOOR_Y = -spring.MODEL_HEIGHT
_PIVOT_ARM_FRONT_Y = -(pivot_screw.SHOULDER_LEN - joints.SPACER.LENGTH)
PIVOT_BALLOON_TIPS = (
    (
        "pd-vn-transgear-pivot-screw",
        "left",
        pivot_screw.HEAD_H / 2.0,
        (pivot_screw.SOCKET_AF / math.sqrt(3.0) + pivot_screw.HEAD_DIA / 2.0) / 2.0,
    ),
    (
        "pd-vn-transgear-pivot-spring",
        "right",
        -spring.MODEL_HEIGHT / 2.0,
        (spring.ID + spring.OD) / 4.0,
    ),
    (
        "pd-transgear-arm",
        "left",
        (_PIVOT_FLOOR_Y + _PIVOT_ARM_FRONT_Y) / 2.0,
        (arm_geometry.PIVOT_BORE_DIA / 2.0 + arm_geometry.SPOT_FACE_DIA / 2.0) / 2.0,
    ),
    (
        "pd-transgear-pivot-spacer",
        "right",
        _PIVOT_ARM_FRONT_Y - joints.SPACER.LENGTH / 2.0,
        (joints.SPACER.BORE_DIA + joints.SPACER.OD) / 4.0,
    ),
    (
        "pd-support-bar",
        "left",
        -pivot_screw.SHOULDER_LEN - BAR_DEPTH / 2.0,
        support_bar.PIVOT_TAP_CSK_DIA / 2.0 + 2.0,
    ),
)
if {stem for stem, *_ in PIVOT_BALLOON_TIPS} != {
    name.rsplit("-", 1)[0] for name in PIVOT_VIEW_INSTANCES
}:
    raise AssertionError("the pivot section balloons exactly its shown families")
# Balloon columns: centres BALLOON_MARGIN off the section's circle, as on the
# other rings, at least one pitch apart within a column. Farm run
# 20261015T110833827Z: at 9 mm two balloons (3.5 mm tall boxes) stood 5.49
# apart, under the layout audit's 5.53 mm row pitch, and read as one block
# (merged-blocks); 12 mm leaves 8.4.
PIVOT_BALLOON_GAP = BALLOON_MARGIN
PIVOT_BALLOON_PITCH = 0.012
_SW_BALLOON_CIRCULAR = 1  # swBalloonStyle_e.swBS_Circular, the BOM balloons'
_SW_BALLOON_FIT_2_CHARS = 2  # swBalloonFit_e, the BOM balloons' size


def spread_balloon_column(tip_ys: Sequence[float], pitch: float) -> list[float]:
    """Balloon heights for one column whose tips sit at ``tip_ys`` (top
    down): the same order, at least ``pitch`` apart, centred on the tips."""
    if any(b > a for a, b in zip(tip_ys, tip_ys[1:])):
        raise ValueError(f"column tips must run top down: {tip_ys!r}")
    ys: list[float] = []
    for tip in tip_ys:
        ys.append(tip if not ys else min(tip, ys[-1] - pitch))
    shift = (sum(tip_ys) - sum(ys)) / len(ys) if ys else 0.0
    return [y + shift for y in ys]


PIVOT_VIEW_REF = (
    f"SECTION {PIVOT_SECTION_LABEL}-{PIVOT_SECTION_LABEL}, "
    f"SHEET {SHEET_NAMES.index('TRANSGEAR VIEWS') + 1}"
)
# Two stake points, opposite across the tap so the cut plane through the axis
# shows both: the section's leader names the one right of the axis.
PIVOT_STAKE_POINTS_TEXT = "2 OPPOSITE POINTS"
PIVOT_CAPTION = (
    "THE HANGER PIVOT AS FITTED IN\n"
    f"STEP {steps.step_number('hanger-pivoted')}: STAKE THE TAP MOUTH ONTO\n"
    f"THE SCREW TIP AT {PIVOT_STAKE_POINTS_TEXT}"
)
PIVOT_CAPTION_XY = (0.022, 0.255)
# The lock in the view (rule 23; the r5 machinist review of SECTION A-A): a
# pointer into the bar's cut face at the tap's front mouth, right of the axis,
# 0.5 mm in from the front face and 0.6 mm outside the countersink's rim, so
# it lands in the metal the punch moves. (y, r) in the screw's frame (mm).
PIVOT_STAKE_TIP = (
    PIVOT_FRONT_FACE_Y + 0.5,
    support_bar.PIVOT_TAP_CSK_DIA / 2.0 + 0.6,
)
PIVOT_STAKE_NOTE = f"STAKE TAP MOUTH,\n{PIVOT_STAKE_POINTS_TEXT}"
# The note stands just outside the section's circle at the front-face end,
# its left edge PIVOT_STAKE_NOTE_SIDE_GAP right of the tip, so its leader
# leaves the text's left end and runs up (or down) and left to the tip without
# crossing it. Farm r6 review: centred on the axis, with the tip right of
# centre, SolidWorks attached the leader at the text's right end and the
# leader ran back through "MOUTH,". The note's top-left is the INote position
# (r6: 0.073, 0.086 asked, text top-left at 0.0731, 0.0860).
PIVOT_STAKE_NOTE_SIDE_GAP = 0.006
PIVOT_STAKE_NOTE_GAP = 0.004
PIVOT_STAKE_NOTE_LINE_PITCH = 0.0045


def pivot_stake_note_xy(tip_x: float, front_side: float) -> tuple[float, float]:
    """Top-left sheet point of the stake note: right of the leader's tip at
    sheet x ``tip_x``, just outside the section's circle on the front face's
    side (``front_side`` +1.0 when the front face is above the circle's
    centre on the sheet, -1.0 below)."""
    if front_side not in (1.0, -1.0):
        raise ValueError(f"front_side must be +1.0 or -1.0, not {front_side!r}")
    offset = PIVOT_SECTION_RADIUS + PIVOT_STAKE_NOTE_GAP
    if front_side > 0.0:
        lines = PIVOT_STAKE_NOTE.count("\n") + 1
        top = PIVOT_SECTION_CENTER[1] + offset + lines * PIVOT_STAKE_NOTE_LINE_PITCH
    else:
        top = PIVOT_SECTION_CENTER[1] - offset
    return (tip_x + PIVOT_STAKE_NOTE_SIDE_GAP, top)


CROP_NO_ERROR = 1  # swCropViewErrors_e.swCropViewErrors_NoError

# --- sheet 3: the transgear drawn apart, two isometric views ------------------
# PAPER_DRIVE_EXPLODED moves the hanger's plate, the disc cluster and the knob
# stack along their own axes (machine Z, and the cup's cross pin along X).
# Farm runs 20261024T014330502Z and 20261024T021816733Z drew them from above:
# every Z-axis circle and every round of the turned arm lay edge-on, and the
# balloon leaders on them re-solved along the line (0.85 and 0.26 mm). The
# isometric draws those circles as ellipses, as on sheet 2, but there the disc
# would cover the knob stack (the two axes stand 29.5 mm apart on the sheet).
# So each axis is its own view: the hanger and the knob stack on its shaft
# left of the title block, the disc cluster on its pin above the caption.
# Only those transgear instances show: the pivot stack is SECTION A-A's and
# the latch hook stays on the bar. The views are full-detail for the same
# reason as sheet 4's (the Default BOM). Both are drawn at 2:3, sheet 2's
# transgear scale, and never rescaled (drawing guidelines rule 15); an outline
# past its field is refused, not shrunk. An isometric's native outline is its
# projected box, not its ink: farm run 20261024T025815061Z read the knob
# stack and hanger's at 1:1 as 247.3 x 226.8 mm, past any 1:1 field here.
TRANSGEAR_EXPLODED_ORIENTATION = "*Isometric"
TRANSGEAR_EXPLODED_SCALE = (2.0, 3.0)
if (
    view_configuration(TRANSGEAR_EXPLODED_SCALE, _SW_SHADED_EDGES, ViewRole.FULL_DETAIL)
    != BOM_CONFIGURATION
):
    raise AssertionError(
        "the transgear explode's scale would leave the BOM configuration"
    )
CLUSTER_STEMS = frozenset(
    {
        "pd-transgear-pin",
        "pd-transgear-rear-bushing",
        "pd-transgear-feed-pinion",
        "pd-rack-pinion",
        "pd-transgear-disc-hub",
        "pd-vn-transgear-disc-screw",
        "pd-transgear-front-bushing",
        "pd-vn-transgear-retaining-ring",
        "pd-vn-transgear-cluster-shim",
    }
)
if not CLUSTER_STEMS < explode.TRANSGEAR_SHOWN_STEMS:
    raise AssertionError("the disc cluster's view shows exploded transgear families")


@dataclass(frozen=True)
class ExplodedGroup:
    """One sheet-3 view: its families, where it is placed and its ring field."""

    label: str
    stems: frozenset[str]
    center: tuple[float, float]
    ring_limits: Box


# The knob stack and hanger's ring at 2:3 is about 199 x 185 mm (run
# 20261024T025815061Z's outline scaled), the cluster's about 135 x 130 mm
# (its projected box from the builder's stations). The title block spans x
# 218 to 420, y 13 to 66 mm, so the left field stops above it.
TRANSGEAR_EXPLODED_GROUPS = (
    ExplodedGroup(
        "knob stack and hanger exploded",
        explode.TRANSGEAR_SHOWN_STEMS - CLUSTER_STEMS,
        (0.140, 0.168),
        (0.018, 0.070, 0.262, 0.267),
    ),
    ExplodedGroup(
        "disc cluster exploded",
        CLUSTER_STEMS,
        (0.341, 0.193),
        (0.268, 0.120, 0.415, 0.267),
    ),
)
TRANSGEAR_EXPLODED_CAPTION_XY = (0.270, 0.112)
TRANSGEAR_EXPLODED_CAPTION_WIDTH = 52  # characters, above the title block

# --- sheet 4: the platen-and-support steps, the ballooned exploded view -----
# The builder's PAPER_DRIVE_EXPLODED shows only these families here. No run
# has read its outline yet, and sheet 1's showed the outline (the projected
# box) well past the ink, so the view takes the largest ladder scale whose
# ring fits right of the steps and over the title block (step_down_to_fit).
# Its balloons must resolve against the Default BOM: native run
# 20261023T205501918Z showed a "Default Simplified" occurrence resolve item
# "*" there, so (release-manager ruling, PR #1895) this view is full-detail and
# shows Default's own persisted explode at every ladder scale.
EXPLODED_SCALE_LADDER = ((1.0, 3.0), (1.0, 4.0), (1.0, 5.0))
EXPLODED_VIEW_ROLE = ViewRole.FULL_DETAIL
if any(
    view_configuration(scale, _SW_SHADED_EDGES, EXPLODED_VIEW_ROLE) != BOM_CONFIGURATION
    for scale in EXPLODED_SCALE_LADDER
):
    raise AssertionError(
        "a rescale on the exploded-view ladder would leave the BOM configuration"
    )
EXPLODED_SCALE = EXPLODED_SCALE_LADDER[0]
EXPLODED_CENTER = (0.318, 0.168)
PLATEN_NOTE_XY = (0.018, 0.262)
# The steps' right limit, left of the exploded view's balloon ring.
PLATEN_NOTE_RIGHT = 0.222
EXPLODED_RING_LIMITS = (PLATEN_NOTE_RIGHT + 0.003, 0.069, 0.418, 0.267)

# --- sheets 5 to 7: ordered steps in two columns, same note-field budgets ----
FITUP_SCALE = (1.0, 10.0)
FITUP_REFERENCE_CENTER = (0.100, 0.045)
FITUP_LINE_WIDTH = 68  # characters; default-format note text
# Each column's top-left corner, then its right limit and lowest y: the left
# column stops above sheet 5's reference view; the right column stops above
# the title block (top 0.066). Sheets 6 and 7 retain the same field clearances.
FITUP_NOTE_XY = ((0.018, 0.262), (0.215, 0.262))
FITUP_NOTE_LIMITS = ((0.210, 0.075), (0.418, 0.072))
# With a blank line between steps the transgear takes four columns, one
# sub-assembly each: sheet 5 the hanger, then the disc cluster; sheet 6 the
# knob stack, then the latch with its mesh and hook. Sheet 7 begins with the
# loaded full-stroke inspection and splits after the fitted collar rear face.
FITUP_FIRST_COLUMN_KEY = "latch-pin-pressed"
FITUP_SECOND_COLUMN_KEY = "disc-cluster-assembled"
FITUP_CONTINUED_KEY = "collar-pins-pressed"
FITUP_CONTINUED_SECOND_KEY = "latch-hook-fitted"
FITUP_CHAIN_KEY = "loaded-rack-geometry-checked"
CHAIN_SECOND_COLUMN_KEY = "collar-shoulder-seated"

# Sheet 5's VIEW K: K's DRO setting from the arm's pin bore S, the
# assembly's hidden KnobSettingReference chain
# (pd_paper_drive_knob_setting_spec) on the arm and plate seen from the
# machine front at 1:1 as the arm-plate-located step sets them, before the pin is pressed;
# cropped to a circle on S-K's midpoint (S, Q and K all lie on it: Q is the
# chain's right angle).
# It stands under the second column, over the title block; each setting's
# text stands well off its leg, away from the chain's third point, clear of
# the circle (run 20261027T230707102Z put them 4 mm past it, over the arm's
# edge). Its one-word callout keeps the text block between its leg's
# extension lines (run 20261028T000650671Z: "ALONG ARM" was struck by one).
# The three circles in the crop are lettered on short leaders and named in the
# legend left of the circle (same run): S the pin bore, K the knob bore, and T
# the arm's plate-screw tap that lies between them.
KNOB_SETTING_VIEW_NAME = steps.KNOB_SETTING_VIEW_NAME
KNOB_SETTING_SCALE = (1.0, 1.0)
KNOB_SETTING_CENTER = (0.320, 0.097)
KNOB_SETTING_RADIUS = 0.024
# At 15:150 Q sits higher in the crop, so at 0.030 ALONG's extension line from
# Q struck the second column's continuation line (run 20261028T063820031Z,
# machinist review r1-r3, rule 14); 0.024 keeps the texts clear of the
# circle and the extension lines 4 mm under the column.
KNOB_SETTING_TEXT_OFFSET = 0.024
# S to N, the set band (43.794 +0.050/-0 at 15:150), spans the crop's
# diameter, so its text stands past S along the line, off it away from Q,
# clear of the circle and under the second column. Its dimension line runs
# through the text, so the offset also sets its extension lines: at 0.028
# N's ran down onto the title block's top border (run
# 20261028T050655383Z, machinist review r1/r3, rule 13); at 0.018 they end
# in the view's field, above the title block.
KNOB_SETTING_CENTRE_TEXT_PAST = 0.045
KNOB_SETTING_CENTRE_TEXT_OFFSET = 0.018
KNOB_SETTING_ARROWS_OUTSIDE = 1  # swDimensionArrowsSide_e.swDimArrowsOutside
KNOB_SETTING_INSTANCES = frozenset({"pd-transgear-arm-1", "pd-transgear-arm-plate-1"})
# The located step's acceptance for "true": a null reading on the indicator, so the
# setting's centring bound comes from this stated sweep, not from the
# indicator's unknown accuracy over its range (codjiflo P2 on 8e8d5d5): under
# half a division of sweep puts each centre within a quarter division.
KNOB_SETTING_TRUE = "TRUE: UNDER HALF A DIVISION OF SWEEP"
KNOB_SETTING_TRUE_SWEEP_DIVISIONS = 0.5
# The second column's steps end above this on sheet 5.
KNOB_SETTING_FIELD_TOP = 0.144
# The plate-screw tap inside the crop, in the machine frame (mm): the arm's
# tap station nearer S, on the plate's centreline.
KNOB_SETTING_TAP_STATION = max(arm_geometry.PLATE_TAP_STATIONS)
KNOB_SETTING_TAP_XY = (
    knob_setting.P_XY[0]
    + arm_geometry.ARM_U[0] * KNOB_SETTING_TAP_STATION
    + arm_geometry.ARM_N[0] * arm_geometry.PLATE_CENTRELINE_OFFSET,
    knob_setting.P_XY[1]
    + arm_geometry.ARM_U[1] * KNOB_SETTING_TAP_STATION
    + arm_geometry.ARM_N[1] * arm_geometry.PLATE_CENTRELINE_OFFSET,
)
KNOB_SETTING_LEGEND = {
    "S": f"{_config.parts('pd-transgear-arm')['number']} PIN BORE",
    "K": f"{_config.parts('pd-transgear-arm-plate')['number']} KNOB BORE",
    "T": f"{_config.parts('pd-vn-transgear-arm-plate-screw')['number']} TAP",
}
# The DRO frame is the arm's P-S axis: ALONG runs from S toward the pivot bore
# P, off the crop (pd_paper_drive_knob_setting_spec.py:59-66, 92-103, on
# pd_transgear_arm_geometry.ARM_U), the axis the located step trams. Named in
# the legend, as the step names it (machinist review of run
# 20261028T090156127Z, r1/r3: the view showed no pivot bore).
KNOB_SETTING_PIVOT_LINES = (
    "ALONG: S TOWARD P",
    "P: ARM'S PIVOT BORE",
)
KNOB_SETTING_CAPTION = "\n".join(
    (
        f"{KNOB_SETTING_VIEW_NAME}, 1:1 (STEP {steps.step_number('arm-plate-located')})",
        *(f"{letter}: {name}" for letter, name in KNOB_SETTING_LEGEND.items()),
        *KNOB_SETTING_PIVOT_LINES,
    )
)
KNOB_SETTING_CAPTION_XY = (0.213, 0.122)
# Each letter's centre stands this far off its circle's centre (sheet m): S
# inward and away from Q (at 15:150 S-K spans most of the crop, so S's
# letter past the pin would leave it), T diagonally away from both chain
# legs, K radially out past the plate's boss, just outside the crop.
KNOB_SETTING_LETTER_GAPS = {"S": 0.005, "T": 0.005, "K": 0.0095}
# Half a default-height capital letter (sheet m): note positions are the
# text's upper-left corner.
KNOB_SETTING_LETTER_HALF = (0.0013, 0.0018)
for _point in (knob_setting.S_XY, knob_setting.K_XY, KNOB_SETTING_TAP_XY):
    if math.dist(
        _point,
        (
            (knob_setting.S_XY[0] + knob_setting.K_XY[0]) / 2.0,
            (knob_setting.S_XY[1] + knob_setting.K_XY[1]) / 2.0,
        ),
    ) / 1000.0 >= KNOB_SETTING_RADIUS:
        raise AssertionError("the knob setting circle must frame S, T and K")

# Sheet 6's VIEW E: the cluster's shimmed ring gap, the assembly's hidden
# ClusterFloatSetting line (pd_paper_drive_cluster_float_spec) between the
# MHA-PD-VN-61 ring and the MHA-PD-25 front bushing on the pin, seen from the
# side at 5:1 and cropped to a circle on the gap. It stands in sheet 6's left
# field, under the knob stack's column and over the reference isometric's
# caption; the shimming step on sheet 5 cites it.
CLUSTER_FLOAT_VIEW_NAME = cluster_float.VIEW_NAME
CLUSTER_FLOAT_ORIENTATION = "*Right"
CLUSTER_FLOAT_SCALE = (5.0, 1.0)
CLUSTER_FLOAT_CENTER = (0.110, 0.135)
CLUSTER_FLOAT_RADIUS = 0.030
# The crop's model centre (mm): on the gap, a little above the pin's axis.
CLUSTER_FLOAT_MODEL_CENTRE = (
    cluster_float.AXIS_XY[0],
    cluster_float.LINE_Y,
    cluster_fit.RING_REAR_Z + cluster_float.NOMINAL_MM / 2.0,
)
CLUSTER_FLOAT_INSTANCES = frozenset(
    {
        "pd-transgear-pin-1",
        "pd-vn-transgear-retaining-ring-1",
        "pd-transgear-front-bushing-1",
        "pd-transgear-feed-pinion-1",
    }
)
CLUSTER_FLOAT_ARROWS_OUTSIDE = 1  # swDimensionArrowsSide_e.swDimArrowsOutside
CLUSTER_FLOAT_CAPTION = "\n".join(
    (
        f"{CLUSTER_FLOAT_VIEW_NAME}, 5:1 (STEP {steps.step_number('disc-cluster-shimmed')})",
        "RING TO FRONT BUSHING, CLUSTER REARWARD",
    )
)
CLUSTER_FLOAT_CAPTION_XY = (
    CLUSTER_FLOAT_CENTER[0] - CLUSTER_FLOAT_RADIUS,
    CLUSTER_FLOAT_CENTER[1] - CLUSTER_FLOAT_RADIUS - 0.004,
)
_CLUSTER_FLOAT_TEXT_REACH_MM = math.dist(
    (cluster_float.TEXT_POINT[1], cluster_float.TEXT_POINT[2]),
    (CLUSTER_FLOAT_MODEL_CENTRE[1], CLUSTER_FLOAT_MODEL_CENTRE[2]),
)
_CLUSTER_FLOAT_M_PER_MM = CLUSTER_FLOAT_SCALE[0] / CLUSTER_FLOAT_SCALE[1] / 1000.0
if _CLUSTER_FLOAT_TEXT_REACH_MM * _CLUSTER_FLOAT_M_PER_MM >= CLUSTER_FLOAT_RADIUS:
    raise AssertionError("VIEW E's circle must frame the ring gap's text")


def knob_setting_letters(
    s: tuple[float, float],
    q: tuple[float, float],
    k: tuple[float, float],
    t: tuple[float, float],
) -> dict[str, tuple[tuple[float, float], tuple[float, float]]]:
    """Each circle's letter: (note upper-left corner, leader tip on the
    circle's centre), from the projected S, Q, K and tap T (sheet metres)."""
    def unit(vector):
        length = math.hypot(*vector)
        return (vector[0] / length, vector[1] / length)

    along = unit((s[0] - q[0], s[1] - q[1]))
    across = unit((k[0] - q[0], k[1] - q[1]))
    centre = ((s[0] + k[0]) / 2.0, (s[1] + k[1]) / 2.0)
    inward = unit((centre[0] - s[0], centre[1] - s[1]))
    away = unit((centre[0] - q[0], centre[1] - q[1]))
    directions = {
        "S": unit((inward[0] + away[0], inward[1] + away[1])),
        "T": unit((along[0] + across[0], along[1] + across[1])),
        "K": unit((k[0] - centre[0], k[1] - centre[1])),
    }
    tips = {"S": s, "T": t, "K": k}
    letters = {}
    for letter, tip in tips.items():
        gap = KNOB_SETTING_LETTER_GAPS[letter]
        dx, dy = directions[letter]
        letters[letter] = (
            (
                tip[0] + gap * dx - KNOB_SETTING_LETTER_HALF[0],
                tip[1] + gap * dy + KNOB_SETTING_LETTER_HALF[1],
            ),
            tip,
        )
    return letters


def knob_setting_keep(
    s: tuple[float, float],
    q: tuple[float, float],
    k: tuple[float, float],
    n: tuple[float, float],
) -> dict[str, tuple[float, float]]:
    """Each setting's text, from the chain's projected S, Q, K and the
    nominal centre N (sheet metres): each coordinate off its leg's midpoint,
    square to the leg, away from the chain's third point; S to N past S
    along its line, off it away from Q."""
    def normal_away(a, b, away):
        mid = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
        length = math.dist(a, b)
        normal = (-(b[1] - a[1]) / length, (b[0] - a[0]) / length)
        if normal[0] * (mid[0] - away[0]) + normal[1] * (mid[1] - away[1]) < 0.0:
            normal = (-normal[0], -normal[1])
        return mid, normal

    def off(a, b, away):
        mid, normal = normal_away(a, b, away)
        return (
            mid[0] + KNOB_SETTING_TEXT_OFFSET * normal[0],
            mid[1] + KNOB_SETTING_TEXT_OFFSET * normal[1],
        )

    mid, normal = normal_away(s, n, q)
    length = math.dist(s, n)
    past = ((s[0] - n[0]) / length, (s[1] - n[1]) / length)
    return {
        knob_setting.ALONG_DIMENSION: off(s, q, k),
        knob_setting.ACROSS_DIMENSION: off(q, k, s),
        knob_setting.CENTRE_DIMENSION: (
            mid[0] + KNOB_SETTING_CENTRE_TEXT_PAST * past[0]
            + KNOB_SETTING_CENTRE_TEXT_OFFSET * normal[0],
            mid[1] + KNOB_SETTING_CENTRE_TEXT_PAST * past[1]
            + KNOB_SETTING_CENTRE_TEXT_OFFSET * normal[1],
        ),
    }


SHEET_SCALES = {
    "ASSEMBLED VIEWS": ASSEMBLED_SCALE,
    "TRANSGEAR VIEWS": TRANSGEAR_VIEW_SCALE,
    "TRANSGEAR EXPLODED": TRANSGEAR_EXPLODED_SCALE,
    "PLATEN AND SUPPORT": EXPLODED_SCALE,
    "ASSEMBLY AND FIT-UP": FITUP_SCALE,
    "ASSEMBLY AND FIT-UP (CONT.)": FITUP_SCALE,
    "CHAIN FIT-UP": FITUP_SCALE,
    "BILL OF MATERIALS": BOM_REFERENCE_SCALE,
}
if tuple(SHEET_SCALES) != SHEET_NAMES:
    raise AssertionError("every paper-drive sheet takes a scale, in sheet order")

# --- BOM identities ------------------------------------------------------------
# Literal stems, so the config-dependency analysis reads exactly these rows.
BOM_PART_NUMBERS = {
    "pd-support-bar": _config.parts("pd-support-bar")["number"],
    "sh-column-clamp-front": _config.parts("sh-column-clamp-front")["number"],
    "sh-column-clamp-back": _config.parts("sh-column-clamp-back")["number"],
    "sh-vn-clamp-screw": _config.parts("sh-vn-clamp-screw")["number"],
    "pd-platen": _config.parts("pd-platen")["number"],
    "pd-platen-rack": _config.parts("pd-platen-rack")["number"],
    "pd-platen-guide": _config.parts("pd-platen-guide")["number"],
    "pd-guide-lock": _config.parts("pd-guide-lock")["number"],
    "pd-platen-clip": _config.parts("pd-platen-clip")["number"],
    "pd-platen-paper": _config.parts("pd-platen-paper")["number"],
    "sh-vn-brass-fillister-screw": _config.parts("sh-vn-brass-fillister-screw")["number"],
    "pd-vn-platen-clip-screw": _config.parts("pd-vn-platen-clip-screw")["number"],
    "pd-vn-guide-lock-screw": _config.parts("pd-vn-guide-lock-screw")["number"],
    "sh-vn-chain-link--InnerLink": _config.parts("sh-vn-chain-link")["number"],
    "sh-vn-chain-link--OuterLink": _config.parts("sh-vn-chain-link")["number"],
    "pd-vn-chain-connecting-link": _config.parts("pd-vn-chain-connecting-link")["number"],
    "pd-transgear-removable": _config.parts("pd-transgear-removable")["number"],
    "pd-transgear-arm": _config.parts("pd-transgear-arm")["number"],
    "pd-transgear-arm-plate": _config.parts("pd-transgear-arm-plate")["number"],
    "pd-vn-transgear-arm-plate-screw": _config.parts("pd-vn-transgear-arm-plate-screw")["number"],
    "pd-vn-transgear-arm-plate-locating-pin": _config.parts(
        "pd-vn-transgear-arm-plate-locating-pin"
    )["number"],
    "pd-transgear-pivot-spacer": _config.parts("pd-transgear-pivot-spacer")["number"],
    "pd-vn-transgear-pivot-screw": _config.parts("pd-vn-transgear-pivot-screw")["number"],
    "pd-vn-transgear-pivot-spring": _config.parts("pd-vn-transgear-pivot-spring")["number"],
    "pd-vn-transgear-latch-pin": _config.parts("pd-vn-transgear-latch-pin")["number"],
    "sh-vn-fillister-screw-90280a108": _config.parts("sh-vn-fillister-screw-90280a108")["number"],
    "pd-latch-hook": _config.parts("pd-latch-hook")["number"],
    "pd-transgear-pin": _config.parts("pd-transgear-pin")["number"],
    "pd-transgear-rear-bushing": _config.parts("pd-transgear-rear-bushing")["number"],
    "pd-transgear-feed-pinion": _config.parts("pd-transgear-feed-pinion")["number"],
    "pd-transgear-disc-hub": _config.parts("pd-transgear-disc-hub")["number"],
    "pd-transgear-front-bushing": _config.parts("pd-transgear-front-bushing")["number"],
    "pd-vn-transgear-retaining-ring": _config.parts("pd-vn-transgear-retaining-ring")["number"],
    "pd-vn-transgear-cluster-shim": _config.parts("pd-vn-transgear-cluster-shim")["number"],
    "pd-rack-pinion": _config.parts("pd-rack-pinion")["number"],
    "pd-vn-transgear-disc-screw": _config.parts("pd-vn-transgear-disc-screw")["number"],
    "pd-transgear-knob-shaft": _config.parts("pd-transgear-knob-shaft")["number"],
    "pd-transgear-drive-collar": _config.parts("pd-transgear-drive-collar")["number"],
    "pd-vn-transgear-knob-drive-pin": _config.parts("pd-vn-transgear-knob-drive-pin")["number"],
    "pd-transgear-thumbnut": _config.parts("pd-transgear-thumbnut")["number"],
    "pd-transgear-knob-thrust-ring": _config.parts("pd-transgear-knob-thrust-ring")["number"],
    "pd-transgear-knob-cup": _config.parts("pd-transgear-knob-cup")["number"],
    "pd-vn-transgear-knob-cup-pin": _config.parts("pd-vn-transgear-knob-cup-pin")["number"],
}
# Logical rows retain member identity even though both print one purchase Number.
BOM_COMPONENT_IDENTITIES: dict[str, tuple[str, str | None]] = {
    key: (key, None) for key in BOM_PART_NUMBERS
}
BOM_COMPONENT_IDENTITIES.update(
    {
        "sh-vn-chain-link--InnerLink": ("sh-vn-chain-link", INNER_LINK_CONFIGURATION),
        "sh-vn-chain-link--OuterLink": ("sh-vn-chain-link", OUTER_LINK_CONFIGURATION),
        "sh-vn-brass-fillister-screw": ("sh-vn-brass-fillister-screw", "Default"),
        "sh-vn-clamp-screw": ("sh-vn-clamp-screw", "Default"),
        "sh-vn-fillister-screw-90280a108": ("sh-vn-fillister-screw-90280a108", "Default"),
    }
)
# A purchased part's registry SKU, printed in its description.
_SKU = {
    "sh-vn-clamp-screw": _config.parts("sh-vn-clamp-screw")["supplier_skus"][0],
    "sh-vn-brass-fillister-screw": _config.parts("sh-vn-brass-fillister-screw")["supplier_skus"][0],
    "pd-vn-platen-clip-screw": _config.parts("pd-vn-platen-clip-screw")["supplier_skus"][0],
    "pd-vn-guide-lock-screw": _config.parts("pd-vn-guide-lock-screw")["supplier_skus"][0],
    "pd-vn-chain-connecting-link": _config.parts("pd-vn-chain-connecting-link")[
        "supplier_skus"
    ][0],
    "pd-vn-transgear-arm-plate-screw": _config.parts("pd-vn-transgear-arm-plate-screw")[
        "supplier_skus"
    ][0],
    "pd-vn-transgear-arm-plate-locating-pin": _config.parts(
        "pd-vn-transgear-arm-plate-locating-pin"
    )["supplier_skus"][0],
    "pd-vn-transgear-pivot-screw": _config.parts("pd-vn-transgear-pivot-screw")["supplier_skus"][0],
    "pd-vn-transgear-pivot-spring": _config.parts("pd-vn-transgear-pivot-spring")["supplier_skus"][
        0
    ],
    "pd-vn-transgear-latch-pin": _config.parts("pd-vn-transgear-latch-pin")["supplier_skus"][0],
    "sh-vn-fillister-screw-90280a108": _config.parts("sh-vn-fillister-screw-90280a108")[
        "supplier_skus"
    ][0],
    "pd-vn-transgear-disc-screw": _config.parts("pd-vn-transgear-disc-screw")["supplier_skus"][0],
    "pd-vn-transgear-retaining-ring": _config.parts("pd-vn-transgear-retaining-ring")[
        "supplier_skus"
    ][0],
    "pd-vn-transgear-cluster-shim": _config.parts("pd-vn-transgear-cluster-shim")[
        "supplier_skus"
    ][0],
    "pd-vn-transgear-knob-drive-pin": _config.parts("pd-vn-transgear-knob-drive-pin")[
        "supplier_skus"
    ][0],
    "pd-vn-transgear-knob-cup-pin": _config.parts("pd-vn-transgear-knob-cup-pin")["supplier_skus"][
        0
    ],
}
# Assembly-specific wording stays here. Shared chain descriptions follow the
# native member spec, whose model-owned BOM text can override a written cell.
BOM_DESCRIPTIONS = {
    "pd-support-bar": "PAPER-DRIVE SUPPORT BAR",
    "sh-column-clamp-front": "COLUMN CLAMP, FRONT",
    "sh-column-clamp-back": "COLUMN CLAMP, BACK",
    "sh-vn-clamp-screw": f"FILLISTER SCREW, MCMASTER {_SKU['sh-vn-clamp-screw']}",
    "pd-platen": "PLATEN",
    "pd-platen-rack": (
        f"PLATEN RACK + BACKER, {feed_pinion.DIAMETRAL_PITCH:g}DP "
        f"PA{feed_pinion.PRESSURE_ANGLE_DEG:g}"
    ),
    "pd-platen-guide": "PLATEN GUIDE",
    "pd-guide-lock": "PLATEN GUIDE LOCK",
    "pd-platen-clip": "PLATEN PAPER CLIP",
    "pd-platen-paper": "PLATEN PAPER",
    "sh-vn-brass-fillister-screw": f"BRASS FILLISTER SCREW, MCMASTER {_SKU['sh-vn-brass-fillister-screw']}",
    "pd-vn-platen-clip-screw": (
        f"BRASS PAN HEAD SCREW, MCMASTER {_SKU['pd-vn-platen-clip-screw']}"
    ),
    "pd-vn-guide-lock-screw": f"PAN HEAD SCREW, MCMASTER {_SKU['pd-vn-guide-lock-screw']}",
    "sh-vn-chain-link--InnerLink": INNER_LINK_BOM_DESCRIPTION,
    "sh-vn-chain-link--OuterLink": OUTER_LINK_BOM_DESCRIPTION,
    "pd-vn-chain-connecting-link": (
        f"ANSI #25 CONN. LINK, MCMASTER {_SKU['pd-vn-chain-connecting-link']}"
    ),
    # Grouped: its configurations' BOM description wins over a written cell,
    # so the row prints the registry description the builder stamps.
    "pd-transgear-removable": str(_config.parts("pd-transgear-removable")["description"]),
    "pd-transgear-arm": "TRANSGEAR ARM",
    "pd-transgear-arm-plate": "TRANSGEAR ARM PLATE",
    "pd-vn-transgear-arm-plate-screw": (
        f"{plate_screw.THREAD} OVAL HEAD SCREW, MCMASTER "
        f"{_SKU['pd-vn-transgear-arm-plate-screw']}"
    ),
    "pd-vn-transgear-arm-plate-locating-pin": (
        f"PLATE LOCATING DOWEL, MCMASTER {_SKU['pd-vn-transgear-arm-plate-locating-pin']}"
    ),
    "pd-transgear-pivot-spacer": "TRANSGEAR PIVOT SPACER",
    "pd-vn-transgear-pivot-screw": (
        f"{pivot_screw.THREAD} SHOULDER SCREW, MCMASTER {_SKU['pd-vn-transgear-pivot-screw']}"
    ),
    "pd-vn-transgear-pivot-spring": (
        f"CURVED DISC SPRING, MCMASTER {_SKU['pd-vn-transgear-pivot-spring']}"
    ),
    "pd-vn-transgear-latch-pin": f"DOWEL PIN, MCMASTER {_SKU['pd-vn-transgear-latch-pin']}",
    "sh-vn-fillister-screw-90280a108": (
        f"FILLISTER SCREW, MCMASTER {_SKU['sh-vn-fillister-screw-90280a108']}"
    ),
    "pd-latch-hook": "LATCH HOOK",
    "pd-transgear-pin": "TRANSGEAR PIN",
    "pd-transgear-rear-bushing": "TRANSGEAR REAR BUSHING",
    "pd-transgear-feed-pinion": (
        f"FEED SLEEVE, STOCK {feed_pinion.TEETH}T "
        f"{feed_pinion.DIAMETRAL_PITCH:g}DP PA{feed_pinion.PRESSURE_ANGLE_DEG:g}"
    ),
    "pd-transgear-disc-hub": "TRANSGEAR DISC HUB",
    "pd-transgear-front-bushing": "TRANSGEAR FRONT BUSHING",
    "pd-vn-transgear-retaining-ring": (
        f"RETAINING RING, MCMASTER {_SKU['pd-vn-transgear-retaining-ring']}"
    ),
    "pd-vn-transgear-cluster-shim": f"SHIM, MCMASTER {_SKU['pd-vn-transgear-cluster-shim']}",
    "pd-rack-pinion": (
        f"REDUCER DISC, STOCK {disc.TEETH}T {disc.DIAMETRAL_PITCH:g}DP "
        f"PA{disc.PRESSURE_ANGLE_DEG:g}"
    ),
    "pd-vn-transgear-disc-screw": (
        f"{disc_screw.THREAD} FILLISTER SCREW, MCMASTER {_SKU['pd-vn-transgear-disc-screw']}"
    ),
    "pd-transgear-knob-shaft": (
        f"KNOB SHAFT, STOCK {knob_shaft.TEETH}T "
        f"{knob_shaft.DIAMETRAL_PITCH:g}DP PA{knob_shaft.PRESSURE_ANGLE_DEG:g}"
    ),
    "pd-transgear-drive-collar": "KNOB DRIVE COLLAR",
    "pd-vn-transgear-knob-drive-pin": (
        f"WHEEL DRIVE DOWEL, MCMASTER {_SKU['pd-vn-transgear-knob-drive-pin']}"
    ),
    "pd-transgear-thumbnut": "TRANSGEAR THUMBNUT",
    "pd-transgear-knob-thrust-ring": "KNOB THRUST RING",
    "pd-transgear-knob-cup": "KNOB CUP",
    "pd-vn-transgear-knob-cup-pin": f"SPRING PIN, MCMASTER {_SKU['pd-vn-transgear-knob-cup-pin']}",
}
if set(BOM_DESCRIPTIONS) != set(BOM_PART_NUMBERS):
    raise AssertionError("paper-drive BOM description coverage is incomplete")
# The registry's grouped-row description is the builder's to stamp and may
# wrap; every written description keeps to one line.
GROUPED_DESCRIPTION_STEMS = frozenset({"pd-transgear-removable"})
_LONG = sorted(
    stem
    for stem, text in BOM_DESCRIPTIONS.items()
    if len(text) > BOM_DESCRIPTION_MAX_CHARS and stem not in GROUPED_DESCRIPTION_STEMS
)
if _LONG:
    raise AssertionError(f"paper-drive BOM descriptions wrap: {_LONG}")

# The transgear instances the contract inserts (instance ``<stem>-<n>``), each
# count read from the geometry that holds its holes: sheet 2 shows and
# balloons exactly these. The mounted knob sprocket is instance 1;
# the crank wheel and spare T18 stay on sheet 1.
TRANSGEAR_QUANTITIES = {
    "pd-transgear-arm": 1,
    "pd-transgear-arm-plate": 1,
    "pd-vn-transgear-arm-plate-screw": len(arm_geometry.PLATE_TAP_STATIONS),
    "pd-vn-transgear-arm-plate-locating-pin": plate_locating_pin.ASSEMBLY_QUANTITY,
    "pd-transgear-pivot-spacer": 1,
    "pd-vn-transgear-pivot-screw": 1,
    "pd-vn-transgear-pivot-spring": spring.COUNT,
    "pd-vn-transgear-latch-pin": 1,
    "sh-vn-fillister-screw-90280a108": len(hook_geometry.SCREW_X),
    "pd-latch-hook": 1,
    "pd-transgear-pin": 1,
    "pd-transgear-rear-bushing": 1,
    "pd-transgear-feed-pinion": 1,
    "pd-transgear-disc-hub": 1,
    "pd-transgear-front-bushing": 1,
    "pd-vn-transgear-retaining-ring": 1,
    # The model's nominal count; the fit-up sets the real one (VIEW E).
    "pd-vn-transgear-cluster-shim": cluster_fit.SHIM_COUNT_MODEL,
    "pd-rack-pinion": 1,
    "pd-vn-transgear-disc-screw": hub_geometry.SCREW_COUNT,
    "pd-transgear-knob-shaft": 1,
    "pd-transgear-drive-collar": 1,
    "pd-vn-transgear-knob-drive-pin": len(seat_geometry.PIN_HOLE_ANGLES_DEG),
    "pd-transgear-removable": 3,  # two mounted wheels plus the loose T18 spare
    "pd-transgear-thumbnut": 1,
    "pd-transgear-knob-thrust-ring": 1,
    "pd-transgear-knob-cup": 1,
    "pd-vn-transgear-knob-cup-pin": 1,
}
# One assembled inner or outer link spans one pitch. The chain is cut with an
# inner link at each end, and the connecting link closes the loop as its last
# outer link.
CHAIN_QUANTITIES = {
    "sh-vn-chain-link--InnerLink": chain.LINK_COUNT // 2,
    "sh-vn-chain-link--OuterLink": chain.LINK_COUNT // 2 - 1,
    "pd-vn-chain-connecting-link": 1,
}
# The inner and outer link rows print one purchase Number, one supplier
# chain's two link kinds, so the BOM sheet says what that Number is and what
# to order (2026-10-27 ENFORCE review, r1-r3: one Number with two
# descriptions and quantities left the order unknown).  It joins the BOM
# reference's caption, in the air right of that view.
_CHAIN_CUT_PITCHES = (
    CHAIN_QUANTITIES["sh-vn-chain-link--InnerLink"]
    + CHAIN_QUANTITIES["sh-vn-chain-link--OuterLink"]
)
BOM_CHAIN_ORDER_NOTE = (
    f"{BOM_PART_NUMBERS['sh-vn-chain-link--InnerLink']} IS ONE CHAIN,\n"
    f"MCMASTER {_config.parts('sh-vn-chain-link')['supplier_skus'][0]}: "
    f"CUT {_CHAIN_CUT_PITCHES} PITCHES,\n"
    f"{CHAIN_QUANTITIES['sh-vn-chain-link--InnerLink']} INNER AND "
    f"{CHAIN_QUANTITIES['sh-vn-chain-link--OuterLink']} OUTER LINKS;\n"
    f"{BOM_PART_NUMBERS['pd-vn-chain-connecting-link']} CLOSES THE LOOP."
)
BOM_SHEET_CAPTION = f"{BOM_REFERENCE_CAPTION}\n{BOM_CHAIN_ORDER_NOTE}"
if not set(TRANSGEAR_QUANTITIES) <= set(BOM_PART_NUMBERS):
    raise AssertionError("every transgear family is a BOM row")
TRANSGEAR_INSTANCES = frozenset(
    f"{stem}-{index}"
    for stem, count in TRANSGEAR_QUANTITIES.items()
    for index in range(1, (1 if stem == "pd-transgear-removable" else count) + 1)
)
# Sheet 2's isometric cannot reach these families' ink. Farm run
# 20261001T051043622Z found none for the feed sleeve: its extreme-point picks
# missed, and its gear edges exceeded the fallback's edge budget. The rear
# bushing behind the reducer disc and the knob drive and hanger hardware are
# obscured by their neighbours. The pin, front bushing and retaining ring
# attach within 3.5 mm of each other on the pin nose, so their three leaders
# met there with overlapping arrowheads (machinist review, run
# 20261024T124144759Z). Sheet 3's explode shows and balloons them all, with
# every other family it draws apart.
ISO_HIDDEN_STEMS = frozenset(
    {
        "pd-transgear-feed-pinion",
        "pd-transgear-knob-shaft",
        "pd-transgear-drive-collar",
        "pd-vn-transgear-knob-drive-pin",
        "pd-vn-transgear-knob-cup-pin",
        "pd-vn-transgear-arm-plate-screw",
        "pd-vn-transgear-arm-plate-locating-pin",
        "pd-vn-transgear-latch-pin",
        "pd-transgear-rear-bushing",
        "pd-transgear-pin",
        "pd-transgear-front-bushing",
        "pd-vn-transgear-retaining-ring",
        "pd-vn-transgear-cluster-shim",
    }
)
if not explode.TRANSGEAR_SHOWN_STEMS <= set(TRANSGEAR_QUANTITIES):
    raise AssertionError("the transgear explode shows transgear families only")
if not ISO_HIDDEN_STEMS < explode.TRANSGEAR_SHOWN_STEMS:
    raise AssertionError("the explode shows every family the isometric cannot")
# The pivot's spring sits in the arm's counterbore under the shoulder screw's
# head, hidden from the isometric: the ENFORCE review of farm run
# 20261024T090600202Z-8e9ffbb4 found its leader on the spacer's edge and the
# arm's face. Section A-A on the same sheet cuts through it and balloons it
# (PIVOT_BALLOON_TIPS), so the isometric leaves it out.
ISO_SECTION_ONLY_STEMS = frozenset({"pd-vn-transgear-pivot-spring"})
if not ISO_SECTION_ONLY_STEMS <= {stem for stem, *_ in PIVOT_BALLOON_TIPS}:
    raise AssertionError("Section A-A balloons every family the isometric leaves to it")
if ISO_SECTION_ONLY_STEMS & explode.TRANSGEAR_SHOWN_STEMS:
    raise AssertionError("a family the explode shows is ballooned there, not by the section")
TRANSGEAR_EXPLODED_INSTANCES = frozenset(
    name
    for name in TRANSGEAR_INSTANCES
    if name.rsplit("-", 1)[0] in explode.TRANSGEAR_SHOWN_STEMS
)
if explode.KNOB_WHEEL_INSTANCE not in TRANSGEAR_EXPLODED_INSTANCES:
    raise AssertionError("the explode moves the mounted knob wheel it shows")
# The knob wheel is the mounted removable; the crank wheel and spare T18 are
# sheet 1's.  The hub's walk took its flange's rear rim on the far side from
# the knob stack (part (-10.676, -6.598, 0)), so on sheet 2 balloon 29's
# leader crossed the T24 and thumbnut and its arrow was lost on the dark disc
# (machinist review of run 20261028T090156127Z, r1/r3).  The diametrically
# opposite point of the flange's front rim (part z = -FLANGE_THICK, wholly
# drawn) faces away from the knob stack on both isometrics, clear of the
# three screw heads.
HUB_BALLOON_ANGLE = math.atan2(6.598, 10.676)
HUB_BALLOON_POINT_MM = (
    round(hub.FLANGE_DIA / 2.0 * math.cos(HUB_BALLOON_ANGLE), 3),
    round(hub.FLANGE_DIA / 2.0 * math.sin(HUB_BALLOON_ANGLE), 3),
    -hub.FLANGE_THICK,
)
TRANSGEAR_BALLOON_ANCHORS = {
    stem: BalloonAnchor(instance=explode.KNOB_WHEEL_INSTANCE)
    if stem == "pd-transgear-removable"
    else BalloonAnchor(point_mm=HUB_BALLOON_POINT_MM)
    if stem == "pd-transgear-disc-hub"
    else BalloonAnchor()
    for stem in TRANSGEAR_QUANTITIES
}


def exploded_group_instances(group: ExplodedGroup) -> frozenset[str]:
    """The sheet-3 instances one view shows: its families' exploded instances."""
    return frozenset(
        name
        for name in TRANSGEAR_EXPLODED_INSTANCES
        if name.rsplit("-", 1)[0] in group.stems
    )


def transgear_balloon_items(
    items: dict[str, str],
) -> tuple[tuple[tuple[str, str], ...], tuple[tuple[str, str], ...]]:
    """(sheet 2 isometric, sheet 3 explode) balloon items, each in item order.

    The isometric balloons every transgear family it can reach, less the
    pivot parts Section A-A balloons; the explode balloons every family it
    shows, the ones the isometric cannot included.
    """
    return (
        _in_item_order(
            items, set(TRANSGEAR_QUANTITIES) - ISO_HIDDEN_STEMS - ISO_SECTION_ONLY_STEMS
        ),
        _in_item_order(items, explode.TRANSGEAR_SHOWN_STEMS),
    )


# _spread_balloons rings a view's balloons in its attachments' angular order
# about the view's centre, then pushes crowded circles apart along the ring.
# An attachment far from that centre can leave its leader across a pushed
# neighbour's: on farm run 20261002T180658288Z (swmaker000009, inner view at
# 1:3, its nine circles 0.60 rad apart on a 27 mm ring) the arm-plate screw's
# (item 17) leader from its attachment (233.3, 188.8) mm crossed the rear
# bushing's (item 24) from (229.0, 180.8) mm at (233.2, 189.0). Swapping two
# crossing leaders' slots uncrosses them and strictly shortens their total
# length (the triangle inequality), so repeated swaps end; the cap only
# bounds a wrong input.
_UNCROSS_SWAPS_MAX = 64
# Farm run 20261023T222629630Z (swmaker000004): the inner view's knob-shaft
# (item 36) attachment sat within the audit's 0.1 mm touch tolerance of the cup
# pin's (item 40) leader when the ring was uncrossed, so no swap was made, and
# after later rebuilds it crossed 0.115 mm past it. The green run of the same
# recipe had swapped them. Leaders nearer than this are swapped too whenever
# that shortens them (so they were effectively crossing); a swap still strictly
# shortens the total, so the loop ends.
_UNCROSS_CLEARANCE_M = 5e-4


def _segment_point_distance(
    segment: tuple[float, float, float, float], x: float, y: float
) -> float:
    x0, y0, x1, y1 = segment
    dx, dy = x1 - x0, y1 - y0
    length2 = dx * dx + dy * dy
    t = 0.0 if length2 == 0.0 else max(0.0, min(1.0, ((x - x0) * dx + (y - y0) * dy) / length2))
    return math.hypot(x - (x0 + t * dx), y - (y0 + t * dy))


def _leader_clearance(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> float:
    """Least distance between two non-crossing leaders (0 when they cross)."""
    if find_leader_leader_crossings(
        [LeaderSegment("a", "balloon", *a), LeaderSegment("b", "balloon", *b)],
        tol=0.0, shared_terminus=0.0,
    ):
        return 0.0
    return min(
        _segment_point_distance(b, a[0], a[1]),
        _segment_point_distance(b, a[2], a[3]),
        _segment_point_distance(a, b[0], b[1]),
        _segment_point_distance(a, b[2], b[3]),
    )


def uncrossed_ring_slots(
    centres: Sequence[tuple[float, float]],
    attachments: Sequence[tuple[float, float]],
) -> list[int]:
    """Which ring slot (an index into ``centres``, the circle centres as
    placed) each balloon takes so that no two leaders, each from its circle's
    centre to its attachment, cross or pass within ``_UNCROSS_CLEARANCE_M``
    where swapping shortens them. Other leaders keep their slots, so the
    slots, and the circles' clearances, are the ring's own."""
    if len(centres) != len(attachments):
        raise ValueError("one ring slot per balloon attachment")
    slots = list(range(len(centres)))

    def leader(index: int, slot: int) -> tuple[float, float, float, float]:
        return (*centres[slot], *attachments[index])

    def length(segment: tuple[float, float, float, float]) -> float:
        return math.hypot(segment[2] - segment[0], segment[3] - segment[1])

    for _swap in range(_UNCROSS_SWAPS_MAX + 1):
        segments = [
            LeaderSegment(str(index), "balloon", *leader(index, slots[index]))
            for index in range(len(attachments))
        ]
        crossings = find_leader_leader_crossings(segments)
        if crossings:
            pair = (int(crossings[0].a.label), int(crossings[0].b.label))
        else:
            pair = next(
                (
                    (first, second)
                    for first in range(len(slots))
                    for second in range(first + 1, len(slots))
                    if _leader_clearance(
                        leader(first, slots[first]), leader(second, slots[second])
                    ) < _UNCROSS_CLEARANCE_M
                    and length(leader(first, slots[second]))
                    + length(leader(second, slots[first]))
                    < length(leader(first, slots[first]))
                    + length(leader(second, slots[second]))
                ),
                None,
            )
            if pair is None:
                return slots
        first, second = pair
        slots[first], slots[second] = slots[second], slots[first]
    raise RuntimeError(
        f"balloon ring: leaders still cross after {_UNCROSS_SWAPS_MAX} slot swaps"
    )


def _uncross_ring(
    adapter: Any, landings: Sequence[BalloonLanding], *, label: str
) -> None:
    """Move ``landings``' ringed balloons between their own ring slots until
    no two leaders cross (:func:`uncrossed_ring_slots`); attachments stay."""
    annotations, centres, offsets, attachments = [], [], [], []
    for landing in landings:
        x, y, _radius = rendered_balloon_circle(landing.note, label=label)
        annotation = _early_bound(
            _early_bound(landing.note, "INote").GetAnnotation(), "IAnnotation"
        )
        anchor = tuple(float(value) for value in (annotation.GetPosition() or ()))
        points = tuple(
            float(value) for value in (annotation.GetLeaderPointsAtIndex(0) or ())
        )
        if len(anchor) < 2 or len(points) < 6:
            raise RuntimeError(f"{label}: {landing.stem} balloon is unreadable")
        annotations.append(annotation)
        centres.append((x, y))
        offsets.append((anchor[0] - x, anchor[1] - y))
        attachments.append((points[-3], points[-2]))
    slots = uncrossed_ring_slots(centres, attachments)
    moved = [index for index, slot in enumerate(slots) if slot != index]
    for index in moved:
        x, y = centres[slots[index]]
        if not annotations[index].SetPosition(
            x + offsets[index][0], y + offsets[index][1], 0.0
        ):
            raise RuntimeError(
                f"{label}: failed to move {landings[index].stem} balloon"
            )
    if moved:
        _telemetry.info(
            f"{label}: swapped ring slots to uncross leaders: "
            + ", ".join(
                f"{landings[index].stem} -> {landings[slots[index]].stem}'s"
                for index in moved
            )
        )
        rebuild_drawing(adapter, label=f"{label} uncrossed")


# Sheet 1's isometric balloons what sheets 2 to 4 do not show: the chain,
# and the spare T18 on the base deck (the third removable inserted), whose
# item sheet 2 balloons on the mounted knob wheel.
SPARE_INSTANCE = "pd-transgear-removable-3"
# The chain's loop stations count from the knob wheel (the builder's
# _chain_station_point); station s is the link @<role>:s // 2 + 1, inner links
# on even stations, and the connecting link closes the loop at the last. The
# first inner and outer links sat in the knob wheel's wrap beside the
# connecting link, under the bar's and wheel's edges, and their three leaders
# met there (machinist review, #1531). One inner link midway along one run
# between the wheels and one outer link midway along the other stand clear.
CHAIN_INNER_BALLOON_STATION = 24
CHAIN_OUTER_BALLOON_STATION = 51
if CHAIN_INNER_BALLOON_STATION % 2 or not CHAIN_OUTER_BALLOON_STATION % 2:
    raise AssertionError("inner links take even loop stations, outer links odd")
# The inner and connecting links' anchors are frozen at the body extreme
# points the walk proved drawn on rolling main (swmaker00000A, run
# 20261024T091056564Z). The walk's ray probe is seat-dependent: on
# swmaker000005 (run 20261024T124144759Z) the same 12 rays over 349 bodies hit
# 98 times, not 138, so it took a covered connecting-link point under the
# transgear arm, and balloon 43's leader crossed the bar to it. A point that
# is drawn stays drawn on a seat that misses occluders.
CHAIN_INNER_BALLOON_POINT_MM = (4.946, -0.867, 1.650)
CONNECTING_LINK_BALLOON_POINT_MM = (-2.042, -1.262, -3.550)
ASSEMBLED_BALLOON_ANCHORS = {
    "sh-vn-chain-link--InnerLink": BalloonAnchor(
        point_mm=CHAIN_INNER_BALLOON_POINT_MM,
        instance=f"@InnerLink:{CHAIN_INNER_BALLOON_STATION // 2 + 1}",
    ),
    "sh-vn-chain-link--OuterLink": BalloonAnchor(
        instance=f"@OuterLink:{CHAIN_OUTER_BALLOON_STATION // 2 + 1}"
    ),
    "pd-vn-chain-connecting-link": BalloonAnchor(
        point_mm=CONNECTING_LINK_BALLOON_POINT_MM
    ),
    "pd-transgear-removable": BalloonAnchor(instance=SPARE_INSTANCE),
}
# Sheet 4's exploded view balloons every family it shows. The builder places
# each lock station's top plate, then its bottom plate, so pd-guide-lock-1 is
# the first station's top plate: exploded, it still stands behind the bar, and
# the default (lowest-named) landing put balloon 8 on the bar's lower edge
# (machinist review of run 20261024T082548908Z-cf4349b5). The bottom plate
# hangs free under the bar.
PLATEN_GUIDE_LOCK_INSTANCE = "pd-guide-lock-2"
# The guides: the builder places the bottom rail first, so pd-platen-guide-1
# exploded still stands behind the platen, only its end showing past the
# platen's edge, where the default landing put balloon 7 beside the bar's
# front clamp screw, its leader through that head and onto balloon 4's
# arrowhead (machinist review of the final-head run 20261101T135807943Z).
# The top rail, -2, explodes clear above the platen; its balloon lands on
# its top edge on the platen-mating face (part frame: x along the rail,
# y = height, z = 0), mid-span between the A4 and A5 screw stations and
# clear of both lock stations' plates and screws.
PLATEN_GUIDE_INSTANCE = "pd-platen-guide-2"
PLATEN_GUIDE_BALLOON_POINT_MM = (110.0, platen_guide.GUIDE_HEIGHT, 0.0)
PLATEN_BALLOON_ANCHORS = {
    stem: BalloonAnchor(instance=PLATEN_GUIDE_LOCK_INSTANCE)
    if stem == "pd-guide-lock"
    else BalloonAnchor(
        point_mm=PLATEN_GUIDE_BALLOON_POINT_MM, instance=PLATEN_GUIDE_INSTANCE
    )
    if stem == "pd-platen-guide"
    else BalloonAnchor()
    for stem in explode.SHOWN_STEMS
}


def _in_item_order(
    items: dict[str, str], stems: Iterable[str]
) -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted(((stem, items[stem]) for stem in stems), key=lambda p: int(p[1]))
    )


def assembled_balloon_items(items: dict[str, str]) -> tuple[tuple[str, str], ...]:
    """Sheet 1's isometric balloons, in item order."""
    return _in_item_order(items, ASSEMBLED_BALLOON_ANCHORS)


def platen_balloon_items(items: dict[str, str]) -> tuple[tuple[str, str], ...]:
    """Sheet 4's exploded-view balloons, in item order."""
    return _in_item_order(items, PLATEN_BALLOON_ANCHORS)


Box = tuple[float, float, float, float]


def _grown(box: Box, by: float) -> Box:
    return (box[0] - by, box[1] - by, box[2] + by, box[3] + by)


def ring_fit_shift(outline: Box, limits: Box, *, name: str) -> tuple[float, float]:
    """Shift that centres a view's balloon ring inside ``limits``.

    Outlines and limits are sheet metres (left, bottom, right, top); the ring
    is the outline grown by BALLOON_RING_REACH. Raises naming each axis on
    which the ring is larger than the room.
    """
    ring = _grown(outline, BALLOON_RING_REACH)
    findings = [
        f"{name} ring {axis} {(ring[hi] - ring[lo]) * 1000:.1f} mm > room "
        f"{(limits[hi] - limits[lo]) * 1000:.1f} mm"
        for axis, lo, hi in (("width", 0, 2), ("height", 1, 3))
        if ring[hi] - ring[lo] > limits[hi] - limits[lo]
    ]
    if findings:
        raise ValueError(f"balloon ring does not fit: {'; '.join(findings)}")
    return (
        (limits[0] + limits[2] - ring[0] - ring[2]) / 2.0,
        (limits[1] + limits[3] - ring[1] - ring[3]) / 2.0,
    )


def step_down_to_fit(
    outline_at: Callable[[tuple[float, float]], Box],
    ladder: tuple[tuple[float, float], ...],
    limits: Box,
    *,
    name: str,
) -> tuple[tuple[float, float], Box]:
    """The first ``ladder`` scale, largest first, whose ring fits ``limits``.

    ``outline_at`` applies a scale to the placed view and returns the outline
    SolidWorks reads back. The outline carries a fixed sheet-space padding, so
    no scale's outline is predicted from another's: each candidate is applied
    and re-read. Returns the scale and its outline; raises naming every
    scale's overflow when the smallest still overflows.
    """
    findings = []
    for scale in ladder:
        outline = outline_at(scale)
        try:
            ring_fit_shift(outline, limits, name=f"{name} at {_scale_text(scale)}")
        except ValueError as error:
            findings.append(str(error))
            continue
        return scale, outline
    raise ValueError(f"no {name} scale fits: {' | '.join(findings)}")


def _native_outline_at(
    adapter: Any, view: Any, placed: tuple[float, float], *, label: str
) -> Callable[[tuple[float, float]], Box]:
    """``outline_at`` for step_down_to_fit on a placed drawing view."""
    current = [placed]

    def outline_at(scale: tuple[float, float]) -> Box:
        if scale != current[0]:
            _set_view_scale(adapter, view, scale, label=label)
            current[0] = scale
        return _view_outline(view)

    return outline_at


def transgear_view_shift(iso_outline: Box) -> tuple[float, float]:
    """Shift that centres the transgear isometric's balloon ring in sheet 2's
    field vertically. It does not move along x, so the pivot section's field
    left of it stays the same.

    The outline is in sheet metres (left, bottom, right, top). Raises if the
    ring is taller than the field or leaves it at either side.
    """
    left, bottom, right, top = SHEET_TWO_RING_LIMITS
    ring = _grown(iso_outline, BALLOON_RING_REACH)
    findings = []
    if ring[3] - ring[1] > top - bottom:
        findings.append(
            f"height {(ring[3] - ring[1]) * 1000:.1f} mm > "
            f"room {(top - bottom) * 1000:.1f} mm"
        )
    if ring[0] < left or ring[2] > right:
        findings.append(
            f"x {ring[0] * 1000:.1f} to {ring[2] * 1000:.1f} mm leaves "
            f"{left * 1000:.1f} to {right * 1000:.1f} mm"
        )
    if findings:
        raise ValueError(f"sheet 2 isometric ring {'; '.join(findings)}")
    return (0.0, (bottom + top - ring[1] - ring[3]) / 2.0)


def _scale_text(scale: tuple[float, float]) -> str:
    return f"{scale[0]:g}:{scale[1]:g}"


def _mm_window(limits: tuple[float, float], places: int) -> str:
    """An inch-authored (min, max) window in this mm sheet's units, rounded
    inward so the printed window never admits a value the part spec refuses
    (machinist review: inch values on a mm sheet stop the fitter)."""
    scale = 10**places
    low = math.ceil(round(limits[0] * scale, 9)) / scale
    high = math.floor(round(limits[1] * scale, 9)) / scale
    return f"{low:.{places}f}-{high:.{places}f}"


# --- sheet wording ---------------------------------------------------------------
_N = BOM_PART_NUMBERS
KNOB_TEETH = knob_shaft.TEETH
# CONTRACT-paper-drive.md §1, front to rear; None is a feature of the plate.
KNOB_STACK: tuple[tuple[str | None, str], ...] = (
    ("pd-transgear-thumbnut", "THUMBNUT"),
    ("pd-transgear-removable", sprocket.KNOB_CONFIG),
    ("pd-transgear-drive-collar", "COLLAR"),
    ("pd-transgear-knob-shaft", f"SHAFT {KNOB_TEETH}T"),
    ("pd-transgear-knob-thrust-ring", "RING"),
    (None, "PLATE HUB"),
    ("pd-transgear-arm-plate", "PLATE"),
    (None, "REAR BOSS"),
    ("pd-transgear-knob-cup", "CUP"),
    ("pd-vn-transgear-knob-cup-pin", "PIN"),
)
# The knob's end float: the cup set on a feeler END_FLOAT behind the plate's
# boss and pinned there (R9-70, K-1), accepted at the feeler's own band.
KNOB_END_FLOAT_RANGE = (
    knob_shaft.END_FLOAT - knob_shaft.END_FLOAT_SET_TOL,
    knob_shaft.END_FLOAT + knob_shaft.END_FLOAT_SET_TOL,
)
# The platen's screw stations (platen_spec): its front counterbores take the
# guide screws, its through-taps the clip screws.
GUIDE_SCREWS = len(platen.GUIDE_HOLE_X) * len(platen.GUIDE_HOLE_Y)
CLIP_SCREWS = len(platen.SOCKET_XY)


# The engaged-feed window, measured from the rack's -X cut end. Machine X is
# drawn on no sheet, so the end and the feed direction are named by the
# crank, which stands on the drive's -X side (machinist review: "-X CUT END"
# could not be found on the part).
ENGAGED_FEED_DATUM_TEXT = (
    "FROM THE RACK'S CRANK-SIDE CUT END TO THE FEED STUD AXIS; PLATEN FEED "
    "AWAY FROM THE CRANK SHORTENS IT"
)


def engaged_feed_text(domain: RackOperatingDomain) -> str:
    """The window the hanger step prints, in the title block's millimetres."""
    low, high = domain.axis_from_left_end_limits_mm
    return (
        f"ENGAGED FEED: {low:.{OPERATING_LIMIT_PLACES}f} TO "
        f"{high:.{OPERATING_LIMIT_PLACES}f} {ENGAGED_FEED_DATUM_TEXT}."
    )


def _stack_text() -> str:
    return ", ".join(
        f"{_N[stem]} {label}" if stem else label for stem, label in KNOB_STACK
    )


def _step_text(*, operating_domain: RackOperatingDomain) -> dict[str, str]:
    pin_lo, pin_hi = joints.LATCH_PIN_PROUD_RANGE
    drive_lo, drive_hi = drive_pin.PROUD_RANGE
    knob_lo, knob_hi = KNOB_END_FLOAT_RANGE
    teeth = f"{KNOB_TEETH}T"
    return {
        "bar-clamped": (
            f"CLAMP THE {_N['pd-support-bar']} BAR TO BOTH COLUMNS, EACH BETWEEN A "
            f"{_N['sh-column-clamp-front']} FRONT AND A {_N['sh-column-clamp-back']} BACK "
            f"ARC, WITH THE {_N['sh-vn-clamp-screw']} SCREWS FROM THE BAR FRONT. SET "
            f"THE BAR TOP {steps.BAR_TOP_ABOVE_DECK:.1f} ABOVE THE BASE DECK AT "
            # Rule 19 fit-up for the slotted west pair (owner ruling
            # 2026-10-15, #1471 option A): the round pair locates.  Named by
            # its holes, not the bar sheet's END A, which no package sheet
            # defines (reviewfix-r3 machinist review).
            "BOTH COLUMNS WITH ALL FOUR SCREWS SNUG; TIGHTEN THE ROUND-HOLE "
            "PAIR, THEN THE SLOTTED PAIR."
        ),
        "rack-soldered": (
            f"SOFT-SOLDER (60/40 TIN-LEAD, ROSIN FLUX) THE {_N['pd-platen-rack']} RACK "
            f"TO THE {_N['pd-platen']} PLATEN'S BACK, TEETH DOWN, ENDS FLUSH WITH THE "
            f"PLATEN'S, CRESTS {steps.RACK_CREST_TEXT} BELOW ITS BOTTOM EDGE: THIS "
            f"HOLDS THE {_N['pd-vn-transgear-latch-pin']} PIN ON THE "
            f"{_N['pd-latch-hook']} HOOK'S STRAIGHT RUN. SIGHT ALONG IT: TEETH "
            "STRAIGHT, NO SOLDER IN THE GAPS."
        ),
        "guides-screwed": (
            f"SCREW THE {len(platen.GUIDE_HOLE_Y)} {_N['pd-platen-guide']} GUIDES TO "
            f"THE PLATEN BACK WITH {GUIDE_SCREWS} {_N['sh-vn-brass-fillister-screw']} SCREWS "
            "FROM THE FRONT, HEADS IN THE COUNTERBORES."
        ),
        "clips-fitted": (
            f"SCREW THE {_N['pd-platen-clip']} CLIPS TO THE PLATEN FRONT WITH "
            f"{CLIP_SCREWS} {_N['pd-vn-platen-clip-screw']} SCREWS, SPRING RAILS "
            f"INBOARD; LAY THE {_N['pd-platen-paper']} PAPER BETWEEN THEM."
        ),
        "platen-hung": (
            "TRIAL-HANG THE PLATEN ON THE BAR, THE TOP GUIDE ON THE BAR TOP. FIT THE "
            f"{_N['pd-guide-lock']} LOCKS TO THE GUIDE BACKS BEHIND THE BAR WITH "
            f"THEIR {_N['pd-vn-guide-lock-screw']} SCREWS, LOOSE."
        ),
        "guide-locks-set": (
            f"SNUG EACH {_N['pd-guide-lock']} LOCK'S {_N['pd-vn-guide-lock-screw']} SCREWS, "
            "PUSH THE LOCK AT ITS MIDDLE AWAY FROM THE BAR TILL ITS HOLES BEAR ON "
            "THEM; TIGHTEN."
        ),
        "lock-seats-faced": (
            f"FACE LOCK SEATS TO {_mm_window(platen_guide.LOCK_GAP_FIT, 3)} PLATEN FLOAT; "
            "ELSE STOP AND REPORT."
        ),
        "latch-pin-pressed": (
            f"PRESS THE {_N['pd-vn-transgear-latch-pin']} DOWEL INTO THE "
            f"{_N['pd-transgear-arm']} ARM'S REAMED HOLE TO THE HOLE FLOOR, "
            f"{pin_lo:.2f} TO {pin_hi:.2f} PROUD."
        ),
        "pin-pressed": (
            f"PRESS THE {_N['pd-transgear-pin']} PIN INTO THE {_N['pd-transgear-arm']} "
            "ARM'S REAMED HOLE FROM THE REAR TILL ITS HEAD SEATS ON THE ARM."
        ),
        "arm-plate-located": (
            f"CLAMP THE {_N['pd-transgear-arm-plate']} PLATE ON THE "
            f"{_N['pd-transgear-arm']} ARM'S REAR FACE WITH TOOLMAKER'S CLAMPS, "
            "SCREWS OUT; ARM ON PARALLELS ON THE MILL, PLATE UP, NO PIN YET. "
            "INDICATE THE PIVOT BORE P AND THE ARM'S PIN BORE S TRUE ON ONE DRO "
            f"AXIS ({KNOB_SETTING_TRUE}); ZERO ON S. AT THE "
            f"{KNOB_SETTING_VIEW_NAME} SETTING FROM S, TAP THE PLATE TILL "
            "ITS KNOB BORE INDICATES TRUE (THE "
            f"{_N['pd-transgear-knob-shaft']} {KNOB_TEETH}T / {_N['pd-rack-pinion']} "
            f"{disc.TEETH}T MESH); CLAMP; RE-INDICATE. "
            "MATCH-DRILL 2 PILOTS THROUGH THE PLATE AND THE ARM. "
            "PART THEM; REAM EACH PART'S HOLES TO ITS DRAWING "
            f"({_N['pd-transgear-arm']} PRESS, {_N['pd-transgear-arm-plate']} SLIP). "
            f"PRESS {TRANSGEAR_QUANTITIES['pd-vn-transgear-arm-plate-locating-pin']} "
            f"{_N['pd-vn-transgear-arm-plate-locating-pin']} DOWELS INTO THE ARM "
            "FROM THE REAR, "
            f"{plate_locating_interface.PROUD_LIMITS_MM[0]:.2f} TO "
            f"{plate_locating_interface.PROUD_LIMITS_MM[1]:.2f} PROUD; "
            "MATCH-MARK ARM AND PLATE."
        ),
        "arm-plate-fitted": (
            f"FIT THE {_N['pd-transgear-arm-plate']} PLATE ON THE LOCATING DOWELS. "
            f"FIT {TRANSGEAR_QUANTITIES['pd-vn-transgear-arm-plate-screw']} "
            f"{_N['pd-vn-transgear-arm-plate-screw']} SCREWS IN THE ARM'S THROUGH TAPS; "
            "SNUG BOTH, THEN TIGHTEN THEM IN TURN. DOWELS LOCATE; SCREWS CLAMP ONLY. "
            "PUSH AND ROCK THE PLATE BY HAND: NO SHAKE ON THE DOWELS, NO DAYLIGHT "
            "UNDER IT. RE-CHECK AFTER EVERY REMOVAL."
        ),
        "arm-plate-screws-cut": (
            f"TAKE BOTH {_N['pd-vn-transgear-arm-plate-screw']} SCREWS OUT; CUT THEIR "
            f"TIPS FLUSH TO {joints.PLATE_SCREW_CUT_PROUD_MAX:.2f} PROUD OF THE ARM'S "
            "FRONT FACE; BREAK THE CUT EDGE "
            f"{math.floor(plate_screw.CUT_END_BREAK_MAX * 100) / 100:.2f} MAX. "
            "REFIT THE SAME SCREWS IN THE SAME HOLES BEFORE PIVOTING THE HANGER."
        ),
        # R9-71: the spacer is pressed on the shoulder, so its faces' tilt is
        # fixed in the bar; the MHA-PD-VN-63 spring holds the arm on it. The
        # screw's tip is faced below the bar's front face, where the platen
        # slides, and staked there (rule 23); the spot-face floor sets the
        # spring room (transgear_hanger_joints).
        "hanger-pivoted": (
            f"ON THE {_N['pd-vn-transgear-pivot-screw']} SHOULDER SCREW FROM THE REAR: "
            f"{_N['pd-vn-transgear-pivot-spring']} "
            f"SPRING, THEN ARM; PRESS THE {_N['pd-transgear-pivot-spacer']} SPACER, AS "
            "MADE, ON THE SHOULDER, FLUSH WITH ITS END ON A FLAT. FACE THE SCREW'S "
            f"TIP SO THAT, SEATED IN THE {_N['pd-support-bar']} BAR'S THROUGH TAP, IT "
            f"STANDS {pivot_screw.TIP_RECESS[0]:.2f} TO {pivot_screw.TIP_RECESS[1]:.2f} "
            "BELOW THE BAR'S FRONT FACE. THE ARM'S PIVOT BORE WAS REAMED TO THIS "
            "SCREW, CHOSEN BEFORE REAMING SO ITS UNFACED TIP REACHES THAT WINDOW: KEEP "
            "THEM TOGETHER. SEAT IT, THREADLOCKER OPTIONAL (LOW STRENGTH ONLY); THE "
            "ARM FALLS FREELY. PLATEN SLID CLEAR, STAKE THE FRONT TAP MOUTH ONTO THE "
            f"TIP AT {PIVOT_STAKE_POINTS_TEXT}, NOTHING PROUD OF THE FACE "
            f"({PIVOT_VIEW_REF})."
        ),
        "disc-cluster-assembled": (
            f"FIT THE {_N['pd-rack-pinion']} DISC ON THE {_N['pd-transgear-disc-hub']} "
            f"HUB'S SPIGOT, THEN THE HUB'S D-BORE ON THE {_N['pd-transgear-feed-pinion']} "
            "D-FLAT, SPIGOT TO THE STEP."
        ),
        "disc-taps-transferred": (
            "MOUNT THE CLUSTER ON A MANDREL IN THE "
            f"{_N['pd-transgear-feed-pinion']} BORE. WITH A "
            f"\u00d8{disc.TOOTH_SPACE_GAUGE_PIN_DIA_MM:.3f} GAUGE PIN IN EACH "
            f"{_N['pd-rack-pinion']} TOOTH SPACE IN TURN, TAP THE DISC CENTRAL, FACE SQUARE, "
            f"TILL THE DIAL READS {quality.toothspace_runout_tir_mm():.2f} TIR MAX. "
            "SPOT-DRILL THE DISC THROUGH THE "
            f"{hub_geometry.SCREW_COUNT} FLANGE HOLES; DRILL AND TAP {disc_screw.THREAD}. "
            f"FIX WITH {hub_geometry.SCREW_COUNT} {_N['pd-vn-transgear-disc-screw']} SCREWS. "
            f"RECHECK ALL {disc.TEETH} SPACES; "
            "THEN MATCH-MARK DISC AND HUB."
        ),
        "disc-screws-cut": (
            f"CUT {_N['pd-vn-transgear-disc-screw']} TIPS "
            f"{_mm_window(disc_screw.TIP_BELOW_REAR_FACE, 2)} BELOW DISC REAR FACE; "
            "BREAK THE CUT END."
        ),
        "oil-hole-drilled": (
            f"DRILL THE \u00d8{hub.OIL_HOLE_DIA:.1f} OIL HOLE CENTRED ON THE HUB BODY, "
            "THROUGH HUB AND "
            f"SLEEVE IN ONE OPERATION AS {_N['pd-transgear-disc-hub']} SHOWS; "
            "DEBURR THE BORE."
        ),
        "disc-cluster-hung": (
            "OIL THE PIN (LIGHT MACHINE OIL); "
            f"{_N['pd-transgear-rear-bushing']} BUSHING ON THE PIN, CLUSTER ON, "
            f"PINION REARWARD; {_N['pd-transgear-front-bushing']} BUSHING ON THE NOSE "
            f"TRAPS HUB AND DISC; {_N['pd-vn-transgear-retaining-ring']} RING SIDEWAYS "
            "IN THE PIN GROOVE."
        ),
        "disc-cluster-shimmed": (
            f"SHIM AT THE ARM FACE: {_N['pd-vn-transgear-cluster-shim']} SHIMS UNDER "
            f"THE {_N['pd-transgear-rear-bushing']} BUSHING TO {CLUSTER_FLOAT_VIEW_NAME} "
            f"(SHEET {SHEET_NAMES.index('ASSEMBLY AND FIT-UP (CONT.)') + 1}) END "
            "FLOAT (FEELER AT THE RING, CLUSTER REARWARD)."
        ),
        "collar-pins-pressed": (
            f"PRESS {TRANSGEAR_QUANTITIES['pd-vn-transgear-knob-drive-pin']} "
            f"{_N['pd-vn-transgear-knob-drive-pin']} DOWELS INTO THE "
            f"{_N['pd-transgear-drive-collar']} COLLAR TO A STOP, {drive_lo:.2f} TO "
            f"{drive_hi:.2f} PROUD OF ITS FRONT FACE."
        ),
        "pilot-faced-to-fit": (
            f"FACE THE COLLAR'S PILOT {collar.PILOT_PROUD_TEXT} PROUD OF EACH "
            f"{_N['pd-transgear-removable']} WHEEL FLAT ON THE PINS; ELSE STOP AND "
            "REPORT."
        ),
        "knob-stack-fitted": (
            f"KNOB STACK, FRONT TO REAR: {_stack_text()}. SHAFT THROUGH THE LOOSE "
            "RING INTO THE PLATE BORE FROM THE FRONT, PUSHED REARWARD. CUP ON THE "
            f"JOURNAL ON A {knob_shaft.END_FLOAT:.1f} FEELER AT THE BOSS; "
            f"MATCH-DRILL {cup_pin.HOLE_TEXT} THROUGH BOTH "
            f"{knob_cup.PIN_HOLE_FROM_FRONT:.1f} FROM THE CUP FRONT; PRESS THE PIN "
            "IN, CENTRED. COLLAR ON THE CORE UNPINNED, PINS FORWARD. THIS SHAFT IS "
            "THE KNOB; ITS GRIP IS THE COLLAR: HOLD OR TURN THE KNOB BY IT TILL "
            f"STEP {steps.step_number('chain-closed')}, THEN TURN THE CRANK."
        ),
        "latch-hook-fitted": (
            f"SCREW THE {_N['pd-latch-hook']} HOOK'S BASE TO THE BAR'S BACK FACE "
            f"WITH {TRANSGEAR_QUANTITIES['sh-vn-fillister-screw-90280a108']} "
            f"{_N['sh-vn-fillister-screw-90280a108']} SCREWS, ARM HANGING DOWN; ITS "
            "PIN HOLE IS NOT YET DRILLED."
        ),
        "hanger-meshed": (
            f"SWING THE HANGER UP TILL THE {_N['pd-transgear-feed-pinion']} TEETH "
            f"ENTER THE {_N['pd-platen-rack']} RACK. ALIGN A FEED TOOTH CENTRE "
            "DIRECTLY BELOW A RACK SPACE CENTRE. KNOB HELD, SET "
            f"{steps.RACK_DATUM_BACKLASH_TEXT} PLATEN SHAKE AT THAT DATUM "
            "(DIAL ALONG THE RACK): THIS SHAKE SETS THE FEED MESH DEPTH. CLAMP "
            f"THE ARM TO THE BAR. {engaged_feed_text(operating_domain)} "
            f"THE FEED STUD IS THE {_N['pd-transgear-pin']} PIN. "
            "RUN THAT WINDOW: NO TIGHT SPOT, SHAKE AT EVERY TOOTH. "
            "STOP BEFORE EITHER END LIMIT; RESET ONLY WITH FEED DISENGAGED."
        ),
        # The hook's Ø3.3 pin hole is match-drilled from the pin at that mesh,
        # then the hook is hardened and refitted with the hole's lower edge on
        # the pin before its screws are tightened, so the unclamped arm has no
        # room to fall and open the mesh (rack_setup.LATCH_SLACK_ALONG; Codex P1 on
        # b2eb9a0e1).
        "hook-pin-hole-match-drilled": (
            f"HOLDING THAT MESH, MARK THE {_N['pd-vn-transgear-latch-pin']} PIN'S "
            f"AXIS WHERE ITS END BEARS ON THE {_N['pd-latch-hook']} HOOK'S "
            "STRAIGHT RUN. REMOVE THE HOOK; DRILL ITS PIN HOLE AT THE MARK PER "
            f"{_N['pd-latch-hook']}; HARDEN AND TEMPER PER {_N['pd-latch-hook']}. "
            f"REFIT, ITS HOLE'S LOWER EDGE ON THE {_N['pd-vn-transgear-latch-pin']} PIN, "
            "THEN TIGHTEN THE SCREWS. UNCLAMP, LATCH, RE-RUN THE DEFINED "
            f"ENGAGED-FEED WINDOW; RE-CHECK {steps.RACK_DATUM_BACKLASH_TEXT} SHAKE AT "
            "THE DATUM."
        ),
        "loaded-rack-geometry-checked": (
            "HANGER LATCHED, PAPER LOADED. TRAVEL: TURN THE KNOB TO RUN THE "
            "PLATEN THROUGH THE WHOLE ENGAGED WINDOW: NO TIGHT SPOT; ARM, HOOK "
            "AND PLATEN STAY SEATED. BACKLASH: KNOB HELD, ROCK THE PLATEN ALONG "
            "THE RACK AT BOTH ENDS AND THE MIDDLE OF THE WINDOW: SHAKE AT EACH. "
            "ELSE RE-SEAT THE RACK OR GUIDES."
        ),
        "fitup-pose-set": (
            "HANGER LATCHED. PULL THE CRANK SHAFT FORWARD; PUSH THE KNOB SHAFT "
            f"REARWARD ({teeth} ON THE "
            f"RING, RING ON THE HUB). SLIDE THE COLLAR BACK AGAINST THE {teeth}; "
            f"{sprocket.KNOB_CONFIG} AND THUMBNUT ON FINGER-TIGHT, "
            f"{steps.KNOB_HELD_BACK_TEXT}. TURN THE DISC SO, ON THE LINE THROUGH THE "
            f"KNOB AND CLUSTER AXES, A {disc.TEETH}T TOOTH STANDS CENTRED IN A "
            f"{teeth} GAP, WITHIN "
            f"{quality.reducer_setup_clock_deviation_mm():.2f} AT THE PITCH CIRCLE. "
            "TURN THE KNOB: NO TIGHT SPOT, SHAKE AT EVERY TOOTH."
        ),
        "collar-rear-faced-to-fit": (
            f"IN STEP {steps.step_number('fitup-pose-set')}'S POSE, "
            f"{steps.KNOB_HELD_BACK_TEXT}. {collar.BODY_FACE_PHRASE}: SET THE "
            f"{sprocket.KNOB_CONFIG} FRONT FACE {collar.FIT_UP_OFFSET_SET_TEXT} FORWARD "
            f"OF THE {sprocket.CRANK_CONFIG} FRONT FACE. START LONG; STRIP AND FACE "
            "THE REAR TO MOVE THE WHEEL REARWARD, REFITTING WITH THE REAR FACE SEATED. "
            f"FINISHED BODY WITHIN {_N['pd-transgear-drive-collar']}'S FITTED LIMITS; "
            f"ELSE REPORT. STEP {steps.step_number('fitup-accepted')} RE-CHECKS. "
            "THE SETTING LEAVES ROOM FOR END FLOAT AND THE WHEEL'S FLOAT UNDER THE "
            f"NUT: IN SERVICE THE WHEELS RUN WITHIN {collar.CHAIN_OFFSET_LIMIT:.1f} "
            "OF IN LINE, THE #25 CHAIN'S LIMIT."
        ),
        "collar-shoulder-seated": (
            f"SEAT THE {_N['pd-transgear-drive-collar']} D-BORE ON THE SHAFT D-FLAT, "
            f"ITS REAR FACE BEARING ON THE {_N['pd-transgear-knob-shaft']} {KNOB_TEETH}T FRONT FACE. "
            f"{sprocket.KNOB_CONFIG} ON THE DRIVE DOWELS, NUT TIGHT ON THE PILOT. "
            "THUMBNUT IS A CLAMP ONLY; NEVER TURNED TO DRIVE."
        ),
        "stud-end-cut": (
            f"IF THE {_N['pd-transgear-knob-shaft']} STUD END STANDS PROUD OF THE "
            f"THUMBNUT RIM, {collar.STUD_CUT_PHRASE}."
        ),
        "collar-disc-air-inspected": (
            f"CHAIN OFF. REMOVE THE {_N['pd-platen']} PLATEN, KEEPING THE ARM HELD IN ITS "
            "OPERATING LATCH POSE. "
            f"{collar.COLLAR_DISC_AIR_PHRASE}; "
            f"ONE DISC TURN = {disc.TEETH / KNOB_TEETH:g} KNOB TURNS. "
            "REFIT THE PLATEN AND LATCH THE HANGER; RE-CHECK THE OVERLAP AIR "
            "AND RACK MESH. ELSE REPORT."
        ),
        "fitup-accepted": (
            f"ACCEPT, IN STEP {steps.step_number('fitup-pose-set')}'S POSE: "
            f"{sprocket.KNOB_CONFIG} FRONT FACE {steps.OFFSET_ACCEPT_TEXT} FORWARD "
            f"OF THE {sprocket.CRANK_CONFIG} FRONT FACE "
            f"(STEP {steps.step_number('collar-rear-faced-to-fit')}'S SETTING, WIDENED "
            f"FOR REFITTING AND GAUGE SPREAD: THE {sprocket.KNOB_CONFIG} UP TO "
            f"{steps.OFFSET_ACCEPT_TOL - collar.FIT_UP_OFFSET_TARGET:.2f} BEHIND "
            f"PASSES); KNOB END FLOAT {knob_lo:.2f} TO {knob_hi:.2f}; "
            f"{sprocket.KNOB_CONFIG} FREE "
            "UNDER THE NUT; THE HANGER FREE; RING GAP PER "
            f"{CLUSTER_FLOAT_VIEW_NAME} AND THE DISC TURNS FREE; COLLAR TO DISC "
            f"AIR PER STEP {steps.step_number('collar-disc-air-inspected')}, "
            f"{steps.COLLAR_DISC_AIR_TEXT} AT OVERLAP AFTER REFITTING AND LATCHING. "
            "ELSE REPORT: NO FACING OR FITTING."
        ),
        "chain-closed": (
            f"LOOP {chain.LINK_COUNT} PITCHES OF ANSI #25 CHAIN, "
            f"{CHAIN_QUANTITIES['sh-vn-chain-link--InnerLink']} {_N['sh-vn-chain-link--InnerLink']} INNER "
            f"AND {CHAIN_QUANTITIES['sh-vn-chain-link--OuterLink']} {_N['sh-vn-chain-link--OuterLink']} "
            f"OUTER LINKS, OVER THE {sprocket.KNOB_CONFIG} AND THE {sprocket.CRANK_CONFIG}; "
            f"JOIN THE ENDS WITH THE {_N['pd-vn-chain-connecting-link']} #25 CONNECTING "
            f"LINK, MCMASTER {_SKU['pd-vn-chain-connecting-link']}, ITS CLIP'S CLOSED END "
            "LEADING IN THE DIRECTION OF TRAVEL. THE CENTRES ARE FIXED: NO TENSIONING, "
            "THE SLACK RUN HANGS FREE."
        ),
        "chain-run-accepted": (
            "TURN THE CRANK 2 TURNS EACH WAY: THE CHAIN SEATS ON EVERY TOOTH OF "
            "BOTH WHEELS WITHOUT CLIMBING OR A TIGHT SPOT, AND THE SLACK RUN "
            "TOUCHES NOTHING. OTHERWISE REPORT."
        ),
    }


def _step_column(heading: str, keys: tuple[str, ...], text: dict[str, str]) -> str:
    """The heading, then each numbered step with one blank line between steps."""
    lines = textwrap.wrap(
        heading,
        width=FITUP_LINE_WIDTH,
        break_on_hyphens=False,
        break_long_words=False,
    )
    for index, key in enumerate(keys):
        if index:
            lines.append("")
        lines += textwrap.wrap(
            text[key],
            width=FITUP_LINE_WIDTH,
            initial_indent=f"{steps.step_number(key)}. ",
            subsequent_indent="   ",
            break_on_hyphens=False,
            break_long_words=False,
        )
    return "\n".join(lines)


def _step_columns(
    *, operating_domain: RackOperatingDomain,
) -> tuple[str, tuple[str, str], tuple[str, str], tuple[str, str]]:
    """Sheet 4's platen steps, then the two columns on each of sheets 5 to 7."""
    text = _step_text(operating_domain=operating_domain)
    if set(text) != set(steps.SEQUENCE):
        raise AssertionError("paper-drive step text must cover exactly the sequence")
    first = steps.step_number(FITUP_FIRST_COLUMN_KEY) - 1
    second = steps.step_number(FITUP_SECOND_COLUMN_KEY) - 1
    continued = steps.step_number(FITUP_CONTINUED_KEY) - 1
    continued_second = steps.step_number(FITUP_CONTINUED_SECOND_KEY) - 1
    chain_start = steps.step_number(FITUP_CHAIN_KEY) - 1
    chain_second = steps.step_number(CHAIN_SECOND_COLUMN_KEY) - 1
    fitup_sheet = SHEET_NAMES.index("ASSEMBLY AND FIT-UP") + 1
    continued_sheet = SHEET_NAMES.index("ASSEMBLY AND FIT-UP (CONT.)") + 1
    return (
        _step_column(
            f"PLATEN AND SUPPORT; STEP {steps.step_number(FITUP_FIRST_COLUMN_KEY)} "
            f"ON: SHEET {fitup_sheet}",
            steps.SEQUENCE[:first],
            text,
        ),
        (
            _step_column("THE TRANSGEAR", steps.SEQUENCE[first:second], text),
            "\n".join(
                (
                    _step_column(
                        "THE TRANSGEAR, CONTINUED",
                        steps.SEQUENCE[second:continued],
                        text,
                    ),
                    "",
                    f"THE TRANSGEAR (CONT.): SHEET {continued_sheet}, "
                    f"STEP {steps.step_number(FITUP_CONTINUED_KEY)} ON",
                )
            ),
        ),
        (
            _step_column(
                "THE TRANSGEAR (CONT.)", steps.SEQUENCE[continued:continued_second], text
            ),
            "\n".join(
                (
                    _step_column(
                        "THE TRANSGEAR, CONTINUED",
                        steps.SEQUENCE[continued_second:chain_start],
                        text,
                    ),
                    "",
                    f"CHAIN FIT-UP: SHEET {SHEET_NAMES.index('CHAIN FIT-UP') + 1}, "
                    f"STEP {steps.step_number(FITUP_CHAIN_KEY)} ON",
                )
            ),
        ),
        (
            _step_column(
                f"CHAIN FIT-UP, TRANSGEAR DONE PER SHEETS {fitup_sheet} AND "
                f"{continued_sheet}; CRANK SIDE DONE PER {steps.CRANK_SIDE_REF}",
                steps.SEQUENCE[chain_start:chain_second],
                text,
            ),
            _step_column(
                "CHAIN FIT-UP, CONTINUED", steps.SEQUENCE[chain_second:], text
            ),
        ),
    )


@dataclass(frozen=True)
class StepNotes:
    """Explicitly formatted note fields, not a module-global qualification."""

    platen_steps: str
    fitup_notes: tuple[str, str]
    fitup_continued_notes: tuple[str, str]
    chain_notes: tuple[str, str]

    @property
    def fitup_steps(self) -> str:
        """Each sheet's columns read left to right; sheets 6 and 7 continue sheet 5."""
        return "\n".join(
            (
                self.platen_steps,
                *self.fitup_notes,
                *self.fitup_continued_notes,
                *self.chain_notes,
            )
        )

    @property
    def exploded_caption_xy(self) -> tuple[float, float]:
        """One blank line under the actual steps, at default 4.5 mm line pitch."""
        return (
            PLATEN_NOTE_XY[0],
            PLATEN_NOTE_XY[1] - (len(self.platen_steps.splitlines()) + 1) * 0.0045,
        )


def format_step_notes(*, operating_domain: RackOperatingDomain) -> StepNotes:
    """Format the sheet steps around a supplied engaged-feed window."""
    return StepNotes(*_step_columns(operating_domain=operating_domain))


def require_step_notes() -> StepNotes:
    """Guard the full paper sweep on the finite rack before printing."""
    return format_step_notes(operating_domain=rack_setup.feed_rack_operating_domain())


# The exploded view's caption at each scale it may take.
EXPLODED_CAPTIONS = {
    scale: f"PLATEN AND SUPPORT EXPLODED {_scale_text(scale)}; "
    f"BOM: SHEET {SHEET_NAMES.index('BILL OF MATERIALS') + 1}"
    for scale in EXPLODED_SCALE_LADDER
}
# Sheet 1, at each scale its isometric may take: which removable is which,
# and where every other item balloons.
ASSEMBLED_CAPTIONS = {
    scale: "\n".join(
        (
            "\n".join(
                textwrap.wrap(
                    f"ISOMETRIC {_scale_text(scale)}: THE "
                    f"{_N['pd-transgear-removable']} ON THE BASE DECK IS THE T18 "
                    f"SPARE, STORED LOOSE; THE {sprocket.KNOB_CONFIG} IS ON THE KNOB, "
                    f"THE {sprocket.CRANK_CONFIG} ON THE "
                    "CRANK. PLATEN AND SUPPORT ITEMS: SHEET "
                    f"{SHEET_NAMES.index('PLATEN AND SUPPORT') + 1}; TRANSGEAR "
                    f"ITEMS: SHEETS {SHEET_NAMES.index('TRANSGEAR VIEWS') + 1} AND "
                    f"{SHEET_NAMES.index('TRANSGEAR EXPLODED') + 1}.",
                    width=FITUP_LINE_WIDTH,
                )
            ),
            steps.PAPER_FEED_REFERENCE_TEXT,
        )
    )
    for scale in ISO_SCALE_LADDER
}
TRANSGEAR_CAPTION = (
    f"TRANSGEAR {TRANSGEAR_VIEW_SCALE[0]:g}:{TRANSGEAR_VIEW_SCALE[1]:g}; "
    f"EXPLODED: SHEET {SHEET_NAMES.index('TRANSGEAR EXPLODED') + 1};\n"
    f"ASSEMBLY AND FIT-UP: SHEETS {SHEET_NAMES.index('ASSEMBLY AND FIT-UP') + 1} "
    f"TO {SHEET_NAMES.index('CHAIN FIT-UP') + 1}; "
    f"BOM: SHEET {SHEET_NAMES.index('BILL OF MATERIALS') + 1}"
)
# Sheet 3's caption, right of the knob-stack view and under the cluster's.
TRANSGEAR_EXPLODED_CAPTION = "\n".join(
    textwrap.wrap(
        f"TRANSGEAR EXPLODED, ISOMETRIC, {_scale_text(TRANSGEAR_EXPLODED_SCALE)}. "
        "LEFT: THE HANGER ARM AND ITS PLATE, AND THE KNOB STACK ON ITS SHAFT. "
        "ABOVE: THE DISC CLUSTER ON ITS PIN. EACH PART IS DRAWN APART ALONG ITS "
        "AXIS IN THE ORDER IT GOES ON. HANGER PIVOT: SECTION A-A, SHEET "
        f"{SHEET_NAMES.index('TRANSGEAR VIEWS') + 1}; LATCH HOOK: SHEET "
        f"{SHEET_NAMES.index('TRANSGEAR VIEWS') + 1}. ASSEMBLY: SHEETS "
        f"{SHEET_NAMES.index('ASSEMBLY AND FIT-UP') + 1} TO "
        f"{SHEET_NAMES.index('CHAIN FIT-UP') + 1}; BOM: SHEET "
        f"{SHEET_NAMES.index('BILL OF MATERIALS') + 1}.",
        width=TRANSGEAR_EXPLODED_CAPTION_WIDTH,
        break_on_hyphens=False,
    )
)
FITUP_REFERENCE_CAPTION = (
    f"REFERENCE {FITUP_SCALE[0]:g}:{FITUP_SCALE[1]:g}; ITEMS: SHEETS 1 TO "
    f"{SHEET_NAMES.index('PLATEN AND SUPPORT') + 1}"
)


def sheet_texts(notes: StepNotes) -> tuple[str, ...]:
    """Every explicitly formatted package text besides the BOM's own cells."""
    return (
        notes.platen_steps,
        *notes.fitup_notes,
        *notes.fitup_continued_notes,
        *notes.chain_notes,
        *EXPLODED_CAPTIONS.values(),
        *ASSEMBLED_CAPTIONS.values(),
        TRANSGEAR_CAPTION,
        TRANSGEAR_EXPLODED_CAPTION,
        FITUP_REFERENCE_CAPTION,
        BOM_REFERENCE_CAPTION,
        PIVOT_CAPTION,
        PIVOT_STAKE_NOTE,
    )


# ============================ COM helpers =======================================


def _activate_sheet(adapter: Any, name: str) -> None:
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    if not ddoc.ActivateSheet(name):
        raise RuntimeError(f"failed to activate drawing sheet {name!r}")
    current = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
    if str(current.GetName() or "") != name:
        raise RuntimeError(f"active drawing sheet is not {name!r}")


def _place_sheet_note(
    adapter: Any, sheet_name: str, text: str, xy: tuple[float, float], *, label: str
) -> None:
    """A sheet-owned note: activate the sheet so no view owns it."""
    _activate_sheet(adapter, sheet_name)
    note = add_note(adapter, text, *xy)
    if note is None:
        raise RuntimeError(f"failed to place the paper-drive {label}")
    printed = str(_early_bound(note, "INote").GetText() or "")
    if printed.replace("\r\n", "\n").replace("\r", "\n") != text:
        raise RuntimeError(f"paper-drive {label} printed as {printed!r}")


def _source_family_counts(model: Any) -> Counter[str]:
    """Count physical file/member identities, not colliding printed Numbers."""
    assembly = _early_bound(model, "IAssemblyDoc")
    counts: Counter[str] = Counter()
    seen_names: set[str] = set()
    for raw in tuple(assembly.GetComponents(True) or ()):
        component = _early_bound(raw, "IComponent2")
        name = str(component.Name2)
        if name in seen_names:
            raise RuntimeError(f"paper-drive repeats native component {name!r}")
        seen_names.add(name)
        stem, configuration = component_identity(component)
        matches = [
            key for key, (native_stem, member) in BOM_COMPONENT_IDENTITIES.items()
            if stem == native_stem and (member is None or configuration == member)
        ]
        if len(matches) != 1:
            raise RuntimeError(
                f"paper-drive component {name!r} has no unique BOM identity: "
                f"{(stem, configuration)!r}"
            )
        counts[matches[0]] += 1
    if set(counts) != set(BOM_PART_NUMBERS):
        raise RuntimeError(
            f"paper-drive families {sorted(counts)!r} != BOM {sorted(BOM_PART_NUMBERS)!r}"
        )
    wrong = {
        stem: counts[stem]
        for stem, quantity in {**TRANSGEAR_QUANTITIES, **CHAIN_QUANTITIES}.items()
        if counts[stem] != quantity
    }
    if wrong:
        raise RuntimeError(f"paper-drive component counts off the contract: {wrong!r}")
    return counts


def _validate_persisted_explode(model: Any) -> None:
    """The builder authored PAPER_DRIVE_EXPLODED in both drawing configurations."""
    assembly = _early_bound(model, "IAssemblyDoc")
    for configuration in (explode.SOURCE_CONFIGURATION, SIMPLIFIED_VIEW_CONFIGURATION):
        wanted = (exploded_view_name(configuration),)
        names = tuple(assembly.GetExplodedViewNames2(configuration) or ())
        if names != wanted:
            raise RuntimeError(
                f"paper-drive source {configuration} exploded views {names!r} "
                f"!= {wanted!r}"
            )


def _create_sheets(adapter: Any) -> None:
    new_project_drawing(adapter, layout=SPEC.layout, scale=ASSEMBLED_SCALE)
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="paper-drive package")
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    for name in SHEET_NAMES:
        _activate_sheet(adapter, name)
        sheet = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
        numerator, denominator = SHEET_SCALES[name]
        if not sheet.SetScale(float(numerator), float(denominator), False, False):
            raise RuntimeError(f"failed to set paper-drive sheet scale: {name}")


def _set_bom_column_widths(
    table: Any, widths: Sequence[tuple[int, float]],
) -> None:
    """Author widths only while physical and legacy column indices agree."""
    physical = _bom_physical_columns(table, label="paper-drive widths")
    visible = int(table.ColumnCount)
    if (
        len(physical) != visible + 1
        or physical[-1] != (201, True)
        or any(hidden or kind == 201 for kind, hidden in physical[:-1])
    ):
        raise RuntimeError("paper-drive BOM widths need one hidden trailing native column")
    native_column = len(physical) - 1
    # Restore exactly the visibility slot that was exposed, even if the typed
    # census changes meanwhile (latent Quantity columns shift this index).
    native_visibility = _bom_mutable_visibility_index(
        table, native_column, label="paper-drive widths"
    )
    original_hidden = _bom_column_hidden_at(
        table, native_visibility, native_column, label="paper-drive widths"
    )
    if original_hidden is not True:
        raise RuntimeError("paper-drive BOM native column hidden state is not proven")
    if (
        not widths
        or any(type(column) is not int or not 0 <= column < visible for column, _width in widths)
        or len({column for column, _width in widths}) != len(widths)
        or any(not math.isfinite(width) or width <= 0.0 for _column, width in widths)
    ):
        raise ValueError("paper-drive BOM width targets must be distinct visible columns")

    # Keep the existing 118 mm native-key width for this production canary.
    # Native2507 disproved the hidden201 row-minimum cause: Qty was hidden instead.
    targets = (*widths, (native_column, BOM_COLUMN_WIDTHS["description"]))

    def column_record(index: int, include_hidden: bool) -> tuple[Any, Any, Any]:
        return (
            table.GetColumnType3(index, include_hidden),
            table.GetColumnTitle2(index, include_hidden),
            table.DisplayedText2(0, index, include_hidden),
        )

    original_records = tuple(column_record(index, True) for index in range(len(physical)))
    all_visible = tuple((kind, False) for kind, _hidden in physical)

    def prove_all_visible() -> None:
        if _bom_physical_columns(table, label="paper-drive visible widths") != all_visible:
            raise RuntimeError("paper-drive BOM column visibility/order changed during width setup")
        for index, expected in enumerate(original_records):
            if column_record(index, True) != expected or column_record(index, False) != expected:
                raise RuntimeError(
                    f"paper-drive BOM physical/legacy column identity disagrees at {index}"
                )

    primary_error: BaseException | None = None
    try:
        # Width indices remain unversioned: author only in the all-visible window.
        table.SetColumnHidden(native_visibility, False)  # VT_VOID, not success.
        prove_all_visible()
        expected_widths = [float(table.GetColumnWidth(index)) for index in range(len(physical))]
        if any(not math.isfinite(width) or width <= 0.0 for width in expected_widths):
            raise RuntimeError("paper-drive BOM all-visible baseline widths are invalid")
        for column, width in targets:
            returned = float(table.SetColumnWidth(column, width, 0))
            if not math.isfinite(returned) or abs(returned - width) > 1e-6:
                raise RuntimeError(f"paper-drive BOM column {column} width was refused")
            expected_widths[column] = width
            actual_widths = tuple(
                float(table.GetColumnWidth(index)) for index in range(len(physical))
            )
            if any(
                not math.isfinite(actual) or abs(actual - expected) > 1e-6
                for actual, expected in zip(actual_widths, expected_widths, strict=True)
            ):
                raise RuntimeError(
                    f"paper-drive BOM column {column} width readback or native key width changed"
                )
        prove_all_visible()
    except BaseException as error:
        primary_error = error
        raise
    finally:
        try:
            # Also restore if exposing the native column raised after taking effect.
            table.SetColumnHidden(native_visibility, original_hidden)  # VT_VOID.
            if _bom_physical_columns(table, label="paper-drive restored widths") != physical:
                raise RuntimeError("paper-drive BOM native column hidden state was not restored")
            if tuple(column_record(index, True) for index in range(len(physical))) != original_records:
                raise RuntimeError("paper-drive BOM column identities changed while restoring visibility")
        except BaseException as error:
            if primary_error is None:
                raise
            primary_error.add_note(f"paper-drive BOM width visibility restoration also failed: {error!r}")


def _validate_bom(
    adapter: Any, table: Any, counts: Counter[str], *, configuration: str
) -> tuple[tuple[str, str], ...]:
    """Prove native row identities, associative Numbers and actual quantities."""
    table = _early_bound(table, "ITableAnnotation")
    rows = int(table.RowCount)
    columns = int(table.ColumnCount)
    if rows != len(BOM_PART_NUMBERS) + 1 or columns < 4:
        raise RuntimeError(
            f"paper-drive BOM is {rows}x{columns}; expected {len(BOM_PART_NUMBERS) + 1} rows"
        )
    if int(table.TotalRowCount) != rows or any(
        table.RowHidden(row) is not False for row in range(rows)
    ):
        raise RuntimeError("paper-drive BOM has hidden or unreadable physical rows")
    contents = tuple(
        tuple(
            str(table.DisplayedText2(row, column, True) or "").strip()
            for column in range(columns)
        )
        for row in range(rows)
    )
    header = tuple(cell.upper() for cell in contents[0])

    def column_named(predicate: Callable[[str], bool], label: str) -> int:
        matches = [index for index, cell in enumerate(header) if predicate(cell)]
        if len(matches) != 1:
            raise RuntimeError(
                f"paper-drive BOM has no unique {label} column: {header!r}"
            )
        return matches[0]

    item_column = column_named(lambda cell: cell.startswith("ITEM NO"), "ITEM NO.")
    part_column = column_named(lambda cell: cell == "PART NUMBER", "PART NUMBER")
    description_column = column_named(lambda cell: cell == "DESCRIPTION", "DESCRIPTION")
    quantity_column = column_named(lambda cell: cell.startswith("QTY"), "QTY.")
    _set_bom_column_widths(
        table,
        (
            (item_column, BOM_COLUMN_WIDTHS["item"]),
            (part_column, BOM_COLUMN_WIDTHS["part"]),
            (description_column, BOM_COLUMN_WIDTHS["description"]),
            (quantity_column, BOM_COLUMN_WIDTHS["quantity"]),
        ),
    )

    actual: dict[str, tuple[int, str, str, str]] = {}
    native_rows = bom_row_identities(
        table, configuration=configuration, component_identities=BOM_COMPONENT_IDENTITIES
    )
    for stem, row_index in native_rows.items():
        row = contents[row_index]
        actual[stem] = (row_index, row[item_column], row[description_column], row[quantity_column])
    if set(actual) != set(BOM_PART_NUMBERS):
        raise RuntimeError(
            f"paper-drive BOM identities {sorted(actual)!r} != {sorted(BOM_PART_NUMBERS)!r}"
        )
    items = {values[1] for values in actual.values()}
    if items != {str(item) for item in range(1, len(BOM_PART_NUMBERS) + 1)}:
        raise RuntimeError(
            f"paper-drive BOM item numbers {sorted(items)!r} are not contiguous"
        )
    for stem, (row_index, _item, description, quantity) in actual.items():
        number = BOM_PART_NUMBERS[stem]
        if contents[row_index][part_column] != number:
            raise RuntimeError(
                f"paper-drive associative Number for {stem!r} reads "
                f"{contents[row_index][part_column]!r}, expected {number!r}"
            )
        if description != BOM_DESCRIPTIONS[stem]:
            raise RuntimeError(f"paper-drive BOM description mismatch for {stem!r}")
        if quantity != str(counts[stem]):
            raise RuntimeError(
                f"paper-drive BOM quantity for {stem!r} is {quantity!r}, "
                f"model has {counts[stem]}"
            )
    for row in range(rows):
        table.SetRowHeight(row, BOM_ROW_HEIGHT, 0)
    rebuilt = adapter.currentModel.EditRebuild3()
    if not rebuilt:
        raise RuntimeError("paper-drive BOM rebuild failed")
    if int(table.RowCount) != rows or int(table.ColumnCount) != columns:
        raise RuntimeError("paper-drive BOM dimensions changed during its final rebuild")
    if int(table.TotalRowCount) != rows or any(
        table.RowHidden(row) is not False for row in range(rows)
    ):
        raise RuntimeError("paper-drive BOM physical row visibility changed during its final rebuild")
    bom_feature = _early_bound(table, "IBomTableAnnotation").BomFeature
    if bom_feature is None:
        raise RuntimeError("paper-drive BOM lost its native feature")
    bom_feature = _early_bound(bom_feature, "IBomFeature")
    grouping = int(bom_feature.PartConfigurationGrouping)
    one_item = bool(bom_feature.DisplayAsOneItem)
    if grouping != 3 or one_item:
        raise RuntimeError(
            "paper-drive BOM configuration grouping changed during its final rebuild: "
            f"grouping={grouping}, one_item={one_item}"
        )
    final_native_rows = bom_row_identities(
        table, configuration=configuration, component_identities=BOM_COMPONENT_IDENTITIES
    )
    if final_native_rows != native_rows:
        raise RuntimeError(
            "paper-drive BOM native associations changed during its final rebuild: "
            f"{native_rows!r} -> {final_native_rows!r}"
        )
    for stem, (row_index, *_rest) in actual.items():
        applied = str(table.DisplayedText2(row_index, part_column, True) or "").strip()
        if applied != BOM_PART_NUMBERS[stem]:
            raise RuntimeError(
                f"paper-drive BOM part number for {stem!r} reads {applied!r}"
            )
        final_row = tuple(
            str(table.DisplayedText2(row_index, column, True) or "").strip()
            for column in range(columns)
        )
        if final_row != contents[row_index]:
            raise RuntimeError(
                f"paper-drive BOM row for {stem!r} changed during its final rebuild: "
                f"{contents[row_index]!r} -> {final_row!r}"
            )
    validate_bom_number_property(
        table,
        configuration=configuration,
        label="paper-drive",
        expected_rows=len(BOM_PART_NUMBERS) + 1,
        occurrence_quantities=True,
    )
    return tuple((stem, actual[stem][1]) for stem in BOM_PART_NUMBERS)


def bom_extent_violations(
    anchor: tuple[float, float], width: float, height: float
) -> list[str]:
    """Contain a measured native piece clear of border, title and reference."""
    template = DRAWING_TEMPLATES[SPEC.layout]
    left, top = anchor
    right, bottom = left + width, top - height
    border = SHEET_INNER_BORDER_BOTTOM + BOM_BORDER_CLEARANCE
    tolerance = 1e-9  # floating-point arithmetic, not a paper-clearance allowance
    findings = []
    if left < border - tolerance or right > template.width_m - border + tolerance:
        findings.append("table crosses the inner side border")
    if top > template.height_m - border + tolerance or bottom < border - tolerance:
        findings.append("table crosses the inner top or bottom border")
    if (
        right > template.title_block_left_m
        and bottom < template.title_block_top_m + BOM_BORDER_CLEARANCE - tolerance
    ):
        findings.append("table enters the title block")
    if left < BOM_ANCHOR[0] + sum(BOM_COLUMN_WIDTHS.values()) and (
        bottom < BOM_REFERENCE_LIMITS[3] + BOM_BORDER_CLEARANCE - tolerance
    ):
        findings.append("table enters the assembly reference field")
    return findings


def bom_split_row(row_heights: Sequence[float], header_count: int) -> int:
    """Choose a horizontal split using every rebuilt row, including headers."""
    if header_count < 1 or len(row_heights) - header_count < 2:
        raise ValueError("paper-drive BOM needs a header and two data rows")
    if any(not math.isfinite(height) or height <= 0 for height in row_heights):
        raise ValueError("paper-drive BOM row heights are unreadable")
    width = sum(BOM_COLUMN_WIDTHS.values())
    header_height = sum(row_heights[:header_count])
    candidates = []
    for split_after in range(header_count, len(row_heights) - 1):
        first_height = sum(row_heights[:split_after + 1])
        second_height = header_height + sum(row_heights[split_after + 1:])
        if not bom_extent_violations(BOM_ANCHOR, width, first_height) and not (
            bom_extent_violations(BOM_SECOND_ANCHOR, width, second_height)
        ):
            candidates.append((abs(first_height - second_height), split_after))
    if not candidates:
        raise RuntimeError(
            "complete paper-drive BOM does not fit its two native fields: "
            f"rebuilt rows {tuple(height * 1000 for height in row_heights)!r} mm"
        )
    return min(candidates)[1]


def _bom_piece_grid_bounds(
    annotation: Any, *, row_heights: Sequence[float], piece: int
) -> tuple[float, float, float, float]:
    """Prove this fixed four-column piece from its actual displayed grid."""
    tolerance = 1e-7
    evidence: dict[str, Any] = {
        "piece": piece, "expected_rows": len(row_heights),
        "encoding": "GetLineAtIndex3: metadata[0:4], startXYZ[4:7], endXYZ[7:10]",
        "coordinate_contract": "untransformed sheet metres; native anchor and row readback checked",
        "lines": [],
    }
    try:
        if not 2 <= len(row_heights) <= 44 or any(
            not math.isfinite(height) or height <= 0.0 for height in row_heights
        ):
            raise RuntimeError("paper-drive BOM displayed grid native row heights are unreadable")
        evidence["native_row_heights_m"] = tuple(row_heights)
        position = tuple(float(value) for value in annotation.GetPosition())
        evidence["native_annotation_position_m"] = tuple(
            value if math.isfinite(value) else repr(value) for value in position
        )
        if (
            len(position) != 3 or any(not math.isfinite(value) for value in position)
            or abs(position[2]) > tolerance
        ):
            raise RuntimeError(f"paper-drive BOM position unreadable: {position!r}")
        raw_display = annotation.GetDisplayData()
        if raw_display is None:
            raise RuntimeError("paper-drive BOM displayed grid display data is unavailable")
        display = _early_bound(raw_display, "IDisplayData")
        count = display.GetLineCount()
        evidence["line_count"] = count
        if type(count) is not int or not 1 <= count <= 1024:
            raise RuntimeError("paper-drive BOM displayed grid line count is unsupported")
        horizontal: list[tuple[float, float, float]] = []
        vertical: list[tuple[float, float, float]] = []
        zero_length = []
        for index in range(count):
            raw_line = display.GetLineAtIndex3(index)
            try:
                if len(raw_line) != 10:
                    raise ValueError("native line record length is not ten")
                values = tuple(float(value) for value in raw_line)
            except (TypeError, ValueError, OverflowError) as error:
                evidence["malformed_line"] = {"index": index, "raw": repr(raw_line)[:512]}
                raise RuntimeError(
                    f"paper-drive BOM displayed grid line {index} is not a ten-value record"
                ) from error
            evidence["lines"].append(tuple(
                value if math.isfinite(value) else repr(value) for value in values
            ))
            if any(not math.isfinite(value) for value in values):
                raise RuntimeError(
                    f"paper-drive BOM displayed grid line {index} has non-finite values"
                )
            start, end = values[4:7], values[7:10]
            if start == end:
                zero_length.append(index)
                continue
            if abs(start[2]) > tolerance or abs(end[2]) > tolerance:
                raise RuntimeError("paper-drive BOM displayed grid has non-sheet Z coordinates")
            dx, dy = abs(start[0] - end[0]), abs(start[1] - end[1])
            if dx <= tolerance and dy <= tolerance:
                raise RuntimeError("paper-drive BOM displayed grid contains an ambiguous short nonzero line")
            if dy <= tolerance:
                horizontal.append((start[1], min(start[0], end[0]), max(start[0], end[0])))
            elif dx <= tolerance:
                vertical.append((start[0], min(start[1], end[1]), max(start[1], end[1])))
            else:
                raise RuntimeError("paper-drive BOM displayed grid has unsupported non-axis-aligned geometry")
        evidence["zero_length_line_indices"] = zero_length

        def coordinates(values: list[float]) -> tuple[float, ...]:
            representatives: list[float] = []
            for value in sorted(values):
                # Each cluster stays anchored to its first observed coordinate.
                if not representatives or value - representatives[-1] > tolerance:
                    representatives.append(value)
            return tuple(representatives)

        xs = coordinates([coordinate for coordinate, _start, _end in vertical])
        ys = coordinates([coordinate for coordinate, _start, _end in horizontal])
        evidence["x_boundaries_m"], evidence["y_boundaries_m"] = xs, ys
        if len(xs) != 5 or len(ys) != len(row_heights) + 1:
            raise RuntimeError(
                "paper-drive BOM displayed grid boundary counts are "
                f"{len(xs)}x{len(ys)}; expected 5x{len(row_heights) + 1}"
            )

        def prove_coverage(
            segments: list[tuple[float, float, float]],
            boundaries: tuple[float, ...], lower: float, upper: float, direction: str,
        ) -> None:
            if any(
                start < lower - tolerance or end > upper + tolerance
                for _coordinate, start, end in segments
            ):
                raise RuntimeError(
                    f"paper-drive BOM displayed grid has outlying {direction} boundary geometry"
                )
            for boundary in boundaries:
                reached = lower
                for start, end in sorted(
                    (start, end) for coordinate, start, end in segments
                    if abs(coordinate - boundary) <= tolerance
                ):
                    if start > reached + tolerance:
                        break
                    reached = max(reached, end)
                if reached < upper - tolerance:
                    raise RuntimeError(
                        f"paper-drive BOM displayed grid has incomplete {direction} boundary coverage"
                    )

        prove_coverage(horizontal, ys, xs[0], xs[-1], "horizontal")
        prove_coverage(vertical, xs, ys[0], ys[-1], "vertical")
        widths = tuple(right - left for left, right in zip(xs, xs[1:]))
        heights = tuple(
            ys[index + 1] - ys[index] for index in range(len(ys) - 2, -1, -1)
        )
        bounds = (xs[0], ys[0], xs[-1], ys[-1])
        evidence.update({
            "bounds_m": bounds, "column_widths_m": widths, "row_heights_m": heights,
        })
        if any(
            abs(actual - expected) > 1e-6
            for actual, expected in zip(widths, BOM_COLUMN_WIDTHS.values(), strict=True)
        ):
            raise RuntimeError("paper-drive BOM displayed grid column widths changed")
        if any(
            abs(actual - expected) > 1e-6
            for actual, expected in zip(heights, row_heights, strict=True)
        ):
            raise RuntimeError(
                "paper-drive BOM displayed grid row heights disagree with native split rows"
            )
        if abs(bounds[0] - position[0]) > 1e-6 or abs(bounds[3] - position[1]) > 1e-6:
            raise RuntimeError("paper-drive BOM displayed grid does not match its native annotation anchor")
        return bounds
    except Exception as error:
        evidence["error"] = f"{type(error).__name__}: {error}"[:512]
        raise
    finally:
        try:
            _telemetry.info("drawing.pd_bom_grid " + json.dumps(evidence, separators=(",", ":")))
        except Exception:
            pass  # Native geometry failures must survive observational logging.


def _assert_bom_pieces(
    pieces: Sequence[Any], *, header_count: int, total_rows: int,
    configuration: str | None = None,
    expected_snapshot: BomSnapshot | None = None,
) -> None:
    """Read split ranges and physical extents; every logical data row survives."""
    if len(pieces) != 2:
        raise RuntimeError("paper-drive BOM split needs exactly two native pieces")
    membership: Counter[int] = Counter()
    findings = []
    validated_pieces = []
    if expected_snapshot is not None and (
        configuration is None
        or tuple(row[0] for row in expected_snapshot) != tuple(range(header_count, total_rows))
    ):
        raise RuntimeError("paper-drive BOM validated snapshot has invalid row coverage")
    for raw in pieces:
        piece = _early_bound(raw, "ITableAnnotation")
        info = tuple(piece.GetSplitInformation(0, 0, 0, 0))
        if len(info) != 5:
            raise RuntimeError(f"paper-drive BOM split information unreadable: {info!r}")
        direction, _index, count, start, end = (int(value) for value in info)
        if direction != 1 or not (0 <= start <= end < total_rows):
            raise RuntimeError(f"paper-drive BOM split range invalid: {info!r}")
        data_rows = tuple(range(max(start, header_count), end + 1))
        membership.update(data_rows)
        validated_pieces.append((piece, (direction, _index, count, start, end), data_rows))
    if membership != Counter(range(header_count, total_rows)):
        raise RuntimeError("paper-drive BOM split: split pieces omit or repeat logical data rows")
    for index, (piece, info, data_rows) in enumerate(validated_pieces):
        _direction, _native_index, count, start, end = info
        _telemetry.event(
            "drawing.bom_piece_row_range", piece=index + 1,
            split_information=info, configuration=configuration,
        )
        if configuration is not None:
            current = validate_bom_number_property(
                piece,
                configuration=configuration,
                label=f"paper-drive split BOM piece {index + 1}",
                row_indices=data_rows,
                occurrence_quantities=True,
            )
            if expected_snapshot is not None and current != tuple(
                row for row in expected_snapshot if row[0] in data_rows
            ):
                raise RuntimeError(
                    "paper-drive split BOM native membership or quantities changed"
                )
        rows = sorted({*range(header_count), *range(start, end + 1)})
        row_heights = tuple(float(piece.GetRowHeight(row)) for row in rows)
        raw_annotation = piece.GetAnnotation()
        if raw_annotation is None:
            raise RuntimeError("paper-drive BOM split annotation is unavailable")
        annotation = _early_bound(raw_annotation, "IAnnotation")
        left, bottom, right, top = _bom_piece_grid_bounds(
            annotation, row_heights=row_heights, piece=index + 1
        )
        anchor = (left, top)
        width, height = right - left, top - bottom
        violations = bom_extent_violations(anchor, width, height)
        expected_anchor = (BOM_ANCHOR, BOM_SECOND_ANCHOR)[index]
        if any(
            abs(anchor[axis] - expected_anchor[axis]) > 1e-6
            for axis in range(2)
        ):
            violations.append("table moved outside its assigned column")
        if abs(width - sum(BOM_COLUMN_WIDTHS.values())) > 1e-6:
            violations.append("table column widths changed after splitting")
        _telemetry.event(
            "drawing.bom_piece", piece=index + 1, split_count=count, split_range=(start, end),
            anchor_mm=(anchor[0] * 1000, anchor[1] * 1000),
            width_mm=width * 1000, height_mm=height * 1000,
            violations=tuple(violations),
        )
        findings.extend(violations)
    if findings:
        raise RuntimeError("paper-drive BOM split: " + "; ".join(findings))


def _split_bom(
    adapter: Any, table: Any, *, configuration: str | None = None,
    expected_snapshot: BomSnapshot | None = None,
) -> tuple[Any, Any]:
    """Keep one native logical parts list, displayed as two complete pieces."""
    table = _early_bound(table, "ITableAnnotation")
    header_count = int(table.GetHeaderCount())
    total_rows = int(table.RowCount)
    heights = tuple(float(table.GetRowHeight(row)) for row in range(total_rows))
    split_after = bom_split_row(heights, header_count)
    second = table.Split(2, split_after)  # swTableSplit_AfterRow
    if second is None:
        raise RuntimeError(f"paper-drive BOM split after row {split_after} failed")
    second = _early_bound(second, "ITableAnnotation")
    annotation = _early_bound(second.GetAnnotation(), "IAnnotation")
    if not annotation.SetPosition(*BOM_SECOND_ANCHOR, 0.0):
        raise RuntimeError("paper-drive BOM second piece refused its position")
    rebuild_drawing(adapter, label="paper-drive BOM split")
    pieces = (table, second)
    _assert_bom_pieces(
        pieces, header_count=header_count, total_rows=total_rows,
        configuration=configuration,
        expected_snapshot=expected_snapshot,
    )
    return pieces


def _isolate_instances(
    adapter: Any, view: Any, names: frozenset[str], *, label: str
) -> None:
    """Show exactly the named top-level instances in one drawing view.

    The shared ``isolate_drawing_view_components`` works per FAMILY, and the
    removable sprocket's family also holds the crank wheel and spare T18
    on the deck; this isolates per instance, as draw_drive_train_assembly
    does, and reads the visibility back.
    """
    _set_instance_visibility(adapter, view, names, shown=True, label=label)


def _hide_instances(
    adapter: Any, view: Any, names: frozenset[str], *, label: str
) -> None:
    """Hide exactly the named top-level instances; show every other one."""
    _set_instance_visibility(adapter, view, names, shown=False, label=label)


def _set_instance_visibility(
    adapter: Any, view: Any, names: frozenset[str], *, shown: bool, label: str
) -> None:
    """Named instances take ``shown``, the rest the opposite; all must exist."""
    view = _early_bound(view, "IView")
    root = view.RootDrawingComponent2(False)
    if root is None:
        raise RuntimeError(f"{label}: drawing view has no root component")
    root = _early_bound(root, "IDrawingComponent")
    found: set[str] = set()
    for raw in tuple(root.GetChildren() or ()):
        drawing_component = _early_bound(raw, "IDrawingComponent")
        raw_name = str(drawing_component.Name or "")
        name = raw_name.split("@", 1)[0].replace("\\", "/").rsplit("/", 1)[-1]
        named = name in names
        drawing_component.Visible = named == shown
        if named:
            found.add(name)
    rebuild_drawing(adapter, label=f"{label} visibility")
    missing = sorted(names - found)
    if missing:
        raise RuntimeError(f"{label}: instances not in the view: {missing!r}")


def _place_assembled_sheet(adapter: Any) -> Any:
    """Front, right and isometric of the whole drive; returns the isometric,
    centred so its balloon ring keeps inside ISO_RING_LIMITS."""
    _activate_sheet(adapter, SHEET_NAMES[0])
    for orientation, center in (
        ("*Front", FRONT_CENTER),
        ("*Right", RIGHT_CENTER),
        ("*Isometric", ISO_CENTER),
    ):
        view = place_view(
            adapter, str(SOURCE), orientation, *center, scale=ASSEMBLED_SCALE
        )
        # The isometric is the drawing's full-detail view.
        role = ViewRole.FULL_DETAIL if orientation == "*Isometric" else ViewRole.PLAIN
        apply_view_configuration(
            adapter, view, role=role, label=f"paper drive {orientation}"
        )
        if orientation != "*Isometric":
            # Lying flat on the deck, the spare T18 shows edge-on in the
            # front and right views as a bare unlabelled bar; the isometric
            # shows and balloons it (eye pass of PD run 11).
            _hide_instances(
                adapter, view, frozenset({SPARE_INSTANCE}),
                label=f"paper drive {orientation} spare",
            )
    label = "sheet 1 isometric"
    scale, outline = step_down_to_fit(
        _native_outline_at(adapter, view, ASSEMBLED_SCALE, label=label),
        ISO_SCALE_LADDER,
        ISO_RING_LIMITS,
        name=label,
    )
    shift = ring_fit_shift(outline, ISO_RING_LIMITS, name=label)
    _shift_view(adapter, view, shift, label=f"{label} ring fit")
    _place_sheet_note(
        adapter,
        SHEET_NAMES[0],
        ASSEMBLED_CAPTIONS[scale],
        ASSEMBLED_CAPTION_XY,
        label="assembled-views caption",
    )
    return view


def _view_outline(view: Any) -> Box:
    outline = tuple(float(value) for value in _early_bound(view, "IView").GetOutline())
    if len(outline) != 4 or outline[2] <= outline[0] or outline[3] <= outline[1]:
        raise RuntimeError(f"view has an invalid outline {outline!r}")
    return outline


def _shift_view(
    adapter: Any, view: Any, delta: tuple[float, float], *, label: str
) -> None:
    """Move a drawing view by a sheet-space delta and read the move back."""
    view = _early_bound(view, "IView")
    before = tuple(float(value) for value in view.Position)
    target = (before[0] + delta[0], before[1] + delta[1])
    if not view.SetViewPosition(double_array(list(target)), False):
        raise RuntimeError(f"{label}: SetViewPosition refused {target!r}")
    adapter.currentModel.EditRebuild3()
    after = tuple(float(value) for value in view.Position)
    if math.dist(after, target) > 1e-6:
        raise RuntimeError(f"{label}: view moved to {after!r}, expected {target!r}")


def _set_view_scale(
    adapter: Any, view: Any, scale: tuple[float, float], *, label: str
) -> None:
    """Re-scale a placed drawing view and read the scale back."""
    view = _early_bound(view, "IView")
    view.ScaleRatio = double_array([float(scale[0]), float(scale[1])])
    adapter.currentModel.EditRebuild3()
    ratio = tuple(float(value) for value in view.ScaleRatio)
    if len(ratio) != 2 or abs(ratio[0] / ratio[1] - scale[0] / scale[1]) > 1e-9:
        raise RuntimeError(f"{label}: view scale reads {ratio!r}, expected {scale!r}")


def _link_view_to_bom(view: Any, table: Any, *, label: str) -> None:
    """Number ``view``'s balloons from the BOM table inserted on another view."""
    bom = _early_bound(table, "IBomTableAnnotation")
    feature = _early_bound(bom.BomFeature, "IBomFeature")
    name = str(feature.Name or "")
    if not name:
        raise RuntimeError("paper-drive BOM feature has no name")
    view = _early_bound(view, "IView")
    if not view.SetKeepLinkedToBOM(True, name):
        raise RuntimeError(f"{label}: SetKeepLinkedToBOM({name!r}) returned false")
    if (
        not bool(view.GetKeepLinkedToBOM())
        or str(view.GetKeepLinkedToBOMName() or "") != name
    ):
        raise RuntimeError(f"{label}: view is not linked to BOM {name!r}")


def _assert_bom_balloon_configuration(view: Any, *, label: str) -> None:
    """Read actual post-operation membership; never coerce a view to fit the BOM."""
    actual = _early_bound(view, "IView").ReferencedConfiguration
    if actual != BOM_CONFIGURATION:
        raise RuntimeError(
            f"{label}: balloon view configuration {actual!r}, expected {BOM_CONFIGURATION!r}"
        )


def _assert_bom_balloon_items(
    landings: Sequence[BalloonLanding], items: dict[str, str],
) -> None:
    """Re-read every native balloon after the final rebuild, including repeated stems."""
    for landing in landings:
        actual = str(_early_bound(landing.note, "INote").GetBomBalloonText(True) or "").strip()
        expected = items[landing.stem]
        if actual != expected:
            raise RuntimeError(
                f"{landing.label}: settled {landing.stem} ({landing.instance}) "
                f"resolved item {actual}, expected {expected}"
            )


def _place_bom_sheet(
    adapter: Any, counts: Counter[str]
) -> tuple[list[Any], Any, dict[str, str], tuple[Any, Any], BomSnapshot]:
    """BOM of the whole drive; the transgear isometric balloons every
    transgear family it can reach. Returns landings, the logical table, its
    (stem: item) numbers, pieces and validated snapshot."""
    _activate_sheet(adapter, SHEET_NAMES[7])
    reference = place_view(
        adapter, str(SOURCE), "*Isometric", *BOM_REFERENCE_CENTER,
        scale=BOM_REFERENCE_SCALE,
    )
    set_high_quality_shaded_with_edges(adapter, reference, label="BOM reference")
    apply_view_configuration(adapter, reference, label="BOM reference")
    outline = _view_outline(reference)
    if not (
        BOM_REFERENCE_LIMITS[0] <= outline[0] < outline[2] <= BOM_REFERENCE_LIMITS[2]
        and BOM_REFERENCE_LIMITS[1] <= outline[1] < outline[3] <= BOM_REFERENCE_LIMITS[3]
    ):
        raise RuntimeError(f"paper-drive BOM reference leaves its field: {outline!r}")
    _place_sheet_note(
        adapter, SHEET_NAMES[7], BOM_SHEET_CAPTION, BOM_REFERENCE_CAPTION_XY,
        label="BOM reference caption",
    )
    # Insert the complete model's BOM on its own sheet; view-only isolation
    # on sheet 2 cannot alter this reference or the logical parts list.
    table = insert_bom_table(
        adapter,
        reference,
        anchor_xy=BOM_ANCHOR,
        expected_components=tuple(BOM_PART_NUMBERS),
        descriptions=BOM_DESCRIPTIONS,
        component_identities=BOM_COMPONENT_IDENTITIES,
        part_number_property="Number",
        configuration_grouping="same-name",
        configuration=BOM_CONFIGURATION,
        label="paper-drive",
    )
    bom_configuration = BOM_CONFIGURATION
    items = dict(
        _validate_bom(
            adapter, table, counts, configuration=bom_configuration
        )
    )
    _activate_sheet(adapter, SHEET_NAMES[1])
    label = "transgear isometric"
    view = place_view(
        adapter, str(SOURCE), "*Isometric", *TRANSGEAR_VIEW_CENTER,
        scale=TRANSGEAR_VIEW_SCALE,
    )
    set_high_quality_shaded_with_edges(adapter, view, label=label)
    apply_view_configuration(adapter, view, label=label)
    _link_view_to_bom(view, table, label=label)
    _isolate_instances(adapter, view, TRANSGEAR_INSTANCES, label=label)
    if dict(
        _validate_bom(adapter, table, counts, configuration=bom_configuration)
    ) != items:
        raise RuntimeError(
            "paper-drive BOM items moved when the transgear view was isolated"
        )
    bom_snapshot = validate_bom_number_property(
        table,
        configuration=bom_configuration,
        label="paper-drive pre-split BOM",
        expected_rows=len(BOM_PART_NUMBERS) + 1,
        occurrence_quantities=True,
    )
    _activate_sheet(adapter, SHEET_NAMES[7])
    pieces = _split_bom(
        adapter, table, configuration=bom_configuration,
        expected_snapshot=bom_snapshot,
    )
    _activate_sheet(adapter, SHEET_NAMES[1])
    # The ring fits before any balloon exists: the isometric is centred in
    # the field's height. Requested creation policy is not proof of the
    # actual post-operation configuration.
    _shift_view(
        adapter, view, transgear_view_shift(_view_outline(view)), label=f"{label} ring fit"
    )
    iso_items, _exploded_items = transgear_balloon_items(items)
    iso_label = "paper-drive transgear BOM coverage"
    _assert_bom_balloon_configuration(view, label=iso_label)
    landings = add_component_bom_balloons(
        adapter,
        view,
        items=iso_items,
        anchors=TRANSGEAR_BALLOON_ANCHORS,
        label=iso_label,
        margin=BALLOON_MARGIN,
    )
    # Farm run 20261015T082822796Z: the isometric's angular ring order still
    # crossed items 14 and 16, whose attachments sit at different depths
    # inside the ring; swapping their ring slots uncrosses them.
    _uncross_ring(adapter, landings, label=iso_label)
    _place_sheet_note(
        adapter,
        SHEET_NAMES[1],
        TRANSGEAR_CAPTION,
        TRANSGEAR_CAPTION_XY,
        label="transgear caption",
    )
    return landings, table, items, pieces, bom_snapshot


def _pivot_sheet_points(
    adapter: Any,
    view: Any,
    points_mm: Sequence[tuple[float, float, float]],
    *,
    label: str,
) -> list[tuple[float, float]]:
    """Sheet points of ``points_mm``, in the pivot screw's part frame (mm)."""
    leaf = _shown_instances(
        _view_component_leaves(adapter, view, label=label),
        "pd-vn-transgear-pivot-screw",
        BalloonAnchor(instance=PIVOT_SCREW_INSTANCE),
        label=label,
    )[0]
    return model_points_in_view(
        adapter,
        view,
        _anchor_model_points(
            adapter,
            leaf,
            tuple(tuple(value / 1000.0 for value in point) for point in points_mm),
            _view_explode_offsets(adapter, view, label=label),
            stem="pd-vn-transgear-pivot-screw",
            label=label,
        ),
        label=label,
    )


def _centre_pivot_view(
    adapter: Any, view: Any, target: tuple[float, float], *, label: str
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Shift ``view`` until the pivot stack's midpoint sits on ``target``;
    return the sheet points of the screw's head top and the bar's front
    face on its axis, read after the shift."""
    points = (
        PIVOT_VIEW_CENTRE_MM,
        (0.0, pivot_screw.HEAD_H, 0.0),
        (0.0, PIVOT_FRONT_FACE_Y, 0.0),
    )
    centre = _pivot_sheet_points(adapter, view, points, label=label)[0]
    _shift_view(
        adapter,
        view,
        (target[0] - centre[0], target[1] - centre[1]),
        label=f"{label} centre",
    )
    centre, head, front = _pivot_sheet_points(adapter, view, points, label=label)
    if math.dist(centre, target) > 1e-4:
        raise RuntimeError(f"{label}: centre sits at {centre!r}, not {target!r}")
    return head, front


def _check_axis_down_the_sheet(
    head: tuple[float, float], front: tuple[float, float], *, label: str
) -> None:
    if abs(head[0] - front[0]) > 1e-5 or head[1] <= front[1]:
        raise RuntimeError(
            f"{label}: the screw's axis runs {head!r} -> {front!r}, not down the sheet"
        )


def _pivot_section_cut_points(
    adapter: Any,
    section: Any,
    tips: Sequence[tuple[str, float, float]],
    *,
    label: str,
) -> list[tuple[float, float]]:
    """Sheet points of ``(side, y, r)`` tips on the section's cut plane in
    the screw's frame (mm): ``r`` off the axis, "right" or "left" of it."""
    origin, along_x, along_z = _pivot_sheet_points(
        adapter,
        section,
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
        label=label,
    )
    # The screw may sit at any angle about its axis. A radial direction
    # (a, 0, b) moves the sheet a*hx + b*hz across; the one along (hx, hz)
    # moves it furthest, which is the radial line in the cut plane, at full
    # view scale, and positive is right of the axis.
    hx, hz = along_x[0] - origin[0], along_z[0] - origin[0]
    reach = math.hypot(hx, hz)
    full = PIVOT_SECTION_SCALE[0] / PIVOT_SECTION_SCALE[1] / 1000.0
    if abs(reach - full) > 0.01 * full:
        raise RuntimeError(
            f"{label}: 1 mm across the screw reads {reach:.6f} m on the sheet, "
            f"not {full:.6f}: the cut plane does not hold the screw's axis"
        )
    across = (hx / reach, hz / reach)
    points = [
        (
            across[0] * r * (1.0 if side == "right" else -1.0),
            y,
            across[1] * r * (1.0 if side == "right" else -1.0),
        )
        for side, y, r in tips
    ]
    return _pivot_sheet_points(adapter, section, points, label=label)


def _note_pivot_stake(
    adapter: Any,
    section: Any,
    head: tuple[float, float],
    front: tuple[float, float],
    *,
    label: str,
) -> None:
    """Point the stake note at the tap's front mouth in SECTION A-A
    (PIVOT_STAKE_TIP), the note outside the circle at the front face's end,
    right of the tip so its leader leaves the text's left end."""
    (tip,) = _pivot_section_cut_points(
        adapter, section, (("right", *PIVOT_STAKE_TIP),), label=label
    )
    if tip[0] <= PIVOT_SECTION_CENTER[0]:
        raise RuntimeError(f"{label}: the stake tip {tip!r} is not right of the axis")
    text_xy = pivot_stake_note_xy(tip[0], 1.0 if front[1] > head[1] else -1.0)
    note = _early_bound(
        add_leader_note(
            adapter,
            PIVOT_STAKE_NOTE,
            text_xy=text_xy,
            attach_xy=tip,
            label=label,
            view=section,
        ),
        "INote",
    )
    # The leader's first point is its end on the note: it must leave the
    # text's left end, not its far side (farm r6 review).
    points = list(
        _early_bound(note.GetAnnotation(), "IAnnotation").GetLeaderPointsAtIndex(0)
        or ()
    )
    if len(points) < 6 or float(points[0]) > text_xy[0] + 0.001:
        raise RuntimeError(
            f"{label}: the leader leaves the note at {points[:2]!r}, "
            f"not its left end at x {text_xy[0]:.4f}"
        )


def _balloon_pivot_section(
    adapter: Any, section: Any, items: dict[str, str], *, label: str
) -> None:
    """Point one item-number balloon into each part's cut face
    (PIVOT_BALLOON_TIPS), in a column each side of the section's circle."""
    tips = _pivot_section_cut_points(
        adapter,
        section,
        [(side, y, r) for _stem, side, y, r in PIVOT_BALLOON_TIPS],
        label=label,
    )
    cx = PIVOT_SECTION_CENTER[0]
    placed: list[tuple[str, Any, tuple[float, float]]] = []
    for side, x in (
        ("left", cx - PIVOT_SECTION_RADIUS - PIVOT_BALLOON_GAP),
        ("right", cx + PIVOT_SECTION_RADIUS + PIVOT_BALLOON_GAP),
    ):
        column = sorted(
            (
                (tip, stem)
                for (stem, tip_side, _y, _r), tip in zip(PIVOT_BALLOON_TIPS, tips)
                if tip_side == side
            ),
            key=lambda pair: -pair[0][1],
        )
        for tip, _stem in column:
            if (tip[0] < cx) != (side == "left"):
                raise RuntimeError(f"{label}: a {side} tip {tip!r} is across the axis")
        heights = spread_balloon_column(
            [tip[1] for tip, _stem in column], PIVOT_BALLOON_PITCH
        )
        for (tip, stem), y in zip(column, heights):
            note = _early_bound(
                add_leader_note(
                    adapter,
                    items[stem],
                    text_xy=(x, y),
                    attach_xy=tip,
                    label=f"{label} {stem}",
                    view=section,
                ),
                "INote",
            )
            if not note.SetBalloon(_SW_BALLOON_CIRCULAR, _SW_BALLOON_FIT_2_CHARS):
                raise RuntimeError(f"{label}: {stem}'s balloon style was refused")
            placed.append((stem, note, tip))
    rebuild_drawing(adapter, label=f"{label} balloons")
    # Read back after the rebuild: still a balloon, its leader still ending
    # on the cut face it names.
    for stem, note, tip in placed:
        if not note.HasBalloon():
            raise RuntimeError(f"{label}: {stem}'s note reads no balloon")
        points = list(
            _early_bound(note.GetAnnotation(), "IAnnotation").GetLeaderPointsAtIndex(0)
            or ()
        )
        if len(points) < 6 or math.dist((points[-3], points[-2]), tip) > 0.001:
            raise RuntimeError(
                f"{label}: {stem}'s balloon leader ends at {points[-3:-1]!r}, "
                f"not on its cut face at {tip!r}"
            )


def _place_pivot_view(adapter: Any, items: dict[str, str]) -> None:
    """Sheet 2's hanger pivot: a 1:1 locator of the step-13 stack from above,
    cut along the screw's axis into SECTION A-A at 2:1, both cropped to
    circles on the stack, the section ballooned part by part."""
    label = "hanger pivot locator"
    _activate_sheet(adapter, SHEET_NAMES[1])
    locator = _early_bound(
        place_view(
            adapter,
            str(SOURCE),
            PIVOT_VIEW_ORIENTATION,
            *PIVOT_LOCATOR_CENTER,
            scale=PIVOT_LOCATOR_SCALE,
        ),
        "IView",
    )
    apply_view_configuration(adapter, locator, label=label)
    _isolate_instances(adapter, locator, PIVOT_VIEW_INSTANCES, label=label)
    head, front = _centre_pivot_view(
        adapter, locator, PIVOT_LOCATOR_CENTER, label=label
    )
    # The cutting line is drawn vertically through the circle's centre: the
    # *Top locator must lay the screw's axis down the sheet, head up.
    _check_axis_down_the_sheet(head, front, label=label)
    _crop_to_circle(
        adapter, locator, PIVOT_LOCATOR_CENTER, PIVOT_LOCATOR_RADIUS, label=label
    )
    set_hidden_lines_removed(adapter, locator)
    section_label = "hanger pivot section"
    section = create_section_view(
        adapter,
        locator,
        line_start=(PIVOT_LOCATOR_CENTER[0], PIVOT_LOCATOR_CENTER[1] + PIVOT_CUT_HALF),
        line_end=(PIVOT_LOCATOR_CENTER[0], PIVOT_LOCATOR_CENTER[1] - PIVOT_CUT_HALF),
        view_xy=PIVOT_SECTION_CENTER,
        section_label=PIVOT_SECTION_LABEL,
        scale=PIVOT_SECTION_SCALE,
        label=section_label,
    )
    _isolate_instances(adapter, section, PIVOT_VIEW_INSTANCES, label=section_label)
    head, front = _centre_pivot_view(
        adapter, section, PIVOT_SECTION_CENTER, label=section_label
    )
    # The balloon columns stand left and right of a vertical axis (farm run
    # 20261015T101105899Z read the cut bar 56 mm wide, 19 mm tall at 2:1);
    # which end is up does not matter to them.
    if abs(head[0] - front[0]) > 1e-5:
        raise RuntimeError(
            f"{section_label}: the screw's axis runs {head!r} -> {front!r}, "
            "not vertically"
        )
    _crop_to_circle(
        adapter,
        section,
        PIVOT_SECTION_CENTER,
        PIVOT_SECTION_RADIUS,
        label=section_label,
    )
    set_hidden_lines_removed(adapter, section)
    position_section_caption(
        adapter, section, PIVOT_SECTION_CAPTION_XY, label=section_label
    )
    _balloon_pivot_section(
        adapter, section, items, label="paper-drive hanger pivot balloons"
    )
    _note_pivot_stake(
        adapter, section, head, front, label="paper-drive hanger pivot stake note"
    )
    _place_sheet_note(
        adapter,
        SHEET_NAMES[1],
        PIVOT_CAPTION,
        PIVOT_CAPTION_XY,
        label="hanger pivot caption",
    )


def _crop_to_circle(
    adapter: Any, view: Any, centre: tuple[float, float], radius: float, *, label: str
) -> None:
    """Crop ``view`` to a sheet circle: sketch it in the active view's own
    sketch and Crop2 while it is still selected (draw_mg_magnifier_assembly's
    detail crop)."""
    view = _early_bound(view, "IView")
    if not _early_bound(adapter.currentModel, "IDrawingDoc").ActivateView(
        view_name(adapter, view)
    ):
        raise RuntimeError(f"{label}: failed to activate the view to crop")
    adapter.currentModel.ClearSelection2(True)
    sketch = _early_bound(view.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (centre, (centre[0] + radius, centre[1])):
        point = _early_bound(
            utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(adapter.currentModel.SketchManager, "ISketchManager")
    previous = bool(manager.AddToDB)
    manager.AddToDB = False
    try:
        circle = manager.CreateCircle(*points[0], *points[1])
    finally:
        manager.AddToDB = previous
    if circle is None:
        raise RuntimeError(f"{label}: failed to sketch the crop circle")
    status = int(view.Crop2(False, False, 1))
    adapter.currentModel.ClearSelection2(True)
    adapter.currentModel.EditRebuild3()
    view.UpdateViewDisplayGeometry()
    cropped = bool(view.IsCropped())
    if status != CROP_NO_ERROR or not cropped:
        raise RuntimeError(
            f"{label}: not cropped: Crop2 status {status}, IsCropped {cropped}"
        )


def _balloon_assembled_sheet(
    adapter: Any, iso: Any, table: Any, items: dict[str, str]
) -> list[Any]:
    """The chain and the spare T18 on sheet 1's isometric."""
    _activate_sheet(adapter, SHEET_NAMES[0])
    _link_view_to_bom(iso, table, label="sheet 1 isometric")
    _assert_bom_balloon_configuration(iso, label="paper-drive sheet 1 BOM coverage")
    return add_component_bom_balloons(
        adapter,
        iso,
        items=assembled_balloon_items(items),
        anchors=ASSEMBLED_BALLOON_ANCHORS,
        label="paper-drive sheet 1 BOM coverage",
        margin=BALLOON_MARGIN,
    )


def _place_transgear_exploded_sheet(
    adapter: Any, table: Any, items: dict[str, str]
) -> list[Any]:
    """The builder's PAPER_DRIVE_EXPLODED in two isometric views, the hanger
    and knob stack in one and the disc cluster in the other, each family
    ballooned once. Both views fit their fields before any balloon exists."""
    sheet = SHEET_NAMES[2]
    _activate_sheet(adapter, sheet)
    views = []
    for group in TRANSGEAR_EXPLODED_GROUPS:
        label = group.label
        view = place_view(
            adapter,
            str(SOURCE),
            TRANSGEAR_EXPLODED_ORIENTATION,
            *group.center,
            scale=TRANSGEAR_EXPLODED_SCALE,
        )
        set_high_quality_shaded_with_edges(adapter, view, label=label)
        configuration = apply_view_configuration(
            adapter, view, role=ViewRole.FULL_DETAIL, label=label
        )
        set_view_exploded_state(
            adapter, view, True, configuration=configuration, label=label
        )
        _isolate_instances(adapter, view, exploded_group_instances(group), label=label)
        _scale, outline = step_down_to_fit(
            _native_outline_at(adapter, view, TRANSGEAR_EXPLODED_SCALE, label=label),
            (TRANSGEAR_EXPLODED_SCALE,),
            group.ring_limits,
            name=label,
        )
        shift = ring_fit_shift(outline, group.ring_limits, name=label)
        _shift_view(adapter, view, shift, label=f"{label} ring fit")
        _link_view_to_bom(view, table, label=label)
        views.append((group, view))
    _iso_items, exploded_items = transgear_balloon_items(items)
    # Both views reference the same configuration's explode, whose offsets
    # cover every moved instance: read them once.
    offsets = _view_explode_offsets(
        adapter, views[0][1], label="paper-drive transgear exploded offsets"
    )
    landings: list[Any] = []
    for group, view in views:
        balloons_label = f"paper-drive transgear {group.label} BOM coverage"
        _assert_bom_balloon_configuration(view, label=balloons_label)
        group_landings = add_component_bom_balloons(
            adapter,
            view,
            items=tuple(pair for pair in exploded_items if pair[0] in group.stems),
            anchors=TRANSGEAR_BALLOON_ANCHORS,
            label=balloons_label,
            margin=BALLOON_MARGIN,
            explode_offsets=offsets,
        )
        _uncross_ring(adapter, group_landings, label=balloons_label)
        landings += group_landings
    _place_sheet_note(
        adapter,
        sheet,
        TRANSGEAR_EXPLODED_CAPTION,
        TRANSGEAR_EXPLODED_CAPTION_XY,
        label="transgear exploded caption",
    )
    return landings


def _place_exploded_sheet(
    adapter: Any, table: Any, items: dict[str, str], notes: StepNotes,
) -> list[Any]:
    """The builder's PAPER_DRIVE_EXPLODED, only the platen-and-support
    families shown, each ballooned once; their steps left of it."""
    _activate_sheet(adapter, SHEET_NAMES[3])
    label = "platen and support exploded"
    view = place_view(
        adapter, str(SOURCE), "*Isometric", *EXPLODED_CENTER, scale=EXPLODED_SCALE
    )
    set_high_quality_shaded_with_edges(adapter, view, label=label)
    configuration = apply_view_configuration(
        adapter, view, role=EXPLODED_VIEW_ROLE, label=label
    )
    set_view_exploded_state(
        adapter, view, True, configuration=configuration, label=label
    )
    isolate_drawing_view_components(
        adapter, view, visible_stems=explode.SHOWN_STEMS, label=label
    )
    scale, outline = step_down_to_fit(
        _native_outline_at(adapter, view, EXPLODED_SCALE, label=label),
        EXPLODED_SCALE_LADDER,
        EXPLODED_RING_LIMITS,
        name=label,
    )
    shift = ring_fit_shift(outline, EXPLODED_RING_LIMITS, name=label)
    _shift_view(adapter, view, shift, label=f"{label} ring fit")
    _link_view_to_bom(view, table, label=label)
    _assert_bom_balloon_configuration(view, label="paper-drive platen BOM coverage")
    landings = add_component_bom_balloons(
        adapter,
        view,
        items=platen_balloon_items(items),
        anchors=PLATEN_BALLOON_ANCHORS,
        label="paper-drive platen BOM coverage",
        margin=BALLOON_MARGIN,
    )
    _place_sheet_note(
        adapter, SHEET_NAMES[3], notes.platen_steps, PLATEN_NOTE_XY, label="platen steps"
    )
    _place_sheet_note(
        adapter,
        SHEET_NAMES[3],
        EXPLODED_CAPTIONS[scale],
        notes.exploded_caption_xy,
        label="exploded-view caption",
    )
    return landings


def _place_knob_setting_view(adapter: Any) -> None:
    """Sheet 5's VIEW K: the arm and plate from the machine front at
    1:1, cropped on S-K's midpoint, carrying the assembly's set band S to N
    and its two K setting dimensions from S (pd_paper_drive_knob_setting_spec)
    that the arm-plate-located step cites."""
    label = "knob setting view"
    _activate_sheet(adapter, SHEET_NAMES[4])
    view = _early_bound(
        place_view(
            adapter, str(SOURCE), "*Front", *KNOB_SETTING_CENTER, scale=KNOB_SETTING_SCALE
        ),
        "IView",
    )
    apply_view_configuration(adapter, view, label=label)
    _isolate_instances(adapter, view, KNOB_SETTING_INSTANCES, label=label)
    model = tuple(
        (x / 1000.0, y / 1000.0, 0.0)
        for x, y in (
            (
                (knob_setting.S_XY[0] + knob_setting.K_XY[0]) / 2.0,
                (knob_setting.S_XY[1] + knob_setting.K_XY[1]) / 2.0,
            ),
            knob_setting.S_XY,
            knob_setting.Q_XY,
            knob_setting.K_XY,
            KNOB_SETTING_TAP_XY,
            knob_setting.N_XY,
        )
    )
    names = (
        "S-K midpoint", "pin S", "corner Q", "knob bore K", "plate-screw tap T",
        "nominal centre N",
    )
    centre = model_points_in_view(adapter, view, model[:1], label=label, names=names[:1])[0]
    _shift_view(
        adapter,
        view,
        (KNOB_SETTING_CENTER[0] - centre[0], KNOB_SETTING_CENTER[1] - centre[1]),
        label=f"{label} centre",
    )
    centre, s, q, k, t, n = model_points_in_view(
        adapter, view, model, label=label, names=names
    )
    if math.dist(centre, KNOB_SETTING_CENTER) > 1e-4:
        raise RuntimeError(f"{label}: S-K midpoint sits at {centre!r}")
    _crop_to_circle(adapter, view, KNOB_SETTING_CENTER, KNOB_SETTING_RADIUS, label=label)
    set_hidden_lines_removed(adapter, view)
    _show_base_view_sketches(adapter, view, (knob_setting.FEATURE,), label=label)
    keep = knob_setting_keep(s, q, k, n)
    annotations = curate_view_dimensions(
        adapter,
        view,
        keep=keep,
        view_label=label,
        dimensions_by_feature=knob_setting.DRAWING_DIMENSIONS,
    )
    assert_imported_precision(
        adapter, annotations, knob_setting.DRAWING_PRECISION[knob_setting.FEATURE]
    )
    imported = sorted(
        dimension_name(adapter, _early_bound(annotation, "IAnnotation"))
        for annotation in annotations
    )
    if imported != sorted(keep):
        raise RuntimeError(f"{label} imported {imported}, not {sorted(keep)}")
    # Arrows outside the extension lines: each value spans most of its short
    # leg, so arrows inside struck its parentheses (run
    # 20261028T030354738Z-98518b6344ca4a139d0dac48e7162995, r1 and r3).
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.ArrowSide = KNOB_SETTING_ARROWS_OUTSIDE
        if int(display.ArrowSide) != KNOB_SETTING_ARROWS_OUTSIDE:
            raise RuntimeError(
                f"{label}: {dimension_name(adapter, annotation)} kept its arrows inside"
            )
    rebuild_drawing(adapter, label=f"{label} arrows")
    for letter, (text_xy, tip) in knob_setting_letters(s, q, k, t).items():
        add_leader_note(
            adapter,
            letter,
            text_xy=text_xy,
            attach_xy=tip,
            label=f"{label} letter {letter}",
            view=view,
        )
    rebuild_drawing(adapter, label=f"{label} letters")
    _place_sheet_note(
        adapter,
        SHEET_NAMES[4],
        KNOB_SETTING_CAPTION,
        KNOB_SETTING_CAPTION_XY,
        label=f"{label} caption",
    )


def _place_cluster_float_view(adapter: Any) -> None:
    """Sheet 6's VIEW E: the pin's front end from the side at 5:1, cropped on
    the ring gap, carrying the assembly's shimmed ring-gap window
    (pd_paper_drive_cluster_float_spec) that the shimming step cites."""
    label = "cluster float view"
    _activate_sheet(adapter, SHEET_NAMES[5])
    view = _early_bound(
        place_view(
            adapter,
            str(SOURCE),
            CLUSTER_FLOAT_ORIENTATION,
            *CLUSTER_FLOAT_CENTER,
            scale=CLUSTER_FLOAT_SCALE,
        ),
        "IView",
    )
    apply_view_configuration(adapter, view, label=label)
    _isolate_instances(adapter, view, CLUSTER_FLOAT_INSTANCES, label=label)
    model = tuple(
        tuple(value / 1000.0 for value in point)
        for point in (CLUSTER_FLOAT_MODEL_CENTRE, cluster_float.TEXT_POINT)
    )
    names = ("ring gap centre", "ring gap text")
    centre = model_points_in_view(adapter, view, model[:1], label=label, names=names[:1])[0]
    _shift_view(
        adapter,
        view,
        (CLUSTER_FLOAT_CENTER[0] - centre[0], CLUSTER_FLOAT_CENTER[1] - centre[1]),
        label=f"{label} centre",
    )
    centre, text = model_points_in_view(adapter, view, model, label=label, names=names)
    if math.dist(centre, CLUSTER_FLOAT_CENTER) > 1e-4:
        raise RuntimeError(f"{label}: the ring gap sits at {centre!r}")
    _crop_to_circle(
        adapter, view, CLUSTER_FLOAT_CENTER, CLUSTER_FLOAT_RADIUS, label=label
    )
    set_hidden_lines_removed(adapter, view)
    _show_base_view_sketches(adapter, view, (cluster_float.FEATURE,), label=label)
    annotations = curate_view_dimensions(
        adapter,
        view,
        keep={cluster_float.DIMENSION: text},
        view_label=label,
        dimensions_by_feature=cluster_float.DRAWING_DIMENSIONS,
    )
    assert_imported_precision(
        adapter, annotations, cluster_float.DRAWING_PRECISION[cluster_float.FEATURE]
    )
    imported = [
        dimension_name(adapter, _early_bound(annotation, "IAnnotation"))
        for annotation in annotations
    ]
    if imported != [cluster_float.DIMENSION]:
        raise RuntimeError(
            f"{label} imported {imported}, not {cluster_float.DIMENSION}"
        )
    # The gap is about a millimetre on the sheet: arrows outside.
    display = _early_bound(
        _early_bound(annotations[0], "IAnnotation").GetSpecificAnnotation(),
        "IDisplayDimension",
    )
    display.ArrowSide = CLUSTER_FLOAT_ARROWS_OUTSIDE
    if int(display.ArrowSide) != CLUSTER_FLOAT_ARROWS_OUTSIDE:
        raise RuntimeError(f"{label}: the ring gap kept its arrows inside")
    rebuild_drawing(adapter, label=f"{label} arrows")
    _place_sheet_note(
        adapter,
        SHEET_NAMES[5],
        CLUSTER_FLOAT_CAPTION,
        CLUSTER_FLOAT_CAPTION_XY,
        label=f"{label} caption",
    )


def _place_fitup_sheets(adapter: Any, step_notes: StepNotes) -> None:
    for sheet_name, notes in (
        (SHEET_NAMES[4], step_notes.fitup_notes),
        (SHEET_NAMES[5], step_notes.fitup_continued_notes),
        (SHEET_NAMES[6], step_notes.chain_notes),
    ):
        _activate_sheet(adapter, sheet_name)
        view = place_view(
            adapter, str(SOURCE), "*Isometric", *FITUP_REFERENCE_CENTER, scale=FITUP_SCALE
        )
        apply_view_configuration(
            adapter, view, label=f"{sheet_name} reference isometric"
        )
        _place_sheet_note(
            adapter,
            sheet_name,
            FITUP_REFERENCE_CAPTION,
            (FITUP_REFERENCE_CENTER[0] - 0.040, FITUP_NOTE_LIMITS[0][1] - 0.002),
            label=f"{sheet_name} reference caption",
        )
        for index, (text, xy) in enumerate(zip(notes, FITUP_NOTE_XY, strict=True)):
            _place_sheet_note(
                adapter, sheet_name, text, xy, label=f"{sheet_name} note {index + 1}"
            )


@_telemetry.traced("drawing.paper_drive_assembly")
async def build(adapter: Any) -> dict[str, str]:
    notes = require_step_notes()
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source assembly is missing: {SOURCE}")

    check("open assembly drawing source", await adapter.open_model(str(SOURCE)))
    properties = read_required_properties(
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
            "Revision",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
    )
    if properties["Number"] != steps.DRAWING_NUMBER:
        raise RuntimeError(
            f"paper-drive source is {properties['Number']!r}, steps name "
            f"{steps.DRAWING_NUMBER!r}"
        )
    counts = _source_family_counts(adapter.currentModel)
    _validate_persisted_explode(adapter.currentModel)
    _create_sheets(adapter)
    iso = _place_assembled_sheet(adapter)
    landings, table, items, pieces, bom_snapshot = _place_bom_sheet(adapter, counts)
    _place_pivot_view(adapter, items)
    landings += _balloon_assembled_sheet(adapter, iso, table, items)
    landings += _place_transgear_exploded_sheet(adapter, table, items)
    landings += _place_exploded_sheet(adapter, table, items, notes)
    _place_fitup_sheets(adapter, notes)
    _place_knob_setting_view(adapter)
    _place_cluster_float_view(adapter)
    assert_full_detail_view(adapter, label="paper-drive assembly")

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        layout=SPEC.layout,
        pdf_title="Paper-Drive Assembly Drawing",
        scale=ASSEMBLED_SCALE,
        expected_sheet_names=SHEET_NAMES,
        sheet_layouts=SHEET_LAYOUTS,
        sheet_scales=SHEET_SCALES,
        settled_checks=(
            lambda: assert_balloon_landings(adapter, landings),
            lambda: _assert_bom_balloon_items(landings, items),
            lambda: _assert_bom_pieces(
                pieces, header_count=int(table.GetHeaderCount()),
                total_rows=len(BOM_PART_NUMBERS) + 1,
                configuration=BOM_CONFIGURATION,
                expected_snapshot=bom_snapshot,
            ),
        ),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[ARTIFACT_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
