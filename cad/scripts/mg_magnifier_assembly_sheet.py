"""Drawing-only data of the magnifier fitter package (MHA-MG-00).

The BOM rows (families, quantities, descriptions), the axle-stack dimensions
the sheet imports, the exploded-view caption, the fit-up steps and the checks
the sheets print. Native setting callouts belong to the model spec, not here.
Only draw_mg_magnifier_assembly (and its tests) import this module; no assembly
builder may (``test_assembly_sheet_isolation`` pins it), so a wording edit here
does not rebuild the magnifier assembly. No SolidWorks.
"""

from __future__ import annotations

import math

import ha_harmonic_analyzer_assembly_steps as _ha_steps
import mg_magnifier_assembly_steps as _steps
import sh_vn_clamp_screw_spec as _clamp_screw
import mg_wheel_axle_spec as _axle
import mg_vn_magnifying_bracket_screw_spec as _bracket_screw
from _inch_fraction import inch_fraction
from sh_vn_thumb_screw_spec import SHANK_LEN as _THUMB_SHANK_LEN
from sh_vn_thumb_screw_spec import THREAD as _THUMB_THREAD
from mg_magnifier_assembly_spec import (
    ENDSHAKE,
    ENDSHAKE_DIMENSION,
    ENDSHAKE_TOL,
    FEATURE,
    PRESS_GAUGE_DIMENSION,
    THREAD_PAST_LOCKNUT_MIN_TEXT,
    THREAD_PAST_LOCKNUT_TEXT,
    UNIT,
)
from _title_block_units import LENGTH_UNITS, render_number
from _printed_tolerance import (
    drilled_oversize_mm,
    edge_break_chamfer_mm,
    edge_break_radius_mm,
)
from sh_vn_music_wire_lever_spec import BOM_DESCRIPTION as _WIRE_BOM_DESCRIPTION
from sh_vn_music_wire_lever_geom import TOGGLE_LENGTH as _TOGGLE_LENGTH
from mg_magnifying_wheel_geom import DRUM_RECESS as _DRUM_RECESS
from mg_magnifying_wheel_geom import SPOKE_COUNT as _SPOKE_COUNT
from mg_magnifying_wheel_geom import TIE1_X as _TIE1_X
from mg_magnifying_wheel_geom import TIE1_Y as _TIE1_Y

# The axle-stack dimensions DETAIL A and DETAIL B import (the builder marks
# the banded ones, DIMENSION_TOLERANCES).
DRAWING_DIMENSIONS = {FEATURE: {PRESS_GAUGE_DIMENSION, ENDSHAKE_DIMENSION}}

# Every view other than the three principal ones carries a letter (rule 9,
# rule 26), its boundary or viewing arrow on the right side view (MG LEFT).
PRESS_DETAIL_LETTER = "A"
ENDSHAKE_DETAIL_LETTER = "B"
LEVER_TIP_VIEW_LETTER = "C"
WHEEL_REST_VIEW_LETTER = "D"
PRESS_DETAIL_TITLE = f"DETAIL {PRESS_DETAIL_LETTER}"
ENDSHAKE_DETAIL_TITLE = f"DETAIL {ENDSHAKE_DETAIL_LETTER}"
THREAD_PROJECTION_DETAIL_TITLE = f"VIEW {LEVER_TIP_VIEW_LETTER}"
WHEEL_REST_VIEW_TITLE = f"VIEW {WHEEL_REST_VIEW_LETTER}"
# VIEW D prints on the last sheet, beside the wire steps that turn the wheel.
WHEEL_REST_VIEW_SHEET = 5

# TIE 1's rest position: the wheel sits at its part frame in the assembly, so
# TIE 1's axis runs from the axle axis at this angle below the wheel bar's
# bottom edge (the bar runs along local X). It lies midway between two
# spokes, so two spokes then lie along the bar (mg_magnifying_wheel_geom).
TIE1_ANGLE_DEG = math.degrees(math.atan2(-_TIE1_Y, _TIE1_X))
_SPOKE_PITCH_DEG = 360.0 / _SPOKE_COUNT
if abs(TIE1_ANGLE_DEG % _SPOKE_PITCH_DEG - _SPOKE_PITCH_DEG / 2.0) > 1.0:
    raise AssertionError(f"TIE 1 at {TIE1_ANGLE_DEG:.2f} deg is not midway between spokes")

# The endshake's feeler-gauge check: the band's low limit enters, its high
# limit does not (machinist review r1: a no-go one thousandth over the band
# passed gaps the band rejects).
_INCH = LENGTH_UNITS[UNIT]
if UNIT != "in":
    raise AssertionError("the endshake feeler check reads inch leaves")
