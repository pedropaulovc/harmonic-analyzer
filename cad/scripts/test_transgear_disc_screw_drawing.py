"""Offline contracts for the MHA-161 transgear disc screws."""

from __future__ import annotations

import asyncio
import contextlib
import json
import math
import re
from pathlib import Path

import pytest

import _config
import _telemetry
import build_transgear_disc_screw as part
import draw_transgear_disc_screw as drawing
import transgear_disc_screw_spec as screw
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _stock_fastener import STOCK_RECIPES
from diagnostics import diag_build_91794A055 as entry
from diagnostics.diag_mcmaster_fillister import FILLISTER_SIZES

IN = 25.4


def test_spec_is_the_catalogue_screw() -> None:
    """91794A055 per mcmaster.com (2026-09-30): #0-80 x 1/4 under the head,
    fillister head Ø0.096 x 0.055, fully threaded."""
    assert screw.SKU == "91794A055"
    assert screw.THREAD == "#0-80"
    assert screw.SHANK_DIA == pytest.approx(0.060 * IN)
    assert screw.PITCH == pytest.approx(IN / 80.0)
    assert screw.SHANK_LEN == pytest.approx(0.25 * IN)
    assert screw.HEAD_DIA == pytest.approx(0.096 * IN)
    assert screw.HEAD_H == pytest.approx(0.055 * IN)
    # The hub spec reads the same screw off the fillister size table.
    assert FILLISTER_SIZES[screw.SKU] == pytest.approx(
        (screw.SHANK_DIA, screw.SHANK_LEN, screw.HEAD_H, screw.HEAD_DIA, screw.PITCH)
    )


_DUMP = (
    Path(__file__).resolve().parents[1]
    / "out"
    / "reports"
    / f"mcmaster-{screw.SKU}-dump.json"
)


def _truth() -> dict:
    if not _DUMP.exists():
        pytest.skip(f"no local vendor harvest at {_DUMP}")
    return json.loads(_DUMP.read_text(encoding="utf-8"))


def _feature(truth: dict, name: str) -> dict:
    (feature,) = [f for f in truth["features"] if f["name"] == name]
    return feature


