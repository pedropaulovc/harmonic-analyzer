"""Offline contracts for part-owned standard-hole definitions."""

from __future__ import annotations

import pytest

import ch_pivot_bracket_spec
import dt_crank_arm_spec
import dt_crank_hub_spec
from _hole_spec import HoleSpec, blind_cut_dia_mm, drill_process


def test_crank_drill_process_is_derived_from_part_owned_specs() -> None:
    assert blind_cut_dia_mm(dt_crank_hub_spec.SERVICE_PIN_HOLE_SPEC) == 4.623
    assert drill_process(dt_crank_hub_spec.SERVICE_PIN_HOLE_SPEC) == "#14 DRILL"
    # The arm pivot is tapped #4-40 (tap drill #43) for MHA-DT-032.
    assert blind_cut_dia_mm(dt_crank_arm_spec.HANDLE_PIVOT_HOLE_SPEC) == 2.261
    with pytest.raises(ValueError, match="not a drill-size hole"):
        drill_process(dt_crank_arm_spec.HANDLE_PIVOT_HOLE_SPEC)


def test_drill_process_rejects_non_drill_holes() -> None:
    with pytest.raises(ValueError, match="not a drill-size hole"):
        drill_process(HoleSpec("clearance", "#4"))


def test_pivot_bracket_hold_down_is_a_true_number_8_close_clearance() -> None:
    # Cut at the table diameter, not a rounded one (8a36fe155 caught #19 cut at
    # 4.2). #19 became #8 close in r743-3C: it caught the screw's fillet.
    assert ch_pivot_bracket_spec.HOLD_DOWN_HOLE_SPEC == HoleSpec("clearance", "#8", fit="close")
    assert ch_pivot_bracket_spec.HOLE_DIA == 4.572
