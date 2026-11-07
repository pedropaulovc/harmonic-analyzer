"""Drawing-only text of the complete-machine fitter package (MHA-HA-00).

The BOM descriptions, balloon targets, setting callouts, integration steps
and checks the sheets print. Only draw_ha_harmonic_analyzer_assembly (and its
tests) import this module; no assembly builder may
(``test_assembly_sheet_isolation`` pins it), so a wording edit here does not
rebuild the complete-machine assembly. No SolidWorks.
"""

from __future__ import annotations

import _config
import dt_drive_train_steps
import ha_harmonic_analyzer_assembly_steps as steps
import pd_paper_drive_assembly_steps as pd_steps
import pd_transgear_removable_spec as removable
import _sprocket_seat_geometry as seat_geometry
import ch_anchor_jam_nut_spec
import ch_vn_spring_hook_spec
from ha_harmonic_analyzer_assembly_spec import (
    BAR_HEIGHT_DIMENSION,
    BOM_ORDER,
    MEASURING_STICK,
    STUD_DROP_DIMENSION,
)
from _printed_tolerance import angular_band_deg
from _recording_geometry import PEN_PAPER_CLEARANCE_MM
from _title_block_units import render_number

DRAWING_NUMBER = steps.DRAWING_NUMBER

BOM_DESCRIPTIONS: dict[str, str] = {
    "fr-frame": "FRAME: BASE, COLUMNS AND TOP FRAME",
    "dt-drive-train": "DRIVE TRAIN: CONES, CRANK AND CYLINDERS",
    "ch-channel": "CHANNEL BANK: RODS, ROCKERS, LEVERS, SPRINGS",
    "sm-summing": "SUMMING LEVER, KNIFE MOUNTS AND GOOSENECK",
    "mg-magnifier": "MAGNIFIER: WHEEL BAR, WHEEL AND BRACKET",
    "pn-pen": "PEN CARRIAGE AND HANGER",
    "pd-paper-drive": "PAPER DRIVE: PLATEN, SUPPORT BAR, TRANSGEAR",
    MEASURING_STICK: "MEASURING STICK WITH CLAMPED STOP",
}
if set(BOM_DESCRIPTIONS) != set(BOM_ORDER):
    raise AssertionError("every BOM row needs exactly one description")

# Each row's balloon lands on one leaf part of its subassembly that the
# exploded isometric shows: the top-level BOM resolves a nested part's
# balloon to its subassembly's row. Every stem lives in exactly one
# subassembly, so the balloon names one row. The channel row lands on the
# front channel's lever (ch-channel-lever-1, nearest the viewer): the
# fulcrum shaft that first held it is buried in the lever hubs (r2 leaf: no
# visible edge).
BALLOON_PARTS: dict[str, str] = {
    # The base, nearest the viewer: the top frame's leader crossed the frame.
    "fr-frame": "fr-harmonic-base",
    "dt-drive-train": "dt-crank-handle",
    "ch-channel": "ch-channel-lever",
    "sm-summing": "sm-summing-lever",
    "mg-magnifier": "mg-magnifying-wheel",
    "pn-pen": "pn-pen-hanger",
    "pd-paper-drive": "pd-platen",
    MEASURING_STICK: "ms-stick",
}
if set(BALLOON_PARTS) != set(BOM_ORDER) or len(set(BALLOON_PARTS.values())) != len(
    BALLOON_PARTS
):
    raise AssertionError("one distinct balloon part per BOM row")

