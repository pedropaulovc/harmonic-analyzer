"""First dirty transition stops the unchanged recipe, even through _attempt."""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from diagnostics import probe_source_dirty_recipe as probe
from diagnostics import _owned_native_documents as owned
from test_owned_native_documents_drawing import Model, native  # noqa: F401


def monitor(tmp_path, monkeypatch):
    model = SimpleNamespace(dirty=False)
    model.GetSaveFlag = lambda: model.dirty
    model.GetPathName = lambda: str(tmp_path / "owned.SLDPRT")
    model.GetType = lambda: 1
    app = SimpleNamespace(
        GetOpenDocumentByName=lambda _: model, IsSame=lambda a, b: int(a is b)
    )
    snapshots = []

    def snapshot(*_):
        snapshots.append(model.dirty)
        return {"dimensions": {"Width": {"value": 0.024, "basic": 1}}}, {"Width": model}

    monkeypatch.setattr(probe, "dimension_snapshot", snapshot)
    report = {"events": []}
    guard = probe.DirtyMonitor(
        app, model, Path(model.GetPathName()), report, lambda: None
    )
    return guard, model, snapshots


def test_first_nested_transition_stops_outer_attempt_and_later_operations(
    tmp_path, monkeypatch
):
    guard, model, snapshots = monitor(tmp_path, monkeypatch)
    guard.baseline()
    later = Mock()

    def import_dimensions():
        model.dirty = True

    imported = guard.wrap("nested.insert_marked_dimensions", import_dimensions)

    def attempted():
        try:
            imported()
        except Exception:
            later()
        later()

    with pytest.raises(probe.DiagnosticStop):
        guard.wrap("recipe.retain_view_dimensions", attempted)()
    later.assert_not_called()
    assert snapshots == [False, True]
    assert guard.report["stop"]["boundary"] == "nested.insert_marked_dimensions"
    assert guard.report["stop"]["phase"] == "after"
    assert guard.report["stop"]["dimension_identity"] == {"Width": "same"}


def test_failed_transition_readback_still_cannot_be_swallowed_by_attempt(
    tmp_path, monkeypatch
):
    guard, model, _ = monitor(tmp_path, monkeypatch)
    guard.baseline()
    later = Mock()

    def broken_readback(*_):
        raise RuntimeError("readback failed")

    monkeypatch.setattr(probe, "dimension_snapshot", broken_readback)

    def changes():
        model.dirty = True

    wrapped = guard.wrap("nested.changed", changes)
    with pytest.raises(probe.DiagnosticStop):
        try:
            wrapped()
        except Exception:
            later()
        later()
    later.assert_not_called()
    assert "readback failed" in guard.report["stop"]["capture_error"]


def test_baseline_readback_that_dirties_copy_is_not_blame_on_recipe(
    tmp_path, monkeypatch
):
    guard, model, _ = monitor(tmp_path, monkeypatch)

    def snapshot(*_):
        model.dirty = True
        return {}, {}

    monkeypatch.setattr(probe, "dimension_snapshot", snapshot)
    with pytest.raises(probe.DiagnosticStop):
        guard.baseline()
    assert guard.report["stop"]["boundary"] == "baseline_dimension_snapshot"
    assert guard.report["baseline_save_flag"] == {"before": False, "after": True}


def test_source_already_dirty_stops_before_operation(tmp_path, monkeypatch):
    guard, model, _ = monitor(tmp_path, monkeypatch)
    guard.baseline()
    model.dirty = True
    operation = Mock()
    with pytest.raises(probe.DiagnosticStop):
        guard.wrap("recipe.next", operation)()
    operation.assert_not_called()
    assert guard.report["stop"]["phase"] == "before"


def test_async_boundary_does_not_swallow_abort(tmp_path, monkeypatch):
    guard, model, _ = monitor(tmp_path, monkeypatch)
    guard.baseline()

    async def operation():
        model.dirty = True

    with pytest.raises(probe.DiagnosticStop):
        asyncio.run(guard.wrap("adapter.open_model", operation)())
    assert guard.report["stop"]["boundary"] == "adapter.open_model"


def test_native_identity_change_fails_even_if_same_path_and_clean(
    tmp_path, monkeypatch
):
    guard, _, _ = monitor(tmp_path, monkeypatch)
    guard.baseline()
    guard.app.GetOpenDocumentByName = lambda _: object()
    with pytest.raises(probe.DiagnosticStop):
        guard.wrap("recipe.next", Mock())()
    assert "identity" in guard.report["stop"]["capture_error"]


