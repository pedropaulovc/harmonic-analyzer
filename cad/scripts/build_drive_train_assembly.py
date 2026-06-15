r"""Reproduction script: drive-train subassembly (book ch. 11-13, 30).

The complete drive train in machine coordinates (assembly origin = base
origin; base top face at y = 50.8, drive height 76 above it):

* cone set: a TRUE CONE -- all 20 gears AND the 64T crank-drive gear
  seated perpendicular to the stepped shaft (p.18/p.20 photos), the
  shaft inclined 21.1 deg in PLAN, big-end journal in the black pivot
  post, thin 1/8" tip resting in the green knob post's U-slot.
* cylinder drum: 20 identical 120T gears spinning freely on the
  stationary arbor along Z at (-47.5, 126.8) (M6.2 keyway refutation),
  clamped by the south arbor pedestal and (at the north end) the
  rocker-arm-support's boss bore in frame.SLDASM; notches up = cosine
  setup (pp. 66-67).
* crankshaft along Z in the green crank pedestal: crank arm + handle at
  the front, the T12 removable chain wheel (ch. 23: the bead chain
  rides the removable's m2 teeth -- swapping removables changes the
  platen ratio) and the 16T DP 16 pinion inboard (the removable
  tapered pin is OMITTED: a tapered pin cannot sit in the straight
  5 mm cross-holes without solid interference).

TRUE-CONE MESH GEOMETRY (M6.7; supersedes the M6.6 canted-vertical
seats, which satisfied the interference checker but visibly deformed
the cone -- user-flagged against the p.18 photo). A gear seated
perpendicular to a shaft inclined i in plan reaches a parallel-axis
drum only with the tooth at the azimuth facing the drum; that contact
tooth sits r*sin(i) SOUTH (along the shaft) of the gear centre and
reaches x = x_centre - r*cos(i). Meshing every station therefore
needs:

* a centre-x grid stepping by the PROJECTED radius step 2.54*cos(i),
* each centre z at z_drum_j + r_j*sin(i) -- NORTH of its drum plane,
  so the contact tooth lands exactly in that plane.

Those centres lie on ONE straight shaft iff sin(i) = 2.54/Z_PITCH ->
i = 21.0976 deg (the retired arcsin(2.54/7.5) = 19.8 put the tracking
on the wrong leg of the triangle: it produced a 0.44/station z-drift
and 0.15/station radial error -- "most gears not meshing"), with seat
pitch Z_PITCH*cos(i) = 6.5839 along the shaft. The 6.5839 pitch forces
CONE_FACE down to 6.5 (annotated 7 mm faces would overlap 0.42): the
book's annotated cone figures (face 7, pitch 7.5, stack 150) are
mutually inconsistent with the photo-measured drum grid -- the drum
grid wins (it anchors the gates and all channel machinery), and the
150 mm annotation reconciles as gear stack 131.6 + 64T face 10 + air.
Self-consistency: tan(cone half-angle) = 2.54/6.5839 = tan(i), so the
cone's drum-side generator runs PARALLEL to the drum axis -- the p.18
seam.

The engagement is intentionally PARTIAL ("oblique angle ... partial
engagement, distinct wear", ch. 12): the contact tooth crosses the
3 mm drum face obliquely, penetration varying +-1.5*tan(i) = 0.58
about its centre value; X_PITCH backs the cone off so the DEEPEST
crossing point stays clear of the DP 30 working depth (edge slack
checker-arbitrated, see PEN_EDGE_SLACK) -> tip interleave 0.00..1.14
across each drum face, identical at ALL 20 stations (zero drift, T006
included). Stub-gap caps hold without any per-gear relief: the drum
tips dive at most 0.24 into a cone gap vs the shallowest (T006) stub
cap 0.88. The 16T crank pinion mesh gets the same treatment: the
perpendicular 64T presents its contact tooth 50.8*sin(i) = 18.3 north
of its centre, the pinion is centred on that plane, and X_CRANK backs
off so the +-1.8 oblique dive across the 64T face caps clear of the
DP 16 working depth (PEN16_EDGE_SLACK; the deep south side stays
visibly interleaved at 2.1 of 3.2).

Positions per cad/DIMENSIONS.md ch. 13 "Drive-train layout" + "Drive
supports". Tooth phasing: every gear script seeds a TOOTH centred on
local +X; the cone gears keep phase 0 (even tooth counts put a tooth
at azimuth 180, the contact azimuth) and the drum gears are
pre-rotated +1.5 deg (half a 3 deg pitch) to receive it tooth-in-gap;
the crank pinion +11.25 deg (half of 22.5) likewise.

Mated-DOF strategy (M6 operation simulation): the structure -- the
stationary arbor, the pedestals/posts, and the disengaged alignment rig
-- is grounded; the crank chain, the cone cluster and the 20 cylinder
gears are inserted on their exact mirrored transforms (so mate
flip-recovery has a clean reference and the tuned tooth phases are
preserved) and joined by real kinematic joints. The crankshaft and the
cone shaft each get a revolute (coincident axis-to-axis + an axial plane
distance); the crank arm/handle/T12 wheel/16T pinion are keyed to the
crankshaft and the 64T + 20 cone gears keyed to the cone shaft (lock
mates); a 16T:64T gear mate drives the cone cluster from the crank, and
each cylinder gear meshes its cone gear k at ratio [120-6k : 120]. The
gear mate is each cylinder gear's sole rotational constraint, so it
holds the cosine-setup phase without nudging the gear. The whole train
is left with exactly ONE free DOF -- the crank angle -- pinned by a
single spin driver on the handle (DRIVER #1, suppressible for the Motion
study). Saved state: every component fixed or fully defined, zero
interferences (tangent/coincident contact allowed -- bores ride their
shafts). Gear-ratio sign is verified kinematically by a motion script.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_drive_train_assembly.py
"""

