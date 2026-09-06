"""Document leader policy is a witnessed native representation transaction."""

from dataclasses import replace
from types import SimpleNamespace

import pytest

import _drawing_native_callouts as callouts
import _drawing_native_datum_leaders as leaders
from _drawing_annotation_bounds import Segment
from _drawing_view_packing import Rect
from test_native_callouts_drawing import NativeAnnotation, frame_strokes, native_setup


@pytest.mark.parametrize(
    "anchor,frame,direction",
    [
        (
            (0.29875, 0.1683376494921567, 0),
            Rect(0.3051, 0.1648376494921567, 0.3121, 0.1718376494921567),
            callouts.Direction.RIGHT,
        ),
        (
            (0.14008966333774672, 0.17163799823614767, -0.001764124996),
            Rect(
                0.12673966333774672,
                0.16813799823614767,
                0.13373966333774673,
                0.17513799823614767,
            ),
            callouts.Direction.LEFT,
        ),
        (
            (0.23146308259773007, 0.18937656194075042, -0.000625),
            Rect(
                0.23781308259773007,
                0.18587656194075042,
                0.24481308259773008,
                0.19287656194075042,
            ),
            callouts.Direction.RIGHT,
        ),
    ],
)
def test_saved_rocker_exact_horizontal_shoulders(anchor, frame, direction):
    joint = (
        frame.xmin if direction is callouts.Direction.RIGHT else frame.xmax,
        anchor[1],
    )
    measured = SimpleNamespace(
        native_strokes=frame_strokes(frame) + (Segment(anchor[:2], joint, 0.00018),)
    )
    actual = callouts._bent_shoulder(measured, anchor, frame)
    assert actual.direction is direction
    assert actual.length_m == pytest.approx(0.00635)


@pytest.mark.parametrize("mode", ["diagonal", "missing", "duplicate", "inside"])
def test_only_exact_unique_native_elbow_frame_segment_is_supported(mode):
    frame = Rect(0.06, 0.05, 0.067, 0.057)
    anchor = (0.05, 0.0535, 0)
    segment = Segment(anchor[:2], (frame.xmin, anchor[1]), 0.00018)
    strokes = frame_strokes(frame) + (segment,)
    if mode == "diagonal":
        anchor = (anchor[0], anchor[1] + 0.001, 0)
    if mode == "missing":
        strokes = frame_strokes(frame)
    if mode == "duplicate":
        strokes += (segment,)
    if mode == "inside":
        anchor = (0.061, anchor[1], 0)
    with pytest.raises(RuntimeError, match="bent datum"):
        callouts._bent_shoulder(SimpleNamespace(native_strokes=strokes), anchor, frame)


