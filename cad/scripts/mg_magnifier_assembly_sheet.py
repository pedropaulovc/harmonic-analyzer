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
    UNIT,
)
from _title_block_units import LENGTH_UNITS, render_number
from sh_vn_music_wire_lever_spec import BOM_DESCRIPTION as _WIRE_BOM_DESCRIPTION
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

# Rule 23: a specified anaerobic bond equals a press fit. The one bond in this
# package is the slip-fit drum's fallback (provisional ruling 2026-11-06,
# pending owner confirmation); its degrease, apply, keep-off and cure rules
# print once, as a general note with the checks on sheet 5, in two lines
# (the sheet 5 column has under three to spare).
BOND_GRADE = "LOCTITE 638"
BOND_NOTE_REF = "NOTE 1 (SHEET 5)"
BOND_NOTE = (
    f"NOTE 1, {BOND_GRADE} BOND: DEGREASE; APPLY TO THE SPIGOT ONLY, NONE IN THE "
    "AXLE BORE OR WIRE SEATS; CURE 24 H AT ROOM TEMPERATURE BEFORE LOAD OR OIL. "
    f"ACCEPT: {_DRUM} DOES NOT TURN BY HAND."
)

# One line per step key (mg_magnifier_assembly_steps.SEQUENCE); each step does
# one thing, a check and its remedy are separate steps (rule 22). Settings are
# named, never valued: their values print as the model dimensions on sheet 1.
# Ends and sides name physical features or a lettered view, never a compass,
# a clock or the machine's front and back (the principal views print unnamed).
STEP_TEXT = {
    _steps.DRUM_PRESSED_KEY: (
        f"PRESS {_DRUM} ONTO THE SPIGOT OF {_WHEEL}, HARD AGAINST THE BOSS."
    ),
    _steps.DRUM_HELD_KEY: f"CHECK {_DRUM} DOES NOT TURN OR SLIDE BY HAND.",
    # A press that goes on by hand is a slip fit (rule 23). Provisional ruling
    # 2026-11-06, pending owner confirmation: a bond equals a press, so a slip
    # drum is bonded rather than the wheel remade (BOND_NOTE).
    "drum-slip-fit": (
        f"IF IT DOES, OR {_DRUM} SLID ON BY HAND: PULL IT OFF AND BOND IT TO "
        f"{_WHEEL} WITH {BOND_GRADE}, {BOND_NOTE_REF}."
    ),
    # Machinist review (run 20261024T053015093Z): the REF depth is the first
    # stop; the ACCEPT limit governs any further press.
    _steps.AXLE_PRESSED_KEY: (
        f"PRESS {_AXLE} INTO {_BAR}, THREADED END OUT, UNTIL ITS STEP REACHES "
        f"THE REF DEPTH IN {PRESS_DETAIL_TITLE}."
    ),
    _steps.AXLE_HELD_KEY: f"CHECK {_AXLE} DOES NOT TURN OR SLIDE BY HAND.",
    "axle-slip-fit": (
        f"IF IT DOES, OR {_AXLE} SLID IN BY HAND: PRESS IT OUT, REMAKE {_AXLE} TO "
        f"ITS PRESS SIZE AND RETURN TO {_step(_steps.AXLE_PRESSED_KEY)}."
    ),
    _steps.AXLE_TRIAL_KEY: f"TRIAL-FIT {_STACK} ON {_AXLE}, IN THAT ORDER.",
    "trial-nuts-jammed": (
        f"JAM BOTH {_NUT} NUTS ON {_AXLE} WITH {_WHEEL} JUST FREE."
    ),
    _steps.AXLE_CHECKED_KEY: (
        f"CHECK BOTH ACCEPT LIMITS IN {PRESS_DETAIL_TITLE} WITH A CALIPER DEPTH "
        "ROD ON THE THREAD END PAST THE SECOND NUT."
    ),
    "trial-parts-removed": f"REMOVE THE TRIAL NUTS AND PARTS FROM {_AXLE}.",
    # A re-press goes back through the hold check before the trial fit.
    "axle-pressed-further": (
        f"IF {_step(_steps.AXLE_CHECKED_KEY)} READ OVER THE MAX, PRESS {_AXLE} IN "
        f"BY THE EXCESS AND RETURN TO {_step(_steps.AXLE_HELD_KEY)}."
    ),
    "axle-pressed-back": (
        f"IF {_step(_steps.AXLE_CHECKED_KEY)} READ UNDER THE MIN, PRESS {_AXLE} "
        f"BACK OUT FROM THE BACK FACE OF {_BAR} BY THE SHORTFALL AND RETURN TO "
        f"{_step(_steps.AXLE_HELD_KEY)}."
    ),
    "column-clamps-fitted": (
        f"FIT {_item(CLAMP_FRONT)} AND {_item(CLAMP_BACK)} TO {_BAR} AS THE "
        "SHEET 2 EXPLODED VIEW SHOWS."
    ),
    # Rule 23 at the package boundary: the screws are seated and accepted at
    # the MHA-HA-00 step that clamps the bar, cited by number.
    _steps.COLUMN_CLAMP_STARTED_KEY: (
        f"START BOTH {_item(CLAMP_SCREW)} SCREWS THROUGH ITEMS "
        f"{ITEM_NUMBERS[WHEEL_BAR]} AND {ITEM_NUMBERS[CLAMP_FRONT]} INTO "
        f"{_item(CLAMP_BACK)}, LOOSE; "
        f"{_ha_steps.step_ref('magnifier-bar-clamped')} TIGHTENS THEM."
    ),
    "axle-oiled": f"WIPE LIGHT MACHINE OIL ON {_AXLE}.",
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
        f"IF {ENDSHAKE_GO_TEXT} DOES NOT ENTER, BACK THE NUT OFF SLIGHTLY AND "
        f"REPEAT {_step(_steps.ENDSHAKE_CHECKED_KEY)}."
    ),
    "endshake-tightened": (
        f"IF {ENDSHAKE_NO_GO_TEXT} ENTERS, TIGHTEN THE NUT SLIGHTLY AND REPEAT "
        f"{_step(_steps.ENDSHAKE_CHECKED_KEY)}."
    ),
    _steps.LOCKNUT_JAMMED_KEY: (
        f"HOLD THE FIRST NUT AND JAM THE SECOND {_NUT} NUT AGAINST IT."
    ),
    "endshake-rechecked": f"REPEAT THE {_step(_steps.ENDSHAKE_CHECKED_KEY)} CHECK.",
    "locknut-reset": (
        f"IF IT FAILS, LOOSEN THE SECOND NUT AND RETURN TO "
        f"{_step(_steps.ENDSHAKE_SET_KEY)}."
    ),
    "axle-accepted": f"REPEAT THE {_step(_steps.AXLE_CHECKED_KEY)} CHECK.",
    _steps.LEVER_THREADED_KEY: (
        f"SCREW {_LEVER} INTO {_BRACKET} UNTIL ITS FLAT TIP STANDS PROUD OF THE "
        f"FAR FACE AS {THREAD_PROJECTION_DETAIL_TITLE} SETS IT; READ THE "
        "PROJECTION WITH A CALIPER DEPTH ROD."
    ),
    "clamp-thumb-screw-started": (
        f"START ONE {_THUMB} INTO THE TAP OF {_CLAMP} THAT BREAKS INTO ITS CROSS "
        "BORE, CLEAR OF THE BORE."
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
        "CLEAR OF ITS BORE."
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
    # The upper end takes the TIE 1 method. The wire is tied in the rest pose
    # its run is derived at (sh_vn_music_wire_lever_geom), which MHA-HA-00 sets
    # as every channel amplitude at zero with the plate top level; the hook,
    # rod and drum lane share one plumb plane (option A1).
    _steps.WIRE_HOOKED_KEY: (
        f"HOOK {_WIRE} LEVER WIRE IN THE SPIGOT GROOVE OF {_FIXTURE} AND LAY IT "
        f"ONCE ROUND, LEAVING THE GROOVE STRAIGHT DOWN TOWARD {_DRUM} AS THE "
        "RIGHT SIDE VIEW ON SHEET 1 SHOWS."
    ),
    "lever-wire-hook-twisted": (
        "TWIST THE WIRE END BACK ON THE WIRE AT LEAST THREE TURNS."
    ),
    "lever-wire-hook-trimmed": "TRIM THE WIRE TAIL CLOSE TO THE TWIST.",
    "machine-at-rest": (
        "SET MHA-HA-00 AT REST: EVERY CHANNEL AMPLITUDE AT ZERO AND THE "
        "MHA-SM-03 PLATE TOP LEVEL."
    ),
    "wheel-turned": (
        f"TURN {_WHEEL} UNTIL TIE 1, THE AXIAL HOLE IN ITS BOSS, STANDS AT THE "
        f"{WHEEL_REST_VIEW_TITLE} ANGLE BELOW THE BOTTOM EDGE OF {_BAR} "
        "(PROTRACTOR); TWO SPOKES THEN LIE ALONG THE BAR."
    ),
    "lever-wire-wrapped": (
        f"LEAD THE WIRE DOWN TO {_DRUM} AND WRAP IT ROUND {_DRUM} TO TIE 1, "
        f"CLOCKWISE AS SEEN IN {WHEEL_REST_VIEW_TITLE}."
    ),
    "lever-wire-through-tie": "PASS THE WIRE END THROUGH TIE 1 AND PULL IT TAUT.",
    "lever-wire-tie-twisted": (
        "TWIST THE WIRE TAIL BACK ON ITSELF AT LEAST THREE TURNS."
    ),
    _steps.WIRE_TIED_KEY: "TRIM THE WIRE TAIL CLOSE TO THE TWIST.",
}
if tuple(STEP_TEXT) != _steps.SEQUENCE:
    raise AssertionError("STEP_TEXT must follow mg_magnifier_assembly_steps.SEQUENCE")
