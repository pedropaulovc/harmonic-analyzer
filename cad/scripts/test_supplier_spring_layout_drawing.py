"""Pure geometry regressions for supplier-state annotation room, without COM."""

from __future__ import annotations

from itertools import combinations
from types import SimpleNamespace

import pytest

import _purchased_fastener_drawing as purchased
from _supplier_spring_drawing import supplier_state_cells
import vn_channel_spring_stock_geom as channel


# Representative annotation requirements, independent of the layout coordinates.
_EXTENSION_MARGINS = {
    "free_front": (0.0, 0.0, 0.0, 0.018),
    "free_right": (0.0, 0.018, 0.045, 0.018),
    "max_front": (0.0, 0.0, 0.0, 0.018),
}
_DIAGRAM_MARGINS = {
    "free_front": (0.035, 0.0, 0.035, 0.0),
    "free_top": (0.040, 0.0, 0.040, 0.0),
    "free_right": (0.035, 0.0, 0.035, 0.0),
}


def _annotation_envelope(bounds, margins):
    left, bottom, right, top = margins
    return (
        bounds[0] - left,
        bounds[1] - bottom,
        bounds[2] + right,
        bounds[3] + top,
    )


def _contains(outer, inner):
    return (
        outer[0] <= inner[0] < inner[2] <= outer[2]
        and outer[1] <= inner[1] < inner[3] <= outer[3]
    )


@pytest.mark.parametrize(
    "maximum,margins",
    [
        pytest.param(True, _EXTENSION_MARGINS, id="extension-free-and-maximum"),
        pytest.param(False, _DIAGRAM_MARGINS, id="nominal-diagrams"),
    ],
)
@pytest.mark.parametrize(
    "notes", ["", "FIRST\nSECOND\nTHIRD"], ids=["bare-footer", "full-footer"]
)
def test_state_cells_leave_positive_geometry_and_all_annotation_budgets(
    maximum, margins, notes
):
    caption_y = purchased.view_band_bottom(notes, label="supplier layout")
    cells = supplier_state_cells(caption_y, maximum=maximum)
    fitted = purchased.supplier_fit_cells(cells, margins, label="supplier layout")
    originals = {name: (center, bounds) for name, center, bounds in cells}
    expected_names = {"free_front", "free_top", "free_right", "installed_iso"}
    if maximum:
        expected_names.add("max_front")
    assert {name for name, _, _ in fitted} == set(originals) == expected_names

    for name, center, inner in fitted:
        outer_center, outer = originals[name]
        assert _contains(outer, inner), name
        assert center == pytest.approx(
            ((inner[0] + inner[2]) / 2.0, (inner[1] + inner[3]) / 2.0)
        ), name
        if name not in margins:
            # The extension Top and every installed pictorial keep their whole
            # cells; unused views must not pay another view's annotation budget.
            assert inner == outer, name
            assert center == outer_center, name
            continue

        left, bottom, right, top = margins[name]
        available = (
            inner[0] - outer[0],
            inner[1] - outer[1],
            outer[2] - inner[2],
            outer[3] - inner[3],
        )
        assert available == pytest.approx(margins[name]), name
        assert _annotation_envelope(inner, margins[name]) == pytest.approx(outer), name
        assert center == pytest.approx(
            (
                outer_center[0] + (left - right) / 2.0,
                outer_center[1] + (bottom - top) / 2.0,
            )
        ), name

    # Insets cannot hide overlapping outer view/caption plans. In particular,
    # the maximum-state Right and installed Iso need separate sheet regions.
    for (name_a, _, a), (name_b, _, b) in combinations(cells, 2):
        assert a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1], (
            name_a,
            name_b,
        )


