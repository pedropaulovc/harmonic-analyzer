"""Pure contract shared by the paper-drive builder's explode and its drawing.

One native presentation opens two groups. The MHA-PD-00 platen-and-support
sheet balloons the bar, its column clamps, the platen and everything that
rides it; the transgear-exploded sheet balloons the hanger arm, the disc
cluster on its pin and the knob stack on its shaft, each drawn apart along
its own axis. Each sheet shows only its own group, so the other group's moves
never reach it. This module names that presentation and the ordered native
steps that open it. Positions come from the opened model; distances are
presentation offsets, not dimensions. The chain, the hanger pivot stack, the
latch hook and the crank and spare wheels never move.

Machine frame: +Y up, -Z front (the paper side). Both sheets look from the
front-left-top isometric, so a part raised in +Y or pushed rearward in +Z
draws above the parts in front of it, and a screw drawn forward in -Z stands
clear in front of its hole. The transgear sheet draws two views of the same
presentation, the hanger and knob stack in one and the disc cluster in the
other, so each axis's parts spread along it in the order they go on: the
cup, plate screws, plate and dowels rearward of the arm, the knob stack
forward of it, and along the pin the pin and its shims rearward of the
rear bushing and the cluster forward of it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

EXPLODED_VIEW_NAME = "PAPER_DRIVE_EXPLODED"
SOURCE_CONFIGURATION = "Default"


@dataclass(frozen=True)
class ExplodeStep:
    """One native explode step: every instance of each member family, and
    each named instance, moves ``distance_mm`` along the world ``axis``
    (sign = direction)."""

    label: str
    stems: tuple[str, ...]
    axis: Literal["x", "y", "z"]
    distance_mm: float
    instances: tuple[str, ...] = ()


PLATEN_STEPS: tuple[ExplodeStep, ...] = (
    ExplodeStep("rack below the platen", ("pd-platen-rack",), "y", -35.0),
    ExplodeStep("guide screws forward", ("sh-vn-brass-fillister-screw",), "z", -45.0),
    ExplodeStep(
        "clips and paper forward",
        ("pd-platen-clip", "pd-platen-paper", "pd-vn-platen-clip-screw"),
        "z",
        -40.0,
    ),
    ExplodeStep("clip screws forward", ("pd-vn-platen-clip-screw",), "z", -30.0),
    ExplodeStep(
        "guides above the platen",
        ("pd-platen-guide", "pd-guide-lock", "pd-vn-guide-lock-screw"),
        "y",
        110.0,
    ),
    ExplodeStep(
        "locks above the guides", ("pd-guide-lock", "pd-vn-guide-lock-screw"), "y", 45.0
    ),
    ExplodeStep("lock screws rearward", ("pd-vn-guide-lock-screw",), "z", 35.0),
    ExplodeStep(
        "bar above the locks",
        (
            "pd-support-bar",
            "sh-column-clamp-front",
            "sh-column-clamp-back",
            "sh-vn-clamp-screw",
        ),
        "y",
        200.0,
    ),
    ExplodeStep(
        "clamp arcs rearward",
        ("sh-column-clamp-front", "sh-column-clamp-back"),
        "z",
        30.0,
    ),
    ExplodeStep("back arcs rearward", ("sh-column-clamp-back",), "z", 30.0),
    ExplodeStep("clamp screws forward", ("sh-vn-clamp-screw",), "z", -45.0),
)
# The platen carries the balloons in place.
STATIONARY_STEMS = frozenset({"pd-platen"})
# Every family the platen-and-support sheet shows and balloons.
SHOWN_STEMS = STATIONARY_STEMS | frozenset(
    stem for step in PLATEN_STEPS for stem in step.stems
)

# The mounted knob wheel; the crank wheel and the spare share its family.
KNOB_WHEEL_INSTANCE = "pd-transgear-removable-1"
# Gaps along each axis are a few millimetres between neighbours. The cluster
# and the knob stack are drawn in separate views, so a wide part (the 120T
# disc, the hub flange, the T24) never sits over the other axis's parts.
TRANSGEAR_STEPS: tuple[ExplodeStep, ...] = (
    # Knob shaft's rear: the cup off the journal, its cross pin out along
    # its own (machine X) axis toward -X, the side sheet 3's isometric sees.
    # Along +X the pin stood behind the plate's lower block: its balloon
    # anchor fell back to a listed edge and the leader landed on the block
    # (run 20261028T074113068Z, ENFORCE review r1-r3 gating on balloon 40).
    ExplodeStep(
        "knob cup rearward",
        ("pd-transgear-knob-cup", "pd-vn-transgear-knob-cup-pin"),
        "z",
        46.0,
    ),
    ExplodeStep(
        "cup pin out of the cup", ("pd-vn-transgear-knob-cup-pin",), "x", -22.0
    ),
    # The plate off the arm's rear face, its screws behind it and the two
    # locating dowels drawn out of the arm between them.  At 16 mm the
    # isometric drew the plate on the arm's top edge with the dowels hidden
    # under it (2026-10-27 ENFORCE review, r1, r2: balloon 20 landed on a
    # barely visible tip).  The 6 mm dowels, 1.7 proud, now stand about
    # 16 mm clear of the arm and 18 mm short of the plate.
    ExplodeStep(
        "arm plate rearward",
        ("pd-transgear-arm-plate", "pd-vn-transgear-arm-plate-screw"),
        "z",
        40.0,
    ),
    ExplodeStep(
        "plate screws rearward", ("pd-vn-transgear-arm-plate-screw",), "z", 24.0
    ),
    ExplodeStep(
        "plate dowels rearward",
        ("pd-vn-transgear-arm-plate-locating-pin",),
        "z",
        20.0,
    ),
    # The disc cluster along its pin, in the order it goes on, each part a
    # clear gap from the next (round 11 review: the pin, shims, rear bushing
    # and sleeve read as one stack): the pin rearward out of the arm (which
    # the cluster's view does not draw), the MHA-PD-VN-68 shims rearward off
    # the arm's front face, the MHA-PD-24 rear bushing in place, then the
    # sleeve with everything on it forward.  The pin's head is the view's
    # rearmost point, so its throw grows the view's projected box: at 12 mm
    # the ring stood 147.4 mm tall in a 147.0 mm field (round 12).
    ExplodeStep("pin rearward", ("pd-transgear-pin",), "z", 4.0),
    ExplodeStep("shims rearward", ("pd-vn-transgear-cluster-shim",), "z", 5.5),
    ExplodeStep(
        "cluster forward",
        (
            "pd-transgear-feed-pinion",
            "pd-rack-pinion",
            "pd-transgear-disc-hub",
            "pd-vn-transgear-disc-screw",
            "pd-transgear-front-bushing",
            "pd-vn-transgear-retaining-ring",
        ),
        "z",
        -6.0,
    ),
    ExplodeStep(
        "disc off the sleeve",
        (
            "pd-rack-pinion",
            "pd-transgear-disc-hub",
            "pd-vn-transgear-disc-screw",
            "pd-transgear-front-bushing",
            "pd-vn-transgear-retaining-ring",
        ),
        "z",
        -20.0,
    ),
    ExplodeStep(
        "hub off the disc",
        (
            "pd-transgear-disc-hub",
            "pd-vn-transgear-disc-screw",
            "pd-transgear-front-bushing",
            "pd-vn-transgear-retaining-ring",
        ),
        "z",
        -18.0,
    ),
    ExplodeStep("disc screws forward", ("pd-vn-transgear-disc-screw",), "z", -14.0),
    ExplodeStep(
        "front bushing forward",
        ("pd-transgear-front-bushing", "pd-vn-transgear-retaining-ring"),
        "z",
        -18.0,
    ),
    ExplodeStep("ring forward", ("pd-vn-transgear-retaining-ring",), "z", -10.0),
    # The knob stack's front off the shaft's stud: collar with its drive
    # dowels, then the knob wheel, then the thumbnut.
    ExplodeStep(
        "drive collar forward",
        (
            "pd-transgear-drive-collar",
            "pd-vn-transgear-knob-drive-pin",
            "pd-transgear-thumbnut",
        ),
        "z",
        -30.0,
        instances=(KNOB_WHEEL_INSTANCE,),
    ),
    ExplodeStep(
        "knob wheel forward",
        ("pd-transgear-thumbnut",),
        "z",
        -26.0,
        instances=(KNOB_WHEEL_INSTANCE,),
    ),
    ExplodeStep("thumbnut forward", ("pd-transgear-thumbnut",), "z", -20.0),
)
# The arm, its pressed latch pin, the cluster's rear bushing and the knob
# shaft with its thrust ring stay put; the moved parts read against them.
TRANSGEAR_STATIONARY_STEMS = frozenset(
    {
        "pd-transgear-arm",
        "pd-vn-transgear-latch-pin",
        "pd-transgear-rear-bushing",
        "pd-transgear-knob-shaft",
        "pd-transgear-knob-thrust-ring",
    }
)
# Every family the transgear-exploded sheet shows and balloons (the knob
# wheel by its one instance).
TRANSGEAR_SHOWN_STEMS = (
    TRANSGEAR_STATIONARY_STEMS
    | frozenset(stem for step in TRANSGEAR_STEPS for stem in step.stems)
    | frozenset({"pd-transgear-removable"})
)

EXPLODE_STEPS: tuple[ExplodeStep, ...] = PLATEN_STEPS + TRANSGEAR_STEPS


@dataclass(frozen=True)
class Instance:
    name: str
    stem: str


def plan_explode(
    instances: Sequence[Instance],
) -> list[tuple[ExplodeStep, tuple[str, ...]]]:
    """Resolve every step to the component names it moves.

    Refuses a shown family or a named instance the model lacks. Families
    outside both shown groups are never moved.
    """
    stems = {instance.stem for instance in instances}
    names = {instance.name for instance in instances}
    missing = sorted((SHOWN_STEMS | TRANSGEAR_SHOWN_STEMS) - stems)
    if missing:
        raise ValueError(f"explode families absent from the model: {missing!r}")
    absent = sorted({name for step in EXPLODE_STEPS for name in step.instances} - names)
    if absent:
        raise ValueError(f"explode instances absent from the model: {absent!r}")
    return [
        (
            step,
            tuple(
                sorted(
                    instance.name
                    for instance in instances
                    if instance.stem in step.stems or instance.name in step.instances
                )
            ),
        )
        for step in EXPLODE_STEPS
    ]