def policy_setup(monkeypatch, *, initial_shoulder=False, mode="ordinary"):
    adapter, view, datum, annotations, calls, activations, base_measure = native_setup(
        monkeypatch
    )
    monkeypatch.setattr(leaders, "_early_bound", lambda value, _: value)
    monkeypatch.setattr(
        leaders,
        "_installed_swconst",
        lambda: SimpleNamespace(
            swDetailingAnnotationBentLeaderLength=113,
            swDetailingNoOptionSpecified=0,
            swDetailingGtolUseDocBentLeaderLength=377,
            swDetailingGtolBentLeaderLength=114,
            swDetailingSFSymbolUseDocBentLeaderLength=379,
            swDetailingSFSymbolBentLeaderLength=115,
        ),
    )
    datum.specific.Shoulder = initial_shoulder
    datum.specific.ForcedShoulder = False
    datum.specific.GetDisplayStyle = lambda: 1
    source = SimpleNamespace(GetPathName=lambda: "C:/test/source.SLDPRT")
    view.ReferencedDocument, view.Position, view.ScaleDecimal = (
        source,
        (0.06, 0.06),
        1.0,
    )
    state = SimpleNamespace(
        length=0.00635,
        writes=[],
        rebuilds=0,
        snapshots=[],
        events=[],
        mode=mode,
        inheritance={377: True, 379: True},
        family_lengths={114: 0.012, 115: 0.015},
        family_writes=[],
    )
    dimension = NativeAnnotation(4)
    dimension.Owner = view
    dimension.position = (0.2, 0.2, 0)
    annotations.append(dimension)

    def set_length(preference, option, value):
        if preference != 113:
            state.family_writes.append((preference, option, value))
            if mode == "family_reject":
                return False
            if mode != "family_ignore":
                state.family_lengths[preference] = value
            return True
        state.writes.append((preference, option, value))
        state.events.append("write")
        if mode == "reject":
            return False
        if mode == "ignore":
            return True
        state.length = value
        if mode == "replace_entity":
            datum.entities = (object(),)
        if mode == "dimension_value":
            dimension.dimension_value += 0.001
        if mode == "view_context":
            view.ScaleDecimal = 0.5
        if mode == "label":
            datum.specific.GetLabel = lambda: "B"
        if mode == "forced_shoulder":
            datum.specific.ForcedShoulder = True
        return True

    def rebuild():
        state.rebuilds += 1
        if mode == "family_drift_after_rebuild":
            state.family_lengths[114] += 0.001
        return mode != "rebuild_rejected"

    def get_length(preference, option):
        if preference == 113:
            return state.length
        toggle = {114: 377, 115: 379}[preference]
        return (
            state.length
            if state.inheritance[toggle]
            else state.family_lengths[preference]
        )

    def set_toggle(preference, option, value):
        state.family_writes.append((preference, option, value))
        if mode != "family_toggle_ignore":
            state.inheritance[preference] = value
        return True  # observed native result even when the actual value is False

    adapter.currentModel.Extension = SimpleNamespace(
        GetUserPreferenceDouble=get_length,
        SetUserPreferenceDouble=set_length,
        GetUserPreferenceToggle=lambda preference, option: state.inheritance[
            preference
        ],
        SetUserPreferenceToggle=set_toggle,
    )
    adapter.currentModel.EditRebuild3 = rebuild

    def measure(native_adapter, annotation):
        state.events.append("measure")
        state.snapshots.append((annotation, state.length))
        measured = base_measure(native_adapter, annotation)
        measured.envelope = measured.body
        measured.leader_segments = ()
        measured.native_leader_segments = ()
        measured.leader_decorations = ()
        if annotation is not datum:
            return measured
        if not datum.specific.Shoulder:
            return measured
        x, y, _ = datum.position
        length = 0.00635 if mode == "ignored_geometry" else state.length
        body = Rect(x + length, y - 0.0035, x + length + 0.007, y + 0.0035)
        measured.body = body
        measured.envelope = Rect(x, body.ymin, body.xmax, body.ymax)
        measured.native_strokes = frame_strokes(body) + (
            Segment((x, y), (body.xmin, y), 0.00018),
        )
        if mode == "rendered_text" and state.writes:
            measured.text_runs[0].value = "A changed"
        return measured

    def run():
        return leaders.prepare_document_datum_leaders(
            adapter,
            views={"front": view},
            measure=measure,
            planning_gap_m=0.003,
            declared_notes={},
            gtol_placement=callouts.GtolPlacement.ARRANGED_NEXT,
        )

    return adapter, view, datum, dimension, state, measure, run


@pytest.mark.parametrize("initial_shoulder", [False, True])
def test_one_document_write_moves_measured_frame_and_keeps_elbow_entity(
    monkeypatch, initial_shoulder
):
    adapter, view, datum, dimension, state, measure, run = policy_setup(
        monkeypatch, initial_shoulder=initial_shoulder
    )
    original_entity, original_anchor = datum.entities, datum.position
    run()
    assert len(state.writes) == state.rebuilds == 1
    assert state.writes[0][:2] == (113, 0)
    assert state.length == pytest.approx(0.053)
    assert datum.position == original_anchor and datum.entities == original_entity
    assert datum.moves == [] and datum.specific.Shoulder is True
    assert measure(adapter, datum).body.xmin == pytest.approx(
        view.GetOutline()[2] + 0.003
    )
    # Both fixed dimensions and native datum bodies are read on both sides of mutation.
    assert {length for item, length in state.snapshots if item is dimension} == {
        0.00635,
        state.length,
    }


