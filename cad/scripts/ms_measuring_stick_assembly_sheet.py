"""MHA-MS-00 fitter-drawing data: the BOM, the captions and the assembly text.

The fit-up steps and checks print in the release's ASSEMBLY.md
(ha_assembly_package, #2889), not on the sheets.

Drawing-only: nothing here reaches ms-measuring-stick.SLDASM, so no assembly
builder imports this module (``test_assembly_sheet_isolation`` pins it) and a
wording edit rebuilds the drawing alone. Printed dimensions interpolate a
symbol of ``ms_measuring_stick_assembly_spec`` or a part/vendor spec; mate
drawing numbers come from the part registry.

Owner ruling 2026-11-06 (option C): the stop has no as-shipped setting; it
clamps anywhere along the stick. The saved pose (STOP_MARK on the thumbscrew
axis) and its sheet-1 near-face reference only show an example position, and
the sheet-1 note says so. Printed lengths are in the assembly contract's
``drawing_unit``.

Issue #2434 (delegated ruling 2026-11-17, no precedent, option 2, for the
owner's review on #2144; issue comment 6970972423): the stick sets a bar
Michelson's way, as drawn. Steps 11-13A and sheet 4 show it: the stop's end
face nearer the 10 end on the MHA-CH-06 rocker arm's outer tip land, the
stick graduations up along the arm's top edge, the MHA-CH-01 bar slid out to
the 10 end. Zero is the stop on the 0.2 tick (``ms_stick_registration``).
"""

from __future__ import annotations

from fractions import Fraction

import _config
import ms_measuring_stick_assembly_spec as spec
import ms_stick_registration as registration
import ms_stop_spec as stop
import _mcmaster_90114a124 as plate_screw
import sh_vn_thumb_screw_spec as thumb
from _assembly_contract import assembly_contract

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


def _inch_fraction(length_mm: float) -> str:
    """A vendor's nominal inch length (``1/4``, ``7/16``) from its modeled mm."""
    inches = Fraction(length_mm / 25.4).limit_denominator(64)
    if abs(float(inches) * 25.4 - length_mm) > 1e-9:
        raise ValueError(f"{length_mm} mm is not a whole sixty-fourth of an inch")
    return str(inches)


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

