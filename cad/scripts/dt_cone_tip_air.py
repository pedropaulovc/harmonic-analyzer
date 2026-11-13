"""Axial air between the cone tip and the drum bank's G19.

Owner decision C1 keyed (2026-11-09, PR #1992): the cone shaft's tip carries
the brass bushing pressed on T006's pivot (MHA-DT-38), whose north face bears
on the end of the end screw (MHA-DT-39) threaded through the moved tip block
(MHA-DT-21).  G19's tooth face is the bank's north end.  Over the whole P1
swing none of the three may reach the bank:

* the bushing rides the shaft at its model station (cone_tip_cluster: the
  layout T006 north face plus TIP_SET_SHIFT_MM), its corner toward T006
  broken by its chamfer at the smallest printed leg (dt_cone_tip_bushing_spec,
  #2697);
* the end screw's end stands proud of the block's south face toward the
  cone, set against the bushing at assembly (dt_cone_tip_block_spec);
* the block's south face, only where it stands over G19 (inside its tip
  circle, or the cam's), since elsewhere the block clears the bank in plan
  (the research's block_air.py definition).

The drum's tooth slab and eccentric cam are different finite material tiers.

The air is a world-Z stack. Every closing term is a tolerance a released
drawing prints (part sheets, the title block, the assembly steps) or a stock
fastener/thread class, read from the spec the drawing prints it from:

* along the shaft, for the bushing and the screw end: the post's mounting
  (as build_dt_drive_train_assembly's POST_BOSS_FACE_AXIAL_BAND_MM books it,
  less the screw clearance the pushed post takes up), the shaft's thrust
  collar, the gear stack's T006 north face (its feeler-set T024 included,
  dt_cone_gear_stack.face_band) and, for the screw end, the bushing's length
  and the end play set at assembly;
* across the shaft, at the post end: the post's tapped-hole station, its
  screws' clearance, its counterbore pattern and its running fit;
* across the shaft, at the tip end: the hold-down tap, the adjuster passage
  centre, the block's square on its one screw at the title block's angular
  band, the end screw's float and cock in its thread and the pivot in the
  end screw's reamed hole (the pivot is captured there, so the shaft's swing
  in the post journal stays inside these);
* for the block: its hold-down station and screw float, its foot tap station,
  its printed depth and its square, along the axis; across it, the same
  stations move the face in plan, which can carry more of it over G19;
* the swing: the reamed pivot on the stock shoulder, the base pivot seat to
  the pedestal seats, the pivot thread and the feel set (cone_set_stack);
* the bank: the south strap/disc datum chain, accepted full-stack length and
  G19's cock in its running fit.

Vertical (Y) errors move the parts across Z, not along it.

Each physical source enters the stack once, with its full projected effect,
and every source is in exactly one of two sets: in-service clearances the
parts can take up together (IN_SERVICE_CLEARANCES, arithmetic) or independent
printed manufacturing and set tolerances (INDEPENDENT_TOLERANCES, RSS); an
unclassified source is refused.  The whole sweep is worst-case arithmetic
over every source when that closes everywhere; otherwise the clearances
arithmetic plus the RSS of the tolerances, everywhere (machining-dfm.md).
Either way the build fails if the governing air closes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import _mcmaster_91794a558 as end_screw_stock
import cone_line
import cone_set_stack
import cone_tip_cluster as cluster
import cylinder_bank_layout as bank
import dt_cone_gear_shaft_spec as shaft
import dt_cone_gear_stack as stack
import dt_cone_pivot_post_spec as post
import dt_cone_swing_platform_spec as plate
import dt_cone_tip_block_spec as tip
import dt_cone_tip_bushing_spec as bushing
import dt_cone_tip_end_screw_spec as end_screw
import dt_cylinder_gear_spec as drum
import dt_vn_cone_tip_block_screw_spec as holddown_screw
from _printed_tolerance import (
    angular_band_deg,
    drilled_oversize_mm,
    edge_break_chamfer_mm,
    edge_break_radius_mm,
    printed_band_mm,
)
from cone_stack_end_play import SHAFT_END_PLAY
from dt_cone_swing_platform_checks import manufactured_p1_stop_enclosure

Vector = tuple[float, float, float]


@dataclass(frozen=True)
class ShaftTier:
    """A cylinder on the cone axis between two cone stations."""

    name: str
    south_mm: float
    north_mm: float
    radius_mm: float
    south_lower_mm: float
    north_upper_mm: float
    radius_upper_mm: float
    # The tier's own limits split by physical source: name -> (axial loss,
    # radial gain), summing to -south_lower_mm and radius_upper_mm.
    limits: dict[str, tuple[float, float]]
    # A 45 deg break on the south O.D. corner, at its smallest printed leg
    # (0: a square corner).
    south_chamfer_mm: float = 0.0


@dataclass(frozen=True)
class DrumTier:
    name: str
    south_mm: float
    north_mm: float
    radius_mm: float
    south_lower_mm: float
    north_upper_mm: float
    radius_upper_mm: float


# --- the moving material ------------------------------------------------------
BUSHING_SOUTH_STATION_MM = cone_line.T006_NORTH_FACE + cluster.TIP_SET_SHIFT_MM
_BUSHING_OD_BAND = printed_band_mm(cluster.BUSHING_PLACES, unit="in")
_BUSHING_LENGTH_BAND = printed_band_mm(cluster.BUSHING_PLACES, unit="in")
# The screw stands set against the bushing at the model's end play; the
# least the assembly step sets brings it this much further south.
_SET_END_PLAY_LOSS = tip.END_SCREW_MODEL_END_PLAY_MM - SHAFT_END_PLAY[0]
_SCREW_LIMITS = {
    "bushing length": (_BUSHING_LENGTH_BAND, 0.0),
    "end screw set end play": (_SET_END_PLAY_LOSS, 0.0),
}
TIERS = (
    ShaftTier(
        "bushing",
        BUSHING_SOUTH_STATION_MM,
        BUSHING_SOUTH_STATION_MM + cluster.BUSHING_LENGTH_MM,
        cluster.BUSHING_OD_MM / 2.0,
        0.0,
        _BUSHING_LENGTH_BAND,
        _BUSHING_OD_BAND / 2.0,
        {"bushing outside diameter": (0.0, _BUSHING_OD_BAND / 2.0)},
        bushing.END_CHAMFER_MIN,
    ),
    # The thread's major at its 2A maximum stands in for the proud end.
    ShaftTier(
        "screw end",
        tip.END_SCREW_END_STATION,
        tip.TIP_BLOCK_SOUTH_FACE,
        end_screw_stock.THREAD_MAJOR_MAX_MM / 2.0,
        -sum(axial for axial, _ in _SCREW_LIMITS.values()),
        0.0,
        0.0,
        _SCREW_LIMITS,
    ),
)
BLOCK_TIER = "block"
TIER_NAMES = (*(tier.name for tier in TIERS), BLOCK_TIER)
if tip.END_SCREW_END_STATION >= tip.TIP_BLOCK_SOUTH_FACE:
    raise AssertionError("the end screw no longer stands proud of MHA-DT-21")
# The block's south face spans the drum axis's height (the cone axis and the
# drive share one height), so over a drum circle only its plan x matters.
if not (
    cone_line.CONE_ORIGIN[1] == cone_line.Y_DRIVE
    and 0.0 < tip.ADJUSTER_AXIS_HEIGHT < tip.BLOCK_HEIGHT
):
    raise AssertionError("the drum axis no longer runs across the block's height")

DRUM_TIERS = (
    DrumTier(
        "tooth_face",
        -drum.FACE_WIDTH,
        0.0,
        drum.OUTSIDE_DIA / 2.0,
        -drum.FACE_WIDTH_TOLERANCE_MM,
        0.0,
        max(0.0, drum.outside_dia_limits_mm()[1] - drum.OUTSIDE_DIA) / 2.0,
    ),
    # Full cam clock is enclosed by its actual eccentric orbit, not tip OD.
    DrumTier(
        "cam",
        -drum.OVERALL_THICKNESS,
        -drum.FACE_WIDTH,
        drum.CAM_DIA / 2.0 + drum.ECCENTRICITY,
        drum.OVERALL_THICKNESS_BAND[1],
        drum.FACE_WIDTH_TOLERANCE_MM,
        max(0.0, drum.CAM_DIA_BAND[0]) / 2.0 + drum.ECCENTRICITY_TOLERANCE_MM,
    ),
)
Z: Vector = (0.0, 0.0, 1.0)

# The P1 swing and its pivot, as the assembly poses them.
P1_SWEEP_DEG = manufactured_p1_stop_enclosure()["angle_interval_deg"]
PIVOT_XYZ: Vector = (cone_line.PIVOT_XZ[0], cone_line.Y_BASE_TOP, cone_line.PIVOT_XZ[1])

# The title block's edge break bounds G19's bore mouths.
DRUM_BORE_END_BREAK_MAX_MM = max(
    edge_break_radius_mm(unit=drum.UNIT), edge_break_chamfer_mm(unit=drum.UNIT)
)

# --- printed fastener and location limits -------------------------------------
# The same limits build_dt_drive_train_assembly books for the post boss face
# (POST_BOSS_FACE_AXIAL_BAND_MM) and the tip tap (TIP_TAP_LATERAL_BAND_MM).
_DRILL_PLUS = drilled_oversize_mm(unit=post.UNIT)  # post and plate both print inch
_ANGULAR_RAD = math.radians(angular_band_deg(unit=tip.UNIT))
_POST_FLOAT = (
    post.ATTACHMENT_THRU_DIA + _DRILL_PLUS - plate.POST_MOUNT_THREAD_DIA
) / 2.0
_TIP_FLOAT = (
    plate.HOLDDOWN_CLEARANCE_DIA + _DRILL_PLUS - holddown_screw.SHANK_DIA
) / 2.0
_JOURNAL_FLOAT = (
    post.BORE_DIA
    + post.JOURNAL_BORE_BAND[0]
    - shaft.JOURNAL_DIA
    - shaft.RUNNING_DIA_BAND[1]
) / 2.0
_MOUNT_X_BAND = printed_band_mm(
    post.DRAWING_PRECISION_BY_NAME["MountWestX"], unit=post.UNIT
)
_SIN_I, _COS_I = cone_line.SIN_I, cone_line.COS_I
# The shaft line runs from the post journal to the pivot in the end screw.
TIP_SUPPORT_STATION_MM = tip.END_SCREW_END_STATION
_SUPPORT_SPAN = TIP_SUPPORT_STATION_MM - cone_line.POST_STATION
_BLOCK_DEPTH_BAND = tip.printed_band_mm(tip.BLOCK_DEPTH_PLACES)
_BLOCK_DEPTH_MAX = tip.BLOCK_Z + _BLOCK_DEPTH_BAND
_BLOCK_HALF_WIDTH_MAX = max(tip.WORST_HALF_WIDTH_MM.values())
# The block stands on one screw; its square to the plate is a plain angle and
# takes the title block's angular band, about that screw, over the end
# screw's reach from it.
_SCREW_REACH = math.hypot(
    abs(tip.FOOT_TAP_OFFSET_X) + tip.printed_band_mm(tip.PASSAGE_CENTER_PLACES),
    abs(tip.TIP_BLOCK_STATION - TIP_SUPPORT_STATION_MM) + _BLOCK_DEPTH_MAX / 2.0,
)
# The end screw floats and cocks in the 1/4-28 thread over its engagement in
# the block (dt_cone_tip_block_spec.END_SCREW_THREAD_FLOAT_MM, the 2A/2B
# pitch-diameter fit), and the pivot runs in its reamed hole, which sits
# END_HOLE_POSITION_MM off the thread axis.
_THREAD_FLOAT = tip.END_SCREW_THREAD_FLOAT_MM[1]
_SCREW_COCK = 2.0 * _THREAD_FLOAT / tip.END_SCREW_ENGAGEMENT_MIN_MM
_PIVOT_IN_HOLE = (
    cluster.PIVOT_RUNNING_CLEARANCE_MM[1] / 2.0 + end_screw.END_HOLE_POSITION_MM
)

# MHA-DT-00 step 2H (user decision 2026-10-12) holds the post pushed toward
# the tip block while it is turned (2J) and its screws are tightened (2K):
# its clearance can only carry the tip away from G19, so its along-shaft
# share is booked 0 (the across-shaft and face-tilt shares stay booked in
# full).  MHA-DT-21 is not slid on its snug hold-down (2F) but may sit
# anywhere in its clearance when 2K tightens it, so that stays booked.
POST_SCREW_CLEARANCE_TAKEN_UP_MM = _POST_FLOAT

# Along the shaft, from the post's mounting to T006's north face.
AXIAL_TERMS_MM = {
    "post platform tap station": plate.POST_MOUNT_STATION_TOL_MM,
    "post screw clearance": _POST_FLOAT - POST_SCREW_CLEARANCE_TAKEN_UP_MM,
    "post counterbore pattern": _MOUNT_X_BAND * _SIN_I,
    "post cone boss length": printed_band_mm(
        post.DRAWING_PRECISION_BY_NAME["ConeBossLen"], unit=post.UNIT
    )
    / 2.0,
    "shaft thrust collar width": shaft.printed_band("CollarWidth"),
    "gear stack T006 north face": -stack.face_band(stack.COUNT - 1, "north")[1],
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
    "tip block foot tap station": tip.FOOT_TAP_X_TOL_MM,
    "tip passage centre": tip.printed_band_mm(tip.PASSAGE_CENTER_PLACES),
    "tip block square on its one screw": _SCREW_REACH * math.sin(_ANGULAR_RAD),
    "end screw in its thread": _THREAD_FLOAT + _BLOCK_DEPTH_MAX * _SCREW_COCK,
    "pivot in the end screw's hole": _PIVOT_IN_HOLE,
}
# The block's south face: along the axis (the platform hole's station, the
# screw's float in it, the foot tap's station from the north face, the
# printed depth, and the square about the screw swinging a corner south) ...
BLOCK_AXIAL_TERMS_MM = {
    "tip platform hold-down station": plate.HOLDDOWN_STATION_TOL_MM,
    "tip hold-down screw clearance": _TIP_FLOAT,
    "tip block foot tap station": tip.FOOT_TAP_Z_TOL_MM,
    "tip block depth": _BLOCK_DEPTH_BAND,
    "tip block square on its one screw": _BLOCK_HALF_WIDTH_MAX * math.sin(_ANGULAR_RAD),
}
# ... and across it in plan (the same stations; its width band only brings
# the +X face in).
BLOCK_LATERAL_TERMS_MM = {
    "tip platform hold-down station": plate.HOLDDOWN_STATION_TOL_MM,
    "tip hold-down screw clearance": _TIP_FLOAT,
    "tip block foot tap station": tip.FOOT_TAP_X_TOL_MM,
}
BLOCK_PLAN_SHIFT_SOURCE = "tip block plan shift over G19"
# The swing's frame (cone_set_stack's set-at-assembly terms).
SWING_TERMS_MM = {
    "platform pivot bore on the shoulder": cone_set_stack.PIVOT_BORE_FLOAT_MM,
    "base pivot seat transferred through the platform bore": cone_set_stack.PIVOT_SEAT_TRANSFER_MM,
    "pivot thread centring": cone_set_stack.PIVOT_THREAD_CENTRING_MM,
}
IN_SERVICE_CLEARANCES = frozenset(
    {
        "post screw clearance",
        "post running journal fit",
        "tip hold-down screw clearance",
        "end screw in its thread",
        "pivot in the end screw's hole",
        "platform pivot bore on the shoulder",
        "pivot thread centring",
        "G19 cock in its running fit",
        # The plan shift combines the block's stations with its screw's float;
        # booked arithmetically.
        BLOCK_PLAN_SHIFT_SOURCE,
    }
)
INDEPENDENT_TOLERANCES = frozenset(
    {
        "post platform tap station",
        "post counterbore pattern",
        "post cone boss length",
        "shaft thrust collar width",
        "gear stack T006 north face",
        "tip platform hold-down station",
        "tip block foot tap station",
        "tip passage centre",
        "tip block square on its one screw",
        "tip block depth",
        "base pivot seat transferred through the platform bore",
        "swing feel set",
        "bushing outside diameter",
        "bushing length",
        "end screw set end play",
        *(f"bank {name}" for name in bank.DATUM_CHAIN_STACK),
        "bank accepted stack length",
        "drum tier limits",
    }
)
if IN_SERVICE_CLEARANCES & INDEPENDENT_TOLERANCES:
    raise AssertionError("a tip air source cannot be both a clearance and a tolerance")
# Sources only some tiers carry.
_TIER_ONLY_SOURCES = frozenset(
    {name for tier in TIERS for name in tier.limits}
    | {"tip block depth", BLOCK_PLAN_SHIFT_SOURCE}
    | set(AXIAL_TERMS_MM)
    | set(POST_END_TERMS_MM)
    | set(TIP_END_TERMS_MM)
)


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b, strict=True))


def _rotate(a: Vector, angle_deg: float) -> Vector:
    c, s = math.cos(math.radians(angle_deg)), math.sin(math.radians(angle_deg))
    return c * a[0] + s * a[2], a[1], -s * a[0] + c * a[2]


def tip_pose_frame(angle_deg: float) -> tuple[Vector, Vector]:
    """Nominal station-zero origin and north unit axis after the P1 swing."""
    delta = tuple(cone_line.CONE_ORIGIN[i] - PIVOT_XYZ[i] for i in range(3))
    moved = _rotate(delta, angle_deg)
    return (
        tuple(PIVOT_XYZ[i] + moved[i] for i in range(3)),
        _rotate((cone_line.SIN_I, 0.0, cone_line.COS_I), angle_deg),
    )


def cylinder_support(origin, axis, south, north, radius, normal, *, maximum):
    """Exact finite filled-cylinder support, not a distance sampling surrogate."""
    along = _dot(axis, normal)
    transverse = math.sqrt(max(0.0, _dot(normal, normal) - along**2))
    ends = (south * along, north * along)
    return _dot(origin, normal) + (
        max(ends) + radius * transverse if maximum else min(ends) - radius * transverse
    )


def _drum_top(fixed: DrumTier) -> float:
    return cylinder_support(
        (cone_line.X_DRUM, cone_line.Y_DRIVE, bank.G19_BACK_FACE_Z),
        Z,
        fixed.south_mm,
        fixed.north_mm,
        fixed.radius_mm,
        Z,
        maximum=True,
    )


def block_shadow_low_z(
    angle_deg: float, radius_mm: float, *, widen_mm: float = 0.0
) -> float:
    """Least world Z of MHA-DT-21's body over a vertical drum circle.

    Exact: the block is the prism of its plan rectangle (BLOCK_X wide, widened
    by ``widen_mm`` a side, BLOCK_Z deep from the south face) standing across
    the drum axis's height, so over the circle of ``radius_mm`` about the
    drum axis the body's Z is linear in its plan coordinates (u across, t
    north) on a convex polygon, and its minimum lies on a vertex: the
    rectangle's corners or its edges' crossings of the two lines bounding the
    circle's x span.  ``inf`` when no block material stands over the circle.
    """
    origin, axis = tip_pose_frame(angle_deg)
    face = tuple(origin[k] + tip.TIP_BLOCK_SOUTH_FACE * axis[k] for k in range(3))
    # Plan: x = face_x + u * axis_z + t * axis_x; z = face_z - u * axis_x + t * axis_z.
    half = tip.BLOCK_X / 2.0 + widen_mm
    box = ((-half, half), (0.0, tip.BLOCK_Z))
    bounds = (cone_line.X_DRUM - radius_mm, cone_line.X_DRUM + radius_mm)

    def x_of(u, t):
        return face[0] + u * axis[2] + t * axis[0]

    def z_of(u, t):
        return face[2] - u * axis[0] + t * axis[2]

    points = [(u, t) for u in box[0] for t in box[1]]
    for x_line in bounds:
        for u in box[0]:
            if abs(axis[0]) > 1e-12:
                points.append((u, (x_line - face[0] - u * axis[2]) / axis[0]))
        for t in box[1]:
            points.append(((x_line - face[0] - t * axis[0]) / axis[2], t))
    feasible = [
        z_of(u, t)
        for u, t in points
        if box[0][0] - 1e-9 <= u <= box[0][1] + 1e-9
        and box[1][0] - 1e-9 <= t <= box[1][1] + 1e-9
        and bounds[0] - 1e-9 <= x_of(u, t) <= bounds[1] + 1e-9
    ]
    return min(feasible, default=math.inf)


def block_shifted_low_z(angle_deg: float, fixed: DrumTier) -> float:
    """block_shadow_low_z with the block moved by its tolerances in plan: the
    face widened by the lateral sources over the drum tier's largest circle
    grown by the axial sources' plan share (their Z share is booked in
    closure_terms_mm)."""
    _origin, axis = tip_pose_frame(angle_deg)
    across = math.sqrt(max(0.0, 1.0 - axis[2] ** 2))
    return block_shadow_low_z(
        angle_deg,
        fixed.radius_mm
        + fixed.radius_upper_mm
        + sum(BLOCK_AXIAL_TERMS_MM.values()) * across,
        widen_mm=sum(BLOCK_LATERAL_TERMS_MM.values()),
    )


def projection_nominal_mm(tier: str, fixed: DrumTier, angle_deg: float = 0.0) -> float:
    """Nominal world-Z air from ``tier`` to the drum tier at the swing angle."""
    stationary = _drum_top(fixed)
    if tier == BLOCK_TIER:
        return block_shadow_low_z(angle_deg, fixed.radius_mm) - stationary
    shaft_tier = next(t for t in TIERS if t.name == tier)
    origin, axis = tip_pose_frame(angle_deg)
    # A chamfered tier is the convex hull of two cylinders: the full radius
    # from the chamfer's top on, and the south face's radius over the whole
    # length.  Its support is the lesser of theirs.
    chamfer = shaft_tier.south_chamfer_mm
    moving = min(
        cylinder_support(
            origin, axis, south, shaft_tier.north_mm, radius, Z, maximum=False
        )
        for south, radius in (
            (shaft_tier.south_mm + chamfer, shaft_tier.radius_mm),
            (shaft_tier.south_mm, shaft_tier.radius_mm - chamfer),
        )
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
    pivot = -drum.OVERALL_THICKNESS / 2.0
    ends = (
        fixed.south_mm + fixed.south_lower_mm - pivot,
        fixed.north_mm + fixed.north_upper_mm - pivot,
    )
    nz = normal[2]
    angle = math.acos(max(-1.0, min(1.0, nz)))
    lo = math.cos(min(math.pi, angle + theta))
    hi = math.cos(max(0.0, angle - theta))
    candidates = [lo, hi]
    for end in ends:
        stationary = end / math.hypot(radius, end)
        if lo <= stationary <= hi:
            candidates.append(stationary)
    support = max(
        max(end * c for end in ends) + radius * math.sqrt(max(0.0, 1.0 - c * c))
        for c in candidates
    )
    return pivot * nz + support


def _ends(tier: ShaftTier) -> tuple[float, float]:
    return (tier.south_mm + tier.south_lower_mm, tier.north_mm + tier.north_upper_mm)


def _plan_reach_mm(points: list[tuple[float, float]]) -> float:
    return max(math.dist(point, (PIVOT_XYZ[0], PIVOT_XYZ[2])) for point in points)


def pivot_reach_mm(tier: str, angle_deg: float) -> float:
    """The tier's furthest material from the swing pivot, in plan."""
    origin, axis = tip_pose_frame(angle_deg)
    if tier == BLOCK_TIER:
        across = (axis[2], -axis[0])
        half = _BLOCK_HALF_WIDTH_MAX
        return _plan_reach_mm(
            [
                (
                    origin[0] + s * axis[0] + u * across[0],
                    origin[2] + s * axis[2] + u * across[1],
                )
                for s in (
                    tip.TIP_BLOCK_SOUTH_FACE,
                    tip.TIP_BLOCK_SOUTH_FACE + _BLOCK_DEPTH_MAX,
                )
                for u in (-half, half)
            ]
        )
    shaft_tier = next(t for t in TIERS if t.name == tier)
    return (
        _plan_reach_mm(
            [
                (origin[0] + end * axis[0], origin[2] + end * axis[2])
                for end in _ends(shaft_tier)
            ]
        )
        + shaft_tier.radius_mm
        + shaft_tier.radius_upper_mm
    )


