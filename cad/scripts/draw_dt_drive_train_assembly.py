r"""Create the native fifteen-sheet drive-train assembly drawing package (MHA-DT-00).

The released ``dt-drive-train.SLDASM`` stays authoritative and byte-for-byte
unchanged. This recipe consumes the builder-owned ``DRIVE_TRAIN_EXPLODED``
presentation (``_drive_train_explode``) and reads every count, identity and
position it prints from the opened model; nothing pending on a sibling branch
(crank hub, lever pin, pinion tooth count, bracket placement) is typed here.

Sheet numbers are fixed; cross-references come from the ``*_SHEET`` constants.
One physical BOM family combines the swing-stop and spring-foot screws; native
occurrence references retain their distinct installation and explode roles.
Fit-up steps give the measured acceptance and the cut that answers it.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime
from fractions import Fraction
import hashlib
from itertools import combinations
import math
from pathlib import Path
import re
import sys
import textwrap
from typing import Any, Callable, Iterator, Literal, NamedTuple, Sequence

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    dimension_name,
    place_view,
    view_name,
)

from _check import check
from _com import _early_bound
from _component_references import component_reference_names
import _config
from _drawing_balloons import (
    BalloonLanding,
    _anchor_model_points,
    _spread_balloons,
    _stems_matching,
    _view_component_leaves,
    add_component_bom_balloons,
    assert_balloon_landings,
    balloon_item_resolved,
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
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision
from _drawing_hidden_sketches import _show_base_view_sketches
from _drawing_layout_check import LeaderSegment, find_leader_leader_crossings
from _drawing_layout_collect import (
    _leader_segments_of,
    check_drawing_layout,
    collect_layout_elements,
)
from _drawing_leader_notes import add_leader_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME, DrawingLayout
from _drawing_sheets import create_blank_drawing_sheets
from _drawing_tables import insert_bom_table
from _drawing_view_configuration import (
    SIMPLIFIED_VIEW_CONFIGURATION,
    ViewRole,
    apply_view_configuration,
    assert_full_detail_view,
    set_view_exploded_state,
    view_configuration,
)
from _drawing_view_display import set_hidden_lines_removed
from _dt_drive_train_balloon_anchors import DRIVE_TRAIN_BALLOON_ANCHORS
from _machinist_review_mode import MachinistReviewMode
import _seat_forensics
from _session import run_build
from _simplified_names import simplified_name
import _telemetry
from ch_channel_assembly_steps import (
    NORTH_BRACKET_SET_KEY,
    RODS_PINNED_REF,
    step_ref as channel_step_ref,
)
import ch_vn_rocker_thrust_washer_spec as rocker_washer
import cone_line
import cone_set_stack as set_stack
from cone_stack_end_play import COLLAR_FEELER, SHAFT_END_PLAY
import cylinder_bank_layout as bank
import dt_cylinder_bank_setting_spec as bank_settings
from dt_cone_gear_stack import COUNT as CONE_GEAR_COUNT, STACK_L20_ACCEPT
from dt_cone_swing_platform_spec import POST_MOUNT_ENGAGEMENT_ASSEMBLY_FACT
from dt_cone_tip_block_spec import ADJUSTER_ENGAGEMENT_ASSEMBLY_FACT, ADJUSTER_THREAD
import dt_crank_drive_gear_spec as gear64
import dt_crank_handle_pivot_screw_spec as handle_screw
from dt_crank_hub_notes import FRONT_FACE_DATUM as HUB_FRONT_FACE_DATUM
import dt_crank_pinion_spec as pinion
from dt_crank_pinion_spec import SEAT_FEELER_MM as PINION_SEAT_FEELER
from dt_crankshaft_spec import SHAFT_END_PROUD_RANGE as CRANK_END_PROUD_RANGE
from dt_cylinder_end_disc_spec import WASHER_THICK as BANK_WASHER_THICK
import dt_cylinder_gear_spec as drum
from dt_drive_train_assembly_sheet import (
    HANDLE_FERRULE_CURE,
    LEVER_PIN_HOLE_FIT,
    T120_FITUP_ASSEMBLY_CHECK,
)
from dt_drive_train_assembly_spec import (
    CLUSTERS,
    COMPONENT_IDENTITIES,
    EXPLODED_VIEW_NAME,
    FOOT_SCREW_SELECTOR,
    PENDING_STEMS,
    SOURCE_CONFIGURATION,
    SWING_STOP_SCREW_SELECTOR,
    Cluster,
    Instance,
    component_stem,
    instance_selector,
    unclassified_stems,
)
import dt_drive_train_steps as steps
import dt_mesh_checks as mesh_checks
import dt_pinion_cam_geometry as cam_geometry
from dt_pinion_spring_section import SCREW_EAST_OF_PIVOT as SPRING_SCREW_EAST_OF_PIVOT
import fr_harmonic_base_spec as base
import pinion_rig_fitup as FITUP
import pinion_rig_tip_gap as TIP_GAP
import rocker_bank_layout as rockers
import dt_vn_cone_lock_knob_spec as lock_knob
import dt_vn_cone_pivot_screw_spec as pivot_screw
import dt_vn_cone_tip_collar_spec as tip_collar
from dt_vn_keeper_chain_spec import BEAD_COUNT as KEEPER_CHAIN_BEADS
import dt_vn_post_mount_screw_spec as post_screw
import dt_swing_stop_screw_spec as stop_screw

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["dt_drive_train_assembly"]
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
DRAWING_NUMBER = "MHA-DT-00"
# swUserPreferenceToggle_e.swViewDisplayHideAllTypes = 198: read by reflection
# from the installed SOLIDWORKS 3DEXPERIENCE R2026x
# SolidWorks.Interop.swconst.dll (2026-09-23), matching the API help's "Hide or
# Show All Types" example. Applied with IModelDocExtension::
# SetUserPreferenceToggle(.., swDetailingNoOptionSpecified), as the API help's
# View > Hide/Show table lists it.
VIEW_DISPLAY_HIDE_ALL_TYPES = 198

SHEET_NAMES = (
    "ASSEMBLED VIEWS",
    "BILL OF MATERIALS",
    "CYLINDER BANK EXPLODED",
    "CONE SET EXPLODED",
    "CRANK EXPLODED",
    "ALIGNMENT PINION RIG EXPLODED",
    "ASSEMBLY SEQUENCE",
    "ASSEMBLY SEQUENCE CONT. - CRANK",
    "ASSEMBLY SEQUENCE CONT. - CYLINDER BANK",
    "ASSEMBLY SEQUENCE CONT. + FIT",
    "ASSEMBLY SEQUENCE CONT. + CRANK END FIT",
    "FULL-DETAIL SIDE VIEW",
    "CHECKS + SETUP",
    "CHECKS (CONT.)",
    "CYLINDER BANK SETTINGS",
)
SHEET_LAYOUTS = {name: DrawingLayout.LANDSCAPE for name in SHEET_NAMES}
if SPEC.layout is not DrawingLayout.LANDSCAPE:
    raise AssertionError("the drive-train package primary sheet must remain landscape")
# Which sheet shows which cluster; the BOM sheet and captions cite these.
CLUSTER_SHEETS: dict[Cluster, int] = {
    "cylinder-bank": 3,
    "cone-set": 4,
    "crank": 5,
    "pinion-rig": 6,
}
CLUSTER_TITLES: dict[Cluster, str] = {
    "cylinder-bank": "CYLINDER BANK",
    "cone-set": "CONE SET AND SWING PLATFORM",
    "crank": "CRANK",
    "pinion-rig": "ALIGNMENT PINION RIG",
}
# #743 grew steps 8-9 past the sequence sheet's right field, so the bank
# sequence has its own sheet (Main, B1 re-ruling 2026-09-26). A blank line
# between numbered steps (user, 2026-10-23: "add line breaks bw steps; add
# extra sheets as needed") pushed steps 6-7 and check 7 onto continuation
# sheets. The numbered steps read in sheet order: 1-5 on sheet 7 (4-5 in its
# right field), 6-7 on 8, 8-10 on 9, 11-18 on 10 and 19-23 on 11; the checks
# follow the full-detail view (gate review of 042726e87: the steps jumped
# 6 -> 11 -> 7 -> 8 -> 11), check 7 on the sheet after them.
SEQUENCE_SHEET = 7
CRANK_SHEET = 8
BANK_SHEET = 9
FIT_SHEET = 10
CONTINUATION_SHEET = 11
# Every view at 1:2 or smaller prints the teeth/thread-free "Default
# Simplified" configuration (the policy in _drawing_view_configuration); the
# user asked for the ENTIRE drive train at 1:2 or larger with every modeled
# tooth and thread, so sheet 12 carries it.
FULL_DETAIL_SHEET = 12
CHECKS_SHEET = 13
CHECKS_CONTINUATION_SHEET = 14
BANK_SETTINGS_SHEET = 15
BANK_SETTING_SCALE = (1.0, 1.0)
BANK_SPRING_DETAIL_SCALE = (4.0, 1.0)
BANK_SETTING_CENTER = (0.205, 0.195)
BANK_SPRING_DETAIL_CENTER = (0.105, 0.075)
BANK_SPRING_CROP_RADIUS_MM = 8.0
BANK_SETTING_KEEP = {bank_settings.STACK_DIMENSION: (0.205, 0.250)}
BANK_SPRING_KEEP = {bank_settings.SPRING_DIMENSION: (0.165, 0.125)}

ASSEMBLED_SCALE = (1.0, 3.0)
ASSEMBLED_ISO_SCALE = (1.0, 3.0)
REFERENCE_ISO_SCALE = (1.0, 8.0)
# At 1:3 the bank and rig explodes filled about a fifth of their sheets (Fable
# review of baseline-5). The bank still filled a small fraction of its sheet at
# 1:2 (r9 Fable review), and at 2:3 its ~169 x 141 mm outline plus the balloon
# ring fit the 395 x 176 field. The inch cylinder gears grew it to 169.9 x
# 145.0 mm at 2:3 (0d454fa91), a 179.0 mm ring: 2:3 no longer fits, and
# stepping down to 1:2 would switch the view off 'Default' after its explode,
# which the fit refuses. So the bank is placed at 1:2: Default Simplified from
# the start, a ~127 x 109 mm outline and a 143 mm ring.
# The rig cannot grow: its ~116 mm-tall outline plus ring already nears 176.
# The cone set and the crank, one 1:4 view until the machinist review of
# 9ebf51696, each start at 1:2 on their own sheet.
# Each is the cluster's PREFERRED scale: the build places the view there and
# steps down CLUSTER_SCALE_LADDER until its balloon ring fits (cluster_ring_scale).
CLUSTER_SCALES: dict[Cluster, tuple[float, float]] = {
    "cylinder-bank": (1.0, 2.0),
    "cone-set": (1.0, 2.0),
    "crank": (1.0, 2.0),
    "pinion-rig": (1.0, 2.0),
}
# The standard scales a cluster view may step down through, largest first
# (Main, 2026-09-27: cascade-3's cone-crank ring ran 191.6 mm tall at 1:3 and
# put balloons '42'/'43' on sheet 4's heading; fit the sheet, never warn).
CLUSTER_SCALE_LADDER: tuple[tuple[float, float], ...] = (
    (2.0, 3.0),
    (1.0, 2.0),
    (1.0, 3.0),
    (1.0, 4.0),
    (1.0, 5.0),
)
# The full-detail view's scales, largest first: it lands at the first one whose
# outline fits FULL_DETAIL_REGION (full_detail_scale); the layout audit is the
# proof. Below 1:2 the view would fall under the simplified-view threshold.
FULL_DETAIL_SCALE_LADDER: tuple[tuple[float, float], ...] = (
    (1.0, 1.0),
    (2.0, 3.0),
    (1.0, 2.0),
)
# Side-on, the long axis of the train runs across the landscape field and
# every gear mesh (cylinder bank, cone set, crank, pinion rig) is in profile.
FULL_DETAIL_ORIENTATION = "*Right"


def package_sheet_scales(
    cluster_scales: dict[Cluster, tuple[float, float]],
    full_detail_scale: tuple[float, float] = FULL_DETAIL_SCALE_LADDER[0],
) -> dict[str, tuple[float, float]]:
    """Every sheet's scale: each cluster sheet at its cluster view's scale and
    the full-detail sheet at the scale its view fitted.

    The other sheets carry only the 1:8 reference isometric, except sheet 1's
    assembled views.
    """
    return {
        **{name: REFERENCE_ISO_SCALE for name in SHEET_NAMES},
        SHEET_NAMES[0]: ASSEMBLED_SCALE,
        **{SHEET_NAMES[number - 1]: cluster_scales[c] for c, number in CLUSTER_SHEETS.items()},
        SHEET_NAMES[FULL_DETAIL_SHEET - 1]: full_detail_scale,
        SHEET_NAMES[BANK_SETTINGS_SHEET - 1]: BANK_SETTING_SCALE,
    }


SHEET_SCALES = package_sheet_scales(CLUSTER_SCALES)

# --- sheet 1: projected front/top/right group + isometric ---------------------
# The projected group's lower-left lands here; the views are aligned on the
# model origin (ASME third angle: top above front, right to the right of it).
# At 1:3 main's group read 209.2 x 190.7 mm with a 14 mm gap (drawing.projected_group);
# the inch train grew it to 213.0 x 194.9 (0d454fa91), 0.9 mm past the 194 mm
# region. A 12 mm gap still holds each caption (4 mm under its view, one
# ~3.5 mm line) ~4.5 mm clear of the view below and fits with 1.1 mm to spare.
# The 175 mm the first region allowed failed on the farm (leaf
# 20260923T045245Z-1-b34a8422). The origin sits just above the title block
# (top y=0.0655) and the region top 4.5 mm under the zone border.
PROJECTED_GROUP_ORIGIN = (0.024, 0.068)
PROJECTED_GAP = 0.012
PROJECTED_REGION = (0.018, 0.068, 0.300, 0.262)
# The right half between the four-line heading (bottom ~0.245) and the title block
# (top 0.0655): a 1:3 isometric outline is ~130 mm, 1.5x baseline-5's 1:4.
ASSEMBLED_ISO_CENTER = (0.320, 0.155)
VIEW_CAPTION_GAP = 0.004
# The general notes sit between the heading and the isometric (see
# general_notes_field). Main's last green build measured the isometric's outline
# top at 0.2117; only the offline budget reads this, the placement reads the
# placed view. The notes clear the view as a caption does.
ASSEMBLED_ISO_TOP = 0.2117
GENERAL_NOTES_ISO_GAP = VIEW_CAPTION_GAP

# --- sheet 2: two BOM pieces + reference isometric below the first ------------
# Give full canonical Numbers their own width; keep the native-proven
# description width and the document's legible table font unchanged.
BOM_COLUMN_WIDTHS = {
    "item": 0.012,
    "part": 0.048,
    "description": 0.118,
    "quantity": 0.012,
}
BOM_COLUMN_WIDTH = sum(BOM_COLUMN_WIDTHS.values())
# Measured, not derived: in the 118 mm column, four 41-character descriptions
# kept one line and the 47-character MHA-VN-006 row wrapped to 10.195 mm
# (farm leaf 20260923T044055Z-1-20b23f24, swmaker000005).
BOM_DESCRIPTION_MAX_CHARS = 41
BOM_ANCHOR = (0.018, 0.252)
BOM_SECOND_COLUMN_X = BOM_ANCHOR[0] + BOM_COLUMN_WIDTH + 0.008
BOM_ROW_HEIGHT = 0.006
BOM_HEIGHT_TOLERANCE = 1e-6
BOM_SHEET_CLEARANCE = 0.003
# The two 190 mm pieces end at x=406 mm. Their old right-hand reference strip
# is now table space; the reference view and station pointer sit below piece 1.
# The grouped cone-gear description cannot reliably carry the station pointer
# (farm leaf 20260923T040258Z-1-0726d474). Keep it as a separate, full note.
BOM_REFERENCE_NOTES = (
    "REFERENCE 1:8\n"
    f"BALLOONS ON SHEETS {min(CLUSTER_SHEETS.values())}-{max(CLUSTER_SHEETS.values())}\n"
    "MHA-DT-03 CONE GEAR\n"
    f"STATIONS: SHEET {FIT_SHEET}"
)

# --- sheets 3-6: exploded cluster views --------------------------------------
CLUSTER_VIEW_CENTER = (0.200, 0.165)
# Top keeps baseline-4's ~5 mm clearance under the two-line sheet heading.
CLUSTER_RING_REGION = (0.020, 0.072, 0.415, 0.248)
CLUSTER_BALLOON_MARGIN = 0.012
BALLOON_DIAMETER = 0.010
# How far past the view outline balloon ink reaches: _spread_balloons puts each
# circle CENTRE on the ellipse CLUSTER_BALLOON_MARGIN outside, so the ink stops
# a radius beyond it. cascade-3's audit read balloon '42' at y 246.1-255.5 mm,
# its centre on the ellipse's top vertex (margin + diameter overstated it 5 mm).
CLUSTER_RING_REACH = CLUSTER_BALLOON_MARGIN + BALLOON_DIAMETER / 2.0
# A ring balloon keeps the paper clearance the BOM keeps off the title block.
CLUSTER_TITLE_BLOCK_CLEARANCE = BOM_SHEET_CLEARANCE
# Extra arc clearance between neighbouring ring balloons. The shared ring keeps
# circles 1.5 apart; on the rig sheet the left-block attachments bunch so tightly that
# items 17/18/19/20/26 read as one converging knot (Main eye-pass of r6b).
# Placement stays in attachment-angle order, so widening cannot add a crossing.
CLUSTER_BALLOON_CLEARANCE = {
    "cylinder-bank": 0.0015,
    "cone-set": 0.0015,
    "crank": 0.0015,
    "pinion-rig": 0.008,
}

# --- note fields (x0, top, x1, bottom), metres --------------------------------
# Tops sit under the one-line sheet heading at HEADING_XY.
NOTE_FIELD_LEFT = (0.018, 0.252, 0.212, 0.035)
NOTE_FIELD_RIGHT = (0.222, 0.252, 0.415, 0.072)
NOTE_FIELD_INSET = 0.0005
NOTE_ANCHOR_PASSES = 3
NOTE_ANCHOR_SETTLE = 0.00005
NOTE_BLOCK_GAP = 0.006
# A note's anchor is its top edge: y=0.268 crossed the top zone border by
# 1.5 mm on every sheet; summing's headings at 0.263 pass.
HEADING_XY = (0.018, 0.263)
# Sheet 1's four-line heading sits over the isometric, clear of the top view.
ASSEMBLED_HEADING_XY = (0.222, 0.263)
BOM_REFERENCE_VIEW_BOTTOM = 0.025
REFERENCE_ISO_CENTER = (0.380, 0.110)
# Notes print at 4.525 mm a line (summing-assembly.pdf; this package's telemetry:
# 47 lines measure 212.33 mm).
NOTE_LINE_PITCH = 0.004525
# ~47 lines fit the full left column, ~24 the right one above the 1:8 reference
# view that every sheet needs for its title-block property links
# (finalize_drawing refuses a sheet without a view: r8, leaf
# 20260923T214354Z-1-4126331f). A blank line between numbered steps takes one
# pitch. Sheet 7 carries steps 1-3 on the left and 4-5 on the right, sheet 8
# the crank's 6-7. Step 10 uses sheet 9's right field. Sheet 10 carries the
# first rig steps and station table; sheet 11 the last rig steps and the crank
# end fit. Sheet 14 carries check 7.
# package_note_fields lists every field and its blocks.
ISO_RIGHT_FIELD = (NOTE_FIELD_RIGHT[0], NOTE_FIELD_RIGHT[1], NOTE_FIELD_RIGHT[2], 0.140)
REFERENCE_ISO_CAPTION_XY = (0.330, 0.082)
# A 1:8 reference view's outline is ~49 mm tall (its ink ~31 mm square inside
# it, st19 dt-02); this half-extent budgets it both ways.
REFERENCE_ISO_HALF_OUTLINE = 0.0247
# With 27 data rows the first piece ends near y=80 mm (the historical header
# measured 10.2 mm). The 1:8 reference view is wholly below that piece; its
# complete metadata, including scale, sits beside it. The native table budget
# reserves this field.
BOM_REFERENCE_FIELD = (
    BOM_ANCHOR[0],
    0.077,
    BOM_ANCHOR[0] + BOM_COLUMN_WIDTH,
    0.0127 + BOM_SHEET_CLEARANCE,
)
BOM_REFERENCE_ISO_CENTER = (0.060, 0.0515)
BOM_REFERENCE_VIEW_FIELD = (
    BOM_REFERENCE_FIELD[0],
    BOM_REFERENCE_FIELD[1],
    0.094,
    BOM_REFERENCE_VIEW_BOTTOM,
)
BOM_REFERENCE_NOTE_FIELD = (0.100, 0.072, BOM_REFERENCE_FIELD[2], 0.040)

# --- sheet 12: the whole drive train, full detail ----------------------------
# The view (outline only) must fit between the one-line heading and the title
# block row: NOTE_FIELD's top under the heading, and the title block's top
# (0.0655) plus the BOM's paper clearance plus the caption under the view
# (VIEW_CAPTION_GAP + one 3.5 mm line). The field spans the full sheet width, so
# the view clears the title block by height, not by sliding left.
FULL_DETAIL_CAPTION_ALLOWANCE = 0.008
FULL_DETAIL_REGION = (
    NOTE_FIELD_LEFT[0],
    DRAWING_TEMPLATES[SPEC.layout].title_block_top_m
    + BOM_SHEET_CLEARANCE
    + FULL_DETAIL_CAPTION_ALLOWANCE,
    NOTE_FIELD_RIGHT[2],
    NOTE_FIELD_LEFT[1],
)
FULL_DETAIL_CAPTION = "GEAR TEETH AND SCREW THREADS AS MODELED"

# --- BOM identities: released part numbers and descriptions ------------------
# The model owns the part number (each component's "Number" property, read and
# cross-checked at build time); the description column is drawing wording.
# test_drive_train_assembly_drawing.py pins every number against the parts
# registry and every builder-inserted family against this table.
BOM_PART_NUMBERS = {
    "dt-cylinder-gear-shaft": "MHA-DT-13",
    "dt-arbor-pedestal": "MHA-DT-02",
    "dt-cylinder-end-disc": "MHA-DT-26",
    "dt-vn-cylinder-bank-spring": "MHA-DT-VN-68",
    "dt-cylinder-gear": "MHA-DT-12",
    "dt-vn-pedestal-hold-down-screw": "MHA-DT-VN-62",
    "sh-vn-arbor-set-screw": "MHA-SH-VN-54",
    "sh-vn-fillister-screw-90280a108": "MHA-SH-VN-52",
    "dt-cone-gear-shaft": "MHA-DT-04",
    "dt-cone-gear": "MHA-DT-03",
    "dt-crank-drive-gear": "MHA-DT-07",
    "dt-cone-swing-platform": "MHA-DT-20",
    "dt-cone-pivot-post": "MHA-DT-05",
    "dt-cone-tip-block": "MHA-DT-21",
    "dt-vn-cone-tip-collar": "MHA-DT-VN-54",
    "dt-vn-cone-tip-adjuster": "MHA-DT-VN-55",
    "dt-vn-cone-tip-pinch-screw": "MHA-DT-VN-56",
    "dt-vn-cone-tip-block-screw": "MHA-DT-VN-60",
    "dt-vn-post-mount-screw": str(_config.parts("dt-vn-post-mount-screw")["number"]),
    "dt-vn-cone-lock-knob": "MHA-DT-VN-51",
    "dt-vn-cone-pivot-screw": "MHA-DT-VN-52",
    "dt-crankshaft": "MHA-DT-11",
    "dt-crank-pinion": "MHA-DT-10",
    "dt-crank-pinion-pin": "MHA-DT-29",
    "dt-crank-arm": "MHA-DT-06",
    "dt-crank-pin": "MHA-DT-09",
    "dt-crank-pin-ring": "MHA-DT-27",
    "dt-crank-pin-eye": "MHA-DT-28",
    "dt-vn-keeper-chain": "MHA-DT-VN-65",
    "dt-vn-keeper-chain-link": "MHA-DT-VN-66",
    "sh-vn-brass-fillister-screw": "MHA-SH-VN-51",
    "dt-crank-handle": "MHA-DT-08",
    "dt-crank-handle-ferrule": "MHA-DT-34",
    "dt-crank-handle-butt-cup": "MHA-DT-35",
    "dt-crank-handle-pivot-screw": "MHA-DT-32",
    "dt-crank-hub": "MHA-DT-31",
    "dt-vn-crank-hub-pin": "MHA-DT-VN-59",
    "dt-vn-crank-seat-drive-pin": "MHA-DT-VN-67",
    "dt-alignment-pinion": "MHA-DT-01",
    "dt-pinion-bracket": "MHA-DT-14",
    "dt-pinion-pivot-block": "MHA-DT-18",
    "dt-pinion-pivot-shaft": "MHA-DT-19",
    "dt-pinion-lift-rod": "MHA-DT-17",
    "dt-pinion-spring": "MHA-DT-24",
    "dt-pinion-cam-pin": "MHA-DT-25",
    "dt-pinion-cam": "MHA-DT-23",
    "dt-pinion-lever": "MHA-DT-16",
    "dt-pinion-lever-pin": "MHA-DT-30",
    "dt-pinion-handle": "MHA-DT-15",
    "dt-pinion-arbor": "MHA-DT-22",
    "dt-pinion-arbor-collar": "MHA-DT-33",
    "dt-vn-pinion-strap-pin": "MHA-DT-VN-63",
    "dt-vn-slotted-screw": "MHA-DT-VN-57",
}
BOM_DESCRIPTIONS = {
    "dt-cylinder-gear-shaft": "CYLINDER GEAR ARBOR",
    "dt-arbor-pedestal": "ARBOR PEDESTAL",
    "dt-cylinder-end-disc": "CYLINDER BANK SOUTH END DISC",
    "dt-vn-cylinder-bank-spring": "WAVE DISC SPRING, MCMASTER 9714K392",
    "dt-cylinder-gear": f"CYLINDER GEAR WITH CAM, {drum.TEETH}T",
    "dt-vn-pedestal-hold-down-screw": "#8-32 FILLISTER SCREW, MCMASTER 90280A197",
    "sh-vn-arbor-set-screw": "#4-40 X 1/4 SET SCREW, MCMASTER 91375A106",
    "sh-vn-fillister-screw-90280a108": "#4-40 FILLISTER SCREW, MCMASTER 90280A108",
    "dt-cone-gear-shaft": "CONE GEAR SHAFT",
    "dt-cone-gear": "CONE GEAR, T006-T120 BY 6; 1 EACH",
    "dt-crank-drive-gear": f"CRANK DRIVE GEAR, {gear64.TEETH}T",
    "dt-cone-swing-platform": "CONE SWING PLATFORM",
    "dt-cone-pivot-post": "CONE PIVOT POST AND CRANK COLUMN",
    "dt-cone-tip-block": "CONE TIP BLOCK",
    "dt-vn-cone-tip-collar": tip_collar.BOM_DESCRIPTION,
    "dt-vn-cone-tip-adjuster": f"{ADJUSTER_THREAD} CUP SET SCREW, MCMASTER 94025A164",
    "dt-vn-cone-tip-pinch-screw": "#4-40 FILLISTER SCREW, MCMASTER 91794A112",
    "dt-vn-cone-tip-block-screw": "#4-40 X 3/8 SHCS, MCMASTER 91251A108",
    "dt-vn-post-mount-screw": f"{post_screw.THREAD} FILLISTER SCREW, MSC {post_screw.SKU}",
    "dt-vn-cone-lock-knob": f"{lock_knob.THREAD} THUMB SCREW, MCMASTER 93585A190",
    "dt-vn-cone-pivot-screw": f"{pivot_screw.THREAD} SHOULDER SCREW, MCMASTER 91829A560",
    "dt-crankshaft": "CRANKSHAFT",
    "dt-crank-pinion": f"CRANK PINION, {pinion.TEETH}T",
    "dt-crank-pinion-pin": "CRANK PINION RETENTION PIN",
    "dt-crank-arm": "CRANK ARM",
    "dt-crank-pin": "CRANK TAPER PIN, 1:48",
    "dt-crank-pin-ring": "TAPER PIN KEEPER RING",
    "dt-crank-pin-eye": "KEEPER CHAIN ANCHOR EYE",
    "dt-vn-keeper-chain": "#3 BRASS BEAD CHAIN, MCMASTER 3606T118",
    "dt-vn-keeper-chain-link": "LOOP LINK, MCMASTER 3606T811",
    "sh-vn-brass-fillister-screw": "#4-40 BRASS FILLISTER, MCMASTER 90114A511",
    "dt-crank-handle": "CRANK HANDLE",
    "dt-crank-handle-ferrule": "CRANK HANDLE FERRULE",
    "dt-crank-handle-butt-cup": "CRANK HANDLE BUTT CUP",
    "dt-crank-handle-pivot-screw": "CRANK HANDLE PIVOT SCREW",
    "dt-crank-hub": "CRANK HUB",
    # Ø4 m6 (ISO 2338), not "4 M6": the machinist review of 82158b1bb read
    # four M6 pins against QTY 1.
    "dt-vn-crank-hub-pin": "4 MM DOWEL PIN ISO 2338 m6, CUT TO PRINT",
    "dt-vn-crank-seat-drive-pin": "3/32 X 1/4 DOWEL PIN, MCMASTER 98381A434",
    "dt-alignment-pinion": "ALIGNMENT PINION",
    "dt-pinion-bracket": "PINION BRACKET STRAP",
    "dt-pinion-pivot-block": "PINION PIVOT BLOCK",
    "dt-pinion-pivot-shaft": "PINION PIVOT SHAFT",
    "dt-pinion-lift-rod": "PINION LIFT ROD",
    "dt-pinion-spring": "PINION SPRING",
    "dt-pinion-cam-pin": "PINION CAM FOLLOWER PIN",
    "dt-pinion-cam": "PINION ECCENTRIC CAM, #2-56 SET SCREW",
    "dt-pinion-lever": "PINION LEVER",
    # Grouped: its configurations' BOM description wins over a written cell,
    # so the row prints the registry description the builder stamps.
    "dt-pinion-lever-pin": str(_config.parts("dt-pinion-lever-pin")["description"]),
    "dt-pinion-handle": "PINION GRIP CROSSROD",
    "dt-pinion-arbor": "INTEGRAL PINION ARBOR AND GRIP HEAD",
    "dt-pinion-arbor-collar": "PINION ARBOR RETENTION COLLAR",
    "dt-vn-pinion-strap-pin": "1/16 X 1/2 SPRING PIN, MCMASTER 98296A027",
    "dt-vn-slotted-screw": "#8-32 FILLISTER SCREW, MCMASTER 90280A203",
}
if set(BOM_DESCRIPTIONS) != set(BOM_PART_NUMBERS):
    raise AssertionError("drive-train BOM description coverage is incomplete")
if set(BOM_PART_NUMBERS) != {component_stem(key) for keys in CLUSTERS.values() for key in keys}:
    raise AssertionError("drive-train BOM identities must cover exactly the clusters")
BOM_NORMALIZED_ALIASES = {
    number.casefold(): stem for stem, number in BOM_PART_NUMBERS.items()
}

# --- sheet wording ---------------------------------------------------------------
# Only assembly-level requirements live here; part drawings own manufacture and
# every quoted fit/process is the wording already printed on that part's sheet.
# "[PENDING ...]" marks a joint whose hardware or ruling has not landed; the
# package is not released while any remains.
_STEP_LINE_WIDTH = 70


def _note_text(rows: Sequence[str], *, heading: bool = True) -> str:
    """Reflow whole steps; retain headings, lettered heads and deeper sublists.

    One blank line separates consecutive top-level numbered steps; lettered
    sub-steps and continuation lines stay tight under their step."""
    paragraphs: list[tuple[str, str, str]] = []
    hang: str | None = None
    for row in rows:
        for source in row.splitlines():
            body = source.lstrip()
            indent = source[: len(source) - len(body)]
            head, separator, _rest = body.partition(". ")
            numbered = bool(separator) and (
                head.isdigit()
                or (head[:-1].isdigit() and head[-1:].isalpha())
                or head in ("A", "B", "C")
            )
            if numbered:
                hang = indent + " " * (len(head) + 2)
                paragraphs.append((indent, hang, body))
            elif not paragraphs and heading:
                paragraphs.append((indent, indent, body))
            elif hang is not None:
                if len(indent) <= len(hang):
                    first, continuation, previous = paragraphs[-1]
                    if continuation == hang and not previous.endswith(":"):
                        paragraphs[-1] = (first, continuation, f"{previous} {body}")
                    else:
                        paragraphs.append((hang, hang, body))
                else:
                    paragraphs.append((indent, indent, body))
            elif len(paragraphs) > int(heading):
                first, continuation, previous = paragraphs[-1]
                if continuation == indent and not previous.endswith((".", ":")):
                    paragraphs[-1] = (first, continuation, f"{previous} {body}")
                else:
                    paragraphs.append((indent, indent, body))
            else:
                paragraphs.append((indent, indent, body))
    # A page number must not become a spurious step head on a hanging line.
    # NBSP is only a wrapping token; every printed space remains ordinary.
    lines: list[str] = []
    stepped = False
    for first, continuation, body in paragraphs:
        head, separator, _rest = body.partition(". ")
        if not first and separator and head.isdigit():
            if stepped:
                lines.append("")
            stepped = True
        lines += (
            line.replace("\u00a0", " ")
            for line in textwrap.wrap(
                re.sub(r"\b(SHEETS?) (?=\d)", r"\1" + "\u00a0", body),
                width=_STEP_LINE_WIDTH,
                initial_indent=first,
                subsequent_indent=continuation,
                break_long_words=False,
                break_on_hyphens=False,
            )
        )
    return "\n".join(lines)


def _split_sequence_notes(text: str, number: int, heading: str) -> tuple[str, str]:
    """Move a whole numbered step (or check) and its successors to a
    continuation field, dropping the blank line that separated them."""
    head = f"{number}. "
    first, separator, rest = text.partition("\n\n" + head)
    if not separator:
        raise ValueError(f"note block has no head {head!r}")
    return first, f"{heading}\n{head}{rest}"


# Acceptance limits on the assembly sheets round inward at these places.
FIT_LIMIT_PLACES = 2


def _inward_limits(low: float, high: float) -> str:
    """Print only sizes inside the owning spec's acceptance interval."""
    scale = 10**FIT_LIMIT_PLACES
    return (
        f"{math.ceil(low * scale - 1e-9) / scale:.{FIT_LIMIT_PLACES}f}-"
        f"{math.floor(high * scale + 1e-9) / scale:.{FIT_LIMIT_PLACES}f}"
    )


