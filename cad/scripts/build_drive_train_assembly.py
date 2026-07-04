r"""Reproduction script: drive-train subassembly (book ch. 11-13, 30).

The complete drive train in machine coordinates (assembly origin = base
origin; base top face at y = 50.8, drive height 54 above it -- ch30 GT
photogrammetry, 2026-07-02: the triangulated cone/arbor journals put the
drive plane at y 104.8, not the old 126.8):

* cone set: a TRUE CONE -- all 20 gears AND the 64T crank-drive gear
  seated perpendicular to the stepped shaft (p.18/p.20 photos), the
  shaft inclined in PLAN and carried at BOTH ends ON the cone swing
  platform (p.18: the wedge plate labelled "pivot" at its tip): big end
  journaled in the green pivot post, thin 1/32" tip in the black tip
  block (the GT tip post at world (-81, 105, +102), realized at station
  185). The plate pivots about a vertical axis at its TIP end, so the
  whole set swings horizontally out of mesh as one unit -- the p1
  disengage DOF; pivoting at the tip gives the big gears (which need
  the most working-depth separation) the largest throw.
* cylinder drum: 20 identical 120T gears spinning freely on the
  stationary arbor along Z at (-54.7, 104.8) (M6.2 keyway refutation),
  carried by the SOUTH arbor pedestal; the arbor's north end clears the
  now-solid rocker-arm-support, the north-end support deferred to the
  back-frame re-layout (the GT shows a real north bearing at z +91.5);
  notches up = cosine setup (pp. 66-67).
* crankshaft along Z in the merged green column (cone-pivot-post: big-end
  journal + crank pedestal, ONE casting riding the swing plate), ABOVE the
  64T (ch30 GT:
  the crank axle triangulates to y 144.8 -- a near-vertical 16T:64T mesh):
  crank arm + handle at the front, the T12 removable chain wheel (ch. 23:
  the bead chain rides the removable's m2 teeth -- swapping removables
  changes the platen ratio) and the 16T pinion inboard (the removable
  tapered pin is OMITTED: a tapered pin cannot sit in the straight
  5 mm cross-holes without solid interference).
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
rescaled to DP 26.57); the alignment pinion is RESTORED (ch30 GT) at the
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
cap 0.88. The 16T crank pinion mesh gets the same treatment, now on a
near-VERTICAL line of centres (the crank sits above the 64T, ch30 GT):
the perpendicular 64T presents its contact tooth r*cos(alpha)*sin(i)
north of its centre (alpha = the contact azimuth from the in-plane
horizontal; the old horizontal mesh is the alpha = 0 special case), the
pinion is centred on that plane, and Y_CRANK backs off so the oblique
dive across the 64T face caps clear of working depth (PEN16_EDGE_SLACK).

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
is left with exactly ONE operational DOF -- the crank angle.

Build mode (``machine/build_lock.yaml`` -> ``_config.machine("build_lock",
"drive_train")``; default ``free``):

* ``free`` (DEFAULT) -- the saved model is a WORKING kinematic model: the
  crank angle DOF is left UNLOCKED, so dragging the crank turns the whole
  geared train (1 DOF). A single ``PARK_crank_angle`` angle mate (the
  reproducibility "park driver") IS authored at the inserted rest pose but
  SUPPRESSED, so it pins nothing.
* ``locked`` -- an explicit opt-in pinned snapshot: the park driver stays
  ENGAGED, the crank angle is fixed, every component is fully defined
  (0 DOF), and the saved pose is byte-reproducible. This reproduces the
  historical grounding exactly.

The model is certified AS BUILT in whichever mode is configured:
``assert_expected_free_dof(adapter, 1 if free else 0)`` runs the park-driver
closure check (re-engage every ``PARK_*`` -> ForceRebuild -> assert 0
under-constrained -> re-suppress -> restore), proving exactly the expected
free DOF and nothing more; ``check_no_interference`` runs on the as-built
pose. Zero interferences (tangent/coincident contact allowed -- bores ride
their shafts). Gear-ratio sign is verified kinematically by a motion script.
The verify ``soundness`` suite re-runs this same DOF gate plus every other
gate on the as-built model; only the DOF gate adapts to the mode.

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
from _transforms import euler_from_rows
from _assembly import (
    angle_driver,
    apply_component_color,
    assert_expected_free_dof,
    assert_free_dof_necessity,
    check_no_interference,
    coincident_mate,
    component_transform,
    distance_driver,
    gear_mate,
    is_locked_build,
    mark_park_driver,
    named_ref,
    parallel_mate,
    place_component,
    save_assembly_and_images,
    seat_signed,
    set_park_defer,
    write_park_specs,
)

ASM_NAME = "drive-train"

# Build mode (cad/config/machine/build_lock.yaml). `free` (default) leaves the
# crank spin -- the single operational DOF -- UNLOCKED: its park driver is
# authored but suppressed, so the saved model is a working kinematic model.
# `locked` engages the park driver for a fully-defined reproducible snapshot.
# The literal accessor tokenises to machine/build_lock.yaml in the doit/cache
# digest, so flipping it rebuilds ONLY drive-train and keys the cache correctly.
# `is_locked_build` rejects any value other than `free`/`locked` (a typo'd opt-in
# must fail loud, not silently build free).
LOCK = is_locked_build(_config.machine("build_lock", "drive_train"))

Y_BASE_TOP = 50.8  # harmonic-base top face
Y_DRIVE = Y_BASE_TOP + 54.0  # 104.8: cone big-end and arbor axes (ch30 GT
# photogrammetry 2026-07-02: cone_back y 104.60 +- 1.1, cyl_back 105.24 +- 1.1,
# cone_front 101.25 +- 1.5 -- the old 76.0/126.8 sat the whole drive plane 22
# too high; the crank moved UP instead, see Y_CRANK)

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
X_DRUM = 54.7  # cam-drum machine X = -54.7 (ch30 GT bundle adjustment, cyl gear
# solved -52.3 +/- 0.9). The drum sits directly UNDER the rocker arms' rod-side
# tips: the rocker pivot (+72.9) is the seesaw mid-span, its rod-pin hole 127.37
# out, and every connecting rod hangs PLUMB from tip to cam (ch30 photos + GT
# rocker-corner triangulation; the earlier "line-2 photogrammetry" oblique-rod
# reading -- drum well clear of the support, LONG rods -- is refuted).
# The whole cone/64T/crank train cascades rigidly off this (DRUM_TIP_X -> X_PITCH ...).
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
DRUM_TIP_X = X_DRUM + (122.0 / DP_TRAIN) * 25.4 / 2.0  # 85.80 at DP 49.82
PEN_EDGE_SLACK = _config.fit("cone_drum_oblique_mesh", "edge_slack_mm")  # cad/config/tolerances.yaml
PEN_MID = WORKING_DEPTH - PEN_EDGE_SLACK - (DRUM_FACE / 2.0) * TAN_I  # 0.565
X_PITCH = DRUM_TIP_X + ADDENDUM * SEC_I - PEN_MID  # 85.76 at DP 49.82


def cone_seat(j: int) -> tuple[float, float]:
    """(x, z) centre of cone gear j: pitch-projected x, r*sin(i) north."""
    r = CONE_T120_PITCH_R - RADIUS_STEP * j
    return X_PITCH + r * COS_I, Z_DRUM0 + Z_PITCH * j + r * SIN_I


# Cone shaft: pivot end at seat station -28.25 from the T120 centre
# (25 journal + half of the first 6.5 face -- build_cone_gear_shaft.py).
# CONE_ORIGIN stays the PIVOT END (station 0, the station datum); the physical
# shaft now runs FRONT_STUB further south (ch30 GT), so the part -- authored
# from its front stub end -- is PLACED at SHAFT_FRONT_STATION instead.
SHAFT_T120_STATION = 25.0 + CONE_FACE / 2.0  # 28.25
CONE_ORIGIN = [
    cone_seat(0)[0] + SHAFT_T120_STATION * SIN_I,
    Y_DRIVE,
    cone_seat(0)[1] - SHAFT_T120_STATION * COS_I,
]
SHAFT_FRONT_STATION = -12.3  # -build_cone_gear_shaft FRONT_STUB (asserted
# below): the stub runs through the pivot post's journal, ending ~1.5 proud of
# the post's south flank (z -100.06). DOCUMENTED DEVIATION: the GT cone_front
# boss at z -123 belonged to the retired nested-pedestal story (stub through
# the pedestal's wall windows); the platform architecture ends the shaft at
# the post.


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
GEAR64_SEAT = cone_station(GEAR64_STATION)  # (117.44, , -68.62)
R64 = (64.0 / DP_CRANK) * 25.4 / 2.0  # 30.59: 64T pitch radius (== cone T120 by design)
R16 = (16.0 / DP_CRANK) * 25.4 / 2.0  # 7.65: 16T crank-pinion pitch radius

# Crank: ABOVE the 64T (ch30 GT photogrammetry -- the crank axle triangulates
# to world (-122.84, 144.78, -189.1) +- 1.4: the pedestal axis of the +122
# photo layout, ~40 ABOVE the drive plane, a near-VERTICAL 16T:64T mesh).
# X_CRANK is the photo-pinned pedestal axis; Y_CRANK closes the mesh at the
# same backed-off centre distance the old horizontal layout used. Slack 1.10
# is checker-arbitrated like the drum mesh's (the long oblique dive across
# the 64T face squeezes flanks: 0.15 left 1.48 mm^3, 0.60 left 0.23, 0.90 a
# 0.00 skin).
ADD16 = 25.4 / DP_CRANK  # crank-pinion addendum
WORK16 = 2.0 * ADD16  # 1.912 at DP 26.57
PEN16_EDGE_SLACK = 1.10
PEN16_MID = WORK16 - PEN16_EDGE_SLACK - (GEAR64_FACE / 2.0) * SIN_I  # -0.272
MESH16_C2C = R64 + R16 + (ADD16 * (1.0 + SEC_I) - PEN16_MID)  # 40.446 backed off
X_CRANK = 122.8  # crank/pedestal axis (GT -122.84 +- 0.9; ratifies the +122
# pedestal photo the DP-26.57 rescale had displaced -- both hold: the crank is
# above the gear, not outboard of it)
Y_CRANK = 144.96  # = Y_DRIVE + sqrt(MESH16_C2C^2 - dx^2) with dx the in-plane
# horizontal offset (GT 144.78 +- 1.4, 0.13 sigma); a literal so the pedestal
# part's BORE_HEIGHT (94.16 above the base top) stays a round number -- both
# self-checked below.
_DX16 = (X_CRANK - GEAR64_SEAT[0]) * COS_I  # 4.82: horizontal leg, 64T plane
_DY16 = Y_CRANK - Y_DRIVE  # 40.16: vertical leg (in BOTH gear planes)
if abs(math.hypot(_DX16, _DY16) - MESH16_C2C) > 0.05:
    raise AssertionError("crank mesh centre distance drifted off the backoff")
if abs(Y_CRANK - (Y_BASE_TOP + 94.16)) > 0.001:
    raise AssertionError("Y_CRANK must equal the pedestal bore height 94.16")
# Contact azimuths (from each gear's centre toward the other axis, in that
# gear's own plane, ccw from the in-plane horizontal). The 64T plane rides
# the inclined cone shaft; the 16T plane is a plain machine-Z section.
ALPHA64 = math.degrees(math.atan2(_DY16, _DX16))  # 83.15
ALPHA16 = math.degrees(math.atan2(_DY16, X_CRANK - GEAR64_SEAT[0]))  # 82.98
# The 64T's contact tooth sits R64*cos(alpha)*sin(i) north of its centre (the
# in-plane horizontal carries the plane's only z-component; alpha = 0 reduces
# to the old horizontal-mesh R64*sin(i)). The 16T is centred on that plane.
PINION_TOOTH_Z = GEAR64_SEAT[2] + R64 * math.cos(math.radians(ALPHA64)) * SIN_I  # -67.83
# Tooth-in-gap phase seed, generalizing the old +11.25 half-pitch: the 64T is
# keyed at its authored phase (a tooth centred at azimuth 0), so its nearest
# tooth leads the contact azimuth by DELTA64; the pinion's gap must sit that
# same contact arc (scaled by R64/R16) past the contact on ITS side. At
# ALPHA = 0 this is exactly 11.25.
_TP64 = 360.0 / 64.0
DELTA64 = round(ALPHA64 / _TP64) * _TP64 - ALPHA64  # 1.22: 64T tooth lead
PINION_SEED_DEG = (
    (ALPHA16 + 180.0) - DELTA64 * (R64 / R16) - 22.5 / 2.0
) % 22.5  # 21.8: tooth-in-gap at the tilted line of centres

ARBOR_SOUTH_Z = -90.0  # arbor south end (ch30 GT cyl_front z -89.66 +- 2.7: the
# end stops INSIDE the arbor-pedestal bore, blind-bearing look; was -98, poking
# 8 clear through the block). = cylinder-gear-shaft origin, placed by its south
# end.
ARBOR_LENGTH = 168.0  # north end stays at z +78, clearing the solid portal
# north upright frustum and still covering the drum stack (north end z +70.6).
# Must match cylinder-gear-shaft SHAFT_LENGTH. GT NOTE (2026-07-02): the photos
# show the real arbor running on to a NORTH bearing + a large helical end gear
# at z ~ +91.5 (GT cyl_back) -- inside the model's portal frustum envelope.
# Extending the arbor + adding the north pedestal stays DEFERRED to the
# portal/back-frame re-layout (the GT top-frame and column positions moved
# too); coordinates are on file in dimensions.yaml.
CRANKSHAFT_Z0 = -175.0  # outboard (crank) end (was -160: the crank plane moved
# south with the ch30 GT re-read -- arm hub -175..-167, GT axle bolt -189 +- 2.7)
CRANKSHAFT_LENGTH = 145.0  # build_crankshaft.py SHAFT_LENGTH (-175..-30)
CRANK_ARM_Z0 = CRANKSHAFT_Z0  # arm hub at the shaft's south end (-175..-167), in
# FRONT of (south of) the T12 chain wheel (-157.5..-152.5): the arm + the handle
# (its grip extends -Z, further south) then sweep entirely south of the chain
# plane (-155) and cannot foul the chain when the crank turns (user, book p005).
ARM_C2C = 66.0  # handle pivot from the shaft axis (rederived from the ch30
# eight-views, see build_crank_arm.py; was 150 -- a down-pointing 150 arm put
# the handle below the table)
REMOVABLE_Z0 = -157.5  # mounted T12 (face 5.0): band -157.5..-152.5, mid -155 =
# the front chain plane (ch30 GT: solved-camera z-ticks bracket the physical
# chain run at -153 +- 3), between the merged crank column (south flank -98.6,
# even at the disengaged swing) and the crank arm (-175..-167). The plane
# clears the paper-drive stub disc
# (-134.5..-137.5) by 15; the arm sits 9.5 SOUTH of the wheel so the rotating
# arm/handle never crosses it. The small removable gear is the chain wheel
# (ch. 23 -- bead chain on its m2 teeth; v2_gears_010).
ARBOR_PEDESTAL_Z = 90.5  # SOUTH end only (at z -90.5): the rocker support no
# longer clamps the arbor, but the solid portal north upright leaves no room for
# a north pedestal where the arbor's north end was (GT NOTE above). South foot
# flange front face -98.5 clears the portal south-plate back face -99 by 0.5
# (the tapered strap above the foot is thinner, z -95.5..-85.5).

# The pinion must sit fully on the crankshaft.
if PINION_TOOTH_Z + PINION_FACE / 2.0 > CRANKSHAFT_Z0 + CRANKSHAFT_LENGTH:
    raise AssertionError("crankshaft too short for the M6.7 pinion station")

# The whole cone set rides the SWING PLATFORM (ch.12 p.18: the dark wedge
# plate labelled "pivot" at its tip end). The green pivot post (big-end
# journal) and the black tip block (1/32" tip journal) stand ON the plate;
# the plate pivots about a vertical axis at cone station PIVOT_STATION, just
# north of the shaft's rear end, so on disengage the BIG end -- where the
# gears need the most working-depth separation -- swings the farthest
# (throw ~ distance from pivot).
POST_STATION = 1.5  # pivot post plan centre: south flank z -98.59, 1.1 air
# to the 64T south face (-73.5) at the NORTH flank (-74.59)
TIP_BLOCK_STATION = 185.0  # tip block plan centre; the shaft's tip end
# (station 190) journals INSIDE its bore -- the GT tip post (-81, 104.6, +102)
PIVOT_STATION = 196.0  # platform swing pivot (plan), north of the shaft end

# --- platform <-> riders fit (SolidWorks-free, import-time) ------------------
# The platform/post/block parts hardcode their envelopes in THEIR part frames;
# they must agree with the live cone-shaft line placed here. Imported, not
# copied (the CAM_ECC precedent), and asserted at import so a drifted anchor
# fails before any COM work.
from build_cone_swing_platform import (  # noqa: E402
    CRANK_AXIS_OFF as PLAT_CRANK_OFF,
    CRANK_AXIS_Y as PLAT_CRANK_Y,
    EAST_HALF_S as PLAT_EAST_S,
    HALF_WIDTH_N as PLAT_HALF_N,
    NORTH_OVERHANG as PLAT_OVERHANG,
    CRANK_SEAT_ANCHOR as PLAT_SEAT_ANCHOR,
    NOTCH_EXIT_TRAVEL as PLAT_NOTCH_EXIT,
    PLATE_LEN as PLAT_LEN,
    PLATE_T as PLAT_T,
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
    SHANK_DIA as PSCREW_SHANK_DIA,
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
    PIVOT_SCREW_XZ as BASE_PIVOT_XZ,
    STOP_SCREW_HOLE_DIA as BASE_STOP_HOLE_DIA,
    STOP_SCREW_XZ as BASE_STOP_XZ,
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
from build_pinion_bracket import (  # noqa: E402
    ARBOR_BORE as STRAP_ARBOR_BORE,
    PIVOT_BORE as STRAP_PIVOT_BORE,
)
from build_pinion_pivot_block import (  # noqa: E402
    BORE_UP as BLOCK_BORE_UP,
    DEPTH as BLOCK_DEPTH,
    HEIGHT as BLOCK_HEIGHT,
    SCREW_HALF_SPACING as BLOCK_SCREW_HALF,
    SCREW_HOLE_DIA as BLOCK_SCREW_HOLE_DIA,
    WIDTH as BLOCK_WIDTH,
)
from build_pinion_lift_rod import (  # noqa: E402
    PIN_STATIONS as ROD_PIN_STATIONS,
    PIN_TIP as ROD_PIN_TIP,
)
from build_pinion_lever import (  # noqa: E402
    CAP_SAG as LEVER_CAP_SAG,
    HUB_LEN as LEVER_HUB_LEN,
    ROD_LEN as LEVER_ROD_LEN,
    ROD_ROOT_DIA as LEVER_ROD_DIA,
    WALL_T as LEVER_WALL_T,
)
from build_pinion_handle import (  # noqa: E402
    GRIP_DIA as HANDLE_GRIP_DIA,
    GRIP_LEN as HANDLE_GRIP_LEN,
    CAP_SAG as HANDLE_CAP_SAG,
    ROD_DOWN as HANDLE_ARM_DOWN,
    ROD_UP as HANDLE_ARM_UP,
    TUBE_ID as HANDLE_TUBE_ID,
    TUBE_LEN as HANDLE_TUBE_LEN,
    WALL_T as HANDLE_WALL_T,
)
from build_pinion_spring import (  # noqa: E402
    AXIS_OFFSET as SPRING_AXIS_OFF,
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
    CRANK_BORE_DX as POST_CRANK_DX,
    CRANK_BORE_Y as POST_CRANK_Y,
)
from build_cone_tip_block import (  # noqa: E402
    ADJUSTER_BORE_DEPTH as TIP_ADJ_BORE_DEPTH,
    BLOCK_X as TIP_BLOCK_X,
    BLOCK_Z as TIP_BLOCK_Z,
    BORE_HEIGHT as TIP_BORE_HEIGHT,
    PINCH_BORE_DIA as TIP_PINCH_BORE_DIA,
    PINCH_BORE_Y as TIP_PINCH_Y,
)
from build_cone_tip_bushing import (  # noqa: E402
    BORE_DIA as BUSH_BORE_DIA,
    LENGTH as BUSH_LEN,
)
from build_cone_tip_adjuster import (  # noqa: E402
    BODY_LEN as ADJ_LEN,
    CUP_DEPTH as ADJ_CUP_DEPTH,
    CUP_DIA as ADJ_CUP_DIA,
)
from build_cone_tip_pinch_screw import (  # noqa: E402
    SHANK_DIA as PINCH_SHANK_DIA,
    SHANK_LEN as PINCH_SHANK_LEN,
)
from build_cone_gear_shaft import (  # noqa: E402
    FRONT_STUB as SHAFT_FRONT_STUB,
    SECTIONS as SHAFT_SECTIONS,
)
# One journal drive height across the platform and both riders: plate
# thickness under each foot + bore height = 54 above the base top.
if (abs((Y_DRIVE - Y_BASE_TOP) - (PLAT_T + POST_BORE_HEIGHT)) > 1e-9
        or abs((Y_DRIVE - Y_BASE_TOP) - (PLAT_T + TIP_BORE_HEIGHT)) > 1e-9):
    raise AssertionError("cone journal height drifted between platform/post/block")
# The shaft is placed by its front stub end; keep the station in lockstep with
# the part's FRONT_STUB.
if abs(SHAFT_FRONT_STATION + SHAFT_FRONT_STUB) > 1e-9:
    raise AssertionError("SHAFT_FRONT_STATION out of sync with the shaft FRONT_STUB")


def _plat_half_width(s: float) -> float:
    """Platform MIN half-width at cone station s (the asymmetric plate's
    narrower side -- east; the west flare is always wider); negative if s is
    off the plate. Riders are centred on the shaft plan line (local x 0), so
    the narrow side bounds their containment."""
    z_local = s - PIVOT_STATION  # platform local z (+ along increasing station)
    if not (PLAT_OVERHANG - PLAT_LEN - 1e-9 <= z_local <= PLAT_OVERHANG + 1e-9):
        return -1.0
    return PLAT_HALF_N + (PLAT_EAST_S - PLAT_HALF_N) * (PLAT_OVERHANG - z_local) / PLAT_LEN


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
                f"{_lbl} overhangs the swing platform at station {_end:g}")
# The shaft's tip end journals INSIDE the tip block (>= 5 engaged, end short
# of the north face).
_TIP_END_STATION = SHAFT_FRONT_STATION + SHAFT_SECTIONS[-1][1]  # 190.0
if not (TIP_BLOCK_STATION - TIP_BLOCK_Z / 2.0 + 5.0
        <= _TIP_END_STATION
        <= TIP_BLOCK_STATION + TIP_BLOCK_Z / 2.0 - 0.5):
    raise AssertionError("shaft tip end does not journal inside the tip block")
# The stub end stands proud of the post's south flank (nothing hides it).
_STUB_END_Z = cone_station(SHAFT_FRONT_STATION)[2]  # -100.06
_POST_SOUTH_Z = cone_station(POST_STATION)[2] - POST_BLOCK_DIA / 2.0  # -98.59
if _STUB_END_Z > _POST_SOUTH_Z - 1.0:
    raise AssertionError(
        f"cone-shaft stub end {_STUB_END_Z:.2f} not proud of the post's south "
        f"flank {_POST_SOUTH_Z:.2f}")
# --- tip end-play stack (item 5, v4_t00471 / 7:49) ---------------------------
# Along the axis, south to north: T006 gear | brass bushing (spacer) | block
# south face | 1/32" journal | adjuster screw in the counterbore, its blind cup
# holding the shaft's tip end; the block's top slit + pinch screw lock it.
TIP_SOUTH_STATION = TIP_BLOCK_STATION - TIP_BLOCK_Z / 2.0  # 179: block south face
BUSH_STATION = TIP_SOUTH_STATION - BUSH_LEN  # 175: bushing south end
ADJ_EMBED = 6.0  # adjuster thread engagement into the counterbore (8 deep)
ADJ_HEAD_STATION = TIP_BLOCK_STATION + TIP_BLOCK_Z / 2.0 + (ADJ_LEN - ADJ_EMBED)  # 199
_ADJ_MOUTH = ADJ_HEAD_STATION - ADJ_LEN  # 185: the blind cup's mouth
_STUB_DIA = SHAFT_SECTIONS[-1][0] * 25.4  # 0.794: the 1/32" tip stub
_STUB_START = SHAFT_FRONT_STATION + SHAFT_SECTIONS[-2][1]  # 155.7
if BUSH_STATION < _STUB_START + 1.0:
    raise AssertionError("tip bushing rides off the 1/32in stub section")
if abs(BUSH_BORE_DIA - _STUB_DIA) > 0.05:
    raise AssertionError("tip-bushing bore does not match the tip stub dia")
if ADJ_EMBED > TIP_ADJ_BORE_DEPTH - 0.5:
    raise AssertionError("adjuster bottoms out in the block counterbore")
if not (_ADJ_MOUTH + 0.5 <= _TIP_END_STATION <= _ADJ_MOUTH + ADJ_CUP_DEPTH - 0.5):
    raise AssertionError("shaft tip end does not rest inside the adjuster cup")
if ADJ_CUP_DIA < _STUB_DIA + 0.25:
    raise AssertionError("adjuster cup too tight around the tip stub")
if abs(PINCH_SHANK_DIA - TIP_PINCH_BORE_DIA) > 0.05:
    raise AssertionError("pinch-screw shank does not match the block cross-bore")
if PINCH_SHANK_LEN < TIP_BLOCK_X / 2.0 + 0.5:
    raise AssertionError("pinch screw too short to cross the top slit")
# The crank pedestal is GONE as a separate base-mounted part: the cone pivot
# post and the crank pedestal are ONE green column riding the swing platform
# (user-confirmed vs v4_t00411/t00417), so the crank rig swings with the cone
# set and the 16T<->64T mesh survives the disengage. Cross-script agreement
# for the merged column's crank bore and the platform's "crank axis":
_PPIVOT = cone_station(PIVOT_STATION)
_PPOST = cone_station(POST_STATION)
if abs(PLAT_CRANK_OFF - (X_CRANK - _PPIVOT[0])) > 0.05:
    raise AssertionError(
        f"platform CRANK_AXIS_OFF {PLAT_CRANK_OFF} != X_CRANK - pivot.x "
        f"{X_CRANK - _PPIVOT[0]:.3f}")
if abs(PLAT_CRANK_Y - (Y_CRANK - Y_BASE_TOP)) > 1e-6:
    raise AssertionError("platform CRANK_AXIS_Y != Y_CRANK - Y_BASE_TOP")
if abs(POST_CRANK_DX - (X_CRANK - _PPOST[0])) > 0.05:
    raise AssertionError(
        f"column CRANK_BORE_DX {POST_CRANK_DX} != X_CRANK - post.x "
        f"{X_CRANK - _PPOST[0]:.3f}")
if abs(POST_CRANK_Y - (Y_CRANK - Y_BASE_TOP - PLAT_T)) > 1e-6:
    raise AssertionError("column CRANK_BORE_Y != Y_CRANK - Y_BASE_TOP - PLAT_T")
# The base's pivot-screw hole sits exactly under the swing pivot. The base
# is MACHINE-handed (frame.SLDASM places it unmirrored) while this module
# derives in the PRE-MIRROR frame, so the hole's x is the NEGATED pivot x
# (the top-level interference gate proved raw +x wrong: both screws landed
# in solid base, exactly their embedded shank volumes).
if (abs(BASE_PIVOT_XZ[0] + _PPIVOT[0]) > 0.05
        or abs(BASE_PIVOT_XZ[1] - _PPIVOT[2]) > 0.05):
    raise AssertionError(
        f"harmonic-base pivot-screw hole {BASE_PIVOT_XZ} != machine swing pivot "
        f"({-_PPIVOT[0]:.3f}, {_PPIVOT[2]:.3f})")
if BASE_PIVOT_HOLE_DIA < PSCREW_SHANK_DIA:
    raise AssertionError("base pivot hole under the pivot-screw shoulder dia")
# The pivot-screw head sits on the plate top at station PIVOT_STATION; the
# tip block (also on the plate) ends at station 191 -- the head radius must
# clear its north face (the first O12 head clipped the corner 13.5 mm^3).
if PSCREW_HEAD_DIA / 2.0 > (
        PIVOT_STATION - (TIP_BLOCK_STATION + TIP_BLOCK_Z / 2.0)) - 0.25:
    raise AssertionError("pivot-screw head reaches the tip block's north face")


# --- cone lock knob (v4_t00411; clamps the swing plate through its notch) ----
# The knob is a base-bolted STATIC (pedestal pattern: located to the machine
# datums); the plate's open lock notch sweeps around its stationary stud and,
# past the mouth, clear of it (t00417: the bolt stands past the plate edge
# when disengaged). Its machine position is DERIVED from the platform's
# engaged notch-seat in the plate's local frame, so the two scripts cannot
# drift apart.
def _plate_local_to_machine(x_l: float, z_l: float) -> tuple[float, float]:
    """Plan point of the ENGAGED plate's local (x, z) in machine coords."""
    return (
        _PPIVOT[0] + x_l * COS_I - z_l * SIN_I,
        _PPIVOT[2] + x_l * SIN_I + z_l * COS_I,
    )


