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
spring anchors down and the fulcrum shaft withdrawn south; the north-most
channel (the one the balloons pin) is pulled out north of the bank whole, its
two pins out of their bores; the pivot shaft and the other channels' rockers,
levers and springs stay put.
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
    # The accepted stack caps the hubs' summed excess, so each strap stays on
    # its rod's cam plane and under its bar's foot notch (test_channel_axial_
    # budget); r10 machinist review: name what the tight band sets (rule 4).
    STACK_LENGTH_DIMENSION: "STACK, CLOSED UP: STRAP PITCH TO RODS AND BARS",
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
BRACKET_HOLD_DOWN = "vn-bracket-hold-down-screw"
WASHER = "vn-rocker-thrust-washer"
BANK_SPRING = "vn-rocker-bank-spring"
ROD = "ch-connecting-rod"
BAR = "ch-amplitude-bar"
BAR_PIN = "ch-bar-pivot-pin"
HOOK = "vn-spring-hook"
ANCHOR_NUT = "ch-anchor-jam-nut"
ARM = "ch-rocker-arm"
ROD_PIN = "ch-rod-pivot-pin"
LEVER = "ch-channel-lever"
# The installed spring's family: the model holds its built variants
# (``-stretchNN``, build_ch_channel_assembly), each one family here.
CHANNEL_SPRING = "vn-channel-spring-installed"


def family(stem: str) -> str:
    """The explode family of a model component stem."""
    return CHANNEL_SPRING if stem.startswith(f"{CHANNEL_SPRING}-stretch") else stem


# "north-most": each member family's instance of greatest z only, the one
# its balloon pins (draw_ch_channel_assembly._validate_source).
Side = Literal["south", "north", "north-most"]


@dataclass(frozen=True)
class ExplodeStep:
    """One native explode step: every instance of each member family (on
    ``side`` of ``BANK_MID_Z`` only, or only the north-most one, when given)
    moves ``distance_mm`` along the world ``axis`` (sign = direction)."""

    label: str
    stems: tuple[str, ...]
    axis: Literal["x", "y", "z"]
    distance_mm: float
    side: Side | None = None