_BANK_X = cone_line.X_DRUM + base.BOTTOM_LENGTH / 2.0
BANK_X_LIMITS = _inward_limits(
    _BANK_X - bank.FRONT_STRAP_LOCATE_BAND, _BANK_X + bank.FRONT_STRAP_LOCATE_BAND
)
_FRONT_STRAP_Y = base.BOTTOM_REAR_Z - bank.FRONT_STRAP_INNER_Z
FRONT_STRAP_Y_LIMITS = _inward_limits(
    _FRONT_STRAP_Y - bank.FRONT_STRAP_LOCATE_BAND,
    _FRONT_STRAP_Y + bank.FRONT_STRAP_LOCATE_BAND,
)
_NORTH_EAR_Y = base.BOTTOM_REAR_Z - rockers.NORTH_EAR_INNER_Z
NORTH_EAR_Y_LIMITS = _inward_limits(
    _NORTH_EAR_Y - rockers.NORTH_EAR_LOCATE_BAND,
    _NORTH_EAR_Y + rockers.NORTH_EAR_LOCATE_BAND,
)

# Step 4's pin fit is the MHA-DT-10 and MHA-DT-11 prints' own wording.
_PINION_PIN_FIT = ", ".join(pinion.PIN_FIT_LINES)
# Step 7's bond and release agents, named so the fitter buys the right ones.
HANDLE_EPOXY = "30-MINUTE TWO-PART EPOXY"
HANDLE_RELEASE = "PASTE WAX"
# Rule 23 (#1174): MHA-DT-32's lock is the arm's tap mouth staked onto the
# filed tip, after the MHA-PD-VN-57 pivot (user ruling 2026-10-15).
HANDLE_STAKE_POINTS = "2 OPPOSITE POINTS"
HANDLE_STAKE_NOTE = "\n".join(
    (
        "STAKE TAP MOUTH",
        "ONTO MHA-DT-32",
        "TIP AT 2 OPPOSITE",
        f"POINTS (STEP {steps.step_number('crank-handle-fitted')})",
    )
)
HANDLE_SCREW_STEM = "dt-crank-handle-pivot-screw"
# The installed tip, in the screw's own frame (metres): on its axis, filed
# flush with the arm's inboard face, where the stake is struck.
HANDLE_STAKE_TIP_M = (
    0.0,
    0.0,
    (handle_screw.SEAT_STATION + handle_screw.INSTALLED_THREAD_LENGTH) / 1000.0,
)
# In the full-detail side view the arm stands outboard of and below that tip,
# so the note stands below and inboard of it, its leader leaving the text's
# right end HANDLE_STAKE_NOTE_GAP short of the tip: it reaches the face from
# the open side, never across the arm (the PD pivot stake's r6 lesson,
# mirrored). INote.GetExtent spans the leader too (farm runs
# 20261018T064504517Z and 20261018T072413596Z read its right end 0.2 mm
# short of the tip), so the leader's own start is the text's right end. The
# note is seeded HANDLE_STAKE_NOTE_SEED_WIDTHS estimated widths (the note
# fields' measured 70 characters a field width) left of that, then slid
# right until its leader starts the gap short of the tip.
HANDLE_STAKE_NOTE_GAP = 0.004
HANDLE_STAKE_NOTE_DROP = 0.014
HANDLE_STAKE_NOTE_SEED_WIDTHS = 1.5
HANDLE_STAKE_NOTE_SETTLE = 0.0005
HANDLE_STAKE_NOTE_WIDTH = (
    max(len(line) for line in HANDLE_STAKE_NOTE.splitlines())
    * (NOTE_FIELD_LEFT[2] - NOTE_FIELD_LEFT[0])
    / _STEP_LINE_WIDTH
)


def handle_stake_note_xy(tip: tuple[float, float]) -> tuple[float, float]:
    """Seed top-left sheet point of the stake note for the tip at sheet ``tip``."""
    return (
        tip[0]
        - HANDLE_STAKE_NOTE_GAP
        - HANDLE_STAKE_NOTE_SEED_WIDTHS * HANDLE_STAKE_NOTE_WIDTH,
        tip[1] - HANDLE_STAKE_NOTE_DROP,
    )


# Rule 23 (#1176): each MHA-DT-23 cam's set screw is staked at the cam set;
# the machinist review of 15cf1dcbc and 8e6a0dbd8 asked for the lock in a
# view, as MHA-DT-32's is. The tap mouth in the cam's own frame (metres):
# the tap drill enters along -Y from the OD's lowest tangent plane at
# SET_SCREW_Z (build_dt_pinion_cam).
CAM_STEM = "dt-pinion-cam"
CAM_TAP_MOUTH_M = (
    0.0,
    -(cam_geometry.ECC + cam_geometry.CAM_OD / 2.0) / 1000.0,
    cam_geometry.SET_SCREW_Z / 1000.0,
)
# One leader names both cams by the 2X count: the machinist review of
# c61144555 read "STAKE EACH" with a single leader as pointing at the front
# cam only.
CAM_STAKE_NOTE = "\n".join(
    (
        "2X MHA-DT-23: STAKE",
        "TAP MOUTH AT 2 POINTS",
        f"(STEP {steps.step_number('cam-collars-set')})",
    )
)
# Sheet 12's Right view puts the front cam's tap at (229.2, 129.2) mm, above
# the base plate (bottom near y 119 mm), with its hold-down screws hanging to
# y 106 mm at x 142-145 mm and x 237-248 mm and the caption at y 90.6-95.4 mm
# (run 20261018T154747118Z, whose 22.5 mm drop overlapped the caption by
# 2.4 mm). The three-line note (about 13.7 mm tall) stands below and left of
# the tap: under the base plate, between those screws and clear above the
# caption. Its leader leaves the text's right end and climbs to the tap.
CAM_STAKE_NOTE_GAP = 0.022
CAM_STAKE_NOTE_DROP = 0.0125
CAM_STAKE_NOTE_WIDTH = (
    max(len(line) for line in CAM_STAKE_NOTE.splitlines())
    * (NOTE_FIELD_LEFT[2] - NOTE_FIELD_LEFT[0])
    / _STEP_LINE_WIDTH
)


def cam_stake_note_xy(tip: tuple[float, float]) -> tuple[float, float]:
    """Top-left sheet point of the cam stake note for the tap at sheet ``tip``."""
    return (
        tip[0] - CAM_STAKE_NOTE_GAP - CAM_STAKE_NOTE_WIDTH,
        tip[1] - CAM_STAKE_NOTE_DROP,
    )


# Step 10 screws the north MHA-CH-08 down with the channel's own hold-down.
NORTH_BRACKET_SCREW = str(_config.parts("ch-vn-bracket-hold-down-screw")["number"])
# Step 5's T12 is the paper drive's removable chain sprocket in its T12
# configuration (pd_transgear_removable_spec: T12 on the crank); the machinist
# review of 8e6a0dbd8 asked for its own number.
CRANK_CHAIN_WHEEL = str(_config.parts("pd-transgear-removable")["number"])


ASSEMBLED_HEADING = (
    f"SAVED WORKING POSE AND FREE MOTIONS: SEE SHEET {CHECKS_SHEET} FOR SETUP.\n"
    "VIEWS 1:2 AND SMALLER OMIT GEAR TEETH AND SCREW THREADS;\n"
    f"FULL DETAIL: SHEET {FULL_DETAIL_SHEET}."
)


