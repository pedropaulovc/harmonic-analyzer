r"""Build crank arm MHA-020 for the separate through-hub construction.

The arm is a plain 8-mm plate with an O19.5 match-fitted MHA-137 seat.  It no
longer mounts directly on the crankshaft and no longer carries the MHA-024
cross-hole.  A blind axial seam groove enters the outboard face at six o'clock,
parallel to the shaft, and accepts MHA-138 for half the arm thickness.  The
outboard witness is a small punched representation, not a machined dimple.

Layout: arm length +X, width +/-Y, thickness +Z (0..8).  In the drive train
local +X hangs down and local +Z faces outboard.

Run with SolidWorks open::

    uv run python cad\scripts\build_crank_arm.py
"""

from __future__ import annotations
import math

import sys

from _common import (
    SketchDims,
    _early_bound,
    add_line_chain,
    anchor_point_to_origin,
    apply_material,
    blank_sketch,
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
from _features import lens_area
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
    AXIAL_PIN_DIA,
    AXIAL_PIN_LENGTH,
    AXIAL_PIN_X,
    AXIAL_PIN_Y,
    DRAWING_NOTES,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    FIDUCIAL_MODEL_DEPTH,
    FIDUCIAL_MODEL_DIA,
    FIDUCIAL_X,
    FIDUCIAL_Y,
    HALF_WIDTH,
    HANDLE_PIVOT_HOLE_SPEC,
    HUB_SEAT_DIA,
    ISOMETRIC_VIEW_NOTE,
    SQUARE_END_OVERHANG,
    SURFACE_FINISHES,
)
from crank_native_acceptance import assert_signed_circle_center

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
    await set_global(adapter, "HubSeatDia", f"{HUB_SEAT_DIA}mm")
    await set_global(adapter, "AxialPinDia", f"{AXIAL_PIN_DIA}mm")
    await set_global(adapter, "AxialPinLength", f"{AXIAL_PIN_LENGTH}mm")
    await set_global(adapter, "FiducialDia", f"{FIDUCIAL_MODEL_DIA}mm")
    await set_global(adapter, "FiducialDepth", f"{FIDUCIAL_MODEL_DEPTH}mm")
    # Sketch distance dimensions are unsigned magnitudes; the negative seeded
    # X coordinate below retains the witness's intended quadrant.
    await set_global(adapter, "FiducialX", f"{abs(FIDUCIAL_X)}mm")
    await set_global(adapter, "FiducialY", f"{abs(FIDUCIAL_Y)}mm")
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

    # Match-fitted through-hub seat.  The assigned actual MHA-137 is lightly
    # arbor-pressed into this nominal bore until its shoulder meets the arm's
    # inboard face; no independent numeric fit band competes with that process.
    hub_seat = SketchDims()
    check("create_sketch hub seat", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        HUB_SEAT_DIA / 2.0,
        "hub seat",
        dims=hub_seat,
        names=("HubSeatX", "HubSeatY", "HubSeatDia"),
        drives=(None, None, '"HubSeatDia"'),
    )
    await ensure_fully_defined(adapter, "hub seat sketch")
    check("exit_sketch hub seat", await adapter.exit_sketch())
    name_last_feature(adapter, "HubSeatProfile")
    drive_jobs += hub_seat.apply(adapter, "HubSeatProfile")
    check(
        "cut hub seat",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "HubSeat")

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

    # HandleSeat is the arm's outboard/operator face after placement.
    check(
        f"create_plane HandleSeat (Front Plane, +{ARM_THICKNESS})",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Front Plane", offset=ARM_THICKNESS
            )
        ),
    )
    name_last_feature(adapter, "HandleSeat")

    # Small visual punch witness.  Its restrained representation is driven so
    # rebuilds remain stable, but it is deliberately absent from the drawing's
    # manufacturing dimension set.
    fiducial = SketchDims()
    check("create_sketch arm fiducial", await adapter.create_sketch("HandleSeat"))
    await define_circle(
        adapter,
        FIDUCIAL_X,
        FIDUCIAL_Y,
        FIDUCIAL_MODEL_DIA / 2.0,
        "arm punch witness",
        dims=fiducial,
        names=("FiducialX", "FiducialY", "FiducialDia"),
        drives=('"FiducialX"', '"FiducialY"', '"FiducialDia"'),
    )
    await ensure_fully_defined(adapter, "arm fiducial sketch")
    check("exit_sketch arm fiducial", await adapter.exit_sketch())
    name_last_feature(adapter, "FiducialProfile")
    drive_jobs += fiducial.apply(adapter, "FiducialProfile")
    check(
        "cut arm fiducial",
        await adapter.create_cut_extrude(
            ExtrusionParameters(
                depth=2.0 * FIDUCIAL_MODEL_DEPTH,
                both_directions=True,
            )
        ),
    )
    name_last_feature(adapter, "PunchedFiducial")
    vol = await _volume(adapter)
    _telemetry.info(f"volume after punch witness: {vol:.1f} mm^3")

    # Keeper-ring anchor: a #4-40 tap through the arm (ch11 p.14), the
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

    # MHA-138 axial seam groove: a blind cylinder from the outboard face,
    # centred exactly on the nominal MHA-137 seat at six o'clock (toward the
    # hanging handle).  The cut leaves only its arm-side segment here; the
    # complementary segment is match-drilled in the assembled hub.
    before_axial_groove = await _volume(adapter)
    axial_groove = SketchDims()
    check("create_sketch axial seam groove", await adapter.create_sketch("HandleSeat"))
    await define_circle(
        adapter,
        AXIAL_PIN_X,
        AXIAL_PIN_Y,
        AXIAL_PIN_DIA / 2.0,
        "axial seam groove",
        dims=axial_groove,
        names=("AxialPinX", "AxialPinY", "AxialPinDia"),
        drives=('"HubSeatDia" / 2', None, '"AxialPinDia"'),
    )
    await ensure_fully_defined(adapter, "axial seam groove sketch")
    check("exit_sketch axial seam groove", await adapter.exit_sketch())
    name_last_feature(adapter, "AxialPinGrooveProfile")
    drive_jobs += axial_groove.apply(adapter, "AxialPinGrooveProfile")
    check(
        "cut axial seam groove",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=AXIAL_PIN_LENGTH)
        ),
    )
    name_last_feature(adapter, "AxialPinGroove")
    vol = await _volume(adapter)
    expected_arm_groove = (
        math.pi * (AXIAL_PIN_DIA / 2.0) ** 2
        - lens_area(AXIAL_PIN_DIA / 2.0, HUB_SEAT_DIA / 2.0)
    ) * AXIAL_PIN_LENGTH
    if abs((before_axial_groove - vol) - expected_arm_groove) > max(
        0.5, 0.02 * expected_arm_groove
    ):
        raise RuntimeError(
            "arm axial seam groove removed "
            f"{before_axial_groove - vol:.2f} mm^3, expected {expected_arm_groove:.2f}"
        )

    # REFERENCE sketches (policy rule 2): the sheet prints the pivot and anchor
    # stations from the hub-seat axis, the anchor's offset from the top long
    # edge and the stock width, yet no feature dimension carries any of them --
    # the Hole Wizard placement sketches measure from the origin and the
    # outline is driven by its half-width and tangent constraints.
    # Each reference's driving dimension is the displayed value.  They remain
    # construction geometry rather than blanked sketches: blanked dimensions do
    # not reach InsertModelAnnotations3, while hiding a drawing-view sketch also
    # hides its imported dimensions.  Construction lines can print grey, so all
    # of them lie under the arm axis, an edge, or a centre-mark line.  The
    # anchor station runs along the axis rather than diagonally to the tap.
    # Direct-to-DB avoids creation-time inference duplicating the explicit
    # relations below and over-defining the sketch.
    stations = SketchDims()
    check("create_sketch station reference", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    pivot_ref = check(
        "pivot station reference line",
        await adapter.add_line(0.0, 0.0, ARM_C2C, 0.0),
    )
    anchor_ref = check(
        "anchor station reference line",
        await adapter.add_line(0.0, 0.0, ANCHOR_SCREW_X, 0.0),
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
    axis_ref = check(
        "common-axis offset reference line",
        await adapter.add_line(ARM_END_X, 0.0, ARM_END_X, HALF_WIDTH),
    )
    set_sketch_direct_db(adapter, False)
    for line in (pivot_ref, anchor_ref, offset_ref, width_ref, axis_ref):
        _as_construction(adapter, line)
    for line, label in ((pivot_ref, "pivot"), (anchor_ref, "anchor")):
        check(
            f"{label} station reference horizontal",
            await adapter.add_sketch_constraint(line, None, "horizontal"),
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
        "anchor offset reference ends above the anchor station",
        await adapter.add_sketch_constraint(
            f"{offset_ref}.end", f"{anchor_ref}.end", "vertical_points"
        ),
    )
    for line, label in (
        (width_ref, "arm width"),
        (axis_ref, "common-axis offset"),
    ):
        check(
            f"{label} reference vertical",
            await adapter.add_sketch_constraint(line, None, "vertical"),
        )
    check(
        "common-axis offset ends on the top long edge",
        await adapter.add_sketch_constraint(
            f"{axis_ref}.end", f"{width_ref}.end", "coincident"
        ),
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
        f"{anchor_ref}.end",
        f"{offset_ref}.end",
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
    await dimension_between(
        adapter,
        f"{axis_ref}.start",
        f"{axis_ref}.end",
        "vertical_distance",
        HALF_WIDTH,
        "common-axis offset reference",
    )
    stations.record("AxisOffset", '"ArmWidth" / 2')
    await anchor_point_to_origin(
        adapter, f"{width_ref}.start", ARM_END_X, -HALF_WIDTH, "arm width reference"
    )
    stations.record("WidthX", '"ArmEndX"')
    stations.record("WidthY", '"ArmWidth" / 2')
    await ensure_fully_defined(adapter, "station reference sketch")
    check("exit_sketch station reference", await adapter.exit_sketch())
    name_last_feature(adapter, "StationReference")
    drive_jobs += stations.apply(adapter, "StationReference")


    # Named axes for semantic assembly mates.  Axis1 is the through-hub seat,
    # Axis2 the handle pivot, Axis3 the six-o'clock axial MHA-138 seam.
    await name_bore_axis(adapter, "Top Plane", 0.0, "Right Plane", 0.0, "hub seat axis")
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
    seam_axis = await name_bore_axis(
        adapter,
        "Top Plane",
        0.0,
        "Right Plane",
        AXIAL_PIN_X,
        "axial seam pin axis",
        drive_b='"HubSeatDia" / 2',
        drive_jobs=drive_jobs,
    )
    _telemetry.info(
        f"handle pivot -> {pivot_axis} (Axis2); axial seam -> {seam_axis} (Axis3)"
    )

    # Apply the deferred drive equations now -- after the whole model + a rebuild
    # exists, so every target resolves. Each equation evaluates to the value just
    # built, so the geometry must not move; the as-built volume captured above is
    # the neutrality reference for the re-check below.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    assert_signed_circle_center(
        adapter,
        "AxialPinGrooveProfile",
        label="MHA-020 six-o'clock seam",
        expected_sketch_xy_mm=(AXIAL_PIN_X, AXIAL_PIN_Y),
        expected_model_xyz_mm=(AXIAL_PIN_X, AXIAL_PIN_Y, ARM_THICKNESS),
        axis_name=seam_axis,
        axis_expected_components_mm={0: AXIAL_PIN_X, 1: AXIAL_PIN_Y},
    )
    assert_signed_circle_center(
        adapter,
        "FiducialProfile",
        label="MHA-020 punched fiducial",
        expected_sketch_xy_mm=(FIDUCIAL_X, FIDUCIAL_Y),
        expected_model_xyz_mm=(FIDUCIAL_X, FIDUCIAL_Y, ARM_THICKNESS),
    )
    # The assigned actual hub governs the final match-fit bore; no independent
    # local band is authored on MHA-020.
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
    # The reference sketch owns printed dimensions but no geometry: hide it so
    # no assembly instance renders it (#880).  The drawing shows it per view
    # through _drawing_hidden_sketches to import those dimensions.
    blank_sketch(adapter, "StationReference")
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
