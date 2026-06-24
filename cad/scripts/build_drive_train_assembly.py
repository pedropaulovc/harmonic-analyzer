r"""Reproduction script: drive-train subassembly (book ch. 11-13, 30).

The complete drive train in machine coordinates (assembly origin = base
origin; base top face at y = 50.8, drive height 76 above it):

* cone set: a TRUE CONE -- all 20 gears AND the 64T crank-drive gear
  seated perpendicular to the stepped shaft (p.18/p.20 photos), the
  shaft inclined 21.1 deg in PLAN, big-end journal in the black pivot
  post, thin 1/8" tip UNSUPPORTED for now (the cone is mis-positioned;
  its small-end bracket is deferred to the cone-position rework, 2026-06-19).
* cylinder drum: 20 identical 120T gears spinning freely on the
  stationary arbor along Z at (-47.5, 126.8) (M6.2 keyway refutation),
  carried by the SOUTH arbor pedestal; the arbor is shortened (200 -> 176) so
  its north end clears the now-solid rocker-arm-support (the old support boss
  bore is gone), the north-end support deferred to the cone-position rework;
  notches up = cosine setup (pp. 66-67).
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

NOTE: the worked numbers in this docstring (incline 21.1 deg, radius step
2.54, z-pitch 7.5, seat 6.5839, DP 30, 50.8 radii) illustrate the METHOD
at the retired DP-30 geometry. The live values are computed from config
at OD 62.2 / DP 49.82 (incline 12.5188 deg, step 1.5295, seat 6.889, 64T
rescaled to DP 26.57); the alignment pinion has been REMOVED (see below).

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
stationary arbor and the pedestals/posts -- is grounded; the crank
chain, the cone cluster and the 20 cylinder
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

    uv run python cad\scripts\build_drive_train_assembly.py
"""

from __future__ import annotations

import math
import sys

import _config
from _common import (
    check,
    run_build,
)
from _assembly import (
    angle_driver,
    apply_component_color,
    assert_components_fully_defined,
    check_no_interference,
    coincident_mate,
    component_transform,
    distance_driver,
    gear_mate,
    lock_mate,
    named_ref,
    place_component,
    save_assembly_and_images,
    spin_driver,
)

ASM_NAME = "drive-train"

Y_BASE_TOP = 50.8  # harmonic-base top face
Y_DRIVE = Y_BASE_TOP + 76.0  # 126.8: crank, cone big end and arbor axes

DP_TRAIN = _config.machine("gear_train", "diametral_pitch")  # cad/config/machine.yaml (DIMENSIONS.md ch12)
DP_CRANK = _config.machine("gear_train", "crank_drive_diametral_pitch")  # 26.57: 64T==cone T120 radius
ADDENDUM = 25.4 / DP_TRAIN  # 0.510 at DP 49.82

# The four smallest cone gears read "more yellow ... a harder metal" (ch.12 p.21):
# a high-zinc yellow metal (Muntz/manganese bronze). Tinted per-INSTANCE here (see
# apply_component_color / build_cone_gear.py rationale), the part stays brass.
MUNTZ_YELLOW = _config.palette("muntz_yellow")
TIP_TEETH = {int(c[1:]) for c in _config.materials().get("cone_tip_gear_configs", [])}
WORKING_DEPTH = 2.0 * ADDENDUM  # 1.020: full tooth interleave depth
RADIUS_STEP = 3.0 * 25.4 / DP_TRAIN  # 1.5295: pitch-radius step per 6 teeth
CONE_T120_PITCH_R = (120.0 / DP_TRAIN) * 25.4 / 2.0  # 30.59: largest cone gear pitch radius

# Frame-locked machine grid (M6.3 lineage -- the drum planes anchor the
# gates, cams, rockers and bars; nothing here may move them).
_DRUM_SEAT_NOMINAL = _config.machine("cone_incline", "drum_seat_nominal_mm")  # 7.2204 (OD 62.2)
Z_PITCH = _DRUM_SEAT_NOMINAL * math.cos(math.asin(RADIUS_STEP / _DRUM_SEAT_NOMINAL))  # 7.0566: drum z-pitch
X_DRUM = -47.5  # rocker-support boss bore + arbor pedestal
Z_DRUM0 = _config.machine("channels", "station_z0_mm")  # -67.1 drum gear 0 plane (shared station anchor)