CONE_CRANK_STEPS = _note_text(
    (
        "ASSEMBLY SEQUENCE - CONE SET AND CRANK",
        # Slide the one flat of every gear onto the shaft and close the
        # accepted stack against its collar before setting tip end play.
        "1. SLIDE MHA-DT-07 ONTO THE MHA-DT-04 D-FLAT AGAINST ITS COLLAR.",
        "   SLIDE {cone_gears}X MHA-DT-03 ON, T120 FIRST THROUGH T006,",
        f"   EACH FLAT TO FLAT AND AGAINST THE LAST. MEASURE THE {CONE_GEAR_COUNT}-GEAR",
        f"   STACK T120 SOUTH FACE TO T006 NORTH FACE: {STACK_L20_ACCEPT[0]:.3f}-"
        f"{STACK_L20_ACCEPT[1]:.3f}.",
        "   RE-FACE A LONG STACK; REMAKE THE THINNEST GEAR OF A SHORT ONE.",
        # U37c cut-to-fit acceptance survives the taller post and longer stock:
        # MHA-DT-VN-61's registry/spec own the selected screw and reference length.
        # Each screw is cut against its own matched post/platform hole, never
        # proud of the plate underside. The short-engagement fact includes
        # the stock band, cut allowance and both tap-mouth edge breaks.
        # The sheet states the actual minimum, never the governance label.
        "2. ALIGN MHA-DT-05 COUNTERBORES TO MHA-DT-20 TAPS; USE 2X",
        f"   MHA-DT-VN-61: MSC {post_screw.SKU}, {post_screw.THREAD} X "
        f"{post_screw.STOCK_LENGTH_MM / 25.4:g} IN STOCK, CUT TO FIT;",
        # Two mm places, rounded up: the step never understates the short the
        # part sheet allows (.005 in = 0.127 prints 0.13).
        f"   FLUSH TO {math.ceil(post_screw.POST_SCREW_CUT_TO_FIT_SHORT * 100.0) / 100.0:.2f} SHORT OF "
        "MHA-DT-20 UNDERSIDE, NEVER PROUD.",
        f"   ({post_screw.CUT_LENGTH_MM:.{post_screw.DRAWING_PRECISION_BY_NAME[post_screw.CUT_LENGTH_DIMENSION]}f}) "
        "REF CUT LENGTH. DEBURR ENDS; " + POST_MOUNT_ENGAGEMENT_ASSEMBLY_FACT,
        # User ruling 2026-09-29 (eight-views-4 photo): MHA-DT-21 is a prism
        # standing directly on MHA-DT-20, held by one #4-40 socket head cap
        # screw up from under the plate through its counterbored hole.  The
        # MHA-DT-VN-54 collar goes on loose here; step 3 sets it.  Whether the post
        # pattern itself can be assembled is issue #1134 (pre-existing).
        # #1074: the collar's bearing on the boss end reacts the tip
        # adjuster's preload (#914), and the model mates it (#1058).
        "   JOURNAL MHA-DT-04 IN THE MHA-DT-05 CONE BOSS UNTIL THE MHA-DT-04",
        "   COLLAR BEARS ON THE BOSS NORTH END. SLIP MHA-DT-VN-54 ON THE TIP STUB.",
        "   STAND MHA-DT-21 ON MHA-DT-20 AT ITS HOLE; MHA-DT-VN-60 UP FROM",
        "   UNDER THE PLATE THROUGH THE COUNTERBORE INTO THE MHA-DT-21 FOOT,",
        "   SNUG. LEAVE MHA-DT-VN-61 LOOSE ENOUGH TO TURN MHA-DT-05.",
        # User ruling 2026-09-29: the stack's north float is held on the
        # shaft by MHA-DT-VN-54, set off T006 by one feeler and locked on the
        # D-flat; the cup screw alone then sets MHA-DT-04's end play
        # (cone_stack_end_play).  U32 (user, 2026-09-23): option 1A turn-set,
        # worded without the pitch (#10-32: 1/8 turn is ~0.10).  The tip's
        # lateral error is taken up by turning MHA-DT-05 on its screws'
        # clearance (TIP_LATERAL_CAPACITY_MM in build_drive_train_assembly),
        # so the fitter centres the tip in the cup before locking the post
        # (Codex P1 on #1136, 9e9982c5d).  User decision 2026-10-12: the post
        # is held pushed toward the tip block while it is turned and its
        # screws tightened, so its screw clearance can only carry the shaft
        # north, away from G19 (dt_tip_collar_air).
        "3. PUSH THE STACK ONTO THE MHA-DT-04 COLLAR. PUSH MHA-DT-VN-54 ONTO A",
        f"   {COLLAR_FEELER:.2f} FEELER ON T006; LOCK ITS SET SCREW ON THE FLAT.",
        "   THREAD MHA-DT-VN-55 INTO MHA-DT-21 TO THE TIP. HOLD MHA-DT-05 PUSHED",
        "   TOWARD MHA-DT-21 ALONG THE SHAFT THROUGHOUT: TURN MHA-DT-05 ON ITS",
        "   SCREWS UNTIL THE TIP CENTRES IN THE CUP; TIGHTEN BOTH MHA-DT-VN-61",
        "   AND RECHECK. THREAD MHA-DT-VN-55 ON UNTIL MHA-DT-04 JUST STOPS",
        "   SHUTTLING AND STILL TURNS FREELY; BACK OFF 1/8 TURN; TIGHTEN",
        "   MHA-DT-VN-56 ACROSS THE SLIT. END PLAY "
        f"{SHAFT_END_PLAY[0]:.2f}-{SHAFT_END_PLAY[1]:.2f}, BY FEEL OR INDICATOR.",
        "   MHA-DT-VN-55 " + ADJUSTER_ENGAGEMENT_ASSEMBLY_FACT,
        # User ruling 2026-09-28: the crank journal runs directly in the post;
        # the centres are fixed, and the only mesh requirement is no binding.
        # CONTRACT-crank: MHA-DT-VN-67 press to the blind-hole floor (their proud
        # length is the result).  Owner ruling D1 (2026-10-15): no crank-seat
        # washer -- the collar is held hard on the boss's south face, the 16T
        # set on its feeler off the north face, and only then is its pin
        # match-drilled, so the end play is the feeler and the shaft end is
        # left proud (CRANK_END_FIT_NOTES, on the continuation sheet).
        # User ruling 2026-09-30 (#1154): the 16T's shoulder and turned band
        # are feeler-checked against T120 before the pin is drilled.  The
        # pair may rub on T120 until that check closes, so the seat and the
        # check come first, turning by hand, and the free-running revolution
        # after them (Codex P2 on #1154, review 3).  The check's last line is
        # short; the step carries on after it.
        "4. PRESS 2X MHA-DT-VN-67 TO THE MHA-DT-11 COLLAR HOLE FLOORS. FIT MHA-DT-11 IN",
        "   THE MHA-DT-05 CRANK BORE; SLIDE MHA-DT-10 ON UNPINNED, TOOTH IN GAP",
        "   WITH MHA-DT-07. HOLD THE MHA-DT-11 COLLAR HARD ON THE BOSS SOUTH FACE;",
        f"   SET MHA-DT-10 {PINION_SEAT_FEELER:.2f} OFF THE MHA-DT-05 BOSS NORTH FACE WITH A FEELER.",
        T120_FITUP_ASSEMBLY_CHECK + " THEN",
        "   TURN MHA-DT-07 ONE FULL REVOLUTION; IT MUST NEVER BIND (ELSE CHECK",
        "   THE PARTS AND BORE SPACING). THEN MATCH-DRILL THROUGH THE MHA-DT-10",
        "   BOSS AT ITS MID-LENGTH INTO MHA-DT-11; "
        + _PINION_PIN_FIT
        + "; RE-CHECK NO BINDING.",
        f"5. SLIDE {CRANK_CHAIN_WHEEL} T12 ONTO MHA-DT-11 BEFORE THE ARM, ITS HOLES OVER",
        "   THE 2X MHA-DT-VN-67.",
        # U33 (user, 2026-09-23): crank hub MHA-DT-31 pressed into the arm and
        # seam-pinned by MHA-DT-VN-59 (a 4 m6 dowel, 4.0 long = half the arm); the
        # MHA-DT-09 cross-hole runs behind the arm through the hub barrel. The
        # handle rides the MHA-DT-32 shoulder screw. Wording from crankhub.
        "6. PRESS MHA-DT-31 INTO MHA-DT-06 TO THE SHOULDER, FACES FLUSH.",
        "   MATCH-DRILL/REAM THE SEAM Ø4 X 4.0 DEEP; DRIVE MHA-DT-VN-59 FLUSH. SLIDE",
        f"   ONTO MHA-DT-11, SET HUB FRONT FACE FLUSH WITH THE {HUB_FRONT_FACE_DATUM},",
        "   PUNCH MARKS ALIGNED; ONLY THEN TAPER-REAM 1:48 THROUGH HUB AND",
        "   SHAFT; LIGHT-DRIVE MHA-DT-09, REMOVABLE BY TAP ON SMALL END. HANG",
        # Codex #1140: the keeper chain's length and topology belong on the
        # sheet; the bead count is the spec's solve, never a typed number.
        "   MHA-DT-27 FROM THE PIN HEAD; CLAMP MHA-DT-28 UNDER MHA-SH-VN-51. CUT MHA-DT-VN-65",
        f"   TO {KEEPER_CHAIN_BEADS} BEADS; THREAD IT THROUGH THE MHA-DT-28 LOOP AND MHA-DT-27; SNAP",
        "   ONE END BEAD INTO EACH DOME OF MHA-DT-VN-66.",
        # Local review of 747487c71: the cup cures centred on the screw, or
        # its offset can bind the head and shoulder.  Owner ruling 2026-10-24
        # (#1900): the ferrule cures centred on the pivot bore, the offset
        # its skimmed wall is budgeted on.  Rule 23: the handle spins on the
        # MHA-DT-32 shoulder, so the screw is staked in the arm's through tap
        # (the MHA-PD-VN-57 pivot's staked-mouth lock, user ruling
        # 2026-10-15); no threadlocker.
        "7. EPOXY MHA-DT-34 ON THE MHA-DT-08 TENON AND MHA-DT-35 IN ITS BUTT",
        f"   WITH {HANDLE_EPOXY}; CURE THEM ON MHA-DT-32, WAXED WITH {HANDLE_RELEASE},",
        f"   THROUGH BOTH; HOLD {HANDLE_FERRULE_CURE} UNTIL CURED.",
        "   WIPE THE WAX OFF MHA-DT-32; SLIDE MHA-DT-08 ON",
        "   MHA-DT-32 AND THREAD MHA-DT-32 INTO MHA-DT-06, NO THREADLOCKER,",
        "   SHOULDER TIGHT; END PLAY",
        "   0.25-1.0. FILE THE TIP FLUSH TO THE ARM INBOARD FACE, THEN STAKE THE",
        f"   TAP MOUTH ONTO IT AT {HANDLE_STAKE_POINTS} (SHEET {FULL_DETAIL_SHEET}).",
        f"   CYLINDER BANK: SHEET {BANK_SHEET}.",
    )
)

BANK_STEPS = _note_text(
    (
        "ASSEMBLY SEQUENCE - CYLINDER BANK",
        # U34c (user/Main 2026-09-23, rev 3 H1, foot 28): pedestals inboard,
        # arbor cut to the measured strap span, base holes transferred at
        # assembly. 168.2 is the arbor-axis x from the base hole-table datum
        # (plinth east face, x = -228.6), not the 161.9 REF arbor length.
        # Wording from dtscout (dt-bank-pedestal-layout-20260923.md sections 3
        # and 11): x is set on the mill DRO against the plinth east face, since
        # a square cannot resolve the band and a caliper cannot reach 168.21.
        # dtscout's 168.21 +/-0.10 prints as the limits 168.11-168.31: the
        # drawing-spec purity gate keeps bilateral bands in model/spec.
        # The band protects channel accuracy (error_budget axis_dx: drum axis
        # x against the rocker pivot tilts all 20 rods), not the cone mesh
        # (depthed at assembly) or the pinion rig (feeler-set).
        # The MHA-DT-13 print owns the stock (3/8 1018 CF X 190, long enough for
        # the edge finder) and its cut-to-fit rule (Main, r9).
        # User ruling 2026-10-20: one reduced-OD brass disc on the SOUTH strap;
        # north spring directly on gear 19. Preserve the nominal gear grid.
        # A thick south disc moves its strap south, hence PLUS its measured
        # excess in the base's rear-face Y coordinate. The north pedestal is
        # then set from the actual accepted stack, not a frozen nominal end.
        "8. MIC EACH OF {cylinder_gears}X MHA-DT-12, CAM FACE TO BACK FACE;",
        "   RECORD. SLIDE THEM ONTO A 3/8 GROUND SETTING",
        # Each connecting rod comes pinned to its rocker arm (MHA-CH-00's
        # bench pinning step, cited by key): its ring is captured in the closed
        # cam slot as the next gear goes on, so the pair travels with its gear.
        "   MANDREL ~190 LONG, ALL ALIKE, CAM SIDE FRONT; SET EACH CONNECTING",
        f"   ROD + ARM PAIR ({RODS_PINNED_REF}) ON ITS CAM AS ITS GEAR GOES ON.",
        "   CLAMP LIGHTLY END TO END: ACCEPT THE GEAR 0 CAM FACE TO GEAR 19",
        f"   NORTH FACE LENGTH SHOWN ON SHEET {BANK_SETTINGS_SHEET}. LONG: SLIDE THE GEARS",
        "   OFF IN ORDER WITH THEIR PAIRS TO THE THICKEST CAM; RE-FACE ITS",
        "   CAM FACE, RESTACK, REMEASURE. SHORT: REMAKE THE THINNEST GEAR, REMEASURE.",
        "   SLIDE THE STACK OFF, GEAR 0 FIRST, EACH GEAR WITH ITS PAIR.",
        "9. BASE MHA-FR-01 OUT OF THE FRAME, ON THE MILL TABLE, PAD TRAMMED,",
        "   OVERHANG SUPPORTED; CONE SET (MHA-DT-20) NOT FITTED.",
        "9A. FRONT MHA-DT-02 ALONE ON THE MANDREL, ON THE BASE. EDGE-FIND BOTH",
        "   MHA-FR-01 HOLE-TABLE DATUM FACES (SEE ITS PRINT); ZERO DRO X AND Y.",
        "   MIC THE MHA-DT-26, W. SET THE FRONT MHA-DT-02 INNER FACE",
        f"   TO Y {FRONT_STRAP_Y_LIMITS} PLUS (W - {BANK_WASHER_THICK:.3f}) AND THE MANDREL",
        f"   CENTRE (EDGE-FIND BOTH SIDES, HALVE) TO X {BANK_X_LIMITS}.",
        "   SPOT MHA-FR-01 THROUGH THE FOOT HOLE (11/64 TRANSFER PUNCH);",
        "   LIFT OFF. DRILL #29 X 19.5, TAP #8-32 X 16.0 (PLUG, THEN",
        "   BOTTOMING); CLEAR CHIPS. REFIT AT X AND Y; TIGHTEN",
        # Check 4 re-reads both coordinates against the step 9 setting bands
        # after the cone swing's radial shims move the pedestals.
        "   MHA-DT-VN-62, RECHECK AND RECORD X AND Y.",
        # Support the loaded mandrel until the second pedestal is fitted.
        # Lift it off before drilling: the mandrel covers that foot's hole.
        "9B. FROM THE BACK, LOAD THE MICED MHA-DT-26, THEN GEARS 0 TO 19,",
        "   CAM SIDE FRONT, THEIR PAIRS HANGING FREE, THEN MHA-DT-VN-68;",
        "   IT SLIDES FREE ON THE MANDREL (ELSE STONE ITS BORE BURR).",
        "   SEAT MHA-DT-26 DIRECTLY ON THE FRONT MHA-DT-02 AND CLOSE THE",
        "   BANK SOUTH ON THE DISC. PROP THE MANDREL BACK END AT BORE HEIGHT",
        "   (V-BLOCK ON PARALLELS); REMOVE THE PROP ONLY TO SLIDE THE BACK MHA-DT-02 ON.",
        "9C. SLIDE THE BACK MHA-DT-02 ON UNTIL THE SPRING-SET BLADE",
        f"   (SHEET {BANK_SETTINGS_SHEET}, DETAIL A), BESIDE MHA-DT-VN-68 BETWEEN THE",
        "   BACK MHA-DT-02 INNER FACE AND GEAR 19'S NORTH FACE, IS LIGHTLY PINCHED.",
        f"   SET X {BANK_X_LIMITS} AND SPOT AS 9A. SLIDE THE BACK MHA-DT-02 OFF;",
        "   DRAW THE LOADED MANDREL OUT OF THE FRONT MHA-DT-02, HOLDING",
        "   MHA-DT-26 AND MHA-DT-VN-68; LAY IT IN V-BLOCKS ON PARALLELS OFF",
        "   THE BASE, PAIRS HANGING FREE. DRILL AND TAP AS 9A. PASS THE MANDREL",
        "   BACK THROUGH THE FRONT MHA-DT-02; SEAT THE DISC AND BANK SOUTH,",
        "   PROP AS 9B. REFIT THE BACK MHA-DT-02; RE-SET THE BLADE AND X, TIGHTEN",
        "   MHA-DT-VN-62, REMOVE THE BLADE, RECHECK AND RECORD X. DRO STILL ZEROED,",
        "   DRILL AND TAP THE MHA-FR-01 PIVOT SEAT PER ITS PRINT NOTE.",
        "9D. MEASURE MHA-DT-02 OUTER FACE TO OUTER FACE. TURN MHA-DT-13: ITS",
        f"   CYLINDER IS THAT SPAN, PLUS A {bank.ARBOR_DOME_HEIGHT:.1f} DOME EACH END (SEE ITS PRINT).",
        "9E. PUSH MHA-DT-13 IN FROM THE BACK, END TO END WITH THE MANDREL, UNTIL",
        f"   THE MANDREL IS OUT AND EACH DOME STANDS {bank.ARBOR_DOME_HEIGHT:.1f} PROUD (DEPTH GAUGE).",
        "   SPOT MHA-DT-13 THROUGH EACH CROWN TAP WITH A #43 DRILL, 0.5 DEEP;",
        "   BLOW OUT CHIPS. RUN THE FRONT MHA-SH-VN-54 IN TIGHT, THEN THE BACK ONE.",
        "9F. EACH GEAR TURNS FREE BY HAND, THE BANK HELD SOUTH BY MHA-DT-VN-68.",
        # #936 P1 b, option A (user ruling 2026-09-26): the north MHA-CH-08 ear
        # is the rocker bank's axial datum (rocker_bank_layout), set here on
        # the 9A DRO zero so the cams and the rocker stations share one datum.
        # Y is the hole-table rear-face distance of the ear inner face,
        # BOTTOM_REAR_Z - NORTH_EAR_INNER_Z, held to the
        # NORTH_EAR_LOCATE_BAND edge-find. Hub 19 bears on the north MHA-CH-VN-56
        # washer against that face (user, 2026-10-10), so the target moves
        # north (LESS Y) by the miced washer's excess, W - 0.787, and hub 19
        # stays at nominal. The plain shaft threads through the set ear, so
        # the bracket stays screwed down. Channel assembly MHA-CH-00 cites
        # this step by key (channel_steps.NORTH_BRACKET_SET_REF).
        # The bracket, washer and screw are MHA-CH-00 BOM items set here on
        # the 9A DRO zero (INTERFACE_NOTES lists them); the screw is the one
        # the channel's south bracket uses.
        f"{steps.step_number(NORTH_BRACKET_SET_KEY)}. MHA-FR-05 SCREWED DOWN ON THE BASE"
        " (FRAME ASSEMBLY MHA-FR-00 STEP 8),",
        "   DRO STILL ZEROED AS 9A. FROM MHA-CH-00 TAKE THE NORTH MHA-CH-08, ONE",
        f"   {NORTH_BRACKET_SCREW} AND ONE MHA-CH-VN-56. STAND THE MHA-CH-08 ON THE MHA-FR-05",
        "   RAIL, FOOT TO THE BACK. MIC THE MHA-CH-VN-56, W. SET THE EAR",
        f"   INNER FACE TO Y {NORTH_EAR_Y_LIMITS} LESS "
        f"(W - {rocker_washer.THICKNESS:.3f});",
        "   CLAMP. DRILL AND TAP THE RAIL THROUGH ITS FOOT PER THE MHA-FR-05 SEAT",
        f"   CALLOUT (VIEW B); SCREW IT DOWN WITH THE {NORTH_BRACKET_SCREW} AND RECHECK Y.",
        "   KEEP THAT MHA-CH-VN-56 FOR THE NORTH END OF "
        f"{channel_step_ref('north-ear-datum')}.",
        # NBSP keeps the continuation pointer on one printed line.
        f"   PINION\u00a0RIG:\u00a0CONT.\u00a0ON\u00a0SHEET {FIT_SHEET}.",
    )
)

RIG_SEQUENCE_HEADING = "ASSEMBLY SEQUENCE CONT. - PINION RIG"

# The rig's own assembly steps are pinion_rig_fitup's (Codex #858,
# PRRT_kwDOPHDy386mTbPB): each part step, SHAFT DRILL SET, RIG SET and
# COLLAR SET print here word for word, re-wrapped to the field, and every
# other sheet cites them by registry key.  Unpacking fails loud if the
# fit-up sequence gains or loses a step.
(
    _ARBOR_COLLAR_STEP,
    _DRUM_BOND_STEP,
    _HANDLE_BOND_STEP,
    _CAM_PIN_BOND_STEP,
    _SHAFT_DRILL_STEP,
    _RIG_SET_STEP,
    _COLLAR_SET_STEP,
    _LEVER_PIN_STEP,
) = FITUP.ASSEMBLY_SEQUENCE

# MHA-DT-24's east-west station, in the strap's swing plane (Main's TbPB
# ruling Q2(2) A): the foot hole where the preload gates put it
# (pinion_spring_section), the crest then bearing on the parked flank.  RIG
# SET's pad leaf sets the other axis, along the bank.  The window a fitter
# must hold it in is known issue #1037, which ships this as the interim.
SPRING_EAST_WEST = (
    f"MHA-DT-24 FOOT HOLE CENTRE {SPRING_SCREW_EAST_OF_PIVOT:.1f} EAST OF THE "
    "MHA-DT-19 AXIS, CREST BEARING ON THE PARKED BACK MHA-DT-14 FLANK"
)


def _numbered_step(key: str, text: str) -> str:
    """Print a complete step with its registry head and retained sublist depth."""
    head = f"{steps.step_number(key)}. "
    hang = " " * len(head)
    first, *rest = text.splitlines()
    return _note_text((head + first, *(hang + source for source in rest)), heading=False)


def rig_steps(*, pivot_blocks: int, cams: int, slotted: int) -> str:
    """The pinion rig's steps, counted from the built assembly."""
    numbered = (
        # MHA-DT-33 and the front strap go on first: neither passes the Ø15
        # head or a bonded drum (Codex #860, PRRT_kwDOPHDy386mTbe7).
        ("arbor-collar-pinned", _ARBOR_COLLAR_STEP),
        ("drum-bonded", _DRUM_BOND_STEP),
        ("handle-bonded", _HANDLE_BOND_STEP),
        ("cam-pins-bonded", _CAM_PIN_BOND_STEP),
        (
            "cluster-hung",
            "JOURNAL THE MHA-DT-22 BACK END IN THE BACK MHA-DT-14 TOP BORE; HANG "
            f"BOTH MHA-DT-14 ON MHA-DT-19 THROUGH {pivot_blocks}X MHA-DT-18.",
        ),
        # E-a (user): the straps are pinned to the torque shaft before the
        # cams go on, which leave the pin's west edge 0.38 of air.
        (
            "straps-pinned-to-torque-shaft",
            f"{_SHAFT_DRILL_STEP}\n"
            "THE CLUSTER SWINGS FREELY; MHA-DT-19 TURNS WITH IT IN BOTH MHA-DT-18.",
        ),
        # Main's TbPB ruling (1), 2026-09-27: the set screws stay loose here;
        # the cam set tightens and stakes them once the cams are set (#1176).
        (
            "cams-and-lever-fitted",
            f"FIT {cams}X MHA-DT-23 AND MHA-DT-16 ON MHA-DT-17 IN THE MHA-DT-18 LIFT "
            "BORES, EACH CAM ECCENTRIC DOWN, ITS #2-56 SET SCREW (SUPPLIED WITH "
            "MHA-DT-23) LOOSE. SEAT MHA-DT-16 ON MHA-DT-17 TO THE BORE FLOOR.",
        ),
        # U28 corollary (Main 2026-09-23): the rig's east-west locate is its
        # parked tip gap, on the level line of centres, where block travel
        # equals gap change; the feeler is the bench rest gap, the pins on
        # the cams (pinion_rig_tip_gap).  RIG SET, next, sets it along the
        # bank.
        (
            "rig-located",
            "LOCATE THE RIG ON BASE MHA-FR-01 (FRAME ASSEMBLY MHA-FR-00); ITS SEATS "
            "ARE TRANSFERRED, NOT PRE-DRILLED. SET BOTH MHA-DT-18 LOOSE ON THE "
            f"BASE WITH MHA-DT-24 FITTED: {SPRING_EAST_WEST}. PARK MHA-DT-16: THE "
            "MHA-DT-25 PINS REST ON THE CAMS UNDER THE SPRING. FACE A MHA-DT-01 "
            "TOOTH TIP TO A MHA-DT-12 TOOTH TIP ON THE LEVEL LINE OF CENTRES. "
            f"SLIDE THE RIG IN UNTIL A {TIP_GAP.TIP_GAP_FEELER_TEXT} IS SNUG; "
            f"{TIP_GAP.TIP_GAP_ACCEPT_TEXT}. SET IT AT THE FRONT AND BACK "
            "STATIONS TO SQUARE BOTH MHA-DT-18 TO THE DRUM.",
        ),
        ("rig-set", f"{_RIG_SET_STEP}\nCLAMP BOTH MHA-DT-18."),
        # The seats' drill, tap and depth are the MHA-FR-01 transfer callouts'
        # (build_harmonic_base), so the sheet names the print, never a copy.
        (
            "rig-seats-transferred",
            f"SPOT MHA-FR-01 THROUGH THE {slotted} MHA-DT-18 HOLES AND THE MHA-DT-24 "
            "FOOT HOLE; DRILL AND TAP EACH PER ITS MHA-FR-01 TRANSFER CALLOUT. "
            f"FIT {slotted}X MHA-DT-VN-57 AND 1X MHA-SH-VN-52 AT THE SPRING FOOT.",
        ),
        # The cams' phase is set with the lever parked; the cam set then sets
        # each cam along the rod, tightens its set screw and stakes the tap.
        (
            "cam-collars-set",
            f"MHA-DT-16 AT PARK, EACH CAM ECCENTRIC DOWN;\n{_COLLAR_SET_STEP}",
        ),
        ("lever-pin-set", f"{_LEVER_PIN_STEP}\n{LEVER_PIN_HOLE_FIT}"),
        # The cone set goes on last, into the pivot seat drilled at 9C; the
        # stop and lock seats are MHA-FR-01 print holes.  Check 4 then sets
        # the swing and clamps it with MHA-DT-VN-51.
        (
            "other-base-mounting",
            "CONE SET ON THE BASE: OIL THE MHA-DT-VN-52 SHOULDER. STAND MHA-DT-20 ON "
            "MHA-FR-01 OVER THE STEP 9C PIVOT SEAT; RUN MHA-DT-VN-52 DOWN THROUGH ITS "
            "PIVOT BORE, SHOULDER SEATED HARD ON THE BASE; MHA-DT-20 SWINGS FREELY "
            "UNDER THE HEAD. RUN 1X MHA-SH-VN-52 AS SWING STOP INTO ITS TAPPED MHA-FR-01 SEAT (HOLE TABLE), "
            "HEAD SEATED. SWING THE CONE SET IN; RUN MHA-DT-VN-51 THROUGH THE MHA-DT-20 "
            "NOTCH INTO ITS TAPPED MHA-FR-01 SEAT (HOLE TABLE), FINGER-LOOSE. CHECK 4 "
            f"(SHEET {CHECKS_SHEET}) SETS THE SWING.",
        ),
    )
    # One blank line between the rig's numbered steps, as _note_text does.
    return "\n".join(
        (
            RIG_SEQUENCE_HEADING,
            "\n\n".join(_numbered_step(key, text) for key, text in numbered),
        )
    )


