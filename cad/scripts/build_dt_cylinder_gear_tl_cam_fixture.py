r"""Build the cylinder gears' cam turning fixture body (MHA-DT-12-TL-01; shop tooling).

The lathe fixture on which each MHA-DT-12 cylinder gear's eccentric cam is
turned (``dt_cylinder_gear_tl_cam_fixture_spec``, issue #2361).

Layout (the spec's model frame): the body is a Front-plane circle about the
origin (the register axis) extruded +Z by the thickness, so the back face
sits on Z0 and the front face, which seats the gear, is Z = thickness. The
stub's press ream is a Front-plane circle on -Y at the throw, cut through
mid-plane. The clock pin's press ream is a circle on a plane offset to the
front face, cut blind into the body (the default cut direction from an
offset plane, build_dt_cone_tip_block's slit); its sketch coordinates go
through ``_sketch_mapper`` (build_dt_cone_gear_tl_index_plate's), which
proves the offset plane keeps model X and Y along its sketch axes.

Run only through the supervised farm launcher:
``part:dt_cylinder_gear_tl_cam_fixture``.
"""

from __future__ import annotations

import math
import sys
from collections.abc import Callable
from typing import Any

import _telemetry
from _appearance import apply_material
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _document_units import apply_package_model_units
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import apply_drawing_precision
from _drawing_tolerances import set_dimension_bilateral_tolerance
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from _sketch import SketchDims, ensure_fully_defined
from _sketch_circle import define_circle
from _visibility import blank_reference_geometry
from dt_cylinder_gear_tl_cam_fixture_spec import (
    BODY_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    GLOBALS,
    ISOMETRIC_VIEW_NOTE,
    MODEL_BANDS_MM,
    PIN_HOLE_DEPTH,
    PIN_HOLE_DIA,
    PIN_X,
    PIN_Y,
    STUB_HOLE_DIA,
    STUB_OFFSET,
    THICKNESS,
    UNIT,
)

PART_NAME = "dt-cylinder-gear-tl-cam-fixture"
MATERIAL = "Plain Carbon Steel"  # see _appearance.apply_material docstring
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Isometric View Note",
)

# Mid-plane cut from the back face: past both faces whatever the thickness.
THROUGH_CUT_DEPTH = 2.0 * THICKNESS
FRONT_FACE_PLANE = "FrontFacePlane"

V_BODY = math.pi / 4.0 * BODY_DIA**2 * THICKNESS
V_STUB_HOLE = math.pi / 4.0 * STUB_HOLE_DIA**2 * THICKNESS
V_PIN_HOLE = math.pi / 4.0 * PIN_HOLE_DIA**2 * PIN_HOLE_DEPTH
V_FINISHED = V_BODY - V_STUB_HOLE - V_PIN_HOLE


def _require_one_solid_body(adapter: Any, *, label: str) -> None:
    bodies = tuple(
        _early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ()
    )
    if len(bodies) != 1:
        raise RuntimeError(
            f"{label}: expected exactly one solid body, found {len(bodies)}"
        )


def _sketch_mapper(
    adapter: Any, *, u_axis: int, v_axis: int, label: str
) -> Callable[[tuple[float, float, float]], tuple[float, float]]:
    """Map model points (mm) into the ACTIVE sketch, requiring model axis
    ``u_axis`` along the sketch's u and ``v_axis`` along its v (either sign);
    build_dt_cone_gear_tl_index_plate's mapper, copied as it copied the
    riser's. Coordinates are rounded to the nanometre."""
    import pythoncom
    from win32com.client import VARIANT

    active = adapter.currentModel.GetActiveSketch2()
    if active is None:
        raise RuntimeError(f"{label}: no active sketch")
    sketch = _early_bound(active, "ISketch")
    math_util = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    xform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")

    def raw(model_mm: tuple[float, float, float]) -> tuple[float, ...]:
        point = math_util.CreatePoint(
            VARIANT(
                pythoncom.VT_ARRAY | pythoncom.VT_R8, [c / 1000.0 for c in model_mm]
            )
        )
        mapped = _early_bound(
            _early_bound(point, "IMathPoint").MultiplyTransform(xform), "IMathPoint"
        )
        return tuple(c * 1000.0 for c in mapped.ArrayData)

    base = raw((0.0, 0.0, 0.0))
    for axis, want in ((u_axis, 0), (v_axis, 1)):
        unit = [0.0, 0.0, 0.0]
        unit[axis] = 1.0
        moved = raw(tuple(unit))
        delta = [m - b for m, b in zip(moved, base, strict=True)]
        if abs(abs(delta[want]) - 1.0) > 1e-6:
            raise RuntimeError(
                f"{label}: model axis {axis} maps to sketch {delta!r}, not along "
                f"sketch {'uv'[want]}"
            )

    def to_sketch(model_mm: tuple[float, float, float]) -> tuple[float, float]:
        u, v, w = raw(model_mm)
        if abs(w) > 1e-4:
            raise RuntimeError(f"{label}: {model_mm} is {w:g} mm off the sketch")
        u, v = round(u, 9), round(v, 9)
        return (0.0 if abs(u) < 1e-9 else u, 0.0 if abs(v) < 1e-9 else v)

    return to_sketch