from __future__ import annotations

import math
import sys

import _config
from _common import (
    angle_driver,
    assert_components_fully_defined,
    check,
    check_no_interference,
    coincident_mate,
    component_transform,
    distance_driver,
    gear_mate,
    lock_mate,
    named_ref,
    place_component,
    run_build,
    save_assembly_and_images,
    spin_driver,
)

ASM_NAME = "drive-train"

Y_BASE_TOP = 50.8  # harmonic-base top face
Y_DRIVE = Y_BASE_TOP + 76.0  # 126.8: crank, cone big end and arbor axes

DP_TRAIN = _config.machine("gear_train", "diametral_pitch")  # cad/config/machine.yaml (DIMENSIONS.md ch12)
ADDENDUM = 25.4 / DP_TRAIN  # 0.847
WORKING_DEPTH = 2.0 * ADDENDUM  # 1.693: full tooth interleave depth
RADIUS_STEP = 3.0 * 25.4 / DP_TRAIN  # 2.54: pitch-radius step per 6 teeth

# Frame-locked machine grid (M6.3 lineage -- the drum planes anchor the
# gates, cams, rockers and bars; nothing here may move them).
_DRUM_SEAT_NOMINAL = _config.machine("cone_incline", "drum_seat_nominal_mm")  # 7.5
Z_PITCH = _DRUM_SEAT_NOMINAL * math.cos(math.asin(RADIUS_STEP / _DRUM_SEAT_NOMINAL))  # 7.0568: drum z-pitch
X_DRUM = -47.5  # rocker-support boss bore + arbor pedestal
Z_DRUM0 = _config.machine("channels", "station_z0_mm")  # -67.1 drum gear 0 plane (shared station anchor)

# True-cone incline (M6.7, exact tracking -- see module docstring).
SIN_I = RADIUS_STEP / Z_PITCH  # 0.35993
COS_I = math.sqrt(1.0 - SIN_I * SIN_I)  # 0.93299
TAN_I = SIN_I / COS_I
SEC_I = 1.0 / COS_I
INCLINE_DEG = math.degrees(math.asin(SIN_I))  # 21.0976
SEAT_PITCH = Z_PITCH * COS_I  # 6.5839: seat pitch along the shaft

CONE_FACE = 6.5  # M6.7 mesh packing (annotated 7 -- build_cone_gear.py)
GEAR64_FACE = 10.0
DRUM_FACE = 3.0  # cylinder gear face (gear z = 0..3, cam 3..6.5)
PINION_FACE = 12.0

# Mesh anchor: X_PITCH is every cone gear's pitch-section x at the
# contact azimuth. The oblique crossing dives (DRUM_FACE/2)*tan(i) past
# the mid-face penetration, so the mid value is capped at working depth
# minus the dive minus the edge slack -> tip interleave 0.00..1.14.
# Slack 0.55 is checker-arbitrated: the oblique crossing distorts the
# flank match beyond plain backlash math, worst at the smallest gears
# (their engagement arc spans a large azimuth, where the off-centre
# teeth barely drift out of the drum band) -- 0.15 left <=0.06 mm^3
# flank slivers at the five smallest stations, 0.35 still skinned the
# last four.
DRUM_TIP_X = X_DRUM + (122.0 / DP_TRAIN) * 25.4 / 2.0  # 4.147
PEN_EDGE_SLACK = 0.55
PEN_MID = WORKING_DEPTH - PEN_EDGE_SLACK - (DRUM_FACE / 2.0) * TAN_I  # 0.565
X_PITCH = DRUM_TIP_X + ADDENDUM * SEC_I - PEN_MID  # 4.490


def cone_seat(j: int) -> tuple[float, float]:
    """(x, z) centre of cone gear j: pitch-projected x, r*sin(i) north."""
    r = 2.0 * 25.4 - RADIUS_STEP * j
    return X_PITCH + r * COS_I, Z_DRUM0 + Z_PITCH * j + r * SIN_I


# Cone shaft: pivot end at seat station -28.25 from the T120 centre
# (25 journal + half of the first 6.5 face -- build_cone_gear_shaft.py).
SHAFT_T120_STATION = 25.0 + CONE_FACE / 2.0  # 28.25
CONE_ORIGIN = [
    cone_seat(0)[0] + SHAFT_T120_STATION * SIN_I,
    Y_DRIVE,
    cone_seat(0)[1] - SHAFT_T120_STATION * COS_I,
]


def cone_station(s: float) -> list[float]:
    """Machine point of the cone-shaft axis at station s (mm from pivot end)."""
    return [
        CONE_ORIGIN[0] - s * SIN_I,
        Y_DRIVE,
        CONE_ORIGIN[2] + s * COS_I,
    ]


# Exact-tracking self-check: the 20 mesh-derived seats lie on the shaft.
for _j in range(20):
    _x, _z = cone_seat(_j)
    _p = cone_station(SHAFT_T120_STATION + _j * SEAT_PITCH)
    if abs(_p[0] - _x) > 1e-9 or abs(_p[2] - _z) > 1e-9:
        raise AssertionError(f"cone seat {_j} off the shaft line: {(_x, _z)} vs {_p}")

# 64T crank-drive gear: perpendicular on the pivot journal, 0.1 air to
# the T120 south face (p.20: directly beside).
GEAR64_STATION = SHAFT_T120_STATION - (CONE_FACE + GEAR64_FACE) / 2.0 - 0.1  # 19.9
GEAR64_SEAT = cone_station(GEAR64_STATION)  # (54.49, , -56.61)
R64 = 2.0 * 25.4  # DP 16, 64T pitch radius

