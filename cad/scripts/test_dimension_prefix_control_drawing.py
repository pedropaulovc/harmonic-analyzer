"""Real prefix helper, fake native PART, and the existing owned cleanup path."""

import asyncio
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from diagnostics import probe_dimension_prefix as probe
from diagnostics import _owned_native_documents as owned
from test_owned_native_documents_drawing import Model, native  # noqa: F401


@pytest.fixture
def scene(native, monkeypatch):  # noqa: F811
    baseline = Model(None, title="User - Sheet1", dirty=True)
    native.app.documents.append(baseline)
    native.app.ActiveDoc = baseline
    monkeypatch.setattr(probe, "_early_bound", lambda value, _: value)
    monkeypatch.setattr(probe.marks, "_early_bound", lambda value, _: value)
    monkeypatch.setattr(probe.prefix_control, "_early_bound", lambda value, _: value)
    monkeypatch.setattr(probe.benchmark, "revision", lambda _: "a" * 40)
    monkeypatch.setattr(probe, "helper_fingerprints", lambda: {"prefix": "frozen"})
    monkeypatch.setattr(probe, "adapter_fingerprints", lambda: {"adapter": "frozen"})
    original_open = native.adapter.open_model
    native.fault = None
    native.setter_calls = []

    async def open_part(path):
        result = await original_open(path)
        model = native.adapter.currentModel
        dim = NS(
            Name=probe.DIMENSION,
            FullName=f"BodyDiaDim@BodyProfile@{Path(path).stem}.Part",
        )
        model.dimension = dim
        model.values = {
            "configuration": "Default",
            "dimensions": {
                "BodyDiaDim@BodyProfile": {
                    "value": 0.01,
                    "tolerance_type": 1,
                    "min": 0.0,
                    "max": 0.0,
                }
            },
        }
        text = {str(index): f"original {index}" for index in range(1, 9)}
        display = NS(ShowDimensionValue=True, IsHoleCallout=lambda: False)

        def get_text(index):
            if native.fault == "baseline_getter_dirty":
                model.dirty = True
            if native.fault == "baseline_getter_error":
                raise RuntimeError("native getter failure")
            return text[str(index)]

        def set_text(index, value):
            native.setter_calls.append((index, value))
            assert index == 1
            text["1"] = text["5"] = value
            model.dirty = True
            if native.fault == "setter_error":
                raise RuntimeError("native setter failure")
            if native.fault == "null_prefix":
                text["1"] = None
            if native.fault == "visibility":
                display.ShowDimensionValue = False
            if native.fault == "suffix":
                text["2"] = "mutated"
            if native.fault == "prefix_definition":
                text["5"] = "different native definition"
            if native.fault == "value":
                model.values["dimensions"]["BodyDiaDim@BodyProfile"]["value"] += 0.001
            if native.fault == "identity":
                model.dimension = NS(**vars(dim))
            if native.fault == "copy_saved":
                Path(path).write_bytes(b"unauthorized source save")
            if native.fault == "original_changed":
                native.source.write_bytes(b"unexpected original mutation")
            if native.fault == "runtime_changed":
                monkeypatch.setattr(
                    probe, "helper_fingerprints", lambda: {"prefix": "changed"}
                )
            return None

        display.GetText, display.SetText = get_text, set_text
        display.GetDimension2 = lambda _: dim
        model.display = display
        model.feature = NS(
            GetFirstDisplayDimension=lambda: display,
            GetNextDisplayDimension=lambda _: None,
        )
        model.GraphicsRedraw2 = Mock()
        native.model = model
        return result

    native.adapter.open_model = open_part
    monkeypatch.setattr(
        probe.marks,
        "_feature_by_name",
        lambda adapter, name: adapter.currentModel.feature,
    )
    monkeypatch.setattr(
        probe,
        "source_dimensions",
        lambda model, target, path: (
            deepcopy(model.values),
            {"BodyDiaDim@BodyProfile": model.dimension},
        ),
    )
    native.baseline = baseline
    native.helper = Mock(wraps=probe.prefix_control.set_dimension_prefix)
    monkeypatch.setattr(probe.prefix_control, "set_dimension_prefix", native.helper)
    return native


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "baseline_getter_dirty",
        "baseline_getter_error",
        "setter_error",
        "null_prefix",
        "visibility",
        "suffix",
        "prefix_definition",
        "value",
        "identity",
        "copy_saved",
        "original_changed",
        "runtime_changed",
    ],
)
def test_real_helper_owned_copy_and_every_refusal_preserve_baseline(
    scene, tmp_path, fault
):
    scene.fault = fault
    digest = probe.file_digest(scene.source)
    root = tmp_path / "reports"
    root.mkdir()

    async def run():
        return await owned.owned_callback(
            scene.adapter,
            lambda adapter: probe.probe(adapter, scene.source, digest, "a" * 40, root),
        )

    if fault:
        with pytest.raises(Exception):
            asyncio.run(run())
    else:
        asyncio.run(run())
    (path,) = root.glob("*/prefix.json")
    report = json.loads(path.read_text())
    assert report["status"] == ("failed" if fault else "passed")
    assert scene.app.documents == [scene.baseline]
    assert scene.baseline.dirty and scene.baseline.Visible
    assert scene.app.closes == [scene.model]
    assert scene.source not in map(Path, scene.adapter.opens)
    assert all(Path(value).parent == path.parent for value in scene.adapter.opens)
    assert not list(path.parent.glob("*.SLDDRW"))
    assert not list(path.parent.glob("*.pdf"))
    if fault not in ("copy_saved", "original_changed"):
        assert set(report["hashes"]["after_close"].values()) == {digest}
    if fault in ("baseline_getter_dirty", "baseline_getter_error"):
        scene.helper.assert_not_called()
        scene.model.GraphicsRedraw2.assert_not_called()
        return
    scene.helper.assert_called_once()
    assert scene.setter_calls == [(1, probe.PREFIX)]
    if fault:
        assert report["errors"]
        return
    assert report["helper_return"] is None
    scene.model.GraphicsRedraw2.assert_called_once_with()
    assert report["before"]["dirty_before_getters"] is False
    for phase in ("immediate", "after_redraw"):
        assert report[phase]["dirty_before_getters"] is True
        assert report[phase]["dirty_after_getters"] is True
        assert report[phase]["display"]["show_dimension_value"] is True
        assert report[phase]["source"] == report["before"]["source"]
        for key, value in report[phase]["display"]["text"].items():
            assert value == (probe.PREFIX if key in ("1", "5") else f"original {key}")


