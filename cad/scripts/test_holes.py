"""Cut-diameter contracts for native Hole Wizard subtype readbacks."""

from types import SimpleNamespace

import pytest

from _holes import _wizard_hole_diameter_mm


def test_tapped_cut_uses_tap_drill_not_plain_hole_diameter() -> None:
    definition = SimpleNamespace(
        HoleDiameter=0.0, ThruHoleDiameter=0.0,
        TapDrillDiameter=0.0, ThruTapDrillDiameter=0.001778,
    )
    assert _wizard_hole_diameter_mm(definition, tapped=True) == pytest.approx(1.778)


def test_drilled_cut_uses_plain_hole_not_tap_drill_diameter() -> None:
    definition = SimpleNamespace(
        HoleDiameter=0.0, ThruHoleDiameter=0.004978,
        TapDrillDiameter=0.001778, ThruTapDrillDiameter=0.001778,
    )
    assert _wizard_hole_diameter_mm(definition, tapped=False) == pytest.approx(4.978)


def test_missing_tap_diameter_cannot_be_replaced_by_unrelated_plain_diameter() -> None:
    definition = SimpleNamespace(
        HoleDiameter=0.001778, ThruHoleDiameter=0.001778,
        TapDrillDiameter=0.0, ThruTapDrillDiameter=0.0,
    )
    with pytest.raises(RuntimeError):
        _wizard_hole_diameter_mm(definition, tapped=True)