EXPLODED_CAPTION = "EXPLODED VIEW - FIT-UP STEPS IN ASSEMBLY.MD"
DRAWING_DIMENSIONS = {spec.SETTING_FEATURE: {spec.SETTING_DIMENSION}}
# Components own material and finish; no assembly coating operation is required.
# The fitter's order, one action a step; the explode
# (ms_measuring_stick_explode_spec) runs steps 7-10 backwards. The block and
# its cover arrive a match-drilled pair from their part travelers (the
# MHA-MS-03 plate is pilot-drilled on its finished MHA-MS-02 block, ends and
# edges flush, then opened; the block is tapped on its return): neither is
# interchangeable. Steps 1-6 receive the pair and prove it is one.
_BLOCK, _PLATE, _STICK = _item(spec.BLOCK), _item(spec.PLATE), _item(spec.STICK)
_THUMB, _SCREWS = _item(spec.THUMB_SCREW), _item(spec.PLATE_SCREW)
STOP_FACE_FEELER = ".002"
ASSEMBLY_STEPS = (
    f"1. {_BLOCK} AND {_PLATE} ARRIVE AS A MATCHED PAIR, MATCH-DRILLED "
    f"PER {BLOCK_DRAWING_NUMBER} AND {PLATE_DRAWING_NUMBER}, A PAIR MARK "
    "ACROSS THEIR LOCATING ENDS.",
    f"2. LAY {_PLATE} ON {_BLOCK}, PAIR MARKS TOGETHER, LEFT ENDS AND TOP "
    "EDGES FLUSH AS IN THE SHEET 1 FRONT VIEW (TOP OF "
    f"{_ref(spec.BLOCK)}: ITS {thumb.THREAD} TAPPED FACE). THESE ARE THE "
    f"{stop.LOCATING_END_NOTE} AND {stop.LOCATING_EDGE_NOTE} ON "
    f"{BLOCK_DRAWING_NUMBER} AND {PLATE_DRAWING_NUMBER}.",
    f"3. CHECK: EACH {plate_screw.THREAD} TAPPED HOLE IN {_ref(spec.BLOCK)} "
    f"SHOWS CENTRED IN ITS HOLE IN {_ref(spec.PLATE)}.",
    f"4. IF ONE DOES NOT, {_ref(spec.PLATE)} IS NOT THIS {_ref(spec.BLOCK)}'S: "
    "FIND ITS OWN BY THE PAIR MARKS, THEN REPEAT 2.",
    f"5. LIFT {_PLATE} OFF {_ref(spec.BLOCK)}.",
    f"6. BLOW THE CHIPS OUT OF BOTH TAPPED HOLES IN {_ref(spec.BLOCK)}.",
    f"7. START THE {_THUMB} INTO THE TAPPED HOLE IN THE TOP OF {_BLOCK}; "
    "KEEP ITS TIP CLEAR OF THE WINDOW.",
    f"8. WITH {_ref(spec.THUMB_SCREW)} ON TOP, LAY {_STICK} IN THE OPEN "
    f"WINDOW OF {_ref(spec.BLOCK)}, GRADUATED FACE DOWN.",
    f"9. FIT {_PLATE} OVER THE WINDOW, PAIR MARKS TOGETHER.",
    f"9A. DRIVE BOTH {_SCREWS} UNTIL THEIR HEADS SEAT.",
    f"10. WITH {_ref(spec.BLOCK)} AT ANY POSITION ALONG {_ref(spec.STICK)}, "
    f"TURN THE {_THUMB} IN BY HAND UNTIL ITS TIP CLAMPS THE TOP FACE OF "
    f"{_ref(spec.STICK)}.",
    # #2434: the stop's end face nearer the 10 both reads the stick and bears
    # on the rocker arm's tip land 8.94 mm below the reading edge, so it is
    # fitted square at assembly, not toleranced on MHA-MS-02 (delegated ruling
    # 2026-11-18, owner precedents #2365 and #2416, fit at assembly;
    # drawing-simplicity rule 5; #2144). error_budget's stop_face_square books
    # the checked .002. The square stands on the stick's top face (the one
    # item 4 clamps) so its blade spans the floor side of that end face, the
    # side that bears on the land; the roof side is about 1.3 mm of flat
    # (Codjiflo r2 on PR #3099).
    f"10A. CHECK: WITH A MACHINIST'S SQUARE ON THE TOP FACE OF "
    f"{_ref(spec.STICK)}, A {STOP_FACE_FEELER} FEELER DOES NOT ENTER ALONG THE "
    f"END FACE OF {_ref(spec.BLOCK)} NEARER THE 10 (SHEET 1).",
    f"10B. IF IT ENTERS, STONE THAT END FACE OF {_ref(spec.BLOCK)} SQUARE, THEN "
    "REPEAT 10A.",
)
# Step 10A's acceptance, printed at that end face on sheet 1 (rule 22). Short
# lines end left of the (8.0) reference's right extension line (rule 14;
# machinist review run 20261118T102641481Z-bfd27b57).
STOP_FACE_NOTE = (
    f"{STOP_FACE_FEELER} FEELER DOES NOT ENTER\n"
    "UNDER A SQUARE ON THE\n"
    f"TOP FACE OF {_ref(spec.STICK)}\n"
    "(ASSEMBLY.MD STEP 10A)"
)
# At MHA-HA-00: setting a bar (#2434). The stop is turned over from the
# fitted pose (item 4 below, the graduated face up), its end face nearer the
# stick's 10 end both reads the stick and bears on the rocker arm's tip.
# One action a step (rule 22). Past about 36 mm the stick and stop
# overbalance outboard about the land (stick and stop brass, the stop hanging
# outboard of the tip), so step 12C holds the 10 end down while the bar comes
# out (Codjiflo r1 on PR #3099).
_ROCKER_ARM = str(_config.parts("ch-rocker-arm")["number"])
_AMPLITUDE_BAR = str(_config.parts("ch-amplitude-bar")["number"])
IN_USE_SHEET = 4
# The in-use view looks the way the front view does, turned over: VIEW B,
# named by a viewing arrow on the sheet-1 bottom view and labelled rotated
# (rules 9 and 26; machinist review run 20261118T085338138Z-6449eada).
IN_USE_VIEW_LETTER = "B"
IN_USE_VIEW_LABEL = f"VIEW {IN_USE_VIEW_LETTER}\nROTATED 180°"
_IN_USE_VIEW = f"VIEW {IN_USE_VIEW_LETTER}, SHEET {IN_USE_SHEET}"
ZERO_TICK_TEXT = registration.ZERO_TICK_TEXT
_TEN_END_FACE = f"END FACE OF {_ref(spec.STICK)} NEAREST ITS 10"
USE_STEPS = (
    f"11. TO SET AN {_AMPLITUDE_BAR} AMPLITUDE BAR, HOLD THE STOP WITH "
    f"{_ref(spec.THUMB_SCREW)} BELOW AND THE GRADUATIONS OF {_ref(spec.STICK)} "
    f"UP ({_IN_USE_VIEW}).",
    f"11A. SLACKEN {_ref(spec.THUMB_SCREW)}.",
    f"11B. SLIDE {_BLOCK} UNTIL ITS END FACE NEARER THE 10 OF {_ref(spec.STICK)} "
    "STANDS ON THE GRADUATION READOUT.MD STEP 1 GIVES FOR THE BAR'S STATION "
    f"(FOR A BAR AT ZERO, GRADUATION {ZERO_TICK_TEXT}).",
    f"11C. TIGHTEN {_ref(spec.THUMB_SCREW)} BY HAND.",
    "12. TURN THE MHA-HA-00 CRANK UNTIL THE OUTER TIPS OF ALL 20 "
    f"{_ROCKER_ARM} ROCKER ARMS (THE ENDS AWAY FROM THE CONNECTING RODS) "
    "LINE UP.",
    f"12A. LAY {_STICK} ON THE TOP EDGE OF THAT BAR'S {_ROCKER_ARM} ROCKER "
    "ARM, ITS 10 TOWARD THE PIVOT.",
    f"12B. SLIDE {_ref(spec.STICK)} OUT UNTIL THE END FACE OF "
    f"{_ref(spec.BLOCK)} BEARS ON THE ARM'S OUTER TIP ({_IN_USE_VIEW}).",
    f"12C. HOLD THE 10 END OF {_ref(spec.STICK)} DOWN ON THE ARM'S TOP EDGE.",
    f"13. SLIDE THE {_AMPLITUDE_BAR} BAR OUT UNTIL ITS OUTBOARD FACE TOUCHES "
    f"THE {_TEN_END_FACE} ({_IN_USE_VIEW}).",
    f"13A. LIFT {_ref(spec.STICK)} OFF WITHOUT MOVING THE BAR.",
)
STEP_SECTIONS = (
    ("ASSEMBLY SEQUENCE", ASSEMBLY_STEPS),
    ("IN USE AT MHA-HA-00: SETTING AN AMPLITUDE BAR", USE_STEPS),
)
ASSEMBLY_CHECKS = (
    f"CHECK: WITH {_ref(spec.THUMB_SCREW)} BACKED OFF, {_STICK} SLIDES FREELY "
    "IN THE WINDOW.",
    f"CHECK: WITH {_ref(spec.THUMB_SCREW)} TIGHT, {_BLOCK} DOES NOT MOVE ALONG "
    f"{_ref(spec.STICK)}.",
    f"CHECK: BOTH {_ref(spec.PLATE_SCREW)} HEADS SEAT ON {_PLATE}.",
    f"CHECK: {_ref(spec.PLATE)} LIES FLAT ON {_ref(spec.BLOCK)}.",
)
# Sheet 1: the pose drawn (and its near-face reference) is one example.
EXAMPLE_POSE_NOTE = (
    f"STOP SHOWN CLAMPED AT AN EXAMPLE POSITION. {_ref(spec.BLOCK)} CLAMPS "
    f"AT ANY POSITION ALONG {_ref(spec.STICK)} (ASSEMBLY.MD STEP 10)."
)
# Sheet 4: VIEW B, the stop turned over and laid on a rocker arm (steps
# 11-13A), the arm and the bar in phantom. The drawn stop is the sheet-1
# example pose, so the arm and bar stand where that reading puts them. The
# caption carries only what the view cannot show.
IN_USE_CAPTION = (
    "IN USE AT MHA-HA-00 (ASSEMBLY.MD STEPS 11-13A). ROCKER ARM AND AMPLITUDE "
    "BAR IN PHANTOM. STOP SHOWN AT AN EXAMPLE READING; FOR A BAR AT ZERO THE "
    f"STOP STANDS ON GRADUATION {ZERO_TICK_TEXT}."
)
IN_USE_LABELS = {
    "rocker": f"{_ROCKER_ARM} ROCKER ARM TOP EDGE",
    "tip": f"{_ref(spec.BLOCK)} END FACE ON THE ARM'S OUTER TIP LAND",
    "reading": f"READ {_ref(spec.STICK)} AT THIS END FACE",
    "ten_end": f"{_ref(spec.STICK)} END FACE ON THE BAR'S OUTBOARD FACE",
    "bar": f"{_AMPLITUDE_BAR} AMPLITUDE BAR",
    "pivot": "ROCKER PIVOT AXIS",
}

# Both dimensions are reference: the assembly pose, not component sizes.
REFERENCE_OVERALL_LENGTH = spec.STICK_X_MAX - spec.STICK_X_MIN
DRAWING_REFERENCE_PRECISION = 1

assert sorted(spec.QUANTITIES) == sorted(BOM_ORDER) == sorted(ITEM_NUMBERS)
assert sorted(ITEM_NUMBERS.values()) == list(range(1, len(BOM_ORDER) + 1))
