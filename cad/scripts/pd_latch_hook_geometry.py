r"""MHA-PD-014 latch hook: one formed spring-steel piece, as pure data.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  The part build, its sheet, the paper-drive assembly and the hanger
joints (``transgear_hanger_joints``) all read the hook from here.

One 0.8 (0.032 in) 1095 spring-steel blank, formed annealed, then hardened
and tempered blue.  It replaces the old edgewise strip, its riveted L
bracket and the two rivets:

* the BASE lies flat on the MHA-PD-007 support bar's back face (machine z
  -129.9) in the bar's lock-free band (y 299.2..307.2) and takes the two
  MHA-VN-043 #4-40 screws into the bar's through taps (x 65.0 / 72.0,
  y 303.234);
* at the base's +X end a 90 deg bend (inside R1.2) raises the EAR rearward
  (+Z) in the machine YZ plane, x 76.8305..77.6305, to z -113.9;
* the ARM hangs from the ear's lower edge (y 299.2), a strip ARM_W wide in
  machine Z (z -123.9..-113.9) with its 0.8 thickness in machine XY.  Its
  mid-plane runs down at x 77.2305, then rolls R80 FLATWISE (about the
  strip's width axis, machine Z) 32.558 deg toward -X, so that the straight
  run through the pin hole lies square to the latch pin: the strip's face
  normal there is the hanger arm's direction U;
* the straight runs RUN_ABOVE_HOLE above the pin hole and RUN_BELOW_HOLE
  below it, then the FINGER TAB rolls R10 TAB_TURN_DEG toward +U (away
  from the hanger arm) and ends in a full round across the band;
* below the guide-lock sweep (y < TAPER_Y[0]) the front edge tapers out
  over ~10 of strip length from z -123.9 to -125.4 and holds there
  through the hole and the tab, so the pin hole keeps a full wall to it.
  Above TAPER_Y[0] the front edge stays 1.5 clear of the guide-lock
  screw heads' z -125.40.

Latch action.  Latched, the MHA-VN-042 pin on the hanger arm's end stands
through the pin hole and the hanger RESTS on the hole's lower (-N) edge with
the feed pinion in the rack: the hole is drilled PIN_BEARING_LIFT up N from
the pin's axis, so the largest pin bears on its lower edge.  To release, the
operator pulls the finger tab along +U: the arm flexes flatwise, the strip
slides off the pin's end and the hanger drops.  To relatch, the operator
lifts the hanger: the pin's crowned end rides up the tab's curved face and
the strip face, and the strip snaps over it into the hole.

Process: cut the blank; bend the ear 90 deg; drill the screw holes from the
formed ear; roll the arm R80 and the tab R10 (annealed); fit to the bar,
clamp the hanger at full feed mesh and match-drill the pin hole from the
pin; remove, harden and temper blue, reinstall.

Part frame (axes parallel to the machine's; the assembly places the part by
translation only, ``PART_ORIGIN_MACHINE``):

* origin = the ear's outer (+X) face, the base's underside (on the bar)
  and the base's low-Y edge (machine (X_B, 299.2, -129.9));
* Right plane (x = 0) = the ear's outer face, the bend's outer tangent and
  the datum for the screw holes, drilled after bending;
* Front plane (z = 0) = the base's underside on the bar's back face;
* Top plane (y = 0) = the base's low-Y edge, which is the ear's lower edge
  and the arm's root;
* the base runs -X to x = -BASE_LENGTH, the ear rises +Z to EAR_HEIGHT,
  the arm hangs -Y below the Top plane.
"""

from __future__ import annotations

import math

from pd_support_bar_spec import BRACKET_TAP_X, HANGER_TAP_Y, PIVOT_TAP_X
from pd_transgear_arm_geometry import PIN_MACHINE_Z
from vn_transgear_latch_pin_spec import DIA_MAX as PIN_DIA_MAX

# --- Stock ---------------------------------------------------------------------
SHEET_T = 0.8  # 0.032 in 1095 spring steel, bought annealed
SHEET_T_PLUS = 0.03  # stock band: the thickest sheet a buyer receives
SHEET_T_MINUS = 0.03  # stock band: the thinnest
HALF_T = SHEET_T / 2.0

