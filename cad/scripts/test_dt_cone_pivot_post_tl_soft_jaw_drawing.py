"""Offline contracts for the cone post vise soft jaw (MHA-DT-005-TL-04)."""

from __future__ import annotations

import re

import pytest

import _config
import draw_dt_cone_pivot_post_tl_soft_jaw as drawing
import dt_cone_pivot_post_spec as post
import dt_cone_pivot_post_tl_soft_jaw_spec as spec
import export_features
from _feature_requirements import limits
from _printed_tolerance import drilled_oversize_mm
from prechips.model import TOLERANCE_REQUIREMENTS

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


# Each printed size -> every exported feature.requirement that owns its band,
# and the printed value it prints. The model dimensions print at their
# DRAWING_PRECISION places; the hole callout prints the drilled hole at two
# places (+drilled oversize/0) and the counterbore at two places.
PRINTED_OWNERS = {
    "PlateLength": ((("jaw_top", "length"),), spec.PLATE_LENGTH),
    "PlateHeight": ((("jaw_top", "height"), ("bed_face", "height")), spec.PLATE_HEIGHT),
    "PlateThick": (
        (("grip_face", "thickness"), ("jaw_seat", "thickness")),
        spec.PLATE_THICK,
    ),
    "BoltLeftX": ((("bolt_left", "station"),), spec.BOLT_LEFT_X),
    "BoltRightX": ((("bolt_right", "station"),), spec.BOLT_RIGHT_X),
    "BoltY": ((("bolt_left", "height"), ("bolt_right", "height")), spec.BOLT_HEIGHT),
}
CALLOUT_OWNERS = {
    "hole dia": (
        (("bolt_left", "dia"), ("bolt_right", "dia")),
        [round(spec.BOLT_HOLE_DIA, 2), round(spec.BOLT_HOLE_DIA, 2) + drilled_oversize_mm()],
    ),
    "counterbore dia": (
        (("bolt_left_counterbore", "dia"), ("bolt_right_counterbore", "dia")),
        limits(round(spec.CBORE_DIA, 2), 2),
    ),
    "counterbore depth": (
        (("bolt_left_counterbore", "depth"), ("bolt_right_counterbore", "depth")),
        limits(round(spec.CBORE_DEPTH, 2), 2),
    ),
}


def test_every_printed_band_has_a_requirement_owner() -> None:
    """One-fact coverage: every printed toleranced size reaches prechips as a
    listed requirement whose band is exactly the band the sheet states."""
    assert set(PRINTED_OWNERS) == set(spec.DRAWING_PRECISION_BY_NAME)
    features = _features()
    expected = {
        printed: (owners, limits(value, spec.DRAWING_PRECISION_BY_NAME[printed]))
        for printed, (owners, value) in PRINTED_OWNERS.items()
    } | CALLOUT_OWNERS
    for printed, (owners, band) in expected.items():
        for name, key in owners:
            assert key in features[name]["requirements"], (printed, name)
            assert features[name][key] == pytest.approx(band, abs=1e-9), (printed, name)


def test_every_exported_band_is_a_requirement() -> None:
    """prechips inspects only the bands a feature lists."""
    for name, feature in _features().items():
        for key, value in feature.items():
            if key in TOLERANCE_REQUIREMENTS and isinstance(value, list) and len(value) == 2:
                assert key in feature["requirements"], (name, key)


def test_number_is_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("dt-cone-pivot-post")["number"]
    number = _config.parts("dt-cone-pivot-post-tl-soft-jaw")["number"]
    assert re.fullmatch(re.escape(parent) + r"-TL-\d{2}", number)


def test_notes_follow_the_simplicity_policy() -> None:
    lines = spec.DRAWING_NOTES.splitlines()
    assert 1 <= len(lines) <= 4
    assert not re.search(r"\d", spec.DRAWING_NOTES)
    assert "GROUND" not in spec.DRAWING_NOTES