CHECKS = _note_text(
    (
        "ASSEMBLY-ONLY FUNCTIONAL CHECKS",
        "1. CRANK TURNS FREELY THROUGH FULL TURNS; ONE CRANK TURN TURNS THE",
        f"   CONE SET {Fraction(pinion.TEETH, gear64.TEETH)} TURN "
        f"({pinion.TEETH}T:{gear64.TEETH}T).",
        # User ruling 2026-09-28: the fixed-centre crank mesh must never bind;
        # no backlash acceptance interval or fit-up target remains.
        "2. MHA-DT-10/MHA-DT-07 TURNS WITHOUT BINDING THROUGH ONE FULL MHA-DT-07",
        "   TURN, MHA-DT-07 CLEAR OF THE UNRELIEVED MHA-DT-20 TOP THROUGHOUT;",
        "   EACH CONE GEAR MESHES ITS MHA-DT-12 PER THE MHA-DT-03 PRINT.",
        "3. EACH MHA-DT-12 TURNS FREELY ON MHA-DT-13 WITHOUT AXIAL BINDING.",
        # Prove the reversed preload seats on the south disc.
        "   PUSH GEAR 0 TOWARD THE BACK BY HAND AND RELEASE; THE BANK SPRINGS",
        "   BACK ONTO THE FRONT MHA-DT-26.",
        # MHA-SH-VN-52 is the DISENGAGED stop (build_cone_swing_platform
        # swing_hardware_geometry): engaged, the plate edge stands >= 2.0 off
        # it. The engaged mesh is SET here with MHA-DT-VN-51, not by the stop:
        # cone_set_stack (user ruling 2026-10-10). The shims line MHA-DT-13
        # up with the cone line before the pedestals tighten (Main ruling:
        # pedestal term booked at zero), then T120 is set on its feeler.  The
        # shims may move each pedestal only inside its step 9 bands, so step
        # 10 (set from the DRO zero) and the rig (re-proved by check 7) stand
        # (#1691 review r4).  Stoning is T012's only remedy: backing the swing
        # off would undo the T120 set (#1691 review r2).
        "4. CONE SWING SET (P1): LOOSEN MHA-DT-VN-51; SWING THE CONE SET ON MHA-DT-VN-52",
        "   TO THE MHA-SH-VN-52 STOP, CLEAR OF EVERY MHA-DT-12. ZERO AN INDICATOR ON",
        "   EACH MHA-DT-02 IN X AND ONE ON THE FRONT MHA-DT-02 IN Y. EASE THE",
        "   MHA-DT-02 SCREWS (MHA-DT-VN-62) TO SNUG-LOOSE. SWING IN ON RADIAL SHIMS,",
        f"   TIP TO MHA-DT-12 ROOT: {set_stack.feeler_gap_mm(12):.2f} AT T012, "
        f"{set_stack.feeler_gap_mm(120):.2f} AT T120; TIGHTEN MHA-DT-VN-62.",
        "   EACH RECORDED X (9A, 9C) PLUS ITS X READING IS "
        f"{BANK_X_LIMITS};",
        "   FRONT INNER-FACE Y RECORDED IN 9A PLUS ITS Y READING IS WITHIN",
        "   THE 9A Y LIMITS, USING THE SAME W. IF OUT, EASE THAT PEDESTAL,",
        "   RESET WITHIN THOSE LIMITS ON ITS INDICATORS AND TIGHTEN. STEPS "
        f"{steps.step_number(NORTH_BRACKET_SET_KEY)}",
        f"   AND {steps.step_number('rig-located')}-"
        f"{steps.step_number('rig-seats-transferred')} STAND; CHECK 7 RE-PROVES THE RIG.",
        "   SWING OUT AND REMOVE THE SHIMS. SWING IN UNTIL A "
        f"{set_stack.feeler_gap_mm(120):.2f} FEELER IS SNUG T120 TIP TO ROOT; HOLD",
        "   IT THERE AND TIGHTEN MHA-DT-VN-51. DO NOT LOOSEN MHA-DT-02 AFTER",
        "   THIS SET; IF YOU DO, REPEAT CHECKS 4, 5, 6 AND 7.",
        # User ruling 2026-10-10: T012's arithmetic worst-corner overlap is a
        # REF fit-up note, never a gate (dt_mesh_checks; the RSS corner is gated).
        "   IF T012 BINDS AFTER THE SET (WORST-CORNER OVERLAP "
        f"{-mesh_checks.cone_check(12).interference_margin_worst_mm:.2f} REF), STONE",
        "   THE T012 TIP UNTIL IT TURNS FREE; THE T120 SET STANDS.",
        "   VERIFY MHA-DT-VN-52 FULL-FORM THREAD ENGAGEMENT "
        f"{pivot_screw.MIN_USEFUL_ENGAGEMENT_TEXT}; SHOULDER FULLY SEATED.",
        "   VERIFY THE MHA-SH-VN-52 SWING STOP FULL-FORM THREAD ENGAGEMENT "
        f"{stop_screw.MIN_USEFUL_ENGAGEMENT_TEXT};",
        "   HEAD FULLY SEATED; MHA-DT-20 REMAINS SEATED THROUGH P1.",
        "5. ZEROING (P2), CONE SET SWUNG CLEAR: TURN EACH MHA-DT-12 BY HAND",
        "   UNTIL ITS NOTCH LINES UP. TURN MHA-DT-16 TO ENGAGE MHA-DT-01; TURN",
        "   MHA-DT-01 BY MHA-DT-15 UNTIL ALL NOTCHES POINT UP (COSINES) OR 90 DEG",
        "   (SINES), FINISHING IN THE CYLINDERS' RUNNING DIRECTION TO TAKE UP PLAY.",
        # The saved pose is engaged with MHA-DT-VN-51 tight (SETUP_NOTES): P2
        # ends by re-setting the swing as check 4 does.
        "   RETURN MHA-DT-16 TO PARK. SWING THE CONE SET IN UNTIL THE "
        f"{set_stack.feeler_gap_mm(120):.2f} FEELER",
        "   IS SNUG T120 TIP TO ROOT AND TIGHTEN MHA-DT-VN-51: THE CHECK 4 SETTING.",
        "6. PARKED, MHA-DT-24 HOLDS MHA-DT-01 CLEAR OF EVERY MHA-DT-12.",
        f"7. PARKED, PINS ON THE CAMS: A {TIP_GAP.TIP_GAP_FEELER:.2f} FEELER IS SNUG TIP TO TIP",
        f"   AT THE FRONT AND BACK STATIONS; {TIP_GAP.TIP_GAP_ACCEPT_TEXT}",
        f"   (SHEET {FIT_SHEET}, STEP {steps.step_number('rig-located')}). IF A STATION IS OUT,",
        "   EASE THE MHA-DT-VN-57 SCREWS, RE-SET THE RIG ON THE FEELER AT BOTH STATIONS",
        f"   AS STEP {steps.step_number('rig-located')}, WITH THE STEP "
        f"{steps.step_number('rig-set')} LEAVES REFITTED SNUG;",
        "   TIGHTEN, RECHECK THOSE LEAVES AND REPEAT CHECKS 6 AND 7.",
    )
)

# Rule 25: the saved pose and every check agree.  MHA-DT-VN-51 clamps the cone
# set's swing and is loosened only for checks 4 and 5.
SETUP_NOTES = _note_text(
    (
        "SAVED POSE AND FREE MOTIONS",
        "SAVED DEFAULT: CONE SET ENGAGED AND CLAMPED BY MHA-DT-VN-51 (CHECK 4),",
        "MHA-DT-01 PARKED CLEAR, CAMS ECCENTRIC DOWN, CRANK ARM DOWN.",
        "FREE, NEVER LOCKED: CRANK SPIN, PINION SWING, LIFT-ROD/CAM SPIN.",
        "CONE-SET SWING: CLAMPED; LOOSEN MHA-DT-VN-51 ONLY FOR CHECKS 4 AND 5.",
    )
)

INTERFACE_NOTES = _note_text(
    (
        "EXTERNAL INTERFACES (RECEIVING PARTS NOT IN THIS BOM)",
        "BASE MHA-FR-01 (FRAME ASSEMBLY MHA-FR-00) RECEIVES MHA-DT-VN-52, MHA-DT-VN-51,",
        "MHA-SH-VN-52 ({stop} SWING STOP + {foot} SPRING FOOT), {slotted}X MHA-DT-VN-57 AND",
        "{hold_down}X MHA-DT-VN-62.",
        f"PAPER DRIVE MHA-PD-00: {CRANK_CHAIN_WHEEL} T12 CHAIN WHEEL ON MHA-DT-11.",
        "FRAME ASSEMBLY MHA-FR-00: ITS MHA-FR-05 RAIL TAKES THE NORTH MHA-CH-08 "
        f"AT STEP {steps.step_number(NORTH_BRACKET_SET_KEY)}.",
        "CHANNEL ASSEMBLY MHA-CH-00:",
        "   CONNECTING RODS RUN ON THE MHA-DT-12 CAMS.",
        f"   ITS NORTH MHA-CH-08, ONE MHA-CH-VN-56 AND ONE {NORTH_BRACKET_SCREW} ARE SET "
        f"AT STEP {steps.step_number(NORTH_BRACKET_SET_KEY)}.",
    )
)

# Main ruling 2026-09-23 on the Fable C6 finding; ISO VG 32 matches the
# fleet's finish notes.
CONSUMABLES_NOTES = _note_text(
    (
        "GENERAL ASSEMBLY NOTES",
        # Every running fit, not only the bank's journals (machinist review of
        # 15cf1dcbc): the crank, cone shaft and rig journals run oiled too.
        "OIL ALL RUNNING JOURNALS AND PIVOTS WITH ISO VG 32",
        "MACHINE OIL. NO THREADLOCKER ON ANY THREAD. RUN EVERY SCREW IN SNUG",
        "UNLESS ITS STEP GIVES ANOTHER SETTING.",
    )
)

# The steps' compass and FRONT/BACK words, keyed once over step 1 (machinist
# review of 53a7c4266: EAST in the rig steps could not be worked out). Model
# -Z is south, the machine front; -X is east (the builder's block screws, "east
# screw first (-x)"). Sheet 1's general notes field has no line to spare.
# One reflowed paragraph (heading=False): as a heading, the 72-character first
# line wrapped "TIP" onto its own line (machinist review of 82158b1bb).
DIRECTION_NOTES = _note_text(
    (
        "DIRECTIONS: FRONT IS SOUTH, THE CRANK END; BACK IS NORTH, THE CONE",
        "TIP END. SHEET 1: THE TOP VIEW HAS SOUTH UP AND EAST LEFT; THE",
        "FRONT VIEW LOOKS SOUTH, EAST AT ITS LEFT; THE RIGHT VIEW LOOKS",
        "EAST, SOUTH AT ITS RIGHT.",
    ),
    heading=False,
)

FIT_PLACEHOLDER = _note_text(
    (
        # U31 (pivot): the bored spacing fixes the mesh; check 2 proves it.
        # The rest of the old placeholder is owned elsewhere now: each cone
        # gear's mesh by the MHA-DT-03 print (check 2), the pinion engagement
        # by the rig-located step and check 7, the taper pin by step 6.
        f"{pinion.TEETH}T:{gear64.TEETH}T CENTRE DISTANCE FIXED BY MHA-DT-05 "
        "BORE SPACING; VERIFY NO",
        "BINDING THROUGH ONE FULL MHA-DT-07 TURN (CHECK 2).",
    ),
    heading=False,
)

# Owner ruling D1 (2026-10-15): the collar bears on the boss with no washer,
# the 16T's feeler is the end play, and the shaft end stands proud of the
# 16T by dt_crankshaft_spec.SHAFT_END_PROUD_RANGE at every accepted part set;
# it is left as it comes, not faced.
CRANK_END_FIT_NOTES = _note_text(
    (
        f"MHA-DT-11 CRANK END FIT (STEP {steps.step_number('crank-mesh-checked')})",
        "A. MHA-DT-11 COLLAR REAR FACE HARD ON THE MHA-DT-05 BOSS SOUTH FACE;",
        "   NO WASHER.",
        f"B. MHA-DT-10 ON THE {PINION_SEAT_FEELER:.2f} FEELER OFF THE BOSS NORTH FACE, "
        "THEN",
        "   MATCH-DRILL AND REAM FOR MHA-DT-29 AS STEP "
        f"{steps.step_number('crank-mesh-checked')}. END PLAY = THE FEELER.",
        f"C. MHA-DT-11 END STANDS {max(CRANK_END_PROUD_RANGE[0], 0.0):.2f}-"
        f"{CRANK_END_PROUD_RANGE[1]:.2f} PROUD OF MHA-DT-10 NORTH FACE;",
        "   LEAVE IT PROUD, DO NOT FACE.",
    )
)

# The blank lines between steps leave sheet 7's left field room for steps 1-3
# only: steps 4-5 go to its right field and the crank's 6-7 to sheet 8.  Steps
# 4 and 5 stay on SEQUENCE_SHEET, where MHA-PD-00 cites them.
CRANK_SEQUENCE_HEADING = "ASSEMBLY SEQUENCE CONT. - CRANK"
CONE_CRANK_PRIMARY, _CONE_CRANK_REST = _split_sequence_notes(
    CONE_CRANK_STEPS,
    steps.step_number("crank-mesh-checked"),
    CRANK_SEQUENCE_HEADING,
)
CONE_CRANK_CONTINUED, CRANK_SHEET_STEPS = _split_sequence_notes(
    _CONE_CRANK_REST,
    steps.step_number("crank-hub-fitted"),
    CRANK_SEQUENCE_HEADING,
)
BANK_PRIMARY, BANK_CONTINUED = _split_sequence_notes(
    BANK_STEPS,
    steps.step_number(NORTH_BRACKET_SET_KEY),
    "ASSEMBLY SEQUENCE CONT. - NORTH BRACKET",
)
# With the blank lines, checks 1-7 overran sheet 13's left field by 5.2 mm and
# check 7 does not fit its right field under the saved pose and interfaces.
CHECKS_CONTINUED_FROM = 7
CHECKS_PRIMARY, CHECKS_CONTINUED = _split_sequence_notes(
    CHECKS,
    CHECKS_CONTINUED_FROM,
    "ASSEMBLY-ONLY FUNCTIONAL CHECKS (CONT.)",
)


# ============================ pure helpers ======================================


def _source_fingerprint(path: Path) -> tuple[int, int, str]:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns, digest.hexdigest()


def note_field_violations(
    extent: tuple[float, float, float, float],
    field: tuple[float, float, float, float],
) -> list[str]:
    """Name every edge of a note box (x0, y0, x1, y1) that leaves its field."""
    x0, y0, x1, y1 = extent
    left, top, right, bottom = field
    violations = []
    if x0 < left - 1e-6:
        violations.append(f"left {x0 * 1000:.2f} mm < field {left * 1000:.2f}")
    if x1 > right + 1e-6:
        violations.append(f"right {x1 * 1000:.2f} mm > field {right * 1000:.2f}")
    if y1 > top + 1e-6:
        violations.append(f"top {y1 * 1000:.2f} mm > field {top * 1000:.2f}")
    if y0 < bottom - 1e-6:
        violations.append(f"bottom {y0 * 1000:.2f} mm < field {bottom * 1000:.2f}")
    return violations


def bank_setting_caption_violations(
    extent: tuple[float, float, float, float],
    outline: tuple[float, float, float, float],
) -> list[str]:
    """Actual caption ink must retain at least 4 mm below its view.

    ``_anchor_note`` steers toward a point; its bounded moves do not promise
    that point. The functional postcondition is measured air, not target error.
    """
    if not all(map(math.isfinite, (*extent, *outline))):
        return ["non-finite caption extent or view outline"]
    findings = []
    gap = outline[1] - extent[3]
    if gap < VIEW_CAPTION_GAP:
        findings.append(
            f"caption is not 4 mm below its view: actual_gap_mm={gap * 1000.0:.6f}, "
            f"view_outline_m={outline!r}"
        )
    return findings


def bank_setting_letter_violations(
    extent: tuple[float, float, float, float],
    centre: tuple[float, float],
    radius: float,
) -> list[str]:
    """Keep the complete identifier at least 4 mm above-left of its circle."""
    if not all(map(math.isfinite, (*extent, *centre, radius))):
        return ["non-finite detail identifier extent or circle"]
    air = (centre[0] - radius - extent[2], extent[1] - centre[1] - radius)
    if min(air) < VIEW_CAPTION_GAP:
        return [
            "detail identifier crowds its boundary circle: "
            f"actual_gaps_mm={tuple(value * 1000.0 for value in air)!r}, "
            f"circle_centre_m={centre!r}, circle_radius_mm={radius * 1000.0:.6f}"
        ]
    return []


def ring_fit_shift(
    outline: tuple[float, float, float, float],
    region: tuple[float, float, float, float],
    *,
    grow: float,
) -> tuple[tuple[float, float], list[str]]:
    """Shift that centres an outline's balloon ring in a region, plus overflows."""
    ring = (outline[0] - grow, outline[1] - grow, outline[2] + grow, outline[3] + grow)
    x0, y0, x1, y1 = region
    ring_w, ring_h = ring[2] - ring[0], ring[3] - ring[1]
    overflows = [
        f"{axis} {size * 1000:.1f} mm > {room * 1000:.1f} mm"
        for axis, size, room in (("width", ring_w, x1 - x0), ("height", ring_h, y1 - y0))
        if size > room
    ]
    shift = (
        (x0 + x1) / 2.0 - (ring[0] + ring[2]) / 2.0,
        (y0 + y1) / 2.0 - (ring[1] + ring[3]) / 2.0,
    )
    return shift, overflows


def ring_keep_out_shift_x(
    outline: tuple[float, float, float, float],
    shift: tuple[float, float],
    *,
    margin: float,
    balloon_radius: float,
    keep_out: tuple[float, float, float, float],
) -> float:
    """The x shift that keeps the balloon ring's low arc left of a keep-out.

    ``_spread_balloons`` puts every balloon centre on the ellipse ``margin``
    outside the (shifted) outline, so the ellipse bounds where a balloon can
    land.  ``keep_out`` is (left, bottom, right, top), already grown by the
    clearance.  Where the ellipse dips low enough for a balloon to reach below
    the keep-out's top, its right-most balloon must stay left of the keep-out:
    returns ``shift[0]`` when that holds, else the shift that just makes it.
    """
    left, _bottom, _right, top = keep_out
    rx = (outline[2] - outline[0]) / 2.0 + margin
    ry = (outline[3] - outline[1]) / 2.0 + margin
    cx = (outline[0] + outline[2]) / 2.0 + shift[0]
    cy = (outline[1] + outline[3]) / 2.0 + shift[1]
    low = (top + balloon_radius - cy) / ry  # sin of the arc's upper edge
    if low <= -1.0:
        return shift[0]
    reach = rx if low >= 0.0 else rx * math.sqrt(1.0 - low * low)
    limit = left - balloon_radius - reach
    return shift[0] if cx <= limit else shift[0] - (cx - limit)


def cluster_ring_fit(
    outline: tuple[float, float, float, float],
) -> tuple[tuple[float, float], list[str], float]:
    """Shift that fits a cluster view's balloon ring, its overflows, its slide.

    The ring is centred in CLUSTER_RING_REGION. A ring taller than the region
    spills below it, where the title block takes the sheet's right half, so it
    slides left until its low arc clears the block (rim-124f: items 5 and 33
    landed on it); a slide that pushes it past the region's left is an overflow.
    Only the outline's size matters: the shift re-centres wherever it landed.
    """
    shift, overflows = ring_fit_shift(outline, CLUSTER_RING_REGION, grow=CLUSTER_RING_REACH)
    template = DRAWING_TEMPLATES[SPEC.layout]
    keep_out = (
        template.title_block_left_m - CLUSTER_TITLE_BLOCK_CLEARANCE,
        0.0,
        template.width_m,
        template.title_block_top_m + CLUSTER_TITLE_BLOCK_CLEARANCE,
    )
    x = ring_keep_out_shift_x(
        outline,
        shift,
        margin=CLUSTER_BALLOON_MARGIN,
        balloon_radius=BALLOON_DIAMETER / 2.0,
        keep_out=keep_out,
    )
    ring_left = outline[0] + x - CLUSTER_RING_REACH
    if ring_left < CLUSTER_RING_REGION[0]:
        overflows.append(
            f"left {ring_left * 1000:.1f} mm < {CLUSTER_RING_REGION[0] * 1000:.1f} mm "
            "clearing the title block"
        )
    return (x, shift[1]), overflows, x - shift[0]


def _scale_text(scale: tuple[float, float]) -> str:
    return f"{scale[0]:g}:{scale[1]:g}"


def cluster_ring_scale(
    outline: tuple[float, float, float, float],
    placed: tuple[float, float],
    *,
    label: str,
) -> tuple[float, float]:
    """The largest ladder scale, from ``placed`` down, whose balloon ring fits.

    ``outline`` is the view's outline at ``placed``; a view's outline scales
    with its scale, and the fit reads only its size (cluster_ring_fit).
    Raises naming every scale's overflow when none on the ladder fits.
    """
    if placed not in CLUSTER_SCALE_LADDER:
        raise ValueError(f"{label}: scale {_scale_text(placed)} is not on the ladder")
    x0, y0, x1, y1 = outline
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    findings = []
    for scale in CLUSTER_SCALE_LADDER[CLUSTER_SCALE_LADDER.index(placed) :]:
        k = (scale[0] / scale[1]) / (placed[0] / placed[1])
        hw, hh = (x1 - x0) / 2.0 * k, (y1 - y0) / 2.0 * k
        _shift, overflows, _slide = cluster_ring_fit((cx - hw, cy - hh, cx + hw, cy + hh))
        if not overflows:
            return scale
        findings.append(f"{_scale_text(scale)}: {'; '.join(overflows)}")
    raise ValueError(
        f"{label}: no ladder scale fits the balloon ring in the cluster region "
        f"({' | '.join(findings)})"
    )


def full_detail_scale(
    outline: tuple[float, float, float, float],
    placed: tuple[float, float],
    *,
    region: tuple[float, float, float, float] = FULL_DETAIL_REGION,
) -> tuple[float, float]:
    """The largest FULL_DETAIL_SCALE_LADDER scale whose view fits ``region``.

    ``outline`` is the view's outline at ``placed``; only its size matters
    (the build then centres the view in the region). Raises naming every
    scale's overflow when even 1:2 does not fit: shrinking further would put
    the view under the simplified-view threshold, so that is a layout ruling,
    not a fallback.
    """
    width, height = outline[2] - outline[0], outline[3] - outline[1]
    room_w, room_h = region[2] - region[0], region[3] - region[1]
    findings = []
    for scale in FULL_DETAIL_SCALE_LADDER:
        k = (scale[0] / scale[1]) / (placed[0] / placed[1])
        overflows = [
            f"{axis} {size * k * 1000:.1f} mm > {room * 1000:.1f} mm"
            for axis, size, room in (("width", width, room_w), ("height", height, room_h))
            if size * k > room
        ]
        if not overflows:
            return scale
        findings.append(f"{_scale_text(scale)}: {'; '.join(overflows)}")
    raise ValueError(
        "no full-detail scale fits the drive train in its sheet field "
        f"({' | '.join(findings)})"
    )


def centre_shift(
    outline: tuple[float, float, float, float],
    region: tuple[float, float, float, float],
) -> tuple[float, float]:
    """The sheet-space shift that centres ``outline`` in ``region``."""
    return (
        (region[0] + region[2]) / 2.0 - (outline[0] + outline[2]) / 2.0,
        (region[1] + region[3]) / 2.0 - (outline[1] + outline[3]) / 2.0,
    )