def test_spec_laws_are_the_vendor_model() -> None:
    """Every head, slot, fillet, chamfer, thread and runout law reproduces the
    harvest's own number (the dump wins over the 90280A family's fractions)."""
    truth = _truth()
    dims = {
        d["full_name"].split("@")[0] + "@" + d["owner"]: d.get(
            "value_mm", d.get("value_deg")
        )
        for f in truth["features"]
        for d in f["dimensions"]
    }
    assert dims["Head Diameter@Sketch1"] == pytest.approx(screw.HEAD_DIA)
    assert dims["Head Height@Sketch1"] == pytest.approx(screw.HEAD_H)
    assert dims["Length@Sketch1"] == pytest.approx(screw.SHANK_LEN)
    assert dims["Screw Size Decimal Equivalent@Sketch1"] == pytest.approx(
        screw.SHANK_DIA
    )
    assert dims["Pitch@Sketch1"] == pytest.approx(screw.PITCH)
    assert dims["Approx Head Edge Flat@Sketch1"] == pytest.approx(screw.HEAD_BAND)
    assert dims["D5@Sketch2"] == pytest.approx(screw.HEAD_SIDE_DRAFT_DEG)
    assert dims["D3@Sketch2"] == pytest.approx(screw.NECK_DIA / 2.0)
    assert dims["D4@Sketch2"] == pytest.approx(screw.NECK_LEN)
    assert dims["D1@Sketch2"] == pytest.approx(screw.TIP_CHAMFER)
    assert dims["D2@Sketch2"] == pytest.approx(45.0)
    assert dims["D1@Sketch9"] == pytest.approx(screw.SLOT_WIDTH)
    assert dims["D1@Fillet1"] == pytest.approx(screw.SLOT_FILLET_R, abs=1e-6)
    assert dims["D1@Fillet2"] == pytest.approx(screw.HEAD_FILLET_R)
    assert dims["D3@Helix/Spiral1"] == pytest.approx(screw.HELIX_HEIGHT)
    assert dims["D3@Boss-Extrude1"] == pytest.approx(screw.RUNOUT_DRAFT_DEG)

    profile = {s["name"]: s for s in _feature(truth, "Sketch2")["sketch"]["segments"]}
    assert profile["Arc4"]["radius_mm"] == pytest.approx(screw.DOME_R, abs=1e-5)
    # Line2: the drafted side, rim radius to the under-head radius.
    side = profile["Line2"]
    assert side["start"]["y"] == pytest.approx(screw.HEAD_DIA / 2.0)
    assert side["end"]["y"] == pytest.approx(screw.UNDER_HEAD_DIA / 2.0, abs=1e-5)

    slot = [
        s
        for s in _feature(truth, "Sketch9")["sketch"]["segments"]
        if not s["construction"]
    ]
    xs = [p["x"] for s in slot for p in (s["start"], s["end"])]
    assert max(xs) - min(xs) == pytest.approx(screw.SLOT_DEPTH, abs=1e-5)

    cutter = _feature(truth, "Sketch7")["sketch"]["segments"]
    ys = sorted({round(p["y"], 6) for s in cutter for p in (s["start"], s["end"])})
    assert ys == pytest.approx([screw.ROOT_DIA / 2.0, screw.SHANK_DIA / 2.0], abs=1e-5)
    (top,) = [s for s in cutter if s["start"]["y"] == s["end"]["y"] == ys[1]]
    (root,) = [s for s in cutter if s["start"]["y"] == s["end"]["y"] == ys[0]]
    assert top["length_mm"] == pytest.approx(screw.CUTTER_TOP_W, abs=1e-5)
    assert root["length_mm"] == pytest.approx(screw.ROOT_FLAT, abs=1e-5)

    helix = _feature(truth, "Helix/Spiral1")["data"]
    assert helix["revolutions"] == pytest.approx(screw.HELIX_REVS)
    assert helix["pitch_mm"] == pytest.approx(screw.PITCH)

    (runout,) = [
        s
        for s in _feature(truth, "Sketch8")["sketch"]["segments"]
        if s["kind"] == "arc"
    ]
    assert runout["radius_mm"] == pytest.approx(screw.RUNOUT_DIA / 2.0)


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


def _record(monkeypatch, **cut) -> tuple[_Recorder, list[tuple]]:
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

    monkeypatch.setattr(entry, "check", logger("check", True))
    monkeypatch.setattr(entry, "name_last_feature", logger("name_last_feature"))
    monkeypatch.setattr(entry, "volume_check", volume_check)
    monkeypatch.setattr(entry, "insert_helix", logger("insert_helix"))
    monkeypatch.setattr(entry, "thread_sweep_cut", logger("thread_sweep_cut"))
    monkeypatch.setattr(entry, "offset_plane", logger("offset_plane"))
    monkeypatch.setattr(entry, "add_line_chain", add_line_chain)
    monkeypatch.setattr(entry, "no_sketch_inference", no_inference)
    monkeypatch.setattr(_telemetry, "info", lambda *a, **k: None)
    asyncio.run(entry.build_91794A055(adapter, **cut))
    return adapter, adapter.events


def _chains(calls) -> list[tuple]:
    return [c[1][0] for c in calls if c[0] == "add_line_chain"]


