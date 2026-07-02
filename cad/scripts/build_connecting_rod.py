r"""Reproduction script: connecting rod (book ch. 13 pp. 22-25 / ch. 14 p. 29; 20 used).

Black rough-finished rod converting each cam's rotation into the rocker
arm's see-saw: a full ring (strap) riding the Ø30.6 eccentric cam (cast
integral with each cylinder gear), a thin flat shank, and a rounded
TOMBSTONE head (the Y-shaped upper end of the ch14 fan photo) pinned (Ø2)
to the rocker arm's rod-pin hole near the arm's rod-side tip. Centre
distance 147.6655: the rod hangs PLUMB with the arm LEVEL -- the ch30
photos show every rod dropping vertically from the arm tip onto its cam,
the ch14 end views show the 0-crank tip row dead level (cos-mode home =
top of stroke, cam lobe UP), so the pin (127.37 out from the mid-seesaw
pivot) sits directly above the phased lobe centre at machine
(-54.474, 113.437) and the rod length closes that vertical link. The head
is SHORTER than the 16 mm arm depth (10.5 crown-to-shoulder), 10 wide,
crown 2.4 above the pin, angled shoulders narrowing into the 8 shank --
proportions read off the ch14 fan photo against the 16 mm arm-depth
callout. It matches the arm's 2.5 thickness so the pin joint stacks
head-beside-arm inside the 7.06 channel pitch; the M2 "thick stepped tip
blocks" read of p.29 was amplitude-bar feet, not these rods.

Dimensions: cad/DIMENSIONS.md "Chapter 13 - Connecting rods" - centre
distance derived (high), ring bore derived from the cam OD + confirmed on
the p.25 overlay (med), head proportions photo-scaled vs the 16 mm callout
(med), everything else photo-scaled (low).

Layout: ring centre at the origin, shank rising +Y to the head;
thicknesses extruded mid-plane in Z. Build order matters: ring disc,
shank and head are bossed first, then the bore is cut so the strap
opening also trims the shank sliver that dips into it.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_connecting_rod.py
"""

from __future__ import annotations

import sys

from _common import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
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

CENTER_DISTANCE = 147.6655  # cam ring centre -> rocker pin, VERTICAL rod: the
# pin rides the arm's rod-pin hole 127.3738 out from the pivot -- directly
# above the phased cam LOBE (authored (54.474, 113.437) = drum (54.7, 104.8) +
# ECC 8.64 rotated by the +1.5 deg tooth phase, lobe UP at the cos-mode home;
# ch30 photos + GT rocker-corner triangulation put the arm's rod-side end over
# the drum). Solved so the rocker rests LEVEL (arm tilt 0 -- the ch14 end views
# show the 0-crank tip row flat at the TOP of the stroke) with the rod plumb
# (rod tilt 0 by construction). Supersedes 144.75, the same closure at the
# pre-ROM-fit lobe-down phase and -7.82 deg tilt. build_channel_assembly
# imports this as ROD_C2C (imported, NOT copied).
RING_BORE_DIA = 30.8  # ch13 rods: cam OD 30.6 + 0.1 clearance per side; the p.25
# overlay's dashed bore reads Ø29.83 at the (weak) gear-OD scale -- confirms
RING_WALL = 5.0  # ch13 rods: radial strap wall, kept (scaled)
RING_THICKNESS = 3.0  # ch13 rods: sandwich budget (scaled)
SHANK_WIDTH = 8.0  # ch13 rods: silhouette vs 7 mm gear face (scaled)
SHANK_THICKNESS = 2.5  # ch13 rods: thinner than the ring (scaled)
# Tombstone head (the "Y" upper end): proportions from the ch14 fan photo
# scaled by the 16 mm arm-depth callout in the same frame. Rounded crown
# (radius = half width), short vertical cheeks, angled shoulders narrowing
# into the shank. The head is SHORTER than the arm depth and the pin sits
# HIGH in the head / LOW in the arm (crown only 2.4 above the pin).
HEAD_WIDTH = 10.0  # across the cheeks (photo ~10.0)
HEAD_HEIGHT = 10.5  # crown top -> shoulder root (photo ~10.5 < arm depth 16)
HEAD_CROWN_ABOVE_PIN = 2.4  # crown top above the pin centre (photo ~2.4)
HEAD_SHOULDER_RISE = 1.2  # shoulder taper height (width 8 -> 10, photo ~1.2)
HEAD_THICKNESS = 2.5  # = arm thickness: pin joint stacks beside the arm (M6.3)
PIN_HOLE_DIA = 2.0  # ch14: rocker arm rod-end pin
THROUGH_CUT_DEPTH = 20.0  # mid-plane total; > any local thickness

