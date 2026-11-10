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
import ha_harmonic_analyzer_assembly_steps as ha_steps
import fr_top_frame_spec as top_frame
import sm_vn_knife_mount_dowel_spec as knife_dowel
from _assembly_contract import assembly_contract
from _inch_fraction import inch_fraction
from _title_block_units import LENGTH_UNITS, render_number
from sm_knife_mount_spec import (
    KNIFE_GAUGE_BAR_CLEARANCE_IN,
    KNIFE_GAUGE_BAR_DIA,
    KNIFE_GAUGE_BAR_LENGTH_IN,
)
from sm_summing_assembly_spec import (
    BOSS_HOOK,
    BOSS_JAM_NUT,
    BOSS_ROCK_TRAVEL,
    COUNTER_DIMENSION,
    COUNTER_FEATURE,
    COUNTER_SPRING,
    DOWEL,
    END_PLUG,
    GOOSENECK,
    HANGER_BOLT,
    HANGER_FIT_REACH,
    HANGER_FIT_REACH_PLACES,
    HANGER_WASHER,
    KNIFE_FREE_ROCK_FLOOR_DEG,
    KNIFE_MOUNT,
    LEVER,
    QUANTITIES,
    ROCK_DIMENSION,
    ROCK_FEATURE,
    ROCK_PRECISION,
    SPRING_SCREW,
)

DRAWING_NUMBER = "MHA-SM-00"
# Printed lengths are in the assembly contract's drawing_unit.
# A literal stem: the build graph narrows this drawing's assemblies/*
# dependency to exactly the contracts its closure names.
UNIT = assembly_contract("sm-summing").drawing_unit
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
    GOOSENECK: "COUNTER-SPRING GOOSENECK, BENT TUBE",
    END_PLUG: "GOOSENECK END PLUG",
    SPRING_SCREW: "GOOSENECK SHOULDER SCREW",
}
if set(BOM_DESCRIPTIONS) != set(QUANTITIES):
    raise AssertionError("summing BOM description coverage is incomplete")

LEVEL_CRITERION = f"LEVEL WITHIN ±{LEVEL_TOLERANCE_DEG:g}°"
# The cut length prints bare: the title block's three-place band holds it
# (Delegated ruling 2026-11-07 (Main), no precedent; owner review #2144 --
# the MHA-MG-08 clamp precedent: a converted band goes to the title block).
HANGER_FIT_CUT = _length(HANGER_FIT_REACH, HANGER_FIT_REACH_PLACES)
ROCK_TRAVEL_MIN = f"{_length(BOSS_ROCK_TRAVEL, ROCK_PRECISION)} MIN"
# The hub set screw bears on the bare .065 wall (owner rulings 2026-11-08
# (Pedro), #2315): snug, to fr_top_frame_spec's torque limit.
HUB_SET_SCREW_TORQUE = (
    f"SNUG, {top_frame.SET_SCREW_TORQUE_MAX_IN_LB:g} IN-LB MAX"
)
# The knife-mount gauge bar (Owner ruling 2026-11-08 (Pedro), #2144 item
# 11.3): a tool named in the steps, not a BOM part.  Owner ruling 2026-11-10
# (Pedro), #2334, S2: an 8.0 in bar, long enough to pass both mounts (outer
# faces 7.41 apart), not a 2 in class ZZ pin.  No gauge class comes that
# long, so its fit route is a matched fit to the mounts it gauges: the
# reference Ø and the diametral clearance in each bore (rule 4).
_KNIFE_GAUGE_BAR_CLEARANCE = "-".join(
    f"{value:.4f}".lstrip("0") for value in KNIFE_GAUGE_BAR_CLEARANCE_IN
)
KNIFE_GAUGE_BAR = (
    f"(Ø{_length(KNIFE_GAUGE_BAR_DIA, 4)}) X "
    f"{_length(KNIFE_GAUGE_BAR_LENGTH_IN * 25.4, 1)} LONG GAUGE BAR, "
    f"{_KNIFE_GAUGE_BAR_CLEARANCE} DIAMETRAL CLEARANCE IN EACH MHA-SM-02 BORE"
)
# The 1:1 knife-edge view is DETAIL A, circled on the sheet 1 front view
# (rule 9: a view named only in prose is unlabelled).
DETAIL_LETTER = "A"
DETAIL_TITLE = f"DETAIL {DETAIL_LETTER}"
BOND_GRADE = "LOCTITE 638"
# The lever's bracket taps are spotted through the magnifying bracket's
# flange holes (sm Q7 ruling): the lever sheet prints their stations as REF.
BRACKET_NUMBER = "MHA-MG-01"
# Callouts print below the value, where line breaks print.
DIMENSION_CALLOUTS = {
    COUNTER_DIMENSION: "SET AT ASSEMBLY:\nGOOSENECK HEIGHT\nFOR LEVER LEVEL",
    ROCK_DIMENSION: "MIN EACH WAY\nFROM LEVEL",
}

