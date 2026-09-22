r"""Knife-hanger joint interface: the stepped stud's tip in the knife-mount tap.

The single source for the joint that three slices share: the knife mount
(boss and tap), the knife-hanger stud (turned tip and shoulder) and the summing
assembly (seat plane and engagement gates). PURE DATA plus import-time
consistency checks, with no SolidWorks/COM imports, so every consumer can
import it without pulling another slice's build script.

User rulings (2026-09-22):

* Installed engagement >= 1.5 x the major diameter of the thread that engages
  (``cad/docs/machining-dfm.md:73``), proven at the tolerance limits.
* Novice machinist: thin walls and tight margins are fixed with geometry so
  bands stay near the title block's .XX +/-0.51. The web between the tap
  drill's point and the knife-bore crown is >= 2.0 mm at the deepest limit
  (1.5 mm hard floor).
* Option D: keep the #10-24 tip and raise the seat on a boss that rises from
  the mount top into the casting's existing hanger-stud hole, so the tap has
  room above the bore crown.

Geometry, top down: the stud's Ø12.7 shank passes the Ø13.49 casting hole; its
shoulder SEATS on the boss top (the seat plane); the #10-24 tip threads into
a blind tap through the boss into the block, above the Ø12 knife bore.
All depths below are measured DOWN from the seat plane.
"""

from __future__ import annotations

import math

from _hole_spec import CLEARANCE_MM, DRILL_POINT_H, TAP_DRILL_MM, THREAD_MAJOR_MM

TITLE_BLOCK_XX_MM = 0.51  # .XX general tolerance, both directions

# --- the engaging thread -----------------------------------------------------
THREAD = "#10-24"
THREAD_CLASS_INTERNAL = "2B"
THREAD_PITCH_MM = 25.4 / 24.0
THREAD_MAJOR_DIA_MM = THREAD_MAJOR_MM[THREAD]  # 4.826
TAP_DRILL_DIA_MM = TAP_DRILL_MM[THREAD]  # 3.797

# machining-dfm.md:73 + user ruling: 1.5 x the engaging thread's major diameter.
REQUIRED_ENGAGEMENT_MM = 1.5 * THREAD_MAJOR_DIA_MM  # 7.239

# --- casting (top frame integral crossbar; pinned by test to build_top_frame) --
CASTING_UNDERSIDE_Y = 999.7
CASTING_TOP_Y = 1036.2
CASTING_STUD_HOLE_DIA_MM = CLEARANCE_MM[("1/2", "close")]  # 13.492, plain thru

# --- mount block top and boss -------------------------------------------------
# The block top hangs MOUNT_GAP below the casting underside; the boss rises
# from it into the casting hole. The gap absorbs the boss-height band, so the
# block top can never land on the casting before the shoulder seats.
MOUNT_GAP = 0.75
MOUNT_BLOCK_TOP_Y = CASTING_UNDERSIDE_Y - MOUNT_GAP  # 998.95
BOSS_DIA_MM = 9.5  # round boss, concentric with the tap
BOSS_DIA_DEVIATIONS_MM = (-TITLE_BLOCK_XX_MM, TITLE_BLOCK_XX_MM)
BOSS_HEIGHT_MM = 5.0  # above the block top
BOSS_HEIGHT_DEVIATIONS_MM = (-TITLE_BLOCK_XX_MM, TITLE_BLOCK_XX_MM)
SHOULDER_SEAT_Y = MOUNT_BLOCK_TOP_Y + BOSS_HEIGHT_MM  # 1003.95, the seat plane
# Title-block edge break at the tap mouth (no countersink is called out).
TAP_MOUTH_COUNTERSINK_DIA_MM = 0.0
TAP_MOUTH_COUNTERSINK_DEPTH_MM = 0.0
TAP_MOUTH_EDGE_BREAK_MM = 0.25

# --- knife-bore crown below the seat -------------------------------------------
# Nominal crown = the knife-edge contact line, 1003.95 - 984.834 (pinned by test
# to build_knife_mount). The adverse limit stacks the boss height, the mount's
# BoreFromTop band and half its bore-diameter band (knife_mount_spec).
KNIFE_BORE_CROWN_DEPTH_MM = 19.116
BORE_FROM_TOP_TOLERANCE_MM = 0.10
BORE_DIAMETER_PLUS_MM = 0.20
KNIFE_BORE_CROWN_DEPTH_MIN_MM = (
    KNIFE_BORE_CROWN_DEPTH_MM
    + BOSS_HEIGHT_DEVIATIONS_MM[0]
    - BORE_FROM_TOP_TOLERANCE_MM
    - BORE_DIAMETER_PLUS_MM / 2.0
)

# --- stud tip (turned, die-cut; knife-hanger stud) ----------------------------
# One direct dimension, shoulder face -> tip end. The die runout beside the
# shoulder (<= 2P: a split die's lead leaves 1.5-2 incomplete threads, ~1P
# flipped) and the 45-degree tip chamfer are not engagement.
STUD_TIP_LENGTH_MM = 10.40
STUD_TIP_LENGTH_DEVIATIONS_MM = (-TITLE_BLOCK_XX_MM, TITLE_BLOCK_XX_MM)
STUD_TIP_CHAMFER_MAX_MM = 0.5
STUD_THREAD_RELIEF_MAX_MM = 2.0 * THREAD_PITCH_MM  # 2.117, die runout

