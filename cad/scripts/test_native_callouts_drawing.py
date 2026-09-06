"""Measured callout placement must preserve native semantics and final clearance."""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from _drawing_view_packing import Rect
from _drawing_annotation_bounds import Segment
from _drawing_native_callouts import (
    Direction,
    GtolPlacement,
    arrange_native_callouts,
    placement_candidates,
    _same_symbol,
    _Symbol,
    _final_symbol,
)


def test_outboard_candidates_keep_other_axis_and_clear_actual_view():
    body = Rect(0.047, 0.052, 0.054, 0.059)
    view = Rect(0.02, 0.04, 0.1, 0.08)
    candidates = placement_candidates(body, view, (), gap_m=0.003)
    assert {item.direction for item in candidates} == set(Direction)
    for item in candidates:
        shifted = body.translated(item.delta)
        assert item.delta[0] == 0 or item.delta[1] == 0
        assert (
            shifted.xmax <= view.xmin - 0.003 + 1e-10
            or shifted.xmin >= view.xmax + 0.003 - 1e-10
            or shifted.ymax <= view.ymin - 0.003 + 1e-10
            or shifted.ymin >= view.ymax + 0.003 - 1e-10
        )


def test_candidate_ray_steps_past_colliding_dimension_and_other_symbol():
    body = Rect(0.047, 0.052, 0.054, 0.059)
    view = Rect(0.02, 0.04, 0.1, 0.08)
    obstacles = (Rect(0.045, 0.082, 0.055, 0.09), Rect(0.04, 0.092, 0.06, 0.10))
    candidate = next(
        item
        for item in placement_candidates(body, view, obstacles, gap_m=0.003)
        if item.direction is Direction.UP
    )
    assert body.translated(candidate.delta).ymin == pytest.approx(0.103)


def test_unrelated_obstacle_does_not_push_candidate_to_far_page_edge():
    body = Rect(0.047, 0.052, 0.054, 0.059)
    view = Rect(0.02, 0.04, 0.1, 0.08)
    obstacle = Rect(0.2, 0.1, 0.3, 0.2)
    plain = placement_candidates(body, view, (), gap_m=0.003)
    with_far_note = placement_candidates(body, view, (obstacle,), gap_m=0.003)
    assert plain == with_far_note


def test_candidates_are_translation_invariant():
    body, view = Rect(0.047, 0.052, 0.054, 0.059), Rect(0.02, 0.04, 0.1, 0.08)
    obstacle = Rect(0.045, 0.082, 0.055, 0.09)
    delta = (0.17, -0.022)
    first = placement_candidates(body, view, (obstacle,), gap_m=0.003)
    second = placement_candidates(
        body.translated(delta),
        view.translated(delta),
        (obstacle.translated(delta),),
        gap_m=0.003,
    )
    assert [item.direction for item in first] == [item.direction for item in second]
    for a, b in zip(first, second):
        assert a.delta == pytest.approx(b.delta)


@pytest.mark.parametrize("gap", [-0.001, float("nan"), float("inf")])
def test_invalid_clearance_is_rejected(gap):
    with pytest.raises(ValueError):
        placement_candidates(Rect(0, 0, 1, 1), Rect(0, 0, 1, 1), (), gap_m=gap)


def symbol():
    return _Symbol(
        "DatumA",
        2,
        object(),
        object(),
        object(),
        (object(),),
        (2,),
        (0.1, 0.2, 0.0),
        Rect(0.0965, 0.2, 0.1035, 0.207),
        ("A", True),
        ("A",),
        ("font", 0.0035),
    )


def test_native_z_can_change_without_being_a_manufacturing_change():
    original = symbol()
    actual = replace(
        original,
        position=(0.1, 0.25, -0.0045385),
        body=original.body.translated((0, 0.05)),
    )
    app = SimpleNamespace(IsSame=lambda a, b: int(a is b))
    _same_symbol(app, original, actual)


