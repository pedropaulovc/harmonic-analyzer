"""Conservative native leader/text-cell crossing and alternative column contracts."""

from types import SimpleNamespace

import pytest

from _drawing_annotation_bounds import Segment
from _drawing_leader_clearance import intersects_cell, VerticalDirection
from _drawing_view_packing import Rect
from probe_drawing_right_gtol_column import (
    right_translation,
    crossing_records,
    _same_native,
    _same_saved_frames,
    vertical_candidates,
    _candidate_trials,
    prove_narrow_reader,
    displayed_leader_coverage,
)


@pytest.mark.parametrize("change", ["none", "segment", "decoration"])
def test_narrow_native_reader_requires_exact_full_snapshot_parity(monkeypatch, change):
    import probe_drawing_right_gtol_column as module

    segments = (Segment((0.1, 0.2), (0.3, 0.2)),)
    decorations = (Rect(0.1, 0.1, 0.11, 0.11),)
    actual = SimpleNamespace(
        segments=segments
        if change != "segment"
        else (Segment((0.1, 0.2), (0.31, 0.2)),),
        decorations=decorations
        if change != "decoration"
        else (Rect(0.1, 0.1, 0.12, 0.12),),
    )
    monkeypatch.setattr(module, "annotation_leader_geometry", lambda _: actual)
    bank = {"frame": SimpleNamespace(annotation=object())}
    measured = {
        "frame": SimpleNamespace(
            leader_segments=segments,
            native_leader_segments=segments,
            leader_decorations=decorations,
        )
    }
    if change != "none":
        with pytest.raises(RuntimeError, match="narrow/full"):
            prove_narrow_reader(bank, measured)
        return
    report = prove_narrow_reader(bank, measured)
    assert report["count"] == 1
    assert report["elapsed_s"] >= 0


def test_display_strokes_may_reverse_or_be_shortened_but_must_be_fully_covered():
    native = SimpleNamespace(
        segments=(Segment((0, 0), (1, 0)),), decorations=(Rect(0.9, -0.1, 1.1, 0.1),)
    )
    displayed = (
        Segment((1, 0), (0, 0)),
        Segment((0.2, 0), (0.7, 0)),
        Segment((1, -0.05), (1, 0.05)),
        Segment((0.4, 0.2), (0.5, 0.2)),
    )
    result = displayed_leader_coverage(native, displayed)
    assert result["coverage"][0]["native_container_indices"] == [0]
    assert result["coverage"][1]["native_container_indices"] == [0]
    assert result["coverage"][2]["decoration_container_indices"] == [0]
    assert result["uncovered_display_indices"] == [3]


def test_raw_parity_does_not_hide_uncovered_displayed_leader(monkeypatch):
    import probe_drawing_right_gtol_column as module

    raw = (Segment((0.1, 0.2), (0.3, 0.2)),)
    monkeypatch.setattr(
        module,
        "annotation_leader_geometry",
        lambda _: SimpleNamespace(segments=raw, decorations=()),
    )
    measured = SimpleNamespace(
        native_leader_segments=raw,
        leader_decorations=(),
        leader_segments=(Segment((0.1, 0.21), (0.3, 0.21)),),
    )
    with pytest.raises(RuntimeError, match="does not cover every displayed"):
        prove_narrow_reader(
            {"frame": SimpleNamespace(annotation=object())}, {"frame": measured}
        )


@pytest.mark.parametrize(
    "start,end,expected",
    [
        ((0, 0.5), (2, 0.5), True),
        ((0, 2), (2, 2), False),
        ((0.5, 0.5), (0.5, 0.5), True),
        ((0, 0), (1, 1), True),
        ((-2, -2), (-1, -1), False),
    ],
)
def test_clipping_includes_touching_and_handles_degenerate_segments(
    start, end, expected
):
    assert (
        intersects_cell(Segment(start, end), Rect(0.25, 0.25, 0.75, 0.75)) is expected
    )


def test_right_column_keeps_y_and_clears_dimension_on_its_ray():
    delta = right_translation(
        Rect(0, 0, 0.02, 0.05),
        Rect(0.03, 0, 0.1, 0.1),
        (Rect(0.105, 0, 0.13, 0.05), Rect(0.3, 0.2, 0.4, 0.3)),
    )
    assert delta == pytest.approx((0.133, 0))


