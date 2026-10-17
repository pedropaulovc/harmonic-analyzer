"""Pure fitting contract for sm-summing.SLDASM (MHA-SM-000): inventory, the
native explode and the two assembly settings.

The builder (``build_sm_summing_assembly``) authors the explode and the two
setting sketches from these values; the package drawing
(``draw_sm_summing_assembly``) proves the BOM against ``QUANTITIES`` and
prints the settings as those sketches' own model dimensions. The BOM
descriptions, callouts, notes, steps and checks the sheets print live in
``sm_summing_assembly_notes``, which only the drawing reads, so a wording
edit does not rebuild the assembly. No SolidWorks imports.

Assembly frame: machine coordinates (Y up, output side -Z). The lever rocks
on the hex trunnions' top ridge (the knife edge) at ``KNIFE_POINT``; the two
knife mounts sit at ``SUMMING_Z +/- HEX_Z_MID`` (front = +Z).
"""

from __future__ import annotations

import math

import _config
import settled_spring_seats
import sm_gooseneck_geom
import sm_summing_lever_spec as lever
from spring_mount_geom import COUNTER_ANCHOR_XY, KNIFE, KNIFE_CONTACT_Y

ASM_NAME = "sm-summing"
DRAWING_NUMBER = "MHA-SM-000"

KNIFE_MOUNT = "sm-knife-mount"
HANGER_WASHER = "vn-knife-hanger-washer"
HANGER_BOLT = "vn-knife-hanger-stud"
DOWEL = "vn-knife-mount-dowel"
LEVER = "sm-summing-lever"
BOSS_HOOK = "vn-boss-hook"
BOSS_JAM_NUT = "vn-boss-hook-jam-nut"
COUNTER_SPRING = "vn-counter-spring"
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
BOM_ORDER = tuple(QUANTITIES)

# --- Native explode (SM_EXPLODED) ---------------------------------------------
# The notes' ASSEMBLY_STEPS read back to front: the gooseneck and its screw
# lift off the spring, the screw backs out of the plug, the spring lifts off
# the boss hook
# and the hook unscrews from the lever boss, its jam nut left standing between
# the cut end and the boss (the nut goes on from the cut end before the hook
# enters the boss); then each knife-mount station (mount, its two dowels, its
# washer and bolt) slides off its hex trunnion along Z, the bolts and washers
# lift, the bolts clear their washers and the dowels leave their mounts.
# (label, families, station, axis, signed mm):
# ``station`` "front"/"back" moves only the instances at +Z/-Z of the lever
# centre plane, None every instance; all along the assembly's global axes.
# Sized for the drawing's *Isometric (it looks from +X+Y+Z): each mount clears
# its trunnion end (17.9 of slide) with room for the dowels to stand between
# mount and washer.
EXPLODED_VIEW_NAME = "SM_EXPLODED"
SOURCE_CONFIGURATION = "Default"
STATIONS = ("front", "back")
_STATION_FAMILIES = (KNIFE_MOUNT, DOWEL, HANGER_WASHER, HANGER_BOLT)
EXPLODE_STEPS: tuple[tuple[str, tuple[str, ...], str | None, str, float], ...] = (
    ("gooseneck lifts", (GOOSENECK, SPRING_SCREW), None, "y", 80.0),
    ("spring screw backs out", (SPRING_SCREW,), None, "x", 35.0),
    ("counter spring lifts off hook", (COUNTER_SPRING,), None, "y", 55.0),
    ("boss hook unscrews", (BOSS_HOOK,), None, "y", 35.0),
    ("jam nut lifts off boss", (BOSS_JAM_NUT,), None, "y", 6.0),
    ("front station slides off", _STATION_FAMILIES, "front", "z", 45.0),
    ("back station slides off", _STATION_FAMILIES, "back", "z", -45.0),
    ("hanger bolts and washers lift", (HANGER_WASHER, HANGER_BOLT), None, "y", 40.0),
    ("hanger bolts clear washers", (HANGER_BOLT,), None, "y", 55.0),
    ("dowels leave mounts", (DOWEL,), None, "y", 20.0),
)

# --- Assembly settings, as model dimensions -------------------------------------
# Two blanked Front-plane construction sketches in the assembly (sketch x =
# machine X, sketch y = machine Y), each driven from globals and marked for the
# drawing, which shows each in the one view that dimensions it.
#
# CounterSetting: the MHA-SM-004 axis over the counter spring, measured up the
# spring's own axis from the knife-edge contact level. Sliding the gooseneck
# post in the frame hub sets it until the lever is level, so it prints as a
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


ROCK_PRECISION = 2
BOSS_ROCK_TRAVEL = (
    math.ceil(
        min(abs(_boss_face_rise(_FLOOR)), abs(_boss_face_rise(-_FLOOR)))
        * 10**ROCK_PRECISION
    )
    / 10**ROCK_PRECISION
)
COUNTER_PRECISION = 1
DRAWING_DIMENSIONS = {
    COUNTER_FEATURE: {COUNTER_DIMENSION},
    ROCK_FEATURE: {ROCK_DIMENSION},
}
DRAWING_PRECISION = {
    COUNTER_FEATURE: {COUNTER_DIMENSION: COUNTER_PRECISION},
    ROCK_FEATURE: {ROCK_DIMENSION: ROCK_PRECISION},
}
# The lever is set level to the title block's general angular tolerance: the
# operating rock (about 1 deg) then stays well inside the free-rock floor.
LEVEL_TOLERANCE_DEG = float(_config.title_block("angular")["value_deg"])
if LEVEL_TOLERANCE_DEG + 1.0 >= KNIFE_FREE_ROCK_FLOOR_DEG:
    raise AssertionError("the level tolerance eats the knife edge's free rock")

assert 0.0 < COUNTER_SCREW_RISE, COUNTER_SCREW_RISE
assert 0.0 < COUNTER_SCREW_OFFSET_X, COUNTER_SCREW_OFFSET_X
assert 0.0 < BOSS_ROCK_TRAVEL < -_BOSS_ARM[0], BOSS_ROCK_TRAVEL