# Crank: the 64T's contact tooth (azimuth 0, toward +x) sits R64*sin(i)
# north of its centre; the pinion is centred on that plane and the mesh
# backs off so the +-5 oblique dive caps short of working depth. Slack
# 1.10 is checker-arbitrated like the drum mesh's (the long +-1.8 dive
# across the 64T face squeezes flanks: 0.15 left 1.48 mm^3, 0.60 left
# 0.23, 0.90 a 0.00 skin).
ADD16 = 25.4 / 16.0
WORK16 = 2.0 * ADD16  # 3.175
PEN16_EDGE_SLACK = 1.10
PEN16_MID = WORK16 - PEN16_EDGE_SLACK - (GEAR64_FACE / 2.0) * SIN_I  # 0.275
PINION_TOOTH_Z = GEAR64_SEAT[2] + R64 * SIN_I  # -38.32
X_CRANK = (
    GEAR64_SEAT[0] + R64 * COS_I + 12.7 + (ADD16 * (1.0 + SEC_I) - PEN16_MID)
)  # 118.00 -- photo: pedestal 122 +- 3 (1.3 sigma, see DIMENSIONS.md)

ARBOR_LENGTH = 196.0  # spans z -98..+98 (M6.9: 1.0 clear of the a-frame
# plate back face -99; north end keeps 23.9 in the support boss bore)
CRANKSHAFT_Z0 = -150.0  # front end; crank-arm hub at +12 (PIN_HOLE_HEIGHT)
CRANKSHAFT_LENGTH = 120.0  # build_crankshaft.py SHAFT_LENGTH
CRANK_ARM_Z0 = CRANKSHAFT_Z0 + 8.0  # hub centre 12 - half thickness 4
ARM_C2C = 150.0  # handle pivot from the shaft axis
REMOVABLE_Z0 = -85.6  # mounted T12 (face 5.0) against the pedestal north face:
# the crank-end chain wheel is the small removable gear (ch. 23 -- the bead
# chain rides its m2 teeth; v2_gears_010 shows the small steel wheel on the
# crank pedestal), band -85.6..-80.6
PEDESTAL_Z = -108.6  # crank pedestal centre (front face inside base edge)
ARBOR_PEDESTAL_Z = 90.5  # south (-z) end only; north end clamps into the
# rocker-arm-support boss bore at z 74.1..133 (frame.SLDASM, M6.5).
# M6.9: 92 -> 90.5 so the block front face -98.5 clears the a-frame
# plate back face -99 by 0.5 (the portal-frame thickening)

# The pinion must sit fully on the crankshaft.
if PINION_TOOTH_Z + PINION_FACE / 2.0 > CRANKSHAFT_Z0 + CRANKSHAFT_LENGTH:
    raise AssertionError("crankshaft too short for the M6.7 pinion station")

# Posts: the rotated 25x20 pivot block reaches 10*cos+12.5*sin = 13.83
# in machine z from its centre; at station -1.0 its north corner stops
# 1.0 short of the perpendicular 64T's south face, with the shaft
# engaging the first 9 mm of the journal bore (blind-bearing look,
# p.18: the shaft end disappears into the black bracket).
PIVOT_POST_STATION = -1.0
KNOB_POST_STATION = 177.0  # thin-tip journal; z 90.0, x -2.1 (p.18)

# --- alignment pinion (ch. 25): carried DISENGAGED (p. 68 "gap") ---
# The 42T DP 30 pinion drum hangs low and FRONT-CENTRE on the base,
# just east-machine of the midline (p002: the silver lever + tee handle
# cluster; the ch25 close-ups are BACK-side shots -- "front side"
# labels the post, not the viewpoint). Two swing straps journal the
# drum's arbor stubs and pivot on a plain torque shaft parked west-
# machine of the cone-knob post; a parallel LIFT ROD through the same
# blocks carries two cam pins and the engage lever (root clamp on its
# front end, standing up+out = disengaged); the turning HANDLE (big
# ball + cross rod) rides the drum's front arbor stub. The rest pose
# threads five hard constraints: tip gap 2.0 to the cylinder train,
# per-disc clearance to every cone gear and the 64T, drum tips 0.8
# above the base top, the back stub 0.5 short of the knob-post
# footprint, and the engaged pose (c2c 68.58, cone swung clear in that
# state) still reachable from the parked pivot with 0.7 spare.
PINION_TEETH = 42
TIP_DRUM = (122.0 / DP_TRAIN) * 25.4 / 2.0  # 51.647: 120T tip radius
TIP_PINION = ((PINION_TEETH + 2.0) / DP_TRAIN) * 25.4 / 2.0  # 18.627
ENGAGED_C2C = (120.0 + PINION_TEETH) / 2.0 * 25.4 / DP_TRAIN  # 68.58
PINION_GAP = 2.0  # disengaged tip clearance
PINION_DRUM_LEN = 143.2  # build_alignment_pinion FACE_WIDTH
PINION_STUB_BACK = 5.5  # build_alignment_pinion STUB_BACK
PINION_Z_FRONT = -75.0  # drum front end face
PINION_Y = 70.5  # drum tips 0.82 above the base top -- the only band the
# rest pose fits: higher crowds the cone fan / 64T discs, lower the base
PINION_X = X_DRUM + math.sqrt(
    (TIP_DRUM + TIP_PINION + PINION_GAP) ** 2 - (Y_DRIVE - PINION_Y) ** 2
)  # -2.18: tip circles backed off to PINION_GAP, just east-machine of
# the midline (p002 front-bottom-centre cluster)
PIVOT_Y = Y_BASE_TOP + 12.0  # 62.8: block bore height; the strap's r 11
# bottom cap swings 1.0 clear of the base top
STRAP_T = 5.0  # build_pinion_bracket THICKNESS
STRAP_C2C = 31.0  # build_pinion_bracket C2C
STRAP_AIR = 0.25  # axial air each side of each strap
BLOCK_T = 12.0  # build_pinion_pivot_block DEPTH
PIVOT_X = PINION_X + math.sqrt(
    STRAP_C2C**2 - (PINION_Y - PIVOT_Y) ** 2
)  # +27.85: torque shaft parked west-machine of the knob post; the
# straps lean 75.6 deg onto the arbor in the rest pose
LIFT_X = PIVOT_X + 15.0  # lift rod in the far bore (2 * block bore
# spacing): squeezed between the strap's swinging r 11 bottom cap
# (0.82 air) and the cone-pivot-post column east face (0.85 air)
STRAP_LEAN_DEG = math.degrees(
    math.atan2(PIVOT_X - PINION_X, PINION_Y - PIVOT_Y)
)  # 75.62
PIVOT_SHAFT_Z0 = -106.0  # plain Ø6.35 x 196: 2 proud past each block face
LIFT_ROD_Z0 = -120.0  # Ø6.35 x 210: front end proud for the lever root;
# cam pins land at machine z -77.5 / +70.5, inside each strap's z band
LEVER_TILT_DEG = 32.0  # from vertical, toward +x script / west machine (p002)
LEVER_Z = -113.0  # clamp ball flush on the lift rod's front end, 1.75
# ahead of the forward front block face
HANDLE_Z = -95.0  # ball centre; hub z -88..-81 seats on the front arbor
# stub (machine -83..-75), 0.75 clear of the front strap face -80.25
HANDLE_TILT_DEG = 65.0  # cross rod from vertical: long arm toward +x
# script / machine west (p002: the tee leans up-left in the front
# view), short arm down-east stopping 1.7 above the base top

