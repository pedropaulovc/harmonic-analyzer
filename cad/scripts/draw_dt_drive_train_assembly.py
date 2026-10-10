r"""Create the native ten-sheet drive-train assembly drawing package (MHA-DT-000).

The released ``dt-drive-train.SLDASM`` stays authoritative and byte-for-byte
unchanged. This recipe consumes the builder-owned ``DRIVE_TRAIN_EXPLODED``
presentation (``_drive_train_explode``) and reads every count, identity and
position it prints from the opened model; nothing pending on a sibling branch
(crank hub, lever pin, pinion tooth count, bracket placement) is typed here.

Sheet numbers are fixed: cross-references on the sheets cite them, so a sheet
whose content is still pending keeps its slot with a placeholder. Every cited
number is generated from the ``*_SHEET`` constants, never typed.
"""

from __future__ import annotations

import argparse
import hashlib
import math
import re
import sys
import textwrap
from datetime import UTC, datetime
from itertools import combinations
from pathlib import Path
from typing import Any, Callable, Literal, NamedTuple, Sequence

import _config
import _seat_forensics
import _telemetry
import ch_pivot_shaft_spec as pivot_shaft
import cylinder_bank_layout as bank
import dt_drive_train_steps as steps
import pinion_rig_fitup as FITUP
import pinion_rig_tip_gap as TIP_GAP
from ch_channel_assembly_steps import NORTH_BRACKET_SET_KEY, RODS_PINNED_REF
from ch_channel_assembly_steps import step_ref as channel_step_ref
from _common import _early_bound, check, run_build
from _drawing_common import (
    SIMPLIFIED_VIEW_CONFIGURATION,
    BalloonLanding,
    DrawingOutputs,
    ViewRole,
    _SW_SHADED_EDGES,
    _leader_segments_of,
    _spread_balloons,
    add_component_bom_balloons,
    apply_view_configuration,
    assert_balloon_landings,
    assert_full_detail_view,
    balloon_item_resolved,
    check_drawing_layout,
    collect_layout_elements,
    create_blank_drawing_sheets,
    finalize_drawing,
    insert_bom_table,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_hidden_lines_removed,
    set_high_quality_shaded_with_edges,
    set_view_exploded_state,
    view_configuration,
)
from _simplified_names import simplified_name
from _drawing_layout_check import LeaderSegment, find_leader_leader_crossings
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME, DrawingLayout
from _dt_drive_train_balloon_anchors import DRIVE_TRAIN_BALLOON_ANCHORS
from dt_cone_swing_platform_spec import POST_MOUNT_ENGAGEMENT_ASSEMBLY_FACT
from dt_cone_gear_stack import COUNT as CONE_GEAR_COUNT, STACK_L20_ACCEPT
from cone_stack_end_play import COLLAR_FEELER, SHAFT_END_PLAY
from dt_cone_tip_block_spec import ADJUSTER_ENGAGEMENT_ASSEMBLY_FACT
from dt_crank_pinion_spec import (
    SEAT_FEELER_MM as PINION_SEAT_FEELER,
    T120_FITUP_ASSEMBLY_CHECK,
)
from dt_crank_pinion_spec import SHAFT_END_RECESS_MAX as PINION_RECESS_MAX
from dt_crank_pinion_spec import SHAFT_END_RECESS_MIN as PINION_RECESS_MIN
from dt_crank_seat_washer_spec import GAP_MAX as WASHER_GAP_MAX
from dt_crank_seat_washer_spec import GAP_MIN as WASHER_GAP_MIN
from dt_cylinder_end_disc_spec import WASHER_THICK as BANK_WASHER_THICK
from dt_crank_hub_notes import FRONT_FACE_DATUM as HUB_FRONT_FACE_DATUM
from vn_keeper_chain_spec import BEAD_COUNT as KEEPER_CHAIN_BEADS
from dt_drive_train_assembly_spec import (
    CLUSTERS,
    EXPLODED_VIEW_NAME,
    PENDING_STEMS,
    SOURCE_CONFIGURATION,
    Cluster,
    Instance,
    cluster_members,
    unclassified_stems,
)
from dt_pinion_spring_section import SCREW_EAST_OF_PIVOT as SPRING_SCREW_EAST_OF_PIVOT
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import add_note, place_view

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
DRAWING_NUMBER = "MHA-DT-000"
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
    "CONE SET + CRANK EXPLODED",
    "ALIGNMENT PINION RIG EXPLODED",
    "ASSEMBLY SEQUENCE",
    "ASSEMBLY SEQUENCE CONT. - CYLINDER BANK",
    "ASSEMBLY SEQUENCE CONT. + FIT",
    "CHECKS + SETUP",
    "FULL-DETAIL SIDE VIEW",
    "ASSEMBLY SEQUENCE CONTINUATIONS + CRANK FIT",
)
SHEET_LAYOUTS = {name: DrawingLayout.LANDSCAPE for name in SHEET_NAMES}
if SPEC.layout is not DrawingLayout.LANDSCAPE:
    raise AssertionError("the drive-train package primary sheet must remain landscape")
# Which sheet shows which cluster; the BOM sheet and captions cite these.
CLUSTER_SHEETS: dict[Cluster, int] = {
    "cylinder-bank": 3,
    "cone-crank": 4,
    "pinion-rig": 5,
}
CLUSTER_TITLES: dict[Cluster, str] = {
    "cylinder-bank": "CYLINDER BANK",
    "cone-crank": "CONE SET, SWING PLATFORM AND CRANK",
    "pinion-rig": "ALIGNMENT PINION RIG",
}
# #743 grew steps 8-9 past sheet 6's right field, so the bank sequence has its
# own sheet (Main, B1 re-ruling 2026-09-26).
SEQUENCE_SHEET = 6
BANK_SHEET = 7
FIT_SHEET = 8
CHECKS_SHEET = 9
# Every view at 1:2 or smaller prints the teeth/thread-free "Default
# Simplified" configuration (the assembly view policy in _drawing_common); the
# user asked for the ENTIRE drive train at 1:2 or larger with every modeled
# tooth and thread, so sheet 10 carries it. Continuations are appended after
# that sheet: no existing sheet number or pointer moves.
FULL_DETAIL_SHEET = 10
CONTINUATION_SHEET = 11

ASSEMBLED_SCALE = (1.0, 3.0)
ASSEMBLED_ISO_SCALE = (1.0, 3.0)
REFERENCE_ISO_SCALE = (1.0, 8.0)
# At 1:3 the bank and rig explodes filled about a fifth of their sheets (Fable
# review of baseline-5); the cone-crank ring already spans ~170 x 150 mm there.
# The bank still filled a small fraction of its sheet at 1:2 (r9 Fable review);
# at 2:3 its ~145 x 107 mm outline plus the balloon ring fits the 395 x 176 field.
# The rig cannot grow: its ~116 mm-tall outline plus ring already nears 176.
# Each is the cluster's PREFERRED scale: the build places the view there and
# steps down CLUSTER_SCALE_LADDER until its balloon ring fits (cluster_ring_scale).
CLUSTER_SCALES: dict[Cluster, tuple[float, float]] = {
    "cylinder-bank": (2.0, 3.0),
    "cone-crank": (1.0, 3.0),
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
    }


