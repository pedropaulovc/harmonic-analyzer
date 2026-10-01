"""Offline contracts for the MHA-158 transgear knob retaining screw."""

from __future__ import annotations

import asyncio
import contextlib
import re
from pathlib import Path

import pytest

import _common
import _config
import _telemetry
import build_transgear_knob_retaining_screw as part
import draw_transgear_knob_retaining_screw as drawing
import transgear_knob_retaining_screw_spec as screw
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _stock_fastener import STOCK_RECIPES
from diagnostics import diag_build_90283A193 as entry
from diagnostics import diag_mcmaster_lib
from diagnostics import diag_mcmaster_pan as recipe

IN = 25.4


def test_spec_is_the_catalogue_screw() -> None:
    """90283A series per mcmaster.com (2026-09-30): 8-32 x 7/16 under the
    head, pan head Ø0.322 x 0.096."""
    assert screw.SKU == "90283A193"
    assert screw.THREAD == "#8-32"
    assert screw.SHANK_DIA == pytest.approx(0.164 * IN)
    assert screw.PITCH == pytest.approx(IN / 32.0)
    assert screw.SHANK_LEN == pytest.approx(7.0 / 16.0 * IN)
    assert screw.HEAD_DIA == pytest.approx(0.322 * IN)
    assert screw.HEAD_H == pytest.approx(0.096 * IN)
    assert recipe.PAN_SIZES[screw.SKU] == (
        screw.SHANK_DIA,
        screw.SHANK_LEN,
        screw.HEAD_H,
        screw.HEAD_DIA,
        screw.PITCH,
    )


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
        self.currentModel = _Obj("model")

    def log(self, name: str, args=(), kwargs=None) -> None:
        self.events.append((name, tuple(args), dict(kwargs or {})))

    async def _async(self, name: str, *args, **kwargs):
        self.log(name, args, kwargs)
        return "ok"

    async def create_sketch(self, *args):
        return await self._async("create_sketch", *args)

    async def exit_sketch(self, *args):
        return await self._async("exit_sketch", *args)

    async def create_revolve(self, *args):
        return await self._async("create_revolve", *args)

    async def create_extrusion(self, *args):
        return await self._async("create_extrusion", *args)

    async def create_cut_extrude(self, *args):
        return await self._async("create_cut_extrude", *args)

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
    monkeypatch.setattr(_common, "add_line_chain", add_line_chain)
    monkeypatch.setattr(diag_mcmaster_lib, "no_sketch_inference", no_inference)
    monkeypatch.setattr(
        diag_mcmaster_lib,
        "split_at_plane",
        lambda _adapter, plane, name: (
            adapter.log("split_at_plane", (plane, name)),
            [
                {"name": "Head", "box_mm": [0.0, 0.0, 0.0, 0.0, 3.0, 0.0]},
                {"name": "Shank", "box_mm": [0.0, -11.0, 0.0, 0.0, 0.0, 0.0]},
            ],
        )[1],
    )
    monkeypatch.setattr(_telemetry, "info", lambda *a, **k: None)
    asyncio.run(entry.build_90283A193(adapter))
    return adapter.events


def test_recipe_builds_the_pan_head_on_the_under_head_face(monkeypatch) -> None:
    calls = _record(monkeypatch)
    # The crown's apex sits one head height above the under-head face (y = 0)
    # and its arc lands on the head's rim.
    (arc,) = [c for c in calls if c[0] == "sketch.Create3PointArc"]
    apex, rim = arc[1][0:3], arc[1][3:6]
    assert apex[:2] == pytest.approx((0.0, screw.HEAD_H / 1000.0))
    assert rim[0] == pytest.approx(screw.HEAD_DIA / 2000.0)
    assert 0.0 < rim[1] < screw.HEAD_H / 1000.0
    # The profile's shank runs the full length under the head to a flat tip.
    profile = next(c for c in calls if c[0] == "add_line_chain")[1][0]
    assert (screw.SHANK_DIA / 2.0, 0.0) in profile
    assert min(y for _x, y in profile) == pytest.approx(-screw.SHANK_LEN)
    # The driver slot stops inside the head.
    slot = [c for c in calls if c[0] == "add_line_chain"][1][1][0]
    slot_floor = min(y for _x, y in slot)
    assert 0.0 < slot_floor < screw.HEAD_H


