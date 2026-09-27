"""Offline contracts for the MHA-140 cone tip block hold-down screw (I31)."""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import re
from pathlib import Path

import pytest

import _common
import _config
import _telemetry
import build_cone_tip_block_screw as part
import cone_tip_block_spec as block
import draw_cone_tip_block_screw as drawing
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import THREAD_MAJOR_MM
from _stock_fastener import STOCK_RECIPES
from diagnostics import diag_build_93075A150 as recipe
from diagnostics import diag_build_93075A194 as family_source
from diagnostics import diag_mcmaster_hex_head as family
from diagnostics import diag_mcmaster_lib

IN = 25.4


def test_recipe_is_the_catalogue_screw_the_hold_down_is_sized_for() -> None:
    """93075A150: #6-32 x 5/8, hex head 1/4 x 3/32 (the tip block spec's
    HOLDDOWN_* stack is computed for exactly this screw)."""
    assert part.THREAD == block.FOOT_THREAD == "#6-32"
    assert recipe.PART_NO == "93075A150"
    assert part.SHANK_DIA == pytest.approx(0.138 * IN)
    assert part.SHANK_DIA == pytest.approx(THREAD_MAJOR_MM[block.FOOT_THREAD], abs=5e-4)
    assert part.THREAD_PITCH == block.HOLDDOWN_PITCH_MM == IN / 32.0
    assert part.SHANK_LEN == block.HOLDDOWN_SCREW_LENGTH == 0.625 * IN
    assert part.HEAD_AF == 0.25 * IN
    assert part.HEAD_H == 3.0 / 32.0 * IN


def test_screw_stands_a_pitch_past_the_nut_at_the_thickest_stack() -> None:
    """Main's condition 3: the screw protrudes one pitch past the nylon insert
    at worst case.  No insert height is published, so the whole 11/64 nut
    counts; the block spec asserts this at import from the same length."""
    thinnest, thickest = block.HOLDDOWN_PROTRUSION_MM
    assert thinnest >= part.THREAD_PITCH
    assert thickest > thinnest
    # Full form past the nut once the family's P*0.851 tip chamfer is taken
    # off: reported, not a requirement (the protrusion rule counts the tip).
    assert thinnest - recipe.DIMS.tip_chamfer > 0.0


def test_family_laws_are_93075A194s() -> None:
    """At 93075A194's dimensions the family's derived frame is that recipe's."""
    dims = family.HexHeadScrew(
        part_no="93075A194",
        major_dia=2.0 * family_source.HX_MAJOR_R,
        pitch=family_source.HX_PITCH,
        length=family_source.HX_LEN,
        head_af=family_source.HX_HW,
        head_h=family_source.HX_HH,
    )
    assert dims.underside_y == pytest.approx(family_source.HX_UNDERSIDE, abs=1e-9)
    assert dims.top_y == pytest.approx(7.747, abs=1e-9)
    assert dims.tip_y == pytest.approx(-7.747, abs=1e-9)
    assert dims.crown_r == pytest.approx(2.8575, abs=1e-9)
    assert dims.crown_d == pytest.approx(0.2794, abs=1e-9)
    assert dims.helix_revs == pytest.approx(17.0, abs=1e-9)


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
    return value if isinstance(value, (int, str, bool, type(None))) else repr(type(value))


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
    monkeypatch.setattr(_common, "add_line_chain", async_logger("add_line_chain"))
    monkeypatch.setattr(_common, "_early_bound", lambda obj, _iface: obj)
    monkeypatch.setattr(
        _common,
        "_feature_by_name",
        lambda _adapter, name: adapter.obj(f"feature {name}"),
    )
    monkeypatch.setattr(
        _common, "_read_member", lambda obj, name: getattr(obj, name)
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


def test_93075A150_is_the_family_at_its_catalogue_dimensions(monkeypatch) -> None:
    calls = _record(monkeypatch, recipe.build_93075A150)
    offsets = {args[1]: args[2] for name, args, _kw in calls if name == "offset_plane"}
    dims = recipe.DIMS
    assert offsets["UndersidePlane"] == pytest.approx((15.875 - 2.38125) / 2.0)
    assert offsets["TipPlane"] == pytest.approx(dims.underside_y - 15.875)
    assert offsets["HeadTopPlane"] == pytest.approx(dims.underside_y + 2.38125)
    helix = next(args for name, args, _kw in calls if name == "insert_helix")
    assert helix[1:3] == (IN / 32.0, 15.875 / (IN / 32.0) + 1.0)


def test_stock_build_uses_its_registered_recipe_head_up_on_the_origin(
    monkeypatch,
) -> None:
    metadata = STOCK_RECIPES["93075A150"]
    assert metadata.module == recipe.__name__
    assert metadata.callable_name == recipe.build_93075A150.__name__
    assert part.SPEC.skus == ("93075A150",)
    assert part.SPEC.stock_name == "Low-Strength Zinc-Plated Steel Hex Head Screw"
    assert part.MATERIAL == "Plain Carbon Steel"

    seen: dict = {}

    async def fake_build(adapter, **kwargs):
        seen.update(kwargs)
        return {}

    monkeypatch.setattr(part, "build_stock_fastener", fake_build)
    asyncio.run(part.build(None))
    (component,) = seen["components"]
    assert component.sku == "93075A150"
    assert component.author is recipe.build_93075A150
    # The vendor frame puts the underside (L - HH)/2 above mid-overall; the
    # part moves it to y = 0 so the assembly mates the bearing face at origin.
    assert component.transform.translation_mm == (0.0, -recipe.DIMS.underside_y, 0.0)
    assert component.transform.rotation_radians == (0.0, 0.0, 0.0)
    assert seen["screw_axis_planes"] == ("Front Plane", "Right Plane")


def test_docstring_names_the_real_geometry_source() -> None:
    """Codex P2 (PRRT_kwDOPHDy386l6TBe): the old docstring claimed catalogue
    dimensions while the recipe replayed a vendor model.  It must name the
    catalogue page, the family laws and the gate that proves them, and state
    that no McMaster .SLDPRT is committed."""
    doc = " ".join((part.__doc__ or "").split())
    assert "McMaster product page for 93075A150" in doc
    assert "1/4 in across flats x 3/32 in high" in doc
    assert "diagnostics/diag_build_93075A150.py" in doc
    assert "diagnostics/diag_mcmaster_hex_head.py" in doc
    assert "diagnostics/diag_build_93075A194.py" in doc
    assert "replica gate" in doc
    assert "test_cone_tip_block_screw_drawing.py" in doc
    assert "No McMaster .SLDPRT is committed or used." in doc
    assert "diag_build_91255A148" in doc and "no production part builds from it" in doc
    recipe_doc = " ".join((recipe.__doc__ or "").split())
    assert "https://www.mcmaster.com/93075A150/" in recipe_doc
    assert "no replica gate of its own" in recipe_doc
    assert "catalog-only" in recipe_doc


def test_standalone_recipe_run_is_catalog_only() -> None:
    """No vendor model: the standalone command must not enter the McMaster
    replica path, which demands a vendor SLDPRT and its harvest."""
    source = Path(recipe.__file__).read_text(encoding="utf-8")
    assert "replica_main(" not in source and "import replica_main" not in source
    assert "run_build(build_catalog)" in source
    assert "diag_build_93075A150.py" in (recipe.__doc__ or "")


def test_no_vendor_model_of_the_new_hardware_is_tracked() -> None:
    root = Path(__file__).resolve().parents[2]
    for sku in ("93075A150", "90631A007"):
        assert not list(root.glob(f"cad/references/**/{sku}*.SLDPRT"))


_DIMENSION = re.compile(r"\d")


def test_sheet_carries_no_installation_note_and_no_dimension_in_a_note() -> None:
    """Main (I31): MHA-140's sheet has no INSTALLATION note and no dimension in
    any note (Rule 6).  The purchased sheet prints only the registry's stock
    name, supplier and SKU besides its fixed footer, so none of those may
    carry a size."""
    row = _config.parts(part.PART_NAME)
    assert "installation_notes" not in row
    for field in ("title", "stock_name", "supplier", "finish"):
        assert not _DIMENSION.search(str(row[field])), (field, row[field])
    assert "INSTALLATION" not in Path(drawing.__file__).read_text(encoding="utf-8")


def test_drawing_is_the_purchased_reference_sheet() -> None:
    spec = DRAWINGS_BY_NAME["cone_tip_block_screw"]
    assert drawing.SPEC is spec
    assert spec.artifact_stem == part.PART_NAME
    assert spec.script == Path(drawing.__file__).resolve()
    assert "build_purchased_fastener_drawing" in Path(drawing.__file__).read_text(
        encoding="utf-8"
    )
