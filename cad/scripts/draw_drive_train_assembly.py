r"""Create the native nine-sheet drive-train assembly drawing package (MHA-A03).

The released ``drive-train.SLDASM`` stays authoritative and byte-for-byte
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
import sys
from datetime import UTC, datetime
from itertools import combinations
from pathlib import Path
from typing import Any, Callable, Literal, Sequence

import _seat_forensics
import _telemetry
import connecting_rod_spec as rod
import cylinder_bank_layout as bank
from _common import _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    _balloon_item_number,
    _leader_segments_of,
    _spread_balloons,
    add_component_bom_balloons,
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
)
from _drawing_layout_check import LeaderSegment, find_leader_leader_crossings
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME, DrawingLayout
from cone_gear_notes import ATTACHMENT as CONE_GEAR_JOINT
from crank_drive_gear_notes import ATTACHMENT_ALTERNATIVE as CRANK_GEAR_ALTERNATIVE
from crank_drive_gear_notes import ATTACHMENT_PROCESS as CRANK_GEAR_JOINT
from drive_train_assembly_spec import (
    CLUSTERS,
    EXPLODED_VIEW_NAME,
    PENDING_STEMS,
    SOURCE_CONFIGURATION,
    Cluster,
    Instance,
    cluster_members,
    unclassified_stems,
)
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import add_note, place_view, view_name

SPEC = DRAWINGS_BY_NAME["drive_train_assembly"]
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
DRAWING_NUMBER = "MHA-A03"
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

ASSEMBLED_SCALE = (1.0, 3.0)
ASSEMBLED_ISO_SCALE = (1.0, 3.0)
REFERENCE_ISO_SCALE = (1.0, 8.0)
# At 1:3 the bank and rig explodes filled about a fifth of their sheets (Fable
# review of baseline-5); the cone-crank ring already spans ~170 x 150 mm there.
# The bank still filled a small fraction of its sheet at 1:2 (r9 Fable review);
# at 2:3 its ~145 x 107 mm outline plus the balloon ring fits the 395 x 176 field.
# The rig cannot grow: its ~116 mm-tall outline plus ring already nears 176.
CLUSTER_SCALES: dict[Cluster, tuple[float, float]] = {
    "cylinder-bank": (2.0, 3.0),
    "cone-crank": (1.0, 3.0),
    "pinion-rig": (1.0, 2.0),
}
# Sheets without a cluster or the assembled views carry only the 1:8
# reference isometric.
SHEET_SCALES = {
    **{name: REFERENCE_ISO_SCALE for name in SHEET_NAMES},
    SHEET_NAMES[0]: ASSEMBLED_SCALE,
    **{SHEET_NAMES[number - 1]: CLUSTER_SCALES[c] for c, number in CLUSTER_SHEETS.items()},
}

# --- sheet 1: projected front/top/right group + isometric ---------------------
# The projected group's lower-left lands here; the views are aligned on the
# model origin (ASME third angle: top above front, right to the right of it).
# At 1:3 the group is ~177 mm tall (front y ~42 + gap + top z ~121, the old
# MHA-A03 sheet); the 175 mm the first region allowed failed on the farm (leaf
# 20260923T045245Z-1-b34a8422). The origin sits just above the title block
# (top y=0.0655) and the region top 4.5 mm under the zone border.
PROJECTED_GROUP_ORIGIN = (0.024, 0.068)
PROJECTED_GAP = 0.014
PROJECTED_REGION = (0.018, 0.068, 0.300, 0.262)
# The right half between the heading (bottom ~0.243) and the title block
# (top 0.0655): a 1:3 isometric outline is ~130 mm, 1.5x baseline-5's 1:4.
ASSEMBLED_ISO_CENTER = (0.320, 0.155)
VIEW_CAPTION_GAP = 0.004

# --- sheet 2: BOM in two columns + reference isometric -----------------------
BOM_COLUMN_WIDTHS = {
    "item": 0.012,
    "part": 0.022,
    "description": 0.118,
    "quantity": 0.012,
}
BOM_COLUMN_WIDTH = sum(BOM_COLUMN_WIDTHS.values())
# Measured, not derived: in the 118 mm column, four 41-character descriptions
# kept one line and the 47-character MHA-030 row wrapped to 10.195 mm
# (farm leaf 20260923T044055Z-1-20b23f24, swmaker000005).
BOM_DESCRIPTION_MAX_CHARS = 41
BOM_ANCHOR = (0.018, 0.252)
BOM_SECOND_COLUMN_X = BOM_ANCHOR[0] + BOM_COLUMN_WIDTH + 0.008
BOM_ROW_HEIGHT = 0.006
BOM_HEIGHT_TOLERANCE = 1e-6
BOM_SHEET_CLEARANCE = 0.003
# Under the first BOM column, where sheet 6 already proved the same 1:8 view
# and caption clear the sheet number; beside the BOM its centred caption ran
# into the second column and past the right border.
BOM_REFERENCE_ISO_CENTER = (0.110, 0.068)
# The MHA-013 station pointer lives here, not in its BOM cell: on the grouped
# 20-configuration row SolidWorks kept a written description only up to its
# second comma (farm leaf 20260923T040258Z-1-0726d474, swmaker000005).
BOM_REFERENCE_CAPTION = (
    f"REFERENCE 1:8 - BALLOONS ON SHEETS {min(CLUSTER_SHEETS.values())}-"
    f"{max(CLUSTER_SHEETS.values())}\n"
    f"MHA-013 CONE GEAR STATIONS: SHEET {FIT_SHEET}"
)

# --- sheets 3-5: exploded cluster views --------------------------------------
CLUSTER_VIEW_CENTER = (0.200, 0.165)
# Top keeps baseline-4's ~5 mm clearance under the two-line sheet heading.
CLUSTER_RING_REGION = (0.020, 0.072, 0.415, 0.248)
CLUSTER_BALLOON_MARGIN = 0.012
BALLOON_DIAMETER = 0.010
# Extra arc clearance between neighbouring ring balloons. The shared ring keeps
# circles 1.5 apart; on sheet 5 the left-block attachments bunch so tightly that
# items 17/18/19/20/26 read as one converging knot (Main eye-pass of r6b).
# Placement stays in attachment-angle order, so widening cannot add a crossing.
CLUSTER_BALLOON_CLEARANCE = {
    "cylinder-bank": 0.0015,
    "cone-crank": 0.0015,
    "pinion-rig": 0.008,
}
# Families whose balloon lands on the head of one chosen instance instead of
# the first visible edge the shared picker meets. Sheet 3's pedestal hold-down
# screw balloon (r6b item 26) pointed at the north screw, which hides behind
# its strap; the south one stands clear in the exploded view.
HEAD_ANCHORED: dict[Cluster, dict[str, Literal["south", "north"]]] = {
    "cylinder-bank": {"pedestal-hold-down-screw": "south"},
}
SW_VIEW_ENTITY_EDGE = 1  # swViewEntityType_e.swViewEntityType_Edge

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
SHEET_NUMBER_XY = (0.018, 0.025)
REFERENCE_ISO_CENTER = (0.380, 0.110)
# Notes pitch 4.525 mm a line (summing-assembly.pdf): ~47 lines fit the full
# left column, ~24 the right one above the 1:8 reference view that every sheet
# needs for its title-block property links (finalize_drawing refuses a sheet
# without a view: r8, leaf 20260923T214354Z-1-4126331f). Sheet 6 carries steps
# 1-7 and the general notes on the left, its right field kept free for D1; the
# bank's steps 8-9F fill sheet 7's left field; steps 10-21 continue on sheet 8
# beside the station table (Main, B1 re-ruling 2026-09-26).
ISO_RIGHT_FIELD = (NOTE_FIELD_RIGHT[0], NOTE_FIELD_RIGHT[1], NOTE_FIELD_RIGHT[2], 0.140)
REFERENCE_ISO_CAPTION_XY = (0.330, 0.082)

# --- BOM identities: released part numbers and descriptions ------------------
# The model owns the part number (each component's "Number" property, read and
# cross-checked at build time); the description column is drawing wording.
# test_drive_train_assembly_drawing.py pins every number against the parts
# registry and every builder-inserted family against this table.
BOM_PART_NUMBERS = {
    "cylinder-gear-shaft": "MHA-028",
    "arbor-pedestal": "MHA-004",
    "cylinder-end-disc": "MHA-121",
    "cylinder-gear": "MHA-027",
    "pedestal-hold-down-screw": "MHA-143",
    "arbor-set-screw": "MHA-147",
    "foot-screw": "MHA-103",
    "cone-gear-shaft": "MHA-014",
    "cone-gear": "MHA-013",
    "crank-drive-gear": "MHA-021",
    "cone-swing-platform": "MHA-091",
    "cone-pivot-post": "MHA-016",
    "cone-tip-block": "MHA-092",
    "cone-tip-bushing": "MHA-096",
    "cone-tip-adjuster": "MHA-097",
    "cone-tip-pinch-screw": "MHA-098",
    "cone-tip-shim": "MHA-141",
    "post-mount-screw": "MHA-142",
    "cone-lock-knob": "MHA-093",
    "cone-pivot-screw": "MHA-094",
    "swing-stop-screw": "MHA-095",
    "crankshaft": "MHA-026",
    "crank-pinion": "MHA-025",
    "crank-pinion-pin": "MHA-134",
    "crank-arm": "MHA-020",
    "crank-pin": "MHA-024",
    "crank-pin-ring": "MHA-128",
    "crank-pin-eye": "MHA-130",
    "fillister-screw": "MHA-030",
    "crank-handle": "MHA-022",
    "crank-handle-pivot-screw": "MHA-139",
    "crank-hub": "MHA-137",
    "crank-hub-pin": "MHA-138",
    "alignment-pinion": "MHA-002",
    "pinion-bracket": "MHA-056",
    "pinion-pivot-block": "MHA-061",
    "pinion-pivot-shaft": "MHA-062",
    "pinion-lift-rod": "MHA-060",
    "pinion-spring": "MHA-114",
    "pinion-cam-pin": "MHA-116",
    "pinion-cam": "MHA-104",
    "pinion-lever": "MHA-059",
    "pinion-lever-pin": "MHA-135",
    "pinion-handle": "MHA-058",
    "pinion-arbor": "MHA-102",
    "pinion-arbor-collar": "MHA-144",
    "slotted-screw": "MHA-101",
}
BOM_DESCRIPTIONS = {
    "cylinder-gear-shaft": "CYLINDER GEAR ARBOR",
    "arbor-pedestal": "ARBOR PEDESTAL",
    "cylinder-end-disc": "CYLINDER BANK THRUST WASHER",
    "cylinder-gear": "CYLINDER GEAR WITH CAM, 120T",
    "pedestal-hold-down-screw": "#8-32 FILLISTER SCREW, MCMASTER 90280A197",
    "arbor-set-screw": "#4-40 X 1/4 SET SCREW, MCMASTER 91375A106",
    "foot-screw": "#4-40 FILLISTER SCREW, MCMASTER 90280A108",
    "cone-gear-shaft": "CONE GEAR SHAFT",
    "cone-gear": "CONE GEAR, T006-T120 BY 6; 1 EACH",
    "crank-drive-gear": "CRANK DRIVE GEAR, 64T",
    "cone-swing-platform": "CONE SWING PLATFORM",
    "cone-pivot-post": "CONE PIVOT POST AND CRANK COLUMN",
    "cone-tip-block": "CONE TIP BLOCK",
    "cone-tip-bushing": "CONE TIP BUSHING",
    "cone-tip-adjuster": "CUP-TIP SET SCREW, MCMASTER 94025A164",
    "cone-tip-pinch-screw": "#4-40 FILLISTER SCREW, MCMASTER 91794A112",
    "cone-tip-shim": "CONE TIP SHIM PACK, 1.10 NOMINAL",
    "post-mount-screw": "1/4-20 FILLISTER SCREW, MSC 40923898",
    "cone-lock-knob": "KNURLED THUMB SCREW, MCMASTER 91882A425",
    "cone-pivot-screw": "SHOULDER SCREW, MCMASTER 91829A560",
    "swing-stop-screw": "#8-32 FILLISTER SCREW, MCMASTER 90280A199",
    "crankshaft": "CRANKSHAFT",
    "crank-pinion": "CRANK PINION, 16T",
    "crank-pinion-pin": "CRANK PINION RETENTION PIN",
    "crank-arm": "CRANK ARM",
    "crank-pin": "CRANK TAPER PIN, 1:48",
    "crank-pin-ring": "TAPER PIN KEEPER RING",
    "crank-pin-eye": "KEEPER RING ANCHOR EYE",
    "fillister-screw": "#4-40 BRASS FILLISTER, MCMASTER 90114A511",
    "crank-handle": "CRANK HANDLE",
    "crank-handle-pivot-screw": "CRANK HANDLE PIVOT SCREW",
    "crank-hub": "CRANK HUB",
    "crank-hub-pin": "CRANK HUB AXIAL PIN",
    "alignment-pinion": "ALIGNMENT PINION",
    "pinion-bracket": "PINION BRACKET STRAP",
    "pinion-pivot-block": "PINION PIVOT BLOCK",
    "pinion-pivot-shaft": "PINION PIVOT SHAFT",
    "pinion-lift-rod": "PINION LIFT ROD",
    "pinion-spring": "PINION SPRING",
    "pinion-cam-pin": "PINION CAM FOLLOWER PIN",
    "pinion-cam": "PINION ECCENTRIC CAM, WITH M2.5 SET SCREW",
    "pinion-lever": "PINION LEVER",
    "pinion-lever-pin": "PINION LEVER PIN, 1/16 X 13 STEEL",
    "pinion-handle": "PINION GRIP CROSSROD",
    "pinion-arbor": "INTEGRAL PINION ARBOR AND GRIP HEAD",
    "pinion-arbor-collar": "PINION ARBOR RETENTION COLLAR",
    "slotted-screw": "#8-32 FILLISTER SCREW, MCMASTER 90280A201",
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
ASSEMBLED_HEADING = f"SAVED WORKING POSE AND FREE MOTIONS: SEE SHEET {CHECKS_SHEET} FOR SETUP."

CONE_CRANK_STEPS = "\n".join(
    (
        "ASSEMBLY SEQUENCE - CONE SET AND CRANK",
        # #834 (rule 6): the cone gears' joining method left the MHA-013
        # sheets for this step; the wording is the gear's own constant.
        "1. BOND {cone_gears}X MHA-013 TO THEIR MHA-014 SEATS, TIP FIRST, WITH",
        f"   {CONE_GEAR_JOINT}: T006 AT THE BACK THROUGH",
        f"   T120 AT THE FRONT (STATION TABLE, SHEET {FIT_SHEET}).",
        # #906 (Main 2026-09-26): MHA-021's joining method moved here from its
        # print (rule 6); the wording is the gear's own constants.
        f"   MHA-021 FRONT OF T120: {CRANK_GEAR_JOINT} ITS MHA-014 SEAT;",
        f"   {CRANK_GEAR_ALTERNATIVE}.",
        # U37c (user, 2026-09-23): MHA-142 is MSC 40923898, 1/4-20 x 3-1/2
        # slotted fillister, through the unchanged 6.02 counterbore. Its floor
        # sits 78.67-81.29 above the post foot at the printed bands, so a fixed
        # length could end 0.98 proud; each screw is cut to its own hole
        # (pivot). Engagement is capped by the plate, printed as 1/4 1018 CF
        # flat bar as supplied (U41, 6.22 min less the 0.3 cut: 5.92 = 0.93D
        # worst case, swing): a named, user-accepted exception to rule 12, in
        # the Named exceptions table of cad/docs/drawing-simplicity-policy.md.
        # The sheet states the range, never the governance label (fleet
        # ruling 2026-09-26, test_printed_text_rulings).
        "2. SCREW MHA-016 TO MHA-091 WITH 2X MHA-142 FROM THE TOP. CUT EACH TO",
        "   FIT AND CHAMFER THE END: FLUSH TO 0.3 SHORT OF THE MHA-091",
        # Named exception: MHA-142 engagement (drawing-simplicity-policy.md, "Named exceptions").
        "   UNDERSIDE, NEVER PROUD (NOMINAL LENGTH 86.0). ENGAGEMENT 5.92-6.35",
        "   (0.93-1.0D).",
        # U30 (user, 2026-09-23, option (a)): one #6-32 button-head screw (W22)
        # up through the MHA-091 slot, height and side set by the shim pack at
        # fit-up. Wording from swing (dt-tip-block-attachment-options-20260923.md
        # section 2(a)).
        "   JOURNAL MHA-014 IN MHA-016. SLIP MHA-096 ON THE TIP STUB AGAINST",
        "   T006. SET MHA-092 ON A 1.10 MHA-141 SHIM PACK OVER THE MHA-091",
        "   SLOT; MHA-140 UP THROUGH THE SLOT, FINGER-TIGHT. RUN MHA-097 IN",
        "   UNTIL ITS CUP SEATS THE TIP. SLIDE MHA-092 IN THE SLOT AND CHANGE",
        "   SHIMS UNTIL MHA-014 SPINS FREE, NO TIGHT SPOT AT THE MHA-016",
        "   JOURNAL; SNUG MHA-140 AND RECHECK. RECORD THE SHIM STACK.",
        # U32 (user, 2026-09-23): option 1A turn-set, dt-pending-rulings
        # packet section 1. Worded without the pitch so it survives E11
        # (MHA-097 5/16-18 -> #10-32: 1/8 turn is ~0.18 -> ~0.10).
        "3. THREAD MHA-097 INTO MHA-092 UNTIL MHA-014 JUST STOPS SHUTTLING",
        "   AND STILL TURNS FREELY; BACK OFF 1/8 TURN; TIGHTEN",
        "   MHA-098 ACROSS THE SLIT. END PLAY 0.05-0.40, BY FEEL OR INDICATOR.",
        # U31 (user, 2026-09-23, option 3a): MHA-016 bores the crank-above-cone
        # spacing 39.33 +0.37/0 in one setup, so the mesh is checked, not
        # set; 14.5 deg PA gives 0.517 backlash per mm of centre distance.
        # Wording from pivot (DT-ConePivotPost-cc-20260923.md, U31).
        "4. FIT MHA-026 IN THE MHA-016 CRANK BORE. SLIDE MHA-025 ON, NOT YET",
        "   PINNED, AND MESH IT WITH MHA-021 TOOTH IN GAP. CHECK BACKLASH",
        "   0.20-0.55 AT THE MHA-025 PITCH LINE, FREE THROUGH ONE FULL MHA-021",
        "   TURN. OUT OF BAND: STOP - MHA-016 BORE SPACING IS OUT (SEE ITS",
        "   PRINT). HOLD MHA-025 IN MESH; SET ITS STATION 0.25 OFF THE SPOT",
        "   FACE WITH A FEELER. ONLY THEN MATCH-DRILL AND REAM FOR MHA-134 AT",
        "   BOSS MID-LENGTH WITH MHA-026; SEAT FLUSH BOTH SIDES PER THE MHA-025",
        "   PRINT. RE-CHECK BACKLASH 0.20-0.55 AFTER PINNING.",
        "5. THE PAPER-DRIVE T12 WHEEL GOES ON MHA-026 BEFORE THE ARM.",
        # U33 (user, 2026-09-23): crank hub MHA-137 pressed into the arm and
        # seam-pinned by MHA-138 (a 4 m6 dowel, 4.0 long = half the arm); the
        # MHA-024 cross-hole runs behind the arm through the hub barrel. The
        # handle rides the MHA-139 shoulder screw. Wording from crankhub.
        "6. PRESS MHA-137 INTO MHA-020 TO THE SHOULDER, FACES FLUSH.",
        "   MATCH-DRILL/REAM THE SEAM Ø4 X 4.0 DEEP; DRIVE MHA-138 FLUSH.",
        "   SLIDE ONTO MHA-026, SHAFT END FLUSH, PUNCH MARKS ALIGNED.",
        "   TAPER-REAM 1:48 THROUGH HUB AND SHAFT; LIGHT-DRIVE MHA-024,",
        "   REMOVABLE BY TAP ON SMALL END. HANG MHA-128 FROM THE PIN HEAD;",
        "   CLAMP MHA-130 UNDER MHA-030.",
        "7. SLIDE MHA-022 ONTO MHA-139. THREAD MHA-139 INTO THE MHA-020",
        "   PIVOT TAP WITH LOCTITE 222 (REMOVABLE); SEAT THE SHOULDER TIGHT",
        "   ON THE ARM FACE. HANDLE TURNS FREELY; END PLAY 0.25-1.0.",
        f"   CYLINDER BANK: SHEET {BANK_SHEET}.",
    )
)

BANK_STEPS = "\n".join(
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
        # The MHA-028 print owns the stock (3/8 1018 CF X 190, long enough for
        # the edge finder) and its cut-to-fit rule (Main, r9).
        # #743 (retention743 plan section 4, user rulings Q1-Q3): the bank is
        # a solid stack, so fit-up proves the stack length, locates the back
        # strap as the Z datum, sets the front strap by one 0.45 leaf and
        # swaps a setting mandrel for the finished arbor, which the MHA-147
        # apex set screws hold. Supersedes U34's disc/feeler end play and
        # its "span -6.0" arbor. Every limit is cylinder_bank_layout's,
        # rounded inward (test_bank_fitup_limits_are_the_layout_bands):
        # 8: T 7.0565 +0.05/0; L20 141.13 +0.20/0. 9A: Y is the hole-table
        # rear-face distance of the back strap inner face, 70.538 +/-0.10.
        # 9F: E_b 0.35-0.55.
        "8. MIC EACH OF {cylinder_gears}X MHA-027, CAM FACE TO BACK FACE:",
        "   7.057-7.106; RECORD. SLIDE THEM ONTO A 3/8 GROUND SETTING",
        "   MANDREL ~190 LONG, ALL ALIKE, CAM SIDE FRONT; ADD EACH CONNECTING",
        "   ROD (CHANNEL ASSEMBLY MHA-A02) ON ITS CAM AS ITS GEAR GOES ON.",
        "   CLAMP LIGHTLY END TO END: GEAR 0 CAM FACE TO GEAR 19 BACK FACE",
        "   141.13-141.33. LONG: RE-FACE THE THICKEST CAM FACE, REMEASURE.",
        "   SLIDE THE STACK OFF IN ORDER.",
        "9. BASE MHA-035 OUT OF THE FRAME, ON THE MILL TABLE, PAD TRAMMED,",
        "   OVERHANG SUPPORTED; CONE SET (MHA-091) NOT FITTED.",
        "9A. BACK MHA-004 ALONE ON THE MANDREL, ON THE BASE. EDGE-FIND BOTH",
        "   MHA-035 HOLE-TABLE DATUM FACES (SEE ITS PRINT); ZERO DRO X AND Y.",
        "   SET THE STRAP INNER FACE TO Y 70.44-70.63 AND THE MANDREL CENTRE",
        "   (EDGE-FIND BOTH SIDES, HALVE) TO X 168.11-168.31.",
        "   SPOT MHA-035 THROUGH THE FOOT HOLE WITH AN 11/64 TRANSFER PUNCH;",
        "   LIFT OFF. DRILL #29 X 19.5, TAP #8-32 X 16.0 (PLUG, THEN",
        "   BOTTOMING); BLOW OUT CHIPS. REFIT, RE-SET Y AND X, TIGHTEN",
        "   MHA-143 AND RECHECK.",
        # dtrefactor's #937 review: the loaded mandrel hangs from the back
        # strap alone until the front one goes on (F2), and its front end sits
        # over the front foot hole, where no chuck or tap wrench reaches (F1).
        # So the loaded mandrel leaves the base for the drill and tap.
        "9B. FROM THE FRONT, LOAD ONE MHA-121, THE STACK IN ORDER, THEN THE",
        "   OTHER MHA-121. PUSH THE BANK BACK, CLOSED UP ON THE BACK MHA-121.",
        "   PROP THE MANDREL FRONT END AT BORE HEIGHT (V-BLOCK ON PARALLELS);",
        "   TAKE THE PROP AWAY ONLY TO SLIDE THE FRONT MHA-004 ON.",
        "9C. SLIDE THE FRONT MHA-004 ON UNTIL A 0.45 LEAF BETWEEN ITS STRAP",
        "   AND THE FRONT MHA-121 IS LIGHTLY PINCHED. SET X 168.11-168.31 AND",
        "   SPOT AS 9A. SLIDE THE FRONT MHA-004 OFF; DRAW THE LOADED MANDREL",
        "   OUT OF THE BACK MHA-004, HOLDING BOTH MHA-121, AND LAY IT IN",
        "   V-BLOCKS ON PARALLELS OFF THE BASE, RODS HANGING FREE. DRILL AND",
        "   TAP AS 9A. PASS THE MANDREL BACK THROUGH THE BACK MHA-004, PUSH",
        "   THE BANK BACK AND PROP IT AS 9B. REFIT THE FRONT MHA-004; RE-SET",
        "   THE LEAF AND X, TIGHTEN MHA-143 AND RECHECK.",
        "9D. MEASURE MHA-004 OUTER FACE TO OUTER FACE. TURN MHA-028: ITS",
        "   CYLINDER IS THAT SPAN, PLUS A 1.5 DOME EACH END (SEE ITS PRINT).",
        "9E. PUSH MHA-028 IN FROM THE BACK, END TO END WITH THE MANDREL, UNTIL",
        "   THE MANDREL IS OUT AND EACH DOME STANDS 1.5 PROUD (DEPTH GAUGE).",
        "   SPOT MHA-028 THROUGH EACH CROWN TAP WITH A #43 DRILL, 0.5 DEEP;",
        "   BLOW OUT CHIPS. RUN THE BACK MHA-147 IN TIGHT, THEN THE FRONT ONE.",
        # F3: the leaf reads the end play only with the bank closed up on
        # the back washer; pulled forward it reads nothing.
        "9F. THE BANK TURNS FREE BY HAND. BANK PUSHED BACK:",
        "   A 0.35 LEAF ENTERS AT THE FRONT MHA-121, A 0.55 LEAF DOES NOT.",
        f"   PINION RIG: CONT. ON SHEET {FIT_SHEET}.",
    )
)

RIG_STEPS = "\n".join(
    (
        "ASSEMBLY SEQUENCE CONT. - PINION RIG",
        # The front MHA-056 top bore is a closed 8 mm hole: once MHA-002 is
        # bonded, the drum blocks MHA-102 from the north and its 15 mm head
        # from the south. So the arbor passes the front strap bare, back end
        # first, and the drum is bonded after (reviewfirst, Main 2026-09-24).
        "10. PRESS {cam_pins}X MHA-116 INTO THE MHA-056 SEATS PER ITS PRINT.",
        "11. MATCH-REAM THE MHA-102 HEAD TO MHA-058; PRESS MHA-058 (NO TURN OR",
        "    SLIDE BY HAND).",
        # R1a (user): pinned retention collar MHA-144 (#860). It goes on
        # before the arbor is journalled (pinion_arbor_collar_spec); the pin
        # is the rig's 1/16 x 1/2 slotted spring pin, never proud of the Ø15.
        "12. SLIDE MHA-144 ON FROM THE MHA-102 BACK END, PAST BOTH JOURNALS,",
        "    TO THE MHA-102 PIN HOLE; DRIVE ONE 1/16 X 1/2 SPRING PIN THROUGH",
        "    BOTH, SUB-FLUSH.",
        "13. PASS MHA-102, BACK END FIRST, THROUGH THE FRONT MHA-056 TOP BORE",
        "    FROM THE HEAD SIDE.",
        "14. FIT MHA-002 ON MHA-102 PER THE MHA-102 PRINT.",
        "15. JOURNAL THE MHA-102 BACK END IN THE BACK MHA-056 TOP BORE; HANG",
        "    BOTH MHA-056 ON MHA-062 THROUGH {pivot_blocks}X MHA-061.",
        # E-a (user): the strap feet are pinned to the torque shaft. Right
        # after the hang: MHA-062 is drilled off the machine (the cams sit
        # ~18.5 west of the foot), and once the cams are on, the pin's west
        # edge has 0.38 of air to the MHA-104 collar. Wording from
        # pinioncluster (dt-torque-shaft-pin-fitup-steps-20260924.md), #858.
        "16. PUSH THE HUNG CLUSTER HARD ON THE BACK MHA-061; SET",
        "    MHA-062 FLUSH WITH ITS OUTER FACE. TRANSFER-PUNCH MHA-062 THROUGH",
        "    EACH MHA-056 CROSS HOLE; WITHDRAW IT AND DRILL 1/16 THRU AT EACH",
        "    MARK (V-BLOCK). REFIT MHA-062 FLUSH END BACK; DRIVE ONE 1/16 X 1/2",
        "    SPRING PIN PER STRAP, SUB-FLUSH BOTH EDGES. THE CLUSTER SWINGS",
        "    FREELY AND MHA-062 TURNS WITH IT IN BOTH MHA-061.",
        "17. FIT {cams}X MHA-104 AND MHA-059 ON MHA-060 IN THE MHA-061 LIFT",
        "    BORES. PARK EACH CAM ECCENTRIC DOWN; LOCK IT WITH THE M2.5 SET",
        "    SCREW SUPPLIED WITH MHA-104. SEAT MHA-059 ON MHA-060 TO THE BORE",
        "    FLOOR, GRIP AT ITS PARK ANGLE; AT 3 O'CLOCK MATCH-DRILL 1/16",
        "    THROUGH HUB AND ROD AT MID-ENGAGEMENT (4.0 FROM THE BORE FLOOR);",
        "    DRIVE MHA-135; PEEN BOTH ENDS FLUSH.",
        # Main ruling 2026-09-23 (U28 corollary): the rig is located by its
        # parked tip gap, and MHA-035 carries its hold-down and spring seats as
        # TRANSFER FROM MHA-061. The level line of centres makes block travel
        # equal gap change; 2.5 is the physical rest gap, not the CAD gap
        # (pinioncluster, PR #837).
        "18. LOCATE THE RIG ON BASE MHA-035 (FRAME ASSEMBLY MHA-A04); ITS",
        "    SEATS ARE TRANSFERRED, NOT PRE-DRILLED. SET BOTH MHA-061 LOOSE",
        "    ON THE BASE WITH MHA-114 FITTED.",
        "    PARK MHA-059: THE MHA-116 PINS REST ON THE CAMS UNDER THE SPRING.",
        "19. FACE A MHA-002 TOOTH TIP TO A MHA-027 TOOTH TIP ON THE LEVEL",
        "    LINE OF CENTRES. SLIDE THE RIG IN UNTIL A 2.5 FEELER (E.G. 2.00",
        "    + 0.50 LEAVES) IS SNUG; ACCEPT 2.3-2.7. SET IT AT THE FRONT AND",
        "    BACK STATIONS TO SQUARE BOTH MHA-061 TO THE DRUM.",
        # #854 Codex P1: the front-block end-play feeler is set here, before
        # the clamp and before step 20 spots the seats. Wording from
        # pinioncluster; the band is pinion_rig_layout FRONT_BLOCK_FEELER
        # 0.25 with FRONT_BLOCK_FEELER_BAND 0.10, printed as limits (the purity
        # gate keeps bilateral bands in the spec). PENDING until #854 lands,
        # when the limits are generated from those two constants.
        "    [PENDING: WITH THE CLUSTER HARD ON THE BACK MHA-061, STAND THE",
        "    FRONT MHA-061 0.15-0.35 OFF THE FRONT MHA-056 OUTER FACE",
        "    (FEELER).] CLAMP.",
        # Seat depths from the base's own seat specs (build_harmonic_base
        # BLOCK_/FOOT_SCREW_DRILL_DEPTH and _HOLE_DEPTH; the #8-32 pair is the
        # rule-12 E10 re-derive on dt-pinion-lever-pin #844). FOOT_HOLE_DEPTH
        # 8.975 prints as 9.0: .X +/-0.8 is the honest band for a tap depth.
        "20. SPOT MHA-035 THROUGH THE MHA-061 HOLES; DRILL #29 X 15.0, TAP",
        "    #8-32 X 12.75 (PLUG, THEN BOTTOMING), {slotted} PLACES. SET",
        "    MHA-114 WITH ITS TERMINAL FLAT ON THE PARKED BACK MHA-056; SPOT",
        "    THROUGH ITS FOOT HOLE; DRILL #43 X 11.0, TAP #4-40 X 9.0 (PLUG,",
        "    THEN BOTTOMING), 1 PLACE. FIT {slotted}X MHA-101 AND 1X MHA-103.",
        f"21. OTHER BASE MOUNTING: SEE SHEET {CHECKS_SHEET}, EXTERNAL INTERFACES.",
    )
)

# Check 3 prints the bank's ring-overhang bound (#743 user ruling Q1) and the
# share of the ring width that bound leaves on the cam, rounded down.
RING_OVERHANG_TEXT = f"{bank.RING_OVERHANG_MAX:.2f}"
RING_ON_CAM_PERCENT = math.floor(
    100.0 * (rod.RING_THICKNESS - bank.RING_OVERHANG_MAX) / rod.RING_THICKNESS
)

CHECKS = "\n".join(
    (
        "ASSEMBLY-ONLY FUNCTIONAL CHECKS",
        "1. CRANK TURNS FREELY THROUGH FULL TURNS; ONE CRANK TURN TURNS THE",
        "   CONE SET 1/4 TURN (16T:64T).",
        # U31: the bored MHA-016 spacing sets the 16T:64T mesh (step 4).
        "2. MHA-025/MHA-021 BACKLASH 0.20-0.55 AT THE MHA-025 PITCH LINE, CRANK",
        "   AT REST, NO TIGHT SPOT THROUGH ONE FULL MHA-021 TURN; EACH CONE",
        "   GEAR MESHES ITS MHA-027 PER THE MHA-013 PRINT.",
        "3. EACH MHA-027 TURNS FREELY ON MHA-028 WITHOUT AXIAL BINDING.",
        # The same bound the MHA-027 print states (cylinder_gear_notes).
        f"   A CONNECTING-ROD RING MAY OVERHANG ITS CAM UP TO {RING_OVERHANG_TEXT} (AT LEAST",
        f"   {RING_ON_CAM_PERCENT}% OF THE RING WIDTH STAYS ON THE CAM).",
        # MHA-095 is the DISENGAGED stop (build_cone_swing_platform
        # swing_hardware_geometry): engaged, the plate edge stands >= 2.0 off
        # it, so the cone set comes back on its meshes, not on the stop.
        "4. CONE SWING (P1): LOOSEN MHA-093; SWING THE CONE SET ON MHA-094 TO",
        "   THE MHA-095 STOP, CLEAR OF EVERY MHA-027. SWING IT BACK UNTIL ALL",
        "   {cone_gears} MESHES RE-ENGAGE; TIGHTEN MHA-093.",
        "5. ZEROING (P2), CONE SET SWUNG CLEAR: TURN EACH MHA-027 BY HAND",
        "   UNTIL ITS NOTCH LINES UP. TURN MHA-059 TO ENGAGE MHA-002; TURN",
        "   MHA-002 BY MHA-058 UNTIL ALL NOTCHES POINT UP (COSINES) OR 90 DEG",
        "   (SINES). RETURN MHA-059 TO PARK; RE-ENGAGE THE CONE SET.",
        "6. PARKED, MHA-114 HOLDS MHA-002 CLEAR OF EVERY MHA-027.",
        "7. PARKED, PINS ON THE CAMS: A 2.5 FEELER IS SNUG TIP TO TIP AT THE",
        f"   FRONT AND BACK STATIONS; ACCEPT 2.3-2.7 (SHEET {FIT_SHEET}, STEP 19).",
    )
)

SETUP_NOTES = "\n".join(
    (
        "SAVED POSE AND FREE MOTIONS",
        "SAVED DEFAULT: CONE SET ENGAGED, MHA-002 PARKED CLEAR, CAMS",
        "ECCENTRIC DOWN, CRANK ARM DOWN.",
        "FREE, NEVER LOCKED: CRANK SPIN, CONE-PLATFORM SWING, PINION",
        "SWING, LIFT-ROD/CAM SPIN.",
    )
)

INTERFACE_NOTES = "\n".join(
    (
        "EXTERNAL INTERFACES - NOT BOM ITEMS",
        "BASE MHA-035 (FRAME ASSEMBLY MHA-A04) RECEIVES MHA-094, MHA-093,",
        "MHA-095, {slotted}X MHA-101, {foot}X MHA-103 AND {hold_down}X MHA-143.",
        "PAPER DRIVE MHA-A06: T12 CHAIN WHEEL ON MHA-026.",
        "CHANNEL ASSEMBLY MHA-A02: CONNECTING RODS RUN ON THE MHA-027 CAMS.",
    )
)

# Main ruling 2026-09-23 on the Fable C6 finding; ISO VG 32 matches the
# fleet's finish notes.
CONSUMABLES_NOTES = "\n".join(
    (
        "GENERAL ASSEMBLY NOTES",
        "ADHESIVE: MHA-013 AND MHA-021 PER STEP 1.",
        "OIL THE MHA-027/MHA-028 JOURNALS AND ALL PIVOTS WITH ISO VG 32",
        "MACHINE OIL. NO THREADLOCKER UNLESS A STEP OR PRINT CALLS FOR IT",
        "(LOCTITE 222 ON MHA-139, STEP 7). #4-40, #6-32, #8-32 SCREWS: SNUG.",
    )
)

FIT_PLACEHOLDER = "\n".join(
    (
        # U31 (pivot): the bored spacing fixes the mesh; check 2 proves it.
        # The rest of the old placeholder is owned elsewhere now: each cone
        # gear's mesh by the MHA-013 print (check 2), the pinion engagement
        # by steps 18-19 and check 7, the taper pin by step 6.
        "16T:64T CENTRE DISTANCE FIXED BY MHA-016 BORE SPACING; VERIFY BY",
        "BACKLASH (CHECK 2).",
    )
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


def balloon_attachment_violations(
    records: Sequence[tuple[str, str, tuple[str, ...]]],
    expected: dict[str, str],
) -> list[str]:
    """Findings for balloons whose attached component is not their BOM item."""
    findings = []
    seen: dict[str, int] = {}
    for name, item, stems in records:
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
    """Data rows in the FIRST column: the larger half, so column two is never taller."""
    if data_rows < 2:
        raise ValueError("a split BOM needs at least two data rows")
    return (data_rows + 1) // 2


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
    return violations


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
    """Two-column station table: STN n  MHA-013 Tnnn."""
    half = (len(rows) + 1) // 2
    lines = ["CONE STATION TABLE - MHA-013 BY STATION, FRONT TO BACK"]
    for left, right in zip(rows[:half], [*rows[half:], None]):
        text = f"STN {left[0]:>2}  {left[1]}"
        if right is not None:
            text += f"      STN {right[0]:>2}  {right[1]}"
        lines.append(text)
    return "\n".join(lines)


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


def _view_outline(view: Any) -> tuple[float, float, float, float]:
    outline = tuple(float(value) for value in _early_bound(view, "IView").GetOutline())
    if len(outline) != 4 or outline[2] <= outline[0] or outline[3] <= outline[1]:
        raise RuntimeError(f"view has an invalid outline {outline!r}")
    return outline


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


def _head_edge(adapter: Any, view: Any, instance: str, *, label: str) -> Any | None:
    """The largest visible circular edge of one named instance: its head rim.

    Reads the view exactly as ``_drawing_common._pick_component_anchor_edge``
    does (the view object as placed, ``GetVisibleEntities2`` of the drawing
    component's model component), the path that finds these screws' edges on
    every build. r7 (leaf 20260923T180240Z-1-e6c4ca27) found no circular edge
    on the south pedestal screw through an early-bound ``IView``; the log
    could not say whether it saw no edges or no circles, so both counts are
    logged now.
    """
    root = adapter._attempt(lambda: view.RootDrawingComponent2(False), default=None)
    if root is None:
        raise RuntimeError(f"{label}: drawing view has no root component")
    component = None
    for raw in tuple(_early_bound(root, "IDrawingComponent").GetChildren() or ()):
        drawing_component = _early_bound(raw, "IDrawingComponent")
        name = str(drawing_component.Name or "").split("@", 1)[0]
        if name.replace("\\", "/").rsplit("/", 1)[-1] == instance:
            component = adapter._attempt(lambda dc=drawing_component: dc.Component, default=None)
            break
    if component is None:
        raise RuntimeError(f"{label}: {instance} is not in the view")
    edges = tuple(
        adapter._attempt(
            lambda: view.GetVisibleEntities2(component, SW_VIEW_ENTITY_EDGE), default=()
        )
        or ()
    )
    best, best_radius, circles = None, 0.0, 0
    for edge in edges:
        curve = adapter._attempt(
            lambda e=edge: _early_bound(_early_bound(e, "IEdge").GetCurve(), "ICurve"),
            default=None,
        )
        if curve is None or not adapter._attempt(lambda c=curve: bool(c.IsCircle()), default=False):
            continue
        circles += 1
        radius = float(tuple(curve.CircleParams)[6])
        if radius > best_radius:
            best, best_radius = edge, radius
    _telemetry.info(
        f"{label}: head anchor {instance}: {len(edges)} visible edges, {circles} circular, "
        f"largest r={best_radius * 1000.0:.3f} mm"
    )
    _telemetry.event(
        "drawing.balloon_head_anchor",
        label=label,
        instance=instance,
        edges=len(edges),
        circles=circles,
        radius_mm=best_radius * 1000.0,
    )
    return best


def _insert_balloon_on_edge(
    adapter: Any, view: Any, edge: Any, *, stem: str, expected_item: str, label: str
) -> Any:
    """``_drawing_common``'s component balloon, on a chosen edge."""
    draw = adapter.currentModel
    if not _early_bound(draw, "IDrawingDoc").ActivateView(view_name(adapter, view)):
        raise RuntimeError(f"{label}: failed to activate the {stem} view")
    draw.ClearSelection2(True)
    if not view.SelectEntity(edge, False):
        raise RuntimeError(f"{label}: failed to select the {stem} head edge")
    options = _early_bound(
        _early_bound(draw.Extension, "IModelDocExtension").CreateBalloonOptions(),
        "IBalloonOptions",
    )
    options.Style = 1
    options.Size = 2
    options.UpperTextContent = 1
    options.ShowQuantity = False
    options.ItemNumberStart = 1
    options.ItemNumberIncrement = 1
    options.ItemOrder = 1
    note = _early_bound(draw.Extension, "IModelDocExtension").InsertBOMBalloon2(options)
    draw.ClearSelection2(True)
    if note is None:
        raise RuntimeError(f"{label}: failed to insert the {stem} balloon")
    item = _balloon_item_number(adapter, note, label=label)
    if item != expected_item:
        raise RuntimeError(f"{label}: {stem} resolved item {item}, expected {expected_item}")
    return note


def _head_anchored_balloons(
    adapter: Any,
    view: Any,
    cluster: Cluster,
    facts: SourceFacts,
    items: dict[str, str],
    *,
    label: str,
) -> tuple[list[Any], frozenset[str]]:
    """Balloons placed on a head rim, and the families they cover.

    The preferred side's instance goes first, then the others. A family with
    no visible head rim on any instance falls back to the shared picker with a
    warning: the anchor is cosmetic, and must not fail an eight-sheet package.
    """
    balloons = []
    anchored = set()
    for stem, side in HEAD_ANCHORED.get(cluster, {}).items():
        candidates = sorted(
            (
                instance
                for instance in facts.instances
                if instance.stem == stem and instance.name in facts.clusters[cluster]
            ),
            key=lambda instance: instance.origin_mm[2],
            reverse=side == "north",
        )
        edge = None
        for instance in candidates:
            edge = _head_edge(adapter, view, instance.name, label=label)
            if edge is not None:
                break
        if edge is None:
            _telemetry.warn(
                f"{label}: no {stem} instance shows a head rim; the shared picker anchors it"
            )
            continue
        balloons.append(
            _insert_balloon_on_edge(
                adapter, view, edge, stem=stem, expected_item=items[stem], label=label
            )
        )
        anchored.add(stem)
    return balloons, frozenset(anchored)


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


def _set_exploded_state(adapter: Any, view: Any, show: bool, *, label: str) -> None:
    bound = _early_bound(view, "IView")
    if str(bound.ReferencedConfiguration) != SOURCE_CONFIGURATION:
        raise RuntimeError(f"{label}: view must reference {SOURCE_CONFIGURATION!r}")
    returned = bool(bound.ShowExploded(show))
    actual = bool(bound.IsExploded())
    if actual != show:
        raise RuntimeError(f"{label}: exploded-state readback is {actual}, expected {show}")
    if show and not returned:
        raise RuntimeError(f"{label}: ShowExploded returned false")
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError(f"{label}: exploded-state rebuild failed")


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
                if instance.stem == "cone-gear"
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
    names = tuple(assembly.GetExplodedViewNames2(SOURCE_CONFIGURATION) or ())
    if names != (EXPLODED_VIEW_NAME,):
        raise RuntimeError(
            f"drive-train source exploded views {names!r} != {(EXPLODED_VIEW_NAME,)!r}"
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
    and MHA-021's OutsideDiaReference sketch (its 65.15 mm construction tip
    circle, kept for the part print's OD dimension) in every view: about ten
    centerline-font paths per sheet that the old MHA-A03 print did not carry.
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
    for sheet_number, sheet_name in enumerate(SHEET_NAMES, start=1):
        _activate_sheet(adapter, sheet_name)
        sheet = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
        scale = SHEET_SCALES[sheet_name]
        if not sheet.SetScale(float(scale[0]), float(scale[1]), False, False):
            raise RuntimeError(f"failed to set drive-train sheet scale: {sheet_name}")
        _add_note_block(
            adapter,
            f"SHEET {sheet_number} OF {len(SHEET_NAMES)}",
            SHEET_NUMBER_XY,
            label="package sheet number",
        )


def _heading(
    adapter: Any, sheet_number: int, text: str = "", *, xy: tuple[float, float] = HEADING_XY
) -> None:
    lines = [f"{DRAWING_NUMBER} - {SHEET_NAMES[sheet_number - 1]}"]
    if text:
        lines.append(text)
    _add_note_block(adapter, "\n".join(lines), xy, label=f"sheet {sheet_number} heading")


def _reference_iso(
    adapter: Any,
    *,
    caption: str,
    label: str,
    center: tuple[float, float] = REFERENCE_ISO_CENTER,
) -> Any:
    """A small collapsed isometric: every sheet needs a view for its title block."""
    view = place_view(adapter, str(SOURCE), "*Isometric", *center, scale=REFERENCE_ISO_SCALE)
    _set_exploded_state(adapter, view, False, label=label)
    set_high_quality_shaded_with_edges(adapter, view, label=label)
    _caption_under(adapter, view, caption, label=f"{label} caption")
    return view


def _place_assembled_sheet(adapter: Any) -> list[str]:
    _activate_sheet(adapter, SHEET_NAMES[0])
    front = place_view(adapter, str(SOURCE), "*Front", 0.080, 0.110, scale=ASSEMBLED_SCALE)
    top = place_view(adapter, str(SOURCE), "*Top", 0.080, 0.200, scale=ASSEMBLED_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", 0.200, 0.110, scale=ASSEMBLED_SCALE)
    iso = place_view(
        adapter, str(SOURCE), "*Isometric", *ASSEMBLED_ISO_CENTER, scale=ASSEMBLED_ISO_SCALE
    )
    for label, view in (("front", front), ("top", top), ("right", right), ("isometric", iso)):
        _set_exploded_state(adapter, view, False, label=f"assembled {label}")
    for view in (front, top, right):
        set_hidden_lines_removed(adapter, view)
    set_high_quality_shaded_with_edges(adapter, iso, label="drive-train assembled isometric")

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
    _heading(adapter, 1, ASSEMBLED_HEADING, xy=ASSEMBLED_HEADING_XY)
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


def _place_bom_sheet(adapter: Any, facts: SourceFacts) -> tuple[str, dict[str, str]]:
    _activate_sheet(adapter, SHEET_NAMES[1])
    view = place_view(
        adapter, str(SOURCE), "*Isometric", *BOM_REFERENCE_ISO_CENTER, scale=REFERENCE_ISO_SCALE
    )
    _set_exploded_state(adapter, view, False, label="BOM reference isometric")
    set_high_quality_shaded_with_edges(adapter, view, label="BOM reference isometric")
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
    _caption_under(
        adapter,
        view,
        BOM_REFERENCE_CAPTION,
        label="BOM reference caption",
    )
    return bom_name, dict(items)


def _place_cluster_sheet(
    adapter: Any,
    cluster: Cluster,
    facts: SourceFacts,
    *,
    bom_name: str,
    items: dict[str, str],
) -> dict[str, Any]:
    """Place one exploded cluster sheet; return its balloons by note name."""
    number = CLUSTER_SHEETS[cluster]
    _activate_sheet(adapter, SHEET_NAMES[number - 1])
    label = f"{cluster} exploded isometric"
    scale = CLUSTER_SCALES[cluster]
    view = place_view(adapter, str(SOURCE), "*Isometric", *CLUSTER_VIEW_CENTER, scale=scale)
    _set_exploded_state(adapter, view, True, label=label)
    names = frozenset(facts.clusters[cluster])
    _isolate_instances(adapter, view, names, label=label)
    set_high_quality_shaded_with_edges(adapter, view, label=label)
    _link_view_to_bom(view, bom_name, label=label)
    outline = _view_outline(view)
    shift, overflows = ring_fit_shift(
        outline, CLUSTER_RING_REGION, grow=CLUSTER_BALLOON_MARGIN + BALLOON_DIAMETER
    )
    _telemetry.event(
        "drawing.cluster_ring_fit",
        cluster=cluster,
        outline_mm=tuple(value * 1000.0 for value in outline),
        shift_mm=tuple(value * 1000.0 for value in shift),
        overflows=tuple(overflows),
    )
    if overflows:
        _telemetry.warn(
            f"{label}: balloon ring estimate overflows ({'; '.join(overflows)}); the audit decides"
        )
    _shift_view(adapter, view, shift, label=f"{label} ring fit")
    stems = sorted(
        {instance.stem for instance in facts.instances if instance.name in names},
        key=lambda stem: int(items[stem]),
    )
    balloon_items = tuple((stem, items[stem]) for stem in stems)
    balloons, anchored = _head_anchored_balloons(
        adapter, view, cluster, facts, items, label=label
    )
    balloons += add_component_bom_balloons(
        adapter,
        view,
        items=tuple(item for item in balloon_items if item[0] not in anchored),
        label=f"drive-train {cluster} BOM coverage",
        margin=CLUSTER_BALLOON_MARGIN,
    )
    # One ring over every balloon, anchored ones included, at this sheet's
    # clearance; the shared call above ringed only its own.
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
        f"{int(scale[0])}:{int(scale[1])}; ITEMS PER SHEET 2",
    )
    return _balloon_annotations(balloons)


def _place_sequence_sheet(adapter: Any, facts: SourceFacts) -> list[str]:
    _activate_sheet(adapter, SHEET_NAMES[SEQUENCE_SHEET - 1])
    _heading(adapter, SEQUENCE_SHEET)
    _reference_iso(
        adapter, caption="FINISHED ASSEMBLY 1:8", label="sequence reference isometric"
    )
    findings = _stack_note_field(
        adapter,
        (
            (
                "cone and crank sequence",
                CONE_CRANK_STEPS.format(cone_gears=facts.count("cone-gear")),
            ),
            ("general assembly notes", CONSUMABLES_NOTES),
        ),
        NOTE_FIELD_LEFT,
        label=f"sheet {SEQUENCE_SHEET} left note field",
    )
    # The right field stays empty: it is reserved for D1.
    return findings


def _place_bank_sheet(adapter: Any, facts: SourceFacts) -> list[str]:
    _activate_sheet(adapter, SHEET_NAMES[BANK_SHEET - 1])
    _heading(adapter, BANK_SHEET)
    _reference_iso(adapter, caption="FINISHED ASSEMBLY 1:8", label="bank reference isometric")
    return _stack_note_field(
        adapter,
        (
            (
                "cylinder bank sequence",
                BANK_STEPS.format(cylinder_gears=facts.count("cylinder-gear")),
            ),
        ),
        NOTE_FIELD_LEFT,
        label=f"sheet {BANK_SHEET} left note field",
    )


def _place_fit_sheet(adapter: Any, facts: SourceFacts) -> list[str]:
    _activate_sheet(adapter, SHEET_NAMES[FIT_SHEET - 1])
    _heading(adapter, FIT_SHEET)
    _reference_iso(adapter, caption="FINISHED ASSEMBLY 1:8", label="fit reference isometric")
    findings = _stack_note_field(
        adapter,
        (
            (
                "pinion rig sequence",
                RIG_STEPS.format(
                    cam_pins=facts.count("pinion-cam-pin"),
                    pivot_blocks=facts.count("pinion-pivot-block"),
                    cams=facts.count("pinion-cam"),
                    slotted=facts.count("slotted-screw"),
                ),
            ),
        ),
        NOTE_FIELD_LEFT,
        label=f"sheet {FIT_SHEET} left note field",
    )
    findings += _stack_note_field(
        adapter,
        (
            ("cone station table", station_table_text(facts.cone_rows())),
            ("fit placeholder", FIT_PLACEHOLDER),
        ),
        ISO_RIGHT_FIELD,
        label=f"sheet {FIT_SHEET} right note field",
    )
    return findings


def _place_checks_sheet(adapter: Any, facts: SourceFacts) -> list[str]:
    _activate_sheet(adapter, SHEET_NAMES[CHECKS_SHEET - 1])
    _heading(adapter, CHECKS_SHEET)
    _reference_iso(
        adapter, caption="CHECK REFERENCE 1:8", label="checks reference isometric"
    )
    findings = _stack_note_field(
        adapter,
        (("functional checks", CHECKS.format(cone_gears=facts.count("cone-gear"))),),
        NOTE_FIELD_LEFT,
        label=f"sheet {CHECKS_SHEET} left note field",
    )
    findings += _stack_note_field(
        adapter,
        (
            ("saved pose", SETUP_NOTES),
            (
                "external interfaces",
                INTERFACE_NOTES.format(
                    slotted=facts.count("slotted-screw"),
                    foot=facts.count("foot-screw"),
                    hold_down=facts.count("pedestal-hold-down-screw"),
                ),
            ),
        ),
        ISO_RIGHT_FIELD,
        label=f"sheet {CHECKS_SHEET} right note field",
    )
    return findings


def _place_package(adapter: Any, facts: SourceFacts) -> None:
    _create_package_sheets(adapter)
    findings = _place_assembled_sheet(adapter)
    bom_name, items = _place_bom_sheet(adapter, facts)
    cluster_balloons: dict[str, dict[str, Any]] = {}
    for cluster, number in CLUSTER_SHEETS.items():
        cluster_balloons[SHEET_NAMES[number - 1]] = _place_cluster_sheet(
            adapter, cluster, facts, bom_name=bom_name, items=items
        )
    findings += _place_sequence_sheet(adapter, facts)
    findings += _place_bank_sheet(adapter, facts)
    findings += _place_fit_sheet(adapter, facts)
    findings += _place_checks_sheet(adapter, facts)
    for sheet_name, sheet_balloons in cluster_balloons.items():
        _final_balloon_uncross(adapter, sheet_name, sheet_balloons)
    _check_package_layout(adapter, findings)


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
            _place_package(adapter, facts)
            artifacts = await finalize_drawing(
                adapter,
                OUTPUTS,
                layout=SPEC.layout,
                pdf_title="Drive-Train Assembly Drawing Package",
                scale=ASSEMBLED_SCALE,
                expected_sheet_names=SHEET_NAMES,
                sheet_layouts=SHEET_LAYOUTS,
                sheet_scales=SHEET_SCALES,
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
