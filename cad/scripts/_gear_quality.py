"""Shared drawn stock-form inspection limits; never a mesh verdict.

The tooth-space limit is total indicated runout against the functional
running journal/bore. For the disc it applies to the indicated, locked,
match-marked disc/hub/feed-sleeve cluster on the feed running-bore mandrel;
a disc-part measurement against its locating pilot is not equivalent.
The ordinary turned-shaft limit remains separate from this tooth-space
control. Position is a diametral circular zone, not a coordinate +/- band.
"""

from __future__ import annotations

import math

import _config


def _positive_limit_mm(key: str) -> float:
    value = _config.fit("stock_form_quality", key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"stock-form quality {key} must be a numeric millimetre limit")
    value = float(value)
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"stock-form quality {key} must be finite and positive")
    return value


def toothspace_runout_tir_mm() -> float:
    """Total tooth-space runout; rotating eccentricity is at most half this."""
    return _positive_limit_mm("toothspace_runout_tir_mm")


def reducer_position_diameter_mm() -> float:
    """Drawn circular position-zone diameter for the reducer locating holes."""
    return _positive_limit_mm("reducer_position_diameter_mm")


def shaft_turned_runout_mm() -> float:
    """Ordinary turned-core total runout to the shaft's running datum."""
    return _positive_limit_mm("shaft_turned_runout_mm")


def reducer_axis_projected_zone_diameter_mm() -> float:
    """S/K axis diametral zones continued through the actual gear/wheel planes."""
    return _positive_limit_mm("reducer_axis_projected_zone_diameter_mm")


def arm_opposite_face_parallelism_mm() -> float:
    """Arm rear mounting face parallelism to its front, over the drawn seat."""
    return _positive_limit_mm("arm_opposite_face_parallelism_mm")


def recording_paper_width_deviation_mm() -> float:
    """Maximum absolute cut-paper width error; reject outside this band."""
    return _positive_limit_mm("recording_paper_width_deviation_mm")


def recording_paper_left_inset_deviation_mm() -> float:
    """Maximum absolute installed paper inset error from the platen/rack end."""
    return _positive_limit_mm("recording_paper_left_inset_deviation_mm")


def recording_pen_x_deviation_mm() -> float:
    """Maximum inspected nib machine-X error, before running-stud movement."""
    return _positive_limit_mm("recording_pen_x_deviation_mm")


def rack_flank_constraint_deviation_mm() -> float:
    """Whole-stock relative X-intercept error across BOTH flanks and all gaps.

    The intercept is x +/- tan(20 degrees)*y in one captured material datum,
    not a unit-normal distance. Its range includes uniform gap-width error.
    Index-only over-pins spans cannot supply this control.
    """
    return _positive_limit_mm("rack_flank_constraint_deviation_mm")


def rack_root_material_intrusion_mm() -> float:
    """Whole root-material intrusion MAX, including indicator uncertainty.

    The current closing/projection root-air budget sets the receiving limit;
    it is subtracted from native root air, never used to relax the root floor.
    This is a conditional inspection/rejection control, not supplier accuracy.
    """
    return _positive_limit_mm("rack_root_material_intrusion_mm")


def stock_form_receiving_status_text() -> str:
    """Draw the authoritative allocation status, never a physical mesh verdict."""
    status = _config.fit("stock_form_quality", "receiving_allocation_status")
    if status == "provisional":
        return "PROVISIONAL / NOT SHOP-RELEASED"
    if status == "released":
        return "RELEASED RECEIVING ALLOCATION"
    raise ValueError("stock-form receiving allocation status must be provisional or released")


def rack_working_side_angle_deviation_deg() -> float:
    """Positive working-side PA half-band under the named straight-form model."""
    key = "rack_working_side_angle_deviation_deg"
    value = _config.fit("stock_form_quality", key)
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value <= 0.0):
        raise ValueError("rack working-side angle deviation must be finite positive degrees")
    return float(value)


def rack_flank_secant_minimum_height_mm() -> float:
    """Minimum same-wire vertical separation; not a local-normal certificate."""
    return _positive_limit_mm("rack_flank_secant_minimum_height_mm")


def purchased_rack_working_side_form_model_premise() -> str:
    """Named SIDE-only model assumption; never received/vendor accuracy."""
    value = _config.fit("stock_form_quality", "purchased_rack_working_side_form_model_premise")
    if value != "PURCHASED_RACK_32DP_PA20_STRAIGHT_SMOOTH_WORKING_SIDE_FORM":
        raise ValueError("the source purchased-rack working-side form MODEL premise is required")
    return value


