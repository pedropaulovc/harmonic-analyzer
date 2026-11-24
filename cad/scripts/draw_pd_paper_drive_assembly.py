r"""Create the eight-sheet paper-drive assembly drawing (MHA-PD-00).

Sheet 1 keeps the Front/Right/Isometric views of the whole paper drive and
balloons the chain and the spare sprocket on the isometric. Sheet 2 carries
a ballooned isometric of the transgear (the hanger, the latch, the disc cluster
and the knob stack) and the hanger pivot's section. Sheet 3 draws the hanger,
the disc cluster and the knob stack apart along their axes on
PAPER_DRIVE_EXPLODED, seen from above, and balloons every part it shows.
Sheet 4 balloons the bar, its clamps and the platen group on
PAPER_DRIVE_EXPLODED and prints their steps. Sheet 5 prints the transgear's
assembly steps; sheets 6 on continue them, and sheet 7 carries DETAIL K, the
knob bore's setting from the arm's pin bore as the assembly's own model
dimensions, beside the step that sets it; sheet 12 prints the chain fit-up
(CONTRACT-paper-drive.md §13.2). Sheet 15 carries the complete native BOM,
split horizontally into two pieces at measured row heights, and an assembly
reference. The BOM identifies the current inch
reducer, finite stock-form integral pinions and purchased feed rack; sheet 1 gives the
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
from fractions import Fraction
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
from _component_order import by_name
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
    set_drawing_view_instance_visibility,
)
from _assembly_contract import assembly_contract
from _drawing_common import (
    _SW_SHADED_EDGES,
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_high_quality_shaded_with_edges,
)
from _layout_geometry import LeaderSegment, find_leader_leader_crossings
from _drawing_leader_notes import add_leader_note
from _drawing_projection import model_point_in_view, model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DRAWING_TEMPLATES, DrawingLayout
from _drawing_detail_crop import native_circle_geometry
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision
from _drawing_hidden_sketches import _show_base_view_sketches
from _drawing_sections import create_section_view
from _drawing_sheets import create_blank_drawing_sheets
from _general_table import insert_general_table, table_column_widths
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
from _hole_spec import NUMBER_DRILL_MM, TAP_DRILL_MM, blind_cut_dia_mm
from _printed_tolerance import printed_deviations
from _recording_geometry import RECORDING_PAPER_HEIGHT_MM, RECORDING_PAPER_WIDTH_MM
import paper_drive_mesh_check as mesh_check
import paper_drive_arm_registration as registration
import pd_latch_hook_geometry as hook_geometry
import paper_drive_rack_setup as rack_setup
import pd_paper_drive_assembly_steps as steps
import pd_paper_drive_knob_setting_spec as knob_setting
import pd_paper_drive_cluster_float_spec as cluster_float
import pd_paper_drive_setting_details_spec as setting_details
import pd_paper_drive_explode_spec as explode
import pd_platen_guide_spec as platen_guide
import pd_platen_bottom_guide_spec as bottom_guide
import pd_feed_rack_spec as feed_rack
import pd_feed_rack_screw_spec as rack_screw
import pd_platen_spec as platen
import pd_guide_lock_spec as guide_lock
import pd_support_bar_spec as support_bar
import pd_transgear_arm_geometry as arm_geometry
import pd_transgear_arm_plate_geometry as plate_geometry
import pd_transgear_disc_hub_geometry as hub_geometry
import pd_transgear_disc_hub_spec as hub
import pd_transgear_drive_collar_spec as collar
import pd_transgear_knob_bush_geometry as knob_bush
import pd_transgear_knob_shaft_spec as knob_shaft
import pd_transgear_removable_spec as sprocket
import _sprocket_seat_geometry as seat_geometry
import transgear_cluster_fit as cluster_fit
import transgear_hanger_joints as joints
import pd_vn_transgear_arm_plate_screw_spec as plate_screw
import pd_transgear_disc_screw_spec as disc_screw
import pd_vn_transgear_knob_cup_screw_spec as cup_screw
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
    "ASSEMBLY AND FIT-UP (CONT. 2)",
    "ASSEMBLY AND FIT-UP (CONT. 3)",
    "ASSEMBLY AND FIT-UP (CONT. 4)",
    "ASSEMBLY AND FIT-UP (CONT. 5)",
    # #2425: the bush press and the knob cup's facing, bond and screw steps
    # take one more fit-up sheet.
    "ASSEMBLY AND FIT-UP (CONT. 6)",
    "CHAIN FIT-UP",
    "SETTING DETAILS",
    "SETTING TABLE",
    "BILL OF MATERIALS",
)
# Rule 22 (R5 machinist review): the geometric settings print as native
# dimensions on the SETTING DETAILS sheet's lettered details, every other
# measurable setting or acceptance as a row of the SETTING TABLE sheet; the
# steps keep their values and cite the detail or row.
SETTING_DETAIL_SHEET = "SETTING DETAILS"
SETTING_TABLE_SHEET = "SETTING TABLE"
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

# --- last sheet: full qualified Numbers and two native BOM pieces ------------
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
# The caption's top row stands under the BOM tables' last rows (y ~.117 on
# the 48-row fill); 19 rows clear the inner border.
BOM_REFERENCE_CAPTION_XY = (0.100, 0.100)
BOM_REFERENCE_CAPTION = (
    "REFERENCE\n"
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
# Sheet 2 retains the established model fields; the BOM has the last sheet.
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
# column's leaders are in the same order as their tips.
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
# The 1:1 locator that carries the cutting line: a *Top view, so it takes a
# letter, and sheet 1's front view carries its viewing arrow.
PIVOT_LOCATOR_LETTER = "B"
PIVOT_LOCATOR_CAPTION = (
    f"VIEW {PIVOT_LOCATOR_LETTER} {PIVOT_LOCATOR_SCALE[0]:g}:{PIVOT_LOCATOR_SCALE[1]:g}"
)
PIVOT_LOCATOR_CAPTION_XY = (
    PIVOT_LOCATOR_CENTER[0] - PIVOT_LOCATOR_RADIUS - 0.030,
    PIVOT_LOCATOR_CENTER[1] + 0.002,
)

CROP_NO_ERROR = 1  # swCropViewErrors_e.swCropViewErrors_NoError

# --- sheet 3: the transgear drawn apart, two isometric views ------------------
# PAPER_DRIVE_EXPLODED moves the hanger's plate, the disc cluster and the knob
# stack along their own axes (machine Z).
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
        "pd-vn-transgear-hub-key-pin",
        explode.DISC_SCREW,
        "pd-transgear-front-bushing",
        "pd-vn-transgear-retaining-ring",
        "pd-vn-transgear-cluster-shim",
    }
)
if not CLUSTER_STEMS < explode.TRANSGEAR_SHOWN_STEMS:
    raise AssertionError("the disc cluster's view shows exploded transgear families")


@dataclass(frozen=True)
class ExplodedGroup:
    """One sheet-3 view: its families, where it is placed and its ring field.
    A ``ring_floor`` lets a ring too tall for the field run down to it where
    its balloons clear the title block (exploded_ring_shift)."""

    label: str
    stems: frozenset[str]
    center: tuple[float, float]
    ring_limits: Box
    ring_floor: float | None = None


# The title block's top-left corner, kept 3 mm clear as sheet 1's isometric
# field keeps its top (ISO_RING_LIMITS).
TITLE_BLOCK_KEEP_OUT = (
    DRAWING_TEMPLATES[SPEC.layout].title_block_left_m - 0.003,
    DRAWING_TEMPLATES[SPEC.layout].title_block_top_m + 0.003,
)
# The knob stack and hanger's ring at 2:3 is about 199 x 185 mm (run
# 20261024T025815061Z's outline scaled), the cluster's about 135 x 130 mm
# (its projected box from the builder's stations). The title block spans x
# 218 to 420, y 13 to 66 mm, so the left field stops above it. #2425's cup
# screw, thrown 18 mm behind the cup, made the knob stack's ring 199.3 mm
# tall in that 197.0 mm field (run 20261121T015111001Z), so it may run down
# into the empty field left of the title block, as far below as the left
# field's margin from the border.
TRANSGEAR_EXPLODED_GROUPS = (
    ExplodedGroup(
        "knob stack and hanger exploded",
        explode.TRANSGEAR_SHOWN_STEMS - CLUSTER_STEMS,
        (0.140, 0.168),
        (0.018, 0.070, 0.262, 0.267),
        ring_floor=0.018,
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

# --- sheets 5 to 8: ordered steps in two columns, same note-field budgets ----
FITUP_SCALE = (1.0, 10.0)
FITUP_REFERENCE_CENTER = (0.100, 0.045)
FITUP_LINE_WIDTH = 68  # characters; default-format note text
STEP_LINE_PITCH = 0.0045  # default-format note line pitch (sheet m)
# Each column's top-left corner, then its right limit and lowest y: the left
# column stops above the reference view; the right column stops above the
# title block (top 0.066).
FITUP_NOTE_XY = ((0.018, 0.262), (0.215, 0.262))
FITUP_NOTE_LIMITS = ((0.210, 0.075), (0.418, 0.072))
# Where the transgear's steps and the chain fit-up's begin.
FITUP_TRANSGEAR_KEY = "disc-cluster-assembled"
FITUP_CHAIN_KEY = "loaded-rack-geometry-checked"

# Sheet 6's DETAIL K: K's DRO setting from the arm's pin bore S, the
# assembly's hidden KnobSettingReference chain
# (pd_paper_drive_knob_setting_spec) on the arm and plate seen from the
# machine front at 1:1, as the arm-plate-located step sets them front up from
# the pin pressed in S;
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
# On the sheet the arm-plate-located step opens (STEP_START_SHEETS): #2417's
# cluster and pin steps ahead of it no longer leave it room on sheet 5, nor
# #2425's bush press on sheet 6.
KNOB_SETTING_SHEET = "ASSEMBLY AND FIT-UP (CONT. 2)"
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
# The MHA-PD-28 bush is pressed and reamed in the plate before the plate is
# set (#2425), so the knob bore N the located step indicates is the bush's.
KNOB_SETTING_INSTANCES = frozenset(
    {"pd-transgear-arm-1", "pd-transgear-arm-plate-1", "pd-transgear-knob-bush-1"}
)
# The located step's acceptance for "true": a null reading on the indicator, so the
# setting's centring bound comes from this stated sweep, not from the
# indicator's unknown accuracy over its range (codjiflo P2 on 8e8d5d5): a
# sweep under .0005 puts each centre within .00025. The shop's 1 um lever
# indicator (shop.toml gauges.dti, owner 2026-11-17) reads it with room to
# spare. It names what it holds (machinist review round 5 read a finer sweep
# as finer than the .002 S-K band needs, rule 4): K's worst case must stay
# inside its Ø.008 setting circle
# (paper_drive_arm_registration.REDUCER_AXIS_SETUP_RADIUS_MM; owner ruling
# 2026-11-08 (Pedro), #2144 item 5.3). The pivot lever amplifies the across
# error, so a .0005 sweep puts K up to .0022 off, inside the .004 radius
# (test_the_jig_bored_k_lands_in_the_set_band_with_margin_at_both_ends).
# The radial part of that worst case (.0008) keeps N inside the S to N set
# band, which governs along S-N; the .004 circle bounds the rest. TRUE names
# both, so it no longer reads as wider than DETAIL K's S to N limits (#2417).
# The trial mesh may move the table only so far that N, indicated TRUE with
# that radial error, stays within those limits (owner ruling 2026-11-24, audit
# part 2 question C1; pd_paper_drive_knob_setting_spec derives the moves).
# The knob-bore point's label inside DETAIL K. DETAIL K keeps its letter
# (other sheets cite "MHA-PD-00 DETAIL K"), so the point takes a letter used
# nowhere else on the package (machinist review round 7, rules 9 and 26: K
# meant both the view and the bore).
KNOB_BORE_LETTER = "N"
KNOB_SETTING_SWEEP_IN = knob_setting.TRUE_SWEEP_IN
_KNOB_SETTING_SWEEP_TEXT = f"{KNOB_SETTING_SWEEP_IN:g}".lstrip("0")
KNOB_SETTING_CIRCLE_TEXT = (
    f"WITHIN {steps.inch_text(registration.REDUCER_AXIS_SETUP_RADIUS_MM, 3)} OF ITS "
    f"{KNOB_SETTING_VIEW_NAME} SETTING"
)
KNOB_SETTING_TRUE = (
    f"TRUE: SWEEP UNDER {_KNOB_SETTING_SWEEP_TEXT} ON THE TEST INDICATOR, SO "
    f"{KNOB_BORE_LETTER} LANDS INSIDE "
    f"THE S TO {KNOB_BORE_LETTER} BAND, {KNOB_SETTING_CIRCLE_TEXT}"
)
# The trial moves of the table, in DRO counts on DETAIL K's two axes
# (pd_paper_drive_knob_setting_spec): one toward S for a shake over the
# ceiling; away from S only where the limit leaves the mill a settable move
# after TRUE's error (from the mid-band aim it leaves .00028, so none prints
# and a pair that runs tight takes the inspection exit).  The move is a
# table setting, so it is a setting-table row the step cites, never step
# text (rule 22; codjiflo r2 on #3539).
def _knob_move_text(move: tuple[float, float]) -> str:
    return f"{steps.inch_text(move[0], 4)} ALONG AND {steps.inch_text(move[1], 4)} ACROSS"


KNOB_TRIAL_MOVE_TEXT = _knob_move_text(knob_setting.TRIAL_MOVE_TOWARD_MM)
KNOB_TRIAL_AWAY_MOVE_TEXT = (
    None
    if knob_setting.TRIAL_MOVE_AWAY_MM is None
    else _knob_move_text(knob_setting.TRIAL_MOVE_AWAY_MM)
)
if KNOB_TRIAL_AWAY_MOVE_TEXT not in (None, KNOB_TRIAL_MOVE_TEXT):
    raise AssertionError("the located step words one move both ways or the toward move alone")
# The second column's steps end above this on DETAIL K's sheet.
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
    KNOB_BORE_LETTER: f"{_config.parts('pd-transgear-knob-bush')['number']} KNOB BORE",
    "T": f"{_config.parts('pd-vn-transgear-arm-plate-screw')['number']} TAP",
}
# The DRO frame is the arm's pivot-bore-to-S axis: ALONG runs from S toward
# the pivot bore, off the crop (pd_paper_drive_knob_setting_spec.py:59-66,
# 92-103, on pd_transgear_arm_geometry.ARM_U), the axis the located step
# trams; ACROSS is square to it in the plate's face.
KNOB_SETTING_PIVOT_LINES = (
    "ALONG: S TO PIVOT BORE",
    "ACROSS: SQUARE TO IT",
)
# Rule 4: the S-N band is the knob pinion's centre distance on the disc, so
# the key names that mesh (two lines, to stay left of the circle).
KNOB_SETTING_MESH_LINES = (
    f"S-{KNOB_BORE_LETTER} SETS {_config.parts('pd-transgear-knob-shaft')['number']} TO",
    f"{_config.parts('pd-rack-pinion')['number']} DISC MESH",
)
# The caption is the detail's own label, scale and step (rule 9); a DETAIL
# enlarges its parent's circle as that view sees it (the sheet 1 front view's
# circle K, *Front here too), so ALONG and ACROSS read as the located step's
# front-up setup sees the arm. Its parent is no longer named in prose
# (integration review at 8fb7fb46f7: "VIEW K" plus "DETAIL OF CIRCLE K, SHEET
# 1 FRONT VIEW" read as an arrow view explained in words). No comma after the
# name: a two-digit step number keeps the line inside the key's 22-character
# width, clear of the setting texts.
KNOB_SETTING_CAPTION = "\n".join(
    (
        f"{KNOB_SETTING_VIEW_NAME} 1:1 (STEP {steps.step_number('arm-plate-located')})",
        *KNOB_SETTING_MESH_LINES,
        *(f"{letter}: {name}" for letter, name in KNOB_SETTING_LEGEND.items()),
        *KNOB_SETTING_PIVOT_LINES,
    )
)
# Under the steps' field top (raised a line in round 10 for two parent lines
# the caption no longer carries, so it now ends two lines higher).
KNOB_SETTING_CAPTION_XY = (0.213, 0.139)
# Each letter's centre stands this far off its circle's centre (sheet m): S
# inward and away from Q (at 15:150 S-N spans most of the crop, so S's
# letter past the pin would leave it), T diagonally away from both chain
# legs, N radially out past the bush's hub, just outside the crop.
KNOB_SETTING_LETTER_GAPS = {"S": 0.005, "T": 0.005, KNOB_BORE_LETTER: 0.0095}
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

# Sheet 6's DETAIL E: the cluster's shimmed ring gap, the assembly's hidden
# ClusterFloatSetting line (pd_paper_drive_cluster_float_spec) between the
# MHA-PD-VN-61 ring and the MHA-PD-25 front bushing on the pin, seen from the
# side at 5:1 and cropped to a circle on the gap. It stands in sheet 6's left
# field, under the knob stack's column and over the reference isometric's
# caption; the shimming step on sheet 5 cites it.
CLUSTER_FLOAT_VIEW_NAME = steps.CLUSTER_FLOAT_VIEW_NAME
CLUSTER_FLOAT_SHEET = "ASSEMBLY AND FIT-UP (CONT.)"
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
        f"{CLUSTER_FLOAT_VIEW_NAME} 5:1 (STEP {steps.step_number('disc-cluster-shimmed')})",
        f"RING TO FRONT BUSHING, {_config.parts('pd-transgear-feed-pinion')['number']} "
        "SLEEVE REARWARD",
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
    raise AssertionError("DETAIL E's circle must frame the ring gap's text")
# The step column over DETAIL E ends this far above its circle.
CLUSTER_FLOAT_FIELD_TOP = CLUSTER_FLOAT_CENTER[1] + CLUSTER_FLOAT_RADIUS + 0.004

# Sheet 1's marks for the lettered views. DETAIL K and DETAIL E enlarge parts
# of the front and right views, so each takes a boundary circle there: the
# crop's own model circle at sheet 1's scale, never under 3 mm across the
# sheet so its letter has something to name. VIEW B, a *Top locator, takes a
# viewing arrow pointing down onto the pivot.
_ASSEMBLED_M_PER_MM = ASSEMBLED_SCALE[0] / ASSEMBLED_SCALE[1] / 1000.0
PARENT_BOUNDARY_MIN_RADIUS = 0.003
KNOB_SETTING_MODEL_CENTRE = (
    (knob_setting.S_XY[0] + knob_setting.K_XY[0]) / 2.0,
    (knob_setting.S_XY[1] + knob_setting.K_XY[1]) / 2.0,
    0.0,
)
KNOB_SETTING_PARENT_RADIUS = max(
    PARENT_BOUNDARY_MIN_RADIUS,
    KNOB_SETTING_RADIUS * KNOB_SETTING_SCALE[1] / KNOB_SETTING_SCALE[0] * 1000.0
    * _ASSEMBLED_M_PER_MM,
)
CLUSTER_FLOAT_PARENT_RADIUS = max(
    PARENT_BOUNDARY_MIN_RADIUS,
    CLUSTER_FLOAT_RADIUS / _CLUSTER_FLOAT_M_PER_MM * _ASSEMBLED_M_PER_MM,
)
# Each boundary's letter stands in clear sheet, pointing back to the circle's
# rim: DETAIL K's right of the circle, under the MHA-PD-07 bar and right of
# the chain's top run; DETAIL E's left of the right view, beyond the knob's
# thumbnut (round 2: letters set just past the circle landed on the chain and
# the sprocket; round 3: K at (8, 10) mm sat on the bar's lower edge).
KNOB_SETTING_LETTER_OFFSET = (0.019, 0.0058)
CLUSTER_FLOAT_LETTER_OFFSET = (-0.012, 0.004)
VIEWING_ARROW_LENGTH = 0.010
VIEWING_ARROW_STANDOFF = 0.002


def detail_letter_pointer(
    centre: tuple[float, float], radius: float, offset: tuple[float, float]
) -> tuple[tuple[float, float], tuple[float, float]]:
    """A boundary letter's (note point, leader tip): the note at ``offset``
    from the circle's centre, the tip on the rim toward it."""
    length = math.hypot(*offset)
    if length <= radius:
        raise AssertionError("a boundary letter must stand outside its circle")
    tip = (
        centre[0] + offset[0] * radius / length,
        centre[1] + offset[1] * radius / length,
    )
    return (centre[0] + offset[0], centre[1] + offset[1]), tip


def viewing_arrow_xy(
    target: tuple[float, float],
) -> tuple[tuple[float, float], tuple[float, float]]:
    """A downward viewing arrow onto ``target``: (tip, letter note point)."""
    tip = (target[0], target[1] + VIEWING_ARROW_STANDOFF)
    return tip, (target[0] - 0.001, tip[1] + VIEWING_ARROW_LENGTH)


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
        KNOB_BORE_LETTER: unit((k[0] - centre[0], k[1] - centre[1])),
    }
    tips = {"S": s, "T": t, KNOB_BORE_LETTER: k}
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
    "ASSEMBLY AND FIT-UP (CONT. 2)": FITUP_SCALE,
    "ASSEMBLY AND FIT-UP (CONT. 3)": FITUP_SCALE,
    "ASSEMBLY AND FIT-UP (CONT. 4)": FITUP_SCALE,
    "ASSEMBLY AND FIT-UP (CONT. 5)": FITUP_SCALE,
    "ASSEMBLY AND FIT-UP (CONT. 6)": FITUP_SCALE,
    "CHAIN FIT-UP": FITUP_SCALE,
    "SETTING DETAILS": (5.0, 1.0),
    "SETTING TABLE": FITUP_SCALE,
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
    "pd-feed-rack": _config.parts("pd-feed-rack")["number"],
    "pd-platen-bottom-guide": _config.parts("pd-platen-bottom-guide")["number"],
    "pd-platen-guide": _config.parts("pd-platen-guide")["number"],
    "sh-vn-fillister-screw-91794a055--RackScrew": _config.parts(
        "sh-vn-fillister-screw-91794a055"
    )["number"],
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
    "pd-vn-transgear-hub-key-pin": _config.parts("pd-vn-transgear-hub-key-pin")["number"],
    "pd-transgear-front-bushing": _config.parts("pd-transgear-front-bushing")["number"],
    "pd-vn-transgear-retaining-ring": _config.parts("pd-vn-transgear-retaining-ring")["number"],
    "pd-vn-transgear-cluster-shim": _config.parts("pd-vn-transgear-cluster-shim")["number"],
    "pd-rack-pinion": _config.parts("pd-rack-pinion")["number"],
    "sh-vn-fillister-screw-91794a055--DiscScrew": _config.parts(
        "sh-vn-fillister-screw-91794a055"
    )["number"],
    "pd-transgear-knob-shaft": _config.parts("pd-transgear-knob-shaft")["number"],
    "pd-transgear-drive-collar": _config.parts("pd-transgear-drive-collar")["number"],
    "pd-vn-transgear-knob-drive-pin": _config.parts("pd-vn-transgear-knob-drive-pin")["number"],
    "pd-vn-transgear-collar-flat-pin": _config.parts("pd-vn-transgear-collar-flat-pin")[
        "number"
    ],
    "pd-transgear-thumbnut": _config.parts("pd-transgear-thumbnut")["number"],
    "pd-transgear-knob-thrust-ring": _config.parts("pd-transgear-knob-thrust-ring")["number"],
    "pd-transgear-knob-bush": _config.parts("pd-transgear-knob-bush")["number"],
    "pd-transgear-knob-cup": _config.parts("pd-transgear-knob-cup")["number"],
    "pd-vn-transgear-knob-cup-screw": _config.parts("pd-vn-transgear-knob-cup-screw")["number"],
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
        explode.RACK_SCREW: (rack_screw.STEM, rack_screw.CONFIGURATION),
        explode.DISC_SCREW: (disc_screw.STEM, disc_screw.CONFIGURATION),
    }
)
if set(BOM_COMPONENT_IDENTITIES) != set(BOM_PART_NUMBERS):
    raise AssertionError("each shared fillister member is its own BOM row")
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
    "pd-vn-transgear-hub-key-pin": _config.parts("pd-vn-transgear-hub-key-pin")[
        "supplier_skus"
    ][0],
    "pd-vn-transgear-retaining-ring": _config.parts("pd-vn-transgear-retaining-ring")[
        "supplier_skus"
    ][0],
    "pd-vn-transgear-cluster-shim": _config.parts("pd-vn-transgear-cluster-shim")[
        "supplier_skus"
    ][0],
    "pd-vn-transgear-knob-drive-pin": _config.parts("pd-vn-transgear-knob-drive-pin")[
        "supplier_skus"
    ][0],
    "pd-vn-transgear-collar-flat-pin": _config.parts("pd-vn-transgear-collar-flat-pin")[
        "supplier_skus"
    ][0],
    "pd-vn-transgear-knob-cup-screw": _config.parts("pd-vn-transgear-knob-cup-screw")[
        "supplier_skus"
    ][0],
}
# Assembly-specific wording stays here. Shared chain and fillister
# descriptions follow the native member spec, whose model-owned BOM text can
# override a written cell.
BOM_DESCRIPTIONS = {
    "pd-support-bar": "PAPER-DRIVE SUPPORT BAR",
    "sh-column-clamp-front": "COLUMN CLAMP, FRONT",
    "sh-column-clamp-back": "COLUMN CLAMP, BACK",
    "sh-vn-clamp-screw": f"FILLISTER SCREW, MCMASTER {_SKU['sh-vn-clamp-screw']}",
    "pd-platen": "PLATEN",
    "pd-feed-rack": f"FEED RACK, {feed_rack.DP:g}DP PA{feed_rack.PA_DEG:g}",
    "pd-platen-bottom-guide": "PLATEN BOTTOM GUIDE",
    "pd-platen-guide": "PLATEN TOP GUIDE",
    explode.RACK_SCREW: rack_screw.BOM_DESCRIPTION,
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
    "pd-vn-transgear-hub-key-pin": (
        f"HUB KEY PIN, MCMASTER {_SKU['pd-vn-transgear-hub-key-pin']}"
    ),
    "pd-transgear-front-bushing": "TRANSGEAR FRONT BUSHING",
    "pd-vn-transgear-retaining-ring": (
        f"RETAINING RING, MCMASTER {_SKU['pd-vn-transgear-retaining-ring']}"
    ),
    # QTY counts the kit: the stack's nominal shims plus the spares stored in
    # the spare T18's bore, so the fit-up's 0 to SHIM_COUNT_MAX (DETAIL E) is
    # supplied (Codjiflo and machinist review, #2124).
    "pd-vn-transgear-cluster-shim": (
        f"SHIM, MCMASTER {_SKU['pd-vn-transgear-cluster-shim']}"
    ),
    "pd-rack-pinion": (
        f"REDUCER DISC, STOCK {disc.TEETH}T {disc.DIAMETRAL_PITCH:g}DP "
        f"PA{disc.PRESSURE_ANGLE_DEG:g}"
    ),
    explode.DISC_SCREW: disc_screw.BOM_DESCRIPTION,
    "pd-transgear-knob-shaft": (
        f"KNOB SHAFT, STOCK {knob_shaft.TEETH}T "
        f"{knob_shaft.DIAMETRAL_PITCH:g}DP PA{knob_shaft.PRESSURE_ANGLE_DEG:g}"
    ),
    "pd-transgear-drive-collar": "KNOB DRIVE COLLAR",
    "pd-vn-transgear-knob-drive-pin": (
        f"WHEEL DRIVE DOWEL, MCMASTER {_SKU['pd-vn-transgear-knob-drive-pin']}"
    ),
    "pd-vn-transgear-collar-flat-pin": (
        f"COLLAR FLAT PIN, MCMASTER {_SKU['pd-vn-transgear-collar-flat-pin']}"
    ),
    "pd-transgear-thumbnut": "TRANSGEAR THUMBNUT",
    "pd-transgear-knob-thrust-ring": "KNOB THRUST RING",
    "pd-transgear-knob-bush": "KNOB BUSH",
    "pd-transgear-knob-cup": "KNOB CUP",
    "pd-vn-transgear-knob-cup-screw": (
        f"{cup_screw.THREAD} FILLISTER SCREW, MCMASTER {_SKU['pd-vn-transgear-knob-cup-screw']}"
    ),
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
    "pd-vn-transgear-hub-key-pin": 1,
    "pd-transgear-front-bushing": 1,
    "pd-vn-transgear-retaining-ring": 1,
    # The kit: the stack's nominal count plus the spares (DETAIL E sets the
    # fitted count).
    "pd-vn-transgear-cluster-shim": cluster_fit.SHIM_COUNT_MAX,
    "pd-rack-pinion": 1,
    explode.DISC_SCREW: hub_geometry.SCREW_COUNT,
    "pd-transgear-knob-shaft": 1,
    "pd-transgear-drive-collar": 1,
    "pd-vn-transgear-knob-drive-pin": len(seat_geometry.PIN_HOLE_ANGLES_DEG),
    "pd-vn-transgear-collar-flat-pin": 1,
    "pd-transgear-removable": 3,  # two mounted wheels plus the loose T18 spare
    "pd-transgear-thumbnut": 1,
    "pd-transgear-knob-thrust-ring": 1,
    "pd-transgear-knob-bush": 1,
    "pd-transgear-knob-cup": 1,
    "pd-vn-transgear-knob-cup-screw": 1,
}
# The platen group's shared-member row: one rack screw in each feed-rack tap.
PLATEN_QUANTITIES = {explode.RACK_SCREW: len(feed_rack.TAP_X)}


