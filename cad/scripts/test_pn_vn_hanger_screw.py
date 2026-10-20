"""Offline contracts for the MHA-PN-VN-50 hanger screw (McMaster 93075A199)."""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import math

import pytest

import _com
import _config
import _feature_tree
import _sketch
import _telemetry
import build_pn_vn_hanger_screw as part
import pn_vn_hanger_screw_spec as spec
from _fastener_catalog import FASTENERS
from _hole_spec import THREAD_MAJOR_MM
from _test_stock_recipes import discovered_recipes
from diagnostics import diag_build_93075A194 as family_source
from diagnostics import diag_build_93075A199 as recipe
from diagnostics import diag_mcmaster_hex_head as family
from diagnostics import diag_mcmaster_lib

IN = 25.4


def test_catalogue_row_is_the_registered_mcmaster_part() -> None:
    row = _config.parts("pn-vn-hanger-screw")
    stock = FASTENERS["pn-vn-hanger-screw"]
    assert part.SPEC is stock
    assert stock.skus == tuple(row["supplier_skus"]) == ("93075A199",)
    assert row["number"] == "MHA-PN-VN-50"
    metadata = discovered_recipes()["93075A199"]
    assert metadata.module == recipe.__name__
    assert metadata.threaded is True


def test_spec_is_the_live_catalogue_screw() -> None:
    """mcmaster.com/93075A199, read live 2026-10-14: 8-32 x 1, fully threaded."""
    assert spec.SHANK_LEN == pytest.approx(1.0 * IN)
    assert spec.SHANK_DIA == pytest.approx(THREAD_MAJOR_MM["#8-32"], abs=5e-4)
    assert spec.THREAD_PITCH == pytest.approx(IN / 32.0)
    assert spec.HEAD_AF == pytest.approx(0.25 * IN)
    assert spec.TIP_CHAMFER == pytest.approx(recipe.DIMS.tip_chamfer)
    dims = recipe.DIMS
    assert (dims.major_dia, dims.pitch, dims.length, dims.head_af, dims.head_h) == (
        spec.SHANK_DIA,
        spec.THREAD_PITCH,
        spec.SHANK_LEN,
        spec.HEAD_AF,
        spec.HEAD_H,
    )


def test_stock_build_seats_the_underside_on_the_part_origin(monkeypatch) -> None:
    seen: dict = {}

    async def fake_build(adapter, **kwargs):
        seen.update(kwargs)
        return {}

    monkeypatch.setattr(part, "build_stock_fastener", fake_build)
    asyncio.run(part.build(None))
    (component,) = seen["components"]
    assert component.sku == "93075A199"
    assert component.author is recipe.build_93075A199
    assert component.transform.translation_mm == pytest.approx(
        (0.0, 0.0, -recipe.DIMS.underside_y)
    )
    assert component.transform.rotation_radians == pytest.approx(
        (math.pi / 2.0, 0.0, 0.0)
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

        self.obj = _Obj
        self.currentSketchManager = _Obj("sketch")
        self.currentModel = _Obj("model")
        self.currentModel.__dict__["FeatureManager"] = _Obj("fm")

    def log(self, name: str, args=(), kwargs=None) -> None:
        self.events.append((name, _norm(args), _norm(kwargs or {})))

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


def _norm(value):
    if isinstance(value, float):
        return _Float(value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return (type(value).__name__, _norm(dataclasses.asdict(value)))
    if isinstance(value, dict):
        return tuple(sorted((k, _norm(v)) for k, v in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_norm(v) for v in value)
    if isinstance(value, _Recorder):
        return "adapter"
    return (
        value if isinstance(value, (int, str, bool, type(None))) else repr(type(value))
    )


class _Float(float):
    """Compares equal within 1e-12 relative: 93075A194 types its frame
    (4.953) where the family computes it ((12.7 - 2.794) / 2)."""

    def __eq__(self, other) -> bool:
        if not isinstance(other, float):
            return NotImplemented
        return abs(self - other) <= 1e-12 * max(1.0, abs(self), abs(other))

    def __ne__(self, other) -> bool:
        equal = self.__eq__(other)
        return equal if equal is NotImplemented else not equal

    __hash__ = float.__hash__


def _record(monkeypatch, author) -> list[tuple]:
    adapter = _Recorder()

    def logger(name, result=None):
        def call(*args, **kwargs):
            adapter.log(name, args, kwargs)
            return result

        return call

    def async_logger(name):
        async def call(*args, **kwargs):
            adapter.log(name, args, kwargs)

        return call

    @contextlib.contextmanager
    def no_inference(_adapter):
        adapter.log("no_sketch_inference.enter")
        yield
        adapter.log("no_sketch_inference.exit")

    for module in (family_source, family):
        monkeypatch.setattr(module, "check", logger("check", True))
        monkeypatch.setattr(module, "name_last_feature", logger("name_last_feature"))
        monkeypatch.setattr(module, "volume_check", async_logger("volume_check"))
        monkeypatch.setattr(module, "insert_helix", logger("insert_helix"))
        monkeypatch.setattr(module, "offset_plane", logger("offset_plane"))
        monkeypatch.setattr(module, "thread_sweep_cut", logger("thread_sweep_cut"))
    monkeypatch.setattr(_sketch, "add_line_chain", async_logger("add_line_chain"))
    monkeypatch.setattr(_com, "_early_bound", lambda obj, _iface: obj)
    monkeypatch.setattr(_com, "_read_member", lambda obj, name: getattr(obj, name))
    monkeypatch.setattr(
        _feature_tree,
        "_feature_by_name",
        lambda _adapter, name: adapter.obj(f"feature {name}"),
    )
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
    asyncio.run(author(adapter))
    adapter.log("_mcm_com_map", tuple(adapter._mcm_com_map(["x", "y", "z"])))
    return adapter.events


def test_family_builder_replays_93075A194_call_for_call(monkeypatch) -> None:
    """The proof the family laws are 93075A194's: at that screw's dimensions
    the shared builder issues exactly the calls its replica-gated recipe does."""
    dims = family.HexHeadScrew(
        part_no="93075A194",
        major_dia=2.0 * family_source.HX_MAJOR_R,
        pitch=family_source.HX_PITCH,
        length=family_source.HX_LEN,
        head_af=family_source.HX_HW,
        head_h=family_source.HX_HH,
    )
    source_calls = _record(monkeypatch, family_source.build_93075A194)
    family_calls = _record(
        monkeypatch, lambda adapter: family.build_hex_head_screw(adapter, dims)
    )
    assert len(source_calls) > 40
    assert family_calls == source_calls


def test_93075A199_is_the_family_at_its_catalogue_dimensions(monkeypatch) -> None:
    calls = _record(monkeypatch, recipe.build_93075A199)
    offsets = {args[1]: args[2] for name, args, _kw in calls if name == "offset_plane"}
    assert offsets["UndersidePlane"] == pytest.approx((25.4 - spec.HEAD_H) / 2.0)
    assert offsets["TipPlane"] == pytest.approx(recipe.DIMS.underside_y - 25.4)
    assert offsets["HeadTopPlane"] == pytest.approx(
        recipe.DIMS.underside_y + spec.HEAD_H
    )
    helix = next(args for name, args, _kw in calls if name == "insert_helix")
    assert helix[1:3] == (IN / 32.0, 25.4 / (IN / 32.0) + 1.0)
