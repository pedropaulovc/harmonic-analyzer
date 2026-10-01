r"""Build MHA-082, the transgear stud (contract §2.1, ruling R9-5).

The fixed steel stud the disc cluster runs on.  Dimensions and the derived
fit facts live in ``transgear_stub_spec``.

Layout: one stepped revolve about local +Z on the Right plane, origin at the
collar's rear face (the seat on the MHA-178 shim).  From the rear: the
#10-32 thread (through the shim and the arm), the Ø3.7 MAX rear thread
relief at the seat, the Ø12 collar, the Ø9 thrust step, the Ø3.9 journal,
the Ø2.4 MAX thread relief at the journal shoulder and the #6-32 front
thread.  Two spherical ends are separate revolves on the same plane.  Named
planes ``SleeveThrust`` (the Ø9 step face) and ``CapShoulder`` (the journal
shoulder) and ``Axis1`` serve the assembly mates; the seat is the Front
Plane.  The shim, not the stud, is faced to fit (R9-65): every axial size
but the rear relief's width dimensions from the thrust face.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_transgear_stub.py
"""

from __future__ import annotations

import math
import sys

import _telemetry
from _common import (
    POLISHED_STEEL,
    SketchDims,
    _early_bound,
    add_line_chain,
    apply_color,
    apply_material,
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
    _named_dimension,
    add_diametric_linear_dimension,
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _fit_limits import deviations
from _part_pmi import author_part_pmi
from _visibility import blank_reference_geometry
from transgear_stub_spec import (
    CAP_SHOULDER_STATION,
    COLLAR_DIA,
    COLLAR_LENGTH,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    FRONT_DOME_R,
    FRONT_DOME_SAG,
    FRONT_THREAD_END,
    FRONT_THREAD_END_STATION,
    FRONT_THREAD_MAJOR,
    ISOMETRIC_VIEW_NOTE,
    JOURNAL_DIA,
    JOURNAL_DIA_BAND,
    JOURNAL_LENGTH,
    JOURNAL_LENGTH_TOL,
    REAR_DOME_R,
    REAR_DOME_SAG,
    REAR_RELIEF_DIA,
    REAR_RELIEF_DIA_BAND,
    REAR_RELIEF_WIDTH,
    REAR_RELIEF_WIDTH_TOL,
    REAR_THREAD_END_FROM_THRUST,
    REAR_THREAD_LENGTH,
    REAR_THREAD_MAJOR,
    RELIEF_DIA,
    RELIEF_DIA_BAND,
    RELIEF_DIA_TOL_TYPE,
    RELIEF_END_STATION,
    RELIEF_WIDTH,
    RELIEF_WIDTH_TOL,
    SLEEVE_THRUST_STATION,
    STEP_DIA,
    STEP_LENGTH,
    SURFACE_FINISHES,
)

PART_NAME = "transgear-stub"
MATERIAL = "Plain Carbon Steel"  # 12L14/1215 (the registry row names it)

R_REAR = REAR_THREAD_MAJOR / 2.0
R_REAR_RELIEF = REAR_RELIEF_DIA / 2.0
R_COLLAR = COLLAR_DIA / 2.0
R_STEP = STEP_DIA / 2.0
R_JOURNAL = JOURNAL_DIA / 2.0
R_RELIEF = RELIEF_DIA / 2.0
R_FRONT = FRONT_THREAD_MAJOR / 2.0

V_PROFILE = math.pi * (
    R_REAR**2 * (REAR_THREAD_LENGTH - REAR_RELIEF_WIDTH)
    + R_REAR_RELIEF**2 * REAR_RELIEF_WIDTH
    + R_COLLAR**2 * COLLAR_LENGTH
    + R_STEP**2 * (SLEEVE_THRUST_STATION - COLLAR_LENGTH)
    + R_JOURNAL**2 * JOURNAL_LENGTH
    + R_RELIEF**2 * RELIEF_WIDTH
    + R_FRONT**2 * (FRONT_THREAD_END - RELIEF_WIDTH)
)


def _cap_volume(sag: float, sphere_r: float) -> float:
    """Spherical cap of height ``sag`` on a sphere of radius ``sphere_r``."""
    return math.pi * sag**2 * (3.0 * sphere_r - sag) / 3.0


V_REAR_DOME = _cap_volume(REAR_DOME_SAG, REAR_DOME_R)
V_FRONT_DOME = _cap_volume(FRONT_DOME_SAG, FRONT_DOME_R)
V_TOTAL = V_PROFILE + V_REAR_DOME + V_FRONT_DOME


def _single_limit_relief(
    adapter, name: str, nominal: float, lower: float, upper: float
) -> None:
    """A relief Ø as a MAX single limit carrying its band's deviations."""
    _, dimension = _named_dimension(adapter, "StudProfile", name)
    label = f"{name}@StudProfile"
    # Driven by a global the build writes in inches to 8 decimals (2.4 mm reads
    # back 2.40000003), so match at the 1e-9 m every other readback uses.
    value = float(dimension.SystemValue)
    if not math.isclose(value, nominal / 1000.0, abs_tol=1e-9):
        raise RuntimeError(
            f"{label}: nominal {value * 1000.0:.7f} is not the band's max {nominal}"
        )
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = RELIEF_DIA_TOL_TYPE
    if not tolerance.SetValues(lower / 1000.0, upper / 1000.0):
        raise RuntimeError(f"{label}: SetValues rejected {lower:+g}/{upper:+g} mm")
    if (
        int(tolerance.Type) != RELIEF_DIA_TOL_TYPE
        or not math.isclose(
            float(tolerance.GetMinValue()), lower / 1000.0, abs_tol=1e-12
        )
        or not math.isclose(
            float(tolerance.GetMaxValue()), upper / 1000.0, abs_tol=1e-12
        )
    ):
        raise RuntimeError(f"{label}: MAX-limit tolerance readback changed")
    _telemetry.success(f"{label}: single limit {nominal:g} MAX")


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
    """A spherical end on the Right plane (the MHA-060 cap idiom, as in
    ``build_pinion_cam_pin``): base on the thread end at ``u_base``, apex on
    the axis at ``u_apex``, closed down the axis.  The arc runs CCW over its
    minor lobe, so it starts at the rim for a +Z end (apex at smaller u) and at
    the apex for a -Z end.  Its radius prints as ``<prefix>DomeR``."""
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
        ("RearThreadDia", REAR_THREAD_MAJOR),
        ("RearThreadEnd", REAR_THREAD_END_FROM_THRUST),
        ("RearReliefDia", REAR_RELIEF_DIA),
        ("RearReliefWidth", REAR_RELIEF_WIDTH),
        ("CollarDia", COLLAR_DIA),
        ("StepLength", STEP_LENGTH),
        ("StepDia", STEP_DIA),
        ("ThrustStation", SLEEVE_THRUST_STATION),
        ("JournalDia", JOURNAL_DIA),
        ("JournalLength", JOURNAL_LENGTH),
        ("ReliefDia", RELIEF_DIA),
        ("ReliefWidth", RELIEF_WIDTH),
        ("ThreadDia", FRONT_THREAD_MAJOR),
        ("FrontThreadEnd", FRONT_THREAD_END),
        ("RearDomeSag", REAR_DOME_SAG),
        ("FrontDomeSag", FRONT_DOME_SAG),
    ):
        await set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []

    # --- Stepped profile ------------------------------------------------------
    # Right sketch (u, v) maps to model (-Z, Y): negative u runs from the
    # seat (origin) toward the front thread; the rear thread lies at u > 0.
    # The rear relief is a groove at the seat: the #10-32 cylinder steps down
    # to the relief Ø REAR_RELIEF_WIDTH behind the seat face.  The other rear
    # stations dimension from the thrust face.
    u_rear = REAR_THREAD_LENGTH
    u_front = -FRONT_THREAD_END_STATION
    profile = SketchDims()
    check("create_sketch stud profile", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "stud axis centerline", await adapter.add_centerline(u_rear, 0.0, u_front, 0.0)
    )
    points = [
        (u_rear, 0.0),
        (u_rear, R_REAR),
        (REAR_RELIEF_WIDTH, R_REAR),
        (REAR_RELIEF_WIDTH, R_REAR_RELIEF),
        (0.0, R_REAR_RELIEF),
        (0.0, R_COLLAR),
        (-COLLAR_LENGTH, R_COLLAR),
        (-COLLAR_LENGTH, R_STEP),
        (-SLEEVE_THRUST_STATION, R_STEP),
        (-SLEEVE_THRUST_STATION, R_JOURNAL),
        (-CAP_SHOULDER_STATION, R_JOURNAL),
        (-CAP_SHOULDER_STATION, R_RELIEF),
        (-RELIEF_END_STATION, R_RELIEF),
        (-RELIEF_END_STATION, R_FRONT),
        (u_front, R_FRONT),
        (u_front, 0.0),
    ]
    lines = await add_line_chain(adapter, points)
    set_sketch_direct_db(adapter, False)
    for index, line in enumerate(lines):
        (_, v0), (_, v1) = points[index], points[(index + 1) % len(lines)]
        relation = "horizontal" if v0 == v1 else "vertical"
        check(
            f"stud profile {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    (
        rear_end,
        rear_thread,
        _rear_relief_flank,
        rear_relief_floor,
        seat_face,
        collar,
        _collar_front,
        step,
        thrust_face,
        journal,
        shoulder,
        relief_floor,
        _relief_flank,
        front_thread,
        _front_end,
        axis_edge,
    ) = lines
    check(
        "stud axis on the origin",
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
    for name, start, end, value in (
        (
            "RearThreadEnd",
            f"{rear_end}.end",
            f"{thrust_face}.start",
            REAR_THREAD_END_FROM_THRUST,
        ),
        (
            "RearReliefWidth",
            f"{rear_relief_floor}.start",
            f"{rear_relief_floor}.end",
            REAR_RELIEF_WIDTH,
        ),
        ("StepLength", f"{step}.start", f"{step}.end", STEP_LENGTH),
        (
            "ThrustStation",
            f"{seat_face}.end",
            f"{journal}.start",
            SLEEVE_THRUST_STATION,
        ),
        ("JournalLength", f"{journal}.start", f"{journal}.end", JOURNAL_LENGTH),
        ("ReliefWidth", f"{relief_floor}.start", f"{relief_floor}.end", RELIEF_WIDTH),
        (
            "FrontThreadEnd",
            f"{shoulder}.start",
            f"{front_thread}.end",
            FRONT_THREAD_END,
        ),
    ):
        await dimension_between(
            adapter, start, end, "horizontal_distance", value, f"stud {name}"
        )
        profile.record(name, f'"{name}"')
    for name, line, u_mid, radius in (
        ("RearThreadDia", rear_thread, u_rear / 2.0, R_REAR),
        (
            "RearReliefDia",
            rear_relief_floor,
            REAR_RELIEF_WIDTH / 2.0,
            R_REAR_RELIEF,
        ),
        ("CollarDia", collar, -COLLAR_LENGTH / 2.0, R_COLLAR),
        (
            "StepDia",
            step,
            -(COLLAR_LENGTH + SLEEVE_THRUST_STATION) / 2.0,
            R_STEP,
        ),
        (
            "JournalDia",
            journal,
            -(SLEEVE_THRUST_STATION + CAP_SHOULDER_STATION) / 2.0,
            R_JOURNAL,
        ),
        (
            "ReliefDia",
            relief_floor,
            -(CAP_SHOULDER_STATION + RELIEF_END_STATION) / 2.0,
            R_RELIEF,
        ),
        ("ThreadDia", front_thread, (u_front - RELIEF_END_STATION) / 2.0, R_FRONT),
    ):
        await add_diametric_linear_dimension(
            adapter, axis, line, (u_mid, radius + 4.0), name
        )
        profile.record(name, f'"{name}"')
    await ensure_fully_defined(adapter, "stud profile sketch")
    check("exit_sketch stud profile", await adapter.exit_sketch())
    name_last_feature(adapter, "StudProfile")
    drive_jobs += profile.apply(adapter, "StudProfile")
    check("revolve stud", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Stud")
    volume = await volume_check(
        adapter, "stepped stud with both reliefs", V_PROFILE, 0.005 * V_PROFILE
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
            "Rear",
            u_rear,
            u_rear + REAR_DOME_SAG,
            REAR_DOME_R,
            REAR_DOME_SAG,
            R_REAR,
            '"RearThreadDia" / 2',
            '"RearThreadEnd" - "ThrustStation"',
            V_REAR_DOME,
        ),
        (
            "Front",
            u_front,
            u_front - FRONT_DOME_SAG,
            FRONT_DOME_R,
            FRONT_DOME_SAG,
            R_FRONT,
            '"ThreadDia" / 2',
            '"ThrustStation" + "JournalLength" + "FrontThreadEnd"',
            V_FRONT_DOME,
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

    # --- Named stations for the assembly mates ----------------------------------
    for plane, offset, drive in (
        ("SleeveThrust", SLEEVE_THRUST_STATION, '"ThrustStation"'),
        ("CapShoulder", CAP_SHOULDER_STATION, '"ThrustStation" + "JournalLength"'),
    ):
        check(
            f"create_plane {plane}",
            await adapter.create_plane(
                CreatePlaneParameters(
                    mode="offset", base_plane="Front Plane", offset=offset
                )
            ),
        )
        name_last_feature(adapter, plane)
        plane_offset = name_dimensions(adapter, plane, [f"{plane}Offset"])
        drive_jobs.append((plane_offset[0], drive))
        blank_reference_geometry(adapter, ((plane, "PLANE"),))
    await name_bore_axis(adapter, "Right Plane", 0.0, "Top Plane", 0.0, "stud axis")

    # Deferred drive equations, then re-check neutrality.
    await force_rebuild(adapter)
    for dimension, expression in drive_jobs:
        await drive_dimension(adapter, dimension, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven stud (equations neutral)", V_TOTAL, 0.005 * V_TOTAL
    )

    # Model-owned bands (policy rule 2): the running-fit journal and its
    # length (cluster float), each relief's width (the 1.0-1.2 window) and
    # each relief Ø's single MAX limit.
    set_dimension_bilateral_tolerance(
        adapter, "StudProfile", "JournalDia", *deviations(JOURNAL_DIA_BAND)
    )
    set_dimension_symmetric_tolerance(
        adapter, "StudProfile", "JournalLength", JOURNAL_LENGTH_TOL
    )
    set_dimension_symmetric_tolerance(
        adapter, "StudProfile", "ReliefWidth", RELIEF_WIDTH_TOL
    )
    set_dimension_symmetric_tolerance(
        adapter, "StudProfile", "RearReliefWidth", REAR_RELIEF_WIDTH_TOL
    )
    _single_limit_relief(adapter, "ReliefDia", RELIEF_DIA, *deviations(RELIEF_DIA_BAND))
    _single_limit_relief(
        adapter, "RearReliefDia", REAR_RELIEF_DIA, *deviations(REAR_RELIEF_DIA_BAND)
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
