"""Offline contracts for the MHA-PD-VN-60 guide-lock screw (McMaster 91792A108)."""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path

import pytest

import _sketch
import _config
import _telemetry
import build_pd_vn_guide_lock_screw as part
import build_pd_platen_guide as guide
import draw_pd_vn_guide_lock_screw as drawing
import pd_vn_guide_lock_screw_spec as screw
import pd_guide_lock_spec as lock
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _hole_spec import blind_cut_dia_mm
from _test_stock_recipes import discovered_recipes
import _mcmaster_91792a108 as pan
from diagnostics import diag_mcmaster_fillister as recipe
from diagnostics import diag_mcmaster_oval as catalog
from diagnostics import diag_build_91792A108 as sku_recipe
from diagnostics import diag_mcmaster_lib

STEM = "pd-vn-guide-lock-screw"
IN = 25.4


def test_recipe_is_the_catalogue_screw() -> None:
    """The McMaster 18-8 pan head slotted family table (read live
    2026-10-11): #4-40 x 3/8 under the head, head Ø0.219 x 0.068 in."""
    assert pan.PART_NO == screw.SKU == "91792A108"
    assert pan.PAN_HEAD_SIZE == pytest.approx(
        (0.112 * IN, 0.375 * IN, 0.068 * IN, 0.219 * IN, IN / 40.0)
    )
    assert (
        screw.SHANK_DIA,
        screw.SHANK_LEN,
        screw.HEAD_H,
        screw.HEAD_DIA,
        screw.PITCH,
    ) == pan.PAN_HEAD_SIZE


def test_shank_is_the_lock_stack() -> None:
    """The shank passes the 1/16 lock sheet into the guide's through tap
    (R9-48) and stops inside the rail."""
    assert screw.THREAD == "#4-40"
    assert guide.LOCK_SCREW_PASSAGE == lock.LOCK_THICK
    assert screw.SHANK_LEN == pytest.approx(
        guide.LOCK_SCREW_PASSAGE + guide.LOCK_SCREW_THREAD_ENGAGEMENT
    )
    assert guide.LOCK_SCREW_THREAD_ENGAGEMENT >= screw.SHANK_DIA
    assert screw.ENGAGEMENT_WORST >= screw.ENGAGEMENT_FLOOR_D * screw.SHANK_DIA
    assert guide.LOCK_TAP_SPEC.end == "through_all"
    assert guide.LOCK_SCREW_TIP_INSIDE_MIN > 0.0
    # The 1/8 drill in the lock plate passes the shank.
    assert blind_cut_dia_mm(lock.HOLE_SPEC) > screw.SHANK_DIA


class _Recorder:
    """A fake SolidWorks that records every call a recipe makes."""

    def __init__(self) -> None:
        self.events: list[tuple] = []
        recorder = self

        class _Obj:
            def __init__(self, name: str) -> None:
                self._name = name

            def __getattr__(self, attr: str):
                if attr.startswith("_"):
                    raise AttributeError(attr)

                def call(*args, **kwargs):
                    recorder.log(f"{self._name}.{attr}", args, kwargs)
                    return _Obj(f"{self._name}.{attr}()")

                return call

        self.currentSketchManager = _Obj("sketch")

    def log(self, name: str, args=(), kwargs=None) -> None:
        self.events.append((name, tuple(args), dict(kwargs or {})))

    async def _async(self, name: str, *args):
        self.log(name, args)
        return "ok"

    async def create_sketch(self, *args):
        return await self._async("create_sketch", *args)

    async def exit_sketch(self, *args):
        return await self._async("exit_sketch", *args)

    async def create_revolve(self, *args):
        return await self._async("create_revolve", *args)

    async def create_cut_extrude(self, *args):
        return await self._async("create_cut_extrude", *args)

    async def create_extrusion(self, *args):
        return await self._async("create_extrusion", *args)

    async def add_fillet(self, *args):
        return await self._async("add_fillet", *args)


def _record(monkeypatch) -> list[tuple]:
    adapter = _Recorder()

    def logger(name, result=None):
        def call(*args, **kwargs):
            adapter.log(name, args, kwargs)
            return result

        return call

    async def add_line_chain(_adapter, points, **kwargs):
        adapter.log("add_line_chain", (tuple(points),), kwargs)

    async def volume_check(_adapter, label, expected, tol):
        adapter.log("volume_check", (label, expected, tol))
        return expected

    @contextlib.contextmanager
    def no_inference(_adapter):
        yield

    monkeypatch.setattr(recipe, "check", logger("check", True))
    monkeypatch.setattr(recipe, "name_last_feature", logger("name_last_feature"))
    monkeypatch.setattr(recipe, "volume_check", volume_check)
    monkeypatch.setattr(recipe, "insert_helix", logger("insert_helix"))
    monkeypatch.setattr(recipe, "thread_sweep_cut", logger("thread_sweep_cut"))
    monkeypatch.setattr(_sketch, "add_line_chain", add_line_chain)
    monkeypatch.setattr(diag_mcmaster_lib, "no_sketch_inference", no_inference)
    monkeypatch.setattr(
        diag_mcmaster_lib,
        "split_at_plane",
        lambda _adapter, plane, name: (
            adapter.log("split_at_plane", (plane, name)),
            [{"name": "Shank", "box_mm": [0.0, -100.0, 0.0, 0.0, 0.0, 0.0]}],
        )[1],
    )
    monkeypatch.setattr(_telemetry, "info", lambda *a, **k: None)
    asyncio.run(sku_recipe.build_91792A108(adapter))
    return adapter.events