# The platform is AUTHORED MIRRORED (MIRROR_PLANE "x0" -- the lock lobe made
# it chiral), so its exported local-x constants NEGATE into this pre-mirror
# frame; z is untouched.
KNOB_X, KNOB_Z = _plate_local_to_machine(-PLAT_SLOT_E_X, PLAT_SLOT_E_Z)  # 96.98,
# -87.60: the video's gap between the pivot post and the arbor pedestal
if PLAT_SLOT_W - KNOB_STUD_DIA < 0.5:
    raise AssertionError("lock stud has <0.5 clearance in the platform notch")
# The plate's crank-anchor point (CrankAxisSeat's anchor, on the plate's
# "crank axis") must land ON the machine crank axis at the engaged pose --
# the SolidWorks-free proof of the platform's CRANK_SEAT_ANCHOR signs.
_SEAT_ANCHOR_M = _plate_local_to_machine(-PLAT_SEAT_ANCHOR[0], PLAT_SEAT_ANCHOR[1])
if abs(_SEAT_ANCHOR_M[0] - X_CRANK) > 0.05:
    raise AssertionError(
        f"platform CRANK_SEAT_ANCHOR maps to machine x {_SEAT_ANCHOR_M[0]:.3f}"
        f" != X_CRANK {X_CRANK} -- anchor sign convention broke")

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
# The DISENGAGE swing is + (the notch region sweeps machine EAST -- the same
# sense that walks the knob stud out the notch mouth), so the plate VACATES
# its west side and it is the EAST taper edge that advances onto a base
# screw. Contact point taken on the east edge at plate-local z -105 (mid
# plate, on the base with margin); the screw centre sits one shank radius
# outside the swung edge. The base part hardcodes the hole (CAM_ECC
# pattern) -- assert agreement, and that the ENGAGED pose clears it on the
# CORRECT side (signed, not |distance|: the first cut of this derivation
# used the west edge + an abs() gap and buried the screw 19 mm INSIDE the
# engaged plate -- caught by the interference gate).
_K_E = (PLAT_EAST_S - PLAT_HALF_N) / PLAT_LEN
_STOP_ZL = -105.0
_STOP_PL = (PLAT_HALF_N + _K_E * (PLAT_OVERHANG - _STOP_ZL), _STOP_ZL)
_EDGE_OUT = (1.0, _K_E)  # outward (east) normal, plate frame
_EDGE_N = math.hypot(*_EDGE_OUT)
_EDGE_OUT = (_EDGE_OUT[0] / _EDGE_N, _EDGE_OUT[1] / _EDGE_N)


