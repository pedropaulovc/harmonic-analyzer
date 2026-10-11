"""Drawing scene-probe zoom isolation and aggregate scan-span attributes.

Separate module so edits re-key only recipes that use this concern.
"""

from __future__ import annotations

from typing import Any
from typing import Iterator
from typing import Sequence
import _telemetry
import contextlib


def _span_scan_attrs(**attributes: float) -> None:
    """Attach aggregate scan counts to the CURRENT span.

    ``@traced`` owns the span, so there is no handle to set attributes on.
    A no-op when nothing is recording, so callers never guard.
    """
    span = _telemetry.trace.get_current_span()
    for key, value in attributes.items():
        span.set_attribute(key, value)


# The hit test's zoom window half-span. Fit to sheet, the pick aperture is a
# few pixels of a ~280 mm portrait sheet: millimetres wide, and wider on a
# 1024x640 seat window than on an 820-high one, so the same point returned
# another part's edge on swmaker000008 than on swmaker000004/6. Zoomed ~56x,
# the aperture is a few hundredths of a millimetre on every seat.
_HIT_ZOOM_HALF = 0.0025


@contextlib.contextmanager
def _zoomed_on(adapter: Any, centre: Sequence[float], half: float) -> Iterator[None]:
    """Zoom the drawing window onto a sheet square, then back to fit.

    new_project_drawing fits the sheet so every other coordinate pick sees the
    zoom it was placed under; this restores that zoom on the way out, also
    when the zoom call itself moved the view and then raised. A restore that
    fails after the body failed is noted on the body's error, which is the
    one raised.
    """
    draw = adapter.currentModel
    try:
        draw.ViewZoomTo2(
            centre[0] - half,
            centre[1] - half,
            0.0,
            centre[0] + half,
            centre[1] + half,
            0.0,
        )
        yield
    except BaseException as primary:
        try:
            draw.ViewZoomtofit2()
        except Exception as restore:
            primary.add_note(f"restoring the fit zoom also failed: {restore!r}")
        raise
    draw.ViewZoomtofit2()
