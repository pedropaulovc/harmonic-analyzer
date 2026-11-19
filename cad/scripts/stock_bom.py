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
no ``ref``) ``unrecorded``.

The output is normalized: one row per part and requirement, ``type`` ``stock``
(a ``[[stock]]`` row, ``ref`` ``#<index>``) or ``tool`` (``ref`` the shop.toml
key), with that requirement's own ``status``. A part without stock reads one
``vendor_sku`` or ``no_stock_record`` stock row, a part without a plan one
``no_traveler`` tool row, and stock allocated to no part closes the table with
its part columns empty.

Usage:
    uv run --frozen python cad/scripts/stock_bom.py [--format md|csv|xlsx] [--out PATH]

``xlsx`` writes the same table to one sheet and needs ``--out``.

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

import xlsxwriter

import _config
import _process_plans
import _telemetry
from _paths import CAD_ROOT

SHOP_EQUIPMENT = CAD_ROOT / "config" / "shop-equipment.toml"
NO_TRAVELER = "no_traveler"
MM_PER_IN = 25.4
REQUIREMENT_COLUMNS = (
    "number",
    "part",
    "kind",
    "quantity",
    "material",
    "type",
    "ref",
    "item",
    "status",
)
# Excel column widths, in characters, for the REQUIREMENT_COLUMNS cells.
XLSX_WIDTHS = (18, 34, 9, 8, 40, 7, 26, 70, 16)


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


class RequirementType(enum.Enum):
    STOCK = "stock"
    TOOL = "tool"


@dataclass(frozen=True)
class Requirement:
    """One stock row or tool a part needs; part fields empty for spare stock."""

    number: str
    part: str
    kind: str
    quantity: str
    material: str
    type: RequirementType
    ref: str
    item: str
    status: str

    def cells(self) -> list[str]:
        return [
            self.number,
            self.part,
            self.kind,
            self.quantity,
            self.material,
            self.type.value,
            self.ref,
            self.item,
            self.status,
        ]


def requirements(lines: list[BomLine], stock: list[StockRow]) -> list[Requirement]:
    """One row per part and stock row or tool, then the stock no part takes.

    A part with no stock row still gets one stock line (``vendor_sku`` naming
    its supplier SKUs, or an empty ``no_stock_record``), and a part with no
    process plan one empty ``no_traveler`` tool line, so every made part
    appears under both types.
    """
    out = []
    for line in lines:
        part = (line.number, line.stem, line.kind, line.quantity, line.material)
        stock_items = [
            (f"#{row.index}", row.description, row.status.value) for row in line.stock
        ]
        if not stock_items:
            skus = ", ".join(line.supplier_skus)
            stock_items = [
                ("", f"supplier SKU {skus}" if skus else "", line.status.value)
            ]
        out += [
            Requirement(*part, RequirementType.STOCK, *item) for item in stock_items
        ]
        if line.tools is None:
            out.append(Requirement(*part, RequirementType.TOOL, "", "", NO_TRAVELER))
            continue
        out += [
            Requirement(
                *part, RequirementType.TOOL, tool.ref, tool.name, tool.status.value
            )
            for tool in line.tools
        ]
    out += [
        Requirement(
            "",
            "",
            "",
            "",
            "",
            RequirementType.STOCK,
            f"#{row.index}",
            row.description,
            row.status.value,
        )
        for row in stock
        if not row.allocated_to
    ]
    return out


def _md_escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def render_markdown(lines: list[BomLine], stock: list[StockRow]) -> str:
    out = io.StringIO()
    counts = {status: 0 for status in PartStockStatus}
    for line in lines:
        counts[line.status] += 1
    out.write("# Stock BOM\n\n")
    out.write(f"{len(lines)} made parts. Part stock status: ")
    out.write(
        ", ".join(f"{status.value}: {count}" for status, count in counts.items())
        + ".\n\n"
    )
    out.write("|" + "|".join(REQUIREMENT_COLUMNS) + "|\n")
    out.write("|" + "---|" * len(REQUIREMENT_COLUMNS) + "\n")
    for row in requirements(lines, stock):
        out.write("|" + "|".join(_md_escape(cell) for cell in row.cells()) + "|\n")
    return out.getvalue()