def _swung_to_machine(x_l: float, z_l: float, ang: float) -> tuple[float, float]:
    c, s = math.cos(ang), math.sin(ang)
    return (_PPIVOT[0] + x_l * c - z_l * s, _PPIVOT[2] + x_l * s + z_l * c)


_A_DIS = math.radians(INCLINE_DEG) + _DISENGAGE_RAD
_CONTACT = _swung_to_machine(_STOP_PL[0], _STOP_PL[1], _A_DIS)
_N_M = (_EDGE_OUT[0] * math.cos(_A_DIS) - _EDGE_OUT[1] * math.sin(_A_DIS),
        _EDGE_OUT[0] * math.sin(_A_DIS) + _EDGE_OUT[1] * math.cos(_A_DIS))
STOP_X = _CONTACT[0] + _N_M[0] * STOP_SHANK_DIA / 2.0
STOP_Z = _CONTACT[1] + _N_M[1] * STOP_SHANK_DIA / 2.0
# Machine-handed base part vs this pre-mirror derivation: x negates (see the
# pivot-hole assert above).
if abs(BASE_STOP_XZ[0] + STOP_X) > 0.05 or abs(BASE_STOP_XZ[1] - STOP_Z) > 0.05:
    raise AssertionError(
        f"harmonic-base stop-screw hole {BASE_STOP_XZ} != machine derived stop "
        f"({-STOP_X:.3f}, {STOP_Z:.3f})")
if BASE_STOP_HOLE_DIA < STOP_SHANK_DIA:
    raise AssertionError("base stop hole under the stop-screw shank dia")
# Engaged pose clears the stop screw on the OUTSIDE (signed distance along
# the engaged east edge's outward normal, minus the shank radius).
_EP = _swung_to_machine(_STOP_PL[0], _STOP_PL[1], math.radians(INCLINE_DEG))
_N_ENG = (_EDGE_OUT[0] * COS_I - _EDGE_OUT[1] * SIN_I,
          _EDGE_OUT[0] * SIN_I + _EDGE_OUT[1] * COS_I)
_W = (STOP_X - _EP[0], STOP_Z - _EP[1])
_STOP_ENGAGED_GAP = (_W[0] * _N_ENG[0] + _W[1] * _N_ENG[1]) - STOP_SHANK_DIA / 2.0
if _STOP_ENGAGED_GAP < 2.0:
    raise AssertionError(
        f"stop screw within {_STOP_ENGAGED_GAP:.2f} of the ENGAGED plate edge "
        f"(needs >= 2.0, signed: negative = inside the plate)")
# ... and it must stand clear of the OTHER swing hardware and on the base.
if math.hypot(STOP_X - KNOB_X, STOP_Z - KNOB_Z) < (
        KNOB_WASHER_DIA + STOP_SHANK_DIA) / 2.0 + 0.25:
    raise AssertionError("stop screw fouls the lock-knob washer")
_POST_LOCAL_Z = POST_STATION - PIVOT_STATION  # -194.5
_WASHER_POST_GAP = (
    math.hypot(PLAT_SLOT_E_X, PLAT_SLOT_E_Z - _POST_LOCAL_Z)
    - KNOB_WASHER_DIA / 2.0 - POST_BLOCK_DIA / 2.0
)
if _WASHER_POST_GAP < 2.0:
    raise AssertionError(
        f"lock knob washer within {_WASHER_POST_GAP:.2f} of the pivot post "
        f"foot (needs >= 2.0)")
# Plate WEST edge (the flare) vs the arbor-pedestal block: sample the edge
# along its run and check each machine point against the block's east flank
# band (the old lobe-corner check generalised to the flared edge).
_K_W = (PLAT_WEST_S - PLAT_HALF_N) / PLAT_LEN
_ARB_E_X = X_DRUM + ARBOR_PED_WIDTH / 2.0  # 66.7
_ARB_Z = (-ARBOR_PEDESTAL_Z - ARBOR_PED_DEPTH / 2.0,
          -ARBOR_PEDESTAL_Z + ARBOR_PED_DEPTH / 2.0)  # -98.5..-82.5
for _step in range(0, 43):
    _zl = PLAT_OVERHANG - PLAT_LEN + 5.0 * _step  # south edge -> north
    _xw = PLAT_HALF_N + _K_W * (PLAT_OVERHANG - _zl)  # authored west x
    _cx, _cz = _plate_local_to_machine(-_xw, _zl)
    _gap = _cx - _ARB_E_X if _ARB_Z[0] - 2.0 <= _cz <= _ARB_Z[1] + 2.0 \
        else math.hypot(max(0.0, _ARB_E_X - _cx),
                        min(abs(_cz - _ARB_Z[0]), abs(_cz - _ARB_Z[1])))
    if _gap < 2.0:
        raise AssertionError(
            f"swing-plate west edge (z_l {_zl:.0f}) within {_gap:.2f} of "
            f"the arbor-pedestal block (needs >= 2.0)")

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
APINION_X = X_DRUM - (TIP_DRUM120 + TIP_APINION + APINION_GAP)  # 10.38: INBOARD,
# tip circles backed off to the parked gap at Delta-y = 0 (axis dead level)
APINION_Y = Y_DRIVE
APINION_DRUM_LEN = 143.2  # build_alignment_pinion FACE_WIDTH
APINION_Z_FRONT = -75.0  # drum front end face (station coverage asserted below)
APINION_Z_BACK = APINION_Z_FRONT + APINION_DRUM_LEN  # +68.2
PIVOT_Y = Y_BASE_TOP + 12.0  # 62.8: pivot block bore height
STRAP_T = 5.0  # build_pinion_bracket THICKNESS
STRAP_R_END = 9.0  # build_pinion_bracket WIDTH / 2 (must match): end-cap radius
STRAP_C2C = 43.0  # build_pinion_bracket C2C (was 31: the drive axis now sits
# 42.0 above the pivot bore, so the strap grew with the level-pinion layout)
STRAP_AIR = 0.25  # axial air each side of each strap
PIVOT_X = APINION_X - math.sqrt(
    STRAP_C2C**2 - (APINION_Y - PIVOT_Y) ** 2
)  # 1.16: on the DRUM side (west) of the pinion, so swinging the strap toward
# vertical advances the pinion into mesh
STRAP_LEAN_DEG = math.degrees(
    math.atan2(PIVOT_X - APINION_X, APINION_Y - PIVOT_Y)
)  # -12.38: strap leans west of vertical
LIFT_X = PIVOT_X - 15.0  # lift rod in the blocks' WEST bores (PR5). It sat
# east (+15) since the DP40 cram (issue #7 dodged the cone-pivot-post column);
# the p.68-69 photos put the lever WEST of the tee handle and the cam pins
# lifting the strap tails' follower pins from the WEST -- an east lift would
# swing the drum OUT of mesh. The column (x ~47) is far east of the new spot,
# and the M6.9 portal south upright that once blocked the west band was
# replaced by the lone NORTH rocker-arm-support (x 41..105) -- nothing lives
# at x -21..-7 in the rod's z run (cam asserts below re-prove the neighbours).
PIVOT_SHAFT_Z0 = -104.0  # Ø6.35 x 192 (PR7 item 13): both crowned ends
# FLUSH with the block outer faces (-104 / +88)
LIFT_ROD_Z0 = -114.0  # Ø6.35 x 202 (PR7 item 13): back end flush at +88,
# front end proud 10 south of the front block -- exactly the lever hub
BLOCK_X = (PIVOT_X + LIFT_X) / 2.0  # block local origin midway the bores
BLOCK_FRONT_Z0 = -104.0
BLOCK_BACK_Z0 = 76.0
LEVER_TILT_DEG = 40.0  # from vertical, leaning east (p.68). The p002-fitted
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
LEVER_Z = -111.0  # hub centre: the clamp hub's blind bore floor (local
# z -3) seats on the lift rod's front end at -114; the hub's north face
# (-106) stands 2 off the front block (item 13)
HANDLE_TILT_DEG = 65.0  # cross rod from vertical
HANDLE_Z = -144.0  # tee-handle CROSS-ROD plane (part origin; GT
# pinion_front z -144.07 +- 2.7). The hub is now a blind tubular cap
# (PR7 item 14): its bore floor at local +9 lands on -135, where the
# steel arbor's flat front tip seats flush (build_pinion_arbor)

if abs(math.hypot(PIVOT_X - APINION_X, APINION_Y - PIVOT_Y) - STRAP_C2C) > 0.001:
    raise AssertionError("strap c2c does not span pivot -> pinion axis")
if Z_DRUM0 - DRUM_FACE / 2.0 < APINION_Z_FRONT + 1.0:
    raise AssertionError("alignment pinion too short at the front station")
if Z_DRUM0 + 19 * Z_PITCH + DRUM_FACE / 2.0 > APINION_Z_BACK + 0.5:
    raise AssertionError("alignment pinion misses the j = 19 station")
if math.hypot(APINION_X - X_DRUM, Y_DRIVE - APINION_Y) < TIP_DRUM120 + TIP_APINION + 1.0:
    raise AssertionError("alignment pinion crowds the cylinder train")
if math.hypot(PIVOT_X - X_DRUM, Y_DRIVE - PIVOT_Y) > ENGAGED_C2C + STRAP_C2C - 0.25:
    raise AssertionError("engage swing cannot reach the meshed centre distance")
for _j in range(20):
    _tip = CONE_T120_PITCH_R - RADIUS_STEP * _j + ADDENDUM
    if (math.hypot(APINION_X - cone_seat(_j)[0], Y_DRIVE - APINION_Y)
            < _tip + TIP_APINION + 0.25):
        raise AssertionError(f"pinion drum crowds cone gear {_j}")
