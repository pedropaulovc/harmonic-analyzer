r"""Build MHA-PD-23, the transgear pin (R9-68).

The plain steel pin the disc cluster runs on, pressed into the MHA-PD-18 arm
from the rear.  Dimensions and the derived fit facts live in
``pd_transgear_pin_spec``.

Layout: one stepped revolve about local +Z on the Right plane, origin at the
head's underside (the seat on the arm's rear face, the Front Plane).  From
the rear: the Ø.20 head land, the Ø.125 turned shank, the MHA-PD-VN-61 ring
groove (its FRONT wall, the load wall, at ``GROOVE_STATION`` from the seat)
and the plain land in front of it.  The two spherical ends are separate
revolves on the same plane.  The named plane ``GrooveLoadWall`` and
``Axis1`` serve the assembly mates.  #290: the part saves in inch units
(the row's ``drawing_unit``); its globals stay millimetre values.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pd_transgear_pin.py
"""

from __future__ import annotations

import math
import sys
from enum import Enum

from _appearance import POLISHED_STEEL, apply_color, apply_material
from _bore_axis import name_bore_axis
from _check import check
from _dimensions import drive_dimension, name_dimensions, set_global
from _document_units import apply_package_model_units
from _feature_tree import name_last_feature
from _part_checks import bbox_extent_check, report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _drawing_dimension_insert import add_diametric_linear_dimension
from _drawing_precision import _named_dimensions, apply_drawing_precision
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_tolerances import (
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _fit_deviations import deviations
from _part_pmi import author_part_pmi
from _visibility import blank_reference_geometry
import pd_transgear_pin_callouts as callouts
from pd_transgear_pin_spec import (
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
    GROOVE_STATION_BAND,
    GROOVE_WIDTH,
    GROOVE_WIDTH_BAND,
    HEAD_DIA,
    HEAD_DOME_R,
    HEAD_DOME_SAG,
    HEAD_LAND,
    ISOMETRIC_VIEW_NOTE,
    OVERALL_LENGTH,
    SEAT_FILLET_R,
    SURFACE_FINISHES,
    TIP_DOME_R,
    TIP_DOME_SAG,
    UNIT,
)

PART_NAME = "pd-transgear-pin"
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
# Pappus: the seat root's spandrel r^2 (1 - pi/4), its centroid
# r (10 - 3 pi) / (3 (4 - pi)) out from the shank, revolved about the axis.
V_SEAT_FILLET = (
    2.0
    * math.pi
    * (R_SHANK + SEAT_FILLET_R * (10.0 - 3.0 * math.pi) / (3.0 * (4.0 - math.pi)))
    * SEAT_FILLET_R**2
    * (1.0 - math.pi / 4.0)
)
V_TOTAL = V_PROFILE + V_HEAD_DOME + V_TIP_DOME + V_SEAT_FILLET


class StationAnchor(Enum):
    """Which dome point ``<prefix>DomeZ`` stations from the head seat."""

    BASE = "base"  # the dome's base, on its land's end face
    APEX = "apex"  # the dome's apex: the one point the shop can pick up


def author_dimension_callouts(adapter) -> None:
    """Write every authored text lane on its source dimension, read it back.

    The drawing only reads these lanes: set from the sheet they would write
    through to this part outside its recipe (#1942).
    """
    for feature, by_name in callouts.authored_text().items():
        displays = _named_dimensions(adapter, feature, set(by_name))
        for name, lanes in by_name.items():
            display, _dimension = displays[name]
            for lane, text in lanes.items():
                display.SetText(lane, text)
                printed = str(display.GetText(lane) or "")
                if callouts.callout_rows(printed) != callouts.callout_rows(text):
                    raise RuntimeError(
                        f"{name}@{feature}: text lane {lane} did not persist: "
                        f"{printed!r}"
                    )


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
    station_anchor: StationAnchor,
) -> SketchDims:
    """A spherical end on the Right plane (the MHA-DT-17 cap idiom): base on
    the end face at ``u_base``, apex on the axis at ``u_apex``, closed down
    the axis.  The arc runs CCW over its minor lobe, so it starts at the rim
    for a +Z end (apex at smaller u) and at the apex for a -Z end.  Its
    radius prints as ``<prefix>DomeR``.  ``<prefix>DomeZ`` stations the
    ``station_anchor`` point from the head seat."""
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
    station_point, station_u = {
        StationAnchor.BASE: (f"{base}.start", u_base),
        StationAnchor.APEX: (f"{close}.start", u_apex),
    }[station_anchor]
    check(
        f"{prefix} dome station",
        await adapter.add_sketch_dimension(
            station_point, "origin", "horizontal_distance", abs(station_u)
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
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)
    # The mm suffix is load-bearing: the equation manager reads bare numbers in
    # document units (see build_dt_crankshaft).
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
        ("SeatRadius", SEAT_FILLET_R),
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
    # shank: collinear with it (one turned diameter, one dimension), not a
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

    # --- Seat root: the tool-nose radius the print allows (R MAX) ---------------
    # Picked on the circular edge where the shank meets the seat face at
    # z = 0: the only edge through that point.
    check(
        "fillet seat root",
        await adapter.add_fillet(SEAT_FILLET_R, [[R_SHANK, 0.0, 0.0]]),
    )
    name_last_feature(adapter, "SeatFillet")
    fillet_dim = name_dimensions(adapter, "SeatFillet", ["SeatRadius"])
    drive_jobs.append((fillet_dim[0], '"SeatRadius"'))
    volume = await volume_check(
        adapter, "seat root fillet", volume + V_SEAT_FILLET, 0.005 * V_PROFILE
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
        station_anchor,
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
            StationAnchor.BASE,
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
            '"GrooveStation" + "FrontLand" + "TipDomeSag"',
            StationAnchor.APEX,
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
            station_anchor=station_anchor,
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

    # Model-owned bands (drawing-simplicity-policy.md `How the repository implements the guidelines`): the turned shank (the running fit and
    # the press in the arm), the ring groove's catalogue Ø and width, and the
    # groove station, a disc-cluster stack term at the cluster's band.  The
    # front land prints .XX and the title block governs it.
    set_dimension_bilateral_tolerance(
        adapter, "PinProfile", "ShankDia", *deviations(DIA_BAND), display_unit=UNIT
    )
    set_dimension_bilateral_tolerance(
        adapter,
        "PinProfile",
        "GrooveDia",
        *deviations(GROOVE_DIA_BAND),
        display_unit=UNIT,
    )
    set_dimension_bilateral_tolerance(
        adapter,
        "PinProfile",
        "GrooveWidth",
        *deviations(GROOVE_WIDTH_BAND),
        display_unit=UNIT,
    )
    set_dimension_symmetric_tolerance(
        adapter,
        "PinProfile",
        "GrooveStation",
        GROOVE_STATION_BAND,
        display_unit=UNIT,
    )

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    author_dimension_callouts(adapter)
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
