"""Pure sheet-space thumb lanes and the recorded native v3 containment failure.

These projections exercise the production layout arithmetic, not COM or an
assertion that restored anchors alone prove the next native sheet's ink fits.
"""

from __future__ import annotations

import pytest

import _mcmaster_91882a221 as source
import _purchased_fastener_drawing as purchased
import draw_vn_thumb_screw as drawing


# Worker15, source 9fc9097a7, drawing:vn_thumb_screw final settled refusal.
# This is complete display ink, NOT the annotation anchor or a displacement.
_V3_THREAD_INK = (0.0930195, 0.0694105, 0.148582, 0.1192704)
_V3_FRONT_CELL = (0.025, 0.077, 0.205, 0.182)


def _projection(cell, scale=5.0):
    # An exact rigid model-to-sheet projection centred in the reserved geometry
    # cell. Native outline padding is deliberately not treated as model geometry.
    margins = drawing.SUPPLIER_MARGINS["*Front"]
    x = (cell[0] + margins[0] + cell[2] - margins[2]) / 2.0
    y = (cell[1] + margins[1] + cell[3] - margins[3]) / 2.0
    origin_x = x - source.OVERALL_LEN / 2000.0 * scale
    axis = [
        (origin_x + station / 1000.0 * scale, y)
        for station in (0.0, source.HEAD_H, source.HEAD_STACK_LEN, source.OVERALL_LEN)
    ]
    head_rim = [
        (origin_x, y + radius / 1000.0 * scale)
        for radius in (-source.HEAD_DIA / 2.0, source.HEAD_DIA / 2.0)
    ]
    return axis, head_rim


@pytest.mark.parametrize("note_count", range(4))
@pytest.mark.parametrize("scale", (2.0, 4.0, 5.0))
def test_all_six_thumb_lanes_fit_the_actual_footer_dependent_cell(note_count, scale):
    notes = "\n".join(f"NOTE {index}" for index in range(note_count))
    cell = next(
        bounds
        for name, _, bounds in purchased.fastener_view_cells(
            purchased.view_band_bottom(notes, label="thumb layout")
        )
        if name == "*Front"
    )
    axis, head_rim = _projection(cell, scale)
    positions = drawing._supplier_dimension_positions(axis, head_rim, cell)
    assert set(positions) == {
        "head_height",
        "collar_height",
        "thread_length",
        "head_diameter",
        "collar_diameter",
        "thread_diameter",
    }
    assert all(
        cell[0] < x < cell[2] and cell[1] < y < cell[3] for x, y in positions.values()
    )
    bottom, top = sorted(point[1] for point in head_rim)
    assert top < positions["head_height"][1] < positions["collar_height"][1]
    assert positions["thread_length"][1] < bottom
    assert positions["head_diameter"][0] < axis[0][0]
    assert (
        axis[-1][0] < positions["thread_diameter"][0] < positions["collar_diameter"][0]
    )
    for name, start, end in (
        ("head_height", 0, 1),
        ("collar_height", 1, 2),
        ("thread_length", 2, 3),
    ):
        assert axis[start][0] < positions[name][0] < axis[end][0]


def test_thumb_lanes_follow_the_projected_frame_not_a_presumed_view_center():
    axis, rim = _projection(_V3_FRONT_CELL)
    initial = drawing._supplier_dimension_positions(axis, rim, _V3_FRONT_CELL)
    dx, dy = 0.017, -0.021
    shifted_axis = [(x + dx, y + dy) for x, y in axis]
    shifted_rim = [(x + dx, y + dy) for x, y in rim]
    cell = tuple(
        value + (dx if index % 2 == 0 else dy)
        for index, value in enumerate(_V3_FRONT_CELL)
    )
    shifted = drawing._supplier_dimension_positions(shifted_axis, shifted_rim, cell)
    for name, (x, y) in initial.items():
        assert shifted[name] == pytest.approx((x + dx, y + dy))


@pytest.mark.parametrize("edge", range(4))
def test_thumb_plan_refuses_overrun_on_every_reserved_edge(edge):
    axis, rim = _projection(_V3_FRONT_CELL)
    left, bottom, right, top = drawing.SUPPLIER_MARGINS["*Front"]
    tight_cell = [
        axis[0][0] - left,
        rim[0][1] - bottom,
        axis[-1][0] + right,
        rim[-1][1] + top,
    ]
    drawing._supplier_dimension_positions(axis, rim, tuple(tight_cell))
    tight_cell[edge] += 0.000002 if edge < 2 else -0.000002
    with pytest.raises(RuntimeError, match="lanes leave the actual Front cell"):
        drawing._supplier_dimension_positions(axis, rim, tuple(tight_cell))


def test_recorded_v3_ink_remains_rejected_even_with_a_valid_six_lane_plan():
    axis, rim = _projection(_V3_FRONT_CELL)
    positions = drawing._supplier_dimension_positions(axis, rim, _V3_FRONT_CELL)
    # A valid planned anchor cannot stand in for the complete settled display.
    # Preserve the production containment predicate and replay the actual escape;
    # this is not a translated-box claim of native after-fix success.
    assert positions["thread_length"][1] > _V3_FRONT_CELL[1]
    assert _V3_FRONT_CELL[1] - _V3_THREAD_INK[1] == pytest.approx(0.0075895)
    assert not purchased._inside(_V3_THREAD_INK, _V3_FRONT_CELL)
