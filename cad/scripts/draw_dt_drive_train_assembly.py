r"""Create the native fourteen-sheet drive-train assembly drawing package (MHA-DT-00).

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

from _assembly_contract import assembly_contract
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
    set_drawing_view_instance_visibility,
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
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DRAWING_TEMPLATES, DrawingLayout
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
from cone_stack_end_play import SHAFT_END_PLAY, STACK_FEELER
import cylinder_bank_layout as bank
import dt_cylinder_bank_setting_spec as bank_settings
from dt_cone_gear_spec import ROUND_BORE_TEETH
from dt_cone_gear_stack import STACK_L20_ACCEPT
from dt_cone_swing_platform_spec import POST_MOUNT_ENGAGEMENT_ASSEMBLY_FACT
import dt_crank_drive_gear_spec as gear64
import dt_crank_handle_pivot_screw_spec as handle_screw
from dt_crank_hub_notes import FRONT_FACE_DATUM as HUB_FRONT_FACE_DATUM
from dt_crank_pin_ring_spec import BUTT_GAP_BAND as RING_BUTT_GAP_BAND
import dt_crank_pinion_spec as pinion
from dt_crank_pinion_spec import SEAT_FEELER_MM as PINION_SEAT_FEELER
from dt_crankshaft_spec import SHAFT_END_PROUD_RANGE as CRANK_END_PROUD_RANGE
from dt_cylinder_end_disc_spec import WASHER_THICK as BANK_WASHER_THICK
import dt_cylinder_gear_spec as drum
import dt_drum_station_setting_spec as drum_station_setting
from dt_pinion_lever_pin_spec import (
    LEVER_NUMBER,
    LEVER_PIN_SET_NAME,
    LEVER_PIN_SET_STEP_KEY,
    LIFT_ROD_NUMBER,
    PIN_NUMBER as LEVER_PIN_NUMBER,
)
from dt_drive_train_assembly_sheet import (
    FEELER_PLACES,
    LEVER_PIN_HOLE_DRILL,
    T120_FITUP_BAND_CHECK,
    T120_FITUP_BAND_REMEDY,
    T120_FITUP_PUSH,
    T120_FITUP_SHOULDER_CHECK,
    T120_FITUP_SHOULDER_REMEDY,
    inch_ceil_mm,
    inch_floor_mm,
    inch_max_text,
    inch_text,
    inch_window,
)
from dt_drive_train_assembly_spec import (
    CLUSTERS,
    COMPONENT_IDENTITIES,
    EXPLODED_VIEW_NAME,
    END_SCREW_ENGAGEMENT_ASSEMBLY_FACT,
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
import dt_pinion_cam_geometry as cam_geometry
from dt_pinion_arbor_geometry import (
    HEAD_CAP_SAG as ARBOR_HEAD_CAP_SAG,
    HEAD_FRONT_Z as ARBOR_HEAD_FRONT_Z,
    HEAD_REAR_Z as ARBOR_HEAD_REAR_Z,
)
from dt_pinion_spring_section import SCREW_EAST_OF_PIVOT as SPRING_SCREW_EAST_OF_PIVOT
import fr_frame_assembly_steps
import fr_harmonic_base_spec as base
import pinion_rig_fitup as FITUP
from pinion_rig_park_geometry import APINION_X
import pinion_rig_tip_gap as TIP_GAP
import rocker_bank_layout as rockers
import dt_vn_cone_lock_knob_spec as lock_knob
import dt_vn_cone_pivot_screw_spec as pivot_screw
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
# The package's sheets, TOL_* rows and model-owned settings print decimal inch
# (#290; the contract's drawing_unit).
UNIT = assembly_contract("dt-drive-train").drawing_unit
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
    "ASSEMBLY SEQUENCE CONT. - CRANK + CYLINDER BANK",
    "ASSEMBLY SEQUENCE CONT. - CYLINDER BANK + PINION RIG",
    "ASSEMBLY SEQUENCE CONT. - PINION RIG + CONE SET ON THE BASE",
    "FULL-DETAIL SIDE VIEW",
    "CHECKS + SETUP",
    "CYLINDER BANK + MHA-DT-01 STATION SETTINGS",
    "SETTING TABLES + CONE STATIONS",
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
# extra sheets as needed").  The rubric sample review of v47 split every step
# into one-thing sub-steps (rule 22), so a field may end inside a step, at a
# lettered sub-step, and its pointer names that sub-step.  The numbered steps
# read in sheet order: 1-3 on sheet 7, 4-6 on sheet 8 (MHA-PD-00 cites 4 and
# 5 there), 7-23 on 9-11 (split at the sub-steps below); the checks follow the
# full-detail view (gate review of 042726e87: the steps jumped 6 -> 11 -> 7 ->
# 8 -> 11).  #2470's two-cure tip bonds outgrew sheet 7, which held 1-5, so
# sheet 8 was added rather than shrinking sheet 7's view (rule 15; Codjiflo
# review of PR #2531).
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
# Step 9D sets the spring gap beside MHA-DT-VN-68 on sheet 14's Detail A.
BANK_SETTINGS_SHEET = 14
# The DRO targets, feeler stacks, pedestal recheck record and the cone
# station table: the sheet the steps and checks read their numbers from.
SETTING_SHEET = 15
# Owner ruling 2026-11-08 (Pedro): one labelled code key defines the cone-gear
# codes and GEAR 0-19 (code_key_text).  It is the sheet 15 station table,
# titled as the key, and every step sheet's first heading points to it.
CODE_KEY_HEADING = f"CODE KEY (SHEETS {SEQUENCE_SHEET}-{CHECKS_SHEET})"
CODE_KEY_POINTER = f"(CODES: SHEET {SETTING_SHEET} KEY)"
BANK_SETTING_SCALE = (1.0, 1.0)
BANK_SPRING_DETAIL_SCALE = (4.0, 1.0)
# 12 mm left of its first seat (0.205): run 20261103T063712849Z's native
# outline audit put the bank's padded right edge (311.0) 5.2 mm into the drum
# station view's (305.7); the column left of the bank is empty.
BANK_SETTING_CENTER = (0.193, 0.195)
BANK_SPRING_DETAIL_CENTER = (0.105, 0.075)
BANK_SPRING_CROP_RADIUS_MM = 8.0
# The bank's settings are labelled on its views, each label naming its
# setting-table row on sheet 15 (rubric sample review of v47: the steps'
# equations needed a labelled sketch).  (text, top-left sheet point, model
# point in mm the leader tip lands on); the spring gap's sits beside Detail A.
# The layout audit boxes a leader note from its text to its tip, so the three
# bank labels stand side by side over the bank, each wholly on its own side
# of the next one's tip (round 1, stacked at one x, overlapped 99 x 47 mm):
# the mandrel label over the back pedestal, right of the Detail A circle's
# letter (x ~103 mm) and under the heading; the disc's left of the front
# pedestal (tip x ~263 mm); the front pedestal's right of it, clear of the
# drum station dimension text (x ~328 mm up).
BANK_SETTINGS_POINTER = f"TARGETS AND STACK LENGTH: SETTING TABLE, SHEET {SETTING_SHEET}."
BANK_SETTING_LABELS = (
    (
        "MANDREL AXIS AT EACH\nMHA-DT-02: DRO X (ROW 3)",
        (0.112, 0.247),
        (cone_line.X_DRUM, bank_settings.AXIS_Y, bank.BACK_STRAP_INNER_Z + 1.0),
    ),
    (
        "MHA-DT-26: MIC ITS\nTHICKNESS, W (ROW 2)",
        (0.200, 0.257),
        (cone_line.X_DRUM, bank_settings.AXIS_Y + 6.0, sum(bank.SOUTH_DISC_Z) / 2.0),
    ),
    (
        "FRONT MHA-DT-02\nINNER FACE:\nDRO Y (ROW 2)",
        (0.274, 0.257),
        (cone_line.X_DRUM, bank_settings.AXIS_Y + 8.0, bank.FRONT_STRAP_INNER_Z - 0.5),
    ),
)
BANK_SPRING_LABEL = (
    "GAP BESIDE MHA-DT-VN-68: FEELER (ROW 4, STEP 9D)",
    (0.145, 0.115),
    (cone_line.X_DRUM, bank_settings.AXIS_Y + 5.0, sum(bank.BANK_SPRING_Z) / 2.0),
)
# Sheet 14's bank and drum views are removed views of parts alone, so each is
# lettered with its scale and named by a viewing arrow on the sheet 1 FRONT
# view (drawing-guidelines rule 9; rubric sample round 2).  Both look from
# the FRONT view's LEFT (model +X, SolidWorks *Right): C runs high on the
# bank, D just under the arbor axis, 42 mm apart in the model (14 mm at 1:3)
# so the two letters clear the layout audit's 7.71 mm row pitch as separate
# blocks (round 3 failed merged-blocks at 8 mm).  Detail A is sheet 14's own
# letter; MHA-FR-05's print owns its VIEW B.
BANK_VIEW_LETTER = "C"
DRUM_VIEW_LETTER = "D"
# Rule 9 (rubric sample round 11): a view label prints its scale only where it
# differs from its sheet's; sheet 14 is at BANK_SETTING_SCALE, so only
# DETAIL A (4:1) carries one.
BANK_VIEW_CAPTION = f"VIEW {BANK_VIEW_LETTER} - CYLINDER BANK ONLY (ARROW: SHEET 1)"
DRUM_VIEW_CAPTION = (
    f"VIEW {DRUM_VIEW_LETTER} - MHA-DT-22 AND MHA-DT-01 ONLY\nPARTIAL (ARROW: SHEET 1)"
)
SHEET1_VIEW_ARROWS = (
    (BANK_VIEW_LETTER, bank_settings.AXIS_Y + 34.0),
    (DRUM_VIEW_LETTER, drum_station_setting.AXIS_Y - 8.0),
)
VIEW_LETTER_HEIGHT = 0.005
# The frame's inner left edge is at 12.4 mm; the FRONT view's outline starts
# near PROJECTED_GROUP_ORIGIN's 24 mm.
VIEW_ARROW_TEXT_X = 0.0145
VIEW_ARROW_MIN_RUN = 0.003
# MHA-DT-22 prints the drum station as a reference; its setting and band live
# on this sheet (dt_drum_station_setting_spec).  A 1:1 *Right view of the
# arbor and drum alone, circle-cropped from the head's front crown to a short
# run of the drum past its front end.  The 1:1 bank's native outline ends at
# x ~299 with its centre at 0.193 (311.0 at 0.205 in run 20261103T063712849Z)
# and the frame's inner edge is at 419.1 mm, so the circle takes that column,
# above the title block (top 65.5 mm).
DRUM_STATION_SETTING_SCALE = (1.0, 1.0)
DRUM_STATION_SETTING_CENTER = (0.364, 0.150)
DRUM_STATION_SETTING_STEMS = frozenset({"dt-pinion-arbor", "dt-alignment-pinion"})
DRUM_STATION_DRUM_RUN_MM = 8.0
DRUM_STATION_CROP_CLEAR_MM = 2.0
# Machine z of the head's front crown apex, in the pose the leg is built in.
DRUM_STATION_HEAD_TIP_Z = drum_station_setting.HEAD_REAR_FACE_Z + (
    ARBOR_HEAD_FRONT_Z - ARBOR_HEAD_CAP_SAG - ARBOR_HEAD_REAR_Z
)
DRUM_STATION_CROP_Z = (
    DRUM_STATION_HEAD_TIP_Z,
    drum_station_setting.DRUM_FRONT_END_Z + DRUM_STATION_DRUM_RUN_MM,
)
DRUM_STATION_CROP_CENTRE_Z = sum(DRUM_STATION_CROP_Z) / 2.0
DRUM_STATION_CROP_RADIUS_MM = (
    (DRUM_STATION_CROP_Z[1] - DRUM_STATION_CROP_Z[0]) / 2.0 + DRUM_STATION_CROP_CLEAR_MM
)
# The value and its three callout lines hang over the circle, as the spring
# detail's do: the text point stands 8 mm of air plus three 5.6 mm callout
# lines above the circle top, so the block clears the boundary even if it
# grows downward from that point.  Its x follows the leg's projected middle.
DRUM_STATION_TEXT_Y = (
    DRUM_STATION_SETTING_CENTER[1] + DRUM_STATION_CROP_RADIUS_MM / 1000.0 + 0.008 + 3 * 0.0056
)
# Sheet 14 reads back every setting spec's model-owned dimension the same way.
SETTING_SPECS = (drum_station_setting,)
SETTING_DIMENSIONS = {
    feature: names for spec in SETTING_SPECS for feature, names in spec.DRAWING_DIMENSIONS.items()
}
SETTING_PRECISION = {
    name: places
    for spec in SETTING_SPECS
    for dimensions in spec.DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
SETTING_CALLOUTS = {
    name: text for spec in SETTING_SPECS for name, text in spec.DIMENSION_CALLOUTS.items()
}
SETTING_BANDS = {
    name: band for spec in SETTING_SPECS for name, band in spec.DIMENSION_BANDS.items()
}

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
# 1:2.5 (rubric sample round 9: the 1:3 cone set and pinion rig read too small
# to tell their parts apart; the magnifier's lever ladder precedent) is still
# Default Simplified, so the step needs no configuration switch.
CLUSTER_SCALE_LADDER: tuple[tuple[float, float], ...] = (
    (2.0, 3.0),
    (1.0, 2.0),
    (1.0, 2.5),
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
# Lowered 16 mm (rubric sample round 3) to give the general notes the
# LOCTITE 638 bond rules rule 23 asks for; its caption still clears the title
# block by ~10 mm.
ASSEMBLED_ISO_CENTER = (0.320, 0.139)
VIEW_CAPTION_GAP = 0.004
# The general notes sit between the heading and the isometric (see
# general_notes_field). Main's last green build measured the isometric's outline
# top at 0.2117 with the centre at 0.155; only the offline budget reads this,
# the placement reads the placed view. The notes clear the view as a caption
# does.
ASSEMBLED_ISO_TOP = 0.2117 - 0.016
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
    "REFERENCE VIEW\n"
    f"BALLOONS ON SHEETS {min(CLUSTER_SHEETS.values())}-{max(CLUSTER_SHEETS.values())}\n"
    "MHA-DT-03 CONE GEAR\n"
    f"STATIONS: SHEET {SETTING_SHEET}"
)

# --- sheets 3-6: exploded cluster views --------------------------------------
CLUSTER_VIEW_CENTER = (0.200, 0.165)
# Top keeps baseline-4's ~5 mm clearance under the two-line sheet heading.
CLUSTER_RING_REGION = (0.020, 0.072, 0.415, 0.248)
# Rubric sample round 9: sheets 4 and 6 printed at 1:3, too small to read.
# Round 12 (20261107T121145212Z, gating 3/3): lowered to 0.030 and slid left
# off the title block, their 1:2.5 and 1:2 rings left each sheet's right half
# empty (rule 15).  Those two now rise instead (raised_ring_fit): the ring
# clears the title block's top and runs up to the frame wherever the sheet
# heading is not.  The bank and crank keep the region their proven sheets fit.
RAISED_RING_CLUSTERS: frozenset[Cluster] = frozenset({"cone-set", "pinion-rig"})
# The frame's inner top edge (12.7 mm in) less the title-block clearance.
RAISED_RING_TOP = DRAWING_TEMPLATES[SPEC.layout].height_m - 0.0127 - BOM_SHEET_CLEARANCE
CLUSTER_RING_REGIONS: dict[Cluster, tuple[float, float, float, float]] = {
    "cylinder-bank": CLUSTER_RING_REGION,
    "cone-set": (CLUSTER_RING_REGION[0], 0.030, CLUSTER_RING_REGION[2], RAISED_RING_TOP),
    "crank": CLUSTER_RING_REGION,
    "pinion-rig": (CLUSTER_RING_REGION[0], 0.030, CLUSTER_RING_REGION[2], RAISED_RING_TOP),
}
# Width of one sheet-heading character: round 12's sheet 4 heading printed
# 67 characters across 170.2 mm (2.54 mm each); this over-reads it 10%.
CLUSTER_HEADING_CHAR_WIDTH = 0.0028
CLUSTER_BALLOON_MARGIN = 0.012
# The raised cone-set ring at 1:2.5 (round 10's 142.8 x 165.0 mm outline) is
# 199 mm tall at the shared margin, more than the 194.7 mm between the title
# block's clearance and RAISED_RING_TOP; its circles sit 8 mm off the outline.
CLUSTER_BALLOON_MARGINS: dict[Cluster, float] = {
    "cylinder-bank": CLUSTER_BALLOON_MARGIN,
    "cone-set": 0.008,
    "crank": CLUSTER_BALLOON_MARGIN,
    "pinion-rig": CLUSTER_BALLOON_MARGIN,
}
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
# Tops sit under the one-line sheet heading at HEADING_XY.  Sheet 7's right
# field (the only user of NOTE_FIELD_RIGHT's foot) runs down to the title
# block's top plus the BOM's paper clearance: PR 2 round 4's one-joint cone
# steps needed its last 3.5 mm (run 20261110T065454309Z printed its foot at
# 75.4 mm with 0.67 line spare over the 65.5 mm title block).
NOTE_FIELD_LEFT = (0.018, 0.252, 0.212, 0.035)
NOTE_FIELD_RIGHT = (
    0.222,
    0.252,
    0.415,
    DRAWING_TEMPLATES[SPEC.layout].title_block_top_m + BOM_SHEET_CLEARANCE,
)
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
# Every sheet's 1:8 reference view sits 7 mm lower than it first did (as sheet
# 12's did first) so the right note fields over it hold two more lines; its
# caption still prints ~3 mm over the title block (rubric sample round 4: the
# one-thing sub-steps outgrew the fields).
REFERENCE_ISO_CENTER = (0.380, 0.103)
# Notes print at 4.525 mm a line (summing-assembly.pdf; this package's telemetry:
# 47 lines measure 212.33 mm).
NOTE_LINE_PITCH = 0.004525
# ~47 lines fit the full left column, ~26 the right one above the 1:8 reference
# view that every sheet needs for its title-block property links
# (finalize_drawing refuses a sheet without a view: r8, leaf
# 20260923T214354Z-1-4126331f). A blank line between numbered steps takes one
# pitch. package_note_fields lists every field, its blocks and where each
# sequence splits.
REFERENCE_ISO_GAP = 0.003
# A 1:8 reference view's outline is ~49 mm tall (its ink ~31 mm square inside
# it, st19 dt-02); this half-extent budgets it both ways.
REFERENCE_ISO_HALF_OUTLINE = 0.0247
ISO_RIGHT_FIELD = (
    NOTE_FIELD_RIGHT[0],
    NOTE_FIELD_RIGHT[1],
    NOTE_FIELD_RIGHT[2],
    REFERENCE_ISO_CENTER[1] + REFERENCE_ISO_HALF_OUTLINE + REFERENCE_ISO_GAP,
)
# Sheet 7's reference view sits under the left column's steps 1-2 (they end
# near y=78 mm), so the right field runs to NOTE_FIELD_RIGHT's foot; its
# caption prints ~9 mm under the outline (~15 mm up), clear of the 12.7 mm
# zone border.  The rule-23 tip dowel steps (owner ruling 2026-11-07, PR
# #2248) lowered it 3 mm and closed its gap to the other sheets'
# REFERENCE_ISO_GAP; PR 2 machinist review round 10's end-screw lock check
# (3F) lowered it one NOTE_LINE_PITCH more (run 20261110T140136846Z: caption
# ink 20.2-23.8 mm up, outline 27.8-78.2 mm).
SEQUENCE_ISO_CENTER = (0.115, 0.0485)
SEQUENCE_ISO_GAP = REFERENCE_ISO_GAP
REFERENCE_ISO_CAPTION_XY = (0.330, 0.082)
SEQUENCE_LEFT_FIELD = (
    NOTE_FIELD_LEFT[0],
    NOTE_FIELD_LEFT[1],
    NOTE_FIELD_LEFT[2],
    SEQUENCE_ISO_CENTER[1] + REFERENCE_ISO_HALF_OUTLINE + SEQUENCE_ISO_GAP,
)
# Sheet 15: the setting, pedestal recheck and feeler stack tables stack down
# the left from NOTE_FIELD_LEFT's top (SETTING_TABLE_LEFT); the cone station
# table prints right of the narrow feeler stack table, under the pedestal
# recheck table (round 1 measured those at x 147.6 mm and y 178.1 mm) and
# clear left of the reference view (x 361 mm up).
# Owner ruling 2026-11-08 (Pedro): the field holds the code key, two lines
# more than the station table it carries (bottom 117 -> 110 mm), and the
# phasing comb's line (machinist review of bd81283964: bottom 110 -> 105.5 mm,
# still 4.5 mm over the interface notes' 101 mm top; run
# 20261110T035403233Z measured the key's bottom at 112.5 mm with 0.6 line
# spare in the 110 mm field).
STATION_TABLE_FIELD = (0.158, 0.172, 0.350, 0.1055)
# The external interfaces print on sheet 15 under the feeler stack table,
# left of the title block (x 216 mm): sheet 13's right field holds the checks
# continuation and saved pose (rubric sample round 4: the one-thing check
# lines outgrew sheet 13).  Round 16's .004 and .020 rows (5.5 mm each, the
# R16 print's pitch) take the table bottom from ~120 to ~109 mm.
INTERFACE_FIELD = (NOTE_FIELD_LEFT[0], 0.101, NOTE_FIELD_LEFT[2], NOTE_FIELD_LEFT[3])
SETTING_TABLE_LEFT = NOTE_FIELD_LEFT[0]
# A general table's cell text runs ~2.8 mm a character at the 3.5 mm note
# font (47 note lines measured 212.33 mm; 70 characters ~194 mm); each column
# is cut to its longest cell plus 2 mm a side.
TABLE_CHAR_WIDTH = 0.0028
TABLE_CELL_PAD = 0.004
TABLE_TITLE_GAP = 0.0015
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
FULL_DETAIL_CAPTION = "GEAR TEETH AND SCREW THREADS AS MODELED (ARROW: SHEET 1)"
# Rubric sample round 4: the full-detail side view is a removed view too, so
# it is lettered and named by an arrow on the sheet 1 TOP view.
FULL_DETAIL_VIEW_LETTER = "E"

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
    "dt-cone-tip-gear": "MHA-DT-37",
    "dt-cone-tip-bushing": "MHA-DT-38",
    "dt-cone-tip-end-screw": "MHA-DT-39",
    "dt-vn-cone-tip-pinch-screw": "MHA-DT-VN-56",
    "dt-vn-cone-tip-block-screw": "MHA-DT-VN-60",
    "dt-vn-locating-pin": "MHA-DT-VN-69",
    "dt-vn-cone-shaft-key": "MHA-DT-VN-71",
    "dt-vn-post-mount-screw": str(_config.parts("dt-vn-post-mount-screw")["number"]),
    "dt-vn-cone-lock-knob": "MHA-DT-VN-51",
    "dt-vn-cone-pivot-screw": "MHA-DT-VN-52",
    "dt-crankshaft": "MHA-DT-11",
    "dt-crank-pinion": "MHA-DT-10",
    "dt-crank-pinion-pin": "MHA-DT-29",
    "dt-crank-arm": "MHA-DT-06",
    "dt-crank-pin": "MHA-DT-09",
    "dt-crank-pin-ring": "MHA-DT-27",
    "dt-vn-keeper-chain": "MHA-DT-VN-65",
    "dt-vn-keeper-chain-screw": "MHA-DT-VN-70",
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
    "dt-cylinder-end-disc": "CYLINDER BANK FRONT END DISC",
    "dt-vn-cylinder-bank-spring": "WAVE DISC SPRING, MCMASTER 9714K392",
    "dt-cylinder-gear": f"CYLINDER GEAR WITH CAM, {drum.TEETH}T",
    "dt-vn-pedestal-hold-down-screw": "#8-32 FILLISTER SCREW, MCMASTER 90280A197",
    "sh-vn-arbor-set-screw": "#4-40 X 1/4 SET SCREW, MCMASTER 91375A106",
    "sh-vn-fillister-screw-90280a108": "#4-40 FILLISTER SCREW, MCMASTER 90280A108",
    "dt-cone-gear-shaft": "CONE GEAR SHAFT",
    "dt-cone-gear": "CONE GEAR, T012-T120 BY 6; 1 EACH",
    "dt-crank-drive-gear": f"CRANK DRIVE GEAR, {gear64.TEETH}T",
    "dt-cone-swing-platform": "CONE SWING PLATFORM",
    "dt-cone-pivot-post": "CONE PIVOT POST AND CRANK COLUMN",
    "dt-cone-tip-block": "CONE TIP BLOCK",
    "dt-cone-tip-gear": "CONE TIP GEAR, 6T WITH SPIGOT AND PIVOT",
    "dt-cone-tip-bushing": "CONE TIP BUSHING",
    "dt-cone-tip-end-screw": "END SCREW, MODIFIED MCMASTER 91794A558",
    "dt-vn-cone-tip-pinch-screw": "#4-40 FILLISTER SCREW, MCMASTER 91794A112",
    "dt-vn-cone-tip-block-screw": "#4-40 X 3/8 SHCS, MCMASTER 91251A108",
    "dt-vn-locating-pin": "1/16 X 3/8 DOWEL PIN, MCMASTER 98381A417",
    "dt-vn-cone-shaft-key": "1/16 SQ KEY STOCK, MCMASTER 98830A511",
    "dt-vn-post-mount-screw": (
        f"{post_screw.THREAD} X {post_screw.STOCK_LENGTH_MM / 25.4:g} FILLISTER STOCK, "
        f"MSC {post_screw.SKU}"
    ),
    "dt-vn-cone-lock-knob": f"{lock_knob.THREAD} THUMB SCREW, MCMASTER 93585A190",
    "dt-vn-cone-pivot-screw": f"{pivot_screw.THREAD} SHOULDER SCREW, MCMASTER 91829A560",
    "dt-crankshaft": "CRANKSHAFT",
    "dt-crank-pinion": f"CRANK PINION, {pinion.TEETH}T",
    "dt-crank-pinion-pin": "CRANK PINION RETENTION PIN",
    "dt-crank-arm": "CRANK ARM",
    "dt-crank-pin": "CRANK TAPER PIN, 1:48",
    "dt-crank-pin-ring": "TAPER PIN KEEPER RING",
    "dt-vn-keeper-chain": "#18 BRASS JACK CHAIN, MCMASTER 3603T354",
    # With "BRASS" the row runs 44 characters, past the column's one-line
    # limit; the registry's material row names the brass.
    "dt-vn-keeper-chain-screw": "#2-56 BINDING HEAD, MCMASTER 92443A077",
    "dt-crank-handle": "CRANK HANDLE",
    "dt-crank-handle-ferrule": "CRANK HANDLE FERRULE",
    "dt-crank-handle-butt-cup": "CRANK HANDLE BUTT CUP",
    "dt-crank-handle-pivot-screw": "CRANK HANDLE PIVOT SCREW",
    "dt-crank-hub": "CRANK HUB",
    "dt-vn-crank-hub-pin": "5/32 X 1/2 DOWEL PIN, MCMASTER 98381A487",
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


def _split_sequence_notes(text: str, number: int | str, heading: str) -> tuple[str, str]:
    """Move a numbered step (or check) -- or, for a lettered head such as
    ``"8K"``, a sub-step -- and everything after it to a continuation field,
    dropping the blank line that separated two numbered steps."""
    head = f"{number}. "
    separator = "\n\n" if str(number).isdigit() else "\n"
    first, found, rest = text.partition(separator + head)
    if not found:
        raise ValueError(f"note block has no head {head!r}")
    return first, f"{heading}\n{head}{rest}"


# DRO-set coordinates print as three-place inch windows rounded inward off the
# owning spec's ±0.10 mm, so the sheet admits no position the spec refuses and
# prints no converted millimetre band (drawing-guidelines rule 4).
FIT_LIMIT_PLACES = 3


def _inward_limits(low: float, high: float) -> str:
    """Print only sizes inside the owning spec's acceptance interval."""
    return inch_window((low, high), FIT_LIMIT_PLACES)