PINION_Z_BACK = PINION_Z_FRONT + PINION_DRUM_LEN  # +68.0
BLOCK_X = (PIVOT_X + LIFT_X) / 2.0  # block local origin midway the bores
BLOCK_FRONT_Z0 = -104.0  # forward of the cone-pivot-post column's z band
# (-89.9..-62.3), 1.8 clear; the front strap floats 11.75 ahead of it
BLOCK_BACK_Z0 = 76.0  # 2.55 behind the back strap; the shaft/lift-rod
# ends land 2 proud of the back block face at z +88

# Geometry self-checks (all 20 stations covered; everything clears).
if abs(math.hypot(PIVOT_X - PINION_X, PINION_Y - PIVOT_Y) - STRAP_C2C) > 0.001:
    raise AssertionError("strap c2c does not span pivot -> pinion axis")
if Z_DRUM0 - DRUM_FACE / 2.0 < PINION_Z_FRONT + 1.0:
    raise AssertionError("alignment pinion too short at the front station")
if Z_DRUM0 + 19 * Z_PITCH + DRUM_FACE / 2.0 > PINION_Z_BACK + 0.5:
    # The knob-post footprint (z >= 74) caps drum + stub + strap; the
    # drum back face may shave at most 0.5 off the j = 19 gear face
    # (actual 0.28 -- 90% face coverage at that one station, Appendix C).
    raise AssertionError("alignment pinion misses the j = 19 station")
if math.hypot(PINION_X - X_DRUM, Y_DRIVE - PINION_Y) < TIP_DRUM + TIP_PINION + 1.0:
    raise AssertionError("alignment pinion crowds the cylinder train")
if math.hypot(PIVOT_X - X_DRUM, Y_DRIVE - PIVOT_Y) > ENGAGED_C2C + STRAP_C2C - 0.25:
    raise AssertionError("engaged pose unreachable from the parked pivot")
for _j in range(20):
    _tip = 2.0 * 25.4 - RADIUS_STEP * _j + ADDENDUM
    if (
        math.hypot(PINION_X - cone_seat(_j)[0], Y_DRIVE - PINION_Y)
        < _tip + TIP_PINION + 0.25
    ):
        raise AssertionError(f"pinion drum crowds cone gear {_j}")
if (
    math.hypot(PINION_X - GEAR64_SEAT[0], Y_DRIVE - PINION_Y)
    < R64 + ADD16 + TIP_PINION + 0.25
):
    raise AssertionError("pinion drum crowds the 64T crank-drive gear")
_post = cone_station(KNOB_POST_STATION)
if PINION_Z_BACK + PINION_STUB_BACK > _post[2] - 16.0 - 0.25:
    raise AssertionError("back arbor stub reaches the cone-knob post footprint")
if BLOCK_X - 16.5 < _post[0] + 16.0 + 0.25:
    raise AssertionError("pivot blocks reach the cone-knob post footprint")
# Cone-PIVOT-post column (25 x 20 rotated by the incline, plan half-
# extents 15.26 x 13.83 about cone_station(-1)): the lift rod passes in
# front of nothing -- it must thread EAST of the column; the front block
# dodges it in z instead.
_ppost = cone_station(PIVOT_POST_STATION)
_PPOST_HX = 12.5 * COS_I + 10.0 * SIN_I  # 15.26
_PPOST_HZ = 12.5 * SIN_I + 10.0 * COS_I  # 13.83
if LIFT_X + 3.175 > _ppost[0] - _PPOST_HX - 0.25:
    raise AssertionError("lift rod reaches the cone-pivot-post column")
