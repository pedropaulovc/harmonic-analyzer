"""One source nominal circle isolated from both configured installed wires.

Reuse the native zero-body configuration pattern, not a new solid variant or
an installed-member alias. The isolation helper compares every original
configuration's bodies and suppression matrix and restores its active member.
"""

from __future__ import annotations

from _check import check
from _com import _early_bound
from _drawing_marks import mark_dimensions_for_drawing
from _feature_tree import name_last_feature
from _mcmaster_9666k56 import DIA
from _mcmaster_9666k56_reference import (
    SUPPLIER_REFERENCE_CONFIGURATION,
    SUPPLIER_REFERENCE_DIMENSION,
    SUPPLIER_REFERENCE_FEATURE,
)
from _sketch import SketchDims, blank_reference_sketches, ensure_fully_defined
from _sketch_circle import define_circle
from _supplier_spring_reference import ReferenceState, add_supplier_reference_configurations


async def _nominal_stock_circle(adapter) -> tuple[str, ...]:
    dims = SketchDims()
    check("create supplier stock cross-section", await adapter.create_sketch("Top"))
    circle = await define_circle(
        adapter, 0.0, 0.0, DIA / 2.0, "as-supplied nominal wire stock", dims=dims,
        names=(None, None, SUPPLIER_REFERENCE_DIMENSION),
    )
    segment = _early_bound(adapter._sketch_entities[circle], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError("supplier stock circle must remain construction-only")
    await ensure_fully_defined(adapter, "supplier nominal stock cross-section")
    check("exit supplier stock cross-section", await adapter.exit_sketch())
    name_last_feature(adapter, SUPPLIER_REFERENCE_FEATURE)
    dims.apply(adapter, SUPPLIER_REFERENCE_FEATURE)
    mark_dimensions_for_drawing(
        adapter, SUPPLIER_REFERENCE_FEATURE, {SUPPLIER_REFERENCE_DIMENSION},
    )
    blank_reference_sketches(adapter, (SUPPLIER_REFERENCE_FEATURE,))
    return (SUPPLIER_REFERENCE_FEATURE,)


async def author_nominal_stock_cross_section(adapter) -> None:
    """Preserve LeverWire and PenWire; add only a zero-body reference diagram."""
    await add_supplier_reference_configurations(
        adapter,
        (ReferenceState(
            SUPPLIER_REFERENCE_CONFIGURATION, None, _nominal_stock_circle,
            body_count=0, kind="diagram",
        ),),
        body_count=1,
    )
