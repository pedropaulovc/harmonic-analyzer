"""Offline contracts for the MHA-141 cone tip shim pack part and drawing."""

from __future__ import annotations

import itertools
from pathlib import Path

import pytest

import _config
import build_cone_tip_shim as part
import cone_tip_block_spec as block
import cone_tip_shim_spec as spec
import draw_cone_tip_shim as drawing
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import THREAD_MAJOR_MM


def test_pack_is_cut_to_the_block_footprint_at_the_nominal_stack() -> None:
    """U30 / handoff item 3: 15.0 x 12.0 x SHIM_NOMINAL, coplanar with the foot."""
    assert (spec.SHIM_X, spec.SHIM_Z) == (block.BLOCK_X, block.BLOCK_Z)
    assert spec.SHIM_T == block.SHIM_NOMINAL == 1.10
    assert spec.STACK_RANGE_MM == block.FOOT_SHIM_RANGE_MM
    low, high = spec.STACK_RANGE_MM
    assert low <= spec.SHIM_T <= high


def test_leaf_stock_builds_the_nominal_and_both_stack_limits() -> None:
    """Some combination of leaves (each size used at most 4 times) hits each."""
    reachable = {
        round(sum(counts[i] * t for i, t in enumerate(spec.LEAF_STOCK_MM)), 2)
        for counts in itertools.product(range(5), repeat=len(spec.LEAF_STOCK_MM))
    }
    for target in (spec.STACK_RANGE_MM[0], spec.SHIM_T, spec.STACK_RANGE_MM[1]):
        assert round(target, 2) in reachable


def test_screw_passes_every_leaf_with_clearance_and_webs() -> None:
    """The MHA-140 #6-32 rises through the pack into the block's foot tap."""
    assert spec.HOLE_SPEC.kind == "clearance"
    assert spec.HOLE_SPEC.size == "#6"
    assert spec.HOLE_SPEC.end == "through_all"
    major = THREAD_MAJOR_MM[block.FOOT_THREAD]
    assert spec.HOLE_DIA - major >= 0.25
    assert spec.EDGE_WEB_MM >= 2.0
    assert spec.EDGE_WEB_MM == pytest.approx((block.BLOCK_Z - spec.HOLE_DIA) / 2.0)


def test_notes_state_the_stack_range_nominal_and_leaf_stock() -> None:
    notes = spec.MANUFACTURING_NOTES
    assert "STACK TO FIT 0.05-2.20" in notes
    assert "NOMINAL 1.10" in notes
    assert "0.05 / 0.10 / 0.25 / 0.50" in notes
    assert "MHA-092" in notes


def test_registry_row_is_the_bom_shim_pack() -> None:
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-141"
    assert row["finish"] == "black oxide"
    assert int(row["quantity"]) == 1
    assert "0.05 / 0.10 / 0.25 / 0.50" in row["material_specification"]


def test_every_marked_dimension_has_a_view_and_a_precision() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert marked == set(drawing.TOP_KEEP) | set(drawing.FRONT_KEEP)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert spec.DRAWING_PRECISION_BY_NAME["Thickness"] == 2
    assert drawing.REFERENCE_DIMENSIONS == ("Thickness",)


def test_hole_location_values_sit_between_their_witnesses() -> None:
    """Each value is mid-span, at least 2 mm off both witness lines."""
    half_w = 0.0065 / 2.0  # three-character value, measured on the tip block
    left = drawing.TOP_CENTER[0] - drawing.HALF_X
    x = drawing.HOLE_X_TEXT[0]
    assert left + 0.002 <= x - half_w and x + half_w <= drawing.TOP_CENTER[0] - 0.002
    lower = drawing.TOP_CENTER[1] - drawing.HALF_Z
    y = drawing.HOLE_Z_TEXT[1]
    assert lower + 0.002 <= y - 0.0019 and y + 0.0019 <= drawing.TOP_CENTER[1] - 0.002


def test_hole_picks_miss_the_centre_mark_arms() -> None:
    for angle in (45.0, -45.0):
        x, y = drawing._hole_edge_xy(angle)
        assert abs(x - drawing.TOP_CENTER[0]) > 0.003
        assert abs(y - drawing.TOP_CENTER[1]) > 0.003


def test_drawing_registry_row() -> None:
    reg = DRAWINGS_BY_NAME["cone_tip_shim"]
    assert drawing.SPEC is reg
    assert reg.artifact_stem == part.PART_NAME
    assert reg.script == Path(drawing.__file__).resolve()
