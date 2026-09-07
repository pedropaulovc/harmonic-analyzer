"""One native imported-PMI command, with no new layout solver or gate bypass."""

from copy import deepcopy
from types import SimpleNamespace as NS
from unittest.mock import Mock
import sys

import pytest

from diagnostics import probe_selected_view_model_pmi as probe
from test_native_model_pmi_import_drawing import valid_records


@pytest.fixture
def bank(monkeypatch):
    monkeypatch.setattr(probe, "_early_bound", lambda value, _: value)
    view, selected = NS(GetName2=lambda: "Right"), []
    annotations = []
    for index, kind in enumerate((5, 5, 2)):
        annotation = NS(
            GetType=lambda kind=kind: kind,
            OwnerType=0,
            Owner=view,
            GetName=lambda index=index: f"PMI{index}",
        )
        annotation.Select2 = Mock(
            side_effect=lambda append, mark, annotation=annotation: (
                selected.append(annotation) or True
            )
        )
        annotations.append(annotation)
    model = NS(
        ActivateView=Mock(return_value=True),
        ClearSelection2=Mock(side_effect=lambda _: selected.clear()),
    )
    model.SelectionManager = NS(
        GetSelectedObjectCount2=lambda _: len(selected),
        GetSelectedObjectType3=lambda index, _: (
            36 if selected[index - 1].GetType() == 2 else 13
        ),
        GetSelectedObject6=lambda index, _: NS(
            GetAnnotation=lambda: selected[index - 1]
        ),
        GetSelectedObjectsDrawingView2=lambda *_: None,
    )
    app = NS(
        IsSame=lambda a, b: int(a is b),
        IsCommandEnabled=Mock(return_value=True),
        RunCommand=Mock(return_value=True),
    )
    adapter = NS(
        currentModel=model, swApp=app, ownership=NS(assert_current_owned=Mock())
    )
    return adapter, view, annotations, selected


def test_native_command_is_only317_exact_three_types_identity_and_cleanup(bank):
    adapter, view, annotations, selected = bank
    row = {}
    probe.space_imported_pmi(
        adapter,
        view,
        annotations,
        row,
        lambda: None,
        arrangement=probe.PmiArrangement.SPACE_TIGHTLY_DOWN,
    )
    adapter.swApp.RunCommand.assert_called_once_with(317, "")
    adapter.swApp.IsCommandEnabled.assert_called_once_with(317)
    assert [item["type"] for item in row["selections"]] == [13, 13, 36]
    assert all(item["identity"] == 1 for item in row["selections"])
    assert row["command_seconds"] >= 0 and row["returned"]
    assert selected == []
    assert adapter.currentModel.ClearSelection2.call_count == 2
    for annotation in annotations:
        annotation.Select2.assert_called_once_with(True, 0)


def test_even_spacing_replaces317_with_one313_call_on_the_same_exact_bank(bank):
    adapter, view, annotations, selected = bank
    row = {}
    probe.space_imported_pmi(
        adapter,
        view,
        annotations,
        row,
        lambda: None,
        arrangement=probe.PmiArrangement.SPACE_EVENLY_DOWN,
    )
    adapter.swApp.IsCommandEnabled.assert_called_once_with(313)
    adapter.swApp.RunCommand.assert_called_once_with(313, "")
    assert row["command"] == 313
    assert [item["type"] for item in row["selections"]] == [13, 13, 36]
    assert all(item["identity"] == 1 for item in row["selections"])
    assert selected == []
    assert adapter.currentModel.ClearSelection2.call_count == 2
    for annotation in annotations:
        annotation.Select2.assert_called_once_with(True, 0)


def test_autoarrange_uses_one2976_call_without_first_running313_or317(bank):
    adapter, view, annotations, selected = bank
    row = {}
    probe.space_imported_pmi(
        adapter,
        view,
        annotations,
        row,
        lambda: None,
        arrangement=probe.PmiArrangement.AUTO_ARRANGE,
    )
    adapter.swApp.IsCommandEnabled.assert_called_once_with(2976)
    adapter.swApp.RunCommand.assert_called_once_with(2976, "")
    assert row["command"] == 2976
    assert [item["type"] for item in row["selections"]] == [13, 13, 36]
    assert all(item["identity"] == 1 for item in row["selections"])
    assert selected == []
    assert adapter.currentModel.ClearSelection2.call_count == 2
    for annotation in annotations:
        annotation.Select2.assert_called_once_with(True, 0)