# --- Machine anchors -------------------------------------------------------------
# The support bar sits unrotated at machine (0, BAR_CENTRE_Y, -134.4) with its
# back face at z -129.9 (pd_support_bar_spec's frame), so a bar-frame X is a
# machine X and a bar-frame Y is BAR_CENTRE_Y above.
BAR_CENTRE_Y = 306.734
BAR_BACK_FACE_Z = -129.9
# The hanger's pivot P and its latched direction U (the paper-drive
# assembly's ARM_ANGLE_DEG, which it asserts equal); N = U turned +90 deg.
PIVOT_XY = (PIVOT_TAP_X, BAR_CENTRE_Y + HANGER_TAP_Y)  # (-58, 303.234)
ARM_ANGLE_DEG = -32.55846520920007
ARM_U = (math.cos(math.radians(ARM_ANGLE_DEG)), math.sin(math.radians(ARM_ANGLE_DEG)))
ARM_N = (-ARM_U[1], ARM_U[0])


def on_arm(station: float, offset: float = 0.0) -> tuple[float, float]:
    """Machine xy of the hanger-frame point ``P + station*U + offset*N``."""
    return (
        PIVOT_XY[0] + station * ARM_U[0] + offset * ARM_N[0],
        PIVOT_XY[1] + station * ARM_U[1] + offset * ARM_N[1],
    )


# --- Machine z bands -------------------------------------------------------------
Z_REAR = -113.9  # the ear's top and the arm's rear edge
Z_FRONT = -123.9  # the arm's front edge across the guide-lock sweep
Z_FRONT_LOW = -125.4  # the front edge below the taper, through hole and tab
ARM_W = Z_REAR - Z_FRONT  # 10.0
LOW_W = Z_REAR - Z_FRONT_LOW  # 11.5
# Machine y where the front edge leaves z -123.9 and where it reaches -125.4,
# linear in y between (the taper is cut square to the ear's plane).  The
# lower guide-lock plate's sweep band ends at y 282.734.
TAPER_Y = (280.0, 270.0)

# --- Base and ear ----------------------------------------------------------------
BASE_Y = (299.2, 307.2)  # inside the bar's lock-free band 298.7..307.7
WIDTH = BASE_Y[1] - BASE_Y[0]  # 8.0
BASE_X0 = 61.0  # the base's -X end
SCREW_X = tuple(float(x) for x in BRACKET_TAP_X)  # (65.0, 72.0)
SCREW_Y = BAR_CENTRE_Y + HANGER_TAP_Y  # 303.234
SCREW_HOLE_DIA = 3.2  # #4 clearance, as the retired bracket's
INSIDE_BEND_R = 1.2  # annealed 1095 at 1.5 T
OUTSIDE_BEND_R = INSIDE_BEND_R + SHEET_T
INSIDE_BEND_R_MAX = 1.5
# The arm's front edge meets the ear's lower edge in a relief radius: the arm
# flexes hardest at its root.
ROOT_R = 2.0

# --- Arm centreline (machine XY, the strip's mid-plane) ----------------------------
# The pin crosses the strip's mid-plane at machine x 58.2, where it crossed
# the retired strip, so the latched pin keeps its station.
PIN_CROSSING_X = 58.2
HOLE_STATION = (PIN_CROSSING_X - PIVOT_XY[0]) / ARM_U[0]  # 137.867 from P
PIN_AXIS_XY = on_arm(HOLE_STATION)  # (58.2, 229.0396)
RUN_ABOVE_HOLE = 12.0  # straight run from the roll's end down to the hole
RUN_BELOW_HOLE = 15.0  # straight run from the hole down to the tab
ROLL_R = 80.0
ROLL_TURN_DEG = -ARM_ANGLE_DEG  # vertical -> square to U
TAB_R = 10.0
TAB_TURN_DEG = 35.0

