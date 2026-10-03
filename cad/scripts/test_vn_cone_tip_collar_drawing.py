"""Offline contracts for the MHA-VN-016 cone tip stack collar (McMaster 9414T1)."""

from __future__ import annotations

import asyncio
import contextlib
import math
from pathlib import Path

import _common
import _config
import build_vn_cone_tip_collar as part
import vn_cone_tip_collar_spec as spec
import draw_vn_cone_tip_collar as drawing
from _drawing_registry import DRAWINGS_BY_NAME
from _stock_fastener import STOCK_RECIPES
from diagnostics import diag_build_9414T1 as recipe
from diagnostics import diag_mcmaster_lib


class _Obj:
    def __init__(self, log, name: str) -> None:
        self._log = log
        self._name = name

    def __getattr__(self, attr: str):
        if attr.startswith("_"):
            raise AttributeError(attr)

        def call(*args, **kwargs):
            self._log.append((f"{self._name}.{attr}", args))
            return _Obj(self._log, f"{self._name}.{attr}()")

        return call


class _Adapter:
    def __init__(self) -> None:
        self.events: list[tuple] = []
        self.currentSketchManager = _Obj(self.events, "sketch")
        self.currentModel = _Obj(self.events, "model")
        self.currentModel.__dict__["FeatureManager"] = _Obj(self.events, "fm")

    async def _ok(self, name, *args):
        self.events.append((name, args))
        return "ok"

    async def create_sketch(self, *args):
        return await self._ok("create_sketch", *args)

    async def exit_sketch(self, *args):
        return await self._ok("exit_sketch", *args)

    async def create_revolve(self, *args):
        return await self._ok("create_revolve", *args)


def _record(monkeypatch) -> list[tuple]:
    adapter = _Adapter()

    async def volume_check(_adapter, label, expected, tol):
        adapter.events.append(("volume_check", (label, expected, tol)))
        return expected

    async def add_line_chain(_adapter, points, **_kw):
        adapter.events.append(("add_line_chain", (list(points),)))

    monkeypatch.setattr(recipe, "volume_check", volume_check)
    monkeypatch.setattr(recipe, "name_last_feature", lambda *_a: None)
    monkeypatch.setattr(recipe, "check", lambda *_a: None)
    monkeypatch.setattr(
        recipe,
        "offset_plane",
        lambda _a, name, off, base="Top Plane": adapter.events.append(
            ("offset_plane", (name, off, base))
        ),
    )
    monkeypatch.setattr(_common, "add_line_chain", add_line_chain)
    monkeypatch.setattr(_common, "_early_bound", lambda obj, _iface: obj)
    monkeypatch.setattr(
        _common, "_feature_by_name", lambda _a, name: _Obj(adapter.events, name)
    )
    monkeypatch.setattr(_common, "_read_member", lambda obj, name: getattr(obj, name))
    monkeypatch.setattr(
        diag_mcmaster_lib, "no_sketch_inference", lambda _a: contextlib.nullcontext()
    )
    asyncio.run(recipe.build_9414T1(adapter))
    return adapter.events


def test_recipe_builds_the_collar_in_the_spec_frame(monkeypatch) -> None:
    """The assembly places the collar by the spec's frame: axis +Y from the
    south face at y=0, set screw along +X at mid-width, cup rim and socket
    end at the spec's radii, socket cut to the spec's depth."""
    events = _record(monkeypatch)
    ring, hole, screw, socket = [e[1][0] for e in events if e[0] == "add_line_chain"]
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    assert (min(xs), max(xs)) == (spec.BORE_DIA / 2.0, spec.OUTER_DIA / 2.0)
    assert (min(ys), max(ys)) == (0.0, spec.WIDTH)
    for profile in (hole, screw):
        assert min(p[1] for p in profile) == spec.WIDTH / 2.0
        assert max(p[1] for p in profile) == spec.WIDTH / 2.0 + spec.SET_SCREW_MAJOR_DIA / 2.0
    assert min(p[0] for p in hole) == 0.0
    assert max(p[0] for p in hole) > spec.OUTER_DIA / 2.0
    assert min(p[0] for p in screw) == spec.SET_SCREW_CUP_RADIUS
    assert max(p[0] for p in screw) == spec.SET_SCREW_END_RADIUS
    assert ("offset_plane", ("SetScrewEndPlane", spec.SET_SCREW_END_RADIUS, "Right Plane")) in events
    socket_af = max(p[0] for p in socket) - min(p[0] for p in socket)
    assert abs(socket_af - spec.SET_SCREW_SOCKET_AF) < 1e-9
    (cut,) = [e for e in events if e[0] == "fm.FeatureCut4"]
    assert cut[1][5] == spec.SET_SCREW_SOCKET_DEPTH / 1000.0
    revolves = [e[1][0] for e in events if e[0] == "create_revolve"]
    assert [r.is_cut for r in revolves] == [False, True, False]


def test_recipe_volumes_are_consistent() -> None:
    """The analytic checks the recipe asserts against: the hole removes less
    than a full-length cylinder through the wall and more than the wall
    chord at the screw's axis."""
    r = spec.SET_SCREW_MAJOR_DIA / 2.0
    wall = spec.OUTER_DIA / 2.0 - spec.BORE_DIA / 2.0
    hole = recipe.hole_volume()
    assert math.pi * r * r * wall < hole < math.pi * r * r * spec.OUTER_DIA / 2.0
    assert 0.0 < recipe.socket_volume() < recipe.screw_volume() < recipe.ring_volume()


def test_stock_build_uses_its_registered_recipe_on_the_origin(monkeypatch) -> None:
    metadata = STOCK_RECIPES[spec.SKU]
    assert metadata.module == recipe.__name__
    assert metadata.callable_name == recipe.build_9414T1.__name__
    assert not metadata.threaded
    assert part.SPEC.skus == (spec.SKU,)
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-VN-016"
    assert row["supplier_skus"] == [spec.SKU]
    assert row["process"] == "purchased"
    assert row["material"] == part.MATERIAL

    seen: dict = {}

    async def fake_build(adapter, **kwargs):
        seen.update(kwargs)
        return {}

    monkeypatch.setattr(part, "build_stock_fastener", fake_build)
    asyncio.run(part.build(None))
    (component,) = seen["components"]
    assert component.sku == spec.SKU
    assert component.author is recipe.build_9414T1
    assert component.transform.translation_mm == (0.0, 0.0, 0.0)
    assert component.transform.rotation_radians == (0.0, 0.0, 0.0)


def test_no_vendor_model_is_tracked() -> None:
    root = Path(__file__).resolve().parents[2]
    assert not list(root.glob("cad/references/**/9414T1*"))


def test_drawing_is_the_purchased_reference_sheet() -> None:
    sheet = DRAWINGS_BY_NAME["vn_cone_tip_collar"]
    assert drawing.SPEC is sheet
    assert sheet.artifact_stem == part.PART_NAME
    assert sheet.script == Path(drawing.__file__).resolve()