def _plus_w_window(low: float, high: float, nominal_w: float, sign: int) -> str:
    """A DRO window that moves with a micrometered thickness W: the limits
    less (``sign`` +1) or plus (``sign`` -1) the nominal W, rounded inward,
    then printed as ``W + a TO W + b`` or ``a - W TO b - W``."""
    a, b = (
        inch_text(inch_ceil_mm(low - sign * nominal_w, FIT_LIMIT_PLACES), FIT_LIMIT_PLACES),
        inch_text(inch_floor_mm(high - sign * nominal_w, FIT_LIMIT_PLACES), FIT_LIMIT_PLACES),
    )
    return f"W + {a} TO W + {b}" if sign > 0 else f"{a} - W TO {b} - W"


_BANK_X = cone_line.X_DRUM + base.BOTTOM_LENGTH / 2.0
BANK_X_LIMITS = _inward_limits(
    _BANK_X - bank.FRONT_STRAP_LOCATE_BAND, _BANK_X + bank.FRONT_STRAP_LOCATE_BAND
)
# A thick front disc moves its strap to the front, hence PLUS its measured
# excess in the base's rear-face Y coordinate (cylinder_bank_layout).
_FRONT_STRAP_Y = base.BOTTOM_REAR_Z - bank.FRONT_STRAP_INNER_Z
FRONT_STRAP_Y_WINDOW = _plus_w_window(
    _FRONT_STRAP_Y - bank.FRONT_STRAP_LOCATE_BAND,
    _FRONT_STRAP_Y + bank.FRONT_STRAP_LOCATE_BAND,
    BANK_WASHER_THICK,
    +1,
)
# Hub 19 bears on the miced washer against the ear, so the ear moves back
# (LESS Y) by the washer's excess over nominal.
_NORTH_EAR_Y = base.BOTTOM_REAR_Z - rockers.NORTH_EAR_INNER_Z
NORTH_EAR_Y_WINDOW = _plus_w_window(
    _NORTH_EAR_Y - rockers.NORTH_EAR_LOCATE_BAND,
    _NORTH_EAR_Y + rockers.NORTH_EAR_LOCATE_BAND,
    rocker_washer.THICKNESS,
    -1,
)
# The closed gear stack's acceptance, gear 0 cam face to gear 19 back face.
_STACK_LENGTH = bank.G19_BACK_FACE_Z - bank.G0_CAM_FACE_Z
STACK_WINDOW = inch_window(
    (
        _STACK_LENGTH + bank.STACK_L20_ACCEPT_BAND[1],
        _STACK_LENGTH + bank.STACK_L20_ACCEPT_BAND[0],
    ),
    FIT_LIMIT_PLACES,
)
# #2362: the shop owns no 5-6 in micrometer (cad/process/shop.toml gauges),
# but it owns the Mitutoyo 81-piece inch gauge blocks and a DTI
# (shop-equipment.toml): the stack is compared on the DTI with a wrung stack
# of its nominal length, each against one stop, the reading added to it.
STACK_GAUGE_BLOCKS = inch_text(_STACK_LENGTH, 4)
# Step 9D's spring gap is set with one leaf of the rig's STARRETT 66MA gage
# (v47 machinist review: the blade was never identified); the steps print its
# inch size and the feeler-stack table its stamped size.
if round(bank.BANK_SPRING_SET, 2) not in FITUP.FEELER_GAGE_LEAVES_MM:
    raise AssertionError(f"spring set {bank.BANK_SPRING_SET} mm is not one gage leaf")
BANK_SPRING_FEELER = inch_text(bank.BANK_SPRING_SET, FEELER_PLACES)

# --- sheet 15: the setting tables ----------------------------------------------
# Every DRO target the bank steps set, with what to measure first and how to
# check it, prints once here as a table row the steps cite (rubric sample
# review of v47: equations in prose and converted millimetre bands).  The DRO
# is zeroed on the MHA-FR-01 hole-table datum faces at step DRO_ZERO_STEP.
def _step_ref(key: str, letter: str = "") -> str:
    return f"{steps.step_number(key)}{letter}"


SETTING_TABLE_TITLE = (
    "SETTING TABLE - DRO ZEROED ON THE MHA-FR-01 HOLE-TABLE DATUM FACES AT STEP "
    f"{_step_ref('cylinder-stack-accepted', 'P')}; W IS THE PART AS MICED"
)
SETTING_TABLE_HEADER = ("ROW", "STEP", "SETTING", "MEASURE FIRST", "SET TO / ACCEPT", "CHECK WITH")
SETTING_TABLE_ROWS = (
    (
        "1",
        _step_ref("cylinder-stack-accepted", "E"),
        "GEAR 0 CAM FACE TO GEAR 19 BACK FACE",
        "-",
        STACK_WINDOW,
        "DTI ON GAUGE BLOCKS",
    ),
    (
        "2",
        f"{_step_ref('cylinder-stack-accepted', 'Q')}-{_step_ref('cylinder-stack-accepted', 'R')}",
        "FRONT MHA-DT-02 INNER FACE, DRO Y",
        "W = MHA-DT-26 THICKNESS",
        FRONT_STRAP_Y_WINDOW,
        "DRO, EDGE FINDER",
    ),
    (
        "3",
        f"{_step_ref('cylinder-stack-accepted', 'S')}, {_step_ref('cylinder-bank-located', 'E')}",
        "MANDREL CENTRE AT EACH MHA-DT-02, DRO X",
        "-",
        BANK_X_LIMITS,
        "EDGE FINDER, HALVED",
    ),
    (
        "4",
        _step_ref("cylinder-bank-located", "D"),
        "BACK MHA-DT-02 INNER FACE TO GEAR 19",
        "-",
        f"{BANK_SPRING_FEELER} FEELER",
        "LIGHTLY PINCHED",
    ),
    (
        "5",
        _step_ref(NORTH_BRACKET_SET_KEY, "C"),
        "BACK MHA-CH-08 EAR INNER FACE, DRO Y",
        "W = MHA-CH-VN-56 THICKNESS",
        NORTH_EAR_Y_WINDOW,
        "DRO, EDGE FINDER",
    ),
)

# The rig's settings and the bank's spring gap are stacks of the STARRETT
# 66MA metric gage's leaves (pinion_rig_fitup): the steps print each setting's
# inch size, this table the stamped leaves that make it up.
FEELER_STACK_TITLE = f"FEELER STACKS - {FITUP.FEELER_GAGE_NAME} LEAVES"
# Round 16: "LEAVES (MM STAMPED)" leaves the STEPS column room for its CHECK
# cites while the table stays left of the cone station table (x 158 mm).
FEELER_STACK_HEADER = ("SETTING", "LEAVES (MM STAMPED)", "STEPS")


def _nearest_leaf(setting: float) -> float:
    """The one gage leaf that prints as ``setting`` to the thousandth: a
    cone feeler is a stack-derived reading, not a whole leaf step."""
    leaf = min(FITUP.FEELER_GAGE_LEAVES_MM, key=lambda value: abs(value - setting))
    if inch_text(leaf, FEELER_PLACES) != inch_text(setting, FEELER_PLACES):
        raise AssertionError(f"no single leaf prints as {inch_text(setting, FEELER_PLACES)}")
    return leaf


def _feeler_stack_rows() -> tuple[tuple[str, str, str], ...]:
    settings = (
        # Rubric sample round 13 (#4): the cone set's feelers are leaves too.
        (STACK_FEELER, (STACK_FEELER,), _step_ref("cone-gears-stacked", "R")),
        (PINION_SEAT_FEELER, (PINION_SEAT_FEELER,), _step_ref("crank-mesh-checked", "F")),
        (
            FITUP.DRUM_END_SHIM,
            (FITUP.DRUM_END_SHIM,),
            _step_ref("straps-pinned-to-torque-shaft", "B"),
        ),
        (FITUP.FRONT_BLOCK_FEELER, (FITUP.FRONT_BLOCK_FEELER,), _step_ref("rig-set")),
        (FITUP.RIG_SET_LEAF_D, FITUP.RIG_SET_LEAVES, _step_ref("rig-set", "A")),
        (FITUP.SPRING_PAD_LEAF, (FITUP.SPRING_PAD_LEAF,), _step_ref("rig-set", "B")),
        (FITUP.FRONT_COLLAR_LEAF, (FITUP.FRONT_COLLAR_LEAF,), _step_ref("cam-collars-set", "C")),
        (FITUP.BACK_COLLAR_LEAF_F, (FITUP.BACK_COLLAR_LEAF_F,), _step_ref("cam-collars-set", "D")),
        (bank.BANK_SPRING_SET, (bank.BANK_SPRING_SET,), _step_ref("cylinder-bank-located", "D")),
        (
            TIP_GAP.TIP_GAP_FEELER,
            TIP_GAP.TIP_GAP_LEAVES,
            f"{_step_ref('rig-located', 'E')}, CHECK 7",
        ),
    )
    # Rubric sample round 16 (#0, 3/3 runs): the cone set's fit-up and
    # radial-set feelers, printed to the thousandth, each one leaf.
    nearest = (
        (
            pinion.T120_FITUP_FEELER_MM,
            f"{_step_ref('crank-mesh-checked', 'H')}, {_step_ref('crank-mesh-checked', 'J')}",
        ),
        (set_stack.feeler_gap_mm(12), "CHECK 4D"),
        (set_stack.feeler_gap_mm(120), "CHECK 4D, 4M"),
    )
    for setting, leaves, _step in settings:
        if abs(sum(leaves) - setting) > 1e-9:
            raise AssertionError(f"the {inch_text(setting, FEELER_PLACES)} leaves miss it")
    rows: dict[tuple[str, str], list[str]] = {}
    for setting, leaves, step in (
        *settings,
        *((setting, (_nearest_leaf(setting),), step) for setting, step in nearest),
    ):
        key = (
            inch_text(setting, FEELER_PLACES),
            " + ".join(f"{leaf:.2f}" for leaf in sorted(leaves, reverse=True)),
        )
        rows.setdefault(key, []).append(step)
    return tuple(
        (inch, leaves, ", ".join(cited))
        for (inch, leaves), cited in sorted(rows.items(), key=lambda item: float(item[0][0]))
    )


FEELER_STACK_ROWS = _feeler_stack_rows()

# Check 4 re-reads the pedestals after the cone swing's shims: each recorded
# DRO value plus its indicator reading must stay in its setting-table range.
PEDESTAL_RECHECK_TITLE = "PEDESTAL RECHECK (CHECK 4) - FILL IN"
PEDESTAL_RECHECK_HEADER = (
    "PEDESTAL, AXIS", "RECORDED AT", "RECORDED VALUE", "INDICATOR READING", "SUM", "ACCEPT"
)
PEDESTAL_RECHECK_ROWS = (
    ("FRONT MHA-DT-02, X", _step_ref("cylinder-stack-accepted", "Z"), "", "", "", BANK_X_LIMITS),
    ("BACK MHA-DT-02, X", _step_ref("cylinder-bank-located", "Q"), "", "", "", BANK_X_LIMITS),
    ("FRONT MHA-DT-02, Y", _step_ref("cylinder-stack-accepted", "Z"), "", "", "", FRONT_STRAP_Y_WINDOW),
)

# Step 7's bond and release agents, named so the fitter buys the right ones.
HANDLE_EPOXY = "30-MINUTE EPOXY"
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


# Rubric sample round 7 (#3): step 22C's peen on the lever cross pin is
# called out in view E, as the stakes are.  MHA-DT-30's origin is its centre
# on its own axis (build_dt_pinion_lever_pin), which runs along the lift
# rod's pin-hole axis; the side view sees the pin end-on in the MHA-DT-16 hub.
LEVER_PIN_STEM = "dt-pinion-lever-pin"
LEVER_PIN_CENTRE_M = (0.0, 0.0, 0.0)
LEVER_PIN_PEEN_NOTE = "\n".join(
    (
        f"PEEN {LEVER_PIN_NUMBER}",
        "FLUSH BOTH ENDS",
        f"(STEP {steps.step_number(LEVER_PIN_SET_STEP_KEY)}C)",
    )
)
# Round 8's layout audit (run 20261107T055609546Z) measured the MHA-DT-32
# stake note's box to y 132.1 mm on sheet 11 and this note's at y
# 128.7-142.6 mm with a 4 mm rise, 3.3 mm into it; the round 8 evidence PDF
# puts the lever grip's foot at about 147.7 mm right above it.  Risen 8.2 mm,
# its three rows (13.9 mm) stand about 0.9 mm clear of each, 30 mm right of
# the hub; the leader leaves the text's left end and runs back to the pin.
LEVER_PIN_PEEN_NOTE_DX = 0.030
LEVER_PIN_PEEN_NOTE_RISE = 0.0082


def lever_pin_peen_note_xy(tip: tuple[float, float]) -> tuple[float, float]:
    """Top-left sheet point of the peen note for the pin at sheet ``tip``."""
    return (tip[0] + LEVER_PIN_PEEN_NOTE_DX, tip[1] + LEVER_PIN_PEEN_NOTE_RISE)


# Step 10 screws the back MHA-CH-08 down with the channel's own hold-down.
NORTH_BRACKET_SCREW = str(_config.parts("ch-vn-bracket-hold-down-screw")["number"])
# Steps 8A-8C hang each MHA-CH-00 connecting rod and rocker arm pair on its cam by
# their own numbers (rubric sample review of v47: "ROD + ARM PAIR" named no part).
CONNECTING_ROD = str(_config.parts("ch-connecting-rod")["number"])
ROCKER_ARM = str(_config.parts("ch-rocker-arm")["number"])
# The step that sets the channel's rods and rocker arms on the cams (the
# interface notes cite it).
CHANNEL_RODS_SET_AT = _step_ref("cylinder-stack-accepted", "B")
# Step 5's chain wheel is the paper drive's removable sprocket (its T12
# configuration, pd_transgear_removable_spec); the machinist review of
# 8e6a0dbd8 asked for its own number.  The sheet prints no "T12": the code
# key defines TNNN for MHA-DT-03 only (review of 5994f29c83, rule 4).
CRANK_CHAIN_WHEEL = str(_config.parts("pd-transgear-removable")["number"])
PLATEN_NUMBER = str(_config.parts("pd-platen")["number"])
# Steps 1S and 2B's phasing comb is a shop tool in the cone-gear indexing kit, never
# a BOM row (owner rulings 2026-11-09 and 2026-11-10); the code key names it
# and its blade (machinist review of bd81283964: an undefined tool and word).
PHASING_COMB = str(_config.parts("dt-cone-gear-tl-phasing-comb")["number"])


ASSEMBLED_HEADING = (
    f"SAVED WORKING POSE AND FREE MOTIONS: SEE SHEET {CHECKS_SHEET} FOR SETUP.\n"
    "VIEWS 1:2 AND SMALLER OMIT GEAR TEETH AND SCREW THREADS;\n"
    f"FULL DETAIL: SHEET {FULL_DETAIL_SHEET}."
)


def inch_envelope(limits_mm: tuple[float, float], places: int) -> str:
    """A predicted (min, max) stack result the fitter cannot adjust, rounded
    outward so every accepted part set lands inside the printed range."""
    return (
        f"{inch_text(inch_floor_mm(limits_mm[0], places), places)}-"
        f"{inch_text(inch_ceil_mm(limits_mm[1], places), places)}"
    )


# Every step does one thing in six printed lines or fewer, and a check and its
# remedy are separate steps (drawing-guidelines rule 22; rubric sample review
# of v47).  A step's number is the registry's (dt_drive_train_steps, which
# other packages cite); the actions under it are lettered sub-steps 1A, 1B...
# (I and O skipped).  Directions are the sheet 1 FRONT view's: FRONT is the
# crank end (model -Z), BACK the cone tip end, RIGHT model -X.
CONE_CRANK_STEPS = _note_text(
    (
        f"ASSEMBLY SEQUENCE - CONE SET AND CRANK {CODE_KEY_POINTER}",
        # Owner decision C1 keyed (2026-11-09, PR #1992), superseding the
        # 2026-09-28 ruling's "one flat per gear land; no keys, no solder, no
        # retaining compound; no gear bonded": the 64T and T120..T030 drive
        # through MHA-DT-VN-71 in the land-1 keyseat, whose collar end stops
        # the key; T024 is bonded (LOCTITE 638) on the round land 2 one
        # STACK_FEELER off T030, T012 and T018 on MHA-DT-37's spigot and the
        # spigot in MHA-DT-04's socket, all four (T024..T006) phased to the
        # keyed T030 by the MHA-DT-03-TL-02 phasing comb, one blade in a tooth
        # space of each gear (owner rulings 2026-11-09 and 2026-11-10; a shop
        # tool, never in this BOM) engaged inside the compound's fixture time
        # (cone_tip_cluster, cone_stack_end_play;
        # error_budget cone_tip_bond_clock).  The stack is first closed dry,
        # T024 against T030 with no feeler, and measured; MHA-DT-38 is pressed
        # on the loose MHA-DT-37 so the press never loads a bond.  Machinist
        # review round 4 of PR 2 (rule 22): every slide and bond names its
        # mate and makes one joint, and 1B names its range and count.  A
        # keyway goes on its key only one way and 1F measures the stack its
        # gears close; the wrap counts 1B's placeholder at its width.  Codjiflo
        # review of PR 2: the tip's stations come only from closed faces (T018
        # on T024, T012 on T018, MHA-DT-37's leaves on T012; the spigot never
        # bottoms), so 1E and 2A push MHA-DT-37 through that chain to T024.
        "1. SEAT MHA-DT-VN-71 IN THE MHA-DT-04 KEYSEAT, TO ITS COLLAR END.",
        "1A. SLIDE MHA-DT-07 ON MHA-DT-VN-71 AGAINST THE MHA-DT-04 COLLAR.",
        "1B. SLIDE T120 TO T030 ({keyed_gears}X MHA-DT-03) ON, T120 FIRST.",
        "1C. SLIDE T024 ON MHA-DT-04 AGAINST T030, DRY, NO FEELER.",
        "1D. SLIDE T012 AND T018 ON THE MHA-DT-37 SPIGOT, DRY.",
        "1E. PUSH MHA-DT-37 INTO THE MHA-DT-04 SOCKET UNTIL T018 BEARS ON T024.",
        f"1F. MEASURE T120 FRONT TO MHA-DT-37 LEAVES' BACK: ACCEPT {inch_window(STACK_L20_ACCEPT, 3)}.",
        "1G. IF THE STACK IS LONG, RE-FACE ITS THICKEST GEAR.",
        "1H. IF IT IS SHORT, REMAKE ITS THINNEST GEAR.",
        "1J. REPEAT 1F UNTIL THE STACK READS IN ITS WINDOW.",
        "1K. TAKE MHA-DT-37, T018, T012 AND T024 OFF.",
        # Rule 23: the press fit's bench acceptance and its slip-fit remedy.
        "1L. PRESS MHA-DT-38 ON THE MHA-DT-37 PIVOT, AGAINST ITS LEAVES.",
        "1M. CHECK THAT MHA-DT-38 DOES NOT TURN OR SLIDE BY HAND.",
        "1N. IF IT DOES, BOND IT ON WITH LOCTITE 638 PER THE SHEET 1 NOTE.",
        # #2470: T024 slides back along its coated land onto the feeler, so
        # its squeeze-out reaches T030's back face, the leaf and the key's
        # back end, the faces that must stay free for the stack float: they
        # are waxed so the compound cannot hold them.  The joint is degreased
        # first so no solvent carries the wax onto the land (Codjiflo review
        # of PR #2531), and the wax comes off once T024 has cured (as 7E).
        "1P. DEGREASE T024'S BORE AND ITS MHA-DT-04 LAND.",
        f"1Q. COAT T030'S BACK FACE, THE KEY'S BACK END AND THE {inch_text(STACK_FEELER, FEELER_PLACES)} FEELER WITH {HANDLE_RELEASE}, NONE ON THE LAND.",
        # T024 pressed onto the feeler on T030 closes the keyed stack onto the
        # collar, so the feeler sets the stack float (cone_stack_end_play).
        f"1R. BOND T024 ON THE LAND, {inch_text(STACK_FEELER, FEELER_PLACES)} FEELER ON T030, PER THE SHEET 1 NOTE.",
        # Owner ruling 2026-11-10: one comb blade drops in one tooth space of
        # each gear.  T030's keyway centreline runs through its phase-0 tooth
        # (dt_cone_gear_spec), and its blade takes the space beside that tooth,
        # 180/30 deg off the key; the comb goes on only one way round, so the
        # step names the key and the other blades take the bonded gears'
        # spaces at the same time (dt_cone_gear_tl_phasing_comb_spec).  The
        # sheet 15 code key names the comb and its blades (code_key_text).
        # #2470: the bonds cure in two rounds so no joint waits on the others
        # inside the fixture time: T024 alone first (the comb's other blades
        # stand over air), then the spigot's three joints once T024 has cured,
        # since pushing T018 onto T024 loads it.
        f"1S. ENGAGE {PHASING_COMB} AT ONCE, T030'S BLADE BESIDE THE KEY.",
        f"1T. REMOVE {PHASING_COMB} AND THE FEELER ONCE THE BOND GRABS.",
        "1U. AFTER T024'S 24 H CURE, WIPE THE WAX OFF T030 AND THE KEY END.",
        # #2470: T024 cures alone so it is accepted alone, before three wet
        # joints wait on the comb (Codjiflo review of PR #2531); a bonded slip
        # fit has nothing to adjust, so the remedy parts it (drawing-
        # guidelines: about 250 C releases 638) and cleans the cured film out.
        f"1V. CHECK THAT {PHASING_COMB} DROPS INTO T030 AND T024.",
        "1W. IF IT DOES NOT, TAKE T024 OFF AT 250 DEG C.",
        "1X. CLEAN THE CURED 638 OUT OF ITS BORE AND OFF THE LAND.",
        "1Y. REDO FROM 1P.",
        # Step 1 has no letter left for the spigot's round, so it opens step 2,
        # before the post goes on.
        "2. BOND T012 AND T018 ON THE MHA-DT-37 SPIGOT PER THE SHEET 1 NOTE.",
        "2A. BOND MHA-DT-37 IN MHA-DT-04, T018 ON T024, PER THE SHEET 1 NOTE.",
        f"2B. ENGAGE {PHASING_COMB} AT ONCE, T030'S BLADE BESIDE THE KEY.",
        # #2470: the coated spigot seals the blind socket's air in as it
        # enters; held home, the compressed air cannot back T018 off T024
        # before the bonds grab.
        "2C. HOLD MHA-DT-37 HOME, T018 ON T024, UNTIL THE BONDS GRAB.",
        f"2D. REMOVE {PHASING_COMB}.",
        # The cured tip is accepted on the comb; the remedy parts every tip
        # bond, cleans the film off the coated spigot and the pivot too, and
        # redoes the tip from 1M, since the heat also frees a 1N bond on
        # MHA-DT-38 (Codjiflo reviews of PR #2531).
        f"2E. ONCE CURED, CHECK THAT {PHASING_COMB} DROPS INTO ALL FIVE GEARS.",
        "2F. IF IT DOES NOT, TAKE THE BONDED TIP PARTS OFF AT 250 DEG C.",
        "2G. CLEAN THE CURED 638 OFF EVERY PARTED FACE: SPIGOT, PIVOT, LAND, BORES, SOCKET.",
        "2H. REDO FROM 1M.",
        # U37c cut-to-fit acceptance survives the taller post and longer stock:
        # MHA-DT-VN-61's registry/spec own the selected screw and reference length.
        # Each screw is cut against its own matched post/platform hole, never
        # proud of the plate underside. The short-engagement fact includes
        # the stock band, cut allowance and both tap-mouth edge breaks.
        # The sheet states the actual minimum, never the governance label.
        # Rubric sample round 6 (rule 22): the stock is the BOM row's, so the
        # step does one thing.
        "2J. ALIGN THE MHA-DT-05 COUNTERBORES TO THE MHA-DT-20 TAPS.",
        # The exact maximum short the part sheet allows (.005 in = 0.127): a
        # maximum never rounds outward, and the part's places print it whole.
        # Rule 22 (rubric sample round 10 lint): one sentence; the REF cut
        # length and the stated engagement are the cut's own facts.  FLUSH TO
        # .005 SHORT is the never-proud limit (MHA-DT-VN-61's own sheet dropped
        # NEVER PROUD as a restatement; PR 2 round 4 needed its line here).
        "2K. CUT EACH MHA-DT-VN-61 TO FIT, "
        f"({inch_text(post_screw.CUT_LENGTH_MM, post_screw.DRAWING_PRECISION_BY_NAME[post_screw.CUT_LENGTH_DIMENSION])}) "
        "REF LONG: FLUSH TO "
        f"{inch_max_text(post_screw.POST_SCREW_CUT_TO_FIT_SHORT, post_screw.CUT_TO_FIT_SHORT_PLACES)}"
        " SHORT OF THE MHA-DT-20 UNDERSIDE, " + POST_MOUNT_ENGAGEMENT_ASSEMBLY_FACT,
        "2L. DEBURR THE CUT ENDS.",
        "2M. RUN BOTH MHA-DT-VN-61 IN, LOOSE ENOUGH TO TURN MHA-DT-05.",
        # #1074: the collar's bearing on the boss end reacts the end screw's
        # load (#914), and the model mates it (#1058).
        "2N. JOURNAL MHA-DT-04 IN MHA-DT-05 UNTIL ITS COLLAR BEARS ON THE BOSS.",
        # User ruling 2026-09-29 (eight-views-4 photo): MHA-DT-21 is a prism
        # standing directly on MHA-DT-20, held by one #4-40 socket head cap
        # screw up from under the plate through its counterbored hole.
        # Rule-23 retention, owner ruling 2026-11-07 (MHA-DT-00 rubric sample,
        # PR #2248; owner question 2 option 0-A): one Ø1/16
        # MHA-DT-VN-69 dowel, match-drilled from under the plate with the block
        # squared and tight, pressed in the foot's blind ream and a slip fit in
        # the plate's opened ream, stops the block turning about its one screw.
        # The block never comes off: the dowel goes in from below.
        "2P. STAND MHA-DT-21 ON MHA-DT-20, RIGHT FACE SQUARE TO ITS BACK EDGE.",
        "2Q. RUN MHA-DT-VN-60 UP THRU THE MHA-DT-20 COUNTERBORE, SNUG.",
        # Owner decision C1 keyed (2026-11-09, PR #1992): T006's pivot runs in
        # MHA-DT-39's reamed end hole.  Its lateral error is taken up by
        # turning MHA-DT-05 on its screws' clearance (Codex P1 on #1136,
        # 9e9982c5d); its vertical error by MHA-DT-21's AxisHeight, made to
        # MHA-DT-05 (build_dt_drive_train_assembly TIP_LATERAL_CAPACITY_MM /
        # TIP_VERTICAL_CAPACITY_MM).  User decision 2026-10-12: the post is
        # held pushed toward the tip block while it is turned and its screws
        # tightened (dt_cone_tip_air books that).
        "2R. THREAD MHA-DT-39 INTO MHA-DT-21 OVER THE MHA-DT-37 PIVOT.",
        "2S. HOLD MHA-DT-05 PUSHED TOWARD MHA-DT-21 ALONG THE SHAFT THROUGH 2U.",
        "2T. TURN MHA-DT-05 ON ITS SCREWS UNTIL THE MHA-DT-37 PIVOT RUNS FREE.",
        "2U. TIGHTEN BOTH MHA-DT-VN-61 AND MHA-DT-VN-60: THE PIVOT RUNS FREE.",
        "2V. DRILL AND REAM UP THRU MHA-DT-20 INTO MHA-DT-21 PER BOTH CALLOUTS.",
        "2W. PRESS MHA-DT-VN-69 UP THRU MHA-DT-20 TO THE MHA-DT-21 HOLE FLOOR.",
        # Rule 23 (rubric sample round 13, #3): a press that goes in by hand
        # is a slip fit, and the step says what to do then (as 4A-4B).
        "2X. CHECK THAT MHA-DT-VN-69 DOES NOT SLIDE BY HAND.",
        "2Y. IF IT DOES, BOND IT IN WITH LOCTITE 638 PER THE SHEET 1 NOTE.",
        "2Z. CHECK THAT MHA-DT-21 DOES NOT TURN ON MHA-DT-20 BY HAND.",
        # Owner decision C1 keyed (2026-11-09, PR #1992): the end screw sets
        # MHA-DT-04's end play against MHA-DT-38 (cone_stack_end_play
        # SHAFT_END_PLAY: 1/8 turn of 1/4-28 is 0.113) and the pinch screw
        # locks it; 4N's full turn checks the shaft runs free after.  U32
        # (user, 2026-09-23): option 1A turn-set.
        "3. THREAD MHA-DT-39 IN UNTIL MHA-DT-04 JUST STOPS SHUTTLING.",
        f"3A. BACK MHA-DT-39 OFF 1/8 TURN: {END_SCREW_ENGAGEMENT_ASSEMBLY_FACT}",
        "3B. TIGHTEN MHA-DT-VN-56 ACROSS THE SLIT.",
        "3C. DIAL-INDICATE THE MHA-DT-04 END PLAY AT THE SHAFT END: "
        f"{inch_window(SHAFT_END_PLAY, 3)}.",
        "3D. IF THE END PLAY IS OUT, LOOSEN MHA-DT-VN-56.",
        "3E. REPEAT 3-3C UNTIL THE END PLAY READS IN ITS WINDOW.",
        # Rule 23 (PR 2 machinist review round 10): the pinch lock's bench
        # acceptance, worded as 2Z's, once the end play is final.
        "3F. CHECK THAT MHA-DT-39 DOES NOT TURN IN MHA-DT-21 BY HAND.",
        # User ruling 2026-09-28: the crank journal runs directly in the post;
        # the centres are fixed, and the only mesh requirement is no binding.
        # CONTRACT-crank: MHA-DT-VN-67 press to the blind-hole floor.  Owner
        # ruling D1 (2026-10-15): no crank-seat washer -- the collar is held
        # hard on the boss's front face, the 16T set on its feeler off the
        # back face, and only then is its pin match-drilled (4E-4S).
        # User ruling 2026-09-30 (#1154): the 16T's shoulder and turned band
        # are feeler-checked against T120 before the pin is drilled, turning
        # by hand, and the free-running revolution after them (Codex P2 on
        # #1154, review 3).
        "4. PRESS 2X MHA-DT-VN-67 TO THE FLOORS OF THE MHA-DT-11 COLLAR HOLES.",
        # Rule 23 (rubric sample round 5): the press fit's bench acceptance
        # and its slip-fit remedy, the sheet 1 LOCTITE 638 note.
        "4A. CHECK THAT NEITHER MHA-DT-VN-67 TURNS OR PULLS OUT BY HAND.",
        "4B. IF ONE DOES, BOND IT IN WITH LOCTITE 638 PER THE SHEET 1 NOTE.",
        "4C. FIT MHA-DT-11 IN THE MHA-DT-05 CRANK BORE.",
        "4D. SLIDE MHA-DT-10 ON WITHOUT ITS PIN, A TOOTH IN A GAP OF MHA-DT-07.",
        # Owner ruling D1 (2026-10-15): the collar bears on the boss with no
        # washer, the 16T's feeler is the end play, and the shaft end stands
        # proud of the 16T by dt_crankshaft_spec.SHAFT_END_PROUD_RANGE at
        # every accepted part set; it is left as it comes, not faced.  These
        # print in step 4 itself (rubric sample round 4: the separate crank end
        # fit block repeated the step and crowded sheet 10).
        "4E. HOLD MHA-DT-11'S COLLAR HARD ON THE MHA-DT-05 BOSS, NO WASHER.",
        f"4F. SET MHA-DT-10 {inch_text(PINION_SEAT_FEELER, FEELER_PLACES)} OFF THE BOSS BACK FACE "
        "WITH A FEELER.",
        "4G. " + T120_FITUP_PUSH,
        "4H. " + T120_FITUP_BAND_CHECK,
        "4J. " + T120_FITUP_SHOULDER_CHECK,
        "4K. " + T120_FITUP_BAND_REMEDY,
        "4L. " + T120_FITUP_SHOULDER_REMEDY,
        "4M. REPEAT 4E-4J UNTIL THE FEELER PASSES BOTH.",
        "4N. TURN MHA-DT-07 ONE FULL REVOLUTION BY HAND: IT MUST NEVER BIND.",
        # Rubric sample round 4: the bind remedy names what to check and how;
        # round 10 (rule 22): one action, the correction.
        "4P. IF IT BINDS, CORRECT AS 4K-4M WHERE THE 4H-4J FEELER STOPS.",
        "4Q. MATCH-DRILL THE MHA-DT-10 BOSS AT MID-LENGTH INTO MHA-DT-11.",
        # Rule 4 (8a1a516): a standard fit name; the part sheets' shared
        # "LIGHT HAMMER FIT" (pinion.PIN_FIT_LINES) is a drive fit.
        f"4R. REAM TO FIT PIN {pinion.PIN_NUMBER}, A DRIVE FIT.",
        f"4S. TAP {pinion.PIN_NUMBER} IN: {pinion.PIN_FIT_LINES[1]}.",
        "4T. TURN MHA-DT-07 ONE FULL REVOLUTION AGAIN: NO BINDING.",
        "4U. CHECK THAT THE MHA-DT-11 END STANDS "
        # A stack result, not a set window: rounded outward (Codjiflo, #2194).
        f"{inch_envelope((max(CRANK_END_PROUD_RANGE[0], 0.0), CRANK_END_PROUD_RANGE[1]), 3)}"
        " PROUD OF MHA-DT-10.",
        "4V. DO NOT FACE THAT END.",
        f"5. SLIDE {CRANK_CHAIN_WHEEL} ON MHA-DT-11, HOLES OVER THE 2X MHA-DT-VN-67.",
        # U33 (user, 2026-09-23): crank hub MHA-DT-31 pressed into the arm and
        # seam-pinned by MHA-DT-VN-59; the MHA-DT-09 cross-hole runs behind
        # the arm through the hub barrel. The seam's size and depth print
        # once, on MHA-DT-06 and MHA-DT-31.  Pipeline review of 49287772c: the
        # ream's acceptance (the ring clear of the hub) is an assembly setting.
        "6. PRESS MHA-DT-31 INTO MHA-DT-06 TO THE SHOULDER: FACES FLUSH.",
        # Rule 23 (rubric sample round 13, #3): the press's slip-fit remedy.
        "6A. CHECK THAT MHA-DT-31 DOES NOT SLIDE IN MHA-DT-06 BY HAND.",
        "6B. IF IT DOES, BOND IT IN WITH LOCTITE 638 PER THE SHEET 1 NOTE.",
        "6C. MATCH-REAM THE MHA-DT-31/MHA-DT-06 SEAM PIN HOLE PER MHA-DT-31.",
        # FoDtVn1 (#2270): which end goes out moved here from the pin's sheet;
        # the faced cut end stays flush, the supplier's chamfer leads in
        # (dt_vn_crank_hub_pin_spec).
        "6D. DRIVE MHA-DT-VN-59 INTO IT FLUSH, FACED END OUT.",
        # Round 17 (#0): the fit's parts by drawing number.
        "6E. SLIDE MHA-DT-06 ONTO MHA-DT-11: MHA-DT-31 FRONT FACE FLUSH WITH",
        f"   THE {HUB_FRONT_FACE_DATUM}, PUNCH MARKS ALIGNED.",
        # Rule 23 (rubric sample round 14, #0): the step 5 wheel is captured
        # between the MHA-DT-11 seat collar and the MHA-DT-31 hub rear face
        # (build_dt_drive_train_assembly CRANK_HUB_SPROCKET_AIR, open at the
        # SeatCollar band); this is its bench acceptance.  Round 15 (#1, 2/3
        # runs): the 2X MHA-DT-VN-67 stop it turning, so it only slides.
        f"6F. CHECK THAT {CRANK_CHAIN_WHEEL} SLIDES FREELY ON THE 2X MHA-DT-VN-67 WITH END",
        "   PLAY BETWEEN THE MHA-DT-11 COLLAR AND THE MHA-DT-31 HUB.",
        # Round 17 (#2): the ream's functional stop (Main's ruling): the
        # driven pin's MHA-DT-27 ring clears the hub (dt_crank_hub_notes,
        # dt_crank_pin_ring_spec.PIN_PROUD), stated without a typed number.
        "6G. TAPER-REAM 1:48 THRU MHA-DT-31 AND MHA-DT-11 UNTIL MHA-DT-09",
        "   PUSHED IN BY HAND LEAVES ITS MHA-DT-27 RING HOLE CLEAR OF THE HUB.",
        "6H. DRIVE MHA-DT-09, REMOVABLE BY A TAP ON ITS SMALL END.",
        # Owner ruling 2026-11-08 (#2144 item 9.2): one open strand of jack
        # chain, its end link screwed flat to the arm through its eye, the
        # ring closed with pliers through the far link's eye; the cut length
        # prints on MHA-DT-VN-65's own sheet.
        "6J. SCREW THE END LINK OF MHA-DT-VN-65 FLAT TO MHA-DT-06 WITH MHA-DT-VN-70",
        "   THROUGH ITS EYE.",
        # Rule 23 (integration proof run 20261109T062834910Z): the anchor
        # screw's bench acceptance.
        "6K. CHECK THAT MHA-DT-VN-70 IS SEATED AND DOES NOT TURN BY HAND.",
        "6L. THREAD MHA-DT-27 THROUGH THE MHA-DT-09 CROSS-HOLE AND THE FAR LINK'S EYE.",
        "6M. CLOSE MHA-DT-27 WITH PLIERS: BUTT GAP 0-"
        + f"{RING_BUTT_GAP_BAND[1] / 25.4:.3f}".removeprefix("0")
        + ".",
        "6N. HANG MHA-DT-27 FROM THE MHA-DT-09 HEAD: CLEAR OF THE HUB.",
        # Rule 23 (rubric sample round 12, #1): the taper-pinned crank arm's
        # bench acceptance.
        "6P. CHECK THAT MHA-DT-06 DOES NOT TURN OR SLIDE ON MHA-DT-11 BY HAND.",
        # Local review of 747487c71 and owner ruling 2026-10-24 (#1900): the
        # ferrule cures centred on the pivot bore.  Rule 23: the handle spins
        # on the MHA-DT-32 shoulder, so the screw is staked in the arm's
        # through tap (user ruling 2026-10-15); no threadlocker.
        f"7. EPOXY MHA-DT-34 ON THE MHA-DT-08 TENON WITH {HANDLE_EPOXY}.",
        "7A. EPOXY MHA-DT-35 IN THE MHA-DT-08 BUTT THE SAME WAY.",
        f"7B. SLIDE MHA-DT-32 THROUGH BOTH BORES WITH A FILM OF {HANDLE_RELEASE} ON IT.",
        # Rule 23 (rubric sample round 5): the epoxy's cure before load and the
        # bond's bench acceptance.  Round 10 (rule 22): the cure is one action;
        # the centring requirement it carried had no check.
        "7C. LEAVE MHA-DT-32 IN BOTH BORES THROUGH THE 24 H CURE.",
        "7D. CHECK BY HAND THAT NEITHER MHA-DT-34 NOR MHA-DT-35 MOVES.",
        "7E. WIPE THE WAX OFF MHA-DT-32.",
        "7F. SLIDE MHA-DT-08 ON MHA-DT-32.",
        "7G. THREAD MHA-DT-32 INTO MHA-DT-06, NO THREADLOCKER, SHOULDER TIGHT.",
        "7H. CHECK THE MHA-DT-08 END PLAY ON MHA-DT-32 WITH FEELERS: "
        f"{inch_window(handle_screw.END_PLAY_RANGE, 3)}.",
        "7J. FILE THE MHA-DT-32 TIP FLUSH TO THE ARM INBOARD FACE.",
        f"7K. STAKE THE TAP MOUTH ONTO IT AT {HANDLE_STAKE_POINTS} (SHEET {FULL_DETAIL_SHEET}).",
        "7L. CHECK THAT MHA-DT-32 DOES NOT TURN BY HAND.",
        "7M. CHECK THAT MHA-DT-08 SPINS FREE.",
    )
)