def test_recipe_threads_the_shank_full_length(monkeypatch) -> None:
    calls = _record(monkeypatch)
    (helix,) = [c for c in calls if c[0] == "insert_helix"]
    pitch, revs = helix[1][1:3]
    assert pitch == pytest.approx(screw.PITCH)
    # Junction to one pitch past the tip: the whole shank is threaded.
    assert revs * pitch >= screw.SHANK_LEN
    (sweep,) = [c for c in calls if c[0] == "thread_sweep_cut"]
    assert sweep[1][3:] == ("Shank", "ThreadGroove")
    assert ("split_at_plane", ("Top Plane", "HeadSplit"), {}) in calls


def test_stock_build_uses_its_registered_recipe_head_up_on_the_origin(
    monkeypatch,
) -> None:
    metadata = STOCK_RECIPES[screw.SKU]
    assert metadata.module == entry.__name__
    assert metadata.callable_name == entry.build_90283A193.__name__
    assert metadata.threaded
    assert FASTENERS[part.PART_NAME] is part.SPEC
    assert part.SPEC.skus == (screw.SKU,)
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-158"
    assert row["supplier_skus"] == [screw.SKU]
    assert row["stock_name"] == part.SPEC.stock_name
    assert row["material"] == part.MATERIAL

    seen: dict = {}

    async def fake_build(adapter, **kwargs):
        seen.update(kwargs)
        return {}

    monkeypatch.setattr(part, "build_stock_fastener", fake_build)
    asyncio.run(part.build(None))
    (component,) = seen["components"]
    assert component.sku == screw.SKU
    assert component.author is entry.build_90283A193
    assert component.transform.translation_mm == (0.0, 0.0, 0.0)
    assert component.transform.rotation_radians == (0.0, 0.0, 0.0)
    assert seen["screw_axis_planes"] == ("Front Plane", "Right Plane")


def test_standalone_recipe_run_is_catalog_only(monkeypatch) -> None:
    """No vendor model: the standalone run builds, checks and saves the
    catalog recipe and never enters the McMaster replica path, which demands
    a vendor SLDPRT and its harvest."""
    assert not hasattr(entry, "replica_main")
    seen: list = []

    async def fake_catalog_run(adapter, part_no, builder):
        seen.append((part_no, builder))
        return {}

    monkeypatch.setattr(entry, "catalog_run", fake_catalog_run)
    asyncio.run(entry.build_catalog(None))
    assert seen == [(screw.SKU, entry.build_90283A193)]


def test_no_vendor_model_of_the_new_hardware_is_tracked() -> None:
    root = Path(__file__).resolve().parents[2]
    assert not list(root.glob(f"cad/references/**/{screw.SKU}*.SLDPRT"))


_DIMENSION = re.compile(r"\d")


def test_sheet_carries_no_installation_note_and_no_dimension_in_a_note() -> None:
    """The purchased sheet prints only the registry's stock name, supplier and
    SKU besides its fixed footer, so none of those may carry a size (Rule 6)."""
    row = _config.parts(part.PART_NAME)
    assert "installation_notes" not in row
    for field in ("title", "stock_name", "supplier", "finish"):
        assert not _DIMENSION.search(str(row[field])), (field, row[field])


def test_drawing_is_the_purchased_reference_sheet() -> None:
    spec = DRAWINGS_BY_NAME["transgear_knob_retaining_screw"]
    assert drawing.SPEC is spec
    assert spec.artifact_stem == part.PART_NAME
    assert spec.script == Path(drawing.__file__).resolve()
    assert (
        drawing.build.__code__.co_names.count("build_purchased_fastener_drawing") == 1
    )
