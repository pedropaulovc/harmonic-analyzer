"""The named-pair experiment cannot bypass the owned pilot's existing gates."""

import asyncio
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace as NS
from unittest.mock import Mock
import sys
from pathlib import Path
import json

import pytest

from _drawing_native_callouts import _Dimension, DimensionSource
from diagnostics import _linear_dimension_arrangement as control
from diagnostics import probe_datum_policy_recipes as pilot


@pytest.fixture
def scene(monkeypatch):
    monkeypatch.setattr(control, "_early_bound", lambda item, _: item)
    monkeypatch.setattr(control, "null_callout", lambda: None)
    views = {label: NS(GetName2=lambda label=label: label) for label in control.PAIRS}
    rows, handles, dimensions, tolerances = {}, {}, {}, {}
    source_handle = object()
    for label, pair in control.PAIRS.items():
        for name, value in pair:
            key = f"{label}/{name}"
            annotation = NS(Owner=views[label])
            display = NS(
                GetAnnotation=lambda annotation=annotation: annotation,
                GetNameForSelection=lambda key=key: key + "@Drawing",
            )
            parameter = NS(Tolerance=NS(Type=1))
            dimensions[key] = _Dimension(
                display,
                (parameter,),
                DimensionSource.DRAWING_REFERENCE,
                11,
                "Default",
                ((name, key + "@Draw1.Drawing", 2, value),),
            )
            tolerances[key] = (1,)
            handles[key] = (annotation, views[label], source_handle)
            rows[key] = {
                "semantic": {
                    "kind": 4,
                    "visible": 1,
                    "owner_type": 0,
                    "texts": (name,),
                },
                "position": (0.1, 0.2, 0),
                "native": {"metadata": "same"},
                "generic": {"texts": (name,)},
                "measurement": {
                    "name": name,
                    "kind": 4,
                    "format_signature": ("Century Gothic",),
                    "body": {"xmin": 0.1, "xmax": 0.12, "ymin": 0.2, "ymax": 0.206},
                    "native_strokes": ((0.1, 0.2, 0.12, 0.2),),
                },
            }
    rows["front/Note"] = {
        "semantic": {"kind": 6},
        "generic": {},
        "position": (0.3, 0.4, 0),
    }
    handles["front/Note"] = (object(),)
    before = control.Capture(
        rows,
        handles,
        dimensions,
        tolerances,
        {key: {"position": (0.1, 0.2), "scale": 0.5} for key in views},
        {
            "configuration": "Default",
            "dimensions": {"BarLength": {"value": 0.169, "tolerance_type": 1}},
        },
        {"BarLength": source_handle},
    )
    extension = NS(
        GetUserPreferenceDouble=Mock(side_effect=[0.005, 0.007]),
        SetUserPreferenceDouble=Mock(return_value=True),
    )
    adapter = NS(
        currentModel=NS(Extension=extension),
        swApp=NS(IsSame=lambda a, b: int(a is b)),
        ownership=NS(assert_current_owned=Mock()),
    )
    return adapter, views, before


def changed(before):
    after = replace(
        before,
        rows=deepcopy(before.rows),
        dimensions=dict(before.dimensions),
        tolerances=dict(before.tolerances),
    )
    for key in before.dimensions:
        after.rows[key]["position"] = (0.1, 0.21, 0)
        after.rows[key]["measurement"]["native_strokes"] = ((0.1, 0.21, 0.12, 0.21),)
    return after


