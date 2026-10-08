r"""Build the rocker arm's vise blank-end stop (MHA-CH-006-TL-01; shop fixture).

A one-piece 6061-T6 aluminium L in the inventory's fixture frame
(``ch_rocker_arm_tl_vise_stop_spec``): a lug screwed to a Kanetec MB-PM
magnetic base on the vise's fixed jaw, an arm, and a finger at its far end
that carries the bonded hardened nose pin against the blank's raw left end.

Layout: the finger's cross-section (with both drilled holes) is a Right-plane
sketch (sketch x = -Z, y = Y) extruded -X from the seat face (X-40) by the
overall length. A sketch ON the seat face then cuts the waste around the arm
back to the finger's front face, so the overall length and the finger-front
station both measure from the seat face. Last, a Top-plane sketch cuts the
full-width step under the arm from the lug's head-bearing face to the back,
which leaves the screw hole in the lug alone; the step's length and height
are dimensioned from the seat face's bottom corner (a construction line on
the seat face).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_vise_stop.py
"""

from __future__ import annotations

import math
import sys
from typing import Any

from _common import (
    SketchDims,
    _feature_by_name,
    _display_dimensions,
    _dim_value_mm,
    _early_bound,
    _rename_dimensions,
    add_line_chain,
    anchor_point_to_origin,
    anchor_point_to_point,
    apply_material,
    check,
    define_rectilinear_chain,
    dimension_between,
    drive_dimension,
    ensure_fully_defined,
    extrude_at_offset,
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
from _drawing_marks import (
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
)
from _fit_limits import deviations
from _holes import find_planar_face
from _saved_part_guard import require_saved_drawing_properties
from ch_rocker_arm_tl_vise_stop_spec import (
    ARM_HEIGHT,
    ARM_INNER_Y,
    ARM_TOP_Z,
    ARM_WIDTH,
    BACK_X,
    BOTTOM_Z,
    DRAWING_DIMENSIONS,
    DRAWING_MODEL_MM,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    DRILLED_BAND,
    FINGER_END_Y,
    FINGER_FRONT,
    FINGER_HEIGHT,
    FINGER_LENGTH,
    FINGER_THICK,
    FINGER_TOP_Z,
    ISOMETRIC_VIEW_NOTE,
    NOSE_HOLE_DIA,
    NOSE_Y,
    NOSE_Z,
    NOTCH_HEIGHT,
    NOTCH_TOP_Z,
    OVERALL_LENGTH,
    REAR_Y,
    SCREW_GRIP,
    SCREW_HOLE_DIA,
    SCREW_Y,
    SCREW_Z,
    SEAT_X,
)

PART_NAME = "ch-rocker-arm-tl-vise-stop"
MATERIAL = "6061 Alloy"  # the registry row names the 6061-T6 bar
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "Isometric View Note",
)

_A_NOSE = math.pi * (NOSE_HOLE_DIA / 2.0) ** 2
_A_SCREW = math.pi * (SCREW_HOLE_DIA / 2.0) ** 2
V_BLOCK = (FINGER_HEIGHT * FINGER_LENGTH - _A_NOSE - _A_SCREW) * OVERALL_LENGTH
# The waste around the arm holds the nose hole (Y-32.5 is off the arm).
V_WASTE = (FINGER_HEIGHT * FINGER_LENGTH - ARM_WIDTH * ARM_HEIGHT - _A_NOSE) * FINGER_FRONT
V_ARM = V_BLOCK - V_WASTE
# The step takes the arm's lower strip (with the screw hole) back to the
# finger, and the finger's lower strip: the screw hole stays in the lug only.
V_STEP = (ARM_WIDTH * NOTCH_HEIGHT - _A_SCREW) * (FINGER_FRONT - SCREW_GRIP) + (
    FINGER_LENGTH * NOTCH_HEIGHT - _A_SCREW
) * FINGER_THICK
V_TOTAL = V_ARM - V_STEP
# The step's sketch overshoots the open back and bottom faces by this much.
_STEP_OVERSHOOT = 2.0


def _require_one_solid_body(adapter: Any, *, label: str) -> None:
    bodies = tuple(
        _early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ()
    )
    if len(bodies) != 1:
        raise RuntimeError(f"{label}: expected exactly one solid body, found {len(bodies)}")


