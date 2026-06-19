r"""Shared builder for the two roller-chain link parts (book ch. 23/30).

A roller chain is alternating INNER links (2 inner plates + 2 bushings) and
OUTER links (2 outer plates + 2 pins). Both are an obround side-plate pair
spanning one LINK_PITCH (pin centres at local x=0 and x=P) plus two round
bodies at the pin stations; only the plate z, the plate hole, and the round
body (bored bushing vs solid pin) differ -- so one builder takes the deltas.

Each link is authored in its own frame: plates in the Front (XY) plane, the
pin axis along local Z. Two named reference axes -- Axis1 at the x=0 station,
Axis2 at the x=P station -- are the chain pattern's PathLink1/PathLink2 (their
spacing IS the pattern pitch). See _chain.py for the clearance rationale (all
gaps >= 0.3 mm; the links float as disconnected multibody solids).
"""

from __future__ import annotations

import math
from typing import Any

from _chain import (
    BUSH_BORE_R,
    BUSH_HALF_LEN,
    INNER_PLATE_HOLE_R,
    INNER_PLATE_Z,
    LINK_PITCH,
    OUTER_PLATE_HOLE_R,
    OUTER_PLATE_Z,
    PIN_HALF_LEN,
    PIN_R,
    PLATE_HALF_H,
    PLATE_THICK,
    ROLLER_R,
)
from _common import (
    BAR_STEEL,
    apply_color,
    apply_material,
    check,
    define_circle,
    ensure_fully_defined,
    extrude_at_offset,
    report_mass_properties,
    save_part_and_images,
    set_isometric_view,
    set_sketch_direct_db,
)


async def _sketch_plate(adapter: Any, hole_r: float) -> None:
    """Front-plane obround side-plate outline (one LINK_PITCH long) with a
    clearance hole at each pin station; fully defined, ready to extrude."""
    from _common import anchor_point_to_origin

    p, h = LINK_PITCH, PLATE_HALF_H
    check("create_sketch plate", await adapter.create_sketch("Front"))
    # ALL geometry under direct-db (suppress inference snapping at the
    # origin/axes), then constraints with it off.
    set_sketch_direct_db(adapter, True)
    # CCW obround: bottom line, right end-arc (+x bulge), top line, left
    # end-arc (-x bulge). Endpoints share exact coords so they merge.
    line_bot = check("plate bottom", await adapter.add_line(0.0, -h, p, -h))
    arc_right = check("plate right arc", await adapter.add_arc(p, 0.0, p, -h, p, h))
    line_top = check("plate top", await adapter.add_line(p, h, 0.0, h))
    arc_left = check("plate left arc", await adapter.add_arc(0.0, 0.0, 0.0, h, 0.0, -h))
    hole0 = check("plate hole 0", await adapter.add_circle(0.0, 0.0, hole_r))
    holep = check("plate hole P", await adapter.add_circle(p, 0.0, hole_r))
    set_sketch_direct_db(adapter, False)
    # Outline: both end-arc centres anchored, both radii, all 4 junction
    # tangents (the proven chain-loop recipe -- tangency makes the two lines
    # the circles' common external tangents, i.e. horizontal).
    await anchor_point_to_origin(adapter, f"{arc_left}.center", 0.0, 0.0, "left arc")
    await anchor_point_to_origin(adapter, f"{arc_right}.center", p, 0.0, "right arc")
    for label, arc in (("left", arc_left), ("right", arc_right)):
        check(
            f"plate {label} arc radius",
            await adapter.add_sketch_dimension(arc, None, "radial", h),
        )
    for label, e1, e2 in (
        ("bot-right", line_bot, arc_right),
        ("right-top", arc_right, line_top),
        ("top-left", line_top, arc_left),
        ("left-bot", arc_left, line_bot),
    ):
        check(
            f"plate tangent {label}",
            await adapter.add_sketch_constraint(e1, e2, "tangent"),
        )
    # Pin-station clearance holes (concentric with the end arcs).
    for label, circle, cx in (("0", hole0, 0.0), ("P", holep, p)):
        await anchor_point_to_origin(adapter, f"{circle}.center", cx, 0.0, f"hole {label}")
        check(
            f"plate hole {label} diameter",
            await adapter.add_sketch_dimension(circle, None, "diameter", 2.0 * hole_r),
        )
    await ensure_fully_defined(adapter, "plate sketch")
    check("exit_sketch plate", await adapter.exit_sketch())


