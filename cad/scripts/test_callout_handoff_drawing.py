"""Actual callout-final measurements replace only the GTol obstacle scan."""

from collections import Counter

import pytest

import _drawing_native_callouts as callouts
import _drawing_native_gtol as gtols
import _drawing_measurement_handoff as handoffs
from test_native_callouts_drawing import native_setup, NativeAnnotation
from test_native_gtol_drawing import native_context


def scene(monkeypatch):
    callout_measure = native_setup(monkeypatch)[-1]
    adapter, view, frames, frame_measure = native_context(monkeypatch, count=3)
    monkeypatch.setattr(handoffs, "_early_bound", lambda value, _: value)
    view.Position, view.ScaleRatio = (0.5, 0.5), (1.0, 1.0)
    view.GetReferencedModelName.return_value = "part.SLDPRT"
    view.ReferencedConfiguration = "Default"
    symbols = [NativeAnnotation(kind) for kind in (2, 4, 7)]
    for annotation in symbols:
        annotation.Owner = view
    annotations = [*symbols, *frames]
    view.GetAnnotations.return_value = annotations
    view.GetAnnotationsByType.side_effect = lambda kind: tuple(
        item for item in annotations if int(item.GetType()) == kind
    )
    reads, outputs = Counter(), []

    def measure(adapter, annotation):
        reads[int(annotation.GetType())] += 1
        measured = (
            callout_measure(adapter, annotation)
            if isinstance(annotation, NativeAnnotation)
            else frame_measure(adapter, annotation)
        )
        measured.name, measured.kind = annotation.GetName(), int(annotation.GetType())
        measured.envelope = measured.body
        measured.text_boxes = ()
        # This scene has no external stroke/decorations; keep the fixture's
        # native-bounds schema complete for the strengthened obstacle consumer.
        measured.leader_segments = ()
        measured.leader_decorations = ()
        outputs.append((annotation, measured))
        return measured

    return adapter, view, frames, symbols, measure, reads, outputs


def test_only_actual_callout_final_bounds_are_recorded_after_all_witnesses(monkeypatch):
    adapter, view, frames, symbols, measure, reads, outputs = scene(monkeypatch)
    recorded = []
    callouts.arrange_native_callouts(
        adapter,
        views={"front": view},
        measure_annotation=measure,
        gtol_placement=callouts.GtolPlacement.ARRANGED_NEXT,
        record_measurement=lambda *args: recorded.append(args),
    )
    assert reads == {2: 2, 4: 2, 7: 3}
    assert {annotation.GetType() for _, annotation, _ in recorded} == {2, 4, 7}
    assert len(recorded) == 3
    for owner, annotation, measured in recorded:
        assert owner is view
        actual = [row for item, row in outputs if item is annotation]
        assert measured is actual[-1]
        assert measured is not actual[0]
        assert measured.anchor == annotation.GetPosition()[:2]
    assert len(symbols[1].dimension_calls) == 2
    assert symbols[2].text_ids == list(range(1, 11)) * 3


@pytest.mark.parametrize("policy", ["fresh", "handoff"])
def test_handoff_eliminates_only_three_obstacle_reads_and_preserves_final_checks(
    monkeypatch, policy
):
    adapter, view, frames, symbols, measure, reads, outputs = scene(monkeypatch)
    obstacle = handoffs.AnnotationMeasurementHandoff(
        adapter,
        views={"front": view},
        measure_annotation=measure,
        purpose=handoffs.HandoffPurpose.GTOL_OBSTACLES,
    )
    packing = handoffs.AnnotationMeasurementHandoff(
        adapter,
        views={"front": view},
        measure_annotation=measure,
        purpose=handoffs.HandoffPurpose.INITIAL_PACKING,
    )
    try:
        callouts.arrange_native_callouts(
            adapter,
            views={"front": view},
            measure_annotation=measure,
            gtol_placement=callouts.GtolPlacement.ARRANGED_NEXT,
            record_measurement=obstacle.record,
        )
        obstacle.seal()
        gtols.arrange_native_gtol_columns(
            adapter,
            views={"front": view},
            measure_annotation=measure,
            measure_obstacle=obstacle.initial_measure
            if policy == "handoff"
            else measure,
            obstacle_read_scope=obstacle.read_scope if policy == "handoff" else None,
            record_measurement=packing.record,
        )
        packing.seal()
        reads_before_packing = reads.copy()
        with packing.read_scope():
            for annotation in (*symbols, *frames):
                packing.initial_measure(adapter, annotation)
        assert reads == reads_before_packing
        # The required final packing read is fresh for EVERY annotation.
        for annotation in (*symbols, *frames):
            measure(adapter, annotation)
        assert reads == {
            2: 3 if policy == "handoff" else 4,
            4: 3 if policy == "handoff" else 4,
            7: 4 if policy == "handoff" else 5,
            5: 9,
        }
        assert len(symbols[1].dimension_calls) == 2
        assert symbols[2].text_ids == list(range(1, 11)) * 3
        for frame in frames:
            assert (
                frame.GetSpecificAnnotation.return_value.GetFrameCount.call_count == 2
            )
            assert frame.GetAttachedEntities3.call_count == 2
    finally:
        packing.close()
        obstacle.close()


def test_native_command_moving_fixed_obstacle_cannot_serve_stale_body(monkeypatch):
    adapter, view, frames, symbols, measure, reads, outputs = scene(monkeypatch)
    handoff = handoffs.AnnotationMeasurementHandoff(
        adapter,
        views={"front": view},
        measure_annotation=measure,
        purpose=handoffs.HandoffPurpose.GTOL_OBSTACLES,
    )
    callouts.arrange_native_callouts(
        adapter,
        views={"front": view},
        measure_annotation=measure,
        gtol_placement=callouts.GtolPlacement.ARRANGED_NEXT,
        record_measurement=handoff.record,
    )
    handoff.seal()
    original_command = adapter.swApp.RunCommand.side_effect

    def move_obstacle(command, title):
        symbols[1].position = (0.06, 0.055, 0.0)
        return original_command(command, title)

    adapter.swApp.RunCommand.side_effect = move_obstacle
    with pytest.raises(RuntimeError, match="annotation position changed"):
        gtols.arrange_native_gtol_columns(
            adapter,
            views={"front": view},
            measure_annotation=measure,
            measure_obstacle=handoff.initial_measure,
            obstacle_read_scope=handoff.read_scope,
        )
    assert reads[4] == 2  # no silent fresh baseline after the rejected handoff
    handoff.close()
