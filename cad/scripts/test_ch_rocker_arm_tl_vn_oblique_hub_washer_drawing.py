"""Offline contracts for the MHA-CH-06-TL-VN-85 oblique-jig hub washer (McMaster 90231A116)."""

from __future__ import annotations

import asyncio
import contextlib
import math
from pathlib import Path

import pytest

import _config
import build_ch_rocker_arm_tl_vn_oblique_hub_washer as part
import ch_rocker_arm_tl_vn_oblique_hub_washer_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DRAWING_TEMPLATES
from _fastener_catalog import FASTENERS
from _test_stock_recipes import discovered_recipes
from diagnostics import diag_build_90231A116 as recipe

STEM = "ch-rocker-arm-tl-vn-oblique-hub-washer"
SHEET = "ch_rocker_arm_tl_vn_oblique_hub_washer"
NUMBER = "MHA-CH-06-TL-VN-85"
STOCK_NAME = "Brass SAE Washer for Number 8 Screw Size"
BUILD = "build_90231A116"
IN = 25.4


def test_catalogue_row_is_the_registered_mcmaster_part() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,) == ("90231A116",)
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert stock.stock_name == row["stock_name"] == STOCK_NAME
    assert stock.material == row["material"] == part.MATERIAL == "Brass"
    assert row["number"] == NUMBER
    assert row["process"] == "purchased"
    assert int(row["quantity"]) == spec.QUANTITY == 1
    metadata = discovered_recipes()[spec.SKU]
    assert metadata.module == recipe.__name__
    assert getattr(recipe, metadata.callable_name) is getattr(recipe, BUILD)
    assert metadata.threaded is False


def test_spec_carries_the_live_catalogue_facts() -> None:
    """mcmaster.com/90231A116, checked live 2026-11-13; ASME B18.21.1 Table 11."""
    assert spec.CATALOG_CHECKED_DATE == "2026-11-13"
    assert spec.CATALOG_STANDARD == "SAE"
    assert spec.SCREW_SIZE == "#8"
    assert spec.ID == pytest.approx(0.188 * IN)
    assert spec.OD == pytest.approx(0.438 * IN)
    assert spec.THICKNESS_MIN == pytest.approx(0.036 * IN)
    assert spec.THICKNESS_MAX == pytest.approx(0.065 * IN)
    # The model is Table 11's basic thickness, inside the supplied range.
    assert spec.THICKNESS == pytest.approx(0.049 * IN)
    assert spec.THICKNESS_MIN < spec.THICKNESS < spec.THICKNESS_MAX
    assert (spec.BOTTOM_Z, spec.TOP_Z) == (0.0, spec.THICKNESS)
    assert spec.SUPPLIER_DATA == ("THICKNESS .036-.065 AS SUPPLIED.",)


class _Recorder:
    """A fake SolidWorks that records every call a recipe makes."""

    def __init__(self) -> None:
        self.events: list[tuple] = []

    def log(self, name: str, args=(), kwargs=None) -> None:
        self.events.append((name, tuple(args), dict(kwargs or {})))

    async def create_sketch(self, *args):
        self.log("create_sketch", args)
        return "ok"

    async def exit_sketch(self, *args):
        self.log("exit_sketch", args)
        return "ok"

    async def create_extrusion(self, *args):
        self.log("create_extrusion", args)
        return "ok"


def _record(monkeypatch) -> list[tuple]:
    adapter = _Recorder()

    async def define_circle(_adapter, x, y, radius, label, **kwargs):
        adapter.log("circle", (x, y, radius, label))
        return label

    async def volume_check(_adapter, label, expected, tol):
        adapter.log("volume_check", (label, expected, tol))
        return expected

    @contextlib.contextmanager
    def no_inference(_adapter):
        adapter.log("no_inference_enter")
        yield
        adapter.log("no_inference_exit")

    monkeypatch.setattr(recipe, "check", lambda *a, **k: True)
    monkeypatch.setattr(
        recipe, "name_last_feature", lambda _a, name: adapter.log("name", (name,))
    )
    monkeypatch.setattr(recipe, "volume_check", volume_check)
    monkeypatch.setattr(recipe, "define_circle", define_circle)
    monkeypatch.setattr(recipe, "no_sketch_inference", no_inference)
    asyncio.run(getattr(recipe, BUILD)(adapter))
    return adapter.events


