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

# Families still arriving from a sibling branch, classified ahead of time so
# the integration head needs no plan edit; an absent pending family is not an
# error. Empty since the crank-hub cluster (MHA-137/138, #831) landed.
PENDING_STEMS: frozenset[str] = frozenset()
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
        "cone-tip-collar",
        "cone-tip-adjuster",
        "cone-tip-pinch-screw",
        "cone-tip-block-screw",
        "post-mount-screw",
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
        "crank-handle-pivot-screw",
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
        "pinion-strap-pin",
        "slotted-screw",
        "foot-screw",
    ),
}
Pick = Literal["south", "north"]
# A role singles out the one instance of a family that explodes apart from its
# siblings.  The builder tags it at insertion by what it is pinned to, never by
# where it stands, so a layout move cannot re-pick it.  MHA-145 serves both as
# the two strap set pins (stationary with the straps) and as the MHA-144 collar
# pin, which leaves with the arbor it pins.
Role = Literal["arbor-collar-pin"]
COLLAR_PIN_ROLE: Role = "arbor-collar-pin"


# The cone set's true axis, read off the post's journal: the rotor withdraws
# along the bore it turns in. The post is stationary, so the direction the
# steps are authored along never moves under them.
CONE_AXIS_SOURCE = ("cone-pivot-post", "journal axis")


@dataclass(frozen=True)
class ExplodeStep:
    """One native explode step: every instance of ``stems`` meeting ALL
    ``picks`` -- and, when ``roles`` is set, carrying one of them -- moves
    ``distance_mm`` along ``axis`` (sign = direction): a world axis, or
    ``"cone"``, the post journal's axis, positive toward the cone's tip."""

    label: str
    stems: tuple[str, ...]
    axis: Literal["x", "y", "z", "cone"]
    distance_mm: float
    picks: tuple[Pick, ...] = ()
    roles: tuple[Role, ...] = ()


# Machine frame: +Y up, -Z front (south), the drum arbor along Z. Every family
# not listed in a step stays put (STATIONARY): the drum stack, shafts, straps
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
    # cone set: base hardware up, swing plate down.  The rotor (shaft, gears,
    # the MHA-096 collar locked on it) withdraws north out of the post along
    # its own axis, so the MHA-014 journal stands clear of the post (user
    # ruling 2026-09-29: run 7's touching gears, collar and tip hardware left
    # no shaft face in view).  The journal is 43.011 long, so 50 leaves ~7 of
    # air south of it; the tip hardware goes 12 further, which clears the
    # 2.79 the tip runs into the block by ~9.
    ExplodeStep("swing plate drops", ("cone-swing-platform",), "y", -30.0),
    ExplodeStep("post mount screws lift", ("post-mount-screw",), "y", 100.0),
    ExplodeStep("pivot screw lifts", ("cone-pivot-screw",), "y", 35.0),
    ExplodeStep("lock knob lifts", ("cone-lock-knob",), "y", 30.0),
    # The withdrawn cone's upper silhouette covers a 25 lift: run
    # 20260929T174651337Z found no swing-stop-screw ink at any of 24 points
    # and anchored its balloon on cone-gear-5.  50 puts its head ~2.9 mm of
    # sheet (1:4) above that silhouette.
    ExplodeStep("swing stop lifts", ("swing-stop-screw",), "y", 50.0),
    ExplodeStep(
        "cone rotor withdraws",
        ("cone-gear-shaft", "cone-gear", "crank-drive-gear", "cone-tip-collar"),
        "cone",
        50.0,
    ),
    ExplodeStep(
        "tip block slides off",
        ("cone-tip-block", "cone-tip-adjuster", "cone-tip-pinch-screw"),
        "cone",
        62.0,
    ),
    ExplodeStep("tip pinch screw lifts", ("cone-tip-pinch-screw",), "y", 25.0),
    # MHA-140 comes down out of the dropped plate's counterbore: 50 carries
    # its tip ~7 below the plate's underside after the plate's 30.
    ExplodeStep("tip block screw drops", ("cone-tip-block-screw",), "y", -50.0),
    ExplodeStep("tip adjuster backs out", ("cone-tip-adjuster",), "cone", 30.0),
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
            "crank-handle-pivot-screw",
            "crank-hub",
            "crank-hub-pin",
        ),
        "z",
        -30.0,
    ),
    # MHA-139 rides out with the handle, then backs out of its bore: the tip
    # starts 9.0 past the handle's inboard end and the handle is ~58 long.
    ExplodeStep(
        "crank handle", ("crank-handle", "crank-handle-pivot-screw"), "z", -35.0
    ),
    ExplodeStep("handle screw backs out", ("crank-handle-pivot-screw",), "z", -80.0),
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
    # ...and so is the collar's MHA-145 spring pin.  The other two MHA-145
    # instances pin the straps to the torque shaft and stay with them.
    ExplodeStep(
        "arbor collar pin", ("pinion-strap-pin",), "z", -50.0, roles=(COLLAR_PIN_ROLE,)
    ),
    ExplodeStep("grip crossrod", ("pinion-handle",), "y", 25.0),
)

STATIONARY_STEMS = frozenset(
    {
        "cylinder-gear-shaft",
        "cylinder-gear",
        "cone-pivot-post",

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
if CONE_AXIS_SOURCE[0] not in STATIONARY_STEMS:
    raise AssertionError(f"the cone axis's owner {CONE_AXIS_SOURCE[0]!r} must stay put")


@dataclass(frozen=True)
class Instance:
    name: str
    stem: str
    origin_mm: tuple[float, float, float]
    role: Role | None = None


def classified_stems() -> frozenset[str]:
    return frozenset(stem for stems in CLUSTERS.values() for stem in stems)


def unclassified_stems(stems: Sequence[str]) -> list[str]:
    """Model families the plan does not know (or knows as retired)."""
    known = classified_stems()
    return sorted(
        {stem for stem in stems if stem not in known or stem in RETIRED_STEMS}
    )


def _picked(step: ExplodeStep, instance: Instance) -> bool:
    if step.roles and instance.role not in step.roles:
        return False
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
    (the machine is laid out about z = 0). A role step moves only the
    instances the builder tagged with its role; each role must be carried by
    exactly one instance, of a family that role's step names.
    """
    stems = {instance.stem for instance in instances}
    unknown = unclassified_stems(sorted(stems))
    if unknown:
        raise ValueError(f"explode plan does not classify {unknown!r}")
    role_stems: dict[Role, set[str]] = {}
    for step in EXPLODE_STEPS:
        for role in step.roles:
            role_stems.setdefault(role, set()).update(step.stems)
    for role, owners in role_stems.items():
        tagged = [instance for instance in instances if instance.role == role]
        if len(tagged) != 1 or tagged[0].stem not in owners:
            found = [(instance.name, instance.stem) for instance in tagged]
            raise ValueError(f"role {role!r} must tag one {sorted(owners)!r}, found {found!r}")
    stray = sorted(
        instance.name
        for instance in instances
        if instance.role is not None and instance.role not in role_stems
    )
    if stray:
        raise ValueError(f"instances carry roles no step moves: {stray!r}")

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