@_telemetry.traced("part.cam_fixture_pin_hole")
async def _pin_hole(adapter: Any) -> list[tuple[str, str]]:
    """The clock pin's press ream: a circle on the front-face plane at
    (PIN_X, PIN_Y), cut blind into the body."""
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check(
        f"create_plane {FRONT_FACE_PLANE}",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Front Plane", offset=THICKNESS
            )
        ),
    )
    name_last_feature(adapter, FRONT_FACE_PLANE)
    jobs = [
        (
            name_dimensions(adapter, FRONT_FACE_PLANE, ["FrontFaceOffset"])[0],
            '"BodyThick"',
        )
    ]
    blank_reference_geometry(adapter, ((FRONT_FACE_PLANE, "PLANE"),))
    dims = SketchDims()
    check("create_sketch pin hole", await adapter.create_sketch(FRONT_FACE_PLANE))
    to_sketch = _sketch_mapper(adapter, u_axis=0, v_axis=1, label="pin hole")
    if to_sketch((0.0, 0.0, THICKNESS)) != (0.0, 0.0):
        raise RuntimeError("pin hole: the register axis is not the sketch origin")
    centre = to_sketch((PIN_X, PIN_Y, THICKNESS))
    await define_circle(
        adapter,
        *centre,
        PIN_HOLE_DIA / 2.0,
        "clock pin hole",
        dims=dims,
        names=("PinX", "PinY", "PinHoleDia"),
        drives=('"PinX"', '"PinY"', '"PinHoleDia"'),
    )
    await ensure_fully_defined(adapter, "pin hole sketch")
    check("exit_sketch pin hole", await adapter.exit_sketch())
    name_last_feature(adapter, "PinHoleProfile")
    jobs += dims.apply(adapter, "PinHoleProfile")
    check(
        "cut pin hole",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=PIN_HOLE_DEPTH)),
    )
    name_last_feature(adapter, "PinHole")
    jobs.append(
        (name_dimensions(adapter, "PinHole", ["PinHoleDepth"])[0], '"PinHoleDepth"')
    )
    return jobs


async def build(adapter: Any) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)
    # The mm suffix is load-bearing: the equation manager reads bare numbers
    # in document units, and this is an inch document.
    for name, value in GLOBALS.items():
        await set_global(adapter, name, f"{value}mm")

    # --- Body: the register about the origin, extruded +Z ---------------------
    body = SketchDims()
    check("create_sketch body", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        BODY_DIA / 2.0,
        "register",
        dims=body,
        names=(None, None, "BodyDia"),
        drives=(None, None, '"BodyDia"'),
    )
    await ensure_fully_defined(adapter, "body profile")
    check("exit_sketch body", await adapter.exit_sketch())
    name_last_feature(adapter, "BodyProfile")
    drive_jobs = body.apply(adapter, "BodyProfile")
    check(
        "extrude body",
        await adapter.create_extrusion(ExtrusionParameters(depth=THICKNESS)),
    )
    name_last_feature(adapter, "Body")
    drive_jobs.append(
        (name_dimensions(adapter, "Body", ["BodyThick"])[0], '"BodyThick"')
    )
    volume = await volume_check(adapter, "body", V_BODY, 0.002 * V_BODY)

    # --- Stub press ream: on -Y at the throw, through ---------------------------
    stub = SketchDims()
    check("create_sketch stub hole", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        -STUB_OFFSET,
        STUB_HOLE_DIA / 2.0,
        "stub hole",
        dims=stub,
        names=(None, "StubOffset", "StubHoleDia"),
        drives=(None, '"StubOffset"', '"StubHoleDia"'),
    )
    await ensure_fully_defined(adapter, "stub hole sketch")
    check("exit_sketch stub hole", await adapter.exit_sketch())
    name_last_feature(adapter, "StubHoleProfile")
    drive_jobs += stub.apply(adapter, "StubHoleProfile")
    check(
        "cut stub hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "StubHole")
    volume = await volume_check(
        adapter, "stub hole", volume - V_STUB_HOLE, 0.01 * V_STUB_HOLE
    )

    # --- Clock pin press ream: blind from the front face -------------------------
    drive_jobs += await _pin_hole(adapter)
    volume = await volume_check(
        adapter, "clock pin hole", volume - V_PIN_HOLE, 0.05 * V_PIN_HOLE + 0.05
    )
    _require_one_solid_body(adapter, label="cam fixture")

    await force_rebuild(adapter)
    for dimension_name, expression in drive_jobs:
        await drive_dimension(adapter, dimension_name, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven cam fixture (equations neutral)", V_FINISHED, 0.002 * V_BODY
    )
    _require_one_solid_body(adapter, label="driven cam fixture")

    # The hole stations carry their +/-.0005 from the register axis and the
    # press reams their +.0005/0; each callout names its pin (spec).
    for (feature_name, dimension_name), deviations in MODEL_BANDS_MM.items():
        set_dimension_bilateral_tolerance(
            adapter,
            feature_name,
            dimension_name,
            *deviations,
            places=DRAWING_PRECISION[feature_name][dimension_name],
            display_unit=UNIT,
        )
    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter, PART_NAME, {"Isometric View Note": ISOMETRIC_VIEW_NOTE}
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
