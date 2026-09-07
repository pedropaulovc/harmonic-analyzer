"""Prefix storage control used by diagnostics, not production source builders.

Keep this module outside production import closures. The caller owns redraw,
save and native identity boundaries; this operation verifies exact text storage.
"""

from typing import Any

from _common import _early_bound
from _drawing_marks import _named_dimension
import _telemetry


@_telemetry.traced("dim.prefix", label_param="dimension_name")
def set_dimension_prefix(
    adapter: Any, feature_name: str, dimension_name: str, prefix: str
) -> None:
    """Set and verify a model display dimension's native prefix text."""
    display, _ = _named_dimension(adapter, feature_name, dimension_name)
    display = _early_bound(display, "IDisplayDimension")
    # IDisplayDimension.SetText is void; GetText supplies the success witness.
    display.SetText(1, prefix)  # swDimensionTextParts_e.swDimensionTextPrefix
    applied = display.GetText(1)
    if applied != prefix:
        raise RuntimeError(
            f"{dimension_name}@{feature_name}: prefix did not persist as {prefix!r}; "
            f"native readback is {applied!r}"
        )
