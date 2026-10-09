"""Paper-feed law of the transgear train -- SolidWorks-free.

Net platen feed per CRANK revolution with the selected crank / knob removables
mounted: chain (tooth ratio, ``pd_transgear_removable_spec``) x
knob-shaft 12T/disc reduction x
feed-pinion reference pitch circumference on the 32DP rack. Every stage is a real mate in
``build_paper_drive_assembly``. This pure module also owns the canonical
paper/pen anchors, accepted-source loaded geometry enclosures and quantitative
ONE-zero transfer reporting; it never replaces total budget qualification.
"""

from __future__ import annotations

import math

import pd_rack_pinion_spec
import pd_transgear_feed_pinion_spec
import pd_transgear_knob_shaft_spec
import pd_transgear_removable_spec
import pd_support_bar_spec as bar
import pd_transgear_arm_geometry as arm
from pd_latch_hook_geometry import BAR_CENTRE_Y
import pd_platen_spec as platen
import pd_latch_hook_geometry as hook
import pd_transgear_pivot_spacer_spec as spacer
import vn_transgear_latch_pin_spec as latch_pin
import pd_latch_hook_spec as hook_spec
from _printed_tolerance import angular_band_deg
from _gear_quality import (
    rack_flank_constraint_deviation_mm,
    rack_form_admission_controls,
    rack_working_side_angle_deviation_deg,
    purchased_rack_working_side_form_model_premise,
    pinion_pitch_index_deviation_mm,
    rack_face_lead_deviation_mm,
    feed_loaded_travel_height_deviation_mm,
    rack_face_width_max_mm,
    rack_stock_height_max_mm,
    reducer_setup_clock_deviation_mm,
    recording_paper_left_inset_deviation_mm,
    recording_paper_width_deviation_mm,
    recording_pen_x_deviation_mm,
    reducer_axis_projected_zone_diameter_mm,
    reducer_position_diameter_mm,
    toothspace_runout_tir_mm,
    wire_measurement_uncertainty_mm,
    pitch_index_measurement_uncertainty_mm,
)

MM_PER_IN = 25.4

# A roller chain advances one tooth per link on both sprockets, so the law is
# the selected TOOTH ratio, not the #25 pitch-diameter ratio:
# PD = p / sin(180/N) is not linear in N.
CHAIN_RATIO = (
    pd_transgear_removable_spec.CRANK_TEETH / pd_transgear_removable_spec.KNOB_TEETH
)  # knob turns per crank turn
GEAR_RATIO = pd_transgear_knob_shaft_spec.TEETH / pd_rack_pinion_spec.TEETH  # 12:120
FEED_PITCH_DIA = pd_transgear_feed_pinion_spec.PITCH_DIA
# Profile shift changes mounting distance, not the reference rolling pitch.
NET_RACK_TRAVEL_PER_CRANK_REV = CHAIN_RATIO * GEAR_RATIO * math.pi * FEED_PITCH_DIA
# Swapping the selected removables end for end multiplies the feed by the
# inverse chain ratio squared.
COARSE_FEED_RATIO = (1.0 / CHAIN_RATIO) ** 2

# Keep the existing pivot/latch/stud pose. Mount the stock rack and backer at
# the shifted feed pitch line; relocate only the reducer's knob bearing.
PLATEN_BOTTOM_Y = 273.234
PIVOT_XY = (bar.PIVOT_TAP_X, BAR_CENTRE_Y + bar.HANGER_TAP_Y)
STUD_XY = (
    arm.STUD_MACHINE_X,
    PIVOT_XY[1] + arm.PIN_STATION * arm.ARM_U[1],
)
KNOB_SHAFT_XY = (
    PIVOT_XY[0]
    + arm.KNOB_BORE_STATION * arm.ARM_U[0]
    + arm.KNOB_BORE_OFFSET * arm.ARM_N[0],
    PIVOT_XY[1]
    + arm.KNOB_BORE_STATION * arm.ARM_U[1]
    + arm.KNOB_BORE_OFFSET * arm.ARM_N[1],
)
RACK_PITCH_Y = STUD_XY[1] + pd_transgear_feed_pinion_spec.RACK_AXIS_DISTANCE
RACK_TIP_Y = RACK_PITCH_Y - pd_transgear_feed_pinion_spec.MODULE_MM
RACK_CREST_DROP = PLATEN_BOTTOM_Y - RACK_TIP_Y


