"""Offline contract for shared MHA-SH-VN-50's InnerLink reference panel."""

from __future__ import annotations

import _chain
import _chain_link
import _config
import draw_pd_paper_drive_assembly as assembly_drawing
import joint_retention

STEM = "sh-vn-chain-link"
NAME = "sh_vn_chain_link"
ROW = _config.parts(STEM)
CONFIGURATION = "InnerLink"
BOM_KEY = f"{STEM}--{CONFIGURATION}"


def test_registry_row_is_the_bought_chain_not_a_machined_part() -> None:
    assert ROW["process"] == "purchased"
    assert ROW["supplier"] == "McMaster-Carr"
    assert ROW["supplier_skus"] == ["6261K171"]
    assert NAME in joint_retention.purchased_parts()
    assert NAME in joint_retention.UNTHREADED_STOCK


def test_quantity_is_half_the_loop_and_matches_the_bom() -> None:
    quantity = int(ROW["configuration_quantities"][CONFIGURATION])
    assert quantity * 2 == _chain.LINK_COUNT == 68
    assert int(ROW["quantity"]) == sum(ROW["configuration_quantities"].values())
    assert assembly_drawing.CHAIN_QUANTITIES[BOM_KEY] == quantity
    assert assembly_drawing.CHAIN_QUANTITIES["pd-vn-chain-connecting-link"] == 1
    assert sum(assembly_drawing.CHAIN_QUANTITIES.values()) == _chain.LINK_COUNT


def test_ordered_chain_is_sufficient_and_minimal_for_the_loop() -> None:
    assert _chain_link.CHAIN_ORDER_FEET * 304.8 >= _chain.LINK_COUNT * _chain.LINK_PITCH
    assert (_chain_link.CHAIN_ORDER_FEET - 1) * 304.8 < (
        _chain.LINK_COUNT * _chain.LINK_PITCH
    )