def _common_terms(tier: str, fixed: DrumTier, angle_deg: float) -> dict[str, float]:
    """The swing's, the bank's and G19's own closing terms."""
    terms = dict(SWING_TERMS_MM)
    # The feel set leaves T120 up to SWING_SET_FROM_PLACEMENT_MM off its CAD
    # placement; the tier turns with the swing about the pivot.
    set_angle = (
        cone_set_stack.SWING_SET_FROM_PLACEMENT_MM
        / cone_set_stack.pivot_distance_mm(120)
    )
    terms["swing feel set"] = pivot_reach_mm(tier, angle_deg) * set_angle
    # G19 is the free end: its north face carries the accepted full stack
    # deviation as well as the south datum chain.
    terms.update(
        {f"bank {name}": value for name, value in bank.DATUM_CHAIN_STACK.items()}
    )
    terms["bank accepted stack length"] = bank.STACK_L20_ACCEPT_BAND[0]
    manufactured = _tilted_fixed_support(fixed, Z, 0.0)
    nominal = cylinder_support(
        (0.0, 0.0, 0.0),
        Z,
        fixed.south_mm,
        fixed.north_mm,
        fixed.radius_mm,
        Z,
        maximum=True,
    )
    terms["drum tier limits"] = max(0.0, manufactured - nominal)
    contact_span = (
        drum.OVERALL_THICKNESS
        + drum.OVERALL_THICKNESS_BAND[1]
        - 2.0 * DRUM_BORE_END_BREAK_MAX_MM
    )
    if contact_span <= 0.0:
        raise ValueError("drum has no finite running-bore contact span")
    running_cock = math.atan(drum.BORE_DIAMETRAL_CLEARANCE_MM[1] / contact_span)
    terms["G19 cock in its running fit"] = max(
        0.0,
        _tilted_fixed_support(fixed, Z, running_cock) - manufactured,
    ) + max(abs(v) for v in drum.OVERALL_THICKNESS_BAND) * math.sin(running_cock / 2.0)
    return terms


