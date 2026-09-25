"""Offline contracts for the MHA-146 cone tip block hold-down nut (I31)."""

from __future__ import annotations

import asyncio
import math
import re
from pathlib import Path

import pytest

import _config
import build_cone_tip_block_nut as part
import cone_tip_block_spec as block
import draw_cone_tip_block_nut as drawing
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import THREAD_MAJOR_MM, HoleSpec, blind_cut_dia_mm
from _stock_fastener import STOCK_RECIPES
from diagnostics import diag_build_90631A007 as recipe

IN = 25.4


def test_recipe_is_the_catalogue_nut_the_flange_is_sized_for() -> None:
    """90631A007: #6-32 nylon-insert locknut, 5/16 across flats x 11/64."""
    assert recipe.PART_NO == "90631A007"
    assert part.THREAD == block.FOOT_THREAD == "#6-32"
    assert part.NUT_AF == block.HOLDDOWN_NUT_AF == 5.0 / 16.0 * IN
    assert part.NUT_H == block.HOLDDOWN_NUT_H == 11.0 / 64.0 * IN
    assert part.NUT_AC == pytest.approx(block.HOLDDOWN_NUT_AC, abs=1e-12)


def test_bore_is_the_tap_drill_inside_the_screw_major() -> None:
    assert part.BORE_DIA == blind_cut_dia_mm(HoleSpec("tapped", part.THREAD))
    assert part.BORE_DIA < THREAD_MAJOR_MM[part.THREAD]


def test_volume_check_is_the_bored_prism() -> None:
    hexagon = 6.0 * (part.NUT_AC / 2.0) ** 2 * math.sqrt(3.0) / 4.0
    bore = math.pi * (part.BORE_DIA / 2.0) ** 2
    assert recipe.prism_volume() == pytest.approx((hexagon - bore) * part.NUT_H)


def test_nut_bears_beside_the_flange_slot() -> None:
    assert (part.NUT_AF - block.FLANGE_SLOT_W_MAX) / 2.0 >= 1.0


def test_stock_build_uses_its_registered_recipe_bearing_face_on_the_origin(
    monkeypatch,
) -> None:
    metadata = STOCK_RECIPES["90631A007"]
    assert metadata.module == recipe.__name__
    assert metadata.callable_name == recipe.build_90631A007.__name__
    assert part.SPEC.skus == ("90631A007",)
    assert part.SPEC.stock_name == "Zinc-Plated Steel Nylon-Insert Locknut"
    assert part.MATERIAL == "Plain Carbon Steel"

    seen: dict = {}

    async def fake_build(adapter, **kwargs):
        seen.update(kwargs)
        return {}

    monkeypatch.setattr(part, "build_stock_fastener", fake_build)
    asyncio.run(part.build(None))
    (component,) = seen["components"]
    assert component.sku == "90631A007"
    assert component.author is recipe.build_90631A007
    # The recipe extrudes midplane; the part lifts it so the bearing face is y = 0.
    assert component.transform.translation_mm == (0.0, part.NUT_H / 2.0, 0.0)
    assert seen["screw_axis_planes"] == ("Front Plane", "Right Plane")


def test_docstrings_name_the_catalogue_source_and_no_vendor_model() -> None:
    doc = " ".join((part.__doc__ or "").split())
    assert "McMaster product page for 90631A007" in doc
    assert "No McMaster .SLDPRT is committed or used." in doc
    recipe_doc = " ".join((recipe.__doc__ or "").split())
    assert "https://www.mcmaster.com/90631A007/" in recipe_doc
    assert "catalog-only" in recipe_doc
    source = Path(recipe.__file__).read_text(encoding="utf-8")
    assert "replica_main" not in source
    assert "run_build(build_catalog)" in source


def test_registry_row_is_the_purchased_nut_without_notes() -> None:
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-146"
    assert tuple(row["supplier_skus"]) == ("90631A007",)
    assert row["process"] == "purchased"
    assert int(row["quantity"]) == 1
    assert "installation_notes" not in row
    for field in ("title", "stock_name", "supplier", "finish"):
        assert not re.search(r"\d", str(row[field])), (field, row[field])


def test_drawing_is_the_purchased_reference_sheet() -> None:
    spec = DRAWINGS_BY_NAME["cone_tip_block_nut"]
    assert drawing.SPEC is spec
    assert spec.artifact_stem == part.PART_NAME
    assert spec.script == Path(drawing.__file__).resolve()
    assert "build_purchased_fastener_drawing" in Path(drawing.__file__).read_text(
        encoding="utf-8"
    )