# The builder names each instance ``<file stem>-<n>`` in placement order and
# proves the shared fillister's names as it places them: the platen's
# RackScrews first, then the transgear's DiscScrews after them.
_FIRST_INSTANCE = {explode.DISC_SCREW: PLATEN_QUANTITIES[explode.RACK_SCREW] + 1}


def row_instance_names(key: str, count: int) -> tuple[str, ...]:
    """The native names of BOM row ``key``'s first ``count`` instances."""
    first = _FIRST_INSTANCE.get(key, 1)
    stem = BOM_COMPONENT_IDENTITIES[key][0]
    return tuple(f"{stem}-{index}" for index in range(first, first + count))


# One assembled inner or outer link spans one pitch. The chain is cut with an
# inner link at each end, and the connecting link closes the loop as its last
# outer link.
CHAIN_QUANTITIES = {
    "sh-vn-chain-link--InnerLink": chain.LINK_COUNT // 2,
    "sh-vn-chain-link--OuterLink": chain.LINK_COUNT // 2 - 1,
    "pd-vn-chain-connecting-link": 1,
}
# MHA-SH-VN-59 numbers two BOM rows (the rack screw and the disc screw) and
# MHA-SH-VN-50 two more (the chain's inner and outer links), so the sheet
# wording adds the BOM item to those four (#3106, rule 22: the number alone
# named either row); _validate_bom reads each item back.
SHARED_NUMBER_ITEMS = {
    explode.RACK_SCREW: 9,
    explode.DISC_SCREW: 34,
    "sh-vn-chain-link--InnerLink": 46,
    "sh-vn-chain-link--OuterLink": 47,
}
if {
    stem
    for stem, number in BOM_PART_NUMBERS.items()
    if list(BOM_PART_NUMBERS.values()).count(number) > 1
} != set(SHARED_NUMBER_ITEMS):
    raise AssertionError("every Number on two BOM rows carries its item in the wording")


# The spare 18-tooth sprocket takes its own loop, cut from the same supplier
# chain and closed by its own connecting link (owner ruling 2026-11-20
# (Pedro), #2429, option A). paper_drive_chain_fit closes it at the source
# centres at 62 pitches with the spare on the knob (12-tooth crank) and 68
# with it on the crank (24-tooth knob); the test solves both. The order
# length covers the longer.
SPARE_TEETH = next(
    teeth
    for name, teeth in sprocket.CONFIGS
    if name not in (sprocket.CRANK_CONFIG, sprocket.KNOB_CONFIG)
)
SPARE_LOOP_PITCHES = {"knob": 62, "crank": 68}
# The inner and outer link rows print one purchase Number, one supplier
# chain's two link kinds, so the BOM sheet says what that Number is and what
# to order (2026-10-27 ENFORCE review, r1-r3: one Number with two
# descriptions and quantities left the order unknown).  It joins the BOM
# reference's caption, in the air right of that view.
_CHAIN_CUT_PITCHES = (
    CHAIN_QUANTITIES["sh-vn-chain-link--InnerLink"]
    + CHAIN_QUANTITIES["sh-vn-chain-link--OuterLink"]
)
_SPARE_CUT_PITCHES = {
    where: pitches - 1 for where, pitches in SPARE_LOOP_PITCHES.items()
}
CHAIN_ORDER_FEET = math.ceil(
    (_CHAIN_CUT_PITCHES + max(_SPARE_CUT_PITCHES.values())) * chain.LINK_PITCH / 304.8
)
BOM_CHAIN_ORDER_NOTE = (
    f"{BOM_PART_NUMBERS['sh-vn-chain-link--InnerLink']}, ITEMS "
    f"{SHARED_NUMBER_ITEMS['sh-vn-chain-link--InnerLink']} AND "
    f"{SHARED_NUMBER_ITEMS['sh-vn-chain-link--OuterLink']}, IS\n"
    f"ONE CHAIN, MCMASTER {_config.parts('sh-vn-chain-link')['supplier_skus'][0]}:\n"
    f"ORDER {CHAIN_ORDER_FEET} FT. CUT {_CHAIN_CUT_PITCHES} PITCHES,\n"
    f"{CHAIN_QUANTITIES['sh-vn-chain-link--InnerLink']} INNER AND "
    f"{CHAIN_QUANTITIES['sh-vn-chain-link--OuterLink']} OUTER LINKS;\n"
    f"{BOM_PART_NUMBERS['pd-vn-chain-connecting-link']} CLOSES THE LOOP.\n"
    f"THE SPARE {SPARE_TEETH}-TOOTH SPROCKET'S LOOP:\n"
    f"CUT {_SPARE_CUT_PITCHES['knob']} PITCHES (IT ON THE KNOB) OR\n"
    f"{_SPARE_CUT_PITCHES['crank']} (ON THE CRANK) FROM THE REST."
)
if not set(TRANSGEAR_QUANTITIES) <= set(BOM_PART_NUMBERS):
    raise AssertionError("every transgear family is a BOM row")