if (math.hypot(APINION_X - GEAR64_SEAT[0], Y_DRIVE - APINION_Y)
        < R64 + ADD16 + TIP_APINION + 0.25):
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
_LEV_U = (math.sin(_LEV_T), math.cos(_LEV_T))  # up the rod, east lean
_LEV_REL = (APINION_X - LIFT_X, APINION_Y - PIVOT_Y)  # root -> arbor axis
_LEV_FOOT = _LEV_REL[0] * _LEV_U[0] + _LEV_REL[1] * _LEV_U[1]
if 0.0 <= _LEV_FOOT <= LEVER_LEN:
    _LEV_STUB_D = abs(_LEV_REL[0] * _LEV_U[1] - _LEV_REL[1] * _LEV_U[0])
else:
    _end = min(max(_LEV_FOOT, 0.0), LEVER_LEN)
    _LEV_STUB_D = math.hypot(_LEV_REL[0] - _end * _LEV_U[0],
                             _LEV_REL[1] - _end * _LEV_U[1])
if _LEV_STUB_D < (ARBOR_DIA + LEVER_ROD_DIA) / 2.0 + 0.25:
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
# Geometry is IMPORTED from build_pinion_spring (machine = part local +
# (SPRING_X, Y_BASE_TOP)). The thin wall is ONE-sided; the part's 1%-tol
# volume gate pins the probed side (right-of-travel: under the foot, EAST
# of the blade/flat centreline), but every clearance that can afford it
# still books the full 0.8 on whichever side hurts. The flat-tip-vs-cap
# check below is the one exception -- it relies on the gated east side.
SPRING_X = 9.04  # part-frame anchor (pre-mirror, like every constant here);
# the chirality mirror needs the part's ("z", 0.0) MIRROR_PLANE entry.
SPRING_Z = APINION_Z_BACK + STRAP_AIR + STRAP_T / 2.0  # 70.95: back-strap mid
_SPR_TH = math.radians(-STRAP_LEAN_DEG)  # blade leans east of vertical
_SPR_U = (math.sin(_SPR_TH), math.cos(_SPR_TH))  # up the blade
_SPR_N = (math.cos(_SPR_TH), -math.sin(_SPR_TH))  # east normal of the axis
_SPR_PIVOT = (SPRING_X + SPR_PIVOT_LX, Y_BASE_TOP + SPR_PIVOT_LY)
SPRING_CREST = (SPRING_X + SPR_CREST_L[0], Y_BASE_TOP + SPR_CREST_L[1])
# the parked contact edge (kink start, tangent parallel to the strap axis)
SPRING_FLAT_TIP = (SPRING_X + SPR_FLAT_TIP_L[0], Y_BASE_TOP + SPR_FLAT_TIP_L[1])
SPRING_FOOT_TOP = Y_BASE_TOP + SPRING_T  # wall under the foot centreline
SPRING_HOLE_X = SPRING_X + SPR_FOOT_END_L[0] + SPR_HOLE_FROM_END  # -20.37

if math.hypot(_SPR_PIVOT[0] - PIVOT_X, _SPR_PIVOT[1] - PIVOT_Y) > 0.01:
    raise AssertionError("spring part frame disagrees with the strap pivot")
if SPRING_AXIS_OFF - STRAP_R_END - SPRING_T < 0.25 - 1e-9:
    raise AssertionError("spring blade touches the parked strap flank")
if SPRING_W / 2.0 > STRAP_T / 2.0:
    raise AssertionError("spring blade overhangs the strap flank axially")
if abs((LIFT_X - PIVOT_X) * _SPR_N[0] - SPRING_AXIS_OFF) - SPRING_T - 3.175 < 0.25:
    raise AssertionError("spring blade fouls the lift rod")  # perpendicular
    # foot of the rod axis lands mid-blade, so the segment bound is the line's
    # (west rod: the blade sits 10.1 EAST of the strap axis, the rod ~14.7 WEST)
if (math.hypot(X_DRUM - SPRING_CREST[0], Y_DRIVE - SPRING_CREST[1])
        - SPRING_T < TIP_DRUM120 + 0.25):
    raise AssertionError("spring contact crest crowds the cylinder-gear tips")
if (math.hypot(X_DRUM - SPRING_FLAT_TIP[0], Y_DRIVE - SPRING_FLAT_TIP[1])
        - SPRING_T < TIP_DRUM120 + 0.25):
    raise AssertionError("spring flat tip crowds the cylinder-gear tips")
if (math.hypot(SPRING_CREST[0] - APINION_X, SPRING_CREST[1] - APINION_Y)
        < STRAP_R_END + SPRING_T + 0.25):
    raise AssertionError("spring contact crest reaches the strap's arbor end cap")
# The flat tips back WEST toward the strap; its wall is on the gated EAST
# side, so the governing surface is the centreline itself. Two constraints,
# tip-governed (n falls monotonically along kink + flat): the parked FLANK
# line (n = R_END, the 6.28 mm^3 interference the first PR7 build hit at
# FLAT_LEN 6) and the arbor-end cap circle.
_FLAT_TIP_N = ((SPRING_FLAT_TIP[0] - PIVOT_X) * _SPR_N[0]
               + (SPRING_FLAT_TIP[1] - PIVOT_Y) * _SPR_N[1])
if _FLAT_TIP_N < STRAP_R_END + 0.25:
    raise AssertionError("spring flat tip re-enters the parked strap flank")
if (math.hypot(SPRING_FLAT_TIP[0] - APINION_X, SPRING_FLAT_TIP[1] - APINION_Y)
        < STRAP_R_END + 0.25):
    raise AssertionError("spring flat tip reaches the strap's arbor end cap")
if SPRING_Z + SPRING_W / 2.0 > BLOCK_BACK_Z0 - 0.25:
    raise AssertionError("spring reaches the back pivot block")
# West foot corridor (PR7 item 11): the strip crosses UNDER the lift rod and
# the parked/sweeping back cam pin; its screw head must clear the rod flank.
if (PIVOT_Y - 3.175) - SPRING_FOOT_TOP < 0.25:
    raise AssertionError("spring foot reaches the lift rod above it")
if (LIFT_X - 3.175) - (SPRING_HOLE_X + FSCREW_HEAD_DIA / 2.0) < 0.25:
    raise AssertionError("spring foot screw head crowds the lift rod")
if SPRING_HOLE_X - FSCREW_HEAD_DIA / 2.0 - 0.25 < SPRING_X + SPR_FOOT_END_L[0]:
    raise AssertionError("spring foot screw head overhangs the foot's free end")

# --- cam engage path (ch. 25, p.68-69; PR5) ----------------------------------
# Each strap tail carries a CAM-FOLLOWER PIN (build_pinion_cam_pin.py) pressed
# through the bracket's tail cross-bore, protruding WEST over the lift rod.
# Turning the lever rotates the lift rod; its radial cam pin sweeps up beneath
# the follower and lifts it -- a west-of-pivot, below-pivot point RISES under
# the CW engage swing -- pushing the drum east into mesh against the return
# spring. Parked (pins straight down) nothing touches; the engaged contact is
# proven REACHABLE analytically below (segment-segment scan), and the probe /
# motion articulation owns driving it.
CAM_DROP = 6.25  # pivot bore -> follower bore, down the strap centreline
# (build_pinion_bracket CAM_DROP, must match)
CAM_PIN_DIA = 3.0  # build_pinion_bracket CAM_BORE / build_pinion_cam_pin
# PIN_DIA (must match)
CAM_PIN_LEN = 17.5  # build_pinion_cam_pin PIN_LEN (must match)
CAM_T_EAST = 7.5  # axial split: follower east end ~1.0 proud of the cap's
# east exit (photo: a short stub), the rest is the west working reach. The
# pin mid-plane therefore sits CAM_PIN_LEN/2 - CAM_T_EAST = 1.25 west of the
# bracket's Right plane -- the axial mate below. (7.25 left the west end just
# 0.15 off the rod flank, under the 0.25 design margin.)
ROD_PIN_DIA = 3.0  # build_pinion_lift_rod PIN_DIA (must match; thinned with
# PR5 -- see the part's comment). ROD_PIN_TIP is imported (10.8 after the
# PR7 shortening for the spring's west foot crossing beneath).
_CAM_R_SUM = (CAM_PIN_DIA + ROD_PIN_DIA) / 2.0  # 3.5 contact centre distance
_CAM_T_WEST = CAM_PIN_LEN - CAM_T_EAST  # 10.25 west of the bore centre
_CAM_C = (
    PIVOT_X - CAM_DROP * _SPR_U[0],
    PIVOT_Y - CAM_DROP * _SPR_U[1],
)  # follower bore centre, machine frame (-0.18, 56.70)
_CAM_HALF_CHORD = math.sqrt(STRAP_R_END**2 - CAM_DROP**2)  # 6.48 through the cap

# Rod-pin z stations (rod z0 -114, pins at +36.5/+184.5) vs the strap
# mid-planes the followers live in: the crossed cylinders meet 0.25/0.45 off
# crown -- well under the 3.5 contact sum, checked here so a z-shuffle of the
# rig cannot silently split the cam from its follower.
_ROD_PIN_Z = tuple(LIFT_ROD_Z0 + s for s in ROD_PIN_STATIONS)  # -77.5 / +70.5
_STRAP_MID_Z = (
    APINION_Z_FRONT - STRAP_AIR - STRAP_T / 2.0,  # -77.75
    APINION_Z_BACK + STRAP_AIR + STRAP_T / 2.0,  # +70.95
)
for _pz, _sz in zip(_ROD_PIN_Z, _STRAP_MID_Z, strict=True):
    if abs(_pz - _sz) > 1.0:
        raise AssertionError("lift-rod cam pin misses its strap's z plane")

# Bore integrity in the tail cap (web to the pivot bore, rim to the cap edge).
if CAM_DROP - CAM_PIN_DIA / 2.0 - 3.175 < 1.5:
    raise AssertionError("cam bore web to the pivot bore too thin")
if STRAP_R_END - CAM_DROP - CAM_PIN_DIA / 2.0 < 1.2:
    raise AssertionError("cam bore rim to the tail cap edge too thin")
if CAM_PIN_LEN - CAM_T_EAST - _CAM_HALF_CHORD < 3.0:
    raise AssertionError("follower's west working protrusion too short")

# Follower east end vs the return spring's blade (same z plane, back strap).
if SPRING_AXIS_OFF - SPRING_T - CAM_T_EAST < 0.25:
    raise AssertionError("follower's east stub reaches the spring blade")
# The spring's west foot (PR7) crosses UNDER the back rod pin: the sweeping
# pin's tip CORNER (radius hypot(tip, r)) must clear the strip top.
if PIVOT_Y - math.hypot(ROD_PIN_TIP, ROD_PIN_DIA / 2.0) - SPRING_FOOT_TOP < 0.25:
    raise AssertionError("sweeping cam-pin corner dips into the spring foot")

# Parked clearances: follower fully east of the down-pin plane and of the
# rod's own flank band; underside off the base.


def _cam_end(t: float, c=_CAM_C) -> tuple[float, float]:
    """Point at axial parameter t along the follower axis (east positive)."""
    return (c[0] + t * _SPR_N[0], c[1] + t * _SPR_N[1])


_CAM_WEST_END = _cam_end(-_CAM_T_WEST)
# End-disc x reach: the face tilts with the lean, so its westmost material is
# r * |in-plane normal x| west of the end centre.
_CAM_WESTMOST = _CAM_WEST_END[0] - CAM_PIN_DIA / 2.0 * abs(_SPR_U[0])
if _CAM_WESTMOST - (LIFT_X + ROD_PIN_DIA / 2.0) < 1.0:
    raise AssertionError("follower's west end crowds the parked down-pin plane")
if _CAM_WESTMOST - (LIFT_X + 3.175) < 0.25:
    raise AssertionError("follower's west end reaches over the lift rod")
if _CAM_WEST_END[1] - CAM_PIN_DIA / 2.0 - Y_BASE_TOP < 0.25:
    raise AssertionError("follower's west end grazes the base top")

# Engage swing angle from the c2c triangle (pivot, drum axis, pinion axis):
# parked ray angle minus engaged ray angle about the pivot, both from +x.
_PD = math.hypot(X_DRUM - PIVOT_X, Y_DRIVE - PIVOT_Y)  # 68.05 pivot -> drum
_ANG_PARKED = math.atan2(APINION_Y - PIVOT_Y, APINION_X - PIVOT_X)
_ANG_ENGAGED = math.atan2(Y_DRIVE - PIVOT_Y, X_DRUM - PIVOT_X) + math.acos(
    max(-1.0, min(1.0, (STRAP_C2C**2 + _PD**2 - ENGAGED_C2C**2)
                  / (2.0 * STRAP_C2C * _PD)))
)
_PHI_ENG = _ANG_PARKED - _ANG_ENGAGED  # ~4.1 deg CW, radians
if not 0.01 < _PHI_ENG < math.radians(10.0):
    raise AssertionError("engage swing angle out of the expected band")


def _seg_seg_dist(p0, p1, q0, q1) -> float:
    """Min distance between 3D segments p0-p1 and q0-q1 (standard clamp)."""
    u = [p1[i] - p0[i] for i in range(3)]
    v = [q1[i] - q0[i] for i in range(3)]
    w = [p0[i] - q0[i] for i in range(3)]
    a = sum(x * x for x in u)
    b = sum(x * y for x, y in zip(u, v, strict=True))
    c = sum(x * x for x in v)
    d = sum(x * y for x, y in zip(u, w, strict=True))
    e = sum(x * y for x, y in zip(v, w, strict=True))
    den = a * c - b * b
    sc, sn, sd = 0.0, 0.0, den
    tc, tn, td = 0.0, 0.0, den
    if den < 1e-12:
        sn, sd, tn, td = 0.0, 1.0, e, c
    else:
        sn, tn = b * e - c * d, a * e - b * d
        if sn < 0.0:
            sn, tn, td = 0.0, e, c
        elif sn > sd:
            sn, tn, td = sd, e + b, c
    # Endpoint branches: clamp sn against the NEW denominator a (clamping
    # against the interior-case sd = den let sc exceed 1, measuring to a
    # phantom point beyond p1 -- caught in review on #163).
    if tn < 0.0:
        tn = 0.0
        sn = min(max(-d, 0.0), a) if a > 1e-12 else 0.0
        sd = a if a > 1e-12 else 1.0
    elif tn > td:
        tn = td
        sn = min(max(-d + b, 0.0), a) if a > 1e-12 else 0.0
        sd = a if a > 1e-12 else 1.0
    sc = sn / sd if sd > 1e-12 else 0.0
    tc = tn / td if td > 1e-12 else 0.0
    dp = [w[i] + sc * u[i] - tc * v[i] for i in range(3)]
    return math.sqrt(sum(x * x for x in dp))


