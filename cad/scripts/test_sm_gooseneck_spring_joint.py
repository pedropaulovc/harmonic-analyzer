"""Offline full-thread, wall and capture contracts for the upper spring clamp."""

from __future__ import annotations

import pytest

import sm_gooseneck_geom as gooseneck
import sm_gooseneck_spring_joint as joint
import vn_counter_spring_stock_geom as spring
import vn_gooseneck_spring_screw_spec as screw


def test_through_plug_keeps_full_engagement_at_both_broken_edges() -> None:
    shortest_plug = gooseneck.PLUG_LENGTH - joint.PLUG_LENGTH_BAND
    full_thread = shortest_plug - 2.0 * joint.EDGE_BREAK
    assert full_thread >= 1.5 * screw.MAJOR_DIA
    # Even the shortest screw's incomplete tip starts beyond the longest plug.
    longest_plug = gooseneck.PLUG_LENGTH + joint.PLUG_LENGTH_BAND
    full_tip_reach = (
        screw.LENGTH
        - screw.LENGTH_MINUS
        - gooseneck.SPRING_EYE_GAP
        - 1.5 * screw.PITCH
    )
    assert full_tip_reach > longest_plug
    # The rejected 3/4-inch alternate cannot cover that complete receiver.
    assert full_tip_reach - 6.35 < longest_plug


def test_tap_has_novice_shop_wall_at_offset_and_wander_corner() -> None:
    nominal_wall = (joint.PLUG_DIA - screw.MAJOR_DIA) / 2.0
    worst_wall = (
        (joint.PLUG_DIA - joint.PLUG_DIAMETER_BAND - screw.MAJOR_DIA) / 2.0
        - joint.THREAD_AXIS_OFFSET_MAX
        - joint.DRILL_WANDER_MAX
    )
    assert nominal_wall >= 2.0
    assert worst_wall >= 1.5


def test_screw_tip_exits_plug_without_reaching_tube_wall_or_bend() -> None:
    longest_plug = gooseneck.PLUG_LENGTH + joint.PLUG_LENGTH_BAND
    shortest_reach = screw.LENGTH - screw.LENGTH_MINUS - gooseneck.SPRING_EYE_GAP
    assert shortest_reach > longest_plug
    assert joint.PLUG_INNER_X < joint.SCREW_TIP_X < -gooseneck.BEND_R
    smallest_bore = joint.PLUG_DIA - joint.PLUG_DIAMETER_BAND
    assert smallest_bore / 2.0 > (
        screw.MAJOR_DIA / 2.0
        + joint.THREAD_AXIS_OFFSET_MAX
        + joint.DRILL_WANDER_MAX
    )


def test_clamped_eye_stays_at_existing_station_and_has_radial_capture() -> None:
    eye_x = gooseneck.ARM_END_X - spring.END_OCCUPIED_WIDTH_MM / 2.0
    assert eye_x == pytest.approx(-105.8)
    assert gooseneck.SPRING_EYE_GAP == spring.END_OCCUPIED_WIDTH_MM
    assert (screw.HEAD_DIA - spring.EYE_ID_MM) / 2.0 >= 1.0
    assert screw.MAJOR_DIA < spring.EYE_ID_MM
