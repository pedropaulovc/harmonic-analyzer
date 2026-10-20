"""Offline contracts for the MHA-VN-040 transgear arm-plate screws."""

from __future__ import annotations

import asyncio
import contextlib
import math
import re
import types
from pathlib import Path

import pytest
from solidworks_mcp.adapters.base import AdapterResult, AdapterResultStatus

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
from _simplified_names import is_simplified, simplified_name
from _test_stock_recipes import discovered_recipes
from diagnostics import diag_build_91790A199 as entry
from diagnostics import diag_mcmaster_lib
from diagnostics import diag_mcmaster_oval as recipe

IN = 25.4


def test_spec_is_the_catalogue_screw() -> None:
    """Verified 91790A199: 8-32 x 1 inch from the bevel top, standard oval.

    Catalogue head height 0.152 and crown 0.052 are reference dimensions,
    not supplied head/length tolerance bands or actual receipt readings.
    """
    assert screw.SKU == "91790A199"
    assert entry.PART_NO == screw.SKU
    assert screw.THREAD == "#8-32"
    assert screw.THREAD_MAJOR == pytest.approx(0.164 * IN)
    assert screw.PITCH == pytest.approx(IN / 32.0)
    assert screw.STOCK_LENGTH == pytest.approx(IN)
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
    assert joints.PLATE_SCREW_STOCK_LEAD_MARGIN_MM > 0.0

def _cone_depth() -> float:
    """Where an 82 deg cone from the Ø HEAD_DIA rim at y = 0 meets the
    thread major (independent of the recipe's own arithmetic)."""
    half = math.radians(screw.HEAD_ANGLE_DEG / 2.0)
    return (screw.HEAD_DIA - screw.THREAD_MAJOR) / 2.0 / math.tan(half)


# The supplier STEP's own readings (FreeCAD, sha256 8dce9258...71bb), as
# measured: axis +X, bevel top x = -12.7.
_STEP_THREAD_START_X = -10.16
_STEP_FILLET_MINOR_R = 0.377767541787383
_STEP_FILLET_CENTRE_X = -10.396526045506446
_STEP_FILLET_CONE_TANGENT_X = -10.644363852155609  # torus true extent, cone side
_STEP_STEP_R = 1.9558
_STEP_THREAD_START_CONE_END_X = -9.935667234187066


def test_underhead_transition_is_the_supplier_step() -> None:
    """The neck ends and the thread starts at H = .100 in below the bevel
    top (.152 total less .052 crown), and the cone-to-neck fillet is the
    STEP's torus, not the fillister family's P/10 at the cone corner."""
    assert screw.THREAD_START_DEPTH == pytest.approx(0.100 * IN, abs=1e-12)
    assert screw.THREAD_START_DEPTH == pytest.approx(screw.HEAD_H - screw.CROWN_H)
    assert screw.THREAD_START_DEPTH == pytest.approx(_STEP_THREAD_START_X + 12.7, abs=1e-9)
    assert screw.BEVEL_CONE_DEPTH == pytest.approx(_cone_depth())
    assert screw.UNDER_HEAD_FILLET_R == pytest.approx(_STEP_FILLET_MINOR_R, abs=1e-9)
    assert screw.UNDER_HEAD_FILLET_R != pytest.approx(screw.PITCH / 10.0)
    deflection = math.radians(screw.HEAD_ANGLE_DEG / 2.0)
    tangent = screw.UNDER_HEAD_FILLET_R * math.tan(deflection / 2.0)
    assert _cone_depth() + tangent == pytest.approx(_STEP_FILLET_CENTRE_X + 12.7, abs=1e-9)
    assert _cone_depth() - tangent * math.cos(deflection) == pytest.approx(
        _STEP_FILLET_CONE_TANGENT_X + 12.7, abs=1e-6
    )
    assert screw.THREAD_START_STEP_R == pytest.approx(_STEP_STEP_R, abs=1e-9)
    assert screw.THREAD_START_CONE_HALF_ANGLE_DEG == 60.0
    assert recipe.thread_start_cone_end(screw.SKU) == pytest.approx(
        _STEP_THREAD_START_CONE_END_X + 12.7, abs=1e-4
    )
    assert recipe.fillet_neck_tangent(screw.SKU) == pytest.approx(
        _STEP_FILLET_CENTRE_X + 12.7, abs=1e-9
    )


