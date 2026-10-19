"""Purchased rack receiving controls, independent of paper-drive placement."""

from __future__ import annotations

import math

import pd_transgear_feed_pinion_spec
from _gear_quality import (
    rack_form_admission_controls,
    rack_working_side_angle_deviation_deg,
    purchased_rack_working_side_form_model_premise,
    wire_measurement_uncertainty_mm,
    pitch_index_measurement_uncertainty_mm,
)


def feed_rack_form_admission_controls() -> dict:
    """Whole material controls plus a named bounded WORKING-SIDE model."""
    return rack_form_admission_controls()


def feed_rack_working_side_angle_band_rad() -> tuple[float, float]:
    """Source PA band for straight/smooth SIDES only, not crest/root normals."""
    purchased_rack_working_side_form_model_premise()
    nominal = pd_transgear_feed_pinion_spec.PRESSURE_ANGLE_DEG
    deviation = rack_working_side_angle_deviation_deg()
    if not 0.0 < nominal - deviation <= nominal + deviation < 90.0:
        raise ValueError("rack working-side source PA band must be acute and positive")
    return (
        math.nextafter(math.radians(nominal - deviation), -math.inf),
        math.nextafter(math.radians(nominal + deviation), math.inf),
    )


def feed_rack_receiving_constraint_uncertainty_mm() -> float:
    """Instrument-only signed-intercept U floor; never the complete method U.

    Centre-X/over-pins and actual wire DIAMETER use the +/- mic uncertainty;
    centre-Y uses the indicator uncertainty. The radius correction's actual
    normal projection coefficient is at most sec(PA), not assumed equal to
    nominal. Angle/model, datum, certification and thermal terms still need
    independently paid method enclosures.
    """
    mic = wire_measurement_uncertainty_mm()
    indicator = pitch_index_measurement_uncertainty_mm()
    alpha = math.radians(pd_transgear_feed_pinion_spec.PRESSURE_ANGLE_DEG)
    return math.nextafter(
        mic + math.tan(alpha) * indicator + mic / (2.0 * math.cos(alpha)),
        math.inf,
    )


def feed_rack_receiving_boundary_uncertainty_mm() -> float:
    """Instrument-only XY point-envelope U floor; not a sampling theorem."""
    return math.nextafter(math.hypot(
        wire_measurement_uncertainty_mm(), pitch_index_measurement_uncertainty_mm()
    ), math.inf)


def feed_rack_receiving_root_uncertainty_mm() -> float:
    """Instrument-only root-height U floor; whole root material is still needed."""
    return pitch_index_measurement_uncertainty_mm()
