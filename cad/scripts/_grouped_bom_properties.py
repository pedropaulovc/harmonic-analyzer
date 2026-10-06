"""Persist native BOM identity for parts grouped across configurations."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import _config
import _telemetry
from _common import _early_bound
from _identity_shapes import CATEGORIES, NUMBER


_USER_SPECIFIED_PART_NUMBER = 8  # swBOMPartNumber_UserSpecified


def apply_grouped_bom_properties(
    adapter: Any,
    configuration_names: Sequence[str],
    *,
    part_name: str,
) -> tuple[str, str]:
    """Stamp the part's frozen registry metadata; return its Number and description."""
    row = _config.parts(part_name)
    number = row.get("number")
    category = row.get("category")
    match = NUMBER.fullmatch(number) if isinstance(number, str) else None
    # Grouped BOM metadata is part-only: 000 is every assembly's sequence.
    if match is None or match[1].lower() not in CATEGORIES or match[2] == "000":
        raise ValueError(f"{part_name}: invalid grouped BOM part number {number!r}")
    if category != match[1].lower() or not part_name.startswith(f"{category}-"):
        raise ValueError(f"{part_name}: grouped BOM Number/category mismatch")
    description = row.get("description")
    if not isinstance(description, str) or not description.strip():
        raise ValueError(f"{part_name}: grouped BOM description must not be blank")
    text = description.strip()
    if not configuration_names:
        raise ValueError("grouped BOM configuration list must not be empty")

    model = adapter.currentModel
    for name in configuration_names:
        raw = model.GetConfigurationByName(name)
        if raw is None:
            raise RuntimeError(f"configuration {name!r} not found for grouped BOM")
        config = _early_bound(raw, "IConfiguration")
        config.BOMPartNoSource = _USER_SPECIFIED_PART_NUMBER
        config.AlternateName = number
        config.UseAlternateNameInBOM = True
        config.Description = text
        config.UseDescriptionInBOM = True

        applied = (
            int(config.BOMPartNoSource),
            str(config.AlternateName or "").strip().upper(),
            bool(config.UseAlternateNameInBOM),
            str(config.Description or "").strip(),
            bool(config.UseDescriptionInBOM),
        )
        expected = (_USER_SPECIFIED_PART_NUMBER, number, True, text, True)
        if applied != expected:
            raise RuntimeError(
                f"{name}: grouped BOM metadata did not persist: "
                f"{applied!r} != {expected!r}"
            )

    _telemetry.success(
        f"grouped BOM metadata: {number}, {len(configuration_names)} configurations"
    )
    return number, text
