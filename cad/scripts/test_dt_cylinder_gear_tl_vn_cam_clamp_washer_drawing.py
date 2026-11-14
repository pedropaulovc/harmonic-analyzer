"""Offline contracts for the MHA-DT-12-TL-VN-53 cam fixture clamp washer (McMaster 92141A011)."""

from __future__ import annotations

import asyncio
import contextlib
import math
from pathlib import Path

import pytest

import _config
import _mcmaster_92141a011 as dims
import build_dt_cylinder_gear_tl_vn_cam_clamp_washer as part
import dt_cylinder_gear_tl_vn_cam_clamp_washer_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DRAWING_TEMPLATES
from _fastener_catalog import FASTENERS
from _stock_recipe import recipe_declaration
from diagnostics import diag_build_92141A011 as recipe

STEM = "dt-cylinder-gear-tl-vn-cam-clamp-washer"
IN = 25.4


def test_catalogue_row_is_the_registered_mcmaster_washer() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock and part.PART_NAME == STEM
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,) == ("92141A011",)
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert stock.stock_name == row["stock_name"]
    assert stock.material == row["material"]
    assert row["number"] == "MHA-DT-12-TL-VN-53"
    metadata = recipe_declaration(spec.SKU, recipe.build_92141A011)
    assert metadata.module == recipe.__name__
    assert metadata.threaded is False


def test_catalogue_dimensions_and_modelled_thickness() -> None:
    assert dims.ID == pytest.approx(0.203 * IN)
    assert dims.OD == pytest.approx(0.438 * IN)
    assert dims.THICKNESS_MIN == pytest.approx(0.017 * IN)
    assert dims.THICKNESS_MAX == pytest.approx(0.047 * IN)
    assert dims.THICKNESS_MIN < spec.THICKNESS < dims.THICKNESS_MAX


def test_recipe_extrudes_the_annulus_from_y0(monkeypatch) -> None:
    class Adapter:
        def __init__(self) -> None:
            self.calls: list[tuple[str, object]] = []

        async def create_sketch(self, plane):
            self.calls.append(("sketch", plane))
            return "ok"

        async def exit_sketch(self):
            self.calls.append(("exit", None))
            return "ok"

        async def create_extrusion(self, params):
            self.calls.append(("extrude", params.depth))
            return "ok"

    circles: list[float] = []
    volumes: list[float] = []

    async def circle(_adapter, x, y, radius, _label, **_kwargs):
        assert (x, y) == (0.0, 0.0)
        circles.append(radius)

    async def volume(_adapter, _label, expected, tolerance):
        volumes.append(expected)

    @contextlib.contextmanager
    def no_inference(_adapter):
        yield

    adapter = Adapter()
    monkeypatch.setattr(recipe, "check", lambda *a, **k: True)
    monkeypatch.setattr(recipe, "define_circle", circle)
    monkeypatch.setattr(recipe, "volume_check", volume)
    monkeypatch.setattr(recipe, "name_last_feature", lambda *_args: None)
    monkeypatch.setattr(recipe, "no_sketch_inference", no_inference)
    asyncio.run(recipe.build_92141A011(adapter))
    assert adapter.calls == [
        ("sketch", "Top"),
        ("exit", None),
        ("extrude", pytest.approx(spec.THICKNESS)),
    ]
    assert circles == [pytest.approx(spec.OD / 2.0), pytest.approx(spec.ID / 2.0)]
    assert volumes == [
        pytest.approx(math.pi / 4 * (spec.OD**2 - spec.ID**2) * spec.THICKNESS)
    ]


def test_standalone_recipe_run_is_catalog_only() -> None:
    source = Path(recipe.__file__).read_text(encoding="utf-8")
    assert "sys.exit(run_build(build_catalog))" in source
    assert "replica_main" not in source


def test_purchased_sheet_documents_the_built_part() -> None:
    import draw_dt_cylinder_gear_tl_vn_cam_clamp_washer as drawing

    sheet = DRAWINGS_BY_NAME["dt_cylinder_gear_tl_vn_cam_clamp_washer"]
    assert drawing.SPEC is sheet
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES
