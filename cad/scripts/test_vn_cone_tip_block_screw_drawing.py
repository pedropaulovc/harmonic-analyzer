"""Offline contracts for the MHA-VN-030 cone tip block hold-down screw."""

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
import build_vn_cone_tip_block_screw as part
import vn_cone_tip_block_screw_spec as screw
import dt_cone_tip_block_spec as block
import draw_vn_cone_tip_block_screw as drawing
from _drawing_registry import DRAWINGS_BY_NAME
from _stock_fastener import STOCK_RECIPES
from diagnostics import diag_build_91251A108 as recipe
from diagnostics import diag_mcmaster_lib
from diagnostics import diag_mcmaster_socket_head as socket_head

IN = 25.4


def test_recipe_is_the_catalogue_screw() -> None:
    """91251A108 per mcmaster.com (2026-09-29): #4-40 x 3/8, socket head
    0.183 x 0.112, 3/32 hex drive; socket depth is ASME B18.3's #4 minimum
    key engagement, 0.055 in."""
    dims = recipe.DIMS
    assert dims.part_no == "91251A108"
    assert dims.major_dia == pytest.approx(0.112 * IN)
    assert dims.pitch == pytest.approx(IN / 40.0)
    assert dims.length == pytest.approx(0.375 * IN)
    assert dims.head_dia == pytest.approx(0.183 * IN)
    assert dims.head_h == pytest.approx(0.112 * IN)
    assert dims.socket_af == pytest.approx(3.0 / 32.0 * IN)
    assert dims.socket_depth == pytest.approx(0.055 * IN)
    assert dims.underside_y == 0.0


def test_screw_is_the_tip_blocks_hold_down() -> None:
    assert screw.THREAD == block.HOLDDOWN_THREAD
    assert screw.SHANK_LEN == pytest.approx(block.HOLDDOWN_SCREW_LENGTH)


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
    """Compares equal within 1e-12 relative."""

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

    monkeypatch.setattr(socket_head, "check", logger("check", True))
    monkeypatch.setattr(socket_head, "name_last_feature", logger("name_last_feature"))
    async def volume_check(_adapter, label, expected, tol):
        adapter.log("volume_check", (label, expected, tol))
        return expected

    monkeypatch.setattr(socket_head, "volume_check", volume_check)
    monkeypatch.setattr(socket_head, "insert_helix", logger("insert_helix"))
    monkeypatch.setattr(socket_head, "offset_plane", logger("offset_plane"))
    monkeypatch.setattr(socket_head, "thread_sweep_cut", logger("thread_sweep_cut"))
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
    return adapter.events

def test_recipe_cuts_the_catalogue_socket_and_thread(monkeypatch) -> None:
    calls = _record(monkeypatch, recipe.build_91251A108)
    (cut,) = [c for c in calls if c[0] == "fm.FeatureCut4"]
    assert cut[1][5] == recipe.DIMS.socket_depth / 1000.0
    (helix,) = [c for c in calls if c[0] == "insert_helix"]
    assert helix[1][1:3] == (IN / 40.0, 0.375 * IN / (IN / 40.0) + 1.0)
    sweeps = [c for c in calls if c[0] == "thread_sweep_cut"]
    assert [c[1][-1] for c in sweeps] == ["ThreadGroove"]
    assert ("split_at_plane", ("Top Plane", "HeadSplit"), ()) in calls


def test_stock_build_uses_its_registered_recipe_head_up_on_the_origin(
    monkeypatch,
) -> None:
    metadata = STOCK_RECIPES["91251A108"]
    assert metadata.module == recipe.__name__
    assert metadata.callable_name == recipe.build_91251A108.__name__
    assert metadata.threaded
    assert part.SPEC.skus == ("91251A108",)
    assert part.SPEC.stock_name == "Black-Oxide Alloy Steel Socket Head Screw"
    assert part.MATERIAL == "Alloy Steel"
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-VN-030"
    assert row["supplier_skus"] == ["91251A108"]

    seen: dict = {}

    async def fake_build(adapter, **kwargs):
        seen.update(kwargs)
        return {}

    monkeypatch.setattr(part, "build_stock_fastener", fake_build)
    asyncio.run(part.build(None))
    (component,) = seen["components"]
    assert component.sku == "91251A108"
    assert component.author is recipe.build_91251A108
    assert component.transform.translation_mm == (0.0, 0.0, 0.0)
    assert component.transform.rotation_radians == (0.0, 0.0, 0.0)
    assert seen["screw_axis_planes"] == ("Front Plane", "Right Plane")


def test_standalone_recipe_run_is_catalog_only() -> None:
    """No vendor model: the standalone command must not enter the McMaster
    replica path, which demands a vendor SLDPRT and its harvest."""
    source = Path(recipe.__file__).read_text(encoding="utf-8")
    assert "replica_main(" not in source and "import replica_main" not in source
    assert "run_build(build_catalog)" in source


def test_no_vendor_model_of_the_new_hardware_is_tracked() -> None:
    root = Path(__file__).resolve().parents[2]
    assert not list(root.glob("cad/references/**/91251A108*.SLDPRT"))

_DIMENSION = re.compile(r"\d")


def test_sheet_carries_no_installation_note_and_no_dimension_in_a_note() -> None:
    """Main (I31): MHA-VN-030's sheet has no INSTALLATION note and no dimension in
    any note (Rule 6).  The purchased sheet prints only the registry's stock
    name, supplier and SKU besides its fixed footer, so none of those may
    carry a size."""
    row = _config.parts(part.PART_NAME)
    assert "installation_notes" not in row
    for field in ("title", "stock_name", "supplier", "finish"):
        assert not _DIMENSION.search(str(row[field])), (field, row[field])
    assert "INSTALLATION" not in Path(drawing.__file__).read_text(encoding="utf-8")


def test_drawing_is_the_purchased_reference_sheet() -> None:
    spec = DRAWINGS_BY_NAME["vn_cone_tip_block_screw"]
    assert drawing.SPEC is spec
    assert spec.artifact_stem == part.PART_NAME
    assert spec.script == Path(drawing.__file__).resolve()
    assert "build_purchased_fastener_drawing" in Path(drawing.__file__).read_text(
        encoding="utf-8"
    )