@pytest.mark.parametrize(
    "mode",
    [
        "empty",
        "two",
        "null",
        "duplicate",
        "wrong_kind",
        "wrong_owner",
        "activate",
        "select",
        "count",
        "type",
        "identity",
        "selection_view",
        "disabled",
        "returned_false",
    ],
)
@pytest.mark.parametrize("arrangement", tuple(probe.PmiArrangement))
def test_native_selection_or_command_rejection_is_not_a_success(
    bank, mode, arrangement
):
    adapter, view, annotations, selected = bank
    selection = adapter.currentModel.SelectionManager
    if mode == "empty":
        annotations = []
    if mode == "two":
        annotations = annotations[:2]
    if mode == "null":
        annotations[-1] = None
    if mode == "duplicate":
        annotations[1] = annotations[0]
    if mode == "wrong_kind":
        annotations[0].GetType = lambda: 6
    if mode == "wrong_owner":
        annotations[0].Owner = object()
    if mode == "activate":
        adapter.currentModel.ActivateView.return_value = False
    if mode == "select":
        annotations[0].Select2.return_value = False
        annotations[0].Select2.side_effect = None
    if mode == "count":
        selection.GetSelectedObjectCount2 = lambda _: 4
    if mode == "type":
        selection.GetSelectedObjectType3 = lambda *_: 14
    if mode == "identity":
        selection.GetSelectedObject6 = lambda *_: NS(GetAnnotation=lambda: object())
    if mode == "selection_view":
        selection.GetSelectedObjectsDrawingView2 = lambda *_: object()
    if mode == "disabled":
        adapter.swApp.IsCommandEnabled.return_value = False
    if mode == "returned_false":
        adapter.swApp.RunCommand.return_value = False
    with pytest.raises(RuntimeError):
        probe.space_imported_pmi(
            adapter, view, annotations, {}, lambda: None, arrangement=arrangement
        )
    assert not selected
    assert adapter.swApp.RunCommand.call_count == (1 if mode == "returned_false" else 0)
    if mode == "returned_false":
        adapter.swApp.RunCommand.assert_called_once_with(
            probe.PMI_SPACING_COMMANDS[arrangement], ""
        )


@pytest.mark.parametrize(
    "variant", ["space-evenly-down", "space-tightly-down", 313, [313, 317]]
)
def test_raw_or_stacked_spacing_requests_are_rejected_before_native_access(
    bank, variant
):
    adapter, view, annotations, _ = bank
    with pytest.raises(ValueError, match="Right"):
        probe.space_imported_pmi(
            adapter, view, annotations, {}, lambda: None, arrangement=variant
        )
    adapter.ownership.assert_current_owned.assert_not_called()
    adapter.swApp.RunCommand.assert_not_called()


@pytest.mark.parametrize("arrangement", tuple(probe.PmiArrangement))
def test_primary_native_error_and_cleanup_failure_are_both_retained(bank, arrangement):
    adapter, view, annotations, _ = bank
    adapter.swApp.RunCommand.side_effect = RuntimeError("command failed")
    adapter.currentModel.ClearSelection2.side_effect = [
        None,
        RuntimeError("cleanup failed"),
    ]
    with pytest.raises(ExceptionGroup) as caught:
        probe.space_imported_pmi(
            adapter, view, annotations, {}, lambda: None, arrangement=arrangement
        )
    assert [str(item) for item in caught.value.exceptions] == [
        "command failed",
        "cleanup failed",
    ]


@pytest.fixture
def scene():
    records = valid_records()
    rows, handles = {}, {}
    for record in records:
        record.update(owner_type=0, view="Right")
        key = "Right/" + record["name"]
        rows[key] = {
            "semantic": {"kind": record["type"], "text": record["key"]},
            "position": (0.1, 0.1, 0),
            "generic": {},
            "native": {"lines": "observed"},
            "measurement": {
                "name": record["name"],
                "kind": record["type"],
                "format_signature": ("font",),
                "body": {"xmin": 0.1, "xmax": 0.12, "ymin": 0.1, "ymax": 0.11},
            },
        }
        handles[key] = (object(), object(), object())
    rows["Top/CenterMark"] = {
        "semantic": {"kind": 13},
        "generic": {},
        "position": (0.2, 0.2, 0),
    }
    handles["Top/CenterMark"] = (object(),)
    before = {
        "pmi": {"annotations": records, "sheet_properties": (1, 2)},
        "views": {"Right": {"source": "same"}},
        "layout": {},
        "annotations": rows,
    }
    after = deepcopy(before)
    for index, record in enumerate(after["pmi"]["annotations"]):
        key = "Right/" + record["name"]
        y = 0.12 + index * 0.02
        record["position_m"] = (0.1, y, 0)
        after["annotations"][key]["position"] = (0.1, y, 0)
        after["annotations"][key]["measurement"]["body"].update(ymin=y, ymax=y + 0.01)
    views = {"Right": object()}
    return NS(swApp=NS(IsSame=lambda a, b: int(a is b))), before, after, views, handles


