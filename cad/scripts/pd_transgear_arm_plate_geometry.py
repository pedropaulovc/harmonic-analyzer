r"""Pure transgear-arm-plate (MHA-PD-19) geometry shared by the plate, its
screws, the knob-shaft stack and the paper-drive assembly.

Book ch. 23 (t157 / p.63; ruling 3): a piece of steel bar screwed across the
MHA-PD-18 arm by two 8-32 oval-head screws.  The book's 1-1/4 in bar is
widened to 1-1/2 in so the outline can stand symmetric about K (the 1-1/4 in
bar centred on K leaves the -X countersink under the wall target).  Since
#2425 (owner ruling 2026-11-20 (Pedro)) it is a flat .197 plate: the knob
shaft's running bore, the thrust ring's hub face and the cup's thrust face
are the MHA-PD-28 bush's (``pd_transgear_knob_bush_geometry``), pressed
into the plate's Ø.4385 reamed hole on axis K from face A, its shoulder seated
on face A.  Two matched stock dowels locate; screws clamp.

Local frame (same axes as the arm, so the assembly places both with one
rotation about Z):

* origin on the press-hole axis K, on face A -- the plate's front face
  that seats on the arm's rear face (machine z -114.888);
* +X and +Y are the arm's +X (toward its square end) and +Y (toward its upper
  tangent edge); the plate's long axis runs along -Y;
* +Z toward the rear (machine +Z): the plate spans z 0..5.0038.

Decimal inch (#290): the plate's own nominals are the exact millimetres of
their printed inch values; the outline edges and hole sites follow the
MHA-PD-18 arm's mm geometry and print rounded, their walls judged at the
printed limits' reach (``printed_reach_mm``), as the arm's do.

Keep drawing-only notes out of this module.
"""

from __future__ import annotations

import math

import _config
import pd_transgear_arm_geometry as ARM
import pd_transgear_knob_bush_geometry as BUSH
import _transgear_arm_plate_locating_interface as LOCATING_PIN
from _gear_quality import reducer_k_setting_diameter_mm
from _package_units import drawing_unit
from _printed_tolerance import (
    angular_band_deg,
    drilled_oversize_mm,
    printed_band_mm,
    printed_deviations,
)

UNIT = drawing_unit("parts/pd-transgear-arm-plate", _config.parts("pd-transgear-arm-plate"))


def printed_reach_mm(model: float, places: int) -> float:
    """Farthest an accepted part may stand from the mm ``model``, either way,
    when the sheet prints it rounded to ``places`` inch places under the title
    block's row."""
    return max(abs(d) for d in printed_deviations(model, places, unit=UNIT))


# --- Where K sits on the arm (arm frame, mm) --------------------------------
# K follows the reducer's physical mounting centre, transformed into the arm
# frame by its pure geometry. The screw midpoint follows that same axis.
BORE_STATION = ARM.KNOB_BORE_STATION
BORE_OFFSET = ARM.KNOB_BORE_OFFSET

# --- Section ----------------------------------------------------------------
END_R = 12.446  # R.49, full round about K; both tapers are tangent to it
WIDTH = 38.1  # 1-1/2 in bar, symmetric about K
# .XXX, the whole plate's thickness: it bounds the locator dowel span, the
# screw engagement and the press length the bush grips.
THICKNESS_OVER_ARM = 5.0038  # .197
THICKNESS_OVER_ARM_PLACES = 3
THICKNESS_OVER_ARM_BAND = printed_band_mm(THICKNESS_OVER_ARM_PLACES, unit=UNIT)

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


