"""Closed-form gates for the paper drive's two meshes, plus one numeric
cross-check of the translated feed-pinion form against the straight rack."""

from __future__ import annotations

import math

import pytest

import paper_drive_mesh_check as mesh
import pd_platen_rack_spec as rack
import pd_rack_pinion_spec as disc
import pd_transgear_feed_pinion_spec as feed
import pd_transgear_knob_shaft_spec as knob


def test_both_meshes_pass_the_standard_gates() -> None:
    assert mesh.feed_rack_mesh().failures() == []
    assert mesh.reducer_mesh().failures() == []


def test_reducer_centre_band_is_plus_only_inside_the_gate_window() -> None:
    # Fine-pitch practice: nominal +x/-0. The nominal is the midpoint of the
    # centres the gates allow (interference below, CR 1.2 above); the
    # allowance is the radius of K's drawn setting circle, the catalogue
    # +0.002 in.
    import _gear_quality

    low, high = disc.CENTRE_DISTANCE_WINDOW
    assert mesh.reducer_runout_shift_mm() == pytest.approx(
        (knob.TOOTH_SPACE_RUNOUT_TIR_MM + disc.TOOTH_SPACE_RUNOUT_TIR_MM) / 2.0
    )
    assert low == disc.CENTRE_DISTANCE
    assert disc.CENTRE_DISTANCE_SET_BAND == pytest.approx((high - low, 0.0))
    assert high - low == pytest.approx(_gear_quality.reducer_k_setting_diameter_mm() / 2.0)
    assert high - low <= 0.002 * 25.4
    assert mesh.reducer_mesh(low).failures() == []
    # The gate window around the set band, each edge where its gate bites.
    usable_low, usable_high = 43.736, 43.847
    assert mesh.reducer_mesh(usable_low).failures() == []
    assert mesh.reducer_mesh(usable_low - 0.001).failures() != []
    assert mesh.reducer_mesh(usable_high).failures() == []
    assert mesh.reducer_mesh(usable_high + 0.001).contact_ratio_min < mesh.CONTACT_RATIO_FLOOR
    assert usable_low < low < high < usable_high
    assert disc.CENTRE_DISTANCE_SET_TEXT == "43.794 +0.050/-0"


def test_reducer_band_ends_both_pass_the_design_floors() -> None:
    nominal, top = mesh.reducer_band_meshes()
    assert nominal.failures() == [] and top.failures() == []
    assert nominal.contact_ratio_min == pytest.approx(1.298, abs=5e-4)
    assert nominal.runout_contact_ratio_min == pytest.approx(1.207, abs=5e-4)
    assert top.contact_ratio_min == pytest.approx(1.207, abs=5e-4)
    assert top.runout_contact_ratio_min == pytest.approx(1.1166, abs=5e-4)
    assert top.contact_ratio_min >= mesh.CONTACT_RATIO_FLOOR
    assert top.runout_contact_ratio_min >= mesh.RUNOUT_CONTACT_RATIO_FLOOR
    assert top.backlash_mm[0] > nominal.backlash_mm[0] > 0.0
    assert top.label.endswith("at +0.050")


def _min_tips() -> tuple[float, float]:
    return (
        min(p.blank_radius_mm for p in knob.manufactured_profiles()),
        min(p.blank_radius_mm for p in disc.manufactured_profiles()),
    )


def test_reducer_contact_ratio_has_a_nominal_and_a_runout_tier() -> None:
    # Nominal tier at the centre, runout tier with the centre opened by both
    # tooth-space runouts; both at the minimum printed tips.
    check = mesh.reducer_mesh()
    loose = disc.CENTRE_DISTANCE + mesh.reducer_runout_shift_mm()
    assert check.contact_ratio_min == pytest.approx(
        mesh.reducer_contact_ratio(disc.CENTRE_DISTANCE, *_min_tips())
    )
    assert check.runout_contact_ratio_min == pytest.approx(
        mesh.reducer_contact_ratio(loose, *_min_tips())
    )
    assert check.contact_ratio_min >= mesh.CONTACT_RATIO_FLOOR
    assert check.runout_contact_ratio_min >= mesh.RUNOUT_CONTACT_RATIO_FLOOR
    assert check.runout_contact_ratio_min < check.contact_ratio_min
    assert mesh.RUNOUT_CONTACT_RATIO_FLOOR < mesh.CONTACT_RATIO_FLOOR


def test_runout_tier_fails_on_its_own() -> None:
    # A larger runout that leaves the nominal tier intact must still fail
    # once the loose extreme drops below its floor.
    tips = _min_tips()
    shift = mesh.reducer_runout_shift_mm()
    while mesh.reducer_contact_ratio(disc.CENTRE_DISTANCE + shift, *tips) >= mesh.RUNOUT_CONTACT_RATIO_FLOOR:
        shift += 0.001
    good = mesh.reducer_mesh()
    bad = mesh.MeshCheck(
        good.label, good.contact_ratio_min, good.backlash_mm, good.root_clearance_min_mm,
        good.root_clearance_floor_mm, good.interference_margin_min_mm,
        mesh.reducer_contact_ratio(disc.CENTRE_DISTANCE + shift, *tips),
    )
    assert bad.contact_ratio_min >= mesh.CONTACT_RATIO_FLOOR
    problems = bad.failures()
    assert len(problems) == 1 and problems[0].startswith("runout-extreme contact ratio")
    # The rack mesh takes its contact ratio at its own loose end: no tier.
    assert mesh.feed_rack_mesh().runout_contact_ratio_min is None


@pytest.mark.parametrize("field", [
    "contact_ratio_min", "runout_contact_ratio_min", "backlash_low", "backlash_high",
    "root_clearance_min_mm", "root_clearance_floor_mm", "interference_margin_min_mm",
])
def test_an_undefined_mesh_number_fails_closed(field: str) -> None:
    good = mesh.reducer_mesh()
    values = {
        "label": good.label,
        "contact_ratio_min": good.contact_ratio_min,
        "backlash_mm": good.backlash_mm,
        "root_clearance_min_mm": good.root_clearance_min_mm,
        "root_clearance_floor_mm": good.root_clearance_floor_mm,
        "interference_margin_min_mm": good.interference_margin_min_mm,
        "runout_contact_ratio_min": good.runout_contact_ratio_min,
    }
    if field.startswith("backlash"):
        low, high = good.backlash_mm
        values["backlash_mm"] = (math.nan, high) if field.endswith("low") else (low, math.nan)
    else:
        values[field] = math.nan
    with pytest.raises(ValueError, match="not a finite number"):
        mesh.MeshCheck(**values).require()


@pytest.mark.parametrize("bad", [math.nan, math.inf])
def test_mesh_entry_points_reject_non_finite_inputs(bad: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        mesh.feed_rack_mesh((bad, bad))
    with pytest.raises(ValueError, match="finite"):
        mesh.feed_rack_mesh(extra_opening_mm=bad)
    with pytest.raises(ValueError, match="finite"):
        mesh.reducer_mesh(bad)


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
