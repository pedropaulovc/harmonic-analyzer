r"""Build separate through hub MHA-DT-31.

The local +Y axis runs inboard from the arm's outboard face.  The Ø.76 seat is
flush through the 5/16 arm; the Ø.88 rear barrel supplies the inboard shoulder
and carries the removable MHA-DT-09 hub-to-shaft cross-hole, located from that
shoulder; behind it a Ø.65 relief turned to the rear face lets the #25 chain
plates wrapping the crank T12 pass.  MHA-DT-VN-59 is an axial
seam groove at local +Z (six o'clock after assembly), match-reamed into arm
and hub to SEAM_DEPTH, deeper than the cut pin.
"""

from __future__ import annotations

import math
import sys

import _telemetry
from _appearance import apply_material
from _bore_axis import name_bore_axis
from _document_units import apply_package_model_units
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    blank_sketch,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_circle import define_circle
from _drawing_dimension_insert import add_diametric_linear_dimension
from _drawing_precision import apply_drawing_precision
from _drawing_marks import apply_drawing_properties, clear_dimensions_for_drawing, mark_dimensions_for_drawing
from _drawing_tolerances import set_dimension_bilateral_tolerance
from _features import lens_area
from _fit_deviations import deviations
from _hole_spec import blind_cut_dia_mm
from _holes import wizard_hole_on_cylinder
from _part_pmi import author_part_pmi
from _single_limit_tolerance import SW_TOL_MIN, set_single_limit
from _visibility import blank_reference_geometry
from dt_crank_hub_geometry import (
    AXIAL_PIN_DIA,
    HUB_LENGTH_BAND,
    AXIAL_PIN_RADIUS_FROM_AXIS,
    SEAM_DEPTH,
    UNIT,
)
from crank_native_acceptance import assert_signed_circle_center
from dt_crank_hub_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    HUB_BARREL_DIA,
    HUB_BORE_BAND,
    HUB_BARREL_LENGTH,
    HUB_BORE_DIA,
    HUB_LENGTH,
    HUB_SEAT_DIA,
    HUB_SEAT_LENGTH,
    ISOMETRIC_VIEW_NOTE,
    PIN_PROUD_MIN_BAND,
    SERVICE_PIN_HOLE_SPEC,
    SERVICE_PIN_STATION,
    SURFACE_FINISHES,
    RELIEF_DIA,
    RELIEF_LENGTH,
    RELIEF_STATION,
)
from dt_crank_pin_ring_spec import PIN_PROUD
from dt_crank_pin_spec import BIG_END_DIA as PIN_BIG_END_DIA


PART_NAME = "dt-crank-hub"
MATERIAL = "Plain Carbon Steel"
SEAT_R = HUB_SEAT_DIA / 2.0
BARREL_R = HUB_BARREL_DIA / 2.0
RELIEF_R = RELIEF_DIA / 2.0
BORE_R = HUB_BORE_DIA / 2.0
PIN_R = AXIAL_PIN_DIA / 2.0
V_BODY = math.pi * (
    SEAT_R**2 * HUB_SEAT_LENGTH
    + BARREL_R**2 * HUB_BARREL_LENGTH
    + RELIEF_R**2 * RELIEF_LENGTH
)
V_BORE = math.pi * BORE_R**2 * HUB_LENGTH
V_SEAM_GROOVE = lens_area(PIN_R, SEAT_R) * SEAM_DEPTH
# The MHA-DT-09 big end drawn in phantom on the end view (r5 review: the
# PinProud MIN's outer extension line ended in air, nothing drawn there):
# its silhouette leaves the barrel's outline at PIN_STUB_X off the axis.
PIN_BIG_END_R = PIN_BIG_END_DIA / 2.0
PIN_STUB_X = math.sqrt(BARREL_R**2 - PIN_BIG_END_R**2)


async def _volume(adapter) -> float:
    result = await adapter.get_mass_properties()
    return result.data.volume if result.is_success else float("nan")