def balloon_attachment_violations(
    records: Sequence[tuple[str, str, tuple[str, ...]]],
    expected: dict[str, str],
) -> list[str]:
    """Findings for balloons whose attached component is not their BOM item,
    or whose item SolidWorks could not resolve (``?`` or no text)."""
    findings = []
    seen: dict[str, int] = {}
    for name, item, stems in records:
        if not balloon_item_resolved(item):
            findings.append(f"{name} shows unresolved item {item!r}")
            continue
        if len(stems) != 1:
            findings.append(f"{name} (item {item}) attaches to {list(stems)!r}")
            continue
        stem = stems[0]
        seen[stem] = seen.get(stem, 0) + 1
        want = expected.get(stem)
        if want is None:
            findings.append(f"{name} (item {item}) attaches to unballooned {stem}")
        elif want != item:
            findings.append(f"{name} shows item {item} but attaches to {stem} (item {want})")
    for stem, item in sorted(expected.items()):
        if seen.get(stem, 0) != 1:
            findings.append(
                f"{stem} (item {item}) carries {seen.get(stem, 0)} balloons, expected 1"
            )
    return findings


def bom_row_fit(requested: float, actual: float) -> Literal["short", "exact", "grown"]:
    """Classify a persisted BOM row height against the requested height."""
    if actual < requested - BOM_HEIGHT_TOLERANCE:
        return "short"
    if actual <= requested + BOM_HEIGHT_TOLERANCE:
        return "exact"
    return "grown"


def bom_split_row(data_rows: int) -> int:
    """Data rows in the FIRST column: the smaller half, so the first piece never
    grows into the reference view below it; the second has open paper below.
    (#948 ruling R's MHA-DT-VN-68 made the count odd: 28 rows met the view.)"""
    if data_rows < 2:
        raise ValueError("a split BOM needs at least two data rows")
    return data_rows // 2


def bom_extent_violations(
    anchor: tuple[float, float],
    width: float,
    height: float,
) -> list[str]:
    """Name every way a top-left-anchored BOM piece leaves its paper budget."""
    template = DRAWING_TEMPLATES[SPEC.layout]
    left, top = anchor
    right = left + width
    bottom = top - height
    clearance = BOM_SHEET_CLEARANCE
    violations = []
    if left < clearance:
        violations.append(f"left edge {left * 1000:.3f} mm is off the sheet")
    if right > template.width_m - clearance:
        violations.append(
            f"right edge {right * 1000:.3f} mm passes "
            f"{(template.width_m - clearance) * 1000:.3f} mm"
        )
    if top > template.height_m - clearance:
        violations.append(
            f"top edge {top * 1000:.3f} mm passes "
            f"{(template.height_m - clearance) * 1000:.3f} mm"
        )
    title_block_floor = template.title_block_top_m + clearance
    if right > template.title_block_left_m and bottom < title_block_floor:
        violations.append(
            f"bottom edge {bottom * 1000:.3f} mm enters the title block "
            f"(floor {title_block_floor * 1000:.3f} mm)"
        )
    if bottom < clearance:
        violations.append(f"bottom edge {bottom * 1000:.3f} mm is off the sheet")
    ref_left, ref_top, ref_right, _ref_bottom = BOM_REFERENCE_FIELD
    if left < ref_right and right > ref_left and bottom < ref_top:
        violations.append(
            f"bottom edge {bottom * 1000:.3f} mm enters the BOM reference field "
            f"(top {ref_top * 1000:.3f} mm)"
        )
    return violations


def bom_reference_iso_violations(outline: tuple[float, ...]) -> list[str]:
    """Hold the reference view within its reserved field below BOM piece 1."""
    return note_field_violations(tuple(outline), BOM_REFERENCE_VIEW_FIELD)


def cluster_members(
    instances: Sequence[Instance],
) -> dict[Cluster, tuple[str, ...]]:
    """Component names per drawing cluster; each occurrence sits in exactly one."""
    members: dict[Cluster, list[str]] = {cluster: [] for cluster in CLUSTERS}
    for instance in instances:
        owners = [c for c, keys in CLUSTERS.items() if instance_selector(instance) in keys]
        if not owners:
            raise ValueError(f"{instance.name}: family {instance.stem!r} has no cluster")
        if len(owners) != 1:
            raise ValueError(f"{instance.name}: family in clusters {owners!r}")
        members[owners[0]].append(instance.name)
    return {cluster: tuple(sorted(names)) for cluster, names in members.items()}


def instance_counts(instances: Sequence[Instance]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for instance in instances:
        counts[instance.stem] = counts.get(instance.stem, 0) + 1
    return counts


def bom_components(counts: dict[str, int]) -> tuple[str, ...]:
    """The BOM families the model carries, in cluster order."""
    ordered = [component_stem(key) for keys in CLUSTERS.values() for key in keys]
    seen: list[str] = []
    for stem in ordered:
        if stem in counts and stem not in seen:
            seen.append(stem)
    return tuple(seen)


def source_violations(counts: dict[str, int]) -> list[str]:
    """Refusals for a source whose families the package cannot represent."""
    findings = []
    unknown = unclassified_stems(sorted(counts))
    if unknown:
        findings.append(f"unclassified or retired families {unknown!r}")
    required = set(BOM_PART_NUMBERS) - PENDING_STEMS
    missing = sorted(required - set(counts))
    if missing:
        findings.append(f"released families missing from the model {missing!r}")
    return findings


def cone_station_rows(
    gears: Sequence[tuple[float, str]],
) -> list[tuple[int, str]]:
    """(station, configuration) front (-z) to back from (world z mm, config)."""
    ordered = sorted(gears)
    return [(index, config) for index, (_z, config) in enumerate(ordered, start=1)]


def station_table_text(rows: Sequence[tuple[int, str]]) -> str:
    """Two-column station table: STN n  MHA-DT-03 Tnnn."""
    half = (len(rows) + 1) // 2
    lines = ["CONE STATION TABLE - MHA-DT-03 BY STATION, FRONT TO BACK"]
    for left, right in zip(rows[:half], [*rows[half:], None]):
        text = f"STN {left[0]:>2}  {left[1]}"
        if right is not None:
            text += f"      STN {right[0]:>2}  {right[1]}"
        lines.append(text)
    return "\n".join(lines)


def heading_text(sheet_number: int, text: str = "") -> str:
    """A sheet heading: the drawing number and sheet name, then ``text``."""
    lines = [f"{DRAWING_NUMBER} - {SHEET_NAMES[sheet_number - 1]}"]
    if text:
        lines.append(text)
    return "\n".join(lines)


def general_notes_field(
    heading_bottom: float, iso_top: float
) -> tuple[float, float, float, float]:
    """Sheet 1's general-notes field: under the heading, over the isometric."""
    return (
        ASSEMBLED_HEADING_XY[0],
        heading_bottom - NOTE_BLOCK_GAP,
        NOTE_FIELD_RIGHT[2],
        iso_top + GENERAL_NOTES_ISO_GAP,
    )


class NoteField(NamedTuple):
    """One fixed-text note field: ``blocks`` stack top-down inside ``bounds``."""

    sheet: int
    label: str
    bounds: tuple[float, float, float, float]
    blocks: tuple[tuple[str, str], ...]


def package_note_fields(facts: SourceFacts) -> tuple[NoteField, ...]:
    """Every note field the package stacks, in placement order.

    Sheet 1's bounds here are nominal (the heading's lines at NOTE_LINE_PITCH
    under ASSEMBLED_HEADING_XY, the isometric's top at ASSEMBLED_ISO_TOP); its
    placement re-derives them from the measured heading and isometric.
    """
    heading_lines = len(heading_text(1, ASSEMBLED_HEADING).splitlines())
    cone_gears = facts.count("dt-cone-gear")
    rig_primary, rig_continued = _split_sequence_notes(
        rig_steps(
            pivot_blocks=facts.count("dt-pinion-pivot-block"),
            cams=facts.count("dt-pinion-cam"),
            slotted=facts.count("dt-vn-slotted-screw"),
        ),
        steps.step_number("rig-set"),
        RIG_SEQUENCE_HEADING,
    )
    return (
        NoteField(
            1,
            "sheet 1 general notes field",
            general_notes_field(
                ASSEMBLED_HEADING_XY[1] - heading_lines * NOTE_LINE_PITCH,
                ASSEMBLED_ISO_TOP,
            ),
            (("general assembly notes", CONSUMABLES_NOTES),),
        ),
        NoteField(
            SEQUENCE_SHEET,
            f"sheet {SEQUENCE_SHEET} left note field",
            NOTE_FIELD_LEFT,
            (
                ("direction key", DIRECTION_NOTES),
                (
                    "cone and crank sequence",
                    CONE_CRANK_PRIMARY.format(cone_gears=cone_gears)
                    + f"\nCONT. STEP {steps.step_number('crank-mesh-checked')}: "
                    "RIGHT FIELD.",
                ),
            ),
        ),
        NoteField(
            SEQUENCE_SHEET,
            f"sheet {SEQUENCE_SHEET} right note field",
            ISO_RIGHT_FIELD,
            (
                (
                    "crank sequence continuation",
                    CONE_CRANK_CONTINUED
                    + f"\nCONT. STEP {steps.step_number('crank-hub-fitted')}: "
                    f"SHEET {CRANK_SHEET}.",
                ),
            ),
        ),
        NoteField(
            CRANK_SHEET,
            f"sheet {CRANK_SHEET} left note field",
            NOTE_FIELD_LEFT,
            (("crank sequence", CRANK_SHEET_STEPS),),
        ),
        NoteField(
            BANK_SHEET,
            f"sheet {BANK_SHEET} left note field",
            NOTE_FIELD_LEFT,
            (
                (
                    "cylinder bank sequence",
                    BANK_PRIMARY.format(cylinder_gears=facts.count("dt-cylinder-gear"))
                    + f"\nCONT. STEP {steps.step_number(NORTH_BRACKET_SET_KEY)}: "
                    "RIGHT FIELD.",
                ),
            ),
        ),
        NoteField(
            BANK_SHEET,
            f"sheet {BANK_SHEET} right note field",
            ISO_RIGHT_FIELD,
            (("north bracket sequence", BANK_CONTINUED),),
        ),
        NoteField(
            FIT_SHEET,
            f"sheet {FIT_SHEET} left note field",
            NOTE_FIELD_LEFT,
            (
                (
                    "pinion rig sequence",
                    rig_primary
                    + f"\nCONT. STEP {steps.step_number('rig-set')}: "
                    f"SHEET {CONTINUATION_SHEET}.",
                ),
            ),
        ),
        NoteField(
            FIT_SHEET,
            f"sheet {FIT_SHEET} right note field",
            ISO_RIGHT_FIELD,
            (
                ("cone station table", station_table_text(facts.cone_rows())),
                ("fit placeholder", FIT_PLACEHOLDER),
                ("crank fit pointer", f"MHA-DT-11 CRANK END FIT: SHEET {CONTINUATION_SHEET}."),
            ),
        ),
        NoteField(
            CONTINUATION_SHEET,
            f"sheet {CONTINUATION_SHEET} left note field",
            NOTE_FIELD_LEFT,
            (("pinion rig sequence continuation", rig_continued),),
        ),
        NoteField(
            CONTINUATION_SHEET,
            f"sheet {CONTINUATION_SHEET} right note field",
            ISO_RIGHT_FIELD,
            (("crank end fit", CRANK_END_FIT_NOTES),),
        ),
        NoteField(
            CHECKS_SHEET,
            f"sheet {CHECKS_SHEET} left note field",
            NOTE_FIELD_LEFT,
            (
                (
                    "functional checks",
                    CHECKS_PRIMARY
                    + f"\nCONT. CHECK {CHECKS_CONTINUED_FROM}: "
                    f"SHEET {CHECKS_CONTINUATION_SHEET}.",
                ),
            ),
        ),
        NoteField(
            CHECKS_SHEET,
            f"sheet {CHECKS_SHEET} right note field",
            ISO_RIGHT_FIELD,
            (
                ("saved pose", SETUP_NOTES),
                (
                    "external interfaces",
                    INTERFACE_NOTES.format(
                        slotted=facts.count("dt-vn-slotted-screw"),
                        foot=facts.role_count(FOOT_SCREW_SELECTOR),
                        stop=facts.role_count(SWING_STOP_SCREW_SELECTOR),
                        hold_down=facts.count("dt-vn-pedestal-hold-down-screw"),
                    ),
                ),
            ),
        ),
        NoteField(
            CHECKS_CONTINUATION_SHEET,
            f"sheet {CHECKS_CONTINUATION_SHEET} left note field",
            NOTE_FIELD_LEFT,
            (("functional checks continuation", CHECKS_CONTINUED),),
        ),
    )


# ============================ COM helpers =======================================


def _activate_sheet(adapter: Any, name: str) -> None:
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    if not ddoc.ActivateSheet(name):
        raise RuntimeError(f"failed to activate drawing sheet {name!r}")
    current = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
    if current is None:
        raise RuntimeError("drawing has no current sheet after activation")
    actual = str(current.GetName() or "")
    if actual != name:
        raise RuntimeError(f"active drawing sheet is {actual!r}, expected {name!r}")


def _add_note_block(adapter: Any, text: str, xy: tuple[float, float], *, label: str) -> Any:
    note = add_note(adapter, text, *xy)
    if note is None:
        raise RuntimeError(f"failed to add {label}")
    note = _early_bound(note, "INote")
    actual = str(note.GetText() or "").replace("\r\n", "\n").replace("\r", "\n")
    expected = text.replace("\r\n", "\n").replace("\r", "\n")
    if actual != expected:
        raise RuntimeError(
            f"{label} text did not persist "
            f"(actual_length={len(actual)}, expected_length={len(expected)})"
        )
    return note


def _note_extent(adapter: Any, note: Any, *, label: str) -> tuple[float, ...]:
    """The rendered sheet-space box (x0, y0, x1, y1) of a free note."""
    adapter.currentModel.GraphicsRedraw2()
    extent = tuple(float(value) for value in (_early_bound(note, "INote").GetExtent() or ()))
    if len(extent) != 6 or extent[3] <= extent[0] or extent[4] <= extent[1]:
        raise RuntimeError(f"{label}: note has no rendered extent: {extent!r}")
    return (extent[0], extent[1], extent[3], extent[4])


def _anchor_note(
    adapter: Any, note: Any, corner: tuple[float, float], *, label: str
) -> tuple[float, ...]:
    """Steer a note's RENDERED top-left corner toward ``corner`` (summing r10/r11:
    the text box neither sits on nor tracks the insertion point 1:1)."""
    target_x, target_y = corner
    annotation = _early_bound(_early_bound(note, "INote").GetAnnotation(), "IAnnotation")
    if annotation is None:
        raise RuntimeError(f"{label}: note has no annotation to move")
    extent = _note_extent(adapter, note, label=label)
    moves = 0
    for _pass in range(NOTE_ANCHOR_PASSES):
        shift = (target_x - extent[0], target_y - extent[3])
        if max(abs(shift[0]), abs(shift[1])) <= NOTE_ANCHOR_SETTLE:
            break
        position = tuple(float(value) for value in (annotation.GetPosition() or ()))
        if len(position) != 3:
            raise RuntimeError(f"{label}: note position is unreadable: {position!r}")
        if not annotation.SetPosition(position[0] + shift[0], position[1] + shift[1], position[2]):
            raise RuntimeError(f"{label}: note SetPosition failed")
        extent = _note_extent(adapter, note, label=label)
        moves += 1
    _telemetry.event(
        "drawing.note_anchor",
        block=label,
        moves=moves,
        target_mm=(target_x * 1000.0, target_y * 1000.0),
        extent_mm=tuple(value * 1000.0 for value in extent),
    )
    return extent


def _stack_note_field(
    adapter: Any,
    blocks: tuple[tuple[str, str], ...],
    field: tuple[float, float, float, float],
    *,
    label: str,
) -> list[str]:
    """Stack note blocks top-down in one field; return every field violation."""
    left, top, _right, _bottom = field
    y = top
    findings = []
    for block_label, text in blocks:
        note = _add_note_block(adapter, text, (left, y), label=block_label)
        extent = _anchor_note(
            adapter, note, (left + NOTE_FIELD_INSET, y - NOTE_FIELD_INSET), label=block_label
        )
        violations = note_field_violations(extent, field)
        _telemetry.event(
            "drawing.note_field",
            field=label,
            block=block_label,
            extent_mm=tuple(value * 1000.0 for value in extent),
            violations=tuple(violations),
        )
        if violations:
            findings.append(f"{label}: {block_label} leaves its note field: " + "; ".join(violations))
        y = extent[1] - NOTE_BLOCK_GAP
    return findings


def _stack_sheet_note_fields(adapter: Any, facts: SourceFacts, sheet: int) -> list[str]:
    """Stack every ``package_note_fields`` field of one fixed-field sheet."""
    findings = []
    for field in package_note_fields(facts):
        if field.sheet == sheet:
            findings += _stack_note_field(
                adapter, field.blocks, field.bounds, label=field.label
            )
    return findings


def _view_outline(view: Any) -> tuple[float, float, float, float]:
    outline = tuple(float(value) for value in _early_bound(view, "IView").GetOutline())
    if len(outline) != 4 or outline[2] <= outline[0] or outline[3] <= outline[1]:
        raise RuntimeError(f"view has an invalid outline {outline!r}")
    return outline


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


def _shift_view(adapter: Any, view: Any, delta: tuple[float, float], *, label: str) -> None:
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


def _caption_under(adapter: Any, view: Any, text: str, *, label: str) -> None:
    """A caption centred under a view's outline."""
    outline = _view_outline(view)
    note = _add_note_block(adapter, text, (outline[0], outline[1]), label=label)
    extent = _note_extent(adapter, note, label=label)
    width = extent[2] - extent[0]
    _anchor_note(
        adapter,
        note,
        ((outline[0] + outline[2]) / 2.0 - width / 2.0, outline[1] - VIEW_CAPTION_GAP),
        label=label,
    )


# A balloon's ``GetPosition`` is an anchor, not its circle centre: integ3 (farm
# run 20260925T012343624Z, key d7ea6d8d9e79) read the centre behind every leader
# start at a constant (+4.0, -1.7) mm from it, sd 0.3 mm over 40 balloons. One
# balloon whose offset strays this far from its sheet's mean is logged loud.
BALLOON_ANCHOR_SCATTER_WARN_M = 0.001
# Leaders this close count as crossed in both uncross passes. The audit calls a
# crossing only past 0.1 mm, and integ1's 375/385 was 0.32 mm past, so sub-mm
# scatter between two reads must not decide whether a pair gets swapped.
UNCROSS_NEAR_MARGIN_M = 0.001
# A near (not crossed) pair is swapped only when that shortens the two leaders
# by more than this; the strict decrease is what bounds the swap count.
UNCROSS_MIN_GAIN_M = 1e-5


def _balloon_annotations(balloons: list[Any]) -> dict[str, Any]:
    """Each balloon's ``IAnnotation`` keyed by its note name (``DetailItemN``)."""
    annotations = {}
    for balloon in balloons:
        note = _early_bound(balloon, "INote")
        annotations[str(note.GetName() or "")] = _early_bound(
            note.GetAnnotation(), "IAnnotation"
        )
    return annotations


def _balloon_attachment(annotation: Any, name: str) -> tuple[float, float]:
    """The last point of a balloon's leader, sheet meters: where it lands."""
    points = tuple(float(value) for value in (annotation.GetLeaderPointsAtIndex(0) or ()))
    if len(points) < 6:
        raise RuntimeError(f"{name}: balloon leader is unreadable: {points!r}")
    return points[-3], points[-2]


def _placed_balloon_leaders(
    adapter: Any, annotations: dict[str, Any]
) -> dict[str, list[LeaderSegment]]:
    """Each balloon's leader through the layout audit's own reader."""
    leaders = {}
    for name, annotation in annotations.items():
        segments = _leader_segments_of(adapter, annotation, label=name, kind="note", owner="")
        if not segments:
            raise RuntimeError(f"{name}: balloon leader is unreadable")
        leaders[name] = segments
    return leaders


def _audit_leader_segments(adapter: Any, sheet_name: str) -> list[LeaderSegment]:
    """The layout audit's own leader read of one sheet, after activating it."""
    _activate_sheet(adapter, sheet_name)
    _elements, segments, _region = collect_layout_elements(
        adapter, layout=SHEET_LAYOUTS[sheet_name]
    )
    return segments


def _audit_balloon_leaders(
    segments: list[LeaderSegment], annotations: dict[str, Any]
) -> dict[str, list[LeaderSegment]]:
    """The balloons' leaders out of an audit read; its labels read ``DetailItemN '11'``."""
    leaders: dict[str, list[LeaderSegment]] = {}
    for segment in segments:
        name = segment.label.split(" ", 1)[0]
        if name in annotations:
            leaders.setdefault(name, []).append(
                LeaderSegment(
                    name, segment.kind, segment.x0, segment.y0, segment.x1, segment.y1
                )
            )
    return leaders


def _leader_ends(segments: list[LeaderSegment]) -> tuple[tuple[float, float], tuple[float, float]]:
    """``(start on the balloon rim, attachment)`` of one balloon's leader."""
    return (segments[0].x0, segments[0].y0), (segments[-1].x1, segments[-1].y1)


def _leader_centre(segments: list[LeaderSegment]) -> tuple[float, float]:
    """The balloon centre behind its leader: SolidWorks starts it on the rim, radially."""
    (sx, sy), (ax, ay) = _leader_ends(segments)
    reach = math.hypot(ax - sx, ay - sy)
    if reach == 0.0:
        return sx, sy
    radius = BALLOON_DIAMETER / 2.0
    return sx - (ax - sx) * radius / reach, sy - (ay - sy) * radius / reach


def _point_segment_gap(x: float, y: float, segment: LeaderSegment) -> float:
    dx, dy = segment.x1 - segment.x0, segment.y1 - segment.y0
    span = dx * dx + dy * dy
    t = 0.0 if span == 0.0 else ((x - segment.x0) * dx + (y - segment.y0) * dy) / span
    t = min(1.0, max(0.0, t))
    return math.hypot(x - segment.x0 - t * dx, y - segment.y0 - t * dy)


def _turn(ax: float, ay: float, bx: float, by: float, cx: float, cy: float) -> float:
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)


def _segment_gap(a: LeaderSegment, b: LeaderSegment) -> float:
    """Closest approach of two segments; 0 when they cross."""
    d1 = _turn(b.x0, b.y0, b.x1, b.y1, a.x0, a.y0)
    d2 = _turn(b.x0, b.y0, b.x1, b.y1, a.x1, a.y1)
    d3 = _turn(a.x0, a.y0, a.x1, a.y1, b.x0, b.y0)
    d4 = _turn(a.x0, a.y0, a.x1, a.y1, b.x1, b.y1)
    if d1 * d2 < 0.0 and d3 * d4 < 0.0:
        return 0.0
    return min(
        _point_segment_gap(a.x0, a.y0, b),
        _point_segment_gap(a.x1, a.y1, b),
        _point_segment_gap(b.x0, b.y0, a),
        _point_segment_gap(b.x1, b.y1, a),
    )


def _crossed_balloons(leaders: dict[str, list[LeaderSegment]]) -> list[tuple[str, str]]:
    """Balloon pairs the audit's own predicate calls crossed."""
    segments = [segment for run in leaders.values() for segment in run]
    return [(c.a.label, c.b.label) for c in find_leader_leader_crossings(segments)]


