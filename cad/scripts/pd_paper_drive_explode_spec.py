"""Pure contract shared by the paper-drive builder's explode and its drawing.

The MHA-PD-000 platen-and-support sheet balloons the bar, its column clamps,
the platen and everything that rides it on one exploded isometric. This
module names that presentation and the ordered native steps that open it.
Positions come from the opened model; distances are presentation offsets,
not dimensions. The transgear and the chain never move.

Machine frame: +Y up, -Z front (the paper side). The drawing's isometric
looks from the front-left-top, so a part raised in +Y or pushed rearward in
+Z draws above the parts in front of it, and a screw drawn forward in -Z
stands clear in front of its hole.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

EXPLODED_VIEW_NAME = "PAPER_DRIVE_EXPLODED"
SOURCE_CONFIGURATION = "Default"

# The fillister-screw family holds both the guide screws (heads in the
# platen's front counterbores) and the paper-clip screws. The builder tags
# every instance with the joint it makes, never by where it stands.
Role = Literal["guide-screw", "clip-screw"]
GUIDE_SCREW_ROLE: Role = "guide-screw"
CLIP_SCREW_ROLE: Role = "clip-screw"
ROLE_STEMS = frozenset({"vn-fillister-screw"})


@dataclass(frozen=True)
class ExplodeStep:
    """One native explode step: every instance of each ``(stem, role)`` member
    moves ``distance_mm`` along the world ``axis`` (sign = direction); a
    ``None`` role takes every instance of the family."""

    label: str
    members: tuple[tuple[str, Role | None], ...]
    axis: Literal["x", "y", "z"]
    distance_mm: float


EXPLODE_STEPS: tuple[ExplodeStep, ...] = (
    ExplodeStep("rack below the platen", (("pd-platen-rack", None),), "y", -35.0),
    ExplodeStep(
        "guide screws forward", (("vn-fillister-screw", GUIDE_SCREW_ROLE),), "z", -45.0
    ),
    ExplodeStep(
        "clips and paper forward",
        (
            ("pd-platen-clip", None),
            ("pd-platen-paper", None),
            ("vn-fillister-screw", CLIP_SCREW_ROLE),
        ),
        "z",
        -40.0,
    ),
    ExplodeStep(
        "clip screws forward", (("vn-fillister-screw", CLIP_SCREW_ROLE),), "z", -30.0
    ),
    ExplodeStep(
        "guides above the platen",
        (("pd-platen-guide", None), ("pd-guide-lock", None), ("vn-guide-lock-screw", None)),
        "y",
        110.0,
    ),
    ExplodeStep(
        "locks above the guides",
        (("pd-guide-lock", None), ("vn-guide-lock-screw", None)),
        "y",
        45.0,
    ),
    ExplodeStep("lock screws rearward", (("vn-guide-lock-screw", None),), "z", 35.0),
    ExplodeStep(
        "bar above the locks",
        (
            ("pd-support-bar", None),
            ("sh-column-clamp-front", None),
            ("sh-column-clamp-back", None),
            ("vn-clamp-screw", None),
        ),
        "y",
        200.0,
    ),
    ExplodeStep(
        "clamp arcs rearward",
        (("sh-column-clamp-front", None), ("sh-column-clamp-back", None)),
        "z",
        30.0,
    ),
    ExplodeStep("back arcs rearward", (("sh-column-clamp-back", None),), "z", 30.0),
    ExplodeStep("clamp screws forward", (("vn-clamp-screw", None),), "z", -45.0),
)
# The platen carries the balloons in place.
STATIONARY_STEMS = frozenset({"pd-platen"})
# Every family the exploded sheet shows and balloons.
SHOWN_STEMS = STATIONARY_STEMS | frozenset(
    stem for step in EXPLODE_STEPS for stem, _role in step.members
)


@dataclass(frozen=True)
class Instance:
    name: str
    stem: str
    role: Role | None = None


def plan_explode(
    instances: Sequence[Instance],
) -> list[tuple[ExplodeStep, tuple[str, ...]]]:
    """Resolve every step to the component names it moves.

    Refuses a shown family the model lacks, an instance of a role family
    without a role (or a role on any other family), and a step member that
    selects nothing. Families outside ``SHOWN_STEMS`` are never moved.
    """
    stems = {instance.stem for instance in instances}
    missing = sorted(SHOWN_STEMS - stems)
    if missing:
        raise ValueError(f"explode families absent from the model: {missing!r}")
    untagged = sorted(
        instance.name
        for instance in instances
        if (instance.stem in ROLE_STEMS) != (instance.role is not None)
    )
    if untagged:
        raise ValueError(f"role tags do not match the role families: {untagged!r}")
    resolved = []
    for step in EXPLODE_STEPS:
        names: list[str] = []
        for stem, role in step.members:
            picked = sorted(
                instance.name
                for instance in instances
                if instance.stem == stem and (role is None or instance.role == role)
            )
            if not picked:
                raise ValueError(
                    f"explode step {step.label!r} selects no {stem!r} ({role})"
                )
            names += picked
        resolved.append((step, tuple(sorted(names))))
    return resolved
