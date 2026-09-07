"""The named-pair experiment cannot bypass the owned pilot's existing gates."""

import asyncio
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace as NS
from unittest.mock import Mock, create_autospec
import inspect
import sys
from pathlib import Path
import json

import pytest

from _drawing_native_callouts import _Dimension, DimensionSource
from _drawing_project_layout import repair_project_drawing_layout
from diagnostics import _linear_dimension_arrangement as control
from diagnostics import probe_datum_policy_recipes as pilot
from diagnostics._linear_pair_k5mypm3x import RETAINED


def measured_basic(name, line_y, height=0.006):
    xmin, xmax, bottom, top = 0.1, 0.12, line_y + 0.0011, line_y + 0.0011 + height

    def line(start, end):
        return {"start": start, "end": end, "width_m": 0.0}

    return {
        "name": name,
        "kind": 4,
        "format_signature": ("Century Gothic",),
        "body": {"xmin": xmin, "xmax": xmax, "ymin": bottom, "ymax": top},
        "native_strokes": [
            line((xmin, bottom), (xmin, top)),
            line((xmin, top), (xmax, top)),
            line((xmax, top), (xmax, bottom)),
            line((xmax, bottom), (xmin, bottom)),
            line((0.05, 0.4), (0.05, line_y - 0.001)),
            line((0.18, 0.4), (0.18, line_y - 0.001)),
            line((0.05, line_y), (0.18, line_y)),
        ],
        "native_leader_segments": (),
        "leader_decorations": tuple(
            {
                "xmin": x - 0.003,
                "xmax": x + 0.003,
                "ymin": line_y - 0.003,
                "ymax": line_y + 0.003,
            }
            for x in (0.05, 0.18)
        ),
    }