# --- Fitter package text ----------------------------------------------------------
EXPLODED_CAPTION = "EXPLODED VIEW - ASSEMBLY SEQUENCE ON SHEETS 3-4"
ASSEMBLED_NOTES = (
    "NOTES:",
    "1. NOT SHOWN: TOP FRAME MHA-FR-02. EACH KNIFE-MOUNT TOP SEAT CLAMPS TO "
    "ITS CROSSBAR UNDERSIDE; EACH WASHER SEATS ON THE CROSSBAR'S FACED TOP. "
    "THE GOOSENECK POST STANDS IN THE FRAME'S GOOSENECK HUB.",
    "2. LEVER SHOWN LEVEL, RESTING ON THE KNIFE EDGE (TOP RIDGE OF EACH HEX "
    "TRUNNION) UNDER THE TOP OF EACH MOUNT BORE.",
    f"3. LEVEL SETTING: {LEVEL_CRITERION}, SHEET 4 STEP 10.",
    f"4. {BOND_GRADE} BOND (STEP 1B): DEGREASE DOWEL AND HOLE; COAT THE "
    "DOWEL, NEVER THE BLIND HOLE; PRESS IT TO THE HOLE FLOOR; CURE 24 H "
    "BEFORE STEP 5. ACCEPT: IT DOES NOT TURN OR SLIDE BY HAND.",
    "5. LOCTITE 638 BOND (STEP 8): DEGREASE THE MHA-SM-05 SPIGOT AND THE "
    "MHA-SM-01 BORE; COAT THE SPIGOT; PUSH IT IN UNTIL THE HEAD SEATS SQUARE "
    "AND FLUSH ON THE TUBE'S FACED END; CURE 24 H BEFORE STEP 8A. ACCEPT: IT "
    "DOES NOT TURN OR PULL OUT BY HAND.",
)
# The fitter's order; sm_summing_explode_spec.EXPLODE_STEPS runs it backwards.
# A step does one thing (rule 22): a numbered step's own sub-steps carry a
# letter (1A, 1B, ...; no I or O), so the numbers other sheets and
# joint_retention cite (cut at 4 on MHA-SM-VN-52, hanger joint complete at 6,
# shoulder screw at 8B, level at 10) stay put. Steps 1-8 are done on the top
# frame, steps 9-10 at final assembly (MHA-HA-00). Owner ruling 2026-10-24
# (T+H3): the dowels press into the crossbar before the mounts go on. Steps
# 3-3C (sm Q7) transfer the bracket taps through their mate: Delegated
# ruling 2026-11-07 (Main), no precedent; owner review #2144. They are
# their own step and the washers seat under step 1 with the dowels (both
# hanger-hole preparation): machinist review of farm build
# 20261110T204245.238203Z found the bracket work buried under step 1. Owner ruling
# 2026-11-10 (Pedro), #2334, S1: each MHA-SM-02 arrives finished, its tap
# cut on the part, so the former knife-mount transfer (sm Q3: hang it
# soft, spot, drill, tap, harden) is gone. Owner ruling 2026-11-08 (Pedro),
# #2144 item 11.3 (scheme S1): one dowel per mount; with both bolts
# finger-tight a gauge bar through both bores sets the mounts' yaw, the
# bolts are tightened and the bar must slide out (step 5). The lever's
# rigid outward stubs cannot enter two fixed bores, so the rear mount comes
# off to take its stub and is
# re-hung and swung until the rock gauge passes (step 6;
# build_sm_summing_assembly's rock and rear-yaw budgets). Owner ruling
# 2026-11-08 (Pedro), #2144 item 11.4: the upper eye rides free on the
# shoulder screw (step 8B, check 3), superseding #1951's clamped eye.
# Owner rulings 2026-11-08 (Pedro), #2315: step 8 bonds the MHA-SM-05 end
# plug into MHA-SM-01 with LOCTITE 638 (note 5; it may be done before step
# 1 and cures before the shoulder screw goes in at 8A-8B); step 10A
# tightens the hub set screw on the bare leg, to its limit, on its own.
ASSEMBLY_STEPS = (
    "1. ON THE TOP FRAME MHA-FR-02, AT EACH HANGER HOLE PRESS ONE MHA-SM-VN-53 "
    "DOWEL (TWO IN ALL), CHAMFER END FIRST, UP INTO THE BLIND HOLE BESIDE IT "
    "IN THE CROSSBAR UNDERSIDE, TO THE HOLE FLOOR.",
    "1A. CHECK THAT NO DOWEL TURNS OR SLIDES BY HAND.",
    f"1B. IF ONE DOES, OR ONE SLID IN BY HAND, BOND IT IN WITH {BOND_GRADE} "
    "PER SHEET 1 NOTE 4.",
    "1C. AT EACH HANGER HOLE SEAT AN MHA-SM-VN-54 WASHER ON THE FACED TOP.",
    "2. SPIN THE MHA-SM-VN-55 JAM NUT ONTO MHA-SM-VN-50 FROM ITS CUT END UP TO "
    "THE EYE.",
    "2A. THREAD MHA-SM-VN-50 INTO THE TAPPED BOSS OF MHA-SM-03 UNTIL ITS CUT "
    "END IS WITHIN HALF A TURN OF FLUSH WITH THE BOSS UNDERSIDE, FINISHING "
    "WITH THE EYE OPENING TOWARD THE KNIFE EDGE AND THE EYE PLANE SQUARE TO IT.",
    "2B. HOLDING THE EYE CLOCKED, RUN THE JAM NUT DOWN TO THE BOSS TOP FACE "
    "AND TIGHTEN IT.",
    f"3. CLAMP THE {BRACKET_NUMBER} FLANGE AGAINST THE COEFFICIENT-PLATE END "
    "OF MHA-SM-03, ITS TWO HOLES ON THE REF STATIONS OF THE MHA-SM-03 BRACKET "
    "TAPS WITHIN ±.005 (CALIPERS).",
    f"3A. SPOT THROUGH EACH {BRACKET_NUMBER} HOLE WITH A DRILL THAT JUST FITS "
    "THE HOLE.",
    f"3B. WITH {BRACKET_NUMBER} OFF, DRILL AND TAP BOTH SPOTS PER THE MHA-SM-03 "
    "BRACKET TAP CALLOUT.",
    f"3C. SET {BRACKET_NUMBER} ASIDE; ITS TWO MHA-MG-VN-53 SCREWS FIX IT AT "
    f"{ha_steps.step_ref('magnifier-bracket-screwed')}.",
    "4. AT EACH HANGER HOLE MEASURE CROSSBAR UNDERSIDE TO WASHER TOP AND CUT AN "
    f"MHA-SM-VN-52 TO THAT PLUS {HANGER_FIT_CUT} UNDER THE HEAD (REACH INTO "
    "MHA-SM-02 TAP: FULL THREAD, TIP CLEAR OF TAP BOTTOM); CHAMFER CUT END PER "
    "MHA-SM-VN-52.",
    "5. WITHOUT THE LEVER, HANG EACH MHA-SM-02 TOP SEAT UP WITH ITS ROUND HOLE "
    "ON THE DOWEL AT ITS HANGER HOLE.",
    "5A. TURN EACH CUT MHA-SM-VN-52 DOWN THROUGH ITS WASHER AND HOLE INTO ITS "
    "MOUNT BY HAND UNTIL ITS HEAD MEETS THE WASHER (FINGER-TIGHT).",
    f"5B. SLIDE A {KNIFE_GAUGE_BAR}, THROUGH BOTH MOUNTS.",
    "5C. TIGHTEN BOTH BOLTS UNTIL EACH TOP SEAT IS DRAWN UP FLAT TO THE "
    "CROSSBAR UNDERSIDE.",
    "5D. WITHDRAW THE BAR (CHECK 6).",
    "6. REMOVE THE REAR MOUNT'S BOLT.",
    "6A. LIFT THE REAR MOUNT OFF ITS DOWEL.",
    "6B. SLIDE THE REAR MOUNT ONTO THE REAR HEX TRUNNION OF MHA-SM-03 FROM ITS "
    "OUTER END.",
    "6C. ENTER THE FRONT TRUNNION INTO THE FRONT MOUNT'S BORE.",
    "6D. RE-HANG THE REAR MOUNT ON ITS DOWEL.",
    "6E. TURN THE REAR MOUNT'S BOLT IN BY HAND (FINGER-TIGHT).",
    "6F. CHECK: EACH TOP RIDGE RESTS UNDER THE TOP OF ITS BORE.",
    "6G. SWING THE REAR MOUNT ABOUT ITS DOWEL UNTIL THE LEVER ROCKS "
    f"{ROCK_TRAVEL_MIN} (DETAIL {DETAIL_LETTER}) EACH WAY (CHECK 2).",
    "6H. TIGHTEN THE REAR MOUNT'S BOLT UNTIL ITS TOP SEAT IS DRAWN UP FLAT TO "
    "THE CROSSBAR UNDERSIDE.",
    f"7. CHECK THE FREE ROCK AGAIN (CHECK 2, DETAIL {DETAIL_LETTER}) BEFORE THE "
    "COUNTER SPRING GOES ON.",
    # One printed line: sheet 4 is full (note 5 names the compound).
    "8. BOND MHA-SM-05 INTO MHA-SM-01 PER SHEET 1 NOTE 5 (MAY BE DONE BEFORE STEP 1).",
    "8A. PASS MHA-SM-VN-56 THROUGH THE UPPER LOOP OF MHA-SM-VN-51.",
    "8B. TURN MHA-SM-VN-56 INTO MHA-SM-05 UNTIL ITS SHOULDER SEATS ON THE END "
    "FACE; NO THREADLOCKER.",
    "9. AT FINAL ASSEMBLY (MHA-HA-00): DROP THE MHA-SM-01 POST INTO THE "
    "FRAME'S GOOSENECK HUB WITH THE HUB SET SCREW MHA-FR-VN-52 (FITTED PER "
    "MHA-FR-00) BACKED CLEAR.",
    "9A. HOOK THE LOWER LOOP OF MHA-SM-VN-51 INTO THE EYE OF MHA-SM-VN-50.",
    f"10. LEVEL SETTING, AT {ha_steps.step_ref('summing-levelled')} WITH THE "
    "MHA-CH-VN-50 CHANNEL SPRINGS HOOKED (ITS STEP "
    f"{ha_steps.step_number('channel-anchors-set')}) AND EVERY CHANNEL "
    "AMPLITUDE AT ZERO: SLIDE THE GOOSENECK POST IN ITS HUB UNTIL THE "
    f"LEVER PLATE TOP IS {LEVEL_CRITERION} (DIGITAL ANGLE GAUGE ACROSS THE "
    "PLATE). THE GOOSENECK HEIGHT REFERENCE DIMENSION ON SHEET 1 IS THE "
    "NOMINAL START.",
    "10A. TIGHTEN THE HUB SET SCREW MHA-FR-VN-52 ON THE POST, "
    f"{HUB_SET_SCREW_TORQUE}.",
)
ASSEMBLY_CHECKS = (
    "CHECKS:",
    "1. EACH MOUNT'S TOP SEAT IS FLAT TO THE CROSSBAR UNDERSIDE: A "
    f"{_length(SEAT_FEELER_MM, 3)} FEELER ENTERS NOWHERE ROUND IT; THE MOUNT "
    "DOES NOT TURN ABOUT ITS DOWEL BY HAND.",
    "2. COUNTER SPRING OFF, THE LEVER ROCKS FREELY ON ITS KNIFE EDGE: THE "
    f"OUTER EDGE OF THE BOSS TOP FACE MOVES {ROCK_TRAVEL_MIN} "
    f"(DETAIL {DETAIL_LETTER}) UP AND DOWN FROM LEVEL BEFORE A HEX FLANK "
    "TOUCHES A BORE.",
    "3. THE UPPER LOOP OF MHA-SM-VN-51 TURNS AND SLIDES FREELY ON THE SHOULDER "
    "OF MHA-SM-VN-56, UNDER ITS HEAD.",
    f"4. AFTER STEP 10A THE LEVER PLATE TOP READS {LEVEL_CRITERION} AND THE "
    "GOOSENECK POST DOES NOT TURN OR SLIDE IN ITS HUB.",
    "5. THE EYE OF MHA-SM-VN-50 CANNOT BE TURNED BY HAND: MHA-SM-VN-55 IS TIGHT ON "
    "THE BOSS TOP FACE.",
    "6. AFTER STEP 5 THE GAUGE BAR SLIDES OUT OF BOTH MOUNTS' BORES BY HAND.",
)
