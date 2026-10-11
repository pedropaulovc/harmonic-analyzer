"""Axial air between the MHA-VN-016 stack collar and the drum bank's G19.

The collar rides the cone shaft just north of T006; G19's tooth face is the
bank's north end. Over the whole P1 swing the collar must never reach the
bank. The drum's tooth slab and eccentric cam are DIFFERENT finite material
tiers, and the collar's nose, body and set screw are three more: the tip
cylinder must not fill the cam's shadow through the overall thickness.

The air is a world-Z stack. Every closing term is a tolerance a released
drawing prints (part sheets, the title block, the assembly steps) or a stock
fastener/thread class, read from the spec the drawing prints it from:

* along the shaft: the post's mounting (as build_dt_drive_train_assembly's
  POST_BOSS_FACE_AXIAL_BAND_MM books it), the shaft's thrust collar, the
  gear stack's terminal north face and the collar's feeler set;
* across the shaft, at the post end: the post's tapped-hole station, its
  screws' clearance, its counterbore pattern and its running fit;
* across the shaft, at the tip end: the hold-down tap (as
  TIP_TAP_LATERAL_BAND_MM), the adjuster passage centre, the block's square
  on its one screw at the title block's angular band, the cup screw's float
  and cock in its thread, and the shaft tip's radial freedom in the cup once
  the cup is backed off for SHAFT_END_PLAY (the shaft swings on its post
  journal to take it, so it also tilts the collar's faces).
* the swing: the reamed pivot on the stock shoulder, the base pivot seat to
  the pedestal seats, the pivot thread and the T120 set (cone_set_stack);
* the collar on the shaft: its nose size, its float and cock on the journal;
* the bank: the back strap and washer datum chain and G19's cock in its
  running fit.

Vertical (Y) errors move the collar across Z, not along it.

Each physical source enters the stack once, with its full projected effect:
a plan move of a shaft support shifts the collar across the shaft by its
share of the span AND tilts the collar's faces with the shaft line, and a
post mounting error that also moves the post along the shaft adds that too.
The projections of one error are summed into that one source, never combined
as separate scatter.  The sources are then of two kinds:

* clearances (IN_SERVICE_CLEARANCES): fastener and running clearances, thread
  centring, the cup screw in its thread, the shaft tip in the backed-off cup,
  the collar's float and cock and G19's cock in its bore.  The parts can take
  them all up together, so they add arithmetically;
* printed manufacturing and set tolerances: independent of each other, so
  they combine as a root sum of squares.

The whole sweep is worst-case arithmetic over every source when that closes
everywhere; otherwise the clearances arithmetic plus the RSS of the
tolerances, everywhere.  Either way the build fails if the governing air
closes.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import _config
import cone_line
import cone_set_stack
import cylinder_bank_layout as bank
import dt_cone_gear_shaft_spec as shaft
import dt_cone_gear_stack as stack
import dt_cone_pivot_post_spec as post
import dt_cone_swing_platform_spec as plate
import dt_cone_tip_block_spec as tip
import dt_cylinder_gear_spec as drum
import vn_cone_tip_block_screw_spec as holddown_screw
import vn_cone_tip_collar_spec as collar
import _mcmaster_94025a164 as adjuster
from _hole_spec import THREAD_MAJOR_MM
from _printed_tolerance import printed_band_mm
from cone_stack_end_play import COLLAR_FEELER_BAND, SHAFT_END_PLAY
from cone_shaft_land_bands import (
    TERMINAL_FINISHED_DIA_LIMITS_MM,
    TERMINAL_FLAT_OFFSET_MIN_MM,
    TIP_COLLAR_INSTALLED_COCK_ANGLE_RAD,
)
from dt_cone_swing_platform_geometry import manufactured_p1_stop_enclosure

Vector = tuple[float, float, float]


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
    collar.TAP_STATION_BAND_MM
    + (collar.SET_SCREW_LENGTH + collar.SET_SCREW_LENGTH_BAND_MM)
    * math.sin(collar.SET_SCREW_MAX_AXIS_ANGLE_RAD)
)
_MAX_STOCK_R = math.hypot(
    collar._POINT_PLANE_MAX + collar.SET_SCREW_LENGTH + collar.SET_SCREW_LENGTH_BAND_MM,
    collar.SET_SCREW_MAJOR_DIA / 2.0 + collar.TAP_LATERAL_BAND_MM
    + (collar.SET_SCREW_LENGTH + collar.SET_SCREW_LENGTH_BAND_MM)
    * math.sin(collar.SET_SCREW_MAX_AXIS_ANGLE_RAD),
)
TIERS = (
    CollarTier("nose", 0.0, PARTITION_STATION_MM, collar.NOSE_DIA / 2.0,
               0.0, collar.AXIAL_BAND_MM + collar.SHOULDER_ROOT_RADIUS,
               collar.ROUTINE_BAND_MM / 2.0),
    CollarTier("body", PARTITION_STATION_MM, collar.WIDTH, collar.OUTER_DIA / 2.0,
               -collar.AXIAL_BAND_MM, collar.WIDTH_BAND_MM, collar.ROUTINE_BAND_MM / 2.0),
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
Z: Vector = (0.0, 0.0, 1.0)

# The P1 swing and its pivot, as the assembly poses them.
P1_SWEEP_DEG = manufactured_p1_stop_enclosure()["angle_interval_deg"]
PIVOT_XYZ: Vector = (cone_line.PIVOT_XZ[0], cone_line.Y_BASE_TOP, cone_line.PIVOT_XZ[1])

# The title block's edge break bounds G19's bore mouths.
DRUM_BORE_END_BREAK_MAX_MM = max(
    float(_config.title_block("edge_break")["radius_mm"]),
    float(_config.title_block("edge_break")["chamfer_max_mm"]),
)

# --- printed fastener and location limits -------------------------------------
# The same limits build_dt_drive_train_assembly books for the post boss face
# (POST_BOSS_FACE_AXIAL_BAND_MM) and the tip tap (TIP_TAP_LATERAL_BAND_MM).
_DRILL_PLUS = float(_config.title_block("drilled_hole")["plus_mm"])
_ANGULAR_RAD = math.radians(float(_config.title_block("angular")["value_deg"]))
_POST_FLOAT = (post.ATTACHMENT_THRU_DIA + _DRILL_PLUS - plate.POST_MOUNT_THREAD_DIA) / 2.0
_TIP_FLOAT = (plate.HOLDDOWN_CLEARANCE_DIA + _DRILL_PLUS - holddown_screw.SHANK_DIA) / 2.0
_JOURNAL_FLOAT = (
    post.BORE_DIA + post.RUNNING_BORE_BAND[0] - shaft.JOURNAL_DIA - shaft.RUNNING_DIA_BAND[1]
) / 2.0
_MOUNT_X_BAND = printed_band_mm(post.DRAWING_PRECISION_BY_NAME["MountWestX"])
_SIN_I, _COS_I = cone_line.SIN_I, cone_line.COS_I
_SUPPORT_SPAN = shaft.T006_TIP_STATION - cone_line.POST_STATION
# The cup screw's #10-32 UNF-2B internal pitch diameter MAX against the
# purchased 94025A164's class 2A minimum: the cup floats and cocks in its
# thread over the block's depth.
_INTERNAL_PITCH_MAX = 0.1736 * 25.4
_THREAD_FLOAT = (_INTERNAL_PITCH_MAX - adjuster.EXTERNAL_PITCH_DIA_MIN_MM) / 2.0
_MIN_EMBED = tip.ADJUSTER_MIN_ENGAGEMENT_D * THREAD_MAJOR_MM[tip.ADJUSTER_THREAD]
_BLOCK_DEPTH_MAX = tip.BLOCK_Z + printed_band_mm(tip.BLOCK_DEPTH_PLACES)
# The block stands on one screw; its square to the plate is a plain angle and
# takes the title block's angular band, about that screw, over the cup's reach.
_CUP_REACH = math.hypot(
    abs(tip.FOOT_TAP_OFFSET_X) + printed_band_mm(tip.PASSAGE_CENTER_PLACES),
    abs(shaft.T006_TIP_STATION - cone_line.TIP_BLOCK_STATION) + _BLOCK_DEPTH_MAX / 2.0,
)
# Step 3 seats the tip in the cup, then backs the cup off for SHAFT_END_PLAY.
# At the far end of that stroke the 45 deg cup wall stands SHAFT_END_PLAY *
# tan(45) clear of the seated tip, and the shaft, swinging on its post
# journal, can carry the tip that far across the cup.  The terminal's D-flat
# runs out through the tip, so toward the flat the D's two corners, not its
# round, meet the wall: a Ø2r D with its flat o off the axis, moved d toward
# the flat, reaches the wall circle r + e when r^2 + 2*o*d + d^2 = (r + e)^2.
# The largest terminal and the shallowest flat (printed limits) give the most
# room; any edge break only lets the tip seat deeper on its break, which
# gives less.  The shaft turns, so the flat can face any way: the larger of
# the two directions is booked.
_TERMINAL_R_MAX = TERMINAL_FINISHED_DIA_LIMITS_MM[1] / 2.0
_CUP_WALL_R = _TERMINAL_R_MAX + SHAFT_END_PLAY[1] * (adjuster.CUP_DIA / 2.0) / adjuster.CUP_DEPTH
_TIP_CAPTURE = max(
    _CUP_WALL_R - _TERMINAL_R_MAX,
    math.sqrt(TERMINAL_FLAT_OFFSET_MIN_MM**2 + _CUP_WALL_R**2 - _TERMINAL_R_MAX**2)
    - TERMINAL_FLAT_OFFSET_MIN_MM,
)

# Along the shaft, from the post's mounting to the collar's south face.
AXIAL_TERMS_MM = {
    "post platform tap station": plate.POST_MOUNT_STATION_TOL_MM,
    "post screw clearance": _POST_FLOAT,
    "post counterbore pattern": _MOUNT_X_BAND * _SIN_I,
    "post cone boss length": printed_band_mm(post.DRAWING_PRECISION_BY_NAME["ConeBossLen"]) / 2.0,
    "shaft thrust collar width": shaft.printed_band("CollarWidth"),
    "gear stack terminal north face": -stack.face_band(stack.COUNT - 1, "north")[1],
    "collar feeler set": COLLAR_FEELER_BAND,
}
# Across the shaft in plan, at each end of the shaft line.
POST_END_TERMS_MM = {
    "post platform tap station": plate.POST_MOUNT_STATION_TOL_MM,
    "post screw clearance": _POST_FLOAT,
    "post counterbore pattern": _MOUNT_X_BAND * _COS_I,
    "post running journal fit": _JOURNAL_FLOAT,
}
TIP_END_TERMS_MM = {
    "tip platform hold-down station": plate.HOLDDOWN_STATION_TOL_MM,
    "tip hold-down screw clearance": _TIP_FLOAT,
    "tip block foot tap station": tip.FOOT_TAP_STATION_TOL_MM,
    "tip passage centre": printed_band_mm(tip.PASSAGE_CENTER_PLACES),
    "tip block square on its one screw": _CUP_REACH * math.sin(_ANGULAR_RAD),
    "tip cup in its thread": _THREAD_FLOAT + _BLOCK_DEPTH_MAX * (2.0 * _THREAD_FLOAT / _MIN_EMBED),
    "shaft tip in the backed-off cup": _TIP_CAPTURE,
}
# The swing's frame (cone_set_stack's set-at-assembly terms).
SWING_TERMS_MM = {
    "platform pivot bore on the shoulder": cone_set_stack.PIVOT_BORE_FLOAT_MM,
    "base pivot seat to the pedestal seats": cone_set_stack.PIVOT_SEAT_POSITION_MM,
    "pivot thread centring": cone_set_stack.PIVOT_THREAD_CENTRING_MM,
}
# The sources booked arithmetically: clearances the parts take up together
# in service or at fit-up, not independent manufacturing scatter.  Every
# other source is a printed tolerance and joins the RSS.
IN_SERVICE_CLEARANCES = frozenset({
    "post screw clearance",
    "post running journal fit",
    "tip hold-down screw clearance",
    "tip cup in its thread",
    "shaft tip in the backed-off cup",
    "platform pivot bore on the shoulder",
    "pivot thread centring",
    "collar float on the journal",
    "collar cock on the journal",
    "G19 cock in its running fit",
})


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b, strict=True))


def _rotate(a: Vector, angle_deg: float) -> Vector:
    c, s = math.cos(math.radians(angle_deg)), math.sin(math.radians(angle_deg))
    return c * a[0] + s * a[2], a[1], -s * a[0] + c * a[2]


def collar_pose_frame(angle_deg: float) -> tuple[Vector, Vector]:
    """Nominal station-zero origin and north unit axis after the P1 swing."""
    delta = tuple(cone_line.CONE_ORIGIN[i] - PIVOT_XYZ[i] for i in range(3))
    moved = _rotate(delta, angle_deg)
    return (tuple(PIVOT_XYZ[i] + moved[i] for i in range(3)),
            _rotate((cone_line.SIN_I, 0.0, cone_line.COS_I), angle_deg))


def cylinder_support(origin, axis, south, north, radius, normal, *, maximum):
    """Exact finite filled-cylinder support, not a distance sampling surrogate."""
    along = _dot(axis, normal)
    transverse = math.sqrt(max(0.0, _dot(normal, normal) - along**2))
    ends = (south * along, north * along)
    return _dot(origin, normal) + (
        max(ends) + radius * transverse if maximum else min(ends) - radius * transverse
    )


def projection_nominal_mm(tier, normal=Z, fixed=None, angle_deg=0.0):
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


def _ends(tier: CollarTier) -> tuple[float, float]:
    return (SOUTH_STATION_MM + tier.south_mm + tier.south_lower_mm,
            SOUTH_STATION_MM + tier.north_mm + tier.north_upper_mm)


def _pivot_reach_mm(tier: CollarTier, angle_deg: float) -> float:
    """The tier's furthest material from the swing pivot, in plan."""
    origin, axis = collar_pose_frame(angle_deg)
    return max(
        math.dist(tuple(origin[k] + end * axis[k] for k in (0, 2)), (PIVOT_XYZ[0], PIVOT_XYZ[2]))
        for end in _ends(tier)
    ) + tier.radius_mm + tier.radius_upper_mm