def test_crossing_report_excludes_intentional_own_frame_join():
    box = SimpleNamespace(
        kind=4,
        text_boxes=(Rect(0.25, 0.25, 0.75, 0.75),),
        text_runs=(SimpleNamespace(value="127"),),
    )
    rows = crossing_records(
        {"frame": (Segment((0, 0.5), (1, 0.5)),)},
        {"frame": box, "dim": box},
        {"frame": ()},
    )
    assert len(rows) == 1
    assert rows[0]["target_annotation"] == "dim"
    assert rows[0]["target_text"] == ["127"]


def test_exact_entity_replacement_cannot_hide_behind_same_dimension_type():
    app = SimpleNamespace(IsSame=lambda a, b: int(a is b))
    annotation, entity = object(), object()
    before = {"dim": (annotation, 4, (entity,), (1,))}
    _same_native(app, before, before)
    with pytest.raises(RuntimeError, match="identity changed"):
        _same_native(app, before, {"dim": (annotation, 4, (object(),), (1,))})


@pytest.mark.parametrize(
    "field,value",
    [
        ("frames", ("differentXML",)),
        ("text", ("different tolerance",)),
        ("position", (0.1, 0.205, 0)),
    ],
)
def test_saved_frame_witness_rejects_content_or_layout_change(field, value):
    row = {
        "frames": ("nativeXML",),
        "text": ("0.05 A B",),
        "format": ("font",),
        "attachment_types": (1,),
        "position": (0.1, 0.2, 0),
        "body": (0.1, 0.2, 0.13, 0.207),
    }
    _same_saved_frames({"frame": row}, {"frame": row})
    with pytest.raises(RuntimeError, match="saved/reopened"):
        _same_saved_frames({"frame": row}, {"frame": {**row, field: value}})


def lever_crossing_fixture():
    leaders = {
        "frame": (
            Segment(
                (0.30007929877717765, 0.16173271196879385),
                (0.2937292987771776, 0.16173271196879385),
            ),
            Segment(
                (0.2937292987771776, 0.16173271196879385),
                (0.26468719797395834, 0.16523271196879386),
            ),
        )
    }
    cell = Rect(
        0.28695150348791637,
        0.15880583677185306,
        0.29602250348791637,
        0.16438570343851974,
    )
    measured = {
        "RD3": SimpleNamespace(
            kind=4, text_boxes=(cell,), text_runs=(SimpleNamespace(value="9.50"),)
        )
    }
    return leaders, measured, crossing_records(leaders, measured, {"frame": ()})


def test_vertical_candidates_come_from_native_elbow_and_measured_text_cell():
    leaders, _measured, crossings = lever_crossing_fixture()
    candidates = vertical_candidates(crossings, leaders, {"frame": ()})
    assert [row.direction for row in candidates] == [
        VerticalDirection.UP,
        VerticalDirection.DOWN,
    ]
    assert [row.dy_m for row in candidates] == pytest.approx(
        [0.0036529914697259, -0.0039268751969408]
    )


def test_vertical_candidate_offsets_do_not_depend_on_sheet_translation():
    leaders, measured, crossings = lever_crossing_fixture()
    delta = (0.1, -0.04)
    shifted_leaders = {
        name: tuple(
            Segment(
                (s.start[0] + delta[0], s.start[1] + delta[1]),
                (s.end[0] + delta[0], s.end[1] + delta[1]),
            )
            for s in segments
        )
        for name, segments in leaders.items()
    }
    shifted_measured = {
        name: SimpleNamespace(
            kind=value.kind,
            text_boxes=tuple(cell.translated(delta) for cell in value.text_boxes),
            text_runs=value.text_runs,
        )
        for name, value in measured.items()
    }
    first = vertical_candidates(crossings, leaders, {"frame": ()})
    second = vertical_candidates(
        crossing_records(shifted_leaders, shifted_measured, {"frame": ()}),
        shifted_leaders,
        {"frame": ()},
    )
    assert [row.dy_m for row in first] == pytest.approx([row.dy_m for row in second])


def test_unproven_leader_chain_shape_does_not_get_a_nominal_elbow():
    leaders, _, crossings = lever_crossing_fixture()
    with pytest.raises(ValueError, match="three-point"):
        vertical_candidates(crossings, {"frame": leaders["frame"][:1]}, {"frame": ()})


