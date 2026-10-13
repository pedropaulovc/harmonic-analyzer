"""Offline stock and purchased-sheet contracts for MHA-VN-059."""

from __future__ import annotations

import asyncio
from math import pi

import pytest

import _config
import build_vn_platen_clip_screw as part
import pd_platen_spec
import vn_platen_clip_screw_spec as spec
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _stock_fastener import RigidTransform
from _test_stock_recipes import discovered_recipes
from diagnostics import diag_build_90114A124 as recipe
from _mcmaster_90114a124 import FILLISTER_SIZE

STEM = "vn-platen-clip-screw"


def test_catalogue_and_recipe_are_the_verified_stock_screw() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,)
    assert stock.skus == ("90114A124",)
    assert (
        stock.stock_name
        == row["stock_name"]
        == row["title"]
        == ("Brass Fillister Head Slotted Screw")
    )
    assert stock.material == row["material"] == "Brass"
    assert row["number"] == "MHA-VN-059"
    assert row["quantity"] == len(pd_platen_spec.SOCKET_XY) == 4
    assert row["finish"] == "plain"
    assert row["process"] == "purchased"
    metadata = discovered_recipes()[spec.SKU]
    assert metadata.module == recipe.__name__
    assert metadata.callable_name == "build_90114A124"
    assert metadata.threaded is True


def test_spec_nominals_are_the_catalogue_row() -> None:
    assert spec.THREAD == "#2-56"
    assert (
        spec.SHANK_DIA,
        spec.SHANK_LEN,
        spec.HEAD_H,
        spec.HEAD_DIA,
        spec.PITCH,
    ) == FILLISTER_SIZE
    # McMaster 90114A124: 0.086 major, 1/4 under head, 0.083 x 0.14 head, 56 TPI.
    assert FILLISTER_SIZE == pytest.approx(
        (0.086 * 25.4, 0.25 * 25.4, 0.083 * 25.4, 0.14 * 25.4, 25.4 / 56.0)
    )


def test_builder_lands_in_the_fillister_assembly_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}
    adapter = object()
    outputs = {"sldprt": "stock-part"}

    async def capture_stock(actual_adapter, **kwargs):
        assert actual_adapter is adapter
        captured.update(kwargs)
        return outputs

    monkeypatch.setattr(part, "build_stock_fastener", capture_stock)
    assert asyncio.run(part.build(adapter)) is outputs
    assert captured["part_name"] == STEM
    components = captured["components"]
    assert len(components) == 1
    assert components[0].sku == spec.SKU
    assert components[0].author is recipe.build_90114A124
    assert components[0].transform == RigidTransform(
        rotation_radians=(-pi / 2.0, 0.0, 0.0)
    )
    assert captured["material"] == part.SPEC.material
    assert "color" not in captured
    assert "screw_axis_planes" not in captured


def test_purchased_sheet_documents_the_built_part() -> None:
    import draw_vn_platen_clip_screw as drawing

    sheet = DRAWINGS_BY_NAME["vn_platen_clip_screw"]
    assert drawing.SPEC is sheet
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES
