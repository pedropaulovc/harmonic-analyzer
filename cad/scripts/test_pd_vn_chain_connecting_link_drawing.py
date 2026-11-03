"""Offline contract for the MHA-PD-VN-66 ANSI #25 connecting link purchased-reference sheet."""

from __future__ import annotations

import _chain_link
import _config
import draw_pd_paper_drive_assembly as assembly_drawing
import joint_retention
import sh_vn_chain_link_spec as chain

STEM = "pd-vn-chain-connecting-link"
NAME = "pd_vn_chain_connecting_link"
ROW = _config.parts(STEM)


def test_registry_row_is_the_bought_link_not_a_machined_part() -> None:
    assert ROW["number"] == "MHA-PD-VN-66"
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


def test_the_model_is_the_outer_link_stand_in() -> None:
    assert _chain_link.CONNECTING_LINK == chain.OUTER_LINK


def test_link_builder_sets_the_package_unit_first(monkeypatch) -> None:
    # Codjiflo (#2148): the inch package's builder sets its document units
    # right after create_part, before any reference, sketch or feature.
    import asyncio

    calls: list[object] = []

    class _Adapter:
        async def create_part(self):
            calls.append("create_part")
            return "created"

    class _Stop(Exception):
        pass

    def units(_adapter, unit, *, label):
        calls.append(("units", unit, label))
        raise _Stop

    async def references(_adapter):
        calls.append("references")

    monkeypatch.setattr(_chain_link, "check", lambda _label, result: result)
    monkeypatch.setattr(_chain_link, "apply_package_model_units", units)
    monkeypatch.setattr(_chain_link, "author_link_references", references)
    try:
        asyncio.run(
            _chain_link.build_link(
                _Adapter(),
                part_name="pd-vn-chain-connecting-link",
                material="Plain Carbon Steel",
                **_chain_link.CONNECTING_LINK,
            )
        )
    except _Stop:
        pass
    assert calls == [
        "create_part",
        ("units", "in", "pd-vn-chain-connecting-link"),
    ]
