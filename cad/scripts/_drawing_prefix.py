"""Model-dimension prefix text, separate to limit cache blast radius."""

from __future__ import annotations

from typing import Any

import _telemetry
from _com import _early_bound
from _drawing_precision import _named_dimension


@_telemetry.traced("dim.prefix", label_param="dimension_name")
def set_dimension_prefix(
    adapter: Any, feature_name: str, dimension_name: str, prefix: str
) -> None:
    """Set and verify a model display dimension's native prefix text."""
    display, _ = _named_dimension(adapter, feature_name, dimension_name)
    display = _early_bound(display, "IDisplayDimension")
    # SetText is void in the native API. Its return value cannot indicate
    # success; the persisted prefix is the authoritative result.
    display.SetText(1, prefix)  # swDimensionTextParts_e.swDimensionTextPrefix
    if str(display.GetText(1) or "") != prefix:
        raise RuntimeError(
            f"{dimension_name}@{feature_name}: prefix did not persist as {prefix!r}"
        )
