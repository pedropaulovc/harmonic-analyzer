r"""Reproduction script: transgear arm (MHA-PD-018; ch. 23; 1 used).

The steel link of the paper-drive hanger: it swings on the MHA-VN-041 shoulder
screw at the pivot P, carries the disc cluster's MHA-PD-023 pin at S, the
MHA-PD-019 plate on two #8-32 taps between them, and the MHA-VN-042 latch pin in
its square end (``transgear_arm_geometry``; the sheet's contract is
``transgear_arm_spec``).

Layout (part frame of ``transgear_arm_geometry``: origin on P at the FRONT
face, +X to the square end, +Z to the rear face):

* ``ArmOutline`` (Front plane): the R12.5 pivot round, the two straight edges
  tangent to it, cut square at the tip station by the 14-wide end face;
  extruded ``THICKNESS`` toward +Z as ``Arm``.
* ``PivotBore``: the Ø4.9 running bore through at P.
* ``PinBore``: the Ø3.874 reamed press bore through at S for the MHA-PD-023
  pin, cut normal to the faces (the pin's head seats on the rear face).
* ``PlateTaps``: native Hole Wizard taps through from the rear face, their
  mouths countersunk (``PlateTapCountersinks``).
* ``SpotFace``: the rear spot face, a revolved cut whose profile (Top plane,
  the arm's centreline section) dimensions its floor from the FRONT face.
* ``PinHole``: the blind, flat-floored latch-pin hole (reamed for the dowel's
  press, which bottoms on the floor), sketched on the square end face.
* ``StationReference`` (blanked): the printed stations of the pin bore and
  the plate taps from P; the Hole Wizard placement sketches that drive the
  taps are not importable.

Datums (all blanked): ``Axis1`` pivot, ``Axis2`` pin, ``Axis3``/``Axis4``
plate taps, ``Axis5`` latch pin; planes ``RearFace`` (z = THICKNESS),
``PivotHeadSeat`` (the spot-face floor, the pivot head's seat) and ``EndFace``
(x = TIP_STATION).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pd_transgear_arm.py
"""

from __future__ import annotations

import math
import sys
from typing import Any

import _telemetry
from _common import (
    POLISHED_STEEL,
    SketchDims,
    _early_bound,
    add_line_chain,
    anchor_point_to_origin,
    apply_color,
    apply_material,
    blank_sketch,
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
    add_diametric_linear_dimension,
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _fit_limits import deviations
from _hole_spec import blind_cut_dia_mm
from _holes import find_planar_face, wizard_holes
from _saved_part_guard import require_saved_drawing_properties
from _visibility import blank_reference_geometry
from pd_transgear_arm_geometry import (
    EDGE_LEAN,
    END_HALF_WIDTH,
    PIN_BORE_DIA,
    PIN_BORE_DIA_BAND,
    PIN_HOLE_DEPTH,
    PIN_HOLE_DIA,
    PIN_HOLE_DIA_BAND,
    PIN_HOLE_Z,
    PIN_STATION,
    PIVOT_BORE_DIA,
    PIVOT_END_R,
    PIVOT_TANGENT_X,
    PIVOT_TANGENT_Y,
    PLATE_TAP_SPEC,
    PLATE_TAP_STATIONS,
    PLATE_TAP_CSK_DIA,
    SPOT_FACE_DEPTH,
    SPOT_FACE_DIA,
    SPOT_FACE_FLOOR_FROM_FRONT,
    THICKNESS,
    TIP_STATION,
)
from pd_transgear_arm_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    HOLE_POSITION_TOLERANCE,
    ISOMETRIC_VIEW_NOTE,
    SPOT_FACE_DIA_BAND,
    SPOT_FACE_FLOOR_TOLERANCE,
)

PART_NAME = "pd-transgear-arm"
MATERIAL = "Plain Carbon Steel"  # AISI 1018; see _common.apply_material
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Isometric View Note",
)