# Actual recording geometry, shared with the paper and pen native builders.
# These are source anchors, not a reduced paper stroke or nominal-only gate.
RECORDING_PAPER_WIDTH_MM = 233.2386
RECORDING_PAPER_HEIGHT_MM = 80.5
RECORDING_PAPER_LEFT_INSET_MM = (platen.PLATE_WIDTH - RECORDING_PAPER_WIDTH_MM) / 2.0
PAPER_FRONT_Z = (
    hook.BAR_BACK_FACE_Z - bar.BAR_DEPTH - platen.PLATE_THICKNESS - 0.5
)
PEN_ROD_X = 3.0
PEN_Z_MID = -157.0
PEN_BLOCK_YAW_DEG = 45.0
PEN_PAPER_CLEARANCE_MM = 0.25
PEN_NIB_X_MM = PEN_ROD_X - math.tan(math.radians(PEN_BLOCK_YAW_DEG)) * (
    PAPER_FRONT_Z - PEN_PAPER_CLEARANCE_MM - PEN_Z_MID
)


def _trig_range(angle_band: tuple[float, float], function) -> tuple[float, float]:
    low, high = angle_band
    values = [function(low), function(high)]
    for index in range(math.floor(2 * low / math.pi), math.ceil(2 * high / math.pi) + 1):
        angle = index * math.pi / 2.0
        if low <= angle <= high:
            values.append(function(angle))
    return min(values), max(values)


def _loaded_hanger_bounds() -> tuple[float, float, float]:
    """Whole seated-latch Jacobian bounds (Y, X, and any-two-state angle).

    The two physical constraints are the shoulder circle and the lower
    hook-hole bearing edge, not independent pivot/stud displacement circles.
    For the latch trace, y=P_y+(x_hook-P_x)*tan(theta)+g(theta).
    The oblique cylindrical pin's swept half-footprint has derivative bounded
    by r*sec(theta)*abs(tan(theta)) + t*sec(theta)**2/2. This is paid
    irrespective of which strip face carries; no favourable friction or
    fixed bearing direction is credited. Implicit differentiation gives
    theta_x=tan(theta)/D, theta_y=-1/D, D=run*sec(theta)**2+g'.
    Component gradient norms enclose the entire shoulder disk by the mean
    value theorem. They are displacement enclosures, NOT a force counterexample
    or a qualification of the physical contact carrier.
    """
    clearance_low, clearance_high = arm.pivot_running_clearance_mm()
    if not 0.0 < clearance_low <= clearance_high:
        raise ValueError("source pivot running clearance must be positive and ordered")
    radius = clearance_high / 2.0
    hx, hy = hook.PIN_AXIS_XY
    dx, dy = hx - PIVOT_XY[0], hy - PIVOT_XY[1]
    distance = math.hypot(dx, dy)
    # The hook's screw float, its formed band along the run and the ear's
    # bend change incidence across assemblies, though they do not float in
    # service once the pin hole is match-drilled.
    bend_lever = abs(arm.PIN_MACHINE_Z - hook.BAR_BACK_FACE_Z)
    mounting = (
        bar.HOLE_POSITION_BAND + hook_spec.POSITION_TOL + hook_spec.HEAD_FLOAT_MAX
        + hook.SHEET_T_PLUS
        + bend_lever * math.tan(math.radians(angular_band_deg()))
    )
    static = math.sqrt(2.0) * (
        mounting + hook_spec.FORMED_BAND + bar.HOLE_POSITION_BAND
    )
    uncertainty = radius + static
    if uncertainty >= distance or dx <= uncertainty:
        raise ValueError("accepted pivot circle cannot define a seated latch incidence")
    nominal = math.atan2(dy, dx)
    half_angle = math.asin(uncertainty / distance)
    angles = nominal - half_angle, nominal + half_angle
    sin_low, sin_high = _trig_range(angles, math.sin)
    cos_low, cos_high = _trig_range(angles, math.cos)
    if cos_low <= 0.0:
        raise ValueError("accepted latch incidence crosses a vertical pin")
    max_sine = max(abs(sin_low), abs(sin_high))
    max_tangent = max_sine / cos_low
    footprint_rate = (
        latch_pin.DIA_MAX / 2.0 * max_tangent / cos_low
        + hook.SHEET_T / (2.0 * cos_low**2)
    )
    # A tilted seated arm also moves the latch trace in Z. The circular
    # hook-hole lower edge has |dy/dz|=|z|/sqrt(R²-z²); pay its whole accepted
    # offset and the complete latch lever rather than a nominal centre slope.
    tilt = (
        math.atan(spacer.FRONT_FACE_PERPENDICULARITY / spacer.FACE_PERPENDICULARITY_ZONE_DIA)
        + math.atan(spacer.REAR_FACE_PERPENDICULARITY / spacer.FACE_PERPENDICULARITY_ZONE_DIA)
    )
    # The pin hole is match-drilled at the pin's marked axis: the drilled
    # position's .XX band, plus the as-built stack bands kept conservatively.
    z_offset = (
        abs(hook.PIN_HOLE_Z - arm.PIN_MACHINE_Z) + hook_spec.POSITION_TOL
        + bar.BAR_DEPTH_BAND + spacer.LENGTH_BAND + arm.THICKNESS_BAND
    )
    hole_radius = hook.PIN_HOLE_DIA / 2.0
    if z_offset >= hole_radius:
        raise ValueError("accepted latch trace has no finite lower-edge slope")
    edge_slope = z_offset / math.sqrt(hole_radius**2 - z_offset**2)
    footprint_rate += edge_slope * arm.TIP_STATION * math.tan(tilt)
    d_low = (dx - uncertainty) / cos_high**2 - footprint_rate
    d_high = (dx + uncertainty) / cos_low**2 + footprint_rate
    if d_low <= 0.0:
        raise ValueError("latch bearing derivative has no positive whole-domain bound")
    length = arm.PIN_STATION + reducer_position_diameter_mm() / 2.0
    gy_x = length * max_sine / d_low
    gy_y = max(abs(1.0 - length * cos_low / d_high),
               abs(1.0 - length * cos_high / d_low))
    gx_x = 1.0 + length * max_sine * max_tangent / d_low
    gx_y = length * max_sine / d_low
    y_change = clearance_high * math.hypot(gy_x, gy_y)
    x_change = clearance_high * math.hypot(gx_x, gx_y)
    angle_change = clearance_high * math.hypot(max_tangent, 1.0) / d_low
    return tuple(math.nextafter(value, math.inf) for value in (
        y_change, x_change, angle_change
    ))


