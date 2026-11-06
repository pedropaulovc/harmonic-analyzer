"""MHA-MS-00 fitter-drawing data: the BOM, the captions and the assembly text.

Drawing-only: nothing here reaches ms-measuring-stick.SLDASM, so no assembly
builder imports this module (``test_assembly_sheet_isolation`` pins it) and a
wording edit rebuilds the drawing alone. Printed dimensions interpolate a
symbol of ``ms_measuring_stick_assembly_spec`` or a part/vendor spec; mate
drawing numbers come from the part registry.

The near-face setting is a native reference dimension of the saved clamped
pose, not an acceptance band; the setting step prints its value and names the
features it runs between, and the stick graduation it puts on the thumbscrew
axis. Printed lengths are in the assembly contract's ``drawing_unit``.
"""

from __future__ import annotations

from fractions import Fraction

import _config
import ms_measuring_stick_assembly_spec as spec
import ms_stop_spec as stop
import _mcmaster_90114a124 as plate_screw
import sh_vn_thumb_screw_spec as thumb
from _assembly_contract import assembly_contract
from _title_block_units import LENGTH_UNITS, render_number

DRAWING_NUMBER = "MHA-MS-00"
PLATE_DRAWING_NUMBER = str(_config.parts("ms-stop-plate")["number"])
BLOCK_DRAWING_NUMBER = str(_config.parts("ms-stop-block")["number"])
# A literal stem: the build graph narrows this drawing's assemblies/*
# dependency to exactly the contracts its closure names.
UNIT = assembly_contract("ms-measuring-stick").drawing_unit

BOM_ORDER = (spec.STICK, spec.BLOCK, spec.PLATE, spec.PLATE_SCREW, spec.THUMB_SCREW)
# The native BOM numbers the families in the builder's insertion order (block,
# plate, stick, thumbscrew, plate screws); the steps cite these numbers and the
# recipe refuses a BOM that numbers otherwise (rule 22: steps name item numbers).
ITEM_NUMBERS = {
    spec.BLOCK: 1,
    spec.PLATE: 2,
    spec.STICK: 3,
    spec.THUMB_SCREW: 4,
    spec.PLATE_SCREW: 5,
}
# The short noun each step prints after the item number.
_ITEM_NOUNS = {
    spec.BLOCK: "BLOCK",
    spec.PLATE: "PLATE",
    spec.STICK: "STICK",
    spec.THUMB_SCREW: "THUMBSCREW",
    spec.PLATE_SCREW: "FILLISTER SCREWS",
}


def _ref(stem: str) -> str:
    """``stem``'s bare item reference, ``ITEM 2``."""
    return f"ITEM {ITEM_NUMBERS[stem]}"


def _item(stem: str) -> str:
    """``stem`` named with its item number, ``ITEM 2 PLATE``."""
    return f"{_ref(stem)} {_ITEM_NOUNS[stem]}"


def _setting() -> str:
    """The near-face reference as the front view rounds and prints it,
    ``(2.923)``; a reference carries no band, so rounding is the display's."""
    inches = spec.SETTING_NEAR_FACE_MM / LENGTH_UNITS[UNIT]
    value = render_number(round(inches, spec.SETTING_PRECISION), UNIT, spec.SETTING_PRECISION)
    return f"({value})"


def _inch_fraction(length_mm: float) -> str:
    """A vendor's nominal inch length (``1/4``, ``7/16``) from its modeled mm."""
    inches = Fraction(length_mm / 25.4).limit_denominator(64)
    if abs(float(inches) * 25.4 - length_mm) > 1e-9:
        raise ValueError(f"{length_mm} mm is not a whole sixty-fourth of an inch")
    return str(inches)


def _hole(length_mm: float) -> str:
    """A stop hole length as the stop sheets' hole callouts print it."""
    return render_number(
        length_mm / LENGTH_UNITS[UNIT], UNIT, stop.HOLE_CALLOUT_PRECISION
    )


# BOM DESCRIPTION cells (the parts carry no Description property).
BOM_DESCRIPTIONS = {
    spec.STICK: "GRADUATED STICK",
    spec.BLOCK: "STOP BLOCK",
    spec.PLATE: "STOP COVER PLATE",
    spec.PLATE_SCREW: (
        f"{plate_screw.THREAD} X {_inch_fraction(plate_screw.LENGTH)} "
        "BRASS FILLISTER SCREW"
    ),
    spec.THUMB_SCREW: (
        f"{thumb.THREAD} X {_inch_fraction(thumb.SHANK_LEN)} KNURLED THUMBSCREW"
    ),
}

