r"""Pure transgear-arm-plate (MHA-PD-19) geometry shared by the plate, its
screws, the knob-shaft stack and the paper-drive assembly.

Book ch. 23 (t157 / p.63; ruling 3): a piece of steel bar screwed across the
MHA-PD-18 arm by two 8-32 oval-head screws.  The book's 1-1/4 in bar is
widened to 1-1/2 in so the outline can stand symmetric about K (the 1-1/4 in
bar centred on K leaves the -X countersink under the wall target).  It
carries the knob shaft's running bore on axis K, a front hub (the thrust
ring's seat) and a rear boss (the cup runs behind it).  Its rear portion is
5 thick where it lies over the arm; below the arm's lower edge it drops the
arm's thickness (7.9375) more to the arm's front face, so the step (the
"notch") wraps that edge, NOTCH_RELIEF clear of it. Two matched stock
dowels locate; screws clamp.

Local frame (same axes as the arm, so the assembly places both with one
rotation about Z):

* origin on the bore axis K, on the MOUNTING face -- the plate's front face
  that seats on the arm's rear face (machine z -116.4625);
* +X and +Y are the arm's +X (toward its square end) and +Y (toward its upper
  tangent edge); the plate's long axis runs along -Y;
* +Z toward the rear (machine +Z): the over-arm section spans z 0..5, the
  section below the arm z -7.9375..5, the front hub z -20.5375..-7.9375 and
  the rear boss z 5..8.5.

Keep drawing-only notes out of this module.
"""

from __future__ import annotations

import math

import pd_transgear_arm_geometry as ARM
import _transgear_arm_plate_locating_interface as LOCATING_PIN
from _gear_quality import reducer_k_setting_diameter_mm
from _printed_tolerance import angular_band_deg, printed_band_mm, printed_deviations

# --- Where the bore sits on the arm (arm frame, mm) -------------------------
# K follows the reducer's physical mounting centre, transformed into the arm
# frame by its pure geometry. The screw midpoint follows that same bore.
BORE_STATION = ARM.KNOB_BORE_STATION
BORE_OFFSET = ARM.KNOB_BORE_OFFSET

# --- Section ----------------------------------------------------------------
END_R = 12.5  # full round about K; both tapers are tangent to it
WIDTH = 38.1  # 1-1/2 in bar, symmetric about K
THICKNESS_OVER_ARM = 5.0  # unchanged nominal; .XX bounds the locator dowel span
THICKNESS_OVER_ARM_PLACES = 2
THICKNESS_OVER_ARM_BAND = printed_band_mm(THICKNESS_OVER_ARM_PLACES)
NOTCH_DEPTH = ARM.THICKNESS  # the section below the arm reaches its front face
THICKNESS_BELOW_ARM = THICKNESS_OVER_ARM + NOTCH_DEPTH  # 12.9375

# Edges along the plate's long axis, in the plate frame (x from K): the
# outline is symmetric about the long axis through K, so the screws' midpoint
# (the arm's PLATE_SCREW_MID_STATION) sits off the plate's centreline.
EDGE_PLUS_X = WIDTH / 2.0
EDGE_MINUS_X = -WIDTH / 2.0
# Each edge runs parallel to the long axis down to its kink, then straight
# to tangency with the end round.  [INFERENCE] kink station from the notch
# crop (row ≈ 790): arm y -20.
KINK_Y = -20.0 - BORE_OFFSET


def arm_upper_edge_y(x: float) -> float:
    """Plate-frame y of the arm's upper tangent edge (the plate's top edge)."""
    return ARM.edge_half_width(x + BORE_STATION) - BORE_OFFSET


def arm_lower_edge_y(x: float) -> float:
    """Plate-frame y of the arm's lower tangent edge."""
    return -ARM.edge_half_width(x + BORE_STATION) - BORE_OFFSET


# The matched locating dowels register the plate; mounting screws clamp ONLY.
# The notch is clearance, not a third locator. A nominal/graded reference
# clearance is not a whole-body certificate inferred from pin-end geometry.
NOTCH_RELIEF = 2.5


