from __future__ import annotations

from pathlib import Path

import pytest

import _assembly
import _assembly_patterns
from _assembly import (
    assert_pose_ledger,
)
from _assembly_patterns import (
    PatternDirection,
    assert_pattern_targets,
    circular_component_pattern,
    ensure_global_pattern_axis,
    grid_component_pattern,
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
        linear_component_pattern(
                None,
                ["seed-1"],
                axis="x",
                spacing_mm=10.0,
                instances=1,
            )


def test_linear_pattern_rejects_nonpositive_spacing_before_com() -> None:
    with pytest.raises(ValueError, match="positive"):
        linear_component_pattern(
                None,
                ["seed-1"],
                axis="x",
                spacing_mm=0.0,
                instances=2,
            )


def test_linear_pattern_preserves_reverse_direction(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = _PatternAdapter()
    monkeypatch.setattr(_assembly_patterns, "ensure_global_pattern_axis", lambda *_: "PatternAxisX")
    monkeypatch.setattr(_assembly_patterns, "_select_pattern_inputs", lambda *_: None)
    monkeypatch.setattr(_assembly_patterns, "_early_bound", lambda obj, *_: obj)
    names = linear_component_pattern(
            adapter,
            ["seed-1"],
            axis="x",
            spacing_mm=35.0,
            instances=2,
            direction=PatternDirection.REVERSE,
        )

    assert adapter.currentModel.FeatureManager.definition.D1ReverseDirection is True
    assert names == ["seed-2"]


def test_circular_pattern_rejects_single_instance_before_com() -> None:
    with pytest.raises(ValueError, match="at least two"):
        circular_component_pattern(
                None,
                ["seed-1"],
                axis_name="Axis1",
                instances=1,
            )


def test_grid_pattern_rejects_repeated_axis_before_com() -> None:
    with pytest.raises(ValueError, match="axes must differ"):
        grid_component_pattern(
                None,
                ["seed-1"],
                axis1="x",
                spacing1_mm=10.0,
                instances1=2,
                axis2="X",
                spacing2_mm=20.0,
                instances2=2,
            )


def test_pattern_targets_join_final_pose_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    position = [10.0, 20.0, 30.0]
    rows = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]

    def transform(*_: object) -> list[float]:
        return [
            1.0, 0.0, 0.0,
            0.0, 1.0, 0.0,
            0.0, 0.0, 1.0,
            position[0] / 1000.0,
            position[1] / 1000.0,
            position[2] / 1000.0,
            1.0, 0.0, 0.0, 0.0,
        ]

    _assembly._POSE_LEDGER.clear()
    monkeypatch.setattr(_assembly, "component_transform", transform)
    monkeypatch.setattr(_assembly_patterns, "component_transform", transform)
    assert_pattern_targets(None, ["pattern-1"], [position.copy()], rows, "pattern")

    position[0] += 1.0
    with pytest.raises(RuntimeError, match="pattern-1"):
        assert_pose_ledger(None)


def test_pattern_targets_read_candidates_in_sorted_name_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Each candidate's transform is a COM read: sorted name order, never the
    # set's (string hashing is salted per process).
    rows = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    stations = {"pattern-3": 30.0, "pattern-1": 10.0, "pattern-2": 20.0}
    read: list[str] = []

    def transform(_adapter: object, name: str) -> list[float]:
        read.append(name)
        rotation = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
        return [*rotation, stations[name] / 1000.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]

    _assembly._POSE_LEDGER.clear()
    monkeypatch.setattr(_assembly, "component_transform", transform)
    monkeypatch.setattr(_assembly_patterns, "component_transform", transform)
    targets = [[x, 0.0, 0.0] for x in (30.0, 10.0, 20.0)]
    assert_pattern_targets(None, list(stations), targets, rows, "pattern")
    _assembly._POSE_LEDGER.clear()
    assert read[:3] == ["pattern-1", "pattern-2", "pattern-3"]


class _UnnamedNeighbourModel(_PatternModel):
    """An assembly already holding a component whose name reads empty."""

    def GetComponents(self, top_level_only: bool) -> list[object]:
        unnamed = type("_Unnamed", (), {"Name2": None})()
        return [unnamed, *super().GetComponents(top_level_only)]


@pytest.mark.parametrize(
    "pattern",
    [
        lambda adapter: linear_component_pattern(
            adapter, ["seed-1"], axis="x", spacing_mm=10.0, instances=2
        ),
        lambda adapter: grid_component_pattern(
            adapter,
            ["seed-1"],
            axis1="x",
            spacing1_mm=10.0,
            instances1=2,
            axis2="y",
            spacing2_mm=10.0,
            instances2=2,
        ),
        lambda adapter: circular_component_pattern(
            adapter, ["seed-1"], axis_name="Axis1", instances=2
        ),
    ],
    ids=["linear", "grid", "circular"],
)
def test_the_names_before_a_pattern_are_read_by_name_and_fail_closed(
    monkeypatch: pytest.MonkeyPatch, pattern
) -> None:
    # Issue #2759: the "before" set goes through by_name like every other
    # component name read, so an unnamed component stops the pattern before
    # its feature is created instead of entering the set as "None".
    adapter = _PatternAdapter()
    adapter.currentModel = _UnnamedNeighbourModel()
    monkeypatch.setattr(_assembly_patterns, "ensure_global_pattern_axis", lambda *_: "Axis")
    monkeypatch.setattr(_assembly_patterns, "_select_pattern_inputs", lambda *_: None)
    monkeypatch.setattr(_assembly_patterns, "_early_bound", lambda obj, *_: obj)
    with pytest.raises(RuntimeError, match="element 0 of 1 has no Name2"):
        pattern(adapter)
    assert adapter.currentModel.created is False


@pytest.mark.parametrize(
    "builder",
    [
        "build_dt_drive_train_assembly.py",
        "build_fr_frame_assembly.py",
        "build_mg_magnifier_assembly.py",
        "build_pd_paper_drive_assembly.py",
    ],
)
def test_every_native_pattern_records_authored_targets(builder: str) -> None:
    source = (Path(__file__).parent / builder).read_text(encoding="utf-8")
    pattern_calls = source.count("linear_component_pattern(")
    pattern_calls += source.count("circular_component_pattern(")
    pattern_calls += source.count("grid_component_pattern(")
    assert pattern_calls > 0
    assert source.count("assert_pattern_targets(") == pattern_calls