TOP_LEFT = (EDGE_MINUS_X, arm_upper_edge_y(EDGE_MINUS_X))
TOP_RIGHT = (EDGE_PLUS_X, arm_upper_edge_y(EDGE_PLUS_X))
KINK = (EDGE_MINUS_X, KINK_Y)
KINK_RIGHT = (EDGE_PLUS_X, KINK_Y)
_KINK_DIST = math.hypot(*KINK)
_TANGENT_ANGLE = math.atan2(KINK[1], KINK[0]) + math.acos(END_R / _KINK_DIST)
KINK_TANGENT = (END_R * math.cos(_TANGENT_ANGLE), END_R * math.sin(_TANGENT_ANGLE))
KINK_TANGENT_RIGHT = (-KINK_TANGENT[0], KINK_TANGENT[1])

# --- Press hole for the MHA-PD-28 knob bush on K ----------------------------
# The bush carries the knob shaft's running bore, the thrust ring's hub face
# and the cup's thrust face; the plate only grips it.  The hole is cut by
# the .4385 set reamer and prints that size with no band; the bush's press
# step is turned to it as measured (pd_transgear_knob_bush_geometry), both
# modelled line to line as the repo's other presses are.  ANALYSIS limits
# (lower, upper) deviations, what the reamer is modelled to cut:
# +.0000/+.0005.
PRESS_HOLE_DIA = BUSH.PRESS_DIA
PRESS_HOLE_LIMITS = (min(BUSH.PRESS_HOLE_BAND), max(BUSH.PRESS_HOLE_BAND))
PRESS_HOLE_PLACES = 4
# The bush's traveler leaves a slip pilot on its press step's rear end
# (BUSH.PILOT_LENGTH_MAX_MM): with the shoulder seated on face A it lies
# wholly behind the thickest plate, so the whole hole grips the press.
_STUB_BEHIND_PLATE_MIN_MM = (
    BUSH.STUB_LENGTH
    - BUSH.LENGTH_BAND
    - BUSH.HUB_LENGTH_BAND
    - THICKNESS_OVER_ARM
    - THICKNESS_OVER_ARM_BAND
)
if BUSH.PILOT_LENGTH_MAX_MM > _STUB_BEHIND_PLATE_MIN_MM:
    raise AssertionError("MHA-PD-28's pilot reaches into MHA-PD-19's press hole")
# Face A's mouth is chamfered .015 X 45° (#2425): the lead-in for pressing
# MHA-PD-28 from face A, and room for the bush's shoulder-root radius so the
# shoulder seats flat on face A.  The bush geometry owns its size and limits
# (it asserts the root clearance); the rear mouth keeps the title block's
# break.
PRESS_HOLE_CHAMFER = BUSH.PRESS_HOLE_MOUTH_CHAMFER
PRESS_HOLE_CHAMFER_PLACES = BUSH.PRESS_HOLE_MOUTH_CHAMFER_PLACES
PRESS_HOLE_CHAMFER_LIMITS = (
    BUSH.PRESS_HOLE_MOUTH_CHAMFER_MIN, BUSH.PRESS_HOLE_MOUTH_CHAMFER_MAX,
)
if max(PRESS_HOLE_CHAMFER_LIMITS) < ARM.OUTLINE_EDGE_BREAK_MAX_MM:
    raise AssertionError("the face-A chamfer, not the title-block break, must govern the mouth")
PRESS_HOLE_CHAMFER_VOLUME_MM3 = math.pi * PRESS_HOLE_CHAMFER**2 * (
    PRESS_HOLE_DIA / 2.0 + PRESS_HOLE_CHAMFER / 3.0
)
REAR_FACE_Z = THICKNESS_OVER_ARM

# The matched locating dowels register the plate; mounting screws clamp ONLY.
# A nominal/graded reference clearance is not a whole-body certificate
# inferred from pin-end geometry.  Shared matched-pair sites, expressed in
# this part's actual K-datum frame.
LOCATOR_SITES_MM = tuple(
    (x - BORE_STATION, y - BORE_OFFSET) for x, y in ARM.LOCATOR_SITES_MM
)
# The .1260 set reamer's size, printed with no band (the dowel slides in,
# no shake); the band is the ANALYSIS band the walls are judged at.
LOCATOR_HOLE_DIA_MM = min(LOCATING_PIN.SLIP_HOLE_LIMITS_MM)  # .1260
LOCATOR_HOLE_PLACES = 4
LOCATOR_HOLE_BAND_MM = tuple(
    limit - LOCATOR_HOLE_DIA_MM for limit in reversed(LOCATING_PIN.SLIP_HOLE_LIMITS_MM)
)