ROLL_END = (  # E: the roll's lower tangent, RUN_ABOVE_HOLE up N from the pin
    PIN_AXIS_XY[0] + RUN_ABOVE_HOLE * ARM_N[0],
    PIN_AXIS_XY[1] + RUN_ABOVE_HOLE * ARM_N[1],
)
ROLL_C = (ROLL_END[0] - ROLL_R * ARM_U[0], ROLL_END[1] - ROLL_R * ARM_U[1])
ROLL_START = (ROLL_C[0] + ROLL_R, ROLL_C[1])  # the vertical's lower tangent
X_C = ROLL_START[0]  # the vertical's mid-plane, machine x 77.2305
X_B = X_C + HALF_T  # the ear's outer face, machine x 77.6305
TAB_START = (
    PIN_AXIS_XY[0] - RUN_BELOW_HOLE * ARM_N[0],
    PIN_AXIS_XY[1] - RUN_BELOW_HOLE * ARM_N[1],
)
TAB_C = (TAB_START[0] + TAB_R * ARM_U[0], TAB_START[1] + TAB_R * ARM_U[1])
_TAB_A0 = math.atan2(TAB_START[1] - TAB_C[1], TAB_START[0] - TAB_C[0])
_TAB_A1 = _TAB_A0 + math.radians(TAB_TURN_DEG)  # counter-clockwise
TAB_END = (TAB_C[0] + TAB_R * math.cos(_TAB_A1), TAB_C[1] + TAB_R * math.sin(_TAB_A1))
# The full round across the band, seen along X (the tab's end runs within
# 2.5 deg of -Y): radius half the low band, its tip ROUND_TRIM inside the
# square end so the round takes the whole end.
ROUND_R = LOW_W / 2.0
ROUND_TRIM = 0.1
ROUND_C_YZ = (TAB_END[1] + ROUND_TRIM + ROUND_R, (Z_REAR + Z_FRONT_LOW) / 2.0)
TIP_Y = ROUND_C_YZ[0] - ROUND_R  # the part's lowest point, machine y

# --- Pin hole --------------------------------------------------------------------
# A round hole square to the strip (axis along U), just over the largest pin.
# Its centre sits PIN_BEARING_LIFT up N from the pin's axis so the largest
# pin bears on the hole's lower edge at the drawn pose (the retired strip's
# PIN_BEARING_LIFT intent: a hole centred on the pin let the hanger drop the
# hole's play, opening the feed mesh).
PIN_HOLE_DIA = 3.3
PIN_BEARING_LIFT = (PIN_HOLE_DIA - PIN_DIA_MAX) / 2.0
PIN_HOLE_XY = (
    PIN_AXIS_XY[0] + PIN_BEARING_LIFT * ARM_N[0],
    PIN_AXIS_XY[1] + PIN_BEARING_LIFT * ARM_N[1],
)
PIN_HOLE_Z = PIN_MACHINE_Z  # -120.43125
# The strip's faces along U at the hole: the near (pin-side, -U) face and the
# far (+U) face, as stations from P.
NEAR_FACE_STATION = HOLE_STATION - HALF_T
FAR_FACE_STATION = HOLE_STATION + HALF_T

# --- Developed (flat) blank ---------------------------------------------------------
# The 90 deg bend's allowance at K 0.4 (R/T 1.5); the R80 roll and the R10
# tab (R/T 100 and 12.5) develop on the mid-plane.
K_BEND = 0.4
BEND_ALLOWANCE = math.pi / 2.0 * (INSIDE_BEND_R + K_BEND * SHEET_T)
BASE_LENGTH = X_B - BASE_X0  # formed, to the ear's outer face: 16.6305
EAR_HEIGHT = Z_REAR - BAR_BACK_FACE_Z  # formed, to the base's underside: 16.0
FLAT_BASE = BASE_LENGTH - SHEET_T - INSIDE_BEND_R  # flat to the bend's start
FLAT_EAR = EAR_HEIGHT - SHEET_T - INSIDE_BEND_R  # flat from the bend's end
FLAT_LENGTH = FLAT_BASE + BEND_ALLOWANCE + FLAT_EAR  # the blank across the bend
_ROLL_TURN = math.radians(ROLL_TURN_DEG)
_TAB_TURN = math.radians(TAB_TURN_DEG)
# Arm stations along the mid-plane from the ear's lower edge (y 299.2).
DEV_ROLL_START = BASE_Y[0] - ROLL_START[1]
DEV_ROLL_END = DEV_ROLL_START + ROLL_R * _ROLL_TURN
DEV_HOLE = DEV_ROLL_END + RUN_ABOVE_HOLE
DEV_TAB_START = DEV_HOLE + RUN_BELOW_HOLE
DEV_TAB_END = DEV_TAB_START + TAB_R * _TAB_TURN
DEV_TIP = DEV_TAB_END - ROUND_TRIM  # the arm's developed length to the round's tip