def _name_dimension_by_value(
    adapter: Any, feature_name: str, value_mm: float, name: str
) -> str:
    """Rename the one display dimension of ``feature_name`` worth ``value_mm``.

    An offset-start extrusion owns its depth and its start offset; the values
    differ, so the depth is picked by value instead of by creation order.
    """
    feature = _feature_by_name(adapter, feature_name)
    matches = [
        dim
        for dim in _display_dimensions(feature, feature_name)
        if abs(_dim_value_mm(dim) - value_mm) < 1e-6
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"{feature_name}: expected one {value_mm:g} mm dimension, found {len(matches)}"
        )
    return _rename_dimensions(matches, feature_name, [name])[0]


async def _hole_circle(
    adapter: Any,
    centre: tuple[float, float],
    corner: str,
    corner_uv: tuple[float, float],
    dia: float,
    label: str,
    *,
    dims: SketchDims,
    names: tuple[str, str, str],
) -> None:
    """A hole circle located from the section's rear-bottom corner.

    Sketch x is -Z and y is Y, so the corner's horizontal distance is the
    height above the bottom face and its vertical distance the run from the
    rear face: the print measures each hole from those two faces.
    """
    sketch_mgr = adapter.currentSketchManager
    prev_add_to_db = bool(sketch_mgr.AddToDB)
    sketch_mgr.AddToDB = True
    try:
        circle = check(f"add_circle {label}", await adapter.add_circle(*centre, dia / 2.0))
    finally:
        sketch_mgr.AddToDB = prev_add_to_db
    await dimension_between(
        adapter,
        f"{circle}.center",
        corner,
        "horizontal_distance",
        abs(corner_uv[0] - centre[0]),
        f"{label} height",
    )
    dims.record(names[0], f'"{names[0]}"')
    await dimension_between(
        adapter,
        f"{circle}.center",
        corner,
        "vertical_distance",
        abs(corner_uv[1] - centre[1]),
        f"{label} from rear",
    )
    dims.record(names[1], f'"{names[1]}"')
    check(
        f"dimension {label} diameter",
        await adapter.add_sketch_dimension(circle, None, "diameter", dia),
    )
    dims.record(names[2], f'"{names[2]}"')


def _active_sketch_map(
    adapter: Any, active: Any, origin_xyz: tuple[float, float, float], axes: tuple[int, int]
) -> tuple[Any, bool]:
    """Map two model axes of the active sketch's plane to sketch (u, v).

    The plane's sketch axes are SolidWorks' choice, so the map is read from
    ``ModelToSketchTransform`` (the transgear-arm end-face precedent) and
    snapped to its exact axis permutation, so axis-parallel model edges stay
    exactly axis-parallel in the sketch. ``axes`` names the in-plane model
    axes (0 X, 1 Y, 2 Z) in the order ``to_uv`` takes them; also returns
    whether the sketch normal points along the remaining model axis's +.
    """
    import pythoncom
    from win32com.client import VARIANT

    sketch = _early_bound(active, "ISketch")
    math_util = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    xform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")

    def to_sketch(model_mm: tuple[float, float, float]) -> tuple[float, ...]:
        point = math_util.CreatePoint(
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [c / 1000.0 for c in model_mm])
        )
        mapped = _early_bound(
            _early_bound(point, "IMathPoint").MultiplyTransform(xform), "IMathPoint"
        )
        return tuple(c * 1000.0 for c in mapped.ArrayData)

    def step(axis: int) -> tuple[float, float, float]:
        point = list(origin_xyz)
        point[axis] += 1.0
        return (point[0], point[1], point[2])

    normal_axis = ({0, 1, 2} - set(axes)).pop()
    origin = to_sketch(origin_xyz)
    if abs(origin[2]) > 1e-4:
        raise RuntimeError(f"sketch plane is {origin[2]:g} mm off {origin_xyz}")
    along = [
        [b - a for a, b in zip(origin, to_sketch(step(axis)), strict=True)] for axis in axes
    ]
    out = to_sketch(step(normal_axis))[2] - origin[2]
    for vector, axis in zip(along, axes, strict=True):
        if any(abs(abs(c) - round(abs(c))) > 1e-6 for c in vector) or abs(vector[2]) > 1e-6:
            raise RuntimeError(f"sketch axes are not a model-axis permutation ({'XYZ'[axis]})")
    if abs(abs(out) - 1.0) > 1e-6:
        raise RuntimeError(f"sketch normal is not along {'XYZ'[normal_axis]} ({out:g})")
    ua, va = round(along[0][0]), round(along[0][1])
    ub, vb = round(along[1][0]), round(along[1][1])
    u0, v0 = round(origin[0], 9), round(origin[1], 9)

    def to_uv(a: float, b: float) -> tuple[float, float]:
        return (u0 + ua * a + ub * b, v0 + va * a + vb * b)

    return to_uv, out > 0.0


