"""Pure contract shared by the complete-machine builder and its fitter package.

MHA-HA-000 is the integration sheet: every subassembly arrives built and
checked to its own drawing, so the BOM lists the eight subassemblies (one row
each, top level only) and the steps are the joints between them, their locks
and consumables, and the settings only the complete machine can make.

The builder (build_ha_harmonic_analyzer_assembly) authors the named explode
and the hidden integration-settings sketch from this module; the drawing
(draw_ha_harmonic_analyzer_assembly) only consumes them. The sheets' text,
BOM descriptions and balloon targets live in ha_harmonic_analyzer_assembly_notes,
which the builder does not import, so wording edits leave the assembly's
recipe alone. No SolidWorks.

Machine frame: +Y up, -Z front (the paper side), +X west, -X east (the
crank). The drawing's isometric looks from the east-front-top, so a part
raised in +Y or pushed rearward in +Z draws above and right of the parts in
front of it; one pushed west (+X) draws up and left, east (-X) down and right.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

import fr_harmonic_base_spec as base
from frame_column_stations import COLUMN_X
from mg_wheel_bar_geom import BAR_LENGTH, BAR_SIDE, WHEEL_BAR_X0
from pn_pen_carriage_geom import STUD_HEAD_TOP_REST_Y
from vn_pen_wire_geom import WHEEL_BAR_Y, WIRE_X

ASM_NAME = "ha-harmonic-analyzer"
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
# * the wheel bar's top above the deck, on the axis of the west front column
#   (+X) the bar clamps round, so the construction line the front view must
#   show for the dimension to import lies on that column's centreline
#   (machinist review r2/r3 on b4df34ad9: at the deck's west edge it floated
#   beside the column, an unlabelled chain line). A vertical dimension does
#   not depend on its station; the bar runs x -8..226 over the column;
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
BAR_HEIGHT_X = COLUMN_X
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