def notch_face_y(x: float) -> float:
    """Plate-frame y of the notch face, NOTCH_RELIEF clear of the arm edge."""
    return arm_lower_edge_y(x) - NOTCH_RELIEF


TOP_LEFT = (EDGE_MINUS_X, arm_upper_edge_y(EDGE_MINUS_X))
TOP_RIGHT = (EDGE_PLUS_X, arm_upper_edge_y(EDGE_PLUS_X))
KINK = (EDGE_MINUS_X, KINK_Y)
KINK_RIGHT = (EDGE_PLUS_X, KINK_Y)
_KINK_DIST = math.hypot(*KINK)
_TANGENT_ANGLE = math.atan2(KINK[1], KINK[0]) + math.acos(END_R / _KINK_DIST)
KINK_TANGENT = (END_R * math.cos(_TANGENT_ANGLE), END_R * math.sin(_TANGENT_ANGLE))
KINK_TANGENT_RIGHT = (-KINK_TANGENT[0], KINK_TANGENT[1])
NOTCH_LEFT = (EDGE_MINUS_X, notch_face_y(EDGE_MINUS_X))
NOTCH_RIGHT = (EDGE_PLUS_X, notch_face_y(EDGE_PLUS_X))
if NOTCH_LEFT[1] <= KINK[1]:
    raise AssertionError("the relieved notch face drops below the -X edge's kink")

# --- Knob-shaft bearing: bore, front hub, rear boss (contract 1.10) ---------
BORE_DIA = 6.0
BORE_DIA_LIMITS = (0.0, 0.012)  # 6 H7 over the 6 g6 (-0.004/-0.012) journal
HUB_DIA = 13.2  # .XX
# The hub stands 12.6 proud of the arm's front face, which puts its face (the
# thrust ring's seat) at machine z -137.0 whatever the arm stock (R9-25): the
# mounting face to the hub face is 20.5375 on the 7.9375 arm.  .XXX: the
# chain-plane station (contract §13).
HUB_LENGTH = 12.6
HUB_FACE_TO_MOUNTING = NOTCH_DEPTH + HUB_LENGTH  # 20.5375
# The chain-plane station prints .XXX (contract §13). Keep its existing
# title-block config reader here, not in the richer drawing/annotation spec:
# ARM.BAND_XXX is a hard-coded wall band, not this station's printed grade.
HUB_STATION_PLACES = 3
HUB_FACE_TO_MOUNTING_BAND = printed_band_mm(HUB_STATION_PLACES)
BOSS_DIA = 20.0  # .X
# The boss face's station is authoritative: the knob stack (HUB_TO_BOSS) runs
# to it, so the boss takes whatever the over-arm section leaves.
BOSS_FACE_Z = 8.5
REAR_FACE_Z = THICKNESS_OVER_ARM
BOSS_HEIGHT = BOSS_FACE_Z - REAR_FACE_Z
HUB_TO_BOSS = HUB_FACE_TO_MOUNTING + BOSS_FACE_Z  # 29.0375
HUB_TO_BOSS_BAND = 0.05  # knob float
HUB_FACE_Z = -HUB_FACE_TO_MOUNTING

# Shared matched-pair sites, expressed in this part's actual K-datum frame.
LOCATOR_SITES_MM = tuple(
    (x - BORE_STATION, y - BORE_OFFSET) for x, y in ARM.LOCATOR_SITES_MM
)
LOCATOR_HOLE_DIA_MM = sum(LOCATING_PIN.SLIP_HOLE_LIMITS_MM) / 2.0
LOCATOR_HOLE_BAND_MM = tuple(
    limit - LOCATOR_HOLE_DIA_MM for limit in reversed(LOCATING_PIN.SLIP_HOLE_LIMITS_MM)
)
FRONT_FACE_Z = -NOTCH_DEPTH

