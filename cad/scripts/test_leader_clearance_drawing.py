"""Final native packing snapshots gate internal leader/text clearance cheaply."""

from types import SimpleNamespace

import pytest

from _drawing_annotation_bounds import Segment
from _drawing_leader_clearance import (
    validate_gtol_leader_clearance,
    displayed_leader_coverage,
    intersects_cell,
    stationary_ink_obstacles,
    _candidate_text_cells,
    crossing_records,
)
from _drawing_view_packing import Rect


def measured(kind, *, native=(), display=(), decorations=(), cells=(), body=None):
    if body is None:
        body = Rect(0.35, 0.25, 0.4, 0.3)
    return SimpleNamespace(
        kind=kind,
        native_leader_segments=native,
        native_strokes=display,
        leader_segments=display,
        leader_decorations=decorations,
        text_boxes=cells,
        text_runs=(),
        body=body,
    )


def test_final_measurements_catch_text_moved_after_candidate_screen():
    line = Segment((0.1, 0.2), (0.3, 0.2))
    frame = measured(5, native=(line,), display=(line,))
    assert (
        validate_gtol_leader_clearance(
            {
                "front": {
                    "frame": frame,
                    "dim": measured(4, cells=(Rect(0.15, 0.21, 0.2, 0.22),)),
                }
            }
        )["front"]["gtol_count"]
        == 1
    )
    with pytest.raises(RuntimeError, match="final measured GTol leader/text-cell"):
        validate_gtol_leader_clearance(
            {
                "front": {
                    "frame": frame,
                    "dim": measured(4, cells=(Rect(0.15, 0.19, 0.2, 0.22),)),
                }
            }
        )


def test_final_note_extent_is_checked_even_without_font_cells():
    line = Segment((0.1, 0.2), (0.3, 0.2))
    with pytest.raises(RuntimeError, match="leader/text-cell"):
        validate_gtol_leader_clearance(
            {
                "front": {
                    "frame": measured(5, native=(line,), display=(line,)),
                    "declared-note": measured(6, body=Rect(0.15, 0.19, 0.2, 0.22)),
                }
            }
        )


def test_final_geometry_cannot_omit_an_uncovered_display_stroke():
    raw, displayed = Segment((0.1, 0.2), (0.3, 0.2)), Segment((0.1, 0.21), (0.3, 0.21))
    with pytest.raises(RuntimeError, match="does not cover displayed leader ink"):
        validate_gtol_leader_clearance(
            {"front": {"frame": measured(5, native=(raw,), display=(displayed,))}}
        )


def test_final_arrow_or_all_around_box_cannot_hide_behind_clear_lines():
    with pytest.raises(RuntimeError, match="leader/text-cell"):
        validate_gtol_leader_clearance(
            {
                "front": {
                    "frame": measured(5, decorations=(Rect(0.15, 0.19, 0.17, 0.21),)),
                    "dim": measured(4, cells=(Rect(0.16, 0.19, 0.2, 0.22),)),
                }
            }
        )


def test_final_scopes_do_not_confuse_same_native_name_on_another_view():
    line = Segment((0.1, 0.2), (0.3, 0.2))
    report = validate_gtol_leader_clearance(
        {
            "front": {"frame": measured(5, native=(line,), display=(line,))},
            "top": {"frame": measured(4, cells=(Rect(0.15, 0.19, 0.2, 0.22),))},
        }
    )
    assert report["front"]["displayed_stroke_count"] == 1
    assert report["top"]["gtol_count"] == 0


def test_nonzero_display_width_cannot_hide_behind_zero_width_native_chain():
    native = SimpleNamespace(
        segments=(Segment((0.1, 0.2), (0.3, 0.2)),), decorations=()
    )
    display = (Segment((0.1, 0.2), (0.3, 0.2), 0.00018),)
    assert displayed_leader_coverage(native, display)["uncovered_display_indices"] == [
        0
    ]
    native.decorations = (Rect(0.099, 0.199, 0.301, 0.201),)
    assert displayed_leader_coverage(native, display)["uncovered_display_indices"] == []
    native.decorations = (Rect(0.1, 0.2, 0.3, 0.201),)
    assert displayed_leader_coverage(native, display)["uncovered_display_indices"] == [
        0
    ]


def test_explicit_width_expands_cell_collision_without_assuming_print_preferences():
    cell = Rect(0.15, 0.20005, 0.2, 0.21)
    assert not intersects_cell(Segment((0.1, 0.2), (0.3, 0.2)), cell)
    assert intersects_cell(Segment((0.1, 0.2), (0.3, 0.2), 0.00018), cell)


@pytest.mark.parametrize("width", [-1, float("nan"), float("inf")])
def test_unknown_or_invalid_width_is_not_silently_zero(width):
    stroke = Segment((0.1, 0.2), (0.3, 0.2), width)
    with pytest.raises(ValueError, match="width"):
        displayed_leader_coverage(
            SimpleNamespace(segments=(stroke,), decorations=()), (stroke,)
        )