SHEET_SCALES = package_sheet_scales(CLUSTER_SCALES)

# --- sheet 1: projected front/top/right group + isometric ---------------------
# The projected group's lower-left lands here; the views are aligned on the
# model origin (ASME third angle: top above front, right to the right of it).
# At 1:3 the group is ~177 mm tall (front y ~42 + gap + top z ~121, the old
# MHA-DT-000 sheet); the 175 mm the first region allowed failed on the farm (leaf
# 20260923T045245Z-1-b34a8422). The origin sits just above the title block
# (top y=0.0655) and the region top 4.5 mm under the zone border.
PROJECTED_GROUP_ORIGIN = (0.024, 0.068)
PROJECTED_GAP = 0.014
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
    "MHA-DT-003 CONE GEAR\n"
    f"STATIONS: SHEET {FIT_SHEET}"
)

# --- sheets 3-5: exploded cluster views --------------------------------------
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
# circles 1.5 apart; on sheet 5 the left-block attachments bunch so tightly that
# items 17/18/19/20/26 read as one converging knot (Main eye-pass of r6b).
# Placement stays in attachment-angle order, so widening cannot add a crossing.
CLUSTER_BALLOON_CLEARANCE = {
    "cylinder-bank": 0.0015,
    "cone-crank": 0.0015,
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
# 20260923T214354Z-1-4126331f). Sheet 6 carries steps 1-5 on the left, its
# right field kept free for D1 (#957). Step 10 uses sheet 7's right field.
# Sheet 8 carries the first rig steps and station table; the final crank/rig
# steps and washer fit are on the appended continuation sheet.
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

# --- sheet 10: the whole drive train, full detail ----------------------------
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
    "dt-cylinder-gear-shaft": "MHA-DT-013",
    "dt-arbor-pedestal": "MHA-DT-002",
    "dt-cylinder-end-disc": "MHA-DT-026",
    "vn-cylinder-bank-spring": "MHA-VN-052",
    "dt-cylinder-gear": "MHA-DT-012",
    "vn-pedestal-hold-down-screw": "MHA-VN-032",
    "vn-arbor-set-screw": "MHA-VN-034",
    "vn-foot-screw": "MHA-VN-020",
    "dt-cone-gear-shaft": "MHA-DT-004",
    "dt-cone-gear": "MHA-DT-003",
    "dt-crank-drive-gear": "MHA-DT-007",
    "dt-cone-swing-platform": "MHA-DT-020",
    "dt-cone-pivot-post": "MHA-DT-005",
    "dt-cone-tip-block": "MHA-DT-021",
    "vn-cone-tip-collar": "MHA-VN-016",
    "vn-cone-tip-adjuster": "MHA-VN-017",
    "vn-cone-tip-pinch-screw": "MHA-VN-018",
    "vn-cone-tip-block-screw": "MHA-VN-030",
    "vn-post-mount-screw": "MHA-VN-031",
    "vn-cone-lock-knob": "MHA-VN-013",
    "vn-cone-pivot-screw": "MHA-VN-014",
    "vn-swing-stop-screw": "MHA-VN-015",
    "dt-crankshaft": "MHA-DT-011",
    "dt-crank-pinion": "MHA-DT-010",
    "dt-crank-pinion-pin": "MHA-DT-029",
    "dt-crank-arm": "MHA-DT-006",
    "dt-crank-pin": "MHA-DT-009",
    "dt-crank-pin-ring": "MHA-DT-027",
    "dt-crank-pin-eye": "MHA-DT-028",
    "vn-keeper-chain": "MHA-VN-035",
    "vn-keeper-chain-link": "MHA-VN-036",
    "vn-fillister-screw": "MHA-VN-006",
    "dt-crank-handle": "MHA-DT-008",
    "dt-crank-handle-ferrule": "MHA-DT-034",
    "dt-crank-handle-butt-cup": "MHA-DT-035",
    "dt-crank-handle-pivot-screw": "MHA-DT-032",
    "dt-crank-hub": "MHA-DT-031",
    "vn-crank-hub-pin": "MHA-VN-029",
    "dt-crank-seat-washer": "MHA-DT-036",
    "vn-crank-seat-drive-pin": "MHA-VN-044",
    "dt-alignment-pinion": "MHA-DT-001",
    "dt-pinion-bracket": "MHA-DT-014",
    "dt-pinion-pivot-block": "MHA-DT-018",
    "dt-pinion-pivot-shaft": "MHA-DT-019",
    "dt-pinion-lift-rod": "MHA-DT-017",
    "dt-pinion-spring": "MHA-DT-024",
    "dt-pinion-cam-pin": "MHA-DT-025",
    "dt-pinion-cam": "MHA-DT-023",
    "dt-pinion-lever": "MHA-DT-016",
    "dt-pinion-lever-pin": "MHA-DT-030",
    "dt-pinion-handle": "MHA-DT-015",
    "dt-pinion-arbor": "MHA-DT-022",
    "dt-pinion-arbor-collar": "MHA-DT-033",
    "vn-pinion-strap-pin": "MHA-VN-033",
    "vn-slotted-screw": "MHA-VN-019",
}
BOM_DESCRIPTIONS = {
    "dt-cylinder-gear-shaft": "CYLINDER GEAR ARBOR",
    "dt-arbor-pedestal": "ARBOR PEDESTAL",
    "dt-cylinder-end-disc": "CYLINDER BANK THRUST WASHER",
    "vn-cylinder-bank-spring": "WAVE DISC SPRING, MCMASTER 9714K392",
    "dt-cylinder-gear": "CYLINDER GEAR WITH CAM, 120T",
    "vn-pedestal-hold-down-screw": "#8-32 FILLISTER SCREW, MCMASTER 90280A197",
    "vn-arbor-set-screw": "#4-40 X 1/4 SET SCREW, MCMASTER 91375A106",
    "vn-foot-screw": "#4-40 FILLISTER SCREW, MCMASTER 90280A108",
    "dt-cone-gear-shaft": "CONE GEAR SHAFT",
    "dt-cone-gear": "CONE GEAR, T006-T120 BY 6; 1 EACH",
    "dt-crank-drive-gear": "CRANK DRIVE GEAR, 64T",
    "dt-cone-swing-platform": "CONE SWING PLATFORM",
    "dt-cone-pivot-post": "CONE PIVOT POST AND CRANK COLUMN",
    "dt-cone-tip-block": "CONE TIP BLOCK",
    "vn-cone-tip-collar": "1/16 SHAFT COLLAR, MCMASTER 9414T1",
    "vn-cone-tip-adjuster": "CUP-TIP SET SCREW, MCMASTER 94025A164",
    "vn-cone-tip-pinch-screw": "#4-40 FILLISTER SCREW, MCMASTER 91794A112",
    "vn-cone-tip-block-screw": "#4-40 X 3/8 SHCS, MCMASTER 91251A108",
    "vn-post-mount-screw": "1/4-20 FILLISTER SCREW, MSC 40923898",
    "vn-cone-lock-knob": "KNURLED THUMB SCREW, MCMASTER 93585A190",
    "vn-cone-pivot-screw": "SHOULDER SCREW, MCMASTER 91829A560",
    "vn-swing-stop-screw": "#4-40 FILLISTER SCREW, MCMASTER 90280A108",
    "dt-crankshaft": "CRANKSHAFT",
    "dt-crank-pinion": "CRANK PINION, 16T",
    "dt-crank-pinion-pin": "CRANK PINION RETENTION PIN",
    "dt-crank-arm": "CRANK ARM",
    "dt-crank-pin": "CRANK TAPER PIN, 1:48",
    "dt-crank-pin-ring": "TAPER PIN KEEPER RING",
    "dt-crank-pin-eye": "KEEPER CHAIN ANCHOR EYE",
    "vn-keeper-chain": "#3 BRASS BEAD CHAIN, MCMASTER 3606T118",
    "vn-keeper-chain-link": "LOOP LINK, MCMASTER 3606T811",
    "vn-fillister-screw": "#4-40 BRASS FILLISTER, MCMASTER 90114A511",
    "dt-crank-handle": "CRANK HANDLE",
    "dt-crank-handle-ferrule": "CRANK HANDLE FERRULE",
    "dt-crank-handle-butt-cup": "CRANK HANDLE BUTT CUP",
    "dt-crank-handle-pivot-screw": "CRANK HANDLE PIVOT SCREW",
    "dt-crank-hub": "CRANK HUB",
    "vn-crank-hub-pin": "CRANK HUB AXIAL PIN",
    "dt-crank-seat-washer": "CRANK SEAT THRUST WASHER",
    "vn-crank-seat-drive-pin": "3/32 X 1/4 DOWEL PIN, MCMASTER 98381A434",
    "dt-alignment-pinion": "ALIGNMENT PINION",
    "dt-pinion-bracket": "PINION BRACKET STRAP",
    "dt-pinion-pivot-block": "PINION PIVOT BLOCK",
    "dt-pinion-pivot-shaft": "PINION PIVOT SHAFT",
    "dt-pinion-lift-rod": "PINION LIFT ROD",
    "dt-pinion-spring": "PINION SPRING",
    "dt-pinion-cam-pin": "PINION CAM FOLLOWER PIN",
    "dt-pinion-cam": "PINION ECCENTRIC CAM, WITH M2.5 SET SCREW",
    "dt-pinion-lever": "PINION LEVER",
    # Grouped: its configurations' BOM description wins over a written cell,
    # so the row prints the registry description the builder stamps.
    "dt-pinion-lever-pin": str(_config.parts("dt-pinion-lever-pin")["description"]),
    "dt-pinion-handle": "PINION GRIP CROSSROD",
    "dt-pinion-arbor": "INTEGRAL PINION ARBOR AND GRIP HEAD",
    "dt-pinion-arbor-collar": "PINION ARBOR RETENTION COLLAR",
    "vn-pinion-strap-pin": "1/16 X 1/2 SPRING PIN, MCMASTER 98296A027",
    "vn-slotted-screw": "#8-32 FILLISTER SCREW, MCMASTER 90280A201",
}
if set(BOM_DESCRIPTIONS) != set(BOM_PART_NUMBERS):
    raise AssertionError("drive-train BOM description coverage is incomplete")
