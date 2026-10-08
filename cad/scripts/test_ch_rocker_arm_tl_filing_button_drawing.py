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
from prechips.model import TOLERANCE_REQUIREMENTS

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


def test_matched_fits_export_the_printed_reference_and_fit_note() -> None:
    """One fact, one source: the print shows the bore and locating diameter
    as references governed by a fit callout, so features.toml carries that
    nominal and that callout text, never a tighter hidden band."""
    for feature, nominal, callout in (
        (
            _features(BUTTON)["bore"],
            button.BORE_DIA,
            button.REFERENCE_CALLOUTS["BoreDia"],
        ),
        (
            _features(STUD)["locating_body"],
            stud.BODY_DIA,
            stud.REFERENCE_CALLOUTS["BodyDia"],
        ),
    ):
        assert "dia" not in feature
        assert feature["dia_nominal"] == nominal
        assert "WITHOUT SHAKE" in feature["note"]
        assert feature["note"] == " ".join(part for part in callout if part)


@pytest.mark.parametrize("stem", [BUTTON, STUD])
def test_every_exported_band_is_a_requirement(stem: str) -> None:
    """One-fact rule: prechips inspects only the bands a feature lists."""
    for name, feature in _features(stem).items():
        for key, value in feature.items():
            if key in TOLERANCE_REQUIREMENTS and isinstance(value, list):
                assert key in feature["requirements"], (name, key)


# Each printed toleranced dimension -> the exported feature and requirement
# that owns its band. Reference sizes governed by a matched-fit callout and
# the thread designation own no band.
PRINTED_OWNERS = {
    BUTTON: (
        button,
        {
            "DiscDia": ("rim", "dia"),
            "DiscThick": ("hub_seat_face", "thickness"),
        },
        {"BoreDia"},
    ),
    STUD: (
        stud,
        {
            "SeatStation": ("button_seat", "station"),
            "ThreadStartStation": ("thread", "length"),
            "HeadBackStation": ("head_back_face", "station"),
            "TailEndStation": ("vise_tail", "station"),
            "HeadDia": ("button_seat", "dia"),
            "TailDia": ("vise_tail", "dia"),
        },
        {"BodyDia", "ThreadDia"},
    ),
}


@pytest.mark.parametrize("stem", [BUTTON, STUD])
def test_every_printed_band_has_a_requirement_owner(stem: str) -> None:
    """One-fact coverage: every printed toleranced dimension reaches prechips
    as a listed requirement band at its printed places."""
    spec, owners, exempt = PRINTED_OWNERS[stem]
    assert set(owners) | exempt == set(spec.DRAWING_PRECISION_BY_NAME)
    features = _features(stem)
    for printed, (name, key) in owners.items():
        feature = features[name]
        assert key in feature["requirements"], printed
        places = spec.DRAWING_PRECISION_BY_NAME[printed]
        assert feature[key] == limits(feature[f"{key}_nominal"], places), printed


def test_body_carries_the_hub_and_stays_inside_the_stack() -> None:
    """At every printed button thickness and hub length the whole hub sits on
    the lapped body (its length the worst case of the two printed tip
    stations), and the nut lands on the upper button (body short of the
    stack top)."""
    stud = _features(STUD)
    seat_low, seat_high = stud["button_seat"]["station"]
    start_low, start_high = stud["thread"]["length"]
    body_low, body_high = seat_low - start_high, seat_high - start_low
    thick_low, thick_high = _features(BUTTON)["hub_seat_face"]["thickness"]
    hub_high = rocker.HUB_LENGTH + rocker.HUB_LENGTH_BAND[0]
    assert body_high < 2 * thick_low + rocker.HUB_LENGTH
    assert body_low > thick_high + hub_high


def test_head_seat_lands_on_the_button_face_outside_its_bore() -> None:
    head = stud.HEAD_DIA
    bore_high = button.BORE_DIA + button.BORE_BAND[0]
    assert bore_high < head < _features(BUTTON)["rim"]["dia"][0]


@pytest.mark.parametrize(
    "dashed", ["ch-rocker-arm-tl-filing-button", "ch-rocker-arm-tl-filing-stud"]
)
def test_number_is_the_parent_number_plus_a_tool_suffix(dashed: str) -> None:
    parent = _config.parts("ch-rocker-arm")["number"]
    assert re.fullmatch(
        re.escape(parent) + r"-TL-\d{2}", _config.parts(dashed)["number"]
    )


@pytest.mark.parametrize("notes", [button.DRAWING_NOTES, stud.DRAWING_NOTES])
def test_notes_follow_the_simplicity_policy(notes: str) -> None:
    assert 1 <= len(notes.splitlines()) <= 4
    assert not re.search(r"\d", notes)
    assert "GROUND" not in notes and "GRIND" not in notes
