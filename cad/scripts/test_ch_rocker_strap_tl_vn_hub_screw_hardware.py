"""Offline part, recipe and schedule contracts for ch-rocker-strap-tl-vn-hub-screw.

MHA-CH-13-TL-VN-51 is tier-1 hardware (owner ruling 2026-11-23: #10-32 x 5/8
button head, McMaster 91255A267): a HARDWARE.md row, never a drawing. These
checks pin the part the fixture assembly builds.
"""

from __future__ import annotations

import ast
import contextlib
import math
import tomllib
from pathlib import Path

import pytest

import _config
import _mcmaster_91255a267 as screw
import build_ch_rocker_strap_tl_vn_hub_screw as part
import hardware_schedule
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _test_stock_recipes import discovered_recipes
from diagnostics import diag_build_91255A267 as recipe

STEM = "ch-rocker-strap-tl-vn-hub-screw"
NUMBER = "MHA-CH-13-TL-VN-51"
STOCK_NAME = "Black-Oxide Button Head Hex-Drive Screw"
IN = 25.4
SCRIPTS = Path(__file__).resolve().parent
PLAN = SCRIPTS.parents[1] / "cad" / "process" / "ch_rocker_strap" / "plan.toml"


def test_catalogue_row_is_the_registered_mcmaster_part() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert stock.skus == tuple(row["supplier_skus"]) == (screw.SKU,) == ("91255A267",)
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert stock.stock_name == row["stock_name"] == STOCK_NAME
    assert stock.material == row["material"] == part.MATERIAL == "Alloy Steel"
    assert row["finish"] == "black oxide"
    assert "ASME B18.3" in row["material_specification"]
    assert "10-32" in row["material_specification"]
    assert row["number"] == NUMBER
    assert row["process"] == "purchased"
    assert int(row["quantity"]) == 1
    metadata = discovered_recipes()[screw.SKU]
    assert metadata.module == recipe.__name__
    assert getattr(recipe, metadata.callable_name) is recipe.build_91255A267
    assert metadata.threaded is False
    for other, entry in FASTENERS.items():
        if other != STEM:
            assert screw.SKU not in entry.skus, other


def test_provider_carries_the_live_catalogue_facts() -> None:
    """McMaster 91255A267 product page, read live 2026-11-23; the head's
    sizes are ASME B18.3's maxima for a No. 10 button head, the major's
    minimum ASME B1.1's for class 3A."""
    assert screw.THREAD == "#10-32"
    assert screw.HEAD_DIA == pytest.approx(0.361 * IN)
    assert screw.HEAD_DIA_MIN == pytest.approx(0.347 * IN)
    assert screw.HEAD_HEIGHT == pytest.approx(0.101 * IN)
    assert screw.LENGTH == pytest.approx(0.625 * IN)
    assert screw.MAJOR_DIA == pytest.approx(0.190 * IN)
    assert screw.MAJOR_DIA_MIN == pytest.approx(0.184 * IN)
    assert screw.SOCKET_AF == pytest.approx(1.0 / 8.0 * IN)
    # The vendor model's dome: its top flat (FreeCAD: the sphere R 5.26903
    # cut at the head height, r 2.2225) follows from the sphere and the
    # catalogue head height.
    assert screw.TOP_FLAT_R == pytest.approx(2.2225, abs=1e-3)
    # The model omits the thread, so it may only exceed the vendor solid.
    assert 0.0 < screw.screw_volume() - screw.STEP_VOLUME < 0.2 * screw.STEP_VOLUME


def test_tier_one_schedule_row_and_no_sheet() -> None:
    row = hardware_schedule.SCHEDULE[STEM]
    assert row["standard"] == "ASME B18.3"
    assert row["designation"].startswith("#10-32 UNF-3A x 5/8")
    assert hardware_schedule.envelope_mm(row["envelope"]["head Ø"]) == pytest.approx(
        screw.HEAD_DIA
    )
    assert hardware_schedule.envelope_mm(row["envelope"]["head H"]) == pytest.approx(
        screw.HEAD_HEIGHT
    )
    assert all(
        spec.part != STEM.replace("-", "_") for spec in DRAWINGS_BY_NAME.values()
    )
    assert not (SCRIPTS / "draw_ch_rocker_strap_tl_vn_hub_screw.py").exists()


def test_screw_head_fits_the_plans_hold_down_stack() -> None:
    """cad/process/ch_rocker_strap/plan.toml's hold-down stack keep-out
    covers this head, .361 dia, .101 high over the washer's .065 maximum."""
    parameters = tomllib.loads(PLAN.read_text(encoding="utf-8"))["parameters"]
    assert (
        0.065 * IN + screw.HEAD_HEIGHT <= parameters["bushing_stack_height_mm"] + 1e-9
    )
    assert screw.HEAD_DIA < parameters["bushing_flange_dia_mm"]


class _Recorder:
    def __init__(self) -> None:
        self.events: list[tuple] = []

    def create_sketch(self, *args):
        self.events.append(("create_sketch", args))
        return "ok"

    def exit_sketch(self):
        self.events.append(("exit_sketch", ()))
        return "ok"

    def add_centerline(self, *args):
        self.events.append(("centerline", args))
        return "ok"

    def add_arc(self, *args):
        self.events.append(("arc", args))
        return "ok"

    def create_revolve(self, params):
        self.events.append(("revolve", (params,)))
        return "ok"

    def create_cut_extrude(self, params):
        self.events.append(("cut", (params,)))
        return "ok"


