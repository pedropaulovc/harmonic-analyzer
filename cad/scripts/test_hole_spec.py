"""Offline contracts for part-owned standard-hole definitions."""

from __future__ import annotations

import pytest

import pivot_bracket_spec
import crank_arm_spec
from _hole_spec import HoleSpec, blind_cut_dia_mm, drill_process


def test_crank_drill_process_is_derived_from_part_owned_specs() -> None:
    assert blind_cut_dia_mm(crank_arm_spec.PIN_HOLE_SPEC) == 4.623
    assert drill_process(crank_arm_spec.PIN_HOLE_SPEC) == "#14 DRILL"
    assert blind_cut_dia_mm(crank_arm_spec.HANDLE_PIVOT_HOLE_SPEC) == 5.953
    assert drill_process(crank_arm_spec.HANDLE_PIVOT_HOLE_SPEC) == "15/64 DRILL"


def test_drill_process_rejects_non_drill_holes() -> None:
    with pytest.raises(ValueError, match="not a drill-size hole"):
        drill_process(HoleSpec("clearance", "#4"))


def test_pivot_bracket_hold_down_is_a_true_number_8_close_clearance() -> None:
    # Cut at the table diameter, not a rounded one (8a36fe155 caught #19 cut at
    # 4.2). #19 became #8 close in r743-3C: it caught the screw's fillet.
    assert pivot_bracket_spec.HOLD_DOWN_HOLE_SPEC == HoleSpec("clearance", "#8", fit="close")
    assert pivot_bracket_spec.HOLE_DIA == 4.572