def _dev_at_y(y: float) -> float:
    """Developed station of the mid-plane at machine ``y`` on the vertical or
    the roll (y >= the roll's end)."""
    if y >= ROLL_START[1]:
        return BASE_Y[0] - y
    return DEV_ROLL_START + ROLL_R * math.asin((ROLL_START[1] - y) / ROLL_R)


DEV_TAPER = (_dev_at_y(TAPER_Y[0]), _dev_at_y(TAPER_Y[1]))
# The blank's front edge (z -123.9) and the lip it widens to: in the flat the
# arm's front edge steps out LOW_W - ARM_W over DEV_TAPER.
LIP_W = LOW_W - ARM_W  # 1.5

# --- Local part frame ----------------------------------------------------------------
PART_ORIGIN_MACHINE = (X_B, BASE_Y[0], BAR_BACK_FACE_Z)
LOCAL_TO_MACHINE = (
    (1.0, 0.0, 0.0),  # machine x = local x
    (0.0, 1.0, 0.0),  # machine y = local y
    (0.0, 0.0, 1.0),  # machine z = local z
)


def to_local(x: float, y: float) -> tuple[float, float]:
    """Machine (x, y) -> the part's Front-plane sketch (x, y)."""
    return (x - PART_ORIGIN_MACHINE[0], y - PART_ORIGIN_MACHINE[1])


def z_local(z: float) -> float:
    """Machine z -> part z (above the Front plane)."""
    return z - PART_ORIGIN_MACHINE[2]


def _offset(point, centre, by: float) -> tuple[float, float]:
    """``point`` moved ``by`` along the ray from ``centre`` (+ = away)."""
    d = math.dist(point, centre)
    return (
        point[0] + by * (point[0] - centre[0]) / d,
        point[1] + by * (point[1] - centre[1]) / d,
    )


# Arm profile in the part's Front-plane sketch.  OUTER is the +X side at the
# vertical, the convex side of the roll and the strip's far (+U) face along
# the straight; it is the concave side of the tab, whose centre lies +U.  The
# profile starts at the ear's top so the arm and the ear overlap on the ear.
ROLL_C_L = to_local(*ROLL_C)
TAB_C_L = to_local(*TAB_C)
OUTER_TOP = (0.0, WIDTH)
INNER_TOP = (-SHEET_T, WIDTH)
OUTER_ROLL_START = (0.0, to_local(*ROLL_START)[1])
INNER_ROLL_START = (-SHEET_T, OUTER_ROLL_START[1])
OUTER_ROLL_END = _offset(to_local(*ROLL_END), ROLL_C_L, HALF_T)
INNER_ROLL_END = _offset(to_local(*ROLL_END), ROLL_C_L, -HALF_T)
OUTER_TAB_START = _offset(to_local(*TAB_START), TAB_C_L, -HALF_T)
INNER_TAB_START = _offset(to_local(*TAB_START), TAB_C_L, HALF_T)
OUTER_TAB_END = _offset(to_local(*TAB_END), TAB_C_L, -HALF_T)
INNER_TAB_END = _offset(to_local(*TAB_END), TAB_C_L, HALF_T)
OUTER_ROLL_R = ROLL_R + HALF_T
INNER_ROLL_R = ROLL_R - HALF_T
OUTER_TAB_R = TAB_R - HALF_T
INNER_TAB_R = TAB_R + HALF_T
PIN_HOLE_L = to_local(*PIN_HOLE_XY)
PIN_HOLE_ZL = z_local(PIN_HOLE_Z)
SCREW_HOLE_X = tuple(round(x - X_B, 6) for x in SCREW_X)  # (-12.6305, -5.6305)
SCREW_HOLE_Y = round(SCREW_Y - BASE_Y[0], 6)  # 4.034
ARM_Z0 = z_local(Z_FRONT_LOW)  # the arm's extrusion: 4.5 .. 16.0 above Front
ARM_Z1 = z_local(Z_REAR)
TAPER_L = (TAPER_Y[0] - BASE_Y[0], TAPER_Y[1] - BASE_Y[0])
ROUND_C_L = (ROUND_C_YZ[0] - BASE_Y[0], z_local(ROUND_C_YZ[1]))

