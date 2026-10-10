r"""Reproduction script: drive-train subassembly (book ch. 11-13, 30).

The complete drive train in machine coordinates (assembly origin = base
origin). The raised post journal and swing-plate seat define the common
drive plane; crank height is re-solved against the unrelieved platform:

* cone set: a TRUE CONE -- all 20 gears AND the 64T crank-drive gear
  seated perpendicular to the stepped shaft (p.18/p.20 photos), the
  shaft inclined in PLAN and carried at BOTH ends ON the cone swing
  platform (p.18: the wedge plate labelled "pivot" at its tip): big end
  journaled in the green pivot post, with its 1/32-inch terminal journal's
  end play located by the stack collar and cup-ended adjuster in the tip
  block. The source-owned tip stack fixes the vertical pivot at the TIP end,
  so the whole set swings horizontally out of mesh as one unit -- the p1
  disengage DOF; pivoting at the tip gives the big gears (which need
  the most working-depth separation) the largest throw.
* cylinder drum: 20 identical 120T gears spinning freely on the stationary
  arbor along Z at the shared CAM_SHAFT_XY, carried by pedestals at both ends.
  The complete arbor/support bank follows the raised drive-axis datum;
  each asymmetric gear/cam sandwich is turned end-for-end while its local +Y
  cosine phase remains up (pp. 66-67).
* crankshaft along Z in the merged green column (cone-pivot-post: big-end
  journal + crank pedestal, ONE casting riding the swing plate), ABOVE the
  64T (ch30 GT:
  the crank axle triangulates to y 144.8 -- a near-vertical 16T:64T mesh):
  crank arm, separate through hub, handle and 16T pinion inboard. (The T12
  removable crank chain wheel -- ch. 23, the roller chain rides its m2 teeth
  -- is NOT placed here: paper-drive now owns the whole crank->paper chain
  drive, so the single crank wheel lives there, avoiding a duplicate at the
  top level -- codex #189 :605.  Removable MHA-DT-009 crosses hub MHA-DT-031 and
  shaft MHA-DT-011 behind the arm; axial MHA-VN-029 keys only the arm/hub seam at
  six o'clock.)
* alignment pinion (ch. 25): the 32T zeroing drum + its swing rig, parked
  DISENGAGED, inboard of the drum and level with the drive axis (GT).

TRUE-CONE MESH GEOMETRY (M6.7; supersedes the M6.6 canted-vertical
seats, which satisfied the interference checker but visibly deformed
the cone -- user-flagged against the p.18 photo). A gear seated
perpendicular to a shaft inclined i in plan reaches a parallel-axis
drum only with the tooth at the azimuth facing the drum; that contact
tooth sits r*sin(i) SOUTH (along the shaft) of the gear centre and
reaches x = x_centre - r*cos(i). Meshing every station therefore
needs:

The live train uses configured 48DP PA20 cone/drum/alignment teeth and a
normal-24DP PA20 crank pair. ``cone_line`` derives the incline, radius step,
channel pitch and shaft seat pitch from that one configuration; no retired
DP-30 or DP-49.82 worked example defines the current layout.

* a centre-x grid stepping by RADIUS_STEP*cos(i),
* each centre z at z_drum_j + r_j*sin(i) -- NORTH of its drum plane,
  so the contact tooth lands exactly in that plane.

Those centres lie on ONE straight shaft iff sin(i) = RADIUS_STEP/Z_PITCH,
with seat pitch Z_PITCH*cos(i) along the shaft (cone_line.SEAT_PITCH).
CONE_FACE is that pitch floored to four places, so the gears
stack solid, face to face (user ruling 2026-09-28): the book's
annotated cone figures (face 7, pitch 7.5, stack 150) are mutually
inconsistent with the photo-measured drum grid -- the drum grid wins
(it anchors the gates and all channel machinery).
Self-consistency: tan(cone half-angle) = RADIUS_STEP/SEAT_PITCH =
tan(i), so the cone's drum-side generator runs PARALLEL to the drum
axis -- the p.18 seam.

The engagement is intentionally PARTIAL ("oblique angle ... partial
engagement, distinct wear", ch. 12): the contact tooth crosses the
3 mm drum face obliquely, penetration varying +-DRUM_FACE/2*tan(i)
about its centre value; X_PITCH backs the cone off so the DEEPEST
crossing point stays clear of the configured working depth by
PEN_EDGE_SLACK. Every station follows the same grid, including T006;
the cone spec owns each tip, tooth thickness and gap floor, and
dt_mesh_checks runs the closed-form standard checks of every drum mesh.
The 16T crank pinion mesh is DIFFERENT: on its near-VERTICAL line of
centres the radial interleave is nearly constant across the face, while
the crossing manifests as LATERAL flank misregistration. The 64T is a
true right-hand helical gear at the configured cone incline, with normal
pitch and pressure angle shared by the straight 16T pinion
(build_dt_crank_drive_gear.py), and
the pinion stands PROUD of the pivot post's uncut casting face (img06:
no relief pocket in the casting). Its south tooth face seats 0.25 mm
north of that boss face; the span checks below keep it off the T120
and cover at least 85% of the grown 64T row. The fixed-centre
mesh's only backlash requirement is positive clearance at the worst
closing corner, checked in closed form by crank_mesh_stack.
The perpendicular 64T presents its contact tooth r*cos(alpha)*sin(i)
north of its centre (alpha = the contact azimuth from the in-plane
horizontal).

Positions per cad/DIMENSIONS.md ch. 13 "Drive-train layout" + "Drive
supports". Tooth phasing: every gear script seeds a TOOTH centred on
local +X; the cone gears keep phase 0 (even tooth counts put a tooth
at azimuth 180, the contact azimuth) and the drum gears are
pre-rotated +1.5 deg (half a 3 deg pitch) to receive it tooth-in-gap;
the crank pinion seeds PINION_SEED_DEG -- the generalization of the old
+11.25 half-pitch to the tilted line of centres (it reduces to 11.25 at
the horizontal mesh; see the derivation at the constant).

Mated-DOF strategy (M6 operation simulation): the structure -- the
stationary arbor and the pedestals -- is grounded; the swing platform
is floated (its riders seat on it and follow the p1 swing); the crank
chain, the cone cluster and the 20 cylinder gears are inserted on their
exact machine transforms, so mate flip-recovery has a clean reference and
the tuned tooth phases are preserved, then joined by real kinematic joints.
The crankshaft and cone shaft each get a revolute; the crank hub, arm,
handle and 16T pinion are keyed to the crankshaft, while the 64T and 20 cone
gears are keyed to the cone shaft. A 16T:64T gear mate drives the cone cluster
from the crank, and each cylinder gear meshes its cone gear k at ratio
[120-6k : 120]. The
gear mate is each cylinder gear's sole rotational constraint, so it
holds the cosine-setup phase without nudging the gear. The whole train
is left with exactly ONE operational DOF -- the crank angle.

The saved model is a WORKING kinematic model: the operational DOF (crank
spin, cone-platform swing, pinion engage swing, lift-rod/cam spin) are left
genuinely FREE -- no driver mates exist for them; each freed DOF's drive
spec (entities + rest value + mate side) is recorded into the assembly's
DOF manifest (``.drive-train.dof.json``) for the transient verify:kinematics
replays. Every part is inserted on its exact solved transform, so the saved
pose is deterministic without full definition.

The model is certified AS BUILT: ``assert_free_dof_necessity`` proves each
freed DOF's component family genuinely reads under-constrained;
``check_no_interference`` runs on the as-built pose. Zero interferences
(tangent/coincident contact allowed -- bores ride their shafts). Gear-ratio
sign is verified kinematically by a motion script. The verify ``soundness``
suite re-runs this same DOF gate plus every other gate on the as-built model.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_dt_drive_train_assembly.py
"""

from __future__ import annotations

import math
import os
import sys

import _config
import _telemetry
from _common import (
    _early_bound,
    apply_custom_properties,
    check,
    force_rebuild,
    log,
    run_build,
)
from _drawing_marks import DRAWN_BY
from _printed_tolerance import printed_deviations
from _transforms import ROT_X_NEG90, ROT_Y_180, compose_rows, euler_from_rows
from channel_frame_geom import (
    CAM_SHAFT_XY,
    CYLINDER_LOCK_PHASE_DEG,
)
from dt_cone_pivot_post_installation import (
    CHANNEL_Z0,
    DRUM_X,
    GEAR_AXIS_SHIFT,
    POST_ROTATION_Y_DEG,
)
# The cone journal line and its named stations live in the pure cone_line
# module, so the base's pivot seat and the paper-drive crank sprocket read the
# same numbers without importing this script.
from cone_line import (
    CONE_FACE_STATION_REFERENCE,
    COS_I,
    DRUM_FACE,
    INCLINE_DEG,
    PIVOT_STATION,
    POST_STATION,
    SEAT_PITCH,
    SHAFT_T120_STATION,
    SIN_I,
    T006_NORTH_FACE,
    TIP_BLOCK_NORTH_FACE_PIVOT_OFFSET,
    TIP_BLOCK_PIVOT_OFFSET,
    TIP_BLOCK_STATION,
    X_CRANK,
    X_DRUM,
    Y_BASE_TOP,
    Y_CRANK,
    Y_DRIVE,
    Z_DRUM0,
    Z_PITCH,
    cone_seat,
    cone_station,
)
from _assembly import (
    activate_assembly_contract,
    angle_driver,
    assembly_title_properties,
    apply_component_color,
    assert_component_placed,
    assert_free_dof_necessity,
    author_in_drawing_configurations,
    check_no_interference,
    coincident_mate,
    component_transform,
    distance_driver,
    lock_mate,
    named_ref,
    parallel_mate,
    place_component,
    reledger_to_solved,
    reset_dof_manifest,
    save_assembly_and_images,
    suspend_automatic_assembly_rebuilds,
    whats_wrong,
)
from _assembly_couplings import (
    gear_mate,
    gear_mates_batch,
)
from _assembly_patterns import (
    assert_pattern_targets,
    linear_component_pattern,
    grid_component_pattern,
    PatternDirection,
)
from _interference_contracts import allowed_interference_pairs
from _dt_drive_train_explode import create_drive_train_explode
from dt_drive_train_assembly_spec import COLLAR_PIN_ROLE

# CopyWithMates2 helpers for the cone-gear ladder (#228). NB importing _cwm
# folds it into THIS assembly's recipe/cache key -- intended.
from _cwm import (  # noqa: E402
    component_constrained_status,
    component_mate_count,
    component_mate_dump,
    copy_with_mates,
    external_mate_rows,
    mates_with_owners,
    put_component_pose,
    resolve_entity,
)

ASM_NAME = "dt-drive-train"

if abs(Y_DRIVE - CAM_SHAFT_XY[1]) > 1e-9 or abs(DRUM_X - CAM_SHAFT_XY[0]) > 1e-9:
    raise AssertionError(
        f"drum shaft axis ({DRUM_X}, {Y_DRIVE}) drifted from channel_frame_geom"
        f".CAM_SHAFT_XY {CAM_SHAFT_XY} (gear_train.drive_axis_y_mm) -- the channel"
        " assembly and the error budget read that one"
    )
# The source-owned post journal sits on the 1/4-inch platform. Its raised
# drive-axis datum feeds the arbor pedestals, channel cams and connecting rods.

# Normal pitch and the actual cone incline determine the helical transverse
# pitch; the straight 16T and both gears' addenda use the normal cutter.
from dt_crank_drive_gear_spec import (  # noqa: E402
    CUTTER_DIAMETRAL_PITCH as DP_CRANK_CUTTER,
    DIAMETRAL_PITCH as DP_CRANK,
)

# The four smallest cone gears read "more yellow ... a harder metal" (ch.12 p.21):
# a high-zinc yellow metal (Muntz/manganese bronze). Tinted per-INSTANCE here (see
# apply_component_color / build_dt_cone_gear.py rationale), the part stays brass.
MUNTZ_YELLOW = _config.palette("muntz_yellow")
TIP_TEETH = {int(c[1:]) for c in _config.materials().get("cone_tip_gear_configs", [])}
# The drum z-pitch, incline and pitch-radius step come from cone_line (the
# working train is recentered along the post's unchanged inclined journal).
if POST_ROTATION_Y_DEG != 180.0:
    raise AssertionError(
        "v2 post installation must preserve the exact Ry180 journal line"
    )
# (ch30 p004 post fit).  The cone seats are derived from this same anchor, so
# the complete cone and cylinder families retain all 20 radial mesh depths.
# solved -52.3 +/- 0.9). The drum sits directly UNDER the rocker arms' rod-side
# tips: the rocker pivot (+72.9) is the seesaw mid-span, its rod-pin hole 127.37
# out, and every connecting rod hangs PLUMB from tip to cam (ch30 photos + GT
# rocker-corner triangulation; the earlier "line-2 photogrammetry" oblique-rod
# reading -- drum well clear of the support, LONG rods -- is refuted).
# The whole cone/64T/crank train cascades rigidly off this (DRUM_TIP_X -> X_PITCH ...).
# The cone/crank cluster extends EAST of the drum (machine east = -x, the
# crank side), so every radial x-extent in the cascade below SUBTRACTS.
# Z_DRUM0 (cone_line) is the shared station anchor. Cone seats, cylinder
# faces, and channels translate as one rigid family without re-indexing the
# j-to-j pairs.
if abs(Z_DRUM0 - CHANNEL_Z0) > 1e-9:
    raise AssertionError("channel station_z0 does not carry the fixed-post recenter")

# True-cone incline (M6.7, exact tracking -- see module docstring): SIN_I,
# COS_I, TAN_I, SEC_I, INCLINE_DEG and SEAT_PITCH come from cone_line.

from dt_cone_gear_spec import blank_dia_band as cone_gear_blank_dia_band  # noqa: E402
from dt_cone_gear_spec import FACE_WIDTH as CONE_GEAR_FACE_WIDTH  # noqa: E402
from dt_cone_gear_spec import FACE_WIDTH_BAND as CONE_GEAR_FACE_WIDTH_BAND  # noqa: E402
from dt_cone_gear_spec import outside_dia_mm as cone_gear_outside_dia_mm  # noqa: E402
import alignment_mesh_check  # noqa: E402
import dt_mesh_checks  # noqa: E402

# Closed-form standard checks of the drum meshes, logged by build(); the
# native interference/soundness gate checks the real flanks.
CONE_MESH_CHECKS = dt_mesh_checks.cone_checks()
ALIGNMENT_MESH_CHECK = alignment_mesh_check.alignment_check()


def _cone_tip_radius_max(teeth: int) -> float:
    """Largest cone-gear tip radius the print allows (#834 long addendum).

    The deepened mesh cuts each gear from an oversize blank, so the tip is
    not the standard pitch radius + addendum; clearance checks use the
    printed outside diameter at its upper limit.
    """
    return (cone_gear_outside_dia_mm(teeth) + cone_gear_blank_dia_band(teeth)[0]) / 2.0

# Cone gear face (dt_cone_gear_spec.FACE_WIDTH = 6.8887: the seat pitch floored
# to the four places it prints).  The cone set is a SOLID STACK (user ruling
# 2026-09-28, dt_cone_gear_stack): collar -> 64T -> T120 ... T006, each gear
# bearing on the one before it.  Every station and the T006 -> stack collar
# -> tip-block stack stay on the historical 6.5 reference face: each gear grew
# from its SOUTH face only (seed placed (reference - face)/2 = 0.19435 SOUTH
# of its station), so all north faces -- and the tip end against T006 -- are
# unchanged.  The drum's engaged zone keeps its place about the
# reference centre, inside the face under the stack's axial stations.
CONE_FACE = CONE_GEAR_FACE_WIDTH
from dt_crank_drive_gear_spec import (  # noqa: E402
    FACE_WIDTH as GEAR64_FACE,
    CENTRE_SHIFT_NORTH as GEAR64_CENTRE_SHIFT_NORTH,
    LAYOUT_FACE_WIDTH as GEAR64_LAYOUT_FACE,
    LAYOUT_CENTRE_STATION as GEAR64_LAYOUT_CENTRE_STATION,
    SOUTH_FACE_SHIFT_NORTH as GEAR64_SOUTH_FACE_SHIFT_NORTH,
)
from dt_crank_pinion_spec import FACE_WIDTH as PINION_FACE  # noqa: E402

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
# DRUM_TIP_X, PEN_EDGE_SLACK, PEN_MID and X_PITCH (the mesh anchor above)
# come from cone_line, with cone_seat(j).

# Cone shaft: pivot end at seat station -28.25 from the T120 centre
# (25 journal + half of the first 6.5 face -- build_dt_cone_gear_shaft.py).
# CONE_ORIGIN (cone_line) stays the PIVOT END (station 0, the station datum);
# the physical shaft now runs FRONT_STUB further south (ch30 GT), so the part
# -- authored from its front stub end -- is PLACED at SHAFT_FRONT_STATION
# instead.  The post/carrier axis remains at its ch30-fitted world placement;
# the gear family is translated GEAR_AXIS_SHIFT along that same infinite line.
from dt_cone_gear_shaft_spec import FRONT_STUB as SHAFT_FRONT_STUB  # noqa: E402

SHAFT_FRONT_STATION = -SHAFT_FRONT_STUB
# = -build_dt_cone_gear_shaft FRONT_STUB (asserted below). The enlarged integral
# journal runs through the v2 post's 42.011-mm-long inclined bore and stands
# 1.0 mm proud of its south face.

# POST_STATION (cone_line): the corrected 2.8360-in v2 crank boss spans local z
# -21.3753..+50.6591. The 16T follows the shifted 64T row while the T12 chain
# plane remains photo-anchored, so the resulting axial gaps are intentionally
# unequal; the post station fixes crank X and its configured bore height sets Y.


# Exact-tracking self-check: the 20 mesh-derived seats lie on the shaft.
for _j in range(20):
    _x, _z = cone_seat(_j)
    _p = cone_station(SHAFT_T120_STATION + GEAR_AXIS_SHIFT + _j * SEAT_PITCH)
    if abs(_p[0] - _x) > 1e-9 or abs(_p[2] - _z) > 1e-9:
        raise AssertionError(f"cone seat {_j} off the shaft line: {(_x, _z)} vs {_p}")

# The 64T's SOUTH face stays on MHA-DT-004's collar, 1.5 north of the 8.0 layout
# face's (#1126), and the gear grew NORTH until it bears on T120's grown south
# face (dt_crank_drive_gear_spec, user ruling 2026-09-28): the solid stack's
# first joint.  GEAR64_STATION is the 19.9 layout station.
GEAR64_STATION = GEAR64_LAYOUT_CENTRE_STATION
GEAR64_CENTRE_STATION = GEAR64_STATION + GEAR_AXIS_SHIFT + GEAR64_CENTRE_SHIFT_NORTH
_T120_SOUTH_FACE_STATION = (
    SHAFT_T120_STATION + GEAR_AXIS_SHIFT + CONE_FACE_STATION_REFERENCE / 2.0 - CONE_FACE
)
if not math.isclose(
    GEAR64_CENTRE_STATION - GEAR64_FACE / 2.0,
    GEAR64_STATION + GEAR_AXIS_SHIFT - GEAR64_LAYOUT_FACE / 2.0 + GEAR64_SOUTH_FACE_SHIFT_NORTH,
    abs_tol=1e-9,
) or not math.isclose(
    GEAR64_CENTRE_STATION + GEAR64_FACE / 2.0, _T120_SOUTH_FACE_STATION, abs_tol=1e-9
):
    raise AssertionError(
        "64T must keep its south face on the collar and bear on T120's south face "
        "(user ruling 2026-09-28)"
    )
GEAR64_SEAT = cone_station(GEAR64_CENTRE_STATION)
R64 = (64.0 / DP_CRANK) * 25.4 / 2.0
R16 = (16.0 / DP_CRANK_CUTTER) * 25.4 / 2.0

# The true RH helical 64T follows the cone incline and meshes the straight
# 16T at their shared standard normal pitch. Only the crank bore height
# moves; the cone journal, solid stack and both axial seats retain their datums.
ADD16 = 25.4 / DP_CRANK_CUTTER
MESH16_C2C = R64 + R16 + _config.fit("crank_mesh", "c2c_slack_mm")
MESH16_C2C_SLACK = MESH16_C2C - R64 - R16
from dt_crank_drive_gear_spec import OUTSIDE_DIA as _GEAR64_TIP_DIA  # noqa: E402
from dt_crank_drive_gear_spec import OUTSIDE_DIA_TOLERANCE_MM as _GEAR64_TIP_DIA_TOLERANCE  # noqa: E402
from dt_crank_pinion_spec import OUTSIDE_DIA as _PINION_TIP_DIA  # noqa: E402

# Interleave of the two printed blanks at the fixed centre. Above ~1.2*ADD
# the teeth are really engaged; below 2*ADD less 0.1 the tips keep root air.
TIP16_C2C = (_GEAR64_TIP_DIA + _PINION_TIP_DIA) / 2.0
CRANK_MESH_DEPTH = TIP16_C2C - MESH16_C2C
if not 1.2 * ADD16 < CRANK_MESH_DEPTH < 2.0 * ADD16 - 0.1:
    raise AssertionError("crank pair mesh depth left its derived band")
# The restored post carries the fixed crank axis (user ruling 2026-09-28).
import crank_mesh_stack as crank_mesh  # noqa: E402

_DX16 = (GEAR64_SEAT[0] - X_CRANK) * COS_I  # horizontal leg toward the
# crank (a plane-local magnitude: the azimuth convention below measures from
# the in-plane horizontal TOWARD the other axis, so it is chirality-free)
_DY16 = Y_CRANK - Y_DRIVE  # vertical leg in both gear planes
if _DX16 <= 0.0:
    raise AssertionError("the 64T no longer lies +x of the crank (crank_mesh_stack premise)")
CRANK_ACTUAL_C2C = math.hypot(_DX16, _DY16)
if not (
    math.isclose(CRANK_ACTUAL_C2C, MESH16_C2C, rel_tol=0.0, abs_tol=1e-9)
    and math.isclose(CRANK_ACTUAL_C2C, crank_mesh.FRAME_C2C, rel_tol=0.0, abs_tol=1e-9)
):
    raise AssertionError(
        "crank physical centre must equal the normal-pitch mesh and stack reference"
    )
# Closed-form standard check over every printed corner and the booked centre
# range; the native interference gate below checks the actual flanks.
CRANK_MESH_CHECK = crank_mesh.standard_check()
from cone_stack_end_play import CONE_FLOAT_NORTH  # noqa: E402
# Line-of-centres azimuths (from each gear's centre toward the other axis, in
# that gear's own plane, ccw from the in-plane horizontal), for the pitch-
# cylinder contact-z law below. The 64T plane rides the inclined cone shaft;
# the 16T plane is a plain machine-Z section.
ALPHA64 = math.degrees(math.atan2(_DY16, _DX16))
ALPHA16 = math.degrees(math.atan2(_DY16, GEAR64_SEAT[0] - X_CRANK))
# (both horizontal legs run TOWARD the other axis and read positive -- the
# chirality-free plane-local convention; the CW spin sense is applied at the
# rot_z(-PINION_SEED_DEG) callsite)
# The 16T seats directly off the restored boss north face. Derive its
# tooth-centre station from the post as installed, not from a historical
# crankshaft station; the shaft's independent datum is checked against it.
_GEAR64_CONTACT_Z = GEAR64_SEAT[2] + R64 * math.cos(math.radians(ALPHA64)) * SIN_I
from dt_crank_pinion_spec import SEAT_FEELER_MM as PINION_SEAT_FEELER  # noqa: E402
from dt_cone_pivot_post_spec import CRANK_BOSS_START_Z as POST_CRANK_BOSS_START_Z  # noqa: E402
from dt_crankshaft_spec import SEAT_PINION as CRANK_PINION_SEAT  # noqa: E402

CRANK_FACE_Z = -183.0
_PPOST = cone_station(POST_STATION)
_POST_BOSS_NORTH = _PPOST[2] - POST_CRANK_BOSS_START_Z
PINION_TOOTH_Z = _POST_BOSS_NORTH + PINION_SEAT_FEELER + PINION_FACE / 2.0
if not math.isclose(
    CRANK_FACE_Z + CRANK_PINION_SEAT, PINION_TOOTH_Z - PINION_FACE / 2.0, abs_tol=1e-6
):
    raise AssertionError("crankshaft pinion seat must match the restored boss-face feeler")
# The pinion follows the recentered cone/64T row while the photo-anchored crank
# arm and T12 chain plane remain at their existing stations below.
# Tooth-in-gap phase seed, generalizing the old +11.25 half-pitch, at the
# PITCH POINT: the 64T mid-plane pitch-circle point nearest the crank axis
# (dt_crank_pinion_spec.pitch_point_azimuths), not the line of centres
# ALPHA64/ALPHA16 above, which sat 1.68 pinion degrees off it and interfered
# at 8e991c4ac. The 64T is keyed at its authored phase (a tooth centred at
# azimuth 0 -- for the helical teeth that is the MID-FACE azimuth), so its
# nearest tooth leads the pitch point; the pinion's gap sits that same arc
# (64/16 pinion degrees per 64T degree) past it on ITS side
# (dt_crank_pinion_spec.tooth_in_gap_seed_deg).
# gear_train.crank_mesh_phase_offset_deg is the one configured offset from
# that standard tooth-in-gap seed; the crankshaft's matched-hole clocking
# (dt_crank_pinion_spec.PIN_CLOCKING_DEG) is checked against it below.
from dt_crank_pinion_spec import PIN_CLOCKING_DEG as PINION_PIN_CLOCKING_DEG  # noqa: E402
from dt_crank_pinion_spec import pitch_point_azimuths, tooth_in_gap_seed_deg  # noqa: E402

PITCH_ALPHA64, PITCH_ALPHA16 = pitch_point_azimuths(
    GEAR64_SEAT[0] - X_CRANK, _DY16, INCLINE_DEG, R64
)
PINION_SEED_DEG = tooth_in_gap_seed_deg(PITCH_ALPHA64, PITCH_ALPHA16) + _config.machine(
    "gear_train", "crank_mesh_phase_offset_deg"
)

# ARBOR_SOUTH_Z / ARBOR_LENGTH (the cylinder arbor) follow from the pedestal
# strap faces and are defined with them below (U34b/U34c).
from dt_crank_hub_geometry import (  # noqa: E402
    AXIAL_PIN_LENGTH,
    AXIAL_PIN_RADIUS_FROM_AXIS,
    HUB_BARREL_DIA,
    HUB_LENGTH,
    HUB_SEAT_LENGTH,
    RELIEF_DIA_MAX as HUB_RELIEF_DIA_MAX,
    HUB_LENGTH_TOL,
    HUB_SHAFT_FLOAT,
    RELIEF_LENGTH as HUB_RELIEF_LENGTH,
    chain_shoulder_axial_air,
)
from dt_crank_arm_spec import (  # noqa: E402
    ANCHOR_HOLE_SPEC,
    ANCHOR_SCREW_X,
    ANCHOR_SCREW_Y,
    ARM_C2C,
    ARM_THICKNESS,
)
from _fit_limits import deviations  # noqa: E402
import _chain  # noqa: E402
import vn_crank_seat_drive_pin_spec as SEAT_PIN  # noqa: E402
import dt_crank_seat_washer_spec as SEAT_WASHER  # noqa: E402
import pd_transgear_removable_spec as REMOVABLE  # noqa: E402
from dt_crankshaft_spec import (  # noqa: E402
    COLLAR_DIA,
    COLLAR_REAR,
    DRIVE_PIN_DEPTH,
    DRIVE_PIN_FLOOR,
    PIN_HOLE_HEIGHT,
    SEAT_COLLAR,
    SEAT_COLLAR_BAND,
    SHAFT_LENGTH as CRANKSHAFT_LENGTH,
    SHAFT_LENGTH_BAND as CRANKSHAFT_LENGTH_BAND,
    SPIGOT_DIA,
    SPIGOT_DIA_BAND,
    SPIGOT_END,
    SPIGOT_LENGTH,
    SPIGOT_LENGTH_TOL,
    WHEEL_SEAT_FLOAT,
)
from dt_crank_handle_spec import HANDLE_LENGTH as HANDLE_BASIC_LENGTH  # noqa: E402
from dt_crank_handle_ferrule_spec import (  # noqa: E402
    INSTALLED_CONFIG as HANDLE_FERRULE_INSTALLED_CONFIG,
)
from dt_crank_handle_pivot_screw_spec import (  # noqa: E402
    INSTALLED_CONFIG as HANDLE_SCREW_INSTALLED_CONFIG,
    INSTALLED_THREAD_LENGTH as HANDLE_SCREW_INSTALLED_THREAD,
    SEAT_STATION as HANDLE_SCREW_SEAT_STATION,
    THREAD_MODEL_DIA as HANDLE_SCREW_THREAD_MAJOR,
)

CRANKSHAFT_Z0 = CRANK_FACE_Z
CRANK_ARM_Z0 = CRANK_FACE_Z
CRANK_HUB_Z0 = CRANK_FACE_Z
CRANK_ARM_ORIGIN_Z = CRANK_ARM_Z0 + ARM_THICKNESS
CRANK_HUB_REAR_Z = CRANK_HUB_Z0 + HUB_LENGTH
CRANK_HUB_PIN_ORIGIN = [
    X_CRANK,
    Y_CRANK - AXIAL_PIN_RADIUS_FROM_AXIS,
    CRANK_FACE_Z,
]
# The common crank face keeps its photo-backed station.  The arm occupies
# -183..-175 and the hub continues behind it to its rear face.
# The shaft cylinder starts flush at -183; only its dome projects outboard.
if abs(CRANK_ARM_ORIGIN_Z - (CRANK_FACE_Z + HUB_SEAT_LENGTH)) > 1e-9:
    raise AssertionError("arm inboard face left the hub shoulder station")

# The selected crank sprocket MHA-PD-009 is the front chain wheel: its plate
# spans BAND_FRONT_Z..SEAT_FACE_Z, the rear face on the crankshaft's integral
# collar, one chain plane with the selected knob sprocket (ch. 23 p.56).
# The sprocket itself lives in paper-drive; this module owns its seat.
if abs((CRANKSHAFT_Z0 + SEAT_COLLAR) - REMOVABLE.SEAT_FACE_Z) > 1e-9:
    raise AssertionError("crankshaft SeatCollar datum off the removable's SEAT_FACE_Z")
# The hub rear face is what stops the removable walking forward once the
# taper pin is in: the contract's 0.7 axial air, derived from both parts.
# The seat station's functional band moves the wheel against the hub; at its
# most-forward limit the air must still be open.
CRANK_HUB_SPROCKET_AIR = REMOVABLE.BAND_FRONT_Z - CRANK_HUB_REAR_Z
CRANK_HUB_SPROCKET_AIR_WORST = CRANK_HUB_SPROCKET_AIR + min(SEAT_COLLAR_BAND)
if abs(CRANK_HUB_SPROCKET_AIR - 0.7) > 1e-9:
    raise AssertionError(
        f"crank hub rear/sprocket air {CRANK_HUB_SPROCKET_AIR:.3f} left the contracted 0.7"
    )
if CRANK_HUB_SPROCKET_AIR_WORST <= 0.0:
    raise AssertionError(
        "crank hub rear/sprocket air closes at the SeatCollar band: "
        f"{CRANK_HUB_SPROCKET_AIR_WORST:.3f}"
    )
# Behind the seat: the integral collar, then the turned MHA-DT-036 thrust washer
# flat on the collar's rear face (its y = 0 face), faced to fit the post boss.
CRANK_SEAT_WASHER_Z0 = CRANKSHAFT_Z0 + COLLAR_REAR
CRANK_SEAT_WASHER_REAR_Z = CRANK_SEAT_WASHER_Z0 + SEAT_WASHER.THICKNESS
# The seat is a Ø17.5 spigot (SEAT_FACE_Z..SPIGOT_END) ahead of the Ø20.6
# body; the hub's rear Ø16.5 relief runs from its barrel's rear shoulder to
# the hub rear face.  Both let the #25 plates wrapping the crank sprocket pass inside
# the collar/barrel diameters (Main's ruling, 2026-09-30).
CRANK_SPIGOT_FRONT_Z = CRANKSHAFT_Z0 + SPIGOT_END  # body front face, -148.5
CRANK_HUB_BARREL_REAR_Z = CRANK_HUB_REAR_Z - HUB_RELIEF_LENGTH  # -161.65
# Chain-plate clearance: the plate's inner edge against the spigot
# (print-worst, largest) and the hub relief, radially, for the CAD link and a
# real ANSI #25 plate; axially, a bought chain's envelope (REMOVABLE.ANSI_*)
# against the shoulders, every link at its printed worst (the CAD link sits
# inside that envelope, so it needs no axial check of its own).
# Radially the chain follows the selected crank sprocket, which floats
# WHEEL_SEAT_FLOAT off the shaft axis on its pins; the hub's relief floats
# HUB_SHAFT_FLOAT in its bore. The spigot, hub, sprocket and plates all turn with the
# shaft (the wheel pinned to the collar, the hub to the shaft): a plate only
# articulates as it engages and leaves the wheel and never slides round the
# spigot or the relief, so contact there is benign and no running clearance
# is owed.  The floated stack is an all-limits coincidence; it must leave
# positive air.
CHAIN_RADIAL_AIR_WORST_MIN = 0.01


def chain_radial_air(
    what: str, plate_height: float, feature_dia_max: float, offset: float
) -> float:
    """Worst radial air from a plate ``plate_height`` tall wrapping the crank sprocket to
    a crank feature of largest diameter ``feature_dia_max``, the wheel's axis
    ``offset`` off the feature's: the plate's closest approach to the wheel's
    axis, less the offset and the feature's radius.  Raises below
    CHAIN_RADIAL_AIR_WORST_MIN."""
    air = (
        REMOVABLE.chain_plate_inner_radius(REMOVABLE.CRANK_TEETH, plate_height)
        - offset
        - feature_dia_max / 2.0
    )
    if air < CHAIN_RADIAL_AIR_WORST_MIN - 1e-9:
        raise AssertionError(
            f"{what} radial air {air:.3f} < {CHAIN_RADIAL_AIR_WORST_MIN}"
        )
    return air


_SPIGOT_DIA_MAX = SPIGOT_DIA + max(SPIGOT_DIA_BAND)
_RELIEF_OFFSET = WHEEL_SEAT_FLOAT + HUB_SHAFT_FLOAT
CHAIN_SPIGOT_RADIAL_AIR_CAD = chain_radial_air(
    "CAD link / seat spigot", _chain.PLATE_HEIGHT, _SPIGOT_DIA_MAX, WHEEL_SEAT_FLOAT
)  # 0.541
CHAIN_SPIGOT_RADIAL_AIR_ANSI = chain_radial_air(
    "ANSI #25 plate / seat spigot",
    REMOVABLE.ANSI_PLATE_HEIGHT,
    _SPIGOT_DIA_MAX,
    WHEEL_SEAT_FLOAT,
)  # 0.020
CHAIN_RELIEF_RADIAL_AIR_CAD = chain_radial_air(
    "CAD link / hub relief", _chain.PLATE_HEIGHT, HUB_RELIEF_DIA_MAX, _RELIEF_OFFSET
)  # 0.749
CHAIN_RELIEF_RADIAL_AIR_ANSI = chain_radial_air(
    "ANSI #25 plate / hub relief",
    REMOVABLE.ANSI_PLATE_HEIGHT,
    HUB_RELIEF_DIA_MAX,
    _RELIEF_OFFSET,
)  # 0.228
# The fitter lines the hub's front face up flush with the shaft's dome root
# (CRANK_FACE_Z) before the match-ream, so the hub rear face is CRANK_FACE_Z
# + the printed hub length; the arm's stock thickness is out of the stack.
_HUB_REAR_Z_WORST = CRANK_HUB_REAR_Z + HUB_LENGTH_TOL
_SEAT_FACE_Z_WORST = REMOVABLE.SEAT_FACE_Z + min(SEAT_COLLAR_BAND)
_CHAIN_REACH_REAR_WORST = REMOVABLE.CHAIN_REACH_REAR_WORST
# A: chain floated frontmost against the relief shoulder, in both wheel
# poses (dt_crank_hub_geometry): seated (seat forward, hub long, relief short)
# and floated forward onto the hub rear face (thinnest wheel, relief short).
# Local stations from the dome root, where the hub's front face is set.
_STACK_A = chain_shoulder_axial_air(
    relief_length=HUB_RELIEF_LENGTH,
    seat_face=REMOVABLE.SEAT_FACE_Z - CRANK_HUB_Z0,
    seat_face_band=SEAT_COLLAR_BAND,
)
CHAIN_BARREL_AXIAL_AIR = _STACK_A["seated"]  # 1.0635
CHAIN_BARREL_AXIAL_AIR_WORST = _STACK_A["seated_worst"]  # 0.4135
CHAIN_BARREL_AXIAL_AIR_FLOATED = _STACK_A["floated"]  # 0.3635
CHAIN_BARREL_AXIAL_AIR_FLOATED_WORST = _STACK_A["floated_worst"]  # 0.2135
_STACK_A_MODELLED = (
    REMOVABLE.SEAT_FACE_Z - REMOVABLE.CHAIN_REACH_FRONT - CRANK_HUB_BARREL_REAR_Z
)
if abs(CHAIN_BARREL_AXIAL_AIR - _STACK_A_MODELLED) > 1e-9:
    raise AssertionError("stack A left the modelled hub shoulder station")
# B: thickest wheel, seat forward, hub long.
CRANK_HUB_SPROCKET_AIR_PRINT_WORST = (
    _SEAT_FACE_Z_WORST - (REMOVABLE.PLATE + max(REMOVABLE.PLATE_BAND))
) - _HUB_REAR_Z_WORST  # 0.10
# C: chain floated rearmost on the thinnest wheel, spigot short; the chain
# and the body front face both ride the seat, so the seat band cancels.
CHAIN_SPIGOT_AXIAL_AIR = SPIGOT_LENGTH - REMOVABLE.chain_reach_rear(
    REMOVABLE.PLATE
)  # 2.3135 on nominal spigot and plate
CHAIN_SPIGOT_AXIAL_AIR_WORST = (
    SPIGOT_LENGTH - SPIGOT_LENGTH_TOL - _CHAIN_REACH_REAR_WORST
)  # 2.1635
for _what, _air in (
    ("chain / hub relief shoulder, wheel seated", CHAIN_BARREL_AXIAL_AIR_WORST),
    (
        "chain / hub relief shoulder, wheel floated onto the hub",
        CHAIN_BARREL_AXIAL_AIR_FLOATED_WORST,
    ),
    ("hub rear face / crank sprocket front face", CRANK_HUB_SPROCKET_AIR_PRINT_WORST),
    ("chain / crank collar body front face", CHAIN_SPIGOT_AXIAL_AIR_WORST),
):
    if _air <= 0.0:
        raise AssertionError(f"{_what} axial air closes at print-worst: {_air:.4f}")
# The two MHA-VN-044 drive pins stand in blind holes drilled from the seat face
# to DrivePinFloor, on the removable's pin circle.  Each pin's pressed end
# bears on the hole floor; its rounded lead end points machine front.
# MHA-VN-044 is crank-only; the knob carries its own MHA-VN-038 pins.
CRANK_DRIVE_PIN_Z0 = CRANKSHAFT_Z0 + DRIVE_PIN_FLOOR  # pressed end face
if abs(DRIVE_PIN_DEPTH - (SEAT_PIN.LENGTH - REMOVABLE.DRIVE_PIN_PROUD)) > 1e-9:
    raise AssertionError("crank drive-pin depth left the pin length less its proud")
if abs(CRANK_DRIVE_PIN_Z0 - SEAT_PIN.LENGTH - REMOVABLE.DRIVE_PIN_TIP_Z) > 1e-9:
    raise AssertionError("crank drive-pin tips are off the removable's DRIVE_PIN_TIP_Z")
if abs(SEAT_PIN.DIA - REMOVABLE.DRIVE_PIN_DIA) > 1e-12:
    raise AssertionError("crank-seat-drive-pin is not the removable's drive pin")
from build_dt_cylinder_end_disc import DISC_DIA as END_DISC_DIA  # noqa: E402
from build_dt_cylinder_end_disc import DISC_THICK as END_DISC_THICK  # noqa: E402

# The cylinder bank is a SOLID STACK (#743, cylinder_bank_layout): each
# MHA-DT-012 is one station pitch thick, cam face to back face, and a turned
# MHA-DT-026 thrust washer closes each end. The back (north) strap is the bank's
# axial datum and the bank is modelled pushed back against it; the front
# strap stands one BANK_END_FEELER leaf off the front washer. Every station
# below is the layout module's, so the ladder, the washers, the straps, the
# arbor and the apex set screws cannot drift apart. (Supersedes U34's
# END_DISC_AIR split and its -72.652 / +75.202 strap stations.)
import cylinder_bank_layout as _bank  # noqa: E402

if abs(Z_DRUM0 - _bank.STATION_Z0) > 1e-9 or abs(Z_PITCH - _bank.BANK_PITCH) > 1e-9:
    raise AssertionError("drive-train drum ladder left the cylinder-bank stations")
if abs(END_DISC_THICK - (_bank.BACK_WASHER_Z[1] - _bank.BACK_WASHER_Z[0])) > 1e-9:
    raise AssertionError("placed thrust washer is not the bank layout's washer")
END_DISC_SOUTH_Z0 = _bank.FRONT_WASHER_Z[0]
END_DISC_NORTH_Z0 = _bank.BACK_WASHER_Z[0]

# Arbor pedestals (U34c, dt-bank-pedestal-layout-20260923 rev 3): the SAME
# casting twice -- south as built, north rotated 180 about Y so its strap looks
# south at the drum (PR8, ch12 img09). Each is anchored on its strap INNER face
# (#743 stations); the foot grows 28 outboard of that face and carries one
# MHA-VN-032 hold-down in a base seat transferred from the pedestal.
from dt_arbor_pedestal_spec import (  # noqa: E402
    FOOT_NEAR_Z as ARBOR_PED_FOOT_NEAR_Z,
    STRAP_INNER_Z as ARBOR_PED_STRAP_INNER_Z,
    STRAP_ROOT_Z as ARBOR_PED_STRAP_ROOT_Z,
)

ARBOR_STRAP_SOUTH_Z = _bank.FRONT_STRAP_INNER_Z  # -71.519
ARBOR_STRAP_NORTH_Z = _bank.BACK_STRAP_INNER_Z  # +73.062
# Pedestal ORIGINS: south at -ARBOR_PEDESTAL_Z (as built, local +Z = machine
# +Z), north at +ARBOR_PEDESTAL_NORTH_Z (Ry180, local +Z = machine -Z).
ARBOR_PEDESTAL_Z = -_bank.FRONT_PEDESTAL_ORIGIN_Z  # 79.519
ARBOR_PEDESTAL_NORTH_Z = _bank.BACK_PEDESTAL_ORIGIN_Z  # 81.062
# Plan z band of each whole foot (strap inner face .. ledge end).
ARBOR_PED_SOUTH_Z_BAND = (
    -ARBOR_PEDESTAL_Z + ARBOR_PED_FOOT_NEAR_Z,
    -ARBOR_PEDESTAL_Z + ARBOR_PED_STRAP_INNER_Z,
)  # -99.519..-71.519
ARBOR_PED_NORTH_Z_BAND = (
    ARBOR_PEDESTAL_NORTH_Z - ARBOR_PED_STRAP_INNER_Z,
    ARBOR_PEDESTAL_NORTH_Z - ARBOR_PED_FOOT_NEAR_Z,
)  # +73.062..+101.062
if (
    abs(-ARBOR_PEDESTAL_Z + ARBOR_PED_STRAP_INNER_Z - ARBOR_STRAP_SOUTH_Z) > 1e-9
    or abs(ARBOR_PEDESTAL_NORTH_Z - ARBOR_PED_STRAP_INNER_Z - ARBOR_STRAP_NORTH_Z)
    > 1e-9
):
    raise AssertionError("a pedestal origin no longer puts its strap on the bank face")

# The cylinder arbor (MHA-DT-013) fills both strap bores and domes
# ARBOR_DOME_HEIGHT proud of each strap's outer face (#743, superseding
# U34b's "span less 6.0" and the MHA-125 dome cap screws: the dome IS the
# arbor end). Its part origin is the cylinder's south end.
from dt_cylinder_gear_shaft_spec import SHAFT_DIA as ARBOR_DIA  # noqa: E402

ARBOR_LENGTH = _bank.ARBOR_LENGTH  # the cylinder; the domes stand past it
ARBOR_SOUTH_Z = _bank.ARBOR_SOUTH_Z
_ARBOR_NORTH = ARBOR_SOUTH_Z + ARBOR_LENGTH
for _label, _end, _outer in (
    ("south", ARBOR_SOUTH_Z, -ARBOR_PEDESTAL_Z + ARBOR_PED_STRAP_ROOT_Z),
    ("north", _ARBOR_NORTH, ARBOR_PEDESTAL_NORTH_Z - ARBOR_PED_STRAP_ROOT_Z),
):
    if abs(_end - _outer) > 1e-9:
        raise AssertionError(f"arbor {_label} end is not flush with its strap face")
# The apex set screws (MHA-VN-034), one per crown at the strap's mid-depth, cup
# point down on the arbor's top.
from vn_arbor_set_screw_spec import LENGTH as SET_SCREW_LEN  # noqa: E402

SET_SCREW_SOUTH_Z = _bank.FRONT_SET_SCREW_Z
SET_SCREW_NORTH_Z = _bank.BACK_SET_SCREW_Z
SET_SCREW_TIP_Y = Y_DRIVE + ARBOR_DIA / 2.0
# The socket sits the layout's named height over the crown apex, exactly;
# cylinder_bank_layout also proves the cup point spans the bore clearance.
from dt_arbor_pedestal_spec import BORE_HEIGHT as _PED_BORE_H  # noqa: E402
from dt_arbor_pedestal_spec import TOP_RADIUS as _PED_CROWN_R  # noqa: E402

_CROWN_APEX_Y = Y_BASE_TOP + _PED_BORE_H + _PED_CROWN_R
if abs(Y_DRIVE - (Y_BASE_TOP + _PED_BORE_H)) > 1e-6:
    raise AssertionError("arbor pedestal bore is off the drive axis")
if (
    abs(SET_SCREW_TIP_Y + SET_SCREW_LEN - _CROWN_APEX_Y - _bank.SET_SCREW_SOCKET_PROUD)
    > 1e-6
):
    raise AssertionError("arbor set screw's socket is not SET_SCREW_SOCKET_PROUD over the apex")
if _bank.SET_SCREW_POINT_MARGIN < _bank.SET_SCREW_POINT_MARGIN_MIN:
    raise AssertionError(
        "arbor set screw's cup point spans the bore clearance by < SET_SCREW_POINT_MARGIN_MIN"
    )
if END_DISC_SOUTH_Z0 - ARBOR_STRAP_SOUTH_Z < 0.25:
    raise AssertionError("south thrust washer reaches the south pedestal strap")
if abs(ARBOR_STRAP_NORTH_Z - (END_DISC_NORTH_Z0 + END_DISC_THICK)) > 1e-9:
    raise AssertionError("north thrust washer does not bear on the datum strap")
# Plan overlap, not z alone, against the rocker-arm-support foot (x 41.15..
# 104.65 about SUPPORT_WORLD_X, z +-88.9): the north foot shares its z band but
# stands ~89.5 away in x (study rev 3 section 6; the z-only test fired falsely).
from build_dt_arbor_pedestal import FOOT_WIDTH as _PED_FOOT_WIDTH  # noqa: E402
from fr_rocker_arm_support_section_spec import WIDE as _SUPPORT_FOOT_HALF_X  # noqa: E402
from fr_rocker_arm_support_spec import (  # noqa: E402
    SUPPORT_HALF_MACHINE_Z as _SUPPORT_FOOT_HALF_Z,
    SUPPORT_WORLD_X as _SUPPORT_X,
    SUPPORT_WORLD_Z as _SUPPORT_Z,
)

for _band in (ARBOR_PED_SOUTH_Z_BAND, ARBOR_PED_NORTH_Z_BAND):
    _gap_x = (_SUPPORT_X - _SUPPORT_FOOT_HALF_X) - (X_DRUM + _PED_FOOT_WIDTH / 2.0)
    _gap_z = max(
        _band[0] - (_SUPPORT_Z + _SUPPORT_FOOT_HALF_Z),
        (_SUPPORT_Z - _SUPPORT_FOOT_HALF_Z) - _band[1],
    )
    if max(_gap_x, _gap_z) < 0.5:
        raise AssertionError("an arbor pedestal foot reaches the rocker-support foot")

# The pinion must sit fully on the crankshaft.
if PINION_TOOTH_Z + PINION_FACE / 2.0 > CRANKSHAFT_Z0 + CRANKSHAFT_LENGTH:
    raise AssertionError("crankshaft too short for the M6.7 pinion station")
# The crankshaft's named seat datums (the flip-free coincident seats for the
# keyed chain -- see _seat_on_crank) must sit exactly at this module's
# authored stations.  Hub and arm seat to one another at the shaft origin.
from _hole_spec import THREAD_MAJOR_MM, blind_cut_dia_mm  # noqa: E402
from build_dt_crankshaft import (  # noqa: E402
    SEAT_PINION as CS_SEAT_PINION,
    SHAFT_LENGTH as CS_SHAFT_LENGTH,
)

# Crank taper pin + keeper ring (ch11 p.14): pin axis along machine X through
# MHA-DT-031's rear barrel and the crankshaft at station 12, behind the arm.
from dt_crank_pin_spec import (  # noqa: E402
    PIN_LENGTH as CRANK_PIN_LENGTH,
    RING_HOLE_DIA as PIN_RING_HOLE_DIA,
    RING_HOLE_X as PIN_RING_HOLE_X,
)
from dt_crank_pin_ring_spec import (  # noqa: E402
    PIN_PROUD,
    WIRE_DIA as CRANK_RING_WIRE_DIA,
)
from dt_crank_pin_eye_spec import (  # noqa: E402
    ANCHOR_AIR,
    TAIL_LEN as EYE_TAIL_LEN,
    WIRE_DIA as EYE_WIRE_DIA,
)
from vn_fillister_screw_spec import (  # noqa: E402
    SHANK_DIA as ANCHOR_SCREW_SHANK_DIA,
    SHANK_LEN as ANCHOR_SCREW_SHANK_LEN,
)
import vn_keeper_chain_spec  # noqa: E402

CRANK_PIN_Z = CRANK_FACE_Z + PIN_HOLE_HEIGHT  # -169.4: behind the 8-mm arm
CRANK_PIN_X0 = X_CRANK - HUB_BARREL_DIA / 2.0 - PIN_PROUD
# The ring lies in machine YZ. Its straight local-Z leg is concentric with the
# pin's machine-Z cross-hole; its bends and return hang toward machine -Y.
CRANK_RING_Y = Y_CRANK
if (PIN_RING_HOLE_DIA - CRANK_RING_WIRE_DIA) / 2.0 < 0.1:
    raise AssertionError("keeper-ring wire does not clear the crank-pin cross-hole")
if abs((CRANKSHAFT_Z0 + PIN_HOLE_HEIGHT) - CRANK_PIN_Z) > 1e-6:
    raise AssertionError("shaft and hub MHA-DT-009 stations do not coincide")
if CRANK_PIN_X0 + CRANK_PIN_LENGTH < X_CRANK + HUB_BARREL_DIA / 2.0 + 2.0:
    raise AssertionError("crank pin does not run out the far side of the hub")
if abs(AXIAL_PIN_LENGTH - ARM_THICKNESS / 2.0) > 1e-9:
    raise AssertionError("MHA-VN-029 no longer has half-arm-thickness engagement")
# Keeper-ring anchor (ch11 p.14): the arm's front (south, machine -z) face is
# CRANK_ARM_Z0; arm local (x, y) -> machine (X_CRANK - y, Y_CRANK - x) (the
# placed rows: local +x -> -Y, local +y -> -X). The brass eyelet's tail lies
# flat on that face (wire centre a wire radius + air south of it), pointing UP
# the arm at the screw and ending at the shank; its loop stands off the face
# below the tail. The fillister-screw's under-head plane rides on the wire
# (one wire diameter + air off the face), shank pointing +z into the arm's
# #4-40 tap.
ANCHOR_SCREW_XY = (X_CRANK - ANCHOR_SCREW_Y, Y_CRANK - ANCHOR_SCREW_X)
ANCHOR_HEAD_Z = CRANK_ARM_Z0 - EYE_WIRE_DIA - ANCHOR_AIR
EYE_Z = CRANK_ARM_Z0 - EYE_WIRE_DIA / 2.0 - ANCHOR_AIR
# the tail's end touches the shank: the eye's origin (the tail root, where it
# runs tangent into the loop) sits TAIL_LEN + shank radius + air below the
# screw axis
EYE_ROOT_Y = ANCHOR_SCREW_XY[1] - (
    ANCHOR_SCREW_SHANK_DIA / 2.0 + ANCHOR_AIR + EYE_TAIL_LEN
)
# Keeper chain (MHA-VN-035) + loop link (MHA-VN-036): authored in the crank
# frame, whose origin is the crank axis on the arm's outboard face. The spec
# derives the eye and ring poses from the part specs alone; they must be the
# ones placed here.
CRANK_FRAME_ORIGIN = (X_CRANK, Y_CRANK, CRANK_ARM_Z0)
for _got, _want, _what in (
    (vn_keeper_chain_spec.EYE_ROOT, (ANCHOR_SCREW_XY[0], EYE_ROOT_Y, EYE_Z), "eye root"),
    (
        (vn_keeper_chain_spec.RING_X, 0.0, vn_keeper_chain_spec.PIN_Z),
        (CRANK_PIN_X0 + PIN_RING_HOLE_X, CRANK_RING_Y, CRANK_PIN_Z),
        "keeper-ring through leg",
    ),
):
    _placed = tuple(g + o for g, o in zip(_got, CRANK_FRAME_ORIGIN))
    if max(abs(p - w) for p, w in zip(_placed, _want)) > 1e-9:
        raise AssertionError(f"vn_keeper_chain_spec {_what} {_placed} != placed {_want}")
if min(vn_keeper_chain_spec.clearance_report().values()) < 0.0:
    raise AssertionError("keeper chain touches a part it must clear")
ANCHOR_THREAD_ENGAGEMENT = ANCHOR_HEAD_Z + ANCHOR_SCREW_SHANK_LEN - CRANK_ARM_Z0
# The #4-40 is tapped THRU the arm (rule 12, W7): nothing to bottom on; the
# screw tip must stay short of the inboard face.
ANCHOR_TIP_RESERVE = ARM_THICKNESS - ANCHOR_THREAD_ENGAGEMENT
if ANCHOR_HOLE_SPEC.end != "through_all":
    raise AssertionError("crank-arm anchor tap is no longer through the arm")
if ANCHOR_THREAD_ENGAGEMENT < 2.0:
    raise AssertionError("anchor screw has under 2.0 thread engagement in the arm")
if ANCHOR_TIP_RESERVE < 0.5:
    raise AssertionError("anchor screw tip stands within 0.5 of the arm's inboard face")
# The plate origin is its inboard face (-175): the Ry(180)-composed pose maps
# the +z extrusion toward machine -z, filling the arm from -175 to -183.

if abs(CS_SHAFT_LENGTH - CRANKSHAFT_LENGTH) > 1e-9:
    raise AssertionError("crankshaft part length does not cover the moved pinion")
if abs((CRANKSHAFT_Z0 + CS_SEAT_PINION) - (PINION_TOOTH_Z - PINION_FACE / 2.0)) > 1e-6:
    raise AssertionError("crankshaft SeatPinion datum off the 16T station")
# Pinion retention pin (ch12 p.19): a plain 1/8 in straight pin through the
# pinion's hub boss and the crankshaft, match-drilled at assembly. The hole is
# on the pinion's local -X at the boss's mid-length; the crankshaft's hole is
# turned to the pinion seed so that, with the pinion seated rot_z(-seed),
# the two holes are one. The pin lies along machine X through the shaft
# axis, flush with the boss on both sides. The pinion and shaft consume the
# same configured clock; their agreement is checked HERE.
from dt_crank_pinion_spec import (  # noqa: E402
    BOSS_DIA as PINION_BOSS_DIA,
    FACE_WIDTH as PINION_SPEC_FACE,
    OVERALL_LENGTH as PINION_OVERALL_LENGTH,
    PIN_DIA as PINION_PIN_DIA,
    PIN_LENGTH as PINION_PIN_LENGTH,
    FACE_WIDTH_PLACES as PINION_FACE_WIDTH_PLACES,
    FACE_WIDTH_LIMITS as PINION_FACE_LIMITS,
    W15_FACE_ALLOWANCE_MM as PINION_W15_FACE_ALLOWANCE,
    OVERALL_LENGTH_PLACES as PINION_OVERALL_LENGTH_PLACES,
    SHAFT_LENGTH_PLACES as PINION_SHAFT_LENGTH_PLACES,
    PIN_EDGE_MIN_WORST as PINION_PIN_EDGE_MIN_WORST,
    PIN_STATION as PINION_PIN_STATION,
    PIN_STATION_LAYOUT_ALLOWANCE_MM as PINION_PIN_LAYOUT_ALLOWANCE,
    SEAT_GAP_MAX_MM as PINION_SEAT_GAP_MAX,
    SHAFT_END_RECESS_MIN_WORST as PINION_RECESS_MIN_WORST,
)
from build_dt_crankshaft import PINION_PIN_STATION_Y as CS_PINION_PIN_STATION  # noqa: E402

PINION_Z0 = PINION_TOOTH_Z - PINION_FACE / 2.0  # pinion origin: toothed south face
PINION_PIN_Z = PINION_Z0 + PINION_PIN_STATION
# The pin's axis is the seated pinion's local X: rot_z(-seed) turns local +X to
# machine (cos s, -sin s, 0). The pin part's +Z runs along that (ROT_Y_POS90
# lays part +Z on machine +X, then the same rot_z(-seed) as the pinion), so
# the pin origin sits on the boss's local -X wall, a half boss diameter back.
PINION_PIN_U = (
    math.cos(math.radians(PINION_SEED_DEG)),
    -math.sin(math.radians(PINION_SEED_DEG)),
    0.0,
)
PINION_PIN_ORIGIN = [
    X_CRANK - PINION_PIN_LENGTH / 2.0 * PINION_PIN_U[0],
    Y_CRANK - PINION_PIN_LENGTH / 2.0 * PINION_PIN_U[1],
    PINION_PIN_Z,
]
if abs(PINION_SPEC_FACE - PINION_FACE) > 1e-9:
    raise AssertionError("dt_crank_pinion_spec.FACE_WIDTH disagrees with PINION_FACE")
if abs(PINION_PIN_CLOCKING_DEG - PINION_SEED_DEG) > 1e-9:
    raise AssertionError(
        "crankshaft matched-hole clock differs from the pinion seed"
    )
if abs((CRANKSHAFT_Z0 + CS_PINION_PIN_STATION) - PINION_PIN_Z) > 1e-6:
    raise AssertionError("crankshaft pin hole station off the pinion's pin station")
if abs(PINION_PIN_LENGTH - PINION_BOSS_DIA) > 1e-9:
    raise AssertionError("pinion pin is not flush with the boss")
_SHAFT_NORTH_END = CRANKSHAFT_Z0 + CS_SHAFT_LENGTH
# Nominal recess of the shaft end inside the boss and the pin's wall to that
# end; their worst cases are asserted once the seat gap is known (below).
PINION_RECESS_NOMINAL = (PINION_Z0 + PINION_OVERALL_LENGTH) - _SHAFT_NORTH_END
PINION_PIN_EDGE_NOMINAL_ACTUAL = _SHAFT_NORTH_END - (
    PINION_PIN_Z + PINION_PIN_DIA / 2.0
)

# The whole cone set rides the SWING PLATFORM (ch.12 p.18: the dark wedge
# plate labelled "pivot" at its tip end). The green pivot post (big-end
# journal) and the black tip block (cup-ended adjuster carrier) stand ON the plate;
# the plate pivots about a vertical axis at cone station PIVOT_STATION, just
# north of the shaft's rear end, so on disengage the BIG end -- where the
# gears need the most working-depth separation -- swings the farthest
# (throw ~ distance from pivot).
# T006 is the reference gear for the tip-end stack.  The MHA-VN-016 stack collar
# is set one COLLAR_FEELER off its north face (cone_stack_end_play). The collar
# and pivot stations come from the current tip-stack law; the tip block's
# north face is TIP_BLOCK_NORTH_FACE_PIVOT_OFFSET south of the pivot, growing
# south from it (user ruling 2026-09-29: its station is fixed by its
# hold-down hole, not slid at fit-up).  T006_CENTER_STATION, T006_NORTH_FACE,
# TIP_BLOCK_STATION and PIVOT_STATION come from cone_line; the checks below
# hold them to the parts.

# --- platform <-> riders fit (SolidWorks-free, import-time) ------------------
# The platform/post/block parts hardcode their envelopes in THEIR part frames;
# they must agree with the live cone-shaft line placed here. Imported, not
# copied (the CAM_ECC precedent), and asserted at import so a drifted anchor
# fails before any COM work.
from dt_cone_swing_platform_crank_axis import (  # noqa: E402
    CRANK_AXIS_OFF as PLAT_CRANK_OFF,
    CRANK_AXIS_Y as PLAT_CRANK_Y,
    CRANK_SEAT_ANCHOR as PLAT_SEAT_ANCHOR,
)
from dt_cone_swing_platform_geometry import (  # noqa: E402
    EAST_HALF_S as PLAT_EAST_S,
    HALF_WIDTH_N as PLAT_EAST_N,  # EAST taper line's north endpoint (12 --
    # the lock-slot side keeps its full seat; feeds the stop-screw/containment
    # east-edge math)
    WEST_HALF_N as PLAT_WEST_N,  # WEST line's north endpoint (the trim;
    # feeds ONLY the west-edge sweep. Aliasing it into the east math shifted
    # the derived stop point -- Codex catch, 2026-07-05)
    NORTH_OVERHANG as PLAT_OVERHANG,
    LOCK_HEAD_POST_CLEARANCE as PLAT_LOCK_HEAD_POST_CLEARANCE,
    PLATE_LEN as PLAT_LEN,
    PLATE_T as PLAT_T,
    SLOT_E_X as PLAT_SLOT_E_X,
    SLOT_E_Z as PLAT_SLOT_E_Z,
    SLOT_W as PLAT_SLOT_W,
    WEST_HALF_S as PLAT_WEST_S,
    manufactured_p1_stop_enclosure,
)
from dt_cone_swing_platform_spec import (  # noqa: E402
    HOLDDOWN_CBORE_DEPTH as PLAT_HOLDDOWN_CBORE_DEPTH,
    HOLDDOWN_CLEARANCE_DIA as PLAT_HOLDDOWN_CLEARANCE_DIA,
    HOLDDOWN_HOLE_SPEC as PLAT_HOLDDOWN_HOLE_SPEC,
    HOLDDOWN_LEDGE_RANGE as PLAT_HOLDDOWN_LEDGE_RANGE,
    HOLDDOWN_LOCAL_X as PLAT_HOLDDOWN_LOCAL_X,
    HOLDDOWN_LOCAL_Z as PLAT_HOLDDOWN_LOCAL_Z,
    HOLDDOWN_SCREW_HEAD_DIA as PLAT_HOLDDOWN_SCREW_HEAD_DIA,
    HOLDDOWN_SCREW_HEAD_H as PLAT_HOLDDOWN_SCREW_HEAD_H,
    HOLDDOWN_STATION_TOL_MM as PLAT_HOLDDOWN_STATION_TOL_MM,
    PIVOT_BEARING_RELIEF_DIAMETER as PLAT_PIVOT_RELIEF_DIA,
    PIVOT_BEARING_THICKNESS as PLAT_PIVOT_BEARING_T,
    PIVOT_HEAD_RADIAL_CLEARANCE as PLAT_PIVOT_HEAD_RADIAL_CLEARANCE,
    POST_MOUNT_ENGAGEMENT_WORST_DIAMETERS,
    POST_MOUNT_SPEC,
    POST_MOUNT_STATION_TOL_MM as PLAT_POST_MOUNT_STATION_TOL_MM,
    POST_MOUNT_TAP_EDGE_BREAK,
    POST_MOUNT_THREAD_DIA,

)
from dt_cone_swing_platform_pivot_spec import (  # noqa: E402
    PIVOT_HOLE_BAND as PLAT_PIVOT_HOLE_BAND,
    PIVOT_HOLE_DIA as PLAT_PIVOT_HOLE_DIA,
)
from vn_post_mount_screw_spec import (  # noqa: E402
    CUT_LENGTH_MM as POST_SCREW_LEN,
    THREAD as POST_SCREW_THREAD,
)
from vn_cone_lock_knob_spec import (  # noqa: E402
    HEAD_DIA as KNOB_HEAD_DIA,
    STUD_DIA as KNOB_STUD_DIA,
    STUD_LEN as KNOB_STUD_LEN,
    THREAD as KNOB_THREAD,
    require_seat_fit as require_lock_seat_fit,
)
from vn_cone_pivot_screw_spec import (  # noqa: E402
    HEAD_DIA as PSCREW_HEAD_DIA,
    SHOULDER_DIA as PSCREW_SHOULDER_DIA,
    SHOULDER_DIA_BAND as PSCREW_SHOULDER_DIA_BAND,
    SHOULDER_LEN as PSCREW_SHOULDER_LEN,
    THREAD as PSCREW_THREAD,
    THREAD_TAIL_LEN as PSCREW_THREAD_TAIL_LEN,
)
from vn_swing_stop_screw_spec import (  # noqa: E402
    EMBED_LEN as STOP_EMBED_LEN,
    HEAD_DIA as STOP_HEAD_DIA,
    PROUD_LEN as STOP_PROUD_LEN,
    SHANK_LEN as STOP_SHANK_LEN,
    THREAD as STOP_THREAD,
    require_seat_fit as require_stop_seat_fit,
)
from build_fr_harmonic_base import (  # noqa: E402
    BLOCK_SCREW_HOLE_DEPTH as BASE_BLOCK_HOLE_DEPTH,
    BLOCK_SEAT_SPEC as BASE_BLOCK_SEAT_SPEC,
    BLOCK_SCREW_XZ as BASE_BLOCK_XZ,
    FOOT_SCREW_HOLE_DEPTH as BASE_FOOT_HOLE_DEPTH,
    FOOT_SEAT_SPEC as BASE_FOOT_SEAT_SPEC,
    FOOT_SCREW_XZ as BASE_FOOT_XZ,
    LOCK_KNOB_XZ as BASE_LOCK_XZ,
    LOCK_SEAT_SPEC as BASE_LOCK_SEAT_SPEC,
    LOCK_STUD_ENGAGEMENT as BASE_LOCK_ENGAGEMENT,
    PEDESTAL_SCREW_HOLE_DEPTH as BASE_PEDESTAL_HOLE_DEPTH,
    PEDESTAL_SCREW_XZ as BASE_PEDESTAL_XZ,
    PEDESTAL_SEAT_SPEC as BASE_PEDESTAL_SEAT_SPEC,
    PIVOT_SEAT_SPEC as BASE_PIVOT_SEAT_SPEC,
    PIVOT_SCREW_XZ as BASE_PIVOT_XZ,
    STOP_SEAT_SPEC as BASE_STOP_SEAT_SPEC,
    STOP_SCREW_XZ as BASE_STOP_XZ,
    SWING_HARDWARE_GEOMETRY as BASE_SWING_HARDWARE,
    require_blind_seat_fit as require_base_seat_fit,
)
from build_fr_harmonic_base import (  # noqa: E402
    HOLE_XZ as BASE_HOLE_XZ,
    NAMEPLATE_SCREW_XZ as BASE_NAMEPLATE_XZ,
    SERIAL_HEIGHT_MM as BASE_SERIAL_HEIGHT,
    SERIAL_XZ as BASE_SERIAL_XZ,
)
from frame_column_stations import COLUMN_SOCKET_DIAMETER  # noqa: E402
from fr_nameplate_spec import (  # noqa: E402
    PLATE_HEIGHT as NAMEPLATE_HEIGHT,
    PLATE_WIDTH as NAMEPLATE_WIDTH,
    mount_point as nameplate_mount_point,
)
from fr_harmonic_base_spec import (  # noqa: E402
    COLUMN_SOCKET_XZ as BASE_COLUMN_SOCKET_XZ,
    LIP_W as BASE_LIP_W,
    TOP_LENGTH as BASE_TOP_LENGTH,
    TOP_WIDTH as BASE_TOP_WIDTH,
)
from build_dt_arbor_pedestal import (  # noqa: E402
    FOOT_HEIGHT as ARBOR_PED_FLANGE_T,
    FOOT_WIDTH as ARBOR_PED_WIDTH,
    SCREW_Z as ARBOR_PED_SCREW_Z,
)
from dt_arbor_pedestal_spec import SCREW_HOLE_SPEC as ARBOR_PED_HOLE_SPEC  # noqa: E402

# --- ch25 pinion swing rig part constants (PR7: imported, not hardcoded) ----
from build_dt_alignment_pinion import (  # noqa: E402
    BORE_DIA as DRUM_BORE_DIA,
)
from dt_pinion_arbor_geometry import (  # noqa: E402
    CROSS_HOLE_DIA as ARBOR_CROSS_HOLE_DIA,
    DRUM_STATION_BAND as ARBOR_DRUM_STATION_BAND,
    BACK_JOURNAL_Z as ARBOR_BACK_JOURNAL_Z,
    DRUM_STATION as ARBOR_DRUM_STATION,
    drum_total_air as ARBOR_DRUM_TOTAL_AIR,
    FRONT_JOURNAL_Z as ARBOR_FRONT_JOURNAL_Z,
    JOURNAL_LEN as ARBOR_JOURNAL_LEN,
    LAND_MARGINS_AT_STOPS as ARBOR_LAND_MARGINS_AT_STOPS,
    MIN_END_PLAY as ARBOR_MIN_END_PLAY,
    MIN_LAND_OVER_STRAP as ARBOR_MIN_LAND_OVER_STRAP,
    HEAD_CAP_SAG as ARBOR_HEAD_CAP_SAG,
    HEAD_CAP_SAG_PLACES as ARBOR_HEAD_CAP_SAG_PLACES,
    HEAD_CENTER_Z as ARBOR_HEAD_CENTER_Z,
    HEAD_DIA as ARBOR_HEAD_DIA,
    HEAD_FRONT_Z as ARBOR_HEAD_FRONT_Z,
    HEAD_LEN as ARBOR_HEAD_LEN,
    HEAD_LEN_PLACES as ARBOR_HEAD_LEN_PLACES,
    HEAD_REAR_Z as ARBOR_HEAD_REAR_Z,
    NECK_END_Z as ARBOR_NECK_END_Z,
    NECK_LEN as ARBOR_NECK_LEN,
    NECK_LEN_PLACES as ARBOR_NECK_LEN_PLACES,
    PIN_Z as ARBOR_PIN_Z,
    SHAFT_DIA as ARBOR_DIA,
)
from dt_pinion_arbor_collar_geometry import (  # noqa: E402
    COLLAR_LEN as ARBOR_COLLAR_LEN,
    COLLAR_OD as ARBOR_COLLAR_OD,
    PIN_HOLE_Z as ARBOR_COLLAR_PIN_Z,
)
from dt_pinion_bracket_geometry import (  # noqa: E402
    ARBOR_BORE as STRAP_ARBOR_BORE,
    C2C as STRAP_C2C,
    CROSS_HOLE_CZ as STRAP_CROSS_HOLE_CZ,
    PIN_BORE as STRAP_PIN_BORE,
    PIN_DROP as FPIN_DROP,
    PIN_SEAT as FPIN_SEAT,
    PIVOT_BORE as STRAP_PIVOT_BORE,
    R_END as STRAP_R_END,
    THICKNESS as STRAP_T,
    THICKNESS_PLACES as STRAP_T_PLACES,
)
from dt_pinion_pivot_block_geometry import (  # noqa: E402
    BLOCK_DEPTH,
    BLOCK_EAST,
    BLOCK_HEIGHT,
    BLOCK_WIDTH,
    BORE_UP as BLOCK_BORE_UP,
    SCREW_HALF_SPACING as BLOCK_SCREW_HALF,
)
from dt_pinion_pivot_block_geometry import SCREW_HOLE_SPEC as BLOCK_SCREW_HOLE_SPEC  # noqa: E402
import pinion_rig_layout as RIG  # noqa: E402
from dt_pinion_cam_geometry import (  # noqa: E402
    BORE as CAM_BORE_DIA,
    CAM_LEN,
    CAM_OD,
    ECC as CAM_ECC,
    THIN_SIDE_WALL as CAM_THIN_SIDE_WALL,
)
from dt_pinion_cam_pin_geometry import (  # noqa: E402
    PIN_DIA as FPIN_DIA,
    PIN_LEN as FPIN_LEN,
    SEAT_LEN as FPIN_SEAT_LEN,
)
from dt_pinion_lever_geometry import (  # noqa: E402
    CAP_SAG as LEVER_CAP_SAG,
    HUB_LEN as LEVER_HUB_LEN,
    ROD_DIA as LEVER_ROD_DIA,
    ROD_PIN_HOLE_FROM_END as LEVER_PIN_FROM_ROD_END,
    ROD_LEN as LEVER_ROD_LEN,
    WALL_T as LEVER_WALL_T,
)
from dt_pinion_lever_pin_geometry import (  # noqa: E402
    INSTALLED_CONFIG as LEVER_PIN_INSTALLED_CONFIG,
)
from dt_pinion_handle_geometry import (  # noqa: E402
    ROD_DIA as HANDLE_ROD_DIA,
    ROD_DIA_BAND as HANDLE_ROD_DIA_BAND,
    ROD_DOWN as HANDLE_ROD_DOWN,
    ROD_UP as HANDLE_ROD_UP,
)
from dt_pinion_spring_geometry import (  # noqa: E402
    BEND_EXIT as SPR_BEND_EXIT_L,
    BLADE_ARM as SPR_BLADE_ARM,
    CONTACT_T as SPR_CONTACT_T,
    CREST as SPR_CREST_L,
    FLAT_TIP as SPR_FLAT_TIP_L,
    FOOT_END as SPR_FOOT_END_L,
    FOOT_TAN as SPR_FOOT_TAN_L,
    FORMED_BAND_MM as SPR_FORMED_BAND,
    FORMED_CORNERS as SPR_FORMED_CORNERS,
    HOLE_SPEC as SPR_HOLE_SPEC,
    HOLE_X as SPR_HOLE_X_L,
    KINK_C as SPR_KINK_C_L,
    KINK_DEG as SPR_KINK_DEG,
    KINK_START as SPR_KINK_START_L,
    PARKED_AIR as SPR_PARKED_AIR,
    PIVOT_LX as SPR_PIVOT_LX,
    PIVOT_LY as SPR_PIVOT_LY,
    PRESET as SPR_PRESET,
    R_KINK as SPR_R_KINK,
    STRAP_HALF_WIDTH as SPR_STRAP_HALF_WIDTH,
    STRAP_LEAN_DEG as SPR_STRAP_LEAN_DEG,
    YIELD_MPA as SPR_YIELD_MPA,
    contact_force as spr_contact_force,
    formed_contact as spr_formed_contact,
    root_stress as spr_root_stress,
)
from dt_pinion_spring_section import (  # noqa: E402
    THICK as SPRING_T,
    THICK_BAND as SPRING_T_BAND,
    WIDTH as SPRING_W,
    WIDTH_PLACES as SPRING_W_PLACES,
)
from vn_slotted_screw_spec import (  # noqa: E402
    HEAD_DIA as BSCREW_HEAD_DIA,
    SHANK_LEN as BSCREW_SHANK_LEN,
    THREAD as BSCREW_THREAD,
)

from vn_foot_screw_spec import (  # noqa: E402
    HEAD_DIA as FSCREW_HEAD_DIA,
    SHANK_LEN as FSCREW_SHANK_LEN,
    THREAD as FSCREW_THREAD,
)
from vn_pedestal_hold_down_screw_spec import (  # noqa: E402
    HEAD_DIA as HDSCREW_HEAD_DIA,
    SHANK_DIA as HDSCREW_SHANK_DIA,
    SHANK_LEN as HDSCREW_SHANK_LEN,
    THREAD as HDSCREW_THREAD,
)
from build_dt_cone_pivot_post import (  # noqa: E402
    ATTACHMENT_CBORE_DEPTH as POST_CBORE_DEPTH,
    ATTACHMENT_X as POST_ATTACHMENT_X,
    BLOCK_DIA as POST_BLOCK_DIA,
    BLOCK_HEIGHT as POST_BLOCK_HEIGHT,
    BORE_HEIGHT as POST_BORE_HEIGHT,
    CONE_BOSS_LENGTH as POST_CONE_BOSS_LENGTH,
    CRANK_BOSS_LENGTH as POST_CRANK_BOSS_LENGTH,
)
from dt_cone_pivot_post_spec import (  # noqa: E402
    ATTACHMENT_THRU_DIA as POST_ATTACHMENT_THRU_DIA,
    DRAWING_PRECISION_BY_NAME as POST_DRAWING_PRECISION,
    JOURNAL_AXIS_HEIGHT_TOLERANCE_MM as POST_JOURNAL_AXIS_HEIGHT_TOLERANCE_MM,
)
import crank_boss_rim  # noqa: E402
import gear64_post_measure  # noqa: E402
import _native_tip_collar_air as native_tip_collar_air  # noqa: E402
import dt_tip_collar_air as tip_collar_air  # noqa: E402
from dt_cone_pivot_post_spec import CRANK_BORE_HEIGHT as POST_CRANK_Y  # noqa: E402
from dt_cone_tip_block_spec import (  # noqa: E402
    ADJUSTER_BORE_SPEC as TIP_ADJ_BORE_SPEC,
    ADJUSTER_AXIS_HEIGHT as TIP_ADJUSTER_AXIS_HEIGHT,
    ADJUSTER_EMBED as TIP_ADJ_EMBED,
    ADJUSTER_EMBED_WINDOW as TIP_ADJ_EMBED_WINDOW,
    AXIS_HEIGHT_TOL_MM as TIP_AXIS_HEIGHT_TOL_MM,
    BLOCK_X as TIP_BLOCK_X,
    BLOCK_Z as TIP_BLOCK_Z,
    DRAWING_PRECISION_BY_NAME as TIP_DRAWING_PRECISION,
    FOOT_BORE_SPEC as TIP_FOOT_BORE_SPEC,
    FOOT_TAP_STATION_TOL_MM as TIP_FOOT_TAP_STATION_TOL_MM,
    HOLDDOWN_LEDGE_RANGE_MM as TIP_HOLDDOWN_LEDGE_RANGE,
    HOLDDOWN_SCREW_LENGTH as TIP_HOLDDOWN_SCREW_LENGTH,
    HOLDDOWN_THREAD as TIP_HOLDDOWN_THREAD,
    FOOT_TAP_OFFSET_X as TIP_FOOT_TAP_OFFSET_X,
    FOOT_TAP_X as TIP_FOOT_TAP_X,
    FOOT_TAP_Z as TIP_FOOT_TAP_Z,
    PASSAGE_CENTER_PLACES as TIP_PASSAGE_CENTER_PLACES,
    PINCH_BORE_SPEC as TIP_PINCH_BORE_SPEC,
    PINCH_CLEARANCE_SPEC as TIP_PINCH_CLEARANCE_SPEC,
    PINCH_HEIGHT as TIP_PINCH_Y,
    PINCH_SCREW_LENGTH as TIP_PINCH_SCREW_LENGTH,
    PINCH_SCREW_SKU as TIP_PINCH_SCREW_SKU,
    SHAFT_PASSAGE_DIA as TIP_SHAFT_PASSAGE_DIA,
    WORST_PINCH_FAR_WALL_MM as TIP_WORST_PINCH_FAR_WALL_MM,
    printed_band_mm as tip_printed_band_mm,
)
from vn_cone_tip_block_screw_spec import (  # noqa: E402
    HEAD_DIA as HOLDDOWN_HEAD_DIA,
    HEAD_H as HOLDDOWN_HEAD_H,
    SHANK_DIA as HOLDDOWN_SHANK_DIA,
    SHANK_LEN as HOLDDOWN_SHANK_LEN,
    THREAD as HOLDDOWN_THREAD,
)
from vn_cone_tip_collar_spec import (  # noqa: E402
    BORE_DIA as COLLAR_BORE_DIA,
    INSTALLED_BORE_AXIS_OFFSET_MM as COLLAR_LOADED_OFFSET,
    WIDTH as COLLAR_WIDTH,
    WIDTH_BAND_MM as COLLAR_WIDTH_BAND_MM,
)
from vn_cone_tip_adjuster_spec import (  # noqa: E402
    BODY_LEN as ADJ_LEN,
    CUP_DEPTH as ADJ_CUP_DEPTH,
    CUP_DIA as ADJ_CUP_DIA,
    THREAD as ADJ_THREAD,
)
from build_vn_cone_tip_pinch_screw import (  # noqa: E402
    SHANK_LEN as PINCH_SHANK_LEN,
    SKU as PINCH_SKU,
    THREAD as PINCH_THREAD,
)
from dt_cone_gear_shaft_spec import (  # noqa: E402
    DRAWING_PRECISION_BY_NAME as SHAFT_DRAWING_PRECISION,
    ADJUSTER_EMBED as ADJ_EMBED,
    COLLAR_END_STATION as SHAFT_COLLAR_END,
    COLLAR_START_STATION as SHAFT_COLLAR_START,
    PIVOT_FROM_T006_NORTH_FACE as SHAFT_PIVOT_FROM_T006,
    SECTIONS as SHAFT_SECTIONS,
    TIP_BLOCK_LENGTH as SHAFT_TIP_BLOCK_LENGTH,
    TIP_BLOCK_NORTH_FACE_PIVOT_OFFSET as SHAFT_TIP_BLOCK_NORTH_OFFSET,
    TIP_COLLAR_END_STATION as SHAFT_TIP_COLLAR_END,
    TIP_COLLAR_START_STATION as SHAFT_TIP_COLLAR_START,
    printed_band as shaft_printed_band,
)
import dt_cone_gear_stack  # noqa: E402
from cone_stack_end_play import (  # noqa: E402
    COLLAR_FEELER,
    COLLAR_FEELER_BAND,
    SHAFT_END_PLAY,
)


def _require_tapped_thread(
    label: str, screw_thread: str, hole_spec, *, kind: str = "tapped"
) -> None:
    """Require the specified native tap tooling for the exact screw thread."""
    if hole_spec.kind != kind or hole_spec.size != screw_thread:
        raise AssertionError(
            f"{label}: screw {screw_thread} does not match "
            f"{hole_spec.kind} hole {hole_spec.size}"
        )
    if hole_spec.thread_class not in (None, "2B"):
        raise AssertionError(f"{label}: mating thread class is not UNC-2B")


def _require_clearance_size(label: str, screw_thread: str, hole_spec) -> None:
    """Require a native clearance hole for the thread's nominal screw size."""
    nominal_size = screw_thread.split("-", 1)[0]
    if hole_spec.kind != "clearance" or hole_spec.size != nominal_size:
        raise AssertionError(
            f"{label}: {screw_thread} screw does not match "
            f"{hole_spec.kind} hole {hole_spec.size}"
        )


# User ruling 2026-09-29 (eight-views-4.png, lower right): the tip block is a
# straight prism standing directly on the platform, its station fixed by ONE
# hold-down hole under its centre; its north face stands
# TIP_BLOCK_NORTH_FACE_PIVOT_OFFSET south of the pivot and the block grows
# south from it.  The platform's hole, cone_line and the shaft spec's own copy
# of the stack must agree, and the hole sits as far off the cone line as the
# block's foot tap sits off its adjuster axis, so the block stands centred on
# the line.  The MHA-VN-016 collar sits one COLLAR_FEELER off T006.
if (
    abs(TIP_BLOCK_STATION + TIP_BLOCK_Z / 2.0 - (PIVOT_STATION - TIP_BLOCK_NORTH_FACE_PIVOT_OFFSET)) > 1e-9
    or abs(TIP_BLOCK_STATION - (PIVOT_STATION - TIP_BLOCK_PIVOT_OFFSET)) > 1e-9
    or abs(PLAT_HOLDDOWN_LOCAL_Z + TIP_BLOCK_PIVOT_OFFSET) > 1e-9
    or abs(PLAT_HOLDDOWN_LOCAL_X - TIP_FOOT_TAP_OFFSET_X) > 1e-9
    or abs(TIP_FOOT_TAP_Z - TIP_BLOCK_Z / 2.0) > 1e-9
    or abs(SHAFT_TIP_BLOCK_NORTH_OFFSET - TIP_BLOCK_NORTH_FACE_PIVOT_OFFSET) > 1e-9
    or abs(SHAFT_PIVOT_FROM_T006 - (PIVOT_STATION - T006_NORTH_FACE)) > 1e-9
    or abs(SHAFT_TIP_BLOCK_LENGTH - TIP_BLOCK_Z) > 1e-9
    or abs(SHAFT_TIP_COLLAR_START - (T006_NORTH_FACE + COLLAR_FEELER)) > 1e-9
    or abs(SHAFT_TIP_COLLAR_END - SHAFT_TIP_COLLAR_START - COLLAR_WIDTH) > 1e-9
):
    raise AssertionError("cone_line tip-end stack drifted from the platform/collar/block parts")
# One journal drive height across the platform and both riders: plate
# thickness under each foot + bore height = 54 above the base top.  The block
# stands straight on PlateTop (no shim).
if (
    abs((Y_DRIVE - Y_BASE_TOP) - (PLAT_T + POST_BORE_HEIGHT)) > 1e-9
    or abs((Y_DRIVE - Y_BASE_TOP) - (PLAT_T + TIP_ADJUSTER_AXIS_HEIGHT)) > 1e-9
):
    raise AssertionError("cone axis height drifted between platform/post/block")
# The hold-down (MHA-VN-030): the placed part is the screw the block and the
# platform were sized for, and the platform's printed ledge range is the one
# the block's engagement/reach stack reads.
_require_tapped_thread("cone-tip hold-down", HOLDDOWN_THREAD, TIP_FOOT_BORE_SPEC)
if (
    HOLDDOWN_THREAD != TIP_HOLDDOWN_THREAD
    or abs(HOLDDOWN_SHANK_LEN - TIP_HOLDDOWN_SCREW_LENGTH) > 1e-9
    or abs(HOLDDOWN_HEAD_DIA - PLAT_HOLDDOWN_SCREW_HEAD_DIA) > 1e-9
    or abs(HOLDDOWN_HEAD_H - PLAT_HOLDDOWN_SCREW_HEAD_H) > 1e-9
):
    raise AssertionError("MHA-VN-030 is not the screw the tip block and platform were sized for")
if PLAT_HOLDDOWN_HOLE_SPEC.size != HOLDDOWN_THREAD.split("-", 1)[0]:
    raise AssertionError("platform hold-down counterbore is not sized for MHA-VN-030")
if any(
    abs(_have - _want) > 1e-9
    for _have, _want in zip(PLAT_HOLDDOWN_LEDGE_RANGE, TIP_HOLDDOWN_LEDGE_RANGE, strict=True)
):
    raise AssertionError(
        f"platform hold-down ledge {PLAT_HOLDDOWN_LEDGE_RANGE} differs from the "
        f"range the tip block's engagement stack reads {TIP_HOLDDOWN_LEDGE_RANGE}"
    )
# U30 post mount (I22): each MHA-VN-031 seats on the MHA-DT-005 counterbore floor and
# is cut to fit into the MHA-DT-020 tap: never proud of the plate underside, and
# at least 0.90D of thread (U37c/U41's named exception to rule 12) both at the
# modelled cut length and at the platform spec's printed worst case.
_require_tapped_thread("cone-post mount", POST_SCREW_THREAD, POST_MOUNT_SPEC)
POST_SCREW_SEAT = POST_BLOCK_HEIGHT - POST_CBORE_DEPTH  # above PlateTop
POST_SCREW_INTO_PLATE = POST_SCREW_LEN - POST_SCREW_SEAT
if POST_SCREW_INTO_PLATE > PLAT_T:
    raise AssertionError("MHA-VN-031 stands proud of the MHA-DT-020 underside")
if (
    POST_SCREW_INTO_PLATE - 2.0 * POST_MOUNT_TAP_EDGE_BREAK
    < 0.90 * POST_MOUNT_THREAD_DIA
    or POST_MOUNT_ENGAGEMENT_WORST_DIAMETERS < 0.90
):
    raise AssertionError("MHA-VN-031 engages the MHA-DT-020 tap under 0.90D")
# The shaft is placed by its front stub end; keep the station in lockstep with
# the part's FRONT_STUB.
if abs(SHAFT_FRONT_STATION + SHAFT_FRONT_STUB) > 1e-9:
    raise AssertionError("SHAFT_FRONT_STATION out of sync with the shaft FRONT_STUB")


def _plat_side_half_widths(s: float) -> dict[str, float]:
    """The plate's own half-widths at cone station ``s`` on its local +x
    (west) and -x (east) sides, keyed by the sign a rider placed with the
    plate's ROT_Y_INCLINE shares; both negative if s is off the plate, so a
    rider run past either end fails its containment check instead of reading
    extrapolated edges."""
    z_local = s - PIVOT_STATION  # platform local z (+ along increasing station)
    if not (PLAT_OVERHANG - PLAT_LEN - 1e-9 <= z_local <= PLAT_OVERHANG + 1e-9):
        return {"+X": -1.0, "-X": -1.0}
    frac = (PLAT_OVERHANG - z_local) / PLAT_LEN
    return {
        "+X": PLAT_WEST_N + (PLAT_WEST_S - PLAT_WEST_N) * frac,
        "-X": PLAT_EAST_N + (PLAT_EAST_S - PLAT_EAST_N) * frac,
    }


def _plat_half_width(s: float) -> float:
    """Platform MIN half-width at cone station s: the narrower of the east
    taper and the west flare (the WEST side is the narrow one near the north
    end -- WEST_HALF_N vs HALF_WIDTH_N); negative if s is off the
    plate. Riders are centred on the shaft plan line (local x 0), so the
    narrower side at each station bounds their containment."""
    return min(_plat_side_half_widths(s).values())


# Both riders stand fully ON the plate (plan, in the platform's own inclined
# frame: both are centred on the shaft-axis plan line, so only the along-axis
# span and the half-width at each end matter), each face at least
# PLATFORM_CONTAINMENT_FLOOR_MM inside the plate's edge.
PLATFORM_CONTAINMENT_FLOOR_MM = 0.25
# Each rider's foot: label -> (south station, north station, half-width).
PLATFORM_RIDER_SPANS: dict[str, tuple[float, float, float]] = {
    "pivot post": (
        POST_STATION - POST_BLOCK_DIA / 2.0,
        POST_STATION + POST_BLOCK_DIA / 2.0,
        POST_BLOCK_DIA / 2.0,
    ),
    # The straight prism's foot is its full plan section.
    "tip block": (
        TIP_BLOCK_STATION - TIP_BLOCK_Z / 2.0,
        TIP_BLOCK_STATION + TIP_BLOCK_Z / 2.0,
        TIP_BLOCK_X / 2.0,
    ),
}
for _lbl, (_south, _north, _hx) in PLATFORM_RIDER_SPANS.items():
    for _end in (_south, _north):
        if _plat_half_width(_end) < _hx + PLATFORM_CONTAINMENT_FLOOR_MM:
            raise AssertionError(
                f"{_lbl} overhangs the swing platform at station {_end:g}"
            )


# r3 (Main, 2026-09-25): the tip block also stands on the plate at its PRINT's
# worst case.  Its two side faces sit asymmetrically there -- PassageCenter
# and FootTapX locate the adjuster axis and the hold-down tap from the -X
# face and the width's band lands on the other -- so each face is held
# against its own plate edge, the block's +X (pinch-head) face against the
# trimmed west edge and its -X face against the east one, with the nominal
# contract's PLATFORM_CONTAINMENT_FLOOR_MM plus TIP_PRINT_WORST_MARGIN_MM,
# from the north face to the south face (the plate's edges run straight
# between those stations).
TIP_PRINT_WORST_MARGIN_MM = 0.25


def tip_block_print_worst_containment_mm(half_widths: dict[str, float]) -> float:
    """Least plate edge left outside the block's side faces, over its whole
    footprint, given each face's worst distance from the plate centreline;
    raise if it is under the floor plus the print-worst margin."""
    margins = [
        _plat_side_half_widths(end)[face] - half_widths[face]
        for end in (
            TIP_BLOCK_STATION - TIP_BLOCK_Z / 2.0,
            TIP_BLOCK_STATION + TIP_BLOCK_Z / 2.0,
        )
        for face in ("+X", "-X")
    ]
    margin = min(margins)
    if margin < PLATFORM_CONTAINMENT_FLOOR_MM + TIP_PRINT_WORST_MARGIN_MM - 1e-9:
        raise AssertionError(
            f"tip block can overhang the swing platform at its printed limits: "
            f"{margin:.3f} left (< {PLATFORM_CONTAINMENT_FLOOR_MM} + "
            f"{TIP_PRINT_WORST_MARGIN_MM})"
        )
    return margin


# --- where the hold-down puts the tip block (user ruling 2026-09-29) --------
# The block is located by its foot tap on MHA-VN-030 in the platform's hold-down
# hole, not slid to the shaft at fit-up, so every station it used to take up
# closes by print tolerance.  The screw floats in its drilled close-clearance
# hole; the hole's two stations from the pivot bore (HoldDownX, HoldDownZ)
# and the tap's two stations carry explicit +/-0.10 bands.
_DRILLED_HOLE_PLUS_MM = float(
    str(_config.title_block("drilled_hole")["display_plus"]).lstrip("+")
)
HOLDDOWN_SCREW_FLOAT_MM = (
    PLAT_HOLDDOWN_CLEARANCE_DIA + _DRILLED_HOLE_PLUS_MM - HOLDDOWN_SHANK_DIA
) / 2.0
# Block north face along the cone axis, about its nominal station off the
# pivot bore.
TIP_NORTH_FACE_BAND_MM = (
    PLAT_HOLDDOWN_STATION_TOL_MM + HOLDDOWN_SCREW_FLOAT_MM + TIP_FOOT_TAP_STATION_TOL_MM
)
# The tap's lateral station about its nominal PLAT_HOLDDOWN_LOCAL_X.
TIP_TAP_LATERAL_BAND_MM = (
    PLAT_HOLDDOWN_STATION_TOL_MM + HOLDDOWN_SCREW_FLOAT_MM + TIP_FOOT_TAP_STATION_TOL_MM
)
# Each side face's worst distance from the plate centreline: the tap stands
# at PLAT_HOLDDOWN_LOCAL_X, the -X face FootTapX to its -X side, and the +X
# face the width on from there.
_TIP_WIDTH_MAX = TIP_BLOCK_X + tip_printed_band_mm(TIP_DRAWING_PRECISION["Width"])
TIP_WORST_HALF_WIDTHS_MM = {
    "-X": TIP_FOOT_TAP_X - PLAT_HOLDDOWN_LOCAL_X + TIP_TAP_LATERAL_BAND_MM,
    "+X": _TIP_WIDTH_MAX - TIP_FOOT_TAP_X + PLAT_HOLDDOWN_LOCAL_X + TIP_TAP_LATERAL_BAND_MM,
}
TIP_PRINT_WORST_CONTAINMENT_MM = tip_block_print_worst_containment_mm(
    TIP_WORST_HALF_WIDTHS_MM
)
# Where the tip ends is owned by the end-play stack below: it sits on the
# adjuster's cup apex, and the cup rim stays inside the adjuster's working
# window.
_TIP_END_STATION = SHAFT_FRONT_STATION + SHAFT_SECTIONS[-1][1]
# The stub end stands 1.0 mm proud of the post's inclined journal face.
_STUB_END_Z = cone_station(SHAFT_FRONT_STATION)[2]
_POST_SOUTH_STATION = POST_STATION - POST_CONE_BOSS_LENGTH / 2.0
_POST_SOUTH_Z = cone_station(_POST_SOUTH_STATION)[2]
if SHAFT_FRONT_STATION > _POST_SOUTH_STATION - 1.0 + 1e-9:
    raise AssertionError(
        f"cone-shaft stub end {_STUB_END_Z:.2f} not proud of the post's south "
        f"flank {_POST_SOUTH_Z:.2f}"
    )
# Axial capture (#914): the tip adjuster pushes the shaft south; the collar's
# south face bears on the post's north boss face and the 64T sits on its north
# face.  The mates below are contacts, so the spec must put both faces there.
_POST_NORTH_STATION = POST_STATION + POST_CONE_BOSS_LENGTH / 2.0
if abs(SHAFT_FRONT_STATION + SHAFT_COLLAR_START - _POST_NORTH_STATION) > 1e-9:
    raise AssertionError("cone-shaft collar face is not on the post's north boss face")
_GEAR64_SOUTH_STATION = GEAR64_CENTRE_STATION - GEAR64_FACE / 2.0
if abs(SHAFT_FRONT_STATION + SHAFT_COLLAR_END - _GEAR64_SOUTH_STATION) > 1e-9:
    raise AssertionError("64T south face is not on the cone-shaft collar")
# Both faces are mated by name: the shaft's CollarFace and the post's
# BossNorth, a plane the post build lays on the whole north annulus.  A point
# pick there is view-dependent (IModelDocExtension::SelectByID2 picks FACEs
# through the graphics ray), and one 0.33 mm outside the collar selected the
# collar's OD on some seats (#916).
# --- tip end-play stack (item 5, v4_t00471 / 7:49) ---------------------------
# Along the axis, south to north: T006 gear | feeler gap | MHA-VN-016 stack
# collar, locked on the Sec4 D-flat | air | block | shaft tip | the 94025A164
# adjuster's conical cup, its #10-32 thread tapped through the block
# (rule-12 E11/W1). The shaft's terminal D-flat end cannot reach the cup apex:
# it seats on the remaining round edge where it meets the cone wall,
# ADJ_SEAT_DEPTH short of the apex (end radius / tan of the vendor cup's
# half-angle). The adjuster backs out from nominal ADJ_EMBED by that depth;
# the current end radius is owned by SHAFT_SECTIONS, not an old stock size.
# The top slit and 91794A112 pinch screw lock that setting.
TIP_SOUTH_STATION = TIP_BLOCK_STATION - TIP_BLOCK_Z / 2.0
COLLAR_STATION = T006_NORTH_FACE + COLLAR_FEELER
_STUB_DIA = SHAFT_SECTIONS[-1][0] * 25.4
ADJ_CUP_HALF_ANGLE = math.atan((ADJ_CUP_DIA / 2.0) / ADJ_CUP_DEPTH)
ADJ_SEAT_DEPTH = (_STUB_DIA / 2.0) / math.tan(ADJ_CUP_HALF_ANGLE)
ADJ_THREAD_ENGAGEMENT = ADJ_EMBED - ADJ_SEAT_DEPTH
ADJ_HEAD_STATION = (
    TIP_BLOCK_STATION + TIP_BLOCK_Z / 2.0 + (ADJ_LEN - ADJ_THREAD_ENGAGEMENT)
)
_ADJ_CUP_RIM = ADJ_HEAD_STATION - ADJ_LEN
_ADJ_CUP_APEX = _ADJ_CUP_RIM + ADJ_CUP_DEPTH
_STUB_START = SHAFT_FRONT_STATION + SHAFT_SECTIONS[-2][1]
# The collar's set screw bites the Sec4 D-flat, so its whole width rides the
# terminal land, on a bore made for that land.
if not (
    _STUB_START + 1.0 <= COLLAR_STATION
    and COLLAR_STATION + COLLAR_WIDTH <= TIP_SOUTH_STATION
):
    raise AssertionError("MHA-VN-016 stack collar rides off the Sec4 land or into the block")
if abs(COLLAR_BORE_DIA - _STUB_DIA) > 0.05:
    raise AssertionError("MHA-VN-016 collar bore does not match the tip land dia")
_require_tapped_thread("cone-tip adjuster", ADJ_THREAD, TIP_ADJ_BORE_SPEC)
# adjuster_cup_in_working_window: the embed is the block spec's; the nominal
# engagement sits in the working window here, and the print-worst stack
# below (TIP_EMBED_WORST_MM) holds both of its extremes there too.
if ADJ_EMBED != TIP_ADJ_EMBED or not (
    TIP_ADJ_EMBED_WINDOW[0] <= ADJ_THREAD_ENGAGEMENT <= TIP_ADJ_EMBED_WINDOW[1]
):
    raise AssertionError("adjuster cup rim is outside its working window")
if not 0.0 < ADJ_CUP_DEPTH < ADJ_LEN:
    raise AssertionError("adjuster cup depth is outside the stock body")
if ADJ_CUP_DIA < _STUB_DIA + 0.25:
    raise AssertionError("adjuster cup rim is too tight around the tip stub")
if not 0.0 < ADJ_SEAT_DEPTH < ADJ_CUP_DEPTH:
    raise AssertionError("shaft end does not seat on the adjuster cup wall")
if abs(_TIP_END_STATION + ADJ_SEAT_DEPTH - _ADJ_CUP_APEX) > 1e-6:
    raise AssertionError(
        f"shaft tip {_TIP_END_STATION:.6f} does not seat on the vendor cup wall "
        f"{ADJ_SEAT_DEPTH:.6f} short of its apex {_ADJ_CUP_APEX:.6f}"
    )
if TIP_SHAFT_PASSAGE_DIA < _STUB_DIA + 0.25:
    raise AssertionError("tip-block passage too tight around the shaft tip")

_require_tapped_thread("cone-tip pinch far jaw", PINCH_THREAD, TIP_PINCH_BORE_SPEC)
_require_clearance_size(
    "cone-tip pinch near jaw", PINCH_THREAD, TIP_PINCH_CLEARANCE_SPEC
)
# r3: the screw threads only into the FAR jaw, from the slit's far wall on,
# and that wall stands at most WORST_PINCH_FAR_WALL_MM from the head's (+X)
# face at the printed limits; the placed screw must be the one the block's
# stack was sized for.
if PINCH_SKU != TIP_PINCH_SCREW_SKU or abs(PINCH_SHANK_LEN - TIP_PINCH_SCREW_LENGTH) > 1e-9:
    raise AssertionError(
        f"placed pinch screw {PINCH_SKU} ({PINCH_SHANK_LEN}) is not the tip "
        f"block's {TIP_PINCH_SCREW_SKU} ({TIP_PINCH_SCREW_LENGTH})"
    )
if PINCH_SHANK_LEN - TIP_WORST_PINCH_FAR_WALL_MM < 1.5 * THREAD_MAJOR_MM[PINCH_THREAD]:
    raise AssertionError(
        "pinch screw lacks 1.5D of far-jaw thread at the printed worst case"
    )
# The crank pedestal is GONE as a separate base-mounted part: the cone pivot
# post and the crank pedestal are ONE green column riding the swing platform
# (user-confirmed vs v4_t00411/t00417), so the crank rig swings with the cone
# set and the 16T<->64T mesh survives the disengage. Cross-script agreement
# for the merged column's crank bore and the platform's "crank axis":
_PPIVOT = cone_station(PIVOT_STATION)
# The centered legacy harmonic base is the installation envelope. The engaged
# platform's four sharp plan vertices must all remain on its top plate; the
# filleted outline is contained by that convex polygon. This catches a plate
# length regression before SolidWorks inserts an off-base rider.
_BASE_X_LIMIT = BASE_TOP_LENGTH / 2.0
_BASE_Z_LIMIT = BASE_TOP_WIDTH / 2.0
_PLATFORM_VERTICES = (
    (-PLAT_EAST_N, PLAT_OVERHANG),
    (PLAT_WEST_N, PLAT_OVERHANG),
    (PLAT_WEST_S, PLAT_OVERHANG - PLAT_LEN),
    (-PLAT_EAST_S, PLAT_OVERHANG - PLAT_LEN),
)
for _x_local, _z_local in _PLATFORM_VERTICES:
    _x_machine = _PPIVOT[0] + _x_local * COS_I + _z_local * SIN_I
    _z_machine = _PPIVOT[2] - _x_local * SIN_I + _z_local * COS_I
    if abs(_x_machine) > _BASE_X_LIMIT + 1e-9 or abs(_z_machine) > _BASE_Z_LIMIT + 1e-9:
        raise AssertionError(
            f"cone swing platform vertex ({_x_machine:.3f}, {_z_machine:.3f}) "
            f"is outside harmonic-base top ({_BASE_X_LIMIT:.3f}, {_BASE_Z_LIMIT:.3f})"
        )

# CRANK_AXIS_OFF is the distance the plate's crank axis sits EAST of the
# pivot (east = machine -x).  The crank train mates to it, so it is the
# fixed axis: pivot.x - X_CRANK, at Y_CRANK.
if abs(PLAT_CRANK_OFF - (_PPIVOT[0] - X_CRANK)) > 1e-6:
    raise AssertionError(
        f"platform CRANK_AXIS_OFF {PLAT_CRANK_OFF} != pivot.x - X_CRANK "
        f"{_PPIVOT[0] - X_CRANK:.6f}"
    )
if abs(PLAT_CRANK_Y - (Y_CRANK - Y_BASE_TOP)) > 1e-6:
    raise AssertionError("platform CRANK_AXIS_Y != Y_CRANK - Y_BASE_TOP")
if abs(_PPOST[0] - X_CRANK) > 1e-9:
    raise AssertionError("v2 crank boss no longer shares the post body centre x")
if abs(POST_CRANK_Y - (Y_CRANK - Y_BASE_TOP - PLAT_T)) > 1e-6:
    raise AssertionError("column CRANK_BORE_Y != Y_CRANK - Y_BASE_TOP - PLAT_T")
# Axial closure around the v2 boss after the casting's exact Ry(180).  The turn
# reverses local Z, so the harvested asymmetric boss now runs from
# post.z - (start + length) to post.z - start.  South of it the crank seat
# stack closes the gap to the chain wheel's seat face: the integral collar,
# then MHA-DT-036, flat on its rear face and faced at assembly to fill the gap to
# the cast south face.  The shaft's only end play is the 16T's feeler gap to
# the boss's north face.
# The 16T follows the translated 64T contact row to the boss's north.
_POST_BOSS_SOUTH = _PPOST[2] - (POST_CRANK_BOSS_START_Z + POST_CRANK_BOSS_LENGTH)
_PINION_SOUTH = PINION_TOOTH_Z - PINION_FACE / 2.0
CRANK_SEAT_WASHER_GAP = _POST_BOSS_SOUTH - CRANK_SEAT_WASHER_Z0
CRANK_SEAT_WASHER_FLOAT = _POST_BOSS_SOUTH - CRANK_SEAT_WASHER_REAR_Z
_BOSS_NORTH_GAP = _PINION_SOUTH - _POST_BOSS_NORTH
# The feeler sets the south face directly off the restored boss (MHA-DT-000).
PINION_BOSS_NORTH_GAP_RANGE = (PINION_SEAT_FEELER, PINION_SEAT_GAP_MAX)
_GAP_LO, _GAP_HI = PINION_BOSS_NORTH_GAP_RANGE
# (1) The modelled gap is the washer spec's nominal fit, and the washer, at
# that thickness, is seated on both faces.
if abs(CRANK_SEAT_WASHER_GAP - SEAT_WASHER.GAP_NOMINAL) > 1e-6:
    raise AssertionError(
        f"MHA-DT-036 gap {CRANK_SEAT_WASHER_GAP:.4f} in the layout is not the washer "
        f"spec's nominal fit {SEAT_WASHER.GAP_NOMINAL:.4f}"
    )
if abs(CRANK_SEAT_WASHER_FLOAT) > 1e-6:
    raise AssertionError(
        f"MHA-DT-036 is not seated on both faces: {CRANK_SEAT_WASHER_FLOAT:.4f} float"
    )
# (2) Every accepted set of parts is fitted from the blank without going under
# the floor.
_BLANK_FACEABLE = SEAT_WASHER.BLANK_THICKNESS_MIN - SEAT_WASHER.FACING_ALLOWANCE
if not (
    SEAT_WASHER.THICKNESS_FLOOR - 1e-9
    <= SEAT_WASHER.GAP_MIN
    <= SEAT_WASHER.GAP_MAX
    <= _BLANK_FACEABLE + 1e-9
):
    raise AssertionError(
        f"MHA-DT-036 fit range {SEAT_WASHER.GAP_MIN:.3f}-{SEAT_WASHER.GAP_MAX:.3f} "
        f"is outside {SEAT_WASHER.THICKNESS_FLOOR}-{_BLANK_FACEABLE:.3f}"
    )
# (3) With the washer seated, the shaft's end play is the 16T's feeler gap.
CRANK_SHAFT_END_PLAY = _BOSS_NORTH_GAP + CRANK_SEAT_WASHER_FLOAT
if abs(CRANK_SHAFT_END_PLAY - PINION_SEAT_FEELER) > 1e-6:
    raise AssertionError(
        f"crankshaft end play {CRANK_SHAFT_END_PLAY:.4f} is not the "
        f"{PINION_SEAT_FEELER} 16T feeler gap"
    )
if not (
    _GAP_LO - 1e-6
    <= _BOSS_NORTH_GAP
    < _GAP_HI
):
    raise AssertionError("v2 crank boss north/pinion clearance left its derived band")

# The grown 64T clears every restored post feature at print-worst.
GEAR64_POST_OFFSET = GEAR64_CENTRE_STATION - POST_STATION
_GEAR64_FROM_POST = [a - b for a, b in zip(GEAR64_SEAT, _PPOST, strict=True)]
if (
    max(
        abs(_GEAR64_FROM_POST[0] - GEAR64_POST_OFFSET * crank_boss_rim.SIN_I),
        abs(_GEAR64_FROM_POST[1]),
        abs(_GEAR64_FROM_POST[2] - GEAR64_POST_OFFSET * crank_boss_rim.COS_I),
        abs(Y_CRANK - Y_DRIVE - crank_boss_rim.CRANK_AXIS_Y),
    )
    > 1e-3  # the post prints its incline to 4 places; the layout keeps full precision
):
    raise AssertionError("crank_boss_rim's post frame no longer matches this layout")
GEAR64_POST_CLEARANCES = crank_boss_rim.clearances(gear_offset=GEAR64_POST_OFFSET)
assert GEAR64_POST_CLEARANCES and min(GEAR64_POST_CLEARANCES.values()) >= crank_boss_rim.FLOOR_CLEARANCE_MM, "user ruling 2026-09-28"


# Every length term below is what an ACCEPTED part may be: the sheet's printed
# nominal (the model rounded to its printed places) under the band that sheet
# prints for it -- the title block's metric row, or the dimension's own band --
# never the inch grade behind the row (Codex P2 on #892).
_SHAFT_LENGTH_LIMITS = deviations(CRANKSHAFT_LENGTH_BAND)  # (lower, upper)


def pinion_pin_edge_stack(
    edge_nominal: float, shaft_length: float, pinion_overall_length: float
) -> dict[str, float]:
    """W15's worst-case wall from the 16T pin hole to the shaft's north end.

    Each term comes from the source that owns it: the shaft printed at its
    lower limit (dt_crankshaft_spec), the seat gap opening from its nominal to the
    range's ceiling (the pinion, and its pin, move north), the boss mid-length
    the pin is laid out at moving north with a long face (W15's .X allowance,
    which the face's printed band sits inside) and a long overall length (its
    printed row), the laid-out station's allowance
    (dt_crank_pinion_spec), and the title block's drilled-hole oversize on the
    pin's radius.
    """
    shaft_lower, _ = printed_deviations(
        shaft_length, PINION_SHAFT_LENGTH_PLACES, _SHAFT_LENGTH_LIMITS
    )
    face_upper = PINION_W15_FACE_ALLOWANCE
    _, overall_upper = printed_deviations(pinion_overall_length, PINION_OVERALL_LENGTH_PLACES)
    return {
        "nominal": edge_nominal,
        "shaft length": shaft_lower,
        "seat gap": -(_GAP_HI - _BOSS_NORTH_GAP),
        "boss mid-length": -(face_upper + overall_upper) / 2.0,
        "pin layout": -PINION_PIN_LAYOUT_ALLOWANCE,
        "drill oversize": -float(_config.title_block("drilled_hole")["plus_mm"]) / 2.0,
    }


def pinion_recess_stack(
    recess_nominal: float, shaft_length: float, pinion_overall_length: float
) -> dict[str, float]:
    """W15's worst-case recess of the shaft end inside the 16T boss.

    A pinion at its printed lower limit, a seat gap closing from its nominal to
    the range's floor, and a shaft at its printed upper limit each bring the
    shaft end out toward the boss face.
    """
    overall_lower, _ = printed_deviations(pinion_overall_length, PINION_OVERALL_LENGTH_PLACES)
    _, shaft_upper = printed_deviations(
        shaft_length, PINION_SHAFT_LENGTH_PLACES, _SHAFT_LENGTH_LIMITS
    )
    return {
        "nominal": recess_nominal,
        "pinion overall length": overall_lower,
        "seat gap": -(_BOSS_NORTH_GAP - _GAP_LO),
        "shaft length": -shaft_upper,
    }


def _stack_text(stack: dict[str, float]) -> str:
    terms = ", ".join(f"{name} {value:+.3f}" for name, value in stack.items())
    return f"{terms} = {sum(stack.values()):.3f}"


PINION_PIN_EDGE_STACK = pinion_pin_edge_stack(
    PINION_PIN_EDGE_NOMINAL_ACTUAL, CS_SHAFT_LENGTH, PINION_OVERALL_LENGTH
)
if sum(PINION_PIN_EDGE_STACK.values()) < PINION_PIN_EDGE_MIN_WORST:
    raise AssertionError(
        f"16T pin wall to the shaft end, worst case: "
        f"{_stack_text(PINION_PIN_EDGE_STACK)} < {PINION_PIN_EDGE_MIN_WORST}"
    )
PINION_RECESS_STACK = pinion_recess_stack(
    PINION_RECESS_NOMINAL, CS_SHAFT_LENGTH, PINION_OVERALL_LENGTH
)
if sum(PINION_RECESS_STACK.values()) < PINION_RECESS_MIN_WORST:
    raise AssertionError(
        f"crankshaft end recess inside the 16T boss, worst case: "
        f"{_stack_text(PINION_RECESS_STACK)} < {PINION_RECESS_MIN_WORST}"
    )

# --- The 16T's north end under the inclined T120 (user ruling c'' variant B,
# 2026-09-30) ----------------------------------------------------------------
# The inclined T120 reaches toward the crank axis above the 16T. Its teeth run
# past the 64T row so the row stays covered, and their north end is turned
# down so it passes under the T120 rim: full OD for the printed shoulder,
# the turned diameter beyond it (dt_crank_pinion_spec). Every check is the worst
# over the corners of every printed band that moves the parts, at both crank
# end-play extremes -- the pinion as set on its feeler, and run south onto the
# boss -- with the cone stack anywhere in its north float.
import itertools  # noqa: E402

import numpy as np  # noqa: E402

from dt_cone_gear_shaft_spec import COLLAR_THICKNESS as SHAFT_COLLAR_THICKNESS  # noqa: E402
from dt_cone_pivot_post_spec import (  # noqa: E402
    CRANK_ABOVE_CONE as POST_CRANK_ABOVE_CONE,
    CRANK_ABOVE_CONE_BAND as POST_CRANK_ABOVE_CONE_BAND,
    CRANK_BOSS_NORTH_FACE as POST_CRANK_BOSS_NORTH_FACE,
)
from dt_crank_drive_gear_spec import FACE_WIDTH_BAND as GEAR64_FACE_WIDTH_BAND  # noqa: E402
from crank_mesh_stack import (  # noqa: E402
    CRANK_BEARING_LENGTH as CRANK_MESH_BEARING_LENGTH,
    CRANK_OVERHANG as CRANK_MESH_OVERHANG,
    MESH_LEVER as CRANK_MESH_LEVER,
    PINION_HALF_FACE_MAX as CRANK_MESH_PINION_HALF_FACE_MAX,
    POST_ANGLE_DEG as CRANK_MESH_POST_ANGLE_DEG,
    TOOTH_RUNOUT_TIR_MM as CRANK_MESH_TOOTH_RUNOUT_TIR,
)
from dt_crank_pinion_spec import (  # noqa: E402
    BORE_DIAMETRAL_CLEARANCE as PINION_BORE_DIAMETRAL_CLEARANCE,
    DRAWING_PRECISION_BY_NAME as PINION_DRAWING_PRECISION,
    OUTSIDE_DIA as PINION_OUTSIDE_DIA,
    OUTSIDE_DIA_TOLERANCE_MM as PINION_OUTSIDE_DIA_TOLERANCE,
    SHOULDER_LENGTH as PINION_SHOULDER_LENGTH,
    SHOULDER_LENGTH_FITUP_MIN as PINION_SHOULDER_LENGTH_FITUP_MIN,
    SHOULDER_LENGTH_LIMITS as PINION_SHOULDER_LIMITS,
    T120_FITUP_FEELER_MM as PINION_T120_FITUP_FEELER,
    T120_FITUP_PUSHED as PINION_T120_FITUP_PUSHED,
    TURNED_DIA as PINION_TURNED_DIA,
    TURNED_DIA_FITUP_MIN as PINION_TURNED_DIA_FITUP_MIN,
    TURNED_DIA_TOLERANCE_MM as PINION_TURNED_DIA_TOLERANCE,
)
from gear_seat_fit import GEAR_SEAT_CLEARANCE  # noqa: E402

# (lower, upper) deviation of each moving surface from the model; + is north
# (crank +Z, cone +station), or up for the crank height.
_PINION_FACE_BAND = printed_deviations(PINION_FACE, PINION_FACE_WIDTH_PLACES, PINION_FACE_LIMITS)
_PINION_SHOULDER_BAND = printed_deviations(
    PINION_SHOULDER_LENGTH, PINION_DRAWING_PRECISION["ShoulderLength"], PINION_SHOULDER_LIMITS
)
_PINION_TIP_RADIUS_BAND = tuple(
    d / 2.0
    for d in printed_deviations(
        PINION_OUTSIDE_DIA,
        PINION_DRAWING_PRECISION["OutsideDia"],
        (-PINION_OUTSIDE_DIA_TOLERANCE, PINION_OUTSIDE_DIA_TOLERANCE),
    )
)
_PINION_TURNED_DIA_BAND = printed_deviations(
    PINION_TURNED_DIA,
    PINION_DRAWING_PRECISION["TurnedDia"],
    (-PINION_TURNED_DIA_TOLERANCE, PINION_TURNED_DIA_TOLERANCE),
)
# Only the turned band's largest radius can close on T120.
_PINION_TURNED_RADIUS_UP = _PINION_TURNED_DIA_BAND[1] / 2.0
_BOSS_NORTH_BAND = printed_deviations(
    POST_CRANK_BOSS_NORTH_FACE, POST_DRAWING_PRECISION["CrankBossStartZ"]
)
_CONE_BOSS_NORTH_BAND = tuple(
    d / 2.0
    for d in printed_deviations(POST_CONE_BOSS_LENGTH, POST_DRAWING_PRECISION["ConeBossLen"])
)
_COLLAR_WIDTH_BAND = printed_deviations(
    SHAFT_COLLAR_THICKNESS, SHAFT_DRAWING_PRECISION["CollarWidth"]
)
_GEAR64_FACE_LIMITS = deviations(GEAR64_FACE_WIDTH_BAND)
_CRANK_HEIGHT_BAND = printed_deviations(
    POST_CRANK_ABOVE_CONE,
    POST_DRAWING_PRECISION["CrankAboveCone"],
    deviations(POST_CRANK_ABOVE_CONE_BAND),
)
# The crank's end play: set on the feeler, or run south onto the boss.
PINION_END_PLAY = (-PINION_SEAT_FEELER, 0.0)
_CONE_FLOATS = (0.0, CONE_FLOAT_NORTH / 2.0, CONE_FLOAT_NORTH)

_TIP120 = _cone_tip_radius_max(120)
# T120 as a solid: its tip cylinder from its south face to its north face,
# the teeth and web inside it counted as metal. Bound the complete displaced
# envelope rather than clipping the raised crank's search to the old 10 mm.
_T120_REACH = _TIP120 + CRANK_ACTUAL_C2C + 2.0 * CONE_FACE
# T120's own face band past its south face; _cone_corners already moves the
# south face by the 64T's band, so the stack's face_band would count it twice.
_T120_NORTH_BAND = CONE_GEAR_FACE_WIDTH_BAND  # (upper, lower)


# Fit offsets and axis poses between the 16T and T120, each at its printed
# worst (the same fits and angularities crank_mesh_stack carries at the
# mesh), summed arithmetically: the most each can move a T120 point relative
# to the 16T, (radial, axial) in the crank frame.  Radial is toward the crank
# axis; axial is along it, carried on the 16T's tip radius or T120's rim.
_PINION_TIP_R_MAX = R16 + ADD16 + max(_PINION_TIP_RADIUS_BAND)
# The band's north end beyond the crank's mesh plane, and T120's north face
# beyond the post's cone-boss north face with the stack at its north float.
_BAND_END_PAST_MESH = CRANK_MESH_PINION_HALF_FACE_MAX
_T120_OVERHANG = (
    _T120_SOUTH_FACE_STATION
    + CONE_FACE
    + max(_T120_NORTH_BAND)
    + max(_GEAR64_FACE_LIMITS)
    + max(_COLLAR_WIDTH_BAND)
    + CONE_FLOAT_NORTH
    - _POST_NORTH_STATION
)
# The shaft-in-bushing running fit: the crank in its journal, the cone shaft
# in the post's cone boss.
_RUNNING_CLEARANCE = float(_config.fit("shaft_in_bushing")["diametral_clearance_mm"][1])
_CRANK_TILT = _RUNNING_CLEARANCE / CRANK_MESH_BEARING_LENGTH
_PINION_COCK = PINION_BORE_DIAMETRAL_CLEARANCE[1] / PINION_OVERALL_LENGTH
_CONE_TILT = _RUNNING_CLEARANCE / POST_CONE_BOSS_LENGTH
_POST_ANGLE = math.tan(math.radians(CRANK_MESH_POST_ANGLE_DEG))


def _cone_frame_moves(
    gear: str, overhang: float, rim: float
) -> dict[str, tuple[float, float]]:
    """Cone-frame (radial, axial) moves of a cone-shaft gear's rim ``rim``
    from its axis, the rim ``overhang`` north of the post's cone-boss north
    face."""
    return {
        f"{gear} seat eccentricity": (GEAR_SEAT_CLEARANCE[1] / 2.0, 0.0),
        "cone shaft float in the post boss": (
            _RUNNING_CLEARANCE / 2.0 + _CONE_TILT * overhang,
            _CONE_TILT * rim,
        ),
        "post cone-bore angle": (
            (overhang + POST_CONE_BOSS_LENGTH / 2.0) * _POST_ANGLE,
            rim * _POST_ANGLE,
        ),
    }


_T120_MOVES = _cone_frame_moves("T120", _T120_OVERHANG, _TIP120)
T120_POSE_TERMS = {
    "crank journal float": (
        _RUNNING_CLEARANCE / 2.0
        + _CRANK_TILT * (CRANK_MESH_OVERHANG + _BAND_END_PAST_MESH),
        _CRANK_TILT * _PINION_TIP_R_MAX,
    ),
    # The bore fit moves the 16T at most c/2 anywhere over its bore, the band
    # included (the cock is bounded by the same bore wall), so the cock adds
    # only its axial lift at the tip radius.
    "16T bore on the crankshaft": (
        PINION_BORE_DIAMETRAL_CLEARANCE[1] / 2.0,
        _PINION_COCK * _PINION_TIP_R_MAX,
    ),
    # The sheet prints no runout for TurnedDia or OutsideDia; the surfaces are
    # turned on the bore, so they carry the 0.05 TIR the mesh stack gives the
    # teeth, half of it as eccentricity.
    "16T runout to the bore": (CRANK_MESH_TOOTH_RUNOUT_TIR / 2.0, 0.0),
    "post crank-bore angle": (
        (CRANK_MESH_LEVER + _BAND_END_PAST_MESH) * _POST_ANGLE,
        _PINION_TIP_R_MAX * _POST_ANGLE,
    ),
    # A cone-frame move (a radial, b axial) seen from the crank axis, which
    # the cone axis crosses at the incline.
    **{
        name: (a + b * SIN_I, a * SIN_I + b * COS_I)
        for name, (a, b) in _T120_MOVES.items()
    },
}
T120_POSE_RADIAL = sum(radial for radial, _ in T120_POSE_TERMS.values())
T120_POSE_AXIAL = sum(axial for _, axial in T120_POSE_TERMS.values())

# The same poses move the 64T's tooth row along the crank axis against the
# 16T's teeth (Codex P2 on #1154): the 16T side as T120_POSE_TERMS carries
# it, and the 64T's own rim (its tip at the printed upper limit, its north
# face with the stack at its north float) moved in the cone frame.
_GEAR64_RIM = (_GEAR64_TIP_DIA + _GEAR64_TIP_DIA_TOLERANCE) / 2.0
_GEAR64_OVERHANG = (
    _T120_SOUTH_FACE_STATION
    + max(_GEAR64_FACE_LIMITS)
    + max(_COLLAR_WIDTH_BAND)
    + CONE_FLOAT_NORTH
    - _POST_NORTH_STATION
)
CRANK_ROW_POSE_TERMS = {
    **{
        name: axial
        for name, (_, axial) in T120_POSE_TERMS.items()
        if name not in _T120_MOVES
    },
    **{
        name: a * SIN_I + b * COS_I
        for name, (a, b) in _cone_frame_moves(
            "64T", _GEAR64_OVERHANG, _GEAR64_RIM
        ).items()
    },
}
CRANK_ROW_POSE_AXIAL = sum(CRANK_ROW_POSE_TERMS.values())


# T120 in the cone plane: horizontal p = x - x0 and vertical w = z - z0 from
# the cone axis's station 0 (cone_station runs (sin I, 0, cos I) per station),
# b = y - Y_DRIVE across it.  A point is in T120 when its station
# p sin I + w cos I lies between T120's faces and its offset a = p cos I -
# w sin I from the axis satisfies a^2 + b^2 <= tip^2: a convex solid, as is
# the 16T's reach (a vertical cylinder about the crank axis).  So both checks
# are convex minimisations; each reduces in closed form to one variable, p,
# over the interval of p where the section is not empty, minimised by golden
# section to far below any printed place.  Codex P1 on #1154: a 0.05-deg
# sampling of T120's rim missed the lowest point between its samples by
# 0.005.  Codex P2 on #1154 (review 3): a finite penalty for leaving that
# interval made the objective multimodal, so the interval is found first.
_T120_ORIGIN = cone_station(0.0)
_T120_CRANK_P = X_CRANK - _T120_ORIGIN[0]
_GOLDEN = (math.sqrt(5.0) - 1.0) / 2.0


def _golden_min(f, lo: np.ndarray, hi: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(argument, value) of the least of each convex ``f`` over [``lo``,
    ``hi``], its ends included, element-wise: 60 golden-section steps shrink
    the bracket to 3e-13 of its width."""
    ends = (lo, hi)
    x1, x2 = hi - _GOLDEN * (hi - lo), lo + _GOLDEN * (hi - lo)
    f1, f2 = f(x1), f(x2)
    for _ in range(60):
        left = f1 <= f2
        lo, hi = np.where(left, lo, x1), np.where(left, x2, hi)
        kept_x, kept_f = np.where(left, x1, x2), np.where(left, f1, f2)
        new = np.where(left, hi - _GOLDEN * (hi - lo), lo + _GOLDEN * (hi - lo))
        f_new = f(new)
        x1, f1 = np.where(left, new, kept_x), np.where(left, f_new, kept_f)
        x2, f2 = np.where(left, kept_x, new), np.where(left, kept_f, f_new)
    x, value = np.where(f1 <= f2, x1, x2), np.minimum(f1, f2)
    for end in ends:
        f_end = f(end)
        x, value = np.where(f_end < value, end, x), np.minimum(f_end, value)
    return x, value


def _feasible_edge(g, inside: np.ndarray, outside: np.ndarray) -> np.ndarray:
    """The end of the interval where the convex ``g`` <= 0, between
    ``inside`` (in it) and ``outside``, element-wise and on its feasible side:
    ``outside`` itself when it is in the interval, else 60 bisections."""
    reached = g(outside) <= 0.0
    for _ in range(60):
        middle = (inside + outside) / 2.0
        kept = g(middle) <= 0.0
        inside, outside = (
            np.where(kept, middle, inside),
            np.where(kept, outside, middle),
        )
    return np.where(reached, outside, inside)


def _convex_min_where(f, constraints, lo: np.ndarray, hi: np.ndarray) -> np.ndarray:
    """Least of ``f`` over the p in [``lo``, ``hi``] where every constraint g
    has g(p) <= 0, element-wise; inf where no p qualifies.  Each g is convex
    on the interval the earlier ones leave, so each narrows it to an interval
    (its least point, then both edges), and ``f`` is convex on the last."""
    feasible = np.ones(np.shape(lo), dtype=bool)
    for g in constraints:
        seed, least = _golden_min(g, lo, hi)
        feasible &= least <= 0.0
        lo, hi = _feasible_edge(g, seed, lo), _feasible_edge(g, seed, hi)
    _, value = _golden_min(f, lo, hi)
    return np.where(feasible, value, np.inf)


def _t120_lowest(south: np.ndarray, dy: np.ndarray, reach: float) -> np.ndarray:
    """T120's lowest machine z within ``reach`` of the crank axis, per corner:
    T120's south face at station ``south``, the crank ``dy`` above its model
    height; inf where T120 is out of reach."""
    north = south + CONE_FACE + _T120_NORTH_BAND[0]
    above = Y_CRANK + dy - Y_DRIVE

    # Across the reach at p, the b nearest the cone axis leaves T120 the
    # widest offset q, which lowers its underside and widens its span; |b| is
    # convex in p.  Where |b| <= tip, q is concave, so T120's underside at p
    # (low) is convex, its top (high) concave.
    def across(p: np.ndarray) -> np.ndarray:
        half = np.sqrt(np.maximum(reach**2 - (p - _T120_CRANK_P) ** 2, 0.0))
        return np.clip(0.0, above - half, above + half)

    def span(p: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        q = np.sqrt(np.maximum(_TIP120**2 - across(p) ** 2, 0.0))
        low = np.maximum((south - p * SIN_I) / COS_I, (p * COS_I - q) / SIN_I)
        high = np.minimum((north - p * SIN_I) / COS_I, (p * COS_I + q) / SIN_I)
        return low, high

    def in_tip(p: np.ndarray) -> np.ndarray:
        return np.abs(across(p)) - _TIP120

    def in_faces(p: np.ndarray) -> np.ndarray:
        low, high = span(p)
        return low - high

    centre = np.full_like(south, _T120_CRANK_P)
    w = _convex_min_where(
        lambda p: span(p)[0], (in_tip, in_faces), centre - reach, centre + reach
    )
    return _T120_ORIGIN[2] + w


def _t120_nearest(
    south: np.ndarray, dy: np.ndarray, z_low: float, z_high: float
) -> np.ndarray:
    """T120's least distance from the crank axis between machine z ``z_low``
    and ``z_high``, per corner (``south`` and ``dy`` as _t120_lowest); inf
    where T120 has no point between them."""
    north = south + CONE_FACE + _T120_NORTH_BAND[0]
    above = np.abs(Y_CRANK + dy - Y_DRIVE)
    w_low, w_high = z_low - _T120_ORIGIN[2], z_high - _T120_ORIGIN[2]

    # T120's span in w at p (low convex, high concave), and its offset from
    # the axis nearest zero over that span (convex): T120 reaches |b| up to q
    # there, q concave where a <= tip, so the distance is convex.
    def span(p: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        low = np.maximum(w_low, (south - p * SIN_I) / COS_I)
        high = np.minimum(w_high, (north - p * SIN_I) / COS_I)
        return low, high

    def offset(p: np.ndarray) -> np.ndarray:
        low, high = span(p)
        return np.maximum(
            np.maximum(p * COS_I - high * SIN_I, low * SIN_I - p * COS_I), 0.0
        )

    def in_window(p: np.ndarray) -> np.ndarray:
        low, high = span(p)
        return low - high

    def in_tip(p: np.ndarray) -> np.ndarray:
        return offset(p) - _TIP120

    def distance(p: np.ndarray) -> np.ndarray:
        q = np.sqrt(np.maximum(_TIP120**2 - offset(p) ** 2, 0.0))
        return np.hypot(p - _T120_CRANK_P, np.maximum(above - q, 0.0))

    centre = np.full_like(south, _T120_CRANK_P)
    return _convex_min_where(
        distance, (in_window, in_tip), centre - _T120_REACH, centre + _T120_REACH
    )


def _cone_corners(
    cone_floats: tuple[float, ...], crank_heights: tuple[float, ...]
) -> tuple[np.ndarray, np.ndarray]:
    """(T120's shift north along the cone axis, crank height) per corner: the
    post's cone boss and the collar the 64T stands on, the 64T's face under
    T120, and the stack's float."""
    corners = np.array(
        [
            (b2 + b3 + b4 + f, dy)
            for b2, b3, b4, f, dy in itertools.product(
                _CONE_BOSS_NORTH_BAND,
                _COLLAR_WIDTH_BAND,
                _GEAR64_FACE_LIMITS,
                cone_floats,
                crank_heights,
            )
        ]
    )
    return corners[:, 0], corners[:, 1]


def pinion_t120_clearances(
    *,
    shoulder_length: float | None = PINION_SHOULDER_LENGTH,
    turned_dia: float = PINION_TURNED_DIA,
    face: float = PINION_FACE,
    pose_radial: float = T120_POSE_RADIAL,
    pose_axial: float = T120_POSE_AXIAL,
    end_plays: tuple[float, ...] = PINION_END_PLAY,
    cone_floats: tuple[float, ...] = _CONE_FLOATS,
    crank_heights: tuple[float, ...] = _CRANK_HEIGHT_BAND,
) -> dict[str, float]:
    """Worst 16T-to-T120 clearances over every printed corner.

    ``shoulder air``: T120's lowest point inside the 16T's tip cylinder, above
    the full-OD shoulder at its long limit.  ``turned band radial``: T120's
    nearest point to the crank axis over the turned band's length (shoulder
    to tooth end, each at either limit), outside the turned diameter at its
    upper limit.  ``shoulder_length`` None models teeth at full OD to their
    end (no turned band).  Every T120 point may also close on the 16T by
    ``pose_radial`` toward the crank axis and ``pose_axial`` along it (the
    fit offsets and axis poses, T120_POSE_TERMS).  The crank's end play, the
    stack's float and the crank height range over ``end_plays``,
    ``cone_floats`` and ``crank_heights``.
    """
    # The largest tip and turned radii close on T120 first.
    tip_r = R16 + ADD16 + max(_PINION_TIP_RADIUS_BAND)
    turned_r = turned_dia / 2.0 + _PINION_TURNED_RADIUS_UP
    shoulders, ends = [], []
    for b1, play, d_face in itertools.product(
        _BOSS_NORTH_BAND, end_plays, _PINION_FACE_BAND
    ):
        south = _POST_BOSS_NORTH + b1 + PINION_SEAT_FEELER + play
        end = south + face + d_face
        ends.append(end)
        if shoulder_length is None:
            shoulders.append(end)
        else:
            shoulders.extend(
                min(south + shoulder_length + d_shoulder, end)
                for d_shoulder in _PINION_SHOULDER_BAND
            )
    shift, dy = _cone_corners(cone_floats, crank_heights)
    t120_south = _T120_SOUTH_FACE_STATION + shift
    air = (
        float(_t120_lowest(t120_south, dy, tip_r + pose_radial).min())
        - pose_axial
        - max(shoulders)
    )
    if shoulder_length is None:
        return {"shoulder air": air, "turned band radial": math.inf}
    # The band's axial windows all overlap, so their union is one window.
    nearest = float(
        _t120_nearest(
            t120_south, dy, min(shoulders) - pose_axial, max(ends) + pose_axial
        ).min()
    )
    if nearest >= _T120_REACH:
        raise AssertionError(
            "T120's nearest point to the turned band lies beyond the searched reach"
        )
    return {"shoulder air": air, "turned band radial": nearest - pose_radial - turned_r}


PINION_T120_CLEARANCES = pinion_t120_clearances()
T120_SHOULDER_AIR = PINION_T120_CLEARANCES["shoulder air"]
T120_TURNED_BAND_RADIAL = PINION_T120_CLEARANCES["turned band radial"]
T120_PINION_AIR_FLOOR = 0.25
T120_TURNED_BAND_RADIAL_FLOOR = 0.25
# T120 on its nominal axis, the crank on its: both floors hold.
PINION_T120_CONCENTRIC = pinion_t120_clearances(pose_radial=0.0, pose_axial=0.0)
if PINION_T120_CONCENTRIC["shoulder air"] < T120_PINION_AIR_FLOOR:
    raise AssertionError(
        f"16T full-OD shoulder leaves {PINION_T120_CONCENTRIC['shoulder air']:.3f} mm to "
        f"the inclined T120 on its nominal axis, below the {T120_PINION_AIR_FLOOR:.2f}-mm "
        "axial-air floor"
    )
if PINION_T120_CONCENTRIC["turned band radial"] < T120_TURNED_BAND_RADIAL_FLOOR:
    raise AssertionError(
        f"16T turned band passes {PINION_T120_CONCENTRIC['turned band radial']:.3f} mm "
        "inside the T120 rim on its nominal axis, below the "
        f"{T120_TURNED_BAND_RADIAL_FLOOR:.2f}-mm radial floor"
    )
# This envelope follows the configured cone family. The nominal floors above
# and the fit-up/service and engagement guards below remain independent of
# the worst-clearance facts stated on the manufacturing sheets.

# The fit-up check (dt_crank_pinion_spec.T120_FITUP_ASSEMBLY_CHECK) reads the
# pair with the 16T on its seat feeler (its end play's north end) and the
# stack resting at its model pose, MHA-DT-010 and T120 pushed toward each other.
# Each running play that can still move after the check is taken up by one of
# those pushes: MHA-DT-010 takes up its own bore and MHA-DT-011's journal, T120 the
# cone shaft in the post boss.  The rest of T120_POSE_TERMS are fixed once
# assembled, and the check's full turn sweeps them.  Codex P2 on #1154: a
# check that pushed only MHA-DT-011 passed a Ø16.043 band that then closed to
# 0.018 when the cone shaft moved.
T120_RUNNING_PLAY = {
    "crank journal float": "MHA-DT-010",
    "16T bore on the crankshaft": "MHA-DT-010",
    "cone shaft float in the post boss": "T120",
}


def t120_fitup_reading(
    *, pushed: tuple[str, ...] = PINION_T120_FITUP_PUSHED, **geometry
) -> dict[str, float]:
    """The least the fit-up feeler can read at the check's pose: every fixed
    offset and pose at its worst, the running play of each part in
    ``pushed`` taken up toward T120 and the rest left centred."""
    left = [
        T120_POSE_TERMS[name]
        for name, part in T120_RUNNING_PLAY.items()
        if part not in pushed
    ]
    return pinion_t120_clearances(
        pose_radial=T120_POSE_RADIAL - sum(radial for radial, _ in left),
        pose_axial=T120_POSE_AXIAL - sum(axial for _, axial in left),
        end_plays=(max(PINION_END_PLAY),),
        cone_floats=(0.0,),
        **geometry,
    )


if not set(T120_RUNNING_PLAY.values()) <= set(PINION_T120_FITUP_PUSHED):
    raise AssertionError("the T120 fit-up check leaves running play unpushed")
# So what the check reads is the pair's worst in service: a band or shoulder
# that passes the feeler keeps that clearance however the plays then move.
T120_FITUP_READING = t120_fitup_reading()
for _name, _reading in T120_FITUP_READING.items():
    if _reading > PINION_T120_CLEARANCES[_name] + 1e-9:
        raise AssertionError(
            f"the T120 fit-up check reads {_name} {_reading:.4f}, more than its service "
            f"worst {PINION_T120_CLEARANCES[_name]:.4f}: its pose is not the closing one"
        )
# The fit-up can always close: a band turned down to its fit-up minimum, or a
# shoulder faced back to its short limit, passes the fit-up feeler at every
# corner of the same stack.  The minimum is an actual size, not a toleranced one.
T120_FITUP_LIMIT_CLEARANCES = {
    "turned band radial": t120_fitup_reading(
        turned_dia=PINION_TURNED_DIA_FITUP_MIN - 2.0 * _PINION_TURNED_RADIUS_UP
    )["turned band radial"],
    "shoulder air": t120_fitup_reading(
        shoulder_length=PINION_SHOULDER_LENGTH_FITUP_MIN
    )["shoulder air"],
}
for _name, _clearance in T120_FITUP_LIMIT_CLEARANCES.items():
    if _clearance < PINION_T120_FITUP_FEELER:
        raise AssertionError(
            f"16T {_name} to T120 at its fit-up limit is {_clearance:.3f} mm, under the "
            f"{PINION_T120_FITUP_FEELER:.2f} fit-up feeler"
        )

# ... and a band turned down must still mesh.  Codex P1 on #1154: at Ø15.48
# and the open centre distance the band's contact path is -0.63, no contact.
# Each cut is called for by its own reading alone (t120_fitup_cuts): the band
# is turned down only where the feeler stops between it and the T120 tips,
# and the check reads the pair's worst, so only a crank no higher than
# T120_BAND_CHECK_CRANK_HEIGHT above its model height is ever turned down
# (every other term taken at its closing worst there: a superset).  A
# shoulder faced back leaves the band reading as it was: the band's window
# already starts at the shoulder's short limit, the facing's floor.  A lower
# crank also closes the 16T:64T centres, so the floor need keep contact only
# up to that height, every other open-corner term open (worst to worst only
# on the terms the two checks do not share).  Codex P1 on #1154 (review 3):
# a check that let either failure turn the band down would turn it at crank
# +0.300, where only the shoulder stops the feeler, and lose contact there.


def t120_fitup_cuts(reading: dict[str, float]) -> frozenset[str]:
    """The clearances whose own fit-up cut the check calls for at
    ``reading`` (dt_crank_pinion_spec.T120_FITUP_ASSEMBLY_CHECK): the band is
    turned down only for ``turned band radial``, the shoulder faced back only
    for ``shoulder air``, each where its own reading stops the feeler."""
    return frozenset(
        name for name, value in reading.items() if value < PINION_T120_FITUP_FEELER
    )


# T120's distance from the crank axis never falls as the crank rises, so the
# band-turn heights run from the bottom of the printed band to one height.
if Y_CRANK + min(_CRANK_HEIGHT_BAND) <= Y_DRIVE:
    raise AssertionError("the T120 band reading is not monotonic over the crank height band")




def _band_check_crank_height() -> float:
    """Highest crank height at which the fit-up check can call for the band
    to be turned down: its own reading, the band at its printed upper limit,
    stops the feeler (the reading grows as the crank rises)."""

    def turns_band(height: float) -> bool:
        reading = t120_fitup_reading(crank_heights=(height,))
        return "turned band radial" in t120_fitup_cuts(reading)

    low, high = _CRANK_HEIGHT_BAND
    if turns_band(high):
        return high
    for _ in range(50):
        middle = (low + high) / 2.0
        low, high = (middle, high) if turns_band(middle) else (low, middle)
    return high


T120_BAND_CHECK_CRANK_HEIGHT = _band_check_crank_height()


# Retain this pitch-cylinder frame construction for independent dimensional
# clearances. It is not an actual stock-tooth contact point or row certificate.
def gear64_contact_z(station_shift: float) -> float:
    """Crank-axis z of the 64T pitch-cylinder near-side point in a slice.

    The inclined axis changes the slice's azimuth; this geometric placement
    law says nothing about supported stock-form carrying contact.
    """
    dx = (GEAR64_SEAT[0] + station_shift * SIN_I - X_CRANK) * COS_I
    alpha = math.atan2(_DY16, dx)
    return GEAR64_SEAT[2] + station_shift * COS_I + R64 * math.cos(alpha) * SIN_I


if not math.isclose(gear64_contact_z(0.0), _GEAR64_CONTACT_Z, abs_tol=1e-9):
    raise AssertionError("gear64_contact_z disagrees with the seated pitch-cylinder azimuth")

# Face overlap of the 16T on the 64T tooth row along the crank axis: the worst
# share of the row the 16T face covers, over every printed axial band, the
# pinion end play, the cone stack's north float and the axis poses (summed
# arithmetically). The contact quality inside the overlap is the standard
# mesh check above; the native interference gate checks the real flanks.
CRANK_ROW_ENGAGEMENT_FLOOR = 0.85


def crank_row_engagement(cone_float: float, pose_axial: float = CRANK_ROW_POSE_AXIAL) -> float:
    worst = math.inf
    for b1, b2, b3, b4, d_length, play, f, shift in itertools.product(
        _BOSS_NORTH_BAND,
        _CONE_BOSS_NORTH_BAND,
        _COLLAR_WIDTH_BAND,
        _GEAR64_FACE_LIMITS,
        _PINION_FACE_BAND,
        PINION_END_PLAY,
        (0.0, cone_float),
        (-pose_axial, pose_axial),
    ):
        south = _POST_BOSS_NORTH + b1 + PINION_SEAT_FEELER + play
        north = south + PINION_FACE + d_length
        row_south = gear64_contact_z(-GEAR64_FACE / 2.0 + b2 + b3 + f) + shift
        row_north = gear64_contact_z(GEAR64_FACE / 2.0 + b2 + b3 + b4 + f) + shift
        overlap = min(north, row_north) - max(south, row_south)
        worst = min(worst, max(0.0, overlap) / (row_north - row_south))
    return worst


CRANK_ROW_ENGAGEMENT_FRACTION_WORST = crank_row_engagement(CONE_FLOAT_NORTH)
if CRANK_ROW_ENGAGEMENT_FRACTION_WORST < CRANK_ROW_ENGAGEMENT_FLOOR:
    raise AssertionError(
        f"16T covers {CRANK_ROW_ENGAGEMENT_FRACTION_WORST:.1%} of the 64T tooth row at worst, "
        f"below {CRANK_ROW_ENGAGEMENT_FLOOR:.0%}"
    )
# The base's pivot-screw hole sits exactly under the swing pivot -- both are
# authored in the machine frame, so the coordinates agree directly (pre-#151
# this module derived in the mirrored frame and the hole's x was the NEGATED
# pivot x).  Both now read cone_line, so the check is exact, not a fit
# window: it catches the base seat being sourced from anywhere else.
if (
    abs(BASE_PIVOT_XZ[0] - _PPIVOT[0]) > 1e-9
    or abs(BASE_PIVOT_XZ[1] - _PPIVOT[2]) > 1e-9
):
    raise AssertionError(
        f"harmonic-base pivot-screw hole {BASE_PIVOT_XZ} != machine swing pivot "
        f"({_PPIVOT[0]!r}, {_PPIVOT[2]!r})"
    )
# The plate's reamed pivot bore runs on the stock shoulder as an H/h location
# fit: least clearance zero at both maximum-material limits (bore at its
# minimum, shoulder at its maximum), never negative (cone_set_stack).
if (
    PLAT_PIVOT_HOLE_DIA + PLAT_PIVOT_HOLE_BAND[1]
    < PSCREW_SHOULDER_DIA + PSCREW_SHOULDER_DIA_BAND[0] - 1e-9
):
    raise AssertionError("platform pivot bore does not clear the screw shoulder")
if abs(PSCREW_SHOULDER_LEN - PLAT_PIVOT_BEARING_T - 0.25) > 1e-9:
    raise AssertionError("pivot screw no longer provides 0.25 axial plate clearance")
if (
    PLAT_PIVOT_RELIEF_DIA - PSCREW_HEAD_DIA
) / 2.0 + 1e-9 < PLAT_PIVOT_HEAD_RADIAL_CLEARANCE:
    raise AssertionError("platform pivot relief lacks required radial head clearance")
_require_tapped_thread(
    "cone pivot", PSCREW_THREAD, BASE_PIVOT_SEAT_SPEC, kind="tapped_bottoming"
)
require_base_seat_fit("cone pivot", BASE_PIVOT_SEAT_SPEC, PSCREW_THREAD_TAIL_LEN)
# --- tip-block print-worst stacks (user ruling 2026-09-29) -------------------
# With no shim, no flange slot and no platform slot, the block's station comes
# from the hold-down (TIP_NORTH_FACE_BAND_MM / TIP_TAP_LATERAL_BAND_MM above)
# and the shaft tip's from the pivot post, both off the same plate.  The cup
# adjuster sets the shaft's end play at assembly; every other stack closes at
# the printed limits.
#
# The post rides its two MHA-VN-031 screws in drilled clearance holes, on the
# plate's post-mount taps (explicit +/-0.10 stations).  Its journal runs at the
# incline to its mount-hole line, so the mount holes' .XX stations move it
# along the cone axis by sin(I); the shaft collar bears on the boss's north
# face, half the ConeBossLen band off the post centre.
_SIN_INCLINE = math.sin(math.radians(INCLINE_DEG))
_COS_INCLINE = math.cos(math.radians(INCLINE_DEG))
POST_SCREW_FLOAT_MM = (
    POST_ATTACHMENT_THRU_DIA + _DRILLED_HOLE_PLUS_MM - POST_MOUNT_THREAD_DIA
) / 2.0
_POST_MOUNT_X_BAND = tip_printed_band_mm(POST_DRAWING_PRECISION["MountWestX"])
POST_BOSS_FACE_AXIAL_BAND_MM = (
    PLAT_POST_MOUNT_STATION_TOL_MM
    + POST_SCREW_FLOAT_MM
    + _POST_MOUNT_X_BAND * _SIN_INCLINE
    + tip_printed_band_mm(POST_DRAWING_PRECISION["ConeBossLen"]) / 2.0
)
# Pivot-screw head vs the block's plain north face: the head stands on its
# shoulder at PIVOT_STATION and floats in the plate's reamed pivot bore by
# the fit's largest radial play; the north face moves by the hold-down band.
# Nothing of the shaft enters, since the block does not follow the tip.
PIVOT_HEAD_AIR = 0.20
PIVOT_HEAD_NOMINAL_GAP = (
    PIVOT_STATION - (TIP_BLOCK_STATION + TIP_BLOCK_Z / 2.0)
) - PSCREW_HEAD_DIA / 2.0
PIVOT_HEAD_FLOAT = (
    PLAT_PIVOT_HOLE_DIA + PLAT_PIVOT_HOLE_BAND[0]
    - (PSCREW_SHOULDER_DIA + PSCREW_SHOULDER_DIA_BAND[1])
) / 2.0


def tip_pivot_head_worst_gap_mm(north_face_band_mm: float) -> float:
    """Least air between the pivot-screw head and the block's north face when
    the face stands north_face_band_mm off its nominal station; raise under
    PIVOT_HEAD_AIR."""
    gap = PIVOT_HEAD_NOMINAL_GAP - PIVOT_HEAD_FLOAT - north_face_band_mm
    if gap < PIVOT_HEAD_AIR - 1e-9:
        raise AssertionError(
            f"pivot-screw head can come within {gap:.3f} of the tip block's north "
            f"face at the printed limits (< {PIVOT_HEAD_AIR})"
        )
    return gap


PIVOT_HEAD_WORST_GAP = tip_pivot_head_worst_gap_mm(TIP_NORTH_FACE_BAND_MM)
# Adjuster engagement: the cup seats on the tip, so the engagement moves by the
# tip's station (post band + Sec4End, collar face to tip) against the north
# face's, and the set end play (cone_stack_end_play.SHAFT_END_PLAY) backs the
# cup off the tip by up to its upper limit.  The block's working window (the
# 1.0D engagement exception at the shallow end, full thread under the rim at
# the deep end) must hold both extremes.
TIP_EMBED_BAND_MM = (
    shaft_printed_band("Sec4End")
    + POST_BOSS_FACE_AXIAL_BAND_MM
    + TIP_NORTH_FACE_BAND_MM
)


def tip_embed_worst_mm(band_mm: float) -> tuple[float, float]:
    """The adjuster's thread engagement at both extremes of band_mm and the
    set end play; raise if either leaves the block's working window."""
    worst = (
        ADJ_THREAD_ENGAGEMENT - band_mm - SHAFT_END_PLAY[1],
        ADJ_THREAD_ENGAGEMENT + band_mm - SHAFT_END_PLAY[0],
    )
    if not (TIP_ADJ_EMBED_WINDOW[0] <= worst[0] and worst[1] <= TIP_ADJ_EMBED_WINDOW[1]):
        raise AssertionError(
            f"adjuster embed {worst[0]:.3f}..{worst[1]:.3f} leaves its working "
            f"window {TIP_ADJ_EMBED_WINDOW[0]:.3f}..{TIP_ADJ_EMBED_WINDOW[1]:.3f} "
            f"at the printed limits"
        )
    return worst


TIP_EMBED_WORST_MM = tip_embed_worst_mm(TIP_EMBED_BAND_MM)
# Collar air: the MHA-VN-016 stack collar is set one COLLAR_FEELER off T006's
# north face at assembly, so its north face is T006's station (post band, the
# shaft collar web, the gear stack's face band, the set end play) plus the
# feeler's reading band and the machined collar's width band. The block's south
# face is the hold-down's north face less the printed depth.  The collar is a
# locked spacer, not a thrust face: it must never touch the block.
TIP_COLLAR_NOMINAL_AIR = (TIP_BLOCK_STATION - TIP_BLOCK_Z / 2.0) - (
    COLLAR_STATION + COLLAR_WIDTH
)
TIP_COLLAR_AIR_BAND_MM = (
    POST_BOSS_FACE_AXIAL_BAND_MM
    + shaft_printed_band("CollarWidth")
    + dt_cone_gear_stack.face_band(dt_cone_gear_stack.COUNT - 1, "north")[0]
    + SHAFT_END_PLAY[1]
    + COLLAR_FEELER_BAND
    + COLLAR_WIDTH_BAND_MM
    + TIP_NORTH_FACE_BAND_MM
    + tip_printed_band_mm(TIP_DRAWING_PRECISION["Depth"])
)


def tip_collar_worst_air_mm(band_mm: float) -> float:
    """Least axial air left between the stack collar and the block's south
    face at band_mm; raise if the collar can touch the block."""
    air = TIP_COLLAR_NOMINAL_AIR - band_mm
    if air < 0.0:
        raise AssertionError(
            f"MHA-VN-016 stack collar can reach the tip block at the printed limits "
            f"(air {air:.3f})"
        )
    return air


TIP_COLLAR_WORST_AIR = tip_collar_worst_air_mm(TIP_COLLAR_AIR_BAND_MM)
# Lateral: the adjuster axis (hold-down + PassageCenter, off the plate
# centreline) against the line the journal points the shaft along.  The
# journal's plan angle to the post's mount holes is BASIC with no frame
# locating it, so it takes the title block's angular band over the post-to-
# tip run; the post's mount holes add their stations (the platform's +/-0.10
# pair turns the post, the post's own .XX pair shifts it).  At assembly the
# post turns on its screws' clearance until the tip sits in the cup: that
# capacity must cover the whole error.
_POST_TO_TIP = TIP_BLOCK_STATION - POST_STATION
_ANGULAR_DEG = float(_config.title_block("angular")["value_deg"])
TIP_LATERAL_ERROR_MM = (
    PLAT_POST_MOUNT_STATION_TOL_MM
    + _POST_TO_TIP
    * (PLAT_POST_MOUNT_STATION_TOL_MM * (_SIN_INCLINE + _COS_INCLINE))
    / POST_ATTACHMENT_X
    + _POST_MOUNT_X_BAND * _COS_INCLINE
    + _POST_TO_TIP * math.tan(math.radians(_ANGULAR_DEG))
    + TIP_TAP_LATERAL_BAND_MM
    + tip_printed_band_mm(TIP_PASSAGE_CENTER_PLACES)
)
TIP_LATERAL_CAPACITY_MM = _POST_TO_TIP * POST_SCREW_FLOAT_MM / POST_ATTACHMENT_X


def require_tip_lateral_take_up(error_mm: float, capacity_mm: float) -> None:
    """Turning the post on its screws must take up the whole lateral error."""
    if error_mm > capacity_mm:
        raise AssertionError(
            f"tip lateral error {error_mm:.3f} exceeds what turning the post on "
            f"its screws takes up ({capacity_mm:.3f})"
        )


require_tip_lateral_take_up(TIP_LATERAL_ERROR_MM, TIP_LATERAL_CAPACITY_MM)
# Vertical: both riders stand on the same plate top (it cancels); the post's
# journal height band and the block's AxisHeight band must keep the stub
# inside the cup's mouth.
TIP_VERTICAL_ERROR_MM = POST_JOURNAL_AXIS_HEIGHT_TOLERANCE_MM + TIP_AXIS_HEIGHT_TOL_MM
TIP_CUP_CAPTURE_MM = (ADJ_CUP_DIA - SHAFT_SECTIONS[-1][0] * 25.4) / 2.0
if TIP_VERTICAL_ERROR_MM > TIP_CUP_CAPTURE_MM:
    raise AssertionError(
        f"tip axis-height error {TIP_VERTICAL_ERROR_MM:.3f} exceeds the adjuster "
        f"cup's capture {TIP_CUP_CAPTURE_MM:.3f}"
    )



# --- cone lock knob and swing stop -------------------------------------------
# Both fasteners are static to the base. build_dt_cone_swing_platform owns the
# single outline/contact calculation; build_fr_harmonic_base supplies the
# installed pivot and exports the resulting lock/stop stations for this
# assembly and its native Hole Wizard seats.
def _plate_local_to_machine(x_l: float, z_l: float) -> tuple[float, float]:
    """Plan point of the engaged plate's local (x, z) in machine coordinates."""
    return (
        _PPIVOT[0] + x_l * COS_I + z_l * SIN_I,
        _PPIVOT[2] - x_l * SIN_I + z_l * COS_I,
    )


KNOB_X, KNOB_Z = BASE_LOCK_XZ
_require_tapped_thread("cone lock knob", KNOB_THREAD, BASE_LOCK_SEAT_SPEC)
if PLAT_SLOT_W - KNOB_STUD_DIA < 0.5:
    raise AssertionError("lock stud has <0.5 clearance in the platform notch")
if abs(BASE_LOCK_ENGAGEMENT - (KNOB_STUD_LEN - PLAT_T)) > 1e-9:
    raise AssertionError("base lock engagement does not use the stock stud excess")
require_lock_seat_fit(BASE_LOCK_SEAT_SPEC, PLAT_T, KNOB_STUD_LEN)

# Keep the stock knurled head's base seat outside a conservative plan-envelope
# of every adjacent gear; the real solids must therefore have clearance at
# every tooth phase.
_KNOB_GEAR_CLEARANCE = 0.25
_KNOB_R = KNOB_HEAD_DIA / 2.0
_GEAR64_TIP_R = _GEAR64_TIP_DIA / 2.0
if (
    math.hypot(KNOB_X - GEAR64_SEAT[0], KNOB_Z - GEAR64_SEAT[2])
    - _KNOB_R
    - _GEAR64_TIP_R
    < _KNOB_GEAR_CLEARANCE
):
    raise AssertionError("cone-lock knob head crowds the 64T crank-drive gear")
for _j in range(20):
    _cone_tip_r = _cone_tip_radius_max(120 - 6 * _j)
    _cone_x, _cone_z = cone_seat(_j)
    if (
        math.hypot(KNOB_X - _cone_x, KNOB_Z - _cone_z) - _KNOB_R - _cone_tip_r
        < _KNOB_GEAR_CLEARANCE
    ):
        raise AssertionError(f"cone-lock knob head crowds cone gear {_j + 1}")

# The plate's crank-axis datum remains on the fixed crank axis.
_SEAT_ANCHOR_M = _plate_local_to_machine(PLAT_SEAT_ANCHOR[0], PLAT_SEAT_ANCHOR[1])
if abs(_SEAT_ANCHOR_M[0] - X_CRANK) > 1e-6:
    raise AssertionError(
        f"platform CRANK_SEAT_ANCHOR maps to machine x {_SEAT_ANCHOR_M[0]:.6f}"
        f" != X_CRANK {X_CRANK:.6f} -- anchor sign convention broke"
    )

# The collarless knurled head controls both notch-exit travel and external
# clearance. The stock stop (the foot screw's #4-40 SKU) seats its head on the
# base top; vn_swing_stop_screw_spec owns the embed/proud split.
DISENGAGE_DEG = BASE_SWING_HARDWARE.disengage_deg
# Keep nominal mates/stop locations distinct from the conditional, fully
# seated manufacturing-corner sweep used by clearance consumers.
P1_STOP_ENCLOSURE = manufactured_p1_stop_enclosure()
P1_SWEEP_DEG = P1_STOP_ENCLOSURE["angle_interval_deg"]
STOP_X, STOP_Z = BASE_SWING_HARDWARE.stop_xz
_STOP_CONTACT = BASE_SWING_HARDWARE.stop_contact_xz
_STOP_ENGAGED_GAP = BASE_SWING_HARDWARE.stop_engaged_gap
if math.dist((STOP_X, STOP_Z), BASE_STOP_XZ) > 1e-9:
    raise AssertionError("shared swing-stop station drifted from the base seat")
_require_tapped_thread("swing stop", STOP_THREAD, BASE_STOP_SEAT_SPEC)
if abs(STOP_PROUD_LEN - (STOP_SHANK_LEN - STOP_EMBED_LEN)) > 1e-9:
    raise AssertionError("swing-stop proud length is not stock length minus embed")
require_stop_seat_fit(BASE_STOP_SEAT_SPEC, PLAT_T)
if _STOP_ENGAGED_GAP < 2.0:
    raise AssertionError(
        f"stop screw within {_STOP_ENGAGED_GAP:.2f} of the engaged plate edge "
        f"(needs >= 2.0)"
    )
if (
    math.hypot(STOP_X - KNOB_X, STOP_Z - KNOB_Z)
    < (KNOB_HEAD_DIA + STOP_HEAD_DIA) / 2.0 + 0.25
):
    raise AssertionError("swing-stop head envelope fouls the lock-knob head")
_POST_LOCAL_Z = POST_STATION - PIVOT_STATION
_KNOB_HEAD_POST_GAP = (
    math.hypot(PLAT_SLOT_E_X, PLAT_SLOT_E_Z - _POST_LOCAL_Z)
    - KNOB_HEAD_DIA / 2.0
    - POST_BLOCK_DIA / 2.0
)
if _KNOB_HEAD_POST_GAP < PLAT_LOCK_HEAD_POST_CLEARANCE - 1e-9:
    raise AssertionError(
        f"lock-knob head within {_KNOB_HEAD_POST_GAP:.2f} of the pivot-post "
        f"foot (needs >= {PLAT_LOCK_HEAD_POST_CLEARANCE:.2f})"
    )
# Plate WEST edge (the flare) vs BOTH arbor-pedestal blocks.  The edge and its
# engaged placement are linear, so solve the exact local interval crossing
# each pedestal z band; a coarse sample previously stepped over the 0.93 mm
# north-pedestal overlap that the SolidWorks interference gate found.
_K_W = (PLAT_WEST_S - PLAT_WEST_N) / PLAT_LEN
_ARB_E_X = X_DRUM - ARBOR_PED_WIDTH / 2.0  # plate-facing pedestal flank
_ARB_Z_BANDS = (
    # (band, min gap): the SOUTH pedestal keeps the 2.0 design margin.  The
    # NORTH one runs at the repository's 0.25 mm interference-design floor;
    # ch12 img09 shows the real clamp hugging the plate edge, and the p1 swing
    # moves the plate away from it.
    (ARBOR_PED_SOUTH_Z_BAND, 2.0),
    (ARBOR_PED_NORTH_Z_BAND, 0.25),
)
_EDGE_X_INTERCEPT = PLAT_WEST_N + _K_W * PLAT_OVERHANG
_EDGE_LOCAL_Z_MIN = PLAT_OVERHANG - PLAT_LEN
_EDGE_LOCAL_Z_MAX = PLAT_OVERHANG
_ARB_BAND_NAMES = ("south arbor pedestal", "north arbor pedestal")


def west_edge_arbor_gaps(swing_deg: float) -> tuple[float, ...]:
    """Plan x-gap from the plate's straight WEST edge to each arbor-pedestal
    block's plate-facing flank, with the plate swung ``swing_deg`` past the
    engaged incline (the p1 disengage turns it about the pivot).  The edge
    and its placement are linear, so the exact local interval crossing each
    block's z band is solved (a coarse sample once stepped over a 0.93 mm
    overlap the SolidWorks interference gate found).  A band the edge does
    not cross reads +inf."""
    angle = math.radians(INCLINE_DEG + swing_deg)
    c, s = math.cos(angle), math.sin(angle)
    world_z_base = _PPIVOT[2] - _EDGE_X_INTERCEPT * s
    world_z_slope = c + _K_W * s
    world_x_base = _PPIVOT[0] + _EDGE_X_INTERCEPT * c
    world_x_slope = s - _K_W * c
    gaps = []
    for arb_z, _min_gap in _ARB_Z_BANDS:
        zl0 = max(_EDGE_LOCAL_Z_MIN, (arb_z[0] - world_z_base) / world_z_slope)
        zl1 = min(_EDGE_LOCAL_Z_MAX, (arb_z[1] - world_z_base) / world_z_slope)
        if zl1 < zl0:
            gaps.append(math.inf)
            continue
        closest_x = max(
            world_x_base + world_x_slope * zl0, world_x_base + world_x_slope * zl1
        )
        gaps.append(_ARB_E_X - closest_x)
    return tuple(gaps)


def plate_vertices_machine(swing_deg: float) -> tuple[tuple[float, float], ...]:
    """The plate's four sharp plan vertices in machine (x, z), swung
    ``swing_deg`` past the engaged incline about the pivot."""
    angle = math.radians(INCLINE_DEG + swing_deg)
    c, s = math.cos(angle), math.sin(angle)
    return tuple(
        (_PPIVOT[0] + x * c + z * s, _PPIVOT[2] - x * s + z * c)
        for x, z in _PLATFORM_VERTICES
    )


Plan = tuple[float, float]


def _edges(poly: tuple[Plan, ...]) -> list[tuple[Plan, Plan]]:
    return list(zip(poly, poly[1:] + poly[:1]))


def _point_segment_gap(p: Plan, a: Plan, b: Plan) -> float:
    dx, dz = b[0] - a[0], b[1] - a[1]
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dz) / (dx * dx + dz * dz)))
    return math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dz))


def _segments_cross(p1: Plan, p2: Plan, q1: Plan, q2: Plan) -> bool:
    def side(a: Plan, b: Plan, c: Plan) -> float:
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    return (side(q1, q2, p1) > 0) != (side(q1, q2, p2) > 0) and (
        side(p1, p2, q1) > 0
    ) != (side(p1, p2, q2) > 0)


def _point_in_polygon(point: Plan, poly: tuple[Plan, ...]) -> bool:
    px, pz = point
    inside = False
    for (ax, az), (bx, bz) in _edges(poly):
        if (az > pz) != (bz > pz) and px < ax + (pz - az) * (bx - ax) / (bz - az):
            inside = not inside
    return inside


def _plan_gap_polygons(a: tuple[Plan, ...], b: tuple[Plan, ...]) -> float:
    """Plan distance between two polygon outlines; negative when they
    overlap (crossing edges, or one inside the other)."""
    nearest = math.inf
    for p1, p2 in _edges(a):
        for q1, q2 in _edges(b):
            if _segments_cross(p1, p2, q1, q2):
                nearest = 0.0
                continue
            nearest = min(
                nearest,
                _point_segment_gap(p1, q1, q2),
                _point_segment_gap(p2, q1, q2),
                _point_segment_gap(q1, p1, p2),
                _point_segment_gap(q2, p1, p2),
            )
    overlap = nearest == 0.0 or _point_in_polygon(a[0], b) or _point_in_polygon(b[0], a)
    return -nearest if overlap else nearest


def _plan_gap_to_plate(point: Plan, swing_deg: float) -> float:
    """Plan distance from a point to the swung plate outline; negative when
    the point lies under the plate."""
    poly = plate_vertices_machine(swing_deg)
    nearest = min(_point_segment_gap(point, a, b) for a, b in _edges(poly))
    return -nearest if _point_in_polygon(point, poly) else nearest


# I31 (Main, 2026-09-25): sweep the plate's north-west edge over the whole
# seated manufacturing enclosure, not just the nominal DISENGAGE_DEG:
# - the straight west edge against both arbor-pedestal blocks (their floors
#   above: 2.0 south, 0.25 north);
# - every sharp plate vertex inside the base deck, within the green lip;
# - every other base-fixed occupant clear of the plate outline: see
#   SWING_OCCUPANT_CLEARANCE, after the rig and spring layout it reads.
SWING_SAMPLES = 400
SWING_ANGLES = tuple(P1_SWEEP_DEG[1] * k / SWING_SAMPLES for k in range(SWING_SAMPLES + 1))
SWING_SWEEP: dict[str, float] = {}
for _k, _swing in enumerate(SWING_ANGLES):
    for (_arb_z, _floor), _name, _gap in zip(
        _ARB_Z_BANDS, _ARB_BAND_NAMES, west_edge_arbor_gaps(_swing), strict=True
    ):
        SWING_SWEEP[_name] = min(SWING_SWEEP.get(_name, math.inf), _gap)
        if _gap < _floor:
            raise AssertionError(
                f"swing-plate west edge within {_gap:.3f} mm of the {_name} "
                f"block at swing {_swing:.3f} deg (needs >= {_floor})"
            )
    for _label, (_vx, _vz) in zip(
        ("NE", "NW", "SW", "SE"), plate_vertices_machine(_swing), strict=True
    ):
        _margin = min(
            _BASE_X_LIMIT - BASE_LIP_W - abs(_vx), _BASE_Z_LIMIT - BASE_LIP_W - abs(_vz)
        )
        _key = f"{_label} corner inside the lip"
        SWING_SWEEP[_key] = min(SWING_SWEEP.get(_key, math.inf), _margin)
        if _margin < 0.0:
            raise AssertionError(
                f"swing-plate {_label} corner crosses the base lip by {-_margin:.3f} "
                f"at swing {_swing:.3f} deg"
            )
# --- alignment pinion (ch. 25): RESTORED 2026-07-02, carried DISENGAGED ------
# The 32T drum shares the train's configured pitch and pressure angle.
# Its standard 1.25m roots leave the 120T tips clear: the engaged stop is
# the pitch-circle sum plus the configured positive running extension, not
# a tip seated on a shallow base-chord floor. The parked placement -- drum,
# strap pivot, lean, lift axis and follower-pin line -- remains the pure
# pinion_rig_park_geometry, which the A03 fit-up text reads too (#880).
from pinion_rig_park_geometry import (  # noqa: E402
    APINION_GAP,  # noqa: F401 -- the placement's input, read as drive.APINION_GAP
    APINION_X,
    APINION_Y,
    ENGAGED_SWING_RAD as _PHI_ENG,
    FPIN_C as _FPIN_C,
    LIFT_X,
    LIFT_Y,
    PIVOT_X,
    PIVOT_Y,
    SPR_N as _SPR_N,
    SPR_U as _SPR_U,
    STRAP_LEAN_DEG,
    TIP_APINION,
    TIP_DRUM120,
)
from pinion_rig_park_geometry import pin_line_dist as _pin_line_dist  # noqa: E402

import dt_alignment_pinion_spec as _ALIGNMENT_PINION  # noqa: E402

ENGAGED_C2C = _ALIGNMENT_PINION.ENGAGED_CENTER_DISTANCE_MM
_CONFIG_ENGAGED_C2C = float(
    _config.machine("alignment_pinion", "engaged_center_distance_mm")
)
if abs(ENGAGED_C2C - _CONFIG_ENGAGED_C2C) > 1e-6:
    raise AssertionError(
        "alignment-pinion configured and derived engaged centre distances disagree: "
        f"{_CONFIG_ENGAGED_C2C:.6f} vs {ENGAGED_C2C:.6f} mm"
    )
# Ruling (c) (user, 2026-09-24): the blocks locate the swing cluster -- every
# rig z station is pinion_rig_layout's fit-up stack (the cluster hard on the
# back block, the drum hard on the back strap and one shim off the front one:
# MHA-DT-000's SHAFT DRILL SET), shared with the base's transferred seats.
APINION_DRUM_LEN = RIG.DRUM_LEN  # build_dt_alignment_pinion FACE_WIDTH
APINION_Z_FRONT = RIG.DRUM_FRONT_Z
APINION_Z_BACK = RIG.DRUM_BACK_Z
# PIVOT_X/Y, STRAP_LEAN_DEG and LIFT_X/Y are pinion_rig_park_geometry's.  The
# lift rod sits in the blocks' WEST bores: it moved there from the
# east since the DP40 cram (issue #7 dodged the cone-pivot-post column);
# the p.68-69 photos put the lever WEST of the grip head and the cam pins lift
# the strap tails' follower pins from the WEST -- an east lift would
# swing the drum OUT of mesh. The column (x ~-47) is far east of the new spot,
# and the M6.9 portal south upright that once blocked the west band was
# replaced by the lone NORTH rocker-arm-support. The recentered p2 rig clears
# the unmodified casting; the complete-machine interference gate proves that
# cross-subassembly relationship from the built solids.  The v2 closure: the
# steep strap carries its follower contact above the pivot at the WEST cam
# station.  The eccentric cam collars still meet the pins from below; the pins
# rest on the collar ODs.
PIVOT_SHAFT_Z0 = RIG.TORQUE_SHAFT_Z0
# Ø6.35 torque shaft, set back-flush; its front end stands the worst-stack
# allowance proud of the front block (pinion_rig_layout).
LIFT_ROD_Z0 = RIG.LIFT_ROD_Z0
# front end LEVER_SEAT_PROUD (15.60) south of the front block -- the lever
# hub's seat, sized so the hub never stops the rod (pinion_rig_layout)
BLOCK_X = PIVOT_X  # block local origin ON the pivot bore (datum B, U28)
BLOCK_FRONT_Z0 = RIG.FRONT_BLOCK_Z0  # one 0.25 feeler off the front strap
BLOCK_BACK_Z0 = RIG.BACK_BLOCK_Z0  # the (c) back stop, the rig's reference
# U28 thinned the blocks (12 -> 10.25); ruling (c) then put the back strap hard
# on the back block, and pinion_rig_layout sizes the shaft and rod from the
# worst fitted stack (Codex #837).  Option E-a deepened them outward, to 10.5
# and then 11.0, so the strap-pinned shaft bears the back block with 0.5 to
# spare over its floor (Codex #858, Main).
LEVER_TILT_DEG = 10.0  # parked, from vertical toward machine -X
# ch25 p.68 page002_img08 is explicitly the FRONT side and shows the
# disengaged lever only about 10 degrees from vertical, with its tip to image
# right = machine -X.  The engaged page002_img07 folds the same lever toward
# machine +X.  This sign also matches rot_z_rows: local +Y maps to
# (-sin(theta), cos(theta)), so positive theta tips toward -X.  The prior
# -40-degree seed put the parked lever on the photographed engaged side.
# The arbor-clearance gate below proves the photo-derived +10-degree rest
# pose, and the cam-contact solve proves its full swing to about -72 degrees.
LEVER_LEN = LEVER_ROD_LEN  # 86: hub centre -> tip (img07 @9.37 px/mm,
# PR7 -- the PR6 98 was img08's perspective-inflated read)
LEVER_Z = LIFT_ROD_Z0 + LEVER_HUB_LEN / 2.0 - LEVER_WALL_T
# seats on the translated lift-rod front end; north face stays 2 off the block.
HANDLE_TILT_DEG = 65.0  # grip crossrod from vertical
# The drum is bonded on MHA-DT-022 at the printed DRUM_STATION from the head
# shoulder, so the arbor rides wherever the fit-up stack puts the drum.
ARBOR_Z0 = APINION_Z_FRONT - ARBOR_DRUM_STATION - ARBOR_HEAD_REAR_Z
# Preserve the released MHA-DT-015 component origin at the head/cross-hole axis.
# The head is now integral with MHA-DT-022, whose local head centre is z=-6.5.
HANDLE_Z = ARBOR_Z0 + ARBOR_HEAD_CENTER_Z
_HANDLE_C = math.cos(math.radians(HANDLE_TILT_DEG))
_HANDLE_S = math.sin(math.radians(HANDLE_TILT_DEG))
HANDLE_ROWS = [
    [_HANDLE_C, _HANDLE_S, 0.0],
    [-_HANDLE_S, _HANDLE_C, 0.0],
    [0.0, 0.0, 1.0],
]
# MHA-DT-022's grip bore and MHA-DT-015's rod both run along local +Y.  They share
# one Rz pose; the circular arbor shaft stays on the same machine-Z journal
# axis while its cross-hole clocks onto the rod.
ARBOR_ROWS = HANDLE_ROWS
# R1a (user, 2026-09-24): the MHA-DT-033 collar is spring-pinned to MHA-DT-022 at its
# printed pin station.  Both pin holes run along their parts' local +Y, so the
# collar shares the arbor's pose and its centred hole lands on the arbor's.
ARBOR_COLLAR_Z0 = ARBOR_Z0 + ARBOR_PIN_Z - ARBOR_COLLAR_PIN_Z
ARBOR_COLLAR_Z = (ARBOR_COLLAR_Z0, ARBOR_COLLAR_Z0 + ARBOR_COLLAR_LEN)

if abs(math.hypot(PIVOT_X - APINION_X, APINION_Y - PIVOT_Y) - STRAP_C2C) > 0.001:
    raise AssertionError("strap c2c does not span pivot -> pinion axis")
if Z_DRUM0 - DRUM_FACE / 2.0 < APINION_Z_FRONT + 1.0:
    raise AssertionError("alignment pinion too short at the front station")
if Z_DRUM0 + 19 * Z_PITCH + DRUM_FACE / 2.0 > APINION_Z_BACK + 0.5:
    raise AssertionError("alignment pinion misses the j = 19 station")
# Worst stack at both ends (user ruling P1-2): the rig is set with the drum's
# back end RIG_SET_LEAF_D off g19's back face, so from the pose it advances
# by DRUM_BACK_ADVANCE_STACK and must still cover all of g19's face (so j = 19
# engages >= 2.0 a fortiori); its front end retreats by DRUM_FRONT_RETREAT_STACK
# and must stay 1.0 south of g0's front face.  Both spares join RIG_MARGINS
# (below), and one leaf step thinner would leave j = 19 short of
# RIG_MARGIN_SPARE (D is the thinnest setting that holds).  D is set with the
# bank pushed north, so the bank adds nothing to j = 19; at the front g0
# itself walks south by the bank's end play and a long g0 -> g19 pitch stack
# (RIG.G0_FRONT_SOUTH_STACK, #743), so the j = 0 row carries those beside the
# drum's own retreat (Codex #858, PRRT_kwDOPHDy386mUjhU).
_G19_FACE_Z = (
    Z_DRUM0 + 19 * Z_PITCH - DRUM_FACE / 2.0,
    Z_DRUM0 + 19 * Z_PITCH + DRUM_FACE / 2.0,
)
APINION_BACK_WORST_Z = APINION_Z_BACK - sum(RIG.DRUM_BACK_ADVANCE_STACK.values())
J19_ENGAGEMENT_WORST = min(APINION_BACK_WORST_Z, _G19_FACE_Z[1]) - _G19_FACE_Z[0]
if J19_ENGAGEMENT_WORST < 2.0:
    raise AssertionError(f"j = 19 engages only {J19_ENGAGEMENT_WORST:.3f} at the worst stack")
J19_FULL_FACE_MARGIN = APINION_BACK_WORST_Z - _G19_FACE_Z[1]
if J19_FULL_FACE_MARGIN < -1e-9:
    raise AssertionError(
        f"j = 19 loses {-J19_FULL_FACE_MARGIN:.3f} of its full face at the worst stack"
    )
if J19_FULL_FACE_MARGIN - RIG.FEELER_LEAF_STEP >= RIG.RIG_MARGIN_SPARE - 1e-9:
    raise AssertionError("RIG_SET_LEAF_D is more than the thinnest setting for j = 19")
# The rig reads the bank's configured-grid datum; the independently placed
# gear and drum must still put the drum's back end exactly D off that face.
if abs(_G19_FACE_Z[1] - RIG.G19_BACK_FACE_Z) > 1e-9:
    raise AssertionError("pinion_rig_layout.G19_BACK_FACE_Z drifted from the gear grid")
if abs(APINION_Z_BACK - _G19_FACE_Z[1] - RIG.RIG_SET_LEAF_D) > 1e-9:
    raise AssertionError("the drum's back end is not RIG_SET_LEAF_D off g19")
APINION_FRONT_WORST_Z = APINION_Z_FRONT + sum(RIG.DRUM_FRONT_RETREAT_STACK.values())
G0_FRONT_WORST_Z = Z_DRUM0 - DRUM_FACE / 2.0 - sum(RIG.G0_FRONT_SOUTH_STACK.values())
J0_SLACK_WORST = (G0_FRONT_WORST_Z - 1.0) - APINION_FRONT_WORST_Z
if J0_SLACK_WORST < 0.0:
    raise AssertionError(f"the drum uncovers j = 0 by {-J0_SLACK_WORST:.3f} at the worst stack")
if (
    math.hypot(APINION_X - X_DRUM, Y_DRIVE - APINION_Y)
    < TIP_DRUM120 + TIP_APINION + 1.0
):
    raise AssertionError("alignment pinion crowds the cylinder train")
if math.hypot(PIVOT_X - X_DRUM, Y_DRIVE - PIVOT_Y) > ENGAGED_C2C + STRAP_C2C - 0.25:
    raise AssertionError("engage swing cannot reach the meshed centre distance")
for _j in range(20):
    _tip = _cone_tip_radius_max(120 - 6 * _j)
    if (
        math.hypot(APINION_X - cone_seat(_j)[0], Y_DRIVE - APINION_Y)
        < _tip + TIP_APINION + 0.25
    ):
        raise AssertionError(f"pinion drum crowds cone gear {_j}")
if (
    math.hypot(APINION_X - GEAR64_SEAT[0], Y_DRIVE - APINION_Y)
    < _GEAR64_TIP_R + TIP_APINION + 0.25
):
    raise AssertionError("pinion drum crowds the 64T crank-drive gear")
if STRAP_C2C < TIP_APINION + 3.175 + 0.25:
    raise AssertionError("pivot shaft fouls the pinion drum tips")
if math.hypot(LIFT_X - APINION_X, APINION_Y - PIVOT_Y) < TIP_APINION + 3.175 + 0.25:
    raise AssertionError("lift rod fouls the pinion drum tips")
if abs(LIFT_X - PIVOT_X) < STRAP_R_END + 3.175 + 0.25:
    raise AssertionError("lift rod fouls the strap's swinging pivot end cap")
if LEVER_Z + LEVER_HUB_LEN / 2.0 > BLOCK_FRONT_Z0 - 0.25:
    raise AssertionError("lever hub reaches the front pivot block")
if abs((LEVER_Z - (LEVER_HUB_LEN / 2.0 - LEVER_WALL_T)) - LIFT_ROD_Z0) > 1e-9:
    raise AssertionError("lever hub bore floor off the lift rod's front end")
# The parked lever shaft passes clear of the pinion ARBOR (PR7: the Ø8 steel
# arbor replaced the drum's Ø6.35 stubs; it spans the lever's z band, so the
# 3D clearance is the 2D distance from the arbor's (x, y) to the Ø6 rod's
# axis line). Perpendicular form when the foot lands on the rod segment,
# endpoint distance otherwise. The rod is a straight Ø6 (ch25 img07).
_LEV_T = math.radians(LEVER_TILT_DEG)
_LEV_U = (-math.sin(_LEV_T), math.cos(_LEV_T))  # positive tips machine -X
_LEV_REL = (APINION_X - LIFT_X, APINION_Y - LIFT_Y)  # root -> arbor axis
_LEV_FOOT = _LEV_REL[0] * _LEV_U[0] + _LEV_REL[1] * _LEV_U[1]
if 0.0 <= _LEV_FOOT <= LEVER_LEN:
    _LEV_STUB_D = abs(_LEV_REL[0] * _LEV_U[1] - _LEV_REL[1] * _LEV_U[0])
else:
    _end = min(max(_LEV_FOOT, 0.0), LEVER_LEN)
    _LEV_STUB_D = math.hypot(
        _LEV_REL[0] - _end * _LEV_U[0], _LEV_REL[1] - _end * _LEV_U[1]
    )
# Where the rod plane shares the collar's z band, the Ø15 collar -- not the
# Ø8 shaft -- is what the lever passes.
_LEV_ROD_Z = (LEVER_Z - 3.0, LEVER_Z + 3.0)
_ARBOR_DIA_AT_LEVER = (
    ARBOR_COLLAR_OD
    if _LEV_ROD_Z[0] < ARBOR_COLLAR_Z[1] + 0.25 and _LEV_ROD_Z[1] > ARBOR_COLLAR_Z[0] - 0.25
    else ARBOR_DIA
)
if _LEV_STUB_D < (_ARBOR_DIA_AT_LEVER + LEVER_ROD_DIA) / 2.0 + 0.25:
    raise AssertionError("lever shaft crowds the pinion arbor")

# --- pinion return spring (ch. 25, p.68-69): keeps the drum disengaged -------
# Phosphor-bronze leaf EAST of the BACK strap only (t00393 shows the front
# strap clean).  Re-derived 2026-09-24 (handoff dt-pinion-spring-rederive-
# 20260924): the foot is screwed to the base OUTBOARD, east of the strap --
# img01's far-left black head; that side of img01 is the drum side (cylinder
# gear top-left, lift rod and follower bottom-right), not west as the old
# block read it.  The blade rises leaning IN toward the strap and its crest
# bears on the straight east flank CONTACT_T up from the pivot, about 5 below
# the arbor (img04); a short flick turns back east above the crest.
# Gravity swings the cluster east into mesh; the leaf pushes the strap top
# back WEST onto the parked cam collar, and the lever engages against it.
# In rigid CAD the engaged pose overlaps the unflexed blade, a documented
# simplification (issue #158): only the PARKED pose is interference-gated;
# the swing's contact locus, preload and root stress are proven analytically
# below the cam block (they need _PHI_ENG).
# Geometry is imported from dt_pinion_spring_geometry: machine = (SPRING_X -
# local x, Y_BASE_TOP + local y) -- the part is placed Ry(180), its local +x
# running machine -x (east).  The part's inside-surface path puts the wall
# west of the blade and under the foot (the build's west-extreme and pad-merge
# gates prove it), so SPR_CREST_L is already the contact face.
SPRING_X = PIVOT_X + SPR_PIVOT_LX  # machine anchor
# The strap's INNER face is what the drum end fixes; the strap thickness grows
# OUTBOARD from there.  The pad is set a gage leaf off the back block
# (pinion_rig_layout.SPRING_PAD_LEAF), which puts the blade SPRING_BLADE_INSET
# in from that inner face.
STRAP_Z_INNER = RIG.STRAP_Z_INNER
# Blade inner edge, in from the strap's inner face: SPRING_BLADE_INSET keeps the
# whole blade on the flank at every strap thickness, RIG_MARGIN_SPARE over its
# floor (pinion_rig_layout).
SPRING_BLADE_INSET = RIG.SPRING_BLADE_INSET
SPRING_Z = RIG.SPRING_Z
# _SPR_U (up the strap axis) and _SPR_N (its east normal, east = machine -x)
# are pinion_rig_park_geometry's parked strap frame.


def _spring_machine(local: tuple[float, float]) -> tuple[float, float]:
    return (SPRING_X - local[0], Y_BASE_TOP + local[1])


def _strap_frame(p: tuple[float, float], phi: float = 0.0) -> tuple[float, float]:
    """(station up the strap axis, offset east of it) of ``p`` for the strap
    swung ``phi`` CCW (toward mesh) about the pivot."""
    c, s = math.cos(phi), math.sin(phi)
    u = (_SPR_U[0] * c - _SPR_U[1] * s, _SPR_U[0] * s + _SPR_U[1] * c)
    n = (_SPR_N[0] * c - _SPR_N[1] * s, _SPR_N[0] * s + _SPR_N[1] * c)
    d = (p[0] - PIVOT_X, p[1] - PIVOT_Y)
    return (d[0] * u[0] + d[1] * u[1], d[0] * n[0] + d[1] * n[1])


_SPR_PIVOT = _spring_machine((SPR_PIVOT_LX, SPR_PIVOT_LY))
SPRING_CREST = _spring_machine(SPR_CREST_L)  # parked contact, crest west face
SPRING_KINK_C = _spring_machine(SPR_KINK_C_L)  # crest centre
SPRING_KINK_START = _spring_machine(SPR_KINK_START_L)  # path = the blade's east face
SPRING_FLAT_TIP = _spring_machine(SPR_FLAT_TIP_L)  # path = the flick's east face
SPRING_BEND_EXIT = _spring_machine(SPR_BEND_EXIT_L)  # path = the blade's east face
SPRING_FOOT_TOP = Y_BASE_TOP + SPRING_T
SPRING_HOLE_X = SPRING_X - SPR_HOLE_X_L
SPRING_FOOT_END_X = SPRING_X - SPR_FOOT_END_L[0]  # the free end, east
SPRING_FOOT_TAN_X = SPRING_X - SPR_FOOT_TAN_L[0]  # the bend tangent

if math.hypot(_SPR_PIVOT[0] - PIVOT_X, _SPR_PIVOT[1] - PIVOT_Y) > 0.01:
    raise AssertionError("spring part frame disagrees with the strap pivot")
if abs(SPR_STRAP_LEAN_DEG - STRAP_LEAN_DEG) > 0.01:
    raise AssertionError("spring geometry assumes another parked strap lean")
if abs(SPR_STRAP_HALF_WIDTH - STRAP_R_END) > 1e-9:
    raise AssertionError("spring geometry assumes another strap width")
# Crest station and air, parked: on the straight flank at CONTACT_T, clear of
# the arbor end cap (the flank is straight from the pivot to STRAP_C2C).
_CREST_T, _CREST_N = _strap_frame(SPRING_CREST)
if abs(_CREST_T - SPR_CONTACT_T) > 0.01:
    raise AssertionError("spring crest is off its contact station")
if abs(_CREST_N - STRAP_R_END - SPR_PARKED_AIR) > 0.01 or SPR_PARKED_AIR < 0.1:
    raise AssertionError("spring crest does not hover its parked air off the flank")
if _CREST_T > STRAP_C2C - 1.0:
    raise AssertionError("spring crest bears on the arbor end cap, not the flank")
if SPRING_BLADE_INSET < 0.0 or SPRING_BLADE_INSET + SPRING_W > STRAP_T:
    raise AssertionError("spring blade overhangs the strap flank axially")
# The cylinder drum: the leaf rides axially PAST its last (j = 19) gear
# (RIG_MARGINS books its front edge against that gear's back face at the
# worst fit-up), so the flexed blade can never meet the 120T tips; only the
# north end disc (Ø55, END_DISC_AIR outboard of that gear) shares its z
# band.  Parked, the crest and the flick tip also clear the tip circle
# itself in 2D; the engaged blade is gated against the disc with the swing
# gates below.  Each books the strip's full thickness on the east side.
for _label, _p in (("crest", SPRING_CREST), ("flick tip", SPRING_FLAT_TIP)):
    if math.hypot(X_DRUM - _p[0], Y_DRIVE - _p[1]) - SPRING_T < TIP_DRUM120 + 0.25:
        raise AssertionError(f"spring {_label} crowds the cylinder-gear tips")
# The flick turns back east: its tip stays off the parked flank and the cap.
if _strap_frame(SPRING_FLAT_TIP)[1] - SPRING_T < STRAP_R_END + 0.25:
    raise AssertionError("spring flick tip re-enters the parked strap flank")
if (
    math.hypot(SPRING_FLAT_TIP[0] - APINION_X, SPRING_FLAT_TIP[1] - APINION_Y)
    - SPRING_T
    < STRAP_R_END + 0.25
):
    raise AssertionError("spring flick tip reaches the strap's arbor end cap")
if SPRING_Z + SPRING_W / 2.0 > BLOCK_BACK_Z0 - 0.25:
    raise AssertionError("spring reaches the back pivot block")
# The foot's screw pad widens the free end forward of the strip, flush with
# its aft edge (pinion_rig_layout): booked with that edge at the pad leaf's
# thinnest setting, no width band reaches it.  The leaf sets z, so z alone
# is gated (Main, #859 restricted review).
_SPR_PAD_Z_HI = RIG.SPRING_PAD_AFT_Z + RIG.FEELER_SET_ERROR
if _SPR_PAD_Z_HI > BLOCK_BACK_Z0 - 0.25:
    raise AssertionError("spring foot pad reaches the back pivot block")
# The screw head sits on the pad: clear of the free end and of the bend.
if (SPRING_HOLE_X - FSCREW_HEAD_DIA / 2.0) - SPRING_FOOT_END_X < 0.25:
    raise AssertionError("spring foot screw head overhangs the foot's free end")
if SPRING_FOOT_TAN_X - (SPRING_HOLE_X + FSCREW_HEAD_DIA / 2.0) < 0.25:
    raise AssertionError("spring foot screw head crowds the bend")

# --- cam engage path (ch. 25 + page001_img01; PR8) ---------------------------
# Each strap carries a Ø4 follower STUD in a blind edge seat FPIN_DROP
# below the pivot (negative = above, 2026-09) (build_dt_pinion_bracket); it RESTS ON the eccentric cam collar
# (build_dt_pinion_cam) pinned to the lift rod in the reclosed WEST bore
# the pivot shaft in the blocks' reclosed west bores. Turning the lever spins rod +
# collars as one; the rising OD lifts the pin -- an upward push ~15 west of
# the pivot -- rotating the strap top EAST into mesh. Parked (ecc down, the
# authored pose) the collar top hovers a designed ~0.15 under the pin (exact
# tangency tips the interference gate on FP noise -- the PR5 gap lesson); the
# return spring holds the strap west on it.
# U27: the drill-rod stud slips into the H7 seat line-to-line and is bonded
# (LOCTITE 638), so the nominal solids touch without overlapping.
if abs(FPIN_DIA - STRAP_PIN_BORE) > 1e-9:
    raise AssertionError("follower pin nominal is not line-to-line with its seat")
if abs(FPIN_SEAT - FPIN_SEAT_LEN) > 1e-9:
    raise AssertionError("pin SEAT_LEN disagrees with the bracket PIN_SEAT")
# U27 slip fit: the set-screwed cam needs only 0.02-0.10 diametral clearance on
# the Ø6.35 lift rod (dt_pinion_cam_spec proves it at the printed limits).
if not 0.02 <= CAM_BORE_DIA - 6.35 <= 0.10:
    raise AssertionError("cam bore nominal is outside its 0.02-0.10 slip clearance")
if CAM_THIN_SIDE_WALL < 1.5:
    raise AssertionError("cam thin-side wall is below the 1.5 mm U27 floor")
# Blind-seat integrity: nearest approach of the seat cylinder to the pivot
# bore (perpendicular skew axes; the worst point is the seat bottom).
_FPIN_S0 = STRAP_R_END - FPIN_SEAT  # 5.0: seat bottom, from the centreline
if math.hypot(_FPIN_S0, FPIN_DROP) - FPIN_DIA / 2.0 - STRAP_PIVOT_BORE / 2.0 < 0.15:
    raise AssertionError("blind pin seat cuts too close to the pivot bore")
# Pin axis, machine frame: _FPIN_C (pinion_rig_park_geometry), through the
# strap axis FPIN_DROP below the pivot, running WEST along -N (the axis RISES
# going west, N[1] < 0).
_FPIN_TIP_S = _FPIN_S0 + FPIN_LEN  # 20: dome end station, from the centreline
_S_CAM = (_FPIN_C[0] - LIFT_X) / _SPR_N[0]  # 14.9: where the pin crosses the
# rod/cam plane x = LIFT_X
if _FPIN_TIP_S - _S_CAM < 2.0:
    raise AssertionError("follower pin ends short of the cam axis")
if _S_CAM - _FPIN_S0 < 2.0:
    raise AssertionError("cam contact lands inside the strap edge, not the pin")
_FPIN_Y_AT_CAM = _FPIN_C[1] - _S_CAM * _SPR_N[1]  # 64.04

# Cam z stations: CAM_PIN_STATION of the 9-long collar, from its front face.
# U28 (2026-09-23) deleted the set-pin boss for a sub-flush M2.5 set screw at
# SET_SCREW_Z = 4.5, so the collar is a bare cylinder at every azimuth of the
# free cam spin.  Ruling (c): the FRONT collar is set against the front
# block's inner face (0.25 feeler) -- flush with the strap's outer face, so
# the pin rides mid-collar (T/2) and the collar and lever hub capture the lift
# rod on the block.  The BACK collar is set the same way, its back face
# BACK_COLLAR_LEAF_F off the back block (user ruling P1-1), so the pin rides
# BACK_CAM_PIN_STATION into it and keeps >= 2.75 of collar on both sides at
# every setting (test_dt_drive_train_support_layout).
_STRAP_MID_Z = tuple(
    z + s * STRAP_T / 2.0 for z, s in zip(STRAP_Z_INNER, (-1.0, 1.0), strict=True)
)  # -74.562, +78.088 (pinion_rig_layout)
CAM_PIN_STATION = (STRAP_T / 2.0, RIG.BACK_CAM_PIN_STATION)  # pin plane, from each collar front face
CAM_Z0 = tuple(z - s for z, s in zip(_STRAP_MID_Z, CAM_PIN_STATION, strict=True))
for _z0 in CAM_Z0:
    if _z0 < LIFT_ROD_Z0 + 1.0 or _z0 + CAM_LEN > LIFT_ROD_Z0 + RIG.LIFT_ROD_LEN - 1.0:
        raise AssertionError("cam collar overhangs the lift rod")
if max(CAM_PIN_STATION) > CAM_LEN - 1.0 or min(CAM_PIN_STATION) < 1.0:
    raise AssertionError("follower pin rides off a collar face")
if CAM_Z0[0] < BLOCK_FRONT_Z0 + BLOCK_DEPTH + RIG.FRONT_BLOCK_FEELER - 1e-9:
    raise AssertionError("front cam collar crowds the front pivot block")


# PARK: collar (ecc down) under the pin, by design 0.10..0.25 of air. The
# binding quantity is the SKEW-perpendicular distance from the collar axis's
# in-plane point to the LEANING pin line, minus the radii sum -- NOT the
# vertical gap at the crossing x (that mistake put the first build 0.009
# into the collar: the pin's closest approach is downhill-west of the
# crossing). The collar axis pierces the pin's z-plane at (LIFT_X, LIFT_Y -
# ECC) parked; the pin line runs from _FPIN_C along -N (_pin_line_dist,
# pinion_rig_park_geometry).
_PARK_GAP = _pin_line_dist(LIFT_Y - CAM_ECC) - (FPIN_DIA + CAM_OD) / 2.0
if not 0.10 <= _PARK_GAP <= 0.25:
    raise AssertionError(f"park gap {_PARK_GAP:.3f} outside the 0.10..0.25 design band")

# The pure parked/engaged pose owner solves the same physical c2c triangle
# for assembly placement, the drawing and the alignment-zero contact datum.
if not 0.01 < _PHI_ENG < math.radians(10.0):
    raise AssertionError("engage swing angle out of the expected band")

# ENGAGE reachability: rotate the pin's axis CCW by _PHI_ENG about the pivot,
# re-read its height over the rod plane, and prove the collar's max top (ecc
# up) reaches the engaged underside with margin. (Pushing UP at a point ~15
# WEST of the pivot torques the strap top EAST: tau_z = +15 * F > 0 = CCW.)
_ENG_C, _ENG_S = math.cos(_PHI_ENG), math.sin(_PHI_ENG)
_FPIN_C_ENG = (
    PIVOT_X + (_FPIN_C[0] - PIVOT_X) * _ENG_C - (_FPIN_C[1] - PIVOT_Y) * _ENG_S,
    PIVOT_Y + (_FPIN_C[0] - PIVOT_X) * _ENG_S + (_FPIN_C[1] - PIVOT_Y) * _ENG_C,
)
_N_ENG = (
    _SPR_N[0] * _ENG_C - _SPR_N[1] * _ENG_S,
    _SPR_N[0] * _ENG_S + _SPR_N[1] * _ENG_C,
)
_S_CAM_ENG = (_FPIN_C_ENG[0] - LIFT_X) / _N_ENG[0]
_FPIN_Y_AT_CAM_ENG = _FPIN_C_ENG[1] - _S_CAM_ENG * _N_ENG[1]
_NEED_LIFT = _FPIN_Y_AT_CAM_ENG - _FPIN_Y_AT_CAM  # ~1.57 up for the 32T rig
if _NEED_LIFT <= 0.2:
    raise AssertionError("engage swing does not RAISE the follower over the cam")
# Drive authority: with the collar rotated ecc-UP, its surface must reach at
# least 0.25 PAST first touch on the engaged pin line (the same skew metric
# as the park gap, engaged pose).
_D_ENG = _pin_line_dist(LIFT_Y + CAM_ECC, c=_FPIN_C_ENG, n=_N_ENG)
if (FPIN_DIA + CAM_OD) / 2.0 - _D_ENG < 0.25:
    raise AssertionError("cam lift cannot reach the engaged follower")
if _FPIN_TIP_S - _S_CAM_ENG < 1.0:
    raise AssertionError("engaged pin slides off the cam axis")


# Solve the lever's photographed engaged angle from the real eccentric-cam
# contact, rather than assuming the throw continues on the parked side.  The
# cam starts eccentric-down at rotation 0 and turns clockwise until its OD
# first reaches the follower in the engaged strap pose.  Bisection is bounded
# by down (clear) and up (over-travel); the unique root is about -81.9 degrees,
# so the +10-degree parked lever finishes near -71.9 degrees.  The ch25 front
# pair independently reads about +10 parked and -76 engaged.
def _engaged_cam_gap(rotation_deg: float) -> float:
    a = math.radians(rotation_deg)
    cam_centre = (
        LIFT_X + CAM_ECC * math.sin(a),
        LIFT_Y - CAM_ECC * math.cos(a),
    )
    dx = cam_centre[0] - _FPIN_C_ENG[0]
    dy = cam_centre[1] - _FPIN_C_ENG[1]
    axis_distance = abs(dx * (-_N_ENG[1]) - dy * (-_N_ENG[0]))
    return axis_distance - (FPIN_DIA + CAM_OD) / 2.0


_CAM_ROT_LO, _CAM_ROT_HI = -180.0, 0.0
if not _engaged_cam_gap(_CAM_ROT_LO) < 0.0 < _engaged_cam_gap(_CAM_ROT_HI):
    raise AssertionError("engaged cam-contact root is not bracketed by down/up")
for _ in range(60):
    _cam_mid = (_CAM_ROT_LO + _CAM_ROT_HI) / 2.0
    if _engaged_cam_gap(_cam_mid) > 0.0:
        _CAM_ROT_HI = _cam_mid
    else:
        _CAM_ROT_LO = _cam_mid
CAM_ENGAGE_ROTATION_DEG = (_CAM_ROT_LO + _CAM_ROT_HI) / 2.0
LEVER_ENGAGED_TILT_DEG = LEVER_TILT_DEG + CAM_ENGAGE_ROTATION_DEG
if not -85.0 < CAM_ENGAGE_ROTATION_DEG < -75.0:
    raise AssertionError("pinion cam engage rotation left the photo-backed range")
if not -80.0 < LEVER_ENGAGED_TILT_DEG < -65.0:
    raise AssertionError("engaged pinion lever left the photographed +X-side range")


# Follower-seat integrity in the uncut strap. The complete Ø4 mouth must land
# on the straight -X flank, and the 4-deep blind seat must leave solid stock
# before the opposite flank.
_PIN_SEAT_Y = -FPIN_DROP
_PIN_SEAT_R = FPIN_DIA / 2.0
if _PIN_SEAT_Y - _PIN_SEAT_R < 0.0 or _PIN_SEAT_Y + _PIN_SEAT_R > STRAP_C2C:
    raise AssertionError("follower-seat mouth leaves the bracket's straight flank")
_PIN_SEAT_ENTRY_X = -STRAP_R_END
_PIN_SEAT_BOTTOM_X = _PIN_SEAT_ENTRY_X + FPIN_SEAT
_PIN_SEAT_REMAINING_WALL = STRAP_R_END - _PIN_SEAT_BOTTOM_X
if _PIN_SEAT_REMAINING_WALL < _PIN_SEAT_R:
    raise AssertionError(
        f"follower seat leaves only {_PIN_SEAT_REMAINING_WALL:.3f} mm "
        "before the opposite flank"
    )

# Full-rotation sweep of the bare collar about the rod axis (U28: no boss, so
# the eccentric OD's far point is the whole sweep) against the base and the
# pivot shaft.  (The return spring's foot no longer runs under the rod: it is
# screwed down east of the strap, 2026-09-24.)
_CAM_SWEEP_R = CAM_ECC + CAM_OD / 2.0  # 9.3: U28 boss deleted, bare collar
if LIFT_Y - _CAM_SWEEP_R - Y_BASE_TOP < 0.25:
    raise AssertionError("cam collar sweep reaches the base top")
if math.hypot(PIVOT_X - LIFT_X, PIVOT_Y - LIFT_Y) - _CAM_SWEEP_R - 3.175 < 0.25:
    raise AssertionError("cam sweep reaches the pivot shaft")
# The return spring stands east of the strap and the lift rod west of it,
# the collar's sweep spanning the blade's height.  The whole leaf -- foot,
# bend, blade and crest -- keeps 0.25 off the rod's envelope (the collar
# sweeps about the rod's own axis, so it contains the rod) where the leaf
# sits furthest west.  The base seat is spotted through the pad hole, so
# the screw's float in that hole and the formed profile's band move it.
SPRING_WEST_SHIFT_STACK = {
    "MHA-DT-024 formed profile band": SPR_FORMED_BAND,
    "#4 screw float in the pad's clearance hole": (
        blind_cut_dia_mm(SPR_HOLE_SPEC) - THREAD_MAJOR_MM[FSCREW_THREAD]
    )
    / 2.0,
}
_SPR_WEST_X = max(
    SPRING_FOOT_TAN_X,  # the foot, up to the bend
    SPRING_BEND_EXIT[0] + SPRING_T,  # the bend and the blade's root
    SPRING_KINK_START[0] + SPRING_T,  # the blade's top
    SPRING_KINK_C[0] + SPR_R_KINK + SPRING_T,  # the crest's outer arc
    SPRING_FLAT_TIP[0] + SPRING_T,  # the flick
)
SPRING_TO_LIFT_ROD = (
    LIFT_X
    - max(3.175, _CAM_SWEEP_R)
    - _SPR_WEST_X
    - sum(SPRING_WEST_SHIFT_STACK.values())
)
if SPRING_TO_LIFT_ROD < 0.25:
    raise AssertionError("spring leaf reaches the lift rod's collar sweep")

# --- return spring across the engage swing (analytic; issue #158) ------------
# The strap swings 0 -> _PHI_ENG CCW into the blade.  The leaf deflects by the
# crest's penetration into the swung flank on top of its PRESET (the free form
# stands PRESET into the parked flank; the model hovers PARKED_AIR off it).
# Gravity moments of the swing cluster about the pivot, parked then engaged,
# N.mm; both turn it INTO mesh. Re-measured 2026-10-10 with
# diagnostics/collect_dt_swing_gravity.py from the seven native STL exports of
# farm run 20261010T084710772Z-bcad1a8e9e664595b56e918f9cc4f1e4 (0d454fa91),
# the finite-stock-profile 48DP drum: its weight volume fell 449 mm^3 and the
# moments 1.0% parked, 4.5% engaged against the 2026-10-08 basis (fb97437).
# The 1e-5 mm KD-tree seam weld preserves every face; watertightness and winding
# are checked separately. Centroids use this module's analytic transforms;
# five weight volumes remain analytic, and drum/brackets use mesh volumes.
# This preserves #859's hybrid method (03b51bce2), not native COM mass metrology.
# Brass is 8500 nominal / 8800 corner; steel is 7800 kg/m^3.
# Install the measured basis AND frozen fingerprint together (DEVELOPING.md).
SWING_GRAVITY_NMM = (14.312953639673118, 24.418432096063757)
SWING_GRAVITY_CORNER_NMM = (14.595168510026149, 24.893891179679525)
# The basis those moments were computed at: part -> (count, volume mm^3,
# density kg/m^3). The measured basis and fingerprint deliberately stay frozen:
# the support-layout regression names both moment constants when
# any current part's analytic volume, material or governing dimensions move.
SWING_GRAVITY_BASIS = {
    "dt-alignment-pinion": (1, 24200.015811223286, 8500.0),
    "dt-pinion-arbor": (1, 13702.959423527212, 7800.0),
    "dt-pinion-pivot-shaft": (1, 5937.0169027658985, 7800.0),
    "dt-pinion-bracket": (2, 4563.672483959315, 7800.0),
    "dt-pinion-arbor-collar": (1, 2135.7428529140184, 7800.0),
    "dt-pinion-handle": (1, 1837.831702350029, 7800.0),
    "dt-pinion-cam-pin": (2, 256.62204310603346, 7800.0),
}
SWING_GRAVITY_MASS_G = 465.0824258937632
# Frozen governing dimensions of the accepted native-STL calibration, never
# live config aliases.
SWING_GRAVITY_FINGERPRINT = {
    "dt-alignment-pinion": {
        "TEETH": 32,
        "DIAMETRAL_PITCH": 48.0,
        "PRESSURE_ANGLE_DEG": 20.0,
        "FACE_WIDTH": 143.2,
        "BORE_DIA": 8.0,
        "CUTTER_REFERENCE_TEETH": 26,
        "CUTTER_RADIAL_TRANSLATION_MM": 1.5874999999999986,
        "PITCH_TOOTH_THICKNESS_MM": 0.8293770709126581,
        "SUPPORT_OUTSIDE_DIA_MM": 17.979877681931494,
        "OUTSIDE_DIA": 17.63,
        "WHOLE_DEPTH": 1.0097916666666675,
        "MAX_CUT_DEPTH_MM": 1.0111012137912878,
        "BASE_TANGENT_SPAN": 4.141050235926491,
        "ROOT_MIN_DIA_MM": 15.607797572417423,
        "ROOT_MAX_DIA_MM": 15.610416666666664,
    },
    "dt-pinion-bracket": {
        "WIDTH": 15.0,
        "C2C": 28.0,
        "THICKNESS": 9.0,
        "PIVOT_BORE": 6.35,
        "ARBOR_BORE": 8.0,
        "PIN_BORE": 4.0,
        "PIN_SEAT": 4.0,
        "PIN_DROP": -7.0,
        "CROSS_HOLE_CZ": 4.5,
    },
}
if (
    abs(
        sum(n * v * rho * 1e-6 for n, v, rho in SWING_GRAVITY_BASIS.values())
        - SWING_GRAVITY_MASS_G
    )
    > 0.01
):
    raise AssertionError("SWING_GRAVITY_BASIS no longer sums to its mass")
_PRELOAD_MARGIN = 1.5  # over gravity, at the soft corner
_STRESS_SF = 1.5  # on yield, at the stiff corner
# Stock corners (#859 ruling 1): the leaf is formed to the nominal inside
# profile, so a thicker strip moves the contact face into the flank by the
# thickness excess.  Soft: thinnest, narrowest strip.  Stiff: thickest strip.
# Each is then walked over every formed corner (below).
_SPR_T_LO, _SPR_T_HI = (SPRING_T + _d for _d in deviations(SPRING_T_BAND))
_SPR_W_LO = SPRING_W + printed_deviations(SPRING_W, SPRING_W_PLACES)[0]
_SPR_STEPS = 1 + math.ceil(math.degrees(_PHI_ENG) / 0.25)
_SPR_BLADE_SAMPLES = 16
_SPR_CREST_OUTER_R = SPR_R_KINK + SPRING_T  # the crest's contact-face radius
_spr_blade = (
    SPRING_KINK_START[0] - SPRING_BEND_EXIT[0],
    SPRING_KINK_START[1] - SPRING_BEND_EXIT[1],
)
_spr_len = math.hypot(*_spr_blade)
_SPR_WEST = (_spr_blade[1] / _spr_len, -_spr_blade[0] / _spr_len)  # blade normal
_spr_deflection: list[float] = []
_spr_station: list[float] = []
for _i in range(_SPR_STEPS):
    _phi = _PHI_ENG * _i / (_SPR_STEPS - 1)
    # The flank touches the crest where the crest's outward normal faces it:
    # that direction must stay on the crest arc (blade side -> flick side).
    _t, _n = _strap_frame(SPRING_KINK_C, _phi)
    _n -= _SPR_CREST_OUTER_R
    _toward = math.atan2(
        -(_SPR_N[0] * math.sin(_phi) + _SPR_N[1] * math.cos(_phi)),
        -(_SPR_N[0] * math.cos(_phi) - _SPR_N[1] * math.sin(_phi)),
    )
    _from = math.atan2(_SPR_WEST[1], _SPR_WEST[0])
    _sweep = (_toward - _from + math.pi) % (2.0 * math.pi) - math.pi
    if not -1e-9 <= _sweep <= math.radians(SPR_KINK_DEG) + 1e-9:
        raise AssertionError(f"spring contact runs off the crest arc at {_phi:.4f}")
    # The contact stays on the STRAIGHT flank, clear of the arbor end cap.
    if not 1.0 <= _t <= STRAP_C2C - 1.0:
        raise AssertionError(f"spring contact leaves the straight flank at {_phi:.4f}")
    # The crest is the first contact: no point of the blade's west face below
    # it nor the flick tip comes nearer the swung flank.
    for _k in range(_SPR_BLADE_SAMPLES + 1):
        _f = _k / _SPR_BLADE_SAMPLES
        _p = (
            SPRING_BEND_EXIT[0] + _f * _spr_blade[0] + SPRING_T * _SPR_WEST[0],
            SPRING_BEND_EXIT[1] + _f * _spr_blade[1] + SPRING_T * _SPR_WEST[1],
        )
        if _strap_frame(_p, _phi)[1] < _n - 1e-6:
            raise AssertionError("spring blade crosses the flank below the crest")
    if _strap_frame(SPRING_FLAT_TIP, _phi)[1] - SPRING_T < _n - 1e-6:
        raise AssertionError("spring flick tip crosses the flank above the crest")
    _spr_deflection.append(SPR_PRESET + SPR_PARKED_AIR - (_n - STRAP_R_END))
    _spr_station.append(_t)
SPRING_DEFLECTION = (_spr_deflection[0], _spr_deflection[-1])  # parked, engaged
# Every accepted formed profile (Codex #859, PRRT_kwDOPHDy386mTao2): the print
# holds FootLen, BendR, FreeKinkH, FreeKinkV and KinkR to the formed band each,
# independently, so each gate walks all 32 sign corners.  A corner moves the
# free crest's penetration, the arm and the contact station by what it moves
# them in the free profile (spr_formed_contact); those changes ride the
# installed nominal the swing above computes.  The swing's own penetration
# grows with the station, so a corner scales it by its station.  The stock
# corners stay: the soft gate forms a thin, narrow strip, the stiff gate a
# thick one (the thickness moves the crest's contact face with it).
_SPR_FREE_NOM = spr_formed_contact()
_SPR_SWING_DEFLECTION = SPRING_DEFLECTION[1] - SPRING_DEFLECTION[0]
_SPR_SWING_STATION = _spr_station[-1] - _spr_station[0]


def _spring_corner(deviations: dict[str, float], thick: float):
    """(parked, engaged) deflection, arm, and (parked, engaged) station."""
    penetration, arm, station = spr_formed_contact(deviations, thick)
    parked = SPRING_DEFLECTION[0] + penetration - _SPR_FREE_NOM[0]
    station_p = _spr_station[0] + station - _SPR_FREE_NOM[2]
    engaged = parked + _SPR_SWING_DEFLECTION * station_p / _spr_station[0]
    return (
        (parked, engaged),
        SPR_BLADE_ARM + arm - _SPR_FREE_NOM[1],
        (station_p, station_p + _SPR_SWING_STATION),
    )


_spr_ratios = []
for _dev in SPR_FORMED_CORNERS:
    _defl, _arm, _stations = _spring_corner(_dev, _SPR_T_LO)
    _spr_ratios.append(
        tuple(
            spr_contact_force(_d, _SPR_T_LO, _SPR_W_LO, _arm) * _t / _m
            for _d, _t, _m in zip(_defl, _stations, SWING_GRAVITY_CORNER_NMM, strict=True)
        )
    )
SPRING_PRELOAD_RATIO = tuple(
    min(_r[_k] for _r in _spr_ratios) for _k in range(2)
)  # parked, engaged: the softest corner's moment over gravity
for _label, _ratio in zip(("parked", "engaged"), SPRING_PRELOAD_RATIO, strict=True):
    if _ratio < _PRELOAD_MARGIN:
        raise AssertionError(
            f"spring preload {_ratio:.2f}x loses to gravity {_label} at the soft corner"
        )
SPRING_STRESS_SF = min(
    SPR_YIELD_MPA / spr_root_stress(_defl[1], _SPR_T_HI, _arm)
    for _defl, _arm, _ in (
        _spring_corner(_dev, _SPR_T_HI) for _dev in SPR_FORMED_CORNERS
    )
)
if SPRING_STRESS_SF < _STRESS_SF:
    raise AssertionError(
        f"spring root stress SF {SPRING_STRESS_SF:.2f} engaged at the stiff corner"
    )
# The engaged blade flexes east toward the cylinder drum: the crest and the
# flick tip, carried east by the extra deflection, keep 0.25 to the north end
# disc beside them (the gears themselves end axially short of the leaf).
_spr_push = SPRING_DEFLECTION[1] - SPRING_DEFLECTION[0]
for _label, _p in (("crest", SPRING_CREST), ("flick tip", SPRING_FLAT_TIP)):
    _q = (_p[0] + _spr_push * _SPR_N[0], _p[1] + _spr_push * _SPR_N[1])
    if (
        math.hypot(X_DRUM - _q[0], Y_DRIVE - _q[1]) - _SPR_T_HI
        < END_DISC_DIA / 2.0 + 0.25
    ):
        raise AssertionError(f"engaged spring {_label} reaches the drum end disc")

# --- full-rotation clearance proofs (PR6) -------------------------------------
# The interference gate sees only the PARKED pose; the grip crossrod spins full
# circle during zeroing and the lift rod (pins + lever) sweeps the cam throw.
# Prove every angle clears the in-assembly neighbours: each sweep is a solid
# of revolution, so a neighbour is cleared by z-band disjointness or, where
# bands overlap, by radial clearance from the sweep axis. (Cross-assembly
# neighbours are parked-gated at the top level; the platen/pen hardware sits
# at y ~390+, far above both sweeps.)
# The separate Ø6 crossrod sweeps a radius set by its 32/33 mm asymmetric
# reaches.  Its thin axial band remains centred at the released HANDLE_Z.
# MHA-DT-022's integral Ø15 head, front crown, and Ø10.5 neck stay on the arbor
# axis; their wider axial band is the exact former handle-body envelope.
_GRIP_ROD_Z = (
    HANDLE_Z - HANDLE_ROD_DIA / 2.0,
    HANDLE_Z + HANDLE_ROD_DIA / 2.0,
)
_GRIP_HEAD_Z = (
    ARBOR_Z0 + ARBOR_HEAD_FRONT_Z - ARBOR_HEAD_CAP_SAG,
    ARBOR_Z0 + ARBOR_NECK_END_Z,
)
# In-assembly bodies near the grip: everything of the swing rig ends well
# north of the crossrod band; the crank cluster lives south/east of it.
_SWING_RIG_BANDS = (
    (
        LEVER_Z - LEVER_HUB_LEN / 2.0 - LEVER_CAP_SAG,
        LEVER_Z + LEVER_HUB_LEN / 2.0,
        "lever hub",
    ),
    (BLOCK_FRONT_Z0, BLOCK_FRONT_Z0 + BLOCK_DEPTH, "front pivot block"),
    (LIFT_ROD_Z0, LIFT_ROD_Z0 + RIG.LIFT_ROD_LEN, "lift rod"),
    (PIVOT_SHAFT_Z0, PIVOT_SHAFT_Z0 + RIG.TORQUE_SHAFT_LEN, "pivot shaft"),
    (RIG.STRAP_Z_OUTER[0], RIG.STRAP_Z_INNER[0], "front strap"),
)
# The crank column behind the hub, each body a solid of revolution about the
# crank axis (z band, diameter): the selected crank sprocket paper-drive seats on it, the
# collar's seat spigot and body, and the MHA-DT-036 washer on the body's rear.
CRANK_SPROCKET_TIP_DIA = REMOVABLE.outside_dia(REMOVABLE.CRANK_TEETH)
CRANK_COLUMN_BANDS = (
    (
        REMOVABLE.BAND_FRONT_Z,
        REMOVABLE.SEAT_FACE_Z,
        CRANK_SPROCKET_TIP_DIA,
        "crank chain wheel",
    ),
    (REMOVABLE.SEAT_FACE_Z, CRANK_SPIGOT_FRONT_Z, SPIGOT_DIA, "crank seat spigot"),
    (CRANK_SPIGOT_FRONT_Z, CRANK_SEAT_WASHER_Z0, COLLAR_DIA, "crank collar body"),
    (
        CRANK_SEAT_WASHER_Z0,
        CRANK_SEAT_WASHER_REAR_Z,
        SEAT_WASHER.OD,
        "crank seat washer",
    ),
)
_CRANK_TO_GRIP_AXIS = math.hypot(X_CRANK - APINION_X, Y_CRANK - APINION_Y)
for _lo, _hi, _what in (
    *_SWING_RIG_BANDS,
    *((lo, hi, what) for lo, hi, _dia, what in CRANK_COLUMN_BANDS),
    (CRANK_ARM_Z0, CRANK_ARM_Z0 + ARM_THICKNESS, "crank arm"),
    (CRANK_HUB_Z0, CRANK_HUB_REAR_Z, "crank hub"),
):
    if _GRIP_ROD_Z[1] > _lo - 0.25 and _GRIP_ROD_Z[0] < _hi + 0.25:
        raise AssertionError(f"grip-crossrod sweep band reaches the {_what}")
# At its worst south travel (RIG_MARGINS' stack) the crossrod enters the
# washer's z band, so the crank column is cleared radially as well: the rod's
# farther reach plus its radius against each body's radius.
_GRIP_ROD_REACH = max(HANDLE_ROD_DOWN, HANDLE_ROD_UP) + HANDLE_ROD_DIA / 2.0
for _lo, _hi, _dia, _what in CRANK_COLUMN_BANDS:
    if _CRANK_TO_GRIP_AXIS - _GRIP_ROD_REACH - _dia / 2.0 < 0.25:
        raise AssertionError(f"grip-crossrod sweep circle reaches the {_what}")
# The integral head's own band (front crown apex to neck shoulder) spins with
# the arbor and is wider than the crossrod's, so it is proved against the same
# swing-rig bodies directly rather than inferred from the rod band.
for _lo, _hi, _what in _SWING_RIG_BANDS:
    if _GRIP_HEAD_Z[1] > _lo - 0.25 and _GRIP_HEAD_Z[0] < _hi + 0.25:
        raise AssertionError(f"integral grip-head band reaches the {_what}")
# The head's wider z band clips the crank column (collar and washer), so a
# column body sharing its band is cleared radially instead.  The crank
# arm/hub/handle sweep is axially disjoint from the integral head.
for _lo, _hi, _dia, _what in CRANK_COLUMN_BANDS:
    if (
        _GRIP_HEAD_Z[1] > _lo - 0.25
        and _GRIP_HEAD_Z[0] < _hi + 0.25
        and _CRANK_TO_GRIP_AXIS < ARBOR_HEAD_DIA / 2.0 + _dia / 2.0 + 0.25
    ):
        raise AssertionError(f"integral grip head reaches the {_what}")
if _GRIP_HEAD_Z[0] < CRANK_HUB_REAR_Z + 0.25:
    raise AssertionError("integral grip-head band reaches the crank hub")

# MHA-DT-032 handle pivot screw (U33): the shoulder seats on the arm's outboard
# face and its thread runs inboard through the arm's tapped hole.  User ruling
# 2026-09-29 (ch11 p.14): the tip is filed flush with the arm's inboard face
# at assembly, so the drive train places the INSTALLED configuration and
# nothing of the screw sweeps past the arm.
HANDLE_SCREW_Z0 = CRANK_ARM_Z0 - HANDLE_SCREW_SEAT_STATION  # slotted head face
HANDLE_SCREW_TIP_Z = CRANK_ARM_Z0 + HANDLE_SCREW_INSTALLED_THREAD
if abs(HANDLE_SCREW_TIP_Z - CRANK_ARM_ORIGIN_Z) > 1e-9:
    raise AssertionError("MHA-DT-032's filed tip is not flush with the arm's inboard face")
for _lo, _what in (
    (REMOVABLE.BAND_FRONT_Z, "crank chain wheel"),
    (_GRIP_HEAD_Z[0], "integral grip head"),
    (_GRIP_ROD_Z[0], "grip crossrod"),
):
    if HANDLE_SCREW_TIP_Z > _lo - 0.25:
        raise AssertionError(f"MHA-DT-032's filed tip reaches the {_what}")
if ARM_C2C - HANDLE_SCREW_THREAD_MAJOR / 2.0 < HUB_BARREL_DIA / 2.0 + 0.25:
    raise AssertionError("MHA-DT-032 thread reaches the crank hub barrel")

# Lever full throw: sample the solved cam-contact path from the photographed
# +10-degree parked pose to about -72 degrees engaged.  Clearance improves
# after the parked endpoint, but the complete crossing through vertical is
# checked rather than inferred.
_LEV_SWEEP_STEPS = math.ceil(abs(CAM_ENGAGE_ROTATION_DEG) / 0.25)
for _step in range(_LEV_SWEEP_STEPS + 1):
    _angle = LEVER_TILT_DEG + CAM_ENGAGE_ROTATION_DEG * _step / _LEV_SWEEP_STEPS
    _t = math.radians(_angle)
    _u = (-math.sin(_t), math.cos(_t))
    _foot = _LEV_REL[0] * _u[0] + _LEV_REL[1] * _u[1]
    if 0.0 <= _foot <= LEVER_LEN:
        _d = abs(_LEV_REL[0] * _u[1] - _LEV_REL[1] * _u[0])
    else:
        _end = min(max(_foot, 0.0), LEVER_LEN)
        _d = math.hypot(
            _LEV_REL[0] - _end * _u[0],
            _LEV_REL[1] - _end * _u[1],
        )
    if _d < (_ARBOR_DIA_AT_LEVER + LEVER_ROD_DIA) / 2.0 + 0.25:
        raise AssertionError("lever shaft crowds the arbor mid-throw")
_LEV_Z = _LEV_ROD_Z  # rod plane through the throw
if (
    _LEV_Z[0] < BLOCK_FRONT_Z0 + BLOCK_DEPTH + 0.25
    and _LEV_Z[1] > BLOCK_FRONT_Z0 - 0.25
):
    raise AssertionError("lever throw plane reaches the front pivot block")
if _LEV_Z[1] > PIVOT_SHAFT_Z0 - 0.25:
    raise AssertionError("lever throw plane reaches the pivot shaft front end")
if _LEV_Z[0] < _GRIP_HEAD_Z[1] + 0.25:
    raise AssertionError("lever throw plane reaches the integral grip head")

# Worst-case travel of the parts whose clearances RIG_MARGINS reads (Main,
# restricted review of #858, P2-3: the table claims worst case, so no row
# may read the nominal pose).  The pose is the drilling set-up -- cluster and
# drum hard back, both collars set -- so from it the arbor can only move
# south by the drum's advance or north by its retreat (it is bonded at the
# drum's front end), the lift rod floats between its two collar stops, and
# the pinned torque shaft runs forward with the cluster.  Each part adds the
# printed bands that station its face; frame-side faces (the T12, the crank
# arm) are their own assemblies' stations.
def _upper(value: float, places: int) -> float:
    return printed_deviations(value, places)[1]


def _lower(value: float, places: int) -> float:
    return -printed_deviations(value, places)[0]


ARBOR_SOUTH_TRAVEL_STACK = {
    **RIG.DRUM_BACK_ADVANCE_STACK,
    "MHA-DT-001 drum length .X (longest)": _upper(RIG.DRUM_LEN, RIG.DRUM_LEN_PLACES),
    "MHA-DT-022 drum station .X (deepest)": ARBOR_DRUM_STATION_BAND,
}
ARBOR_NORTH_TRAVEL_STACK = {
    **RIG.DRUM_FRONT_RETREAT_STACK,
    "MHA-DT-022 drum station .X (shallowest)": ARBOR_DRUM_STATION_BAND,
}


LEVER_SOUTH_TRAVEL_STACK = RIG.LEVER_SOUTH_TRAVEL_STACK
LEVER_NORTH_TRAVEL_STACK = RIG.LEVER_NORTH_TRAVEL_STACK
SHAFT_FRONT_SOUTH_TRAVEL_STACK = RIG.SHAFT_FRONT_SOUTH_TRAVEL_STACK
# The rig layout sizes MHA-DT-017 from the lever's nominal throw plane; the pose
# must put it there.
if abs(_LEV_Z[1] - (LIFT_ROD_Z0 + RIG.LEVER_PLANE_NORTH_FROM_ROD_END)) > 1e-9:
    raise AssertionError("the lever throw plane drifted from the rig layout's")
GRIP_ROD_SOUTH_TRAVEL_STACK = {
    **ARBOR_SOUTH_TRAVEL_STACK,
    "MHA-DT-022 head length .X, half (crossrod centred)": _upper(
        ARBOR_HEAD_LEN, ARBOR_HEAD_LEN_PLACES
    )
    / 2.0,
    "MHA-DT-015 crossrod dia, half": HANDLE_ROD_DIA_BAND[0] / 2.0,
}
GRIP_HEAD_SOUTH_TRAVEL_STACK = {
    **ARBOR_SOUTH_TRAVEL_STACK,
    "MHA-DT-022 head length .X": _upper(ARBOR_HEAD_LEN, ARBOR_HEAD_LEN_PLACES),
    "MHA-DT-022 front crown sag .X": _upper(
        ARBOR_HEAD_CAP_SAG, ARBOR_HEAD_CAP_SAG_PLACES
    ),
}
GRIP_HEAD_NORTH_TRAVEL_STACK = {
    **ARBOR_NORTH_TRAVEL_STACK,
    "MHA-DT-022 neck length .XX": _upper(ARBOR_NECK_LEN, ARBOR_NECK_LEN_PLACES),
}
# TODO(#743): the bank retention replaces the Ø55 end discs (MHA-DT-026) with
# Ø25 x 1.50 steel thrust washers, so this row changes or retires with it
# (retention743 owns the update).
# Radial: the widest drum tip against the largest end disc, which has no
# sheet and so carries the title block's general .X row on its diameter.
DRUM_TIP_TO_END_DISC_STACK = {
    "MHA-DT-001 critical tip, half": (
        _ALIGNMENT_PINION.outside_dia_limits_mm()[1] / 2.0 - TIP_APINION
    ),
    "end disc dia, general .X, half": _upper(END_DISC_DIA, 1) / 2.0,
}


# Axial: the return spring's strip against gear j = 19.  The back block is
# spotted with the strap between it and the drum, whose back end the rig-set
# leaf D stands off j = 19's back face; the pad is set its leaf off the block
# with the strip's aft edge flush (pinion_rig_layout).  Each term moves the
# strip's front edge south, toward the gear.
SPRING_TO_J19_STACK = {
    "rig-set leaf D, thinnest setting": RIG.FEELER_SET_ERROR,
    "MHA-DT-014 strap thickness .X, thinnest": _lower(STRAP_T, STRAP_T_PLACES),
    "spring pad leaf, thickest setting": RIG.FEELER_SET_ERROR,
    "MHA-DT-024 strip width .XX, widest": _upper(SPRING_W, SPRING_W_PLACES),
}


def _worst(nominal: float, *stacks: dict[str, float]) -> float:
    return nominal - sum(sum(stack.values()) for stack in stacks)


# The novice-margin rule (Main, restricted review of #858): every rig-scope
# margin -- the fit-up stacks, the drum's gears and end play, and each
# clearance the rig's axial stations set against its neighbours -- stands at
# least RIG_MARGIN_SPARE over its floor.  name -> (worst value, floor).
RIG_MARGINS = {
    "j = 19 past its full face (bank pushed north)": (J19_FULL_FACE_MARGIN, 0.0),
    "j = 0 drum overhang slack (rig and bank terms)": (J0_SLACK_WORST, 0.0),
    "torque shaft bearing in the front block": (
        sum(RIG.TORQUE_SHAFT_BEARING_STACK.values()),
        RIG.FRONT_BLOCK_MIN_BEARING,
    ),
    "torque shaft bearing in the back block": (
        sum(RIG.TORQUE_SHAFT_BACK_BEARING_STACK.values()),
        RIG.BACK_BLOCK_MIN_BEARING,
    ),
    "lift rod seat past the front block": (
        sum(RIG.LIFT_ROD_SEAT_STACK.values()),
        RIG.LEVER_SEAT_MIN,
    ),
    "drum end play": (ARBOR_DRUM_TOTAL_AIR()[0], ARBOR_MIN_END_PLAY),
    "MHA-DT-022 journal land over its strap": (
        min(min(stop.values()) for stop in ARBOR_LAND_MARGINS_AT_STOPS.values()),
        ARBOR_MIN_LAND_OVER_STRAP,
    ),
    "back collar to the back block": (RIG.BACK_COLLAR_GAP_MIN, RIG.BACK_COLLAR_MIN_GAP),
    "spring blade on the back strap flank": (
        RIG.SPRING_BLADE_ON_FLANK_WORST,
        RIG.SPRING_BLADE_MIN_ON_FLANK,
    ),
    "spring foot pad to the back block": (
        RIG.SPRING_PAD_TO_BLOCK_WORST,
        RIG.SPRING_PAD_MIN_AIR,
    ),
    "spring strip to gear j = 19": (
        _worst(SPRING_Z - SPRING_W / 2.0 - RIG.G19_BACK_FACE_Z, SPRING_TO_J19_STACK),
        0.25,
    ),
    # Axial against the crank sprocket plate, the widest crank-column body. Worst-case
    # travel does enter the collar/washer band behind it; those are cleared
    # radially instead (CRANK_COLUMN_BANDS above).
    "grip crossrod to the crank chain wheel": (
        _worst(_GRIP_ROD_Z[0] - REMOVABLE.SEAT_FACE_Z, GRIP_ROD_SOUTH_TRAVEL_STACK),
        0.25,
    ),
    "grip head to the crank arm": (
        _worst(
            _GRIP_HEAD_Z[0] - (CRANK_ARM_Z0 + ARM_THICKNESS),
            GRIP_HEAD_SOUTH_TRAVEL_STACK,
        ),
        0.25,
    ),
    "lever throw plane to the grip head": (
        _worst(
            _LEV_Z[0] - _GRIP_HEAD_Z[1],
            LEVER_SOUTH_TRAVEL_STACK,
            GRIP_HEAD_NORTH_TRAVEL_STACK,
        ),
        0.25,
    ),
    "lever throw plane to the torque shaft's front end": (
        _worst(
            PIVOT_SHAFT_Z0 - _LEV_Z[1],
            LEVER_NORTH_TRAVEL_STACK,
            SHAFT_FRONT_SOUTH_TRAVEL_STACK,
        ),
        0.25,
    ),
    "engaged drum tips to the north end disc": (
        _worst(
            ENGAGED_C2C - TIP_APINION - END_DISC_DIA / 2.0,
            DRUM_TIP_TO_END_DISC_STACK,
        ),
        0.25,
    ),
}
_THIN = {
    name: (value, floor)
    for name, (value, floor) in RIG_MARGINS.items()
    if value < floor + RIG.RIG_MARGIN_SPARE - 1e-9
}


def rig_margin_lines() -> list[str]:
    """One line per RIG_MARGINS row: worst value, floor and spare over the
    floor + RIG_MARGIN_SPARE requirement, for the build log."""
    return [
        f"{name}: worst {value:.3f}, floor {floor:g}, "
        f"spare {value - floor - RIG.RIG_MARGIN_SPARE:+.3f}"
        for name, (value, floor) in RIG_MARGINS.items()
    ]


if _THIN:
    raise AssertionError(
        "rig margins under their floor + RIG_MARGIN_SPARE: "
        + "; ".join(f"{n} {v:.3f} (floor {f})" for n, (v, f) in _THIN.items())
    )

# (The PR5 rod-pin throw checks died with the pins; the cam block above
# bounds the collar sweep against the base and shaft.)

# The MHA-DT-033 collar rides the arbor outboard of the front strap.  It must
# stand clear of the strap's outer face (the printed-band stack lives in
# dt_pinion_arbor_collar_spec) and of every rig body whose z band it shares:
# the lift rod and pivot shaft by radial distance between parallel axes (the
# front pivot block, by height, once BLOCK_TOP_Y is derived below).
if ARBOR_COLLAR_Z[1] > RIG.STRAP_Z_OUTER[0] - 0.25:
    raise AssertionError("arbor collar reaches the front strap's outer face")
if ARBOR_COLLAR_Z[0] < _GRIP_HEAD_Z[1] + 0.25:
    raise AssertionError("arbor collar reaches the integral grip head's neck")
for _lo, _hi, _axis_xy, _r, _what in (
    (LIFT_ROD_Z0, LIFT_ROD_Z0 + RIG.LIFT_ROD_LEN, (LIFT_X, LIFT_Y), 3.175, "lift rod"),
    (
        PIVOT_SHAFT_Z0,
        PIVOT_SHAFT_Z0 + RIG.TORQUE_SHAFT_LEN,
        (PIVOT_X, PIVOT_Y),
        3.175,
        "pivot shaft",
    ),
):
    if _hi < ARBOR_COLLAR_Z[0] - 0.25 or _lo > ARBOR_COLLAR_Z[1] + 0.25:
        continue
    if (
        math.hypot(_axis_xy[0] - APINION_X, _axis_xy[1] - APINION_Y)
        < ARBOR_COLLAR_OD / 2.0 + _r + 0.25
    ):
        raise AssertionError(f"arbor collar crowds the {_what}")

# --- pinion arbor + rig fasteners (PR7 items 2/11/12/14) ---------------------
# The steel Ø8 arbor slips through the drum (bonded) and journals in both
# straps' top bores.  Its turned head/neck are integral; MHA-DT-015 is only the
# separate crossrod, bonded into the head's reamed hole at the unchanged
# head/cross-hole station.
if abs(HANDLE_Z - (ARBOR_Z0 + ARBOR_HEAD_CENTER_Z)) > 1e-9:
    raise AssertionError("grip crossrod is not centred in the integral head")
# MHA-DT-022 runs in the straps on its two journal lands, so each land must
# cover its strap in the pose, past both faces (the worst case over every
# printed band and both drum stops is dt_pinion_arbor_geometry's own stack).
for _land_z, _strap_faces, _which in (
    (ARBOR_FRONT_JOURNAL_Z, (RIG.STRAP_Z_OUTER[0], RIG.STRAP_Z_INNER[0]), "front"),
    (ARBOR_BACK_JOURNAL_Z, (RIG.STRAP_Z_INNER[1], RIG.STRAP_Z_OUTER[1]), "back"),
):
    _land = (ARBOR_Z0 + _land_z, ARBOR_Z0 + _land_z + ARBOR_JOURNAL_LEN)
    if min(_strap_faces[0] - _land[0], _land[1] - _strap_faces[1]) < (
        ARBOR_MIN_LAND_OVER_STRAP - 1e-9
    ):
        raise AssertionError(f"MHA-DT-022's {_which} journal land misses its strap")
if not (ARBOR_DIA == DRUM_BORE_DIA == STRAP_ARBOR_BORE):
    raise AssertionError("arbor dia disagrees with drum and strap bores")
# R1: the crossrod is a bonded slip fit, modelled line to line.  Its printed
# limits (rod enters, gap inside Loctite 638) are dt_pinion_arbor_spec's asserts;
# the assembly only needs the shared nominal it places both parts at.
if abs(HANDLE_ROD_DIA - ARBOR_CROSS_HOLE_DIA) > 1e-9:
    raise AssertionError("grip crossrod and head hole no longer share a nominal")
if abs(STRAP_PIVOT_BORE - 6.35) > 1e-9:
    raise AssertionError("strap pivot bore no longer rides the O6.35 shaft")
# Block screws: the catalog-owned #8-32 fully threaded stock screws pass
# through normal #8 clearance holes. Engagement follows the current raised
# block height and the matching blind base seat, not the retired stock length.
BLOCK_TOP_Y = PIVOT_Y + (BLOCK_HEIGHT - BLOCK_BORE_UP)
_require_clearance_size("pinion block", BSCREW_THREAD, BLOCK_SCREW_HOLE_SPEC)
_require_tapped_thread(
    "pinion block base seat",
    BSCREW_THREAD,
    BASE_BLOCK_SEAT_SPEC,
    kind="tapped_bottoming",
)
_BLOCK_SCREW_ENGAGEMENT = BSCREW_SHANK_LEN - BLOCK_HEIGHT
if _BLOCK_SCREW_ENGAGEMENT < 1.0:
    raise AssertionError("block screw barely engages the base")
if _BLOCK_SCREW_ENGAGEMENT > BASE_BLOCK_HOLE_DEPTH - 0.25:
    raise AssertionError("block screw bottoms out in the base tapped seat")
if (
    BLOCK_SCREW_HALF + BSCREW_HEAD_DIA / 2.0
    > min(BLOCK_EAST, BLOCK_WIDTH - BLOCK_EAST) - 0.25
):
    raise AssertionError("block screw head overhangs the block end")
_BLOCK_SCREW_XZ = tuple(
    (BLOCK_X + sx, z0 + BLOCK_DEPTH / 2.0)
    for z0 in (BLOCK_FRONT_Z0, BLOCK_BACK_Z0)
    # east screw first (-x), preserving the mirrored-era instance order
    for sx in (-BLOCK_SCREW_HALF, BLOCK_SCREW_HALF)
)
# Both machine-handed: the base holes agree directly.
for _want, _have in zip(_BLOCK_SCREW_XZ, BASE_BLOCK_XZ, strict=True):
    if abs(_want[0] - _have[0]) > 0.05 or abs(_want[1] - _have[1]) > 0.05:
        raise AssertionError(
            f"harmonic-base block-screw hole {_have} != machine derived "
            f"({_want[0]:.3f}, {_want[1]:.3f})"
        )
# I31 swing sweep, the base-fixed occupants (Main, reviews of 0c1e615c0 and
# 7240ae0de).  Whatever stands on a base seat keeps
# SWING_SEAT_RUNNING_CLEARANCE -- the drive train's 2.0 design margin, as the
# south arbor pedestal and the swing stop keep -- off the swinging plate's
# plan outline at every SWING_ANGLES sample.  The part standing on a seat,
# not the screw holding it, is what the plate could hit, so each is checked
# by its plan footprint; only the column tube, round in its socket, keeps a
# radius.  Plan-only, so conservative whatever the heights.  The pivot,
# lock-knob and stop seats meet the plate by design and are proven with their
# hardware; the arbor pedestals are the blocks proven above.
SWING_SEAT_RUNNING_CLEARANCE = 2.0
SWING_COARSE = 10
# The plate's farthest plan point from its pivot: a vertex of its outline.
_SWING_REACH = max(math.hypot(x, z) for x, z in _PLATFORM_VERTICES)


def _plan_box(x0: float, x1: float, z0: float, z1: float) -> tuple[Plan, ...]:
    return ((x0, z0), (x1, z0), (x1, z1), (x0, z1))


# The spring's formed profile, foot end to flick tip, one strip thickness
# wider each way.  Across z the foot pad is the widest part, flush with the
# strip's aft edge and widening forward only (pinion_rig_layout).
_SPRING_PLAN_X = tuple(
    SPRING_X - local[0]
    for local in (
        SPR_FOOT_END_L,
        SPR_FOOT_TAN_L,
        SPR_BEND_EXIT_L,
        SPR_KINK_START_L,
        SPR_KINK_C_L,
        SPR_CREST_L,
        SPR_FLAT_TIP_L,
    )
)
_SPRING_Z_BAND = (
    RIG.SPRING_PAD_AFT_Z - max(RIG.SPRING_PAD_WIDTH, SPRING_W),
    RIG.SPRING_PAD_AFT_Z,
)
_PIVOT_BLOCK_X = (PIVOT_X - BLOCK_EAST, PIVOT_X - BLOCK_EAST + BLOCK_WIDTH)
SWING_FOOTPRINTS: dict[str, tuple[Plan, ...]] = {
    # The support's trapezoid is widest at its foot (x +-WIDE, z +-88.9).
    "rocker-arm support": _plan_box(
        _SUPPORT_X - _SUPPORT_FOOT_HALF_X,
        _SUPPORT_X + _SUPPORT_FOOT_HALF_X,
        _SUPPORT_Z - _SUPPORT_FOOT_HALF_Z,
        _SUPPORT_Z + _SUPPORT_FOOT_HALF_Z,
    ),
    "front pivot block": _plan_box(
        *_PIVOT_BLOCK_X, BLOCK_FRONT_Z0, BLOCK_FRONT_Z0 + BLOCK_DEPTH
    ),
    "back pivot block": _plan_box(*_PIVOT_BLOCK_X, BLOCK_BACK_Z0, BLOCK_BACK_Z0 + BLOCK_DEPTH),
    "pinion spring": _plan_box(
        min(_SPRING_PLAN_X) - SPRING_T,
        max(_SPRING_PLAN_X) + SPRING_T,
        *_SPRING_Z_BAND,
    ),
    "nameplate": tuple(
        (corner[0], corner[2])
        for corner in (
            nameplate_mount_point((u, v, 0.0))
            for u, v in (
                (0.0, 0.0),
                (NAMEPLATE_WIDTH, 0.0),
                (NAMEPLATE_WIDTH, NAMEPLATE_HEIGHT),
                (0.0, NAMEPLATE_HEIGHT),
            )
        )
    ),
    # The stamp's glyph is narrower than it is tall.
    "serial stamp": _plan_box(
        BASE_SERIAL_XZ[0] - BASE_SERIAL_HEIGHT / 2.0,
        BASE_SERIAL_XZ[0] + BASE_SERIAL_HEIGHT / 2.0,
        BASE_SERIAL_XZ[1] - BASE_SERIAL_HEIGHT / 2.0,
        BASE_SERIAL_XZ[1] + BASE_SERIAL_HEIGHT / 2.0,
    ),
}
SWING_ROUND_OCCUPANTS: dict[str, tuple[Plan, float]] = {
    f"column socket {i}": (xz, COLUMN_SOCKET_DIAMETER / 2.0)
    for i, xz in enumerate(BASE_COLUMN_SOCKET_XZ)
}
# Each footprint must cover the base seats that hold it down: a frame or
# sign slip would otherwise sweep the wrong rectangle.
SWING_OCCUPANT_SEATS: dict[str, tuple[Plan, ...]] = {
    "rocker-arm support": tuple(BASE_HOLE_XZ),
    "front pivot block": tuple(
        xz for xz in BASE_BLOCK_XZ if BLOCK_FRONT_Z0 <= xz[1] <= BLOCK_FRONT_Z0 + BLOCK_DEPTH
    ),
    "back pivot block": tuple(
        xz for xz in BASE_BLOCK_XZ if BLOCK_BACK_Z0 <= xz[1] <= BLOCK_BACK_Z0 + BLOCK_DEPTH
    ),
    "pinion spring": tuple(BASE_FOOT_XZ),
    "nameplate": tuple(BASE_NAMEPLATE_XZ),
    "serial stamp": (BASE_SERIAL_XZ,),
}
for _occupant, _seats in SWING_OCCUPANT_SEATS.items():
    if len(_seats) == 0 or not all(
        _point_in_polygon(_seat, SWING_FOOTPRINTS[_occupant]) for _seat in _seats
    ):
        raise AssertionError(f"the {_occupant} footprint misses its base seats {_seats}")
if sum(len(_seats) for _seats in SWING_OCCUPANT_SEATS.values()) != (
    len(BASE_HOLE_XZ) + len(BASE_BLOCK_XZ) + len(BASE_FOOT_XZ) + len(BASE_NAMEPLATE_XZ) + 1
):
    raise AssertionError("a base seat is claimed by no swing occupant, or by two")


def swing_occupant_clearances(
    footprints: dict[str, tuple[Plan, ...]],
    round_occupants: dict[str, tuple[Plan, float]],
) -> dict[str, tuple[float, float]]:
    """Each occupant's least plan clearance to the swinging plate over
    SWING_ANGLES, and the swing angle (deg) where it occurs.

    The plate turns about its pivot, so no plate point moves faster than
    _SWING_REACH mm per radian and the gap between samples a and b cannot
    dip below (g(a) + g(b) - reach * (b - a)) / 2.  Every SWING_COARSE-th
    sample is evaluated first; an interval is filled in only while that
    bound could still undercut the least gap found -- the same minimum as
    evaluating every sample, at a fraction of the import time."""

    def gap_at(name: str, k: int) -> float:
        swing = SWING_ANGLES[k]
        if name in footprints:
            return _plan_gap_polygons(plate_vertices_machine(swing), footprints[name])
        xz, radius = round_occupants[name]
        return _plan_gap_to_plate(xz, swing) - radius

    reach = _SWING_REACH * math.radians(SWING_ANGLES[1] - SWING_ANGLES[0])
    coarse = list(range(0, len(SWING_ANGLES), SWING_COARSE))
    if coarse[-1] != len(SWING_ANGLES) - 1:
        coarse.append(len(SWING_ANGLES) - 1)
    worst: dict[str, tuple[float, float]] = {}
    for name in (*footprints, *round_occupants):
        gaps = {k: gap_at(name, k) for k in coarse}
        least = min(gaps.values())
        for a, b in zip(coarse, coarse[1:]):
            if (gaps[a] + gaps[b] - reach * (b - a)) / 2.0 >= least:
                continue
            for k in range(a + 1, b):
                gaps[k] = gap_at(name, k)
                least = min(least, gaps[k])
        k = min(sorted(gaps), key=gaps.__getitem__)
        worst[name] = (gaps[k], SWING_ANGLES[k])
    return worst


def require_swing_clearance(
    footprints: dict[str, tuple[Plan, ...]],
    round_occupants: dict[str, tuple[Plan, float]],
) -> dict[str, tuple[float, float]]:
    """swing_occupant_clearances, failing loud below SWING_SEAT_RUNNING_CLEARANCE."""
    worst = swing_occupant_clearances(footprints, round_occupants)
    for name, (gap, swing) in worst.items():
        if gap < SWING_SEAT_RUNNING_CLEARANCE:
            raise AssertionError(
                f"swing plate within {gap:.3f} of the {name} at swing {swing:.3f} "
                f"deg (needs >= {SWING_SEAT_RUNNING_CLEARANCE})"
            )
    return worst


SWING_OCCUPANT_CLEARANCE = require_swing_clearance(SWING_FOOTPRINTS, SWING_ROUND_OCCUPANTS)
SWING_NEAREST_OCCUPANT: tuple[float, str] = min(
    (gap, name) for name, (gap, _swing) in SWING_OCCUPANT_CLEARANCE.items()
)
# The MHA-DT-033 collar can share the front pivot block's z band; its underside
# must then clear the block's flat top.
if (
    BLOCK_FRONT_Z0 < ARBOR_COLLAR_Z[1] + 0.25
    and BLOCK_FRONT_Z0 + BLOCK_DEPTH > ARBOR_COLLAR_Z[0] - 0.25
    and APINION_Y - ARBOR_COLLAR_OD / 2.0 < BLOCK_TOP_Y + 0.25
):
    raise AssertionError("arbor collar sits on the front pivot block")
# The exact 90280A108 #4-40 x 9.525 stock screw passes through the spring's
# normal #4 clearance into the base's #4-40 UNC-2B seat.
_require_clearance_size("pinion spring foot", FSCREW_THREAD, SPR_HOLE_SPEC)
_require_tapped_thread(
    "foot-screw base seat", FSCREW_THREAD, BASE_FOOT_SEAT_SPEC, kind="tapped_bottoming"
)
# The thinnest strip lets the screw deepest.  The base sizes the seat from
# the same stock band, so its 0.25 tip reserve holds line to line.
if BASE_FOOT_HOLE_DEPTH - (FSCREW_SHANK_LEN - _SPR_T_LO) < 0.25 - 1e-9:
    raise AssertionError("foot screw bottoms out in the base spring seat")
_FOOT_SCREW_XZ = ((SPRING_HOLE_X, RIG.SPRING_PAD_Z),)
# U34c: one MHA-VN-032 (90280A197 #8-32 x 3/4) per pedestal, through the ledge's
# #8 close clearance into a base seat transferred from the fitted pedestal.
_require_clearance_size("arbor pedestal ledge", HDSCREW_THREAD, ARBOR_PED_HOLE_SPEC)
_require_tapped_thread(
    "pedestal hold-down base seat",
    HDSCREW_THREAD,
    BASE_PEDESTAL_SEAT_SPEC,
    kind="tapped_bottoming",
)
# Rule 12 (audit E15): at the printed worst case (flange 5.0 +-0.8, screw
# 19.05 +0/-0.76, seat depths +-0.8) the screw keeps >= 1.5D of thread and
# never reaches the incomplete threads at the bottom of the seat.
_HDSCREW_MIN_ENGAGEMENT = (HDSCREW_SHANK_LEN - 0.76) - (ARBOR_PED_FLANGE_T + 0.8)
_HDSCREW_MAX_REACH = HDSCREW_SHANK_LEN - (ARBOR_PED_FLANGE_T - 0.8)
if _HDSCREW_MIN_ENGAGEMENT < 1.5 * HDSCREW_SHANK_DIA:
    raise AssertionError("pedestal hold-down keeps under 1.5D of thread at worst case")
if _HDSCREW_MAX_REACH + 0.25 > BASE_PEDESTAL_HOLE_DEPTH - 0.8:
    raise AssertionError("pedestal hold-down reaches the seat's incomplete threads")
# The head sits on the 18 ledge, clear of the strap root and the ledge end.
if HDSCREW_HEAD_DIA / 2.0 > min(
    ARBOR_PED_SCREW_Z - ARBOR_PED_FOOT_NEAR_Z,
    ARBOR_PED_STRAP_ROOT_Z - ARBOR_PED_SCREW_Z,
):
    raise AssertionError("pedestal hold-down head overhangs the ledge")
_PEDESTAL_SCREW_XZ = (
    (X_DRUM, -ARBOR_PEDESTAL_Z + ARBOR_PED_SCREW_Z),  # -91.652
    # North pedestal (Ry180 flips its ledge to +z): origin - SCREW_Z.
    (X_DRUM, ARBOR_PEDESTAL_NORTH_Z - ARBOR_PED_SCREW_Z),  # +94.202
)

# Both machine-handed: the base holes agree directly.
for _label, _derived, _base in (
    ("vn-foot-screw", _FOOT_SCREW_XZ, BASE_FOOT_XZ),
    ("pedestal hold-down", _PEDESTAL_SCREW_XZ, BASE_PEDESTAL_XZ),
):
    for _want, _have in zip(_derived, _base, strict=True):
        if abs(_want[0] - _have[0]) > 0.05 or abs(_want[1] - _have[1]) > 0.05:
            raise AssertionError(
                f"harmonic-base {_label} hole {_have} != machine derived "
                f"({_want[0]:.3f}, {_want[1]:.3f})"
            )


IDENTITY = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
CRANK_HUB_PIN_ROWS = IDENTITY
ROT_X_POS90 = [[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, -1.0, 0.0]]
ROT_Y_POS90 = [[0.0, 0.0, -1.0], [0.0, 1.0, 0.0], [1.0, 0.0, 0.0]]
# Cam-follower pin pose (PR8): part +Z (root -> dome) -> WEST along -N,
# part +Y -> up the strap line (_SPR_U), part +X = Y x Z = machine -z.
# The part origin (the seated root face) lands at the blind seat's bottom,
# _FPIN_S0 out from the strap centreline along -N.
FPIN_ROWS = [
    [0.0, 0.0, -1.0],
    [_SPR_U[0], _SPR_U[1], 0.0],
    [-_SPR_N[0], -_SPR_N[1], 0.0],
]
FPIN_EULER = euler_from_rows(FPIN_ROWS)
_FPIN_ORG = (_FPIN_C[0] - _FPIN_S0 * _SPR_N[0], _FPIN_C[1] - _FPIN_S0 * _SPR_N[1])
ROT_Y_INCLINE = [
    [COS_I, 0.0, -SIN_I],
    [0.0, 1.0, 0.0],
    [SIN_I, 0.0, COS_I],
]  # Ry(+INCLINE), row-vector convention (matches the frame script's Ry rows)
# The tip-stack riders are authored along +Y (Top-plane extrusions); these lay
# that +Y axis along the inclined plate frame (same row-vector convention).
ROT_SHAFT_NORTH = [  # +Y -> the increasing-station shaft direction (tip collar)
    [COS_I, 0.0, -SIN_I],
    [SIN_I, 0.0, COS_I],
    [0.0, -1.0, 0.0],
]
ROT_SHAFT_SOUTH = [  # +Y -> the decreasing-station direction (adjuster: head north)
    [COS_I, 0.0, -SIN_I],
    [-SIN_I, 0.0, -COS_I],
    [0.0, 1.0, 0.0],
]
# The fillister screw is authored head up (+Y), its under-head face at y = 0.
# The block's clearance hole is drilled from its +X face, which the plate
# frame puts on machine WEST (dt_cone_swing_platform_geometry's local-frame
# convention), so the head seats there and the shank runs east into the far
# jaw's thread.
ROT_PINCH_WEST = [  # +Y (head) -> plate-frame +X (west)
    [0.0, 1.0, 0.0],
    [COS_I, 0.0, -SIN_I],
    [-SIN_I, 0.0, -COS_I],
]
PINCH_WEST_EULER = euler_from_rows(ROT_PINCH_WEST)
# MHA-VN-030 is authored head up along +Y; Rx(180) turns it head down under the
# platform (it is a revolved screw, so its spin is immaterial).
ROT_X_180 = [[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]]
HOLDDOWN_HEAD_DOWN_EULER = euler_from_rows(ROT_X_180)


def rot_z_rows(deg: float) -> list[list[float]]:
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [[c, s, 0.0], [-s, c, 0.0], [0.0, 0.0, 1.0]]


# MHA-DT-030 is match-drilled through the lever hub and the lift rod at assembly,
# so both pin holes share one axis.  Each part cuts its hole along its own
# local X; the lever is photographed at LEVER_TILT_DEG, so the ROD is phased to
# the lever (the rod is round: its phase is free and never printed) and the
# lever clamps parallel to it.  The cams keep their world phase (ecc straight
# down) through an angle tie of the same LEVER_TILT_DEG back off the rod.
LIFT_ROD_ROWS = rot_z_rows(LEVER_TILT_DEG)
# Option E-a: the torque shaft's pin holes run along its local X, which must
# lie along the straps' cross holes (their local X after Ry(180) . Rz(lean)).
TORQUE_SHAFT_ROWS = rot_z_rows(STRAP_LEAN_DEG)
# The straps extrude local +z, so their machine-handed pose composes a
# Ry(180) with the lean, and each part origin sits on the strap's north face.
STRAP_ROWS = compose_rows(ROT_Y_180, rot_z_rows(STRAP_LEAN_DEG))
STRAP_ORIGIN_Z = (RIG.STRAP_Z_INNER[0], RIG.STRAP_Z_OUTER[1])  # (front, back)
# Option E-a set pins (MHA-VN-033, pinion-strap-pin): each strap cuts its cross
# hole along its local X through the pivot-bore axis, CROSS_HOLE_CZ from its
# part origin (build_dt_pinion_bracket).  The torque shaft's holes are
# match-drilled through those cross holes at the fit-up stack, which this pose
# is, so each pin runs straight through its shaft hole (Codex #858 P1: a
# straight pin cannot pass offset holes, and no interference row may pretend
# it does).  LOCKSTEP GUARD (Main, restricted review of #858): each cross hole
# is taken from the strap part as placed, each shaft hole from the stations
# the shaft part cuts, so a strap placement, a cross-hole station or a shaft
# station that drifts from the others fails here.
STRAP_CROSS_HOLE_Z = tuple(
    z0 + STRAP_CROSS_HOLE_CZ * STRAP_ROWS[2][2] for z0 in STRAP_ORIGIN_Z
)
STRAP_PIN_Z = STRAP_CROSS_HOLE_Z
for _z_strap, _z_hole in zip(
    STRAP_CROSS_HOLE_Z, RIG.TORQUE_SHAFT_PIN_HOLE_Z, strict=True
):
    if abs(PIVOT_SHAFT_Z0 + _z_hole * TORQUE_SHAFT_ROWS[2][2] - _z_strap) > 1e-9:
        raise AssertionError("a strap cross hole is not coaxial with its torque-shaft hole")
LEVER_ROWS = rot_z_rows(LEVER_TILT_DEG)
# R1a: the MHA-DT-033 collar's spring pin is the stock MHA-VN-033, whose axis is its
# local X.  The collar's and MHA-DT-022's pin holes run along their local +Y
# under ARBOR_ROWS, so the pin turns a further 90 about Z; its centre is the
# arbor's printed pin station, where the collar's centred hole lands.
COLLAR_PIN_ROWS = rot_z_rows(HANDLE_TILT_DEG + 90.0)
COLLAR_PIN_Z = ARBOR_COLLAR_Z0 + ARBOR_COLLAR_PIN_Z
if any(abs(a - b) > 1e-9 for a, b in zip(COLLAR_PIN_ROWS[0], ARBOR_ROWS[1])):
    raise AssertionError("collar spring pin axis is not the arbor's pin-hole axis")
if abs(COLLAR_PIN_Z - (ARBOR_Z0 + ARBOR_PIN_Z)) > 1e-9:
    raise AssertionError("collar pin hole is off the arbor's pin station")
PINION_CAM_ROWS = IDENTITY
# Rod Top-plane normal (local +Y) against the assembly Right normal (+X): the
# freed pinion_cam spin's rest dihedral -- 90 + LEVER_TILT_DEG.
LIFT_ROD_PARK_DEG = math.degrees(math.acos(LIFT_ROD_ROWS[1][0]))
# Cam Right-plane normal against the rod's: the set-pin phase.
CAM_ROD_PHASE_DEG = math.degrees(
    math.acos(sum(a * b for a, b in zip(PINION_CAM_ROWS[0], LIFT_ROD_ROWS[0])))
)


def _org(adapter, name: str) -> list[float]:
    """A component's current origin (mm) in the assembly frame."""
    a = component_transform(adapter, name)
    return [a[9] * 1000.0, a[10] * 1000.0, a[11] * 1000.0]


async def _lock_static(adapter, name: str, reference: str) -> None:
    """Rigidly retain an authored static pose with one mate.

    These base-bolted mounts have no contact partner inside this subassembly.
    Their exact machine-frame transform is already authored at insertion, so
    three assembly-datum distance mates only make the solver rediscover six
    coordinates it already has. Locking each mount to the fixed seed arbor
    preserves the same relative transform in one branch-free relationship.
    """
    await lock_mate(
        adapter,
        named_ref(f"Front Plane@{name}", "PLANE"),
        named_ref(f"Front Plane@{reference}", "PLANE"),
        label=f"{name} fixed to static reference",
    )


async def _key_to_shaft(
    adapter,
    part,
    part_axis,
    shaft_axis_ref,
    shaft,
    shaft_o,
    axis_dir,
    label,
    *,
    seat_plane: str = "",
) -> None:
    """Key a gear rigidly onto a shaft via SEMANTIC mates, replacing a lock:
    coaxial (collinear axes) + an axial seat + a parallel anti-spin. The gear
    and shaft share the inclined orientation (ROT_Y_INCLINE), so their Right
    planes are parallel at the keyed phase -- the parallel pins the spin with
    no tuned angle (the lag-screw idiom). Removes the same 6 DOF the lock did;
    no fix/lock.  On the cone shaft the parallel IS the D-flat (user ruling
    2026-09-28): every gear land's flat and every cone-gear/64T D-bore flat
    face outward on their part's local +X, the Right-plane normal, so the
    mate states the physical joint; a gear flipped 180 deg would put its flat
    into the land, which the interference gate catches.  The seat is a
    Front-plane distance along the shaft axis (read live) unless
    ``seat_plane`` names the shaft plane the gear's south face sits ON (see
    :func:`_axial_seat`)."""
    p_o = _org(adapter, part)
    await coincident_mate(
        adapter,
        named_ref(f"{part_axis}@{part}", "AXIS"),
        shaft_axis_ref,
        label=f"{label} coaxial",
        verify=(part, p_o),
    )
    await _axial_seat(adapter, part, shaft, shaft_o, axis_dir, p_o, label, seat_plane)
    await parallel_mate(
        adapter,
        named_ref(f"Right Plane@{part}", "PLANE"),
        named_ref(f"Right Plane@{shaft}", "PLANE"),
        label=f"{label} anti-spin",
        verify=(part, p_o),
    )


async def _axial_seat(
    adapter, part, shaft, shaft_o, axis_dir, p_o, label, seat_plane
) -> None:
    """A gear's axial seat on its shaft: contact with a named shaft plane (a
    gear located by a shoulder -- the 64T on the thrust collar, #914), else the
    Front-plane distance at its as-placed station."""
    if seat_plane:
        await coincident_mate(
            adapter,
            named_ref(f"Front Plane@{part}", "PLANE"),
            named_ref(f"{seat_plane}@{shaft}", "PLANE"),
            label=f"{label} axial seat on {seat_plane}",
            verify=(part, p_o),
        )
        return
    d_axial = sum((p_o[k] - shaft_o[k]) * axis_dir[k] for k in range(3))
    await distance_driver(
        adapter,
        named_ref(f"Front Plane@{part}", "PLANE"),
        named_ref(f"Front Plane@{shaft}", "PLANE"),
        d_axial,
        label=f"{label} axial seat d={d_axial:.2f}",
        verify=(part, p_o),
    )


async def _seat_on_crank(
    adapter,
    part,
    part_axis,
    crank_axis,
    crankshaft,
    seat_plane,
    alignment: str = "closest",
) -> list[float]:
    """Journal a keyed crank part with semantic mates.

    The part is coaxial on the crank axis and its Z-normal Front plane seats
    coincident to a named crankshaft datum (e.g. SeatPinion).  Coincident
    replaces the old UNSIGNED plane-plane distance, whose two solution branches
    let the free-spinning crank family reflect about the shaft origin on a
    re-solve: the 16T rendered floating ~200 south of its seat with every gate
    green (render-gate catch, 2026-07-04).  The seat must reference the
    crankshaft, NOT a world datum (a world plane pins the crank axis to machine
    z and through it the whole p1 swing).  The caller supplies the anti-spin,
    leaving only the shared crank rotation.  Returns the part's live origin.
    """
    o = _org(adapter, part)
    await coincident_mate(
        adapter,
        named_ref(f"{part_axis}@{part}", "AXIS"),
        crank_axis,
        label=f"{part} coaxial on crank",
        verify=(part, o),
    )
    await coincident_mate(
        adapter,
        named_ref(f"Front Plane@{part}", "PLANE"),
        named_ref(f"{seat_plane}@{crankshaft}", "PLANE"),
        label=f"{part} axial seat on {seat_plane} (coincident, flip-free)",
        alignment=alignment,
        verify=(part, o),
    )
    return o


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
            centre[0] - (face / 2.0) * SIN_I,
            Y_DRIVE,
            centre[2] - (face / 2.0) * COS_I,
        ],
        [0.0, INCLINE_DEG, 0.0],
        ROT_Y_INCLINE,
        ground=False,
        configuration=configuration,
        label=label,
    )


def _require_collar_pin_in_collar_hole(adapter, pin: str, collar: str) -> None:
    """The MHA-VN-033 tagged as the collar pin for the explode must be the one in
    the MHA-DT-033 collar's pin hole: its axis (local X) along the hole's (the
    collar's local +Y) and its centre on that axis.  A mislabelled instance
    fails here instead of leaving a strap pin with the arbor."""
    pin_t = component_transform(adapter, pin)
    collar_t = component_transform(adapter, collar)
    hole_axis = collar_t[3:6]
    if abs(abs(sum(a * b for a, b in zip(pin_t[0:3], hole_axis))) - 1.0) > 1e-6:
        raise AssertionError(f"{pin} does not lie along {collar}'s pin hole")
    hole_centre = [
        o + ARBOR_COLLAR_PIN_Z / 1000.0 * z
        for o, z in zip(collar_t[9:12], collar_t[6:9], strict=True)
    ]
    offset = [p - h for p, h in zip(pin_t[9:12], hole_centre, strict=True)]
    along = sum(d * a for d, a in zip(offset, hole_axis))
    off_axis = math.sqrt(max(sum(d * d for d in offset) - along * along, 0.0))
    if off_axis * 1000.0 > 1e-3:
        raise AssertionError(f"{pin} stands {off_axis * 1000.0:.4f} mm off {collar}'s pin hole")


async def build(adapter) -> dict[str, str]:
    # Flip seeds + free-DOF contract: cad/config/assemblies/<ASM_NAME>.yaml.
    activate_assembly_contract(ASM_NAME)
    # Reset the free-DOF manifest buffer before any *_driver(free_dof_key=...)
    # call: each freed DOF is recorded (never authored) and persisted below.
    reset_dof_manifest()
    for mesh_check in (*CONE_MESH_CHECKS, ALIGNMENT_MESH_CHECK, CRANK_MESH_CHECK):
        _telemetry.info("standard mesh check: " + mesh_check.text())
    for feature, clearance in GEAR64_POST_CLEARANCES.items():
        _telemetry.info(
            f"64T/restored post {feature}: worst clearance {clearance:.4f} "
            f">= {crank_boss_rim.FLOOR_CLEARANCE_MM:.2f} mm"
        )
    _telemetry.info(crank_mesh.stack_text())
    _telemetry.info(
        f"crank mesh actual centre distance {CRANK_ACTUAL_C2C:.6f} mm; "
        f"physical backlash reference {MESH16_C2C:.6f} mm"
    )
    _telemetry.info(
        f"16T/boss north-face feeler {_BOSS_NORTH_GAP:.4f} mm; "
        f"16T/T120 shoulder air {PINION_T120_CONCENTRIC['shoulder air']:.4f} >= "
        f"{T120_PINION_AIR_FLOOR:.2f} mm, turned band radial "
        f"{PINION_T120_CONCENTRIC['turned band radial']:.4f} >= "
        f"{T120_TURNED_BAND_RADIAL_FLOOR:.2f} mm on the nominal axes; at the worst fit "
        f"offsets and poses {T120_SHOULDER_AIR:.4f} "
        f"and {T120_TURNED_BAND_RADIAL:.4f} mm, "
        f"checked at fit-up on a {PINION_T120_FITUP_FEELER:.2f} feeler; band turned down to "
        f"{PINION_TURNED_DIA_FITUP_MIN:.2f} only at crank height <= "
        f"{T120_BAND_CHECK_CRANK_HEIGHT:.4f}"
    )
    _telemetry.info(
        f"16T covers {CRANK_ROW_ENGAGEMENT_FRACTION_WORST:.2%} of the 64T tooth row at worst "
        f"(axis poses +/-{CRANK_ROW_POSE_AXIAL:.4f}, cone stack floated {CONE_FLOAT_NORTH:.2f}) "
        f">= {CRANK_ROW_ENGAGEMENT_FLOOR:.0%}"
    )
    # #893: the W15 stacks are import-time asserts, so a passing build would
    # otherwise leave no record of their sums or margins in the leaf log.
    _telemetry.info(
        "16T pin wall to the shaft end, worst case: "
        f"{_stack_text(PINION_PIN_EDGE_STACK)} >= {PINION_PIN_EDGE_MIN_WORST}"
    )
    _telemetry.info(
        "crankshaft end recess inside the 16T boss, worst case: "
        f"{_stack_text(PINION_RECESS_STACK)} >= {PINION_RECESS_MIN_WORST}"
    )
    # The rig's worst-case margin table (asserted at import), in the task log at
    # info: the farm leaf log runs at info, and a debug line never reached it
    # (pc-p1 leaf, 2026-09-25).
    for line in rig_margin_lines():
        _telemetry.info(f"rig margin {line}")
    check("create_assembly", await adapter.create_assembly())

    # =================== structure (static lock + moving joints) ===========
    # The stationary arbor is the reference frame the moving train mates
    # against. Inserted FIRST, so SolidWorks auto-fixes it as the seed (the one
    # allowed fixed component, mirroring frame's harmonic-base) -- no explicit fix.
    arbor = await place_component(
        adapter,
        "dt-cylinder-gear-shaft",
        [X_DRUM, Y_DRIVE, ARBOR_SOUTH_Z],
        [90.0, 0.0, 0.0],
        ROT_X_POS90,
        ground=False,
        label="cylinder arbor (seed)",
    )
    # The arbor-pedestal is a static mount bolted to the (absent) base. With
    # no in-subassembly contact partner, its authored machine-frame pose is
    # retained by one lock to the fixed seed arbor. (The old separate
    # crank-pedestal is GONE: the merged green
    # column below rides the swing platform.)
    # South arbor pedestal only (2026-06-19): the rocker support's arbor-clamp
    # boss is gone with the portal unification, AND the now-solid portal north
    # upright occupies the space the arbor's north end used to pass through. The
    # arbor seats in the support ArborClampBoss at its north end (PR8) and is
    # left unsupported for now -- the dedicated north-end support (pedestal) and
    # the cone small-end bracket are DEFERRED to the cone-position rework, since
    # the cone is currently mis-positioned and that region will be re-laid out.
    arbor_pedestal = await place_component(
        adapter,
        "dt-arbor-pedestal",
        [X_DRUM, Y_BASE_TOP, -ARBOR_PEDESTAL_Z],
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
        label=f"arbor-pedestal z={-ARBOR_PEDESTAL_Z:g}",
    )
    await _lock_static(adapter, arbor_pedestal, arbor)
    # NORTH pedestal (PR8, ch12 img09): the same casting rotated 180 about Y
    # so its strap face looks south at the drum's north end; the arbor's north
    # end seats ~7.0 into its strap bore (U34c). Base-bolted static like the
    # south one.
    north_pedestal = await place_component(
        adapter,
        "dt-arbor-pedestal",
        [X_DRUM, Y_BASE_TOP, ARBOR_PEDESTAL_NORTH_Z],
        [0.0, 180.0, 0.0],
        [[-1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, -1.0]],
        ground=False,
        label=f"arbor-pedestal north z={ARBOR_PEDESTAL_NORTH_Z:g}",
    )
    await _lock_static(adapter, north_pedestal, arbor)
    # Thrust washers (MHA-DT-026, #743): the front one on gear 0's cam face, the
    # back one on gear 19's back face against the datum strap -- the bank
    # modelled pushed back. They turn with nothing, so each is held like the
    # pedestals: one lock to the fixed seed arbor.
    for _disc_z0, _end in ((END_DISC_SOUTH_Z0, "south"), (END_DISC_NORTH_Z0, "north")):
        end_disc = await place_component(
            adapter,
            "dt-cylinder-end-disc",
            [X_DRUM, Y_DRIVE, _disc_z0],
            [0.0, 0.0, 0.0],
            IDENTITY,
            ground=False,
            label=f"cylinder thrust washer {_end} z0={_disc_z0:.3f}",
        )
        await _lock_static(adapter, end_disc, arbor)
    # Apex set screws (MHA-VN-034, #743 Q3): point down through each crown onto
    # the arbor's top at the strap's mid-depth; static like their pedestals.
    for _screw_z, _end in ((SET_SCREW_SOUTH_Z, "south"), (SET_SCREW_NORTH_Z, "north")):
        set_screw = await place_component(
            adapter,
            "vn-arbor-set-screw",
            [X_DRUM, SET_SCREW_TIP_Y, _screw_z],
            [0.0, 0.0, 0.0],
            IDENTITY,
            ground=False,
            label=f"arbor set screw {_end} z={_screw_z:.3f}",
        )
        await _lock_static(adapter, set_screw, arbor)
    # The cone SWING PLATFORM is the swing bracket (ch.12, p.18 "pivot"):
    # floated so the whole cone set can swing horizontally out of mesh about
    # its tip-end vertical pivot (p1). Pinned at the engaged rest pose by a
    # suppressible angle driver in the joints section. The pivot post and tip
    # block are seated ON its PlateTop below, so they -- and the shaft they
    # journal -- ride the swing as one unit.
    ppivot = cone_station(PIVOT_STATION)
    platform = await place_component(
        adapter,
        "dt-cone-swing-platform",
        [ppivot[0], Y_BASE_TOP, ppivot[2]],
        [0.0, INCLINE_DEG, 0.0],
        ROT_Y_INCLINE,
        ground=False,
        label="cone-swing-platform (swing bracket, engaged rest)",
    )
    ppost = cone_station(POST_STATION)
    pivot_post = await place_component(
        adapter,
        "dt-cone-pivot-post",
        [ppost[0], Y_BASE_TOP + PLAT_T, ppost[2]],
        [0.0, POST_ROTATION_Y_DEG, 0.0],
        ROT_Y_180,
        ground=False,
        label="cone-pivot-post (v2 Ry180, big-end journal, on the plate)",
    )
    # I22: the two MHA-VN-031 fillisters, head up on the post's counterbore
    # floors. The post is turned Ry180, so its local +X "mount west" axis
    # lands at machine -X of the post origin.
    post_screws: list[str] = []
    for tag, dx in (("west", -POST_ATTACHMENT_X), ("east", POST_ATTACHMENT_X)):
        post_screws.append(
            await place_component(
                adapter,
                "vn-post-mount-screw",
                [ppost[0] + dx, Y_BASE_TOP + PLAT_T + POST_SCREW_SEAT, ppost[2]],
                [0.0, 0.0, 0.0],
                IDENTITY,
                ground=False,
                label=f"post-mount-screw {tag} (MHA-VN-031 on the post counterbore)",
            )
        )
    ptip = cone_station(TIP_BLOCK_STATION)
    # User ruling 2026-09-29: the block is a straight prism standing directly
    # on PlateTop (no shim), so its foot is the plate top and its height is
    # the axis-height assert above.
    tip_foot_y = Y_BASE_TOP + PLAT_T
    tip_block = await place_component(
        adapter,
        "dt-cone-tip-block",
        [ptip[0], tip_foot_y, ptip[2]],
        [0.0, INCLINE_DEG, 0.0],
        ROT_Y_INCLINE,
        ground=False,
        label="cone-tip-block (end-play adjuster support, on the plate)",
    )
    # MHA-VN-030 (#4-40 x 3/8 SHCS) rises from under the plate: head down on the
    # hold-down counterbore's floor, HOLDDOWN_CBORE_DEPTH above the plate's
    # underside, shank up into the block foot's blind tap.  The hole sits
    # TIP_BLOCK_PIVOT_OFFSET south of the pivot (the block's station) and
    # PLAT_HOLDDOWN_LOCAL_X along the plate's local x (ROT_Y_INCLINE's row 0).
    tip_tap_xz = (
        ptip[0] + PLAT_HOLDDOWN_LOCAL_X * ROT_Y_INCLINE[0][0],
        ptip[2] + PLAT_HOLDDOWN_LOCAL_X * ROT_Y_INCLINE[0][2],
    )
    tip_holddown = await place_component(
        adapter,
        "vn-cone-tip-block-screw",
        [tip_tap_xz[0], Y_BASE_TOP + PLAT_HOLDDOWN_CBORE_DEPTH, tip_tap_xz[1]],
        HOLDDOWN_HEAD_DOWN_EULER,
        ROT_X_180,
        ground=False,
        label="cone-tip-block-screw (MHA-VN-030 up through the plate into the block foot)",
    )
    # Tip end-play stack (item 5, v4_t00471): the MHA-VN-016 stack collar on the
    # tip land, the axial adjuster screw in the block's tapped bore, and the
    # pinch screw across the block's top slit. Stations derived at import
    # (COLLAR_STATION / ADJ_HEAD_STATION); all three ride the swing family.
    # ROT_SHAFT_NORTH lays the collar's +X (its set screw) on the shaft's +X,
    # the D-flat's outward normal.
    pcollar = cone_station(COLLAR_STATION)
    tip_collar = await place_component(
        adapter,
        "vn-cone-tip-collar",
        [pcollar[0] + COLLAR_LOADED_OFFSET * ROT_SHAFT_NORTH[0][0],
         Y_DRIVE + COLLAR_LOADED_OFFSET * ROT_SHAFT_NORTH[0][1],
         pcollar[2] + COLLAR_LOADED_OFFSET * ROT_SHAFT_NORTH[0][2]],
        [90.0, INCLINE_DEG, 0.0],
        ROT_SHAFT_NORTH,
        ground=False,
        label="cone-tip-collar (stack collar, locked on the tip D-flat)",
    )
    padj = cone_station(ADJ_HEAD_STATION)
    tip_adjuster = await place_component(
        adapter,
        "vn-cone-tip-adjuster",
        [padj[0], Y_DRIVE, padj[2]],
        [-90.0, INCLINE_DEG, 0.0],
        ROT_SHAFT_SOUTH,
        ground=False,
        label="cone-tip-adjuster (axial end-play screw, head north)",
    )
    pinch_screw = await place_component(
        adapter,
        "vn-cone-tip-pinch-screw",
        [
            ptip[0] + (TIP_BLOCK_X / 2.0) * COS_I,
            tip_foot_y + TIP_PINCH_Y,
            ptip[2] - (TIP_BLOCK_X / 2.0) * SIN_I,
        ],
        PINCH_WEST_EULER,
        ROT_PINCH_WEST,
        ground=False,
        label="cone-tip-pinch-screw (slit clamp, head on the +X clearance face)",
    )
    # The lock knob is a base-bolted static: its head underside lands on the
    # plate top and its longer stud passes through the slot into the new 1/4-20
    # base seat. The plate remains the mover, sweeping around the stationary
    # stud without changing the assembly's operational swing DOF.
    lock_knob = await place_component(
        adapter,
        "vn-cone-lock-knob",
        [KNOB_X, Y_BASE_TOP + PLAT_T, KNOB_Z],
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
        label="cone-lock-knob (platform clamp, engaged end)",
    )
    await _lock_static(adapter, lock_knob, arbor)
    # The platform pivot screw (item 2, p.18 "pivot"): a base-threaded STATIC.
    # Its shoulder bottoms on the base top, placing the head 0.25 above the
    # plate and leaving the plate free to swing; the threaded tail enters the
    # matching blind #10-24 UNC-2B seat.
    pivot_screw = await place_component(
        adapter,
        "vn-cone-pivot-screw",
        [ppivot[0], Y_BASE_TOP + PSCREW_SHOULDER_LEN, ppivot[2]],
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
        label="cone-pivot-screw (p1 pivot pin)",
    )
    await _lock_static(adapter, pivot_screw, arbor)
    # The base-threaded swing stop remains a static at the base-top production
    # frame. Screwed fully home, its head meets the disengaged platform's east edge
    # at the one shared contact station exported with the base hole.
    stop_screw = await place_component(
        adapter,
        "vn-swing-stop-screw",
        [STOP_X, Y_BASE_TOP, STOP_Z],
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
        label="swing-stop-screw (p1 travel limit)",
    )
    await _lock_static(adapter, stop_screw, arbor)

    # ============ alignment pinion swing group (ch.25, p.66; p2) ============
    # Floated straps + drum, joined and parked DISENGAGED in the joints
    # section. The pivot blocks and torque shaft are base-bolted statics
    # (locked to the fixed seed arbor below); the lift rod is a REVOLUTE in
    # the blocks' raised west bores carrying the two eccentric cams and the
    # lever (PR8 -- all semantically mated, spinning as one family on the
    # freed pinion_cam DOF). The separate MHA-DT-015 grip crossrod is LOCKED to
    # MHA-DT-022's integral head in the joints section, so the freed p2 swing
    # carries it with the rig instead of leaving it base-fixed in space
    # (Codex catch, 2026-07-05).
    align_pinion = await place_component(
        adapter,
        "dt-alignment-pinion",
        [APINION_X, APINION_Y, APINION_Z_FRONT],
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
        label="alignment-pinion (disengaged rest)",
    )
    # The straps and pivot blocks extrude local +z, so their machine-handed
    # pose composes a Ry(180) with the lean: the part origin then lands at the
    # component's NORTH face (south face + part thickness), which is where the
    # strap bands below are authored from.
    _strap_rows = STRAP_ROWS
    _strap_euler = euler_from_rows(_strap_rows)
    pinion_brackets: dict[str, str] = {}
    for tag, z0 in zip(("front", "back"), STRAP_ORIGIN_Z, strict=True):
        pinion_brackets[tag] = await place_component(
            adapter,
            "dt-pinion-bracket",
            [PIVOT_X, PIVOT_Y, z0],
            _strap_euler,
            _strap_rows,
            ground=False,
            label=f"pinion-bracket {tag} (leaning, arbor bore up top)",
        )
    # Option E-a set pins (MHA-VN-033): the purchased 1/16 x 1/2 spring pin in
    # each strap's cross hole, inserted with the strap's own rows so its axis
    # (local X) is the hole's and its principal planes parallel the strap's.
    # Front first: the interference contract keys the front pin as -1.
    strap_pins: dict[str, str] = {}
    for tag, z_pin in zip(("front", "back"), STRAP_PIN_Z, strict=True):
        strap_pins[tag] = await place_component(
            adapter,
            "vn-pinion-strap-pin",
            [PIVOT_X, PIVOT_Y, z_pin],
            _strap_euler,
            _strap_rows,
            ground=False,
            label=f"pinion-strap-pin {tag} (MHA-VN-033 in the strap cross hole)",
        )
    pinion_blocks: list[str] = []
    for tag, z0 in (("front", BLOCK_FRONT_Z0), ("back", BLOCK_BACK_Z0)):
        blk = await place_component(
            adapter,
            "dt-pinion-pivot-block",
            [BLOCK_X, PIVOT_Y, z0 + BLOCK_DEPTH],
            [0.0, 180.0, 0.0],
            ROT_Y_180,
            ground=False,
            label=f"pinion-pivot-block {tag}",
        )
        pinion_blocks.append(blk)
    # Option E-a: the shaft is pinned to both straps through their cross
    # holes, so it is inserted phased to them -- its local X (the pin-hole
    # axis) lies along the straps' local X at the park lean.
    pivot_shaft = await place_component(
        adapter,
        "dt-pinion-pivot-shaft",
        [PIVOT_X, PIVOT_Y, PIVOT_SHAFT_Z0],
        [0.0, 0.0, STRAP_LEAN_DEG],
        TORQUE_SHAFT_ROWS,
        ground=False,
        label="pinion-pivot-shaft (pinned to the straps, E-a)",
    )
    lift_rod = await place_component(
        adapter,
        "dt-pinion-lift-rod",
        [LIFT_X, LIFT_Y, LIFT_ROD_Z0],
        [0.0, 0.0, LEVER_TILT_DEG],
        LIFT_ROD_ROWS,  # phased to the lever: coaxial MHA-DT-030 pin holes
        ground=False,
        label="pinion-lift-rod (in the blocks' raised west bores)",
    )
    spring = await place_component(
        adapter,
        "dt-pinion-spring",
        [SPRING_X, Y_BASE_TOP, SPRING_Z],
        [0.0, 180.0, 0.0],
        ROT_Y_180,
        ground=False,
        label="pinion-spring (holds the swing disengaged)",
    )
    cam_pins: dict[str, str] = {}
    for tag, z_mid in (("front", _STRAP_MID_Z[0]), ("back", _STRAP_MID_Z[1])):
        cam_pins[tag] = await place_component(
            adapter,
            "dt-pinion-cam-pin",
            [_FPIN_ORG[0], _FPIN_ORG[1], z_mid],
            FPIN_EULER,
            FPIN_ROWS,
            ground=False,
            label=f"pinion-cam-pin {tag} (edge-seat follower)",
        )
    # Eccentric cam collars (PR8 items 8b/9): one per strap station, pinned to
    # the lift rod in the authored PARK pose (ecc straight down).
    pinion_cams: dict[str, str] = {}
    for tag, z0 in (("front", CAM_Z0[0]), ("back", CAM_Z0[1])):
        pinion_cams[tag] = await place_component(
            adapter,
            "dt-pinion-cam",
            [LIFT_X, LIFT_Y, z0],
            [0.0, 0.0, 0.0],
            PINION_CAM_ROWS,
            ground=False,
            label=f"pinion-cam {tag} (parked ecc down)",
        )
    lever = await place_component(
        adapter,
        "dt-pinion-lever",
        [LIFT_X, LIFT_Y, LEVER_Z],
        [0.0, 0.0, LEVER_TILT_DEG],
        LEVER_ROWS,  # positive rest angle tips machine -X
        ground=False,
        label="pinion-lever (clamp hub on the lift rod front end)",
    )
    # MHA-DT-030: the 1/16 pin driven through the match-drilled hub and rod holes.
    # Its axis is its local X, so it takes the rod's phase and sits centred on
    # the rod's "lever pin" station.  The INSTALLED configuration is the pin
    # trimmed and peened flush with the hub (Codex #858 P2), not the overlength
    # cut the part's drawing prints.
    lever_pin = await place_component(
        adapter,
        "dt-pinion-lever-pin",
        [LIFT_X, LIFT_Y, LIFT_ROD_Z0 + LEVER_PIN_FROM_ROD_END],
        [0.0, 0.0, LEVER_TILT_DEG],
        LIFT_ROD_ROWS,
        ground=False,
        configuration=LEVER_PIN_INSTALLED_CONFIG,
        label="pinion-lever-pin (MHA-DT-030 through hub and rod)",
    )
    grip_crossrod = await place_component(
        adapter,
        "dt-pinion-handle",
        [APINION_X, APINION_Y, HANDLE_Z],
        [0.0, 0.0, HANDLE_TILT_DEG],
        HANDLE_ROWS,  # unchanged +z spin tips the local +Y rod toward machine -X
        ground=False,
        label="pinion-handle (separate grip crossrod through integral head)",
    )
    # MHA-DT-022 is pressed through the brass drum and journaled in both straps'
    # Ø8 top bores.  Its turned grip head and neck are part of this same solid.
    # Rotate only about the circular shaft axis so its local-Y cross-hole is
    # coaxial with MHA-DT-015's local-Y rod; every world centre and Z station stays
    # unchanged.
    pinion_arbor = await place_component(
        adapter,
        "dt-pinion-arbor",
        [APINION_X, APINION_Y, ARBOR_Z0],
        [0.0, 0.0, HANDLE_TILT_DEG],
        ARBOR_ROWS,
        ground=False,
        label="pinion-arbor (integral steel arbor and grip head)",
    )
    arbor_collar = await place_component(
        adapter,
        "dt-pinion-arbor-collar",
        [APINION_X, APINION_Y, ARBOR_COLLAR_Z0],
        [0.0, 0.0, HANDLE_TILT_DEG],
        ARBOR_ROWS,
        ground=False,
        label="pinion-arbor-collar (spring-pinned walk-out backstop)",
    )
    # Its MHA-VN-033 spring pin through collar and arbor.
    collar_pin = await place_component(
        adapter,
        "vn-pinion-strap-pin",
        [APINION_X, APINION_Y, COLLAR_PIN_Z],
        euler_from_rows(COLLAR_PIN_ROWS),
        COLLAR_PIN_ROWS,
        ground=False,
        label="pinion-strap-pin collar (MHA-VN-033 through MHA-DT-033 and MHA-DT-022)",
    )
    # Rig hold-downs (PR7 items 2/11/12): physically located seeds are patterned
    # across the repeated block/pedestal stations in the joints section below.
    sx, sz = _BLOCK_SCREW_XZ[0]
    block_screw = await place_component(
        adapter,
        "vn-slotted-screw",
        [sx, BLOCK_TOP_Y, sz],
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
        label="slotted-screw block hold-down seed",
    )
    sx, sz = _FOOT_SCREW_XZ[0]
    spring_foot_screw = await place_component(
        adapter,
        "vn-foot-screw",
        [sx, Y_BASE_TOP + SPRING_T, sz],
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
        label="foot-screw (spring foot)",
    )
    # U34c: the south pedestal's MHA-VN-032 is the seed; the north one is its
    # linear pattern instance below (vn-pedestal-hold-down-screw-1 / -2).
    sx, sz = _PEDESTAL_SCREW_XZ[0]
    pedestal_screw = await place_component(
        adapter,
        "vn-pedestal-hold-down-screw",
        [sx, Y_BASE_TOP + ARBOR_PED_FLANGE_T, sz],
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
        label="pedestal-hold-down-screw (south ledge)",
    )

    # =================== cone cluster (driven, on-solution) ====================
    cone_shaft = await place_component(
        adapter,
        "dt-cone-gear-shaft",
        cone_station(SHAFT_FRONT_STATION),  # part origin = the front stub end
        [0.0, INCLINE_DEG, 0.0],
        ROT_Y_INCLINE,
        ground=False,
    )
    gear64 = await _place_on_shaft(
        adapter,
        "dt-crank-drive-gear",
        GEAR64_CENTRE_STATION,
        GEAR64_FACE,
        label="crank-drive-gear (perpendicular, journal seat)",
    )
    # The full 20-gear cone stack is ALWAYS built (it is one rigid keyed cluster
    # derived from the full channel table); only the cylinder drum + its cam
    # followers downstream follow active_count -- the build-speed knob (see
    # machine.yaml channels.active_count / _config.active_count; 20 = full).
    # Only the T120 SEED is inserted here; stations 1..19 are REPLICATED from
    # it with CopyWithMates2 in the keying section below (#228) -- the slice is
    # fully defined (the vendor-blessed copy case, no free-DOF attractor), and
    # each copy is re-pointed at its own T-configuration post-copy.
    seed_teeth = _config.cone_teeth(0)
    seed_cg = await _place_on_shaft(
        adapter,
        "dt-cone-gear",
        SHAFT_T120_STATION + GEAR_AXIS_SHIFT + (CONE_FACE_STATION_REFERENCE - CONE_FACE) / 2.0,
        CONE_FACE,
        configuration=f"T{seed_teeth:03d}",
        label=f"cone-gear T{seed_teeth:03d}",
    )
    cone_gears: list[tuple[int, str]] = [(seed_teeth, seed_cg)]

    # =================== cylinder drum (driven, free on the arbor) =============
    # Only the first active_count cylinder gears (and, via the channel assembly,
    # their cam followers) are built -- active_count is the build-speed knob for
    # debugging iterations (20 = the full machine, the default). Cone gears
    # 0..19 above stay; cone gears active_count..19 simply mesh nothing (they
    # remain keyed to the cone shaft, fully defined, harmless).
    # Only the station-0 SEED is inserted here; stations 1..19 are REPLICATED
    # from it in the mate section below with 2-mate CopyWithMates2 (the
    # fresh-mesh ladder, diagnostics/diag_cwm_cylinder.py): a copy CARRYING
    # the gear-mesh mate parks 9.12 deg off in the mesh's stored phase
    # (measured, stable across rebuilds, and uncorrectable -- through the
    # coupling any post-copy spin fix would crank the whole free train), so
    # the mesh is never copied; each station's is authored fresh instead.
    # Flip the asymmetric gear/cam sandwich about its already-phased local Y
    # diameter.  Local +Z becomes machine -Z while local +Y (the cam-lobe
    # phase) is unchanged.  Translating the origin from face centre -1.5 to
    # face centre +1.5 keeps the 3-mm toothed slab centred on station z_j. The
    # lock phase is gear_train.cylinder_lock_phase_deg via channel_frame_geom.
    cylinder_rows = compose_rows(ROT_Y_180, rot_z_rows(-CYLINDER_LOCK_PHASE_DEG))
    cyl_gears: list[str] = [
        await place_component(
            adapter,
            "dt-cylinder-gear",
            [X_DRUM, Y_DRIVE, Z_DRUM0 + DRUM_FACE / 2.0],
            euler_from_rows(cylinder_rows),
            cylinder_rows,
            ground=False,
            label="cylinder-gear 0 (face-centred local-Y flip seed)",
        )
    ]

    # =================== crank (driven, on-solution) ===========================
    crankshaft = await place_component(
        adapter,
        "dt-crankshaft",
        [X_CRANK, Y_CRANK, CRANKSHAFT_Z0],
        [90.0, 0.0, 0.0],
        ROT_X_POS90,
        ground=False,
    )
    pinion = await place_component(
        adapter,
        "dt-crank-pinion",
        [X_CRANK, Y_CRANK, PINION_TOOTH_Z - PINION_FACE / 2.0],
        [0.0, 0.0, -PINION_SEED_DEG],
        rot_z_rows(-PINION_SEED_DEG),  # tooth-in-gap
        ground=False,
        label="crank-pinion (centred on the 64T contact tooth)",
    )
    hub = await place_component(
        adapter,
        "dt-crank-hub",
        [X_CRANK, Y_CRANK, CRANK_HUB_Z0],
        [90.0, 0.0, 0.0],
        ROT_X_POS90,
        ground=False,
        label="MHA-DT-031 through hub",
    )
    seam_pin = await place_component(
        adapter,
        "vn-crank-hub-pin",
        CRANK_HUB_PIN_ORIGIN,
        [0.0, 0.0, 0.0],
        CRANK_HUB_PIN_ROWS,
        ground=False,
        label="MHA-VN-029 six-o'clock axial seam pin",
    )
    # The crank seat behind the chain wheel: MHA-DT-036 flat on the collar's rear
    # face (local +Y -> machine +Z, rearward), and the two MHA-VN-044 drive pins
    # standing in the collar's blind holes, pressed end on DrivePinFloor and
    # rounded lead end forward (local +Y -> machine -Z).  DrivePinAxis1 lies
    # on the shaft's local +Z (machine -Y), DrivePinAxis2 opposite.
    seat_washer = await place_component(
        adapter,
        "dt-crank-seat-washer",
        [X_CRANK, Y_CRANK, CRANK_SEAT_WASHER_Z0],
        [90.0, 0.0, 0.0],
        ROT_X_POS90,
        ground=False,
        label="MHA-DT-036 on the crank collar's rear face",
    )
    seat_pins = [
        await place_component(
            adapter,
            "vn-crank-seat-drive-pin",
            [X_CRANK, Y_CRANK + side * REMOVABLE.PIN_CIRCLE_RADIUS, CRANK_DRIVE_PIN_Z0],
            euler_from_rows(ROT_X_NEG90),
            ROT_X_NEG90,
            ground=False,
            label=f"MHA-VN-044 drive pin in DrivePinAxis{k}",
        )
        for k, side in ((1, -1.0), (2, 1.0))
    ]
    # The crank-end T12 chain wheel is NOT placed here: paper-drive now OWNS the
    # whole crank->paper chain drive (both sprockets + roller chain + belt), so the
    # single crank chain wheel lives in paper-drive (codex #189 :605). Placing it
    # here too made two coincident T12 wheels at the crank centre once both
    # subassemblies are inserted at the top level -> interference. Drive-train
    # keeps the shaft, its seat washer and drive pins, hub, arm, handle, both
    # crank pins and 16T pinion; the crank spin DOF remains keyed through the arm.
    # Crank rest pose: the arm hangs straight DOWN (ch30 eight-views -- the
    # handle reads "down" in all eight roll angles, which only a -Y arm does,
    # since a downward vector lies on the views' vertical rotation axis). The
    # arm's local +x maps to machine -Y, while local +z maps toward machine -Z;
    # its origin is the inboard face at -175 and the plate fills -183..-175.
    arm = await place_component(
        adapter,
        "dt-crank-arm",
        [X_CRANK, Y_CRANK, CRANK_ARM_ORIGIN_Z],
        [180.0, 0.0, -90.0],
        compose_rows(rot_z_rows(-90.0), ROT_Y_180),
        ground=False,
    )
    # Taper pin MHA-DT-009 crosses the separate hub's rear barrel and crankshaft
    # at station -169.4, behind the arm.  Its big end stands PIN_PROUD outside
    # the hub's -X face; the brass keeper ring hangs from the head cross-hole.
    # The hub #14 and shaft #9 pilots are match-reamed together to the pin's
    # 1:48 taper, so those two overlaps alone are volume-bounded allowed pairs
    # in _interference_contracts.
    pin = await place_component(
        adapter,
        "dt-crank-pin",
        [CRANK_PIN_X0, Y_CRANK, CRANK_PIN_Z],
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
        label="crank taper pin",
    )
    await lock_mate(
        adapter,
        named_ref(f"Front Plane@{pin}", "PLANE"),
        named_ref(f"Front Plane@{hub}", "PLANE"),
        label="MHA-DT-009 locked to the crank hub",
    )
    ring = await place_component(
        adapter,
        "dt-crank-pin-ring",
        [CRANK_PIN_X0 + PIN_RING_HOLE_X, CRANK_RING_Y, CRANK_PIN_Z],
        [0.0, 0.0, -90.0],
        rot_z_rows(-90.0),
        ground=False,
        label="crank pin keeper ring",
    )
    await lock_mate(
        adapter,
        named_ref(f"Front Plane@{ring}", "PLANE"),
        named_ref(f"Front Plane@{pin}", "PLANE"),
        label="keeper ring locked to the pin",
    )
    # Pinion retention pin (ch12 p.19): through the boss and the shaft at the
    # pin station along the seated pinion's local X (PINION_PIN_U), flush with
    # the boss both sides. Locked to the pinion so it turns with the crank; a
    # light drive fit in its own match-drilled hole is line contact at the
    # nominal, so no allowed-pair volume is needed.
    pinion_pin = await place_component(
        adapter,
        "dt-crank-pinion-pin",
        PINION_PIN_ORIGIN,
        [0.0, 90.0, -PINION_SEED_DEG],
        compose_rows(ROT_Y_POS90, rot_z_rows(-PINION_SEED_DEG)),
        ground=False,
        label="crank pinion retention pin",
    )
    await lock_mate(
        adapter,
        named_ref(f"Front Plane@{pinion_pin}", "PLANE"),
        named_ref(f"Front Plane@{pinion}", "PLANE"),
        label="pinion retention pin locked to the pinion",
    )
    # Keeper-ring anchor screw + brass eyelet on the arm's front face (ch11
    # p.14); both lock to the arm so they turn with the crank.
    eye = await place_component(
        adapter,
        "dt-crank-pin-eye",
        [ANCHOR_SCREW_XY[0], EYE_ROOT_Y, EYE_Z],
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
        label="keeper-ring anchor eyelet",
    )
    await lock_mate(
        adapter,
        named_ref(f"Front Plane@{eye}", "PLANE"),
        named_ref(f"Front Plane@{arm}", "PLANE"),
        label="anchor eyelet locked to the arm",
    )
    anchor = await place_component(
        adapter,
        "vn-fillister-screw",
        [ANCHOR_SCREW_XY[0], ANCHOR_SCREW_XY[1], ANCHOR_HEAD_Z],
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
        label="keeper-ring anchor screw",
    )
    await lock_mate(
        adapter,
        named_ref(f"Front Plane@{anchor}", "PLANE"),
        named_ref(f"Front Plane@{arm}", "PLANE"),
        label="anchor screw locked to the arm",
    )
    # Keeper chain (MHA-VN-035): one loop through the eye and the pin's ring,
    # closed by the MHA-VN-036 loop link. Both lock to the arm: the eye, the pin
    # and the ring all turn with the crank, so the loop's rest drape rides
    # with it.
    chain = await place_component(
        adapter,
        "vn-keeper-chain",
        [c + o for c, o in zip(CRANK_FRAME_ORIGIN, vn_keeper_chain_spec.CHAIN_PART_ORIGIN)],
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
        label="keeper chain",
    )
    await lock_mate(
        adapter,
        named_ref(f"Front Plane@{chain}", "PLANE"),
        named_ref(f"Front Plane@{arm}", "PLANE"),
        label="keeper chain locked to the arm",
    )
    # The link is authored along local X; its axis runs along machine z
    # beside the arm edge (ROT_Y_POS90: local X -> machine -Z; the link is
    # symmetric end for end, and its +Y seam stays up).
    if vn_keeper_chain_spec.LINK_AXIS != (0.0, 0.0, 1.0):
        raise AssertionError("keeper-chain link placement assumes an axis along machine z")
    link = await place_component(
        adapter,
        "vn-keeper-chain-link",
        [o + c for o, c in zip(vn_keeper_chain_spec.LINK_ORIGIN, CRANK_FRAME_ORIGIN)],
        [0.0, 90.0, 0.0],
        ROT_Y_POS90,
        ground=False,
        label="keeper chain loop link",
    )
    await lock_mate(
        adapter,
        named_ref(f"Front Plane@{link}", "PLANE"),
        named_ref(f"Front Plane@{arm}", "PLANE"),
        label="keeper chain loop link locked to the arm",
    )
    # Handle pivot rides the arm tip, now ARM_C2C below the crankshaft. Its grip
    # axis stays parallel to the crankshaft (ROT_Y_POS90 -> assembly -Z).
    handle = await place_component(
        adapter,
        "dt-crank-handle",
        [X_CRANK, Y_CRANK - ARM_C2C, CRANK_ARM_Z0],
        [0.0, 90.0, 0.0],
        ROT_Y_POS90,
        ground=False,
    )
    # User ruling 2026-09-29 (ch11 p.14/p.15): the brass ferrule MHA-DT-034 and the
    # steel butt cup MHA-DT-035 are bonded to the oak, each authored in the
    # handle's own frame -- the ferrule from the arm face at x=0, the cup from
    # its face at the basic overall length -- so both take the handle's
    # transform and lock to it.
    handle_ferrule = await place_component(
        adapter,
        "dt-crank-handle-ferrule",
        [X_CRANK, Y_CRANK - ARM_C2C, CRANK_ARM_Z0],
        [0.0, 90.0, 0.0],
        ROT_Y_POS90,
        ground=False,
        label="crank-handle-ferrule (MHA-DT-034, on the handle tenon)",
        # As assembly leaves it: skimmed to the grip contour with the oak
        # shoulder (user ruling 2026-10-01).
        configuration=HANDLE_FERRULE_INSTALLED_CONFIG,
    )
    handle_cup = await place_component(
        adapter,
        "dt-crank-handle-butt-cup",
        [X_CRANK, Y_CRANK - ARM_C2C, CRANK_ARM_Z0 - HANDLE_BASIC_LENGTH],
        [0.0, 90.0, 0.0],
        ROT_Y_POS90,
        ground=False,
        label="crank-handle-butt-cup (MHA-DT-035, in the handle butt)",
    )
    # MHA-DT-032 carries the handle: head outboard, local +Z (head -> tip) along
    # machine +z, so the shoulder's ArmSeat lands on the arm's outboard face.
    # Its INSTALLED configuration is the tip filed flush with the arm's
    # inboard face, not the long as-turned thread the part's drawing prints.
    handle_screw = await place_component(
        adapter,
        "dt-crank-handle-pivot-screw",
        [X_CRANK, Y_CRANK - ARM_C2C, HANDLE_SCREW_Z0],
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
        configuration=HANDLE_SCREW_INSTALLED_CONFIG,
        label="crank-handle-pivot-screw (MHA-DT-032, tip filed flush)",
    )

    # =================== joints ================================================
    # Crankshaft revolute on the PLATFORM's "crank axis" (the machine-z crank
    # line the plate carries -- the merged column's bore is geometry only):
    # coincident axis-to-axis (4 DOF) + an axial plane distance (1 DOF),
    # BOTH relative to the swinging plate so the whole crank rig follows the
    # p1 swing. The crankshaft axis is local +Y -> assembly Z (ROT_X_POS90),
    # so its Top Plane is the axial reference; the plate's Front plane is the
    # swing-following axial datum (distance read live from the rest pose).
    cs_o = _org(adapter, crankshaft)
    await coincident_mate(
        adapter,
        named_ref(f"Axis1@{crankshaft}", "AXIS"),
        named_ref(f"crank axis@{platform}", "AXIS"),
        label="crankshaft radial (plate crank axis)",
        verify=(crankshaft, cs_o),
    )
    # Axial seat vs the plate's CrankAxisSeat plane (perpendicular to the
    # crank axis, anchored at the plate's crank-anchor point -- ON the crank
    # axis, so its machine x is X_CRANK, asserted at import): distance =
    # |Delta z| at the engaged rest pose (both are machine-z-normal planes
    # there).
    _cs_axial = cs_o[2] - _SEAT_ANCHOR_M[1]
    await distance_driver(
        adapter,
        named_ref(f"Top Plane@{crankshaft}", "PLANE"),
        named_ref(f"CrankAxisSeat@{platform}", "PLANE"),
        _cs_axial,
        label=f"crankshaft axial d={_cs_axial:.2f} (on the plate)",
        verify=(crankshaft, cs_o),
    )
    # Keyed crank rig: the 16T pinion, separate hub and matched arm rotate with
    # the crankshaft; the handle rides the arm pivot.  Semantic coaxial, axial
    # seat and anti-spin mates retain the single crankshaft spin DOF without
    # grounding the swing rig.  The suppressible crank angle driver below pins
    # that spin via the arm.  The T12 chain wheel lives in paper-drive.
    crank_axis = named_ref(f"Axis1@{crankshaft}", "AXIS")
    cs_right = named_ref(f"Right Plane@{crankshaft}", "PLANE")

    # 16T pinion (placed +half-pitch, tooth-in-gap on the 64T): no plane pair is
    # parallel at that phase, so pin the spin with an ANGLE anti-spin holding the
    # live dihedral between its Right plane and the crankshaft's (~11.25 deg). The
    # pinion origin sits ON the spin axis (flip-recovery can't read it), so a
    # wrong side surfaces as tooth interference, not a silent miss.
    pn_o = await _seat_on_crank(
        adapter, pinion, "Axis2", crank_axis, crankshaft, "SeatPinion"
    )
    a_pn = component_transform(adapter, pinion)
    a_cs = component_transform(adapter, crankshaft)
    pin_phase = math.degrees(
        math.acos(max(-1.0, min(1.0, sum(a_pn[k] * a_cs[k] for k in range(3)))))
    )
    await angle_driver(
        adapter,
        named_ref(f"Right Plane@{pinion}", "PLANE"),
        cs_right,
        pin_phase,
        label=f"16T pinion anti-spin (tooth-in-gap a={pin_phase:.2f})",
        verify=(pinion, pn_o),
    )

    # MHA-DT-031 seats directly on the shaft's common outboard plane.  The
    # through bore leaves the service pair removable after MHA-DT-009 is tapped
    # out; the Right-plane anti-spin represents that installed taper pin.
    hub_o = _org(adapter, hub)
    hub_axis = named_ref(f"Axis1@{hub}", "AXIS")
    await coincident_mate(
        adapter,
        hub_axis,
        crank_axis,
        label="MHA-DT-031 coaxial on crankshaft",
        verify=(hub, hub_o),
    )
    await coincident_mate(
        adapter,
        named_ref(f"Top Plane@{hub}", "PLANE"),
        named_ref(f"Top Plane@{crankshaft}", "PLANE"),
        label="MHA-DT-031 flush on shaft cylinder face",
        alignment="aligned",
        verify=(hub, hub_o),
    )
    await parallel_mate(
        adapter,
        named_ref(f"Right Plane@{hub}", "PLANE"),
        cs_right,
        label="MHA-DT-031 anti-spin (MHA-DT-009)",
        verify=(hub, hub_o),
    )

    # MHA-DT-006 is a matched light press fit onto the 15-mm hub seat and butts
    # against ArmShoulder at local station 8.  Its local +x hangs machine -Y,
    # putting the seam at six o'clock.
    arm_o = _org(adapter, arm)
    await coincident_mate(
        adapter,
        named_ref(f"Axis1@{arm}", "AXIS"),
        hub_axis,
        label="crank arm matched on MHA-DT-031 seat",
        verify=(arm, arm_o),
    )
    await coincident_mate(
        adapter,
        named_ref(f"Front Plane@{arm}", "PLANE"),
        named_ref(f"ArmShoulder@{hub}", "PLANE"),
        label="crank arm inboard face on hub shoulder",
        alignment="anti_aligned",
        verify=(arm, arm_o),
    )
    await parallel_mate(
        adapter,
        named_ref(f"Right Plane@{arm}", "PLANE"),
        named_ref(f"Front Plane@{hub}", "PLANE"),
        label="crank arm six-o'clock phase on hub",
        verify=(arm, arm_o),
    )

    # MHA-VN-029 runs axially from the common outboard face for 4 mm and keys only
    # the arm/hub seam; it never crosses the shaft bore.
    seam_o = _org(adapter, seam_pin)
    await coincident_mate(
        adapter,
        named_ref(f"Axis1@{seam_pin}", "AXIS"),
        named_ref(f"Axis2@{hub}", "AXIS"),
        label="MHA-VN-029 coaxial with six-o'clock seam",
        verify=(seam_pin, seam_o),
    )
    await coincident_mate(
        adapter,
        named_ref(f"Front Plane@{seam_pin}", "PLANE"),
        named_ref(f"Top Plane@{hub}", "PLANE"),
        label="MHA-VN-029 seated at outboard face",
        alignment="aligned",
        verify=(seam_pin, seam_o),
    )
    await parallel_mate(
        adapter,
        named_ref(f"Right Plane@{seam_pin}", "PLANE"),
        named_ref(f"Right Plane@{hub}", "PLANE"),
        label="MHA-VN-029 rotational closure",
        verify=(seam_pin, seam_o),
    )

    # MHA-DT-036 rides the shaft flat against CollarRear; faced to fit, its rear
    # face lands on the boss's south face with no float, so the collar mate
    # places it.  A revolved washer's spin is immaterial: the parallel closes
    # it like MHA-VN-029's.
    washer_o = _org(adapter, seat_washer)
    await coincident_mate(
        adapter,
        named_ref(f"Axis1@{seat_washer}", "AXIS"),
        crank_axis,
        label="MHA-DT-036 coaxial on crankshaft",
        verify=(seat_washer, washer_o),
    )
    await coincident_mate(
        adapter,
        named_ref(f"Top Plane@{seat_washer}", "PLANE"),
        named_ref(f"CollarRear@{crankshaft}", "PLANE"),
        label="MHA-DT-036 flat on the collar rear face",
        verify=(seat_washer, washer_o),
    )
    await parallel_mate(
        adapter,
        named_ref(f"Right Plane@{seat_washer}", "PLANE"),
        cs_right,
        label="MHA-DT-036 rotational closure",
        verify=(seat_washer, washer_o),
    )
    # Each MHA-VN-044 is pressed to the hole floor; its axis is the collar's
    # drilled pin axis, and the parallel closes the revolved pin's spin.
    for k, seat_pin in enumerate(seat_pins, start=1):
        seat_pin_o = _org(adapter, seat_pin)
        await coincident_mate(
            adapter,
            named_ref(f"ScrewAxis@{seat_pin}", "AXIS"),
            named_ref(f"DrivePinAxis{k}@{crankshaft}", "AXIS"),
            label=f"MHA-VN-044 #{k} coaxial in DrivePinAxis{k}",
            verify=(seat_pin, seat_pin_o),
        )
        await coincident_mate(
            adapter,
            named_ref(f"Top Plane@{seat_pin}", "PLANE"),
            named_ref(f"DrivePinFloor@{crankshaft}", "PLANE"),
            label=f"MHA-VN-044 #{k} pressed to DrivePinFloor",
            verify=(seat_pin, seat_pin_o),
        )
        await parallel_mate(
            adapter,
            named_ref(f"Right Plane@{seat_pin}", "PLANE"),
            cs_right,
            label=f"MHA-VN-044 #{k} rotational closure",
            verify=(seat_pin, seat_pin_o),
        )

    # Crank handle: rides the arm's PIVOT pin (Axis2@arm), NOT the crankshaft --
    # a real pin joint. Coaxial to the arm pivot bore + an axial seat (its
    # Z-normal Right/origin plane -- the brass collar face -- COINCIDENT to
    # the arm's HandleSeat datum, the plate's SOUTH face at CRANK_ARM_Z0, so
    # the collar butts flush where it physically rides) + a parallel holding
    # the grip's rest orientation (the grip spin is immaterial, like a lag
    # screw). The seat WAS the last unsigned axial distance on the crank chain
    # (278.29 to the plate's CrankAxisSeat): adding it teleported the handle
    # to the far branch, and the flip recovery re-solved by wrenching the
    # FREE-swinging plate +8 in z, dragging the whole crank family off pose
    # (caught live 2026-07-05; the pose ledger would have refused the save).
    # Coincident has one branch -- and referencing the ARM keeps the seat
    # internal to the swinging rig.
    hd_o = _org(adapter, handle)
    await coincident_mate(
        adapter,
        named_ref(f"Axis1@{handle}", "AXIS"),
        named_ref(f"Axis2@{arm}", "AXIS"),
        label="handle coaxial on arm pivot",
        verify=(handle, hd_o),
    )
    await coincident_mate(
        adapter,
        named_ref(f"Right Plane@{handle}", "PLANE"),
        named_ref(f"HandleSeat@{arm}", "PLANE"),
        label="handle axial seat on arm south face (coincident, flip-free)",
        # Both normals read machine -z in the composed handle/arm poses; pin
        # the alignment rather than trusting the closest-solution heuristic.
        alignment="aligned",
        verify=(handle, hd_o),
    )
    await parallel_mate(
        adapter,
        named_ref(f"Top Plane@{handle}", "PLANE"),
        named_ref(f"Right Plane@{arm}", "PLANE"),
        label="handle anti-spin (grip rest)",
        verify=(handle, hd_o),
    )
    # The bonded ferrule and butt cup ride the handle rigidly (epoxy).
    for bonded, what in (
        (handle_ferrule, "MHA-DT-034 ferrule"),
        (handle_cup, "MHA-DT-035 butt cup"),
    ):
        await lock_mate(
            adapter,
            named_ref(f"Front Plane@{bonded}", "PLANE"),
            named_ref(f"Front Plane@{handle}", "PLANE"),
            label=f"{what} bonded to the handle",
        )
    # MHA-DT-032 mirrors the handle's pin joint on the same arm datums: coaxial
    # on the arm pivot, shoulder seated on HandleSeat (ArmSeat's normal is
    # machine +z, HandleSeat's reads -z), and a parallel holding the slot's
    # clocking (immaterial, like the handle's grip spin).  The arm's Right
    # Plane is machine XZ, the identity-placed screw's Top Plane.
    hs_o = _org(adapter, handle_screw)
    await coincident_mate(
        adapter,
        named_ref(f"Axis1@{handle_screw}", "AXIS"),
        named_ref(f"Axis2@{arm}", "AXIS"),
        label="MHA-DT-032 coaxial on arm pivot",
        verify=(handle_screw, hs_o),
    )
    await coincident_mate(
        adapter,
        named_ref(f"ArmSeat@{handle_screw}", "PLANE"),
        named_ref(f"HandleSeat@{arm}", "PLANE"),
        label="MHA-DT-032 shoulder seated on arm outboard face",
        alignment="anti_aligned",
        verify=(handle_screw, hs_o),
    )
    await parallel_mate(
        adapter,
        named_ref(f"Top Plane@{handle_screw}", "PLANE"),
        named_ref(f"Right Plane@{arm}", "PLANE"),
        label="MHA-DT-032 slot clocking",
        verify=(handle_screw, hs_o),
    )

    # =============== cone platform swing (p1 disengage DOF) ==============
    # The platform is the swing bracket: the whole cone set -- post, shaft,
    # gears, tip block -- swings horizontally out of mesh about the plate's
    # tip-end vertical pivot (ch.12, p.18). Pin the floated plate with three
    # locating drivers that leave ONLY the rotation about the pivot axis
    # ("swing pivot", Axis1): a Top-plane distance (upright + height) and the
    # pivot axis's distance to the Right/Front planes (plan X/Z). The swing
    # angle itself stays FREE (its ANGLE drive spec -- today's ENGAGED incline
    # dihedral -- is recorded into the DOF manifest). The riders seat on the
    # plate below and follow the swing, so the validated 20-gear mesh is
    # untouched in `rest`; drag the plate to articulate the disengage.
    plat_o = _org(adapter, platform)
    await distance_driver(
        adapter,
        named_ref(f"Top Plane@{platform}", "PLANE"),
        named_ref("Top Plane", "PLANE"),
        plat_o[1],
        label=f"cone-platform height d={abs(plat_o[1]):.2f}",
        verify=(platform, plat_o),
    )
    await distance_driver(
        adapter,
        named_ref(f"Axis1@{platform}", "AXIS"),
        named_ref("Right Plane", "PLANE"),
        plat_o[0],
        label=f"cone-platform pivot-X d={abs(plat_o[0]):.2f}",
        verify=(platform, plat_o),
    )
    await distance_driver(
        adapter,
        named_ref(f"Axis1@{platform}", "AXIS"),
        named_ref("Front Plane", "PLANE"),
        plat_o[2],
        label=f"cone-platform pivot-Z d={abs(plat_o[2]):.2f}",
        verify=(platform, plat_o),
    )
    # The swing is a FREED operational DOF (user item 1): its drive spec is
    # recorded, not authored -- the plate swings freely between the gear mesh
    # and the stop screw. Same mechanism as the crank spin below.
    await angle_driver(
        adapter,
        named_ref(f"Right Plane@{platform}", "PLANE"),
        named_ref("Right Plane", "PLANE"),
        INCLINE_DEG,
        label=f"cone-platform swing PARK driver (p1, engaged a={INCLINE_DEG:.2f}; "
        f"freed in default build)",
        verify=(platform, plat_o),
        free_dof_key="cone_swing",
    )

    # Pivot post rides the plate through its physical two-fastener pattern.
    # The rederived v2 casting is turned exactly 180 about machine Y: its foot
    # remains down, its undirected cone journal line remains collinear, and its
    # asymmetric crank boss points to the photographed side.  The turn swaps
    # the physical east/west holes, hence the cross-paired axes below.
    post_o = _org(adapter, pivot_post)
    await coincident_mate(
        adapter,
        named_ref(f"Top Plane@{pivot_post}", "PLANE"),
        named_ref(f"PlateTop@{platform}", "PLANE"),
        label="cone-post seats on the plate (Top <-> PlateTop)",
        verify=(pivot_post, post_o),
    )
    await coincident_mate(
        adapter,
        named_ref(f"mount east@{pivot_post}", "AXIS"),
        named_ref(f"post mount west@{platform}", "AXIS"),
        label="cone-post local-east to platform-west mounting axis",
        verify=(pivot_post, post_o),
    )
    await coincident_mate(
        adapter,
        named_ref(f"mount west@{pivot_post}", "AXIS"),
        named_ref(f"post mount east@{platform}", "AXIS"),
        label="cone-post local-west to platform-east mounting axis",
        verify=(pivot_post, post_o),
    )
    # I22: each MHA-VN-031 clamps the post to the plate.
    for screw in post_screws:
        await lock_mate(
            adapter,
            named_ref(f"Front Plane@{screw}", "PLANE"),
            named_ref(f"Front Plane@{pivot_post}", "PLANE"),
            label=f"{screw} clamped in the post counterbore",
        )

    # Cone shaft revolute in the black pivot post: coincident axes + the
    # thrust collar ON the post's north boss face (#914) -- the contact that
    # reacts the tip adjuster's preload.  Its spin is driven by the 16T -> 64T
    # mesh, not pinned here.
    a_s = component_transform(adapter, cone_shaft)
    cone_o = [a_s[9] * 1000.0, a_s[10] * 1000.0, a_s[11] * 1000.0]
    cone_axis_dir = [a_s[6], a_s[7], a_s[8]]  # image of local Z = inclined shaft axis
    await coincident_mate(
        adapter,
        named_ref(f"Axis1@{cone_shaft}", "AXIS"),
        named_ref(f"journal axis@{pivot_post}", "AXIS"),
        label="cone-shaft radial",
        verify=(cone_shaft, cone_o),
    )
    collar_face = named_ref(f"CollarFace@{cone_shaft}", "PLANE")
    boss_face = named_ref(f"BossNorth@{pivot_post}", "PLANE")
    _telemetry.info(
        f"collar seat by name: {collar_face.name} on {boss_face.name}",
        collar_face=collar_face.name,
        boss_face=boss_face.name,
    )
    await coincident_mate(
        adapter,
        collar_face,
        boss_face,
        label="cone-shaft collar on the post's north boss face",
        verify=(cone_shaft, cone_o),
    )
    # Tip block: aligned to the shaft/adjuster axis (which the post + platform
    # already carry) + an axial seat + a parallel anti-spin against the
    # PLATFORM (not the spinning shaft).  It stands directly on PlateTop (user
    # ruling 2026-09-29): its height falls out of the coaxial (plate + axis
    # height = drive height, asserted at import), so the foot's contact with
    # the plate is proven by that assert and the interference gate, not a
    # mate.  It follows the p1 swing through the shaft.
    tb_o = _org(adapter, tip_block)
    tb_axial = sum((tb_o[k] - cone_o[k]) * cone_axis_dir[k] for k in range(3))
    await coincident_mate(
        adapter,
        named_ref(f"Axis1@{tip_block}", "AXIS"),
        named_ref(f"Axis1@{cone_shaft}", "AXIS"),
        label="tip-block adjuster axis aligned to shaft tip",
        verify=(tip_block, tb_o),
    )
    await distance_driver(
        adapter,
        named_ref(f"Front Plane@{tip_block}", "PLANE"),
        named_ref(f"Front Plane@{cone_shaft}", "PLANE"),
        tb_axial,
        label=f"tip-block axial seat d={tb_axial:.2f}",
        verify=(tip_block, tb_o),
    )
    await parallel_mate(
        adapter,
        named_ref(f"Right Plane@{tip_block}", "PLANE"),
        named_ref(f"Right Plane@{platform}", "PLANE"),
        label="tip-block anti-spin (rides the plate)",
        verify=(tip_block, tb_o),
    )
    # MHA-VN-030 clamps the block to the plate: locked to the platform, whose
    # hold-down hole is the block's station.  Its origin (the head's bearing
    # face) must sit on the counterbore floor, under the block's foot tap.
    await lock_mate(
        adapter,
        named_ref(f"Front Plane@{tip_holddown}", "PLANE"),
        named_ref(f"Front Plane@{platform}", "PLANE"),
        label=f"{tip_holddown} clamped in the platform hold-down counterbore",
    )
    _hd_o = _org(adapter, tip_holddown)
    _tb_o = _org(adapter, tip_block)
    _tap = (
        _tb_o[0] + TIP_FOOT_TAP_OFFSET_X * ROT_Y_INCLINE[0][0],
        _tb_o[2] + TIP_FOOT_TAP_OFFSET_X * ROT_Y_INCLINE[0][2],
    )
    if (
        abs(_hd_o[0] - _tap[0]) > 1e-4
        or abs(_hd_o[2] - _tap[1]) > 1e-4
        or abs(_hd_o[1] - (Y_BASE_TOP + PLAT_HOLDDOWN_CBORE_DEPTH)) > 1e-4
    ):
        raise AssertionError(
            f"hold-down screw at {_hd_o} is not on the counterbore floor under the "
            f"tip block's foot tap (x, z) {_tap}"
        )
    # --- tip end-play stack (item 5): collar | adjuster | pinch screw ---------
    # MHA-VN-016 is locked one unchanged feeler off T006. Its FINISHED round
    # bore has positive clearance: the bore axis is displaced toward +X and
    # seats on both retained -X BACK arcs, never concentric zero-clearance.
    # InstalledShaftAxis is the named parallel axis -loaded_offset from the
    # actual collar bore. Right-plane clocking keeps the dog on the D-flat.
    collar_o = _org(adapter, tip_collar)
    collar_axial = sum((collar_o[k] - cone_o[k]) * cone_axis_dir[k] for k in range(3))
    await coincident_mate(
        adapter,
        named_ref(f"InstalledShaftAxis@{tip_collar}", "AXIS"),
        named_ref(f"Axis1@{cone_shaft}", "AXIS"),
        label="tip collar two-ended loaded ROUND BACK-arc seating",
        verify=(tip_collar, collar_o),
    )
    await distance_driver(
        adapter,
        named_ref(f"Top Plane@{tip_collar}", "PLANE"),
        named_ref(f"Front Plane@{cone_shaft}", "PLANE"),
        collar_axial,
        label=f"tip collar axial seat d={collar_axial:.2f}",
        verify=(tip_collar, collar_o),
    )
    await parallel_mate(
        adapter,
        named_ref(f"Right Plane@{tip_collar}", "PLANE"),
        named_ref(f"Right Plane@{cone_shaft}", "PLANE"),
        label="tip collar set screw on the D-flat",
        verify=(tip_collar, collar_o),
    )
    # The adjuster screws into the BLOCK's tapped bore: coaxial on the block's
    # adjuster axis + an axial seat off the block's Front plane + an anti-spin
    # (the pinch screw locks its turn in reality).
    adj_o = _org(adapter, tip_adjuster)
    adj_axial = sum((adj_o[k] - tb_o[k]) * cone_axis_dir[k] for k in range(3))
    await coincident_mate(
        adapter,
        named_ref(f"ScrewAxis@{tip_adjuster}", "AXIS"),
        named_ref(f"Axis1@{tip_block}", "AXIS"),
        label="adjuster in the block counterbore",
        verify=(tip_adjuster, adj_o),
    )
    await distance_driver(
        adapter,
        named_ref(f"Top Plane@{tip_adjuster}", "PLANE"),
        named_ref(f"Front Plane@{tip_block}", "PLANE"),
        adj_axial,
        label=f"adjuster axial set d={adj_axial:.2f}",
        verify=(tip_adjuster, adj_o),
    )
    await parallel_mate(
        adapter,
        named_ref(f"Right Plane@{tip_adjuster}", "PLANE"),
        named_ref(f"Right Plane@{tip_block}", "PLANE"),
        label="adjuster anti-spin (pinch-locked)",
        verify=(tip_adjuster, adj_o),
    )
    # The pinch screw journals in the block's cross-bore (Axis2, the named
    # "pinch axis"): coaxial + its head seat a half-block off the block's Right
    # plane + an anti-spin.
    pin_o = _org(adapter, pinch_screw)
    await coincident_mate(
        adapter,
        named_ref(f"ScrewAxis@{pinch_screw}", "AXIS"),
        named_ref(f"Axis2@{tip_block}", "AXIS"),
        label="pinch screw in the cross-bore",
        verify=(pinch_screw, pin_o),
    )
    await distance_driver(
        adapter,
        named_ref(f"Top Plane@{pinch_screw}", "PLANE"),
        named_ref(f"Right Plane@{tip_block}", "PLANE"),
        TIP_BLOCK_X / 2.0,
        label=f"pinch head seat d={TIP_BLOCK_X / 2.0:.2f}",
        verify=(pinch_screw, pin_o),
    )
    await parallel_mate(
        adapter,
        named_ref(f"Front Plane@{pinch_screw}", "PLANE"),
        named_ref(f"Front Plane@{tip_block}", "PLANE"),
        label="pinch-screw anti-spin (slot upright)",
        verify=(pinch_screw, pin_o),
    )
    # The head must bear on the +X face, where the near jaw is drilled clear;
    # on the -X face it would thread into its own jaw and never pinch.
    _pin_o = _org(adapter, pinch_screw)
    _pin_x = sum(
        (_pin_o[k] - _tb_o[k]) * ROT_Y_INCLINE[0][k] for k in range(3)
    )
    if abs(_pin_x - TIP_BLOCK_X / 2.0) > 1e-4:
        raise AssertionError(
            f"pinch screw head face sits at block x {_pin_x:.4f}, not on the +X "
            f"clearance face (x {TIP_BLOCK_X / 2.0:.4f})"
        )
    # The 64T crank-drive gear and the 20 cone gears are one rigid stepped
    # cluster KEYED to the cone shaft -- each via coaxial + axial seat + parallel
    # anti-spin (see _key_to_shaft), replacing its lock with no fix/lock/tuned
    # angle. The 64T uses its Axis2 central axis, the cone gears their Axis1.
    # The 64T seat is a contact: its Front plane IS its south face (the blank
    # is sketched on Front and extruded +z by the face width, and
    # _place_on_shaft puts that origin face/2 south of the gear's centre), so
    # Front coincident with the collar's north plane sits the gear ON it.
    cone_axis = named_ref(f"Axis1@{cone_shaft}", "AXIS")
    await _key_to_shaft(
        adapter,
        gear64,
        "Axis2",
        cone_axis,
        cone_shaft,
        cone_o,
        cone_axis_dir,
        "64T",
        seat_plane="CollarEndPlane",
    )
    # Key the T120 seed, then REPLICATE stations 1..19 from it (#228): one
    # CopyWithMates2 per station with the axial-seat slot laddered by
    # SEAT_PITCH, then re-point the copy at its own T-configuration. The
    # slice is fully defined (3 mates, all external to the shared shaft), so
    # copies land ON the mates -- no landing recipe needed (contrast the
    # channel's free-DOF put+driver dance). Measured ~0.7 s/copy vs ~8.7 s
    # authored (memory/v018-perf-review.md, cone-gear ladder GO).
    await _key_to_shaft(
        adapter,
        seed_cg,
        "Axis1",
        cone_axis,
        cone_shaft,
        cone_o,
        cone_axis_dir,
        f"cone-gear T{seed_teeth:03d}",
    )
    # Cheap slot-shape audit (one IComponent2::GetMates, not a 48-second full
    # MateGroup tree walk): _key_to_shaft just authored [coaxial, axial dim,
    # anti-spin], all external to the shared shaft.  GetMates order is not by
    # itself the CopyWithMates2 slot contract, so the first copy's pre-config
    # landing below is the decisive runtime tripwire for the slot/side map.
    seed_dump = component_mate_dump(adapter, seed_cg)
    if len(seed_dump) != 3:
        raise RuntimeError(
            f"cone seed slice carries {len(seed_dump)} mates, expected 3: {seed_dump}"
        )
    dims = [(i, row) for i, row in enumerate(seed_dump) if row["mm"] is not None]
    if len(dims) != 1 or dims[0][0] != 1:
        raise RuntimeError(
            "cone seed slice drifted: expected [coaxial, axial dim, anti-spin],"
            f" got {seed_dump}; re-derive the CopyWithMates2 slot map"
        )
    dim_slot, seed_dim = dims[0]
    seed_arr = list(component_transform(adapter, seed_cg))
    d_seed = sum(
        (seed_arr[9 + k] * 1000.0 - cone_o[k]) * cone_axis_dir[k] for k in range(3)
    )
    if abs(seed_dim["mm"] - abs(d_seed)) > 0.01:
        raise RuntimeError(
            f"cone seed axial dim {seed_dim['mm']:.3f} != measured"
            f" |d|={abs(d_seed):.3f} -- the seat formulation moved"
        )
    if d_seed <= 0:
        raise RuntimeError(
            f"cone seed axial seat d={d_seed:.2f} -- the ladder assumes"
            " positive stations marching one way off the shaft's Front"
            " plane (copies land on the seed's side)"
        )
    # The seed authors flip=True on the inclined frame (measured: the first
    # epoch-3 build failed the old flip=False assert at d=37.30). The Repeat
    # path RESETS a re-valued dim to flip=False, but the CORRECT idiom re-points
    # the axial-seat slot with Repeat=false + NewEntityToMateTo (the shared
    # shaft's Front plane, the same reference the seed's seat uses) and honours
    # FlipDimension=seed_flip on that slot directly -- so each copy lands on the
    # seed's side in the copy call itself, no post-copy ModifyDefinition heal
    # (measured 2026-07-10, MIXED Repeat array; _cwm.py module doc).
    seed_flip = bool(seed_dim["flipped"])
    shaft_front = resolve_entity(
        adapter, named_ref(f"Front Plane@{cone_shaft}", "PLANE")
    )
    seed_mates = component_mate_count(adapter, seed_cg)
    # The status REFERENCE is the seed's own reading, NOT fully-defined: the
    # cone cluster deliberately rides freed DOF (crank spin, platform swing --
    # cone-gear is in verify's drive-train allowed-under-constrained set), so
    # at this build point a correctly keyed gear reads whatever the seed
    # reads. A copy must merely MATCH it (an unsolvable copied mate flips a
    # component to over/no-solution without moving it, which a pose read
    # alone misses).
    seed_status = component_constrained_status(adapter, seed_cg)
    with _telemetry.span("cone.replicate", copies=19):
        for j in range(1, 20):
            teeth = _config.cone_teeth(j)
            cfg = f"T{teeth:03d}"
            values = [0.0] * 3
            values[dim_slot] = (d_seed + j * SEAT_PITCH) / 1000.0
            # Re-point ONLY the axial-seat slot to the shared shaft's Front
            # plane (Repeat=false) so FlipDimension=seed_flip is honoured on it;
            # the coaxial + anti-spin slots keep the seed's shaft references
            # (Repeat=true) untouched -- the measured mixed-array idiom.
            repeat = [True] * 3
            repeat[dim_slot] = False
            new_ents: list = [None] * 3
            new_ents[dim_slot] = shaft_front
            flips = [False] * 3
            flips[dim_slot] = seed_flip
            copy_with_mates(
                adapter,
                [seed_cg],
                3,
                values,
                flips=flips,
                repeat=repeat,
                new_entities=new_ents,
            )
            cg = f"dt-cone-gear-{j + 1}"
            if (
                _early_bound(adapter.currentModel, "IAssemblyDoc").GetComponentByName(
                    cg
                )
                is None
            ):
                raise RuntimeError(
                    f"cone-gear copy {j}: expected deterministic instance {cg!r}"
                    " after CopyWithMates2, but it is absent"
                )
            # Validate the CopyWithMates2 slot map before a configuration swap
            # or later solve can obscure its landing.  Wrong slot/side maps put
            # copy 1 at the seed station or two axial distances away.
            got = list(component_transform(adapter, cg))
            target = [
                seed_arr[9 + k] * 1000.0 + j * SEAT_PITCH * cone_axis_dir[k]
                for k in range(3)
            ]
            err = math.dist([v * 1000.0 for v in got[9:12]], target)
            if err > 0.05:
                raise RuntimeError(
                    f"cone-gear copy {j} landed {err:.3f} mm off its station"
                    " pre-config -- the CopyWithMates2 slot order on this"
                    " seat/model does not match [coaxial, axial dim, anti-spin]"
                    " (or the flip side moved); re-derive the slot map"
                )
            model = adapter.currentModel
            _early_bound(model, "IAssemblyDoc").GetComponentByName(
                cg
            ).ReferencedConfiguration = cfg
            if teeth in TIP_TEETH:  # the four hard yellow tip gears
                await apply_component_color(adapter, cg, MUNTZ_YELLOW)
            cone_gears.append((teeth, cg))
        # No post-copy flip heal: FlipDimension=seed_flip was honoured in each
        # copy call (Repeat=false on the axial-seat slot), so the copied dims
        # already sit on the seed's side. The end-state validation below (pose
        # + status + mate count) is the tripwire if any copy landed wrong.
        model = adapter.currentModel
        rebuilt = adapter._attempt(lambda: model.EditRebuild3(), default=None)
        if rebuilt is False or rebuilt is None:
            faults = whats_wrong(adapter, model)
            hard_faults = [
                f"{name} [code={code}]" for name, code, warning in faults if not warning
            ]
            warnings = [
                f"{name} [code={code}]" for name, code, warning in faults if warning
            ]
            _telemetry.error(
                "cone-gear replication rebuild rejected",
                rebuild_result=repr(rebuilt),
                hard_faults=hard_faults,
                warnings=warnings,
            )
            raise RuntimeError(
                "EditRebuild3 after cone-gear replication returned "
                f"{rebuilt!r}; hard faults: {hard_faults or ['none reported']}; "
                f"warnings: {warnings or ['none reported']}"
            )
    # Validate the production way (CopyWithMates2's return LIES): pose on the
    # seed's transform translated one seat pitch per station, full mate set,
    # fully-defined status, the configuration actually taken; then re-anchor
    # the pose ledger (copies were never place_component'd).
    for j, (teeth, cg) in enumerate(cone_gears):
        if j == 0:
            continue
        tgt = [
            seed_arr[9 + k] * 1000.0 + j * SEAT_PITCH * cone_axis_dir[k]
            for k in range(3)
        ]
        assert_component_placed(
            adapter,
            cg,
            tgt,
            [list(seed_arr[0:3]), list(seed_arr[3:6]), list(seed_arr[6:9])],
        )
        got_cfg = str(
            _early_bound(model, "IAssemblyDoc")
            .GetComponentByName(cg)
            .ReferencedConfiguration
        )
        if got_cfg != f"T{teeth:03d}":
            raise RuntimeError(
                f"{cg}: configuration {got_cfg!r}, expected T{teeth:03d}"
            )
        got = component_mate_count(adapter, cg)
        if got != seed_mates:
            raise RuntimeError(
                f"{cg}: {got} mates, seed has {seed_mates} -- the copy dropped mates"
            )
        status = component_constrained_status(adapter, cg)
        if status != seed_status:
            raise RuntimeError(
                f"{cg}: constrained status {status}, seed reads"
                f" {seed_status} -- a copied mate is unsolvable or"
                " over-defining"
            )
        reledger_to_solved(adapter, cg)
    # 16T pinion (keyed to the crank) drives the 64T -> the cone cluster turns.
    # The cone keying above replicated 19 gears with CopyWithMates2, and a
    # copy's solve can WANDER the free cone train's spin off its inserted
    # phase (the cylinder ladder below documents the same parked-pose
    # wander). The gear mate authored NEXT records the CURRENT relative
    # phase forever -- and through the 64:16 ratio a 0.5 deg cone wander
    # misregisters the mesh by 2 deg of pinion seed (2026-07-14
    # interference-gate catch: 1.1 mm^3, an effective +1.9 deg seed error).
    # Measure both spins against design and rotate the cone train back so
    # the mate freezes the DESIGNED phase. The rigid family rotation keeps
    # every kept mate satisfied (all are family-internal), and the train's
    # world spin is the deliberately-free DOF, so the solve holds the put.
    _u = (SIN_I, 0.0, COS_I)  # cone axis (world)
    _exd = (COS_I, 0.0, -SIN_I)  # design image of the 64T's part +X

    def _pinion_spin_off() -> float:
        """Pinion spin off its design pose (deg, CCW about +z)."""
        r = component_transform(adapter, pinion)
        sd = math.radians(-PINION_SEED_DEG)
        return math.degrees(
            math.atan2(
                math.cos(sd) * r[1] - math.sin(sd) * r[0],
                math.cos(sd) * r[0] + math.sin(sd) * r[1],
            )
        )

    def _gear64_spin_off() -> float:
        """64T spin off its design pose (deg, CCW about +u)."""
        c = component_transform(adapter, gear64)[0:3]
        cross = (
            _exd[1] * c[2] - _exd[2] * c[1],
            _exd[2] * c[0] - _exd[0] * c[2],
            _exd[0] * c[1] - _exd[1] * c[0],
        )
        return math.degrees(
            math.atan2(
                sum(x * a for x, a in zip(cross, _u)),
                sum(e * a for e, a in zip(_exd, c)),
            )
        )

    def _seed_error() -> float:
        """Wander as an equivalent pinion-seed offset (deg): a 64T slip
        counts 4x through the external 64:16 mesh."""
        return -(_pinion_spin_off() + 4.0 * _gear64_spin_off())

    _err = _seed_error()
    log(
        f"crank-mesh phase at authoring: pinion {_pinion_spin_off():+.4f}, "
        f"64T {_gear64_spin_off():+.4f} deg off design -> seed error "
        f"{_err:+.4f} deg"
    )
    if abs(_err) > 0.02:
        _dl = math.radians(_err / 4.0)  # cone-train correction, CCW about +u
        _c, _s = math.cos(_dl), math.sin(_dl)
        _R = [
            [
                _c + (1 - _c) * _u[0] * _u[0],
                (1 - _c) * _u[0] * _u[1] - _s * _u[2],
                (1 - _c) * _u[0] * _u[2] + _s * _u[1],
            ],
            [
                (1 - _c) * _u[1] * _u[0] + _s * _u[2],
                _c + (1 - _c) * _u[1] * _u[1],
                (1 - _c) * _u[1] * _u[2] - _s * _u[0],
            ],
            [
                (1 - _c) * _u[2] * _u[0] - _s * _u[1],
                (1 - _c) * _u[2] * _u[1] + _s * _u[0],
                _c + (1 - _c) * _u[2] * _u[2],
            ],
        ]  # w' = R w: Rodrigues, CCW about +u
        _p0 = [
            v / 1000.0 for v in cone_station(GEAR64_CENTRE_STATION)
        ]  # axis point at the recentered 64T (m)
        _sh = [_p0[k] - sum(_R[k][j] * _p0[j] for j in range(3)) for k in range(3)]

        def _spun(a: list[float]) -> list[float]:
            out = list(a)
            for i in range(3):  # rows = local axes' world images
                for k in range(3):
                    out[i * 3 + k] = sum(a[i * 3 + j] * _R[k][j] for j in range(3))
            for k in range(3):  # translation (metres)
                out[9 + k] = sum(_R[k][j] * a[9 + j] for j in range(3)) + _sh[k]
            return out

        with suspend_automatic_assembly_rebuilds(adapter):
            for _nm in [cone_shaft, gear64] + [n for _, n in cone_gears]:
                put_component_pose(
                    adapter, _nm, _spun(list(component_transform(adapter, _nm)))
                )
        await force_rebuild(adapter)
        _err2 = _seed_error()
        log(f"crank-mesh phase corrected: seed error {_err:+.4f} -> {_err2:+.4f} deg")
        if abs(_err2) > 0.10:
            raise RuntimeError(
                f"crank-mesh phase correction did not hold: seed error"
                f" {_err2:+.4f} deg after the cone-train put (was"
                f" {_err:+.4f}) -- the free train reverted the pose"
            )
        # The puts spun the family AFTER its ledger entries were recorded
        # (insert / the reledger_to_solved above); a correction big enough
        # to matter (>~0.06 deg of cone spin) would fail the save-time
        # assert_pose_ledger rotation check as pose drift. Re-anchor them.
        for _nm in [cone_shaft, gear64] + [n for _, n in cone_gears]:
            reledger_to_solved(adapter, _nm)
    await gear_mate(
        adapter,
        named_ref(f"Axis2@{pinion}", "AXIS"),
        named_ref(f"Axis2@{gear64}", "AXIS"),
        _config.machine("gear_train", "crank_drive_ratio"),
        label="16T:64T crank drive",
    )

    # The cylinder set is a SANDWICH (book ch.13): brass gears alternate with the
    # black connecting rods, each riding a cam attached to the gear on its right.
    # Those rods/cams live in the channel subassembly, so on the bare arbor each
    # gear sits one stack PITCH from its neighbour (gear face 3 mm + cam to 6.5 ->
    # Z_PITCH ~= 7.06). The axial locators ladder each station j * Z_PITCH off
    # the SEED's Front Plane -- one anchored reference + one meaningful pitch
    # constant; only gear 0 anchors the stack's reference end to the world
    # datum. Radially each runs free (coincident, leaving its spin) and meshes
    # its cone gear k at ratio [120-6k : 120] -- the gear mate is the sole
    # rotational constraint, so it holds the tuned tooth phase without nudging
    # the gear (validated keystone, M6).
    # Station 0 (the seed) gets its two authored locators; stations 1..19 are
    # 2-mate COPIES of it laddered off its anchor plane via Repeat=False +
    # NewEntityToMateTo, then their spin PUT at design -- the copy parks
    # ~9.12 deg off (parked-pose wander), and with no spin-referencing mate
    # copied a plain Transform2 put holds through rebuilds. Every station's
    # gear mesh (the seed's included) is authored FRESH afterwards: it records
    # the tuned tooth phase from the current pose and carries its per-station
    # ratio natively -- no tree walk, no ratio edit. (Measured: copy ~1.2 s +
    # put ~0.1 s + fresh mesh ~2.5 s vs ~7.8 s per authored station --
    # diagnostics/diag_cwm_cylinder.py + the 2026-07-10 validation build.)
    seed_cyl = cyl_gears[0]
    seed_cyl_o = _org(adapter, seed_cyl)
    await coincident_mate(
        adapter,
        named_ref(f"Axis2@{seed_cyl}", "AXIS"),
        named_ref(f"Axis1@{arbor}", "AXIS"),
        label="cylinder-gear 0 radial",
        verify=(seed_cyl, seed_cyl_o),
    )
    await distance_driver(  # anchor the stack's reference end once
        adapter,
        named_ref(f"Front Plane@{seed_cyl}", "PLANE"),
        named_ref("Front Plane", "PLANE"),
        seed_cyl_o[2],
        label=f"cylinder-gear 0 axial anchor d={abs(seed_cyl_o[2]):.2f}",
        verify=(seed_cyl, seed_cyl_o),
    )
    # Slot audit, two layers (codex #240; a MateGroup tree walk here -- the
    # cone path's external_mate_rows -- would cost ~100 s, more than the
    # ladder saves). Layer 1, SHAPE (cheap, one IComponent2::GetMates): the
    # seed slice must be exactly the two mates above with the dim second.
    # GetMates order is not the CopyWithMates2 slot contract (that is
    # MateGroup tree order), so layer 2 validates the ACTUAL slot source at
    # runtime: every copy's pre-put translation is checked in the loop below
    # -- a mis-slotted Values array re-values the live dim to 0.0 (the _cwm
    # contract) and the copy lands on station 0, failing copy 1 immediately.
    dump = component_mate_dump(adapter, seed_cyl)
    if len(dump) != 2 or dump[0]["mm"] is not None or dump[1]["mm"] is None:
        raise RuntimeError(
            f"cylinder seed slice drifted: {dump} -- expected"
            " [dimension-less radial, axial dim]; re-derive the ladder's"
            " slot map before replicating"
        )
    cylinder_dim_slot = 1
    if os.environ.get("HARMONIC_CYLINDER_SLOT_DEBUG"):
        rows = mates_with_owners(adapter, {"dt-cylinder-gear", "dt-cylinder-gear-shaft"})
        seed_rows = [row for row in rows if seed_cyl in row["instances"]]
        external = external_mate_rows(seed_rows, {seed_cyl})
        dim_slots = [
            i for i, row in enumerate(external) if row["type"] == "MateDistanceDim"
        ]
        log(
            "  DEBUG cylinder external slots: "
            f"{[(row['name'], row['type'], sorted(row['owners'])) for row in external]}"
        )
        if len(external) != 2 or len(dim_slots) != 1:
            raise RuntimeError(
                "cylinder debug slot survey expected two external mates and one dim;"
                f" got {[(row['name'], row['type']) for row in external]}"
            )
        cylinder_dim_slot = dim_slots[0]
    seed_cyl_arr = list(component_transform(adapter, seed_cyl))
    # Every copy's axial slot re-points at the SEED's Front Plane, laddered
    # j * Z_PITCH -- ONE resolve_entity for the whole drum (re-resolving the
    # previous station per copy measured ~1.5 s x 19, half the ladder's win)
    # The face-centred Ry180 changes the distance side: with alignment repaired,
    # FlipDimension=True lands copy 1 at seed-Z - pitch instead of + pitch, so
    # this ladder's measured side is False. The authored seed mate references
    # the assembly Front Plane (+Z), while each copy re-points that slot to the
    # Ry180 seed's Front Plane (-Z). The reference normal changed, so
    # CopyWithMates2 also needs FlipAlignment=True.
    # Without it SolidWorks creates red Distance32, code 47, reporting reversed
    # plane alignment; changing FlipDimension alone leaves the same 5.597 mm miss.
    seed_front = resolve_entity(adapter, named_ref(f"Front Plane@{seed_cyl}", "PLANE"))
    pending_cylinder_puts: list[tuple[str, list[float]]] = []
    with _telemetry.span("cylinder.replicate", copies=_config.active_count() - 1):
        for j in range(1, _config.active_count()):
            values = [0.0, 0.0]
            values[cylinder_dim_slot] = j * Z_PITCH / 1000.0
            repeat = [True, True]
            repeat[cylinder_dim_slot] = False
            new_entities: list = [None, None]
            new_entities[cylinder_dim_slot] = seed_front
            flips = [False, False]
            flip_alignments = [False, False]
            flip_alignments[cylinder_dim_slot] = True
            copy_with_mates(
                adapter,
                [seed_cyl],
                2,
                values,
                flips=flips,
                flip_alignments=flip_alignments,
                repeat=repeat,
                new_entities=new_entities,
            )
            new_name = f"dt-cylinder-gear-{j + 1}"
            if (
                _early_bound(adapter.currentModel, "IAssemblyDoc").GetComponentByName(
                    new_name
                )
                is None
            ):
                raise RuntimeError(
                    f"cylinder-gear copy {j}: expected deterministic instance"
                    f" {new_name!r} after CopyWithMates2, but it is absent"
                )
            # Layer-2 slot validation, BEFORE the put (which would mask the
            # translation until the closing solve snapped it back): the copy
            # must land translation-exact on its station off the re-valued
            # axial dim alone. A wrong slot/side lands it on station 0 or
            # 2 * the dim off -- fail on copy 1, naming the cause.
            got = list(component_transform(adapter, new_name))
            want = [
                seed_cyl_arr[9] * 1000.0,
                seed_cyl_arr[10] * 1000.0,
                seed_cyl_arr[11] * 1000.0 + j * Z_PITCH,
            ]
            err = math.dist([v * 1000.0 for v in got[9:12]], want)
            if err > 0.05:
                # CopyWithMates2 returns no usable status. Ask the same API
                # behind What's Wrong only on the failure path, so the build
                # names a red mate and its swFeatureError_e immediately without
                # adding a document scan to every successful copy. IMate2's
                # state dump distinguishes alignment from dimension-side errors.
                hard_errors = [
                    (name, code)
                    for name, code, is_warning in whats_wrong(
                        adapter, adapter.currentModel
                    )
                    if not is_warning
                ]
                mate_state = component_mate_dump(adapter, new_name)
                raise RuntimeError(
                    f"cylinder-gear copy {j} landed {err:.3f} mm off its"
                    f" station pre-put: got {[round(v * 1000.0, 3) for v in got[9:12]]},"
                    f" want {[round(v, 3) for v in want]}, dim slot"
                    f" {cylinder_dim_slot}; SolidWorks hard errors"
                    f" {hard_errors or 'none'}, copied mate state {mate_state} --"
                    " the CopyWithMates2 slot order on"
                    " this seat/model does not match the audited"
                    " [radial, axial dim] map (or the flip side moved);"
                    " re-derive the slot map (external_mate_rows)"
                )
            put = list(seed_cyl_arr)
            put[11] += j * Z_PITCH / 1000.0
            pending_cylinder_puts.append((new_name, put))
            cyl_gears.append(new_name)
        # Let every CopyWithMates2 call finish before correcting the copies'
        # unconstrained spin. A later copy used to wake the solver and wander
        # earlier transforms, so the v0.20.0 ladder paid for repeated corrections.
        # Transform the complete bank once, then author the fresh gear mates below.
        with _telemetry.span("cylinder.pose_bank", copies=len(pending_cylinder_puts)):
            with suspend_automatic_assembly_rebuilds(adapter):
                for name, put in pending_cylinder_puts:
                    put_component_pose(adapter, name, put)
    gear_mates_batch(
        adapter,
        (
            (
                named_ref(f"Axis1@{cone_gears[j][1]}", "AXIS"),
                named_ref(f"Axis2@{cyl}", "AXIS"),
                [cone_gears[j][0], 120],
                f"cone T{cone_gears[j][0]:03d}:cyl120 ch{j:02d}",
            )
            for j, cyl in enumerate(cyl_gears)
        ),
        label="cylinder.mesh_bank",
    )
    # Validate the production way and re-anchor the pose ledger (copies were
    # never place_component'd): pose on the seed's transform one stack pitch
    # per station -- rotation included, the put-held tooth phase -- full mate
    # set, and the seed's own constrained reading (the drum rides the freed
    # crank train, so a correctly mated copy reads whatever the seed reads).
    # Mate-count expectation follows the STAR topology: every copy carries
    # its own 3 mates (radial + axial + mesh), each copy's axial references
    # the SEED's anchor plane -- so the seed reads 3 + one per copy.
    want_seed = 3 + (len(cyl_gears) - 1)
    seed_cyl_mates = component_mate_count(adapter, seed_cyl)
    if seed_cyl_mates != want_seed:
        raise RuntimeError(
            f"{seed_cyl}: {seed_cyl_mates} mates, expected {want_seed}"
            " (radial + axial anchor + fresh mesh + one laddered axial"
            " per copy)"
        )
    seed_cyl_status = component_constrained_status(adapter, seed_cyl)
    for j, cyl in enumerate(cyl_gears):
        if j == 0:
            continue
        tgt = [
            seed_cyl_arr[9] * 1000.0,
            seed_cyl_arr[10] * 1000.0,
            seed_cyl_arr[11] * 1000.0 + j * Z_PITCH,
        ]
        assert_component_placed(
            adapter,
            cyl,
            tgt,
            [list(seed_cyl_arr[0:3]), list(seed_cyl_arr[3:6]), list(seed_cyl_arr[6:9])],
        )
        got = component_mate_count(adapter, cyl)
        if got != 3:
            raise RuntimeError(
                f"{cyl}: {got} mates, expected 3 (radial + laddered axial"
                " + fresh mesh) -- the copy dropped or grew mates"
            )
        status = component_constrained_status(adapter, cyl)
        if status != seed_cyl_status:
            raise RuntimeError(
                f"{cyl}: constrained status {status}, seed reads"
                f" {seed_cyl_status} -- a copied or fresh mate is unsolvable"
                " or over-defining"
            )
        reledger_to_solved(adapter, cyl)

    # =============== alignment-pinion swing group (p2 engage DOF) ==============
    # The two straps + the pinion drum swing as ONE group to mesh the cylinder
    # train (ch.25, p.66); parked DISENGAGED (p.68 "gap").  Option E-a pins
    # both straps to the torque shaft, so the shaft swings with them in the
    # blocks' pivot bores.  Statics first: the pivot blocks are base-bolted
    # mounts at their authored transforms -> locked once to the fixed seed
    # arbor. The lift rod is NOT static any more (PR8): it journals in the
    # blocks' raised west bores as a revolute below, carrying the cams + lever.
    for blk in pinion_blocks:
        await _lock_static(adapter, blk, arbor)
    # The shaft's axis sits on the blocks' pivot bores and its station is the
    # authored one (the cone-platform pivot idiom: an axis held off two
    # assembly planes); only its spin is left, and the pin tie to the front
    # strap below takes that.
    ps_o = _org(adapter, pivot_shaft)
    await distance_driver(
        adapter,
        named_ref(f"Axis1@{pivot_shaft}", "AXIS"),
        named_ref("Right Plane", "PLANE"),
        ps_o[0],
        label=f"torque shaft axis X d={abs(ps_o[0]):.2f}",
        verify=(pivot_shaft, ps_o),
    )
    await distance_driver(
        adapter,
        named_ref(f"Axis1@{pivot_shaft}", "AXIS"),
        named_ref("Top Plane", "PLANE"),
        ps_o[1],
        label=f"torque shaft axis Y d={abs(ps_o[1]):.2f}",
        verify=(pivot_shaft, ps_o),
    )
    await distance_driver(
        adapter,
        named_ref(f"Front Plane@{pivot_shaft}", "PLANE"),
        named_ref("Front Plane", "PLANE"),
        ps_o[2],
        label=f"torque shaft axial d={abs(ps_o[2]):.2f}",
        verify=(pivot_shaft, ps_o),
    )
    await _lock_static(adapter, spring, arbor)
    for scr in (block_screw, spring_foot_screw, pedestal_screw):
        await _lock_static(adapter, scr, arbor)
    block_instances = await grid_component_pattern(
        adapter,
        [block_screw],
        axis1="x",
        spacing1_mm=_BLOCK_SCREW_XZ[1][0] - _BLOCK_SCREW_XZ[0][0],
        instances1=2,
        axis2="z",
        spacing2_mm=_BLOCK_SCREW_XZ[2][1] - _BLOCK_SCREW_XZ[0][1],
        instances2=2,
        direction1=PatternDirection.REVERSE,
        direction2=PatternDirection.FORWARD,
        label="pinion block-screw grid",
    )
    assert_pattern_targets(
        adapter,
        block_instances,
        [[x, BLOCK_TOP_Y, z] for x, z in _BLOCK_SCREW_XZ[1:]],
        IDENTITY,
        "pinion block-screw grid",
    )
    pedestal_target = [
        _PEDESTAL_SCREW_XZ[1][0],
        Y_BASE_TOP + ARBOR_PED_FLANGE_T,
        _PEDESTAL_SCREW_XZ[1][1],
    ]
    pedestal_instances = await linear_component_pattern(
        adapter,
        [pedestal_screw],
        axis="z",
        spacing_mm=_PEDESTAL_SCREW_XZ[1][1] - _PEDESTAL_SCREW_XZ[0][1],
        instances=2,
        label="arbor pedestal hold-down pattern",
    )
    assert_pattern_targets(
        adapter,
        pedestal_instances,
        [pedestal_target],
        IDENTITY,
        "arbor pedestal hold-down pattern",
    )
    # Front strap: revolute on the torque shaft (coincident pivot bore + axial
    # seat) -- the swing DOF. The parked-lean ANGLE driver is a FREED
    # operational DOF (PR8 item 3, ``free_dof_key``): its spec is recorded
    # into the DOF manifest instead of authored, so the saved model swings
    # the drum in/out of mesh by hand.
    fb, bb = pinion_brackets["front"], pinion_brackets["back"]
    fb_o = _org(adapter, fb)
    await coincident_mate(
        adapter,
        named_ref(f"Axis1@{fb}", "AXIS"),
        named_ref(f"Axis1@{pivot_shaft}", "AXIS"),
        label="pinion swing radial",
        verify=(fb, fb_o),
    )
    await distance_driver(
        adapter,
        named_ref(f"Front Plane@{fb}", "PLANE"),
        named_ref("Front Plane", "PLANE"),
        fb_o[2],
        label=f"pinion swing axial d={abs(fb_o[2]):.2f}",
        verify=(fb, fb_o),
    )
    await angle_driver(
        adapter,
        named_ref(f"Right Plane@{fb}", "PLANE"),
        named_ref("Right Plane", "PLANE"),
        180.0 - abs(STRAP_LEAN_DEG),
        label=f"pinion swing PARK driver (p2, disengaged a={abs(STRAP_LEAN_DEG):.2f})",
        verify=(fb, fb_o),
        free_dof_key="pinion_swing",
        # The strap's origin IS the pivot bore, ON the torque-shaft axis: the
        # angle is satisfied at EITHER branch and the origin readback is blind to
        # it (#154). The arbor bore at the strap top is the off-axis witness.
        #
        # The DIHEDRAL is 180 - |lean|, NOT |lean|: the strap is inserted
        # machine-handed as Ry(180) . Rz(lean) (`_strap_rows` above), so its
        # Right-plane normal is flipped to -X and its angle to the assembly Right
        # plane is the SUPPLEMENT of the physical lean -- the same 180 - tilt rule
        # spin_driver documents for parts whose normals flip. Targeting |lean|
        # solved the far branch, 180 - 2*|lean| ~ 155 deg off (an 84 mm witness
        # drift the deferred replay caught at release preflight -- #211 regression).
        witness_local=[0.0, STRAP_C2C, 0.0],
    )
    # Back strap: the same revolute on the shaft + a parallel anti-spin to the
    # front strap (both inserted at the same lean, so their Right planes are
    # parallel) -- the rigid-group tie, semantic (no lock).
    bb_o = _org(adapter, bb)
    await coincident_mate(
        adapter,
        named_ref(f"Axis1@{bb}", "AXIS"),
        named_ref(f"Axis1@{pivot_shaft}", "AXIS"),
        label="pinion back strap radial",
        verify=(bb, bb_o),
    )
    await distance_driver(
        adapter,
        named_ref(f"Front Plane@{bb}", "PLANE"),
        named_ref("Front Plane", "PLANE"),
        bb_o[2],
        label=f"pinion back strap axial d={abs(bb_o[2]):.2f}",
        verify=(bb, bb_o),
    )
    await parallel_mate(
        adapter,
        named_ref(f"Right Plane@{bb}", "PLANE"),
        named_ref(f"Right Plane@{fb}", "PLANE"),
        label="pinion back strap anti-spin (rigid with front)",
        verify=(bb, bb_o),
        # Same on-axis-origin blindness as the front strap (#154): parallel is
        # satisfied at either lean, so witness the arbor bore at the strap top.
        witness_local=[0.0, STRAP_C2C, 0.0],
    )
    # Option E-a set pins: the shaft's pin holes and the straps' cross holes
    # run along the same direction (their local X), and each pair shares an
    # axis: the shaft's holes sit at the fit-up stack's strap stations, which
    # this pose is (dt_pinion_pivot_shaft_spec).  The pin tie is the back strap's
    # own rigid-group idiom -- the shaft's Right plane parallel to the front
    # strap's.  The front strap's swing is the freed DOF, so the shaft now
    # turns with the group in the block bores.  Its origin is on the swing
    # axis (#154 blindness), so a point on the pin-hole axis at the shaft's
    # surface witnesses the phase.
    shaft_x = component_transform(adapter, pivot_shaft)[0:3]
    strap_x = component_transform(adapter, fb)[0:3]
    if abs(abs(sum(a * b for a, b in zip(shaft_x, strap_x))) - 1.0) > 1e-6:
        raise AssertionError(
            "torque-shaft pin holes are not phased to the straps' cross holes"
        )
    await parallel_mate(
        adapter,
        named_ref(f"Right Plane@{pivot_shaft}", "PLANE"),
        named_ref(f"Right Plane@{fb}", "PLANE"),
        label="torque shaft pinned to the front strap (E-a set pin)",
        verify=(pivot_shaft, ps_o),
        witness_local=[STRAP_PIVOT_BORE / 2.0, 0.0, 0.0],
    )
    # Cam-follower pins (PR8): pressed in each strap's blind WEST-EDGE seat
    # (Axis3), so they RIDE the swing group -- coaxial + the seat-bottom axial
    # split off the strap's Right plane (which contains the seat bottom's
    # station along the pin axis) + a spin pin at the inserted dihedral (the
    # pin is axisymmetric, so the angle is cosmetic, but the DOF must close
    # for the release 0-DOF closure proof).
    for tag in ("front", "back"):
        cpin = cam_pins[tag]
        br = pinion_brackets[tag]
        cp_o = _org(adapter, cpin)
        await coincident_mate(
            adapter,
            named_ref(f"Axis1@{cpin}", "AXIS"),
            named_ref(f"Axis3@{br}", "AXIS"),
            label=f"cam follower {tag} pressed in the edge seat",
            verify=(cpin, cp_o),
        )
        await distance_driver(
            adapter,
            named_ref(f"Front Plane@{cpin}", "PLANE"),
            named_ref(f"Right Plane@{br}", "PLANE"),
            _FPIN_S0,
            label=f"cam follower {tag} seat depth d={_FPIN_S0:.2f}",
            verify=(cpin, cp_o),
        )
        # Anti-spin plane pair: pin TOP (normal = pin local Y, rotates with the
        # spin) vs bracket FRONT (normal = machine z). Pin RIGHT vs bracket
        # RIGHT is DEGENERATE here -- the bracket's Right normal lies ALONG the
        # pin axis, so that dihedral reads 90 for every spin angle; SolidWorks
        # flags the no-op mate as redundant on BOTH parties (caught by the
        # over-constrained gate). This pair reads 90 at insert (mid-range, no
        # flip singularity) and genuinely pins the spin.
        a_cp = component_transform(adapter, cpin)
        a_br = component_transform(adapter, br)
        cp_phase = math.degrees(
            math.acos(
                max(-1.0, min(1.0, sum(a_cp[3 + k] * a_br[6 + k] for k in range(3))))
            )
        )
        await angle_driver(
            adapter,
            named_ref(f"Top Plane@{cpin}", "PLANE"),
            named_ref(f"Front Plane@{br}", "PLANE"),
            cp_phase,
            label=f"cam follower {tag} anti-spin (a={cp_phase:.2f})",
            verify=(cpin, cp_o),
        )
    # Option E-a set pins (MHA-VN-033): each is inserted on its strap's cross
    # hole -- coaxial with its shaft hole -- and locked to that strap, so it
    # rides the freed swing.
    for tag in ("front", "back"):
        await lock_mate(
            adapter,
            named_ref(f"Front Plane@{strap_pins[tag]}", "PLANE"),
            named_ref(f"Front Plane@{pinion_brackets[tag]}", "PLANE"),
            label=f"strap pin {tag} locked to its strap",
        )
    # Lift rod REVOLUTE (PR8): coaxial in the front block's raised west bore
    # + an axial seat; its spin -- the lever/cam input -- is a FREED
    # operational DOF (``free_dof_key``), recorded into the DOF manifest, not
    # authored. Top@rod vs the assembly RIGHT plane reads 90 at insert
    # (mid-range, no flip singularity).
    lr_o = _org(adapter, lift_rod)
    await coincident_mate(
        adapter,
        named_ref(f"Axis1@{lift_rod}", "AXIS"),
        named_ref(f"Axis1@{pinion_blocks[0]}", "AXIS"),
        label="lift rod revolute in the block west bores",
        verify=(lift_rod, lr_o),
    )
    await distance_driver(
        adapter,
        named_ref(f"Front Plane@{lift_rod}", "PLANE"),
        named_ref("Front Plane", "PLANE"),
        lr_o[2],
        label=f"lift rod axial d={abs(lr_o[2]):.2f}",
        verify=(lift_rod, lr_o),
    )
    await angle_driver(
        adapter,
        named_ref(f"Top Plane@{lift_rod}", "PLANE"),
        named_ref("Right Plane", "PLANE"),
        LIFT_ROD_PARK_DEG,
        label=(
            "lift rod spin PARK driver (cams parked ecc-down, "
            f"a={LIFT_ROD_PARK_DEG:.2f})"
        ),
        verify=(lift_rod, lr_o),
        free_dof_key="pinion_cam",
        # The rod origin sits on the spin axis: an off-axis witness pins the
        # branch (a +/-LEVER_TILT_DEG mirror would re-phase the cams).
        witness_local=[0.0, 5.0, 0.0],
    )
    # Eccentric cams: pinned to the rod (set pin) -- coaxial on the rod's axis
    # + an axial seat + an angle anti-spin at CAM_ROD_PHASE_DEG to the rod (the
    # rod is phased to the lever's pin hole, the cams stay ecc-down in the
    # world), so the set spins as one with the rod.
    for tag in ("front", "back"):
        cam = pinion_cams[tag]
        cam_o = _org(adapter, cam)
        await coincident_mate(
            adapter,
            named_ref(f"Axis1@{cam}", "AXIS"),
            named_ref(f"Axis1@{lift_rod}", "AXIS"),
            label=f"pinion cam {tag} on the lift rod",
            verify=(cam, cam_o),
        )
        _cam_ax = cam_o[2] - lr_o[2]
        await distance_driver(
            adapter,
            named_ref(f"Front Plane@{cam}", "PLANE"),
            named_ref(f"Front Plane@{lift_rod}", "PLANE"),
            _cam_ax,
            label=f"pinion cam {tag} set-pin axial d={_cam_ax:.2f}",
            verify=(cam, cam_o),
        )
        await angle_driver(
            adapter,
            named_ref(f"Right Plane@{cam}", "PLANE"),
            named_ref(f"Right Plane@{lift_rod}", "PLANE"),
            CAM_ROD_PHASE_DEG,
            label=(f"pinion cam {tag} set-pin anti-spin (a={CAM_ROD_PHASE_DEG:.2f})"),
            verify=(cam, cam_o),
            witness_local=[0.0, 5.0, 0.0],
        )
    # Lever: clamped on the rod's front end -- coaxial + axial + a parallel
    # tie to the ROD (the rod carries the photographed 10-degree parked phase,
    # so the match-drilled MHA-DT-030 holes stay coaxial) -- so it spins WITH the
    # rod: dragging the lever in the saved free model turns the cams.
    lev_o = _org(adapter, lever)
    await coincident_mate(
        adapter,
        named_ref(f"Axis1@{lever}", "AXIS"),
        named_ref(f"Axis1@{lift_rod}", "AXIS"),
        label="lever clamp hub on the lift rod",
        verify=(lever, lev_o),
    )
    await distance_driver(
        adapter,
        named_ref(f"Front Plane@{lever}", "PLANE"),
        named_ref(f"Front Plane@{lift_rod}", "PLANE"),
        lev_o[2] - lr_o[2],
        label=f"lever axial seat d={abs(lev_o[2] - lr_o[2]):.2f}",
        verify=(lever, lev_o),
    )
    await parallel_mate(
        adapter,
        named_ref(f"Right Plane@{lever}", "PLANE"),
        named_ref(f"Right Plane@{lift_rod}", "PLANE"),
        label="lever clamp phase (parallel to the rod: coaxial pin holes)",
        verify=(lever, lev_o),
        witness_local=[0.0, LEVER_LEN, 0.0],
    )
    # MHA-DT-030 locked to the rod: on the rod's pin-hole axis (Axis2), centred
    # across it (Right planes coincident -- both contain the rod axis), and
    # anti-spun about its own axis by a Top-plane parallel.  Rigid with the
    # rod, it turns with the freed lift-rod spin.
    lp_o = _org(adapter, lever_pin)
    await coincident_mate(
        adapter,
        named_ref(f"Axis1@{lever_pin}", "AXIS"),
        named_ref(f"Axis2@{lift_rod}", "AXIS"),
        label="MHA-DT-030 on the lift rod's pin-hole axis",
        verify=(lever_pin, lp_o),
    )
    await coincident_mate(
        adapter,
        named_ref(f"Right Plane@{lever_pin}", "PLANE"),
        named_ref(f"Right Plane@{lift_rod}", "PLANE"),
        label="MHA-DT-030 centred across the lift rod",
        verify=(lever_pin, lp_o),
    )
    await parallel_mate(
        adapter,
        named_ref(f"Top Plane@{lever_pin}", "PLANE"),
        named_ref(f"Top Plane@{lift_rod}", "PLANE"),
        label="MHA-DT-030 anti-spin (parallel to the rod)",
        verify=(lever_pin, lp_o),
        witness_local=[0.0, 0.0, 1.0],
    )
    # Pinion drum: journaled in the straps' top bores -- coaxial on the front
    # strap's Axis2 + an axial seat. Its free spin (real: the zeroing input) is
    # pinned by an angle anti-spin at the inserted dihedral vs the leaning strap
    # (the tilted analogue of the 16T's tooth-in-gap anti-spin); riding the
    # strap, the pin survives the engage swing.
    ap_o = _org(adapter, align_pinion)
    await coincident_mate(
        adapter,
        named_ref(f"Axis1@{align_pinion}", "AXIS"),
        named_ref(f"Axis2@{fb}", "AXIS"),
        label="alignment-pinion journaled in the straps",
        verify=(align_pinion, ap_o),
    )
    await distance_driver(
        adapter,
        named_ref(f"Front Plane@{align_pinion}", "PLANE"),
        named_ref("Front Plane", "PLANE"),
        ap_o[2],
        label=f"alignment-pinion axial d={abs(ap_o[2]):.2f}",
        verify=(align_pinion, ap_o),
    )
    a_ap = component_transform(adapter, align_pinion)
    a_fb = component_transform(adapter, fb)
    ap_phase = math.degrees(
        math.acos(max(-1.0, min(1.0, sum(a_ap[k] * a_fb[k] for k in range(3)))))
    )
    await angle_driver(
        adapter,
        named_ref(f"Right Plane@{align_pinion}", "PLANE"),
        named_ref(f"Right Plane@{fb}", "PLANE"),
        ap_phase,
        label=f"alignment-pinion anti-spin (parked a={ap_phase:.2f})",
        verify=(align_pinion, ap_o),
    )
    # Steel arbor (PR7 item 14): pressed through the drum on the same strap
    # bore axis -- coaxial + an axial seat (Front-plane distance, invariant
    # under the z-parallel engage swing) + a fixed 65-degree anti-spin phase
    # to the drum.  The phase clocks its local-Y cross-hole onto the grip rod;
    # an off-axis head witness distinguishes the two angle-mate branches.
    arb_o = _org(adapter, pinion_arbor)
    await coincident_mate(
        adapter,
        named_ref(f"Axis1@{pinion_arbor}", "AXIS"),
        named_ref(f"Axis2@{fb}", "AXIS"),
        label="pinion arbor journaled in the straps",
        verify=(pinion_arbor, arb_o),
    )
    await distance_driver(
        adapter,
        named_ref(f"Front Plane@{pinion_arbor}", "PLANE"),
        named_ref("Front Plane", "PLANE"),
        arb_o[2],
        label=f"pinion arbor axial d={abs(arb_o[2]):.2f}",
        verify=(pinion_arbor, arb_o),
    )
    await angle_driver(
        adapter,
        named_ref(f"Right Plane@{pinion_arbor}", "PLANE"),
        named_ref(f"Right Plane@{align_pinion}", "PLANE"),
        HANDLE_TILT_DEG,
        label=f"pinion arbor anti-spin (pressed phase={HANDLE_TILT_DEG:.2f})",
        verify=(pinion_arbor, arb_o),
        witness_local=[0.0, ARBOR_HEAD_DIA / 2.0, ARBOR_HEAD_CENTER_Z],
    )
    # The separate grip crossrod is bonded in MHA-DT-022's reamed integral head
    # (R1).  A LOCK records that authored relative pose with no
    # branches or added DOF, so the engage swing carries the complete crank.
    await lock_mate(
        adapter,
        named_ref(f"Front Plane@{grip_crossrod}", "PLANE"),
        named_ref(f"Front Plane@{pinion_arbor}", "PLANE"),
        label="grip crossrod bonded in the integral arbor head",
    )
    # R1a: the collar is spring-pinned to the arbor, so it LOCKs to it and
    # rides the engage swing with no added DOF.
    await lock_mate(
        adapter,
        named_ref(f"Front Plane@{arbor_collar}", "PLANE"),
        named_ref(f"Front Plane@{pinion_arbor}", "PLANE"),
        label="arbor collar spring-pinned to the arbor",
    )
    # Its pin is line-to-line in both 1/16 holes (no interference row, as the
    # strap pins) and rides the collar.
    await lock_mate(
        adapter,
        named_ref(f"Front Plane@{collar_pin}", "PLANE"),
        named_ref(f"Front Plane@{arbor_collar}", "PLANE"),
        label="collar spring pin locked in the collar",
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
    # The crank angle is a FREED operational DOF (``free_dof_key``): NOT
    # authored -- its resolved spec is recorded into the DOF manifest for the
    # transient kinematics replays -- leaving the crank (and the whole
    # keyed/geared train it pins) free to spin: the working kinematic model.
    # The BDC dihedral + handle verify target feed the recorded spec.
    await angle_driver(
        adapter,
        named_ref(f"Right Plane@{arm}", "PLANE"),
        named_ref("Right Plane", "PLANE"),
        crank_angle,
        label=f"crank angle PARK driver (reproducibility lock; freed in default "
        f"build; BDC a={crank_angle:.2f})",
        verify=(handle, handle_o),
        free_dof_key="crank_angle",
    )

    # Certify the AS-BUILT model: FOUR freed operational DOF -- the crank
    # spin, the platform swing, the pinion engage swing and the lift-rod/cam
    # spin (all recorded above). Each names its family: the aggregate count
    # alone passes on the crank chain even with the others pinned (codex
    # review 2026-07-04). All other checks run on the as-built model.
    #
    # These gates read a fully solved model, and run on the one produced by
    # save's final deep rebuild (``resolve=False``) rather than on a deep
    # rebuild of their own before the explode: two ForceRebuild3(False) of
    # this assembly cost 78 s + 62 s p50 (n=89, 30 d to 2026-09-27). The
    # state is the same as-built model: the explode adds no mates (only
    # exploded-view steps), and create_drive_train_explode proves the
    # collapse restores every component's presentation AND operational
    # transform to 1e-9 -- so the constrained statuses, the interference set
    # and the 64T clearance are read on the identical mate system and poses,
    # which is also exactly the state being saved. Soundness reads the same
    # gate on the saved (exploded-and-collapsed) model after one shared
    # rebuild, also ``resolve=False``. The DOF manifest (the recorded free-DOF
    # specs) is published by the save only after the assembly it describes is
    # saved and fingerprinted.
    def _certify_as_built(solved_adapter) -> None:
        assert_free_dof_necessity(
            solved_adapter,
            4,
            resolve=False,
            required_stems=(
                "dt-crankshaft",
                "dt-cone-swing-platform",
                "dt-pinion-bracket",
                "dt-pinion-lift-rod",
            ),
        )
        check_no_interference(
            solved_adapter,
            allowed_pairs=allowed_interference_pairs(ASM_NAME),
        )
        # The positive control for crank_boss_rim's analytic 64T clearances.
        gear64_post_measure.measure(
            solved_adapter, post_origin=tuple(_PPOST), gear_offset=GEAR64_POST_OFFSET
        )
        # Same final solved/saved model: finite signed BACK-arc seating and
        # all20 native material shadows over the manufactured closed P1 range.
        installed_axis, bank_thrust = tip_collar_air.installation_acceptances()
        native_tip_collar_air.measure(
            solved_adapter, collar_component=tip_collar, shaft_component=cone_shaft,
            installed=installed_axis, bank_thrust=bank_thrust,
        )

    # Title-block identity for the assembly drawing (draw_dt_drive_train_assembly.py):
    # assembly_title_properties supplies the Title/Generator and TOL_* cells
    # finalize_drawing requires without consulting the part registry;
    # released component drawing (the BOM has no material/finish columns).
    apply_custom_properties(
        adapter,
        {
            **assembly_title_properties(ASM_NAME),
            "Revision Description": "Initial release",
            "Material": "SEE COMPONENT DRAWINGS",
            "Material Specification": "SEE COMPONENT DRAWINGS",
            "Finish": "SEE COMPONENT DRAWINGS",
            "Quantity": "1",
            "Drawn By": DRAWN_BY,
        },
    )
    # The collar's MHA-VN-033 leaves with the arbor it pins; the strap pins stay.
    # The explode is authored in both drawing configurations: the package's
    # small exploded views reference Default Simplified.
    _require_collar_pin_in_collar_hole(adapter, collar_pin, arbor_collar)
    author_in_drawing_configurations(
        adapter,
        ASM_NAME,
        lambda configuration: create_drive_train_explode(
            adapter, {collar_pin: COLLAR_PIN_ROLE}, configuration
        ),
    )
    return await save_assembly_and_images(
        adapter, ASM_NAME, solved_gates=_certify_as_built, dof_manifest=True
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
