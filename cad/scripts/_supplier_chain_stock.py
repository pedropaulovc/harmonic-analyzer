"""Construction-only supplier stock diagrams, never installed chain geometry.

The diagrams are construction sketches (the shared zero-body diagram contract);
the chain drawings print them black at visible-edge weight, so the roller,
plate and pin section outlines read as the diagram's edges.

6261K171 is the configurable family; its 6261K401 graphic is an eleven-foot
example. The inspected 6261K281 native/STEP is the family's ONE-foot selection,
not this project's two-foot purchase. Only family cross-sections and pitch are
used here. 6261K108 supplies the connector's own stock/application references.
No downloaded body, reconstructed solid or chain purchase length is authored.
"""

from __future__ import annotations

from typing import Any

from _check import check
from _com import _early_bound
from _drawing_marks import mark_dimensions_for_drawing
from _feature_tree import name_last_feature
from _sketch import (
    SketchDims,
    add_line_chain,
    blank_reference_sketches,
    ensure_fully_defined,
)
from _sketch_chains import define_rectilinear_chain
from _sketch_circle import define_circle
from _supplier_spring_reference import ReferenceState, add_supplier_reference_configurations

SUPPLIER_REFERENCE_CONFIGURATION = "SUPPLIER_REFERENCE"
PITCH = 6.35
PIN_DIAMETER = 2.2987  # Exact native .0905 in; supplier prints .091, not .091 exact.
ROLLER_DIAMETER = 3.302
ROLLER_WIDTH = 3.175
PLATE_THICKNESS = 0.762
CONNECTING_PIN_LENGTH = 8.509
# ANSI #25 link-plate height H 0.228 in (PEER Chain single-strand size chart,
# 25R column, read 2026-11-01, https://www.peerchain.com/chain-pitches/; the
# same chart's T 0.030 in matches PLATE_THICKNESS). Drawn only as the plate's
# nominal section outline in the TOP diagram; it is not a supplier REF.
PLATE_HEIGHT = 0.228 * 25.4  # 5.7912
FRONT_FEATURE = "SupplierChainNominalFront"
SECTION_FEATURE = "SupplierChainNominalSections"
PITCH_DIMENSION = "SupplierPitch"
PIN_DIMENSION = "SupplierPinDiameter"
ROLLER_DIMENSION = "SupplierRollerDiameter"
WIDTH_DIMENSION = "SupplierRollerWidth"
PLATE_DIMENSION = "SupplierPlateThickness"
LENGTH_DIMENSION = "SupplierOverallPinLength"
DIMENSIONS_BY_FEATURE = {
    FRONT_FEATURE: {PITCH_DIMENSION, PIN_DIMENSION, ROLLER_DIMENSION},
    SECTION_FEATURE: {WIDTH_DIMENSION, PLATE_DIMENSION, LENGTH_DIMENSION},
}


def _construction(adapter: Any, entity: str) -> None:
    segment = _early_bound(adapter._sketch_entities[entity], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity}: supplier diagram must be construction-only")


async def _reference_front(adapter: Any) -> str:
    """Two nominal section circles; origin-to-centre dimension is their pitch.

    The circles are the pin and roller outlines. There is no plate profile:
    the supplier gives no plate height. The origin is the first section
    centre, so the second centre's driving station is also the native
    centre-to-centre pitch. No duplicate carrier is needed.
    """
    check("create supplier chain nominal front", await adapter.create_sketch("Front"))
    dims = SketchDims()
    for name, diameter, x in (
        (PIN_DIMENSION, PIN_DIAMETER, 0.0),
        (ROLLER_DIMENSION, ROLLER_DIAMETER, PITCH),
    ):
        circle = await define_circle(
            adapter, x, 0.0, diameter / 2.0, name, dims=dims,
            names=(PITCH_DIMENSION if x else None, None, name),
        )
        _construction(adapter, circle)
    await ensure_fully_defined(adapter, FRONT_FEATURE)
    check("exit supplier chain nominal front", await adapter.exit_sketch())
    name_last_feature(adapter, FRONT_FEATURE)
    dims.apply(adapter, FRONT_FEATURE)
    mark_dimensions_for_drawing(adapter, FRONT_FEATURE, DIMENSIONS_BY_FEATURE[FRONT_FEATURE])
    blank_reference_sketches(adapter, (FRONT_FEATURE,))
    return FRONT_FEATURE


async def _reference_sections(adapter: Any, *, connecting: bool) -> str:
    """Separate nominal sections, not dimensions on the installed stand-in.

    Each dimensioned span is one side of its section outline, so the
    extension lines start on printed edges: the roller (diameter wide), the
    plate (PLATE_HEIGHT wide) and the pin (diameter wide, drawn back from its
    span, whose dimension sits on the right). The pin stands at three pitches,
    clear of the plate outline.
    """
    rows = [(WIDTH_DIMENSION, 0.0, ROLLER_WIDTH, ROLLER_DIAMETER)]
    if connecting:
        rows.extend(((PLATE_DIMENSION, PITCH, PLATE_THICKNESS, PLATE_HEIGHT),
                     (LENGTH_DIMENSION, 3.0 * PITCH, CONNECTING_PIN_LENGTH, -PIN_DIAMETER)))
    check("create supplier chain nominal sections", await adapter.create_sketch("Top"))
    dims = SketchDims()
    for name, x, length, outline in rows:
        y0, y1 = -length / 2.0, length / 2.0
        anchors = [f"{name}StartX"] if x else []
        points = [(x, y0), (x, y1), (x + outline, y1), (x + outline, y0)]
        lines = await add_line_chain(adapter, points)
        for line in lines:
            _construction(adapter, line)
        await define_rectilinear_chain(
            adapter, lines, points, label=name, dims=dims,
            names=[name, f"{name}Outline", *anchors, f"{name}StartY"],
        )
    await ensure_fully_defined(adapter, SECTION_FEATURE)
    check("exit supplier chain nominal sections", await adapter.exit_sketch())
    name_last_feature(adapter, SECTION_FEATURE)
    dims.apply(adapter, SECTION_FEATURE)
    mark_dimensions_for_drawing(adapter, SECTION_FEATURE, {row[0] for row in rows})
    blank_reference_sketches(adapter, (SECTION_FEATURE,))
    return SECTION_FEATURE


async def add_chain_stock_references(adapter: Any, *, connecting: bool = False) -> None:
    """Add a zero-body reference state while preserving every original member."""
    async def references(target: Any) -> tuple[str, ...]:
        return await _reference_front(target), await _reference_sections(
            target, connecting=connecting,
        )

    await add_supplier_reference_configurations(
        adapter,
        (ReferenceState(
            SUPPLIER_REFERENCE_CONFIGURATION, None, references,
            body_count=0, kind="diagram",
        ),),
        body_count=4,
    )
