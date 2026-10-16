"""Drawing-only text of the complete-machine fitter package (MHA-HA-000).

The BOM descriptions, balloon targets, setting callouts, integration steps
and checks the sheets print. Only draw_ha_harmonic_analyzer_assembly (and its
tests) import this module; the builder reads ha_harmonic_analyzer_assembly_spec
alone, so a wording edit here does not rebuild the complete-machine assembly.
No SolidWorks.
"""

from __future__ import annotations

import dt_drive_train_steps
import ha_harmonic_analyzer_assembly_steps as steps
import pd_paper_drive_assembly_steps as pd_steps
from ha_harmonic_analyzer_assembly_spec import (
    BAR_HEIGHT_DIMENSION,
    BOM_ORDER,
    MEASURING_STICK,
    STUD_DROP_DIMENSION,
)
from paper_drive_geom import PEN_PAPER_CLEARANCE_MM

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
    "fr-frame": "fr-top-frame",
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

NIB_CLEARANCE_TEXT = f"{PEN_PAPER_CLEARANCE_MM:.2f}"
# Each setting's printed callout names what it sets and the step that sets
# it; the step text points back to the sheet-1 dimension, so the value lives
# only on the associative model dimension.
# Both callouts stay short: the bar-height text stands wholly west of the
# front view, the stud text in the bay between the pen rod and the east column.
SETTING_CALLOUTS = {
    BAR_HEIGHT_DIMENSION: f"BAR TOP (STEP {steps.step_number('magnifier-bar-clamped')})",
    STUD_DROP_DIMENSION: f"STUD (STEP {steps.step_number('pen-wire-tied')})",
}

# --- Fitter package text ----------------------------------------------------
THREADLOCKER = "LOCTITE 243 (BLUE, REMOVABLE MEDIUM-STRENGTH)"
CHANNEL_ANCHORS = 20


def _n(key: str) -> int:
    return steps.step_number(key)


