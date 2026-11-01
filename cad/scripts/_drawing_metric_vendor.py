"""Drawing-side proof for ``_metric_vendor_dimension`` (#290 owner ruling 4).

Kept apart from the part-side setter so part builds never import the drawing
adapter module (``test_part_isolation``).
"""

from __future__ import annotations

from typing import Any, Iterable

from solidworks_mcp.adapters.solidworks.drawing import (
    dimension_name as _annotation_name,
)

import _telemetry
from _com import _early_bound
from _metric_vendor_dimension import MM_SUFFIX, _SW_MM, _presentation


@_telemetry.traced("drawing.metric_vendor_dimensions")
def assert_imported_metric_dimensions(
    adapter: Any, annotations: Iterable[Any], places: dict[str, int]
) -> None:
    """Prove each named imported dimension still prints mm at its places with
    the ``mm`` label; an unmatched name is an error."""
    remaining = dict(places)
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        name = _annotation_name(adapter, annotation)
        digits = remaining.pop(name, None)
        if digits is None:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        expected = (False, _SW_MM, digits, MM_SUFFIX)
        if _presentation(display) != expected:
            raise RuntimeError(
                f"imported dimension {name!r} lost its millimetre presentation: "
                f"{_presentation(display)!r} != {expected!r}; rebuild the source part"
            )
    if remaining:
        raise RuntimeError(
            f"metric dimensions never reached the sheet: {sorted(remaining)}"
        )
