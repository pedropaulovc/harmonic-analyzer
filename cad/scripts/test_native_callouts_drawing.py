"""Measured callout placement must preserve native semantics and final clearance."""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from _drawing_view_packing import Rect
from _drawing_native_callouts import (
    Direction,
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
        GetName2=lambda: "Front",
        GetOutline=lambda: outline,
        GetAnnotations=lambda: tuple(annotations),
        GetAnnotationsByType=lambda target: tuple(
            a for a in annotations if a.GetType() == target
        ),
    )
    annotation.Owner = view
    model = SimpleNamespace(
        GetType=lambda: 3,
        GetViews=lambda: ((object(), view),),
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
            anchor=(x, y), body=body, text_runs=(), format_signature=("font", 0.0035)
        )

    return adapter, view, annotation, annotations, calls, activations, measure


def run_native(setup):
    adapter, view, *_rest, measure = setup
    return arrange_native_callouts(
        adapter, views={"front": view}, measure_annotation=measure
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


def test_witnessed_native_datum_frame_flip_is_not_mistaken_for_deformation():
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
