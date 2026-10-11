r"""Pure transgear-arm (MHA-PD-018) geometry shared by the arm, its plate, its
pivot hardware and the paper-drive assembly.

Book ch. 23 (t157 / t161 / t241): a steel link that swings on the MHA-VN-041
shoulder screw at the pivot P on the support bar, carries the MHA-PD-023 pin of
the disc cluster (pressed into a reamed hole) at S, the MHA-PD-019 plate (and
through it the knob shaft) on two #8-32 taps between them, and the 1/8 latch
pin in its square end.

Local frame (the part's origin and axes; the assembly places it by a pure
rotation about Z and a translation):

* origin on the pivot axis P, on the arm's FRONT face (the face that bears on
  the MHA-PD-020 spacer; machine z FRONT_FACE_MACHINE_Z, -124.4);
* +X along the arm centreline from P toward the square end (machine U);
* +Y across the arm toward its upper tangent edge (machine N = U rotated
  +90 deg about +Z), the edge the plate's top edge sits flush with;
* +Z through the thickness toward the rear face (machine +Z), so the arm
  occupies z 0..THICKNESS and the plate mounts on z = THICKNESS.

Keep drawing-only notes and annotation contracts out of this module so that
sheet-text edits cannot invalidate the assembly recipe.
"""

from __future__ import annotations

import math
from fractions import Fraction

import pd_rack_pinion_spec as DISC
import pd_support_bar_spec as BAR
import vn_transgear_pivot_screw_spec as PIVOT
from _fit_close_running import measured_close_running_clearance_mm
from _gear_quality import reducer_position_diameter_mm
from _printed_tolerance import angular_band_deg
import pd_transgear_pivot_spacer_spec as SPACER
import vn_transgear_arm_plate_locating_pin_spec as LOCATING_PIN

from _hole_spec import THREAD_MAJOR_MM, HoleSpec, blind_cut_dia_mm

MM_PER_IN = 25.4
# The assembly's anchor for the arm: its front face on the spacer.
FRONT_FACE_MACHINE_Z = -124.4

# --- Stock: 5/16 x 1 precision-ground flat bar, faces as supplied ------------
# The arm is cut from McMaster 9517K466 (R9-6, R9-25): its thickness is the
# stock's, ±0.001 in as supplied, not a machined band.  The sheet prints it
# as a reference to the stock; walls, joints and the chain stack read
# THICKNESS_BAND.
STOCK_SKU = "9517K466"
STOCK_THICKNESS_IN = Fraction(5, 16)
THICKNESS = float(STOCK_THICKNESS_IN) * MM_PER_IN  # 7.9375
THICKNESS_BAND = 0.001 * MM_PER_IN  # ±0.0254
# Actual graded seated bearing-contact cap from the reviewed 3D stack.
# SOURCE mm; not a whole-crown cap or native IPS physical-unit proof.
CLAMP_TAP_PROJECTED_HEIGHT_MM = 14.7

# --- Outline: hull of r12.5 about P and r7 about T, cut square through T ----
PIVOT_END_R = 12.5
TIP_END_R = 7.0
# T: the r7 round's centre; the square end face lies on it.  The model
# carries the printed 128.9 (R9-13); the outline's lean and end width derive
# from it.  The sheet prints it .XX (R9-23, TIP_STATION_BAND): the latch
# pin's full diameter must pass the hook's far face, and the hook's fit-up
# set moves the hook in y/z only, so nothing absorbs the station along the
# pin axis.  With the 7/8 pin, the flap's bend and the pin's length grade
# (R9-50, transgear_hanger_joints) the worst is +0.306 at .XX, +0.016 at .X.
TIP_STATION = 128.9
# The straight edges are tangent to both rounds; each leans in toward the
# square end by EDGE_LEAN, its outward normal (sin, cos) of that angle.
EDGE_LEAN = math.asin((PIVOT_END_R - TIP_END_R) / TIP_STATION)
# Tangent point of the upper edge on the pivot round (the lower is its mirror
# in y); the square end truncates both edges at the tip station, short of
# their tangent points on the r7 round.
PIVOT_TANGENT_X = PIVOT_END_R * math.sin(EDGE_LEAN)
PIVOT_TANGENT_Y = PIVOT_END_R * math.cos(EDGE_LEAN)