ENDSHAKE_GO_TEXT = render_number((ENDSHAKE - ENDSHAKE_TOL) / _INCH, UNIT, 3)
ENDSHAKE_NO_GO_TEXT = render_number((ENDSHAKE + ENDSHAKE_TOL) / _INCH, UNIT, 3)
# The pressed axle's plain end below the bar's far face: the window the axle
# spec proves from the printed shank, gauge and bar depth (mg_wheel_axle_spec;
# the bar sheet names the stack, MHA-MG-00's press step accepts it).
BACK_END_SUNK_TEXT = (
    f"{render_number(_axle.BACK_END_SUNK_MIN / _INCH, UNIT, 3)}-"
    f"{render_number(_axle.BACK_END_SUNK_MAX / _INCH, UNIT, 3)}"
)
# The pressed drum's front face below the wheel's spigot face, hard against
# the boss: the window the printed spigot and drum lengths prove
# (mg_magnifying_wheel_geom.DRUM_RECESS). Delegated ruling (assembly-step
# moves): MHA-MG-00's press step accepts it.
# The geom asserts the near limit >= -1e-9 mm; rounding (and + 0.0, for -0.0)
# drops float residue that render_number would reject as a negative magnitude.
DRUM_RECESS_TEXT = "-".join(
    render_number(round(limit / _INCH, 6) + 0.0, UNIT, 3) for limit in _DRUM_RECESS
)

# The summing lever (cad/config/parts/sm-summing-lever.yaml), the mate the
# bracket screws to at MHA-HA-00; rule 4 names it by its drawing number.
SUMMING_LEVER_NUMBER = "MHA-SM-03"

# --- Fitter package -----------------------------------------------------------
DRAWING_NUMBER = _steps.DRAWING_NUMBER
WHEEL_BAR = "mg-wheel-bar"
CLAMP_FRONT = "sh-column-clamp-front"
CLAMP_BACK = "sh-column-clamp-back"
CLAMP_SCREW = "sh-vn-clamp-screw"
AXLE = "mg-wheel-axle"
SPACER = "mg-wheel-axle-spacer"
BACK_WASHER = "mg-vn-wheel-axle-back-washer"
WHEEL = "mg-magnifying-wheel"
DRUM = "mg-wheel-drum"
FRONT_WASHER = "mg-vn-wheel-axle-front-washer"
NUT = "mg-vn-wheel-axle-nut"
LEVER = "mg-magnifying-lever"
BRACKET = "mg-magnifying-bracket"
BRACKET_SCREW = "mg-vn-magnifying-bracket-screw"
CLAMP = "mg-magnifying-clamp"
THUMB_SCREW = "sh-vn-thumb-screw"
ROD = "mg-magnifying-vertical-rod"
FIXTURE = "mg-output-fixture"
WIRE = "sh-vn-music-wire"
# Wheel group, then lever group, then the wire: the order the steps fit them.
BOM_ORDER = (
    AXLE,
    WHEEL_BAR,
    CLAMP_FRONT,
    CLAMP_BACK,
    CLAMP_SCREW,
    DRUM,
    WHEEL,
    SPACER,
    BACK_WASHER,
    FRONT_WASHER,
    NUT,
    LEVER,
    BRACKET,
    BRACKET_SCREW,
    CLAMP,
    THUMB_SCREW,
    ROD,
    FIXTURE,
    WIRE,
)
QUANTITIES = {stem: 1 for stem in BOM_ORDER} | {
    CLAMP_SCREW: 2,
    NUT: 2,
    BRACKET_SCREW: 2,
    THUMB_SCREW: 2,
}
# BOM DESCRIPTION cells (the parts carry no Description property); the steps
# below name the parts the same way, with their part numbers. The screw
# lengths print as the vendor parts' own inch fractions, read from their specs.
BOM_DESCRIPTIONS = {
    AXLE: "WHEEL AXLE",
    WHEEL_BAR: "WHEEL BAR",
    CLAMP_FRONT: "COLUMN CLAMP, FRONT",
    CLAMP_BACK: "COLUMN CLAMP, BACK",
    CLAMP_SCREW: (
        "#8-32 X "
        f"{inch_fraction(_clamp_screw.SHANK_LEN, what=f'{CLAMP_SCREW} length')} "
        "FILLISTER SCREW"
    ),
    DRUM: "WHEEL DRUM",
    WHEEL: "MAGNIFYING WHEEL",
    SPACER: "WHEEL AXLE SPACER",
    BACK_WASHER: "WHEEL BACK WASHER",
    FRONT_WASHER: "WHEEL FRONT WASHER",
    NUT: "#4-40 HEX NUT",
    LEVER: "MAGNIFYING LEVER",
    BRACKET: "MAGNIFYING BRACKET",
    BRACKET_SCREW: (
        f"{_bracket_screw.THREAD} X "
        f"{inch_fraction(_bracket_screw.LENGTH, what=f'{BRACKET_SCREW} length')} "
        "FILLISTER SCREW"
    ),
    CLAMP: "MAGNIFYING CLAMP",
    THUMB_SCREW: (
        f"{_THUMB_THREAD} X "
        f"{inch_fraction(_THUMB_SHANK_LEN, what=f'{THUMB_SCREW} length')} "
        "KNURLED THUMB SCREW"
    ),
    ROD: "VERTICAL ROD",
    FIXTURE: "OUTPUT FIXTURE",
    WIRE: _WIRE_BOM_DESCRIPTION,
}
if set(BOM_DESCRIPTIONS) != set(BOM_ORDER) or len(set(BOM_ORDER)) != len(BOM_ORDER):
    raise AssertionError("every BOM family needs exactly one description")