_KEEPER_GROUP = (KEEPER, KEEPER_SET_SCREW, KEEPER_FOOT_SCREW)
_BRACKET_GROUP = (BRACKET, BRACKET_SET_SCREW, BRACKET_HOLD_DOWN)
# The exploded view's outline is the isometric of the exploded model's x/y/z
# box, not of its ink (r12/r13 drawing leaves: 300 more north on DETAIL B's
# cluster grew it 17.5 mm tall and 30 mm wide, 90 more up on the pulled
# channel 10.5 mm tall, each exactly that box's growth). The balloon ring
# leaves it 198 mm of sheet height and r11 used 181, so 17 mm (x 7 x sqrt 6:
# 286 model mm) is left to spend: a step that carries a part past the box
# spends 1 per mm along x or z and 2 along y.
#
# The north bracket's hardware and the north washer (DETAIL B's cluster): at
# 60 north alone the bracket sat inside the hanging rocker arms. Leaders 4 and
# 7 met on it there, and the letter B fell on the arms (r10 machinist review).
# 30 further north and 570 up lifts the cluster, free (still inside the box),
# into the open space between the bank's bar column and the pulled-out
# channel. At 60/500 (r14) it sorted round the ring among the channel's lever
# balloons and leader 4 crossed 14; a replay of the r14 ring (its 19 logged
# attachments) clears every pair from 540 to 580 up at 10 to 40 further north.
_NORTH_END_GROUP = (*_BRACKET_GROUP, WASHER)
# One whole channel, pulled north out of the bank off both shafts: closed up,
# the 20 channels print as one dark mass at 1:7 and the balloons pinned on
# the north-most instances landed inside it (r11 machinist review). At 300
# its footprint stands 26 px (5.5 mm) clear of the bank's on an r11 sheet
# replay; its two pins then come 25 further out of their bores, along their
# axes. It spends 156 of the box's 286 (its pins' north ends ~400 north).
_CHANNEL_GROUP = (
    ARM,
    ROD,
    ROD_PIN,
    LEVER,
    BAR,
    BAR_PIN,
    CHANNEL_SPRING,
    HOOK,
    ANCHOR_NUT,
)
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
    ExplodeStep("north end further out", _NORTH_END_GROUP, "z", 30.0, "north"),
    ExplodeStep("north end up", _NORTH_END_GROUP, "y", 570.0, "north"),
    ExplodeStep("rods down", (ROD,), "y", -50.0),
    # Up, not along x: 50 west put each bar (pin x 72.9) on its own spring's
    # line (lever spring hole x 24.85) and hid the spring (r2 balloon pick);
    # 50 east put bar 3 over the bank spring (r4 balloon pick, shared edge).
    ExplodeStep("bars up", (BAR, BAR_PIN), "y", 50.0),
    # Each anchor's MHA-CH-012 jam nut goes down with it, then a further 30
    # off the shank's bottom. On the shank, the 6.66-diameter nut is under 1 mm
    # at 1:7 and shares the anchor's outline. 30 (3.5 mm on the sheet) orders
    # its balloon round the ring clear of the anchor's (ring replay).
    ExplodeStep("anchors down", (HOOK, ANCHOR_NUT), "y", -40.0),
    ExplodeStep("anchor nuts off the shank", (ANCHOR_NUT,), "y", -30.0),
    # Withdrawn past a keeper: in place only its 10 mm tips stand clear of the
    # lever hubs, under 1.5 mm at 1:7, and its balloon landed on lever 20's
    # ink (r4 balloon pick, shared edge). South, not north: withdrawn north its
    # balloon joined the lever-bank cluster at the top of the view and the ring
    # crossed leaders 2/17 and 8/10 (r6 layout audit); south it attaches out at
    # the right, which a replay of the r6 ring places clear of every leader.
    ExplodeStep("fulcrum shaft out south", (FULCRUM_SHAFT,), "z", -120.0),
    ExplodeStep("north-most channel out", _CHANNEL_GROUP, "z", 300.0, "north-most"),
    ExplodeStep("its pins out", (ROD_PIN, BAR_PIN), "z", 25.0, "north-most"),
    # Its bar and bar pin, coaxial still, 30 back down the 50 every bar went
    # up: at 50 the bar's balloon took the ring slot past its rod's and
    # leaders 12/13 crossed (r14 layout audit); the r14 ring replay clears
    # every pair from 10 to 40 down (at 45-50 the pin's leader meets 17's).
    ExplodeStep("its bar down", (BAR, BAR_PIN), "y", -30.0, "north-most"),
)
EXPLODED_STEMS = frozenset(stem for step in EXPLODE_STEPS for stem in step.stems)
# The families every instance of which moves (the channel's own move only
# its north-most instance).
FULLY_EXPLODED_STEMS = frozenset(
    stem for step in EXPLODE_STEPS if step.side != "north-most" for stem in step.stems
)


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
    by_family = [(family(instance.stem), instance) for instance in instances]
    missing = sorted(EXPLODED_STEMS - {stem for stem, _ in by_family})
    if missing:
        raise ValueError(f"explode families absent from the model: {missing!r}")
    plan = []
    for step in EXPLODE_STEPS:
        if step.side == "north-most":
            names = [
                max(
                    (instance for owner, instance in by_family if owner == stem),
                    key=lambda instance: instance.z_mm,
                ).name
                for stem in step.stems
            ]
            plan.append((step, tuple(sorted(names))))
            continue
        names = []
        moved = set()
        for stem, instance in by_family:
            if stem not in step.stems:
                continue
            south = instance.z_mm < BANK_MID_Z
            if step.side is None or (step.side == "south") == south:
                names.append(instance.name)
                moved.add(stem)
        if not names:
            raise ValueError(f"{step.label}: moves no instance")
        if step.side is not None and (
            moved != set(step.stems) or len(names) != len(step.stems)
        ):
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
    BRACKET_HOLD_DOWN: "#8-32 X 5/8 FILLISTER HEAD SCREW",
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
    ANCHOR_NUT: "#6-32 ROUND ANCHOR JAM NUT",
}
