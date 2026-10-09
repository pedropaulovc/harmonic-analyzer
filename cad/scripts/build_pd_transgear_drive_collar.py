r"""Build MHA-PD-022, the transgear drive collar (contract §1.2, round 10).

A brass collar with a true D-bore on the integral knob's solid D-core.
Its rear face reacts on the actual gear front F; the body is supplied long
and faced at assembly.  The pilot seats the thumbnut while the removable
T24 floats 0.05..0.15 under it.  Both dimensions and fitted acceptance live
in ``pd_transgear_drive_collar_spec``.

Layout: axis local +Z (machine +Z, rearward), origin on the front (seat)
face, the Front Plane; the body runs z 0..LENGTH, the pilot in front of it.

* ``Axis1``: the bore axis (Top Plane x Right Plane), made first so the
  assembly mates always find it by that name.
* ``Body``: the turned Ø17.5 body and Ø10 pilot.
* ``Bore``: the actual major-arc-plus-flat D opening through both.
* ``RearBoreChamfer``: both rear D edges, 45-degree equal-leg entry relief.
* ``PinHoles``: the two drive-pin holes on local ±Y, cut from ``RearFace``
  through the body.

Datums: ``RearFace`` (z LENGTH), ``PilotFront`` (z -PILOT_LENGTH),
``DrivePinAxis1`` (+Y) and ``DrivePinAxis2`` (-Y), all hidden.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pd_transgear_drive_collar.py
"""

from __future__ import annotations

import math
import sys