@pytest.mark.parametrize(
    "mode,match",
    [
        ("reject", "length rejected"),
        ("ignore", "did not persist"),
        ("rebuild_rejected", "rebuild failed"),
        ("ignored_geometry", "shoulder geometry changed"),
        ("replace_entity", "entity identity changed"),
        ("dimension_value", "system value changed"),
        ("view_context", "view/model context"),
        ("label", "rendered datum text"),
        ("rendered_text", "rendered datum text"),
        ("forced_shoulder", "shoulder_constraint changed"),
    ],
)
def test_property_true_never_substitutes_for_final_native_witness(
    monkeypatch, mode, match
):
    *_, run = policy_setup(monkeypatch, mode=mode)
    with pytest.raises(RuntimeError, match=match):
        run()


def test_document_mutation_requires_every_native_view(monkeypatch):
    adapter, view, datum, dimension, state, measure, run = policy_setup(monkeypatch)
    with pytest.raises(RuntimeError, match="every drawing view"):
        leaders.prepare_document_datum_leaders(
            adapter,
            views={},
            measure=measure,
            planning_gap_m=0.003,
            declared_notes={},
            gtol_placement=callouts.GtolPlacement.FIXED,
        )
    assert state.writes == [] and datum.specific.Shoulder is False


def test_same_side_overlapping_datums_fail_before_global_write(monkeypatch):
    adapter, view, datum, dimension, state, measure, run = policy_setup(
        monkeypatch, initial_shoulder=True
    )
    original = callouts._read_symbol(
        adapter,
        view,
        datum,
        measure,
        datum_leader_policy=callouts.DatumLeaderPolicy.BENT_DOCUMENT,
    )
    bank = leaders._Bank(
        view,
        leaders._context(view),
        {"A": original, "B": replace(original, name="B")},
        {},
        {},
        {},
    )
    monkeypatch.setattr(leaders, "_read_banks", lambda *_: {"front": bank})
    with pytest.raises(RuntimeError, match="one document length cannot separate"):
        run()
    assert state.writes == []


def test_template_native_ink_change_is_not_excluded_from_global_witness(monkeypatch):
    adapter, view, datum, dimension, state, measure, run = policy_setup(monkeypatch)
    native = object()
    monkeypatch.setattr(
        leaders,
        "_sheet_witness",
        lambda *_: ({}, {"template": (native, 1, ("ink", state.length))}),
    )
    with pytest.raises(RuntimeError, match="fixed template ink"):
        run()


def test_outboard_extension_steps_past_actual_fixed_dimension_text(monkeypatch):
    adapter, view, datum, dimension, state, measure, run = policy_setup(
        monkeypatch, initial_shoulder=True
    )
    original = callouts._read_symbol(
        adapter,
        view,
        datum,
        measure,
        datum_leader_policy=callouts.DatumLeaderPolicy.BENT_DOCUMENT,
    )
    amount = leaders.required_increase(
        original, Rect(*view.GetOutline()), (Rect(0.103, 0.05, 0.12, 0.06),), 0.003
    )
    assert original.body.translated((amount, 0)).xmin == pytest.approx(0.123)


def test_callout_handoff_receives_only_post_policy_final_measurements(monkeypatch):
    adapter, view, datum, dimension, state, measure, run = policy_setup(monkeypatch)
    records = []
    callouts.arrange_native_callouts(
        adapter,
        views={"front": view},
        measure_annotation=measure,
        datum_leader_policy=callouts.DatumLeaderPolicy.BENT_DOCUMENT,
        record_measurement=lambda v, a, b: records.append((v, a, b, state.length)),
    )
    assert len(state.writes) == 1
    assert {row[1] for row in records} == {datum, dimension}
    assert all(row[3] == state.length for row in records)
    assert datum.moves == []


def test_two_pilots_explicitly_opt_in_without_changing_other_recipes():
    from pathlib import Path

    scripts = Path(__file__).parent
    opted_in = {
        path.name
        for path in scripts.glob("draw_*.py")
        if "datum_leader_policy=DatumLeaderPolicy.BENT_DOCUMENT"
        in path.read_text(encoding="utf-8")
    }
    assert opted_in == {"draw_rocker_arm.py", "draw_channel_lever.py"}