# --- Areas and volumes (for the build's gates) ----------------------------------
# The L section across the bend (Top plane): base and ear plates less their
# overlap at the corner, with the R1.2 / R2.0 bend fillets.
_L_AREA = (
    BASE_LENGTH * SHEET_T
    + EAR_HEIGHT * SHEET_T
    - SHEET_T**2
    + (1.0 - math.pi / 4.0) * INSIDE_BEND_R**2
    - (1.0 - math.pi / 4.0) * OUTSIDE_BEND_R**2
)
V_L = _L_AREA * WIDTH
# The arm's Front-plane profile: the strip's mid-plane length below the ear's
# top times its thickness (concentric offsets keep the area exact).
ARM_PROFILE_AREA = SHEET_T * (WIDTH + DEV_TAB_END)
V_ARM_PRISM = ARM_PROFILE_AREA * (ARM_Z1 - ARM_Z0)
# The arm's prism inside the ear (y 0..WIDTH, z ARM_Z0..ARM_Z1) is already
# solid.
V_ARM_ON_EAR = SHEET_T * WIDTH * (ARM_Z1 - ARM_Z0)


def _ds_dy(y: float) -> float:
    """Mid-plane arc length per unit of machine y on the vertical or the roll."""
    if y >= ROLL_START[1]:
        return 1.0
    return ROLL_R / math.sqrt(ROLL_R**2 - (ROLL_START[1] - y) ** 2)


def _front_edge_z(y: float) -> float:
    """The front edge's machine z at machine ``y`` (the taper's cut)."""
    if y >= TAPER_Y[0]:
        return Z_FRONT
    if y <= TAPER_Y[1]:
        return Z_FRONT_LOW
    t = (TAPER_Y[0] - y) / (TAPER_Y[0] - TAPER_Y[1])
    return Z_FRONT + t * (Z_FRONT_LOW - Z_FRONT)


def _taper_cut_volume(n: int = 4000) -> float:
    """What the taper cut removes from the arm prism below the ear: the strip's
    0.8 x ds slab times the band cut off its front, y TAPER_Y[1]..BASE_Y[0]."""
    y0, y1 = TAPER_Y[1], BASE_Y[0]
    h = (y1 - y0) / n
    total = 0.0
    for i in range(n):
        y = y0 + (i + 0.5) * h
        total += (_front_edge_z(y) - Z_FRONT_LOW) * _ds_dy(y) * h
    return SHEET_T * total


V_TAPER_CUT = _taper_cut_volume()
# The full round at the tip, seen along X: the two corners the round takes
# off a band LOW_W wide, ROUND_TRIM of square end above them included.  The
# tab's end runs within 2.5 deg of -Y, so the slab is 0.8 x dy to 0.1 %.
V_ROUND_CUT = SHEET_T * ((2.0 - math.pi / 2.0) * ROUND_R**2 + ROUND_TRIM * LOW_W)
# The root's relief radius fills the inside corner across the strip.
V_ROOT_FILL = (1.0 - math.pi / 4.0) * ROOT_R**2 * SHEET_T
V_PIN_HOLE = math.pi * (PIN_HOLE_DIA / 2.0) ** 2 * SHEET_T
V_SCREW_HOLES = 2.0 * math.pi * (SCREW_HOLE_DIA / 2.0) ** 2 * SHEET_T
VOLUME = (
    V_L
    + V_ARM_PRISM
    - V_ARM_ON_EAR
    - V_TAPER_CUT
    - V_ROUND_CUT
    + V_ROOT_FILL
    - V_PIN_HOLE
    - V_SCREW_HOLES
)