EXPLODED_CAPTION = "EXPLODED VIEW - ASSEMBLY SEQUENCE ON SHEETS 4-5"

# The BOM's item numbers, as the native table numbers the families (component
# order in the source assembly); the drawing proves the inserted table prints
# exactly these. Steps name parts by item (drawing-guidelines.md rule 22).
ITEM_NUMBERS = {
    WHEEL_BAR: 1,
    CLAMP_FRONT: 2,
    CLAMP_BACK: 3,
    CLAMP_SCREW: 4,
    LEVER: 5,
    BRACKET: 6,
    BRACKET_SCREW: 7,
    CLAMP: 8,
    THUMB_SCREW: 9,
    ROD: 10,
    FIXTURE: 11,
    AXLE: 12,
    SPACER: 13,
    BACK_WASHER: 14,
    WHEEL: 15,
    DRUM: 16,
    FRONT_WASHER: 17,
    NUT: 18,
    WIRE: 19,
}
if set(ITEM_NUMBERS) != set(BOM_ORDER) or sorted(ITEM_NUMBERS.values()) != list(
    range(1, len(BOM_ORDER) + 1)
):
    raise AssertionError("every BOM family needs exactly one contiguous item number")


def _item(stem: str) -> str:
    return f"ITEM {ITEM_NUMBERS[stem]}"


def _step(key: str) -> str:
    return f"STEP {_steps.step_number(key)}"


_AXLE, _BAR, _WHEEL, _DRUM = _item(AXLE), _item(WHEEL_BAR), _item(WHEEL), _item(DRUM)
_NUT, _WASHER, _LEVER, _BRACKET = _item(NUT), _item(FRONT_WASHER), _item(LEVER), _item(BRACKET)
_CLAMP, _THUMB, _ROD, _FIXTURE = _item(CLAMP), _item(THUMB_SCREW), _item(ROD), _item(FIXTURE)
_WIRE = _item(WIRE)
# The wheel stack on the axle, bar side first (sheet 2 shows the order).
_STACK = (
    f"ITEMS {ITEM_NUMBERS[SPACER]}, {ITEM_NUMBERS[BACK_WASHER]}, "
    f"{ITEM_NUMBERS[WHEEL]} ({_DRUM} AWAY FROM {_BAR}) AND {ITEM_NUMBERS[FRONT_WASHER]}"
)

# Rule 23: a specified anaerobic bond equals a press fit. The package bonds
# a press that went in slack: the drum on the wheel's spigot (owner ruling
# 2026-11-07) and the axle in the bar (owner ruling 2026-11-11, #2541 and
# #2523, amending the 2026-11-07 "a slip axle is remade": a remade axle cut
# from the same as-supplied rod comes out the same size). Its degrease,
# coated length, squeeze-out, cure and acceptance rules print once, as a
# general note with the checks on sheet 5. The axle's coat stays on the
# length inside the bar and its squeeze-out is wiped off at once, since the
# spacer and the wheel slide and run on the same shank just outside it.
BOND_GRADE = "LOCTITE 638"
BOND_NOTE_REF = "NOTE 1 (SHEET 5)"
BOND_NOTE = (
    f"NOTE 1, {BOND_GRADE} BOND: DEGREASE; COAT THE SPIGOT OR THE AXLE END IN "
    f"{_BAR} ONLY; WIPE OFF THE EXCESS; CURE 24 H AT ROOM TEMPERATURE BEFORE "
    "LOAD OR OIL. ACCEPT: NO TURN OR SLIDE BY HAND."
)

