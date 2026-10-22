"""Threaded supplier-reference saver, separate from unthreaded sketch authoring."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from _simplified_part import save_simplified_part
from _supplier_screw_reference import add_supplier_reference_sketch


async def save_supplier_reference_part(
    adapter: Any,
    part_name: str,
    suppressed_features: tuple[str, ...],
    *,
    dimensions: Sequence[tuple[str, float, str]],
    starts: Mapping[str, tuple[float, float]] | None = None,
    planes: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Add references in the final stock frame, then perform the normal save."""
    await add_supplier_reference_sketch(adapter, dimensions, starts=starts, planes=planes)
    return await save_simplified_part(adapter, part_name, suppressed_features)
