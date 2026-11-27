"""Drawing-only data of the summing-lever fitter package (MHA-SM-00).

The drawing number, BOM order, the setting dimensions the drawing imports,
the level tolerance, the BOM descriptions, setting callouts, the sheet 1
setting table, detail title and assembled-view notes the sheets print, and
the assembly steps and checks the release's ASSEMBLY.md prints
(ha_assembly_package, #2889). Only
draw_sm_summing_assembly, ha_assembly_package (and their tests) import this
module; no assembly builder may (``test_assembly_sheet_isolation`` pins it),
so a wording edit here does not rebuild the summing assembly. No SolidWorks.
"""

from __future__ import annotations

import math

import _config
import ha_harmonic_analyzer_assembly_steps as ha_steps
import fr_top_frame_spec as top_frame
import sm_vn_knife_mount_dowel_spec as knife_dowel
from _assembly_contract import assembly_contract
from _inch_fraction import inch_fraction
from _title_block_units import LENGTH_UNITS, render_number
from sm_knife_mount_spec import (
    BORE_R_MAX as KNIFE_BORE_R_MAX,
    BORE_R_MIN as KNIFE_BORE_R_MIN,
    KNIFE_GAUGE_BAR_DIA_MIN_IN,
    KNIFE_GAUGE_BAR_LENGTH_IN,
)
from sm_summing_assembly_spec import (
    BOSS_HOOK,
    BOSS_ROCK_TRAVEL,
    COUNTER_DIMENSION,
    COUNTER_FEATURE,
    COUNTER_SPRING,
    DOWEL,
    DOWEL_PROUD_DIMENSION,
    DOWEL_PROUD_FEATURE,
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
    DOWEL_PROUD_FEATURE: {DOWEL_PROUD_DIMENSION},
}
# The lever is set level to the title block's general angular tolerance: the
# operating rock (about 1 deg) then stays well inside the free-rock floor.
LEVEL_TOLERANCE_DEG = float(_config.title_block("angular")["value_deg"])
if LEVEL_TOLERANCE_DEG + 1.0 >= KNIFE_FREE_ROCK_FLOOR_DEG:
    raise AssertionError("the level tolerance eats the knife edge's free rock")
# The feeler check 1 tries round each mount's clamped top seat.
SEAT_FEELER_MM = 0.0508  # .002
# Step 3 sets each MHA-MG-01 flange hole on its REF bracket-tap station to
# the title block's three-place band, the band the station prints at.
BRACKET_STATION_TOL_MM = (
    float(_config.title_block("linear_3pl", unit=UNIT)["value_in"]) * LENGTH_UNITS["in"]
)


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
# faces 7.67 apart), not a 2 in class ZZ pin.  No gauge class comes that
# long, so the bar is made to the mounts it gauges.  Owner ruling 2026-11-24,
# fit audit S6: its make record (shop-equipment gauges.gauge-bar-0472x8, the
# tool list's TO MAKE row) reads "TURN THE BAR UNTIL IT SLIDES THROUGH BOTH
# MOUNTS; DIA .496 MIN", the floor capping the play the rock budget charges
# (.0040 in the largest bore); the matched .0026-.0041 fit of owner ruling
# 2026-11-20 (Pedro), #2499 is gone.  Owner, #3203 (2026-11-24): "Accepted
# when the bar is made; the assembly sheet says nothing more".  The step
# states no number that needs an
# instrument, only the fitter's hand check (rule 22; Main on PR #2717's
# gating clarity finding, 2026-11-13: no gauge ceremony for a setting bar).
# A bar from Ø.4960 up to just under the largest Ø.5000 bore (owner ruling
# 2026-11-23, tool audit Q13) floors to (Ø.49) at two places; a (Ø.50)
# reads as stock 1/2 in rod, which cannot pass a Ø.4985 bore (Codjiflo r1
# on PR #3444). So the reference is the two places at or under every
# conforming bar, under the bores' smallest Ø, and it shakes in the bores:
# the hand check is that it slides through both, not that it does not shake.
# The sizes run from the floor up to, not including, the largest bore.
KNIFE_GAUGE_BAR_SIZES_IN = (KNIFE_GAUGE_BAR_DIA_MIN_IN, 2.0 * KNIFE_BORE_R_MAX / 25.4)
KNIFE_GAUGE_BAR_REF_DIA_IN = math.floor(KNIFE_GAUGE_BAR_SIZES_IN[0] * 100.0 + 1e-9) / 100.0
if (
    math.floor(KNIFE_GAUGE_BAR_SIZES_IN[1] * 100.0 - 1e-6) / 100.0
    != KNIFE_GAUGE_BAR_REF_DIA_IN
    or KNIFE_GAUGE_BAR_REF_DIA_IN * 25.4 >= 2.0 * KNIFE_BORE_R_MIN
):
    raise AssertionError(
        f"gauge bars Ø{KNIFE_GAUGE_BAR_SIZES_IN[0]:.4f} up to Ø{KNIFE_GAUGE_BAR_SIZES_IN[1]:.4f} "
        f"do not all floor to a (Ø{KNIFE_GAUGE_BAR_REF_DIA_IN:.2f}) reference under the bore"
    )
