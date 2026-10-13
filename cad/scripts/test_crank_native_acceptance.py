"""Offline contracts for native crank position and stock screw-sweep gates."""

from __future__ import annotations

import json
import math
from types import SimpleNamespace

import pytest

import crank_native_acceptance as acceptance


class _Feature:
    def __init__(self, name: str, specific: object, next_feature: object = None) -> None:
        self.Name = name
        self._specific = specific
        self._next = next_feature

    def GetSpecificFeature2(self) -> object:
        return self._specific

    def GetNextFeature(self) -> object:
        return self._next


def _adapter(sketch_xy_mm: tuple[float, float], axis_x_mm: float = 7.5) -> object:
    point = SimpleNamespace(X=sketch_xy_mm[0] / 1000.0, Y=sketch_xy_mm[1] / 1000.0)
    arc = SimpleNamespace(GetCenterPoint2=lambda: point)
    sketch = SimpleNamespace(GetSketchSegments=lambda: [arc])
    axis = SimpleNamespace(
        GetRefAxisParams=lambda: (
            axis_x_mm / 1000.0,
            0.0,
            -0.1,
            axis_x_mm / 1000.0,
            0.0,
            0.1,
        )
    )
    axis_feature = _Feature("Axis3", axis)
    sketch_feature = _Feature("AxialPinGrooveProfile", sketch, axis_feature)
    return SimpleNamespace(currentModel=SimpleNamespace(FirstFeature=sketch_feature))


def test_signed_center_gate_records_rebuilt_sketch_and_axis(monkeypatch) -> None:
    messages: list[str] = []
    monkeypatch.setattr(acceptance._telemetry, "info", messages.append)

    acceptance.assert_signed_circle_center(
        _adapter((7.5, 0.0)),
        "AxialPinGrooveProfile",
        label="arm seam",
        expected_sketch_xy_mm=(7.5, 0.0),
        expected_model_xyz_mm=(7.5, 0.0, 8.0),
        axis_name="Axis3",
        axis_expected_components_mm={0: 7.5, 1: 0.0},
    )

    record = json.loads(messages[-1].removeprefix("crank.signed_center "))
    assert record["sketch_actual_xy_mm"] == [7.5, 0.0]
    assert record["sketch_expected_xy_mm"] == [7.5, 0.0]
    assert record["axis"]["actual_start_xyz_mm"][:2] == [7.5, 0.0]


def test_signed_center_gate_rejects_mirrored_equation_branch(monkeypatch) -> None:
    monkeypatch.setattr(acceptance._telemetry, "info", lambda _message: None)

    with pytest.raises(RuntimeError, match=r"sketch\[0\] actual -7.5, expected 7.5"):
        acceptance.assert_signed_circle_center(
            _adapter((-7.5, 0.0)),
            "AxialPinGrooveProfile",
            label="arm seam",
            expected_sketch_xy_mm=(7.5, 0.0),
            expected_model_xyz_mm=(7.5, 0.0, 8.0),
            axis_name="Axis3",
            axis_expected_components_mm={0: 7.5, 1: 0.0},
        )


class _ClosestFace:
    """Hermetic native-query response with an independently prescribed phase error."""

    def __init__(self, phase_error) -> None:
        self.phase_error = phase_error

    def GetClosestPointOn(self, x: float, y: float, z: float) -> tuple[float, ...]:
        angle = self.phase_error(z * 1000.0)
        cosine, sine = math.cos(angle), math.sin(angle)
        return (x * cosine - y * sine, x * sine + y * cosine, z, 0.0, 0.0)


def _screw_adapter(face: object) -> object:
    body = SimpleNamespace(GetFaces=lambda: (face,))
    part = SimpleNamespace(GetBodies2=lambda _body_type, _visible: (body,))
    return SimpleNamespace(currentModel=part)