def _near_balloons(
    leaders: dict[str, list[LeaderSegment]],
) -> list[tuple[float, float, str, str]]:
    """``(gap, swap gain, a, b)`` for leaders within the near margin, closest first.

    Leaders sharing an attachment converge by design (the audit exempts them),
    so they are not near pairs. The gain is how much a slot swap would shorten
    the two centre-to-attachment runs.
    """
    near = []
    for first, second in combinations(sorted(leaders), 2):
        a_start, a_attach = _leader_ends(leaders[first])
        b_start, b_attach = _leader_ends(leaders[second])
        if math.dist(a_attach, b_attach) < UNCROSS_NEAR_MARGIN_M:
            continue
        gap = min(_segment_gap(a, b) for a in leaders[first] for b in leaders[second])
        if gap >= UNCROSS_NEAR_MARGIN_M:
            continue
        a_centre = _leader_centre(leaders[first])
        b_centre = _leader_centre(leaders[second])
        gain = (math.dist(a_centre, a_attach) + math.dist(b_centre, b_attach)) - (
            math.dist(b_centre, a_attach) + math.dist(a_centre, b_attach)
        )
        near.append((gap, gain, first, second))
    return sorted(near)


def _next_balloon_swap(
    leaders: dict[str, list[LeaderSegment]],
) -> tuple[str, str, str] | None:
    """``(a, b, reason)`` of the next slot swap, or None when the ring is settled.

    A crossed pair always goes: swapping two crossing straight leaders strictly
    shortens their summed length (triangle inequality). A near pair goes only
    when the swap shortens them by ``UNCROSS_MIN_GAIN_M``, so every swap lowers
    the ring's total leader length and the swaps cannot cycle.
    """
    crossed = _crossed_balloons(leaders)
    if crossed:
        return (*crossed[0], "crossing")
    for _gap, gain, first, second in _near_balloons(leaders):
        if gain > UNCROSS_MIN_GAIN_M:
            return first, second, "near"
    return None


def _swap_balloon_slots(adapter: Any, a: Any, b: Any, *, label: str, names: str) -> None:
    pa = tuple(float(value) for value in a.GetPosition())
    pb = tuple(float(value) for value in b.GetPosition())
    if not (a.SetPosition(*pb) and b.SetPosition(*pa)):
        raise RuntimeError(f"{label}: cannot swap balloons {names}")
    rebuild_drawing(adapter, label=f"{label} swap")


def _uncross_balloons(
    adapter: Any,
    annotations: dict[str, Any],
    read: Callable[[], dict[str, list[LeaderSegment]]],
    *,
    label: str,
) -> tuple[list[tuple[str, str, str]], dict[str, list[LeaderSegment]]]:
    """Swap slots until no pair is crossed or swappably near; the final read too."""
    swaps: list[tuple[str, str, str]] = []
    leaders = read()
    for _attempt in range(len(annotations) ** 2):
        swap = _next_balloon_swap(leaders)
        if swap is None:
            break
        first, second, reason = swap
        _swap_balloon_slots(
            adapter,
            annotations[first],
            annotations[second],
            label=label,
            names=f"{first} and {second}",
        )
        swaps.append(swap)
        leaders = read()
    return swaps, leaders


def _log_balloon_anchor_offsets(
    annotations: dict[str, Any], leaders: dict[str, list[LeaderSegment]], *, label: str
) -> None:
    """Record each balloon's centre-behind-its-leader minus its ``GetPosition``.

    The offset is expected constant across a sheet (integ3); one balloon off the
    sheet mean by over ``BALLOON_ANCHOR_SCATTER_WARN_M`` is a leader the audit
    and the ring disagree on, so it WARNs by name.
    """
    offsets = []
    for name, annotation in annotations.items():
        centre = _leader_centre(leaders[name])
        anchor = tuple(float(value) for value in annotation.GetPosition())[:2]
        offsets.append((name, centre[0] - anchor[0], centre[1] - anchor[1]))
    if not offsets:
        return
    mean_x = sum(row[1] for row in offsets) / len(offsets)
    mean_y = sum(row[2] for row in offsets) / len(offsets)
    rows = tuple(
        (
            name,
            round(dx * 1000.0, 2),
            round(dy * 1000.0, 2),
            round(math.hypot(dx - mean_x, dy - mean_y) * 1000.0, 2),
        )
        for name, dx, dy in offsets
    )
    sd = math.sqrt(sum((row[3] / 1000.0) ** 2 for row in rows) / len(rows))
    _telemetry.event(
        "drawing.balloon_anchor_offset",
        label=label,
        mean_dx_mm=round(mean_x * 1000.0, 2),
        mean_dy_mm=round(mean_y * 1000.0, 2),
        sd_mm=round(sd * 1000.0, 2),
        max_deviation_mm=max(row[3] for row in rows),
        offsets=rows,
    )
    stray = [row for row in rows if row[3] > BALLOON_ANCHOR_SCATTER_WARN_M * 1000.0]
    summary = (
        f"{label}: {len(rows)} balloon centre(s) sit ({mean_x * 1000.0:+.2f}, "
        f"{mean_y * 1000.0:+.2f}) mm off their anchors, sd {sd * 1000.0:.2f} mm"
    )
    if not stray:
        _telemetry.info(summary)
        return
    listed = ", ".join(f"{row[0]} {row[3]:.2f} mm" for row in stray)
    _telemetry.warn(f"{summary}; off the sheet mean: {listed}")


def _describe_near(near: list[tuple[float, float, str, str]]) -> str:
    return ", ".join(f"{a}/{b} {gap * 1000.0:.2f} mm" for gap, _gain, a, b in near)


def _uncross_balloon_leaders(adapter: Any, balloons: list[Any], *, label: str) -> None:
    """Swap the ring slots of any two balloons whose leaders cross or nearly do.

    Leaders are read exactly as the layout audit reads them
    (``_leader_segments_of``); ``_final_balloon_uncross`` stays the authority.
    """
    annotations = _balloon_annotations(balloons)
    swaps, leaders = _uncross_balloons(
        adapter,
        annotations,
        lambda: _placed_balloon_leaders(adapter, annotations),
        label=label,
    )
    _log_balloon_anchor_offsets(annotations, leaders, label=label)
    _telemetry.event("drawing.balloon_uncross", label=label, swaps=tuple(swaps))
    _telemetry.info(f"{label}: uncrossed balloon leaders with {len(swaps)} swap(s)")
    crossed = _crossed_balloons(leaders)
    if crossed:
        pairs = ", ".join(f"{a}/{b}" for a, b in crossed)
        _telemetry.warn(f"{label}: leaders still cross after {len(swaps)} swap(s): {pairs}")
    near = _near_balloons(leaders)
    if near:
        _telemetry.warn(f"{label}: leaders left within the near margin: {_describe_near(near)}")


def _final_balloon_uncross(
    adapter: Any,
    sheet_name: str,
    annotations: dict[str, Any],
    *,
    read_segments: Callable[[Any, str], list[LeaderSegment]] = _audit_leader_segments,
) -> None:
    """Uncross a sheet's balloons on the audit's geometry, just before the audit.

    One predicate, one reader: the audit's ``collect_layout_elements`` after
    ``_activate_sheet``, exactly as ``_check_package_layout`` will read it. A
    crossing the placement-time pass could not see (a view regenerated since,
    sub-mm scatter between reads) is swapped here; one that survives the
    quadratic cap raises by name. A near pair the swap would not shorten is
    only warned: the audit does not call it. Crossings with non-balloon leaders
    are the audit's to report.
    """
    swaps, leaders = _uncross_balloons(
        adapter,
        annotations,
        lambda: _audit_balloon_leaders(read_segments(adapter, sheet_name), annotations),
        label=sheet_name,
    )
    _telemetry.event("drawing.balloon_final_uncross", sheet=sheet_name, swaps=tuple(swaps))
    _telemetry.info(f"{sheet_name}: final uncross on audit geometry, {len(swaps)} swap(s)")
    near = _near_balloons(leaders)
    if near:
        _telemetry.warn(
            f"{sheet_name}: balloon leaders left within the near margin: {_describe_near(near)}"
        )
    crossed = _crossed_balloons(leaders)
    if crossed:
        listed = ", ".join(f"{a}/{b}" for a, b in crossed)
        raise RuntimeError(
            f"{sheet_name}: balloon leaders still cross after {len(swaps)} swap(s): {listed}"
        )


def _component_stem(component: Any) -> str:
    component = _early_bound(component, "IComponent2")
    path = str(component.GetPathName() or "")
    if not path:
        raise RuntimeError(f"component {component.Name2!r} has no referenced path")
    return Path(path).stem.casefold()


def _component_name(component: Any) -> str:
    return str(_early_bound(component, "IComponent2").Name2 or "").rsplit("/", 1)[-1]


def _verify_balloon_attachments(
    balloons: Sequence[Any], items: Sequence[tuple[str, str]], *, label: str
) -> None:
    """Prove each balloon's leader lands on the component its item names."""
    records = []
    evidence = []
    for balloon in balloons:
        note = _early_bound(balloon, "INote")
        name = str(note.GetName() or "")
        item = str(note.GetBomBalloonText(True) or "").strip()
        annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
        entities = tuple(annotation.GetAttachedEntities3() or ())
        types = tuple(int(value) for value in (annotation.GetAttachedEntityTypes() or ()))
        stems = []
        components = []
        for entity, kind in zip(entities, types):
            if kind == 0 or entity is None:  # swSelNOTHING
                continue
            component = _early_bound(entity, "IEntity").GetComponent()
            if component is None:
                continue
            components.append(_component_name(component))
            stems.append(_component_stem(component))
        attach = _balloon_attachment(annotation, name)
        records.append((name, item, tuple(sorted(set(stems)))))
        evidence.append(
            {
                "balloon": name,
                "item": item,
                "components": tuple(components),
                "attach_mm": (attach[0] * 1000.0, attach[1] * 1000.0),
            }
        )
    violations = balloon_attachment_violations(records, dict(items))
    _telemetry.event(
        "drawing.balloon_attachment",
        label=label,
        balloons=repr(evidence),
        violations=tuple(violations),
    )
    if violations:
        raise RuntimeError(f"{label}: balloon attachment mismatch: " + "; ".join(violations))


def _configure_view(
    adapter: Any,
    view: Any,
    *,
    exploded: bool,
    role: ViewRole = ViewRole.PLAIN,
    label: str,
) -> str:
    """Point a view at its policy configuration, then explode or collapse it
    there: each configuration owns its own explode (``_drive_train_explode``).
    Both are read back; returns the configuration."""
    configuration = apply_view_configuration(adapter, view, role=role, label=label)
    set_view_exploded_state(adapter, view, exploded, configuration=configuration, label=label)
    return configuration


@_telemetry.traced("drawing.isolate_instances", label_param="label")
def _isolate_instances(adapter: Any, view: Any, names: frozenset[str], *, label: str) -> None:
    """Show exactly the named top-level instances in one drawing view.

    The shared ``isolate_drawing_view_components`` works per FAMILY; this
    isolates per instance and reads the visibility back.
    """
    view = _early_bound(view, "IView")
    root = view.RootDrawingComponent2(False)
    if root is None:
        raise RuntimeError(f"{label}: drawing view has no root component")
    root = _early_bound(root, "IDrawingComponent")
    shown: set[str] = set()
    seen: list[str] = []
    hidden = 0
    for raw in tuple(root.GetChildren() or ()):
        drawing_component = _early_bound(raw, "IDrawingComponent")
        raw_name = str(drawing_component.Name or "")
        seen.append(raw_name)
        name = raw_name.split("@", 1)[0].replace("\\", "/").rsplit("/", 1)[-1]
        visible = name in names
        drawing_component.Visible = visible
        if visible:
            shown.add(name)
        else:
            hidden += 1
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError(f"{label}: rebuild after isolation failed")
    missing = sorted(names - shown)
    _telemetry.event(
        "drawing.isolate_instances",
        label=label,
        shown=len(shown),
        hidden=hidden,
        missing=tuple(missing),
        outline_mm=tuple(value * 1000.0 for value in _view_outline(view)),
    )
    if missing:
        raise RuntimeError(
            f"{label}: instances not in the view: {missing!r}; "
            f"drawing components seen (first 12): {seen[:12]!r}"
        )


def _check_package_layout(adapter: Any, field_findings: list[str]) -> None:
    """Audit every sheet; fail on any finding, including note-field findings."""
    failures = list(field_findings)
    for number, sheet_name in enumerate(SHEET_NAMES, start=1):
        _activate_sheet(adapter, sheet_name)
        try:
            check_drawing_layout(
                adapter, layout=SHEET_LAYOUTS[sheet_name], stem=f"{ARTIFACT_STEM} sheet {number}"
            )
        except RuntimeError as exc:
            failures.append(f"sheet {number} {sheet_name}: {exc}")
    if failures:
        raise RuntimeError("drive-train package layout audit failed:\n" + "\n".join(failures))


def _export_failure_pdf(adapter: Any, stage: str) -> None:
    """Export the failing package under the forensic tree the farm uploads."""
    try:
        model = adapter.currentModel
        is_drawing = model is not None and int(_early_bound(model, "IModelDoc2").GetType()) == 3
    except Exception as exc:  # noqa: BLE001 - evidence must not mask the failure
        _telemetry.warn(f"{stage}-failure PDF skipped: active model unreadable: {exc!r}")
        return
    if not is_drawing:
        _telemetry.warn(f"{stage}-failure PDF skipped: no active drawing")
        return
    path = (
        _seat_forensics.OUT_FAILURES
        / f"drive-train-package-{stage}"
        / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        / f"{ARTIFACT_STEM}.pdf"
    )
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        _early_bound(adapter.currentModel, "IModelDoc2").SaveAs3(str(path), 0, 0)
    except Exception as exc:  # noqa: BLE001 - evidence must not mask the failure
        _telemetry.warn(f"{stage}-failure PDF export failed: {exc!r}")
        return
    if not path.is_file():
        _telemetry.warn(f"{stage}-failure PDF export produced no file: {path}")
        return
    _telemetry.event("drawing.failure_pdf", stage=stage, path=str(path))
    _telemetry.info(f"{stage}-failure evidence PDF: {path}")


# ============================ source validation ==================================


class SourceFacts:
    """What the package reads from the opened drive-train model."""

    def __init__(self, instances: list[Instance], configurations: dict[str, str]):
        self.instances = instances
        self.configurations = configurations
        self.counts = instance_counts(instances)
        self.components = bom_components(self.counts)
        self.clusters = cluster_members(instances)
        self.reference_names = {
            f"@{instance.role}": instance.name
            for instance in instances
            if f"@{instance.role}" in COMPONENT_IDENTITIES
        }

    def cone_rows(self) -> list[tuple[int, str]]:
        return cone_station_rows(
            [
                (instance.origin_mm[2], self.configurations[instance.name])
                for instance in self.instances
                if instance.stem == "dt-cone-gear"
            ]
        )

    def count(self, stem: str) -> int:
        return self.counts.get(stem, 0)

    def role_count(self, selector: str) -> int:
        return sum(instance_selector(instance) == selector for instance in self.instances)


def _validate_source(source_model: Any) -> SourceFacts:
    """Consume the builder-owned presentation without changing the assembly."""
    assembly = _early_bound(source_model, "IAssemblyDoc")
    manager = _early_bound(source_model.ConfigurationManager, "IConfigurationManager")
    configuration = _early_bound(manager.ActiveConfiguration, "IConfiguration")
    if str(configuration.Name) != SOURCE_CONFIGURATION:
        raise RuntimeError(f"drive-train source must open in {SOURCE_CONFIGURATION!r}")
    # Each drawing configuration owns its explode; a view shows the one of the
    # configuration it references.
    for owner, wanted in (
        (SOURCE_CONFIGURATION, EXPLODED_VIEW_NAME),
        (SIMPLIFIED_VIEW_CONFIGURATION, simplified_name(EXPLODED_VIEW_NAME)),
    ):
        names = tuple(assembly.GetExplodedViewNames2(owner) or ())
        if names != (wanted,):
            raise RuntimeError(
                f"drive-train source {owner} exploded views {names!r} != {(wanted,)!r}"
            )
    instances = []
    configurations = {}
    numbers: dict[str, set[str]] = {}
    reference_names = component_reference_names(source_model, COMPONENT_IDENTITIES)
    roles = {name: selector[1:] for selector, name in reference_names.items()}
    for raw_component in tuple(assembly.GetComponents(True) or ()):
        component = _early_bound(raw_component, "IComponent2")
        name = _component_name(component)
        stem = _component_stem(component)
        total = _early_bound(component.GetTotalTransform(True), "IMathTransform").ArrayData
        base = _early_bound(component.GetTotalTransform(False), "IMathTransform").ArrayData
        if any(abs(float(a) - float(b)) > 1e-9 for a, b in zip(total, base, strict=True)):
            raise RuntimeError(f"drive-train source must open collapsed: {name!r} is displaced")
        origin = tuple(float(value) * 1000.0 for value in tuple(base)[9:12])
        instances.append(Instance(name=name, stem=stem, origin_mm=origin, role=roles.get(name)))
        configurations[name] = str(component.ReferencedConfiguration or "")
        # A lightweight component has no loaded model; its Number is then
        # unreadable here (the offline registry test still pins it).
        model = component.GetModelDoc2()
        if model is not None:
            number = str(
                _early_bound(model, "IModelDoc2").GetCustomInfoValue("", "Number") or ""
            )
            numbers.setdefault(stem, set()).add(number)
    facts = SourceFacts(instances, configurations)
    findings = source_violations(facts.counts)
    for stem, seen in sorted(numbers.items()):
        want = BOM_PART_NUMBERS.get(stem)
        if want is not None and seen != {want}:
            findings.append(f"{stem} model Number {sorted(seen)!r} != released {want!r}")
    unread = sorted(set(facts.counts) - set(numbers))
    if unread:
        _telemetry.warn(f"drive-train source: Number unreadable (not loaded) for {unread!r}")
    _telemetry.event(
        "drawing.drive_train_source",
        counts=repr(facts.counts),
        numbers_read=tuple(sorted(numbers)),
        numbers_unread=tuple(unread),
        pending_present=tuple(sorted(PENDING_STEMS & set(facts.counts))),
        findings=tuple(findings),
    )
    if findings:
        raise RuntimeError("drive-train source refused: " + "; ".join(findings))
    return facts


# ============================ BOM ==============================================


def _validate_bom(
    adapter: Any, table: Any, facts: SourceFacts
) -> tuple[tuple[tuple[str, str], ...], int]:
    """Rewrite part numbers, prove identities/quantities; return (stem, item) and part column."""
    table = _early_bound(table, "ITableAnnotation")
    rows = int(table.RowCount)
    columns = int(table.ColumnCount)
    components = facts.components
    if rows != len(components) + 1 or columns < 4:
        raise RuntimeError(
            f"drive-train BOM is {rows}x{columns}; expected {len(components) + 1} rows"
        )
    contents = tuple(
        tuple(str(table.DisplayedText(row, column) or "").strip() for column in range(columns))
        for row in range(rows)
    )
    header = tuple(cell.upper() for cell in contents[0])

    def column_named(predicate: Callable[[str], bool], label: str) -> int:
        matches = [index for index, cell in enumerate(header) if predicate(cell)]
        if len(matches) != 1:
            raise RuntimeError(f"drive-train BOM has no unique {label} column: {header!r}")
        return matches[0]

    item_column = column_named(lambda cell: cell.startswith("ITEM NO"), "ITEM NO.")
    part_column = column_named(lambda cell: cell == "PART NUMBER", "PART NUMBER")
    description_column = column_named(lambda cell: cell == "DESCRIPTION", "DESCRIPTION")
    quantity_column = column_named(lambda cell: cell.startswith("QTY"), "QTY.")
    for column, width in (
        (item_column, BOM_COLUMN_WIDTHS["item"]),
        (part_column, BOM_COLUMN_WIDTHS["part"]),
        (description_column, BOM_COLUMN_WIDTHS["description"]),
        (quantity_column, BOM_COLUMN_WIDTHS["quantity"]),
    ):
        actual_width = float(table.SetColumnWidth(column, width, 0))
        if abs(actual_width - width) > 1e-6:
            raise RuntimeError(
                f"drive-train BOM column {column} width did not persist: "
                f"{actual_width * 1000:.3f} mm"
            )

    actual: dict[str, tuple[int, str, str, str]] = {}
    for row_index, row in enumerate(contents[1:], start=1):
        text = row[part_column].strip().casefold()
        stem = BOM_NORMALIZED_ALIASES.get(text, text)
        if stem in actual:
            raise RuntimeError(f"drive-train BOM repeats component family {stem!r}")
        actual[stem] = (row_index, row[item_column], row[description_column], row[quantity_column])
    if set(actual) != set(components):
        raise RuntimeError(
            f"drive-train BOM identities {sorted(actual)!r} != {sorted(components)!r}"
        )
    items = {values[1] for values in actual.values()}
    if items != {str(item) for item in range(1, len(components) + 1)}:
        raise RuntimeError(f"drive-train BOM item numbers {sorted(items)!r} are not contiguous")
    for stem, (row_index, _item, description, quantity) in actual.items():
        number = BOM_PART_NUMBERS[stem]
        if contents[row_index][part_column] != number:
            if not table.IsCellTextEditable(row_index, part_column):
                raise RuntimeError(f"drive-train BOM part-number cell for {stem!r} is not editable")
            table.SetText2(row_index, part_column, False, number)
            if str(table.DisplayedText2(row_index, part_column, False) or "").strip() != number:
                raise RuntimeError(f"drive-train BOM part number for {stem!r} did not persist")
        if description != BOM_DESCRIPTIONS[stem]:
            raise RuntimeError(f"drive-train BOM description mismatch for {stem!r}: {description!r}")
        if quantity != str(facts.count(stem)):
            raise RuntimeError(
                f"drive-train BOM quantity for {stem!r} is {quantity!r}, "
                f"model has {facts.count(stem)}"
            )
    header_count = int(table.GetHeaderCount())
    setter_heights = tuple(float(table.SetRowHeight(row, BOM_ROW_HEIGHT, 0)) for row in range(rows))
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError("drive-train BOM rebuild failed")
    for row, setter_height in enumerate(setter_heights):
        height = float(table.GetRowHeight(row))
        fit = bom_row_fit(BOM_ROW_HEIGHT, height)
        _telemetry.event(
            "drawing.bom_row_height",
            row=row,
            row_kind="header" if row < header_count else "data",
            fit=fit,
            setter_mm=setter_height * 1000.0,
            actual_mm=height * 1000.0,
            cells=contents[row],
        )
        if fit == "short":
            raise RuntimeError(f"drive-train BOM row {row} is {height * 1000:.3f} mm, below request")
        if fit == "grown" and row >= header_count:
            _telemetry.warn(f"drive-train BOM data row {row} grew to {height * 1000:.3f} mm")
    for stem, (row_index, *_rest) in actual.items():
        if str(table.DisplayedText(row_index, part_column) or "").strip() != BOM_PART_NUMBERS[stem]:
            raise RuntimeError(f"drive-train BOM part number for {stem!r} reverted")
    return tuple((stem, actual[stem][1]) for stem in components), header_count


def _bom_feature_name(table: Any) -> str:
    bom = _early_bound(table, "IBomTableAnnotation")
    feature = _early_bound(bom.BomFeature, "IBomFeature")
    name = str(feature.Name or "")
    if not name:
        raise RuntimeError("drive-train BOM feature has no name")
    return name