THROUGH_CUT_DEPTH = 4.0 * THICKNESS  # mid-plane total; > the arm's thickness
# The spot-face profile runs this far past the rear face so the revolved cut
# clears it (not printed).
SPOT_FACE_OVERRUN = SPOT_FACE_DEPTH

_R_BORE = PIVOT_BORE_DIA / 2.0
_R_SPOT = SPOT_FACE_DIA / 2.0
_R_PIN = PIN_HOLE_DIA / 2.0
_R_PIN_BORE = PIN_BORE_DIA / 2.0
_R_PLATE = blind_cut_dia_mm(PLATE_TAP_SPEC) / 2.0
# 90-degree countersinks: one 45-degree chamfer leg on each plate-tap drill
# mouth.
PLATE_CSK = PLATE_TAP_CSK_DIA / 2.0 - _R_PLATE


def _outline_area() -> float:
    """The pivot round's sector (π + 2λ) plus the polygon P, lower tangent
    point, lower end corner, upper end corner, upper tangent point."""
    sector = 0.5 * PIVOT_END_R**2 * (math.pi + 2.0 * EDGE_LEAN)
    polygon = (
        (0.0, 0.0),
        (PIVOT_TANGENT_X, -PIVOT_TANGENT_Y),
        (TIP_STATION, -END_HALF_WIDTH),
        (TIP_STATION, END_HALF_WIDTH),
        (PIVOT_TANGENT_X, PIVOT_TANGENT_Y),
    )
    shoelace = sum(
        x0 * y1 - x1 * y0
        for (x0, y0), (x1, y1) in zip(polygon, polygon[1:] + polygon[:1], strict=True)
    )
    return sector + 0.5 * shoelace


def _csk_volume(csk: float, r: float) -> float:
    """One 45-degree countersink ring on a drill of radius ``r``."""
    return math.pi * csk**2 * (r + csk / 3.0)


V_ARM = _outline_area() * THICKNESS
V_BORE = math.pi * _R_BORE**2 * THICKNESS
V_PIN_BORE = math.pi * _R_PIN_BORE**2 * THICKNESS
V_PLATE = len(PLATE_TAP_STATIONS) * math.pi * _R_PLATE**2 * THICKNESS
V_PLATE_CSK = 2.0 * len(PLATE_TAP_STATIONS) * _csk_volume(PLATE_CSK, _R_PLATE)
V_SPOT = math.pi * (_R_SPOT**2 - _R_BORE**2) * SPOT_FACE_DEPTH
V_PIN = math.pi * _R_PIN**2 * PIN_HOLE_DEPTH


async def _mass(adapter: Any) -> tuple[float, list[float]]:
    res = await adapter.get_mass_properties()
    if not res.is_success:
        raise RuntimeError(f"arm mass properties failed: {res.error}")
    return float(res.data.volume), [float(c) for c in res.data.center_of_mass]


def _as_construction(adapter: Any, entity_id: str) -> None:
    """Flag a registered sketch line as construction geometry (the flag is
    ISketchSegment's, not the derived ISketchLine's)."""
    segment = _early_bound(adapter._sketch_entities[entity_id], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity_id} did not take the construction flag")


