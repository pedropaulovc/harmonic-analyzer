r"""Reproduction script: drive-train subassembly (book ch. 11-13, 30).

The complete drive train in machine coordinates (assembly origin = base
origin; base top face at y = 50.8. The v2 post's 33.368-mm journal height
above the 6.35-mm swing plate fixes the drive plane at y = 90.518):

* cone set: a TRUE CONE -- all 20 gears AND the 64T crank-drive gear
  seated perpendicular to the stepped shaft (p.18/p.20 photos), the
  shaft inclined in PLAN and carried at BOTH ends ON the cone swing
  platform (p.18: the wedge plate labelled "pivot" at its tip): big end
  journaled in the green pivot post, thin 1/32" tip end-play located by the
  external spacer and cup-ended adjuster carried in the black tip block (the GT tip post at world
  (-81, 105, +102), realized at station
  185). The plate pivots about a vertical axis at its TIP end, so the
  whole set swings horizontally out of mesh as one unit -- the p1
  disengage DOF; pivoting at the tip gives the big gears (which need
  the most working-depth separation) the largest throw.
* cylinder drum: 20 identical 120T gears spinning freely on the stationary
  arbor along Z at (-60.394, 90.518), carried by pedestals at both ends. The
  complete arbor/support bank follows the fixed-post mechanism recenter;
  each asymmetric gear/cam sandwich is turned end-for-end while its local +Y
  cosine phase remains up (pp. 66-67).
* crankshaft along Z in the merged green column (cone-pivot-post: big-end
  journal + crank pedestal, ONE casting riding the swing plate), ABOVE the
  64T (ch30 GT:
  the crank axle triangulates to y 144.8 -- a near-vertical 16T:64T mesh):
  crank arm + handle at the front and the 16T pinion inboard. (The T12
  removable crank chain wheel -- ch. 23, the roller chain rides its m2 teeth
  -- is NOT placed here: paper-drive now owns the whole crank->paper chain
  drive, so the single crank wheel lives there, avoiding a duplicate at the
  top level -- codex #189 :605. MHA-024 is not inserted in this as-machined
  assembly model: MHA-020 and MHA-026 retain their coaxial straight pilot
  holes here, while the released drawings require their shared 1:48 taper to
  be match-reamed at assembly.)
* alignment pinion (ch. 25): the 42T zeroing drum + its swing rig, parked
  DISENGAGED, inboard of the drum and level with the drive axis (GT).

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
crank pair at DP 25.7311); the alignment pinion is RESTORED (ch30 GT) at the
level-inboard placement (see the constants block).

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
150 mm annotation reconciles as gear stack 131.6 + 64T face 8 + air.
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
cap 0.88. The 16T crank pinion mesh is DIFFERENT (2026-07-14 rederive): on its
near-VERTICAL line of centres (the crank sits above the 64T, ch30 GT)
the radial interleave is ~constant across the face -- the crossing
manifests as LATERAL flank misregistration instead, which no radial
backoff can clear (the retired PEN16 backoff left the tip circles 0.29
apart, a visible air gap vs the engaged pair in ch12
page002_img02/img06). The 64T is now cut as a linearized helix at the
incline angle with a backlash allowance (build_crank_drive_gear.py --
a crossed-helical pair, gear helix = shaft angle, pinion straight), and
the pinion stands PROUD of the pivot post's casting face (img06: no
relief pocket in the casting -- the pinion's face fills the static
casting-to-T120 span, ~0.55 clearance each side, spanning ~96% of the
64T row; the span-fit assert below keeps it off both neighbours). The
pair engages at 87% of working depth: MESH16_C2C =
R64 + R16 + slack 0.25, the deepest zero-collision pose over a full
crank-pitch phase sweep (diagnostics/crossed_mesh_study.py). The
perpendicular 64T presents its contact tooth r*cos(alpha)*sin(i) north
of its centre (alpha = the contact azimuth from the in-plane
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
chain, the cone cluster and the 20 cylinder
gears are inserted on their exact machine transforms (so mate
flip-recovery has a clean reference and the tuned tooth phases are
preserved) and joined by real kinematic joints. The crankshaft and the
cone shaft each get a revolute (coincident axis-to-axis + an axial plane
distance); the crank arm/handle/T12 wheel/16T pinion are keyed to the
crankshaft and the 64T + 20 cone gears keyed to the cone shaft (lock
mates); a 16T:64T gear mate drives the cone cluster from the crank, and
each cylinder gear meshes its cone gear k at ratio [120-6k : 120]. The
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

    uv run python cad\scripts\build_drive_train_assembly.py
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
    apply_summary_info,
    check,
    force_rebuild,
    log,
    run_build,
)
from _drawing_marks import DRAWN_BY
from _transforms import ROT_Y_180, compose_rows, euler_from_rows
from cone_pivot_post_installation import (
    CHANNEL_Z0,
    DRUM_X,
    GEAR_AXIS_SHIFT,
    MECHANISM_Z_SHIFT,
    POST_ROTATION_Y_DEG,
)
from _assembly import (
    angle_driver,
    assembly_title_properties,
    apply_component_color,
    assert_component_placed,
    assert_free_dof_necessity,
    assert_pattern_targets,
    check_no_interference,
    coincident_mate,
    component_transform,
    distance_driver,
    gear_mate,
    gear_mates_batch,
    linear_component_pattern,
    grid_component_pattern,
    lock_mate,
    named_ref,
    parallel_mate,
    PatternDirection,
    place_component,
    reledger_to_solved,
    reset_dof_manifest,
    save_assembly_and_images,
    suspend_automatic_assembly_rebuilds,
    whats_wrong,
    write_dof_manifest,
)
from _interference_contracts import allowed_interference_pairs

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

ASM_NAME = "drive-train"

Y_BASE_TOP = 50.8  # harmonic-base top face
Y_DRIVE = Y_BASE_TOP + 6.35 + 33.368  # 90.518: v2 casting's journal axis
# The manually rederived cone-pivot-post-v2 is the harder source than the old
# GT centreline fit: its foot sits on the 1/4-in platform and its cast-in
# journal is 33.368 above that seat. The resulting drive line cascades into
# the arbor pedestals, channel cams and connecting rods below.

DP_TRAIN = _config.machine(
    "gear_train", "diametral_pitch"
)  # cad/config/machine.yaml (DIMENSIONS.md ch12)
DP_CRANK = _config.machine("gear_train", "crank_drive_diametral_pitch")
ADDENDUM = 25.4 / DP_TRAIN  # 0.510 at DP 49.82

# The four smallest cone gears read "more yellow ... a harder metal" (ch.12 p.21):
# a high-zinc yellow metal (Muntz/manganese bronze). Tinted per-INSTANCE here (see
# apply_component_color / build_cone_gear.py rationale), the part stays brass.
MUNTZ_YELLOW = _config.palette("muntz_yellow")
TIP_TEETH = {int(c[1:]) for c in _config.materials().get("cone_tip_gear_configs", [])}
WORKING_DEPTH = 2.0 * ADDENDUM  # 1.020: full tooth interleave depth
RADIUS_STEP = 3.0 * 25.4 / DP_TRAIN  # 1.5295: pitch-radius step per 6 teeth
CONE_T120_PITCH_R = (
    (120.0 / DP_TRAIN) * 25.4 / 2.0
)  # 30.59: largest cone gear pitch radius

# Shared machine grid: the working train is recentered independently of the
# fixed post/carrier, along the post's unchanged inclined journal.
_DRUM_SEAT_NOMINAL = _config.machine(
    "cone_incline", "drum_seat_nominal_mm"
)  # 7.2204 (OD 62.2)
Z_PITCH = _DRUM_SEAT_NOMINAL * math.cos(
    math.asin(RADIUS_STEP / _DRUM_SEAT_NOMINAL)
)  # 7.0566: drum z-pitch
X_DRUM = DRUM_X
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
Z_DRUM0 = _config.machine("channels", "station_z0_mm")
# Shared station anchor. Cone seats, cylinder faces, and channels translate as
# one rigid family without re-indexing the j-to-j pairs.
if abs(Z_DRUM0 - CHANNEL_Z0) > 1e-9:
    raise AssertionError("channel station_z0 does not carry the fixed-post recenter")

# True-cone incline (M6.7, exact tracking -- see module docstring). Values are
# at the OD-62.2 / DP 49.82 re-anchor (was 21.10 deg at the retired DP 30).
SIN_I = RADIUS_STEP / Z_PITCH  # 0.21675
COS_I = math.sqrt(1.0 - SIN_I * SIN_I)  # 0.97623
TAN_I = SIN_I / COS_I
SEC_I = 1.0 / COS_I
INCLINE_DEG = math.degrees(math.asin(SIN_I))  # 12.5182
SEAT_PITCH = Z_PITCH * COS_I  # 6.8888: seat pitch along the shaft

CONE_FACE = 6.5  # M6.7 mesh packing (annotated 7 -- build_cone_gear.py)
GEAR64_FACE = 8.0
# Preserve the rederived gear centre while narrowing both axial faces equally.
# The 10 mm reference face is placement history, not current part geometry.
GEAR64_CENTRE_REFERENCE_FACE = 10.0
DRUM_FACE = 3.0  # cylinder gear face (gear z = 0..3, cam 3..6.5)
PINION_FACE = 10.8  # re-derived 2026-07-14: fills the casting-face -> T120
# span (0.32 wall / 0.30 T120 clearance, span-fit assert below); ch12
# page002_img06 shows the pinion proud of the casting spanning the 64T row
# (the old 12.0 "slightly wider than the drive gear's 10" was a low-
# confidence read and does not fit the span; 11.0 fit the LINE-OF-CENTRES
# overhang model but grazed the true T120 arc minimum once the tight fit
# dropped Y_CRANK -- the 2026-07-14 0.00 mm^3 interference-gate catch).
# = build_crank_pinion FACE_WIDTH.

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
DRUM_TIP_X = X_DRUM - (122.0 / DP_TRAIN) * 25.4 / 2.0  # -85.80 at DP 49.82
PEN_EDGE_SLACK = _config.fit(
    "cone_drum_oblique_mesh", "edge_slack_mm"
)  # cad/config/tolerances.yaml
PEN_MID = WORKING_DEPTH - PEN_EDGE_SLACK - (DRUM_FACE / 2.0) * TAN_I  # 0.565
X_PITCH = DRUM_TIP_X - ADDENDUM * SEC_I + PEN_MID  # -85.76 at DP 49.82


def cone_seat(j: int) -> tuple[float, float]:
    """(x, z) centre of cone gear j: pitch-projected x, r*sin(i) north."""
    r = CONE_T120_PITCH_R - RADIUS_STEP * j
    return X_PITCH - r * COS_I, Z_DRUM0 + Z_PITCH * j + r * SIN_I


# Cone shaft: pivot end at seat station -28.25 from the T120 centre
# (25 journal + half of the first 6.5 face -- build_cone_gear_shaft.py).
# CONE_ORIGIN stays the PIVOT END (station 0, the station datum); the physical
# shaft now runs FRONT_STUB further south (ch30 GT), so the part -- authored
# from its front stub end -- is PLACED at SHAFT_FRONT_STATION instead.
SHAFT_T120_STATION = 25.0 + CONE_FACE / 2.0  # 28.25
_GEAR_CONE_ORIGIN = [
    cone_seat(0)[0] - SHAFT_T120_STATION * SIN_I,
    Y_DRIVE,
    cone_seat(0)[1] - SHAFT_T120_STATION * COS_I,
]
# The post/carrier axis remains at its ch30-fitted world placement.  The gear
# family is translated GEAR_AXIS_SHIFT along that same infinite line.
CONE_ORIGIN = [
    _GEAR_CONE_ORIGIN[0] - GEAR_AXIS_SHIFT * SIN_I,
    Y_DRIVE,
    _GEAR_CONE_ORIGIN[2] - GEAR_AXIS_SHIFT * COS_I,
]
SHAFT_FRONT_STATION = -61.90686099792956
# = -build_cone_gear_shaft FRONT_STUB (asserted below). The enlarged integral
# journal runs through the v2 post's 42.011-mm-long inclined bore and stands
# 1.0 mm proud of its south face.


def cone_station(s: float) -> list[float]:
    """Machine point of the cone-shaft axis at station s (mm from pivot end)."""
    return [
        CONE_ORIGIN[0] + s * SIN_I,
        Y_DRIVE,
        CONE_ORIGIN[2] + s * COS_I,
    ]


# The corrected 2.8360-in v2 crank boss spans local z
# -21.3753..+50.6591. The 16T follows the shifted 64T row while the T12 chain
# plane remains photo-anchored, so the resulting axial gaps are intentionally
# unequal; the post station still fixes crank X and the pair DP.
POST_STATION = -39.90136099792956


# Exact-tracking self-check: the 20 mesh-derived seats lie on the shaft.
for _j in range(20):
    _x, _z = cone_seat(_j)
    _p = cone_station(SHAFT_T120_STATION + GEAR_AXIS_SHIFT + _j * SEAT_PITCH)
    if abs(_p[0] - _x) > 1e-9 or abs(_p[2] - _z) > 1e-9:
        raise AssertionError(f"cone seat {_j} off the shaft line: {(_x, _z)} vs {_p}")

# 64T crank-drive gear: perpendicular on the pivot journal, directly beside
# T120 (p.20).  Its station remains the rederived 19.9 mm centre; narrowing
# the face symmetrically increases the axial air to T120 and the post to 1.1 mm.
GEAR64_STATION = (
    SHAFT_T120_STATION - (CONE_FACE + GEAR64_CENTRE_REFERENCE_FACE) / 2.0 - 0.1
)  # 19.9
GEAR64_SEAT = cone_station(GEAR64_STATION + GEAR_AXIS_SHIFT)
R64 = (64.0 / DP_CRANK) * 25.4 / 2.0
R16 = (16.0 / DP_CRANK) * 25.4 / 2.0

# Crank: ABOVE the 64T (ch30 GT photogrammetry -- the crank axle triangulates
# to world (-122.84, 144.78, -189.1) +- 1.4: the pedestal axis of the +122
# photo layout, ~39 ABOVE the drive plane, a near-VERTICAL 16T:64T mesh).
# X_CRANK is the photo-pinned pedestal axis; Y_CRANK closes the mesh at a REAL
# engaged centre distance (2026-07-14 rederive, "crank-pinion and crank-drive
# gear are not meshing"): the crossed pair (crank machine-z, 64T plane on the
# 12.52-deg inclined shaft) engages at depth because the 64T's teeth are a
# TRUE 12.0-degree helix (boss-swept with twist, _gear.py) with a
# 0.15 backlash allowance (build_crank_drive_gear.py) -- matching the engaged
# pair in the ch12 closeups (page002_img02/img06). C2C = R64 + R16 + slack;
# slack 0.25 keeps a 1.0-deg zero-collision seed window over a full
# crank-pitch phase sweep of the exact tooth solids
# (diagnostics/crossed_mesh_study.py; tips reach 1.66 into the gaps, 87% of
# working depth). Re-arbitrated 2026-07-14 from the K=12-slice era's
# 0.40/0.60 -- the smooth swept flanks return the clearance the slice facets
# consumed, after the user flagged the visible slop. This RETIRES the PEN16
# radial-backoff block (C2C 40.446 left the tip circles 0.29 APART -- a
# literal air gap; its (FACE/2)*SIN_I "dive" term modeled the
# horizontal-mesh depth gradient, but on the near-vertical line of centres
# the radial interleave is ~constant across the face and the real constraint
# is LATERAL flank misregistration, which no radial backoff fixes and the
# helix + backlash do).
ADD16 = 25.4 / DP_CRANK  # crank-pinion addendum
MESH16_C2C_SLACK = _config.fit("crank_mesh", "c2c_slack_mm")  # 0.25, tolerances.yaml
MESH16_C2C = R64 + R16 + MESH16_C2C_SLACK
TIP16_C2C = R64 + R16 + 2.0 * ADD16
CRANK_MESH_DEPTH = TIP16_C2C - MESH16_C2C
# Depth band: above ~1.2*ADD (really engaged), below 2*ADD minus the root
# clearance floor (slack + 0.157*ADD16 of tip-to-root air stays positive).
if not 1.2 * ADD16 < CRANK_MESH_DEPTH < 2.0 * ADD16 - 0.1:
    raise AssertionError("crank pair mesh depth left its derived band")
X_CRANK = cone_station(POST_STATION)[0]  # -129.336: Ry180 v2 installation
Y_CRANK = Y_BASE_TOP + 6.35 + 72.7  # 129.850: v2 cast-in crank-axis height
_DX16 = (GEAR64_SEAT[0] - X_CRANK) * COS_I  # horizontal leg toward the
# crank (a plane-local magnitude: the azimuth convention below measures from
# the in-plane horizontal TOWARD the other axis, so it is chirality-free)
_DY16 = Y_CRANK - Y_DRIVE  # vertical leg in both gear planes
if abs(math.hypot(_DX16, _DY16) - MESH16_C2C) > 0.05:
    raise AssertionError("crank mesh centre distance drifted off the engaged c2c")
# Contact azimuths (from each gear's centre toward the other axis, in that
# gear's own plane, ccw from the in-plane horizontal). The 64T plane rides
# the inclined cone shaft; the 16T plane is a plain machine-Z section.
ALPHA64 = math.degrees(math.atan2(_DY16, _DX16))
ALPHA16 = math.degrees(math.atan2(_DY16, GEAR64_SEAT[0] - X_CRANK))
# (both horizontal legs run TOWARD the other axis and read positive -- the
# chirality-free plane-local convention; the CW spin sense is applied at the
# rot_z(-PINION_SEED_DEG) callsite)
# The 10.8-wide pinion stands north of the v2 casting's finite crank boss and
# is centred on the 64T contact row. The relocated cast-in axis removes the
# former T120-rim radial overlap; the exact boss/T12/pinion closure below owns
# the axial clearances.
_GEAR64_CONTACT_Z = GEAR64_SEAT[2] + R64 * math.cos(math.radians(ALPHA64)) * SIN_I
PINION_TOOTH_Z = _GEAR64_CONTACT_Z
# The pinion follows the recentered cone/64T row while the photo-anchored crank
# arm and T12 chain plane remain at their existing stations below.
# Tooth-in-gap phase seed, generalizing the old +11.25 half-pitch: the 64T is
# keyed at its authored phase (a tooth centred at azimuth 0 -- for the helical
# teeth that is the MID-FACE azimuth, the twist's symmetry plane), so its
# nearest tooth leads the contact azimuth by DELTA64; the pinion's gap must
# sit that same contact arc (scaled by R64/R16) past the contact on ITS side.
# At ALPHA = 0 this is exactly 11.25. The formula is then CENTRED in the
# zero-collision window: at the full-row band the helical twist biases the
# window negative of the formula (crossed_mesh_study seed sweep 2026-07-14 at
# the tight 0.15/0.25 fit: zero over [-1.90, -1.10] deg around it), so the
# shipped seed sits at the window centre, buying +-0.40 deg of margin against
# authoring-time phase wander -- 4x the 0.10-deg bound the authoring-time
# measure-and-correct block enforces below. Re-arbitrate BOTH terms with the
# study if the slack, band or backlash ever changes.
_TP64 = 360.0 / 64.0
DELTA64 = round(ALPHA64 / _TP64) * _TP64 - ALPHA64  # 1.57: 64T tooth lead
# The v2 post changed the crank-pair DP and therefore the tooth count's phase at
# the new line of centres.  Re-arbitrated against the exact solid study and the
# exact-solid phase sweep: -1.50 centres the recentered DP25.742 / 12-degree
# helix window with +-0.40-degree authoring margin.
MESH_WINDOW_CENTRE_DEG = -1.50
PINION_SEED_DEG = (
    (ALPHA16 + 180.0) - DELTA64 * (R64 / R16) - 22.5 / 2.0
) % 22.5 + MESH_WINDOW_CENTRE_DEG  # window-centred tooth-in-gap

ARBOR_SOUTH_Z = -90.0 + MECHANISM_Z_SHIFT
# end stops INSIDE the arbor-pedestal bore, blind-bearing look; was -98, poking
# 8 clear through the block). = cylinder-gear-shaft origin, placed by its south
# end.
ARBOR_LENGTH = 187.0  # north end at z +132.415: 7.5 seated in the NORTH
# arbor-pedestal's bore band (PR8, ch12 page002_img09 -- the real machine's
# base-standing north clamp restored as a second, mirrored pedestal with its
# foot just clear of the rocker-arm-support footprint). Must match
# cylinder-gear-shaft SHAFT_LENGTH; the pedestal geometry is asserted below.
CRANKSHAFT_Z0 = -175.0  # outboard (crank) end (was -160: the crank plane moved
# south with the ch30 GT re-read -- arm hub -175..-167, GT axle bolt -189 +- 2.7)
CRANKSHAFT_LENGTH = 122.0  # 2026-09 re-derive: -175..-53 ends 6.2 past the
# 16T pinion's north face (-59.2) -- ch12 page002_img02 shows a short capped
# end right behind the pinion, not a 34 mm bare stub out the column's back.
CRANK_ARM_Z0 = CRANKSHAFT_Z0  # arm PLATE south face: the hub band is
# -175..-167 at the shaft's south end, in FRONT of (south of) the T12 chain
# wheel (-157.5..-152.5): the arm + the handle (its grip extends -Z, further
# south) then sweep entirely south of the chain plane (-155) and cannot foul
# the chain when the crank turns (user, book p005). The placed pose composes a
# Ry(180) (the plate's local +z extrusion runs machine -z), so the component
# ORIGIN sits at the north face -- see CRANK_ARM_ORIGIN_Z.
from crank_arm_spec import ARM_C2C, ARM_WIDTH  # noqa: E402
from crankshaft_spec import PIN_HOLE_HEIGHT  # noqa: E402  # 75: handle pivot from the

# shaft axis (2026-09 front-view re-derive, see crank_arm_spec; was 66 from the
# perspective-magnified side view, 150 before that)
REMOVABLE_Z0 = -157.5  # mounted T12 (face 5.0): band -157.5..-152.5, mid -155 =
# the front chain plane (ch30 GT: solved-camera z-ticks bracket the physical
# chain run at -153 +- 3), between the merged crank column (south flank -98.6,
# even at the disengaged swing) and the crank arm (-175..-167). The plane
# clears the paper-drive stub disc
# (-134.5..-137.5) by 15; the arm sits 9.5 SOUTH of the wheel so the rotating
# arm/handle never crosses it. The small removable gear is the chain wheel
# (ch. 23 -- bead chain on its m2 teeth; v2_gears_010).
ARBOR_PEDESTAL_Z = 90.5 - MECHANISM_Z_SHIFT
# Its complete footing follows the translated cylinder/arbor family.
ARBOR_PEDESTAL_NORTH_Z = 97.5 + MECHANISM_Z_SHIFT
# real machine's base-standing north clamp) -- the SAME casting rotated 180
# about Y so its strap looks SOUTH at the drum.  After the fixed-post recenter
# its foot spans z 92.588..108.588, still north of the unchanged rocker support.
from build_arbor_pedestal import FOOT_DEPTH as ARBOR_PED_DEPTH  # noqa: E402
from build_cylinder_end_disc import DISC_THICK as END_DISC_THICK  # noqa: E402

# Cylinder END DISCS (2026-09, ch13 page002_img01/img03, ch25 page001_img02):
# the plain brass washer closing each end of the gear/rod sandwich, seated
# END_DISC_AIR outboard of the END GEAR on the arbor (p.23 "back side": the
# disc face sits right against the last gear's teeth, the pedestal further
# out). Every drum gear is end-for-end: face z_j -+ DRUM_FACE/2, its cam on
# the south side (z_j - DRUM_FACE/2 - cam), so the south disc clears gear 0's
# cam and rod ring, the north disc gear 19's face. Beside the north pedestal
# instead, the O60 disc fouled the cone-tip block (interference gate).
from build_cylinder_gear import CAM_THICKNESS as DRUM_CAM_T  # noqa: E402

END_DISC_AIR = 0.5
# Dome cap screws (2026-09, ch13 page002_img01/img03, ch25 page002_img03): the
# bright crown head on each pedestal's OUTER strap face, on the arbor axis --
# it closes the blind arbor bore (the arbor ends 2.5 inside the strap; the
# cap's 2.0 spigot stops 0.5 short of it). South strap face = foot centre
# - 2 (band -2..+8 of the 16 foot); north casting turned 180 -> + 2.
from build_dome_cap_screw import STUB_LEN as CAP_STUB_LEN  # noqa: E402

CAP_SOUTH_Z = -ARBOR_PEDESTAL_Z - 2.0  # crown base on the south face, +Y -> -Z
CAP_NORTH_Z = ARBOR_PEDESTAL_NORTH_Z + 2.0  # crown base on the north face, +Y -> +Z
if (ARBOR_SOUTH_Z - CAP_SOUTH_Z) - CAP_STUB_LEN < 0.25:
    raise AssertionError("south dome cap spigot reaches the arbor end")
END_DISC_SOUTH_Z0 = (
    Z_DRUM0 - DRUM_FACE / 2.0 - DRUM_CAM_T - END_DISC_AIR - END_DISC_THICK
)
END_DISC_NORTH_Z0 = Z_DRUM0 + 19 * Z_PITCH + DRUM_FACE / 2.0 + END_DISC_AIR
if END_DISC_SOUTH_Z0 < -ARBOR_PEDESTAL_Z + ARBOR_PED_DEPTH / 2.0 + 0.25:
    raise AssertionError("south end disc reaches the south pedestal strap")
if (
    END_DISC_NORTH_Z0 + END_DISC_THICK
    > ARBOR_PEDESTAL_NORTH_Z - ARBOR_PED_DEPTH / 2.0 - 0.25
):
    raise AssertionError("north end disc reaches the north pedestal strap")
# (also imported with the main block below; repeated here because these
# asserts run before it)

_ARBOR_NORTH = ARBOR_SOUTH_Z + ARBOR_LENGTH  # +132.415
if (ARBOR_PEDESTAL_NORTH_Z - ARBOR_PED_DEPTH / 2.0) - 88.9 < 0.5:
    raise AssertionError("north pedestal foot reaches the rocker-support foot")
_N_PED_FACE = ARBOR_PEDESTAL_NORTH_Z - ARBOR_PED_DEPTH / 2.0
# south-looking strap face after the Ry180 installation
if not 6.0 <= _ARBOR_NORTH - _N_PED_FACE <= ARBOR_PED_DEPTH - 4.0:
    raise AssertionError("arbor north engagement in the north pedestal out of band")

# The pinion must sit fully on the crankshaft.
if PINION_TOOTH_Z + PINION_FACE / 2.0 > CRANKSHAFT_Z0 + CRANKSHAFT_LENGTH:
    raise AssertionError("crankshaft too short for the M6.7 pinion station")
# The crankshaft's named seat datums (the flip-free coincident seats for the
# keyed chain -- see _seat_on_crank) must sit exactly at this module's
# authored stations.
from build_crank_arm import ARM_THICKNESS  # noqa: E402
from build_crankshaft import (  # noqa: E402
    SEAT_ARM as CS_SEAT_ARM,
    SEAT_PINION as CS_SEAT_PINION,
    SEAT_T12 as CS_SEAT_T12,
    SHAFT_LENGTH as CS_SHAFT_LENGTH,
)

CRANK_ARM_ORIGIN_Z = CRANK_ARM_Z0 + ARM_THICKNESS  # the arm origin's world z
# Crank taper pin + keeper ring (ch11 p.14): pin axis along machine X through
# the arm hub's mid-thickness (= the crankshaft's PIN_HOLE_HEIGHT above its
# outboard end), big end PIN_PROUD outside the hub's -X face.
from crank_pin_spec import (  # noqa: E402
    PIN_LENGTH as CRANK_PIN_LENGTH,
    RING_HOLE_DIA as PIN_RING_HOLE_DIA,
    RING_HOLE_X as PIN_RING_HOLE_X,
)
from build_crank_pin_ring import WIRE_DIA as CRANK_RING_WIRE_DIA  # noqa: E402
from build_crank_pin_eye import (  # noqa: E402
    LOOP_R as EYE_LOOP_R,
    TAIL_LEN as EYE_TAIL_LEN,
    WIRE_DIA as EYE_WIRE_DIA,
)
from crank_arm_spec import ANCHOR_SCREW_X, ANCHOR_SCREW_Y, ANCHOR_THREAD_DEPTH  # noqa: E402
from fillister_screw_spec import (  # noqa: E402
    SHANK_DIA as ANCHOR_SCREW_SHANK_DIA,
    SHANK_LEN as ANCHOR_SCREW_SHANK_LEN,
)

CRANK_RING_ARM_CLEARANCE = 0.25
PIN_PROUD = PIN_RING_HOLE_X + CRANK_RING_WIRE_DIA / 2.0 + CRANK_RING_ARM_CLEARANCE
CRANK_PIN_Z = CRANK_ARM_Z0 + ARM_THICKNESS / 2.0  # -171: hub mid-thickness
CRANK_PIN_X0 = X_CRANK - ARM_WIDTH / 2.0 - PIN_PROUD  # big end, -X of the hub
# The ring lies in machine YZ. Its straight local-Z leg is concentric with the
# pin's machine-Z cross-hole; its bends and return hang toward machine -Y.
CRANK_RING_Y = Y_CRANK
if (PIN_RING_HOLE_DIA - CRANK_RING_WIRE_DIA) / 2.0 < 0.1:
    raise AssertionError("keeper-ring wire does not clear the crank-pin cross-hole")
if abs((CRANKSHAFT_Z0 + PIN_HOLE_HEIGHT) - CRANK_PIN_Z) > 1e-6:
    raise AssertionError("crankshaft cross-hole is not at the arm hub's mid-thickness")
if CRANK_PIN_X0 + CRANK_PIN_LENGTH < X_CRANK + ARM_WIDTH / 2.0 + 2.0:
    raise AssertionError("crank pin does not run out the far side of the hub")
# Keeper-ring anchor (ch11 p.14): the arm's front (south, machine -z) face is
# CRANK_ARM_Z0; arm local (x, y) -> machine (X_CRANK - y, Y_CRANK - x) (the
# placed rows: local +x -> -Y, local +y -> -X). The brass eyelet lies flat on
# that face (wire centre a wire radius + air south of it), its tail pointing
# UP the arm at the screw and ending at the shank; the fillister-screw's
# under-head plane rides on the wire (one wire diameter + air off the face),
# shank pointing +z into the arm's #4-40 tap.
ANCHOR_AIR = 0.02
ANCHOR_SCREW_XY = (X_CRANK - ANCHOR_SCREW_Y, Y_CRANK - ANCHOR_SCREW_X)
ANCHOR_HEAD_Z = CRANK_ARM_Z0 - EYE_WIRE_DIA - ANCHOR_AIR
EYE_Z = CRANK_ARM_Z0 - EYE_WIRE_DIA / 2.0 - ANCHOR_AIR
# the tail's end touches the shank: loop centre (tail root) sits LOOP_R + TAIL_LEN
# + shank radius + air below the screw axis
EYE_CENTER_Y = ANCHOR_SCREW_XY[1] - (
    ANCHOR_SCREW_SHANK_DIA / 2.0 + ANCHOR_AIR + EYE_TAIL_LEN + EYE_LOOP_R
)
if ANCHOR_SCREW_SHANK_LEN - EYE_WIRE_DIA - ANCHOR_AIR > ANCHOR_THREAD_DEPTH:
    raise AssertionError("anchor screw bottoms in the crank arm's tap")
if ANCHOR_SCREW_SHANK_LEN - EYE_WIRE_DIA - ANCHOR_AIR < 2.0:
    raise AssertionError("anchor screw has under 2.0 thread engagement in the arm")
# = the plate's NORTH face (-167): the placed rows compose a Ry(180), so the
# +z-extruded plate fills CRANK_ARM_Z0..here running machine -z from the
# origin. Both the place_component z and the crankshaft's SeatArm datum
# station (asserted below) use THIS value.

if abs(CS_SHAFT_LENGTH - CRANKSHAFT_LENGTH) > 1e-9:
    raise AssertionError("crankshaft part length does not cover the moved pinion")
if abs((CRANKSHAFT_Z0 + CS_SEAT_T12) - REMOVABLE_Z0) > 1e-6:
    raise AssertionError("crankshaft SeatT12 datum off the REMOVABLE_Z0 station")
if abs((CRANKSHAFT_Z0 + CS_SEAT_PINION) - (PINION_TOOTH_Z - PINION_FACE / 2.0)) > 1e-6:
    raise AssertionError("crankshaft SeatPinion datum off the 16T station")
if abs((CRANKSHAFT_Z0 + CS_SEAT_ARM) - CRANK_ARM_ORIGIN_Z) > 1e-6:
    raise AssertionError("crankshaft SeatArm datum off the arm origin station")

# The whole cone set rides the SWING PLATFORM (ch.12 p.18: the dark wedge
# plate labelled "pivot" at its tip end). The green pivot post (big-end
# journal) and the black tip block (cup-ended adjuster carrier) stand ON the plate;
# the plate pivots about a vertical axis at cone station PIVOT_STATION, just
# north of the shaft's rear end, so on disengage the BIG end -- where the
# gears need the most working-depth separation -- swings the farthest
# (throw ~ distance from pivot).
# T006 is the reference gear for the tip-end stack. The bushing sits directly
# against its north face; the block follows after one bushing-half-width of
# clearance, and the pivot keeps its established 11 mm offset from the block.
T006_CENTER_STATION = SHAFT_T120_STATION + GEAR_AXIS_SHIFT + 19 * SEAT_PITCH
T006_NORTH_FACE = T006_CENTER_STATION + CONE_FACE / 2.0

# --- platform <-> riders fit (SolidWorks-free, import-time) ------------------
# The platform/post/block parts hardcode their envelopes in THEIR part frames;
# they must agree with the live cone-shaft line placed here. Imported, not
# copied (the CAM_ECC precedent), and asserted at import so a drifted anchor
# fails before any COM work.
from build_cone_swing_platform import (  # noqa: E402
    CRANK_AXIS_OFF as PLAT_CRANK_OFF,
    CRANK_AXIS_Y as PLAT_CRANK_Y,
    EAST_HALF_S as PLAT_EAST_S,
    HALF_WIDTH_N as PLAT_EAST_N,  # EAST taper line's north endpoint (12 --
    # the lock-slot side keeps its full seat; feeds the stop-screw/containment
    # east-edge math)
    WEST_HALF_N as PLAT_WEST_N,  # WEST line's north endpoint (8.0, the
    # trim; feeds ONLY the west-edge pedestal scan. Aliasing it into the east
    # math shifted the derived stop point -- Codex catch, 2026-07-05)
    NORTH_OVERHANG as PLAT_OVERHANG,
    CRANK_SEAT_ANCHOR as PLAT_SEAT_ANCHOR,
    NOTCH_EXIT_TRAVEL as PLAT_NOTCH_EXIT,
    PLATE_LEN as PLAT_LEN,
    PLATE_T as PLAT_T,
    PIVOT_HOLE_DIA as PLAT_PIVOT_HOLE_DIA,
    SLOT_E_X as PLAT_SLOT_E_X,
    SLOT_E_Z as PLAT_SLOT_E_Z,
    SLOT_R as PLAT_SLOT_R,
    SLOT_W as PLAT_SLOT_W,
    WEST_HALF_S as PLAT_WEST_S,
)
from build_cone_lock_knob import (  # noqa: E402
    STUD_DIA as KNOB_STUD_DIA,
    WASHER_DIA as KNOB_WASHER_DIA,
)
from build_cone_pivot_screw import (  # noqa: E402
    HEAD_DIA as PSCREW_HEAD_DIA,
    SHOULDER_DIA as PSCREW_SHOULDER_DIA,
    SHOULDER_LEN as PSCREW_SHOULDER_LEN,
    THREAD_TAIL_LEN as PSCREW_THREAD_TAIL_LEN,
)
from cone_pivot_screw_spec import (  # noqa: E402
    THREAD as PSCREW_THREAD,
    THREAD_SOLID_DIA as PSCREW_THREAD_SOLID_DIA,
    THREAD_TAP_DRILL_DIA as PSCREW_THREAD_TAP_DRILL_DIA,
)
from build_swing_stop_screw import (  # noqa: E402
    SHANK_DIA as STOP_SHANK_DIA,
)
from build_harmonic_base import (  # noqa: E402
    BLOCK_SCREW_HOLE_DEPTH as BASE_BLOCK_HOLE_DEPTH,
    BLOCK_SCREW_HOLE_DIA as BASE_BLOCK_HOLE_DIA,
    BLOCK_SCREW_XZ as BASE_BLOCK_XZ,
    FOOT_SCREW_HOLE_DEPTH as BASE_FOOT_HOLE_DEPTH,
    FOOT_SCREW_HOLE_DIA as BASE_FOOT_HOLE_DIA,
    FOOT_SCREW_XZ as BASE_FOOT_XZ,
    PIVOT_SCREW_HOLE_DIA as BASE_PIVOT_HOLE_DIA,
    PIVOT_HOLE_DEPTH as BASE_PIVOT_HOLE_DEPTH,
    PIVOT_SEAT_SPEC as BASE_PIVOT_SEAT_SPEC,
    PIVOT_SCREW_XZ as BASE_PIVOT_XZ,
    STOP_SCREW_HOLE_DIA as BASE_STOP_HOLE_DIA,
    STOP_SCREW_XZ as BASE_STOP_XZ,
)
from harmonic_base_spec import (  # noqa: E402
    TOP_LENGTH as BASE_TOP_LENGTH,
    TOP_WIDTH as BASE_TOP_WIDTH,
)
from build_arbor_pedestal import (  # noqa: E402
    FOOT_DEPTH as ARBOR_PED_DEPTH,  # PR3 reshaped the pedestal; its foot
    FOOT_HEIGHT as ARBOR_PED_FLANGE_T,  # the exposed flange the foot screw clamps
    FOOT_WIDTH as ARBOR_PED_WIDTH,  # flange keeps the old block's 24x16 plan
    SCREW_HOLE_DIA as ARBOR_PED_HOLE_DIA,
    SCREW_Z as ARBOR_PED_SCREW_Z,
    STRAP_T as ARBOR_PED_STRAP_T,
)

# --- ch25 pinion swing rig part constants (PR7: imported, not hardcoded) ----
from build_alignment_pinion import (  # noqa: E402
    BORE_DIA as DRUM_BORE_DIA,
)
from build_pinion_arbor import (  # noqa: E402
    SHAFT_DIA as ARBOR_DIA,
    SHAFT_LEN as ARBOR_LEN,
)
from pinion_bracket_geometry import (  # noqa: E402
    ARBOR_BORE as STRAP_ARBOR_BORE,
    CAM_RELIEF_ENGAGED_CENTER as STRAP_CAM_RELIEF_ENGAGED,
    CAM_RELIEF_ENVELOPE_RADIUS as STRAP_CAM_RELIEF_ENVELOPE_R,
    CAM_RELIEF_PARK_CENTER as STRAP_CAM_RELIEF_PARK,
    CAM_RELIEF_RADIUS as STRAP_CAM_RELIEF_R,
    C2C as STRAP_C2C,
    PIN_BORE as STRAP_PIN_BORE,
    PIN_DROP as FPIN_DROP,
    PIN_SEAT as FPIN_SEAT,
    PIVOT_BORE as STRAP_PIVOT_BORE,
    R_END as STRAP_R_END,
    THICKNESS as STRAP_T,
)
from build_pinion_pivot_block import (  # noqa: E402
    BLOCK_DEPTH,
    BLOCK_HEIGHT,
    BLOCK_WIDTH,
    BORE_HALF_SPACING as BLOCK_BORE_HALF_SPACING,
    BORE_UP as BLOCK_BORE_UP,
    LIFT_BORE_RISE,
    SCREW_HALF_SPACING as BLOCK_SCREW_HALF,
    SCREW_HOLE_DIA as BLOCK_SCREW_HOLE_DIA,
)
from pinion_cam_geometry import (  # noqa: E402
    BORE as CAM_BORE_DIA,
    BOSS_DIA as CAM_BOSS_DIA,
    BOSS_PROUD as CAM_BOSS_PROUD,
    BOSS_Z as CAM_BOSS_Z,
    CAM_LEN,
    CAM_OD,
    ECC as CAM_ECC,
    THIN_SIDE_WALL as CAM_THIN_SIDE_WALL,
)
from pinion_cam_pin_geometry import (  # noqa: E402
    PIN_DIA as FPIN_DIA,
    PIN_LEN as FPIN_LEN,
    SEAT_LEN as FPIN_SEAT_LEN,
)
from pinion_lever_geometry import (  # noqa: E402
    CAP_SAG as LEVER_CAP_SAG,
    HUB_LEN as LEVER_HUB_LEN,
    ROD_LEN as LEVER_ROD_LEN,
    ROD_ROOT_DIA as LEVER_ROD_DIA,
    ROD_TIP_DIA as LEVER_ROD_TIP_DIA,
    WALL_T as LEVER_WALL_T,
)
from pinion_handle_geometry import (  # noqa: E402
    GRIP_DIA as HANDLE_GRIP_DIA,
    GRIP_LEN as HANDLE_GRIP_LEN,
    CAP_SAG as HANDLE_CAP_SAG,
    ROD_DIA as HANDLE_ROD_DIA,
    TUBE_ID as HANDLE_TUBE_ID,
    TUBE_LEN as HANDLE_TUBE_LEN,
    WALL_T as HANDLE_WALL_T,
)
from pinion_spring_geometry import (  # noqa: E402
    AXIS_OFFSET as SPRING_AXIS_OFF,
    BLADE_TILT_DEG as SPR_BLADE_TILT_DEG,
    FLAT_TIP as SPR_FLAT_TIP_L,
    FOOT_END as SPR_FOOT_END_L,
    HOLE_DIA as SPR_HOLE_DIA,
    HOLE_FROM_END as SPR_HOLE_FROM_END,
    KINK_START as SPR_CREST_L,
    PIVOT_LX as SPR_PIVOT_LX,
    PIVOT_LY as SPR_PIVOT_LY,
    THICK as SPRING_T,
    WIDTH as SPRING_W,
)
from build_slotted_screw import (  # noqa: E402
    HEAD_DIA as BSCREW_HEAD_DIA,
    SHANK_DIA as BSCREW_SHANK_DIA,
    SHANK_LEN as BSCREW_SHANK_LEN,
)
from build_foot_screw import (  # noqa: E402
    HEAD_DIA as FSCREW_HEAD_DIA,
    SHANK_DIA as FSCREW_SHANK_DIA,
    SHANK_LEN as FSCREW_SHANK_LEN,
)
from build_cone_pivot_post import (  # noqa: E402
    BLOCK_DIA as POST_BLOCK_DIA,
    BORE_HEIGHT as POST_BORE_HEIGHT,
    CONE_BOSS_LENGTH as POST_CONE_BOSS_LENGTH,
    CRANK_BORE_HEIGHT as POST_CRANK_Y,
    CRANK_BOSS_LENGTH as POST_CRANK_BOSS_LENGTH,
    CRANK_BOSS_START_Z as POST_CRANK_BOSS_START_Z,
)
from build_cone_tip_block import (  # noqa: E402
    ADJUSTER_BORE_DIA as TIP_ADJ_BORE_DIA,
    ADJUSTER_BORE_DEPTH as TIP_ADJ_BORE_DEPTH,
    ADJUSTER_AXIS_HEIGHT as TIP_ADJUSTER_AXIS_HEIGHT,
    BLOCK_X as TIP_BLOCK_X,
    BLOCK_Z as TIP_BLOCK_Z,
    PINCH_BORE_DIA as TIP_PINCH_BORE_DIA,
    PINCH_BORE_Y as TIP_PINCH_Y,
    SHAFT_PASSAGE_DIA as TIP_SHAFT_PASSAGE_DIA,
)
from build_cone_tip_bushing import (  # noqa: E402
    BORE_DIA as BUSH_BORE_DIA,
    LENGTH as BUSH_LEN,
)
from build_cone_tip_adjuster import (  # noqa: E402
    BODY_DIA as ADJ_BODY_DIA,
    BODY_LEN as ADJ_LEN,
    CUP_DEPTH as ADJ_CUP_DEPTH,
    CUP_DIA as ADJ_CUP_DIA,
)
from build_cone_tip_pinch_screw import (  # noqa: E402
    SHANK_DIA as PINCH_SHANK_DIA,
    SHANK_LEN as PINCH_SHANK_LEN,
)
from cone_gear_shaft_spec import (  # noqa: E402
    FRONT_STUB as SHAFT_FRONT_STUB,
    SECTIONS as SHAFT_SECTIONS,
)

TIP_BLOCK_STATION = T006_NORTH_FACE + BUSH_LEN + BUSH_LEN / 2.0 + TIP_BLOCK_Z / 2.0
PIVOT_STATION = TIP_BLOCK_STATION + 11.0
# One journal drive height across the platform and both riders: plate
# thickness under each foot + bore height = 54 above the base top.
if (
    abs((Y_DRIVE - Y_BASE_TOP) - (PLAT_T + POST_BORE_HEIGHT)) > 1e-9
    or abs((Y_DRIVE - Y_BASE_TOP) - (PLAT_T + TIP_ADJUSTER_AXIS_HEIGHT)) > 1e-9
):
    raise AssertionError("cone axis height drifted between platform/post/block")
# The shaft is placed by its front stub end; keep the station in lockstep with
# the part's FRONT_STUB.
if abs(SHAFT_FRONT_STATION + SHAFT_FRONT_STUB) > 1e-9:
    raise AssertionError("SHAFT_FRONT_STATION out of sync with the shaft FRONT_STUB")


def _plat_half_width(s: float) -> float:
    """Platform MIN half-width at cone station s: the narrower of the east
    taper and the west flare (the west-tip trim makes the WEST side the
    narrow one near the north end -- 8 vs 12); negative if s is off the
    plate. Riders are centred on the shaft plan line (local x 0), so the
    narrower side at each station bounds their containment."""
    z_local = s - PIVOT_STATION  # platform local z (+ along increasing station)
    if not (PLAT_OVERHANG - PLAT_LEN - 1e-9 <= z_local <= PLAT_OVERHANG + 1e-9):
        return -1.0
    frac = (PLAT_OVERHANG - z_local) / PLAT_LEN
    east = PLAT_EAST_N + (PLAT_EAST_S - PLAT_EAST_N) * frac
    west = PLAT_WEST_N + (PLAT_WEST_S - PLAT_WEST_N) * frac
    return min(east, west)


# Both riders stand fully ON the plate (plan, in the platform's own inclined
# frame: both are centred on the shaft-axis plan line, so only the along-axis
# span and the half-width at each end matter).
for _lbl, _s0, _hx, _hz in (
    ("pivot post", POST_STATION, POST_BLOCK_DIA / 2.0, POST_BLOCK_DIA / 2.0),
    ("tip block", TIP_BLOCK_STATION, TIP_BLOCK_X / 2.0, TIP_BLOCK_Z / 2.0),
):
    for _end in (_s0 - _hz, _s0 + _hz):
        if _plat_half_width(_end) < _hx + 0.25:
            raise AssertionError(
                f"{_lbl} overhangs the swing platform at station {_end:g}"
            )
# The shaft's tip reaches through the block to the adjuster cup (>= 5 inside
# the block envelope, end short of the north face).
_TIP_END_STATION = SHAFT_FRONT_STATION + SHAFT_SECTIONS[-1][1]
if not (
    TIP_BLOCK_STATION - TIP_BLOCK_Z / 2.0 + 5.0
    <= _TIP_END_STATION
    <= TIP_BLOCK_STATION + TIP_BLOCK_Z / 2.0 - 0.5
):
    raise AssertionError("shaft tip end does not reach the tip-block adjuster")
# The stub end stands 1.0 mm proud of the post's inclined journal face.
_STUB_END_Z = cone_station(SHAFT_FRONT_STATION)[2]
_POST_SOUTH_STATION = POST_STATION - POST_CONE_BOSS_LENGTH / 2.0
_POST_SOUTH_Z = cone_station(_POST_SOUTH_STATION)[2]
if SHAFT_FRONT_STATION > _POST_SOUTH_STATION - 1.0 + 1e-9:
    raise AssertionError(
        f"cone-shaft stub end {_STUB_END_Z:.2f} not proud of the post's south "
        f"flank {_POST_SOUTH_Z:.2f}"
    )
# --- tip end-play stack (item 5, v4_t00471 / 7:49) ---------------------------
# Along the axis, south to north: T006 gear | brass bushing (spacer) | block
# south face | short unsupported tip span | adjuster screw in the tapped bore, its blind cup
# holding the shaft's tip end; the block's top slit + pinch screw lock it.
TIP_SOUTH_STATION = TIP_BLOCK_STATION - TIP_BLOCK_Z / 2.0
BUSH_STATION = T006_NORTH_FACE
ADJ_EMBED = 6.0  # adjuster thread engagement into the counterbore (8 deep)
ADJ_HEAD_STATION = TIP_BLOCK_STATION + TIP_BLOCK_Z / 2.0 + (ADJ_LEN - ADJ_EMBED)
_ADJ_MOUTH = ADJ_HEAD_STATION - ADJ_LEN
_STUB_DIA = SHAFT_SECTIONS[-1][0] * 25.4  # 0.794: the 1/32" tip stub
_STUB_START = SHAFT_FRONT_STATION + SHAFT_SECTIONS[-2][1]  # 155.7
if BUSH_STATION < _STUB_START + 1.0:
    raise AssertionError("tip bushing rides off the 1/32in stub section")
if abs(BUSH_BORE_DIA - _STUB_DIA) > 0.05:
    raise AssertionError("tip-bushing bore does not match the tip stub dia")
if ADJ_EMBED > TIP_ADJ_BORE_DEPTH - 0.5:
    raise AssertionError("adjuster bottoms out in the block counterbore")
if TIP_ADJ_BORE_DIA - ADJ_BODY_DIA < 0.25:
    raise AssertionError("modeled adjuster envelope interferes with its tap drill")
if not (_ADJ_MOUTH + 0.5 <= _TIP_END_STATION <= _ADJ_MOUTH + ADJ_CUP_DEPTH - 0.5):
    raise AssertionError("shaft tip end does not rest inside the adjuster cup")
if ADJ_CUP_DIA < _STUB_DIA + 0.25:
    raise AssertionError("adjuster cup too tight around the tip stub")
if TIP_SHAFT_PASSAGE_DIA < _STUB_DIA + 0.25:
    raise AssertionError("tip-block passage too tight around the shaft tip")
# The pinch screw THREADS INTO the block's tapped #3-48 cross-bore: the
# modeled shank rides at tap-drill - ~0.3 (memory/fastener-policy lag
# precedent), so the fit is an engagement band, not the old equality.
if not (0.15 <= TIP_PINCH_BORE_DIA - PINCH_SHANK_DIA <= 0.45):
    raise AssertionError(
        f"pinch-screw shank {PINCH_SHANK_DIA} does not thread-fit the block "
        f"cross-bore {TIP_PINCH_BORE_DIA} (want bore - shank in [0.15, 0.45])"
    )
if PINCH_SHANK_LEN < TIP_BLOCK_X / 2.0 + 0.5:
    raise AssertionError("pinch screw too short to cross the top slit")
# The crank pedestal is GONE as a separate base-mounted part: the cone pivot
# post and the crank pedestal are ONE green column riding the swing platform
# (user-confirmed vs v4_t00411/t00417), so the crank rig swings with the cone
# set and the 16T<->64T mesh survives the disengage. Cross-script agreement
# for the merged column's crank bore and the platform's "crank axis":
_PPIVOT = cone_station(PIVOT_STATION)
_PPOST = cone_station(POST_STATION)
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

# CRANK_AXIS_OFF is the distance the crank axis sits EAST of the pivot
# (east = machine -x), so it equals pivot.x - X_CRANK.
if abs(PLAT_CRANK_OFF - (_PPIVOT[0] - X_CRANK)) > 0.05:
    raise AssertionError(
        f"platform CRANK_AXIS_OFF {PLAT_CRANK_OFF} != pivot.x - X_CRANK "
        f"{_PPIVOT[0] - X_CRANK:.3f}"
    )
if abs(PLAT_CRANK_Y - (Y_CRANK - Y_BASE_TOP)) > 1e-6:
    raise AssertionError("platform CRANK_AXIS_Y != Y_CRANK - Y_BASE_TOP")
if abs(_PPOST[0] - X_CRANK) > 1e-9:
    raise AssertionError("v2 crank boss no longer shares the post body centre x")
if abs(POST_CRANK_Y - (Y_CRANK - Y_BASE_TOP - PLAT_T)) > 1e-6:
    raise AssertionError("column CRANK_BORE_Y != Y_CRANK - Y_BASE_TOP - PLAT_T")
# Axial closure around the v2 boss after the casting's exact Ry(180).  The turn
# reverses local Z, so the harvested asymmetric boss now runs from
# post.z - (start + length) to post.z - start.  The photo-anchored T12 remains
# south of it while the 16T follows the translated 64T contact row to its north;
# the two positive clearances are intentionally no longer equal.
_POST_BOSS_SOUTH = _PPOST[2] - (POST_CRANK_BOSS_START_Z + POST_CRANK_BOSS_LENGTH)
_POST_BOSS_NORTH = _PPOST[2] - POST_CRANK_BOSS_START_Z
_T12_NORTH = REMOVABLE_Z0 + 5.0
_PINION_SOUTH = PINION_TOOTH_Z - PINION_FACE / 2.0
_BOSS_SOUTH_GAP = _POST_BOSS_SOUTH - _T12_NORTH
_BOSS_NORTH_GAP = _PINION_SOUTH - _POST_BOSS_NORTH
if min(_BOSS_SOUTH_GAP, _BOSS_NORTH_GAP) < 0.25:
    raise AssertionError("v2 crank boss does not clear its axial hardware")
# Keep both independently derived gaps visible to import-time geometry checks.
if not 10.0 < _BOSS_SOUTH_GAP < 10.5:
    raise AssertionError("v2 crank boss south/T12 clearance left its derived band")
if not 0.24 < _BOSS_NORTH_GAP < 1.0:
    raise AssertionError("v2 crank boss north/pinion clearance left its derived band")
if abs(PINION_TOOTH_Z - _GEAR64_CONTACT_Z) > 0.05:
    raise AssertionError("16T is no longer centred on the 64T contact row")

# The relocated v2 crank axis also clears the inclined T120 rim radially. Keep
# the exact arc scan as a tripwire: if a later diameter/station change restores
# radial overlap, the pinion's north face must retain 0.25 mm axial air.
_T120_SEAT = cone_station(SHAFT_T120_STATION + GEAR_AXIS_SHIFT)
_TIP120 = CONE_T120_PITCH_R + ADDENDUM
_T120_SOUTH = math.inf  # no radial overlap -> no T120 bound at all
for _k in range(7200):
    _c = _TIP120 * math.cos(math.radians(0.05 * _k))
    _s = _TIP120 * math.sin(math.radians(0.05 * _k))
    if (
        math.hypot(_T120_SEAT[0] + _c * COS_I - X_CRANK, Y_DRIVE + _s - Y_CRANK)
        <= R16 + ADD16
    ):
        _T120_SOUTH = min(
            _T120_SOUTH, _T120_SEAT[2] - _c * SIN_I - CONE_FACE / 2.0 * COS_I
        )
if PINION_TOOTH_Z + PINION_FACE / 2.0 > _T120_SOUTH - 0.25:
    raise AssertionError(
        f"16T north face {PINION_TOOTH_Z + PINION_FACE / 2.0:.3f} reaches "
        f"the inclined T120 rim bound {_T120_SOUTH:.3f}"
    )
# ... and must still cover the 64T row (>= 85% of its face) -- an engagement
# floor so a future station edit cannot quietly starve the mesh.
_G64_BAND = (
    _GEAR64_CONTACT_Z - GEAR64_FACE / 2.0 * COS_I,
    _GEAR64_CONTACT_Z + GEAR64_FACE / 2.0 * COS_I,
)
_ENGAGED = min(PINION_TOOTH_Z + PINION_FACE / 2.0, _G64_BAND[1]) - max(
    PINION_TOOTH_Z - PINION_FACE / 2.0, _G64_BAND[0]
)
if _ENGAGED < 0.85 * GEAR64_FACE * COS_I:
    raise AssertionError(
        f"16T engages only {_ENGAGED:.3f} of the 64T row "
        f"{GEAR64_FACE * COS_I:.3f} (floor 85%)"
    )
# The base's pivot-screw hole sits exactly under the swing pivot -- both are
# authored in the machine frame, so the coordinates agree directly (pre-#151
# this module derived in the mirrored frame and the hole's x was the NEGATED
# pivot x).
if (
    abs(BASE_PIVOT_XZ[0] - _PPIVOT[0]) > 0.05
    or abs(BASE_PIVOT_XZ[1] - _PPIVOT[2]) > 0.05
):
    raise AssertionError(
        f"harmonic-base pivot-screw hole {BASE_PIVOT_XZ} != machine swing pivot "
        f"({_PPIVOT[0]:.3f}, {_PPIVOT[2]:.3f})"
    )
if PLAT_PIVOT_HOLE_DIA <= PSCREW_SHOULDER_DIA:
    raise AssertionError("platform pivot hole does not clear the screw shoulder")
if abs(PSCREW_SHOULDER_LEN - PLAT_T - 0.25) > 1e-9:
    raise AssertionError("pivot screw no longer provides 0.25 axial plate clearance")
if BASE_PIVOT_SEAT_SPEC.kind != "tapped":
    raise AssertionError("base pivot seat is not tapped")
if BASE_PIVOT_SEAT_SPEC.size != PSCREW_THREAD:
    raise AssertionError("base pivot thread does not match the pivot screw")
if BASE_PIVOT_SEAT_SPEC.thread_class != "2B":
    raise AssertionError("base pivot thread is not UNC")
if abs(PSCREW_THREAD_SOLID_DIA - PSCREW_THREAD_TAP_DRILL_DIA) > 1e-9:
    raise AssertionError("pivot screw solid envelope does not match the tap drill")
if abs(BASE_PIVOT_HOLE_DIA - PSCREW_THREAD_SOLID_DIA) > 1e-9:
    raise AssertionError("pivot screw solid envelope does not match the mating hole")
if BASE_PIVOT_HOLE_DEPTH - PSCREW_THREAD_TAIL_LEN < 1.5:
    raise AssertionError("base pivot tap lacks blind-hole bottom clearance")
# The pivot-screw head sits on the plate top at station PIVOT_STATION; the
# tip block (also on the plate) ends at station 191 -- the head radius must
# clear its north face (the first O12 head clipped the corner 13.5 mm^3).
if (
    PSCREW_HEAD_DIA / 2.0
    > (PIVOT_STATION - (TIP_BLOCK_STATION + TIP_BLOCK_Z / 2.0)) - 0.25
):
    raise AssertionError("pivot-screw head reaches the tip block's north face")


# --- cone lock knob (v4_t00411; clamps the swing plate through its notch) ----
# The knob is a base-bolted STATIC (pedestal pattern: locked to the static
# datums); the plate's open lock notch sweeps around its stationary stud and,
# past the mouth, clear of it (t00417: the bolt stands past the plate edge
# when disengaged). Its machine position is DERIVED from the platform's
# engaged notch-seat in the plate's local frame, so the two scripts cannot
# drift apart.
def _plate_local_to_machine(x_l: float, z_l: float) -> tuple[float, float]:
    """Plan point of the ENGAGED plate's local (x, z) in machine coords.

    The engaged plate sits at Ry(+INCLINE) (its local +z runs up-station along
    the inclined shaft line), so local +x tips toward machine +x/-z."""
    return (
        _PPIVOT[0] + x_l * COS_I + z_l * SIN_I,
        _PPIVOT[2] - x_l * SIN_I + z_l * COS_I,
    )


# The platform is authored machine-handed (it was the "x0" pre-mirrored part
# of the retired M6.8 scheme), so its exported local-x constants feed straight
# through; z is untouched.
KNOB_X, KNOB_Z = _plate_local_to_machine(PLAT_SLOT_E_X, PLAT_SLOT_E_Z)
# (-92.563, -52.834): the video's gap between the pivot post and pedestal
if PLAT_SLOT_W - KNOB_STUD_DIA < 0.5:
    raise AssertionError("lock stud has <0.5 clearance in the platform notch")
# The plate's crank-anchor point (CrankAxisSeat's anchor, on the plate's
# "crank axis") must land ON the machine crank axis at the engaged pose --
# the SolidWorks-free proof of the platform's CRANK_SEAT_ANCHOR signs.
_SEAT_ANCHOR_M = _plate_local_to_machine(PLAT_SEAT_ANCHOR[0], PLAT_SEAT_ANCHOR[1])
if abs(_SEAT_ANCHOR_M[0] - X_CRANK) > 0.05:
    raise AssertionError(
        f"platform CRANK_SEAT_ANCHOR maps to machine x {_SEAT_ANCHOR_M[0]:.3f}"
        f" != X_CRANK {X_CRANK} -- anchor sign convention broke"
    )

# Disengaged pose: the plate swings (same sense as the incline) until its
# lobe edge clears the knob's WASHER, so the screwed-down washer fences the
# notch mouth -- the DISENGAGED lock (see the platform's constants block).
# Angle = (stud travel to the mouth + washer radius + margin) / notch radius.
DISENGAGE_DEG = math.degrees(
    (PLAT_NOTCH_EXIT + KNOB_WASHER_DIA / 2.0 + 2.0) / PLAT_SLOT_R
)  # 6.30
# At that swing the big end separates ~18.4 at the T120 -- visibly and
# mechanically out of mesh (the v4_t00417 pose, bolt past the plate edge).
_DISENGAGE_RAD = math.radians(DISENGAGE_DEG)

# --- swing-stop screw (item 6): bounds the free swing at the disengaged pose.
# The DISENGAGE swing is + (the notch region sweeps machine EAST, -x -- the
# same sense that walks the knob stud out the notch mouth), so the plate
# VACATES its west side and it is the EAST taper edge that advances onto a
# base screw. Contact point taken on the east edge at plate-local z -105 (mid
# plate, on the base with margin); the screw centre sits one shank radius
# outside the swung edge. The base part hardcodes the hole (CAM_ECC
# pattern) -- assert agreement, and that the ENGAGED pose clears it on the
# CORRECT side (signed, not |distance|: the first cut of this derivation
# used the west edge + an abs() gap and buried the screw 19 mm INSIDE the
# engaged plate -- caught by the interference gate).
_K_E = (PLAT_EAST_S - PLAT_EAST_N) / PLAT_LEN
_STOP_ZL = -105.0
# The east half-width sits at plate-local -x (the machine-handed platform's
# local +x tips machine-west at the engaged pose, see _plate_local_to_machine).
_STOP_PL = (-(PLAT_EAST_N + _K_E * (PLAT_OVERHANG - _STOP_ZL)), _STOP_ZL)
_EDGE_OUT = (-1.0, _K_E)  # outward (east) normal, plate frame
_EDGE_N = math.hypot(*_EDGE_OUT)
_EDGE_OUT = (_EDGE_OUT[0] / _EDGE_N, _EDGE_OUT[1] / _EDGE_N)


def _swung_to_machine(x_l: float, z_l: float, ang: float) -> tuple[float, float]:
    c, s = math.cos(ang), math.sin(ang)
    return (_PPIVOT[0] + x_l * c + z_l * s, _PPIVOT[2] - x_l * s + z_l * c)


_A_DIS = math.radians(INCLINE_DEG) + _DISENGAGE_RAD
_CONTACT = _swung_to_machine(_STOP_PL[0], _STOP_PL[1], _A_DIS)
_N_M = (
    _EDGE_OUT[0] * math.cos(_A_DIS) + _EDGE_OUT[1] * math.sin(_A_DIS),
    -_EDGE_OUT[0] * math.sin(_A_DIS) + _EDGE_OUT[1] * math.cos(_A_DIS),
)
STOP_X = _CONTACT[0] + _N_M[0] * STOP_SHANK_DIA / 2.0
STOP_Z = _CONTACT[1] + _N_M[1] * STOP_SHANK_DIA / 2.0
# The base part hardcodes the hole (CAM_ECC pattern) in the same machine
# frame -- assert direct agreement.
if abs(BASE_STOP_XZ[0] - STOP_X) > 0.05 or abs(BASE_STOP_XZ[1] - STOP_Z) > 0.05:
    raise AssertionError(
        f"harmonic-base stop-screw hole {BASE_STOP_XZ} != machine derived stop "
        f"({STOP_X:.3f}, {STOP_Z:.3f})"
    )
if BASE_STOP_HOLE_DIA < STOP_SHANK_DIA:
    raise AssertionError("base stop hole under the stop-screw shank dia")
# Engaged pose clears the stop screw on the OUTSIDE (signed distance along
# the engaged east edge's outward normal, minus the shank radius).
_EP = _swung_to_machine(_STOP_PL[0], _STOP_PL[1], math.radians(INCLINE_DEG))
_N_ENG = (
    _EDGE_OUT[0] * COS_I + _EDGE_OUT[1] * SIN_I,
    -_EDGE_OUT[0] * SIN_I + _EDGE_OUT[1] * COS_I,
)
_W = (STOP_X - _EP[0], STOP_Z - _EP[1])
_STOP_ENGAGED_GAP = (_W[0] * _N_ENG[0] + _W[1] * _N_ENG[1]) - STOP_SHANK_DIA / 2.0
if _STOP_ENGAGED_GAP < 2.0:
    raise AssertionError(
        f"stop screw within {_STOP_ENGAGED_GAP:.2f} of the ENGAGED plate edge "
        f"(needs >= 2.0, signed: negative = inside the plate)"
    )
# ... and it must stand clear of the OTHER swing hardware and on the base.
if (
    math.hypot(STOP_X - KNOB_X, STOP_Z - KNOB_Z)
    < (KNOB_WASHER_DIA + STOP_SHANK_DIA) / 2.0 + 0.25
):
    raise AssertionError("stop screw fouls the lock-knob washer")
_POST_LOCAL_Z = POST_STATION - PIVOT_STATION  # -194.5
_WASHER_POST_GAP = (
    math.hypot(PLAT_SLOT_E_X, PLAT_SLOT_E_Z - _POST_LOCAL_Z)
    - KNOB_WASHER_DIA / 2.0
    - POST_BLOCK_DIA / 2.0
)
if _WASHER_POST_GAP < 2.0:
    raise AssertionError(
        f"lock knob washer within {_WASHER_POST_GAP:.2f} of the pivot post "
        f"foot (needs >= 2.0)"
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
    (
        (
            -ARBOR_PEDESTAL_Z - ARBOR_PED_DEPTH / 2.0,
            -ARBOR_PEDESTAL_Z + ARBOR_PED_DEPTH / 2.0,
        ),
        2.0,
    ),  # -63.085..-47.085
    (
        (
            ARBOR_PEDESTAL_NORTH_Z - ARBOR_PED_DEPTH / 2.0,
            ARBOR_PEDESTAL_NORTH_Z + ARBOR_PED_DEPTH / 2.0,
        ),
        0.25,
    ),
)
_EDGE_X_INTERCEPT = PLAT_WEST_N + _K_W * PLAT_OVERHANG
_EDGE_WORLD_Z_BASE = _PPIVOT[2] - _EDGE_X_INTERCEPT * SIN_I
_EDGE_WORLD_Z_SLOPE = COS_I + _K_W * SIN_I
_EDGE_WORLD_X_BASE = _PPIVOT[0] + _EDGE_X_INTERCEPT * COS_I
_EDGE_WORLD_X_SLOPE = SIN_I - _K_W * COS_I
_EDGE_LOCAL_Z_MIN = PLAT_OVERHANG - PLAT_LEN
_EDGE_LOCAL_Z_MAX = PLAT_OVERHANG
for _ARB_Z, _min_gap in _ARB_Z_BANDS:
    _zl0 = max(
        _EDGE_LOCAL_Z_MIN,
        (_ARB_Z[0] - _EDGE_WORLD_Z_BASE) / _EDGE_WORLD_Z_SLOPE,
    )
    _zl1 = min(
        _EDGE_LOCAL_Z_MAX,
        (_ARB_Z[1] - _EDGE_WORLD_Z_BASE) / _EDGE_WORLD_Z_SLOPE,
    )
    if _zl1 < _zl0:
        continue
    _closest_x = max(
        _EDGE_WORLD_X_BASE + _EDGE_WORLD_X_SLOPE * _zl0,
        _EDGE_WORLD_X_BASE + _EDGE_WORLD_X_SLOPE * _zl1,
    )
    _gap = _ARB_E_X - _closest_x
    if _gap < _min_gap:
        raise AssertionError(
            f"swing-plate west edge within {_gap:.3f} mm of an arbor-pedestal "
            f"block over world z {_ARB_Z} (needs >= {_min_gap})"
        )

# --- alignment pinion (ch. 25): RESTORED 2026-07-02, carried DISENGAGED ------
# The ch30 GT proves the zeroing rig is on the machine (tee handle triangulates
# to world (-10.2, 104.2, -144.1), back stub end to (-11.4, 106.7, +91.3)) --
# INBOARD of the drum and LEVEL with the drive axis, not the old outboard/low
# placement the OD-62.2 rescale squeezed out (removal note: git c1ebca3).
# Level + the book's parked tip gap puts the axis at X_DRUM - 44.32 = 10.38
# authored = world -10.38, 0.2 sigma from GT. Parked DISENGAGED (p.68 "gap");
# the engage swing is the p2 setup DOF, park-driven and never suppressed in
# `free` builds (it is a setup motion, not an operational DOF).
APINION_TEETH = _config.machine("alignment_pinion", "teeth")  # 42 (ch25 plate)
TIP_APINION = ((APINION_TEETH + 2.0) / DP_TRAIN) * 25.4 / 2.0  # 11.22
TIP_DRUM120 = (122.0 / DP_TRAIN) * 25.4 / 2.0  # 31.10: cylinder-gear tip radius
APINION_GAP = _config.machine("alignment_pinion", "disengaged_tip_gap_mm")  # 2.0
ENGAGED_C2C = (120.0 + APINION_TEETH) / 2.0 * 25.4 / DP_TRAIN  # 41.30 engaged
APINION_X = X_DRUM + (TIP_DRUM120 + TIP_APINION + APINION_GAP)  # -10.38: INBOARD,
# tip circles backed off to the parked gap at Delta-y = 0 (axis dead level)
APINION_Y = Y_DRIVE
APINION_DRUM_LEN = 143.2  # build_alignment_pinion FACE_WIDTH
APINION_Z_FRONT = -75.0 + MECHANISM_Z_SHIFT
APINION_Z_BACK = APINION_Z_FRONT + APINION_DRUM_LEN  # +103.615
PIVOT_Y = Y_BASE_TOP + 12.0  # 62.8: pivot block bore height
# Bracket thickness, end radius and pivot-to-arbor spacing come from the
# geometry-only contract imported above.
STRAP_AIR = 0.25  # axial air each side of each strap
PIVOT_X = APINION_X + math.sqrt(
    STRAP_C2C**2 - (APINION_Y - PIVOT_Y) ** 2
)  # the far side from the drum, so swinging the strap toward
# vertical advances the pinion into mesh
STRAP_LEAN_DEG = math.degrees(
    math.atan2(PIVOT_X - APINION_X, APINION_Y - PIVOT_Y)
)  # the v2 drive line makes the parked strap lean west of vertical
LIFT_X = PIVOT_X + 2.0 * BLOCK_BORE_HALF_SPACING  # lift rod in the blocks' WEST bores
# east since the DP40 cram (issue #7 dodged the cone-pivot-post column);
# the p.68-69 photos put the lever WEST of the tee handle and the cam pins
# lifting the strap tails' follower pins from the WEST -- an east lift would
# swing the drum OUT of mesh. The column (x ~-47) is far east of the new spot,
# and the M6.9 portal south upright that once blocked the west band was
# replaced by the lone NORTH rocker-arm-support. The recentered p2 rig clears
# the unmodified casting; the complete-machine interference gate proves that
# cross-subassembly relationship from the built solids.
LIFT_Y = PIVOT_Y + LIFT_BORE_RISE  # v2 closure: the steep strap carries its
# follower contact above the pivot at the WEST cam station.  The eccentric cam
# collars still meet the pins from below; the pins rest on the collar ODs.
PIVOT_SHAFT_Z0 = -104.0 + MECHANISM_Z_SHIFT
# Ø6.35 x 192 remains flush with the translated block outer faces.
LIFT_ROD_Z0 = -114.0 + MECHANISM_Z_SHIFT
# front end proud 10 south of the translated front block -- lever hub seat
BLOCK_X = (PIVOT_X + LIFT_X) / 2.0  # block local origin midway the bores
BLOCK_FRONT_Z0 = -104.0 + MECHANISM_Z_SHIFT
BLOCK_BACK_Z0 = 76.0 + MECHANISM_Z_SHIFT
LEVER_TILT_DEG = -40.0  # from vertical; NEGATIVE = leaning machine +X, away
# from the drum and the pinion arbor (2026-09: with the lift rod now right
# under the drum, the old +40 lean ran the rod into the arbor's front stub --
# 40.8 mm^3 in the gate; 4/4 v4_pinion_004 shows the lever standing off to
# the front-right, i.e. this side). The p002-fitted
# 32 was measured with the lever rooted EAST of the pivot (pre-PR5); from the
# west root that tilt swept the shaft through the pinion's front arbor stub
# (117.9 mm^3), and 36 still grazed it (10.3 mm^3): the binding quantity is
# the PERPENDICULAR distance from the stub's (x, y) to the rod line -- the
# stub runs along z, so the 3D minimum is the 2D point-to-line distance, NOT
# the vertical gap at the x-crossing (that mistake cost a build). 40 gives
# 8.44 vs the 7.25 the Ø8 arbor requires, asserted below (PR7 replaced the
# Ø6.35 stub with the arbor on the same axis).
LEVER_LEN = LEVER_ROD_LEN  # 86: hub centre -> tip (img07 @9.37 px/mm,
# PR7 -- the PR6 98 was img08's perspective-inflated read)
LEVER_Z = -111.0 + MECHANISM_Z_SHIFT
# seats on the translated lift-rod front end; north face stays 2 off the block.
HANDLE_TILT_DEG = 65.0  # cross rod from vertical
HANDLE_Z = (-135.0 + MECHANISM_Z_SHIFT) - (HANDLE_GRIP_LEN / 2.0 + HANDLE_WALL_T)
# = ARBOR_Z0 - (hub bore floor station): the blind hub's floor seats on the
# arbor's flat front tip (asserted below), so the grip station follows the
# grip length (2026-09: the O23 x 14 drum became a O15 x 9 ball-crowned grip).
# translated with the p2 arbor. The hub is a blind tubular cap
# (PR7 item 14): its bore floor at local +9 lands on -99.585, where the
# steel arbor's flat front tip seats flush (build_pinion_arbor)

if abs(math.hypot(PIVOT_X - APINION_X, APINION_Y - PIVOT_Y) - STRAP_C2C) > 0.001:
    raise AssertionError("strap c2c does not span pivot -> pinion axis")
if Z_DRUM0 - DRUM_FACE / 2.0 < APINION_Z_FRONT + 1.0:
    raise AssertionError("alignment pinion too short at the front station")
if Z_DRUM0 + 19 * Z_PITCH + DRUM_FACE / 2.0 > APINION_Z_BACK + 0.5:
    raise AssertionError("alignment pinion misses the j = 19 station")
if (
    math.hypot(APINION_X - X_DRUM, Y_DRIVE - APINION_Y)
    < TIP_DRUM120 + TIP_APINION + 1.0
):
    raise AssertionError("alignment pinion crowds the cylinder train")
if math.hypot(PIVOT_X - X_DRUM, Y_DRIVE - PIVOT_Y) > ENGAGED_C2C + STRAP_C2C - 0.25:
    raise AssertionError("engage swing cannot reach the meshed centre distance")
for _j in range(20):
    _tip = CONE_T120_PITCH_R - RADIUS_STEP * _j + ADDENDUM
    if (
        math.hypot(APINION_X - cone_seat(_j)[0], Y_DRIVE - APINION_Y)
        < _tip + TIP_APINION + 0.25
    ):
        raise AssertionError(f"pinion drum crowds cone gear {_j}")
if (
    math.hypot(APINION_X - GEAR64_SEAT[0], Y_DRIVE - APINION_Y)
    < R64 + ADD16 + TIP_APINION + 0.25
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
# The east-leaning lever shaft passes under the pinion ARBOR (PR7: the Ø8
# steel arbor replaced the drum's Ø6.35 stubs; it spans the lever's z band,
# so the 3D clearance is the 2D distance from the arbor's (x, y) to the Ø6
# rod-root axis line). Perpendicular form when the foot lands on the rod
# segment, endpoint distance otherwise. Rod ROOT dia books the worst case
# (the PR7 taper only thins toward the tip).
_LEV_T = math.radians(LEVER_TILT_DEG)
_LEV_U = (-math.sin(_LEV_T), math.cos(_LEV_T))  # up the rod: rot_z(+tilt) tips
# the +Y rod toward -X (CCW), so the placement and this check agree (2026-09:
# the old +sin let a +40 lean read as clear while the gate found it in the arbor)
_LEV_REL = (APINION_X - LIFT_X, APINION_Y - LIFT_Y)  # root -> arbor axis
_LEV_FOOT = _LEV_REL[0] * _LEV_U[0] + _LEV_REL[1] * _LEV_U[1]
if 0.0 <= _LEV_FOOT <= LEVER_LEN:
    _LEV_STUB_D = abs(_LEV_REL[0] * _LEV_U[1] - _LEV_REL[1] * _LEV_U[0])
else:
    _end = min(max(_LEV_FOOT, 0.0), LEVER_LEN)
    _LEV_STUB_D = math.hypot(
        _LEV_REL[0] - _end * _LEV_U[0], _LEV_REL[1] - _end * _LEV_U[1]
    )
if _LEV_STUB_D < (ARBOR_DIA + max(LEVER_ROD_DIA, LEVER_ROD_TIP_DIA)) / 2.0 + 0.25:
    raise AssertionError("lever shaft crowds the pinion arbor")

# --- pinion return spring (ch. 25, p.68-69): keeps the drum disengaged -------
# Brass leaf east of the BACK strap only (t00393 shows the front strap clean):
# foot flat on the base pointing WEST (crossing under the lift rod so its
# black hold-down screw lands west of the whole moving rig -- img01's
# far-left dark head), blade rising parallel to the parked strap's east
# flank; near the top a SUBTLE BEND BACK (PR7 item 10): the kink's convex
# crest is the parked contact edge, the flat above it the engaged contact
# face. Engaging the drum swings the strap east INTO the blade -- in the
# real machine the leaf flexes and pushes the swing back west (the default-
# disengaged behaviour); in rigid CAD the engaged pose overlaps the unflexed
# blade, a documented simplification: only the PARKED pose is interference-
# gated. The cam engage path (PR5, below) defines the engaged pose; flexed
# spring geometry for it stays deferred -- issue #158 (the channel springs'
# stretchNN precedent is the eventual shape of the fix).
# Geometry is imported from pinion_spring_geometry (machine = part local +
# (SPRING_X, Y_BASE_TOP)). The thin wall is ONE-sided; the part's 1%-tol
# volume gate pins the probed side (right-of-travel: under the foot, EAST
# of the blade/flat centreline), but every clearance that can afford it
# still books the full 0.8 on whichever side hurts. The flat-tip-vs-cap
# check below is the one exception -- it relies on the gated east side.
SPRING_X = PIVOT_X + SPR_PIVOT_LX  # machine anchor; the part is placed Ry(180)
# (its local +x runs machine -x), so every local-x offset below SUBTRACTS.
SPRING_Z = APINION_Z_BACK + STRAP_AIR + STRAP_T / 2.0  # 106.365: back strap
_SPR_TH = math.radians(-STRAP_LEAN_DEG)  # blade leans east of vertical
_SPR_U = (math.sin(_SPR_TH), math.cos(_SPR_TH))  # up the blade
_SPR_N = (-math.cos(_SPR_TH), math.sin(_SPR_TH))  # east normal of the axis
# (east = machine -x)
_SPR_PIVOT = (SPRING_X - SPR_PIVOT_LX, Y_BASE_TOP + SPR_PIVOT_LY)
SPRING_CREST = (SPRING_X - SPR_CREST_L[0], Y_BASE_TOP + SPR_CREST_L[1])
# the parked contact edge (kink start, tangent parallel to the strap axis)
SPRING_FLAT_TIP = (SPRING_X - SPR_FLAT_TIP_L[0], Y_BASE_TOP + SPR_FLAT_TIP_L[1])
SPRING_FOOT_TOP = Y_BASE_TOP + SPRING_T  # wall under the foot centreline
SPRING_HOLE_X = SPRING_X - SPR_FOOT_END_L[0] - SPR_HOLE_FROM_END

if math.hypot(_SPR_PIVOT[0] - PIVOT_X, _SPR_PIVOT[1] - PIVOT_Y) > 0.01:
    raise AssertionError("spring part frame disagrees with the strap pivot")
if abs(SPR_BLADE_TILT_DEG - STRAP_LEAN_DEG) > 0.01:
    raise AssertionError("spring blade is not parallel to the parked strap")
if SPRING_AXIS_OFF - STRAP_R_END - SPRING_T < 0.25 - 1e-9:
    raise AssertionError("spring blade touches the parked strap flank")
if SPRING_W / 2.0 > STRAP_T / 2.0:
    raise AssertionError("spring blade overhangs the strap flank axially")
if abs((LIFT_X - PIVOT_X) * _SPR_N[0] - SPRING_AXIS_OFF) - SPRING_T - 3.175 < 0.25:
    raise AssertionError("spring blade fouls the lift rod")  # perpendicular
    # foot of the rod axis lands mid-blade, so the segment bound is the line's
    # (west rod: the blade sits 10.1 EAST of the strap axis, the rod ~14.7 WEST)
if (
    math.hypot(X_DRUM - SPRING_CREST[0], Y_DRIVE - SPRING_CREST[1]) - SPRING_T
    < TIP_DRUM120 + 0.25
):
    raise AssertionError("spring contact crest crowds the cylinder-gear tips")
if (
    math.hypot(X_DRUM - SPRING_FLAT_TIP[0], Y_DRIVE - SPRING_FLAT_TIP[1]) - SPRING_T
    < TIP_DRUM120 + 0.25
):
    raise AssertionError("spring flat tip crowds the cylinder-gear tips")
if (
    math.hypot(SPRING_CREST[0] - APINION_X, SPRING_CREST[1] - APINION_Y)
    < STRAP_R_END + SPRING_T + 0.25
):
    raise AssertionError("spring contact crest reaches the strap's arbor end cap")
# The flat tips back WEST toward the strap; its wall is on the gated EAST
# side, so the governing surface is the centreline itself. Two constraints,
# tip-governed (n falls monotonically along kink + flat): the parked FLANK
# line (n = R_END, the 6.28 mm^3 interference the first PR7 build hit at
# FLAT_LEN 6) and the arbor-end cap circle.
_FLAT_TIP_N = (SPRING_FLAT_TIP[0] - PIVOT_X) * _SPR_N[0] + (
    SPRING_FLAT_TIP[1] - PIVOT_Y
) * _SPR_N[1]
if _FLAT_TIP_N < STRAP_R_END + 0.25:
    raise AssertionError("spring flat tip re-enters the parked strap flank")
if (
    math.hypot(SPRING_FLAT_TIP[0] - APINION_X, SPRING_FLAT_TIP[1] - APINION_Y)
    < STRAP_R_END + 0.25
):
    raise AssertionError("spring flat tip reaches the strap's arbor end cap")
if SPRING_Z + SPRING_W / 2.0 > BLOCK_BACK_Z0 - 0.25:
    raise AssertionError("spring reaches the back pivot block")
# West foot corridor (PR7 item 11): the strip crosses UNDER the lift rod and
# the back cam collar; its screw head must clear the rod flank. (The rod now
# rides at LIFT_Y, PR8; the collar sweep is bounded in the cam block below.)
if (LIFT_Y - 3.175) - SPRING_FOOT_TOP < 0.25:
    raise AssertionError("spring foot reaches the lift rod above it")
if (SPRING_HOLE_X - FSCREW_HEAD_DIA / 2.0) - (LIFT_X + 3.175) < 0.25:
    raise AssertionError("spring foot screw head crowds the lift rod")
if SPRING_HOLE_X + FSCREW_HEAD_DIA / 2.0 + 0.25 > SPRING_X - SPR_FOOT_END_L[0]:
    raise AssertionError("spring foot screw head overhangs the foot's free end")

# --- cam engage path (ch. 25 + page001_img01; PR8) ---------------------------
# Each strap carries a Ø4 follower STUD in a blind edge seat FPIN_DROP
# below the pivot (negative = above, 2026-09) (build_pinion_bracket); it RESTS ON the eccentric cam collar
# (build_pinion_cam) pinned to the lift rod in the reclosed WEST bore
# the pivot shaft in the blocks' reclosed west bores. Turning the lever spins rod +
# collars as one; the rising OD lifts the pin -- an upward push ~15 west of
# the pivot -- rotating the strap top EAST into mesh. Parked (ecc down, the
# authored pose) the collar top hovers a designed ~0.15 under the pin (exact
# tangency tips the interference gate on FP noise -- the PR5 gap lesson); the
# return spring holds the strap west on it.
if not STRAP_PIN_BORE <= FPIN_DIA <= STRAP_PIN_BORE + 0.020:
    raise AssertionError("follower pin nominal is outside the strap press-fit band")
if abs(FPIN_SEAT - FPIN_SEAT_LEN) > 1e-9:
    raise AssertionError("pin SEAT_LEN disagrees with the bracket PIN_SEAT")
if not 6.36 <= CAM_BORE_DIA <= 6.375:
    raise AssertionError("cam bore nominal is outside its O6.360-O6.375 fit limits")
if CAM_THIN_SIDE_WALL < 0.5:
    raise AssertionError("cam thin-side wall is below 0.5 mm")
# Blind-seat integrity: nearest approach of the seat cylinder to the pivot
# bore (perpendicular skew axes; the worst point is the seat bottom).
_FPIN_S0 = STRAP_R_END - FPIN_SEAT  # 5.0: seat bottom, from the centreline
if math.hypot(_FPIN_S0, FPIN_DROP) - FPIN_DIA / 2.0 - STRAP_PIVOT_BORE / 2.0 < 0.15:
    raise AssertionError("blind pin seat cuts too close to the pivot bore")
# Pin axis, machine frame: through the strap axis FPIN_DROP below the pivot,
# running WEST along -N (the axis RISES going west, N[1] < 0).
_FPIN_C = (PIVOT_X - FPIN_DROP * _SPR_U[0], PIVOT_Y - FPIN_DROP * _SPR_U[1])
_FPIN_TIP_S = _FPIN_S0 + FPIN_LEN  # 20: dome end station, from the centreline
_S_CAM = (_FPIN_C[0] - LIFT_X) / _SPR_N[0]  # 14.9: where the pin crosses the
# rod/cam plane x = LIFT_X
if _FPIN_TIP_S - _S_CAM < 2.0:
    raise AssertionError("follower pin ends short of the cam axis")
if _S_CAM - _FPIN_S0 < 2.0:
    raise AssertionError("cam contact lands inside the strap edge, not the pin")
_FPIN_Y_AT_CAM = _FPIN_C[1] - _S_CAM * _SPR_N[1]  # 64.04

# Cam z stations: the follower pin rides near each collar's BACK face --
# station CAM_PIN_STATION of the 9-long collar, NOT the middle -- so the
# set-pin boss (front region, BOSS_Z +- BOSS_R) clears BOTH the pin's z band
# and (back cam) the spring foot crossing beneath, at EVERY azimuth of the
# free cam spin (codex review 2026-07-05: a mid-mounted collar put the boss
# 0.8 into the pin's band on the engaged side, invisible to the parked gate).
_STRAP_MID_Z = (
    APINION_Z_FRONT - STRAP_AIR - STRAP_T / 2.0,  # -42.335
    APINION_Z_BACK + STRAP_AIR + STRAP_T / 2.0,  # +106.365
)
CAM_PIN_STATION = 7.0  # pin plane, from the collar front face
CAM_Z0 = tuple(z - CAM_PIN_STATION for z in _STRAP_MID_Z)
for _z0 in CAM_Z0:
    if _z0 < LIFT_ROD_Z0 + 1.0 or _z0 + CAM_LEN > LIFT_ROD_Z0 + 202.0 - 1.0:
        raise AssertionError("cam collar overhangs the lift rod")
if not CAM_BOSS_Z + CAM_BOSS_DIA / 2.0 + 0.25 <= CAM_PIN_STATION - FPIN_DIA / 2.0:
    raise AssertionError("set-pin boss z band reaches the follower pin's band")
if CAM_PIN_STATION > CAM_LEN - 1.0:
    raise AssertionError("follower pin rides off the collar's back face")
# Back cam only: the boss z band must also clear the spring foot's band
# (the strip crosses under the collar at the same z region).
_BOSS_Z_BACK = (
    CAM_Z0[1] + CAM_BOSS_Z - CAM_BOSS_DIA / 2.0,
    CAM_Z0[1] + CAM_BOSS_Z + CAM_BOSS_DIA / 2.0,
)
if (
    _BOSS_Z_BACK[1] > SPRING_Z - SPRING_W / 2.0 - 0.25
    and _BOSS_Z_BACK[0] < SPRING_Z + SPRING_W / 2.0 + 0.25
):
    raise AssertionError("set-pin boss z band overlaps the spring foot band")


# PARK: collar (ecc down) under the pin, by design 0.10..0.25 of air. The
# binding quantity is the SKEW-perpendicular distance from the collar axis's
# in-plane point to the LEANING pin line, minus the radii sum -- NOT the
# vertical gap at the crossing x (that mistake put the first build 0.009
# into the collar: the pin's closest approach is downhill-west of the
# crossing). The collar axis pierces the pin's z-plane at (LIFT_X, LIFT_Y -
# ECC) parked; the pin line runs from _FPIN_C along -N.
def _pin_line_dist(centre_y: float, c=None, n=None) -> float:
    """Perpendicular distance from (LIFT_X, centre_y) to the pin axis line."""
    c = c if c is not None else _FPIN_C
    n = n if n is not None else _SPR_N
    dx, dy = LIFT_X - c[0], centre_y - c[1]
    return abs(dx * (-n[1]) - dy * (-n[0]))


_PARK_GAP = _pin_line_dist(LIFT_Y - CAM_ECC) - (FPIN_DIA + CAM_OD) / 2.0
if not 0.10 <= _PARK_GAP <= 0.25:
    raise AssertionError(f"park gap {_PARK_GAP:.3f} outside the 0.10..0.25 design band")

# Engage swing angle from the c2c triangle (pivot, drum axis, pinion axis):
# parked ray angle minus engaged ray angle about the pivot, both from +x.
_PD = math.hypot(X_DRUM - PIVOT_X, Y_DRIVE - PIVOT_Y)  # 68.05 pivot -> drum
_ANG_PARKED = math.atan2(APINION_Y - PIVOT_Y, APINION_X - PIVOT_X)
_ANG_ENGAGED = math.atan2(Y_DRIVE - PIVOT_Y, X_DRUM - PIVOT_X) - math.acos(
    max(
        -1.0,
        min(1.0, (STRAP_C2C**2 + _PD**2 - ENGAGED_C2C**2) / (2.0 * STRAP_C2C * _PD)),
    )
)
_PHI_ENG = _ANG_ENGAGED - _ANG_PARKED  # ~4.1 deg CCW, radians
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
_NEED_LIFT = _FPIN_Y_AT_CAM_ENG - _FPIN_Y_AT_CAM  # ~1.07 up
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


# Bracket scallop closure. The lift rod is base-fixed while the bracket swings,
# so its centre traces an arc in the bracket's local frame. The part carries
# two R6.90 open scallops at the parked/engaged endpoint centres; their overlap
# must cover the full collar sweep plus 0.25 air over the intervening arc.
def _lift_axis_in_strap(lean_rad: float) -> tuple[float, float]:
    dx, dy = LIFT_X - PIVOT_X, LIFT_Y - PIVOT_Y
    c, s = math.cos(lean_rad), math.sin(lean_rad)
    return (-dx * c - dy * s, -dx * s + dy * c)


_RELIEF_PARK_ACTUAL = _lift_axis_in_strap(math.radians(STRAP_LEAN_DEG))
_RELIEF_ENG_ACTUAL = _lift_axis_in_strap(math.radians(STRAP_LEAN_DEG) + _PHI_ENG)
for _label, _actual, _authored in (
    ("parked", _RELIEF_PARK_ACTUAL, STRAP_CAM_RELIEF_PARK),
    ("engaged", _RELIEF_ENG_ACTUAL, STRAP_CAM_RELIEF_ENGAGED),
):
    if math.dist(_actual, _authored) > 0.001:
        raise AssertionError(
            f"bracket cam relief {_label} centre {_authored} != linkage {_actual}"
        )
_RELIEF_CENTRE_CHORD = math.dist(_RELIEF_PARK_ACTUAL, _RELIEF_ENG_ACTUAL)
_RELIEF_ARC_SAGITTA = math.hypot(LIFT_X - PIVOT_X, LIFT_Y - PIVOT_Y) * (
    1.0 - math.cos(_PHI_ENG / 2.0)
)
_RELIEF_REQUIRED_R = (
    math.hypot(STRAP_CAM_RELIEF_ENVELOPE_R, _RELIEF_CENTRE_CHORD / 2.0)
    + _RELIEF_ARC_SAGITTA
)
if STRAP_CAM_RELIEF_R < _RELIEF_REQUIRED_R:
    raise AssertionError(
        f"bracket cam relief R{STRAP_CAM_RELIEF_R:.3f} does not cover "
        f"R{_RELIEF_REQUIRED_R:.3f} moving envelope"
    )
# Seat mouth: on the straight flank when the stud sits between the two bores
# (0 <= -FPIN_DROP <= C2C), else on the end cap arc.
_PIN_SEAT_SURFACE_X = (
    -STRAP_R_END
    if 0.0 <= -FPIN_DROP <= STRAP_C2C
    else -math.sqrt(STRAP_R_END**2 - FPIN_DROP**2)
)
_PIN_SEAT_BOTTOM_X = -(STRAP_R_END - FPIN_SEAT)
_PIN_SEAT_OPEN_X = _PIN_SEAT_SURFACE_X
for _cx, _cy in (STRAP_CAM_RELIEF_PARK, STRAP_CAM_RELIEF_ENGAGED):
    _dy = -FPIN_DROP - _cy
    if abs(_dy) < STRAP_CAM_RELIEF_R:
        _PIN_SEAT_OPEN_X = max(
            _PIN_SEAT_OPEN_X,
            _cx + math.sqrt(STRAP_CAM_RELIEF_R**2 - _dy**2),
        )
_PIN_SEAT_REMAINING = _PIN_SEAT_BOTTOM_X - _PIN_SEAT_OPEN_X
if _PIN_SEAT_REMAINING < 1.5:
    raise AssertionError(
        f"cam scallop leaves only {_PIN_SEAT_REMAINING:.3f} mm follower-stud seat"
    )

# Full-rotation sweep of collar + set-pin boss about the rod axis. The boss
# sweep books its OUTER CORNER -- hypot(axis reach, boss radius), not just
# the axis tip (codex review 2026-07-05) -- against the base and the pivot
# shaft; the spring foot shares z only with the bare collar (the boss z band
# clears it above), so the foot books the collar OD sweep.
_CAM_SWEEP_R = math.hypot(
    CAM_ECC + CAM_OD / 2.0 + CAM_BOSS_PROUD, CAM_BOSS_DIA / 2.0
)  # 6.31 corner
_COLLAR_SWEEP_R = CAM_ECC + CAM_OD / 2.0  # 5.6 bare collar
if LIFT_Y - _CAM_SWEEP_R - Y_BASE_TOP < 0.25:
    raise AssertionError("cam boss sweep reaches the base top")
if LIFT_Y - _COLLAR_SWEEP_R - SPRING_FOOT_TOP < 0.25:
    raise AssertionError("cam collar sweep dips into the spring foot below")
if math.hypot(PIVOT_X - LIFT_X, PIVOT_Y - LIFT_Y) - _CAM_SWEEP_R - 3.175 < 0.25:
    raise AssertionError("cam sweep reaches the pivot shaft")

# --- full-rotation clearance proofs (PR6) -------------------------------------
# The interference gate sees only the PARKED pose; the tee handle spins full
# circle during zeroing and the lift rod (pins + lever) sweeps the cam throw.
# Prove every angle clears the in-assembly neighbours: each sweep is a solid
# of revolution, so a neighbour is cleared by z-band disjointness or, where
# bands overlap, by radial clearance from the sweep axis. (Cross-assembly
# neighbours are parked-gated at the top level; the platen/pen hardware sits
# at y ~390+, far above both sweeps.)
# Handle geometry is imported (PR7 img07 re-derivation: arms 42/43, the
# grip a Ø23 cylinder + domed cap, the hub a blind tube over the arbor).
# The SWEPT geometry splits in two: the Ø6 cross rod sweeps a R43.5 disc
# (max(HANDLE_ARM_DOWN, HANDLE_ARM_UP) + 0.5; the long arm's flat-end corner
# reaches hypot(43, 3) = 43.1)
# in its own thin band; the grip + cap + tube hub stay ON AXIS (R11.5 worst),
# only their z reach is wider.
_TEE_DISC_Z = (
    HANDLE_Z - HANDLE_ROD_DIA / 2.0,
    HANDLE_Z + HANDLE_ROD_DIA / 2.0,
)
_TEE_HUB_Z = (
    HANDLE_Z - HANDLE_GRIP_LEN / 2.0 - HANDLE_CAP_SAG,
    HANDLE_Z + HANDLE_GRIP_LEN / 2.0 + HANDLE_WALL_T + HANDLE_TUBE_LEN,
)  # -153 .. -125: cap, grip, blind wall, tube seat
# In-assembly bodies near the tee: everything of the swing rig ends well
# north of the disc band; the crank cluster lives south/east of it.
for _lo, _hi, _what in (
    (
        LEVER_Z - LEVER_HUB_LEN / 2.0 - LEVER_CAP_SAG,
        LEVER_Z + LEVER_HUB_LEN / 2.0,
        "lever hub",
    ),
    (BLOCK_FRONT_Z0, BLOCK_FRONT_Z0 + BLOCK_DEPTH, "front pivot block"),
    (LIFT_ROD_Z0, LIFT_ROD_Z0 + 202.0, "lift rod"),
    (PIVOT_SHAFT_Z0, PIVOT_SHAFT_Z0 + 192.0, "pivot shaft"),
    (APINION_Z_FRONT - STRAP_T - STRAP_AIR, APINION_Z_FRONT, "front strap"),
    (REMOVABLE_Z0, REMOVABLE_Z0 + 5.0, "T12 chain wheel"),
    (CRANK_ARM_Z0, CRANK_ARM_Z0 + ARM_THICKNESS, "crank arm hub"),
):
    if _TEE_DISC_Z[1] > _lo - 0.25 and _TEE_DISC_Z[0] < _hi + 0.25:
        raise AssertionError(f"tee-handle sweep disc band reaches the {_what}")
# The hub's wider z band DOES clip the T12 plane: radial clearance instead
# (the grip is on-axis, the wheel is on the crank axis). The crank arm+handle
# sweep entirely south of the arm hub (-175..) -- z-disjoint from the grip.
if (
    math.hypot(X_CRANK - APINION_X, Y_CRANK - APINION_Y)
    < HANDLE_GRIP_DIA / 2.0 + 16.0 + 0.25
):  # T12 OD/2 ~14 + margin
    raise AssertionError("tee-handle grip reaches the T12 chain wheel")
if _TEE_HUB_Z[0] < CRANK_ARM_Z0 + ARM_THICKNESS + 0.25:
    raise AssertionError("tee-handle grip band reaches the crank arm sweep")

# Lever full throw (parked 40 deg -> engaged ~51 deg, checked to 60): the
# arbor distance grows monotonically past 37.6 deg, but prove it numerically,
# and prove the swept tip annulus shares no z band with anything it could hit.
for _step in range(0, 81):
    _t = math.radians(LEVER_TILT_DEG + math.copysign(_step * 0.25, LEVER_TILT_DEG))
    # rod direction (-sin t, cos t), the placement's rot_z convention (see _LEV_U)
    _d = abs(_LEV_REL[0] * math.cos(_t) + _LEV_REL[1] * math.sin(_t))
    if _d < (ARBOR_DIA + max(LEVER_ROD_DIA, LEVER_ROD_TIP_DIA)) / 2.0 + 0.25:
        raise AssertionError("lever shaft crowds the arbor mid-throw")
_LEV_Z = (LEVER_Z - 3.0, LEVER_Z + 3.0)  # rod plane through the throw
if (
    _LEV_Z[0] < BLOCK_FRONT_Z0 + BLOCK_DEPTH + 0.25
    and _LEV_Z[1] > BLOCK_FRONT_Z0 - 0.25
):
    raise AssertionError("lever throw plane reaches the front pivot block")
if _LEV_Z[1] > PIVOT_SHAFT_Z0 - 0.25:
    raise AssertionError("lever throw plane reaches the pivot shaft front end")
if _LEV_Z[0] < _TEE_HUB_Z[1] + 0.25:
    raise AssertionError("lever throw plane reaches the tee-handle sweep")

# (The PR5 rod-pin throw checks died with the pins; the cam block above
# bounds the collar + boss sweep against the base, spring foot and shaft.)

# --- pinion arbor + rig fasteners (PR7 items 2/11/12/14) ---------------------
# The steel Ø8 arbor replaced the drum's integral stubs: it presses through
# the drum, journals in both straps' top bores, and its flat front tip seats
# flush on the tee handle's blind-cap bore floor.
ARBOR_Z0 = -135.0 + MECHANISM_Z_SHIFT
if abs((HANDLE_Z + HANDLE_GRIP_LEN / 2.0 + HANDLE_WALL_T) - ARBOR_Z0) > 1e-9:
    raise AssertionError("arbor front tip off the handle cap's bore floor")
if abs(ARBOR_Z0 + ARBOR_LEN - (91.25 + MECHANISM_Z_SHIFT)) > 0.01:
    raise AssertionError("arbor back end off the translated p2 station")
if not (ARBOR_DIA == DRUM_BORE_DIA == HANDLE_TUBE_ID == STRAP_ARBOR_BORE):
    raise AssertionError("arbor dia disagrees with drum bore/handle tube/strap bore")
if abs(STRAP_PIVOT_BORE - 6.35) > 1e-9:
    raise AssertionError("strap pivot bore no longer rides the O6.35 shaft")
# Block screws (item 12): two bright slotted heads per block, seated on the
# block top, shanks dropping through the O4.2 block holes into the base.
BLOCK_TOP_Y = PIVOT_Y + (BLOCK_HEIGHT - BLOCK_BORE_UP)  # 66.8
if BSCREW_SHANK_DIA > BLOCK_SCREW_HOLE_DIA - 0.1:
    raise AssertionError("block screw shank binds in the block hole")
if BSCREW_SHANK_DIA > BASE_BLOCK_HOLE_DIA - 0.1:
    raise AssertionError("block screw shank binds in the base hole")
if BSCREW_SHANK_LEN - BLOCK_HEIGHT < 1.0:
    raise AssertionError("block screw barely engages the base")
if BSCREW_SHANK_LEN - BLOCK_HEIGHT > BASE_BLOCK_HOLE_DEPTH - 0.25:
    raise AssertionError("block screw bottoms out in the base hole")
if BLOCK_SCREW_HALF + BSCREW_HEAD_DIA / 2.0 > BLOCK_WIDTH / 2.0 - 0.25:
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
# Foot screws (items 2 + 11): the black O2.9 hold-down at the spring foot
# and on the pedestal's exposed flange.
if FSCREW_SHANK_DIA > min(SPR_HOLE_DIA, ARBOR_PED_HOLE_DIA, BASE_FOOT_HOLE_DIA) - 0.1:
    raise AssertionError("foot screw shank binds in a foot hole")
if FSCREW_SHANK_LEN - ARBOR_PED_FLANGE_T < 2.0:
    raise AssertionError("foot screw barely engages the base at the pedestal")
if FSCREW_SHANK_LEN - SPRING_T > BASE_FOOT_HOLE_DEPTH - 0.25:
    raise AssertionError("foot screw bottoms out in the base hole (spring seat)")
# Head fits the pedestal's exposed flange strip (local z -8..-2, centre -5).
if FSCREW_HEAD_DIA / 2.0 > min(
    abs(ARBOR_PED_SCREW_Z + ARBOR_PED_DEPTH / 2.0),
    abs(ARBOR_PED_DEPTH / 2.0 - ARBOR_PED_STRAP_T - ARBOR_PED_SCREW_Z),
):
    raise AssertionError("foot screw head overhangs the pedestal flange")
_FOOT_SCREW_XZ = (
    (SPRING_HOLE_X, SPRING_Z),
    (X_DRUM, -ARBOR_PEDESTAL_Z + ARBOR_PED_SCREW_Z),
    # North pedestal (ry180 flips its flange to +z): z_c - SCREW_Z = 102.5.
    (X_DRUM, ARBOR_PEDESTAL_NORTH_Z - ARBOR_PED_SCREW_Z),
)

# Both machine-handed: the base holes agree directly.
for _want, _have in zip(_FOOT_SCREW_XZ, BASE_FOOT_XZ, strict=True):
    if abs(_want[0] - _have[0]) > 0.05 or abs(_want[1] - _have[1]) > 0.05:
        raise AssertionError(
            f"harmonic-base foot-screw hole {_have} != machine derived "
            f"({_want[0]:.3f}, {_want[1]:.3f})"
        )


IDENTITY = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
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
ROT_SHAFT_NORTH = [  # +Y -> the increasing-station shaft direction (bushing)
    [COS_I, 0.0, -SIN_I],
    [SIN_I, 0.0, COS_I],
    [0.0, -1.0, 0.0],
]
ROT_SHAFT_SOUTH = [  # +Y -> the decreasing-station direction (adjuster: head north)
    [COS_I, 0.0, -SIN_I],
    [-SIN_I, 0.0, -COS_I],
    [0.0, 1.0, 0.0],
]
ROT_PINCH_WEST = [  # +Y -> plate-frame -X: the head seats east, the shank runs west
    [0.0, -1.0, 0.0],
    [-COS_I, 0.0, SIN_I],
    [-SIN_I, 0.0, -COS_I],
]
PINCH_WEST_EULER = euler_from_rows(ROT_PINCH_WEST)  # [180-INCLINE, 0, -90]


def rot_z_rows(deg: float) -> list[list[float]]:
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [[c, s, 0.0], [-s, c, 0.0], [0.0, 0.0, 1.0]]


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
) -> None:
    """Key a gear rigidly onto a shaft via SEMANTIC mates, replacing a lock:
    coaxial (collinear axes) + an axial seat (Front-plane distance along the
    shaft axis, read live) + a parallel anti-spin. The gear and shaft share the
    inclined orientation (ROT_Y_INCLINE), so their Right planes are parallel at
    the keyed phase -- the parallel pins the spin with no tuned angle (the
    lag-screw idiom). Removes the same 6 DOF the lock did; no fix/lock."""
    p_o = _org(adapter, part)
    d_axial = sum((p_o[k] - shaft_o[k]) * axis_dir[k] for k in range(3))
    await coincident_mate(
        adapter,
        named_ref(f"{part_axis}@{part}", "AXIS"),
        shaft_axis_ref,
        label=f"{label} coaxial",
        verify=(part, p_o),
    )
    await distance_driver(
        adapter,
        named_ref(f"Front Plane@{part}", "PLANE"),
        named_ref(f"Front Plane@{shaft}", "PLANE"),
        d_axial,
        label=f"{label} axial seat d={d_axial:.2f}",
        verify=(part, p_o),
    )
    await parallel_mate(
        adapter,
        named_ref(f"Right Plane@{part}", "PLANE"),
        named_ref(f"Right Plane@{shaft}", "PLANE"),
        label=f"{label} anti-spin (keyed phase)",
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
    """Journal a crank-chain part on the crankshaft via SEMANTIC mates: coaxial
    on the crank axis + an axial seat -- the part's Z-normal Front plane
    COINCIDENT to the crankshaft's named seat datum ('SeatT12'/'SeatPinion'/
    'SeatArm'). Coincident replaces the old
    UNSIGNED plane-plane distance, whose two solution branches let the free-
    spinning crank family reflect about the shaft origin on a re-solve: the
    16T rendered floating ~200 south of its seat with every gate green
    (render-gate catch, 2026-07-04). The seat must reference the crankshaft,
    NOT a world datum (a world plane pins the crank axis to machine z and
    through it the whole p1 swing). Leaves ONLY spin -- the caller pins it
    with a per-part anti-spin. Returns the part's live origin."""
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


