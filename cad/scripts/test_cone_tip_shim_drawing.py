"""Offline contracts for the MHA-141 cone tip shim pack part and drawing."""

from __future__ import annotations

import itertools
import math
from pathlib import Path

import pytest

import _config
import build_cone_tip_shim as part
import cone_tip_block_spec as block
import cone_tip_shim_spec as spec
import draw_cone_tip_shim as drawing
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import THREAD_MAJOR_MM, blind_cut_dia_mm


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


def test_horseshoe_slot_passes_the_screw_with_clearance_and_webs() -> None:
    """Main's ruling: #6 normal clearance wide, full radius on the screw axis."""
    assert spec.SLOT_SPEC.kind == "clearance"
    assert spec.SLOT_SPEC.size == "#6"
    assert spec.SLOT_SPEC.fit == "normal"
    assert spec.SLOT_W == pytest.approx(blind_cut_dia_mm(spec.SLOT_SPEC))
    assert spec.SLOT_R == pytest.approx(spec.SLOT_W / 2.0)
    major = THREAD_MAJOR_MM[block.FOOT_THREAD]
    assert spec.SLOT_W - major >= 0.25
    assert spec.SIDE_WEB_MM >= 2.0
    assert spec.SIDE_WEB_MM == pytest.approx((block.BLOCK_Z - spec.SLOT_W) / 2.0)
    assert spec.END_WEB_MM >= 2.0
    assert spec.END_WEB_MM == pytest.approx(block.BLOCK_X / 2.0 - spec.SLOT_R)


def test_slot_opens_away_from_the_drum() -> None:
    """Local -X (east) is the accessible 12 mm edge; +X faces the drum."""
    assert spec.SLOT_OPEN_SIDE == -1
    run_end = part.SLOT_OPEN_SIDE * (spec.SHIM_X / 2.0 + part.SLOT_OVERRUN)
    assert run_end < -spec.SHIM_X / 2.0
    # The mid-plane cut clears the whole pack from its bottom face.
    assert part.CUT_DEPTH / 2.0 > spec.SHIM_T


def test_notes_state_the_stack_range_nominal_and_the_horseshoe() -> None:
    lines = spec.MANUFACTURING_NOTES.splitlines()
    assert len(lines) <= 4
    assert lines[0] == "SHIM PACK, STACK TO FIT 0.05-2.20, NOMINAL 1.10."
    assert lines[1] == "HORSESHOE; SLIDE LEAVES IN WITH SCREW BACKED OFF."


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
    assert spec.DRAWING_PRECISION_BY_NAME["SlotWidth"] == 2
    assert drawing.REFERENCE_DIMENSIONS == ("Thickness",)
    assert drawing.DIMENSION_CALLOUTS["SlotWidth"] == "SLOT, FULL R"


def test_slot_width_reads_past_the_open_mouth() -> None:
    x, y = drawing.TOP_KEEP["SlotWidth"]
    assert x < drawing.TOP_CENTER[0] - drawing.HALF_X
    assert y == pytest.approx(drawing.TOP_CENTER[1])


def test_depth_stands_outside_the_radius_centre_location() -> None:
    assert drawing.TOP_KEEP["Depth"][0] > drawing.SLOT_Z_TEXT[0] + 0.008


def test_slot_location_values_sit_between_their_witnesses() -> None:
    """Each value is mid-span, at least 2 mm off both witness lines."""
    half_w = 0.0065 / 2.0  # three-character value, measured on the tip block
    right = drawing.TOP_CENTER[0] + drawing.HALF_X
    x = drawing.SLOT_X_TEXT[0]
    assert drawing.TOP_CENTER[0] + 0.002 <= x - half_w and x + half_w <= right - 0.002
    lower = drawing.TOP_CENTER[1] - drawing.HALF_Z
    y = drawing.SLOT_Z_TEXT[1]
    assert lower + 0.002 <= y - 0.0019 and y + 0.0019 <= drawing.TOP_CENTER[1] - 0.002


def test_slot_picks_land_on_the_closed_radius() -> None:
    r = spec.SLOT_R * drawing._S
    for angle in (45.0, -45.0):
        x, y = drawing._slot_end_xy(angle)
        assert x > drawing.TOP_CENTER[0]  # the closed end looks right
        assert math.hypot(x - drawing.TOP_CENTER[0], y - drawing.TOP_CENTER[1]) == (
            pytest.approx(r)
        )
    with pytest.raises(ValueError):
        drawing._slot_end_xy(135.0)


def test_drawing_registry_row() -> None:
    reg = DRAWINGS_BY_NAME["cone_tip_shim"]
    assert drawing.SPEC is reg
    assert reg.artifact_stem == part.PART_NAME
    assert reg.script == Path(drawing.__file__).resolve()
