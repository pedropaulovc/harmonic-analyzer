"""The MHA-MG-000 magnifier fitter package: its settings, BOM text and steps.

Two settings belong to no single part: the press gauge the wheel axle is pressed
to in the bar, and the endshake the first nut sets. Each one is printed as a
native model dimension on the MHA-MG-000 sheet. A construction chain in the
assembly carries both (the ms-measuring-stick ClampedSetting pattern). It runs
along the axle centreline on the Right plane, through four stations: the bar
front face, the shank step, the wheel's spigot face and the front washer. The
chain is blanked, so it prints only in the drawing view that dimensions it.

Two more are the lever group's operator settings: the clamp station on the
lever and the output fixture's drop below the lever axis. A second blanked
chain on the Front plane carries them (LEVER_FEATURE), from the lever rod's
west tip along its axis to the clamp centre, then down the vertical-rod line
to the fixture axis. They print at the title block's general tolerance.
"""

from __future__ import annotations

import magnifying_bracket_joint_layout as _bracket
import mg_magnifier_assembly_steps as _steps
import mg_magnifying_lever_geom as _lever
import mg_output_fixture_geom as _fixture
import mg_wheel_axle_spec as _pin
import mg_wheel_bar_geom as _bar
import mg_wheel_group as _group
import vn_clamp_screw_spec as _clamp_screw
import vn_magnifying_bracket_screw_spec as _bracket_screw
from _mcmaster_91882a221 import SHANK_LEN as _THUMB_SHANK_LEN
from _mcmaster_91882a221 import THREAD as _THUMB_THREAD
from vn_lever_wire_geom import WIRE_DIA as _WIRE_DIA
from vn_lever_wire_geom import WHEEL_BAR_Y, WHEEL_X

# The axle centreline in the machine frame: x, y of the bore; z runs from the
# bar's front face forward (-z), station d at z = BAR_FRONT_Z - d.
AXLE_X = WHEEL_X
AXLE_Y = WHEEL_BAR_Y
BAR_FRONT_Z = _bar.BAR_FRONT_Z

PRESS_GAUGE = _pin.PRESS_GAUGE
PRESS_GAUGE_TOL = _pin.PRESS_GAUGE_TOL
# The modelled endshake sits mid-band, so its band prints symmetric.
ENDSHAKE = _group.ENDSHAKE
ENDSHAKE_TOL = _group.ENDSHAKE_MAX - _group.ENDSHAKE
if abs((_group.ENDSHAKE - _group.ENDSHAKE_MIN) - ENDSHAKE_TOL) > 1e-9:
    raise AssertionError("the endshake band is not symmetric about its model value")

# Chain stations d (from the bar front face) along the axle centreline.
STEP_D = PRESS_GAUGE
HUB_FRONT_D = _group.HUB_FRONT_D
WASHER_D = _group.FRONT_WASHER_D
if abs((WASHER_D - HUB_FRONT_D) - ENDSHAKE) > 1e-9:
    raise AssertionError("the front washer no longer sits one endshake off the hub")
if not 0.0 < HUB_FRONT_D - STEP_D:
    raise AssertionError("the shank step must stand inside the wheel hub")
CHAIN_D = (0.0, STEP_D, HUB_FRONT_D, WASHER_D)

FEATURE = "AxleStackReference"
PRESS_GAUGE_DIMENSION = "PressGauge"
ENDSHAKE_DIMENSION = "Endshake"
DRAWING_DIMENSIONS = {FEATURE: {PRESS_GAUGE_DIMENSION, ENDSHAKE_DIMENSION}}
DRAWING_PRECISION = {FEATURE: {PRESS_GAUGE_DIMENSION: 2, ENDSHAKE_DIMENSION: 2}}
TOLERANCE_PRECISION = 2
DIMENSION_TOLERANCES = {
    PRESS_GAUGE_DIMENSION: PRESS_GAUGE_TOL,
    ENDSHAKE_DIMENSION: ENDSHAKE_TOL,
}
# Each callout states what its band protects. The gauge's prints above its
# value, on one line: SolidWorks keeps a line break in that compartment but
# prints none of the callout (run 20261012T185729782Z). The endshake's
# prints below, where line breaks print.
DIMENSION_CALLOUTS = {
    PRESS_GAUGE_DIMENSION: "PRESS GAUGE: KEEPS WHEEL LOCKNUT ON FULL THREAD",
    ENDSHAKE_DIMENSION: "\n".join(
        (
            "WHEEL FREE, NO RATTLE;",
            "SET BY THE FIRST NUT,",
            "LOCKED BY THE SECOND",
        )
    ),
}