def wrapper(monkeypatch, scene, after=None):
    adapter, views, before = scene
    after = after or changed(before)
    capture = Mock(side_effect=[before, after])
    monkeypatch.setattr(control, "capture", capture)
    select = Mock(
        return_value={"selection_names": ["first", "second"], "seconds": 0.001}
    )
    monkeypatch.setattr(control, "select_and_align", select)
    monkeypatch.setattr(
        control,
        "_installed_swconst",
        lambda: NS(swDetailingDimToDimOffset=1, swDetailingNoOptionSpecified=0),
    )
    original = Mock(return_value="strict original layout result")

    async def build(adapter, *, layout=original):
        return layout(adapter, views)

    trial, checkpoint = {"target": "channel_lever"}, Mock()
    instance = control.ParallelLinearControl(control.LinearArrangement.PARALLEL)
    kwargs = instance.bind(
        adapter, NS(build=build), trial, checkpoint, Mock(), object()
    )
    # Use the actual geometry-derived value, never a nominal assertion constant.
    requested = control.planned_pairs(before, views)[1]
    adapter.currentModel.Extension.GetUserPreferenceDouble.side_effect = [
        0.005,
        requested,
    ]
    return NS(
        adapter=adapter,
        views=views,
        before=before,
        after=after,
        capture=capture,
        select=select,
        original=original,
        trial=trial,
        checkpoint=checkpoint,
        instance=instance,
        invoke=kwargs["layout"],
    )


def test_pair_offset_uses_actual_body_height_and_exact_source_values(scene):
    _, views, before = scene
    before.rows["holes/RD2"]["measurement"]["body"]["ymax"] = 0.209
    pairs, distance = control.planned_pairs(before, views)
    assert pairs == {
        "front": ("front/BarLength", "front/TipCentreX"),
        "holes": ("holes/RD1", "holes/RD2"),
    }
    assert distance == pytest.approx(0.010)


def test_retained_native_nominal_roundoff_is_not_a_parameter_mutation(scene):
    # datum-policy-wepq18dc stopped on the first pair before any native setter.
    _, views, before = scene
    values = {
        "front/BarLength": 0.16900000007399998,
        "front/TipCentreX": 0.182799999906,
        "holes/RD1": 0.127,
        "holes/RD2": 0.1778,
    }
    for key, value in values.items():
        row = before.dimensions[key]
        before.dimensions[key] = replace(
            row, parameters=((*row.parameters[0][:3], value),)
        )
    pairs, _ = control.planned_pairs(before, views)
    assert set(values) == {key for pair in pairs.values() for key in pair}


@pytest.mark.parametrize("delta", [-2e-9, 2e-9])
def test_nominal_design_check_still_rejects_outside_one_nanometre(scene, delta):
    _, views, before = scene
    key = "front/BarLength"
    row = before.dimensions[key]
    before.dimensions[key] = replace(
        row, parameters=((*row.parameters[0][:3], 0.169 + delta),)
    )
    with pytest.raises(RuntimeError, match="value contract"):
        control.planned_pairs(before, views)


def test_even_one_ulp_same_session_value_change_remains_a_mutation(scene):
    import math

    adapter, _, before = scene
    after = changed(before)
    key = "front/BarLength"
    row = before.dimensions[key]
    after.dimensions[key] = replace(
        row, parameters=((*row.parameters[0][:3], math.nextafter(0.169, math.inf)),)
    )
    with pytest.raises(RuntimeError, match="system value changed"):
        control.compare_control(adapter, before, after, set(before.dimensions))


@pytest.mark.parametrize(
    "mode",
    [
        "missing_view",
        "same_view",
        "missing_dimension",
        "hidden",
        "diameter",
        "not_basic",
        "wrong_value",
        "nan_height",
        "zero_height",
    ],
)
def test_named_pair_rejects_unsupported_or_wrong_feature_without_coordinate_search(
    scene, mode
):
    _, views, before = scene
    key = "front/BarLength"
    if mode == "missing_view":
        del views["front"]
    if mode == "same_view":
        views["holes"] = views["front"]
    if mode == "missing_dimension":
        del before.dimensions[key]
    if mode == "hidden":
        before.rows[key]["semantic"]["visible"] = 3
    if mode == "diameter":
        before.dimensions[key] = replace(before.dimensions[key], display_type=6)
    if mode == "not_basic":
        before.tolerances[key] = (0,)
    if mode == "wrong_value":
        before.dimensions[key] = replace(
            before.dimensions[key], parameters=(("BarLength", key, 2, 0.170),)
        )
    if mode in {"nan_height", "zero_height"}:
        before.rows[key]["measurement"]["body"]["ymax"] = (
            float("nan") if mode == "nan_height" else 0.2
        )
    with pytest.raises(RuntimeError):
        control.planned_pairs(before, views)


