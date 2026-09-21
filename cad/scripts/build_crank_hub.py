r"""Build separate through hub MHA-137.

The local +Y axis runs inboard from the arm's outboard face.  The O15 seat is
flush through the 8-mm arm; the O18.1 rear barrel supplies the inboard shoulder
and carries the removable MHA-024 hub-to-shaft cross-hole.  MHA-138 is an axial
seam groove at local +Z (six o'clock after assembly), match-reamed through arm
and hub for only half the arm thickness.
"""

from __future__ import annotations

import math
import sys

import _telemetry
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
    name_bore_axis,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)
from _drawing_marks import (
    add_diametric_linear_dimension,
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
)
from _features import lens_area
from _fit_limits import deviations
from _hole_spec import blind_cut_dia_mm
from _holes import wizard_hole_on_cylinder
from _part_pmi import author_part_pmi
from crank_hub_geometry import (
    AXIAL_PIN_DIA,
    AXIAL_PIN_LENGTH,
    AXIAL_PIN_RADIUS_FROM_AXIS,
)
from crank_hub_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    HUB_BARREL_DIA,
    HUB_BORE_BAND,
    HUB_BORE_DIA,
    HUB_LENGTH,
    HUB_SEAT_DIA,
    HUB_SEAT_LENGTH,
    ISOMETRIC_VIEW_NOTE,
    SERVICE_PIN_HOLE_SPEC,
    SERVICE_PIN_STATION,
    SURFACE_FINISHES,
)


PART_NAME = "crank-hub"
MATERIAL = "Plain Carbon Steel"
SEAT_R = HUB_SEAT_DIA / 2.0
BARREL_R = HUB_BARREL_DIA / 2.0
BORE_R = HUB_BORE_DIA / 2.0
PIN_R = AXIAL_PIN_DIA / 2.0
V_BODY = math.pi * (
    SEAT_R**2 * HUB_SEAT_LENGTH
    + BARREL_R**2 * (HUB_LENGTH - HUB_SEAT_LENGTH)
)
V_BORE = math.pi * BORE_R**2 * HUB_LENGTH
V_SEAM_GROOVE = lens_area(PIN_R, SEAT_R) * AXIAL_PIN_LENGTH


async def _volume(adapter) -> float:
    result = await adapter.get_mass_properties()
    return result.data.volume if result.is_success else float("nan")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreatePlaneParameters,
        ExtrusionParameters,
        RevolveParameters,
    )

    check("create_part", await adapter.create_part())
    for name, value in (
        ("HubLength", HUB_LENGTH),
        ("SeatLength", HUB_SEAT_LENGTH),
        ("SeatDia", HUB_SEAT_DIA),
        ("BarrelDia", HUB_BARREL_DIA),
        ("BoreDia", HUB_BORE_DIA),
        ("ServicePinStation", SERVICE_PIN_STATION),
        ("AxialPinDia", AXIAL_PIN_DIA),
        ("AxialPinLength", AXIAL_PIN_LENGTH),
    ):
        await set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Stepped sleeve profile about local +Y.
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
        (BARREL_R, HUB_LENGTH),
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
        adapter, axis, lines[3], (BARREL_R + 4.0, (HUB_SEAT_LENGTH + HUB_LENGTH) / 2.0), "BarrelDia"
    )
    profile.record("BarrelDia", '"BarrelDia"')
    check(
        "seat length",
        await adapter.add_sketch_dimension(lines[1], None, "linear", HUB_SEAT_LENGTH),
    )
    profile.record("SeatLength", '"SeatLength"')
    check(
        "hub length",
        await adapter.add_sketch_dimension(lines[5], None, "linear", HUB_LENGTH),
    )
    profile.record("HubLength", '"HubLength"')
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
        await adapter.create_cut_extrude(ExtrusionParameters(depth=HUB_LENGTH)),
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
        drives=(None, '"SeatDia" / -2', '"AxialPinDia"'),
    )
    await ensure_fully_defined(adapter, "axial seam groove sketch")
    check("exit_sketch axial seam groove", await adapter.exit_sketch())
    name_last_feature(adapter, "AxialPinGrooveProfile")
    drive_jobs += groove.apply(adapter, "AxialPinGrooveProfile")
    check(
        "cut axial seam groove",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=AXIAL_PIN_LENGTH)),
    )
    name_last_feature(adapter, "AxialPinGroove")
    await volume_check(
        adapter,
        "hub axial seam groove",
        V_BODY - V_BORE - V_SEAM_GROOVE,
        max(0.5, 0.02 * V_SEAM_GROOVE),
    )

    # Inboard shoulder and the existing MHA-024 match-ream station.
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
            dimensions = name_dimensions(adapter, plane_name, ["ServicePinStation"])
            drive_jobs.append((dimensions[0], '"ServicePinStation"'))

    wizard_hole_on_cylinder(
        adapter,
        SERVICE_PIN_HOLE_SPEC,
        [-BARREL_R, SERVICE_PIN_STATION, 0.0],
        "MHA-024 hub pilot",
        name="ServicePinHole",
        point_planes=("ServicePinStationPlane", "Front Plane"),
    )
    final_volume = await _volume(adapter)
    _telemetry.info(
        f"volume after {blind_cut_dia_mm(SERVICE_PIN_HOLE_SPEC):.3f} service pilot: "
        f"{final_volume:.1f} mm^3"
    )

    # Axis1 is the shaft/hub axis; Axis2 is the axial seam-pin axis.
    await name_bore_axis(adapter, "Front Plane", 0.0, "Right Plane", 0.0, "hub axis")
    await name_bore_axis(
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
    set_dimension_bilateral_tolerance(
        adapter, "BoreProfile", "BoreDia", *deviations(HUB_BORE_BAND)
    )
    await volume_check(adapter, "driven crank hub", final_volume, 0.001 * final_volume)

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
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
