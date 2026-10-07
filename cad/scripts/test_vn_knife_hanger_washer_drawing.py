"""Receiving-sheet identity must match the native purchased-part properties."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

import draw_vn_knife_hanger_washer as drawing


@pytest.mark.parametrize("native_title_is_slug", [True, False])
def test_source_title_uses_saved_part_identity_not_display_title(
    monkeypatch, tmp_path, native_title_is_slug
):
    """Accept the saved PART slug, not the human-readable registry title.

    The latter remains the PDF/document title; accepting it as the source Title
    would reject every correctly saved current-framework purchased washer.
    """
    stock = drawing.fastener(drawing.SPEC.artifact_stem)
    registry = drawing.PART_REGISTRY
    source = tmp_path / f"{stock.part_name}.SLDPRT"
    source.touch()
    monkeypatch.setattr(
        drawing,
        "SPEC",
        SimpleNamespace(
            source=source,
            source_kind="part",
            artifact_stem=stock.part_name,
            layout=drawing.SPEC.layout,
        ),
    )
    properties = {
        "Number": str(registry["number"]),
        "Title": stock.part_name if native_title_is_slug else registry["title"],
        "Material": str(registry["material"]),
        "Stock Name": stock.stock_name,
        "Supplier": stock.supplier,
        "Supplier SKUs": ", ".join(stock.skus),
    }
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(drawing, "check", lambda _label, result: result)
    monkeypatch.setattr(
        drawing,
        "read_required_properties",
        lambda _model, _names, *, required: properties,
    )

    class SourceAccepted(Exception):
        pass

    def stop_at_sheet_creation(*_args, **_kwargs):
        raise SourceAccepted

    monkeypatch.setattr(drawing, "new_project_drawing", stop_at_sheet_creation)

    class Adapter:
        currentModel = SimpleNamespace(GetPathName=lambda: str(source))

        async def open_model(self, _path):
            return True

    if native_title_is_slug:
        with pytest.raises(SourceAccepted):
            asyncio.run(drawing.build(Adapter()))
    else:
        with pytest.raises(RuntimeError, match="stale source Title"):
            asyncio.run(drawing.build(Adapter()))
