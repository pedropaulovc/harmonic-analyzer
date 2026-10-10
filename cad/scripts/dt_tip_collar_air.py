"""Manufactured all-clock, continuous-P1 collar/bank material enclosures.

The drum's tooth slab and eccentric cam are DIFFERENT finite material tiers.
The tip cylinder must not fill the cam's shadow through the overall thickness.
Filled tiers deliberately retain tooth spaces, the bore, breaks and flats: no
native relief is credited as a manufacturing tolerance reserve. Installed
shaft/bank inspections are conditional inputs, never measured-stock claims.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import cone_line
import cylinder_bank_layout as bank
import dt_cone_gear_shaft_spec as shaft
import dt_cylinder_gear_spec as drum
import dt_cone_gear_stack as stack
import dt_cone_pivot_post_spec as post
import vn_cone_tip_collar_spec as collar
from _printed_tolerance import printed_band_mm
from cone_stack_end_play import COLLAR_FEELER_BAND, SHAFT_END_PLAY, STACK_FLOAT


@dataclass(frozen=True)
class CollarTier:
    name: str
    south_mm: float
    north_mm: float
    radius_mm: float
    south_lower_mm: float
    north_upper_mm: float
    radius_upper_mm: float


@dataclass(frozen=True)
class DrumTier:
    name: str
    south_mm: float
    north_mm: float
    radius_mm: float
    south_lower_mm: float
    north_upper_mm: float
    radius_upper_mm: float


SOUTH_STATION_MM = shaft.TIP_COLLAR_START_STATION
PARTITION_STATION_MM = collar.NOSE_LENGTH - collar.SHOULDER_ROOT_RADIUS
_MIN_STOCK_Y = collar.TAP_STATION - collar.SET_SCREW_MAJOR_DIA / 2.0
_STOCK_R = math.hypot(collar.SET_SCREW_END_RADIUS, collar.SET_SCREW_MAJOR_DIA / 2.0)
_MAX_STOCK_Y_LOSS = (
    collar.TAP_POSITION_RADIUS_MM
    + (collar.SET_SCREW_LENGTH + collar.SET_SCREW_LENGTH_BAND_MM)
    * math.sin(collar.TIP_SCREW_MAX_AXIS_ANGLE_RAD)
    + collar.TIP_SCREW_DOG_TOTAL_RUNOUT_MM / 2.0
)
_MAX_STOCK_R = math.hypot(
    collar._FLAT_MAX + collar._FLOAT_MAX + collar.SET_SCREW_LENGTH
    + collar.SET_SCREW_LENGTH_BAND_MM,
    collar.SET_SCREW_MAJOR_DIA / 2.0 + _MAX_STOCK_Y_LOSS,
)
TIERS = (
    CollarTier("nose", 0.0, PARTITION_STATION_MM, collar.NOSE_DIA / 2.0,
               0.0, collar.ROUTINE_BAND_MM + collar.SHOULDER_ROOT_RADIUS,
               collar.ROUTINE_BAND_MM / 2.0),
    CollarTier("body", PARTITION_STATION_MM, collar.WIDTH, collar.OUTER_DIA / 2.0,
               -collar.ROUTINE_BAND_MM, collar.WIDTH_BAND_MM, collar.ROUTINE_BAND_MM / 2.0),
    CollarTier("screw", _MIN_STOCK_Y,
               collar.TAP_STATION + collar.SET_SCREW_MAJOR_DIA / 2.0,
               _STOCK_R, -_MAX_STOCK_Y_LOSS, _MAX_STOCK_Y_LOSS,
               max(0.0, _MAX_STOCK_R - _STOCK_R)),
)
DRUM_TIERS = (
    DrumTier("tooth_face", -drum.FACE_WIDTH, 0.0, drum.OUTSIDE_DIA / 2.0,
             -drum.FACE_WIDTH_TOLERANCE_MM, 0.0,
             max(0.0, drum.outside_dia_limits_mm()[1] - drum.OUTSIDE_DIA) / 2.0),
    # Full cam clock is enclosed by its actual eccentric orbit, not tip OD.
    DrumTier("cam", -drum.OVERALL_THICKNESS, -drum.FACE_WIDTH,
             drum.CAM_DIA / 2.0 + drum.ECCENTRICITY,
             drum.OVERALL_THICKNESS_BAND[1], drum.FACE_WIDTH_TOLERANCE_MM,
             max(0.0, drum.CAM_DIA_BAND[0]) / 2.0 + drum.ECCENTRICITY_TOLERANCE_MM),
)


def station_band_mm() -> dict[str, float]:
    """Axial lengths only; inspected running support pose is NOT paid twice."""
    return {
        "post boss half length": printed_band_mm(post.DRAWING_PRECISION_BY_NAME["ConeBossLen"]) / 2.0,
        "shaft integral thrust collar width": shaft.printed_band("CollarWidth"),
        "accepted gear stack terminal north face": -stack.face_band(stack.COUNT - 1, "north")[1],
        "T006 collar feeler set error": COLLAR_FEELER_BAND,
    }


# Conditional setup requirements, NOT measurements or a supplier stock grade.
# One numerical authority feeds collar air, native saved-body guards and the
# assembly installation handoff; support reconstruction itself belongs to pose.
POST_CENTRE_INSPECTION_XYZ_MM = (0.025, 0.23, 0.025)
CUP_SEATED_NORTH_CENTRE_XYZ_MM = (0.025, 0.23, 0.025)
NORTH_RADIAL_MOTION_MAX_MM = 0.480
BANK_WORKING_FACE_TIR_MM = 0.025
BANK_WORKING_TRACE_MIN_MM = 23.0
TERMINAL_PROBE_DIAMETER_MAX_MM = 0.25
TERMINAL_CENTRE_EXPANDED_UNCERTAINTY_MAX_MM = 0.005
TERMINAL_INDICATOR_RESOLUTION_MAX_MM = 0.001
DRUM_BORE_END_BREAK_MAX_MM = 0.25
TERMINAL_INSPECTION_STATION_MIN_MM = (
    shaft.T006_NORTH_FACE_STATION
    - sum(value for name, value in station_band_mm().items() if name != "T006 collar feeler set error")
    + STACK_FLOAT[0]/2.0
)
TERMINAL_INSPECTION_STATION_MAX_MM = (
    shaft.T006_NORTH_FACE_STATION
    + sum(value for name, value in station_band_mm().items() if name != "T006 collar feeler set error")
    + SHAFT_END_PLAY[1] + STACK_FLOAT[1]/2.0
)


def installation_acceptances(*, terminal_station_mm=None):
    """Actual support centres plus a CLOSED full-stroke shaft-motion domain.

    Post and cup-SEATED north centre boxes are datum observations, NOT tight
    all-state shaft boxes or a subtracted/tared mean. In the SAME FIXED north
    plane normal to the nominal shaft, rho is radial-plane distance to the
    required XYZ box's intersection with that plane. The COMPLETE stroke
    satisfies rho²/Rmax²+q/e<=1, including all loads, clocks and metrology.
    No supplier cup-angle/form grade is inferred. Follow the original moving
    feeler gap with <=.25 stylus and record stations for this fixed-plane fit.
    """
    from dt_cone_support_pose import BankThrustAcceptance, InstalledSupportMotionAcceptance

    station = TERMINAL_INSPECTION_STATION_MIN_MM if terminal_station_mm is None else float(terminal_station_mm)
    if not math.isfinite(station) or not TERMINAL_INSPECTION_STATION_MIN_MM <= station <= TERMINAL_INSPECTION_STATION_MAX_MM:
        raise ValueError("terminal inspection station must be the actual retained feeler-gap BACK arc")
    return (
        InstalledSupportMotionAcceptance(
            POST_CENTRE_INSPECTION_XYZ_MM, CUP_SEATED_NORTH_CENTRE_XYZ_MM,
            NORTH_RADIAL_MOTION_MAX_MM, station, SHAFT_END_PLAY[1],
        ),
        BankThrustAcceptance(BANK_WORKING_FACE_TIR_MM, BANK_WORKING_TRACE_MIN_MM),
    )


def installation_requirements() -> tuple[str, ...]:
    """Complete operator handoff; assembly drawing owns its note placement."""
    from dt_cone_tip_block_spec import ADJUSTER_EMBED_WINDOW, ADJUSTER_ENGAGEMENT_MIN_MM

    return (
        "CRITICAL RUNNING-BORE/SHAFT-SEAT SETUP ONLY; NO COMMODITY RECEIVING OR FULL-P1 TRACKING. ACTUAL BANK ARBOR X/Y AND SEATED THRUST/WASHER Z ARE THE SETUP DATUMS.",
        "INDICATE REMOVABLE MANDREL IN ACTUAL POST BORE; POST MIDPOINT X/Z WITHIN +/-0.025 AND Y +/-0.23 INCLUDING METROLOGY; LOCK POST, THEN FIT FINAL SHAFT. RETAIN REAL POST RUNNING RADIAL FIT.",
        "STACK SOUTH, ORIGINAL GAP >=0.35: FOLLOW GAP WITH <=0.25 STYLUS; FIT >=3 ROUND BACK POINTS AT EACH OF >=2 RECORDED STATIONS, NOT FLAT/GEAR OD. BOUND FIXED-NORTH-PLANE EXTRAPOLATION USING INDICATED POST CENTRE PLUS FULL RUNNING FIT; INCLUDE FIT/FORM/METROLOGY. CUP-SEATED FAMILY X/Z +/-0.025, Y +/-0.23.",
        f"FULL TURN/OPPOSED RADIAL LOADS/CONTINUOUS ORIGINAL STROKE: rho^2/{NORTH_RADIAL_MOTION_MAX_MM:.3f}^2+q/e<=1, q NORTH FROM SOUTH THRUST STOP, ACTUAL e=0.05..0.25. rho=DISTANCE IN SAME FIXED RADIAL PLANE TO REQUIRED DATUM-REFERENCED XYZ BOX, NOT 3D DISTANCE/SUBTRACTED MEAN. INCLUDE METROLOGY; NEVER REMOVE FLOAT.",
        f"FITTED-CENTRE TOTAL EXPANDED UNCERTAINTY <={TERMINAL_CENTRE_EXPANDED_UNCERTAINTY_MAX_MM:.3f}; INDICATOR RESOLUTION <={TERMINAL_INDICATOR_RESOLUTION_MAX_MM:.3f} IS NOT ACCURACY. PROPAGATE CENTRE/STATION/PLANE AND CORRELATED q/e UNCERTAINTY INTO THE WHOLE-STATE UPPER; OBSERVED UPPER PLUS ITS EXPANDED UNCERTAINTY MUST NOT EXCEED {NORTH_RADIAL_MOTION_MAX_MM:.3f}. CUP-SEATED UNCERTAINTY FAMILY MUST REMAIN INSIDE THE FIXED BOX; NO MEAN/TARE.",
        f"GAUGE ACTUAL CUP RIM FROM TIP-BLOCK NORTH FACE: EMBED {ADJUSTER_EMBED_WINDOW[0]:.3f}..{ADJUSTER_EMBED_WINDOW[1]:.3f}; RETAIN ACTUAL FULL THREAD {ADJUSTER_ENGAGEMENT_MIN_MM:.2f} MIN (ORIGINAL 1.0D EXCEPTION) AT FINAL END-PLAY SETTING. NO NOMINAL CUP-ANGLE/TOLERANCE PASS CLAIM.",
        "BOTH WASHER WORKING FACES TO ACTUAL SEATED THRUST DATUM; ALL20 BOTH GEAR WORKING FACES TO ACTUAL BORE ON CLOSE INDICATED MANDREL: FULL-TURN/FULL-FACE FORM TIR <=0.025 OVER ACTUAL RETAINED-MATERIAL TRACE >=23.0. THIS MANUFACTURED FACE GRADE DOES NOT REMOVE RUNNING-BORE COCK.",
        "VERIFY BOTH GEAR BORE MOUTHS <=0.25 AXIAL BREAK; FINITE CYLINDRICAL CONTACT SPAN >=ACTUAL OVERALL THICKNESS-0.50. RETAIN MATCHED 0.030..0.070 DIAMETRAL RUNNING CLEARANCE; DO NOT PRELOAD THE BANK.",
        "SET ORIGINAL 0.45+/-0.10 FEELER OFF T006; LOAD BOTH FINITE BORE ENDS ON RETAINED ROUND BACK ARC AND SNUG COMPLETE GROUND DOG ON UNBROKEN D-FLAT. REMOVE LEAF; NEVER RUN/SWING LOOSE.",
        "RETAIN ORIGINAL SHAFT 0.05..0.25 END PLAY, STACK/BANK FLOAT AND ALL PART FIT BANDS; REJECT/REWORK AN UNMET CONDITIONAL INSPECTION, NEVER CLAIM SUPPLIED STOCK PASSED.",
    )


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b, strict=True))


def _normal(vector):
    length = math.sqrt(_dot(vector, vector))
    return tuple(value / length for value in vector) if length > 1e-12 else None


def cylinder_support(origin, axis, south, north, radius, normal, *, maximum):
    """Exact finite filled-cylinder support, not a distance sampling surrogate."""
    along = _dot(axis, normal)
    transverse = math.sqrt(max(0.0, _dot(normal, normal) - along**2))
    ends = (south * along, north * along)
    return _dot(origin, normal) + (
        max(ends) + radius * transverse if maximum else min(ends) - radius * transverse
    )


def _maximum_radial_projection(axis, normal, theta):
    """Exact radial support over a closed 3D axis cap, including its equator."""
    angle = math.acos(max(-1.0, min(1.0, _dot(axis, normal))))
    lo = math.cos(min(math.pi, angle+theta))
    hi = math.cos(max(0.0, angle-theta))
    return 1.0 if lo <= 0.0 <= hi else math.sqrt(max(0.0, 1.0-min(lo*lo, hi*hi)))


def nominal_full_clock_air_mm(tier: CollarTier) -> float:
    return projection_nominal_mm(tier, (0.0, 0.0, 1.0), DRUM_TIERS[0])


def projection_nominal_mm(tier, normal, fixed=None, angle_deg=0.0):
    from dt_cone_support_pose import collar_pose_frame

    fixed = DRUM_TIERS[0] if fixed is None else fixed
    origin, axis = collar_pose_frame(angle_deg)
    moving = cylinder_support(
        origin, axis, SOUTH_STATION_MM + tier.south_mm,
        SOUTH_STATION_MM + tier.north_mm, tier.radius_mm, normal, maximum=False,
    )
    stationary = cylinder_support(
        (cone_line.X_DRUM, cone_line.Y_DRIVE, bank.G19_BACK_FACE_Z),
        (0.0, 0.0, 1.0), fixed.south_mm, fixed.north_mm,
        fixed.radius_mm, normal, maximum=True,
    )
    return moving - stationary


def _tilted_fixed_support(fixed, normal, theta):
    """Exact 3D support over the COMPLETE finite cylinder axis cap.

    Rotation is about the running-bore midpoint, not its north face.
    For axis dot normal c in its closed spherical-cap interval, maximize
    max(s*c,n*c)+R*sqrt(1-c*c). Endpoints and the two analytic stationary
    points are complete; no angular samples or (R+lever)*theta shortcut.
    """
    radius = fixed.radius_mm + fixed.radius_upper_mm
    pivot = -drum.OVERALL_THICKNESS/2.0
    ends = (fixed.south_mm+fixed.south_lower_mm-pivot,
            fixed.north_mm+fixed.north_upper_mm-pivot)
    nz = normal[2]
    angle = math.acos(max(-1.0, min(1.0, nz)))
    lo = math.cos(min(math.pi, angle+theta))
    hi = math.cos(max(0.0, angle-theta))
    candidates = [lo, hi]
    for end in ends:
        stationary = end/math.hypot(radius, end)
        if lo <= stationary <= hi:
            candidates.append(stationary)
    support = max(max(end*c for end in ends)+radius*math.sqrt(max(0.0, 1.0-c*c))
                  for c in candidates)
    return pivot*nz + support


def projection_closure_terms_mm(
    tier, normal, fixed=None, angle_deg=0.0, half_interval_rad=0.0,
    *, installed, bank_thrust,
):
    from dt_cone_support_pose import collar_pose_frame, collar_projection_closure_terms_mm, cone_axis_angle_bound_rad

    fixed = DRUM_TIERS[0] if fixed is None else fixed
    _origin, axis = collar_pose_frame(angle_deg)
    along = _dot(axis, normal)
    radial = math.sqrt(max(0.0, 1.0 - along**2))
    axial_projection = min(1.0, abs(along) + half_interval_rad)
    terms = {name: value * axial_projection for name, value in station_band_mm().items()}
    # The actual-bank inspection frame already contains strap location and
    # washer thickness. In the unconditional frame they remain independent.
    if installed is None:
        terms.update({f"j19 {name}": float(value) * abs(normal[2])
                      for name, value in bank.DATUM_CHAIN_STACK.items()})
    terms["tier axial manufacturing limit"] = (
        max(0.0, along) * -tier.south_lower_mm
        + max(0.0, -along) * tier.north_upper_mm
        + max(-tier.south_lower_mm, tier.north_upper_mm) * half_interval_rad
    )
    terms["tier radial manufacturing limit"] = tier.radius_upper_mm * min(1.0, radial + half_interval_rad)
    axis_angle = cone_axis_angle_bound_rad(angle_deg, installed=installed)
    cock = collar.TIP_COLLAR_INSTALLED_COCK_ANGLE_RAD
    bore_upper_r = collar.BORE_FINISHED_DIA_LIMITS_MM[1]/2.0
    ellipse_extra = bore_upper_r*(1.0/math.cos(cock)-1.0)
    radial_cap = _maximum_radial_projection(axis, normal, axis_angle+half_interval_rad)
    terms["loaded collar ROUND back-arc offset"] = (
        collar.TIP_COLLAR_MAX_RADIAL_FLOAT_MM+ellipse_extra
    ) * radial_cap
    # Both actual bore END offsets are bounded. Interior centreline offsets
    # interpolate inside their convex radial disk; only free end overhangs
    # extrapolate. Paying full WIDTH*theta again discards this contact law.
    extrapolation = max(
        0.0, collar.EDGE_BREAK-(tier.south_mm+tier.south_lower_mm),
        tier.north_mm+tier.north_upper_mm
        - (collar.WIDTH-collar.WIDTH_BAND_MM-collar.EDGE_BREAK)*math.cos(cock),
    )
    axial_lever = max(abs(tier.south_mm+tier.south_lower_mm),
                      abs(tier.north_mm+tier.north_upper_mm))
    terms["loaded two-end collar cock"] = (
        extrapolation*math.tan(cock)*radial_cap
        + axial_lever*(1.0-math.cos(cock))
        + (tier.radius_mm+tier.radius_upper_mm)*max(
            0.0, _maximum_radial_projection(axis, normal, cock+half_interval_rad)-radial,
        )
    )
    manufactured_fixed = _tilted_fixed_support(fixed, normal, 0.0)
    nominal_fixed = cylinder_support(
        (0.0, 0.0, 0.0), (0.0, 0.0, 1.0),
        fixed.south_mm, fixed.north_mm, fixed.radius_mm, normal, maximum=True,
    )
    terms["drum tier radial/axial manufacturing limits"] = max(0.0, manufactured_fixed-nominal_fixed)
    terms["drum running bore radial fit"] = drum.BORE_DIAMETRAL_CLEARANCE_MM[1] / 2.0 * math.hypot(
        normal[0], normal[1],
    )
    contact_span = drum.OVERALL_THICKNESS + drum.OVERALL_THICKNESS_BAND[1] - 2.0*DRUM_BORE_END_BREAK_MAX_MM
    if contact_span <= 0.0:
        raise ValueError("drum has no finite retained running-bore contact span")
    running_cock = math.atan(drum.BORE_DIAMETRAL_CLEARANCE_MM[1]/contact_span)
    face_angle = 0.0 if bank_thrust is None else bank_thrust.direction_angle_rad
    face_form = 0.0 if bank_thrust is None else bank_thrust.face_tir_mm
    theta = running_cock + face_angle
    terms["drum FULL retained running/face tilted finite-cylinder enclosure"] = max(
        0.0, _tilted_fixed_support(fixed, normal, theta)-manufactured_fixed,
    )
    terms["drum printed bore-midpoint transport"] = max(abs(v) for v in drum.OVERALL_THICKNESS_BAND)/2.0 * 2.0*math.sin(theta/2.0)
    terms["actual manufactured thrust/washer full-face form"] = face_form * min(
        1.0, abs(normal[2])+math.sin(theta),
    )
    # No end-play term: MHA-VN-052 preloads the bank north onto its thrust
    # datum (#948 ruling R, cylinder_bank_layout), so G19 has no free axial
    # travel to shuttle south.
    # The observer pays the ACTUAL correlated stroke/motion support. A is an
    # upper signed material-closing coefficient across the whole axis/P1 cap,
    # not merely the nominal -axis·normal. Never independently max-add q again.
    axial_closing = min(1.0, -along+2.0*math.sin(axis_angle/2.0)+half_interval_rad)
    arguments = (
        SOUTH_STATION_MM + tier.south_mm + tier.south_lower_mm,
        SOUTH_STATION_MM + tier.north_mm + tier.north_upper_mm,
        tier.radius_mm + tier.radius_upper_mm,
    )
    pose = collar_projection_closure_terms_mm(
        *arguments, normal, angle_deg=angle_deg, installed=installed,
        axial_closing_coefficient=axial_closing,
    )
    if set(terms).intersection(pose):
        raise ValueError("collar pose/length ledger contains duplicate terms")
    terms.update(pose)
    if half_interval_rad:
        # Whole enclosures may switch authority with projection direction. Use
        # a direct common Euclidean OUTER bound, not per-axis term-name matching.
        bounds = [sum(collar_projection_closure_terms_mm(
            *arguments, unit, angle_deg=angle_deg, installed=installed,
            axial_closing_coefficient=1.0,
        ).values()) for unit in ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))]
        terms["pose interval rotation remainder"] = math.sqrt(sum(value**2 for value in bounds)) * half_interval_rad
    if not all(math.isfinite(value) and value >= 0.0 for value in terms.values()):
        raise ValueError(f"collar air has an invalid or unbooked closure: {terms}")
    return terms


def closure_terms_mm(tier, *, installed, bank_thrust):
    return projection_closure_terms_mm(tier, (0.0, 0.0, 1.0), installed=installed, bank_thrust=bank_thrust)


def worst_air_mm(tier: CollarTier, *, installed, bank_thrust) -> float:
    return nominal_full_clock_air_mm(tier) - sum(closure_terms_mm(
        tier, installed=installed, bank_thrust=bank_thrust,
    ).values())


def _candidate_normals(tier, fixed, angle_deg):
    from dt_cone_support_pose import collar_pose_frame

    origin, axis = collar_pose_frame(angle_deg)
    fixed_centre = (cone_line.X_DRUM, cone_line.Y_DRIVE,
                    bank.G19_BACK_FACE_Z + (fixed.south_mm + fixed.north_mm) / 2.0)
    vectors = [(0.0, 0.0, 1.0)]
    for station in (tier.south_mm, tier.north_mm):
        point = tuple(origin[k] + (SOUTH_STATION_MM + station) * axis[k] for k in range(3))
        z = min(bank.G19_BACK_FACE_Z + fixed.north_mm, max(
            bank.G19_BACK_FACE_Z + fixed.south_mm, point[2],
        ))
        vectors.append((point[0] - fixed_centre[0], point[1] - fixed_centre[1], point[2] - z))
    # Valid separating planes in the physical XZ section. This is a sufficient
    # enclosure proof, not a claim its finite search finds the exact distance.
    vectors.extend((math.sin(math.radians(degrees)), 0.0, math.cos(math.radians(degrees)))
                   for degrees in range(-90, 91, 3))
    normals = []
    for vector in vectors:
        normal = _normal(vector)
        if normal is not None and normal[2] >= 0.0 and normal not in normals:
            normals.append(normal)
    return normals


def full_sweep_proof(*, installed, bank_thrust, intervals=400):
    """Separate every manufactured tier pair over CLOSED P1 intervals.

    The arc debit bounds intermediate poses; sampled centre air is not a
    certificate. Failure means this OUTER proof refuses, not shop infeasibility.
    Nonnegative-Z planes also dominate the older, identical bank tiers: their
    ordered positive thicknesses put them south of G19's enclosing north tier.
    Face inspection bounds manufactured lean/form only; the COMPLETE retained
    running-fit cock, radial play and south bank travel remain in every tier.
    """
    from dt_cone_support_pose import P1_SWEEP_DEG, InstalledSupportMotionAcceptance

    if type(intervals) is not int or intervals < 1:
        raise ValueError("collar swing proof requires at least one closed interval")
    if bank_thrust is None:
        raise ValueError("full source collar air requires an observable bank thrust/face acceptance")
    if not isinstance(installed, InstalledSupportMotionAcceptance):
        raise ValueError("full source collar air requires the observable correlated support-motion acceptance")
    lower, upper = P1_SWEEP_DEG
    width = (upper - lower) / intervals
    half_rad = abs(math.radians(width)) / 2.0
    rows = []
    for index in range(intervals):
        angle = lower + (index + 0.5) * width
        for tier in TIERS:
            rotation_radius = max(abs(SOUTH_STATION_MM + station - cone_line.PIVOT_STATION)
                                  for station in (tier.south_mm + tier.south_lower_mm,
                                                  tier.north_mm + tier.north_upper_mm)) + tier.radius_mm + tier.radius_upper_mm
            for fixed in DRUM_TIERS:
                best = None
                for normal in _candidate_normals(tier, fixed, angle):
                    nominal = projection_nominal_mm(tier, normal, fixed, angle)
                    terms = projection_closure_terms_mm(
                        tier, normal, fixed, angle, half_rad,
                        installed=installed, bank_thrust=bank_thrust,
                    )
                    terms["continuous p1 interval arc"] = rotation_radius * half_rad
                    worst = nominal - sum(terms.values())
                    if best is None or worst > best["worst_mm"]:
                        best = {
                            "tier": tier.name, "drum_tier": fixed.name, "angle_deg": angle,
                            "angle_interval_deg": (lower + index * width, lower + (index + 1) * width),
                            "normal": normal, "nominal_mm": nominal,
                            "closure_mm": terms, "worst_mm": worst,
                        }
                if best is None or best["worst_mm"] <= 0.0:
                    raise ValueError(f"collar/bank shadow-aware full-clock enclosure refuses P1 interval {index}: {best}")
                rows.append(best)
    return rows


def require_air(*, installed, bank_thrust):
    rows = full_sweep_proof(installed=installed, bank_thrust=bank_thrust)
    return {tier.name: min(row["worst_mm"] for row in rows if row["tier"] == tier.name)
            for tier in TIERS}
