r"""Reproduction script: dt-cone-gear-tl-arbor.SLDASM (MHA-DT-03-TL-05).

The keyed cutting arbor kit, a shop fixture (issue #2465;
``dt_cone_gear_tl_arbor_assembly_spec``): the arbor, its bonded key, the three
backing collars and the nut, each fixed at its kit pose (0 DOF). The ``_tl_``
stem keeps the kit out of every machine assembly and BOM
(``_buildgraph.is_shop_fixture``). One hidden assembly sketch on the Right
Plane carries the two settings the fitting sheet states as reference
dimensions: the blank's near face from the jaw step and the seat's length
(``build_sm_summing_assembly._author_settings``'s recipe).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_dt_cone_gear_tl_arbor_assembly.py
"""

from __future__ import annotations

import sys
from typing import Any

from _assembly import (
    activate_assembly_contract,
    assembly_title_properties,
    assert_components_fully_defined,
    place_component,
    save_assembly_and_images,
)
from _assembly_contract import assembly_contract
from _check import check
from _com import _early_bound
from _custom_properties import apply_custom_properties
from _document_units import apply_package_model_units
from _drawing_marks import DRAWN_BY, mark_dimensions_for_drawing
from _drawing_precision import apply_drawing_precision
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
import dt_cone_gear_tl_arbor_assembly_spec as spec
from solidworks_mcp.adapters.com_variant import double_array

ASM_NAME = "dt-cone-gear-tl-arbor"
if ASM_NAME != spec.ASM_NAME:
    raise AssertionError("the builder's contract and the kit spec disagree")


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


def _as_construction(adapter: Any, entity_id: str) -> None:
    segment = _early_bound(adapter._sketch_entities[entity_id], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity_id} did not take the construction flag")


async def _author_settings(adapter: Any) -> None:
    """ArborSettings: a construction line along the arbor's -Y silhouette for
    each setting, anchored from the kit origin, its length the setting."""
    dims = SketchDims()
    check("create arbor settings sketch", await adapter.create_sketch("Right"))
    for name, (radius, start, end) in spec.SETTINGS.items():
        a = _sketch_xy_mm(adapter, (0.0, -radius, start))
        b = _sketch_xy_mm(adapter, (0.0, -radius, end))
        along_x = abs(b[0] - a[0]) > abs(b[1] - a[1])
        (line,) = await add_line_chain(adapter, [a, b], close=False)
        _as_construction(adapter, line)
        check(
            f"{name} along the arbor",
            await adapter.add_sketch_constraint(
                line, None, "horizontal" if along_x else "vertical"
            ),
        )
        await anchor_point_to_origin(
            adapter, f"{line}.start", a[0], a[1], f"{name} start"
        )
        dims.record(f"{name}AnchorX")
        dims.record(f"{name}AnchorY")
        await dimension_between(
            adapter,
            f"{line}.start",
            f"{line}.end",
            "horizontal_distance" if along_x else "vertical_distance",
            end - start,
            name,
        )
        dims.record(name)
    await ensure_fully_defined(adapter, spec.SETTINGS_SKETCH)
    check("exit arbor settings sketch", await adapter.exit_sketch())
    name_last_feature(adapter, spec.SETTINGS_SKETCH)
    dims.apply(adapter, spec.SETTINGS_SKETCH)
    apply_drawing_precision(adapter, spec.DRAWING_PRECISION)
    for feature, names in spec.DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature, names)
    blank_sketch(adapter, spec.SETTINGS_SKETCH)


async def build(adapter) -> dict[str, str]:
    # Free-DOF contract: cad/config/assemblies/<ASM_NAME>.yaml.
    activate_assembly_contract(ASM_NAME)
    check("create_assembly", await adapter.create_assembly())
    apply_package_model_units(
        adapter, assembly_contract(ASM_NAME).drawing_unit, label=ASM_NAME
    )
    # Inserted in BOM order (spec.BOM_ORDER): the fitting steps cite the BOM's
    # item numbers. Literal stems, so the build graph reads the sources.
    rows = [list(row) for row in spec.IDENTITY_ROWS]
    euler = euler_from_rows(rows)
    collars = spec.collar.CONFIGURATIONS
    await place_component(
        adapter,
        "dt-cone-gear-tl-keyed-arbor",
        list(spec.POSITIONS[spec.ARBOR]),
        euler,
        rows,
    )
    for configuration in collars:
        await place_component(
            adapter,
            "dt-cone-gear-tl-arbor-collar",
            list(spec.POSITIONS[spec.member(configuration)]),
            euler,
            rows,
            configuration=configuration,
            label=spec.member(configuration),
        )
    await place_component(
        adapter,
        "dt-cone-gear-tl-arbor-key",
        list(spec.POSITIONS[spec.KEY]),
        euler,
        rows,
    )
    await place_component(
        adapter,
        "dt-cone-gear-tl-vn-arbor-nut",
        list(spec.POSITIONS[spec.NUT]),
        euler,
        rows,
    )
    assert_components_fully_defined(adapter)
    await _author_settings(adapter)

    # Title-block identity for the fitting sheet
    # (draw_dt_cone_gear_tl_arbor_assembly.py); material and finish belong
    # to the component drawings.
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