def edge_half_width(x: float) -> float:
    """The outline's half-width at station x on its straight tangent edges."""
    if not PIVOT_TANGENT_X <= x <= TIP_STATION:
        raise ValueError(f"station {x} is off the straight edges")
    return PIVOT_END_R / math.cos(EDGE_LEAN) - x * math.tan(EDGE_LEAN)


END_HALF_WIDTH = edge_half_width(TIP_STATION)

# --- Pivot at P: matched measured-shoulder running fit ---------------------
# The model is a reference at the stock nominal and clearance midpoint.
# Acceptance is correlated to THIS measured VN041 shoulder, not a universal
# bore zone or the title block's general tolerance.


# The spot face seats the MHA-VN-049 curved disc spring's OD rim (Ø10.744) under
# the MHA-VN-041 head; the spring's float on the shoulder still clears its rim.
SPOT_FACE_DIA = 11.5
SPOT_FACE_DIA_GROWTH = 0.10  # +0.10/0 (drilled row)
# The floor is dimensioned from the FRONT face so the spring's room never
# sees the arm's stock thickness (transgear_hanger_joints.SPRING_ROOM_*):
# 0.70..0.95, inside the spring's catalogue deflection at every corner.
SPOT_FACE_FLOOR_FROM_FRONT = 6.4
SPOT_FACE_FLOOR_BAND = 0.05
SPOT_FACE_DEPTH = THICKNESS - SPOT_FACE_FLOOR_FROM_FRONT

PIVOT_BEARING_LENGTH_MAX = SPOT_FACE_FLOOR_FROM_FRONT + SPOT_FACE_FLOOR_BAND
PIVOT_BORE_TO_FRONT_FACE_ANGLE_DEG = 90.0
PIVOT_BORE_TO_FRONT_FACE_ANGLE_BAND_DEG = angular_band_deg()
PIVOT_SEATED_AXIS_ANGLE_MAX = (
    math.radians(PIVOT_BORE_TO_FRONT_FACE_ANGLE_BAND_DEG)
    + math.atan(SPACER.FRONT_FACE_PERPENDICULARITY / SPACER.FACE_PERPENDICULARITY_ZONE_DIA)
    + math.atan(SPACER.REAR_FACE_PERPENDICULARITY / SPACER.FACE_PERPENDICULARITY_ZONE_DIA)
)
PIVOT_AXIS_BINDING_SWEEP_MAX = PIVOT_BEARING_LENGTH_MAX * math.tan(PIVOT_SEATED_AXIS_ANGLE_MAX)
PIVOT_FIT_CLEARANCE_PLACES = 3


def pivot_running_clearance_mm() -> tuple[float, float]:
    """Pay ordinary squareness before the shared standard free-running gap.

    The arm's printed 90-degree bore-to-front-face angle takes the general
    angular row. Both existing spacer face grades are paid without credit
    for favourable alignment. Round the MIN upward; preserve the shared fit
    class's clearance-window width, so the printed MAX is paid as load play.
    """
    free_min, free_max = measured_close_running_clearance_mm()
    scale = 10**PIVOT_FIT_CLEARANCE_PLACES
    minimum = math.ceil((free_min + PIVOT_AXIS_BINDING_SWEEP_MAX) * scale) / scale
    return minimum, minimum + free_max - free_min


PIVOT_BORE_DIAMETRAL_CLEARANCE = pivot_running_clearance_mm()
if not 3.0 < PIVOT.SHOULDER_DIA <= 6.0:
    raise ValueError("the matched pivot fit requires the shared ISO 3-through-6 mm clearance class")
PIVOT_BORE_DIA = PIVOT.SHOULDER_DIA + sum(PIVOT_BORE_DIAMETRAL_CLEARANCE) / 2.0
PIVOT_BORE_FULL_LIMITS = (
    PIVOT.SHOULDER_DIA + min(PIVOT.SHOULDER_DIA_LIMITS) + PIVOT_BORE_DIAMETRAL_CLEARANCE[0],
    PIVOT.SHOULDER_DIA + max(PIVOT.SHOULDER_DIA_LIMITS) + PIVOT_BORE_DIAMETRAL_CLEARANCE[1],
)


