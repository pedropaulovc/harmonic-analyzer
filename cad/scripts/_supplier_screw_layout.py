"""Pure pre-fit annotation budgets for native supplier reference dimensions."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import isfinite

from _supplier_screw_reference_names import FEATURE_BY_PLANE

_TEXT_ROOM_M = 0.020


def supplier_screw_lane_plan(
    dimensions: Sequence[tuple[str, float, str]],
    *,
    planes: Mapping[str, str] | None = None,
    sides: Mapping[str, str] | None = None,
) -> dict[str, tuple[str, float]]:
    """Route source chords on authored free sides, allocating distinct lanes.

    Small shank/collar chords must escape away from wider heads. Per-SKU
    sides encode that physical choice, rather than a parity heuristic.
    Same-side linear spans nest smallest first; angular symbols follow them.
    """
    planes = planes or {}
    sides = sides or {}
    names = {name for name, _, _ in dimensions}
    if len(names) != len(dimensions) or (set(sides) | set(planes)) - names:
        raise ValueError("supplier side plan must name unique source dimensions")
    counts: dict[tuple[str, str], int] = {}
    groups: dict[tuple[str, str], list[tuple[str, float, str]]] = {}
    plan: dict[str, tuple[str, float]] = {}
    for name, value, orientation in dimensions:
        if (
            not isinstance(name, str)
            or not name
            or "@" in name
            or isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not isfinite(value)
            or value == 0.0
        ):
            raise ValueError(f"{name}: supplier reference value must be finite and nonzero")
        plane = planes.get(name, "Front")
        if plane not in FEATURE_BY_PLANE:
            raise ValueError(f"{name}: unsupported supplier reference plane {plane!r}")
        if orientation == "vertical":
            allowed = ("right", "left")
        elif orientation == "horizontal":
            allowed = ("top", "bottom")
        elif orientation == "angle":
            if not 0.0 < value < 180.0:
                raise ValueError(f"{name}: supplier included angle must be between 0 and 180")
            allowed = ("left", "right")
        else:
            raise ValueError(f"{name}: unsupported supplier reference orientation {orientation!r}")
        key = (plane, orientation)
        ordinal = counts.get(key, 0)
        counts[key] = ordinal + 1
        default = allowed[ordinal % 2] if orientation != "angle" else "left"
        side = sides.get(name, default)
        if side not in allowed:
            raise ValueError(f"{name}: side {side!r} is incompatible with {orientation!r}")
        groups.setdefault((plane, side), []).append((name, value, orientation))
    for (_, side), rows in groups.items():
        ordered = sorted(
            rows,
            key=lambda row: (row[2] == "angle", abs(row[1]) if row[2] != "angle" else 0.0),
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
    """Reserve the identical lane plan before fitting annotated views.

    The final settled guard still checks actual native ink against its outer
    cell and caption. A pre-fit allowance is not evidence of native ink fit.
    """
    planes = planes or {}
    plan = supplier_screw_lane_plan(dimensions, planes=planes, sides=sides)
    margins_by_plane: dict[str, list[float]] = {}
    indices = {"left": 0, "bottom": 1, "right": 2, "top": 3}
    for name, _, _ in dimensions:
        plane = planes.get(name, "Front")
        margins = margins_by_plane.setdefault(plane, [_TEXT_ROOM_M] * 4)
        side, offset = plan[name]
        index = indices[side]
        margins[index] = max(margins[index], offset + _TEXT_ROOM_M)
    return {
        f"*{plane}": (margins[0], margins[1], margins[2], margins[3])
        for plane, margins in margins_by_plane.items()
    }