# --- Machine (y, z) sections for the lock sweep -------------------------------------
def arm_sections(step: float = 0.25) -> list[tuple[float, float, float, float]]:
    """The arm's machine (y0, y1, z0, z1) silhouette, seen along X, as thin
    slices from the tip up to the ear's lower edge (the round end as its
    bounding square)."""
    sections = [
        (TIP_Y, ROUND_C_YZ[0], Z_FRONT_LOW, Z_REAR),
    ]
    count = math.ceil((BASE_Y[0] - ROUND_C_YZ[0]) / step)
    for i in range(count + 1):
        y = ROUND_C_YZ[0] + (BASE_Y[0] - ROUND_C_YZ[0]) * i / count
        sections.append((y, y, _front_edge_z(y), Z_REAR))
    return sections


# Machine bounding box of the part.
BBOX_X = (
    min(BASE_X0, TAB_END[0] - HALF_T, PIN_HOLE_XY[0] - 1.0),
    X_B,
)
BBOX_Y = (TIP_Y, BASE_Y[1])
BBOX_Z = (BAR_BACK_FACE_Z, Z_REAR)

# --- Import-time checks of the published chain -------------------------------------
_TOL = 1e-6
if (
    abs(math.dist(ROLL_C, ROLL_END) - ROLL_R) > _TOL
    or abs(ROLL_START[1] - ROLL_C[1]) > _TOL
):
    raise AssertionError("the R80 roll does not leave the vertical tangent")
# The roll's lower tangent is square to U: its radius runs along U.
if abs((ROLL_END[0] - ROLL_C[0]) / ROLL_R - ARM_U[0]) > _TOL:
    raise AssertionError("the roll does not end square to the latch pin")
if abs(math.dist(TAB_C, TAB_START) - TAB_R) > _TOL:
    raise AssertionError("the finger tab does not leave the straight tangent")
if not BASE_Y[0] > TAPER_Y[0] > TAPER_Y[1] > ROLL_END[1]:
    raise AssertionError("the front-edge taper is off the vertical/roll")
# The taper ends a full ROOT_R below the root radius and above the pin hole.
if not (TAPER_Y[0] < BASE_Y[0] - ROOT_R and TAPER_Y[1] > PIN_HOLE_XY[1] + PIN_HOLE_DIA):
    raise AssertionError("the taper overlaps the root radius or the pin hole")
if not BASE_Y[0] < SCREW_Y < BASE_Y[1]:
    raise AssertionError("the screw holes left the base's width")
if not all(
    BASE_X0 < x - SCREW_HOLE_DIA / 2.0
    and x + SCREW_HOLE_DIA / 2.0 < X_B - SHEET_T - INSIDE_BEND_R
    for x in SCREW_X
):
    raise AssertionError("a screw hole left the base's flat")
if SCREW_X[0] >= SCREW_X[1]:
    raise AssertionError("the screw holes are not ordered -X to +X")
# The round end's tip lies on the square end's own run, so the round takes
# the whole end.
if not TAB_END[1] - HALF_T < TIP_Y < TAB_END[1] + 0.5:
    raise AssertionError("the full round is off the tab's square end")
if (
    not Z_FRONT_LOW
    < PIN_HOLE_Z - PIN_HOLE_DIA / 2.0
    < PIN_HOLE_Z + PIN_HOLE_DIA / 2.0
    < Z_REAR
):
    raise AssertionError("the pin hole left the strip's band")
if PIN_BEARING_LIFT <= 0.0:
    raise AssertionError("the pin hole is not over the largest latch pin")