def _activate_sketch(adapter: Any, model: Any, label: str) -> Any:
    """Register the just-inserted sketch with the adapter; return it."""
    active = adapter.currentModel.GetActiveSketch2()
    if active is None:
        raise RuntimeError(f"no active sketch on {label}")
    adapter.currentSketchManager = model.SketchManager
    adapter.currentSketch = active
    adapter._sketch_count += 1
    adapter._last_sketch_name = str(active.Name)
    return active


def _open_seat_face_sketch(adapter: Any) -> tuple[Any, bool]:
    """Open a sketch ON the seat face; return a model (Y, Z) -> sketch map
    and whether the sketch normal points OUT of the seat face (+X)."""
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    face = find_planar_face(model, (1.0, 0.0, 0.0), [[SEAT_X, SCREW_Y, BOTTOM_Z + 1.0]])
    model.ClearSelection2(True)
    if not _early_bound(face, "IEntity").Select2(False, 0):
        raise RuntimeError("seat face Select2 failed")
    adapter.currentSketchManager = model.SketchManager
    adapter._reset_sketch_entity_registry()
    model.SketchManager.InsertSketch(True)
    active = _activate_sketch(adapter, model, "the seat face")
    return _active_sketch_map(adapter, active, (SEAT_X, 0.0, 0.0), (1, 2))


def _cut_through_all_both(adapter: Any, sketch_name: str) -> None:
    """Through-All-Both ``FeatureCut4`` on the named sketch (the 27-param
    SW 2026 form, falling back to the 26-param one; the
    build_fr_rocker_arm_support precedent)."""
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    feature_manager = _early_bound(model.FeatureManager, "IFeatureManager")
    model.ClearSelection2(True)
    if not _feature_by_name(adapter, sketch_name).Select2(False, 0):
        raise RuntimeError(f"cannot select sketch {sketch_name!r}")
    through = adapter.constants.get("swEndCondThroughAll", 1)
    args = (
        False,  # Sd: both directions
        False,  # Flip side to cut
        False,  # Dir
        through,
        through,
        0.0,
        0.0,
        False,
        False,
        False,
        False,
        0.0,
        0.0,
        False,
        False,
        False,
        False,
        False,  # NormalCut
        False,  # UseFeatScope
        True,  # UseAutoSelect
        False,
        False,
        False,
        adapter.constants.get("swStartSketchPlane", 0),
        0.0,
        False,
        False,
    )
    feature = adapter._attempt(lambda: feature_manager.FeatureCut4(*args), default=None)
    if not feature:
        feature = adapter._attempt(lambda: feature_manager.FeatureCut4(*args[:-1]), default=None)
    model.ClearSelection2(True)
    if not feature:
        raise RuntimeError(f"FeatureCut4 through-all-both on {sketch_name} failed")


