from __future__ import annotations


import pytest

from diagnostics import diag_dump_part as dump


class _NamedFeatureReference:
    Name = "Top Plane"

    def GetType(self, _required_argument):
        raise AssertionError("the failed accessor must not escape as harvested data")


def test_named_feature_reference_ignores_rejected_entity_get_type() -> None:
    assert dump._entity(_NamedFeatureReference()) == {"name": "Top Plane"}


class _ThinExtrude:
    ThinWallType = 3
    CapThickness = 0.0

    def GetWallThickness(self, forward: bool) -> float:
        return 0.0 if forward else 0.0015


class _ThinExtrudeFeature:
    def GetDefinition(self):
        return _ThinExtrude()


def test_thin_extrude_dump_preserves_both_wall_directions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(dump, "_early_bound", lambda value, _interface: value)

    data = dump._feature_data(_ThinExtrudeFeature(), "BossThin")

    assert data is not None
    assert data["ThinWallType"] == 3
    assert data["wall_forward_mm"] == 0.0
    assert data["wall_reverse_mm"] == 1.5
    assert data["cap_mm"] == 0.0