def test_supplier_references_land_on_the_stock_spans() -> None:
    """The 1 in spans the full stock (bevel top to factory tip), never the
    installed cut; .152 runs crown apex to the STEP's thread start; and no
    row sizes the thread major, which the supplier drawing does not show."""
    rows = {name: value for name, value, _ in screw.SUPPLIER_REFERENCE_DIMENSIONS}
    starts = screw.SUPPLIER_REFERENCE_STARTS
    assert all(abs(value) != pytest.approx(screw.THREAD_MAJOR) for value in rows.values())
    assert all(abs(value) != pytest.approx(screw.CUT_LENGTH) for value in rows.values())
    _x, top = starts["SupplierStockLength"]
    assert top == pytest.approx(0.0)
    assert top + rows["SupplierStockLength"] == pytest.approx(-screw.STOCK_LENGTH)
    _x, apex = starts["SupplierHeadHeight"]
    assert apex == pytest.approx(screw.CROWN_H)
    assert apex + rows["SupplierHeadHeight"] == pytest.approx(-screw.THREAD_START_DEPTH)


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


def _record(monkeypatch, *, supplied: bool = False) -> list[tuple]:
    """Record the part's build (the supplied screw trimmed to its installed
    cut) or, ``supplied``, the recipe's own catalog build of the screw as bought."""
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

    # The B-rep readbacks of the cut answer what a correct trim leaves.
    def lowest_y_mm(_adapter, label):
        adapter.log("lowest_y_mm", (label,))
        return -screw.CUT_LENGTH

    def end_rim_radius_mm(_adapter, end_y, label):
        adapter.log("end_rim_radius_mm", (end_y, label))
        return screw.THREAD_MAJOR / 2.0 - screw.CUT_END_BREAK_MAX

    # The head body reaches below y = -1 (the neck runs to the thread start),
    # so the shank must be told apart by more than "extends below -1 mm".
    start = -screw.THREAD_START_DEPTH
    boxes = [
        {"name": "Shank", "box_mm": [-2.1, -screw.STOCK_LENGTH, -2.1, 2.1, start, 2.1]},
        {"name": "Head", "box_mm": [-4.0, start, -4.0, 4.0, screw.CROWN_H, 4.0]},
    ]
    monkeypatch.setattr(recipe, "check", logger("check", True))
    monkeypatch.setattr(recipe, "name_last_feature", logger("name_last_feature"))
    monkeypatch.setattr(recipe, "volume_check", volume_check)
    monkeypatch.setattr(recipe, "insert_helix", logger("insert_helix"))
    monkeypatch.setattr(recipe, "thread_sweep_cut", logger("thread_sweep_cut"))
    monkeypatch.setattr(recipe, "lowest_y_mm", lowest_y_mm)
    monkeypatch.setattr(recipe, "end_rim_radius_mm", end_rim_radius_mm)
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
    monkeypatch.setattr(_telemetry, "success", lambda *a, **k: None)

    async def stock_build(_adapter, **kwargs):
        # As build_stock_fastener calls each component's recipe.
        for component in kwargs["components"]:
            if component.parameters is None:
                await component.author(adapter, None)
            else:
                await component.author(adapter, None, **component.parameters)
        return {}

    if supplied:
        asyncio.run(entry.build_91790A199(adapter))
    else:
        monkeypatch.setattr(part, "build_stock_fastener", stock_build)
        asyncio.run(part.build(adapter))
    return adapter.events


def _chains(calls) -> list[tuple]:
    return [c[1][0] for c in calls if c[0] == "add_line_chain"]