def test_named_native_void_calls_once_per_pair_then_original_gate_once(
    monkeypatch, scene
):
    test = wrapper(monkeypatch, scene)
    result = test.invoke(
        test.adapter,
        test.views,
        "notes",
        additional_annotation_validation="mandatory checker",
    )
    assert result == "strict original layout result"
    test.original.assert_called_once_with(
        test.adapter,
        test.views,
        "notes",
        additional_annotation_validation="mandatory checker",
    )
    assert test.select.call_count == 2
    assert [call.args[2] for call in test.select.call_args_list] == [
        ("front/BarLength", "front/TipCentreX"),
        ("holes/RD1", "holes/RD2"),
    ]
    assert test.capture.call_count == 2
    extension = test.adapter.currentModel.Extension
    assert extension.SetUserPreferenceDouble.call_count == 1
    assert extension.GetUserPreferenceDouble.call_count == 2
    assert set(test.trial["linear_dimension_control"]["moved"]) == set(
        test.before.dimensions
    )
    test.instance.require_used()
    with pytest.raises(RuntimeError, match="exactly once"):
        test.invoke(test.adapter, test.views)
    assert test.select.call_count == 2


@pytest.mark.parametrize("mode", ["write_false", "readback", "invalid_initial"])
def test_document_preference_rejection_stops_before_native_arrangement(
    monkeypatch, scene, mode
):
    test = wrapper(monkeypatch, scene)
    extension = test.adapter.currentModel.Extension
    if mode == "write_false":
        extension.SetUserPreferenceDouble.return_value = False
    if mode == "readback":
        extension.GetUserPreferenceDouble.side_effect = [0.005, 0.004]
    if mode == "invalid_initial":
        extension.GetUserPreferenceDouble.side_effect = [float("nan")]
    with pytest.raises(RuntimeError):
        test.invoke(test.adapter, test.views)
    test.select.assert_not_called()
    test.original.assert_not_called()


@pytest.mark.parametrize(
    "mode",
    [
        "source_value",
        "source_handle",
        "annotation_handle",
        "attachment",
        "dimension_handle",
        "dimension_value",
        "basic",
        "unselected_ink",
        "selected_text",
        "format",
        "view_move",
        "added_annotation",
        "no_movement",
        "metadata_only",
    ],
)
def test_full_same_session_witness_blocks_semantic_changes_and_noop(
    monkeypatch, scene, mode
):
    _, _, before = scene
    after = changed(before)
    key = "front/BarLength"
    if mode == "source_value":
        after.source = {"changed": True}
    if mode == "source_handle":
        after.source_handles = {"BarLength": object()}
    if mode in {"annotation_handle", "attachment"}:
        after.handles = dict(before.handles)
        values = list(before.handles[key])
        values[0 if mode == "annotation_handle" else -1] = object()
        after.handles[key] = tuple(values)
    if mode == "dimension_handle":
        after.dimensions[key] = replace(before.dimensions[key], dimensions=(object(),))
    if mode == "dimension_value":
        after.dimensions[key] = replace(
            before.dimensions[key], parameters=(("BarLength", key, 2, 0.170),)
        )
    if mode == "basic":
        after.tolerances[key] = (0,)
    if mode == "unselected_ink":
        after.rows["front/Note"]["position"] = (0.4, 0.4, 0)
    if mode == "selected_text":
        after.rows[key]["semantic"]["texts"] = ("wrong",)
    if mode == "format":
        after.rows[key]["measurement"]["format_signature"] = ("wrong",)
    if mode == "view_move":
        after.layout = deepcopy(before.layout)
        after.layout["front"]["position"] = (0.2, 0.2)
    if mode == "added_annotation":
        after.rows["front/new"] = {}
    if mode in {"no_movement", "metadata_only"}:
        after.rows = deepcopy(before.rows)
        if mode == "metadata_only":
            after.rows[key]["native"]["metadata"] = "changed only"
    test = wrapper(monkeypatch, scene, after)
    with pytest.raises(RuntimeError):
        test.invoke(test.adapter, test.views)
    test.original.assert_not_called()
    assert "error" in test.trial["linear_dimension_control"]


