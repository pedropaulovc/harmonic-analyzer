"""Pure contract shared by the paper-drive builder's explode and its drawing.

The MHA-PD-00 platen-and-support sheet balloons the bar, its column clamps,
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


@dataclass(frozen=True)
class ExplodeStep:
    """One native explode step: every instance of each member family moves
    ``distance_mm`` along the world ``axis`` (sign = direction)."""

    label: str
    stems: tuple[str, ...]
    axis: Literal["x", "y", "z"]
    distance_mm: float


EXPLODE_STEPS: tuple[ExplodeStep, ...] = (
    ExplodeStep("rack below the platen", ("pd-platen-rack",), "y", -35.0),
    ExplodeStep("guide screws forward", ("pd-vn-fillister-screw",), "z", -45.0),
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
            "pd-vn-clamp-screw",
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
    ExplodeStep("clamp screws forward", ("pd-vn-clamp-screw",), "z", -45.0),
)
# The platen carries the balloons in place.
STATIONARY_STEMS = frozenset({"pd-platen"})
# Every family the exploded sheet shows and balloons.
SHOWN_STEMS = STATIONARY_STEMS | frozenset(
    stem for step in EXPLODE_STEPS for stem in step.stems
)


@dataclass(frozen=True)
class Instance:
    name: str
    stem: str


def plan_explode(
    instances: Sequence[Instance],
) -> list[tuple[ExplodeStep, tuple[str, ...]]]:
    """Resolve every step to the component names it moves.

    Refuses a shown family the model lacks. Families outside ``SHOWN_STEMS``
    are never moved.
    """
    stems = {instance.stem for instance in instances}
    missing = sorted(SHOWN_STEMS - stems)
    if missing:
        raise ValueError(f"explode families absent from the model: {missing!r}")
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