def test_recipe_builds_the_vendor_head_on_the_under_head_face(monkeypatch) -> None:
    _adapter, calls = _record(monkeypatch)
    (arc,) = [c for c in calls if c[0] == "sketch.Create3PointArc"]
    apex, rim, mid = arc[1][0:3], arc[1][3:6], arc[1][6:9]
    assert apex[:2] == pytest.approx((0.0, screw.HEAD_H / 1000.0))
    assert rim[:2] == pytest.approx((screw.HEAD_DIA / 2000.0, screw.HEAD_BAND / 1000.0))
    # The mid point lies on the vendor's dome sphere, centred on the axis.
    centre_y = (screw.HEAD_H - screw.DOME_R) / 1000.0
    assert math.hypot(mid[0], mid[1] - centre_y) == pytest.approx(screw.DOME_R / 1000.0)

    profile, slot, cutter, runout = _chains(calls)
    # Drafted side from the rim down to the bearing face, then the neck, the
    # major and a flat tip one full length under the head.
    assert [v for point in profile[0:3] for v in point] == pytest.approx(
        [
            screw.HEAD_DIA / 2.0,
            screw.HEAD_BAND,
            screw.UNDER_HEAD_DIA / 2.0,
            0.0,
            screw.NECK_DIA / 2.0,
            0.0,
        ]
    )
    assert min(y for _x, y in profile) == pytest.approx(-screw.SHANK_LEN)
    # The slot is the vendor width and stops 1.5 dome heights under the apex.
    assert max(x for x, _y in slot) - min(x for x, _y in slot) == pytest.approx(
        screw.SLOT_WIDTH
    )
    assert min(y for _x, y in slot) == pytest.approx(screw.HEAD_H - screw.SLOT_DEPTH)
    (revolve_check,) = [c for c in calls if c[0] == "volume_check"]
    assert revolve_check[1][1] == pytest.approx(entry.revolved_volume())

    fillets = [c[1] for c in calls if c[0] == "add_fillet"]
    assert [f[0] for f in fillets] == pytest.approx(
        [screw.SLOT_FILLET_R, screw.HEAD_FILLET_R]
    )
    assert len(fillets[0][1]) == 2 and len(fillets[1][1]) == 3


def test_recipe_threads_tip_seeded_one_pitch_into_the_head(monkeypatch) -> None:
    _adapter, calls = _record(monkeypatch)
    assert ("offset_plane", (_adapter, "TipPlane", -screw.SHANK_LEN), {}) in calls
    (helix,) = [c for c in calls if c[0] == "insert_helix"]
    pitch, revs = helix[1][1:3]
    assert pitch == pytest.approx(screw.PITCH)
    assert revs * pitch == pytest.approx(screw.SHANK_LEN + screw.PITCH)
    assert helix[2]["clockwise"] is False and helix[2]["reversed_dir"] is False
    # The cutter's top rides ON the major; its root flat is P/8 at the root.
    _profile, _slot, cutter, _runout = _chains(calls)
    radii = sorted({x for x, _y in cutter})
    assert radii == pytest.approx([screw.ROOT_DIA / 2.0, screw.SHANK_DIA / 2.0])
    assert max(y for _x, y in cutter) == pytest.approx(-screw.SHANK_LEN)
    (sweep,) = [c for c in calls if c[0] == "thread_sweep_cut"]
    # Unscoped: the vendor's one-body sweep leaves its last turn as a void in
    # the head, and the harvest's face multiset carries that void.
    assert sweep[1][1:5] == ("ThreadCutter", "ThreadHelix", None, "ThreadGroove")
    assert not [c for c in calls if c[0] == "split_at_plane"]


def test_runout_swallows_the_neck_under_the_bearing_face(monkeypatch) -> None:
    _adapter, calls = _record(monkeypatch)
    *_rest, runout = _chains(calls)
    assert (screw.RUNOUT_DIA / 2.0, 0.0) in runout
    assert (screw.RUNOUT_DIA / 2.0, -screw.NECK_LEN) in runout
    (x0, y0), (x1, y1) = runout[2], runout[3]
    # 60 deg from the axis: radius falls tan(60) per unit of depth.
    assert (x0 - x1) / (y0 - y1) == pytest.approx(math.tan(math.radians(60.0)))
    assert x1 == pytest.approx(screw.ROOT_DIA / 2.0)