def test_unknown_original_sha_refuses_before_open(scene, tmp_path):
    with pytest.raises(Exception):
        asyncio.run(
            owned.owned_callback(
                scene.adapter,
                lambda adapter: probe.probe(
                    adapter, scene.source, "0" * 64, "a" * 40, tmp_path
                ),
            )
        )
    scene.helper.assert_not_called()
    assert not scene.adapter.opens and not scene.app.closes
    assert scene.app.documents == [scene.baseline]


def test_primary_setter_error_survives_cleanup_failure(scene, tmp_path):
    scene.fault = "setter_error"
    scene.app.CloseDoc = Mock(side_effect=RuntimeError("native cleanup failure"))
    with pytest.raises(ExceptionGroup) as caught:
        asyncio.run(
            owned.owned_callback(
                scene.adapter,
                lambda adapter: probe.probe(
                    adapter,
                    scene.source,
                    probe.file_digest(scene.source),
                    "a" * 40,
                    tmp_path,
                ),
            )
        )
    (path,) = tmp_path.glob("dimension-prefix-*/prefix.json")
    report = json.loads(path.read_text())
    assert "native setter failure" in report["errors"][0]
    assert "native cleanup failure" in report["cleanup_error"]
    assert report["hashes"]["after_close"]
    assert scene.baseline in scene.app.documents
    assert "prefix control" in str(caught.value.exceptions[0])


def test_getter_exception_and_lost_owner_are_both_retained(monkeypatch, tmp_path):
    before = Mock(side_effect=[False, RuntimeError("owner changed")])
    monkeypatch.setattr(probe, "current", before)
    monkeypatch.setattr(
        probe, "source_dimensions", Mock(side_effect=RuntimeError("getter failed"))
    )
    evidence = {}
    with pytest.raises(ExceptionGroup) as caught:
        probe.capture(object(), object(), tmp_path, evidence)
    assert [str(error) for error in caught.value.exceptions] == [
        "getter failed",
        "owner changed",
    ]
    assert "getter failed" in evidence["getter_error"]
    assert "owner changed" in evidence["getter_guard_error"]


