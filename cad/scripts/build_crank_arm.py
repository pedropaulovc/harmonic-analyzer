r"""Reproduction script: crank arm (book ch. 11, pp. 12-15).

The metal crank arm that drives the machine: full-radius boss at the
crankshaft end (bored for the shaft and cross-drilled for the removable
tapered pin), straight arm, square end carrying the handle pivot, and a
fiducial dimple for alignment. The wooden handle and the tapered pin are
separate parts (build_crank_handle.py / build_crank_pin.py); the chain
eyelet (chain lost) is omitted.

Dimensions: cad/DIMENSIONS.md "Chapter 11" — all photo-scaled (low) except
the legacy 3/8" crankshaft bore (med).

Layout: arm length along +X from the origin (shaft bore axis = global Z
through the origin), thickness extruded +Z (0..8). The cross-pin hole runs
along global Y at mid-thickness: probed live, a Top-plane sketch maps
(x, y) -> global (X, -Z), so the hole circle sits at sketch (0, -4).
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
    SketchDims,
    add_line_chain,
    apply_material,
    name_bore_axis,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)
from _holes import HoleSpec, wizard_holes

import _telemetry
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
)
from _fit_limits import deviations
from crank_arm_spec import (
    ARM_C2C,
    ARM_END_X,
    ARM_THICKNESS,
    ARM_WIDTH,
    DIMPLE_DEPTH,
    DIMPLE_DIA,
    DIMPLE_X,
    DRAWING_NOTES,
    DRAWING_DIMENSIONS,
    HALF_WIDTH,
    ISOMETRIC_VIEW_NOTE,
    SHAFT_BORE_DIA,
    SHAFT_BORE_BAND,
    SQUARE_END_OVERHANG,
)

PART_NAME = "crank-arm"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring

# (The old PivotBoreDia Ø6.0 and PinHoleDia Ø5.0 constants are gone: the handle-
# pivot hole and the tapered-pin cross-hole are now native Hole Wizard features
# whose diameters come from the drill standard -- 15/64 (Ø5.953) and #14 (Ø4.623)
# -- not equation-driven sketch dims. The 3/8 shaft bore stays a reamed circle
# cut: it is a precision running fit, not a twist-drill hole.)

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
    await set_global(adapter, "ArmThickness", f"{ARM_THICKNESS}mm")
    await set_global(adapter, "SquareEndOverhang", f"{SQUARE_END_OVERHANG}mm")
    await set_global(adapter, "ShaftBoreDia", f"{SHAFT_BORE_DIA}mm")
    await set_global(adapter, "DimpleDia", f"{DIMPLE_DIA}mm")
    await set_global(adapter, "DimpleDepth", f"{DIMPLE_DEPTH}mm")
    await set_global(adapter, "DimpleX", f"{DIMPLE_X}mm")
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
    depth_dim = name_dimensions(adapter, "Arm", ["Depth"])
    drive_jobs += [(depth_dim[0], '"ArmThickness"')]
    vol = await _volume(adapter)
    _telemetry.info(f"volume after extrude: {vol:.1f} mm^3")

    # Shaft bore: the 3/8 reamed journal the crankshaft runs in -- a precision
    # running fit, kept a plain circle cut (NOT a twist-drill Hole Wizard hole).
    # On the origin, so only its diameter is a dim.
    shaft_bore = SketchDims()
    check("create_sketch shaft bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, SHAFT_BORE_DIA / 2.0, "shaft bore", dims=shaft_bore,
        names=("ShaftBoreX", "ShaftBoreZ", "ShaftBoreDia"),
        drives=(None, None, '"ShaftBoreDia"'),
    )
    await ensure_fully_defined(adapter, "shaft bore sketch")
    check("exit_sketch shaft bore", await adapter.exit_sketch())
    name_last_feature(adapter, "ShaftBoreProfile")
    drive_jobs += shaft_bore.apply(adapter, "ShaftBoreProfile")
    check(
        "cut shaft bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "ShaftBore")

    # Handle-pivot hole: was a plain Ø6.0 cut, now a native Hole Wizard 15/64
    # fractional drill (Ø5.953) at the handle-pivot centre (ARM_C2C), drilled +Z
    # through the 8 mm plate (memory/fastener-policy-us-customary). Cut while the
    # body is still prismatic (~15 faces) -- wizard_holes enumerates every face.
    pivot_cut = wizard_holes(
        adapter,
        HoleSpec("drilled_fractional", "15/64"),
        [[ARM_C2C, 0.0, ARM_THICKNESS]],
        (0.0, 0.0, 1.0),
        "handle-pivot hole (15/64)",
        name="PivotBore",
        placement_dims=[(("PivotBoreX", '"ArmC2C"'), (None, None))],
    )
    drive_jobs += pivot_cut.placement_drive_jobs
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

    # Tapered-pin cross-hole: pilot below the No. 2 taper pin's small end, then
    # taper-reamed with the shaft at assembly.
    # number drill (Ø4.978) along global Y through the boss + shaft bore at
    # mid-thickness (memory/fastener-policy-us-customary). Drilled from the +Y
    # side face (a pristine planar face, normal +Y) at (x 0, z ArmThickness/2);
    # through-all is geometrically identical to the old mid-plane cut.
    pin_cut = wizard_holes(
        adapter,
        HoleSpec("drilled_number", "#14"),
        [[0.0, HALF_WIDTH, ARM_THICKNESS / 2.0]],
        (0.0, 1.0, 0.0),
        "tapered-pin cross-hole (#14)",
        name="PinHole",
        placement_dims=[((None, None), ("PinHoleZ", '"ArmThickness" / 2'))],
    )
    drive_jobs += pin_cut.placement_drive_jobs
    vol = await _volume(adapter)
    _telemetry.info(f"volume after pin hole: {vol:.1f} mm^3")

    # Named bore/central axis for view-independent assembly mate
    # selection (M6 mated-DOF drive train). Axis1 = shaft bore (on origin);
    # Axis2 = the handle PIVOT bore at +X (ARM_C2C), so the drive-train assembly
    # can journal the crank handle COAXIAL to its real pivot pin (replacing the
    # handle's lock with a semantic pin joint). Order is load-bearing: the shaft
    # axis is created first so it stays Axis1@<arm>.
    await name_bore_axis(adapter, "Top Plane", 0.0, "Right Plane", 0.0, "shaft bore axis")
    pivot_axis = await name_bore_axis(
        adapter,
        "Top Plane",
        0.0,
        "Right Plane",
        ARM_C2C,
        "pivot bore axis",
        drive_b='"ArmC2C"',
        drive_jobs=drive_jobs,
    )
    _telemetry.info(f"handle pivot bore axis -> {pivot_axis} (expect Axis2)")

    # Apply the deferred drive equations now -- after the whole model + a rebuild
    # exists, so every target resolves. Each equation evaluates to the value just
    # built, so the geometry must not move; the as-built volume captured above is
    # the neutrality reference for the re-check below.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    set_dimension_bilateral_tolerance(
        adapter,
        "ShaftBoreProfile",
        "ShaftBoreDia",
        *deviations(SHAFT_BORE_BAND),
    )
    await volume_check(adapter, "driven crank arm (equations neutral)", vol, 0.001 * vol)

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

    # Manufacturing drawing support: mark exactly the print's dimensions (the
    # drawing recipe imports the marked set and must find every one of these),
    # and stamp the make-critical title-block properties.
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
