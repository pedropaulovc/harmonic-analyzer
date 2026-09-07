"""Selected-view import must prove actual view selection, never activation alone."""

from types import SimpleNamespace
from unittest.mock import Mock
import math

import pytest

from diagnostics import probe_selected_view_model_pmi as probe
from test_owned_native_documents_drawing import Model, native  # noqa: F401

ROTATIONS = {
    "*Front": (1, 0, 0, 0, 1, 0, 0, 0, 1),
    "*Top": (1, 0, 0, 0, 0, -1, 0, 1, 0),
    "*Right": (0, 0, -1, 0, 1, 0, 1, 0, 0),
}


def native_fixture(monkeypatch):
    monkeypatch.setattr(probe, "_early_bound", lambda value, _: value)
    monkeypatch.setattr(probe, "null_callout", lambda: None)
    view = Mock()
    view.GetName2.return_value = "Native View 17"
    model = Mock()
    model.ActivateView.return_value = True
    model.Extension.SelectByID2.return_value = True
    manager = model.SelectionManager
    manager.GetSelectedObjectCount2.return_value = 1
    manager.GetSelectedObjectType3.return_value = 12
    manager.GetSelectedObject6.return_value = view
    model.InsertModelAnnotations3.side_effect = [(Mock(), Mock()), (Mock(),)]
    adapter = SimpleNamespace(
        currentModel=model,
        swApp=SimpleNamespace(IsSame=lambda a, b: int(a is b)),
        ownership=SimpleNamespace(assert_current_owned=Mock()),
    )
    return adapter, view, model


def test_two_imports_reselect_exact_named_view_and_only_flip_all_views(monkeypatch):
    adapter, view, model = native_fixture(monkeypatch)
    rows = []
    returned = probe.selected_imports(adapter, view, rows, lambda: None)
    assert len(returned) == 3
    assert [call.args for call in model.Extension.SelectByID2.call_args_list] == [
        ("Native View 17", "DRAWINGVIEW", 0, 0, 0, False, 0, None, 0),
        ("Native View 17", "DRAWINGVIEW", 0, 0, 0, False, 0, None, 0),
    ]
    assert [call.args for call in model.InsertModelAnnotations3.call_args_list] == [
        (0, 32, False, True, False, True),
        (0, 2, False, True, False, True),
    ]
    assert model.SelectionManager.GetSelectedObject6.call_count == 2
    assert all(row["selection"]["identity"] == 1 for row in rows)


@pytest.mark.parametrize(
    "failure", ["name", "selection_false", "count", "type", "identity", "activation"]
)
def test_inexact_selection_stops_before_first_native_import(monkeypatch, failure):
    adapter, view, model = native_fixture(monkeypatch)
    if failure == "name":
        view.GetName2.return_value = ""
    if failure == "selection_false":
        model.Extension.SelectByID2.return_value = False
    if failure == "count":
        model.SelectionManager.GetSelectedObjectCount2.return_value = 2
    if failure == "type":
        model.SelectionManager.GetSelectedObjectType3.return_value = 14
    if failure == "identity":
        model.SelectionManager.GetSelectedObject6.return_value = object()
    if failure == "activation":
        model.ActivateView.return_value = False
    rows = []
    with pytest.raises(RuntimeError):
        probe.selected_imports(adapter, view, rows, lambda: None)
    model.InsertModelAnnotations3.assert_not_called()
    assert rows[0]["status"] == "failed"


def test_null_import_is_retained_as_missing_coverage_not_a_recreation(monkeypatch):
    adapter, view, model = native_fixture(monkeypatch)
    model.InsertModelAnnotations3.side_effect = [None, None]
    rows = []
    assert probe.selected_imports(adapter, view, rows, lambda: None) == []
    assert [row["returned_count"] for row in rows] == [0, 0]
    assert (
        len(probe.coverage_failures({"annotations": []}, "Native View 17", "initial"))
        == 3
    )


def test_second_selection_is_not_assumed_to_survive_first_import(monkeypatch):
    adapter, view, model = native_fixture(monkeypatch)
    model.SelectionManager.GetSelectedObject6.side_effect = [view, object()]
    with pytest.raises(RuntimeError, match="selection"):
        probe.selected_imports(adapter, view, [], lambda: None)
    assert model.InsertModelAnnotations3.call_count == 1


