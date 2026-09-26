"""Offline contracts for the native crank signed-position gate."""

from __future__ import annotations

import json
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
