"""Offline contracts for the MHA-VN-041 transgear pivot screw."""

from __future__ import annotations

import asyncio
import contextlib
import json
import re
from pathlib import Path

import pytest

import _config
import _telemetry
import build_vn_transgear_pivot_screw as part
import draw_vn_transgear_pivot_screw as drawing
import transgear_hanger_joints as joints
import vn_transgear_pivot_screw_spec as screw
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _test_stock_recipes import discovered_recipes
from diagnostics import diag_build_91829A205 as entry

IN = 25.4
UNDERHEAD = screw.SHOULDER_LEN + screw.THREAD_LEN


def test_spec_is_the_catalogue_screw() -> None:
    """91829A205 per mcmaster.com (2026-09-30): shoulder Ø3/16 x 1/2,
    8-32 UNC-2A x 3/16, slotted head Ø5/16 x 5/32."""
    assert screw.SKU == "91829A205"
    assert screw.SHOULDER_DIA == pytest.approx(3.0 / 16.0 * IN)
    assert screw.SHOULDER_LEN == pytest.approx(0.5 * IN)
    assert screw.THREAD == "#8-32"
    assert screw.THREAD_MAJOR == pytest.approx(0.164 * IN)
    assert screw.PITCH == pytest.approx(IN / 32.0)
    assert screw.THREAD_LEN == pytest.approx(3.0 / 16.0 * IN)
    assert screw.HEAD_DIA == pytest.approx(5.0 / 16.0 * IN)
    assert screw.HEAD_H == pytest.approx(5.0 / 32.0 * IN)


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

    async def create_extrusion(self, *args):
        return await self._async("create_extrusion", *args)

    async def create_cut_extrude(self, *args):
        return await self._async("create_cut_extrude", *args)

    async def create_revolve(self, *args):
        return await self._async("create_revolve", *args)

    async def add_chamfer(self, *args):
        return await self._async("add_chamfer", *args)


# Two bodies after the split at the neck's land bottom: the head-and-shoulder
# body ends there, the threaded tail runs from there to the tip.
_SPLIT_BODIES = [
    {"name": "Head", "box_mm": [-4.0, entry.Y_LAND_BOT, -4.0, 4.0, 4.0, 4.0]},
    {
        "name": "Tail",
        "box_mm": [-2.1, -UNDERHEAD, -2.1, 2.1, entry.Y_LAND_BOT, 2.1],
    },
]


def _record(monkeypatch, bodies=_SPLIT_BODIES) -> _Recorder:
    adapter = _Recorder()

    def logger(name, result=None):
        def call(*args, **kwargs):
            adapter.log(name, args, kwargs)
            return result

        return call

    def com_logger(name):
        def call(_adapter, *args, **kwargs):
            adapter.log(name, args, kwargs)

        return call

    def async_logger(name):
        async def call(_adapter, *args, **kwargs):
            adapter.log(name, args, kwargs)

        return call

    async def volume_check(_adapter, label, expected, tol):
        adapter.log("volume_check", (label, expected, tol))
        return expected

    @contextlib.contextmanager
    def no_inference(_adapter):
        yield

    def split(_adapter, plane, name):
        adapter.log("split_at_plane", (plane, name))
        return bodies

    monkeypatch.setattr(entry, "check", logger("check", True))
    monkeypatch.setattr(entry, "name_last_feature", com_logger("name_last_feature"))
    monkeypatch.setattr(entry, "volume_check", volume_check)
    monkeypatch.setattr(entry, "define_circle", async_logger("define_circle"))
    monkeypatch.setattr(
        entry, "define_centered_rectangle", async_logger("define_centered_rectangle")
    )
    monkeypatch.setattr(entry, "add_line_chain", async_logger("add_line_chain"))
    monkeypatch.setattr(entry, "extrude_at_offset", com_logger("extrude_at_offset"))
    monkeypatch.setattr(entry, "offset_plane", com_logger("offset_plane"))
    monkeypatch.setattr(entry, "insert_helix", com_logger("insert_helix"))
    monkeypatch.setattr(entry, "thread_sweep_cut", com_logger("thread_sweep_cut"))
    monkeypatch.setattr(entry, "combine_union", com_logger("combine_union"))
    monkeypatch.setattr(entry, "split_at_plane", split)
    monkeypatch.setattr(entry, "no_sketch_inference", no_inference)
    monkeypatch.setattr(_telemetry, "info", lambda *a, **k: None)
    asyncio.run(entry.build_91829A205(adapter))
    return adapter


def _calls(events, name):
    return [c for c in events if c[0] == name]


