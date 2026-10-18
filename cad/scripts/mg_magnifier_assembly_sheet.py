"""Drawing-only data of the magnifier fitter package (MHA-MG-000).

The BOM rows (families, quantities, descriptions), the axle-stack dimensions
the sheet imports, the setting callouts, the exploded-view caption, the
fit-up steps and the checks the sheets print. Only draw_mg_magnifier_assembly
(and its tests) import this module; no assembly builder may
(``test_assembly_sheet_isolation`` pins it), so a wording edit here does not
rebuild the magnifier assembly. No SolidWorks.
"""

from __future__ import annotations

import mg_magnifier_assembly_steps as _steps
import vn_clamp_screw_spec as _clamp_screw
import vn_magnifying_bracket_screw_spec as _bracket_screw
from _inch_fraction import inch_fraction
from _mcmaster_91882a221 import SHANK_LEN as _THUMB_SHANK_LEN
from _mcmaster_91882a221 import THREAD as _THUMB_THREAD
from mg_magnifier_assembly_spec import (
    CLAMP_STATION_DIMENSION,
    ENDSHAKE_DIMENSION,
    FEATURE,
    FIXTURE_DROP_DIMENSION,
    PRESS_GAUGE_DIMENSION,
)
from vn_lever_wire_geom import WIRE_DIA as _WIRE_DIA

# The axle-stack dimensions the AXLE AS PRESSED and WHEEL ENDSHAKE details
# import (the builder marks the banded ones, DIMENSION_TOLERANCES).
DRAWING_DIMENSIONS = {FEATURE: {PRESS_GAUGE_DIMENSION, ENDSHAKE_DIMENSION}}

# --- Setting callouts ---------------------------------------------------------
# Each callout states what its band protects, naming the mate the tight gauge
# serves (drawing-guidelines.md rule 4; machinist review r6 read the ±0.05 as
# over-tight without it: mg_wheel_group's worst-case stack spends it, leaving
# LOCKNUT_THREAD_MARGIN 0.002). The gauge's prints above its
# value, on one line: SolidWorks keeps a line break in that compartment but
# prints none of the callout (run 20261012T185729782Z). The endshake's
# prints below, where line breaks print.
DIMENSION_CALLOUTS = {
    PRESS_GAUGE_DIMENSION: "PRESS GAUGE: KEEPS MHA-VN-025 LOCKNUT ON FULL THREAD",
    ENDSHAKE_DIMENSION: "\n".join(
        (
            "WHEEL FREE, NO RATTLE;",
            "SET BY THE FIRST NUT,",
            "LOCKED BY THE SECOND",
        )
    ),
}

# --- Lever setting callouts (LEVER_FEATURE) -----------------------------------
# What each setting does (joint_retention's clamp and fixture rows): the
# clamp's radius from the knife is the magnification; the fixture's height on
# the rod places the trace. Above-callouts print on one line only.
LEVER_CALLOUTS = {
    CLAMP_STATION_DIMENSION: "CLAMP STATION: SETS MAGNIFICATION",
    FIXTURE_DROP_DIMENSION: "FIXTURE DROP:\nSETS TRACE HEIGHT",
}

# --- Fitter package -----------------------------------------------------------
DRAWING_NUMBER = _steps.DRAWING_NUMBER
WHEEL_BAR = "mg-wheel-bar"
CLAMP_FRONT = "sh-column-clamp-front"
CLAMP_BACK = "sh-column-clamp-back"
CLAMP_SCREW = "vn-clamp-screw"
AXLE = "mg-wheel-axle"
SPACER = "mg-wheel-axle-spacer"
BACK_WASHER = "vn-wheel-axle-back-washer"
WHEEL = "mg-magnifying-wheel"
DRUM = "mg-wheel-drum"
FRONT_WASHER = "vn-wheel-axle-front-washer"
NUT = "vn-wheel-axle-nut"
LEVER = "mg-magnifying-lever"
BRACKET = "mg-magnifying-bracket"
BRACKET_SCREW = "vn-magnifying-bracket-screw"
CLAMP = "mg-magnifying-clamp"
THUMB_SCREW = "vn-thumb-screw"
ROD = "mg-magnifying-vertical-rod"
FIXTURE = "mg-output-fixture"
WIRE = "vn-lever-wire"
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
    WIRE: f"LEVER WIRE, DIA {_WIRE_DIA:.1f}",
}
if set(BOM_DESCRIPTIONS) != set(BOM_ORDER) or len(set(BOM_ORDER)) != len(BOM_ORDER):
    raise AssertionError("every BOM family needs exactly one description")

EXPLODED_CAPTION = "EXPLODED VIEW - ASSEMBLY SEQUENCE ON SHEET 4"

