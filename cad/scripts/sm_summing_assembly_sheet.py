"""Drawing-only data of the summing-lever fitter package (MHA-SM-00).

The drawing number, BOM order, the setting dimensions the drawing imports,
the level tolerance, the BOM descriptions, setting callouts, detail title,
assembled-view notes, assembly steps and checks the sheets print. Only
draw_sm_summing_assembly (and its tests) import this module; no assembly
builder may (``test_assembly_sheet_isolation`` pins it), so a wording edit
here does not rebuild the summing assembly. No SolidWorks.
"""

from __future__ import annotations

import _config
import sm_vn_knife_mount_dowel_spec as knife_dowel
from _assembly_contract import assembly_contract
from _inch_fraction import inch_fraction
from _title_block_units import LENGTH_UNITS, render_number
from sm_summing_assembly_spec import (
    ASM_NAME,
    BOSS_HOOK,
    BOSS_JAM_NUT,
    COUNTER_DIMENSION,
    COUNTER_FEATURE,
    COUNTER_SPRING,
    DOWEL,
    GOOSENECK,
    HANGER_BOLT,
    HANGER_FIT_REACH,
    HANGER_FIT_REACH_PLACES,
    HANGER_FIT_REACH_TOL,
    HANGER_WASHER,
    KNIFE_FREE_ROCK_FLOOR_DEG,
    KNIFE_MOUNT,
    LEVER,
    QUANTITIES,
    ROCK_DIMENSION,
    ROCK_FEATURE,
    SPRING_SCREW,
)

DRAWING_NUMBER = "MHA-SM-00"
# Printed lengths are in the assembly contract's drawing_unit.
UNIT = assembly_contract(ASM_NAME).drawing_unit
# The BOM lists every family in the builder's insertion order.
BOM_ORDER = tuple(QUANTITIES)
# The drawing imports exactly these, each in the one view that dimensions it.
DRAWING_DIMENSIONS = {
    COUNTER_FEATURE: {COUNTER_DIMENSION},
    ROCK_FEATURE: {ROCK_DIMENSION},
}
# The lever is set level to the title block's general angular tolerance: the
# operating rock (about 1 deg) then stays well inside the free-rock floor.
LEVEL_TOLERANCE_DEG = float(_config.title_block("angular")["value_deg"])
if LEVEL_TOLERANCE_DEG + 1.0 >= KNIFE_FREE_ROCK_FLOOR_DEG:
    raise AssertionError("the level tolerance eats the knife edge's free rock")
# The feeler check 1 tries round each mount's clamped top seat.
SEAT_FEELER_MM = 0.0508  # .002


def _length(length_mm: float, places: int) -> str:
    """A length as the sheet prints it in its drawing unit."""
    return render_number(length_mm / LENGTH_UNITS[UNIT], UNIT, places)


# The DESCRIPTION cell is drawing wording: the part numbers and vendor SKUs
# print in their own columns, so no size the part drawings own is restated.
BOM_DESCRIPTIONS = {
    KNIFE_MOUNT: "KNIFE-EDGE MOUNT",
    HANGER_WASHER: "#10 SAE FLAT WASHER",
    HANGER_BOLT: "#10-24 HEX BOLT, CUT",
    DOWEL: f"{inch_fraction(knife_dowel.DIA, what='knife-mount dowel')} DOWEL PIN",
    LEVER: "SUMMING LEVER",
    BOSS_HOOK: "#10-24 OPEN EYEBOLT, TRIMMED",
    BOSS_JAM_NUT: "#10-24 THIN HEX JAM NUT",
    COUNTER_SPRING: "COUNTER SPRING",
    GOOSENECK: "COUNTER-SPRING GOOSENECK",
    SPRING_SCREW: "GOOSENECK SPRING SCREW",
}
if set(BOM_DESCRIPTIONS) != set(QUANTITIES):
    raise AssertionError("summing BOM description coverage is incomplete")

