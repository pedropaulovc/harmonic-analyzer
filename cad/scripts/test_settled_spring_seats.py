"""Measured spring seats reject unsafe transforms and uncalibrated stations."""

import ast
from pathlib import Path

import pytest

import _config
import settled_spring_seats
from settled_spring_seats import (
    channel_seat,
    counter_seat,
    counter_upper_support_geometry,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = Path(__file__).resolve().parent
_ACCEPT_STALE = "accept_stale_counter_record_for_recalibration"


@pytest.fixture(autouse=True)
def strict_stale_counter(monkeypatch):
    # Importing diagnostics/calibrate_spring_seats.py anywhere in this process
    # (test_seat_search does) sets the recalibration bypass; every test here
    # starts from, and restores, the module's own default.
    monkeypatch.setattr(
        settled_spring_seats, "_ACCEPT_STALE_COUNTER_FOR_RECALIBRATION", False
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


def test_counter_record_without_support_certificate_is_rejected(isolated_calibration):
    # A record measured before the made support existed carries no
    # upper_support at all; it must not certify the MHA-SM-04 clamp.
    _, counter_record = isolated_calibration
    del counter_record["upper_support"]

    with pytest.raises(ValueError, match="Stale counter native calibration"):
        counter_seat()


def test_counter_record_tagged_for_another_support_is_rejected(isolated_calibration):
    _, counter_record = isolated_calibration
    counter_record["upper_support"] = {
        **counter_upper_support_geometry(),
        "component": "sm-gooseneck",
        "number": "MHA-SM-01",
    }

    with pytest.raises(ValueError, match="Stale counter native calibration"):
        counter_seat()


def test_isolated_counter_provenance_identifies_the_whole_made_support(
    isolated_calibration,
):
    _, record = isolated_calibration
    support = record["upper_support"]
    assert support["component"] == "sm-gooseneck-spring-screw"
    assert support["number"] == "MHA-SM-04"
    assert "sku" not in support
    assert support["thread"] == "#8-32 UNC"
    assert support["major_dia_mm"] == pytest.approx(4.1656)
    assert support["underhead_length_mm"] == 16.0
    assert support["head_dia_mm"] == 12.5
    assert support["head_height_mm"] == 7.0
    assert support["crown_rise_mm"] == 1.0
    assert support["slot_width_mm"] == 1.6
    assert support["slot_depth_mm"] == 3.0
    assert support["seat_dia_mm"] == 3.5
    assert support["shoulder_length_mm"] == 3.9
    assert not any(key.startswith("relief_") for key in support)
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
        "seat_dia_mm",
        "shoulder_length_mm",
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


def _stale(record: dict) -> None:
    record["upper_support"] = {
        **counter_upper_support_geometry(),
        "thread": "#6-32 UNC",
    }


def test_stale_counter_record_still_raises_by_default(isolated_calibration):
    _, record = isolated_calibration
    _stale(record)
    with pytest.raises(ValueError, match="Stale counter native calibration"):
        counter_seat()


def test_recalibration_bypass_returns_the_stored_stale_record(isolated_calibration):
    _, record = isolated_calibration
    _stale(record)
    settled_spring_seats.accept_stale_counter_record_for_recalibration()

    seat, gooseneck_y = counter_seat()

    assert seat.pose.upper_eye_xy == (-6.0, 5.0)
    assert seat.pose.clocking == "half_turn"
    assert gooseneck_y == 15.0


def _references_bypass(path: Path) -> bool:
    """True when ``path`` names the bypass as an identifier, attribute, import,
    definition or bare string (``getattr``); docstrings and comments do not."""
    source = path.read_bytes()
    if _ACCEPT_STALE.encode() not in source:
        return False
    return any(
        _ACCEPT_STALE
        in (
            getattr(node, "id", None),
            getattr(node, "attr", None),
            node.name if isinstance(node, (ast.alias, ast.FunctionDef)) else None,
            node.value if isinstance(node, ast.Constant) else None,
        )
        for node in ast.walk(ast.parse(source))
    )


def _python_sources():
    pruned = {"node_modules", "__pycache__", "SolidworksMCP-python", "out"}
    for root, dirs, files in REPO_ROOT.walk():
        dirs[:] = [d for d in dirs if d not in pruned and not d.startswith(".")]
        yield from (root / name for name in files if name.endswith(".py"))


def test_only_the_calibrator_may_accept_a_stale_counter_record():
    owner = SCRIPTS / "settled_spring_seats.py"
    calibrator = SCRIPTS / "diagnostics" / "calibrate_spring_seats.py"
    this_test = Path(__file__).resolve()
    referencing = {
        path.resolve()
        for path in _python_sources()
        if path.resolve() != this_test and _references_bypass(path)
    }
    # Anchors: each allowed source must still be found, or the scan proves nothing.
    assert referencing == {owner, calibrator}

    # The calibrator calls it as a module-level statement, before it imports
    # the summing builder (whose spec reads counter_seat() at import).
    body = ast.parse(calibrator.read_text(encoding="utf-8")).body
    call = next(
        index
        for index, node in enumerate(body)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and getattr(node.value.func, "attr", None) == _ACCEPT_STALE
    )
    summing = next(
        index
        for index, node in enumerate(body)
        if isinstance(node, ast.ImportFrom)
        and node.module == "build_sm_summing_assembly"
    )
    assert call < summing