def test_recipe_draws_the_screw_cut_to_fit_as_installed(monkeypatch) -> None:
    """R9-47: the part is modelled cut, its end broken in place of the factory
    tip chamfer; the thread stays the vendor's, seeded on the factory tip."""
    cut = {"cut_length": screw.CUT_LENGTH, "cut_end_break": screw.CUT_END_BREAK_MAX}
    _adapter, calls = _record(monkeypatch, **cut)
    profile, *_rest = _chains(calls)
    length, brk = screw.CUT_LENGTH, screw.CUT_END_BREAK_MAX
    major_r = screw.SHANK_DIA / 2.0
    assert [v for point in profile[5:8] for v in point] == pytest.approx(
        [major_r, -(length - brk), major_r - brk, -length, 0.0, -length]
    )
    (revolve_check,) = [c for c in calls if c[0] == "volume_check"]
    assert revolve_check[1][1] == pytest.approx(entry.revolved_volume(**cut))
    assert entry.revolved_volume(**cut) < entry.revolved_volume()
    assert ("offset_plane", (_adapter, "TipPlane", -screw.SHANK_LEN), {}) in calls


@pytest.mark.parametrize(
    ("cut_length", "cut_end_break"),
    [
        (screw.CUT_LENGTH, None),  # half a cut
        (None, screw.CUT_END_BREAK_MAX),
        (screw.SHANK_LEN, screw.CUT_END_BREAK_MAX),  # not short of the stock tip
        (screw.CUT_LENGTH, 0.0),  # an unbroken end
        (screw.NECK_LEN, screw.CUT_END_BREAK_MAX),  # no shank left
    ],
)
def test_recipe_refuses_a_cut_it_cannot_draw(cut_length, cut_end_break) -> None:
    with pytest.raises(ValueError):
        entry.revolved_volume(cut_length, cut_end_break)


def test_stock_build_uses_its_registered_recipe_head_up_on_the_origin(
    monkeypatch,
) -> None:
    metadata = STOCK_RECIPES[screw.SKU]
    assert metadata.module == entry.__name__
    assert metadata.callable_name == entry.build_91794A055.__name__
    assert metadata.threaded
    assert FASTENERS[part.PART_NAME] is part.SPEC
    assert part.SPEC.skus == (screw.SKU,)
    assert part.SPEC.material == "AISI 304"
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-161"
    assert int(row["quantity"]) == 3
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
    assert component.author is entry.build_91794A055
    assert component.parameters == {
        "cut_length": screw.CUT_LENGTH,
        "cut_end_break": screw.CUT_END_BREAK_MAX,
    }
    assert component.transform.translation_mm == (0.0, 0.0, 0.0)
    assert component.transform.rotation_radians == (0.0, 0.0, 0.0)
    assert seen["material"] == part.SPEC.material
    assert seen["screw_axis_planes"] == ("Front Plane", "Right Plane")


_DIMENSION = re.compile(r"\d")


def test_sheet_states_the_cut_and_no_dimension_in_the_registry_names() -> None:
    """The purchased sheet prints the registry's stock name, supplier and SKU
    besides its fixed footer, so none of those may carry a size (Rule 6); the
    installation note states the cut to fit (R9-47, as the paper-drive
    assembly step prints it) and the cut end's break."""
    row = _config.parts(part.PART_NAME)
    for field in ("title", "supplier", "finish"):
        assert not _DIMENSION.search(str(row[field])), (field, row[field])
    lines = row["installation_notes"].splitlines()
    assert len(lines) <= 4
    assert all(len(line) <= 70 for line in lines), lines
    flat = " ".join(lines)
    assert (
        f"CUT EACH TIP {screw.TIP_BELOW_REAR_FACE_TEXT} BELOW THE MHA-070 DISC "
        "REAR FACE AT ASSEMBLY;"
    ) in flat
    assert f"BREAK THE CUT END {screw.CUT_END_BREAK_TEXT}." in flat


def test_drawing_is_the_purchased_reference_sheet() -> None:
    spec = DRAWINGS_BY_NAME["transgear_disc_screw"]
    assert drawing.SPEC is spec
    assert spec.artifact_stem == part.PART_NAME
    assert spec.script == Path(drawing.__file__).resolve()
    assert (
        drawing.build.__code__.co_names.count("build_purchased_fastener_drawing") == 1
    )
