r"""Reproduction script: crank arm (book ch. 11, pp. 12-15).

The metal crank arm that drives the machine: round O14 boss at the
crankshaft end (bored for the shaft and cross-drilled for the removable
tapered pin; the bar's own full-radius end would leave 0.24 mm walls around
the 9.525 bore), straight 10-wide bar, square end carrying the handle pivot,
and a fiducial dimple for alignment. The wooden handle and the tapered pin are
separate parts (build_crank_handle.py / build_crank_pin.py); the chain
eyelet (chain lost) is omitted.

Dimensions: cad/DIMENSIONS.md "Chapter 11" — all photo-scaled (low) except
the legacy 3/8" crankshaft bore (med).

Layout: arm length along +X from the origin (shaft bore axis = global Z
through the origin), thickness extruded +Z (0..ARM_THICKNESS). The cross-pin hole runs
along global Y at mid-thickness: probed live, a Top-plane sketch maps
(x, y) -> global (X, -Z), so the hole circle sits at sketch
(0, -ARM_THICKNESS/2).
Through-cuts use mid-plane blind cuts (depth > extent) because the
ThroughAll+both_directions combination fails live on SW 2026 (MCP issue
#38); the dimple uses a mid-plane cut of twice its depth so the cut
direction never matters.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_crank_arm.py
"""

from __future__ import annotations

import sys

from _common import (
    IN,
    SketchDims,
    add_line_chain,
    apply_material,
    name_bore_axis,
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
    volume_check,
)

import _telemetry

PART_NAME = "crank-arm"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring

ARM_C2C = 66.0  # DIMENSIONS.md ch11: shaft-to-handle-pivot centres -- REDERIVED
# from the ch30 eight-views (angle 90 side view, scaled to the 280 mm base depth):
# the crank hangs straight down, handle pivot 66 mm below the crankshaft axis,
# landing the handle ~10 mm above the base top. The former 150 (cone-axial scaled,
# low) was >2x too long -- a down-pointing 150 arm would drive the handle below
# the table (med).
ARM_WIDTH = 10.0  # re-measured 2026-07-08 on the ch11 macro + ch30 p008 (both
# anchored on the handle collar O11 / handle O22): the bar reads 9-10 wide;
# the former 16 was ~60% over (med)
ARM_THICKNESS = 5.0  # same re-measure: the ch11 edge-on face reads 4-5 (was 8)
BOSS_DIA = 14.0  # round boss at the shaft end: the 9.525 bore through a
# full-radius 10 bar would leave 0.24 walls, so the end flares to a O14 disc
# (2.24 walls) -- reads as the slightly-flared rounded end in the ch11 macro
SQUARE_END_OVERHANG = 10.0  # DIMENSIONS.md ch11: square end past the pivot (low)
SHAFT_BORE_DIA = 0.375 * IN  # 9.525: 3/8" crankshaft (med); the legacy 9.5
# rounding left the bore 0.025 smaller than the shaft (caught in M6.2)
PIVOT_BORE_DIA = 6.0  # DIMENSIONS.md ch11: handle pivot screw (low)
DIMPLE_DIA = 5.0  # fiducial indentation, rescaled with the slimmer bar (an 8
# dimple on a 10 bar would leave 1 mm edge webs)
DIMPLE_DEPTH = 0.5  # DIMENSIONS.md ch11: fiducial indentation (low)
DIMPLE_X = 30.0  # DIMENSIONS.md ch11: on the arm near the boss (low)
PIN_HOLE_DIA = 5.0  # DIMENSIONS.md ch11: tapered-pin cross-hole, small end (low)

