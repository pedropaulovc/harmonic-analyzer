"""Stock bill of materials: every part the shop makes, joined to the raw stock
recorded for it in cad/config/shop-equipment.toml.

A part is made in the shop when its registry row's ``process`` does not start
with ``purchased`` (cad/config/parts/*.yaml through ``_config.parts``). A
``[[stock]]`` row serves the parts named in its ``allocated_to``; its ``status``
says whether that stock is on hand, bought but not received, or still to
order. Rows allocated to one part are complementary (a cone gear takes brass
and bronze), so the part reads the worst of their statuses. A made part with no
allocated row reads ``vendor_sku`` when its registry row names supplier SKUs
(bought hardware reworked in the shop), otherwise ``no_stock_record``.

Tools come from the part's process plan, never from the inventory: each
enrolled plan (``_process_plans.TRAVELER_STEMS``) lists its ``[[tools]]``, and a
tool's ``ref`` names its cad/process/shop.toml ``tools`` key. Ownership reads
the same key in shop-equipment.toml's ``tools`` table: ``present = true`` is
``on_hand``, ``present = false`` ``to_buy``, and no record (or a plan tool with
no ``ref``) ``unrecorded``. A part without a plan reads ``no traveler``.

Usage:
    uv run --frozen python cad/scripts/stock_bom.py [--format md|csv] [--out PATH]

Exits 2 when a row allocates a stem that is not in the registry or is a
purchased part, carries an unknown status, or a plan names an unknown or
purchased part or a tool ``ref`` missing from shop.toml: the inventory and the
plans must not point at a retired or bought identity.
"""

from __future__ import annotations

import argparse
import csv
import enum
import io
import sys
import tomllib
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import _config
import _process_plans
import _telemetry
from _paths import CAD_ROOT

SHOP_EQUIPMENT = CAD_ROOT / "config" / "shop-equipment.toml"
NO_TRAVELER = "no traveler"
MM_PER_IN = 25.4


class StockStatus(enum.Enum):
    ON_HAND = "on_hand"
    NOT_RECEIVED = "not_received"
    TO_ORDER = "to_order"


class PartStockStatus(enum.Enum):
    """A part's stock state; declaration order runs from complete to missing."""

    ON_HAND = "on_hand"
    NOT_RECEIVED = "not_received"
    TO_ORDER = "to_order"
    VENDOR_SKU = "vendor_sku"
    NO_STOCK_RECORD = "no_stock_record"


class ToolStatus(enum.Enum):
    ON_HAND = "on_hand"
    TO_BUY = "to_buy"
    UNRECORDED = "unrecorded"


@dataclass(frozen=True)
class ToolLine:
    ref: str
    name: str
    status: ToolStatus


@dataclass(frozen=True)
class StockRow:
    index: int
    description: str
    status: StockStatus
    allocated_to: tuple[str, ...]


@dataclass(frozen=True)
class BomLine:
    stem: str
    number: str
    kind: str
    quantity: str
    material: str
    stock: tuple[StockRow, ...]
    supplier_skus: tuple[str, ...]
    status: PartStockStatus
    # None: the part has no process plan, so its tools are not recorded.
    tools: tuple[ToolLine, ...] | None


class InventoryError(ValueError):
    pass


def _inch(value_in: float) -> str:
    """Nominal inch size as a fraction when it is a 1/64 multiple, else 3 places."""
    sixty_fourths = round(value_in * 64)
    if abs(sixty_fourths / 64 - value_in) > 1e-6:
        return f"{value_in:.3f}"
    whole, rest = divmod(Fraction(sixty_fourths, 64), 1)
    if rest == 0:
        return str(whole)
    if whole == 0:
        return str(rest)
    return f"{whole}-{rest}"


def _size(row: dict) -> str:
    if "section_mm" in row:
        width, thick = row["section_mm"]
        return f"{_inch(thick / MM_PER_IN)} x {_inch(width / MM_PER_IN)}"
    if "dia_in" in row:
        return " / ".join(f"Ø{_inch(d)}" for d in row["dia_in"])
    if "across_flats_mm" in row:
        return f"{_inch(row['across_flats_mm'] / MM_PER_IN)} hex"
    if "od_mm" in row:
        return f"{_inch(row['od_mm'] / MM_PER_IN)} OD x {row['wall_mm'] / MM_PER_IN:.3f} wall"
    return ""