def closure_terms_mm(tier: CollarTier, fixed: DrumTier, angle_deg: float = 0.0) -> dict[str, float]:
    """Worst-case closing of the world-Z air, one entry per physical source.

    A source with several projections (a post mounting error moves the post
    along the shaft, moves the line across it and tilts the collar's faces)
    enters once, as the sum of all of them.
    """
    origin, axis = collar_pose_frame(angle_deg)
    along = abs(axis[2])
    across = math.sqrt(max(0.0, 1.0 - along**2))
    ends = _ends(tier)
    radius = tier.radius_mm + tier.radius_upper_mm
    terms = {name: value * along for name, value in AXIAL_TERMS_MM.items()}
    # The shaft line runs from the post journal to the cup: a plan move of
    # either end across the shaft moves each collar station by its share of
    # the span, and tilts the collar's faces with the line.
    share = max((end - cone_line.POST_STATION) / _SUPPORT_SPAN for end in ends)
    tilt = radius / _SUPPORT_SPAN
    for name, value in POST_END_TERMS_MM.items():
        terms[name] = terms.get(name, 0.0) + value * ((1.0 - share) * across + tilt)
    for name, value in TIP_END_TERMS_MM.items():
        terms[name] = terms.get(name, 0.0) + value * (share * across + tilt)
    terms.update(SWING_TERMS_MM)
    # The T120 feeler sets the swing angle to T120_SET_MM at T120; the
    # collar turns with it about the pivot.
    set_angle = cone_set_stack.T120_SET_MM / cone_set_stack.pivot_distance_mm(120)
    terms["T120 set of the swing"] = _pivot_reach_mm(tier, angle_deg) * set_angle
    # The collar on its journal: nose size, float and cock (vn_cone_tip_collar).
    terms["collar tier axial limit"] = -tier.south_lower_mm * along
    terms["collar tier radial limit"] = tier.radius_upper_mm * across
    cock = TIP_COLLAR_INSTALLED_COCK_ANGLE_RAD
    bore_upper_r = collar.BORE_FINISHED_DIA_LIMITS_MM[1] / 2.0
    terms["collar float on the journal"] = (
        collar.TIP_COLLAR_MAX_RADIAL_FLOAT_MM + bore_upper_r * (1.0 / math.cos(cock) - 1.0)
    ) * across
    terms["collar cock on the journal"] = (
        max(abs(e - SOUTH_STATION_MM) for e in ends) * (1.0 - math.cos(cock))
        + radius * math.sin(cock)
    )
    # The bank: its datum chain, then G19's cock within its running fit.
    terms.update({f"bank {name}": value for name, value in bank.DATUM_CHAIN_STACK.items()})
    manufactured = _tilted_fixed_support(fixed, Z, 0.0)
    nominal = cylinder_support((0.0, 0.0, 0.0), Z, fixed.south_mm, fixed.north_mm,
                               fixed.radius_mm, Z, maximum=True)
    terms["drum tier limits"] = max(0.0, manufactured - nominal)
    contact_span = (drum.OVERALL_THICKNESS + drum.OVERALL_THICKNESS_BAND[1]
                    - 2.0 * DRUM_BORE_END_BREAK_MAX_MM)
    if contact_span <= 0.0:
        raise ValueError("drum has no finite running-bore contact span")
    running_cock = math.atan(drum.BORE_DIAMETRAL_CLEARANCE_MM[1] / contact_span)
    terms["G19 cock in its running fit"] = max(
        0.0, _tilted_fixed_support(fixed, Z, running_cock) - manufactured,
    ) + max(abs(v) for v in drum.OVERALL_THICKNESS_BAND) * math.sin(running_cock / 2.0)
    if not all(math.isfinite(value) and value >= 0.0 for value in terms.values()):
        raise ValueError(f"collar air has an invalid closing term: {terms}")
    if not IN_SERVICE_CLEARANCES <= terms.keys():
        raise ValueError(f"collar air lost a clearance source: {IN_SERVICE_CLEARANCES - terms.keys()}")
    return terms


