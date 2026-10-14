"""Offline contracts for the MHA-VN-063 pen-hanger locknut (McMaster 90631A009)."""

from __future__ import annotations

import asyncio
import contextlib
import math
import re
from pathlib import Path

import pytest

import _config
import build_vn_pen_hanger_locknut as part
import vn_pen_hanger_locknut_spec as spec
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _test_stock_recipes import discovered_recipes
from diagnostics import diag_build_90631A009 as recipe

STEM = "vn-pen-hanger-locknut"
SHEET = "vn_pen_hanger_locknut"
NUMBER = "MHA-VN-063"
STOCK_NAME = "Low-Strength Steel Nylon-Insert Locknut"
BUILD = "build_90631A009"
IN = 25.4


def test_catalogue_row_is_the_registered_mcmaster_part() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,) == ("90631A009",)
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert stock.stock_name == row["stock_name"] == STOCK_NAME
    assert stock.material == row["material"] == part.MATERIAL == "Plain Carbon Steel"
    assert row["finish"] == "zinc plated"
    assert row["number"] == NUMBER
    assert row["process"] == "purchased"
    assert int(row["quantity"]) == 1
    metadata = discovered_recipes()[spec.SKU]
    assert metadata.module == recipe.__name__
    assert getattr(recipe, metadata.callable_name) is getattr(recipe, BUILD)
    assert metadata.threaded is False


def test_spec_carries_the_live_catalogue_facts() -> None:
    """mcmaster.com/90631A009, read live 2026-10-14."""
    assert spec.THREAD == "#8-32"
    assert spec.ACROSS_FLATS == pytest.approx(11.0 / 32.0 * IN)
    assert spec.THICKNESS == pytest.approx(15.0 / 64.0 * IN)
    # The thread is not modelled: the bore is the #8-32 basic major.
    assert spec.BORE_DIA == pytest.approx(0.164 * IN, abs=0.001)
    assert spec.ACROSS_CORNERS == pytest.approx(
        spec.ACROSS_FLATS / math.cos(math.pi / 6)
    )
    assert spec.MASS_G == pytest.approx(spec.nut_volume() * 7.8e-3)


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

    async def add_line_chain(_adapter, points, close=True):
        adapter.log("lines", (tuple(points),))
        return [f"L{i}" for i in range(len(points))]

    monkeypatch.setattr(recipe, "check", lambda *a, **k: True)
    monkeypatch.setattr(
        recipe, "name_last_feature", lambda _a, name: adapter.log("name", (name,))
    )
    monkeypatch.setattr(recipe, "volume_check", volume_check)
    monkeypatch.setattr(recipe, "define_circle", define_circle)
    monkeypatch.setattr(recipe, "no_sketch_inference", no_inference)
    monkeypatch.setattr(recipe, "add_line_chain", add_line_chain)
    asyncio.run(getattr(recipe, BUILD)(adapter))
    return adapter.events


def test_recipe_is_the_hex_with_a_plain_major_bore(monkeypatch) -> None:
    calls = _record(monkeypatch)
    names = [c[0] for c in calls]
    assert calls[0] == ("create_sketch", ("Top",), {})
    (lines,) = [c[1][0] for c in calls if c[0] == "lines"]
    assert len(lines) == 6
    assert all(
        math.hypot(x, y) == pytest.approx(spec.ACROSS_CORNERS / 2.0) for x, y in lines
    )
    assert max(x for x, _ in lines) - min(x for x, _ in lines) == pytest.approx(
        spec.ACROSS_FLATS
    )
    (circle,) = [c[1] for c in calls if c[0] == "circle"]
    assert circle[:3] == pytest.approx((0.0, 0.0, spec.BORE_DIA / 2.0))
    enter, leave = names.index("no_inference_enter"), names.index("no_inference_exit")
    assert enter < names.index("circle") < leave
    assert names.index("lines") < names.index("exit_sketch")
    (extrude,) = [c for c in calls if c[0] == "create_extrusion"]
    assert extrude[1][0].depth == pytest.approx(spec.THICKNESS)
    assert not extrude[1][0].both_directions
    assert [c[1][0] for c in calls if c[0] == "name"] == ["NutProfile", "NutBody"]
    (volume,) = [c for c in calls if c[0] == "volume_check"]
    hexagon = math.sqrt(3.0) / 2.0 * spec.ACROSS_FLATS**2
    assert volume[1][1] == pytest.approx(
        (hexagon - math.pi / 4.0 * spec.BORE_DIA**2) * spec.THICKNESS
    )


def test_stock_build_turns_the_recipe_axis_onto_part_z(monkeypatch) -> None:
    seen: dict = {}

    async def fake_build(adapter, **kwargs):
        seen.update(kwargs)
        return {}

    monkeypatch.setattr(part, "build_stock_fastener", fake_build)
    asyncio.run(part.build(None))
    (component,) = seen["components"]
    assert component.sku == spec.SKU
    assert component.author is getattr(recipe, BUILD)
    assert component.transform.rotation_radians == pytest.approx(
        (math.pi / 2.0, 0.0, 0.0)
    )
    assert component.transform.translation_mm == (0.0, 0.0, 0.0)
    assert seen["material"] == part.SPEC.material
    assert seen.get("color") is None
    assert seen["screw_axis_planes"] == ("Top Plane", "Right Plane")


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
    monkeypatch.setattr(lib, "mass_properties", lambda _a: {"volume_mm3": 300.0})
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
    import draw_vn_pen_hanger_locknut as drawing

    sheet = DRAWINGS_BY_NAME[SHEET]
    assert drawing.SPEC is sheet
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES
    assert (
        drawing.build.__code__.co_names.count("build_purchased_fastener_drawing") == 1
    )


@pytest.mark.parametrize("stem", [STEM, "vn-hanger-screw"])
def test_installation_note_fits_the_sheet(stem: str) -> None:
    lines = _config.parts(stem)["installation_notes"].splitlines()
    assert len(lines) <= 4
    assert all(len(line) <= 70 for line in lines), lines
    notes = " ".join(lines)
    assert notes.startswith("INSTALLATION - ")
    assert not re.search(r"\d+\.\d|\+/-|±|Ø|MAX|MIN| MM\b", notes)


def test_hanger_screw_runs_through_the_nut_past_the_insert() -> None:
    """Rule 23: the insert locks only on full thread standing past the nut."""
    import build_pn_pen_assembly as pen
    import vn_hanger_screw_spec as screw

    assert pen.HANGER_LOCKNUT_POS[2] == pytest.approx(
        pen.HANGER_STRAP_FRONT_Z - spec.THICKNESS
    )
    assert pen.HANGER_LOCKNUT_POS[:2] == pen.HANGER_SCREW_POS[:2]
    # Two full pitches past the insert end, the screw's tip chamfer excluded.
    assert spec.THREAD_PAST_MIN_PITCHES == 2
    past = pen.HANGER_LOCKNUT_POS[2] - pen.HANGER_SCREW_TIP_Z - screw.TIP_CHAMFER
    assert pen.HANGER_THREAD_PAST_NUT == pytest.approx(past)
    assert past >= 2 * screw.THREAD_PITCH
    # The nut's flats fit the strap face: 5.0 under its top edge.
    assert spec.ACROSS_FLATS / 2.0 < 5.0
