"""Offline contract for shared MHA-SH-VN-50's OuterLink reference panel."""

from __future__ import annotations

import _chain
import _config
import draw_pd_paper_drive_assembly as assembly_drawing
import joint_retention

STEM = "sh-vn-chain-link"
NAME = "sh_vn_chain_link"
ROW = _config.parts(STEM)
CONFIGURATION = "OuterLink"
BOM_KEY = f"{STEM}--{CONFIGURATION}"


def test_registry_row_is_the_bought_chain_not_a_machined_part() -> None:
    assert ROW["process"] == "purchased"
    assert ROW["supplier"] == "McMaster-Carr"
    assert ROW["supplier_skus"] == ["6261K171"]
    assert NAME in joint_retention.purchased_parts()
    assert NAME in joint_retention.UNTHREADED_STOCK


def test_quantity_is_one_short_of_half_the_loop_and_matches_the_bom() -> None:
    quantity = int(ROW["configuration_quantities"][CONFIGURATION])
    # The connecting link (MHA-PD-VN-66) is the loop's last outer link.
    assert quantity * 2 + 2 == _chain.LINK_COUNT == 66
    assert int(ROW["quantity"]) == sum(ROW["configuration_quantities"].values())
    assert assembly_drawing.CHAIN_QUANTITIES[BOM_KEY] == quantity
    assert assembly_drawing.CHAIN_QUANTITIES["pd-vn-chain-connecting-link"] == 1
    assert sum(assembly_drawing.CHAIN_QUANTITIES.values()) == _chain.LINK_COUNT