def _split_bom(adapter: Any, table: Any, *, data_rows: int, header_count: int) -> None:
    """Split the BOM into two side-by-side columns and hold both to the sheet."""
    table = _early_bound(table, "ITableAnnotation")
    first_rows = bom_split_row(data_rows)
    split_after = header_count + first_rows - 1  # 0-based row index
    second = table.Split(2, split_after)  # swTableSplit_AfterRow
    if second is None:
        raise RuntimeError(f"drive-train BOM split after row {split_after} failed")
    second = _early_bound(second, "ITableAnnotation")
    annotation = _early_bound(second.GetAnnotation(), "IAnnotation")
    if not annotation.SetPosition(BOM_SECOND_COLUMN_X, BOM_ANCHOR[1], 0.0):
        raise RuntimeError("drive-train BOM second column refused its position")
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError("drive-train BOM split rebuild failed")
    findings = []
    for label, piece in (("first", table), ("second", second)):
        piece_annotation = _early_bound(piece.GetAnnotation(), "IAnnotation")
        position = tuple(float(value) for value in piece_annotation.GetPosition())
        # Row indexes stay those of the original table (ITableAnnotation::Split
        # remarks), so a piece's rows come from its split range, not RowCount.
        # The early-bound wrapper types the four outs as in/out VT_I4 BYREF, so
        # they must be passed; a bare call raises 'Type mismatch' (leaf
        # 20260923T044055Z-1-20b23f24). Same form as the layout audit's read.
        info = tuple(piece.GetSplitInformation(0, 0, 0, 0))
        if len(info) != 5:
            raise RuntimeError(f"{label} BOM column split information unreadable: {info!r}")
        _direction, _index, _count, start, end = (int(value) for value in info)
        piece_rows = sorted({*range(header_count), *range(start, end + 1)})
        rows = len(piece_rows)
        height = sum(float(piece.GetRowHeight(row)) for row in piece_rows)
        width = sum(float(piece.GetColumnWidth(column)) for column in range(int(piece.ColumnCount)))
        violations = bom_extent_violations((position[0], position[1]), width, height)
        _telemetry.event(
            "drawing.bom_piece",
            piece=label,
            anchor_mm=(position[0] * 1000.0, position[1] * 1000.0),
            rows=rows,
            split_range=(start, end),
            width_mm=width * 1000.0,
            height_mm=height * 1000.0,
            violations=tuple(violations),
        )
        findings.extend(f"{label} BOM column: {violation}" for violation in violations)
    if findings:
        raise RuntimeError("drive-train BOM split: " + "; ".join(findings))


def _link_view_to_bom(view: Any, bom_name: str, *, label: str) -> None:
    view = _early_bound(view, "IView")
    if not view.SetKeepLinkedToBOM(True, bom_name):
        raise RuntimeError(f"{label}: SetKeepLinkedToBOM({bom_name!r}) returned false")
    if not bool(view.GetKeepLinkedToBOM()) or str(view.GetKeepLinkedToBOMName() or "") != bom_name:
        raise RuntimeError(f"{label}: view is not linked to BOM {bom_name!r}")


# ============================ sheets ============================================


def _hide_model_reference_types(adapter: Any) -> None:
    """View > Hide/Show > Hide All Types on the drawing.

    Baseline-5 printed the source's PatternAxisX/Y/Z (the explode directions)
    and MHA-DT-07's OutsideDiaReference sketch (its 65.15 mm construction tip
    circle, kept for the part print's OD dimension) in every view: about ten
    centerline-font paths per sheet that the old MHA-DT-00 print did not carry.
    """
    extension = _early_bound(adapter.currentModel.Extension, "IModelDocExtension")
    if not extension.SetUserPreferenceToggle(VIEW_DISPLAY_HIDE_ALL_TYPES, 0, True):
        raise RuntimeError("drive-train drawing refused Hide All Types")
    if not extension.GetUserPreferenceToggle(VIEW_DISPLAY_HIDE_ALL_TYPES, 0):
        raise RuntimeError("drive-train drawing Hide All Types did not persist")


def _create_package_sheets(adapter: Any) -> None:
    new_project_drawing(adapter, layout=SPEC.layout, scale=ASSEMBLED_SCALE)
    _hide_model_reference_types(adapter)
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="drive-train assembly package")
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    for sheet_name in SHEET_NAMES:
        _activate_sheet(adapter, sheet_name)
        sheet = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
        scale = SHEET_SCALES[sheet_name]
        if not sheet.SetScale(float(scale[0]), float(scale[1]), False, False):
            raise RuntimeError(f"failed to set drive-train sheet scale: {sheet_name}")


def _heading(
    adapter: Any, sheet_number: int, text: str = "", *, xy: tuple[float, float] = HEADING_XY
) -> Any:
    return _add_note_block(
        adapter,
        heading_text(sheet_number, text),
        xy,
        label=f"sheet {sheet_number} heading",
    )


def _reference_iso(
    adapter: Any,
    *,
    caption: str,
    label: str,
    center: tuple[float, float] = REFERENCE_ISO_CENTER,
) -> Any:
    """A small collapsed isometric: every sheet needs a view for its title block."""
    view = place_view(adapter, str(SOURCE), "*Isometric", *center, scale=REFERENCE_ISO_SCALE)
    set_hidden_lines_removed(adapter, view)
    set_high_quality_shaded_with_edges(adapter, view, label=label)
    _configure_view(adapter, view, exploded=False, label=label)
    _caption_under(adapter, view, caption, label=f"{label} caption")
    return view


