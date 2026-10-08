"""SolidWorks-free acceptance checks for the metric paper-drive experiment."""
import math

import pytest

import pd_paper_drive_assembly_steps as steps
import pd_rack_pinion_spec as disc
import pd_transgear_feed_pinion_spec as feed
import pd_transgear_knob_shaft_spec as knob
import paper_drive_geom as law


def test_matched_modules_and_shift():
    assert 25.4 / disc.DIAMETRAL_PITCH == pytest.approx(0.7)
    assert knob.DIAMETRAL_PITCH == disc.DIAMETRAL_PITCH
    assert feed.MODULE_MM == pytest.approx(0.8)
    assert disc.PRESSURE_ANGLE_DEG == knob.PRESSURE_ANGLE_DEG == feed.PRESSURE_ANGLE_DEG == 20.0
    minimum = 1.0 - 6.0 * math.sin(math.radians(20.0)) ** 2
    assert knob.PROFILE_SHIFT == pytest.approx(minimum)
    assert feed.PROFILE_SHIFT == pytest.approx(minimum)


def test_feed_mesh_band_and_nominal():
    steps.check_mesh_band(steps.MESH_BACKLASH_RANGE)
    extension = steps.mesh_extension(0.12)
    assert steps.feed_mesh_penetration(extension) <= 1e-5
    assert steps.feed_mesh_contact_ratio(extension) >= 1.2
    assert feed.ROOT_DIA_MIN <= feed.ROOT_DIA


def test_disc_contact_ratio_and_base_interference():
    pa = math.radians(disc.PRESSURE_ANGLE_DEG)
    rb1 = knob.PITCH_DIA / 2 * math.cos(pa)
    rb2 = disc.PITCH_DIA / 2 * math.cos(pa)
    ra1 = knob.OUTSIDE_DIA / 2
    ra2 = disc.OUTSIDE_DIA / 2
    line = math.sqrt(disc.CENTRE_DISTANCE ** 2 - (rb1 + rb2) ** 2)
    q1 = math.sqrt(ra1 ** 2 - rb1 ** 2)
    q2 = math.sqrt(ra2 ** 2 - rb2 ** 2)
    assert q1 < line and q2 < line
    ratio = (q1 + q2 - line) / (math.pi * disc.MODULE_MM * math.cos(pa))
    assert ratio >= 1.2
    assert disc.CENTRE_DISTANCE - ra2 - knob.ROOT_DIA / 2 > 0


def test_reference_feed_travel_not_shifted_circumference():
    assert law.NET_RACK_TRAVEL_PER_CRANK_REV == pytest.approx(1.5079644737231008)
    assert law.FEED_TRAVEL_CHANGE_PERCENT == pytest.approx(-5.511811023622047)
