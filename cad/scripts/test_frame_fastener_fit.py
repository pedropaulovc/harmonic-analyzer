"""SolidWorks-free frame retention and cap-seat contracts."""

from __future__ import annotations

import math

import build_frame_assembly as frame
import frame_cross_screw_spec as cross_screw
from tube_frame_cap_spec import INSIDE_HEIGHT, TOTAL_HEIGHT


def test_cross_screws_clear_tubes_and_engage_both_casting_sides() -> None:
    assert frame.CROSS_SCREW_SHANK_LEN == cross_screw.SHANK_LEN == 44.45
    assert frame.CROSS_SCREW_THREAD == cross_screw.THREAD == "#10-32"
    assert cross_screw.THREAD_CLASS == "2A"
    assert frame.BASE_CROSS_TAP_SPEC.thread_class == "2B"
    assert frame.TOP_CROSS_TAP_SPEC.thread_class == "2B"
    assert frame.BASE_CROSS_TAP_SPEC.kind == "tapped_bottoming"
    assert frame.TOP_CROSS_TAP_SPEC.kind == "tapped_bottoming"
    assert frame.TUBE_CROSS_HOLE_DIAMETER > cross_screw.SHANK_DIA
    assert math.isclose(frame.BASE_FAR_CASTING_ENGAGEMENT, 10.70, abs_tol=1e-9)
    assert math.isclose(frame.TOP_FAR_CASTING_ENGAGEMENT, 6.10, abs_tol=1e-9)
    assert (
        min(
            frame.BASE_FAR_CASTING_ENGAGEMENT,
            frame.TOP_FAR_CASTING_ENGAGEMENT,
        )
        >= cross_screw.SHANK_DIA
    )
    assert math.isclose(frame.CROSS_SCREW_THREAD_RESERVE, 1.55, abs_tol=1e-9)


def test_stock_caps_seat_on_tube_ends_and_preserve_finished_height() -> None:
    assert math.isclose(
        frame.CAP_MOUTH_Y + INSIDE_HEIGHT,
        frame.COLUMN_TOP_Y,
        abs_tol=1e-9,
    )
    assert math.isclose(
        frame.CAP_MOUTH_Y + TOTAL_HEIGHT,
        frame.CAP_TOP_Y,
        abs_tol=1e-9,
    )