if BLOCK_FRONT_Z0 + BLOCK_T > _ppost[2] - _PPOST_HZ - 0.25:
    raise AssertionError("front pivot block reaches the cone-pivot-post column")
if LIFT_X - PIVOT_X < 11.0 + 3.175 + 0.25:
    raise AssertionError("lift rod fouls the strap's swinging bottom cap")
if LEVER_Z + 7.0 > BLOCK_FRONT_Z0 - 0.25:
    raise AssertionError("lever clamp ball fouls the front pivot block")
if PINION_X - TIP_PINION < -28.45 + 0.25:
    raise AssertionError("pinion drum reaches the rocker-support frustum")
if STRAP_C2C < TIP_PINION + 3.175 + 0.25:
    raise AssertionError("pivot shaft fouls the pinion drum tips")
if math.hypot(LIFT_X - PINION_X, PINION_Y - PIVOT_Y) < TIP_PINION + 3.175 + 0.25:
    raise AssertionError("lift rod fouls the pinion drum tips")
if PIVOT_Y - 11.0 < Y_BASE_TOP + 0.5:
    raise AssertionError("strap bottom cap dips into the base top")
if PIVOT_Y - 11.175 < Y_BASE_TOP + 0.5:
    raise AssertionError("lift-rod cam pin tips dip into the base top")
if (
    PINION_Y
    - 35.0 * math.cos(math.radians(HANDLE_TILT_DEG))
    - 3.0 * math.sin(math.radians(HANDLE_TILT_DEG))
    < Y_BASE_TOP + 0.5
):
    raise AssertionError("handle cross-rod short arm dips into the base top")
if abs(HANDLE_Z - LEVER_Z) < 6.0 + 1.0:
    raise AssertionError("engage lever plane fouls the handle cross-rod plane")
if HANDLE_Z - 3.0 < -99.0 + 0.25:
    raise AssertionError("handle cross-rod plane reaches the A-frame band")

IDENTITY = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
ROT_X_POS90 = [[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, -1.0, 0.0]]
ROT_Y_POS90 = [[0.0, 0.0, -1.0], [0.0, 1.0, 0.0], [1.0, 0.0, 0.0]]
ROT_Y_INCLINE = [
    [COS_I, 0.0, SIN_I],
    [0.0, 1.0, 0.0],
    [-SIN_I, 0.0, COS_I],
]  # Ry(-21.1), row-vector convention (matches the frame script's Ry rows)


def rot_z_rows(deg: float) -> list[list[float]]:
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [[c, s, 0.0], [-s, c, 0.0], [0.0, 0.0, 1.0]]


def _org(adapter, name: str) -> list[float]:
    """A component's current origin (mm) in the assembly frame."""
    a = component_transform(adapter, name)
    return [a[9] * 1000.0, a[10] * 1000.0, a[11] * 1000.0]


async def _place_on_shaft(
    adapter,
    part: str,
    station: float,
    face: float,
    *,
    configuration: str = "",
    label: str = "",
) -> str:
    """Insert a gear perpendicular on the cone shaft (free), centred at station.

    The gear's central reference axis ends up collinear with the inclined cone
    shaft axis, so a lock / gear mate against the shaft holds the tuned phase.
    """
    centre = cone_station(station)
    return await place_component(
        adapter,
        part,
        [
            centre[0] + (face / 2.0) * SIN_I,
            Y_DRIVE,
            centre[2] - (face / 2.0) * COS_I,
        ],
        [0.0, -INCLINE_DEG, 0.0],
        ROT_Y_INCLINE,
        ground=False,
        configuration=configuration,
        label=label,
    )


