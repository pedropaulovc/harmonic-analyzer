"""Offline contracts for native crank position and straight tooth-space gates."""

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
    """Hermetic native-query response with an independently prescribed tangential error."""

    def __init__(self, shift_mm) -> None:
        self.shift_mm = shift_mm

    def GetClosestPointOn(self, x: float, y: float, z: float) -> tuple[float, ...]:
        radius = math.hypot(x, y)
        angle = self.shift_mm(z * 1000.0) / (radius * 1000.0)
        cosine, sine = math.cos(angle), math.sin(angle)
        return (x * cosine - y * sine, x * sine + y * cosine, z, 0.0, 0.0)


def _part_adapter(face: object) -> object:
    body = SimpleNamespace(GetFaces=lambda: (face,))
    part = SimpleNamespace(GetBodies2=lambda _body_type, _visible: (body,))
    return SimpleNamespace(currentModel=part)


def _gate(monkeypatch, shift_mm, messages: list[str] | None = None) -> None:
    import dt_crank_drive_gear_spec as spec

    import _straight_gash_gear as geometry

    monkeypatch.setattr(
        geometry._telemetry, "info", (messages if messages is not None else []).append
    )
    monkeypatch.setattr(geometry, "_early_bound", lambda value, _interface: value)
    geometry.assert_straight_gash_flanks(
        _part_adapter(_ClosestFace(shift_mm)),
        spec.TOOTH_SPACE_FORM,
        spec.TOOTH_SPACE,
        tolerance_mm=spec.NATIVE_FLANK_BOUND_MM,
    )


def test_straight_tooth_space_gate_measures_both_flanks_at_three_stations(monkeypatch) -> None:
    import dt_crank_drive_gear_spec as spec

    messages: list[str] = []
    _gate(monkeypatch, lambda _z: 0.0, messages)
    record = json.loads(messages[-1].removeprefix("crank.straight_tooth_space_flanks "))
    assert record["inclination_deg"] == spec.TOOTH_INCLINATION_DEG
    assert record["crossing_z_mm"] == spec.TOOTH_SPACE_CROSSING
    points = record["points"]
    assert len(points) == 3 * 2 * 2
    assert {point["face_fraction"] for point in points} == {0.25, 0.5, 0.75}
    assert {point["flank_side"] for point in points} == {-1, 1}
    form, gash = spec.TOOTH_SPACE_FORM, spec.TOOTH_SPACE
    beta = math.radians(spec.TOOTH_INCLINATION_DEG)
    for point in points:
        u = point["flank_parameter"]
        assert form.flank_parameter_min < u < form.flank_parameter_max
        x, y = form.flank_point(u, side=point["flank_side"])
        z = point["face_fraction"] * spec.FACE_WIDTH
        # Independently: the transverse section is (X, Y/cos + (z - zc) tan)
        # in the space's own (r, t) frame at the crossing azimuth.
        across = y / math.cos(beta) + (z - spec.TOOTH_SPACE_CROSSING) * math.tan(beta)
        a = gash.azimuth_rad
        expected = (
            x * math.cos(a) - across * math.sin(a),
            x * math.sin(a) + across * math.cos(a),
            z,
        )
        assert point["expected_xyz_mm"] == pytest.approx(expected, abs=1e-9)
        assert point["native_xyz_mm"] == pytest.approx(expected, abs=1e-9)
        assert point["distance_mm"] <= record["tolerance_mm"]


@pytest.mark.parametrize(
    "label, shift_per_mm",
    (("wrong hand", -2.0), ("axial spur", -1.0), ("double inclination", 1.0)),
)
def test_straight_tooth_space_gate_rejects_wrong_hand_and_inclination(
    monkeypatch, label: str, shift_per_mm: float
) -> None:
    import dt_crank_drive_gear_spec as spec

    lean = shift_per_mm * math.tan(math.radians(spec.TOOTH_INCLINATION_DEG))
    messages: list[str] = []
    with pytest.raises(RuntimeError, match="straight tooth-space flank mismatch"):
        _gate(monkeypatch, lambda z: lean * (z - spec.TOOTH_SPACE_CROSSING), messages)
    record = json.loads(messages[-1].removeprefix("crank.straight_tooth_space_flanks "))
    # Every station off the crossing is caught, label: the quarter-face
    # station is only 0.028 mm from it and still fails by microns.
    assert all(point["distance_mm"] > record["tolerance_mm"] for point in record["points"]), label


def test_straight_tooth_space_gate_rejects_a_turned_seed_or_moved_crossing(monkeypatch) -> None:
    import dt_crank_drive_gear_spec as spec

    pitch_mm = math.pi * spec.PITCH_DIA / spec.TEETH
    with pytest.raises(RuntimeError, match="straight tooth-space flank mismatch"):
        _gate(monkeypatch, lambda _z: pitch_mm / 2.0)
    # A crossing at mid-face instead of the south quarter: a constant 0.42 mm.
    moved = (spec.FACE_WIDTH / 2.0 - spec.TOOTH_SPACE_CROSSING) * math.tan(
        math.radians(spec.TOOTH_INCLINATION_DEG)
    )
    with pytest.raises(RuntimeError, match="straight tooth-space flank mismatch"):
        _gate(monkeypatch, lambda _z: moved)


def test_straight_tooth_space_gate_refuses_empty_native_faces(monkeypatch) -> None:
    import dt_crank_drive_gear_spec as spec

    import _straight_gash_gear as geometry

    monkeypatch.setattr(geometry, "_early_bound", lambda value, _interface: value)
    body = SimpleNamespace(GetFaces=lambda: ())
    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(GetBodies2=lambda _body_type, _visible: (body,))
    )
    with pytest.raises(RuntimeError, match="no native faces"):
        geometry.assert_straight_gash_flanks(
            adapter, spec.TOOTH_SPACE_FORM, spec.TOOTH_SPACE,
            tolerance_mm=spec.NATIVE_FLANK_BOUND_MM,
        )