def _rotating_stud_error_change_mm(angle_change: float) -> float:
    """Fixed S position, projected-axis and spacer tilt rotate with the arm."""
    projected_radius = reducer_axis_projected_zone_diameter_mm() / 2.0
    position_radius = reducer_position_diameter_mm() / 2.0
    tilt = (
        math.atan(spacer.FRONT_FACE_PERPENDICULARITY / spacer.FACE_PERPENDICULARITY_ZONE_DIA)
        + math.atan(spacer.REAR_FACE_PERPENDICULARITY / spacer.FACE_PERPENDICULARITY_ZONE_DIA)
    )
    # The complete stud ends at the source groove + front land + dome.
    # Paying that longer lever also encloses the actual feed tooth mid-plane.
    import pd_transgear_pin_spec as pin

    lever = pin.LENGTH + arm.THICKNESS + arm.THICKNESS_BAND
    fixed_radius = position_radius + projected_radius + lever * math.tan(tilt)
    return 2.0 * fixed_radius * math.sin(min(math.pi, angle_change) / 2.0)


def feed_profilecentre_x_offset_band_mm() -> tuple[float, float]:
    """Absolute profile-centre X minus ACTUAL running-stud X at feed mid-plane.

    The feed gear lies inside the sleeve's running bore, so the full accepted
    journal radial clearance bounds its local centre. Tooth-space TIR refers
    to that running bore and contributes half TIR. In a machine-Z plane the
    section of that transverse offset disk stretches by sec(theta). The
    actual full feed-axis tilt includes spacer, projected-axis and journal
    cock. Hanger/pivot motion changes the running axis itself and must NOT
    be added again to this offset.
    """
    radius = (
        pd_transgear_feed_pinion_spec.BORE_DIAMETRAL_CLEARANCE[1]
        + toothspace_runout_tir_mm()
    ) / (2.0 * math.cos(reducer_axis_tilt_maxima_rad()[1]))
    radius = math.nextafter(radius, math.inf)
    return -radius, radius


def feed_running_axis_x_displacement_band_mm() -> tuple[float, float]:
    """Installed loaded stud axis to any seated loaded phase, at the feed plane."""
    _y_change, x_change, angle_change = _loaded_hanger_bounds()
    excursion = math.nextafter(
        x_change + _rotating_stud_error_change_mm(angle_change), math.inf
    )
    return -excursion, excursion