import _telemetry
from _common import (
    SketchDims,
    _early_bound,
    _feature_by_name,
    add_line_chain,
    apply_material,
    check,
    define_circle,
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
from _gtol_spec import PlanarFace
from _part_pmi import _resolve_faces
from _visibility import blank_reference_geometry
from pd_transgear_drive_collar_spec import (
    BORE_DIA,
    BORE_DIA_BAND,
    BORE_ENTRY_BREAK,
    BORE_ENTRY_BREAK_BAND,
    BORE_ENTRY_BREAK_ANGLE_DEG,
    BORE_PIN_WALL_WORST,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    DRIVE_PIN_COLLAR_RIM_WORST,
    FLAT_BAND,
    FLAT_LIMITS,
    FLAT_PLACES,
    FLAT_TOL_TYPE,
    FLAT_TO_AXIS,
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
)

PART_NAME = "pd-transgear-drive-collar"
MATERIAL = "Brass"  # C36000 free-machining brass (the registry row names it)

OD_R = OD / 2.0
PILOT_R = PILOT_DIA / 2.0
BORE_R = BORE_DIA / 2.0
PIN_HOLE_R = PIN_HOLE_DIA / 2.0
# How far the through cuts run past the part into air.
_OVERRUN = 1.0


def _d_bore_area(radius: float, flat: float) -> float:
    """Exact area of the retained major arc closed by its D-flat."""
    if not 0.0 < flat < radius:
        raise ValueError("D-bore flat must lie inside its round envelope")
    chord = math.sqrt(radius * radius - flat * flat)
    return math.pi * radius * radius - (
        radius * radius * math.acos(flat / radius) - flat * chord
    )


def _entry_break_volume(radius: float, flat: float, leg: float) -> float:
    """Equal-leg relief offsets both the arc and flat; no circular proxy."""
    base = _d_bore_area(radius, flat)
    steps = 16
    dz = leg / steps
    return dz / 3.0 * sum(
        (1 if i in (0, steps) else 4 if i % 2 else 2)
        * (_d_bore_area(radius + i * dz, flat + i * dz) - base)
        for i in range(steps + 1)
    )


V_COLLAR = math.pi * OD_R**2 * LENGTH
V_PILOT = math.pi * PILOT_R**2 * PILOT_LENGTH
V_BORE = _d_bore_area(BORE_R, FLAT_TO_AXIS) * (LENGTH + PILOT_LENGTH)
V_ENTRY_BREAK = _entry_break_volume(BORE_R, FLAT_TO_AXIS, BORE_ENTRY_BREAK)
V_PIN_HOLES = 2.0 * math.pi * PIN_HOLE_R**2 * PIN_HOLE_DEPTH
V_TOTAL = V_COLLAR + V_PILOT - V_BORE - V_ENTRY_BREAK - V_PIN_HOLES


def _as_construction(adapter, entity_id: str) -> None:
    segment = _early_bound(adapter._sketch_entities[entity_id], "ISketchSegment")
    segment.ConstructionGeometry = True
    if segment.ConstructionGeometry is not True:
        raise RuntimeError(f"{entity_id} did not take the construction flag")


async def _d_bore(adapter) -> list[tuple[str, str]]:
    """The disc-hub's native major-arc/flat construction, not a round hole."""
    bore = SketchDims()
    check("create_sketch D-bore", await adapter.create_sketch("Front"))
    chord = math.sqrt(BORE_R * BORE_R - FLAT_TO_AXIS * FLAT_TO_AXIS)
    set_sketch_direct_db(adapter, True)
    arc = check(
        "D-bore major arc",
        await adapter.add_arc(0.0, 0.0, chord, -FLAT_TO_AXIS, -chord, -FLAT_TO_AXIS),
    )
    flat = check(
        "D-bore flat",
        await adapter.add_line(-chord, -FLAT_TO_AXIS, chord, -FLAT_TO_AXIS),
    )
    witness = check(
        "D-bore flat witness", await adapter.add_line(0.0, 0.0, 0.0, -FLAT_TO_AXIS)
    )
    set_sketch_direct_db(adapter, False)
    _as_construction(adapter, witness)
    for label, first, second, relation in (
        ("arc centre", f"{arc}.center", "origin", "coincident"),
        ("left junction", f"{flat}.start", f"{arc}.end", "coincident"),
        ("right junction", f"{flat}.end", f"{arc}.start", "coincident"),
        ("horizontal flat", flat, None, "horizontal"),
        ("vertical witness", witness, None, "vertical"),
        ("witness on axis", f"{witness}.start", "origin", "coincident"),
        ("witness on flat", f"{witness}.end", flat, "coincident"),
    ):
        check(label, await adapter.add_sketch_constraint(first, second, relation))
    check(
        "D-bore diameter", await adapter.add_sketch_dimension(arc, None, "diameter", BORE_DIA)
    )
    bore.record("BoreDia", '"BoreDia"')
    await dimension_between(
        adapter, f"{witness}.start", f"{witness}.end", "vertical_distance",
        FLAT_TO_AXIS, "D-flat from the bore axis",
    )
    bore.record("FlatToAxis", '"FlatToAxis"')
    await ensure_fully_defined(adapter, "D-bore sketch")
    check("exit_sketch D-bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    return bore.apply(adapter, "BoreProfile")


async def _rear_bore_chamfer(adapter) -> list[str]:
    """Both rear D edges have the controlled equal-leg functional entry."""
    from solidworks_mcp.adapters.solidworks.features import _select_edges_geometric

    points = [[0.0, BORE_R, LENGTH], [0.0, -FLAT_TO_AXIS, LENGTH]]
    if _select_edges_geometric(adapter, points, tol_mm=0.001) is not True:
        raise RuntimeError("rear D entry: arc and flat edges did not resolve")
    manager = adapter.currentModel.FeatureManager
    if manager is None:
        raise RuntimeError("rear D entry: native feature manager is missing")
    # The rear end face meets both the axial bore cylinder and D-flat at 90
    # degrees. The farm-proven crank-drive-gear D entry uses this same native
    # 45-degree angle-distance path: both physical legs equal the source width.
    check(
        "rear D entry chamfer",
        await adapter.add_chamfer(BORE_ENTRY_BREAK, points, tangent_propagation=False),
    )
    name_last_feature(adapter, "RearBoreChamfer")
    feature = _feature_by_name(adapter, "RearBoreChamfer")
    if feature is None:
        raise RuntimeError("rear D entry: native chamfer feature is missing")
    feature = _early_bound(feature, "IFeature")
    definition = feature.GetDefinition()
    if definition is None:
        raise RuntimeError("rear D entry: chamfer definition is missing")
    definition = _early_bound(definition, "IChamferFeatureData2")
    if int(definition.Type) != 1:  # swChamferAngleDistance
        raise RuntimeError("rear D entry: angle-distance leg control did not persist")
    angle = float(definition.EdgeChamferAngle)
    if (
        not math.isfinite(angle)
        or abs(math.degrees(angle) - BORE_ENTRY_BREAK_ANGLE_DEG) > 1e-9
    ):
        raise RuntimeError("rear D entry: source chamfer angle did not persist")
    # GetEdgeChamferDistance documents only side 0 for angle-distance mode.
    # At the authored right-angle face junction, the other physical leg is
    # width*tan(native angle); do not treat undocumented side 1 as a readback.
    width = float(definition.GetEdgeChamferDistance(0)) * 1000.0
    for side, leg in enumerate((width, width * math.tan(angle))):
        if not math.isfinite(leg) or abs(leg - BORE_ENTRY_BREAK) > 1e-6:
            raise RuntimeError(f"rear D entry: leg {side} does not match source")
    dimensions = name_dimensions(adapter, "RearBoreChamfer", ["BoreEntryBreak"])
    _, dimension = _named_dimension(adapter, "RearBoreChamfer", "BoreEntryBreak")
    if dimension is None:
        raise RuntimeError("rear D entry: controlled native size is missing")
    linked_width = float(dimension.SystemValue) * 1000.0
    if not math.isfinite(linked_width) or abs(linked_width - BORE_ENTRY_BREAK) > 1e-6:
        raise RuntimeError("rear D entry: controlled native size does not match source")
    return dimensions


def _flat_limits(adapter) -> None:
    """Model at the real midpoint and print its native accepted limits."""
    display, dimension = _named_dimension(adapter, "BoreProfile", "FlatToAxis")
    if abs(float(dimension.SystemValue) * 1000.0 - FLAT_TO_AXIS) > 1e-6:
        raise RuntimeError("collar native D-flat is not the accepted midpoint")
    tolerance = dimension.Tolerance
    if tolerance is None:
        raise RuntimeError("collar native D-flat has no tolerance object")
    tolerance = _early_bound(tolerance, "IDimensionTolerance")
    tolerance.Type = FLAT_TOL_TYPE
    low, high = (value / 1000.0 for value in sorted(FLAT_BAND))
    if tolerance.SetValues(low, high) is not True:
        raise RuntimeError("collar native D-flat limits were rejected")
    if (
        int(tolerance.Type) != FLAT_TOL_TYPE
        or abs(float(tolerance.GetMinValue()) - low) > 1e-12
        or abs(float(tolerance.GetMaxValue()) - high) > 1e-12
        or abs(FLAT_TO_AXIS + low * 1000.0 - FLAT_LIMITS[0]) > 1e-9
        or abs(FLAT_TO_AXIS + high * 1000.0 - FLAT_LIMITS[1]) > 1e-9
    ):
        raise RuntimeError("collar native D-flat limits did not persist")
    status = display.SetPrecision3(FLAT_PLACES, -1, FLAT_PLACES, -1)
    if int(status) != 0 or int(display.GetPrimaryTolPrecision2()) != FLAT_PLACES:
        raise RuntimeError("collar native D-flat limit precision did not persist")


def _collar_length_reference(adapter) -> None:
    """Save the fitted nominal as REF, never an independent size acceptance."""
    display, dimension = _named_dimension(adapter, "BodyProfile", "CollarLength")
    if abs(float(dimension.SystemValue) * 1000.0 - LENGTH) > 1e-6:
        raise RuntimeError("collar body reference does not match the fitted nominal")
    tolerance = dimension.Tolerance
    if tolerance is None or int(tolerance.Type) != 0:
        raise RuntimeError("collar body has an independent size band")
    display.SetText(1, "(")
    display.SetText(2, ")")
    if (display.GetText(1), display.GetText(2)) != ("(", ")"):
        raise RuntimeError("collar body reference text did not persist")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreatePlaneParameters,
        ExtrusionParameters,
        RevolveParameters,
    )

    check("create_part", await adapter.create_part())
    # The mm suffix is load-bearing: the equation manager reads bare numbers in
    # document units (see build_dt_crankshaft).
    for name, value in (
        ("CollarDia", OD),
        ("CollarLength", LENGTH),
        ("PilotDia", PILOT_DIA),
        ("PilotLength", PILOT_LENGTH),
        ("BoreDia", BORE_DIA),
        ("FlatToAxis", FLAT_TO_AXIS),
        ("BoreEntryBreak", BORE_ENTRY_BREAK),
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

    # --- True D opening through pilot and body --------------------------------
    drive_jobs += await _d_bore(adapter)
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
    for dim in await _rear_bore_chamfer(adapter):
        drive_jobs.append((dim, '"BoreEntryBreak"'))
    volume = await volume_check(
        adapter, "rear D entry relief", volume - V_ENTRY_BREAK, 0.03 * V_ENTRY_BREAK + 0.02
    )

    # --- Datum planes -------------------------------------------------------------
    stations = (
        ("RearFace", LENGTH, '"CollarLength"'),
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
        f"{DRIVE_PIN_COLLAR_RIM_WORST:.2f}, pilot {PILOT_WALL_WORST:.2f}, "
        f"bore to pin hole {BORE_PIN_WALL_WORST:.3f}; pressed pin end "
        f"{PIN_REAR_INSET_WORST:.4f} min inside the rear face"
    )

    # Actual D sizes and both entry legs carry their source-owned controls.
    # Body length is fitted at assembly and remains REF on part and drawing.
    set_dimension_bilateral_tolerance(
        adapter, "BodyProfile", "CollarDia", *deviations(OD_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "BodyProfile", "PilotDia", *deviations(PILOT_DIA_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "BoreProfile", "BoreDia", *deviations(BORE_DIA_BAND)
    )
    _flat_limits(adapter)
    set_dimension_bilateral_tolerance(
        adapter, "RearBoreChamfer", "BoreEntryBreak", *deviations(BORE_ENTRY_BREAK_BAND)
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
    _collar_length_reference(adapter)
    _resolve_faces(
        adapter.currentModel,
        {
            "collar actual rear reaction face": PlanarFace((0.0, 0.0, 1.0), LENGTH, tolerance_mm=1e-5),
            "collar actual D-flat": PlanarFace((0.0, 1.0, 0.0), -FLAT_TO_AXIS, tolerance_mm=1e-5),
        },
    )
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