def _named(calls) -> list[str]:
    return [c[1][1] for c in calls if c[0] == "name_last_feature"]


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
    # The revolved body is the supplied screw, STOCK_LENGTH from the top of
    # the bevel to its factory tip; the trim comes later as its own feature.
    profile = _chains(calls)[0]
    assert min(y for _x, y in profile) == pytest.approx(-screw.STOCK_LENGTH)
    assert max(x for x, _y in profile) == pytest.approx(screw.HEAD_DIA / 2.0)


def _revolved_volume(length: float, end_chamfer: float) -> float:
    """Crown cap + 82 deg bevel frustum + shank + 45 deg end frustum,
    independent of the recipe's arithmetic."""
    head_r, major_r = screw.HEAD_DIA / 2.0, screw.THREAD_MAJOR / 2.0
    crown = screw.CROWN_H
    bevel = _cone_depth()

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


def test_part_trims_the_supplied_screw_with_one_suppressible_cut(monkeypatch) -> None:
    """The part builds the supplied screw (factory tip, stock volume) and
    then trims it with ONE revolve cut, the last feature, ending it at
    y = -CUT_LENGTH with a 45 deg break of CUT_END_BREAK_MAX; the B-rep
    readbacks of that end and break run after it."""
    calls = _record(monkeypatch)
    major_r = screw.THREAD_MAJOR / 2.0
    brk = screw.CUT_END_BREAK_MAX
    tip = 0.7 * screw.PITCH
    assert _end_of_shank(calls) == pytest.approx(
        [(major_r, -(screw.STOCK_LENGTH - tip)), (major_r - tip, -screw.STOCK_LENGTH)]
    )
    (volume,) = [c for c in calls if c[0] == "volume_check"]
    assert volume[1][1] == pytest.approx(_revolved_volume(screw.STOCK_LENGTH, tip))

    cut = _chains(calls)[-1]
    assert cut[0] == pytest.approx((0.0, -screw.CUT_LENGTH))
    assert cut[1] == pytest.approx((major_r - brk, -screw.CUT_LENGTH))
    (x0, y0), (x1, y1) = cut[1], cut[2]
    assert x1 - x0 == pytest.approx(y1 - y0)  # 45 deg
    assert x1 > major_r  # the break line clears the whole thread
    assert cut[3][0] == pytest.approx(x1)
    assert cut[3][1] < -screw.STOCK_LENGTH  # and everything below the cut
    assert cut[4] == pytest.approx((0.0, cut[3][1]))
    assert _named(calls)[-1] == recipe.CUT_FEATURE
    revolves = [c for c in calls if c[0] == "create_revolve"]
    assert [r[1][0].is_cut for r in revolves] == [False, False, True]
    readbacks = [c[0] for c in calls if c[0] in ("lowest_y_mm", "end_rim_radius_mm")]
    assert readbacks == ["lowest_y_mm", "end_rim_radius_mm"]
    assert calls.index(revolves[-1]) < min(
        i for i, c in enumerate(calls) if c[0] == "lowest_y_mm"
    )
    (rim,) = [c for c in calls if c[0] == "end_rim_radius_mm"]
    assert rim[1][0] == pytest.approx(-screw.CUT_LENGTH)


@pytest.mark.parametrize(
    ("readback", "value"),
    [
        ("lowest_y_mm", -screw.CUT_LENGTH - 0.01),
        ("end_rim_radius_mm", screw.THREAD_MAJOR / 2.0),
    ],
)
def test_cut_readback_refuses_a_wrong_trim(monkeypatch, readback, value) -> None:
    monkeypatch.setattr(recipe, "check", lambda *_a, **_k: True)
    monkeypatch.setattr(recipe, "name_last_feature", lambda *_a, **_k: None)
    monkeypatch.setattr(_sketch, "add_line_chain", _noop_chain)
    monkeypatch.setattr(diag_mcmaster_lib, "no_sketch_inference", _no_inference)
    monkeypatch.setattr(recipe, "lowest_y_mm", lambda *_a: -screw.CUT_LENGTH)
    monkeypatch.setattr(
        recipe,
        "end_rim_radius_mm",
        lambda *_a: screw.THREAD_MAJOR / 2.0 - screw.CUT_END_BREAK_MAX,
    )
    monkeypatch.setattr(recipe, readback, lambda *_a: value)
    with pytest.raises(RuntimeError):
        asyncio.run(
            recipe.cut_to_fit(
                _Recorder(), screw.SKU, screw.CUT_LENGTH, screw.CUT_END_BREAK_MAX
            )
        )