# --- Screw holes: 2 x 82° countersinks for the #8 clamp heads ----------------
# Clearance, drilled +0.10/0. Accommodate the published ASME maximum
# under-head fillet: basic shank radius + 15% basic diameter, with room for
# the projected axes. Matched dowels alone locate.
SCREW_HOLE_DIA = 5.8
CSK_DIA = 7.9248  # 0.312 in, the head's Ø at the top of the bevel
CSK_ANGLE_DEG = 82.0
CSK_DIA_PLACES = 1  # ordinary row now retains the true 2 mm floor with the larger clearance
CSK_ANGLE_BAND_DEG = angular_band_deg()
CSK_HALF_ANGLE_LIMITS_RAD = tuple(
    math.radians((CSK_ANGLE_DEG + sign * CSK_ANGLE_BAND_DEG) / 2.0)
    for sign in (-1.0, 1.0)
)
CLAMP_PLATE_PROJECTED_HEIGHT_MM = 7.0  # seated bearing-contact cap; SOURCE mm, not whole crown/native unit proof
CSK_DIA_DEVIATIONS_MM = printed_deviations(CSK_DIA, CSK_DIA_PLACES)
CSK_DIA_LIMITS_MM = tuple(CSK_DIA + deviation for deviation in CSK_DIA_DEVIATIONS_MM)
CSK_DEPTH = (
    (CSK_DIA - SCREW_HOLE_DIA) / 2.0 / math.tan(math.radians(CSK_ANGLE_DEG / 2.0))
)
SCREW_HOLES = tuple(
    (station - BORE_STATION, -BORE_OFFSET) for station in ARM.PLATE_TAP_STATIONS
)

# --- Bands the sheet prints (hard-coded title-block rows, drawing-guidelines.md rule 3 (decimal places carry the tolerance)) ---
BAND_X = ARM.BAND_X
BAND_XX = ARM.BAND_XX
BAND_XXX = ARM.BAND_XXX
# The plate's hole patterns are toleranced from its own knob bore B (= K),
# and the matched pilots go through at the arm's pattern from the pin S:
# K's setting circle about S (MHA-PD-00 VIEW K) carries into every
# B-referenced frame here, so they take that circle, not the arm's zone.
REDUCER_POSITION_DIAMETER = reducer_k_setting_diameter_mm()
REDUCER_POSITION_RADIUS = REDUCER_POSITION_DIAMETER / 2.0
LOCATOR_FULL_CYLINDER_SPAN_MIN_MM = (
    THICKNESS_OVER_ARM - THICKNESS_OVER_ARM_BAND
    - 2.0 * LOCATING_PIN.HOLE_MOUTH_BREAK_AXIAL_MAX_MM
)
LOCATOR_MOUTH_POSITION_RADIUS_MM = REDUCER_POSITION_RADIUS * (
    1.0 + 2.0 * LOCATING_PIN.HOLE_MOUTH_BREAK_AXIAL_MAX_MM
    / LOCATOR_FULL_CYLINDER_SPAN_MIN_MM
)
DRILL_GROWTH = 0.10
WALL_TARGET = ARM.WALL_TARGET
# Actual rounded diameter and angular limits control every cone cut and
# the shortest-stock head seat, not symmetric bands around an unprinted model.
CSK_DIA_BAND = printed_band_mm(CSK_DIA_PLACES)
# The notch face's corner heights print .X: the face only clears the arm's
# lower edge (transgear_hanger_joints.NOTCH_REFERENCE_AIR_WORST_MM).
NOTCH_BAND = BAND_X
# Each cone is coaxial with its hole (the plan's 2X CSK callout), so its axis lies in the
# hole's projected zone. The floor still pays two independent zone radii at
# EVERY height, which bounds that with no coaxial credit.
# Pay the cone rim's vertical lever and its shallowest global generatrix.
_CSK_AXIS_TILT_MAX_RAD = math.atan(REDUCER_POSITION_DIAMETER / CLAMP_PLATE_PROJECTED_HEIGHT_MM)
_CSK_DEPTH_MAX = (
    ((CSK_DIA_LIMITS_MM[1] - SCREW_HOLE_DIA) / 2.0 + REDUCER_POSITION_DIAMETER)
    / math.tan(CSK_HALF_ANGLE_LIMITS_RAD[0] - _CSK_AXIS_TILT_MAX_RAD)
    + CSK_DIA_LIMITS_MM[1] / 2.0 * math.sin(_CSK_AXIS_TILT_MAX_RAD)
)
# Full worst-case wall terms (enforce brief 2026-10-26). The title block's
# R0.25 / C0.25 MAX edge break, on each exposed edge at a wall (the arm's
# constant). Drill run-off of 0.3 deg (#2000 holds the method) wherever a
# hole and the wall's other boundary are made in different setups, over the
# depth from the entry face to the wall: the locating holes and the screw
# holes are drilled through the plate after the outline is milled; the bore
# is reamed on the lathe after the outline and the notch are milled, over its
# whole hub-to-boss length. The hub and boss are turned on the bore axis in
# the bore's own setup (the part's process), so their walls over the bore
# pay no run-off.
OUTLINE_EDGE_BREAK_MAX_MM = ARM.OUTLINE_EDGE_BREAK_MAX_MM
_RUN_OFF = math.tan(math.radians(ARM.DRILL_RUN_OFF_DEG))
# Over the deepest stock the print allows: the .XX thickness and the
# hub-to-boss length at their upper limits.
HOLE_RUN_OFF_MM = (THICKNESS_OVER_ARM + THICKNESS_OVER_ARM_BAND) * _RUN_OFF
BORE_RUN_OFF_MM = (HUB_TO_BOSS + HUB_TO_BOSS_BAND) * _RUN_OFF

