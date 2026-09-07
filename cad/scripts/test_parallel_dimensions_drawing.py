"""Four exact lever handles, native parallel spacing, no scene rescans."""

from dataclasses import replace
import ast
import math
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

import _drawing_parallel_dimensions as spacing
from _drawing_annotation_bounds import AnnotationBounds, Segment, TextRun
from _drawing_native_callouts import _Dimension, DimensionSource
from _drawing_view_packing import Rect


def measured(name, line_y):
    body = Rect(0.1, line_y + 0.0011, 0.12, line_y + 0.0071)
    a, b, c, d = (
        (0.1, body.ymin),
        (0.1, body.ymax),
        (0.12, body.ymax),
        (0.12, body.ymin),
    )
    strokes = tuple(
        Segment(*points)
        for points in (
            (a, b),
            (b, c),
            (c, d),
            (d, a),
            ((0.05, 0.4), (0.05, line_y - 0.001)),
            ((0.18, 0.4), (0.18, line_y - 0.001)),
            ((0.05, line_y), (0.18, line_y)),
        )
    )
    return AnnotationBounds(
        name,
        4,
        (0.11, body.ymin),
        body,
        Rect(0.05, line_y - 0.001, 0.18, 0.4),
        (body,),
        (TextRun(name, (0.1, body.ymin), 0.0035, "Century Gothic", 0, 1, 0),),
        (),
        ("Century Gothic",),
        strokes,
    )


@pytest.fixture
def scene(monkeypatch):
    monkeypatch.setattr(spacing, "_early_bound", lambda value, _: value)
    monkeypatch.setattr(spacing, "null_callout", lambda: None)
    monkeypatch.setattr(
        spacing,
        "_installed_swconst",
        lambda: NS(
            swDetailingDimToDimOffset=1,
            swDetailingNoOptionSpecified=0,
        ),
    )
    part, sheet = object(), object()
    views = {
        label: NS(
            GetName2=lambda label=label: label,
            ReferencedDocument=part,
            ReferencedConfiguration="Default",
            ScaleDecimal=0.5,
            Position=(0.2, 0.2),
            GetAnnotations=Mock(side_effect=AssertionError("no scene enumeration")),
            GetAnnotationsByType=Mock(
                side_effect=AssertionError("no scene enumeration")
            ),
        )
        for label in ("front", "holes")
    }
    annotations, witnesses, measurements, displays = {}, {}, {}, {}
    for label, definitions in spacing.PAIRS.items():
        for index, (name, value) in enumerate(definitions):
            annotation = NS(Owner=views[label], OwnerType=0, Visible=1)
            annotation.GetName = lambda name=name: name
            annotation.GetType = lambda: 4
            annotation.IsDangling = lambda: False
            annotation.entities = (object(), object())
            annotation.types = (11, 11) if label == "front" else (1, 1)
            annotation.GetAttachedEntities3 = lambda a=annotation: a.entities
            annotation.GetAttachedEntityTypes = lambda a=annotation: a.types
            annotation.GetAttachedEntityCount3 = lambda a=annotation: len(a.entities)
            annotation.GetPosition = lambda name=name: (*measurements[name].anchor, 0.0)
            display = NS(
                GetAnnotation=lambda a=annotation: a,
                GetNameForSelection=lambda name=name: name + "@Drawing",
            )
            parameter = NS(Tolerance=NS(Type=1))
            witness = _Dimension(
                display,
                (parameter,),
                DimensionSource.MODEL
                if label == "front"
                else DimensionSource.DRAWING_REFERENCE,
                11 if label == "front" else 2,
                "Default",
                ((name, name + "@native.Owner", 0, value),),
            )
            annotations[name], witnesses[name], displays[name] = (
                annotation,
                witness,
                display,
            )
            measurements[name] = measured(name, 0.19 - index * 0.006)
    selections, commands, offsets = [], [], []

    def select(name, kind, x, y, z, append, mark, callout, option):
        assert (kind, x, y, z, append, mark, callout, option) == (
            "DIMENSION",
            0.0,
            0.0,
            0.0,
            True,
            0,
            None,
            0,
        )
        selections.append(displays[name.removesuffix("@Drawing")])
        return True

    extension = NS(
        SelectByID2=Mock(side_effect=select),
        GetUserPreferenceDouble=Mock(
            side_effect=lambda *_: offsets[-1] if offsets else 0.005
        ),
        SetUserPreferenceDouble=Mock(
            side_effect=lambda _a, _b, value: offsets.append(value) or True
        ),
    )
    selection = NS(
        GetSelectedObjectCount2=lambda _: len(selections),
        GetSelectedObject6=lambda index, _: selections[index - 1],
    )
    model = NS(
        Extension=extension,
        SelectionManager=selection,
        GetType=lambda: 3,
        GetCurrentSheet=lambda: sheet,
        ClearSelection2=Mock(side_effect=lambda _: selections.clear()),
        ActivateView=Mock(return_value=True),
    )

    def align():
        names = tuple(
            item.GetNameForSelection().removesuffix("@Drawing") for item in selections
        )
        commands.append(names)
        gain = 1.0 if names[0] == "BarLength" else 0.5
        y = spacing.basic_linear_geometry(
            spacing.BasicLinearInk.from_bounds(measurements[names[0]])
        ).line_y_m
        measurements[names[1]] = measured(names[1], y - offsets[-1] * gain)

    model.AlignParallelDimensions = Mock(side_effect=align)
    adapter = NS(
        currentModel=model, swApp=NS(ActiveDoc=model, IsSame=lambda a, b: int(a is b))
    )
    reader = Mock(
        side_effect=lambda _adapter, annotation: measurements[annotation.GetName()]
    )
    monkeypatch.setattr(spacing, "annotation_box", reader)
    monkeypatch.setattr(
        spacing,
        "_dimension_witness",
        lambda _adapter, _view, annotation: witnesses[annotation.GetName()],
    )
    log = Mock()
    monkeypatch.setattr(spacing._telemetry, "info", log)

    def run():
        return spacing.align_channel_lever_basic_pairs(
            adapter,
            front=views["front"],
            holes=views["holes"],
            bar_length=annotations["BarLength"],
            tip_centre_x=annotations["TipCentreX"],
            bar_pin_c2c=annotations["RD1"],
            spring_c2c=annotations["RD2"],
        )

    return NS(**locals())


