"""Offline contracts for the cone post cap jaw button (MHA-DT-005-TL-03)."""

from __future__ import annotations

import re

import _config
import draw_dt_cone_pivot_post_tl_cap_jaw_button as drawing
import dt_cone_pivot_post_spec as post
import dt_cone_pivot_post_tl_cap_jaw_button_spec as spec
import export_features


def test_every_marked_dimension_prints_once_at_its_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.PROFILE_KEEP) | set(drawing.DONOR_KEEP) == marked
    assert not set(drawing.PROFILE_KEEP) & set(drawing.DONOR_KEEP)
    # every donated diameter lands on the profile
    assert set(drawing.PROFILE_DIAMETER_XY) == set(drawing.DONOR_KEEP)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked


def test_spigot_drops_into_every_journal_bore_the_post_allows() -> None:
    """The largest spigot keeps a hand clearance in the smallest bore of the
    post's running band; a post change that closes it fails here, not at the
    vise."""
    largest_spigot = spec.SPIGOT_DIA + spec.SPIGOT_BAND[0]
    smallest_bore = post.BORE_DIA + post.RUNNING_BORE_BAND[1]
    assert smallest_bore - largest_spigot >= spec.SPIGOT_HAND_CLEARANCE_MIN


def test_face_bears_on_the_cap_alone_at_its_worst_float() -> None:
    widest_float = (post.BORE_DIA + post.RUNNING_BORE_BAND[0]) - (
        spec.SPIGOT_DIA + spec.SPIGOT_BAND[1]
    )
    largest_face = export_features.requirement_manifest(
        "dt_cone_pivot_post_tl_cap_jaw_button"
    )["features"]["cap_face"]["dia"][1]
    assert largest_face / 2.0 + widest_float / 2.0 < post.CONE_BOSS_DIA / 2.0


def test_exported_spigot_band_is_the_printed_band() -> None:
    spigot = export_features.requirement_manifest(
        "dt_cone_pivot_post_tl_cap_jaw_button"
    )["features"]["spigot"]
    assert spigot["dia"] == [
        round(spec.SPIGOT_DIA + spec.SPIGOT_BAND[1], 2),
        round(spec.SPIGOT_DIA + spec.SPIGOT_BAND[0], 2),
    ]


def test_number_is_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("dt-cone-pivot-post")["number"]
    number = _config.parts("dt-cone-pivot-post-tl-cap-jaw-button")["number"]
    assert re.fullmatch(re.escape(parent) + r"-TL-\d{2}", number)
