"""Native whole-bank candidates stay bounded and cannot bypass final witnesses."""

from types import SimpleNamespace

import pytest

import _drawing_native_gtol as policy
from _drawing_annotation_bounds import LeaderGeometry, Segment
from _drawing_view_packing import Rect
from test_right_gtol_column_probe import (
    lever_crossing_fixture,
    native_all_around_fixture,
)
from test_native_gtol_drawing import native_context


@pytest.mark.parametrize("clear_at", [1, 2, 3, 6, 7])
def test_candidate_budget_uses_immutable_seed_and_actual_native_route(
    monkeypatch, clear_at
):
    leaders, cells, _ = lever_crossing_fixture()
    decorations = native_all_around_fixture()
    seed = {
        "frame": SimpleNamespace(
            position=(0.3, 0.165, 0),
            body=Rect(0.3, 0.158, 0.34, 0.165),
            annotation=object(),
        )
    }
    cells["frame"] = SimpleNamespace(kind=5, text_boxes=(), text_runs=())
    moves, reads = [], []

    def move(original, deltas, stage):
        assert original is seed
        dx, dy = deltas["frame"]
        moves.append((dx, dy))
        return {
            "frame": SimpleNamespace(
                position=(0.3 + dx, 0.165 + dy, 0),
                body=seed["frame"].body.translated((dx, dy)),
                annotation=seed["frame"].annotation,
            )
        }

    def read(annotation):
        assert annotation is seed["frame"].annotation
        reads.append(annotation)
        if len(reads) >= clear_at:
            return LeaderGeometry((), ())
        return LeaderGeometry(leaders["frame"], decorations["frame"])

    monkeypatch.setattr(policy, "_move_bank", move)
    monkeypatch.setattr(
        policy,
        "_read_gtols",
        lambda *_: pytest.fail("candidate performed full frame/font/XML read"),
    )
    arguments = dict(gap_m=0.002, read_geometry=read)
    if clear_at == 7:
        with pytest.raises(RuntimeError, match="six-candidate bound"):
            policy._place_clear_column(
                seed, seed, cells, Rect(0.08, 0.148, 0.287, 0.172), (), **arguments
            )
        assert len(moves) == 6
        return
    predicted, actual, attempts = policy._place_clear_column(
        seed, seed, cells, Rect(0.08, 0.148, 0.287, 0.172), (), **arguments
    )
    assert len(moves) == len(reads) == len(attempts) == clear_at
    assert predicted["frame"].position == pytest.approx(
        (0.3 + moves[-1][0], 0.165 + moves[-1][1], 0)
    )
    assert actual["frame"] == LeaderGeometry((), ())
    if clear_at >= 3:
        # Both sides get a native baseline, then the latest side's measured UP.
        assert moves[0][1] == moves[1][1] == 0
        assert moves[2][1] == pytest.approx(0.0054029914697259)


def test_zero_absolute_offset_is_not_mistaken_for_noop_after_another_candidate(
    monkeypatch,
):
    adapter, view, rows, measure = native_context(monkeypatch, count=1)
    original = policy._read_gtols(adapter, view, measure)
    rows[0].position[0] += 0.02
    restored = policy._move_bank(
        original, {"GTol0": (0, 0)}, "absolute original candidate"
    )
    assert restored["GTol0"].position == original["GTol0"].position
    rows[0].SetPosition2.assert_called_once_with(*original["GTol0"].position)


@pytest.mark.parametrize("mutation", ["route", "decoration", "display"])
def test_final_full_native_witness_rejects_route_or_display_drift(mutation):
    raw = (Segment((0.1, 0.2), (0.3, 0.2)),)
    geometry = {"frame": LeaderGeometry(raw, ())}
    full = SimpleNamespace(
        native_leader_segments=raw, leader_decorations=(), leader_segments=raw
    )
    if mutation == "route":
        full.native_leader_segments = (Segment((0.1, 0.2), (0.31, 0.2)),)
    if mutation == "decoration":
        full.leader_decorations = (Rect(0.2, 0.2, 0.21, 0.21),)
    if mutation == "display":
        full.leader_segments = (Segment((0.1, 0.21), (0.3, 0.21)),)
    with pytest.raises(
        RuntimeError, match="differs from candidate|does not cover every displayed"
    ):
        policy._final_leader_witness(
            geometry, {"frame": SimpleNamespace(measurement=full)}
        )


def test_obstacles_are_measured_once_after_commands_not_once_per_candidate(monkeypatch):
    adapter, view, rows, measure = native_context(monkeypatch, count=3)
    obstacle = SimpleNamespace(
        GetName=lambda: "dimension", position=[0.01, 0.85, 0], size=(0.1, 0.1)
    )
    view.GetAnnotationsByType.side_effect = lambda kind: (
        rows if kind == 5 else [obstacle] if kind == 4 else ()
    )
    observations = []

    def measured(adapter, annotation):
        observations.append((annotation, adapter.swApp.RunCommand.call_count))
        return measure(adapter, annotation)

    policy.arrange_native_gtol_columns(
        adapter, views={"front": view}, measure_annotation=measured
    )
    assert [commands for obj, commands in observations if obj is obstacle] == [2]
    for annotation in rows:
        assert sum(obj is annotation for obj, _ in observations) == 2