def recording_paper_sweep_bands_mm() -> dict[str, tuple[float, float]]:
    """Accepted FULL located recording sweep, including changing loaded stud X.

    Width, installed inset and nib X are independently inspected/rejected.
    The nominal nib is not the running stud datum: its error also includes
    accepted static support/S position and the whole loaded axis excursion.
    """
    width = recording_paper_width_deviation_mm()
    inset = recording_paper_left_inset_deviation_mm()
    axis_low, axis_high = feed_running_axis_x_displacement_band_mm()
    static_axis = bar.HOLE_POSITION_BAND + reducer_position_diameter_mm() / 2.0
    pen = recording_pen_x_deviation_mm() + static_axis
    return {
        "paper_left_inset_band_mm": (
            RECORDING_PAPER_LEFT_INSET_MM - inset,
            RECORDING_PAPER_LEFT_INSET_MM + inset,
        ),
        "paper_width_band_mm": (
            RECORDING_PAPER_WIDTH_MM - width, RECORDING_PAPER_WIDTH_MM + width,
        ),
        "pen_x_from_running_axis_band_mm": (
            PEN_NIB_X_MM - pen - axis_high,
            PEN_NIB_X_MM + pen - axis_low,
        ),
    }


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


def feed_service_cocking_lateral_deviation_mm() -> float:
    """Pay WHOLE journal cocking across the actual accepted rack face.

    Two bore-end constraint disks limit relative axis slope to clearance/L.
    General edge breaks remove real bearing length; the oil cross-hole does
    not remove the end contact rings. No one-time assembled lead inspection
    is substituted for this service motion. Normal Y skew is converted to
    the equivalent lateral constraint debit as well as direct X skew. Across
    the actual machine-Z face, the derivative of transverse axis slope is
    bounded by sec(theta)**2 times the relative angular excursion. The whole
    source feed-axis tilt is used, not an assumed world-Z journal.
    Rigid quasi-static kinematics; elastic compliance excluded by scope.
    """
    import _config

    edge = float(_config.title_block("edge_break")["chamfer_max_mm"])
    if not math.isfinite(edge) or edge < 0.0:
        raise ValueError("bore end edge loss must be finite and nonnegative")
    length = (
        pd_transgear_feed_pinion_spec.OVERALL_LENGTH
        - pd_transgear_feed_pinion_spec.STATION_TOL - 2.0 * edge
    )
    if length <= 0.0:
        raise ValueError("feed bore has no positive end-to-end contact span")
    slope = pd_transgear_feed_pinion_spec.BORE_DIAMETRAL_CLEARANCE[1] / length
    # This is the nominal X-intercept sandwich, not an assumption that the
    # actual rack normal equals PA. Unknown actual normals are handled by
    # the full-carrier oracle and its all-native-working-point moment bound.
    normal_projection = 1.0 / math.cos(
        math.radians(pd_transgear_feed_pinion_spec.PRESSURE_ANGLE_DEG)
    )
    section_slope_factor = 1.0 / math.cos(reducer_axis_tilt_maxima_rad()[1])**2
    return math.nextafter(
        rack_face_width_max_mm() * slope * section_slope_factor * normal_projection,
        math.inf,
    )


def feed_section_constraint_excursion_mm() -> float:
    """Any-two-phase X-equivalent growth of the true tilted feed section."""
    radius = (
        max(profile.blank_radius_mm for profile
            in pd_transgear_feed_pinion_spec.manufactured_profiles())
        + toothspace_runout_tir_mm() / 2.0
    )
    growth = 1.0 / math.cos(reducer_axis_tilt_maxima_rad()[1]) - 1.0
    return math.nextafter(
        2.0 * radius * growth
        / math.cos(math.radians(pd_transgear_feed_pinion_spec.PRESSURE_ANGLE_DEG)),
        math.inf,
    )


def feed_lateral_deviation_terms_mm() -> dict[str, float]:
    """Whole incoming form PLUS independent mounted lead and service cock."""
    return {
        "rack_both_flank_full_form_constraints": rack_flank_constraint_deviation_mm(),
        "pinion_local_and_cumulative_index": pinion_pitch_index_deviation_mm(),
        "assembled_static_full_face_lead": rack_face_lead_deviation_mm(),
        "feed_service_cocking_across_face": feed_service_cocking_lateral_deviation_mm(),
        "feed_tilted_section_constraint_excursion": feed_section_constraint_excursion_mm(),
    }