if set(BOM_PART_NUMBERS) != {stem for stems in CLUSTERS.values() for stem in stems}:
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
    """Reflow whole steps; retain headings, lettered heads and deeper sublists."""
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
    return "\n".join(
        line.replace("\u00a0", " ")
        for first, continuation, body in paragraphs
        for line in textwrap.wrap(
            re.sub(r"\b(SHEETS?) (?=\d)", r"\1" + "\u00a0", body),
            width=_STEP_LINE_WIDTH,
            initial_indent=first,
            subsequent_indent=continuation,
            break_long_words=False,
            break_on_hyphens=False,
        )
    )


def _split_sequence_notes(text: str, key: str, heading: str) -> tuple[str, str]:
    """Move a whole numbered step and its successors to a continuation field."""
    head = f"{steps.step_number(key)}. "
    first, separator, rest = text.partition("\n" + head)
    if not separator:
        raise ValueError(f"assembly sequence has no head for {key!r}")
    return first, f"{heading}\n{head}{rest}"


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
        "1. SLIDE MHA-DT-007 ONTO THE MHA-DT-004 D-FLAT AGAINST ITS COLLAR.",
        "   SLIDE {cone_gears}X MHA-DT-003 ON, T120 FIRST THROUGH T006,",
        f"   EACH FLAT TO FLAT AND AGAINST THE LAST. MEASURE THE {CONE_GEAR_COUNT}-GEAR",
        f"   STACK T120 SOUTH FACE TO T006 NORTH FACE: {STACK_L20_ACCEPT[0]:.3f}-"
        f"{STACK_L20_ACCEPT[1]:.3f}.",
        "   RE-FACE A LONG STACK; REMAKE THE THINNEST GEAR OF A SHORT ONE.",
        # U37c (user, 2026-09-23): MHA-VN-031 is MSC 40923898, 1/4-20 x 3-1/2
        # slotted fillister, through the 6.02 counterbore.  Cut each screw
        # against its own MHA-DT-005/MHA-DT-020 matched holes, never proud of the
        # plate underside.  The MHA-DT-020 plate's worst-case 5.72 mm = 0.90D
        # includes stock, cut allowance and both tap-mouth edge breaks; this
        # is the named short-engagement exception in the drawing policy.
        # The sheet states the actual minimum, never the governance label.
        "2. ALIGN MHA-DT-005 COUNTERBORES TO MHA-DT-020 TAPS; SCREW WITH 2X",
        "   MHA-VN-031 FROM TOP, EACH CUT TO FIT: FLUSH TO 0.3 SHORT OF",
        "   MHA-DT-020 UNDERSIDE, NEVER PROUD (NOMINAL LENGTH 86.0).",
        "   CHAMFER ENDS; " + POST_MOUNT_ENGAGEMENT_ASSEMBLY_FACT,
        # User ruling 2026-09-29 (eight-views-4 photo): MHA-DT-021 is a prism
        # standing directly on MHA-DT-020, held by one #4-40 socket head cap
        # screw up from under the plate through its counterbored hole.  The
        # MHA-VN-016 collar goes on loose here; step 3 sets it.  Whether the post
        # pattern itself can be assembled is issue #1134 (pre-existing).
        "   JOURNAL MHA-DT-004 IN MHA-DT-005. SLIP MHA-VN-016 ON THE TIP STUB.",
        "   STAND MHA-DT-021 ON MHA-DT-020 AT ITS HOLE; MHA-VN-030 UP FROM",
        "   UNDER THE PLATE THROUGH THE COUNTERBORE INTO THE MHA-DT-021 FOOT,",
        "   SNUG. LEAVE MHA-VN-031 LOOSE ENOUGH TO TURN MHA-DT-005.",
        # User ruling 2026-09-29: the stack's north float is held on the
        # shaft by MHA-VN-016, set off T006 by one feeler and locked on the
        # D-flat; the cup screw alone then sets MHA-DT-004's end play
        # (cone_stack_end_play).  U32 (user, 2026-09-23): option 1A turn-set,
        # worded without the pitch (#10-32: 1/8 turn is ~0.10).  The tip's
        # lateral error is taken up by turning MHA-DT-005 on its screws'
        # clearance (TIP_LATERAL_CAPACITY_MM in build_drive_train_assembly),
        # so the fitter centres the tip in the cup before locking the post
        # (Codex P1 on #1136, 9e9982c5d).
        "3. PUSH THE STACK ONTO THE MHA-DT-004 COLLAR. PUSH MHA-VN-016 ONTO A",
        f"   {COLLAR_FEELER:.2f} FEELER ON T006; LOCK ITS SET SCREW ON THE FLAT.",
        "   THREAD MHA-VN-017 INTO MHA-DT-021 TO THE TIP. TURN MHA-DT-005 ON ITS",
        "   SCREWS UNTIL THE TIP CENTRES IN THE CUP; TIGHTEN BOTH MHA-VN-031",
        "   AND RECHECK. THREAD MHA-VN-017 ON UNTIL MHA-DT-004 JUST STOPS",
        "   SHUTTLING AND STILL TURNS FREELY; BACK OFF 1/8 TURN; TIGHTEN",
        "   MHA-VN-018 ACROSS THE SLIT. END PLAY "
        f"{SHAFT_END_PLAY[0]:.2f}-{SHAFT_END_PLAY[1]:.2f}, BY FEEL OR INDICATOR.",
        "   MHA-VN-017 " + ADJUSTER_ENGAGEMENT_ASSEMBLY_FACT,
        # User ruling 2026-09-28: the crank journal runs directly in the post;
        # the centres are fixed, and the only mesh requirement is no binding.
        # CONTRACT-crank: MHA-VN-044 press to the blind-hole floor (their proud
        # length is the result).  User ruling 2026-09-30 (MHA-DT-036 floor 0.5):
        # MHA-DT-036 is faced to fit at assembly; it goes on from the rear end
        # before the journal enters the bore, and MHA-DT-010's pin is
        # match-drilled, so the gap is taken in a trial fit before either
        # (CRANK_WASHER_FIT_NOTES, on the continuation sheet).
        # User ruling 2026-09-30 (#1154): the 16T's shoulder and turned band
        # are feeler-checked against T120 before the pin is drilled.  The
        # pair may rub on T120 until that check closes, so the seat and the
        # check come first, turning by hand, and the free-running revolution
        # after them (Codex P2 on #1154, review 3).  The check's last line is
        # short; the step carries on after it.
        "4. PRESS 2X MHA-VN-044 TO THE MHA-DT-011 COLLAR HOLE FLOORS. FIT MHA-DT-011 IN",
        "   THE MHA-DT-005 CRANK BORE; SLIDE MHA-DT-010 ON UNPINNED, TOOTH IN GAP",
        f"   WITH MHA-DT-007. FIT MHA-DT-036 PER SHEET {CONTINUATION_SHEET}. WITH MHA-DT-036 SEATED,",
        f"   SET MHA-DT-010 {PINION_SEAT_FEELER:.2f} OFF THE MHA-DT-005 BOSS NORTH FACE WITH A FEELER.",
        T120_FITUP_ASSEMBLY_CHECK + " THEN",
        "   TURN MHA-DT-007 ONE FULL REVOLUTION; IT MUST NEVER BIND (ELSE CHECK",
        "   THE PARTS AND BORE SPACING). THEN MATCH-DRILL/REAM MHA-DT-029 AT BOSS",
        "   MID-LENGTH WITH MHA-DT-011, FLUSH BOTH SIDES; RE-CHECK NO BINDING.",
        "5. PAPER-DRIVE T12 ON MHA-DT-011 BEFORE THE ARM, HOLES OVER 2X MHA-VN-044.",
        # U33 (user, 2026-09-23): crank hub MHA-DT-031 pressed into the arm and
        # seam-pinned by MHA-VN-029 (a 4 m6 dowel, 4.0 long = half the arm); the
        # MHA-DT-009 cross-hole runs behind the arm through the hub barrel. The
        # handle rides the MHA-DT-032 shoulder screw. Wording from crankhub.
        "6. PRESS MHA-DT-031 INTO MHA-DT-006 TO THE SHOULDER, FACES FLUSH.",
        "   MATCH-DRILL/REAM THE SEAM Ø4 X 4.0 DEEP; DRIVE MHA-VN-029 FLUSH. SLIDE",
        f"   ONTO MHA-DT-011, SET HUB FRONT FACE FLUSH WITH THE {HUB_FRONT_FACE_DATUM},",
        "   PUNCH MARKS ALIGNED; ONLY THEN TAPER-REAM 1:48 THROUGH HUB AND",
        "   SHAFT; LIGHT-DRIVE MHA-DT-009, REMOVABLE BY TAP ON SMALL END. HANG",
        # Codex #1140: the keeper chain's length and topology belong on the
        # sheet; the bead count is the spec's solve, never a typed number.
        "   MHA-DT-027 FROM THE PIN HEAD; CLAMP MHA-DT-028 UNDER MHA-VN-006. CUT MHA-VN-035",
        f"   TO {KEEPER_CHAIN_BEADS} BEADS; THREAD IT THROUGH THE MHA-DT-028 LOOP AND MHA-DT-027; SNAP",
        "   ONE END BEAD INTO EACH DOME OF MHA-VN-036.",
        # Local review of 747487c71: the cup cures centred on the screw, or
        # its offset can bind the head and shoulder.
        "7. EPOXY MHA-DT-034 ON THE MHA-DT-008 TENON, MHA-DT-035 IN ITS BUTT; CURE ON",
        "   THE WAXED MHA-DT-032 THROUGH BOTH. FIT IT; SLIDE MHA-DT-008 ON; THREAD IT",
        "   INTO MHA-DT-006, LOCTITE 222, SHOULDER TIGHT; END PLAY 0.25-1.0; FILE",
        f"   TIP FLUSH TO ARM INBOARD FACE, BREAK EDGE. CYLINDER BANK: SHEET {BANK_SHEET}.",
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
        # The MHA-DT-013 print owns the stock (3/8 1018 CF X 190, long enough for
        # the edge finder) and its cut-to-fit rule (Main, r9).
        # #743 (retention743 plan section 4, user rulings Q1-Q3): the bank is
        # a solid stack, so fit-up proves the stack length, locates the back
        # strap as the Z datum and swaps a setting mandrel for the finished
        # arbor, which the MHA-VN-034 apex set screws hold. #948 ruling R
        # (PR #1292): the front strap is set one BANK_SPRING_SET blade off the
        # front washer and the MHA-VN-052 wave spring in that gap holds the
        # bank back (no end play); the back strap's DRO target moves north by
        # the miced back washer's excess, W - 1.500. Supersedes U34's
        # disc/feeler end play and its "span -6.0" arbor. Every limit is
        # cylinder_bank_layout's, rounded inward
        # (test_bank_fitup_limits_are_the_layout_bands):
        # 9A: Y is the hole-table rear-face distance of the back strap inner
        # face, 70.538 +/-0.10; north (+Z) is LESS Y.
        # 8 (user ruling L20 d'): T 7.0565 +/-0.025 and L20 141.13 +/-0.10,
        # both exact at the places printed, read from the layout's limits. A
        # short stack cannot be re-faced longer: its thinnest gear is remade.
        "8. MIC EACH OF {cylinder_gears}X MHA-DT-012, CAM FACE TO BACK FACE:",
        f"   {bank.GEAR_THICKNESS_ACCEPT[0]:.4f}-{bank.GEAR_THICKNESS_ACCEPT[1]:.4f};"
        " RECORD. SLIDE THEM ONTO A 3/8 GROUND SETTING",
        # Each connecting rod comes pinned to its rocker arm (MHA-CH-000's
        # bench pinning step, cited by key): its ring is captured in the closed
        # cam slot as the next gear goes on, so the pair travels with its gear.
        "   MANDREL ~190 LONG, ALL ALIKE, CAM SIDE FRONT; SET EACH CONNECTING",
        f"   ROD + ARM PAIR ({RODS_PINNED_REF}) ON ITS CAM AS ITS GEAR GOES ON.",
        "   CLAMP LIGHTLY END TO END: GEAR 0 CAM FACE TO GEAR 19 BACK FACE",
        f"   {bank.STACK_L20_ACCEPT[0]:.2f}-{bank.STACK_L20_ACCEPT[1]:.2f}."
        " LONG: SLIDE THE GEARS OFF IN ORDER WITH THEIR PAIRS TO THE THICKEST",
        "   CAM; RE-FACE ITS CAM FACE, RESTACK, REMEASURE.",
        f"   SHORT OF {bank.STACK_L20_ACCEPT[0]:.2f}: REMAKE THE THINNEST GEAR,"
        " REMEASURE.",
        "   SLIDE THE STACK OFF IN ORDER, EACH GEAR WITH ITS PAIR.",
        "9. BASE MHA-FR-001 OUT OF THE FRAME, ON THE MILL TABLE, PAD TRAMMED,",
        "   OVERHANG SUPPORTED; CONE SET (MHA-DT-020) NOT FITTED.",
        "9A. BACK MHA-DT-002 ALONE ON THE MANDREL, ON THE BASE. EDGE-FIND BOTH",
        "   MHA-FR-001 HOLE-TABLE DATUM FACES (SEE ITS PRINT); ZERO DRO X AND Y.",
        "   MIC ONE MHA-DT-026, W; IT GOES AT THE BACK. SET THE STRAP INNER",
        f"   FACE TO Y 70.44-70.63 LESS (W - {BANK_WASHER_THICK:.3f}) AND THE MANDREL",
        "   CENTRE (EDGE-FIND BOTH SIDES, HALVE) TO X 168.11-168.31.",
        "   SPOT MHA-FR-001 THROUGH THE FOOT HOLE WITH AN 11/64 TRANSFER PUNCH;",
        "   LIFT OFF. DRILL #29 X 19.5, TAP #8-32 X 16.0 (PLUG, THEN",
        "   BOTTOMING); BLOW OUT CHIPS. REFIT, RE-SET Y AND X, TIGHTEN",
        "   MHA-VN-032 AND RECHECK.",
        # dtrefactor's #937 review: the loaded mandrel hangs from the back
        # strap alone until the front one goes on (F2), and its front end sits
        # over the front foot hole, where no chuck or tap wrench reaches (F1).
        # So the loaded mandrel leaves the base for the drill and tap.
        "9B. FROM THE FRONT, LOAD THE MICED MHA-DT-026, THE STACK IN ORDER, ITS",
        "   PAIRS HANGING FREE, THEN THE OTHER MHA-DT-026, THEN ONE MHA-VN-052",
        "   THAT SLIDES FREE ON THE MHA-DT-013 BAR (ELSE TAKE ANOTHER). PUSH THE",
        "   BANK BACK, CLOSED UP ON THE BACK MHA-DT-026.",
        "   PROP THE MANDREL FRONT END AT BORE HEIGHT (V-BLOCK ON PARALLELS);",
        "   TAKE THE PROP AWAY ONLY TO SLIDE THE FRONT MHA-DT-002 ON.",
        "9C. SLIDE THE FRONT MHA-DT-002 ON UNTIL A "
        f"{bank.BANK_SPRING_SET:.2f} BLADE BETWEEN ITS STRAP",
        "   AND THE FRONT MHA-DT-026, BESIDE MHA-VN-052, IS LIGHTLY PINCHED. SET",
        "   X 168.11-168.31 AND SPOT AS 9A. SLIDE THE FRONT MHA-DT-002 OFF; DRAW",
        "   THE LOADED MANDREL OUT OF THE BACK MHA-DT-002, HOLDING BOTH",
        "   MHA-DT-026 AND MHA-VN-052, AND LAY IT IN V-BLOCKS ON PARALLELS OFF",
        "   THE BASE, PAIRS HANGING FREE. DRILL AND TAP AS 9A. PASS THE MANDREL",
        "   BACK THROUGH THE BACK MHA-DT-002, PUSH THE BANK BACK AND",
        "   PROP IT AS 9B. REFIT THE FRONT MHA-DT-002; RE-SET THE BLADE AND X, TIGHTEN",
        "   MHA-VN-032, REMOVE THE BLADE AND RECHECK.",
        "9D. MEASURE MHA-DT-002 OUTER FACE TO OUTER FACE. TURN MHA-DT-013: ITS",
        "   CYLINDER IS THAT SPAN, PLUS A 1.5 DOME EACH END (SEE ITS PRINT).",
        "9E. PUSH MHA-DT-013 IN FROM THE BACK, END TO END WITH THE MANDREL, UNTIL",
        "   THE MANDREL IS OUT AND EACH DOME STANDS 1.5 PROUD (DEPTH GAUGE).",
        "   SPOT MHA-DT-013 THROUGH EACH CROWN TAP WITH A #43 DRILL, 0.5 DEEP;",
        "   BLOW OUT CHIPS. RUN THE BACK MHA-VN-034 IN TIGHT, THEN THE FRONT ONE.",
        # #948 ruling R (PR #1292): MHA-VN-052 holds the bank back on its
        # datum, so there is no end play to read; check 3 proves the preload.
        "9F. THE BANK TURNS FREE BY HAND, HELD BACK BY MHA-VN-052.",
        # #936 P1 b, option A (user ruling 2026-09-26): the north MHA-CH-008 ear
        # is the rocker bank's axial datum (rocker_bank_layout), set here on
        # the 9A DRO zero so the cams and the rocker stations share one datum.
        # Y is the hole-table rear-face distance of the ear inner face,
        # BOTTOM_REAR_Z - NORTH_EAR_INNER_Z = 72.039, held to the
        # NORTH_EAR_LOCATE_BAND edge-find. #948 ruling R (PR #1292): the
        # target moves north (LESS Y) by the miced shoulder's excess,
        # S - 1.500, so hub 19 stays at nominal. Channel assembly MHA-CH-000
        # cites this step by key (channel_steps.NORTH_BRACKET_SET_REF).
        f"{steps.step_number(NORTH_BRACKET_SET_KEY)}. MHA-FR-005 SCREWED DOWN ON THE BASE"
        " (FRAME ASSEMBLY MHA-FR-000 STEP 8),",
        "   DRO STILL ZEROED AS 9A. STAND THE NORTH MHA-CH-008 ON THE MHA-FR-005",
        "   RAIL, FOOT TO THE BACK. MIC THE MHA-CH-005 SHOULDER, S. SET ITS EAR",
        "   INNER FACE TO Y 71.94-72.13 LESS "
        f"(S - {pivot_shaft.SHOULDER_LENGTH:.3f});",
        "   CLAMP. DRILL AND TAP THE RAIL THROUGH ITS FOOT PER THE MHA-FR-005 SEAT",
        "   CALLOUT (VIEW B); SCREW IT DOWN AND RECHECK Y.",
        # Main's ruling (option i): the shaft's integral shoulder cannot pass
        # the north ear, so the bracket comes off again and MHA-CH-000 threads
        # the shaft from the north and refits it on these seats, rechecking Y
        # on this DRO zero -- which must survive until its cut-to-fit refit.
        "   UNSCREW IT AND LIFT IT OFF; KEEP THE BASE ON THE MILL, DRO ZEROED,",
        f"   THROUGH {channel_step_ref('shaft-cut-to-fit')}."
        f" {channel_step_ref('north-ear-datum')} REFITS IT OVER THE SHAFT.",
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

