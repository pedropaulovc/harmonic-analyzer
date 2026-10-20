"""Pure contract shared by the magnifier builder's explode and its drawing.

MHA-MG-00 shows the wheel group and the lever group on their own exploded
sheets, each an isometric of ``MG_MAGNIFIER_EXPLODED`` with only its own
families shown. This module names that presentation, the ordered native steps
that open it, and the two family sets. Positions come from the opened model;
distances are presentation offsets, not dimensions. The bar, the pressed wheel
axle, the lever and the clamp on it never move, and neither does the lever
wire (the finished sheet balloons it).

Machine frame: +X west, +Y up, -Z front (the pen side). Standard Front is
rebased to the machine front, while the fitter package uses the preserved
``MG BACK-TOP-LEFT`` view from +X+Y+Z: the machine's back, above and west.
A part moved -Z draws up and right and passes BEHIND what it left; a part
moved +Z draws down and left, in front. Each part pushed off the front of the
axle therefore clears the wheel's outline by more than the wheel's projected
radius (about 0.58 R along the axle's sheet direction, 0.82 mm of sheet travel
per mm of Z), or the wheel hides it from its balloon.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, Sequence

from _simplified_names import simplified_name
from mg_output_fixture_geom import FIXTURE_YAW_RAD

EXPLODED_VIEW_NAME = "MG_MAGNIFIER_EXPLODED"
SOURCE_CONFIGURATION = "Default"


def exploded_view_name(configuration: str) -> str:
    """The named explode ``configuration`` owns: exploded-view names are unique
    per document, so ``Default Simplified``'s copy carries the suffix too.

    Here, not in ``_mg_magnifier_explode``, so the drawing reads it without
    importing the builder's COM chain (``_assembly_patterns`` -> ``_assembly``),
    whose part/assembly config reads would key the sheet on every part YAML."""
    if configuration == SOURCE_CONFIGURATION:
        return EXPLODED_VIEW_NAME
    if configuration == simplified_name(SOURCE_CONFIGURATION):
        return simplified_name(EXPLODED_VIEW_NAME)
    raise ValueError(
        f"{EXPLODED_VIEW_NAME}: no explode is authored in {configuration!r}"
    )


@dataclass(frozen=True)
class ExplodeStep:
    """One native explode step: each member moves ``distance_mm`` along the
    world ``axis`` (sign = direction). A member is a family stem (every
    instance moves) or ``"<stem>:<n>"`` (only that family's instance ``n``)."""

    label: str
    members: tuple[str, ...]
    axis: Literal["x", "y", "z"]
    distance_mm: float


def member_stem(member: str) -> str:
    return member.partition(":")[0]


# How far the fixture's thumb screw backs out of its spigot, along its axis.
FIXTURE_SCREW_TRAVEL = 20.0


EXPLODE_STEPS: tuple[ExplodeStep, ...] = (
    # Wheel group, the stack off the front of the axle, front first. Station d
    # (from the bar's front face, mg_wheel_group) after the move: spacer
    # 57-75.6, back washer 84, wheel mid-plane 100.6, then the drum, front
    # washer and nuts each at least 43 past the wheel mid-plane, where the
    # wheel no longer hides them.
    ExplodeStep("locknut off the axle", ("mg-vn-wheel-axle-nut:2",), "z", -152.0),
    ExplodeStep("nut off the axle", ("mg-vn-wheel-axle-nut:1",), "z", -141.0),
    ExplodeStep("front washer off", ("mg-vn-wheel-axle-front-washer",), "z", -131.0),
    ExplodeStep(
        "wheel off the axle", ("mg-magnifying-wheel", "mg-wheel-drum"), "z", -77.0
    ),
    ExplodeStep("drum off the spigot", ("mg-wheel-drum",), "z", -38.0),
    ExplodeStep("back washer off", ("mg-vn-wheel-axle-back-washer",), "z", -65.0),
    ExplodeStep("spacer off", ("mg-wheel-axle-spacer",), "z", -57.0),
    # The column clamp: the screws forward out of the bar, the arcs rearward.
    ExplodeStep("clamp screws forward", ("mg-vn-clamp-screw",), "z", -45.0),
    ExplodeStep(
        "clamp arcs rearward",
        ("sh-column-clamp-front", "sh-column-clamp-back"),
        "z",
        30.0,
    ),
    ExplodeStep("back arc rearward", ("sh-column-clamp-back",), "z", 30.0),
    # Lever group: the clamp's thumb screw up, the rod down out of the clamp
    # with the fixture still on it, the fixture's screw out of its spigot, the
    # bracket off the lever's east end and its screws forward off the flange.
    ExplodeStep("clamp thumb screw up", ("mg-vn-thumb-screw:1",), "y", 25.0),
    ExplodeStep(
        "rod and fixture down",
        ("mg-magnifying-vertical-rod", "mg-output-fixture", "mg-vn-thumb-screw:2"),
        "y",
        -45.0,
    ),
    # The spigot axis runs east and FIXTURE_YAW back (+Z) to lay the groove's
    # front tangent in the wheel plane (#1559), so the screw backs out along
    # it in two world steps; one -X step left it 8 mm off its tap's line.
    ExplodeStep(
        "fixture screw out",
        ("mg-vn-thumb-screw:2",),
        "x",
        -FIXTURE_SCREW_TRAVEL * math.cos(FIXTURE_YAW_RAD),
    ),
    ExplodeStep(
        "fixture screw out, back",
        ("mg-vn-thumb-screw:2",),
        "z",
        FIXTURE_SCREW_TRAVEL * math.sin(FIXTURE_YAW_RAD),
    ),
    ExplodeStep(
        "bracket off the lever",
        ("mg-magnifying-bracket", "mg-vn-magnifying-bracket-screw"),
        "x",
        -30.0,
    ),
    # Forward alone leaves the screws behind the bracket's arm on the sheet.
    ExplodeStep("bracket screws forward", ("mg-vn-magnifying-bracket-screw",), "z", -40.0),
    ExplodeStep("bracket screws up", ("mg-vn-magnifying-bracket-screw",), "y", 20.0),
)

# The families each exploded sheet shows and balloons; the stationary ones
# carry the moved parts' context.
WHEEL_GROUP_STEMS = frozenset(
    {
        "mg-wheel-bar",
        "sh-column-clamp-front",
        "sh-column-clamp-back",
        "mg-vn-clamp-screw",
        "mg-wheel-axle",
        "mg-wheel-axle-spacer",
        "mg-vn-wheel-axle-back-washer",
        "mg-magnifying-wheel",
        "mg-wheel-drum",
        "mg-vn-wheel-axle-front-washer",
        "mg-vn-wheel-axle-nut",
    }
)
LEVER_GROUP_STEMS = frozenset(
    {
        "mg-magnifying-lever",
        "mg-magnifying-bracket",
        "mg-vn-magnifying-bracket-screw",
        "mg-magnifying-clamp",
        "mg-vn-thumb-screw",
        "mg-magnifying-vertical-rod",
        "mg-output-fixture",
    }
)
# Shown on the finished isometric only: it spans both groups.
WIRE_STEM = "mg-vn-lever-wire"
SHOWN_STEMS = WHEEL_GROUP_STEMS | LEVER_GROUP_STEMS | {WIRE_STEM}
_moved = {member_stem(member) for step in EXPLODE_STEPS for member in step.members}
if not _moved <= WHEEL_GROUP_STEMS | LEVER_GROUP_STEMS:
    raise AssertionError(f"explode moves unshown families: {_moved}")
if any(
    {member_stem(member) for member in step.members} & WHEEL_GROUP_STEMS
    and {member_stem(member) for member in step.members} & LEVER_GROUP_STEMS
    for step in EXPLODE_STEPS
):
    raise AssertionError("an explode step moves both groups")


@dataclass(frozen=True)
class Instance:
    name: str
    stem: str


def _instance_number(name: str, stem: str) -> int | None:
    head, sep, tail = name.rpartition("-")
    if sep and head.casefold() == stem and tail.isdigit():
        return int(tail)
    return None


def plan_explode(
    instances: Sequence[Instance],
) -> list[tuple[ExplodeStep, tuple[str, ...]]]:
    """Resolve every step to the component names it moves.

    Refuses a shown family the model lacks and an instance member it does
    not have. Families outside ``SHOWN_STEMS`` are never moved.
    """
    stems = {instance.stem for instance in instances}
    missing = sorted(SHOWN_STEMS - stems)
    if missing:
        raise ValueError(f"explode families absent from the model: {missing!r}")
    plan = []
    for step in EXPLODE_STEPS:
        names: set[str] = set()
        for member in step.members:
            stem, _sep, number = member.partition(":")
            matched = [
                instance.name
                for instance in instances
                if instance.stem == stem
                and (not number or _instance_number(instance.name, stem) == int(number))
            ]
            if not matched:
                raise ValueError(f"{step.label}: no instance {member!r} in the model")
            names.update(matched)
        plan.append((step, tuple(sorted(names))))
    return plan
