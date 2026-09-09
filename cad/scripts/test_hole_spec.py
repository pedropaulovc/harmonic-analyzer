"""Offline contracts for part-owned standard-hole definitions."""

from __future__ import annotations

import pytest

import _holes
import build_channel_assembly
import build_pivot_bracket
import build_summing_lever
import channel_lever_spec
import crank_arm_spec
import rocker_arm_spec
import summing_lever_spec
from _hole_spec import HoleSpec, blind_cut_dia_mm, drill_process


def test_holes_executor_uses_the_pure_contract_type() -> None:
    assert _holes.HoleSpec is HoleSpec


def test_crank_drill_process_is_derived_from_part_owned_specs() -> None:
    assert blind_cut_dia_mm(crank_arm_spec.PIN_HOLE_SPEC) == 4.623
    assert drill_process(crank_arm_spec.PIN_HOLE_SPEC) == "#14 DRILL"
    assert blind_cut_dia_mm(crank_arm_spec.HANDLE_PIVOT_HOLE_SPEC) == 5.953
    assert drill_process(crank_arm_spec.HANDLE_PIVOT_HOLE_SPEC) == "15/64 DRILL"


def test_drill_process_rejects_non_drill_holes() -> None:
    with pytest.raises(ValueError, match="not a drill-size hole"):
        drill_process(HoleSpec("clearance", "#4"))


def test_part_builds_consume_shared_drill_specs() -> None:
    assert build_summing_lever.HOLE_SPEC is summing_lever_spec.HOLE_SPEC
    assert build_channel_assembly.PLATE_HOLE_DIA == blind_cut_dia_mm(
        summing_lever_spec.HOLE_SPEC
    )
    assert blind_cut_dia_mm(channel_lever_spec.BAR_PIN_HOLE_SPEC) == 1.994
    assert blind_cut_dia_mm(channel_lever_spec.SPRING_EYE_HOLE_SPEC) == 4.039
    assert blind_cut_dia_mm(rocker_arm_spec.ROD_HOLE_SPEC) == 1.994


def test_pivot_bracket_is_a_true_number_19_drill() -> None:
    assert build_pivot_bracket.HOLD_DOWN_HOLE_SPEC == HoleSpec("drilled_number", "#19")
    assert build_pivot_bracket.HOLE_DIA == 4.216
