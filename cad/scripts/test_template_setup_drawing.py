"""COM-free setup-only ABBA and real document-ownership contracts."""

import asyncio
from contextlib import contextmanager
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from diagnostics import benchmark_template_setup as probe
from diagnostics import _owned_native_documents as owned
from test_owned_native_documents_drawing import Model, native  # noqa: F401


@pytest.mark.parametrize(
    "scene", ["blank", "part", "saved", "model_view", "two_sheets", "no_sheet"]
)
def test_only_one_unsaved_blank_sheet_is_accepted(monkeypatch, scene):
    sheet = (object(),)
    model = SimpleNamespace(
        GetType=lambda: 1 if scene == "part" else 3,
        GetPathName=lambda: "saved.SLDDRW" if scene == "saved" else "",
        GetViews=lambda: (
            ()
            if scene == "no_sheet"
            else (sheet, sheet)
            if scene == "two_sheets"
            else ((object(), object()),)
            if scene == "model_view"
            else (sheet,)
        ),
    )
    monkeypatch.setattr(probe, "_early_bound", lambda value, _: value)
    if scene != "blank":
        with pytest.raises(RuntimeError):
            probe.blank_drawing_witness(SimpleNamespace(currentModel=model))
        return
    assert probe.blank_drawing_witness(SimpleNamespace(currentModel=model)) == {
        "kind": 3,
        "path": "",
        "sheet_count": 1,
        "model_view_count": 0,
    }


@pytest.fixture
def setup_scene(native, monkeypatch, tmp_path):  # noqa: F811
    original = tmp_path / "project.DRWDOT"
    original.write_bytes(b"immutable project template")
    baseline = [
        Model(native.source, kind=1),
        Model(None, title="Draw2 - Sheet1", dirty=True),
    ]
    native.app.documents.extend(baseline)
    native.app.ActiveDoc = baseline[-1]
    calls, created, preparations, receipts = [], [], [], []
    failure = {}
    expected = {
        "units": {"system": 4, "linear": 0, "decimals": 2},
        "dimension_styles": {"linear": 2, "chamfer": 2},
        "sheet_properties": [2.0, 1.0],
        "sheet_notes": [json.dumps({"text": "0.25 MM", "font": "Century Gothic"})],
        "blank_linked_extent_observations": [{"extent": [0, 0, 0, 0, 1, 0]}],
    }
    monkeypatch.setattr(probe, "_early_bound", lambda value, _: value)
    monkeypatch.setattr(probe.defaults.common, "PROJECT_DRWDOT", original)
    monkeypatch.setattr(
        probe.defaults,
        "runtime_fingerprints",
        lambda: {"helper": failure.get("helper", "pinned")},
    )
    monkeypatch.setattr(probe.defaults.recipes, "revision", lambda _: "frozen")

    async def prepare(adapter, spec, directory, row):
        preparations.append(spec)
        path = directory / "derived.DRWDOT"
        path.write_bytes(b"owned prepared template")
        row.update(
            path=str(path),
            sha256=probe.defaults.attachments.file_digest(path),
            before=deepcopy(expected),
            seconds=12.0,
            status="passed",
        )
        if failure.get("prepare"):
            row.update(status="failed", error="preparation failure")
            raise RuntimeError("preparation failure")
        return row

    def setup(adapter, variant):
        calls.append(variant)
        model = Model(None, title=f"Owned blank {len(created)}", dirty=True)
        created.append(model)
        native.app.documents.append(model)
        native.app.ActiveDoc = model
        adapter.currentModel = model
        if failure.get("setup"):
            raise RuntimeError("setup failure")
        return model, object()

    def snapshot(adapter, spec):
        result = deepcopy(expected)
        result["blank_linked_extent_observations"][0]["extent"][4] = 0
        if failure.get("semantic") and calls[-1] == "candidate":
            result["dimension_styles"]["chamfer"] = 0
        if failure.get("original"):
            original.write_bytes(b"changed original")
        if failure.get("helper_drift"):
            failure["helper"] = "changed"
        return result

    monkeypatch.setattr(probe.defaults, "prepare_template", prepare)
    monkeypatch.setattr(
        probe.defaults.common,
        "new_project_drawing",
        lambda adapter, **kwargs: setup(adapter, "baseline"),
    )
    monkeypatch.setattr(
        probe.defaults,
        "inherited_drawing",
        lambda adapter, path, spec: setup(adapter, "candidate"),
    )
    monkeypatch.setattr(probe.defaults, "defaults_snapshot", snapshot)
    original_close = native.app.CloseDoc

    def close(name):
        if failure.get("cleanup"):
            raise RuntimeError("cleanup failure")
        original_close(name)

    native.app.CloseDoc = close
    reports = tmp_path / "reports"

    async def run():
        return await owned.owned_callback(
            native.adapter,
            lambda adapter: probe.benchmark(
                adapter, probe.defaults.TemplateSpec((2, 1), 2), reports
            ),
        )

    def read():
        (receipt,) = reports.glob("*/measurements.json")
        receipts.append(receipt)
        return json.loads(receipt.read_text())

    return SimpleNamespace(
        run=lambda: asyncio.run(run()),
        report=read,
        calls=calls,
        created=created,
        preparations=preparations,
        baseline=baseline,
        native=native,
        failure=failure,
        original=original,
        receipts=receipts,
    )