@pytest.fixture
def scene(monkeypatch):
    monkeypatch.setattr(control, "_early_bound", lambda item, _: item)
    monkeypatch.setattr(control, "null_callout", lambda: None)
    views = {label: NS(GetName2=lambda label=label: label) for label in control.PAIRS}
    rows, handles, dimensions, tolerances, source_handles = {}, {}, {}, {}, {}
    source_handle = object()
    for label, pair in control.PAIRS.items():
        for index, (name, value) in enumerate(pair):
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
                DimensionSource.MODEL
                if label == "front"
                else DimensionSource.DRAWING_REFERENCE,
                11 if label == "front" else 2,
                "Default",
                ((name, key + "@Draw1.Drawing", 2, value),),
            )
            tolerances[key] = (1,)
            if label == "front":
                source_handles[name] = parameter
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
                "measurement": measured_basic(
                    name, 0.19 + (0.1 if label == "holes" else 0) - index * 0.006
                ),
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
        source_handles,
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
    pairs, plans = control.planned_pairs(
        before,
        {label: NS(GetName2=lambda label=label: label) for label in control.PAIRS},
    )
    for label, keys in pairs.items():
        first_line = plans[label]["geometry"][keys[0]]["line_y_m"] + 0.002
        for index, key in enumerate(keys):
            y = first_line - index * plans[label]["paper_pitch_m"]
            after.rows[key]["position"] = (0.1, y + 0.002778, 0)
            after.rows[key]["measurement"] = measured_basic(key.split("/")[1], y)
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
    original = create_autospec(
        inspect.unwrap(repair_project_drawing_layout),
        return_value="strict original layout result",
    )

    async def build(adapter, *, layout=original):
        return layout(adapter, views=views)

    trial, checkpoint = {"target": "channel_lever"}, Mock()
    instance = control.ParallelLinearControl(control.LinearArrangement.PARALLEL)
    kwargs = instance.bind(
        adapter, NS(build=build), trial, checkpoint, Mock(), object()
    )
    # Use the actual geometry-derived value, never a nominal assertion constant.
    plans = control.planned_pairs(before, views)[1]
    adapter.currentModel.Extension.GetUserPreferenceDouble.side_effect = [
        0.005,
        plans["front"]["document_offset_m"],
        plans["holes"]["document_offset_m"],
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


def test_pair_offset_uses_full_body_to_line_reach_and_exact_source_values(scene):
    _, views, before = scene
    before.rows["holes/RD2"]["measurement"]["body"]["ymax"] += 0.003
    pairs, plans = control.planned_pairs(before, views)
    assert pairs == {
        "front": ("front/BarLength", "front/TipCentreX"),
        "holes": ("holes/RD1", "holes/RD2"),
    }
    assert plans["front"]["paper_pitch_m"] == pytest.approx(0.0081)
    assert plans["holes"]["paper_pitch_m"] == pytest.approx(0.0111)
    assert plans["front"]["document_offset_m"] == pytest.approx(0.0081)
    assert plans["holes"]["document_offset_m"] == pytest.approx(0.0222)


def test_diagnostic_rejects_production_spacing_before_reads_or_mutation(monkeypatch):
    from _drawing_parallel_dimensions import align_channel_lever_basic_pairs

    capture = Mock(side_effect=AssertionError("must not capture"))
    select = Mock(side_effect=AssertionError("must not select"))
    monkeypatch.setattr(control, "capture", capture)
    monkeypatch.setattr(control, "select_and_align", select)
    module = NS(align_channel_lever_basic_pairs=align_channel_lever_basic_pairs)
    trial = {"target": "channel_lever"}
    source_reader, checkpoint = Mock(), Mock()
    with pytest.raises(RuntimeError, match="cannot stack"):
        control.ParallelLinearControl(control.LinearArrangement.PARALLEL).bind(
            object(), module, trial, checkpoint, source_reader, object()
        )
    capture.assert_not_called()
    select.assert_not_called()
    source_reader.assert_not_called()
    checkpoint.assert_not_called()
    assert trial == {"target": "channel_lever"}


def test_retained_native_basic_lines_derive_calibrated_per_view_pitch(scene):
    _, views, before = scene
    for key, measurement in RETAINED["before"].items():
        before.rows[key]["measurement"].update(deepcopy(measurement))
    pairs, plans = control.planned_pairs(before, views)
    assert plans["front"]["paper_pitch_m"] == pytest.approx(
        0.00768111649025552, abs=1e-15
    )
    assert plans["holes"]["paper_pitch_m"] == pytest.approx(
        0.00768111649025552, abs=1e-15
    )
    assert plans["front"]["document_offset_m"] == plans["front"]["paper_pitch_m"]
    assert plans["holes"]["document_offset_m"] == plans["holes"]["paper_pitch_m"] * 2
    after = replace(before, rows=deepcopy(before.rows))
    for key, measurement in RETAINED["after"].items():
        after.rows[key]["measurement"].update(deepcopy(measurement))
    # Native movement alone did not provide line/body clearance at the old offset.
    for label, keys in pairs.items():
        with pytest.raises(RuntimeError, match="1mm paper line/body clearance"):
            control.observed_pair_clearance(after, {label: keys})


@pytest.mark.parametrize(
    "mode",
    ["scale", "missing_scale", "duplicate_scale", "source", "type", "parameters"],
)
def test_calibrated_gain_rejects_unmeasured_contracts(scene, mode):
    _, views, before = scene
    key = "front/BarLength"
    if mode == "scale":
        before.layout["front"]["scale"] = 0.25
    if mode == "missing_scale":
        del before.layout["front"]
    if mode == "duplicate_scale":
        before.layout["Sheet2/front"] = before.layout["front"]
    if mode == "source":
        before.dimensions[key] = replace(
            before.dimensions[key], source=DimensionSource.DRAWING_REFERENCE
        )
    if mode == "type":
        before.dimensions[key] = replace(before.dimensions[key], display_type=2)
    if mode == "parameters":
        before.dimensions[key] = replace(
            before.dimensions[key], parameters=before.dimensions[key].parameters * 2
        )
    with pytest.raises(RuntimeError):
        control.planned_pairs(before, views)


def test_geometry_classification_is_independent_of_native_stroke_order_and_direction():
    original = deepcopy(RETAINED["before"]["front/BarLength"])
    shuffled = deepcopy(original)
    shuffled["native_strokes"] = [
        dict(row, start=row["end"], end=row["start"])
        for row in reversed(shuffled["native_strokes"])
    ]
    assert control.basic_linear_geometry(shuffled) == control.basic_linear_geometry(
        original
    )


@pytest.mark.parametrize(
    "mode",
    [
        "extra",
        "missing",
        "diagonal",
        "width",
        "nan",
        "open_frame",
        "frame_outside",
        "wrong_extension",
        "native_jog",
        "decoration",
        "ambiguous",
    ],
)
def test_unrecognized_basic_geometry_does_not_use_arbitrary_segment_indices(mode):
    measured = measured_basic("BarLength", 0.19)
    strokes = measured["native_strokes"]
    if mode == "extra":
        strokes.append(strokes[-1])
    if mode == "missing":
        strokes.pop()
    if mode == "diagonal":
        strokes[-1]["end"] = (0.18, 0.191)
    if mode == "width":
        strokes[0]["width_m"] = 0.0001
    if mode == "nan":
        strokes[0]["end"] = (float("nan"), 0.2)
    if mode == "open_frame":
        strokes[0]["end"] = (0.1, 0.21)
    if mode == "frame_outside":
        measured["body"]["xmin"] += 0.001
    if mode == "wrong_extension":
        strokes[-2]["start"] = (0.17, 0.4)
        strokes[-2]["end"] = (0.17, 0.189)
    if mode == "native_jog":
        measured["native_leader_segments"] = [strokes[-1]]
    if mode == "decoration":
        measured["leader_decorations"][0]["xmin"] = float("nan")
    if mode == "ambiguous":
        strokes[1] = dict(strokes[-1])
    with pytest.raises(RuntimeError):
        control.basic_linear_geometry(measured)


@pytest.mark.parametrize("mode", ["reverse_rank", "nonnested", "arrow_over_body"])
def test_pair_geometry_requires_observed_rank_nested_stations_and_safe_decorations(
    scene, mode
):
    _, views, before = scene
    measured = before.rows["front/TipCentreX"]["measurement"]
    if mode == "reverse_rank":
        before.rows["front/TipCentreX"]["measurement"] = measured_basic(
            "TipCentreX", 0.2
        )
    if mode == "nonnested":
        # Entire second frame/body moves right of the first line's extension.
        for x in ("xmin", "xmax"):
            measured["body"][x] += 0.1
        for stroke in measured["native_strokes"][:4]:
            stroke["start"] = (stroke["start"][0] + 0.1, stroke["start"][1])
            stroke["end"] = (stroke["end"][0] + 0.1, stroke["end"][1])
        for stroke in measured["native_strokes"][4:]:
            stroke["start"] = (stroke["start"][0] + 0.1, stroke["start"][1])
            stroke["end"] = (stroke["end"][0] + 0.1, stroke["end"][1])
    if mode == "arrow_over_body":
        measured["leader_decorations"][0].update(xmin=0.11, xmax=0.13)
    with pytest.raises(RuntimeError):
        control.planned_pairs(before, views)


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
        body = before.rows[key]["measurement"]["body"]
        body["ymax"] = float("nan") if mode == "nan_height" else body["ymin"]
    with pytest.raises(RuntimeError):
        control.planned_pairs(before, views)


def test_named_native_void_calls_once_per_pair_then_original_gate_once(
    monkeypatch, scene
):
    test = wrapper(monkeypatch, scene)
    result = test.invoke(
        test.adapter,
        views=test.views,
        notes="notes",
        additional_annotation_validation="mandatory checker",
    )
    assert result == "strict original layout result"
    test.original.assert_called_once_with(
        test.adapter,
        views=test.views,
        notes="notes",
        additional_annotation_validation="mandatory checker",
    )
    assert test.select.call_count == 2
    assert [call.args[2] for call in test.select.call_args_list] == [
        ("front/BarLength", "front/TipCentreX"),
        ("holes/RD1", "holes/RD2"),
    ]
    assert test.capture.call_count == 2
    extension = test.adapter.currentModel.Extension
    assert extension.SetUserPreferenceDouble.call_count == 2
    assert extension.GetUserPreferenceDouble.call_count == 3
    assert set(test.trial["linear_dimension_control"]["moved"]) == set(
        test.before.dimensions
    )
    test.instance.require_used()
    with pytest.raises(RuntimeError, match="exactly once"):
        test.invoke(test.adapter, views=test.views)
    assert test.select.call_count == 2


def test_each_pair_uses_its_own_offset_immediately_before_single_native_call(
    monkeypatch, scene
):
    test = wrapper(monkeypatch, scene)
    events = []
    extension = test.adapter.currentModel.Extension
    extension.SetUserPreferenceDouble.side_effect = lambda p, o, v: (
        events.append(("write", v)) or True
    )
    test.select.side_effect = lambda a, v, keys, b: (
        events.append(("align", keys)) or {"seconds": 0.001}
    )
    test.invoke(test.adapter, views=test.views)
    report = test.trial["linear_dimension_control"]
    assert events == [
        ("write", report["plans"]["front"]["document_offset_m"]),
        ("align", ("front/BarLength", "front/TipCentreX")),
        ("write", report["plans"]["holes"]["document_offset_m"]),
        ("align", ("holes/RD1", "holes/RD2")),
    ]
    assert all(
        row["line_body_clearance_m"] == pytest.approx(0.001)
        for row in report["observed_pair_clearance"].values()
    )
    assert test.capture.call_count == 2  # existing full before/after, no per-pair scan


def test_moved_pair_with_insufficient_actual_clearance_is_not_accepted(
    monkeypatch, scene
):
    _, _, before = scene
    after = changed(before)
    # Translation proves movement, but unchanged 6mm rank still overlaps BASIC ink.
    after.rows["holes/RD1"]["measurement"] = measured_basic("RD1", 0.3)
    after.rows["holes/RD2"]["measurement"] = measured_basic("RD2", 0.294)
    test = wrapper(monkeypatch, scene, after)
    with pytest.raises(RuntimeError, match="1mm paper line/body clearance"):
        test.invoke(test.adapter, views=test.views)
    assert len(test.trial["linear_dimension_control"]["moved"]) == 4
    test.original.assert_not_called()
    assert test.capture.call_count == 2


def test_retained_native_fixture_is_enrolled_by_recipe_gate():
    import dodo

    fixture = Path(__file__).parent / "diagnostics/_linear_pair_k5mypm3x.py"
    task = next(item for item in dodo.task_check() if item["name"] == "recipe")
    assert str(fixture.resolve()) in task["file_dep"]


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
        test.invoke(test.adapter, views=test.views)
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
        test.invoke(test.adapter, views=test.views)
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
        test.invoke(test.adapter, views=test.views)
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
        test.invoke(object(), views=test.views)
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
        key = "holes/RD1"
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
@pytest.mark.parametrize("signature_count", [0, 2])
async def test_layout_fixture_rejects_missing_or_duplicate_build_signature(
    tmp_path, monkeypatch, signature_count
):
    import test_benchmark_drawing_recipes as recipes

    signature = "async def build(adapter, *, drawing_factory):"
    monkeypatch.setattr(recipes, "recipe", lambda _: signature * signature_count)
    invoked = Mock(side_effect=AssertionError("pilot must not run with a drifted fixture"))
    monkeypatch.setattr(pilot, "pilot", invoked)
    with pytest.raises(
        AssertionError, match="fixture build signature must occur exactly once"
    ):
        await test_pilot_explicit_layout_binding_retains_source_and_cold_gates(
            tmp_path, monkeypatch, "passed"
        )
    invoked.assert_not_called()


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
    signature = "async def build(adapter, *, drawing_factory):"
    source = recipe(Path("unused.SLDPRT"))
    assert source.count(signature) == 1, "fixture build signature must occur exactly once"
    source = source.replace(
        signature,
        "async def build(adapter, *, drawing_factory, layout):\n    layout(adapter)",
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
