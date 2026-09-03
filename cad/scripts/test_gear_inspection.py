"""Offline contracts for the measurement-over-pins module (``_gear_inspection``).

Three independent checks back the formula every gear sheet prints:

1. a worked example in plain arithmetic (the rack-pinion disc) so a reader
   can follow the number on the sheet with a calculator and Machinery's
   Handbook open;
2. a geometric tangency check that never touches the involute-function
   algebra: build the flank curve parametrically, put the pin centre where the
   formula says the pins sit, and confirm the pin just touches the flank;
3. the helical branch against an independent transcription of the DIN 3960 /
   KHK form written in normal-module terms.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

import _gear_inspection as gi


MM_PER_IN = 25.4


def test_worked_example_rack_pinion_disc() -> None:
    # 120T, 38 DP, 14.5 deg, 1.30 pin -- every intermediate written out.
    module_t = MM_PER_IN / 38.0  # 0.668421
    pitch_dia = 120 * module_t  # 80.2105
    alpha = math.radians(14.5)
    base_dia = pitch_dia * math.cos(alpha)  # 77.6556
    inv_alpha = math.tan(alpha) - alpha  # 0.005545
    assert module_t == pytest.approx(0.668421, abs=1e-6)
    assert pitch_dia == pytest.approx(80.2105, abs=1e-4)
    assert base_dia == pytest.approx(77.6556, abs=1e-4)
    assert inv_alpha == pytest.approx(0.005545, abs=1e-6)
    # t/d for a standard tooth is pi/(2N); pin/d_b; minus pi/N.
    inv_alpha_m = math.pi / 240.0 + inv_alpha + 1.30 / base_dia - math.pi / 120.0
    assert inv_alpha_m == pytest.approx(0.009195, abs=1e-6)
    alpha_m = gi.inverse_involute(inv_alpha_m)
    assert math.degrees(alpha_m) == pytest.approx(17.104, abs=1e-3)
    over_pins = base_dia / math.cos(alpha_m) + 1.30  # even N
    assert over_pins == pytest.approx(82.549, abs=1e-3)
    measured = gi.pin_measurement(
        teeth=120, diametral_pitch=38.0, pressure_angle_deg=14.5, pin_dia_mm=1.30
    )
    assert measured.over_pins_mm == pytest.approx(over_pins, abs=1e-9)
    assert gi.over_pins_row(measured) == ("OVER 2 PINS 1.30 DIA", "82.55 +0/-0.10")


def _flank_min_distance_to_pin(
    *, teeth: int, dp: float, pa_deg: float, pin: float, over_pins: float, thinning: float
) -> float:
    """Independent geometry: the involute flank as a parametric curve, the pin
    centre on the tooth-space centreline at the radius the formula implies.

    Flank: ``x = rb (cos t + t sin t)``, ``y = rb (sin t - t cos t)``; its polar
    angle ``t - atan t`` grows with radius, so the tooth lies on the +angle
    side and the space on the -angle side.  At the pitch circle the flank sits
    at ``inv(alpha)``; the space centreline is half a space width further
    round toward -angle.  Even N: two pins are diametrically opposite, so the
    centre radius is ``(M - d) / 2``; odd N: ``(M - d) / (2 cos(90 deg / N))``.
    """
    module_t = MM_PER_IN / dp
    pitch_r = teeth * module_t / 2.0
    alpha = math.radians(pa_deg)
    base_r = pitch_r * math.cos(alpha)
    thickness = math.pi * module_t / 2.0 - thinning
    half_space = (math.pi * module_t - thickness) / (2.0 * pitch_r)
    theta_c = (math.tan(alpha) - alpha) - half_space
    if teeth % 2:
        centre_r = (over_pins - pin) / (2.0 * math.cos(math.pi / (2.0 * teeth)))
    else:
        centre_r = (over_pins - pin) / 2.0
    cx, cy = centre_r * math.cos(theta_c), centre_r * math.sin(theta_c)
    t = np.linspace(0.0, 2.0, 400001)
    x = base_r * (np.cos(t) + t * np.sin(t))
    y = base_r * (np.sin(t) - t * np.cos(t))
    return float(np.hypot(x - cx, y - cy).min())


@pytest.mark.parametrize(
    ("teeth", "dp", "pa_deg", "pin", "thinning"),
    [
        (120, 38.0, 14.5, 1.30, 0.0),  # rack-pinion disc (even N)
        (12, 30.0, 14.5, 1.65, 0.0),  # transgear feed pinion (small N)
        (42, 49.82, 14.5, 1.00, 0.0),  # alignment pinion (fine pitch)
        (7, 49.82, 14.5, 1.00, 0.0),  # odd N, tiny
        (15, 25.73110354953376, 20.0, 1.90, 0.0),  # odd N, 20 deg
        (16, 25.73110354953376, 14.5, 1.90, 0.0),  # crank pinion
        (64, 25.73110354953376, 14.5, 1.90, 0.15),  # thinned tooth (spur form)
    ],
)
def test_pin_is_tangent_to_the_involute_flank(
    teeth: int, dp: float, pa_deg: float, pin: float, thinning: float
) -> None:
    measured = gi.pin_measurement(
        teeth=teeth,
        diametral_pitch=dp,
        pressure_angle_deg=pa_deg,
        pin_dia_mm=pin,
        tooth_thinning_mm=thinning,
    )
    distance = _flank_min_distance_to_pin(
        teeth=teeth,
        dp=dp,
        pa_deg=pa_deg,
        pin=pin,
        over_pins=measured.over_pins_mm,
        thinning=thinning,
    )
    assert distance == pytest.approx(pin / 2.0, abs=2e-5)


def test_helical_branch_matches_the_normal_module_form() -> None:
    # Crank-drive gear: 64T, transverse DP 25.7311, 14.5 deg transverse,
    # 12 deg helix, 0.15 transverse thinning, 1.90 pin.  DIN 3960 / KHK:
    #   inv a_M = inv a_t + d / (m_n z cos a_n) - pi / (2 z) - ds_t / (m_t z)
    teeth, dp, helix, thinning, pin = 64, 25.73110354953376, 12.0, 0.15, 1.90
    module_t = MM_PER_IN / dp
    beta = math.radians(helix)
    alpha_t = math.radians(14.5)
    alpha_n = math.atan(math.tan(alpha_t) * math.cos(beta))
    module_n = module_t * math.cos(beta)
    inv_alpha_m = (
        (math.tan(alpha_t) - alpha_t)
        + pin / (module_n * teeth * math.cos(alpha_n))
        - math.pi / (2.0 * teeth)
        - thinning / (module_t * teeth)
    )
    alpha_m = gi.inverse_involute(inv_alpha_m)
    base_dia = teeth * module_t * math.cos(alpha_t)
    expected = base_dia / math.cos(alpha_m) + pin
    measured = gi.pin_measurement(
        teeth=teeth,
        diametral_pitch=dp,
        pressure_angle_deg=14.5,
        pin_dia_mm=pin,
        helix_angle_deg=helix,
        tooth_thinning_mm=thinning,
    )
    assert measured.over_pins_mm == pytest.approx(expected, abs=1e-9)
    assert measured.usable
    # A helical gear reads larger over pins than its spur twin: the pin sits
    # across the base helix, so it seats less deeply.
    spur = gi.pin_measurement(
        teeth=teeth,
        diametral_pitch=dp,
        pressure_angle_deg=14.5,
        pin_dia_mm=pin,
        tooth_thinning_mm=thinning,
    )
    assert measured.over_pins_mm > spur.over_pins_mm


def test_inverse_involute_round_trips() -> None:
    for degrees in (1.0, 5.0, 14.5, 17.1, 20.0, 30.0, 45.0, 60.0, 80.0):
        angle = math.radians(degrees)
        assert gi.inverse_involute(gi.involute(angle)) == pytest.approx(angle, abs=1e-12)
    with pytest.raises(ValueError):
        gi.inverse_involute(0.0)


def test_usability_boundaries_from_the_fleet_table() -> None:
    # 120T DP 49.82: the Handbook 1.68/P wire (0.85) stands only 0.06 proud;
    # 0.90 clears the 0.10 floor; 1.20 contacts ABOVE the tooth tips.
    cone = dict(teeth=120, diametral_pitch=49.82, pressure_angle_deg=14.5)
    assert not gi.pin_measurement(pin_dia_mm=0.85, **cone).usable
    assert gi.pin_measurement(pin_dia_mm=0.85, **cone).pin_protrusion_mm == pytest.approx(
        0.059, abs=1e-3
    )
    assert gi.pin_measurement(pin_dia_mm=0.90, **cone).usable
    too_big = gi.pin_measurement(pin_dia_mm=1.20, **cone)
    assert not too_big.usable
    assert too_big.contact_radius_mm >= too_big.outside_radius_mm
    # 12T DP 30 feed pinion: 1.40 (the 1.68/P wire) barely protrudes.
    feed = gi.pin_measurement(
        teeth=12, diametral_pitch=30.0, pressure_angle_deg=14.5, pin_dia_mm=1.40
    )
    assert not feed.usable
    assert feed.pin_protrusion_mm == pytest.approx(0.036, abs=1e-3)
    with pytest.raises(ValueError, match="not usable"):
        gi.over_pins_row(feed)


def test_preferred_pin_is_the_handbook_1_92_wire_on_a_0_05_step() -> None:
    assert gi.preferred_pin_dia_mm(49.82) == pytest.approx(1.00)
    assert gi.preferred_pin_dia_mm(38.0) == pytest.approx(1.30)
    assert gi.preferred_pin_dia_mm(30.0) == pytest.approx(1.65)
    assert gi.preferred_pin_dia_mm(25.73110354953376) == pytest.approx(1.90)
    for dp in (49.82, 38.0, 30.0, 25.73110354953376):
        raw = 1.92 / dp * MM_PER_IN
        assert abs(gi.preferred_pin_dia_mm(dp) - raw) <= 0.025 + 1e-9
    with pytest.raises(ValueError):
        gi.preferred_pin_dia_mm(0.0)


def test_one_pin_serves_every_cone_gear_configuration() -> None:
    pin = gi.preferred_pin_dia_mm(49.82)
    for teeth in range(6, 121, 6):
        measured = gi.pin_measurement(
            teeth=teeth, diametral_pitch=49.82, pressure_angle_deg=14.5, pin_dia_mm=pin
        )
        assert measured.usable, teeth
        assert measured.pin_protrusion_mm >= 0.24, teeth
        assert measured.contact_above_base_mm >= 0.08, teeth


def test_diametral_pitch_text_drops_false_decimals() -> None:
    assert gi.diametral_pitch_text(49.82) == "49.82"
    assert gi.diametral_pitch_text(38.0) == "38"
    assert gi.diametral_pitch_text(30.0) == "30"
    assert gi.diametral_pitch_text(25.73110354953376) == "25.73"


def test_input_validation() -> None:
    with pytest.raises(ValueError):
        gi.pin_measurement(
            teeth=2, diametral_pitch=38.0, pressure_angle_deg=14.5, pin_dia_mm=1.0
        )
    with pytest.raises(ValueError):
        gi.pin_measurement(
            teeth=12, diametral_pitch=38.0, pressure_angle_deg=14.5, pin_dia_mm=0.0
        )
