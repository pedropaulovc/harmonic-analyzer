"""Measured spring seats reject unsafe transforms and uncalibrated stations."""

import pytest

import _config
from settled_spring_seats import (
    channel_seat,
    counter_seat,
    counter_upper_support_geometry,
)


@pytest.fixture
def isolated_calibration(monkeypatch):
    channel_record = {
        "amplitude_mm": 0.0,
        "pose": {
            "length_mm": 10.0,
            "lower_eye_xy": [1.0, 2.0],
            "upper_eye_xy": [7.0, 10.0],
            "axis_xy": [0.6, 0.8],
            "centre_xy": [4.0, 6.0],
            "clocking": "standard",
        },
        "final_distance_mm": {"lower": 0.004, "upper": 0.020},
    }
    counter_record = {
        "pose": {
            "length_mm": 12.0,
            "lower_eye_xy": [-3.0, 1.0],
            "upper_eye_xy": [-6.0, 5.0],
            "axis_xy": [-0.6, 0.8],
            "centre_xy": [-4.5, 3.0],
            "clocking": "half_turn",
        },
        "final_distance_mm": {"lower": 0.0, "upper": 0.0},
        "gooseneck_origin_y_mm": 15.0,
        "upper_support": counter_upper_support_geometry(),
    }
    amplitudes = [0.0]
    config = {
        "amplitude": {"preset": "isolated"},
        "springs": {
            "native_distance_guard_mm": 0.010,
            "calibration_resolution_mm": 0.001,
            "channel_seats": [channel_record],
            "presets": {
                "isolated": {
                    "amplitudes_mm": amplitudes,
                    "counter": counter_record,
                }
            },
        },
    }

    def machine(*keys):
        value = config
        for key in keys:
            value = value[key]
        return value

    monkeypatch.setattr(_config, "machine", machine)
    monkeypatch.setattr(_config, "amplitudes", lambda: amplitudes)
    return channel_record, counter_record


def test_unknown_channel_station_is_not_interpolated(isolated_calibration):
    with pytest.raises(ValueError, match="No native spring calibration for amplitude"):
        channel_seat(1.0)


def test_changed_bank_cannot_reuse_a_known_station_or_counter_seat(
    monkeypatch, isolated_calibration
):
    amplitudes = list(_config.amplitudes())
    amplitudes[-1] = 1.0
    monkeypatch.setattr(_config, "amplitudes", lambda: amplitudes)

    for read_seat in (lambda: channel_seat(0.0), counter_seat):
        with pytest.raises(
            ValueError, match="does not match its calibrated amplitude vector"
        ):
            read_seat()


def test_valid_unit_axis_poses_retain_their_native_transform(isolated_calibration):
    channel = channel_seat(0.0)
    counter, _ = counter_seat()

    assert channel.pose.rotation_rows == [
        [0.6, 0.8, 0.0],
        [0.0, 0.0, 1.0],
        [0.8, -0.6, 0.0],
    ]
    assert counter.pose.rotation_rows == [
        [-0.6, 0.8, 0.0],
        [0.0, 0.0, -1.0],
        [-0.8, -0.6, 0.0],
    ]


def test_maximum_distance_uses_guard_or_measured_resolution_bound(
    isolated_calibration,
):
    seat = channel_seat(0.0)

    assert seat.lower_maximum_distance_mm == pytest.approx(0.010)
    assert seat.upper_maximum_distance_mm == pytest.approx(0.021)


@pytest.mark.parametrize(
    ("length_mm", "message"),
    [
        (0.0, "length must be positive"),
        (float("inf"), "length must be a finite number"),
    ],
)
def test_nonpositive_or_nonfinite_pose_length_is_rejected(
    isolated_calibration, length_mm, message
):
    channel_record, _ = isolated_calibration
    channel_record["pose"]["length_mm"] = length_mm

    with pytest.raises(ValueError, match=message):
        channel_seat(0.0)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("lower_eye_xy", [1.0]),
        ("upper_eye_xy", [1.0, 2.0, 3.0]),
        ("axis_xy", [1.0, float("nan")]),
        ("centre_xy", ["0.0", 1.0]),
    ],
)
def test_every_pose_xy_vector_requires_exactly_two_finite_numbers(
    isolated_calibration, field, value
):
    channel_record, _ = isolated_calibration
    channel_record["pose"][field] = value

    with pytest.raises(ValueError, match=f"{field} must contain exactly two"):
        channel_seat(0.0)