# MHA-PD-00 stores its spare chain wheel flat and loose on the base deck,
# its own sheet 1 says so; at this level it lies beside item 7's group on
# sheet 3 and on the deck on sheet 2. Machinist review of 5bca52e13 (r1, r2)
# could not tell which row supplies it or where it stays: sheet 3 labels it
# and the paper-drive step names its supplier and its place. The spare is the
# one removable configuration neither wheel mounts, read the way the drawing
# finds it in the source (never an allocator-numbered instance).
PAPER_DRIVE = "pd-paper-drive"
SPARE_SPROCKET_STEM = "pd-transgear-removable"
(SPARE_SPROCKET_CONFIG,) = tuple(
    name
    for name, _teeth in removable.CONFIGS
    if name not in {removable.CRANK_CONFIG, removable.KNOB_CONFIG}
)
# Literal row name: a dynamic _config.parts read would widen this drawing's
# config dependency to every part row (test_dodo_recipe foreign-row guard).
SPARE_SPROCKET_NUMBER = str(_config.parts("pd-transgear-removable")["number"])
PAPER_DRIVE_ITEM = str(BOM_ORDER.index(PAPER_DRIVE) + 1)
# The label's leader tip: a point on the spare's upper plate face, part
# millimetres (plate local z 0..PLATE), on the local x axis between the
# drive-pin circle (pins on local y) and the tooth roots.
SPARE_SPROCKET_TIP_MM = (12.0, 0.0, seat_geometry.PLATE)
if not (
    seat_geometry.PIN_CIRCLE_RADIUS + seat_geometry.PIN_HOLE_DIA
    < SPARE_SPROCKET_TIP_MM[0]
    < removable.bottom_dia(removable.TEETH[SPARE_SPROCKET_CONFIG]) / 2.0 - 1.0
):
    raise AssertionError("the spare label's tip must land on the solid plate face")

# The parked nib's feeler, in the sheet's decimal inch (#290): the modelled
# 0.25 gap prints as the stock .010 leaf (0.254), three places as a feeler
# size reads; the next step closes the gap, so the 0.004 is immaterial.
NIB_CLEARANCE_PLACES = 3
NIB_CLEARANCE_TEXT = render_number(
    round(PEN_PAPER_CLEARANCE_MM / 25.4, NIB_CLEARANCE_PLACES), "in", NIB_CLEARANCE_PLACES
)
# Each setting's printed callout names what it sets and the step that sets
# it; the step text points back to the sheet-1 dimension, so the value lives
# only on the associative model dimension.
# Both callouts stay short: the bar-height text stands wholly left of the
# front view, the stud-drop text in the narrow strip between the right-hand
# column and the crank-side view, so it names only its step (the extension
# lines show it runs from the bar top to the stud head). The bar height runs
# from the raised deck top (ha_harmonic_analyzer_assembly_spec.DECK_TOP_Y),
# whose extension line ends at the left column short of that deck, so its
# callout and step name the surface (#2060), in short lines.
SETTING_CALLOUTS = {
    BAR_HEIGHT_DIMENSION: (
        "BAR TOP ABOVE\nRAISED DECK TOP\n"
        f"(STEP {steps.step_number('magnifier-bar-clamped')})"
    ),
    STUD_DROP_DIMENSION: f"STEP {steps.step_number('pen-wire-tied')}",
}

# --- Fitter package text ----------------------------------------------------
CHANNEL_ANCHORS = 20
# Rule 22: a step does one thing. A keyed step that needs several actions
# prints them as lettered sub-steps (5A, 5B, ...) under its own number, so the
# numbers other sheets cite (MHA-CH-00 cites the anchor step) never move. I
# and O never letter a sub-step.
SUB_STEP_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ"
# The title block's angular row is the level acceptance, read with the digital
# angle gauge the shop owns (as MHA-SM-00 sets its plate).
LEVEL_TOLERANCE_DEG = angular_band_deg()
LEVEL_ACCEPTANCE = f"LEVEL WITHIN \u00b1{LEVEL_TOLERANCE_DEG:g}\u00b0"
_AMPLITUDE_BAR = str(_config.parts("ch-amplitude-bar")["number"])
_ANCHOR = str(_config.parts("ch-vn-spring-hook")["number"])
_ANCHOR_NUT = str(_config.parts("ch-anchor-jam-nut")["number"])
_SUMMING_PLATE = str(_config.parts("sm-summing-lever")["number"])