@pytest.mark.parametrize(
    "field,value",
    [
        ("properties", ("B", True)),
        ("text", ("changed",)),
        ("format", ("font", 0.00635)),
        ("entity_types", (1,)),
        ("kind", 7),
    ],
)
def test_semantic_or_format_change_is_not_a_new_accepted_base(field, value):
    original = symbol()
    app = SimpleNamespace(IsSame=lambda a, b: int(a is b))
    with pytest.raises(RuntimeError):
        _same_symbol(app, original, replace(original, **{field: value}))


@pytest.mark.parametrize("field", ["annotation", "specific", "owner"])
def test_native_object_replacement_is_rejected(field):
    original = symbol()
    app = SimpleNamespace(IsSame=lambda a, b: int(a is b))
    with pytest.raises(RuntimeError):
        _same_symbol(app, original, replace(original, **{field: object()}))


def test_same_type_different_controlled_face_is_rejected():
    original = symbol()
    app = SimpleNamespace(IsSame=lambda a, b: int(a is b))
    with pytest.raises(RuntimeError):
        _same_symbol(app, original, replace(original, entities=(object(),)))


class NativeAnnotation:
    """A bounded native-call contract, not an alternate drawing implementation."""

    def __init__(self, kind=2):
        self.kind = kind
        self.Visible = 1
        self.OwnerType = 0
        self.Owner = None
        self.position = (0.05, 0.055, 0.0)
        self.entities = (object(),)
        self.leader = 0
        self.leader_calls = []
        self.moves = []
        self.text_ids = []
        self.parameter = "Ra 1.6"
        self.dimension_value = 0.012
        self.dimension_calls = []
        self.mode = "ordinary"
        self.specific = SimpleNamespace(
            GetAnnotation=lambda: self,
            GetTextCount=lambda: 1,
            GetTextAtIndex=lambda index: "A" if kind == 2 else "Ra 1.6",
            GetLabel=lambda: "A",
            Shoulder=True,
            GetDisplayStyle=lambda: 2,
            GetSymbol=lambda: 1,
            GetDirectionOfLay=lambda: 0,
            Orientation=1,
            GetText=self.get_text,
        )
        if kind == 4:
            self.dimension = SimpleNamespace(
                Name="RD1",
                FullName="RD1@Drawing View1@Test.Drawing",
                GetType=lambda: 1,
                GetSystemValue2=lambda configuration: (
                    self.dimension_calls.append((2, configuration))
                    or self.dimension_value
                ),
                GetSystemValue3=lambda option, configuration: (
                    self.dimension_calls.append((3, option, configuration))
                    or (self.dimension_value,)
                ),
            )
            self.specific.Type2 = 2
            self.specific.IsReferenceDim = lambda: True
            self.specific.GetDimension2 = lambda index: self.dimension

    def get_text(self, index):
        self.text_ids.append(index)
        return self.parameter if index == 8 else ""

    def GetType(self):
        return self.kind

    def GetName(self):
        return f"Symbol{self.kind}"

    def GetPosition(self):
        return self.position

    def IsDangling(self):
        return False

    def GetAttachedEntities3(self):
        return self.entities

    def GetAttachedEntityCount3(self):
        return len(self.entities)

    def GetAttachedEntityTypes(self):
        return (2,)

    def GetSpecificAnnotation(self):
        return self.specific

    def GetLeaderStyle(self):
        return self.leader

    def SetLeader3(self, *args):
        self.leader_calls.append(args)
        self.leader = args[0]
        if self.mode == "style_changes_parameter":
            self.parameter = "Ra 6.3"
        return 0

    def SetPosition2(self, x, y, z):
        self.moves.append((x, y, z))
        if self.mode == "clamp_horizontal" and x != 0.05:
            self.position = (0.05, y, z)
            return True
        self.position = (x, y, -0.0045385 if y > 0.055 else z)
        if self.mode == "replace_face":
            self.entities = (object(),)
        return True


