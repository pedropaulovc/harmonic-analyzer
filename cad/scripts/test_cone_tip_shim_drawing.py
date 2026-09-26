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
from _drawing_contract import drawing_specification_violations
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import THREAD_MAJOR_MM


def test_pack_is_cut_to_the_block_foot_face_at_the_nominal_stack() -> None:
    """U30 / handoff item 3 / I31: the block's width, from the foot flange's
    south end to the heel relief's inner face (15.0 x 31.27), at
    SHIM_NOMINAL."""
    assert spec.SHIM_X == block.BLOCK_X
    assert spec.SHIM_SOUTH_Z == pytest.approx(-block.BLOCK_Z / 2.0 - block.FLANGE_LEN)
    assert spec.SHIM_NORTH_Z == pytest.approx(
        block.BLOCK_Z / 2.0 - block.HEEL_RELIEF_DEPTH
    )
    assert spec.SHIM_Z == pytest.approx(31.27)
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


def test_horseshoe_slot_spans_the_flange_slot_with_webs() -> None:
    """I31: at its narrowest .XX print the slot still spans the flange
    slot's widest cut (4.07 +0.10/0 -> 4.58 .XX), full radius at the end."""
    assert spec.SLOT_W == 4.58
    assert spec.SLOT_W - 0.51 >= block.FLANGE_SLOT_W_MAX
    assert spec.SLOT_R == pytest.approx(spec.SLOT_W / 2.0)
    major = THREAD_MAJOR_MM[block.FOOT_THREAD]
    assert spec.SLOT_W - 0.51 - major >= 0.25
    assert spec.SIDE_WEB_MM == pytest.approx(block.BLOCK_X / 2.0 - spec.SLOT_R)
    assert spec.END_WEB_MM == pytest.approx(spec.SLOT_CENTRE_FROM_NORTH - spec.SLOT_R)
    assert min(spec.SIDE_WEB_MM, spec.END_WEB_MM) >= 2.0


def test_closed_end_stays_north_of_every_screw_position() -> None:
    """The pack is squared on the heel-relief face; the screw's farthest
    reach north of that edge runs through the block's printed bands and its
    float in the flange slot.  The radius end, at its narrowest and at its
    location's long limit, still passes it.

    #838 r3 (datum A): the block baselines the flange slot's north arc
    centre from the body's south face at .X (FlangeSlotNorthZ 6.5), so the
    chain is heel relief .XX + Depth .X + FlangeSlotNorthZ .X + float; the
    old midpoint (FlangeSlotZ .X) and half-spacing (.XX / 2) terms are gone."""
    assert block.FLANGE_SLOT_NORTH_Z == 6.5
    assert block.FLANGE_SLOT_END_PLACES == 1
    nominal = (12.0 - 1.53) + 6.5
    assert spec.FLANGE_SLOT_NORTH_CENTRE_FROM_NORTH == pytest.approx(nominal)
    bands = 0.51 + 0.8 + 0.8
    assert spec.SCREW_NORTH_REACH_BANDS_MM == pytest.approx(bands)
    reach = nominal - (bands + block.FLANGE_SLOT_FLOAT)
    assert spec.SCREW_NORTH_REACH_FROM_NORTH == pytest.approx(reach)
    slack = (spec.SLOT_W - 0.51) / 2.0 - 3.505 / 2.0
    assert spec.SLOT_CENTRE_FROM_NORTH == 14.0
    assert spec.SLOT_CENTRE_FROM_NORTH + 0.8 - slack <= reach
    # One step further south (14.1) no longer passes: the value is derived.
    assert 14.1 + 0.8 - slack > reach
    assert spec.SLOT_CENTRE_Z == pytest.approx(spec.SHIM_NORTH_Z - 14.0)