def test_exactly_four_initial_four_final_bounds_and_one_native_call_per_pair(scene):
    scene.run()
    assert scene.reader.call_count == 8
    assert scene.commands == [("BarLength", "TipCentreX"), ("RD1", "RD2")]
    assert scene.offsets == pytest.approx([0.0081, 0.0162])
    assert scene.extension.GetUserPreferenceDouble.call_count == 3
    assert scene.extension.SelectByID2.call_count == 4
    assert not scene.selections
    assert scene.log.call_count == 2
    for view in scene.views.values():
        view.GetAnnotations.assert_not_called()
        view.GetAnnotationsByType.assert_not_called()


@pytest.mark.parametrize(
    "mode",
    [
        "scale",
        "same_view",
        "hidden",
        "owner",
        "value",
        "type",
        "source",
        "basic",
        "null",
        "count",
        "name",
        "wrong_active",
    ],
)
def test_unsupported_inputs_fail_before_any_preference_or_native_command(scene, mode):
    annotation = scene.annotations["BarLength"]
    dimension = scene.witnesses["BarLength"]
    if mode == "scale":
        scene.views["front"].ScaleDecimal = 0.25
    if mode == "same_view":
        scene.views["holes"] = scene.views["front"]
    if mode == "hidden":
        annotation.Visible = 3
    if mode == "owner":
        annotation.Owner = object()
    if mode == "value":
        scene.witnesses["BarLength"] = replace(
            dimension, parameters=(("BarLength", "full", 0, 0.170),)
        )
    if mode == "type":
        scene.witnesses["BarLength"] = replace(dimension, display_type=2)
    if mode == "source":
        scene.witnesses["BarLength"] = replace(
            dimension, source=DimensionSource.DRAWING_REFERENCE
        )
    if mode == "basic":
        dimension.dimensions[0].Tolerance.Type = 0
    if mode == "null":
        annotation.entities = (None, object())
    if mode == "count":
        annotation.GetAttachedEntityCount3 = lambda: 1
    if mode == "name":
        annotation.GetName = lambda: "Wrong"
    if mode == "wrong_active":
        scene.adapter.swApp.ActiveDoc = object()
    with pytest.raises(RuntimeError):
        scene.run()
    assert not scene.commands and not scene.offsets