def feed_lateral_deviation_mm() -> float:
    """MAX relative offset of ANY TWO active constraints; never a vendor zero.

    Each receiving control is a max-relative range, not +/- coordinates.
    The independent full-journal service-cock term is added. The finite rack
    window reserves this lateral offset beyond one pitch at each cut end.
    """
    return math.nextafter(math.fsum(feed_lateral_deviation_terms_mm().values()), math.inf)


def feed_loaded_geometry_inspection_text() -> str:
    """One traveller requirement for the source whole-travel geometry grade."""
    return (
        "AT THE SAME POSITIVE-LOADED TOOTH-CENTRED SETUP GEOMETRY. "
        "ALIGN FEED TOOTH AND RACK-SPACE CENTRES; HOLD THE KNOB AND TAKE THE "
        "FORWARD PLATEN ENDPOINT UNDER POSITIVE PAPER RESISTANCE. "
        "INSPECT THE ENTIRE LOCATED RECORDING STROKE WITHIN THE PRINTED ENGAGED WINDOW. "
        "CAPTURE THE LOADED RUNNING-STUD AXIS DATUM ONCE; MEASURE THE "
        "RACK/SUPPORT ASSET RANGE AGAINST THAT FIXED DATUM, NOT A MOVING "
        "PIVOT OR RUNNING-JOURNAL DATUM. "
        "INCLUDE RACK/SOLDER, GUIDE/SUPPORT STRAIGHTNESS AND PLATEN ROCKING: "
        f"RELATIVE RACK PITCH-HEIGHT RANGE {feed_loaded_travel_height_deviation_mm():.3f} MM MAX; "
        "REJECT AN EXCESS. KEEP ARM FACES, HOOK LOWER BEARING AND PLATEN Y SUPPORT "
        "SEATED. RETAIN ONE LOADED SETUP AND ONE PAPER ZERO; DO NOT RE-ZERO AT "
        "EACH STATION OR LOAD."
    )


def reducer_setup_clock_inspection_text() -> str:
    """One actual reducer clock setup, distinct from relative tooth indexing."""
    return (
        "WITH THE DISC CLUSTER LOCKED TO ITS MATCHED RUNNING-BORE DATUM, "
        "KEEP THE ACTUAL S-K GEAR-PLANE AXES IN THE MATCHED LOADED SETUP. "
        "ALIGN THE INTEGRAL 12T GAP BISECTOR TOWARD S AND A 120T TOOTH "
        "BISECTOR TOWARD K, USING THEIR ACTUAL FORMED FLANKS. "
        f"AT EACH GEAR'S OWN REFERENCE RADIUS, ABSOLUTE SETUP-CLOCK ERROR "
        f"INCLUDING CALIBRATION UNCERTAINTY {reducer_setup_clock_deviation_mm():.3f} MM MAX; "
        "REJECT AN EXCESS. THIS IS ONE MATCHED CLOCK DATUM, NOT TOOTH THICKNESS, "
        "TIR OR THE RELATIVE ALL-SPACE INDEX RANGE. RETAIN IT THROUGH ALL "
        "RUNNING PHASES AND POSITIVE LOADS; DO NOT RE-CLOCK OR RE-ZERO PER LOAD."
    )


def feed_rack_cut_end_section_maxima_mm() -> tuple[float, float]:
    """Whole actual cut-Y/cut-Z envelope, not the nominal overall-height REF.

    Incoming stock HEIGHT and face WIDTH have separate positive receiving
    maxima.  The printed SeamHeight, BackerDepth and RackInset bounds locate
    the soldered stock; rejected incoming sections never enter this domain.
    """
    import pd_platen_rack_spec as rack
    from _printed_tolerance import printed_deviations

    def dimension_band(name: str) -> tuple[float, float]:
        nominal = rack.DRAWING_NOMINALS_MM[name]
        lower, upper = printed_deviations(
            nominal, rack.DRAWING_PRECISION_BY_NAME[name]
        )
        return nominal + lower, nominal + upper

    seam = dimension_band("SeamHeight")
    backer = dimension_band("BackerDepth")
    inset = dimension_band("RackInset")
    height = seam[1] + rack_stock_height_max_mm()
    depth = max(backer[1], inset[1] + rack_face_width_max_mm()) - min(0.0, inset[0])
    if not all(math.isfinite(value) and value > 0.0 for value in (height, depth)):
        raise ValueError("actual rack cut section has no finite positive envelope")
    return math.nextafter(height, math.inf), math.nextafter(depth, math.inf)