async def _sketch_round_bodies(adapter: Any, outer_r: float, bore_r: float | None) -> None:
    """Front-plane circles at both pin stations -- a bored tube (bushing) when
    ``bore_r`` is given (nested circle = even-odd hole), else a solid disc."""
    p = LINK_PITCH
    check("create_sketch bodies", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    for label, cx in (("0", 0.0), ("P", p)):
        await define_circle(adapter, cx, 0.0, outer_r, f"body outer {label}")
        if bore_r is not None:
            await define_circle(adapter, cx, 0.0, bore_r, f"body bore {label}")
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "round bodies sketch")
    check("exit_sketch bodies", await adapter.exit_sketch())


async def build_link(
    adapter: Any,
    *,
    part_name: str,
    material: str,
    plate_z: float,
    plate_hole_r: float,
    body_outer_r: float,
    body_bore_r: float | None,
    body_half_len: float,
) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreateAxisParameters, CreatePlaneParameters

    check("create_part", await adapter.create_part())
    set_isometric_view(adapter)

    # Offset plane at the x=P pin station (Right Plane normal is +X, so
    # flip=False steps +P); created first so the axes name as Axis1/Axis2.
    station_plane = check(
        "create_plane @ x=P",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Right Plane", offset=LINK_PITCH, flip=False
            )
        ),
    )
    station_plane_name = getattr(station_plane, "name", station_plane)

    # Two side plates, mirror-paired across the chain mid-plane.
    for sign in (1.0, -1.0):
        await _sketch_plate(adapter, plate_hole_r)
        z_lo = sign * plate_z - PLATE_THICK / 2.0
        extrude_at_offset(adapter, PLATE_THICK, z_lo)

    # Two round bodies (bushings or pins), centred on the mid-plane.
    await _sketch_round_bodies(adapter, body_outer_r, body_bore_r)
    extrude_at_offset(adapter, 2.0 * body_half_len, -body_half_len)

    _gate_volume(
        await _volume(adapter), plate_hole_r, body_outer_r, body_bore_r, body_half_len
    )

    # Path-link axes (chain pattern PathLink1/PathLink2): Z lines through the
    # two pin stations, named Axis1 (x=0, Top x Right) and Axis2 (x=P,
    # Top x the station plane). Two-plane intersection is the proven recipe.
    for label, second_plane in (("Axis1", "Right Plane"), ("Axis2", station_plane_name)):
        axis = check(
            f"create_axis {label}",
            await adapter.create_axis(
                CreateAxisParameters(mode="two_planes", planes=["Top Plane", second_plane])
            ),
        )
        if axis.name != label:
            raise RuntimeError(f"pin-station axis is {axis.name!r}, expected {label!r}")

    await apply_material(adapter, material)
    await apply_color(adapter, BAR_STEEL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, part_name)


async def _volume(adapter: Any) -> float:
    res = await adapter.get_mass_properties()
    return float(res.data.volume) if res.is_success else float("nan")


def _gate_volume(
    vol: float,
    hole_r: float,
    outer_r: float,
    bore_r: float | None,
    half_len: float,
) -> None:
    h, p, t = PLATE_HALF_H, LINK_PITCH, PLATE_THICK
    plate_area = 2.0 * h * p + math.pi * h * h - 2.0 * math.pi * hole_r * hole_r
    plates = 2.0 * plate_area * t
    ring = math.pi * (outer_r * outer_r - (bore_r * bore_r if bore_r else 0.0))
    bodies = 2.0 * ring * (2.0 * half_len)
    expected = plates + bodies
    print(f"  volume: {vol:.2f} mm^3 (analytic {expected:.2f})")
    if abs(vol - expected) > 0.02 * expected:
        raise RuntimeError(f"link volume {vol:.2f} != {expected:.2f}")


INNER_LINK = dict(
    plate_z=INNER_PLATE_Z,
    plate_hole_r=INNER_PLATE_HOLE_R,
    body_outer_r=ROLLER_R,
    body_bore_r=BUSH_BORE_R,
    body_half_len=BUSH_HALF_LEN,
)
OUTER_LINK = dict(
    plate_z=OUTER_PLATE_Z,
    plate_hole_r=OUTER_PLATE_HOLE_R,
    body_outer_r=PIN_R,
    body_bore_r=None,
    body_half_len=PIN_HALF_LEN,
)
