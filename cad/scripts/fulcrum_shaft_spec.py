r"""Pure-data dimensional contract shared by the fulcrum shaft and drawing."""

from __future__ import annotations


MM_PER_IN = 25.4

SHAFT_DIA = 0.25 * MM_PER_IN
SHAFT_LENGTH = 182.0

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "SectionProfile": {"ShaftDia"},
    "Shaft": {"Depth"},
}
