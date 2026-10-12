"""Pure discrete ANSI #25 acceptance; the native visual is not the oracle."""

from __future__ import annotations

import math
from functools import cache

import pytest

import _chain as visual
import paper_drive_chain_fit as physical
import paper_drive_geom as law
import pd_transgear_removable_spec as sprocket


@cache
def _selected(side: int = 1) -> physical.ChainFit:
    return physical.solve_source_nominal_chain_fit(taut_side=side)


def test_selected_count_is_the_same_single_source_as_the_visual() -> None:
    assert sprocket.CHAIN_LINK_COUNT == 68
    assert visual.LINK_COUNT == sprocket.CHAIN_LINK_COUNT
    assert visual.LINK_PITCH == sprocket.CHAIN_PITCH
    knob, crank = physical.source_nominal_chain_centres_mm()
    assert visual.KNOB_CENTRE == (-knob[0], knob[1])
    assert visual.CRANK_CENTRE == (-crank[0], crank[1])
    # Inherited continuous guide only; this is not a roller-seating certificate.
    assert visual.VISUAL_TAUT_LENGTH < visual.CENTRELINE_LEN < visual.VISUAL_MAX_LENGTH
    assert 0.0 < visual.SAG < visual.VISUAL_MAX_SAG
    assert visual._loop_length(visual.SAG) == pytest.approx(
        visual.CENTRELINE_LEN, abs=1e-6
    )


@pytest.mark.parametrize("side", (-1, 1))
def test_real_source_centres_have_a_closed_standard_pitch_pinned_cycle(side: int) -> None:
    fit = _selected(side)
    assert fit.knob_centre == law.KNOB_SHAFT_XY
    assert fit.crank_centre == physical.source_nominal_chain_centres_mm()[1]
    assert len(fit.pins) == sprocket.CHAIN_LINK_COUNT
    assert physical.require_pinned_cycle(fit.pins) < 1e-7
    assert sum(math.dist(point, fit.pins[(index + 1) % len(fit.pins)])
               for index, point in enumerate(fit.pins)) == pytest.approx(
        sprocket.CHAIN_LINK_COUNT * sprocket.CHAIN_PITCH, abs=1e-6
    )
    assert fit.sag_mm > 0.0
    assert fit.roller_air_mm >= -1e-7
    assert fit.plate_air_mm >= -1e-7
    assert fit.backbend_air_mm >= -1e-7
    assert fit.strand_air_mm >= -1e-7
    assert sprocket.ANSI_ROLLER_WIDTH > sprocket.PLATE
    x0, y0, x1, y1 = fit.envelope_mm
    assert all(x0 < x < x1 and y0 < y < y1 for x, y in fit.pins)


def test_seated_rollers_use_actual_gap_phase_and_polygon_chords() -> None:
    fit = _selected()
    for centre, teeth, phase, indices in (
        (fit.knob_centre, fit.knob_teeth, fit.knob_phase_rad, fit.knob_seated),
        (fit.crank_centre, fit.crank_teeth, fit.crank_phase_rad, fit.crank_seated),
    ):
        pitch_radius = sprocket.pitch_dia(teeth) / 2.0
        for index in indices:
            point = fit.pins[index]
            assert math.dist(point, centre) == pytest.approx(pitch_radius, abs=1e-7)
            angle = math.atan2(point[1] - centre[1], point[0] - centre[0])
            registration = (angle - phase - math.pi / teeth) * teeth / (2.0 * math.pi)
            assert registration == pytest.approx(round(registration), abs=1e-7)
            assert physical.roller_air_mm(point, centre, teeth, phase) >= -1e-7
        for first, last in zip(indices, indices[1:]):
            assert math.dist(fit.pins[first], fit.pins[last]) == pytest.approx(
                sprocket.CHAIN_PITCH, abs=1e-7
            )
        # A half-tooth phase mutation places those same rollers on tooth metal.
        assert min(physical.roller_air_mm(fit.pins[index], centre, teeth,
                                        phase + math.pi / teeth) for index in indices) < 0.0


def test_every_roller_not_just_declared_wrap_indices_has_root_to_tip_air() -> None:
    fit = _selected()
    observed = min(
        min(physical.roller_air_mm(point, fit.knob_centre, fit.knob_teeth, fit.knob_phase_rad,
                                  tip_deviation_mm=physical.printed_tip_max_deviation_mm(fit.knob_teeth)),
            physical.roller_air_mm(point, fit.crank_centre, fit.crank_teeth, fit.crank_phase_rad,
                                  tip_deviation_mm=physical.printed_tip_max_deviation_mm(fit.crank_teeth)))
        for point in fit.pins
    )
    assert fit.roller_air_mm == pytest.approx(observed, abs=1e-9)
    assert observed >= -1e-7


