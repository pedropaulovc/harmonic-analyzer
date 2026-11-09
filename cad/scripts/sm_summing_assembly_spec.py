"""Pure fitting contract for sm-summing.SLDASM (MHA-SM-00): inventory and
the two assembly settings.

Builder data only: the builder (``build_sm_summing_assembly``) places
``QUANTITIES`` and authors the two setting sketches from these values; the
package drawing (``draw_sm_summing_assembly``) proves the BOM against
``QUANTITIES`` and prints the settings as those sketches' own model
dimensions. The ``SM_EXPLODED`` presentation lives in
``sm_summing_explode_spec``. The drawing number, BOM order, the dimensions
the drawing imports, the level tolerance, the BOM descriptions, callouts,
notes, steps and checks the sheets print live in ``sm_summing_assembly_sheet``,
which only the drawing reads, so a wording edit does not rebuild the
assembly. No SolidWorks imports.

Assembly frame: machine coordinates (Y up, output side -Z). The lever rocks
on the hex trunnions' top ridge (the knife edge) at ``KNIFE_POINT``; the two
knife mounts sit at ``SUMMING_Z +/- HEX_Z_MID`` (front = +Z).
"""

from __future__ import annotations

import math

import settled_spring_seats
import sm_gooseneck_geom
import sm_gooseneck_spring_joint as spring_joint
import sm_summing_lever_spec as lever
from spring_mount_geom import COUNTER_ANCHOR_XY, KNIFE, KNIFE_CONTACT_Y

ASM_NAME = "sm-summing"

KNIFE_MOUNT = "sm-knife-mount"
HANGER_WASHER = "sm-vn-knife-hanger-washer"
HANGER_BOLT = "sm-vn-knife-hanger-stud"
DOWEL = "sm-vn-knife-mount-dowel"
LEVER = "sm-summing-lever"
BOSS_HOOK = "sm-vn-boss-hook"
BOSS_JAM_NUT = "sm-vn-boss-hook-jam-nut"
COUNTER_SPRING = "sm-vn-counter-spring"
GOOSENECK = "sm-gooseneck"
# MHA-SM-05, bonded into the gooseneck's arm end at this assembly (owner
# rulings 2026-11-08 (Pedro), #2315).
END_PLUG = "sm-gooseneck-end-plug"
SPRING_SCREW = "sm-vn-gooseneck-shoulder-screw"

# Every component family and its count, in the builder's insertion order: the
# builder places, the explode moves and the drawing's BOM proves exactly this.
QUANTITIES = {
    KNIFE_MOUNT: 2,
    HANGER_WASHER: 2,
    HANGER_BOLT: 2,
    DOWEL: 2,
    LEVER: 1,
    BOSS_HOOK: 1,
    BOSS_JAM_NUT: 1,
    COUNTER_SPRING: 1,
    GOOSENECK: 1,
    END_PLUG: 1,
    SPRING_SCREW: 1,
}

# --- Knife-hanger bolt fit-up ---------------------------------------------------
# Each MHA-SM-VN-52 is cut at this assembly to the stack measured at its own
# crossbar hole -- crossbar underside to the top of the MHA-SM-VN-54 washer
# seated on the faced top -- plus this reach into its knife mount's tap. The
# frame's printed grip band and the washer's catalogue thickness spread are
# measured out of the reach; only this cut band reaches the tap. Three
# decimal-inch places, so the sheet prints it as ".351" under the title
# block's .XXX ±.005 (the converted ±.006 band went to the title block:
# Delegated ruling 2026-11-07 (Main), no precedent; owner review #2144).
HANGER_FIT_REACH = 8.9154  # .351
HANGER_FIT_REACH_TOL = 0.127  # .005, the title block's three-place band
HANGER_FIT_REACH_PLACES = 3

# --- Knife-mount gauge bar (Owner ruling 2026-11-08 (Pedro), #2144 item 11.3) --
# A tool, not a BOM part: with each MHA-SM-02 hung on its one MHA-SM-VN-53
# dowel and its bolt finger-tight, a Ø.4720 class ZZ MINUS gauge pin
# (+.0000/-.0002 in) slides through BOTH mounts' bores; the bolts are
# tightened and the bar must slide back out.  It sets the front mount's yaw
# about its dowel (and proves both mounts' pitch); the rear mount is then
# re-hung on the lever's stub and swung until the rock gauge passes (this
# fit-up order owner-confirmed 2026-11-08 (Pedro), #2144 item 11.3;
# ``build_sm_summing_assembly`` budgets both).  Its nominal is the bore's
# smallest printed Ø, so it enters every conforming bore.
KNIFE_GAUGE_BAR_DIA_IN = 0.4720
KNIFE_GAUGE_BAR_BAND_IN = (0.0, -0.0002)  # (upper, lower), class ZZ minus
KNIFE_GAUGE_BAR_DIA = KNIFE_GAUGE_BAR_DIA_IN * 25.4  # 11.9888
KNIFE_GAUGE_BAR_DIA_MIN = (KNIFE_GAUGE_BAR_DIA_IN + min(KNIFE_GAUGE_BAR_BAND_IN)) * 25.4