def pivot_bore_limits_mm(measured_shoulder_mm: float) -> tuple[float, float]:
    """Matched-set bore limits; measure the straight shoulder, away from radii."""
    if (not math.isfinite(measured_shoulder_mm)
            or not PIVOT.SHOULDER_DIA + min(PIVOT.SHOULDER_DIA_LIMITS) - 1e-10
            <= measured_shoulder_mm
            <= PIVOT.SHOULDER_DIA + max(PIVOT.SHOULDER_DIA_LIMITS) + 1e-10):
        raise ValueError("measured VN041 shoulder is outside its as-supplied stock limits")
    lower, upper = PIVOT_BORE_DIAMETRAL_CLEARANCE
    return measured_shoulder_mm + lower, measured_shoulder_mm + upper


def require_pivot_running_fit(bore_mm: float, measured_shoulder_mm: float) -> float:
    """Inspect the actual paired bore and shoulder; return diametral clearance."""
    lower, upper = pivot_bore_limits_mm(measured_shoulder_mm)
    if not math.isfinite(bore_mm) or not lower - 1e-10 <= bore_mm <= upper + 1e-10:
        raise ValueError("arm pivot bore does not meet its measured-shoulder running clearance")
    return bore_mm - measured_shoulder_mm

# --- Pin at S: REAM THROUGH, the press for the MHA-PD-023 pin (R9-68) ---------
# The pin (pd_transgear_pin_spec: Ø3.900 0/-0.008, ground) is pressed in from
# the rear until its head seats on the rear face, so the hole is reamed
# square through the ground faces.  The interference (0.010..0.026) is
# asserted in pd_transgear_arm_spec, which imports both: the pin spec imports
# this module.
PIN_STATION = 68.815  # |S - P|, printed .XXX (hole position)
# Preserve the pivot, latch and pressed stud. The rack setting follows the
# feed contact law; only the reducer bearing follows its physical axis datum.
STUD_MACHINE_X = 0.0
ARM_U = (
    (STUD_MACHINE_X - BAR.PIVOT_TAP_X) / PIN_STATION,
    -math.sqrt(1.0 - ((STUD_MACHINE_X - BAR.PIVOT_TAP_X) / PIN_STATION) ** 2),
)
ARM_N = (-ARM_U[1], ARM_U[0])
ARM_ANGLE_DEG = math.degrees(math.atan2(ARM_U[1], ARM_U[0]))
_MESH_ANGLE = math.radians(DISC.MESH_ANGLE_DEG)
# CENTRE_DISTANCE is the physical mounting source, not a profile-shift-derived
# generated centre. Keep this transform shared by the plate and native assembly.
KNOB_BORE_STATION = PIN_STATION + DISC.CENTRE_DISTANCE * (
    math.cos(_MESH_ANGLE) * ARM_U[0] + math.sin(_MESH_ANGLE) * ARM_U[1]
)
KNOB_BORE_OFFSET = DISC.CENTRE_DISTANCE * (
    math.cos(_MESH_ANGLE) * ARM_N[0] + math.sin(_MESH_ANGLE) * ARM_N[1]
)




PIN_BORE_DIA = 3.874
PIN_BORE_DIA_BAND = (0.008, 0.0)  # (upper, lower) deviations, reamed
PIN_BORE_DIA_MAX = round(PIN_BORE_DIA + PIN_BORE_DIA_BAND[0], 6)
PIN_BORE_DIA_MIN = round(PIN_BORE_DIA + PIN_BORE_DIA_BAND[1], 6)
# --- Plate taps: 2 x #8-32 THROUGH; ordinary entry/exit edge breaks ---------
PLATE_SCREW_PITCH = 15.0
PLATE_CENTRELINE_OFFSET = -3.375  # 1-1/4 in plate's centreline from its bore
PLATE_SCREW_MID_STATION = KNOB_BORE_STATION + PLATE_CENTRELINE_OFFSET
PLATE_TAP_STATIONS = (
    PLATE_SCREW_MID_STATION - PLATE_SCREW_PITCH / 2.0,
    PLATE_SCREW_MID_STATION + PLATE_SCREW_PITCH / 2.0,
)