def test_existing_crossing_failure_and_checkpoint_failure_preserve_original(
    monkeypatch, scene
):
    test = wrapper(monkeypatch, scene)
    primary = RuntimeError("the unchanged crossing gate rejected the trial")

    def original(*_, **__):
        test.checkpoint.side_effect = OSError("receipt write failed")
        raise primary

    test.original.side_effect = original
    with pytest.raises(RuntimeError) as caught:
        test.invoke(test.adapter, test.views)
    assert caught.value is primary
    assert (
        "receipt write failed"
        in test.trial["linear_dimension_control"]["checkpoint_error"]
    )


def test_empty_unused_or_wrong_adapter_callback_is_not_accepted(monkeypatch, scene):
    test = wrapper(monkeypatch, scene)
    with pytest.raises(RuntimeError, match="not invoked"):
        test.instance.require_used()
    with pytest.raises(RuntimeError, match="owned adapter"):
        test.invoke(object(), test.views)
    test.capture.assert_not_called()
    test.original.assert_not_called()


@pytest.mark.parametrize(
    "mode",
    [
        "valid",
        "empty",
        "duplicate",
        "activate",
        "blank_name",
        "select_false",
        "count",
        "selected_identity",
        "annotation_identity",
        "owner",
    ],
)
def test_exact_named_selection_and_native_void_call_cleanup(scene, mode):
    adapter, views, before = scene
    keys = ("front/BarLength", "front/TipCentreX")
    selected = []
    model = adapter.currentModel
    model.ClearSelection2 = Mock(side_effect=lambda _: selected.clear())
    model.ActivateView = Mock(return_value=mode != "activate")
    model.AlignParallelDimensions = Mock(return_value=None)
    display_by_name = {
        row.display.GetNameForSelection(): row.display
        for row in before.dimensions.values()
    }

    def select(name, kind, x, y, z, append, mark, callout, option):
        assert (kind, x, y, z, append, mark, callout, option) == (
            "DIMENSION",
            0,
            0,
            0,
            True,
            0,
            None,
            0,
        )
        selected.append(display_by_name[name])
        return mode != "select_false"

    model.Extension.SelectByID2 = Mock(side_effect=select)
    model.SelectionManager = NS(
        GetSelectedObjectCount2=lambda _: 0 if mode == "count" else len(selected),
        GetSelectedObject6=lambda index, _: (
            object() if mode == "selected_identity" else selected[index - 1]
        ),
    )
    if mode == "empty":
        keys = ()
    if mode == "duplicate":
        keys = keys[:1] * 2
    display = before.dimensions["front/BarLength"].display
    if mode == "blank_name":
        display.GetNameForSelection = lambda: ""
    if mode == "annotation_identity":
        display.GetAnnotation = lambda: object()
    if mode == "owner":
        display.GetAnnotation().Owner = object()
    if mode == "valid":
        report = control.select_and_align(adapter, views["front"], keys, before)
        assert report["selection_names"] == [key + "@Drawing" for key in keys]
        model.AlignParallelDimensions.assert_called_once_with()
    else:
        with pytest.raises(RuntimeError):
            control.select_and_align(adapter, views["front"], keys, before)
        model.AlignParallelDimensions.assert_not_called()
    assert not selected
    assert model.ClearSelection2.call_count == 2


@pytest.mark.parametrize(
    "targets",
    [
        ("rocker_arm",),
        ("rocker_arm", "channel_lever"),
        (),
        ("channel_lever", "channel_lever"),
    ],
)
def test_optin_rejects_unsupported_target_sequences(targets):
    control.require_targets(None, targets)
    with pytest.raises(ValueError):
        control.require_targets(control.LinearArrangement.PARALLEL, targets)