async def _noop_chain(_adapter, points, **_kwargs):
    return []


@contextlib.contextmanager
def _no_inference(_adapter):
    yield


def test_catalog_build_is_the_supplied_screw(monkeypatch) -> None:
    """Without a cut the recipe builds the screw as bought: STOCK_LENGTH with
    the family's 45 deg x 0.7P factory tip, and no trim."""
    calls = _record(monkeypatch, supplied=True)
    major_r = screw.THREAD_MAJOR / 2.0
    tip = 0.7 * screw.PITCH
    assert _end_of_shank(calls) == pytest.approx(
        [(major_r, -(screw.STOCK_LENGTH - tip)), (major_r - tip, -screw.STOCK_LENGTH)]
    )
    (volume,) = [c for c in calls if c[0] == "volume_check"]
    assert volume[1][1] == pytest.approx(_revolved_volume(screw.STOCK_LENGTH, tip))
    assert recipe.CUT_FEATURE not in _named(calls)
    assert not [c for c in calls if c[0] in ("lowest_y_mm", "end_rim_radius_mm")]


@pytest.mark.parametrize(
    ("cut_length", "cut_end_break"),
    [
        (screw.CUT_LENGTH, None),  # half a cut
        (None, screw.CUT_END_BREAK_MAX),
        (screw.STOCK_LENGTH, screw.CUT_END_BREAK_MAX),  # leaves the factory tip
        (screw.CUT_LENGTH, 0.0),  # an unbroken cut end
        (_cone_depth(), screw.CUT_END_BREAK_MAX),  # no shank under the bevel
        # into the supplier's thread start under the neck
        (screw.THREAD_START_DEPTH + screw.CUT_END_BREAK_MAX, screw.CUT_END_BREAK_MAX),
    ],
)
def test_recipe_refuses_a_cut_it_cannot_draw(cut_length, cut_end_break) -> None:
    with pytest.raises(ValueError):
        asyncio.run(
            entry.build_91790A199(
                None, cut_length=cut_length, cut_end_break=cut_end_break
            )
        )


def test_head_seats_in_the_plate_countersink_without_interference(monkeypatch) -> None:
    """Through the plate's thickness the modelled screw never leaves the
    countersink cone or the clearance hole under it, and its bevel bears on
    the countersink (not only on the rim).  The supplier's underhead fillet
    is concave: it ADDS metal outside the sharp cone/neck corner, so it is
    bounded by its own torus arc, which starts below the countersink and
    stays inside the clearance hole."""
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
    assert plate.CSK_DEPTH < _cone_depth()
    assert screw.THREAD_MAJOR < plate.SCREW_HOLE_DIA
    # The concave fillet adds metal between its tangents, outside the sharp
    # profile sampled above, so bound the actual torus section: centre at
    # r = major + R, depth = corner + R tan(deflection / 2).
    deflection = math.radians(screw.HEAD_ANGLE_DEG / 2.0)
    fillet_r = screw.UNDER_HEAD_FILLET_R
    tangent = fillet_r * math.tan(deflection / 2.0)
    centre_r = screw.THREAD_MAJOR / 2.0 + fillet_r
    centre_depth = _cone_depth() + tangent
    cone_tangent_depth = _cone_depth() - tangent * math.cos(deflection)
    cone_tangent_r = screw.THREAD_MAJOR / 2.0 + tangent * math.sin(deflection)
    assert centre_r - math.sqrt(
        fillet_r**2 - (cone_tangent_depth - centre_depth) ** 2
    ) == pytest.approx(cone_tangent_r)
    # The bearing cone is whole above the fillet ...
    assert plate.CSK_DEPTH < cone_tangent_depth
    for i in range(steps + 1):
        depth = cone_tangent_depth + (centre_depth - cone_tangent_depth) * i / steps
        arc_r = centre_r - math.sqrt(max(fillet_r**2 - (depth - centre_depth) ** 2, 0.0))
        assert arc_r >= head_radius(depth) - 1e-9, depth  # it does add metal
        assert arc_r < envelope(depth), depth  # ... and clears the hole
    assert cone_tangent_r < envelope(cone_tangent_depth)
    assert screw.UNDER_HEAD_FILLET_R < screw.UNDER_HEAD_FILLET_RADIUS_MAX_MM
    # The neck and thread start sit inside the plate, above the arm.
    assert screw.THREAD_START_DEPTH < plate.THICKNESS_OVER_ARM


