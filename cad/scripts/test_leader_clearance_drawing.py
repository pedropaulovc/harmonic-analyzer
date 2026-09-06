"""Final native packing snapshots gate internal leader/text clearance cheaply."""

from types import SimpleNamespace

import pytest

from _drawing_annotation_bounds import Segment
from _drawing_leader_clearance import (
    validate_gtol_leader_clearance,
    displayed_leader_coverage,
    intersects_cell,
)
from _drawing_view_packing import Rect


def measured(kind, *, native=(), display=(), decorations=(), cells=(), body=None):
    return SimpleNamespace(
        kind=kind,
        native_leader_segments=native,
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