def _cam_contact_azimuth(phi: float, dz: float) -> float | None:
    """Rod-pin azimuth (rad, east-of-down) where the sweeping pin first
    CONTACTS the follower (segment-segment distance = the radii sum), with the
    follower swung CW by ``phi`` about the pivot. ``dz`` = rod-pin plane minus
    strap mid-plane. Returns None if no contact by 60 deg."""
    cphi, sphi = math.cos(phi), math.sin(phi)

    def rot(p):  # CW by phi about the pivot
        x, y = p[0] - PIVOT_X, p[1] - PIVOT_Y
        return (PIVOT_X + x * cphi + y * sphi, PIVOT_Y - x * sphi + y * cphi)

    e = rot(_cam_end(CAM_T_EAST))
    w = rot(_cam_end(-_CAM_T_WEST))
    q0 = (w[0], w[1], 0.0)
    q1 = (e[0], e[1], 0.0)
    for step in range(0, 1201):
        th = math.radians(step * 0.05)
        tip = (
            LIFT_X + ROD_PIN_TIP * math.sin(th),
            PIVOT_Y - ROD_PIN_TIP * math.cos(th),
            dz,
        )
        root = (LIFT_X, PIVOT_Y, dz)
        if _seg_seg_dist(root, tip, q0, q1) <= _CAM_R_SUM:
            return th
    return None


def _cam_park_gap(dz: float) -> float:
    """Surface-to-surface gap between the parked (straight-down) rod pin and
    the parked follower."""
    q0 = (*_CAM_WEST_END, 0.0)
    q1 = (*_cam_end(CAM_T_EAST), 0.0)
    root, tip = (LIFT_X, PIVOT_Y, dz), (LIFT_X, PIVOT_Y - ROD_PIN_TIP, dz)
    return _seg_seg_dist(root, tip, q0, q1) - _CAM_R_SUM


_TH_PARK_TOUCH = _TH_ENG = None
for _dz in (abs(_pz - _sz) for _pz, _sz in zip(_ROD_PIN_Z, _STRAP_MID_Z, strict=True)):
    if _cam_park_gap(_dz) < 0.4:
        raise AssertionError("parked cam pin sits under 0.4 off the follower")
    _TH_PARK_TOUCH = _cam_contact_azimuth(0.0, _dz)
    _TH_ENG = _cam_contact_azimuth(_PHI_ENG, _dz)
    if _TH_PARK_TOUCH is None or _TH_PARK_TOUCH < math.radians(5.0):
        raise AssertionError("cam pin touches the follower at (or too near) park")
    if _TH_ENG is None:
        raise AssertionError("cam pin cannot reach the engaged follower")
# Tip stays clear of the tail cap (R9 about the pivot, which does not move)
# through the whole working sweep, with margin.
for _step in range(0, int(math.degrees(_TH_ENG) * 4) + 1):
    _th = math.radians(_step * 0.25)
    _tip = (LIFT_X + ROD_PIN_TIP * math.sin(_th), PIVOT_Y - ROD_PIN_TIP * math.cos(_th))
    if math.hypot(_tip[0] - PIVOT_X, _tip[1] - PIVOT_Y) < STRAP_R_END + 0.25:
        raise AssertionError("cam pin tip gouges the strap tail cap mid-sweep")

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
_TEE_R = max(HANDLE_ARM_DOWN, HANDLE_ARM_UP) + 0.5  # swept disc radius:
# the long arm's flat-end corner reaches hypot(43, 3) = 43.1
# The SWEPT geometry splits in two: the Ø6 cross rod sweeps the R43.5 disc
# in its own thin band; the grip + cap + tube hub stay ON AXIS (R11.5 worst),
# only their z reach is wider.
_TEE_DISC_Z = (HANDLE_Z - 3.0, HANDLE_Z + 3.0)
_TEE_HUB_Z = (
    HANDLE_Z - HANDLE_GRIP_LEN / 2.0 - HANDLE_CAP_SAG,
    HANDLE_Z + HANDLE_GRIP_LEN / 2.0 + HANDLE_WALL_T + HANDLE_TUBE_LEN,
)  # -153 .. -125: cap, grip, blind wall, tube seat
# In-assembly bodies near the tee: everything of the swing rig ends well
# north of the disc band; the crank cluster lives south/east of it.
for _lo, _hi, _what in (
    (LEVER_Z - LEVER_HUB_LEN / 2.0 - LEVER_CAP_SAG, LEVER_Z + LEVER_HUB_LEN / 2.0,
     "lever hub"),
    (BLOCK_FRONT_Z0, BLOCK_FRONT_Z0 + BLOCK_DEPTH, "front pivot block"),
    (LIFT_ROD_Z0, LIFT_ROD_Z0 + 202.0, "lift rod"),
    (PIVOT_SHAFT_Z0, PIVOT_SHAFT_Z0 + 192.0, "pivot shaft"),
    (APINION_Z_FRONT - STRAP_T - STRAP_AIR, APINION_Z_FRONT, "front strap"),
    (REMOVABLE_Z0, REMOVABLE_Z0 + 5.0, "T12 chain wheel"),
    (CRANK_ARM_Z0, CRANK_ARM_Z0 + 8.0, "crank arm hub"),
):
    if _TEE_DISC_Z[1] > _lo - 0.25 and _TEE_DISC_Z[0] < _hi + 0.25:
        raise AssertionError(f"tee-handle sweep disc band reaches the {_what}")
# The hub's wider z band DOES clip the T12 plane: radial clearance instead
# (the grip is on-axis, the wheel is on the crank axis). The crank arm+handle
# sweep entirely south of the arm hub (-175..) -- z-disjoint from the grip.
if (math.hypot(X_CRANK - APINION_X, Y_CRANK - APINION_Y)
        < HANDLE_GRIP_DIA / 2.0 + 16.0 + 0.25):  # T12 OD/2 ~14 + margin
    raise AssertionError("tee-handle grip reaches the T12 chain wheel")
if _TEE_HUB_Z[0] < CRANK_ARM_Z0 + 8.0 + 0.25:
    raise AssertionError("tee-handle grip band reaches the crank arm sweep")

# Lever full throw (parked 40 deg -> engaged ~51 deg, checked to 60): the
# arbor distance grows monotonically past 37.6 deg, but prove it numerically,
# and prove the swept tip annulus shares no z band with anything it could hit.
for _step in range(0, 81):
    _t = math.radians(LEVER_TILT_DEG + _step * 0.25)
    _d = abs(_LEV_REL[0] * math.cos(_t) - _LEV_REL[1] * math.sin(_t))
    if _d < (ARBOR_DIA + LEVER_ROD_DIA) / 2.0 + 0.25:
        raise AssertionError("lever shaft crowds the arbor mid-throw")
_LEV_Z = (LEVER_Z - 3.0, LEVER_Z + 3.0)  # rod plane through the throw
if _LEV_Z[0] < BLOCK_FRONT_Z0 + BLOCK_DEPTH + 0.25 and _LEV_Z[1] > BLOCK_FRONT_Z0 - 0.25:
    raise AssertionError("lever throw plane reaches the front pivot block")
if _LEV_Z[1] > PIVOT_SHAFT_Z0 - 0.25:
    raise AssertionError("lever throw plane reaches the pivot shaft front end")
if _LEV_Z[0] < _TEE_HUB_Z[1] + 0.25:
    raise AssertionError("lever throw plane reaches the tee-handle sweep")

# Lift-rod cam pins through the throw (0 -> 60 deg): tip circle vs the pivot
# shaft, the base top, and (back station, spring plane) the blade line.
if 15.0 - ROD_PIN_TIP - 3.175 < 0.25:  # rod->pivot-shaft spacing is 15
    raise AssertionError("cam pin sweep reaches the pivot shaft")
if (PIVOT_Y - ROD_PIN_TIP) - Y_BASE_TOP < 0.25:
    raise AssertionError("cam pin sweep reaches the base top")
if (LIFT_X + ROD_PIN_TIP) > SPRING_X - 3.5 - 0.25:
    raise AssertionError("cam pin sweep reaches the spring foot region")

# --- pinion arbor + rig fasteners (PR7 items 2/11/12/14) ---------------------
# The steel Ø8 arbor replaced the drum's integral stubs: it presses through
# the drum, journals in both straps' top bores, and its flat front tip seats
# flush on the tee handle's blind-cap bore floor.
ARBOR_Z0 = -135.0  # front tip station (crowned back end at +91.25)
if abs((HANDLE_Z + HANDLE_GRIP_LEN / 2.0 + HANDLE_WALL_T) - ARBOR_Z0) > 1e-9:
    raise AssertionError("arbor front tip off the handle cap's bore floor")
if abs(ARBOR_Z0 + ARBOR_LEN - 91.25) > 0.01:  # GT pinion_back free end
    raise AssertionError("arbor back end off the GT pinion_back station")
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
    for sx in (BLOCK_SCREW_HALF, -BLOCK_SCREW_HALF)
)
# Machine-handed base part vs this pre-mirror derivation: x negates (the
# pivot-hole assert convention above).
for _want, _have in zip(_BLOCK_SCREW_XZ, BASE_BLOCK_XZ, strict=True):
    if abs(_want[0] + _have[0]) > 0.05 or abs(_want[1] - _have[1]) > 0.05:
        raise AssertionError(
            f"harmonic-base block-screw hole {_have} != machine derived "
            f"({-_want[0]:.3f}, {_want[1]:.3f})")
# Foot screws (items 2 + 11): the black O2.9 hold-down at the spring foot
# and on the pedestal's exposed flange.
if FSCREW_SHANK_DIA > min(SPR_HOLE_DIA, ARBOR_PED_HOLE_DIA,
                          BASE_FOOT_HOLE_DIA) - 0.1:
    raise AssertionError("foot screw shank binds in a foot hole")
if FSCREW_SHANK_LEN - ARBOR_PED_FLANGE_T < 2.0:
    raise AssertionError("foot screw barely engages the base at the pedestal")
if FSCREW_SHANK_LEN - SPRING_T > BASE_FOOT_HOLE_DEPTH - 0.25:
    raise AssertionError("foot screw bottoms out in the base hole (spring seat)")
# Head fits the pedestal's exposed flange strip (local z -8..-2, centre -5).
if FSCREW_HEAD_DIA / 2.0 > min(
        abs(ARBOR_PED_SCREW_Z + ARBOR_PED_DEPTH / 2.0),
        abs(ARBOR_PED_DEPTH / 2.0 - ARBOR_PED_STRAP_T - ARBOR_PED_SCREW_Z)):
    raise AssertionError("foot screw head overhangs the pedestal flange")
_FOOT_SCREW_XZ = (
    (SPRING_HOLE_X, SPRING_Z),
    (X_DRUM, -ARBOR_PEDESTAL_Z + ARBOR_PED_SCREW_Z),
)
# Same machine-handed x negation as the block screws above.
for _want, _have in zip(_FOOT_SCREW_XZ, BASE_FOOT_XZ, strict=True):
    if abs(_want[0] + _have[0]) > 0.05 or abs(_want[1] - _have[1]) > 0.05:
        raise AssertionError(
            f"harmonic-base foot-screw hole {_have} != machine derived "
            f"({-_want[0]:.3f}, {_want[1]:.3f})")


IDENTITY = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
ROT_X_POS90 = [[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, -1.0, 0.0]]
ROT_Y_POS90 = [[0.0, 0.0, -1.0], [0.0, 1.0, 0.0], [1.0, 0.0, 0.0]]
# Cam-follower pin pose: part +Z (the pin axis) -> the strap's leaned bore
# direction d = _SPR_N, part +Y -> up the strap line (_SPR_U), part +X -> -z.
# Right-handed: X x Y = (u1, -u0, 0) = _SPR_N. The pin's mid-plane origin
# sits CAM_PIN_LEN/2 - CAM_T_EAST west of the bore centre along d.
CAM_ROWS = [
    [0.0, 0.0, -1.0],
    [_SPR_U[0], _SPR_U[1], 0.0],
    [_SPR_N[0], _SPR_N[1], 0.0],
]
CAM_EULER = euler_from_rows(CAM_ROWS)
_CAM_PIN_ORG = _cam_end((CAM_T_EAST - _CAM_T_WEST) / 2.0)
ROT_Y_INCLINE = [
    [COS_I, 0.0, SIN_I],
    [0.0, 1.0, 0.0],
    [-SIN_I, 0.0, COS_I],
]  # Ry(-INCLINE), row-vector convention (matches the frame script's Ry rows)
# The tip-stack riders are authored along +Y (Top-plane extrusions); these lay
# that +Y axis along the inclined plate frame (same row-vector convention).
ROT_SHAFT_NORTH = [  # +Y -> the increasing-station shaft direction (bushing)
    [COS_I, 0.0, SIN_I],
    [-SIN_I, 0.0, COS_I],
    [0.0, -1.0, 0.0],
]
ROT_SHAFT_SOUTH = [  # +Y -> the decreasing-station direction (adjuster: head north)
    [COS_I, 0.0, SIN_I],
    [SIN_I, 0.0, -COS_I],
    [0.0, 1.0, 0.0],
]
ROT_PINCH_WEST = [  # +Y -> plate-frame +X: the head seats east, the shank runs west
    [0.0, 1.0, 0.0],
    [COS_I, 0.0, SIN_I],
    [SIN_I, 0.0, -COS_I],
]