_BORE_R_MAX = (BORE_DIA + BORE_DIA_LIMITS[1]) / 2.0
_NOTCH_DISTANCE = (
    BORE_STATION * math.sin(ARM.EDGE_LEAN)
    - BORE_OFFSET * math.cos(ARM.EDGE_LEAN)
    - ARM.PIVOT_END_R
    - NOTCH_RELIEF * math.cos(ARM.EDGE_LEAN)
)
_NEAR_HOLE = min(SCREW_HOLES, key=lambda xy: math.hypot(*xy))
# The nearer side edge to either hole's axis (the -X hole sits nearer its edge).
_HOLE_TO_EDGE = min(SCREW_HOLES[0][0] - EDGE_MINUS_X, EDGE_PLUS_X - SCREW_HOLES[-1][0])
# Each wall pays the edge breaks of the edges exposed at it: both rims at
# the hub's and boss's end faces; the outline's or the notch's edge where a
# hole stands inside it; the screw hole's exit mouth at face A over the bore
# and under the countersink; and the countersink's rim at the rear face,
# which the title block does not exempt, on the ligaments beside it.
WALLS: dict[str, tuple[float, float]] = {
    "hub over the bore": (
        (HUB_DIA - BORE_DIA) / 2.0,
        (HUB_DIA - BAND_XX) / 2.0 - _BORE_R_MAX - 2.0 * OUTLINE_EDGE_BREAK_MAX_MM,
    ),
    "boss over the bore": (
        (BOSS_DIA - BORE_DIA) / 2.0,
        (BOSS_DIA - BAND_X) / 2.0 - _BORE_R_MAX - 2.0 * OUTLINE_EDGE_BREAK_MAX_MM,
    ),
    "bore to end round": (
        END_R - BORE_DIA / 2.0,
        END_R - BAND_X - _BORE_R_MAX - OUTLINE_EDGE_BREAK_MAX_MM - BORE_RUN_OFF_MM,
    ),
    "bore to notch": (
        _NOTCH_DISTANCE - BORE_DIA / 2.0,
        _NOTCH_DISTANCE - NOTCH_BAND - _BORE_R_MAX
        - OUTLINE_EDGE_BREAK_MAX_MM - BORE_RUN_OFF_MM,
    ),
    "bore to screw holes": (
        math.hypot(*_NEAR_HOLE) - BORE_DIA / 2.0 - SCREW_HOLE_DIA / 2.0,
        math.hypot(*_NEAR_HOLE)
        - REDUCER_POSITION_RADIUS
        - _BORE_R_MAX
        - (SCREW_HOLE_DIA + DRILL_GROWTH) / 2.0
        - OUTLINE_EDGE_BREAK_MAX_MM - HOLE_RUN_OFF_MM - BORE_RUN_OFF_MM,
    ),
    "under the countersinks": (
        THICKNESS_OVER_ARM - CSK_DEPTH,
        THICKNESS_OVER_ARM - THICKNESS_OVER_ARM_BAND - _CSK_DEPTH_MAX
        - OUTLINE_EDGE_BREAK_MAX_MM,
    ),
    "countersinks to the side edges": (
        _HOLE_TO_EDGE - CSK_DIA / 2.0,
        _HOLE_TO_EDGE
        - CSK_DIA_LIMITS_MM[1] / 2.0
        - BAND_X
        - REDUCER_POSITION_RADIUS
        - 2.0 * OUTLINE_EDGE_BREAK_MAX_MM,  # the side edge and the cone's rim
    ),
}
for _index, (_x, _y) in enumerate(LOCATOR_SITES_MM, 1):
    _edge_air = min(
        _x - EDGE_MINUS_X, EDGE_PLUS_X - _x,
        (arm_upper_edge_y(_x) - _y) * math.cos(ARM.EDGE_LEAN),
        (_y - notch_face_y(_x)) * math.cos(ARM.EDGE_LEAN),
    )
    WALLS[f"locator {_index} to plate edge/notch"] = (
        _edge_air - LOCATOR_HOLE_DIA_MM / 2.0,
        _edge_air - BAND_X - LOCATOR_MOUTH_POSITION_RADIUS_MM
        - LOCATING_PIN.SLIP_HOLE_LIMITS_MM[1] / 2.0 - LOCATING_PIN.HOLE_MOUTH_BREAK_RADIAL_MAX_MM
        - OUTLINE_EDGE_BREAK_MAX_MM - HOLE_RUN_OFF_MM,
    )
    _csk_air = min(math.hypot(_x - x, _y - y) for x, y in SCREW_HOLES)
    WALLS[f"locator {_index} to countersink"] = (
        _csk_air - (LOCATOR_HOLE_DIA_MM + CSK_DIA) / 2.0,
        _csk_air - LOCATOR_MOUTH_POSITION_RADIUS_MM - REDUCER_POSITION_RADIUS
        - (LOCATING_PIN.SLIP_HOLE_LIMITS_MM[1] + CSK_DIA_LIMITS_MM[1]) / 2.0
        - LOCATING_PIN.HOLE_MOUTH_BREAK_RADIAL_MAX_MM - OUTLINE_EDGE_BREAK_MAX_MM
        - 2.0 * HOLE_RUN_OFF_MM,
    )
    WALLS[f"locator {_index} to running bore"] = (
        math.hypot(_x, _y) - (LOCATOR_HOLE_DIA_MM + BORE_DIA) / 2.0,
        math.hypot(_x, _y) - LOCATOR_MOUTH_POSITION_RADIUS_MM
        - LOCATING_PIN.SLIP_HOLE_LIMITS_MM[1] / 2.0 - _BORE_R_MAX
        - LOCATING_PIN.HOLE_MOUTH_BREAK_RADIAL_MAX_MM - HOLE_RUN_OFF_MM - BORE_RUN_OFF_MM,
    )
