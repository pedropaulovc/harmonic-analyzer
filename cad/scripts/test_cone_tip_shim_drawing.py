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
from _drawing_contract import drawing_specification_violations
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import THREAD_MAJOR_MM, blind_cut_dia_mm


def test_pack_is_cut_to_the_block_foot_face_at_the_nominal_stack() -> None:
    """U30 / handoff item 3: the block's width, from its south face to the
    I31 heel relief's inner face (15.0 x 10.47), at SHIM_NOMINAL."""
    assert spec.SHIM_X == block.BLOCK_X
    assert spec.SHIM_SOUTH_Z == pytest.approx(-block.BLOCK_Z / 2.0)
    assert spec.SHIM_NORTH_Z == pytest.approx(
        block.BLOCK_Z / 2.0 - block.HEEL_RELIEF_DEPTH
    )
    assert spec.SHIM_Z == pytest.approx(10.47)
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
    assert spec.SIDE_WEB_MM == pytest.approx(spec.SHIM_NORTH_Z - spec.SLOT_R)
    assert spec.END_WEB_MM >= 2.0
    assert spec.END_WEB_MM == pytest.approx(block.BLOCK_X / 2.0 - spec.SLOT_R)


def test_slot_opens_away_from_the_drum() -> None:
    """Local -X (east) is the accessible 12 mm edge; +X faces the drum."""
    assert spec.SLOT_OPEN_SIDE == -1
    run_end = part.SLOT_OPEN_SIDE * (spec.SHIM_X / 2.0 + part.SLOT_OVERRUN)
    assert run_end < -spec.SHIM_X / 2.0
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
    x, y = drawing.TOP_KEEP["SlotWidth"]
    assert x < drawing.TOP_CENTER[0] - drawing.HALF_X
    assert y == pytest.approx(drawing.SLOT_AXIS_Y)
    # North (the trimmed edge) is at the bottom of the plan, so the axis sits
    # below the view centre by half the trim.
    assert drawing.TOP_CENTER[1] - y == pytest.approx(
        block.HEEL_RELIEF_DEPTH / 2.0 * drawing._S
    )


def test_depth_stands_outside_the_radius_centre_location() -> None:
    assert drawing.TOP_KEEP["Depth"][0] > drawing.TOP_KEEP["SlotCentreZ"][0] + 0.008


def test_slot_location_values_sit_between_their_witnesses() -> None:
    """Each value is mid-span, at least 2 mm off both witness lines."""
    half_w = 0.0065 / 2.0  # three-character value, measured on the tip block
    right = drawing.TOP_CENTER[0] + drawing.HALF_X
    x = drawing.TOP_KEEP["SlotCentreX"][0]
    assert drawing.TOP_CENTER[0] + 0.002 <= x - half_w and x + half_w <= right - 0.002
    lower = drawing.TOP_CENTER[1] - drawing.HALF_Z
    y = drawing.TOP_KEEP["SlotCentreZ"][1]
    assert lower + 0.002 <= y - 0.0019 and y + 0.0019 <= drawing.SLOT_AXIS_Y - 0.002


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