def test_finalization_is_never_called_when_no_dirty_transition(tmp_path, monkeypatch):
    guard, _, _ = monitor(tmp_path, monkeypatch)
    guard.baseline()
    with pytest.raises(probe.DiagnosticStop):
        asyncio.run(guard.stop_before_finalize(None))
    assert guard.report["stop"]["reason"] == "clean_before_finalize"


def test_instrumented_functions_are_restored_on_early_abort(tmp_path, monkeypatch):
    guard, _, _ = monitor(tmp_path, monkeypatch)

    def original():
        return None

    module = SimpleNamespace(
        read_required_properties=original, finalize_drawing=original
    )
    with pytest.raises(probe.DiagnosticStop):
        with probe.instrument_recipe(module, guard):
            assert module.read_required_properties is not original
            raise probe.DiagnosticStop()
    assert module.read_required_properties is original
    assert module.finalize_drawing is original


def test_outer_environment_is_checked_before_parent_dodo(monkeypatch, tmp_path):
    monkeypatch.setenv("HARMONIC_SW_AUTOSTART", "1")
    with pytest.raises(RuntimeError, match="AUTOSTART=0"):
        probe.main(
            ["--source", str(tmp_path / "source.SLDPRT"), "--expected-sha256", "a" * 64]
        )


@pytest.mark.parametrize(
    "mode", ["dirty", "clean", "snapshot_failure", "source_disk_change"]
)
def test_real_owned_copy_cleanup_preserves_baseline_and_never_saves(
    native,  # noqa: F811 - imported pytest fixture
    tmp_path,
    monkeypatch,
    mode,
):
    import json
    import _drawing_common as common

    baseline = Model(None, title="Draw2 - Sheet1", dirty=True)
    native.app.documents.append(baseline)
    native.app.ActiveDoc = baseline
    original_hash = probe.file_digest(native.source)
    monkeypatch.setattr(probe.benchmark, "revision", lambda _: "pinned")
    monkeypatch.setattr(probe, "helper_fingerprints", lambda: {"helper": "same"})
    monkeypatch.setattr(probe, "adapter_fingerprints", lambda: {"package": "same"})
    monkeypatch.setattr(probe, "_early_bound", lambda value, _: value)

    def snapshot(app, model, path):
        if mode == "snapshot_failure" and model.dirty:
            raise RuntimeError("native dimension readback failed")
        return {"dimensions": {"Width": {"native": "same"}}}, {"Width": model}

    monkeypatch.setattr(probe, "dimension_snapshot", snapshot)
    touched = []

    def blank(adapter):
        drawing = Model(None, title="Owned new drawing", dirty=True)
        native.app.documents.append(drawing)
        native.app.ActiveDoc = drawing
        adapter.currentModel = drawing
        touched.append("blank")
        return drawing

    def place(adapter, source):
        touched.append("view")
        adapter.currentModel.references = [native.app.GetOpenDocumentByName(source)]

    def callouts(adapter, source):
        touched.append("callouts")
        if mode != "clean":
            native.app.GetOpenDocumentByName(source).dirty = True
        if mode == "source_disk_change":
            native.source.write_bytes(b"corrupted original fixture")

    monkeypatch.setattr(common, "new_project_drawing", blank)
    monkeypatch.setattr(common, "set_dimension_callouts", callouts)
    monkeypatch.setattr(common, "read_required_properties", place)
    code = """from pathlib import Path
from _drawing_common import new_project_drawing, read_required_properties, set_dimension_callouts, finalize_drawing
SOURCE = Path("incorrect original; redirected before execution")
OUTPUTS = None
async def build(adapter):
    await adapter.open_model(str(SOURCE))
    new_project_drawing(adapter)
    read_required_properties(adapter, str(SOURCE))
    set_dimension_callouts(adapter, str(SOURCE))
    return await finalize_drawing(adapter, OUTPUTS)
"""
    monkeypatch.setattr(probe.benchmark, "recipe_source", lambda *_: code)
    reports = tmp_path / "reports"

    async def run():
        return await owned.owned_callback(
            native.adapter,
            lambda adapter: probe.probe(
                adapter, native.source, original_hash, "pinned", reports
            ),
        )

    if mode in {"snapshot_failure", "source_disk_change"}:
        with pytest.raises(Exception):
            asyncio.run(run())
    else:
        asyncio.run(run())
    (receipt,) = reports.glob("*/source-dirty.json")
    report = json.loads(receipt.read_text())
    assert native.app.documents == [baseline]
    assert (
        baseline.dirty and baseline.Visible and baseline.GetTitle() == "Draw2 - Sheet1"
    )
    assert native.app.closes and all(item is not baseline for item in native.app.closes)
    assert all(Path(path).parent == receipt.parent for path in native.adapter.opens)
    assert native.source not in [Path(path) for path in native.adapter.opens]
    assert report["copy_after"] == original_hash
    assert not list(receipt.parent.glob("*.SLDDRW"))
    assert not list(receipt.parent.glob("*.pdf"))
    assert not list(receipt.parent.glob("*.png"))
    assert touched == ["blank", "view", "callouts"]
    if mode == "source_disk_change":
        assert report["original_after"] != original_hash
        return
    assert report["original_after"] == original_hash
    if mode == "dirty":
        assert report["stop"]["boundary"] == "recipe.set_dimension_callouts"


