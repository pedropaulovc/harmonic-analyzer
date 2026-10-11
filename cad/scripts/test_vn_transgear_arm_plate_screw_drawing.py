"""Offline contracts for the MHA-VN-040 transgear arm-plate screws."""

from __future__ import annotations

import asyncio
import contextlib
import math
import re
from pathlib import Path

import pytest

import _sketch
import _sketch_rectangle
import _config
import _telemetry
import build_vn_transgear_arm_plate_screw as part
import draw_vn_transgear_arm_plate_screw as drawing
import pd_transgear_arm_geometry as arm
import pd_transgear_arm_plate_geometry as plate
import vn_transgear_arm_plate_screw_spec as screw
import transgear_hanger_joints as joints
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _test_stock_recipes import discovered_recipes
from diagnostics import diag_build_91790A196 as entry
from diagnostics import diag_mcmaster_lib
from diagnostics import diag_mcmaster_oval as recipe

IN = 25.4


def test_spec_is_the_catalogue_screw() -> None:
    """91790A196 ([INFERENCE] SKU; the series per mcmaster.com, 2026-09-30):
    8-32 x 5/8 from the top of the bevel, 82 deg oval head Ø0.312 x 0.152
    total, crown 0.052, the B18.6.3 length band +0/-0.03 in."""
    assert screw.SKU == "91790A196"
    assert screw.THREAD == "#8-32"
    assert screw.THREAD_MAJOR == pytest.approx(0.164 * IN)
    assert screw.PITCH == pytest.approx(IN / 32.0)
    assert screw.STOCK_LENGTH == pytest.approx(0.625 * IN)
    assert screw.STOCK_LENGTH_BAND == pytest.approx((0.0, 0.03 * IN))
    assert screw.HEAD_DIA == pytest.approx(0.312 * IN)
    assert screw.HEAD_H == pytest.approx(0.152 * IN)
    assert screw.CROWN_H == pytest.approx(0.052 * IN)
    assert screw.HEAD_ANGLE_DEG == 82.0
    # The shared recipe's row is the supplied screw, not the cut one.
    assert recipe.OVAL_SIZES[screw.SKU] == (
        screw.THREAD_MAJOR,
        screw.STOCK_LENGTH,
        screw.HEAD_DIA,
        screw.CROWN_H,
        screw.HEAD_ANGLE_DEG,
        screw.PITCH,
    )


def test_the_cut_is_flush_with_the_arm_front_face() -> None:
    """Bevel top flush with the plate's rear face, so the tip is flush with
    the arm's front face after the plate's over-arm section and the arm."""
    assert screw.CUT_LENGTH == pytest.approx(plate.THICKNESS_OVER_ARM + arm.THICKNESS)
    assert screw.LENGTH == screw.CUT_LENGTH
    assert screw.CUT_END_BREAK_MAX == pytest.approx(0.1)
    # Even the shortest in-band screw is cut on full thread, below its
    # factory tip.
    shortest = screw.STOCK_LENGTH - screw.STOCK_LENGTH_BAND[1]
    assert shortest - recipe.TIP_CHAMFER_PER_PITCH * screw.PITCH > screw.CUT_LENGTH


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


def _record(monkeypatch, *, supplied: bool = False) -> list[tuple]:
    """Record the part's build (the installed, cut screw) or, ``supplied``,
    the recipe's own catalog build of the screw as bought."""
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
    monkeypatch.setattr(_sketch, "add_line_chain", add_line_chain)
    monkeypatch.setattr(_sketch_rectangle, "add_line_chain", add_line_chain)
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

    async def stock_build(_adapter, **kwargs):
        # As build_stock_fastener calls each component's recipe.
        for component in kwargs["components"]:
            if component.parameters is None:
                await component.author(adapter, None)
            else:
                await component.author(adapter, None, **component.parameters)
        return {}

    if supplied:
        asyncio.run(entry.build_91790A196(adapter))
    else:
        monkeypatch.setattr(part, "build_stock_fastener", stock_build)
        asyncio.run(part.build(adapter))
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
    # The modelled shank runs LENGTH from the top of the bevel to the cut end.
    profile = _chains(calls)[0]
    assert min(y for _x, y in profile) == pytest.approx(-screw.LENGTH)
    assert max(x for x, _y in profile) == pytest.approx(screw.HEAD_DIA / 2.0)


def _revolved_volume(length: float, end_chamfer: float) -> float:
    """Crown cap + 82 deg bevel frustum + shank + 45 deg end frustum,
    independent of the recipe's arithmetic."""
    head_r, major_r = screw.HEAD_DIA / 2.0, screw.THREAD_MAJOR / 2.0
    crown = screw.CROWN_H
    bevel = -_junction_y()

    def frustum(h: float, r1: float, r2: float) -> float:
        return math.pi * h * (r1 * r1 + r1 * r2 + r2 * r2) / 3.0

    return (
        math.pi * crown * (3.0 * head_r**2 + crown**2) / 6.0
        + frustum(bevel, head_r, major_r)
        + math.pi * major_r**2 * (length - bevel - end_chamfer)
        + frustum(end_chamfer, major_r, major_r - end_chamfer)
    )