def _length(row: dict) -> str:
    if "length_mm" in row:
        lengths = [row["length_mm"] / MM_PER_IN]
    else:
        lengths = row.get("length_in", [])
    text = " / ".join(f"{_inch(length)} in" for length in lengths)
    pieces = row.get("pieces")
    if pieces is None:
        return text
    return f"{pieces} x {text}" if text else f"{pieces} pcs"


def _describe(row: dict) -> str:
    form = row["form"].replace("_", " ")
    parts = [row["material"], form, _size(row), _length(row)]
    return ", ".join(part for part in parts if part)


def load_stock(path: Path = SHOP_EQUIPMENT) -> list[StockRow]:
    document = tomllib.loads(path.read_text(encoding="utf-8"))
    rows = []
    for index, row in enumerate(document["stock"]):
        try:
            status = StockStatus(row["status"])
        except (KeyError, ValueError) as exc:
            raise InventoryError(
                f"[[stock]] #{index}: bad status {row.get('status')!r}"
            ) from exc
        rows.append(
            StockRow(
                index=index,
                description=_describe(row),
                status=status,
                allocated_to=tuple(row.get("allocated_to", ())),
            )
        )
    return rows


def _tool_status(record: dict | None) -> ToolStatus:
    if record is None or "present" not in record:
        return ToolStatus.UNRECORDED
    if record["present"] is True:
        return ToolStatus.ON_HAND
    return ToolStatus.TO_BUY


def load_tools(
    stems: tuple[str, ...] = _process_plans.TRAVELER_STEMS,
    shop_path: Path = _process_plans.SHOP_PATH,
    equipment_path: Path = SHOP_EQUIPMENT,
) -> dict[str, tuple[ToolLine, ...]]:
    """Registry stem -> the tools its process plan lists, in plan order."""
    shop_tools = tomllib.loads(shop_path.read_text(encoding="utf-8"))["tools"]
    owned = tomllib.loads(equipment_path.read_text(encoding="utf-8"))["tools"]
    errors = []
    by_part = {}
    for stem in stems:
        plan_file = _process_plans.plan_path(stem)
        plan = tomllib.loads(plan_file.read_text(encoding="utf-8"))
        tools = []
        for tool in plan.get("tools", ()):
            ref = tool.get("ref", "")
            if ref and ref not in shop_tools:
                errors.append(
                    f"{plan_file.parent.name}: tool ref {ref!r} not in shop.toml"
                )
                continue
            record = owned.get(ref) if ref else None
            tools.append(
                ToolLine(ref=ref, name=tool["name"], status=_tool_status(record))
            )
        by_part[plan["cad"]["part"]] = tuple(tools)
    if errors:
        raise InventoryError("; ".join(errors))
    return by_part


def _is_made(row: dict) -> bool:
    return not str(row.get("process", "")).startswith("purchased")


def _part_status(
    stock: tuple[StockRow, ...], supplier_skus: tuple[str, ...]
) -> PartStockStatus:
    if stock:
        statuses = (PartStockStatus(row.status.value) for row in stock)
        return max(statuses, key=list(PartStockStatus).index)
    if supplier_skus:
        return PartStockStatus.VENDOR_SKU
    return PartStockStatus.NO_STOCK_RECORD