def _record(monkeypatch) -> list[tuple]:
    adapter = _Recorder()

    @contextlib.contextmanager
    def no_inference(_adapter):
        yield

    def add_line_chain(_adapter, points, close=True):
        adapter.events.append(("lines", (tuple(points), close)))
        return [f"L{i}" for i in range(len(points))]

    monkeypatch.setattr(recipe, "check", lambda *a, **k: True)
    monkeypatch.setattr(
        recipe,
        "name_last_feature",
        lambda _a, name: adapter.events.append(("name", (name,))),
    )
    monkeypatch.setattr(
        recipe,
        "volume_check",
        lambda _a, _l, expected, _t: adapter.events.append(("volume", (expected,))),
    )
    monkeypatch.setattr(recipe, "no_sketch_inference", no_inference)
    monkeypatch.setattr(recipe, "add_line_chain", add_line_chain)
    monkeypatch.setattr(
        recipe,
        "offset_plane",
        lambda _a, name, y: adapter.events.append(("plane", (name, y))),
    )
    recipe.build_91255A267(adapter)
    return adapter.events


def test_recipe_revolves_the_dome_head_and_cuts_the_socket(monkeypatch) -> None:
    events = _record(monkeypatch)
    names = [e[1][0] for e in events if e[0] == "name"]
    assert names == ["ScrewProfile", "ScrewBody", "SocketProfile", "HexSocket"]
    (axis,) = [e[1] for e in events if e[0] == "centerline"]
    assert axis == (0.0, screw.HEAD_HEIGHT, 0.0, -screw.LENGTH)
    chain, hexagon = [e[1] for e in events if e[0] == "lines"]
    points, close = chain
    assert close is False
    (arc,) = [e[1] for e in events if e[0] == "arc"]
    cx, cy, sx, sy, ex, ey = arc
    # The arc closes the open chain, counter-clockwise from the dome's foot.
    assert (sx, sy) == points[0] and (ex, ey) == points[-1]
    assert (cx, cy) == (0.0, screw.DOME_CENTER_Y)
    assert math.atan2(ey - cy, ex - cx) > math.atan2(sy - cy, sx - cx)
    for x, y in ((sx, sy), (ex, ey)):
        assert math.hypot(x - cx, y - cy) == pytest.approx(screw.DOME_R)
    assert max(x for x, _ in points) == pytest.approx(screw.HEAD_DIA / 2.0)
    assert min(y for _, y in points) == pytest.approx(-screw.LENGTH)
    assert (screw.MAJOR_DIA / 2.0, 0.0) in points
    hex_points, hex_close = hexagon
    assert hex_close is True and len(hex_points) == 6
    xs = [x for x, _ in hex_points]
    assert max(xs) - min(xs) == pytest.approx(screw.SOCKET_AF)
    assert ("plane", (recipe.HEAD_TOP_PLANE, screw.HEAD_HEIGHT)) in events
    assert ("create_sketch", (recipe.HEAD_TOP_PLANE,)) in events
    (revolve,) = [e[1][0] for e in events if e[0] == "revolve"]
    assert revolve.angle == 360.0 and not revolve.is_cut
    (cut,) = [e[1][0] for e in events if e[0] == "cut"]
    assert cut.depth == pytest.approx(2.0 * screw.SOCKET_DEPTH) and cut.both_directions
    volumes = [e[1][0] for e in events if e[0] == "volume"]
    assert volumes == pytest.approx([screw.revolved_volume(), screw.screw_volume()])


def test_stock_build_turns_the_recipe_axis_onto_part_z(monkeypatch) -> None:
    seen: dict = {}
    monkeypatch.setattr(part, "build_stock_fastener", lambda _a, **kw: seen.update(kw))
    part.build(None)
    (component,) = seen["components"]
    assert component.sku == screw.SKU
    assert component.author is recipe.build_91255A267
    assert component.transform.rotation_radians == pytest.approx(
        (math.pi / 2.0, 0.0, 0.0)
    )
    assert component.transform.translation_mm == (0.0, 0.0, 0.0)
    assert seen["material"] == part.SPEC.material
    assert seen["screw_axis_planes"] == ("Top Plane", "Right Plane")


def test_no_vendor_model_is_tracked() -> None:
    root = SCRIPTS.parents[1]
    assert not list(root.glob(f"cad/references/**/{screw.SKU}*.SLDPRT"))
    assert not list(root.glob(f"cad/references/**/{screw.SKU}*.STEP"))


@pytest.mark.parametrize(
    "module",
    ["diagnostics/diag_build_91255A267.py", "build_ch_rocker_strap_tl_vn_hub_screw.py"],
)
def test_every_direct_adapter_call_exists_and_binds(module: str) -> None:
    from test_pd_transgear_adapter_contract import (
        _adapter_calls,
        _adapter_methods,
        _missing,
        _signature,
    )

    tree = ast.parse((SCRIPTS / module).read_text(encoding="utf-8"))
    assert not _missing(tree), sorted(_missing(tree))
    for call in _adapter_calls(tree):
        _, method = _adapter_methods()[call.func.attr]
        assert not any(isinstance(arg, ast.Starred) for arg in call.args), call.lineno
        _signature(method).bind(
            call.func.value,
            *call.args,
            **{keyword.arg: keyword.value for keyword in call.keywords},
        )