# --- Screw holes: 2 x 82° countersinks for the #8 clamp heads ----------------
# Clearance, a #1 drill (.228) +.004/0. Accommodate the published ASME maximum
# under-head fillet: basic shank radius + 15% basic diameter, with room for
# the projected axes. Matched dowels alone locate.
SCREW_HOLE_DIA = 5.7912  # .228
SCREW_HOLE_PLACES = 3
CSK_DIA = 7.9248  # .312, the head's Ø at the top of the bevel
CSK_ANGLE_DEG = 82.0
CSK_DIA_PLACES = 3
CSK_ANGLE_BAND_DEG = angular_band_deg(unit=UNIT)
CSK_HALF_ANGLE_LIMITS_RAD = tuple(
    math.radians((CSK_ANGLE_DEG + sign * CSK_ANGLE_BAND_DEG) / 2.0)
    for sign in (-1.0, 1.0)
)
CSK_DIA_DEVIATIONS_MM = printed_deviations(CSK_DIA, CSK_DIA_PLACES, unit=UNIT)
CSK_DIA_LIMITS_MM = tuple(CSK_DIA + deviation for deviation in CSK_DIA_DEVIATIONS_MM)
CSK_DEPTH = (
    (CSK_DIA - SCREW_HOLE_DIA) / 2.0 / math.tan(math.radians(CSK_ANGLE_DEG / 2.0))
)
SCREW_HOLES = tuple(
    (station - BORE_STATION, -BORE_OFFSET) for station in ARM.PLATE_TAP_STATIONS
)