@pytest.mark.parametrize(
    "mode",
    [
        "value_ulp",
        "parameter",
        "attachment",
        "attachment_type",
        "basic",
        "owner",
        "text",
        "format",
        "scale",
        "config",
        "source",
        "position",
        "active",
    ],
)
def test_post_native_mutations_fail_exact_semantic_or_context_gate(scene, mode):
    original = scene.model.AlignParallelDimensions.side_effect

    def mutation():
        original()
        if len(scene.commands) != 2:
            return
        annotation = scene.annotations["BarLength"]
        dimension = scene.witnesses["BarLength"]
        if mode == "value_ulp":
            scene.witnesses["BarLength"] = replace(
                dimension,
                parameters=(
                    (
                        "BarLength",
                        "BarLength@native.Owner",
                        0,
                        math.nextafter(0.169, math.inf),
                    ),
                ),
            )
        if mode == "parameter":
            scene.witnesses["BarLength"] = replace(
                dimension, dimensions=(NS(Tolerance=NS(Type=1)),)
            )
        if mode == "attachment":
            annotation.entities = (object(), annotation.entities[1])
        if mode == "attachment_type":
            annotation.types = (1, 1)
        if mode == "basic":
            dimension.dimensions[0].Tolerance.Type = 0
        if mode == "owner":
            annotation.Owner = object()
        if mode == "text":
            scene.measurements["BarLength"] = replace(
                scene.measurements["BarLength"], text_runs=()
            )
        if mode == "format":
            scene.measurements["BarLength"] = replace(
                scene.measurements["BarLength"], format_signature=("changed",)
            )
        if mode == "scale":
            scene.views["front"].ScaleDecimal = 0.25
        if mode == "config":
            scene.views["front"].ReferencedConfiguration = "changed"
        if mode == "source":
            scene.views["front"].ReferencedDocument = object()
        if mode == "position":
            scene.views["front"].Position = (0.3, 0.2)
        if mode == "active":
            scene.adapter.swApp.ActiveDoc = object()

    scene.model.AlignParallelDimensions.side_effect = mutation
    with pytest.raises(RuntimeError):
        scene.run()
    scene.log.assert_not_called()


def test_no_native_movement_cannot_be_accepted(scene):
    scene.model.AlignParallelDimensions.side_effect = None
    with pytest.raises(RuntimeError, match="move|clearance"):
        scene.run()
    assert scene.reader.call_count == 8
    scene.log.assert_not_called()


def test_native_spacing_readback_failure_stops_before_command(scene):
    scene.extension.GetUserPreferenceDouble.side_effect = [0.005, 0.123]
    with pytest.raises(RuntimeError, match="spacing.*retain|spacing.*readback"):
        scene.run()
    scene.model.AlignParallelDimensions.assert_not_called()


def test_wrong_selected_native_handle_fails_and_clears_selection(scene):
    scene.selection.GetSelectedObject6 = lambda *_: object()
    with pytest.raises(RuntimeError, match="selection"):
        scene.run()
    scene.model.AlignParallelDimensions.assert_not_called()
    assert not scene.selections


@pytest.mark.parametrize("mode", ["activate", "select", "count", "write", "command"])
def test_native_failures_never_log_success_or_retry(scene, mode):
    if mode == "activate":
        scene.model.ActivateView.return_value = False
    if mode == "select":
        scene.extension.SelectByID2.side_effect = None
        scene.extension.SelectByID2.return_value = False
    if mode == "count":
        scene.selection.GetSelectedObjectCount2 = lambda _: 999
    if mode == "write":
        scene.extension.SetUserPreferenceDouble.side_effect = None
        scene.extension.SetUserPreferenceDouble.return_value = False
    if mode == "command":
        scene.model.AlignParallelDimensions.side_effect = RuntimeError(
            "native command failed"
        )
    with pytest.raises(RuntimeError):
        scene.run()
    assert scene.model.AlignParallelDimensions.call_count <= 1
    assert scene.extension.SetUserPreferenceDouble.call_count == 1
    assert scene.reader.call_count == 4
    scene.log.assert_not_called()
    assert not scene.selections


