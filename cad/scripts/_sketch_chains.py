"""Fully-defined polygon and rectilinear chain recipes.

Separate module so edits affect only recipes that use this scope.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import _telemetry
from _check import check
from _sketch import (
    SketchDims,
    anchor_point_to_origin,
    anchor_point_to_point,
    dimension_between,
)


def _record_point_to_point_cursor(
    rec: "Callable[[], None]", dx: float, dy: float
) -> None:
    """Drive ``rec`` once per dim :func:`anchor_point_to_point` emits for offset
    ``(dx, dy)`` -- one on an axis-aligned segment, two (horizontal then
    vertical) in general -- keeping a cursor record aligned with its emission."""
    sdx = 0.0 if abs(dx) < 1e-9 else dx
    sdy = 0.0 if abs(dy) < 1e-9 else dy
    if sdx == 0.0 and sdy == 0.0:
        return
    if sdx == 0.0 or sdy == 0.0:
        rec()
        return
    rec()
    rec()


@_telemetry.traced("sketch.polygon", label_param="label")
async def define_polygon_chain(
    adapter: Any,
    lines: list[str],
    points: list[tuple[float, float]],
    anchor: int = 0,
    label: str = "polygon",
    *,
    dims: "SketchDims | None" = None,
    names: list[str | None] | None = None,
    drives: list[str | None] | None = None,
) -> None:
    """Fully define a CLOSED line chain of arbitrary slopes semantically.

    Vertex ``anchor`` goes to the origin; every segment then pins its end
    relative to its start via :func:`anchor_point_to_point` — except the
    segment ENDING at the anchored vertex, whose span the closure supplies
    (dimensioning it too over-defines the sketch). Prefer
    :func:`define_rectilinear_chain` for axis-parallel chains: it emits
    segment-length dims instead of per-axis offsets.

    Self-naming: pass ``dims`` plus ``names`` / ``drives`` aligned to the
    EMISSION ORDER -- the anchor dims first (x, then z; only the non-zero ones),
    THEN each kept segment's offset dims in line order (horizontal then vertical
    per general segment; one for an axis-aligned segment). Unnamed slots stay
    auto-named/undriven.
    """
    n = len(lines)
    if n != len(points):
        raise ValueError(
            f"{label}: need a closed chain (lines {n} != points {len(points)})"
        )
    rec = _dim_cursor(dims, names, drives)
    await anchor_point_to_origin(
        adapter, f"{lines[anchor]}.start", *points[anchor], f"{label} anchor"
    )
    _record_origin_anchor_cursor(rec, *points[anchor])
    skip = (anchor - 1) % n  # the segment ending at the anchored vertex
    for i, line in enumerate(lines):
        if i == skip:
            continue
        (x1, y1), (x2, y2) = points[i], points[(i + 1) % n]
        await anchor_point_to_point(
            adapter, f"{line}.start", f"{line}.end", x2 - x1, y2 - y1, f"{label} {line}"
        )
        _record_point_to_point_cursor(rec, x2 - x1, y2 - y1)


def _dim_cursor(
    dims: "SketchDims | None",
    names: list[str | None] | None,
    drives: list[str | None] | None,
) -> "Callable[[], None]":
    """Return a zero-arg ``rec()`` that records the next (name, drive) into
    ``dims`` in emission order, pulling sequentially from ``names``/``drives``
    (``None`` once exhausted). The caller calls it once per dim it emits, in the
    exact order emitted; :meth:`SketchDims.apply` then count-asserts the total
    against the feature's real display-dim count, so a miscount fails loud."""
    _names = list(names) if names else []
    _drives = list(drives) if drives else []
    state = {"k": 0}

    def rec() -> None:
        k = state["k"]
        if dims is not None:
            nm = _names[k] if k < len(_names) else None
            dv = _drives[k] if k < len(_drives) else None
            dims.record(nm, dv)
        state["k"] = k + 1

    return rec


def _record_origin_anchor_cursor(rec: "Callable[[], None]", x: float, y: float) -> None:
    """Drive ``rec`` once per dim :func:`anchor_point_to_origin` emits for
    ``(x, y)`` -- none on the origin, one on an axis (x then y), two in general
    -- so a cursor-based record stays aligned with the anchor's emission."""
    sx = 0.0 if abs(x) < 1e-9 else x
    sy = 0.0 if abs(y) < 1e-9 else y
    if sx != 0.0:
        rec()
    if sy != 0.0:
        rec()


@_telemetry.traced("sketch.rect_chain", label_param="label")
async def define_rectilinear_chain(
    adapter: Any,
    lines: list[str],
    points: list[tuple[float, float]],
    anchor: int = 0,
    label: str = "chain",
    *,
    dims: "SketchDims | None" = None,
    names: list[str | None] | None = None,
    drives: list[str | None] | None = None,
) -> None:
    """Fully define a CLOSED axis-parallel line chain semantically.

    ``lines``/``points`` are :func:`add_line_chain` output and input (line i
    runs points[i] -> points[i+1], wrapping). Every segment gets its
    horizontal/vertical relation; every segment except the LAST one of each
    direction gets a driving point-pair distance dim — closure makes one dim
    per direction redundant, and adding it over-defines the sketch. Vertex
    ``anchor`` is the chain's single origin anchor (one-anchor rule, see the
    module docstring).

    Self-naming: pass ``dims`` plus ``names`` / ``drives`` lists aligned to the
    EMISSION ORDER -- the per-segment distance dims in line order (skipping the
    one redundant segment per direction), THEN the anchor dims (x, then z; only
    the non-zero ones). Unnamed slots (``None`` or past the list end) stay
    auto-named/undriven. For an origin-centred rectangle prefer
    :func:`define_centered_rectangle`, which names width/depth/corner directly.
    """
    n = len(lines)
    if n != len(points):
        raise ValueError(
            f"{label}: need a closed chain (lines {n} != points {len(points)})"
        )
    rec = _dim_cursor(dims, names, drives)
    directions: list[str] = []
    for i, line in enumerate(lines):
        (x1, y1), (x2, y2) = points[i], points[(i + 1) % n]
        if y1 == y2 and x1 != x2:
            direction = "horizontal"
        elif x1 == x2 and y1 != y2:
            direction = "vertical"
        else:
            raise ValueError(
                f"{label}: segment {line} ({x1:g},{y1:g})->({x2:g},{y2:g}) "
                "is not axis-parallel"
            )
        directions.append(direction)
        check(
            f"{label} {direction} {line}",
            await adapter.add_sketch_constraint(line, None, direction),
        )
    last = {
        d: max(i for i, d2 in enumerate(directions) if d2 == d) for d in set(directions)
    }
    for i, (line, direction) in enumerate(zip(lines, directions, strict=True)):
        if last[direction] == i:
            continue  # the closure equation supplies this span
        (x1, y1), (x2, y2) = points[i], points[(i + 1) % n]
        if direction == "horizontal":
            kind, span = "horizontal_distance", abs(x2 - x1)
        else:
            kind, span = "vertical_distance", abs(y2 - y1)
        await dimension_between(
            adapter, f"{line}.start", f"{line}.end", kind, span, f"{label} {line}"
        )
        rec()
    await anchor_point_to_origin(
        adapter, f"{lines[anchor]}.start", *points[anchor], f"{label} anchor"
    )
    _record_origin_anchor_cursor(rec, *points[anchor])
