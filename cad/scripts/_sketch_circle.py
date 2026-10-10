"""Fully-defined circle recipes.

Separate module so edits affect only recipes that use this scope.
"""

from __future__ import annotations

from typing import Any, Literal

import _telemetry
from _check import check
from _sketch import SketchDims, _record_origin_anchor, anchor_point_to_origin


@_telemetry.traced("sketch.circle", label_param="label")
async def define_circle(
    adapter: Any,
    x: float,
    y: float,
    radius: float,
    label: str,
    *,
    dims: "SketchDims | None" = None,
    names: tuple[str | None, str | None, str | None] | None = None,
    drives: tuple[str | None, str | None, str | None] | None = None,
    size_dimension: Literal["diameter", "radius"] = "diameter",
) -> str:
    """Add a circle, anchor its centre to the origin semantically, then add
    a DRIVING size dimension. No ``fix`` involved.

    ``size_dimension`` picks what that dimension measures, and therefore what
    its name/drive slot means. A circle that PRINTS as a radius (an arc crown)
    must be dimensioned as one here: a drawing that flips a model diameter to
    radial keeps its value and re-reads it as a radius, so an equation-driven
    diameter doubles the feature on the sheet's rebuild (v37 arbor-pedestal
    printed an R22 crown on its R11 part).

    The raw ``add_circle`` runs with sketch inference SUPPRESSED (restored
    afterwards): with it on, a second concentric/near circle snaps to the first
    and the call fails (proven live on the coefficients-plate hole column).
    Same rationale as :func:`add_line_chain` -- the centre/diameter are pinned
    explicitly below, so inference during the draw only ever hurts.

    Self-naming: pass ``dims`` (a per-sketch :class:`SketchDims`) plus ``names`` /
    ``drives`` as ``(centre_x, centre_z, size)`` tuples to record this
    circle's dims for later renaming/driving. Only the dims actually emitted are
    recorded -- an on-axis centre drops its zero coordinate -- so the same call
    is correct whether the circle is on an axis or not."""
    sketch_mgr = adapter.currentSketchManager
    prev_add_to_db = bool(sketch_mgr.AddToDB)
    sketch_mgr.AddToDB = True
    try:
        circle = await adapter.add_circle(x, y, radius)
        check(f"add_circle {label}", circle)
    finally:
        sketch_mgr.AddToDB = prev_add_to_db
    await anchor_point_to_origin(adapter, f"{circle.data}.center", x, y, label)
    n_x, n_z, n_size = names or (None, None, None)
    d_x, d_z, d_size = drives or (None, None, None)
    _record_origin_anchor(dims, x, y, n_x, n_z, d_x, d_z)
    dimension_type, value = _CIRCLE_SIZE_DIMENSIONS[size_dimension](radius)
    check(
        f"dimension {label} {size_dimension}",
        await adapter.add_sketch_dimension(circle.data, None, dimension_type, value),
    )
    if dims is not None:
        dims.record(n_size, d_size)
    return circle.data


# define_circle's size_dimension -> (adapter dimension type, value from radius).
_CIRCLE_SIZE_DIMENSIONS = {
    "diameter": lambda radius: ("diameter", radius * 2.0),
    "radius": lambda radius: ("radial", radius),
}
