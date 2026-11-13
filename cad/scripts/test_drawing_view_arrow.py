"""Viewing arrows square the same way on every seat window (#2708).

The farm's drawing windows are 1010x598 px (2.098 px/mm fitted to a B sheet)
and, on swmaker000004, 1010x678 px (2.325 px/mm).  A note's leader start is
laid out on those pixels, so the model window below floors every leader
readback to its pixel grid at the current zoom.
"""

from __future__ import annotations

import math
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

import _drawing_view_arrow as arrow
import draw_ch_amplitude_bar
import draw_dt_pinion_cam
import draw_fr_top_frame
import draw_pd_support_bar
import draw_pd_transgear_feed_pinion
import draw_pd_transgear_knob_shaft
import draw_pn_pen_assembly
import draw_pn_pen_rod
import draw_sm_summing_lever

# (window px, fitted px per sheet metre)
WINDOWS = {"598 px": ((1010, 598), 2098.0), "678 px": ((1010, 678), 2325.0)}
# Under a twentieth of a millimetre a pixel: what "resolved" means here.
RESOLVED = 0.00005
LETTER_HEIGHT = 0.005
LETTER_WIDTH = 0.0037


class _PixelWindow:
    def __init__(self, window_px: tuple[int, int], fit_px_per_m: float) -> None:
        self.window_px, self.fit_px_per_m = window_px, fit_px_per_m
        self.px_per_m = fit_px_per_m

    def ViewZoomTo2(self, x0, y0, _z0, x1, y1, _z1):  # noqa: N802
        self.px_per_m = min(
            self.window_px[0] / (x1 - x0), self.window_px[1] / (y1 - y0)
        )

    def ViewZoomtofit2(self):  # noqa: N802
        self.px_per_m = self.fit_px_per_m

    def GraphicsRedraw2(self):  # noqa: N802
        return None


class _ArrowNote:
    """A letter note whose leader leaves its box ``offset`` across the arrow
    from where the requested letter would square it; the readback floors
    that start to the window's pixels."""

    def __init__(
        self, window: _PixelWindow, text_xy, tip, axis: int, offset: float
    ) -> None:
        self.window, self.anchor, self.tip, self.axis = (
            window,
            list(text_xy),
            tuple(tip),
            axis,
        )
        self.start_from_anchor = tip[axis] - text_xy[axis] + offset

    def true_start(self) -> list[float]:
        start = list(self.anchor)
        start[self.axis] += self.start_from_anchor
        return start

    def GetAnnotation(self):  # noqa: N802
        return self

    def GetTextFormat(self, _index):  # noqa: N802
        return SimpleNamespace(CharHeight=0.0035)

    def SetTextFormat(self, _index, _use_document, _text_format):  # noqa: N802
        return True

    def GetLeaderPointsAtIndex(self, _index):  # noqa: N802
        px = self.window.px_per_m
        start = [math.floor(value * px) / px for value in self.true_start()]
        return (*start, 0.0, *self.tip, 0.0)

    def GetPosition(self):  # noqa: N802
        return (*self.anchor, 0.0)

    def SetPosition2(self, x, y, _z):  # noqa: N802
        self.anchor = [x, y]
        return True


def _sheet_arrows() -> dict[str, tuple[tuple[float, float], tuple[float, float], int]]:
    """Every arrow-sheet's (letter, tip, axis the letter slides along)."""
    support_letter, support_tip = draw_pd_support_bar._view_arrow_points(
        (0.200, 0.150), (0.180, 0.150)
    )
    knob_tip = (0.290, 0.1624)
    knob = draw_pd_transgear_knob_shaft
    pen = draw_pn_pen_assembly
    pen_tip = (0.150, 0.120)
    return {
        "ch_amplitude_bar C": (*draw_ch_amplitude_bar.VIEW_C_ARROW, 1),
        "dt_pinion_cam A": (*draw_dt_pinion_cam.SET_SCREW_VIEW_ARROW, 0),
        "fr_top_frame G": (*draw_fr_top_frame.VIEW_G_ARROW, 1),
        "fr_top_frame underside": (*draw_fr_top_frame.UNDERSIDE_VIEW_ARROW, 0),
        "pd_support_bar D": (support_letter, support_tip, 1),
        "pd_transgear_feed_pinion C": (*draw_pd_transgear_feed_pinion.VIEW_C_ARROW, 1),
        "pd_transgear_feed_pinion D": (*draw_pd_transgear_feed_pinion.VIEW_D_ARROW, 1),
        "pd_transgear_feed_pinion E": (*draw_pd_transgear_feed_pinion.VIEW_E_ARROW, 1),
        "pd_transgear_knob_shaft C": (
            (
                knob_tip[0] + knob.VIEW_ARROW_LENGTH,
                knob_tip[1] + knob.VIEW_LETTER_HEIGHT / 2.0,
            ),
            knob_tip,
            1,
        ),
        "pn_pen_assembly C": (
            (pen_tip[0] - pen.DETAIL_LETTER_WIDTH, pen_tip[1] + pen.VIEW_ARROW_RISE),
            pen_tip,
            0,
        ),
        "pn_pen_rod A": (*draw_pn_pen_rod.VIEW_A_ARROW, 1),
        "sm_summing_lever F": (*draw_sm_summing_lever.VIEW_F_ARROW, 0),
        "sm_summing_lever G": (*draw_sm_summing_lever.VIEW_G_ARROW, 0),
    }