# U34c (user/Main 2026-09-23): pedestals inboard, arbor cut to the measured
# strap span, base holes transferred at assembly; x is set on the mill DRO
# against the hole-table datum, since a square cannot resolve the band.  The
# band protects channel accuracy (error_budget axis_dx), not the cone mesh.
# User ruling 2026-10-20: one reduced-OD brass disc on the FRONT strap; back
# spring directly on gear 19.  A thick front disc moves its strap to the
# front, hence W in the front strap's Y; the back pedestal is then set from
# the actual accepted stack on the spring-gap feeler.  The front pedestal's
# location and seat run as 8K-8Z, so step 9D is the spring-gap set (setting
# table row 4, sheet 14 DETAIL A).  Every DRO target is
# a SETTING_TABLE row on sheet 15.
# The DRO zero every later bank and back-ear setting reads from.
DRO_ZERO_STEP = "8P"
BANK_STEPS = _note_text(
    (
        "ASSEMBLY SEQUENCE - CYLINDER BANK",
        # Owner ruling 2026-11-08 (Pedro): GEAR 0-19 are defined in the sheet 7
        # code key (code_key_text), not by a prose line here.
        "8. WRITE DOWN EACH MHA-DT-12'S MICED THICKNESS, CAM FACE TO BACK FACE.",
        # Each connecting rod comes pinned to its rocker arm (MHA-CH-00's
        # bench pinning step, cited by key): its ring is captured in the closed
        # cam slot as the next gear goes on, so the pair travels with its gear.
        # Rubric sample round 5: one gear and one pair per line, then repeat.
        "8A. SLIDE GEAR 0, CAM SIDE FRONT, ONTO A 3/8 GROUND SETTING MANDREL LONG",
        "   ENOUGH TO PASS BOTH MHA-DT-02.",
        f"8B. AS EACH GEAR GOES ON, SET ITS {CONNECTING_ROD} CONNECTING ROD AND {ROCKER_ARM}",
        f"   ROCKER ARM PAIR ({RODS_PINNED_REF}) ON ITS CAM.",
        "8C. REPEAT 8A-8B FOR GEARS 1 TO 19 IN ORDER, ALL ALIKE.",
        "8D. CLAMP THE STACK LIGHTLY END TO END.",
        "8E. MEASURE GEAR 0 CAM FACE TO GEAR 19 BACK FACE ON A DTI AGAINST",
        f"   {STACK_GAUGE_BLOCKS} GAUGE BLOCKS, BOTH ON ONE STOP: ACCEPT {STACK_WINDOW}.",
        "8F. IF LONG, RE-FACE THE THICKEST GEAR'S CAM FACE.",
        "8G. IF SHORT, REMAKE THE THINNEST GEAR.",
        "8H. REPEAT 8D-8E UNTIL THE STACK READS IN ITS WINDOW.",
        "8J. SLIDE THE STACK OFF, GEAR 0 FIRST, EACH GEAR WITH ITS PAIR.",
        # Rubric sample round 9 (rule 22): the base set-up is two actions.
        "8K. PUT BASE MHA-FR-01 ON THE MILL TABLE OUT OF THE FRAME, WITHOUT ITS",
        "   CONE SET (MHA-DT-20).",
        "8L. TRAM THE BASE PAD ON THE TABLE WITH ITS OVERHANG SUPPORTED.",
        "8M. STAND THE FRONT MHA-DT-02 ALONE ON THE MANDREL, ON THE BASE.",
        "8N. EDGE-FIND BOTH MHA-FR-01 HOLE-TABLE DATUM FACES (SEE ITS PRINT).",
        f"{DRO_ZERO_STEP}. ZERO DRO X AND Y THERE.",
        f"8Q. MIC MHA-DT-26: ITS THICKNESS IS W (SETTING TABLE ROW 2, SHEET {SETTING_SHEET}).",
        "8R. SET THE FRONT MHA-DT-02 INNER FACE TO ITS Y (SETTING TABLE ROW 2).",
        "8S. SET THE MANDREL CENTRE TO ITS X (ROW 3), EDGE-FOUND BOTH SIDES.",
        # The seat's drill, tap and depth are the MHA-FR-01 transfer callout's,
        # so the step names the print, never a copy (as the rig's seats do).
        "8T. SPOT MHA-FR-01 THROUGH THE FOOT HOLE WITH AN 11/64 TRANSFER PUNCH.",
        "8U. LIFT THE FRONT MHA-DT-02 OFF.",
        "8V. DRILL AND TAP THE SEAT PER MHA-FR-01 (PLUG, THEN BOTTOMING TAP).",
        "8W. BLOW OUT THE CHIPS.",
        # Check 4 re-reads both coordinates after the cone swing's radial
        # shims move the pedestals.
        "8X. REFIT THE FRONT MHA-DT-02 AT X AND Y.",
        "8Y. TIGHTEN MHA-DT-VN-62.",
        "8Z. WRITE THE DRO X AND Y IN THE PEDESTAL RECHECK TABLE.",
        "9. FROM THE BACK, LOAD THE MICED MHA-DT-26, THEN GEARS 0 TO 19 CAM SIDE",
        "   FRONT WITH THEIR PAIRS HANGING, THEN MHA-DT-VN-68.",
        # One action with its stop condition, not a check and its remedy.
        "9A. STONE ANY BORE BURR THAT DRAGS ON THE MANDREL.",
        # Support the loaded mandrel until the second pedestal replaces the
        # prop; rubric sample round 9 (rule 22): prop, then close the bank.
        "9B. PROP THE MANDREL BACK END AT BORE HEIGHT ON A V-BLOCK.",
        "9C. PUSH THE BANK UNTIL MHA-DT-26 SEATS ON THE FRONT MHA-DT-02.",
        f"9D. SLIDE THE BACK MHA-DT-02 ON IN PLACE OF THE PROP UNTIL A {BANK_SPRING_FEELER} FEELER",
        "   BESIDE MHA-DT-VN-68, BETWEEN ITS INNER FACE AND GEAR 19'S BACK FACE (SHEET",
        f"   {BANK_SETTINGS_SHEET}, DETAIL A), IS LIGHTLY PINCHED.",
        "9E. SET ITS X (SETTING TABLE ROW 3).",
        "9F. SPOT ITS FOOT HOLE AS 8T.",
        # Lift it off before drilling: the mandrel covers that foot's hole.
        "9G. SLIDE THE BACK MHA-DT-02 OFF.",
        "9H. LIFT THE MANDREL AND ITS HANGING PAIRS ONTO V-BLOCKS OFF THE BASE.",
        "9J. DRILL AND TAP THE BACK SEAT AS 8V.",
        "9K. BLOW OUT ITS CHIPS.",
        "9L. PUT THE MANDREL BACK THROUGH THE FRONT MHA-DT-02 AS 9B-9C.",
        "9M. REFIT THE BACK MHA-DT-02 AT THE 9D FEELER AND THE 9E X.",
        "9N. TIGHTEN MHA-DT-VN-62.",
        "9P. REMOVE THE FEELER.",
        "9Q. WRITE THE DRO X IN THE PEDESTAL RECHECK TABLE.",
        # The MHA-FR-01 pivot seat is not cut here on the DRO: step 23
        # transfers it from the MHA-DT-20 pivot bore.
        "9R. MEASURE MHA-DT-02 OUTER FACE TO OUTER FACE.",
        # Round 11: the length plainly, both domes counted.
        f"9S. TURN MHA-DT-13 TO THE 9R SPAN + {inch_text(2.0 * bank.ARBOR_DOME_HEIGHT, 2)} "
        f"({inch_text(bank.ARBOR_DOME_HEIGHT, 2)} DOME EACH END).",
        # Round 18: one line, so the fields keep room for step 23's transfer.
        "9T. PUSH MHA-DT-13 IN FROM THE BACK UNTIL EACH DOME STANDS "
        f"{inch_text(bank.ARBOR_DOME_HEIGHT, 2)} PROUD.",
        "9U. SPOT MHA-DT-13 THROUGH EACH CROWN TAP WITH A #43 DRILL, .02 DEEP.",
        "9V. BLOW OUT THE CHIPS.",
        "9W. RUN THE FRONT MHA-SH-VN-54 IN TIGHT, THEN THE BACK ONE.",
        "9X. CHECK THAT EACH GEAR TURNS FREE BY HAND.",
        # Rule 23 (rubric sample round 12, #0): MHA-DT-13, set in both crowns
        # (9W), ties the two pedestals into one frame on two screws; the
        # bench check covers all three.
        "9Y. CHECK BY HAND THAT MHA-DT-13 AND BOTH MHA-DT-02 DO NOT MOVE.",
        # #936 P1 b, option A (user ruling 2026-09-26): the back MHA-CH-08 ear
        # is the rocker bank's axial datum (rocker_bank_layout), set on the
        # DRO zero so the cams and the rocker stations share one datum.  Hub
        # 19 bears on the back MHA-CH-VN-56 washer against that face (user,
        # 2026-10-10), so the target moves back (LESS Y) by the miced washer's
        # excess.  Channel assembly MHA-CH-00 cites this step by key
        # (channel_steps.NORTH_BRACKET_SET_REF).  The bracket is a one-screw
        # static clamp: 10H is its rule-23 bench check (rubric sample round 9).
        f"{steps.step_number(NORTH_BRACKET_SET_KEY)}. TAKE THE BACK MHA-CH-08, ONE {NORTH_BRACKET_SCREW} AND ONE MHA-CH-VN-56",
        "   FROM MHA-CH-00 (MHA-FR-05 IS ON THE BASE, "
        f"{fr_frame_assembly_steps.step_ref(fr_frame_assembly_steps.SUPPORT_SCREWED_KEY)}).",
        f"{steps.step_number(NORTH_BRACKET_SET_KEY)}A. STAND THE MHA-CH-08 ON THE MHA-FR-05 RAIL, FOOT TO THE BACK.",
        f"{steps.step_number(NORTH_BRACKET_SET_KEY)}B. MIC THE MHA-CH-VN-56: ITS THICKNESS IS W (SETTING TABLE ROW 5).",
        f"{steps.step_number(NORTH_BRACKET_SET_KEY)}C. SET THE EAR INNER FACE TO ITS Y (SETTING TABLE ROW 5, {DRO_ZERO_STEP} ZERO).",
        f"{steps.step_number(NORTH_BRACKET_SET_KEY)}D. CLAMP IT.",
        f"{steps.step_number(NORTH_BRACKET_SET_KEY)}E. DRILL AND TAP THE RAIL THROUGH THE FOOT PER MHA-FR-05 VIEW B.",
        f"{steps.step_number(NORTH_BRACKET_SET_KEY)}F. SCREW THE MHA-CH-08 DOWN WITH THE {NORTH_BRACKET_SCREW}.",
        f"{steps.step_number(NORTH_BRACKET_SET_KEY)}G. RECHECK Y.",
        f"{steps.step_number(NORTH_BRACKET_SET_KEY)}H. CHECK THAT THE MHA-CH-08 DOES NOT TURN ON MHA-FR-05 BY HAND.",
        f"{steps.step_number(NORTH_BRACKET_SET_KEY)}J. KEEP THAT MHA-CH-VN-56 FOR THE BACK END OF "
        f"{channel_step_ref('north-ear-datum')}.",
    )
)

