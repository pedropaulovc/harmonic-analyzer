"""Drawing side of ``_metric_vendor_dimension`` (#290 owner ruling 4).

An imported model dimension keeps its places and ``mm`` suffix but takes the
inch sheet's document units (farm run 20261101T101833081Z read back
``UseDocUnits`` True), so the sheet sets millimetres on each imported display
dimension, as ``_supplier_dimensions`` does, and reads the result back. Kept
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
    _KEEP,
    _SW_DECIMAL,
    MM_SUFFIX,
    _SW_MM,
    _presentation,
)


@_telemetry.traced("drawing.metric_vendor_dimensions")
def print_imported_metric_dimensions(
    adapter: Any, annotations: Iterable[Any], places: dict[str, int]
) -> None:
    """Print each named imported dimension in mm at its places with the
    ``mm`` label, and prove it reads back; an unmatched name is an error."""
    remaining = dict(places)
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        name = _annotation_name(adapter, annotation)
        digits = remaining.pop(name, None)
        if digits is None:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        if display.SetUnits2(False, _SW_MM, _SW_DECIMAL, 0, False, 0) != 0:
            raise RuntimeError(f"{name}: millimetre units were rejected on the sheet")
        if display.SetPrecision3(digits, _KEEP, _KEEP, _KEEP) != 0:
            raise RuntimeError(
                f"{name}: {digits} millimetre places were rejected on the sheet"
            )
        expected = (False, _SW_MM, digits, MM_SUFFIX)
        if _presentation(display) != expected:
            raise RuntimeError(
                f"imported dimension {name!r} does not print millimetres: "
                f"{_presentation(display)!r} != {expected!r}"
            )
    if remaining:
        raise RuntimeError(
            f"metric dimensions never reached the sheet: {sorted(remaining)}"
        )