ARM_END_X = ARM_C2C + SQUARE_END_OVERHANG
HALF_WIDTH = ARM_WIDTH / 2.0
THROUGH_CUT_DEPTH = 40.0  # mid-plane total; > any extent it crosses


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success else float("nan")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): every module constant above as a named
    # global that drives the dimensions below. The mm suffix is load-bearing --
    # this is an INCH document and the equation manager reads BARE numbers in
    # document units, so an unsuffixed 66 would be read as 66 inches and blow the
    # part up 25.4x. ArmEndX is a derived span (equation of the primitives) so the
    # square end stays SQUARE_END_OVERHANG past the pivot when either changes.
    await set_global(adapter, "ArmC2C", f"{ARM_C2C}mm")
    await set_global(adapter, "ArmWidth", f"{ARM_WIDTH}mm")
    await set_global(adapter, "BossDia", f"{BOSS_DIA}mm")
    await set_global(adapter, "ArmThickness", f"{ARM_THICKNESS}mm")
    await set_global(adapter, "SquareEndOverhang", f"{SQUARE_END_OVERHANG}mm")
    await set_global(adapter, "ShaftBoreDia", f"{SHAFT_BORE_DIA}mm")
    await set_global(adapter, "PivotBoreDia", f"{PIVOT_BORE_DIA}mm")
    await set_global(adapter, "DimpleDia", f"{DIMPLE_DIA}mm")
    await set_global(adapter, "DimpleDepth", f"{DIMPLE_DEPTH}mm")
    await set_global(adapter, "DimpleX", f"{DIMPLE_X}mm")
    await set_global(adapter, "PinHoleDia", f"{PIN_HOLE_DIA}mm")
    await set_global(adapter, "ArmEndX", '"ArmC2C" + "SquareEndOverhang"')

    # Each sketch declares its dim names + drive equations as it is built; a
    # per-sketch SketchDims records each dim in emission order, then apply()
    # renames them and collects the drive jobs run in one deferred batch at the
    # end (every equation target must resolve against the finished model).
    drive_jobs: list[tuple[str, str]] = []

    # Arm outline: full-radius boss cap (arc about the origin) + 3 lines.
    outline = SketchDims()
    check("create_sketch outline", await adapter.create_sketch("Front"))
    arc = check(
        "add_arc boss cap",
        await adapter.add_arc(0.0, 0.0, 0.0, HALF_WIDTH, 0.0, -HALF_WIDTH),
    )
    bottom, right, top = await add_line_chain(
        adapter,
        [
            (0.0, -HALF_WIDTH),
            (ARM_END_X, -HALF_WIDTH),
            (ARM_END_X, HALF_WIDTH),
            (0.0, HALF_WIDTH),
        ],
        close=False,
    )
    check("constraint horizontal bottom", await adapter.add_sketch_constraint(bottom, None, "horizontal"))
    check("constraint vertical right", await adapter.add_sketch_constraint(right, None, "vertical"))
    check("constraint horizontal top", await adapter.add_sketch_constraint(top, None, "horizontal"))
    # Manual dims recorded into SketchDims as created (creation order): the arm
    # length on the bottom line, then the boss-cap radius.
    check(
        f"dimension arm length = {ARM_END_X:g}",
        await adapter.add_sketch_dimension(bottom, None, "linear", ARM_END_X),
    )
    outline.record("ArmEndX", '"ArmEndX"')
    # Boss cap: centre at the origin + radius + both ends on the Y axis
    # fully pin the semicircle; the merged chain follows.
    check(
        "boss centre -> origin",
        await adapter.add_sketch_constraint(f"{arc}.center", "origin", "coincident"),
    )
    check("boss radius", await adapter.add_sketch_dimension(arc, None, "radial", HALF_WIDTH))
    outline.record("BossRadius", '"ArmWidth" / 2')
    for point in (f"{arc}.start", f"{arc}.end"):
        check(
            f"{point} on Y axis",
            await adapter.add_sketch_constraint(point, "origin", "vertical_points"),
        )
    await ensure_fully_defined(adapter, "arm outline")
    check("exit_sketch outline", await adapter.exit_sketch())
    name_last_feature(adapter, "ArmOutline")
    drive_jobs += outline.apply(adapter, "ArmOutline")
    check(
        "extrude arm",
        await adapter.create_extrusion(ExtrusionParameters(depth=ARM_THICKNESS)),
    )
    name_last_feature(adapter, "Arm")
    vol = await _volume(adapter)
    _telemetry.info(f"volume after extrude: {vol:.1f} mm^3")

    # Shaft boss: O14 disc at the origin, same thickness as the bar, merged.
    # The 9.525 shaft bore through the 10-wide bar alone would leave 0.24 mm
    # walls; the flared round end is visible in the ch11 macro.
    boss = SketchDims()
    check("create_sketch boss", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, BOSS_DIA / 2.0, "shaft boss", dims=boss,
        names=("BossX", "BossZ", "BossDiaDim"),
        drives=(None, None, '"BossDia"'),
    )
    await ensure_fully_defined(adapter, "boss sketch")
    check("exit_sketch boss", await adapter.exit_sketch())
    name_last_feature(adapter, "BossProfile")
    drive_jobs += boss.apply(adapter, "BossProfile")
    check(
        "extrude boss",
        await adapter.create_extrusion(ExtrusionParameters(depth=ARM_THICKNESS)),
    )
    name_last_feature(adapter, "Boss")
    vol = await _volume(adapter)
    _telemetry.info(f"volume after boss: {vol:.1f} mm^3")

    # Shaft bore + handle pivot bore, one through-cut. The shaft bore sits on the
    # origin (only its diameter is a dim); the pivot bore is off-axis at +X
    # (an X centre dim, then its diameter).
    bores = SketchDims()
    check("create_sketch bores", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, SHAFT_BORE_DIA / 2.0, "shaft bore", dims=bores,
        names=("ShaftBoreX", "ShaftBoreZ", "ShaftBoreDia"),
        drives=(None, None, '"ShaftBoreDia"'),
    )
    await define_circle(
        adapter, ARM_C2C, 0.0, PIVOT_BORE_DIA / 2.0, "pivot bore", dims=bores,
        names=("PivotBoreX", "PivotBoreZ", "PivotBoreDia"),
        drives=('"ArmC2C"', None, '"PivotBoreDia"'),
    )
    await ensure_fully_defined(adapter, "bores sketch")
    check("exit_sketch bores", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bores.apply(adapter, "BoreProfile")
    check(
        "cut bores",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Bores")
    vol = await _volume(adapter)
    _telemetry.info(f"volume after bores: {vol:.1f} mm^3")

    # Fiducial dimple on the Z=0 face (which face carries it is arbitrary
    # until assembly). Mid-plane cut of 2x depth: only the +Z half removes
    # material, so the result is DIMPLE_DEPTH regardless of cut direction.
    dimple = SketchDims()
    check("create_sketch dimple", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, DIMPLE_X, 0.0, DIMPLE_DIA / 2.0, "dimple", dims=dimple,
        names=("DimpleX", "DimpleZ", "DimpleDia"),
        drives=('"DimpleX"', None, '"DimpleDia"'),
    )
    await ensure_fully_defined(adapter, "dimple sketch")
    check("exit_sketch dimple", await adapter.exit_sketch())
    name_last_feature(adapter, "DimpleProfile")
    drive_jobs += dimple.apply(adapter, "DimpleProfile")
    check(
        "cut dimple",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * DIMPLE_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Dimple")
    vol = await _volume(adapter)
    _telemetry.info(f"volume after dimple: {vol:.1f} mm^3")

    # Tapered-pin cross-hole along global Y through boss and shaft bore at
    # mid-thickness (global Z = ARM_THICKNESS/2 -> Top sketch y = -Z).
    # On-axis in X (sketch x = 0), off-axis in Z (sketch y = -ArmThickness/2):
    # define_circle emits a Z centre dim then the diameter. The centre sits at a
    # NEGATIVE sketch y, but the dim displays the magnitude, so its drive must
    # evaluate POSITIVE -- '"ArmThickness" / 2', not the signed value.
    pin_hole = SketchDims()
    check("create_sketch pin hole", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, -ARM_THICKNESS / 2.0, PIN_HOLE_DIA / 2.0, "pin hole",
        dims=pin_hole,
        names=("PinHoleX", "PinHoleZ", "PinHoleDia"),
        drives=(None, '"ArmThickness" / 2', '"PinHoleDia"'),
    )
    await ensure_fully_defined(adapter, "pin hole sketch")
    check("exit_sketch pin hole", await adapter.exit_sketch())
    name_last_feature(adapter, "PinHoleProfile")
    drive_jobs += pin_hole.apply(adapter, "PinHoleProfile")
    check(
        "cut pin hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "PinHole")
    vol = await _volume(adapter)
    _telemetry.info(f"volume after pin hole: {vol:.1f} mm^3")

    # Apply the deferred drive equations now -- after the whole model + a rebuild
    # exists, so every target resolves. Each equation evaluates to the value just
    # built, so the geometry must not move; the as-built volume captured above is
    # the neutrality reference for the re-check below.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven crank arm (equations neutral)", vol, 0.001 * vol)

    # Named bore/central axis for view-independent assembly mate
    # selection (M6 mated-DOF drive train). Axis1 = shaft bore (on origin);
    # Axis2 = the handle PIVOT bore at +X (ARM_C2C), so the drive-train assembly
    # can journal the crank handle COAXIAL to its real pivot pin (replacing the
    # handle's lock with a semantic pin joint). Order is load-bearing: the shaft
    # axis is created first so it stays Axis1@<arm>.
    await name_bore_axis(adapter, "Top Plane", 0.0, "Right Plane", 0.0, "shaft bore axis")
    pivot_axis = await name_bore_axis(
        adapter, "Top Plane", 0.0, "Right Plane", ARM_C2C, "pivot bore axis"
    )
    _telemetry.info(f"handle pivot bore axis -> {pivot_axis} (expect Axis2)")

    # HandleSeat datum: the plate face OPPOSITE the origin plane (z =
    # ARM_THICKNESS). The chirality-mirrored drive-train maps part +z to
    # machine -z, so this is the arm's SOUTH face -- the crank handle's brass
    # collar butts flush against it (its Right/origin plane mates COINCIDENT
    # here, the flip-free seat idiom; seating on Front@arm instead buried the
    # collar inside the plate, 502 mm^3, 2026-07-05).
    from solidworks_mcp.adapters.base import CreatePlaneParameters

    check(
        f"create_plane HandleSeat (Front Plane, +{ARM_THICKNESS})",
        await adapter.create_plane(CreatePlaneParameters(
            mode="offset", base_plane="Front Plane", offset=ARM_THICKNESS,
        )),
    )
    name_last_feature(adapter, "HandleSeat")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