def test_old_midpoint_chain_no_longer_describes_the_block() -> None:
    """The pre-r3 chain ran through FlangeSlotZ (.X, the slot midpoint) and
    half the .XX spacing; the baselined chain runs through FlangeSlotNorthZ
    (.X) alone.  Same nominal, but the old chain spends half a .XX band more,
    so on today's block it reaches a shorter distance (and floored the slot
    centre to 13.8, not 14.0) -- and the shim spec no longer reads the
    retired names."""
    old_nominal = (12.0 - 1.53) + block.FLANGE_SLOT_Z - block.FLANGE_SLOT_CTOC / 2.0
    old_reach = old_nominal - (0.51 + 0.8 + 0.8 + 0.51 / 2.0 + block.FLANGE_SLOT_FLOAT)
    assert old_nominal == pytest.approx(spec.FLANGE_SLOT_NORTH_CENTRE_FROM_NORTH)
    assert spec.SCREW_NORTH_REACH_FROM_NORTH - old_reach == pytest.approx(0.51 / 2.0)
    slack = (spec.SLOT_W - 0.51) / 2.0 - 3.505 / 2.0
    old_centre = math.floor((old_reach + slack - 0.8) * 10.0 + 1e-6) / 10.0
    assert old_centre == 13.8 != spec.SLOT_CENTRE_FROM_NORTH
    source = Path(spec.__file__).read_text(encoding="utf-8")
    for retired in ("FLANGE_SLOT_Z_PLACES", "FlangeSlotCtoC", "_CTOC_PLACES"):
        assert retired not in source


def test_slot_opens_south_along_the_flange_slot() -> None:
    """I31: the screw rides the block's axial flange slot, so the horseshoe
    opens to the south edge on the block's centre plane."""
    assert spec.SLOT_OPEN_EDGE == "south"
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "run_end = -SHIM_SOUTH_Z + SLOT_OVERRUN" in source
    assert "slot_pts = [(-h, y_centre), (h, y_centre), (h, run_end), (-h, run_end)]" in source
    # The mid-plane cut clears the whole pack from its bottom face.
    assert part.CUT_DEPTH / 2.0 > spec.SHIM_T


def test_stack_range_rides_the_thickness_dimension_not_a_note() -> None:
    """Rule 6 (Main's eye pass of warm-c486): no dimension in a note.  The
    stack range wraps the imported thickness, derived from the spec's range
    at the model's places; the value between is the model's own."""
    places = spec.DRAWING_PRECISION_BY_NAME["Thickness"]
    low, high = spec.STACK_RANGE_MM
    shown = (
        f"{spec.THICKNESS_TEXT_PREFIX}{spec.SHIM_T:.{places}f}"
        f"{spec.THICKNESS_TEXT_SUFFIX}"
    )
    assert shown == f"{low:.2f}–{high:.2f} STACK (1.10 NOM)"
    # The nominal is the model's dimension, never typed into the text.
    assert f"{spec.SHIM_T:.{places}f}" not in spec.THICKNESS_TEXT_PREFIX
    assert not any(ch.isdigit() for ch in spec.THICKNESS_TEXT_SUFFIX)
    assert drawing.THICKNESS_TEXT_PREFIX is spec.THICKNESS_TEXT_PREFIX
    assert drawing.THICKNESS_TEXT_SUFFIX is spec.THICKNESS_TEXT_SUFFIX
    # Nothing else labels the thickness: no reference parentheses of its own
    # and no "NOMINAL STACK" callout competing with the stack text.
    assert "Thickness" not in drawing.DIMENSION_CALLOUTS
    assert not hasattr(drawing, "REFERENCE_DIMENSIONS")


def test_sheet_carries_no_general_note() -> None:
    """The leaf stock is the material specification and blackening the
    finish (rule 1); the fitting procedure is an MHA-A03 assembly step.  So
    no Manufacturing Notes block is authored, stamped or placed."""
    assert not hasattr(spec, "MANUFACTURING_NOTES")
    for module in (part, drawing):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "Manufacturing Notes" not in source
        assert "MANUFACTURING_NOTES" not in source


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
    assert drawing.DIMENSION_CALLOUTS == {"SlotWidth": "SLOT, FULL R"}


def test_slot_width_reads_past_the_open_mouth() -> None:
    """The slot opens at the plan's top (south) edge; its width reads above
    that edge, under the 15.0 width."""
    x, y = drawing.TOP_KEEP["SlotWidth"]
    assert x == pytest.approx(drawing.TOP_CENTER[0])
    assert drawing.PLAN_TOP < y < drawing.TOP_KEEP["Width"][1] - 0.008
    # North (the trimmed edge) is at the bottom of the plan.
    assert drawing.PLAN_BOTTOM < drawing.SLOT_CENTRE_Y < drawing.PLAN_TOP
    assert drawing.PLAN_TOP - drawing.PLAN_BOTTOM == pytest.approx(
        spec.SHIM_Z * drawing._S
    )


