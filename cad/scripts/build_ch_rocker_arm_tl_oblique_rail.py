r"""Purchased HIWIN HGR15R linear rail, cut to 440 (MHA-CH-006-TL-30).

The oblique trammel jig's two rails (vendor-checked against HIWIN's own
HGR15R440C STEP; ``ch_rocker_arm_tl_oblique_rail_spec`` records every source):
the end-face ``SECTION`` on the Right plane extruded 440 along +X, then the
seven Ø4.5 holes through and their Ø7.5 counterbores down from the top.

Frame: origin at the -X end face, on the seat (bottom) face, on the rail
centreline; +X along the rail, +Z up. The Right plane's sketch reads model
(-Z, Y); the profile maps through the sketch's own transform, so only that
orientation is assumed, and it is checked.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_oblique_rail.py
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Any

import _config
import _telemetry
from _appearance import POLISHED_STEEL, apply_color, apply_material
from _check import check
from _com import _early_bound
from _custom_properties import apply_custom_properties
from _drawing_marks import apply_drawing_properties
from _feature_tree import name_last_feature
from _part_checks import bbox_extent_check, report_mass_properties, volume_check
from _part_save import save_part_and_images
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from _sketch import add_line_chain, ensure_fully_defined, set_sketch_direct_db
from _sketch_chains import define_polygon_chain
from _sketch_circle import define_circle
from _visibility import blank_reference_geometry
from ch_rocker_arm_tl_oblique_rail_spec import (
    CBORE_DEPTH,
    CBORE_DIA,
    CENTROID,
    DRAWING_NOTES,
    HEIGHT,
    HOLE_DIA,
    HOLE_X,
    LENGTH,
    MATERIAL,
    SECTION,
    SECTION_CENTROID_Z,
    V_CBORES,
    V_HOLES,
    V_PRISM,
    VOLUME_MM3,
    VOLUME_TOL_MM3,
    WIDTH,
)

PART_NAME = "ch-rocker-arm-tl-oblique-rail"
_PART = _config.parts(PART_NAME)
STOCK_PROPERTIES = {
    "Stock Name": str(_PART["stock_name"]),
    "Supplier": str(_PART["supplier"]),
    "Supplier SKUs": ", ".join(str(sku) for sku in _PART["supplier_skus"]),
}
THROUGH_CUT_DEPTH = 2.0 * HEIGHT
# The through cut runs the rail's full height; the counterbores then remove
# only their annulus around the hole (the spec's V_HOLES stops at the floor).
V_FULL_HOLES = V_HOLES * HEIGHT / (HEIGHT - CBORE_DEPTH)
V_CBORE_ANNULI = V_CBORES - (V_FULL_HOLES - V_HOLES)


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
    ``u_axis`` along the sketch's u and ``v_axis`` along its v (either sign).

    The pivot block's mapper (build_ch_rocker_arm_tl_oblique_pivot_block):
    points go through ``ModelToSketchTransform`` so only the orientation is
    assumed, and it is checked here.
    """
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


async def _centroid_check(
    adapter: Any, label: str, expected: tuple[float, float, float], tol: float
) -> None:
    """Fail if the solid grew to the wrong side of a sketch plane."""
    mass = await adapter.get_mass_properties()
    if not mass.is_success:
        raise RuntimeError(f"{label}: get_mass_properties failed: {mass.error}")
    com = tuple(float(c) for c in mass.data.center_of_mass[:3])
    if any(abs(c - e) > tol for c, e in zip(com, expected, strict=True)):
        raise RuntimeError(
            f"{label}: centre of mass {com!r} mm, expected {expected!r} +/- {tol}"
        )
    _telemetry.success(f"{label}: centre of mass {com!r} mm")