# --- Bands the sheet prints (title-block rows, drawing-guidelines.md rule 3 (decimal places carry the tolerance)) ---
BAND_XX = printed_band_mm(2, unit=UNIT)
BAND_XXX = printed_band_mm(3, unit=UNIT)
# The outline prints .XX (rule 3): the .X row's +/-.1 is wider than every
# wall it bounds.  Its nominals follow the arm's mm edges, so each is judged
# at its printed limits' reach.
OUTLINE_PLACES = 2
OUTLINE_BAND = max(
    printed_reach_mm(abs(value), OUTLINE_PLACES)
    for value in (END_R, WIDTH / 2.0, TOP_LEFT[1], TOP_RIGHT[1], KINK[1])
)
# The plate's hole patterns are toleranced from its own press hole B (= K),
# and the matched pilots go through at the arm's pattern from the pin S:
# K's setting circle about S (MHA-PD-00 VIEW K) carries into every
# B-referenced frame here, so they take that circle, not the arm's zone.
# It reads stock_form_quality.reducer_k_setting_diameter_mm (Ø.008 since
# owner ruling 2026-11-08 (Pedro), #2144 item 5.3), not the S-K set band.
REDUCER_POSITION_DIAMETER = reducer_k_setting_diameter_mm()
REDUCER_POSITION_RADIUS = REDUCER_POSITION_DIAMETER / 2.0
# The plate's slip-hole mouths take the title block's edge break (its
# axial and radial legs): the slip fit only locates, and every stack the
# mouths touch -- the full cylinder the frame holds, the mouth's position
# radius and the walls below -- still holds at it, so the sheet prints no
# tighter break (fan-out L2, delegated ruling 2026-11-07 (Main)).  The
# arm's press holes keep the interface's tighter break for dowel grip.
LOCATOR_MOUTH_BREAK_MAX_MM = ARM.OUTLINE_EDGE_BREAK_MAX_MM
LOCATOR_FULL_CYLINDER_SPAN_MIN_MM = (
    THICKNESS_OVER_ARM - THICKNESS_OVER_ARM_BAND - 2.0 * LOCATOR_MOUTH_BREAK_MAX_MM
)
LOCATOR_MOUTH_POSITION_RADIUS_MM = REDUCER_POSITION_RADIUS * (
    1.0 + 2.0 * LOCATOR_MOUTH_BREAK_MAX_MM / LOCATOR_FULL_CYLINDER_SPAN_MIN_MM
)
DRILL_GROWTH = drilled_oversize_mm(unit=UNIT)
WALL_TARGET = ARM.WALL_TARGET
# Actual rounded diameter and angular limits control every cone cut and
# the shortest-stock head seat, not symmetric bands around an unprinted model.
CSK_DIA_BAND = printed_band_mm(CSK_DIA_PLACES, unit=UNIT)
# Each screw hole prints a plain position frame at the drilled-hole location
# row (drawing-guidelines.md shop table: ±.005 from its datum, Ø.014 as a
# diametral zone): the arm's plate taps are spotted through these holes at
# assembly with the plate doweled on, so the holes are the joint's master
# and need no reamed-pattern zone (fan-out Q2-A and L1; rule 26 bars the
# projected-zone modifier; delegated ruling 2026-11-07 (Main), no
# precedent; owner review #2144; pending owner confirmation).  The frame
# holds the hole's axis inside the zone over the drilled cylinder, face A to
# the cone's floor; the drill's own run-off (ARM.DRILL_RUN_OFF_DEG, #2000
# holds the method) bounds its tilt, so past the floor the axis runs on at
# that tilt over the shortest such cylinder (the thinnest stock less the
# deepest cone).  Each cone is coaxial with its hole (one hole callout
# carries both); the floor pays two independent such radii (cone and hole)
# at the deepest stock's rear face, with no coaxial credit, and the cone
# rim's vertical lever and its shallowest global generatrix.  The deepest
# cone depends on the axis radius, the radius on the cylinder that cone
# leaves: both settle together.
SCREW_HOLE_POSITION_DIAMETER_MM = 0.3556  # Ø.014
SCREW_HOLE_POSITION_RADIUS_MM = SCREW_HOLE_POSITION_DIAMETER_MM / 2.0
_CSK_AXIS_TILT_MAX_RAD = math.radians(ARM.DRILL_RUN_OFF_DEG)
_THINNEST_STOCK_MM = THICKNESS_OVER_ARM - THICKNESS_OVER_ARM_BAND
_DEEPEST_STOCK_MM = THICKNESS_OVER_ARM + THICKNESS_OVER_ARM_BAND


def _axis_radius_at(height_mm: float, zone_length_mm: float) -> float:
    """Axis offset bound at ``height_mm`` above face A for a zone held over
    ``zone_length_mm`` from face A."""
    return SCREW_HOLE_POSITION_RADIUS_MM + max(0.0, height_mm - zone_length_mm) * math.tan(
        _CSK_AXIS_TILT_MAX_RAD
    )


def _deepest_cone_mm(zone_length_mm: float) -> float:
    radius = _axis_radius_at(_DEEPEST_STOCK_MM, zone_length_mm)
    return (
        ((CSK_DIA_LIMITS_MM[1] - SCREW_HOLE_DIA) / 2.0 + 2.0 * radius)
        / math.tan(CSK_HALF_ANGLE_LIMITS_RAD[0] - _CSK_AXIS_TILT_MAX_RAD)
        + CSK_DIA_LIMITS_MM[1] / 2.0 * math.sin(_CSK_AXIS_TILT_MAX_RAD)
    )


_zone_length = _THINNEST_STOCK_MM - CSK_DEPTH
for _pass in range(50):
    _next = _THINNEST_STOCK_MM - _deepest_cone_mm(_zone_length)
    if not _next > 0.0:
        raise AssertionError("the deepest cone leaves no drilled cylinder for the frame")
    if abs(_next - _zone_length) < 1e-12:
        break
    _zone_length = _next