EXPLODED_CAPTION = "EXPLODED VIEW - ASSEMBLY SEQUENCE ON SHEET 3"
DRAWING_DIMENSIONS = {spec.SETTING_FEATURE: {spec.SETTING_DIMENSION}}
# Components own material and finish; no assembly coating operation is required.
# The fitter's order, one action a step; the explode
# (ms_measuring_stick_explode_spec) runs steps 7-11 backwards. The block and
# its cover are a match-drilled pair (steps 1-6): neither is interchangeable.
# The block's own tapped-hole callout states the drill and full-thread depths;
# steps 3 and 5 point to it instead of restating them.
_BLOCK, _PLATE, _STICK = _item(spec.BLOCK), _item(spec.PLATE), _item(spec.STICK)
_THUMB, _SCREWS = _item(spec.THUMB_SCREW), _item(spec.PLATE_SCREW)
ASSEMBLY_STEPS = (
    f"1. LAY OUT THE TWO HOLES OF {_PLATE} PER {PLATE_DRAWING_NUMBER}; "
    "DO NOT DRILL THEM YET.",
    f"2. CLAMP {_PLATE} TO {_BLOCK} WITH THEIR "
    f"{stop.MATCH_DRILL_DATUM_ALIGNMENT}.",
    f"3. AT EACH LAID-OUT HOLE, DRILL Ø{_hole(stop.PLATE_TAP_DRILL_DIA)} "
    f"THROUGH {_PLATE} AND INTO {_BLOCK} TO THE {BLOCK_DRAWING_NUMBER} TAP "
    f"DRILL DEPTH, MEASURED FROM THE {_ref(spec.BLOCK)} FACE UNDER "
    f"{_ref(spec.PLATE)}.",
    f"4. WITH {_PLATE} OFF {_ref(spec.BLOCK)}, OPEN ITS TWO HOLES TO "
    f"Ø{_hole(stop.PLATE_CLEARANCE_DIA)} THRU.",
    f"5. TAP BOTH HOLES IN {_BLOCK} {plate_screw.THREAD} WITH A BOTTOMING TAP "
    f"TO THE {BLOCK_DRAWING_NUMBER} FULL THREAD DEPTH.",
    f"6. MARK {_BLOCK} AND {_PLATE} AS A MATCHED PAIR.",
    f"7. START THE {_THUMB} INTO THE TAPPED HOLE IN THE TOP OF {_BLOCK}; "
    "KEEP ITS TIP CLEAR OF THE WINDOW.",
    f"8. WITH {_ref(spec.THUMB_SCREW)} ON TOP, LAY {_STICK} IN THE OPEN "
    f"WINDOW OF {_ref(spec.BLOCK)}, GRADUATED FACE DOWN.",
    f"9. FIT {_PLATE} OVER THE WINDOW, PAIR MARKS TOGETHER; DRIVE BOTH "
    f"{_SCREWS} UNTIL THEIR HEADS SEAT.",
    f"10. SLIDE {_ref(spec.BLOCK)} ALONG {_ref(spec.STICK)} UNTIL THE LEFT END "
    f"OF {_ref(spec.STICK)} IS {_setting()} FROM THE LEFT FACE OF "
    f"{_ref(spec.BLOCK)}, THE REF DIMENSION IN THE SHEET 1 FRONT VIEW. STICK "
    f"GRADUATION {stop.STOP_MARK:.1f} THEN LIES ON THE {_ref(spec.THUMB_SCREW)} "
    "AXIS.",
    f"11. TURN THE {_THUMB} IN BY HAND UNTIL ITS TIP CLAMPS THE TOP FACE OF "
    f"{_ref(spec.STICK)}.",
)
ASSEMBLY_CHECKS = (
    f"CHECK: WITH {_ref(spec.THUMB_SCREW)} BACKED OFF, {_STICK} SLIDES FREELY "
    "IN THE WINDOW.",
    f"CHECK: WITH {_ref(spec.THUMB_SCREW)} TIGHT, {_BLOCK} DOES NOT MOVE ALONG "
    f"{_ref(spec.STICK)}.",
    f"CHECK: BOTH {_ref(spec.PLATE_SCREW)} HEADS SEAT ON {_PLATE}, AND "
    f"{_ref(spec.PLATE)} LIES FLAT ON {_ref(spec.BLOCK)}.",
)

# Both dimensions are reference: the assembly pose, not component sizes.
REFERENCE_OVERALL_LENGTH = spec.STICK_X_MAX - spec.STICK_X_MIN
DRAWING_REFERENCE_PRECISION = 1

assert sorted(spec.QUANTITIES) == sorted(BOM_ORDER) == sorted(ITEM_NUMBERS)
assert sorted(ITEM_NUMBERS.values()) == list(range(1, len(BOM_ORDER) + 1))
