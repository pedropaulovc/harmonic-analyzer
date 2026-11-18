"""stock_bom: the shop's [[stock]] allocations stay joined to live registry parts."""

from __future__ import annotations

import _config
import stock_bom


def test_every_allocation_names_a_live_made_part() -> None:
    # A retired or purchased stem in allocated_to raises InventoryError.
    stock_bom.build_bom(_config.parts(), stock_bom.load_stock())


def test_complementary_rows_report_the_missing_stock() -> None:
    registry = {"gear": {"number": "MHA-XX-01", "process": "turned"}}
    stock = [
        stock_bom.StockRow(0, "brass", stock_bom.StockStatus.ON_HAND, ("gear",)),
        stock_bom.StockRow(1, "bronze", stock_bom.StockStatus.TO_ORDER, ("gear",)),
    ]
    (line,) = stock_bom.build_bom(registry, stock)
    assert line.status is stock_bom.PartStockStatus.TO_ORDER