# Matched locating dowels, independent of the mounting screws' clearance.
LOCATOR_PAIR_BASELINE_MM = 13.7
LOCATOR_SITES_MM = (
    (PLATE_SCREW_MID_STATION, LOCATOR_PAIR_BASELINE_MM / 2.0),
    (PLATE_SCREW_MID_STATION, -LOCATOR_PAIR_BASELINE_MM / 2.0),
)
LOCATOR_HOLE_DIA_MM = sum(LOCATING_PIN.PRESS_HOLE_LIMITS_MM) / 2.0
LOCATOR_HOLE_BAND_MM = tuple(
    limit - LOCATOR_HOLE_DIA_MM for limit in reversed(LOCATING_PIN.PRESS_HOLE_LIMITS_MM)
)
LOCATOR_BLIND_DEPTH_MM = LOCATING_PIN.ARM_BLIND_DEPTH_MM
LOCATOR_BLIND_DEPTH_BAND_MM = LOCATING_PIN.ARM_BLIND_DEPTH_TOLERANCE_MM
LOCATOR_PROUD_MM = LOCATING_PIN.PROUD_MM
LOCATOR_PROUD_BAND_MM = LOCATING_PIN.PROUD_TOLERANCE_MM
PLATE_TAP_SPEC = HoleSpec("tapped", "#8-32")
PLATE_TAP_ENTRY_BREAK_MAX_MM = 0.1
PLATE_TAP_EXIT_BREAK_MAX_MM = 0.1
TAP_EDGE_BREAK_ANGLE_DEG = 90.0
PLATE_TAP_MOUTH_DIA_MAX_MM = (
    blind_cut_dia_mm(PLATE_TAP_SPEC)
    + 2.0 * max(PLATE_TAP_ENTRY_BREAK_MAX_MM, PLATE_TAP_EXIT_BREAK_MAX_MM)
)
# Pay the ordinary angular row at its smallest half-angle, not nominal45.
PLATE_TAP_ENTRY_LOSS_MAX_MM = PLATE_TAP_ENTRY_BREAK_MAX_MM / math.tan(
    math.radians((TAP_EDGE_BREAK_ANGLE_DEG - angular_band_deg()) / 2.0)
)
PLATE_TAP_EXIT_LOSS_MAX_MM = PLATE_TAP_EXIT_BREAK_MAX_MM / math.tan(
    math.radians((TAP_EDGE_BREAK_ANGLE_DEG - angular_band_deg()) / 2.0)
)
# ASME B1.1 #8-32 UNC-2B pitch limits; Thread Check standard-inch table p54.
PLATE_TAP_PITCH_DIA_LIMITS_MM = tuple(value * 25.4 for value in (0.1437, 0.1475))

# --- Latch pin: reamed press hole along -X into the square end, flat floor --
PIN_HOLE_DIA = 3.175
# REAM 0/-0.010: the press fit for the 98381A474 dowel (+0.0025/+0.0076 over
# nominal) holds at both limits; .XXX (±0.13) could not hold a press.  The
# band follows the crank seat drive-pin holes' convention (R9-12).
PIN_HOLE_DIA_BAND = (0.0, -0.010)
# The dowel is pressed to the hole's flat floor (R9-12, the MHA-DT-011 / MHA-VN-044
# precedent), so the depth sets the pin's proud length: 22.225 - 8.50 = 13.725.
# R9-50: 8.50 (was 6.05 for the 3/4 pin) keeps the full diameter past the
# latch hook's far face with the flap's bend and the pin's length grade.
PIN_HOLE_DEPTH = 8.50
# The depth prints .XX: the hanger joints judge the pin's full-diameter grip
# at the shallowest hole, and the latch hook's grip on the pin over the proud
# range, both at this band.
PIN_HOLE_DEPTH_BAND = 0.51
PIN_HOLE_Z = THICKNESS / 2.0  # mid-thickness, on y = 0
# The latch pin's axis in the machine frame; the hook's hole is drilled on it.
PIN_MACHINE_Z = FRONT_FACE_MACHINE_Z + PIN_HOLE_Z  # -120.43125

