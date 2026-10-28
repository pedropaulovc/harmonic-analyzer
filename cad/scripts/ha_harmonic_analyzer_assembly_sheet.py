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
import ch_vn_spring_hook_spec
from ha_harmonic_analyzer_assembly_spec import (
    BAR_HEIGHT_DIMENSION,
    BOM_ORDER,
    MEASURING_STICK,
    STUD_DROP_DIMENSION,
)
from _recording_geometry import PEN_PAPER_CLEARANCE_MM

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

NIB_CLEARANCE_TEXT = f"{PEN_PAPER_CLEARANCE_MM:.2f}"
# Each setting's printed callout names what it sets and the step that sets
# it; the step text points back to the sheet-1 dimension, so the value lives
# only on the associative model dimension.
# Both callouts stay short: the bar-height text stands wholly west of the
# front view, the stud-drop text in the narrow strip between the east column
# and the crank-side view, so it names only its step (the extension lines
# show it runs from the bar top to the stud head). The bar height runs from
# the raised deck top (ha_harmonic_analyzer_assembly_spec.DECK_TOP_Y), whose
# extension line ends at the west column short of that deck, so its callout
# and step name the surface (#2060), in short lines.
SETTING_CALLOUTS = {
    BAR_HEIGHT_DIMENSION: (
        "BAR TOP ABOVE\nRAISED DECK TOP\n"
        f"(STEP {steps.step_number('magnifier-bar-clamped')})"
    ),
    STUD_DROP_DIMENSION: f"STEP {steps.step_number('pen-wire-tied')}",
}

# --- Fitter package text ----------------------------------------------------
CHANNEL_ANCHORS = 20


def _n(key: str) -> int:
    return steps.step_number(key)