def closure_terms_mm(
    tier: str, fixed: DrumTier, angle_deg: float = 0.0
) -> dict[str, float]:
    """Worst-case closing of the world-Z air, one entry per physical source.

    A source with several projections (a post mounting error moves the post
    along the shaft, moves the line across it and tilts the tier's faces)
    enters once, as the sum of all of them.
    """
    _origin, axis = tip_pose_frame(angle_deg)
    along = abs(axis[2])
    across = math.sqrt(max(0.0, 1.0 - along**2))
    if tier == BLOCK_TIER:
        terms = {name: value * along for name, value in BLOCK_AXIAL_TERMS_MM.items()}
        # Moved in plan along the axis and across it, more of the face can
        # stand over the drum (block_shifted_low_z).  Where the nominal block
        # stands over none, the sweep takes the shifted face as its nominal
        # and this term is 0.
        shifted = block_shifted_low_z(angle_deg, fixed)
        nominal = block_shadow_low_z(angle_deg, fixed.radius_mm)
        terms[BLOCK_PLAN_SHIFT_SOURCE] = (
            max(0.0, nominal - shifted) if math.isfinite(nominal) else 0.0
        )
    else:
        shaft_tier = next(t for t in TIERS if t.name == tier)
        ends = _ends(shaft_tier)
        radius = shaft_tier.radius_mm + shaft_tier.radius_upper_mm
        terms = {name: value * along for name, value in AXIAL_TERMS_MM.items()}
        # The shaft line runs from the post journal to the pivot in the end
        # screw: a plan move of either end across the shaft moves each
        # station by its share of the span, and tilts the faces with the line.
        share = max((end - cone_line.POST_STATION) / _SUPPORT_SPAN for end in ends)
        tilt = radius / _SUPPORT_SPAN
        for name, value in POST_END_TERMS_MM.items():
            terms[name] = terms.get(name, 0.0) + value * (
                abs(1.0 - share) * across + tilt
            )
        for name, value in TIP_END_TERMS_MM.items():
            terms[name] = terms.get(name, 0.0) + value * (share * across + tilt)
        for name, (axial, radial) in shaft_tier.limits.items():
            terms[name] = terms.get(name, 0.0) + axial * along + radial * across
    terms.update(_common_terms(tier, fixed, angle_deg))
    if not all(math.isfinite(value) and value >= 0.0 for value in terms.values()):
        raise ValueError(f"tip air has an invalid closing term: {terms}")
    unclassified = terms.keys() - IN_SERVICE_CLEARANCES - INDEPENDENT_TOLERANCES
    if unclassified:
        raise ValueError(f"tip air has an unclassified source: {sorted(unclassified)}")
    missing = (
        (IN_SERVICE_CLEARANCES | INDEPENDENT_TOLERANCES)
        - _TIER_ONLY_SOURCES
        - terms.keys()
    )
    if missing:
        raise ValueError(f"tip air lost a source: {sorted(missing)}")
    return terms