def rot_z_rows(deg: float) -> list[list[float]]:
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [[c, s, 0.0], [-s, c, 0.0], [0.0, 0.0, 1.0]]


def _org(adapter, name: str) -> list[float]:
    """A component's current origin (mm) in the assembly frame."""
    a = component_transform(adapter, name)
    return [a[9] * 1000.0, a[10] * 1000.0, a[11] * 1000.0]


async def _locate_to_datum(adapter, name: str) -> None:
    """Locate a static mount to the machine datum planes (three orthogonal plane
    distances), replacing an explicit fix for a part with no in-subassembly
    contact partner. A free-space position relative to the machine origin
    (strictly necessary) -- the frame-column idiom. The mount is inserted at
    IDENTITY, so its principal planes are parallel to the assembly's and the
    three distances are just its origin coordinates."""
    o = _org(adapter, name)
    for axis, plane, coord in (
        ("Y", "Top Plane", o[1]),
        ("X", "Right Plane", o[0]),
        ("Z", "Front Plane", o[2]),
    ):
        await seat_signed(
            adapter,
            named_ref(f"{plane}@{name}", "PLANE"),
            plane,
            coord,
            label=f"{name} datum {axis} d={coord:+.2f}",
            verify=(name, o),
        )


async def _key_to_shaft(
    adapter, part, part_axis, shaft_axis_ref, shaft, shaft_o, axis_dir, label,
) -> None:
    """Key a gear rigidly onto a shaft via SEMANTIC mates, replacing a lock:
    coaxial (collinear axes) + an axial seat (Front-plane distance along the
    shaft axis, read live) + a parallel anti-spin. The gear and shaft share the
    inclined orientation (ROT_Y_INCLINE), so their Right planes are parallel at
    the keyed phase -- the parallel pins the spin with no tuned angle (the
    lag-screw idiom). Removes the same 6 DOF the lock did; no fix/lock."""
    p_o = _org(adapter, part)
    d_axial = abs(sum((p_o[k] - shaft_o[k]) * axis_dir[k] for k in range(3)))
    await coincident_mate(
        adapter, named_ref(f"{part_axis}@{part}", "AXIS"), shaft_axis_ref,
        label=f"{label} coaxial", verify=(part, p_o),
    )
    await distance_driver(
        adapter,
        named_ref(f"Front Plane@{part}", "PLANE"),
        named_ref(f"Front Plane@{shaft}", "PLANE"),
        d_axial,
        label=f"{label} axial seat d={d_axial:.2f}", verify=(part, p_o),
    )
    await parallel_mate(
        adapter,
        named_ref(f"Right Plane@{part}", "PLANE"),
        named_ref(f"Right Plane@{shaft}", "PLANE"),
        label=f"{label} anti-spin (keyed phase)", verify=(part, p_o),
    )


