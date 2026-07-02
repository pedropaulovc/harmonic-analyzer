r"""Reproduction script: connecting rod (book ch. 13 pp. 22-25 / ch. 14 p. 29; 20 used).

Black rough-finished rod converting each cam's rotation into the rocker
arm's see-saw: a full ring (strap) riding the Ø30.6 eccentric cam (cast
integral with each cylinder gear), a thin flat shank, and a flattened tip
strap pinned (Ø2) to the rocker arm's rod-pin hole near the arm's rod-side
tip. Centre distance 144.75: the rod hangs PLUMB -- the ch30 photos show
every rod dropping vertically from the arm tip onto its cam, so the pin
(127.49 out from the mid-seesaw pivot) sits directly above the cam drum at
machine (-54.7, 104.8), and the rod length is solved to keep the rocker
rest tilt (-7.82 deg). The tip strap matches the arm's
2.5 thickness so the pin joint stacks strap-beside-arm inside the 7.06
channel pitch; the M2 "thick stepped tip blocks" read of p.29 was
amplitude-bar feet, not these rods.

Dimensions: cad/DIMENSIONS.md "Chapter 13 - Connecting rods" - centre
distance derived (high), ring bore derived from the cam OD (med),
everything else photo-scaled (low).

Layout: ring centre at the origin, shank rising +Y to the tip block;
thicknesses extruded mid-plane in Z. Build order matters: ring disc,
shank and tip block are bossed first, then the bore is cut so the strap
opening also trims the shank sliver that dips into it.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_connecting_rod.py
"""

from __future__ import annotations

import sys

