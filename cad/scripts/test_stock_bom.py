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
    rows = stock_bom.requirements([line], stock)
    assert [(row.type.value, row.ref, row.status) for row in rows] == [
        ("stock", "#0", "on_hand"),
        ("stock", "#1", "to_order"),
        ("tool", "", "no_traveler"),
    ]
    (entry,) = stock_bom.readiness(rows)
    assert (entry.missing_stock, entry.missing_tools) == (1, 0)
    assert entry.state is stock_bom.ReadinessState.NO_TRAVELER


def test_a_part_is_ready_only_with_its_stock_and_every_tool_on_hand() -> None:
    registry = {"gear": {"number": "MHA-XX-01", "process": "turned"}}
    stock = [stock_bom.StockRow(0, "brass", stock_bom.StockStatus.ON_HAND, ("gear",))]
    owned = stock_bom.ToolLine("t", "owned", stock_bom.ToolStatus.ON_HAND)
    unknown = stock_bom.ToolLine("u", "unknown", stock_bom.ToolStatus.UNRECORDED)
    ready = stock_bom.build_bom(registry, stock, {"gear": (owned,)})
    blocked = stock_bom.build_bom(registry, stock, {"gear": (owned, unknown)})
    (ready_entry,) = stock_bom.readiness(stock_bom.requirements(ready, stock))
    (blocked_entry,) = stock_bom.readiness(stock_bom.requirements(blocked, stock))
    assert ready_entry.state is stock_bom.ReadinessState.READY
    assert (blocked_entry.missing_tools, blocked_entry.state) == (
        1,
        stock_bom.ReadinessState.MISSING,
    )


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