# #2399: the axle presses in plain end first, so the press would push on its
# threaded end and drive the band's interference (.0003-.0012) through the
# relief neck (Ø.066-.076, .0034-.0045 sq in), which yields under 250 lbf in
# annealed drill rod (about 55 ksi), short of any press in the band. The press
# pushes on the shank step instead, through a sleeve over the thread: its
# drilled bore clears the thread's major Ø and stays on the step's flat inside
# the shank's title-block edge break, its OD covers the step, and it stands
# past the dome at the thread's longest. Its drill prints as a US customary
# size (drawing-guidelines.md, What the shop holds).
PRESS_SLEEVE_DRILL = "#32"
PRESS_SLEEVE_BORE = 2.9464  # .116, a #32 drill
PRESS_SLEEVE_OD = 6.35  # .25
PRESS_SLEEVE_LENGTH = 12.7  # .50
_AXLE_EDGE_BREAK = max(
    edge_break_radius_mm(unit=_axle.UNIT), edge_break_chamfer_mm(unit=_axle.UNIT)
)
_SLEEVE_BORE_MAX = PRESS_SLEEVE_BORE + drilled_oversize_mm(unit=UNIT)
_STEP_FLAT_DIA_MIN = _axle.PIN_DIA - _axle.PIN_DIA_TOL - 2.0 * _AXLE_EDGE_BREAK
if not (
    _axle.THREAD_MAJOR < PRESS_SLEEVE_BORE
    and _SLEEVE_BORE_MAX < _STEP_FLAT_DIA_MIN
    and PRESS_SLEEVE_OD > _axle.PIN_DIA + _axle.PIN_DIA_TOL
    and PRESS_SLEEVE_LENGTH > _axle.THREAD_LEN + _axle.THREAD_LEN_BAND[0] + _axle.DOME_H
):
    raise AssertionError("the press sleeve does not bear on the axle step alone")
# The step's bearing at the press's top force [hand estimate, #2399]: an oiled
# steel press (friction .10) at the band's top interference, the bar's hub
# pressure capped near 40 ksi by its yield, over the bar's whole depth (about
# .88 kip). The worst annulus (the sleeve's bore at the drilled limit, the
# step's flat inside a full edge break) carries it at about 83 ksi, under the
# 1.8 x yield static bearing on a finished face takes (AISC 360-16 J7), so at
# worst the step's rim coins; the step locates nothing (the wheel hub
# overhangs it, mg_wheel_group.STEP_INSIDE_HUB; the press is accepted at the
# thread end past the nuts).
PRESS_FRICTION_OILED = 0.10
PRESS_HUB_PRESSURE_KSI = 40.0
AXLE_YIELD_KSI = 55.0  # annealed O1/W1 drill rod
BEARING_YIELD_FACTOR = 1.8  # AISC 360-16 J7, bearing on a finished surface
PRESS_FORCE_MAX_KIP = (
    PRESS_FRICTION_OILED
    * PRESS_HUB_PRESSURE_KSI
    * math.pi
    * ((_axle.PIN_DIA + _axle.PIN_DIA_TOL) / _INCH)
    * (_axle.BAR_DEPTH / _INCH)
)
STEP_BEARING_AREA_MIN_SQIN = (
    math.pi
    / 4.0
    * ((_STEP_FLAT_DIA_MIN / _INCH) ** 2 - (_SLEEVE_BORE_MAX / _INCH) ** 2)
)
STEP_BEARING_MAX_KSI = PRESS_FORCE_MAX_KIP / STEP_BEARING_AREA_MIN_SQIN
if STEP_BEARING_MAX_KSI > BEARING_YIELD_FACTOR * AXLE_YIELD_KSI:
    raise AssertionError(
        f"the press sleeve bears {STEP_BEARING_MAX_KSI:.0f} ksi on the axle step"
    )
PRESS_SLEEVE = (
    f"A STEEL SLEEVE OVER THE THREAD ({PRESS_SLEEVE_DRILL} DRILLED BORE, "
    f"{render_number(PRESS_SLEEVE_OD / _INCH, UNIT, 2)} OD, "
    f"{render_number(PRESS_SLEEVE_LENGTH / _INCH, UNIT, 2)} LONG)"
)

