"""Imported-text readback for the measuring-stick stop drawings
(MHA-MS-02, MHA-MS-03).

The drawings author no presentation on imported dimensions: the parts write
their own callout rows and quantity prefixes (#1942), which a drawing only
reads back here, with the text parts and row normalizer the part builds use
(``ms_stop_callouts``).  The clean-source guard is ``_drawing_source_guard``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import _telemetry
from _com import _early_bound
from ms_stop_callouts import CALLOUT_BELOW, PREFIX_DEFINITION, callout_rows
from solidworks_mcp.adapters.solidworks.drawing import dimension_name


@_telemetry.traced("drawing.ms_imported_text")
def assert_imported_text(
    adapter: Any,
    annotations: Iterable[Any],
    below: Mapping[str, str],
    prefixes: Mapping[str, str] | None = None,
) -> None:
    """Every named imported dimension prints the callout rows and quantity
    prefix its PART authored; the drawing never writes them."""
    prefixes = prefixes or {}
    seen: set[str] = set()
    wrong: dict[str, str] = {}
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        name = dimension_name(adapter, annotation)
        if name not in below and name not in prefixes:
            continue
        seen.add(name)
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        if name in below:
            printed = str(display.GetText(CALLOUT_BELOW) or "")
            if callout_rows(printed) != callout_rows(below[name]):
                wrong[name] = printed
        if name in prefixes:
            definition = str(display.GetText(PREFIX_DEFINITION) or "")
            if not definition.startswith(prefixes[name]):
                wrong[f"{name} prefix"] = definition
    missing = sorted({*below, *prefixes} - seen)
    if missing:
        raise RuntimeError(f"imported dimensions missing from the sheet: {missing}")
    if wrong:
        raise RuntimeError(
            f"imported dimension text differs from the part's: {wrong!r}"
        )
