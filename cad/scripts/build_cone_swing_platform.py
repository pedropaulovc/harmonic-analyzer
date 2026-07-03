r"""Reproduction script: cone swing platform (book ch. 12, p. 18 "pivot").

The wedge-shaped plate the whole cone-gear set rides on. The book's
top-down photo (p. 18) labels the TIP end "pivot": the pivot post, the
cone shaft and the tip clamp block all stand ON this plate, and the whole
unit swings horizontally about a vertical axis near the shaft's thin tip
to dis/engage the 16T pinion from the 64T cylinder gear (video 4/4,
engage/disengage stills). Swing separation grows with distance from the
pivot, so pivoting at the TIP gives the big-end gears -- the ones that
need real working-depth clearance -- the largest throw.

Plan shape is the p.18 wedge: a trapezoid, wide under the big end and
tapering toward the pivot. Dimensions estimated from the p.18 top-down
vs the 64T gear and the v4 stills (low).

Layout: plate lying on the Top plane, extruded +Y by the thickness.
Origin at the SWING PIVOT (the assembly rotates the plate about this
point); local +Z runs along increasing cone station, so the wide south
edge sits at local z = NORTH_OVERHANG - PLATE_LEN and the narrow north
edge overhangs the pivot by NORTH_OVERHANG. A O6.35 pivot hole marks the
pivot screw. Named refs for the assembly: "swing pivot" (vertical axis
through the origin) and "PlateTop" (datum plane on the top face -- the
riders' seat mate, FootSeat/DeckTop pattern).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_cone_swing_platform.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    PANEL_BLACK,
    SketchDims,
    add_line_chain,
    apply_color,
    apply_material,
    check,
    define_circle,
    define_polygon_chain,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)

PART_NAME = "cone-swing-platform"
MATERIAL = "Plain Carbon Steel"  # black-finished steel plate (p.18 dark wedge)

PLATE_T = 6.35  # 1/4" plate (low)
HALF_WIDTH_S = 20.0  # south (big-end) half-width -- wide end of the wedge
HALF_WIDTH_N = 12.0  # north (pivot/tip) half-width -- narrow end
PLATE_LEN = 215.0  # north edge -> south edge along the cone axis: covers the
# pivot post's south flank by 1.5 while keeping ~1.9 true (corner) air to the
# crank pedestal -- the south edge is slanted in machine z, so the assembly
# asserts the gap in the plate's own frame
NORTH_OVERHANG = 7.0  # pivot -> north edge (plate continues past the pivot)
PIVOT_HOLE_DIA = 6.35  # pivot screw clearance hole at the origin

THROUGH_CUT_DEPTH = 40.0  # mid-plane total (both_directions splits it half per
# side of the sketch plane); must exceed 2x any extent crossed


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreatePlaneParameters,
        ExtrusionParameters,
    )

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units (an unsuffixed 216.3 = 216.3 in).
    await set_global(adapter, "PlateT", f"{PLATE_T}mm")
    await set_global(adapter, "HalfWidthS", f"{HALF_WIDTH_S}mm")
    await set_global(adapter, "HalfWidthN", f"{HALF_WIDTH_N}mm")
    await set_global(adapter, "PlateLen", f"{PLATE_LEN}mm")
    await set_global(adapter, "NorthOverhang", f"{NORTH_OVERHANG}mm")
    await set_global(adapter, "PivotHoleDia", f"{PIVOT_HOLE_DIA}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Trapezoid plan on the Top plane (sketch (x, y) -> global (X, -Z), so the
    # north edge at local z +NORTH_OVERHANG is sketch y -NORTH_OVERHANG). The
    # tapered side lines are sloped, so direct-to-DB keeps inference from
    # snapping them.
    plate = SketchDims()
    check("create_sketch plate", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    plan_pts = [
        (-HALF_WIDTH_N, -NORTH_OVERHANG),  # north-west (anchor)
        (HALF_WIDTH_N, -NORTH_OVERHANG),  # north-east
        (HALF_WIDTH_S, PLATE_LEN - NORTH_OVERHANG),  # south-east
        (-HALF_WIDTH_S, PLATE_LEN - NORTH_OVERHANG),  # south-west
    ]
    lines = await add_line_chain(adapter, plan_pts)
    set_sketch_direct_db(adapter, False)
    # Anchor vertex 0 is off both axes -> 2 anchor dims (x, z) first; then seg0
    # north edge (horizontal), seg1 east taper (dx + dy), seg2 south edge
    # (horizontal); seg3 ends at the anchor -> skipped by closure = 6 dims.
    await define_polygon_chain(
        adapter, lines, plan_pts, label="plate plan", dims=plate,
        names=["NorthHalfW", "NorthOverhangDim", "NorthEdge",
               "TaperDx", "PlateLenDim", "SouthEdge"],
        drives=['"HalfWidthN"', '"NorthOverhang"', '2 * "HalfWidthN"',
                '"HalfWidthS" - "HalfWidthN"', '"PlateLen"',
                '2 * "HalfWidthS"'],
    )
    await ensure_fully_defined(adapter, "plate plan")
    check("exit_sketch plate", await adapter.exit_sketch())
    name_last_feature(adapter, "PlateProfile")
    drive_jobs += plate.apply(adapter, "PlateProfile")
    check(
        "extrude plate",
        await adapter.create_extrusion(ExtrusionParameters(depth=PLATE_T)),
    )
    name_last_feature(adapter, "Plate")
    v_plate = (HALF_WIDTH_S + HALF_WIDTH_N) * PLATE_LEN * PLATE_T
    volume = await volume_check(adapter, "plate", v_plate, 0.005 * v_plate)

    # Pivot screw hole at the origin. Origin circle: only the diameter dim.
    hole = SketchDims()
    check("create_sketch pivot hole", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, PIVOT_HOLE_DIA / 2.0, "pivot hole", dims=hole,
        names=("PivotCx", "PivotCz", "PivotHoleDiaDim"),
        drives=(None, None, '"PivotHoleDia"'),
    )
    await ensure_fully_defined(adapter, "pivot hole sketch")
    check("exit_sketch pivot hole", await adapter.exit_sketch())
    name_last_feature(adapter, "PivotHoleProfile")
    drive_jobs += hole.apply(adapter, "PivotHoleProfile")
    check(
        "cut pivot hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "PivotHole")
    v_hole = math.pi * (PIVOT_HOLE_DIA / 2.0) ** 2 * PLATE_T
    volume = await volume_check(adapter, "pivot hole", volume - v_hole, 0.01 * v_hole)

    # Apply the deferred drive equations after the model + a rebuild exist, then
    # re-check: every equation evaluates to the value just built, so geometry
    # must not move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven platform (equations neutral)", volume, 0.01 * v_hole
    )

    # Vertical swing axis through the pivot hole -- the assembly floats the
    # plate and rotates it (and every rider on it) about this axis; the p1
    # disengage DOF. The plate is inserted with a pure Ry incline, which leaves
    # this axis vertical, so a rotation about it is the horizontal swing the
    # book describes.
    await name_bore_axis(adapter, "Front Plane", 0.0, "Right Plane", 0.0, "swing pivot")

    # PlateTop datum: a reference plane ON the top face (+PlateT). The pivot
    # post and tip block seat COINCIDENT to it (FootSeat/DeckTop pattern) so
    # the riders' height mates are flip-free and face-pick-free.
    check(
        "create_plane PlateTop (Top Plane, +PLATE_T)",
        await adapter.create_plane(
            CreatePlaneParameters(mode="offset", base_plane="Top Plane", offset=PLATE_T)
        ),
    )
    name_last_feature(adapter, "PlateTop")

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, PANEL_BLACK)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
