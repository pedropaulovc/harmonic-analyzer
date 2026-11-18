"""Stock bill of materials: every part the shop makes, joined to the raw stock
recorded for it in cad/config/shop-equipment.toml.

A part is made in the shop when its registry row's ``process`` does not start
with ``purchased`` (cad/config/parts/*.yaml through ``_config.parts``). A
``[[stock]]`` row serves the parts named in its ``allocated_to``; its ``status``
says whether that stock is on hand, bought but not received, or still to
order. A made part with no allocated row reads ``vendor_sku`` when its registry
row names supplier SKUs (bought hardware reworked in the shop), otherwise
``no_stock_record``.

Usage:
    uv run --frozen python cad/scripts/stock_bom.py [--format md|csv] [--out PATH]

Exits 2 when a row allocates a stem that is not in the registry or is a
purchased part, or carries an unknown status: the inventory must not point at a
retired or bought identity.
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
from _paths import CAD_ROOT

SHOP_EQUIPMENT = CAD_ROOT / "config" / "shop-equipment.toml"
MM_PER_IN = 25.4


class StockStatus(enum.Enum):
    ON_HAND = "on_hand"
    NOT_RECEIVED = "not_received"
    TO_ORDER = "to_order"


class PartStockStatus(enum.Enum):
    """A part's stock state; declaration order is precedence (best first)."""

    ON_HAND = "on_hand"
    NOT_RECEIVED = "not_received"
    TO_ORDER = "to_order"
    VENDOR_SKU = "vendor_sku"
    NO_STOCK_RECORD = "no_stock_record"


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


def _is_made(row: dict) -> bool:
    return not str(row.get("process", "")).startswith("purchased")


def _part_status(
    stock: tuple[StockRow, ...], supplier_skus: tuple[str, ...]
) -> PartStockStatus:
    if stock:
        statuses = (PartStockStatus(row.status.value) for row in stock)
        return min(statuses, key=list(PartStockStatus).index)
    if supplier_skus:
        return PartStockStatus.VENDOR_SKU
    return PartStockStatus.NO_STOCK_RECORD


def build_bom(registry: dict[str, dict], stock: list[StockRow]) -> list[BomLine]:
    made = {stem: row for stem, row in registry.items() if _is_made(row)}
    errors = []
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
        "|Number|Part|Kind|Qty|Status|Material (registry)|Stock (shop-equipment.toml)|\n"
    )
    out.write("|---|---|---|---|---|---|---|\n")
    for line in lines:
        cells = [
            line.number,
            line.stem,
            line.kind,
            line.quantity,
            line.status.value,
            line.material,
            _stock_cell(line),
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


def render_csv(lines: list[BomLine]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(
        ["number", "part", "kind", "quantity", "status", "material", "stock"]
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
        lines = build_bom(_config.parts(), stock)
    except InventoryError as exc:
        print(f"stock_bom: {exc}", file=sys.stderr)
        return 2

    text = render_markdown(lines, stock) if args.format == "md" else render_csv(lines)
    if args.out is None:
        sys.stdout.write(text)
        return 0
    args.out.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
