"""SolidWorks-free frame retention and cap-seat contracts."""

from __future__ import annotations

import math

import build_fr_frame_assembly as frame
import fr_top_frame_spec as top_frame_spec
import fr_vn_frame_cross_screw_spec as cross_screw
from fr_vn_tube_frame_cap_spec import INSIDE_HEIGHT, TOTAL_HEIGHT


def test_cross_screws_clear_tubes_and_engage_both_casting_sides() -> None:
    assert frame.CROSS_SCREW_SHANK_LEN == cross_screw.SHANK_LEN == 44.45
    assert frame.CROSS_SCREW_THREAD == cross_screw.THREAD == "#10-32"
    assert cross_screw.THREAD_CLASS == "2A"
    assert frame.BASE_CROSS_TAP_SPEC.thread_class == "2B"
    assert frame.TOP_CROSS_TAP_SPEC.thread_class == "2B"
    assert frame.BASE_CROSS_TAP_SPEC.kind == "tapped_bottoming"
    assert frame.TOP_CROSS_TAP_SPEC.kind == "tapped_bottoming"
    assert frame.TUBE_CROSS_HOLE_DIAMETER > cross_screw.SHANK_DIA
    # About .42 of far casting: column line - 1.004/2 socket - (5.236 - 1.750);
    # 10.705 at the 112.0 column line, 10.719 once it snaps to 4.410.
    assert math.isclose(frame.BASE_FAR_CASTING_ENGAGEMENT, 10.71, abs_tol=0.015)
    assert (
        min(
            frame.BASE_FAR_CASTING_ENGAGEMENT,
            frame.TOP_FAR_CASTING_ENGAGEMENT,
        )
        >= cross_screw.SHANK_DIA
    )
    # 1.81 full thread past the 1.750 shank: .060.
    assert math.isclose(frame.CROSS_SCREW_THREAD_RESERVE, 0.060 * 25.4, abs_tol=1e-9)


def _printed_mm(value_mm: float, places: int) -> float:
    """``value_mm`` as the inch sheet prints it at ``places``, in mm."""
    return round(value_mm / 25.4, places) * 25.4


def test_upper_stock_screw_keeps_casting_engagement_at_the_printed_bands() -> None:
    floor_places = top_frame_spec.DRAWING_REFERENCE_PRECISION[
        "counterbore floor from socket axis"
    ]
    bore_places = top_frame_spec.DRAWING_PRECISION["BoreProfile"]["B0Dia"]
    max_floor_offset = (
        _printed_mm(frame.TOP_SCREW_SEAT_Z - abs(frame.REAR_COLUMN_Z), floor_places)
        + top_frame_spec.PRINTED_LINEAR_BAND_MM[floor_places]
    )
    max_bore_radius = (
        _printed_mm(frame.COLUMN_SOCKET_DIAMETER, bore_places)
        + top_frame_spec.PRINTED_LINEAR_BAND_MM[bore_places]
    ) / 2.0
    minimum_engagement = cross_screw.SHANK_LEN - max_floor_offset - max_bore_radius
    # drawing-guidelines.md rule 17 (walls and webs): the flush counterbore floor still leaves 1.5D of far thread.
    assert minimum_engagement >= 1.5 * cross_screw.SHANK_DIA
    full_thread = frame.TOP_CROSS_TAP_SPEC.overrides_mm["ThreadDepth"]
    # The thread depth prints .XX (1.81): .050 of reserve past the shank tip.
    minimum_thread_reserve = (
        full_thread - top_frame_spec.PRINTED_LINEAR_BAND_MM[2] - cross_screw.SHANK_LEN
    )
    assert math.isclose(minimum_thread_reserve, 0.050 * 25.4, abs_tol=1e-9)
    assert minimum_thread_reserve >= 0.25


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