@dataclass(frozen=True)
class AirStack:
    tier: str
    drum_tier: str
    angle_deg: float
    nominal_mm: float
    terms: dict[str, float]
    arc_mm: float  # the swing between this interval's midpoint and its ends

    @property
    def clearances(self) -> dict[str, float]:
        return {k: v for k, v in self.terms.items() if k in IN_SERVICE_CLEARANCES}

    @property
    def tolerance_rss_mm(self) -> float:
        return math.hypot(*(v for k, v in self.terms.items() if k not in IN_SERVICE_CLEARANCES))

    @property
    def arithmetic_mm(self) -> float:
        return self.nominal_mm - sum(self.terms.values()) - self.arc_mm

    @property
    def statistical_mm(self) -> float:
        return (self.nominal_mm - sum(self.clearances.values())
                - self.tolerance_rss_mm - self.arc_mm)

    def closure_mm(self, method: str) -> dict[str, float]:
        if method == "arithmetic":
            return {**self.terms, "continuous p1 interval arc": self.arc_mm}
        return {**self.clearances,
                "RSS of the printed tolerances": self.tolerance_rss_mm,
                "continuous p1 interval arc": self.arc_mm}


def full_sweep_proof(*, intervals: int = 400) -> list[dict]:
    """Every collar tier against both drum tiers over closed P1 intervals.

    Each row is one interval's midpoint; the arc term bounds the poses
    between midpoints. The whole sweep is worst-case arithmetic when that
    closes everywhere; otherwise "statistical" everywhere: the clearances
    arithmetic plus the RSS of the printed tolerances.  Raises if the
    governing air closes anywhere.
    """
    if type(intervals) is not int or intervals < 1:
        raise ValueError("collar swing proof requires at least one closed interval")
    lower, upper = P1_SWEEP_DEG
    width = (upper - lower) / intervals
    half_rad = abs(math.radians(width)) / 2.0
    stacks = []
    for index in range(intervals):
        angle = lower + (index + 0.5) * width
        for tier in TIERS:
            for fixed in DRUM_TIERS:
                stacks.append((index, AirStack(
                    tier.name, fixed.name, angle, projection_nominal_mm(tier, Z, fixed, angle),
                    closure_terms_mm(tier, fixed, angle), _pivot_reach_mm(tier, angle) * half_rad,
                )))
    method = "arithmetic" if all(s.arithmetic_mm > 0.0 for _, s in stacks) else "statistical"
    rows = []
    for index, s in stacks:
        air = s.arithmetic_mm if method == "arithmetic" else s.statistical_mm
        if not math.isfinite(air) or air <= 0.0:
            raise ValueError(
                f"MHA-VN-016 collar can reach G19 at P1 {s.angle_deg:.3f} deg: {s.tier}/"
                f"{s.drum_tier} nominal {s.nominal_mm:.3f}, arithmetic "
                f"{s.arithmetic_mm:.3f}, statistical {s.statistical_mm:.3f}: {s.terms}"
            )
        rows.append({
            "tier": s.tier, "drum_tier": s.drum_tier, "angle_deg": s.angle_deg,
            "angle_interval_deg": (lower + index * width, lower + (index + 1) * width),
            "normal": Z, "nominal_mm": s.nominal_mm, "method": method,
            "arithmetic_mm": s.arithmetic_mm, "statistical_mm": s.statistical_mm,
            "closure_mm": s.closure_mm(method), "air_mm": air,
        })
    return rows


def require_air() -> dict[str, float]:
    rows = full_sweep_proof()
    return {tier.name: min(row["air_mm"] for row in rows if row["tier"] == tier.name)
            for tier in TIERS}
