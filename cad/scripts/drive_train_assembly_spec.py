"""Pure contract shared by the drive-train builder's explode and its drawing.

Everything here is presentation topology, never geometry: which component
family belongs to which drawing cluster, and the ordered explode steps that
separate the families for the exploded cluster sheets. Positions come from the
opened model; distances are presentation offsets, not dimensions.

Drawing wording (BOM descriptions, steps, checks) stays in the drawing script so
a wording change never enters the native assembly rebuild closure.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

EXPLODED_VIEW_NAME = "DRIVE_TRAIN_EXPLODED"
SOURCE_CONFIGURATION = "Default"

# Families still arriving from a sibling branch (crank-hub cluster MHA-137/138,
# #831). They are classified now so the integration head needs no plan edit;
# an absent pending family is not an error.
PENDING_STEMS = frozenset({"crank-hub", "crank-hub-pin"})
# Retired by the integral-arbor ruling (U11); refused if it reappears.
RETIRED_STEMS = frozenset({"pinion-handle-pin"})

Cluster = Literal["cylinder-bank", "cone-crank", "pinion-rig"]
CLUSTERS: dict[Cluster, tuple[str, ...]] = {
    "cylinder-bank": (
        "cylinder-gear-shaft",
        "arbor-pedestal",
        "cylinder-end-disc",
        "cylinder-gear",
        "pedestal-hold-down-screw",
        "arbor-set-screw",
    ),
    "cone-crank": (
        "cone-gear-shaft",
        "cone-gear",
        "crank-drive-gear",
        "cone-swing-platform",
        "cone-pivot-post",
        "cone-tip-block",
        "cone-tip-bushing",
        "cone-tip-adjuster",
        "cone-tip-pinch-screw",
        "cone-lock-knob",
        "cone-pivot-screw",
        "swing-stop-screw",
        "crankshaft",
        "crank-pinion",
        "crank-pinion-pin",
        "crank-arm",
        "crank-pin",
        "crank-pin-ring",
        "crank-pin-eye",
        "fillister-screw",
        "crank-handle",
        "crank-hub",
        "crank-hub-pin",
    ),
    "pinion-rig": (
        "alignment-pinion",
        "pinion-bracket",
        "pinion-pivot-block",
        "pinion-pivot-shaft",
        "pinion-lift-rod",
        "pinion-spring",
        "pinion-cam-pin",
        "pinion-cam",
        "pinion-lever",
        "pinion-lever-pin",
        "pinion-handle",
        "pinion-arbor",
        "pinion-arbor-collar",
        "slotted-screw",
        "foot-screw",
    ),
}
Pick = Literal["south", "north"]


@dataclass(frozen=True)
class ExplodeStep:
    """One native explode step: every instance of ``stems`` meeting ALL
    ``picks`` moves ``distance_mm`` along the world ``axis`` (sign = direction)."""

    label: str
    stems: tuple[str, ...]
    axis: Literal["x", "y", "z"]
    distance_mm: float
    picks: tuple[Pick, ...] = ()


# Machine frame: +Y up, -Z front (south), the drum arbor along Z. Every family
# not listed in a step stays put (STATIONARY): the gear stacks, shafts, straps
# and castings carry the balloons in place; only what hides or overlaps moves.
EXPLODE_STEPS: tuple[ExplodeStep, ...] = (
    # cylinder bank: slide the retention stack off each end of the arbor
    ExplodeStep(
        "south pedestal",
        ("arbor-pedestal", "pedestal-hold-down-screw", "arbor-set-screw"),
        "z",
        -35.0,
        ("south",),
    ),
    ExplodeStep(
        "north pedestal",
        ("arbor-pedestal", "pedestal-hold-down-screw", "arbor-set-screw"),
        "z",
        35.0,
        ("north",),
    ),
    ExplodeStep("south thrust washer", ("cylinder-end-disc",), "z", -15.0, ("south",)),
    ExplodeStep("north thrust washer", ("cylinder-end-disc",), "z", 15.0, ("north",)),
    ExplodeStep("pedestal screws lift", ("pedestal-hold-down-screw",), "y", 30.0),
    ExplodeStep("apex set screws lift", ("arbor-set-screw",), "y", 20.0),
    # cone set: base hardware up, swing plate down
    ExplodeStep("swing plate drops", ("cone-swing-platform",), "y", -30.0),
    ExplodeStep("pivot screw lifts", ("cone-pivot-screw",), "y", 35.0),
    ExplodeStep("lock knob lifts", ("cone-lock-knob",), "y", 30.0),
    ExplodeStep("swing stop lifts", ("swing-stop-screw",), "y", 25.0),
    ExplodeStep("tip pinch screw lifts", ("cone-tip-pinch-screw",), "y", 25.0),
    ExplodeStep("tip adjuster backs out", ("cone-tip-adjuster",), "z", 30.0),
    # crank: the arm group comes off the crankshaft's front end
    ExplodeStep(
        "crank arm group",
        (
            "crank-arm",
            "crank-pin",
            "crank-pin-ring",
            "crank-pin-eye",
            "fillister-screw",
            "crank-handle",
            "crank-hub",
            "crank-hub-pin",
        ),
        "z",
        -30.0,
    ),
    ExplodeStep("crank handle", ("crank-handle",), "z", -35.0),
    ExplodeStep("taper pin", ("crank-pin", "crank-pin-ring"), "x", -25.0),
    ExplodeStep("anchor screw", ("fillister-screw",), "z", -20.0),
    ExplodeStep("anchor eyelet", ("crank-pin-eye",), "z", -10.0),
    # alignment pinion rig
    ExplodeStep("block screws lift", ("slotted-screw",), "y", 30.0),
    ExplodeStep("spring foot screw lifts", ("foot-screw",), "y", 25.0),
    ExplodeStep("pinion lever", ("pinion-lever", "pinion-lever-pin"), "z", -40.0),
    # The MHA-144 collar is pinned to the arbor, so it comes out with it.
    ExplodeStep(
        "pinion arbor",
        ("pinion-arbor", "pinion-arbor-collar", "pinion-handle"),
        "z",
        -50.0,
    ),
    ExplodeStep("grip crossrod", ("pinion-handle",), "y", 25.0),
)

STATIONARY_STEMS = frozenset(
    {
        "cylinder-gear-shaft",
        "cylinder-gear",
        "cone-gear-shaft",
        "cone-gear",
        "crank-drive-gear",
        "cone-pivot-post",
        "cone-tip-block",
        "cone-tip-bushing",
        "crankshaft",
        "crank-pinion",
        "crank-pinion-pin",
        "alignment-pinion",
        "pinion-bracket",
        "pinion-pivot-block",
        "pinion-pivot-shaft",
        "pinion-lift-rod",
        "pinion-spring",
        "pinion-cam-pin",
        "pinion-cam",
    }
)

@dataclass(frozen=True)
class Instance:
    name: str
    stem: str
    origin_mm: tuple[float, float, float]


def classified_stems() -> frozenset[str]:
    return frozenset(stem for stems in CLUSTERS.values() for stem in stems)


def unclassified_stems(stems: Sequence[str]) -> list[str]:
    """Model families the plan does not know (or knows as retired)."""
    known = classified_stems()
    return sorted(
        {stem for stem in stems if stem not in known or stem in RETIRED_STEMS}
    )


def _picked(step: ExplodeStep, instance: Instance) -> bool:
    z = instance.origin_mm[2]
    tests = {"south": z < 0.0, "north": z > 0.0}
    return all(tests[pick] for pick in step.picks)


def plan_explode(
    instances: Sequence[Instance],
) -> list[tuple[ExplodeStep, tuple[str, ...]]]:
    """Resolve every step to the component names it moves.

    Refuses an unknown or retired family, a moving family no step moves, a
    step that selects nothing, and a non-pending family a step names but the
    model lacks. The south/north picks split each paired family by world z
    (the machine is laid out about z = 0).
    """
    stems = {instance.stem for instance in instances}
    unknown = unclassified_stems(sorted(stems))
    if unknown:
        raise ValueError(f"explode plan does not classify {unknown!r}")

    moved_stems = {stem for step in EXPLODE_STEPS for stem in step.stems}
    unplanned = sorted(stems - moved_stems - STATIONARY_STEMS)
    if unplanned:
        raise ValueError(f"families neither exploded nor stationary: {unplanned!r}")
    overlap = sorted(moved_stems & STATIONARY_STEMS)
    if overlap:
        raise ValueError(f"families both exploded and stationary: {overlap!r}")
    missing = sorted((moved_stems | STATIONARY_STEMS) - stems - PENDING_STEMS)
    if missing:
        raise ValueError(f"planned families absent from the model: {missing!r}")

    resolved = []
    for step in EXPLODE_STEPS:
        names = tuple(
            sorted(
                instance.name
                for instance in instances
                if instance.stem in step.stems and _picked(step, instance)
            )
        )
        if not names:
            raise ValueError(f"explode step {step.label!r} selects nothing")
        resolved.append((step, names))
    return resolved


def cluster_members(
    instances: Sequence[Instance],
) -> dict[Cluster, tuple[str, ...]]:
    """Component names per drawing cluster; every family sits in exactly one."""
    members: dict[Cluster, list[str]] = {cluster: [] for cluster in CLUSTERS}
    for instance in instances:
        owners = [c for c, stems in CLUSTERS.items() if instance.stem in stems]
        if not owners:
            raise ValueError(f"{instance.name}: family {instance.stem!r} has no cluster")
        if len(owners) != 1:
            raise ValueError(f"{instance.name}: family in clusters {owners!r}")
        members[owners[0]].append(instance.name)
    return {cluster: tuple(sorted(names)) for cluster, names in members.items()}
