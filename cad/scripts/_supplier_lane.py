"""Move one imported vertical supplier reference clear of its part.

``annotate_supplier_screw`` sets every vertical reference 6 mm off the view
outline with its three-line horizontal text centred on the line at mid-span.
On a small purchased part that text is wider than the lane and taller than
the span, so it prints across the part and its own extension lines. This moves
the line further out (the text follows it) and lifts the text past the upper
extension line, where the dimension line extends to it. The caller reserves
the wider lane in its pre-fit ``supplier_margins``.
"""

from __future__ import annotations

import math
from typing import Any

from _com import _early_bound
from _drawing_common import rebuild_drawing

# Half a three-line reference text (~14 mm) plus a 2 mm gap to the upper
# extension line.
TEXT_CLEAR_M = 0.009


def move_supplier_lane(
    adapter: Any, display: Any, view: Any, *, lane_shift: float, label: str
) -> None:
    """Shift ``display``'s line ``lane_shift`` metres left; text above its span."""
    display = _early_bound(display, "IDisplayDimension")
    span = abs(float(_early_bound(display.GetDimension2(0), "IDimension").SystemValue))
    span *= float(_early_bound(view, "IView").ScaleDecimal)
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    x, y, _z = (float(value) for value in annotation.GetPosition())
    target = (x - lane_shift, y + span / 2.0 + TEXT_CLEAR_M)
    if not annotation.SetPosition2(*target, 0.0):
        raise RuntimeError(f"{label}: failed to move to its supplier lane")
    rebuild_drawing(adapter, label=f"{label} supplier lane")
    moved = tuple(float(value) for value in annotation.GetPosition())[:2]
    if not all(math.isclose(a, b, rel_tol=0.0, abs_tol=5e-4) for a, b in zip(moved, target)):
        raise RuntimeError(f"{label}: supplier lane read back at {moved!r}, not {target!r}")
