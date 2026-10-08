"""SolidWorks-free checks of the inch-standard paper experiment."""

import math

import pytest

import paper_drive_geom as law
import pd_rack_pinion_spec as disc
import pd_transgear_feed_pinion_spec as feed
import pd_transgear_knob_shaft_spec as knob
import pd_paper_drive_assembly_steps as mesh


def test_matching_standards_and_shifted_pinions():
    assert (disc.TEETH, disc.DIAMETRAL_PITCH, disc.PRESSURE_ANGLE_DEG) == (120, 40.0, 20.0)
    assert (knob.TEETH, knob.DIAMETRAL_PITCH, knob.PRESSURE_ANGLE_DEG) == (12, 40.0, 20.0)
    assert (feed.TEETH, feed.DIAMETRAL_PITCH, feed.PRESSURE_ANGLE_DEG) == (12, 32.0, 20.0)
    for pinion in (knob, feed):
        shift = 1.0 - pinion.TEETH * math.sin(math.radians(20.0)) ** 2 / 2.0
        assert pinion.PROFILE_SHIFT == pytest.approx(shift)
        module = 25.4 / pinion.DIAMETRAL_PITCH
        assert pinion.OUTSIDE_DIA == pytest.approx(module * (pinion.TEETH + 2 + 2 * shift))
        assert pinion.ROOT_DIA == pytest.approx(module * (pinion.TEETH - 2.5 + 2 * shift))


def test_reducer_contact_and_positive_backlash():
    alpha = math.radians(20.0)
    module = 25.4 / 40.0
    r1, r2 = knob.PITCH_DIA / 2, disc.PITCH_DIA / 2
    rb1, rb2 = r1 * math.cos(alpha), r2 * math.cos(alpha)
    centre = disc.CENTRE_DISTANCE
    working = math.acos((rb1 + rb2) / centre)
    length = centre * math.sin(working)
    q1 = math.sqrt((knob.OUTSIDE_DIA / 2) ** 2 - rb1 ** 2)
    q2 = math.sqrt((disc.OUTSIDE_DIA / 2) ** 2 - rb2 ** 2)
    assert q1 <= length and q2 <= length
    ratio = (q1 + q2 - length) / (math.pi * module * math.cos(alpha))
    assert ratio >= 1.2
    inv = lambda angle: math.tan(angle) - angle
    scaled = centre / (r1 + r2)
    s1 = module * (math.pi / 2 + 2 * knob.PROFILE_SHIFT * math.tan(alpha))
    s2 = module * math.pi / 2
    backlash = scaled * (math.pi * module - s1 - s2 + 2 * (r1 + r2) * (inv(working) - inv(alpha)))
    assert 0.06 < backlash < 0.20
    assert centre - knob.OUTSIDE_DIA / 2 - disc.ROOT_DIA / 2 > 0
    assert centre - disc.OUTSIDE_DIA / 2 - knob.ROOT_DIA / 2 > 0


def test_feed_band_and_travel():
    low, high = (mesh.mesh_extension(value) for value in mesh.MESH_BACKLASH_RANGE)
    assert mesh.feed_mesh_penetration(low) <= 1e-5
    assert mesh.feed_mesh_contact_ratio(high, mesh.TIP_DIA_MIN) >= 1.2
    old = 0.5 * 0.1 * math.pi * 12 * 25.4 / 30
    expected = 0.5 * 0.1 * math.pi * 12 * 25.4 / 32
    assert law.NET_RACK_TRAVEL_PER_CRANK_REV == pytest.approx(expected)
    assert law.NET_RACK_TRAVEL_PER_CRANK_REV / old == pytest.approx(0.9375)


def test_shared_layout_centres():
    import _chain as chain
    import pd_transgear_arm_geometry as arm
    import pd_transgear_arm_plate_geometry as plate
    from cone_line import X_CRANK, Y_CRANK

    assert math.dist(law.STUD_XY, law.KNOB_SHAFT_XY) == pytest.approx(disc.CENTRE_DISTANCE)
    assert chain.KNOB_CENTRE == (-law.KNOB_SHAFT_XY[0], law.KNOB_SHAFT_XY[1])
    assert chain.CRANK_CENTRE == (-X_CRANK, Y_CRANK)
    assert plate.BORE_STATION == arm.KNOB_BORE_STATION
    assert plate.BORE_OFFSET == arm.KNOB_BORE_OFFSET
    assert abs(law.RACK_PITCH_Y - law.STUD_XY[1]) == pytest.approx(feed.RACK_AXIS_DISTANCE)
