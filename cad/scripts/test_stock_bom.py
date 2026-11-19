"""stock_bom: the process plans' stock and tools stay joined to live registry
parts and inventory keys."""

from __future__ import annotations

import zipfile

import pytest

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
    assert line.placeholder is None
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
    assert line.placeholder is stock_bom.StockPlaceholder.NO_TRAVELER
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


def test_a_part_is_bought_by_vendor_identity_not_process_text() -> None:
    # Bought hardware with added machining is made; a -vn- stem is bought, so
    # a plan for it is refused.
    registry = {
        "xx-reworked-screw": {
            "number": "MHA-XX-02",
            "process": "purchased screw; ream",
        },
        "xx-vn-pin": {"number": "MHA-XX-VN-03", "process": "turned"},
    }
    (line,) = stock_bom.build_bom(registry, {}, {})
    assert line.stem == "xx-reworked-screw"
    plan = stock_bom.PlanRefs(stock_keys=(), tools=())
    with pytest.raises(stock_bom.InventoryError, match="purchased part 'xx-vn-pin'"):
        stock_bom.build_bom(registry, {}, {"xx-vn-pin": plan})


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
        '[[tools]]\nid = "d"\nname = "described"\ndescription = "x"\n'
        '[[tools]]\nid = "e"\nname = "to make"\nref = "t-make"\n',
        encoding="utf-8",
    )
    shop = tmp_path / "shop.toml"
    shop.write_text(
        "[tools.t-owned]\n[tools.t-buy]\n[tools.t-shop]\n[tools.t-make]\n",
        encoding="utf-8",
    )
    equipment = tmp_path / "equipment"
    equipment.mkdir()
    (equipment / "tools.toml").write_text(
        '[tools.t-owned]\nstatus = "on_hand"\n[tools.t-buy]\nstatus = "to_order"\n'
        '[tools.t-make]\nstatus = "to_make"\nsupply = "shop_made"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(stock_bom._process_plans, "PROCESS_ROOT", tmp_path)
    plans = stock_bom.load_plans(("part_a",), shop, equipment)
    assert plans["part-a"].stock_keys == ("bar",)
    statuses = [tool.status for tool in plans["part-a"].tools]
    assert statuses == [
        stock_bom.ToolStatus.ON_HAND,
        stock_bom.ToolStatus.TO_ORDER,
        stock_bom.ToolStatus.UNRECORDED,
        stock_bom.ToolStatus.UNRECORDED,
        stock_bom.ToolStatus.TO_MAKE,
    ]
    # Every status but on_hand keeps the part from being made.
    assert set(stock_bom.MISSING_TOOLS) == {
        status.value for status in stock_bom.ToolStatus
    } - {"on_hand"}


def test_an_unknown_tool_status_is_refused(tmp_path, monkeypatch) -> None:
    plan_dir = tmp_path / "part_a"
    plan_dir.mkdir()
    (plan_dir / "plan.toml").write_text(
        '[cad]\npart = "part-a"\n[[tools]]\nid = "a"\nname = "x"\nref = "t"\n',
        encoding="utf-8",
    )
    shop = tmp_path / "shop.toml"
    shop.write_text("[tools.t]\n", encoding="utf-8")
    equipment = tmp_path / "equipment"
    equipment.mkdir()
    (equipment / "tools.toml").write_text(
        '[tools.t]\nstatus = "to_buy"\n', encoding="utf-8"
    )
    monkeypatch.setattr(stock_bom._process_plans, "PROCESS_ROOT", tmp_path)
    with pytest.raises(stock_bom.InventoryError, match="to_buy"):
        stock_bom.load_plans(("part_a",), shop, equipment)


def _plan_dir(tmp_path, monkeypatch, plan: str, shop: str, equipment: str):
    (tmp_path / "part_a").mkdir()
    (tmp_path / "part_a" / "plan.toml").write_text(plan, encoding="utf-8")
    (tmp_path / "shop.toml").write_text(shop, encoding="utf-8")
    (tmp_path / "equipment").mkdir()
    (tmp_path / "equipment" / "inventory.toml").write_text(equipment, encoding="utf-8")
    monkeypatch.setattr(stock_bom._process_plans, "PROCESS_ROOT", tmp_path)
    return tmp_path / "shop.toml", tmp_path / "equipment"


def test_tools_and_gauges_read_ownership_from_any_inventory_section(
    tmp_path, monkeypatch
) -> None:
    shop, equipment = _plan_dir(
        tmp_path,
        monkeypatch,
        '[cad]\npart = "gear"\n'
        '[[tools]]\nid = "a"\nname = "fixture"\nref = "t-fixture"\n'
        '[[tools]]\nid = "b"\nname = "tape"\nref = "t-tape"\n'
        '[[setups]]\ngauge_checks = [{ gauge = "g-owned" }]\n'
        "[[setups.operations]]\n"
        'gauge_checks = [{ gauge = "g-buy" }, { gauge = "g-owned" }]\n'
        "[[setups.operations]]\n"
        'gauge_checks = [{ gauge = "g-shop" }]\n',
        "[tools.t-fixture]\n[tools.t-tape]\n"
        "[gauges.g-owned]\n[gauges.g-buy]\n[gauges.g-shop]\n",
        '[fixtures.t-fixture]\nstatus = "to_make"\n'
        '[consumables.t-tape]\nstatus = "on_hand"\n'
        '[gauges.g-owned]\nstatus = "on_hand"\n'
        '[gauges.g-buy]\nstatus = "to_order"\n',
    )
    plan = stock_bom.load_plans(("part_a",), shop, equipment)["part-a"]
    assert [(t.ref, t.status.value) for t in plan.tools] == [
        ("t-fixture", "to_make"),
        ("t-tape", "on_hand"),
    ]
    # Setup and operation checks, in plan order, each gauge once; a shop.toml
    # gauge with no inventory record is unrecorded.
    assert [(g.ref, g.status.value) for g in plan.gauges] == [
        ("g-owned", "on_hand"),
        ("g-buy", "to_order"),
        ("g-shop", "unrecorded"),
    ]
    stock = {"brass": stock_bom.StockRow("brass", "brass bar", ON_HAND)}
    plan = stock_bom.PlanRefs(("brass",), (), plan.gauges)
    rows = stock_bom.requirements(
        stock_bom.build_bom(REGISTRY, stock, {"gear": plan}), stock
    )
    assert [(r.type.value, r.ref) for r in rows][1:] == [
        ("gauge", "g-owned"),
        ("gauge", "g-buy"),
        ("gauge", "g-shop"),
    ]
    (entry,) = stock_bom.readiness(rows)
    assert (entry.missing_stock, entry.missing_tools, entry.missing_gauges) == (0, 0, 2)
    assert entry.state is stock_bom.ReadinessState.MISSING


@pytest.mark.parametrize(
    ("shop", "equipment", "message"),
    [
        ("[tools.t]\n", "", "gauge ref 'g' not in shop.toml"),
        (
            "[tools.t]\n[gauges.g]\n",
            '[tools.g]\nstatus = "on_hand"\n[gauges.g]\nstatus = "on_hand"\n',
            "'g' is in tools and gauges",
        ),
    ],
)
def test_an_unknown_gauge_or_a_key_owned_twice_is_refused(
    tmp_path, monkeypatch, shop, equipment, message
) -> None:
    paths = _plan_dir(
        tmp_path,
        monkeypatch,
        '[cad]\npart = "gear"\n[[setups]]\ngauge_checks = [{ gauge = "g" }]\n',
        shop,
        equipment,
    )
    with pytest.raises(stock_bom.InventoryError, match=message):
        stock_bom.load_plans(("part_a",), *paths)


def test_the_readiness_sheet_counts_missing_gauges(tmp_path) -> None:
    stock = {"brass": stock_bom.StockRow("brass", "brass bar", ON_HAND)}
    gauge = stock_bom.ToolLine("g", "g", stock_bom.ToolStatus.TO_ORDER)
    lines = stock_bom.build_bom(
        REGISTRY, stock, {"gear": stock_bom.PlanRefs(("brass",), (), (gauge,))}
    )
    path = tmp_path / "bom.xlsx"
    stock_bom.write_xlsx(lines, stock, path)
    with zipfile.ZipFile(path) as book:
        sheet = book.read("xl/worksheets/sheet1.xml").decode("utf-8")
    # The gauge count (E2) is a COUNTIFS over the BOM's gauge rows, and it
    # feeds the state (F2).
    assert ',"gauge",' in sheet
    assert '<c r="E2"><f>' in sheet and "<v>1</v></c>" in sheet
    assert "C2+D2+E2&gt;0" in sheet
    assert "<v>missing</v>" in sheet


def test_a_placeholder_plans_tools_appear_unenrolled(tmp_path, monkeypatch) -> None:
    # Every plan under cad/process counts, enrolled or not, named by its
    # directory.
    shop, equipment = _plan_dir(
        tmp_path,
        monkeypatch,
        'revision = "placeholder"\n[[tools]]\nid = "pins"\nname = "pins"\nref = "pins"\n',
        '[tools.pins]\ndescription = "pin gauges"\n',
        '[gauges.pins]\nstatus = "to_order"\n',
    )
    monkeypatch.setattr(stock_bom._process_plans, "TRAVELER_STEMS", ())
    plans = stock_bom.load_plans(shop_path=shop, equipment_dir=equipment)
    assert plans["part-a"].tools == (
        stock_bom.ToolLine("pins", "pins", stock_bom.ToolStatus.TO_ORDER),
    )