async def _step_cut(adapter: Any) -> list[tuple[str, str]]:
    """Cut the full-width step under the arm, from the lug's head-bearing
    face back past the finger; return its drive jobs.

    Top-plane sketch (model X and Z): a construction line on the seat face's
    edge, anchored to the origin, carries the step's two printed sizes to the
    rectangle's corner on the lug: its length from the seat face (the screw
    grip) and its height above the lug's bottom face.
    """
    check("create_sketch step", await adapter.create_sketch("Top"))
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    active = model.GetActiveSketch2()
    if active is None:
        raise RuntimeError("no active Top-plane sketch for the step")
    to_uv, _normal = _active_sketch_map(adapter, active, (0.0, 0.0, 0.0), (0, 2))
    dims = SketchDims()

    seat_bottom = to_uv(SEAT_X, BOTTOM_Z)
    seat_top = to_uv(SEAT_X, ARM_TOP_Z)
    corner_x, corner_z = SEAT_X - SCREW_GRIP, NOTCH_TOP_Z
    back_x, low_z = BACK_X - _STEP_OVERSHOOT, BOTTOM_Z - _STEP_OVERSHOOT
    outline_xz = [(corner_x, corner_z), (back_x, corner_z), (back_x, low_z), (corner_x, low_z)]
    outline = [to_uv(x, z) for x, z in outline_xz]
    # Direct to the database: no inference snaps the corner onto the finger's
    # section, which crosses this plane.
    set_sketch_direct_db(adapter, True)
    try:
        seat_line = check(
            "add_centerline seat edge", await adapter.add_centerline(*seat_bottom, *seat_top)
        )
        edges = await add_line_chain(adapter, outline)
    finally:
        set_sketch_direct_db(adapter, False)
    check(
        "seat edge vertical" if seat_bottom[0] == seat_top[0] else "seat edge horizontal",
        await adapter.add_sketch_constraint(
            seat_line, None, "vertical" if seat_bottom[0] == seat_top[0] else "horizontal"
        ),
    )
    await anchor_point_to_origin(adapter, f"{seat_line}.start", *seat_bottom, "seat edge anchor")
    for value in seat_bottom:
        if abs(value) > 1e-9:
            dims.record(None)
    await dimension_between(
        adapter,
        f"{seat_line}.start",
        f"{seat_line}.end",
        "vertical_distance" if seat_bottom[0] == seat_top[0] else "horizontal_distance",
        ARM_HEIGHT,
        "seat edge length",
    )
    dims.record(None)

    for index, edge in enumerate(edges):
        (u1, v1), (u2, v2) = outline[index], outline[(index + 1) % 4]
        relation = "horizontal" if v1 == v2 else "vertical"
        if relation == "vertical" and u1 != u2:
            raise RuntimeError("step outline is not axis-parallel in the sketch")
        check(f"step {relation} {edge}", await adapter.add_sketch_constraint(edge, None, relation))
    for index in (0, 1):
        (u1, v1), (u2, v2) = outline[index], outline[index + 1]
        kind = "horizontal_distance" if v1 == v2 else "vertical_distance"
        await dimension_between(
            adapter,
            f"{edges[index]}.start",
            f"{edges[index]}.end",
            kind,
            abs(u2 - u1) if v1 == v2 else abs(v2 - v1),
            f"step side {index}",
        )
        dims.record(None)
    # The corner on the lug, from the seat edge's bottom: the screw grip
    # along X, then the step height along Z.
    grip_uv = (outline[0][0] - seat_bottom[0], outline[0][1] - seat_bottom[1])
    await anchor_point_to_point(
        adapter, f"{seat_line}.start", f"{edges[0]}.start", *grip_uv, "step corner"
    )
    # anchor_point_to_point emits the sketch-horizontal span first.
    sketch_u_is_model_x = to_uv(1.0, 0.0)[0] != to_uv(0.0, 0.0)[0]
    names = ("ScrewGrip", "NotchHeight") if sketch_u_is_model_x else ("NotchHeight", "ScrewGrip")
    for name in names:
        dims.record(name, f'"{name}"')
    await ensure_fully_defined(adapter, "step sketch")
    check("exit_sketch step", await adapter.exit_sketch())
    name_last_feature(adapter, "NotchProfile")
    jobs = dims.apply(adapter, "NotchProfile")
    _cut_through_all_both(adapter, "NotchProfile")
    name_last_feature(adapter, "NotchCut")
    return jobs