def test_recipe_is_the_washer_annulus(monkeypatch) -> None:
    calls = _record(monkeypatch)
    names = [c[0] for c in calls]
    assert calls[0] == ("create_sketch", ("Top",), {})
    circles = [c[1] for c in calls if c[0] == "circle"]
    assert sorted(r for _x, _y, r, _ in circles) == pytest.approx(
        [spec.ID / 2.0, spec.OD / 2.0]
    )
    assert all((x, y) == (0.0, 0.0) for x, y, _r, _ in circles)
    enter, leave = names.index("no_inference_enter"), names.index("no_inference_exit")
    assert all(enter < i < leave for i, n in enumerate(names) if n == "circle")
    (extrude,) = [c for c in calls if c[0] == "create_extrusion"]
    assert extrude[1][0].depth == pytest.approx(spec.THICKNESS)
    assert not extrude[1][0].both_directions
    assert [c[1][0] for c in calls if c[0] == "name"] == ["WasherProfile", "WasherBody"]
    (volume,) = [c for c in calls if c[0] == "volume_check"]
    assert volume[1][1] == pytest.approx(
        math.pi / 4.0 * (spec.OD**2 - spec.ID**2) * spec.THICKNESS
    )
    assert volume[1][1] == pytest.approx(spec.washer_volume())


def test_standalone_recipe_run_is_catalog_only(monkeypatch, tmp_path) -> None:
    from diagnostics import diag_mcmaster_lib as lib

    assert not hasattr(recipe, "replica_main")
    saved: list[str] = []
    built: list = []

    class _Adapter:
        async def create_part(self):
            return "ok"

        async def save_file(self, path):
            saved.append(path)
            return "ok"

    async def fake_recipe(adapter, truth=None):
        built.append(adapter)

    async def no_views(_adapter, _stem):
        return {}

    async def no_close(_adapter):
        return None

    monkeypatch.setattr(recipe, "check", lambda *a, **k: True)
    monkeypatch.setattr(recipe, BUILD, fake_recipe)
    monkeypatch.setattr(lib, "OUT_DIR", tmp_path)
    monkeypatch.setattr(lib, "assert_seat_sketch_baseline", lambda *a: None)
    monkeypatch.setattr(lib, "mass_properties", lambda _a: {"volume_mm3": 13.0})
    monkeypatch.setattr(lib, "export_views", no_views)
    monkeypatch.setattr(lib, "close_all", no_close)
    adapter = _Adapter()
    artefacts = asyncio.run(recipe.build_catalog(adapter))
    assert built == [adapter]
    assert saved == [str((tmp_path / f"{spec.SKU}-catalog.SLDPRT").resolve())]
    assert artefacts["sldprt"] == str(tmp_path / f"{spec.SKU}-catalog.SLDPRT")


def test_no_vendor_model_is_tracked() -> None:
    root = Path(__file__).resolve().parents[2]
    assert not list(root.glob(f"cad/references/**/{spec.SKU}*.SLDPRT"))
    assert not list(root.glob(f"cad/references/**/{spec.SKU}*.STEP"))


def test_turned_top_hat_washer_is_retired_without_an_alias() -> None:
    """Owner ruling 2026-11-13 (#2448): no TL-52 registry, builder or sheet."""
    scripts = Path(__file__).resolve().parent
    old = "ch_rocker_arm_tl_oblique_hub_washer"
    assert old not in DRAWINGS_BY_NAME
    for name in (f"{old}_spec.py", f"build_{old}.py", f"draw_{old}.py"):
        assert not (scripts / name).exists()
    assert not (scripts.parent / "config/parts/ch-rocker-arm-tl-oblique-hub-washer.yaml").exists()


def test_purchased_sheet_documents_the_built_part() -> None:
    import draw_ch_rocker_arm_tl_vn_oblique_hub_washer as drawing

    sheet = DRAWINGS_BY_NAME[SHEET]
    assert drawing.SPEC is sheet
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES
    assert (
        drawing.build.__code__.co_names.count("build_purchased_fastener_drawing") == 1
    )
