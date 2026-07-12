from __future__ import annotations

import asyncio

import pytest

import _assembly
from _assembly import (
    PatternDirection,
    circular_component_pattern,
    ensure_global_pattern_axis,
    linear_component_pattern,
)


class _PatternDefinition:
    D1ReverseDirection = False


class _PatternComponent:
    Name2 = "seed-2"

    @staticmethod
    def IsPatternInstance() -> bool:
        return True


class _PatternFeature:
    Name = "LocalLPattern"


class _PatternManager:
    def __init__(self, model: _PatternModel) -> None:
        self.model = model
        self.definition = _PatternDefinition()

    def CreateDefinition(self, feature_id: int) -> _PatternDefinition:
        return self.definition

    def CreateFeature(self, definition: _PatternDefinition) -> _PatternFeature:
        self.model.created = True
        return _PatternFeature()


class _PatternModel:
    def __init__(self) -> None:
        self.created = False
        self.FeatureManager = _PatternManager(self)

    def GetComponents(self, top_level_only: bool) -> list[_PatternComponent]:
        return [_PatternComponent()] if self.created else []

    @staticmethod
    def ClearSelection2(all_selections: bool) -> None:
        return None


class _PatternAdapter:
    def __init__(self) -> None:
        self.currentModel = _PatternModel()


def test_global_pattern_axis_rejects_unknown_axis_before_com() -> None:
    with pytest.raises(ValueError, match="x, y, or z"):
        ensure_global_pattern_axis(None, "diagonal")


def test_linear_pattern_rejects_single_instance_before_com() -> None:
    with pytest.raises(ValueError, match="at least two"):
        asyncio.run(
            linear_component_pattern(
                None,
                "seed-1",
                axis="x",
                spacing_mm=10.0,
                instances=1,
            )
        )


def test_linear_pattern_rejects_nonpositive_spacing_before_com() -> None:
    with pytest.raises(ValueError, match="positive"):
        asyncio.run(
            linear_component_pattern(
                None,
                "seed-1",
                axis="x",
                spacing_mm=0.0,
                instances=2,
            )
        )


def test_linear_pattern_preserves_reverse_direction(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = _PatternAdapter()
    monkeypatch.setattr(_assembly, "ensure_global_pattern_axis", lambda *_: "PatternAxisX")
    monkeypatch.setattr(_assembly, "_select_pattern_inputs", lambda *_: None)
    monkeypatch.setattr(_assembly, "_flag", lambda *_: None)
    monkeypatch.setattr(_assembly, "_flag_only", lambda *_: None)
    names = asyncio.run(
        linear_component_pattern(
            adapter,
            "seed-1",
            axis="x",
            spacing_mm=35.0,
            instances=2,
            direction=PatternDirection.REVERSE,
        )
    )

    assert adapter.currentModel.FeatureManager.definition.D1ReverseDirection is True
    assert names == ["seed-2"]


def test_circular_pattern_rejects_single_instance_before_com() -> None:
    with pytest.raises(ValueError, match="at least two"):
        asyncio.run(
            circular_component_pattern(
                None,
                "seed-1",
                axis_name="Axis1",
                instances=1,
            )
        )