def _end_of_shank(calls) -> list[tuple[float, float]]:
    profile = _chains(calls)[0]
    major_r = screw.THREAD_MAJOR / 2.0
    start = max(i for i, (x, _y) in enumerate(profile) if x == pytest.approx(major_r))
    return list(profile[start : start + 2])


def test_part_is_the_installed_screw_cut_flush_with_its_end_broken(monkeypatch) -> None:
    """The part ends at the cut (y = -CUT_LENGTH) with a 45 deg break of
    CUT_END_BREAK_MAX in place of the factory tip, and the revolved body's
    volume check expects that cut body."""
    calls = _record(monkeypatch)
    major_r = screw.THREAD_MAJOR / 2.0
    brk = screw.CUT_END_BREAK_MAX
    assert _end_of_shank(calls) == pytest.approx(
        [(major_r, -(screw.CUT_LENGTH - brk)), (major_r - brk, -screw.CUT_LENGTH)]
    )
    (volume,) = [c for c in calls if c[0] == "volume_check"]
    assert volume[1][1] == pytest.approx(_revolved_volume(screw.CUT_LENGTH, brk))


def test_catalog_build_is_the_supplied_screw(monkeypatch) -> None:
    """Without a cut the recipe builds the screw as bought: STOCK_LENGTH with
    the family's 45 deg x 0.7P factory tip."""
    calls = _record(monkeypatch, supplied=True)
    major_r = screw.THREAD_MAJOR / 2.0
    tip = 0.7 * screw.PITCH
    assert _end_of_shank(calls) == pytest.approx(
        [(major_r, -(screw.STOCK_LENGTH - tip)), (major_r - tip, -screw.STOCK_LENGTH)]
    )
    (volume,) = [c for c in calls if c[0] == "volume_check"]
    assert volume[1][1] == pytest.approx(_revolved_volume(screw.STOCK_LENGTH, tip))


@pytest.mark.parametrize(
    ("cut_length", "cut_end_break"),
    [
        (screw.CUT_LENGTH, None),  # half a cut
        (None, screw.CUT_END_BREAK_MAX),
        (screw.STOCK_LENGTH, screw.CUT_END_BREAK_MAX),  # leaves the factory tip
        (screw.CUT_LENGTH, 0.0),  # an unbroken cut end
        (-_junction_y(), screw.CUT_END_BREAK_MAX),  # no shank under the bevel
    ],
)
def test_recipe_refuses_a_cut_it_cannot_draw(cut_length, cut_end_break) -> None:
    with pytest.raises(ValueError):
        recipe.revolved_volume(screw.SKU, cut_length, cut_end_break)


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
    metadata = discovered_recipes()[screw.SKU]
    assert metadata.module == entry.__name__
    assert metadata.callable_name == entry.build_91790A196.__name__
    assert metadata.threaded
    assert FASTENERS[part.PART_NAME] is part.SPEC
    assert part.SPEC.skus == (screw.SKU,)
    assert part.MATERIAL == "AISI 304"
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-VN-040"
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
    assert component.author is entry.build_91790A196
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
    assert seen == [(screw.SKU, entry.build_91790A196)]


def test_no_vendor_model_of_the_new_hardware_is_tracked() -> None:
    root = Path(__file__).resolve().parents[2]
    assert not list(root.glob(f"cad/references/**/{screw.SKU}*.SLDPRT"))


# A size on the sheet's registry-printed fields: a thread (#8-32), a fraction,
# a length with units, or an "x" between numbers.  The 18-8 grade is not one.
_SIZE = re.compile(r"#\d|\d+/\d+|\d\s*(?:mm|in\b|\")|\d\s*[xX]\s*\d|°")


def test_sheet_states_the_cut_and_no_size_in_the_registry_names() -> None:
    """The purchased sheet prints the registry's stock name, supplier and
    SKU besides its fixed footer, so none of those may carry a size; the
    installation note states the cut to fit (the joint's proud allowance,
    as the paper-drive assembly step prints it) and the cut end's break."""
    row = _config.parts(part.PART_NAME)
    for field in ("title", "stock_name", "supplier", "finish", "material"):
        assert not _SIZE.search(str(row[field])), (field, row[field])
    lines = row["installation_notes"].splitlines()
    assert len(lines) <= 4
    assert all(len(line) <= 70 for line in lines), lines
    flat = " ".join(lines)
    proud = joints.PLATE_SCREW_CUT_PROUD_MAX
    assert (
        f"CUT EACH TIP FLUSH TO {proud:.2f} PROUD OF THE MHA-PD-018 ARM FRONT FACE "
        "AT ASSEMBLY;"
    ) in flat
    assert f"BREAK THE CUT END {screw.CUT_END_BREAK_MAX:.1f} MAX." in flat


def test_drawing_is_the_purchased_reference_sheet() -> None:
    spec = DRAWINGS_BY_NAME["vn_transgear_arm_plate_screw"]
    assert drawing.SPEC is spec
    assert spec.artifact_stem == part.PART_NAME
    assert spec.script == Path(drawing.__file__).resolve()
    assert (
        drawing.build.__code__.co_names.count("build_purchased_fastener_drawing") == 1
    )