# One line per step key (mg_magnifier_assembly_steps.SEQUENCE); each step does
# one thing, a check and its remedy are separate steps (rule 22). Settings are
# named, never valued: their values print as the model dimensions on sheet 1.
# Ends and sides name physical features or a lettered view, never a compass,
# a clock or the machine's front and back (the principal views print unnamed).
# The wheel's lever-wire tie hole by its plain name (rule 26), on VIEW D's
# leader and in the steps; MHA-MG-05 keys it as TIE 1 on its own sheet.
WIRE_TIE_HOLE = "WIRE TIE HOLE"
_TIE_HOLE = f"THE {WIRE_TIE_HOLE}"
STEP_TEXT = {
    _steps.DRUM_PRESSED_KEY: (
        f"PRESS {_DRUM} ONTO THE SPIGOT OF {_WHEEL} UNTIL IT IS HARD AGAINST THE "
        f"BOSS, ITS OUTER FACE {DRUM_RECESS_TEXT} BELOW THE END OF THE SPIGOT "
        "(CALIPER DEPTH ROD)."
    ),
    _steps.DRUM_HELD_KEY: f"CHECK {_DRUM} DOES NOT TURN OR SLIDE BY HAND.",
    # A press that goes on by hand is a slip fit (rule 23). Owner ruling
    # 2026-11-07: a bond equals a press, so a slip drum is bonded rather than
    # the wheel remade (BOND_NOTE).
    "drum-pulled-off": f"IF IT DOES, OR {_DRUM} SLID ON BY HAND, PULL {_DRUM} OFF.",
    "drum-bonded": f"IF IT CAME OFF, BOND IT ON WITH {BOND_GRADE}, {BOND_NOTE_REF}.",
    # The press goes to a first setting: the plain end's window below the
    # bar's far face (the bar's depth stack, which MHA-MG-08 names; the spec
    # proves the window), read with a depth rod. The only acceptance of the
    # axle's position is the thread end past the second nut: the number pair
    # a depth rod reads there (owner ruling 2026-11-06 Q1), printed in the
    # check from the spec's constants and read where DETAIL B draws the nuts.
    # Farm rounds 1-3 gated it as a callout on DETAIL A, which draws no nut,
    # and r3 read two acceptances; Main chose option A on 2026-11-08. The
    # press goes in oiled and pushes only on the shank step, through
    # PRESS_SLEEVE (#2399).
    _steps.AXLE_PRESSED_KEY: (
        f"PRESS {_AXLE} INTO {_BAR} WITH LIGHT MACHINE OIL ON ITS PLAIN END, "
        "THREADED END OUT, ON ITS SHOULDER ONLY, "
        f"THROUGH {PRESS_SLEEVE}, TO A FIRST SETTING: ITS PLAIN END "
        f"{BACK_END_SUNK_TEXT} BELOW THE FAR FACE OF {_BAR} (CALIPER DEPTH ROD)."
    ),
    _steps.AXLE_HELD_KEY: f"CHECK {_AXLE} DOES NOT TURN OR SLIDE BY HAND.",
    # Owner ruling 2026-11-11 (#2541, #2523; amends 2026-11-07): a slip axle
    # is bonded, not remade, under NOTE 1 as the drum is: clean, bond, set
    # before it grabs, then the hold check again once cured. The slip clause
    # names an unbonded axle, so the bonded one passes back through 2A-2B.
    # Step 3 is the only position acceptance: a bonded axle it moves (3D/3E)
    # comes back through 2A, and one that no longer holds is rebonded at the
    # first setting plus that correction, so the correction is not lost.
    "axle-pressed-out": f"IF IT DOES, OR AN UNBONDED {_AXLE} SLID IN BY HAND, PRESS IT OUT.",
    "axle-cleaned": f"IF {_AXLE} CAME OUT, CLEAN IT AND THE BORE IN {_BAR} TO BARE METAL.",
    "axle-bonded": f"IF IT WAS CLEANED, BOND IT IN WITH {BOND_GRADE}, {BOND_NOTE_REF}.",
    "axle-bond-set": (
        f"IF IT WAS BONDED, SET IT AT ONCE TO THE {_step(_steps.AXLE_PRESSED_KEY)} "
        f"FIRST SETTING PLUS ANY STEP {_steps.step_number('axle-pressed-further')} "
        f"OR {_steps.step_number('axle-pressed-back')} CORRECTION."
    ),
    "axle-bond-cured": (
        f"IF IT WAS BONDED, RETURN TO {_step(_steps.AXLE_HELD_KEY)} ONCE IT HAS "
        "CURED 24 H."
    ),
    _steps.AXLE_TRIAL_KEY: f"TRIAL-FIT {_STACK} ON {_AXLE}, IN THAT ORDER.",
    "trial-nuts-jammed": (
        f"JAM BOTH {_NUT} NUTS ON {_AXLE} WITH {_WHEEL} JUST FREE."
    ),
    _steps.AXLE_CHECKED_KEY: (
        f"CHECK THE THREAD END IN {ENDSHAKE_DETAIL_TITLE} STANDS "
        f"{THREAD_PAST_LOCKNUT_MIN_TEXT}-{THREAD_PAST_LOCKNUT_TEXT} PAST THE "
        "SECOND NUT (CALIPER DEPTH ROD)."
    ),
    "trial-parts-removed-to-press": (
        f"IF IT FAILS, REMOVE THE TRIAL NUTS AND PARTS FROM {_AXLE}."
    ),
    "axle-pressed-further": (
        f"IF {_step(_steps.AXLE_CHECKED_KEY)} READ OVER THE MAX, PRESS {_AXLE} IN "
        "BY THE EXCESS, ON ITS SHOULDER THROUGH THE "
        f"{_step(_steps.AXLE_PRESSED_KEY)} SLEEVE."
    ),
    "axle-pressed-back": (
        f"IF {_step(_steps.AXLE_CHECKED_KEY)} READ UNDER THE MIN, PRESS {_AXLE} "
        "OUT TOWARD ITS THREADED END BY THE SHORTFALL."
    ),
    # A re-press goes back through the hold check before the trial fit.
    "axle-rechecked": (
        f"IF {_AXLE} WAS PRESSED AGAIN, RETURN TO {_step(_steps.AXLE_HELD_KEY)}."
    ),
    "trial-parts-removed": f"REMOVE THE TRIAL NUTS AND PARTS FROM {_AXLE}.",
    "column-clamps-fitted": (
        f"FIT {_item(CLAMP_FRONT)} AND {_item(CLAMP_BACK)} TO {_BAR} AS THE "
        "SHEET 2 EXPLODED VIEW SHOWS."
    ),
    _steps.COLUMN_CLAMP_STARTED_KEY: (
        f"START BOTH {_item(CLAMP_SCREW)} SCREWS THROUGH ITEMS "
        f"{ITEM_NUMBERS[WHEEL_BAR]} AND {ITEM_NUMBERS[CLAMP_FRONT]} INTO "
        f"{_item(CLAMP_BACK)}."
    ),
    # Rule 23 at the package boundary: the screws are seated and accepted at
    # the MHA-HA-00 step that clamps the bar, cited by number.
    "column-clamp-screws-left-loose": (
        f"LEAVE THEM LOOSE FOR {_ha_steps.step_ref('magnifier-bar-clamped')} "
        "TO TIGHTEN."
    ),
    "axle-oiled": f"WIPE LIGHT MACHINE OIL ON {_AXLE}.",
    # The stack the washer and nut sheets once described in INSTALLATION
    # notes (F6): the order here, the nut and locknut in the next two steps.
    "wheel-stacked": f"SLIDE {_STACK} ONTO {_AXLE}, IN THAT ORDER.",
    _steps.ENDSHAKE_SET_KEY: (
        f"RUN ONE {_NUT} NUT DOWN ONTO {_WASHER} UNTIL {_WHEEL} TURNS FREE "
        "WITHOUT RATTLE."
    ),
    _steps.ENDSHAKE_CHECKED_KEY: (
        f"CHECK THE {ENDSHAKE_DETAIL_TITLE} ENDSHAKE WITH FEELER GAUGES BETWEEN "
        f"{_WASHER} AND THE SPIGOT FACE, {_WHEEL} PUSHED TOWARD {_BAR}: "
        f"{ENDSHAKE_GO_TEXT} ENTERS, {ENDSHAKE_NO_GO_TEXT} DOES NOT."
    ),
    "endshake-loosened": (
        f"IF {ENDSHAKE_GO_TEXT} DOES NOT ENTER, LOOSEN THE NUT SLIGHTLY."
    ),
    "endshake-tightened": f"IF {ENDSHAKE_NO_GO_TEXT} ENTERS, TIGHTEN THE NUT SLIGHTLY.",
    "endshake-repeated": (
        f"REPEAT {_steps.step_number(_steps.ENDSHAKE_CHECKED_KEY)}-"
        f"{_steps.step_number('endshake-tightened')} UNTIL BOTH FEELERS PASS."
    ),
    _steps.LOCKNUT_JAMMED_KEY: (
        f"HOLD THE FIRST NUT AND JAM THE SECOND {_NUT} NUT AGAINST IT."
    ),
    "endshake-rechecked": (
        f"CHECK THE ENDSHAKE AGAIN AS IN {_step(_steps.ENDSHAKE_CHECKED_KEY)}."
    ),
    "locknut-loosened": "IF IT FAILS, LOOSEN THE SECOND NUT.",
    "locknut-reset": (
        f"IF THE SECOND NUT WAS LOOSENED, RETURN TO {_step(_steps.ENDSHAKE_SET_KEY)}."
    ),
    _steps.AXLE_ACCEPTED_KEY: (
        "CHECK THE THREAD END PAST THE SECOND NUT AGAIN, AS IN "
        f"{_step(_steps.AXLE_CHECKED_KEY)}."
    ),
    # The final reading's own remedy: strip the stack back to the bare axle
    # and take the trial-fit loop again (machinist review, stab-split s2).
    "axle-stack-removed": (
        f"IF IT FAILS, REMOVE ITEMS {ITEM_NUMBERS[NUT]}, "
        f"{ITEM_NUMBERS[FRONT_WASHER]}, {ITEM_NUMBERS[WHEEL]}, "
        f"{ITEM_NUMBERS[BACK_WASHER]} AND {ITEM_NUMBERS[SPACER]}."
    ),
    "axle-reset": (
        f"IF THEY WERE REMOVED, RETURN TO {_step(_steps.AXLE_TRIAL_KEY)}."
    ),
    # The setting names the instrument that reads it (rule 22).
    _steps.LEVER_THREADED_KEY: (
        f"SCREW {_LEVER} INTO {_BRACKET} UNTIL ITS FLAT TIP STANDS PROUD OF THE "
        f"FAR FACE AS {THREAD_PROJECTION_DETAIL_TITLE} SETS IT (CALIPER DEPTH ROD)."
    ),
    "clamp-thumb-screw-started": (
        f"START ONE {_THUMB} INTO THE TAP OF {_CLAMP} THAT BREAKS INTO ITS CROSS "
        "BORE, SHORT OF THE BORE."
    ),
    _steps.CLAMP_SET_KEY: (
        f"SLIDE {_CLAMP} ONTO {_LEVER} FROM ITS DOMED FREE END, {_THUMB} UP, TO "
        "THE CLAMP STATION (SHEET 1)."
    ),
    "clamp-thumb-screw-tightened": f"TIGHTEN THAT {_THUMB} BY HAND.",
    # Rule 23 (adjustable clamp): a thumb screw on the round holds a light-load
    # setting that must stay adjustable when a step sets it and checks it holds.
    _steps.CLAMP_HELD_KEY: f"CHECK {_CLAMP} DOES NOT SLIP ON {_LEVER} BY HAND.",
    "clamp-reset": f"IF IT SLIPS, RETURN TO {_step(_steps.CLAMP_SET_KEY)}.",
    "fixture-thumb-screw-started": (
        f"START THE OTHER {_THUMB} INTO THE TAP IN THE SPIGOT FACE OF {_FIXTURE}, "
        "SHORT OF ITS BORE."
    ),
    "rod-through-fixture": (
        f"PASS THE THREADED END OF {_ROD} UP THROUGH THE BORE OF {_FIXTURE}."
    ),
    # #1559: the rod is retained by its own thread, seated on its shoulder.
    "rod-seated": (
        f"SCREW {_ROD} BY HAND INTO THE BOTTOM TAP OF {_CLAMP} UNTIL ITS SHOULDER "
        "SEATS."
    ),
    _steps.FIXTURE_SET_KEY: (
        f"SLIDE {_FIXTURE} TO THE FIXTURE DROP (SHEET 1), ITS SPIGOT TOWARD "
        f"{_BRACKET}."
    ),
    "fixture-thumb-screw-tightened": f"TIGHTEN THE {_THUMB} IN {_FIXTURE} BY HAND.",
    _steps.FIXTURE_HELD_KEY: f"CHECK {_FIXTURE} DOES NOT SLIP ON {_ROD} BY HAND.",
    "fixture-reset": f"IF IT SLIPS, RETURN TO {_step(_steps.FIXTURE_SET_KEY)}.",
    # The wire is tied in the rest pose its run is derived at
    # (sh_vn_music_wire_lever_geom), which MHA-HA-00 sets as every channel
    # amplitude at zero with the plate top level; the hook, rod and drum lane
    # share one plumb plane (option A1).
    _steps.WIRE_HOOKED_KEY: (
        f"PASS THE END OF {_WIRE} LEVER WIRE ONCE ROUND THE SPIGOT GROOVE OF "
        f"{_FIXTURE}."
    ),
    "lever-wire-led-down": (
        f"LEAD THE WIRE STRAIGHT DOWN TO {_DRUM}, AS THE RIGHT SIDE VIEW ON "
        "SHEET 1 SHOWS."
    ),
    # A thin wire is tied, not twisted (#2398, owner ruling 2026-11-12).
    "lever-wire-hook-knotted": "KNOT THE WIRE END ROUND THE WIRE BELOW THE GROOVE.",
    "machine-at-rest": (
        "SET MHA-HA-00 AT REST: EVERY CHANNEL AMPLITUDE AT ZERO AND THE "
        "MHA-SM-03 PLATE TOP LEVEL."
    ),
    _steps.WHEEL_TURNED_KEY: (
        f"TURN {_WHEEL} UNTIL ITS {WIRE_TIE_HOLE} STANDS AT THE "
        f"{WHEEL_REST_VIEW_TITLE} ANGLE BELOW THE BOTTOM EDGE OF {_BAR} "
        "(PROTRACTOR)."
    ),
    "lever-wire-wrapped": (
        f"WRAP THE WIRE TWO FULL TURNS ROUND {_DRUM} AND ON TO {_TIE_HOLE}, "
        f"CLOCKWISE AS SEEN IN {WHEEL_REST_VIEW_TITLE}."
    ),
    "lever-wire-through-tie": f"PASS THE WIRE END THROUGH {_TIE_HOLE} AND PULL IT TAUT.",
    "lever-wire-tie-knotted": (
        "KNOT THE WIRE TAIL BEHIND THE HOLE ROUND A "
        f"{inch_fraction(_TOGGLE_LENGTH, what='wire toggle')} LONG OFFCUT OF THE "
        "WIRE LAID ACROSS THE HOLE."
    ),
    # Each hand-made joint is checked to hold (rule 23).
    "lever-wire-knots-held": "CHECK NEITHER KNOT SLIPS UNDER A LIGHT PULL BY HAND.",
    _steps.WIRE_TIED_KEY: "TRIM BOTH WIRE TAILS CLOSE TO THEIR KNOTS.",
}
if tuple(STEP_TEXT) != _steps.SEQUENCE:
    raise AssertionError("STEP_TEXT must follow mg_magnifier_assembly_steps.SEQUENCE")
