"""The original gear selector, not a duplicate algorithm, drives every fixture."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import _drawing_common as common
import _gear_drawing_entities as gear
from diagnostics import _tooth_selector_observation as observation
from diagnostics import probe_datum_policy_recipes as pilot
from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter


@pytest.fixture(autouse=True)
def no_optin(monkeypatch):
    monkeypatch.delenv("HARMONIC_TOOTH_SELECTOR_OBSERVATION", raising=False)


class Point:
    def __init__(self, values):
        self.values, self.reads = values, 0

    @property
    def ArrayData(self):
        self.reads += 1
        if isinstance(self.values, BaseException):
            raise self.values
        return self.values


def silhouette(start, end):
    return SimpleNamespace(
        GetStartPoint=Mock(return_value=start), GetEndPoint=Mock(return_value=end)
    )


class Adapter:
    _attempt = PyWin32Adapter._attempt
    _get_attr_or_call = PyWin32Adapter._get_attr_or_call


@pytest.fixture
def scene(monkeypatch):
    monkeypatch.setattr(common, "_early_bound", lambda obj, *_: obj)
    monkeypatch.setattr(gear, "_early_bound", lambda obj, *_: obj)
    monkeypatch.setattr(observation, "_early_bound", lambda obj, *_: obj)
    attributes = Mock()
    monkeypatch.setattr(gear, "_span_attrs", attributes)
    start, end = Point((0.0, 0.03, -0.004)), Point((-0.0, 0.03, 0.004))
    edge = silhouette(start, end)
    source = object()
    view = SimpleNamespace(
        Position=(0.3, 0.175),
        ScaleDecimal=1.0,
        ModelToViewTransform=SimpleNamespace(
            ArrayData=tuple(float(i) for i in range(16))
        ),
        ReferencedDocument=source,
        ReferencedConfiguration="Default",
        GetName2=Mock(return_value="Drawing View2"),
        GetVisibleComponents=Mock(return_value=[object()]),
        GetVisibleEntities2=Mock(return_value=[edge]),
    )
    drawing = SimpleNamespace(
        GetType=Mock(return_value=3),
        GetTitle=Mock(return_value="Draw1 - Sheet1"),
        GetPathName=Mock(return_value=""),
        GetViews=Mock(return_value=[[object(), view]]),
    )
    adapter = Adapter()
    adapter.currentModel = drawing
    adapter.swApp = SimpleNamespace(
        ActiveDoc=drawing, IsSame=Mock(side_effect=lambda a, b: int(a is b))
    )
    adapter.ownership = SimpleNamespace(assert_current_owned=Mock())
    module = SimpleNamespace(
        visible_tooth_tip_silhouette=gear.visible_tooth_tip_silhouette
    )
    return SimpleNamespace(
        adapter=adapter,
        source=source,
        view=view,
        drawing=drawing,
        module=module,
        edge=edge,
        start=start,
        end=end,
        attributes=attributes,
        trial={},
    )


def run(c, mode=observation.ToothObservation.ENDPOINTS):
    with observation.observe_selector(c.adapter, c.module, c.source, c.trial, mode):
        return c.module.visible_tooth_tip_silhouette(c.adapter, c.view, 60.0)


def record(c):
    (row,) = c.trial["tooth_selector_observations"]
    return row


def assert_once(c):
    c.view.GetVisibleComponents.assert_called_once_with()
    c.view.GetVisibleEntities2.assert_called_once()
    c.edge.GetStartPoint.assert_called_once_with()
    c.edge.GetEndPoint.assert_called_once_with()


def test_default_is_exact_noop_and_preserves_actual_result(scene):
    c = scene
    original = c.module.visible_tooth_tip_silhouette
    with observation.observe_selector(
        c.adapter,
        c.module,
        c.source,
        c.trial,
        observation.observation_from_environment(),
    ):
        assert c.module.visible_tooth_tip_silhouette is original
        assert original(c.adapter, c.view, 60.0) is c.edge
    assert c.trial == {}
    c.adapter.ownership.assert_current_owned.assert_not_called()
    c.adapter.swApp.IsSame.assert_not_called()
    c.drawing.GetViews.assert_not_called()
    assert_once(c)
    assert c.start.reads == c.end.reads == 1


def test_original_pass_single_enumeration_exact_handles_and_raw_arrays(scene):
    c = scene
    bindings, scan = gear._early_bound, gear.visible_view_entities
    original = c.module.visible_tooth_tip_silhouette
    assert run(c) is c.edge
    assert (gear._early_bound, gear.visible_view_entities) == (bindings, scan)
    assert c.module.visible_tooth_tip_silhouette is original
    assert_once(c)
    assert c.start.reads == c.end.reads == 1
    c.attributes.assert_called_once_with(
        silhouettes=1, matched=1, outside_diameter_mm=60.0
    )
    row = record(c)
    assert row["enumerations"][0]["count"] == 1
    assert row["returned_binding_indices"] == [0]
    assert row["candidates"][0]["enumeration_indices"] == [0]
    calls = row["candidates"][0]["calls"]
    assert [call["name"].split("@")[0] for call in calls] == [
        "GetStartPoint",
        "adapter._attempt.return",
        "GetEndPoint",
        "adapter._attempt.return",
        "ArrayData",
        "ArrayData",
    ]
    assert calls[4]["returned"]["value"][1]["value"] == 0.03
    assert calls[5]["returned"]["value"][0]["value"] == -0.0
    assert all(call["array_shape"] == "finite_native_doubles" for call in calls[4:])
    assert row["entry"]["owner_view_matches"] == row["exit"]["owner_view_matches"] == 1
    assert row["seconds_including_observations"] >= 0
    json.dumps(c.trial, allow_nan=False)


@pytest.mark.parametrize("reason", ["radius", "null", "getter_error", "empty"])
def test_real_rejection_retains_actual_reads_and_adapter_default(scene, reason):
    c = scene
    if reason == "radius":
        c.start.values = (0.0, 0.02, 0.0)
    if reason == "null":
        c.edge.GetStartPoint.return_value = None
    if reason == "getter_error":
        c.edge.GetStartPoint.side_effect = OSError("native start unavailable")
    if reason == "empty":
        c.start.values = ()
    with pytest.raises(RuntimeError, match="no visible tooth-tip silhouette"):
        run(c)
    assert_once(c)
    c.attributes.assert_called_once_with(
        silhouettes=1, matched=0, outside_diameter_mm=60.0
    )
    calls = record(c)["candidates"][0]["calls"]
    if reason in ("null", "getter_error"):
        assert len(calls) == 4
        assert calls[1]["returned"]["value"] is None
        assert c.start.reads == c.end.reads == 0
    if reason == "getter_error":
        assert calls[0]["error"] == "OSError('native start unavailable')"
    if reason == "empty":
        assert calls[4]["array_shape"] == "invalid"
        assert c.start.reads == c.end.reads == 1
    assert "returned_binding_indices" not in record(c)


@pytest.mark.parametrize("failure", ["array", "scan", "binding"])
def test_exact_original_exception_and_scoped_patches_survive_exit_failure(
    scene, monkeypatch, failure
):
    c = scene
    primary = OSError("primary native error")
    if failure == "array":
        c.start.values = primary
    if failure == "scan":
        c.view.GetVisibleEntities2.side_effect = primary
    if failure == "binding":
        monkeypatch.setattr(gear, "_early_bound", Mock(side_effect=primary))
    original, binding, scan = (
        c.module.visible_tooth_tip_silhouette,
        gear._early_bound,
        gear.visible_view_entities,
    )
    c.drawing.GetViews.side_effect = [
        [[object(), c.view]],
        OSError("exit observation failed"),
    ]
    with pytest.raises(OSError) as caught:
        run(c)
    assert caught.value is primary
    assert c.module.visible_tooth_tip_silhouette is original
    assert gear._early_bound is binding and gear.visible_view_entities is scan
    assert record(c)["error"] == repr(primary)
    assert "exit observation failed" in record(c)["exit"]["observation_error"]


def test_return_entity_not_replaced_by_secondary_exit_error(scene):
    scene.drawing.GetViews.side_effect = [
        [[object(), scene.view]],
        OSError("exit failed"),
    ]
    assert run(scene) is scene.edge
    assert "exit failed" in record(scene)["exit"]["observation_error"]


@pytest.mark.parametrize(
    "state",
    [
        "wrong_active",
        "wrong_owner",
        "duplicate",
        "wrong_source",
        "unknown",
        "wrong_type",
    ],
)
def test_refuse_unproved_owned_entry_before_any_selector_reads(scene, state):
    c = scene
    if state == "wrong_active":
        c.adapter.swApp.ActiveDoc = object()
    if state == "wrong_owner":
        c.drawing.GetViews.return_value = [[object(), object()]]
    if state == "duplicate":
        c.drawing.GetViews.return_value = [[object(), c.view, c.view]]
    if state == "wrong_source":
        c.view.ReferencedDocument = object()
    if state == "unknown":
        c.adapter.swApp.IsSame.return_value = -1
        c.adapter.swApp.IsSame.side_effect = None
    if state == "wrong_type":
        c.drawing.GetType.return_value = True
    with pytest.raises(RuntimeError):
        run(c)
    c.view.GetVisibleComponents.assert_not_called()
    c.edge.GetStartPoint.assert_not_called()
    assert record(c)["candidates"] == []


@pytest.mark.parametrize("raw", [(1.0,), (0.0, float("nan")), (True, 0.2), None])
def test_invalid_view_array_recorded_without_rounding_or_selector_rule_change(
    scene, raw
):
    scene.view.Position = raw
    assert run(scene) is scene.edge
    reading = next(
        row for row in record(scene)["entry"]["reads"] if row["name"] == "view.Position"
    )
    assert reading["array_shape"] == "invalid"
    json.dumps(scene.trial, allow_nan=False)


@pytest.mark.parametrize("value", ["", "on", "ENDPOINTS", "unknown"])
@pytest.mark.parametrize("worker", ["parent", "worker"])
def test_invalid_environment_before_owned_parent_worker_routing(
    monkeypatch, tmp_path, value, worker
):
    monkeypatch.setenv("HARMONIC_TOOTH_SELECTOR_OBSERVATION", value)
    route = Mock(side_effect=AssertionError("native route reached"))
    monkeypatch.setattr(pilot, "require_owned_diagnostic_environment", route)
    args = ["--source-root", str(tmp_path), "--guard-root", str(tmp_path)]
    if worker == "worker":
        args.append("--worker")
    with pytest.raises(ValueError, match="HARMONIC_TOOTH_SELECTOR_OBSERVATION"):
        pilot.main(args)
    route.assert_not_called()


@pytest.mark.asyncio
async def test_direct_pilot_invalid_mode_before_files_and_owned_setup(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("HARMONIC_TOOTH_SELECTOR_OBSERVATION", "invalid")
    adapter = SimpleNamespace(ownership=Mock())
    with pytest.raises(ValueError, match="HARMONIC_TOOTH_SELECTOR_OBSERVATION"):
        await pilot.pilot(adapter, "HEAD", tmp_path, tmp_path, tmp_path / "new")
    adapter.ownership.register_directory.assert_not_called()
    assert not (tmp_path / "new").exists()


@pytest.mark.parametrize("value", [None, "off", "endpoints"])
def test_exact_environment_enum(monkeypatch, value):
    if value is not None:
        monkeypatch.setenv("HARMONIC_TOOTH_SELECTOR_OBSERVATION", value)
    assert observation.observation_from_environment() is observation.ToothObservation(
        value or "off"
    )


def test_optin_rejects_unrelated_target_before_native_routing(monkeypatch, tmp_path):
    monkeypatch.setenv("HARMONIC_TOOTH_SELECTOR_OBSERVATION", "endpoints")
    route = Mock(side_effect=AssertionError("native route reached"))
    monkeypatch.setattr(pilot, "require_owned_diagnostic_environment", route)
    with pytest.raises(ValueError, match="requires crank"):
        pilot.main(
            [
                "--source-root",
                str(tmp_path),
                "--guard-root",
                str(tmp_path),
                "--target",
                "rocker_arm",
            ]
        )
    route.assert_not_called()


def test_original_tie_rule_and_duplicate_wrapper_enumeration_are_not_reimplemented(
    scene,
):
    c = scene
    lower = silhouette(Point((0.03, 0.0, -0.004)), Point((0.03, 0.0, 0.004)))
    c.view.GetVisibleEntities2.return_value = [c.edge, lower, c.edge]
    assert run(c) is c.edge
    assert record(c)["returned_binding_indices"] == [0, 2]
    assert record(c)["candidates"][0]["enumeration_indices"] == [0, 2]
    assert record(c)["candidates"][1]["enumeration_indices"] == [1]
    assert c.edge.GetStartPoint.call_count == c.edge.GetEndPoint.call_count == 2
    lower.GetStartPoint.assert_called_once_with()
    c.attributes.assert_called_once_with(
        silhouettes=3, matched=3, outside_diameter_mm=60.0
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["passed", "radius_rejected"])
async def test_actual_owned_pilot_scope_retains_journal_and_source_guards(
    scene,
    monkeypatch,
    tmp_path,
    outcome,
):
    from pathlib import Path
    from types import MethodType
    from test_benchmark_drawing_recipes import recipe
    from test_datum_policy_recipes_drawing import (
        Adapter as PilotAdapter,
        fixture_sources,
    )

    c = scene
    source_root, guard_root = fixture_sources(tmp_path, monkeypatch)
    for directory in (source_root, guard_root):
        (directory / "crank-drive-gear.SLDPRT").write_bytes(b"exact source")
    monkeypatch.setitem(
        pilot.EXPECTED_PART_HASHES,
        "crank_drive_gear",
        pilot.attachments.file_digest(source_root / "crank-drive-gear.SLDPRT"),
    )
    # This test isolates the new seam. Existing native entity-bank coverage is
    # exercised separately, not replaced by synthetic role claims here.
    monkeypatch.setitem(pilot.TARGETS, "crank_drive_gear", pilot.TARGETS["rocker_arm"])
    code = recipe(Path("not-the-owned-source"))
    assert code.count("    drawing_factory(adapter)\n") == 1
    code = (
        "from _gear_drawing_entities import visible_tooth_tip_silhouette\n"
        + code.replace(
            "    drawing_factory(adapter)\n",
            "    drawing_factory(adapter)\n    visible_tooth_tip_silhouette(adapter, adapter.view, 60.0)\n",
        )
    )
    monkeypatch.setattr(pilot.benchmark, "recipe_source", lambda *_: code)
    monkeypatch.setattr(pilot.benchmark, "revision", lambda *_: "frozen")
    monkeypatch.setattr(pilot, "helper_fingerprints", lambda: {"helper": "frozen"})
    monkeypatch.setattr(pilot, "adapter_fingerprints", lambda: {"adapter": "frozen"})
    handle = object()
    monkeypatch.setattr(
        pilot,
        "source_dimensions",
        lambda *_: ({"configuration": "Default"}, {"D": handle}),
    )
    monkeypatch.setattr(pilot, "drawing_witness", Mock(return_value={"native": "same"}))
    monkeypatch.setattr(
        pilot, "compare_drawing_reopen", Mock(return_value={"status": "passed"})
    )
    monkeypatch.setattr(pilot, "retain_failed_drawing", Mock())
    monkeypatch.setattr(observation, "_state", Mock())
    monkeypatch.setenv("HARMONIC_TOOTH_SELECTOR_OBSERVATION", "endpoints")
    adapter = PilotAdapter("normal")
    adapter.view = c.view
    adapter._attempt = MethodType(PyWin32Adapter._attempt, adapter)
    adapter._get_attr_or_call = MethodType(PyWin32Adapter._get_attr_or_call, adapter)
    if outcome == "radius_rejected":
        c.start.values = (0.0, 0.02, 0.0)
        with pytest.raises(RuntimeError, match="no visible tooth-tip silhouette"):
            await pilot.pilot(
                adapter,
                "frozen",
                source_root,
                guard_root,
                tmp_path / "reports",
                targets=("crank_drive_gear",),
            )
    else:
        await pilot.pilot(
            adapter,
            "frozen",
            source_root,
            guard_root,
            tmp_path / "reports",
            targets=("crank_drive_gear",),
        )
    (report_path,) = (tmp_path / "reports").glob("*/pilot.json")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    trial = report["trials"][0]
    assert report["tooth_selector_observation"] == "endpoints"
    assert report["sources_after"] == report["sources_before"]
    assert report["runtime_final_guard_errors"] == []
    assert trial["copy_final"] == pilot.EXPECTED_PART_HASHES["crank_drive_gear"]
    (row,) = trial["tooth_selector_observations"]
    assert row["enumerations"][0]["count"] == 1
    assert len(row["candidates"][0]["calls"]) == 6
    assert c.view.GetVisibleEntities2.call_count == 1
    assert report["status"] == ("passed" if outcome == "passed" else "failed")
    if outcome == "passed":
        assert trial["reopen_annotation_comparison"]["status"] == "passed"
        assert pilot.drawing_witness.call_count == 2
        assert len(adapter.drawn) == 1
    else:
        assert "no visible tooth-tip silhouette" in row["error"]
        assert adapter.drawn == []
        pilot.retain_failed_drawing.assert_called_once()
