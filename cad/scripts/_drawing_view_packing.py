"""Pack measured decorated view rectangles using rigid translations only.

All coordinates are sheet metres. Give each movable view its own group and
constrain projected views with axis alignment and ordering. Their spacing can
then increase without losing projection alignment. Intentionally rigid groups
can contain several rectangles; an isometric view usually has no relations.
Obstacles are fixed rectangles. Rectangles, clearance, and drawable boundaries
are not reduced, and this module knows nothing about fonts or model entities.

The search branches on the four possible separations of a colliding pair.
Each branch is a pair of difference-constraint systems (one per axis), solved
with Bellman-Ford. Exhausting the branches proves infeasibility for these
axis-aligned footprints; hitting the node budget reports SEARCH_LIMIT instead.
Numeric comparisons allow 1e-12 m solely for floating-point roundoff. A feasible
answer is not necessarily the minimum-displacement or most attractive layout.

Integration example (bounds are measured decorated rectangles; positions are
the same snapshot's actual IView.Position anchors, not rectangle centres)::

    groups = [RigidViewGroup(name, {name: bounds[name]})
              for name in ("front", "top", "right", "iso")]
    result = pack_view_groups(
        groups, drawable, fixed_obstacles, gap_m=0.002,
        alignments=(
            AxisAlignment(Axis.X, "front", "top", positions["front"][0], positions["top"][0]),
            AxisAlignment(Axis.Y, "front", "right", positions["front"][1], positions["right"][1]),
        ),
        orderings=(AxisOrder(Axis.Y, "front", "top"),
                   AxisOrder(Axis.X, "front", "right")),
    )

The caller owns COM application and validation. Compute every absolute target
from the ORIGINAL position snapshot plus its returned translation. Moving a
SolidWorks parent can propagate to aligned/dependent children: do not add a
child's delta to a position already moved by its parent. Apply parent targets
before dependent targets, use documented non-propagating movement where valid,
then read back every position and remeasure decorations before accepting the
layout. This helper neither models propagation nor certifies annotation ink.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from itertools import combinations
import math
from typing import Mapping, Sequence


_EPSILON_M = 1e-12
Translation = tuple[float, float]
# source, destination, upper bound: offset[destination] - offset[source] <= bound.
_Constraint = tuple[int, int, float]


@dataclass(frozen=True)
class Rect:
    """Finite, positive-area axis-aligned sheet bounds in metres.

    Horizontal/vertical leader segments are endpoint pairs, not degenerate
    rectangles. A caller can include their occupied ink in an enclosing bound.
    """

    xmin: float
    ymin: float
    xmax: float
    ymax: float

    def __post_init__(self) -> None:
        if not all(math.isfinite(value) for value in self.bounds):
            raise ValueError("rectangle coordinates must be finite")
        if self.xmin >= self.xmax or self.ymin >= self.ymax:
            raise ValueError("rectangle must have positive width and height")

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        return self.xmin, self.ymin, self.xmax, self.ymax

    def translated(self, delta: Translation) -> Rect:
        dx, dy = delta
        return Rect(self.xmin + dx, self.ymin + dy, self.xmax + dx, self.ymax + dy)


@dataclass(frozen=True)
class RigidViewGroup:
    """Views that intentionally share one translation.

    Each mapping entry is a full decorated view footprint, not an overlapping
    annotation fragment. Use separate groups plus axis constraints when view
    spacing needs adjustment.
    """

    name: str
    rectangles: Mapping[str, Rect]


class Axis(Enum):
    X = 0
    Y = 1


@dataclass(frozen=True)
class AxisAlignment:
    """Keep two measured view anchors equal on one axis; other axis stays free."""

    axis: Axis
    first_group: str
    second_group: str
    first_anchor: float
    second_anchor: float


@dataclass(frozen=True)
class AxisOrder:
    """Keep the before group's decorated extent left of/below the after group."""

    axis: Axis
    before_group: str
    after_group: str


class PackingStatus(Enum):
    PACKED = "packed"
    DOES_NOT_FIT = "does_not_fit"
    SEARCH_LIMIT = "search_limit"


@dataclass(frozen=True)
class PackingResult:
    status: PackingStatus
    translations: Mapping[str, Translation]
    explored_nodes: int
    reason: str


