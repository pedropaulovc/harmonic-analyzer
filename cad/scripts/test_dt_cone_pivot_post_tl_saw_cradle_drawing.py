"""Offline contracts for the cone post saw cradle (MHA-DT-005-TL-02)."""

from __future__ import annotations

import re

import _config
import draw_dt_cone_pivot_post_tl_saw_cradle as drawing
import dt_cone_pivot_post_spec as post
import dt_cone_pivot_post_tl_saw_cradle_spec as spec
import export_features
from _feature_requirements import limits

STEM = "dt_cone_pivot_post_tl_saw_cradle"


def _features() -> dict:
    return export_features.requirement_manifest(STEM)["features"]


def test_every_marked_dimension_prints_once_at_its_model_places() -> None:
    views = (drawing.FRONT_KEEP, drawing.TOP_KEEP, drawing.RIGHT_KEEP)
    printed = [name for keep in views for name in keep]
    assert len(printed) == len(set(printed))
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(printed) == marked
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked


def test_every_body_the_post_print_allows_bottoms_on_the_seat_line() -> None:
    """The smallest printed seat is no smaller than the largest printed body,
    so the body lies on the seat bottoms and its cap meets the pad; a post
    change that grows the body past the seat fails here, not at the saw."""
    body_max = limits(post.BLOCK_DIA, post.DRAWING_PRECISION_BY_NAME["MainBodyDia"])[1]
    for seat in ("head_seat", "foot_seat"):
        assert _features()[seat]["dia"][0] >= body_max - 1e-9


def test_pad_top_shares_the_printed_seat_bottom_band() -> None:
    features = _features()
    assert features["cap_pad"]["height"] == features["head_seat"]["height"]
    assert features["cap_pad"]["height"] == features["foot_seat"]["height"]
    assert features["cap_pad"]["note"] in spec.DRAWING_NOTES.splitlines()


def test_head_saddle_fits_between_the_head_shoulder_and_the_cone_boss() -> None:
    head = _features()["head_seat"]["length"]
    assert head[1] <= spec.HEAD_GAP_MIN


def test_bridge_studs_clear_the_pad_at_print_worst() -> None:
    """A drawing-compliant pad never fouls a bridge stud's thread: the pad's
    longest print against each stud's one-place station band."""
    features = _features()
    pad_half = features["cap_pad"]["length"][1] / 2.0
    stud_r = spec.THREAD_MAJOR_MM[spec.STUD_THREAD] / 2.0
    for name in ("stud_tap_near", "stud_tap_far"):
        offset = abs(features[name]["at"][2] - features["cap_pad"]["at"][2]) - 0.8
        assert offset - pad_half - stud_r >= spec.WALL_FLOOR_MM


def test_cradle_is_one_piece() -> None:
    """No component definition exists for a built-up cradle, so the export
    must not let prechips plan one."""
    assert export_features.requirement_manifest(STEM)["construction"] == "one_piece"


def test_number_is_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("dt-cone-pivot-post")["number"]
    number = _config.parts("dt-cone-pivot-post-tl-saw-cradle")["number"]
    assert re.fullmatch(re.escape(parent) + r"-TL-\d{2}", number)


def test_notes_follow_the_simplicity_policy() -> None:
    lines = spec.DRAWING_NOTES.splitlines()
    assert 1 <= len(lines) <= 4
    assert not re.search(r"\d", spec.DRAWING_NOTES)
    # the shop has no grinder
    assert not re.search(r"\bGROUND\b|\bGRIND", spec.DRAWING_NOTES)
