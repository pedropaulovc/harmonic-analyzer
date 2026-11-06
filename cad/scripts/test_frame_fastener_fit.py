"""SolidWorks-free frame retention and cap-seat contracts."""

from __future__ import annotations

import math

import pytest

import build_fr_frame_assembly as frame
import build_fr_top_frame as top_frame
import fr_frame_cross_screw as joint
import fr_harmonic_base_fasteners as base_fasteners
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


def test_near_wall_clearance_passes_a_standard_tap_and_guides_the_tube_drill() -> None:
    # Owner ruling 2026-11-05 (both castings): the near casting wall is #10
    # close clearance, wide enough for a standard 10-32 tap shank to reach
    # the far wall and to guide the tube's match drill.
    assert joint.NEAR_WALL_CLEARANCE_DIAMETER == 5.232
    assert joint.NEAR_WALL_CLEARANCE_DIAMETER > joint.STANDARD_10_32_TAP_SHANK_DIAMETER
    assert joint.NEAR_WALL_CLEARANCE_DIAMETER >= frame.TUBE_CROSS_HOLE_DIAMETER
    assert joint.NEAR_WALL_CLEARANCE_DIAMETER > cross_screw.SHANK_DIA
    for spec in (
        base_fasteners.BASE_CROSS_CLEARANCE_SPEC,
        top_frame.SIDE_CLEARANCE_SPEC,
    ):
        assert (spec.kind, spec.size, spec.fit, spec.end) == (
            "clearance",
            joint.NEAR_WALL_CLEARANCE_SIZE,
            joint.NEAR_WALL_CLEARANCE_FIT,
            "blind",
        )


def test_far_wall_engagement_books_the_shortest_screw_and_its_tip() -> None:
    # B18.6.3 -.06 length, 0.7P nominal tip (dt_swing_stop precedent).
    reach = 44.45 - 0.06 * 25.4 - 0.7 * 25.4 / 32.0
    assert joint.far_wall_full_thread_min_mm(10.0) == pytest.approx(reach - 10.0)
    assert joint.far_wall_full_thread_min_mm(
        10.0, tip_loss_mm=1.5 * joint.CROSS_SCREW_PITCH
    ) == pytest.approx(reach + (0.7 - 1.5) * 25.4 / 32.0 - 10.0)
    # The socket may be match-bored to Ø26.0; the far mouth takes .010.
    assert joint.far_wall_start_max_mm(10.0, unit="in") == pytest.approx(
        10.0 + 13.0 + 0.254
    )
    assert joint.FAR_WALL_ENGAGEMENT_FLOOR_MM == pytest.approx(
        1.5 * cross_screw.SHANK_DIA
    )


def test_base_cross_screws_engage_the_far_wall() -> None:
    # Front and rear differ by the front chain's .XX top width; the front
    # starts the far wall farther out and governs at 7.50 (1.55D).
    front = base_fasteners.base_cross_screw_far_wall_start_max_mm(front=True)
    rear = base_fasteners.base_cross_screw_far_wall_start_max_mm(front=False)
    assert front > rear
    engagement = joint.far_wall_full_thread_min_mm(front)
    assert engagement == base_fasteners.BASE_CROSS_SCREW_FAR_WALL_MIN_ENGAGEMENT
    assert engagement >= joint.FAR_WALL_ENGAGEMENT_FLOOR_MM
    assert math.isclose(engagement, 7.501, abs_tol=0.005)
    # 1.42D at a 1.5-pitch tip: MHA-FR-00 check 2 catches a short tip.
    assert math.isclose(
        joint.far_wall_full_thread_min_mm(
            front, tip_loss_mm=1.5 * joint.CROSS_SCREW_PITCH
        ),
        6.866,
        abs_tol=0.005,
    )


def test_top_cross_screws_engage_the_far_wall() -> None:
    # Every MHA-FR-02 floor is located .XX from its own socket axis.
    floor_places = top_frame_spec.DRAWING_REFERENCE_PRECISION[
        "counterbore floor from socket axis"
    ]
    max_floor_offset = (
        _printed_mm(frame.TOP_SCREW_SEAT_Z - abs(frame.REAR_COLUMN_Z), floor_places)
        + top_frame_spec.PRINTED_LINEAR_BAND_MM[floor_places]
    )
    start = joint.far_wall_start_max_mm(max_floor_offset, unit=top_frame_spec.UNIT)
    assert start == pytest.approx(top_frame.TOP_CROSS_SCREW_FAR_WALL_START_MAX)
    engagement = top_frame.TOP_CROSS_SCREW_FAR_WALL_MIN_ENGAGEMENT
    assert engagement == pytest.approx(joint.far_wall_full_thread_min_mm(start))
    assert math.isclose(engagement, 12.352, abs_tol=0.005)  # 2.56D
    assert engagement >= joint.FAR_WALL_ENGAGEMENT_FLOOR_MM
    assert math.isclose(
        joint.far_wall_full_thread_min_mm(
            start, tip_loss_mm=1.5 * joint.CROSS_SCREW_PITCH
        ),
        11.717,
        abs_tol=0.005,
    )  # 2.43D
    # The screw still seats before the tip meets the far tap's end: the
    # thread depth prints .XX (1.81), .050 of reserve past the shank tip.
    full_thread = frame.TOP_CROSS_TAP_SPEC.overrides_mm["ThreadDepth"]
    minimum_thread_reserve = (
        full_thread - top_frame_spec.PRINTED_LINEAR_BAND_MM[2] - cross_screw.SHANK_LEN
    )
    assert math.isclose(minimum_thread_reserve, 0.050 * 25.4, abs_tol=1e-9)


def test_assembly_check_accepts_every_installed_screw_on_far_wall_engagement() -> None:
    # The 0.7P tip allowance is nominal (dt_swing_stop precedent): MHA-FR-00
    # accepts each installed joint, upper and lower, at 1.5D of full-form
    # far-wall engagement, a ratio of the screw with no dimension in the note.
    import draw_fr_frame_assembly as assembly_sheet

    assert joint.CROSS_SCREW_ENGAGEMENT_CHECK == (
        "FULL-FORM THREAD ENGAGEMENT OF AT LEAST 1.5 SCREW DIAMETERS"
    )
    checks = " ".join(
        line.strip() for line in assembly_sheet.ASSEMBLY_CHECKS.splitlines()
    )
    assert (
        f"VERIFY EACH SCREW HAS {joint.CROSS_SCREW_ENGAGEMENT_CHECK} "
        "IN THE FAR WALL OF ITS MHA-FR-01 OR MHA-FR-02 CASTING."
    ) in checks
    assert "THREAD SEGMENTS" not in checks
    steps = " ".join(
        line.strip() for line in assembly_sheet.ASSEMBLY_STEPS.splitlines()
    )
    assert "5. THROUGH THE MHA-FR-02 NEAR-WALL CLEARANCES, PILOT-TRANSFER" in steps
    assert steps.count("PROTECT THE FAR-WALL THREAD") == 2
    assert "BOTH THREAD SEGMENTS" not in steps


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
