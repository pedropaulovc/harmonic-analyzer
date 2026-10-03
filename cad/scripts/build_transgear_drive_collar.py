r"""Build MHA-177, the transgear drive collar (contract §1.2, round 10).

A brass collar reamed to slide on the knob shaft's plain Ø6.35 core, set and
pinned at assembly; its front face seats the removable T24, whose bore takes
the front pilot and whose holes drop over two dowels pressed through the
collar.  The pilot runs through the T24 and is the thumbnut's seat: supplied
long and faced at assembly to stand 0.05..0.15 proud of the T24's front face,
so the nut bears on the pilot and the T24 floats under it.  Dimensions and
the derived fit facts live in ``transgear_drive_collar_spec``.

Layout: axis local +Z (machine +Z, rearward), origin on the front (seat)
face, the Front Plane; the body runs z 0..LENGTH, the pilot in front of it.

* ``Axis1``: the bore axis (Top Plane x Right Plane), made first so the
  assembly mates always find it by that name.
* ``Collar``: the Ø17.5 body, extruded rearward from the Front Plane.
* ``Pilot``: the Ø10.00 pilot, extruded forward from the Front Plane to its
  nominal fitted length (faced to fit at assembly).
* ``Bore``: the Ø6.350 reamed bore, cut through both ways.
* ``Slot``: the diametral rear slot, a Right-plane rectangle from the rear
  face to the slot floor, cut through both ways along X, so its width and
  depth print in the side view.
* ``PinHoles``: the two drive-pin holes on local ±Y, cut from ``RearFace``
  through the body.

Datums: ``RearFace`` (z LENGTH), ``SlotFloor`` (z SLOT_FLOOR_Z),
``PilotFront`` (z -PILOT_LENGTH), ``DrivePinAxis1`` (+Y) and
``DrivePinAxis2`` (-Y), all hidden.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_transgear_drive_collar.py
"""

from __future__ import annotations

import math
import sys

import _telemetry
from _common import (
    SketchDims,
    add_line_chain,
    apply_material,
    check,
    define_circle,
    define_rectilinear_chain,
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
    set_dimension_symmetric_tolerance,
)
from _fit_limits import deviations
from _visibility import blank_reference_geometry
from transgear_drive_collar_spec import (
    BORE_DIA,
    BORE_DIA_BAND,
    BORE_PIN_WALL_WORST,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    DRIVE_PIN_COLLAR_RIM_WORST,
    ISOMETRIC_VIEW_NOTE,
    LENGTH,
    OD,
    OD_BAND,
    PILOT_DIA,
    PILOT_DIA_BAND,
    PILOT_LENGTH,
    PILOT_WALL_WORST,
    PIN_CIRCLE_RADIUS,
    PIN_HOLE_BAND,
    PIN_HOLE_DEPTH,
    PIN_HOLE_DIA,
    PIN_OFFSET_TOL,
    PIN_REAR_INSET_WORST,
    SLOT_DEPTH,
    SLOT_DEPTH_BAND,
    SLOT_FLOOR_WALL_WORST,
    SLOT_FLOOR_Z,
    SLOT_PIN_WALL_WORST,
    SLOT_WIDTH,
    SLOT_WIDTH_BAND,
)

PART_NAME = "transgear-drive-collar"
MATERIAL = "Brass"  # C36000 free-machining brass (the registry row names it)

OD_R = OD / 2.0
PILOT_R = PILOT_DIA / 2.0
BORE_R = BORE_DIA / 2.0
PIN_HOLE_R = PIN_HOLE_DIA / 2.0
# How far the through cuts run past the part into air.
_OVERRUN = 1.0


def _strip_area(radius: float, half_width: float) -> float:
    """Area of a disc of ``radius`` inside the band |y| <= ``half_width``."""
    return 2.0 * (
        half_width * math.sqrt(radius**2 - half_width**2)
        + radius**2 * math.asin(half_width / radius)
    )