def rack_form_admission_controls() -> dict:
    """Full material/intercept controls at the declared shop resolution.

    Complete active XY/root envelopes remain independently required. The
    named straight/smooth WORKING-SIDE model supplies a bounded side normal;
    same-wire finite secants back its angle admission, not arbitrary local
    normals or vendor accuracy. Crest/root/birth cones remain fully physical.
    """
    return {
        "constraint_relative_mm": rack_flank_constraint_deviation_mm(),
        "active_boundary_mm": rack_flank_constraint_deviation_mm(),
        "root_intrusion_mm": rack_root_material_intrusion_mm(),
        "wire_measurement_uncertainty_mm": wire_measurement_uncertainty_mm(),
        "indicator_measurement_uncertainty_mm": pitch_index_measurement_uncertainty_mm(),
        "working_side_angle_deviation_deg": rack_working_side_angle_deviation_deg(),
        "working_side_secant_minimum_height_mm": rack_flank_secant_minimum_height_mm(),
        "working_side_form_model_premise": purchased_rack_working_side_form_model_premise(),
        "status_text": stock_form_receiving_status_text(),
    }


def rack_pitch_index_deviation_mm() -> float:
    """Maximum RELATIVE local/cumulative rack index error between any stations."""
    return _positive_limit_mm("rack_pitch_index_deviation_mm")


def pinion_pitch_index_deviation_mm() -> float:
    """Maximum RELATIVE tooth-space index error at the actual reference radius."""
    return _positive_limit_mm("pinion_pitch_index_deviation_mm")


def rack_face_lead_deviation_mm() -> float:
    """Assembled rigid face/axis misalignment; intrinsic stock lead is in form."""
    return _positive_limit_mm("rack_face_lead_deviation_mm")


def pitch_index_measurement_uncertainty_mm() -> float:
    """Absolute indicator uncertainty; used by each calibrated XY/index reading."""
    return _positive_limit_mm("pitch_index_measurement_uncertainty_mm")


def wire_measurement_uncertainty_mm() -> float:
    """Absolute shop micrometer uncertainty on the measured wire/pin diameter."""
    return _positive_limit_mm("wire_measurement_uncertainty_mm")


def require_pitch_index_measurements_mm(
    *,
    measured_index_errors_mm: dict[int, float],
    required_stations: tuple[int, ...],
    relative_deviation_limit_mm: float,
    absolute_measurement_uncertainty_mm: float,
) -> float:
    """Receive ALL stations against ONE datum, paying calibration uncertainty.

    Errors are cumulative positions at the actual reference line after
    correcting the gauge with its certified actual diameter. Max-minus-min
    encloses EVERY local/cumulative span; a pinion also requires its wrap
    station. Radial TIR and one span-thickness reading do not supply index.
    """
    if (not required_stations or len(set(required_stations)) != len(required_stations)
            or set(measured_index_errors_mm) != set(required_stations)):
        raise ValueError("index receiving requires every specified station exactly once")
    for value, label in (
        (relative_deviation_limit_mm, "relative index acceptance"),
        (absolute_measurement_uncertainty_mm, "absolute measurement uncertainty"),
    ):
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or value <= 0.0):
            raise ValueError(f"{label} must be finite numeric and positive")
    values = tuple(measured_index_errors_mm[station] for station in required_stations)
    if any(isinstance(value, bool) or not isinstance(value, (int, float))
           or not math.isfinite(value) for value in values):
        raise ValueError("index receiving measurements must be finite numeric millimetres")
    deviation = max(values) - min(values) + 2.0 * absolute_measurement_uncertainty_mm
    if deviation > relative_deviation_limit_mm:
        raise ValueError(
            f"REJECT paid pitch/index range {deviation:.6f} mm exceeds "
            f"{relative_deviation_limit_mm:.6f} mm"
        )
    return deviation


def rack_face_width_max_mm() -> float:
    """Incoming measured maximum rack face width, not a catalog stock tolerance."""
    return _positive_limit_mm("rack_face_width_max_mm")


def rack_stock_height_max_mm() -> float:
    """Incoming measured stock height; separate from face width and catalog REF."""
    return _positive_limit_mm("rack_stock_height_max_mm")


def reducer_setup_clock_deviation_mm() -> float:
    """Absolute one-time matched reducer clock setup error, including uncertainty."""
    return _positive_limit_mm("reducer_setup_clock_deviation_mm")
