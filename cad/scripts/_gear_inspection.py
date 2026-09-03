r"""Measurement-over-pins acceptance for the gear sheets (pure math, no COM).

A gear print that states DP / N / PA / OD fixes the tooth SYSTEM but gives
the machinist nothing to put a micrometer on: the involute OD is a scalloped
outline and the whole depth is a cutter setting, not an inspection. The
standard shop acceptance is the measurement over two pins (Machinery's
Handbook, "Checking Gear Size by Measurement Over Pins"): drop two pins of a
stated diameter into diametrically opposite tooth spaces and read across them
with an ordinary micrometer. Every gear-data block carries that one row; this
module computes it so the specs never hand-type a derived number.

Formulas (external gear, standard proportions, ISO/DIN 3960 form -- the same
result as Machinery's Handbook for a spur gear, and it extends to a helical
gear through the base helix angle):

    inv(a)   = tan(a) - a
    d        = N * m_t                     transverse pitch diameter
    d_b      = d * cos(a_t)                base diameter
    t_t      = pi * m_t / 2 - thinning     transverse circular tooth thickness
    inv(a_M) = t_t / d + inv(a_t) + d_pin / (d_b * cos(b_b)) - pi / N
    M (even N) = d_b / cos(a_M) + d_pin
    M (odd  N) = d_b * cos(90 deg / N) / cos(a_M) + d_pin

with ``a_t`` the transverse pressure angle, ``b_b`` the base helix angle
(``cos b_b = cos b * cos a_n / cos a_t``; zero for a spur gear) and ``m_t``
the transverse module.  Lengths are millimetres throughout; the diametral
pitches this repo uses are inch-based, so ``m_t = 25.4 / DP``.

Importable from both the part and the drawing tier (like ``_fit_limits`` /
``_surface_finish``): no adapter, no COM, nothing but ``math``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

MM_PER_IN = 25.4

# Acceptance band on the over-pins reading, quoted the way the OD band is.
# Minus only: an undersize reading means thinner teeth (backlash), the safe
# side for a train meshed at fixed centres; oversize teeth bind.  At 14.5 deg
# a 0.10 mm drop in the reading is ~0.035 mm off one tooth thickness.
OVER_PINS_BAND_TEXT = "+0/-0.10"

# A pin must stand proud of the tooth tips by at least this much for the
# micrometer anvils to bear on the pins rather than the OD, and its contact
# point must sit at least this far above the base circle so it bears on the
# involute flank (the modelled flank starts exactly at the base circle).
MIN_PIN_PROTRUSION_MM = 0.10
MIN_CONTACT_ABOVE_BASE_MM = 0.04


def involute(angle_rad: float) -> float:
    return math.tan(angle_rad) - angle_rad


def inverse_involute(value: float) -> float:
    """Pressure angle (rad) whose involute function equals ``value``."""
    if value <= 0.0:
        raise ValueError(f"involute function must be positive, got {value!r}")
    angle = 0.3
    for _ in range(100):
        step = (involute(angle) - value) / math.tan(angle) ** 2
        angle -= step
        if abs(step) < 1e-15:
            break
    return angle


def diametral_pitch_text(diametral_pitch: float) -> str:
    """``38`` for an integer DP, ``49.82`` otherwise -- a cutter designation
    does not carry false decimals."""
    text = f"{diametral_pitch:.2f}".rstrip("0").rstrip(".")
    return text


@dataclass(frozen=True)
class PinMeasurement:
    """One over-pins acceptance: the reading and the geometry that proves the
    pin is usable on this tooth."""

    teeth: int
    pin_dia_mm: float
    over_pins_mm: float
    contact_angle_deg: float
    contact_radius_mm: float
    base_radius_mm: float
    outside_radius_mm: float

    @property
    def pin_protrusion_mm(self) -> float:
        """How far the pin's outer extreme stands past the tooth tips."""
        return self.over_pins_mm / 2.0 - self.outside_radius_mm

    @property
    def contact_above_base_mm(self) -> float:
        return self.contact_radius_mm - self.base_radius_mm

    @property
    def usable(self) -> bool:
        return (
            self.pin_protrusion_mm >= MIN_PIN_PROTRUSION_MM
            and self.contact_above_base_mm >= MIN_CONTACT_ABOVE_BASE_MM
            and self.contact_radius_mm < self.outside_radius_mm
        )


def pin_measurement(
    *,
    teeth: int,
    diametral_pitch: float,
    pressure_angle_deg: float,
    pin_dia_mm: float,
    helix_angle_deg: float = 0.0,
    tooth_thinning_mm: float = 0.0,
) -> PinMeasurement:
    """Measurement over two pins for an external involute gear.

    ``pressure_angle_deg`` and ``diametral_pitch`` are TRANSVERSE values (what
    every gear-data block in this repo states); ``tooth_thinning_mm`` is the
    transverse circular-thickness reduction at the pitch circle (backlash
    allowance cut into this gear), zero for a standard tooth.
    """
    if teeth < 3:
        raise ValueError(f"teeth must be >= 3, got {teeth}")
    if pin_dia_mm <= 0.0:
        raise ValueError(f"pin diameter must be positive, got {pin_dia_mm!r}")
    module_t = MM_PER_IN / diametral_pitch
    pitch_dia = teeth * module_t
    alpha_t = math.radians(pressure_angle_deg)
    beta = math.radians(helix_angle_deg)
    alpha_n = math.atan(math.tan(alpha_t) * math.cos(beta))
    cos_beta_b = math.cos(beta) * math.cos(alpha_n) / math.cos(alpha_t)
    base_dia = pitch_dia * math.cos(alpha_t)
    thickness_t = math.pi * module_t / 2.0 - tooth_thinning_mm
    inv_alpha_m = (
        thickness_t / pitch_dia
        + involute(alpha_t)
        + pin_dia_mm / (base_dia * cos_beta_b)
        - math.pi / teeth
    )
    alpha_m = inverse_involute(inv_alpha_m)
    over_pins = base_dia / math.cos(alpha_m) + pin_dia_mm
    if teeth % 2:
        over_pins = base_dia * math.cos(math.pi / (2.0 * teeth)) / math.cos(alpha_m) + pin_dia_mm
    base_r = base_dia / 2.0
    # The pin touches the flank where the line of action through the pin
    # centre is tangent to the base circle.
    contact_r = math.hypot(base_r, base_r * math.tan(alpha_m) - pin_dia_mm / 2.0)
    outside_r = (teeth + 2.0) / diametral_pitch / 2.0 * MM_PER_IN
    return PinMeasurement(
        teeth=teeth,
        pin_dia_mm=pin_dia_mm,
        over_pins_mm=over_pins,
        contact_angle_deg=math.degrees(alpha_m),
        contact_radius_mm=contact_r,
        base_radius_mm=base_r,
        outside_radius_mm=outside_r,
    )


def over_pins_row(measurement: PinMeasurement) -> tuple[str, str]:
    """The gear-data row: ``("OVER 2 PINS 1.00 DIA", "63.00 +0/-0.10")``."""
    if not measurement.usable:
        raise ValueError(
            f"{measurement.pin_dia_mm:.2f} pin is not usable on a "
            f"{measurement.teeth}T gear: protrusion "
            f"{measurement.pin_protrusion_mm:.3f}, contact "
            f"{measurement.contact_above_base_mm:.3f} above base"
        )
    return (
        f"OVER 2 PINS {measurement.pin_dia_mm:.2f} DIA",
        f"{measurement.over_pins_mm:.2f} {OVER_PINS_BAND_TEXT}",
    )