@pytest.mark.parametrize(
    "maximum,legacy_width,margins",
    [
        pytest.param(True, 0.032, _EXTENSION_MARGINS, id="old-32mm-extension-right"),
        pytest.param(False, 0.042, _DIAGRAM_MARGINS, id="old-42mm-diagram-right"),
    ],
)
def test_old_right_widths_cannot_reserve_the_requested_annotation_room(
    maximum, legacy_width, margins
):
    caption_y = purchased.view_band_bottom("", label="legacy supplier layout")
    cells = supplier_state_cells(caption_y, maximum=maximum)
    old_cells = []
    for name, center, bounds in cells:
        if name == "free_right":
            # Change only the historical insufficient width, not a copied
            # coordinate table: 45 mm cannot fit in 32 mm, nor 35+35 in 42 mm.
            x0, y0, _, y1 = bounds
            bounds = (x0, y0, x0 + legacy_width, y1)
            center = ((bounds[0] + bounds[2]) / 2.0, (y0 + y1) / 2.0)
        old_cells.append((name, center, bounds))

    right_budget = margins["free_right"]
    assert right_budget[0] + right_budget[2] > legacy_width
    with pytest.raises(
        ValueError, match="free_right: supplier margins leave no geometry space"
    ):
        purchased.supplier_fit_cells(
            tuple(old_cells), margins, label="legacy supplier layout"
        )


class _CoilEndView:
    """A real coil's circular end span plus fixed synthetic native padding.

    The outline is calculated from the supplier model diameter and candidate
    scale, never from a target cell or a remembered outline. A 1 mm per-edge
    sheet-space pad stays fixed while the model scales, as in nearby fit tests.
    """

    PADDING_M = 0.001

    def __init__(self, center):
        self.Position = center
        self.ScaleRatio = (1.0, 1.0)
        self.UseSheetScale = 1

    def GetOutline(self):
        ratio = self.ScaleRatio[0] / self.ScaleRatio[1]
        radius = channel.COIL_OD_MM / 2000.0 * ratio + self.PADDING_M
        x, y = self.Position
        return (x - radius, y - radius, x + radius, y + radius)

    def SetViewPosition(self, position, _update):
        self.Position = tuple(position)
        return True


def test_largest_scale_is_chosen_with_annotation_room_not_the_bare_outer_cell(
    monkeypatch,
):
    monkeypatch.setattr(purchased, "double_array", tuple)
    caption_y = purchased.view_band_bottom("", label="extension scale")
    cells = supplier_state_cells(caption_y, maximum=True)
    fitted = purchased.supplier_fit_cells(
        cells, _EXTENSION_MARGINS, label="extension scale"
    )
    outer_cell = next(cell for cell in cells if cell[0] == "free_right")
    inner_cell = next(cell for cell in fitted if cell[0] == "free_right")
    draw = SimpleNamespace(EditRebuild3=lambda: True)
    bare_view = _CoilEndView(outer_cell[1])
    annotated_view = _CoilEndView(outer_cell[1])

    bare_scale = purchased._fit_group(draw, [(bare_view, outer_cell)])
    annotated_scale = purchased._fit_group(draw, [(annotated_view, inner_cell)])
    ratio = annotated_scale[0] / annotated_scale[1]
    assert bare_scale[0] / bare_scale[1] > ratio

    # Prove maximality from model geometry and fixed padding independently of
    # the fake's GetOutline and the fitter's position/scale readback checks.
    inner = inner_cell[2]
    available_span = min(inner[2] - inner[0], inner[3] - inner[1])
    fitting_ratios = [
        numerator / denominator
        for numerator, denominator in purchased._SCALES
        if channel.COIL_OD_MM / 1000.0 * numerator / denominator
        + 2.0 * _CoilEndView.PADDING_M
        <= available_span
    ]
    assert ratio == max(fitting_ratios)
    assert _contains(inner, annotated_view.GetOutline())
    margins = _EXTENSION_MARGINS["free_right"]
    assert _contains(
        outer_cell[2], _annotation_envelope(annotated_view.GetOutline(), margins)
    )
    assert not _contains(
        outer_cell[2], _annotation_envelope(bare_view.GetOutline(), margins)
    )