# --- Bands the sheet prints (hard-coded title-block rows, policy rule 12) ---
BAND_X = 0.8
BAND_XX = 0.51
BAND_XXX = 0.13
LATCH_PIN_HEIGHT_BAND = 0.065  # ordinary end-face latch-hole height, per side
REDUCER_POSITION_DIAMETER = reducer_position_diameter_mm()
REDUCER_POSITION_RADIUS = REDUCER_POSITION_DIAMETER / 2.0
LOCATOR_FULL_CYLINDER_SPAN_MIN_MM = (
    LOCATOR_BLIND_DEPTH_MM - LOCATOR_BLIND_DEPTH_BAND_MM
    - LOCATING_PIN.HOLE_MOUTH_BREAK_AXIAL_MAX_MM
)
LOCATOR_MOUTH_POSITION_RADIUS_MM = REDUCER_POSITION_RADIUS * (
    1.0 + 2.0 * LOCATING_PIN.HOLE_MOUTH_BREAK_AXIAL_MAX_MM
    / LOCATOR_FULL_CYLINDER_SPAN_MIN_MM
)
WALL_TARGET = 2.0
# The tip station's printed band (R9-23; see TIP_STATION).
TIP_STATION_BAND = BAND_XX



def _tap_major(spec: HoleSpec) -> float:
    return THREAD_MAJOR_MM[spec.size]


# Walls: nominal and worst at the printed bands (contract §8).  The hull
# radii and the tip station retain their printed outline bands. The reducer
# bores/taps use the drawn circular position radius, not a coordinate box;
# tap majors carry a 0.025 radial allowance for the tap's oversize.
_TAP_OVERSIZE_R = 0.025
WALLS: dict[str, tuple[float, float]] = {
    "pivot bore to end round": (
        PIVOT_END_R - PIVOT_BORE_DIA / 2.0,
        PIVOT_END_R - BAND_X - PIVOT_BORE_FULL_LIMITS[1] / 2.0,
    ),
    "pivot bore to spot face": (
        (SPOT_FACE_DIA - PIVOT_BORE_DIA) / 2.0,
        # conservative, as the contract: the counterbore's growth is charged
        # against the ring too (it only widens it in fact)
        (SPOT_FACE_DIA - SPOT_FACE_DIA_GROWTH - PIVOT_BORE_FULL_LIMITS[1]) / 2.0,
    ),
    "spot-face floor": (
        SPOT_FACE_FLOOR_FROM_FRONT,
        SPOT_FACE_FLOOR_FROM_FRONT - SPOT_FACE_FLOOR_BAND,
    ),
    "spot face to end round": (
        PIVOT_END_R - SPOT_FACE_DIA / 2.0,
        PIVOT_END_R - BAND_X - (SPOT_FACE_DIA + SPOT_FACE_DIA_GROWTH) / 2.0,
    ),
    "pin bore to edges": (
        edge_half_width(PIN_STATION) - PIN_BORE_DIA / 2.0,
        edge_half_width(PIN_STATION)
        - BAND_X
        - REDUCER_POSITION_RADIUS
        - PIN_BORE_DIA_MAX / 2.0,
    ),
    "plate taps to edges": (
        edge_half_width(PLATE_TAP_STATIONS[1]) - _tap_major(PLATE_TAP_SPEC) / 2.0,
        edge_half_width(PLATE_TAP_STATIONS[1])
        - BAND_X
        - REDUCER_POSITION_RADIUS
        - _tap_major(PLATE_TAP_SPEC) / 2.0
        - _TAP_OVERSIZE_R,
    ),
    # The hole's height is dimensioned from the FRONT face, so thin stock
    # takes its whole band off the rear ligament.
    "pin hole to faces": (
        (THICKNESS - PIN_HOLE_DIA) / 2.0,
        (THICKNESS - PIN_HOLE_DIA - PIN_HOLE_DIA_BAND[0]) / 2.0
        - THICKNESS_BAND
        - LATCH_PIN_HEIGHT_BAND,
    ),
    "pin hole to end-face edges": (
        TIP_END_R - PIN_HOLE_DIA / 2.0,
        TIP_END_R
        - BAND_X
        - (PIN_HOLE_DIA + PIN_HOLE_DIA_BAND[0]) / 2.0
        - LATCH_PIN_HEIGHT_BAND,
    ),
    # The latch pin's hole, at its deepest on the shortest tip station, to
    # the pin bore's far side.
    "latch-pin hole floor to pin bore": (
        TIP_STATION - PIN_HOLE_DEPTH - PIN_STATION - PIN_BORE_DIA / 2.0,
        TIP_STATION
        - TIP_STATION_BAND
        - PIN_HOLE_DEPTH
        - PIN_HOLE_DEPTH_BAND
        - PIN_STATION
        - REDUCER_POSITION_RADIUS
        - PIN_BORE_DIA_MAX / 2.0,
    ),
}
for _index, (_x, _y) in enumerate(LOCATOR_SITES_MM, 1):
    _edge_air = PIVOT_END_R - _x * math.sin(EDGE_LEAN) - abs(_y) * math.cos(EDGE_LEAN)
    WALLS[f"locator {_index} to arm edge"] = (
        _edge_air - LOCATOR_HOLE_DIA_MM / 2.0,
        _edge_air - BAND_X - LOCATOR_MOUTH_POSITION_RADIUS_MM
        - LOCATING_PIN.PRESS_HOLE_LIMITS_MM[1] / 2.0 - LOCATING_PIN.HOLE_MOUTH_BREAK_RADIAL_MAX_MM,
    )
    _tap_air = min(math.hypot(_x - station, _y) for station in PLATE_TAP_STATIONS)
    WALLS[f"locator {_index} to tap mouth"] = (
        _tap_air - (LOCATOR_HOLE_DIA_MM + PLATE_TAP_MOUTH_DIA_MAX_MM) / 2.0,
        _tap_air - LOCATOR_MOUTH_POSITION_RADIUS_MM - REDUCER_POSITION_RADIUS
        - (LOCATING_PIN.PRESS_HOLE_LIMITS_MM[1] + PLATE_TAP_MOUTH_DIA_MAX_MM) / 2.0
        - LOCATING_PIN.HOLE_MOUTH_BREAK_RADIAL_MAX_MM,
    )