@pytest.mark.parametrize(
    "variant",
    [
        "normal",
        "chamfer",
        "hole_callout",
        "duplicate_identity",
        "missing_required",
        "wrong_owner",
        "nonfinite",
    ],
)
def test_complete_observed_dimension_inventory_includes_unmarked_and_chamfer_values(
    tmp_path, monkeypatch, variant
):
    monkeypatch.setattr(probe, "_early_bound", lambda value, _: value)
    monkeypatch.setattr(
        probe, "_read_member", lambda value, name: getattr(value, name)()
    )
    monkeypatch.setattr(probe, "DRAWING_DIMENSIONS", {"FootProfile": {"Width"}})
    path = tmp_path / "owned-part.SLDPRT"

    def dimension(name):
        return SimpleNamespace(
            FullName=f"{name}@{path.stem if variant != 'wrong_owner' else 'Other'}.Part",
            Tolerance=SimpleNamespace(
                Type=1, GetMinValue=lambda: 0.0, GetMaxValue=lambda: 0.0
            ),
            GetToleranceType=lambda: 1,
            GetSystemValue3=lambda *_: (
                float("nan") if variant == "nonfinite" else 0.024,
            ),
        )

    width = dimension(
        "Wrong@FootProfile" if variant == "missing_required" else "Width@FootProfile"
    )
    unmarked = dimension("D1@UnmarkedSketch")
    angle = dimension("D2@Chamfer")
    text = Mock(return_value="native text")

    def display(dims, marked):
        return SimpleNamespace(
            Type2=10 if len(dims) == 2 else 2,
            GetDimension2=lambda index: dims[index],
            MarkedForDrawing=marked,
            GetPrimaryPrecision2=lambda: 3,
            GetPrimaryTolPrecision2=lambda: 2,
            IsHoleCallout=lambda: variant == "hole_callout",
            GetText=text,
        )

    displays = [
        display([width], True),
        display([unmarked, angle] if variant == "chamfer" else [unmarked], False),
    ]
    if variant == "duplicate_identity":
        displays.append(display([dimension("Width@FootProfile")], True))

    feature = SimpleNamespace(
        Name=lambda: "FootProfile",
        GetFirstDisplayDimension=lambda: displays[0],
        GetNextDisplayDimension=lambda item: (
            displays[displays.index(item) + 1]
            if displays.index(item) + 1 < len(displays)
            else None
        ),
    )
    monkeypatch.setattr(probe, "_iter_features", lambda _: (feature,))
    model = SimpleNamespace(
        ConfigurationManager=SimpleNamespace(
            ActiveConfiguration=SimpleNamespace(Name="Default")
        )
    )
    app = SimpleNamespace(IsSame=lambda a, b: int(a is b))
    if variant in {
        "duplicate_identity",
        "missing_required",
        "wrong_owner",
        "nonfinite",
    }:
        with pytest.raises(RuntimeError):
            probe.dimension_snapshot(app, model, path)
        return
    actual, handles = probe.dimension_snapshot(app, model, path)
    assert (
        len(actual["dimensions"]) == len(handles) == (3 if variant == "chamfer" else 2)
    )
    assert handles[unmarked.FullName] is unmarked
    row = actual["dimensions"][unmarked.FullName]
    assert row["native"]["tolerance_type"] == 1
    assert row["displays"][0]["marked_for_drawing"] is False
    if variant == "hole_callout":
        text.assert_not_called()


def test_operation_error_that_dirties_part_records_error_and_aborts(
    tmp_path, monkeypatch
):
    guard, model, _ = monitor(tmp_path, monkeypatch)
    guard.baseline()

    def operation():
        model.dirty = True
        raise RuntimeError("native operation failed")

    with pytest.raises(probe.DiagnosticStop):
        guard.wrap("recipe.failed_callout", operation)()
    assert guard.report["stop"]["phase"] == "after_error"
    assert "native operation failed" in guard.report["stop"]["operation_error"]