_STEP_TEXT: dict[str, str] = {
    "frame-built": (
        "FRAME: BUILD MHA-FR-000 COMPLETE ON A FLAT BENCH. MHA-VN-023 STAYS "
        f"BACKED CLEAR IN THE GOOSENECK HUB UNTIL STEP {_n('summing-levelled')}."
    ),
    "drive-train-built": (
        f"DRIVE TRAIN: BUILD {dt_drive_train_steps.DRAWING_NUMBER} ON THE BASE, "
        f"STEPS 1-{len(dt_drive_train_steps.SEQUENCE)} IN ORDER."
    ),
    "summing-hung": (
        "SUMMING LEVER: HANG MHA-SM-000 UNDER THE TOP-FRAME CROSSBAR AND CLAMP "
        "THE COUNTER SPRING'S UPPER LOOP TO THE MHA-SM-001 POST, PER ITS STEPS "
        "BEFORE FINAL ASSEMBLY. THE POST STAYS OUT OF ITS HUB."
    ),
    "channel-built": (
        "CHANNEL BANK: BUILD MHA-CH-000 COMPLETE. EACH MHA-VN-004 SPRING HANGS "
        "FROM ITS LEVER WITH ITS BOTTOM LOOP FREE."
    ),
    "channel-anchors-set": (
        f"CHANNEL ANCHORS ({CHANNEL_ANCHORS} OFF): DISCARD THE HEX NUT SUPPLIED "
        f"WITH EACH MHA-VN-012. WET THE THREAD WITH {THREADLOCKER}. RUN IT DOWN "
        "ITS #6-32 TAP IN THE MHA-SM-003 PLATE UNTIL THE NECK SEATS ON THE "
        "PLATE TOP, THEN BACK IT OUT NO MORE THAN 1 TURN (CHANNEL PRELOAD) TO "
        "CLOCK THE EYE INTO ITS SPRING'S PULL PLANE. HOOK THE SPRING'S BOTTOM "
        "LOOP INTO THE EYE. "
        "CURE 24 H BEFORE THE MACHINE IS RUN."
    ),
    "summing-levelled": (
        "GOOSENECK AND LEVEL, PER MHA-SM-000 FINAL-ASSEMBLY STEPS: DROP THE "
        "MHA-SM-001 POST INTO THE TOP FRAME'S GOOSENECK HUB AND HOOK THE "
        "MHA-VN-005 LOWER LOOP INTO THE MHA-VN-001 EYE. WITH EVERY CHANNEL "
        "AMPLITUDE AT ZERO, SLIDE THE POST UNTIL THE MHA-SM-003 PLATE TOP READS "
        "LEVEL, THEN TIGHTEN MHA-VN-023 ON THE POST (NO LOCK; RE-SET IF IT "
        "DRIFTS)."
    ),
    "paper-drive-built": (
        f"PAPER DRIVE: BUILD MHA-PD-000 STEPS 1-{len(pd_steps.SEQUENCE)} IN "
        f"ORDER; ITS STEP {pd_steps.step_number('bar-clamped')} SETS THE "
        "SUPPORT BAR ON THE FRONT COLUMNS. ITS CHAIN STEPS NEED THE CRANK SIDE "
        f"OF STEP {_n('drive-train-built')}."
    ),
    "magnifier-bar-clamped": (
        "MAGNIFIER BAR: CLOSE THE MHA-SH-001/MHA-SH-002 CLAMP ARCS (STARTED "
        "LOOSE AT MHA-MG-000) ROUND THE WEST FRONT COLUMN, WHEEL TOWARD THE PEN "
        "ROD. SET THE MHA-MG-008 BAR TOP TO ITS HEIGHT ABOVE THE DECK (SHEET 1) "
        "AND "
        "LEVEL ALONG ITS LENGTH, THEN TIGHTEN BOTH MHA-VN-021 CLAMP SCREWS "
        "EVENLY. NO THREADLOCKER."
    ),
    "magnifier-bracket-screwed": (
        "MAGNIFIER BRACKET: SEAT THE MHA-MG-001 BRACKET FLANGE ON ITS SEATS ON "
        "MHA-SM-003 AND DRIVE BOTH MHA-VN-050 #2-56 SCREWS UNTIL THE HEADS SEAT "
        "ON THE COUNTERBORE FLOORS. NO THREADLOCKER."
    ),
    "lever-wire-fitted": "LEVER WIRE: PER MHA-MG-000 (SHEET 4).",
    "pen-hung": (
        "PEN: HANG MHA-PN-000 FROM THE MHA-MG-008 BAR AND LOCK THE HANGER SCREW "
        "PER ITS HANGER SCREW LOCK STEP (MHA-VN-007, MHA-VN-063 NUT, "
        "MHA-VN-064 JAM NUT)."
    ),
    "pen-wire-tied": (
        f"PEN WIRE, WITH THE PLATE TOP LEVEL (STEP {_n('summing-levelled')}): "
        "LEAD THE UPPER END OF MHA-VN-067 INTO THE MHA-MG-005 RIM GROOVE AT "
        "THE 3 O'CLOCK TANGENT (FRONT VIEW) AND TIE IT OFF AT TIE 2, SET SO "
        "THE MHA-PN-007 STUD HEAD TOP HANGS ITS SHEET 1 DROP BELOW THE "
        "MHA-MG-008 BAR TOP. TRIM THE TAIL."
    ),
    "nib-set": (
        "NIB TO PAPER, WITH PAPER CLIPPED ON THE PLATEN: SLACKEN THE MHA-VN-010 "
        "THUMB SCREW, SLIDE THE MHA-VN-065 MARKER UNTIL A "
        f"{NIB_CLEARANCE_TEXT} FEELER JUST DRAGS BETWEEN NIB AND PAPER, THEN "
        "RE-TIGHTEN THE THUMB SCREW FINGER-TIGHT. THE MHA-PN-007 STUD KEEPS "
        "ITS MHA-PN-000 SETTING."
    ),
    "stick-parked": (
        "MEASURING STICK: PARK MHA-MS-000 ON THE MHA-FR-001 AS-CAST TOP BETWEEN "
        "THE RAISED DECK'S EAST EDGE AND THE EAST COLUMNS, AS SHOWN ON SHEET 2: "
        "STICK FRONT TO REAR, GRADUATIONS UP, CENTRED FRONT TO REAR."
    ),
}
if set(_STEP_TEXT) != set(steps.SEQUENCE):
    raise AssertionError("every integration step needs exactly one text")

ASSEMBLY_STEPS: tuple[str, ...] = tuple(
    f"{number}. {_STEP_TEXT[key]}" for number, key in enumerate(steps.SEQUENCE, 1)
)

ASSEMBLY_CHECKS: tuple[str, ...] = (
    "1. BAR TOP AND STUD READ THEIR SHEET 1 SETTINGS; A "
    f"{NIB_CLEARANCE_TEXT} FEELER JUST DRAGS BETWEEN NIB AND PAPER.",
    f"2. ALL {CHANNEL_ANCHORS} ANCHOR EYES STAND IN THEIR SPRINGS' PULL PLANES; "
    "NO NECK STANDS MORE THAN 1 TURN OFF THE PLATE TOP.",
    "3. WITH EVERY CHANNEL AMPLITUDE AT ZERO THE PLATE TOP READS LEVEL, AND "
    "TWO CRANK TURNS DRAW A STRAIGHT LINE ALONG THE PAPER.",
    "4. THROUGH TWO CRANK TURNS NOTHING BINDS OR RUBS, THE CHAIN STAYS ON BOTH "
    "WHEELS AND BOTH WIRES STAY IN THEIR GROOVES.",
)

EXPLODED_CAPTION = "EXPLODED VIEW - INTEGRATION STEPS ON SHEET 4"
ORIENTATION_NOTE = (
    "FRONT = PAPER SIDE. WEST IS LEFT IN THE FRONT VIEW; THE CRANK IS EAST."
)