WALLS["locator blind floor"] = (
    THICKNESS - LOCATOR_BLIND_DEPTH_MM,
    THICKNESS - THICKNESS_BAND - LOCATOR_BLIND_DEPTH_MM - LOCATOR_BLIND_DEPTH_BAND_MM,
)
for _name, (_nominal, _worst) in WALLS.items():
    if _worst < WALL_TARGET:
        raise AssertionError(f"arm {_name} wall {_worst:.3f} < {WALL_TARGET}")

def polygon_area_moments(points: tuple[tuple[float, float], ...]) -> tuple[float, float, float]:
    """Exact signed-polygon area and first moments, returned with positive area."""
    area = mx = my = 0.0
    for first, last in zip(points, points[1:] + points[:1], strict=True):
        cross = first[0] * last[1] - last[0] * first[1]
        area += cross / 2.0
        mx += (first[0] + last[0]) * cross / 6.0
        my += (first[1] + last[1]) * cross / 6.0
    sign = 1.0 if area > 0.0 else -1.0
    return sign * area, sign * mx, sign * my


def sector_area_moments(radius: float, start: float, end: float) -> tuple[float, float, float]:
    """Exact circular-sector area and first moments about the circle centre."""
    return (
        radius**2 * (end - start) / 2.0,
        radius**3 * (math.sin(end) - math.sin(start)) / 3.0,
        radius**3 * (math.cos(start) - math.cos(end)) / 3.0,
    )


def nominal_material_properties(*, density_kg_m3: float = 7870.0) -> dict[str, object]:
    """Analytic native-recipe nominal volume, mass and full 3D local CG.

    Density is an explicit engineering material input, not a stock-lot
    certificate. The paired pivot is the nominal reference realization;
    a physical force counterexample must supply its actual accepted bore.
    """
    return material_properties(PIVOT_BORE_DIA, density_kg_m3=density_kg_m3)