def test_thread_starts_at_the_supplier_station(monkeypatch) -> None:
    calls = _record(monkeypatch)
    corner = -_cone_depth()
    start = -(screw.HEAD_H - screw.CROWN_H)
    # The bevel cone runs to its theoretical corner on the thread major ...
    profile = _chains(calls)[0]
    major_r = screw.THREAD_MAJOR / 2.0
    top_of_shank = max(y for x, y in profile if x == pytest.approx(major_r))
    assert top_of_shank == pytest.approx(corner)
    # ... the body is split at the supplier's thread start, H = .100 in down,
    # so the scoped thread starts there, under the full-major neck.
    (plane,) = [c for c in calls if c[0] == "offset_plane"]
    plane_name, offset = plane[1][1:3]
    assert offset == pytest.approx(start)
    assert ("split_at_plane", (plane_name, "HeadSplit"), {}) in calls
    (sweep,) = [c for c in calls if c[0] == "thread_sweep_cut"]
    assert sweep[1][3:] == ("Shank", "ThreadGroove")
    # The helix, seeded at the top of the bevel, runs past the factory tip.
    (helix,) = [c for c in calls if c[0] == "insert_helix"]
    pitch, revs = helix[1][1:3]
    assert pitch == pytest.approx(screw.PITCH)
    assert revs * pitch >= screw.STOCK_LENGTH
    # One fill restores the neck from the corner, the annular step to .077 in
    # at the thread start, and the 60 deg (from the axis) cone to the root.
    fill = _chains(calls)[3]
    root_r = major_r - 0.75 * screw.PITCH * math.sqrt(3.0) / 2.0
    step_r = 0.077 * IN
    cone_end = start - (step_r - root_r) / math.tan(math.radians(60.0))
    assert [v for point in fill for v in point] == pytest.approx(
        [
            0.0, corner,
            major_r, corner,
            major_r, start,
            step_r, start,
            root_r, cone_end,
            0.0, cone_end,
        ]
    )
    # The cone-to-neck fillet is the STEP's radius, on the corner edge.
    (fillet,) = [c for c in calls if c[0] == "add_fillet"]
    radius, edges = fillet[1]
    assert radius == pytest.approx(_STEP_FILLET_MINOR_R, abs=1e-9)
    assert edges == [[pytest.approx(major_r), pytest.approx(corner), 0.0]]
    def named_at(name: str) -> int:
        (index,) = [
            i for i, c in enumerate(calls)
            if c[0] == "name_last_feature" and c[1][1] == name
        ]
        return index

    groove = calls.index(sweep)
    assert groove < named_at("ThreadStartFill") < named_at("UnderheadFillet")
    assert named_at("UnderheadFillet") < named_at(recipe.CUT_FEATURE)


