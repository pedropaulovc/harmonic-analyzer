"""stock_bom: the process plans' stock and tools stay joined to live registry
parts and inventory keys."""

from __future__ import annotations

import _config
import stock_bom

ON_HAND = stock_bom.StockStatus.ON_HAND
TO_ORDER = stock_bom.StockStatus.TO_ORDER
REGISTRY = {"gear": {"number": "MHA-XX-01", "process": "turned"}}


def test_every_plan_names_a_live_made_part_and_known_stock() -> None:
    # A retired or purchased stem, an unknown stock key, or a tool ref missing
    # from shop.toml raises InventoryError.
    stock_bom.build_bom(_config.parts(), stock_bom.load_stock(), stock_bom.load_plans())


def test_complementary_rows_report_the_missing_stock() -> None:
    stock = {
        "brass": stock_bom.StockRow("brass", "brass bar", ON_HAND),
        "bronze": stock_bom.StockRow("bronze", "bronze bar", TO_ORDER),
        "spare": stock_bom.StockRow("spare", "spare bar", ON_HAND),
    }
    plan = stock_bom.PlanRefs(stock_keys=("brass", "bronze"), tools=())
    (line,) = stock_bom.build_bom(REGISTRY, stock, {"gear": plan})
    assert line.status is stock_bom.PartStockStatus.TO_ORDER
    rows = stock_bom.requirements([line], stock)
    assert [(row.part, row.type.value, row.ref, row.status) for row in rows] == [
        ("gear", "stock", "brass", "on_hand"),
        ("gear", "stock", "bronze", "to_order"),
        ("", "stock", "spare", "on_hand"),
    ]
    (entry,) = stock_bom.readiness(rows)
    assert (entry.missing_stock, entry.missing_tools) == (1, 0)
    assert entry.state is stock_bom.ReadinessState.MISSING


def test_a_part_without_a_plan_reads_no_traveler() -> None:
    (line,) = stock_bom.build_bom(REGISTRY, {}, {})
    assert line.status is stock_bom.PartStockStatus.NO_TRAVELER
    (entry,) = stock_bom.readiness(stock_bom.requirements([line], {}))
    assert entry.state is stock_bom.ReadinessState.NO_TRAVELER


def test_a_plan_naming_unknown_stock_is_refused() -> None:
    plan = stock_bom.PlanRefs(stock_keys=("gone",), tools=())
    try:
        stock_bom.build_bom(REGISTRY, {}, {"gear": plan})
    except stock_bom.InventoryError as exc:
        assert "gone" in str(exc)
    else:
        raise AssertionError("unknown stock key accepted")


def test_a_part_is_ready_only_with_its_stock_and_every_tool_on_hand() -> None:
    stock = {"brass": stock_bom.StockRow("brass", "brass bar", ON_HAND)}
    owned = stock_bom.ToolLine("t", "owned", stock_bom.ToolStatus.ON_HAND)
    unknown = stock_bom.ToolLine("u", "unknown", stock_bom.ToolStatus.UNRECORDED)
    ready = stock_bom.build_bom(
        REGISTRY, stock, {"gear": stock_bom.PlanRefs(("brass",), (owned,))}
    )
    blocked = stock_bom.build_bom(
        REGISTRY, stock, {"gear": stock_bom.PlanRefs(("brass",), (owned, unknown))}
    )
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
        'stock_refs = ["bar"]\n[cad]\npart = "part-a"\n'
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
    plans = stock_bom.load_plans(("part_a",), shop, equipment)
    assert plans["part-a"].stock_keys == ("bar",)
    statuses = [tool.status for tool in plans["part-a"].tools]
    assert statuses == [
        stock_bom.ToolStatus.ON_HAND,
        stock_bom.ToolStatus.TO_BUY,
        stock_bom.ToolStatus.UNRECORDED,
        stock_bom.ToolStatus.UNRECORDED,
    ]
