r"""Reproduction script: pivot ball mount (book ch. 14 p. 27 / ch. 17 p. 40; 4 used).

The ball-end pillar that carries each pivot shaft end: a short pedestal
rising from its seat to a Ø19 ball whose centre sits 25.2 above the seat,
cross-bored Ø6.5 for the Ø6.35 shaft. Two seat on the rocker-support
apexes (seat y 228.6 -> pivot axis 253.8); two on the top-frame west rail
(seat y 1040.7 -> fulcrum axis 1065.9). The book's clevis-and-ball detail
(p. 40) is simplified to a monolithic base + stem + ball - the clamping
hardware is not modeled.

Dimensions: cad/DIMENSIONS.md ch. 14 layout "Ball mounts" row - ball rise
25.2 derived from the photo-measured pivot height; everything else
photo-scaled (low).

Layout: seat (base underside) on the Top plane at y = 0, axis +Y, ball
centre at (0, 25.2, 0), cross-bore along Z (mid-plane cut - direction
never matters). Single revolved profile: base disc, stem, ball; the stem
meets the ball exactly at the sphere chord so the profile is one closed
chain with no tangent-contact sliver.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_pivot_ball_mount.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    add_line_chain,
    anchor_point_to_origin,
    apply_material,
    check,
    define_circle,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_isometric_view,
    set_sketch_direct_db,
)

PART_NAME = "pivot-ball-mount"
MATERIAL = "Plain Carbon Steel"  # chrome-look ball/pillar in the photos

BALL_DIA = 19.0  # DIMENSIONS.md ch14 layout: Ø19 ball (scaled, low)
BALL_CENTER_H = 25.2  # ball centre above the seat (derived: 253.8 - 228.6)
BASE_DIA = 16.0  # seat pad on the 20 x 16.9 support apex (scaled, low)
BASE_H = 4.0  # seat pad height (scaled, low)
STEM_DIA = 8.0  # pillar between pad and ball (scaled, low)
BORE_DIA = 6.5  # shaft cross-bore, rides the Ø6.35 pivot shaft (derived)
THROUGH_CUT_DEPTH = 40.0  # mid-plane total; > ball dia

BALL_R = BALL_DIA / 2.0
# Stem meets the sphere where the Ø8 cylinder pierces it.
STEM_TOP_Y = BALL_CENTER_H - math.sqrt(BALL_R**2 - (STEM_DIA / 2.0) ** 2)
BALL_TOP_Y = BALL_CENTER_H + BALL_R


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters

    check("create_part", await adapter.create_part())
    set_isometric_view(adapter)

    # Revolved profile about +Y: base disc -> stem -> ball.
    check("create_sketch profile", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    check(
        "add_centerline axis",
        await adapter.add_centerline(0.0, 0.0, 0.0, BALL_TOP_Y),
    )
    lines = await add_line_chain(
        adapter,
        [
            (0.0, 0.0),
            (BASE_DIA / 2.0, 0.0),
            (BASE_DIA / 2.0, BASE_H),
            (STEM_DIA / 2.0, BASE_H),
            (STEM_DIA / 2.0, STEM_TOP_Y),
        ],
        close=False,
    )
    # Ball arc from the stem junction over the equator to the top pole
    # (add_arc draws CCW from start to end about the centre).
    arc = check(
        "add_arc ball",
        await adapter.add_arc(
            0.0, BALL_CENTER_H, STEM_DIA / 2.0, STEM_TOP_Y, 0.0, BALL_TOP_Y
        ),
    )
    closing = check(
        "add_line axis closure",
        await adapter.add_line(0.0, BALL_TOP_Y, 0.0, 0.0),
    )
    set_sketch_direct_db(adapter, False)
    base_bottom, base_wall, shoulder, stem_wall = lines
    # 13-DOF profile: seat corner on the origin; h/v on the chain edges
    # and the axis closure; ball centre anchored on the axis + radius;
    # the stem-wall vertical and the closure vertical each consume one
    # arc-endpoint angle. The centerline merged into the (0, 0) /
    # (0, BALL_TOP_Y) profile corners at creation -- no constraints.
    check(
        "anchor seat corner",
        await adapter.add_sketch_constraint(
            f"{base_bottom}.start", "origin", "coincident"
        ),
    )
    for label, ent, relation in (
        ("base bottom", base_bottom, "horizontal"),
        ("base wall", base_wall, "vertical"),
        ("shoulder", shoulder, "horizontal"),
        ("stem wall", stem_wall, "vertical"),
        ("axis closure", closing, "vertical"),
    ):
        check(
            f"{label} {relation}",
            await adapter.add_sketch_constraint(ent, None, relation),
        )
    await anchor_point_to_origin(
        adapter, f"{arc}.center", 0.0, BALL_CENTER_H, "ball centre"
    )
    check(
        "ball radius",
        await adapter.add_sketch_dimension(arc, None, "radial", BALL_R),
    )
    check(
        "base radius",
        await adapter.add_sketch_dimension(
            base_bottom, None, "linear", BASE_DIA / 2.0
        ),
    )
    check(
        "base height",
        await adapter.add_sketch_dimension(base_wall, None, "linear", BASE_H),
    )
    check(
        "shoulder run",
        await adapter.add_sketch_dimension(
            shoulder, None, "linear", (BASE_DIA - STEM_DIA) / 2.0
        ),
    )
    await ensure_fully_defined(adapter, "ball mount profile")
    check("exit_sketch profile", await adapter.exit_sketch())
    check(
        "revolve ball mount",
        await adapter.create_revolve(RevolveParameters(angle=360.0)),
    )
    res = await adapter.get_mass_properties()
    print(f"  volume after revolve: {res.data.volume:.1f} mm^3")
    # expected: disc 804.2 + stem 632.5 + sphere cap above the chord 3568.6
    #           = ~5,005 mm^3

    # Shaft cross-bore through the ball centre, along Z.
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, BALL_CENTER_H, BORE_DIA / 2.0, "shaft bore")
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    check(
        "cut bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    res = await adapter.get_mass_properties()
    print(f"  volume after bore: {res.data.volume:.1f} mm^3")
    # expected: -(4pi/3)(R^3 - (R^2 - r^2)^1.5) = ~-612 -> ~4,393 mm^3

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
