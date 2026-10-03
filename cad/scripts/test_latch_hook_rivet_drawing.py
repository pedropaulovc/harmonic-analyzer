"""Offline contracts for the MHA-175 latch-hook rivet (McMaster 97482A015)."""

from __future__ import annotations

import asyncio
import contextlib
import importlib.util
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
from diagnostics import diag_build_97482A015 as recipe

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
    assert getattr(recipe, metadata.callable_name) is recipe.build_97482A015
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
    assert worst_grip <= 0.157 * IN == pytest.approx(spec.MAX_GRIP)
    # One match-drilled hole: the smallest either sheet may print.
    assert hook.RIVET_HOLE_DIA == bracket.RIVET_HOLE_DIA
    smallest = hook.RIVET_HOLE_DIA + max(
        min(hook_spec.HOLE_BAND), min(bracket_spec.HOLE_BAND)
    )
    assert spec.DIA < smallest
    # The vendor's #51 hole now lies inside the printed band.
    largest = hook.RIVET_HOLE_DIA + min(
        max(hook_spec.HOLE_BAND), max(bracket_spec.HOLE_BAND)
    )
    assert smallest < spec.VENDOR_HOLE_DIA < largest


# ASME B18.1.1, 1/16 solid rivet: shank Ø0.064 max / 0.059 min, length
# +/-0.016 in; MIL-R-47196A Table III, 1/16 driven head Ø0.081 min x 0.025
# min thick.
_SHANK_MAX, _SHANK_MIN, _LENGTH_TOL = 0.064 * IN, 0.059 * IN, 0.016 * IN
_HEAD_DIA_MIN, _HEAD_T_MIN = 0.081 * IN, 0.025 * IN


def _worst_rivet_corners(hole_dia: float, length: float) -> tuple[float, float]:
    """(least shank clearance, least shop-head volume) of a 1/16 rivet of
    ``length`` in a hole ``hole_dia`` drilled to the printed +0.10/0 band in
    the strip and the flap (or to the vendor's #51 drill), over a 0.6 strip on
    the 1.5 sheet at its thickest stock."""
    drilled = (hole_dia, hole_dia + 0.10, 0.067 * IN)
    grip = hook.STRIP_T + bracket.SHEET_T + bracket.SHEET_T_PLUS
    clearance = min(drilled) - _SHANK_MAX
    area = math.pi / 4.0
    head = min(
        area * shank**2 * (rivet - grip) - area * (hole**2 - shank**2) * grip
        for hole in drilled
        for shank in (_SHANK_MIN, _SHANK_MAX)
        for rivet in (length - _LENGTH_TOL, length + _LENGTH_TOL)
    )
    return clearance, head


def test_every_rivet_corner_clears_the_shank_and_forms_the_shop_head() -> None:
    """R9-51: the largest B18.1.1 shank enters the least printed hole, and
    the shortest, thinnest rivet in the largest hole over the thickest grip
    leaves the MIL-R-47196A shop head."""
    need = math.pi / 4.0 * _HEAD_DIA_MIN**2 * _HEAD_T_MIN  # 2.111 mm^3
    clearance, head = _worst_rivet_corners(hook.RIVET_HOLE_DIA, spec.LENGTH)
    assert clearance == pytest.approx(0.0244, abs=1e-4)
    assert head == pytest.approx(2.392, abs=1e-3) and head >= need
    assert spec.SHANK_CLEARANCE_MIN == pytest.approx(clearance)
    assert spec.SHOP_HEAD_VOLUME_WORST == pytest.approx(head)
    # Negative controls: the old Ø1.6 hole binds the largest shank, and the
    # 1/8 rivet in the Ø1.65 hole leaves too little for the head.
    assert _worst_rivet_corners(1.6, spec.LENGTH)[0] < 0.0
    assert _worst_rivet_corners(1.65, IN / 8.0)[1] < need


def _reload_rivet_spec():
    fresh_spec = importlib.util.spec_from_file_location(
        "_rivet_perturbed", spec.__file__
    )
    fresh = importlib.util.module_from_spec(fresh_spec)
    fresh_spec.loader.exec_module(fresh)
    return fresh


