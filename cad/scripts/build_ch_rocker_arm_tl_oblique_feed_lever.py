r"""Build the oblique-trammel jig's feed lever (MHA-CH-06-TL-26; shop fixture).

A 6061-T6 1/2 x 1 in flat, 11.8 long, bolted on the carrier plate's top by two
5/16-18 SHCS into the carrier's lever stations; the grip end's plan corners are
broken (``ch_rocker_arm_tl_oblique_feed_lever_spec``).

Layout (the spec's model frame, +Y up): the lever is a Top-plane rectangle
(sketch v along model -Z) extruded +Y by the stock thickness; the two bolt
holes are one native 5/16 clearance Hole Wizard feature from the top face;
the two grip-end vertical edges are
filleted last, the printed radius on its own one-edge feature
(build_pd_guide_lock: an imported fillet dimension attaches to its feature's
first edge), the other corner driven by the same global. The stock thickness
the front view prints lives on a hidden Front-plane reference sketch,
``LeverThickReference`` (a drawing view cannot attach the extrusion's depth).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_oblique_feed_lever.py
"""

from __future__ import annotations

import math
import sys
from collections.abc import Callable
from typing import Any

from _appearance import apply_material
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _document_units import apply_package_model_units
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    blank_sketch,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_chains import define_rectilinear_chain
from _drawing_precision import apply_drawing_precision
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _holes import wizard_holes
from _saved_part_guard import require_saved_drawing_properties
from ch_rocker_arm_tl_oblique_feed_lever_spec import (
    CORNER_R,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    CLEARANCE_SPEC,
    HOLE_DIA,
    HOLE_X,
    HOLE_Y,
    ISOMETRIC_VIEW_NOTE,
    LEVER_LENGTH,
    LEVER_THICK,
    LEVER_WIDTH,
)

PART_NAME = "ch-rocker-arm-tl-oblique-feed-lever"
MATERIAL = "6061 Alloy"  # the registry row names the 6061-T6 flat bar
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Isometric View Note",
)

_R_HOLE = HOLE_DIA / 2.0

V_LEVER = LEVER_LENGTH * LEVER_WIDTH * LEVER_THICK
V_HOLES = len(HOLE_X) * math.pi * _R_HOLE**2 * LEVER_THICK
# Each fillet gives up the square R x R less its quarter disc.
V_CORNER = (CORNER_R**2 - math.pi * CORNER_R**2 / 4.0) * LEVER_THICK