async def _seat_on_crank(
        adapter, part, part_axis, crank_axis, crankshaft, cs_z) -> list[float]:
    """Journal a crank-chain part on the crankshaft via SEMANTIC mates: coaxial
    on the crank axis + an axial seat (the part's Z-normal Front plane to the
    CRANKSHAFT's Top plane -- its axial datum -- distance read live). The seat
    must reference the crankshaft, NOT a world datum: a plane-plane distance
    forces the planes parallel, so seating against the assembly Front plane
    pins the crank axis to machine z and through it the whole p1 swing (the
    platform reads fully defined -- caught by drive-train:dof-free-necessity).
    Leaves ONLY spin -- the caller pins it with a per-part anti-spin. Returns
    the part's live origin."""
    o = _org(adapter, part)
    await coincident_mate(
        adapter, named_ref(f"{part_axis}@{part}", "AXIS"), crank_axis,
        label=f"{part} coaxial on crank", verify=(part, o),
    )
    d_seat = abs(o[2] - cs_z)
    await distance_driver(
        adapter, named_ref(f"Front Plane@{part}", "PLANE"),
        named_ref(f"Top Plane@{crankshaft}", "PLANE"), d_seat,
        label=f"{part} axial seat d={d_seat:.2f} (on the crankshaft)",
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
    # `free` (default) DEFERS the freed-DOF park drivers (records, does not author);
    # `locked` authors them engaged. Set before any *_driver(free_dof_key=...) call.
    set_park_defer(not LOCK)
    check("create_assembly", await adapter.create_assembly())

    # =================== structure (located, not fixed) ====================
    # The stationary arbor is the reference frame the moving train mates
    # against. Inserted FIRST, so SolidWorks auto-fixes it as the seed (the one
    # allowed fixed component, mirroring frame's harmonic-base) -- no explicit fix.
    arbor = await place_component(
        adapter, "cylinder-gear-shaft",
        [X_DRUM, Y_DRIVE, ARBOR_SOUTH_Z],
        [90.0, 0.0, 0.0], ROT_X_POS90, ground=False, label="cylinder arbor (seed)",
    )
    # The arbor-pedestal is a static mount bolted to the (absent) base. With
    # no in-subassembly contact partner, it is LOCATED to the machine datum
    # planes by three orthogonal plane distances (a free-space machine-frame
    # position, strictly necessary) -- the frame-column pattern, replacing the
    # explicit fix. (The old separate crank-pedestal is GONE: the merged green
    # column below rides the swing platform.)
    # South arbor pedestal only (2026-06-19): the rocker support's arbor-clamp
    # boss is gone with the portal unification, AND the now-solid portal north
    # upright occupies the space the arbor's north end used to pass through. The
    # arbor is shortened to clear the portal (ARBOR_LENGTH) and its north end is
    # left unsupported for now -- the dedicated north-end support (pedestal) and
    # the cone small-end bracket are DEFERRED to the cone-position rework, since
    # the cone is currently mis-positioned and that region will be re-laid out.
    arbor_pedestal = await place_component(
        adapter, "arbor-pedestal",
        [X_DRUM, Y_BASE_TOP, -ARBOR_PEDESTAL_Z], [0.0, 0.0, 0.0], IDENTITY, ground=False,
        label=f"arbor-pedestal z={-ARBOR_PEDESTAL_Z:g}",
    )
    await _locate_to_datum(adapter, arbor_pedestal)
    # The cone SWING PLATFORM is the swing bracket (ch.12, p.18 "pivot"):
    # floated so the whole cone set can swing horizontally out of mesh about
    # its tip-end vertical pivot (p1). Pinned at the engaged rest pose by a
    # suppressible angle driver in the joints section. The pivot post and tip
    # block are seated ON its PlateTop below, so they -- and the shaft they
    # journal -- ride the swing as one unit.
    ppivot = cone_station(PIVOT_STATION)
    platform = await place_component(
        adapter, "cone-swing-platform",
        [ppivot[0], Y_BASE_TOP, ppivot[2]], [0.0, -INCLINE_DEG, 0.0], ROT_Y_INCLINE,
        ground=False, label="cone-swing-platform (swing bracket, engaged rest)",
    )
    ppost = cone_station(POST_STATION)
    pivot_post = await place_component(
        adapter, "cone-pivot-post",
        [ppost[0], Y_BASE_TOP + PLAT_T, ppost[2]], [0.0, -INCLINE_DEG, 0.0],
        ROT_Y_INCLINE, ground=False,
        label="cone-pivot-post (big-end journal, on the plate)",
    )
    ptip = cone_station(TIP_BLOCK_STATION)
    tip_block = await place_component(
        adapter, "cone-tip-block",
        [ptip[0], Y_BASE_TOP + PLAT_T, ptip[2]], [0.0, -INCLINE_DEG, 0.0],
        ROT_Y_INCLINE, ground=False,
        label="cone-tip-block (tip journal, on the plate)",
    )
    # Tip end-play stack (item 5, v4_t00471): the brass spacer bushing on the
    # tip stub, the axial adjuster screw in the block's counterbore, and the
    # pinch screw across the block's top slit. Stations derived at import
    # (BUSH_STATION / ADJ_HEAD_STATION); all three ride the swing family.
    pbush = cone_station(BUSH_STATION)
    tip_bushing = await place_component(
        adapter, "cone-tip-bushing",
        [pbush[0], Y_DRIVE, pbush[2]], [90.0, -INCLINE_DEG, 0.0],
        ROT_SHAFT_NORTH, ground=False,
        label="cone-tip-bushing (T006 spacer, on the tip stub)",
    )
    padj = cone_station(ADJ_HEAD_STATION)
    tip_adjuster = await place_component(
        adapter, "cone-tip-adjuster",
        [padj[0], Y_DRIVE, padj[2]], [-90.0, -INCLINE_DEG, 0.0],
        ROT_SHAFT_SOUTH, ground=False,
        label="cone-tip-adjuster (axial end-play screw, head north)",
    )
    pinch_screw = await place_component(
        adapter, "cone-tip-pinch-screw",
        [
            ptip[0] + (TIP_BLOCK_X / 2.0) * COS_I,
            Y_BASE_TOP + PLAT_T + TIP_PINCH_Y,
            ptip[2] + (TIP_BLOCK_X / 2.0) * SIN_I,
        ],
        [0.0, -INCLINE_DEG, -90.0], ROT_PINCH_WEST, ground=False,
        label="cone-tip-pinch-screw (slit clamp, head east)",
    )
    # The lock knob (v4_t00411) is a base-bolted static like the pedestals: its
    # washer seat lands on the plate top, its stud drops through the plate's
    # lock slot (engaged end -- the as-built pose). The plate is the mover: on
    # disengage its slot sweeps around this stationary stud. No rotation: the
    # knob is axisymmetric and belongs to the BASE, not the inclined plate.
    lock_knob = await place_component(
        adapter, "cone-lock-knob",
        [KNOB_X, Y_BASE_TOP + PLAT_T, KNOB_Z], [0.0, 0.0, 0.0], IDENTITY,
        ground=False, label="cone-lock-knob (platform clamp, engaged end)",
    )
    await _locate_to_datum(adapter, lock_knob)
    # The platform pivot screw (item 2, p.18 "pivot"): a base-threaded STATIC
    # like the knob -- head seated on the plate top at the swing pivot, its
    # shoulder dropping through the plate's clearance hole into the base's
    # pivot hole. The plate rotates ABOUT it; the screw never moves.
    pivot_screw = await place_component(
        adapter, "cone-pivot-screw",
        [ppivot[0], Y_BASE_TOP + PLAT_T, ppivot[2]], [0.0, 0.0, 0.0], IDENTITY,
        ground=False, label="cone-pivot-screw (p1 pivot pin)",
    )
    await _locate_to_datum(adapter, pivot_screw)
    # The swing-stop screw (item 6): a base-threaded STATIC just past the
    # DISENGAGED pose -- the plate's west edge bumps its proud shank, limiting
    # the p1 swing to exactly the knob-clear travel (STOP_X/STOP_Z derived at
    # import and asserted against the base's hardcoded hole).
    stop_screw = await place_component(
        adapter, "swing-stop-screw",
        [STOP_X, Y_BASE_TOP, STOP_Z], [0.0, 0.0, 0.0], IDENTITY,
        ground=False, label="swing-stop-screw (p1 travel limit)",
    )
    await _locate_to_datum(adapter, stop_screw)

    # ============ alignment pinion swing group (ch.25, p.66; p2) ============
    # Floated straps + drum, joined and parked DISENGAGED in the joints
    # section. The pivot blocks, torque shaft and lift rod are base-bolted
    # statics (located to the machine datums below); the tilted lever + tee
    # handle coincide with the parked rig and stay FIXED for now -- their
    # z-rotation breaks the plane-distance locate, and a semantic re-mate is
    # deferred with the engaged configuration.
    align_pinion = await place_component(
        adapter, "alignment-pinion",
        [APINION_X, APINION_Y, APINION_Z_FRONT], [0.0, 0.0, 0.0], IDENTITY,
        ground=False, label="alignment-pinion (disengaged rest)",
    )
    pinion_brackets: dict[str, str] = {}
    for tag, z0 in (
        ("front", APINION_Z_FRONT - STRAP_T - STRAP_AIR),
        ("back", APINION_Z_BACK + STRAP_AIR),
    ):
        pinion_brackets[tag] = await place_component(
            adapter, "pinion-bracket",
            [PIVOT_X, PIVOT_Y, z0],
            [0.0, 0.0, STRAP_LEAN_DEG], rot_z_rows(STRAP_LEAN_DEG),
            ground=False, label=f"pinion-bracket {tag} (leaning, arbor bore up top)",
        )
    pinion_blocks: list[str] = []
    for tag, z0 in (("front", BLOCK_FRONT_Z0), ("back", BLOCK_BACK_Z0)):
        blk = await place_component(
            adapter, "pinion-pivot-block",
            [BLOCK_X, PIVOT_Y, z0], [0.0, 0.0, 0.0], IDENTITY,
            ground=False, label=f"pinion-pivot-block {tag}",
        )
        pinion_blocks.append(blk)
    pivot_shaft = await place_component(
        adapter, "pinion-pivot-shaft",
        [PIVOT_X, PIVOT_Y, PIVOT_SHAFT_Z0], [0.0, 0.0, 0.0], IDENTITY,
        ground=False,
    )
    lift_rod = await place_component(
        adapter, "pinion-lift-rod",
        [LIFT_X, PIVOT_Y, LIFT_ROD_Z0], [0.0, 0.0, 0.0], IDENTITY,
        ground=False, label="pinion-lift-rod (cam pins parked down)",
    )
    spring = await place_component(
        adapter, "pinion-spring",
        [SPRING_X, Y_BASE_TOP, SPRING_Z], [0.0, 0.0, 0.0], IDENTITY,
        ground=False, label="pinion-spring (holds the swing disengaged)",
    )
    cam_pins: dict[str, str] = {}
    for tag, z_mid in (("front", _STRAP_MID_Z[0]), ("back", _STRAP_MID_Z[1])):
        cam_pins[tag] = await place_component(
            adapter, "pinion-cam-pin",
            [_CAM_PIN_ORG[0], _CAM_PIN_ORG[1], z_mid], CAM_EULER, CAM_ROWS,
            ground=False, label=f"pinion-cam-pin {tag} (strap tail follower)",
        )
    await place_component(
        adapter, "pinion-lever",
        [LIFT_X, PIVOT_Y, LEVER_Z],
        [0.0, 0.0, -LEVER_TILT_DEG], rot_z_rows(-LEVER_TILT_DEG),
        label="pinion-lever (clamp hub on the lift rod front end)",
    )
    await place_component(
        adapter, "pinion-handle",
        [APINION_X, APINION_Y, HANDLE_Z],
        [0.0, 0.0, -HANDLE_TILT_DEG], rot_z_rows(-HANDLE_TILT_DEG),
        label="pinion-handle (blind cap over the arbor front end)",
    )
    # The steel arbor (PR7 item 14): pressed through the brass drum, journaled
    # in both straps' Ø8 top bores -- it RIDES the swing group (mated in the
    # joints section, not located: the engage swing carries it).
    pinion_arbor = await place_component(
        adapter, "pinion-arbor",
        [APINION_X, APINION_Y, ARBOR_Z0], [0.0, 0.0, 0.0], IDENTITY,
        ground=False, label="pinion-arbor (steel, through the drum)",
    )
    # Rig hold-downs (PR7 items 2/11/12): 4 bright block screws + 2 black foot
    # screws, all base-bolted statics located to the machine datums below.
    block_screws: list[str] = []
    for k, (sx, sz) in enumerate(_BLOCK_SCREW_XZ):
        scr = await place_component(
            adapter, "slotted-screw",
            [sx, BLOCK_TOP_Y, sz], [0.0, 0.0, 0.0], IDENTITY,
            ground=False, label=f"slotted-screw block hold-down {k}",
        )
        block_screws.append(scr)
    foot_screws: list[str] = []
    for tag, (sx, sz), seat_y in (
        ("spring foot", _FOOT_SCREW_XZ[0], Y_BASE_TOP + SPRING_T),
        ("pedestal flange", _FOOT_SCREW_XZ[1], Y_BASE_TOP + ARBOR_PED_FLANGE_T),
    ):
        scr = await place_component(
            adapter, "foot-screw",
            [sx, seat_y, sz], [0.0, 0.0, 0.0], IDENTITY,
            ground=False, label=f"foot-screw ({tag})",
        )
        foot_screws.append(scr)

    # =================== cone cluster (driven, on-solution) ====================
    cone_shaft = await place_component(
        adapter, "cone-gear-shaft",
        cone_station(SHAFT_FRONT_STATION),  # part origin = the front stub end
        [0.0, -INCLINE_DEG, 0.0], ROT_Y_INCLINE, ground=False,
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
        [X_CRANK, Y_CRANK, CRANKSHAFT_Z0], [90.0, 0.0, 0.0], ROT_X_POS90, ground=False,
    )
    pinion = await place_component(
        adapter, "crank-pinion",
        [X_CRANK, Y_CRANK, PINION_TOOTH_Z - PINION_FACE / 2.0],
        [0.0, 0.0, PINION_SEED_DEG], rot_z_rows(PINION_SEED_DEG),  # tooth-in-gap
        ground=False, label="crank-pinion (centred on the 64T contact tooth)",
    )
    removable = await place_component(
        adapter, "transgear-removable",
        [X_CRANK, Y_CRANK, REMOVABLE_Z0], [0.0, 0.0, 0.0], IDENTITY,
        ground=False, configuration="T12",
        label="transgear-removable (crank chain wheel T12)",
    )
    # Crank rest pose: the arm hangs straight DOWN (ch30 eight-views -- the
    # handle reads "down" in all eight roll angles, which only a -Y arm does,
    # since a downward vector lies on the views' vertical rotation axis). The
    # arm part extrudes along its local +X; rot_z(-90) maps that to assembly -Y.
    arm = await place_component(
        adapter, "crank-arm",
        [X_CRANK, Y_CRANK, CRANK_ARM_Z0], [0.0, 0.0, -90.0], rot_z_rows(-90.0),
        ground=False,
    )
    # Handle pivot rides the arm tip, now ARM_C2C below the crankshaft. Its grip
    # axis stays parallel to the crankshaft (ROT_Y_POS90 -> assembly -Z).
    handle = await place_component(
        adapter, "crank-handle",
        [X_CRANK, Y_CRANK - ARM_C2C, CRANK_ARM_Z0], [0.0, 90.0, 0.0], ROT_Y_POS90,
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
        label="crankshaft radial (plate crank axis)", verify=(crankshaft, cs_o),
    )
    # Axial seat vs the plate's CrankAxisSeat plane (perpendicular to the
    # crank axis, anchored at the plate's crank-anchor point -- ON the crank
    # axis, so its machine x is X_CRANK, asserted at import): distance =
    # |Delta z| at the engaged rest pose (both are machine-z-normal planes
    # there).
    _SEAT_M = _plate_local_to_machine(-PLAT_SEAT_ANCHOR[0], PLAT_SEAT_ANCHOR[1])
    _cs_axial = abs(cs_o[2] - _SEAT_M[1])
    await distance_driver(
        adapter,
        named_ref(f"Top Plane@{crankshaft}", "PLANE"),
        named_ref(f"CrankAxisSeat@{platform}", "PLANE"),
        _cs_axial,
        label=f"crankshaft axial d={_cs_axial:.2f} (on the plate)",
        verify=(crankshaft, cs_o),
    )
    # Keyed crank chain: the T12 chain wheel, the 16T pinion and the arm turn
    # rigidly WITH the crankshaft; the handle rides the arm's pivot pin. Each lock
    # is replaced by a SEMANTIC keyed joint -- coaxial + axial seat + an anti-spin
    # -- so the chain shares the crankshaft's single spin DOF with no lock/fix.
    # The suppressible crank ANGLE DRIVER below pins that spin (via the arm).
    crank_axis = named_ref(f"Axis1@{crankshaft}", "AXIS")
    cs_right = named_ref(f"Right Plane@{crankshaft}", "PLANE")

    # T12 chain wheel (IDENTITY): its Right plane is parallel to the crankshaft's
    # at the keyed phase, so a parallel pins the spin (no tuned angle).
    rm_o = await _seat_on_crank(
        adapter, removable, "Axis1", crank_axis, crankshaft, cs_o[2])
    await parallel_mate(
        adapter, named_ref(f"Right Plane@{removable}", "PLANE"), cs_right,
        label="T12 wheel anti-spin (keyed phase)", verify=(removable, rm_o),
    )

    # 16T pinion (placed +half-pitch, tooth-in-gap on the 64T): no plane pair is
    # parallel at that phase, so pin the spin with an ANGLE anti-spin holding the
    # live dihedral between its Right plane and the crankshaft's (~11.25 deg). The
    # pinion origin sits ON the spin axis (flip-recovery can't read it), so a
    # wrong side surfaces as tooth interference, not a silent miss.
    pn_o = await _seat_on_crank(
        adapter, pinion, "Axis2", crank_axis, crankshaft, cs_o[2])
    a_pn = component_transform(adapter, pinion)
    a_cs = component_transform(adapter, crankshaft)
    pin_phase = math.degrees(
        math.acos(max(-1.0, min(1.0, sum(a_pn[k] * a_cs[k] for k in range(3)))))
    )
    await angle_driver(
        adapter, named_ref(f"Right Plane@{pinion}", "PLANE"), cs_right, pin_phase,
        label=f"16T pinion anti-spin (tooth-in-gap a={pin_phase:.2f})",
        verify=(pinion, pn_o),
    )

    # Crank arm (rest pose -Y, rot_z -90): its Top plane is parallel to the
    # crankshaft's Right at the keyed phase. The crank angle driver below pins the
    # arm -- hence the whole keyed chain -- to the assembly.
    arm_o = await _seat_on_crank(
        adapter, arm, "Axis1", crank_axis, crankshaft, cs_o[2])
    await parallel_mate(
        adapter, named_ref(f"Top Plane@{arm}", "PLANE"), cs_right,
        label="crank-arm anti-spin (keyed phase)", verify=(arm, arm_o),
    )

    # Crank handle: rides the arm's PIVOT pin (Axis2@arm), NOT the crankshaft --
    # a real pin joint. Coaxial to the arm pivot bore + an axial seat (its
    # Z-normal Right plane to the assembly Front) + a parallel holding the grip's
    # rest orientation (the grip spin is immaterial, like a lag screw).
    hd_o = _org(adapter, handle)
    await coincident_mate(
        adapter, named_ref(f"Axis1@{handle}", "AXIS"),
        named_ref(f"Axis2@{arm}", "AXIS"),
        label="handle coaxial on arm pivot", verify=(handle, hd_o),
    )
    _hd_axial = abs(hd_o[2] - _SEAT_M[1])
    await distance_driver(
        adapter, named_ref(f"Right Plane@{handle}", "PLANE"),
        named_ref(f"CrankAxisSeat@{platform}", "PLANE"), _hd_axial,
        label=f"handle axial seat d={_hd_axial:.2f} (on the plate)",
        verify=(handle, hd_o),
    )
    await parallel_mate(
        adapter, named_ref(f"Top Plane@{handle}", "PLANE"),
        named_ref(f"Right Plane@{arm}", "PLANE"),
        label="handle anti-spin (grip rest)", verify=(handle, hd_o),
    )

    # =============== cone platform swing (p1 disengage DOF) ==============
    # The platform is the swing bracket: the whole cone set -- post, shaft,
    # gears, tip block -- swings horizontally out of mesh about the plate's
    # tip-end vertical pivot (ch.12, p.18). Pin the floated plate with three
    # locating drivers that leave ONLY the rotation about the pivot axis
    # ("swing pivot", Axis1): a Top-plane distance (upright + height) and the
    # pivot axis's distance to the Right/Front planes (plan X/Z). Then a
    # suppressible ANGLE PARK DRIVER holds today's ENGAGED orientation (the
    # incline dihedral). The riders seat on the plate below and follow the
    # swing, so the validated 20-gear mesh is untouched in `rest`; suppress
    # the angle driver to articulate the disengage.
    plat_o = _org(adapter, platform)
    await seat_signed(
        adapter,
        named_ref(f"Top Plane@{platform}", "PLANE"), "Top Plane",
        plat_o[1],
        label=f"cone-platform height d={plat_o[1]:+.2f}", verify=(platform, plat_o),
    )
    await seat_signed(
        adapter,
        named_ref(f"Axis1@{platform}", "AXIS"), "Right Plane",
        plat_o[0],
        label=f"cone-platform pivot-X d={plat_o[0]:+.2f}", verify=(platform, plat_o),
    )
    await seat_signed(
        adapter,
        named_ref(f"Axis1@{platform}", "AXIS"), "Front Plane",
        plat_o[2],
        label=f"cone-platform pivot-Z d={plat_o[2]:+.2f}", verify=(platform, plat_o),
    )
    # The swing is a FREED operational DOF (user item 1): the park driver is
    # DEFERRED in the default `free` build (recorded, not authored -- the
    # plate swings freely between the gear mesh and the stop screw), authored
    # engaged in a `locked` build. Same mechanism as the crank spin below.
    await angle_driver(
        adapter,
        named_ref(f"Right Plane@{platform}", "PLANE"), named_ref("Right Plane", "PLANE"),
        INCLINE_DEG,
        label=f"cone-platform swing PARK driver (p1, engaged a={INCLINE_DEG:.2f}; "
              f"freed in default build)",
        verify=(platform, plat_o),
        free_dof_key="cone_swing",
    )

    # Pivot post rides the plate -- the frame rocker-support idiom (two
    # flip-free coincidents between named/symmetry planes + one distance):
    # its Top plane seats on the plate's PlateTop datum, its Right plane (the
    # plane through its axis, parallel to the plate's at rest) coincides with
    # the plate's Right plane (the shaft-axis plan line), and a Front-plane
    # distance sets the along-plate station. 6 DOF, no fix/lock; the post
    # follows the p1 swing.
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
        named_ref(f"Right Plane@{pivot_post}", "PLANE"),
        named_ref(f"Right Plane@{platform}", "PLANE"),
        label="cone-post on the plate centreline", verify=(pivot_post, post_o),
    )
    await distance_driver(
        adapter,
        named_ref(f"Front Plane@{pivot_post}", "PLANE"),
        named_ref(f"Front Plane@{platform}", "PLANE"),
        PIVOT_STATION - POST_STATION,
        label=f"cone-post station d={PIVOT_STATION - POST_STATION:.2f}",
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
    # Tip block: positioned BY the shaft it journals -- coaxial on the shaft's
    # axis (which the post + platform already carry) + an axial seat + a
    # parallel anti-spin against the PLATFORM (not the spinning shaft). Its
    # height falls out of the coaxial (bore height + plate = drive height,
    # asserted at import), so its foot lands ON PlateTop with no seat mate --
    # contact, not constraint. It follows the p1 swing through the shaft.
    tb_o = _org(adapter, tip_block)
    tb_axial = abs(sum((tb_o[k] - cone_o[k]) * cone_axis_dir[k] for k in range(3)))
    await coincident_mate(
        adapter,
        named_ref(f"Axis1@{tip_block}", "AXIS"),
        named_ref(f"Axis1@{cone_shaft}", "AXIS"),
        label="tip-block journals the shaft tip", verify=(tip_block, tb_o),
    )
    await distance_driver(
        adapter,
        named_ref(f"Front Plane@{tip_block}", "PLANE"),
        named_ref(f"Front Plane@{cone_shaft}", "PLANE"),
        tb_axial,
        label=f"tip-block axial seat d={tb_axial:.2f}", verify=(tip_block, tb_o),
    )
    await parallel_mate(
        adapter,
        named_ref(f"Right Plane@{tip_block}", "PLANE"),
        named_ref(f"Right Plane@{platform}", "PLANE"),
        label="tip-block anti-spin (rides the plate)", verify=(tip_block, tb_o),
    )
    # --- tip end-play stack (item 5): bushing | adjuster | pinch screw --------
    # The bushing spaces the T006 gear off the block's south face: coaxial on
    # the tip stub + an axial seat off the shaft. Free-spinning in reality; its
    # spin is pinned to the PLATFORM (immaterial, the lag-screw idiom) so the
    # 0-DOF closure proof stays exact. Its Top plane is the axial reference
    # (the part is authored along +Y).
    bush_o = _org(adapter, tip_bushing)
    bush_axial = abs(sum((bush_o[k] - cone_o[k]) * cone_axis_dir[k] for k in range(3)))
    await coincident_mate(
        adapter,
        named_ref(f"Axis1@{tip_bushing}", "AXIS"),
        named_ref(f"Axis1@{cone_shaft}", "AXIS"),
        label="tip-bushing on the tip stub", verify=(tip_bushing, bush_o),
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
    # The adjuster screws into the BLOCK's counterbore: coaxial on the block's
    # journal axis + an axial seat off the block's Front plane + an anti-spin
    # (the pinch screw locks its turn in reality).
    adj_o = _org(adapter, tip_adjuster)
    adj_axial = abs(sum((adj_o[k] - tb_o[k]) * cone_axis_dir[k] for k in range(3)))
    await coincident_mate(
        adapter,
        named_ref(f"Axis1@{tip_adjuster}", "AXIS"),
        named_ref(f"Axis1@{tip_block}", "AXIS"),
        label="adjuster in the block counterbore", verify=(tip_adjuster, adj_o),
    )
    await distance_driver(
        adapter,
        named_ref(f"Top Plane@{tip_adjuster}", "PLANE"),
        named_ref(f"Front Plane@{tip_block}", "PLANE"),
        adj_axial,
        label=f"adjuster axial set d={adj_axial:.2f}", verify=(tip_adjuster, adj_o),
    )
    await parallel_mate(
        adapter,
        named_ref(f"Right Plane@{tip_adjuster}", "PLANE"),
        named_ref(f"Right Plane@{tip_block}", "PLANE"),
        label="adjuster anti-spin (pinch-locked)", verify=(tip_adjuster, adj_o),
    )
    # The pinch screw journals in the block's cross-bore (Axis2, the named
    # "pinch axis"): coaxial + its head seat a half-block off the block's Right
    # plane + an anti-spin.
    pin_o = _org(adapter, pinch_screw)
    await coincident_mate(
        adapter,
        named_ref(f"Axis1@{pinch_screw}", "AXIS"),
        named_ref(f"Axis2@{tip_block}", "AXIS"),
        label="pinch screw in the cross-bore", verify=(pinch_screw, pin_o),
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
        label="pinch-screw anti-spin (slot upright)", verify=(pinch_screw, pin_o),
    )
    # The 64T crank-drive gear and the 20 cone gears are one rigid stepped
    # cluster KEYED to the cone shaft -- each via coaxial + axial seat + parallel
    # anti-spin (see _key_to_shaft), replacing its lock with no fix/lock/tuned
    # angle. The 64T uses its Axis2 central axis, the cone gears their Axis1.
    cone_axis = named_ref(f"Axis1@{cone_shaft}", "AXIS")
    await _key_to_shaft(
        adapter, gear64, "Axis2", cone_axis, cone_shaft, cone_o, cone_axis_dir, "64T",
    )
    for teeth, cg in cone_gears:
        await _key_to_shaft(
            adapter, cg, "Axis1", cone_axis, cone_shaft, cone_o, cone_axis_dir,
            f"cone-gear T{teeth:03d}",
        )
    # 16T pinion (keyed to the crank) drives the 64T -> the cone cluster turns.
    await gear_mate(
        adapter,
        named_ref(f"Axis2@{pinion}", "AXIS"),
        named_ref(f"Axis2@{gear64}", "AXIS"),
        _config.machine("gear_train", "crank_drive_ratio"), label="16T:64T crank drive",
    )

    # The cylinder set is a SANDWICH (book ch.13): brass gears alternate with the
    # black connecting rods, each riding a cam attached to the gear on its right.
    # Those rods/cams live in the channel subassembly, so on the bare arbor each
    # gear sits one stack PITCH from its neighbour (gear face 3 mm + cam to 6.5 ->
    # Z_PITCH ~= 7.06). The axial locator therefore CHAINS each gear off the
    # previous one by that physical pitch -- the real stack relationship, one
    # meaningful constant -- instead of pinning 20 independent absolute coords to
    # the world datum; only gear 0 anchors the stack's reference end. Radially each
    # runs free (coincident, leaving its spin) and meshes its cone gear k at ratio
    # [120-6k : 120] -- the gear mate is the sole rotational constraint, so it holds
    # the tuned tooth phase without nudging the gear (validated keystone, M6).
    prev_cyl: str | None = None
    for j, cyl in enumerate(cyl_gears):
        cyl_o = _org(adapter, cyl)
        await coincident_mate(
            adapter,
            named_ref(f"Axis2@{cyl}", "AXIS"),
            named_ref(f"Axis1@{arbor}", "AXIS"),
            label=f"cylinder-gear {j} radial", verify=(cyl, cyl_o),
        )
        if prev_cyl is None:
            await seat_signed(  # anchor the stack's reference end once
                adapter,
                named_ref(f"Front Plane@{cyl}", "PLANE"),
                "Front Plane",
                cyl_o[2],
                label=f"cylinder-gear {j} axial anchor d={cyl_o[2]:+.2f}",
                verify=(cyl, cyl_o),
            )
        else:
            await distance_driver(  # one sandwich pitch off the previous gear
                adapter,
                named_ref(f"Front Plane@{cyl}", "PLANE"),
                named_ref(f"Front Plane@{prev_cyl}", "PLANE"),
                Z_PITCH,
                label=f"cylinder-gear {j} axial pitch d={Z_PITCH:.2f}",
                verify=(cyl, cyl_o),
            )
        teeth, cg = cone_gears[j]
        await gear_mate(
            adapter,
            named_ref(f"Axis1@{cg}", "AXIS"),
            named_ref(f"Axis2@{cyl}", "AXIS"),
            [teeth, 120], label=f"cone T{teeth:03d}:cyl120 ch{j:02d}",
        )
        prev_cyl = cyl

    # =============== alignment-pinion swing group (p2 engage DOF) ==============
    # The two straps + the pinion drum swing as ONE group on the torque shaft to
    # mesh the cylinder train (ch.25, p.66); parked DISENGAGED (p.68 "gap").
    # Statics first: the pivot blocks, torque shaft and lift rod are base-bolted
    # mounts at IDENTITY -> located to the machine datums (the frame-column
    # idiom; the tilted lever/handle stay fixed, see the placement note).
    for blk in pinion_blocks:
        await _locate_to_datum(adapter, blk)
    await _locate_to_datum(adapter, pivot_shaft)
    await _locate_to_datum(adapter, lift_rod)
    await _locate_to_datum(adapter, spring)
    for scr in block_screws + foot_screws:
        await _locate_to_datum(adapter, scr)
    # Front strap: revolute on the torque shaft (coincident pivot bore + axial
    # seat) -- the swing DOF -- then a suppressible ANGLE PARK DRIVER at the
    # parked lean pins it. Unlike the crank park it stays ENGAGED in `free`
    # builds (the swing is a setup motion, not an operational DOF); the p2
    # mobility probe suppresses it to articulate the engage.
    fb, bb = pinion_brackets["front"], pinion_brackets["back"]
    fb_o = _org(adapter, fb)
    await coincident_mate(
        adapter,
        named_ref(f"Axis1@{fb}", "AXIS"), named_ref(f"Axis1@{pivot_shaft}", "AXIS"),
        label="pinion swing radial", verify=(fb, fb_o),
    )
    await seat_signed(
        adapter,
        named_ref(f"Front Plane@{fb}", "PLANE"), "Front Plane",
        fb_o[2],
        label=f"pinion swing axial d={fb_o[2]:+.2f}", verify=(fb, fb_o),
    )
    swing_park = await angle_driver(
        adapter,
        named_ref(f"Right Plane@{fb}", "PLANE"), named_ref("Right Plane", "PLANE"),
        abs(STRAP_LEAN_DEG),
        label=f"pinion swing PARK driver (p2, disengaged a={abs(STRAP_LEAN_DEG):.2f})",
        verify=(fb, fb_o),
    )
    await mark_park_driver(adapter, swing_park, "pinion_swing")
    # Back strap: the same revolute on the shaft + a parallel anti-spin to the
    # front strap (both inserted at the same lean, so their Right planes are
    # parallel) -- the rigid-group tie, semantic (no lock).
    bb_o = _org(adapter, bb)
    await coincident_mate(
        adapter,
        named_ref(f"Axis1@{bb}", "AXIS"), named_ref(f"Axis1@{pivot_shaft}", "AXIS"),
        label="pinion back strap radial", verify=(bb, bb_o),
    )
    await seat_signed(
        adapter,
        named_ref(f"Front Plane@{bb}", "PLANE"), "Front Plane",
        bb_o[2],
        label=f"pinion back strap axial d={bb_o[2]:+.2f}", verify=(bb, bb_o),
    )
    await parallel_mate(
        adapter,
        named_ref(f"Right Plane@{bb}", "PLANE"), named_ref(f"Right Plane@{fb}", "PLANE"),
        label="pinion back strap anti-spin (rigid with front)", verify=(bb, bb_o),
    )
    # Cam-follower pins: pressed in each strap's tail cross-bore (Axis3), so
    # they RIDE the swing group -- coaxial + the CAM_T_EAST axial split off the
    # strap's Right plane (which contains the bore centre) + a spin pin at the
    # inserted dihedral (the pin is axisymmetric, so the angle is cosmetic, but
    # the DOF must close for the release 0-DOF closure proof).
    for tag in ("front", "back"):
        cpin = cam_pins[tag]
        br = pinion_brackets[tag]
        cp_o = _org(adapter, cpin)
        await coincident_mate(
            adapter,
            named_ref(f"Axis1@{cpin}", "AXIS"), named_ref(f"Axis3@{br}", "AXIS"),
            label=f"cam follower {tag} pressed in the tail bore",
            verify=(cpin, cp_o),
        )
        _split = abs(CAM_PIN_LEN / 2.0 - CAM_T_EAST)
        await distance_driver(
            adapter,
            named_ref(f"Front Plane@{cpin}", "PLANE"),
            named_ref(f"Right Plane@{br}", "PLANE"),
            _split,
            label=f"cam follower {tag} axial split d={_split:.2f}",
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
            math.acos(max(-1.0, min(1.0, sum(a_cp[3 + k] * a_br[6 + k] for k in range(3)))))
        )
        await angle_driver(
            adapter,
            named_ref(f"Top Plane@{cpin}", "PLANE"),
            named_ref(f"Front Plane@{br}", "PLANE"), cp_phase,
            label=f"cam follower {tag} anti-spin (a={cp_phase:.2f})",
            verify=(cpin, cp_o),
        )
    # Pinion drum: journaled in the straps' top bores -- coaxial on the front
    # strap's Axis2 + an axial seat. Its free spin (real: the zeroing input) is
    # pinned by an angle anti-spin at the inserted dihedral vs the leaning strap
    # (the tilted analogue of the 16T's tooth-in-gap anti-spin); riding the
    # strap, the pin survives the engage swing.
    ap_o = _org(adapter, align_pinion)
    await coincident_mate(
        adapter,
        named_ref(f"Axis1@{align_pinion}", "AXIS"), named_ref(f"Axis2@{fb}", "AXIS"),
        label="alignment-pinion journaled in the straps", verify=(align_pinion, ap_o),
    )
    await seat_signed(
        adapter,
        named_ref(f"Front Plane@{align_pinion}", "PLANE"),
        "Front Plane",
        ap_o[2],
        label=f"alignment-pinion axial d={ap_o[2]:+.2f}",
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
        named_ref(f"Right Plane@{fb}", "PLANE"), ap_phase,
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
        named_ref(f"Axis1@{pinion_arbor}", "AXIS"), named_ref(f"Axis2@{fb}", "AXIS"),
        label="pinion arbor journaled in the straps", verify=(pinion_arbor, arb_o),
    )
    await distance_driver(
        adapter,
        named_ref(f"Front Plane@{pinion_arbor}", "PLANE"),
        named_ref("Front Plane", "PLANE"),
        abs(arb_o[2]),
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
    # The crank angle is a FREED operational-DOF park driver (``free_dof_key``). In
    # the default `free` build it is NOT authored -- its resolved spec is recorded
    # and re-authored transiently by the release preflight -- leaving the crank (and
    # the whole keyed/geared train it pins) free to spin: ONE operational DOF, the
    # working kinematic model. A `locked` build authors it engaged and renames it
    # PARK_crank_angle for a fully-defined reproducible snapshot. Compute the BDC
    # dihedral + handle verify target either way (they feed the recorded spec).
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

    # Certify the AS-BUILT model. free -> necessity only (the freed crank DOF is
    # genuinely free; the exact-count closure runs in the release preflight, where
    # the recorded spec is replayed); locked -> strict 0-DOF. All other checks run
    # on the as-built model unchanged.
    if LOCK:
        await assert_expected_free_dof(adapter, 0)
    else:
        # TWO freed operational DOF: the crank spin and the platform swing
        # (both deferred PARK drivers above). Each names its family: the
        # aggregate count alone passes on the crank chain even with the
        # swing pinned (codex review 2026-07-04).
        assert_free_dof_necessity(
            adapter, 2, required_stems=("crankshaft", "cone-swing-platform"))
        write_park_specs(ASM_NAME)
    check_no_interference(adapter)
    return await save_assembly_and_images(adapter, ASM_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