def test_shared_length_rechecks_earlier_dimension_after_another_datum_extends(
    monkeypatch,
):
    adapter, view, datum, dimension, state, measure, run = policy_setup(
        monkeypatch, initial_shoulder=True
    )
    symbol = callouts._read_symbol(
        adapter,
        view,
        datum,
        measure,
        datum_leader_policy=callouts.DatumLeaderPolicy.BENT_DOCUMENT,
    )
    # A is initially clear of its text at x=.16, but B's required extension
    # would place A in that text. The final single value must clear both.
    first = (symbol, Rect(0.02, 0.04, 0.1, 0.08), (Rect(0.16, 0.05, 0.18, 0.06),))
    second = (symbol, Rect(0.02, 0.04, 0.155, 0.08), ())
    increase = leaders.shared_increase((first, second), 0.003)
    assert symbol.body.translated((increase, 0)).xmin == pytest.approx(0.183)
    assert leaders.shared_increase((second, first), 0.003) == pytest.approx(increase)


@pytest.mark.parametrize("length", [0, -1, float("nan"), float("inf")])
def test_invalid_document_length_fails_before_any_representation_write(
    monkeypatch, length
):
    adapter, view, datum, dimension, state, measure, run = policy_setup(monkeypatch)
    state.length = length
    with pytest.raises(RuntimeError, match="not positive/finite"):
        run()
    assert datum.specific.Shoulder is False and state.writes == []


def test_shoulder_setter_rejection_fails_before_document_write(monkeypatch):
    adapter, view, datum, dimension, state, measure, run = policy_setup(monkeypatch)

    class IgnoredShoulder(SimpleNamespace):
        def __setattr__(self, key, value):
            if key == "Shoulder":
                return
            super().__setattr__(key, value)

    datum.specific = IgnoredShoulder(**vars(datum.specific))
    with pytest.raises(RuntimeError, match="shoulder rejected"):
        run()
    assert state.writes == []


@pytest.mark.parametrize("count", [0, -1, 10001])
def test_global_gtol_frame_inventory_is_bounded(count, monkeypatch):
    monkeypatch.setattr(leaders, "_early_bound", lambda value, _: value)
    specific = SimpleNamespace(GetFrameCount=lambda: count)
    annotation = SimpleNamespace(
        GetType=lambda: 5, GetSpecificAnnotation=lambda: specific
    )
    with pytest.raises(RuntimeError, match="frame count"):
        leaders._gtol_xml({"gtol": annotation})


def test_gtol_xml_witness_uses_documented_one_based_indices(monkeypatch):
    monkeypatch.setattr(leaders, "_early_bound", lambda value, _: value)
    indices = []
    frame = SimpleNamespace(GetSymbolXml=lambda: '<gtol value="0.2"/>')
    specific = SimpleNamespace(
        GetFrameCount=lambda: 2, GetFrame=lambda index: indices.append(index) or frame
    )
    annotation = SimpleNamespace(
        GetType=lambda: 5, GetSpecificAnnotation=lambda: specific
    )
    assert leaders._gtol_xml({"gtol": annotation}) == {
        "gtol": ('<gtol value="0.2"></gtol>',) * 2
    }
    assert indices == [1, 2]


@pytest.mark.parametrize(
    "gtol_inherited,sf_inherited",
    [(True, True), (True, False), (False, True), (False, False)],
)
def test_family_defaults_preserve_each_initial_effective_length_with_one_rebuild(
    monkeypatch, gtol_inherited, sf_inherited
):
    *_, state, measure, run = policy_setup(monkeypatch)
    state.length = 0.011  # deliberately not the6.35mm diagnostic control value
    state.inheritance = {377: gtol_inherited, 379: sf_inherited}
    expected = {
        114: 0.011 if gtol_inherited else 0.012,
        115: 0.011 if sf_inherited else 0.015,
    }
    run()
    assert state.inheritance == {377: False, 379: False}
    assert state.family_lengths == expected
    assert len(state.family_writes) == 2 * (int(gtol_inherited) + int(sf_inherited))
    assert state.rebuilds == 1


@pytest.mark.parametrize(
    "mode",
    [
        "family_toggle_ignore",
        "family_reject",
        "family_ignore",
        "family_drift_after_rebuild",
    ],
)
def test_family_default_true_cannot_hide_ignored_or_drifting_native_definition(
    monkeypatch, mode
):
    *_, run = policy_setup(monkeypatch, mode=mode)
    with pytest.raises(RuntimeError, match="family"):
        run()