def test_import_and_selection_cleanup_errors_remain_in_order(monkeypatch):
    adapter, view, model = native_fixture(monkeypatch)
    model.InsertModelAnnotations3.side_effect = RuntimeError("import rejected")
    model.ClearSelection2.side_effect = [
        None,
        RuntimeError("selection cleanup rejected"),
    ]
    rows = []
    with pytest.raises(ExceptionGroup) as error:
        probe.selected_imports(adapter, view, rows, lambda: None)
    assert [str(item) for item in error.value.exceptions] == [
        "import rejected",
        "selection cleanup rejected",
    ]
    assert "import rejected" in rows[0]["error"]
    assert "selection cleanup rejected" in rows[0]["selection_cleanup_error"]


@pytest.mark.parametrize(
    "change", ["wrong_view", "part_owner", "duplicate", "hidden", "null_face"]
)
def test_selected_scope_cannot_pass_with_wrong_owner_or_incomplete_native_semantics(
    change,
):
    from test_native_model_pmi_import_drawing import valid_records

    records = valid_records()
    for row in records:
        row.update(view="Front", owner_type=0)
    if change == "wrong_view":
        records[0]["view"] = "Top"
    if change == "part_owner":
        records[0]["owner_type"] = 3
    if change == "duplicate":
        records.append(dict(records[0]))
    if change == "hidden":
        records[0]["visible"] = 3
    if change == "null_face":
        records[0]["null_entities"] = 1
    assert probe.coverage_failures({"annotations": records}, "Front", "initial")


@pytest.mark.parametrize(
    "returned", ["exact", "duplicate", "different", "missing", "null"]
)
def test_returned_array_matches_new_view_annotation_native_identities(returned):
    first, second, old = object(), object(), object()
    array = {
        "exact": [first, second],
        "duplicate": [first, first],
        "different": [first, object()],
        "missing": [first],
        "null": [first, None],
    }[returned]
    args = (
        SimpleNamespace(IsSame=lambda a, b: int(a is b)),
        array,
        {"old": {}},
        {"old": {}, "new1": {}, "new2": {}},
        {"old": (old,), "new1": (first,), "new2": (second,)},
    )
    if returned == "exact":
        probe.exact_returned_inventory(*args)
    else:
        with pytest.raises(RuntimeError):
            probe.exact_returned_inventory(*args)


@pytest.mark.parametrize("names", [[], ["Front", "Duplicate"], ["Front"]])
def test_front_resolved_from_unique_native_orientation_not_view_order(names):
    handles = {name: object() for name in names}
    rows = {
        name: {"orientation": "*Front", "rotation": ROTATIONS["*Front"]}
        for name in names
    }
    if len(names) == 1:
        assert (
            probe.orientation_view(handles, rows, "*Front", ROTATIONS)
            is handles["Front"]
        )
    else:
        with pytest.raises(RuntimeError, match="not unique"):
            probe.orientation_view(handles, rows, "*Front", ROTATIONS)


@pytest.mark.parametrize("orientation", ["*Front", "*Top", "*Right"])
def test_explicit_orientation_selects_native_view_not_array_position(orientation):
    rows = {
        "Arbitrary 31": {"orientation": "", "rotation": ROTATIONS["*Right"]},
        "Arbitrary 17": {"orientation": "*Front", "rotation": ROTATIONS["*Front"]},
        "Arbitrary 2": {"orientation": "", "rotation": ROTATIONS["*Top"]},
    }
    handles = {name: object() for name in rows}
    expected = next(
        name for name, row in rows.items() if row["rotation"] == ROTATIONS[orientation]
    )
    assert (
        probe.orientation_view(handles, rows, orientation, ROTATIONS)
        is handles[expected]
    )


def test_unknown_orientation_does_not_guess_an_available_view():
    with pytest.raises(ValueError, match="unsupported"):
        probe.orientation_view(
            {"Front": object()},
            {"Front": {"orientation": "*Front"}},
            "Front",
            ROTATIONS,
        )