RING_OUTER_RADIUS = RING_BORE_DIA / 2.0 + RING_WALL  # 20.4
SHANK_START_Y = RING_BORE_DIA / 2.0 - 0.5  # overlaps the strap annulus
HEAD_TOP_Y = CENTER_DISTANCE + HEAD_CROWN_ABOVE_PIN  # crown top (150.07)
HEAD_START_Y = HEAD_TOP_Y - HEAD_HEIGHT  # shoulder root: shank ends here (139.57)
HEAD_CROWN_CY = HEAD_TOP_Y - HEAD_WIDTH / 2.0  # crown arc centre (145.07)
SHOULDER_TOP_Y = HEAD_START_Y + HEAD_SHOULDER_RISE  # cheeks start here (140.77)


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
    await set_global(adapter, "HeadWidth", f"{HEAD_WIDTH}mm")
    await set_global(adapter, "HeadHeight", f"{HEAD_HEIGHT}mm")
    await set_global(adapter, "HeadCrownAbovePin", f"{HEAD_CROWN_ABOVE_PIN}mm")
    await set_global(adapter, "HeadShoulderRise", f"{HEAD_SHOULDER_RISE}mm")
    await set_global(adapter, "HeadThickness", f"{HEAD_THICKNESS}mm")
    await set_global(adapter, "PinHoleDia", f"{PIN_HOLE_DIA}mm")
    await set_global(adapter, "RingOuterRadius", '"RingBoreDia" / 2 + "RingWall"')
    await set_global(adapter, "ShankStartY", '"RingBoreDia" / 2 - 0.5mm')
    await set_global(
        adapter, "HeadStartY",
        '"CenterDistance" + "HeadCrownAbovePin" - "HeadHeight"',
    )
    await set_global(
        adapter, "HeadCrownCy",
        '"CenterDistance" + "HeadCrownAbovePin" - "HeadWidth" / 2',
    )

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

    # Shank: flat bar from the strap up to the head's shoulder root. Rectilinear
    # chain emits width, length, then the corner anchor (x, z) -- the corner sits
    # at (-ShankWidth/2, ShankStartY); the anchor X dim is the unsigned half-width.
    shank_sd = SketchDims()
    check("create_sketch shank", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    shank_rect = [
        (-SHANK_WIDTH / 2.0, SHANK_START_Y),
        (SHANK_WIDTH / 2.0, SHANK_START_Y),
        (SHANK_WIDTH / 2.0, HEAD_START_Y),
        (-SHANK_WIDTH / 2.0, HEAD_START_Y),
    ]
    shank = await add_line_chain(adapter, shank_rect)
    set_sketch_direct_db(adapter, False)
    await define_rectilinear_chain(
        adapter, shank, shank_rect, label="shank", dims=shank_sd,
        names=["ShankWidthDim", "ShankLength", "ShankCornerX", "ShankCornerZ"],
        drives=['"ShankWidth"', '"HeadStartY" - "ShankStartY"',
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

    # Tombstone head, pinned beside the rocker arm at assembly (the ch14 fan
    # photo's "Y" upper end): angled shoulders flare the 8 shank to the 10-wide
    # cheeks, short vertical cheeks, and a semicircular crown (R = HeadWidth/2,
    # tangent to the cheeks -- add_arc runs CCW start->end, so right-cheek-top ->
    # left-cheek-top bows over the TOP). Because the crown centre sits on the
    # sketch axis (x 0) with radius = the cheek half-width, each cheek-top lands
    # at the crown's equator by construction (x = R forces y = centre y).
    # Dim EMISSION ORDER (each recorded as its display dim is created): shoulder
    # width (= ShankWidth), the shoulder-root corner anchor (X half-width, then
    # Z = HeadStartY), crown radius, crown-centre height (x on-axis, so
    # anchor_point_to_origin emits ONE dim), the two shoulder rises, the two
    # cheek half-width offsets. Bottom horizontal + cheek verticals are
    # RELATIONS, not dims -- exactly 14 coordinate constraints for the 7 free
    # vertices, no redundancy.
    head_sd = SketchDims()
    check("create_sketch head", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    hw, sw = HEAD_WIDTH / 2.0, SHANK_WIDTH / 2.0
    head_bottom = check(
        "head bottom",
        await adapter.add_line(-sw, HEAD_START_Y, sw, HEAD_START_Y),
    )
    head_sh_r = check(
        "head shoulder right",
        await adapter.add_line(sw, HEAD_START_Y, hw, SHOULDER_TOP_Y),
    )
    head_cheek_r = check(
        "head cheek right",
        await adapter.add_line(hw, SHOULDER_TOP_Y, hw, HEAD_CROWN_CY),
    )
    head_crown = check(
        "head crown",
        await adapter.add_arc(0.0, HEAD_CROWN_CY, hw, HEAD_CROWN_CY, -hw, HEAD_CROWN_CY),
    )
    head_cheek_l = check(
        "head cheek left",
        await adapter.add_line(-hw, HEAD_CROWN_CY, -hw, SHOULDER_TOP_Y),
    )
    check(
        "head shoulder left",
        await adapter.add_line(-hw, SHOULDER_TOP_Y, -sw, HEAD_START_Y),
    )
    set_sketch_direct_db(adapter, False)
    for ent, relation in (
        (head_bottom, "horizontal"),
        (head_cheek_r, "vertical"),
        (head_cheek_l, "vertical"),
    ):
        check(f"head {relation}", await adapter.add_sketch_constraint(ent, None, relation))
    check(
        "dimension head bottom width",
        await adapter.add_sketch_dimension(head_bottom, None, "linear", SHANK_WIDTH),
    )
    head_sd.record("HeadBottomWidth", '"ShankWidth"')
    await anchor_point_to_origin(
        adapter, f"{head_bottom}.start", -sw, HEAD_START_Y, "head shoulder root"
    )
    head_sd.record("HeadAnchorX", '"ShankWidth" / 2')
    head_sd.record("HeadAnchorZ", '"HeadStartY"')
    check(
        "dimension crown radius",
        await adapter.add_sketch_dimension(head_crown, None, "radial", hw),
    )
    head_sd.record("HeadCrownR", '"HeadWidth" / 2')
    await anchor_point_to_origin(
        adapter, f"{head_crown}.center", 0.0, HEAD_CROWN_CY, "crown centre"
    )
    head_sd.record("HeadCrownCyDim", '"HeadCrownCy"')
    check(
        "dimension shoulder rise right",
        await adapter.add_sketch_dimension(
            f"{head_sh_r}.end", f"{head_bottom}.end", "vertical_distance",
            HEAD_SHOULDER_RISE,
        ),
    )
    head_sd.record("HeadShoulderRiseR", '"HeadShoulderRise"')
    check(
        "dimension shoulder rise left",
        await adapter.add_sketch_dimension(
            f"{head_cheek_l}.end", f"{head_bottom}.start", "vertical_distance",
            HEAD_SHOULDER_RISE,
        ),
    )
    head_sd.record("HeadShoulderRiseL", '"HeadShoulderRise"')
    check(
        "dimension cheek right x",
        await adapter.add_sketch_dimension(
            f"{head_cheek_r}.start", "origin", "horizontal_distance", hw
        ),
    )
    head_sd.record("HeadCheekRX", '"HeadWidth" / 2')
    check(
        "dimension cheek left x",
        await adapter.add_sketch_dimension(
            f"{head_cheek_l}.start", "origin", "horizontal_distance", hw
        ),
    )
    head_sd.record("HeadCheekLX", '"HeadWidth" / 2')
    await ensure_fully_defined(adapter, "head sketch")
    check("exit_sketch head", await adapter.exit_sketch())
    name_last_feature(adapter, "HeadProfile")
    drive_jobs += head_sd.apply(adapter, "HeadProfile")
    check(
        "extrude head",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=HEAD_THICKNESS, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Head")
    res = await adapter.get_mass_properties()
    _telemetry.info(f"volume after bosses: {res.data.volume:.1f} mm^3")
    # disc ~3922 + shank ~2467 + head ~233 (shoulder trapezoid 10.8 + cheeks
    # 43.0 + crown semicircle 39.3 = 93.1 mm^2 x 2.5) - overlap; Phase 3
    # rebuild confirms

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

    # Rocker pin hole through the head (high in the crown: 2.4 below the crown
    # top). Off-axis circle at (0, 147.67): the X is on-axis (a relation), so
    # only the Z centre + diameter are dims. The Z dim is an unsigned distance
    # and positive, so it drives directly.
    pin_sd = SketchDims()
    check("create_sketch pin hole", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)  # inference near the head edges
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
    # Axis1 = strap bore on the cam (origin), Axis2 = rocker pin bore (0, 147.67).
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