def compare(scene, after_handles=None):
    adapter, before, after, views, handles = scene
    return probe.compare_arranged_pmi(
        adapter, before, after, views, views, handles, after_handles or handles, "Right"
    )


def test_measured_spacing_preserves_all_existing_native_semantics(scene):
    report = compare(scene)
    assert not report["failures"]
    assert len(report["body_gaps"]) == 3
    assert all(row["axis_gap_m"] > 0 for row in report["body_gaps"])
    assert len(report["movement"]) == 3


@pytest.mark.parametrize(
    "mode",
    [
        "sheet",
        "view",
        "signature",
        "annotation_identity",
        "attachment_identity",
        "added_ink",
        "unselected_ink",
        "format",
        "unsupported",
        "duplicate_pmi",
    ],
)
def test_spacing_cannot_waive_source_frame_or_native_inventory_changes(scene, mode):
    _, before, after, _, handles = scene
    key = next(iter(handles))
    changed_handles = dict(handles)
    if mode == "sheet":
        after["pmi"]["sheet_properties"] = (2, 3)
    if mode == "view":
        after["views"]["Right"]["source"] = "other"
    if mode == "signature":
        after["pmi"]["annotations"][0]["signature"] = "changed manufacturing tolerance"
    if mode in {"annotation_identity", "attachment_identity"}:
        values = list(handles[key])
        values[0 if mode == "annotation_identity" else -1] = object()
        changed_handles[key] = tuple(values)
    if mode == "added_ink":
        after["annotations"]["new"] = {}
    if mode == "unselected_ink":
        after["annotations"]["Top/CenterMark"]["position"] = (0.3, 0.3, 0)
    if mode == "format":
        after["annotations"][key]["measurement"]["format_signature"] = ("other",)
    if mode == "unsupported":
        del after["annotations"][key]["measurement"]
    if mode == "duplicate_pmi":
        after["pmi"]["annotations"].append(deepcopy(after["pmi"]["annotations"][0]))
    with pytest.raises(RuntimeError):
        compare(scene, changed_handles)


@pytest.mark.parametrize("mode", ["noop", "overlap", "touch"])
def test_true_native_return_cannot_pass_without_readable_actual_motion(scene, mode):
    _, before, after, _, _ = scene
    keys = list(after["annotations"])[:3]
    if mode == "noop":
        after.update(deepcopy(before))
    if mode == "overlap":
        after["annotations"][keys[1]]["measurement"]["body"] = deepcopy(
            after["annotations"][keys[0]]["measurement"]["body"]
        )
    if mode == "touch":
        first = after["annotations"][keys[0]]["measurement"]["body"]
        after["annotations"][keys[1]]["measurement"]["body"].update(
            ymin=first["ymax"], ymax=first["ymax"] + 0.01
        )
    report = compare(scene)
    assert report["failures"]
    if mode == "noop":
        assert any("did not move" in message for message in report["failures"])


@pytest.mark.parametrize(
    "variant", ["space-tightly-down", "space-evenly-down", "auto-arrange"]
)
def test_right_only_selector_is_forwarded_and_front_rejected_before_native(
    tmp_path, monkeypatch, variant
):
    source = tmp_path / "source.SLDPRT"
    source.write_bytes(b"owned fixture")
    environment, parent = Mock(), Mock()
    monkeypatch.setattr(probe, "require_environment", environment)
    monkeypatch.setitem(sys.modules, "dodo", NS(_run=parent))
    args = [str(source), "--expected-pid", "123", "--arrangement", variant]
    with pytest.raises(ValueError, match="Right"):
        probe.main(args)
    environment.assert_not_called()
    assert probe.main([*args, "--orientation", "*Right"]) == 0
    command = parent.call_args.args[0]
    assert command[command.index("--arrangement") + 1] == variant
    assert command[command.index("--orientation") + 1] == "*Right"
    assert parent.call_args.kwargs["com"] is True