def _open_end_face_sketch(adapter: Any) -> tuple[float, float, bool]:
    """Open a sketch ON the square end face; map the pin-hole centre into it.

    A sketch on a reference plane coincident with the face would display the
    blind depth from the blanked plane; a face sketch anchors it on the real
    end-face edge (the pinion-bracket pin-seat precedent).  The face's sketch
    axes are SolidWorks' choice, so the centre maps through
    ``ModelToSketchTransform``.  Returns the sketch ``(u, v)`` and whether the
    sketch normal points OUT of the end face (+X).
    """
    import pythoncom
    from win32com.client import VARIANT

    model = _early_bound(adapter.currentModel, "IModelDoc2")
    centre = (TIP_STATION, 0.0, PIN_HOLE_Z)
    face = find_planar_face(model, (1.0, 0.0, 0.0), [list(centre)])
    model.ClearSelection2(True)
    if not _early_bound(face, "IEntity").Select2(False, 0):
        raise RuntimeError("latch-pin hole: end face Select2 failed")
    adapter.currentSketchManager = model.SketchManager
    adapter._reset_sketch_entity_registry()
    model.SketchManager.InsertSketch(True)
    active = adapter.currentModel.GetActiveSketch2()
    if active is None:
        raise RuntimeError("latch-pin hole: no active sketch on the end face")
    adapter.currentSketch = active
    adapter._sketch_count += 1
    adapter._last_sketch_name = str(active.Name)
    sketch = _early_bound(active, "ISketch")
    math_util = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    xform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")

    def to_sketch(model_mm: tuple[float, float, float]) -> tuple[float, ...]:
        point = math_util.CreatePoint(
            VARIANT(
                pythoncom.VT_ARRAY | pythoncom.VT_R8, [c / 1000.0 for c in model_mm]
            )
        )
        mapped = _early_bound(
            _early_bound(point, "IMathPoint").MultiplyTransform(xform), "IMathPoint"
        )
        return tuple(c * 1000.0 for c in mapped.ArrayData)

    u, v, w = to_sketch(centre)
    if abs(w) > 1e-4:
        raise RuntimeError(f"latch-pin hole centre is {w:g} mm off the end-face sketch")
    w_out = to_sketch((TIP_STATION + 1.0, 0.0, PIN_HOLE_Z))[2]
    if abs(abs(w_out) - 1.0) > 1e-4:
        raise RuntimeError(f"end-face sketch normal is not along X (w {w_out:g})")
    return u, v, w_out > 0.0


