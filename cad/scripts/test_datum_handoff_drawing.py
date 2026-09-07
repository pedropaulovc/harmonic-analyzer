"""Post-datum reuse is one read-only bounds bank, never a semantic cache."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import _drawing_measurement_handoff as module
import _drawing_native_callouts as callouts
from test_measurement_handoff_drawing import context
from test_native_callouts_drawing import NativeAnnotation
from test_native_datum_leaders_drawing import add_family_annotations, policy_setup


def strict_context(monkeypatch):
    _, adapter, view, annotation, measured, fresh = context(monkeypatch)
    annotation.GetType.return_value = measured.kind = 4
    annotation.Visible = 1
    adapter.swApp.ActiveDoc = adapter.currentModel
    source = view.ReferencedDocument = object()
    view.GetOutline.return_value = (0.01, 0.02, 0.2, 0.3)
    inventory = {"Control": annotation}
    handoff = module.AnnotationMeasurementHandoff(
        adapter,
        views={"front": view},
        measure_annotation=fresh,
        purpose=module.HandoffPurpose.POST_DATUM_CALLOUTS,
        inventory_of=lambda _: dict(inventory),
    )
    rows = {
        "Control": SimpleNamespace(
            annotation=annotation, owner=view, kind=4, measurement=measured
        )
    }
    handoff.record_bank(view, rows, source=source)
    handoff.seal()
    return handoff, adapter, view, annotation, measured, fresh, inventory


def test_strict_post_datum_bank_consumes_bounds_once_then_expires(monkeypatch):
    handoff, adapter, view, annotation, measured, fresh, _ = strict_context(monkeypatch)
    with handoff.read_scope():
        assert handoff.initial_measure(adapter, annotation) is measured
        with pytest.raises(RuntimeError, match="consumed twice"):
            handoff.initial_measure(adapter, annotation)
    with pytest.raises(RuntimeError, match="begin a read bank"):
        handoff.begin_read()
    handoff.close()
    with pytest.raises(RuntimeError, match="not ready"):
        handoff.initial_measure(adapter, annotation)
    fresh.assert_not_called()


@pytest.mark.parametrize("stage", ["begin", "end"])
@pytest.mark.parametrize(
    "change",
    [
        "drawing",
        "active_document",
        "sheet",
        "view_position",
        "scale",
        "configuration",
        "source",
        "outline",
        "identity",
        "owner",
        "position",
        "added",
        "deleted",
        "hidden",
    ],
)
def test_post_datum_context_or_inventory_drift_rejects_before_mutation(
    monkeypatch, stage, change
):
    handoff, adapter, view, annotation, measured, fresh, inventory = strict_context(
        monkeypatch
    )
    mutate = Mock()
    if stage == "end":
        handoff.begin_read()
        assert handoff.initial_measure(adapter, annotation) is measured
    if change == "drawing":
        adapter.currentModel = object()
    if change == "active_document":
        adapter.swApp.ActiveDoc = object()
    if change == "sheet":
        adapter.currentModel.GetCurrentSheet.return_value = object()
    if change == "view_position":
        view.Position = (0.11, 0.2)
    if change == "scale":
        view.ScaleRatio = (2, 2)
    if change == "configuration":
        view.ReferencedConfiguration = "Other"
    if change == "source":
        view.ReferencedDocument = object()
    if change == "outline":
        view.GetOutline.return_value = (0.02, 0.02, 0.2, 0.3)
    if change == "identity":
        replacement = Mock()
        replacement.GetName.return_value = "Control"
        replacement.GetType.return_value = 4
        replacement.Visible = 1
        replacement.OwnerType, replacement.Owner = 0, view
        replacement.GetPosition.return_value = annotation.GetPosition()
        inventory["Control"] = replacement
    if change == "owner":
        annotation.Owner = object()
    if change == "position":
        annotation.GetPosition.return_value = (0.021, 0.03, 0)
    if change == "added":
        inventory["Extra"] = Mock()
    if change == "deleted":
        inventory.clear()
    if change == "hidden":
        annotation.Visible = 3
    with pytest.raises(RuntimeError, match="changed"):
        handoff.begin_read() if stage == "begin" else handoff.end_read()
        mutate()
    mutate.assert_not_called()
    fresh.assert_not_called()


def test_post_datum_prior_mid_inventory_change_cannot_complete_or_mutate(monkeypatch):
    handoff, adapter, view, annotation, _, _, _ = strict_context(monkeypatch)
    mutate = Mock()
    with pytest.raises(RuntimeError, match="context changed"):
        with handoff.read_scope():
            view.ReferencedConfiguration = "Other"
            handoff.initial_measure(adapter, annotation)
        mutate()
    mutate.assert_not_called()
    with pytest.raises(RuntimeError, match="begin a read bank"):
        handoff.begin_read()


def candidate_setup(monkeypatch):
    adapter, view, datum, dimension, state, measure, _ = policy_setup(monkeypatch)
    monkeypatch.setattr(module, "_early_bound", lambda value, _: value)
    sheet = object()
    adapter.currentModel.GetCurrentSheet = lambda: sheet
    adapter.swApp.ActiveDoc = adapter.currentModel
    view.ScaleRatio = (1, 1)
    view.GetReferencedModelName = lambda: "C:/test/source.SLDPRT"
    original = measure

    def measure(native_adapter, annotation):
        measured = original(native_adapter, annotation)
        measured.name, measured.kind = annotation.GetName(), annotation.GetType()
        return measured

    return adapter, view, datum, dimension, state, measure


def test_candidate_keeps_all_semantic_reads_and_finals_but_skips_initial_bounds(
    monkeypatch,
):
    adapter, view, datum, dimension, state, measure = candidate_setup(monkeypatch)
    sf, _ = add_family_annotations(view)
    record = Mock()
    result = callouts.arrange_native_callouts(
        adapter,
        views={"front": view},
        measure_annotation=measure,
        record_measurement=record,
        datum_leader_policy=callouts.DatumLeaderPolicy.BENT_DOCUMENT,
        datum_initial_measurement=callouts.DatumInitialMeasurement.REUSE_POST_POLICY,
        gtol_placement=callouts.GtolPlacement.ARRANGED_NEXT,
    )
    assert result["front"]["count"] == 2
    # Datum: document before/style/final + callout final. Dimension: both
    # document passes + callout final. SF: both document passes/style/final.
    assert sum(a is datum for a, _ in state.snapshots) == 4
    assert sum(a is dimension for a, _ in state.snapshots) == 3
    assert sum(a is sf for a, _ in state.snapshots) == 4
    assert len(dimension.dimension_calls) == 4  # semantics never cached
    assert len(sf.leader_calls) == 1
    assert record.call_count == 3
    assert state.rebuilds == 1


@pytest.mark.parametrize("change", ["entity", "dimension_value", "sf_parameter"])
def test_candidate_keeps_fresh_callout_final_semantic_rejection(monkeypatch, change):
    adapter, view, datum, dimension, state, measure = candidate_setup(monkeypatch)
    sf, _ = add_family_annotations(view)
    original_place = callouts._place

    def place(*args, **kwargs):
        result = original_place(*args, **kwargs)
        if change == "entity":
            datum.entities = (object(),)
        if change == "dimension_value":
            dimension.dimension_value += 0.001
        if change == "sf_parameter":
            sf.parameter = "Ra 6.3"
        return result

    monkeypatch.setattr(callouts, "_place", place)
    with pytest.raises(RuntimeError, match="changed"):
        callouts.arrange_native_callouts(
            adapter,
            views={"front": view},
            measure_annotation=measure,
            datum_leader_policy=callouts.DatumLeaderPolicy.BENT_DOCUMENT,
            datum_initial_measurement=callouts.DatumInitialMeasurement.REUSE_POST_POLICY,
            gtol_placement=callouts.GtolPlacement.ARRANGED_NEXT,
        )


def test_candidate_cannot_bypass_document_final_fixed_ink_guard(monkeypatch):
    adapter, view, datum, dimension, state, measure = candidate_setup(monkeypatch)

    def drift(native_adapter, annotation):
        measured = measure(native_adapter, annotation)
        if annotation is dimension and state.writes:
            measured.body = measured.body.translated((0.01, 0))
        return measured

    with pytest.raises(RuntimeError, match="non-datum native body"):
        callouts.arrange_native_callouts(
            adapter,
            views={"front": view},
            measure_annotation=drift,
            datum_leader_policy=callouts.DatumLeaderPolicy.BENT_DOCUMENT,
            datum_initial_measurement=callouts.DatumInitialMeasurement.REUSE_POST_POLICY,
        )


@pytest.mark.parametrize(
    "field", ["active_document", "sheet", "source", "configuration"]
)
def test_full_candidate_rejects_mid_inventory_context_change_before_any_callout_write(
    monkeypatch, field
):
    adapter, view, datum, dimension, state, measure = candidate_setup(monkeypatch)
    sf, _ = add_family_annotations(view)
    original = callouts._initial_callout_witness

    def changed(*args):
        result = original(*args)
        if field == "active_document":
            adapter.swApp.ActiveDoc = object()
        if field == "sheet":
            adapter.currentModel.GetCurrentSheet = lambda: object()
        if field == "source":
            view.ReferencedDocument = object()
        if field == "configuration":
            view.ReferencedConfiguration = "Other"
        return result

    monkeypatch.setattr(callouts, "_initial_callout_witness", changed)
    record = Mock()
    with pytest.raises(RuntimeError, match="changed"):
        callouts.arrange_native_callouts(
            adapter,
            views={"front": view},
            measure_annotation=measure,
            record_measurement=record,
            datum_leader_policy=callouts.DatumLeaderPolicy.BENT_DOCUMENT,
            datum_initial_measurement=callouts.DatumInitialMeasurement.REUSE_POST_POLICY,
            gtol_placement=callouts.GtolPlacement.ARRANGED_NEXT,
        )
    assert datum.moves == sf.moves == sf.leader_calls == []
    record.assert_not_called()


def test_all_initial_view_inventories_complete_before_any_sf_mutation(monkeypatch):
    adapter, view, datum, dimension, state, measure = candidate_setup(monkeypatch)
    sf, _ = add_family_annotations(view)
    other_sf = NativeAnnotation(7)
    other_sf.BentLeaderLength = -1.0
    other_sf.position = (0.35, 0.35, 0)
    other = SimpleNamespace(**vars(view))
    other.GetName2 = lambda: "Right"
    other.GetAnnotations = lambda: (other_sf,)
    other.GetAnnotationsByType = lambda kind: (other_sf,) if kind == 7 else ()
    other_sf.Owner = other
    sheet_view = adapter.currentModel.GetViews()[0][0]
    adapter.currentModel.GetViews = lambda: ((sheet_view, view, other),)
    events = []
    initial = callouts._initial_callout_witness

    def capture(*args):
        result = initial(*args)
        events.append(("initial", args[1].GetName2()))
        return result

    monkeypatch.setattr(callouts, "_initial_callout_witness", capture)
    for symbol in (sf, other_sf):
        native_style = symbol.SetLeader3

        def style(*args, native_style=native_style):
            assert events[:2] == [("initial", "Front"), ("initial", "Right")]
            events.append(("style",))
            return native_style(*args)

        symbol.SetLeader3 = style
    report = callouts.arrange_native_callouts(
        adapter,
        views={"front": view, "right": other},
        measure_annotation=measure,
        datum_leader_policy=callouts.DatumLeaderPolicy.BENT_DOCUMENT,
        datum_initial_measurement=callouts.DatumInitialMeasurement.REUSE_POST_POLICY,
        gtol_placement=callouts.GtolPlacement.ARRANGED_NEXT,
    )
    assert report["front"]["count"] == 2 and report["right"]["count"] == 1
    assert events == [
        ("initial", "Front"),
        ("initial", "Right"),
        ("style",),
        ("style",),
    ]


def test_nonreused_anchorless_centerline_still_has_fresh_initial_strokes(monkeypatch):
    handoff, adapter, view, annotation, measured, fresh, inventory = strict_context(
        monkeypatch
    )
    # Independent new bank because sealed banks cannot be extended.
    handoff.close()
    centerline = NativeAnnotation(15)
    centerline.Owner = view
    centerline.GetPosition = lambda: None
    inventory[centerline.GetName()] = centerline
    handoff = module.AnnotationMeasurementHandoff(
        adapter,
        views={"front": view},
        measure_annotation=fresh,
        purpose=module.HandoffPurpose.POST_DATUM_CALLOUTS,
        inventory_of=lambda _: dict(inventory),
    )
    rows = {
        key: SimpleNamespace(
            annotation=item, owner=view, kind=item.GetType(), measurement=measured
        )
        for key, item in inventory.items()
    }
    handoff.record_bank(view, rows, source=view.ReferencedDocument)
    handoff.seal()
    with handoff.read_scope():
        assert handoff.initial_measure(adapter, centerline) is fresh.return_value
        assert handoff.initial_measure(adapter, annotation) is measured
    fresh.assert_called_once_with(adapter, centerline)
    handoff.close()


def test_default_remains_fresh_and_opt_in_requires_document_policy(monkeypatch):
    adapter, view, datum, dimension, state, measure = candidate_setup(monkeypatch)
    callouts.arrange_native_callouts(
        adapter,
        views={"front": view},
        measure_annotation=measure,
        datum_leader_policy=callouts.DatumLeaderPolicy.BENT_DOCUMENT,
    )
    assert sum(a is dimension for a, _ in state.snapshots) == 4
    with pytest.raises(ValueError, match="completed bent-document"):
        callouts.arrange_native_callouts(
            adapter,
            views={"front": view},
            measure_annotation=measure,
            datum_initial_measurement=callouts.DatumInitialMeasurement.REUSE_POST_POLICY,
        )


@pytest.mark.parametrize("stage", ["begin", "end"])
def test_post_datum_context_drift_inside_inventory_reader_is_rejected(
    monkeypatch, stage
):
    handoff, adapter, view, annotation, measured, fresh, inventory = strict_context(
        monkeypatch
    )
    if stage == "end":
        handoff.begin_read()
        handoff.initial_measure(adapter, annotation)

    def inventory_of(_):
        view.Position = (0.15, 0.2)
        return dict(inventory)

    handoff._inventory_of = inventory_of
    with pytest.raises(RuntimeError, match="context changed"):
        handoff.begin_read() if stage == "begin" else handoff.end_read()


def test_post_datum_bank_cannot_record_again_or_read_without_completion(monkeypatch):
    handoff, adapter, view, annotation, measured, fresh, _ = strict_context(monkeypatch)
    with pytest.raises(RuntimeError, match="not recording"):
        handoff.record_bank(view, {}, source=view.ReferencedDocument)
    with pytest.raises(RuntimeError, match="all views"):
        handoff.begin_read(view)
    handoff.begin_read()
    with pytest.raises(RuntimeError, match="completion"):
        handoff.close()
    handoff.end_read()
    handoff.close()


def test_project_option_is_forwarded_without_changing_final_measurement_callbacks(
    monkeypatch,
):
    import _drawing_project_layout as project
    import _drawing_native_gtol as gtol
    import _drawing_native_layout as layout
    import _drawing_annotation_bounds as bounds

    monkeypatch.setattr(project, "_early_bound", lambda value, _: value)
    sheet = SimpleNamespace(GetProperties2=lambda: (8, 12, 1, 1, 0, 0.4318, 0.2794, 0))
    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(GetCurrentSheet=lambda: sheet)
    )
    monkeypatch.setattr(
        module, "AnnotationMeasurementHandoff", Mock(side_effect=(Mock(), Mock()))
    )
    arrange = Mock()
    monkeypatch.setattr(callouts, "arrange_native_callouts", arrange)
    monkeypatch.setattr(gtol, "arrange_native_gtol_columns", Mock())
    pack = Mock(
        return_value=SimpleNamespace(status=layout.NativeLayoutStatus.UNCHANGED)
    )
    monkeypatch.setattr(layout, "repair_native_layout", pack)
    monkeypatch.setattr(project._telemetry, "info", Mock())
    # Production telemetry calls asdict; retain the actual report dataclass.
    from test_project_native_layout_drawing import Report

    pack.return_value = Report(layout.NativeLayoutStatus.UNCHANGED, "unchanged")
    project.repair_project_drawing_layout(
        adapter,
        views={"front": object()},
        datum_leader_policy=callouts.DatumLeaderPolicy.BENT_DOCUMENT,
        datum_initial_measurement=callouts.DatumInitialMeasurement.REUSE_POST_POLICY,
    )
    assert (
        arrange.call_args.kwargs["datum_initial_measurement"]
        is callouts.DatumInitialMeasurement.REUSE_POST_POLICY
    )
    assert pack.call_args.kwargs["measure_annotation"] is bounds.annotation_box
    assert callable(pack.call_args.kwargs["final_annotation_validation"])


@pytest.mark.parametrize("content", ["empty", "hidden_sf", "dimension_only"])
def test_candidate_covers_empty_hidden_only_and_no_callout_views(monkeypatch, content):
    adapter, view, datum, dimension, state, measure = candidate_setup(monkeypatch)
    other = SimpleNamespace(**vars(view))
    other.GetName2 = lambda: "Right"
    item = NativeAnnotation(7 if content == "hidden_sf" else 4)
    item.Owner = other
    item.Visible = 3 if content == "hidden_sf" else 1
    item.position = (0.3, 0.3, 0)
    inventory = () if content == "empty" else (item,)
    other.GetAnnotations = lambda: inventory
    other.GetAnnotationsByType = lambda kind: tuple(
        annotation for annotation in inventory if annotation.kind == kind
    )
    sheet_view = adapter.currentModel.GetViews()[0][0]
    adapter.currentModel.GetViews = lambda: ((sheet_view, view, other),)
    report = callouts.arrange_native_callouts(
        adapter,
        views={"front": view, "right": other},
        measure_annotation=measure,
        datum_leader_policy=callouts.DatumLeaderPolicy.BENT_DOCUMENT,
        datum_initial_measurement=callouts.DatumInitialMeasurement.REUSE_POST_POLICY,
    )
    assert report["right"] == {"count": 0}
    assert item.leader_calls == item.moves == []
    assert sum(annotation is item for annotation, _ in state.snapshots) == (
        2 if content == "dimension_only" else 0
    )