async def build(adapter: Any) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # The mm suffix is load-bearing: the equation manager reads bare numbers
    # in document units.
    for name, value in DRAWING_MODEL_MM.items():
        await set_global(adapter, name, f"{value}mm")

    # --- Finger section with both holes (Right plane: sketch x = -Z, y = Y) ---
    block = SketchDims()
    check("create_sketch block section", await adapter.create_sketch("Right"))
    # Rear-bottom corner first: the rear edge (the finger height) and the top
    # edge (the finger length) carry the two driving sizes.
    section = [
        (-BOTTOM_Z, REAR_Y),
        (-FINGER_TOP_Z, REAR_Y),
        (-FINGER_TOP_Z, FINGER_END_Y),
        (-BOTTOM_Z, FINGER_END_Y),
    ]
    edges = await add_line_chain(adapter, section)
    await define_rectilinear_chain(
        adapter,
        edges,
        section,
        anchor=0,
        label="finger section",
        dims=block,
        names=["FingerHeight", "FingerLength"],
        drives=['"FingerHeight"', '"FingerLength"'],
    )
    corner = f"{edges[0]}.start"
    await _hole_circle(
        adapter,
        (-NOSE_Z, NOSE_Y),
        corner,
        section[0],
        NOSE_HOLE_DIA,
        "nose hole",
        dims=block,
        names=("NoseHeight", "NoseFromRear", "NoseHoleDia"),
    )
    await _hole_circle(
        adapter,
        (-SCREW_Z, SCREW_Y),
        corner,
        section[0],
        SCREW_HOLE_DIA,
        "screw hole",
        dims=block,
        names=("ScrewHeight", "ScrewFromRear", "ScrewHoleDia"),
    )
    await ensure_fully_defined(adapter, "finger section sketch")
    check("exit_sketch block section", await adapter.exit_sketch())
    name_last_feature(adapter, "BlockProfile")
    drive_jobs = block.apply(adapter, "BlockProfile")

    # -X from the seat face (X-40) through the overall length.
    extrude_at_offset(adapter, OVERALL_LENGTH, -SEAT_X, flip=True)
    name_last_feature(adapter, "Block")
    drive_jobs.append(
        (_name_dimension_by_value(adapter, "Block", OVERALL_LENGTH, "OverallLength"),
         '"OverallLength"')
    )
    await volume_check(adapter, "drilled block", V_BLOCK, 0.005 * V_BLOCK)
    _require_one_solid_body(adapter, label="block")

    # --- Waste around the arm, cut from the seat face to the finger front ---
    to_uv, normal_out = _open_seat_face_sketch(adapter)
    waste = SketchDims()
    # Start at the finger end's top corner so the two closing edges (arm top
    # to finger top along the rear face, and the top edge) are the ones the
    # chain leaves undimensioned; the arm's height and width are driven.
    outline_yz = [
        (FINGER_END_Y, FINGER_TOP_Z),
        (FINGER_END_Y, BOTTOM_Z),
        (ARM_INNER_Y, BOTTOM_Z),
        (ARM_INNER_Y, ARM_TOP_Z),
        (REAR_Y, ARM_TOP_Z),
        (REAR_Y, FINGER_TOP_Z),
    ]
    outline = [to_uv(y, z) for y, z in outline_yz]
    cut_edges = await add_line_chain(adapter, outline)
    await define_rectilinear_chain(
        adapter,
        cut_edges,
        outline,
        anchor=0,
        label="arm waste",
        dims=waste,
        names=[None, None, "ArmHeight", "ArmWidth"],
        drives=[None, None, '"ArmHeight"', '"ArmWidth"'],
    )
    await ensure_fully_defined(adapter, "arm waste sketch")
    check("exit_sketch arm waste", await adapter.exit_sketch())
    name_last_feature(adapter, "ArmCutProfile")
    drive_jobs += waste.apply(adapter, "ArmCutProfile")
    # A cut runs opposite the sketch normal unless reversed.
    check(
        "cut arm waste",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=FINGER_FRONT, reverse_direction=not normal_out)
        ),
    )
    name_last_feature(adapter, "ArmCut")
    drive_jobs.append(
        (name_dimensions(adapter, "ArmCut", ["FingerFront"])[0], '"FingerFront"')
    )
    await volume_check(adapter, "arm", V_ARM, 0.005 * V_ARM)
    _require_one_solid_body(adapter, label="arm")

    # --- The step under the arm, from the lug's head face to the back -------
    drive_jobs += await _step_cut(adapter)
    await volume_check(adapter, "vise stop", V_TOTAL, 0.005 * V_TOTAL)
    _require_one_solid_body(adapter, label="vise stop")

    await force_rebuild(adapter)
    for dimension_name, expression in drive_jobs:
        await drive_dimension(adapter, dimension_name, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven vise stop (equations neutral)", V_TOTAL, 0.005 * V_TOTAL
    )
    _require_one_solid_body(adapter, label="driven vise stop")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    for dimension in ("NoseHoleDia", "ScrewHoleDia"):
        set_dimension_bilateral_tolerance(
            adapter, "BlockProfile", dimension, *deviations(DRILLED_BAND)
        )
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