async def _hole_circles(
    adapter: Any, plane: str, z: float, dia: float, label: str
) -> None:
    """One circle per rail hole station, on ``plane`` at model height ``z``."""
    check(f"create_sketch {label}", await adapter.create_sketch(plane))
    to_sketch = _sketch_mapper(adapter, u_axis=0, v_axis=1, label=label)
    for index, x in enumerate(HOLE_X, start=1):
        await define_circle(
            adapter, *to_sketch((x, 0.0, z)), dia / 2.0, f"{label} {index}"
        )
    await ensure_fully_defined(adapter, label)
    check(f"exit_sketch {label}", await adapter.exit_sketch())


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check("create_part", await adapter.create_part())

    # --- Rail: the end-face section on the Right plane, extruded +X ------------
    check("create_sketch rail section", await adapter.create_sketch("Right"))
    to_right = _sketch_mapper(adapter, u_axis=2, v_axis=1, label="rail section")
    points = [to_right((0.0, y, z)) for y, z in SECTION]
    # Off the inference engine: the groove chords and blend chords are short.
    set_sketch_direct_db(adapter, True)
    lines = await add_line_chain(adapter, points)
    set_sketch_direct_db(adapter, False)
    await define_polygon_chain(adapter, lines, points, label="rail section")
    await ensure_fully_defined(adapter, "rail section")
    check("exit_sketch rail section", await adapter.exit_sketch())
    name_last_feature(adapter, "RailSection")
    check(
        "extrude rail",
        await adapter.create_extrusion(ExtrusionParameters(depth=LENGTH)),
    )
    name_last_feature(adapter, "Rail")
    volume = await volume_check(adapter, "rail prism", V_PRISM, 5e-4 * V_PRISM)
    # The prism's centroid catches a profile mapped to the wrong side of an
    # axis or extruded the wrong way along X.
    await _centroid_check(
        adapter, "rail prism", (LENGTH / 2.0, 0.0, SECTION_CENTROID_Z), 0.01
    )

    # --- Holes: Ø4.5 through, from the seat face both ways ---------------------
    await _hole_circles(adapter, "Front", 0.0, HOLE_DIA, "bolt hole")
    name_last_feature(adapter, "BoltHoleProfile")
    check(
        "cut bolt holes",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "BoltHoles")
    volume = await volume_check(
        adapter, "bolt holes", volume - V_FULL_HOLES, 0.01 * V_FULL_HOLES
    )

    # --- Counterbores: Ø7.5, down from the top face ------------------------------
    check(
        "create_plane RailTop",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Front Plane", offset=HEIGHT
            )
        ),
    )
    name_last_feature(adapter, "RailTop")
    blank_reference_geometry(adapter, (("RailTop", "PLANE"),))
    await _hole_circles(adapter, "RailTop", HEIGHT, CBORE_DIA, "counterbore")
    name_last_feature(adapter, "CounterboreProfile")
    # A cut on a plane runs against its normal by default: down from RailTop.
    check(
        "cut counterbores",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=CBORE_DEPTH)),
    )
    name_last_feature(adapter, "Counterbores")
    await volume_check(
        adapter, "counterbores", volume - V_CBORE_ANNULI, 0.01 * V_CBORE_ANNULI
    )

    await volume_check(adapter, "rail", VOLUME_MM3, VOLUME_TOL_MM3)
    await _centroid_check(adapter, "rail", CENTROID, 0.01)
    await bbox_extent_check(adapter, "rail length", "x", LENGTH)
    await bbox_extent_check(adapter, "rail width", "y", WIDTH)
    await bbox_extent_check(adapter, "rail height", "z", HEIGHT)
    _require_one_solid_body(adapter, label="rail")

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    apply_custom_properties(adapter, STOCK_PROPERTIES)
    apply_drawing_properties(adapter, PART_NAME, {"Manufacturing Notes": DRAWING_NOTES})
    await report_mass_properties(adapter)
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(
        adapter,
        (
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Stock Name",
            "Supplier",
            "Supplier SKUs",
            "Manufacturing Notes",
        ),
    )
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
