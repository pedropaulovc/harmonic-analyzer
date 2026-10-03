"""Offline contracts for the MHA-184 transgear pivot spring (McMaster 9715K43)."""

from __future__ import annotations

import asyncio
import contextlib
import math
from pathlib import Path

import pytest

import _config
import build_transgear_pivot_spring as part
import transgear_pivot_spring_spec as spec
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _stock_fastener import STOCK_RECIPES
from diagnostics import diag_build_9715K43 as recipe

STEM = "transgear-pivot-spring"
IN = 25.4
LBF = 4.4482216


def test_catalogue_row_is_the_registered_mcmaster_disc_spring() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,) == ("9715K43",)
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert stock.stock_name == row["stock_name"] == "Curved Disc Spring"
    assert stock.material == row["material"] == part.MATERIAL
    assert row["number"] == "MHA-184"
    assert int(row["quantity"]) == spec.COUNT == 1
    metadata = STOCK_RECIPES[spec.SKU]
    assert metadata.module == recipe.__name__
    assert getattr(recipe, metadata.callable_name) is recipe.build_9715K43
    assert metadata.threaded is False


def test_spec_carries_the_live_catalogue_facts() -> None:
    """mcmaster.com/9715K43, read live 2026-10-02."""
    assert spec.ID == pytest.approx(0.200 * IN)
    assert spec.OD == pytest.approx(0.423 * IN)
    assert spec.THICKNESS == pytest.approx(0.0113 * IN)
    assert spec.FREE_HEIGHT == pytest.approx(0.047 * IN)
    assert spec.WORKING_HEIGHT == pytest.approx(0.027 * IN)
    assert spec.WORKING_DEFLECTION == pytest.approx(0.020 * IN)
    assert spec.WORKING_LOAD_N == pytest.approx(9.0 * LBF)
    assert spec.RATE_N_PER_MM == pytest.approx(9.0 * LBF / (0.020 * IN))
    # The model is the installed spring at the nominal room under the head:
    # loaded, but never past the rated working deflection.
    assert spec.MODEL_HEIGHT == spec.INSTALLED_HEIGHT == pytest.approx(0.80)
    assert spec.WORKING_HEIGHT <= spec.MODEL_HEIGHT < spec.FREE_HEIGHT
    assert (spec.FREE_HEIGHT - spec.MODEL_HEIGHT) * spec.RATE_N_PER_MM == (
        pytest.approx(31.0, abs=0.05)
    )
    # "For 0.190" shaft": the bore clears the size it is sold for.
    assert spec.ID > 0.190 * IN


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
        adapter.log("no_inference_enter")
        yield
        adapter.log("no_inference_exit")

    monkeypatch.setattr(recipe, "check", lambda *a, **k: True)
    monkeypatch.setattr(
        recipe, "name_last_feature", lambda _a, name: adapter.log("name", (name,))
    )
    monkeypatch.setattr(recipe, "volume_check", volume_check)
    monkeypatch.setattr(recipe, "add_line_chain", add_line_chain)
    monkeypatch.setattr(recipe, "no_sketch_inference", no_inference)
    asyncio.run(recipe.build_9715K43(adapter))
    return adapter.events


def test_recipe_section_is_the_installed_spring_in_the_part_frame(
    monkeypatch,
) -> None:
    calls = _record(monkeypatch)
    names = [c[0] for c in calls]
    assert calls[0] == ("create_sketch", ("Front",), {})
    # The axis and the section are drawn inside the inference suppression.
    (axis,) = [c for c in calls if c[0] == "sketch.CreateCenterLine"]
    (chain_call,) = [c for c in calls if c[0] == "add_line_chain"]
    enter, leave = names.index("no_inference_enter"), names.index("no_inference_exit")
    assert enter < calls.index(axis) < calls.index(chain_call) < leave
    # The revolve axis is the recipe's Y axis, from the OD rim's face up.
    start, end = axis[1][0:3], axis[1][3:6]
    assert start == (0.0, 0.0, 0.0)
    assert end == pytest.approx((0.0, spec.MODEL_HEIGHT / 1000.0, 0.0))
    chain = chain_call[1][0]
    assert chain_call[2] == {"close": True}
    inner, outer = spec.ID / 2.0, spec.OD / 2.0
    # The parallelogram: outer edge at the OD from the OD rim's bearing face
    # up one thickness, inner edge at the ID up to the installed height.
    assert sorted(chain) == pytest.approx(
        [
            (inner, spec.MODEL_HEIGHT - spec.THICKNESS),
            (inner, spec.MODEL_HEIGHT),
            (outer, 0.0),
            (outer, spec.THICKNESS),
        ]
    )
    # Closed in order round the loop: the outer and inner edges are vertices
    # 0-1 and 2-3, never a diagonal.
    assert {chain[0][0], chain[1][0]} == {outer}
    assert {chain[2][0], chain[3][0]} == {inner}
    assert [c[1][0] for c in calls if c[0] == "name"] == ["SpringProfile", "SpringBody"]
    (revolve,) = [c for c in calls if c[0] == "create_revolve"]
    assert revolve[1][0].angle == 360.0 and revolve[1][0].is_cut is False
    (volume,) = [c for c in calls if c[0] == "volume_check"]
    assert volume[1][1] == pytest.approx(spec.spring_volume())


def test_the_recipe_volume_is_the_section_swept_round_the_axis() -> None:
    """Pappus on the drawn section (shoelace area and centroid radius),
    independent of the closed form the volume check uses."""
    points = recipe.spring_section()
    pairs = list(zip(points, points[1:] + points[:1], strict=True))
    cross = [x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in pairs]
    area = sum(cross) / 2.0
    centroid_r = sum(
        (x0 + x1) * c for ((x0, _), (x1, _)), c in zip(pairs, cross, strict=True)
    ) / (6.0 * area)
    assert area > 0.0  # counter-clockwise, a simple loop
    assert 2.0 * math.pi * centroid_r * area == pytest.approx(
        spec.spring_volume(), rel=1e-9
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
    assert component.author is recipe.build_9715K43
    # Rx(+90 deg) maps the recipe's +Y onto +Z (the transgear-retaining-ring
    # convention); with no lift the OD rim's bearing face stays on z = 0.
    assert component.transform.rotation_radians == pytest.approx(
        (math.pi / 2.0, 0.0, 0.0)
    )
    assert component.transform.translation_mm == (0.0, 0.0, 0.0)
    assert seen["material"] == part.SPEC.material
    # The published axis is the part's Z: Top (XZ) ∩ Right (YZ).
    assert seen["screw_axis_planes"] == ("Top Plane", "Right Plane")


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
    monkeypatch.setattr(recipe, "build_9715K43", fake_recipe)
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
    import draw_transgear_pivot_spring as drawing

    sheet = DRAWINGS_BY_NAME["transgear_pivot_spring"]
    assert drawing.SPEC is sheet
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES
    assert (
        drawing.build.__code__.co_names.count("build_purchased_fastener_drawing") == 1
    )


def test_installation_note_fits_the_sheet() -> None:
    lines = _config.parts(STEM)["installation_notes"].splitlines()
    assert len(lines) <= 4
    assert all(len(line) <= 70 for line in lines), lines