@pytest.mark.parametrize("invalid", [(1,) * 8, (float("nan"),) * 9, (0,) * 9])
def test_malformed_native_rotation_is_rejected(invalid):
    with pytest.raises(RuntimeError, match="rotation"):
        probe.rotation_values(invalid)


def test_projected_selection_requires_front_matrix_positive_control():
    rows = {"Front": {"orientation": "*Front", "rotation": ROTATIONS["*Top"]}}
    with pytest.raises(RuntimeError, match="standard Front"):
        probe.orientation_view({"Front": object()}, rows, "*Right", ROTATIONS)


def test_duplicate_projected_rotations_are_not_disambiguated_by_position():
    rows = {
        "Front": {"orientation": "*Front", "rotation": ROTATIONS["*Front"]},
        "First": {"orientation": "", "rotation": ROTATIONS["*Right"]},
        "Second": {"orientation": "", "rotation": ROTATIONS["*Right"]},
    }
    with pytest.raises(RuntimeError, match="not unique"):
        probe.orientation_view(
            {name: object() for name in rows}, rows, "*Right", ROTATIONS
        )


def test_parent_forwards_explicit_orientation_to_native_worker(tmp_path, monkeypatch):
    import sys

    source = tmp_path / "transgear-stub.SLDPRT"
    source.write_bytes(b"pinned source")
    monkeypatch.setenv("HARMONIC_DIAGNOSTIC_SW_PID", "123")
    monkeypatch.setenv("HARMONIC_SW_AUTOSTART", "0")
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "off")
    native_parent = Mock()
    monkeypatch.setitem(sys.modules, "dodo", SimpleNamespace(_run=native_parent))
    assert (
        probe.main([str(source), "--expected-pid", "123", "--orientation", "*Right"])
        == 0
    )
    command = native_parent.call_args.args[0]
    assert command[command.index("--orientation") + 1] == "*Right"
    assert native_parent.call_args.kwargs["com"] is True


@pytest.mark.parametrize("failure", ["pid_missing", "autostart", "remote"])
def test_parent_environment_fails_before_native_wrapper(tmp_path, monkeypatch, failure):
    import sys

    monkeypatch.setenv("HARMONIC_DIAGNOSTIC_SW_PID", "123")
    monkeypatch.setenv("HARMONIC_SW_AUTOSTART", "0")
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "off")
    if failure == "pid_missing":
        monkeypatch.delenv("HARMONIC_DIAGNOSTIC_SW_PID")
    if failure == "autostart":
        monkeypatch.setenv("HARMONIC_SW_AUTOSTART", "1")
    if failure == "remote":
        monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "rw")
    native_parent = Mock(side_effect=AssertionError("native parent must not run"))
    monkeypatch.setitem(sys.modules, "dodo", SimpleNamespace(_run=native_parent))
    with pytest.raises(RuntimeError):
        probe.main([str(tmp_path / "not-even-opened.SLDPRT"), "--expected-pid", "123"])
    native_parent.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("arrangement", [None, *tuple(probe.PmiArrangement)])