def test_context_change_after_first_command_rejects_before_second_mutation(scene):
    original = scene.model.AlignParallelDimensions.side_effect

    def change_context():
        original()
        scene.adapter.currentModel = object()

    scene.model.AlignParallelDimensions.side_effect = change_context
    with pytest.raises(RuntimeError, match="context"):
        scene.run()
    assert scene.model.AlignParallelDimensions.call_count == 1
    assert scene.extension.SetUserPreferenceDouble.call_count == 1
    scene.log.assert_not_called()


def test_reader_does_not_accept_replaced_display_annotation_before_selection(scene):
    scene.displays["BarLength"].GetAnnotation = lambda: NS(Owner=scene.views["front"])
    with pytest.raises(RuntimeError, match="identity changed before selection"):
        scene.run()
    scene.model.AlignParallelDimensions.assert_not_called()


def test_recognized_native_fixture_matches_shared_diagnostic_pure_geometry():
    from diagnostics import _linear_dimension_arrangement as diagnostic
    from diagnostics._linear_pair_k5mypm3x import RETAINED
    from dataclasses import asdict

    rows = RETAINED["before"]
    for key, row in rows.items():
        ink = spacing.BasicLinearInk(
            Rect(**row["body"]),
            tuple(Segment(**line) for line in row["native_strokes"]),
            tuple(Segment(**line) for line in row.get("native_leader_segments", ())),
            tuple(Rect(**box) for box in row.get("leader_decorations", ())),
        )
        assert diagnostic.basic_linear_geometry(row) == asdict(
            spacing.basic_linear_geometry(ink)
        )
    assert diagnostic.read_basic_linear_geometry is spacing.basic_linear_geometry
    assert diagnostic.basic_pair_geometry is spacing.basic_pair_geometry
    assert diagnostic.required_paper_pitch is spacing.required_paper_pitch
    assert diagnostic.observed_paper_clearance is spacing.observed_paper_clearance


def test_recipe_supplies_four_existing_handles_before_unchanged_final_gate():
    import draw_channel_lever as recipe

    tree = ast.parse(Path(recipe.__file__).read_text(encoding="utf-8"))
    build = next(
        node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "build"
    )
    calls = [
        node
        for node in ast.walk(build)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    align = [
        node for node in calls if node.func.id == "align_channel_lever_basic_pairs"
    ]
    layout = next(node for node in calls if node.func.id == "layout")
    assert len(align) == 1 and align[0].lineno < layout.lineno
    assert {item.arg: ast.unparse(item.value) for item in align[0].keywords} == {
        "front": "front",
        "holes": "holes",
        "bar_length": "profile_linear['BarLength']",
        "tip_centre_x": "profile_linear['TipCentreX']",
        "bar_pin_c2c": "bar_pin_c2c.GetAnnotation()",
        "spring_c2c": "spring_c2c.GetAnnotation()",
    }
    assert (
        ast.unparse(
            next(
                item.value
                for item in layout.keywords
                if item.arg == "additional_annotation_validation"
            )
        )
        == "validate_dimension_leader_clearance"
    )
    assert sum(node.func.id == "auto_arrange_view_dimensions" for node in calls) == 1
    assert (
        max(node.lineno for node in calls if node.func.id == "add_property_linked_note")
        < align[0].lineno
    )


def test_production_closure_excludes_diagnostics_and_gate_enrolls_new_tests():
    import _buildgraph
    import dodo
    import draw_channel_lever as recipe

    dependencies = tuple(
        Path(item).resolve()
        for item in _buildgraph.module_deps_of(Path(recipe.__file__).resolve())
    )
    assert Path(spacing.__file__).resolve() in dependencies
    assert all("diagnostics" not in path.parts for path in dependencies)
    check = next(row for row in dodo.task_check() if row["name"] == "recipe")
    assert str(Path(__file__).resolve()) in {
        str(Path(item).resolve()) for item in check["file_dep"]
    }
