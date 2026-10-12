"""Offline stock identity and catalogue-envelope contracts for MHA-VN-054."""

from __future__ import annotations

import asyncio

import pytest

import _config
import build_vn_ms_stop_plate_screw as part
import _mcmaster_90114a124 as spec
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _stock_recipe import recipe_declaration
from diagnostics import diag_build_90114A124 as recipe

STEM = "vn-ms-stop-plate-screw"


def test_catalogue_and_native_recipe_share_the_small_brass_identity() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,) == ("90114A124",)
    assert stock.material == row["material"] == "Brass"
    assert stock.stock_name == row["stock_name"] == "Brass Fillister Head Slotted Screw"
    assert row["number"] == "MHA-VN-054"
    assert row["quantity"] == 2
    assert row["process"] == "purchased"
    metadata = recipe_declaration(spec.SKU, recipe.build_90114A124)
    assert metadata is recipe.build_90114A124.__stock_recipe__
    assert metadata.sku == spec.SKU
    assert metadata.module == recipe.__name__
    assert metadata.callable_name == "build_90114A124"
    assert metadata.threaded


def test_catalogue_envelope_is_the_live_smallest_brass_fillister() -> None:
    assert spec.THREAD == "#2-56"
    assert spec.FILLISTER_SIZE == pytest.approx(
        (spec.MAJOR_DIA, spec.LENGTH, spec.HEAD_H, spec.HEAD_DIA, spec.PITCH)
    )
    assert (spec.MAJOR_DIA, spec.LENGTH, spec.HEAD_H, spec.HEAD_DIA) == pytest.approx(
        (2.1844, 6.35, 2.1082, 3.556)
    )
    assert spec.PITCH == pytest.approx(25.4 / 56.0)
    assert recipe.FILLISTER_SIZE is spec.FILLISTER_SIZE
    assert spec.HEAD_DIA < 4.0


def test_purchased_sheet_points_to_the_built_brass_part() -> None:
    import draw_vn_ms_stop_plate_screw as drawing

    sheet = DRAWINGS_BY_NAME["vn_ms_stop_plate_screw"]
    assert drawing.SPEC is sheet
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem


def test_stop_plate_threads_have_clearance_and_full_engagement() -> None:
    import ms_stop_spec as joint

    assert joint.PLATE_CLEARANCE_DIA > spec.MAJOR_DIA
    penetration = spec.LENGTH - joint.PLATE_THICKNESS
    assert penetration > 1.5 * spec.MAJOR_DIA + spec.PITCH
    assert joint.PLATE_TAP_THREAD_DEPTH > penetration
    assert joint.PLATE_TAP_DRILL_DEPTH > joint.PLATE_TAP_THREAD_DEPTH
    assert joint.BLOCK_DEPTH > joint.PLATE_TAP_DRILL_DEPTH


def test_native_author_passes_the_per_sku_catalogue_size(monkeypatch) -> None:
    adapter = object()
    calls = []

    async def capture(actual_adapter, sku, size):
        calls.append((actual_adapter, sku, size))

    monkeypatch.setattr(recipe, "build_fillister", capture)
    asyncio.run(recipe.build_90114A124(adapter))
    assert calls == [(adapter, spec.SKU, spec.FILLISTER_SIZE)]
    assert calls[0][2] is spec.FILLISTER_SIZE


def test_stock_builder_keeps_the_native_author_frame_and_threaded_saver(
    monkeypatch,
) -> None:
    adapter = object()
    captured = {}
    artefacts = {"sldprt": "vn-ms-stop-plate-screw.SLDPRT"}

    async def capture(actual_adapter, **kwargs):
        assert actual_adapter is adapter
        captured.update(kwargs)
        return artefacts

    monkeypatch.setattr(part, "build_stock_fastener", capture)
    assert asyncio.run(part.build(adapter)) is artefacts
    (component,) = captured["components"]
    assert component.sku == spec.SKU
    assert component.author is recipe.build_90114A124
    assert component.transform == part.RigidTransform()
    assert captured["part_name"] == STEM
    assert captured["material"] == "Brass"
    assert captured["screw_axis_planes"] == ("Front Plane", "Right Plane")
    assert captured["save_threaded_part"] is part.save_simplified_part
