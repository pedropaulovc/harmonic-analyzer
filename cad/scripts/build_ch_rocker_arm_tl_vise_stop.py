r"""Build the rocker arm's vise blank-end stop (MHA-CH-006-TL-01; shop fixture).

A one-piece 1018 steel L in the inventory's fixture frame
(``ch_rocker_arm_tl_vise_stop_spec``): an arm screwed to a magnetic base on
the vise's fixed jaw, and a finger at its far end that carries the bonded
hardened nose pin against the blank's raw left end.

Layout: the finger's cross-section (with both drilled holes) is a Right-plane
sketch (sketch x = -Z, y = Y) extruded -X from the seat face (X-30) by the
overall length, so both holes run the full block. A sketch ON the seat face
then cuts the waste around the arm back to the finger's front face, so the
overall length and the finger-front station both measure from the seat face.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_vise_stop.py
"""

from __future__ import annotations

import math
import sys
from typing import Any

from _common import (
    SketchDims,
    _display_dimensions,
    _dim_value_mm,
    _early_bound,
    _feature_by_name,
    _rename_dimensions,
    add_line_chain,
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
    BOTTOM_Z,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    DRILLED_BAND,
    FINGER_END_Y,
    FINGER_FRONT,
    FINGER_HEIGHT,
    FINGER_LENGTH,
    FINGER_TOP_Z,
    ISOMETRIC_VIEW_NOTE,
    NOSE_FROM_REAR,
    NOSE_HEIGHT,
    NOSE_HOLE_DIA,
    NOSE_Y,
    NOSE_Z,
    OVERALL_LENGTH,
    REAR_Y,
    SCREW_FROM_REAR,
    SCREW_HEIGHT,
    SCREW_HOLE_DIA,
    SCREW_Y,
    SCREW_Z,
    SEAT_X,
)

PART_NAME = "ch-rocker-arm-tl-vise-stop"
MATERIAL = "Plain Carbon Steel"  # AISI 1018 bar
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
V_TOTAL = V_BLOCK - V_WASTE


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


def _open_seat_face_sketch(adapter: Any) -> tuple[Any, bool]:
    """Open a sketch ON the seat face; return a model (Y, Z) -> sketch map.

    The face's sketch axes are SolidWorks' choice, so the map is read from
    ``ModelToSketchTransform`` (the transgear-arm end-face precedent) and
    snapped to its exact axis permutation, so axis-parallel model edges stay
    exactly axis-parallel in the sketch. Also returns whether the sketch
    normal points OUT of the seat face (+X).
    """
    import pythoncom
    from win32com.client import VARIANT

    model = _early_bound(adapter.currentModel, "IModelDoc2")
    face = find_planar_face(model, (1.0, 0.0, 0.0), [[SEAT_X, SCREW_Y, BOTTOM_Z + 1.0]])
    model.ClearSelection2(True)
    if not _early_bound(face, "IEntity").Select2(False, 0):
        raise RuntimeError("seat face Select2 failed")
    adapter.currentSketchManager = model.SketchManager
    adapter._reset_sketch_entity_registry()
    model.SketchManager.InsertSketch(True)
    active = adapter.currentModel.GetActiveSketch2()
    if active is None:
        raise RuntimeError("no active sketch on the seat face")
    adapter.currentSketch = active
    adapter._sketch_count += 1
    adapter._last_sketch_name = str(active.Name)
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

    origin = to_sketch((SEAT_X, 0.0, 0.0))
    if abs(origin[2]) > 1e-4:
        raise RuntimeError(f"seat-face sketch plane is {origin[2]:g} mm off X{SEAT_X:g}")
    along_y = [b - a for a, b in zip(origin, to_sketch((SEAT_X, 1.0, 0.0)), strict=True)]
    along_z = [b - a for a, b in zip(origin, to_sketch((SEAT_X, 0.0, 1.0)), strict=True)]
    out = to_sketch((SEAT_X + 1.0, 0.0, 0.0))[2] - origin[2]
    for vector, label in ((along_y, "Y"), (along_z, "Z")):
        if any(abs(abs(c) - round(abs(c))) > 1e-6 for c in vector) or abs(vector[2]) > 1e-6:
            raise RuntimeError(f"seat-face sketch axes are not a model-axis permutation ({label})")
    if abs(abs(out) - 1.0) > 1e-6:
        raise RuntimeError(f"seat-face sketch normal is not along X ({out:g})")
    uy, vy = round(along_y[0]), round(along_y[1])
    uz, vz = round(along_z[0]), round(along_z[1])
    u0, v0 = round(origin[0], 9), round(origin[1], 9)

    def to_uv(y: float, z: float) -> tuple[float, float]:
        return (u0 + uy * y + uz * z, v0 + vy * y + vz * z)

    return to_uv, out > 0.0


async def build(adapter: Any) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # The mm suffix is load-bearing: the equation manager reads bare numbers
    # in document units.
    for name, value in (
        ("FingerHeight", FINGER_HEIGHT),
        ("FingerLength", FINGER_LENGTH),
        ("NoseHeight", NOSE_HEIGHT),
        ("NoseFromRear", NOSE_FROM_REAR),
        ("NoseHoleDia", NOSE_HOLE_DIA),
        ("ScrewHeight", SCREW_HEIGHT),
        ("ScrewFromRear", SCREW_FROM_REAR),
        ("ScrewHoleDia", SCREW_HOLE_DIA),
        ("OverallLength", OVERALL_LENGTH),
        ("FingerFront", FINGER_FRONT),
        ("ArmHeight", ARM_HEIGHT),
        ("ArmWidth", ARM_WIDTH),
    ):
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

    # -X from the seat face (X-30) through the overall length.
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
