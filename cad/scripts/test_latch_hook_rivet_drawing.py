"""Offline contracts for the MHA-175 latch-hook rivet (McMaster 97482A010)."""

from __future__ import annotations

import asyncio
import contextlib
import math
import re
from fractions import Fraction
from pathlib import Path

import pytest

import _config
import build_latch_hook_rivet as part
import latch_hook_bracket_geometry as bracket
import latch_hook_bracket_spec as bracket_spec
import latch_hook_geometry as hook
import latch_hook_rivet_spec as spec
import latch_hook_spec as hook_spec
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _stock_fastener import STOCK_RECIPES
from diagnostics import diag_build_97482A010 as recipe

STEM = "latch-hook-rivet"
IN = 25.4


def test_catalogue_row_is_the_registered_mcmaster_rivet() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,)
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert stock.stock_name == row["stock_name"]
    assert stock.material == row["material"] == part.MATERIAL
    assert row["number"] == "MHA-175"
    assert int(row["quantity"]) == 2
    metadata = STOCK_RECIPES[spec.SKU]
    assert metadata.module == recipe.__name__
    assert getattr(recipe, metadata.callable_name) is recipe.build_97482A010
    assert metadata.threaded is False


def test_recipe_is_the_size_the_registry_names() -> None:
    text = _config.parts(STEM)["material_specification"]
    match = re.search(r"(\d+/\d+) x (\d+/\d+)", text)
    assert match, text
    dia, length = (float(Fraction(size)) * IN for size in match.groups())
    assert spec.DIA == pytest.approx(dia)
    assert spec.LENGTH == pytest.approx(length)


def test_the_joint_is_within_the_vendor_grip_and_the_shank_enters_every_hole() -> None:
    worst_grip = hook.STRIP_T + bracket.SHEET_T + bracket.SHEET_T_PLUS
    assert worst_grip <= 0.094 * IN == pytest.approx(spec.MAX_GRIP)
    # One match-drilled hole: the smallest either sheet may print.
    assert hook.RIVET_HOLE_DIA == bracket.RIVET_HOLE_DIA
    smallest = hook.RIVET_HOLE_DIA + max(
        min(hook_spec.HOLE_BAND), min(bracket_spec.HOLE_BAND)
    )
    assert spec.DIA < smallest
    # The vendor's #51 hole is looser than the printed band's top.
    largest = hook.RIVET_HOLE_DIA + min(
        max(hook_spec.HOLE_BAND), max(bracket_spec.HOLE_BAND)
    )
    assert spec.VENDOR_HOLE_DIA > largest


def test_the_dome_is_a_cap_through_the_rim_and_apex() -> None:
    a = spec.HEAD_DIA / 2.0
    centre = spec.DOME_CENTRE_Y
    assert math.hypot(a, 0.0 - centre) == pytest.approx(spec.DOME_R)
    assert spec.HEAD_H - centre == pytest.approx(spec.DOME_R)


def test_the_recipe_volume_is_shank_plus_cap() -> None:
    shank = math.pi * (0.5 * spec.DIA) ** 2 * spec.LENGTH
    # The cap by the disc integral, independent of the closed form.
    steps = 20000
    dy = spec.HEAD_H / steps
    cap = sum(
        math.pi * (spec.DOME_R**2 - ((i + 0.5) * dy - spec.DOME_CENTRE_Y) ** 2) * dy
        for i in range(steps)
    )
    assert spec.rivet_volume() == pytest.approx(shank + cap, rel=1e-6)


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

    async def create_sketch(self, *args):
        self.log("create_sketch", args)
        return "ok"

    async def exit_sketch(self, *args):
        self.log("exit_sketch", args)
        return "ok"

    async def create_revolve(self, *args):
        self.log("create_revolve", args)
        return "ok"


def _record(monkeypatch) -> list[tuple]:
    adapter = _Recorder()

    async def add_line_chain(_adapter, points, **kwargs):
        adapter.log("add_line_chain", (tuple(points),), kwargs)

    async def volume_check(_adapter, label, expected, tol):
        adapter.log("volume_check", (label, expected, tol))
        return expected

    @contextlib.contextmanager
    def no_inference(_adapter):
        yield

    monkeypatch.setattr(recipe, "check", lambda *a, **k: True)
    monkeypatch.setattr(
        recipe, "name_last_feature", lambda _a, name: adapter.log("name", (name,))
    )
    monkeypatch.setattr(recipe, "volume_check", volume_check)
    monkeypatch.setattr(recipe, "add_line_chain", add_line_chain)
    monkeypatch.setattr(recipe, "no_sketch_inference", no_inference)
    asyncio.run(recipe.build_97482A010(adapter))
    return adapter.events


def test_recipe_section_is_the_rivet_in_the_part_frame(monkeypatch) -> None:
    calls = _record(monkeypatch)
    (arc,) = [c for c in calls if c[0] == "sketch.CreateArc"]
    centre, rim, apex = arc[1][0:3], arc[1][3:6], arc[1][6:9]
    # The dome lands on the Ø HEAD_DIA rim on the bearing face (Top Plane)
    # and peaks HEAD_H above it, about a centre on the axis.
    assert rim[:2] == pytest.approx((spec.HEAD_DIA / 2000.0, 0.0))
    assert apex[:2] == pytest.approx((0.0, spec.HEAD_H / 1000.0))
    assert centre[0] == 0.0
    assert math.dist(centre[:2], rim[:2]) == pytest.approx(
        math.dist(centre[:2], apex[:2])
    )
    (chain,) = [c[1][0] for c in calls if c[0] == "add_line_chain"]
    assert chain[0] == pytest.approx((0.0, spec.HEAD_H))
    assert chain[-1] == pytest.approx((spec.HEAD_DIA / 2.0, 0.0))
    assert min(y for _x, y in chain) == pytest.approx(-spec.LENGTH)
    shank = [x for x, y in chain if y < 0.0 and x > 0.0]
    assert shank and shank == pytest.approx([spec.DIA / 2.0] * len(shank))
    names = [c[1][0] for c in calls if c[0] == "name"]
    assert names == ["RivetProfile", "RivetBody"]
    (volume,) = [c for c in calls if c[0] == "volume_check"]
    assert volume[1][1] == pytest.approx(spec.rivet_volume())


def test_stock_build_uses_its_registered_recipe_on_the_origin(monkeypatch) -> None:
    seen: dict = {}

    async def fake_build(adapter, **kwargs):
        seen.update(kwargs)
        return {}

    monkeypatch.setattr(part, "build_stock_fastener", fake_build)
    asyncio.run(part.build(None))
    (component,) = seen["components"]
    assert component.sku == spec.SKU
    assert component.author is recipe.build_97482A010
    assert component.transform.translation_mm == (0.0, 0.0, 0.0)
    assert component.transform.rotation_radians == (0.0, 0.0, 0.0)
    assert seen["screw_axis_planes"] == ("Front Plane", "Right Plane")


def test_standalone_recipe_run_is_catalog_only(monkeypatch, tmp_path) -> None:
    """No vendor model: the standalone run builds the recipe and saves it
    under the reference directory, never entering the replica path."""
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
    monkeypatch.setattr(recipe, "build_97482A010", fake_recipe)
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


def test_purchased_sheet_documents_the_built_part() -> None:
    import draw_latch_hook_rivet as drawing

    sheet = DRAWINGS_BY_NAME["latch_hook_rivet"]
    assert drawing.SPEC is sheet
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES
