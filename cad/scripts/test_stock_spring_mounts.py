"""Physical mounting regressions for the purchased springs."""

from dataclasses import replace

import pytest

import _config

import build_ch_channel_assembly as channel
import ch_vn_channel_spring_stock_geom as channel_stock
import sm_gooseneck_geom
import spring_mount_geom
import sm_summing_lever_spec as lever
from stock_anchor_geom import ANCHOR_9489T111 as anchor


def test_uniform_plate_preserves_anchor_and_nut_installation_coordinates() -> None:
    """Thickening downward must not lift a spring or move any channel seat."""
    assert spring_mount_geom.KNIFE == (-15.0, 979.7)
    assert spring_mount_geom.PLATE_TOP_Y == pytest.approx(982.24)
    assert spring_mount_geom.PLATE_BOTTOM_Y == pytest.approx(975.24)
    assert (
        spring_mount_geom.PLATE_TOP_Y - spring_mount_geom.PLATE_BOTTOM_Y
    ) == pytest.approx(lever.COEFFICIENT_T)
    assert spring_mount_geom.CHANNEL_ANCHOR_XY == pytest.approx((24.85, 991.765))
    assert (
        spring_mount_geom.CHANNEL_ANCHOR_XY[1] + anchor.thread_start_y_mm
    ) == pytest.approx(spring_mount_geom.PLATE_TOP_Y)
    assert channel.CHANNEL_ANCHOR_NUT_XY == pytest.approx((24.85, 975.24))
    # The nut's bearing face is local z=0; +Z must still point downward.
    assert channel.CHANNEL_ANCHOR_NUT_ROWS[2] == [0.0, -1.0, 0.0]
    assert lever.HOLE_COUNT == 20
    for index in range(lever.HOLE_COUNT):
        station = channel.z_station(index) + channel.ARM_MID_DZ
        assert station == pytest.approx(-70.62825 + 7.0565 * index)
        assert station == pytest.approx(lever.HOLE_Z_FIRST + lever.CHANNEL_PITCH * index)


def test_counter_leading_half_turn_clears_tube_and_head() -> None:
    """The extra half-turn must face the open side, not penetrate the tube."""
    pose = spring_mount_geom.COUNTER_REFERENCE_POSE
    screw_y = spring_mount_geom.GOOSENECK_ORIGIN_Y + sm_gooseneck_geom.ARM_Y
    tube_gap, head_gap = spring_mount_geom.counter_half_turn_clearances(pose, screw_y)
    assert tube_gap >= spring_mount_geom.MIN_CLEARANCE_MM
    assert head_gap >= spring_mount_geom.MIN_CLEARANCE_MM


def test_counter_upper_eye_bears_on_full_thread_and_clears_the_tube() -> None:
    """The MHA-SM-04 shank supports the plumb eye on its full-thread major."""
    import build_sm_summing_assembly as summing
    import sm_gooseneck_spring_screw_geom as spring_screw

    pose = spring_mount_geom.COUNTER_REFERENCE_POSE
    assert pose.axis_xy[1] == pytest.approx(1.0, abs=1e-6)
    assert spring_mount_geom.counter_upper_support_offset(
        pose.axis_xy
    ) == pytest.approx(2.9972, abs=1e-4)
    assert sm_gooseneck_geom.SPRING_EYE_GAP == pytest.approx(4.88061)
    assert spring_mount_geom.COUNTER_UPPER_EYE_X == pytest.approx(
        spring_mount_geom.COLUMN_X - sm_gooseneck_geom.SPRING_EYE_X
    )
    assert (
        spring_screw.LENGTH
        > sm_gooseneck_geom.SPRING_EYE_GAP + sm_gooseneck_geom.PLUG_LENGTH
    )
    summing._assert_counter_spring_top_hang(pose, spring_mount_geom.GOOSENECK_ORIGIN_Y)
    # The screw frame's head (+Z) points outboard (machine +X), so its shank
    # runs into the plug.
    assert summing.ROT_Y_POS90[2] == [1.0, 0.0, 0.0]


def test_bank_balance_uses_each_configured_station_force_and_moment() -> None:
    """A heterogeneous nonzero bank cannot collapse to neutral force times 20."""
    neutral = spring_mount_geom.solve_bank_balance([0.0] * 20)
    fundamental = float(_config.machine("amplitude", "fundamental_station_mm"))
    heterogeneous = [
        fundamental / harmonic if harmonic % 2 else 0.0
        for harmonic in range(1, 21)
    ]
    loaded = spring_mount_geom.solve_bank_balance(heterogeneous)

    assert loaded.stations_mm == pytest.approx(heterogeneous)
    assert loaded.channel_force_sum_n != pytest.approx(neutral.channel_force_sum_n)
    assert loaded.channel_moment_n_mm != pytest.approx(neutral.channel_moment_n_mm)
    assert loaded.counter_pose is not None
    assert neutral.counter_pose is not None
    assert loaded.counter_pose.length_mm != pytest.approx(
        neutral.counter_pose.length_mm
    )

    configured = spring_mount_geom.solve_bank_balance(_config.amplitudes())
    assert configured.counter_pose is not None
    assert configured.counter_pose.length_mm == pytest.approx(
        spring_mount_geom.COUNTER_REFERENCE_POSE.length_mm
    )


def test_native_mount_keeps_clearance_gates_without_requiring_analytic_tangency() -> None:
    seed = spring_mount_geom.channel_pose(0.0)
    # Move only the upper seat down its pull axis, consistently shortening the
    # spring to represent a non-analytic installed pose.
    correction_mm = 0.01
    upper = tuple(
        seed.upper_eye_xy[k] - correction_mm * seed.axis_xy[k] for k in range(2)
    )
    corrected = replace(
        seed,
        length_mm=seed.length_mm - correction_mm,
        upper_eye_xy=upper,
        centre_xy=tuple((seed.lower_eye_xy[k] + upper[k]) / 2 for k in range(2)),
    )
    channel._assert_spring_mount(corrected, 0.0, state="native_seated")
    with pytest.raises(RuntimeError, match="loaded bore margin"):
        channel._assert_spring_mount(corrected, 0.0, state="catalog_seed")

    # Translate the same consistent pose until its lower hook has only 0.2 mm
    # plate clearance. Native seating must not bypass the real 0.3 mm minimum.
    bottom = (
        corrected.lower_eye_xy[1]
        - corrected.axis_xy[1] * channel_stock.COIL_MEAN_RADIUS_MM
        - channel_stock.WIRE_DIA_MM / 2
    )
    drop = bottom - (spring_mount_geom.PLATE_TOP_Y + 0.2)
    below_plate_clearance = replace(
        corrected,
        lower_eye_xy=(corrected.lower_eye_xy[0], corrected.lower_eye_xy[1] - drop),
        upper_eye_xy=(corrected.upper_eye_xy[0], corrected.upper_eye_xy[1] - drop),
        centre_xy=(corrected.centre_xy[0], corrected.centre_xy[1] - drop),
    )
    with pytest.raises(RuntimeError, match="lower hook enters the summing plate"):
        channel._assert_spring_mount(below_plate_clearance, 0.0, state="native_seated")
