"""Every cone gear D-bore against the D-flat land it slides onto.

Cross-part contract between the cone gear family (MHA-DT-003) and the cone gear
shaft (MHA-DT-004), closing two Codex findings:

* #834: a gear's bore must be the land under its station (the U40 S1 bores
  and #839's moved lands arrive in different PRs);
* #811: a slide-on fit needs a stated, positive clearance.  The solid-stack
  ruling (2026-09-28) makes it the shared gear seat fit (gear_seat_fit):
  0.025-0.105 diametral on the round, 0.010-0.030 across the flat.
"""

from __future__ import annotations

import math
import itertools

import pytest

import _config
import _fit_limits
import build_dt_cone_gear_shaft
import dt_cone_gear_shaft_spec as shaft
import dt_cone_gear_spec as spec
import cone_shaft_land_bands as lands
from gear_seat_fit import (
    FLAT_AF_CLEARANCE,
    GEAR_SEAT_CLEARANCE,
    flat_bore_af_band,
    seat_bore_band,
    connected_home_clock_angle_bound_rad,
)

MIN_BAND_WIDTH = 0.01


def test_the_shaft_reads_the_land_bands_from_their_own_module() -> None:
    assert shaft.SECTION_DIA_BANDS is lands.SECTION_DIA_BANDS
    assert shaft.GEAR_SEAT_BAND is lands.GEAR_SEAT_BAND
    assert shaft.RUNNING_DIA_BAND is lands.RUNNING_DIA_BAND
    assert lands.RUNNING_DIA_BAND is _fit_limits.SHAFT_H
    assert build_dt_cone_gear_shaft.SECTION_DIA_BANDS is lands.SECTION_DIA_BANDS
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


def test_every_gear_station_lies_on_its_land() -> None:
    # Solid stack: gear j occupies gear_faces(j).  Each land step stands one
    # SEAT_STEP_SETBACK south of the north face of the last gear on the
    # larger land, so that gear overhangs its land by the setback and the
    # smaller-bore gear north of it sits wholly on its own land.
    for j, teeth in enumerate(reversed(spec.CONFIGURATION_TEETH)):
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
    # Terminal deep-D keeps over half the cylindrical guidance at print corners;
    # intermediate lands retain their original shallow-flat condition.
    for teeth in spec.CONFIGURATION_TEETH:
        radius = spec.bore_dia_mm(teeth) / 2.0
        offset = spec.bore_flat_offset_mm(teeth)
        if teeth in spec.TERMINAL_WEB_REQUIREMENTS_MM:
            assert 0.0 < offset < radius, teeth
            maximum_radius = (spec.bore_dia_mm(teeth) + spec.BORE_DIA_BAND[0]) / 2.0
            minimum_offset = (
                spec.bore_flat_af_mm(teeth) + spec.BORE_AF_BAND[1] - maximum_radius
            )
            assert minimum_offset > 0.0
            retained_arc = 2.0 * math.pi - 2.0 * math.acos(minimum_offset / maximum_radius)
            assert retained_arc > math.pi
        else:
            assert 0.5 * radius < offset < radius, teeth
        half_chord = math.sqrt(radius**2 - offset**2)
        assert spec.bore_flat_segment_area_mm2(teeth) == pytest.approx(
            radius**2 * math.acos(offset / radius) - offset * half_chord
        )
    assert lands.TERMINAL_HALF_CHORD_MIN_MM >= lands.TERMINAL_REQUIRED_HALF_CHORD_MM
    minimum_land_radius = (
        lands.TERMINAL_DIA_MM + lands.RUNNING_DIA_BAND[1]
    ) / 2.0
    assert 0.0 < lands.TERMINAL_FLAT_OFFSET_MAX_MM < minimum_land_radius
    assert lands.TERMINAL_HALF_CHORD_MIN_MM - (
        lands.TIP_SCREW_DOG_PROJECTED_RADIUS_MM
        + lands.TIP_COLLAR_MAX_RADIAL_FLOAT_MM + lands.TIP_SCREW_DOG_AXIS_OFFSET_MM
    ) >= lands.TERMINAL_FLAT_EDGE_BREAK_MAX


def test_retained_seat_band_is_input_and_qualified_web_is_acceptance() -> None:
    # Selected cutter geometry must meet the retained fit; it must not make
    # its own numerical producer depend on an unpublished output floor first.
    assert spec.BORE_BAND_FIT_UPPER == pytest.approx(
        min(
            seat_bore_band(band)[0]
            for band, teeth in zip(
                lands.SECTION_DIA_BANDS, lands.SECTION_CONE_GEAR_TEETH
            )
            if teeth
        )
    )
    scale = 10**spec.BORE_BAND_PLACES
    web_cap = min(
        spec.floor_limits_mm(teeth)[0] - 2.0 * minimum
        - math.ceil(spec.bore_dia_mm(teeth) * scale - 1e-9) / scale
        for teeth, minimum in spec.TERMINAL_WEB_REQUIREMENTS_MM.items()
    )
    cutter_cap = spec.terminal_web_bore_upper_mm()
    assert cutter_cap <= web_cap + 1e-9
    assert web_cap - cutter_cap < 1.0 / scale + 1e-9
    assert spec.BORE_DIA_BAND[0] == pytest.approx(spec.BORE_BAND_FIT_UPPER)
    assert spec.BORE_DIA_BAND[0] <= cutter_cap + 1e-9
    assert spec.BORE_DIA_BAND[1] == pytest.approx(spec.BORE_BAND_LOWER)


