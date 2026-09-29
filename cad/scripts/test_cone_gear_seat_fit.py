"""Every cone gear D-bore against the D-flat land it slides onto.

Cross-part contract between the cone gear family (MHA-013) and the cone gear
shaft (MHA-014), closing two Codex findings:

* #834: a gear's bore must be the land under its station (the U40 S1 bores
  and #839's moved lands arrive in different PRs);
* #811: a slide-on fit needs a stated, positive clearance.  The solid-stack
  ruling (2026-09-28) makes it the shared gear seat fit (gear_seat_fit):
  0.025-0.105 diametral on the round, 0.010-0.030 across the flat.
"""

from __future__ import annotations

import math

import pytest

import _fit_limits
import build_cone_gear_shaft
import cone_gear_shaft_spec as shaft
import cone_gear_spec as spec
import cone_shaft_land_bands as lands
from gear_seat_fit import (
    FLAT_AF_CLEARANCE,
    GEAR_SEAT_CLEARANCE,
    flat_bore_af_band,
    seat_bore_band,
)

MIN_BAND_WIDTH = 0.01


def test_the_shaft_reads_the_land_bands_from_their_own_module() -> None:
    assert shaft.SECTION_DIA_BANDS is lands.SECTION_DIA_BANDS
    assert shaft.GEAR_SEAT_BAND is lands.GEAR_SEAT_BAND
    assert shaft.RUNNING_DIA_BAND is lands.RUNNING_DIA_BAND
    assert lands.RUNNING_DIA_BAND is _fit_limits.SHAFT_H
    assert build_cone_gear_shaft.SECTION_DIA_BANDS is lands.SECTION_DIA_BANDS
    assert len(lands.SECTION_CONE_GEAR_TEETH) == len(shaft.SECTIONS)
    assert len(lands.SECTION_FLAT_AF) == len(shaft.SECTIONS)


def test_every_gear_bore_is_the_d_flat_land_under_it() -> None:
    carried = sorted(t for teeth in lands.SECTION_CONE_GEAR_TEETH for t in teeth)
    assert carried == sorted(spec.CONFIGURATION_TEETH)
    for teeth in spec.CONFIGURATION_TEETH:
        section = spec.land_section(teeth)
        assert teeth in lands.SECTION_CONE_GEAR_TEETH[section]
        assert spec.bore_dia_mm(teeth) == pytest.approx(shaft.SECTION_DIAS[section])
        # Every gear land carries a flat (ruling 1: the Sec4 flat runs out
        # through the tip, so T006 and T012 slide onto it too).
        assert lands.SECTION_FLAT_AF[section] is not None, teeth
        assert spec.bore_flat_af_mm(teeth) == pytest.approx(
            lands.SECTION_FLAT_AF[section]
        )
    assert spec.bore_flat_af_mm(6) == pytest.approx(1.460)
    assert spec.bore_flat_af_mm(12) == pytest.approx(1.460)


def test_every_gear_station_lies_on_its_land() -> None:
    # Solid stack: gear j occupies gear_faces(j).  Each land step stands one
    # SEAT_STEP_SETBACK south of the north face of the last gear on the
    # larger land, so that gear overhangs its land by the setback and the
    # smaller-bore gear north of it sits wholly on its own land.
    for j, teeth in enumerate(range(120, 0, -6)):
        south, north = shaft.gear_faces(j)
        assert north - south == pytest.approx(spec.FACE_WIDTH)
        section = spec.land_section(teeth)
        land_start = shaft.SECTION_ENDS[section - 1] - shaft.FRONT_STUB
        land_end = shaft.SECTION_ENDS[section] - shaft.FRONT_STUB
        assert land_start <= south + 1e-9, teeth
        if j in shaft.SEAT_STEP_GEARS:
            assert north - land_end == pytest.approx(shaft.SEAT_STEP_SETBACK), teeth
            assert spec.land_section(teeth - 6) == section + 1
        else:
            assert north <= land_end + 1e-9, teeth