else:
    raise AssertionError("the screw holes' zone length and cone depth did not settle")
SCREW_HOLE_ZONE_LENGTH_MIN_MM = _next


def screw_axis_radius_mm(height_mm: float) -> float:
    """Bound on a screw hole's (or its cone's) axis offset from true position
    at ``height_mm`` above face A, inside the plate."""
    if height_mm < 0.0:
        raise ValueError("inside the plate is above face A")
    return _axis_radius_at(height_mm, SCREW_HOLE_ZONE_LENGTH_MIN_MM)


SCREW_AXIS_RADIUS_IN_PLATE_MM = screw_axis_radius_mm(_DEEPEST_STOCK_MM)
_CSK_DEPTH_MAX = _deepest_cone_mm(SCREW_HOLE_ZONE_LENGTH_MIN_MM)
# Full worst-case wall terms (enforce brief 2026-10-26). The title block's
# R0.25 / C0.25 MAX edge break, on each exposed edge at a wall (the arm's
# constant). Drill run-off of 0.3 deg (#2000 holds the method) wherever a
# hole and the wall's other boundary are made in different setups, over the
# depth from the entry face to the wall: the press hole, the locating holes
# and the screw holes are each drilled (and the press hole reamed) through
# the plate after the outline is milled.
OUTLINE_EDGE_BREAK_MAX_MM = ARM.OUTLINE_EDGE_BREAK_MAX_MM
_RUN_OFF = math.tan(math.radians(ARM.DRILL_RUN_OFF_DEG))
# Over the deepest stock the print allows: the .XXX thickness at its upper
# limit.
HOLE_RUN_OFF_MM = (THICKNESS_OVER_ARM + THICKNESS_OVER_ARM_BAND) * _RUN_OFF

