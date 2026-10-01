"""Offline contracts for the MHA-166 transgear arm-plate screws."""

from __future__ import annotations

import asyncio
import contextlib
import math
import re
from pathlib import Path

import pytest

import _common
import _config
import _telemetry
import build_transgear_arm_plate_screw as part
import draw_transgear_arm_plate_screw as drawing
import transgear_arm_plate_geometry as plate
import transgear_arm_plate_screw_spec as screw
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _stock_fastener import STOCK_RECIPES
from diagnostics import diag_build_91790A194 as entry
from diagnostics import diag_mcmaster_lib
from diagnostics import diag_mcmaster_oval as recipe

IN = 25.4


def test_spec_is_the_catalogue_screw() -> None:
    """91790A194 per mcmaster.com (2026-09-30): 8-32 x 1/2 from the top of
    the bevel, 82 deg oval head Ø0.312 x 0.152 total, crown 0.052."""
    assert screw.SKU == "91790A194"
    assert screw.THREAD == "#8-32"
    assert screw.THREAD_MAJOR == pytest.approx(0.164 * IN)
    assert screw.PITCH == pytest.approx(IN / 32.0)
    assert screw.LENGTH == pytest.approx(0.5 * IN)
    assert screw.HEAD_DIA == pytest.approx(0.312 * IN)
    assert screw.HEAD_H == pytest.approx(0.152 * IN)
    assert screw.CROWN_H == pytest.approx(0.052 * IN)
    assert screw.HEAD_ANGLE_DEG == 82.0
    assert recipe.OVAL_SIZES[screw.SKU] == (
        screw.THREAD_MAJOR,
        screw.LENGTH,
        screw.HEAD_DIA,
        screw.CROWN_H,
        screw.HEAD_ANGLE_DEG,
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

    async def create_cut_extrude(self, *args):
        return await self._async("create_cut_extrude", *args)

    async def add_fillet(self, *args):
        return await self._async("add_fillet", *args)


def _junction_y() -> float:
    """Where an 82 deg cone from the Ø HEAD_DIA rim at y = 0 meets the
    thread major (independent of the recipe's own arithmetic)."""
    half = math.radians(screw.HEAD_ANGLE_DEG / 2.0)
    return -(screw.HEAD_DIA - screw.THREAD_MAJOR) / 2.0 / math.tan(half)


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

    # The head body reaches below y = -1 (the bevel runs to the junction), so
    # the shank must be told apart by more than "extends below -1 mm".
    junction = _junction_y()
    boxes = [
        {"name": "Shank", "box_mm": [-2.1, -screw.LENGTH, -2.1, 2.1, junction, 2.1]},
        {"name": "Head", "box_mm": [-4.0, junction, -4.0, 4.0, screw.CROWN_H, 4.0]},
    ]
    monkeypatch.setattr(recipe, "check", logger("check", True))
    monkeypatch.setattr(recipe, "name_last_feature", logger("name_last_feature"))
    monkeypatch.setattr(recipe, "volume_check", volume_check)
    monkeypatch.setattr(recipe, "insert_helix", logger("insert_helix"))
    monkeypatch.setattr(recipe, "thread_sweep_cut", logger("thread_sweep_cut"))
    monkeypatch.setattr(_common, "add_line_chain", add_line_chain)
    monkeypatch.setattr(diag_mcmaster_lib, "no_sketch_inference", no_inference)
    monkeypatch.setattr(diag_mcmaster_lib, "offset_plane", logger("offset_plane"))
    monkeypatch.setattr(
        diag_mcmaster_lib,
        "split_at_plane",
        lambda _adapter, plane_name, name: (
            adapter.log("split_at_plane", (plane_name, name)),
            boxes,
        )[1],
    )
    monkeypatch.setattr(_telemetry, "info", lambda *a, **k: None)
    asyncio.run(entry.build_91790A194(adapter))
    return adapter.events


def _chains(calls) -> list[tuple]:
    return [c[1][0] for c in calls if c[0] == "add_line_chain"]


def _profile_below_bevel_top(calls) -> list[tuple[float, float]]:
    profile = _chains(calls)[0]
    return [p for p in profile if p[1] <= 0.0 and p[0] > 0.0]


def test_recipe_puts_the_top_of_the_bevel_on_the_top_plane(monkeypatch) -> None:
    calls = _record(monkeypatch)
    (arc,) = [c for c in calls if c[0] == "sketch.Create3PointArc"]
    apex, rim = arc[1][0:3], arc[1][3:6]
    # The crown rises CROWN_H above y = 0 and lands on the Ø HEAD_DIA rim at
    # y = 0, the plane that sits flush with the plate's rear face.
    assert apex[:2] == pytest.approx((0.0, screw.CROWN_H / 1000.0))
    assert rim[:2] == pytest.approx((screw.HEAD_DIA / 2000.0, 0.0))
    # The shank runs LENGTH from the top of the bevel to the tip.
    profile = _chains(calls)[0]
    assert min(y for _x, y in profile) == pytest.approx(-screw.LENGTH)
    assert max(x for x, _y in profile) == pytest.approx(screw.HEAD_DIA / 2.0)


def test_head_seats_in_the_plate_countersink_without_interference(monkeypatch) -> None:
    """Through the plate's thickness the modelled screw never leaves the
    countersink cone or the clearance hole under it, and its bevel bears on
    the countersink (not only on the rim)."""
    half = math.radians(plate.CSK_ANGLE_DEG / 2.0)

    def envelope(depth: float) -> float:
        cone = plate.CSK_DIA / 2.0 - depth * math.tan(half)
        return max(cone, plate.SCREW_HOLE_DIA / 2.0)

    def head_radius(depth: float) -> float:
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            if -y0 <= depth <= -y1 and y0 != y1:
                return x0 + (x1 - x0) * (-depth - y0) / (y1 - y0)
        raise AssertionError(f"no profile at depth {depth}")

    points = _profile_below_bevel_top(_record(monkeypatch))
    steps = 400
    for i in range(steps + 1):
        depth = plate.THICKNESS_OVER_ARM * i / steps
        assert head_radius(depth) <= envelope(depth) + 1e-9, depth
    # Seated: the bevel is on the countersink cone halfway down it.
    mid = plate.CSK_DEPTH / 2.0
    assert head_radius(mid) == pytest.approx(envelope(mid))
    # The countersink reaches the clearance hole before the bevel ends, so
    # the thread passes the Ø hole with radial clearance.
    assert plate.CSK_DEPTH < -_junction_y()
    assert screw.THREAD_MAJOR < plate.SCREW_HOLE_DIA


def test_recipe_threads_the_shank_to_under_the_head(monkeypatch) -> None:
    calls = _record(monkeypatch)
    junction = _junction_y()
    # The bevel meets the thread major at the junction ...
    profile = _chains(calls)[0]
    major_r = screw.THREAD_MAJOR / 2.0
    top_of_shank = max(y for x, y in profile if x == pytest.approx(major_r))
    assert top_of_shank == pytest.approx(junction)
    # ... and the body is split there, so the scoped thread starts under it.
    (plane,) = [c for c in calls if c[0] == "offset_plane"]
    plane_name, offset = plane[1][1:3]
    assert offset == pytest.approx(junction)
    assert ("split_at_plane", (plane_name, "HeadSplit"), {}) in calls
    (sweep,) = [c for c in calls if c[0] == "thread_sweep_cut"]
    assert sweep[1][3:] == ("Shank", "ThreadGroove")
    # The helix, seeded at the top of the bevel, runs past the tip.
    (helix,) = [c for c in calls if c[0] == "insert_helix"]
    pitch, revs = helix[1][1:3]
    assert pitch == pytest.approx(screw.PITCH)
    assert revs * pitch >= screw.LENGTH
    # The runout fill starts at the junction and stays on the major diameter.
    runout = _chains(calls)[-1]
    assert max(y for _x, y in runout) == pytest.approx(junction)
    assert max(x for x, _y in runout) == pytest.approx(major_r)


def test_driver_slot_stops_inside_the_oval_head(monkeypatch) -> None:
    calls = _record(monkeypatch)
    slot = _chains(calls)[1]
    slot_floor = min(y for _x, y in slot)
    assert _junction_y() < slot_floor < screw.CROWN_H
    assert max(y for _x, y in slot) > screw.CROWN_H  # open through the crown


def test_stock_build_uses_its_registered_recipe_head_up_on_the_origin(
    monkeypatch,
) -> None:
    metadata = STOCK_RECIPES[screw.SKU]
    assert metadata.module == entry.__name__
    assert metadata.callable_name == entry.build_91790A194.__name__
    assert metadata.threaded
    assert FASTENERS[part.PART_NAME] is part.SPEC
    assert part.SPEC.skus == (screw.SKU,)
    assert part.MATERIAL == "AISI 304"
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-166"
    assert int(row["quantity"]) == 2
    assert row["supplier_skus"] == [screw.SKU]
    assert row["stock_name"] == part.SPEC.stock_name

    seen: dict = {}

    async def fake_build(adapter, **kwargs):
        seen.update(kwargs)
        return {}

    monkeypatch.setattr(part, "build_stock_fastener", fake_build)
    asyncio.run(part.build(None))
    (component,) = seen["components"]
    assert component.sku == screw.SKU
    assert component.author is entry.build_91790A194
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
    assert seen == [(screw.SKU, entry.build_91790A194)]


def test_no_vendor_model_of_the_new_hardware_is_tracked() -> None:
    root = Path(__file__).resolve().parents[2]
    assert not list(root.glob(f"cad/references/**/{screw.SKU}*.SLDPRT"))


# A size on the sheet's registry-printed fields: a thread (#8-32), a fraction,
# a length with units, or an "x" between numbers.  The 18-8 grade is not one.
_SIZE = re.compile(r"#\d|\d+/\d+|\d\s*(?:mm|in\b|\")|\d\s*[xX]\s*\d|°")


def test_sheet_carries_no_installation_note_and_no_size_in_a_note() -> None:
    """The purchased sheet prints only the registry's stock name, supplier and
    SKU besides its fixed footer, so none of those may carry a size (Rule 6)."""
    row = _config.parts(part.PART_NAME)
    assert "installation_notes" not in row
    for field in ("title", "stock_name", "supplier", "finish", "material"):
        assert not _SIZE.search(str(row[field])), (field, row[field])


def test_drawing_is_the_purchased_reference_sheet() -> None:
    spec = DRAWINGS_BY_NAME["transgear_arm_plate_screw"]
    assert drawing.SPEC is spec
    assert spec.artifact_stem == part.PART_NAME
    assert spec.script == Path(drawing.__file__).resolve()
    assert (
        drawing.build.__code__.co_names.count("build_purchased_fastener_drawing") == 1
    )