# --- Assembly settings, as model dimensions -------------------------------------
# Two blanked Front-plane construction sketches in the assembly (sketch x =
# machine X, sketch y = machine Y), each driven from globals and marked for the
# drawing, which shows each in the one view that dimensions it.
#
# CounterSetting: the MHA-SM-VN-56 axis over the counter spring, measured up the
# spring's own axis from the knife-edge contact level. Sliding the gooseneck's
# bare leg in the frame hub sets it until the lever is level, so it prints as
# a reference nominal.
#
# KnifeRockGauge: how far the boss-hook face rises when the lever rocks the
# free-rock floor about the knife edge -- the free-rock acceptance in a
# distance a fitter measures at the boss, rounded up so the check is never
# looser than the floor.
SETTING_FEATURES = ("CounterSetting", "KnifeRockGauge")
COUNTER_FEATURE, ROCK_FEATURE = SETTING_FEATURES
COUNTER_DIMENSION = "CounterScrewRise"
ROCK_DIMENSION = "BossRockTravel"

KNIFE_POINT = (KNIFE[0], KNIFE_CONTACT_Y)
_COUNTER_SEAT, GOOSENECK_ORIGIN_Y = settled_spring_seats.counter_seat()
COUNTER_SCREW_POINT = (
    COUNTER_ANCHOR_XY[0],
    GOOSENECK_ORIGIN_Y + sm_gooseneck_geom.ARM_Y,
)
COUNTER_SCREW_RISE = COUNTER_SCREW_POINT[1] - KNIFE_POINT[1]
COUNTER_SCREW_OFFSET_X = KNIFE_POINT[0] - COUNTER_SCREW_POINT[0]

# --- Counter-spring arm play ---------------------------------------------------
# Owner ruling 2026-11-08 (Pedro), #2144 item 11.4, supersedes #1951's clamped
# eye: the upper eye rides free on MHA-SM-VN-56's shoulder, so it may slide
# from the end face (the native seat) out toward the knife by up to the
# joint's axial play (sm_gooseneck_spring_joint.EYE_AXIAL_PLAY_MIN/MAX).  The
# spring then swings about its lower eye on the boss hook, and its line of
# pull moves against the knife: COUNTER_ARM is that line's perpendicular
# distance from the knife-edge contact, and COUNTER_ARM_PLAY its change at the
# largest play (positive: the arm grows), with its share of the arm in
# percent.  The spring's stretch, (L**2 + play**2)**0.5 - L, is second order.
COUNTER_EYE_AXIAL_PLAY = (spring_joint.EYE_AXIAL_PLAY_MIN, spring_joint.EYE_AXIAL_PLAY_MAX)


def counter_arm(eye_shift: float) -> float:
    """The counter spring's moment arm about the knife, its upper eye shifted
    ``eye_shift`` along the shoulder (machine +X) from the native seat."""
    lower = _COUNTER_SEAT.pose.lower_eye_xy
    upper = _COUNTER_SEAT.pose.upper_eye_xy
    ux, uy = upper[0] + eye_shift - lower[0], upper[1] - lower[1]
    span = math.hypot(ux, uy)
    dx, dy = KNIFE_POINT[0] - lower[0], KNIFE_POINT[1] - lower[1]
    return abs(dx * uy - dy * ux) / span


COUNTER_ARM = counter_arm(0.0)
COUNTER_ARM_PLAY = counter_arm(COUNTER_EYE_AXIAL_PLAY[1]) - COUNTER_ARM
COUNTER_ARM_PLAY_PCT = 100.0 * COUNTER_ARM_PLAY / COUNTER_ARM

# The boss's outboard top edge, clear of the hook, where the fitter reads the rock.
BOSS_FACE_POINT = (
    COUNTER_ANCHOR_XY[0] - lever.ANCHOR_R,
    KNIFE[1] + lever.ANCHOR_H / 2.0,
)
_BOSS_ARM = (BOSS_FACE_POINT[0] - KNIFE_POINT[0], BOSS_FACE_POINT[1] - KNIFE_POINT[1])
# Floor of the knife edge's free rock each way (2026-10-09 ruling); the
# builder proves the print-worst stack still rocks at least this far.
KNIFE_FREE_ROCK_FLOOR_DEG = 5.0
_FLOOR = math.radians(KNIFE_FREE_ROCK_FLOOR_DEG)


def _boss_face_rise(angle: float) -> float:
    """Vertical travel of the boss face for a rock of ``angle`` about the knife."""
    x, y = _BOSS_ARM
    return x * math.sin(angle) + y * math.cos(angle) - y


# Printed decimal-inch places (the contract's drawing_unit): the rock gauge
# rounds up onto the .001 grid, the counter-screw reference prints .XX. The
# one gauge is read each way from level, so it carries the larger of the two
# directional travels: a fitter who sees it both ways has the floor both ways.
ROCK_PRECISION = 3
_ROCK_GRID_MM = 25.4 / 10**ROCK_PRECISION
BOSS_ROCK_TRAVEL = round(
    math.ceil(
        max(abs(_boss_face_rise(_FLOOR)), abs(_boss_face_rise(-_FLOOR))) / _ROCK_GRID_MM
    )
    * _ROCK_GRID_MM,
    6,
)
COUNTER_PRECISION = 2
DRAWING_PRECISION = {
    COUNTER_FEATURE: {COUNTER_DIMENSION: COUNTER_PRECISION},
    ROCK_FEATURE: {ROCK_DIMENSION: ROCK_PRECISION},
}

assert 0.0 < COUNTER_SCREW_RISE, COUNTER_SCREW_RISE
assert 0.0 < COUNTER_SCREW_OFFSET_X, COUNTER_SCREW_OFFSET_X
assert 0.0 < BOSS_ROCK_TRAVEL < -_BOSS_ARM[0], BOSS_ROCK_TRAVEL