@dataclass(frozen=True)
class AirStack:
    tier: str
    drum_tier: str
    angle_deg: float
    nominal_mm: float
    terms: dict[str, float]
    arc_mm: float  # the swing between this interval's midpoint and its ends

    def __post_init__(self):
        unclassified = (
            self.terms.keys() - IN_SERVICE_CLEARANCES - INDEPENDENT_TOLERANCES
        )
        if unclassified:
            raise ValueError(
                f"tip air has an unclassified source: {sorted(unclassified)}"
            )

    @property
    def clearances(self) -> dict[str, float]:
        return {k: v for k, v in self.terms.items() if k in IN_SERVICE_CLEARANCES}

    @property
    def tolerance_rss_mm(self) -> float:
        return math.hypot(
            *(v for k, v in self.terms.items() if k in INDEPENDENT_TOLERANCES)
        )

    @property
    def arithmetic_mm(self) -> float:
        return self.nominal_mm - sum(self.terms.values()) - self.arc_mm

    @property
    def statistical_mm(self) -> float:
        return (
            self.nominal_mm
            - sum(self.clearances.values())
            - self.tolerance_rss_mm
            - self.arc_mm
        )

    def closure_mm(self, method: str) -> dict[str, float]:
        if method == "arithmetic":
            return {**self.terms, "continuous p1 interval arc": self.arc_mm}
        return {
            **self.clearances,
            "RSS of the printed tolerances": self.tolerance_rss_mm,
            "continuous p1 interval arc": self.arc_mm,
        }


