"""Offline contract for the MHA-PD-VN-50 ANSI #25 inner link purchased-reference sheet."""

from __future__ import annotations

import asyncio

import _chain
import _chain_link
import _config
import draw_pd_paper_drive_assembly as assembly_drawing
import draw_sh_vn_chain_link as draw
import joint_retention
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout

STEM = "pd-vn-chain-inner-link"
NAME = "pd_vn_chain_inner_link"
ROW = _config.parts(STEM)


def test_sheet_is_the_registered_purchased_part_reference(monkeypatch) -> None:
    spec = DRAWINGS_BY_NAME[NAME]
    assert (spec.part, spec.artifact_stem, spec.script_name) == (
        NAME,
        STEM,
        f"draw_{NAME}.py",
    )
    assert spec.layout is DrawingLayout.LANDSCAPE
    calls = []

    async def fake(adapter, drawn, *, item, cut_to_suit=False):
        calls.append((adapter, drawn, item, cut_to_suit))
        return {"pdf": "x"}

    monkeypatch.setattr(draw, "build_purchased_part_drawing", fake)
    adapter = object()
    assert asyncio.run(draw.build(adapter)) == {"pdf": "x"}
    assert calls == [(adapter, spec, draw.ITEM, True)]
    assert "INNER LINK" in draw.ITEM


def test_registry_row_is_the_bought_chain_not_a_machined_part() -> None:
    assert ROW["number"] == assembly_drawing.BOM_PART_NUMBERS[STEM]
    assert ROW["process"] == "purchased"
    assert ROW["supplier"] == "McMaster-Carr"
    assert ROW["supplier_skus"] == ["6261K171"]
    for sku in ROW["supplier_skus"]:
        assert sku in ROW["material_specification"]
    assert NAME in joint_retention.purchased_parts()
    assert NAME in joint_retention.UNTHREADED_STOCK


def test_quantity_is_half_the_loop_and_matches_the_bom() -> None:
    quantity = int(ROW["quantity"])
    assert quantity * 2 == _chain.LINK_COUNT
    assert assembly_drawing.CHAIN_QUANTITIES[STEM] == quantity
    assert assembly_drawing.BOM_DESCRIPTIONS[STEM].endswith(
        f"MCMASTER {ROW['supplier_skus'][0]}"
    )


def test_source_part_stamps_the_purchase_identity() -> None:
    assert _chain_link.stock_properties(STEM) == {
        "Stock Name": ROW["stock_name"],
        "Supplier": "McMaster-Carr",
        "Supplier SKUs": ", ".join(ROW["supplier_skus"]),
    }
    assert set(_chain_link.stock_properties(STEM)) < set(_chain_link.DRAWING_PROPERTIES)
    assert "Manufacturing Notes" in _chain_link.DRAWING_PROPERTIES


def test_note_is_one_short_line_that_closes_the_loop_count() -> None:
    note = _chain_link.DRAWING_NOTES[STEM]
    assert "\n" not in note and len(note) <= 80
    assert " MM" not in note
    quantity = int(ROW["quantity"])
    # Broken to whole links, an inner link at each end; the connecting link
    # (MHA-PD-VN-66, the loop's last outer link) closes the loop's pitch count.
    assert (
        f"{_chain_link.CHAIN_SKU} TO {quantity} INNER + {quantity - 1} OUTER LINKS"
        in note
    )
    assert (
        f"{_chain_link.CONNECTING_LINK_SKU} CLOSES {_chain.LINK_COUNT} PITCHES" in note
    )
    assert quantity + quantity == _chain.LINK_COUNT
    assert _chain_link.CHAIN_ORDER_FEET * 304.8 >= _chain.LINK_COUNT * _chain.LINK_PITCH