# The transgear views draw the mounted knob wheel and the stacked shims; the
# crank wheel, the spare T18 and the spare shims in its bore are sheet 1's.
TRANSGEAR_INSTANCE_ROWS = {
    name: key
    for key, count in TRANSGEAR_QUANTITIES.items()
    for name in row_instance_names(
        key,
        {
            "pd-transgear-removable": 1,
            "pd-vn-transgear-cluster-shim": cluster_fit.SHIM_COUNT_MODEL,
        }.get(key, count),
    )
}
TRANSGEAR_INSTANCES = frozenset(TRANSGEAR_INSTANCE_ROWS)
# Sheet 2's isometric cannot reach these families' ink. Farm run
# 20261001T051043622Z found none for the feed sleeve: its extreme-point picks
# missed, and its gear edges exceeded the fallback's edge budget. The rear
# bushing behind the reducer disc and the knob drive and hanger hardware are
# obscured by their neighbours. The pin, front bushing and retaining ring
# attach within 3.5 mm of each other on the pin nose, so their three leaders
# met there with overlapping arrowheads (machinist review, run
# 20261024T124144759Z). The collar's flat pin and the hub's key pin sit
# inside their hosts (#2409), as the MHA-PD-VN-71 screw sits in the cup's
# counterbore; the MHA-PD-28 bush's hub stands under the thrust ring and in
# the arm, its stub under the cup (#2425). Sheet 3's explode shows and
# balloons them all, with every other family it draws apart.
ISO_HIDDEN_STEMS = frozenset(
    {
        "pd-transgear-feed-pinion",
        "pd-transgear-knob-shaft",
        "pd-transgear-drive-collar",
        "pd-vn-transgear-knob-drive-pin",
        "pd-vn-transgear-collar-flat-pin",
        "pd-vn-transgear-hub-key-pin",
        "pd-transgear-knob-bush",
        "pd-vn-transgear-knob-cup-screw",
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
    for name, key in TRANSGEAR_INSTANCE_ROWS.items()
    if key in explode.TRANSGEAR_SHOWN_STEMS
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
# Sheet 3's balloon 36 walked to the journal's rear end, where the shaft
# meets the exploded plate's knob boss in the isometric, and read as the
# plate's (2026-11-03 ENFORCE review of #2095's run 20261103T013313660Z,
# r1/r3). It lands instead on a 15T tooth tip at F, the pinion's front face:
# the knob shaft is placed unrotated (FRONT_STACK_PHASE_DEG 0) with a tooth
# centred on local +X every 24 deg, and the tooth at 192 deg projects lower
# right of the axis in the *Isometric (sheet right -0.707 x, sheet up
# 0.408 x + 0.816 y), on F's camera side and away from the forward neck.
KNOB_SHAFT_BALLOON_ANGLE = math.radians(8 * 360.0 / knob_shaft.TEETH)
if knob_shaft.FRONT_STACK_PHASE_DEG != 0.0:
    raise AssertionError("balloon 36's tooth needs the knob shaft unrotated")
_KNOB_TIP_R = knob_shaft.OUTSIDE_DIA / 2.0
KNOB_SHAFT_BALLOON_POINT_MM = (
    round(_KNOB_TIP_R * math.cos(KNOB_SHAFT_BALLOON_ANGLE), 4),
    round(_KNOB_TIP_R * math.sin(KNOB_SHAFT_BALLOON_ANGLE), 4),
    0.0,
)
# Sheet 3's balloon 28 walked to the sleeve's rear-face tip arc (part
# (4.892, 3.024, 0)), drawn hard against the exploded MHA-PD-24 bushing, so
# its arrow read as the bushing's and balloon 26 seemed to share a part
# (machinist review of #2551's run 20261111T200045620Z, r1/r3). It lands
# instead on an edge along the teeth: the corner where the 30-degree tooth's
# tip land meets its flank toward 45 degrees (teeth centre on local +X every
# 30 degrees; the spaces centre on TOOTH_SPACE_INSPECTION_PHASE_RAD), 6 mm
# forward of the rear face. The sleeve is placed turned about Y, so the
# sheet's *Isometric looks along local (1, 1, 1) and that corner faces the
# eye; at 2:3 it draws about 3 mm down-left of the old point. (A point on
# the tip land off a corner is on no edge: run 20261111T221813123Z.)
FEED_SLEEVE_BALLOON_Z = 6.0
if not 0.0 < FEED_SLEEVE_BALLOON_Z < feed_pinion.FACE_WIDTH:
    raise AssertionError("balloon 28 lands on the feed sleeve's teeth")
if feed_pinion.TOOTH_SPACE_INSPECTION_PHASE_RAD != math.pi / feed_pinion.TEETH:
    raise AssertionError("balloon 28's corner needs the teeth centred on local +X")
_FEED_CORNER_ANGLE = (
    math.radians(30.0)
    + feed_pinion.STOCK_PROFILE.angular_pitch_rad / 2.0
    - feed_pinion.STOCK_PROFILE.tip_half_angle_rad
)
_FEED_TIP_R = feed_pinion.STOCK_PROFILE.blank_radius_mm
FEED_SLEEVE_BALLOON_POINT_MM = (
    round(_FEED_TIP_R * math.cos(_FEED_CORNER_ANGLE), 4),
    round(_FEED_TIP_R * math.sin(_FEED_CORNER_ANGLE), 4),
    FEED_SLEEVE_BALLOON_Z,
)
# Sheet 3's balloon 37 walked to the collar's lowest point, where the
# MHA-PD-VN-70 flat pin, drawn just below it, ends, so its arrow read as the
# pin's beside balloon 39's (#2831, machinist review of #2822's run
# 20261115T133410689Z). It lands instead on the front face's outer circle at
# local -X: the collar is placed unrotated about its axis (its flat pin at
# local -Y draws below it), so -X draws lower right of the axis in the
# *Isometric (sheet right -0.707 x), on the face the camera sees and clear
# of the pin, the drive dowels (+-Y) and the knob wheel drawn down-left.
COLLAR_BALLOON_POINT_MM = (round(-collar.OD / 2.0, 4), 0.0, 0.0)
_BALLOON_POINTS_MM = {
    "pd-transgear-disc-hub": HUB_BALLOON_POINT_MM,
    "pd-transgear-knob-shaft": KNOB_SHAFT_BALLOON_POINT_MM,
    "pd-transgear-feed-pinion": FEED_SLEEVE_BALLOON_POINT_MM,
    "pd-transgear-drive-collar": COLLAR_BALLOON_POINT_MM,
}
TRANSGEAR_BALLOON_ANCHORS = {
    stem: BalloonAnchor(instance=explode.KNOB_WHEEL_INSTANCE)
    if stem == "pd-transgear-removable"
    else BalloonAnchor(point_mm=_BALLOON_POINTS_MM.get(stem))
    for stem in TRANSGEAR_QUANTITIES
}


def exploded_group_instances(group: ExplodedGroup) -> frozenset[str]:
    """The sheet-3 instances one view shows: its families' exploded instances."""
    return frozenset(
        name
        for name in TRANSGEAR_EXPLODED_INSTANCES
        if TRANSGEAR_INSTANCE_ROWS[name] in group.stems
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
# The spare shims, inserted after the stack's, in the spare T18's bore.
SPARE_SHIM_INSTANCES = frozenset(
    f"pd-vn-transgear-cluster-shim-{index}"
    for index in range(cluster_fit.SHIM_COUNT_MODEL + 1, cluster_fit.SHIM_COUNT_MAX + 1)
)
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
# each lock station's top plate (on the top guide), then its bottom plate
# (on the bottom guide), so pd-guide-lock-1 is the first station's top plate:
# exploded, it still stands behind the bar, and the default (lowest-named)
# landing put balloon 8 on the bar's lower edge (machinist review of run
# 20261024T082548908Z-cf4349b5). Every lock rises with the top guide, so the
# bottom plate, pd-guide-lock-2, hangs free under the bar.
PLATEN_GUIDE_LOCK_INSTANCE = "pd-guide-lock-2"
# The top guide: with MHA-PD-27 the bottom rail (#2410), MHA-PD-11 has one
# instance, pd-platen-guide-1. Its earlier default landing, on the bottom
# rail's end behind the platen, put balloon 7 beside the bar's front clamp
# screw, its leader through that head and onto balloon 4's arrowhead
# (machinist review of the final-head run 20261101T135807943Z). It explodes
# clear above the platen; its balloon lands on its top edge on the
# platen-mating face (part frame: x along the rail, y = height, z = 0),
# mid-span between the A4 and A5 screw stations and clear of both lock
# stations' plates and screws.
PLATEN_GUIDE_INSTANCE = "pd-platen-guide-1"
PLATEN_GUIDE_BALLOON_POINT_MM = (110.0, platen_guide.GUIDE_HEIGHT, 0.0)
# The paper and the platen: the default landings put balloon 10 on the
# paper's corner where it meets a clip and the platen, and balloon 5 on the
# platen's bottom corner beside balloon 6's arrow on the rack end (machinist
# review of run 20261111T044441656Z). Each lands mid-span on an edge of its
# own face, clear of the clips at the ends: the paper on its top edge (part
# frame: x along the sheet, y = height, the sketch plane z = 0), the platen
# on its front face's bottom edge (front face z = 0), each off the other's
# span.
PLATEN_PAPER_BALLOON_POINT_MM = (0.6 * RECORDING_PAPER_WIDTH_MM, RECORDING_PAPER_HEIGHT_MM, 0.0)
PLATEN_BALLOON_POINT_MM = (0.4 * platen.PLATE_WIDTH, 0.0, 0.0)
# The bottom guide, the rack and the rack screws hang below the platen
# (explode.PLATEN_STEPS), nothing in front of or above them, each ballooned
# on drawn ink and spread along the platen's width so their leaders come in
# from below in the order they stand, apart from the platen's (0.4 of its
# width from its crank-side edge). The bottom guide on its top face's front
# edge (part frame: x along the rail, y = height from the underside, front
# face z = 0), mid-span between its 3rd and 4th rack-screw counterbores,
# which its Ry180 pose puts 0.30 of the width from the crank-side edge. The
# rack on its flat top's edge (part frame: x along the strip from its
# crank-side end, flat top y = 0, z = 0 on a long face), mid-span between its
# 3rd and 4th taps, 0.70 of the width along. Between them, the 3rd rack screw
# (on the 3rd tap, 0.60 along) by its own body: its head and shank stand clear
# above the guide.
BOTTOM_GUIDE_BALLOON_POINT_MM = (
    (bottom_guide.SCREW_HOLE_X[2] + bottom_guide.SCREW_HOLE_X[3]) / 2.0,
    bottom_guide.GUIDE_HEIGHT,
    0.0,
)
FEED_RACK_BALLOON_POINT_MM = ((feed_rack.TAP_X[2] + feed_rack.TAP_X[3]) / 2.0, 0.0, 0.0)
PLATEN_RACK_SCREW_INSTANCE = row_instance_names(
    explode.RACK_SCREW, PLATEN_QUANTITIES[explode.RACK_SCREW]
)[2]
_PLATEN_PLACED_ANCHORS = {
    "pd-guide-lock": BalloonAnchor(instance=PLATEN_GUIDE_LOCK_INSTANCE),
    "pd-platen-guide": BalloonAnchor(
        point_mm=PLATEN_GUIDE_BALLOON_POINT_MM, instance=PLATEN_GUIDE_INSTANCE
    ),
    "pd-platen-paper": BalloonAnchor(point_mm=PLATEN_PAPER_BALLOON_POINT_MM),
    "pd-platen": BalloonAnchor(point_mm=PLATEN_BALLOON_POINT_MM),
    "pd-platen-bottom-guide": BalloonAnchor(point_mm=BOTTOM_GUIDE_BALLOON_POINT_MM),
    "pd-feed-rack": BalloonAnchor(point_mm=FEED_RACK_BALLOON_POINT_MM),
    explode.RACK_SCREW: BalloonAnchor(instance=PLATEN_RACK_SCREW_INSTANCE),
}
PLATEN_BALLOON_ANCHORS = {
    stem: _PLATEN_PLACED_ANCHORS.get(stem, BalloonAnchor()) for stem in explode.SHOWN_STEMS
}
if not set(_PLATEN_PLACED_ANCHORS) <= set(PLATEN_BALLOON_ANCHORS):
    raise AssertionError("sheet 4 shows every family it places a balloon on")


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


def exploded_ring_shift(outline: Box, group: ExplodedGroup) -> tuple[float, float]:
    """Shift that fits a sheet-3 view's balloon ring in its field.

    A ring that fits ``ring_limits`` is centred there (ring_fit_shift). One
    too tall for it, in a group with a ``ring_floor``, is centred across and
    hung from the field's top, running down at most to the floor. Its corners
    may then stand over the title block, but no balloon does:
    _spread_balloons sets each balloon's circle on an ellipse BALLOON_MARGIN
    outside the outline, so that ellipse, its circles and the outline itself
    must clear TITLE_BLOCK_KEEP_OUT. Raises naming the overflow.
    """
    try:
        return ring_fit_shift(outline, group.ring_limits, name=group.label)
    except ValueError:
        if group.ring_floor is None:
            raise
    left, _bottom, right, top = group.ring_limits
    ring_fit_shift(outline, (left, group.ring_floor, right, top), name=group.label)
    ring = _grown(outline, BALLOON_RING_REACH)
    shift = ((left + right - ring[0] - ring[2]) / 2.0, top - ring[3])
    centre_x = (outline[0] + outline[2]) / 2.0 + shift[0]
    centre_y = (outline[1] + outline[3]) / 2.0 + shift[1]
    semi_x = (outline[2] - outline[0]) / 2.0 + BALLOON_MARGIN
    semi_y = (outline[3] - outline[1]) / 2.0 + BALLOON_MARGIN
    circle = BALLOON_RING_REACH - BALLOON_MARGIN
    keep_x, keep_y = TITLE_BLOCK_KEEP_OUT
    # A circle reaches over the block from centres at keep_x - circle on; the
    # ellipse's lower edge rises away from its centre, so it is lowest there,
    # or at its foot when the centre itself stands over the block.
    across = max(keep_x - circle - centre_x, 0.0) / semi_x
    lowest = centre_y - semi_y * math.sqrt(1.0 - across**2) if across < 1.0 else math.inf
    findings = []
    if lowest - circle < keep_y:
        findings.append(
            f"{group.label} balloons down to {(lowest - circle) * 1000:.1f} mm over the "
            f"title block (keep above {keep_y * 1000:.1f} mm)"
        )
    if outline[2] + shift[0] > keep_x and outline[1] + shift[1] < keep_y:
        findings.append(f"{group.label} outline stands on the title block")
    if findings:
        raise ValueError(f"balloon ring does not fit: {'; '.join(findings)}")
    return shift


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


# --- sheet wording ---------------------------------------------------------------
# The sheets' part names: the BOM Number, with the item where one Number
# covers two rows (SHARED_NUMBER_ITEMS).
_N = {
    stem: f"{number} (ITEM {SHARED_NUMBER_ITEMS[stem]})"
    if stem in SHARED_NUMBER_ITEMS
    else number
    for stem, number in BOM_PART_NUMBERS.items()
}
KNOB_TEETH = knob_shaft.TEETH
# The knob shaft's gear named in words (rule 26): a coined "15T" read as
# Detail K's tap label T (machinist review of 7d151d7f13, r1 and r3). The
# MHA-PD-10 sleeve is the BOM's Feed Pinion Sleeve, so neither gear is a bare
# PINION (#3107, Codjiflo P3 on 3e6318a026): the knob shaft's is the KNOB
# PINION, or PINION after its MHA-PD-08 number; the sleeve's the FEED PINION.
KNOB_PINION = "KNOB PINION"
FEED_PINION = "FEED PINION"
# The knob's end float, set at fit-up (#2425, owner ruling 2026-11-20): the
# cup's front faced until its pilot depth is END_FLOAT less than the
# journal's stand-out behind the MHA-PD-28 bush, then bonded and screwed on
# the journal end; accepted on feelers at the setting's own band.
KNOB_END_FLOAT_RANGE = (
    knob_shaft.END_FLOAT - knob_shaft.END_FLOAT_SET_TOL,
    knob_shaft.END_FLOAT + knob_shaft.END_FLOAT_SET_TOL,
)
# Rule 23's bond bullet for the cup on the journal end (#2425, owner ruling
# 2026-11-20: LOCTITE 641, the removable grade, as the screw lock): the knob
# stack's sub-step that coats the journal, which the BOM sheet's consumables
# lines cite, and the cure before the knob is first turned, loaded or oiled
# (Henkel's LOCTITE 641 TDS states its strength at 24 h, 22 °C).
KNOB_CUP_BOND_SUB_STEP = 6
KNOB_CUP_BOND_CURE_H = 24
# Rule 23's bond bullet for the MHA-PD-20 spacer on the MHA-PD-VN-57
# shoulder (owner ruling 2026-11-24, fit audit question 6; LOCTITE 638,
# the grade pd_transgear_pivot_spacer_spec holds the gap to): the sub-step
# that coats the spacer's bore, which the BOM sheet's consumables lines cite,
# and the cure before the screw is seated (the spring then loads the bond).
PIVOT_SPACER_BOND_SUB_STEP = 6
PIVOT_SPACER_BOND_CURE_H = 24
# The same grade bonds the MHA-PD-23 pin in the arm (the next bullet), so
# the two cures and grades are pinned equal by test.
# Rule 23's bond bullet for the MHA-PD-23 pin in the arm (owner ruling
# 2026-11-24, fit audit question 4): the grade the pin's sheet names
# (pd_transgear_pin_spec.RETAINING_COMPOUND, pinned by test), the sub-step
# that coats the pin, and the cure before the cluster is fitted on it
# (Henkel's LOCTITE 638 TDS states its strength at 24 h, 22 °C).
PIN_BOND_COMPOUND = "LOCTITE 638"
PIN_BOND_SUB_STEP = 1
PIN_BOND_CURE_H = 24
# The reducer's backlash as an indicator reads it (#2417: a feeler leaf
# cannot be laid between 48DP flanks). The knob shaft and the disc are
# pressed lightly together, the shaft held and the disc rocked, with a test
# indicator's stylus tangent on the flank, at its tip, of the disc tooth
# next to the 15T.
#
# What that reads (codjiflo P2 on 27438d7: the running clearances are in the
# shake). Pressed together, the knob journal sits on the S side of the bush
# bore and the sleeve on the N side of the pin, so neither gives way along
# the rock and the mesh stands at the tightest centre the two running fits
# allow: closer than the axes by half of both diametral clearances
# (knob_setting.PRESSED_CLOSURE_MM). The tooth beside the mesh moves only as far as the
# flanks let it, so the cluster's shift on the pin and the pin's own bending
# are not read as shake.
#
# The ceiling is the loosest reading the charged terms can give: the
# circular backlash at the top of the S to N set band at every printed corner
# (paper_drive_mesh_check.reducer_mesh), closed by the smallest clearances,
# moved to the tip by the tip radius over the pitch radius and
# rounded outward onto the shop indicator's division, so that a build inside
# those terms is never refused and a reading over it sends the fitter to
# the remedy. It is the only check at assembly on the loose side of this
# mesh, the side the contact ratio lives on. The pin's lean in its bore (S is held
# square only within .001 over the arm, which the disc's height multiplies)
# is not in the window: the located step indicates S on the shank at the
# height the disc runs, so the setting is made where the mesh is (codjiflo
# P2 on 176fad0). The smaller tilt terms at the knob
# (paper_drive_geom.reducer_axis_tilt_maxima_rad) are not charged: #2510.
# Outward rounding
# departs from the package's inward windows (steps.inch_window) because this
# reading is a cross-check of parts already accepted on their own sheets.
# No floor prints: the disc shakes, which the needle moving shows, and the
# no-tight-spot turn checks the same thing all round (owner ruling
# 2026-11-24, audit part 2 question C2: "Yes." to THE DISC SHAKES (THE
# NEEDLE MOVES), .008 MAX; it retires the half-division floor of the
# delegated ruling of 2026-11-10, review finding #2960). What stays coded is
# that the tightest mesh the fits allow does not bind: a positive shake at
# the closest N may stand after the trial's move toward S, TRUE's error
# included (owner ruling 2026-11-24, audit part 2 question C1;
# knob_setting.TRIAL_LOWEST_CENTRE_MM, -.00069) closed by the largest
# clearances; the spec picks that move so it does not. A tight spot at any
# setting is still caught by the re-run trial.
_REDUCER_CIRCULAR_BACKLASH_MM = (
    mesh_check.reducer_mesh(
        knob_setting.TRIAL_LOWEST_CENTRE_MM - knob_setting.PRESSED_CLOSURE_MM[1]
    ).backlash_mm[0],
    mesh_check.reducer_mesh(
        disc.CENTRE_DISTANCE_WINDOW[1] - knob_setting.PRESSED_CLOSURE_MM[0]
    ).backlash_mm[1],
)
_DISC_TIP_RADII_MM = [profile.blank_radius_mm for profile in disc.manufactured_profiles()]
# Read on one of the shop's .001 in dial indicators (shop.toml
# gauges.dial-indicators): the loosest mesh shakes about 0.19 mm at the tip,
# past the 1 um lever indicator's 0.14 mm range (gauges.dti, owner
# 2026-11-17). The ceiling prints on the .001 grid, rounded up.
REDUCER_DIAL_STEP_MM = 0.001 * 25.4
REDUCER_SHAKE_MIN_MM = (
    _REDUCER_CIRCULAR_BACKLASH_MM[0] * min(_DISC_TIP_RADII_MM) / (disc.PITCH_DIA / 2.0)
)
REDUCER_SHAKE_MAX_MM = math.ceil(
    _REDUCER_CIRCULAR_BACKLASH_MM[1] * max(_DISC_TIP_RADII_MM) / (disc.PITCH_DIA / 2.0)
    / REDUCER_DIAL_STEP_MM - 1e-9
) * REDUCER_DIAL_STEP_MM
if not REDUCER_SHAKE_MIN_MM > 0.0:
    raise AssertionError("the reducer's tightest mesh binds when pressed together")
# The acceptance: any shake the needle shows, under the ceiling.
REDUCER_BACKLASH_DIAL_TEXT = (
    f"(THE NEEDLE MOVES), {steps.inch_max_text(REDUCER_SHAKE_MAX_MM, 3)}"
)
# The disc is read at stations round one turn: 45 degrees apart sample its
# once-a-turn tooth-space runout within cos 22.5 (92 %) of its peak. Each
# move turns the 15T 1.25 turns, so it is read at four phases 90 degrees
# apart, within cos 45 (71 %) of its own peak: the unread part of its .001
# eccentricity moves the backlash under .0003, less than a division.
REDUCER_DIAL_STATIONS = 8


def reducer_dial_check(held: str) -> str:
    """The reducer's indicator acceptance, ``held`` naming what the fitter
    holds still (the bare shaft at the trial, the knob on the machine)."""
    return (
        f"CHECK: {held} PRESSED LIGHTLY TOWARD THE DISC AND HELD, THE DISC "
        "PRESSED LIGHTLY TOWARD IT AND ROCKED BY HAND SHAKES "
        f"{REDUCER_BACKLASH_DIAL_TEXT} ON A DIAL INDICATOR ON A MAGNETIC BASE, ITS PLUNGER TANGENT "
        "ON THE FLANK, AT THE TIP, OF THE DISC TOOTH IN MESH, "
        f"AT {REDUCER_DIAL_STATIONS} PLACES "
        f"{360 // REDUCER_DIAL_STATIONS}\u00b0 APART ROUND THE DISC "
        f"{row_cite('reducer-shake')}."
    )


# The platen's screw stations (platen_spec): its front counterbores take the
# guide screws, its through-taps the clip screws.
GUIDE_SCREWS = len(platen.GUIDE_HOLE_X) * len(platen.GUIDE_HOLE_Y)
CLIP_SCREWS = len(platen.SOCKET_XY)
# The rack screws, one in each of the feed rack's taps.
RACK_SCREWS = PLATEN_QUANTITIES[explode.RACK_SCREW]
# Each guide's row of taps along its length: the platen-screw taps, tapped to
# MHA-PD-11's print on the top guide (owner ruling 2026-11-08 (Pedro), #2144
# item 2.3: the screws float in MHA-PD-02's holes, so nothing is spotted
# through the platen), alternate with the 4 lock taps, so the lock taps are
# the 2nd, 4th, 6th and 8th from either end (build_pd_platen_guide HOLE_X and
# SCREW_STATION_X; the test checks the order). MHA-PD-27 keeps the same
# stations. The steps count them in plain words: the A1-A9 tags live only on
# MHA-PD-11 (machinist review round 4, rule 22).
GUIDE_TAPS_IN_ROW = 9
# The bottom guide's platen-screw taps follow the rack's crest set, so they
# are spotted through MHA-PD-02's lower row (delegated ruling 2026-11-14
# (Main), pending owner confirmation; owner review #2144, #2410; precedent
# R9-9) with the largest 64ths transfer punch that enters its holes
# (pd_platen_bottom_guide_spec books its float).
GUIDE_SPOT_PUNCH = Fraction(bottom_guide.PLATEN_SPOT_PUNCH_64THS, 64)


# The engaged-feed window, measured from the rack's -X cut end. Machine X is
# drawn on no sheet, so the end is named by a view: the crank stands on the
# drive's -X side, at the right of sheet 1's front view (#3106, rule 26: the
# earlier "CRANK-SIDE CUT END" was a private convention; machinist review
# before that: "-X CUT END" could not be found on the part).
RACK_FEED_END_TEXT = "THE RACK'S RIGHT END IN SHEET 1'S FRONT VIEW"


def engaged_feed_window(domain: RackOperatingDomain) -> str:
    """The window the meshing step runs, in the title block's inches,
    rounded inward."""
    return steps.inch_window(
        domain.axis_from_left_end_limits_mm, OPERATING_LIMIT_PLACES + 1, " TO "
    )


def engaged_feed_text(domain: RackOperatingDomain) -> str:
    """The meshing step's engaged-feed window, with what it is measured on."""
    return (
        f"{engaged_feed_window(domain)} FROM {RACK_FEED_END_TEXT} TO THE "
        f"{_N['pd-transgear-pin']} PIN AXIS"
    )


# Lettered sub-steps under each fixed step number (7A, 7B, ...): the numbers
# stay the ones the arm, plate, collar, cup and purchased-part sheets cite.
# No I or O, which read as 1 and 0.
SUB_STEP_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ"


def sub_step(key: str, index: int) -> str:
    """The printed head of ``key``'s ``index``-th sub-step (0-based): ``9C``."""
    return f"{steps.step_number(key)}{SUB_STEP_LETTERS[index]}"


# Rule 22 (machinist review r3, r5): the BOM sheet states what the steps use
# up beyond the BOM rows: four more MHA-SH-VN-59, cut into the rack's transfer
# screws, the spare sprocket's connecting link (#2429), and the #4-40
# transfer screws, a bought shop tool, four in each guide's lock taps when
# the locks are struck; and (rule 23, #2425) the retaining compounds, one
# row group per grade naming every sub-step that uses it, with its cure:
# LOCTITE 638 bonds the MHA-PD-23 pin and the pivot spacer and, by DETAIL
# H's bond note, a plate dowel that slides in by hand (a latch dowel that
# slides in renews the arm, step 10; a collar dowel or pin, the collar,
# step 20);
# LOCTITE 641 bonds the knob cup.
LOCK_TRANSFER_SCREWS = 4 * 2
# The sub-steps that send a hand-slid dowel or pin to DETAIL H's bond note.
BOND_NOTE_SUB_STEPS = (("arm-plate-fitted", 6),)
LOCTITE_638_SUB_STEPS = tuple(
    sorted(
        (
            ("pin-pressed", PIN_BOND_SUB_STEP),
            ("hanger-pivoted", PIVOT_SPACER_BOND_SUB_STEP),
            *BOND_NOTE_SUB_STEPS,
        ),
        key=lambda row: (steps.step_number(row[0]), row[1]),
    )
)
_LOCTITE_638_HEADS = [sub_step(key, index) for key, index in LOCTITE_638_SUB_STEPS]
BOM_EXPENDABLES_NOTE = (
    f"ALSO ORDER {RACK_SCREWS} MORE {BOM_PART_NUMBERS[explode.RACK_SCREW]}\n"
    f"(ITEM {SHARED_NUMBER_ITEMS[explode.RACK_SCREW]}): "
    f"{sub_step('rack-screwed', 0)}-{sub_step('rack-screwed', 2)} MAKE THEM TRANSFER\n"
    f"SCREWS, AND 1 MORE {BOM_PART_NUMBERS['pd-vn-chain-connecting-link']} TO\n"
    f"CLOSE THE SPARE'S LOOP. {sub_step('platen-hung', 0)} USES {LOCK_TRANSFER_SCREWS}\n"
    "#4-40 TRANSFER SCREWS, A SHOP TOOL.\n"
    f"LOCTITE 638 AT {', '.join(_LOCTITE_638_HEADS)};\n"
    f"CURE {PIN_BOND_CURE_H} H.\n"
    f"LOCTITE 641 AT {sub_step('knob-stack-fitted', KNOB_CUP_BOND_SUB_STEP)}; "
    f"CURE {KNOB_CUP_BOND_CURE_H} H."
)
BOM_SHEET_CAPTION = (
    f"{BOM_REFERENCE_CAPTION}\n{BOM_CHAIN_ORDER_NOTE}\n{BOM_EXPENDABLES_NOTE}"
)


# The #4-40 taps spotted through a mating part at assembly: the tap drill
# the shop's chart names for the thread.
TAP_4_40_DRILL = "#43"
if abs(TAP_DRILL_MM["#4-40"] - NUMBER_DRILL_MM[TAP_4_40_DRILL]) > 1e-9:
    raise AssertionError("the #4-40 tap drill is not #43")
TAP_4_40_DRILL_TEXT = (
    f"{TAP_4_40_DRILL} (\u00d8{steps.inch_text(NUMBER_DRILL_MM[TAP_4_40_DRILL], 3)})"
)
# The arm's #8-32 plate taps, spotted through MHA-PD-19's clearance holes
# with a drill of the holes' own size (a #1, .228), then tapped from the
# chart's drill; the mouths take the title block's edge break.
TAP_8_32_DRILL = "#29"
if abs(TAP_DRILL_MM["#8-32"] - NUMBER_DRILL_MM[TAP_8_32_DRILL]) > 1e-9:
    raise AssertionError("the #8-32 tap drill is not #29")
TAP_8_32_DRILL_TEXT = (
    f"{TAP_8_32_DRILL} (\u00d8{steps.inch_text(NUMBER_DRILL_MM[TAP_8_32_DRILL], 3)})"
)
# The disc's #0-80 taps, spotted through the hub flange: the chart's drill.
TAP_0_80_DRILL = "3/64"
if abs(TAP_DRILL_MM["#0-80"] - 25.4 * 3.0 / 64.0) > 1e-3:
    raise AssertionError("the #0-80 tap drill is not 3/64")
TAP_0_80_DRILL_TEXT = (
    f"{TAP_0_80_DRILL} (\u00d8{steps.inch_text(TAP_DRILL_MM['#0-80'], 3)})"
)
# The frame parts the bar is clamped to and set from (MHA-FR-03's four tubes
# are the columns; MHA-FR-01 carries the base deck).
FRAME_COLUMN = str(_config.parts("fr-tube-frame")["number"])
FRAME_BASE = str(_config.parts("fr-harmonic-base")["number"])
# The drive-train crankshaft the chain fit-up pulls forward (rule 4: named by
# its drawing number; machinist review round 4).
CRANKSHAFT = str(_config.parts("dt-crankshaft")["number"])


def sprocket_name(configuration: str, *, numbered: bool = True) -> str:
    """Rule 26 (machinist review round 8): a MHA-PD-09 sprocket by its plain
    name, its tooth count from the configuration, never the bare code."""
    teeth = sprocket.configuration_teeth(configuration)
    if numbered:
        return f"{teeth}-TOOTH {_N['pd-transgear-removable']} SPROCKET"
    return f"{teeth}-TOOTH SPROCKET"


def _press_remedy(
    item: str, receiver: str, restart_key: str, *, or_condition: str = ""
) -> str:
    """Rule 23: a press whose part slides in by hand is a slip fit; the hole
    is oversize, so the receiving part is remade and the build repeated.
    ``or_condition`` names a second failure with the same remedy."""
    condition = "SLIDES IN BY HAND" + (f" OR {or_condition}" if or_condition else "")
    return (
        f"IF THE {item} {condition}, MAKE A NEW {receiver} AND REPEAT FROM "
        f"STEP {steps.step_number(restart_key)}."
    )


ARM_PLATE_SCREW_HOLE_TEXT = (
    f"{len(plate_geometry.SCREW_HOLES)}X "
    f"\u00d8{steps.inch_text(plate_geometry.SCREW_HOLE_DIA, 3)}"
)
ARM_PLATE_SPOT_DRILL_TEXT = (
    f"#1 (\u00d8{steps.inch_text(plate_geometry.SCREW_HOLE_DIA, 3)})"
)
# The located step's pilots: a #32 drill (owned 115-piece index) under the
# .1240 press ream leaves stock for both reams (machinist review round 8: the
# step named no size or place; 1/8 dowels, fit audit 2026-11-23).
PLATE_DOWEL_PILOT_DIA_MM = 2.9464  # #32 (.116)
if PLATE_DOWEL_PILOT_DIA_MM >= min(plate_locating_interface.PRESS_HOLE_LIMITS_MM) - 0.1:
    raise AssertionError("the dowel pilots must leave ream stock")
PLATE_DOWEL_PILOT_TEXT = f"#32 (\u00d8{steps.inch_text(PLATE_DOWEL_PILOT_DIA_MM, 3)})"
# MHA-PD-12's holes are struck through the MHA-PD-11 taps with the lock placed
# by hand; each mark is checked from the lock's edges to the hole locations'
# printed .XXX band less the transfer's own .001 (the screw point and the
# drill on its mark), so the drilled holes stay inside the band the lock's
# walls are judged at (FoPdFab1's per-joint ruling; pending owner
# confirmation, owner review #2144).
GUIDE_LOCK_TRANSFER_MM = 0.0254
GUIDE_LOCK_MARK_BAND_MM = max(
    abs(deviation)
    for xy in guide_lock.HOLE_XY
    for value in xy
    for deviation in printed_deviations(
        value, guide_lock.HOLE_LOCATION_PLACES, unit=guide_lock.UNIT
    )
) - GUIDE_LOCK_TRANSFER_MM


def _mark_window(location_mm: float) -> str:
    """A struck guide-lock mark's accepted window about its drawn place."""
    return steps.inch_window(
        (location_mm - GUIDE_LOCK_MARK_BAND_MM, location_mm + GUIDE_LOCK_MARK_BAND_MM),
        3,
        " TO ",
    )


# --- rule 22: the values the setting table and the steps share ---------------
LOCK_GAP_WINDOW = steps.inch_window(platen_guide.LOCK_GAP_FIT, 3, " TO ")
KNOB_END_FLOAT_WINDOW = steps.inch_window(KNOB_END_FLOAT_RANGE, 3, " TO ")
REDUCER_CLOCK_TEXT = steps.inch_text(
    steps.inch_floor_mm(quality.reducer_setup_clock_deviation_mm(), 3), 3
)
# The tooth-space runout grade is the .002 inch step (F3).
DISC_TIR_TEXT = steps.inch_text(
    steps.inch_floor_mm(disc.TOOTH_SPACE_RUNOUT_TIR_MM, 3), 3
)
# The disc is centred on its O.D., cut on the same arbor as its teeth, and
# its tooth-space runout is read in 12 spaces about evenly round it: any
# evenly spaced sample catches a once-a-turn runout (owner rulings
# 2026-11-20 and 2026-11-21 (Pedro), #2665). The sample is MHA-PD-06's own
# control's, so the two sheets read the same spaces.
DISC_TIR_SAMPLE_SPACES = disc.TOOTH_SPACE_SAMPLE_SPACES
DISC_TIR_SAMPLE_STRIDES = disc.TOOTH_SPACE_SAMPLE_STRIDES
# The setting table's rows, in step order; each step cites its row by number.
SETTING_ROW_KEYS = (
    "bar-top",
    "lock-mark-edge",
    "lock-mark-left",
    "lock-mark-right",
    "lock-gap",
    "disc-tir",
    "bush-seated",
    "bush-reamed",
    "reducer-shake",
    "trial-move",
    "plate-screw-tips",
    "pivot-tip",
    "disc-screw-tips",
    "collar-pilot",
    "cup-set",
    "engaged-feed",
    "crest-level",
    "tooth-centred",
    "offset-set",
    "offset-accept",
    "stud-cut",
    "collar-disc-air",
    "knob-end-float",
)
SETTING_ROW = {key: index for index, key in enumerate(SETTING_ROW_KEYS, start=1)}


def row_cite(*keys: str) -> str:
    """A step's pointer to its setting-table rows: ``(ROW 5, SHEET 13)``."""
    rows = sorted(SETTING_ROW[key] for key in keys)
    if rows != list(range(rows[0], rows[-1] + 1)):
        raise AssertionError(f"rows {rows} are not one run")
    numbers = f"ROW {rows[0]}" if len(rows) == 1 else f"ROWS {rows[0]}-{rows[-1]}"
    return f"({numbers}, SHEET {SHEET_NAMES.index(SETTING_TABLE_SHEET) + 1})"


def detail_cite(key: str) -> str:
    """A step's pointer to the setting detail that dimensions it."""
    detail = setting_details.DETAILS_BY_STEP[key]
    return f"({detail.view_name}, SHEET {SHEET_NAMES.index(SETTING_DETAIL_SHEET) + 1})"


def _step_text(
    *, operating_domain: RackOperatingDomain
) -> dict[str, tuple[str, ...]]:
    """Each step's sub-steps, one action or one check each."""
    n = _N
    # The windows DETAILS L and F print as limits: the part specs' press
    # windows on the .001 grid, so step and detail read alike.
    pin_window = steps.inch_window(setting_details.LATCH_PROUD_BAND, 3, " TO ")
    drive_window = steps.inch_window(setting_details.DRIVE_PIN_PROUD_BAND, 3, " TO ")
    knob_window = KNOB_END_FLOAT_WINDOW
    # #2425: the MHA-PD-28 bush pressed in the plate and reamed (pin-pressed's
    # last sub-steps, after the pin's bond sub-steps); a plate or bush
    # renewed later is made again by them.
    bush = n["pd-transgear-knob-bush"]
    # A leaf of the shop's set, the coarsest (in .001 steps) that still
    # closes the collar-to-disc air (pd_transgear_knob_bush_geometry).
    bush_seat_feeler = steps.inch_text(knob_bush.SHOULDER_SEAT_GAP_MAX, 3)
    # The bore prints the reamer's size and no band; the journal is turned
    # to it (drawing-guidelines rule 4, form 2).
    bush_ream = steps.inch_text(knob_bush.BORE_DIA, 4)
    bush_made = f"{sub_step('pin-pressed', 9)}-{sub_step('pin-pressed', 14)}"
    lock_gap = LOCK_GAP_WINDOW
    lock_gap_min, lock_gap_max = lock_gap.split(" TO ")
    # R9-47: the gap is the rail's depth less the bar's, so facing the rail's
    # back under a lock closes it. As made it is always over the window
    # (build_pd_platen_guide asserts it): each over lock is faced by its
    # reading less the window's middle, and only an over-faced rail (under
    # the window) is replaced.
    lock_gap_target = steps.inch_text(sum(platen_guide.LOCK_GAP_FIT) / 2.0, 3)
    after_lock_seats = steps.SEQUENCE[steps.SEQUENCE.index("lock-seats-faced") + 1]
    teeth = KNOB_PINION
    knob = sprocket_name(sprocket.KNOB_CONFIG)
    crank = sprocket_name(sprocket.CRANK_CONFIG)
    knob_short = sprocket_name(sprocket.KNOB_CONFIG, numbered=False)
    crank_short = sprocket_name(sprocket.CRANK_CONFIG, numbered=False)
    # The knob wheel floats collar.KNOB_FLOAT_RANGE forward of its seat (the
    # collar's front face) under the thumbnut; the setting and its acceptance
    # read it held back on that seat (27E; 29A refits as 27D-27F), the pose
    # ACCEPTED_CHAIN_OFFSET_IN_SERVICE assumes.
    float_sheet = SHEET_NAMES.index(CLUSTER_FLOAT_SHEET) + 1
    pose = steps.step_number("fitup-pose-set")
    clock = REDUCER_CLOCK_TEXT
    tir = DISC_TIR_TEXT

    def s(key: str, index: int) -> str:
        return sub_step(key, index)

    shim_target = steps.inch_text(sum(cluster_fit.RING_FLOAT_RANGE) / 2.0, 3)
    shim_thickness = steps.inch_text(cluster_fit.SHIM.THICKNESS, 3)
    if cluster_fit.RING_FLOAT_RANGE[1] - cluster_fit.RING_FLOAT_RANGE[0] < (
        cluster_fit.SHIM.THICKNESS
    ):
        raise AssertionError("a shim count to the nearest shim can miss DETAIL E")
    # The bare stack's ring gap, widened outward to the .001 grid: its floor
    # still holds the window's floor (never under) and the most shims, at
    # their thinnest, still bring its top into the window.
    _bare_in = (
        math.floor(cluster_fit.UNSHIMMED_FLOAT_RANGE[0] / 25.4 * 1000.0 + 1e-9) / 1000.0,
        math.ceil(cluster_fit.UNSHIMMED_FLOAT_RANGE[1] / 25.4 * 1000.0 - 1e-9) / 1000.0,
    )
    bare_gap = " TO ".join(steps.inch_text(limit * 25.4, 3) for limit in _bare_in)
    # Remedies that run back through joints made permanent by then (9G-9K
    # tapped disc) release and renew named parts. Owner ruling 2026-11-08
    # (auto-selected after timeout), pending owner confirmation (#2144):
    # renew, 31E's cluster re-faced without renewal. The knob cup's LOCTITE
    # 641 bond is the removable grade and its screw comes out (#2425).
    # The pivot screw is unlocked (owner ruling U-MHA-PD-VN-57-no-lock,
    # #1194); it comes out with the spacer bonded on its shoulder, and a
    # rebuild renews both.
    knob_stack_off = (
        f"REMOVE THE {n['pd-transgear-thumbnut']} THUMBNUT, {knob_short} AND "
        "COLLAR."
    )
    # Each a pair of sub-steps, one action each (machinist review, #2417).
    # The cured LOCTITE 641 lets go only hot (rule 23: about 250 °C); the bush
    # runs in oil, so the heat is kept off it (codjiflo review, #2425).  The
    # screw's removal is its own sub-step, and the strips at 28 and 33 cite
    # the pair in step 22 (machinist review r10 of #2425: one action each).
    knob_cup_off = (
        f"UNSCREW THE {n['pd-vn-transgear-knob-cup-screw']} SCREW.",
        f"PULL THE {n['pd-transgear-knob-cup']} CUP OFF THE JOURNAL HOT, ABOUT "
        f"250\u00b0C, THE HEAT KEPT OFF THE {bush} BUSH'S OIL.",
    )
    knob_cup_off_cited = (
        f"TAKE THE {n['pd-transgear-knob-cup']} CUP OFF AS "
        f"{s('knob-stack-fitted', 14)}-{s('knob-stack-fitted', 15)}."
    )
    knob_shaft_out = f"DRAW THE {n['pd-transgear-knob-shaft']} SHAFT OUT FORWARD."
    # The bonded spacer holds the arm captive on the shoulder, so the arm
    # comes off the bar with the screw, not off the screw (Codjiflo r2 on
    # #3487).
    pivot_unscrewed = (
        f"UNSCREW THE {n['pd-vn-transgear-pivot-screw']} SCREW.",
        "LIFT IT OUT, THE ARM AND THE SPACER ON IT.",
    )
    # The pivot's reseat (15R-15U: unscrew, lift off, flush, clean; then
    # 15L-15P: reseat, re-check) is written once and done from 33 (the
    # step-line budget); a repeat failure there rebuilds the arm as
    # 28R-28V, whose step 15 carries the full renewal and inspection. 28's
    # rebuild takes only 15R-15S.
    pivot_remedied = (
        f"{s('hanger-pivoted', 15)}-{s('hanger-pivoted', 18)} AND "
        f"{s('hanger-pivoted', 10)}-{s('hanger-pivoted', 13)}"
    )
    # #2409: the hub is keyed to the sleeve's flat by its MHA-PD-VN-69 pin,
    # pressed along a chord of the hub to its ream's stop before the hub is
    # fitted, its side lying over the flat. The flat runs out at the nose, so
    # a remedy slides hub and disc off and back on with the pin riding it;
    # the pin stays in the hub, on any sleeve.
    hub_pin = n["pd-vn-transgear-hub-key-pin"]
    hub_slid_off = (
        f"SLIDE THE HUB AND DISC OFF THE {n['pd-transgear-feed-pinion']} NOSE AS ONE, "
        f"THE {hub_pin} PIN RIDING THE FLAT."
    )
    # #3106: a feed sleeve found outside after the cluster is hung is renewed
    # as 12X renews it, from the stripped cluster: the collar slid on at
    # 22 comes off first, the hub's oil hole is drilled on into the new
    # sleeve (step 17) and the collar goes back on (22U; the bonded cup
    # stays, #2425). Written once at 24 and pointed to from 26 (the
    # step-line budget), one action per sub-step (machinist review of
    # 592b20079f).
    sleeve_renewed = (
        f"FOR A {n['pd-transgear-feed-pinion']} FOUND OUTSIDE, SLIDE THE COLLAR OFF.",
        f"FOR IT, STRIP THE CLUSTER ({s('disc-cluster-hung', 4)} BACK TO "
        f"{s('disc-cluster-hung', 1)}), KEEPING ITS SHIMS.",
        f"FOR IT, DO THE SLIDE-OFF AND THE REPEATS IN {s('arm-plate-located', 21)} "
        "ON A NEW ONE.",
        f"FOR IT, REPEAT STEPS {steps.step_number('oil-hole-drilled')}-"
        f"{steps.step_number('disc-cluster-shimmed')} AND {s('knob-stack-fitted', 18)}, "
        f"THEN FROM {s('hanger-meshed', 0)}.",
    )

    return {
        "bar-clamped": (
            f"CLOSE A {n['sh-column-clamp-front']} FRONT ARC AND A "
            f"{n['sh-column-clamp-back']} BACK ARC ROUND EACH {FRAME_COLUMN} COLUMN "
            f"ON THE {n['pd-support-bar']} BAR WITH THE {n['sh-vn-clamp-screw']} "
            "SCREWS FROM THE BAR FRONT, ALL FOUR SNUG.",
            f"SET THE BAR TOP {steps.BAR_TOP_ABOVE_DECK_TEXT} ABOVE THE {FRAME_BASE} "
            f"BASE DECK AT BOTH COLUMNS BY HEIGHT GAUGE ON THE DECK {row_cite('bar-top')}.",
            # Rule 19 fit-up for the slotted pair (owner ruling 2026-10-15,
            # #1471 option A): the round pair locates.
            "TIGHTEN THE ROUND-HOLE PAIR OF SCREWS.",
            "TIGHTEN THE SLOTTED PAIR OF SCREWS.",
            "CHECK: UNDER FIRM HAND PRESSURE THE BAR SLIPS ON NEITHER COLUMN.",
            "IF IT SLIPS, SLACKEN ALL FOUR SCREWS AND REPEAT "
            f"{s('bar-clamped', 1)}-{s('bar-clamped', 3)}.",
        ),
        # Owner rulings 2026-11-13 (#2410): the bare purchased strip, screwed
        # by its flat top to MHA-PD-27's underside with stock RackScrews from
        # the guide's top; the guide's four holes are struck from the strip's
        # taps (delegated ruling 2026-11-14 (Main)), the strip's front face
        # set behind the guide's front face against a rule.
        # One action per sub-step (rule 22; machinist review r3, r5). The
        # transfer screws keep a grip for the pliers (codjiflo P2 on 19ef870):
        # run in by fingers short of the tap's end, never bottomed against
        # the tooth-root wall (RV-03), and the strip pressed square on the
        # four points, which lie on its centreline and so stay on the roll
        # axis of any tilt.
        "rack-screwed": (
            # The BOM sheet's expendables note gives these spares' item.
            f"SCREW A SPARE {BOM_PART_NUMBERS[explode.RACK_SCREW]} BY FINGERS INTO "
            "EACH OF THE "
            f"{n['pd-feed-rack']} RACK'S {RACK_SCREWS} TAPS UNTIL IT STOPS TURNING "
            "FREELY, NOT BOTTOMED.",
            "CUT EACH SCREW OFF, LEAVING A PLIERS GRIP PROUD OF THE FLAT TOP.",
            "FILE EACH CUT END TO A POINT: THESE ARE THE TRANSFER SCREWS.",
            f"CLAMP THE RACK, TEETH DOWN, PRESSED SQUARE ON ITS {RACK_SCREWS} "
            f"POINTS, TO THE {n['pd-platen-bottom-guide']} GUIDE'S UNDERSIDE, ENDS "
            f"FLUSH, ITS FRONT FACE {steps.RACK_FRONT_SET_TEXT} BEHIND THE GUIDE'S "
            f"FRONT BY RULE {detail_cite('rack-screwed')}.",
            f"SQUEEZE THE CLAMPS TO STRIKE THE {RACK_SCREWS} MARKS.",
            "UNCLAMP THE RACK.",
            "UNSCREW THE TRANSFER SCREWS WITH PLIERS.",
            f"DRILL THE GUIDE AT EACH MARK PER {n['pd-platen-bottom-guide']}.",
            f"COUNTERBORE EACH HOLE PER {n['pd-platen-bottom-guide']}.",
            f"SCREW THE RACK ON WITH THE {RACK_SCREWS} {n[explode.RACK_SCREW]} "
            "SCREWS FROM THE GUIDE TOP, ENDS FLUSH, ITS FRONT FACE "
            f"{steps.RACK_FRONT_SET_TEXT} BEHIND THE GUIDE'S, SET AGAINST A RULE "
            f"{detail_cite('rack-screwed')}.",
            "CHECK: EVERY SCREW ENTERS ITS TAP BY HAND.",
            f"IF EVERY SCREW ENTERS, SKIP {s('rack-screwed', 12)}-{s('rack-screwed', 14)}.",
            "REMOVE THE RACK SCREWS AND THE RACK.",
            f"SCREW THE TRANSFER SCREWS BACK INTO THE RACK'S TAPS PER {s('rack-screwed', 0)}.",
            f"MAKE A NEW {n['pd-platen-bottom-guide']} GUIDE AND REPEAT FROM "
            f"{s('rack-screwed', 3)}.",
            f"TIGHTEN THE {RACK_SCREWS} RACK SCREWS.",
            "CHECK: PUSHED FIRMLY BY HAND ALONG AND ACROSS ITS TEETH, THE RACK "
            "DOES NOT SHIFT ON THE GUIDE.",
            f"IF IT SHIFTS, REPEAT {s('rack-screwed', 9)}-{s('rack-screwed', 16)} "
            f"WITH NEW {n[explode.RACK_SCREW]}.",
        ),
        # The top guide's taps are tapped to MHA-PD-11's print; the bottom
        # guide's are spotted through the platen with the rack's crests set
        # (GUIDE_SPOT_PUNCH), then it is set again at the same crests.
        "guides-screwed": (
            f"CLAMP THE {n['pd-platen-guide']} TOP GUIDE TO THE {n['pd-platen']} "
            "PLATEN'S BACK, ENDS FLUSH WITH THE PLATEN ENDS, ON THE UPPER ROW OF "
            f"\u00d8{steps.inch_text(platen.GUIDE_HOLE_DIA, 3)} PLATEN HOLES.",
            f"CLAMP THE {n['pd-platen-bottom-guide']} BOTTOM GUIDE, RACK ON, TO THE "
            "PLATEN BACK, ENDS FLUSH, THE RACK'S CRESTS "
            f"{steps.RACK_CREST_TEXT} BELOW THE PLATEN'S BOTTOM EDGE AT BOTH ENDS "
            f"BY HEIGHT GAUGE {detail_cite('guides-screwed')}.",
            "SPOT THE BOTTOM GUIDE THROUGH THE LOWER ROW OF PLATEN HOLES WITH A "
            f"{GUIDE_SPOT_PUNCH.numerator}/{GUIDE_SPOT_PUNCH.denominator} TRANSFER "
            "PUNCH.",
            "UNCLAMP THE BOTTOM GUIDE.",
            f"DRILL EACH SPOT PER {n['pd-platen-bottom-guide']}.",
            f"TAP EACH HOLE PER {n['pd-platen-bottom-guide']}.",
            f"CLAMP THE BOTTOM GUIDE AGAIN PER {s('guides-screwed', 1)}.",
            f"SCREW THE GUIDES ON WITH {GUIDE_SCREWS} "
            f"{n['sh-vn-brass-fillister-screw']} SCREWS FROM THE PLATEN FRONT, "
            "HEADS IN THE COUNTERBORES.",
            "CHECK: EVERY SCREW ENTERS BY HAND.",
            "IF ONE BINDS, RUN A #4-40 TAP THROUGH ITS GUIDE TAP AGAIN.",
            f"TIGHTEN ALL {GUIDE_SCREWS} GUIDE SCREWS.",
            "UNCLAMP THE GUIDES.",
            "CHECK: PUSHED FIRMLY BY HAND ALONG AND ACROSS, NEITHER GUIDE MOVES ON "
            "THE PLATEN.",
            f"IF THE TOP GUIDE MOVES, MAKE A NEW {n['pd-platen-guide']} GUIDE AND "
            f"REPEAT {s('guides-screwed', 0)} AND {s('guides-screwed', 7)}-"
            f"{s('guides-screwed', 12)} FOR IT.",
            # One action and its repeat, as the top guide's (machinist review
            # of 70917f0316: making the guide and moving the rack read as two).
            "IF THE BOTTOM GUIDE MOVES, MOVE THE RACK TO A NEW "
            f"{n['pd-platen-bottom-guide']} GUIDE PER STEP "
            f"{steps.step_number('rack-screwed')} AND REPEAT "
            f"{s('guides-screwed', 1)}-{s('guides-screwed', 12)} FOR IT.",
        ),
        "clips-fitted": (
            f"SCREW THE {n['pd-platen-clip']} CLIPS TO THE PLATEN FRONT WITH "
            f"{CLIP_SCREWS} {n['pd-vn-platen-clip-screw']} SCREWS, SPRING RAILS "
            "INBOARD.",
            f"TIGHTEN ALL {CLIP_SCREWS} CLIP SCREWS.",
            "CHECK: PUSHED FIRMLY BY HAND, NEITHER CLIP MOVES ON THE PLATEN.",
            "IF ONE MOVES, FIT NEW SCREWS TO IT AND REPEAT "
            f"{s('clips-fitted', 1)}-{s('clips-fitted', 2)}.",
            f"LAY THE {n['pd-platen-paper']} PAPER BETWEEN THE CLIPS.",
        ),
        "platen-hung": (
            "SCREW A #4-40 TRANSFER SCREW INTO THE 2ND, 4TH, 6TH AND 8TH OF EACH "
            f"GUIDE'S {GUIDE_TAPS_IN_ROW} TAPS, COUNTED FROM EITHER END.",
            f"LAY A {n['pd-guide-lock']} LOCK OVER EACH TAP PAIR (2ND AND 4TH, 6TH "
            "AND 8TH), ITS GUIDE-SIDE EDGE TOWARD THE GUIDE.",
            "STRIKE EACH LOCK TO MARK BOTH ITS HOLES.",
            f"CHECK WITH CALIPERS: EACH MARK {_mark_window(guide_lock.HOLE_Y)} FROM "
            f"THE LOCK'S GUIDE-SIDE EDGE {row_cite('lock-mark-edge')}.",
            "CHECK WITH CALIPERS: THE LEFT MARK "
            f"{_mark_window(guide_lock.HOLE_XY[0][0])} AND THE RIGHT MARK "
            f"{_mark_window(guide_lock.HOLE_XY[1][0])} FROM THE LOCK'S LEFT EDGE, "
            f"LEFT AND RIGHT AS {n['pd-guide-lock']}'S FRONT VIEW SHOWS "
            f"{row_cite('lock-mark-left', 'lock-mark-right')}.",
            "IF A MARK IS OUTSIDE, STONE THE MARKS OFF AND REPEAT "
            f"{s('platen-hung', 1)}-{s('platen-hung', 4)}.",
            "DRILL EACH LOCK "
            f"\u00d8{steps.inch_text(blind_cut_dia_mm(guide_lock.HOLE_SPEC), 3)} THRU "
            "AT ITS MARKS.",
            "MATCH-MARK EACH LOCK TO ITS TAP PAIR.",
            "REMOVE THE TRANSFER SCREWS.",
            "TRIAL-HANG THE PLATEN ON THE BAR, THE TOP GUIDE ON THE BAR TOP.",
            "FIT EACH LOCK TO ITS TAP PAIR BEHIND THE BAR WITH 2 "
            f"{n['pd-vn-guide-lock-screw']} SCREWS, LOOSE.",
        ),
        "guide-locks-set": (
            "SNUG BOTH SCREWS OF EACH LOCK.",
            "PUSH EACH LOCK AT ITS MIDDLE AWAY FROM THE BAR UNTIL ITS HOLES BEAR "
            "ON THE SCREWS.",
            "TIGHTEN THE LOCK SCREWS.",
            # Machinist review r8 (PD-00 on 5be0be4): every screwed joint
            # gets a holding check (2M, 3N, 4C), the locks too.
            "CHECK: PUSHED FIRMLY BY HAND, NO LOCK MOVES ON ITS GUIDE.",
            f"IF ONE MOVES, FIT NEW {n['pd-vn-guide-lock-screw']} SCREWS AND REPEAT "
            f"{s('guide-locks-set', 0)}-{s('guide-locks-set', 3)}.",
        ),
        # The read branches three ways (machinist review of 492f8b4a70: the
        # in-window case had no exit and the platen lift read as
        # unconditional); a faced rail goes back to the read.
        "lock-seats-faced": (
            "WITH THE LOCK SCREWS TIGHT, READ THE GAP BETWEEN EACH LOCK'S FRONT "
            "FACE AND THE BAR'S BACK FACE WITH FEELERS.",
            f"IF EVERY GAP IS {lock_gap} {row_cite('lock-gap')}, GO TO STEP "
            f"{steps.step_number(after_lock_seats)}.",
            f"IF A GAP IS UNDER {lock_gap_min}, REPLACE THAT GUIDE AND REPEAT FROM "
            f"STEP {steps.step_number('guides-screwed')} FOR THE "
            f"{n['pd-platen-guide']} GUIDE, FROM STEP "
            f"{steps.step_number('rack-screwed')} FOR THE "
            f"{n['pd-platen-bottom-guide']} GUIDE.",
            f"IF A GAP IS OVER {lock_gap_max}, REMOVE THE LOCKS.",
            "WITH THE LOCKS REMOVED, LIFT THE PLATEN OFF THE BAR.",
            "FACE THE GUIDE'S BACK FACE UNDER EACH LOCK THAT READ OVER "
            f"{lock_gap_max} BY ITS GAP LESS {lock_gap_target}.",
            f"REFIT PER {s('platen-hung', 9)}-{s('guide-locks-set', 3)}.",
            f"REPEAT FROM STEP {steps.step_number('lock-seats-faced')}.",
        ),
        # #3124: the arm's hole runs past the deepest insertion to a drill
        # point, so the proud is set as the dowel goes in, not by a floor;
        # the press is permanent (MHA-PD-18 RV-03), so an over-pressed dowel
        # stays in the arm it costs, and both are remade (Codjiflo #3127).
        # A dowel that slides into the .1240 ream by hand is a slip fit (rule
        # 23): the hole is reamed with the set reamer and the dowel is its
        # gauge, so its size is unknown and no bonded clearance can be
        # printed for it, and the arm does not yet carry DETAIL K's
        # jig-boring, the one place owner ruling 2026-11-20 (#2497) allows
        # compound; arm and dowel are remade, as the arm's traveler rejects
        # the arm when the dowel enters by hand (MHA-PD-18 note 3; Codjiflo
        # r2 on #3486: the bond salvage had no valid ruling).
        "latch-pin-pressed": (
            f"PRESS THE {n['pd-vn-transgear-latch-pin']} DOWEL, CHAMFERED END FIRST, "
            f"INTO THE {n['pd-transgear-arm']} ARM'S REAMED HOLE, {pin_window} PROUD, "
            f"CALIPER DEPTH ROD {detail_cite('latch-pin-pressed')}.",
            "IF THE DOWEL SLIDES IN BY HAND OR READS UNDER "
            f"{pin_window.split(' TO ')[0]}, MAKE A NEW {n['pd-transgear-arm']} ARM AND "
            f"{n['pd-vn-transgear-latch-pin']} DOWEL AND REPEAT FROM STEP "
            f"{steps.step_number('latch-pin-pressed')}.",
        ),
        # Owner ruling 2026-11-24, fit audit question 4: the one-diameter
        # MHA-PD-23 pin is a slip fit bonded in the arm's reamed hole (rule
        # 23's bond bullet: degrease, coat the pin, seat, keep the compound
        # off the running shank and the rear bushing's seat on the arm's
        # front face, cure clamped before anything loads it); nothing is
        # pressed, so the press remedy is gone.  One action per sub-step.
        # #2425 (owner ruling 2026-11-20): the MHA-PD-28 bush is pressed into
        # the plate from face A to its shoulder and its bore reamed through
        # after the press, before the plate is set on the arm, so the located
        # step indicates the finished knob bore. Last in this step, so the
        # arm-only remedies above it never meet a bushed plate.
        "pin-pressed": (
            f"DEGREASE THE {n['pd-transgear-pin']} PIN'S SHANK UNDER ITS HEAD AND THE "
            f"{n['pd-transgear-arm']} ARM'S REAMED HOLE.",
            f"COAT THE SHANK UNDER THE HEAD, NOT THE HOLE, WITH {PIN_BOND_COMPOUND}, "
            "AS FAR AS THE ARM IS THICK.",
            "PUSH THE PIN THROUGH THE HOLE FROM THE REAR, TURNING IT, UNTIL ITS HEAD "
            "SEATS ON THE ARM.",
            "WIPE ALL COMPOUND OFF THE SHANK IN FRONT OF THE ARM AND OFF THE ARM'S "
            "FRONT FACE.",
            # One action per sub-step (machinist review
            # 20261124T013305458Z, rule 22): the clamp, the cure, the pull
            # and the clean each stand alone.
            "CLAMP THE HEAD ON THE ARM'S REAR FACE.",
            f"LET THE BOND CURE {PIN_BOND_CURE_H} H BEFORE ANYTHING IS FITTED ON "
            "THE PIN.",
            "CHECK: PUSHED FIRMLY BY HAND AT ITS TIP, THE CURED PIN DOES NOT MOVE IN "
            "THE ARM.",
            "IF IT MOVES, PULL THE PIN.",
            "IF PULLED, CLEAN THE PIN AND THE HOLE AND REPEAT "
            f"{s('pin-pressed', 0)}-{s('pin-pressed', 6)}.",
            f"PRESS THE {bush} BUSH, STUB FIRST, INTO THE {n['pd-transgear-arm-plate']} "
            f"PLATE FROM ITS FRONT FACE (FACE A ON {n['pd-transgear-arm-plate']}) "
            "UNTIL ITS SHOULDER SEATS.",
            # The bush is turned to the plate's measured hole, so a slip fit
            # is an undersize bush, not a bad plate (codjiflo review, #2425).
            # One action per sub-step, the face named by its view and the
            # ream by its mate, fit and gauge (machinist review r10, #2425).
            f"IF IT SLIDES IN BY HAND, REPEAT {s('pin-pressed', 9)} WITH A NEW {bush} "
            "BUSH TURNED TO THE PLATE'S MEASURED HOLE.",
            f"CHECK: A {bush_seat_feeler} FEELER DOES NOT ENTER UNDER THE SHOULDER "
            f"{row_cite('bush-seated')}.",
            # A first failure is pressed home and checked again before the
            # pair is renewed (codjiflo review round 2, #2425).
            f"IF IT ENTERS, PRESS AGAIN TO THE SHOULDER AND REPEAT {s('pin-pressed', 11)}.",
            f"IF IT STILL ENTERS, REPEAT FROM {s('pin-pressed', 9)} WITH A NEW "
            f"{n['pd-transgear-arm-plate']} PLATE AND {bush} BUSH.",
            f"REAM THE BUSH'S BORE \u00d8{bush_ream} THRU, A RUNNING FIT ON THE "
            f"{n['pd-transgear-knob-shaft']} JOURNAL, WHICH IS TURNED TO IT "
            f"{row_cite('bush-reamed')}.",
        ),
        # #2417: the pin is already bonded (its shank, not its head, is S),
        # and the reducer is meshed on its real seats while the plate is
        # still clamped and undrilled; it is doweled only once it reads.
        # The plate overlaps the arm past the disc's tips only along its edge
        # nearest the pivot bore, so the clamps go there; the arm is clamped
        # to the table so that fitting and lifting the trial stack cannot
        # move the DRO's zero off S (codjiflo P2 on 27438d7), and the
        # parallels leave the knob shaft's rear end free below the plate.
        "arm-plate-located": (
            f"CLAMP THE {n['pd-transgear-arm-plate']} PLATE ON THE "
            f"{n['pd-transgear-arm']} ARM'S REAR FACE WITH TOOLMAKER'S CLAMPS, "
            "SCREWS OUT, THE CLAMPS ON THE PLATE'S EDGE NEAREST THE PIVOT BORE, "
            "WHERE THE DISC WILL NOT REACH.",
            "CLAMP THE ARM FRONT UP ON PARALLELS ON THE MILL TABLE, THE PIN HEAD, "
            f"THE PLATE AND ITS CLAMPS CLEAR, WITH ROOM UNDER THE {bush} BUSH FOR "
            f"THE {n['pd-transgear-knob-shaft']} SHAFT'S REAR END.",
            # #2432: a test indicator's contact cannot sweep the small pivot
            # bore squarely, so it sweeps a snug gauge pin standing in it.
            "WITH A TEST INDICATOR IN THE SPINDLE, INDICATE A SNUG GAUGE PIN IN "
            f"THE ARM'S PIVOT BORE AND THE {n['pd-transgear-pin']} PIN'S "
            "SHANK IN ITS PIN BORE S, AT THE HEIGHT THE DISC WILL RUN, TRUE ON ONE DRO "
            f"AXIS ({KNOB_SETTING_TRUE}).",
            # 12D and 12E can print on the sheet after DETAIL K's key: they
            # point to the key's sheet (review of run
            # 20261117T152142787Z-3d98e09383ba4ebea17fbf039b2b0697).
            f"ZERO THE DRO ON S (SHEET {SHEET_NAMES.index(KNOB_SETTING_SHEET) + 1}).",
            f"SET THE TABLE TO {KNOB_SETTING_VIEW_NAME}'S "
            f"(SHEET {SHEET_NAMES.index(KNOB_SETTING_SHEET) + 1}) ALONG AND ACROSS "
            "FROM S.",
            # The clamps are slackened here, so every return to 12F (12H's
            # re-tap, the trial move, a part's retrial) frees the plate first.
            f"SLACKEN THE CLAMPS AND TAP THE PLATE UNTIL KNOB BORE {KNOB_BORE_LETTER} "
            f"READS TRUE PER {s('arm-plate-located', 2)} "
            f"(SHEET {SHEET_NAMES.index(KNOB_SETTING_SHEET) + 1}).",
            "TIGHTEN THE CLAMPS.",
            # Named in full: the continued column on the next sheet has no
            # DETAIL K key (integration review, run 20261109T062834910Z).
            f"CHECK: RE-INDICATED, {bush} KNOB BORE "
            f"{KNOB_BORE_LETTER} IS STILL TRUE PER {s('arm-plate-located', 2)} "
            f"(SHEET {SHEET_NAMES.index(KNOB_SETTING_SHEET) + 1}).",
            f"IF NOT, REPEAT {s('arm-plate-located', 5)}-{s('arm-plate-located', 7)}.",
            # #2629 (machinist rule 22): the pass exit takes its own letter
            # within the step's 24-letter budget, so the trial stack goes on
            # in one sub-step, as the lift-off takes it off in one.
            f"TRIAL MESH: FIT THE {n['pd-transgear-rear-bushing']} BUSHING AND THE "
            f"{n['pd-transgear-feed-pinion']} SLEEVE, HUB AND DISC, {FEED_PINION} "
            "REARWARD, ON THE PIN.",
            f"PASS THE {n['pd-transgear-knob-shaft']} SHAFT THROUGH THE LOOSE "
            f"{n['pd-transgear-knob-thrust-ring']} RING INTO THE {bush} BUSH FROM "
            "THE FRONT, MESHING WITH THE DISC.",
            "CHECK: TURNED BY THE SHAFT, THE DISC RUNS ONE FULL TURN WITH NO TIGHT "
            "SPOT.",
            reducer_dial_check("SHAFT"),
            "LIFT OFF THE SHAFT, THE RING, THE CLUSTER AND THE BUSHING.",
            # The trial counts only if nothing moved under it: S still at the
            # DRO's zero and N still true at the table's setting, DETAIL K's
            # or as the trial move left it (codjiflo r2 on #3539: read
            # against DETAIL K alone, a moved plate failed here and undid the
            # move).  Pointed
            # back like 12H, with both bores named: the step can pack onto a
            # sheet without the DETAIL K key (machinist review on 0a4408f590).
            # The arm's number is left to 12C so the steps fit their sheets
            # (C1 restack).
            f"CHECK: RE-INDICATED PER {s('arm-plate-located', 2)} "
            f"(SHEET {SHEET_NAMES.index(KNOB_SETTING_SHEET) + 1}), "
            "PIN BORE S READS TRUE AT THE DRO'S ZERO AND "
            f"KNOB BORE {KNOB_BORE_LETTER} AT THE TABLE'S SETTING.",
            f"IF NOT, REPEAT FROM {s('arm-plate-located', 2)}.",
            # The trial may move the plate before a part is blamed: owner
            # ruling 2026-11-24, audit part 2 question C1, "Yes, the trial
            # may move the plate within those limits." (.001 away from S for
            # a tight spot, .001 toward S if the shake reads over .008; never
            # above +.002 nor below -.001 of DETAIL K). It retires the
            # delegated ruling of 2026-11-10 that the plate is not moved to
            # chase a reading. Each move is whole DRO counts on both axes,
            # derived so N, indicated TRUE, stays inside the limits
            # (pd_paper_drive_knob_setting_spec.TRIAL_MOVE_TOWARD_MM,
            # TRIAL_MOVE_AWAY_MM): from the mid-band aim no away move is
            # left, so a tight spot or no shake goes straight to the
            # inspection. A mesh that still reads outside the window with N
            # true is a part off its drawing: a gear or one of the two
            # running fits the window charges; only when all are inside is
            # the arm renewed (codjiflo P2 on 176fad0). The restart follows
            # the part (codjiflo P2 on ab2fdaf): a new plate is set to DETAIL
            # K again, a new disc or sleeve is centred again; one sub-step
            # per part (machinist review on 36242bf: one action per step).
            # A new disc, sleeve or shaft is tried with the table back at
            # DETAIL K's setting, not at a move made for the part it replaces
            # (codjiflo r2 on #3539), so each repeats from the table's
            # setting (the tap sub-step slackens the clamps first).
            f"IF {s('arm-plate-located', 11)} AND {s('arm-plate-located', 12)} "
            f"PASSED, GO TO STEP {steps.step_number('arm-plate-fitted')}.",
            (
                f"IF ONLY {s('arm-plate-located', 12)} FAILED, ON SHAKE OVER "
                f"{steps.inch_text(REDUCER_SHAKE_MAX_MM, 3)}, AT {KNOB_SETTING_VIEW_NAME}'S "
                f"SETTING, MOVE THE TABLE TOWARD S BY THE TRIAL MOVE "
                f"{row_cite('trial-move')}, THEN FROM {s('arm-plate-located', 5)}."
                if KNOB_TRIAL_AWAY_MOVE_TEXT is None
                # With the C2 floor gone, "no shake" fails the dial check
                # low and moves away from S, as a tight spot does.
                else f"IF {s('arm-plate-located', 11)} OR {s('arm-plate-located', 12)} "
                f"ALONE FAILED AT {KNOB_SETTING_VIEW_NAME}'S SETTING, MOVE THE TABLE "
                f"BY THE TRIAL MOVE {row_cite('trial-move')}, AWAY FROM S FOR A TIGHT "
                "SPOT OR NO SHAKE, "
                f"TOWARD S FOR SHAKE OVER {steps.inch_text(REDUCER_SHAKE_MAX_MM, 3)}, "
                f"THEN FROM {s('arm-plate-located', 5)}."
            ),
            f"IF NOT, INSPECT THE {n['pd-transgear-knob-shaft']} PINION, "
            f"{n['pd-rack-pinion']} DISC, {n['pd-transgear-knob-shaft']} JOURNAL AND "
            f"{bush} AND {n['pd-transgear-feed-pinion']} "
            "BORES TO THEIR SHEETS.",
            # The bush is pressed for good, so a bore found outside renews it
            # with its plate, made again as before (#2425).
            f"REPLACE A {bush} BUSH FOUND OUTSIDE WITH A NEW BUSH AND "
            f"{n['pd-transgear-arm-plate']} PLATE PER {bush_made} AND REPEAT FROM "
            f"{s('arm-plate-located', 0)}.",
            # #3106: the sub-steps by letter; 8A-8B press the hub's pin, which
            # stays in.
            "REPLACE A DISC FOUND OUTSIDE THROUGH "
            f"{s('disc-cluster-assembled', 2)}-{s('disc-taps-transferred', 17)} ON THE "
            f"SAME HUB, ITS {hub_pin} PIN RIDING THE FLAT, AND REPEAT FROM "
            f"{s('arm-plate-located', 4)}.",
            # The disc is screwed to the hub by then, so it is slackened before
            # it is centred again (codjiflo P3 on 593f4ee). One sub-step, as
            # the disc's (C1's move took the letter the slide-off had).
            f"REPLACE A {n['pd-transgear-feed-pinion']} FOUND OUTSIDE: SLIDE THE HUB "
            "AND DISC OFF IT AS ONE, THE PIN RIDING THE FLAT, THE DISC SCREWS "
            "SLACKENED, REPEAT "
            f"{s('disc-cluster-assembled', 3)}-{s('disc-cluster-assembled', 4)}, "
            f"{s('disc-taps-transferred', 0)}-"
            f"{s('disc-taps-transferred', 2)}, {s('disc-taps-transferred', 9)} AND "
            f"{s('disc-taps-transferred', 12)}-{s('disc-taps-transferred', 17)} ON A NEW "
            "ONE, THEN FROM "
            f"{s('arm-plate-located', 4)}.",
            f"REPLACE A {n['pd-transgear-knob-shaft']} FOUND OUTSIDE AND REPEAT FROM "
            f"{s('arm-plate-located', 4)}.",
            "IF ALL ARE INSIDE, UNCLAMP AND REPEAT FROM STEP "
            f"{steps.step_number('latch-pin-pressed')} WITH A NEW "
            f"{n['pd-transgear-arm']} ARM, {n['pd-transgear-pin']} PIN AND "
            f"{n['pd-vn-transgear-latch-pin']} DOWEL, THE BUSHED PLATE KEPT, SKIPPING "
            f"{bush_made}.",
        ),
        # The located step uses all 24 sub-step letters, so the match-drill,
        # the parting, the final reams and the dowel press open the fitted
        # step.
        "arm-plate-fitted": (
            # Front up, the drill enters the arm, at its own pattern from S
            # (pd_transgear_arm_plate_geometry: the matched pilots go through
            # at the arm's pattern).
            f"MATCH-DRILL 2 {PLATE_DOWEL_PILOT_TEXT} PILOTS THROUGH THE ARM AND "
            f"THE PLATE AT {n['pd-transgear-arm']}'S 2 LOCATING-HOLE PLACES.",
            "UNCLAMP THE ARM AND THE PLATE.",
            "LIFT THE PLATE OFF THE ARM.",
            f"REAM THE ARM'S 2 HOLES TO {n['pd-transgear-arm']} (PRESS).",
            f"REAM THE PLATE'S 2 HOLES TO {n['pd-transgear-arm-plate']} (SLIP).",
            f"PRESS {TRANSGEAR_QUANTITIES['pd-vn-transgear-arm-plate-locating-pin']} "
            f"{n['pd-vn-transgear-arm-plate-locating-pin']} DOWELS INTO THE ARM "
            "FROM THE REAR, "
            f"{steps.inch_window(plate_locating_interface.PROUD_LIMITS_MM, 3, ' TO ')} "
            f"PROUD, CALIPER DEPTH ROD {detail_cite('arm-plate-fitted')}.",
            # The arm carries DETAIL K's jig-boring by now, so a dowel that
            # slides in is bonded, not scrapped with the arm (owner ruling
            # 2026-11-20 (Pedro), #2497; machinist exception
            # PD-00-press-salvage). The scrap rule stays at the bush's press
            # (11), the latch dowel's (10B), the hub pin's (16) and the
            # collar's pins (20); the MHA-PD-23 pin and the MHA-PD-20 spacer
            # are bonded slip fits.
            # The cured dowel is read again before the plate goes on;
            # a bond that fails renews the arm's set as 13Y does. The plate
            # refit and its match mark share a sub-step (24-letter budget).
            # The bond's prep and application (machinist review of
            # 592b20079f) are DETAIL H's bond note, so 13G stays one action
            # within the step's 24 letters (review of 70917f0316).
            "IF A DOWEL SLIDES IN BY HAND, BOND IT PER THE BOND NOTE AT "
            f"{detail_cite('arm-plate-fitted')[1:-1]}.",
            "CHECK: A BONDED DOWEL, PUSHED, STILL READS AS "
            f"{s('arm-plate-fitted', 5)}.",
            f"IF IT MOVES OR READS OUTSIDE, RENEW AS {s('arm-plate-fitted', 22)}.",
            "FIT THE PLATE BACK ON ITS DOWELS AND MATCH-MARK ARM AND PLATE.",
            # Delegated ruling 2026-11-07 (Main, L1): the plate's screw holes
            # are the master for the arm's 8-32 taps.
            f"WITH {n['pd-transgear-arm-plate']} DOWELED TO {n['pd-transgear-arm']}, "
            f"SPOT THROUGH {n['pd-transgear-arm-plate']}'S {ARM_PLATE_SCREW_HOLE_TEXT} "
            f"SCREW HOLES WITH A {ARM_PLATE_SPOT_DRILL_TEXT} DRILL.",
            "REMOVE THE PLATE.",
            f"DRILL EACH SPOT {TAP_8_32_DRILL_TEXT} THRU {n['pd-transgear-arm']}.",
            # The title block's edge break (.010 max) breaks the tap mouths.
            "TAP EACH HOLE #8-32 UNC THRU.",
            f"FIT THE {n['pd-transgear-arm-plate']} PLATE ON ITS DOWELS, "
            "MATCH MARKS TOGETHER.",
            # Snug, then tighten, as the bar's and the locks' screws are
            # (machinist review 20261124T013305458Z, rule 22).
            f"FIT {TRANSGEAR_QUANTITIES['pd-vn-transgear-arm-plate-screw']} "
            f"{n['pd-vn-transgear-arm-plate-screw']} SCREWS IN THE ARM'S THROUGH "
            "TAPS, BOTH SNUG.",
            "TIGHTEN BOTH SCREWS IN TURN.",
            "CHECK, AFTER EVERY REFIT: PUSHED AND ROCKED BY HAND, THE PLATE HAS "
            "NO SHAKE ON THE DOWELS AND NO DAYLIGHT UNDER IT.",
            "IF IT SHAKES OR SHOWS DAYLIGHT, CLEAN AND DEBURR THE FACES AND "
            f"DOWELS AND REPEAT {s('arm-plate-fitted', 14)}-{s('arm-plate-fitted', 17)}.",
            # The doweled plate is read before the pivot spacer is bonded, the cup
            # bonded or the hook drilled, so a setting the dowels lost
            # costs only the arm's own parts. The uncut plate screws stand
            # under the disc with room to spare
            # (test_the_trial_stack_goes_together_at_the_located_step).
            # Machinist review r9 (rule 22): one action; the step is at its
            # 24-letter budget, so the clamp set-up is the repeat's condition.
            f"REPEAT {s('arm-plate-located', 9)}-{s('arm-plate-located', 10)} WITH "
            "THE ARM CLAMPED FRONT UP ON THE SAME PARALLELS ON THE MILL TABLE.",
            f"CHECK: AS {s('arm-plate-located', 11)} AND {s('arm-plate-located', 12)}, "
            "A DIAL INDICATOR ON A MAGNETIC BASE.",
            # A chip from the drilling just done reads as a tight spot or an
            # off reading, so the doweled set is cleaned and read once more
            # before it is scrapped (codjiflo P2 on ab2fdaf, as 28A/28B).
            "IF A CHECK FAILS, CLEAN THE TEETH AND SEATS AND REPEAT "
            f"{s('arm-plate-fitted', 19)}-{s('arm-plate-fitted', 20)}.",
            "IF A CHECK STILL FAILS, THE DOWELS HAVE NOT HELD: "
            f"REPEAT FROM STEP {steps.step_number('latch-pin-pressed')} WITH A NEW "
            f"{n['pd-transgear-arm']} ARM, {n['pd-transgear-arm-plate']} PLATE, {bush} "
            f"BUSH, {n['pd-transgear-pin']} PIN, {n['pd-vn-transgear-latch-pin']} DOWEL "
            f"AND {TRANSGEAR_QUANTITIES['pd-vn-transgear-arm-plate-locating-pin']} "
            f"{n['pd-vn-transgear-arm-plate-locating-pin']} DOWELS, THE SCREWS "
            "REUSED.",
            "LIFT OFF THE SHAFT, THE RING, THE CLUSTER AND THE BUSHING.",
        ),
        "arm-plate-screws-cut": (
            f"REMOVE BOTH {n['pd-vn-transgear-arm-plate-screw']} SCREWS.",
            "CUT EACH TIP FLUSH TO "
            f"{steps.inch_text(joints.PLATE_SCREW_CUT_PROUD_MAX, 3)} PROUD OF THE "
            f"ARM {row_cite('plate-screw-tips')}.",
            "BREAK THE CUT EDGE "
            f"{steps.inch_max_text(plate_screw.CUT_END_BREAK_MAX, 3)} TO KEEP THE TAP'S "
            "LAST THREAD.",
            "REFIT THE SAME SCREWS IN THE SAME HOLES, TIGHT.",
            # A check and its remedy are separate steps (rule 22; r10).
            "CHECK: ROCKED BY HAND, THE PLATE HAS NO SHAKE AND NO DAYLIGHT.",
            f"IF IT SHAKES OR SHOWS DAYLIGHT, DO {s('arm-plate-fitted', 18)} AND "
            f"REPEAT {s('arm-plate-screws-cut', 4)}.",
            # #2430: the pivot screw's tip is faced on the bare screw, before
            # the spring, the arm and the bonded spacer make it captive; it
            # seats the same bare as finished (the spacer stands flush with
            # the shoulder's end, both on the bar's back face). It is this
            # step's last cut tip so step 15 keeps a letter for lifting the
            # dry-trial spacer off (Codjiflo r1 on #3487).
            f"FACE THE {n['pd-vn-transgear-pivot-screw']} SCREW'S TIP UNTIL, SEATED "
            f"BARE IN THE {n['pd-support-bar']} BAR'S TAP, IT STANDS "
            f"{steps.inch_window(pivot_screw.TIP_RECESS, 3, ' TO ')} BELOW THE BAR'S "
            f"FRONT FACE, CALIPER DEPTH ROD {row_cite('pivot-tip')}.",
        ),
        # The spacer is bonded on the shoulder (LOCTITE 638; owner ruling
        # 2026-11-24, fit audit question 6), its front face and the
        # shoulder's end clamped down on one flat plate while it cures, so
        # its faces' tilt is fixed in the bar; the MHA-PD-VN-63 spring holds
        # the arm on it. The
        # screw's tip is faced below the bar's front face, where the platen
        # slides; the screw is unlocked, held by its shoulder seated on the
        # bar's back face (owner ruling U-MHA-PD-VN-57-no-lock, #1194). The
        # spot-face floor sets the spring room (transgear_hanger_joints).
        "hanger-pivoted": (
            f"FIT THE {n['pd-vn-transgear-pivot-spring']} SPRING ON ITS SHOULDER, FROM "
            "THE REAR.",
            # Paste wax keeps the compound out of the running fit and off the
            # face the arm bears on (rule 23); named in full so the package's
            # tool scan lists it (Codjiflo r1 on #3487).
            "FIT THE ARM, ITS BORE AND FRONT FACE COATED WITH PASTE WAX, ON IT "
            "FROM THE REAR.",
            # The dry trial is what holds one bought screw's shoulder end
            # inside the squareness the drilled pivot bore tolerates
            # (pd_transgear_arm_geometry.PIVOT_SHOULDER_END_SQUARENESS_ALLOWED):
            # no catalogue row states it. It is also the acceptance of the
            # spacer's bore-to-face squareness, which the MHA-PD-20 sheet
            # holds only at the angular row: a spacer whose front face will
            # not lie on the plate with the shoulder's end cannot cure in
            # the plane the hanger tilt stack assumes (Codjiflo r1 on
            # #3487). The plate is covered with polyethylene film, which the
            # compound does not bond to, not waxed: the shoulder's end is
            # the unlocked screw's only seat and takes no wax.
            f"CHECK, DRY: THE {n['pd-transgear-pivot-spacer']} SPACER, AS MADE, ON "
            "THE SHOULDER, SCREW HELD DOWN ON A FLAT PLATE COVERED WITH "
            f"POLYETHYLENE FILM, WHOSE HOLE CLEARS THE {pivot_screw.THREAD} THREAD, "
            f"NOT THE \u00d8{steps.inch_text(pivot_screw.SHOULDER_DIA, 4)} SHOULDER: "
            "THE SPACER SHOWS NO DAYLIGHT ON THE PLATE AND THE ARM SWINGS FREELY.",
            # Bounded: the one renewal and the inspection that follows it
            # are the step's own tail (Codjiflo r1 on #3487).
            f"IF EITHER FAILS, DO {s('hanger-pivoted', 20)}-{s('hanger-pivoted', 23)}.",
            "LIFT THE SPACER OFF THE SHOULDER.",
            # One action per sub-step (machinist review
            # 20261124T013305458Z, rule 22): coat, push on, wipe and clamp
            # each stand alone, and the cure is the wait before the screw is
            # seated (the arm is first oiled only in the remedy after it).
            # The bore is coated, not the shoulder: the shoulder's end
            # entering the bore drives the compound toward the spacer's
            # front face, away from the arm, where it is wiped.
            "DEGREASE THE SPACER'S BORE AND THE SHOULDER BELOW THE ARM.",
            "COAT THE SPACER'S BORE WITH LOCTITE 638, NOT THE SHOULDER.",
            "PUSH THE SPACER ON THE SHOULDER UNTIL ITS FRONT FACE IS FLUSH WITH "
            "THE SHOULDER'S END.",
            "WIPE THE SPACER'S FRONT FACE CLEAN.",
            "AT ONCE, CLAMP THE SCREW DOWN, THE SHOULDER'S END AND THE SPACER BOTH "
            f"ON THE PLATE OF {s('hanger-pivoted', 2)}.",
            f"WHEN THE BOND HAS CURED {PIVOT_SPACER_BOND_CURE_H} H, SEAT THE SCREW, "
            f"ITS SHOULDER TIGHT ON THE BAR'S BACK FACE ({PIVOT_VIEW_REF}).",
            "CHECK: NO DAYLIGHT BETWEEN THE SPACER AND THE BAR'S BACK FACE.",
            # The seat's preload is the joint's only retention (Codjiflo P2
            # on 93879abc87): a hand-torque acceptance that locks nothing.
            "CHECK: A HEX KEY BY HAND DOES NOT LOOSEN THE SCREW.",
            "CHECK: RAISED AND RELEASED, THE ARM FALLS FREELY.",
            f"IF ALL THREE CHECKS PASS, SKIP {s('hanger-pivoted', 15)}-"
            f"{s('hanger-pivoted', 23)}.",
            # The arm is captured on the shoulder between the head and the
            # bonded spacer, so the remedy takes the screw out first
            # (Codjiflo P3 on 93879abc87).
            pivot_unscrewed[0],
            pivot_unscrewed[1],
            "FLUSH OIL INTO THE ARM'S BORE, WORKING THE ARM ON THE SHOULDER.",
            "CLEAN AND DEBURR THE SPACER END, BAR BACK FACE AND TAP MOUTH.",
            # #3107 (Codjiflo P3 on 3e6318a026, P2s on f92995b8e6): the
            # renewal runs once; a second failure sends the bar and the arm
            # to their sheets and closes every outcome, one action a step
            # (machinist review of 17c29c2192, rule 22).  One repeat of the
            # reseat, its checks, their skip and the strip: checks that now
            # pass leave the step there, and checks that fail again leave
            # the screw out and the arm off for the renewal (the 24-letter
            # budget).
            f"REPEAT {s('hanger-pivoted', 10)}-{s('hanger-pivoted', 16)} ONCE.",
            # The arm is captive between the screw's head and the spacer
            # bonded on its shoulder: the renewal frees it on the owned arbor
            # press, the screw pushed out of the spacer (the LOCTITE 638 bond
            # shears at about 199 N, transgear_hanger_joints
            # .SPACER_BOND_SHEAR_N) with no heat near the arm's other bonds;
            # screw and spacer are renewed anyway (delegated ruling 2026-11-24
            # (Main), D10: owner question Q7a, option B; no precedent, #2144).
            # In this sub-step, not a new one: the steps fill STEP_SLOTS.
            "IF NOT YET RENEWED, PUSH THE SCREW OUT OF THE SPACER, ARM REAR FACE "
            f"DOWN ON THE ARBOR PRESS, AND REPEAT FROM {s('arm-plate-screws-cut', 6)} "
            f"WITH A NEW {n['pd-vn-transgear-pivot-screw']} "
            f"SCREW AND {n['pd-transgear-pivot-spacer']} SPACER.",
            f"IF ALREADY RENEWED, INSPECT THE {n['pd-support-bar']} BAR'S "
            f"TAP AND BACK FACE AND THE {n['pd-transgear-arm']} ARM'S BORE "
            "TO THEIR SHEETS.",
            # Codjiflo r2 on e8b4e199aa: a new bar renews everything built on
            # it, so its route is the whole paper drive (Main's ruling), and
            # an arm found outside with it is renewed in that rebuild.
            f"FOR A BAR FOUND OUTSIDE, MAKE A NEW {n['pd-support-bar']} BAR AND "
            f"REBUILD FROM STEP {steps.step_number('bar-clamped')}, WITH "
            f"{s('hanger-pivoted', 23)}'S PARTS IF THE ARM IS ALSO OUTSIDE.",
            "FOR AN ARM FOUND OUTSIDE, OR IF ALL ARE INSIDE, REPEAT FROM STEP "
            f"{steps.step_number('latch-pin-pressed')} WITH A NEW "
            f"{n['pd-transgear-arm']} ARM, {n['pd-transgear-arm-plate']} PLATE, {bush} BUSH, "
            f"{n['pd-transgear-pin']} PIN, {n['pd-transgear-pivot-spacer']} SPACER, "
            f"{n['pd-vn-transgear-latch-pin']} DOWEL, "
            f"{TRANSGEAR_QUANTITIES['pd-vn-transgear-arm-plate-locating-pin']} "
            f"{n['pd-vn-transgear-arm-plate-locating-pin']} DOWELS, "
            f"{TRANSGEAR_QUANTITIES['pd-vn-transgear-arm-plate-screw']} "
            f"{n['pd-vn-transgear-arm-plate-screw']} SCREWS AND "
            f"{n['pd-vn-transgear-pivot-screw']} SCREW.",
        ),
        "disc-cluster-assembled": (
            f"PRESS THE {hub_pin} PIN INTO THE {n['pd-transgear-disc-hub']} HUB'S "
            "REAMED CROSS HOLE FROM ITS REAMED END UNTIL IT STOPS.",
            _press_remedy(
                "PIN", f"{n['pd-transgear-disc-hub']} HUB", "disc-cluster-assembled"
            ),
            f"FIT THE {n['pd-rack-pinion']} DISC ON THE HUB'S SPIGOT.",
            f"SLIDE THE HUB'S BORE ON THE {n['pd-transgear-feed-pinion']} BOSS FROM "
            "THE NOSE, THE PIN OVER THE FLAT, SPIGOT TO THE "
            f"{n['pd-transgear-feed-pinion']} STEP FACE.",
            "CHECK: TURNED EACH WAY, THE HUB DRIVES THE SLEEVE BY THE PIN.",
        ),
        "disc-taps-transferred": (
            # #2418: not a Ø1/8 mandrel between centres, a precision tool of
            # its own whose ends are no bigger than the smallest centre drill's
            # body. A stub turned in the chuck to the bore runs true to the
            # spindle by construction, is fitted to the actual bore and needs
            # no drawing. The sleeve, not the slender stub, takes the truing
            # taps: its rear face sits on the stub's faced shoulder and the
            # tailstock centre holds its front bore mouth. The stub stays
            # chucked until the re-check, or a re-chucked stub's own runout
            # enters the reading.
            # Machinist review r9 (cca037c3d, rule 22): turning the stub and
            # mounting the cluster on it are separate sub-steps.
            "TURN A STUB MANDREL IN PLACE IN THE LATHE CHUCK TO A SLIDING FIT IN "
            f"THE {n['pd-transgear-feed-pinion']} BORE, WITH A FACED SHOULDER.",
            f"MOUNT THE {n['pd-transgear-feed-pinion']} SLEEVE, HUB AND DISC ON THE "
            "MANDREL, THE SLEEVE'S REAR FACE ON ITS SHOULDER, THE TAILSTOCK CENTRE "
            "IN ITS FRONT BORE MOUTH.",
            # #2665: centred on the O.D., cut on the teeth's arbor; the
            # tooth spaces are sampled at the re-check.
            f"WITH A DIAL INDICATOR ON THE {n['pd-rack-pinion']} DISC'S O.D. "
            f"{row_cite('disc-tir')}, TAP THE DISC CENTRAL UNTIL THE O.D. READS {tir} "
            "TIR MAX.",
            # The flange holes are off the axis, so the spots are taken off the
            # lathe; the trued disc is clamped to the flange first, or the
            # spigot's centring clearance lets it shift before it is spotted
            # (#2418).
            "CLAMP THE DISC TO THE HUB FLANGE WITH 2 TOOLMAKER'S CLAMPS BETWEEN "
            "ITS HOLES.",
            "BACK OFF THE TAILSTOCK.",
            "SLIDE THE SLEEVE, HUB AND DISC OFF THE MANDREL, LEAVING THE MANDREL IN "
            "THE CHUCK.",
            f"SPOT-DRILL THE DISC THROUGH THE {hub_geometry.SCREW_COUNT} HUB FLANGE "
            "HOLES.",
            f"DRILL EACH SPOT {TAP_0_80_DRILL_TEXT} THRU THE DISC.",
            f"TAP EACH HOLE {disc_screw.THREAD} THRU.",
            f"FIX THE DISC WITH {hub_geometry.SCREW_COUNT} "
            f"{n[explode.DISC_SCREW]} SCREWS.",
            "REMOVE THE CLAMPS.",
            "REFIT THE SLEEVE, HUB AND DISC ON MANDREL AND TAILSTOCK AS "
            f"{s('disc-taps-transferred', 1)}.",
            f"CHECK {row_cite('disc-tir')}: A "
            f"\u00d8{steps.inch_text(disc.TOOTH_SPACE_GAUGE_PIN_DIA_MM, 3)} GAUGE PIN "
            f"IN {DISC_TIR_SAMPLE_SPACES} SPACES, EVERY {DISC_TIR_SAMPLE_STRIDES[0]}TH "
            f"OR {DISC_TIR_SAMPLE_STRIDES[1]}TH, READS {tir} TIR MAX.",
            # The O.D. already read true, so the disc is set by the gauge
            # pin's readings (machinist review 20261124T035641048Z: "the
            # pins" named nothing the builder had met).
            "IF NOT, SLACKEN THE SCREWS.",
            f"TAP THE DISC CENTRAL BY {s('disc-taps-transferred', 12)}'S GAUGE-PIN READINGS "
            f"AND REPEAT {s('disc-taps-transferred', 9)} AND "
            f"{s('disc-taps-transferred', 12)}.",
            # Rule 23 bench acceptance for the disc screws: they carry the
            # drive torque as shear on the flange's bolt circle
            # (joint_retention 'pd-paper-drive/disc-screws', STATIC_CLAMP;
            # machinist review round 6, accept PD-00-disc-hub-shear-clamp).
            "CHECK: WITH THE SLEEVE HELD, FIRM HAND TORQUE AT THE DISC RIM DOES "
            "NOT TURN THE DISC ON THE HUB.",
            f"IF IT TURNS, FIT NEW {n[explode.DISC_SCREW]}, REPEAT "
            f"{s('disc-taps-transferred', 12)}-{s('disc-taps-transferred', 15)}.",
            "MATCH-MARK DISC AND HUB.",
        ),
        "disc-screws-cut": (
            f"CUT THE {n[explode.DISC_SCREW]} TIPS "
            f"{steps.inch_window(disc_screw.TIP_BELOW_REAR_FACE, 3, ' TO ')} BELOW "
            "THE DISC REAR FACE "
            f"{row_cite('disc-screw-tips')}.",
        ),
        "oil-hole-drilled": (
            f"DRILL THE \u00d8{steps.inch_text(hub.OIL_HOLE_DIA, hub.OIL_HOLE_PLACES)} "
            "OIL HOLE CENTRED ON THE HUB BODY, THROUGH HUB AND SLEEVE IN ONE "
            f"SETUP, AS {n['pd-transgear-disc-hub']} SHOWS.",
        ),
        "disc-cluster-hung": (
            "OIL THE PIN WITH LIGHT MACHINE OIL.",
            f"FIT THE {n['pd-transgear-rear-bushing']} BUSHING ON THE PIN.",
            f"FIT THE {n['pd-transgear-feed-pinion']} SLEEVE, HUB AND DISC ON IT, "
            f"ON THE PIN, {FEED_PINION} REARWARD.",
            f"FIT THE {n['pd-transgear-front-bushing']} BUSHING ON THE SLEEVE'S "
            "FRONT END, "
            f"TRAPPING THE {n['pd-transgear-disc-hub']} HUB AND THE DISC.",
            f"PUSH THE {n['pd-vn-transgear-retaining-ring']} RING SIDEWAYS INTO THE "
            "PIN GROOVE, SEATED ON THE GROOVE'S FRONT WALL.",
        ),
        "disc-cluster-shimmed": (
            f"PUSH THE {n['pd-transgear-feed-pinion']} SLEEVE REARWARD, THE "
            f"{n['pd-vn-transgear-retaining-ring']} "
            "RING ON ITS GROOVE'S FRONT WALL.",
            f"READ THE GAP BETWEEN THE {n['pd-transgear-front-bushing']} BUSHING AND "
            f"THE {n['pd-vn-transgear-retaining-ring']} RING WITH FEELERS "
            f"(WITH NO SHIMS IT READS {bare_gap}).",
            # Machinist review rounds 8-10: the shims sit under the rear
            # bushing, so the stack comes off to change them, either way, and
            # goes back on to re-read. The bare stack is never under the
            # window (transgear_cluster_fit.UNSHIMMED_FLOAT_RANGE), so an
            # under gap is an overshoot: one shim comes off. The shims are
            # sized to bring the gap to the window's middle. The check is the
            # reading alone and the next sub-step names what it passes on
            # (machinist review of fanout/integration 8fb7fb46f7: a bare-stack
            # remark between them left "IF IT DOES" pointing at either). The
            # bare gap's range and the shim's thickness print with the reading
            # and the remedy, so the sheet shows that none to the most shims
            # cover every stack and an under reading always has a shim to take
            # off (review of the DETAIL E rename: the loop could stall).
            f"CHECK: THE GAP READS {CLUSTER_FLOAT_VIEW_NAME} (SHEET {float_sheet}).",
            f"IF THE GAP READS {CLUSTER_FLOAT_VIEW_NAME}, GO TO STEP "
            f"{steps.step_number('disc-cluster-shimmed') + 1}.",
            "IF NOT, REMOVE THE RING, THE "
            f"{n['pd-transgear-front-bushing']} BUSHING, THE SLEEVE WITH HUB AND DISC, "
            f"AND THE {n['pd-transgear-rear-bushing']} BUSHING.",
            # #3106: the count is stated; to the nearest shim the gap lands
            # within half a shim of the middle, inside DETAIL E's window
            # (asserted where shim_target is set).
            f"IF IT READ OVER, ADD {shim_thickness} {n['pd-vn-transgear-cluster-shim']} "
            f"SHIMS AT THE ARM FACE, ONE PER {shim_thickness} OVER {shim_target} TO THE "
            f"NEAREST, UP TO {cluster_fit.SHIM_COUNT_RANGE[1]} IN ALL.",
            "IF IT READ UNDER, TAKE ONE SHIM OFF.",
            f"REFIT PER {s('disc-cluster-hung', 1)}-{s('disc-cluster-hung', 4)}.",
            f"REPEAT FROM {s('disc-cluster-shimmed', 0)}.",
        ),
        "collar-pins-pressed": (
            f"PRESS {TRANSGEAR_QUANTITIES['pd-vn-transgear-knob-drive-pin']} "
            f"{n['pd-vn-transgear-knob-drive-pin']} DOWELS INTO THE "
            f"{n['pd-transgear-drive-collar']} COLLAR TO A STOP, {drive_window} "
            f"PROUD OF ITS FRONT {detail_cite('collar-pins-pressed')}.",
            # The collar's pin holes are reamed to the bought dowels, which
            # are their gauges and print no band, so a dowel or pin that
            # slides in by hand is in a hole of unknown size: no bonded
            # clearance can be printed for it (rule 23), and the looseness
            # is what the reams exist to prevent (MHA-PD-22's necessity
            # register, N-01 and N-02).  The collar is renewed, rule 23's
            # press remedy (Codjiflo P2 on #3485: the bond salvage printed
            # no clearance).  The drive-pin offsets are REF targets on
            # MHA-PD-22 (MHA-PD-09 keeps its printed band): their acceptance
            # is this trial of the three wheels (owner ruling 2026-11-24, fit
            # audit question 8, applied to MHA-PD-22 only).
            # No easing drill is printed; a wheel that binds is renewed.
            # A new collar has a fresh #11 bore and a fresh pin crest, and
            # MHA-PD-08's core and D-flat were made to the old ones, so every
            # collar renewal (here, the pilot's and the rear face's) runs
            # through this step's last five sub-steps: the new collar is
            # tried on the shaft, a shaft that binds is cut to it and one
            # that shakes is renewed to it (Codjiflo P2 on #3485: the
            # remedies broke the made-to-fit pair).  One action each.
            "IF A DOWEL SLIDES IN BY HAND, RENEW THE COLLAR PER "
            f"{s('collar-pins-pressed', 7)}-{s('collar-pins-pressed', 11)}.",
            # The flat pin is pressed on the collar's own traveler, so the
            # collar arrives with it and MHA-PD-08's D-flat, milled to that
            # pin (its note 2), is finished before the shaft is first used
            # at the arm-plate-located step (Codjiflo P2 on #3485: the flat
            # needed a pin pressed at this later step).  This step checks
            # the joint (rule 23: a bench acceptance).
            f"CHECK: THE {n['pd-vn-transgear-collar-flat-pin']} PIN STANDS ON THE "
            "BOTTOM OF THE COLLAR'S REAR BLIND HOLE AND DOES NOT MOVE BY HAND; "
            "COLLAR AND PIN ARE ONE PERMANENT UNIT.",
            "IF THE PIN MOVES, RENEW THE COLLAR PER "
            f"{s('collar-pins-pressed', 7)}-{s('collar-pins-pressed', 11)}.",
            f"CHECK: EACH OF THE {len(sprocket.CONFIGS)} "
            f"{n['pd-transgear-removable']} WHEELS DROPS ON THE COLLAR'S DOWELS "
            "FREELY AND LIFTS OFF.",
            "IF ONE WHEEL BINDS, RENEW IT.",
            "IF NO WHEEL BINDS, GO TO STEP "
            f"{steps.step_number('collar-pins-pressed') + 1}.",
            "ALL WHEELS BINDING, OR A COLLAR SENT HERE FOR RENEWAL: MAKE A NEW "
            f"{n['pd-transgear-drive-collar']} COLLAR.",
            f"CHECK: THE NEW COLLAR SLIDES ON THE {n['pd-transgear-knob-shaft']} "
            "SHAFT'S CORE BY HAND WITH NO SHAKE, ITS PIN ON THE D-FLAT.",
            "IF IT BINDS, CUT THE SHAFT'S CORE AND D-FLAT TO THE NEW COLLAR PER "
            f"{n['pd-transgear-knob-shaft']}.",
            f"IF IT SHAKES, MAKE A NEW {n['pd-transgear-knob-shaft']} SHAFT TO THE "
            "NEW COLLAR.",
            f"REPEAT FROM {s('collar-pins-pressed', 0)} WITH THE NEW COLLAR.",
        ),
        "pilot-faced-to-fit": (
            f"FACE THE {n['pd-transgear-drive-collar']} COLLAR'S FRONT PILOT "
            f"{collar.PILOT_PROUD_TEXT} PROUD OF EACH "
            f"{n['pd-transgear-removable']} WHEEL LAID FLAT ON THE PINS, READ WITH "
            f"A STRAIGHTEDGE AND FEELERS {row_cite('collar-pilot')}.",
            "IF THE PILOT FACES BELOW THE WINDOW, RENEW THE COLLAR PER "
            f"{s('collar-pins-pressed', 7)}-{s('collar-pins-pressed', 11)}.",
        ),
        # #2425 (owner ruling 2026-11-20): the end float is set at fit-up. The
        # shaft stands rearward (pinion on the ring, ring on the bush's hub
        # face), the journal's stand-out behind the bush is read, and the
        # cup's front faced until its pilot depth is END_FLOAT less; the
        # pilot is then bonded on the journal end with LOCTITE 641 and the
        # MHA-PD-VN-71 screw seated on the axis (rule 23: the grade, degrease,
        # the compound on the journal, not the blind pilot, kept off the bush
        # bore the journal runs in, set at once, and the cure before load).
        "knob-stack-fitted": (
            f"PASS THE {n['pd-transgear-knob-shaft']} SHAFT THROUGH THE LOOSE "
            f"{n['pd-transgear-knob-thrust-ring']} RING INTO THE {bush} BUSH'S BORE "
            "FROM THE FRONT.",
            f"PUSH THE SHAFT REARWARD, THE {teeth} ON THE RING, THE RING ON THE "
            "BUSH'S HUB FACE.",
            "READ THE JOURNAL'S STAND-OUT BEHIND THE BUSH'S REAR FACE, CALIPER DEPTH "
            "ROD.",
            f"FACE THE {n['pd-transgear-knob-cup']} CUP'S FRONT UNTIL ITS PILOT DEPTH "
            f"READS {steps.inch_text(knob_shaft.END_FLOAT, 3)} LESS THAN "
            f"{s('knob-stack-fitted', 2)}'S STAND-OUT, CALIPER DEPTH ROD "
            f"{row_cite('cup-set')}.",
            "IF THE PILOT ENDS SHALLOWER THAN THAT, MAKE A NEW "
            f"{n['pd-transgear-knob-cup']} CUP AND REPEAT {s('knob-stack-fitted', 3)}.",
            "DEGREASE THE CUP'S PILOT, THE JOURNAL'S STAND-OUT AND REAR TAP, AND THE "
            f"{n['pd-vn-transgear-knob-cup-screw']} SCREW.",
            "COAT THE JOURNAL'S REAR END WITH LOCTITE 641, NOT THE CUP'S BLIND "
            "PILOT, KEEPING IT OFF THE JOURNAL IN THE BUSH.",
            "AT ONCE, FIT THE CUP'S PILOT ON THE JOURNAL END.",
            f"SEAT THE {n['pd-vn-transgear-knob-cup-screw']} SCREW THROUGH THE CUP "
            "INTO THE JOURNAL'S TAP, ITS HEAD TIGHT IN THE CUP'S COUNTERBORE.",
            "WIPE OFF COMPOUND SQUEEZED OUT AT THE CUP'S FRONT, CLEAR OF THE BUSH.",
            f"LET THE BOND CURE {KNOB_CUP_BOND_CURE_H} H BEFORE THE KNOB IS TURNED, "
            "LOADED OR OILED.",
            f"CHECK: SHAFT REARWARD AS {s('knob-stack-fitted', 1)}, THE GAP BETWEEN "
            f"THE CUP'S FRONT AND THE BUSH'S REAR FACE READS {knob_window} ON FEELERS "
            f"{row_cite('knob-end-float')}.",
            "CHECK: SHAFT HELD, THE CUP DOES NOT TURN OR SLIDE ON THE JOURNAL BY HAND.",
            f"IF BOTH CHECKS PASS, SKIP {s('knob-stack-fitted', 14)}-"
            f"{s('knob-stack-fitted', 17)}.",
            knob_cup_off[0],
            knob_cup_off[1],
            "CLEAN THE COMPOUND OFF THE JOURNAL END AND OUT OF ITS TAP.",
            f"REPEAT FROM {s('knob-stack-fitted', 2)} WITH A NEW "
            f"{n['pd-transgear-knob-cup']} CUP AND {n['pd-vn-transgear-knob-cup-screw']} "
            "SCREW.",
            f"SLIDE THE {n['pd-transgear-drive-collar']} COLLAR ON THE "
            f"{n['pd-transgear-knob-shaft']} SHAFT, ITS PIN ON THE D-FLAT, ITS DOWELS "
            "FORWARD, NOT YET FIXED TO THE SHAFT.",
            "TURN THE KNOB ONLY BY THE COLLAR UNTIL STEP "
            f"{steps.step_number('chain-closed')}; FROM THEN ON, TURN THE CRANK.",
        ),
        "latch-hook-fitted": (
            f"CLAMP THE {n['pd-latch-hook']} HOOK'S BASE TO THE "
            f"{n['pd-support-bar']} BAR'S BACK FACE, ITS 2 SCREW HOLES ON THE "
            f"HOOK-TAP CENTRES LAID OUT PER {n['pd-support-bar']}, ARM HANGING "
            "DOWN.",
            "SPOT THE BAR THROUGH THE HOOK'S 2 "
            f"\u00d8{steps.inch_text(hook_geometry.SCREW_HOLE_DIA, 3)} HOLES WITH A "
            "TRANSFER PUNCH.",
            "REMOVE THE HOOK.",
            f"DRILL EACH SPOT {TAP_4_40_DRILL_TEXT} THRU.",
            "TAP EACH HOLE #4-40 UNC-2B THRU.",
            f"SCREW THE HOOK ON WITH "
            f"{TRANSGEAR_QUANTITIES['sh-vn-fillister-screw-90280a108']} "
            f"{n['sh-vn-fillister-screw-90280a108']} SCREWS; ITS PIN HOLE IS NOT "
            "YET DRILLED.",
            "CHECK: BOTH SCREWS ENTER BY HAND.",
            "IF ONE BINDS, RUN THE TAP THROUGH AGAIN.",
            "CHECK: THE HOOK BASE SEATS FLAT ON THE BAR.",
            "IF IT ROCKS, DEBURR THE TAP MOUTHS AND THE BASE.",
        ),
        # Owner direction 2026-11-11 (#2416): the feed mesh only has to run
        # without binding, keep its teeth engaged and feed the paper steadily;
        # its backlash is not a function. So, as on the original, the arm is
        # swung up until the teeth are fully engaged without binding and set
        # there by feel, with no gauge, and accepted on function; a tight spot
        # is cleared by easing the arm off at it. The band stays the builder's
        # design proof (paper_drive_rack_setup); what a feel set leaves is
        # steps.FEED_LOOSEST_MESH's. The ease stops where the teeth just turn
        # free at the tight spot, which keeps the set at that spot's bind; the
        # no-skip check before the hook is drilled only guards against the
        # mesh coming loose (codjiflo P2 on 2f5bac993, P3 on da9bf7c5e).
        "hanger-meshed": (
            f"SWING THE ARM UP UNTIL THE {n['pd-transgear-feed-pinion']} TEETH ARE "
            f"FULLY ENGAGED IN THE {n['pd-feed-rack']} RACK WITHOUT BINDING.",
            "CLAMP THE ARM TO THE BAR.",
            "RUN THE PLATEN THROUGH THE ENGAGED FEED, "
            f"{engaged_feed_text(operating_domain)}, STOPPING SHORT OF BOTH ENDS "
            f"{row_cite('engaged-feed')}.",
            "CHECK: NO TIGHT SPOT.",
            "IF IT HAS A TIGHT SPOT, STOP THE PLATEN AT IT.",
            "WITH THE PLATEN AT THE TIGHT SPOT, UNCLAMP THE ARM.",
            "WITH THE ARM UNCLAMPED, EASE IT DOWN UNTIL THE TEETH JUST TURN FREE "
            "AT THE TIGHT SPOT.",
            f"AFTER EASING, REPEAT {s('hanger-meshed', 1)}-{s('hanger-meshed', 6)} "
            "UNTIL THE RUN HAS NO TIGHT SPOT.",
            "CHECK: KNOB HELD, PUSHED FIRMLY BY HAND EACH WAY AT BOTH ENDS AND THE "
            "MIDDLE OF THE ENGAGED FEED, THE PLATEN SKIPS NO TOOTH.",
            "IF IT SKIPS, INSPECT THE "
            f"{n['pd-transgear-feed-pinion']} TEETH AND THE {n['pd-feed-rack']} RACK "
            "TO THEIR SHEETS.",
            *sleeve_renewed,
            "IF IT SKIPPED, REPLACE ANY PART FOUND OUTSIDE, REPEAT FROM "
            f"{s('hanger-meshed', 0)}.",
        ),
        # The hook's pin hole is match-drilled from the pin at that mesh,
        # then the hook is refitted with the hole's lower edge on
        # the pin before its screws are tightened, so the unclamped arm has no
        # room to fall and open the mesh (rack_setup.LATCH_SLACK_ALONG; Codex P1 on
        # b2eb9a0e1).
        "hook-pin-hole-match-drilled": (
            f"HOLDING THAT MESH, MARK THE {n['pd-vn-transgear-latch-pin']} PIN'S "
            f"AXIS ON THE {n['pd-latch-hook']} HOOK'S STRAIGHT RUN WHERE THE PIN'S "
            "END BEARS.",
            "REMOVE THE HOOK.",
            f"DRILL ITS PIN HOLE AT THE MARK PER {n['pd-latch-hook']}.",
            "REFIT THE HOOK WITH ITS PIN HOLE'S LOWER EDGE ON THE PIN.",
            "TIGHTEN THE HOOK SCREWS.",
            "CHECK: PUSHED FIRMLY BY HAND, THE HOOK DOES NOT MOVE ON THE BAR.",
            f"IF IT MOVES, FIT NEW {n['sh-vn-fillister-screw-90280a108']} SCREWS AND "
            f"REPEAT {s('hook-pin-hole-match-drilled', 3)}-"
            f"{s('hook-pin-hole-match-drilled', 5)}.",
            "UNCLAMP THE ARM.",
            f"CHECK: THE ARM STAYS LATCHED, THE {n['pd-vn-transgear-latch-pin']} PIN "
            f"STANDING THROUGH THE {n['pd-latch-hook']} HOOK'S PIN HOLE.",
            "CHECK: THE ENGAGED FEED RUNS WITH NO TIGHT SPOT.",
            "CHECK: KNOB HELD, PUSHED FIRMLY BY HAND EACH WAY AT BOTH ENDS AND THE "
            "MIDDLE OF THE ENGAGED FEED, THE PLATEN SKIPS NO TOOTH.",
            f"IF A CHECK FAILS, FIT A NEW UNDRILLED {n['pd-latch-hook']} HOOK PER "
            f"{s('latch-hook-fitted', 5)}-{s('latch-hook-fitted', 9)} AND REPEAT "
            f"{s('hanger-meshed', 0)}-{s('hook-pin-hole-match-drilled', 10)}.",
        ),
        "loaded-rack-geometry-checked": (
            "LOAD THE PAPER.",
            "TURN THE KNOB TO RUN THE PLATEN THROUGH THE WHOLE ENGAGED FEED.",
            "CHECK: THE PLATEN ADVANCES STEADILY, WITH NO TIGHT SPOT.",
            "CHECK: ARM, HOOK AND PLATEN STAY SEATED.",
            "CHECK: KNOB HELD, THE PLATEN SHAKES ALONG THE RACK AT BOTH ENDS AND "
            "THE MIDDLE OF THE FEED.",
            # Codjiflo P2s on 6abe1aa7f and aa3c6786c: any rework of the rack
            # or guides moves the rack against the match-drilled latch, so the
            # mesh is set again by feel on a new hook. A feel set always lands
            # at the run's tight-spot bind, so with every part inside its sheet
            # the remedy takes out the one term the fitter controls, the crest
            # drift, by setting the bottom guide again with the rack level
            # (its screws float in the platen's holes); that the loop then
            # ends is steps.FEED_LEVEL_RACK_WORST_CASE_MESH's gate. The platen
            # comes off for the rework as in lock-seats-faced (codjiflo P3 on
            # 6c847adb0).
            # Machinist review r8 (59eb13ee2): a pass exit first, so a builder
            # whose checks all passed does not read on into the rework.
            "IF EVERY CHECK PASSES, GO TO STEP "
            f"{steps.step_number('fitup-pose-set')}.",
            f"IF A CHECK FAILS, INSPECT THE {n['pd-transgear-feed-pinion']} TEETH "
            f"AND THE {n['pd-feed-rack']} RACK TO THEIR SHEETS.",
            # The inspection's own sub-step comes first, so the check needs no
            # "after" (the step-line budget, machinist review of 592b20079f).
            "CHECK: PUSHED FIRMLY BY HAND ALONG AND ACROSS, THE RACK DOES NOT MOVE "
            "ON ITS GUIDE NOR THE GUIDES ON THE PLATEN.",
            f"AFTER CHECKING, UNSCREW AND REMOVE THE {n['pd-latch-hook']} HOOK.",
            "WITH THE HOOK OFF, REMOVE THE LOCKS.",
            "WITH THE LOCKS REMOVED, LIFT THE PLATEN OFF THE BAR.",
            "REPLACE ANY PART FOUND OUTSIDE OR LOOSE PER STEP "
            f"{steps.step_number('rack-screwed')}, "
            f"{steps.step_number('guides-screwed')} OR {s('hanger-meshed', 10)}.",
            f"IF NONE WAS FOUND, SLACKEN THE {n['pd-platen-bottom-guide']} BOTTOM "
            "GUIDE'S SCREWS.",
            "WITH THE SCREWS SLACK, SET THE GUIDE AGAIN PER "
            f"{s('guides-screwed', 1)}, THE CRESTS AT THE TWO ENDS WITHIN "
            f"{steps.inch_text(steps.LEVEL_RACK_CREST_DRIFT, 3)} OF EACH OTHER "
            f"{row_cite('crest-level')}.",
            "WITH THE GUIDE SET AGAIN, TIGHTEN ITS SCREWS.",
            f"REFIT PER {s('platen-hung', 9)}-{s('guide-locks-set', 3)}.",
            f"FIT A NEW UNDRILLED {n['pd-latch-hook']} HOOK PER "
            f"{s('latch-hook-fitted', 5)}-{s('latch-hook-fitted', 9)}.",
            f"WITH THE NEW HOOK, REPEAT {s('hanger-meshed', 0)}-"
            f"{s('loaded-rack-geometry-checked', 4)}.",
        ),
        "fitup-pose-set": (
            f"CHECK: THE ARM IS LATCHED, THE {n['pd-vn-transgear-latch-pin']} PIN "
            f"THROUGH THE {n['pd-latch-hook']} HOOK'S PIN HOLE.",
            f"PULL THE {CRANKSHAFT} CRANKSHAFT FORWARD.",
            f"PUSH THE KNOB SHAFT REARWARD, {teeth} ON THE "
            f"{n['pd-transgear-knob-thrust-ring']} RING, THE RING ON THE "
            f"{bush} BUSH'S HUB FACE.",
            f"SLIDE THE COLLAR BACK AGAINST THE {teeth}.",
            f"FIT THE {knob}, HELD BACK ON ITS SEAT.",
            f"FIT THE {n['pd-transgear-thumbnut']} THUMBNUT FINGER-TIGHT.",
            "TURN THE DISC UNTIL, ON THE LINE THROUGH THE KNOB AND DISC AXES, "
            f"A DISC TOOTH STANDS CENTRED IN A {teeth} GAP WITHIN {clock} "
            "AT THE PITCH CIRCLE, READ WITH A TEST INDICATOR ON A GAUGE PIN IN "
            f"THE GAP {row_cite('tooth-centred')}.",
            "CHECK: TURNED BY THE COLLAR, THE KNOB RUNS WITH NO TIGHT SPOT.",
            "CHECK: THE KNOB HAS SHAKE AT EVERY TOOTH.",
            # The final confirmation reads the doweled reducer as the trial
            # (arm-plate-located) and the doweled re-read (arm-plate-fitted)
            # did, now on the machine (#2417), held by the knob; it points
            # to the trial's full wording (the step-line budget, #3106).
            f"CHECK: KNOB PRESSED LIGHTLY TOWARD THE DISC AND HELD, THE DISC "
            f"SHAKES {REDUCER_BACKLASH_DIAL_TEXT} AS {s('arm-plate-located', 12)} "
            f"{row_cite('reducer-shake')}.",
        ),
        # The mesh was proven before the dowels and re-read on them before
        # anything irreversible, so what usually fails here is the plate's
        # seat (its screws were refitted at the cut) or a tooth fouled or
        # damaged since: those are tried first and cost a clean, a knob
        # stack or a disc (delegated ruling 2026-11-10 (PR #2494 takeover
        # agent), no precedent; owner review #2144; pending owner
        # confirmation). A fault that is the same all round
        # is in the arm's setting, and still takes the whole-transgear
        # rebuild (delegated ruling 2026-11-07 (Main), no precedent; owner
        # review #2144; pending owner confirmation), now from the latch
        # pin with the cluster reused. Taking the knob cup off renews the cup,
        # faced to its shaft's stand-out, and its screw (#2425; the owner
        # ruling 2026-11-08 renewing what a release frees, pending owner
        # confirmation, #2144); the pivot screw comes out with its pressed
        # spacer and both are renewed. One action per sub-step
        # (machinist review, #2417): the turn only finds the fault's period;
        # each remedy branch names it.
        # #2629 (machinist rule 22): a pass exit before the branch and again
        # after its clean-and-repeat, and each fault branch's sub-steps carry
        # its condition, so a builder whose checks pass, or whose fault is
        # another branch's, never reads on into a plain command.
        "fitup-mesh-remedied": (
            f"IF EVERY {s('fitup-pose-set', 7)}-{s('fitup-pose-set', 9)} CHECK "
            f"PASSES, GO TO STEP {steps.step_number('collar-rear-faced-to-fit')}.",
            "CHECK: ROCKED BY HAND, THE PLATE HAS NO SHAKE ON ITS DOWELS.",
            "CHECK: THE PLATE'S SCREWS ARE TIGHT.",
            f"IF SOUND, CLEAN THE {teeth} AND DISC AND "
            f"REPEAT {s('fitup-pose-set', 2)}-{s('fitup-pose-set', 9)}.",
            f"IF EVERY {s('fitup-pose-set', 7)}-{s('fitup-pose-set', 9)} CHECK NOW "
            f"PASSES, GO TO STEP {steps.step_number('collar-rear-faced-to-fit')}.",
            "TURN THE DISC ONE TURN BY THE COLLAR, NOTING WHERE IT FAULTS.",
            knob_stack_off,
            "FOR A FAULT ONCE A DISC TURN (A DISC TOOTH), STRIP THE CLUSTER "
            f"({s('disc-cluster-hung', 4)} BACK TO {s('disc-cluster-hung', 1)}), "
            "KEEPING ITS SHIMS.",
            f"FOR A DISC TOOTH, {hub_slid_off}",
            # A new disc's thickness is its own, so the old screws' cut tips
            # no longer sit in their window under its rear face: new screws,
            # cut again (codjiflo P2 on 27438d7).
            f"FOR A DISC TOOTH, REPEAT {s('disc-cluster-assembled', 2)}-"
            f"{s('disc-taps-transferred', 17)} WITH A NEW "
            f"{n['pd-rack-pinion']} DISC AND NEW {n[explode.DISC_SCREW]} "
            f"SCREWS ON THE SAME HUB, ITS PIN LEFT IN AND RIDING THE FLAT, THEN STEPS "
            f"{steps.step_number('disc-screws-cut')}, "
            f"{steps.step_number('disc-cluster-hung')}-"
            f"{steps.step_number('disc-cluster-shimmed')} AND FROM STEP {pose}.",
            f"FOR A LOOSE PLATE OR A FAULT EVERY KNOB TURN (A {KNOB_PINION} TOOTH), "
            f"{knob_cup_off_cited}",
            f"FOR EITHER, {knob_shaft_out}",
            f"REFIT A LOOSE PLATE AS {s('arm-plate-fitted', 18)}.",
            f"FOR A {KNOB_PINION} TOOTH, MAKE A NEW {n['pd-transgear-knob-shaft']} "
            "SHAFT.",
            # The cup, faced to its shaft's stand-out, and its screw are
            # renewed whenever the cup comes off (#2425).
            f"FOR EITHER, REPEAT STEP {steps.step_number('knob-stack-fitted')} WITH A NEW "
            f"{n['pd-transgear-knob-cup']} CUP AND "
            f"{n['pd-vn-transgear-knob-cup-screw']} SCREW, THEN FROM STEP {pose}.",
            f"FOR A FAULT ALL ROUND (ARM SETTING), REMOVE THE {n['pd-latch-hook']} "
            "HOOK.",
            f"FOR THE ARM SETTING, STRIP THE CLUSTER ({s('disc-cluster-hung', 4)} "
            f"BACK TO {s('disc-cluster-hung', 1)}), KEEPING ITS SHIMS.",
            f"FOR THE ARM SETTING, DO {s('hanger-pivoted', 15)}-"
            f"{s('hanger-pivoted', 16)}.",
            "FOR THE ARM SETTING, REBUILD FROM STEP "
            f"{steps.step_number('latch-pin-pressed')} WITH A NEW "
            f"{n['pd-transgear-arm']} ARM, {n['pd-transgear-arm-plate']} PLATE, {bush} BUSH, "
            f"{n['pd-transgear-pin']} PIN, {n['pd-transgear-pivot-spacer']} SPACER, "
            f"{n['pd-transgear-knob-shaft']} SHAFT, {n['pd-transgear-knob-cup']} CUP, "
            f"{n['pd-latch-hook']} HOOK, {n['pd-vn-transgear-latch-pin']} DOWEL, "
            f"{TRANSGEAR_QUANTITIES['pd-vn-transgear-arm-plate-locating-pin']} "
            f"{n['pd-vn-transgear-arm-plate-locating-pin']} DOWELS, "
            f"{TRANSGEAR_QUANTITIES['pd-vn-transgear-arm-plate-screw']} "
            f"{n['pd-vn-transgear-arm-plate-screw']} SCREWS, "
            f"{n['pd-vn-transgear-pivot-screw']} SCREW AND "
            f"{n['pd-vn-transgear-knob-cup-screw']} SCREW.",
            # The cluster, the collar and the bar's hook taps are reused.
            f"SKIP STEPS {steps.step_number('disc-screws-cut')}-"
            f"{steps.step_number('oil-hole-drilled')}, "
            f"{steps.step_number('collar-pins-pressed')}-"
            f"{steps.step_number('pilot-faced-to-fit')} AND "
            f"{s('latch-hook-fitted', 1)}-{s('latch-hook-fitted', 4)} IN THE REBUILD.",
        ),
        "collar-rear-faced-to-fit": (
            # #3106: step 29 is entered from 28 with the knob stack on (27D-27F)
            # and from 33 and 35 with it off, so it starts by putting it on and
            # takes all three off to face the collar.
            f"IN STEP {pose}'S POSE, REFIT ANY OF THE COLLAR, {knob_short} AND "
            f"THUMBNUT THAT IS OFF AS {s('fitup-pose-set', 3)}-{s('fitup-pose-set', 5)}.",
            f"READ THE {knob_short}'S FRONT FACE AGAINST THE {crank}'S WITH A "
            "STRAIGHTEDGE AND FEELERS.",
            knob_stack_off,
            "FACE THE COLLAR'S REAR UNTIL, REFITTED, THE "
            f"{knob_short}'S FRONT FACE STANDS {collar.FIT_UP_OFFSET_SET_TEXT} FORWARD "
            f"OF THE {crank_short}'S FRONT FACE {row_cite('offset-set')}.",
            "BREAK THE COLLAR'S REAR BORE MOUTH 45° TO ITS SHEET'S SIZE, THROUGH THE "
            f"{n['pd-vn-transgear-collar-flat-pin']} PIN'S CREST WITH IT.",
            f"CHECK: THE COLLAR BODY IS IN "
            f"{n['pd-transgear-drive-collar']}'S FITTED LIMITS.",
            # The shaft is in its bush here, its cup bonded on: a new collar
            # that does not fit it takes the cup off and the shaft out
            # before the shaft is cut or renewed to it (step 20's block).
            f"IF NOT, OR IF THE {s('collar-rear-faced-to-fit', 1)} READING WAS "
            f"ALREADY BEHIND {s('collar-rear-faced-to-fit', 3)}'S WINDOW, MAKE A NEW "
            f"{n['pd-transgear-drive-collar']} COLLAR.",
            "CHECK THE NEW COLLAR ON THE SHAFT AS "
            f"{s('collar-pins-pressed', 8)}.",
            f"IF IT BINDS OR SHAKES, {knob_cup_off_cited}",
            f"IF IT BINDS OR SHAKES, {knob_shaft_out}",
            f"IF IT BINDS OR SHAKES, DO {s('collar-pins-pressed', 9)}-"
            f"{s('collar-pins-pressed', 10)}.",
            f"REPEAT FROM STEP {steps.step_number('collar-pins-pressed')} WITH THE "
            f"NEW COLLAR, STEP {steps.step_number('knob-stack-fitted')} WITH A NEW "
            f"{n['pd-transgear-knob-cup']} CUP AND "
            f"{n['pd-vn-transgear-knob-cup-screw']} SCREW IF THE CUP CAME OFF.",
        ),
        "collar-shoulder-seated": (
            f"SEAT THE {n['pd-transgear-drive-collar']} COLLAR ON THE SHAFT, ITS PIN ON "
            "THE D-FLAT, "
            f"ITS REAR FACE ON THE {n['pd-transgear-knob-shaft']} PINION'S FRONT "
            "FACE.",
            f"FIT THE {knob} ON THE DRIVE DOWELS.",
            f"TIGHTEN THE {n['pd-transgear-thumbnut']} THUMBNUT BY HAND ON THE "
            f"{n['pd-transgear-drive-collar']} COLLAR'S "
            "PILOT. IT CLAMPS ONLY: NEVER TURN IT TO DRIVE THE KNOB.",
        ),
        "stud-end-cut": (
            f"CHECK: THE {n['pd-transgear-knob-shaft']} STUD END IS NOT PROUD OF "
            "THE THUMBNUT RIM.",
            f"IF PROUD, CUT IT {steps.inch_text(collar.STUD_CUT_BELOW_RIM[0], 3)} "
            f"TO {steps.inch_text(collar.STUD_CUT_BELOW_RIM[1], 3)} BELOW THE RIM "
            f"{row_cite('stud-cut')}.",
            f"CHAMFER THE CUT END {collar.STUD_RECHAMFER_DEG}\u00b0 TO THE THREAD "
            "MINOR.",
        ),
        "collar-disc-air-inspected": (
            "WITH THE ARM LATCHED, REMOVE THE LOCKS AND LIFT OFF THE PLATEN.",
            "PUSH THE DISC AND COLLAR TOWARD EACH OTHER AND TURN THE DISC ONE "
            f"FULL TURN ({disc.TEETH / KNOB_TEETH:g} KNOB TURNS).",
            f"CHECK: A {steps.COLLAR_DISC_AIR_TEXT.split()[0]} FEELER ENTERS "
            f"BETWEEN THE {n['pd-transgear-drive-collar']} COLLAR AND THE "
            f"{n['pd-rack-pinion']} DISC ALL ROUND THE OVERLAP (CLEARANCE "
            f"{steps.COLLAR_DISC_AIR_TEXT}, {row_cite('collar-disc-air')[1:-1]}).",
            # The feeler check above only passes or fails, so the shortfall the
            # re-face takes out is read here, before the stack comes off: the
            # true air is at least this reading, so facing the step by the
            # minimum less the reading leaves at least the minimum (integration
            # review, run 20261109T062834910Z).
            # #2629 (machinist rule 22): a pass exit to the platen's refit, so
            # the re-face branch after it needs no carried condition.
            f"IF {s('collar-disc-air-inspected', 2)} PASSES, SKIP "
            f"{s('collar-disc-air-inspected', 4)}-{s('collar-disc-air-inspected', 15)}.",
            "READ THE THICKEST FEELER ENTERING ALL ROUND (NONE: READ 0).",
            knob_stack_off,
            f"STRIP THE CLUSTER ({s('disc-cluster-hung', 4)} BACK TO "
            f"{s('disc-cluster-hung', 1)}), KEEPING ITS SHIMS.",
            f"SLIDE THE HUB AND DISC OFF THE {n['pd-transgear-feed-pinion']} NOSE "
            f"AS ONE, THEIR SCREWS LEFT IN, THE {hub_pin} PIN RIDING THE FLAT.",
            # The feeler check carries every feeler-accepted collar-air source:
            # the MHA-PD-10 step face (Q1 C), the MHA-PD-17 spigot end ⊥ .001
            # (owner ruling 2026-11-08 (Pedro), #2144 item 3.2) and the
            # MHA-PD-18 pin bore S ⊥ Ø.001 A, its projected axis zone (owner
            # ruling 2026-11-08 (Pedro), #2144 item 4.1). Setting the step
            # back recovers the air whichever face or axis closed it; the
            # spigot end is never re-faced, as that would take the disc off
            # its screws.
            # #2418: the sleeve is driven by its rear face on the stub's
            # shoulder, pushed there by the tailstock centre in the bore mouth;
            # a Ø1/8 mandrel's friction alone cannot drive a cut on steel, and
            # a collet on the Ø.313 boss would face the step toward the collet.
            f"MOUNT THE {n['pd-transgear-feed-pinion']} SLEEVE ON A STUB MANDREL AS "
            f"{s('disc-taps-transferred', 0)}-{s('disc-taps-transferred', 1)}, ITS "
            "REAR FACE HELD ON THE MANDREL'S "
            "FACED SHOULDER BY THE TAILSTOCK CENTRE IN ITS BORE MOUTH.",
            f"RE-FACE THE {n['pd-transgear-feed-pinion']} STEP FACE SQUARE BY "
            f"{steps.COLLAR_DISC_AIR_TEXT.split()[0]} LESS THE "
            f"{s('collar-disc-air-inspected', 4)} READING; "
            f"THE {n['pd-transgear-disc-hub']} SPIGOT END SEATS ON IT, SO HUB AND "
            "DISC SET BACK BY THAT AMOUNT.",
            "SLIDE THE HUB'S BORE BACK ON THE BOSS, ITS PIN RIDING THE FLAT, SPIGOT "
            "TO THE STEP FACE, MATCH MARKS TOGETHER.",
            f"REPEAT {s('disc-taps-transferred', 1)} AND "
            f"{s('disc-taps-transferred', 12)}-{s('disc-taps-transferred', 16)}.",
            "RE-DRILL THE HUB'S OIL HOLE INTO THE SLEEVE'S HOLE, AS STEP "
            f"{steps.step_number('oil-hole-drilled')}.",
            f"REPEAT STEPS {steps.step_number('disc-cluster-hung')}-"
            f"{steps.step_number('disc-cluster-shimmed')} AND "
            f"{steps.step_number('collar-shoulder-seated')}.",
            f"REPEAT {s('collar-disc-air-inspected', 1)}-"
            f"{s('collar-disc-air-inspected', 2)}.",
            # #3107 (Codjiflo P3 on 3e6318a026): each re-face takes the read
            # shortfall, so a still-short air is read and re-faced again.
            f"IF {s('collar-disc-air-inspected', 2)} STILL FAILS, REPEAT FROM "
            f"{s('collar-disc-air-inspected', 4)}.",
            f"REFIT THE PLATEN PER {s('platen-hung', 9)}-{s('guide-locks-set', 3)}.",
            f"IF {s('collar-disc-air-inspected', 9)} RE-FACED THE STEP, REPEAT "
            f"{s('loaded-rack-geometry-checked', 1)}-"
            f"{s('loaded-rack-geometry-checked', 4)}.",
        ),
        "fitup-accepted": (
            f"CHECK, IN STEP {pose}'S POSE: THE {knob_short}'S FRONT FACE STANDS "
            f"{steps.OFFSET_ACCEPT_TEXT} FORWARD OF THE {crank_short}'S FRONT FACE "
            f"(STRAIGHTEDGE AND FEELERS) {row_cite('offset-accept')}.",
            f"CHECK: KNOB END FLOAT {knob_window} {row_cite('knob-end-float')}.",
            # #2615: the knob wheel rides the collar's drive dowels and the nut
            # seats on the collar's pilot, so it shakes along them; it does not
            # turn free.
            f"CHECK: THE {knob_short} SHAKES UNDER THE NUT.",
            f"UNLATCH THE ARM: PULL THE {n['pd-latch-hook']} HOOK'S FINGER TAB ALONG "
            "THE ARM UNTIL THE HOOK CLEARS THE PIN.",
            "LOWER THE ARM.",
            "CHECK: RAISED AND RELEASED, THE ARM SWINGS FREE ON ITS PIVOT.",
            f"LATCH THE ARM: LIFT IT UNTIL THE {n['pd-vn-transgear-latch-pin']} PIN "
            f"SNAPS INTO THE {n['pd-latch-hook']} HOOK'S PIN HOLE.",
            f"CHECK: THE RING GAP READS {CLUSTER_FLOAT_VIEW_NAME} ON FEELERS.",
            "CHECK: THE DISC TURNS FREE.",
            "CHECK: COLLAR TO DISC CLEARANCE "
            f"{steps.COLLAR_DISC_AIR_TEXT}, AS "
            f"{s('collar-disc-air-inspected', 2)}.",
            # #2629 (machinist rule 22): a pass exit, then each failure's
            # follow-on sub-steps carry its check.
            "IF EVERY CHECK PASSES, GO TO STEP "
            f"{steps.step_number('chain-closed')}.",
            # A collar refaced at step 29 comes off with the thumbnut and the
            # knob first, and every step it sets is then redone (machinist
            # review of ab77adcbac).
            f"IF {s('fitup-accepted', 0)} OR {s('fitup-accepted', 1)} FAILS, "
            f"{knob_stack_off}",
            f"FOR {s('fitup-accepted', 0)}, REPEAT STEPS "
            f"{steps.step_number('collar-rear-faced-to-fit')}-"
            f"{steps.step_number('fitup-accepted')}.",
            f"FOR {s('fitup-accepted', 1)}, {knob_cup_off_cited}",
            f"FOR {s('fitup-accepted', 1)}, {knob_shaft_out}",
            # The shaft is sound; only the cup, faced to its stand-out, and
            # its screw are renewed (#2425).
            f"FOR {s('fitup-accepted', 1)}, REPEAT STEP "
            f"{steps.step_number('knob-stack-fitted')} WITH A NEW "
            f"{n['pd-transgear-knob-cup']} CUP AND "
            f"{n['pd-vn-transgear-knob-cup-screw']} SCREW, THEN FROM STEP {pose}.",
            f"IF {s('fitup-accepted', 2)} FAILS, REPEAT FROM STEP "
            f"{steps.step_number('collar-shoulder-seated')}.",
            f"IF {s('fitup-accepted', 5)} FAILS, ARM UNLATCHED, DO {pivot_remedied}.",
            f"IF A {s('hanger-pivoted', 11)}-{s('hanger-pivoted', 13)} CHECK THEN FAILS, DO "
            f"{s('fitup-mesh-remedied', 6)} AND {s('fitup-mesh-remedied', 15)}-"
            f"{s('fitup-mesh-remedied', 19)}.",
            f"FOR {s('fitup-accepted', 5)}, REPEAT {s('hook-pin-hole-match-drilled', 8)}-"
            f"{s('hook-pin-hole-match-drilled', 10)}, THEN FROM STEP {pose}.",
            f"IF {s('fitup-accepted', 7)} OR {s('fitup-accepted', 8)} FAILS, REPEAT "
            f"STEP {steps.step_number('disc-cluster-shimmed')}, THEN FROM STEP "
            f"{steps.step_number('collar-disc-air-inspected')}.",
            f"IF {s('fitup-accepted', 9)} FAILS, REPEAT STEP "
            f"{steps.step_number('collar-disc-air-inspected')}.",
        ),
        "chain-closed": (
            # Owner ruling 2026-11-20 (Pedro), #2429, option A: the 66-pitch
            # droop stays; the sheet says how the loop is cut. The spare
            # 18-tooth sprocket's loop is the BOM sheet's (BOM_CHAIN_ORDER_NOTE),
            # whose order length the cut is taken from. The two link rows share
            # one Number, so the items name them. Cut, loop and join are one
            # action each (machinist review of 592b20079f).
            f"CUT {chain.LINK_COUNT - 1} PITCHES "
            f"({CHAIN_QUANTITIES['sh-vn-chain-link--InnerLink']} INNER, ITEM "
            f"{SHARED_NUMBER_ITEMS['sh-vn-chain-link--InnerLink']}, AND "
            f"{CHAIN_QUANTITIES['sh-vn-chain-link--OuterLink']} OUTER LINKS, ITEM "
            f"{SHARED_NUMBER_ITEMS['sh-vn-chain-link--OuterLink']}) FROM THE ANSI #25 "
            "CHAIN WITH A #25 CHAIN BREAKER.",
            f"LOOP THEM OVER THE {knob_short} AND THE {crank_short}, SLACK RUN "
            "HANGING FREE; NO TENSIONING.",
            f"JOIN THE ENDS WITH THE {n['pd-vn-chain-connecting-link']} #25 "
            f"CONNECTING LINK (MCMASTER {_SKU['pd-vn-chain-connecting-link']}), "
            "ITS CLIP'S CLOSED END LEADING IN THE DIRECTION OF TRAVEL; IT MAKES "
            f"THE LOOP {chain.LINK_COUNT} PITCHES.",
        ),
        "chain-run-accepted": (
            "TURN THE CRANK 2 TURNS EACH WAY.",
            "CHECK: THE CHAIN SEATS ON EVERY TOOTH OF BOTH WHEELS WITHOUT "
            "CLIMBING OR A TIGHT SPOT.",
            "CHECK: THE SLACK RUN TOUCHES NOTHING.",
            # #2629 (machinist rule 22): a pass exit past the remedy.
            f"IF BOTH CHECKS PASS, SKIP {s('chain-run-accepted', 4)}-"
            f"{s('chain-run-accepted', 7)}.",
            f"OPEN THE {n['pd-vn-chain-connecting-link']} LINK.",
            "LIFT THE CHAIN OFF.",
            knob_stack_off,
            f"REPEAT STEPS {steps.step_number('collar-rear-faced-to-fit')}-"
            f"{steps.step_number('chain-run-accepted')}.",
            # As shipped: latched, the feed in mesh (delegated ruling
            # 2026-11-07 (Main), no precedent; owner review #2144; pending
            # owner confirmation).
            "LEAVE THE ARM LATCHED FOR SHIPPING.",
            f"CHECK: THE {n['pd-vn-transgear-latch-pin']} PIN IS THROUGH THE "
            f"{n['pd-latch-hook']} HOOK.",
            "CHECK: THE FEED IS IN MESH.",
        ),
    }


# The setting table (SETTING_TABLE_SHEET): every measurable setting or
# acceptance the steps print that is not a single model dimension on a
# setting detail: feeler, indicator and gauge readings, struck marks, cut
# windows from a flush or zero floor, the engaged feed's travel, and the
# settings measured from parts this model does not carry (the MHA-FR-01 deck)
# or hides inside a part (the pivot screw's tip in the bar's tap, the knob
# cup's pilot depth).  Cells are the steps' own values.
SETTING_TABLE_TITLE = (
    "SETTING TABLE: SETTINGS AND CHECKS NOT DIMENSIONED ON DETAILS F, H, J, L "
    f"(SHEET {SHEET_NAMES.index(SETTING_DETAIL_SHEET) + 1})"
)
SETTING_TABLE_HEADER = ("ROW", "STEP", "SETTING OR CHECK", "SET TO / ACCEPT", "CHECK WITH")


def setting_table_rows(
    *, operating_domain: RackOperatingDomain
) -> tuple[tuple[str, ...], ...]:
    """The setting table's rows in SETTING_ROW_KEYS order, each the step's
    own value with the step that sets or checks it and its instrument."""
    n = _N
    s = sub_step
    knob_short = sprocket_name(sprocket.KNOB_CONFIG, numbered=False)
    crank_short = sprocket_name(sprocket.CRANK_CONFIG, numbered=False)
    offset = f"{knob_short} FRONT FACE FORWARD OF THE {crank_short}'S"
    cells = {
        "bar-top": (
            s("bar-clamped", 1),
            f"BAR TOP ABOVE THE {FRAME_BASE} BASE DECK, BOTH COLUMNS",
            steps.BAR_TOP_ABOVE_DECK_TEXT,
            "HEIGHT GAUGE ON THE DECK",
        ),
        "lock-mark-edge": (
            s("platen-hung", 3),
            f"{n['pd-guide-lock']} MARKS FROM ITS GUIDE-SIDE EDGE",
            _mark_window(guide_lock.HOLE_Y),
            "CALIPERS",
        ),
        "lock-mark-left": (
            s("platen-hung", 4),
            "LEFT MARK FROM THE LOCK'S LEFT EDGE",
            _mark_window(guide_lock.HOLE_XY[0][0]),
            "CALIPERS",
        ),
        "lock-mark-right": (
            s("platen-hung", 4),
            "RIGHT MARK FROM THE LOCK'S LEFT EDGE",
            _mark_window(guide_lock.HOLE_XY[1][0]),
            "CALIPERS",
        ),
        "lock-gap": (
            s("lock-seats-faced", 1),
            "EACH LOCK'S FRONT FACE TO THE BAR'S BACK FACE",
            LOCK_GAP_WINDOW,
            "FEELERS",
        ),
        "disc-tir": (
            f"{s('disc-taps-transferred', 2)}, {s('disc-taps-transferred', 12)}",
            f"{n['pd-rack-pinion']} O.D., THEN {DISC_TIR_SAMPLE_SPACES} SPACES, ON THE "
            "MANDREL",
            f"{DISC_TIR_TEXT} TIR MAX",
            "DIAL INDICATOR, "
            f"\u00d8{steps.inch_text(disc.TOOTH_SPACE_GAUGE_PIN_DIA_MM, 3)} PIN",
        ),
        # The bush's two step-11 acceptances are on no view (machinist
        # review r13, #2425, two runs).
        "bush-seated": (
            s("pin-pressed", 11),
            f"{n['pd-transgear-knob-bush']} SHOULDER ON THE "
            f"{n['pd-transgear-arm-plate']} FRONT FACE",
            f"{steps.inch_text(knob_bush.SHOULDER_SEAT_GAP_MAX, 3)} DOES NOT ENTER",
            "FEELER",
        ),
        "bush-reamed": (
            s("pin-pressed", 14),
            f"{n['pd-transgear-knob-bush']} BORE, REAMED IN THE PLATE",
            "TURNS FREE, NO SHAKE",
            f"{n['pd-transgear-knob-shaft']} JOURNAL",
        ),
        "reducer-shake": (
            f"{s('arm-plate-located', 12)}, {s('arm-plate-fitted', 20)}, "
            f"{s('fitup-pose-set', 9)}",
            "DISC SHAKE AT THE TIP OF THE TOOTH IN MESH",
            f"THE NEEDLE MOVES, {steps.inch_max_text(REDUCER_SHAKE_MAX_MM, 3)}",
            f"DIAL INDICATOR, {REDUCER_DIAL_STATIONS} PLACES",
        ),
        # The located step's one move of the table (owner ruling 2026-11-24,
        # audit part 2 question C1), whole DRO counts derived in
        # pd_paper_drive_knob_setting_spec.
        "trial-move": (
            s("arm-plate-located", 17),
            f"TABLE MOVED TOWARD S FROM {KNOB_SETTING_VIEW_NAME}'S SETTING"
            if KNOB_TRIAL_AWAY_MOVE_TEXT is None
            else f"TABLE MOVED AWAY OR TOWARD S FROM {KNOB_SETTING_VIEW_NAME}'S SETTING",
            KNOB_TRIAL_MOVE_TEXT,
            "DRO",
        ),
        "plate-screw-tips": (
            s("arm-plate-screws-cut", 1),
            f"{n['pd-vn-transgear-arm-plate-screw']} TIPS PROUD OF THE ARM FRONT",
            f"FLUSH TO {steps.inch_text(joints.PLATE_SCREW_CUT_PROUD_MAX, 3)}",
            "STRAIGHTEDGE AND FEELERS",
        ),
        "pivot-tip": (
            s("arm-plate-screws-cut", 6),
            f"{n['pd-vn-transgear-pivot-screw']} TIP BELOW THE BAR FRONT FACE",
            steps.inch_window(pivot_screw.TIP_RECESS, 3, " TO "),
            "CALIPER DEPTH ROD",
        ),
        "disc-screw-tips": (
            str(steps.step_number("disc-screws-cut")),
            f"{n[explode.DISC_SCREW]} TIPS BELOW THE DISC REAR FACE",
            steps.inch_window(disc_screw.TIP_BELOW_REAR_FACE, 3, " TO "),
            "STRAIGHTEDGE AND FEELERS",
        ),
        "collar-pilot": (
            s("pilot-faced-to-fit", 0),
            f"COLLAR PILOT PROUD OF EACH {n['pd-transgear-removable']} WHEEL",
            collar.PILOT_PROUD_TEXT,
            "STRAIGHTEDGE AND FEELERS",
        ),
        "cup-set": (
            s("knob-stack-fitted", 3),
            f"{n['pd-transgear-knob-cup']} PILOT DEPTH UNDER THE JOURNAL STAND-OUT",
            steps.inch_text(knob_shaft.END_FLOAT, 3),
            "CALIPER DEPTH ROD",
        ),
        "engaged-feed": (
            s("hanger-meshed", 2),
            f"ENGAGED FEED: RIGHT RACK END (SHEET 1) TO {n['pd-transgear-pin']} AXIS",
            engaged_feed_window(operating_domain),
            "STEEL RULE",
        ),
        "crest-level": (
            s("loaded-rack-geometry-checked", 13),
            "RACK CRESTS, ONE END AGAINST THE OTHER",
            f"WITHIN {steps.inch_text(steps.LEVEL_RACK_CREST_DRIFT, 3)}",
            "HEIGHT GAUGE",
        ),
        "tooth-centred": (
            s("fitup-pose-set", 6),
            f"DISC TOOTH IN A {KNOB_PINION} GAP, AT THE PITCH CIRCLE",
            f"CENTRED WITHIN {REDUCER_CLOCK_TEXT}",
            "TEST INDICATOR, GAUGE PIN",
        ),
        "offset-set": (
            s("collar-rear-faced-to-fit", 3),
            offset,
            collar.FIT_UP_OFFSET_SET_TEXT,
            "STRAIGHTEDGE AND FEELERS",
        ),
        "offset-accept": (
            s("fitup-accepted", 0),
            offset,
            steps.OFFSET_ACCEPT_TEXT,
            "STRAIGHTEDGE AND FEELERS",
        ),
        "stud-cut": (
            s("stud-end-cut", 1),
            f"{n['pd-transgear-knob-shaft']} STUD BELOW THE THUMBNUT RIM, IF CUT",
            steps.inch_window(collar.STUD_CUT_BELOW_RIM, 3, " TO "),
            "CALIPER DEPTH ROD",
        ),
        "collar-disc-air": (
            f"{s('collar-disc-air-inspected', 2)}, {s('fitup-accepted', 9)}",
            "COLLAR TO DISC, ALL ROUND THE OVERLAP",
            steps.COLLAR_DISC_AIR_TEXT,
            "FEELER",
        ),
        "knob-end-float": (
            f"{s('knob-stack-fitted', 11)}, {s('fitup-accepted', 1)}",
            f"KNOB END FLOAT, CUP TO {n['pd-transgear-knob-bush']} REAR FACE",
            KNOB_END_FLOAT_WINDOW,
            "FEELERS",
        ),
    }
    if tuple(cells) != SETTING_ROW_KEYS:
        raise AssertionError("the setting table's rows follow SETTING_ROW_KEYS")
    return tuple((str(SETTING_ROW[key]), *cells[key]) for key in SETTING_ROW_KEYS)


def _printed(key: str, texts: tuple[str, ...]) -> list[tuple[str, str]]:
    """``key``'s (head, text) pairs: ``9.`` alone, or ``9A.``, ``9B.``, ..."""
    if len(texts) == 1:
        return [(f"{steps.step_number(key)}.", texts[0])]
    return [(f"{sub_step(key, index)}.", text) for index, text in enumerate(texts)]


def _wrapped_sub_steps(key: str, texts: tuple[str, ...]) -> list[list[str]]:
    """``key``'s printed sub-steps, each wrapped under its own head."""
    return [
        textwrap.wrap(
            part,
            width=FITUP_LINE_WIDTH,
            initial_indent=f"{head} ",
            subsequent_indent=" " * (len(head) + 1),
            break_on_hyphens=False,
            break_long_words=False,
        )
        for head, part in _printed(key, texts)
    ]


@dataclass(frozen=True)
class StepSlot:
    """One step column's field: its sheet, its note's top-left corner and
    the lowest height its last line may reach."""

    sheet: str
    xy: tuple[float, float]
    bottom: float

    @property
    def capacity(self) -> int:
        """Lines that end strictly above ``bottom``."""
        return int((self.xy[1] - self.bottom) / STEP_LINE_PITCH - 1e-9)


_TITLE_BLOCK_TOP = DRAWING_TEMPLATES[SPEC.layout].title_block_top_m
# The step columns in reading order. Sheet 4's one column stands left of the
# platen exploded view, its caption one line under the steps; DETAIL E fills
# sheet 6's left column below its steps and DETAIL K sheet 7's right column.
STEP_SLOTS: tuple[StepSlot, ...] = (
    StepSlot("PLATEN AND SUPPORT", PLATEN_NOTE_XY, _TITLE_BLOCK_TOP + 2 * STEP_LINE_PITCH),
    StepSlot("ASSEMBLY AND FIT-UP", FITUP_NOTE_XY[0], FITUP_NOTE_LIMITS[0][1]),
    StepSlot("ASSEMBLY AND FIT-UP", FITUP_NOTE_XY[1], FITUP_NOTE_LIMITS[1][1]),
    StepSlot(CLUSTER_FLOAT_SHEET, FITUP_NOTE_XY[0], CLUSTER_FLOAT_FIELD_TOP),
    StepSlot(CLUSTER_FLOAT_SHEET, FITUP_NOTE_XY[1], FITUP_NOTE_LIMITS[1][1]),
    StepSlot(KNOB_SETTING_SHEET, FITUP_NOTE_XY[0], FITUP_NOTE_LIMITS[0][1]),
    StepSlot(KNOB_SETTING_SHEET, FITUP_NOTE_XY[1], KNOB_SETTING_FIELD_TOP),
    StepSlot("ASSEMBLY AND FIT-UP (CONT. 3)", FITUP_NOTE_XY[0], FITUP_NOTE_LIMITS[0][1]),
    StepSlot("ASSEMBLY AND FIT-UP (CONT. 3)", FITUP_NOTE_XY[1], FITUP_NOTE_LIMITS[1][1]),
    StepSlot("ASSEMBLY AND FIT-UP (CONT. 4)", FITUP_NOTE_XY[0], FITUP_NOTE_LIMITS[0][1]),
    StepSlot("ASSEMBLY AND FIT-UP (CONT. 4)", FITUP_NOTE_XY[1], FITUP_NOTE_LIMITS[1][1]),
    StepSlot("ASSEMBLY AND FIT-UP (CONT. 5)", FITUP_NOTE_XY[0], FITUP_NOTE_LIMITS[0][1]),
    StepSlot("ASSEMBLY AND FIT-UP (CONT. 5)", FITUP_NOTE_XY[1], FITUP_NOTE_LIMITS[1][1]),
    StepSlot("ASSEMBLY AND FIT-UP (CONT. 6)", FITUP_NOTE_XY[0], FITUP_NOTE_LIMITS[0][1]),
    StepSlot("ASSEMBLY AND FIT-UP (CONT. 6)", FITUP_NOTE_XY[1], FITUP_NOTE_LIMITS[1][1]),
    StepSlot("CHAIN FIT-UP", FITUP_NOTE_XY[0], FITUP_NOTE_LIMITS[0][1]),
    StepSlot("CHAIN FIT-UP", FITUP_NOTE_XY[1], FITUP_NOTE_LIMITS[1][1]),
)
if {slot.sheet for slot in STEP_SLOTS} != set(
    SHEET_NAMES[3 : SHEET_NAMES.index(SETTING_DETAIL_SHEET)]
):
    raise AssertionError("every steps sheet takes step columns")
# A step that works from a lettered view opens on that view's sheet: the
# packing closes the column before it when it would start a sheet earlier.
STEP_START_SHEETS: dict[str, str] = {"arm-plate-located": KNOB_SETTING_SHEET}
# Each section's first step: (title for continued columns, heading).
STEP_SECTIONS: dict[str, tuple[str, str]] = {
    steps.SEQUENCE[0]: ("PLATEN AND SUPPORT", "PLATEN AND SUPPORT"),
    FITUP_TRANSGEAR_KEY: ("THE TRANSGEAR", "THE TRANSGEAR"),
    FITUP_CHAIN_KEY: (
        "CHAIN FIT-UP",
        f"CHAIN FIT-UP, STEPS 1 TO {steps.step_number(FITUP_CHAIN_KEY) - 1} DONE; "
        f"CRANK SIDE DONE PER {steps.CRANK_SIDE_REF}",
    ),
}


@dataclass(frozen=True)
class StepColumn:
    sheet: str
    xy: tuple[float, float]
    text: str


def _wrapped_heading(heading: str) -> list[str]:
    return textwrap.wrap(
        heading,
        width=FITUP_LINE_WIDTH,
        break_on_hyphens=False,
        break_long_words=False,
    )


def pack_step_columns(text: dict[str, tuple[str, ...]]) -> tuple[StepColumn, ...]:
    """Fill STEP_SLOTS in reading order, one blank line between numbered
    steps; a column breaks only between sub-steps, never inside one.

    A section's heading leads its first step; a column that opens mid-section
    leads with the section's title and "(CONT.)". A step in STEP_START_SHEETS
    opens on its view's sheet, closing the column before it early. Every slot
    must take steps, so no sheet is left without them. The columns are
    balanced: each holds at most the smallest line count that still fits
    every step into the slots, so no sheet ends as a short block beside an
    empty field (rule 15; round 3 found the last sheet's 12 lines bunched in
    one corner)."""
    if set(text) != set(steps.SEQUENCE):
        raise AssertionError("paper-drive step text must cover exactly the sequence")
    for cap in range(1, max(slot.capacity for slot in STEP_SLOTS) + 1):
        columns = _packed_columns(text, cap)
        if columns is not None:
            return columns
    raise RuntimeError("the paper-drive steps overflow STEP_SLOTS")


def _packed_columns(
    text: dict[str, tuple[str, ...]], cap: int
) -> tuple[StepColumn, ...] | None:
    """The steps packed with each slot holding at most ``cap`` lines, or None
    when they do not fit or leave a slot empty."""
    columns: list[StepColumn] = []
    slots = iter(STEP_SLOTS)
    slot = next(slots)
    lines: list[str] = []
    title = ""
    for key in steps.SEQUENCE:
        section = STEP_SECTIONS.get(key)
        if section is not None:
            title = section[0]
        start_sheet = STEP_START_SHEETS.get(key)
        if start_sheet is not None and slot.sheet != start_sheet:
            if not lines:
                return None
            columns.append(StepColumn(slot.sheet, slot.xy, "\n".join(lines)))
            slot = next(slots, None)
            if slot is None or slot.sheet != start_sheet:
                return None
            lines = []
        for index, unit in enumerate(_wrapped_sub_steps(key, text[key])):
            starts_step = index == 0

            def lead(open_lines: list[str]) -> list[str]:
                if starts_step and section is not None:
                    heading = _wrapped_heading(section[1])
                elif not open_lines:
                    heading = _wrapped_heading(f"{title} (CONT.)")
                else:
                    heading = []
                return ([""] if open_lines and starts_step else []) + heading

            added = lead(lines) + unit
            if lines and len(lines) + len(added) > min(slot.capacity, cap):
                columns.append(StepColumn(slot.sheet, slot.xy, "\n".join(lines)))
                slot = next(slots, None)
                if slot is None:
                    return None
                lines = []
                added = lead(lines) + unit
            if len(added) > min(slot.capacity, cap):
                return None
            # Its first sub-step spilling past the view's sheet opens it elsewhere.
            if starts_step and start_sheet is not None and slot.sheet != start_sheet:
                return None
            lines += added
    columns.append(StepColumn(slot.sheet, slot.xy, "\n".join(lines)))
    if len(columns) != len(STEP_SLOTS):
        return None
    return tuple(columns)


@dataclass(frozen=True)
class StepNotes:
    """Explicitly formatted note fields, not a module-global qualification."""

    columns: tuple[StepColumn, ...]
    setting_rows: tuple[tuple[str, ...], ...]

    @property
    def platen_steps(self) -> str:
        """Sheet 4's one column, beside the platen exploded view."""
        first = self.columns[0]
        if first.sheet != "PLATEN AND SUPPORT":
            raise AssertionError("the steps start beside the platen exploded view")
        return first.text

    @property
    def fitup_steps(self) -> str:
        """Every column, in reading order."""
        return "\n".join(column.text for column in self.columns)

    @property
    def exploded_caption_xy(self) -> tuple[float, float]:
        """One blank line under the actual steps, at default 4.5 mm line pitch."""
        return (
            PLATEN_NOTE_XY[0],
            PLATEN_NOTE_XY[1] - (len(self.platen_steps.splitlines()) + 1) * STEP_LINE_PITCH,
        )


def format_step_notes(*, operating_domain: RackOperatingDomain) -> StepNotes:
    """Format the sheet steps and the setting table around a supplied
    engaged-feed window; the table must fit its sheet's width."""
    rows = setting_table_rows(operating_domain=operating_domain)
    width = sum(table_column_widths(SETTING_TABLE_HEADER, rows))
    if SETTING_TABLE_TOP_LEFT[0] + width > SETTING_TABLE_RIGHT_LIMIT:
        raise AssertionError(f"the setting table is {width * 1000:.1f} mm wide")
    return StepNotes(pack_step_columns(_step_text(operating_domain=operating_domain)), rows)


def require_step_notes() -> StepNotes:
    """Guard the full paper sweep on the finite rack before printing."""
    return format_step_notes(operating_domain=rack_setup.feed_rack_operating_domain())


def _scale_suffix(view_scale: tuple[float, float], sheet_scale: tuple[float, float]) -> str:
    """A view caption states its scale only when it differs from the sheet's."""
    return "" if view_scale == sheet_scale else f" {_scale_text(view_scale)}"


# The exploded view's caption at each scale it may take.
EXPLODED_CAPTIONS = {
    scale: f"PLATEN AND SUPPORT EXPLODED"
    f"{_scale_suffix(scale, SHEET_SCALES['PLATEN AND SUPPORT'])}; "
    f"BOM: SHEET {SHEET_NAMES.index('BILL OF MATERIALS') + 1}"
    for scale in EXPLODED_SCALE_LADDER
}
_SPARE_CONFIGS = [
    name
    for name, _teeth in sprocket.CONFIGS
    if name not in (sprocket.CRANK_CONFIG, sprocket.KNOB_CONFIG)
]
if len(_SPARE_CONFIGS) != 1:
    raise AssertionError("sheet 1 names one crank, one knob and one spare sprocket")
# Sheet 1's feed reference, the sprockets by plain name (machinist review
# round 8, rule 26: the configuration codes read as undefined).
PAPER_FEED_TEXT = (
    f"FEED SETUP: {sprocket.CRANK_TEETH}-TOOTH CRANK / {sprocket.KNOB_TEETH}-TOOTH "
    "KNOB SPROCKET.\n"
    f"PLATEN TRAVEL {steps.PAPER_TRAVEL_PER_CRANK_TEXT} PER CRANK REV (REF)."
)
# Sheet 1, at each scale its isometric may take: which removable is which,
# and where every other item balloons.
ASSEMBLED_CAPTIONS = {
    scale: "\n".join(
        (
            "\n".join(
                textwrap.wrap(
                    f"ISOMETRIC{_scale_suffix(scale, SHEET_SCALES['ASSEMBLED VIEWS'])}: THE "
                    f"{sprocket_name(_SPARE_CONFIGS[0])} ON THE BASE DECK IS A "
                    f"SPARE, STORED LOOSE WITH THE SPARE "
                    f"{_N['pd-vn-transgear-cluster-shim']} SHIMS IN ITS BORE; "
                    f"THE {sprocket_name(sprocket.KNOB_CONFIG, numbered=False)} IS ON "
                    f"THE KNOB, THE {sprocket.CRANK_TEETH}-TOOTH ON THE "
                    "CRANK. PLATEN AND SUPPORT ITEMS: SHEET "
                    f"{SHEET_NAMES.index('PLATEN AND SUPPORT') + 1}; TRANSGEAR "
                    f"ITEMS: SHEETS {SHEET_NAMES.index('TRANSGEAR VIEWS') + 1} AND "
                    f"{SHEET_NAMES.index('TRANSGEAR EXPLODED') + 1}.",
                    width=FITUP_LINE_WIDTH,
                )
            ),
            PAPER_FEED_TEXT,
        )
    )
    for scale in ISO_SCALE_LADDER
}
TRANSGEAR_CAPTION = (
    f"TRANSGEAR; EXPLODED: SHEET {SHEET_NAMES.index('TRANSGEAR EXPLODED') + 1};\n"
    f"ASSEMBLY AND FIT-UP: SHEETS {SHEET_NAMES.index('PLATEN AND SUPPORT') + 1} "
    f"TO {SHEET_NAMES.index('CHAIN FIT-UP') + 1}; "
    f"BOM: SHEET {SHEET_NAMES.index('BILL OF MATERIALS') + 1}"
)
# Sheet 3's caption, right of the knob-stack view and under the cluster's.
TRANSGEAR_EXPLODED_CAPTION = "\n".join(
    textwrap.wrap(
        "TRANSGEAR EXPLODED, ISOMETRIC: THE ARM WITH ITS PLATE AND THE KNOB "
        "STACK ON ITS SHAFT, AND THE DISC CLUSTER ON ITS PIN, EACH PART DRAWN "
        "APART ALONG ITS AXIS IN THE ORDER IT GOES ON. ARM PIVOT: SECTION A-A, "
        f"SHEET {SHEET_NAMES.index('TRANSGEAR VIEWS') + 1}; LATCH HOOK: SHEET "
        f"{SHEET_NAMES.index('TRANSGEAR VIEWS') + 1}. ASSEMBLY: SHEETS "
        f"{SHEET_NAMES.index('PLATEN AND SUPPORT') + 1} TO "
        f"{SHEET_NAMES.index('CHAIN FIT-UP') + 1}; BOM: SHEET "
        f"{SHEET_NAMES.index('BILL OF MATERIALS') + 1}.",
        width=TRANSGEAR_EXPLODED_CAPTION_WIDTH,
        break_on_hyphens=False,
    )
)
FITUP_REFERENCE_CAPTION = (
    "REFERENCE; ITEMS: SHEETS 1 TO "
    f"{SHEET_NAMES.index('PLATEN AND SUPPORT') + 1}"
)


# --- the SETTING DETAILS sheet (rule 22) --------------------------------------
# Each lettered detail shows its hidden setting sketch
# (pd_paper_drive_setting_details_spec) on only the parts it measures,
# cropped to a circle; its boundary is drawn on one of two cropped reference
# views on the same sheet (rule 9): a side view for F, H and J and a front
# view for L.  The sheet takes the details' 5:1; the others state their scale.
SETTING_DETAILS_BY_LETTER = {detail.letter: detail for detail in setting_details.DETAILS}
SETTING_DETAIL_CENTRES = {
    "F": (0.180, 0.205),
    "H": (0.265, 0.205),
    "J": (0.355, 0.200),
    "L": (0.180, 0.105),
}
if set(SETTING_DETAIL_CENTRES) != set(SETTING_DETAILS_BY_LETTER):
    raise AssertionError("every setting detail takes a place on its sheet")
SETTING_CAPTION_DROP = 0.004
SETTING_ARROWS_OUTSIDE = 1  # swDimensionArrowsSide_e.swDimArrowsOutside
# A dimension shorter than this on the sheet takes its arrows outside.
SETTING_ARROWS_OUTSIDE_BELOW = 0.015


def _steps_label(keys: tuple[str, ...]) -> str:
    numbers = sorted({steps.step_number(key) for key in keys})
    if len(numbers) == 1:
        return f"STEP {numbers[0]}"
    return "STEPS " + ", ".join(str(number) for number in numbers)


# A caption line is at most 26 characters (about 71 mm): the details stand
# 85 mm apart, and the review of run
# 20261117T144118108Z-771678f99db440ccbcec03874c9b1aca found one-line titles
# printing over the next caption and through the border.
SETTING_CAPTION_WIDTH = 26
# DETAIL H carries the bond 13G points to (owner ruling 2026-11-20 (Pedro),
# #2497: retaining compound only on the arm, which already carries DETAIL K's
# jig-boring); a latch dowel that slides in at 10B, before that jig-boring,
# renews the arm (Codjiflo r2 on #3486). Its prep and where the compound
# goes are the machinist review's (592b20079f); as a note, 13G stays one
# action (review of 70917f0316). The column under H's caption is empty down
# to the title block, clear of DETAIL L left and DETAIL J right.
BOND_NOTE = (
    "BOND NOTE ("
    + ", ".join(sub_step(key, index) for key, index in BOND_NOTE_SUB_STEPS)
    + "): PULL THE DOWEL. DEGREASE IT "
    "AND ITS HOLE. COAT THE DOWEL, NOT THE HOLE, WITH LOCTITE 638. PRESS IT "
    "BACK AT ONCE TO ITS STEP'S PROUD. CURE 24 H."
)
SETTING_DETAIL_NOTES = {"H": BOND_NOTE}
SETTING_DETAIL_CAPTIONS = {
    detail.letter: "\n".join(
        (
            f"{detail.view_name}"
            f"{_scale_suffix(detail.scale, SHEET_SCALES[SETTING_DETAIL_SHEET])} "
            f"({_steps_label(detail.step_keys)})",
            *textwrap.wrap(detail.title, SETTING_CAPTION_WIDTH),
            *(
                (
                    "",
                    *textwrap.wrap(
                        SETTING_DETAIL_NOTES[detail.letter], SETTING_CAPTION_WIDTH
                    ),
                )
                if detail.letter in SETTING_DETAIL_NOTES
                else ()
            ),
        )
    )
    for detail in setting_details.DETAILS
}


@dataclass(frozen=True)
class SettingParent:
    """A cropped reference view carrying the boundaries of ``letters``; it is
    itself DETAIL ``letter`` of sheet 1's view in its orientation, whose
    boundary letter stands at ``sheet1_letter_offset`` from that circle's
    centre (rule 9; #3110)."""

    name: str
    letter: str
    orientation: str
    scale: tuple[float, float]
    centre: tuple[float, float]
    radius: float
    model_centre: tuple[float, float, float]
    letters: tuple[str, ...]
    sheet1_letter_offset: tuple[float, float]


def _view_plane_mm(orientation: str, point: tuple[float, float, float]) -> tuple[float, float]:
    """A machine point in a parent's view plane (mm), for fit checks only."""
    return (point[2], point[1]) if orientation == "*Right" else (point[0], point[1])


def _boundary_radius(detail: setting_details.SettingDetail, scale: tuple[float, float]) -> float:
    """A detail's crop circle on a parent at ``scale`` (sheet m)."""
    return detail.radius * detail.scale[1] / detail.scale[0] * scale[0] / scale[1]


_SIDE_CENTRES = [
    _view_plane_mm("*Right", SETTING_DETAILS_BY_LETTER[letter].centre)
    for letter in ("F", "H", "J")
]
SETTING_PARENTS = (
    SettingParent(
        name="RIGHT SIDE",
        letter="M",
        orientation="*Right",
        scale=(1.0, 1.0),
        centre=(0.075, 0.200),
        radius=0.032,
        model_centre=(
            0.0,
            (min(v for _u, v in _SIDE_CENTRES) + max(v for _u, v in _SIDE_CENTRES)) / 2.0,
            (min(u for u, _v in _SIDE_CENTRES) + max(u for u, _v in _SIDE_CENTRES)) / 2.0,
        ),
        letters=("F", "H", "J"),
        # In the gap right of the knob stack, between its two bosses.
        sheet1_letter_offset=(0.016, 0.0),
    ),
    SettingParent(
        name="FRONT",
        letter="P",
        orientation="*Front",
        scale=(1.0, 2.0),
        centre=(0.075, 0.090),
        radius=0.025,
        model_centre=(*setting_details.on_arm(105.0), arm_geometry.PIN_MACHINE_Z),
        letters=("L",),
        # Left of the arm tip, clear of the bar and the crank lead.
        sheet1_letter_offset=(-0.020, 0.0),
    ),
)
SETTING_LETTER_GAP = 0.005
for _parent in SETTING_PARENTS:
    _parent_m_per_mm = _parent.scale[0] / _parent.scale[1] / 1000.0
    for _letter in _parent.letters:
        _child = SETTING_DETAILS_BY_LETTER[_letter]
        if _child.orientation != _parent.orientation:
            raise AssertionError(f"DETAIL {_letter}'s parent must share its orientation")
        _reach = math.dist(
            _view_plane_mm(_parent.orientation, _child.centre),
            _view_plane_mm(_parent.orientation, _parent.model_centre),
        ) * _parent_m_per_mm + _boundary_radius(_child, _parent.scale)
        if _reach > _parent.radius - 0.002:
            raise AssertionError(f"DETAIL {_letter}'s boundary leaves its parent's crop")
SETTING_PARENT_CAPTIONS = {
    parent.name: (
        f"DETAIL {parent.letter}"
        f"{_scale_suffix(parent.scale, SHEET_SCALES[SETTING_DETAIL_SHEET])} "
        f"(REFERENCE): {'DETAILS' if len(parent.letters) > 1 else 'DETAIL'} "
        + ", ".join(parent.letters)
    )
    for parent in SETTING_PARENTS
}


def setting_parent_sheet1_radius(parent: SettingParent) -> float:
    """A reference view's crop circle on sheet 1's 1:4 views (sheet m)."""
    return max(
        PARENT_BOUNDARY_MIN_RADIUS,
        parent.radius * parent.scale[1] / parent.scale[0] * 1000.0 * _ASSEMBLED_M_PER_MM,
    )


# The setting table hangs from the sheet's top-left note corner and must stand
# inside the inner border's width.
SETTING_TABLE_TOP_LEFT = (0.018, 0.262)
SETTING_TABLE_RIGHT_LIMIT = 0.418


def sheet_texts(notes: StepNotes) -> tuple[str, ...]:
    """Every explicitly formatted package text besides the BOM's own cells."""
    return (
        *(column.text for column in notes.columns),
        *EXPLODED_CAPTIONS.values(),
        *ASSEMBLED_CAPTIONS.values(),
        TRANSGEAR_CAPTION,
        TRANSGEAR_EXPLODED_CAPTION,
        FITUP_REFERENCE_CAPTION,
        BOM_REFERENCE_CAPTION,
        PIVOT_LOCATOR_CAPTION,
        SETTING_TABLE_TITLE,
        *SETTING_DETAIL_CAPTIONS.values(),
        *SETTING_PARENT_CAPTIONS.values(),
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
    for name, component in by_name(assembly.GetComponents(True)):
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
        for stem, quantity in {
            **TRANSGEAR_QUANTITIES, **CHAIN_QUANTITIES, **PLATEN_QUANTITIES
        }.items()
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
    new_project_drawing(
        adapter, layout=SPEC.layout, scale=ASSEMBLED_SCALE,
        unit=assembly_contract("pd-paper-drive").drawing_unit,
    )
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
    for stem, item in SHARED_NUMBER_ITEMS.items():
        if actual[stem][1] != str(item):
            raise RuntimeError(
                f"paper-drive BOM item for {stem!r} is {actual[stem][1]!r}; the "
                f"steps print ITEM {item}"
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




def _place_assembled_sheet(adapter: Any) -> Any:
    """Front, right and isometric of the whole drive; returns the isometric,
    centred so its balloon ring keeps inside ISO_RING_LIMITS."""
    _activate_sheet(adapter, SHEET_NAMES[0])
    views: dict[str, Any] = {}
    for orientation, center in (
        ("*Front", FRONT_CENTER),
        ("*Right", RIGHT_CENTER),
        ("*Isometric", ISO_CENTER),
    ):
        view = place_view(
            adapter, str(SOURCE), orientation, *center, scale=ASSEMBLED_SCALE
        )
        views[orientation] = view
        # The isometric is the drawing's full-detail view.
        role = ViewRole.FULL_DETAIL if orientation == "*Isometric" else ViewRole.PLAIN
        apply_view_configuration(
            adapter, view, role=role, label=f"paper drive {orientation}"
        )
        if orientation != "*Isometric":
            # Lying flat on the deck, the spare T18 shows edge-on in the
            # front and right views as a bare unlabelled bar; the isometric
            # shows and balloons it (eye pass of PD run 11).
            view = set_drawing_view_instance_visibility(
                adapter,
                view,
                frozenset({SPARE_INSTANCE, *SPARE_SHIM_INSTANCES}),
                mode="hide",
                label=f"paper drive {orientation} spare",
            )
            views[orientation] = view
    _mark_parent_views(adapter, views["*Front"], views["*Right"])
    view = views["*Isometric"]
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
    _activate_sheet(adapter, SHEET_NAMES[-1])
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
        adapter, SHEET_NAMES[-1], BOM_SHEET_CAPTION, BOM_REFERENCE_CAPTION_XY,
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
    view = set_drawing_view_instance_visibility(adapter, view, TRANSGEAR_INSTANCES, mode="show", label=label)
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
    _activate_sheet(adapter, SHEET_NAMES[-1])
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
    locator = set_drawing_view_instance_visibility(adapter, locator, PIVOT_VIEW_INSTANCES, mode="show", label=label)
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
    section = set_drawing_view_instance_visibility(adapter, section, PIVOT_VIEW_INSTANCES, mode="show", label=section_label)
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
    _place_sheet_note(
        adapter,
        SHEET_NAMES[1],
        PIVOT_LOCATOR_CAPTION,
        PIVOT_LOCATOR_CAPTION_XY,
        label="hanger pivot locator caption",
    )


def _sketch_view_circle(
    adapter: Any,
    view: Any,
    centre: tuple[float, float],
    radius: float,
    *,
    label: str,
    direct: bool = False,
) -> None:
    """Sketch a sheet circle in ``view``'s own sketch, left selected
    (draw_mg_magnifier_assembly's detail crop).

    ``direct`` writes it straight to the sketch database, read back: screen-
    space inference snapped a detail boundary drawn over model edges to a
    smaller circle (DETAIL H) or none at all (DETAIL L) in run
    20261117T144118108Z-771678f99db440ccbcec03874c9b1aca."""
    view = _early_bound(view, "IView")
    if not _early_bound(adapter.currentModel, "IDrawingDoc").ActivateView(
        view_name(adapter, view)
    ):
        raise RuntimeError(f"{label}: failed to activate the view for its circle")
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
    manager.AddToDB = direct
    try:
        circle = manager.CreateCircle(*points[0], *points[1])
    finally:
        manager.AddToDB = previous
    if circle is None:
        raise RuntimeError(f"{label}: failed to sketch the circle")
    if direct:
        drawn_centre, drawn_radius = native_circle_geometry(circle, label=label)
        intended = math.dist(points[0][:2], points[1][:2])
        if (
            math.dist(drawn_centre[:2], points[0][:2]) > 1e-3 * intended
            or abs(drawn_radius - intended) > 1e-3 * intended
        ):
            raise RuntimeError(
                f"{label}: circle drew at {drawn_centre!r} r {drawn_radius}, "
                f"not {points[0]!r} r {intended}"
            )


def _crop_to_circle(
    adapter: Any, view: Any, centre: tuple[float, float], radius: float, *, label: str
) -> None:
    """Crop ``view`` to a sheet circle: Crop2 while the sketched circle is
    still selected."""
    view = _early_bound(view, "IView")
    _sketch_view_circle(adapter, view, centre, radius, label=label)
    status = int(view.Crop2(False, False, 1))
    adapter.currentModel.ClearSelection2(True)
    adapter.currentModel.EditRebuild3()
    view.UpdateViewDisplayGeometry()
    cropped = bool(view.IsCropped())
    if status != CROP_NO_ERROR or not cropped:
        raise RuntimeError(
            f"{label}: not cropped: Crop2 status {status}, IsCropped {cropped}"
        )


def _mark_parent_views(adapter: Any, front: Any, right: Any) -> None:
    """Sheet 1's front and right views locate the lettered views: DETAIL K's
    and DETAIL P's boundaries on the front view, DETAIL E's and DETAIL M's on
    the right view, each lettered in clear sheet with a pointer to its rim;
    VIEW B's viewing arrow points down onto the arm's pivot in the front
    view. M and P are the SETTING DETAILS sheet's reference views (#3110);
    their circles, drawn over model edges, go straight to the sketch database
    (_sketch_view_circle)."""
    views = {"*Front": front, "*Right": right}
    for parent, letter, model_mm, radius, offset, direct in (
        (
            front, KNOB_SETTING_VIEW_NAME[-1], KNOB_SETTING_MODEL_CENTRE,
            KNOB_SETTING_PARENT_RADIUS, KNOB_SETTING_LETTER_OFFSET, False,
        ),
        (
            right, CLUSTER_FLOAT_VIEW_NAME[-1], CLUSTER_FLOAT_MODEL_CENTRE,
            CLUSTER_FLOAT_PARENT_RADIUS, CLUSTER_FLOAT_LETTER_OFFSET, False,
        ),
        *(
            (
                views[reference.orientation], reference.letter, reference.model_centre,
                setting_parent_sheet1_radius(reference), reference.sheet1_letter_offset,
                True,
            )
            for reference in SETTING_PARENTS
        ),
    ):
        label = f"sheet 1 view {letter} boundary"
        centre = model_point_in_view(
            adapter, parent, tuple(value / 1000.0 for value in model_mm), label=label
        )
        _sketch_view_circle(adapter, parent, centre, radius, label=label, direct=direct)
        adapter.currentModel.ClearSelection2(True)
        adapter.currentModel.EditRebuild3()
        text, tip = detail_letter_pointer(centre, radius, offset)
        add_leader_note(
            adapter, letter, text_xy=text, attach_xy=tip, label=label, view=parent
        )
    label = f"sheet 1 view {PIVOT_LOCATOR_LETTER} arrow"
    pivot = model_point_in_view(
        adapter, front, (knob_setting.P_XY[0] / 1000.0, knob_setting.P_XY[1] / 1000.0, 0.0),
        label=label,
    )
    tip, text = viewing_arrow_xy(pivot)
    add_leader_note(
        adapter, PIVOT_LOCATOR_LETTER, text_xy=text, attach_xy=tip, label=label, view=front
    )
    rebuild_drawing(adapter, label="sheet 1 view letters")


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
        view = set_drawing_view_instance_visibility(adapter, view, exploded_group_instances(group), mode="show", label=label)
        # One scale, never stepped down (rule 15): read the placed outline.
        shift = exploded_ring_shift(_view_outline(view), group)
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
    view = isolate_drawing_view_components(adapter, view, visible_stems=explode.SHOWN_STEMS, label=label)
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
    """Sheet 6's DETAIL K: the arm and plate from the machine front at
    1:1, cropped on S-K's midpoint, carrying the assembly's set band S to N
    and its two K setting dimensions from S (pd_paper_drive_knob_setting_spec)
    that the arm-plate-located step cites."""
    label = "knob setting view"
    _activate_sheet(adapter, KNOB_SETTING_SHEET)
    view = _early_bound(
        place_view(
            adapter, str(SOURCE), "*Front", *KNOB_SETTING_CENTER, scale=KNOB_SETTING_SCALE
        ),
        "IView",
    )
    apply_view_configuration(adapter, view, label=label)
    view = set_drawing_view_instance_visibility(adapter, view, KNOB_SETTING_INSTANCES, mode="show", label=label)
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
        KNOB_SETTING_SHEET,
        KNOB_SETTING_CAPTION,
        KNOB_SETTING_CAPTION_XY,
        label=f"{label} caption",
    )


def _place_cluster_float_view(adapter: Any) -> None:
    """Sheet 6's DETAIL E: the pin's front end from the side at 5:1, cropped on
    the ring gap, carrying the assembly's shimmed ring-gap window
    (pd_paper_drive_cluster_float_spec) that the shimming step cites."""
    label = "cluster float view"
    _activate_sheet(adapter, CLUSTER_FLOAT_SHEET)
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
    view = set_drawing_view_instance_visibility(adapter, view, CLUSTER_FLOAT_INSTANCES, mode="show", label=label)
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
        CLUSTER_FLOAT_SHEET,
        CLUSTER_FLOAT_CAPTION,
        CLUSTER_FLOAT_CAPTION_XY,
        label=f"{label} caption",
    )


def _place_setting_detail(
    adapter: Any, detail: setting_details.SettingDetail
) -> None:
    """One lettered setting detail: the parts it measures from its view's
    side, cropped on the setting, its hidden sketch's dimensions imported,
    toleranced in the model (pd_paper_drive_setting_details_spec)."""
    label = f"setting {detail.view_name}"
    centre_xy = SETTING_DETAIL_CENTRES[detail.letter]
    _activate_sheet(adapter, SETTING_DETAIL_SHEET)
    view = _early_bound(
        place_view(adapter, str(SOURCE), detail.orientation, *centre_xy, scale=detail.scale),
        "IView",
    )
    apply_view_configuration(adapter, view, label=label)
    view = set_drawing_view_instance_visibility(
        adapter, view, detail.instances, mode="show", label=label
    )
    model = tuple(
        tuple(value / 1000.0 for value in point)
        for point in (detail.centre, *(line.text for line in detail.lines))
    )
    names = ("centre", *(f"{line.dimension} text" for line in detail.lines))
    centre = model_points_in_view(adapter, view, model[:1], label=label, names=names[:1])[0]
    _shift_view(
        adapter,
        view,
        (centre_xy[0] - centre[0], centre_xy[1] - centre[1]),
        label=f"{label} centre",
    )
    centre, *texts = model_points_in_view(adapter, view, model, label=label, names=names)
    if math.dist(centre, centre_xy) > 1e-4:
        raise RuntimeError(f"{label}: its setting sits at {centre!r}")
    _crop_to_circle(adapter, view, centre_xy, detail.radius, label=label)
    set_hidden_lines_removed(adapter, view)
    _show_base_view_sketches(adapter, view, (detail.feature,), label=label)
    keep = {line.dimension: text for line, text in zip(detail.lines, texts, strict=True)}
    annotations = curate_view_dimensions(
        adapter,
        view,
        keep=keep,
        view_label=label,
        dimensions_by_feature=setting_details.DRAWING_DIMENSIONS,
    )
    assert_imported_precision(
        adapter, annotations, setting_details.DRAWING_PRECISION[detail.feature]
    )
    imported = sorted(
        dimension_name(adapter, _early_bound(annotation, "IAnnotation"))
        for annotation in annotations
    )
    if imported != sorted(keep):
        raise RuntimeError(f"{label} imported {imported}, not {sorted(keep)}")
    lengths = {line.dimension: line.length_mm for line in detail.lines}
    sheet_per_mm = detail.scale[0] / detail.scale[1] / 1000.0
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        name = dimension_name(adapter, annotation)
        if lengths[name] * sheet_per_mm >= SETTING_ARROWS_OUTSIDE_BELOW:
            continue
        # A short dimension's arrows inside strike its own text (DETAIL E).
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.ArrowSide = SETTING_ARROWS_OUTSIDE
        if int(display.ArrowSide) != SETTING_ARROWS_OUTSIDE:
            raise RuntimeError(f"{label}: {name} kept its arrows inside")
    rebuild_drawing(adapter, label=f"{label} arrows")
    _place_sheet_note(
        adapter,
        SETTING_DETAIL_SHEET,
        SETTING_DETAIL_CAPTIONS[detail.letter],
        (
            centre_xy[0] - detail.radius,
            centre_xy[1] - detail.radius - SETTING_CAPTION_DROP,
        ),
        label=f"{label} caption",
    )


def _place_setting_parent(adapter: Any, parent: SettingParent) -> None:
    """A cropped reference view carrying its details' lettered boundaries,
    each letter outside the crop, its leader to the boundary's rim."""
    label = f"setting reference {parent.name.lower()}"
    _activate_sheet(adapter, SETTING_DETAIL_SHEET)
    view = _early_bound(
        place_view(
            adapter, str(SOURCE), parent.orientation, *parent.centre, scale=parent.scale
        ),
        "IView",
    )
    apply_view_configuration(adapter, view, label=label)
    centre = model_point_in_view(
        adapter, view, tuple(value / 1000.0 for value in parent.model_centre), label=label
    )
    _shift_view(
        adapter,
        view,
        (parent.centre[0] - centre[0], parent.centre[1] - centre[1]),
        label=f"{label} centre",
    )
    _crop_to_circle(adapter, view, parent.centre, parent.radius, label=label)
    set_hidden_lines_removed(adapter, view)
    for letter in parent.letters:
        detail = SETTING_DETAILS_BY_LETTER[letter]
        boundary = f"{label} {detail.view_name} boundary"
        middle = model_point_in_view(
            adapter, view, tuple(value / 1000.0 for value in detail.centre), label=boundary
        )
        radius = _boundary_radius(detail, parent.scale)
        if math.dist(middle, parent.centre) + radius > parent.radius:
            raise RuntimeError(f"{boundary} at {middle!r} leaves the crop")
        _sketch_view_circle(adapter, view, middle, radius, label=boundary, direct=True)
        adapter.currentModel.ClearSelection2(True)
        adapter.currentModel.EditRebuild3()
        reach = math.dist(middle, parent.centre)
        direction = (
            ((middle[0] - parent.centre[0]) / reach, (middle[1] - parent.centre[1]) / reach)
            if reach > 1e-6
            else (0.0, -1.0)
        )
        letter_xy = (
            parent.centre[0] + direction[0] * (parent.radius + SETTING_LETTER_GAP),
            parent.centre[1] + direction[1] * (parent.radius + SETTING_LETTER_GAP),
        )
        text, tip = detail_letter_pointer(
            middle, radius, (letter_xy[0] - middle[0], letter_xy[1] - middle[1])
        )
        add_leader_note(adapter, letter, text_xy=text, attach_xy=tip, label=boundary, view=view)
    rebuild_drawing(adapter, label=f"{label} letters")
    _place_sheet_note(
        adapter,
        SETTING_DETAIL_SHEET,
        SETTING_PARENT_CAPTIONS[parent.name],
        (
            parent.centre[0] - parent.radius,
            parent.centre[1] - parent.radius - 3 * SETTING_CAPTION_DROP,
        ),
        label=f"{label} caption",
    )


def _place_setting_sheets(adapter: Any, step_notes: StepNotes) -> None:
    """The SETTING DETAILS sheet's references and details, then the SETTING
    TABLE sheet's one native general table (rule 22)."""
    for parent in SETTING_PARENTS:
        _place_setting_parent(adapter, parent)
    for detail in setting_details.DETAILS:
        _place_setting_detail(adapter, detail)
    # A sheet carries its title block's property links through a view: the
    # table's sheet takes the step sheets' reference isometric (run
    # 20261117T133502796Z-117e953f2f9746a682948215106b40a1).
    _place_fitup_reference(adapter, SETTING_TABLE_SHEET)
    _activate_sheet(adapter, SETTING_TABLE_SHEET)
    box = insert_general_table(
        adapter,
        title=SETTING_TABLE_TITLE,
        header=SETTING_TABLE_HEADER,
        rows=step_notes.setting_rows,
        top_left=SETTING_TABLE_TOP_LEFT,
        label="setting table",
    )
    # Above the reference caption (and so the title block), inside the border.
    if box[2] > SETTING_TABLE_RIGHT_LIMIT or box[1] < FITUP_NOTE_LIMITS[0][1]:
        raise RuntimeError(f"setting table at {box!r} leaves its field")


def _place_fitup_reference(adapter: Any, sheet_name: str) -> None:
    """A step sheet's reference isometric at the bottom left, captioned."""
    _activate_sheet(adapter, sheet_name)
    view = place_view(
        adapter, str(SOURCE), "*Isometric", *FITUP_REFERENCE_CENTER, scale=FITUP_SCALE
    )
    apply_view_configuration(adapter, view, label=f"{sheet_name} reference isometric")
    _place_sheet_note(
        adapter,
        sheet_name,
        FITUP_REFERENCE_CAPTION,
        (FITUP_REFERENCE_CENTER[0] - 0.040, FITUP_NOTE_LIMITS[0][1] - 0.002),
        label=f"{sheet_name} reference caption",
    )


def _place_fitup_sheets(adapter: Any, step_notes: StepNotes) -> None:
    """Sheets 5 on: a reference isometric each, then their step columns."""
    for sheet_name in dict.fromkeys(column.sheet for column in step_notes.columns[1:]):
        _place_fitup_reference(adapter, sheet_name)
    for index, column in enumerate(step_notes.columns[1:]):
        _place_sheet_note(
            adapter, column.sheet, column.text, column.xy,
            label=f"{column.sheet} step column {index + 1}",
        )


@_telemetry.traced("drawing.paper_drive_assembly")
def build(adapter: Any) -> dict[str, str]:
    notes = require_step_notes()
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source assembly is missing: {SOURCE}")

    check("open assembly drawing source", adapter.open_model(str(SOURCE)))
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
    _place_setting_sheets(adapter, notes)
    assert_full_detail_view(adapter, label="paper-drive assembly")

    return finalize_drawing(
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
