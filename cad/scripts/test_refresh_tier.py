"""The refresh tier: which recorded-input changes may skip the insert/mate loop.

Offline: the decision is pure over per-input digests, the explode closure is a
static read of the real builders, and the COM side runs against fakes.
"""

from __future__ import annotations

import asyncio
import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest

import _explode_refresh
from _buildgraph import ASSEMBLY_ORDER, SCRIPTS_DIR
from _refresh_tier import (
    RefreshTier,
    _author_function,
    _Entangled,
    classify_refresh,
    explode_plan,
)

BUILDER = "cad/scripts/build_pd_paper_drive_assembly.py"
EXPLODE = "cad/scripts/_pd_paper_drive_explode.py"
EXPLODE_SPEC = "cad/scripts/pd_paper_drive_explode_spec.py"
SHARED = "cad/scripts/_assembly_patterns.py"
PART = "cad/out/sldprt/pd-feed-roller.SLDPRT"
TOKEN = "cad/out/sldprt/.pd-feed-roller.execution"
RECIPE = frozenset({BUILDER, EXPLODE, EXPLODE_SPEC, SHARED})
CLOSURE = frozenset({EXPLODE, EXPLODE_SPEC})
SAVED = {
    BUILDER: "b0",
    EXPLODE: "e0",
    EXPLODE_SPEC: "s0",
    SHARED: "h0",
    PART: "p0",
    TOKEN: "t0",
}


def _tier(**changes):
    return classify_refresh(SAVED, {**SAVED, **changes}, RECIPE, CLOSURE)[0]


def test_explode_only_change_takes_the_explode_tier():
    assert _tier(**{EXPLODE_SPEC: "s1"}) is RefreshTier.EXPLODE
    assert _tier(**{EXPLODE: "e1", EXPLODE_SPEC: "s1"}) is RefreshTier.EXPLODE


def test_explode_and_geometry_change_rebuilds_full():
    assert _tier(**{EXPLODE_SPEC: "s1", BUILDER: "b1"}) is RefreshTier.FULL


def test_part_change_takes_the_parts_tier():
    assert _tier(**{PART: "p1", TOKEN: "t1"}) is RefreshTier.PARTS
    assert _tier() is RefreshTier.PARTS


def test_explode_and_part_change_rebuilds_full():
    assert _tier(**{EXPLODE_SPEC: "s1", TOKEN: "t1"}) is RefreshTier.FULL


def test_entangled_spec_change_rebuilds_full():
    # A module the explode reads but the builder also imports is outside the
    # closure: editing it can move the operational model.
    assert _tier(**{SHARED: "h1"}) is RefreshTier.FULL
    # An assembly without an explode closure never takes the tier.
    current = {**SAVED, EXPLODE_SPEC: "s1"}
    assert classify_refresh(SAVED, current, RECIPE, frozenset())[0] is RefreshTier.FULL


def test_unknown_or_reshaped_inputs_rebuild_full():
    assert classify_refresh(None, SAVED, RECIPE, CLOSURE)[0] is RefreshTier.FULL
    dropped = {k: v for k, v in SAVED.items() if k != EXPLODE_SPEC}
    assert classify_refresh(SAVED, dropped, RECIPE - {EXPLODE_SPEC}, CLOSURE)[0] is (
        RefreshTier.FULL
    )


# Every assembly whose explode may refresh without the insert/mate loop:
# (explode module, the function its builder authors with, the closure files).
QUALIFYING_EXPLODES = {
    "pd_paper_drive": (
        "_pd_paper_drive_explode",
        "create_paper_drive_explode",
        ("_pd_paper_drive_explode.py", "pd_paper_drive_explode_spec.py"),
    ),
    "mg_magnifier": (
        "_mg_magnifier_explode",
        "create_mg_magnifier_explode",
        ("_mg_magnifier_explode.py", "mg_magnifier_explode_spec.py"),
    ),
    "pn_pen": (
        "_pn_pen_explode",
        "create_pn_explode",
        ("_pn_pen_explode.py", "pn_pen_explode_spec.py", "_assembly_patterns.py"),
    ),
    "sm_summing": (
        "_sm_summing_explode",
        "create_summing_explode",
        ("_sm_summing_explode.py", "_assembly_patterns.py"),
    ),
}