def test_the_seat_fit_derives_both_bore_bands() -> None:
    assert GEAR_SEAT_CLEARANCE == (0.025, 0.105)
    assert FLAT_AF_CLEARANCE == (0.010, 0.030)
    assert seat_bore_band(lands.GEAR_SEAT_BAND) == pytest.approx((0.055, 0.025))
    assert seat_bore_band(lands.RUNNING_DIA_BAND) == pytest.approx((0.085, 0.025))
    assert spec.BORE_AF_BAND == pytest.approx(flat_bore_af_band(lands.FLAT_AF_BAND))
    assert spec.BORE_AF_BAND == pytest.approx((0.020, 0.010))


def test_every_seat_keeps_both_clearance_windows_at_the_print_extremes() -> None:
    bore_upper, bore_lower = spec.BORE_DIA_BAND
    af_upper, af_lower = spec.BORE_AF_BAND
    assert bore_upper - bore_lower >= MIN_BAND_WIDTH - 1e-9
    assert af_upper - af_lower >= MIN_BAND_WIDTH - 1e-9
    round_min, round_max = GEAR_SEAT_CLEARANCE
    flat_min, flat_max = FLAT_AF_CLEARANCE
    land_af_upper, land_af_lower = lands.FLAT_AF_BAND
    for teeth in spec.CONFIGURATION_TEETH:
        section = spec.land_section(teeth)
        land_upper, land_lower = lands.SECTION_DIA_BANDS[section]
        assert bore_lower - land_upper >= round_min - 1e-9, teeth
        assert bore_upper - land_lower <= round_max + 1e-9, teeth
        # Nominals match, so the AF clearance is the band difference alone.
        assert spec.bore_flat_af_mm(teeth) == pytest.approx(
            lands.SECTION_FLAT_AF[section]
        )
        assert af_lower - land_af_upper >= flat_min - 1e-9, teeth
        assert af_upper - land_af_lower <= flat_max + 1e-9, teeth


def test_the_flat_is_a_true_chord_clocked_to_one_place() -> None:
    # The printed clock (tooth centreline to flat normal) takes one place and
    # carries the error budget's cone_flat_clock term.
    assert spec.FLAT_CLOCK_TOLERANCE_DEG == 0.25
    assert spec.DRAWING_PRECISION_BY_NAME["BoreFlatClock"] == 1
    assert "BoreFlatClock" in spec.DRAWING_DIMENSIONS["BoreProfile"]
    # The flat is a real chord: shallow enough to leave the round bore
    # guiding the gear, deep enough to key it (AF below the diameter).
    for teeth in spec.CONFIGURATION_TEETH:
        radius = spec.bore_dia_mm(teeth) / 2.0
        offset = spec.bore_flat_offset_mm(teeth)
        assert 0.5 * radius < offset < radius, teeth
        half_chord = math.sqrt(radius**2 - offset**2)
        assert spec.bore_flat_segment_area_mm2(teeth) == pytest.approx(
            radius**2 * math.acos(offset / radius) - offset * half_chord
        )


def test_the_band_upper_is_the_lower_of_its_two_named_limits() -> None:
    # A later land or web change re-derives the band instead of silently
    # breaking the T006 web or the seat window.
    assert spec.BORE_BAND_FIT_UPPER == pytest.approx(
        min(
            seat_bore_band(band)[0]
            for band, teeth in zip(
                lands.SECTION_DIA_BANDS, lands.SECTION_CONE_GEAR_TEETH
            )
            if teeth
        )
    )
    web_cap = (
        spec.floor_limits_mm(6)[0]
        - 2.0 * spec.WEB_EXCEPTIONS_MM[6]
        - spec.bore_dia_mm(6)
    )
    assert spec.BORE_BAND_WEB_UPPER <= web_cap
    assert web_cap - spec.BORE_BAND_WEB_UPPER < 10.0**-spec.BORE_BAND_PLACES
    assert spec.BORE_DIA_BAND[0] == pytest.approx(
        min(spec.BORE_BAND_FIT_UPPER, spec.BORE_BAND_WEB_UPPER)
    )
    assert spec.BORE_DIA_BAND[1] == pytest.approx(spec.BORE_BAND_LOWER)


def test_the_t006_web_caps_the_bore_band() -> None:
    # The largest T006 bore under its printed MIN floor keeps the named web.
    floor_min = spec.floor_limits_mm(6)[0]
    largest_bore = spec.bore_dia_mm(6) + spec.BORE_DIA_BAND[0]
    assert (floor_min - largest_bore) / 2.0 >= spec.WEB_EXCEPTIONS_MM[6] - 1e-9