def test_recipe_stacks_head_shoulder_and_thread_on_the_shoulder_face(
    monkeypatch,
) -> None:
    calls = _record(monkeypatch).events
    # Head, shoulder and shank circles on the Top Plane (the shoulder face).
    radii = [c[1][2] for c in _calls(calls, "define_circle")]
    assert radii == pytest.approx(
        [screw.HEAD_DIA / 2.0, screw.SHOULDER_DIA / 2.0, screw.THREAD_MAJOR / 2.0]
    )
    head = _calls(calls, "create_extrusion")[0][1][0]
    assert head.depth == pytest.approx(screw.HEAD_H)
    # The shoulder hangs from y = 0 and the thread from the shoulder's end.
    offsets = [c[1] for c in _calls(calls, "extrude_at_offset")]
    assert offsets == [
        pytest.approx((screw.SHOULDER_LEN, -screw.SHOULDER_LEN)),
        pytest.approx((screw.THREAD_LEN, -UNDERHEAD)),
    ]
    # The driver slot is cut down from the head top and stops inside it.
    assert ("offset_plane", ("HeadTop", pytest.approx(screw.HEAD_H)), {}) in calls
    (slot,) = _calls(calls, "define_centered_rectangle")
    assert slot[1][1] == pytest.approx(screw.SLOT_WIDTH / 2.0)
    assert slot[1][0] > screw.HEAD_DIA / 2.0
    (cut,) = _calls(calls, "create_cut_extrude")
    assert cut[1][0].depth == pytest.approx(screw.SLOT_DEPTH)
    assert 0.0 < cut[1][0].depth < screw.HEAD_H


def test_neck_regains_the_major_where_the_joint_counts_full_thread(
    monkeypatch,
) -> None:
    """The revolved neck cut is the vendor's: fillet off the shoulder's end
    face into the land, then a 45 deg flank that reaches the thread major
    exactly FULL_THREAD_START below that face -- where the hanger joint
    starts counting engagement."""
    calls = _record(monkeypatch).events
    (revolve,) = _calls(calls, "create_revolve")
    assert revolve[1][0].is_cut
    assert revolve[1][0].angle == pytest.approx(360.0)
    end_face = -screw.SHOULDER_LEN
    major_r = screw.THREAD_MAJOR / 2.0
    neck_r = screw.NECK_DIA / 2.0
    (arc,) = _calls(calls, "sketch.CreateArc")
    centre, start, stop = ([v * 1000.0 for v in arc[1][i : i + 2]] for i in (0, 3, 6))
    assert start == pytest.approx([major_r, end_face])
    assert stop == pytest.approx([neck_r, end_face - screw.NECK_FILLET_R])
    assert centre == pytest.approx([major_r, end_face - screw.NECK_FILLET_R])
    neck_chain = _calls(calls, "add_line_chain")[0][1][0]
    land_top, land_bot, flank_end = neck_chain[:3]
    assert land_top[0] == land_bot[0] == pytest.approx(neck_r)
    assert land_bot[1] == pytest.approx(end_face - screw.NECK_FLAT_END)
    # The flank is 45 deg and crosses the major at the full-thread start.
    rise = flank_end[0] - land_bot[0]
    assert land_bot[1] - flank_end[1] == pytest.approx(rise)
    assert flank_end[0] > major_r
    y_at_major = land_bot[1] - (major_r - land_bot[0])
    assert y_at_major == pytest.approx(end_face - screw.FULL_THREAD_START)


def test_thread_is_cut_on_the_tail_below_the_neck_land(monkeypatch) -> None:
    calls = _record(monkeypatch).events
    (helix,) = _calls(calls, "insert_helix")
    pitch, revs = helix[1][0:2]
    assert pitch == pytest.approx(screw.PITCH)
    assert revs * pitch == pytest.approx(screw.THREAD_LEN)
    assert ("offset_plane", ("TipPlane", pytest.approx(-UNDERHEAD)), {}) in calls
    # Split at the land bottom (vendor Plane1); the groove is scoped to the
    # tail below it, so it cannot touch the shoulder or the neck fillet.
    split_plane = next(
        c for c in _calls(calls, "offset_plane") if c[1][0] == "SplitPlane"
    )
    assert split_plane[1][1] == pytest.approx(-screw.SHOULDER_LEN - screw.NECK_FLAT_END)
    assert ("split_at_plane", ("SplitPlane", "TailSplit"), {}) in calls
    (sweep,) = _calls(calls, "thread_sweep_cut")
    assert sweep[1][2:4] == ("Tail", "ThreadGroove")
    assert _calls(calls, "combine_union")


def test_recipe_refuses_a_split_that_leaves_no_single_tail(monkeypatch) -> None:
    whole = [dict(_SPLIT_BODIES[0], box_mm=[-4.0, -UNDERHEAD, -4.0, 4.0, 4.0, 4.0])]
    with pytest.raises(RuntimeError, match="below the neck land"):
        _record(monkeypatch, bodies=whole)


def test_fleet_diagnostic_driver_gates_the_new_sku() -> None:
    from diagnostics.diag_build_mcmaster import REGISTRY

    assert REGISTRY[screw.SKU] is entry.build_91829A205