def native_all_around_fixture():
    # Captured native RIGHT-column all-around circle bounds, not a nominal radius.
    return {
        "frame": (
            Rect(
                0.2919792987771776,
                0.15998271196879385,
                0.2954792987771776,
                0.16348271196879385,
            ),
        )
    }


def test_leader_decoration_inventory_cannot_be_silently_omitted():
    leaders, measured, _ = lever_crossing_fixture()
    with pytest.raises(ValueError, match="explicit decoration inventory"):
        crossing_records(leaders, measured, {})


def test_native_circle_requires_more_lift_than_its_leader_centerline():
    leaders, measured, lines_only = lever_crossing_fixture()
    decorations = native_all_around_fixture()
    crossings = crossing_records(leaders, measured, decorations)
    assert crossings[0]["segments"] == [0, 1]
    assert crossings[0]["decorations"] == [0]
    line_lift = vertical_candidates(lines_only, leaders, {"frame": ()})[0].dy_m
    lifted_decoration = {
        "frame": tuple(box.translated((0, line_lift)) for box in decorations["frame"])
    }
    remaining = crossing_records({"frame": ()}, measured, lifted_decoration)
    assert remaining[0]["segments"] == []
    assert remaining[0]["decorations"] == [0]
    candidates = vertical_candidates(crossings, leaders, decorations)
    assert [row.dy_m for row in candidates] == pytest.approx(
        [0.0054029914697259, -0.0056768751969408]
    )
    for candidate in candidates:
        moved = {
            "frame": tuple(
                box.translated((0, candidate.dy_m)) for box in decorations["frame"]
            )
        }
        assert crossing_records({"frame": ()}, measured, moved) == []


def test_decoration_only_crossing_uses_its_native_bounds_without_inventing_elbow():
    _, measured, _ = lever_crossing_fixture()
    decorations = native_all_around_fixture()
    leaders = {"frame": ()}
    crossings = crossing_records(leaders, measured, decorations)
    assert crossings[0]["segments"] == []
    assert [
        row.dy_m for row in vertical_candidates(crossings, leaders, decorations)
    ] == pytest.approx([0.0054029914697259, -0.0056768751969408])


def test_decoration_offsets_are_translation_independent():
    leaders, measured, _ = lever_crossing_fixture()
    decorations = native_all_around_fixture()
    delta = (0.2, -0.06)
    shifted_decorations = {
        name: tuple(box.translated(delta) for box in boxes)
        for name, boxes in decorations.items()
    }
    shifted_cells = {
        name: SimpleNamespace(
            kind=row.kind,
            text_boxes=tuple(box.translated(delta) for box in row.text_boxes),
            text_runs=row.text_runs,
        )
        for name, row in measured.items()
    }
    original = vertical_candidates(
        crossing_records({"frame": ()}, measured, decorations),
        {"frame": ()},
        decorations,
    )
    shifted = vertical_candidates(
        crossing_records({"frame": ()}, shifted_cells, shifted_decorations),
        {"frame": ()},
        shifted_decorations,
    )
    assert [row.dy_m for row in original] == pytest.approx(
        [row.dy_m for row in shifted]
    )


def test_native_decoration_readback_rejects_line_clear_candidate():
    leaders, measured, _ = lever_crossing_fixture()
    decorations = native_all_around_fixture()
    crossings = crossing_records(leaders, measured, decorations)
    original = {
        "frame": SimpleNamespace(
            position=(0.3, 0.165, 0), body=Rect(0.3, 0.158, 0.34, 0.165)
        )
    }
    attempts = []

    def move(seed, deltas, _stage):
        assert seed is original
        dy = deltas["frame"][1]
        return {
            "frame": SimpleNamespace(
                position=(0.3, 0.165 + dy, 0),
                body=seed["frame"].body.translated((0, dy)),
            )
        }

    direction, _, rows = _candidate_trials(
        original,
        measured,
        leaders,
        decorations,
        crossings,
        Rect(0.08, 0.148, 0.287, 0.172),
        (),
        move_bank=move,
        read_leaders=lambda _: {"frame": ()},
        # Actual native rerouting remains blocked despite clear open segments.
        read_decorations=lambda _: decorations,
        attempts=attempts,
    )
    assert direction is None
    assert len(rows) == 2
    assert all(row["crossings"][0]["segments"] == [] for row in rows)
    assert all(row["crossings"][0]["decorations"] == [0] for row in rows)


