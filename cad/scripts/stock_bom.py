"""Stock bill of materials: every part the shop makes, with the stock, tools
and gauges its process plan names.

A part is made in the shop unless its stem names a vendor identity (``-vn-``,
cad/docs/subsystem-identities.md): a vendor part is bought finished, cut to
length at most, while bought hardware with added machining is a made part
whatever its registry ``process`` text says (cad/config/parts/*.yaml through
``_config.parts``). Parts
point at what they need from their process plans, never the other way round:
every plan under cad/process (``<stem>/plan.toml``: the enrolled plans of
``_process_plans.TRAVELER_STEMS`` and the placeholder plans that only list a
part's tools until its traveler is written; the directory names the part,
``<stem>`` with ``_`` for ``-``, or a family of parts made on one plan, which
names each under ``[[parts]]``, ``_process_plans.family_parts``) names its
stock in ``stock_refs`` (keys of the
cad/config/shop-equipment/ ``[stock.<key>]`` rows) and its tools in
``[[tools]]``, whose ``ref`` is a ``tools`` key of the shop directory
cad/process/shop/ (``_process_plans.load_shop``), and its gauges in the
setups' and operations' ``gauge_checks``, whose ``gauge`` is a shop
``gauges`` key. A stock row's ``status`` says whether
it is on hand, bought but not received, or still to order. A tool's or gauge's
ownership reads the same key in the inventory (``_shop_equipment.load``),
in whichever of its ``tools``, ``fixtures``, ``consumables``, ``gauges`` and
``holders`` sections holds it: its ``status`` (``on_hand``, ``not_received``,
``to_order`` or ``to_make``), or ``unrecorded`` when there is no record, the
record has no status, or the plan tool has no ``ref``. A part without stock
reads one placeholder stock row:
``vendor_sku`` when its registry row names supplier SKUs (bought hardware
reworked in the shop) and its plan names no stock, ``no_stock_record`` for any
other part with a plan but no stock, ``no_traveler`` for a part without a plan.

The output is normalized: one row per part and requirement, ``type`` ``stock``
(``ref`` the stock key), ``tool`` or ``gauge`` (``ref`` the shop key),
with that requirement's own ``status``. A part without stock reads one stock
row with its placeholder status, a part without a plan one ``no_traveler``
tool row, and stock no plan names closes the table with its part columns
empty. The md summary line counts the parts ``ready``, ``missing`` and
``no_traveler`` (``readiness``): a part is ready only with no stock, tool or
gauge missing.

Usage:
    uv run --frozen python cad/scripts/stock_bom.py [--format md|csv|xlsx] [--out PATH]

``xlsx`` writes a Readiness sheet and the table and needs ``--out``.

Exits 2 when a stock row or an inventory record carries an unknown status, an
inventory key sits in two ownership sections, or a plan names an unknown or
vendor (``-vn-``) part, an unknown stock key, or a tool ``ref`` or gauge missing from
the shop: the plans must not point at a retired or bought identity.
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
import _shop_equipment
import _telemetry

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


class StockPlaceholder(enum.Enum):
    """The status of the one stock row a part with no stock row reads."""

    VENDOR_SKU = "vendor_sku"
    NO_STOCK_RECORD = "no_stock_record"
    NO_TRAVELER = "no_traveler"


class ToolStatus(enum.Enum):
    ON_HAND = "on_hand"
    NOT_RECEIVED = "not_received"
    TO_ORDER = "to_order"
    TO_MAKE = "to_make"
    UNRECORDED = "unrecorded"


@dataclass(frozen=True)
class ToolLine:
    ref: str
    name: str
    status: ToolStatus


@dataclass(frozen=True)
class StockRow:
    key: str
    description: str
    status: StockStatus


@dataclass(frozen=True)
class PlanRefs:
    """What one process plan points at, in plan order."""

    stock_keys: tuple[str, ...]
    tools: tuple[ToolLine, ...]
    gauges: tuple[ToolLine, ...] = ()


@dataclass(frozen=True)
class BomLine:
    stem: str
    number: str
    kind: str
    quantity: str
    material: str
    stock: tuple[StockRow, ...]
    supplier_skus: tuple[str, ...]
    # None when the part has stock rows; else the status its one stock row reads.
    placeholder: StockPlaceholder | None
    # None: the part has no process plan, so its tools are not recorded.
    tools: tuple[ToolLine, ...] | None
    # The gauges its plan's operations check with; empty without a plan.
    gauges: tuple[ToolLine, ...] = ()


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


def load_stock(directory: Path = _shop_equipment.DIRECTORY) -> dict[str, StockRow]:
    rows = {}
    for key, row in _shop_equipment.load(directory)["stock"].items():
        try:
            status = StockStatus(row["status"])
        except (KeyError, ValueError) as exc:
            raise InventoryError(
                f"stock.{key}: bad status {row.get('status')!r}"
            ) from exc
        rows[key] = StockRow(key=key, description=_describe(row), status=status)
    return rows


def _tool_status(record: dict | None) -> ToolStatus:
    if record is None or "status" not in record:
        return ToolStatus.UNRECORDED
    status = ToolStatus(record["status"])
    if status is ToolStatus.UNRECORDED:
        raise ValueError(record["status"])
    return status


# Inventory sections a plan tool or gauge's key is owned under: a plan's fixture,
# tape or die stock is a shop ``tools`` record to prechips but a fixtures,
# consumables or holders record here.
OWNERSHIP_SECTIONS = ("tools", "fixtures", "consumables", "gauges", "holders")


def _owned_record(inventory: dict, key: str) -> dict | None:
    """The one inventory record under ``key`` in ``OWNERSHIP_SECTIONS``."""
    found = [s for s in OWNERSHIP_SECTIONS if key in inventory.get(s, {})]
    if len(found) > 1:
        raise ValueError(f"{key!r} is in {' and '.join(found)}")
    return inventory[found[0]][key] if found else None


def _gauge_refs(plan: dict) -> list[str]:
    """The gauges a plan's setups and operations check with, in plan order,
    once each. A ``gauge_checks = "other"`` (prechips: checked by sight or
    feel, no gauge) names none."""
    refs = [
        check["gauge"]
        for setup in plan.get("setups", ())
        for checker in (setup, *setup.get("operations", ()))
        if checker.get("gauge_checks") != "other"
        for check in checker.get("gauge_checks", ())
    ]
    return list(dict.fromkeys(refs))


def plan_stems() -> tuple[str, ...]:
    """Every ``cad/process/<stem>/plan.toml``, enrolled or placeholder."""
    root = _process_plans.PROCESS_ROOT
    return tuple(sorted(path.parent.name for path in root.glob("*/plan.toml")))


def load_plans(
    stems: tuple[str, ...] | None = None,
    shop_dir: Path = _process_plans.SHOP_DIR,
    equipment_dir: Path = _shop_equipment.DIRECTORY,
) -> dict[str, PlanRefs]:
    """Registry stem -> the stock keys, tools and gauges its process plan names.

    ``stems`` defaults to every plan under cad/process (``plan_stems``). A
    tool's or gauge's ownership is the inventory record under its shop key in
    any of ``OWNERSHIP_SECTIONS``; a tool without a ``ref`` has none.
    """
    shop = _process_plans.load_shop(shop_dir)
    inventory = _shop_equipment.load(equipment_dir)
    errors = []
    by_part = {}

    def line(plan_name: str, kind: str, ref: str, name: str) -> ToolLine | None:
        if ref and ref not in shop.get(kind, {}):
            errors.append(f"{plan_name}: {kind[:-1]} ref {ref!r} not in the shop")
            return None
        try:
            status = _tool_status(_owned_record(inventory, ref) if ref else None)
        except ValueError as exc:
            errors.append(f"{plan_name}: {kind[:-1]} {ref!r}: {exc}")
            return None
        return ToolLine(ref=ref, name=name, status=status)

    for stem in plan_stems() if stems is None else stems:
        plan_file = _process_plans.plan_path(stem)
        whole = tomllib.loads(plan_file.read_text(encoding="utf-8"))
        name = plan_file.parent.name
        # A family plan lists each of its parts with the tools and gauges
        # of the setups and operations that part goes through.
        family = _process_plans.family_parts(stem)
        views = {
            part: _process_plans.part_view(whole, part_id)
            for part_id, part in family.items()
        } or {stem: whole}
        for part, plan in views.items():
            used = {
                operation["tool"]
                for setup in plan.get("setups", ())
                for operation in setup.get("operations", ())
                if "tool" in operation
            }
            tools = [
                line(name, "tools", tool.get("ref", ""), tool["name"])
                for tool in plan.get("tools", ())
                if not family or tool["id"] in used
            ]
            gauges = [line(name, "gauges", ref, ref) for ref in _gauge_refs(plan)]
            by_part[part.replace("_", "-")] = PlanRefs(
                stock_keys=tuple(plan.get("stock_refs", ())),
                tools=tuple(t for t in tools if t is not None),
                gauges=tuple(g for g in gauges if g is not None),
            )
    if errors:
        raise InventoryError("; ".join(errors))
    return by_part


def _is_made(stem: str) -> bool:
    """Made unless ``stem`` is a vendor identity (``-vn-``): bought finished."""
    return "-vn-" not in stem


def _placeholder(
    plan: PlanRefs | None,
    stock: tuple[StockRow, ...],
    supplier_skus: tuple[str, ...],
) -> StockPlaceholder | None:
    if stock:
        return None
    if supplier_skus:
        return StockPlaceholder.VENDOR_SKU
    if plan is None:
        return StockPlaceholder.NO_TRAVELER
    return StockPlaceholder.NO_STOCK_RECORD


def build_bom(
    registry: dict[str, dict],
    stock: dict[str, StockRow],
    plans: dict[str, PlanRefs],
) -> list[BomLine]:
    made = {stem: row for stem, row in registry.items() if _is_made(stem)}
    errors = [
        f"process plan for {'unknown' if stem not in registry else 'vendor (-vn-)'} part {stem!r}"
        for stem in plans
        if stem not in made
    ]
    errors += [
        f"process plan for {stem!r} names unknown stock {key!r}"
        for stem, plan in plans.items()
        for key in plan.stock_keys
        if key not in stock
    ]
    if errors:
        raise InventoryError("; ".join(errors))

    lines = []
    for stem in sorted(made, key=lambda s: str(made[s].get("number", s))):
        row = made[stem]
        plan = plans.get(stem)
        rows = tuple(stock[key] for key in plan.stock_keys) if plan else ()
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
                placeholder=_placeholder(plan, rows, skus),
                tools=plan.tools if plan else None,
                gauges=plan.gauges if plan else (),
            )
        )
    return lines


class RequirementType(enum.Enum):
    STOCK = "stock"
    TOOL = "tool"
    GAUGE = "gauge"


@dataclass(frozen=True)
class Requirement:
    """One stock row, tool or gauge a part needs; part fields empty for spare stock."""

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


def requirements(lines: list[BomLine], stock: dict[str, StockRow]) -> list[Requirement]:
    """One row per part and stock row, tool or gauge, then the stock no plan names.

    A part with no stock row still gets one stock line (``vendor_sku`` naming
    its supplier SKUs, or an empty ``no_stock_record`` / ``no_traveler``), and
    a part with no process plan one empty ``no_traveler`` tool line, so every
    made part appears under the stock and tool types. Gauge lines come only
    from a plan's ``gauge_checks``.
    """
    out = []
    for line in lines:
        part = (line.number, line.stem, line.kind, line.quantity, line.material)
        stock_items = [
            (row.key, row.description, row.status.value) for row in line.stock
        ]
        if line.placeholder is not None:
            skus = ", ".join(line.supplier_skus)
            stock_items = [
                ("", f"supplier SKU {skus}" if skus else "", line.placeholder.value)
            ]
        out += [
            Requirement(*part, RequirementType.STOCK, *item) for item in stock_items
        ]
        if line.tools is None:
            out.append(Requirement(*part, RequirementType.TOOL, "", "", NO_TRAVELER))
            continue
        out += [
            Requirement(*part, kind, tool.ref, tool.name, tool.status.value)
            for kind, tools in (
                (RequirementType.TOOL, line.tools),
                (RequirementType.GAUGE, line.gauges),
            )
            for tool in tools
        ]
    named = {row.key for line in lines for row in line.stock}
    out += [
        Requirement(
            "",
            "",
            "",
            "",
            "",
            RequirementType.STOCK,
            row.key,
            row.description,
            row.status.value,
        )
        for row in stock.values()
        if row.key not in named
    ]
    return out


def _md_escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def render_markdown(lines: list[BomLine], stock: dict[str, StockRow]) -> str:
    out = io.StringIO()
    rows = requirements(lines, stock)
    states = [entry.state for entry in readiness(rows)]
    out.write("# Stock BOM\n\n")
    out.write(f"{len(lines)} made parts. Readiness: ")
    out.write(
        ", ".join(f"{state.value}: {states.count(state)}" for state in ReadinessState)
        + ".\n\n"
    )
    out.write("|" + "|".join(REQUIREMENT_COLUMNS) + "|\n")
    out.write("|" + "---|" * len(REQUIREMENT_COLUMNS) + "\n")
    for row in rows:
        out.write("|" + "|".join(_md_escape(cell) for cell in row.cells()) + "|\n")
    return out.getvalue()


def render_csv(lines: list[BomLine], stock: dict[str, StockRow]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(REQUIREMENT_COLUMNS)
    writer.writerows(row.cells() for row in requirements(lines, stock))
    return out.getvalue()


class ReadinessState(enum.Enum):
    READY = "ready"
    MISSING = "missing"
    NO_TRAVELER = "no_traveler"


# Statuses that keep a part from being made now. An ``unrecorded`` tool or
# gauge counts: the shop's ownership of it is not on record.
MISSING_STOCK = (
    StockStatus.NOT_RECEIVED.value,
    StockStatus.TO_ORDER.value,
    StockPlaceholder.NO_STOCK_RECORD.value,
)
MISSING_TOOLS = tuple(
    status.value for status in ToolStatus if status is not ToolStatus.ON_HAND
)
MISSING_GAUGES = MISSING_TOOLS
READINESS_COLUMNS = (
    "number",
    "part",
    "missing_stock",
    "missing_tools",
    "missing_gauges",
    "state",
)


@dataclass(frozen=True)
class PartReadiness:
    number: str
    part: str
    missing_stock: int
    missing_tools: int
    missing_gauges: int
    state: ReadinessState


def readiness(rows: list[Requirement]) -> list[PartReadiness]:
    """Per part, in BOM order: missing stock, tools and gauges, and its state.

    A part without a process plan reads ``no_traveler`` whatever its counts:
    its tools are not known. Otherwise it is ``ready`` only with nothing missing.
    """
    by_part: dict[str, list[Requirement]] = {}
    for row in rows:
        if row.part:
            by_part.setdefault(row.part, []).append(row)
    out = []
    for part, reqs in by_part.items():
        missing = [
            sum(r.type is kind and r.status in statuses for r in reqs)
            for kind, statuses in (
                (RequirementType.STOCK, MISSING_STOCK),
                (RequirementType.TOOL, MISSING_TOOLS),
                (RequirementType.GAUGE, MISSING_GAUGES),
            )
        ]
        state = ReadinessState.READY
        if any(missing):
            state = ReadinessState.MISSING
        if any(r.status == NO_TRAVELER for r in reqs):
            state = ReadinessState.NO_TRAVELER
        out.append(PartReadiness(reqs[0].number, part, *missing, state))
    return out


def _xlsx_list(values: tuple[str, ...]) -> str:
    return "{" + ",".join(f'"{value}"' for value in values) + "}"


def write_xlsx(lines: list[BomLine], stock: dict[str, StockRow], path: Path) -> None:
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
        for column, (type_, statuses, value) in enumerate(
            (
                (RequirementType.STOCK, MISSING_STOCK, entry.missing_stock),
                (RequirementType.TOOL, MISSING_TOOLS, entry.missing_tools),
                (RequirementType.GAUGE, MISSING_GAUGES, entry.missing_gauges),
            ),
            start=2,
        ):
            summary.write_formula(
                index,
                column,
                f'=SUM(COUNTIFS({match},{kind},"{type_.value}",'
                f"{status},{_xlsx_list(statuses)}))",
                None,
                value,
            )
        summary.write_formula(
            index,
            5,
            f'=IF(COUNTIFS({match},{status},"{NO_TRAVELER}")>0,"{NO_TRAVELER}",'
            f"IF(C{excel_row}+D{excel_row}+E{excel_row}>0,"
            f'"{ReadinessState.MISSING.value}","{ReadinessState.READY.value}"))',
            None,
            entry.state.value,
        )
    for column, width in enumerate((18, 34, 14, 14, 14, 12)):
        summary.set_column(column, column, width)
    summary.freeze_panes(1, 0)
    summary.autofilter(0, 0, len(parts), len(READINESS_COLUMNS) - 1)

    # Parts per state beside the table.
    summary.write_row(0, 7, ("state", "parts"), header)
    states = [entry.state for entry in parts]
    for index, state in enumerate(ReadinessState, start=1):
        summary.write(index, 7, state.value)
        summary.write_formula(
            index,
            8,
            f"=COUNTIF($F$2:$F${len(parts) + 1},H{index + 1})",
            None,
            states.count(state),
        )
    summary.set_column(7, 7, 14)
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
        lines = build_bom(_config.parts(), stock, load_plans())
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
