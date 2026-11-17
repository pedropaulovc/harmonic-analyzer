"""Thumb supplier lane regressions at the native boundary, without COM.

The recorded abe9 thread-length ink crossed its 77 mm cell floor by
7.5895 mm. Native 9aae then passed containment at 2:1 but printed two
overlapping .094 spans. Synthetic display primitives exercise the real ink
and path guards below; they are not evidence of a successful native rerender.
Native 34eb subsequently refused a station transition without numeric evidence;
these synthetic failures require full before/after data and live-sheet capture,
not a relaxed station tolerance or a claimed native layout fix.
Native 012dd showed that enabling offset mode relocates its line to the prior
annotation anchor, which is above the text baseline by a measured font offset.
The primitive fixture models that transition independently of text-only moves.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import _purchased_fastener_drawing as purchased
import draw_sh_vn_thumb_screw as thumb


class _ThumbView:
    """Supplier envelope plus the fixed native outline padding read on 9aae."""

    X_PADDING = 0.0058302
    Y_PADDING = 0.0057014

    def __init__(self, center):
        self.Position = tuple(center)
        self.ScaleRatio = (1.0, 1.0)
        self.UseSheetScale = 0
        self.displays = []

    def GetOrientationName(self):
        return "*Front"

    def GetName2(self):
        return "Drawing View1"

    def GetOutline(self):
        ratio = self.ScaleRatio[0] / self.ScaleRatio[1]
        x, y = self.Position
        radius = thumb.supplier.HEAD_DIA / 2000.0 * ratio
        return (
            x - self.X_PADDING,
            y - radius - self.Y_PADDING,
            x + thumb.supplier.OVERALL_LEN / 1000.0 * ratio + self.X_PADDING,
            y + radius + self.Y_PADDING,
        )

    def SetViewPosition(self, position, _update):
        self.Position = tuple(position)
        return True

    def UpdateViewDisplayGeometry(self):
        pass

    def GetFirstDisplayDimension6(self):
        return self.displays[0] if self.displays else None

    def GetAnnotations(self):
        return ()

    def project(self, point):
        ratio = self.ScaleRatio[0] / self.ScaleRatio[1]
        return tuple(
            origin + value * ratio for origin, value in zip(self.Position, point)
        )


def _fitted_front(monkeypatch, notes=""):
    monkeypatch.setattr(purchased, "double_array", tuple)
    cell = next(
        row
        for row in purchased.fastener_view_cells(
            purchased.view_band_bottom(notes, label="thumb regression")
        )
        if row[0] == "*Front"
    )
    fit = purchased.supplier_fit_cells(
        (cell,), thumb.SUPPLIER_MARGINS, label="thumb regression"
    )[0]
    view = _ThumbView(cell[1])
    draw = SimpleNamespace(EditRebuild3=lambda: True)
    scale = purchased._fit_group(draw, [(view, fit)])
    return view, cell[2], fit[2], scale


def test_thumb_prefit_reserves_native_text_and_intentionally_chooses_four_to_one(
    monkeypatch,
):
    view, outer, inner, scale = _fitted_front(monkeypatch)
    assert outer == pytest.approx((0.025, 0.077, 0.205, 0.182))
    assert thumb.SUPPLIER_MARGINS["*Front"] == pytest.approx(
        (0.0345, 0.016, 0.0665, 0.020)
    )
    # The outer diameter line must clear the inner native text as well as
    # reserving its own text. Include fixed padding rather than scaling it.
    available_width, available_height = inner[2] - inner[0], inner[3] - inner[1]
    assert available_width == pytest.approx(0.079)
    assert available_height == pytest.approx(0.069)
    assert (
        thumb.supplier.OVERALL_LEN / 1000.0 * 4 + 2 * view.X_PADDING < available_width
    )
    assert (
        thumb.supplier.OVERALL_LEN / 1000.0 * 5 + 2 * view.X_PADDING > available_width
    )
    assert scale == (4, 1)
    assert view.GetOutline()[1] >= inner[1]
    assert view.GetOutline()[3] <= inner[3]
