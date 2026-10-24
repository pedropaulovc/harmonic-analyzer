"""Move one imported supplier reference dimension to a wider lane.

``annotate_supplier_screw`` sets every vertical reference 6 mm off the view
outline with its horizontal text centred on the line. A labelled text is far
wider than a small purchased part, so it prints across the part; moving the
line further out (the text follows it) keeps the part clear. The caller
reserves the wider lane in its pre-fit ``supplier_margins``.
"""

from __future__ import annotations

import math
from typing import Any

from _com import _early_bound
from _drawing_common import rebuild_drawing


def move_supplier_lane(adapter: Any, display: Any, dx: float, *, label: str) -> None:
    """Shift ``display`` by ``dx`` sheet metres along X and read it back."""
    annotation = _early_bound(
        _early_bound(display, "IDisplayDimension").GetAnnotation(), "IAnnotation"
    )
    x, y, _z = (float(value) for value in annotation.GetPosition())
    if not annotation.SetPosition2(x + dx, y, 0.0):
        raise RuntimeError(f"{label}: failed to move to its supplier lane")
    rebuild_drawing(adapter, label=f"{label} supplier lane")
    moved = float(annotation.GetPosition()[0])
    if not math.isclose(moved, x + dx, rel_tol=0.0, abs_tol=5e-4):
        raise RuntimeError(f"{label}: supplier lane read back at x {moved!r}")
