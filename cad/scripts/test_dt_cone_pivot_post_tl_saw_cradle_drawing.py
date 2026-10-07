"""Offline contracts for the cone post saw cradle (MHA-DT-005-TL-02)."""

from __future__ import annotations

import re

import _config
import draw_dt_cone_pivot_post_tl_saw_cradle as drawing
import dt_cone_pivot_post_spec as post
import dt_cone_pivot_post_tl_saw_cradle_spec as spec
import export_features
from _feature_requirements import limits
from prechips.model import TOLERANCE_REQUIREMENTS

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
    so every body lies on the seat bottoms; a post change that grows the body
    past the seat fails here, not at the saw."""
    body_max = limits(post.BLOCK_DIA, post.DRAWING_PRECISION_BY_NAME["MainBodyDia"])[1]
    for seat in ("head_seat", "foot_seat"):
        assert _features()[seat]["dia"][0] >= body_max - 1e-9


def test_unfitted_pad_stands_above_every_compliant_cap() -> None:
    """The pad is fitted down to the cap, never built up: its unfitted top
    clears the highest cap any compliant post presents to a seat bored at
    the top of its printed band."""
    body = limits(post.BLOCK_DIA, post.DRAWING_PRECISION_BY_NAME["MainBodyDia"])
    boss = limits(post.CONE_BOSS_LENGTH, post.DRAWING_PRECISION_BY_NAME["ConeBossLen"])
    seat_bottom_max = _features()["head_seat"]["height"][1]
    highest_cap = seat_bottom_max + (body[1] - boss[0]) / 2.0
    assert _features()["cap_pad"]["height_nominal"] - highest_cap >= spec.PAD_FIT_STOCK_MIN


def test_pad_height_is_a_matched_fit_not_a_band() -> None:
    pad = _features()["cap_pad"]
    assert "height" not in pad
    assert "note" in pad["requirements"]
    assert pad["note"] == spec.PAD_FIT_CALLOUT
    assert spec.POST_NUMBER in pad["note"]


def test_every_exported_band_is_a_requirement() -> None:
    """One-fact rule: prechips inspects only the bands a feature lists."""
    for name, feature in _features().items():
        for key, value in feature.items():
            if key in TOLERANCE_REQUIREMENTS and isinstance(value, list) and len(value) == 2:
                assert key in feature["requirements"], (name, key)


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