# True-cone incline (M6.7, exact tracking -- see module docstring). Values are
# at the OD-62.2 / DP 49.82 re-anchor (was 21.10 deg at the retired DP 30).
SIN_I = RADIUS_STEP / Z_PITCH  # 0.21675
COS_I = math.sqrt(1.0 - SIN_I * SIN_I)  # 0.97623
TAN_I = SIN_I / COS_I
SEC_I = 1.0 / COS_I
INCLINE_DEG = math.degrees(math.asin(SIN_I))  # 12.5182
SEAT_PITCH = Z_PITCH * COS_I  # 6.8888: seat pitch along the shaft

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
DRUM_TIP_X = X_DRUM + (122.0 / DP_TRAIN) * 25.4 / 2.0  # -16.40 at DP 49.82
PEN_EDGE_SLACK = _config.fit("cone_drum_oblique_mesh", "edge_slack_mm")  # cad/config/tolerances.yaml
PEN_MID = WORKING_DEPTH - PEN_EDGE_SLACK - (DRUM_FACE / 2.0) * TAN_I  # 0.565
X_PITCH = DRUM_TIP_X + ADDENDUM * SEC_I - PEN_MID  # -16.01 at DP 49.82


def cone_seat(j: int) -> tuple[float, float]:
    """(x, z) centre of cone gear j: pitch-projected x, r*sin(i) north."""
    r = CONE_T120_PITCH_R - RADIUS_STEP * j
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
R64 = (64.0 / DP_CRANK) * 25.4 / 2.0  # 30.59: 64T pitch radius (== cone T120 by design)
R16 = (16.0 / DP_CRANK) * 25.4 / 2.0  # 7.65: 16T crank-pinion pitch radius

# Crank: the 64T's contact tooth (azimuth 0, toward +x) sits R64*sin(i)
# north of its centre; the pinion is centred on that plane and the mesh
# backs off so the +-5 oblique dive caps short of working depth. Slack
# 1.10 is checker-arbitrated like the drum mesh's (the long +-1.8 dive
# across the 64T face squeezes flanks: 0.15 left 1.48 mm^3, 0.60 left
# 0.23, 0.90 a 0.00 skin).
ADD16 = 25.4 / DP_CRANK  # crank-pinion addendum
WORK16 = 2.0 * ADD16  # 1.912 at DP 26.57
PEN16_EDGE_SLACK = 1.10
PEN16_MID = WORK16 - PEN16_EDGE_SLACK - (GEAR64_FACE / 2.0) * SIN_I  # 0.275
PINION_TOOTH_Z = GEAR64_SEAT[2] + R64 * SIN_I  # -38.32
X_CRANK = (
    GEAR64_SEAT[0] + R64 * COS_I + R16 + (ADD16 * (1.0 + SEC_I) - PEN16_MID)
)  # ~58 at DP 26.57 -- the crank-drive pair scaled with the cone, so the
# crankshaft moved well inboard of the old +118 (the +122 pedestal photo no
# longer holds; flagged in DIMENSIONS.md as a 62.2-anchor consequence)

