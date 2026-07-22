"""Persist native BOM identity for parts grouped across configurations."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

import _telemetry
from _common import _early_bound


_PART_NUMBER = re.compile(r"MHA-\d{3}\Z")
_USER_SPECIFIED_PART_NUMBER = 8  # swBOMPartNumber_UserSpecified


def apply_grouped_bom_properties(
    adapter: Any,
    configuration_names: Sequence[str],
    *,
    part_number: str,
    description: str,
) -> None:
    """Stamp identical native BOM metadata on every grouped configuration."""
    number = part_number.strip().upper()
    if not _PART_NUMBER.fullmatch(number):
        raise ValueError(f"invalid grouped BOM part number {part_number!r}")
    text = description.strip()
    if not text:
        raise ValueError("grouped BOM description must not be blank")
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