def build_bom(
    registry: dict[str, dict],
    stock: list[StockRow],
    tools: dict[str, tuple[ToolLine, ...]],
) -> list[BomLine]:
    made = {stem: row for stem, row in registry.items() if _is_made(row)}
    errors = [
        f"process plan for {'unknown' if stem not in registry else 'purchased'} part {stem!r}"
        for stem in tools
        if stem not in made
    ]
    by_stem: dict[str, list[StockRow]] = {stem: [] for stem in made}
    for row in stock:
        for stem in row.allocated_to:
            if stem not in registry:
                errors.append(f"[[stock]] #{row.index} allocates unknown part {stem!r}")
                continue
            if stem not in made:
                errors.append(
                    f"[[stock]] #{row.index} allocates purchased part {stem!r}"
                )
                continue
            by_stem[stem].append(row)
    if errors:
        raise InventoryError("; ".join(errors))

    lines = []
    for stem in sorted(made, key=lambda s: str(made[s].get("number", s))):
        row = made[stem]
        rows = tuple(by_stem[stem])
        skus = tuple(row.get("supplier_skus", ()))
        quantity = row.get("quantity")
        lines.append(
            BomLine(
                stem=stem,
                number=str(row.get("number", "")),
                kind="fixture" if "-tl-" in stem else "machine",
                quantity="" if quantity is None else str(quantity),
                material=str(
                    row.get("material_specification") or row.get("material") or ""
                ),
                stock=rows,
                supplier_skus=skus,
                status=_part_status(rows, skus),
                tools=tools.get(stem),
            )
        )
    return lines


def _stock_cell(line: BomLine) -> str:
    if line.stock:
        return "; ".join(
            f"#{row.index} {row.description} [{row.status.value}]" for row in line.stock
        )
    if line.supplier_skus:
        return "supplier SKU " + ", ".join(line.supplier_skus)
    return ""


def _tools_cell(line: BomLine) -> str:
    if line.tools is None:
        return NO_TRAVELER
    return "; ".join(f"{tool.name} [{tool.status.value}]" for tool in line.tools)


def _md_escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def render_markdown(lines: list[BomLine], stock: list[StockRow]) -> str:
    out = io.StringIO()
    counts = {status: 0 for status in PartStockStatus}
    for line in lines:
        counts[line.status] += 1
    out.write("# Stock BOM\n\n")
    out.write(f"{len(lines)} made parts. ")
    out.write(
        ", ".join(f"{status.value}: {count}" for status, count in counts.items())
        + ".\n\n"
    )
    out.write(
        "|Number|Part|Kind|Qty|Status|Material (registry)|Stock (shop-equipment.toml)"
        "|Tools (process plan)|\n"
    )
    out.write("|---|---|---|---|---|---|---|---|\n")
    for line in lines:
        cells = [
            line.number,
            line.stem,
            line.kind,
            line.quantity,
            line.status.value,
            line.material,
            _stock_cell(line),
            _tools_cell(line),
        ]
        out.write("|" + "|".join(_md_escape(cell) for cell in cells) + "|\n")
    spare = [row for row in stock if not row.allocated_to]
    if spare:
        out.write(
            "\n## Stock allocated to no part\n\n|Row|Stock|Status|\n|---|---|---|\n"
        )
        for row in spare:
            out.write(
                f"|#{row.index}|{_md_escape(row.description)}|{row.status.value}|\n"
            )
    return out.getvalue()


def render_csv(lines: list[BomLine], stock: list[StockRow]) -> str:
    """Part lines, then each unallocated row with an empty part column."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(
        ["number", "part", "kind", "quantity", "status", "material", "stock", "tools"]
    )
    for line in lines:
        writer.writerow(
            [
                line.number,
                line.stem,
                line.kind,
                line.quantity,
                line.status.value,
                line.material,
                _stock_cell(line),
                _tools_cell(line),
            ]
        )
    for row in stock:
        if row.allocated_to:
            continue
        writer.writerow(
            [
                "",
                "",
                "",
                "",
                row.status.value,
                "",
                f"#{row.index} {row.description}",
                "",
            ]
        )
    return out.getvalue()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--format", choices=("md", "csv"), default="md")
    parser.add_argument("--out", type=Path, help="write here instead of stdout")
    args = parser.parse_args(argv)

    try:
        stock = load_stock()
        lines = build_bom(_config.parts(), stock, load_tools())
    except InventoryError as exc:
        _telemetry.error(f"stock_bom: {exc}")
        return 2

    if args.format == "md":
        text = render_markdown(lines, stock)
    else:
        text = render_csv(lines, stock)
    if args.out is None:
        sys.stdout.write(text)
        return 0
    args.out.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
