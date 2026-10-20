"""Pure pre-fit annotation budgets for native supplier screw references."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from _supplier_screw_reference_names import FEATURE_BY_PLANE

_TEXT_ROOM_M = 0.020


def supplier_screw_lane_plan(
    dimensions: Sequence[tuple[str, float, str]],
    *,
    planes: Mapping[str, str] | None = None,
    sides: Mapping[str, str] | None = None,
) -> dict[str, tuple[str, float]]:
    """Route source chords on authored free sides, then allocate distinct lanes.

    A smaller shank/collar chord must escape away from the wider head. Those
    source-geometry choices belong to the per-SKU ``sides`` map, not a parity
    heuristic. Other references retain the alternating layout. Same-side linear
    spans nest smallest first in the 6/14/22 mm lanes, keeping a smaller chord's
    witnesses inside the larger dimension line. Angular symbols follow those
    lanes; degrees are not compared with linear spans.
    """
    planes = planes or {}
    sides = sides or {}
    names = {name for name, _, _ in dimensions}
    if len(names) != len(dimensions) or set(sides) - names:
        raise ValueError("supplier side plan must name unique source dimensions")
    orientation_counts: dict[tuple[str, str], int] = {}
    groups: dict[tuple[str, str], list[tuple[str, float, str]]] = {}
    plan: dict[str, tuple[str, float]] = {}
    for name, value, orientation in dimensions:
        plane = planes.get(name, "Front")
        if plane not in FEATURE_BY_PLANE:
            raise ValueError(f"{name}: unsupported supplier reference plane {plane!r}")
        if orientation == "vertical":
            allowed = ("right", "left")
        elif orientation == "horizontal":
            allowed = ("top", "bottom")
        elif orientation == "angle":
            allowed = ("left", "right")
        else:
            raise ValueError(
                f"{name}: unsupported supplier reference orientation {orientation!r}"
            )
        orientation_key = (plane, orientation)
        ordinal = orientation_counts.get(orientation_key, 0)
        orientation_counts[orientation_key] = ordinal + 1
        default = allowed[ordinal % 2] if orientation != "angle" else "left"
        side = sides.get(name, default)
        if side not in allowed:
            raise ValueError(
                f"{name}: side {side!r} is incompatible with {orientation!r}"
            )
        groups.setdefault((plane, side), []).append((name, value, orientation))
    for (_, side), rows in groups.items():
        ordered = sorted(
            rows,
            key=lambda row: (
                row[2] == "angle",
                abs(row[1]) if row[2] != "angle" else 0.0,
            ),
        )
        for lane, (name, _, _) in enumerate(ordered):
            plan[name] = (side, 0.006 + lane * 0.008)
    return plan


def supplier_screw_margins(
    dimensions: Sequence[tuple[str, float, str]],
    *,
    planes: Mapping[str, str] | None = None,
    sides: Mapping[str, str] | None = None,
) -> dict[str, tuple[float, float, float, float]]:
    """Budget the identical free-side lane plan before fitting annotated views.

    This is not native ink proof: the shared settled guard must still check
    actual annotation primitives/text against the outer cell and caption.
    """
    planes = planes or {}
    plan = supplier_screw_lane_plan(dimensions, planes=planes, sides=sides)
    margins_by_plane: dict[str, list[float]] = {}
    side_indices = {"left": 0, "bottom": 1, "right": 2, "top": 3}
    for name, _, _ in dimensions:
        plane = planes.get(name, "Front")
        margins = margins_by_plane.setdefault(plane, [_TEXT_ROOM_M] * 4)
        side, offset = plan[name]
        index = side_indices[side]
        margins[index] = max(margins[index], offset + _TEXT_ROOM_M)
    return {
        f"*{plane}": (margins[0], margins[1], margins[2], margins[3])
        for plane, margins in margins_by_plane.items()
    }