def test_native_rocker_dimension_extension_crossing_gtol_symbol_is_rejected():
    # Captured datum-policy-79q2phjn: RD3's 8.46 dimension penetrates the
    # position-symbol frame by 2.772 mm although GTol -> text checks are clear.
    extension = Segment(
        (0.20824696752879507, 0.16886630953174836),
        (0.20824696752879507, 0.17966130952459589),
    )
    symbol_frame = Rect(
        0.20583496752879504,
        0.17688934158156538,
        0.21283496752879505,
        0.1838893415815654,
    )
    with pytest.raises(RuntimeError, match="annotation stroke/GTol-body.*RD3"):
        validate_gtol_leader_clearance(
            {
                "front": {
                    "RD3": measured(4, display=(extension,)),
                    # No font cell covers the entire symbol/frame. The frame body
                    # must be checked even without any GTol leader of its own.
                    "position": measured(5, body=symbol_frame),
                }
            }
        )


@pytest.mark.parametrize("kind", [2, 4, 6, 7])
def test_foreign_decoration_also_cannot_overlap_gtol_body(kind):
    with pytest.raises(RuntimeError, match="annotation stroke/GTol-body"):
        validate_gtol_leader_clearance(
            {
                "front": {
                    "foreign": measured(
                        kind, decorations=(Rect(0.3, 0.2, 0.31, 0.21),)
                    ),
                    "frame": measured(5, body=Rect(0.305, 0.205, 0.4, 0.25)),
                }
            }
        )


def test_clear_foreign_strokes_and_own_gtol_join_are_allowed():
    frame = measured(
        5,
        body=Rect(0.3, 0.2, 0.4, 0.25),
        native=(Segment((0.29, 0.21), (0.3, 0.21)),),
    )
    result = validate_gtol_leader_clearance(
        {
            "front": {
                "frame": frame,
                "dimension": measured(4, display=(Segment((0.2, 0.2), (0.2, 0.25)),)),
            }
        }
    )
    assert result["front"]["reverse_crossings"] == []


@pytest.mark.parametrize("kind", [1, 5, 13, 15])
def test_other_gtol_centerline_or_thread_ink_cannot_cross_a_frame(kind):
    source = measured(kind, display=(Segment((0.2, 0.21), (0.35, 0.21)),))
    if kind == 5:
        source.native_leader_segments = source.native_strokes
    else:
        # Centerline/thread ink is body geometry, not an open annotation leader.
        source.leader_segments = ()
    with pytest.raises(RuntimeError, match="annotation stroke/GTol-body"):
        validate_gtol_leader_clearance(
            {
                "front": {
                    "source": source,
                    "target": measured(5, body=Rect(0.3, 0.2, 0.4, 0.25)),
                }
            }
        )


def test_stationary_obstacles_include_displayed_width_and_decorations():
    body = Rect(0.1, 0.1, 0.12, 0.12)
    arrow = Rect(0.14, 0.12, 0.15, 0.13)
    obstacles = stationary_ink_obstacles(
        measured(
            4,
            body=body,
            decorations=(arrow,),
            display=(Segment((0.15, 0.13), (0.2, 0.18), 0.002),),
        )
    )
    assert obstacles[:2] == (body, arrow)
    assert obstacles[2].bounds == pytest.approx((0.149, 0.129, 0.201, 0.181))


@pytest.mark.parametrize("width", [-1, float("nan"), float("inf")])
def test_invalid_stationary_stroke_width_fails_before_planning(width):
    with pytest.raises(ValueError, match="width"):
        stationary_ink_obstacles(
            measured(
                4,
                display=(Segment((0.1, 0.2), (0.3, 0.2), width),),
            )
        )


def test_candidate_screen_includes_another_gtol_symbol_frame_not_only_text():
    original = measured(5, body=Rect(0.3, 0.2, 0.4, 0.25))
    predicted = SimpleNamespace(position=(0.5, 0.2, 0), body=Rect(0.5, 0.2, 0.6, 0.25))
    cells = _candidate_text_cells(
        {"target": original},
        {"target": SimpleNamespace(position=(0.3, 0.2, 0))},
        {"target": predicted},
    )
    hits = crossing_records(
        {"other-gtol": (Segment((0.45, 0.21), (0.52, 0.21)),)},
        cells,
        {"other-gtol": ()},
    )
    assert hits[0]["target_annotation"] == "target"
    assert hits[0]["text_cell"] == predicted.body.bounds


def test_nonfinite_stationary_stroke_fails_before_planning():
    with pytest.raises(ValueError, match="finite"):
        stationary_ink_obstacles(
            measured(
                4,
                display=(Segment((float("nan"), 0.2), (0.3, 0.2)),),
            )
        )
