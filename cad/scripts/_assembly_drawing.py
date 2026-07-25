"""Shared one-sheet, three-view recipe for assembly drawings."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import _telemetry
from _common import _early_bound, check
from _drawing_common import DrawingOutputs, finalize_drawing, new_project_drawing
from solidworks_mcp.adapters.solidworks.drawing import iter_views, place_view


@_telemetry.traced("drawing.assembly.simple_three_view", label_param="pdf_title")
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
    drawing, _sheet = new_project_drawing(adapter, scale=sheet_scale)
    drawing_doc = _early_bound(drawing, "IDrawingDoc")
    sheet_names = tuple(
        adapter._get_attr_or_call(drawing_doc, "GetSheetNames") or ()
    )
    if len(sheet_names) != 1:
        raise RuntimeError(
            "assembly drawing template has "
            f"{len(sheet_names)} sheets, expected 1: {sheet_names!r}"
        )
    if next(iter_views(adapter), None) is not None:
        raise RuntimeError("assembly drawing template has a pre-existing model view")

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
