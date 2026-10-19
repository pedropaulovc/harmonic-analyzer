"""Revolved bought-part bodies, shared by the oblique jig's datasheet builders.

The pen-marker idiom (``build_pn_vn_pen_marker``) generalised for the bought
leadscrew, nut and handwheel: sketch a closed line chain, fully define it
semantically, revolve it 360° (boss or cut), and name the sketch and feature.
"""

from __future__ import annotations

from typing import Any

from _check import check
from _feature_tree import name_last_feature
from _sketch import (
    add_line_chain,
    anchor_point_to_origin,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_chains import define_polygon_chain
from _visibility import blank_reference_geometry


async def revolve_profile(
    adapter: Any,
    plane: str,
    label: str,
    points: list[tuple[float, float]],
    names: tuple[str, str],
    *,
    is_cut: bool = False,
    free_axis_length: float | None = None,
) -> None:
    """Sketch the closed chain ``points`` on ``plane`` and revolve it 360°.

    The revolve axis is the chain's closing edge (points[-1] -> points[0]): a
    centerline drawn over it merges into its two corners, as on the pen
    marker. A profile clear of its axis (a body round a bore) passes
    ``free_axis_length`` instead: a centerline up the sketch's v-axis from the
    origin, pinned vertical, to the origin and by that length.
    """
    from solidworks_mcp.adapters.base import RevolveParameters

    check(f"create_sketch {label}", await adapter.create_sketch(plane))
    set_sketch_direct_db(adapter, True)
    if free_axis_length is None:
        axis = (*points[-1], *points[0])
    else:
        axis = (0.0, 0.0, 0.0, free_axis_length)
    centerline = check(f"{label} axis", await adapter.add_centerline(*axis))
    lines = await add_line_chain(adapter, points)
    set_sketch_direct_db(adapter, False)
    if free_axis_length is not None:
        check(
            f"{label} axis vertical",
            await adapter.add_sketch_constraint(centerline, None, "vertical"),
        )
        await anchor_point_to_origin(
            adapter, f"{centerline}.start", 0.0, 0.0, f"{label} axis"
        )
        check(
            f"{label} axis length",
            await adapter.add_sketch_dimension(
                centerline, None, "linear", free_axis_length
            ),
        )
    await define_polygon_chain(adapter, lines, points, label=label)
    await ensure_fully_defined(adapter, f"{label} profile")
    check(f"exit_sketch {label}", await adapter.exit_sketch())
    name_last_feature(adapter, names[0])
    check(
        f"revolve {label}",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=is_cut)),
    )
    name_last_feature(adapter, names[1])


async def fillet_edge(
    adapter: Any,
    label: str,
    radius: float,
    point: tuple[float, float, float],
    name: str,
) -> None:
    """Round the one (circular) edge through model ``point``."""
    check(
        f"fillet {label}",
        await adapter.add_fillet(radius, [list(point)], propagate=False),
    )
    name_last_feature(adapter, name)


async def publish_screw_axis(adapter: Any) -> None:
    """The stock-part mate contract: ``ScrewAxis`` at Front ∩ Right, hidden."""
    from solidworks_mcp.adapters.base import CreateAxisParameters

    check(
        "create_axis ScrewAxis (Front ∩ Right)",
        await adapter.create_axis(
            CreateAxisParameters(
                mode="two_planes", planes=["Front Plane", "Right Plane"]
            )
        ),
    )
    name_last_feature(adapter, "ScrewAxis")
    blank_reference_geometry(adapter, (("ScrewAxis", "AXIS"),))


# The bought parts' saved-property contract (the pen marker's).
SAVED_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Stock Name",
    "Supplier",
    "Supplier SKUs",
    "Manufacturing Notes",
)


def stock_properties(row: dict[str, Any]) -> dict[str, str]:
    """A purchased part's identity stamps from its registry row."""
    return {
        "Stock Name": str(row["stock_name"]),
        "Supplier": str(row["supplier"]),
        "Supplier SKUs": ", ".join(str(sku) for sku in row["supplier_skus"]),
    }
