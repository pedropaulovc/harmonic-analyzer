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
import pd_transgear_knob_bush_geometry as BUSH
import pd_transgear_drive_collar_spec as COLLAR
import pd_transgear_knob_shaft_spec as SHAFT
import pd_transgear_knob_thrust_ring_spec as RING
import _sprocket_seat_geometry as WHEEL
from _gear_quality import (
    arm_plate_loaded_normal_change_mm,
    reducer_axis_projected_zone_diameter_mm,
    reducer_k_setting_diameter_mm,
    reducer_position_diameter_mm,
)

ARM_LOCATOR_SITES_MM = ARM.LOCATOR_SITES_MM
PLATE_LOCATOR_SITES_MM = PLATE.LOCATOR_SITES_MM
LOCATOR_PAIR_BASELINE_MM = ARM.LOCATOR_PAIR_BASELINE_MM
# K's drawn setting circle about S (MHA-PD-00 VIEW K), Ø.008:
# stock_form_quality.reducer_k_setting_diameter_mm (owner ruling 2026-11-08
# (Pedro), #2144 item 5.3). It bounds K's whole landing error, across S-K
# included; along S-K the set band below is tighter, and both are checked.
REDUCER_AXIS_SETUP_RADIUS_MM = reducer_k_setting_diameter_mm() / 2.0
# The drawn matched setting: K held this band (upper, lower) from
# CENTRE_DISTANCE along S-K (the reducer's set band,
# pd_rack_pinion_spec.CENTRE_DISTANCE_SET_BAND_IN, which the mesh sets).
REDUCER_CENTRE_DISTANCE_SET_BAND_MM = ARM.DISC.CENTRE_DISTANCE_SET_BAND
# Unit vector S -> K in the arm frame (x along the arm, y across), the
# frame of every K reading below.
_S_TO_K = (ARM.KNOB_BORE_STATION - ARM.PIN_STATION, ARM.KNOB_BORE_OFFSET)
S_TO_K_UNIT = (
    _S_TO_K[0] / math.hypot(*_S_TO_K), _S_TO_K[1] / math.hypot(*_S_TO_K)
)
LOCATOR_GEAR_PLANE_TRAVEL_MAX_MM = 2.0 * reducer_position_diameter_mm()
LOCATOR_COORDINATE_TRAVEL_MAX_MM = math.floor(
    LOCATOR_GEAR_PLANE_TRAVEL_MAX_MM / math.sqrt(2.0) * 1e4
) / 1e4  # inward printed acceptance, not a looser unprinted threshold
ARM_SEAT_SPAN_MIN_MM = 13.7  # drawn indicator support requirement, not a stock-pin contact span
ARM_PLATE_LOADED_NORMAL_CHANGE_MAX_MM = arm_plate_loaded_normal_change_mm()
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
# The arm's rear face carries no frame (machinist review, rule 5): it is the
# Online Metals 12095 ground stock's as-supplied face (thickness 3/8
# ±0.001", the precision-ground 1018 row of Online Metals' tool-steel
# tolerances, #2019). What this bounds
# is the plate seat's tilt relative to the arm's own surface under it, not to
# a remote datum: any bow bends both faces together and cancels, so over the
# seat span the relative wedge is the local thickness difference, and the
# band holds the thickness at every point: <= 2 x 0.0254. The owner ruling
# 2026-10-27 (#1379) charges no frame. The governing gate is the
# MHA-PD-VN-56 plate screw's worst full-thread engagement, >= 1.5D.
ARM_OPPOSITE_FACE_PARALLELISM_MM = 2.0 * ARM.THICKNESS_BAND
AXIS_PROJECTED_ZONE_DIAMETER_MM = reducer_axis_projected_zone_diameter_mm()
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
# K's journal is the MHA-PD-28 bush pressed into the flat plate from face A
# (#2425): its hub face stands HUB_LENGTH forward of the shoulder, which a
# full press seats on face A to within SHOULDER_SEAT_GAP_MAX.
KNOB_F_MACHINE_Z_MM = ARM_REAR_MACHINE_Z_MM - (
    BUSH.HUB_LENGTH + RING.LENGTH + SHAFT.FACE_WIDTH
)
KNOB_F_AXIAL_BAND_MM = (
    ARM.THICKNESS_BAND + BUSH.HUB_LENGTH_BAND + BUSH.SHOULDER_SEAT_GAP_MAX
    + RING.LENGTH_TOL + SHAFT.FACE_WIDTH_BAND
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
# The frames print these heights, so they are rounded UP to the inch sheets'
# .001 grid (MHA-PD-18 and MHA-PD-19): a longer projection still reaches the
# farthest chain plane (run 20261009T214031408Z printed the raw float
# "40.52290000000002" in the arm plate's frame).
S_PROJECTED_HEIGHT_MM = (
    math.ceil(1000.0 * (ARM_FRONT_MACHINE_Z_MM - CHAIN_PLANE_MACHINE_Z_LIMITS_MM[0]) / 25.4)
    * 25.4 / 1000.0
)
K_PROJECTED_HEIGHT_MM = (
    math.ceil(1000.0 * (PLATE_MOUNT_MACHINE_Z_MM - CHAIN_PLANE_MACHINE_Z_LIMITS_MM[0]) / 25.4)
    * 25.4 / 1000.0
)
# The pin S's axis zone at the farthest chain plane.  MHA-PD-23 is one
# diameter, a slip fit bonded in MHA-PD-18's reamed bore (owner ruling
# 2026-11-24, fit audit question 4: "pin MHA-PD-23 bonded, no lean check";
# it replaces the #2415 press land):
# its axis may lean in the bore by the bore's plain ⊥ .001 (no projected
# zone, rule 26; owner ruling 2026-11-08 (Pedro), #2144 item 4.1) plus the
# whole diametral gap, over the bonded length, the bore's full-diameter
# length on the thinnest stock.  No credit is taken for the head, clamped on
# the rear face while the bond cures.  The gap charged is the largest the
# sheets accept, not the modelled one: MHA-PD-18's bore refuses the pin
# set's .127 pin, against the pin's smallest modelled shank.
#
# A slip fit leans most with the pin on opposite walls at the two ends of
# the bonded length (Codjiflo on #3494).  Two things follow, and they are
# different quantities:
# - the TILT, S_AXIS_TILT_MAX_RAD: the bore's tilt plus gap / bonded length.
#   S_AXIS_ZONE_DIAMETER_MM is that tilt run on from the bore's front end
#   (the front face's largest edge break behind face A) to
#   S_PROJECTED_HEIGHT_MM.  It is what a tilt consumer divides by the
#   height: the disc's tilt in the airs (pd_cluster_air.S_ZONE_TILT) and in
#   the meshes (paper_drive_geom.reducer_axis_tilt_maxima_rad, which the
#   feed's lateral deviation reads).  Wider than K's
#   AXIS_PROJECTED_ZONE_DIAMETER_MM; MHA-PD-00's collar feeler accepts the
#   collar air it closes (pd_cluster_air.ASSEMBLY_ACCEPTED_COLLAR_SOURCES).
# - the OFFSET, S_AXIS_RADIAL_OFFSET_MAX_MM: where the pin's axis stands at
#   that plane, off the bore's axis at the bore's front end (which the
#   bore's position frame locates).  The leaning pin's axis crosses the
#   bore's at mid-bond, so at the front end it is already half the gap off,
#   and from there the whole tilt (the bore's and the pin's) carries it on:
#   a radius of gap / 2 + tilt x run-on, not half the zone above.  A
#   position consumer reads it (paper_drive_geom's rotating stud error).
#   It moves no tilt, so no air and no mesh closing changes with it.
# The pin's and the bore's numbers are literals pinned by a test to
# pd_transgear_pin_spec and pd_transgear_arm_spec, so pin edits do not
# re-key every importer of this module.
S_PIN_BOND_LENGTH_MIN_MM = 8.9916  # .354
S_PIN_BOND_GAP_MAX_MM = 0.05588  # .0022: the .127 NO-GO less the .1248 shank
S_ARM_FRONT_EDGE_BREAK_MAX_MM = 0.254  # .010, the title block's
S_AXIS_TILT_MAX_RAD = (
    ARM.PIN_BORE_PERPENDICULARITY_MM + S_PIN_BOND_GAP_MAX_MM
) / S_PIN_BOND_LENGTH_MIN_MM
S_AXIS_RUN_ON_MM = S_PROJECTED_HEIGHT_MM + S_ARM_FRONT_EDGE_BREAK_MAX_MM
S_AXIS_ZONE_DIAMETER_MM = S_AXIS_TILT_MAX_RAD * S_AXIS_RUN_ON_MM
S_AXIS_FRONT_END_OFFSET_MAX_MM = S_PIN_BOND_GAP_MAX_MM / 2.0
S_AXIS_RADIAL_OFFSET_MAX_MM = S_AXIS_FRONT_END_OFFSET_MAX_MM + S_AXIS_ZONE_DIAMETER_MM
# The shaft's journal runs the bush bore's whole length, hub face to stub end.
KNOB_JOURNAL_CONTACT_START_LOCAL_Z_MM = SHAFT.PINION_REAR_Z + RING.LENGTH
KNOB_JOURNAL_CONTACT_END_LOCAL_Z_MM = KNOB_JOURNAL_CONTACT_START_LOCAL_Z_MM + BUSH.LENGTH
KNOB_JOURNAL_CONTACT_SPAN_MIN_MM = (
    BUSH.LENGTH - BUSH.LENGTH_BAND - 2.0 * SHAFT.EDGE_BREAK_MAX
)
KNOB_JOURNAL_CONTACT_FRONT_MACHINE_Z_MM = ARM_REAR_MACHINE_Z_MM - BUSH.HUB_LENGTH
KNOB_JOURNAL_CONTACT_REAR_MACHINE_Z_MM = ARM_REAR_MACHINE_Z_MM + BUSH.STUB_LENGTH


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

    ``setup_error_xy_mm`` and every ``gear_plane_k_xy_mm`` are K's measured
    gear-plane position less its nominal, in the arm frame (x along the arm,
    y across), so the setup reading anchors the loaded envelope. Setup must
    lie in the drawn position circle AND in the drawn S-K centre-distance
    window along S-K.

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
    along = setup_error_xy_mm[0] * S_TO_K_UNIT[0] + setup_error_xy_mm[1] * S_TO_K_UNIT[1]
    high, low = REDUCER_CENTRE_DISTANCE_SET_BAND_MM
    # A reading exactly on a limit is accepted: allow the roundoff of
    # rebuilding the reading from its two coordinates, nothing more.
    roundoff = 1e-9
    if (along - measurement_uncertainty_mm < low - roundoff
            or along + measurement_uncertainty_mm > high + roundoff):
        raise ValueError("actual S-K centre distance is outside the drawn setting band")
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
    # The envelope spans the setup reading too: a joint that slips off its
    # accepted setting and stays there moves every loaded reading together.
    poses = (tuple(setup_error_xy_mm), *(row.gear_plane_k_xy_mm for row in readings))
    widths = tuple(
        max(pose[axis] for pose in poses) - min(pose[axis] for pose in poses)
        + 2.0 * measurement_uncertainty_mm for axis in range(2)
    )
    if any(width > LOCATOR_COORDINATE_TRAVEL_MAX_MM for width in widths):
        raise ValueError("measured loaded K motion exceeds the accepted full two-pose envelope")
    return widths