def test_depth_stands_outside_the_radius_centre_location() -> None:
    assert drawing.TOP_KEEP["Depth"][0] > drawing.TOP_KEEP["SlotCentreZ"][0] + 0.008


def test_slot_location_values_sit_between_their_witnesses() -> None:
    """Each value is mid-span, at least 2 mm off both witness lines."""
    half_w = 0.0065 / 2.0  # three-character value, measured on the tip block
    right = drawing.TOP_CENTER[0] + drawing.HALF_X
    x = drawing.TOP_KEEP["SlotCentreX"][0]
    assert drawing.TOP_CENTER[0] + 0.002 <= x - half_w and x + half_w <= right - 0.002
    lower = drawing.PLAN_BOTTOM
    y = drawing.TOP_KEEP["SlotCentreZ"][1]
    assert lower + 0.002 <= y - 0.0019 and y + 0.0019 <= drawing.SLOT_CENTRE_Y - 0.002


def test_drawing_registry_row() -> None:
    reg = DRAWINGS_BY_NAME["cone_tip_shim"]
    assert drawing.SPEC is reg
    assert reg.artifact_stem == part.PART_NAME
    assert reg.script == Path(drawing.__file__).resolve()


def test_stack_text_leads_off_its_dimension_line() -> None:
    """r1 printed "(Ø1.10)" across its own 4.4 mm-tall dimension line.

    warm-c486 measured the sheet's 3.5 mm text at ~2.85 mm per capital and
    ~1.95 per digit or stop; 2.6 mm per character bounds the one-line stack
    text, positioned by its centre.  The title block's top edge sits at
    ~65 mm on the B sheet (the same render).
    """
    places = spec.DRAWING_PRECISION_BY_NAME["Thickness"]
    text = (
        f"{spec.THICKNESS_TEXT_PREFIX}{spec.SHIM_T:.{places}f}"
        f"{spec.THICKNESS_TEXT_SUFFIX}"
    )
    line_x = drawing.FRONT_KEEP["Thickness"][0]
    text_x, text_y = drawing.THICKNESS_TEXT
    half_w = len(text) * 0.0026 / 2.0
    assert text_x - half_w >= line_x + 0.004
    assert text_y - 0.003 > 0.065 + 0.008  # clear above the title block
    # Right end stays short of the isometric's cell.
    assert text_x + half_w < drawing.ISO_CENTER[0] - 0.040


def test_stack_text_carries_no_diameter_glyph() -> None:
    """The plural reference helper prefixes "(<MOD-DIAM>" ("(Ø1.10)" in r1);
    the stack is a length, and its prefix is the spec's plain text."""
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "set_reference_dimensions(" not in source
    assert "MOD-DIAM" not in spec.THICKNESS_TEXT_PREFIX


def test_radius_centre_locations_are_model_owned_one_place() -> None:
    """Codex P1 on #857: .X locations the machinist works to take the
    part's places, imported, never a render-time SetPrecision3."""
    assert spec.DRAWING_DIMENSIONS["SlotCentreXReference"] == {"SlotCentreX"}
    assert spec.DRAWING_DIMENSIONS["SlotCentreZReference"] == {"SlotCentreZ"}
    assert spec.DRAWING_PRECISION_BY_NAME["SlotCentreX"] == 1
    assert spec.DRAWING_PRECISION_BY_NAME["SlotCentreZ"] == 1
    assert set(spec.REFERENCE_SKETCHES) == {
        "SlotCentreXReference",
        "SlotCentreZReference",
    }
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "SetPrecision3" not in source
    assert "hidden_sketches.curate_view_dimensions" in source


def test_sheet_passes_the_drawing_owned_precision_rule() -> None:
    violations = drawing_specification_violations(
        Path(drawing.__file__).read_text(encoding="utf-8"),
        filename=Path(drawing.__file__).name,
    )
    assert violations == ()