@pytest.mark.parametrize("route", ["parent", "worker"])
def test_explicit_cli_selector_keeps_guards_and_only_passes_optin(
    tmp_path, monkeypatch, route
):
    monkeypatch.setattr(pilot, "require_owned_diagnostic_environment", lambda: None)
    monkeypatch.setattr(pilot.benchmark, "revision", lambda _: "frozen")
    native_parent, received = Mock(), []
    monkeypatch.setitem(sys.modules, "dodo", NS(_run=native_parent))

    async def run(*args, targets, linear_control):
        received.append((targets, linear_control.variant))
        return 0

    monkeypatch.setattr(pilot, "pilot", run)
    monkeypatch.setattr(
        pilot, "run_copy_diagnostic", lambda fn: asyncio.run(fn(object()))
    )
    args = [
        "--source-root",
        str(tmp_path),
        "--guard-root",
        str(tmp_path),
        "--target",
        "channel_lever",
        "--linear-dimensions",
        "parallel",
    ]
    if route == "worker":
        args.append("--worker")
    assert pilot.main(args) == 0
    if route == "worker":
        assert received == [(("channel_lever",), control.LinearArrangement.PARALLEL)]
        native_parent.assert_not_called()
        return
    command = native_parent.call_args.args[0]
    assert command[command.index("--linear-dimensions") + 1] == "parallel"
    assert command[command.index("--target") + 1] == "channel_lever"
    assert command[command.index("--candidate") + 1] == "frozen"
    assert native_parent.call_args.kwargs["com"] is True


def test_unsupported_cli_fails_before_environment_or_native_task(tmp_path, monkeypatch):
    environment = Mock(side_effect=AssertionError("must not access native environment"))
    monkeypatch.setattr(pilot, "require_owned_diagnostic_environment", environment)
    with pytest.raises(ValueError, match="exactly channel_lever"):
        pilot.main(
            [
                "--source-root",
                str(tmp_path),
                "--guard-root",
                str(tmp_path),
                "--linear-dimensions",
                "parallel",
            ]
        )
    environment.assert_not_called()


@pytest.mark.parametrize(
    "mode",
    ["valid", "wrong_source", "wrong_owner", "undeclared_model_parameter", "duplicate"],
)
def test_capture_reads_native_inventory_once_and_rejects_owner_or_source_drift(
    monkeypatch, scene, mode
):
    adapter, views, before = scene
    source = object()
    raw_inventory = Mock(return_value=(before.rows, before.handles))
    monkeypatch.setattr(control.shoulder, "all_annotation_layout", raw_inventory)
    monkeypatch.setattr(control.attachments, "layout", lambda _: before.layout)
    annotations = {}
    for label, view in views.items():
        view.ReferencedDocument = object() if mode == "wrong_source" else source
        bank = []
        for key, row in before.dimensions.items():
            if not key.startswith(label + "/"):
                continue
            annotation = before.handles[key][0]
            annotation.GetName = lambda key=key: key.split("/")[1]
            if mode == "wrong_owner":
                annotation.Owner = object()
            annotations[id(annotation)] = row
            bank.append(annotation)
        if mode == "duplicate":
            bank.append(bank[0])
        view.GetAnnotationsByType = Mock(return_value=bank)
    if mode == "undeclared_model_parameter":
        key = "front/BarLength"
        annotations[id(before.handles[key][0])] = replace(
            before.dimensions[key], source=DimensionSource.MODEL
        )
    monkeypatch.setattr(
        control,
        "_dimension_witness",
        lambda _a, _v, annotation: annotations[id(annotation)],
    )
    source_reader = Mock(return_value=(before.source, before.source_handles))
    if mode == "valid":
        measured = control.capture(adapter, views, source_reader, source)
        assert measured.rows is before.rows
        assert measured.handles is before.handles
        assert measured.dimensions == before.dimensions
        assert measured.tolerances == before.tolerances
        assert (
            measured.receipt()["dimensions"]["holes/RD1"]["parameters"]
            == before.dimensions["holes/RD1"].parameters
        )
    else:
        with pytest.raises(RuntimeError):
            control.capture(adapter, views, source_reader, source)
    raw_inventory.assert_called_once_with(adapter)
    source_reader.assert_called_once_with()
    adapter.ownership.assert_current_owned.assert_called_once_with()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["passed", "cold_title", "copy_saved", "unused"])