def native_setup(monkeypatch, kind=2, outline=(0.02, 0.04, 0.1, 0.08)):
    import _drawing_native_callouts as module

    monkeypatch.setattr(module, "_early_bound", lambda value, _: value)
    annotation = NativeAnnotation(kind)
    annotations = [annotation]
    calls = {annotation.GetName(): []}
    activations = []
    view = SimpleNamespace(
        ReferencedConfiguration="Default",
        GetName2=lambda: "Front",
        GetOutline=lambda: outline,
        GetAnnotations=lambda: tuple(annotations),
        GetAnnotationsByType=lambda target: tuple(
            a for a in annotations if a.GetType() == target
        ),
    )
    annotation.Owner = view
    sheet_view = SimpleNamespace(
        GetAnnotations=lambda: (), GetAnnotationsByType=lambda kind: ()
    )
    model = SimpleNamespace(
        GetType=lambda: 3,
        GetViews=lambda: ((sheet_view, view),),
        ActivateView=lambda name: activations.append(name) or True,
        ClearSelection2=lambda _: None,
    )
    adapter = SimpleNamespace(
        currentModel=model, swApp=SimpleNamespace(IsSame=lambda a, b: int(a is b))
    )

    def measure(_adapter, item):
        calls.setdefault(item.GetName(), []).append((item.position, item.leader))
        x, y, _ = item.position
        width = 0.007
        if item.kind == 7 and item.leader == 2:
            width = 0.018  # intentional representation change needs a NEW measured seed
        if item.mode == "deform_final" and item.moves:
            width += 0.001
        body = Rect(x - width / 2, y, x + width / 2, y + 0.007)
        if item.mode == "collide_final" and len(calls[item.GetName()]) > 1:
            target = annotation.position
            body = Rect(
                target[0] - 0.002, target[1], target[0] + 0.002, target[1] + 0.007
            )
        return SimpleNamespace(
            anchor=(x, y),
            body=body,
            text_runs=(),
            format_signature=("font", 0.0035),
            native_strokes=(Segment((x, y), (x, y + 0.007), 0.00018),)
            if item.kind == 15
            else (),
        )

    return adapter, view, annotation, annotations, calls, activations, measure


def run_native(setup, **kwargs):
    adapter, view, *_rest, measure = setup
    return arrange_native_callouts(
        adapter, views={"front": view}, measure_annotation=measure, **kwargs
    )


def test_real_dispatch_contract_keeps_datum_z_and_exact_two_witnesses(monkeypatch):
    setup = native_setup(monkeypatch, outline=(0.02, 0.0, 0.1, 0.065))
    result = run_native(setup)["front"]
    _, _, annotation, _, calls, activations, _ = setup
    assert activations == ["Front"]
    assert len(calls[annotation.GetName()]) == 2
    assert result["positions_after"][annotation.GetName()][2] == -0.0045385
    # Both witnessed datum frame sides clear the outline; no assumed side.
    assert result["bodies_after"][annotation.GetName()][1] == pytest.approx(0.075)


def test_surface_finish_remeasures_after_bent_leader_before_positioning(monkeypatch):
    setup = native_setup(monkeypatch, kind=7)
    result = run_native(setup)["front"]
    _, _, annotation, _, calls, _, _ = setup
    assert annotation.leader_calls == [(2, 0, True, False, False, False)]
    assert [row[1] for row in calls[annotation.GetName()]] == [0, 2, 2]
    assert calls[annotation.GetName()][0][0] == calls[annotation.GetName()][1][0]
    box = result["bodies_after"][annotation.GetName()]
    assert box[2] - box[0] == pytest.approx(0.018)
    assert annotation.text_ids == list(range(1, 11)) * 3