_STEP_TEXT: dict[str, str] = {
    "frame-built": (
        "FRAME: BUILD MHA-FR-00 COMPLETE ON A FLAT BENCH. MHA-FR-VN-52 STAYS "
        f"BACKED CLEAR IN THE GOOSENECK HUB UNTIL STEP {_n('summing-levelled')}."
    ),
    "drive-train-built": (
        f"DRIVE TRAIN: BUILD {dt_drive_train_steps.DRAWING_NUMBER} ON THE BASE, "
        f"STEPS 1-{len(dt_drive_train_steps.SEQUENCE)} IN ORDER."
    ),
    "summing-hung": (
        "SUMMING LEVER: HANG MHA-SM-00 UNDER THE TOP-FRAME CROSSBAR AND CLAMP "
        "THE COUNTER SPRING'S UPPER LOOP TO THE MHA-SM-01 POST, PER ITS STEPS "
        "BEFORE FINAL ASSEMBLY. THE POST STAYS OUT OF ITS HUB."
    ),
    "channel-built": (
        "CHANNEL BANK: BUILD MHA-CH-00 COMPLETE ON THE FRAME PER ITS STEPS. "
        "EACH MHA-CH-VN-50 SPRING HANGS FROM ITS LEVER WITH ITS BOTTOM LOOP FREE."
    ),
    # The anchor's install and jam-nut lock are the anchor spec's own text
    # (ch_vn_spring_hook_spec, owned with the part), printed here unforked.
    "channel-anchors-set": (
        f"CHANNEL ANCHORS ({CHANNEL_ANCHORS} OFF): DISCARD THE HEX NUT SUPPLIED "
        f"WITH EACH MHA-CH-VN-51. {ch_vn_spring_hook_spec.ANCHOR_INSTALL_STEP} "
        "HOOK THE SPRING'S BOTTOM LOOP INTO THE EYE."
    ),
    "summing-levelled": (
        "GOOSENECK AND LEVEL, PER MHA-SM-00 FINAL-ASSEMBLY STEPS: DROP THE "
        "MHA-SM-01 POST INTO THE TOP FRAME'S GOOSENECK HUB AND HOOK THE "
        "MHA-SM-VN-51 LOWER LOOP INTO THE MHA-SM-VN-50 EYE. WITH EVERY CHANNEL "
        "AMPLITUDE AT ZERO, SLIDE THE POST UNTIL THE MHA-SM-03 PLATE TOP READS "
        "LEVEL, THEN TIGHTEN MHA-FR-VN-52 ON THE POST (NO LOCK; RE-SET IF IT "
        "DRIFTS)."
    ),
    "paper-drive-built": (
        f"PAPER DRIVE: BUILD MHA-PD-00 STEPS 1-{len(pd_steps.SEQUENCE)} IN "
        f"ORDER; ITS STEP {pd_steps.step_number('bar-clamped')} SETS THE "
        "SUPPORT BAR ON THE FRONT COLUMNS. ITS CHAIN STEPS NEED THE CRANK SIDE "
        f"OF STEP {_n('drive-train-built')}. MHA-PD-00 ALSO SUPPLIES ONE LOOSE "
        f"{SPARE_SPROCKET_NUMBER} {SPARE_SPROCKET_CONFIG} SPARE SPROCKET (LABELLED "
        "ON SHEET 3): LEAVE IT LYING FLAT ON THE BASE DECK WHERE SHEET 2 SHOWS IT."
    ),
    "magnifier-bar-clamped": (
        "MAGNIFIER BAR: MHA-MG-00 SUPPLIES THE MHA-SH-01/MHA-SH-02 CLAMP ARCS "
        "AND BOTH MHA-SH-VN-53 CLAMP SCREWS. CLOSE THE LOOSE ARCS ROUND THE "
        "WEST FRONT COLUMN, WHEEL TOWARD THE PEN ROD. SET THE MHA-MG-08 BAR "
        "TOP TO ITS HEIGHT ABOVE THE RAISED DECK TOP (SHEET 1) AND LEVEL "
        "ALONG ITS LENGTH, THEN TIGHTEN BOTH SCREWS EVENLY."
    ),
    "magnifier-bracket-screwed": (
        "MAGNIFIER BRACKET: SEAT THE MHA-MG-01 BRACKET FLANGE ON ITS SEATS ON "
        "MHA-SM-03 AND DRIVE BOTH MHA-MG-VN-53 #2-56 SCREWS UNTIL THE HEADS SEAT "
        "ON THE FLANGE."
    ),
    "lever-wire-fitted": "LEVER WIRE: PER MHA-MG-00 SHEET 5.",
    "pen-hung": (
        "PEN: HANG MHA-PN-00 FROM THE MHA-MG-08 BAR AND LOCK THE HANGER SCREW "
        "PER ITS HANGER SCREW LOCK STEP (MHA-PN-VN-50, MHA-PN-VN-54 NUT, "
        "MHA-PN-VN-55 JAM NUT)."
    ),
    # The wrap follows mg_wheel_group (PEN_WIRE_WRAP_DEG: from the 3 o'clock
    # tangent counter-clockwise, up over the top, to TIE 2 at about 4:30, under
    # one turn); TIE 2 is the radial hole drawn on the MHA-MG-05 sheet.
    "pen-wire-tied": (
        f"PEN WIRE, WITH THE PLATE TOP LEVEL (STEP {_n('summing-levelled')}): "
        "LEAD THE UPPER END OF MHA-SH-VN-56 (SUPPLIED WITH MHA-PN-00) INTO THE "
        "MHA-MG-05 RIM GROOVE AT THE 3 O'CLOCK TANGENT (FRONT VIEW), WRAP IT "
        "COUNTER-CLOCKWISE UP OVER "
        "THE TOP (UNDER ONE TURN) TO THE TIE 2 HOLE SHOWN ON THE MHA-MG-05 "
        "DRAWING, PASS IT THROUGH AND TIE IT OFF INSIDE THE RIM, SET SO THE "
        "MHA-PN-07 STUD HEAD TOP HANGS THE SHEET 1 STEP "
        f"{_n('pen-wire-tied')} DROP BELOW THE MHA-MG-08 BAR TOP. TRIM THE TAIL."
    ),
    # The parked, as-modelled nib: the views show it here, a feeler's gap
    # off the paper (PEN_PAPER_CLEARANCE_MM). Nothing on the carriage brings
    # it nearer -- it hangs plumb and CG-balanced on the wire, the rod
    # guided -- so "nib-on-paper" closes the gap by sliding the marker on in
    # the V (code review C08).
    "nib-set": (
        "NIB PARKED, WITH PAPER CLIPPED ON THE PLATEN: SLACKEN THE MHA-PN-VN-51 "
        "THUMB SCREW, SLIDE THE MHA-PN-VN-56 MARKER UNTIL A "
        f"{NIB_CLEARANCE_TEXT} FEELER JUST DRAGS BETWEEN NIB AND PAPER, THEN "
        "RE-TIGHTEN THE THUMB SCREW FINGER-TIGHT. THE MHA-PN-07 STUD KEEPS "
        "ITS MHA-PN-00 SETTING."
    ),
    "nib-on-paper": (
        "NIB ON PAPER, BEFORE RUNNING: SLACKEN THE MHA-PN-VN-51 THUMB SCREW, "
        "PUSH THE MHA-PN-VN-56 MARKER ON ALONG ITS AXIS UNTIL THE NIB JUST "
        "TOUCHES THE PAPER, NO FEELER, THEN RE-TIGHTEN THE THUMB SCREW "
        f"FINGER-TIGHT. TO PARK THE PEN, REPEAT STEP {_n('nib-set')}."
    ),
    "stick-parked": (
        "MEASURING STICK: PARK MHA-MS-00 ON THE MHA-FR-01 AS-CAST TOP BETWEEN "
        "THE RAISED DECK'S EAST EDGE AND THE EAST COLUMNS, AS SHOWN ON SHEET 2: "
        "STICK FRONT TO REAR, THUMBSCREW ABOVE THE STICK, CENTRED FRONT TO REAR."
    ),
}
if set(_STEP_TEXT) != set(steps.SEQUENCE):
    raise AssertionError("every integration step needs exactly one text")

ASSEMBLY_STEPS: tuple[str, ...] = tuple(
    f"{number}. {_STEP_TEXT[key]}" for number, key in enumerate(steps.SEQUENCE, 1)
)

ASSEMBLY_CHECKS: tuple[str, ...] = (
    "1. THE SHEET 1 BAR TOP AND STUD DROP READ AS DIMENSIONED; THE NIB "
    "TOUCHES THE PAPER.",
    f"2. {ch_vn_spring_hook_spec.ANCHOR_INSTALL_CHECK}",
    "3. WITH EVERY CHANNEL AMPLITUDE AT ZERO THE PLATE TOP READS LEVEL, AND "
    "TWO CRANK TURNS DRAW A STRAIGHT LINE ALONG THE PAPER.",
    "4. THROUGH TWO CRANK TURNS NOTHING BINDS OR RUBS, THE CHAIN STAYS ON BOTH "
    "WHEELS AND BOTH WIRES STAY IN THEIR GROOVES.",
)

EXPLODED_CAPTION = "EXPLODED VIEW - INTEGRATION STEPS ON SHEET 4"
ORIENTATION_NOTE = (
    "FRONT = PAPER SIDE. WEST IS LEFT IN THE FRONT VIEW; THE CRANK IS EAST."
)
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
