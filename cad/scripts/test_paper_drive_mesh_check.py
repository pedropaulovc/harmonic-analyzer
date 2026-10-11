"""Closed-form gates for the paper drive's two meshes, plus one numeric
cross-check of the translated feed-pinion form against the straight rack."""

from __future__ import annotations

import math

import pytest

import paper_drive_mesh_check as mesh
import pd_platen_rack_spec as rack
import pd_rack_pinion_spec as disc
import pd_transgear_feed_pinion_spec as feed


def test_both_meshes_pass_the_standard_gates() -> None:
    assert mesh.feed_rack_mesh().failures() == []
    assert mesh.reducer_mesh().failures() == []


def test_reducer_centre_sits_inside_its_derived_window() -> None:
    # pd_rack_pinion_spec states the window: the interference point at the
    # tight extreme (centre less the 0.05 TIR shift) bounds it below, CR 1.2
    # at the minimum tips above. The centre is the window's midpoint.
    centre = disc.CENTRE_DISTANCE
    assert mesh.reducer_runout_shift_mm() == pytest.approx(0.05)
    assert mesh.reducer_mesh(35.097).interference_margin_min_mm >= 0.0
    assert mesh.reducer_mesh(35.096).interference_margin_min_mm < 0.0
    assert mesh.reducer_mesh(35.105).contact_ratio_min >= mesh.CONTACT_RATIO_FLOOR
    assert mesh.reducer_mesh(35.106).contact_ratio_min < mesh.CONTACT_RATIO_FLOOR
    assert centre == pytest.approx((35.097 + 35.105) / 2.0)
    assert mesh.reducer_mesh(centre).failures() == []
    # The superseded 35.183 centre fails the contact-ratio gate.
    assert "contact ratio" in " ".join(mesh.reducer_mesh(35.183).failures())


def test_reducer_formulas_reduce_to_the_standard_mesh() -> None:
    # At the standard centre the operating angle is the cutting angle, so
    # standard-thickness teeth (half the circular pitch) have zero backlash.
    standard = disc.STANDARD_CENTRE_DISTANCE
    half_pitch = math.pi * disc.MODULE_MM / 2.0
    assert mesh.reducer_backlash_mm(standard, half_pitch, half_pitch) == pytest.approx(0.0, abs=1e-12)


def _rotate(point: tuple[float, float], angle: float) -> tuple[float, float]:
    c, s = math.cos(angle), math.sin(angle)
    return c * point[0] - s * point[1], s * point[0] + c * point[1]


def _numeric_rack_contact_ratio(profile, axis_distance_mm: float, samples: int = 4000) -> float:
    """Step one translated flank through mesh against the straight rack.

    The profile frame has a gap bisector on +x. A rack flank at pressure
    angle a touches the pinion where the pinion flank's outward normal
    turns to (cos a, sin a) in the world, with the gap first turned to face
    the rack (+y). Contact is real only when that point lies below the rack
    crest line. The pinion angle spanned by one tooth's real contacts over
    its angular pitch is the contact ratio.
    """
    angle = math.radians(feed.PRESSURE_ANGLE_DEG)
    crest = axis_distance_mm - rack.ADDENDUM
    low, high = max(0.0, profile.flank_parameter_min), profile.flank_parameter_max
    turns = []
    for index in range(samples + 1):
        u = low + (high - low) * index / samples
        normal = profile.flank_normal(u, 1)
        turn = math.remainder(angle - math.pi / 2.0 - math.atan2(normal[1], normal[0]), 2.0 * math.pi)
        if _rotate(profile.flank_point(u, 1), math.pi / 2.0 + turn)[1] >= crest:
            turns.append(turn)
    return (max(turns) - min(turns)) / (2.0 * math.pi / feed.TEETH)


def test_numeric_rack_contact_ratio_agrees_with_the_closed_form() -> None:
    # Loose datum end, minimum-OD corner at both translation limits: the
    # translated #8 form exactly as stock_form_cutter generates it.
    loose = feed.RACK_BACKLASH_RANGE[1]
    tip = min(p.blank_radius_mm for p in feed.manufactured_profiles())
    numeric = []
    for profile in feed.manufactured_profiles():
        if profile.blank_radius_mm != tip:
            continue
        distance = mesh.feed_rack_axis_distance_mm(loose, profile.radial_translation_mm)
        numeric.append(_numeric_rack_contact_ratio(profile, distance))
    assert min(numeric) >= mesh.CONTACT_RATIO_FLOOR
    assert min(numeric) == pytest.approx(mesh.feed_rack_mesh().contact_ratio_min, abs=0.01)