def test_style_semantic_change_cannot_become_an_accepted_seed(monkeypatch):
    setup = native_setup(monkeypatch, kind=7)
    setup[2].mode = "style_changes_parameter"
    with pytest.raises(RuntimeError, match="properties changed"):
        run_native(setup)
    assert not setup[2].moves


def test_native_horizontal_clamp_tries_permitted_vertical_direction_without_remeasurement(
    monkeypatch,
):
    setup = native_setup(monkeypatch, outline=(0.045, 0, 0.055, 0.08))
    setup[2].mode = "clamp_horizontal"
    result = run_native(setup)["front"]
    attempts = result["attempts"][setup[2].GetName()]
    assert {attempts[0]["direction"], attempts[1]["direction"]} == {"left", "right"}
    assert attempts[-1]["direction"] == "up"
    assert attempts[0]["target"][0] != attempts[0]["actual"][0]
    assert len(setup[4][setup[2].GetName()]) == 2


@pytest.mark.parametrize(
    "mode,message",
    [
        ("replace_face", "controlled entity identity"),
        ("deform_final", "post-style translation"),
    ],
)
def test_final_native_witness_rejects_content_or_body_drift(monkeypatch, mode, message):
    setup = native_setup(monkeypatch)
    setup[2].mode = mode
    with pytest.raises(RuntimeError, match=message):
        run_native(setup)


def test_final_native_obstacle_measurement_not_initial_prediction_decides_clearance(
    monkeypatch,
):
    setup = native_setup(monkeypatch)
    obstacle = NativeAnnotation(4)
    obstacle.Owner = setup[1]
    obstacle.position = (0.2, 0.2, 0)
    obstacle.mode = "collide_final"
    setup[3].append(obstacle)
    with pytest.raises(RuntimeError, match="final native callout body clearance"):
        run_native(setup)
    assert len(setup[4][obstacle.GetName()]) == 2


def test_unregistered_view_fails_before_moving_any_annotation(monkeypatch):
    setup = native_setup(monkeypatch)
    setup[0].currentModel.GetViews = lambda: ()
    with pytest.raises(ValueError, match="unique members"):
        run_native(setup)
    assert not setup[2].moves


def test_hidden_callouts_are_explicitly_left_untouched(monkeypatch):
    setup = native_setup(monkeypatch)
    setup[2].Visible = 3
    result = run_native(setup)
    assert result["front"]["count"] == 0
    assert not setup[2].moves


def test_full_final_measurement_still_runs_when_already_clear(monkeypatch):
    setup = native_setup(monkeypatch)
    setup[2].position = (0.05, 0.15, 0)
    run_native(setup)
    assert len(setup[4][setup[2].GetName()]) == 2


def test_native_attachment_count_cannot_hide_truncated_return_arrays(monkeypatch):
    setup = native_setup(monkeypatch)
    setup[2].GetAttachedEntityCount3 = lambda: 2
    with pytest.raises(RuntimeError, match="exact callout attachments"):
        run_native(setup)
    assert not setup[2].moves


def extra_annotation(setup, kind):
    annotation = NativeAnnotation(kind)
    annotation.Owner = setup[1]
    annotation.position = (0.2, 0.2, 0)
    setup[3].append(annotation)
    return annotation


def test_gtols_remain_fully_measured_obstacles_by_default(monkeypatch):
    setup = native_setup(monkeypatch)
    annotation = extra_annotation(setup, 5)
    run_native(setup)
    assert len(setup[4][annotation.GetName()]) == 2


def test_following_gtol_pass_defers_only_gtol_glyph_measurement(monkeypatch):
    setup = native_setup(monkeypatch)
    gtol = extra_annotation(setup, 5)
    dimension = extra_annotation(setup, 4)
    result = run_native(setup, gtol_placement=GtolPlacement.ARRANGED_NEXT)
    assert gtol.GetName() not in setup[4]
    assert len(setup[4][dimension.GetName()]) == 2
    assert result["front"]["deferred_annotations"] == {gtol.GetName(): 5}