@pytest.mark.parametrize("clear_at", [1, 2, 3])
def test_native_candidate_screen_is_bounded_and_uses_original_right_seed(
    monkeypatch, clear_at
):
    import probe_drawing_right_gtol_column as module

    leaders, measured, crossings = lever_crossing_fixture()
    original = {
        "frame": SimpleNamespace(
            position=(0.30007929877717765, 0.16523271196879386, 0),
            body=Rect(
                0.30007929877717765,
                0.15823271196879385,
                0.3388272168707547,
                0.16523271196879386,
            ),
        )
    }
    measured["frame"] = SimpleNamespace(
        kind=5, text_boxes=(original["frame"].body,), text_runs=()
    )
    moves, reads = [], []
    monkeypatch.setattr(
        module,
        "annotation_box",
        lambda *_: pytest.fail("candidate did a full annotation measurement"),
    )

    def move(seed, deltas, stage):
        assert seed is original
        moves.append(deltas["frame"])
        point = (
            seed["frame"].position[0],
            seed["frame"].position[1] + deltas["frame"][1],
            0,
        )
        return {
            "frame": SimpleNamespace(
                position=point, body=seed["frame"].body.translated(deltas["frame"])
            )
        }

    def read(bank):
        reads.append(bank)
        if len(reads) >= clear_at:
            return {
                "frame": (
                    Segment((0.3, 0.2), (0.29, 0.2)),
                    Segment((0.29, 0.2), (0.26, 0.2)),
                )
            }
        return leaders  # native reroute remains blocked despite derived body move

    direction, final, attempts = _candidate_trials(
        original,
        measured,
        leaders,
        {"frame": ()},
        crossings,
        Rect(0.08, 0.148, 0.287, 0.172),
        (),
        move_bank=move,
        read_leaders=read,
        read_decorations=lambda _: {"frame": ()},
        attempts=[],
    )
    assert len(moves) == min(clear_at, 2)
    assert (
        direction
        == {1: VerticalDirection.UP, 2: VerticalDirection.DOWN, 3: None}[clear_at]
    )
    assert final["frame"].position[1] == pytest.approx(
        original["frame"].position[1] + moves[-1][1]
    )
    assert len(attempts) == min(clear_at, 2)
    assert len(attempts[0]["crossings"]) == (0 if clear_at == 1 else 1)


def test_failed_native_move_leaves_its_bounded_attempt_checkpoint():
    leaders, measured, crossings = lever_crossing_fixture()
    seed = {
        "frame": SimpleNamespace(
            position=(0.3, 0.165, 0), body=Rect(0.3, 0.158, 0.34, 0.165)
        )
    }
    attempts = []

    def reject(*_args):
        raise RuntimeError("native position rejected")

    with pytest.raises(RuntimeError, match="native position rejected"):
        _candidate_trials(
            seed,
            measured,
            leaders,
            {"frame": ()},
            crossings,
            Rect(0.08, 0.148, 0.287, 0.172),
            (),
            move_bank=reject,
            read_leaders=lambda _: pytest.fail("read after failed movement"),
            read_decorations=lambda _: pytest.fail("read after failed movement"),
            attempts=attempts,
        )
    assert attempts == [
        {
            "direction": "up",
            "absolute_delta_from_right_m": (0, pytest.approx(0.0036529914697259)),
            "status": "started",
        }
    ]


def test_text_clear_candidate_still_rejected_when_frame_body_hits_dimension():
    leaders, measured, crossings = lever_crossing_fixture()
    seed = {
        "frame": SimpleNamespace(
            position=(0.3, 0.165, 0), body=Rect(0.3, 0.158, 0.34, 0.165)
        )
    }

    def move(original, deltas, _stage):
        dy = deltas["frame"][1]
        return {
            "frame": SimpleNamespace(
                position=(0.3, 0.165 + dy, 0),
                body=original["frame"].body.translated((0, dy)),
            )
        }

    direction, _bank, attempts = _candidate_trials(
        seed,
        measured,
        leaders,
        {"frame": ()},
        crossings,
        Rect(0.08, 0.148, 0.287, 0.172),
        (Rect(0.305, 0.167, 0.33, 0.18),),
        move_bank=move,
        read_leaders=lambda _: {"frame": ()},
        read_decorations=lambda _: {"frame": ()},
        attempts=[],
    )
    assert direction is VerticalDirection.DOWN
    assert attempts[0]["crossings"] == []
    assert attempts[0]["body_clearance"] == "blocked"
