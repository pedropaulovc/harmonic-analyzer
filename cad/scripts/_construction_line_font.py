"""Draw this drawing's construction curves as solid, thick visible outline.

Zero-body supplier diagrams are model construction geometry. In the default
construction font a thin feature prints as short dashes, which a reader takes
for hidden lines. The setting is a drawing document preference
(DP_LineFont), so it changes this SLDDRW only.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from solidworks_mcp.adapters.sw_type_info import constant

from _com import _early_bound

_CONSTRUCTION_LINE_FONT = (
    ("swLineFontConstructionCurvesStyle", "swLineCONTINUOUS"),
    ("swLineFontConstructionCurvesThickness", "swLW_THICK"),
)


def _construction_curves_as_outline(adapter: Any) -> Callable[[], None]:
    """Set the active drawing's construction line font; return its readback."""
    extension = _early_bound(adapter.currentModel.Extension, "IModelDocExtension")
    option = constant("swDetailingNoOptionSpecified")
    settings = tuple(
        (name, constant(name), constant(value))
        for name, value in _CONSTRUCTION_LINE_FONT
    )

    def readback() -> None:
        for name, preference, value in settings:
            if int(extension.GetUserPreferenceInteger(preference, option)) != value:
                raise RuntimeError(f"construction line font {name} readback differs")

    for name, preference, value in settings:
        if not extension.SetUserPreferenceInteger(preference, option, value):
            raise RuntimeError(f"failed to set construction line font {name}")
    readback()
    return readback
