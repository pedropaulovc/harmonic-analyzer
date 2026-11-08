"""Drawing side of ``_metric_vendor_dimension`` (#290 owner ruling 4).

An imported model dimension keeps its places and ``mm`` suffix but takes the
inch sheet's document units (farm run 20261101T101833081Z read back
``UseDocUnits`` True), so the sheet sets millimetres on each imported display
dimension, as ``_supplier_dimensions`` does, and reads the result back. The
model owns precision (drawing-simplicity-policy, rules 3 and 4): the sheet
checks the imported places before and after and never rewrites them. Kept
apart from the part-side setter so part builds never import the drawing
adapter module (``test_part_isolation``).
"""

from __future__ import annotations

from typing import Any, Iterable

from solidworks_mcp.adapters.solidworks.drawing import (
    dimension_name as _annotation_name,
)

import _telemetry
from _com import _early_bound
from _metric_vendor_dimension import (
    _SW_DECIMAL,
    MM_SUFFIX,
    _SW_MM,
    _presentation,
)


@_telemetry.traced("drawing.metric_vendor_dimensions")
def print_imported_metric_dimensions(
    adapter: Any, annotations: Iterable[Any], places: dict[str, int],
    *, references: Iterable[str] = (),
) -> None:
    """Print model-owned metric controls/REFs without rewriting their text.

    Reference dimensions require the complete ``(value mm)`` presentation,
    not bare parentheses which would discard the metric unit label.
    """
    remaining = dict(places)
    reference_names = set(references)
    if not reference_names <= remaining.keys():
        raise ValueError("metric reference names must also declare model precision")
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        name = _annotation_name(adapter, annotation)
        digits = remaining.pop(name, None)
        if digits is None:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        imported = _presentation(display)
        if imported[2] != digits:
            raise RuntimeError(
                f"imported dimension {name!r} arrived at {imported[2]} places, "
                f"not the builder's {digits}"
            )
        if display.SetUnits2(False, _SW_MM, _SW_DECIMAL, 0, False, 0) != 0:
            raise RuntimeError(f"{name}: millimetre units were rejected on the sheet")
        suffix = MM_SUFFIX + ")" if name in reference_names else MM_SUFFIX
        expected = (False, _SW_MM, digits, suffix)
        if _presentation(display) != expected or (
            name in reference_names and str(display.GetText(1) or "") != "("
        ):
            raise RuntimeError(
                f"imported dimension {name!r} does not print millimetres: "
                f"{_presentation(display)!r} != {expected!r}"
            )
    if remaining:
        raise RuntimeError(
            f"metric dimensions never reached the sheet: {sorted(remaining)}"
        )
