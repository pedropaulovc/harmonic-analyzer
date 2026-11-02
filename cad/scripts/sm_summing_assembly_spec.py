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
SPRING_SCREW = "sm-gooseneck-spring-screw"

# Every component family and its count, in the builder's insertion order: the
# builder places, the explode moves and the drawing's BOM proves exactly this.
QUANTITIES = {
    KNIFE_MOUNT: 2,
    HANGER_WASHER: 2,
    HANGER_BOLT: 2,
    DOWEL: 4,
    LEVER: 1,
    BOSS_HOOK: 1,
    BOSS_JAM_NUT: 1,
    COUNTER_SPRING: 1,
    GOOSENECK: 1,
    SPRING_SCREW: 1,
}

# --- Knife-hanger bolt fit-up ---------------------------------------------------
# Each MHA-SM-VN-52 is cut at this assembly to the stack measured at its own
# crossbar hole -- crossbar underside to the top of the MHA-SM-VN-54 washer
# seated on the faced top -- plus this reach into its knife mount's tap. The
# frame's printed grip band and the washer's catalogue thickness spread are
# measured out of the reach; only this cut band reaches the tap. Three
# decimal-inch places, so the sheet prints it as ".351 ±.006".
HANGER_FIT_REACH = 8.9154  # .351
HANGER_FIT_REACH_TOL = 0.1524  # .006
HANGER_FIT_REACH_PLACES = 3

# --- Assembly settings, as model dimensions -------------------------------------
# Two blanked Front-plane construction sketches in the assembly (sketch x =
# machine X, sketch y = machine Y), each driven from globals and marked for the
# drawing, which shows each in the one view that dimensions it.
#
# CounterSetting: the MHA-SM-04 axis over the counter spring, measured up the
# spring's own axis from the knife-edge contact level. Sliding the gooseneck's
# sleeve in the frame hub sets it until the lever is level, so it prints as a
# reference nominal.
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
# rounds up onto the .001 grid, the counter-screw reference prints .XX.
ROCK_PRECISION = 3
_ROCK_GRID_MM = 25.4 / 10**ROCK_PRECISION
BOSS_ROCK_TRAVEL = round(
    math.ceil(
        min(abs(_boss_face_rise(_FLOOR)), abs(_boss_face_rise(-_FLOOR))) / _ROCK_GRID_MM
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
