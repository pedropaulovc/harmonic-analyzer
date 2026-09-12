"""Finished pivot acceptance must check both ears and the retaining rims."""

from __future__ import annotations

import pytest

from rod_pivot_spec import check_measured_joint


@pytest.fixture
def joint() -> dict[str, float]:
    # Dimensions of the native three-station fork specimen, in mm.
    return {
        "fork_gap": 2.535,
        "rocker": 2.5,
        "cheek_left": 1.25,
        "cheek_right": 1.25,
        "head_left": 0.4,
        "head_right": 0.4,
        "head_dia_left": 3.0,
        "head_dia_right": 3.0,
        "head_rim_left": 0.4,
        "head_rim_right": 0.4,
        "ear_bore_left": 1.9939,
        "ear_bore_right": 1.9939,
        "bore": 1.9939,
        "journal": 1.98,
        "station_pitch": 7.0565,
    }


def test_rocker_clearance_does_not_hide_a_noninsertable_fork_pin(joint):
    accepted = check_measured_joint(**joint)
    assert accepted["diametral_clearance_mm"] == pytest.approx(0.0139)
    joint["ear_bore_right"] = 1.979
    with pytest.raises(ValueError):
        check_measured_joint(**joint)


def test_a_tall_formed_head_cannot_hide_a_thin_bearing_rim(joint):
    joint.update(head_right=0.7, head_rim_right=0.31)
    accepted = check_measured_joint(**joint)
    assert accepted["minimum_head_rim_mm"] == pytest.approx(0.31)
    joint["head_rim_right"] = 0.29
    with pytest.raises(ValueError):
        check_measured_joint(**joint)


def test_each_head_must_cover_its_own_finished_ear_bore(joint):
    joint.update(head_dia_left=2.8, ear_bore_left=2.1)
    accepted = check_measured_joint(**joint)
    assert accepted["head_overlap_left_mm"] == pytest.approx(0.35)
    joint["ear_bore_left"] = 2.101
    with pytest.raises(ValueError):
        check_measured_joint(**joint)