def material_properties(pivot_bore_mm: float, *, density_kg_m3: float = 7870.0) -> dict[str, object]:
    """Material properties of an accepted pivot-bore realization of the arm."""
    if (not math.isfinite(pivot_bore_mm)
            or not PIVOT_BORE_FULL_LIMITS[0] <= pivot_bore_mm <= PIVOT_BORE_FULL_LIMITS[1]
            or not math.isfinite(density_kg_m3) or density_kg_m3 <= 0.0):
        raise ValueError("arm material properties require an accepted bore and positive density")
    polygon = polygon_area_moments((
        (0.0, 0.0), (PIVOT_TANGENT_X, -PIVOT_TANGENT_Y),
        (TIP_STATION, -END_HALF_WIDTH), (TIP_STATION, END_HALF_WIDTH),
        (PIVOT_TANGENT_X, PIVOT_TANGENT_Y),
    ))
    sector = sector_area_moments(
        PIVOT_END_R, math.pi / 2.0 - EDGE_LEAN, 3.0 * math.pi / 2.0 + EDGE_LEAN,
    )
    area, ax, ay = (polygon[i] + sector[i] for i in range(3))
    volume = area * THICKNESS
    moments = [ax * THICKNESS, ay * THICKNESS, volume * THICKNESS / 2.0]

    def remove(amount: float, x: float, y: float, z: float) -> None:
        nonlocal volume
        volume -= amount
        for axis, coordinate in enumerate((x, y, z)):
            moments[axis] -= amount * coordinate

    bore_radius = pivot_bore_mm / 2.0
    remove(math.pi * bore_radius**2 * THICKNESS, 0.0, 0.0, THICKNESS / 2.0)
    remove(math.pi * (PIN_BORE_DIA / 2.0)**2 * THICKNESS, PIN_STATION, 0.0, THICKNESS / 2.0)
    drill_radius = blind_cut_dia_mm(PLATE_TAP_SPEC) / 2.0
    leg = PLATE_TAP_ENTRY_BREAK_MAX_MM
    tap_volume = math.pi * drill_radius**2 * THICKNESS
    rear_volume = math.pi * leg**2 * (drill_radius + leg / 3.0)
    front_leg = PLATE_TAP_EXIT_BREAK_MAX_MM
    front_volume = math.pi * front_leg**2 * (drill_radius + front_leg / 3.0)
    rear_z = THICKNESS - leg * (4.0 * drill_radius + leg) / (12.0 * (drill_radius + leg / 3.0))
    front_z = front_leg * (4.0 * drill_radius + front_leg) / (12.0 * (drill_radius + front_leg / 3.0))
    for station in PLATE_TAP_STATIONS:
        remove(tap_volume, station, 0.0, THICKNESS / 2.0)
        remove(rear_volume, station, 0.0, rear_z)
        remove(front_volume, station, 0.0, front_z)
    remove(
        math.pi * ((SPOT_FACE_DIA / 2.0)**2 - bore_radius**2) * SPOT_FACE_DEPTH,
        0.0, 0.0, (SPOT_FACE_FLOOR_FROM_FRONT + THICKNESS) / 2.0,
    )
    remove(
        math.pi * (PIN_HOLE_DIA / 2.0)**2 * PIN_HOLE_DEPTH,
        TIP_STATION - PIN_HOLE_DEPTH / 2.0, 0.0, PIN_HOLE_Z,
    )
    for x, y in LOCATOR_SITES_MM:
        remove(
            math.pi * (LOCATOR_HOLE_DIA_MM / 2.0)**2 * LOCATOR_BLIND_DEPTH_MM,
            x, y, THICKNESS - LOCATOR_BLIND_DEPTH_MM / 2.0,
        )
    return {
        "volume_mm3": volume,
        "mass_kg": volume * density_kg_m3 * 1e-9,
        "centre_of_mass_local_mm": tuple(moment / volume for moment in moments),
        "density_kg_m3": density_kg_m3,
    }