# The forked driver that runs each round, slotted MHA-CH-14 jam nut up its
# anchor (ch_anchor_jam_nut_spec: one straight slot across the lower face, the
# anchor's shank through the nut's centre). A screwdriver blade, its tines in
# the nut's slot either side of the shank: thinner than the slot, no wider
# than the nut, its centre slot clearing the shank's major diameter and
# deeper than the shank stands below the plate. Sizes in the sheet's inch,
# at the .XX/.XXX grades a tool sketch needs.
DRIVER_BLADE_WIDTH = 0.25
DRIVER_BLADE_THICK_MAX = 0.045
DRIVER_SLOT_WIDTH = 0.16
DRIVER_SLOT_DEPTH = 0.40
if not (
    DRIVER_BLADE_THICK_MAX < ch_anchor_jam_nut_spec.SLOT_WIDTH / 25.4
    and DRIVER_BLADE_WIDTH <= ch_anchor_jam_nut_spec.OD_MIN / 25.4
    and ch_anchor_jam_nut_spec.THREAD_MAJOR / 25.4 + 0.01 < DRIVER_SLOT_WIDTH
    and DRIVER_SLOT_DEPTH > ch_vn_spring_hook_spec.PROTRUSION_MAX_MM / 25.4
    and (DRIVER_BLADE_WIDTH - DRIVER_SLOT_WIDTH) / 2.0 >= 0.04
):
    raise AssertionError("the forked driver must fit the jam nut's slot round the shank")


def _n(key: str) -> int:
    return steps.step_number(key)


def sub_step(key: str, index: int) -> str:
    """The printed head of ``key``'s ``index``-th sub-step (0-based): ``5A``."""
    if len(_STEP_TEXT[key]) == 1:
        raise ValueError(f"{key} prints as one step, not sub-steps")
    return f"{_n(key)}{SUB_STEP_LETTERS[index]}"