# MHA-DT-024's east-west station, in the strap's swing plane (Main's TbPB
# ruling Q2(2) A): the foot hole where the preload gates put it
# (pinion_spring_section), the crest then bearing on the parked flank.  RIG
# SET's pad leaf sets the other axis, along the bank.  The window a fitter
# must hold it in is known issue #1037, which ships this as the interim.
SPRING_EAST_WEST = (
    f"MHA-DT-024 FOOT HOLE CENTRE {SPRING_SCREW_EAST_OF_PIVOT:.1f} EAST OF THE "
    "MHA-DT-019 AXIS, CREST BEARING ON THE PARKED BACK MHA-DT-014 FLANK"
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
        # MHA-DT-033 and the front strap go on first: neither passes the Ø15
        # head or a bonded drum (Codex #860, PRRT_kwDOPHDy386mTbe7).
        ("arbor-collar-pinned", _ARBOR_COLLAR_STEP),
        ("drum-bonded", _DRUM_BOND_STEP),
        ("handle-bonded", _HANDLE_BOND_STEP),
        ("cam-pins-bonded", _CAM_PIN_BOND_STEP),
        (
            "cluster-hung",
            "JOURNAL THE MHA-DT-022 BACK END IN THE BACK MHA-DT-014 TOP BORE; HANG "
            f"BOTH MHA-DT-014 ON MHA-DT-019 THROUGH {pivot_blocks}X MHA-DT-018.",
        ),
        # E-a (user): the straps are pinned to the torque shaft before the
        # cams go on, which leave the pin's west edge 0.38 of air.
        (
            "straps-pinned-to-torque-shaft",
            f"{_SHAFT_DRILL_STEP}\n"
            "THE CLUSTER SWINGS FREELY; MHA-DT-019 TURNS WITH IT IN BOTH MHA-DT-018.",
        ),
        # Main's TbPB ruling (1), 2026-09-27: the set screws stay loose here;
        # COLLAR SET locks them once the collars are set.
        (
            "cams-and-lever-fitted",
            f"FIT {cams}X MHA-DT-023 AND MHA-DT-016 ON MHA-DT-017 IN THE MHA-DT-018 LIFT "
            "BORES, EACH CAM ECCENTRIC DOWN, ITS M2.5 SET SCREW (SUPPLIED WITH "
            "MHA-DT-023) LOOSE. SEAT MHA-DT-016 ON MHA-DT-017 TO THE BORE FLOOR.",
        ),
        # U28 corollary (Main 2026-09-23): the rig's east-west locate is its
        # parked tip gap, on the level line of centres, where block travel
        # equals gap change; the feeler is the bench rest gap, the pins on
        # the cams (pinion_rig_tip_gap).  RIG SET, next, sets it along the
        # bank.
        (
            "rig-located",
            "LOCATE THE RIG ON BASE MHA-FR-001 (FRAME ASSEMBLY MHA-FR-000); ITS SEATS "
            "ARE TRANSFERRED, NOT PRE-DRILLED. SET BOTH MHA-DT-018 LOOSE ON THE "
            f"BASE WITH MHA-DT-024 FITTED: {SPRING_EAST_WEST}. PARK MHA-DT-016: THE "
            "MHA-DT-025 PINS REST ON THE CAMS UNDER THE SPRING. FACE A MHA-DT-001 "
            "TOOTH TIP TO A MHA-DT-012 TOOTH TIP ON THE LEVEL LINE OF CENTRES. "
            f"SLIDE THE RIG IN UNTIL A {TIP_GAP.TIP_GAP_FEELER_TEXT} IS SNUG; "
            f"{TIP_GAP.TIP_GAP_ACCEPT_TEXT}. SET IT AT THE FRONT AND BACK "
            "STATIONS TO SQUARE BOTH MHA-DT-018 TO THE DRUM.",
        ),
        ("rig-set", f"{_RIG_SET_STEP}\nCLAMP BOTH MHA-DT-018."),
        # The seats' drill, tap and depth are the MHA-FR-001 transfer callouts'
        # (build_harmonic_base), so the sheet names the print, never a copy.
        (
            "rig-seats-transferred",
            f"SPOT MHA-FR-001 THROUGH THE {slotted} MHA-DT-018 HOLES AND THE MHA-DT-024 "
            "FOOT HOLE; DRILL AND TAP EACH PER ITS MHA-FR-001 TRANSFER CALLOUT. "
            f"FIT {slotted}X MHA-VN-019 AND 1X MHA-VN-020.",
        ),
        # The cams' phase is set with the lever parked; COLLAR SET then sets
        # each collar along the rod and locks it.
        (
            "cam-collars-set",
            f"MHA-DT-016 AT PARK, EACH CAM ECCENTRIC DOWN;\n{_COLLAR_SET_STEP}",
        ),
        ("lever-pin-set", _LEVER_PIN_STEP),
        (
            "other-base-mounting",
            f"OTHER BASE MOUNTING: SEE SHEET {CHECKS_SHEET}, EXTERNAL INTERFACES.",
        ),
    )
    return "\n".join(
        (RIG_SEQUENCE_HEADING, *(_numbered_step(key, text) for key, text in numbered))
    )