def test_stock_screw_sweep_gate_measures_supported_flanks_and_all_three_stations(
    monkeypatch,
) -> None:
    import dt_crank_drive_gear_spec as spec

    import _gear as geometry

    profile = spec.STOCK_PROFILE
    messages: list[str] = []
    monkeypatch.setattr(geometry._telemetry, "info", messages.append)
    monkeypatch.setattr(geometry, "_early_bound", lambda value, _interface: value)
    midface_phase = math.pi / profile.teeth
    geometry.assert_stock_screw_sweep_phase(
        _screw_adapter(_ClosestFace(lambda _z: 0.0)),
        profile,
        spec.FACE_WIDTH,
        midface_tooth_phase_rad=midface_phase,
        tolerance_mm=spec.NATIVE_SWEEP_BOUND_MM,
    )
    record = json.loads(messages[-1].removeprefix("crank.stock_screw_sweep_phase "))
    assert record["physical_teeth"] == spec.TEETH
    assert record["reference_teeth"] == profile.template.reference_teeth
    assert record["helix_angle_deg"] == spec.HELIX_ANGLE_DEG
    points = record["points"]
    assert len(points) == 3 * 2 * 2
    assert {point["face_fraction"] for point in points} == {0.25, 0.5, 0.75}
    assert {point["flank_side"] for point in points} == {-1, 1}
    for point in points:
        u = point["flank_parameter"]
        assert profile.template.flank_parameter_min < u < profile.template.flank_parameter_max
        x, y = profile.flank_point(u, side=point["flank_side"])
        assert math.hypot(x, y) < profile.blank_radius_mm
        z = point["face_fraction"] * spec.FACE_WIDTH
        pitch_phase = (
            (z - spec.FACE_WIDTH / 2.0)
            * math.tan(math.radians(spec.HELIX_ANGLE_DEG))
            / profile.pitch_radius_mm
        )
        gap_phase = midface_phase - point["flank_side"] * math.pi / spec.TEETH
        expected = (
            x * math.cos(gap_phase + pitch_phase) - y * math.sin(gap_phase + pitch_phase),
            x * math.sin(gap_phase + pitch_phase) + y * math.cos(gap_phase + pitch_phase),
            z,
        )
        assert point["expected_xyz_mm"] == pytest.approx(expected)
        assert point["native_xyz_mm"] == pytest.approx(expected)
        assert point["distance_mm"] <= record["tolerance_mm"]


@pytest.mark.parametrize("twist_multiplier", (-1.0, 0.0, 2.0))
def test_stock_screw_sweep_gate_rejects_wrong_hand_missing_twist_and_double_twist(
    monkeypatch, twist_multiplier: float
) -> None:
    import dt_crank_drive_gear_spec as spec

    import _gear as geometry

    profile = spec.STOCK_PROFILE
    messages: list[str] = []
    monkeypatch.setattr(geometry._telemetry, "info", messages.append)
    monkeypatch.setattr(geometry, "_early_bound", lambda value, _interface: value)
    twist_per_mm = math.tan(math.radians(spec.HELIX_ANGLE_DEG)) / profile.pitch_radius_mm

    def native_phase_error(z: float) -> float:
        return (twist_multiplier - 1.0) * (z - spec.FACE_WIDTH / 2.0) * twist_per_mm

    with pytest.raises(RuntimeError, match="stock screw-sweep phase mismatch"):
        geometry.assert_stock_screw_sweep_phase(
            _screw_adapter(_ClosestFace(native_phase_error)), profile, spec.FACE_WIDTH,
            tolerance_mm=spec.NATIVE_SWEEP_BOUND_MM,
        )
    record = json.loads(messages[-1].removeprefix("crank.stock_screw_sweep_phase "))
    assert all(
        point["distance_mm"] <= record["tolerance_mm"]
        for point in record["points"]
        if point["face_fraction"] == 0.5
    )
    assert all(
        point["distance_mm"] > record["tolerance_mm"]
        for point in record["points"]
        if point["face_fraction"] != 0.5
    )


def test_stock_screw_sweep_gate_rejects_rotated_midface_datum(monkeypatch) -> None:
    import dt_crank_drive_gear_spec as spec

    import _gear as geometry

    monkeypatch.setattr(geometry._telemetry, "info", lambda _message: None)
    monkeypatch.setattr(geometry, "_early_bound", lambda value, _interface: value)
    with pytest.raises(RuntimeError, match="stock screw-sweep phase mismatch"):
        geometry.assert_stock_screw_sweep_phase(
            _screw_adapter(_ClosestFace(lambda _z: math.pi / spec.TEETH)),
            spec.STOCK_PROFILE,
            spec.FACE_WIDTH,
            tolerance_mm=spec.NATIVE_SWEEP_BOUND_MM,
        )


def test_stock_screw_sweep_gate_refuses_empty_native_faces(monkeypatch) -> None:
    import dt_crank_drive_gear_spec as spec

    import _gear as geometry

    monkeypatch.setattr(geometry, "_early_bound", lambda value, _interface: value)
    body = SimpleNamespace(GetFaces=lambda: ())
    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(GetBodies2=lambda _body_type, _visible: (body,))
    )
    with pytest.raises(RuntimeError, match="no native faces"):
        geometry.assert_stock_screw_sweep_phase(
            adapter, spec.STOCK_PROFILE, spec.FACE_WIDTH,
            tolerance_mm=spec.NATIVE_SWEEP_BOUND_MM,
        )
