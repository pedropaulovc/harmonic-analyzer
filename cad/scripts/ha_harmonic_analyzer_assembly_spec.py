"""Pure contract shared by the complete-machine builder and its fitter package.

MHA-HA-000 is the integration sheet: every subassembly arrives built and
checked to its own drawing, so the BOM lists the eight subassemblies (one row
each, top level only) and the steps are the joints between them, their locks
and consumables, and the settings only the complete machine can make.

The builder (build_ha_harmonic_analyzer_assembly) authors the named explode
and the hidden integration-settings sketch from this module; the drawing
(draw_ha_harmonic_analyzer_assembly) only consumes them. No SolidWorks.

Machine frame: +Y up, -Z front (the paper side), +X west, -X east (the
crank). The drawing's isometric looks from the east-front-top, so a part
raised in +Y or pushed rearward in +Z draws above and right of the parts in
front of it; one pushed west (+X) draws up and left, east (-X) down and right.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

import dt_drive_train_steps
import fr_harmonic_base_spec as base
import ha_harmonic_analyzer_assembly_steps as steps
import pd_paper_drive_assembly_steps as pd_steps
from mg_wheel_bar_geom import BAR_LENGTH, BAR_SIDE, WHEEL_BAR_X0
from paper_drive_geom import PEN_PAPER_CLEARANCE_MM
from pn_pen_carriage_geom import STUD_HEAD_TOP_REST_Y
from vn_pen_wire_geom import WHEEL_BAR_Y, WIRE_X

ASM_NAME = "ha-harmonic-analyzer"
DRAWING_NUMBER = steps.DRAWING_NUMBER
SOURCE_CONFIGURATION = "Default"

# --- BOM: one row per subassembly, in the builder's insertion order ---------
MEASURING_STICK = "ms-measuring-stick"
BOM_ORDER: tuple[str, ...] = (
    "fr-frame",
    "dt-drive-train",
    "ch-channel",
    "sm-summing",
    "mg-magnifier",
    "pn-pen",
    "pd-paper-drive",
    MEASURING_STICK,
)
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
# subassembly, so the balloon names one row.
BALLOON_PARTS: dict[str, str] = {
    "fr-frame": "fr-top-frame",
    "dt-drive-train": "dt-crank-handle",
    "ch-channel": "ch-fulcrum-shaft",
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

# --- Named explode (HA_EXPLODED) --------------------------------------------
EXPLODED_VIEW_NAME = "HA_EXPLODED"


@dataclass(frozen=True)
class ExplodeStep:
    """One native explode step: every instance of each member subassembly
    moves ``distance_mm`` along the world ``axis`` (sign = direction)."""

    label: str
    stems: tuple[str, ...]
    axis: Literal["x", "y", "z"]
    distance_mm: float


# The frame stays put. Distances are presentation offsets, sized so no two
# subassemblies overlap on the isometric: the summing lever lifts clear above
# the top frame, the channel bank goes rearward (up-right), the drive train
# east (down-right), and the output chain stacks forward-left: paper drive
# low, pen above it, magnifier above the pen. The stick goes forward below.
EXPLODE_STEPS: tuple[ExplodeStep, ...] = (
    ExplodeStep("summing up", ("sm-summing",), "y", 450.0),
    ExplodeStep("channel rearward", ("ch-channel",), "z", 750.0),
    ExplodeStep("drive train east", ("dt-drive-train",), "x", -700.0),
    ExplodeStep("paper drive forward", ("pd-paper-drive",), "z", -450.0),
    ExplodeStep("magnifier west", ("mg-magnifier",), "x", 450.0),
    ExplodeStep("pen forward", ("pn-pen",), "z", -450.0),
    ExplodeStep("pen up", ("pn-pen",), "y", 300.0),
    ExplodeStep("stick forward", (MEASURING_STICK,), "z", -700.0),
)
STATIONARY_STEMS = frozenset({"fr-frame"})
SHOWN_STEMS = STATIONARY_STEMS | frozenset(
    stem for step in EXPLODE_STEPS for stem in step.stems
)
if SHOWN_STEMS != frozenset(BOM_ORDER):
    raise AssertionError("the explode must show exactly the BOM rows")


@dataclass(frozen=True)
class Instance:
    name: str
    stem: str


def plan_explode(
    instances: Sequence[Instance],
) -> list[tuple[ExplodeStep, tuple[str, ...]]]:
    """Resolve every step to the top-level component names it moves.

    Refuses a shown subassembly the model lacks, or one it holds twice.
    """
    counts: dict[str, int] = {}
    for instance in instances:
        counts[instance.stem] = counts.get(instance.stem, 0) + 1
    missing = sorted(SHOWN_STEMS - set(counts))
    if missing:
        raise ValueError(f"explode subassemblies absent from the model: {missing!r}")
    repeated = sorted(stem for stem in SHOWN_STEMS if counts[stem] != 1)
    if repeated:
        raise ValueError(f"explode subassemblies inserted more than once: {repeated!r}")
    return [
        (
            step,
            tuple(
                sorted(
                    instance.name
                    for instance in instances
                    if instance.stem in step.stems
                )
            ),
        )
        for step in EXPLODE_STEPS
    ]


# --- Integration settings (hidden top-assembly sketch on the Front plane) ---
# Two construction lines carry the two settings the complete machine owns,
# each a driving dimension the drawing imports onto the front view:
# * the wheel bar's top above the deck, measured at the deck's west edge
#   (the bar runs x -8..226 over it);
# * the pen adjuster stud head's top below the bar top, on the pen-rod line
#   (the wire's rest run), which the pen-wire tie sets.
SETTING_FEATURE = "IntegrationSettings"
BAR_HEIGHT_DIMENSION = "WheelBarTopAboveDeck"
STUD_DROP_DIMENSION = "StudHeadBelowWheelBar"
SETTING_PRECISION = 1
DRAWING_DIMENSIONS = {SETTING_FEATURE: {BAR_HEIGHT_DIMENSION, STUD_DROP_DIMENSION}}
DRAWING_PRECISION = {
    SETTING_FEATURE: {
        BAR_HEIGHT_DIMENSION: SETTING_PRECISION,
        STUD_DROP_DIMENSION: SETTING_PRECISION,
    }
}

DECK_TOP_Y = base.STACK_HEIGHT
WHEEL_BAR_TOP_Y = WHEEL_BAR_Y + BAR_SIDE / 2.0
BAR_HEIGHT_X = base.DECK_HALF_X
STUD_X = WIRE_X
_BAR_X_SPAN = (WHEEL_BAR_X0 - BAR_LENGTH / 2.0, WHEEL_BAR_X0 + BAR_LENGTH / 2.0)
if not (_BAR_X_SPAN[0] < STUD_X < BAR_HEIGHT_X < _BAR_X_SPAN[1]):
    raise AssertionError("both setting stations must lie under the wheel bar")
BAR_HEIGHT_MM = round(WHEEL_BAR_TOP_Y - DECK_TOP_Y, 6)
STUD_DROP_MM = round(WHEEL_BAR_TOP_Y - STUD_HEAD_TOP_REST_Y, 6)
if not (BAR_HEIGHT_MM > 0.0 and STUD_DROP_MM > 0.0):
    raise AssertionError("setting dimensions must be positive")


@dataclass(frozen=True)
class SettingLine:
    """One vertical construction line: start (low) and end (high), mm."""

    dimension: str
    x: float
    y_low: float
    y_high: float

    @property
    def length(self) -> float:
        return round(self.y_high - self.y_low, 6)


SETTING_LINES: tuple[SettingLine, ...] = (
    SettingLine(BAR_HEIGHT_DIMENSION, BAR_HEIGHT_X, DECK_TOP_Y, WHEEL_BAR_TOP_Y),
    SettingLine(STUD_DROP_DIMENSION, STUD_X, STUD_HEAD_TOP_REST_Y, WHEEL_BAR_TOP_Y),
)
if tuple(line.length for line in SETTING_LINES) != (BAR_HEIGHT_MM, STUD_DROP_MM):
    raise AssertionError("setting lines must carry the setting values")

NIB_CLEARANCE_TEXT = f"{PEN_PAPER_CLEARANCE_MM:.2f}"
# Each setting's printed callout names what it sets and the step that sets
# it; the step text points back to the sheet-1 dimension, so the value lives
# only on the associative model dimension.
SETTING_CALLOUTS = {
    BAR_HEIGHT_DIMENSION: f"WHEEL BAR TOP (STEP {steps.step_number('magnifier-bar-clamped')})",
    STUD_DROP_DIMENSION: f"STUD HEAD (STEP {steps.step_number('pen-wire-tied')})",
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
        "MEASURING STICK: PARK MHA-MS-000 ON THE GREEN LAND BETWEEN THE DECK'S "
        "EAST EDGE AND THE EAST COLUMNS, STICK FRONT TO REAR, GRADUATIONS UP, "
        "CENTRED FRONT TO REAR (SHEET 2)."
    ),
}
if set(_STEP_TEXT) != set(steps.SEQUENCE):
    raise AssertionError("every integration step needs exactly one text")

ASSEMBLY_STEPS: tuple[str, ...] = tuple(
    f"{number}. {_STEP_TEXT[key]}" for number, key in enumerate(steps.SEQUENCE, 1)
)

ASSEMBLY_CHECKS: tuple[str, ...] = (
    "1. WHEEL BAR TOP AND STUD HEAD READ THEIR SHEET 1 SETTINGS; A "
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
