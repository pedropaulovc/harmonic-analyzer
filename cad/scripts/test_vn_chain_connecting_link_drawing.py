"""Offline contract for the MHA-VN-068 ANSI #25 connecting link purchased-reference sheet."""

from __future__ import annotations


import _chain_link
import _config
import build_vn_chain_connecting_link as builder
import draw_pd_paper_drive_assembly as assembly_drawing
import draw_vn_chain_connecting_link as draw
import joint_retention
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout

STEM = "vn-chain-connecting-link"
NAME = "vn_chain_connecting_link"
ROW = _config.parts(STEM)


def test_sheet_is_the_registered_purchased_part_reference() -> None:
    spec = DRAWINGS_BY_NAME[NAME]
    assert (spec.part, spec.artifact_stem, spec.script_name) == (
        NAME,
        STEM,
        f"draw_{NAME}.py",
    )
    assert spec.layout is DrawingLayout.LANDSCAPE
    assert "CONNECTING LINK" in draw.ITEM


def test_registry_row_is_the_bought_link_not_a_machined_part() -> None:
    assert ROW["number"] == "MHA-VN-068"
    assert ROW["number"] == assembly_drawing.BOM_PART_NUMBERS[STEM]
    assert ROW["process"] == "purchased"
    assert ROW["supplier"] == "McMaster-Carr"
    assert ROW["supplier_skus"] == [_chain_link.CONNECTING_LINK_SKU] == ["6261K108"]
    assert "6261K108" in ROW["material_specification"]
    assert NAME in joint_retention.purchased_parts()
    assert NAME in joint_retention.UNTHREADED_STOCK


def test_one_closes_the_loop_and_matches_the_bom() -> None:
    assert int(ROW["quantity"]) == 1
    assert assembly_drawing.CHAIN_QUANTITIES[STEM] == 1
    assert assembly_drawing.BOM_DESCRIPTIONS[STEM].endswith("MCMASTER 6261K108")
    assert (
        len(assembly_drawing.BOM_DESCRIPTIONS[STEM])
        <= assembly_drawing.BOM_DESCRIPTION_MAX_CHARS
    )


def test_the_model_is_the_outer_link_stand_in() -> None:
    assert builder.PART_NAME == STEM
    assert _chain_link.CONNECTING_LINK == _chain_link.OUTER_LINK


def test_source_part_stamps_the_purchase_identity() -> None:
    assert _chain_link.stock_properties(STEM) == {
        "Stock Name": ROW["stock_name"],
        "Supplier": "McMaster-Carr",
        "Supplier SKUs": "6261K108",
    }


def test_note_is_one_short_line_naming_what_it_joins() -> None:
    note = _chain_link.DRAWING_NOTES[STEM]
    assert "\n" not in note and len(note) <= 80
    assert " MM" not in note
    assert note.startswith("1 PER LOOP")
    assert f"INNER-LINK ENDS OF THE CUT {_chain_link.CHAIN_SKU}" in note
    # Clip orientation is assembly information, kept on the A-sheet step.
    assert "LEADING" not in note