def _place_assembled_sheet(adapter: Any, facts: SourceFacts) -> list[str]:
    _activate_sheet(adapter, SHEET_NAMES[0])
    front = place_view(adapter, str(SOURCE), "*Front", 0.080, 0.110, scale=ASSEMBLED_SCALE)
    top = place_view(adapter, str(SOURCE), "*Top", 0.080, 0.200, scale=ASSEMBLED_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", 0.200, 0.110, scale=ASSEMBLED_SCALE)
    iso = place_view(
        adapter, str(SOURCE), "*Isometric", *ASSEMBLED_ISO_CENTER, scale=ASSEMBLED_ISO_SCALE
    )
    for view in (front, top, right, iso):
        set_hidden_lines_removed(adapter, view)
    set_high_quality_shaded_with_edges(adapter, iso, label="drive-train assembled isometric")
    # Every 1:3 view prints the teeth/thread-free configuration; the last
    # sheet carries the full-detail view.
    for label, view in (("front", front), ("top", top), ("right", right), ("isometric", iso)):
        _configure_view(adapter, view, exploded=False, label=f"assembled {label}")

    # ASME alignment on the model origin: top shares front's x, right shares y.
    origin = (0.0, 0.0, 0.0)
    front_origin = model_point_in_view(adapter, front, origin, label="front origin")
    top_origin = model_point_in_view(adapter, top, origin, label="top origin")
    right_origin = model_point_in_view(adapter, right, origin, label="right origin")
    _shift_view(adapter, top, (front_origin[0] - top_origin[0], 0.0), label="top alignment")
    _shift_view(adapter, right, (0.0, front_origin[1] - right_origin[1]), label="right alignment")
    front_box, top_box, right_box = (_view_outline(v) for v in (front, top, right))
    _shift_view(adapter, top, (0.0, front_box[3] + PROJECTED_GAP - top_box[1]), label="top gap")
    _shift_view(
        adapter, right, (front_box[2] + PROJECTED_GAP - right_box[0], 0.0), label="right gap"
    )
    boxes = [_view_outline(v) for v in (front, top, right)]
    group = (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )
    delta = (PROJECTED_GROUP_ORIGIN[0] - group[0], PROJECTED_GROUP_ORIGIN[1] - group[1])
    for label, view in (("front", front), ("top", top), ("right", right)):
        _shift_view(adapter, view, delta, label=f"projected group {label}")
    group = (group[0] + delta[0], group[1] + delta[1], group[2] + delta[0], group[3] + delta[1])
    findings = [
        f"sheet 1 projected group {edge}"
        for edge, bad in (
            ("passes the right of its region", group[2] > PROJECTED_REGION[2]),
            ("passes the top of its region", group[3] > PROJECTED_REGION[3]),
        )
        if bad
    ]
    _telemetry.event(
        "drawing.projected_group",
        group_mm=tuple(value * 1000.0 for value in group),
        findings=tuple(findings),
    )
    heading = _heading(adapter, 1, ASSEMBLED_HEADING, xy=ASSEMBLED_HEADING_XY)
    # The general notes fill the slot between the measured heading and the
    # measured isometric: an isometric grown upward fails the gate, not overlaps.
    (notes,) = (field for field in package_note_fields(facts) if field.sheet == 1)
    heading_box = _note_extent(adapter, heading, label="sheet 1 heading")
    iso_box = _view_outline(iso)
    bounds = general_notes_field(heading_box[1], iso_box[3])
    _telemetry.event(
        "drawing.general_notes_field",
        heading_mm=tuple(value * 1000.0 for value in heading_box),
        iso_mm=tuple(value * 1000.0 for value in iso_box),
        field_mm=tuple(value * 1000.0 for value in bounds),
    )
    findings += _stack_note_field(adapter, notes.blocks, bounds, label=notes.label)
    scale = f"{int(ASSEMBLED_SCALE[0])}:{int(ASSEMBLED_SCALE[1])}"
    _caption_under(adapter, front, f"FRONT {scale}", label="front caption")
    _caption_under(adapter, top, f"TOP {scale}", label="top caption")
    _caption_under(adapter, right, f"RIGHT {scale}", label="right caption")
    _caption_under(
        adapter,
        iso,
        f"ISOMETRIC {int(ASSEMBLED_ISO_SCALE[0])}:{int(ASSEMBLED_ISO_SCALE[1])}",
        label="isometric caption",
    )
    return findings


def _place_bom_view(adapter: Any) -> Any:
    """The BOM sheet's reference view, on its policy configuration: the BOM's
    rows read this view's configuration (``_insert_bom``)."""
    _activate_sheet(adapter, SHEET_NAMES[1])
    view = place_view(
        adapter, str(SOURCE), "*Isometric", *BOM_REFERENCE_ISO_CENTER, scale=REFERENCE_ISO_SCALE
    )
    set_hidden_lines_removed(adapter, view)
    set_high_quality_shaded_with_edges(adapter, view, label="BOM reference isometric")
    _configure_view(adapter, view, exploded=False, label="BOM reference isometric")
    violations = bom_reference_iso_violations(_view_outline(view))
    if violations:
        raise RuntimeError("BOM reference isometric: " + "; ".join(violations))
    return view


def _insert_bom(adapter: Any, view: Any, facts: SourceFacts) -> tuple[str, dict[str, str]]:
    _activate_sheet(adapter, SHEET_NAMES[1])
    table = insert_bom_table(
        adapter,
        view,
        anchor_xy=BOM_ANCHOR,
        expected_components=facts.components,
        descriptions={stem: BOM_DESCRIPTIONS[stem] for stem in facts.components},
        identity_aliases={BOM_PART_NUMBERS[stem]: stem for stem in facts.components},
        configuration_grouping="same-part",
        label="drive-train",
    )
    items, header_count = _validate_bom(adapter, table, facts)
    bom_name = _bom_feature_name(table)
    _split_bom(adapter, table, data_rows=len(facts.components), header_count=header_count)
    _heading(adapter, 2)
    findings = _stack_note_field(
        adapter,
        (("BOM reference and station pointer", BOM_REFERENCE_NOTES),),
        BOM_REFERENCE_NOTE_FIELD,
        label="BOM reference notes",
    )
    if findings:
        raise RuntimeError("drive-train BOM reference notes: " + "; ".join(findings))
    return bom_name, dict(items)


def _place_cluster_view(adapter: Any, cluster: Cluster) -> Any:
    """Place one cluster's view at its preferred scale and point it, still
    collapsed, at its policy configuration (see ``_place_package``)."""
    _activate_sheet(adapter, SHEET_NAMES[CLUSTER_SHEETS[cluster] - 1])
    label = f"{cluster} exploded isometric"
    view = place_view(
        adapter, str(SOURCE), "*Isometric", *CLUSTER_VIEW_CENTER, scale=CLUSTER_SCALES[cluster]
    )
    set_hidden_lines_removed(adapter, view)
    set_high_quality_shaded_with_edges(adapter, view, label=label)
    _configure_view(adapter, view, exploded=False, label=label)
    return view


def _fit_cluster_view(
    adapter: Any, cluster: Cluster, view: Any, facts: SourceFacts
) -> tuple[float, float]:
    """Explode, isolate and ring-fit one cluster's view
    (``_place_cluster_view``), before the BOM table exists (``_place_package``);
    return the scale it fitted at."""
    _activate_sheet(adapter, SHEET_NAMES[CLUSTER_SHEETS[cluster] - 1])
    label = f"{cluster} exploded isometric"
    preferred = CLUSTER_SCALES[cluster]
    # Its configuration is already set; now its own explode and isolation, so
    # the ring fits, and later every balloon attaches to, the geometry the
    # sheet prints.
    configuration = _configure_view(adapter, view, exploded=True, label=label)
    _isolate_instances(adapter, view, frozenset(facts.clusters[cluster]), label=label)
    preferred_outline = _view_outline(view)
    scale = cluster_ring_scale(preferred_outline, preferred, label=label)
    outline = preferred_outline
    # The ladder predicts each fit from the preferred outline; the re-read
    # outline is the proof, before any balloon exists. A shaded pictorial's
    # outline does not scale exactly (r4, 20261018T074844468Z: the cone set,
    # predicted to fit at 1:3, read 176.6 mm against 176.0), so a refused
    # proof steps on down the ladder and proves again.
    for scale in CLUSTER_SCALE_LADDER[CLUSTER_SCALE_LADDER.index(scale) :]:
        if scale != preferred:
            # Every configuration switch comes before every explode and the
            # BOM (``_place_package``): a step across 1:2 is refused, not
            # switched. The pictorial view is judged shaded-with-edges, as
            # apply_view_configuration judges it.
            if view_configuration(scale, _SW_SHADED_EDGES) != configuration:
                raise RuntimeError(
                    f"{label}: {_scale_text(scale)} would move the exploded view off "
                    f"{configuration!r}; a configuration switch here dirties the source"
                )
            _set_view_scale(adapter, view, scale, label=label)
            outline = _view_outline(view)
        shift, overflows, slide = cluster_ring_fit(outline)
        if not overflows:
            break
    _telemetry.event(
        "drawing.cluster_ring_fit",
        cluster=cluster,
        preferred_scale=_scale_text(preferred),
        scale=_scale_text(scale),
        preferred_outline_mm=tuple(value * 1000.0 for value in preferred_outline),
        outline_mm=tuple(value * 1000.0 for value in outline),
        shift_mm=tuple(value * 1000.0 for value in shift),
        title_block_slide_mm=slide * 1000.0,
        overflows=tuple(overflows),
    )
    if overflows:
        raise RuntimeError(
            f"{label}: at {_scale_text(scale)} the balloon ring still overflows "
            f"the cluster region ({'; '.join(overflows)})"
        )
    if scale != preferred:
        _telemetry.info(
            f"{label}: balloon ring fits at {_scale_text(scale)}, "
            f"not the preferred {_scale_text(preferred)}"
        )
    _shift_view(adapter, view, shift, label=f"{label} ring fit")
    return scale


def _balloon_cluster_sheet(
    adapter: Any,
    cluster: Cluster,
    view: Any,
    facts: SourceFacts,
    scale: tuple[float, float],
    *,
    bom_name: str,
    items: dict[str, str],
) -> tuple[dict[str, Any], list[BalloonLanding]]:
    """Link one fitted cluster view (``_fit_cluster_view``) to the BOM and
    balloon it; return its balloons by note name, and their landings for
    ``finalize_drawing`` to prove again after the last rebuild."""
    number = CLUSTER_SHEETS[cluster]
    _activate_sheet(adapter, SHEET_NAMES[number - 1])
    label = f"{cluster} exploded isometric"
    names = frozenset(facts.clusters[cluster])
    _link_view_to_bom(view, bom_name, label=label)
    stems = sorted(
        {instance.stem for instance in facts.instances if instance.name in names},
        key=lambda stem: int(items[stem]),
    )
    balloon_items = tuple((stem, items[stem]) for stem in stems)
    landings = add_component_bom_balloons(
        adapter,
        view,
        items=balloon_items,
        anchors={
            stem: replace(anchor, instance=facts.reference_names[anchor.instance])
            if anchor.instance in COMPONENT_IDENTITIES
            else anchor
            for stem, anchor in DRIVE_TRAIN_BALLOON_ANCHORS[cluster].items()
        },
        label=f"drive-train {cluster} BOM coverage",
        margin=CLUSTER_BALLOON_MARGIN,
    )
    balloons = [landing.note for landing in landings]
    # One ring over every balloon at this sheet's clearance; the shared call
    # above ringed them at the default.
    _spread_balloons(
        adapter,
        view,
        balloons,
        margin=CLUSTER_BALLOON_MARGIN,
        clearance=CLUSTER_BALLOON_CLEARANCE[cluster],
    )
    rebuild_drawing(adapter, label=f"{label} ring")
    _uncross_balloon_leaders(adapter, balloons, label=label)
    _verify_balloon_attachments(balloons, balloon_items, label=label)
    _heading(
        adapter,
        number,
        f"{CLUSTER_TITLES[cluster]} - EXPLODED ISOMETRIC "
        f"{_scale_text(scale)}; ITEMS PER SHEET 2",
    )
    return _balloon_annotations(balloons), landings


def _place_sequence_sheet(adapter: Any, facts: SourceFacts) -> list[str]:
    _activate_sheet(adapter, SHEET_NAMES[SEQUENCE_SHEET - 1])
    _heading(adapter, SEQUENCE_SHEET)
    _reference_iso(
        adapter, caption="FINISHED ASSEMBLY 1:8", label="sequence reference isometric"
    )
    return _stack_sheet_note_fields(adapter, facts, SEQUENCE_SHEET)


def _place_crank_sheet(adapter: Any, facts: SourceFacts) -> list[str]:
    _activate_sheet(adapter, SHEET_NAMES[CRANK_SHEET - 1])
    _heading(adapter, CRANK_SHEET)
    _reference_iso(adapter, caption="FINISHED ASSEMBLY 1:8", label="crank reference isometric")
    return _stack_sheet_note_fields(adapter, facts, CRANK_SHEET)


def _place_bank_sheet(adapter: Any, facts: SourceFacts) -> list[str]:
    _activate_sheet(adapter, SHEET_NAMES[BANK_SHEET - 1])
    _heading(adapter, BANK_SHEET)
    _reference_iso(adapter, caption="FINISHED ASSEMBLY 1:8", label="bank reference isometric")
    return _stack_sheet_note_fields(adapter, facts, BANK_SHEET)


def _place_fit_sheet(adapter: Any, facts: SourceFacts) -> list[str]:
    _activate_sheet(adapter, SHEET_NAMES[FIT_SHEET - 1])
    _heading(adapter, FIT_SHEET)
    _reference_iso(adapter, caption="FINISHED ASSEMBLY 1:8", label="fit reference isometric")
    return _stack_sheet_note_fields(adapter, facts, FIT_SHEET)


def _place_checks_sheet(adapter: Any, facts: SourceFacts) -> list[str]:
    _activate_sheet(adapter, SHEET_NAMES[CHECKS_SHEET - 1])
    _heading(adapter, CHECKS_SHEET)
    _reference_iso(
        adapter, caption="CHECK REFERENCE 1:8", label="checks reference isometric"
    )
    return _stack_sheet_note_fields(adapter, facts, CHECKS_SHEET)


def _place_checks_continuation_sheet(adapter: Any, facts: SourceFacts) -> list[str]:
    _activate_sheet(adapter, SHEET_NAMES[CHECKS_CONTINUATION_SHEET - 1])
    _heading(adapter, CHECKS_CONTINUATION_SHEET)
    _reference_iso(
        adapter,
        caption="CHECK REFERENCE 1:8",
        label="checks continuation reference isometric",
    )
    return _stack_sheet_note_fields(adapter, facts, CHECKS_CONTINUATION_SHEET)


def _place_continuation_sheet(adapter: Any, facts: SourceFacts) -> list[str]:
    _activate_sheet(adapter, SHEET_NAMES[CONTINUATION_SHEET - 1])
    _heading(adapter, CONTINUATION_SHEET)
    _reference_iso(
        adapter, caption="FINISHED ASSEMBLY 1:8", label="continuation reference isometric"
    )
    return _stack_sheet_note_fields(adapter, facts, CONTINUATION_SHEET)


def _bank_setting_view(
    adapter: Any, facts: SourceFacts, *, centre: tuple[float, float],
    model_z: float, scale: tuple[float, float], label: str,
    step: Callable[[str], None],
) -> Any:
    view = _early_bound(
        place_view(adapter, str(SOURCE), "*Right", *centre, scale=scale), "IView"
    )
    step(f"{label}: place_view")
    set_hidden_lines_removed(adapter, view)
    step(f"{label}: set_hidden_lines_removed")
    _configure_view(adapter, view, exploded=False, label=label)
    step(f"{label}: configure_view")
    _isolate_instances(adapter, view, frozenset(facts.clusters["cylinder-bank"]), label=label)
    step(f"{label}: isolate_instances")
    projected = model_point_in_view(
        adapter, view, (cone_line.X_DRUM / 1000.0, bank_settings.AXIS_Y / 1000.0,
                        model_z / 1000.0), label=label
    )
    _shift_view(adapter, view, (centre[0] - projected[0], centre[1] - projected[1]), label=label)
    step(f"{label}: shift_view")
    return view


def _bank_setting_circle(
    adapter: Any, view: Any, centre: tuple[float, float], radius: float
) -> None:
    """The channel package's view-sketch circle pattern, in sheet metres."""
    name = view_name(adapter, view)
    if not _early_bound(adapter.currentModel, "IDrawingDoc").ActivateView(name):
        raise RuntimeError(f"cannot activate bank setting view {name}")
    adapter.currentModel.ClearSelection2(True)
    sketch = _early_bound(view.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (centre, (centre[0] + radius, centre[1])):
        point = _early_bound(utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint")
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
        raise RuntimeError("cannot create bank setting crop circle")


@contextmanager
def _bank_dimension_source_trace(
    adapter: Any, step: Callable[[str], None], *, label: str
) -> Iterator[None]:
    """Observe existing import/curation COM calls without changing their semantics.

    The rack source-save probe established the observer pattern; unlike that
    probe, delegate to the original _attempt so its error handling is unchanged.
    Direct view/sketch operations have separate checkpoints in the sheet recipe.
    """
    original_attempt = adapter._attempt
    ordinal = 0
    mutators = frozenset({
        "InsertModelAnnotations3", "EditDelete", "SetPosition", "EditRebuild3", "SetText",
    })

    def observed(operation: Any, *args: Any, **kwargs: Any) -> Any:
        nonlocal ordinal
        names = getattr(getattr(operation, "__code__", None), "co_names", ())
        mutations = mutators.intersection(names)
        if not mutations:
            return original_attempt(operation, *args, **kwargs)
        ordinal += 1
        phase = f"{label}: COM {ordinal} {'+'.join(sorted(mutations))}"
        step(f"before {phase}")
        try:
            return original_attempt(operation, *args, **kwargs)
        finally:
            # Also identify a source mutation if the existing operation raises.
            step(f"after {phase}")

    adapter._attempt = observed
    try:
        yield
    finally:
        adapter._attempt = original_attempt


def _place_bank_setting_sheet(
    adapter: Any, facts: SourceFacts, step: Callable[[str], None]
) -> Callable[[], None]:
    """Full bank at 1:1 and a 4:1 north bearing-face detail; no scaled-down views.

    Captions follow measured view outlines; the ordinary crop's identifier is
    owned by its parent view and its rendered clearance survives final rebuilds.

    R7 first marked the source dirty somewhere in this sheet. Keep checkpoints
    around its operations rather than assigning that observation to SetText,
    sketch visibility or model-item import without native evidence. These read
    the source's save flag only; the package's pre-export guard still owns failure.
    """
    _activate_sheet(adapter, SHEET_NAMES[BANK_SETTINGS_SHEET - 1])
    step("bank settings: activate sheet")
    _heading(adapter, BANK_SETTINGS_SHEET)
    step("bank settings: heading")
    overall = _bank_setting_view(
        adapter, facts, centre=BANK_SETTING_CENTER,
        model_z=(bank.FRONT_STRAP_INNER_Z + bank.BACK_STRAP_INNER_Z) / 2.0,
        scale=BANK_SETTING_SCALE, label="cylinder bank setting",
        step=step,
    )
    spring_z = sum(bank.BANK_SPRING_Z) / 2.0
    detail = _bank_setting_view(
        adapter, facts, centre=BANK_SPRING_DETAIL_CENTER, model_z=spring_z,
        scale=BANK_SPRING_DETAIL_SCALE, label="north spring setting",
        step=step,
    )
    annotations = []
    for view, feature, keep, label in (
        (overall, bank_settings.STACK_FEATURE, BANK_SETTING_KEEP, "closed bank length"),
        (detail, bank_settings.SPRING_FEATURE, BANK_SPRING_KEEP, "north spring gap"),
    ):
        _show_base_view_sketches(adapter, view, (feature,), label=label)
        step(f"{label}: show base-view sketch {feature}")
        with _bank_dimension_source_trace(adapter, step, label=f"{label} / {feature}"):
            imported = curate_view_dimensions(
                adapter, view, keep=keep, view_label=label,
                dimensions_by_feature=bank_settings.DRAWING_DIMENSIONS,
            )
            step(f"{label}: curate_view_dimensions")
        annotations.extend(imported)
    radius = BANK_SPRING_CROP_RADIUS_MM / 1000.0
    parent_centre = model_point_in_view(
        adapter, overall,
        (cone_line.X_DRUM / 1000.0, bank_settings.AXIS_Y / 1000.0, spring_z / 1000.0),
        label="spring detail boundary",
    )
    _bank_setting_circle(adapter, overall, parent_centre, radius)
    step("bank settings: overall boundary circle")
    adapter.currentModel.ClearSelection2(True)
    _bank_setting_circle(adapter, detail, BANK_SPRING_DETAIL_CENTER, radius * 4.0)
    step("bank settings: detail crop circle")
    status = int(detail.Crop2(False, False, 1))
    step("bank settings: detail Crop2")
    adapter.currentModel.ClearSelection2(True)
    rebuild_drawing(adapter, label="bank setting crop")
    step("bank settings: crop rebuild")
    detail.UpdateViewDisplayGeometry()
    step("bank settings: detail UpdateViewDisplayGeometry")
    if status != 1 or not bool(detail.IsCropped()):
        raise RuntimeError(f"north spring setting Crop2 failed: {status}")
    # Follow the rebuilt outlines, not insertion coordinates. Centering the
    # overall caption below its view would hit the spring dimension's two-line
    # callout; its right end has clear space below the south pedestal instead.
    # All three annotations target 8 mm, inside their 4 mm minimum-air
    # regions. Bounded anchoring cannot promise a corner on the boundary
    # (R6's detail caption undershot); the actual 4 mm guards stay unchanged.
    placement_gap = 2.0 * VIEW_CAPTION_GAP
    captions = []
    for view, text, right_aligned, label in (
        (overall, "CYLINDER BANK RIGHT 1:1", True, "bank setting caption"),
        (detail, "DETAIL A 4:1 - NORTH SPRING SET", False, "spring detail caption"),
    ):
        view.UpdateViewDisplayGeometry()
        step(f"{label}: UpdateViewDisplayGeometry")
        outline = _view_outline(view)
        _activate_sheet(adapter, SHEET_NAMES[BANK_SETTINGS_SHEET - 1])
        step(f"{label}: activate sheet")
        note = _add_note_block(adapter, text, (outline[0], outline[1]), label=label)
        step(f"{label}: add note")
        extent = _note_extent(adapter, note, label=label)
        step(f"{label}: note extent redraw")
        width = extent[2] - extent[0]
        left = outline[2] - width if right_aligned else (outline[0] + outline[2] - width) / 2.0
        corner = (left, outline[1] - placement_gap)
        _anchor_note(adapter, note, corner, label=label)
        step(f"{label}: anchor note")
        captions.append((note, view, label))

    # This is the channel package's ordinary cropped-view/boundary pattern,
    # not an IDetailCircle. The parent view must own both its sketch circle and
    # identifier so they move together. Keep the whole rendered A above-left
    # of the circle, clear of the pedestal, rather than exempting sheet ink.
    overall_name = view_name(adapter, overall)
    if not _early_bound(adapter.currentModel, "IDrawingDoc").ActivateView(overall_name):
        raise RuntimeError("cannot activate bank setting view for its detail identifier")
    step("spring detail letter: ActivateView")
    letter = _add_note_block(adapter, "A", parent_centre, label="spring detail letter")
    step("spring detail letter: add note")
    letter_extent = _note_extent(adapter, letter, label="spring detail letter")
    step("spring detail letter: note extent redraw")
    # Seed inside the clear region, not on its minimum-air boundary: the
    # bounded anchor helper does not guarantee its requested text-box corner.
    letter_corner = (
        parent_centre[0] - radius - placement_gap - (letter_extent[2] - letter_extent[0]),
        parent_centre[1] + radius + placement_gap + (letter_extent[3] - letter_extent[1]),
    )
    _anchor_note(adapter, letter, letter_corner, label="spring detail letter")
    step("spring detail letter: anchor note")
    placements = []
    for note, label, owner_type in (
        *((note, label, 1) for note, _view, label in captions),
        (letter, "spring detail letter", 0),
    ):
        annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
        position = tuple(float(value) for value in (annotation.GetPosition() or ()))
        if len(position) != 3 or not all(map(math.isfinite, position)):
            raise RuntimeError(f"{label} position is unreadable: {position!r}")
        placements.append((annotation, position, label, owner_type))
    letter_annotation = _early_bound(letter.GetAnnotation(), "IAnnotation")

    def settled() -> None:
        _activate_sheet(adapter, SHEET_NAMES[BANK_SETTINGS_SHEET - 1])
        step("bank settings settled: activate sheet")
        # Preserve the actual native position and independently check current
        # ink clearance, not the helper's requested point (R4's harmless
        # rendered target error was +0.186/-0.185 mm).
        for annotation, baseline, label, expected_owner in placements:
            position = tuple(float(value) for value in (annotation.GetPosition() or ()))
            if len(position) != 3 or not all(map(math.isfinite, position)):
                raise RuntimeError(f"{label} position is unreadable: {position!r}")
            if math.dist(position, baseline) > NOTE_ANCHOR_SETTLE:
                raise RuntimeError(f"{label} moved from {baseline!r} to {position!r}")
            # swAnnotationOwner_e: DrawingView=0, DrawingSheet=1.
            if int(annotation.OwnerType) != expected_owner:
                raise RuntimeError(f"{label} has the wrong native owner: {annotation.OwnerType!r}")
        for note, view, label in captions:
            view.UpdateViewDisplayGeometry()
            step(f"{label} settled: UpdateViewDisplayGeometry")
            extent = _note_extent(adapter, note, label=label)
            step(f"{label} settled: note extent redraw")
            violations = bank_setting_caption_violations(extent, _view_outline(view))
            if violations:
                raise RuntimeError(f"{label}: {'; '.join(violations)}; actual extent {extent!r}")
        owner = _early_bound(letter_annotation.Owner, "IView")
        if view_name(adapter, owner) != overall_name:
            raise RuntimeError("spring detail letter is not owned by the bank setting view")
        extent = _note_extent(adapter, letter, label="spring detail letter")
        violations = bank_setting_letter_violations(extent, parent_centre, radius)
        if violations:
            raise RuntimeError(f"{'; '.join(violations)}; actual extent {extent!r}")
        assert_imported_precision(
            adapter, annotations,
            {name: 2 for names in bank_settings.DRAWING_DIMENSIONS.values() for name in names},
        )
        step("bank settings settled: imported precision readback")
        for annotation in annotations:
            name = dimension_name(adapter, annotation)
            display = _early_bound(
                _early_bound(annotation, "IAnnotation").GetSpecificAnnotation(), "IDisplayDimension"
            )
            # Read only: SetText on an imported dimension can dirty its source.
            text = str(display.GetText(4) or "")  # swDimensionTextCalloutBelow
            if text != bank_settings.DIMENSION_CALLOUTS[name]:
                raise RuntimeError(
                    f"{name} lost its model-authored setting callout: {text!r}; "
                    "rebuild the source assembly"
                )
            dimension = _early_bound(display.GetDimension2(0), "IDimension")
            tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
            upper, lower = bank_settings.DIMENSION_BANDS[name]
            if (abs(float(tolerance.GetMaxValue()) - upper / 1000.0) > 1e-9
                    or abs(float(tolerance.GetMinValue()) - lower / 1000.0) > 1e-9):
                raise RuntimeError(f"{name} lost its model-authored setting band")
        names = {
            dimension_name(adapter, _early_bound(annotation, "IAnnotation"))
            for annotation in (detail.GetAnnotations() or ())
        }
        if bank_settings.SPRING_DIMENSION not in names:
            raise RuntimeError("north spring setting dimension did not survive its crop")
        step("bank settings settled: callout, tolerance and crop readback")

    settled()
    return settled


def _place_full_detail_sheet(adapter: Any) -> tuple[float, float]:
    """The whole drive train, side-on, every modeled tooth and thread.

    Returns the scale the view fitted at. The view stays in Default (the view
    policy's FULL_DETAIL role) whatever the ladder picks.
    """
    _activate_sheet(adapter, SHEET_NAMES[FULL_DETAIL_SHEET - 1])
    label = "full-detail side view"
    placed = FULL_DETAIL_SCALE_LADDER[0]
    region = FULL_DETAIL_REGION
    view = place_view(
        adapter,
        str(SOURCE),
        FULL_DETAIL_ORIENTATION,
        (region[0] + region[2]) / 2.0,
        (region[1] + region[3]) / 2.0,
        scale=placed,
    )
    set_hidden_lines_removed(adapter, view)
    configuration = _configure_view(
        adapter, view, exploded=False, role=ViewRole.FULL_DETAIL, label=label
    )
    scale = full_detail_scale(_view_outline(view), placed)
    if scale != placed:
        _set_view_scale(adapter, view, scale, label=label)
    outline = _view_outline(view)
    _shift_view(adapter, view, centre_shift(outline, region), label=f"{label} centring")
    _telemetry.event(
        "drawing.full_detail_view",
        scale=_scale_text(scale),
        configuration=configuration,
        outline_mm=tuple(round(value * 1000.0, 1) for value in _view_outline(view)),
    )
    _heading(adapter, FULL_DETAIL_SHEET)
    _caption_under(
        adapter,
        view,
        f"RIGHT {_scale_text(scale)} - {FULL_DETAIL_CAPTION}",
        label=f"{label} caption",
    )
    _note_handle_stake(adapter, view, label=f"{label} stake note")
    _note_cam_stake(adapter, view, label=f"{label} cam stake note")
    return scale


def _note_handle_stake(adapter: Any, view: Any, *, label: str) -> None:
    """Point step 7's stake note (rule 23, #1174) at the MHA-DT-32 tip on
    the arm's inboard face (HANDLE_STAKE_TIP_M), the note below and inboard
    of it so its leader leaves the text's right end (handle_stake_note_xy)."""
    stem = frozenset({HANDLE_SCREW_STEM})
    leaf = next(
        (
            leaf
            for leaf in _view_component_leaves(adapter, view, label=label)
            if leaf.visible and _stems_matching(leaf.identities, stem)
        ),
        None,
    )
    if leaf is None:
        raise RuntimeError(f"{label}: the view shows no {HANDLE_SCREW_STEM}")
    (tip_model,) = _anchor_model_points(
        adapter, leaf, (HANDLE_STAKE_TIP_M,), {}, stem=HANDLE_SCREW_STEM, label=label
    )
    tip = model_point_in_view(adapter, view, tip_model, label=label)
    text_xy = handle_stake_note_xy(tip)
    note = _early_bound(
        add_leader_note(
            adapter,
            HANDLE_STAKE_NOTE,
            text_xy=text_xy,
            attach_xy=tip,
            label=label,
            view=view,
        ),
        "INote",
    )
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    points = list(annotation.GetLeaderPointsAtIndex(0) or ())
    shift = 0.0
    # The text does not track its insertion point 1:1 (_anchor_note), so the
    # slide is repeated until the leader start settles.
    for _pass in range(NOTE_ANCHOR_PASSES):
        if len(points) < 6:
            raise RuntimeError(f"{label}: the leader is unreadable: {points!r}")
        step_x = tip[0] - HANDLE_STAKE_NOTE_GAP - float(points[0])
        if abs(step_x) <= HANDLE_STAKE_NOTE_SETTLE:
            break
        position = tuple(float(value) for value in (annotation.GetPosition() or ()))
        if len(position) != 3:
            raise RuntimeError(f"{label}: note position is unreadable: {position!r}")
        if not annotation.SetPosition(position[0] + step_x, position[1], position[2]):
            raise RuntimeError(f"{label}: note SetPosition failed")
        rebuild_drawing(adapter, label=f"{label} slid")
        points = list(annotation.GetLeaderPointsAtIndex(0) or ())
        shift += step_x
    extent = _note_extent(adapter, note, label=label)
    _telemetry.event(
        "drawing.handle_stake_note",
        tip_mm=tuple(round(value * 1000.0, 2) for value in tip),
        shift_mm=round(shift * 1000.0, 2),
        extent_mm=tuple(round(value * 1000.0, 2) for value in extent),
        leader_start_mm=tuple(round(float(value) * 1000.0, 2) for value in points[:2]),
    )
    # The extent's left is the text's: the leader runs right, to the tip.
    if (
        len(points) < 6
        or float(points[0]) > tip[0] - HANDLE_STAKE_NOTE_GAP / 2.0
        or float(points[0]) < extent[0] + HANDLE_STAKE_NOTE_WIDTH / 2.0
    ):
        raise RuntimeError(
            f"{label}: the leader does not leave the note's right end short of "
            f"the tip {tip[0]:.4f}: text left {extent[0]:.4f}, leader {points!r}"
        )


def _note_cam_stake(adapter: Any, view: Any, *, label: str) -> None:
    """Point step 21's cam stake note (rule 23, #1176) at the front MHA-DT-23
    tap mouth (CAM_TAP_MOUTH_M), the note below and left of it
    (cam_stake_note_xy). The front cam is the one furthest right: the Right
    view has south at its right."""
    stem = frozenset({CAM_STEM})
    tips: list[tuple[float, float]] = []
    for leaf in _view_component_leaves(adapter, view, label=label):
        if not (leaf.visible and _stems_matching(leaf.identities, stem)):
            continue
        (mouth,) = _anchor_model_points(
            adapter, leaf, (CAM_TAP_MOUTH_M,), {}, stem=CAM_STEM, label=label
        )
        tips.append(model_point_in_view(adapter, view, mouth, label=label))
    if not tips:
        raise RuntimeError(f"{label}: the view shows no {CAM_STEM}")
    tip = max(tips)
    note = _early_bound(
        add_leader_note(
            adapter,
            CAM_STAKE_NOTE,
            text_xy=cam_stake_note_xy(tip),
            attach_xy=tip,
            label=label,
            view=view,
        ),
        "INote",
    )
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    points = list(annotation.GetLeaderPointsAtIndex(0) or ())
    _telemetry.event(
        "drawing.cam_stake_note",
        tips_mm=tuple(tuple(round(value * 1000.0, 2) for value in t) for t in tips),
        extent_mm=tuple(
            round(value * 1000.0, 2) for value in _note_extent(adapter, note, label=label)
        ),
        leader_mm=tuple(round(float(value) * 1000.0, 2) for value in points),
    )
    if len(points) < 6:
        raise RuntimeError(f"{label}: the leader is unreadable: {points!r}")


def _source_dirty_tracer(source_model: Any) -> Callable[[str], None]:
    """Return ``step(name)``: log the released source's save flag after a step.

    The drawing save writes a dirty source, which the fingerprint guard only
    sees after the fact (run 20261001T035353825Z: drive-train drawing changed
    the released source with no step named).  Each transition is logged with
    the step that caused it, so the next leaf names the culprit.
    """
    state = {"dirty": bool(source_model.GetSaveFlag())}

    def step(name: str) -> None:
        dirty = bool(source_model.GetSaveFlag())
        _telemetry.event("drive_train.source_save_flag", step=name, dirty=dirty)
        if dirty == state["dirty"]:
            return
        state["dirty"] = dirty
        report = _telemetry.warn if dirty else _telemetry.info
        report(f"drive-train source went {'DIRTY' if dirty else 'clean'} after {name}")

    return step


def _place_package(
    adapter: Any, facts: SourceFacts, step: Callable[[str], None]
) -> tuple[dict[str, tuple[float, float]], list[BalloonLanding], Callable[[], None]]:
    """Place every sheet; return each sheet's scale as placed, and every
    balloon landing.

    Every view is placed and pointed at its policy configuration first, then
    the cluster views are exploded, isolated and fitted, and only then is the
    BOM table inserted; after it come only the BOM links and balloons -- the
    frame drawing's order. A view configuration switch made once the BOM table
    (bound to Default Simplified) exists dirtied the released source, and the
    drawing save wrote it: farm probes read the source's save flag after every
    drawing step, and it went dirty on the rebuild of the first switch after
    ``insert_bom_table`` -- the cone-crank cluster view, and, with every switch
    moved ahead of the explodes but not the BOM, the sequence reference view --
    and clean again on ``save_drawing``. The
    full-detail view stays in Default, so it switches nothing.
    """
    _create_package_sheets(adapter)
    step("create sheets")
    findings = _place_assembled_sheet(adapter, facts)
    step("assembled sheet")
    bom_view = _place_bom_view(adapter)
    step("BOM view")
    findings += _place_sequence_sheet(adapter, facts)
    step("sequence sheet")
    findings += _place_crank_sheet(adapter, facts)
    step("crank sheet")
    findings += _place_bank_sheet(adapter, facts)
    step("bank sheet")
    settings_settled = _place_bank_setting_sheet(adapter, facts, step)
    step("bank setting dimensions")
    findings += _place_fit_sheet(adapter, facts)
    step("fit sheet")
    findings += _place_checks_sheet(adapter, facts)
    step("checks sheet")
    findings += _place_checks_continuation_sheet(adapter, facts)
    step("checks continuation sheet")
    full_detail = _place_full_detail_sheet(adapter)
    step("full-detail sheet")
    findings += _place_continuation_sheet(adapter, facts)
    step("continuation sheet")
    cluster_views = {}
    for cluster in CLUSTER_SHEETS:
        cluster_views[cluster] = _place_cluster_view(adapter, cluster)
        step(f"{cluster} view")
    cluster_scales = {}
    for cluster, view in cluster_views.items():
        cluster_scales[cluster] = _fit_cluster_view(adapter, cluster, view, facts)
        step(f"{cluster} fit")
    bom_name, items = _insert_bom(adapter, bom_view, facts)
    step("BOM table")
    placed = {}
    for cluster, view in cluster_views.items():
        placed[SHEET_NAMES[CLUSTER_SHEETS[cluster] - 1]] = _balloon_cluster_sheet(
            adapter, cluster, view, facts, cluster_scales[cluster], bom_name=bom_name, items=items
        )
        step(f"{cluster} balloons")
    assert_full_detail_view(adapter, label="drive-train package")
    for sheet_name, (sheet_balloons, _landings) in placed.items():
        _final_balloon_uncross(adapter, sheet_name, sheet_balloons)
    step("balloon uncross")
    _check_package_layout(adapter, findings)
    step("layout check")
    landings = [landing for _balloons, sheet in placed.values() for landing in sheet]
    return package_sheet_scales(cluster_scales, full_detail), landings, settings_settled


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source assembly is missing: {SOURCE}")
    fingerprint = _source_fingerprint(SOURCE)
    check("open drive-train drawing source", await adapter.open_model(str(SOURCE)))
    source_model = _early_bound(adapter.currentModel, "IModelDoc2")
    if bool(source_model.GetSaveFlag()):
        raise RuntimeError("drive-train source assembly is already dirty; refusing to discard changes")
    read_required_properties(
        source_model,
        ("Number", "Revision", "Title", "Material Specification", "Finish", "Quantity"),
        required=("Number", "Revision", "Material Specification", "Finish", "Quantity"),
    )
    source_title = str(source_model.GetTitle() or "")
    if not source_title:
        raise RuntimeError("drive-train source assembly has no document title")

    artifacts: dict[str, str] | None = None
    try:
        try:
            facts = _validate_source(source_model)
            step = _source_dirty_tracer(source_model)
            step("validate source")
            sheet_scales, landings, settings_settled = _place_package(adapter, facts, step)

            def assert_source_clean(where: str) -> None:
                # Saving the drawing would write a dirty released source.
                step(where)
                if bool(source_model.GetSaveFlag()):
                    raise RuntimeError(
                        f"drive-train drawing dirtied the released source assembly "
                        f"by {where}; the per-step trace names the step"
                    )

            assert_source_clean("package placement")
            artifacts = await finalize_drawing(
                adapter,
                OUTPUTS,
                layout=SPEC.layout,
                pdf_title="Drive-Train Assembly Drawing Package",
                scale=ASSEMBLED_SCALE,
                expected_sheet_names=SHEET_NAMES,
                sheet_layouts=SHEET_LAYOUTS,
                sheet_scales=sheet_scales,
                settled_checks=(
                    lambda: assert_balloon_landings(adapter, landings),
                    lambda: assert_source_clean("finalize rebuilds"),
                    settings_settled,
                ),
            )
        except Exception:
            _export_failure_pdf(adapter, "build")
            raise
    finally:
        primary_error = sys.exception()
        cleanup_errors: list[str] = []
        if artifacts is None:
            try:
                active_model = adapter.currentModel
                if active_model is not None:
                    active_model = _early_bound(active_model, "IModelDoc2")
                    if int(active_model.GetType()) == 3:
                        drawing_title = str(active_model.GetTitle() or "")
                        if drawing_title:
                            adapter.swApp.CloseDoc(drawing_title)
                        else:
                            cleanup_errors.append("generated drive-train drawing has no title")
            except Exception as exc:  # noqa: BLE001
                cleanup_errors.append(f"failed to close generated drive-train drawing: {exc}")
        try:
            adapter.swApp.CloseDoc(source_title)
            if adapter.swApp.GetOpenDocumentByName(str(SOURCE.resolve())) is not None:
                cleanup_errors.append(f"drive-train source {source_title!r} remained open")
        except Exception as exc:  # noqa: BLE001
            cleanup_errors.append(f"failed to close drive-train source {source_title!r}: {exc}")
        try:
            after = _source_fingerprint(SOURCE)
            if after != fingerprint:
                cleanup_errors.append(
                    "drive-train drawing generation changed the released source assembly: "
                    f"{fingerprint!r} -> {after!r}"
                )
        except Exception as exc:  # noqa: BLE001
            cleanup_errors.append(f"failed to verify drive-train source fingerprint: {exc}")
        if cleanup_errors:
            message = "; ".join(cleanup_errors)
            if primary_error is not None:
                _telemetry.warn(f"drive-train drawing cleanup after failure: {message}")
            else:
                raise RuntimeError(message)

    if artifacts is None:
        raise RuntimeError("drive-train drawing package returned no artifacts")
    return artifacts


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[ARTIFACT_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