@dataclass(frozen=True)
class _Footprint:
    group: int
    label: str
    rectangle: Rect


def _separated(first: Rect, second: Rect, gap: float) -> bool:
    return (
        first.xmax + gap <= second.xmin + _EPSILON_M
        or second.xmax + gap <= first.xmin + _EPSILON_M
        or first.ymax + gap <= second.ymin + _EPSILON_M
        or second.ymax + gap <= first.ymin + _EPSILON_M
    )


def _axis_solution(
    count: int, constraints: tuple[_Constraint, ...]
) -> tuple[float, ...] | None:
    values = [0.0] * count
    for _ in range(count):
        changed = False
        for source, target, bound in constraints:
            candidate = values[source] + bound
            if values[target] <= candidate + _EPSILON_M:
                continue
            values[target] = candidate
            changed = True
        if not changed:
            # Index zero is the fixed sheet/obstacle reference. Subtracting its
            # potential anchors every solution without changing differences.
            return tuple(value - values[0] for value in values)
    return None  # A negative cycle makes these separation choices infeasible.


def _collision(
    pairs: Sequence[tuple[_Footprint, _Footprint]],
    x: Sequence[float],
    y: Sequence[float],
    gap: float,
) -> tuple[_Footprint, _Footprint] | None:
    for first, second in pairs:
        a = first.rectangle.translated((x[first.group], y[first.group]))
        b = second.rectangle.translated((x[second.group], y[second.group]))
        if not _separated(a, b, gap):
            return first, second
    return None


def _branches(first: _Footprint, second: _Footprint, gap: float):
    a, b = first.rectangle, second.rectangle
    i, j = first.group, second.group
    return (
        (0, (j, i, b.xmin - a.xmax - gap)),  # first left of second
        (0, (i, j, a.xmin - b.xmax - gap)),  # first right of second
        (1, (j, i, b.ymin - a.ymax - gap)),  # first below second
        (1, (i, j, a.ymin - b.ymax - gap)),  # first above second
    )