async def test_pilot_explicit_layout_binding_retains_source_and_cold_gates(
    tmp_path, monkeypatch, mode
):
    from test_datum_policy_recipes_drawing import Adapter, fixture_sources
    from test_benchmark_drawing_recipes import recipe

    source_root, guard_root = fixture_sources(tmp_path, monkeypatch)
    monkeypatch.setattr(pilot.benchmark, "revision", lambda _: "frozen")
    monkeypatch.setattr(pilot, "helper_fingerprints", lambda: {"helper": "same"})
    monkeypatch.setattr(pilot, "adapter_fingerprints", lambda: {"adapter": "same"})
    source = recipe(Path("unused.SLDPRT")).replace(
        "async def build(adapter):",
        "async def build(adapter, *, layout):\n    layout(adapter)",
    )
    monkeypatch.setattr(pilot.benchmark, "recipe_source", lambda *_: source)
    source_handle = object()
    reader = Mock(
        return_value=(
            {"configuration": "Default", "values": "same"},
            {"D": source_handle},
        )
    )
    monkeypatch.setattr(pilot, "source_dimensions", reader)
    witness = Mock(return_value={"geometry": "same", "values": "same"})
    monkeypatch.setattr(pilot, "drawing_witness", witness)
    comparison = Mock(
        return_value={
            "status": "failed" if mode == "cold_title" else "passed",
            "rejected": ["title moved"],
        }
    )
    monkeypatch.setattr(pilot, "compare_drawing_reopen", comparison)
    adapter = Adapter("source_drift" if mode == "copy_saved" else "normal")
    callback = Mock()
    events = []

    class Controller:
        variant = control.LinearArrangement.PARALLEL

        def bind(self, actual, module, trial, checkpoint, source_reader, source_model):
            assert (
                actual is adapter
                and not adapter.drawn
                and trial["target"] == "channel_lever"
            )
            assert source_model == adapter.currentModel
            assert source_reader() == reader.return_value
            events.append("bind")
            return {"layout": callback}

        def require_used(self):
            callback.assert_called_once_with(adapter)
            events.append("used")
            if mode == "unused":
                raise RuntimeError("control was not invoked exactly once")

    arguments = (adapter, "frozen", source_root, guard_root, tmp_path / "reports")
    if mode == "passed":
        await pilot.pilot(
            *arguments, targets=("channel_lever",), linear_control=Controller()
        )
    else:
        with pytest.raises(RuntimeError):
            await pilot.pilot(
                *arguments, targets=("channel_lever",), linear_control=Controller()
            )
    (path,) = (tmp_path / "reports").glob("*/pilot.json")
    report = json.loads(path.read_text())
    assert events == ["bind", "used"]
    assert report["status"] == ("passed" if mode == "passed" else "failed")
    assert report["sources_before"] == report["sources_after"]
    assert adapter.ownership.creating_document.call_count == 1
    if mode in {"passed", "cold_title"}:
        assert witness.call_count == 2
        comparison.assert_called_once()
    if mode == "cold_title":
        assert "title moved" in report["error"]


def test_actual_tracked_recipe_has_explicit_layout_default_without_diagnostic_import(
    tmp_path, monkeypatch
):
    source = (Path(__file__).parent / "draw_channel_lever.py").read_text()
    monkeypatch.setattr(pilot.benchmark, "recipe_source", lambda *_: source)
    (tmp_path / "owned.SLDPRT").write_bytes(b"owned diagnostic fixture")
    module = pilot.benchmark.load_recipe(
        "local-source", "channel_lever", tmp_path, source=tmp_path / "owned.SLDPRT"
    )
    original = module.build.__kwdefaults__["layout"]
    assert original.__name__ == "repair_project_drawing_layout"
    assert "_linear_dimension_arrangement" not in source
    assert module.build.__kwdefaults__["source"] == tmp_path / "owned.SLDPRT"