def test_qualifying_explode_plans():
    plans = {stem: explode_plan(stem) for stem in ASSEMBLY_ORDER}
    qualified = {stem for stem, plan in plans.items() if plan.closure}
    assert qualified == set(QUALIFYING_EXPLODES)
    for stem, (module, function, closure) in QUALIFYING_EXPLODES.items():
        plan = plans[stem]
        assert (plan.module, plan.function) == (module, function), stem
        assert {Path(path) for path in plan.closure} == {
            (SCRIPTS_DIR / name).resolve() for name in closure
        }, stem
    # The drive train's explode takes build-time collar-pin roles.
    assert "found 0" in plans["dt_drive_train"].decline
    # The frame and measuring stick author their explodes inline.
    assert "no _fr_frame_explode.py" in plans["fr_frame"].decline
    assert "no _ms_measuring_stick_explode.py" in plans["ms_measuring_stick"].decline


@pytest.mark.parametrize("stem", sorted(QUALIFYING_EXPLODES))
def test_the_planned_function_is_the_one_the_builder_calls(stem):
    plan = explode_plan(stem)
    assert callable(getattr(importlib.import_module(plan.module), plan.function))


CANONICAL = """
from _x_explode import create
def build(adapter):
    author_in_drawing_configurations(adapter, NAME, lambda c: create(adapter, c))
"""


@pytest.mark.parametrize(
    "source, reason",
    [
        (
            CANONICAL.replace("create(adapter, c)", "create(adapter, roles, c)"),
            "found 0",
        ),
        (CANONICAL + "    create(adapter, 'Default')\n", "outside the explode"),
        (CANONICAL.replace("lambda c: create(adapter, c)", "create"), "found 0"),
        (
            CANONICAL
            + "    author_in_drawing_configurations(adapter, N, lambda c: create(adapter, c))\n",
            "found 2",
        ),
        ("import _x_explode\n" + CANONICAL, "module object"),
        (CANONICAL.replace("import create", "import *"), "star-imports"),
    ],
)
def test_entangled_builders_decline(source, reason):
    with pytest.raises(_Entangled, match=reason):
        _author_function(source, "_x_explode")


def test_canonical_builder_names_its_function():
    aliased = CANONICAL.replace("import create", "import make as create")
    assert _author_function(aliased, "_x_explode") == "make"


class _Selection:
    def GetSelectedObjectType3(self, _index, _mark):
        return _explode_refresh.SW_SEL_EXPLVIEWS


PIN = "vn-transgear-knob-drive-pin-1"
# A rotation with a signed zero, as the paper drive's knob drive pins report.
PIN_POSE = (0.99863, -0.052336, 0.0, 0.0, -0.0, -1.0, 0.052336, 0.99863, -0.0)
PIN_POSE += (0.01, 0.2, -0.1, 1.0, 0.0, 0.0, 0.0)


class _Model:
    """IModelDoc2 + IAssemblyDoc stand-in owning per-configuration views and
    top-level component poses."""

    def __init__(self, events, views, poses):
        self.events = events
        self.views = views
        self.poses = poses
        self.selected = None
        self.SelectionManager = _Selection()
        self.Extension = SimpleNamespace(
            SelectByID2=self._select, DeleteSelection2=self._delete
        )

    def _select(self, name, kind, *_rest):
        assert kind == "EXPLODEDVIEWS"
        self.selected = name
        return True

    def _delete(self, _options):
        for names in self.views.values():
            if self.selected in names:
                names.remove(self.selected)
        self.events.append(("delete", self.selected))
        return True

    def ClearSelection2(self, _all):
        self.selected = None

    def EditRebuild3(self):
        return True

    def GetExplodedViewNames2(self, configuration):
        return tuple(self.views.get(configuration, ()))

    def GetComponents(self, _top_level):
        return [
            SimpleNamespace(Name2=name, Transform2=SimpleNamespace(ArrayData=pose))
            for name, pose in self.poses.items()
        ]

    def IsExploded(self):
        return False


def _moved(pose, metres):
    return (*pose[:9], pose[9] + metres, *pose[10:])


