"""Offline contracts for the rocker trammel setting bar (MHA-CH-006-TL-17)."""

from __future__ import annotations

import math
import re

from prechips.model import FixtureSolid

import _config
import ch_rocker_arm_tl_trammel_setting_bar_spec as spec
import draw_ch_rocker_arm_tl_trammel_setting_bar as drawing
import export_features

STEM = "ch_rocker_arm_tl_trammel_setting_bar"


def _features() -> dict:
    return export_features.requirement_manifest(STEM)["features"]


def test_every_marked_dimension_prints_once_at_its_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    top, section = set(drawing.TOP_OFFSETS), {*drawing.SECTION_OFFSETS, "BarThickness"}
    assert top | section == marked
    assert not top & section
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert {name for _feature, name in spec.DRAWING_BANDS} <= marked
    assert set(drawing.CALLOUTS_ABOVE) | set(drawing.CALLOUTS_BELOW) <= marked


def test_stations_are_the_trammel_radii_from_h0() -> None:
    features = _features()
    assert features["seat_h800"]["station"] == [799.95, 800.05]
    assert features["seat_h816"]["station"] == [815.95, 816.05]
    for name in ("seat_h0", "seat_h800", "seat_h816"):
        assert features[name]["axis"] == [0.0, -1.0, 0.0]


def test_seat_takes_both_trammel_points() -> None:
    seat = _features()["seat_h0"]
    pilot = _features()["seat_h0_pilot"]
    # The cone lies inside the #2 centre drill's body and outside the pilot.
    assert seat["dia"][1] < spec.CENTRE_DRILL_BODY_DIA
    assert seat["dia"][0] > pilot["dia"][1]
    assert pilot["thru"] is True
    # The 1/4 point bodies never enter; the pivot apex stays inside the bar.
    assert spec.TRAMMEL_POINT_DIA > seat["dia"][1]
    half = math.radians(spec.PIVOT_POINT_HALF_ANGLE_DEG - 1.0)
    assert seat["dia"][1] / 2.0 / math.tan(half) < spec.BAR_THICKNESS
    # Face-to-flank angle of a 60 deg included seat.
    assert seat["land_angle_nominal_deg"] == 90.0 - spec.SEAT_HALF_ANGLE_DEG == 60.0
    assert seat["land_angle_deg"] == [59.0, 61.0]


def test_bar_is_the_supply_stock_with_h0_and_h816_equally_in_from_the_ends() -> None:
    assert (spec.BAR_LENGTH, spec.BAR_WIDTH, spec.BAR_THICKNESS) == (914.4, 25.4, 6.35)
    assert math.isclose(
        spec.H0_FROM_END, spec.BAR_LENGTH - spec.H816 - spec.H0_FROM_END
    )


def test_prechips_solids_are_valid_fixture_solids() -> None:
    for solid in spec.PRECHIPS_SOLIDS:
        FixtureSolid.model_validate(solid)
    bar, *seats = spec.PRECHIPS_SOLIDS
    assert bar["size_mm"] == [spec.BAR_LENGTH, spec.BAR_THICKNESS, spec.BAR_WIDTH]
    assert [seat["at_mm"][0] for seat in seats] == [0.0, 800.0, 816.0]
    assert all(seat["void"] for seat in seats)


def test_number_is_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("ch-rocker-arm")["number"]
    number = _config.parts("ch-rocker-arm-tl-trammel-setting-bar")["number"]
    assert number == f"{parent}-TL-17"


def test_notes_follow_the_simplicity_policy() -> None:
    lines = spec.DRAWING_NOTES.splitlines()
    assert 1 <= len(lines) <= 4
    assert not re.search(r"\d", spec.DRAWING_NOTES)
    for callout in (*drawing.CALLOUTS_ABOVE.values(), *drawing.CALLOUTS_BELOW.values()):
        assert not re.search(r"\d(?!X\b)", callout), callout


def test_every_exported_band_endpoint_is_a_printed_value() -> None:
    """One fact: a band applied to an unrounded model nominal exports limits
    the sheet never prints."""
    checked = 0
    for name, feature in _features().items():
        for requirement in feature["requirements"]:
            band = feature.get(requirement)
            if not (isinstance(band, list) and len(band) == 2):
                continue
            places = feature["precision"][requirement]
            for end in band:
                assert abs(end - round(end, places)) < 1e-9, (
                    name,
                    requirement,
                    band,
                    places,
                )
            nominal = feature.get(f"{requirement}_nominal")
            if nominal is not None:
                assert band[0] <= nominal <= band[1], (name, requirement, nominal, band)
                assert abs(nominal - round(nominal, places)) < 1e-9, (
                    name,
                    requirement,
                    nominal,
                )
            checked += 1
    assert checked