def reducer_working_z_band_mm() -> tuple[float, float]:
    """All actual axial working planes of the integral reducer pinion.

    Paying its full tooth face conservatively encloses every actual disc
    overlap plane, including fit-up m, cluster float and knob end float.
    The directly controlled rigid-seat normal change at K is extrapolated
    from the three critical witnesses; K is outside their triangle.
    """
    import paper_drive_arm_registration as registration
    from _printed_tolerance import printed_band_mm

    front = registration.KNOB_F_MACHINE_Z_MM
    band = registration.KNOB_F_AXIAL_BAND_MM
    seat_height = math.nextafter(
        registration.gear_plane_k_loaded_normal_change_bound_mm(), math.inf
    )
    return (
        math.nextafter(front - band - seat_height, -math.inf),
        math.nextafter(
            front + band + seat_height + pd_transgear_knob_shaft_spec.FACE_WIDTH
            + printed_band_mm(pd_transgear_knob_shaft_spec.FACE_WIDTH_PLACES),
            math.inf,
        ),
    )


def reducer_axis_tilt_maxima_rad() -> tuple[float, float]:
    """Driver/disc actual axis tilts through the full source working section.

    The journal end rings can seat oppositely; neither is constrained to the
    centre of its clearance circle. The arm's opposite face and loaded seat
    add real three-dimensional rotation, despite K travel being measured at
    one gear plane. Spacer faces set the common mounting-plane inclination.
    """
    import paper_drive_arm_registration as registration
    import pd_transgear_arm_plate_geometry as plate
    import _config

    low_z, high_z = reducer_working_z_band_mm()
    if not (
        registration.ARM_FRONT_MACHINE_Z_MM - registration.S_PROJECTED_HEIGHT_MM
        <= low_z <= high_z <= registration.ARM_FRONT_MACHINE_Z_MM
        and registration.PLATE_MOUNT_MACHINE_Z_MM - registration.K_PROJECTED_HEIGHT_MM
        <= low_z <= high_z <= registration.PLATE_MOUNT_MACHINE_Z_MM
    ):
        raise ValueError("actual reducer working faces leave the printed S/K projected-axis zones")
    common = (
        math.atan(spacer.FRONT_FACE_PERPENDICULARITY / spacer.FACE_PERPENDICULARITY_ZONE_DIA)
        + math.atan(spacer.REAR_FACE_PERPENDICULARITY / spacer.FACE_PERPENDICULARITY_ZONE_DIA)
    )
    edge = float(_config.title_block("edge_break")["chamfer_max_mm"])
    feed_span = (
        pd_transgear_feed_pinion_spec.OVERALL_LENGTH
        - pd_transgear_feed_pinion_spec.STATION_TOL - 2.0 * edge
    )
    knob_clearance = (
        max(plate.BORE_DIA_LIMITS)
        - min(pd_transgear_knob_shaft_spec.JOURNAL_DIA_BAND)
    )
    if feed_span <= 0.0 or knob_clearance <= 0.0:
        raise ValueError("actual reducer journals have no positive contact span/clearance")
    driver = (
        common
        + math.atan(registration.ARM_OPPOSITE_FACE_PARALLELISM_MM / registration.ARM_SEAT_SPAN_MIN_MM)
        + math.atan(2.0 * registration.ARM_PLATE_LOADED_NORMAL_CHANGE_MAX_MM / registration.ARM_SEAT_SPAN_MIN_MM)
        + math.atan(registration.AXIS_PROJECTED_ZONE_DIAMETER_MM / registration.K_PROJECTED_HEIGHT_MM)
        + math.atan(knob_clearance / registration.KNOB_JOURNAL_CONTACT_SPAN_MIN_MM)
    )
    disc = (
        common
        + math.atan(registration.AXIS_PROJECTED_ZONE_DIAMETER_MM / registration.S_PROJECTED_HEIGHT_MM)
        + math.atan(pd_transgear_feed_pinion_spec.BORE_DIAMETRAL_CLEARANCE[1] / feed_span)
    )
    if not all(math.isfinite(angle) and 0.0 < angle < math.pi / 6 for angle in (driver, disc)):
        raise ValueError("actual three-dimensional axis tilt cannot be projected uniquely")
    return math.nextafter(driver, math.inf), math.nextafter(disc, math.inf)