def test_driver_slot_stops_inside_the_oval_head(monkeypatch) -> None:
    calls = _record(monkeypatch)
    slot = _chains(calls)[1]
    slot_floor = min(y for _x, y in slot)
    assert -_cone_depth() < slot_floor < screw.CROWN_H
    assert max(y for _x, y in slot) > screw.CROWN_H  # open through the crown


def test_stock_build_uses_its_registered_recipe_head_up_on_the_origin(
    monkeypatch,
) -> None:
    metadata = discovered_recipes()[screw.SKU]
    assert metadata.module == entry.__name__
    assert metadata.callable_name == entry.build_91790A199.__name__
    assert metadata.threaded
    assert FASTENERS[part.PART_NAME] is part.SPEC
    assert part.SPEC.skus == (screw.SKU,)
    assert part.MATERIAL == "AISI 304"
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-VN-040"
    assert int(row["quantity"]) == 2
    assert row["supplier_skus"] == [screw.SKU]
    assert row["stock_name"] == part.SPEC.stock_name
    assert screw.SKU in row["material_specification"]
    assert f"{screw.STOCK_LENGTH:.2f}" in row["material_specification"]

    seen: dict = {}

    async def fake_build(adapter, **kwargs):
        seen.update(kwargs)
        return {}

    monkeypatch.setattr(part, "build_stock_fastener", fake_build)
    asyncio.run(part.build(None))
    (component,) = seen["components"]
    assert component.sku == screw.SKU
    assert component.author is entry.build_91790A199
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
    assert seen == [(screw.SKU, entry.build_91790A199)]


def test_no_vendor_model_of_the_new_hardware_is_tracked() -> None:
    root = Path(__file__).resolve().parents[2]
    assert not list(root.glob(f"cad/references/**/{screw.SKU}*.SLDPRT"))


# A size on the sheet's registry-printed fields: a thread (#8-32), a fraction,
# a length with units, or an "x" between numbers.  The 18-8 grade is not one.
_SIZE = re.compile(r"#\d|\d+/\d+|\d\s*(?:mm|in\b|\")|\d\s*[xX]\s*\d|°")


def test_sheet_states_the_cut_and_no_size_in_the_registry_names() -> None:
    """The ordinary purchased reference sheet carries the actual stock identity
    and off-mechanism cut instruction, not a commodity receiving procedure."""
    row = _config.parts(part.PART_NAME)
    for field in ("title", "stock_name", "supplier", "finish", "material"):
        assert not _SIZE.search(str(row[field])), (field, row[field])
    assert row["installation_notes"] == screw.PURCHASED_STOCK_NOTE
    lines = row["installation_notes"].splitlines()
    assert len(lines) <= 4
    assert all(len(line) <= 70 for line in lines), lines
    assert "1 IN" in screw.PURCHASED_STOCK_NOTE
    assert f"{screw.STOCK_LENGTH:.2f}" in screw.PURCHASED_STOCK_NOTE
    assert "CUT LENGTH AT ASSEMBLY" in screw.PURCHASED_STOCK_NOTE
    flat = " ".join(screw.PURCHASED_STOCK_NOTE.splitlines())
    proud = joints.PLATE_SCREW_CUT_PROUD_MAX
    assert f"FLUSH OR PROUD {proud:g} MAX" in flat
    assert f"CUT-END BREAK {screw.CUT_END_BREAK_TEXT}" in flat
    assert "AT ASSEMBLY (MHA-PD-000, BEFORE THE GUIDE-LOCK SWEEP)" in flat
    # The trim limit names the face it is measured from (machinist review).
    assert f"PROUD {proud:g} MAX OF THE MHA-PD-018 ARM FRONT FACE" in flat


def test_drawing_is_the_purchased_reference_sheet() -> None:
    spec = DRAWINGS_BY_NAME["vn_transgear_arm_plate_screw"]
    assert drawing.SPEC is spec
    assert spec.artifact_stem == part.PART_NAME
    assert spec.script == Path(drawing.__file__).resolve()