# --- The lever group's settings (LEVER_FEATURE, Front plane: sketch x is
# machine x, sketch y machine y) ---------------------------------------------
# The lever rod lies along machine x at the bracket's height; its west dome
# tip is the collar station east of the bracket (Ry(180) placement).
LEVER_AXIS_Y = _bracket.BRACKET_ORIGIN[1]
LEVER_TIP_X = _bracket.BRACKET_ORIGIN[0] + _lever.COLLAR_LOCAL_X
CLAMP_STATION = _lever.CLAMP_LOCAL_X
CLAMP_CENTRE_X = LEVER_TIP_X - CLAMP_STATION
FIXTURE_AXIS_Y = _fixture.FIXTURE_AXIS_Y
FIXTURE_DROP = LEVER_AXIS_Y - FIXTURE_AXIS_Y
if not 0.0 < FIXTURE_DROP:
    raise AssertionError("the output fixture must hang below the lever axis")
LEVER_FEATURE = "LeverSettingReference"
CLAMP_STATION_DIMENSION = "ClampStation"
FIXTURE_DROP_DIMENSION = "FixtureDrop"
LEVER_DRAWING_DIMENSIONS = {
    LEVER_FEATURE: {CLAMP_STATION_DIMENSION, FIXTURE_DROP_DIMENSION}
}
LEVER_DRAWING_PRECISION = {
    LEVER_FEATURE: {CLAMP_STATION_DIMENSION: 1, FIXTURE_DROP_DIMENSION: 1}
}
# What each setting does (joint_retention's clamp and fixture rows): the
# clamp's radius from the knife is the magnification; the fixture's height on
# the rod places the trace. Above-callouts print on one line only.
LEVER_CALLOUTS = {
    CLAMP_STATION_DIMENSION: "CLAMP STATION: SETS MAGNIFICATION",
    FIXTURE_DROP_DIMENSION: "FIXTURE DROP:\nSETS TRACE HEIGHT",
}

# --- Fitter package -----------------------------------------------------------
ASM_NAME = "mg-magnifier"
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
# below name the parts the same way, with their part numbers.
BOM_DESCRIPTIONS = {
    AXLE: "WHEEL AXLE",
    WHEEL_BAR: "WHEEL BAR",
    CLAMP_FRONT: "COLUMN CLAMP, FRONT",
    CLAMP_BACK: "COLUMN CLAMP, BACK",
    CLAMP_SCREW: "#8-32 X 1-1/4 FILLISTER SCREW",
    DRUM: "WHEEL DRUM",
    WHEEL: "MAGNIFYING WHEEL",
    SPACER: "WHEEL AXLE SPACER",
    BACK_WASHER: "WHEEL BACK WASHER",
    FRONT_WASHER: "WHEEL FRONT WASHER",
    NUT: "#4-40 HEX NUT",
    LEVER: "MAGNIFYING LEVER",
    BRACKET: "MAGNIFYING BRACKET",
    BRACKET_SCREW: f"{_bracket_screw.THREAD} X 1/4 FILLISTER SCREW",
    CLAMP: "MAGNIFYING CLAMP",
    THUMB_SCREW: f"{_THUMB_THREAD} X 7/16 KNURLED THUMB SCREW",
    ROD: "VERTICAL ROD",
    FIXTURE: "OUTPUT FIXTURE",
    WIRE: f"LEVER WIRE, DIA {_WIRE_DIA:.1f}",
}
if set(BOM_DESCRIPTIONS) != set(BOM_ORDER) or len(set(BOM_ORDER)) != len(BOM_ORDER):
    raise AssertionError("every BOM family needs exactly one description")
