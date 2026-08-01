"""SolidWorks-free contract for reversible range-stop DOF probing."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _assembly  # noqa: E402


class FakeFeature:
    def __init__(self, name: str, type_name: str, *, suppressed: bool = False):
        self.Name = name
        self._type_name = type_name
        self.IsSuppressed = suppressed
        self.transitions: list[int] = []
        self.model = None

    def GetTypeName2(self):
        return self._type_name

    def Select2(self, append, _mark):
        if not append:
            self.model.selected.clear()
        self.model.selected.append(self)
        return True


class FakeModel:
    def __init__(self):
        self.selected = []
        self.operations: list[str] = []

    def ClearSelection2(self, _all):
        self.selected.clear()

    def EditSuppress2(self):
        self.operations.append("suppress")
        for feature in self.selected:
            feature.transitions.append(0)
            feature.IsSuppressed = True
        return True

    def EditUnsuppress2(self):
        self.operations.append("unsuppress")
        for feature in self.selected:
            feature.transitions.append(1)
            feature.IsSuppressed = False
        return True


class FakeAdapter:
    def __init__(self, features):
        self.features = features
        self.currentModel = FakeModel()
        for feature in features:
            feature.model = self.currentModel

    def _attempt(self, operation, default=None):
        try:
            return operation()
        except Exception:
            return default


@pytest.fixture(autouse=True)
def _patch_mate_walk(monkeypatch):
    from solidworks_mcp.adapters.solidworks import assembly as assembly_api

    monkeypatch.setattr(
        assembly_api,
        "_mate_group_subfeatures",
        lambda adapter: list(adapter.features),
    )
    monkeypatch.setattr(_assembly, "_early_bound", lambda obj, _iface: obj)


def test_range_stop_probe_restores_only_active_limit_mates():
    active = FakeFeature("LimitAngle1", "MateLimitPlanarAngleDim")
    already_suppressed = FakeFeature(
        "LimitDistance1", "MateLimitDistanceDim", suppressed=True
    )
    ordinary = FakeFeature("Coincident1", "MateCoincident")
    adapter = FakeAdapter([active, already_suppressed, ordinary])

    with _assembly._range_stops_suppressed(adapter) as count:
        assert count == 1
        assert active.IsSuppressed is True
        assert already_suppressed.IsSuppressed is True
        assert adapter.currentModel.operations == ["suppress"]

    assert active.IsSuppressed is False
    assert already_suppressed.IsSuppressed is True
    assert active.transitions == [0, 1]
    assert already_suppressed.transitions == []
    assert ordinary.transitions == []
    assert adapter.currentModel.operations == ["suppress", "unsuppress"]


def test_range_stop_probe_restores_after_a_failed_status_walk():
    active = FakeFeature("LimitAngle1", "MateLimitPlanarAngleDim")
    adapter = FakeAdapter([active])

    with pytest.raises(RuntimeError, match="status walk failed"):
        with _assembly._range_stops_suppressed(adapter):
            raise RuntimeError("status walk failed")

    assert active.IsSuppressed is False
    assert active.transitions == [0, 1]
    assert adapter.currentModel.operations == ["suppress", "unsuppress"]