from _common import (
    SketchDims,
    add_line_chain,
    apply_material,
    check,
    define_circle,
    define_rectilinear_chain,
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

import _telemetry

PART_NAME = "connecting-rod"
MATERIAL = "Gray Cast Iron"  # see _common.apply_material docstring

CENTER_DISTANCE = 144.75  # cam ring centre -> rocker pin, VERTICAL rod: the pin
# rides the arm's rod-pin hole 127.49 out from the pivot -- directly above the
# phased cam centre (authored (54.78, 101.74); ch30 photos + GT rocker-corner
# triangulation, which put the arm's rod-side end over the drum and refuted the
# oblique 180.83 read -- that "line-2 photogrammetry" reading had the drum on
# the far side of the rocker support). 144.75 is solved to preserve the rocker
# rest tilt (arm tilt -7.82 deg) bit-close (pin (54.78, 246.49)), so the whole
# downstream bar/lever/spring chain is untouched; the rod itself is shorter and
# hangs plumb (rod tilt ~0.001 deg). MUST stay in sync with
# build_channel_assembly.ROD_C2C.
RING_BORE_DIA = 30.8  # ch13 rods: cam OD 30.6 + 0.1 clearance per side (cam scaled 0.6022)
RING_WALL = 5.0  # ch13 rods: radial strap wall, kept (scaled)
RING_THICKNESS = 3.0  # ch13 rods: sandwich budget (scaled)
SHANK_WIDTH = 8.0  # ch13 rods: silhouette vs 7 mm gear face (scaled)
SHANK_THICKNESS = 2.5  # ch13 rods: thinner than the ring (scaled)
BLOCK_WIDTH = 10.0  # flattened tip strap (scaled)
BLOCK_LENGTH = 18.0
BLOCK_THICKNESS = 2.5  # = arm thickness: pin joint stacks beside the arm (M6.3)
PIN_HOLE_DIA = 2.0  # ch14: rocker arm rod-end pin
THROUGH_CUT_DEPTH = 20.0  # mid-plane total; > any local thickness

RING_OUTER_RADIUS = RING_BORE_DIA / 2.0 + RING_WALL  # 20.4
SHANK_START_Y = RING_BORE_DIA / 2.0 - 0.5  # overlaps the strap annulus
BLOCK_START_Y = CENTER_DISTANCE - BLOCK_LENGTH / 2.0  # pin hole centred


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations) for every module constant; derived spans
    # (ring outer radius, the shank/block start heights) are equations of those
    # primitives, so a knob edit keeps the strap-to-pin geometry consistent. The
    # mm suffix is load-bearing -- this is an INCH document and the equation
    # manager reads BARE numbers in document units (an unsuffixed 127 = 127 in,
    # blowing the part up 25.4x).
    await set_global(adapter, "CenterDistance", f"{CENTER_DISTANCE}mm")
    await set_global(adapter, "RingBoreDia", f"{RING_BORE_DIA}mm")
    await set_global(adapter, "RingWall", f"{RING_WALL}mm")
    await set_global(adapter, "RingThickness", f"{RING_THICKNESS}mm")
    await set_global(adapter, "ShankWidth", f"{SHANK_WIDTH}mm")
    await set_global(adapter, "ShankThickness", f"{SHANK_THICKNESS}mm")
    await set_global(adapter, "BlockWidth", f"{BLOCK_WIDTH}mm")
    await set_global(adapter, "BlockLength", f"{BLOCK_LENGTH}mm")
    await set_global(adapter, "BlockThickness", f"{BLOCK_THICKNESS}mm")
    await set_global(adapter, "PinHoleDia", f"{PIN_HOLE_DIA}mm")
    await set_global(adapter, "RingOuterRadius", '"RingBoreDia" / 2 + "RingWall"')
    await set_global(adapter, "ShankStartY", '"RingBoreDia" / 2 - 0.5mm')
    await set_global(adapter, "BlockStartY", '"CenterDistance" - "BlockLength" / 2')

    # Each sketch records its dim names + drive equations into a per-sketch
    # SketchDims in helper emission order; the drives are collected and applied in
    # one deferred batch at the end (every target resolves against the finished
    # model).
    drive_jobs: list[tuple[str, str]] = []

    # Ring disc (bore is cut last so it also trims the shank sliver). On-axis
    # circle: only the diameter is a dim (centre is a coincident relation).
    ring_disc = SketchDims()
    check("create_sketch ring disc", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, RING_OUTER_RADIUS, "ring outer", dims=ring_disc,
        names=("RingCx", "RingCz", "RingOuterDia"),
        drives=(None, None, '2 * "RingOuterRadius"'),
    )
    await ensure_fully_defined(adapter, "ring disc sketch")
    check("exit_sketch ring disc", await adapter.exit_sketch())
    name_last_feature(adapter, "RingDiscProfile")
    drive_jobs += ring_disc.apply(adapter, "RingDiscProfile")
    check(
        "extrude ring disc",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=RING_THICKNESS, both_directions=True)
        ),
    )
    name_last_feature(adapter, "RingDisc")

    # Shank: flat bar from the strap up to the tip block. Rectilinear chain emits
    # width, length, then the corner anchor (x, z) -- the corner sits at
    # (-ShankWidth/2, ShankStartY); the anchor X dim is the unsigned half-width.
    shank_sd = SketchDims()
    check("create_sketch shank", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    shank_rect = [
        (-SHANK_WIDTH / 2.0, SHANK_START_Y),
        (SHANK_WIDTH / 2.0, SHANK_START_Y),
        (SHANK_WIDTH / 2.0, BLOCK_START_Y),
        (-SHANK_WIDTH / 2.0, BLOCK_START_Y),
    ]
    shank = await add_line_chain(adapter, shank_rect)
    set_sketch_direct_db(adapter, False)
    await define_rectilinear_chain(
        adapter, shank, shank_rect, label="shank", dims=shank_sd,
        names=["ShankWidthDim", "ShankLength", "ShankCornerX", "ShankCornerZ"],
        drives=['"ShankWidth"', '"BlockStartY" - "ShankStartY"',
                '"ShankWidth" / 2', '"ShankStartY"'],
    )
    await ensure_fully_defined(adapter, "shank sketch")
    check("exit_sketch shank", await adapter.exit_sketch())
    name_last_feature(adapter, "ShankProfile")
    drive_jobs += shank_sd.apply(adapter, "ShankProfile")
    check(
        "extrude shank",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=SHANK_THICKNESS, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Shank")

    # Flattened tip strap, pinned beside the rocker arm at assembly. Same chain
    # emission as the shank: width, length, corner-X (unsigned half-width),
    # corner-Z (= BlockStartY).
    block_sd = SketchDims()
    check("create_sketch tip block", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    block_rect = [
        (-BLOCK_WIDTH / 2.0, BLOCK_START_Y),
        (BLOCK_WIDTH / 2.0, BLOCK_START_Y),
        (BLOCK_WIDTH / 2.0, BLOCK_START_Y + BLOCK_LENGTH),
        (-BLOCK_WIDTH / 2.0, BLOCK_START_Y + BLOCK_LENGTH),
    ]
    block = await add_line_chain(adapter, block_rect)
    set_sketch_direct_db(adapter, False)
    await define_rectilinear_chain(
        adapter, block, block_rect, label="tip block", dims=block_sd,
        names=["BlockWidthDim", "BlockLengthDim", "BlockCornerX", "BlockCornerZ"],
        drives=['"BlockWidth"', '"BlockLength"', '"BlockWidth" / 2', '"BlockStartY"'],
    )
    await ensure_fully_defined(adapter, "tip block sketch")
    check("exit_sketch tip block", await adapter.exit_sketch())
    name_last_feature(adapter, "TipBlockProfile")
    drive_jobs += block_sd.apply(adapter, "TipBlockProfile")
    check(
        "extrude tip block",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=BLOCK_THICKNESS, both_directions=True)
        ),
    )
    name_last_feature(adapter, "TipBlock")
    res = await adapter.get_mass_properties()
    _telemetry.info(f"volume after bosses: {res.data.volume:.1f} mm^3")
    # ring strap shrank with the 0.6022-scaled cam (bore 30.8, outer r 20.4) ->
    # disc ~3922 + shank ~2062 + block ~450 - overlap; Phase 3 rebuild confirms

    # Strap bore - rides the eccentric cam. On-axis circle: diameter only.
    bore_sd = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, RING_BORE_DIA / 2.0, "strap bore", dims=bore_sd,
        names=("StrapBoreCx", "StrapBoreCz", "StrapBoreDia"),
        drives=(None, None, '"RingBoreDia"'),
    )
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "StrapBoreProfile")
    drive_jobs += bore_sd.apply(adapter, "StrapBoreProfile")
    check(
        "cut strap bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "StrapBore")

    # Rocker pin hole through the tip block. Off-axis circle at (0, 127): the X is
    # on-axis (a relation), so only the Z centre + diameter are dims. The Z dim is
    # an unsigned distance and 127 is positive, so it drives directly.
    pin_sd = SketchDims()
    check("create_sketch pin hole", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)  # inference near the block edges
    await define_circle(
        adapter, 0.0, CENTER_DISTANCE, PIN_HOLE_DIA / 2.0, "pin hole", dims=pin_sd,
        names=("PinCx", "PinCz", "PinHoleDiaDim"),
        drives=(None, '"CenterDistance"', '"PinHoleDia"'),
    )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "pin hole sketch")
    check("exit_sketch pin hole", await adapter.exit_sketch())
    name_last_feature(adapter, "PinHoleProfile")
    drive_jobs += pin_sd.apply(adapter, "PinHoleProfile")
    check(
        "cut pin hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "PinHole")
    res = await adapter.get_mass_properties()
    v_built = float(res.data.volume)
    _telemetry.info(f"volume after cuts: {v_built:.1f} mm^3")
    # bore now -2234 (r 15.4 x 3) - sliver - pin; Phase 3 rebuild confirms

    # Named bore axes for assembly mates (view-independent name selection):
    # Axis1 = strap bore on the cam (origin), Axis2 = rocker pin bore (0, 127).
    await name_bore_axis(adapter, "Right Plane", 0.0, "Top Plane", 0.0, "strap bore")
    await name_bore_axis(
        adapter, "Right Plane", 0.0, "Top Plane", CENTER_DISTANCE, "rod pin bore"
    )

    # Apply the deferred drive equations after the whole model + a rebuild exists,
    # so every target resolves. Each equation evaluates to the as-built value (the
    # rod's volume has no tidy closed form, so the neutrality gate asserts the
    # post-drive volume equals the captured as-built volume): geometry must not
    # move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven connecting rod (equations neutral)", v_built, 0.001 * v_built
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