for _name, (_nominal, _worst) in WALLS.items():
    if _worst < WALL_TARGET:
        raise AssertionError(f"arm-plate {_name} wall {_worst:.3f} < {WALL_TARGET}")


def section_outline(
    upper_left: tuple[float, float], upper_right: tuple[float, float],
) -> tuple[tuple[tuple[float, float], ...], tuple[float, float]]:
    """The native recipe's closed section outline below an upper edge.

    Returns the polygon through the edge, the +X kink and its tangent, K, the
    -X kink tangent and the -X kink, and the end round's sector angles about
    K, from the -X tangent round the bottom to the +X one. The recipe's
    volume oracle and the mass moments both read this one definition.
    """
    start = math.atan2(KINK_TANGENT[1], KINK_TANGENT[0])
    end = math.atan2(KINK_TANGENT_RIGHT[1], KINK_TANGENT_RIGHT[0])
    if not start < end:
        raise AssertionError("the end round's sector must sweep round the bottom")
    vertices = (
        upper_left, upper_right, KINK_RIGHT, KINK_TANGENT_RIGHT, (0.0, 0.0), KINK_TANGENT, KINK,
    )
    return vertices, (start, end)


def section_area_moments(
    upper_left: tuple[float, float], upper_right: tuple[float, float],
) -> tuple[float, float, float]:
    """Exact area and first moments of one native section outline."""
    vertices, (start, end) = section_outline(upper_left, upper_right)
    polygon = ARM.polygon_area_moments(vertices)
    sector = ARM.sector_area_moments(END_R, start, end)
    return polygon[0] + sector[0], polygon[1] + sector[1], polygon[2] + sector[2]