_INSTALLED = "Default"


class _Configuration:
    """IConfiguration: its name and the configuration it derives from."""

    def __init__(self, name: str, parent: _Configuration | None) -> None:
        self.Name = name
        self.parent = parent

    def GetParent(self) -> _Configuration | None:
        return self.parent


class _ConfiguredPart:
    """Minimal native state behind ``_supplier_stock``/``_save_installed``:
    configurations with their parents, the active one, and where the trim
    feature is suppressed.  The solid's lowest point follows that state.
    As SolidWorks: AddConfiguration2 (Options = 0) activates the new
    configuration, and ShowConfiguration2 of the active one returns False.
    ``misparent`` makes the created configuration report the wrong parent."""

    def __init__(self, *, misparent: bool = False) -> None:
        self.parents: dict[str, str | None] = {_INSTALLED: None}
        self.active = _INSTALLED
        self.trim_suppressed: set[str] = set()
        self.misparent = misparent
        self.ConfigurationManager = self

    def AddConfiguration2(self, name, _comment, _alt, options, parent, _desc, _rebuild):
        if name in self.parents or parent not in self.parents:
            return None
        self.parents[name] = parent
        if not options & 128:  # swConfigOption_DontActivate
            self.active = name
        reported = _Configuration("Elsewhere" if self.misparent else parent, None)
        return _Configuration(name, reported)

    def ShowConfiguration2(self, name) -> bool:
        if name not in self.parents or name == self.active:
            return False
        self.active = name
        return True

    def GetConfigurationNames(self) -> tuple[str, ...]:
        return tuple(self.parents)

    # The trim feature, IFeature: (action, configuration option, names).
    def SetSuppression2(self, action, option, _names) -> bool:
        assert (action, option) == (0, 1)  # suppress, this configuration
        self.trim_suppressed.add(self.active)
        return True

    def IsSuppressed2(self, option, _names) -> tuple[bool, ...]:
        assert option == 1
        return (self.active in self.trim_suppressed,)

    def lowest_y(self) -> float:
        stock = self.active in self.trim_suppressed
        return -(screw.STOCK_LENGTH if stock else screw.CUT_LENGTH)


def _configured(monkeypatch, *, stock_end=None, stock_rebuild_fails=False, misparent=False):
    """A part whose COM boundary is ``_ConfiguredPart``; ``stock_end`` forces
    the stock's span readback, ``stock_rebuild_fails`` its rebuild,
    ``misparent`` the created configuration's reported parent."""
    model = _ConfiguredPart(misparent=misparent)
    adapter = types.SimpleNamespace(currentModel=model)

    async def open_model(_path) -> AdapterResult[None]:
        return AdapterResult(status=AdapterResultStatus.SUCCESS)

    async def force_rebuild(_adapter) -> None:
        if stock_rebuild_fails and model.active == screw.SUPPLIER_STOCK_CONFIGURATION:
            raise RuntimeError("rebuild failed")

    async def reference_sketch(*_args, **_kwargs) -> None:
        return None

    def lowest_y_mm(_adapter, _label) -> float:
        if stock_end is not None and model.active == screw.SUPPLIER_STOCK_CONFIGURATION:
            return stock_end
        return model.lowest_y()

    def feature(_adapter, name):
        assert name == recipe.CUT_FEATURE
        return model

    adapter.open_model = open_model
    monkeypatch.setattr(part, "_early_bound", lambda obj, _iface: obj)
    monkeypatch.setattr(part, "null_variant", lambda: None)
    monkeypatch.setattr(part, "active_configuration_name", lambda _a, m: m.active)
    monkeypatch.setattr(part, "_feature_by_name", feature)
    monkeypatch.setattr(part, "force_rebuild", force_rebuild)
    monkeypatch.setattr(part, "lowest_y_mm", lowest_y_mm)
    monkeypatch.setattr(part, "add_supplier_reference_sketch", reference_sketch)
    monkeypatch.setattr(
        part, "require_material_in_every_configuration", lambda *_a, **_k: None
    )
    return adapter, model


