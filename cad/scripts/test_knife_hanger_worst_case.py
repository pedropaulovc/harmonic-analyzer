"""Rule-12 worst case of the #6-32 knife hanger (MHA-VN-024 in MHA-SM-002,
keyed by MHA-VN-051), read from the real spec and assembly constants.

The retired 1/2-13 hanger broke its tap-drill point into the knife bore crown
and needed a drawing exception; every number here is judged at the printed
bands (cad/docs/drawing-simplicity-policy.md rule 12), and the old geometry is
run through the same web formula to prove it discriminates.  SolidWorks-free.
"""

from __future__ import annotations

import pytest

import _interference_contracts
import build_sm_knife_mount
import build_sm_summing_assembly as asm
import fr_top_frame_spec as top_frame
import sm_knife_mount_spec as knife_mount
import vn_knife_hanger_stud_spec as screw
import vn_knife_mount_dowel_spec as dowel
from _hole_spec import TAP_DRILL_MM, THREAD_MAJOR_MM


def test_the_tap_point_leaves_the_web_over_the_bore_crown() -> None:
    assert knife_mount.STUD_TAP_WEB_MIN == 2.0
    # 14.62 - 0.10 - 0.255 - 11.41 - 0.813 at the spec's 14.87 top.
    assert knife_mount.STUD_TAP_WEB_WORST == pytest.approx(2.042, abs=5e-4)
    assert knife_mount.STUD_TAP_WEB_WORST >= knife_mount.STUD_TAP_WEB_MIN
    # The build's exact derived top (14.866) is what gets cut: 2.038.
    built = knife_mount.tap_web_worst(
        build_sm_knife_mount.BLK_TOP,
        knife_mount.STUD_TAP_DRILL_DEPTH,
        knife_mount.STUD_TAP_DIA,
    )
    assert built == pytest.approx(2.038, abs=5e-4)
    assert built >= knife_mount.STUD_TAP_WEB_MIN


def test_the_retired_half_inch_tap_fails_the_same_web_formula() -> None:
    # 1/2-13 x 12.0 blind under the old 14.62 top (MOUNT_GAP 0.25): the drill
    # point broke 0.85 into the crown nominally, -1.71 at the printed bands.
    old = knife_mount.tap_web_worst(14.62, 12.0, TAP_DRILL_MM["1/2-13"])
    assert old == pytest.approx(-1.714, abs=5e-4)
    assert old < knife_mount.STUD_TAP_WEB_MIN


def test_the_screw_reach_holds_engagement_and_stays_in_the_thread() -> None:
    asm._assert_knife_hanger_stack()
    assert asm.MOUNT_GAP == 0.0
    assert asm.HANGER_SEAT_Y == pytest.approx(1029.7)
    assert asm.HANGER_STUD_Y == pytest.approx(991.6)
    assert asm.HANGER_REACH == pytest.approx(8.10)
    assert asm.HANGER_REACH_MIN == pytest.approx(6.284)
    assert asm.HANGER_REACH_MAX == pytest.approx(8.90)
    # Engagement: r_min - P >= 1.5 D, 5.49 >= 5.258.
    assert asm.HANGER_ENGAGEMENT_MIN == pytest.approx(
        asm.HANGER_REACH_MIN - screw.PITCH
    )
    assert asm.HANGER_ENGAGEMENT_MIN == pytest.approx(5.49, abs=5e-3)
    assert asm.HANGER_ENGAGEMENT_FLOOR == pytest.approx(1.5 * screw.SHANK_DIA)
    assert asm.HANGER_ENGAGEMENT_MIN >= asm.HANGER_ENGAGEMENT_FLOOR
    # Tip: r_max under the shallowest full thread, 8.90 <= 9.19 (0.29 clear).
    assert knife_mount.STUD_TAP_THREAD_DEPTH_MIN == pytest.approx(9.19)
    assert asm.HANGER_REACH_MAX <= knife_mount.STUD_TAP_THREAD_DEPTH_MIN
    assert asm.HANGER_TIP_CLEARANCE == pytest.approx(0.29)
    # The partial thread covers the longest reach: 19.05 >= 8.90.
    assert screw.THREAD_LENGTH >= asm.HANGER_REACH_MAX
    # The screw clears the crossbar's #6 hole: 4.318 - 3.505.
    assert asm.HANGER_SCREW_CLEARANCE == pytest.approx(0.813, abs=5e-4)


def test_the_dowel_presses_deep_enough_and_never_bottoms_the_slip_hole() -> None:
    assert dowel.SLIP_DEPTH_CLEARANCE_MIN == pytest.approx(0.596)
    assert dowel.SLIP_DEPTH_CLEARANCE_MIN > 0.0
    assert dowel.PRESS_ENGAGEMENT_D_MIN == pytest.approx(2.60, abs=5e-3)
    assert dowel.PRESS_ENGAGEMENT_D_MIN >= dowel.PRESS_ENGAGEMENT_MIN_D == 1.5
    assert knife_mount.PIN_PRESS_INTERFERENCE[0] > 0.0
    # Both parts' stations are the dowel's, and the assembly seats it there.
    assert knife_mount.PIN_HOLE_X == top_frame.HANGER_PIN_X == dowel.HANGER_OFFSET
    assert asm.KNIFE_DOWEL_X_OFFSET == dowel.HANGER_OFFSET
    assert asm.KNIFE_DOWEL_Y == pytest.approx(
        asm.KNIFE_MOUNT_TOP_Y - knife_mount.PIN_HOLE_DEPTH
    )
    assert top_frame.HANGER_PIN_HOLE_DEPTH == dowel.SLIP_DEPTH


def test_the_slip_band_and_the_screw_float_absorb_the_dowel_stations() -> None:
    assert top_frame.HANGER_PIN_SLIP_CLEARANCE_MIN == pytest.approx(0.02738)
    assert top_frame.HANGER_PIN_SLIP_CLEARANCE_MAX == pytest.approx(0.09246)
    assert 0.02 <= top_frame.HANGER_PIN_SLIP_CLEARANCE_MIN
    assert top_frame.HANGER_PIN_SLIP_CLEARANCE_MAX <= 0.10
    assert top_frame.HANGER_SCREW_FLOAT == pytest.approx(0.4065)
    assert top_frame.HANGER_PIN_MISMATCH_MAX == pytest.approx(0.30623)
    assert top_frame.HANGER_SCREW_FLOAT >= top_frame.HANGER_PIN_MISMATCH_MAX


def test_the_summing_interference_rows_match_their_owners() -> None:
    # _interference_contracts keeps the knife-mount-owned terms as literals.
    assert _interference_contracts._KNIFE_HANGER_REACH == pytest.approx(
        asm.HANGER_REACH
    )
    assert _interference_contracts._KNIFE_DOWEL_HOLE_MIN == pytest.approx(
        knife_mount.PIN_HOLE_DIA + min(knife_mount.PIN_HOLE_DIA_BAND)
    )
    assert screw.THREAD == knife_mount.STUD_THREAD == "#6-32"
    assert THREAD_MAJOR_MM["#6-32"] == knife_mount.STUD_THREAD_MAJOR
    assert TAP_DRILL_MM["#6-32"] == knife_mount.STUD_TAP_DIA
