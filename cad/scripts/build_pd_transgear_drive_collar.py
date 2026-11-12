r"""Build MHA-PD-22, the transgear drive collar (contract §1.2, round 10).

A brass collar with a plain round bore on the integral knob's solid D-core;
the MHA-PD-VN-70 pin pressed into its blind ream is the drive flat (#2409).
Its rear face reacts on the actual gear front F; the body is supplied long
and faced at assembly.  The pilot seats the thumbnut while the removable
T24 floats 0.05..0.15 under it.  Both dimensions and fitted acceptance live
in ``pd_transgear_drive_collar_spec``.

Layout: axis local +Z (machine +Z, rearward), origin on the front (seat)
face, the Front Plane; the body runs z 0..LENGTH, the pilot in front of it.

* ``Axis1``: the bore axis (Top Plane x Right Plane), made first so the
  assembly mates always find it by that name.
* ``Body``: the turned Ø17.5 body and Ø10 pilot.
* ``Bore``: the round reamed bore through both.
* ``PinHoles``: the two drive-pin holes on local ±Y, cut from ``RearFace``
  through the body.
* ``FlatPinHole``: the flat pin's blind ream on local -Y, a revolve cut
  sketched in the Right plane (the section plane) from its floor station
  behind the front face out through the rear face; its size, centre and
  floor station are that sketch's dimensions.
* ``RearBreak``: the rear bore mouth's 45° break, a revolve cut about the
  bore axis whose radial leg prints on section A-A; at assembly it cuts the
  pressed pin's crest corner with it.

Datums: ``RearFace`` (z LENGTH), ``PilotFront`` (z -PILOT_LENGTH),
``DrivePinAxis1`` (+Y), ``DrivePinAxis2`` (-Y) and ``FlatPinAxis`` (the
flat pin's), all hidden.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pd_transgear_drive_collar.py
"""

from __future__ import annotations

import math
import sys