def test_replica_gate_reads_the_vendor_com_in_the_part_frame(monkeypatch) -> None:
    """The vendor origin is mid-overall, head +z: its tip and head top land
    at the part frame's tip and head top."""
    com_map = _record(monkeypatch)._mcm_com_map
    half = (screw.HEAD_H + UNDERHEAD) / 2.0
    assert com_map([0.0, 0.0, -half])[1] == pytest.approx(-UNDERHEAD)
    assert com_map([0.0, 0.0, half])[1] == pytest.approx(screw.HEAD_H)


def test_stock_build_uses_its_registered_recipe_head_up_on_the_origin(
    monkeypatch,
) -> None:
    metadata = discovered_recipes()[screw.SKU]
    assert metadata.module == entry.__name__
    assert metadata.callable_name == entry.build_91829A205.__name__
    assert metadata.threaded
    assert FASTENERS[part.PART_NAME] is part.SPEC
    assert part.SPEC.skus == (screw.SKU,)
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-VN-041"
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
    assert component.author is entry.build_91829A205
    assert component.transform.translation_mm == (0.0, 0.0, 0.0)
    assert component.transform.rotation_radians == (0.0, 0.0, 0.0)
    assert seen["material"] == part.SPEC.material
    assert seen["screw_axis_planes"] == ("Front Plane", "Right Plane")


_DUMP = (
    Path(__file__).resolve().parents[1]
    / "out"
    / "reports"
    / f"mcmaster-{screw.SKU}-dump.json"
)


def test_spec_is_the_vendor_model() -> None:
    """The local-only harvest of the vendor SLDPRT (ruling R9-7) states the
    spec's catalogue, neck, slot and chamfer dimensions."""
    if not _DUMP.exists():
        pytest.skip(f"no local vendor harvest at {_DUMP}")
    truth = json.loads(_DUMP.read_text(encoding="utf-8"))
    dims = {
        d["full_name"].split("@")[0] + "@" + d["owner"]: d.get("value_mm")
        for f in truth["features"]
        for d in f["dimensions"]
    }
    assert dims["Head Diameter@Sketch1"] == pytest.approx(screw.HEAD_DIA)
    assert dims["Head Height@Sketch1"] == pytest.approx(screw.HEAD_H)
    assert dims["Shoulder Diameter@Sketch1"] == pytest.approx(screw.SHOULDER_DIA)
    assert dims["Shoulder Length@Sketch1"] == pytest.approx(screw.SHOULDER_LEN)
    assert dims["Thread Length@Sketch1"] == pytest.approx(screw.THREAD_LEN)
    assert dims["Screw Size Decimal Equivalent@Sketch1"] == pytest.approx(
        screw.THREAD_MAJOR
    )
    assert dims["Pitch@Helix/Spiral2"] == pytest.approx(screw.PITCH)
    assert dims["CADA@Sketch5"] == pytest.approx(screw.NECK_DIA)
    assert dims["CADB@Sketch5"] == pytest.approx(screw.NECK_FLAT_END)
    assert dims["D1@Sketch8"] == pytest.approx(screw.SLOT_WIDTH)
    assert dims["D1@Cut-Extrude2"] == pytest.approx(screw.SLOT_DEPTH)
    assert dims["D1@Chamfer1"] == pytest.approx(screw.HEAD_CHAMFER)
    assert dims["D1@Chamfer2"] == pytest.approx(screw.TIP_CHAMFER)
    (fillet,) = [
        s
        for f in truth["features"]
        if f["name"] == "Sketch5"
        for s in f["sketch"]["segments"]
        if s["kind"] == "arc"
    ]
    assert fillet["radius_mm"] == pytest.approx(screw.NECK_FILLET_R)


_DIMENSION = re.compile(r"\d")


def test_sheet_states_the_joint_engagement_the_hanger_judges() -> None:
    """The purchased sheet prints the registry's installation line: it must be
    the joint module's text, stating the floored worst-case engagement."""
    row = _config.parts(part.PART_NAME)
    notes = row["installation_notes"]
    assert notes == joints.PIVOT_SCREW_INSTALLATION_NOTES
    assert f"{joints.PIVOT_ENGAGEMENT_WORST_PRINTED:.2f}D MIN" in notes
    assert f"{joints.PIVOT_ENGAGEMENT_NOMINAL_D:.2f}D NOMINAL" in notes
    # A MIN never claims more than the worst case gives.
    assert joints.PIVOT_ENGAGEMENT_WORST_PRINTED <= joints.PIVOT_ENGAGEMENT_WORST_D
    for field in ("title", "supplier", "finish"):
        assert not _DIMENSION.search(str(row[field])), (field, row[field])


def test_drawing_is_the_purchased_reference_sheet() -> None:
    spec = DRAWINGS_BY_NAME["vn_transgear_pivot_screw"]
    assert drawing.SPEC is spec
    assert spec.artifact_stem == part.PART_NAME
    assert spec.script == Path(drawing.__file__).resolve()
    assert (
        drawing.build.__code__.co_names.count("build_purchased_fastener_drawing") == 1
    )