def _require_one_solid_body(adapter, *, label: str) -> None:
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

    build_ch_rocker_arm_tl_trammel_pivot_plate's mapper: the points go
    through ``ModelToSketchTransform`` so only the orientation is assumed,
    and it is checked here.
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


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # The mm suffix is load-bearing: the equation manager reads bare numbers
    # in document units.
    for name, value in (
        ("LeverLength", LEVER_LENGTH),
        ("LeverWidth", LEVER_WIDTH),
        ("LeverThick", LEVER_THICK),
        ("LeverHoleX1", HOLE_X[0]),
        ("LeverHoleX2", HOLE_X[1]),
        ("LeverHoleY", HOLE_Y),
        ("GripCornerR", CORNER_R),
    ):
        await set_global(adapter, name, f"{value}mm")

    # --- Lever: Top-plane rectangle from the origin, extruded +Y ------------
    lever = SketchDims()
    check("create_sketch lever", await adapter.create_sketch("Top"))
    to_top = _sketch_mapper(adapter, u_axis=0, v_axis=2, label="lever profile")
    points = [
        to_top((0.0, 0.0, 0.0)),
        to_top((LEVER_LENGTH, 0.0, 0.0)),
        to_top((LEVER_LENGTH, 0.0, -LEVER_WIDTH)),
        to_top((0.0, 0.0, -LEVER_WIDTH)),
    ]
    lines = await add_line_chain(adapter, points)
    await define_rectilinear_chain(
        adapter,
        lines,
        points,
        label="lever profile",
        dims=lever,
        names=["LeverLength", "LeverWidth"],
        drives=['"LeverLength"', '"LeverWidth"'],
    )
    await ensure_fully_defined(adapter, "lever profile")
    check("exit_sketch lever", await adapter.exit_sketch())
    name_last_feature(adapter, "LeverProfile")
    drive_jobs = lever.apply(adapter, "LeverProfile")
    check(
        "extrude lever",
        await adapter.create_extrusion(ExtrusionParameters(depth=LEVER_THICK)),
    )
    name_last_feature(adapter, "Lever")
    # The depth stays off the print: the stock thickness prints from
    # LeverThickReference (below), which a drawing view can attach to.
    drive_jobs.append(
        (name_dimensions(adapter, "Lever", ["LeverDepth"])[0], '"LeverThick"')
    )
    volume = await volume_check(adapter, "lever", V_LEVER, 0.002 * V_LEVER)

    # --- Bolt holes: ONE native 5/16 clearance feature, two THRU instances
    # from the top face on the mid-width line; the second hole's Y repeats
    # the first's and stays off the print.
    holes = wizard_holes(
        adapter,
        CLEARANCE_SPEC,
        [[x, LEVER_THICK, -HOLE_Y] for x in HOLE_X],
        (0.0, 1.0, 0.0),
        "feed lever bolt holes (5/16 clearance)",
        name="BoltHoles",
        expect_dia_mm=HOLE_DIA,
        placement_dims=[
            (("Hole1X", '"LeverHoleX1"'), ("Hole1Y", '"LeverHoleY"')),
            (("Hole2X", '"LeverHoleX2"'), ("Hole2Y", '"LeverHoleY"')),
        ],
    )
    drive_jobs += holes.placement_drive_jobs
    volume = await volume_check(adapter, "bolt holes", volume - V_HOLES, 0.01 * V_HOLES)

    # --- Grip-end corners LAST: the printed radius on a one-edge fillet -----
    mid = LEVER_THICK / 2.0
    for feature, dimension, edge in (
        ("GripCorner", "GripCornerR", [LEVER_LENGTH, mid, 0.0]),
        ("OtherGripCorner", "OtherGripCornerR", [LEVER_LENGTH, mid, -LEVER_WIDTH]),
    ):
        check(f"fillet {feature}", await adapter.add_fillet(CORNER_R, [edge]))
        name_last_feature(adapter, feature)
        corner_dim = name_dimensions(adapter, feature, [dimension])
        drive_jobs.append((corner_dim[0], '"GripCornerR"'))
        volume = await volume_check(
            adapter, f"lever with {feature}", volume - V_CORNER, 0.1 * V_CORNER
        )
    _require_one_solid_body(adapter, label="feed lever")

    # --- The stock thickness: a reference sketch ------------------------------
    # Farm r1 (#290): the extrusion's imported depth has no sound drawing-view
    # attachment, so _supplier_dimensions refuses to dress it as the STOCK
    # reference; a sketch dimension attaches to its witness line (the base
    # bar's BarWidth, _supplier_washer_model's thickness witness). One plain
    # sketch line up the grip end on the Front plane, the front view's: it
    # lies on the end's edge, where a construction line's dash font printed
    # over the outline (end bracket, machinist review mr4).
    thick = SketchDims()
    check("create_sketch thickness reference", await adapter.create_sketch("Front"))
    to_front = _sketch_mapper(adapter, u_axis=0, v_axis=1, label="thickness reference")
    foot = to_front((LEVER_LENGTH, 0.0, 0.0))
    top = to_front((LEVER_LENGTH, LEVER_THICK, 0.0))
    set_sketch_direct_db(adapter, True)
    witness = check("thickness witness line", await adapter.add_line(*foot, *top))
    set_sketch_direct_db(adapter, False)
    await anchor_point_to_origin(
        adapter, f"{witness}.start", *foot, "thickness witness foot"
    )
    thick.record("ThickWitnessX", '"LeverLength"')
    check(
        "thickness witness along Y",
        await adapter.add_sketch_constraint(witness, None, "vertical"),
    )
    await dimension_between(
        adapter,
        f"{witness}.start",
        f"{witness}.end",
        "distance",
        LEVER_THICK,
        "LeverThick",
    )
    thick.record("LeverThick", '"LeverThick"')
    await ensure_fully_defined(adapter, "thickness reference sketch")
    check("exit_sketch thickness reference", await adapter.exit_sketch())
    name_last_feature(adapter, "LeverThickReference")
    drive_jobs += thick.apply(adapter, "LeverThickReference")

    await force_rebuild(adapter)
    for dimension_name, expression in drive_jobs:
        await drive_dimension(adapter, dimension_name, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven feed lever (equations neutral)", volume, 0.002 * V_LEVER
    )
    _require_one_solid_body(adapter, label="driven feed lever")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    # No model band: the holes print DRILL, so the title block's DRILLED
    # HOLES row governs them (spec DRILLED_BAND).
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter, PART_NAME, {"Isometric View Note": ISOMETRIC_VIEW_NOTE}
    )
    # The reference sketch owns a printed dimension but no geometry: hide it
    # so no assembly renders it; the drawing shows it in the front view that
    # imports its dimension (_drawing_hidden_sketches).
    blank_sketch(adapter, "LeverThickReference")
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