V_COLLAR = math.pi * OD_R**2 * LENGTH
V_PILOT = math.pi * PILOT_R**2 * PILOT_LENGTH
V_BORE = math.pi * BORE_R**2 * (LENGTH + PILOT_LENGTH)
# The slot crosses the whole collar behind the slot floor, less the bore.
V_SLOT = SLOT_DEPTH * (
    _strip_area(OD_R, SLOT_WIDTH / 2.0) - _strip_area(BORE_R, SLOT_WIDTH / 2.0)
)
V_PIN_HOLES = 2.0 * math.pi * PIN_HOLE_R**2 * PIN_HOLE_DEPTH
V_TOTAL = V_COLLAR + V_PILOT - V_BORE - V_SLOT - V_PIN_HOLES


async def _front_circle(
    adapter, radius: float, name: str, label: str
) -> list[tuple[str, str]]:
    """One on-axis circle on the Front Plane, its diameter named and driven by
    the global of the same name; returns its drive job."""
    dims = SketchDims()
    check(f"create_sketch {label}", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        radius,
        label,
        dims=dims,
        names=(None, None, name),
        drives=(None, None, f'"{name}"'),
    )
    await ensure_fully_defined(adapter, f"{label} sketch")
    check(f"exit_sketch {label}", await adapter.exit_sketch())
    feature = name_last_feature(adapter, name.replace("Dia", "Profile"))
    return dims.apply(adapter, feature)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreatePlaneParameters,
        ExtrusionParameters,
        RevolveParameters,
    )

    check("create_part", await adapter.create_part())
    # The mm suffix is load-bearing: the equation manager reads bare numbers in
    # document units (see build_crankshaft).
    for name, value in (
        ("CollarDia", OD),
        ("CollarLength", LENGTH),
        ("PilotDia", PILOT_DIA),
        ("PilotLength", PILOT_LENGTH),
        ("BoreDia", BORE_DIA),
        ("SlotWidth", SLOT_WIDTH),
        ("SlotDepth", SLOT_DEPTH),
        ("PinCircleRadius", PIN_CIRCLE_RADIUS),
        ("PinHoleDia", PIN_HOLE_DIA),
    ):
        await set_global(adapter, name, f"{value}mm")

    # The bore axis before any other reference geometry, so it is Axis1.
    bore_axis = await name_bore_axis(
        adapter, "Top Plane", 0.0, "Right Plane", 0.0, "collar bore axis"
    )
    if bore_axis != "Axis1":
        raise RuntimeError(f"the collar's bore axis is {bore_axis!r}, not Axis1")

    drive_jobs: list[tuple[str, str]] = []

    # --- Body and pilot: one stepped profile revolved about the axis -----------
    # Right sketch (u, v) maps to model (-Z, Y), the plane the *Right side view
    # looks at, so the turned diameters and both lengths print there (policy
    # rule 7).  The seat face is u = 0; the body runs to the rear face at
    # u = -LENGTH, the pilot to its front face at u = +PILOT_LENGTH.  Both
    # lengths run from the seat face, the datum the T24 seats on.  A profile
    # turned the wrong way fails the volume gate and the planes' rebuild.
    body = SketchDims()
    check("create_sketch body profile", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "body axis centerline",
        await adapter.add_centerline(-LENGTH, 0.0, PILOT_LENGTH, 0.0),
    )
    points = [
        (-LENGTH, 0.0),
        (-LENGTH, OD_R),
        (0.0, OD_R),
        (0.0, PILOT_R),
        (PILOT_LENGTH, PILOT_R),
        (PILOT_LENGTH, 0.0),
    ]
    lines = await add_line_chain(adapter, points)
    set_sketch_direct_db(adapter, False)
    for index, line in enumerate(lines):
        (_, v0), (_, v1) = points[index], points[(index + 1) % len(lines)]
        relation = "horizontal" if v0 == v1 else "vertical"
        check(
            f"body profile {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    rear_face, collar, seat_face, pilot, pilot_front, axis_edge = lines
    check(
        "body axis on the origin",
        await adapter.add_sketch_constraint(
            f"{axis_edge}.end", "origin", "horizontal_points"
        ),
    )
    check(
        "seat face on the origin",
        await adapter.add_sketch_constraint(
            f"{seat_face}.start", "origin", "vertical_points"
        ),
    )
    for name, line, u_mid, radius in (
        ("CollarDia", collar, -LENGTH / 2.0, OD_R),
        ("PilotDia", pilot, PILOT_LENGTH / 2.0, PILOT_R),
    ):
        await add_diametric_linear_dimension(
            adapter, axis, line, (u_mid, radius + 4.0), name
        )
        body.record(name, f'"{name}"')
    for name, start, end, value in (
        ("CollarLength", f"{seat_face}.start", f"{rear_face}.end", LENGTH),
        ("PilotLength", f"{seat_face}.end", f"{pilot_front}.start", PILOT_LENGTH),
    ):
        await dimension_between(
            adapter, start, end, "horizontal_distance", value, f"body {name}"
        )
        body.record(name, f'"{name}"')
    await ensure_fully_defined(adapter, "body profile sketch")
    check("exit_sketch body profile", await adapter.exit_sketch())
    name_last_feature(adapter, "BodyProfile")
    drive_jobs += body.apply(adapter, "BodyProfile")
    check("revolve body", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Body")
    volume = await volume_check(
        adapter, "collar body and pilot", V_COLLAR + V_PILOT, 0.005 * V_COLLAR
    )

    # --- Reamed bore through pilot and body ------------------------------------
    drive_jobs += await _front_circle(adapter, BORE_R, "BoreDia", "bore")
    check(
        "cut bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(
                depth=2.0 * (LENGTH + PILOT_LENGTH + _OVERRUN), both_directions=True
            )
        ),
    )
    name_last_feature(adapter, "Bore")
    volume = await volume_check(adapter, "bore", volume - V_BORE, 0.01 * V_BORE)

    # --- Datum planes -------------------------------------------------------------
    stations = (
        ("RearFace", LENGTH, '"CollarLength"'),
        ("SlotFloor", SLOT_FLOOR_Z, '"CollarLength" - "SlotDepth"'),
        ("PilotFront", -PILOT_LENGTH, '"PilotLength"'),
    )
    for plane, offset, expression in stations:
        check(
            f"create_plane {plane} (Front Plane {offset:+g})",
            await adapter.create_plane(
                CreatePlaneParameters(
                    mode="offset", base_plane="Front Plane", offset=offset
                )
            ),
        )
        name_last_feature(adapter, plane)
        offset_dim = name_dimensions(adapter, plane, [f"{plane}Offset"])
        drive_jobs.append((offset_dim[0], expression))
    blank_reference_geometry(adapter, tuple((p, "PLANE") for p, _, _ in stations))

    # --- Diametral rear slot along X ----------------------------------------------
    # Right sketch (u, v) maps to model (-Z, Y).  The rectangle's rear edge
    # lies on the rear face and its front edge is the slot floor, so its two
    # driving spans ARE the printed depth and width; cut through both ways
    # along X.  A slot on the wrong side of the origin would cut the pilot's
    # air and fail the volume gate.
    slot = SketchDims()
    corners = [
        (-LENGTH, -SLOT_WIDTH / 2.0),
        (-SLOT_FLOOR_Z, -SLOT_WIDTH / 2.0),
        (-SLOT_FLOOR_Z, SLOT_WIDTH / 2.0),
        (-LENGTH, SLOT_WIDTH / 2.0),
    ]
    check("create_sketch slot", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    slot_lines = await add_line_chain(adapter, corners)
    set_sketch_direct_db(adapter, False)
    await define_rectilinear_chain(
        adapter,
        slot_lines,
        corners,
        anchor=0,
        label="rear slot",
        dims=slot,
        names=["SlotDepth", "SlotWidth", "SlotRearZ", "SlotHalfWidth"],
        drives=['"SlotDepth"', '"SlotWidth"', '"CollarLength"', '"SlotWidth" / 2'],
    )
    await ensure_fully_defined(adapter, "slot sketch")
    check("exit_sketch slot", await adapter.exit_sketch())
    name_last_feature(adapter, "SlotProfile")
    drive_jobs += slot.apply(adapter, "SlotProfile")
    check(
        "cut slot",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=OD + 2.0 * _OVERRUN, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Slot")
    volume = await volume_check(adapter, "rear slot", volume - V_SLOT, 0.02 * V_SLOT)

    # --- Drive-pin holes, reamed through ------------------------------------------
    # Sketched on RearFace (a Front-parallel sketch reads (x, y) = (X, Y)) and
    # cut toward the seat face, the cut's default opposite the sketch normal;
    # the overrun breaks out into the air beside the pilot (the holes' inner
    # edge r 5.81 clears the pilot's r 5.0).
    holes = SketchDims()
    check("create_sketch pin holes", await adapter.create_sketch("RearFace"))
    for label, y in (("PinPos", PIN_CIRCLE_RADIUS), ("PinNeg", -PIN_CIRCLE_RADIUS)):
        await define_circle(
            adapter,
            0.0,
            y,
            PIN_HOLE_R,
            f"drive-pin hole {label}",
            dims=holes,
            names=(None, f"{label}Y", f"{label}Dia"),
            drives=(None, '"PinCircleRadius"', '"PinHoleDia"'),
        )
    await ensure_fully_defined(adapter, "pin-hole sketch")
    check("exit_sketch pin holes", await adapter.exit_sketch())
    name_last_feature(adapter, "PinHoleProfile")
    drive_jobs += holes.apply(adapter, "PinHoleProfile")
    check(
        "cut pin holes",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=PIN_HOLE_DEPTH + _OVERRUN)
        ),
    )
    name_last_feature(adapter, "PinHoles")
    volume = await volume_check(
        adapter, "drive-pin holes", volume - V_PIN_HOLES, 0.05 * V_PIN_HOLES
    )

    # The pins' axes: DrivePinAxis1 on local +Y, DrivePinAxis2 opposite.
    for axis_name, y in (
        ("DrivePinAxis1", PIN_CIRCLE_RADIUS),
        ("DrivePinAxis2", -PIN_CIRCLE_RADIUS),
    ):
        await name_bore_axis(
            adapter,
            "Right Plane",
            0.0,
            "Top Plane",
            y,
            axis_name,
            drive_b='"PinCircleRadius"',
            drive_jobs=drive_jobs,
        )
        name_last_feature(adapter, axis_name)

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dimension, expression in drive_jobs:
        await drive_dimension(adapter, dimension, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven collar (equations neutral)", V_TOTAL, 0.005 * V_TOTAL
    )
    _telemetry.info(
        f"drive collar walls (worst case): pin hole to rim "
        f"{DRIVE_PIN_COLLAR_RIM_WORST:.2f}, pilot {PILOT_WALL_WORST:.2f}, slot "
        f"floor {SLOT_FLOOR_WALL_WORST:.2f}, slot side {SLOT_PIN_WALL_WORST:.3f}, "
        f"bore to pin hole {BORE_PIN_WALL_WORST:.3f}; pressed pin end "
        f"{PIN_REAR_INSET_WORST:.4f} min inside the rear face"
    )

    # Bands (transgear_drive_collar_spec): the seat O.D., the pilot, the
    # reamed bore, the slot and the drive-pin press carry their own; the
    # length prints at the title block's row and the pilot length is set by
    # facing at assembly (the sheet's fitted-band callout), so no model band.
    set_dimension_bilateral_tolerance(
        adapter, "BodyProfile", "CollarDia", *deviations(OD_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "BodyProfile", "PilotDia", *deviations(PILOT_DIA_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "BoreProfile", "BoreDia", *deviations(BORE_DIA_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "SlotProfile", "SlotWidth", *deviations(SLOT_WIDTH_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "SlotProfile", "SlotDepth", *deviations(SLOT_DEPTH_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "PinHoleProfile", "PinPosDia", *deviations(PIN_HOLE_BAND)
    )
    set_dimension_symmetric_tolerance(
        adapter, "PinHoleProfile", "PinPosY", PIN_OFFSET_TOL
    )
    set_dimension_symmetric_tolerance(
        adapter, "PinHoleProfile", "PinNegY", PIN_OFFSET_TOL
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
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