CHECKS = _note_text(
    (
        "ASSEMBLY-ONLY FUNCTIONAL CHECKS",
        "1. CRANK TURNS FREELY THROUGH FULL TURNS; ONE CRANK TURN TURNS THE",
        "   CONE SET 1/4 TURN (16T:64T).",
        # User ruling 2026-09-28: the fixed-centre crank mesh must never bind;
        # no backlash acceptance interval or fit-up target remains.
        "2. MHA-DT-010/MHA-DT-007 TURNS WITHOUT BINDING THROUGH ONE FULL MHA-DT-007",
        "   TURN; EACH CONE GEAR MESHES ITS MHA-DT-012 PER THE MHA-DT-003 PRINT.",
        "3. EACH MHA-DT-012 TURNS FREELY ON MHA-DT-013 WITHOUT AXIAL BINDING.",
        # #948 ruling R (PR #1292): MHA-VN-052 preloads the bank back, so no
        # ring overhangs its cam; the fitter proves the spring holds.
        "   PUSH GEAR 0 TOWARD THE FRONT BY HAND AND RELEASE; THE BANK SPRINGS",
        "   BACK ONTO THE BACK MHA-DT-026.",
        # MHA-VN-015 is the DISENGAGED stop (build_cone_swing_platform
        # swing_hardware_geometry): engaged, the plate edge stands >= 2.0 off
        # it, so the cone set comes back on its meshes, not on the stop.
        "4. CONE SWING (P1): LOOSEN MHA-VN-013; SWING THE CONE SET ON MHA-VN-014 TO",
        "   THE MHA-VN-015 STOP, CLEAR OF EVERY MHA-DT-012. SWING IT BACK UNTIL ALL",
        "   {cone_gears} MESHES RE-ENGAGE; TIGHTEN MHA-VN-013.",
        "5. ZEROING (P2), CONE SET SWUNG CLEAR: TURN EACH MHA-DT-012 BY HAND",
        "   UNTIL ITS NOTCH LINES UP. TURN MHA-DT-016 TO ENGAGE MHA-DT-001; TURN",
        "   MHA-DT-001 BY MHA-DT-015 UNTIL ALL NOTCHES POINT UP (COSINES) OR 90 DEG",
        "   (SINES). RETURN MHA-DT-016 TO PARK; RE-ENGAGE THE CONE SET.",
        "6. PARKED, MHA-DT-024 HOLDS MHA-DT-001 CLEAR OF EVERY MHA-DT-012.",
        f"7. PARKED, PINS ON THE CAMS: A {TIP_GAP.TIP_GAP_FEELER:.2f} FEELER IS SNUG TIP TO TIP",
        f"   AT THE FRONT AND BACK STATIONS; {TIP_GAP.TIP_GAP_ACCEPT_TEXT}",
        f"   (SHEET {FIT_SHEET}, STEP {steps.step_number('rig-located')}).",
    )
)

