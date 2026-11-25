"""Drawing-only data of the magnifier fitter package (MHA-MG-00).

The BOM rows (families, quantities, descriptions), the axle-stack dimensions
the sheet imports and the exploded-view caption the sheets print, and the
fit-up steps and checks the release's ASSEMBLY.md prints for the package
(ha_assembly_package, #2889). Native setting callouts belong to the model
spec, not here. Only draw_mg_magnifier_assembly, ha_assembly_package (and
their tests) import this module; no assembly builder may
(``test_assembly_sheet_isolation`` pins it), so a wording edit here does not
rebuild the magnifier assembly. No SolidWorks.
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
    BACK_END_SUNK_DIMENSION,
    DRUM_RECESS_DIMENSION,
    ENDSHAKE,
    ENDSHAKE_DIMENSION,
    ENDSHAKE_TOL,
    FEATURE,
    PRESS_GAUGE_DIMENSION,
    THREAD_PAST_LOCKNUT_DIMENSION,
    UNIT,
)
from _title_block_units import LENGTH_UNITS, render_number
from _printed_tolerance import (
    drilled_oversize_mm,
    edge_break_chamfer_mm,
    edge_break_radius_mm,
)
from sh_vn_music_wire_lever_spec import BOM_DESCRIPTION as _WIRE_BOM_DESCRIPTION
from mg_magnifying_wheel_geom import SPOKE_COUNT as _SPOKE_COUNT
from mg_magnifying_wheel_geom import TIE1_X as _TIE1_X
from mg_magnifying_wheel_geom import TIE1_Y as _TIE1_Y

# The axle-stack dimensions DETAIL A and DETAIL B import (the builder marks
# the banded and limit ones, DIMENSION_TOLERANCES and LIMIT_DIMENSIONS, and
# the references). DETAIL A: the step station past the spacer face and the
# plain end below the bar's far face, both REF; DETAIL B: the drum face
# below the spigot end (REF), the endshake and the thread end past the
# second nut.
PRESS_DETAIL_DIMENSIONS = frozenset({PRESS_GAUGE_DIMENSION, BACK_END_SUNK_DIMENSION})
ENDSHAKE_DETAIL_DIMENSIONS = frozenset(
    {DRUM_RECESS_DIMENSION, ENDSHAKE_DIMENSION, THREAD_PAST_LOCKNUT_DIMENSION}
)
DRAWING_DIMENSIONS = {FEATURE: set(PRESS_DETAIL_DIMENSIONS | ENDSHAKE_DETAIL_DIMENSIONS)}

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
# VIEW D prints on the last sheet, its own; the wire steps that turn the wheel
# cite it.
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

# The fit-up steps and checks print in the release's ASSEMBLY.md (#2889).
EXPLODED_CAPTION = "EXPLODED VIEW - FIT-UP STEPS IN ASSEMBLY.MD"

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
_SPACER = _item(SPACER)
# The wheel stack on the axle past the spacer, bar side first (sheet 2 shows
# the order). The spacer goes on before the dry trial, comes off with the
# trial stack before the bond and goes back on before the wheel stack.
_STACK = (
    f"ITEMS {ITEM_NUMBERS[BACK_WASHER]}, "
    f"{ITEM_NUMBERS[WHEEL]} ({_DRUM} AWAY FROM {_BAR}) AND {ITEM_NUMBERS[FRONT_WASHER]}"
)
# What the trial puts on the axle, outermost first, as it comes off.
_TRIAL_OFF = (
    f"THE NUTS, THE FEELER AND ITEMS {ITEM_NUMBERS[FRONT_WASHER]}, "
    f"{ITEM_NUMBERS[WHEEL]}, {ITEM_NUMBERS[BACK_WASHER]} AND {ITEM_NUMBERS[SPACER]}"
)
# Every part whose size is a term of the trial's stack under the flush start
# (mg_wheel_group): the bar's depth and the spacer's length place the step
# and the hub's front face, the hub and the washers and nuts their own
# thickness (the axle's lengths are the axle's own replacement). Each reads
# on a micrometer against its own sheet or catalogue band.
_STACK_PARTS = (
    f"{_BAR} (DEPTH), {_SPACER} (LENGTH), {_WHEEL} (HUB LENGTH) AND ITEMS "
    f"{ITEM_NUMBERS[BACK_WASHER]}, {ITEM_NUMBERS[FRONT_WASHER]} AND "
    f"{ITEM_NUMBERS[NUT]} (THICKNESS)"
)

# Rule 23: a specified anaerobic bond equals a press fit. The package bonds
# the drum on the wheel's spigot (owner ruling 2026-11-24, fit audit
# question 17) and the axle in the bar's drilled bore (question 18), both
# always. Its degrease,
# coated length, squeeze-out, cure and acceptance rules print once, as a
# general note with the checks in ASSEMBLY.md. The axle's coat stays on the
# length inside the bar and its squeeze-out is wiped off at once, since the
# spacer and the wheel slide and run on the same shank just outside it.
BOND_GRADE = "LOCTITE 638"
BOND_NOTE_REF = "NOTE 1"
BOND_NOTE = (
    f"NOTE 1, {BOND_GRADE} BOND: DEGREASE; COAT THE SPIGOT OR THE AXLE END IN "
    f"{_BAR} ONLY; WIPE OFF THE EXCESS; CURE 24 H AT ROOM TEMPERATURE BEFORE "
    "LOAD OR OIL. ACCEPT: NO TURN OR SLIDE BY HAND."
)

# #2399: the axle goes in plain end first, so a push on its threaded end at
# the bore's tightest corner (a .0002 light press since question 18; the
# old .0003-.0012 press band, which the bearing check below still covers)
# would load the relief neck (Ø.066-.076, .0034-.0045 sq in), which yields
# under 250 lbf in annealed drill rod (about 55 ksi). The push
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
# worst the step's rim coins. Since C11 the setting is read at the plain end
# and accepted at the thread end past the nuts, so a coined rim moves
# nothing either reads, and the step locates no part (the wheel hub
# overhangs it, mg_wheel_group.TRIAL_STEP_INSIDE_HUB_MIN).
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
    f"A STEEL SLEEVE THAT FITS OVER THE THREAD ({PRESS_SLEEVE_DRILL} DRILLED BORE, "
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
# The axle's setting is read at its plain end (owner ruling 2026-11-24, fit
# audit part 2, C11): the bar stands on the surface plate on its far face, so
# a plain end on the plate is flush, and a caliper depth rod from that face
# reads how far the end stands inside the bore.
_PLATE = f"THE SURFACE PLATE {_BAR} STANDS ON"
STEP_TEXT = {
    # Owner ruling 2026-11-24, fit audit question 17: the drum is bonded on
    # the spigot MHA-MG-05 is turned to slide in its drilled bore (rule 23:
    # the step gives the grade and the stop, its own check the acceptance;
    # NOTE 1 the degrease, coat and cure). The boss face squares it; none of
    # the compound goes in the wheel's bore, which runs on the axle.
    _steps.DRUM_BONDED_KEY: (
        f"BOND {_DRUM} ON THE SPIGOT OF {_WHEEL} WITH {BOND_GRADE}, {BOND_NOTE_REF}, "
        "NONE IN THE BORE, UNTIL IT IS HARD AGAINST THE BOSS."
    ),
    # A slip fit cures wherever it sits in its clearance, so the drum is
    # centred while wet (fit audit question 17, as the cone gears' wet
    # tap-true of #3292 on MHA-DT-00): the wheel turns on its own axle, held
    # on an owned V-block, under an owned dial indicator on its magnetic
    # base, the setup of MHA-DT-00's wet tap-true. The approved form (fit
    # audit question 17: "centred on an indicator while wet") carries no
    # reading, so none is
    # added: the drum is tapped until the needle swings least, which tells
    # the builder when he is done (machinist review r1, run
    # 20261124T092122388Z) without a new instrument limit.
    "drum-centred": (
        f"AT ONCE, BEFORE IT GRABS, TAP {_DRUM} ON ITS RIM UNTIL AN INDICATOR ON "
        f"THE RIM SWINGS LEAST, {_WHEEL} TURNING ON {_AXLE} CLAMPED ON A V-BLOCK."
    ),
    "drum-bond-cured": f"LEAVE {_DRUM} UNDISTURBED 24 H TO CURE.",
    # Owner ruling 2026-11-24, fit audit part 2, S4: the seat is seen, not
    # read (DETAIL B prints the drum face's window as REF); the semicolon of
    # the approved text is a comma here (rule 22's one-clause lint). Its own
    # check (rule 22, machinist review of run 20261125T172832344Z r2), with
    # the hand check sharing the strip below.
    "drum-seated": (
        f"CHECK {_DRUM} IS HARD AGAINST THE BOSS: NO LIGHT UNDER THE DRUM, NOT "
        "PROUD OF THE SPIGOT END (STRAIGHTEDGE)."
    ),
    _steps.DRUM_HELD_KEY: f"CHECK {_DRUM} DOES NOT TURN OR SLIDE BY HAND.",
    "drum-stripped": (
        f"IF {_step('drum-seated')} OR {_step(_steps.DRUM_HELD_KEY)} FAILS, PULL "
        f"{_DRUM} OFF {_WHEEL}."
    ),
    "drum-cleaned": (
        f"IF {_DRUM} WAS PULLED OFF, CLEAN IT AND THE SPIGOT TO BARE METAL."
    ),
    "drum-rebonded": (
        f"IF {_DRUM} WAS PULLED OFF, RETURN TO {_step(_steps.DRUM_BONDED_KEY)}."
    ),
    # Owner ruling 2026-11-24, fit audit part 2, C11 ("Yes, set to the trial
    # stack"), with question 18's bond: the trial runs dry (the steps module
    # says why). The axle is pushed on its shoulder only, through the
    # sleeve, over the thread (#2399); at the drilled bore's tightest corner
    # (a .0002 light press) the arbor press pushes it, the sleeve between.
    _steps.PRESS_SLEEVE_MADE_KEY: f"MAKE {PRESS_SLEEVE} FOR {_AXLE}.",
    _steps.SPACER_FITTED_KEY: f"SLIDE {_SPACER} ONTO THE SHANK OF {_AXLE}.",
    _steps.AXLE_DRY_FITTED_KEY: (
        f"PUSH {_AXLE} DRY INTO {_BAR}, THREADED END OUT, ON ITS SHOULDER "
        f"THROUGH THE {_step(_steps.PRESS_SLEEVE_MADE_KEY)} SLEEVE BY HAND OR IN "
        f"THE ARBOR PRESS, UNTIL ITS PLAIN END MEETS {_PLATE}."
    ),
    _steps.AXLE_TRIAL_KEY: f"TRIAL-FIT {_STACK} ON {_AXLE}, IN THAT ORDER.",
    # The shank step inside the hub, read directly (mg_wheel_group
    # TRIAL_STEP_INSIDE_HUB_MIN; Codjiflo r1 of #3529): the washer's bore is
    # under the shank's, so a step standing past the spigot face grounds the
    # washer on it and shows light, the S4 drum seat's way of seeing a seat.
    _steps.TRIAL_WASHER_SEATED_KEY: (
        f"CHECK {_WASHER} LIES ON THE SPIGOT FACE WITH NO LIGHT UNDER IT, "
        f"{_WHEEL} PUSHED TOWARD {_BAR}."
    ),
    # The trial reads the thread end at the go leaf's endshake (#3344).
    "trial-feeler-placed": (
        f"SLIDE THE {ENDSHAKE_GO_TEXT} FEELER BETWEEN {_WASHER} AND THE SPIGOT FACE, "
        f"{_WHEEL} PUSHED TOWARD {_BAR}."
    ),
    "trial-nuts-jammed": (
        f"JAM BOTH {_NUT} NUTS ON {_AXLE} WITH THE FEELER JUST NIPPED."
    ),
    # C11's three things to see: the first nut on thread, the thread end
    # inside DETAIL B, the plain end not proud (the flush start, never pushed
    # further in). The step inside the hub is the washer seat's.
    _steps.AXLE_NUT_ON_THREAD_KEY: (
        f"CHECK THE FIRST NUT RAN DOWN TO {_WASHER} ON THREAD ALL THE WAY, "
        "NOT SPINNING ON THE RELIEF NECK."
    ),
    _steps.AXLE_CHECKED_KEY: (
        f"CHECK THE THREAD END STANDS PAST THE SECOND NUT AS "
        f"{ENDSHAKE_DETAIL_TITLE} SETS IT (CALIPER DEPTH ROD)."
    ),
    # The one setting remedy: a short thread end moves the axle out, its
    # plain end sunk by the shortfall to the window's middle, and the trial
    # runs again from the washer seat. One action per step (rule 22).
    "trial-nuts-off": (
        f"IF ONLY THE THREAD END FELL SHORT, REMOVE THE NUTS AND THE FEELER FROM "
        f"{_AXLE}."
    ),
    "axle-sunk": (
        f"IF ONLY THE THREAD END FELL SHORT, SLIDE {_AXLE} OUT BY ITS SHORTFALL TO "
        f"THE MIDDLE OF {ENDSHAKE_DETAIL_TITLE}, READ AT ITS PLAIN END INSIDE THE "
        "BORE (CALIPER DEPTH ROD)."
    ),
    "trial-rerun": (
        f"IF ONLY THE THREAD END FELL SHORT, RETURN TO "
        f"{_step(_steps.TRIAL_WASHER_SEATED_KEY)}."
    ),
    # Any other failure: the trial comes off and the axle out, so a replaced
    # bar, spacer or axle restarts at the spacer like any other part. A part
    # outside its own limits, else the axle (its lengths, the stack's last
    # terms), is replaced, so the loop always ends on a new part. Each
    # sub-step is conditioned on the failure, so a passed trial skips them;
    # the measurement and the replacement are separate steps (rule 22).
    "trial-stripped": (
        f"IF {_step(_steps.TRIAL_WASHER_SEATED_KEY)}, "
        f"{_step(_steps.AXLE_NUT_ON_THREAD_KEY)} OR "
        f"{_step(_steps.AXLE_CHECKED_KEY)} FAILS ANY OTHER WAY, REMOVE {_TRIAL_OFF} "
        f"FROM {_AXLE}."
    ),
    "trial-axle-withdrawn": f"IF {_SPACER} WAS REMOVED, PUSH {_AXLE} OUT OF {_BAR}.",
    "stack-parts-measured": (
        f"IF {_AXLE} WAS PUSHED OUT, MEASURE {_STACK_PARTS} AGAINST THEIR DRAWING "
        "OR CATALOGUE LIMITS (MICROMETER)."
    ),
    "stack-part-replaced": "IF ONE MEASURES OUTSIDE ITS LIMITS, REPLACE IT.",
    "axle-replaced": (
        f"IF {_AXLE} WAS PUSHED OUT AND NO OTHER PART WAS REPLACED, REPLACE {_AXLE}."
    ),
    "trial-refitted": (
        f"IF {_AXLE} WAS PUSHED OUT, RETURN TO {_step(_steps.SPACER_FITTED_KEY)}."
    ),
    _steps.AXLE_SINK_RECORDED_KEY: (
        f"RECORD HOW FAR THE PLAIN END OF {_AXLE} STANDS INSIDE THE BORE "
        "(CALIPER DEPTH ROD, NONE WHEN FLUSH)."
    ),
    "trial-parts-removed": f"REMOVE {_TRIAL_OFF} FROM {_AXLE}.",
    "axle-withdrawn": f"PUSH {_AXLE} OUT OF {_BAR}.",
    # Rule 23 for the bond: the grade and the stop here, NOTE 1 the degrease,
    # the coat on the length inside the bar only and the cure; held square
    # to the bar while wet with owned equipment (the surface plate and the
    # combination square), cured untouched, then accepted by hand.
    _steps.AXLE_BONDED_KEY: (
        f"BOND {_AXLE} INTO {_BAR} WITH {BOND_GRADE}, {BOND_NOTE_REF}, THE SAME "
        f"WAY AS {_step(_steps.AXLE_DRY_FITTED_KEY)}, UNTIL ITS PLAIN END STANDS AT "
        f"THE {_step(_steps.AXLE_SINK_RECORDED_KEY)} READING (CALIPER DEPTH ROD)."
    ),
    "axle-squared": (
        f"AT ONCE, BEFORE IT GRABS, SQUARE {_AXLE} TO A SQUARE STANDING ON "
        "THE SURFACE PLATE AT TWO PLACES A QUARTER TURN APART."
    ),
    "axle-bond-cured": f"LEAVE {_AXLE} UNDISTURBED 24 H TO CURE.",
    _steps.AXLE_HELD_KEY: f"CHECK {_AXLE} DOES NOT TURN OR SLIDE BY HAND.",
    "axle-stripped": f"IF IT DOES, PUSH {_AXLE} OUT OF {_BAR}.",
    "axle-cleaned": (
        f"IF {_AXLE} WAS PUSHED OUT, CLEAN IT AND THE BORE OF {_BAR} TO BARE METAL."
    ),
    "axle-rebonded": (
        f"IF {_AXLE} WAS PUSHED OUT, RETURN TO {_step(_steps.AXLE_BONDED_KEY)}."
    ),
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
    # The spacer the trial set the axle with, off for the bond (NOTE 1 wipes
    # the squeeze-out at the bar's face), back on the shank against the bar.
    "spacer-refitted": f"SLIDE {_SPACER} ONTO THE SHANK OF {_AXLE} AGAIN, AGAINST {_BAR}.",
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
    # The final reading's own remedy. The axle is bonded at a setting the
    # trial accepted at the go leaf's endshake, so the set endshake can only
    # lower the thread end (by up to mg_wheel_group.TRIAL_ENDSHAKE_DROP) and
    # never past the high limit: a short final reading closes the endshake
    # back to the go leaf, where it reads what the trial read (the drop is
    # bounded by mg_wheel_group.TRIAL_ENDSHAKE_DROP, so no new limit).
    # Loosen, place the go leaf, close, remove it, return to the locknut so
    # the jam, the endshake re-check and this reading all run again on the
    # closed setting: one action per step, none undoing another (rule 22;
    # Codjiflo r1 P2 of #3601: returning to the endshake set reset it).
    "locknut-backed-off": "IF IT FALLS SHORT, LOOSEN THE SECOND NUT.",
    "endshake-feeler-placed": (
        f"IF THE SECOND NUT WAS LOOSENED, SLIDE THE {ENDSHAKE_GO_TEXT} FEELER BETWEEN "
        f"{_WASHER} AND THE SPIGOT FACE, {_WHEEL} PUSHED TOWARD {_BAR}."
    ),
    "axle-endshake-closed": (
        "IF THE SECOND NUT WAS LOOSENED, TIGHTEN THE FIRST NUT UNTIL THE FEELER IS "
        "JUST NIPPED."
    ),
    "endshake-feeler-removed": "IF THE SECOND NUT WAS LOOSENED, REMOVE THE FEELER.",
    "locknut-rejammed": (
        f"IF THE SECOND NUT WAS LOOSENED, RETURN TO {_step(_steps.LOCKNUT_JAMMED_KEY)}."
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
    # A knot round the standing wire is a running noose (#3086): it is drawn
    # closed on the groove here, so the lever's load cannot close it later
    # and the knot check reads the knot alone.
    "lever-wire-hook-knotted": "KNOT THE WIRE END ROUND THE WIRE BELOW THE GROOVE.",
    "lever-wire-hook-closed": "SLIDE THE KNOT UP UNTIL THE LOOP CLOSES IN THE GROOVE.",
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
    # The toggle prints no length (#2796: a step carries no dimension), but it
    # is bounded by a feature the builder holds: no longer than the drum's
    # face width (its axial length). test_mg_wheel_axle_spacer_drawing proves
    # a toggle that long still clears the back washer and spacer;
    # mg_wheel_group's TAIL_STACK_CLEARANCE proves the modelled 1/8 toggle.
    # It must span the hole it lies across, which sets its lower bound.
    "lever-wire-tie-knotted": (
        "KNOT THE WIRE TAIL BEHIND THE HOLE ROUND A SHORT OFFCUT OF THE WIRE, "
        f"SHORTER THAN THE FACE WIDTH OF {_DRUM}, LAID ACROSS THE HOLE."
    ),
    # Each hand-made joint is checked to hold (rule 23). A slipped knot has
    # let the wire run, so the wheel's rest angle is lost with it: the remedy
    # starts the wire again from the hook (#3086).
    "lever-wire-knots-held": "CHECK NEITHER KNOT SLIPS UNDER A LIGHT PULL BY HAND.",
    "lever-wire-cut-off": "IF ONE SLIPS, CUT THE WIRE OFF.",
    "lever-wire-renewed": (
        f"IF IT WAS CUT OFF, RETURN TO {_step(_steps.WIRE_HOOKED_KEY)} WITH A NEW "
        "LENGTH OF WIRE."
    ),
    _steps.WIRE_TIED_KEY: "TRIM BOTH WIRE TAILS CLOSE TO THEIR KNOTS.",
}
if tuple(STEP_TEXT) != _steps.SEQUENCE:
    raise AssertionError("STEP_TEXT must follow mg_magnifier_assembly_steps.SEQUENCE")
ASSEMBLY_STEPS = tuple(
    f"{_steps.step_number(key)}. {text}" for key, text in STEP_TEXT.items()
)
# The sequence prints in three titled groups, each opening at a numbered
# step; the wire group's title states when its steps run, so no step carries
# a precondition clause. Steps cite the drawing's sheets, views and BOM items.
STEP_GROUPS = (
    ("WHEEL GROUP (EXPLODED ON SHEET 2):", _steps.DRUM_BONDED_KEY),
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
_GROUP_STARTS = (*_GROUP_INDICES, len(ASSEMBLY_STEPS))
# Each group's title (its colon dropped) and numbered steps, as ASSEMBLY.md
# prints them.
STEP_SECTIONS = tuple(
    (title.rstrip(":"), ASSEMBLY_STEPS[start:end])
    for (title, _key), start, end in zip(
        STEP_GROUPS, _GROUP_STARTS, _GROUP_STARTS[1:], strict=False
    )
)
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