_STEP_TEXT: dict[str, tuple[str, ...]] = {
    "frame-built": (
        "FRAME: BUILD MHA-FR-00 COMPLETE ON A FLAT BENCH, ITS MHA-FR-VN-52 SET "
        "SCREW BACKED CLEAR IN THE GOOSENECK HUB.",
    ),
    "drive-train-built": (
        f"DRIVE TRAIN: BUILD {dt_drive_train_steps.DRAWING_NUMBER} ON THE BASE, "
        f"STEPS 1-{len(dt_drive_train_steps.SEQUENCE)} IN ORDER.",
    ),
    "summing-hung": (
        "SUMMING LEVER: BUILD MHA-SM-00 UNDER THE TOP-FRAME CROSSBAR, ITS STEPS "
        "BEFORE FINAL ASSEMBLY IN ORDER, THE MHA-SM-01 POST OUT OF ITS HUB.",
    ),
    "channel-built": (
        "CHANNEL BANK: BUILD MHA-CH-00 COMPLETE ON THE FRAME PER ITS STEPS, EACH "
        "MHA-CH-VN-50 SPRING HANGING FROM ITS LEVER WITH ITS BOTTOM LOOP FREE.",
    ),
    "channel-anchors-set": (
        f"MAKE A FORKED DRIVER FOR THE {_ANCHOR_NUT} NUTS: GRIND A FLAT "
        f"SCREWDRIVER BLADE TO {render_number(DRIVER_BLADE_WIDTH, 'in', 2)} WIDE AND "
        f"{render_number(DRIVER_BLADE_THICK_MAX, 'in', 3)} THICK MAX, THEN SLOT ITS "
        f"MIDDLE {render_number(DRIVER_SLOT_WIDTH, 'in', 2)} WIDE X "
        f"{render_number(DRIVER_SLOT_DEPTH, 'in', 2)} DEEP.",
        f"DISCARD THE HEX NUT SUPPLIED WITH EACH OF THE {CHANNEL_ANCHORS} {_ANCHOR} "
        "ANCHORS.",
        f"THREAD EACH {_ANCHOR} DOWN INTO ITS {_SUMMING_PLATE} PLATE TAP UNTIL ITS "
        "NECK SEATS ON THE PLATE TOP.",
        f"TURN EACH {_ANCHOR} BACK, NO MORE THAN "
        f"{ch_vn_spring_hook_spec.ADJUSTMENT_TURNS} TURN, TO BRING ITS EYE OPENING "
        "IN LINE WITH ITS SPRING.",
        f"HOLDING THE EYE THERE, RUN ONE {_ANCHOR_NUT} UP THE SHANK WITH THE "
        "FORKED DRIVER, TINES IN THE NUT'S SLOT, TIGHT AGAINST THE PLATE "
        "UNDERSIDE.",
        f"CHECK EACH {_ANCHOR}: ITS EYE CANNOT BE TURNED BY HAND.",
        f"CHECK EACH {_ANCHOR_NUT}: FULL THREAD SHOWS BELOW IT.",
        "IF AN EYE TURNS OR NO THREAD SHOWS, SLACKEN THAT NUT AND REPEAT "
        f"{_n('channel-anchors-set')}D-{_n('channel-anchors-set')}E.",
        "HOOK EACH SPRING'S BOTTOM LOOP INTO ITS ANCHOR EYE.",
    ),
    "summing-levelled": (
        "DROP THE MHA-SM-01 POST INTO THE TOP FRAME'S GOOSENECK HUB.",
        "HOOK THE MHA-SM-VN-51 LOWER LOOP INTO THE MHA-SM-VN-50 EYE.",
        f"SET EVERY {_AMPLITUDE_BAR} AMPLITUDE BAR TO ZERO ON THE MHA-MS-00 "
        "STICK'S SCALE.",
        "SLIDE THE POST IN ITS HUB UNTIL A DIGITAL ANGLE GAUGE ACROSS THE "
        f"MHA-SM-03 PLATE TOP READS {LEVEL_ACCEPTANCE}.",
        "TIGHTEN THE MHA-FR-VN-52 SET SCREW ON THE POST.",
        "CHECK: UNDER FIRM HAND PRESSURE THE POST DOES NOT TURN OR SLIDE IN "
        "ITS HUB.",
        "IF THE POST MOVES, SLACKEN THE SET SCREW AND REPEAT "
        f"{_n('summing-levelled')}D-{_n('summing-levelled')}E.",
    ),
    "paper-drive-built": (
        f"PAPER DRIVE: BUILD MHA-PD-00 ON THE FRONT COLUMNS, ITS STEPS "
        f"1-{len(pd_steps.SEQUENCE)} IN ORDER.",
        f"LAY THE LOOSE {SPARE_SPROCKET_NUMBER} {SPARE_SPROCKET_CONFIG} SPARE "
        "SPROCKET SUPPLIED WITH MHA-PD-00 (LABELLED ON SHEET 3) FLAT ON THE "
        "BASE DECK WHERE SHEET 2 SHOWS IT.",
    ),
    "magnifier-bar-clamped": (
        "MAGNIFIER BAR: CLOSE THE MHA-SH-01/MHA-SH-02 CLAMP ARCS SUPPLIED WITH "
        "MHA-MG-00 ROUND THE LEFT FRONT COLUMN (FRONT VIEW), WHEEL TOWARD THE "
        "PEN ROD, BOTH MHA-SH-VN-53 CLAMP SCREWS LOOSE.",
        "SET THE MHA-MG-08 BAR TOP TO ITS HEIGHT ABOVE THE RAISED DECK TOP "
        "(SHEET 1), READ WITH A RULE FROM THE DECK TOP.",
        "TURN THE BAR ON THE COLUMN UNTIL A DIGITAL ANGLE GAUGE ALONG ITS TOP "
        f"READS {LEVEL_ACCEPTANCE}.",
        "TIGHTEN BOTH CLAMP SCREWS EVENLY.",
        "CHECK: UNDER FIRM HAND PRESSURE THE BAR DOES NOT SLIP OR TURN ON THE "
        "COLUMN.",
        "IF THE BAR MOVES, SLACKEN BOTH SCREWS AND REPEAT "
        f"{_n('magnifier-bar-clamped')}B-{_n('magnifier-bar-clamped')}D.",
    ),
    "magnifier-bracket-screwed": (
        "MAGNIFIER BRACKET: SEAT THE MHA-MG-01 BRACKET FLANGE ON ITS SEATS ON "
        "MHA-SM-03.",
        "DRIVE BOTH MHA-MG-VN-53 #2-56 SCREWS UNTIL THE HEADS SEAT ON THE FLANGE.",
    ),
    "lever-wire-fitted": ("LEVER WIRE: FIT IT PER MHA-MG-00 SHEET 5.",),
    "pen-hung": (
        "PEN: HANG MHA-PN-00 FROM THE MHA-MG-08 BAR.",
        "LOCK ITS MHA-PN-VN-50 HANGER SCREW WITH THE MHA-PN-VN-54 NUT AND "
        "MHA-PN-VN-55 JAM NUT PER THE MHA-PN-00 HANGER SCREW LOCK STEP.",
    ),
    # The wrap follows mg_wheel_group (PEN_WIRE_WRAP_DEG: from the right-hand
    # tangent counter-clockwise, up over the top, to the rim's radial wire tie
    # hole drawn on the MHA-MG-05 sheet, under one turn).
    "pen-wire-tied": (
        f"PEN WIRE, WITH THE PLATE TOP LEVEL ({_n('summing-levelled')}D): LEAD "
        "THE UPPER END OF MHA-SH-VN-56 (SUPPLIED WITH MHA-PN-00) INTO THE "
        "MHA-MG-05 RIM GROOVE AT ITS RIGHT-HAND TANGENT (FRONT VIEW).",
        "WRAP THE WIRE COUNTERCLOCKWISE (FRONT VIEW) UP OVER THE TOP, UNDER ONE "
        "TURN, TO THE RADIAL WIRE TIE HOLE IN THE MHA-MG-05 RIM.",
        "PASS THE WIRE THROUGH THE HOLE AND DRAW IT UNTIL THE MHA-PN-07 STUD "
        "HEAD TOP HANGS THE SHEET 1 DROP BELOW THE MHA-MG-08 BAR TOP.",
        "TIE THE WIRE OFF INSIDE THE RIM AT THAT DROP.",
        "TRIM THE TAIL.",
    ),
    # The parked, as-modelled nib: the views show it here, a feeler's gap
    # off the paper (PEN_PAPER_CLEARANCE_MM). Nothing on the carriage brings
    # it nearer -- it hangs plumb and CG-balanced on the wire, the rod
    # guided -- so "nib-on-paper" closes the gap by sliding the marker on in
    # the V (code review C08).
    "nib-set": (
        "NIB PARKED, WITH PAPER CLIPPED ON THE PLATEN: SLACKEN THE MHA-PN-VN-51 "
        "THUMB SCREW.",
        f"SLIDE THE MHA-PN-VN-56 MARKER UNTIL A {NIB_CLEARANCE_TEXT} FEELER JUST "
        "DRAGS BETWEEN NIB AND PAPER.",
        "TIGHTEN THE THUMB SCREW FINGER-TIGHT.",
        "CHECK: PUSHED LIGHTLY ALONG ITS AXIS, THE MARKER DOES NOT SLIDE.",
    ),
    "nib-on-paper": (
        "NIB ON PAPER, BEFORE RUNNING: SLACKEN THE MHA-PN-VN-51 THUMB SCREW.",
        "PUSH THE MHA-PN-VN-56 MARKER ALONG ITS AXIS UNTIL THE NIB JUST TOUCHES "
        "THE PAPER.",
        "TIGHTEN THE THUMB SCREW FINGER-TIGHT.",
        "CHECK: PUSHED LIGHTLY ALONG ITS AXIS, THE MARKER DOES NOT SLIDE.",
    ),
    "stick-parked": (
        "MEASURING STICK: PARK MHA-MS-00 ON THE MHA-FR-01 AS-CAST TOP BETWEEN "
        "THE RIGHT EDGE OF THE RAISED DECK AND THE RIGHT-HAND COLUMNS (FRONT "
        "VIEW), AS SHEET 2 SHOWS IT: STICK FRONT TO REAR AND CENTRED, "
        "THUMBSCREW ON TOP.",
    ),
}
if set(_STEP_TEXT) != set(steps.SEQUENCE):
    raise AssertionError("every integration step needs exactly one text")