# --- mount tap -----------------------------------------------------------------
# The usable full thread is a MINIMUM callout; the drill depth caps it. The
# drill runs three pitches past that minimum, so a bottoming tap (<= 2P lead)
# reaches it with a pitch to spare: the thread never depends on the tap
# reaching the bottom of the hole.
TAP_THREAD_DEPTH_MIN_MM = 10.95
TAP_LEAD_ALLOWANCE_PITCHES = 3.0
TAP_DRILL_DEPTH_MM = 14.65
TAP_DRILL_DEPTH_DEVIATIONS_MM = (-TITLE_BLOCK_XX_MM, TITLE_BLOCK_XX_MM)
# Adverse drill-point allowances: oversize drill, 1 degree blunter point.
DRILLED_HOLE_DIAMETER_PLUS_MM = 0.10
DRILL_POINT_MIN_INCLUDED_ANGLE_DEG = 117.0

# --- derived limits -------------------------------------------------------------
STUD_TIP_LENGTH_MIN_MM = STUD_TIP_LENGTH_MM + STUD_TIP_LENGTH_DEVIATIONS_MM[0]
STUD_TIP_LENGTH_MAX_MM = STUD_TIP_LENGTH_MM + STUD_TIP_LENGTH_DEVIATIONS_MM[1]
TAP_DRILL_DEPTH_MIN_MM = TAP_DRILL_DEPTH_MM + TAP_DRILL_DEPTH_DEVIATIONS_MM[0]
TAP_DRILL_DEPTH_MAX_MM = TAP_DRILL_DEPTH_MM + TAP_DRILL_DEPTH_DEVIATIONS_MM[1]
TAP_DRILL_POINT_HEIGHT_MM = 0.5 * TAP_DRILL_DIA_MM * DRILL_POINT_H
TAP_DRILL_POINT_HEIGHT_MAX_MM = (
    0.5
    * (TAP_DRILL_DIA_MM + DRILLED_HOLE_DIAMETER_PLUS_MM)
    / math.tan(math.radians(DRILL_POINT_MIN_INCLUDED_ANGLE_DEG / 2.0))
)
TAP_MOUTH_ALLOWANCE_MM = max(
    TAP_MOUTH_COUNTERSINK_DEPTH_MM, TAP_MOUTH_EDGE_BREAK_MM
)
# Engagement = overlap of the stud's full thread [relief, tip - chamfer] with
# the tap's full thread [mouth allowance, usable minimum], both from the seat.
MIN_ENGAGEMENT_MM = min(
    STUD_TIP_LENGTH_MIN_MM - STUD_TIP_CHAMFER_MAX_MM, TAP_THREAD_DEPTH_MIN_MM
) - max(STUD_THREAD_RELIEF_MAX_MM, TAP_MOUTH_ALLOWANCE_MM)
TAP_LEAD_MIN_MM = TAP_DRILL_DEPTH_MIN_MM - TAP_THREAD_DEPTH_MIN_MM
MIN_CROWN_WEB_MM = (
    KNIFE_BORE_CROWN_DEPTH_MIN_MM
    - TAP_DRILL_DEPTH_MAX_MM
    - TAP_DRILL_POINT_HEIGHT_MAX_MM
)
CROWN_WEB_TARGET_MM = 2.0
BOSS_MAX_RADIUS_MM = (BOSS_DIA_MM + BOSS_DIA_DEVIATIONS_MM[1]) / 2.0
BOSS_HOLE_RADIAL_CLEARANCE_MM = CASTING_STUD_HOLE_DIA_MM / 2.0 - BOSS_MAX_RADIUS_MM
BOSS_WALL_MIN_MM = (
    BOSS_DIA_MM + BOSS_DIA_DEVIATIONS_MM[0] - THREAD_MAJOR_DIA_MM
) / 2.0
MOUNT_GAP_MIN_MM = MOUNT_GAP + BOSS_HEIGHT_DEVIATIONS_MM[0]

# --- import-time gates ------------------------------------------------------------
if MIN_ENGAGEMENT_MM < REQUIRED_ENGAGEMENT_MM:
    raise AssertionError(
        f"knife-hanger engagement {MIN_ENGAGEMENT_MM:.3f} mm at limits is below "
        f"1.5D = {REQUIRED_ENGAGEMENT_MM:.3f} mm"
    )
if STUD_TIP_LENGTH_MAX_MM > TAP_THREAD_DEPTH_MIN_MM:
    raise AssertionError(
        "knife-hanger stud tip can run past the usable thread before its "
        "shoulder seats"
    )
if TAP_LEAD_MIN_MM < TAP_LEAD_ALLOWANCE_PITCHES * THREAD_PITCH_MM - 1e-9:
    raise AssertionError(
        f"knife-mount tap leaves {TAP_LEAD_MIN_MM:.3f} mm below the usable "
        f"thread, under {TAP_LEAD_ALLOWANCE_PITCHES:g} pitches"
    )
if MIN_CROWN_WEB_MM < CROWN_WEB_TARGET_MM:
    raise AssertionError(
        f"knife-bore crown web {MIN_CROWN_WEB_MM:.3f} mm at the deepest drill "
        f"limit is under {CROWN_WEB_TARGET_MM} mm"
    )
if BOSS_HOLE_RADIAL_CLEARANCE_MM < 1.5:
    raise AssertionError(
        f"knife-mount boss clears the casting hole by only "
        f"{BOSS_HOLE_RADIAL_CLEARANCE_MM:.3f} mm radially at maximum size"
    )
if BOSS_WALL_MIN_MM < 1.5:
    raise AssertionError(
        f"knife-mount boss wall {BOSS_WALL_MIN_MM:.3f} mm outside the thread "
        "major at minimum size is under 1.5 mm"
    )
if MOUNT_GAP_MIN_MM <= 0.0:
    raise AssertionError("knife-mount block top can land on the casting")
if SHOULDER_SEAT_Y + BOSS_HEIGHT_DEVIATIONS_MM[1] >= CASTING_TOP_Y:
    raise AssertionError("knife-mount boss rises through the casting top")
