"""Conservative, correlated two-support pose enclosure for the seated cone set.

This is an OUTER enclosure, not a claim that every enclosed pose assembles.
A positive separating-plane certificate is sufficient; refusal is not proof of
interference. The platform remains seated on the base. Loose lifting/rocking is
not this state. Its nominal P1 rotation is handled separately from tolerances.

There is no independent +/-1 degree on the BASIC cone incline. The shaft line
passes through the post running journal and the retained, threaded tip support.
Common translations are paid once, never again as an independent shaft tilt.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import _config
import cone_line as line
import dt_cone_gear_shaft_spec as shaft
import dt_cone_pivot_post_spec as post
import dt_cone_swing_platform_spec as plate
import dt_cone_tip_block_spec as tip
import dt_crankshaft_spec as crankshaft
import fr_harmonic_base_spec as base
import vn_cone_pivot_screw_spec as pivot
import vn_cone_tip_adjuster_spec as adjuster
from _hole_spec import THREAD_MAJOR_MM
from _printed_tolerance import printed_band_mm
from dt_cone_swing_platform_geometry import (
    manufactured_p1_stop_enclosure,
    seated_pivot_axis_offset_terms_mm,
)

Vector = tuple[float, float, float]
PIVOT_xyz: Vector = (line.PIVOT_XZ[0], line.Y_BASE_TOP, line.PIVOT_XZ[1])
P1_STOP_ENCLOSURE = manufactured_p1_stop_enclosure()
P1_SWEEP_DEG = P1_STOP_ENCLOSURE["angle_interval_deg"]
_DRILL_PLUS = float(_config.title_block("drilled_hole")["plus_mm"])
_POST_FLOAT = (post.ATTACHMENT_THRU_DIA + _DRILL_PLUS - plate.POST_MOUNT_THREAD_DIA) / 2.0
_TIP_FLOAT = (plate.HOLDDOWN_CLEARANCE_DIA + _DRILL_PLUS - THREAD_MAJOR_MM[tip.HOLDDOWN_THREAD]) / 2.0
_PIVOT_FLOAT = (plate.PIVOT_HOLE_DIA + _DRILL_PLUS - (pivot.SHOULDER_DIA + pivot.SHOULDER_DIA_BAND[1])) / 2.0
_JOURNAL_FLOAT = (post.BORE_DIA + post.RUNNING_BORE_BAND[0] - shaft.JOURNAL_DIA - shaft.RUNNING_DIA_BAND[1]) / 2.0
_SUPPORT_SPAN = shaft.T006_TIP_STATION - line.POST_STATION
_CRANK_FLOAT = crankshaft.JOURNAL_DIAMETRAL_CLEARANCE_MM[1] / 2.0
SEATED_FACE_PREMISE = (
    "Fully seated machined foot faces on a base-seated plate whose two "
    "opposed bearing faces stay inside its printed stock-size envelope; "
    "the stock +/-0.13 alone is not an independent flatness certificate."
)
_POST_FOOT_TILT_RAD = math.atan(
    2.0 * plate.PLATE_STOCK_BAND
    / (round(post.BLOCK_DIA, post.DRAWING_PRECISION_BY_NAME["MainBodyDia"])
       - printed_band_mm(post.DRAWING_PRECISION_BY_NAME["MainBodyDia"]))
)
_TIP_FOOT_TILT_RAD = math.atan(2.0 * plate.PLATE_STOCK_BAND * math.hypot(
    1.0 / (tip.BLOCK_X - printed_band_mm(tip.BLOCK_WIDTH_PLACES)),
    1.0 / (tip.BLOCK_Z - printed_band_mm(tip.BLOCK_DEPTH_PLACES)),
))

# #10-32 UNF-2B pitch MAX, supplier standard-thread table:
# https://www.steelmasters.co.nz/wp-content/uploads/2022/03/External___Internal_Thread_Dimensions_for_UNF_Screw_Thread_2016.pdf
# The actual purchased 94025A164 is class 2A (live McMaster product page).
# Cup dimensions remain vendor NOMINALS, not zero-tolerance product definition.
_INTERNAL_PITCH_MAX = 0.1736 * 25.4
_THREAD_FLOAT = (_INTERNAL_PITCH_MAX - adjuster.EXTERNAL_PITCH_DIA_MIN_MM) / 2.0
_MIN_EMBED = tip.ADJUSTER_MIN_ENGAGEMENT_D * THREAD_MAJOR_MM[tip.ADJUSTER_THREAD]
_POST_MOUNT_X_BAND = printed_band_mm(post.DRAWING_PRECISION_BY_NAME["MountWestX"])
_POST_PATTERN_YAW_RAD = math.asin(min(1.0,
    2.0 * (_POST_FLOAT + math.sqrt(2.0) * plate.POST_MOUNT_STATION_TOL_MM)
    / (post.ATTACHMENT_SPACING - 2.0 * _POST_MOUNT_X_BAND)
))
_CONE_BORE_LENGTH_MIN = shaft.JOURNAL_SUPPORT_SPAN_MIN_MM
_SHAFT_IN_POST_ANGLE_RAD = math.atan(2.0 * _JOURNAL_FLOAT / _CONE_BORE_LENGTH_MIN)
_BLOCK_DEPTH_MAX = tip.BLOCK_Z + printed_band_mm(tip.BLOCK_DEPTH_PLACES)
# A headless cup is a cut inside the external-thread material envelope. The
# accepted rim remains inside the block's full-thread engagement window. Use
# the entire block depth as the extrapolation lever, not an assumed cup depth.
# The open top slit makes the bare countersink circle an invalid capture proof.
TIP_CAPTURE_ENVELOPE_MM = (
    adjuster.THREAD_MAJOR_MAX_MM / 2.0 + _THREAD_FLOAT
    + _BLOCK_DEPTH_MAX * (2.0 * _THREAD_FLOAT / _MIN_EMBED)
)


@dataclass(frozen=True, slots=True)
class InstalledAxisAcceptance:
    """Conditional actual SHAFT inspection, not a supplied post-bore grade.

    Measure the retained shaft's round-back centres at two separated stations,
    TIP retained, through a full shaft turn, opposed light radial seating
    loads and the ENTIRE retained axial endplay. A north-seated cup or a
    south-seated thrust collar alone is not this full running-axis envelope:
    axial cup withdrawal permits additional transverse shaft motion.
    Refer X/Y to the ACTUAL bank arbor axis and Z to its actual thrust/washer
    plane, fit the centre line and project to ``station_mm``. Include
    measurement uncertainty. Gear-seat eccentricity, tooth runout, axial
    MATERIAL travel and the booked mesh opening remain with the caller.

    This records a proposed/required domain, never a claim of measurements.
    Production values must be derived jointly from actual20 mesh and full-P1
    collar air margins; there is deliberately no default numeric grade.
    """

    xyz_half_width_mm: Vector
    direction_angle_rad: float
    station_mm: float = shaft.TIP_COLLAR_START_STATION

    def __post_init__(self) -> None:
        if (len(self.xyz_half_width_mm) != 3
                or not all(math.isfinite(v) and v > 0.0 for v in self.xyz_half_width_mm)
                or not math.isfinite(self.direction_angle_rad)
                or not 0.0 < self.direction_angle_rad < math.pi / 2.0
                or not math.isfinite(self.station_mm)):
            raise ValueError("installed shaft acceptance needs finite positive XYZ/direction limits")


@dataclass(frozen=True, slots=True)
class InstalledSupportMotionAcceptance:
    """Observed support centres and a CLOSED full-stroke north-motion domain.

    Indicate the actual post BORE centre against the bank datum and retain
    that setting during installation. In the FIXED measurement plane at
    ``north_station_mm``, normal to the nominal shaft, indicate the actual
    shaft round-back centre against the actual bank datums. The north XYZ
    box is FIXED about the source nominal north centre in those datums.
    It is not recentered on a measured mean or on any selected seated point.

    Rho is the minimum radial-plane distance from the actual north centre
    to the intersection of that FIXED box with the SAME measurement plane.
    It is not unrestricted 3D distance or an XZ-only distance that ignores Y.
    At cup seating the ENTIRE centre family under every clock/opposed load
    must lie in that box. Thus rho=0 retains post-fit-dependent seated
    freedom, without matching or subtracting a measured baseline centre.
    Observe the box-plus-excursion condition through the complete stroke.

    For q measured northward from the south thrust stop, actual endplay e
    must satisfy 0 < e <= axial_travel_max_mm, and the ENTIRE admitted motion
    must satisfy rho**2 / north_radial_motion_max_mm**2 + q / e <= 1.
    Both axial endpoints and all intervening motion are covered, including
    metrology/setup uncertainty. The bound using the maximum e is an outer
    enclosure of every accepted actual e; it is not a nominal cup model.

    No supplier cup angle, cup/thread coaxiality, sharp D-tip or preload is
    assumed. Actual post radial running fit is added once. Axial MATERIAL
    travel is correlated by the projection law, not independently max-added.
    Numeric requirements belong to the joint air/mesh margin owner; this
    record neither chooses grades nor claims an actual part passed.
    """

    post_xyz_half_width_mm: Vector
    north_xyz_half_width_mm: Vector
    north_radial_motion_max_mm: float
    north_station_mm: float
    axial_travel_max_mm: float

    def __post_init__(self) -> None:
        for widths in (self.post_xyz_half_width_mm, self.north_xyz_half_width_mm):
            if len(widths) != 3 or not all(math.isfinite(v) and v > 0.0 for v in widths):
                raise ValueError("support motion inspection needs finite positive centre bounds")
        if (not math.isfinite(self.north_radial_motion_max_mm)
                or self.north_radial_motion_max_mm <= 0.0
                or not math.isfinite(self.north_station_mm)
                or not math.isfinite(self.axial_travel_max_mm)
                or self.axial_travel_max_mm <= 0.0
                or self.support_span_mm <= self.relative_error_mm):
            raise ValueError("support motion inspection needs a positive resolved span, motion radius and axial travel")

    @property
    def support_span_mm(self) -> float:
        return self.north_station_mm - line.POST_STATION

    @property
    def relative_error_mm(self) -> float:
        return (
            _norm(self.post_xyz_half_width_mm) + _JOURNAL_FLOAT
            + _norm(self.north_xyz_half_width_mm) + self.north_radial_motion_max_mm
        )

    @property
    def direction_angle_rad(self) -> float:
        return math.atan(self.relative_error_mm / (self.support_span_mm - self.relative_error_mm))


@dataclass(frozen=True, slots=True)
class BankThrustAcceptance:
    """Manufactured bank face-to-bore error, NOT a running-cock acceptance.

    Indicate both working faces of ALL 20 actual bank gears through a full
    turn on a close, indicated mandrel referenced to each ACTUAL bore axis;
    indicate both actual thrust washers against their seated thrust datum.
    Include complete face form and metrology error in ``face_tir_mm``.
    ``indicated_span_mm`` is an actual measured diametral trace on retained
    working material, never nominal OD or an edge-break allowance.

    ``direction_angle_rad`` bounds manufactured face lean relative to the
    inspected datum only. The consumer MUST retain the full independent
    running-fit cock and the indicated face-form debit. This inspection
    cannot remove clearance, provide preload, or certify a free-running gear
    meets this TIR under opposed loads. A short trace or one point does not
    establish the complete face enclosure. No default grade replaces the
    joint mesh/air margin derivation.
    """

    face_tir_mm: float
    indicated_span_mm: float

    def __post_init__(self) -> None:
        if not (math.isfinite(self.face_tir_mm) and math.isfinite(self.indicated_span_mm)
                and 0.0 < self.face_tir_mm < self.indicated_span_mm):
            raise ValueError("bank thrust inspection needs positive TIR below measured span")

    @property
    def direction_angle_rad(self) -> float:
        return math.atan(self.face_tir_mm / self.indicated_span_mm)


INSTALLED_AXIS_INSPECTION_SCOPE = (
    "Conditional fitted retained shaft, not post-bore or loose gear OD; "
    "actual bank arbor and thrust/washer datums; full-turn opposed-load "
    "round-back centre extrema across the ENTIRE retained axial endplay; "
    "a single cup-seated setup is not the full running domain; "
    "measurement uncertainty included; no claim stock has passed."
)


def installed_axis_projection_terms_mm(
    acceptance: InstalledAxisAcceptance | InstalledSupportMotionAcceptance,
    south_station: float, north_station: float, radius_mm: float,
    normal: Vector, angle_deg: float = 0.0,
    *, axial_closing_coefficient: float = 0.0,
) -> dict[str, float]:
    """Complete inspected enclosure; do not add the source hardware again.

    Transporting an engaged measurement about the ACTUAL rather than nominal
    pivot adds (I-R)*pivot_error, which vanishes at engagement. It does not
    re-add the engaged pivot displacement already measured. The opposed-load
    inspection must bound the retained running-clearance extrema throughout
    the seated functional swing; rigid nominal transport alone is not that
    evidence.
    """
    if isinstance(acceptance, InstalledSupportMotionAcceptance):
        return installed_support_projection_terms_mm(
            acceptance, south_station, north_station, radius_mm, normal, angle_deg,
            axial_closing_coefficient=axial_closing_coefficient,
        )
    if axial_closing_coefficient != 0.0:
        raise ValueError("correlated axial travel requires a support motion acceptance")
    if (not all(math.isfinite(v) for v in (*normal, south_station, north_station, radius_mm, angle_deg))
            or abs(_norm(normal) - 1.0) > 1e-9 or radius_mm < 0.0
            or north_station < south_station):
        raise ValueError("installed enclosure requires finite stations, radius and unit normal")
    lever = max(abs(station - acceptance.station_mm) for station in (south_station, north_station))
    axes = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    result = {
        f"installed shaft {name} at inspection station": width * abs(_dot(normal, _rotate(axis, angle_deg)))
        for name, width, axis in zip("XYZ", acceptance.xyz_half_width_mm, axes)
    }
    result["installed shaft direction at material lever"] = (
        lever * 2.0 * math.sin(acceptance.direction_angle_rad / 2.0)
    )
    _, axis = collar_pose_frame(angle_deg)
    result["installed shaft directional radial growth"] = radial_projection_growth_mm(
        radius_mm, normal, axis, acceptance.direction_angle_rad,
    )
    pivot_radius = math.sqrt(2.0) * printed_band_mm(2) + sum(seated_pivot_axis_offset_terms_mm().values())
    # Plate-to-shoulder clearance can change which material point is the
    # rotation centre; include it in the transport remainder, not at angle 0.
    pivot_radius += _PIVOT_FLOAT
    result["actual pivot transport remainder"] = (
        2.0 * pivot_radius * abs(math.sin(math.radians(angle_deg) / 2.0))
        * math.hypot(normal[0], normal[2])
    )
    return result


def _dot(a: Vector, b: Vector) -> float:
    return sum(x * y for x, y in zip(a, b))


def _norm(a: Vector) -> float:
    return math.sqrt(_dot(a, a))


def _rotate(a: Vector, angle_deg: float) -> Vector:
    c, s = math.cos(math.radians(angle_deg)), math.sin(math.radians(angle_deg))
    return c * a[0] + s * a[2], a[1], -s * a[0] + c * a[2]


def radial_projection_growth_mm(
    radius_mm: float, normal: Vector, axis: Vector, direction_angle_rad: float,
) -> float:
    """Exact outward support growth of a radial disk over an axis-angle cone.

    For theta=acos(|normal.axis|), the nominal disk support is R*sin(theta).
    The greatest permitted support is R*sin(min(pi/2, theta+alpha)).
    In particular a normal perpendicular to the nominal axis pays ZERO
    outward radial growth, not R*alpha. Material-centre/endpoint motion is
    accounted separately; a shrinking radial projection cannot close air.
    """
    if (not math.isfinite(radius_mm) or radius_mm < 0.0
            or not math.isfinite(direction_angle_rad) or not 0.0 <= direction_angle_rad <= math.pi
            or not all(math.isfinite(v) for v in (*normal, *axis))
            or abs(_norm(normal) - 1.0) > 1e-9 or abs(_norm(axis) - 1.0) > 1e-9):
        raise ValueError("radial projection needs a finite radius, angle and unit vectors")
    theta = math.acos(min(1.0, abs(_dot(normal, axis))))
    return radius_mm * max(0.0, math.sin(min(math.pi / 2.0, theta + direction_angle_rad)) - math.sin(theta))


def collar_pose_frame(angle_deg: float) -> tuple[Vector, Vector]:
    """Nominal station-zero origin and north unit axis after actual P1 Ry."""
    delta = tuple(line.CONE_ORIGIN[i] - PIVOT_xyz[i] for i in range(3))
    moved = _rotate(delta, angle_deg)
    return (tuple(PIVOT_xyz[i] + moved[i] for i in range(3)),
            _rotate((line.SIN_I, 0.0, line.COS_I), angle_deg))


@dataclass(frozen=True)
class _Motion:
    name: str
    radius: float
    direction: Vector | None = None
    planar: bool = False
    plane_normal: Vector | None = None

    def support(self, normal: Vector) -> float:
        if self.direction is not None:
            return self.radius * abs(_dot(normal, self.direction))
        if self.plane_normal is not None:
            return self.radius * math.sqrt(max(
                0.0, _dot(normal, normal) - _dot(normal, self.plane_normal) ** 2,
            ))
        return self.radius * (math.hypot(normal[0], normal[2]) if self.planar else _norm(normal))


def _support_motions(angle_deg: float) -> tuple[list[_Motion], list[_Motion], list[_Motion]]:
    """Common, post-only and tip-only enclosures; no independent bore angle."""
    x = _rotate((line.COS_I, 0.0, -line.SIN_I), angle_deg)
    z = _rotate((line.SIN_I, 0.0, line.COS_I), angle_deg)
    y = (0.0, 1.0, 0.0)
    mount_band = printed_band_mm(post.DRAWING_PRECISION_BY_NAME["MountWestX"])
    # Averages of two holes have at most each hole's coordinate band. The
    # post's mounting-hole X dimensions are in POST/world-X, not shaft Z.
    # The two-hole pattern permits bounded yaw; enclose its rotated X vector
    # with the nominal vector plus an explicit chord remainder.
    yaw = _POST_PATTERN_YAW_RAD
    common = [
        # _drawing_common._check_hole_table_locations documents two-place cells;
        # the base table is explicitly non-BASIC. The finished-edge datum's
        # common translation relative to the bank cancels, not this hole error.
        _Motion("platform base pivot X coordinate", printed_band_mm(2), (1.0, 0.0, 0.0)),
        _Motion("platform base pivot Z coordinate", printed_band_mm(2), (0.0, 0.0, 1.0)),
        _Motion("platform pivot shoulder radial fit", _PIVOT_FLOAT, planar=True),
        *(_Motion(name, radius, planar=True)
          for name, radius in seated_pivot_axis_offset_terms_mm().items()),
    ]
    post_terms = [
        _Motion("post platform tap X station", plate.POST_MOUNT_STATION_TOL_MM, x),
        _Motion("post platform tap Z station", plate.POST_MOUNT_STATION_TOL_MM, z),
        _Motion("post mounting screw planar clearance", _POST_FLOAT, planar=True),
        _Motion("post mounting printed X vector", mount_band, _rotate((1.0, 0.0, 0.0), angle_deg)),
        _Motion("post mounting X vector yaw remainder", 2.0 * mount_band * math.sin(yaw / 2.0), planar=True),
        _Motion("post journal axis height", post.JOURNAL_AXIS_HEIGHT_TOLERANCE_MM, y),
        _Motion("post local plate thickness", plate.PLATE_STOCK_BAND, y),
        _Motion("post running journal radial fit", _JOURNAL_FLOAT),
        # One whole-body foot rotation moves this endpoint; normalization
        # derives the corresponding retained shaft direction from BOTH ends.
        _Motion("post seated foot endpoint", 2.0 * (
            post.BORE_HEIGHT + post.JOURNAL_AXIS_HEIGHT_TOLERANCE_MM + _JOURNAL_FLOAT
        ) * math.sin(_POST_FOOT_TILT_RAD / 2.0)),
    ]
    # One hold-down bolt does not index block yaw. Enclose the complete plan
    # orbit of its cup-support point; do not silently fix the block orientation.
    # The rim's accepted engagement window lies within the actual block depth.
    # Its contact can be at most the retained support capture beyond that rim.
    tap_to_axis = abs(tip.FOOT_TAP_OFFSET_X) + tip.FOOT_TAP_STATION_TOL_MM + printed_band_mm(tip.PASSAGE_CENTER_PLACES)
    orbit = math.hypot(tap_to_axis, _BLOCK_DEPTH_MAX / 2.0)
    nominal_lever = math.hypot(tip.FOOT_TAP_OFFSET_X, shaft.T006_TIP_STATION - line.TIP_BLOCK_STATION)
    tip_terms = [
        _Motion("tip platform hold-down X station", plate.HOLDDOWN_STATION_TOL_MM, x),
        _Motion("tip platform hold-down Z station", plate.HOLDDOWN_STATION_TOL_MM, z),
        _Motion("tip hold-down screw planar clearance", _TIP_FLOAT, planar=True),
        _Motion("tip one-bolt block orbit and axial engagement", orbit + nominal_lever, planar=True),
        _Motion("tip adjuster axis height", tip.AXIS_HEIGHT_TOL_MM, y),
        _Motion("tip local plate thickness", plate.PLATE_STOCK_BAND, y),
        _Motion("tip retained thread and cup material envelope", TIP_CAPTURE_ENVELOPE_MM),
        _Motion("tip seated foot endpoint", 2.0 * (
            math.hypot(tip.ADJUSTER_AXIS_HEIGHT + tip.AXIS_HEIGHT_TOL_MM, orbit)
            + TIP_CAPTURE_ENVELOPE_MM
        ) * math.sin(_TIP_FOOT_TILT_RAD / 2.0)),
    ]
    return common, post_terms, tip_terms


def _support_line_projection_terms_mm(
    south_station: float, north_station: float, radius_mm: float,
    normal: Vector, u: Vector,
    common: list[_Motion], post_terms: list[_Motion], tip_terms: list[_Motion],
    support_span: float, relative_error_mm: float,
) -> dict[str, float]:
    """Normalized two-point line bound, with an explicit complete error ball."""
    nu = _dot(normal, u)
    transverse = tuple(normal[i] - nu * u[i] for i in range(3))
    result = {term.name: term.support(normal) for term in common}
    lambdas = tuple((station - line.POST_STATION) / support_span for station in (south_station, north_station))
    for terms, at_tip in ((post_terms, False), (tip_terms, True)):
        for term in terms:
            result[term.name] = max(term.support(tuple(
                lam * transverse[i] if at_tip else normal[i] - lam * transverse[i]
                for i in range(3)
            )) for lam in lambdas)
    length_min = support_span - relative_error_mm
    if length_min <= 0.0:
        raise ValueError("support enclosure permits coincident endpoints")
    transverse_remainder = relative_error_mm * (
        relative_error_mm + relative_error_mm**2 / (2.0 * length_min)
    ) / (support_span * length_min)
    axial_remainder = relative_error_mm**2 / (2.0 * length_min**2)
    lever = max(abs(station - line.POST_STATION) for station in (south_station, north_station))
    result["two-support normalization remainder"] = lever * (
        _norm(transverse) * transverse_remainder + abs(nu) * axial_remainder
    )
    result["two-support radial-frame rotation"] = radial_projection_growth_mm(
        radius_mm, normal, u, math.atan(relative_error_mm / length_min),
    )
    return result


def correlated_north_motion_support_mm(
    radial_support_mm: float, axial_closing_coefficient: float,
    axial_travel_max_mm: float,
) -> float:
    """Exact max of A*q + radial_support*sqrt(1-q/e) on the admitted stroke.

    This support law is conditional on the full-stroke observation contract,
    not a deduction from an unspecified vendor cup. A must upper-bound the
    SIGNED axial material closing coefficient over every permitted axis pose.
    """
    if (not all(math.isfinite(v) for v in (
            radial_support_mm, axial_closing_coefficient, axial_travel_max_mm,
        )) or radial_support_mm < 0.0 or axial_travel_max_mm <= 0.0):
        raise ValueError("correlated motion needs finite support/coefficient and positive travel")
    axial_support = axial_closing_coefficient * axial_travel_max_mm
    if axial_support <= 0.0 or radial_support_mm >= 2.0 * axial_support:
        return radial_support_mm
    return axial_support + radial_support_mm**2 / (4.0 * axial_support)


def installed_support_projection_terms_mm(
    acceptance: InstalledSupportMotionAcceptance,
    south_station: float, north_station: float, radius_mm: float,
    normal: Vector, angle_deg: float = 0.0,
    *, axial_closing_coefficient: float = 0.0,
) -> dict[str, float]:
    """Complete correlated observation; axial coefficient bounds all axis poses."""
    if (not all(math.isfinite(v) for v in (*normal, south_station, north_station, radius_mm, angle_deg))
            or abs(_norm(normal) - 1.0) > 1e-9 or radius_mm < 0.0
            or north_station < south_station):
        raise ValueError("support projection requires finite stations, radius and unit normal")
    axes = tuple(_rotate(axis, angle_deg) for axis in (
        (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0),
    ))
    _, u = collar_pose_frame(angle_deg)
    post_terms = [
        _Motion(f"indicated post bore centre {name}", width, axis)
        for name, width, axis in zip("XYZ", acceptance.post_xyz_half_width_mm, axes)
    ]
    post_terms.append(_Motion("actual post running radial fit", _JOURNAL_FLOAT))
    north_terms = [
        _Motion(f"indicated north motion centre {name}", width, axis)
        for name, width, axis in zip("XYZ", acceptance.north_xyz_half_width_mm, axes)
    ]
    north_terms.append(_Motion(
        "actual full north shaft-motion envelope",
        acceptance.north_radial_motion_max_mm, plane_normal=u,
    ))
    pivot_radius = (
        math.sqrt(2.0) * printed_band_mm(2)
        + sum(seated_pivot_axis_offset_terms_mm().values()) + _PIVOT_FLOAT
    )
    common = [_Motion(
        "actual pivot transport remainder",
        2.0 * pivot_radius * abs(math.sin(math.radians(angle_deg) / 2.0)),
        planar=True,
    )]
    result = _support_line_projection_terms_mm(
        south_station, north_station, radius_mm, normal, u,
        common, post_terms, north_terms,
        acceptance.support_span_mm, acceptance.relative_error_mm,
    )
    radial_support = result.pop("actual full north shaft-motion envelope")
    result["correlated north motion and axial material travel"] = correlated_north_motion_support_mm(
        radial_support, axial_closing_coefficient, acceptance.axial_travel_max_mm,
    )
    return result


def installed_axis_from_support_inspections(
    post_xyz_half_width_mm: Vector,
    terminal_xyz_half_width_mm: Vector,
    terminal_station_mm: float,
    *, station_mm: float = shaft.TIP_COLLAR_START_STATION,
) -> InstalledAxisAcceptance:
    """Derive a shaft domain from accessible installed support observations.

    Indicate a removable gauge arbor in the actual post bore against the bank
    datums, infer its centre at POST_STATION, and lock the post. Keep that
    setting while replacing the arbor with the real shaft/stack/collar.
    Retain the TIP support and indicate the exposed terminal round BACK arc
    through a full turn and opposed seating loads across the ENTIRE retained
    axial endplay. Neither the D-flat, a loose gear OD, nor an assumed
    accessible south journal proud is a target. If only a cup-seated setup
    axis is observed, first enclose the full sourced cup-gap/capture motion
    in the terminal input; a tight setup-axis grade cannot replace that
    running freedom.

    Both input boxes include instrument/centering error, actual station-plane
    uncertainty and any verified post movement during final installation.
    The post observation is a BORE centre: add its real radial running
    clearance once. The terminal observation already measures the SHAFT.
    Normalizing this pair bounds running cock; do not add a full-boss cock
    term to the returned class. This computes required-domain consequences,
    not evidence that an actual setup or piece passed the observations.
    """
    for widths in (post_xyz_half_width_mm, terminal_xyz_half_width_mm):
        if len(widths) != 3 or not all(math.isfinite(v) and v > 0.0 for v in widths):
            raise ValueError("support inspection needs finite positive XYZ bounds")
    if not math.isfinite(terminal_station_mm) or not math.isfinite(station_mm):
        raise ValueError("support inspection needs finite stations")
    span = terminal_station_mm - line.POST_STATION
    error = _norm(post_xyz_half_width_mm) + _norm(terminal_xyz_half_width_mm) + _JOURNAL_FLOAT
    if span <= error:
        raise ValueError("support inspection cannot resolve the shaft direction")
    axes = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    post_terms = [
        _Motion(f"indicated post bore {name}", width, axis)
        for name, width, axis in zip("XYZ", post_xyz_half_width_mm, axes)
    ]
    post_terms.append(_Motion("actual running radial clearance at post midpoint", _JOURNAL_FLOAT))
    tip_terms = [
        _Motion(f"indicated retained terminal {name}", width, axis)
        for name, width, axis in zip("XYZ", terminal_xyz_half_width_mm, axes)
    ]
    _, u = collar_pose_frame(0.0)
    widths = tuple(sum(_support_line_projection_terms_mm(
        station_mm, station_mm, 0.0, normal, u, [], post_terms, tip_terms, span, error,
    ).values()) for normal in axes)
    return InstalledAxisAcceptance(widths, math.atan(error / (span - error)), station_mm)


def collar_projection_closure_terms_mm(
    south_station: float, north_station: float, radius_mm: float,
    normal: Vector, angle_deg: float = 0.0,
    *, installed: InstalledAxisAcceptance | InstalledSupportMotionAcceptance | None = None,
    axial_closing_coefficient: float = 0.0,
) -> dict[str, float]:
    """Bound support-plane movement of a finite shaft-attached cylinder.

    Unit ``normal`` is in the world frame. Boss/shaft/stack/feeler/collar size
    bands and nominal P1 sweep variation belong to the caller. Base elevation
    and its finished-edge origin are common with the cylinder bank and cancel.

    For P=P0+p, T=T0+t, Q=P+l*unit(T-P), the linear movement is
    p + (l/L)*(I-uu')*(t-p). Its coefficients preserve the common-mode
    correlation. Explicit normalization and radial-frame remainders make the
    result a bound, not a first-order tolerance estimate.
    A nonzero axial_closing_coefficient requires the correlated support-motion
    observation and must bound the signed axial material closing coefficient
    over every admitted axis pose. Its travel is then included in BOTH whole
    enclosures before intersection; the caller must not add that travel again.
    """
    if (not all(math.isfinite(v) for v in (*normal, south_station, north_station, radius_mm, angle_deg))
            or abs(_norm(normal) - 1.0) > 1e-9 or radius_mm < 0.0
            or north_station < south_station):
        raise ValueError("pose enclosure requires finite stations, radius and unit normal")
    if (not math.isfinite(axial_closing_coefficient)
            or (axial_closing_coefficient != 0.0
                and not isinstance(installed, InstalledSupportMotionAcceptance))):
        raise ValueError("correlated axial travel requires a support motion acceptance")
    _, u = collar_pose_frame(angle_deg)
    common, post_terms, tip_terms = _support_motions(angle_deg)
    # Common pivot/coordinate errors cannot become a second shaft tilt.
    error = sum(term.radius for term in (*post_terms, *tip_terms))
    source_result = _support_line_projection_terms_mm(
        south_station, north_station, radius_mm, normal, u,
        common, post_terms, tip_terms, _SUPPORT_SPAN, error,
    )
    if isinstance(installed, InstalledSupportMotionAcceptance) and axial_closing_coefficient != 0.0:
        source_result["axial material travel outer bound"] = (
            max(0.0, axial_closing_coefficient) * installed.axial_travel_max_mm
        )
    # A finite post journal bounds shaft-to-BORE cock, not the bore's
    # absolute direction relative to the mounted body. The BASIC inter-bore
    # angle and crank-relative FCF do not license a narrower body-yaw cone.
    if installed is None:
        return source_result
    inspected = installed_axis_projection_terms_mm(
        installed, south_station, north_station, radius_mm, normal, angle_deg,
        axial_closing_coefficient=axial_closing_coefficient,
    )
    # A support function of the intersection is bounded by the minimum of
    # the two WHOLE support functions. Never mix per-term minima, nor claim
    # the box of those projections consists only of physically attainable poses.
    return inspected if sum(inspected.values()) < sum(source_result.values()) else source_result


def collar_z_closure_terms_mm(south_station: float, north_station: float, radius_mm: float) -> dict[str, float]:
    """Engaged world-Z wrapper; full P1 proof must use directional intervals."""
    return collar_projection_closure_terms_mm(south_station, north_station, radius_mm, (0.0, 0.0, 1.0))


def platform_geometric_endplay_interval_mm() -> tuple[float, float]:
    """Geometric bound only, NOT a new numerical matched-fit acceptance.

    e=shoulder_length-finished_bearing_thickness, with positive retained
    bearing thickness and free swing. Thus 0<=e<shoulder_MAX; the closed outer
    interval is safe. The .25 relief depth is reference-only, not +/-.51.
    Seated/clamped pose uses no vertical head-float translation.
    """
    return 0.0, pivot.SHOULDER_LEN + pivot.SHOULDER_LEN_BAND[0]


def _crank_axis_world_frame(angle_deg: float) -> tuple[Vector, Vector]:
    """Physical post-axis anchor and configured crank direction after P1."""
    post_point = line.cone_station(line.POST_STATION)
    post_point[1] = line.Y_CRANK
    delta = tuple(post_point[i] - PIVOT_xyz[i] for i in range(3))
    rotated = _rotate(delta, angle_deg)
    return (
        tuple(PIVOT_xyz[i] + rotated[i] for i in range(3)),
        _rotate((0.0, 0.0, 1.0), angle_deg),
    )


def crank_axis_nominal_xy_mm(z_mm: float, angle_deg: float = 0.0) -> tuple[float, float]:
    """Current source-selected crank axis at a world-Z plane, NOT qualification.

    Reads the live post/cone/pivot station including the approved tip extension.
    This nominal reader remains usable when a conservative uncertainty outer
    enclosure refuses; it neither freezes a historical Y nor implies that
    actual3D crank station/phase or a manufactured chain fit has passed.
    """
    if not math.isfinite(z_mm) or not math.isfinite(angle_deg):
        raise ValueError("crank nominal axis requires finite Z and P1 angle")
    centre, direction = _crank_axis_world_frame(angle_deg)
    if abs(direction[2]) < 1e-12:
        raise ValueError("nominal crank axis is parallel to the requested Z plane")
    t = (z_mm - centre[2]) / direction[2]
    return tuple(centre[i] + t * direction[i] for i in range(2))


def crank_axis_global_xy_bounds(z_mm: float, angle_deg: float = 0.0, *, relative_to_base: bool = False) -> dict:
    """Outer GLOBAL crank-axis bounds at a specified machine-Z station.

    The chain-wheel plane must be supplied: a tilted axis has no single XY.
    These are not crossed-mesh relative-centre tolerances. ``relative_to_base``
    removes only the deck/finished-edge frame shared with another base rider;
    pivot-hole placement, shaft fit and all post controls remain included.
    """
    if not math.isfinite(z_mm) or not math.isfinite(angle_deg):
        raise ValueError("crank global bounds require finite Z and P1 angle")
    centre, direction = _crank_axis_world_frame(angle_deg)
    common, post_terms, _ = _support_motions(angle_deg)
    axes = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    post_terms = [term for term in post_terms if term.name != "post seated foot endpoint"]
    bands = [sum(term.support(axis) for term in (*common, *post_terms)) for axis in axes]
    # Replace the cone support's radial fit with the independent crank fit.
    # The +.37/0 spacing is conservatively enclosed symmetrically here; it
    # must NOT replace the asymmetric local mesh law.
    for i in range(3):
        bands[i] += _CRANK_FLOAT - _JOURNAL_FLOAT
    bands[1] += max(abs(value) for value in post.CRANK_ABOVE_CONE_BAND)
    # One foot rotation moves the physical post-axis anchor. Direction is
    # reconstructed from the actual cone datum and foot normal below; there
    # is no second whole-line/long-lever foot debit after that reconstruction.
    foot_anchor_displacement = 2.0 * (
        post.CRANK_BORE_HEIGHT + post.JOURNAL_AXIS_HEIGHT_TOLERANCE_MM
        + max(abs(value) for value in post.CRANK_ABOVE_CONE_BAND) + _CRANK_FLOAT
    ) * math.sin(_POST_FOOT_TILT_RAD / 2.0)
    bands = [value + foot_anchor_displacement for value in bands]
    if not relative_to_base:
        bands[0] += printed_band_mm(base.DRAWING_PRECISION_BY_NAME["BottomLen"]) / 2.0
        bands[2] += printed_band_mm(base.DRAWING_PRECISION_BY_NAME["BottomWid"]) / 2.0
        bands[1] += sum(printed_band_mm(base.DRAWING_PRECISION_BY_NAME[name])
                        for name in ("BottomThickness", "FlangeToRim", "RimHeight"))
    boss_places = post.DRAWING_PRECISION_BY_NAME["CrankBossLen"]
    boss_min = round(post.CRANK_BOSS_LENGTH, boss_places) - printed_band_mm(boss_places)
    # The FCF fixes crank relative to cone datum A and foot B, NOT relative
    # to nominal body yaw. Recover the actual A direction from the retained
    # shaft plus its real journal cock, and B from the seated-foot premise.
    cone_bore_angle = cone_axis_angle_bound_rad(angle_deg) + _SHAFT_IN_POST_ANGLE_RAD
    cone_chord = 2.0 * math.sin(min(math.pi, cone_bore_angle) / 2.0)
    foot_chord = 2.0 * math.sin(_POST_FOOT_TILT_RAD / 2.0)
    cross_error = cone_chord + foot_chord
    if cross_error >= 1.0:
        raise ValueError("source cone/foot frame permits an unresolved crank direction")
    # x=unit(B cross A); |cross-cross0|<=e, |cross|>=1-e.
    # v=cos(I)*A-sin(I)*x is the BASIC crank line before its own FCF error.
    cross_chord = min(2.0, 2.0 * cross_error / (1.0 - cross_error))
    frame_chord = min(2.0, abs(line.COS_I) * cone_chord + abs(line.SIN_I) * cross_chord)
    frame_angle = 2.0 * math.asin(frame_chord / 2.0)
    theta = (
        frame_angle + math.atan(post.CRANK_BORE_ANGULARITY_MM / boss_min)
        + math.atan(2.0 * _CRANK_FLOAT / crankshaft.JOURNAL_SUPPORT_SPAN_MIN_MM)
    )
    # Do not project a relative mesh centre allowance into this global frame.
    # The finite journal permits a direction chord epsilon and the actual
    # intersection parameter is (Z-Cz)/dz, including the centre's Z uncertainty.
    epsilon = 2.0 * math.sin(theta / 2.0)
    denominator_min = direction[2] - epsilon
    if denominator_min <= 0.0:
        raise ValueError("global crank enclosure can become parallel to requested Z plane")
    nominal_t = (z_mm - centre[2]) / direction[2]
    t_error = (bands[2] + abs(nominal_t) * epsilon) / denominator_min
    nominal_xy = crank_axis_nominal_xy_mm(z_mm, angle_deg)
    xy_bands = tuple(bands[i] + abs(direction[i]) * t_error
                     + epsilon * (abs(nominal_t) + t_error) for i in range(2))
    return {
        "z_mm": z_mm, "angle_deg": angle_deg,
        "nominal_xy_mm": nominal_xy,
        "lower_xy_mm": tuple(nominal_xy[i] - xy_bands[i] for i in range(2)),
        "upper_xy_mm": tuple(nominal_xy[i] + xy_bands[i] for i in range(2)),
        "centre_xyz_half_width_mm": tuple(bands),
        "direction_angle_bound_rad": theta,
        "foot_rotation_bound_rad": _POST_FOOT_TILT_RAD,
        "foot_anchor_displacement_mm": foot_anchor_displacement,
        "cone_and_foot_frame_angle_bound_rad": frame_angle,
        "seated_face_premise": SEATED_FACE_PREMISE,
        "relative_to_base": relative_to_base,
        "qualification": (
            "conditional seated source outer enclosure; refusal is not interference; "
            "nominal crank station is not an actual3D mesh qualification"
        ),
        "crank_mesh_qualified": False,
        "installed_joint_scope": P1_STOP_ENCLOSURE["qualification"],
    }


def cone_axis_angle_bound_rad(
    angle_deg: float = 0.0, *, installed: InstalledAxisAcceptance | InstalledSupportMotionAcceptance | None = None,
) -> float:
    """Whole source-enclosure angle, not an independently attainable corner.

    Common translations cancel. The retained post/TIP endpoints bound the
    complete shaft line. The crank's relative FCF is deliberately absent.
    A finite post journal bounds shaft-relative-to-bore cock only: it cannot
    manufacture an independent absolute cone-bore/body angle grade.
    """
    _, post_terms, tip_terms = _support_motions(angle_deg)
    error = sum(term.radius for term in (*post_terms, *tip_terms))
    length_min = _SUPPORT_SPAN - error
    if length_min <= 0.0:
        raise ValueError("support enclosure permits coincident endpoints")
    bound = math.atan(error / length_min)
    return min(bound, installed.direction_angle_rad) if installed is not None else bound


def cone_axis_local_pose_enclosure(
    origin_station_mm: float,
    nominal_frame: tuple[Vector, Vector, Vector],
    *, installed: InstalledAxisAcceptance | InstalledSupportMotionAcceptance | None = None,
) -> dict:
    """Nominal-local origin/shortest-transport bounds for a rigid-body solver.

    ``nominal_frame`` contains world-coordinate ROWS, with its third column
    along the nominal shaft. Translation is bounded at this exact placement
    origin with radius zero: the caller rotates the actual material, so a
    finite-face/radius movement must not also be charged as translation.

    A direction cone admits a shortest-axis transport of rotation angle at
    most alpha. For alpha<pi/2 each local Rz*Ry*Rx Euler component is within
    +/-alpha (off-diagonal entries <=sin(alpha), diagonals >=cos(alpha)).
    These Euler boxes are a safe OUTER, not independently observed rotations.
    Material twist is NOT measured by a centreline inspection. The caller
    must retain its separately sourced physical clock law in this transport
    gauge, and any rotating gear-seat eccentricity. No zero clock is supplied.
    """
    if len(nominal_frame) != 3 or any(len(row) != 3 for row in nominal_frame):
        raise ValueError("nominal frame must have three world-coordinate rows")
    columns = tuple(tuple(nominal_frame[row][column] for row in range(3)) for column in range(3))
    if (not all(math.isfinite(value) for column in columns for value in column)
            or any(abs(_norm(column) - 1.0) > 1e-9 for column in columns)
            or any(abs(_dot(columns[i], columns[j])) > 1e-9 for i in range(3) for j in range(i))):
        raise ValueError("nominal frame must be orthonormal")
    cross = (
        columns[0][1] * columns[1][2] - columns[0][2] * columns[1][1],
        columns[0][2] * columns[1][0] - columns[0][0] * columns[1][2],
        columns[0][0] * columns[1][1] - columns[0][1] * columns[1][0],
    )
    _, nominal_axis = collar_pose_frame(0.0)
    if _dot(cross, columns[2]) < 1.0 - 1e-9 or _dot(columns[2], nominal_axis) < 1.0 - 1e-9:
        raise ValueError("nominal frame must be right-handed with north shaft axis")
    ledgers = tuple(collar_projection_closure_terms_mm(
        origin_station_mm, origin_station_mm, 0.0, normal, installed=installed,
    ) for normal in columns)
    widths = tuple(sum(ledger.values()) for ledger in ledgers)
    angle = cone_axis_angle_bound_rad(installed=installed)
    if not 0.0 <= angle < math.pi / 2.0:
        raise ValueError("source axis cannot use the local Euler transport chart")
    return {
        "origin_station_mm": origin_station_mm,
        "nominal_frame_rows": tuple(tuple(row) for row in nominal_frame),
        "translation_intervals_mm": tuple((-width, width) for width in widths),
        "shortest_transport_euler_intervals_rad": ((-angle, angle),) * 3,
        "source_projection_ledgers_mm": ledgers,
        "axis_direction_bound_rad": angle,
        "installed_axis_acceptance": asdict(installed) if installed is not None else None,
        "material_clock_observed": False,
        "qualification": (
            "complete source/installed intersection projected to an outer box; "
            "shortest-axis transport only; retain separately sourced material "
            "clock, rotating body eccentricity and axial material travel; "
            "outer refusal is not physical infeasibility"
        ),
    }