KNIFE_GAUGE_BAR = (
    f"(Ø{_length(KNIFE_GAUGE_BAR_REF_DIA_IN * 25.4, 2)}) X "
    f"{_length(KNIFE_GAUGE_BAR_LENGTH_IN * 25.4, 1)} LONG GAUGE BAR"
)
KNIFE_GAUGE_BAR_FEEL = "IT SLIDES BY HAND WITHOUT FORCE"
# The 1:1 knife-edge view is DETAIL A, circled on the sheet 1 front view
# (rule 9: a view named only in prose is unlabelled); it shows the knife
# contact and the boss face the rock acceptance is read at.
DETAIL_LETTER = "A"
DETAIL_TITLE = f"DETAIL {DETAIL_LETTER}"
BOND_GRADE = "LOCTITE 638"
# The lever's bracket taps are spotted through the magnifying bracket's
# flange holes (sm Q7 ruling): the lever sheet prints their stations as REF.
BRACKET_NUMBER = "MHA-MG-01"
# Callouts print below the value, where line breaks print.
DIMENSION_CALLOUTS = {
    COUNTER_DIMENSION: "SET AT ASSEMBLY:\nGOOSENECK HEIGHT\nFOR LEVER LEVEL",
    DOWEL_PROUD_DIMENSION: "SET AT ASSEMBLY:\nDOWEL PROUD OF\nCROSSBAR UNDERSIDE",
}

# --- Sheet 1 setting table -----------------------------------------------------------
# Rule 22: a setting or acceptance that no visible single model dimension
# carries prints here, built from the values the steps use, and the steps
# and checks cite its row: the bracket transfer's station band, the hanger
# bolt's cut-to-fit length (the measured stack plus the reach; on DETAIL A
# the reach ran to the hidden tip inside MHA-SM-02), the top-seat feeler, and
# the free-rock travel read at the boss (a travel, not a feature: on DETAIL
# A its upper end landed on nothing). Machinist review of farm run
# 20261117T143446475Z-fdea6028. Delegated ruling 2026-11-17 (MainBuild), no
# precedent; owner review #2144: a value no visible single model dimension
# carries prints as a setting-table row built from the spec/sheet symbols.
# Check 1 runs once both mounts are tightened (6H), not at 5C, while the
# rear mount is still finger-tight.
SETTING_TABLE_TITLE = "SETTING TABLE - ASSEMBLY.MD STEPS CITE EACH ROW"
SETTING_TABLE_HEADER = (
    "ROW",
    "STEP",
    "SETTING",
    "MEASURE FIRST",
    "SET TO / ACCEPT",
    "CHECK WITH",
)
BRACKET_ROW = "1"
CUT_ROW = "2"
SEAT_ROW = "3"
ROCK_ROW = "4"
# The lever-level acceptance is a measured setting like the others, so it
# prints as a row the step and check cite, not as a sheet note (machinist
# review, farm run 20261119T233258920Z, gating clarity: step 10 cited no row).
# Its instrument prints as step 10 names it (codjiflo #3128): the seat row's
# acceptance reads "NO .002 FEELER ENTERS" so the wider CHECK WITH column
# still fits the top border.
LEVEL_ROW = "5"
LEVEL_GAUGE = "DIGITAL ANGLE GAUGE"
# The stack step 4 measures at each hanger hole, named in the cut row.
HANGER_STACK = "S"
SETTING_TABLE_ROWS = (
    (
        BRACKET_ROW,
        "3",
        f"{BRACKET_NUMBER} HOLES ON MHA-SM-03 STATIONS",
        "-",
        f"ON STATION ±{_length(BRACKET_STATION_TOL_MM, 3)}",
        "CALIPERS",
    ),
    (
        CUT_ROW,
        "4, 4A",
        "MHA-SM-VN-52 LENGTH UNDER HEAD",
        f"{HANGER_STACK} = CROSSBAR UNDERSIDE TO WASHER TOP",
        f"{HANGER_STACK} + {HANGER_FIT_CUT}",
        "CALIPERS",
    ),
    (
        SEAT_ROW,
        "6H (CHECK 1)",
        "MHA-SM-02 TOP SEAT ON MHA-FR-02",
        "-",
        f"NO {_length(SEAT_FEELER_MM, 3)} FEELER ENTERS",
        "FEELER GAUGE",
    ),
    (
        ROCK_ROW,
        "6G, 7 (CHECK 2)",
        "MHA-SM-03 BOSS TOP FACE OUTER EDGE",
        "LEVER LEVEL (ZERO)",
        f"{ROCK_TRAVEL_MIN} UP AND DOWN",
        "DIAL INDICATOR",
    ),
    (
        LEVEL_ROW,
        "10 (CHECK 4)",
        "MHA-SM-03 LEVER PLATE TOP",
        "-",
        LEVEL_CRITERION,
        LEVEL_GAUGE,
    ),
)