def test_deferred_gtol_replacement_is_not_hidden_by_skipped_glyph_measurement(
    monkeypatch,
):
    setup = native_setup(monkeypatch)
    gtol = extra_annotation(setup, 5)
    original_move = setup[2].SetPosition2

    def replace_gtol(*point):
        replacement = NativeAnnotation(5)
        replacement.Owner = setup[1]
        setup[3][setup[3].index(gtol)] = replacement
        return original_move(*point)

    setup[2].SetPosition2 = replace_gtol
    with pytest.raises(RuntimeError, match="deferred native annotation identity"):
        run_native(setup, gtol_placement=GtolPlacement.ARRANGED_NEXT)


def unattached_note(setup):
    note = extra_annotation(setup, 6)
    note.entities = ()
    note.GetAttachedEntityTypes = lambda: ()
    return note


def test_only_exact_declared_unattached_note_defers_glyph_measurement(monkeypatch):
    setup = native_setup(monkeypatch)
    note = unattached_note(setup)
    result = run_native(setup, deferred_notes=(note,))
    assert note.GetName() not in setup[4]
    assert result["front"]["deferred_annotations"] == {note.GetName(): 6}


def test_sheet_owned_declared_note_has_valid_drawing_membership(monkeypatch):
    setup = native_setup(monkeypatch)
    note = unattached_note(setup)
    setup[3].remove(note)
    sheet_view = setup[0].currentModel.GetViews()[0][0]
    sheet_view.GetAnnotations = lambda: (note,)
    sheet_view.GetAnnotationsByType = lambda kind: (note,) if kind == 6 else ()
    note.Owner = sheet_view
    result = run_native(setup, deferred_notes=(note,))
    assert result["front"]["deferred_annotations"] == {}
    assert note.GetName() not in setup[4]


def test_raw_dispatch_declared_note_is_bound_before_typed_access(monkeypatch):
    import _drawing_native_callouts as module

    setup = native_setup(monkeypatch)
    note = unattached_note(setup)
    raw = SimpleNamespace(GetName=note.GetName(), typed_note=note)
    bindings = []

    def bind(value, interface):
        bindings.append((value, interface))
        return note if value is raw else value

    monkeypatch.setattr(module, "_early_bound", bind)
    run_native(setup, deferred_notes=(raw,))
    assert (raw, "IAnnotation") in bindings
    assert note.GetName() not in setup[4]


def test_declared_notes_shortlist_native_names_but_still_check_exact_identity(
    monkeypatch,
):
    import _drawing_native_callouts as module

    setup = native_setup(monkeypatch)
    note = unattached_note(setup)
    adapter, view = setup[:2]
    calls = []
    for index in range(40):
        unrelated = NativeAnnotation(6)
        unrelated.GetName = lambda index=index: f"Unrelated{index}"
        setup[3].append(unrelated)
    adapter.swApp.IsSame = lambda first, second: (
        calls.append((first, second)) or int(first is second)
    )
    result = module._declared_notes(
        adapter, adapter.currentModel, {"front": view}, (note,)
    )
    assert result[note.GetName()].annotation is note
    assert calls == [(note, note)]


def test_same_name_replacement_cannot_establish_declared_note_membership(monkeypatch):
    import _drawing_native_callouts as module

    setup = native_setup(monkeypatch)
    note = unattached_note(setup)
    setup[3].remove(note)
    replacement = NativeAnnotation(6)
    replacement.GetName = note.GetName
    setup[3].append(replacement)
    with pytest.raises(ValueError, match="absent from the planned drawing inventory"):
        module._declared_notes(
            setup[0], setup[0].currentModel, {"front": setup[1]}, (note,)
        )