def test_zero_required_extension_leaves_all_family_definitions_and_rebuild_untouched(
    monkeypatch,
):
    *_, state, measure, run = policy_setup(monkeypatch)
    monkeypatch.setattr(leaders, "shared_increase", lambda *_: 0.0)
    run()
    assert state.family_writes == [] and state.writes == [] and state.rebuilds == 0
    assert state.inheritance == {377: True, 379: True}


def add_family_annotations(view):
    class FamilyAnnotation(NativeAnnotation):
        @property
        def BentLeaderLength(self):
            return self.native_override

        @BentLeaderLength.setter
        def BentLeaderLength(self, value):
            raise AssertionError(
                "production policy must never write individual overrides"
            )

    sf, gtol = FamilyAnnotation(7), FamilyAnnotation(5)
    sf.native_override, gtol.native_override = -1.0, 0.019
    frame = SimpleNamespace(GetSymbolXml=lambda: '<gtol value="0.2"/>')
    gtol.specific.GetFrameCount = lambda: 1
    gtol.specific.GetFrame = lambda index: frame
    for item in (sf, gtol):
        item.Owner = view
        item.position = (0.3, 0.3, 0)
    inventory = (*view.GetAnnotations(), sf, gtol)
    view.GetAnnotations = lambda: inventory
    view.GetAnnotationsByType = lambda kind: tuple(
        a for a in inventory if a.kind == kind
    )
    return sf, gtol


def test_individual_overrides_and_document_driven_minus_one_are_read_only(monkeypatch):
    adapter, view, datum, dimension, state, measure, run = policy_setup(monkeypatch)
    sf, gtol = add_family_annotations(view)
    run()
    assert (sf.BentLeaderLength, gtol.BentLeaderLength) == (-1.0, 0.019)
    assert state.rebuilds == 1
    # The stronger primitive/override comparisons consume the original two
    # measurement banks; no additional native stroke/text measurement pass.
    assert sum(item is sf for item, _ in state.snapshots) == 2
    assert sum(item is gtol for item, _ in state.snapshots) == 2


@pytest.mark.parametrize("target", ["sf", "gtol"])
def test_changed_annotation_override_fails_even_if_primitive_geometry_is_unchanged(
    monkeypatch, target
):
    adapter, view, datum, dimension, state, measure, run = policy_setup(monkeypatch)
    sf, gtol = add_family_annotations(view)
    original_rebuild = adapter.currentModel.EditRebuild3

    def rebuild():
        returned = original_rebuild()
        (sf if target == "sf" else gtol).native_override = 0.023
        return returned

    adapter.currentModel.EditRebuild3 = rebuild
    with pytest.raises(RuntimeError, match="annotation length override changed"):
        run()


@pytest.mark.parametrize("kind", [4, 5, 7])
@pytest.mark.parametrize(
    "field",
    [
        "native_strokes",
        "leader_segments",
        "native_leader_segments",
        "leader_decorations",
    ],
)
def test_final_non_datum_primitive_drift_rejected_with_identical_body_and_content(
    monkeypatch, kind, field
):
    adapter, view, datum, dimension, state, measure, run = policy_setup(monkeypatch)
    sf, gtol = add_family_annotations(view)
    target = {4: dimension, 5: gtol, 7: sf}[kind]

    def measured(native_adapter, annotation):
        actual = measure(native_adapter, annotation)
        if annotation is target:
            delta = 0.001 if state.writes else 0.0
            primitive = (
                Rect(0.02, 0.04, 0.021 + delta, 0.041)
                if field == "leader_decorations"
                else Segment((0.02, 0.04), (0.021 + delta, 0.041), 0.00018)
            )
            setattr(actual, field, (primitive,))
        return actual

    with pytest.raises(RuntimeError, match=f"non-datum native {field}"):
        leaders.prepare_document_datum_leaders(
            adapter,
            views={"front": view},
            measure=measured,
            planning_gap_m=0.003,
            declared_notes={},
            gtol_placement=callouts.GtolPlacement.ARRANGED_NEXT,
        )


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf")])
def test_invalid_independent_family_length_fails_before_any_style_or_preference_write(
    monkeypatch, value
):
    adapter, view, datum, dimension, state, measure, run = policy_setup(monkeypatch)
    state.inheritance[377] = False
    state.family_lengths[114] = value
    with pytest.raises(RuntimeError, match="family length is not positive/finite"):
        run()
    assert datum.specific.Shoulder is False
    assert state.writes == state.family_writes == []