RIG_SEQUENCE_HEADING = "ASSEMBLY SEQUENCE CONT. - PINION RIG"

# The rig's own assembly steps are pinion_rig_fitup's (Codex #858,
# PRRT_kwDOPHDy386mTbPB): each part step, SHAFT DRILL SET, RIG SET and
# COLLAR SET print here, re-wrapped to the field, and every other sheet cites
# them by registry key.  Where a spec's paragraph joins two actions or carries
# a reason, the sheet re-breaks or re-words it (RIG_REWORDINGS; rule 22,
# rubric sample round 9); each replaced phrase must still be the spec's, so
# the two cannot drift.  Unpacking fails loud if the fit-up sequence gains or
# loses a step.
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

# MHA-DT-24's left-right station, in the strap's swing plane (Main's TbPB
# ruling Q2(2) A): the foot hole where the preload gates put it
# (pinion_spring_section; model -X, the sheet 1 FRONT view's RIGHT), the crest
# then bearing on the parked flank.  RIG SET's pad leaf sets the other axis,
# along the bank.  The window a fitter must hold it in is known issue #1037,
# which ships this as the interim.
SPRING_EAST_WEST = (
    f"FOOT HOLE CENTRE {inch_text(SPRING_SCREW_EAST_OF_PIVOT, 2)} RIGHT OF THE MHA-DT-19 AXIS"
)

# Sub-step letters: I and O are skipped, as on drawing zones.
_SUB_STEP_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ"


def _flat(text: str) -> str:
    """One paragraph of a part spec's soft-wrapped step text."""
    return " ".join(text.split())


def _reworded(text: str, *edits: tuple[str, str]) -> str:
    """A part spec's step with each ``(old, new)`` phrase replaced: a re-break
    (``new`` starts a sub-step line with ``\\n``) or a dropped reason.  Each
    ``old`` must occur exactly once in ``text``, so a spec that stops printing
    it fails loud rather than drifting from this sheet."""
    for old, new in edits:
        if text.count(old) != 1:
            raise AssertionError(f"part step does not print {old!r} once: {text!r}")
        text = text.replace(old, new)
    return text


# Rubric sample round 9 (rule 22): the pinion_rig_fitup paragraphs this sheet
# re-breaks into one action a line or strips of a design reason, keyed by
# step.  The specs keep their own wording; the sheets that cite them cite
# the step number only.
RIG_REWORDINGS: dict[str, tuple[tuple[str, str], ...]] = {
    # MHA-DT-33 and the front strap go on first: neither passes the Ø15
    # head or a bonded drum (Codex #860, PRRT_kwDOPHDy386mTbe7).
    "arbor-collar-pinned": (
        # Rubric sample round 13 (rule 26): "the drum bond" was a private label.
        ("BEFORE THE DRUM BOND: ", f"BEFORE STEP {steps.step_number('drum-bonded')}: "),
        ("PIN STATION; DRIVE ", "PIN STATION.\nDRIVE "),
        ("THRU BOTH, BOTH ENDS SUB-FLUSH AND", "THRU BOTH: BOTH ENDS SUB-FLUSH,"),
        ("OF EACH OTHER; THEN SLIDE ", "OF EACH OTHER.\nSLIDE "),
    ),
    # The drum is bonded to the setting MHA-DT-22 prints only as a REF:
    # bond, set the station, wipe.  Round 13: the station is named by its
    # view, not as "the drum station".
    "drum-bonded": (
        (
            "SLIDE MHA-DT-22 INTO MHA-DT-01 AND BOND WITH LOCTITE 638, DRUM FRONT END "
            "AT THE DRUM STATION SETTING; WIPE",
            "BOND MHA-DT-22 INTO MHA-DT-01 WITH LOCTITE 638.\n"
            f"AT ONCE, SET MHA-DT-01 AT ITS VIEW {DRUM_VIEW_LETTER} STATION (SHEET "
            f"{BANK_SETTINGS_SHEET}).\nWIPE",
        ),
    ),
    # The bond and its acceptance are two steps.
    "handle-bonded": (
        (
            "; INSTALLED ROD SHALL NOT TURN OR SLIDE BY HAND.",
            ".\nAFTER THE CURE, CHECK THAT MHA-DT-15 DOES NOT TURN OR SLIDE BY HAND.",
        ),
    ),
    # The pin's position is the instruction; why it bears is not.
    # Round 19: 16C on one line (the possessive, as 21A), so step 23 has room.
    "straps-pinned-to-torque-shaft": (
        (", SO IT BEARS IN BOTH MHA-DT-18 AND CLEARS MHA-DT-16.", "."),
        (
            "SET THE MHA-DT-19 REAR END FLUSH WITH THE MHA-DT-18 REAR FACE ",
            "SET MHA-DT-19'S REAR END FLUSH WITH MHA-DT-18'S REAR FACE ",
        ),
    ),
}


def _numbered_step(key: str, text: str) -> str:
    """Print a step with its registry head: each further line of ``text`` is
    one sub-step, lettered 1A, 1B... (drawing-guidelines rule 22)."""
    number = steps.step_number(key)
    first, *rest = text.splitlines()
    return _note_text(
        (
            f"{number}. {first}",
            *(f"{number}{_SUB_STEP_LETTERS[index]}. {line}" for index, line in enumerate(rest)),
        ),
        heading=False,
    )


def rig_steps(*, pivot_blocks: int, cams: int, slotted: int) -> str:
    """The pinion rig's steps, counted from the built assembly."""
    reworded = {
        key: _reworded(text, *RIG_REWORDINGS[key])
        for key, text in (
            ("arbor-collar-pinned", _flat(_ARBOR_COLLAR_STEP)),
            ("drum-bonded", _flat(_DRUM_BOND_STEP)),
            ("handle-bonded", _flat(_HANDLE_BOND_STEP)),
            # A multi-line spec step: its lines are already one-thing lines.
            ("straps-pinned-to-torque-shaft", _SHAFT_DRILL_STEP),
        )
    }
    numbered = (
        ("arbor-collar-pinned", reworded["arbor-collar-pinned"]),
        ("drum-bonded", reworded["drum-bonded"]),
        ("handle-bonded", reworded["handle-bonded"]),
        ("cam-pins-bonded", _flat(_CAM_PIN_BOND_STEP)),
        (
            "cluster-hung",
            "JOURNAL THE MHA-DT-22 BACK END IN THE BACK MHA-DT-14 TOP BORE.\n"
            f"HANG BOTH MHA-DT-14 ON MHA-DT-19 THROUGH {pivot_blocks}X MHA-DT-18.",
        ),
        # E-a (user): the straps are pinned to the torque shaft before the
        # cams go on, which leave the pin's left edge 0.38 of air.
        (
            "straps-pinned-to-torque-shaft",
            f"{reworded['straps-pinned-to-torque-shaft']}\n"
            # Rubric sample round 13 (rule 26): "the cluster" named no parts.
            "CHECK THAT MHA-DT-19 AND BOTH MHA-DT-14 SWING FREELY AS ONE IN BOTH "
            "MHA-DT-18.",
        ),
        # Main's TbPB ruling (1), 2026-09-27: the set screws stay loose here;
        # the cam set tightens and stakes them once the cams are set (#1176).
        (
            "cams-and-lever-fitted",
            f"FIT {cams}X MHA-DT-23 AND MHA-DT-16 ON MHA-DT-17 IN BOTH MHA-DT-18.\n"
            "TURN EACH CAM ECCENTRIC DOWN.\n"
            "LEAVE EACH CAM'S #2-56 SET SCREW (SUPPLIED WITH MHA-DT-23) LOOSE.\n"
            "SEAT MHA-DT-16 ON MHA-DT-17 TO THE BORE FLOOR.",
        ),
        # U28 corollary (Main 2026-09-23): the rig's left-right locate is its
        # parked tip gap, on the level line of centres, where block travel
        # equals gap change; the feeler is the bench rest gap, the pins on
        # the cams (pinion_rig_tip_gap).  RIG SET, next, sets it along the
        # bank.
        # Rubric sample round 9 (rule 22): the locate is one action a line.
        (
            "rig-located",
            "STAND BOTH MHA-DT-18 LOOSE ON BASE MHA-FR-01 (FRAME ASSEMBLY MHA-FR-00) OVER "
            "THEIR UNDRILLED SEATS.\n"
            f"STAND MHA-DT-24 ON THE BASE WITH ITS {SPRING_EAST_WEST}.\n"
            "TURN MHA-DT-24 ABOUT ITS FOOT HOLE UNTIL ITS CREST BEARS ON THE PARKED BACK "
            "MHA-DT-14 FLANK.\n"
            "PARK MHA-DT-16: THE MHA-DT-25 PINS ON THE CAMS UNDER THE SPRING.\n"
            "TURN MHA-DT-01 SO A TOOTH TIP FACES A MHA-DT-12 TOOTH TIP ON THE LEVEL "
            "LINE OF CENTRES.\n"
            f"SLIDE THE RIG IN UNTIL A {TIP_GAP.TIP_GAP_FEELER_TEXT} IS SNUG "
            f"BETWEEN THE TIPS: {TIP_GAP.TIP_GAP_ACCEPT_TEXT}.\n"
            f"SET THE TIP GAP AS {steps.step_number('rig-located')}D-"
            # Round 15 (#2, rule 26): the stations by gear (sheet 8's key).
            f"{steps.step_number('rig-located')}E AT GEAR 0 AND AT GEAR 19.",
        ),
        ("rig-set", f"{_RIG_SET_STEP}\nCLAMP BOTH MHA-DT-18."),
        # The seats' drill, tap and depth are the MHA-FR-01 transfer callouts'
        # (build_harmonic_base), so the sheet names the print, never a copy.
        # Rubric sample round 13 (#0, rule 22): as the bank does at 8U-8X, the
        # rig and spring come off for the drilling, go back at their 18-19
        # settings, and those settings are rechecked once screwed down.
        (
            "rig-seats-transferred",
            f"SPOT MHA-FR-01 THRU {slotted} MHA-DT-18 HOLES AND THE MHA-DT-24 FOOT HOLE.\n"
            "LIFT THE RIG AND MHA-DT-24 OFF THE BASE.\n"
            "DRILL AND TAP EACH SEAT PER ITS MHA-FR-01 TRANSFER CALLOUT.\n"
            f"REFIT THE RIG AND MHA-DT-24 AT THE {steps.step_number('rig-located')}B-"
            f"{steps.step_number('rig-set')}B SETTINGS.\n"
            f"FIT {slotted}X MHA-DT-VN-57 AND 1X MHA-SH-VN-52 AT THE SPRING FOOT.\n"
            f"RECHECK THE {steps.step_number('rig-located')}E TIP GAP AND THE "
            f"{steps.step_number('rig-set')}-{steps.step_number('rig-set')}B LEAVES.\n"
            "IF ONE IS OUT, RESET IT AS CHECKS 7A-7E.",
        ),
        # The cams' phase is set with the lever parked; the cam set then sets
        # each cam along the rod, tightens its set screw and stakes the tap.
        (
            "cam-collars-set",
            f"PUT MHA-DT-16 AT PARK, EACH CAM ECCENTRIC DOWN.\n{_COLLAR_SET_STEP}",
        ),
        # Rubric sample round 4: the hole's station, drill and fit read before
        # the match-drill, insert and peen lines that use them.
        (
            "lever-pin-set",
            # Rubric sample round 6 (rule 22): the hole's drill and station
            # fold into the match-drill action; insert, trim and peen are
            # one thing each.  Round 9 (rule 23): the cross pin's bench check.
            f"{LEVER_PIN_SET_NAME}, GRIP PARKED: MATCH-DRILL {LEVER_PIN_HOLE_DRILL} THRU "
            f"{LEVER_NUMBER}'S HUB AT ITS PRINTED STATION AND {LIFT_ROD_NUMBER} TOGETHER.\n"
            f"INSERT {LEVER_PIN_NUMBER}, A SLIDING FIT.\n"
            "TRIM BOTH ENDS.\n"
            f"PEEN BOTH ENDS FLUSH WITH THE HUB (SHEET {FULL_DETAIL_SHEET}).\n"
            f"CHECK THAT {LEVER_NUMBER} DOES NOT TURN OR SLIDE ON {LIFT_ROD_NUMBER} BY HAND.",
        ),
        # Owner ruling 2026-11-08 (Pedro): step 23 trusts the transfer
        # through the MHA-DT-20 reamed pivot bore, with the cone set at its
        # working position (the check 4D leaves): punch, lift off, spot-drill,
        # drill and tap.  The swing check (23J) is the only acceptance, and
        # DT-00 prints no offset from the pedestal seats (FoFr #2261 owns D1
        # as a transfer).  The stop and lock seats are MHA-FR-01 print holes.
        # Check 4 then sets the swing and clamps it.  PR 2 machinist review
        # round 6 (clarity): a seated screw's engagement cannot be read, so
        # each blind seat's full-thread depth and its screw's thread length
        # are recorded before the screw goes in; checks 4U and 4W take the
        # lesser of the two.
        (
            "other-base-mounting",
            "CONE SET ON THE BASE: SET MHA-DT-20 ON THE CHECK 4D FEELER LEAVES.\n"
            "CLAMP MHA-DT-20 TO MHA-FR-01.\n"
            "TRANSFER-PUNCH MHA-FR-01 THRU THE MHA-DT-20 PIVOT BORE.\n"
            "LIFT MHA-DT-20 AND THE LEAVES OFF.\n"
            "SPOT-DRILL THE PUNCH MARK.\n"
            f"DRILL AND TAP {pivot_screw.THREAD} THERE PER MHA-FR-01.\n"
            "RECORD THE TAPPED HOLE'S FULL-THREAD DEPTH WITH A DEPTH GAUGE.\n"
            "RECORD MHA-DT-VN-52'S THREAD LENGTH WITH CALIPERS.\n"
            "RUN OILED MHA-DT-VN-52 THRU MHA-DT-20 UNTIL ITS SHOULDER SEATS.\n"
            "CHECK THAT MHA-DT-20 SWINGS FREELY UNDER THE HEAD.\n"
            "RECORD THE STOP SEAT'S FULL-THREAD DEPTH WITH A DEPTH GAUGE.\n"
            "RECORD MHA-SH-VN-52'S THREAD LENGTH WITH CALIPERS.\n"
            "RUN THE MHA-SH-VN-52 SWING STOP INTO MHA-FR-01 UNTIL IT SEATS.\n"
            "SWING THE CONE SET IN.\n"
            "RUN MHA-DT-VN-51 IN FINGER-LOOSE THRU THE MHA-DT-20 NOTCH.",
        ),
    )
    # One blank line between the rig's numbered steps, as _note_text does.
    return "\n".join(
        (
            RIG_SEQUENCE_HEADING,
            FEELER_TABLE_NOTE,
            "",
            "\n\n".join(_numbered_step(key, text) for key, text in numbered),
        )
    )