def test_deferred_annotations_do_not_compare_unrelated_dimensions_to_notes(monkeypatch):
    import _drawing_native_callouts as module

    setup = native_setup(monkeypatch)
    note = unattached_note(setup)
    dimension = extra_annotation(setup, 4)
    calls = []
    app = SimpleNamespace(IsSame=lambda a, b: calls.append((a, b)) or int(a is b))
    result = module._deferred_annotations(
        app,
        {note.GetName(): note, dimension.GetName(): dimension},
        module.GtolPlacement.FIXED,
        {note.GetName(): module._Deferred(note, 6, 1)},
    )
    assert result.keys() == {note.GetName()}
    assert calls == [(note, note)]


def test_undeclared_note_remains_a_measured_obstacle(monkeypatch):
    setup = native_setup(monkeypatch)
    note = unattached_note(setup)
    run_native(setup)
    assert len(setup[4][note.GetName()]) == 2


@pytest.mark.parametrize("problem", ["absent", "wrong_kind", "attached", "hidden"])
def test_invalid_declared_packing_note_rejected_before_motion(monkeypatch, problem):
    setup = native_setup(monkeypatch)
    note = unattached_note(setup)
    if problem == "absent":
        setup[3].remove(note)
    if problem == "wrong_kind":
        note.kind = 5
    if problem == "attached":
        note.entities = (object(),)
    if problem == "hidden":
        note.Visible = 3
    with pytest.raises(ValueError):
        run_native(setup, deferred_notes=(note,))
    assert not setup[2].moves


def test_non_deferred_unsupported_footprint_still_fails(monkeypatch):
    setup = native_setup(monkeypatch)
    unsupported = extra_annotation(setup, 99)
    adapter, view, *_rest, measure = setup

    def strict_measure(adapter, annotation):
        if annotation is unsupported:
            raise ValueError("unsupported kind99")
        return measure(adapter, annotation)

    with pytest.raises(ValueError, match="unsupported kind99"):
        arrange_native_callouts(
            adapter,
            views={"front": view},
            measure_annotation=strict_measure,
            gtol_placement=GtolPlacement.ARRANGED_NEXT,
        )


@pytest.mark.parametrize("change", ["reattach", "value"])
def test_unrelated_dimension_semantic_change_is_not_a_new_layout_baseline(
    monkeypatch, change
):
    setup = native_setup(monkeypatch)
    dimension = extra_annotation(setup, 4)
    dimension.dimension_value = 0.127
    original_move = setup[2].SetPosition2

    def mutate_other_dimension(*point):
        if change == "reattach":
            dimension.entities = (object(),)
        if change == "value":
            dimension.dimension_value = 0.125
        return original_move(*point)

    setup[2].SetPosition2 = mutate_other_dimension
    with pytest.raises(RuntimeError, match="obstacle attachment|dimension"):
        run_native(setup)


def test_reference_dimension_with_no_geometry_still_has_native_value_witness(
    monkeypatch,
):
    setup = native_setup(monkeypatch)
    dimension = extra_annotation(setup, 4)
    dimension.entities = ()
    dimension.GetAttachedEntityTypes = lambda: ()
    run_native(setup)
    assert dimension.dimension_calls == [(2, ""), (2, "")]


def test_model_dimension_uses_the_exact_view_configuration(monkeypatch):
    setup = native_setup(monkeypatch)
    dimension = extra_annotation(setup, 4)
    dimension.specific.IsReferenceDim = lambda: False
    setup[1].ReferencedConfiguration = "Machining"
    run_native(setup)
    assert dimension.dimension_calls == [(3, 3, "Machining"), (3, 3, "Machining")]