def test_gap_bottom_and_tip_land_are_real_boundaries() -> None:
    for teeth in (12, 24):
        radius = sprocket.pitch_dia(teeth) / 2.0
        gap_phase = -math.pi / teeth
        assert physical.roller_air_mm((radius, 0.0), (0.0, 0.0), teeth, gap_phase) == pytest.approx(
            sprocket.SEAT_CURVE_R - sprocket.ANSI_ROLLER_DIA / 2.0, abs=1e-9
        )
        assert physical.roller_air_mm((radius, 0.0), (0.0, 0.0), teeth, 0.0) < 0.0
        tip = sprocket.outside_dia(teeth) / 2.0
        assert physical.roller_air_mm((tip + sprocket.ANSI_ROLLER_DIA / 2.0 + 0.1, 0.0),
                                     (0.0, 0.0), teeth, 0.0) == pytest.approx(0.1)


def test_printed_od_maximum_clips_the_real_native_closing_line() -> None:
    for teeth in (12, 24):
        deviation = physical.printed_tip_max_deviation_mm(teeth)
        geometry = sprocket.gap_geometry(teeth)
        actual, _arcs, lines = physical._tooth_boundary(teeth, deviation)
        assert actual["ra"] == pytest.approx(geometry["ra"] + deviation / 2.0)
        assert 0.0 < actual["corner_angle"] < geometry["corner_angle"]
        corner, new_corner = lines[0]
        assert corner == (geometry["corner_x"], geometry["corner_y"])
        apex = (2.0 * geometry["ra"], 0.0)
        assert physical._cross(physical._sub(new_corner, corner),
                               physical._sub(apex, corner)) == pytest.approx(0.0, abs=1e-8)
        assert math.hypot(*new_corner) == pytest.approx(actual["ra"])
        outside = (actual["ra"] + sprocket.ANSI_ROLLER_DIA / 2.0 + 0.1, 0.0)
        assert physical.roller_air_mm(outside, (0.0, 0.0), teeth, 0.0,
                                     tip_deviation_mm=deviation) == pytest.approx(0.1)


def test_tension_loaded_junction_rejects_small_reverse_turn() -> None:
    pitch = sprocket.CHAIN_PITCH
    turn = math.radians(3.0)
    before, pin = (-pitch, 0.0), (0.0, 0.0)
    for sense in (-1, 1):
        forward = pitch * math.cos(turn), sense * pitch * math.sin(turn)
        backward = pitch * math.cos(turn), -sense * pitch * math.sin(turn)
        assert physical._supported_turn(before, pin, forward, sense, math.radians(30.0))
        assert not physical._supported_turn(before, pin, backward, sense, math.radians(30.0))


def test_wrong_count_stretched_pitch_and_open_seam_are_refused() -> None:
    pins = _selected().pins
    with pytest.raises(ValueError, match="exactly"):
        physical.require_pinned_cycle(pins[:-2])
    stretched = tuple((x * 1.001, y * 1.001) for x, y in pins)
    with pytest.raises(ValueError, match="pitch/seam"):
        physical.require_pinned_cycle(stretched)
    open_seam = pins[:-1] + ((pins[-1][0] + 0.01, pins[-1][1]),)
    with pytest.raises(ValueError, match="pitch/seam"):
        physical.require_pinned_cycle(open_seam)


@pytest.mark.parametrize("count", (0, -2, 67, 68.0, True))
def test_invalid_physical_selection_is_refused(count) -> None:
    with pytest.raises(ValueError, match="positive even integer"):
        physical.solve_chain_fit((0.0, 0.0), (100.0, 100.0), link_count=count)


def test_unreachable_centres_report_a_numeric_length_bound_without_resizing() -> None:
    with pytest.raises(ValueError, match="necessary taut-length lower bound") as caught:
        physical.solve_chain_fit((0.0, 0.0), (1000.0, 0.0))
    assert f"selected {sprocket.CHAIN_LINK_COUNT} links" in str(caught.value)
    assert f"available {sprocket.CHAIN_LINK_COUNT * sprocket.CHAIN_PITCH:.6f}" in str(caught.value)


def test_proper_rotations_preserve_the_physical_cycle_and_gravity() -> None:
    fit = _selected()
    angle = 0.73
    rotation = ((math.cos(angle), -math.sin(angle)), (math.sin(angle), math.cos(angle)))
    translation = (17.0, -23.0)
    pins = physical.transform_cycle(fit.pins, rotation, translation)
    centres = physical.transform_cycle((fit.knob_centre, fit.crank_centre), rotation, translation)
    gravity = physical.transform_cycle((fit.gravity,), rotation, (0.0, 0.0))[0]
    rotated = physical.solve_chain_fit(*centres, gravity=gravity)
    assert physical.require_pinned_cycle(pins) < 1e-7
    for expected, actual in zip(pins, rotated.pins, strict=True):
        assert actual == pytest.approx(expected, abs=1e-6)
    assert rotated.sag_mm == pytest.approx(fit.sag_mm, abs=1e-6)


@pytest.mark.parametrize("rotation", (((-1.0, 0.0), (0.0, 1.0)),
                                       ((1.01, 0.0), (0.0, 1.01))))
def test_reflected_or_scaled_frames_cannot_masquerade_as_native_placements(rotation) -> None:
    with pytest.raises(ValueError, match="right-handed rigid rotation"):
        physical.transform_cycle(_selected().pins, rotation, (0.0, 0.0))