# Each feeler the rig steps and checks print is a stack of gage leaves the
# sheet 15 table lists (rubric sample review of v47: no mm in the steps).
# Step 11's "PIN STATION" is MHA-DT-33's part-spec wording; the arbor's print
# dimensions it as the COLLAR PIN hole (rubric sample round 2: undefined term).
FEELER_TABLE_NOTE = _note_text(
    (
        # Round 16 (#0): package-wide, not only the rig's.
        f"ALL SET FEELERS AND SHIMS: {FITUP.FEELER_GAGE_NAME} LEAF STACKS, SHEET "
        f"{SETTING_SHEET} TABLE.",
        f"PIN STATION (STEP {steps.step_number('arbor-collar-pinned')}): THE MHA-DT-22 COLLAR "
        "PIN HOLE (SEE ITS PRINT).",
    ),
    heading=False,
)

_T120_SET_FEELER = inch_text(set_stack.feeler_gap_mm(120), FEELER_PLACES)

CHECKS = _note_text(
    (
        f"ASSEMBLY-ONLY FUNCTIONAL CHECKS {CODE_KEY_POINTER}",
        # Rubric sample round 9 (rule 22): one check a line.
        "1. THE CRANK TURNS FREELY THROUGH FULL TURNS.",
        f"1A. ONE CRANK TURN TURNS THE CONE SET {Fraction(pinion.TEETH, gear64.TEETH)} TURN "
        f"({pinion.TEETH}T:{gear64.TEETH}T).",
        # User ruling 2026-09-28: the fixed-centre crank mesh must never bind;
        # no backlash acceptance interval or fit-up target remains.
        "2. MHA-DT-10/MHA-DT-07 TURNS WITHOUT BINDING THROUGH ONE FULL MHA-DT-07",
        "   TURN.",
        "2A. MHA-DT-07 CLEARS THE UNRELIEVED MHA-DT-20 TOP THROUGH THAT TURN.",
        # Round 17 (#3): the mesh is set and accepted in check 4.
        "2B. EACH CONE GEAR MESHES ITS MHA-DT-12 PER CHECKS 4D, 4M AND 4S.",
        "3. EACH MHA-DT-12 TURNS FREELY ON MHA-DT-13 WITHOUT AXIAL BINDING.",
        # Prove the reversed preload seats on the front disc.
        "3A. PUSH GEAR 0 TOWARD THE BACK BY HAND AND RELEASE: THE BANK SPRINGS",
        "   BACK ONTO THE FRONT MHA-DT-26.",
        # MHA-SH-VN-52 is the DISENGAGED stop (build_cone_swing_platform
        # swing_hardware_geometry): engaged, the plate edge stands >= 2.0 off
        # it. The engaged mesh is SET here with MHA-DT-VN-51, not by the stop:
        # cone_set_stack (user ruling 2026-10-10). The shims line MHA-DT-13
        # up with the cone line before the pedestals tighten (Main ruling:
        # pedestal term booked at zero), then T120 is set on its feeler.  The
        # shims may move each pedestal only inside its setting-table range, so
        # stand (#1691 review r4).  Backing the swing off would undo the T120
        # set (#1691 review r2), so a T012 bind is cleared at the MHA-DT-12
        # tip that marks (owner ruling 2026-11-08 (Pedro), option B).
        "4. CONE SWING SET: LOOSEN MHA-DT-VN-51.",
        "4A. SWING THE CONE SET ON MHA-DT-VN-52 OUT TO THE MHA-SH-VN-52 STOP.",
        "4B. ZERO DIAL INDICATORS: EACH MHA-DT-02 IN X, THE FRONT ONE IN Y.",
        "4C. EASE MHA-DT-VN-62 UNTIL EACH MHA-DT-02 MOVES UNDER LIGHT TAPS.",
        "4D. SWING IN ON FEELER LEAVES, TIP TO MHA-DT-12 ROOT: "
        f"{inch_text(set_stack.feeler_gap_mm(12), FEELER_PLACES)} AT T012, "
        f"{_T120_SET_FEELER} AT T120.",
        "4E. TIGHTEN MHA-DT-VN-62.",
        "4F. FILL IN THE PEDESTAL RECHECK TABLE (SHEET "
        f"{SETTING_SHEET}): EACH RECORDED VALUE PLUS ITS INDICATOR READING MUST BE IN "
        "ITS ACCEPT RANGE.",
        "4G. IF A PEDESTAL IS OUT, EASE ITS MHA-DT-VN-62.",
        "4H. RESET IT INTO ITS ACCEPT RANGE ON ITS INDICATORS.",
        "4J. TIGHTEN ITS MHA-DT-VN-62.",
        "4K. SWING THE CONE SET OUT.",
        "4L. REMOVE THE LEAVES.",
        f"4M. SWING IN UNTIL A {_T120_SET_FEELER} FEELER IS SNUG T120 TIP TO ROOT.",
        "4N. TIGHTEN MHA-DT-VN-51 WITH THE CONE SET HELD THERE.",
        # Rule 23 (rubric sample round 5): the adjustable clamp's acceptance.
        "4P. PUSH THE CONE SET BY HAND: IT DOES NOT SWING, AND THE "
        f"{_T120_SET_FEELER} FEELER AT T120 IS STILL SNUG.",
        # Rubric sample round 9 (rule 22): the hold, the redo, the T012 check
        # and its remedy are one step each.
        "4Q. LEAVE MHA-DT-02 AND THE T120 SET AS THEY ARE FROM HERE ON.",
        "4R. REDO CHECKS 4-7 AFTER ANY LATER LOOSENING OF MHA-DT-02.",
        # Owner ruling 2026-11-08 (Pedro), option B: 4S prints the running
        # acceptance only; the gate is the RSS corner (test_standard_mesh_checks).
        f"4S. TURN THE CRANK {gear64.TEETH // pinion.TEETH} FULL TURNS: T012 MUST RUN FREE IN ITS "
        "MHA-DT-12.",
        "4T. IF IT BINDS, STONE THE MHA-DT-12 TIP WHERE IT MARKS.",
        "4U. VERIFY MHA-DT-VN-52 FULL-FORM THREAD ENGAGEMENT "
        f"{pivot_screw.MIN_USEFUL_ENGAGEMENT_TEXT}: THE LESSER READING OF STEPS "
        f"{_step_ref('other-base-mounting', 'F')}-{_step_ref('other-base-mounting', 'G')}.",
        "4V. CHECK THAT MHA-DT-20 AND THE MHA-DT-VN-52 SHOULDER STAY SEATED.",
        "4W. VERIFY THE MHA-SH-VN-52 SWING STOP FULL-FORM THREAD ENGAGEMENT "
        f"{stop_screw.MIN_USEFUL_ENGAGEMENT_TEXT}: THE LESSER READING OF STEPS "
        f"{_step_ref('other-base-mounting', 'K')}-{_step_ref('other-base-mounting', 'L')}.",
        "4X. CHECK THAT ITS HEAD IS FULLY SEATED.",
        # Rubric sample round 2: the notch's reference, the running direction
        # and the sine sense must be readable.  Notches up = cosine mode,
        # turned 90° = sine mode (book pp. 66-67; dimensions.yaml ch14).
        # Owner ruling 2026-11-07 (rubric-sample owner question 1): follow
        # engineerguy video 4, "Operation" (jfH-NbsmvD4).  Forward is
        # clockwise in the sheet 1 FRONT view: the crank arm at 1:51-1:52,
        # gear 4 turning counter-clockwise at 2:16-2:21, and the platen
        # feeding away from the crank at 4:02-4:10 and 10:03.  The sine notch
        # sits level with the axis on the alignment-pinion (MHA-DT-01) side,
        # the left in the FRONT view (7:50-8:15, 8:42-8:48; notches on top
        # = cosines, 7:57-8:12), so the cylinders' outputs read
        # cos(k theta - 90°) = +sin(k theta).
        # Round 13 (rule 4): the platen by its drawing number.
        "5. ZEROING: CRANK FORWARD IS CLOCKWISE IN THE SHEET 1 FRONT VIEW: "
        f"{PLATEN_NUMBER} FEEDS AWAY FROM THE CRANK, AND MHA-DT-12 RUN CLOCKWISE.",
        "5A. SWING THE CONE SET CLEAR AS 4A.",
        "5B. TURN EACH MHA-DT-12 BY HAND UNTIL ITS NOTCH POINTS STRAIGHT UP.",
        "5C. TURN MHA-DT-16 TO ENGAGE MHA-DT-01.",
        "5D. COSINES: TURN MHA-DT-01 BY MHA-DT-15 UNTIL ALL NOTCHES POINT STRAIGHT "
        "UP, THE MHA-DT-12 FINISHING CLOCKWISE TO TAKE UP PLAY.",
        "5E. SINES: AS 5D, BUT STOP ALL NOTCHES LEVEL ON THE MHA-DT-01 SIDE "
        "(LEFT IN THE FRONT VIEW), A QUARTER TURN SHORT OF THE TOP.",
        # The saved pose is engaged with MHA-DT-VN-51 tight (SETUP_NOTES):
        # zeroing ends by re-setting the swing as check 4 does.
        "5F. RETURN MHA-DT-16 TO PARK.",
        "5G. RE-SET THE CONE SET SWING AS 4K-4P.",
        "6. PARKED, MHA-DT-24 HOLDS MHA-DT-01 CLEAR OF EVERY MHA-DT-12.",
        f"7. PARKED, PINS ON THE CAMS: A {TIP_GAP.TIP_GAP_SETTING_TEXT} FEELER IS SNUG TIP TO TIP",
        f"   AT GEAR 0 AND AT GEAR 19, {TIP_GAP.TIP_GAP_ACCEPT_TEXT}",
        f"   (SHEET {CONTINUATION_SHEET}, STEP {steps.step_number('rig-located')}E).",
        "7A. IF ONE IS OUT, EASE THE MHA-DT-VN-57 SCREWS.",
        f"7B. REFIT THE STEP {steps.step_number('rig-set')} LEAVES SNUG.",
        f"7C. RE-SET THE RIG AS STEP {steps.step_number('rig-located')}F.",
        "7D. TIGHTEN MHA-DT-VN-57.",
        "7E. RECHECK THOSE LEAVES.",
        "7F. REPEAT CHECKS 6 AND 7.",
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
        f"PAPER DRIVE MHA-PD-00: {CRANK_CHAIN_WHEEL} CHAIN WHEEL ON MHA-DT-11,",
        # Rubric sample round 14 (rule 23): its retention and acceptance.
        "   PINNED BY 2X MHA-DT-VN-67, HELD ENDWISE BY MHA-DT-31 (STEP "
        f"{steps.step_number('crank-hub-fitted')}F).",
        # Rubric sample round 13 (rule 4): check 5's feed sense names it.
        f"   ITS {PLATEN_NUMBER} PLATEN FEEDS AS CHECK 5 STATES.",
        "FRAME ASSEMBLY MHA-FR-00: ITS MHA-FR-05 RAIL TAKES THE BACK MHA-CH-08 "
        f"AT STEP {steps.step_number(NORTH_BRACKET_SET_KEY)}.",
        "CHANNEL ASSEMBLY MHA-CH-00:",
        f"   ITS {CONNECTING_ROD} CONNECTING RODS AND {ROCKER_ARM} ROCKER ARMS ARE SET ON THE "
        f"MHA-DT-12 CAMS AT STEP {CHANNEL_RODS_SET_AT}.",
        f"   ITS BACK MHA-CH-08, ONE MHA-CH-VN-56 AND ONE {NORTH_BRACKET_SCREW} ARE SET "
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
        # Rule 23 (rubric d9f8b0c): one package note may carry the bond's
        # degrease, apply and cure rules; the bonds are part-spec steps.
        # Round 13: every bond cites the note (1N, 1R, 2-2A, 2Y, 4B, 6B, 12-14), so the
        # note names no step range; the station it sets at once is 12A's.
        "LOCTITE 638 BONDS: DEGREASE BOTH PARTS; COAT THE "
        "INSERTED PART, NEVER A BLIND SEAT; KEEP IT OFF RUNNING LANDS; SET STEP "
        f"{steps.step_number('drum-bonded')}A AT ONCE, BEFORE IT GRABS; CURE "
        "24 H BEFORE LOADING OR OILING. ACCEPT: THE BONDED PART DOES NOT TURN OR "
        "SLIDE BY HAND.",
    )
)

# The steps' FRONT/BACK/LEFT/RIGHT words, keyed once to the sheet 1 FRONT view
# (rubric sample review of v47: compass words needed a private key).  The
# FRONT view is the model's *Back view, looking from the crank end (model -Z)
# toward the cone tip, so its RIGHT is model -X.  Sheet 1's general notes
# field has no line to spare.
DIRECTION_NOTES = _note_text(
    (
        "DIRECTIONS: FRONT, BACK, LEFT AND RIGHT AS SEEN IN THE SHEET 1 FRONT",
        "VIEW, LOOKING FROM THE CRANK END (FRONT) TO THE CONE TIP (BACK).",
    ),
    heading=False,
)


def _split_sequence_chain(
    text: str, *splits: tuple[int | str, str]
) -> tuple[str, ...]:
    """Cut a note block at each (head, continuation heading) in order."""
    pieces = []
    for head, heading in splits:
        piece, text = _split_sequence_notes(text, head, heading)
        pieces.append(piece)
    return (*pieces, text)


# The fields, in reading order (package_note_fields): sheet 7's left field
# carries the direction key and step 1, its full-height right field 2-3 (the
# spigot's bond round opens step 2); sheet 8 carries 4-6 (MHA-PD-00
# cites 4 and 5 on CRANK_SHEET), each step whole; sheets 9-11 carry 7-23, each
# field cut at a sub-step by the constants below.  Sub-step splits keep every
# field full once the one-thing lines grew the sequence (rubric sample rounds
# 2 and 4); test_every_note_field_holds_its_stacked_blocks proves each fits.
CONE_CONTINUED_FROM = str(steps.step_number("post-and-tip-block"))
CRANK_SHEET_FROM = str(steps.step_number("crank-mesh-checked"))
CRANK_SHEET_RIGHT_FROM = f"{steps.step_number('crank-hub-fitted')}D"
CRANK_CONTINUED_FROM = str(steps.step_number("crank-handle-fitted"))
_CRANK_CONTINUED_HEADING = f"ASSEMBLY SEQUENCE CONT. - CRANK {CODE_KEY_POINTER}"
(
    CONE_CRANK_PRIMARY,
    CONE_CRANK_CONTINUED,
    CRANK_SHEET_LEFT,
    CRANK_SHEET_RIGHT,
    CRANK_CONTINUED,
) = _split_sequence_chain(
    CONE_CRANK_STEPS,
    (CONE_CONTINUED_FROM, "ASSEMBLY SEQUENCE CONT. - CONE SET"),
    (CRANK_SHEET_FROM, _CRANK_CONTINUED_HEADING),
    (CRANK_SHEET_RIGHT_FROM, "ASSEMBLY SEQUENCE CONT. - CRANK"),
    (CRANK_CONTINUED_FROM, _CRANK_CONTINUED_HEADING),
)
_BANK_CONTINUED_HEADING = "ASSEMBLY SEQUENCE CONT. - CYLINDER BANK"
BANK_CONTINUED_FROM = str(steps.step_number("cylinder-bank-located"))
BANK_LAST_FROM = f"{steps.step_number('cylinder-bank-located')}W"
BANK_PRIMARY, BANK_CONTINUED, BANK_LAST = _split_sequence_chain(
    BANK_STEPS,
    (BANK_CONTINUED_FROM, _BANK_CONTINUED_HEADING),
    (BANK_LAST_FROM, f"{_BANK_CONTINUED_HEADING} {CODE_KEY_POINTER}"),
)
# Rounds 19-20: step 23's pivot-seat transfer moved each rig split on; #2470
# moved step 6 to sheet 8, so the bank and rig splits moved on to refill
# sheets 9-11 (16C, 18E, 23J).  Step 18E stays on CONTINUATION_SHEET, where
# the checks' tip-gap reset cites it.
RIG_SPLITS = (
    (f"{steps.step_number('straps-pinned-to-torque-shaft')}C", RIG_SEQUENCE_HEADING),
    (
        f"{steps.step_number('rig-located')}E",
        f"{RIG_SEQUENCE_HEADING} {CODE_KEY_POINTER}",
    ),
    (
        f"{steps.step_number('other-base-mounting')}J",
        "ASSEMBLY SEQUENCE CONT. - PINION RIG AND CONE SET ON THE BASE",
    ),
)
# The one-thing check lines (rubric sample round 4) run checks 1-5 down
# sheet 13's left field; 5A heads its right field, over the saved pose.
CHECKS_CONTINUED_FROM = "5B"
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
    region: tuple[float, float, float, float] = CLUSTER_RING_REGION,
) -> tuple[tuple[float, float], list[str], float]:
    """Shift that fits a cluster view's balloon ring, its overflows, its slide.

    The ring is centred in ``region`` (the cluster's CLUSTER_RING_REGIONS
    entry). A ring reaching below the title block's top, where the block takes
    the sheet's right half, slides left until its low arc clears the block
    (rim-124f: items 5 and 33 landed on it); a slide that pushes it past the
    region's left is an overflow.
    Only the outline's size matters: the shift re-centres wherever it landed.
    """
    shift, overflows = ring_fit_shift(outline, region, grow=CLUSTER_RING_REACH)
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
    if ring_left < region[0]:
        overflows.append(
            f"left {ring_left * 1000:.1f} mm < {region[0] * 1000:.1f} mm "
            "clearing the title block"
        )
    return (x, shift[1]), overflows, x - shift[0]


def cluster_heading(cluster: Cluster) -> str:
    """A cluster sheet's heading text under its sheet name."""
    return f"{CLUSTER_TITLES[cluster]} - EXPLODED ISOMETRIC; ITEMS PER SHEET 2"