async def build(adapter: Any) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreatePlaneParameters,
        ExtrusionParameters,
        RevolveParameters,
    )

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations).  The mm suffix is load-bearing: this
    # is an INCH document and the equation manager reads bare numbers in
    # document units.
    for name, value in (
        ("ArmThickness", THICKNESS),
        ("PivotEndR", PIVOT_END_R),
        ("TipStation", TIP_STATION),
        ("EndWidth", 2.0 * END_HALF_WIDTH),
        ("PivotBoreDia", PIVOT_BORE_DIA),
        ("PinBoreDia", PIN_BORE_DIA),
        ("SpotFaceDia", SPOT_FACE_DIA),
        ("SpotFaceFloor", SPOT_FACE_FLOOR_FROM_FRONT),
        ("PinStation", PIN_STATION),
        ("PlateTapStation1", PLATE_TAP_STATIONS[0]),
        ("PlateTapStation2", PLATE_TAP_STATIONS[1]),
        ("PinHoleDia", PIN_HOLE_DIA),
        ("PinHoleDepth", PIN_HOLE_DEPTH),
        ("PinHoleZ", PIN_HOLE_Z),
    ):
        await set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []

    # --- Outline: R12.5 about P, tangent edges, square 14-wide end ----------
    # Equal tangent lengths from the two end corners put them symmetric about
    # the centreline; the end width, the tip station and the pivot radius
    # then fix the lean the geometry module derives from the r7 round.
    outline = SketchDims()
    check("create_sketch arm outline", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    tx, ty = PIVOT_TANGENT_X, PIVOT_TANGENT_Y
    upper = check(
        "upper edge", await adapter.add_line(TIP_STATION, END_HALF_WIDTH, tx, ty)
    )
    pivot_round = check("pivot round", await adapter.add_arc(0.0, 0.0, tx, ty, tx, -ty))
    lower = check(
        "lower edge", await adapter.add_line(tx, -ty, TIP_STATION, -END_HALF_WIDTH)
    )
    end_face = check(
        "square end",
        await adapter.add_line(
            TIP_STATION, -END_HALF_WIDTH, TIP_STATION, END_HALF_WIDTH
        ),
    )
    set_sketch_direct_db(adapter, False)
    await anchor_point_to_origin(
        adapter, f"{pivot_round}.center", 0.0, 0.0, "pivot round centre"
    )
    for label, e1, e2, relation in (
        ("upper edge tangent", upper, pivot_round, "tangent"),
        ("lower edge tangent", pivot_round, lower, "tangent"),
        ("edges symmetric", upper, lower, "equal"),
    ):
        check(label, await adapter.add_sketch_constraint(e1, e2, relation))
    check(
        "square end vertical",
        await adapter.add_sketch_constraint(end_face, None, "vertical"),
    )
    check(
        "pivot radius",
        await adapter.add_sketch_dimension(pivot_round, None, "radial", PIVOT_END_R),
    )
    outline.record("PivotEndR", '"PivotEndR"')
    await dimension_between(
        adapter,
        f"{pivot_round}.center",
        f"{end_face}.start",
        "horizontal_distance",
        TIP_STATION,
        "tip station",
    )
    outline.record("TipStation", '"TipStation"')
    check(
        "end width",
        await adapter.add_sketch_dimension(
            end_face, None, "linear", 2.0 * END_HALF_WIDTH
        ),
    )
    outline.record("EndWidth", '"EndWidth"')
    await ensure_fully_defined(adapter, "arm outline")
    check("exit_sketch arm outline", await adapter.exit_sketch())
    name_last_feature(adapter, "ArmOutline")
    drive_jobs += outline.apply(adapter, "ArmOutline")
    check(
        "extrude arm",
        await adapter.create_extrusion(ExtrusionParameters(depth=THICKNESS)),
    )
    name_last_feature(adapter, "Arm")
    drive_jobs += [(name_dimensions(adapter, "Arm", ["Depth"])[0], '"ArmThickness"')]
    expected = V_ARM
    await volume_check(adapter, "arm blank", expected, 0.002 * expected)
    _, com = await _mass(adapter)
    if abs(com[2] - THICKNESS / 2.0) > 0.01:
        raise RuntimeError(
            f"arm blank centre of mass z = {com[2]:.3f}, expected "
            f"{THICKNESS / 2.0:.3f}: the extrusion must run toward +Z"
        )

    # --- Pivot bore through at P ---------------------------------------------
    bore = SketchDims()
    check("create_sketch pivot bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        _R_BORE,
        "pivot bore",
        dims=bore,
        names=(None, None, "PivotBoreDia"),
        drives=(None, None, '"PivotBoreDia"'),
    )
    await ensure_fully_defined(adapter, "pivot bore sketch")
    check("exit_sketch pivot bore", await adapter.exit_sketch())
    name_last_feature(adapter, "PivotBoreProfile")
    drive_jobs += bore.apply(adapter, "PivotBoreProfile")
    check(
        "cut pivot bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "PivotBore")
    expected -= V_BORE
    await volume_check(adapter, "arm with pivot bore", expected, 0.01 * V_BORE)

    # --- Pin bore through at S: the MHA-PD-023 press, reamed square to the faces
    pin_bore = SketchDims()
    check("create_sketch pin bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        PIN_STATION,
        0.0,
        _R_PIN_BORE,
        "pin bore",
        dims=pin_bore,
        names=("PinBoreX", None, "PinBoreDia"),
        drives=('"PinStation"', None, '"PinBoreDia"'),
    )
    await ensure_fully_defined(adapter, "pin bore sketch")
    check("exit_sketch pin bore", await adapter.exit_sketch())
    name_last_feature(adapter, "PinBoreProfile")
    drive_jobs += pin_bore.apply(adapter, "PinBoreProfile")
    check(
        "cut pin bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "PinBore")
    expected -= V_PIN_BORE
    await volume_check(adapter, "arm with pin bore", expected, 0.01 * V_PIN_BORE)

    # --- Plate taps through from the rear face, their mouths countersunk ----
    plate = wizard_holes(
        adapter,
        PLATE_TAP_SPEC,
        [[x, 0.0, THICKNESS] for x in PLATE_TAP_STATIONS],
        (0.0, 0.0, 1.0),
        f"plate taps ({PLATE_TAP_SPEC.size} through)",
        name="PlateTaps",
        expect_dia_mm=2.0 * _R_PLATE,
        placement_dims=[
            (("PlateTapX1", '"PlateTapStation1"'), (None, None)),
            (("PlateTapX2", '"PlateTapStation2"'), (None, None)),
        ],
    )
    drive_jobs += plate.placement_drive_jobs
    expected -= V_PLATE
    await volume_check(adapter, "arm with plate taps", expected, 0.03 * V_PLATE)
    check(
        "countersink plate-tap mouths",
        await adapter.add_chamfer(
            PLATE_CSK,
            [
                [x + _R_PLATE, 0.0, z_face]
                for x in PLATE_TAP_STATIONS
                for z_face in (0.0, THICKNESS)
            ],
        ),
    )
    name_last_feature(adapter, "PlateTapCountersinks")
    expected -= V_PLATE_CSK
    await volume_check(
        adapter, "plate-tap countersinks", expected, 0.03 * V_PLATE_CSK + 0.05
    )

    # --- Rear spot face: revolved in the centreline section so its floor is
    # dimensioned from the FRONT face (the pivot end play, contract §13).
    # Top-plane sketch v is model -Z.
    spot = SketchDims()
    check("create_sketch spot face", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    spot_axis = check(
        "spot face axis",
        await adapter.add_centerline(0.0, 0.0, 0.0, -SPOT_FACE_FLOOR_FROM_FRONT),
    )
    top = -(THICKNESS + SPOT_FACE_OVERRUN)
    points = [
        (0.0, -SPOT_FACE_FLOOR_FROM_FRONT),
        (_R_SPOT, -SPOT_FACE_FLOOR_FROM_FRONT),
        (_R_SPOT, top),
        (0.0, top),
    ]
    spot_lines = await add_line_chain(adapter, points)
    set_sketch_direct_db(adapter, False)
    for index, line in enumerate(spot_lines):
        relation = "horizontal" if index % 2 == 0 else "vertical"
        check(
            f"spot face profile {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    check(
        "spot face axis vertical",
        await adapter.add_sketch_constraint(spot_axis, None, "vertical"),
    )
    await anchor_point_to_origin(
        adapter, f"{spot_axis}.start", 0.0, 0.0, "spot face axis on P"
    )
    await add_diametric_linear_dimension(
        adapter, spot_axis, spot_lines[1], (_R_SPOT, top - 4.0), "SpotFaceDia"
    )
    spot.record("SpotFaceDia", '"SpotFaceDia"')
    await dimension_between(
        adapter,
        f"{spot_axis}.start",
        f"{spot_lines[0]}.end",
        "vertical_distance",
        SPOT_FACE_FLOOR_FROM_FRONT,
        "spot-face floor from the front face",
    )
    spot.record("FloorDepth", '"SpotFaceFloor"')
    # The profile's height past the floor only has to clear the rear face;
    # it is not printed.
    check(
        "spot face profile height",
        await adapter.add_sketch_dimension(
            spot_lines[1],
            None,
            "linear",
            THICKNESS + SPOT_FACE_OVERRUN - SPOT_FACE_FLOOR_FROM_FRONT,
        ),
    )
    spot.record("SpotFaceHeight")
    await ensure_fully_defined(adapter, "spot face profile")
    check("exit_sketch spot face", await adapter.exit_sketch())
    name_last_feature(adapter, "SpotFaceProfile")
    drive_jobs += spot.apply(adapter, "SpotFaceProfile")
    check(
        "revolve-cut spot face",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
    )
    name_last_feature(adapter, "SpotFace")
    expected -= V_SPOT
    await volume_check(adapter, "arm with rear spot face", expected, 0.02 * V_SPOT)

    # --- Latch-pin hole: blind along -X from the square end face -------------
    # A plain cut-extrude, so the floor is flat: the dowel is pressed onto it
    # (a wizard drill point would leave a cone under the pressed end).
    before, com_before = await _mass(adapter)
    pin = SketchDims()
    u, v, normal_out = _open_end_face_sketch(adapter)
    # The face's sketch axes carry model z on one axis and y (= 0) on the
    # other; the one nonzero centre offset is the pin height from the front.
    if abs(abs(u) - PIN_HOLE_Z) < 1e-4 and abs(v) < 1e-4:
        v = 0.0
    elif abs(abs(v) - PIN_HOLE_Z) < 1e-4 and abs(u) < 1e-4:
        u = 0.0
    else:
        raise RuntimeError(
            f"pin-hole centre mapped to unexpected sketch ({u:g}, {v:g})"
        )
    await define_circle(
        adapter,
        u,
        v,
        _R_PIN,
        "latch-pin hole",
        dims=pin,
        names=("PinHoleZ", "PinHoleZ", "PinHoleDia"),
        drives=('"PinHoleZ"', '"PinHoleZ"', '"PinHoleDia"'),
    )
    await ensure_fully_defined(adapter, "latch-pin hole sketch")
    check("exit_sketch latch-pin hole", await adapter.exit_sketch())
    name_last_feature(adapter, "PinHoleProfile")
    drive_jobs += pin.apply(adapter, "PinHoleProfile")
    # A cut runs opposite the sketch normal unless reversed.
    check(
        "cut latch-pin hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=PIN_HOLE_DEPTH, reverse_direction=not normal_out)
        ),
    )
    name_last_feature(adapter, "PinHole")
    drive_jobs += [
        (name_dimensions(adapter, "PinHole", ["PinHoleDepth"])[0], '"PinHoleDepth"')
    ]
    expected -= V_PIN
    after, com_after = await _mass(adapter)
    if abs((before - after) - V_PIN) > 0.02 * V_PIN:
        raise RuntimeError(
            f"latch-pin hole removed {before - after:.2f} mm^3, expected "
            f"{V_PIN:.2f}: circle misplaced or cut the wrong way"
        )
    # Material removed at the +X end moves the centre of mass toward -X.
    if com_after[0] >= com_before[0]:
        raise RuntimeError(
            f"latch-pin hole missed the square end (COM x {com_before[0]:.4f} -> "
            f"{com_after[0]:.4f})"
        )
    _telemetry.success(
        f"latch-pin hole (end-face sketch {u:+g}, {v:+g}) removed "
        f"{before - after:.2f} mm^3 (analytic {V_PIN:.2f})"
    )

    # --- REFERENCE sketch: the printed hole stations from P ------------------
    stations = SketchDims()
    check("create_sketch station reference", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    references = (
        ("PinStation", PIN_STATION),
        ("PlateTapStation1", PLATE_TAP_STATIONS[0]),
        ("PlateTapStation2", PLATE_TAP_STATIONS[1]),
    )
    reference_lines = [
        check(f"{name} reference line", await adapter.add_line(0.0, 0.0, x, 0.0))
        for name, x in references
    ]
    set_sketch_direct_db(adapter, False)
    for line, (name, _) in zip(reference_lines, references, strict=True):
        _as_construction(adapter, line)
        check(
            f"{name} reference horizontal",
            await adapter.add_sketch_constraint(line, None, "horizontal"),
        )
        check(
            f"{name} reference starts on P",
            await adapter.add_sketch_constraint(
                f"{line}.start", "origin", "coincident"
            ),
        )
    # Dimensions in creation order; SketchDims renames them by that order.
    for line, (name, x) in zip(reference_lines, references, strict=True):
        await dimension_between(
            adapter,
            f"{line}.start",
            f"{line}.end",
            "horizontal_distance",
            x,
            f"{name} reference",
        )
        stations.record(name, f'"{name}"')
    await ensure_fully_defined(adapter, "station reference sketch")
    check("exit_sketch station reference", await adapter.exit_sketch())
    name_last_feature(adapter, "StationReference")
    drive_jobs += stations.apply(adapter, "StationReference")

    # --- Named datums for the assembly mates ---------------------------------
    for label, plane_b, offset_b, drive_b, want in (
        ("pivot axis", "Right Plane", 0.0, None, "Axis1"),
        ("pin axis", "Right Plane", PIN_STATION, '"PinStation"', "Axis2"),
        (
            "plate tap 1 axis",
            "Right Plane",
            PLATE_TAP_STATIONS[0],
            '"PlateTapStation1"',
            "Axis3",
        ),
        (
            "plate tap 2 axis",
            "Right Plane",
            PLATE_TAP_STATIONS[1],
            '"PlateTapStation2"',
            "Axis4",
        ),
        ("latch-pin axis", "Front Plane", PIN_HOLE_Z, '"PinHoleZ"', "Axis5"),
    ):
        axis = await name_bore_axis(
            adapter,
            "Top Plane",
            0.0,
            plane_b,
            offset_b,
            label,
            drive_b=drive_b,
            drive_jobs=drive_jobs,
        )
        if axis != want:
            raise RuntimeError(f"{label} came back {axis!r}, not {want}")
    for plane, base, offset, drive in (
        ("RearFace", "Front Plane", THICKNESS, '"ArmThickness"'),
        ("PivotHeadSeat", "Front Plane", SPOT_FACE_FLOOR_FROM_FRONT, '"SpotFaceFloor"'),
        ("EndFace", "Right Plane", TIP_STATION, '"TipStation"'),
    ):
        check(
            f"create_plane {plane}",
            await adapter.create_plane(
                CreatePlaneParameters(mode="offset", base_plane=base, offset=offset)
            ),
        )
        name_last_feature(adapter, plane)
        drive_jobs.append(
            (name_dimensions(adapter, plane, [f"{plane}Offset"])[0], drive)
        )
    blank_reference_geometry(
        adapter,
        (("RearFace", "PLANE"), ("PivotHeadSeat", "PLANE"), ("EndFace", "PLANE")),
    )

    # Deferred drive equations; each evaluates to the value just built.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven arm (equations neutral)", expected, 0.001 * expected
    )

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    # Explicit bands (contract §3.1 / §12); every other printed dimension is
    # governed by its places (the spec's DRAWING_PRECISION).
    set_dimension_bilateral_tolerance(
        adapter, "SpotFaceProfile", "SpotFaceDia", *deviations(SPOT_FACE_DIA_BAND)
    )
    set_dimension_symmetric_tolerance(
        adapter, "SpotFaceProfile", "FloorDepth", SPOT_FACE_FLOOR_TOLERANCE
    )
    set_dimension_symmetric_tolerance(
        adapter, "StationReference", "PinStation", HOLE_POSITION_TOLERANCE
    )
    set_dimension_symmetric_tolerance(
        adapter, "StationReference", "PlateTapStation1", HOLE_POSITION_TOLERANCE
    )
    set_dimension_symmetric_tolerance(
        adapter, "StationReference", "PlateTapStation2", HOLE_POSITION_TOLERANCE
    )
    set_dimension_symmetric_tolerance(
        adapter, "PinHoleProfile", "PinHoleZ", HOLE_POSITION_TOLERANCE
    )
    set_dimension_bilateral_tolerance(
        adapter, "PinHoleProfile", "PinHoleDia", *deviations(PIN_HOLE_DIA_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "PinBoreProfile", "PinBoreDia", *deviations(PIN_BORE_DIA_BAND)
    )
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter, PART_NAME, {"Isometric View Note": ISOMETRIC_VIEW_NOTE}
    )
    # The reference sketch owns printed dimensions but no geometry: hidden in
    # the part; the drawing shows it per view (_drawing_hidden_sketches).
    blank_sketch(adapter, "StationReference")
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
