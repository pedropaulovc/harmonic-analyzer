"""Offline contracts for the pivot bracket's reworked angle plate (MHA-CH-008-TL-02)."""

from __future__ import annotations

import re

import _config
import ch_pivot_bracket_spec as bracket
import ch_pivot_bracket_tl_angle_plate_spec as spec
import draw_ch_pivot_bracket_tl_angle_plate as drawing
import export_features
from _feature_requirements import limits


def _features() -> dict:
    return export_features.requirement_manifest("ch_pivot_bracket_tl_angle_plate")["features"]


def test_every_marked_dimension_prints_once_at_its_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) | set(drawing.SIDE_KEEP) == marked
    assert not set(drawing.FRONT_KEEP) & set(drawing.SIDE_KEEP)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked


def test_exported_stations_are_the_printed_general_bands() -> None:
    """Every station prints at one place, so prechips sees the title block's
    .X band the shop is held to, not a tighter one."""
    features = _features()
    places = spec.DRAWING_PRECISION_BY_NAME
    for side, x in zip(("left", "right"), spec.TAP_X, strict=True):
        tap = features[f"ledge_tap_{side}"]
        assert tap["station"] == limits(x, places["Tap1X"])
        assert tap["height"] == limits(spec.SCREW_Y, places["Tap1Y"])
    for side, x in zip(("left", "right"), spec.STUD_X, strict=True):
        stud = features[f"stud_hole_{side}"]
        assert stud["station"] == limits(x, places["Stud1X"])
        assert stud["height"] == limits(spec.STUD_Y, places["Stud1Y"])


def test_bracket_seat_lies_on_the_upright_face_above_the_ledge() -> None:
    seat = _features()["seat_face"]
    low, high = seat["bounds"]["y"]
    assert spec.BASE_THICK < low < high <= spec.PLATE_HEIGHT
    assert abs((high - low) - (bracket.FOOT_LEN - spec.PART_PROUD)) < 1e-9
    x_low, x_high = seat["bounds"]["x"]
    assert 0.0 < x_low and x_high < spec.PLATE_LENGTH


def test_stud_holes_clear_the_bracket_foot() -> None:
    """The bridge's studs pass outside the foot's width on the face."""
    seat = _features()["seat_face"]
    stud_r = _features()["stud_hole_left"]["dia"][1] / 2.0
    assert spec.STUD_X[0] + stud_r < seat["bounds"]["x"][0]
    assert spec.STUD_X[1] - stud_r > seat["bounds"]["x"][1]


def test_number_is_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("ch-pivot-bracket")["number"]
    number = _config.parts("ch-pivot-bracket-tl-angle-plate")["number"]
    assert re.fullmatch(re.escape(parent) + r"-TL-\d{2}", number)


def test_notes_follow_the_simplicity_policy() -> None:
    lines = spec.DRAWING_NOTES.splitlines()
    assert 1 <= len(lines) <= 4
    assert not re.search(r"\d", spec.DRAWING_NOTES)
    assert "GROUND" not in spec.DRAWING_NOTES.upper()