async def build(adapter) -> dict[str, str]:
    check("create_assembly", await adapter.create_assembly())

    # =================== structure (ground = fixed) ====================
    # Stationary arbor, the pedestals/posts, and the disengaged alignment
    # rig are the fixed reference frame the moving train mates against.
    arbor = await place_component(
        adapter, "cylinder-gear-shaft",
        [X_DRUM, Y_DRIVE, -ARBOR_LENGTH / 2.0],
        [90.0, 0.0, 0.0], ROT_X_POS90, label="cylinder arbor",
    )
    pedestal = await place_component(
        adapter, "crank-pedestal",
        [X_CRANK, Y_BASE_TOP, PEDESTAL_Z], [0.0, 0.0, 0.0], IDENTITY,
    )
    # South pedestal only (M6.5): the arbor's north end clamps into the
    # rocker-arm-support's east-flank boss bore (frame.SLDASM) - the back
    # view (p5) shows the drum running straight into that casting, and a
    # pedestal at z +92 cannot coexist with the frustum footprint.
    await place_component(
        adapter, "arbor-pedestal",
        [X_DRUM, Y_BASE_TOP, -ARBOR_PEDESTAL_Z], [0.0, 0.0, 0.0], IDENTITY,
        label=f"arbor-pedestal z={-ARBOR_PEDESTAL_Z:g}",
    )
    ppost = cone_station(PIVOT_POST_STATION)
    # The cone-pivot-post is the SWING BRACKET (ch.12, p.18 "pivot"): floated so
    # the whole cone set can swing horizontally out of mesh about its vertical
    # axis (p1). Pinned at the engaged rest pose by a suppressible angle driver
    # in the joints section.
    pivot_post = await place_component(
        adapter, "cone-pivot-post",
        [ppost[0], Y_BASE_TOP, ppost[2]], [0.0, -INCLINE_DEG, 0.0], ROT_Y_INCLINE,
        ground=False, label="cone-pivot-post (swing bracket, engaged rest)",
    )
    kpost = cone_station(KNOB_POST_STATION)
    await place_component(
        adapter, "cone-knob-post",
        [kpost[0], Y_BASE_TOP, kpost[2]], [0.0, -INCLINE_DEG, 0.0], ROT_Y_INCLINE,
    )

    # alignment pinion SWING GROUP (ch. 25, p.66): the two brackets pivot on the
    # torque shaft and journal the pinion drum; the whole group swings to engage
    # the cylinder train (p2). Floated (ground=False) and joined by a swing
    # revolute + suppressible park driver in the joints section -- the rest pose
    # is today's DISENGAGED state (p.68 "gap").
    align_pinion = await place_component(
        adapter, "alignment-pinion",
        [PINION_X, PINION_Y, PINION_Z_FRONT], [0.0, 0.0, 0.0], IDENTITY,
        ground=False, label="alignment-pinion (disengaged rest)",
    )
    pinion_brackets: dict[str, str] = {}
    for tag, z0 in (
        ("front", PINION_Z_FRONT - STRAP_T - STRAP_AIR),
        ("back", PINION_Z_BACK + STRAP_AIR),
    ):
        pinion_brackets[tag] = await place_component(
            adapter, "pinion-bracket",
            [PIVOT_X, PIVOT_Y, z0], [0.0, 0.0, STRAP_LEAN_DEG], rot_z_rows(STRAP_LEAN_DEG),
            ground=False, label=f"pinion-bracket {tag} (leaning onto the arbor stub)",
        )
    for tag, z0 in (("front", BLOCK_FRONT_Z0), ("back", BLOCK_BACK_Z0)):
        await place_component(
            adapter, "pinion-pivot-block",
            [BLOCK_X, PIVOT_Y, z0], [0.0, 0.0, 0.0], IDENTITY,
            label=f"pinion-pivot-block {tag}",
        )
    pivot_shaft = await place_component(
        adapter, "pinion-pivot-shaft",
        [PIVOT_X, PIVOT_Y, PIVOT_SHAFT_Z0], [0.0, 0.0, 0.0], IDENTITY,
    )
    await place_component(
        adapter, "pinion-lift-rod",
        [LIFT_X, PIVOT_Y, LIFT_ROD_Z0], [0.0, 0.0, 0.0], IDENTITY,
        label="pinion-lift-rod (cam pins parked down)",
    )
    await place_component(
        adapter, "pinion-lever",
        [LIFT_X, PIVOT_Y, LEVER_Z], [0.0, 0.0, -LEVER_TILT_DEG], rot_z_rows(-LEVER_TILT_DEG),
        label="pinion-lever (clamp on the lift rod front end)",
    )
    await place_component(
        adapter, "pinion-handle",
        [PINION_X, PINION_Y, HANDLE_Z], [0.0, 0.0, -HANDLE_TILT_DEG], rot_z_rows(-HANDLE_TILT_DEG),
        label="pinion-handle (on the front arbor stub)",
    )

    # =================== cone cluster (driven, on-solution) ====================
    cone_shaft = await place_component(
        adapter, "cone-gear-shaft",
        CONE_ORIGIN, [0.0, -INCLINE_DEG, 0.0], ROT_Y_INCLINE, ground=False,
    )
    gear64 = await _place_on_shaft(
        adapter, "crank-drive-gear", GEAR64_STATION, GEAR64_FACE,
        label="crank-drive-gear (perpendicular, journal seat)",
    )
    cone_gears: list[tuple[int, str]] = []
    for j in range(20):
        teeth = _config.cone_teeth(j)
        cfg = f"T{teeth:03d}"
        cg = await _place_on_shaft(
            adapter, "cone-gear", SHAFT_T120_STATION + j * SEAT_PITCH, CONE_FACE,
            configuration=cfg, label=f"cone-gear {cfg}",
        )
        cone_gears.append((teeth, cg))

    # =================== cylinder drum (driven, free on the arbor) =============
    cyl_gears: list[str] = []
    for j in range(20):
        z_j = Z_DRUM0 + Z_PITCH * j
        cyl = await place_component(
            adapter, "cylinder-gear",
            [X_DRUM, Y_DRIVE, z_j - DRUM_FACE / 2.0], [0.0, 0.0, 1.5], rot_z_rows(1.5),
            ground=False, label=f"cylinder-gear {j}",
        )
        cyl_gears.append(cyl)

    # =================== crank (driven, on-solution) ===========================
    crankshaft = await place_component(
        adapter, "crankshaft",
        [X_CRANK, Y_DRIVE, CRANKSHAFT_Z0], [90.0, 0.0, 0.0], ROT_X_POS90, ground=False,
    )
    pinion = await place_component(
        adapter, "crank-pinion",
        [X_CRANK, Y_DRIVE, PINION_TOOTH_Z - PINION_FACE / 2.0],
        [0.0, 0.0, 11.25], rot_z_rows(11.25),  # +11.25 = half pitch, tooth-in-gap
        ground=False, label="crank-pinion (centred on the 64T contact tooth)",
    )
    removable = await place_component(
        adapter, "transgear-removable",
        [X_CRANK, Y_DRIVE, REMOVABLE_Z0], [0.0, 0.0, 0.0], IDENTITY,
        ground=False, configuration="T12",
        label="transgear-removable (crank chain wheel T12)",
    )
    arm = await place_component(
        adapter, "crank-arm",
        [X_CRANK, Y_DRIVE, CRANK_ARM_Z0], [0.0, 0.0, 0.0], IDENTITY, ground=False,
    )
    handle = await place_component(
        adapter, "crank-handle",
        [X_CRANK + ARM_C2C, Y_DRIVE, CRANK_ARM_Z0], [0.0, 90.0, 0.0], ROT_Y_POS90,
        ground=False,
    )

    # =================== joints ================================================
    # Crankshaft revolute in the green pedestal: coincident axis-to-axis
    # (4 DOF) + an axial plane distance (1 DOF). Its spin is the single crank
    # driver, pinned via the handle below. The crankshaft axis is local +Y ->
    # assembly Z (ROT_X_POS90), so its Top Plane is the axial reference.
    cs_o = _org(adapter, crankshaft)
    await coincident_mate(
        adapter,
        named_ref(f"Axis1@{crankshaft}", "AXIS"),
        named_ref(f"Axis1@{pedestal}", "AXIS"),
        label="crankshaft radial", verify=(crankshaft, cs_o),
    )
    await distance_driver(
        adapter,
        named_ref(f"Top Plane@{crankshaft}", "PLANE"),
        named_ref("Front Plane", "PLANE"),
        abs(cs_o[2]),
        label=f"crankshaft axial d={abs(cs_o[2]):.2f}", verify=(crankshaft, cs_o),
    )
    # Keyed crank chain: arm, handle, the T12 chain wheel and the 16T pinion
    # all turn rigidly with the crankshaft (a lock preserves the inserted
    # pose and shares the crankshaft's single spin DOF).
    crank_axis = named_ref(f"Axis1@{crankshaft}", "AXIS")
    await lock_mate(
        adapter, named_ref(f"Axis1@{arm}", "AXIS"), crank_axis, label="crank-arm keyed",
    )
    await lock_mate(
        adapter, named_ref(f"Axis1@{handle}", "AXIS"), crank_axis, label="crank-handle keyed",
    )
    await lock_mate(
        adapter, named_ref(f"Axis1@{removable}", "AXIS"), crank_axis,
        label="T12 chain wheel keyed",
    )
    await lock_mate(
        adapter, named_ref(f"Axis2@{pinion}", "AXIS"), crank_axis, label="16T pinion keyed",
    )

    # =============== cone pivot post swing (p1 disengage DOF) ==============
    # The post is the swing bracket: the whole cone set swings horizontally out
    # of mesh about its vertical pivot (ch.12, p.18). Pin the floated post with
    # three locating drivers that leave ONLY the rotation about the vertical
    # axis (Axis2): a Top-plane distance (upright + height) and the vertical
    # axis's distance to the Right/Front planes (plan X/Z). Then a suppressible
    # ANGLE PARK DRIVER holds today's ENGAGED orientation (the incline dihedral).
    # The cone shaft stays journaled to the post (below) and rides the swing, so
    # the validated 20-gear mesh is untouched in `rest`; suppress the angle
    # driver to articulate the disengage.
    post_o = _org(adapter, pivot_post)
    await distance_driver(
        adapter,
        named_ref(f"Top Plane@{pivot_post}", "PLANE"), named_ref("Top Plane", "PLANE"),
        abs(post_o[1]),
        label=f"cone-post height d={abs(post_o[1]):.2f}", verify=(pivot_post, post_o),
    )
    await distance_driver(
        adapter,
        named_ref(f"Axis2@{pivot_post}", "AXIS"), named_ref("Right Plane", "PLANE"),
        abs(post_o[0]),
        label=f"cone-post pivot-X d={abs(post_o[0]):.2f}", verify=(pivot_post, post_o),
    )
    await distance_driver(
        adapter,
        named_ref(f"Axis2@{pivot_post}", "AXIS"), named_ref("Front Plane", "PLANE"),
        abs(post_o[2]),
        label=f"cone-post pivot-Z d={abs(post_o[2]):.2f}", verify=(pivot_post, post_o),
    )
    await angle_driver(
        adapter,
        named_ref(f"Right Plane@{pivot_post}", "PLANE"), named_ref("Right Plane", "PLANE"),
        INCLINE_DEG,
        label=f"cone-post swing park (p1, engaged a={INCLINE_DEG:.2f})",
        verify=(pivot_post, post_o),
    )

    # Cone shaft revolute in the black pivot post: coincident + an axial plane
    # distance along the inclined axis (the shaft's local Z, read live). Its
    # spin is driven by the 16T -> 64T mesh, not pinned here.
    a_s = component_transform(adapter, cone_shaft)
    cone_o = [a_s[9] * 1000.0, a_s[10] * 1000.0, a_s[11] * 1000.0]
    cone_axis_dir = [a_s[6], a_s[7], a_s[8]]  # image of local Z = inclined shaft axis
    post_o = _org(adapter, pivot_post)
    d_axial = abs(sum((cone_o[k] - post_o[k]) * cone_axis_dir[k] for k in range(3)))
    await coincident_mate(
        adapter,
        named_ref(f"Axis1@{cone_shaft}", "AXIS"),
        named_ref(f"Axis1@{pivot_post}", "AXIS"),
        label="cone-shaft radial", verify=(cone_shaft, cone_o),
    )
    await distance_driver(
        adapter,
        named_ref(f"Front Plane@{cone_shaft}", "PLANE"),
        named_ref(f"Front Plane@{pivot_post}", "PLANE"),
        d_axial,
        label=f"cone-shaft axial d={d_axial:.2f}", verify=(cone_shaft, cone_o),
    )
    # The 64T crank-drive gear and the 20 cone gears are one rigid stepped
    # cluster keyed to the cone shaft.
    cone_axis = named_ref(f"Axis1@{cone_shaft}", "AXIS")
    await lock_mate(
        adapter, named_ref(f"Axis2@{gear64}", "AXIS"), cone_axis,
        label="64T keyed to cone shaft",
    )
    for teeth, cg in cone_gears:
        await lock_mate(
            adapter, named_ref(f"Axis1@{cg}", "AXIS"), cone_axis,
            label=f"cone-gear T{teeth:03d} keyed",
        )
    # 16T pinion (keyed to the crank) drives the 64T -> the cone cluster turns.
    await gear_mate(
        adapter,
        named_ref(f"Axis2@{pinion}", "AXIS"),
        named_ref(f"Axis2@{gear64}", "AXIS"),
        _config.machine("gear_train", "crank_drive_ratio"), label="16T:64T crank drive",
    )

    # Each cylinder gear runs free on the stationary arbor (coincident + axial,
    # leaving its spin) and meshes its cone gear k at ratio [120-6k : 120] --
    # the gear mate is the sole rotational constraint, so it holds the tuned
    # tooth phase without nudging the gear (validated keystone, M6).
    for j, cyl in enumerate(cyl_gears):
        cyl_o = _org(adapter, cyl)
        await coincident_mate(
            adapter,
            named_ref(f"Axis2@{cyl}", "AXIS"),
            named_ref(f"Axis1@{arbor}", "AXIS"),
            label=f"cylinder-gear {j} radial", verify=(cyl, cyl_o),
        )
        await distance_driver(
            adapter,
            named_ref(f"Front Plane@{cyl}", "PLANE"),
            named_ref("Front Plane", "PLANE"),
            abs(cyl_o[2]),
            label=f"cylinder-gear {j} axial d={abs(cyl_o[2]):.2f}", verify=(cyl, cyl_o),
        )
        teeth, cg = cone_gears[j]
        await gear_mate(
            adapter,
            named_ref(f"Axis1@{cg}", "AXIS"),
            named_ref(f"Axis2@{cyl}", "AXIS"),
            [teeth, 120], label=f"cone T{teeth:03d}:cyl120 ch{j:02d}",
        )

    # DRIVER #1 (the single machine input): the crank angle, pinned by the
    # handle ball's height. The handle is keyed to the crankshaft and its axis
    # sits ARM_C2C from the crank axis, so the spin_driver's y-sensitivity is
    # well-conditioned (Top-plane distance picked, |Δx| >> |Δy|).
    crank_o = _org(adapter, crankshaft)
    handle_o = _org(adapter, handle)
    await spin_driver(
        adapter,
        named_ref(f"Axis1@{handle}", "AXIS"),
        (crank_o[0], crank_o[1]),
        (handle_o[0], handle_o[1]),
        label="crank angle driver (#1)",
        verify=(handle, handle_o),
    )

    # =================== pinion swing group (p2 engage DOF) ====================
    # The two brackets + the alignment-pinion are ONE rigid body that pivots on
    # the torque shaft to swing the pinion into mesh with the cylinder train
    # (ch.25, p.66). Lock the group rigid (crank-chain pattern), ground it with
    # ONE revolute about the pivot shaft (coincident axes + an axial plane
    # distance), and pin the swing with a suppressible PARK DRIVER at today's
    # DISENGAGED pose. `rest` is bit-exact; suppress the driver (motion study /
    # a pinion_engaged config) to articulate the engage swing. The pinion-handle
    # stays grounded for now -- it coincides at rest; floating + locking it is
    # deferred to the engaged config (where the swung pose would otherwise
    # detach it).
    fb = pinion_brackets["front"]
    bb = pinion_brackets["back"]
    fb_o = _org(adapter, fb)
    # Rigid group: back bracket + pinion locked to the front bracket. The pivot
    # bores (Axis1) of both straps are collinear on the shaft; the pinion axis
    # (Axis1) is collinear with each strap's arbor bore (Axis2) -- STRAP_C2C spans
    # pivot->pinion exactly (geometry self-check above), so the locks preserve the
    # inserted pose.
    await lock_mate(
        adapter, named_ref(f"Axis1@{bb}", "AXIS"), named_ref(f"Axis1@{fb}", "AXIS"),
        label="pinion back-bracket keyed",
    )
    await lock_mate(
        adapter, named_ref(f"Axis1@{align_pinion}", "AXIS"), named_ref(f"Axis2@{fb}", "AXIS"),
        label="alignment-pinion keyed to the front bracket",
    )
    # Swing revolute on the torque shaft: the front strap's pivot bore (Axis1)
    # coincident with the shaft central axis (Axis1) + an axial plane distance.
    # Leaves exactly the swing DOF.
    await coincident_mate(
        adapter,
        named_ref(f"Axis1@{fb}", "AXIS"), named_ref(f"Axis1@{pivot_shaft}", "AXIS"),
        label="pinion swing radial", verify=(fb, fb_o),
    )
    await distance_driver(
        adapter,
        named_ref(f"Front Plane@{fb}", "PLANE"), named_ref("Front Plane", "PLANE"),
        abs(fb_o[2]),
        label=f"pinion swing axial d={abs(fb_o[2]):.2f}", verify=(fb, fb_o),
    )
    # Swing PARK DRIVER (suppressible): pin the swing via the pinion axis, which
    # sits STRAP_C2C off the pivot, so the spin_driver's in-plane sensitivity is
    # well-conditioned. Suppressing it frees the engage articulation.
    shaft_o = _org(adapter, pivot_shaft)
    pin_o = _org(adapter, align_pinion)
    await spin_driver(
        adapter,
        named_ref(f"Axis1@{align_pinion}", "AXIS"),
        (shaft_o[0], shaft_o[1]),
        (pin_o[0], pin_o[1]),
        label="pinion swing park driver (p2, disengaged rest)",
        verify=(align_pinion, pin_o),
    )

    assert_components_fully_defined(adapter)
    check_no_interference(adapter)
    return await save_assembly_and_images(adapter, ASM_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