LEVEL_CRITERION = f"LEVEL WITHIN ±{LEVEL_TOLERANCE_DEG:g}°"
HANGER_FIT_CUT = (
    f"{_length(HANGER_FIT_REACH, HANGER_FIT_REACH_PLACES)} "
    f"±{_length(HANGER_FIT_REACH_TOL, HANGER_FIT_REACH_PLACES)}"
)
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
    "1. NOT SHOWN: TOP FRAME MHA-FR-02. EACH KNIFE-MOUNT TOP SEAT CLAMPS TO "
    "ITS CROSSBAR UNDERSIDE; EACH WASHER SEATS ON THE CROSSBAR'S FACED TOP. "
    "THE GOOSENECK POST STANDS IN THE FRAME'S GOOSENECK HUB.",
    "2. LEVER SHOWN LEVEL, RESTING ON THE KNIFE EDGE (TOP RIDGE OF EACH HEX "
    "TRUNNION) UNDER THE TOP OF EACH MOUNT BORE.",
    f"3. LEVEL SETTING: {LEVEL_CRITERION}, SHEET 3 STEP 10.",
)
# The fitter's order; sm_summing_explode_spec.EXPLODE_STEPS runs it backwards.
# Steps 1 and 4-10 are done on the top frame, steps 9-10 at final assembly
# (MHA-HA-00).  Owner ruling 2026-10-24 (T+H3): the dowels press into the
# crossbar before the mounts go on; each mount then slips onto its pair.
ASSEMBLY_STEPS = (
    "1. ON THE TOP FRAME MHA-FR-02, AT EACH HANGER HOLE PRESS TWO MHA-SM-VN-53 "
    "DOWELS (FOUR IN ALL), CHAMFER END FIRST, UP INTO THE BLIND HOLES BESIDE IT "
    "IN THE CROSSBAR UNDERSIDE, EACH TO THE HOLE FLOOR.",
    "2. SPIN THE MHA-SM-VN-55 JAM NUT ONTO MHA-SM-VN-50 FROM ITS CUT END UP TO THE "
    "EYE. THREAD MHA-SM-VN-50 INTO THE TAPPED BOSS OF MHA-SM-03 UNTIL ITS CUT "
    "END IS WITHIN HALF A TURN OF FLUSH WITH THE BOSS UNDERSIDE, FINISHING "
    "WITH THE EYE OPENING TOWARD THE KNIFE EDGE AND THE EYE PLANE SQUARE TO IT. "
    "RUN THE JAM NUT DOWN TO THE BOSS TOP FACE AND, HOLDING THE EYE CLOCKED, "
    "TIGHTEN IT.",
    "3. SLIDE ONE MHA-SM-02 ONTO EACH HEX TRUNNION OF MHA-SM-03 FROM ITS "
    "OUTER END, TOP SEAT UP, SO THE TOP RIDGE OF THE HEX RESTS UNDER THE TOP "
    "OF THE BORE.",
    "4. ON THE TOP FRAME, AT EACH HANGER HOLE: SEAT AN MHA-SM-VN-54 WASHER ON THE "
    "FACED TOP, MEASURE CROSSBAR UNDERSIDE TO WASHER TOP AND CUT AN MHA-SM-VN-52 "
    f"TO THAT PLUS {HANGER_FIT_CUT} UNDER THE HEAD (REACH INTO MHA-SM-02 TAP: "
    "FULL THREAD, TIP CLEAR OF TAP BOTTOM); CHAMFER CUT END PER MHA-SM-VN-52.",
    "5. LIFT THE LEVER WITH BOTH MOUNTS UP TO THE CROSSBAR UNDERSIDE, EACH "
    "MOUNT EITHER WAY ROUND, ITS ROUND HOLE ON ONE DOWEL AND ITS OPEN SLOT ON "
    "THE OTHER.",
    "6. PASS EACH CUT MHA-SM-VN-52 DOWN THROUGH ITS WASHER AND HOLE INTO ITS "
    "MOUNT AND TURN IT IN BY HAND UNTIL ITS HEAD MEETS THE WASHER; THEN TIGHTEN "
    "UNTIL THE MOUNT'S TOP SEAT IS DRAWN UP FLAT TO THE CROSSBAR UNDERSIDE.",
    "7. CHECK THE FREE ROCK (CHECK 2, KNIFE-EDGE DETAIL) BEFORE THE COUNTER SPRING GOES "
    "ON.",
    "8. CLAMP THE UPPER LOOP OF MHA-SM-VN-51 TO THE END-PIECE FACE OF MHA-SM-01 WITH "
    "MHA-SM-04: TIGHTEN UNTIL THE LOOP IS CLAMPED AND CANNOT SWIVEL; NO "
    "THREADLOCKER.",
    "9. AT FINAL ASSEMBLY (MHA-HA-00): DROP THE MHA-SM-01 POST INTO THE "
    "FRAME'S GOOSENECK HUB WITH THE HUB SET SCREW MHA-FR-VN-52 (FITTED PER "
    "MHA-FR-00) BACKED CLEAR, AND HOOK THE LOWER LOOP OF MHA-SM-VN-51 INTO THE "
    "EYE OF MHA-SM-VN-50.",
    "10. LEVEL SETTING, WITH THE CHANNEL SPRINGS FITTED AND EVERY CHANNEL "
    "AMPLITUDE SET TO ZERO: SLIDE THE GOOSENECK POST IN ITS HUB UNTIL THE "
    f"LEVER PLATE TOP IS {LEVEL_CRITERION} (DIGITAL ANGLE GAUGE ACROSS THE "
    "PLATE), THEN TIGHTEN THE HUB SET SCREW MHA-FR-VN-52 ON THE POST. THE "
    "GOOSENECK HEIGHT REFERENCE DIMENSION ON SHEET 1 IS THE NOMINAL START.",
)
ASSEMBLY_CHECKS = (
    "CHECKS:",
    "1. EACH MOUNT'S TOP SEAT IS FLAT TO THE CROSSBAR UNDERSIDE: A "
    f"{_length(SEAT_FEELER_MM, 3)} FEELER ENTERS NOWHERE ROUND IT.",
    "2. COUNTER SPRING OFF, THE LEVER ROCKS FREELY ON ITS KNIFE EDGE: THE "
    "OUTER EDGE OF THE BOSS TOP FACE MOVES AT LEAST THE KNIFE-EDGE DETAIL DISTANCE UP "
    "AND DOWN FROM LEVEL "
    "BEFORE A HEX FLANK TOUCHES A BORE.",
    "3. THE UPPER LOOP OF MHA-SM-VN-51 CANNOT SWIVEL ON MHA-SM-04.",
    f"4. AFTER STEP 10 THE LEVER PLATE TOP READS {LEVEL_CRITERION} AND THE "
    "GOOSENECK POST DOES NOT TURN OR SLIDE IN ITS HUB.",
    "5. THE EYE OF MHA-SM-VN-50 CANNOT BE TURNED BY HAND: MHA-SM-VN-55 IS TIGHT ON "
    "THE BOSS TOP FACE.",
)