def cluster_heading_keep_out(cluster: Cluster) -> tuple[float, float, float, float]:
    """The cluster sheet's heading as (left, bottom, right, top), grown by the
    title-block clearance: its width from its longest line at
    CLUSTER_HEADING_CHAR_WIDTH, its depth from its lines at NOTE_LINE_PITCH
    plus 1 mm (round 12's two lines printed down to 253.5 mm, 0.45 mm under
    the pitch alone)."""
    lines = heading_text(CLUSTER_SHEETS[cluster], cluster_heading(cluster)).splitlines()
    return (
        0.0,
        HEADING_XY[1] - len(lines) * NOTE_LINE_PITCH - 0.001 - CLUSTER_TITLE_BLOCK_CLEARANCE,
        HEADING_XY[0]
        + max(len(line) for line in lines) * CLUSTER_HEADING_CHAR_WIDTH
        + CLUSTER_TITLE_BLOCK_CLEARANCE,
        DRAWING_TEMPLATES[SPEC.layout].height_m,
    )


def _boxes_overlap(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> bool:
    return a[2] > b[0] and a[0] < b[2] and a[3] > b[1] and a[1] < b[3]


RAISED_RING_SEARCH_STEP = 0.0005


def raised_ring_fit(
    outline: tuple[float, float, float, float], cluster: Cluster
) -> tuple[tuple[float, float], list[str], float]:
    """Shift that fits a RAISED_RING_CLUSTERS view's balloon ring, its
    overflows, and how far its centre sits off the region's centre.

    The ring stands as low as its ink clears the title block's top (or, too
    tall for that, against the region's top), then takes the x nearest the
    region's centre where neither the view's box nor any balloon the ellipse
    can carry (``_spread_balloons`` puts each centre on it, the cluster's
    margin outside the outline) touches the title block or the sheet heading.
    Only the outline's size matters: the shift re-centres wherever it landed.
    """
    margin = CLUSTER_BALLOON_MARGINS[cluster]
    radius = BALLOON_DIAMETER / 2.0
    reach = margin + radius
    x0, y0, x1, y1 = CLUSTER_RING_REGIONS[cluster]
    width, height = outline[2] - outline[0], outline[3] - outline[1]
    ring_w, ring_h = width + 2.0 * reach, height + 2.0 * reach
    overflows = [
        f"{axis} {size * 1000:.1f} mm > {room * 1000:.1f} mm"
        for axis, size, room in (("width", ring_w, x1 - x0), ("height", ring_h, y1 - y0))
        if size > room
    ]
    template = DRAWING_TEMPLATES[SPEC.layout]
    keep_outs = (
        (
            template.title_block_left_m - CLUSTER_TITLE_BLOCK_CLEARANCE,
            0.0,
            template.width_m,
            template.title_block_top_m + CLUSTER_TITLE_BLOCK_CLEARANCE,
        ),
        cluster_heading_keep_out(cluster),
    )
    cy = max(y0, keep_outs[0][3]) + ring_h / 2.0
    if cy + ring_h / 2.0 > y1:
        cy = y1 - ring_h / 2.0
    centre = (x0 + x1) / 2.0
    rx, ry = width / 2.0 + margin, height / 2.0 + margin
    arc = [(math.cos(math.radians(a)), math.sin(math.radians(a))) for a in range(360)]

    def clear(cx: float) -> bool:
        if cx - ring_w / 2.0 < x0 or cx + ring_w / 2.0 > x1:
            return False
        boxes = [(cx - width / 2.0, cy - height / 2.0, cx + width / 2.0, cy + height / 2.0)]
        for cos_a, sin_a in arc:
            bx, by = cx + rx * cos_a, cy + ry * sin_a
            boxes.append((bx - radius, by - radius, bx + radius, by + radius))
        return not any(_boxes_overlap(box, keep) for box in boxes for keep in keep_outs)

    def shift_to(cx: float) -> tuple[float, float]:
        return (cx - (outline[0] + outline[2]) / 2.0, cy - (outline[1] + outline[3]) / 2.0)

    if overflows:
        return shift_to(centre), overflows, 0.0
    for n in range(int((x1 - x0) / RAISED_RING_SEARCH_STEP) + 1):
        for cx in (centre + n * RAISED_RING_SEARCH_STEP, centre - n * RAISED_RING_SEARCH_STEP):
            if clear(cx):
                return shift_to(cx), overflows, cx - centre
    return shift_to(centre), ["no centre clears the heading and the title block"], 0.0


def fit_cluster_ring(
    outline: tuple[float, float, float, float], cluster: Cluster
) -> tuple[tuple[float, float], list[str], float]:
    """The cluster's ring fit: raised_ring_fit or cluster_ring_fit."""
    if cluster in RAISED_RING_CLUSTERS:
        return raised_ring_fit(outline, cluster)
    return cluster_ring_fit(outline, CLUSTER_RING_REGIONS[cluster])


def _scale_text(scale: tuple[float, float]) -> str:
    return f"{scale[0]:g}:{scale[1]:g}"


def view_label(name: str, scale: tuple[float, float], sheet_scale: tuple[float, float]) -> str:
    """Rule 9: a view's label carries its scale only when it differs from the
    sheet's (rubric sample round 11 refused every repeated one)."""
    return name if tuple(scale) == tuple(sheet_scale) else f"{name} {_scale_text(scale)}"


def cluster_ring_scale(
    outline: tuple[float, float, float, float],
    placed: tuple[float, float],
    *,
    label: str,
    cluster: Cluster | None = None,
) -> tuple[float, float]:
    """The largest ladder scale, from ``placed`` down, whose balloon ring fits.

    ``outline`` is the view's outline at ``placed``; a view's outline scales
    with its scale, and the fit reads only its size (``fit_cluster_ring`` for
    ``cluster``, else cluster_ring_fit in the shared region).
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
        scaled = (cx - hw, cy - hh, cx + hw, cy + hh)
        _shift, overflows, _slide = (
            cluster_ring_fit(scaled) if cluster is None else fit_cluster_ring(scaled, cluster)
        )
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


def code_key_text(rows: Sequence[tuple[int, str]], cylinder_gears: int) -> str:
    """The package's labelled code key (owner ruling 2026-11-08, Pedro): the
    MHA-DT-03 codes as the model configures them, by station front to back
    (``rows``, from the placed cone gears), two columns, GEAR 0 to the last of
    the ``cylinder_gears`` MHA-DT-12, counted from the front, and steps 1S
    and 2B's phasing comb and its blades (a shop tool on its own print, no
    BOM row)."""
    code = rows[0][1]
    digits = "N" * (len(code) - 1)
    half = (len(rows) + 1) // 2
    lines = [
        CODE_KEY_HEADING,
        f"{code[0]}{digits} = MHA-DT-03 WITH {digits} TEETH, BY STATION, FRONT TO BACK:",
    ]
    for left, right in zip(rows[:half], [*rows[half:], None]):
        text = f"STN {left[0]:>2}  {left[1]}"
        if right is not None:
            text += f"      STN {right[0]:>2}  {right[1]}"
        lines.append(text)
    lines.append(
        f"GEAR 0-{cylinder_gears - 1} = MHA-DT-12 FROM THE FRONT, GEAR 0 ON MHA-DT-26."
    )
    lines.append(f"{PHASING_COMB} = PHASING COMB, ONE BLADE IN A TOOTH SPACE PER GEAR.")
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
    # Step 1B slides the keyed MHA-DT-03 gears; T024, T018 and T012 are bonded.
    keyed_gears = facts.count("dt-cone-gear") - len(ROUND_BORE_TEETH)
    rig_first, rig_second, rig_third, rig_last = _split_sequence_chain(
        rig_steps(
            pivot_blocks=facts.count("dt-pinion-pivot-block"),
            cams=facts.count("dt-pinion-cam"),
            slotted=facts.count("dt-vn-slotted-screw"),
        ),
        *RIG_SPLITS,
    )
    (rig_second_from, _), (rig_third_from, _), (rig_last_from, _) = RIG_SPLITS

    def cont(head: int | str, where: str) -> str:
        return f"\nCONT. STEP {head}: {where}."

    right = "RIGHT FIELD"

    def sheet(number: int) -> str:
        return f"SHEET {number}"

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
            SEQUENCE_LEFT_FIELD,
            (
                ("direction key", DIRECTION_NOTES),
                (
                    "cone set sequence",
                    CONE_CRANK_PRIMARY.format(keyed_gears=keyed_gears)
                    + cont(CONE_CONTINUED_FROM, right),
                ),
            ),
        ),
        NoteField(
            SEQUENCE_SHEET,
            f"sheet {SEQUENCE_SHEET} right note field",
            NOTE_FIELD_RIGHT,
            (
                (
                    "cone set sequence continuation",
                    CONE_CRANK_CONTINUED + cont(CRANK_SHEET_FROM, sheet(CRANK_SHEET)),
                ),
            ),
        ),
        NoteField(
            CRANK_SHEET,
            f"sheet {CRANK_SHEET} left note field",
            NOTE_FIELD_LEFT,
            (
                (
                    "crank sequence",
                    CRANK_SHEET_LEFT + cont(CRANK_SHEET_RIGHT_FROM, right),
                ),
            ),
        ),
        NoteField(
            CRANK_SHEET,
            f"sheet {CRANK_SHEET} right note field",
            ISO_RIGHT_FIELD,
            (
                (
                    "crank hub sequence",
                    CRANK_SHEET_RIGHT + cont(CRANK_CONTINUED_FROM, sheet(BANK_SHEET)),
                ),
            ),
        ),
        NoteField(
            BANK_SHEET,
            f"sheet {BANK_SHEET} left note field",
            NOTE_FIELD_LEFT,
            (
                ("crank sequence continuation", CRANK_CONTINUED),
                ("cylinder bank sequence", BANK_PRIMARY + cont(BANK_CONTINUED_FROM, right)),
            ),
        ),
        NoteField(
            BANK_SHEET,
            f"sheet {BANK_SHEET} right note field",
            ISO_RIGHT_FIELD,
            (
                (
                    "cylinder bank sequence continuation",
                    BANK_CONTINUED + cont(BANK_LAST_FROM, sheet(FIT_SHEET)),
                ),
            ),
        ),
        NoteField(
            FIT_SHEET,
            f"sheet {FIT_SHEET} left note field",
            NOTE_FIELD_LEFT,
            (
                ("back bracket sequence", BANK_LAST),
                (
                    "pinion rig sequence",
                    rig_first + cont(rig_second_from, right),
                ),
            ),
        ),
        NoteField(
            FIT_SHEET,
            f"sheet {FIT_SHEET} right note field",
            ISO_RIGHT_FIELD,
            (
                (
                    "pinion rig sequence continuation",
                    rig_second
                    + cont(rig_third_from, sheet(CONTINUATION_SHEET)),
                ),
            ),
        ),
        NoteField(
            CONTINUATION_SHEET,
            f"sheet {CONTINUATION_SHEET} left note field",
            NOTE_FIELD_LEFT,
            (
                (
                    "pinion rig sequence, second continuation",
                    rig_third + cont(rig_last_from, right),
                ),
            ),
        ),
        NoteField(
            CONTINUATION_SHEET,
            f"sheet {CONTINUATION_SHEET} right note field",
            ISO_RIGHT_FIELD,
            (
                ("cone set mounting", rig_last),
            ),
        ),
        NoteField(
            CHECKS_SHEET,
            f"sheet {CHECKS_SHEET} left note field",
            NOTE_FIELD_LEFT,
            (
                (
                    "functional checks",
                    CHECKS_PRIMARY
                    + f"\nCONT. CHECK {CHECKS_CONTINUED_FROM}: RIGHT FIELD.",
                ),
            ),
        ),
        NoteField(
            CHECKS_SHEET,
            f"sheet {CHECKS_SHEET} right note field",
            ISO_RIGHT_FIELD,
            (
                ("functional checks continuation", CHECKS_CONTINUED),
                ("saved pose", SETUP_NOTES),
            ),
        ),
        NoteField(
            SETTING_SHEET,
            f"sheet {SETTING_SHEET} station table field",
            STATION_TABLE_FIELD,
            (
                (
                    "code key",
                    code_key_text(facts.cone_rows(), facts.count("dt-cylinder-gear")),
                ),
            ),
        ),
        NoteField(
            SETTING_SHEET,
            f"sheet {SETTING_SHEET} interface notes field",
            INTERFACE_FIELD,
            (
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


def table_column_widths(
    header: Sequence[str], rows: Sequence[Sequence[str]]
) -> tuple[float, ...]:
    """Each general-table column cut to its longest cell (metres)."""
    return tuple(
        max(len(text) for text in column) * TABLE_CHAR_WIDTH + TABLE_CELL_PAD
        for column in zip(header, *rows, strict=True)
    )


def table_box_violations(
    box: tuple[float, float, float, float], *, label: str
) -> list[str]:
    """A sheet 15 table stays above the note floor, off the station table
    and over the interface notes."""
    x0, y0, x1, y1 = box
    station = STATION_TABLE_FIELD
    findings = []
    if y0 < NOTE_FIELD_LEFT[3]:
        findings.append(f"{label} runs {(NOTE_FIELD_LEFT[3] - y0) * 1000.0:.1f} mm below its floor")
    if x1 > station[0] and y0 < station[1] and y1 > station[3]:
        findings.append(f"{label} overlaps the cone station table field")
    if x0 < INTERFACE_FIELD[2] and y0 < INTERFACE_FIELD[1]:
        findings.append(
            f"{label} runs {(INTERFACE_FIELD[1] - y0) * 1000.0:.1f} mm into the interface notes field"
        )
    return findings


def _place_general_table(
    adapter: Any,
    *,
    title: str,
    header: Sequence[str],
    rows: Sequence[Sequence[str]],
    top_left: tuple[float, float],
    label: str,
) -> tuple[float, float, float, float]:
    """A titled native general table, every cell read back; returns its box."""
    x, top = top_left
    title_note = _add_note_block(adapter, title, (x, top), label=f"{label} title")
    title_extent = _anchor_note(
        adapter, title_note, (x + NOTE_FIELD_INSET, top - NOTE_FIELD_INSET), label=f"{label} title"
    )
    table_top = title_extent[1] - TABLE_TITLE_GAP
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    # swBOMConfigurationAnchor_TopLeft = 1; no template: a plain general table.
    raw = ddoc.InsertTableAnnotation2(False, x, table_top, 1, "", len(rows) + 1, len(header))
    if raw is None:
        raise RuntimeError(f"{label}: InsertTableAnnotation2 returned no table")
    table = _early_bound(raw, "ITableAnnotation")
    if (int(table.RowCount), int(table.ColumnCount)) != (len(rows) + 1, len(header)):
        raise RuntimeError(
            f"{label}: table is {table.RowCount}x{table.ColumnCount}, "
            f"expected {len(rows) + 1}x{len(header)}"
        )
    for column, width in enumerate(table_column_widths(header, rows)):
        # swTableRowColChange_TableSizeCanChange = 0
        if abs(float(table.SetColumnWidth(column, width, 0)) - width) > 1e-6:
            raise RuntimeError(f"{label}: column {column} width did not persist")
    for row, cells in enumerate((header, *rows)):
        for column, text in enumerate(cells):
            table.SetText2(row, column, True, text)
            applied = str(table.DisplayedText2(row, column, True) or "")
            if applied != text:
                raise RuntimeError(
                    f"{label}: cell ({row}, {column}) did not persist: {applied!r} != {text!r}"
                )
    annotation = _early_bound(table.GetAnnotation(), "IAnnotation")
    position = tuple(float(value) for value in (annotation.GetPosition() or ()))
    heights = tuple(float(table.GetRowHeight(row)) for row in range(int(table.RowCount)))
    widths = tuple(float(table.GetColumnWidth(column)) for column in range(int(table.ColumnCount)))
    if len(position) != 3 or not all(map(math.isfinite, (*position, *heights, *widths))):
        raise RuntimeError(f"{label}: table geometry is unreadable")
    box = (position[0], position[1] - sum(heights), position[0] + sum(widths), position[1])
    _telemetry.event(
        "drawing.general_table",
        table=label,
        box_mm=tuple(value * 1000.0 for value in box),
        row_heights_mm=tuple(value * 1000.0 for value in heights),
        column_widths_mm=tuple(value * 1000.0 for value in widths),
    )
    return box


def _place_setting_sheet(adapter: Any, facts: SourceFacts) -> list[str]:
    """The setting, pedestal recheck and feeler stack tables, then the cone
    station table beside them."""
    _activate_sheet(adapter, SHEET_NAMES[SETTING_SHEET - 1])
    _heading(adapter, SETTING_SHEET)
    _reference_iso(adapter, caption="FINISHED ASSEMBLY", label="setting reference isometric")
    findings = []
    top = NOTE_FIELD_LEFT[1]
    for title, header, rows, label in (
        (SETTING_TABLE_TITLE, SETTING_TABLE_HEADER, SETTING_TABLE_ROWS, "setting table"),
        (
            PEDESTAL_RECHECK_TITLE,
            PEDESTAL_RECHECK_HEADER,
            PEDESTAL_RECHECK_ROWS,
            "pedestal recheck table",
        ),
        (FEELER_STACK_TITLE, FEELER_STACK_HEADER, FEELER_STACK_ROWS, "feeler stack table"),
    ):
        box = _place_general_table(
            adapter,
            title=title,
            header=header,
            rows=rows,
            top_left=(SETTING_TABLE_LEFT, top),
            label=label,
        )
        findings += table_box_violations(box, label=f"sheet {SETTING_SHEET} {label}")
        top = box[1] - NOTE_BLOCK_GAP
    return findings + _stack_sheet_note_fields(adapter, facts, SETTING_SHEET)



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
    new_project_drawing(adapter, layout=SPEC.layout, scale=ASSEMBLED_SCALE, unit=UNIT)
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


def _add_view_arrows(adapter: Any, front: Any, top: Any) -> list[str]:
    """Sheet 14's removed views C and D and sheet 12's full-detail view E
    look from the projected group's LEFT (model +X): each is named by a
    letter note whose straight leader is the viewing arrow.  C and D end at
    the FRONT view's left edge at the height of what they show; E, the whole
    train, ends at the TOP view's left edge, mid-height, clear of them (the
    draw_ch_rocker_arm recipe; rule 9)."""
    arrows = []
    for letter, model_y in SHEET1_VIEW_ARROWS:
        _x, tip_y = model_point_in_view(
            adapter, front, (0.0, model_y / 1000.0, 0.0), label=f"view {letter} arrow height"
        )
        arrows.append((letter, front, "FRONT", tip_y))
    top_outline = _view_outline(top)
    arrows.append((FULL_DETAIL_VIEW_LETTER, top, "TOP", (top_outline[1] + top_outline[3]) / 2.0))
    findings = []
    for letter, view, name, tip_y in arrows:
        label = f"view {letter} viewing arrow"
        left = _view_outline(view)[0]
        if VIEW_ARROW_TEXT_X + VIEW_LETTER_HEIGHT >= left - VIEW_ARROW_MIN_RUN:
            findings.append(
                f"sheet 1 view {letter} arrow: {(left - VIEW_ARROW_TEXT_X) * 1000.0:.1f} mm "
                f"left of the {name} view is too short for a letter and its arrow"
            )
        tip = (left, tip_y)
        note = add_leader_note(
            adapter,
            letter,
            text_xy=(VIEW_ARROW_TEXT_X, tip_y + VIEW_LETTER_HEIGHT / 2.0),
            attach_xy=tip,
            view=view,
            label=label,
        )
        # add_note leaves text at the document height; size the letter and
        # prove the leader tip did not move with it.
        annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
        text_format = annotation.GetTextFormat(0)
        if text_format is None:
            raise RuntimeError(f"{label}: note has no text format")
        text_format.CharHeight = VIEW_LETTER_HEIGHT
        if not annotation.SetTextFormat(0, False, text_format):
            raise RuntimeError(f"{label}: failed to size the letter")
        rebuild_drawing(adapter, label=f"{label} letter")
        points = list(annotation.GetLeaderPointsAtIndex(0) or ())
        if len(points) < 6 or math.dist((points[-3], points[-2]), tip) > 0.001:
            raise RuntimeError(f"{label}: tip moved when its letter was sized")
    return findings


def _place_assembled_sheet(adapter: Any, facts: SourceFacts) -> list[str]:
    _activate_sheet(adapter, SHEET_NAMES[0])
    # The FRONT view looks at the crank end (model -Z, the machine's front)
    # toward the cone tip, so the steps' FRONT, BACK, LEFT and RIGHT read off
    # it (DIRECTION_NOTES; rubric sample review of v47).  That is the model's
    # *Back view; the TOP over it is *Top turned half a turn, and the RIGHT
    # beside it *Left.
    front = place_view(adapter, str(SOURCE), "*Back", 0.080, 0.110, scale=ASSEMBLED_SCALE)
    top = _early_bound(
        place_view(adapter, str(SOURCE), "*Top", 0.080, 0.200, scale=ASSEMBLED_SCALE), "IView"
    )
    top.Angle = math.pi
    rebuild_drawing(adapter, label="assembled top view turned")
    if abs(abs(float(top.Angle)) - math.pi) > 1e-6:
        raise RuntimeError(f"assembled top view angle reads {top.Angle!r}, expected pi")
    right = place_view(adapter, str(SOURCE), "*Left", 0.200, 0.110, scale=ASSEMBLED_SCALE)
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
    findings += _add_view_arrows(adapter, front, top)
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
    # Rule 9: the sheet is at ASSEMBLED_SCALE, so the projected views' labels
    # carry no scale; the isometric's would only if it differed.
    _caption_under(adapter, front, "FRONT", label="front caption")
    _caption_under(adapter, top, "TOP", label="top caption")
    _caption_under(adapter, right, "RIGHT", label="right caption")
    _caption_under(
        adapter,
        iso,
        view_label("ISOMETRIC", ASSEMBLED_ISO_SCALE, ASSEMBLED_SCALE),
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
    view = set_drawing_view_instance_visibility(adapter, view, frozenset(facts.clusters[cluster]), mode="show", label=label)
    preferred_outline = _view_outline(view)
    scale = cluster_ring_scale(preferred_outline, preferred, label=label, cluster=cluster)
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
        shift, overflows, slide = fit_cluster_ring(outline, cluster)
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
        margin=CLUSTER_BALLOON_MARGINS[cluster],
    )
    balloons = [landing.note for landing in landings]
    # One ring over every balloon at this sheet's clearance; the shared call
    # above ringed them at the default.
    _spread_balloons(
        adapter,
        view,
        balloons,
        margin=CLUSTER_BALLOON_MARGINS[cluster],
        clearance=CLUSTER_BALLOON_CLEARANCE[cluster],
    )
    rebuild_drawing(adapter, label=f"{label} ring")
    _uncross_balloon_leaders(adapter, balloons, label=label)
    _verify_balloon_attachments(balloons, balloon_items, label=label)
    _heading(adapter, number, cluster_heading(cluster))
    return _balloon_annotations(balloons), landings


def _place_sequence_sheet(adapter: Any, facts: SourceFacts) -> list[str]:
    _activate_sheet(adapter, SHEET_NAMES[SEQUENCE_SHEET - 1])
    _heading(adapter, SEQUENCE_SHEET)
    _reference_iso(
        adapter,
        caption="FINISHED ASSEMBLY",
        label="sequence reference isometric",
        center=SEQUENCE_ISO_CENTER,
    )
    return _stack_sheet_note_fields(adapter, facts, SEQUENCE_SHEET)


def _place_crank_sheet(adapter: Any, facts: SourceFacts) -> list[str]:
    _activate_sheet(adapter, SHEET_NAMES[CRANK_SHEET - 1])
    _heading(adapter, CRANK_SHEET)
    _reference_iso(adapter, caption="FINISHED ASSEMBLY", label="crank reference isometric")
    return _stack_sheet_note_fields(adapter, facts, CRANK_SHEET)


def _place_bank_sheet(adapter: Any, facts: SourceFacts) -> list[str]:
    _activate_sheet(adapter, SHEET_NAMES[BANK_SHEET - 1])
    _heading(adapter, BANK_SHEET)
    _reference_iso(adapter, caption="FINISHED ASSEMBLY", label="bank reference isometric")
    return _stack_sheet_note_fields(adapter, facts, BANK_SHEET)


def _place_fit_sheet(adapter: Any, facts: SourceFacts) -> list[str]:
    _activate_sheet(adapter, SHEET_NAMES[FIT_SHEET - 1])
    _heading(adapter, FIT_SHEET)
    _reference_iso(adapter, caption="FINISHED ASSEMBLY", label="fit reference isometric")
    return _stack_sheet_note_fields(adapter, facts, FIT_SHEET)


def _place_checks_sheet(adapter: Any, facts: SourceFacts) -> list[str]:
    _activate_sheet(adapter, SHEET_NAMES[CHECKS_SHEET - 1])
    _heading(adapter, CHECKS_SHEET)
    _reference_iso(adapter, caption="CHECK REFERENCE", label="checks reference isometric")
    return _stack_sheet_note_fields(adapter, facts, CHECKS_SHEET)


def _place_continuation_sheet(adapter: Any, facts: SourceFacts) -> list[str]:
    _activate_sheet(adapter, SHEET_NAMES[CONTINUATION_SHEET - 1])
    _heading(adapter, CONTINUATION_SHEET)
    _reference_iso(
        adapter, caption="FINISHED ASSEMBLY", label="continuation reference isometric"
    )
    return _stack_sheet_note_fields(adapter, facts, CONTINUATION_SHEET)


def _setting_view(
    adapter: Any, *, names: frozenset[str], model_point: tuple[float, float, float],
    centre: tuple[float, float], scale: tuple[float, float], label: str,
    step: Callable[[str], None],
) -> Any:
    """A *Right view of ``names`` alone, shifted so ``model_point`` (machine
    mm) lands on ``centre``: a Right-plane setting leg is true length in it."""
    view = _early_bound(
        place_view(adapter, str(SOURCE), "*Right", *centre, scale=scale), "IView"
    )
    step(f"{label}: place_view")
    set_hidden_lines_removed(adapter, view)
    step(f"{label}: set_hidden_lines_removed")
    _configure_view(adapter, view, exploded=False, label=label)
    step(f"{label}: configure_view")
    view = set_drawing_view_instance_visibility(adapter, view, names, mode="show", label=label)
    step(f"{label}: isolate_instances")
    projected = model_point_in_view(
        adapter, view, tuple(value / 1000.0 for value in model_point), label=label
    )
    _shift_view(adapter, view, (centre[0] - projected[0], centre[1] - projected[1]), label=label)
    step(f"{label}: shift_view")
    return view


def _setting_circle(
    adapter: Any, view: Any, centre: tuple[float, float], radius: float
) -> None:
    """The channel package's view-sketch circle pattern, in sheet metres."""
    name = view_name(adapter, view)
    if not _early_bound(adapter.currentModel, "IDrawingDoc").ActivateView(name):
        raise RuntimeError(f"cannot activate setting view {name}")
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
        raise RuntimeError(f"cannot create setting circle in view {name}")


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
    """Full bank at 1:1, a 4:1 north bearing-face detail and a cropped 1:1
    drum station; no scaled-down views.

    MHA-DT-22 prints the drum station as a reference; the toleranced setting
    is the assembly's (dt_drum_station_setting_spec), shown here on the arbor
    and drum alone.

    Captions follow measured view outlines; the ordinary crop's identifier is
    owned by its parent view and its rendered clearance survives final rebuilds.

    R7 first marked the source dirty somewhere in this sheet. Keep checkpoints
    around its operations rather than assigning that observation to SetText,
    sketch visibility or model-item import without native evidence. These read
    the source's save flag only; the package's pre-export guard still owns failure.
    """
    _activate_sheet(adapter, SHEET_NAMES[BANK_SETTINGS_SHEET - 1])
    step("bank settings: activate sheet")
    _heading(adapter, BANK_SETTINGS_SHEET, BANK_SETTINGS_POINTER)
    step("bank settings: heading")
    bank_names = frozenset(facts.clusters["cylinder-bank"])
    overall = _setting_view(
        adapter, names=bank_names, centre=BANK_SETTING_CENTER,
        model_point=(
            cone_line.X_DRUM, bank_settings.AXIS_Y,
            (bank.FRONT_STRAP_INNER_Z + bank.BACK_STRAP_INNER_Z) / 2.0,
        ),
        scale=BANK_SETTING_SCALE, label="cylinder bank setting",
        step=step,
    )
    spring_z = sum(bank.BANK_SPRING_Z) / 2.0
    detail = _setting_view(
        adapter, names=bank_names, centre=BANK_SPRING_DETAIL_CENTER,
        model_point=(cone_line.X_DRUM, bank_settings.AXIS_Y, spring_z),
        scale=BANK_SPRING_DETAIL_SCALE, label="north spring setting",
        step=step,
    )
    drum_instances = [
        instance for instance in facts.instances if instance.stem in DRUM_STATION_SETTING_STEMS
    ]
    drum_stems = {instance.stem for instance in drum_instances}
    if drum_stems != DRUM_STATION_SETTING_STEMS:
        raise RuntimeError(
            f"drum station setting needs {sorted(DRUM_STATION_SETTING_STEMS)}, "
            f"the source has {sorted(drum_stems)}"
        )
    drum_names = frozenset(instance.name for instance in drum_instances)
    drum_view = _setting_view(
        adapter, names=drum_names, centre=DRUM_STATION_SETTING_CENTER,
        model_point=(APINION_X, drum_station_setting.AXIS_Y, DRUM_STATION_CROP_CENTRE_Z),
        scale=DRUM_STATION_SETTING_SCALE, label="drum station setting",
        step=step,
    )
    _feature, _name, head_rear_z, drum_front_z = drum_station_setting.LEGS[0]
    leg_middle = model_point_in_view(
        adapter, drum_view,
        (
            APINION_X / 1000.0, drum_station_setting.AXIS_Y / 1000.0,
            (head_rear_z + drum_front_z) / 2000.0,
        ),
        label="drum station leg",
    )
    drum_keep = {drum_station_setting.DIMENSION: (leg_middle[0], DRUM_STATION_TEXT_Y)}
    # The bank's closed stack and spring gap print as setting-table rows
    # (sheet 15) and labels here, not as the model's imported setting
    # dimensions: those carry a model-authored converted band and compass
    # wording the drawing cannot re-word without dirtying the source.
    annotations = []
    _show_base_view_sketches(adapter, drum_view, (drum_station_setting.FEATURE,), label="drum station")
    step(f"drum station: show base-view sketch {drum_station_setting.FEATURE}")
    with _bank_dimension_source_trace(
        adapter, step, label=f"drum station / {drum_station_setting.FEATURE}"
    ):
        annotations.extend(
            curate_view_dimensions(
                adapter, drum_view, keep=drum_keep, view_label="drum station",
                dimensions_by_feature=SETTING_DIMENSIONS,
            )
        )
        step("drum station: curate_view_dimensions")
    radius = BANK_SPRING_CROP_RADIUS_MM / 1000.0
    parent_centre = model_point_in_view(
        adapter, overall,
        (cone_line.X_DRUM / 1000.0, bank_settings.AXIS_Y / 1000.0, spring_z / 1000.0),
        label="spring detail boundary",
    )
    _setting_circle(adapter, overall, parent_centre, radius)
    step("bank settings: overall boundary circle")
    adapter.currentModel.ClearSelection2(True)
    _setting_circle(adapter, detail, BANK_SPRING_DETAIL_CENTER, radius * 4.0)
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
    # The drum station's crop: the same view-sketch circle, on the point the
    # view was shifted to put the crop centre on.
    drum_radius = DRUM_STATION_CROP_RADIUS_MM / 1000.0
    adapter.currentModel.ClearSelection2(True)
    _setting_circle(adapter, drum_view, DRUM_STATION_SETTING_CENTER, drum_radius)
    step("drum station: crop circle")
    drum_status = int(drum_view.Crop2(False, False, 1))
    step("drum station: Crop2")
    adapter.currentModel.ClearSelection2(True)
    rebuild_drawing(adapter, label="drum station setting crop")
    step("drum station: crop rebuild")
    drum_view.UpdateViewDisplayGeometry()
    step("drum station: UpdateViewDisplayGeometry")
    if drum_status != 1 or not bool(drum_view.IsCropped()):
        raise RuntimeError(f"drum station setting Crop2 failed: {drum_status}")
    # Follow the rebuilt outlines, not insertion coordinates. Centering the
    # overall caption below its view would hit the spring dimension's two-line
    # callout; its right end has clear space below the south pedestal instead.
    # All four annotations target 8 mm, inside their 4 mm minimum-air
    # regions. Bounded anchoring cannot promise a corner on the boundary
    # (R6's detail caption undershot); the actual 4 mm guards stay unchanged.
    placement_gap = 2.0 * VIEW_CAPTION_GAP
    captions = []
    for view, text, right_aligned, label in (
        (overall, BANK_VIEW_CAPTION, True, "bank setting caption"),
        (detail, "DETAIL A 4:1", False, "spring detail caption"),
        (drum_view, DRUM_VIEW_CAPTION, False, "drum station caption"),
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
    # The labelled sketch the setting table's rows name: each leader tip on
    # the model point it labels, the note owned by its view.
    for view, (text, text_xy, model_point), label in (
        *((overall, spec, f"bank setting label {index}") for index, spec in enumerate(BANK_SETTING_LABELS, 1)),
        (detail, BANK_SPRING_LABEL, "spring gap label"),
    ):
        tip = model_point_in_view(
            adapter, view, tuple(value / 1000.0 for value in model_point), label=label
        )
        add_leader_note(adapter, text, text_xy=text_xy, attach_xy=tip, label=label, view=view)
        step(f"{label}: leader note")
    _activate_sheet(adapter, SHEET_NAMES[BANK_SETTINGS_SHEET - 1])
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
        assert_imported_precision(adapter, annotations, SETTING_PRECISION)
        step("bank settings settled: imported precision readback")
        for annotation in annotations:
            name = dimension_name(adapter, annotation)
            display = _early_bound(
                _early_bound(annotation, "IAnnotation").GetSpecificAnnotation(), "IDisplayDimension"
            )
            # Read only: SetText on an imported dimension can dirty its source.
            # swDimensionTextCalloutBelow; a multi-line callout reads with CRLF.
            text = str(display.GetText(4) or "").replace("\r\n", "\n")
            if text != SETTING_CALLOUTS[name]:
                raise RuntimeError(
                    f"{name} lost its model-authored setting callout: {text!r}; "
                    "rebuild the source assembly"
                )
            dimension = _early_bound(display.GetDimension2(0), "IDimension")
            tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
            upper, lower = SETTING_BANDS[name]
            if (abs(float(tolerance.GetMaxValue()) - upper / 1000.0) > 1e-9
                    or abs(float(tolerance.GetMinValue()) - lower / 1000.0) > 1e-9):
                raise RuntimeError(f"{name} lost its model-authored setting band")
        for view, kept, label in (
            (drum_view, drum_station_setting.DIMENSION, "drum station setting"),
        ):
            names = {
                dimension_name(adapter, _early_bound(annotation, "IAnnotation"))
                for annotation in (view.GetAnnotations() or ())
            }
            if kept not in names:
                raise RuntimeError(f"{label} dimension did not survive its crop")
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
        # The model's *Right looks from model +X: the machine's LEFT side
        # (DIRECTION_NOTES).
        f"VIEW {FULL_DETAIL_VIEW_LETTER} - {FULL_DETAIL_CAPTION}",
        label=f"{label} caption",
    )
    _note_handle_stake(adapter, view, label=f"{label} stake note")
    _note_cam_stake(adapter, view, label=f"{label} cam stake note")
    _note_lever_pin_peen(adapter, view, label=f"{label} lever pin peen note")
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


