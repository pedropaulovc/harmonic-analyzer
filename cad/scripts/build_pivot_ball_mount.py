r"""Reproduction script: pivot ball mount (book ch. 14 p. 27 / ch. 17 p. 40; 4 used).

The ball-end pillar that carries each pivot shaft end: a short pedestal
rising from its seat to a Ø13 ball whose centre sits 25.2 above the seat,
cross-bored Ø6.5 for the Ø6.35 shaft. Two seat on the rocker-support
apexes (seat y 228.6 -> pivot axis 253.8); two on the top-frame west rail
(seat y 1074.6 -> fulcrum axis 1099.8). The book's clevis-and-ball detail
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

    uv run python cad\scripts\build_pivot_ball_mount.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    apply_material,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from pivot_ball_mount_spec import (
    BALL_CENTER_H,
    BALL_DIA,
    BASE_DIA,
    BASE_H,
    BORE_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    STEM_DIA,
)

import _telemetry

PART_NAME = "pivot-ball-mount"
MATERIAL = "Plain Carbon Steel"  # chrome-look ball/pillar in the photos

THROUGH_CUT_DEPTH = 40.0  # mid-plane total; > ball dia

BALL_R = BALL_DIA / 2.0
# Stem meets the sphere where the Ø8 cylinder pierces it.
STEM_TOP_Y = BALL_CENTER_H - math.sqrt(BALL_R**2 - (STEM_DIA / 2.0) ** 2)
BALL_TOP_Y = BALL_CENTER_H + BALL_R


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): ball/base/stem/bore primitives + the
    # ball-centre rise. The mm suffix is load-bearing -- this is an INCH document
    # and the equation manager reads BARE numbers in document units (an
    # unsuffixed 25.2 = 25.2 in, a 25.4x in-plane blow-up).
    await set_global(adapter, "BallDia", f"{BALL_DIA}mm")
    await set_global(adapter, "BallCenterH", f"{BALL_CENTER_H}mm")
    await set_global(adapter, "BaseDia", f"{BASE_DIA}mm")
    await set_global(adapter, "BaseH", f"{BASE_H}mm")
    await set_global(adapter, "StemDia", f"{STEM_DIA}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIA}mm")

    # Drive equations collected as dims are recorded, applied in one deferred
    # batch after the whole model + a rebuild exists (every target must resolve).
    drive_jobs: list[tuple[str, str]] = []

    # Revolved profile about +Y: base disc -> stem -> ball.
    profile = SketchDims()
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
    # Record each display dim into SketchDims in CREATION order. The ball-centre
    # anchor is on the Y axis (x=0, y!=0), so anchor_point_to_origin emits ONE
    # dim (the vertical rise) -- an UNSIGNED distance from the origin, driven by
    # the positive global. Then the four manual dims follow: ball radius, base
    # radius, base height, shoulder run. Five display dims total.
    await anchor_point_to_origin(
        adapter, f"{arc}.center", 0.0, BALL_CENTER_H, "ball centre"
    )
    profile.record("BallRise", '"BallCenterH"')
    check(
        "ball radius",
        await adapter.add_sketch_dimension(arc, None, "radial", BALL_R),
    )
    profile.record("BallRadius", '"BallDia" / 2')
    check(
        "base radius",
        await adapter.add_sketch_dimension(
            base_bottom, None, "linear", BASE_DIA / 2.0
        ),
    )
    profile.record("BaseRadius", '"BaseDia" / 2')
    check(
        "base height",
        await adapter.add_sketch_dimension(base_wall, None, "linear", BASE_H),
    )
    profile.record("BaseHeight", '"BaseH"')
    check(
        "shoulder run",
        await adapter.add_sketch_dimension(
            shoulder, None, "linear", (BASE_DIA - STEM_DIA) / 2.0
        ),
    )
    profile.record("ShoulderRun", '("BaseDia" - "StemDia") / 2')
    await ensure_fully_defined(adapter, "ball mount profile")
    check("exit_sketch profile", await adapter.exit_sketch())
    name_last_feature(adapter, "BallMountProfile")
    drive_jobs += profile.apply(adapter, "BallMountProfile")
    check(
        "revolve ball mount",
        await adapter.create_revolve(RevolveParameters(angle=360.0)),
    )
    name_last_feature(adapter, "BallMount")
    res = await adapter.get_mass_properties()
    _telemetry.info(f"volume after revolve: {res.data.volume:.1f} mm^3")
    # expected: disc 804.2 + stem 632.5 + sphere cap above the chord 3568.6
    #           = ~5,005 mm^3

    # Shaft cross-bore through the ball centre, along Z. On-axis in X (x=0,
    # y=BALL_CENTER_H!=0): define_circle records only the Z centre (an unsigned
    # rise) + the diameter -- the X slot is ignored.
    bore = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, BALL_CENTER_H, BORE_DIA / 2.0, "shaft bore", dims=bore,
        names=("BoreCx", "BoreCz", "ShaftBoreDia"),
        drives=(None, '"BallCenterH"', '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "ShaftBoreProfile")
    drive_jobs += bore.apply(adapter, "ShaftBoreProfile")
    check(
        "cut bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "ShaftBore")
    res = await adapter.get_mass_properties()
    v_final = float(res.data.volume)
    _telemetry.info(f"volume after bore: {v_final:.1f} mm^3")
    # expected: -(4pi/3)(R^3 - (R^2 - r^2)^1.5) = ~-612 -> ~4,393 mm^3

    # Apply the deferred drive equations after the model + a rebuild exists, then
    # re-check neutrality: every equation evaluates to the as-built value, so the
    # geometry must not move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven ball mount (equations neutral)", v_final, 0.005 * v_final
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {"Manufacturing Notes": DRAWING_NOTES},
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
