"""The running-axis geometry of #2473 against the specs that own its inputs."""

from __future__ import annotations

from pathlib import Path

import pytest

import _buildgraph
import cone_line
import cone_running_axis as axis
import cone_set_stack
import cone_tip_cluster as cluster
import dt_cone_gear_shaft_spec as shaft
import dt_cone_gear_spec as cone
import dt_cone_pivot_post_spec as post

IN = 25.4
DT04_TEETH = tuple(t for t in cone.CONE_TEETH if t not in axis.DT37_TEETH)
_RATIO = axis.SPIGOT_ENGAGEMENT_MIN_MM / (
    axis.PIVOT_STATION - axis.SOCKET_MOUTH_STATION
)


def test_the_restated_stations_are_their_owners() -> None:
    """The module imports neither cone_line nor the shaft and post specs, so
    the cone gears' recipes stay off the channel table and those registries
    (test_buildgraph.test_config_files_track_real_reads)."""
    assert axis.POST_STATION == cone_line.POST_STATION
    assert axis.CONE_BOSS_LENGTH_MM == post.CONE_BOSS_LENGTH
    assert axis.BOSS_NORTH_STATION == pytest.approx(
        shaft.JOURNAL_END - shaft.FRONT_STUB
    )
    assert axis.SOCKET_MOUTH_STATION == pytest.approx(shaft.TIP_END_STATION)
    order = sorted(cone.CONE_TEETH, reverse=True)
    for seat, teeth in enumerate(order):
        south, north = shaft.gear_faces(seat)
        shift = cluster.TIP_SET_SHIFT_MM if teeth <= 24 else 0.0
        assert axis.seat_faces(teeth) == pytest.approx((south + shift, north + shift))
    assert axis.seat_faces(24)[1] == pytest.approx(shaft.T024_NORTH_FACE_STATION)
    # The booked engagement is the floor the shaft spec proves it keeps.
    assert axis.SPIGOT_ENGAGEMENT_MIN_MM == cluster.SPIGOT_SOCKET_ENGAGEMENT_MIN_MM
    assert axis.SPIGOT_ENGAGEMENT_MIN_MM <= shaft.SPIGOT_ENGAGEMENT_MIN_MM
    assert shaft.SPIGOT_ENGAGEMENT_MIN_MM < (
        cluster.SPIGOT_LENGTH_MM - 2.0 * cone.FACE_WIDTH - cluster.TIP_END_RECESS_MM
    )
    config = _buildgraph.config_files_of(Path(axis.__file__))
    assert "machine/channels.yaml" not in config
    assert not any(name.startswith("parts/dt-cone-pivot-post") for name in config)


def test_the_pivot_bears_north_of_every_gear_and_the_fulcrum_south_of_them() -> None:
    planes = [axis.seat_plane(t) for t in cone.CONE_TEETH]
    assert axis.BOSS_SOUTH_STATION < axis.BOSS_NORTH_STATION < min(planes)
    south, north = axis.PIVOT_BARE_STATIONS
    assert max(planes) < south < axis.PIVOT_STATION < north
    assert axis.SOCKET_MOUTH_STATION < axis.seat_plane(18) < axis.seat_plane(12)
    # The bare pivot is what stands past MHA-DT-38: .090 in.
    assert north - south == pytest.approx(
        cluster.PIVOT_LENGTH_MM - cluster.BUSHING_LENGTH_MM
    )
    assert north - south == pytest.approx(0.090 * IN)


def test_k_grows_toward_the_tip_and_stays_under_one() -> None:
    ranges = [axis.dt04_k_range(t) for t in sorted(DT04_TEETH, reverse=True)]
    for (lo, hi), (next_lo, next_hi) in zip(ranges, ranges[1:]):
        assert 0.0 < lo < hi < 1.0
        assert next_lo > lo and next_hi > hi
    # T024 sits next to the socket mouth: k 0.81-0.85 (q2473-verify.md).
    lo, hi = axis.dt04_k_range(24)
    assert lo == pytest.approx(0.810, abs=0.005)
    assert hi == pytest.approx(0.849, abs=0.005)
    assert axis.dt04_k_range(24)[1] < axis.K_MOUTH < 1.0


def test_only_dt04_gears_take_k_and_only_dt37_gears_take_a_share() -> None:
    assert axis.DT37_TEETH == (6, 12, 18)
    for teeth in axis.DT37_TEETH:
        with pytest.raises(ValueError):
            axis.dt04_k_range(teeth)
        assert 0.0 < axis.spigot_share(teeth) < 1.0
    with pytest.raises(ValueError):
        axis.spigot_share(24)
    # The share falls toward the pivot.
    assert axis.spigot_share(18) > axis.spigot_share(12) > axis.spigot_share(6)