def _note_lever_pin_peen(adapter: Any, view: Any, *, label: str) -> None:
    """Point step 22C's peen note at MHA-DT-30 in the MHA-DT-16 hub
    (LEVER_PIN_CENTRE_M), the note right of it (lever_pin_peen_note_xy)."""
    stem = frozenset({LEVER_PIN_STEM})
    tips: list[tuple[float, float]] = []
    for leaf in _view_component_leaves(adapter, view, label=label):
        if not (leaf.visible and _stems_matching(leaf.identities, stem)):
            continue
        (centre,) = _anchor_model_points(
            adapter, leaf, (LEVER_PIN_CENTRE_M,), {}, stem=LEVER_PIN_STEM, label=label
        )
        tips.append(model_point_in_view(adapter, view, centre, label=label))
    if len(tips) != 1:
        raise RuntimeError(f"{label}: expected one visible {LEVER_PIN_STEM}, got {tips!r}")
    (tip,) = tips
    note = _early_bound(
        add_leader_note(
            adapter,
            LEVER_PIN_PEEN_NOTE,
            text_xy=lever_pin_peen_note_xy(tip),
            attach_xy=tip,
            label=label,
            view=view,
        ),
        "INote",
    )
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    points = list(annotation.GetLeaderPointsAtIndex(0) or ())
    _telemetry.event(
        "drawing.lever_pin_peen_note",
        tip_mm=tuple(round(value * 1000.0, 2) for value in tip),
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
    findings += _place_setting_sheet(adapter, facts)
    step("setting sheet")
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