SHEET_ARROWS = _sheet_arrows()


def _square(
    monkeypatch,
    window_key: str,
    text_xy,
    tip,
    axis: int,
    *,
    zoomed: bool,
    offset: float = 0.0004,
):
    window = _PixelWindow(*WINDOWS[window_key])
    # 0.4 mm off by default: under one fitted pixel on either window.
    note = _ArrowNote(window, text_xy, tip, axis, offset)
    monkeypatch.setattr(arrow, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(arrow, "rebuild_drawing", lambda *_args, **_kwargs: None)
    if not zoomed:
        monkeypatch.setattr(arrow, "_zoomed_on", lambda *_args: nullcontext())
    arrow.square_view_arrow(
        SimpleNamespace(currentModel=window),
        note,
        text_xy=text_xy,
        tip_xy=tip,
        axis=axis,
        label="test arrow",
        letter_height=LETTER_HEIGHT,
    )
    return window, note


@pytest.mark.parametrize("name", sorted(SHEET_ARROWS))
def test_every_sheet_arrow_squares_alike_on_both_windows(
    monkeypatch, name: str
) -> None:
    text_xy, tip, axis = SHEET_ARROWS[name]
    anchors = {}
    for key in WINDOWS:
        window, note = _square(monkeypatch, key, text_xy, tip, axis, zoomed=True)
        assert window.px_per_m == window.fit_px_per_m
        assert abs(note.true_start()[axis] - tip[axis]) < RESOLVED
        anchors[key] = note.anchor
    assert math.dist(*anchors.values()) < RESOLVED


@pytest.mark.parametrize("name", sorted(SHEET_ARROWS))
def test_a_fitted_readback_leaves_each_arrow_off_square_on_some_window(
    monkeypatch, name: str
) -> None:
    """The control: read on the fitted window, as the sheets did before
    #2708, every arrow is left off square on one of the two windows for some
    leader start under a fitted pixel (VIEW E on the 678 px one, 0.4 mm, was
    release v49 r2's leaf 20261113T013309Z)."""
    text_xy, tip, axis = SHEET_ARROWS[name]
    misses = []
    for key in WINDOWS:
        for offset in (0.00032, 0.00036, 0.0004, 0.00042):
            _window, note = _square(
                monkeypatch, key, text_xy, tip, axis, zoomed=False, offset=offset
            )
            misses.append(abs(note.true_start()[axis] - tip[axis]))
    assert max(misses) > arrow.VIEW_ARROW_SQUARE_TOL


@pytest.mark.parametrize("name", sorted(SHEET_ARROWS))
def test_the_zoom_square_holds_the_arrow_at_a_resolving_scale(name: str) -> None:
    text_xy, tip, _axis = SHEET_ARROWS[name]
    centre, half = arrow.view_arrow_zoom(text_xy, tip)
    # The letter's box hangs right and down from its upper-left point.
    corners = (
        tip,
        text_xy,
        (text_xy[0] + LETTER_WIDTH, text_xy[1] - LETTER_HEIGHT),
    )
    for x, y in corners:
        assert abs(x - centre[0]) < half and abs(y - centre[1]) < half
    for (width, height), _fit in WINDOWS.values():
        assert 2.0 * half / min(width, height) < RESOLVED