def _fake_session(monkeypatch, tmp_path, *, digests, resaved_pin=PIN_POSE):
    """``digests`` are the fingerprints of the reopened and the re-saved model,
    in that order; ``resaved_pin`` is the pin's pose once the model is
    reopened after the save."""
    events = []
    views = {"Default": ["OLD"], "Default Simplified": ["OLD Simplified"]}
    model = _Model(events, views, {PIN: PIN_POSE})
    (tmp_path / "pd-paper-drive.SLDASM").write_bytes(b"saved")
    proof = tmp_path / ".pd-paper-drive.massprops.sha"
    proof.write_text("proof\n", encoding="utf-8")

    async def open_model(path):
        events.append(("open", Path(path).name))
        return SimpleNamespace(is_success=True)

    fingerprints = iter(digests)

    async def geometry(_adapter, _name):
        return next(fingerprints)

    async def reconcile(_adapter, _name, _path):
        events.append(("reconcile",))
        adapter.currentModel = _Model(events, views, {PIN: resaved_pin})

    def author_both(_adapter, _name, author):
        for configuration in ("Default", "Default Simplified"):
            author(configuration)

    module = _explode_refresh
    monkeypatch.setattr(module, "OUT_SLDASM", tmp_path)
    monkeypatch.setattr(module, "_massprops_sidecar", lambda _name: proof)
    monkeypatch.setattr(module, "assert_saved_display_data", lambda _path: None)
    monkeypatch.setattr(module, "check", lambda _what, result: result)
    monkeypatch.setattr(module, "saved_rebuild_status", lambda _adapter: 0)
    monkeypatch.setattr(module, "sync_simplified_configuration", lambda *_a, **_k: 0)
    monkeypatch.setattr(module, "_early_bound", lambda obj, _iface: obj)
    monkeypatch.setattr(module, "author_in_drawing_configurations", author_both)
    monkeypatch.setattr(module, "final_rebuild_before_save", lambda *_a: None)
    monkeypatch.setattr(module, "assert_reference_geometry_hidden", lambda *_a: None)
    monkeypatch.setattr(module, "assembly_geometry_digest", geometry)
    monkeypatch.setattr(module, "set_isometric_view", lambda _adapter: None)
    monkeypatch.setattr(
        module,
        "save_assembly_in_place",
        lambda _adapter, _name, changed: events.append(("save", changed)),
    )
    monkeypatch.setattr(module, "reconcile_saved_rebuild_state", reconcile)
    adapter = SimpleNamespace(currentModel=model, open_model=open_model)

    def author(configuration):
        assert model.GetExplodedViewNames2(configuration) == ()
        views[configuration].append(f"NEW {configuration}")
        events.append(("author", configuration))

    return adapter, author, events, proof


def _refresh(adapter, author):
    return asyncio.run(
        _explode_refresh.refresh_explode(adapter, "pd-paper-drive", author)
    )


def test_explode_refresh_replaces_each_configurations_views_then_saves(
    monkeypatch, tmp_path
):
    # The re-saved pin reports +0.0 where the reopened one reported -0.0: the
    # fingerprint's repr changes, the pose does not.
    unsigned = tuple(0.0 if value == 0.0 else value for value in PIN_POSE)
    adapter, author, events, proof = _fake_session(
        monkeypatch, tmp_path, digests=("proof", "resaved"), resaved_pin=unsigned
    )

    _refresh(adapter, author)

    assert events == [
        ("open", "pd-paper-drive.SLDASM"),
        ("delete", "OLD"),
        ("author", "Default"),
        ("delete", "OLD Simplified"),
        ("author", "Default Simplified"),
        ("save", True),
        ("reconcile",),
    ]
    assert proof.read_text(encoding="utf-8") == "resaved\n"


def test_explode_refresh_refuses_a_model_that_reopens_off_its_proof(
    monkeypatch, tmp_path
):
    adapter, author, events, proof = _fake_session(
        monkeypatch, tmp_path, digests=("drifted",)
    )

    with pytest.raises(RuntimeError, match="not its proof"):
        _refresh(adapter, author)

    assert events == [("open", "pd-paper-drive.SLDASM")]
    assert proof.read_text(encoding="utf-8") == "proof\n"


def test_explode_refresh_refuses_a_component_moved_by_authoring(monkeypatch, tmp_path):
    adapter, author, events, proof = _fake_session(
        monkeypatch, tmp_path, digests=("proof",)
    )
    model = adapter.currentModel

    def nudging(configuration):
        author(configuration)
        model.poses[PIN] = _moved(PIN_POSE, 1e-6)

    with pytest.raises(RuntimeError, match="moved re-authoring the explode"):
        _refresh(adapter, nudging)

    assert ("save", True) not in events
    assert proof.read_text(encoding="utf-8") == "proof\n"


def test_explode_refresh_retires_the_proof_when_the_saved_model_moved(
    monkeypatch, tmp_path
):
    adapter, author, events, proof = _fake_session(
        monkeypatch,
        tmp_path,
        digests=("proof",),
        resaved_pin=_moved(PIN_POSE, 1e-6),
    )

    with pytest.raises(RuntimeError, match="moved in the re-saved model"):
        _refresh(adapter, author)

    assert events[-2:] == [("save", True), ("reconcile",)]
    # Without a proof the next build cannot take the explode tier again.
    assert not proof.exists()


def test_explode_refresh_refuses_a_model_left_exploded(monkeypatch, tmp_path):
    adapter, author, events, _proof = _fake_session(monkeypatch, tmp_path, digests=())
    adapter.currentModel.IsExploded = lambda: True

    with pytest.raises(RuntimeError, match="must be collapsed"):
        _refresh(adapter, author)

    assert events == [("open", "pd-paper-drive.SLDASM")]