def full_sweep_proof(*, intervals: int = 400) -> list[dict]:
    """Every tip tier against both drum tiers over closed P1 intervals.

    Each row is one interval's midpoint; the arc term bounds the poses
    between midpoints.  A block row exists only where some block material
    stands over that drum tier (elsewhere the block clears it in plan, even
    shifted by its tolerances).  The whole sweep is worst-case arithmetic
    when that closes everywhere; otherwise "statistical" everywhere: the
    clearances arithmetic plus the RSS of the printed tolerances.  Raises if
    the governing air closes anywhere.
    """
    if type(intervals) is not int or intervals < 1:
        raise ValueError("tip swing proof requires at least one closed interval")
    lower, upper = P1_SWEEP_DEG
    width = (upper - lower) / intervals
    half_rad = abs(math.radians(width)) / 2.0
    stacks = []
    for index in range(intervals):
        angle = lower + (index + 0.5) * width
        for tier in TIER_NAMES:
            for fixed in DRUM_TIERS:
                terms = closure_terms_mm(tier, fixed, angle)
                nominal = projection_nominal_mm(tier, fixed, angle)
                nominal_shadow = math.isfinite(nominal)
                if not nominal_shadow:
                    # Only the block can miss G19 in plan; shifted by its
                    # tolerances it may still stand over it.
                    nominal = block_shifted_low_z(angle, fixed) - _drum_top(fixed)
                    if not math.isfinite(nominal):
                        continue
                stacks.append(
                    (
                        index,
                        nominal_shadow,
                        AirStack(
                            tier,
                            fixed.name,
                            angle,
                            nominal,
                            terms,
                            pivot_reach_mm(tier, angle) * half_rad,
                        ),
                    )
                )
    method = (
        "arithmetic"
        if all(s.arithmetic_mm > 0.0 for _, _, s in stacks)
        else "statistical"
    )
    rows = []
    for index, nominal_shadow, s in stacks:
        air = s.arithmetic_mm if method == "arithmetic" else s.statistical_mm
        if not math.isfinite(air) or air <= 0.0:
            raise ValueError(
                f"cone tip {s.tier} can reach G19 at P1 {s.angle_deg:.3f} deg: "
                f"{s.drum_tier} nominal {s.nominal_mm:.3f}, arithmetic "
                f"{s.arithmetic_mm:.3f}, statistical {s.statistical_mm:.3f}: {s.terms}"
            )
        rows.append(
            {
                "tier": s.tier,
                "drum_tier": s.drum_tier,
                "angle_deg": s.angle_deg,
                "angle_interval_deg": (
                    lower + index * width,
                    lower + (index + 1) * width,
                ),
                "normal": Z,
                "nominal_mm": s.nominal_mm,
                "nominal_shadow": nominal_shadow,
                "method": method,
                "arithmetic_mm": s.arithmetic_mm,
                "statistical_mm": s.statistical_mm,
                "closure_mm": s.closure_mm(method),
                "air_mm": air,
            }
        )
    return rows


def require_air() -> dict[str, float]:
    """The proved least air of each tip tier over the P1 sweep, in mm."""
    rows = full_sweep_proof()
    return {
        name: min(row["air_mm"] for row in rows if row["tier"] == name)
        for name in TIER_NAMES
        if any(row["tier"] == name for row in rows)
    }