def test_four_blank_drawings_use_abba_and_preserve_real_baseline_ownership(setup_scene):
    setup_scene.run()
    report = setup_scene.report()
    assert setup_scene.calls == list(probe.defaults.ORDER)
    assert len(setup_scene.preparations) == 1
    assert len(setup_scene.created) == 4
    assert setup_scene.native.app.documents == setup_scene.baseline
    assert setup_scene.native.app.closes == setup_scene.created
    assert setup_scene.native.adapter.opens == []
    assert setup_scene.original.read_bytes() == b"immutable project template"
    assert report["status"] == "passed"
    assert report["scope"] == "blank_sheet_setup_only"
    assert report["immutable_input_changes"] == {}
    for row in report["trials"]:
        assert row["status"] == "passed" and row["blank"]["model_view_count"] == 0
        assert all(
            row[field] >= 0
            for field in ("setup_seconds", "witness_seconds", "cleanup_seconds")
        )
    root = setup_scene.receipts[0].parent
    assert list(root.rglob("*.SLDDRW")) == []
    assert list(root.rglob("*.pdf")) == []
    assert len(list(root.rglob("*.DRWDOT"))) == 1


@pytest.mark.parametrize(
    "failure,count",
    [
        ("prepare", 0),
        ("setup", 1),
        ("semantic", 2),
        ("original", 1),
        ("helper_drift", 1),
    ],
)
def test_failure_stops_without_later_trials_and_preserves_evidence(
    setup_scene, failure, count
):
    setup_scene.failure[failure] = True
    with pytest.raises(Exception):
        setup_scene.run()
    report = setup_scene.report()
    assert report["status"] == "failed"
    assert len(setup_scene.calls) == count
    assert setup_scene.native.app.documents == setup_scene.baseline
    assert setup_scene.native.adapter.opens == []
    if count:
        assert report["trials"][-1]["status"] == "failed"
        assert "trial_error" in report["trials"][-1]


def test_setup_and_cleanup_errors_both_survive(setup_scene):
    setup_scene.failure.update(setup=True, cleanup=True)
    with pytest.raises(Exception):
        setup_scene.run()
    row = setup_scene.report()["trials"][0]
    assert row["failed_phase"] == "setup"
    assert "setup failure" in row["error"]
    assert "cleanup failure" in row["cleanup_error"]
    assert setup_scene.native.app.documents[:2] == setup_scene.baseline


def test_inner_setup_timer_excludes_ownership_witness_and_cleanup(
    monkeypatch, tmp_path
):
    clock = [0.0]
    monkeypatch.setattr(probe, "time", SimpleNamespace(perf_counter=lambda: clock[0]))

    @contextmanager
    def creation(*args):
        clock[0] += 11.0
        yield
        clock[0] += 13.0

    async def close():
        clock[0] += 17.0

    def setup(*args, **kwargs):
        clock[0] += 2.0

    def witness(*args):
        clock[0] += 3.0
        return {}

    adapter = SimpleNamespace(
        ownership=SimpleNamespace(creating_document=creation),
        close_owned_documents=close,
    )
    monkeypatch.setattr(probe.defaults.common, "new_project_drawing", setup)
    monkeypatch.setattr(probe, "blank_drawing_witness", lambda adapter: {})
    monkeypatch.setattr(probe.defaults, "defaults_snapshot", witness)
    row = {"variant": "baseline"}
    asyncio.run(
        probe.setup_trial(
            adapter,
            probe.defaults.TemplateSpec((2, 1), 2),
            {"before": {}},
            tmp_path,
            row,
            lambda: None,
        )
    )
    assert row["setup_seconds"] == 2.0
    assert row["witness_seconds"] == 3.0
    assert row["cleanup_seconds"] == 17.0
    assert row["trial_elapsed_seconds"] == 46.0


def test_parent_requires_attach_only_environment_before_seat(monkeypatch):
    monkeypatch.delenv("HARMONIC_SW_AUTOSTART", raising=False)
    with pytest.raises(RuntimeError, match="AUTOSTART=0"):
        probe.main([])


def test_parent_uses_existing_seat_wrapper_without_source_or_recipe_arguments(
    monkeypatch, tmp_path
):
    import dodo

    calls = []
    monkeypatch.setenv("HARMONIC_SW_AUTOSTART", "0")
    monkeypatch.setattr(
        dodo, "_run", lambda *args, **kwargs: calls.append((args, kwargs))
    )
    assert (
        probe.main(
            ["--scale", "2", "1", "--decimals", "2", "--report-root", str(tmp_path)]
        )
        == 0
    )
    ((args, kwargs),) = calls
    assert kwargs["com"] is True
    assert "--worker" in args[0]
    assert "--source-root" not in args[0] and "--recipe-revision" not in args[0]