ASSEMBLY_STEPS = tuple(
    f"{_steps.step_number(key)}. {text}" for key, text in STEP_TEXT.items()
)
# The sequence prints in three titled groups, each opening at its first key;
# the wire group's title states when its steps run, so no step carries a
# precondition clause.
STEP_GROUPS = (
    ("WHEEL GROUP (EXPLODED ON SHEET 2):", _steps.DRUM_PRESSED_KEY),
    ("LEVER GROUP (EXPLODED ON SHEET 3):", _steps.LEVER_THREADED_KEY),
    (
        "LEVER WIRE, ON THE MACHINE, AFTER MHA-HA-00 HAS CLAMPED "
        f"{_BAR} IN PLACE AND SCREWED {_BRACKET} TO {SUMMING_LEVER_NUMBER}:",
        _steps.WIRE_HOOKED_KEY,
    ),
)
if STEP_GROUPS[0][1] != _steps.SEQUENCE[0] or [
    _steps.step_number(key) for _title, key in STEP_GROUPS
] != sorted(_steps.step_number(key) for _title, key in STEP_GROUPS):
    raise AssertionError("the step groups must open the sequence in order")
ASSEMBLY_CHECKS = (
    f"CHECK: WITH BOTH {_NUT} NUTS SET, {_WHEEL} TURNS FREE, NO RATTLE.",
    f"CHECK: {_CLAMP} AND {_FIXTURE} HOLD THEIR SETTINGS WHEN {_LEVER} IS "
    "ROCKED BY HAND.",
    f"CHECK: {_WIRE} CLEARS THE RIM, SPOKES AND BOSS OF {_WHEEL}.",
    f"CHECK: WITH {_LEVER} ROCKED BY HAND TO EACH END OF ITS TRAVEL ON THE "
    f"MACHINE, {_WIRE} STAYS WRAPPED ON {_DRUM} SHORT OF TIE 1.",
    f"LOOSE ITEMS: BOTH {_item(BRACKET_SCREW)} SCREWS GO WITH THE ASSEMBLY; "
    f"{_ha_steps.step_ref('magnifier-bracket-screwed')} DRIVES THEM THROUGH "
    f"{_BRACKET} INTO {SUMMING_LEVER_NUMBER} UNTIL THE HEADS SEAT.",
    BOND_NOTE,
)
