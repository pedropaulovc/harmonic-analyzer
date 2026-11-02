"""Supplier sizes print as untoleranced REF: the catalogue tolerance governs.

drawing-guidelines.md: purchased-part supplier dimensions are shown as REF,
untoleranced. A catalogue band stays in the spec wherever fit math reads it;
it never reaches the native dimension that prints.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from _com import _early_bound


def assert_supplier_screw_unbanded(displays: Mapping[str, Any]) -> None:
    """Refuse any supplier reference display that carries a native tolerance."""
    for name, display in displays.items():
        display = _early_bound(display, "IDisplayDimension")
        native = _early_bound(display.GetDimension2(0), "IDimension")
        if int(_early_bound(native.Tolerance, "IDimensionTolerance").Type) != 0:
            raise RuntimeError(f"{name}: supplier REF gained a tolerance")
