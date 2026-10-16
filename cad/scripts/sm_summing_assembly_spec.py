"""Pure fitting contract for sm-summing.SLDASM (MHA-SM-000): inventory, the
native explode, the two assembly settings and the fitter's text.

The builder (``build_sm_summing_assembly``) authors the explode and the two
setting sketches from these values; the package drawing
(``draw_sm_summing_assembly``) proves the BOM against ``QUANTITIES`` and
prints the settings as those sketches' own model dimensions. No SolidWorks
imports.

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
# The DESCRIPTION cell is drawing wording: the part numbers and vendor SKUs
# print in their own columns, so no size the part drawings own is restated.
BOM_DESCRIPTIONS = {
    KNIFE_MOUNT: "KNIFE-EDGE MOUNT",
    HANGER_WASHER: "#10 SAE FLAT WASHER",
    HANGER_BOLT: "#10-24 HEX BOLT, CUT",
    DOWEL: "1/8 DOWEL PIN",
    LEVER: "SUMMING LEVER",
    BOSS_HOOK: "#10-24 OPEN EYEBOLT, TRIMMED",
    BOSS_JAM_NUT: "#10-24 THIN HEX JAM NUT",
    COUNTER_SPRING: "COUNTER SPRING",
    GOOSENECK: "COUNTER-SPRING GOOSENECK",
    SPRING_SCREW: "GOOSENECK SPRING SCREW",
}
if set(BOM_DESCRIPTIONS) != set(QUANTITIES):
    raise AssertionError("summing BOM description coverage is incomplete")

# --- Native explode (SM_EXPLODED) ---------------------------------------------
# ASSEMBLY_STEPS read back to front: the gooseneck and its screw lift off the
# spring, the screw backs out of the plug, the spring lifts off the boss hook
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
LEVEL_CRITERION = f"LEVEL WITHIN ±{LEVEL_TOLERANCE_DEG:g}°"
DETAIL_TITLE = "KNIFE-EDGE DETAIL (FRONT, CROPPED)"
# Callouts print below the value, where line breaks print.
DIMENSION_CALLOUTS = {
    COUNTER_DIMENSION: "SET AT ASSEMBLY:\nGOOSENECK HEIGHT\nFOR LEVER LEVEL",
    ROCK_DIMENSION: "MIN EACH WAY\nFROM LEVEL",
}

# --- Fitter package text ----------------------------------------------------------
EXPLODED_CAPTION = "EXPLODED VIEW - ASSEMBLY SEQUENCE ON SHEET 3"
ASSEMBLED_NOTES = (
    "NOTES:",
    "1. NOT SHOWN: TOP FRAME MHA-FR-002. EACH KNIFE-MOUNT TOP SEAT CLAMPS TO "
    "ITS CROSSBAR UNDERSIDE; EACH WASHER SEATS ON THE CROSSBAR'S FACED TOP. "
    "THE GOOSENECK POST STANDS IN THE FRAME'S GOOSENECK HUB.",
    "2. LEVER SHOWN LEVEL, RESTING ON THE KNIFE EDGE (TOP RIDGE OF EACH HEX "
    "TRUNNION) UNDER THE TOP OF EACH MOUNT BORE.",
    f"3. LEVEL SETTING: {LEVEL_CRITERION}, SHEET 3 STEP 9.",
)
# The fitter's order; the explode above runs it backwards. Steps 4-9 are done
# on the top frame, steps 8-9 at final assembly (MHA-HA-000).
ASSEMBLY_STEPS = (
    "1. PRESS TWO MHA-VN-051 DOWELS, CHAMFER END FIRST, INTO THE TOP-SEAT "
    "HOLES OF EACH MHA-SM-002 KNIFE MOUNT, EACH TO THE HOLE FLOOR.",
    "2. SPIN THE MHA-VN-070 JAM NUT ONTO MHA-VN-001 FROM ITS CUT END UP TO THE "
    "EYE. THREAD MHA-VN-001 INTO THE TAPPED BOSS OF MHA-SM-003 UNTIL ITS CUT "
    "END IS WITHIN HALF A TURN OF FLUSH WITH THE BOSS UNDERSIDE, FINISHING "
    "WITH THE EYE OPENING TOWARD THE KNIFE EDGE AND THE EYE PLANE SQUARE TO IT. "
    "RUN THE JAM NUT DOWN TO THE BOSS TOP FACE AND, HOLDING THE EYE CLOCKED, "
    "TIGHTEN IT.",
    "3. SLIDE ONE MHA-SM-002 ONTO EACH HEX TRUNNION OF MHA-SM-003 FROM ITS "
    "OUTER END, DOWELS UP, SO THE TOP RIDGE OF THE HEX RESTS UNDER THE TOP OF "
    "THE BORE.",
    "4. ON THE TOP FRAME: LIFT THE LEVER WITH BOTH MOUNTS UP TO THE CROSSBAR "
    "UNDERSIDE, ENTERING EACH MOUNT'S DOWELS IN THE CROSSBAR'S ROUND HOLE AND "
    "SLOT.",
    "5. PUT ONE MHA-VN-060 WASHER UNDER THE HEAD OF EACH MHA-VN-024, PASS IT "
    "DOWN THROUGH THE CROSSBAR INTO ITS MOUNT AND TIGHTEN UNTIL THE MOUNT'S "
    "TOP SEAT IS DRAWN UP FLAT TO THE CROSSBAR UNDERSIDE.",
    "6. CHECK THE FREE ROCK (CHECK 2, KNIFE-EDGE DETAIL) BEFORE THE COUNTER SPRING GOES "
    "ON.",
    "7. CLAMP THE UPPER LOOP OF MHA-VN-005 TO THE PLUG FACE OF MHA-SM-001 WITH "
    "MHA-SM-004: TIGHTEN UNTIL THE LOOP IS CLAMPED AND CANNOT SWIVEL.",
    "8. AT FINAL ASSEMBLY (MHA-HA-000): DROP THE MHA-SM-001 POST INTO THE "
    "FRAME'S GOOSENECK HUB WITH THE HUB SET SCREW MHA-VN-023 (FITTED PER "
    "MHA-FR-000) BACKED CLEAR, AND HOOK THE LOWER LOOP OF MHA-VN-005 INTO THE "
    "EYE OF MHA-VN-001.",
    "9. LEVEL SETTING, WITH THE CHANNEL SPRINGS FITTED AND EVERY CHANNEL "
    "AMPLITUDE SET TO ZERO: SLIDE THE GOOSENECK POST IN ITS HUB UNTIL THE "
    f"LEVER PLATE TOP IS {LEVEL_CRITERION} (DIGITAL ANGLE GAUGE ACROSS THE "
    "PLATE), THEN TIGHTEN THE HUB SET SCREW MHA-VN-023 ON THE POST. THE "
    "GOOSENECK HEIGHT REFERENCE DIMENSION ON SHEET 1 IS THE NOMINAL START.",
)
ASSEMBLY_CHECKS = (
    "CHECKS:",
    "1. EACH MOUNT'S TOP SEAT IS FLAT TO THE CROSSBAR UNDERSIDE: A 0.05 FEELER "
    "ENTERS NOWHERE ROUND IT.",
    "2. COUNTER SPRING OFF, THE LEVER ROCKS FREELY ON ITS KNIFE EDGE: THE "
    "OUTER EDGE OF THE BOSS TOP FACE MOVES AT LEAST THE KNIFE-EDGE DETAIL DISTANCE UP "
    "AND DOWN FROM LEVEL "
    "BEFORE A HEX FLANK TOUCHES A BORE.",
    "3. THE UPPER LOOP OF MHA-VN-005 CANNOT SWIVEL ON MHA-SM-004.",
    f"4. AFTER STEP 9 THE LEVER PLATE TOP READS {LEVEL_CRITERION} AND THE "
    "GOOSENECK POST DOES NOT TURN OR SLIDE IN ITS HUB.",
    "5. THE EYE OF MHA-VN-001 CANNOT BE TURNED BY HAND: MHA-VN-070 IS TIGHT ON "
    "THE BOSS TOP FACE.",
)

assert 0.0 < COUNTER_SCREW_RISE, COUNTER_SCREW_RISE
assert 0.0 < COUNTER_SCREW_OFFSET_X, COUNTER_SCREW_OFFSET_X
assert 0.0 < BOSS_ROCK_TRAVEL < -_BOSS_ARM[0], BOSS_ROCK_TRAVEL