def test_axis_outside_strict_unit_tolerance_is_rejected(isolated_calibration):
    channel_record, _ = isolated_calibration
    channel_record["pose"]["axis_xy"] = [1.000000000002, 0.0]

    with pytest.raises(ValueError, match="axis_xy must be unit length"):
        channel_seat(0.0)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("centre_xy", [4.0, 6.001], "centre_xy must match the eye-point midpoint"),
        (
            "axis_xy",
            [-0.6, -0.8],
            "axis_xy must be parallel and co-directed with the eye-point vector",
        ),
    ],
)
def test_pose_metadata_must_describe_its_eye_points(
    isolated_calibration, field, value, message
):
    channel_record, _ = isolated_calibration
    channel_record["pose"][field] = value

    with pytest.raises(ValueError, match=message):
        channel_seat(0.0)


def test_unknown_clocking_literal_is_rejected(isolated_calibration):
    channel_record, _ = isolated_calibration
    channel_record["pose"]["clocking"] = "standrad"

    with pytest.raises(ValueError, match="clocking must be 'standard' or 'half_turn'"):
        channel_seat(0.0)


def test_channel_requires_standard_clocking(isolated_calibration):
    channel_record, _ = isolated_calibration
    channel_record["pose"]["clocking"] = "half_turn"

    with pytest.raises(ValueError, match="clocking must be 'standard'"):
        channel_seat(0.0)


def test_counter_requires_half_turn_clocking(isolated_calibration):
    _, counter_record = isolated_calibration
    counter_record["pose"]["clocking"] = "standard"

    with pytest.raises(ValueError, match="clocking must be 'half_turn'"):
        counter_seat()


@pytest.mark.parametrize("gooseneck_y", [float("nan"), float("inf")])
def test_counter_rejects_nonfinite_gooseneck_origin(isolated_calibration, gooseneck_y):
    _, counter_record = isolated_calibration
    counter_record["gooseneck_origin_y_mm"] = gooseneck_y

    with pytest.raises(
        ValueError, match="gooseneck_origin_y_mm must be a finite number"
    ):
        counter_seat()


def test_production_old_counter_record_cannot_certify_the_made_support(monkeypatch):
    presets = _config.machine("springs", "presets")
    machine = _config.machine
    for name, preset in presets.items():
        # Read the historical measured record itself, not a fabricated bad pose.
        assert (
            preset["counter"].get("upper_support") != counter_upper_support_geometry()
        )

        def selected_machine(*keys):
            if keys == ("amplitude", "preset"):
                return name
            return machine(*keys)

        monkeypatch.setattr(_config, "machine", selected_machine)
        monkeypatch.setattr(_config, "amplitudes", lambda: preset["amplitudes_mm"])
        with pytest.raises(ValueError, match="Stale counter native calibration"):
            counter_seat()


def test_isolated_counter_provenance_identifies_the_whole_made_support(
    isolated_calibration,
):
    _, record = isolated_calibration
    support = record["upper_support"]
    assert support["component"] == "sm-gooseneck-spring-screw"
    assert support["number"] == "MHA-SM-004"
    assert "sku" not in support
    assert support["major_dia_mm"] == pytest.approx(3.5052)
    assert support["underhead_length_mm"] == 16.0
    assert support["head_dia_mm"] == 12.5
    assert support["head_height_mm"] == 7.0
    assert support["crown_rise_mm"] == 1.0
    assert support["slot_width_mm"] == 1.6
    assert support["slot_depth_mm"] == 3.0
    assert support["relief_dia_mm"] == 2.2
    assert support["relief_width_mm"] == 2.2
    assert support["relief_lead_mm"] == 0.3
    assert support["tip_chamfer_mm"] == 0.3
    assert support["plug_length_mm"] == 8.0
    counter_seat()


@pytest.mark.parametrize(
    "field",
    [
        "major_dia_mm",
        "underhead_length_mm",
        "head_dia_mm",
        "head_height_mm",
        "crown_rise_mm",
        "slot_width_mm",
        "slot_depth_mm",
        "relief_dia_mm",
        "relief_width_mm",
        "relief_lead_mm",
        "tip_chamfer_mm",
        "clamp_gap_mm",
        "plug_length_mm",
    ],
)
def test_changed_support_geometry_cannot_reuse_a_native_certificate(
    isolated_calibration,
    field,
):
    _, record = isolated_calibration
    record["upper_support"][field] += 0.01
    with pytest.raises(ValueError, match="Stale counter native calibration"):
        counter_seat()