@pytest.mark.parametrize(
    "mode",
    [
        "passed",
        "missing_pmi",
        "cold_title",
        "copy_saved",
        "view_creation_failed",
        "cold_source_roundoff",
        "live_source_roundoff",
        "reopened_export_source_roundoff",
        "reopened_export_source_identity",
    ],
)
async def test_owned_control_exports_failures_but_never_saves_original_or_ignores_copy_drift(
    native,  # noqa: F811 - imported pytest fixture
    tmp_path,
    monkeypatch,
    mode,  # noqa: F811
    arrangement,
):
    from copy import deepcopy
    from pathlib import Path
    import json
    from diagnostics._owned_native_documents import owned_callback
    from test_native_model_pmi_import_drawing import valid_records

    source, template = tmp_path / "source.SLDPRT", tmp_path / "drawing.DRWDOT"
    source.write_bytes(b"unchanged source")
    template.write_bytes(b"unchanged template")
    original, existing_draw = (
        Model(source, kind=1),
        Model(None, title="Draw2 - Sheet1", dirty=True),
    )
    native.app.documents.extend((original, existing_draw))
    native.app.ActiveDoc = existing_draw
    native.app.GetProcessID = lambda: 123
    native.app.GetUserPreferenceStringValue = lambda _: str(template)
    monkeypatch.setattr(probe, "require_environment", lambda _: None)
    monkeypatch.setattr(probe, "_early_bound", lambda value, _: value)
    monkeypatch.setattr(probe.pilot.benchmark, "revision", lambda _: "frozen")
    monkeypatch.setattr(probe.pilot, "helper_fingerprints", lambda: {"helper": "same"})
    monkeypatch.setattr(
        probe.pilot, "adapter_fingerprints", lambda: {"adapter": "same"}
    )
    source_records = valid_records()
    for row in source_records:
        row["position_m"] = tuple(float(value) for value in row["position_m"])
    source_reads = []

    def read_source(_app, model):
        source_reads.append(model)
        rows = deepcopy(source_records)
        if mode == "live_source_roundoff" and len(source_reads) > 1:
            rows[0]["position_m"] = (math.nextafter(0.1, math.inf), 0.1, 0.0)
        if (
            mode in {"cold_source_roundoff", "reopened_export_source_roundoff"}
            and model is not source_reads[0]
        ):
            value = math.nextafter(0.1, math.inf)
            if mode == "reopened_export_source_roundoff" and phase.get("cold_exported"):
                value = math.nextafter(value, math.inf)
            rows[0]["position_m"] = (value, 0.1, 0.0)
        return rows

    monkeypatch.setattr(probe.pmi, "source_snapshot", read_source)
    dimensions = {
        "configuration": "Default",
        "features": ["StubProfile"],
        "dimensions": {"D": {"native": {"value": 0.01}, "displays": []}},
    }
    monkeypatch.setattr(
        probe,
        "dimension_snapshot",
        lambda app, model, path, required: (
            deepcopy(dimensions),
            {
                "D": object()
                if mode == "reopened_export_source_identity"
                and phase.get("cold_exported")
                else model
            },
        ),
    )
    records = deepcopy(source_records)
    view_label = "Front" if arrangement is None else "Right"
    for row in records:
        row.update(view=view_label, owner_type=0)
    if mode == "missing_pmi":
        records.pop()
    items = {row["name"]: object() for row in records}
    selected = SimpleNamespace(GetName2=lambda: view_label)
    view_handles = {
        name: selected if name == view_label else object()
        for name in ("Front", "Top", "Right")
    }
    phase = {"imported": False}

    def captured(adapter, copy, configuration, source_model):
        native_records = records if phase["imported"] else []
        rows = (
            {
                name: {
                    "semantic": {"label": name},
                    "generic": {},
                    "position": (0.1, 0.1, 0),
                }
                for name in items
            }
            if phase["imported"]
            else {}
        )
        view_rows = {
            name: {
                "orientation": "*Front" if name == "Front" else "",
                "rotation": ROTATIONS[f"*{name}"],
                "source": str(copy),
                "configuration": configuration,
            }
            for name in view_handles
        }
        return (
            {
                "pmi": {"annotations": deepcopy(native_records)},
                "views": view_rows,
                "layout": {},
                "annotations": rows,
            },
            view_handles,
            {name: (items[name],) for name in rows},
        )

    monkeypatch.setattr(probe, "snapshot", captured)

    def importing(adapter, view, rows, checkpoint):
        assert view is selected
        adapter.ownership.assert_current_owned()
        phase["imported"] = True
        rows.append({"count": len(items)})
        return list(items.values())

    monkeypatch.setattr(probe, "selected_imports", importing)
    spacing = Mock()
    spacing_comparison = Mock(
        return_value={
            "movement": "measured by focused tests",
            "body_gaps": [],
            "failures": [],
        }
    )
    monkeypatch.setattr(probe, "space_imported_pmi", spacing)
    monkeypatch.setattr(probe, "compare_arranged_pmi", spacing_comparison)
    monkeypatch.setattr(
        probe,
        "compare_reopened_annotations",
        lambda before, after: {
            "status": "failed" if mode == "cold_title" else "passed",
            "rejected": ["title moved"] if mode == "cold_title" else [],
        },
    )
    references = {}
    initial_open = native.adapter.open_model

    async def opening(path):
        result = await initial_open(path)
        native.adapter.currentModel.GetStandardViewRotation = lambda view_id: ROTATIONS[
            {1: "*Front", 4: "*Right", 5: "*Top"}[view_id]
        ]
        if Path(path).suffix.upper() == ".SLDDRW":
            part = Model(references[path], kind=1)
            native.app.documents.append(part)
            native.adapter.currentModel.references = [part]
        return result

    native.adapter.open_model = opening

    def create(adapter, *, template):
        part = adapter.currentModel
        assert part is not original and part.path != str(source)
        drawing = Model(None, title="Owned PMI", dirty=True)
        drawing.references = [part]

        def create_views(path):
            # Observed native transition, including a rejection after rename.
            drawing.title = Path(path).stem + " - Sheet1"
            return path == part.path and mode != "view_creation_failed"

        drawing.Create3rdAngleViews2 = create_views
        native.app.documents.append(drawing)
        native.app.ActiveDoc = drawing
        adapter.currentModel = drawing

    monkeypatch.setattr(probe.native_drawing, "new_drawing", create)

    def save(adapter, path, *, pdf_path):
        drawing = adapter.currentModel
        with adapter.ownership.saving_as(path):
            drawing.path, drawing.title, drawing.dirty = path, Path(path).name, False
            Path(path).write_bytes(b"native saved drawing")
        part = drawing.references[0]
        references[path] = part.path
        if mode == "copy_saved":
            Path(part.path).write_bytes(b"unintended native source save")
        Path(pdf_path).write_bytes(b"pdf")

    monkeypatch.setattr(probe, "save_drawing", save)

    def export_cold(adapter, path):
        phase["cold_exported"] = True
        path.write_bytes(b"cold pdf")

    monkeypatch.setattr(probe.retained, "export_pdf_only", export_cold)
    monkeypatch.setattr(
        probe.pmi, "render_pdf_png", lambda pdf, png: png.write_bytes(b"png")
    )

    def callback(adapter):
        return probe.probe(
            adapter,
            source,
            tmp_path / "reports",
            123,
            probe.pmi.file_digest(source),
            orientation="*" + view_label,
            arrangement=arrangement,
        )

    expected_status = (
        "passed" if mode in {"passed", "cold_source_roundoff"} else "failed"
    )
    if expected_status == "passed":
        await owned_callback(native.adapter, callback)
    else:
        with pytest.raises((RuntimeError, ExceptionGroup)):
            await owned_callback(native.adapter, callback)
    assert native.app.documents == [original, existing_draw]
    assert not original.dirty and existing_draw.dirty
    assert all(str(source) != str(path) for path in native.adapter.opens)
    assert original not in native.app.closes and existing_draw not in native.app.closes
    assert source.read_bytes() == b"unchanged source"
    assert template.read_bytes() == b"unchanged template"
    (receipt,) = (tmp_path / "reports").glob("*/observations.json")
    report = json.loads(receipt.read_text())
    assert report["status"] == expected_status
    assert report["inputs_before"] == report["inputs_after"]
    assert report["visual_review"] == "pending"
    if arrangement is not None:
        assert f"one native {probe.PMI_SPACING_COMMANDS[arrangement]} spacing command" in report["scope"]
    if arrangement is None or mode in {
        "missing_pmi",
        "view_creation_failed",
        "live_source_roundoff",
    }:
        spacing.assert_not_called()
        spacing_comparison.assert_not_called()
    else:
        spacing.assert_called_once()
        spacing_comparison.assert_called_once()
        assert "source_after_arrangement" in report
        assert (
            report["source_before"]["dimensions"]
            == report["source_after_arrangement"]["dimensions"]
        )
        assert report["requested_arrangement"] == arrangement.value
        assert spacing.call_args.kwargs == {"arrangement": arrangement}
    if mode in {"cold_source_roundoff", "reopened_export_source_roundoff"}:
        cold = report["source_reopened"]["pmi_comparison"]
        live = report["source_after_reopened_export"]["pmi_comparison"]
        assert cold["boundary"] == "cold_reopen" and cold["status"] == "passed"
        assert len(cold["coordinate_roundoff"]) == 1
        assert live["boundary"] == "same_session" and live["coordinate_roundoff"] == []
        assert live["status"] == expected_status
    if mode == "reopened_export_source_identity":
        assert "source native dimension identity changed" in report["operation_error"]
        assert (
            report["source_after_reopened_export"]["pmi_comparison"]["status"]
            == "passed"
        )
    if mode == "view_creation_failed":
        assert not report["artifacts"] and not report["imports"]
        assert "third-angle views rejected" in report["operation_error"]
        assert "cleanup_error" not in report
        return
    if arrangement is not None and mode == "missing_pmi":
        assert not report["artifacts"]
        assert "requires complete initial coverage" in report["operation_error"]
        return
    if mode == "live_source_roundoff":
        assert not report["artifacts"]
        comparison = report["source_after_import"]["pmi_comparison"]
        assert comparison["status"] == "failed"
        assert comparison["boundary"] == "same_session"
        assert not comparison["coordinate_roundoff"]
        return
    assert "initial" in report["artifacts"]
    if mode != "copy_saved":
        assert "reopened" in report["artifacts"]
        assert report["copy_after"][report["copy"]] == probe.pmi.file_digest(source)
    if mode == "missing_pmi":
        assert any("coverage" in failure for failure in report["failures"])
    if mode == "cold_title":
        assert report["cold_comparison"]["status"] == "failed"
    if mode == "copy_saved":
        assert "copy_guard_error" in report