def test_both_chamfer_parameters_are_checked_even_when_print_text_does_not_change(
    monkeypatch,
):
    setup = native_setup(monkeypatch)
    dimension = extra_annotation(setup, 4)
    second = SimpleNamespace(
        Name="RD2",
        FullName="RD2@Drawing View1@Test.Drawing",
        GetType=lambda: 2,
        GetSystemValue2=lambda _: dimension.dimension_value,
    )
    indices = []
    dimension.specific.Type2 = 10
    dimension.specific.GetDimension2 = lambda index: (
        indices.append(index) or (dimension.dimension if index == 0 else second)
    )
    dimension.dimension.GetSystemValue2 = lambda _: 0.002
    original_move = setup[2].SetPosition2

    def change_angle(*point):
        dimension.dimension_value = 0.785
        return original_move(*point)

    setup[2].SetPosition2 = change_angle
    with pytest.raises(RuntimeError, match="dimension.*system value changed"):
        run_native(setup)
    assert indices == [0, 1, 0, 1]


def test_obstacle_native_count_rejects_truncated_attachment_arrays(monkeypatch):
    setup = native_setup(monkeypatch)
    obstacle = extra_annotation(setup, 4)
    obstacle.GetAttachedEntityCount3 = lambda: 2
    with pytest.raises(RuntimeError, match="obstacle attachment inventory"):
        run_native(setup)
    assert not setup[2].moves


def test_generic_null_obstacle_attachment_is_not_allowed(monkeypatch):
    setup = native_setup(monkeypatch)
    obstacle = extra_annotation(setup, 4)
    obstacle.entities = (None,)
    obstacle.GetAttachedEntityTypes = lambda: (0,)
    with pytest.raises(RuntimeError, match="unsupported null"):
        run_native(setup)


def test_supported_null_centerline_keeps_explicit_geometry_exclusion(monkeypatch):
    setup = native_setup(monkeypatch)
    obstacle = extra_annotation(setup, 15)
    obstacle.entities = (None,)
    obstacle.GetAttachedEntityTypes = lambda: (0,)
    result = run_native(setup)
    assert (
        "exact specific identity"
        in result["front"]["obstacle_attachment_exclusions"][obstacle.GetName()]
    )


def test_null_centerline_internal_stroke_change_fails_even_with_unchanged_body(
    monkeypatch,
):
    setup = native_setup(monkeypatch)
    obstacle = extra_annotation(setup, 15)
    obstacle.entities = (None,)
    obstacle.GetAttachedEntityTypes = lambda: (0,)
    adapter, view, *_rest, measure = setup

    def changed_stroke(adapter, annotation):
        measured = measure(adapter, annotation)
        if annotation is obstacle and setup[2].moves:
            measured.native_strokes = (Segment((0.2, 0.2), (0.2, 0.206), 0.00018),)
        return measured

    with pytest.raises(RuntimeError, match="centerline/stroke witness changed"):
        arrange_native_callouts(
            adapter, views={"front": view}, measure_annotation=changed_stroke
        )


def test_telemetry_retains_native_attempt_and_final_body_readbacks(monkeypatch):
    import _drawing_native_callouts as module

    setup = native_setup(monkeypatch)
    rows = []
    monkeypatch.setattr(
        module._telemetry,
        "info",
        lambda message, **fields: rows.append((message, fields)),
    )
    result = run_native(setup)
    import json

    recorded = next(
        fields
        for message, fields in rows
        if message == "native callout layout witnessed"
    )
    decoded = json.loads(recorded["callout_report"])
    assert decoded["attempts"][setup[2].GetName()][0]["actual"] == list(
        result["front"]["attempts"][setup[2].GetName()][0]["actual"]
    )
    assert decoded["bodies_after"][setup[2].GetName()] == list(
        result["front"]["bodies_after"][setup[2].GetName()]
    )