def pack_view_groups(
    groups: Sequence[RigidViewGroup],
    drawable: Rect,
    obstacles: Sequence[Rect] = (),
    *,
    gap_m: float = 0.0,
    max_search_nodes: int = 10_000,
    alignments: Sequence[AxisAlignment] = (),
    orderings: Sequence[AxisOrder] = (),
) -> PackingResult:
    """Return rigid group translations or an explicit feasibility/search result.

    Rectangles must include all decorations that should move with a view.
    Group-internal overlaps/clearance violations cannot be repaired by a rigid
    translation and return DOES_NOT_FIT. Fixed obstacles may overlap each other;
    this function certifies view placement, not the obstacle layout itself.
    Alignment anchors must be actual view positions in the supplied footprint
    snapshot. Orderings enforce decorated-envelope clearance on the chosen axis.
    """
    if not math.isfinite(gap_m) or gap_m < 0:
        raise ValueError("packing clearance must be finite and nonnegative")
    if (
        isinstance(max_search_nodes, bool)
        or not isinstance(max_search_nodes, int)
        or max_search_nodes < 1
    ):
        raise ValueError("max_search_nodes must be a positive integer")
    groups = tuple(sorted(groups, key=lambda group: group.name))
    names = [group.name for group in groups]
    if any(not name.strip() for name in names) or len(set(names)) != len(names):
        raise ValueError("view groups require unique nonempty names")
    footprints = []
    x_constraints: list[_Constraint] = []
    y_constraints: list[_Constraint] = []
    view_names = set()
    group_bounds = {}
    for index, group in enumerate(groups, 1):
        if not group.rectangles:
            raise ValueError(f"view group {group.name!r} is empty")
        rectangles = tuple(sorted(group.rectangles.items()))
        for name, rectangle in rectangles:
            if not name.strip() or name in view_names:
                raise ValueError("views require unique nonempty names across groups")
            view_names.add(name)
            footprints.append(_Footprint(index, name, rectangle))
        for (first_name, first), (second_name, second) in combinations(rectangles, 2):
            if not _separated(first, second, gap_m):
                return PackingResult(
                    PackingStatus.DOES_NOT_FIT,
                    {},
                    0,
                    f"rigid group {group.name!r} has unrepairable internal overlap/clearance: {first_name}, {second_name}",
                )
        xmin = min(rectangle.xmin for _, rectangle in rectangles)
        ymin = min(rectangle.ymin for _, rectangle in rectangles)
        xmax = max(rectangle.xmax for _, rectangle in rectangles)
        ymax = max(rectangle.ymax for _, rectangle in rectangles)
        group_bounds[group.name] = Rect(xmin, ymin, xmax, ymax)
        x_constraints.extend(
            ((0, index, drawable.xmax - xmax), (index, 0, xmin - drawable.xmin))
        )
        y_constraints.extend(
            ((0, index, drawable.ymax - ymax), (index, 0, ymin - drawable.ymin))
        )
    indexes = {name: index for index, name in enumerate(names, 1)}
    axes = (x_constraints, y_constraints)
    for alignment in alignments:
        if not isinstance(alignment.axis, Axis):
            raise ValueError("alignment axis must be Axis.X or Axis.Y")
        if (
            alignment.first_group not in indexes
            or alignment.second_group not in indexes
        ):
            raise ValueError("alignment refers to an unknown view group")
        if not all(
            math.isfinite(value)
            for value in (alignment.first_anchor, alignment.second_anchor)
        ):
            raise ValueError("alignment anchors must be finite")
        first, second = indexes[alignment.first_group], indexes[alignment.second_group]
        delta = alignment.second_anchor - alignment.first_anchor
        axes[alignment.axis.value].extend(
            ((second, first, delta), (first, second, -delta))
        )
    for ordering in orderings:
        if not isinstance(ordering.axis, Axis):
            raise ValueError("ordering axis must be Axis.X or Axis.Y")
        if ordering.before_group not in indexes or ordering.after_group not in indexes:
            raise ValueError("ordering refers to an unknown view group")
        before, after = indexes[ordering.before_group], indexes[ordering.after_group]
        first, second = (
            group_bounds[ordering.before_group],
            group_bounds[ordering.after_group],
        )
        bound = (
            second.xmin - first.xmax - gap_m
            if ordering.axis is Axis.X
            else second.ymin - first.ymax - gap_m
        )
        axes[ordering.axis.value].append((after, before, bound))
    fixed = tuple(
        _Footprint(0, f"obstacle {index}", rectangle)
        for index, rectangle in enumerate(obstacles)
    )
    pairs = tuple(
        (first, second)
        for first, second in combinations(footprints, 2)
        if first.group != second.group
    )
    pairs += tuple((view, obstacle) for view in footprints for obstacle in fixed)
    initial = (0.0,) * (len(groups) + 1)
    bounds = (*x_constraints, *y_constraints)
    if (
        all(bound >= -_EPSILON_M for _, _, bound in bounds)
        and _collision(pairs, initial, initial, gap_m) is None
    ):
        return PackingResult(
            PackingStatus.PACKED,
            {name: (0.0, 0.0) for name in names},
            0,
            "already fits",
        )

    stack = [(tuple(x_constraints), tuple(y_constraints))]
    explored = 0
    while stack:
        if explored >= max_search_nodes:
            return PackingResult(
                PackingStatus.SEARCH_LIMIT,
                {},
                explored,
                "packing search node budget exhausted; feasibility not determined",
            )
        axes = stack.pop()
        explored += 1
        x = _axis_solution(len(groups) + 1, axes[0])
        y = _axis_solution(len(groups) + 1, axes[1])
        if x is None or y is None:
            continue
        collision = _collision(pairs, x, y, gap_m)
        if collision is None:
            return PackingResult(
                PackingStatus.PACKED,
                {
                    group.name: (x[index], y[index])
                    for index, group in enumerate(groups, 1)
                },
                explored,
                "rigid translations satisfy supplied footprints",
            )
        choices = _branches(*collision, gap_m)

        # Visit the separation with the least current violation first. This is
        # a deterministic search heuristic, not a minimum-motion guarantee.
        def displacement(choice):
            axis, (source, target, bound) = choice
            positions = (x, y)[axis]
            return positions[target] - positions[source] - bound

        for axis, constraint in sorted(choices, key=displacement, reverse=True):
            branch = list(axes)
            branch[axis] += (constraint,)
            stack.append(tuple(branch))
    return PackingResult(
        PackingStatus.DOES_NOT_FIT,
        {},
        explored,
        "no rigid translation satisfies supplied rectangles, obstacles and clearance",
    )