def test_supplier_stock_trims_only_its_own_configuration(monkeypatch) -> None:
    """SupplierStock is derived from the installed configuration with the
    trim suppressed there only; the installed one is active again, still
    trimmed to CUT_LENGTH."""
    adapter, model = _configured(monkeypatch)
    asyncio.run(part._supplier_stock(adapter))
    stock = screw.SUPPLIER_STOCK_CONFIGURATION
    assert model.parents == {_INSTALLED: None, stock: _INSTALLED}
    assert model.trim_suppressed == {stock}
    assert model.active == _INSTALLED
    assert model.lowest_y() == pytest.approx(-screw.CUT_LENGTH)
    model.active = stock
    assert model.lowest_y() == pytest.approx(-screw.STOCK_LENGTH)


@pytest.mark.parametrize(
    "failure",
    [
        {"stock_end": -screw.CUT_LENGTH},  # the stock span is not the stock
        {"stock_rebuild_fails": True},
        {"misparent": True},  # created, then refused before any suppression
    ],
)
def test_supplier_stock_failure_restores_the_installed_screw(monkeypatch, failure) -> None:
    """A failure inside SupplierStock still returns to the installed
    configuration with its trim unsuppressed."""
    adapter, model = _configured(monkeypatch, **failure)
    with pytest.raises(RuntimeError):
        asyncio.run(part._supplier_stock(adapter))
    assert model.active == _INSTALLED
    assert _INSTALLED not in model.trim_suppressed
    assert model.lowest_y() == pytest.approx(-screw.CUT_LENGTH)


def _save_boundary(monkeypatch, model) -> list[str]:
    """Persistence boundary of ``_save_installed``: saving is recorded, and
    deriving adds ``P Simplified`` for each selected parent (every
    configuration when none are given, as the shared helper does)."""
    saved: list[str] = []

    async def save(_adapter, part_name):
        saved.append(part_name)
        return {"part": f"{part_name}.SLDPRT"}

    async def derive(_adapter, _part_name, _features, _path, parents=None):
        chosen = parents if parents is not None else [
            name for name in model.GetConfigurationNames() if not is_simplified(name)
        ]
        for parent in chosen:
            model.parents[simplified_name(parent)] = parent

    monkeypatch.setattr(part, "save_part_and_images", save)
    monkeypatch.setattr(part, "derive_simplified_on_saved_part", derive)
    monkeypatch.setattr(part, "assert_saved_configurations_regenerate", lambda *_a: None)
    monkeypatch.setattr(part, "assert_simplified_configurations", lambda *_a, **_k: None)
    return saved


def test_save_simplifies_the_installed_screw_not_the_stock(monkeypatch) -> None:
    adapter, model = _configured(monkeypatch)
    asyncio.run(part._supplier_stock(adapter))
    saved = _save_boundary(monkeypatch, model)
    asyncio.run(part._save_installed(adapter, part.PART_NAME, ("ThreadGroove",)))
    stock = screw.SUPPLIER_STOCK_CONFIGURATION
    assert saved == [part.PART_NAME]
    assert model.parents == {
        _INSTALLED: None,
        stock: _INSTALLED,
        simplified_name(_INSTALLED): _INSTALLED,
    }
    assert simplified_name(stock) not in model.parents


def test_save_refuses_with_the_supplier_stock_active(monkeypatch) -> None:
    adapter, model = _configured(monkeypatch)
    asyncio.run(part._supplier_stock(adapter))
    saved = _save_boundary(monkeypatch, model)
    model.active = screw.SUPPLIER_STOCK_CONFIGURATION
    with pytest.raises(RuntimeError):
        asyncio.run(part._save_installed(adapter, part.PART_NAME, ("ThreadGroove",)))
    assert saved == []
    assert not any(is_simplified(name) for name in model.parents)