@pytest.mark.parametrize(
    "failure",
    ["none", "source_path", "configuration", "source_identity", "duplicate_view_name"],
)
def test_native_view_inventory_keeps_exact_source_and_configuration(
    tmp_path, monkeypatch, failure
):
    monkeypatch.setattr(probe, "_early_bound", lambda value, _: value)
    path = tmp_path / "copy.SLDPRT"
    source = SimpleNamespace(GetPathName=lambda: str(path))
    referenced = (
        SimpleNamespace(GetPathName=lambda: str(path))
        if failure == "source_identity"
        else source
    )
    if failure == "source_path":
        source.GetPathName = lambda: str(tmp_path / "original.SLDPRT")
    names = (
        ["Front", "Top", "Right"] if failure != "duplicate_view_name" else ["Front"] * 3
    )
    views = [
        SimpleNamespace(
            GetName2=lambda name=name: name,
            ReferencedDocument=referenced,
            ReferencedConfiguration="Wrong"
            if failure == "configuration"
            else "Default",
            GetOrientationName=lambda: "*Front",
            ModelToViewTransform=SimpleNamespace(
                ArrayData=(*ROTATIONS[f"*{name}"], 0, 0, 0, 1, 0, 0, 0)
            ),
        )
        for name in names
    ]
    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(GetViews=lambda: [(object(), *views)]),
        swApp=SimpleNamespace(IsSame=lambda a, b: int(a is b)),
    )
    if failure == "none":
        handles, rows = probe.native_views(adapter, path, "Default", source)
        assert len(handles) == len(rows) == 3
        assert all(row["source_identity"] == 1 for row in rows.values())
    else:
        with pytest.raises(RuntimeError):
            probe.native_views(adapter, path, "Default", source)


def test_selected_probe_has_no_geometry_picks_layout_setters_or_global_cleanup():
    import ast
    from pathlib import Path

    tree = ast.parse(Path(probe.__file__).read_text())
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    attributes = {
        node.func.attr for node in calls if isinstance(node.func, ast.Attribute)
    }
    assert not attributes & {
        "CloseAllDocuments",
        "SetPosition2",
        "SetSelectionPoint2",
        "SetAttachedEntities",
        "InsertGtol",
        "InsertDatumTag2",
        "SetLeader3",
        "SetUserPreferenceToggle",
        "ForceRebuild3",
        "EditRebuild3",
    }
    picks = [
        node
        for node in calls
        if isinstance(node.func, ast.Attribute) and node.func.attr == "SelectByID2"
    ]
    assert len(picks) == 1 and picks[0].args[1].value == "DRAWINGVIEW"
    assert [node.value for node in picks[0].args[2:5]] == [0, 0, 0]
