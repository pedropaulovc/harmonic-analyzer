"""stock_bom: the shop's [[stock]] allocations and the process plans' tools stay
joined to live registry parts."""

from __future__ import annotations

import _config
import stock_bom


def test_every_allocation_and_plan_names_a_live_made_part() -> None:
    # A retired or purchased stem, or a tool ref missing from shop.toml, raises
    # InventoryError.
    stock_bom.build_bom(_config.parts(), stock_bom.load_stock(), stock_bom.load_tools())


def test_complementary_rows_report_the_missing_stock() -> None:
    registry = {"gear": {"number": "MHA-XX-01", "process": "turned"}}
    stock = [
        stock_bom.StockRow(0, "brass", stock_bom.StockStatus.ON_HAND, ("gear",)),
        stock_bom.StockRow(1, "bronze", stock_bom.StockStatus.TO_ORDER, ("gear",)),
    ]
    (line,) = stock_bom.build_bom(registry, stock, {})
    assert line.status is stock_bom.PartStockStatus.TO_ORDER
    assert line.tools is None


def test_tool_ownership_follows_the_shared_equipment_key(tmp_path, monkeypatch) -> None:
    plan_dir = tmp_path / "part_a"
    plan_dir.mkdir()
    (plan_dir / "plan.toml").write_text(
        '[cad]\npart = "part-a"\n'
        '[[tools]]\nid = "a"\nname = "owned"\nref = "t-owned"\n'
        '[[tools]]\nid = "b"\nname = "to buy"\nref = "t-buy"\n'
        '[[tools]]\nid = "c"\nname = "shop only"\nref = "t-shop"\n'
        '[[tools]]\nid = "d"\nname = "described"\ndescription = "x"\n',
        encoding="utf-8",
    )
    shop = tmp_path / "shop.toml"
    shop.write_text(
        "[tools.t-owned]\n[tools.t-buy]\n[tools.t-shop]\n", encoding="utf-8"
    )
    equipment = tmp_path / "equipment.toml"
    equipment.write_text(
        "[tools.t-owned]\npresent = true\n[tools.t-buy]\npresent = false\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(stock_bom._process_plans, "PROCESS_ROOT", tmp_path)
    tools = stock_bom.load_tools(("part_a",), shop, equipment)
    statuses = [tool.status for tool in tools["part-a"]]
    assert statuses == [
        stock_bom.ToolStatus.ON_HAND,
        stock_bom.ToolStatus.TO_BUY,
        stock_bom.ToolStatus.UNRECORDED,
        stock_bom.ToolStatus.UNRECORDED,
    ]