def test_the_rivet_gate_refuses_the_old_hole_and_the_short_rivet(monkeypatch) -> None:
    assert _reload_rivet_spec().SHOP_HEAD_VOLUME_WORST == spec.SHOP_HEAD_VOLUME_WORST
    with monkeypatch.context() as m:
        m.setattr(hook, "RIVET_HOLE_DIA", 1.6)
        m.setattr(bracket, "RIVET_HOLE_DIA", 1.6)
        with pytest.raises(AssertionError, match=r"MHA-175 rivet .* binds"):
            _reload_rivet_spec()
    # The 1/8 rivet: the spec's own source with the old length.
    source = (
        Path(spec.__file__)
        .read_text(encoding="utf-8")
        .replace("LENGTH = 3.0 * MM_PER_IN / 16.0", "LENGTH = 0.125 * MM_PER_IN")
    )
    assert "LENGTH = 0.125 * MM_PER_IN" in source
    with pytest.raises(AssertionError, match=r"MHA-175 rivet .* shop head"):
        exec(compile(source, spec.__file__, "exec"), {"__name__": "_rivet_short"})


def test_the_lock_sweep_clears_either_end_of_the_rivet(monkeypatch) -> None:
    """The model shows the rivet undriven: its tail stands 2.66 past the
    flap's outer face (3.17 at the longest rivet in the thinnest grip).  The
    guide-lock stations sweep past it unbounded in x, so the sweep's rivet
    section must hold the widest end: the 0.130-in dome, or the shop head the
    most shank the joint leaves makes at MIL-R-47196A's least thickness."""
    import build_paper_drive_assembly as assembly

    holes = (hook.RIVET_HOLE_DIA, hook.RIVET_HOLE_DIA + 0.10, 0.067 * IN)
    grips = (
        hook.STRIP_T + bracket.SHEET_T - bracket.SHEET_T_MINUS,
        hook.STRIP_T + bracket.SHEET_T + bracket.SHEET_T_PLUS,
    )
    area = math.pi / 4.0
    most = max(
        area * shank**2 * (rivet - grip) - area * (hole**2 - shank**2) * grip
        for hole in holes
        for shank in (_SHANK_MIN, _SHANK_MAX)
        for rivet in (3.0 * IN / 16.0 - _LENGTH_TOL, 3.0 * IN / 16.0 + _LENGTH_TOL)
        for grip in grips
    )
    shop_head = math.sqrt(most / (area * _HEAD_T_MIN))
    assert shop_head == pytest.approx(3.597, abs=1e-3)
    assert 3.0 * IN / 16.0 + _LENGTH_TOL - grips[0] == pytest.approx(
        spec.TAIL_PROUD_MAX
    )
    dome = 0.130 * IN
    envelope = max(dome, shop_head)
    assert spec.ENVELOPE_DIA == pytest.approx(envelope)

    def rivet_gap() -> float:
        lines: list[str] = []
        monkeypatch.setattr(assembly, "log", lines.append)
        assembly._assert_lock_station_sweep()
        (line,) = lines
        return float(re.search(r"latch-hook rivet (-?\d+\.\d+)", line).group(1))

    gap = rivet_gap()
    assert gap >= assembly.LOCK_SWEEP_FLOOR
    monkeypatch.setattr(spec, "ENVELOPE_DIA", dome)
    # Each side grows by half the excess; across a corner the gap is the
    # hypotenuse, so it shrinks by between that and sqrt(2) times it.
    grow = (envelope - dome) / 2.0
    dome_gap = rivet_gap()
    assert dome_gap - math.sqrt(2.0) * grow - 1e-3 <= gap <= dome_gap - grow + 1e-3
    # Negative control: an end 0.02 wider than the sweep's margin fouls it.
    breaking = envelope + 2.0 * (gap - assembly.LOCK_SWEEP_FLOOR) + 0.02
    monkeypatch.setattr(spec, "ENVELOPE_DIA", breaking)
    with pytest.raises(AssertionError, match="latch-hook rivet"):
        assembly._assert_lock_station_sweep()


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
    asyncio.run(recipe.build_97482A015(adapter))
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
    assert component.author is recipe.build_97482A015
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
    monkeypatch.setattr(recipe, "build_97482A015", fake_recipe)
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