def test_recipe_profile_is_the_catalogue_pan_head_and_shank(monkeypatch) -> None:
    major, length, head_h, head_dia, _pitch = pan.PAN_HEAD_SIZE
    band = 0.8 * head_h
    calls = _record(monkeypatch)
    (arc,) = [c for c in calls if c[0] == "sketch.Create3PointArc"]
    start, end = arc[1][0:2], arc[1][3:5]
    assert start == pytest.approx((0.0, head_h / 1000.0))
    assert end == pytest.approx((head_dia / 2000.0, band / 1000.0))
    profile = [c[1][0] for c in calls if c[0] == "add_line_chain"][0]
    assert max(y for _x, y in profile) == pytest.approx(head_h)
    assert max(x for x, _y in profile) == pytest.approx(head_dia / 2.0)
    assert min(y for _x, y in profile) == pytest.approx(-length)
    assert (major / 2.0, 0.0) in profile


def test_recipe_cuts_the_driver_slot_and_thread(monkeypatch) -> None:
    _major, length, head_h, head_dia, pitch = pan.PAN_HEAD_SIZE
    slot_w = 0.135 * head_dia
    calls = _record(monkeypatch)
    slot = [c[1][0] for c in calls if c[0] == "add_line_chain"][1]
    assert sorted({x for x, _y in slot}) == pytest.approx([-slot_w / 2.0, slot_w / 2.0])
    slot_floor = min(y for _x, y in slot)
    assert slot_floor == pytest.approx(head_h - 1.5 * slot_w)
    # The slot floor stays inside the head, above its bearing face.
    assert 0.0 < slot_floor < head_h
    assert ("create_sketch", ("Front",), {}) in calls
    assert any(c[0] == "create_cut_extrude" for c in calls)
    (helix,) = [c for c in calls if c[0] == "insert_helix"]
    assert helix[1][1:3] == pytest.approx((pitch, length / pitch + 1.0))
    sweeps = [c for c in calls if c[0] == "thread_sweep_cut"]
    assert [c[1][-1] for c in sweeps] == ["ThreadGroove"]
    assert ("split_at_plane", ("Top Plane", "HeadSplit"), {}) in calls


def test_catalogue_row_is_the_registered_mcmaster_screw() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert stock.skus == tuple(row["supplier_skus"]) == (screw.SKU,)
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert stock.stock_name == row["stock_name"]
    assert "Slotted" in stock.stock_name
    assert stock.material == row["material"] == part.MATERIAL == "AISI 304"
    assert row["number"] == "MHA-PD-VN-60"
    metadata = discovered_recipes()[screw.SKU]
    assert metadata.module == sku_recipe.__name__
    assert getattr(sku_recipe, metadata.callable_name) is sku_recipe.build_91792A108
    assert metadata.threaded


def test_quantity_is_one_screw_per_guide_lock_hole() -> None:
    per_lock = len(lock.HOLE_XY)
    locks = int(_config.parts("pd-guide-lock")["quantity"])
    assert int(_config.parts(STEM)["quantity"]) == per_lock * locks
    assert len(guide.HOLE_X) * 2 == per_lock * locks  # two guide rails


def test_stock_build_takes_the_fillister_frame(monkeypatch) -> None:
    """The paper drive places it as it placed MHA-PD-VN-52: bearing face on the
    origin, shank along +Z."""
    import build_dt_vn_fillister_screw as fillister

    seen: dict = {}
    fillister_seen: dict = {}

    def fake(store):
        async def fake_build(adapter, **kwargs):
            store.update(kwargs)
            return {}

        return fake_build

    monkeypatch.setattr(part, "build_stock_fastener", fake(seen))
    monkeypatch.setattr(fillister, "build_stock_fastener", fake(fillister_seen))
    asyncio.run(part.build(None))
    asyncio.run(fillister.build(None))
    (component,) = seen["components"]
    (reference,) = fillister_seen["components"]
    assert component.sku == screw.SKU
    assert component.author is sku_recipe.build_91792A108
    assert component.transform == reference.transform
    assert "screw_axis_planes" not in seen


def test_standalone_recipe_run_is_catalog_only(monkeypatch, tmp_path) -> None:
    """No vendor model: the standalone run builds the recipe and saves it
    under the reference directory, never entering a replica path."""
    assert not hasattr(sku_recipe, "replica_main")
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

    monkeypatch.setattr(catalog, "check", lambda *a, **k: True)
    monkeypatch.setattr(sku_recipe, "build_91792A108", fake_recipe)
    monkeypatch.setattr(diag_mcmaster_lib, "OUT_DIR", tmp_path)
    monkeypatch.setattr(
        diag_mcmaster_lib, "assert_seat_sketch_baseline", lambda *a: None
    )
    monkeypatch.setattr(
        diag_mcmaster_lib, "mass_properties", lambda _a: {"volume_mm3": 40.0}
    )
    monkeypatch.setattr(diag_mcmaster_lib, "export_views", no_views)
    monkeypatch.setattr(diag_mcmaster_lib, "close_all", no_close)
    adapter = _Adapter()
    artefacts = asyncio.run(sku_recipe.build_catalog(adapter))
    assert built == [adapter]
    assert saved == [str((tmp_path / f"{screw.SKU}-catalog.SLDPRT").resolve())]
    assert artefacts["sldprt"] == str(tmp_path / f"{screw.SKU}-catalog.SLDPRT")


def test_no_vendor_model_is_tracked() -> None:
    root = Path(__file__).resolve().parents[2]
    assert not list(root.glob(f"cad/references/**/{screw.SKU}*.SLDPRT"))


def test_purchased_sheet_documents_the_built_part() -> None:
    sheet = DRAWINGS_BY_NAME["pd_vn_guide_lock_screw"]
    assert drawing.SPEC is sheet
    assert sheet.script == Path(drawing.__file__).resolve()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES
