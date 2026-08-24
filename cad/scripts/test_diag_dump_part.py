from __future__ import annotations

from diagnostics import diag_dump_part as dump


class _NamedFeatureReference:
    Name = "Top Plane"

    def GetType(self, _required_argument):
        raise AssertionError("the failed accessor must not escape as harvested data")


def test_named_feature_reference_ignores_rejected_entity_get_type() -> None:
    assert dump._entity(_NamedFeatureReference()) == {"name": "Top Plane"}
