"""Pure contract shared by the drive-train builder's explode and its drawing.

Everything here is presentation topology, never geometry: which component
family belongs to which drawing cluster, and the ordered explode steps that
separate the families for the exploded cluster sheets. Positions come from the
opened model; distances are presentation offsets, not dimensions.

Drawing wording (BOM descriptions, steps, checks), the sheets' fit-limit
rounding and the per-cluster member split stay in the drawing script, so a
sheet change never enters the native assembly rebuild closure.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

EXPLODED_VIEW_NAME = "DRIVE_TRAIN_EXPLODED"
SOURCE_CONFIGURATION = "Default"

# Families still arriving from a sibling branch, classified ahead of time so
# the integration head needs no plan edit; an absent pending family is not an
# error. Empty since the crank-hub cluster (MHA-DT-31/138, #831) landed.
PENDING_STEMS: frozenset[str] = frozenset()
# Retired by the integral-arbor ruling (U11); refused if it reappears.
RETIRED_STEMS = frozenset({"pinion-handle-pin"})

# The cone set and the crank are separate sheets: on one 1:4 view their 31
# balloons converged at the crank column and the tip block (machinist review of
# 9ebf51696, sheet 4 clarity finding).
Cluster = Literal["cylinder-bank", "cone-set", "crank", "pinion-rig"]
CLUSTERS: dict[Cluster, tuple[str, ...]] = {
    "cylinder-bank": (
        "dt-cylinder-gear-shaft",
        "dt-arbor-pedestal",
        "dt-cylinder-end-disc",
        "dt-vn-cylinder-bank-spring",
        "dt-cylinder-gear",
        "dt-vn-pedestal-hold-down-screw",
        "dt-vn-arbor-set-screw",
    ),
    "cone-set": (
        "dt-cone-gear-shaft",
        "dt-cone-gear",
        "dt-crank-drive-gear",
        "dt-cone-swing-platform",
        "dt-cone-pivot-post",
        "dt-cone-tip-block",
        "dt-vn-cone-tip-collar",
        "dt-vn-cone-tip-adjuster",
        "dt-vn-cone-tip-pinch-screw",
        "dt-vn-cone-tip-block-screw",
        "dt-vn-post-mount-screw",
        "dt-vn-cone-lock-knob",
        "dt-vn-cone-pivot-screw",
        "dt-vn-swing-stop-screw",
    ),
    "crank": (
        "dt-crankshaft",
        "dt-crank-pinion",
        "dt-crank-pinion-pin",
        "dt-crank-arm",
        "dt-crank-pin",
        "dt-crank-pin-ring",
        "dt-crank-pin-eye",
        "dt-vn-keeper-chain",
        "dt-vn-keeper-chain-link",
        "dt-vn-fillister-screw",
        "dt-crank-handle",
        "dt-crank-handle-ferrule",
        "dt-crank-handle-butt-cup",
        "dt-crank-handle-pivot-screw",
        "dt-crank-hub",
        "dt-vn-crank-hub-pin",
        "dt-vn-crank-seat-drive-pin",
    ),
    "pinion-rig": (
        "dt-alignment-pinion",
        "dt-pinion-bracket",
        "dt-pinion-pivot-block",
        "dt-pinion-pivot-shaft",
        "dt-pinion-lift-rod",
        "dt-pinion-spring",
        "dt-pinion-cam-pin",
        "dt-pinion-cam",
        "dt-pinion-lever",
        "dt-pinion-lever-pin",
        "dt-pinion-handle",
        "dt-pinion-arbor",
        "dt-pinion-arbor-collar",
        "dt-vn-pinion-strap-pin",
        "dt-vn-slotted-screw",
        "dt-vn-foot-screw",
    ),
}
Pick = Literal["south", "north"]
# A role singles out the one instance of a family that explodes apart from its
# siblings.  The builder tags it at insertion by what it is pinned to, never by
# where it stands, so a layout move cannot re-pick it.  MHA-DT-VN-63 serves both as
# the two strap set pins (stationary with the straps) and as the MHA-DT-33 collar
# pin, which leaves with the arbor it pins.
Role = Literal["arbor-collar-pin"]
COLLAR_PIN_ROLE: Role = "arbor-collar-pin"


# The cone set's true axis, read off the post's journal: the rotor withdraws
# along the bore it turns in. The post is stationary, so the direction the
# steps are authored along never moves under them.
CONE_AXIS_SOURCE = ("dt-cone-pivot-post", "journal axis")


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
        ("dt-arbor-pedestal", "dt-vn-pedestal-hold-down-screw", "dt-vn-arbor-set-screw"),
        "z",
        -35.0,
        ("south",),
    ),
    ExplodeStep(
        "north pedestal",
        ("dt-arbor-pedestal", "dt-vn-pedestal-hold-down-screw", "dt-vn-arbor-set-screw"),
        "z",
        35.0,
        ("north",),
    ),
    ExplodeStep("south thrust washer", ("dt-cylinder-end-disc",), "z", -15.0, ("south",)),
    # MHA-DT-VN-68 (#948 ruling R) sits between the front strap and the front
    # washer: it stops between their exploded stations.
    ExplodeStep("bank spring", ("dt-vn-cylinder-bank-spring",), "z", -25.0),
    ExplodeStep("north thrust washer", ("dt-cylinder-end-disc",), "z", 15.0, ("north",)),
    ExplodeStep("pedestal screws lift", ("dt-vn-pedestal-hold-down-screw",), "y", 30.0),
    ExplodeStep("apex set screws lift", ("dt-vn-arbor-set-screw",), "y", 20.0),
    # cone set: base hardware up, swing plate down.  The rotor (shaft, gears,
    # the MHA-DT-VN-54 collar locked on it) withdraws north out of the post along
    # its own axis, so the MHA-DT-04 journal stands clear of the post (user
    # ruling 2026-09-29: run 7's touching gears, collar and tip hardware left
    # no shaft face in view). The rotor travels farther than the current journal
    # length; the tip hardware leads it far enough to clear the tip's embed in
    # the block (both checked against the live shaft spec offline).
    ExplodeStep("swing plate drops", ("dt-cone-swing-platform",), "y", -30.0),
    # The MHA-DT-VN-61 pair sets the cone-set sheet's top: lifted 100 (their
    # 94.9 length clear of the post) its 1:3 balloon ring read 176.6 mm tall
    # against the region's 176.0 (r4, 20261018T074844468Z). 88 leaves the
    # lower 7 of each below its seated top end, the rest standing clear.
    ExplodeStep("post mount screws lift", ("dt-vn-post-mount-screw",), "y", 88.0),
    ExplodeStep("pivot screw lifts", ("dt-vn-cone-pivot-screw",), "y", 35.0),
    ExplodeStep("lock knob lifts", ("dt-vn-cone-lock-knob",), "y", 30.0),
    # The withdrawn cone's upper silhouette covers a 25 lift: run
    # 20260929T174651337Z found no swing-stop-screw ink at any of 24 points
    # and anchored its balloon on cone-gear-5.  At 50 the 1:3 sheet still
    # showed only a head sliver there (#1687 r6 and DtPinionLeverPin r2,
    # balloon 16); 75 stands the head 8 mm of sheet higher, below the
    # MHA-DT-VN-61 heads that set the sheet's top.
    ExplodeStep("swing stop lifts", ("dt-vn-swing-stop-screw",), "y", 75.0),
    ExplodeStep(
        "cone rotor withdraws",
        ("dt-cone-gear-shaft", "dt-cone-gear", "dt-crank-drive-gear", "dt-vn-cone-tip-collar"),
        "cone",
        50.0,
    ),
    # The MHA-DT-VN-54 collar then slips off the tip stub past the shaft's end,
    # and the tip block hardware stands clear beyond it (#1121): the collar's
    # 11.5 width sat on the last 18.4 of the stub, the block 3.7 past it, so 20
    # puts the collar 1.6 past the tip and the block 18.7 past the collar.
    ExplodeStep("tip collar slips off", ("dt-vn-cone-tip-collar",), "cone", 20.0),
    ExplodeStep(
        "tip block slides off",
        ("dt-cone-tip-block", "dt-vn-cone-tip-adjuster", "dt-vn-cone-tip-pinch-screw"),
        "cone",
        85.0,
    ),
    # The cone gears then slide on toward the tip, leaving MHA-DT-07 alone on
    # the MHA-DT-04 collar: unexploded, its balloon and the cone gear's met on
    # the stack's first disc (r15, 20261018T215310765Z, balloons 35 and 36).
    # 6.9 of stub still stands past the tip gear; MHA-DT-VN-54 goes with the
    # gears, ending 6.7 short of the tip block.
    ExplodeStep(
        "cone gears slide toward the tip",
        ("dt-cone-gear", "dt-vn-cone-tip-collar"),
        "cone",
        12.0,
    ),
    ExplodeStep("tip pinch screw lifts", ("dt-vn-cone-tip-pinch-screw",), "y", 25.0),
    # MHA-DT-VN-60 comes down out of the dropped plate's counterbore: 50 carries
    # its tip ~7 below the plate's underside after the plate's 30.
    ExplodeStep("tip block screw drops", ("dt-vn-cone-tip-block-screw",), "y", -50.0),
    ExplodeStep("tip adjuster backs out", ("dt-vn-cone-tip-adjuster",), "cone", 30.0),
    # crank, step 4 order: the MHA-DT-10 pinion slides north off the
    # crankshaft with its MHA-DT-29 cross pin, which then drives out of the
    # boss along its own (pinion-local X, 14 deg off world X) axis; the two
    # MHA-DT-VN-67 come south out of the collar holes.
    ExplodeStep(
        "crank pinion slides off", ("dt-crank-pinion", "dt-crank-pinion-pin"), "z", 35.0
    ),
    ExplodeStep("pinion pin drives out", ("dt-crank-pinion-pin",), "x", -20.0),
    ExplodeStep("crank drive pins", ("dt-vn-crank-seat-drive-pin",), "z", -12.0),
    # step 6: the arm group comes off the crankshaft's front end
    ExplodeStep(
        "crank arm group",
        (
            "dt-crank-arm",
            "dt-crank-pin",
            "dt-crank-pin-ring",
            "dt-crank-pin-eye",
            "dt-vn-keeper-chain",
            "dt-vn-keeper-chain-link",
            "dt-vn-fillister-screw",
            "dt-crank-handle",
            "dt-crank-handle-ferrule",
            "dt-crank-handle-butt-cup",
            "dt-crank-handle-pivot-screw",
            "dt-crank-hub",
            "dt-vn-crank-hub-pin",
        ),
        "z",
        -30.0,
    ),
    # MHA-DT-32 rides out with the handle and its bonded ferrule and cup, then
    # backs out of its bore: the handle is ~58 long.
    ExplodeStep(
        "crank handle",
        (
            "dt-crank-handle",
            "dt-crank-handle-ferrule",
            "dt-crank-handle-butt-cup",
            "dt-crank-handle-pivot-screw",
        ),
        "z",
        -35.0,
    ),
    ExplodeStep("handle screw backs out", ("dt-crank-handle-pivot-screw",), "z", -80.0),
    # The keeper chain stays tied to the pin: pin, ring, chain and links come
    # out together, then the chain drops clear of the arm.
    ExplodeStep(
        "taper pin",
        ("dt-crank-pin", "dt-crank-pin-ring", "dt-vn-keeper-chain", "dt-vn-keeper-chain-link"),
        "x",
        -25.0,
    ),
    ExplodeStep("keeper chain", ("dt-vn-keeper-chain", "dt-vn-keeper-chain-link"), "y", -20.0),
    ExplodeStep("anchor screw", ("dt-vn-fillister-screw",), "z", -35.0),
    ExplodeStep("anchor eyelet", ("dt-crank-pin-eye",), "z", -18.0),
    # MHA-DT-VN-59 comes forward out of the arm/hub seam, past the anchor screw
    # head (#1121): it sits 11 from the screw axis.
    ExplodeStep("hub seam pin", ("dt-vn-crank-hub-pin",), "z", -55.0),
    # alignment pinion rig, steps 15-18 order: the base-mounted MHA-DT-18 pair
    # and MHA-DT-24 drop with their screws, then the screws lift out of them;
    # the lift rod, its cams and the lever drop out of the MHA-DT-18 lift
    # bores to stand between the straps and the blocks (machinist review of
    # 9ebf51696, sheet 5 clarity finding). The straps stay hung on the pivot
    # shaft with their pins.
    ExplodeStep(
        "pivot blocks drop",
        (
            "dt-pinion-pivot-block",
            "dt-vn-slotted-screw",
            "dt-pinion-spring",
            "dt-vn-foot-screw",
        ),
        "y",
        -50.0,
    ),
    ExplodeStep(
        "lift rod drops",
        (
            "dt-pinion-lift-rod",
            "dt-pinion-cam",
            "dt-pinion-lever",
            "dt-pinion-lever-pin",
        ),
        "y",
        -22.0,
    ),
    ExplodeStep("block screws lift", ("dt-vn-slotted-screw",), "y", 30.0),
    # In the iso, MHA-DT-VN-58 stood 0.4 behind the back block's east MHA-DT-VN-57
    # shank (DtPinionLeverPin r2, 20261019T012255621Z, balloon 32): MHA-DT-24
    # and its screw step east off the strap, the blade ~7 clear of the block's
    # north-east corner in the view, then the screw lifts out of the foot.
    ExplodeStep("spring steps east", ("dt-pinion-spring", "dt-vn-foot-screw"), "x", -30.0),
    ExplodeStep("spring foot screw lifts", ("dt-vn-foot-screw",), "y", 25.0),
    ExplodeStep("pinion lever", ("dt-pinion-lever", "dt-pinion-lever-pin"), "z", -40.0),
    # The MHA-DT-33 collar is pinned to the arbor, so it comes out with it.
    ExplodeStep(
        "pinion arbor",
        ("dt-pinion-arbor", "dt-pinion-arbor-collar", "dt-pinion-handle"),
        "z",
        -50.0,
    ),
    # ...and so is the collar's MHA-DT-VN-63 spring pin.  The other two MHA-DT-VN-63
    # instances pin the straps to the torque shaft and stay with them.
    ExplodeStep(
        "arbor collar pin", ("dt-vn-pinion-strap-pin",), "z", -50.0, roles=(COLLAR_PIN_ROLE,)
    ),
    ExplodeStep("grip crossrod", ("dt-pinion-handle",), "y", 25.0),
)

STATIONARY_STEMS = frozenset(
    {
        "dt-cylinder-gear-shaft",
        "dt-cylinder-gear",
        "dt-cone-pivot-post",
        "dt-crankshaft",
        "dt-alignment-pinion",
        "dt-pinion-bracket",
        "dt-pinion-pivot-shaft",
        "dt-pinion-cam-pin",
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
