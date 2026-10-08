"""Offline contracts for the pivot bracket's reworked angle plate (MHA-CH-008-TL-02)."""

from __future__ import annotations

import re

import pytest

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
    """The stud stations print toleranced at one place, so prechips sees the
    title block's .X band; the reference tap stations export no band at all,
    only their nominals under the spot note that governs them."""
    features = _features()
    places = spec.DRAWING_PRECISION_BY_NAME
    for side, x in zip(("left", "right"), spec.TAP_X, strict=True):
        tap = features[f"ledge_tap_{side}"]
        assert sorted(tap["requirements"]) == ["dia", "note", "thread"]
        assert "station" not in tap and "height" not in tap
        assert (tap["station_nominal"], tap["height_nominal"]) == (x, spec.SCREW_Y)
        assert tap["note"] == " ".join(spec.DRAWING_NOTES.splitlines()[1:])
    for side, x in zip(("left", "right"), spec.STUD_X, strict=True):
        stud = features[f"stud_hole_{side}"]
        assert stud["station"] == limits(x, places["Stud1X"])
        assert stud["height"] == limits(spec.STUD_Y, places["Stud1Y"])


def test_drilled_bands_are_the_printed_callout_bands() -> None:
    """Each callout prints its drill at two places under DRILLED HOLES +0.10/0
    (tap 'Ø3.80 THRU ALL', stud 'Ø10.08'); the exported band is that printed
    band, not one around the unrounded drill, which would admit sizes the
    sheet rejects. The thread keeps the true tap drill."""
    features = _features()
    oversize = spec.drilled_oversize_mm()
    for side in ("left", "right"):
        tap = features[f"ledge_tap_{side}"]
        assert tap["dia"] == [3.80, pytest.approx(3.80 + oversize)]
        assert tap["tap_drill_mm"] == spec.blind_cut_dia_mm(spec.TAP_SPEC) != 3.80
        assert features[f"stud_hole_{side}"]["dia"] == [10.08, pytest.approx(10.08 + oversize)]


@pytest.mark.parametrize("stem", ["ch_pivot_bracket_tl_angle_plate", "ch_pivot_bracket_tl_ledge"])
def test_every_exported_nominal_lies_in_its_band(stem: str) -> None:
    """prechips rejects a feature whose *_nominal sits outside its band, as an
    unrounded drill (3.797 beside [3.80, 3.90]) would."""
    checked = 0
    for name, feature in export_features.requirement_manifest(stem)["features"].items():
        for key, nominal in feature.items():
            band_key = key.removesuffix("_nominal").removeprefix("nominal_")
            if band_key == key or not isinstance(feature.get(band_key), list):
                continue
            low, high = feature[band_key]
            assert low <= nominal <= high, f"{name}.{key} {nominal} outside {band_key} {[low, high]}"
            checked += 1
    assert checked


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