def nominal_material_properties(*, density_kg_m3: float = 7870.0) -> dict[str, object]:
    """Exact nominal native sections, cuts, mass and local 3D centre of mass."""
    if not math.isfinite(density_kg_m3) or density_kg_m3 <= 0.0:
        raise ValueError("plate material density must be finite and positive")
    volume = 0.0
    moments = [0.0, 0.0, 0.0]

    def add(amount: float, x: float, y: float, z: float) -> None:
        nonlocal volume
        volume += amount
        for axis, coordinate in enumerate((x, y, z)):
            moments[axis] += amount * coordinate

    for left, right, depth, z in (
        (TOP_LEFT, TOP_RIGHT, THICKNESS_OVER_ARM, THICKNESS_OVER_ARM / 2.0),
        (NOTCH_LEFT, NOTCH_RIGHT, NOTCH_DEPTH, -NOTCH_DEPTH / 2.0),
    ):
        area, ax, ay = section_area_moments(left, right)
        add(area * depth, ax / area, ay / area, z)
    add(math.pi * (HUB_DIA / 2.0)**2 * HUB_LENGTH, 0.0, 0.0, HUB_FACE_Z + HUB_LENGTH / 2.0)
    add(math.pi * (BOSS_DIA / 2.0)**2 * BOSS_HEIGHT, 0.0, 0.0, REAR_FACE_Z + BOSS_HEIGHT / 2.0)
    add(-math.pi * (BORE_DIA / 2.0)**2 * HUB_TO_BOSS, 0.0, 0.0, (HUB_FACE_Z + BOSS_FACE_Z) / 2.0)
    radius = SCREW_HOLE_DIA / 2.0
    slope = math.tan(math.radians(CSK_ANGLE_DEG / 2.0))
    cone_volume = math.pi * (radius * slope * CSK_DEPTH**2 + slope**2 * CSK_DEPTH**3 / 3.0)
    cone_z = REAR_FACE_Z - CSK_DEPTH + math.pi * (
        2.0 * radius * slope * CSK_DEPTH**3 / 3.0 + slope**2 * CSK_DEPTH**4 / 4.0
    ) / cone_volume
    for x, y in SCREW_HOLES:
        add(-math.pi * radius**2 * THICKNESS_OVER_ARM, x, y, THICKNESS_OVER_ARM / 2.0)
        add(-cone_volume, x, y, cone_z)
    for x, y in LOCATOR_SITES_MM:
        add(
            -math.pi * (LOCATOR_HOLE_DIA_MM / 2.0)**2 * THICKNESS_OVER_ARM,
            x, y, THICKNESS_OVER_ARM / 2.0,
        )
    return {
        "volume_mm3": volume,
        "mass_kg": volume * density_kg_m3 * 1e-9,
        "centre_of_mass_local_mm": tuple(moment / volume for moment in moments),
        "density_kg_m3": density_kg_m3,
    }
