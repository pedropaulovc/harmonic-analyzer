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
  bands stay at the title block's .XX +/-0.51. The web between the tap
  drill's point and the knife-bore crown is >= 2.0 mm at the deepest limit
  (1.5 mm hard floor), and the tap never has to reach the bottom of its hole.
* Option D: keep the #10-24 tip and raise the seat on a boss that rises from
  the mount top into the casting's existing hanger-stud hole, so the tap has
  room above the bore crown.

Geometry, top down: the stud's Ø12.7 shank passes the Ø13.49 casting hole; its
shoulder SEATS on the boss top (the seat plane); the #10-24 tip threads into
a blind tap through the boss into the block, above the Ø12 knife bore.
All depths below are measured DOWN from the seat plane.

The lengths are DERIVED down the stack, each rounded up to a 0.05-mm print
value (the boss height to 0.5 mm): tip from the engagement, usable thread from
the longest tip, drill from the thread minimum plus the tap lead, and the boss
height from the drill's deepest point plus the crown web.
"""

from __future__ import annotations

import math

from _hole_spec import CLEARANCE_MM, DRILL_POINT_H, TAP_DRILL_MM, THREAD_MAJOR_MM

# General tolerances as the title block PRINTS them (cad/config/title_block.yaml).
TITLE_BLOCK_X_MM = 0.8  # .X
TITLE_BLOCK_XX_MM = 0.51  # .XX
X_BAND_MM = (-TITLE_BLOCK_X_MM, TITLE_BLOCK_X_MM)
XX_BAND_MM = (-TITLE_BLOCK_XX_MM, TITLE_BLOCK_XX_MM)
_PRINT_STEP_MM = 0.05
_BOSS_STEP_MM = 0.5


def _round_up(value_mm: float, step_mm: float = _PRINT_STEP_MM) -> float:
    """The smallest multiple of ``step_mm`` at or above ``value_mm``."""
    return round(math.ceil(value_mm / step_mm - 1e-9) * step_mm, 6)


# --- the engaging thread -----------------------------------------------------
THREAD = "#10-24"
THREAD_CLASS_INTERNAL = "2B"
THREAD_PITCH_MM = 25.4 / 24.0
THREAD_MAJOR_DIA_MM = THREAD_MAJOR_MM[THREAD]  # 4.826
TAP_DRILL_DIA_MM = TAP_DRILL_MM[THREAD]  # 3.797

# machining-dfm.md:73 + user ruling: 1.5 x the engaging thread's major diameter.
REQUIRED_ENGAGEMENT_MM = 1.5 * THREAD_MAJOR_DIA_MM  # 7.239

# --- casting (top frame integral crossbar; pinned by test to its models) -----
CASTING_UNDERSIDE_Y = 999.7
CASTING_TOP_Y = 1036.2
CASTING_STUD_HOLE_DIA_MM = CLEARANCE_MM[("1/2", "close")]  # 13.492, plain thru

# --- knife contact line (the bore crown; pinned by test to build_knife_mount) --
KNIFE_CONTACT_Y = 984.834  # KNIFE 979.7 + the hex trunnion's half height

# --- stud tip (turned, die-cut; knife-hanger stud) ----------------------------
# One direct dimension, shoulder face -> tip end. The die runout beside the
# shoulder (<= 2P: a split die's lead leaves 1.5-2 incomplete threads, ~1P
# flipped) and the 45-degree tip chamfer are not engagement.
STUD_TIP_CHAMFER_MAX_MM = 0.5
STUD_THREAD_RELIEF_MAX_MM = 2.0 * THREAD_PITCH_MM  # 2.117, die runout
STUD_TIP_LENGTH_DEVIATIONS_MM = XX_BAND_MM
STUD_TIP_LENGTH_MM = _round_up(
    REQUIRED_ENGAGEMENT_MM
    + STUD_TIP_CHAMFER_MAX_MM
    + STUD_THREAD_RELIEF_MAX_MM
    - STUD_TIP_LENGTH_DEVIATIONS_MM[0]
)  # 10.40

# --- mount tap -----------------------------------------------------------------
# The usable full thread is a MINIMUM callout (the drill caps it) that the
# longest tip still seats inside. The drill runs three pitches past it, so a
# bottoming tap (<= 2P lead) reaches it with a pitch to spare: the thread
# never depends on the tap reaching the bottom of the hole.
TAP_THREAD_DEPTH_MIN_MM = _round_up(
    STUD_TIP_LENGTH_MM + STUD_TIP_LENGTH_DEVIATIONS_MM[1]
)  # 10.95
TAP_LEAD_ALLOWANCE_PITCHES = 3.0
TAP_DRILL_DEPTH_DEVIATIONS_MM = XX_BAND_MM
TAP_DRILL_DEPTH_MM = _round_up(
    TAP_THREAD_DEPTH_MIN_MM
    + TAP_LEAD_ALLOWANCE_PITCHES * THREAD_PITCH_MM
    - TAP_DRILL_DEPTH_DEVIATIONS_MM[0]
)  # 14.65
# Title-block edge break at the tap mouth (no countersink is called out).
TAP_MOUTH_COUNTERSINK_DIA_MM = 0.0
TAP_MOUTH_COUNTERSINK_DEPTH_MM = 0.0
TAP_MOUTH_EDGE_BREAK_MM = 0.25
# Adverse drill-point allowances: oversize drill, 1 degree blunter point.
DRILLED_HOLE_DIAMETER_PLUS_MM = 0.10
DRILL_POINT_MIN_INCLUDED_ANGLE_DEG = 117.0
TAP_DRILL_POINT_HEIGHT_MM = 0.5 * TAP_DRILL_DIA_MM * DRILL_POINT_H
TAP_DRILL_POINT_HEIGHT_MAX_MM = (
    0.5
    * (TAP_DRILL_DIA_MM + DRILLED_HOLE_DIAMETER_PLUS_MM)
    / math.tan(math.radians(DRILL_POINT_MIN_INCLUDED_ANGLE_DEG / 2.0))
)
TAP_DRILL_APEX_DEPTH_MAX_MM = (
    TAP_DRILL_DEPTH_MM + TAP_DRILL_DEPTH_DEVIATIONS_MM[1] + TAP_DRILL_POINT_HEIGHT_MAX_MM
)

# --- mount block top and boss -------------------------------------------------
# The boss prints one-place (.X): nothing about it needs .XX once the stack
# below absorbs the looser band (Codex machinist review, knife-cc-12).
BOSS_DIA_MM = 9.5  # round boss, concentric with the tap
BOSS_DIA_DEVIATIONS_MM = X_BAND_MM
BOSS_HEIGHT_DEVIATIONS_MM = X_BAND_MM
# The block top hangs MOUNT_GAP below the casting underside: the boss-height
# band plus the original 0.25 clearance (knife-cc-1..11) held at the short-boss
# limit, so the block top never lands on the casting before the shoulder seats.
MOUNT_GAP_MIN_MM_REQUIRED = 0.25
MOUNT_GAP = _round_up(MOUNT_GAP_MIN_MM_REQUIRED - BOSS_HEIGHT_DEVIATIONS_MM[0])  # 1.05
MOUNT_BLOCK_TOP_Y = CASTING_UNDERSIDE_Y - MOUNT_GAP  # 998.65
BLOCK_TOP_ABOVE_CROWN_MM = MOUNT_BLOCK_TOP_Y - KNIFE_CONTACT_Y  # 13.816
# The mount dimensions its bore from the BLOCK top (knife_mount_spec), so the
# crown's adverse depth below the seat stacks the boss-height band, the
# BoreFromTop band and half the bore-diameter band. BoreFromTop rides the
# title block's .XX (Codex knife-cc-17 over-spec; Main 2026-09-23): .X would
# drop the crown web under its 2.0 target and the fitted-stud gap under 0.25.
BORE_FROM_TOP_TOLERANCE_MM = TITLE_BLOCK_XX_MM
BORE_DIAMETER_PLUS_MM = 0.20
CROWN_WEB_TARGET_MM = 2.0
BOSS_HEIGHT_MIN_REQUIRED_MM = (
    TAP_DRILL_APEX_DEPTH_MAX_MM
    + CROWN_WEB_TARGET_MM
    - BLOCK_TOP_ABOVE_CROWN_MM
    - BOSS_HEIGHT_DEVIATIONS_MM[0]
    + BORE_FROM_TOP_TOLERANCE_MM
    + BORE_DIAMETER_PLUS_MM / 2.0
)  # 5.538
BOSS_HEIGHT_MM = _round_up(BOSS_HEIGHT_MIN_REQUIRED_MM, _BOSS_STEP_MM)  # 6.0
SHOULDER_SEAT_Y = MOUNT_BLOCK_TOP_Y + BOSS_HEIGHT_MM  # 1004.65, the seat plane

# --- knife-bore crown below the seat -------------------------------------------
KNIFE_BORE_CROWN_DEPTH_MM = SHOULDER_SEAT_Y - KNIFE_CONTACT_Y  # 19.816
KNIFE_BORE_CROWN_DEPTH_MIN_MM = (
    KNIFE_BORE_CROWN_DEPTH_MM
    + BOSS_HEIGHT_DEVIATIONS_MM[0]
    - BORE_FROM_TOP_TOLERANCE_MM
    - BORE_DIAMETER_PLUS_MM / 2.0
)

# --- derived limits -------------------------------------------------------------
STUD_TIP_LENGTH_MIN_MM = STUD_TIP_LENGTH_MM + STUD_TIP_LENGTH_DEVIATIONS_MM[0]
STUD_TIP_LENGTH_MAX_MM = STUD_TIP_LENGTH_MM + STUD_TIP_LENGTH_DEVIATIONS_MM[1]
TAP_DRILL_DEPTH_MIN_MM = TAP_DRILL_DEPTH_MM + TAP_DRILL_DEPTH_DEVIATIONS_MM[0]
TAP_DRILL_DEPTH_MAX_MM = TAP_DRILL_DEPTH_MM + TAP_DRILL_DEPTH_DEVIATIONS_MM[1]
TAP_MOUTH_ALLOWANCE_MM = max(
    TAP_MOUTH_COUNTERSINK_DEPTH_MM, TAP_MOUTH_EDGE_BREAK_MM
)
# Engagement = overlap of the stud's full thread [relief, tip - chamfer] with
# the tap's full thread [mouth allowance, usable minimum], both from the seat.
MIN_ENGAGEMENT_MM = min(
    STUD_TIP_LENGTH_MIN_MM - STUD_TIP_CHAMFER_MAX_MM, TAP_THREAD_DEPTH_MIN_MM
) - max(STUD_THREAD_RELIEF_MAX_MM, TAP_MOUTH_ALLOWANCE_MM)
TAP_LEAD_MIN_MM = TAP_DRILL_DEPTH_MIN_MM - TAP_THREAD_DEPTH_MIN_MM
MIN_CROWN_WEB_MM = KNIFE_BORE_CROWN_DEPTH_MIN_MM - TAP_DRILL_APEX_DEPTH_MAX_MM
BOSS_MAX_RADIUS_MM = (BOSS_DIA_MM + BOSS_DIA_DEVIATIONS_MM[1]) / 2.0
BOSS_HOLE_RADIAL_CLEARANCE_MM = CASTING_STUD_HOLE_DIA_MM / 2.0 - BOSS_MAX_RADIUS_MM
BOSS_WALL_MIN_MM = (
    BOSS_DIA_MM + BOSS_DIA_DEVIATIONS_MM[0] - THREAD_MAJOR_DIA_MM
) / 2.0
MOUNT_GAP_MIN_MM = MOUNT_GAP + BOSS_HEIGHT_DEVIATIONS_MM[0]
# With the stud cut to the measured seat-to-knife-line stack (MHA-A07 sheet 4)
# the knife line is fixed instead: the boss band cancels and the block top
# follows the crown's height above the bore axis.
MOUNT_GAP_MIN_FITTED_MM = (
    MOUNT_GAP - BORE_FROM_TOP_TOLERANCE_MM - BORE_DIAMETER_PLUS_MM / 2.0
)
# How far the tallest boss rises into the casting hole, against the crossbar.
BOSS_PENETRATION_MAX_MM = (
    SHOULDER_SEAT_Y + BOSS_HEIGHT_DEVIATIONS_MM[1] - CASTING_UNDERSIDE_Y
)
CASTING_CROSSBAR_HEIGHT_MM = CASTING_TOP_Y - CASTING_UNDERSIDE_Y

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
if MIN_CROWN_WEB_MM < CROWN_WEB_TARGET_MM - 1e-9:
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
if MOUNT_GAP_MIN_MM < MOUNT_GAP_MIN_MM_REQUIRED - 1e-9:
    raise AssertionError(
        f"knife-mount block top clears the casting by only {MOUNT_GAP_MIN_MM:.3f} mm "
        "with the boss at its shortest"
    )
if MOUNT_GAP_MIN_FITTED_MM < MOUNT_GAP_MIN_MM_REQUIRED - 1e-9:
    raise AssertionError(
        f"knife-mount block top clears the casting by only "
        f"{MOUNT_GAP_MIN_FITTED_MM:.3f} mm with the stud fitted to the knife line "
        "and the bore at its adverse location"
    )
if BOSS_PENETRATION_MAX_MM > CASTING_CROSSBAR_HEIGHT_MM / 2.0:
    raise AssertionError(
        f"knife-mount boss rises {BOSS_PENETRATION_MAX_MM:.3f} mm into the "
        f"{CASTING_CROSSBAR_HEIGHT_MM:.1f} mm crossbar, past half its height"
    )
