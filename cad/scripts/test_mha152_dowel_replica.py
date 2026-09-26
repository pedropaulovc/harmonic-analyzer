"""MHA-152: the cone tip block's dowel pin, McMaster 98381A472 (#917 R5).

SolidWorks-free: the tracked replay's section, read offline from the vendor
file's Parasolid partition, its analytic mass properties, and the replica-gate
registration.  The replay itself is untested on a seat until the amet window
runs ``diag_dump_part`` + ``diag_build_mcmaster 98381A472``.
"""

from __future__ import annotations

import math

import pytest

from diagnostics import diag_build_98381A472 as recipe

MM_PER_IN = 25.4


def test_replay_section_is_the_vendor_pin() -> None:
    """The vendor file's own section: a 1/8 x 5/8 pin, a 16 deg lead-in on one
    end and an R.016 crown blend on the other (the values its Parasolid
    partition carries: r 1.5875, half-length 7.9375, lead start -7.494598,
    lead end r 1.4605, crown R 0.4064 centred at z 7.5311 and r 1.1811)."""
    assert 2.0 * recipe.PIN_RADIUS == pytest.approx(0.125 * MM_PER_IN)
    assert recipe.PIN_LENGTH == pytest.approx(0.625 * MM_PER_IN)
    assert recipe.PIN_END_Y == pytest.approx((-7.9375, 7.9375))
    assert recipe.LEAD_HALF_ANGLE_DEG == 16.0
    lead_axial = recipe.LEAD_RADIAL / math.tan(math.radians(16.0))
    assert recipe.LEAD_START_Y == pytest.approx(-recipe.PIN_LENGTH / 2.0 + lead_axial)
    assert recipe.LEAD_START_Y == pytest.approx(-7.494598, abs=1e-6)
    assert recipe.LEAD_END_RADIUS == pytest.approx(1.4605)
    # The crown blend is tangent to the flank and to the end face.
    assert recipe.CROWN_CENTRE_R + recipe.CROWN_R == pytest.approx(recipe.PIN_RADIUS)
    assert recipe.CROWN_CENTRE_Y + recipe.CROWN_R == pytest.approx(
        recipe.PIN_LENGTH / 2.0
    )
    assert recipe.CROWN_CENTRE_Y == pytest.approx(7.5311)
    assert recipe.CROWN_CENTRE_R == pytest.approx(1.1811)
    assert recipe.CROWN_R == pytest.approx(0.016 * MM_PER_IN)


def test_replay_mass_properties_are_analytic() -> None:
    r, re_ = recipe.PIN_RADIUS, recipe.LEAD_END_RADIUS
    a = recipe.LEAD_START_Y + recipe.PIN_LENGTH / 2.0
    flank = recipe.CROWN_CENTRE_Y - recipe.LEAD_START_Y
    rc, rr = recipe.CROWN_CENTRE_R, recipe.CROWN_R
    volume = (
        math.pi * r * r * flank
        + math.pi * a / 3.0 * (r * r + r * re_ + re_ * re_)
        + math.pi * (rc * rc * rr + rc * math.pi * rr * rr / 2.0 + 2.0 * rr**3 / 3.0)
    )
    area = (
        2.0 * math.pi * r * flank
        + math.pi * (r + re_) * math.hypot(a, r - re_)
        + math.pi * re_ * re_
        + math.pi * rc * rc
        + 2.0 * math.pi * rr * (rc * math.pi / 2.0 + rr)
    )
    assert recipe.VOLUME_MM3 == pytest.approx(volume)
    assert recipe.AREA_MM2 == pytest.approx(area)
    assert recipe.FACE_COUNT == 5
    assert round(recipe.VOLUME_MM3, 3) == 125.081
    assert round(recipe.AREA_MM2, 3) == 171.145


def test_replica_gate_is_registered() -> None:
    from diagnostics import diag_build_mcmaster as driver

    assert driver.REGISTRY["98381A472"] is recipe.build_98381A472