_PRESS_R_MAX = (PRESS_HOLE_DIA + PRESS_HOLE_LIMITS[1]) / 2.0
_NEAR_HOLE = min(SCREW_HOLES, key=lambda xy: math.hypot(*xy))
# The nearer side edge to either hole's axis (the -X hole sits nearer its edge).
_HOLE_TO_EDGE = min(SCREW_HOLES[0][0] - EDGE_MINUS_X, EDGE_PLUS_X - SCREW_HOLES[-1][0])
# Each wall pays the edge breaks of the edges exposed at it: the press
# hole's mouths (its face-A chamfer at its upper limit, the title block's
# break at the rear) and the locating holes' mouths; the outline's edge
# where a hole stands inside it; the countersink's rim at the rear face,
# which the title block does not exempt, on the ligaments beside it.  Where
# a wall meets the press hole on both faces, the face whose mouths reach
# further into it governs.
_PRESS_CHAMFER_MAX = max(PRESS_HOLE_CHAMFER_LIMITS)
_SCREW_REACH_AT_PRESS_HOLE = max(
    # rear face: the countersink's rim and the press hole's broken mouth
    CSK_DIA_LIMITS_MM[1] / 2.0 + 2.0 * OUTLINE_EDGE_BREAK_MAX_MM,
    # face A: the drilled hole's broken mouth and the press hole's chamfer
    (SCREW_HOLE_DIA + DRILL_GROWTH) / 2.0 + OUTLINE_EDGE_BREAK_MAX_MM + _PRESS_CHAMFER_MAX,
)
WALLS: dict[str, tuple[float, float]] = {
    # At face A, where the chamfer and the outline's broken edge meet it.
    "press hole to end round": (
        END_R - PRESS_HOLE_DIA / 2.0 - PRESS_HOLE_CHAMFER,
        END_R - OUTLINE_BAND - _PRESS_R_MAX - _PRESS_CHAMFER_MAX
        - OUTLINE_EDGE_BREAK_MAX_MM - HOLE_RUN_OFF_MM,
    ),
    "press hole to countersinks": (
        math.hypot(*_NEAR_HOLE) - PRESS_HOLE_DIA / 2.0 - CSK_DIA / 2.0,
        math.hypot(*_NEAR_HOLE)
        - SCREW_AXIS_RADIUS_IN_PLATE_MM
        - _PRESS_R_MAX
        - _SCREW_REACH_AT_PRESS_HOLE
        - 2.0 * HOLE_RUN_OFF_MM,
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
        - OUTLINE_BAND
        - SCREW_AXIS_RADIUS_IN_PLATE_MM
        # The countersink follows the drilled hole's exit at the rear face,
        # which has run off over the plate since entry at face A; the side
        # edge was milled in an earlier setup.
        - HOLE_RUN_OFF_MM
        - 2.0 * OUTLINE_EDGE_BREAK_MAX_MM,  # the side edge and the cone's rim
    ),
}
for _index, (_x, _y) in enumerate(LOCATOR_SITES_MM, 1):
    _edge_air = min(
        _x - EDGE_MINUS_X, EDGE_PLUS_X - _x,
        (arm_upper_edge_y(_x) - _y) * math.cos(ARM.EDGE_LEAN),
    )
    WALLS[f"locator {_index} to plate edge"] = (
        _edge_air - LOCATOR_HOLE_DIA_MM / 2.0,
        _edge_air - OUTLINE_BAND - LOCATOR_MOUTH_POSITION_RADIUS_MM
        - LOCATING_PIN.SLIP_HOLE_LIMITS_MM[1] / 2.0 - LOCATOR_MOUTH_BREAK_MAX_MM
        - OUTLINE_EDGE_BREAK_MAX_MM - HOLE_RUN_OFF_MM,
    )
    _csk_air = min(math.hypot(_x - x, _y - y) for x, y in SCREW_HOLES)
    WALLS[f"locator {_index} to countersink"] = (
        _csk_air - (LOCATOR_HOLE_DIA_MM + CSK_DIA) / 2.0,
        _csk_air - LOCATOR_MOUTH_POSITION_RADIUS_MM - SCREW_AXIS_RADIUS_IN_PLATE_MM
        - (LOCATING_PIN.SLIP_HOLE_LIMITS_MM[1] + CSK_DIA_LIMITS_MM[1]) / 2.0
        - LOCATOR_MOUTH_BREAK_MAX_MM - OUTLINE_EDGE_BREAK_MAX_MM
        - 2.0 * HOLE_RUN_OFF_MM,
    )
    # At face A, where the press hole's chamfer governs its mouth.
    WALLS[f"locator {_index} to press hole"] = (
        math.hypot(_x, _y) - (LOCATOR_HOLE_DIA_MM + PRESS_HOLE_DIA) / 2.0 - PRESS_HOLE_CHAMFER,
        math.hypot(_x, _y) - LOCATOR_MOUTH_POSITION_RADIUS_MM
        - LOCATING_PIN.SLIP_HOLE_LIMITS_MM[1] / 2.0 - _PRESS_R_MAX
        - LOCATOR_MOUTH_BREAK_MAX_MM - _PRESS_CHAMFER_MAX - 2.0 * HOLE_RUN_OFF_MM,
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

    area, ax, ay = section_area_moments(TOP_LEFT, TOP_RIGHT)
    add(area * THICKNESS_OVER_ARM, ax / area, ay / area, THICKNESS_OVER_ARM / 2.0)
    add(
        -math.pi * (PRESS_HOLE_DIA / 2.0)**2 * THICKNESS_OVER_ARM,
        0.0, 0.0, THICKNESS_OVER_ARM / 2.0,
    )
    # The face-A chamfer's ring: a c x c right triangle about K, its
    # centroid c/3 out from the hole wall and c/3 behind face A.
    add(-PRESS_HOLE_CHAMFER_VOLUME_MM3, 0.0, 0.0, PRESS_HOLE_CHAMFER / 3.0)
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
