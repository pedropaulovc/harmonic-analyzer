"""Shared one-sheet, three-view recipe for assembly drawings."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import _telemetry
from _common import check
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
)
from solidworks_mcp.adapters.solidworks.drawing import place_view


@_telemetry.traced("drawing.simple_three_view", label_param="pdf_title")
async def build_simple_three_view_drawing(
    adapter: Any,
    *,
    source: Path,
    outputs: DrawingOutputs,
    sheet_scale: tuple[float, float],
    front_center: tuple[float, float],
    right_center: tuple[float, float],
    iso_center: tuple[float, float],
    pdf_title: str,
) -> dict[str, str]:
    """Build a default-visual Front/Right/Isometric assembly drawing."""
    if not source.is_file():
        raise FileNotFoundError(f"source assembly is missing: {source}")

    check("open assembly drawing source", await adapter.open_model(str(source)))
    # An assembly missing its title-block properties would render blank
    # $PRPSHEET cells; read_required_properties also enforces the current
    # release Revision, and finalize_drawing repeats that check per sheet.
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
        required=(
            "Number",
            "Revision",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
    )
    new_project_drawing(adapter, scale=sheet_scale)

    for view_name, center in (
        ("*Front", front_center),
        ("*Right", right_center),
        ("*Isometric", iso_center),
    ):
        place_view(
            adapter,
            str(source),
            view_name,
            *center,
            scale=sheet_scale,
        )

    return await finalize_drawing(
        adapter,
        outputs,
        pdf_title=pdf_title,
        scale=sheet_scale,
    )