ARBOR_SOUTH_Z = -98.0  # arbor south end: 1.0 clear of the portal south-plate
# back face -99 (= cylinder-gear-shaft origin, placed by its south end).
ARBOR_LENGTH = 176.0  # shortened from 200 (2026-06-19): the now-solid portal
# north upright occupies the arbor's old north reach, so the arbor stops at
# z -98+176 = +78, clearing the frustum south face (~+85.6 at the drive axis
# y 126.8) by ~7.6 and still covering the drum stack (north end z +70.6). North
# end unsupported for now -- the north pedestal is DEFERRED to the cone-position
# rework. Must match cylinder-gear-shaft SHAFT_LENGTH.
CRANKSHAFT_Z0 = -150.0  # front end; crank-arm hub at +12 (PIN_HOLE_HEIGHT)
CRANKSHAFT_LENGTH = 120.0  # build_crankshaft.py SHAFT_LENGTH
CRANK_ARM_Z0 = CRANKSHAFT_Z0 + 8.0  # hub centre 12 - half thickness 4
ARM_C2C = 66.0  # handle pivot from the shaft axis (rederived from the ch30
# eight-views, see build_crank_arm.py; was 150 -- a down-pointing 150 arm put
# the handle below the table)
REMOVABLE_Z0 = -85.6  # mounted T12 (face 5.0) against the pedestal north face:
# the crank-end chain wheel is the small removable gear (ch. 23 -- the bead
# chain rides its m2 teeth; v2_gears_010 shows the small steel wheel on the
# crank pedestal), band -85.6..-80.6
PEDESTAL_Z = -108.6  # crank pedestal centre (front face inside base edge)
ARBOR_PEDESTAL_Z = 90.5  # SOUTH end only (at z -90.5): the rocker support no
# longer clamps the arbor, but the solid portal north upright leaves no room for
# a north pedestal where the arbor's north end was. South block front face -98.5
# clears the portal south-plate back face -99 by 0.5. North-end support deferred.

# The pinion must sit fully on the crankshaft.
if PINION_TOOTH_Z + PINION_FACE / 2.0 > CRANKSHAFT_Z0 + CRANKSHAFT_LENGTH:
    raise AssertionError("crankshaft too short for the M6.7 pinion station")

# Posts: the rotated 25x20 pivot block reaches 10*cos+12.5*sin = 13.83
# in machine z from its centre; at station -1.0 its north corner stops
# 1.0 short of the perpendicular 64T's south face, with the shaft
# engaging the first 9 mm of the journal bore (blind-bearing look,
# p.18: the shaft end disappears into the black bracket).
PIVOT_POST_STATION = -1.0
# --- cone small-end support: DEFERRED to the cone-position rework -------------
# The old green Ø32 round tip-rest post (cone-knob-post, p.18) never fit the
# rescaled north region at OD 62.2 and was retired. A dedicated small-end bracket
# is the right fix, but the cone is currently mis-positioned and the whole north
# drive region will be re-laid out; placing a bracket now (against the wrong cone
# axis) only collides with the solid portal, so the cone tip is left unsupported
# until that rework (2026-06-19).