# The printed lengths are the vendor parts' own (inch stock, 25.4 mm/in).
for _length_mm, _inches in (
    (_clamp_screw.SHANK_LEN, 1.25),
    (_bracket_screw.LENGTH, 0.25),
    (_THUMB_SHANK_LEN, 7.0 / 16.0),
):
    if abs(_length_mm - _inches * 25.4) > 1e-6:
        raise AssertionError(f"a BOM screw length no longer reads {_inches} in")

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
        "ON THE AXLE, IN ORDER: THE MHA-MG-011 SPACER, THE MHA-VN-057 BACK "
        "WASHER, THE WHEEL WITH ITS DRUM FORWARD, THE MHA-VN-058 FRONT WASHER."
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
        "LIGHT-PRESS THE MHA-MG-001 BRACKET'S COLLAR ONTO THE PRESS-ZONE END OF "
        "THE MHA-MG-003 LEVER, LEVER END FLUSH WITH THE COLLAR'S OUTER FACE. "
        "THE TWO MHA-VN-050 SCREWS GO WITH THE LEVER: MHA-HA-000 DRIVES THEM "
        "INTO THE SUMMING LEVER."
    ),
    _steps.CLAMP_SET_KEY: (
        "SLIDE THE MHA-MG-002 CLAMP ONTO THE LEVER FROM ITS FREE END, SCREW "
        "HOLE UP, TO THE CLAMP STATION (SHEET 1); TIGHTEN ITS MHA-VN-011 THUMB "
        "SCREW BY HAND."
    ),
    _steps.FIXTURE_SET_KEY: (
        "PASS THE MHA-MG-004 ROD UP THROUGH THE MHA-MG-006 FIXTURE INTO THE "
        "CLAMP'S ROD BORE. SET THE FIXTURE AT THE FIXTURE DROP (SHEET 1), "
        "SPIGOT TOWARD THE BRACKET; TIGHTEN ITS MHA-VN-011 THUMB SCREW BY HAND."
    ),
    _steps.WIRE_HOOKED_KEY: (
        "AFTER MHA-HA-000 HAS CLAMPED THE BAR AND SCREWED THE BRACKET TO THE "
        "SUMMING LEVER: HOOK THE MHA-VN-066 LEVER WIRE IN THE FIXTURE'S SPIGOT "
        "GROOVE, LEAVING THE GROOVE AT ITS FRONT."
    ),
    _steps.WIRE_TIED_KEY: (
        "LEAD THE WIRE DOWN TO THE DRUM'S RIGHT SIDE, SEEN FROM THE FRONT; WRAP "
        "IT CLOCKWISE DOWN THE DRUM TO TIE 1, THE AXIAL HOLE AT 6 O'CLOCK IN "
        "THE WHEEL BOSS; PASS IT THROUGH WITH THE WIRE TAUT AND TWIST THE TAIL "
        "BACK ON ITSELF, AT LEAST THREE TURNS."
    ),
}
if tuple(STEP_TEXT) != _steps.SEQUENCE:
    raise AssertionError("STEP_TEXT must follow mg_magnifier_assembly_steps.SEQUENCE")
ASSEMBLY_STEPS = tuple(
    f"{_steps.step_number(key)}. {text}" for key, text in STEP_TEXT.items()
)
ASSEMBLY_CHECKS = (
    "CHECK: WITH BOTH NUTS SET THE WHEEL TURNS FREE WITHOUT RATTLE.",
    "CHECK: THE CLAMP AND THE FIXTURE HOLD THEIR SETTINGS WHEN THE LEVER IS "
    "ROCKED BY HAND.",
    "CHECK: THE LEVER WIRE CLEARS THE WHEEL RIM, SPOKES AND BOSS.",
)