def test_a_true_pivot_still_leaves_the_spigot_its_tilt() -> None:
    # With the pivot dead true MHA-DT-37 still pivots about it inside the
    # socket's float: the mouth offset u and the inner-end offset (1 + r) u
    # both stay within the float.
    # D51: the spigot's bond opens to .0038, its float half that.
    assert axis.SPIGOT_FLOAT_MM == pytest.approx(0.0019 * IN, abs=1e-4)
    assert axis.spigot_stand_off_mm(0.0) == pytest.approx(
        axis.SPIGOT_FLOAT_MM / (1.0 + _RATIO)
    )
    assert axis.spigot_stand_off_mm(0.0) < axis.SPIGOT_FLOAT_MM


@pytest.mark.parametrize("pivot_offset", (0.0, 0.01, 0.0254, 0.05))
def test_the_stand_off_is_the_worst_spigot_pose_in_the_socket(
    pivot_offset: float,
) -> None:
    # Brute force over the mouth offset u, along the pivot's offset and
    # against it: the inner end v = (1 + r) u - r p must stay in the float.
    s = axis.SPIGOT_FLOAT_MM
    worst = 0.0
    steps = 4000
    for i in range(-steps, steps + 1):
        u = s * i / steps
        if abs((1.0 + _RATIO) * u - _RATIO * pivot_offset) <= s + 1e-12:
            worst = max(worst, abs(u - axis.K_MOUTH * pivot_offset))
    booked = axis.spigot_stand_off_mm(pivot_offset)
    assert worst <= booked + 1e-12
    assert worst == pytest.approx(booked, abs=2 * s / steps)


def test_a_shorter_engagement_tilts_more(monkeypatch: pytest.MonkeyPatch) -> None:
    booked = axis.spigot_stand_off_mm(0.0254)
    nominal = (
        cluster.SPIGOT_LENGTH_MM - 2.0 * cone.FACE_WIDTH - cluster.TIP_END_RECESS_MM
    )
    monkeypatch.setattr(
        axis,
        "_ENGAGEMENT_RATIO",
        nominal / (axis.PIVOT_STATION - axis.SOCKET_MOUTH_STATION),
    )
    assert axis.spigot_stand_off_mm(0.0254) < booked


@pytest.mark.parametrize("teeth", cone.CONE_TEETH)
def test_the_stack_books_each_axis_offset_at_the_read_pivot_limit(teeth: int) -> None:
    pivot_offset = cone_set_stack.PIVOT_RUNOUT_TIR_MM / 2.0
    if teeth in cone_set_stack.ASSEMBLED_RUNOUT_TIR_MM:
        # Read after cure about the journal: the journal axis's own offset
        # from the running axis at the gear's plane, wherever it is seated.
        offset = axis.journal_axis_offset_mm(teeth, pivot_offset)
        assert offset == pytest.approx(
            axis.k_range(axis.seat_plane(teeth))[1] * pivot_offset
        )
        assert cone_set_stack.seat_eccentricity_mm(teeth) == pytest.approx(
            cone_set_stack.ASSEMBLED_RUNOUT_TIR_MM[teeth] / 2.0
        )
    elif teeth in axis.DT37_TEETH:
        offset = axis.seat_offset_mm(teeth, pivot_offset)
        assert offset == pytest.approx(
            axis.spigot_share(teeth) * axis.spigot_stand_off_mm(pivot_offset)
        )
    else:
        offset = axis.seat_offset_mm(teeth, pivot_offset)
        assert offset == pytest.approx(axis.dt04_k_range(teeth)[1] * pivot_offset)
        assert offset == pytest.approx(axis.journal_axis_offset_mm(teeth, pivot_offset))
    assert 0.0 < offset < pivot_offset
    assert cone_set_stack.cone_eccentricity_mm(teeth) == pytest.approx(
        cone_set_stack.seat_eccentricity_mm(teeth) + offset
    )


def test_only_t006_is_left_to_the_tilt_model() -> None:
    unread = [
        t for t in axis.DT37_TEETH if t not in cone_set_stack.ASSEMBLED_RUNOUT_TIR_MM
    ]
    assert unread == [6]
    assert sorted(cone_set_stack.ASSEMBLED_RUNOUT_TIR_MM) == [12, 18, 24]