def setting_row(row: str) -> str:
    """How a step or check cites a sheet 1 setting-table row."""
    if row not in {cells[0] for cells in SETTING_TABLE_ROWS}:
        raise KeyError(f"no summing setting-table row {row!r}")
    return f"SETTING TABLE ROW {row}, SHEET 1"


# --- Fitter package text ----------------------------------------------------------
EXPLODED_CAPTION = "EXPLODED VIEW - FIT-UP STEPS IN ASSEMBLY.MD"
ASSEMBLED_NOTES = (
    "NOTES:",
    "1. NOT SHOWN: TOP FRAME MHA-FR-02. EACH KNIFE-MOUNT TOP SEAT CLAMPS TO "
    "ITS CROSSBAR UNDERSIDE; EACH WASHER SEATS ON THE CROSSBAR'S FACED TOP. "
    "THE GOOSENECK POST STANDS IN THE FRAME'S GOOSENECK HUB.",
    "2. LEVER SHOWN LEVEL, RESTING ON THE KNIFE EDGE (TOP RIDGE OF EACH HEX "
    "TRUNNION) UNDER THE TOP OF EACH MOUNT BORE.",
)
# The bonds' consumable notes print with the checks in ASSEMBLY.md (rule 22).
# A bonded dowel slid in by hand has no floor to stop it (the ream ends in a
# drill point, #3124 item 3), so steps 1B-1G hold it at its proud on a
# support while it cures and 1H accepts it, proud re-read (codjiflo #3128).
# One action a step and only degrease, apply and cure rules in the note
# (rules 22-23: the machinist reviews of farm runs 20261120T004738926Z and
# 20261120T012147518Z found the support, then the fixture actions, buried
# in one step and in the note).  Lowered upright onto the parallels, the
# frame's own weight carries the coated dowel, stood on the gauge blocks,
# up to the proud.
DOWEL_PROUD = _length(knife_dowel.PROUD, 3)
# Delegated ruling 2026-11-26 (Main), no precedent; owner form timed out on
# this option; owner review #2144 (D56): a held dowel standing low is
# accepted while it still keys the knife mount over the model's own 1.5 D
# floor (sm_vn_knife_mount_dowel_spec PRESS_ENGAGEMENT_MIN_D and
# SLIP_ENGAGEMENT_D_MIN: proud less the free end's crown), rounded up to the
# printed place: (1.5 x 3.175 + 0.406) mm = .2035, printed .204.
DOWEL_PROUD_FLOOR = render_number(
    math.ceil(
        (
            knife_dowel.PRESS_ENGAGEMENT_MIN_D * knife_dowel.DIA
            + knife_dowel.FREE_END_LEN
        )
        / LENGTH_UNITS[UNIT]
        * 1000
    )
    / 1000,
    UNIT,
    3,
)
BOND_NOTE_A = (
    f"BOND NOTE A, {BOND_GRADE} (STEPS 1E-1G): DEGREASE DOWEL AND HOLE; COAT "
    "THE DOWEL, NEVER THE BLIND HOLE; SEAT IT WITHIN THE FIXTURE TIME AND "
    "LEAVE IT UNDISTURBED; CURE 24 H AT ROOM TEMPERATURE BEFORE STEP 5. "
    "ACCEPT AT STEP 1H."
)
# Note B's acceptance is step 8C's, once the cured plug carries the seated
# shoulder screw, with its remedy at 8D (8B keeps its number for the screw
# that sm-summing.yaml and joint_retention cite): a
# plug that turns or pulls out is not held, so it still comes out and is
# bonded again (delegated ruling 2026-11-26 (Main), no precedent; owner
# review #2144 (D54); #3646).  The cure is 24 h at
# room temperature (LOCTITE 638 TDS, May 2024: about 85-90 % of full
# strength at 24 h on steel at 22-23 C, gap 0.05 mm or less).
BOND_NOTE_B = (
    "BOND NOTE B, LOCTITE 638 (STEP 8): DEGREASE THE MHA-SM-05 SPIGOT AND THE "
    "MHA-SM-01 BORE; COAT THE SPIGOT; PUSH IT IN UNTIL THE HEAD SEATS SQUARE "
    "AND FLUSH ON THE TUBE'S FACED END; CURE 24 H AT ROOM TEMPERATURE BEFORE "
    "STEP 8A. ACCEPT AT STEP 8C."
)
# The fitter's order; sm_summing_explode_spec.EXPLODE_STEPS runs it backwards.
# A step does one thing (rule 22): a numbered step's own sub-steps carry a
# letter (1A, 1B, ...; no I or O), so the numbers other sheets and
# joint_retention cite (cut at 4 on MHA-SM-VN-52, hanger joint complete at 6,
# shoulder screw at 8B, level at 10) stay put. Steps 1-8 are done on the top
# frame, steps 9-10 at final assembly (MHA-HA-00). Owner ruling 2026-10-24
# (T+H3): the dowels press into the crossbar before the mounts go on, each
# to its proud on DETAIL A, not to the ream's drill point (owner decision
# 2026-11-19, #3124 item 3). Steps
# 3-3C (sm Q7) transfer the bracket taps through their mate: Delegated
# ruling 2026-11-07 (Main), no precedent; owner review #2144. They are
# their own step and the washers seat under step 1 with the dowels (both
# hanger-hole preparation): machinist review of farm build
# 20261110T204245.238203Z found the bracket work buried under step 1. Owner ruling
# 2026-11-10 (Pedro), #2334, S1: each MHA-SM-02 arrives finished, its tap
# cut on the part, so the former knife-mount transfer (sm Q3: hang it
# soft, spot, drill, tap, harden) is gone. Owner ruling 2026-11-08 (Pedro),
# #2144 item 11.3 (scheme S1): one dowel per mount; with both bolts
# finger-tight a gauge bar through both bores sets the front mount's yaw,
# its bolt is tightened and the bar must slide out (step 5). The lever's
# rigid outward stubs cannot enter two fixed bores, so the rear mount comes
# off to take its stub and is
# re-hung and swung until the rock gauge passes (step 6;
# build_sm_summing_assembly's rock and rear-yaw budgets): 6G, not the bar,
# sets the rear mount, so its bolt stays finger-tight through step 5
# (Delegated ruling 2026-11-11 (SmGauge2400), no precedent; owner review
# #2144; #2400: tightening it there was undone at step 6). Owner ruling
# 2026-11-08 (Pedro), #2144 item 11.4: the upper eye rides free on the
# shoulder screw (step 8B, check 3), superseding #1951's clamped eye.
# Owner rulings 2026-11-08 (Pedro), #2315: step 8 bonds the MHA-SM-05 end
# plug into MHA-SM-01 with LOCTITE 638 (BOND NOTE B; it may be done before
# step 1 and cures before the shoulder screw goes in at 8A-8B); step 10A
# tightens the hub set screw on the bare leg, to its limit, on its own.
ASSEMBLY_STEPS = (
    "1. ON THE TOP FRAME MHA-FR-02, AT EACH HANGER HOLE PRESS ONE MHA-SM-VN-53 "
    "DOWEL (TWO IN ALL), CHAMFER END FIRST, UP INTO THE BLIND HOLE BESIDE IT "
    "IN THE CROSSBAR UNDERSIDE UNTIL IT STANDS PROUD OF THE UNDERSIDE BY THE "
    f"DOWEL PROUD SET ON {DETAIL_TITLE}, SHEET 1 (CALIPER DEPTH ROD).",
    "1A. CHECK THAT NO DOWEL TURNS OR SLIDES BY HAND.",
    "1B. IF ONE DOES, OR ONE SLID IN BY HAND, SET THE TOP FRAME UPRIGHT, ITS "
    "FACED UNDERSIDE DOWN ON A PAIR OF EQUAL PARALLELS ON THE SURFACE PLATE, "
    "CLEAR OF THE BOSSES AND HANGER HOLES.",
    "1C. UNDER THAT DOWEL'S HOLE WRING GAUGE BLOCKS TO THE PARALLELS' HEIGHT "
    f"LESS {DOWEL_PROUD}.",
    "1D. LIFT THE TOP FRAME OFF THE PARALLELS AND TAKE THAT DOWEL OUT.",
    f"1E. COAT THE DOWEL WITH {BOND_GRADE} PER BOND NOTE A.",
    "1F. STAND THE COATED DOWEL CHAMFER UP ON ITS GAUGE BLOCKS.",
    "1G. WITHIN THE FIXTURE TIME LOWER THE TOP FRAME BACK OVER IT ONTO THE "
    "PARALLELS, AND LEAVE IT THERE UNTIL THE BOND CURES (BOND NOTE A).",
    "1H. AFTER THE CURE, CHECK THAT THE BONDED DOWEL DOES NOT TURN OR SLIDE BY "
    f"HAND AND STANDS AT THE DOWEL PROUD SET ON {DETAIL_TITLE}, SHEET 1 "
    "(CALIPER DEPTH ROD).",
    # Delegated ruling 2026-11-27 (Main), no precedent; owner review #2144
    # (D54 item 4): a dowel that moves is not held, so it
    # pulls out cold and is bonded again from 1B; a held dowel that stands
    # high is stoned down (the mount's slip hole clears the tip by
    # SLIP_DEPTH_CLEARANCE_MIN, 1.78 mm, at the printed maximum proud).  A
    # held dowel that stands low is accepted down to DOWEL_PROUD_FLOOR (D56,
    # above); under it the top frame goes back for a drill-out (#3646).
    "1J. IF A DOWEL TURNS OR SLIDES, PULL IT OUT OF ITS HOLE.",
    "1K. IF PULLED, CLEAN THE DOWEL AND ITS HOLE TO BARE METAL.",
    "1L. IF PULLED, REDO FROM 1B.",
    "1M. IF A HELD DOWEL STANDS ABOVE THE DOWEL PROUD, STONE ITS END DOWN TO IT.",
    f"1N. IF A HELD DOWEL STANDS LOW BUT AT LEAST {DOWEL_PROUD_FLOOR} PROUD, ACCEPT IT.",
    f"1P. IF ONE STANDS UNDER {DOWEL_PROUD_FLOOR}, RETURN THE TOP FRAME MHA-FR-02 "
    "FOR A CARBIDE DRILL-OUT AND AN OVERSIZE DOWEL.",
    "1Q. AT EACH HANGER HOLE SEAT AN MHA-SM-VN-54 WASHER ON THE FACED TOP.",
    "2. THREAD MHA-SM-VN-50 INTO THE TAPPED BOSS OF MHA-SM-03 UNTIL ITS CUT "
    "END IS WITHIN HALF A TURN OF FLUSH WITH THE BOSS UNDERSIDE, FINISHING "
    "WITH THE EYE OPENING TOWARD THE KNIFE EDGE AND THE EYE PLANE SQUARE TO IT.",
    f"3. CLAMP THE {BRACKET_NUMBER} FLANGE AGAINST THE COEFFICIENT-PLATE END "
    "OF MHA-SM-03, ITS TWO HOLES ON THE REF STATIONS OF THE MHA-SM-03 BRACKET "
    f"TAPS WITHIN ±{_length(BRACKET_STATION_TOL_MM, 3)} "
    f"(CALIPERS; {setting_row(BRACKET_ROW)}).",
    f"3A. SPOT THROUGH EACH {BRACKET_NUMBER} HOLE WITH A DRILL THAT JUST FITS "
    "THE HOLE.",
    f"3B. WITH {BRACKET_NUMBER} OFF, DRILL AND TAP BOTH SPOTS PER THE MHA-SM-03 "
    "BRACKET TAP CALLOUT.",
    f"3C. SET {BRACKET_NUMBER} ASIDE; ITS TWO MHA-MG-VN-53 SCREWS FIX IT AT "
    f"{ha_steps.step_ref('magnifier-bracket-screwed')}.",
    "4. AT EACH HANGER HOLE MEASURE CROSSBAR UNDERSIDE TO WASHER TOP: "
    f"{HANGER_STACK} ({setting_row(CUT_ROW)}).",
    f"4A. CUT AN MHA-SM-VN-52 TO {HANGER_STACK} PLUS {HANGER_FIT_CUT} UNDER THE "
    f"HEAD ({setting_row(CUT_ROW)}): ITS FULL-THREAD REACH INTO THE MHA-SM-02 "
    "TAP, TIP CLEAR OF THE TAP BOTTOM.",
    "4B. CHAMFER EACH CUT END PER MHA-SM-VN-52.",
    "5. WITHOUT THE LEVER, HANG EACH MHA-SM-02 TOP SEAT UP WITH ITS ROUND HOLE "
    "ON THE DOWEL AT ITS HANGER HOLE; THE ONE AT THE HANGER HOLE NEARER THE "
    "GOOSENECK HUB IS THE REAR MOUNT, THE OTHER THE FRONT MOUNT.",
    "5A. TURN EACH CUT MHA-SM-VN-52 DOWN THROUGH ITS WASHER AND HOLE INTO ITS "
    "MOUNT BY HAND UNTIL ITS HEAD MEETS THE WASHER (FINGER-TIGHT).",
    f"5B. SLIDE A {KNIFE_GAUGE_BAR}, MADE TO THE MHA-SM-02 BORES, THROUGH "
    f"BOTH MOUNTS: {KNIFE_GAUGE_BAR_FEEL}.",
    "5C. TIGHTEN THE FRONT MOUNT'S BOLT UNTIL ITS TOP SEAT IS DRAWN UP FLAT "
    "TO THE CROSSBAR UNDERSIDE (THE REAR MOUNT IS SET AT 6G).",
    "5D. WITHDRAW THE BAR (CHECK 5).",
    "6. REMOVE THE REAR MOUNT'S BOLT.",
    "6A. LIFT THE REAR MOUNT OFF ITS DOWEL.",
    "6B. SLIDE THE REAR MOUNT ONTO THE HEX TRUNNION AT THE DATUM B END OF "
    "MHA-SM-03 (THE REAR TRUNNION) FROM THE TRUNNION'S OUTER END.",
    "6C. ENTER THE FRONT TRUNNION INTO THE FRONT MOUNT'S BORE.",
    "6D. RE-HANG THE REAR MOUNT ON ITS DOWEL.",
    "6E. TURN THE REAR MOUNT'S BOLT IN BY HAND (FINGER-TIGHT).",
    "6F. CHECK: EACH TOP RIDGE RESTS UNDER THE TOP OF ITS BORE.",
    "6G. SWING THE REAR MOUNT ABOUT ITS DOWEL UNTIL THE LEVER ROCKS "
    f"{ROCK_TRAVEL_MIN} EACH WAY, {setting_row(ROCK_ROW)} (CHECK 2).",
    "6H. TIGHTEN THE REAR MOUNT'S BOLT UNTIL ITS TOP SEAT IS DRAWN UP FLAT TO "
    "THE CROSSBAR UNDERSIDE (CHECK 1).",
    "7. CHECK THE FREE ROCK AGAIN (CHECK 2) BEFORE THE COUNTER SPRING GOES ON.",
    # One line: bond note B names the compound.
    "8. BOND MHA-SM-05 INTO MHA-SM-01 PER BOND NOTE B (MAY BE DONE BEFORE STEP 1).",
    "8A. PASS MHA-SM-VN-56 THROUGH THE UPPER LOOP OF MHA-SM-VN-51.",
    "8B. TURN MHA-SM-VN-56 INTO MHA-SM-05 UNTIL ITS SHOULDER SEATS ON THE END "
    "FACE; NO THREADLOCKER.",
    # 8C accepts the cured bond after 8B's seat, the joint's largest assembly
    # load, so a bond the seating breaks is caught too.  A plug that turns
    # cannot hold the screw back, so it is pulled out by the screw first.
    "8C. CHECK THAT MHA-SM-05 DOES NOT TURN OR PULL OUT OF MHA-SM-01 BY HAND.",
    "8D. IF IT DOES, PULL MHA-SM-05 OUT OF MHA-SM-01 BY MHA-SM-VN-56.",
    "8E. IF PULLED, TURN MHA-SM-VN-56 OUT OF MHA-SM-05.",
    "8F. IF PULLED, CLEAN MHA-SM-05 AND THE MHA-SM-01 BORE TO BARE METAL.",
    "8G. IF PULLED, REDO FROM STEP 8.",
    "9. AT FINAL ASSEMBLY (MHA-HA-00): DROP THE MHA-SM-01 POST INTO THE "
    "FRAME'S GOOSENECK HUB WITH THE HUB SET SCREW MHA-FR-VN-52 (FITTED PER "
    "MHA-FR-00) BACKED CLEAR.",
    "9A. HOOK THE LOWER LOOP OF MHA-SM-VN-51 INTO THE EYE OF MHA-SM-VN-50.",
    f"10. LEVEL SETTING, AT {ha_steps.step_ref('summing-levelled')} WITH THE "
    "MHA-CH-VN-50 CHANNEL SPRINGS HOOKED (ITS STEP "
    f"{ha_steps.step_number('channel-anchors-set')}) AND EVERY CHANNEL "
    "AMPLITUDE AT ZERO: SLIDE THE GOOSENECK POST IN ITS HUB UNTIL THE "
    f"LEVER PLATE TOP IS {LEVEL_CRITERION} ({LEVEL_GAUGE} ACROSS THE "
    f"PLATE, {setting_row(LEVEL_ROW)}). THE GOOSENECK HEIGHT REFERENCE "
    "DIMENSION ON SHEET 1 IS THE NOMINAL START.",
    "10A. TIGHTEN THE HUB SET SCREW MHA-FR-VN-52 ON THE POST, "
    f"{HUB_SET_SCREW_TORQUE}.",
)
STEP_SECTIONS = (("ASSEMBLY SEQUENCE", ASSEMBLY_STEPS),)
ASSEMBLY_CHECKS = (
    "1. EACH MOUNT'S TOP SEAT IS FLAT TO THE CROSSBAR UNDERSIDE: A "
    f"{_length(SEAT_FEELER_MM, 3)} FEELER ENTERS NOWHERE ROUND IT "
    f"({setting_row(SEAT_ROW)}); THE MOUNT DOES NOT TURN ABOUT ITS DOWEL BY "
    "HAND.",
    "2. COUNTER SPRING OFF, THE LEVER ROCKS FREELY ON ITS KNIFE EDGE: THE "
    f"OUTER EDGE OF THE BOSS TOP FACE (DETAIL {DETAIL_LETTER}) MOVES "
    f"{ROCK_TRAVEL_MIN} UP AND DOWN FROM LEVEL BEFORE A HEX FLANK TOUCHES A "
    f"BORE ({setting_row(ROCK_ROW)}).",
    "3. THE UPPER LOOP OF MHA-SM-VN-51 TURNS AND SLIDES FREELY ON THE SHOULDER "
    "OF MHA-SM-VN-56, UNDER ITS HEAD.",
    f"4. AFTER STEP 10A THE LEVER PLATE TOP READS {LEVEL_CRITERION} "
    f"({setting_row(LEVEL_ROW)}) AND THE GOOSENECK POST DOES NOT TURN OR "
    "SLIDE IN ITS HUB.",
    "5. AFTER STEP 5 THE GAUGE BAR SLIDES OUT OF BOTH MOUNTS' BORES BY HAND.",
    BOND_NOTE_A,
    BOND_NOTE_B,
)
