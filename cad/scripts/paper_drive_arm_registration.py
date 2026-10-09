"""Critical matched gear-plane and seat inspection, not stock-pin certification.

The two round patterns are COUPLED matched pilots and separately finished
press/slip bores. Their own-datum position inspections, free-hand assembly,
and drawn S-K setting are all mandatory; independent patterns are not
promised to assemble. No countersink/shank centring or clamp-friction credit.
The directly inspected loaded K-motion budget includes pin play AND seat
motion; do not add that same loaded tilt to K a second time.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import pd_transgear_arm_geometry as ARM
import pd_transgear_arm_plate_geometry as PLATE
import pd_transgear_drive_collar_spec as COLLAR
import pd_transgear_knob_shaft_spec as SHAFT
import pd_transgear_knob_thrust_ring_spec as RING
import pd_transgear_removable_spec as WHEEL
from _gear_quality import (
    arm_opposite_face_parallelism_mm,
    reducer_axis_projected_zone_diameter_mm,
    reducer_position_diameter_mm,
)
from _printed_tolerance import printed_band_mm

ARM_LOCATOR_SITES_MM = ARM.LOCATOR_SITES_MM
PLATE_LOCATOR_SITES_MM = PLATE.LOCATOR_SITES_MM
LOCATOR_PAIR_BASELINE_MM = ARM.LOCATOR_PAIR_BASELINE_MM
REDUCER_AXIS_SETUP_RADIUS_MM = reducer_position_diameter_mm() / 2.0
LOCATOR_GEAR_PLANE_TRAVEL_MAX_MM = 2.0 * reducer_position_diameter_mm()
LOCATOR_COORDINATE_TRAVEL_MAX_MM = math.floor(
    LOCATOR_GEAR_PLANE_TRAVEL_MAX_MM / math.sqrt(2.0) * 1e4
) / 1e4  # inward printed acceptance, not a looser unprinted threshold
ARM_SEAT_SPAN_MIN_MM = 13.7  # drawn indicator support requirement, not a stock-pin contact span
ARM_PLATE_LOADED_NORMAL_CHANGE_MAX_MM = arm_opposite_face_parallelism_mm()
ARM_SEAT_NORMAL_WITNESS_XY_MM = (
    (ARM.PLATE_SCREW_MID_STATION - 13.0, -7.0),
    (ARM.PLATE_SCREW_MID_STATION + 13.0, -7.0),
    (ARM.PLATE_SCREW_MID_STATION + 4.0, 7.5),
)
ARM_SEAT_WITNESS_POSITION_RADIUS_MM = 0.10
ARM_SEAT_INDICATOR_TIP_DIA_MAX_MM = 1.0
# U is for the FULL signed loaded-minus-snug difference, not one reading.
# No tighter independent instrument grade: receive against the actual
# inclusive normal budget, so ordinary indicators may qualify real data.
ARM_SEAT_NORMAL_UNCERTAINTY_MAX_MM = ARM_PLATE_LOADED_NORMAL_CHANGE_MAX_MM
# Triangle support width decreases by at most twice the point-location radius.
ARM_SEAT_WITNESS_MIN_WIDTH_MM = 26.0 * 14.5 / max(
    math.dist(ARM_SEAT_NORMAL_WITNESS_XY_MM[i], ARM_SEAT_NORMAL_WITNESS_XY_MM[j])
    for i, j in ((0, 1), (1, 2), (2, 0))
) - 2.0 * ARM_SEAT_WITNESS_POSITION_RADIUS_MM
if ARM_SEAT_WITNESS_MIN_WIDTH_MM < ARM_SEAT_SPAN_MIN_MM:
    raise AssertionError("actual three-indicator support width is below the charged tilt span")
ARM_OPPOSITE_FACE_PARALLELISM_MM = arm_opposite_face_parallelism_mm()
AXIS_PROJECTED_ZONE_DIAMETER_MM = reducer_axis_projected_zone_diameter_mm()
# Reviewed geometrical head-plane caps. These are SOURCE mm grades; XML
# serialization alone does not prove physical P height on an IPS document.
CLAMP_AXIS_INSPECTION_NOTE = "\n".join((
    f"ARM TAPS: PROJECTED POSITION DIA {reducer_position_diameter_mm():.3f}, ARM A THROUGH z=+{ARM.CLAMP_TAP_PROJECTED_HEIGHT_MM:.1f}.",
    f"PLATE HOLES / EACH CSK AXIS: DIA {reducer_position_diameter_mm():.3f}, MOUNT A THROUGH z=+{PLATE.CLAMP_PLATE_PROJECTED_HEIGHT_MM:.1f}.",
))
ARM_PLATE_TILT_MAX_RAD = (
    math.atan(ARM_OPPOSITE_FACE_PARALLELISM_MM / ARM_SEAT_SPAN_MIN_MM)
    + math.atan(2.0 * ARM_PLATE_LOADED_NORMAL_CHANGE_MAX_MM / ARM_SEAT_SPAN_MIN_MM)
)


def gear_plane_k_loaded_normal_change_bound_mm() -> float:
    """Rigid seat-plane height at K from the three signed indicator grades.

    The screw midpoint lies inside every admitted witness triangle, so its
    normal change is at most e. The actual minimum triangle width bounds
    slope by 2e/h. K lies outside that triangle: extrapolate its true XY
    lever and directly accepted setup/loaded K location, never use e alone
    or infer the plane from unpublished stock-pin end geometry.
    """
    lever = (
        math.hypot(ARM.KNOB_BORE_STATION - ARM.PLATE_SCREW_MID_STATION, ARM.KNOB_BORE_OFFSET)
        + REDUCER_AXIS_SETUP_RADIUS_MM + LOCATOR_GEAR_PLANE_TRAVEL_MAX_MM
    )
    return ARM_PLATE_LOADED_NORMAL_CHANGE_MAX_MM * (1.0 + 2.0 * lever / ARM_SEAT_SPAN_MIN_MM)

ARM_FRONT_MACHINE_Z_MM = ARM.FRONT_FACE_MACHINE_Z
ARM_REAR_MACHINE_Z_MM = ARM_FRONT_MACHINE_Z_MM + ARM.THICKNESS
PLATE_MOUNT_MACHINE_Z_MM = ARM_REAR_MACHINE_Z_MM
KNOB_F_MACHINE_Z_MM = ARM_REAR_MACHINE_Z_MM - (
    PLATE.HUB_FACE_TO_MOUNTING + RING.LENGTH + SHAFT.FACE_WIDTH
)
KNOB_F_AXIAL_BAND_MM = (
    ARM.THICKNESS_BAND + PLATE.HUB_FACE_TO_MOUNTING_BAND
    + RING.LENGTH_TOL + printed_band_mm(SHAFT.FACE_WIDTH_PLACES)
    + SHAFT.END_FLOAT + SHAFT.END_FLOAT_SET_TOL
)
# The fitted collar is NOT nominal +/- a printed band. Its actual accepted
# length range determines the wheel plane and is paid at the farthest end.
CHAIN_PLANE_MACHINE_Z_LIMITS_MM = (
    KNOB_F_MACHINE_Z_MM - KNOB_F_AXIAL_BAND_MM
    - COLLAR.SEAT_MAX_FROM_F - (WHEEL.PLATE + max(WHEEL.PLATE_BAND)) / 2.0,
    KNOB_F_MACHINE_Z_MM + KNOB_F_AXIAL_BAND_MM
    - COLLAR.SEAT_MIN_FROM_F - (WHEEL.PLATE + min(WHEEL.PLATE_BAND)) / 2.0,
)
# The frames print these heights, so they are rounded UP to 0.1 mm: a longer
# projection still reaches the farthest chain plane (run 20261009T214031408Z
# printed the raw float "40.52290000000002" in the arm plate's frame).
S_PROJECTED_HEIGHT_MM = math.ceil(10.0 * (ARM_FRONT_MACHINE_Z_MM - CHAIN_PLANE_MACHINE_Z_LIMITS_MM[0])) / 10.0
K_PROJECTED_HEIGHT_MM = math.ceil(10.0 * (PLATE_MOUNT_MACHINE_Z_MM - CHAIN_PLANE_MACHINE_Z_LIMITS_MM[0])) / 10.0
KNOB_JOURNAL_CONTACT_START_LOCAL_Z_MM = SHAFT.PINION_REAR_Z + RING.LENGTH
KNOB_JOURNAL_CONTACT_END_LOCAL_Z_MM = KNOB_JOURNAL_CONTACT_START_LOCAL_Z_MM + PLATE.HUB_TO_BOSS
KNOB_JOURNAL_CONTACT_SPAN_MIN_MM = (
    PLATE.HUB_TO_BOSS - PLATE.HUB_TO_BOSS_BAND - 2.0 * SHAFT.EDGE_BREAK_MAX
)
KNOB_JOURNAL_CONTACT_FRONT_MACHINE_Z_MM = ARM_REAR_MACHINE_Z_MM + PLATE.HUB_FACE_Z
KNOB_JOURNAL_CONTACT_REAR_MACHINE_Z_MM = ARM_REAR_MACHINE_Z_MM + PLATE.BOSS_FACE_Z


def gear_plane_machine_z_mm() -> float:
    """Native disc face midpoint from the canonical fitted cluster source.

    Lazy import avoids a spec->registration->cluster->spec dependency cycle.
    """
    import transgear_cluster_fit as cluster
    return (cluster.DISC_FRONT_Z + cluster.DISC_REAR_Z) / 2.0




@dataclass(frozen=True, slots=True)
class RegistrationReading:
    """One recorded extreme under a named applied physical load vector."""
    load_case: str
    applied_force_n: tuple[float, float, float]
    applied_moment_nmm: tuple[float, float, float]
    gear_plane_k_xy_mm: tuple[float, float]
    seat_normal_changes_mm: tuple[float, float, float]


def require_matched_registration(
    *, setup_error_xy_mm: tuple[float, float], readings: tuple[RegistrationReading, ...],
    required_load_cases: tuple[str, ...], measurement_uncertainty_mm: float,
    own_datum_patterns_accepted: tuple[bool, bool], free_hand_assembly: bool,
) -> tuple[float, float]:
    """Receive the measured complete push/rock/load extrema, charging uncertainty.

    Required load cases must come from the caller's physical operating-load
    envelope. This receiver checks observations; it does not fabricate or
    certify that the caller's finite load list encloses a continuous domain.
    """
    if (len(own_datum_patterns_accepted) != 2
            or any(accepted is not True for accepted in own_datum_patterns_accepted)
            or free_hand_assembly is not True):
        raise ValueError("both own-datum inspections and matched free-hand assembly are required")
    if (len(setup_error_xy_mm) != 2 or not all(map(math.isfinite, setup_error_xy_mm))
            or math.hypot(*setup_error_xy_mm) + measurement_uncertainty_mm > REDUCER_AXIS_SETUP_RADIUS_MM):
        raise ValueError("actual S-K gear-plane setup fails the drawn position circle")
    if (not required_load_cases or len(set(required_load_cases)) != len(required_load_cases)
            or not math.isfinite(measurement_uncertainty_mm)
            or not 0.0 < measurement_uncertainty_mm <= ARM_SEAT_NORMAL_UNCERTAINTY_MAX_MM
            or not readings or set(row.load_case for row in readings) != set(required_load_cases)):
        raise ValueError("registration requires all named operating loads and positive measurement uncertainty")
    for row in readings:
        if (len(row.applied_force_n) != 3 or len(row.applied_moment_nmm) != 3
                or len(row.gear_plane_k_xy_mm) != 2
                or len(row.seat_normal_changes_mm) != 3
                or not all(map(math.isfinite, (*row.applied_force_n, *row.applied_moment_nmm,
                                               *row.gear_plane_k_xy_mm, *row.seat_normal_changes_mm)))
                or any(abs(delta) + measurement_uncertainty_mm
                       > ARM_PLATE_LOADED_NORMAL_CHANGE_MAX_MM for delta in row.seat_normal_changes_mm)):
            raise ValueError("recorded applied load/pose/seat observation is invalid or exceeds the grade")
    widths = tuple(
        max(row.gear_plane_k_xy_mm[axis] for row in readings)
        - min(row.gear_plane_k_xy_mm[axis] for row in readings)
        + 2.0 * measurement_uncertainty_mm for axis in range(2)
    )
    if any(width > LOCATOR_COORDINATE_TRAVEL_MAX_MM for width in widths):
        raise ValueError("measured loaded K motion exceeds the accepted full two-pose envelope")
    return widths


NORMAL_INSPECTION_NOTE = "\n".join((
    "REAR-FACE INDICATORS NORMAL TO ARM A; SIGNED LOADED - SNUG.",
    "ARM XY: " + "; ".join(f"({x:.3f},{y:.3f})" for x, y in ARM_SEAT_NORMAL_WITNESS_XY_MM) + ".",
    f"TIP DIA {ARM_SEAT_INDICATOR_TIP_DIA_MAX_MM:.1f} MAX; SITE RADIAL ERROR {ARM_SEAT_WITNESS_POSITION_RADIUS_MM:.2f} MAX.",
    f"ALL 3 |NORMAL DELTAS|+U<={ARM_PLATE_LOADED_NORMAL_CHANGE_MAX_MM:.3f}; U>0 FOR FULL LOADED-SNUG DELTA.",
    f"MIN ALL-DIRECTION SPAN {ARM_SEAT_SPAN_MIN_MM:.1f}; NO FRICTION CREDIT.",
))

MATCHED_REGISTRATION_NOTE = "\n".join((
    "MATCHED PAIR: SCREWS CLAMP ONLY; NEVER LOCATE ON COUNTERSINKS.",
    "FIXTURE DRAWN S-K BASIC XY; COMMON 1.80 PILOTS; RETAIN BOTH DATUM CARRIERS.",
    "SEPARATELY FINISH ARM PRESS FROM REAR / PLATE SLIP THROUGH; NEVER OVERREAM ARM.",
    "PRESS AS CALLOUT; MATCH-MARK; FREE HAND ASSEMBLY; INSPECT BOTH OWN-DATUM FCFs.",
    f"FINAL ACTUAL S-K AT GEAR PLANE: DIA {reducer_position_diameter_mm():.3f} RFS.",
    "PUSH +/-X/Y AND ROCK UNDER ALL QUALIFIED LOADS; RECORD EXTREMA AND APPLIED LOADS.",
    f"MAX X/Y RANGE + 2x GAUGE UNCERTAINTY {LOCATOR_COORDINATE_TRAVEL_MAX_MM:.4f} MAX; FULL TRAVEL {LOCATOR_GEAR_PLANE_TRAVEL_MAX_MM:.3f} MAX.",
    "RECORD ALL THREE NORMAL DELTAS AS THE ARM/PLATE NORMAL INSPECTION CALLOUT.",
    "REINSPECT AFTER EVERY REMOVAL OR PIN REPLACEMENT; DO NOT ACCEPT AS-MADE CENTRES.",
))