@pytest.mark.parametrize(
    "damage", ["active", "current", "named", "kind", "path", "flag"]
)
def test_immediate_current_barrier_refuses_before_a_mutation(damage, tmp_path):
    model = NS(
        GetType=lambda: 1, GetPathName=lambda: str(tmp_path), GetSaveFlag=lambda: False
    )
    app = NS(
        ActiveDoc=model,
        GetOpenDocumentByName=lambda _: model,
        IsSame=lambda a, b: int(a is b),
    )
    adapter = NS(
        currentModel=model, swApp=app, ownership=NS(assert_current_owned=lambda: None)
    )
    if damage == "active":
        app.ActiveDoc = object()
    if damage == "current":
        adapter.currentModel = object()
    if damage == "named":
        app.GetOpenDocumentByName = lambda _: object()
    if damage == "kind":
        model.GetType = lambda: 3
    if damage == "path":
        model.GetPathName = lambda: str(tmp_path / "wrong")
    if damage == "flag":
        model.GetSaveFlag = lambda: 0
    with pytest.raises(RuntimeError):
        probe.current(adapter, model, tmp_path)


@pytest.mark.parametrize("value", [0, -1, True, 1.0, "1", None])
def test_native_identity_rejects_nonexact_one(value):
    with pytest.raises(RuntimeError):
        probe.same(NS(IsSame=lambda *_: value), object(), object(), "dimension")


def test_cli_parent_is_locked_and_forwards_exact_inputs(monkeypatch, tmp_path):
    import dodo

    source = tmp_path / "source.SLDPRT"
    source.write_bytes(b"part")
    monkeypatch.setenv("HARMONIC_SW_AUTOSTART", "0")
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "off")
    monkeypatch.setenv("HARMONIC_DIAGNOSTIC_SW_PID", "31860")
    monkeypatch.setattr(probe.benchmark, "revision", lambda _: "a" * 40)
    run = Mock()
    monkeypatch.setattr(dodo, "_run", run)
    assert probe.main(["--source", str(source), "--expected-sha256", "b" * 64]) == 0
    command = run.call_args.args[0]
    assert command[command.index("--candidate") + 1] == "a" * 40
    assert command[command.index("--source") + 1] == str(source.resolve())
    assert command[command.index("--expected-sha256") + 1] == "b" * 64
    assert "--worker" in command and run.call_args.kwargs["com"] is True


@pytest.mark.parametrize(
    "key,value",
    [
        ("HARMONIC_SW_AUTOSTART", "1"),
        ("HARMONIC_DIAGNOSTIC_SW_PID", ""),
        ("HARMONIC_REMOTE_CACHE_MODE", "rw"),
    ],
)
def test_cli_safety_contract_is_validated_before_parent_or_worker(
    monkeypatch, tmp_path, key, value
):
    monkeypatch.setenv("HARMONIC_SW_AUTOSTART", "0")
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "off")
    monkeypatch.setenv("HARMONIC_DIAGNOSTIC_SW_PID", "31860")
    monkeypatch.setenv(key, value)
    with pytest.raises((ValueError, RuntimeError)):
        probe.main(
            ["--source", str(tmp_path / "missing"), "--expected-sha256", "b" * 64]
        )


def test_cli_worker_runs_existing_owned_runner(monkeypatch, tmp_path):
    source = tmp_path / "source.SLDPRT"
    source.write_bytes(b"part")
    monkeypatch.setenv("HARMONIC_SW_AUTOSTART", "0")
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "off")
    monkeypatch.setenv("HARMONIC_DIAGNOSTIC_SW_PID", "31860")
    monkeypatch.setattr(probe.benchmark, "revision", lambda _: "a" * 40)
    adapter = object()
    calls = []

    async def operation(*args):
        calls.append(args)

    monkeypatch.setattr(probe, "probe", operation)
    monkeypatch.setattr(
        probe, "run_copy_diagnostic", lambda callback: asyncio.run(callback(adapter))
    )
    probe.main(
        [
            "--worker",
            "--source",
            str(source),
            "--expected-sha256",
            "b" * 64,
            "--report-root",
            str(tmp_path / "reports"),
        ]
    )
    assert calls == [
        (
            adapter,
            source.resolve(),
            "b" * 64,
            "a" * 40,
            (tmp_path / "reports").resolve(),
        )
    ]