import _telemetry
from _appearance import apply_material
from _bore_axis import name_bore_axis
from _check import check
from _dimensions import drive_dimension, name_dimensions, set_global
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
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
from _sketch_circle import define_circle
from _drawing_dimension_insert import add_diametric_linear_dimension
from _drawing_precision import _named_dimension, apply_drawing_precision
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_tolerances import (
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _document_units import apply_package_model_units
from _fit_deviations import deviations
from _part_properties import part_drawing_unit
from _gtol_planar import PlanarFace
from _gtol_face_resolve import resolve_faces
from _visibility import blank_reference_geometry
from pd_transgear_drive_collar_spec import (
    BORE_DIA,
    BORE_DIA_BAND,
    BORE_PIN_WALL_WORST,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    DRIVE_PIN_COLLAR_RIM_WORST,
    FLAT_PIN_CENTRE,
    FLAT_PIN_CENTRE_TOL,
    FLAT_PIN_FLOOR,
    FLAT_PIN_HOLE_BAND,
    FLAT_PIN_HOLE_DIA,
    FLAT_PIN_SHOULDER_WALL_WORST,
    FLAT_PIN_WEB_WORST,
    ISOMETRIC_VIEW_NOTE,
    LENGTH,
    OD,
    OD_BAND,
    PILOT_DIA,
    PILOT_LENGTH,
    PILOT_WALL_WORST,
    PIN_CIRCLE_RADIUS,
    PIN_HOLE_BAND,
    PIN_HOLE_DEPTH,
    PIN_HOLE_DIA,
    PIN_OFFSET_TOL,
    PIN_REAR_INSET_WORST,
    REAR_BREAK,
    REAR_BREAK_TOL,
    UNIT,
    circle_overlap_area,
    cone_cylinder_volume,
)

PART_NAME = "pd-transgear-drive-collar"
MATERIAL = "Brass"  # C36000 free-machining brass (the registry row names it)

OD_R = OD / 2.0
PILOT_R = PILOT_DIA / 2.0
BORE_R = BORE_DIA / 2.0
PIN_HOLE_R = PIN_HOLE_DIA / 2.0
FLAT_PIN_HOLE_R = FLAT_PIN_HOLE_DIA / 2.0
# How far the through cuts run past the part into air.
_OVERRUN = 1.0


V_COLLAR = math.pi * OD_R**2 * LENGTH
V_PILOT = math.pi * PILOT_R**2 * PILOT_LENGTH
V_BORE = math.pi * BORE_R**2 * (LENGTH + PILOT_LENGTH)
V_PIN_HOLES = 2.0 * math.pi * PIN_HOLE_R**2 * PIN_HOLE_DEPTH
# The flat-pin hole breaks into the bore: only its part outside the bore,
# from the floor station to the rear face, is new metal removed.
V_FLAT_PIN_HOLE = (
    math.pi * FLAT_PIN_HOLE_R**2
    - circle_overlap_area(BORE_R, FLAT_PIN_HOLE_R, FLAT_PIN_CENTRE)
) * (LENGTH - FLAT_PIN_FLOOR)
# The rear break's ring of brass between the bore and its cone, less the part
# of that ring the flat-pin hole has already opened.
_BREAK_FACE_R = BORE_R + REAR_BREAK
V_REAR_BREAK = (
    math.pi * ((_BREAK_FACE_R**3 - BORE_R**3) / 3.0 - BORE_R**2 * REAR_BREAK)
    - cone_cylinder_volume(_BREAK_FACE_R, REAR_BREAK, FLAT_PIN_HOLE_R, FLAT_PIN_CENTRE)
    + circle_overlap_area(BORE_R, FLAT_PIN_HOLE_R, FLAT_PIN_CENTRE) * REAR_BREAK
)
V_TOTAL = V_COLLAR + V_PILOT - V_BORE - V_PIN_HOLES - V_FLAT_PIN_HOLE - V_REAR_BREAK


async def _round_bore(adapter) -> list[tuple[str, str]]:
    """The plain round bore's circle on the seat face, centred on the axis."""
    bore = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        BORE_R,
        "collar bore",
        dims=bore,
        names=(None, None, "BoreDia"),
        drives=(None, None, '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    return bore.apply(adapter, "BoreProfile")


async def _flat_pin_hole(adapter) -> list[tuple[str, str]]:
    """The flat pin's blind ream, the body profile's way: in the Right sketch
    (u, v) = (-Z, Y), a rectangle beside the hole's centreline at
    v = -FLAT_PIN_CENTRE, from the floor station u = -FLAT_PIN_FLOOR out past
    the rear face, revolved about that line.  Its diameter, centre and floor
    station are the sketch's dimensions, so they print on section A-A."""
    hole = SketchDims()
    centre, floor = -FLAT_PIN_CENTRE, -FLAT_PIN_FLOOR
    far = -(LENGTH + _OVERRUN)
    rim_v = centre - FLAT_PIN_HOLE_R
    check("create_sketch flat-pin hole", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "flat-pin hole centreline", await adapter.add_centerline(floor, centre, far, centre)
    )
    points = [(floor, centre), (floor, rim_v), (far, rim_v), (far, centre)]
    lines = await add_line_chain(adapter, points)
    set_sketch_direct_db(adapter, False)
    for index, line in enumerate(lines):
        (_, v0), (_, v1) = points[index], points[(index + 1) % len(lines)]
        relation = "horizontal" if v0 == v1 else "vertical"
        check(
            f"flat-pin hole {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    floor_edge, rim, _far_end, _on_axis = lines
    await dimension_between(
        adapter, f"{floor_edge}.start", "origin", "vertical_distance",
        FLAT_PIN_CENTRE, "flat-pin hole centre from the bore axis",
    )
    hole.record("FlatPinCentre", '"FlatPinCentre"')
    await dimension_between(
        adapter, f"{floor_edge}.start", "origin", "horizontal_distance",
        FLAT_PIN_FLOOR, "flat-pin hole floor from the seat face",
    )
    hole.record("FlatPinFloor", '"FlatPinFloor"')
    await add_diametric_linear_dimension(
        adapter, axis, rim, ((floor + far) / 2.0, rim_v - 2.0), "FlatPinDia"
    )
    hole.record("FlatPinDia", '"FlatPinHoleDia"')
    await dimension_between(
        adapter, f"{rim}.start", f"{rim}.end", "horizontal_distance",
        LENGTH + _OVERRUN - FLAT_PIN_FLOOR, "flat-pin hole run past the rear face",
    )
    hole.record("FlatPinRun")
    await ensure_fully_defined(adapter, "flat-pin hole sketch")
    check("exit_sketch flat-pin hole", await adapter.exit_sketch())
    name_last_feature(adapter, "FlatPinProfile")
    return hole.apply(adapter, "FlatPinProfile")


async def _rear_break(adapter) -> list[tuple[str, str]]:
    """The rear bore mouth's 45° break, build_pd_transgear_arm's pin-mouth
    profile in the Right sketch (u, v) = (-Z, Y): it spans the bore's empty
    middle from the axis, the leg's depth in from the rear face, out past the
    face; only the mouth's ring is brass.  On the collar the same cone also
    cuts the pressed pin's crest corner (its faced configuration carries it)."""
    mouth = SketchDims()
    floor_u = -(LENGTH - REAR_BREAK)
    rim_v = BORE_R + REAR_BREAK
    beyond = -(LENGTH + _OVERRUN)
    profile = [(floor_u, 0.0), (floor_u, BORE_R), (-LENGTH, rim_v), (beyond, rim_v), (beyond, 0.0)]
    check("create_sketch rear break", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "rear break axis", await adapter.add_centerline(beyond, 0.0, beyond - _OVERRUN, 0.0)
    )
    floor, leg, rim, top, axis_side = await add_line_chain(adapter, profile)
    set_sketch_direct_db(adapter, False)
    for line, relation in (
        (floor, "vertical"),
        (rim, "horizontal"),
        (top, "vertical"),
        (axis_side, "horizontal"),
        (axis, "horizontal"),
    ):
        check(
            f"rear break {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    check(
        "rear break axis on the profile",
        await adapter.add_sketch_constraint(f"{axis}.start", f"{axis_side}.start", "coincident"),
    )
    check(
        "rear break on the bore axis",
        await adapter.add_sketch_constraint(f"{axis_side}.start", "origin", "horizontal_points"),
    )
    check(
        "rear break axis length",
        await adapter.add_sketch_dimension(axis, None, "linear", _OVERRUN),
    )
    mouth.record("RearBreakAxisLength")
    await dimension_between(
        adapter, "origin", f"{rim}.start", "horizontal_distance", LENGTH,
        "rear break on the rear face",
    )
    mouth.record("RearBreakSeat", '"CollarLength"')
    await dimension_between(
        adapter, f"{rim}.start", f"{rim}.end", "horizontal_distance", _OVERRUN,
        "rear break overrun",
    )
    mouth.record("RearBreakOverrun")
    check(
        "rear break bore radius",
        await adapter.add_sketch_dimension(floor, None, "linear", BORE_R),
    )
    mouth.record("RearBreakBoreR", '"BoreDia" / 2')
    # The printed leg, across the rear face (section A-A shows it at the +Y
    # mouth); the equal leg along the bore holds the 45 degrees.
    await dimension_between(
        adapter, f"{leg}.start", f"{leg}.end", "vertical_distance", REAR_BREAK,
        "rear break leg on the rear face",
    )
    mouth.record("RearBreak", '"RearBreak"')
    await dimension_between(
        adapter, f"{leg}.start", f"{leg}.end", "horizontal_distance", REAR_BREAK,
        "rear break leg along the bore",
    )
    mouth.record("RearBreakDepth", '"RearBreak"')
    await ensure_fully_defined(adapter, "rear break profile")
    check("exit_sketch rear break", await adapter.exit_sketch())
    name_last_feature(adapter, "RearBreakProfile")
    return mouth.apply(adapter, "RearBreakProfile")


def _fitted_length_reference(adapter, name: str, nominal: float) -> None:
    """Save a fitted nominal as REF, never an independent size acceptance."""
    display, dimension = _named_dimension(adapter, "BodyProfile", name)
    if abs(float(dimension.SystemValue) * 1000.0 - nominal) > 1e-6:
        raise RuntimeError(f"collar {name} reference does not match the fitted nominal")
    tolerance = dimension.Tolerance
    if tolerance is None or int(tolerance.Type) != 0:
        raise RuntimeError(f"collar {name} has an independent size band")
    display.SetText(1, "(")
    display.SetText(2, ")")
    if (display.GetText(1), display.GetText(2)) != ("(", ")"):
        raise RuntimeError(f"collar {name} reference text did not persist")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreatePlaneParameters,
        ExtrusionParameters,
        RevolveParameters,
    )

    check("create_part", await adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)
    # The mm suffix is load-bearing: the equation manager reads bare numbers in
    # document units (see build_dt_crankshaft).
    for name, value in (
        ("CollarDia", OD),
        ("CollarLength", LENGTH),
        ("PilotDia", PILOT_DIA),
        ("PilotLength", PILOT_LENGTH),
        ("BoreDia", BORE_DIA),
        ("PinCircleRadius", PIN_CIRCLE_RADIUS),
        ("PinHoleDia", PIN_HOLE_DIA),
        ("FlatPinCentre", FLAT_PIN_CENTRE),
        ("FlatPinFloor", FLAT_PIN_FLOOR),
        ("FlatPinHoleDia", FLAT_PIN_HOLE_DIA),
        ("RearBreak", REAR_BREAK),
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
    # drawing-guidelines.md rule 11 (turned parts read like the lathe)).  The seat face is u = 0; the body runs to the rear face at
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

    # --- Round bore through pilot and body ------------------------------------
    drive_jobs += await _round_bore(adapter)
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

    # --- The flat pin's blind ream on local -Y --------------------------------
    # After the drive-pin holes and their axes, so every earlier feature and
    # datum the assembly mates keeps its name.
    drive_jobs += await _flat_pin_hole(adapter)
    check(
        "revolve-cut flat-pin hole",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
    )
    name_last_feature(adapter, "FlatPinHole")
    volume = await volume_check(
        adapter, "flat-pin hole", volume - V_FLAT_PIN_HOLE, 0.05 * V_FLAT_PIN_HOLE
    )
    await name_bore_axis(
        adapter,
        "Right Plane",
        0.0,
        "Top Plane",
        -FLAT_PIN_CENTRE,
        "FlatPinAxis",
        drive_b='"FlatPinCentre"',
        drive_jobs=drive_jobs,
    )
    name_last_feature(adapter, "FlatPinAxis")

    # --- The rear bore mouth's break, after the flat-pin hole it crosses ------
    drive_jobs += await _rear_break(adapter)
    check(
        "revolve-cut rear break",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
    )
    name_last_feature(adapter, "RearBreak")
    volume = await volume_check(
        adapter, "rear break", volume - V_REAR_BREAK, 0.05 * V_REAR_BREAK + 0.02
    )

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
        f"bore to pin hole {BORE_PIN_WALL_WORST:.3f}, flat-pin hole to drive-pin "
        f"hole {FLAT_PIN_WEB_WORST:.3f}, flat-pin floor to pilot shoulder "
        f"{FLAT_PIN_SHOULDER_WALL_WORST:.3f}; pressed pin end "
        f"{PIN_REAR_INSET_WORST:.4f} min inside the rear face"
    )

    # The bore and both hole patterns carry their source-owned controls.
    # Body and pilot lengths are fitted at assembly and remain REF on part
    # and drawing; the flat pin's floor station takes the title block's row.
    set_dimension_bilateral_tolerance(
        adapter, "BodyProfile", "CollarDia", *deviations(OD_BAND), display_unit=UNIT
    )
    set_dimension_bilateral_tolerance(
        adapter, "BoreProfile", "BoreDia", *deviations(BORE_DIA_BAND), display_unit=UNIT
    )
    set_dimension_bilateral_tolerance(
        adapter, "PinHoleProfile", "PinPosDia", *deviations(PIN_HOLE_BAND), display_unit=UNIT
    )
    set_dimension_symmetric_tolerance(
        adapter, "PinHoleProfile", "PinPosY", PIN_OFFSET_TOL, display_unit=UNIT
    )
    set_dimension_symmetric_tolerance(
        adapter, "PinHoleProfile", "PinNegY", PIN_OFFSET_TOL, display_unit=UNIT
    )
    set_dimension_bilateral_tolerance(
        adapter, "FlatPinProfile", "FlatPinDia", *deviations(FLAT_PIN_HOLE_BAND),
        display_unit=UNIT,
    )
    set_dimension_symmetric_tolerance(
        adapter, "FlatPinProfile", "FlatPinCentre", FLAT_PIN_CENTRE_TOL, display_unit=UNIT
    )
    set_dimension_symmetric_tolerance(
        adapter, "RearBreakProfile", "RearBreak", REAR_BREAK_TOL, display_unit=UNIT
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    _fitted_length_reference(adapter, "CollarLength", LENGTH)
    _fitted_length_reference(adapter, "PilotLength", PILOT_LENGTH)
    resolve_faces(
        adapter.currentModel,
        {
            "collar actual rear reaction face": PlanarFace((0.0, 0.0, 1.0), LENGTH, tolerance_mm=1e-5),
            "collar flat-pin hole floor": PlanarFace(
                (0.0, 0.0, 1.0), FLAT_PIN_FLOOR, tolerance_mm=1e-5
            ),
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