if max(map(len, _STEP_TEXT.values())) > len(SUB_STEP_LETTERS):
    raise AssertionError("a step outgrows its sub-step letters")


def _printed(key: str) -> tuple[str, ...]:
    texts = _STEP_TEXT[key]
    if len(texts) == 1:
        return (f"{_n(key)}. {texts[0]}",)
    return tuple(f"{sub_step(key, index)}. {text}" for index, text in enumerate(texts))


# Every printed step, in order, each led by its head (``7.`` or ``7B.``).
ASSEMBLY_STEPS: tuple[str, ...] = tuple(
    line for key in steps.SEQUENCE for line in _printed(key)
)


def step_lines(key: str) -> tuple[str, ...]:
    """The printed step lines of ``key``: one, or its lettered sub-steps."""
    return _printed(key)


# Sheet 5's checks before running: one acceptance each.
ASSEMBLY_CHECKS: tuple[str, ...] = (
    "1. THE MHA-MG-08 BAR TOP READS ITS SHEET 1 HEIGHT.",
    "2. THE MHA-PN-07 STUD DROP READS AS SHEET 1.",
    "3. THE NIB TOUCHES THE PAPER.",
    f"4. WITH EVERY {_AMPLITUDE_BAR} AMPLITUDE BAR AT ZERO, THE MHA-SM-03 PLATE "
    f"TOP READS {LEVEL_ACCEPTANCE}.",
    f"5. WITH EVERY {_AMPLITUDE_BAR} AMPLITUDE BAR AT ZERO, TWO CRANK TURNS DRAW "
    "A STRAIGHT LINE ALONG THE PAPER.",
    "6. THROUGH TWO CRANK TURNS NOTHING BINDS OR RUBS.",
    "7. THROUGH TWO CRANK TURNS THE CHAIN STAYS ON BOTH WHEELS.",
    "8. THROUGH TWO CRANK TURNS BOTH WIRES STAY IN THEIR GROOVES.",
)

EXPLODED_CAPTION = "EXPLODED VIEW - INTEGRATION STEPS ON SHEETS 4 AND 5"
ORIENTATION_NOTE = "FRONT VIEW: THE PAPER SIDE. THE CRANK IS AT THE RIGHT."
# The model holds the pen parked (step "nib-set"); running needs it on the
# paper (step "nib-on-paper").
NIB_PARKED_NOTE = (
    f"VIEWS SHOW THE NIB PARKED {NIB_CLEARANCE_TEXT} OFF THE PAPER (STEP "
    f"{_n('nib-set')}); STEP {_n('nib-on-paper')} SETS IT ON."
)
# Sheet 3's label on the spare, beside item 7's group (its leader ends on the
# spare's plate face).
SPARE_SPROCKET_LABEL = "\n".join(
    (
        f"{SPARE_SPROCKET_NUMBER} {SPARE_SPROCKET_CONFIG}",
        "SPARE SPROCKET",
        f"(ITEM {PAPER_DRIVE_ITEM}, STEP {_n('paper-drive-built')})",
    )
)