def test_both_terminal_web_guards_read_the_current_cutter_and_bore() -> None:
    for teeth, minimum in spec.TERMINAL_WEB_REQUIREMENTS_MM.items():
        assert spec.terminal_web_mm(teeth) >= minimum - 1e-9
        profile = spec.stock_form_profile(teeth)
        assert spec.floor_limits_mm(teeth)[0] <= 2.0 * profile.root_radius_min_mm + 1e-9
        assert profile.root_radius_min_mm - (
            spec.bore_dia_mm(teeth) + spec.BORE_DIA_BAND[0]
        ) / 2.0 >= minimum - 1e-9


def _actual_clock_fit(teeth):
    section = spec.land_section(teeth)
    nominal_dia = spec.bore_dia_mm(teeth)
    dia = lands.land_finished_dia_limits_mm(nominal_dia, section)
    shaft_af = lands.land_finished_af_limits_mm(section)
    printed_bore_af = round(spec.bore_flat_af_mm(teeth), spec.BORE_AF_PLACES)
    bore_af = tuple(printed_bore_af + value for value in reversed(spec.BORE_AF_BAND))
    edge = _config.title_block("edge_break")
    edge_break = (
        lands.TERMINAL_FLAT_EDGE_BREAK_MAX
        if section == len(lands.SECTION_DIA_BANDS)-1
        else max(float(edge["radius_mm"]),float(edge["chamfer_max_mm"]))
    )
    return dia,shaft_af,bore_af,edge_break


def test_connected_home_clock_uses_actual_all_twenty_coupled_fit_bands() -> None:
    for teeth in spec.CONFIGURATION_TEETH:
        dia,shaft_af,bore_af,edge_break = _actual_clock_fit(teeth)
        bound = connected_home_clock_angle_bound_rad(
            dia,shaft_af,bore_af,edge_break_mm=edge_break,
        )
        sharp = connected_home_clock_angle_bound_rad(
            dia,shaft_af,bore_af,edge_break_mm=0.0,
        )
        radius = dia[0]/2
        offset = shaft_af[0]-radius
        chord = math.sqrt(radius*radius-offset*offset)
        retained = min(
            chord-edge_break,
            math.sqrt((shaft_af[0]-2*edge_break)*(dia[0]-shaft_af[0])),
        )
        exact_retained_width_barrier = (
            math.asin((bore_af[1]-radius)/math.hypot(offset,retained))
            - math.atan2(offset,retained)
        )
        assert exact_retained_width_barrier <= bound < exact_retained_width_barrier+1e-10
        assert sharp < bound < math.pi
        # The legacy small-angle estimate ignores both sine curvature and
        # the material removed by the stock-permitted torque-corner break.
        assert bound > (bore_af[1]-shaft_af[0])/chord
        for d,af,bore in itertools.product(dia,shaft_af,bore_af):
            corner = connected_home_clock_angle_bound_rad(
                (d,d),(af,af),(bore,bore),edge_break_mm=edge_break,
            )
            assert corner <= bound+1e-10


def test_clock_bound_stays_in_first_connected_width_component() -> None:
    radius,af,bore = 2.0,3.6,3.7
    bound = connected_home_clock_angle_bound_rad(
        (4,4),(af,af),(bore,bore),edge_break_mm=0.0,
    )
    offset = af-radius
    chord = math.sqrt(radius*radius-offset*offset)
    def width(theta):
        return radius+offset*math.cos(theta)+chord*abs(math.sin(theta))
    assert width(bound-1e-6) < bore
    assert width(bound+1e-6) > bore
    assert width(0.0) == pytest.approx(af)  # home: the D's own across-flat
    assert bound < math.acos(offset/radius)
    assert connected_home_clock_angle_bound_rad(
        (4,4),(af,af),(4,4),edge_break_mm=0.0,
    ) == math.pi


def test_circular_round_corner_setback_is_not_a_tangent_line_approximation() -> None:
    diameter,af,bore,edge = 2.0,1.01,1.05,0.20
    radius = diameter/2
    offset = af-radius
    chord = math.sqrt(radius*radius-offset*offset)
    retained_round = math.sqrt((af-2*edge)*(diameter-af))
    assert chord-retained_round > edge
    false_setback_barrier = (
        math.asin((bore-radius)/math.hypot(offset,chord-edge))
        - math.atan2(offset,chord-edge)
    )
    bound = connected_home_clock_angle_bound_rad(
        (diameter,diameter),(af,af),(bore,bore),edge_break_mm=edge,
    )
    assert bound > false_setback_barrier


def test_clock_reader_has_no_default_sharp_stock_acceptance() -> None:
    with pytest.raises(TypeError,match="edge_break_mm"):
        connected_home_clock_angle_bound_rad((4,4),(3.6,3.6),(3.7,3.7))


def test_no_retained_width_barrier_reports_full_wrapped_outer_not_zero() -> None:
    assert connected_home_clock_angle_bound_rad(
        (4,4),(3.6,3.6),(3.7,3.7),edge_break_mm=1.8,
    ) == math.pi


@pytest.mark.parametrize("edge",(-0.1,math.nan,math.inf))
def test_clock_reader_refuses_invalid_edge_break_grade(edge) -> None:
    with pytest.raises(ValueError,match="edge break"):
        connected_home_clock_angle_bound_rad(
            (4,4),(3.6,3.6),(3.7,3.7),edge_break_mm=edge,
        )


@pytest.mark.parametrize("dia,af,bore",(
    ((0,4),(3.6,3.6),(3.7,3.7)),
    ((4,3),(3.6,3.6),(3.7,3.7)),
    ((4,4),(1.9,1.9),(3.7,3.7)),
    ((4,4),(3.6,3.6),(3.5,3.5)),
))
def test_clock_reader_refuses_invalid_or_non_home_grade_boxes(dia,af,bore) -> None:
    with pytest.raises(ValueError):
        connected_home_clock_angle_bound_rad(dia,af,bore,edge_break_mm=0.0)