def test_all_rejected_absolute_candidates_fail_with_original_seed_telemetry(
    monkeypatch,
):
    import _drawing_native_callouts as module

    setup = native_setup(monkeypatch, outline=(0.045, 0, 0.055, 0.08))
    annotation = setup[2]
    seed = annotation.position
    rows = []
    monkeypatch.setattr(
        module._telemetry,
        "info",
        lambda message, **fields: rows.append((message, fields)),
    )

    def always_clamped(x, y, z):
        annotation.moves.append((x, y, z))
        annotation.position = (seed[0] + 0.0002, seed[1], seed[2])
        return True

    annotation.SetPosition2 = always_clamped
    with pytest.raises(
        RuntimeError,
        match="no permitted native direction clears measured bodies",
    ):
        run_native(setup)
    records = [
        fields
        for message, fields in rows
        if message == "native callout candidate readback rejected"
    ]
    assert len(records) == 4
    assert all(row["seed_position"] == seed for row in records)
    assert all(
        row["candidate_actual"] == (seed[0] + 0.0002, seed[1], seed[2])
        for row in records
    )
    assert len(annotation.moves) == 4  # one absolute trial per bounded direction


def test_next_absolute_candidate_does_not_require_restorable_intermediate_seed(
    monkeypatch,
):
    setup = native_setup(monkeypatch, outline=(0.045, 0, 0.055, 0.08))
    annotation = setup[2]
    seed = annotation.position
    restorations = []

    def native_absolute_position(x, y, z):
        annotation.moves.append((x, y, z))
        if (x, y, z) == seed:
            restorations.append((x, y, z))
            annotation.position = (x + 0.0002, y, z)
            return False  # Original insertion seed is not a stable native target.
        if x != seed[0]:
            annotation.position = (seed[0] + 0.0001, y, z)
            return True  # Native horizontal direction clamps off the original seed.
        annotation.position = (x, y, -0.0045385)
        return True  # The subsequent original-seed absolute vertical target works.

    annotation.SetPosition2 = native_absolute_position
    result = run_native(setup)["front"]
    assert restorations == []
    directions = [
        item["direction"] for item in result["attempts"][annotation.GetName()]
    ]
    assert set(directions[:2]) == {"left", "right"}
    assert directions[-1] == "up"
    assert annotation.moves[-1][0] == seed[0]  # not accumulated from the clamped x
    assert (
        len(setup[4][annotation.GetName()]) == 2
    )  # fresh final native body still checked


def test_witnessed_native_datum_frame_flip_is_not_mistaken_for_deformation(monkeypatch):
    # Actual marker copy control: crossing the attachment changes the frame side.
    before = symbol()
    original = replace(
        before,
        position=(0.05547827660427293, 0.18199999999799998, 0),
        body=Rect(
            0.05197827660427293,
            0.18199999999799998,
            0.05897827660427293,
            0.18899999999799998,
        ),
    )
    position = (0.05547827660427293, 0.15641199999799996, 0)
    delta = position[0] - original.position[0], position[1] - original.position[1]
    predicted = replace(
        original, position=position, body=original.body.translated(delta)
    )
    actual = replace(
        predicted,
        body=Rect(
            0.05197827660427293,
            0.14941199999799995,
            0.05897827660427293,
            0.15641199999799996,
        ),
    )
    app = SimpleNamespace(IsSame=lambda a, b: int(a is b))
    _final_symbol(app, original, predicted, actual)
    records = []
    monkeypatch.setattr(
        "_drawing_native_callouts._telemetry.info",
        lambda message, **attributes: records.append((message, attributes)),
    )
    with pytest.raises(RuntimeError, match="post-style translation"):
        _final_symbol(
            app,
            original,
            predicted,
            replace(
                actual,
                body=Rect(
                    actual.body.xmin,
                    actual.body.ymin,
                    actual.body.xmax,
                    actual.body.ymax + 0.001,
                ),
            ),
        )
    message, evidence = records[0]
    assert message == "native callout body translation mismatch"
    assert evidence["annotation_kind"] == 2
    assert evidence["initial_body"] == original.body.bounds
    assert evidence["predicted_position"] == predicted.position
    assert evidence["actual_position"] == actual.position
    assert evidence["actual_body"][-1] == actual.body.ymax + 0.001
    assert len(evidence["allowed_bodies"]) == 2