SETUP_NOTES = _note_text(
    (
        "SAVED POSE AND FREE MOTIONS",
        "SAVED DEFAULT: CONE SET ENGAGED, MHA-DT-001 PARKED CLEAR, CAMS",
        "ECCENTRIC DOWN, CRANK ARM DOWN.",
        "FREE, NEVER LOCKED: CRANK SPIN, CONE-PLATFORM SWING, PINION",
        "SWING, LIFT-ROD/CAM SPIN.",
    )
)

INTERFACE_NOTES = _note_text(
    (
        "EXTERNAL INTERFACES - NOT BOM ITEMS",
        "BASE MHA-FR-001 (FRAME ASSEMBLY MHA-FR-000) RECEIVES MHA-VN-014, MHA-VN-013,",
        "MHA-VN-015, {slotted}X MHA-VN-019, {foot}X MHA-VN-020 AND {hold_down}X MHA-VN-032.",
        "PAPER DRIVE MHA-PD-000: T12 CHAIN WHEEL ON MHA-DT-011.",
        "CHANNEL ASSEMBLY MHA-CH-000: CONNECTING RODS RUN ON THE MHA-DT-012 CAMS.",
    )
)

# Main ruling 2026-09-23 on the Fable C6 finding; ISO VG 32 matches the
# fleet's finish notes.
CONSUMABLES_NOTES = _note_text(
    (
        "GENERAL ASSEMBLY NOTES",
        "OIL THE MHA-DT-012/MHA-DT-013 JOURNALS AND ALL PIVOTS WITH ISO VG 32",
        "MACHINE OIL. NO THREADLOCKER UNLESS A STEP OR PRINT CALLS FOR IT",
        "(LOCTITE 222 ON MHA-DT-032, STEP 7). #4-40, #6-32, #8-32 SCREWS: SNUG.",
    )
)

