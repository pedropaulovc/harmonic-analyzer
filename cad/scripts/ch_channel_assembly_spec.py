"""MHA-CH-000 fitter-package data: settings chain, explode plan, BOM text.

Pure data, no SolidWorks: build_ch_channel_assembly authors the settings
reference sketch and the named explode from it, and draw_ch_channel_assembly
reads the same names back.

Settings: two construction sketches on the Right plane (sketch x is machine
-z, sketch y machine y), one per bank view, so each 1:1 view shows only the
chain on its own axis (the other lies 808 mm off it, off the sheet).
``PIVOT_FEATURE`` is a chain along the pivot axis -- south ear inner face,
south washer south face, hub 0 south face, hub 19 north face;
``FULCRUM_FEATURE`` one leg on the fulcrum axis between the keeper lugs'
inner faces. The spring set and the closed-up stack length are the fit-up's
two settings (rocker_bank_layout); the lug span is shown as a reference, the
pair being set off the top frame.

Explode (``EXPLODED_VIEW_NAME``): every channel alike, end hardware out along
z on its own side, fasteners up out of their taps, the rods down off the
arms, the bars (with the pins pressed in them) up off the rocker straps, the
spring anchors down and the fulcrum shaft withdrawn north; the pivot shaft,
rockers, levers and springs stay put.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from ch_fulcrum_keeper_spec import (
    FULCRUM_KEEPER_CENTRE_Z,
    KEEPER_INNER_FACE_SPAN_MM,
    KEEPER_Z_OFF,
    LUG_HALF_T,
)
from channel_frame_geom import LEVER_FULCRUM_XY, ROCKER_PIVOT_XY
from rocker_bank_layout import (
    HUB0_SOUTH_FACE_Z,
    HUB19_NORTH_FACE_Z,
    ROCKER_SPRING_SET,
    ROCKER_SPRING_SET_BAND,
    SOUTH_EAR_INNER_Z,
    SOUTH_WASHER_Z,
    STACK_L20_ACCEPT,
    STACK_L20_ACCEPT_BAND,
    STACK_MID_Z,
)

# --- Settings reference sketches --------------------------------------------
PIVOT_FEATURE = "RockerBankSettingsReference"
FULCRUM_FEATURE = "LeverBankSettingsReference"
FEATURES = (PIVOT_FEATURE, FULCRUM_FEATURE)
SPRING_SET_DIMENSION = "RockerSpringSet"
STACK_LENGTH_DIMENSION = "RockerStackLength"
LUG_SPAN_DIMENSION = "KeeperLugSpan"

# Pivot-axis chain stations, machine z, south to north.
PIVOT_CHAIN_Z = (
    SOUTH_EAR_INNER_Z,
    SOUTH_WASHER_Z[0],
    HUB0_SOUTH_FACE_Z,
    HUB19_NORTH_FACE_Z,
)
# Fulcrum-axis leg: the keeper lugs' inner faces, south then north.
LUG_INNER_FACE_Z = (
    FULCRUM_KEEPER_CENTRE_Z - (KEEPER_Z_OFF - LUG_HALF_T),
    FULCRUM_KEEPER_CENTRE_Z + (KEEPER_Z_OFF - LUG_HALF_T),
)
PIVOT_Y = ROCKER_PIVOT_XY[1]
FULCRUM_Y = LEVER_FULCRUM_XY[1]

if abs(PIVOT_CHAIN_Z[1] - PIVOT_CHAIN_Z[0] - ROCKER_SPRING_SET) > 1e-9:
    raise AssertionError("the spring-set leg is not ROCKER_SPRING_SET")
if abs(PIVOT_CHAIN_Z[3] - PIVOT_CHAIN_Z[2] - STACK_L20_ACCEPT[0]) > 1e-9:
    raise AssertionError("the stack leg is not the closed-up stack length")
if abs(LUG_INNER_FACE_Z[1] - LUG_INNER_FACE_Z[0] - KEEPER_INNER_FACE_SPAN_MM) > 1e-9:
    raise AssertionError("the lug leg is not the keeper inner-face span")

# Marked for the drawing: the two settings and the reference span.
DRAWING_DIMENSIONS = {
    PIVOT_FEATURE: {SPRING_SET_DIMENSION, STACK_LENGTH_DIMENSION},
    FULCRUM_FEATURE: {LUG_SPAN_DIMENSION},
}
DRAWING_PRECISION = {
    PIVOT_FEATURE: {SPRING_SET_DIMENSION: 2, STACK_LENGTH_DIMENSION: 2},
    FULCRUM_FEATURE: {LUG_SPAN_DIMENSION: 2},
}
DIMENSION_FEATURE = {
    name: feature for feature, names in DRAWING_DIMENSIONS.items() for name in names
}
TOLERANCE_PRECISION = 2
# (lower, upper) deviations; the stack accepts only long (STACK_L20_ACCEPT).
DIMENSION_TOLERANCES = {
    SPRING_SET_DIMENSION: (-ROCKER_SPRING_SET_BAND, ROCKER_SPRING_SET_BAND),
    STACK_LENGTH_DIMENSION: (-STACK_L20_ACCEPT_BAND[1], STACK_L20_ACCEPT_BAND[0]),
}
REFERENCE_DIMENSIONS = frozenset({LUG_SPAN_DIMENSION})
DIMENSION_CALLOUTS = {
    SPRING_SET_DIMENSION: "SPRING-SET BLADE",
    STACK_LENGTH_DIMENSION: "STACK, CLOSED UP",
    LUG_SPAN_DIMENSION: "LUG SPAN",
}
if set(DIMENSION_TOLERANCES) | REFERENCE_DIMENSIONS != set(DIMENSION_FEATURE):
    raise AssertionError("every marked dimension is toleranced or reference")

# --- Named explode -----------------------------------------------------------
EXPLODED_VIEW_NAME = "CHANNEL_EXPLODED"
SOURCE_CONFIGURATION = "Default"
# Pairs at the bank ends split on this plane: south below it, north above.
BANK_MID_Z = STACK_MID_Z

KEEPER = "ch-fulcrum-keeper"
FULCRUM_SHAFT = "ch-fulcrum-shaft"
KEEPER_SET_SCREW = "vn-fulcrum-set-screw"
KEEPER_FOOT_SCREW = "vn-frame-side-screw"
BRACKET = "ch-pivot-bracket"
BRACKET_SET_SCREW = "vn-arbor-set-screw"
BRACKET_HOLD_DOWN = "vn-pedestal-hold-down-screw"
WASHER = "ch-rocker-thrust-washer"
BANK_SPRING = "vn-rocker-bank-spring"
ROD = "ch-connecting-rod"
BAR = "ch-amplitude-bar"
BAR_PIN = "ch-bar-pivot-pin"
HOOK = "vn-spring-hook"

Side = Literal["south", "north"]


@dataclass(frozen=True)
class ExplodeStep:
    """One native explode step: every instance of each member family (on
    ``side`` of ``BANK_MID_Z`` only, when given) moves ``distance_mm`` along
    the world ``axis`` (sign = direction)."""

    label: str
    stems: tuple[str, ...]
    axis: Literal["x", "y", "z"]
    distance_mm: float
    side: Side | None = None


_KEEPER_GROUP = (KEEPER, KEEPER_SET_SCREW, KEEPER_FOOT_SCREW)
_BRACKET_GROUP = (BRACKET, BRACKET_SET_SCREW, BRACKET_HOLD_DOWN)
EXPLODE_STEPS: tuple[ExplodeStep, ...] = (
    ExplodeStep("south keeper out", _KEEPER_GROUP, "z", -50.0, "south"),
    ExplodeStep("north keeper out", _KEEPER_GROUP, "z", 50.0, "north"),
    ExplodeStep("keeper set screws up", (KEEPER_SET_SCREW,), "y", 25.0),
    ExplodeStep("keeper foot screws up", (KEEPER_FOOT_SCREW,), "y", 25.0),
    ExplodeStep("south bracket out", _BRACKET_GROUP, "z", -60.0, "south"),
    ExplodeStep("north bracket out", _BRACKET_GROUP, "z", 60.0, "north"),
    ExplodeStep("bracket set screws up", (BRACKET_SET_SCREW,), "y", 25.0),
    ExplodeStep("bracket hold-downs up", (BRACKET_HOLD_DOWN,), "y", 25.0),
    ExplodeStep("bank spring out", (BANK_SPRING,), "z", -40.0, "south"),
    ExplodeStep("south washer out", (WASHER,), "z", -20.0, "south"),
    ExplodeStep("north washer out", (WASHER,), "z", 20.0, "north"),
    ExplodeStep("rods down", (ROD,), "y", -50.0),
    # Up, not along x: 50 west put each bar (pin x 72.9) on its own spring's
    # line (lever spring hole x 24.85) and hid the spring (r2 balloon pick);
    # 50 east put bar 3 over the bank spring (r4 balloon pick, shared edge).
    ExplodeStep("bars up", (BAR, BAR_PIN), "y", 50.0),
    ExplodeStep("anchors down", (HOOK,), "y", -40.0),
    # Withdrawn north past the north keeper: in place only its 10 mm tips
    # stand clear of the lever hubs, under 1.5 mm at 1:7, and its balloon
    # landed on lever 20's ink (r4 balloon pick, shared edge).
    ExplodeStep("fulcrum shaft out north", (FULCRUM_SHAFT,), "z", 120.0),
)
EXPLODED_STEMS = frozenset(stem for step in EXPLODE_STEPS for stem in step.stems)


@dataclass(frozen=True)
class Instance:
    name: str
    stem: str
    z_mm: float


def plan_explode(
    instances: Sequence[Instance],
) -> list[tuple[ExplodeStep, tuple[str, ...]]]:
    """Resolve every step to the component names it moves.

    Refuses a family the model lacks, a sided step that would move nothing,
    and a sided pair that is not one instance per side.
    """
    stems = {instance.stem for instance in instances}
    missing = sorted(EXPLODED_STEMS - stems)
    if missing:
        raise ValueError(f"explode families absent from the model: {missing!r}")
    plan = []
    for step in EXPLODE_STEPS:
        names = []
        for instance in instances:
            if instance.stem not in step.stems:
                continue
            south = instance.z_mm < BANK_MID_Z
            if step.side is None or (step.side == "south") == south:
                names.append(instance.name)
        if not names:
            raise ValueError(f"{step.label}: moves no instance")
        if step.side is not None:
            moved = {instance.stem for instance in instances if instance.name in names}
            if moved != set(step.stems) or len(names) != len(step.stems):
                raise ValueError(
                    f"{step.label}: expected one instance per family, got {names!r}"
                )
        plan.append((step, tuple(sorted(names))))
    return plan


# --- BOM ---------------------------------------------------------------------
# Hand-written (components carry no Description property), keyed by stem; the
# spring row is keyed by its built variant stem in the drawing.
BOM_DESCRIPTIONS = {
    "ch-pivot-shaft": "ROCKER PIVOT SHAFT",
    "ch-fulcrum-shaft": "LEVER FULCRUM SHAFT",
    BRACKET: "ROCKER PIVOT BRACKET",
    BRACKET_SET_SCREW: "#4-40 X 1/4 CUP-POINT SET SCREW",
    WASHER: "ROCKER BANK THRUST WASHER",
    BANK_SPRING: "WAVE DISC SPRING",
    BRACKET_HOLD_DOWN: "#8-32 X 3/4 FILLISTER HEAD SCREW",
    KEEPER: "FULCRUM SHAFT KEEPER",
    KEEPER_FOOT_SCREW: "#2-56 X 7/16 FILLISTER HEAD SCREW",
    KEEPER_SET_SCREW: "#1-72 X 5/32 CUP-POINT SET SCREW",
    "ch-rocker-arm": "ROCKER ARM",
    ROD: "CONNECTING ROD",
    BAR: "AMPLITUDE BAR",
    "ch-channel-lever": "CHANNEL LEVER",
    "ch-rod-pivot-pin": "ROD PIVOT PIN",
    BAR_PIN: "BAR PIVOT PIN",
    "vn-channel-spring-installed": "EXTENSION SPRING",
    HOOK: "#6-32 EYEBOLT SPRING ANCHOR",
}
