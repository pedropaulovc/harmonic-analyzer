"""Offline contracts for part-owned standard-hole definitions."""

from __future__ import annotations

import pytest

import build_pivot_bracket
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


def test_pivot_bracket_is_a_true_number_19_drill() -> None:
    assert build_pivot_bracket.HOLD_DOWN_HOLE_SPEC == HoleSpec("drilled_number", "#19")
    assert build_pivot_bracket.HOLE_DIA == 4.216
