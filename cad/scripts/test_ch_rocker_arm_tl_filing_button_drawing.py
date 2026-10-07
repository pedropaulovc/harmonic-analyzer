"""Offline contracts for the rocker arm hub filing kit (MHA-CH-006-TL-04/-05)."""

from __future__ import annotations

import re

import _config
import ch_rocker_arm_spec as rocker
import ch_rocker_arm_tl_filing_button_spec as button
import ch_rocker_arm_tl_filing_stud_spec as stud
import draw_ch_rocker_arm_tl_filing_button as button_drawing
import draw_ch_rocker_arm_tl_filing_stud as stud_drawing
import export_features
import pytest
from _feature_requirements import limits

BUTTON = "ch_rocker_arm_tl_filing_button"
STUD = "ch_rocker_arm_tl_filing_stud"


def _features(stem: str) -> dict:
    return export_features.requirement_manifest(stem)["features"]


def test_every_marked_dimension_prints_once() -> None:
    marked = set().union(*button.DRAWING_DIMENSIONS.values())
    assert set(button_drawing.FACE_KEEP) | set(button_drawing.EDGE_KEEP) == marked
    assert not set(button_drawing.FACE_KEEP) & set(button_drawing.EDGE_KEEP)
    marked = set().union(*stud.DRAWING_DIMENSIONS.values())
    assert set(stud_drawing.PROFILE_KEEP) | set(stud_drawing.DONOR_KEEP) == marked
    assert not set(stud_drawing.PROFILE_KEEP) & set(stud_drawing.DONOR_KEEP)
    assert set(stud_drawing.PROFILE_DIAMETER_XY) == set(stud_drawing.DONOR_KEEP)


def test_rim_is_the_hub_filing_line() -> None:
    """The filed hub ends at the rim: every button the band allows lies inside
    the hub's printed O.D. band."""
    low, high = _features(BUTTON)["rim"]["dia"]
    hub_low, hub_high = limits(rocker.HUB_DIA, 2)
    assert hub_low <= low < high <= hub_high
    assert low < rocker.HUB_DIA < high


def test_stud_slips_into_the_smallest_pivot_bore_and_button_bore() -> None:
    body_high = _features(STUD)["locating_body"]["dia"][1]
    assert rocker.PIVOT_HOLE_DIA + rocker.PIVOT_HOLE_BAND[1] - body_high >= stud.BODY_CLEARANCE_MIN
    assert _features(BUTTON)["bore"]["dia"][0] - body_high >= stud.BODY_CLEARANCE_MIN


def test_body_carries_the_hub_and_stays_inside_the_stack() -> None:
    """At every printed button thickness and hub length the whole hub sits on
    the lapped body, and the nut lands on the upper button (body short of the
    stack top)."""
    body_low, body_high = _features(STUD)["locating_body"]["length"]
    thick_low, thick_high = _features(BUTTON)["hub_seat_face"]["thickness"]
    hub_high = rocker.HUB_LENGTH + rocker.HUB_LENGTH_BAND[0]
    assert body_high < 2 * thick_low + rocker.HUB_LENGTH
    assert body_low > thick_high + hub_high


def test_head_seat_lands_on_the_button_face_outside_its_bore() -> None:
    head = stud.HEAD_DIA
    assert _features(BUTTON)["bore"]["dia"][1] < head < _features(BUTTON)["rim"]["dia"][0]


@pytest.mark.parametrize("dashed", ["ch-rocker-arm-tl-filing-button", "ch-rocker-arm-tl-filing-stud"])
def test_number_is_the_parent_number_plus_a_tool_suffix(dashed: str) -> None:
    parent = _config.parts("ch-rocker-arm")["number"]
    assert re.fullmatch(re.escape(parent) + r"-TL-\d{2}", _config.parts(dashed)["number"])


@pytest.mark.parametrize("notes", [button.DRAWING_NOTES, stud.DRAWING_NOTES])
def test_notes_follow_the_simplicity_policy(notes: str) -> None:
    assert 1 <= len(notes.splitlines()) <= 4
    assert not re.search(r"\d", notes)
    assert "GROUND" not in notes and "GRIND" not in notes
