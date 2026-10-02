r"""Build MHA-179, the transgear pin (R9-68).

The plain steel pin the disc cluster runs on, pressed into the MHA-164 arm
from the rear.  Dimensions and the derived fit facts live in
``transgear_pin_spec``.

Layout: one stepped revolve about local +Z on the Right plane, origin at the
head's underside (the seat on the arm's rear face, the Front Plane).  From
the rear: the Ø5.0 head land, the Ø3.900 ground shank, the MHA-182 ring
groove (its FRONT wall, the load wall, at ``GROOVE_STATION`` from the seat)
and the plain land in front of it.  The two spherical ends are separate
revolves on the same plane.  The named plane ``GrooveLoadWall`` and
``Axis1`` serve the assembly mates.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_transgear_pin.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    POLISHED_STEEL,
    SketchDims,
    add_line_chain,
    apply_color,
    apply_material,
    bbox_extent_check,
    check,
    dimension_between,
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
from _fit_limits import deviations
from _part_pmi import author_part_pmi
from _visibility import blank_reference_geometry
from transgear_pin_spec import (
    DIA,
    DIA_BAND,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    FRONT_LAND,
    GROOVE_DIA,
    GROOVE_DIA_BAND,
    GROOVE_REAR_STATION,
    GROOVE_STATION,
    GROOVE_WIDTH,
    GROOVE_WIDTH_BAND,
    HEAD_DIA,
    HEAD_DOME_R,
    HEAD_DOME_SAG,
    HEAD_LAND,
    ISOMETRIC_VIEW_NOTE,
    OVERALL_LENGTH,
    SURFACE_FINISHES,
    TIP_DOME_R,
    TIP_DOME_SAG,
)

PART_NAME = "transgear-pin"
MATERIAL = "Plain Carbon Steel"  # 12L14/1215 (the registry row names it)

R_HEAD = HEAD_DIA / 2.0
R_SHANK = DIA / 2.0
R_GROOVE = GROOVE_DIA / 2.0
FRONT_END_STATION = GROOVE_STATION + FRONT_LAND

V_PROFILE = math.pi * (
    R_HEAD**2 * HEAD_LAND
    + R_SHANK**2 * (FRONT_END_STATION - GROOVE_WIDTH)
    + R_GROOVE**2 * GROOVE_WIDTH
)


def _cap_volume(sag: float, sphere_r: float) -> float:
    """Spherical cap of height ``sag`` on a sphere of radius ``sphere_r``."""
    return math.pi * sag**2 * (3.0 * sphere_r - sag) / 3.0


V_HEAD_DOME = _cap_volume(HEAD_DOME_SAG, HEAD_DOME_R)
V_TIP_DOME = _cap_volume(TIP_DOME_SAG, TIP_DOME_R)
V_TOTAL = V_PROFILE + V_HEAD_DOME + V_TIP_DOME


async def _dome(
    adapter,
    *,
    prefix: str,
    u_base: float,
    u_apex: float,
    sphere_r: float,
    sag: float,
    rim_r: float,
    rim_drive: str,
    station_drive: str,
) -> SketchDims:
    """A spherical end on the Right plane (the MHA-060 cap idiom): base on
    the end face at ``u_base``, apex on the axis at ``u_apex``, closed down
    the axis.  The arc runs CCW over its minor lobe, so it starts at the rim
    for a +Z end (apex at smaller u) and at the apex for a -Z end.  Its
    radius prints as ``<prefix>DomeR``."""
    toward_minus_z = u_apex > u_base
    u_centre = u_apex - sphere_r if toward_minus_z else u_apex + sphere_r
    dims = SketchDims()
    check(f"create_sketch {prefix} dome", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    check(
        f"{prefix} dome centerline",
        await adapter.add_centerline(u_base, 0.0, u_apex, 0.0),
    )
    base = check(
        f"{prefix} dome base", await adapter.add_line(u_base, 0.0, u_base, rim_r)
    )
    if toward_minus_z:
        arc_points = (u_apex, 0.0, u_base, rim_r)
    else:
        arc_points = (u_base, rim_r, u_apex, 0.0)
    arc = check(f"{prefix} dome arc", await adapter.add_arc(u_centre, 0.0, *arc_points))
    close = check(
        f"{prefix} dome close", await adapter.add_line(u_apex, 0.0, u_base, 0.0)
    )
    set_sketch_direct_db(adapter, False)
    check(
        f"{prefix} dome base vertical",
        await adapter.add_sketch_constraint(base, None, "vertical"),
    )
    check(
        f"{prefix} dome close horizontal",
        await adapter.add_sketch_constraint(close, None, "horizontal"),
    )
    check(
        f"{prefix} dome rim reach",
        await adapter.add_sketch_dimension(
            f"{base}.end", "origin", "vertical_distance", rim_r
        ),
    )
    dims.record(f"{prefix}DomeRim", rim_drive)
    check(
        f"{prefix} dome sagitta",
        await adapter.add_sketch_dimension(
            f"{close}.start", f"{close}.end", "horizontal_distance", sag
        ),
    )
    dims.record(f"{prefix}DomeSagDim", f'"{prefix}DomeSag"')
    check(
        f"{prefix} dome on axis",
        await adapter.add_sketch_constraint(
            f"{base}.start", "origin", "horizontal_points"
        ),
    )
    check(
        f"{prefix} dome station",
        await adapter.add_sketch_dimension(
            f"{base}.start", "origin", "horizontal_distance", abs(u_base)
        ),
    )
    dims.record(f"{prefix}DomeZ", station_drive)
    check(
        f"{prefix} dome radius",
        await adapter.add_sketch_dimension(arc, None, "radial", sphere_r),
    )
    sag_name = f'"{prefix}DomeSag"'
    dims.record(
        f"{prefix}DomeR",
        f"(({rim_drive}) * ({rim_drive}) + {sag_name} * {sag_name}) / (2 * {sag_name})",
    )
    return dims


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, RevolveParameters

    check("create_part", await adapter.create_part())
    # The mm suffix is load-bearing: the equation manager reads bare numbers in
    # document units (see build_crankshaft).
    for name, value in (
        ("HeadDia", HEAD_DIA),
        ("HeadLand", HEAD_LAND),
        ("ShankDia", DIA),
        ("GrooveStation", GROOVE_STATION),
        ("GrooveDia", GROOVE_DIA),
        ("GrooveWidth", GROOVE_WIDTH),
        ("FrontLand", FRONT_LAND),
        ("HeadDomeSag", HEAD_DOME_SAG),
        ("TipDomeSag", TIP_DOME_SAG),
    ):
        await set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []

    # --- Stepped profile ------------------------------------------------------
    # Right sketch (u, v) maps to model (-Z, Y): negative u runs from the
    # seat (origin) toward the front end; the head land lies at u > 0.  Every
    # axial station dimensions from the seat face, the groove's load wall
    # first; the groove width and the front land hang off that wall.
    u_rear = HEAD_LAND
    u_front = -FRONT_END_STATION
    profile = SketchDims()
    check("create_sketch pin profile", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "pin axis centerline", await adapter.add_centerline(u_rear, 0.0, u_front, 0.0)
    )
    points = [
        (u_rear, 0.0),
        (u_rear, R_HEAD),
        (0.0, R_HEAD),
        (0.0, R_SHANK),
        (-GROOVE_REAR_STATION, R_SHANK),
        (-GROOVE_REAR_STATION, R_GROOVE),
        (-GROOVE_STATION, R_GROOVE),
        (-GROOVE_STATION, R_SHANK),
        (u_front, R_SHANK),
        (u_front, 0.0),
    ]
    lines = await add_line_chain(adapter, points)
    set_sketch_direct_db(adapter, False)
    # The land in front of the groove is the same Ø3.900 cylinder as the
    # shank: collinear with it (one ground diameter, one dimension), not a
    # second horizontal with its own Ø.
    front_land_index = 7
    for index, line in enumerate(lines):
        if index == front_land_index:
            continue
        (_, v0), (_, v1) = points[index], points[(index + 1) % len(lines)]
        relation = "horizontal" if v0 == v1 else "vertical"
        check(
            f"pin profile {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    (
        _head_back,
        head_rim,
        seat_face,
        shank,
        _groove_rear_wall,
        groove_floor,
        load_wall,
        front_land,
        _front_end,
        axis_edge,
    ) = lines
    check(
        "pin axis on the origin",
        await adapter.add_sketch_constraint(
            f"{axis_edge}.end", "origin", "horizontal_points"
        ),
    )
    check(
        "seat on the origin",
        await adapter.add_sketch_constraint(
            f"{seat_face}.start", "origin", "vertical_points"
        ),
    )
    check(
        "front land on the shank cylinder",
        await adapter.add_sketch_constraint(front_land, shank, "collinear"),
    )
    for name, start, end, value in (
        ("HeadLand", f"{head_rim}.start", f"{head_rim}.end", HEAD_LAND),
        ("GrooveStation", f"{seat_face}.end", f"{load_wall}.end", GROOVE_STATION),
        ("GrooveWidth", f"{groove_floor}.start", f"{groove_floor}.end", GROOVE_WIDTH),
        ("FrontLand", f"{front_land}.start", f"{front_land}.end", FRONT_LAND),
    ):
        await dimension_between(
            adapter, start, end, "horizontal_distance", value, f"pin {name}"
        )
        profile.record(name, f'"{name}"')
    for name, line, u_mid, radius in (
        ("HeadDia", head_rim, u_rear / 2.0, R_HEAD),
        ("ShankDia", shank, -GROOVE_REAR_STATION / 2.0, R_SHANK),
        (
            "GrooveDia",
            groove_floor,
            -(GROOVE_REAR_STATION + GROOVE_STATION) / 2.0,
            R_GROOVE,
        ),
    ):
        await add_diametric_linear_dimension(
            adapter, axis, line, (u_mid, radius + 4.0), name
        )
        profile.record(name, f'"{name}"')
    await ensure_fully_defined(adapter, "pin profile sketch")
    check("exit_sketch pin profile", await adapter.exit_sketch())
    name_last_feature(adapter, "PinProfile")
    drive_jobs += profile.apply(adapter, "PinProfile")
    check("revolve pin", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Pin")
    volume = await volume_check(
        adapter, "stepped pin with its groove", V_PROFILE, 0.005 * V_PROFILE
    )

    # --- Spherical ends ----------------------------------------------------------
    for (
        prefix,
        u_base,
        u_apex,
        sphere_r,
        sag,
        rim_r,
        rim_drive,
        station_drive,
        v_dome,
    ) in (
        (
            "Head",
            u_rear,
            u_rear + HEAD_DOME_SAG,
            HEAD_DOME_R,
            HEAD_DOME_SAG,
            R_HEAD,
            '"HeadDia" / 2',
            '"HeadLand"',
            V_HEAD_DOME,
        ),
        (
            "Tip",
            u_front,
            u_front - TIP_DOME_SAG,
            TIP_DOME_R,
            TIP_DOME_SAG,
            R_SHANK,
            '"ShankDia" / 2',
            '"GrooveStation" + "FrontLand"',
            V_TIP_DOME,
        ),
    ):
        dims = await _dome(
            adapter,
            prefix=prefix,
            u_base=u_base,
            u_apex=u_apex,
            sphere_r=sphere_r,
            sag=sag,
            rim_r=rim_r,
            rim_drive=rim_drive,
            station_drive=station_drive,
        )
        feature = f"{prefix}DomeProfile"
        await ensure_fully_defined(adapter, f"{prefix.lower()} dome sketch")
        check(f"exit_sketch {prefix} dome", await adapter.exit_sketch())
        name_last_feature(adapter, feature)
        drive_jobs += dims.apply(adapter, feature)
        check(
            f"revolve {prefix} dome",
            await adapter.create_revolve(RevolveParameters(angle=360.0)),
        )
        name_last_feature(adapter, f"{prefix}Dome")
        volume = await volume_check(
            adapter, f"{prefix.lower()} dome", volume + v_dome, 0.03 * v_dome
        )

    # --- Named station for the assembly mates -----------------------------------
    check(
        "create_plane GrooveLoadWall",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Front Plane", offset=GROOVE_STATION
            )
        ),
    )
    name_last_feature(adapter, "GrooveLoadWall")
    plane_offset = name_dimensions(adapter, "GrooveLoadWall", ["GrooveLoadWallOffset"])
    drive_jobs.append((plane_offset[0], '"GrooveStation"'))
    blank_reference_geometry(adapter, (("GrooveLoadWall", "PLANE"),))
    await name_bore_axis(adapter, "Right Plane", 0.0, "Top Plane", 0.0, "pin axis")

    # Deferred drive equations, then re-check neutrality.
    await force_rebuild(adapter)
    for dimension, expression in drive_jobs:
        await drive_dimension(adapter, dimension, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven pin (equations neutral)", V_TOTAL, 0.005 * V_TOTAL
    )
    # The envelope: apex to tip along the axis, the head across it.
    await bbox_extent_check(adapter, "pin apex to tip", "z", OVERALL_LENGTH, 0.01)
    await bbox_extent_check(adapter, "head Ø (x)", "x", HEAD_DIA, 0.01)
    await bbox_extent_check(adapter, "head Ø (y)", "y", HEAD_DIA, 0.01)

    # Model-owned bands (policy rule 2): the ground shank (the running fit and
    # the press in the arm) and the ring groove's catalogue Ø and width.  The
    # groove station prints .XXX and the title block governs it.
    set_dimension_bilateral_tolerance(
        adapter, "PinProfile", "ShankDia", *deviations(DIA_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "PinProfile", "GrooveDia", *deviations(GROOVE_DIA_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "PinProfile", "GrooveWidth", *deviations(GROOVE_WIDTH_BAND)
    )

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
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