FIT_PLACEHOLDER = _note_text(
    (
        # U31 (pivot): the bored spacing fixes the mesh; check 2 proves it.
        # The rest of the old placeholder is owned elsewhere now: each cone
        # gear's mesh by the MHA-DT-003 print (check 2), the pinion engagement
        # by the rig-located step and check 7, the taper pin by step 6.
        "16T:64T CENTRE DISTANCE FIXED BY MHA-DT-005 BORE SPACING; VERIFY NO",
        "BINDING THROUGH ONE CRANK TURN (CHECK 2).",
    ),
    heading=False,
)

# User ruling 2026-09-30 (MHA-DT-036 floor 0.5): MHA-DT-036 goes on from the rear
# before MHA-DT-011 enters the bore and MHA-DT-010's pin is match-drilled, so the
# gap is measured in a trial fit without either, at the pinion's feeler and
# the shaft end's mid-window recess; the washer is faced to it and slid on,
# and the parts refitted.  Seated, the washer leaves the feeler as the end
# play, and the recess lands in the window the 16T boss was sized for.
_RECESS_MID = (PINION_RECESS_MIN + PINION_RECESS_MAX) / 2.0
CRANK_WASHER_FIT_NOTES = _note_text(
    (
        f"MHA-DT-036 THRUST WASHER FIT (STEP {steps.step_number('crank-mesh-checked')})",
        "A. TRIAL FIT WITHOUT MHA-DT-036, MHA-DT-010 UNPINNED ON THE "
        f"{PINION_SEAT_FEELER:.2f} FEELER,",
        f"   MHA-DT-011 END {_RECESS_MID:.2f} BELOW MHA-DT-010 NORTH FACE: MEASURE MHA-DT-011 "
        "COLLAR",
        "   REAR FACE TO MHA-DT-005 BOSS SOUTH FACE "
        f"({WASHER_GAP_MIN:.2f}-{WASHER_GAP_MAX:.2f}).",
        "B. WITHDRAW BOTH. FACE MHA-DT-036 TO THAT GAP; SLIDE IT ONTO MHA-DT-011",
        "   FROM THE REAR, FLAT ON THE COLLAR. REFIT MHA-DT-011 AND MHA-DT-010.",
        "C. MHA-DT-036 SEATED ON THE BOSS AND MHA-DT-010 ON THE FEELER: MHA-DT-011 END",
        f"   {PINION_RECESS_MIN:.2f}-{PINION_RECESS_MAX:.2f} BELOW MHA-DT-010 NORTH FACE, "
        f"END PLAY {PINION_SEAT_FEELER:.2f}.",
    )
)

