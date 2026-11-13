"""Square a letter viewing arrow on a readback that no seat window can move.

A viewing arrow (rule 9) is a letter note whose straight leader is the arrow;
the sheet slides the letter until the leader stands square onto its tip.  The
leader starts on the letter's box, and SolidWorks lays that box out on the
drawing window's pixels at the current zoom: the same letter's box read 13 px
high (6.20 mm) fitted on a 1010x598 px window and 16 px (6.88 mm) on a
1010x678 px one (#2708).  Fitted to a B sheet a pixel is 0.48 or 0.43 mm, over
:data:`VIEW_ARROW_SQUARE_TOL`, so a fitted readback squares to a different
place on each seat, or reads off square after its correction (release v49 r2,
``drawing:pd_transgear_feed_pinion`` leaf 20261113T013309Z, PR #2698).

Here the leader is read and squared zoomed onto the arrow itself
(:func:`_drawing_scan._zoomed_on`): the zoom square fills the window whatever
its pixel size, so a pixel is under 0.05 mm on any seat, and the fit is
restored afterwards.  The zoom square is built from the requested letter and
tip, not from a readback.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

from _com import _early_bound
from _drawing_common import rebuild_drawing
from _drawing_scan import _zoomed_on
import _telemetry

VIEW_ARROW_SQUARE_TOL = 0.0003
# The zoom square's least half-span about the arrow's middle; a longer arrow
# widens it to its own half-length plus VIEW_ARROW_LETTER_ROOM, so the letter's
# box and the tip stay in the window.  At 12.5 mm a pixel of a 598 px high
# window is 0.042 mm.
VIEW_ARROW_ZOOM_HALF = 0.012
VIEW_ARROW_LETTER_ROOM = 0.006
# The leader's tip is attached to geometry; this only proves it did not move.
_TIP_TOL = 0.001


def view_arrow_zoom(
    text_xy: Sequence[float], tip_xy: Sequence[float]
) -> tuple[tuple[float, float], float]:
    """The sheet square (centre, half-span) the arrow is read in."""
    centre = ((text_xy[0] + tip_xy[0]) / 2.0, (text_xy[1] + tip_xy[1]) / 2.0)
    span = max(abs(text_xy[0] - tip_xy[0]), abs(text_xy[1] - tip_xy[1]))
    return centre, max(VIEW_ARROW_ZOOM_HALF, span / 2.0 + VIEW_ARROW_LETTER_ROOM)


def _leader(
    annotation: Any, tip_xy: Sequence[float], label: str, stage: str
) -> list[float]:
    points = [float(value) for value in annotation.GetLeaderPointsAtIndex(0) or ()]
    if len(points) < 6 or math.dist((points[-3], points[-2]), tip_xy) > _TIP_TOL:
        raise RuntimeError(f"{label} tip moved {stage}: leader {points}")
    return points


def square_view_arrow(
    adapter: Any,
    note: Any,
    *,
    text_xy: Sequence[float],
    tip_xy: Sequence[float],
    axis: int,
    label: str,
    letter_height: float | None = None,
) -> list[float]:
    """Size the letter to ``letter_height`` (when given), then slide it along
    ``axis`` (0 = x, 1 = y) by the leader start's miss from ``tip_xy`` so
    the arrow stands square, all read zoomed onto the arrow.  Returns the
    zoomed leader points (x, y, z triples, start first)."""
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    if letter_height is not None:
        # add_note leaves text at the document height.
        text_format = annotation.GetTextFormat(0)
        if text_format is None:
            raise RuntimeError(f"{label} note has no text format")
        text_format.CharHeight = letter_height
        if not annotation.SetTextFormat(0, False, text_format):
            raise RuntimeError(f"failed to size the {label} letter")
        rebuild_drawing(adapter, label=f"{label} letter")
    fitted = [float(value) for value in annotation.GetLeaderPointsAtIndex(0) or ()]
    centre, half = view_arrow_zoom(text_xy, tip_xy)
    with _zoomed_on(adapter, centre, half):
        adapter.currentModel.GraphicsRedraw2()
        points = _leader(annotation, tip_xy, label, "when its letter was sized")
        zoomed = points[axis]
        # The leader leaves the letter's nearer side: slide the letter by any
        # miss across the arrow.
        miss = tip_xy[axis] - zoomed
        if abs(miss) > VIEW_ARROW_SQUARE_TOL:
            position = [float(value) for value in annotation.GetPosition()]
            position[axis] += miss
            if not annotation.SetPosition2(*position):
                raise RuntimeError(f"failed to square the {label}")
            rebuild_drawing(adapter, label=f"square {label}")
            adapter.currentModel.GraphicsRedraw2()
            points = _leader(annotation, tip_xy, label, "when it was squared")
            if abs(tip_xy[axis] - points[axis]) > VIEW_ARROW_SQUARE_TOL:
                raise RuntimeError(f"{label} did not square: leader {points}")
    _telemetry.info(
        f"{label}: leader start {'xy'[axis]} read fitted {fitted[axis : axis + 1]}, "
        f"zoomed {zoomed:.5f} (half-span {half:.4f}), tip {tip_xy[axis]:.5f}; leader "
        f"{points[0]:.5f},{points[1]:.5f} -> {points[-3]:.5f},{points[-2]:.5f}"
    )
    return points
