"""Offline contracts for the cone post vise soft jaw (MHA-DT-005-TL-04)."""

from __future__ import annotations

import re

import pytest

import _config
import draw_dt_cone_pivot_post_tl_soft_jaw as drawing
import dt_cone_pivot_post_spec as post
import dt_cone_pivot_post_tl_soft_jaw_spec as spec
import export_features

STEM = "dt_cone_pivot_post_tl_soft_jaw"


def _features() -> dict:
    return export_features.requirement_manifest(STEM)["features"]


def test_every_marked_dimension_prints_once_at_its_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP) == marked
    assert not set(drawing.FRONT_KEEP) & set(drawing.TOP_KEEP)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked


def test_exported_jaw_top_reaches_over_the_caps_and_under_the_head() -> None:
    """At either end of the exported height band, on the S11 parallels, the
    jaw top covers the cone caps at the post's highest axis and stays under
    the head shoulder and the crank boss; a post change that closes either
    gap fails here, not at the vise."""
    low, high = _features()["jaw_top"]["height"]
    cap_top = (
        post.BORE_HEIGHT
        + post.JOURNAL_AXIS_HEIGHT_TOLERANCE_MM
        + (post.CONE_BOSS_DIA + 0.8) / 2.0
    )
    assert low - spec.PARALLEL_HEIGHT > cap_top
    assert high - spec.PARALLEL_HEIGHT < post.HEAD_BASE_Y
    assert high - spec.PARALLEL_HEIGHT < post.CRANK_BORE_HEIGHT - post.CRANK_BOSS_DIA / 2.0


def test_screw_heads_sink_below_the_gripping_face() -> None:
    for side in ("left", "right"):
        cbore = _features()[f"bolt_{side}_counterbore"]
        assert cbore["depth"][0] > spec.JAW_SCREW_HEAD_HEIGHT
        assert cbore["dia"][0] > spec.JAW_SCREW_HEAD_DIA


def test_exported_bolt_stations_are_the_printed_stations_from_one_end() -> None:
    features = _features()
    assert features["bolt_left"]["station"] == [
        round(spec.BOLT_LEFT_X - 0.51, 2),
        round(spec.BOLT_LEFT_X + 0.51, 2),
    ]
    # Symmetric pattern about the plate centre, as the vise's plate is drilled.
    assert spec.BOLT_LEFT_X + spec.BOLT_RIGHT_X == pytest.approx(spec.PLATE_LENGTH)
    for side in ("left", "right"):
        assert features[f"bolt_{side}"]["height"] == [
            round(spec.BOLT_HEIGHT - 0.51, 2),
            round(spec.BOLT_HEIGHT + 0.51, 2),
        ]


def test_number_is_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("dt-cone-pivot-post")["number"]
    number = _config.parts("dt-cone-pivot-post-tl-soft-jaw")["number"]
    assert re.fullmatch(re.escape(parent) + r"-TL-\d{2}", number)


def test_notes_follow_the_simplicity_policy() -> None:
    lines = spec.DRAWING_NOTES.splitlines()
    assert 1 <= len(lines) <= 4
    assert not re.search(r"\d", spec.DRAWING_NOTES)
    assert "GROUND" not in spec.DRAWING_NOTES
