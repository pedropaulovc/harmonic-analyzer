r"""Reproduction script: dt-cone-tip-gear-tl-cutter.SLDASM (MHA-DT-37-TL-00).

The cone tip gear's fly cutter as set up, a shop fixture (issue #2358): the
bar dt-cone-tip-gear-tl-cutter-bar (MHA-DT-37-TL-02), the DT6-FORM1 bit
dt-cone-tip-gear-tl-form-cutter (MHA-DT-37-TL-01) in its cross hole at the
nominal stick-out, face leading, and the bought set screw
sh-vn-arbor-set-screw (MHA-SH-VN-54) seated on the bit, each fixed (0 DOF) at
``dt_cone_tip_gear_tl_cutter_spec``'s pose. The ``_tl_`` stem keeps the
fixture out of every machine assembly and BOM
(``_buildgraph.is_shop_fixture``). One hidden assembly sketch on the Front
Plane carries the stick-out and swing radius the fitter sheet prints as
references (``build_sm_summing_assembly._author_settings``'s recipe).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_dt_cone_tip_gear_tl_cutter_assembly.py
"""

from __future__ import annotations

import sys
from typing import Any

from _assembly import (
    activate_assembly_contract,
    assembly_title_properties,
    assert_components_fully_defined,
    check_no_interference,
    place_component,
    save_assembly_and_images,
)
from _check import check
from _com import _early_bound
from _custom_properties import apply_custom_properties
from _document_units import apply_package_model_units
from _drawing_marks import DRAWN_BY, mark_dimensions_for_drawing
from _drawing_precision import apply_drawing_precision
from _dt_cone_tip_gear_tl_cutter_interference import ALLOWED_PAIRS
from _feature_tree import name_last_feature
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    blank_sketch,
    dimension_between,
    ensure_fully_defined,
)
from _transforms import euler_from_rows
from dt_cone_tip_gear_tl_cutter_spec import (
    BAR_POSITION,
    BAR_ROWS,
    BIT_POSITION,
    BIT_ROWS,
    CONTRACT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    SET_SCREW_POSITION,
    SET_SCREW_ROWS,
    SETTINGS_CHAIN,
    SETTINGS_SKETCH,
    STICK_OUT,
    STICK_OUT_DIMENSION,
    SWING_RADIUS,
    SWING_RADIUS_DIMENSION,
)
from solidworks_mcp.adapters.com_variant import double_array

ASM_NAME = "dt-cone-tip-gear-tl-cutter"


def _rows(frozen: tuple[tuple[float, ...], ...]) -> list[list[float]]:
    return [list(row) for row in frozen]


def _sketch_xy_mm(
    adapter: Any, point_mm: tuple[float, float, float]
) -> tuple[float, float]:
    """The active sketch's (x, y), mm, of a model point given in mm."""
    sketch = _early_bound(adapter.currentModel.SketchManager.ActiveSketch, "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    point = _early_bound(
        utility.CreatePoint(double_array([value / 1000.0 for value in point_mm])),
        "IMathPoint",
    )
    moved = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
    data = [float(value) for value in moved.ArrayData]
    return data[0] * 1000.0, data[1] * 1000.0


async def _author_settings(adapter: Any) -> None:
    """CutterSettingsReference: two construction lines end to end along the
    bit's axis at the cross-hole station, bar axis -> bar surface -> P1. The
    outer line's length is the stick-out; the chain's span is the swing
    radius. Both are marked for the drawing, then the sketch is blanked."""
    dims = SketchDims()
    check("create cutter settings sketch", await adapter.create_sketch("Front"))
    axis, surface, tip = (
        _sketch_xy_mm(adapter, (x, y, 0.0)) for x, y in SETTINGS_CHAIN
    )
    if any(abs(point[1] - axis[1]) > 1e-9 for point in (surface, tip)):
        raise RuntimeError("the cutter settings chain is not sketch-horizontal")
    inner, outer = await add_line_chain(adapter, [axis, surface, tip], close=False)
    for line in (inner, outer):
        segment = _early_bound(adapter._sketch_entities[line], "ISketchSegment")
        segment.ConstructionGeometry = True
        if not bool(segment.ConstructionGeometry):
            raise RuntimeError(f"{line} did not take the construction flag")
        check(
            f"{line} along the bit",
            await adapter.add_sketch_constraint(line, None, "horizontal"),
        )
    await anchor_point_to_origin(
        adapter, f"{inner}.start", *axis, "bar axis at the cross-hole station"
    )
    # anchor_point_to_origin emits one dimension per non-zero coordinate.
    for name, value in zip(("SettingsAxisX", "SettingsStation"), axis, strict=True):
        if abs(value) >= 1e-9:
            dims.record(name)
    await dimension_between(
        adapter,
        f"{outer}.start",
        f"{outer}.end",
        "horizontal_distance",
        STICK_OUT,
        "stick-out",
    )
    dims.record(STICK_OUT_DIMENSION)
    await dimension_between(
        adapter,
        f"{inner}.start",
        f"{outer}.end",
        "horizontal_distance",
        SWING_RADIUS,
        "swing radius",
    )
    dims.record(SWING_RADIUS_DIMENSION)
    await ensure_fully_defined(adapter, SETTINGS_SKETCH)
    check("exit cutter settings sketch", await adapter.exit_sketch())
    name_last_feature(adapter, SETTINGS_SKETCH)
    dims.apply(adapter, SETTINGS_SKETCH)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    for feature, names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature, names)
    blank_sketch(adapter, SETTINGS_SKETCH)


async def build(adapter) -> dict[str, str]:
    # Free-DOF contract: cad/config/assemblies/<ASM_NAME>.yaml.
    activate_assembly_contract(ASM_NAME)
    check("create_assembly", await adapter.create_assembly())
    apply_package_model_units(adapter, CONTRACT.drawing_unit, label=ASM_NAME)

    # The bar keeps its part frame; the bit lies through its cross hole, face
    # leading; the screw stands on the axis below the bit, cup on its shank.
    rows = _rows(BAR_ROWS)
    await place_component(
        adapter,
        "dt-cone-tip-gear-tl-cutter-bar",
        list(BAR_POSITION),
        euler_from_rows(rows),
        rows,
    )
    rows = _rows(BIT_ROWS)
    await place_component(
        adapter,
        "dt-cone-tip-gear-tl-form-cutter",
        list(BIT_POSITION),
        euler_from_rows(rows),
        rows,
    )
    rows = _rows(SET_SCREW_ROWS)
    await place_component(
        adapter,
        "sh-vn-arbor-set-screw",
        list(SET_SCREW_POSITION),
        euler_from_rows(rows),
        rows,
    )
    assert_components_fully_defined(adapter)
    # Only the set screw's thread envelope in the bar's tap may overlap; the
    # bit's slip fit and the screw's cup on the bit are clearance and contact.
    check_no_interference(adapter, allowed_pairs=ALLOWED_PAIRS)
    await _author_settings(adapter)

    # Title-block identity for the fitter sheet
    # (draw_dt_cone_tip_gear_tl_cutter_assembly.py); material and finish
    # belong to each component's own drawing.
    apply_custom_properties(
        adapter,
        {
            **assembly_title_properties(ASM_NAME),
            "Revision Description": "Initial release",
            "Material": "SEE COMPONENT DRAWINGS",
            "Material Specification": "SEE COMPONENT DRAWINGS",
            "Finish": "SEE COMPONENT DRAWINGS",
            "Quantity": "1",
            "Drawn By": DRAWN_BY,
        },
    )
    return await save_assembly_and_images(adapter, ASM_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