# One line per step key (mg_magnifier_assembly_steps.SEQUENCE). Settings are
# named, never valued: their values print as the model dimensions on sheet 1.
# Ends and sides are named by features the fitter can see (the lever's PRESS
# ZONE on MHA-MG-003, the bracket), not compass words no view defines
# (machinist review r1).
STEP_TEXT = {
    _steps.AXLE_PRESSED_KEY: (
        "PRESS THE MHA-MG-007 WHEEL AXLE INTO THE MHA-MG-008 WHEEL BAR FROM ITS "
        "FRONT FACE TO THE PRESS GAUGE (SHEET 1, AXLE AS PRESSED)."
    ),
    _steps.COLUMN_CLAMP_STARTED_KEY: (
        "FIT THE MHA-SH-001 FRONT AND MHA-SH-002 BACK COLUMN CLAMPS BEHIND THE "
        "BAR; START BOTH MHA-VN-021 SCREWS THROUGH THE BAR AND THE FRONT CLAMP "
        "INTO THE BACK CLAMP, LOOSE. MHA-HA-000 SETS THE BAR ON THE FRONT "
        "COLUMN AND TIGHTENS THEM."
    ),
    "drum-pressed": (
        "PRESS THE MHA-MG-010 DRUM ON THE MHA-MG-005 WHEEL'S FRONT SPIGOT, HARD "
        "AGAINST THE BOSS; ITS FRONT FACE STAYS BELOW THE SPIGOT FACE."
    ),
    "wheel-stacked": (
        "LIGHT OIL ON THE AXLE; ON IT, IN ORDER: THE MHA-MG-011 SPACER, THE "
        "MHA-VN-057 BACK WASHER, THE WHEEL WITH ITS DRUM FORWARD, THE "
        "MHA-VN-058 FRONT WASHER."
    ),
    _steps.ENDSHAKE_SET_KEY: (
        "RUN THE FIRST MHA-VN-025 NUT DOWN ON THE FRONT WASHER TO THE WHEEL "
        "ENDSHAKE (SHEET 1): THE WHEEL TURNS FREE WITHOUT RATTLE."
    ),
    _steps.LOCKNUT_JAMMED_KEY: (
        "HOLD THE FIRST NUT; JAM THE SECOND MHA-VN-025 NUT AGAINST IT. RECHECK "
        "THE ENDSHAKE."
    ),
    "collar-pressed": (
        "HOLDING THE MHA-MG-003 LEVER NEAR ITS PRESS-ZONE END, PRESS THE "
        "MHA-MG-001 BRACKET'S COLLAR ONTO THAT END, LEVER END FLUSH WITH THE "
        "COLLAR'S OUTER FACE. THE TWO MHA-VN-050 SCREWS GO WITH THE LEVER: "
        "MHA-HA-000 DRIVES THEM INTO THE SUMMING LEVER."
    ),
    _steps.CLAMP_SET_KEY: (
        "SLIDE THE MHA-MG-002 CLAMP ONTO THE LEVER FROM ITS FREE END, THE END "
        "NEARER THE BORE UP, TO THE CLAMP STATION (SHEET 1); TIGHTEN ITS "
        "MHA-VN-011 THUMB SCREW BY HAND."
    ),
    # #1559: the rod is retained by its own thread, seated on its shoulder.
    _steps.FIXTURE_SET_KEY: (
        "PASS THE MHA-MG-004 ROD'S THREADED END UP THROUGH THE MHA-MG-006 "
        "FIXTURE; SCREW IT INTO THE CLAMP'S BOTTOM TAP BY HAND UNTIL ITS "
        "SHOULDER SEATS. SET THE FIXTURE AT THE FIXTURE DROP (SHEET 1), SPIGOT "
        "TOWARD THE BRACKET; TIGHTEN ITS MHA-VN-011 THUMB SCREW BY HAND."
    ),
    # Machinist review r3: the step must name how the upper end is secured
    # and the state the wire is tied in. The upper end takes the tie-1
    # method; the state is the rest pose the wire run is derived at
    # (vn_lever_wire_geom), which MHA-HA-000 sets as every channel amplitude
    # at zero with the plate top level (its pen wire is tied in the same
    # state), with TIE 1 at 6 o'clock (mg_wheel_group.LEVER_WIRE_WRAP_DEG).
    _steps.WIRE_HOOKED_KEY: (
        "AFTER MHA-HA-000 HAS CLAMPED THE BAR AND SCREWED THE BRACKET TO THE "
        "SUMMING LEVER: LAY THE MHA-VN-066 LEVER WIRE ONCE ROUND THE FIXTURE'S "
        "SPIGOT GROOVE, TWIST THE END BACK ON THE WIRE AT LEAST THREE TURNS "
        "AND TRIM THE TAIL; THE WIRE LEAVES THE GROOVE AT ITS FRONT."
    ),
    _steps.WIRE_TIED_KEY: (
        "WITH EVERY CHANNEL AMPLITUDE AT ZERO AND THE MHA-SM-003 PLATE TOP "
        "LEVEL (MHA-HA-000), TURN THE WHEEL TO BRING TIE 1, THE AXIAL HOLE IN "
        "THE WHEEL BOSS, TO 6 O'CLOCK SEEN FROM THE FRONT. LEAD THE WIRE DOWN "
        "TO THE DRUM'S RIGHT SIDE; WRAP IT CLOCKWISE DOWN THE DRUM TO TIE 1; "
        "PASS IT THROUGH TAUT, TWIST THE TAIL BACK ON ITSELF AT LEAST THREE "
        "TURNS AND TRIM THE TAIL."
    ),
}
if tuple(STEP_TEXT) != _steps.SEQUENCE:
    raise AssertionError("STEP_TEXT must follow mg_magnifier_assembly_steps.SEQUENCE")
ASSEMBLY_STEPS = tuple(
    f"{_steps.step_number(key)}. {text}" for key, text in STEP_TEXT.items()
)
ASSEMBLY_CHECKS = (
    "CHECK: WITH BOTH NUTS SET THE WHEEL TURNS FREE, NO RATTLE.",
    "CHECK: THE CLAMP AND THE FIXTURE HOLD THEIR SETTINGS WHEN THE LEVER IS "
    "ROCKED BY HAND.",
    "CHECK: THE LEVER WIRE CLEARS THE WHEEL RIM, SPOKES AND BOSS AND, "
    "ROCKED THROUGH THE LEVER'S TRAVEL, STAYS WRAPPED ON THE DRUM SHORT OF "
    "TIE 1.",
)