CONE_CRANK_PRIMARY, CONE_CRANK_CONTINUED = _split_sequence_notes(
    CONE_CRANK_STEPS,
    "crank-hub-fitted",
    "ASSEMBLY SEQUENCE CONT. - CRANK",
)
BANK_PRIMARY, BANK_CONTINUED = _split_sequence_notes(
    BANK_STEPS,
    NORTH_BRACKET_SET_KEY,
    "ASSEMBLY SEQUENCE CONT. - NORTH BRACKET",
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
    (#948 ruling R's MHA-VN-052 made the count odd: 28 rows met the view.)"""
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


def instance_counts(instances: Sequence[Instance]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for instance in instances:
        counts[instance.stem] = counts.get(instance.stem, 0) + 1
    return counts


def bom_components(counts: dict[str, int]) -> tuple[str, ...]:
    """The BOM families the model carries, in cluster order."""
    ordered = [stem for stems in CLUSTERS.values() for stem in stems]
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
    """Two-column station table: STN n  MHA-DT-003 Tnnn."""
    half = (len(rows) + 1) // 2
    lines = ["CONE STATION TABLE - MHA-DT-003 BY STATION, FRONT TO BACK"]
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
    placement re-derives them from the measured heading and isometric. Sheet
    6's right field stays empty: it is reserved for D1 (#957).
    """
    heading_lines = len(heading_text(1, ASSEMBLED_HEADING).splitlines())
    cone_gears = facts.count("dt-cone-gear")
    rig_primary, rig_continued = _split_sequence_notes(
        rig_steps(
            pivot_blocks=facts.count("dt-pinion-pivot-block"),
            cams=facts.count("dt-pinion-cam"),
            slotted=facts.count("vn-slotted-screw"),
        ),
        "rig-set",
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
                (
                    "cone and crank sequence",
                    CONE_CRANK_PRIMARY.format(cone_gears=cone_gears)
                    + f"\nCONT. STEP {steps.step_number('crank-hub-fitted')}: "
                    f"SHEET {CONTINUATION_SHEET}.",
                ),
            ),
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
                ("crank fit pointer", f"MHA-DT-036 THRUST WASHER FIT: SHEET {CONTINUATION_SHEET}."),
            ),
        ),
        NoteField(
            CHECKS_SHEET,
            f"sheet {CHECKS_SHEET} left note field",
            NOTE_FIELD_LEFT,
            (("functional checks", CHECKS.format(cone_gears=cone_gears)),),
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
                        slotted=facts.count("vn-slotted-screw"),
                        foot=facts.count("vn-foot-screw"),
                        hold_down=facts.count("vn-pedestal-hold-down-screw"),
                    ),
                ),
            ),
        ),
        NoteField(
            CONTINUATION_SHEET,
            f"sheet {CONTINUATION_SHEET} left note field",
            NOTE_FIELD_LEFT,
            (
                ("crank sequence continuation", CONE_CRANK_CONTINUED),
                ("pinion rig sequence continuation", rig_continued),
            ),
        ),
        NoteField(
            CONTINUATION_SHEET,
            f"sheet {CONTINUATION_SHEET} right note field",
            ISO_RIGHT_FIELD,
            (("crank washer fit", CRANK_WASHER_FIT_NOTES),),
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
    for raw_component in tuple(assembly.GetComponents(True) or ()):
        component = _early_bound(raw_component, "IComponent2")
        name = _component_name(component)
        stem = _component_stem(component)
        total = _early_bound(component.GetTotalTransform(True), "IMathTransform").ArrayData
        base = _early_bound(component.GetTotalTransform(False), "IMathTransform").ArrayData
        if any(abs(float(a) - float(b)) > 1e-9 for a, b in zip(total, base, strict=True)):
            raise RuntimeError(f"drive-train source must open collapsed: {name!r} is displaced")
        origin = tuple(float(value) * 1000.0 for value in tuple(base)[9:12])
        instances.append(Instance(name=name, stem=stem, origin_mm=origin))
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
    and MHA-DT-007's OutsideDiaReference sketch (its 65.15 mm construction tip
    circle, kept for the part print's OD dimension) in every view: about ten
    centerline-font paths per sheet that the old MHA-DT-000 print did not carry.
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
    for view in (front, top, right):
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
    if scale != preferred:
        # Every configuration switch comes before every explode and the BOM
        # (``_place_package``): a step across 1:2 is refused, not switched.
        # The pictorial view is judged shaded-with-edges, as
        # apply_view_configuration judges it.
        if view_configuration(scale, _SW_SHADED_EDGES) != configuration:
            raise RuntimeError(
                f"{label}: {_scale_text(scale)} would move the exploded view off "
                f"{configuration!r}; a configuration switch here dirties the source"
            )
        _set_view_scale(adapter, view, scale, label=label)
        outline = _view_outline(view)
    # The ladder predicted this fit from the preferred outline; the re-read
    # outline is the proof, before any balloon exists.
    shift, overflows, slide = cluster_ring_fit(outline)
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
        anchors=DRIVE_TRAIN_BALLOON_ANCHORS[cluster],
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
    # The right field stays empty: it is reserved for D1 (#957).
    return _stack_sheet_note_fields(adapter, facts, SEQUENCE_SHEET)


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


def _place_continuation_sheet(adapter: Any, facts: SourceFacts) -> list[str]:
    _activate_sheet(adapter, SHEET_NAMES[CONTINUATION_SHEET - 1])
    _heading(adapter, CONTINUATION_SHEET)
    _reference_iso(
        adapter, caption="FINISHED ASSEMBLY 1:8", label="continuation reference isometric"
    )
    return _stack_sheet_note_fields(adapter, facts, CONTINUATION_SHEET)


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
    return scale


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
) -> tuple[dict[str, tuple[float, float]], list[BalloonLanding]]:
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
    findings += _place_bank_sheet(adapter, facts)
    step("bank sheet")
    findings += _place_fit_sheet(adapter, facts)
    step("fit sheet")
    findings += _place_checks_sheet(adapter, facts)
    step("checks sheet")
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
    return package_sheet_scales(cluster_scales, full_detail), landings


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
            sheet_scales, landings = _place_package(adapter, facts, step)

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