def _force_rebuild_after_cone_replication(adapter, model) -> None:
    """Regenerate all switched cone configurations, then reject real faults.

    Assigning ``ReferencedConfiguration`` dirties the copied component model.
    ``EditRebuild3`` only updates features already marked dirty in the active
    assembly configuration and, since the cone-gear PMI regeneration sweep,
    can report the temporary ``swFeatureErrorUnknown`` state on every copy.
    One deep ``ForceRebuild3(False)`` after all 19 switches regenerates those
    child configurations and solves the assembly in the proven health-gate
    order.  Its boolean remains authoritative: a genuine rebuild failure is
    diagnosed and rejected, never treated as the known transient.
    """
    rebuilt = adapter._attempt(lambda: model.ForceRebuild3(False), default=None)
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
            "ForceRebuild3 after cone-gear replication returned "
            f"{rebuilt!r}; hard faults: {hard_faults or ['none reported']}; "
            f"warnings: {warnings or ['none reported']}"
        )


async def build(adapter) -> dict[str, str]:
    # Reset the free-DOF manifest buffer before any *_driver(free_dof_key=...)
    # call: each freed DOF is recorded (never authored) and persisted below.
    reset_dof_manifest()
    check("create_assembly", await adapter.create_assembly())

    # =================== structure (static lock + moving joints) ===========
    # The stationary arbor is the reference frame the moving train mates
    # against. Inserted FIRST, so SolidWorks auto-fixes it as the seed (the one
    # allowed fixed component, mirroring frame's harmonic-base) -- no explicit fix.
    arbor = await place_component(
        adapter,
        "cylinder-gear-shaft",
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
        "arbor-pedestal",
        [X_DRUM, Y_BASE_TOP, -ARBOR_PEDESTAL_Z],
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
        label=f"arbor-pedestal z={-ARBOR_PEDESTAL_Z:g}",
    )
    await _lock_static(adapter, arbor_pedestal, arbor)
    # NORTH pedestal (PR8, ch12 img09): the same casting rotated 180 about Y
    # so its strap face looks south at the drum's north end; the arbor's +97
    # end seats 7.5 into its bore band. Base-bolted static like the south one.
    north_pedestal = await place_component(
        adapter,
        "arbor-pedestal",
        [X_DRUM, Y_BASE_TOP, ARBOR_PEDESTAL_NORTH_Z],
        [0.0, 180.0, 0.0],
        [[-1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, -1.0]],
        ground=False,
        label=f"arbor-pedestal north z={ARBOR_PEDESTAL_NORTH_Z:g}",
    )
    await _lock_static(adapter, north_pedestal, arbor)
    # Cylinder end discs: one against each pedestal strap (END_DISC_AIR off),
    # riding the arbor; retained like the pedestals (they turn with nothing).
    for _disc_z0, _end in ((END_DISC_SOUTH_Z0, "south"), (END_DISC_NORTH_Z0, "north")):
        end_disc = await place_component(
            adapter,
            "cylinder-end-disc",
            [X_DRUM, Y_DRIVE, _disc_z0],
            [0.0, 0.0, 0.0],
            IDENTITY,
            ground=False,
            label=f"cylinder end disc {_end} z0={_disc_z0:.3f}",
        )
        await _lock_static(adapter, end_disc, arbor)
    # Dome cap screws: crown base on each strap's outer face, spigot into the
    # blind bore (+Y turned outward: -Z south, +Z north).
    for _cap_z, _euler, _rows, _end in (
        (
            CAP_SOUTH_Z,
            [-90.0, 0.0, 0.0],
            [[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]],
            "south",
        ),
        (CAP_NORTH_Z, [90.0, 0.0, 0.0], ROT_X_POS90, "north"),
    ):
        cap = await place_component(
            adapter,
            "dome-cap-screw",
            [X_DRUM, Y_DRIVE, _cap_z],
            _euler,
            _rows,
            ground=False,
            label=f"dome cap screw {_end} z={_cap_z:.3f}",
        )
        await _lock_static(adapter, cap, arbor)
    # The cone SWING PLATFORM is the swing bracket (ch.12, p.18 "pivot"):
    # floated so the whole cone set can swing horizontally out of mesh about
    # its tip-end vertical pivot (p1). Pinned at the engaged rest pose by a
    # suppressible angle driver in the joints section. The pivot post and tip
    # block are seated ON its PlateTop below, so they -- and the shaft they
    # journal -- ride the swing as one unit.
    ppivot = cone_station(PIVOT_STATION)
    platform = await place_component(
        adapter,
        "cone-swing-platform",
        [ppivot[0], Y_BASE_TOP, ppivot[2]],
        [0.0, INCLINE_DEG, 0.0],
        ROT_Y_INCLINE,
        ground=False,
        label="cone-swing-platform (swing bracket, engaged rest)",
    )
    ppost = cone_station(POST_STATION)
    pivot_post = await place_component(
        adapter,
        "cone-pivot-post",
        [ppost[0], Y_BASE_TOP + PLAT_T, ppost[2]],
        [0.0, POST_ROTATION_Y_DEG, 0.0],
        ROT_Y_180,
        ground=False,
        label="cone-pivot-post (v2 Ry180, big-end journal, on the plate)",
    )
    ptip = cone_station(TIP_BLOCK_STATION)
    tip_block = await place_component(
        adapter,
        "cone-tip-block",
        [ptip[0], Y_BASE_TOP + PLAT_T, ptip[2]],
        [0.0, INCLINE_DEG, 0.0],
        ROT_Y_INCLINE,
        ground=False,
        label="cone-tip-block (end-play adjuster support, on the plate)",
    )
    # Tip end-play stack (item 5, v4_t00471): the brass spacer bushing on the
    # tip stub, the axial adjuster screw in the block's counterbore, and the
    # pinch screw across the block's top slit. Stations derived at import
    # (BUSH_STATION / ADJ_HEAD_STATION); all three ride the swing family.
    pbush = cone_station(BUSH_STATION)
    tip_bushing = await place_component(
        adapter,
        "cone-tip-bushing",
        [pbush[0], Y_DRIVE, pbush[2]],
        [90.0, INCLINE_DEG, 0.0],
        ROT_SHAFT_NORTH,
        ground=False,
        label="cone-tip-bushing (T006 spacer, on the tip stub)",
    )
    padj = cone_station(ADJ_HEAD_STATION)
    tip_adjuster = await place_component(
        adapter,
        "cone-tip-adjuster",
        [padj[0], Y_DRIVE, padj[2]],
        [-90.0, INCLINE_DEG, 0.0],
        ROT_SHAFT_SOUTH,
        ground=False,
        label="cone-tip-adjuster (axial end-play screw, head north)",
    )
    pinch_screw = await place_component(
        adapter,
        "cone-tip-pinch-screw",
        [
            ptip[0] - (TIP_BLOCK_X / 2.0) * COS_I,
            Y_BASE_TOP + PLAT_T + TIP_PINCH_Y,
            ptip[2] + (TIP_BLOCK_X / 2.0) * SIN_I,
        ],
        PINCH_WEST_EULER,
        ROT_PINCH_WEST,
        ground=False,
        label="cone-tip-pinch-screw (slit clamp, head east)",
    )
    # The lock knob (v4_t00411) is a base-bolted static like the pedestals: its
    # washer seat lands on the plate top, its stud drops through the plate's
    # lock slot (engaged end -- the as-built pose). The plate is the mover: on
    # disengage its slot sweeps around this stationary stud. No rotation: the
    # knob is axisymmetric and belongs to the BASE, not the inclined plate.
    lock_knob = await place_component(
        adapter,
        "cone-lock-knob",
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
    # matching blind #10-24 UNC seat.
    pivot_screw = await place_component(
        adapter,
        "cone-pivot-screw",
        [ppivot[0], Y_BASE_TOP + PSCREW_SHOULDER_LEN, ppivot[2]],
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
        label="cone-pivot-screw (p1 pivot pin)",
    )
    await _lock_static(adapter, pivot_screw, arbor)
    # The swing-stop screw (item 6): a base-threaded STATIC just past the
    # DISENGAGED pose -- the plate's west edge bumps its proud shank, limiting
    # the p1 swing to exactly the knob-clear travel (STOP_X/STOP_Z derived at
    # import and asserted against the base's hardcoded hole).
    stop_screw = await place_component(
        adapter,
        "swing-stop-screw",
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
    # freed pinion_cam DOF). The tee handle is LOCKED to the arbor in
    # the joints section (cross-pinned in the real machine) so the freed p2
    # swing carries it with the rig -- it was base-FIXED while the swing was
    # pinned, which PR8's freed swing would have left hanging in space
    # (Codex catch, 2026-07-05).
    align_pinion = await place_component(
        adapter,
        "alignment-pinion",
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
    _strap_rows = compose_rows(ROT_Y_180, rot_z_rows(STRAP_LEAN_DEG))
    _strap_euler = euler_from_rows(_strap_rows)
    pinion_brackets: dict[str, str] = {}
    for tag, z0 in (
        ("front", APINION_Z_FRONT - STRAP_AIR),
        ("back", APINION_Z_BACK + STRAP_AIR + STRAP_T),
    ):
        pinion_brackets[tag] = await place_component(
            adapter,
            "pinion-bracket",
            [PIVOT_X, PIVOT_Y, z0],
            _strap_euler,
            _strap_rows,
            ground=False,
            label=f"pinion-bracket {tag} (leaning, arbor bore up top)",
        )
    pinion_blocks: list[str] = []
    for tag, z0 in (("front", BLOCK_FRONT_Z0), ("back", BLOCK_BACK_Z0)):
        blk = await place_component(
            adapter,
            "pinion-pivot-block",
            [BLOCK_X, PIVOT_Y, z0 + BLOCK_DEPTH],
            [0.0, 180.0, 0.0],
            ROT_Y_180,
            ground=False,
            label=f"pinion-pivot-block {tag}",
        )
        pinion_blocks.append(blk)
    pivot_shaft = await place_component(
        adapter,
        "pinion-pivot-shaft",
        [PIVOT_X, PIVOT_Y, PIVOT_SHAFT_Z0],
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
    )
    lift_rod = await place_component(
        adapter,
        "pinion-lift-rod",
        [LIFT_X, LIFT_Y, LIFT_ROD_Z0],
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
        label="pinion-lift-rod (in the blocks' raised west bores)",
    )
    spring = await place_component(
        adapter,
        "pinion-spring",
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
            "pinion-cam-pin",
            [_FPIN_ORG[0], _FPIN_ORG[1], z_mid],
            FPIN_EULER,
            FPIN_ROWS,
            ground=False,
            label=f"pinion-cam-pin {tag} (edge-seat follower)",
        )
    # Eccentric cam collars (PR8 items 8b/9): one per strap station, pinned to
    # the lift rod in the authored PARK pose (ecc + boss straight down).
    pinion_cams: dict[str, str] = {}
    for tag, z0 in (("front", CAM_Z0[0]), ("back", CAM_Z0[1])):
        pinion_cams[tag] = await place_component(
            adapter,
            "pinion-cam",
            [LIFT_X, LIFT_Y, z0],
            [0.0, 0.0, 0.0],
            IDENTITY,
            ground=False,
            label=f"pinion-cam {tag} (parked ecc down)",
        )
    lever = await place_component(
        adapter,
        "pinion-lever",
        [LIFT_X, LIFT_Y, LEVER_Z],
        [0.0, 0.0, LEVER_TILT_DEG],
        rot_z_rows(LEVER_TILT_DEG),  # +z spin tips east (-x)
        ground=False,
        label="pinion-lever (clamp hub on the lift rod front end)",
    )
    tee_handle = await place_component(
        adapter,
        "pinion-handle",
        [APINION_X, APINION_Y, HANDLE_Z],
        [0.0, 0.0, HANDLE_TILT_DEG],
        rot_z_rows(HANDLE_TILT_DEG),  # +z spin tips east (-x)
        ground=False,
        label="pinion-handle (blind cap over the arbor front end)",
    )
    # The steel arbor (PR7 item 14): pressed through the brass drum, journaled
    # in both straps' Ø8 top bores -- it RIDES the swing group (mated in the
    # joints section, not located: the engage swing carries it).
    pinion_arbor = await place_component(
        adapter,
        "pinion-arbor",
        [APINION_X, APINION_Y, ARBOR_Z0],
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
        label="pinion-arbor (steel, through the drum)",
    )
    # Rig hold-downs (PR7 items 2/11/12): physically located seeds are patterned
    # across the repeated block/pedestal stations in the joints section below.
    sx, sz = _BLOCK_SCREW_XZ[0]
    block_screw = await place_component(
        adapter,
        "slotted-screw",
        [sx, BLOCK_TOP_Y, sz],
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
        label="slotted-screw block hold-down seed",
    )
    foot_screws: list[str] = []
    for tag, (sx, sz), seat_y in (
        ("spring foot", _FOOT_SCREW_XZ[0], Y_BASE_TOP + SPRING_T),
        ("pedestal flange", _FOOT_SCREW_XZ[1], Y_BASE_TOP + ARBOR_PED_FLANGE_T),
    ):
        scr = await place_component(
            adapter,
            "foot-screw",
            [sx, seat_y, sz],
            [0.0, 0.0, 0.0],
            IDENTITY,
            ground=False,
            label=f"foot-screw ({tag})",
        )
        foot_screws.append(scr)

    # =================== cone cluster (driven, on-solution) ====================
    cone_shaft = await place_component(
        adapter,
        "cone-gear-shaft",
        cone_station(SHAFT_FRONT_STATION),  # part origin = the front stub end
        [0.0, INCLINE_DEG, 0.0],
        ROT_Y_INCLINE,
        ground=False,
    )
    gear64 = await _place_on_shaft(
        adapter,
        "crank-drive-gear",
        GEAR64_STATION + GEAR_AXIS_SHIFT,
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
        "cone-gear",
        SHAFT_T120_STATION + GEAR_AXIS_SHIFT,
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
    # face centre +1.5 keeps the 3-mm toothed slab centred on station z_j.
    cylinder_rows = compose_rows(ROT_Y_180, rot_z_rows(-1.5))
    cyl_gears: list[str] = [
        await place_component(
            adapter,
            "cylinder-gear",
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
        "crankshaft",
        [X_CRANK, Y_CRANK, CRANKSHAFT_Z0],
        [90.0, 0.0, 0.0],
        ROT_X_POS90,
        ground=False,
    )
    pinion = await place_component(
        adapter,
        "crank-pinion",
        [X_CRANK, Y_CRANK, PINION_TOOTH_Z - PINION_FACE / 2.0],
        [0.0, 0.0, -PINION_SEED_DEG],
        rot_z_rows(-PINION_SEED_DEG),  # tooth-in-gap
        ground=False,
        label="crank-pinion (centred on the 64T contact tooth)",
    )
    # The crank-end T12 chain wheel is NOT placed here: paper-drive now OWNS the
    # whole crank->paper chain drive (both sprockets + roller chain + belt), so the
    # single crank chain wheel lives in paper-drive (codex #189 :605). Placing it
    # here too made two coincident T12 wheels at the crank centre once both
    # subassemblies are inserted at the top level -> interference. drive-train keeps
    # only the crankshaft, arm, handle and 16T pinion; the crank spin DOF is
    # unchanged (crankshaft/arm, free_dof_key="crank_angle").
    # Crank rest pose: the arm hangs straight DOWN (ch30 eight-views -- the
    # handle reads "down" in all eight roll angles, which only a -Y arm does,
    # since a downward vector lies on the views' vertical rotation axis). The
    # arm part extrudes along its local +X; rot_z(-90) maps that to assembly
    # -Y, and the composed Ry(180) flips the plate's local +z extrusion to run
    # machine -z: the origin sits at the plate's NORTH face
    # (CRANK_ARM_ORIGIN_Z, -167) with the plate band filling -175..-167.
    arm = await place_component(
        adapter,
        "crank-arm",
        [X_CRANK, Y_CRANK, CRANK_ARM_ORIGIN_Z],
        [180.0, 0.0, -90.0],
        compose_rows(rot_z_rows(-90.0), ROT_Y_180),
        ground=False,
    )
    # Taper pin (2026-09-02, ch11 p.14): through the arm hub + the crankshaft
    # cross-hole along machine X at the arm's mid-thickness, big end PIN_PROUD
    # proud of the hub's outer (-X) face, the small end running out the far
    # side; the brass keeper ring hangs from the head's cross-hole (0.25 air
    # under the hole's bottom edge). Both lock to the arm so they spin with the
    # crank. The pin's nominal taper is larger than the arm's #14 / shaft's #9
    # pilot holes (they are taper-reamed together at assembly), so the two
    # overlaps are volume-bounded allowed pairs in _interference_contracts.
    pin = await place_component(
        adapter,
        "crank-pin",
        [CRANK_PIN_X0, Y_CRANK, CRANK_PIN_Z],
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
        label="crank taper pin",
    )
    await lock_mate(
        adapter,
        named_ref(f"Front Plane@{pin}", "PLANE"),
        named_ref(f"Front Plane@{arm}", "PLANE"),
        label="crank pin locked to the arm",
    )
    ring = await place_component(
        adapter,
        "crank-pin-ring",
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
    # Keeper-ring anchor screw + brass eyelet on the arm's front face (ch11
    # p.14); both lock to the arm so they turn with the crank.
    eye = await place_component(
        adapter,
        "crank-pin-eye",
        [ANCHOR_SCREW_XY[0], EYE_CENTER_Y, EYE_Z],
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
        "fillister-screw",
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
    # Handle pivot rides the arm tip, now ARM_C2C below the crankshaft. Its grip
    # axis stays parallel to the crankshaft (ROT_Y_POS90 -> assembly -Z).
    handle = await place_component(
        adapter,
        "crank-handle",
        [X_CRANK, Y_CRANK - ARM_C2C, CRANK_ARM_Z0],
        [0.0, 90.0, 0.0],
        ROT_Y_POS90,
        ground=False,
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
    # Keyed crank rig: the 16T pinion and the arm turn rigidly WITH the crankshaft;
    # the handle rides the arm's pivot pin. Each lock is replaced by a SEMANTIC
    # keyed joint -- coaxial + axial seat + an anti-spin -- so they share the
    # crankshaft's single spin DOF with no lock/fix. The suppressible crank ANGLE
    # DRIVER below pins that spin (via the arm). (The T12 chain wheel that used to
    # be keyed here now lives in paper-drive -- codex #189 :605.)
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

    # Crank arm (rest pose -Y, rot_z -90): its Top plane is parallel to the
    # crankshaft's Right at the keyed phase. The crank angle driver below pins the
    # arm -- hence the whole keyed chain -- to the assembly.
    # The arm's Ry(180)-composed pose turns its Front normal to machine -z
    # against SeatArm's +z: the seat holds at the as-built pose only
    # ANTI-aligned. Pin it explicitly rather than trust CLOSEST.
    arm_o = await _seat_on_crank(
        adapter,
        arm,
        "Axis1",
        crank_axis,
        crankshaft,
        "SeatArm",
        alignment="anti_aligned",
    )
    await parallel_mate(
        adapter,
        named_ref(f"Top Plane@{arm}", "PLANE"),
        cs_right,
        label="crank-arm anti-spin (keyed phase)",
        verify=(arm, arm_o),
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
        # Both normals read machine -z (Ry(180)-composed poses): pin the
        # alignment rather than trust CLOSEST (see the SeatArm note above).
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

    # Cone shaft revolute in the black pivot post: coincident + an axial plane
    # distance along the inclined axis (the shaft's local Z, read live). Its
    # spin is driven by the 16T -> 64T mesh, not pinned here.
    a_s = component_transform(adapter, cone_shaft)
    cone_o = [a_s[9] * 1000.0, a_s[10] * 1000.0, a_s[11] * 1000.0]
    cone_axis_dir = [a_s[6], a_s[7], a_s[8]]  # image of local Z = inclined shaft axis
    post_o = _org(adapter, pivot_post)
    # Ry180 reverses ConeShaftNormal's directed normal.  The physical plane and
    # undirected journal line are unchanged, but the signed distance side must
    # reverse to keep the shaft Front plane at the same decreasing station.
    d_axial = -sum((cone_o[k] - post_o[k]) * cone_axis_dir[k] for k in range(3))
    await coincident_mate(
        adapter,
        named_ref(f"Axis1@{cone_shaft}", "AXIS"),
        named_ref(f"journal axis@{pivot_post}", "AXIS"),
        label="cone-shaft radial",
        verify=(cone_shaft, cone_o),
    )
    await distance_driver(
        adapter,
        named_ref(f"Front Plane@{cone_shaft}", "PLANE"),
        named_ref(f"ConeShaftNormal@{pivot_post}", "PLANE"),
        d_axial,
        label=f"cone-shaft axial d={d_axial:.2f}",
        verify=(cone_shaft, cone_o),
    )
    # Tip block: aligned to the shaft/adjuster axis (which the post + platform
    # already carry) + an axial seat + a
    # parallel anti-spin against the PLATFORM (not the spinning shaft). Its
    # height falls out of the coaxial (bore height + plate = drive height,
    # asserted at import), so its foot lands ON PlateTop with no seat mate --
    # contact, not constraint. It follows the p1 swing through the shaft.
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
    # --- tip end-play stack (item 5): bushing | adjuster | pinch screw --------
    # The bushing spaces the T006 gear off the block's south face: coaxial on
    # the tip stub + an axial seat off the shaft. Free-spinning in reality; its
    # spin is pinned to the PLATFORM (immaterial, the lag-screw idiom) so the
    # 0-DOF closure proof stays exact. Its Top plane is the axial reference
    # (the part is authored along +Y).
    bush_o = _org(adapter, tip_bushing)
    bush_axial = sum((bush_o[k] - cone_o[k]) * cone_axis_dir[k] for k in range(3))
    await coincident_mate(
        adapter,
        named_ref(f"Axis1@{tip_bushing}", "AXIS"),
        named_ref(f"Axis1@{cone_shaft}", "AXIS"),
        label="tip-bushing on the tip stub",
        verify=(tip_bushing, bush_o),
    )
    await distance_driver(
        adapter,
        named_ref(f"Top Plane@{tip_bushing}", "PLANE"),
        named_ref(f"Front Plane@{cone_shaft}", "PLANE"),
        bush_axial,
        label=f"tip-bushing axial seat d={bush_axial:.2f}",
        verify=(tip_bushing, bush_o),
    )
    await parallel_mate(
        adapter,
        named_ref(f"Right Plane@{tip_bushing}", "PLANE"),
        named_ref(f"Right Plane@{platform}", "PLANE"),
        label="tip-bushing anti-spin (spin immaterial)",
        verify=(tip_bushing, bush_o),
    )
    # The adjuster screws into the BLOCK's tapped bore: coaxial on the block's
    # adjuster axis + an axial seat off the block's Front plane + an anti-spin
    # (the pinch screw locks its turn in reality).
    adj_o = _org(adapter, tip_adjuster)
    adj_axial = sum((adj_o[k] - tb_o[k]) * cone_axis_dir[k] for k in range(3))
    await coincident_mate(
        adapter,
        named_ref(f"Axis1@{tip_adjuster}", "AXIS"),
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
        named_ref(f"Axis1@{pinch_screw}", "AXIS"),
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
    # The 64T crank-drive gear and the 20 cone gears are one rigid stepped
    # cluster KEYED to the cone shaft -- each via coaxial + axial seat + parallel
    # anti-spin (see _key_to_shaft), replacing its lock with no fix/lock/tuned
    # angle. The 64T uses its Axis2 central axis, the cone gears their Axis1.
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
            cg = f"cone-gear-{j + 1}"
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
        # already sit on the seed's side. Every ReferencedConfiguration switch
        # above is now complete; regenerate all changed cone-gear child models
        # and solve the assembly once before the pose/status/mate-count scan.
        model = adapter.currentModel
        _force_rebuild_after_cone_replication(adapter, model)
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
            v / 1000.0 for v in cone_station(GEAR64_STATION + GEAR_AXIS_SHIFT)
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
        rows = mates_with_owners(adapter, {"cylinder-gear", "cylinder-gear-shaft"})
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
            new_name = f"cylinder-gear-{j + 1}"
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
    # The two straps + the pinion drum swing as ONE group on the torque shaft to
    # mesh the cylinder train (ch.25, p.66); parked DISENGAGED (p.68 "gap").
    # Statics first: the pivot blocks and torque shaft are base-bolted mounts at
    # their authored transforms -> locked once to the fixed seed arbor. The
    # lift rod is NOT static any more (PR8): it journals in the blocks' raised
    # west bores as a revolute below, carrying the cams + lever.
    for blk in pinion_blocks:
        await _lock_static(adapter, blk, arbor)
    await _lock_static(adapter, pivot_shaft, arbor)
    await _lock_static(adapter, spring, arbor)
    for scr in [block_screw, *foot_screws]:
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
        _FOOT_SCREW_XZ[2][0],
        Y_BASE_TOP + ARBOR_PED_FLANGE_T,
        _FOOT_SCREW_XZ[2][1],
    ]
    pedestal_instances = await linear_component_pattern(
        adapter,
        [foot_screws[1]],
        axis="z",
        spacing_mm=_FOOT_SCREW_XZ[2][1] - _FOOT_SCREW_XZ[1][1],
        instances=2,
        label="arbor pedestal foot-screw pattern",
    )
    assert_pattern_targets(
        adapter,
        pedestal_instances,
        [pedestal_target],
        IDENTITY,
        "arbor pedestal foot-screw pattern",
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
        90.0,
        label="lift rod spin PARK driver (cams parked ecc-down, a=90.00)",
        verify=(lift_rod, lr_o),
        free_dof_key="pinion_cam",
    )
    # Eccentric cams: pinned to the rod (set pin) -- coaxial on the rod's axis
    # + an axial seat + a parallel anti-spin to the rod (both at IDENTITY, so
    # their Right planes are parallel; the pair spins as one with the rod).
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
        await parallel_mate(
            adapter,
            named_ref(f"Right Plane@{cam}", "PLANE"),
            named_ref(f"Right Plane@{lift_rod}", "PLANE"),
            label=f"pinion cam {tag} set-pin anti-spin",
            verify=(cam, cam_o),
        )
    # Lever: clamped on the rod's front end -- coaxial + axial + an angle tie
    # to the ROD (not the frame) at the inserted 40-deg dihedral, so it spins
    # WITH the rod: dragging the lever in the saved free model turns the cams.
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
    await angle_driver(
        adapter,
        named_ref(f"Right Plane@{lever}", "PLANE"),
        named_ref(f"Right Plane@{lift_rod}", "PLANE"),
        abs(LEVER_TILT_DEG),
        label=f"lever clamp phase (a={abs(LEVER_TILT_DEG):.2f})",
        verify=(lever, lev_o),
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
    # under the z-parallel engage swing) + a parallel anti-spin to the drum
    # it is pressed into (both inserted at IDENTITY, so their Right planes
    # are parallel; riding the same swing group keeps the pair parallel).
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
    await parallel_mate(
        adapter,
        named_ref(f"Right Plane@{pinion_arbor}", "PLANE"),
        named_ref(f"Right Plane@{align_pinion}", "PLANE"),
        label="pinion arbor anti-spin (pressed in the drum)",
        verify=(pinion_arbor, arb_o),
    )
    # Tee handle: cross-pinned on the arbor front end (the zeroing crank), so
    # it is RIGID to the arbor -- a LOCK records the authored relative pose
    # with no branches and no DOF change, and the freed p2 swing carries the
    # handle with the rig instead of leaving it base-fixed in space.
    await lock_mate(
        adapter,
        named_ref(f"Front Plane@{tee_handle}", "PLANE"),
        named_ref(f"Front Plane@{pinion_arbor}", "PLANE"),
        label="tee handle cross-pinned on the arbor",
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
    assert_free_dof_necessity(
        adapter,
        4,
        required_stems=(
            "crankshaft",
            "cone-swing-platform",
            "pinion-bracket",
            "pinion-lift-rod",
        ),
    )
    write_dof_manifest(ASM_NAME)
    check_no_interference(
        adapter,
        allowed_pairs=allowed_interference_pairs(ASM_NAME),
    )
    # Title-block identity for the assembly drawing (draw_drive_train_assembly.py):
    # assembly_title_properties supplies the Title/Generator and TOL_* cells
    # finalize_drawing requires without consulting the part registry;
    # released component drawing (the BOM has no material/finish columns).
    apply_custom_properties(
        adapter,
        {
            **assembly_title_properties(ASM_NAME),
            # MHA-A## = assembly-drawing ids, beside the parts' MHA-### range
            # (a longer number overflows the DWG. NO. title-block cell).
            "Number": "MHA-A03",
            "Revision Description": "Initial release",
            "Material": "SEE COMPONENT DRAWINGS",
            "Material Specification": "SEE COMPONENT DRAWINGS",
            "Finish": "SEE COMPONENT DRAWINGS",
            "Quantity": "1",
            "Drawn By": DRAWN_BY,
        },
    )
    # The PART cell resolves the document summary Title; "drive-train assembly"
    # (not the bare stem) so the sheet identifies itself as an assembly drawing.
    apply_summary_info(adapter, title=f"{ASM_NAME} assembly")
    return await save_assembly_and_images(adapter, ASM_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