def render_csv(lines: list[BomLine], stock: list[StockRow]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(REQUIREMENT_COLUMNS)
    writer.writerows(row.cells() for row in requirements(lines, stock))
    return out.getvalue()


class ReadinessState(enum.Enum):
    READY = "ready"
    MISSING = "missing"
    NO_TRAVELER = "no_traveler"


# Statuses that keep a part from being made now. An ``unrecorded`` tool counts:
# the shop's ownership of it is not on record.
MISSING_STOCK = (
    PartStockStatus.NOT_RECEIVED.value,
    PartStockStatus.TO_ORDER.value,
    PartStockStatus.NO_STOCK_RECORD.value,
)
MISSING_TOOLS = (ToolStatus.TO_BUY.value, ToolStatus.UNRECORDED.value)
READINESS_COLUMNS = ("number", "part", "missing_stock", "missing_tools", "state")


@dataclass(frozen=True)
class PartReadiness:
    number: str
    part: str
    missing_stock: int
    missing_tools: int
    state: ReadinessState


def readiness(rows: list[Requirement]) -> list[PartReadiness]:
    """Per part, in BOM order: missing stock rows, missing tools and its state.

    A part without a process plan reads ``no_traveler`` whatever its counts:
    its tools are not known. Otherwise it is ``ready`` only with nothing missing.
    """
    by_part: dict[str, list[Requirement]] = {}
    for row in rows:
        if row.part:
            by_part.setdefault(row.part, []).append(row)
    out = []
    for part, reqs in by_part.items():
        stock = sum(
            r.type is RequirementType.STOCK and r.status in MISSING_STOCK for r in reqs
        )
        tools = sum(
            r.type is RequirementType.TOOL and r.status in MISSING_TOOLS for r in reqs
        )
        state = ReadinessState.READY
        if stock or tools:
            state = ReadinessState.MISSING
        if any(r.status == NO_TRAVELER for r in reqs):
            state = ReadinessState.NO_TRAVELER
        out.append(PartReadiness(reqs[0].number, part, stock, tools, state))
    return out


def _xlsx_list(values: tuple[str, ...]) -> str:
    return "{" + ",".join(f'"{value}"' for value in values) + "}"


def write_xlsx(lines: list[BomLine], stock: list[StockRow], path: Path) -> None:
    """A Readiness sheet of COUNTIFS formulas over the BOM sheet, then the BOM.

    xlsxwriter cannot author a native PivotTable; the formulas keep the summary
    live when the BOM sheet is edited, and carry the values computed here.
    """
    workbook = xlsxwriter.Workbook(str(path))
    header = workbook.add_format({"bold": True})
    cell = workbook.add_format({"text_wrap": True, "valign": "top"})
    summary = workbook.add_worksheet("Readiness")
    sheet = workbook.add_worksheet("BOM")
    sheet.write_row(0, 0, REQUIREMENT_COLUMNS, header)
    rows = requirements(lines, stock)
    quantity = REQUIREMENT_COLUMNS.index("quantity")
    for index, row in enumerate(rows, start=1):
        cells: list = row.cells()
        if row.quantity.isdigit():
            cells[quantity] = int(row.quantity)
        sheet.write_row(index, 0, cells, cell)
    for column, width in enumerate(XLSX_WIDTHS):
        sheet.set_column(column, column, width)
    sheet.freeze_panes(1, 0)
    sheet.autofilter(0, 0, len(rows), len(REQUIREMENT_COLUMNS) - 1)

    last = len(rows) + 1

    def bom_range(name: str) -> str:
        letter = chr(ord("A") + REQUIREMENT_COLUMNS.index(name))
        return f"BOM!${letter}$2:${letter}${last}"

    part, kind, status = bom_range("part"), bom_range("type"), bom_range("status")
    parts = readiness(rows)
    summary.write_row(0, 0, READINESS_COLUMNS, header)
    for index, entry in enumerate(parts, start=1):
        excel_row = index + 1
        match = f"{part},$B{excel_row}"
        summary.write_row(index, 0, (entry.number, entry.part))
        summary.write_formula(
            index,
            2,
            f'=SUM(COUNTIFS({match},{kind},"stock",{status},{_xlsx_list(MISSING_STOCK)}))',
            None,
            entry.missing_stock,
        )
        summary.write_formula(
            index,
            3,
            f'=SUM(COUNTIFS({match},{kind},"tool",{status},{_xlsx_list(MISSING_TOOLS)}))',
            None,
            entry.missing_tools,
        )
        summary.write_formula(
            index,
            4,
            f'=IF(COUNTIFS({match},{status},"{NO_TRAVELER}")>0,"{NO_TRAVELER}",'
            f'IF(C{excel_row}+D{excel_row}>0,"{ReadinessState.MISSING.value}",'
            f'"{ReadinessState.READY.value}"))',
            None,
            entry.state.value,
        )
    for column, width in enumerate((18, 34, 14, 14, 12)):
        summary.set_column(column, column, width)
    summary.freeze_panes(1, 0)
    summary.autofilter(0, 0, len(parts), len(READINESS_COLUMNS) - 1)

    # Parts per state beside the table.
    summary.write_row(0, 6, ("state", "parts"), header)
    states = [entry.state for entry in parts]
    for index, state in enumerate(ReadinessState, start=1):
        summary.write(index, 6, state.value)
        summary.write_formula(
            index,
            7,
            f"=COUNTIF($E$2:$E${len(parts) + 1},G{index + 1})",
            None,
            states.count(state),
        )
    summary.set_column(6, 6, 14)
    workbook.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--format", choices=("md", "csv", "xlsx"), default="md")
    parser.add_argument("--out", type=Path, help="write here instead of stdout")
    args = parser.parse_args(argv)
    if args.format == "xlsx" and args.out is None:
        parser.error("--format xlsx needs --out")

    try:
        stock = load_stock()
        lines = build_bom(_config.parts(), stock, load_tools())
    except InventoryError as exc:
        _telemetry.error(f"stock_bom: {exc}")
        return 2

    if args.format == "xlsx":
        write_xlsx(lines, stock, args.out)
        return 0
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
