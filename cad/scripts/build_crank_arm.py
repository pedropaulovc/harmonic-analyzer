r"""Reproduction script: crank arm (book ch. 11, pp. 12-15).

The metal crank arm that drives the machine: full-radius boss at the
crankshaft end (bored for the shaft and cross-drilled for the removable
tapered pin), straight arm, square end carrying the handle pivot, and a
fiducial dimple for alignment. The wooden handle and the tapered pin are
separate parts (build_crank_handle.py / build_crank_pin.py); the keeper
ring's anchor screw (fillister-screw) and brass eyelet (crank-pin-eye) sit
in the front-face tap authored here (the chain itself is lost).

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
    _early_bound,
    add_line_chain,
    anchor_point_to_origin,
    apply_material,
    name_bore_axis,
    check,
    define_circle,
    dimension_between,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)
from _hole_spec import blind_cut_dia_mm
from _holes import wizard_holes

import _telemetry
from _drawing_marks import (
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _part_pmi import author_part_pmi
from crank_arm_spec import (
    ANCHOR_SCREW_X,
    ANCHOR_SCREW_Y,
    ANCHOR_HOLE_SPEC,
    ARM_C2C,
    ARM_END_X,
    ARM_THICKNESS,
    ARM_WIDTH,
    DIMPLE_DEPTH,
    DIMPLE_DIA,
    DIMPLE_X,
    DRAWING_NOTES,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    HALF_WIDTH,
    HANDLE_PIVOT_HOLE_SPEC,
    PIN_HOLE_SPEC,
    ISOMETRIC_VIEW_NOTE,
    SHAFT_BORE_DIA,
    SQUARE_END_OVERHANG,
    SURFACE_FINISHES,
)

PART_NAME = "crank-arm"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring


THROUGH_CUT_DEPTH = 40.0  # mid-plane total; > any extent it crosses


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success else float("nan")


def _as_construction(adapter, entity_id: str) -> None:
    """Flag a registered sketch line as construction geometry.

    ``ConstructionGeometry`` is declared on the base ISketchSegment, not the
    derived ISketchLine the entity registry binds -- rebind before the set.
    """
    segment = _early_bound(adapter._sketch_entities[entity_id], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity_id} did not take the construction flag")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

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
    await set_global(adapter, "AnchorScrewX", f"{ANCHOR_SCREW_X}mm")
    await set_global(adapter, "AnchorScrewY", f"{ANCHOR_SCREW_Y}mm")
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

    # Handle-pivot native fractional-drill hole at the handle-pivot centre,
    # drilled +Z through the plate while the body is still prismatic.
    pivot_cut = wizard_holes(
        adapter,
        HANDLE_PIVOT_HOLE_SPEC,
        [[ARM_C2C, 0.0, ARM_THICKNESS]],
        (0.0, 0.0, 1.0),
        f"handle-pivot hole ({HANDLE_PIVOT_HOLE_SPEC.size})",
        name="PivotBore",
        expect_dia_mm=blind_cut_dia_mm(HANDLE_PIVOT_HOLE_SPEC),
        placement_dims=[(("PivotBoreX", '"ArmC2C"'), (None, None))],
    )
    drive_jobs += pivot_cut.placement_drive_jobs
    vol = await _volume(adapter)
    _telemetry.info(f"volume after bores: {vol:.1f} mm^3")

    # HandleSeat = the z = ARM_THICKNESS face: the arm's FRONT face once
    # placed (the composed Ry(180) turns local +z to machine -z, so this face
    # looks south at the operator). 2026-09-02, ch11 p.14: the dimple and the
    # keeper-ring anchor screw sit on THIS face, not the z = 0 one (which the
    # earlier build carried the dimple on -- hidden against the chain wheel).
    check(
        f"create_plane HandleSeat (Front Plane, +{ARM_THICKNESS})",
        await adapter.create_plane(CreatePlaneParameters(
            mode="offset", base_plane="Front Plane", offset=ARM_THICKNESS,
        )),
    )
    name_last_feature(adapter, "HandleSeat")

    # Fiducial dimple on the front face. Mid-plane cut of 2x depth: only the
    # in-material half removes anything, so the result is DIMPLE_DEPTH
    # regardless of cut direction.
    dimple = SketchDims()
    check("create_sketch dimple", await adapter.create_sketch("HandleSeat"))
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

    # Keeper-ring anchor: a blind #4-40 tap in the front face (ch11 p.14), the
    # brass fillister-screw clamps the wire eyelet's tail under its head.
    anchor_cut = wizard_holes(
        adapter,
        ANCHOR_HOLE_SPEC,
        [[ANCHOR_SCREW_X, ANCHOR_SCREW_Y, ARM_THICKNESS]],
        (0.0, 0.0, 1.0),
        "keeper-ring anchor tap (#4-40)",
        name="AnchorTap",
        placement_dims=[(("AnchorX", '"AnchorScrewX"'), ("AnchorY", '"AnchorScrewY"'))],
    )
    drive_jobs += anchor_cut.placement_drive_jobs
    vol = await _volume(adapter)
    _telemetry.info(f"volume after anchor tap: {vol:.1f} mm^3")

    # Tapered-pin cross-hole: pilot below the No. 2 taper pin's small end, then
    # taper-reamed with the shaft at assembly. Drill along global Y through the
    # boss + shaft bore at mid-thickness.
    pin_cut = wizard_holes(
        adapter,
        PIN_HOLE_SPEC,
        [[0.0, HALF_WIDTH, ARM_THICKNESS / 2.0]],
        (0.0, 1.0, 0.0),
        f"tapered-pin cross-hole ({PIN_HOLE_SPEC.size})",
        name="PinHole",
        expect_dia_mm=blind_cut_dia_mm(PIN_HOLE_SPEC),
        placement_dims=[((None, None), ("PinHoleZ", '"ArmThickness" / 2'))],
    )
    drive_jobs += pin_cut.placement_drive_jobs
    vol = await _volume(adapter)
    _telemetry.info(f"volume after pin hole: {vol:.1f} mm^3")

    # Two REFERENCE sketches (policy rule 2): the sheet prints the pivot and
    # anchor stations from the shaft-bore axis, the anchor's offset from the
    # top long edge, the stock width and the cross-hole's station from the
    # broad face, yet no feature dimension carries any of them -- the Hole
    # Wizard placement sketches measure from the origin and the outline is
    # pinned by its boss radius. Each value therefore gets a construction line
    # whose driving dimension IS the value, marked for drawing like any other
    # dimension. Construction, not blanked: a blanked sketch's dimensions never
    # reach InsertModelAnnotations3 (build_harmonic_base measured it), while
    # construction geometry imports normally and is never drawn in a view.
    # Direct-to-DB for the geometry: these lines lie on the axes and on the
    # arm's own edges, so creation-time inference would snap in exactly the
    # relations the explicit ones below add and leave the sketch over-defined.
    stations = SketchDims()
    check("create_sketch station reference", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    pivot_ref = check(
        "pivot station reference line",
        await adapter.add_line(0.0, 0.0, ARM_C2C, 0.0),
    )
    anchor_ref = check(
        "anchor station reference line",
        await adapter.add_line(0.0, 0.0, ANCHOR_SCREW_X, ANCHOR_SCREW_Y),
    )
    offset_ref = check(
        "anchor offset reference line",
        await adapter.add_line(
            ANCHOR_SCREW_X, HALF_WIDTH, ANCHOR_SCREW_X, ANCHOR_SCREW_Y
        ),
    )
    width_ref = check(
        "arm width reference line",
        await adapter.add_line(ARM_END_X, -HALF_WIDTH, ARM_END_X, HALF_WIDTH),
    )
    set_sketch_direct_db(adapter, False)
    for line in (pivot_ref, anchor_ref, offset_ref, width_ref):
        _as_construction(adapter, line)
    check(
        "pivot station reference horizontal",
        await adapter.add_sketch_constraint(pivot_ref, None, "horizontal"),
    )
    for line, label in ((pivot_ref, "pivot"), (anchor_ref, "anchor")):
        check(
            f"{label} station reference starts on the bore axis",
            await adapter.add_sketch_constraint(
                f"{line}.start", "origin", "coincident"
            ),
        )
    check(
        "anchor offset reference vertical",
        await adapter.add_sketch_constraint(offset_ref, None, "vertical"),
    )
    check(
        "anchor offset reference ends on the anchor axis",
        await adapter.add_sketch_constraint(
            f"{offset_ref}.end", f"{anchor_ref}.end", "coincident"
        ),
    )
    check(
        "arm width reference vertical",
        await adapter.add_sketch_constraint(width_ref, None, "vertical"),
    )
    # Dimensions in creation order; SketchDims renames them by that order.
    await dimension_between(
        adapter,
        f"{pivot_ref}.start",
        f"{pivot_ref}.end",
        "horizontal_distance",
        ARM_C2C,
        "pivot station reference",
    )
    stations.record("PivotStation", '"ArmC2C"')
    await dimension_between(
        adapter,
        f"{anchor_ref}.start",
        f"{anchor_ref}.end",
        "horizontal_distance",
        ANCHOR_SCREW_X,
        "anchor station reference",
    )
    stations.record("AnchorStation", '"AnchorScrewX"')
    await dimension_between(
        adapter,
        f"{anchor_ref}.start",
        f"{anchor_ref}.end",
        "vertical_distance",
        ANCHOR_SCREW_Y,
        "anchor axis height reference",
    )
    stations.record("AnchorY", '"AnchorScrewY"')
    await dimension_between(
        adapter,
        f"{offset_ref}.start",
        f"{offset_ref}.end",
        "vertical_distance",
        HALF_WIDTH - ANCHOR_SCREW_Y,
        "anchor offset reference",
    )
    stations.record("AnchorOffset", '"ArmWidth" / 2 - "AnchorScrewY"')
    await dimension_between(
        adapter,
        f"{width_ref}.start",
        f"{width_ref}.end",
        "vertical_distance",
        ARM_WIDTH,
        "arm width reference",
    )
    stations.record("Width", '"ArmWidth"')
    await anchor_point_to_origin(
        adapter, f"{width_ref}.start", ARM_END_X, -HALF_WIDTH, "arm width reference"
    )
    stations.record("WidthX", '"ArmEndX"')
    stations.record("WidthY", '"ArmWidth" / 2')
    await ensure_fully_defined(adapter, "station reference sketch")
    check("exit_sketch station reference", await adapter.exit_sketch())
    name_last_feature(adapter, "StationReference")
    drive_jobs += stations.apply(adapter, "StationReference")

    # Cross-hole station from the z = 0 broad face, on the Top plane so the
    # edge-on top view imports it: Top sketch (u, v) -> (X, -Z), so the hole
    # axis at z = ArmThickness / 2 sits at v = -ArmThickness / 2.
    pin_station = SketchDims()
    check("create_sketch pin station reference", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    pin_ref = check(
        "pin station reference line",
        await adapter.add_line(0.0, 0.0, 0.0, -ARM_THICKNESS / 2.0),
    )
    set_sketch_direct_db(adapter, False)
    _as_construction(adapter, pin_ref)
    check(
        "pin station reference vertical",
        await adapter.add_sketch_constraint(pin_ref, None, "vertical"),
    )
    check(
        "pin station reference starts on the broad face",
        await adapter.add_sketch_constraint(f"{pin_ref}.start", "origin", "coincident"),
    )
    await dimension_between(
        adapter,
        f"{pin_ref}.start",
        f"{pin_ref}.end",
        "vertical_distance",
        ARM_THICKNESS / 2.0,
        "pin station reference",
    )
    pin_station.record("PinStation", '"ArmThickness" / 2')
    await ensure_fully_defined(adapter, "pin station reference sketch")
    check("exit_sketch pin station reference", await adapter.exit_sketch())
    name_last_feature(adapter, "PinStationReference")
    drive_jobs += pin_station.apply(adapter, "PinStationReference")

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
    # No local size band on the shaft bore: the arm is pinned to its shaft, so
    # this is no running fit and the title block's drilled-hole row governs it
    # (cad/docs/tolerance-policy.md).
    await volume_check(adapter, "driven crank arm (equations neutral)", vol, 0.001 * vol)

    # HandleSeat datum: the plate face OPPOSITE the origin plane (z =
    # ARM_THICKNESS). The chirality-mirrored drive-train maps part +z to
    # machine -z, so this is the arm's SOUTH face -- the crank handle's brass
    # collar butts flush against it (its Right/origin plane mates COINCIDENT
    # here, the flip-free seat idiom; seating on Front@arm instead buried the
    # collar inside the plate, 502 mm^3, 2026-07-05).


    # Manufacturing drawing support: mark exactly the print's dimensions (the
    # drawing recipe imports the marked set and must find every one of these),
    # author their decimal places on the part (policy rule 2: the places are
    # the tolerance, so the sheet reads them back instead of rewriting them),
    # and stamp the make-critical title-block properties.
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
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
