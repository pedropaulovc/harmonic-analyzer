"""The engaged-feed window on the finite purchased rack."""

from __future__ import annotations

import math

import pytest

from _printed_tolerance import printed_deviations
import paper_drive_geom as geometry
import paper_drive_mesh_check as mesh
import paper_drive_rack_travel as travel
import pd_paper_drive_assembly_steps as steps
import pd_platen_rack_spec as rack


@pytest.fixture(scope="module")
def domain():
    return steps.feed_rack_operating_domain()


def test_window_clips_the_contact_path_and_one_pitch_inside_the_shortest_cut(domain):
    lower, _upper = printed_deviations(
        rack.CUT_LENGTH_MM, rack.DRAWING_PRECISION["BarProfile"]["Length"]
    )
    assert domain.minimum_cut_length_mm == pytest.approx(rack.CUT_LENGTH_MM + lower)
    reach = mesh.feed_rack_contact_half_width_mm()
    assert domain.contact_footprint_x_limits_mm == (-reach, reach)
    assert domain.cut_end_reserve_mm == pytest.approx(
        rack.PITCH + geometry.feed_lateral_deviation_mm()
    )
    assert domain.cut_end_reserve_mm >= rack.PITCH / 2.0 + 2.0 * rack.DEDENDUM * rack.TAN_PA
    assert domain.cut_end_finish_reach_mm < rack.PITCH
    low, high = domain.axis_from_left_end_limits_mm
    offset_low, offset_high = domain.profilecentre_x_offset_band_mm
    assert low + offset_low - reach >= domain.cut_end_reserve_mm
    assert high + offset_high + reach <= domain.minimum_cut_length_mm - domain.cut_end_reserve_mm
    factor = 10**travel.OPERATING_LIMIT_PLACES
    assert low * factor == pytest.approx(round(low * factor))
    assert high * factor == pytest.approx(round(high * factor))
    assert f"{low:.2f} TO {high:.2f} MM" in domain.operating_window_text


def test_overruns_are_refused_with_the_cut_face_datum_and_x_sign(domain):
    low, high = domain.axis_from_left_end_limits_mm
    domain.require_axis_distance_band_mm((low, high))
    for overrun in (math.nextafter(low, -math.inf), math.nextafter(high, math.inf)):
        with pytest.raises(ValueError, match="cut-end overrun"):
            domain.require_axis_distance_mm(overrun)
    axis_x = 19.0
    left = (axis_x - high + 0.001, axis_x - low - 0.001)
    domain.require_machine_travel_mm(
        rack_left_end_x_band_mm=left, running_axis_x_band_mm=(axis_x, axis_x)
    )
    with pytest.raises(ValueError, match="cut-end overrun"):
        domain.require_machine_travel_mm(
            rack_left_end_x_band_mm=(left[0] - 0.01, left[1]),
            running_axis_x_band_mm=(axis_x, axis_x),
        )
    assert "DECREASES" in travel.OPERATING_DIRECTION_TEXT


def test_the_located_paper_sweep_fits_and_a_moved_pen_line_overruns(domain):
    bands = geometry.recording_paper_sweep_bands_mm()
    domain.require_recording_paper_sweep_mm(**bands)
    _low, high = domain.axis_from_left_end_limits_mm
    inset_high = bands["paper_left_inset_band_mm"][1]
    shifted = inset_high - high + 1.0
    with pytest.raises(ValueError, match="cut-end overrun"):
        domain.require_recording_paper_sweep_mm(
            **{**bands, "pen_x_from_running_axis_band_mm": (shifted - 0.01, shifted + 0.01)}
        )


def test_oversize_cut_section_refuses_the_one_pitch_end_reserve():
    with pytest.raises(ValueError, match="cut-end finish exceeds"):
        travel.rack_operating_domain_mm(
            contact_half_width_mm=1.0,
            lateral_deviation_mm=0.0,
            profilecentre_x_offset_band_mm=(0.0, 0.0),
            cut_end_section_maxima_mm=(500.0, 50.0),
        )
