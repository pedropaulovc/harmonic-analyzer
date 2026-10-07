"""Offline contracts for the rocker arm's vise blank-end stop (MHA-CH-006-TL-01)."""

from __future__ import annotations

import re

import _config
import ch_rocker_arm_spec as arm
import ch_rocker_arm_tl_vise_stop_spec as spec
import draw_ch_rocker_arm_tl_vise_stop as drawing
import export_features

STEM = "ch_rocker_arm_tl_vise_stop"


def _features() -> dict:
    return export_features.requirement_manifest(STEM)["features"]


def test_every_marked_dimension_prints_once_at_its_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.ELEVATION_KEEP) | set(drawing.SIDE_KEEP) == marked
    assert not set(drawing.ELEVATION_KEEP) & set(drawing.SIDE_KEEP)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked


def test_nose_stops_the_blank_on_stock_outboard_of_the_finished_arm() -> None:
    """The exported stop point sits on the raw blank end, which lies outboard
    of the parent arm's widest half-span, so the contact mark is cut away."""
    end_x, _y, end_z = _features()["nose_hole"]["end"]
    setup_x = end_x - spec.JAW_HALF_WIDTH
    assert setup_x == spec.BLANK_END_X_SETUP
    assert -setup_x > arm.ROD_TIP_X
    blank_low, blank_high = (z - spec.SETUP_Z_OF_JAW_TOP for z in spec.BLANK_Z_SETUP)
    assert blank_low < end_z - spec.NOSE_PIN_DIA / 2.0
    assert end_z + spec.NOSE_PIN_DIA / 2.0 < blank_high


def test_bonded_nose_pin_ends_at_the_stop_face() -> None:
    """A pin bonded flush with the back face ends at the exported stop X,
    standing proud of the finger front."""
    features = _features()
    back_x = spec.SEAT_X - features["seat_face"]["length_nominal"]
    pin_end_x = back_x + spec.NOSE_PIN_LENGTH
    assert abs(features["nose_hole"]["end"][0] - pin_end_x) < 1e-9
    assert pin_end_x > features["finger_front"]["plane"]["value"]


def test_exported_hole_bands_are_the_printed_drilled_band() -> None:
    features = _features()
    for name, dia in (("nose_hole", spec.NOSE_HOLE_DIA), ("screw_hole", spec.SCREW_HOLE_DIA)):
        assert features[name]["dia"] == [dia, round(dia + spec.DRILLED_BAND[0], 12)]


def test_bond_gap_holds_on_every_pin_and_hole_the_bands_allow() -> None:
    largest_hole = spec.NOSE_HOLE_DIA + spec.DRILLED_BAND[0]
    smallest_hole = spec.NOSE_HOLE_DIA + spec.DRILLED_BAND[1]
    assert largest_hole - spec.NOSE_PIN_DIA <= spec.BOND_GAP_MAX
    assert smallest_hole > spec.NOSE_PIN_MAX


def test_walls_and_screw_engagement_meet_rule_12_at_worst_case() -> None:
    assert min(spec.WALLS.values()) >= spec.RULE12_WALL_TARGET
    assert spec.SCREW_ENGAGEMENT_MIN >= 1.5 * spec.SCREW_MAJOR


def test_number_is_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("ch-rocker-arm")["number"]
    number = _config.parts("ch-rocker-arm-tl-vise-stop")["number"]
    assert re.fullmatch(re.escape(parent) + r"-TL-\d{2}", number)


def test_notes_follow_the_simplicity_policy() -> None:
    lines = spec.DRAWING_NOTES.splitlines()
    assert 1 <= len(lines) <= 4
    assert not re.search(r"\d", spec.DRAWING_NOTES)
    assert not re.search(r"\bGROUND\b|\bGRIND", spec.DRAWING_NOTES)