ASSEMBLY_STEPS = tuple(
    f"{_steps.step_number(key)}. {text}" for key, text in STEP_TEXT.items()
)
# The sequence prints in three titled groups, each opening at a numbered
# step; the wire group's title states when its steps run, so no step carries
# a precondition clause.
STEP_GROUPS = (
    ("WHEEL GROUP (EXPLODED ON SHEET 2):", _steps.DRUM_PRESSED_KEY),
    ("LEVER GROUP (EXPLODED ON SHEET 3):", _steps.LEVER_THREADED_KEY),
    (
        "LEVER WIRE, ON THE MACHINE, AFTER MHA-HA-00 HAS CLAMPED "
        f"{_BAR} AND SCREWED {_BRACKET} TO {SUMMING_LEVER_NUMBER}:",
        _steps.WIRE_HOOKED_KEY,
    ),
)
_GROUP_INDICES = [_steps.SEQUENCE.index(key) for _title, key in STEP_GROUPS]
if (
    STEP_GROUPS[0][1] != _steps.SEQUENCE[0]
    or _GROUP_INDICES != sorted(_GROUP_INDICES)
    or not all(_steps.step_number(key).isdigit() for _title, key in STEP_GROUPS)
):
    raise AssertionError("the step groups must open numbered steps in order")
ASSEMBLY_CHECKS = (
    f"CHECK: WITH BOTH {_NUT} NUTS SET, {_WHEEL} TURNS FREE, NO RATTLE.",
    f"CHECK: {_CLAMP} AND {_FIXTURE} HOLD THEIR SETTINGS WHEN {_LEVER} IS "
    "ROCKED BY HAND.",
    f"CHECK: {_WIRE} CLEARS THE RIM, SPOKES AND BOSS OF {_WHEEL}.",
    f"CHECK: WITH {_LEVER} ROCKED BY HAND TO EACH END OF ITS TRAVEL ON THE "
    f"MACHINE, {_WIRE} STAYS WRAPPED ON {_DRUM} SHORT OF {_TIE_HOLE}.",
    f"LOOSE ITEMS: BOTH {_item(BRACKET_SCREW)} SCREWS GO WITH THE ASSEMBLY; "
    f"{_ha_steps.step_ref('magnifier-bracket-screwed')} DRIVES THEM THROUGH "
    f"{_BRACKET} INTO {SUMMING_LEVER_NUMBER} UNTIL THE HEADS SEAT.",
    BOND_NOTE,
)
