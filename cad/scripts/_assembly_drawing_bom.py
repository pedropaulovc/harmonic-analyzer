"""Assembly-drawing BOM policy layered over the shared SolidWorks table helper."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

import _config
import _telemetry
from _drawing_common import insert_bom_table


_PART_NUMBER = re.compile(r"MHA-(?:\d{3}|A\d{2})\Z")


def configured_part_numbers(component_stems: Sequence[str]) -> dict[str, str]:
    """Return the released MHA identifier for every configured part stem."""
    numbers: dict[str, str] = {}
    for stem in component_stems:
        number = str(_config.parts(stem).get("number", "")).strip().upper()
        if not _PART_NUMBER.fullmatch(number):
            raise ValueError(f"{stem}: invalid or missing drawing number {number!r}")
        numbers[stem] = number
    if len(numbers) != len(set(numbers.values())):
        raise ValueError(f"duplicate MHA identifiers in one BOM: {numbers!r}")
    return numbers


def insert_identified_bom_table(
    adapter: Any,
    view: Any,
    *,
    anchor_xy: tuple[float, float],
    descriptions: Mapping[str, str],
    part_numbers: Mapping[str, str],
    display_as_one_item: bool = False,
    label: str,
) -> Any:
    """Insert a validated BOM, then replace filename stems with MHA identifiers."""
    components = tuple(descriptions)
    if set(part_numbers) != set(components):
        raise ValueError(
            f"{label} BOM part-number keys differ from descriptions: "
            f"{sorted(set(part_numbers) ^ set(components))}"
        )
    invalid = sorted(
        number for number in part_numbers.values() if not _PART_NUMBER.fullmatch(number)
    )
    if invalid:
        raise ValueError(f"{label} BOM carries invalid MHA identifiers: {invalid}")
    if len(part_numbers) != len(set(part_numbers.values())):
        raise ValueError(f"{label} BOM carries duplicate MHA identifiers")

    table = insert_bom_table(
        adapter,
        view,
        anchor_xy=anchor_xy,
        expected_components=components,
        descriptions=dict(descriptions),
        display_as_one_item=display_as_one_item,
        label=label,
    )

    with _telemetry.span("drawing.bom.identify", label=label):
        rows = int(adapter._get_attr_or_call(table, "RowCount") or 0)
        columns = int(adapter._get_attr_or_call(table, "ColumnCount") or 0)
        header = [
            str(table.DisplayedText2(0, column, False) or "").strip().upper()
            for column in range(columns)
        ]
        if "PART NUMBER" not in header:
            raise RuntimeError(f"{label} BOM has no PART NUMBER column: {header!r}")
        part_column = header.index("PART NUMBER")
        remaining = {stem.lower(): number for stem, number in part_numbers.items()}
        for row in range(1, rows):
            stem = str(
                table.DisplayedText2(row, part_column, False) or ""
            ).strip().lower()
            number = remaining.pop(stem, None)
            if number is None:
                continue
            if not table.IsCellTextEditable(row, part_column):
                raise RuntimeError(f"{label} BOM part-number cell {row} is not editable")
            table.SetText2(row, part_column, False, number)
            applied = str(
                table.DisplayedText2(row, part_column, False) or ""
            ).strip()
            if applied != number:
                raise RuntimeError(
                    f"{label} BOM part number did not persist: "
                    f"{applied!r} != {number!r}"
                )
        if remaining:
            raise RuntimeError(
                f"{label} BOM part numbers not applied (no matching row): "
                f"{sorted(remaining)}"
            )
        adapter.currentModel.EditRebuild3()
    _telemetry.success(f"{label} BOM part numbers replaced with released MHA IDs")
    return table
