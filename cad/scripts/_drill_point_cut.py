"""The 118° drill point that ends a blind drilled or reamed hole, as a cut.

One revolve cut from the point's half-section (floor centre, hole wall, tip)
on the caller's open sketch, which holds the hole's axis, revolved about that
axis.  The point's height is ``_hole_spec.DRILL_POINT_H`` times the hole's
radius, the ratio every 118° drill point shares, so the cut and the specs'
point heights read one constant.

Separate to limit cache blast radius: only the recipes that cut a drill point
this way (``build_sm_knife_mount``, ``build_fr_top_frame``) carry it in their
closure.
"""

from __future__ import annotations

import math
from typing import Any

from _check import check
from _feature_tree import name_last_feature
from _hole_spec import DRILL_POINT_H
from _sketch import (
    add_line_chain,
    anchor_point_to_origin,
    ensure_fully_defined,
    set_sketch_direct_db,
)


def drill_point_volume(radius: float) -> float:
    """The cone a 118° drill point on a hole of ``radius`` removes (mm³)."""
    return math.pi / 3.0 * radius**2 * (radius * DRILL_POINT_H)


def cut_drill_point(
    adapter: Any,
    *,
    label: str,
    floor_centre: tuple[float, float],
    radius: float,
    wall_sign: int,
    tip_sign: int,
    profile_name: str,
    feature_name: str,
) -> None:
    """Revolve-cut the drill point past a hole's full-diameter floor.

    The sketch is open and holds the hole's axis.  ``floor_centre`` is the
    floor's centre in sketch (u, v), on the axis, and the axis runs along v;
    ``wall_sign`` (+1 or -1) is the sketch u direction to the hole wall and
    ``tip_sign`` the sketch v direction from the floor to the tip.  Closes the
    sketch, names it ``profile_name`` and the cut ``feature_name``.
    """
    from solidworks_mcp.adapters.base import RevolveParameters

    if wall_sign not in (1, -1) or tip_sign not in (1, -1):
        raise ValueError(f"{label}: wall_sign and tip_sign must be +1 or -1")
    height = radius * DRILL_POINT_H
    au, av = floor_centre
    bu = au + wall_sign * radius
    cv = av + tip_sign * height
    set_sketch_direct_db(adapter, True)
    axis = check(
        f"{label} axis",
        adapter.add_centerline(au, cv, au, cv + tip_sign * height),
    )
    floor, _flank, on_axis = add_line_chain(adapter, [(au, av), (bu, av), (au, cv)])
    set_sketch_direct_db(adapter, False)
    for line, relation in (
        (floor, "horizontal"),
        (on_axis, "vertical"),
        (axis, "vertical"),
    ):
        check(
            f"{label} {relation} {line}",
            adapter.add_sketch_constraint(line, None, relation),
        )
    check(
        f"{label} axis at the tip",
        adapter.add_sketch_constraint(
            f"{axis}.start", f"{on_axis}.start", "coincident"
        ),
    )
    anchor_point_to_origin(adapter, f"{floor}.start", au, av, f"{label} floor centre")
    check(
        f"{label} radius", adapter.add_sketch_dimension(floor, None, "linear", radius)
    )
    check(
        f"{label} height",
        adapter.add_sketch_dimension(on_axis, None, "linear", height),
    )
    check(
        f"{label} axis length",
        adapter.add_sketch_dimension(axis, None, "linear", height),
    )
    ensure_fully_defined(adapter, f"{label} profile")
    check(f"exit_sketch {label}", adapter.exit_sketch())
    name_last_feature(adapter, profile_name)
    check(
        f"revolve-cut {label}",
        adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
    )
    name_last_feature(adapter, feature_name)