async def _pin_proud_reference(adapter) -> list[tuple[str, str]]:
    """The MHA-DT-09 ream's acceptance, printed natively on the end view: a
    hidden construction line out from the barrel along the pin's axis on its
    big-end side (local -X, where the drill enters), as long as PIN_PROUD, so
    its driving dimension prints "4.45 MIN" once set_single_limit types it.
    The pin's proud big end is drawn round it as construction (phantom on the
    sheet): its face across the line's outer end, Ø PIN_BIG_END_DIA, and two
    silhouette stubs back to the barrel's outline, so the MIN's extension
    line lands on drawn geometry (r5 review).  No model geometry changes.
    On the Top plane, parallel to the *Bottom end view that imports it; Top
    (u, v) -> (X, -Z), so the line lies on the pin's projected axis.  Returns
    the deferred drive jobs (the length, its anchor to the barrel, then the
    big end's face and the stubs' start)."""
    check("create_sketch pin proud reference", await adapter.create_sketch("Top"))
    tip = -(BARREL_R + PIN_PROUD)
    # Direct-to-DB: the line lies on the sketch's horizontal axis, where
    # creation-time inference would over-define it.
    set_sketch_direct_db(adapter, True)
    try:
        line = check(
            "pin proud reference line",
            await adapter.add_line(-BARREL_R, 0.0, tip, 0.0),
        )
        top, face, bottom = await add_line_chain(
            adapter,
            [
                (-PIN_STUB_X, PIN_BIG_END_R),
                (tip, PIN_BIG_END_R),
                (tip, -PIN_BIG_END_R),
                (-PIN_STUB_X, -PIN_BIG_END_R),
            ],
            close=False,
        )
    finally:
        set_sketch_direct_db(adapter, False)
    for entity in (line, top, face, bottom):
        segment = _early_bound(adapter._sketch_entities[entity], "ISketchSegment")
        segment.ConstructionGeometry = True
        if not bool(segment.ConstructionGeometry):
            raise RuntimeError(f"pin proud reference {entity} did not take the construction flag")
    for entity, relation in ((line, "horizontal"), (top, "horizontal"), (bottom, "horizontal"), (face, "vertical")):
        check(
            f"pin proud reference {entity} {relation}",
            await adapter.add_sketch_constraint(entity, None, relation),
        )
    check(
        "pin big end centred on the pin axis",
        await adapter.add_sketch_constraint(f"{line}.end", face, "midpoint"),
    )
    await dimension_between(
        adapter,
        f"{line}.start",
        f"{line}.end",
        "horizontal_distance",
        PIN_PROUD,
        "pin proud reference",
    )
    await anchor_point_to_origin(
        adapter, f"{line}.start", -BARREL_R, 0.0, "pin proud reference at the barrel"
    )
    await dimension_between(
        adapter,
        f"{face}.start",
        f"{face}.end",
        "vertical_distance",
        PIN_BIG_END_DIA,
        "pin big end face",
    )
    await dimension_between(
        adapter,
        f"{top}.start",
        "origin",
        "horizontal_distance",
        PIN_STUB_X,
        "pin big end stubs at the barrel",
    )
    check(
        "pin big end stubs start square",
        await adapter.add_sketch_constraint(f"{top}.start", f"{bottom}.end", "vertical_points"),
    )
    await ensure_fully_defined(adapter, "pin proud reference sketch")
    check("exit_sketch pin proud reference", await adapter.exit_sketch())
    name_last_feature(adapter, "PinProudReference")
    full = name_dimensions(
        adapter,
        "PinProudReference",
        ["PinProud", "PinProudBarrel", "PinBigEnd", "PinBigEndStub"],
    )
    return list(
        zip(
            full,
            ('"PinProud"', '"BarrelDia" / 2', '"PinBigEndDia"', '"PinBigEndStubX"'),
            strict=True,
        )
    )


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreatePlaneParameters,
        ExtrusionParameters,
        RevolveParameters,
    )

    check("create_part", await adapter.create_part())
    apply_package_model_units(adapter, UNIT, label=PART_NAME)
    for name, value in (
        ("HubLength", HUB_LENGTH),
        ("SeatLength", HUB_SEAT_LENGTH),
        ("SeatDia", HUB_SEAT_DIA),
        ("BarrelDia", HUB_BARREL_DIA),
        ("ReliefLength", RELIEF_LENGTH),
        ("ReliefDia", RELIEF_DIA),
        ("BoreDia", HUB_BORE_DIA),
        ("ServicePinStation", SERVICE_PIN_STATION),
        ("AxialPinDia", AXIAL_PIN_DIA),
        ("SeamDepth", SEAM_DEPTH),
        # The MHA-DT-09 ream's acceptance: a limit, not geometry, so only the
        # hidden reference line carries it.
        ("PinProud", PIN_PROUD),
        # Its phantom big end on the end view (reference sketch only).
        ("PinBigEndDia", PIN_BIG_END_DIA),
        ("PinBigEndStubX", PIN_STUB_X),
    ):
        await set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Stepped sleeve profile about local +Y: seat, barrel, rear relief.
    profile = SketchDims()
    check("create_sketch hub profile", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "hub axis", await adapter.add_centerline(0.0, 0.0, 0.0, HUB_LENGTH)
    )
    points = [
        (0.0, 0.0),
        (SEAT_R, 0.0),
        (SEAT_R, HUB_SEAT_LENGTH),
        (BARREL_R, HUB_SEAT_LENGTH),
        (BARREL_R, RELIEF_STATION),
        (RELIEF_R, RELIEF_STATION),
        (RELIEF_R, HUB_LENGTH),
        (0.0, HUB_LENGTH),
    ]
    lines = await add_line_chain(adapter, points)
    set_sketch_direct_db(adapter, False)
    for index, line in enumerate(lines):
        p0 = points[index]
        p1 = points[(index + 1) % len(points)]
        relation = "horizontal" if p0[1] == p1[1] else "vertical"
        check(
            f"hub profile {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    check("hub axis vertical", await adapter.add_sketch_constraint(axis, None, "vertical"))
    await anchor_point_to_origin(
        adapter, f"{lines[0]}.start", 0.0, 0.0, "hub origin"
    )
    await add_diametric_linear_dimension(
        adapter, axis, lines[1], (SEAT_R + 4.0, HUB_SEAT_LENGTH / 2.0), "SeatDia"
    )
    profile.record("SeatDia", '"SeatDia"')
    await add_diametric_linear_dimension(
        adapter,
        axis,
        lines[3],
        (BARREL_R + 4.0, (HUB_SEAT_LENGTH + RELIEF_STATION) / 2.0),
        "BarrelDia",
    )
    profile.record("BarrelDia", '"BarrelDia"')
    await add_diametric_linear_dimension(
        adapter,
        axis,
        lines[5],
        (RELIEF_R + 4.0, (RELIEF_STATION + HUB_LENGTH) / 2.0),
        "ReliefDia",
    )
    profile.record("ReliefDia", '"ReliefDia"')
    check(
        "seat length",
        await adapter.add_sketch_dimension(lines[1], None, "linear", HUB_SEAT_LENGTH),
    )
    profile.record("SeatLength", '"SeatLength"')
    # The overall, front face to rear face (outer corners, where the
    # drawing's extension lines rise): the barrel's length is its remainder
    # and is not printed.
    await dimension_between(
        adapter,
        f"{lines[1]}.start",
        f"{lines[6]}.start",
        "vertical_distance",
        HUB_LENGTH,
        "hub overall length",
    )
    profile.record("HubLength", '"HubLength"')
    check(
        "relief length",
        await adapter.add_sketch_dimension(lines[5], None, "linear", RELIEF_LENGTH),
    )
    profile.record("ReliefLength", '"ReliefLength"')
    await ensure_fully_defined(adapter, "hub profile")
    check("exit_sketch hub profile", await adapter.exit_sketch())
    name_last_feature(adapter, "HubProfile")
    drive_jobs += profile.apply(adapter, "HubProfile")
    check("revolve hub", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "HubBody")
    await volume_check(adapter, "stepped hub body", V_BODY, 0.005 * V_BODY)

    # Reamed through bore on the shaft axis.
    bore = SketchDims()
    check("create_sketch hub bore", await adapter.create_sketch("Top"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        BORE_R,
        "hub through bore",
        dims=bore,
        names=("BoreCx", "BoreCz", "BoreDia"),
        drives=(None, None, '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "hub bore sketch")
    check("exit_sketch hub bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bore.apply(adapter, "BoreProfile")
    check(
        "cut hub bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=HUB_LENGTH, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "ThroughBore")
    await volume_check(adapter, "hub through bore", V_BODY - V_BORE, 0.01 * V_BORE)

    # Axial six-o'clock seam groove: Top sketch coordinates (u,v) map to
    # model (X,-Z), hence v=-radius places the key at local +Z.
    groove = SketchDims()
    check("create_sketch axial seam groove", await adapter.create_sketch("Top"))
    await define_circle(
        adapter,
        0.0,
        -AXIAL_PIN_RADIUS_FROM_AXIS,
        PIN_R,
        "axial seam groove",
        dims=groove,
        names=("GrooveX", "GrooveZ", "GrooveDia"),
        drives=(None, '"SeatDia" / 2', '"AxialPinDia"'),
    )
    await ensure_fully_defined(adapter, "axial seam groove sketch")
    check("exit_sketch axial seam groove", await adapter.exit_sketch())
    name_last_feature(adapter, "AxialPinGrooveProfile")
    drive_jobs += groove.apply(adapter, "AxialPinGrooveProfile")
    check(
        "cut axial seam groove",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=SEAM_DEPTH, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "AxialPinGroove")
    await volume_check(
        adapter,
        "hub axial seam groove",
        V_BODY - V_BORE - V_SEAM_GROOVE,
        max(0.5, 0.02 * V_SEAM_GROOVE),
    )
    # Inboard shoulder and the plane locating the MHA-DT-09 match-ream station.
    # The plane offset is not printable through a drawing view (targeted import
    # selects sketches/body features); it is driven from the same global as
    # the printed station dimension on the reference sketch below.
    for plane_name, station in (
        ("ArmShoulder", HUB_SEAT_LENGTH),
        ("ServicePinStationPlane", SERVICE_PIN_STATION),
    ):
        check(
            f"create_plane {plane_name}",
            await adapter.create_plane(
                CreatePlaneParameters(mode="offset", base_plane="Top Plane", offset=station)
            ),
        )
        name_last_feature(adapter, plane_name)
        if plane_name == "ServicePinStationPlane":
            dimensions = name_dimensions(adapter, plane_name, ["ServicePinStationPlaneOffset"])
            drive_jobs.append((dimensions[0], '"ServicePinStation"'))

    wizard_hole_on_cylinder(
        adapter,
        SERVICE_PIN_HOLE_SPEC,
        [-BARREL_R, SERVICE_PIN_STATION, 0.0],
        "MHA-DT-09 hub pilot",
        name="ServicePinHole",
        point_planes=("ServicePinStationPlane", "Front Plane"),
    )
    final_volume = await _volume(adapter)
    _telemetry.info(
        f"volume after {blind_cut_dia_mm(SERVICE_PIN_HOLE_SPEC):.3f} service pilot: "
        f"{final_volume:.1f} mm^3"
    )
    # Drawing-only station reference on the hub axis, printing the MHA-DT-09
    # station from the faced outboard end (the machinist's baseline; the
    # shoulder ligament is the drawing-guidelines.md rule 17 (walls and webs)
    # stack in dt_crank_hub_geometry).
    # Keeping the construction line under the view centreline avoids extra
    # printed geometry while giving targeted model-item import a real sketch
    # owner.  It sits on the Right plane because the *Right side view prints
    # it; every reference sketch that imports natively sits on the plane of
    # its view.  On the Front plane the sketch was selected but its dimension
    # never arrived (run 20260922T020620997Z-4a7ef16e).  Right (u, v) -> (-Z, Y).
    station = SketchDims()
    check("create_sketch service pin station", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    station_line = check(
        "service pin station reference line",
        await adapter.add_line(0.0, 0.0, 0.0, SERVICE_PIN_STATION),
    )
    set_sketch_direct_db(adapter, False)
    segment = _early_bound(adapter._sketch_entities[station_line], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError("service pin station reference did not take construction flag")
    check(
        "service pin station reference vertical",
        await adapter.add_sketch_constraint(station_line, None, "vertical"),
    )
    await anchor_point_to_origin(
        adapter,
        f"{station_line}.start",
        0.0,
        0.0,
        "service pin station reference at the outboard face",
    )
    await dimension_between(
        adapter,
        f"{station_line}.start",
        f"{station_line}.end",
        "vertical_distance",
        SERVICE_PIN_STATION,
        "service pin station from the outboard face",
    )
    station.record("ServicePinStation", '"ServicePinStation"')
    await ensure_fully_defined(adapter, "service pin station reference sketch")
    check("exit_sketch service pin station", await adapter.exit_sketch())
    name_last_feature(adapter, "ServicePinStationReference")
    drive_jobs += station.apply(adapter, "ServicePinStationReference")
    drive_jobs += await _pin_proud_reference(adapter)
    # Axis1 is the shaft/hub axis; Axis2 is the axial seam-pin axis.
    await name_bore_axis(adapter, "Front Plane", 0.0, "Right Plane", 0.0, "hub axis")
    seam_axis = await name_bore_axis(
        adapter,
        "Front Plane",
        AXIAL_PIN_RADIUS_FROM_AXIS,
        "Right Plane",
        0.0,
        "axial seam pin axis",
        drive_a='"SeatDia" / 2',
        drive_jobs=drive_jobs,
    )

    await force_rebuild(adapter)
    for dimension, expression in drive_jobs:
        await drive_dimension(adapter, dimension, expression)
    await force_rebuild(adapter)
    assert_signed_circle_center(
        adapter,
        "AxialPinGrooveProfile",
        label="MHA-DT-31 six-o'clock seam",
        expected_sketch_xy_mm=(0.0, -AXIAL_PIN_RADIUS_FROM_AXIS),
        expected_model_xyz_mm=(0.0, 0.0, AXIAL_PIN_RADIUS_FROM_AXIS),
        axis_name=seam_axis,
        axis_expected_components_mm={0: 0.0, 2: AXIAL_PIN_RADIUS_FROM_AXIS},
    )
    set_dimension_bilateral_tolerance(
        adapter, "BoreProfile", "BoreDia", *deviations(HUB_BORE_BAND), display_unit=UNIT
    )
    # The overall places the rear face the removable and the drive-pin tips
    # clear, so it carries its functional limit on the side that closes an
    # air and keeps the .XX band's -.010 on the other (dt_crank_hub_geometry),
    # printed at the nominal's three places.
    set_dimension_bilateral_tolerance(
        adapter,
        "HubProfile",
        "HubLength",
        *deviations(HUB_LENGTH_BAND),
        places=DRAWING_PRECISION["HubProfile"]["HubLength"],
        display_unit=UNIT,
    )
    set_single_limit(
        adapter,
        "PinProudReference",
        "PinProud",
        limit=PIN_PROUD,
        band=PIN_PROUD_MIN_BAND,
        tol_type=SW_TOL_MIN,
    )
    await volume_check(adapter, "driven crank hub", final_volume, 0.001 * final_volume)
    # Both datum planes stay selectable by name for the drive-train mates.
    blank_reference_geometry(
        adapter, (("ArmShoulder", "PLANE"), ("ServicePinStationPlane", "PLANE"))
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature, dimensions in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature, dimensions)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    # The reference sketch owns printed dimensions but no geometry: hide it so
    # no assembly instance renders it (#880).  The drawing shows it per view
    # through _drawing_hidden_sketches to import those dimensions.
    blank_sketch(adapter, "ServicePinStationReference")
    blank_sketch(adapter, "PinProudReference")
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