# --- alignment pinion: REMOVED 2026-06-18 ---------------------------
# The 42T zeroing pinion no longer fits the rescaled frame at OD 62.2:
# its Ø22.4 drum cannot thread the 12.6 mm channel between the rocker-
# support frustum (x -28.45) and the rescaled 64T (west edge x -15.89).
# The whole swing group (drum, 2 straps, 2 blocks, torque shaft, lift
# rod, lever, handle) is dropped from the assembly pending a rework.
# See dimensions.yaml ch.25 + the build docstring.


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
        [X_DRUM, Y_DRIVE, ARBOR_SOUTH_Z],
        [90.0, 0.0, 0.0], ROT_X_POS90, label="cylinder arbor",
    )
    pedestal = await place_component(
        adapter, "crank-pedestal",
        [X_CRANK, Y_BASE_TOP, PEDESTAL_Z], [0.0, 0.0, 0.0], IDENTITY,
    )
    # South arbor pedestal only (2026-06-19): the rocker support's arbor-clamp
    # boss is gone with the portal unification, AND the now-solid portal north
    # upright occupies the space the arbor's north end used to pass through. The
    # arbor is shortened to clear the portal (ARBOR_LENGTH) and its north end is
    # left unsupported for now -- the dedicated north-end support (pedestal) and
    # the cone small-end bracket are DEFERRED to the cone-position rework, since
    # the cone is currently mis-positioned and that region will be re-laid out.
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
    # (cone small-end support deferred to the cone-position rework -- see the
    # note above PIVOT_POST_STATION; the cone tip is unsupported for now.)

    # =================== cone cluster (driven, on-solution) ====================
    cone_shaft = await place_component(
        adapter, "cone-gear-shaft",
        CONE_ORIGIN, [0.0, -INCLINE_DEG, 0.0], ROT_Y_INCLINE, ground=False,
    )
    gear64 = await _place_on_shaft(
        adapter, "crank-drive-gear", GEAR64_STATION, GEAR64_FACE,
        label="crank-drive-gear (perpendicular, journal seat)",
    )
    # The full 20-gear cone stack is ALWAYS built (it is one rigid keyed cluster
    # derived from the full channel table); only the cylinder drum + its cam
    # followers downstream follow the TEMPORARY active_count (see machine.yaml
    # channels.active_count / _config.active_count).
    cone_gears: list[tuple[int, str]] = []
    for j in range(20):
        teeth = _config.cone_teeth(j)
        cfg = f"T{teeth:03d}"
        cg = await _place_on_shaft(
            adapter, "cone-gear", SHAFT_T120_STATION + j * SEAT_PITCH, CONE_FACE,
            configuration=cfg, label=f"cone-gear {cfg}",
        )
        if teeth in TIP_TEETH:  # the four hard yellow tip gears
            await apply_component_color(adapter, cg, MUNTZ_YELLOW)
        cone_gears.append((teeth, cg))

    # =================== cylinder drum (driven, free on the arbor) =============
    # TEMPORARY: only the first active_count cylinder gears (and, via the channel
    # assembly, their cam followers) are built — the build-performance reduction.
    # Cone gears 0..19 above stay; cone gears active_count..19 simply mesh nothing
    # (they remain keyed to the cone shaft, fully defined, harmless).
    cyl_gears: list[str] = []
    for j in range(_config.active_count()):
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
    # Crank rest pose: the arm hangs straight DOWN (ch30 eight-views -- the
    # handle reads "down" in all eight roll angles, which only a -Y arm does,
    # since a downward vector lies on the views' vertical rotation axis). The
    # arm part extrudes along its local +X; rot_z(-90) maps that to assembly -Y.
    arm = await place_component(
        adapter, "crank-arm",
        [X_CRANK, Y_DRIVE, CRANK_ARM_Z0], [0.0, 0.0, -90.0], rot_z_rows(-90.0),
        ground=False,
    )
    # Handle pivot rides the arm tip, now ARM_C2C below the crankshaft. Its grip
    # axis stays parallel to the crankshaft (ROT_Y_POS90 -> assembly -Z).
    handle = await place_component(
        adapter, "crank-handle",
        [X_CRANK, Y_DRIVE - ARM_C2C, CRANK_ARM_Z0], [0.0, 90.0, 0.0], ROT_Y_POS90,
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

    # DRIVER #1 (the single machine input): the crank angle. The arm hangs at
    # bottom-dead-centre (straight down, ch30), which is a kinematic SINGULARITY
    # for a single-coordinate distance driver -- the two distance solutions
    # merge there, so SW reports the pin as over-defining (rank-deficient
    # against the lock+axial mates) even though a free spin DOF remains, and the
    # build hard-fails. An ANGLE mate's Jacobian is non-degenerate at every
    # pose, so it pins the spin cleanly at BDC (the same formulation the
    # cone-post swing-park above uses). The arm, handle, T12 wheel and pinion
    # are one locked rigid body, so pinning the arm's angle pins the crank.
    # Read the dihedral live from the arm's rest transform (the assembly-x
    # component of its local +X = its Right-plane normal); _mate's flip-recovery
    # resolves the sign, and the handle-origin verify (the arm origin sits ON
    # the spin axis, so only the offset handle proves the pose) confirms the
    # rigid crank landed back on its book-accurate down pose.
    handle_o = _org(adapter, handle)
    a_arm = component_transform(adapter, arm)
    crank_angle = math.degrees(math.acos(max(-1.0, min(1.0, a_arm[0]))))
    await angle_driver(
        adapter,
        named_ref(f"Right Plane@{arm}", "PLANE"),
        named_ref("Right Plane", "PLANE"),
        crank_angle,
        label=f"crank angle driver (#1, BDC a={crank_angle:.2f})",
        verify=(handle, handle_o),
    )

    assert_components_fully_defined(adapter)
    check_no_interference(adapter)
    return await save_assembly_and_images(adapter, ASM_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
