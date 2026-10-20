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
``ISO MG BACK-TOP-LEFT`` view from +X+Y+Z: the machine's back, above and west.
A part moved -Z draws up and right and passes BEHIND what it left; a part
moved +Z draws down and left, in front. Each part pushed off the front of the
axle therefore clears the wheel's outline by more than the wheel's projected
radius (about 0.58 R along the axle's sheet direction, 0.82 mm of sheet travel
per mm of Z), or the wheel hides it from its balloon.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Literal, Mapping, Sequence

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
    ExplodeStep("clamp screws forward", ("sh-vn-clamp-screw",), "z", -45.0),
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
    ExplodeStep("clamp thumb screw up", ("sh-vn-thumb-screw:1",), "y", 25.0),
    ExplodeStep(
        "rod and fixture down",
        ("mg-magnifying-vertical-rod", "mg-output-fixture", "sh-vn-thumb-screw:2"),
        "y",
        -45.0,
    ),
    # The spigot axis runs east and FIXTURE_YAW back (+Z) to lay the groove's
    # front tangent in the wheel plane (#1559), so the screw backs out along
    # it in two world steps; one -X step left it 8 mm off its tap's line.
    ExplodeStep(
        "fixture screw out",
        ("sh-vn-thumb-screw:2",),
        "x",
        -FIXTURE_SCREW_TRAVEL * math.cos(FIXTURE_YAW_RAD),
    ),
    ExplodeStep(
        "fixture screw out, back",
        ("sh-vn-thumb-screw:2",),
        "z",
        FIXTURE_SCREW_TRAVEL * math.sin(FIXTURE_YAW_RAD),
    ),
    ExplodeStep(
        "bracket unthreaded then withdrawn from the lever",
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
        "sh-vn-clamp-screw",
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
        "sh-vn-thumb-screw",
        "mg-magnifying-vertical-rod",
        "mg-output-fixture",
    }
)
# Shown on the finished isometric only: it spans both groups.
WIRE_STEM = "sh-vn-music-wire"
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


def explode_offsets_property(configuration: str) -> str:
    """File-level native-readback metadata, separate for each owned explode."""
    return f"{exploded_view_name(configuration)} Offsets"


def explode_contract_fingerprint(instances: Sequence[Instance]) -> str:
    """Bind metadata to the current recipe and its resolved instance membership.

    This detects stale recipe readbacks, including same-count changes. It does
    not establish that an externally edited native explode still matches them.
    """
    contract = {
        "instances": sorted(
            (instance.name.replace("\\", "/").casefold(), instance.stem)
            for instance in instances
        ),
        "steps": [
            {
                "label": step.label,
                "members": step.members,
                "axis": step.axis,
                "distance_mm": step.distance_mm,
                "instances": sorted(
                    name.replace("\\", "/").casefold() for name in names
                ),
            }
            for step, names in plan_explode(instances)
        ],
    }
    encoded = json.dumps(
        contract, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _checked_offset_rows(
    rows: object, instances: Sequence[str]
) -> dict[str, tuple[float, float, float]]:
    expected = {name.replace("\\", "/").casefold() for name in instances}
    if not expected or "" in expected or len(expected) != len(instances):
        raise ValueError("component instance identities are empty or duplicated")
    if not isinstance(rows, dict) or set(rows) != expected:
        raise ValueError("offset instance identities do not match the source")
    offsets = {}
    for name, vector in rows.items():
        if (
            not isinstance(vector, (list, tuple))
            or len(vector) != 3
            or any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                for value in vector
            )
        ):
            raise ValueError(f"{name!r} has no finite three-axis translation")
        offsets[name] = (float(vector[0]), float(vector[1]), float(vector[2]))
    return offsets


def encode_explode_offsets(
    configuration: str,
    offsets: Mapping[str, Sequence[float]],
    instances: Sequence[Instance],
) -> str:
    """Persist measured native world translations, never recipe estimates.

    The author verifies every instance, including stationary ones, before its
    normal source save. File-level text avoids a configuration activation when
    the drawing consumes that immutable readback.
    """
    rows = {
        name.replace("\\", "/").casefold(): vector for name, vector in offsets.items()
    }
    if len(rows) != len(offsets):
        raise ValueError("builder-owned explode offsets have duplicate instance paths")
    checked = _checked_offset_rows(rows, tuple(instance.name for instance in instances))
    return json.dumps(
        {
            "configuration": configuration,
            "view": exploded_view_name(configuration),
            "steps": len(EXPLODE_STEPS),
            "contract_sha256": explode_contract_fingerprint(instances),
            "offsets_m": checked,
        },
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def decode_explode_offsets(
    text: str, configuration: str, instances: Sequence[Instance]
) -> dict[str, tuple[float, float, float]]:
    """Require the source builder's complete, configuration-bound readback.

    There is no drawing-time reconstruction or zero-step fallback: a stale or
    incomplete source must be rebuilt by its owner.
    """
    view_name = exploded_view_name(configuration)
    try:
        payload = json.loads(text)
        if (
            not isinstance(payload, dict)
            or set(payload)
            != {"configuration", "view", "steps", "contract_sha256", "offsets_m"}
            or payload["configuration"] != configuration
            or payload["view"] != view_name
            or type(payload["steps"]) is not int
            or payload["steps"] != len(EXPLODE_STEPS)
            or payload["contract_sha256"] != explode_contract_fingerprint(instances)
        ):
            raise ValueError(
                "configuration, named view, native step count or explode contract differs"
            )
        return _checked_offset_rows(
            payload["offsets_m"], tuple(instance.name for instance in instances)
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{view_name}: missing or invalid builder-owned explode offsets "
            f"({exc}); rebuild assembly:mg_magnifier"
        ) from exc
