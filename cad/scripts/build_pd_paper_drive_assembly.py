r"""Reproduction script: paper-drive subassembly (book ch. 22-23, 25).

The orthogonal time-base of the plotter: the platen carries the recording paper
across the pen as the operator turns the crank, driven through the translational
gearing, in machine coordinates (assembly origin = base origin; base top
y = 50.8; the output side is -Z). Rebuilt against the primary references
(memory/paper-drive-rework.md) and the paper-drive geometry contract: ONE
support bar, two-piece column clamps, the hanging platen (guides + locks), the
swinging transgear hanger behind the bar, and the REAL power train:

    crank T12 --(belt/chain feature, 12:24 teeth)--> knob T24
      --(drive collar: two pressed drive pins + cross pin, LOCK)--> knob shaft
      with its integral 12T DP38 --(GEAR mate 12:120)--> 120T DP38 reducer disc
      --(LOCK: brass hub + feed sleeve)--> 12T DP30 feed pinion
      --(RACK-PINION mate, pi*10.16/rev)--> rack --(LOCK)--> platen

Operational kinematics: the crank-end T12 sprocket spin is the ONE free
operational DOF -- drag it and the whole feed train follows at 1.596 mm of
paper per crank revolution (T12/T24 mounted). Every stage is a real SolidWorks
mate on real, geometrically meshed gears. The hanger arm pivots on the bar and
carries the stud, so the 12T:120T mesh is permanent. The crank-spin drive spec
is recorded into the DOF manifest for the transient verify:kinematics replay,
never authored.

* ONE support bar (22 x 9 x 452, book p.62 "the bar that the platen rides on"),
  front face on the platen back, clamped to each column by a FRONT + BACK
  semi-arc pair closed by two long screws whose heads show on the bar front
  (ch30 p002).
* Platen group (HANGS on the bar): platen + two full-width back guide rails
  (above/below the bar band) + 4 lock plates bridging behind the bar (held by
  low button-head guide-lock screws) + the teeth-down rack at the bottom edge
  (crests 2 below the platen edge) + two bright-brass edge clips + the paper
  sheet + ALL its screws -- everything lock-mated to the platen so the whole
  group feeds together.
* Transgear hanger (behind the bar): the arm stands on the pivot spacer and
  swings on the shoulder pivot screw in the bar's tap; the stepped stud in the
  arm carries the feed sleeve (12T DP30), the 120T disc and its brass hub,
  closed by the hub cap. The arm plate, screwed to the arm, bores the knob
  shaft, whose integral 12T meshes the disc; the thrust ring and the knob cup
  (set on a feeler, cross-pinned to the journal) set its end float. On the
  shaft's front core the drive collar (pressed drive pins, cross pin) carries
  the mounted T24 removable CHAIN-WRAPPED at the z -155.7 chain plane, and the
  knurled thumbnut on the shaft's front thread, seated on the collar's pilot,
  retains it free (ch23 p.58/59; R9-70).
* Latch hook: one formed spring-steel piece screwed to the bar's back face;
  the arm's latch pin rides in the round hole in its strip.
* The ANSI #25 roller chain loops both removables (native connected-linkage
  chain component pattern); the 2.8 sprocket plate fits BETWEEN the chain's
  inner plates, so only the roller<->tooth seating is intended contact.
* Spare transgear-removable (T18 chain wheel) stored loose on the base top.

Cross-subassembly fits (checked at the top level): the column-clamp arcs ride
the O25.4 columns (fr-frame.SLDASM); the roller chain spans this sub's knob shaft
and the drive-train crankshaft -- both share the z -155.7 chain plane.

Fix-all strategy (M6.2): every structural component inserted at its exact final
transform and fixed; the platen group and the gear train are left free and
constrained by mates; transforms asserted by read-back; zero interference.

Dimensions: memory/paper-drive-rework.md; cad/DIMENSIONS.md ch. 22-23, 25.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pd_paper_drive_assembly.py
"""

from __future__ import annotations

import math
import sys

from _chain import (
    CENTRELINE_LEN,
    CRANK_CENTRE as CHAIN_CRANK_CENTRE,
    KNOB_CENTRE as CHAIN_KNOB_CENTRE,
    LINK_COUNT,
    LINK_PITCH,
    PIN_HALF_LEN as CHAIN_PIN_HALF_LEN,
    PITCH_R_T12,
    PITCH_R_T24,
    PLATE_HALF_H as CHAIN_PLATE_HALF_H,
    SLACK_R as CHAIN_SLACK_R,
    SPAN_A as CHAIN_SPAN_A,
    SPAN_SLACK as CHAIN_SPAN_SLACK,
    TIP_R_T12,
    TIP_R_T24,
    WRAP_R_A as CHAIN_WRAP_R_A,
    centreline_distance,
    loop_point_tangent,
)
from _check import check, log
from _com import _early_bound
from _custom_properties import apply_custom_properties
from _paths import IN
from _session import run_build
from _drawing_marks import DRAWN_BY
from _assembly import (
    activate_assembly_contract,
    angle_driver,
    author_in_drawing_configurations,
    assembly_title_properties,
    assert_component_placed,
    assert_free_dof_necessity,
    check_no_interference,
    component_names,
    component_origin,
    coincident_mate,
    component_transform,
    distance_driver,
    lock_mate,
    named_ref,
    parallel_mate,
    place_component,
    reledger_to_solved,
    remap_front_to_machine_front,
    reset_dof_manifest,
    save_assembly_and_images,
    write_dof_manifest,
)
from _assembly_couplings import (
    gear_mate,
    rack_pinion_mate,
)
from _assembly_patterns import (
    assert_pattern_targets,
    linear_component_pattern,
    grid_component_pattern,
    PatternDirection,
)
from _chain_mounts import mounted_wheels
from _interference_contracts import allowed_interference_pairs
from _visibility import blank_reference_geometry, visible_reference_geometry
from _transforms import (  # noqa: E402
    IDENTITY,
    ROT_X_NEG90,
    ROT_X_POS90,
    ROT_Y_POS90,
    rot_z_rows,
)
from dt_cone_pivot_post_installation import FRAME_FRONT_COLUMN_Z
from fr_harmonic_base_spec import STACK_HEIGHT as BASE_DECK_Y
from _pd_paper_drive_explode import create_paper_drive_explode
from pd_paper_drive_explode_spec import CLIP_SCREW_ROLE, GUIDE_SCREW_ROLE

ASM_NAME = "pd-paper-drive"

ROT_Y_180 = [[-1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, -1.0]]
ROT_X_180 = [[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]]

# --- machine anchors ---------------------------------------------------------
import pd_latch_hook_geometry as HOOK  # noqa: E402
import pd_support_bar_spec as BAR  # noqa: E402
import pd_transgear_arm_geometry as ARM  # noqa: E402
import pd_transgear_arm_spec as ARM_SPEC  # noqa: E402
from build_pd_support_bar import (  # noqa: E402
    BAR_DEPTH,
    BAR_HEIGHT,
    BAR_LENGTH,
    CLAMP_CBORE_DEPTH,
    CLAMP_CBORE_DIA,
    CLAMP_HEAD_RECESS,
    CLAMP_HOLE_DIA,
    CLAMP_HOLE_X,
)
from sh_column_clamp_front_geom import ARC_DEPTH as ARC_FRONT_DEPTH  # noqa: E402
from build_sh_column_clamp_back import (  # noqa: E402
    DEPTH as ARC_BACK_DEPTH,
    HOLE_SPEC as CLAMP_RECEIVER_SPEC,
)

COLUMN_X = 197.0
COLUMN_Z = FRAME_FRONT_COLUMN_Z
# Depth chain: the front arc's front face (-129.9) carries the bar's back
# face; the bar's front face (-138.9) carries the platen's back face.
BAR_BACK_Z = COLUMN_Z - ARC_FRONT_DEPTH  # -129.9
BAR_FRONT_Z = BAR_BACK_Z - BAR_DEPTH  # -138.9
BAR_Z = (BAR_FRONT_Z + BAR_BACK_Z) / 2.0  # -134.4 bar centre

# --- platen (hangs on the bar) ----------------------------------------------
from pd_platen_spec import (  # noqa: E402
    CBORE_DEPTH as PLATEN_CBORE_DEPTH,
    CBORE_DIA as PLATEN_CBORE_DIA,
    GUIDE_HOLE_DIA as PLATEN_GUIDE_HOLE_DIA,
    GUIDE_HOLE_X as PLATEN_GUIDE_HOLE_X,
    GUIDE_HOLE_Y as PLATEN_GUIDE_HOLE_Y,
    HEAD_RECESS as PLATEN_HEAD_RECESS,
    PLATE_HEIGHT,
    PLATE_THICKNESS,
    PLATE_WIDTH,
    SOCKET_SPEC as PLATEN_SOCKET_SPEC,
    SOCKET_THREAD_ENGAGEMENT as PLATEN_SOCKET_ENGAGEMENT,
    SOCKET_XY as PLATEN_SOCKET_XY,
)
from build_pd_platen_guide import (  # noqa: E402
    GUIDE_DEPTH,
    GUIDE_HEIGHT,
    GUIDE_LENGTH,
    GUIDE_SCREW_BOTTOM_CLEARANCE,
    GUIDE_SCREW_PASSAGE,
    GUIDE_SCREW_THREAD_ENGAGEMENT,
    HOLE_X as GUIDE_LOCK_HOLE_X,
    LOCK_SCREW_PASSAGE,
    LOCK_SCREW_THREAD_ENGAGEMENT,
    LOCK_SCREW_TIP_INSIDE_MIN,
    LOCK_STATION_X,
    SCREW_STATION_X as GUIDE_SCREW_STATION_X,
)
from build_pd_guide_lock import (  # noqa: E402
    HOLE_DIA as LOCK_HOLE_DIA,
    LOCK_HEIGHT,
    LOCK_THICK,
    LOCK_WIDTH,
)

# The printed bands the lock-station sweep judges the platen's lock stack at:
# the same spec constants the guide and lock builds author on their model
# dimensions, so the sheets and the sweep read one source.
from _fit_deviations import deviations  # noqa: E402
from _printed_tolerance import printed_band_mm, printed_deviations  # noqa: E402
from pd_guide_lock_spec import (  # noqa: E402
    DRAWING_PRECISION_BY_NAME as LOCK_PRECISION,
    HOLE_XY as LOCK_HOLE_XY,
    LOCK_HEIGHT_BAND,
    RAIL_EDGE_LIP as LOCK_RAIL_LIP,
)
from pd_platen_guide_spec import (  # noqa: E402
    GUIDE_DEPTH_BAND,
    GUIDE_DEPTH_PLACES,
    LOCK_GAP_FIT,
)
from build_pd_platen_clip import (  # noqa: E402
    CLIP_LENGTH,
    CLIP_THICKNESS,
    HOLE_INSET as CLIP_HOLE_INSET,
    HOLE_Y as CLIP_HOLE_Y,
    HOLE_DIA as CLIP_HOLE_DIA,
    SCREW_SEAT_BOSS_H,
    SCREW_SEAT_DIA,
    SCREW_SEAT_STACK,
)
from vn_clamp_screw_spec import (  # noqa: E402
    HEAD_DIA as CLAMP_SCREW_HEAD_DIA,
    HEAD_H as CLAMP_SCREW_HEAD_H,
    SHANK_DIA as CLAMP_SCREW_DIA,
    SHANK_LEN as CLAMP_SCREW_LEN,
)
from vn_fillister_screw_spec import (  # noqa: E402
    HEAD_DIA as FILLISTER_HEAD_DIA,
    HEAD_H as FILLISTER_HEAD_H,
    SHANK_DIA as FILLISTER_SHANK_DIA,
    SHANK_LEN as FILLISTER_SHANK_LEN,
)

# The guide-lock screws alone are low button heads (R9-31): a fillister head
# on the lock back would sweep into the hanger arm as the platen feeds
# (_assert_lock_station_sweep).
from vn_guide_lock_screw_spec import (  # noqa: E402
    HEAD_DIA as LOCK_SCREW_HEAD_DIA,
    HEAD_H as LOCK_SCREW_HEAD_H,
    LOCK_SET_EDGE_REACH,
    SHANK_DIA as LOCK_SCREW_SHANK_DIA,
    SHANK_LEN as LOCK_SCREW_SHANK_LEN,
)
from _platen_rack_geometry import (  # noqa: E402
    ADDENDUM as RACK_ADDENDUM,
    BAR_HEIGHT as RACK_BAR_HEIGHT,
    BAR_LENGTH as RACK_BAR_LENGTH,
    BAR_THICKNESS as RACK_BAR_THICKNESS,
    FIRST_GAP_X as RACK_FIRST_GAP_X,
    PITCH as RACK_PITCH,
)
from build_pd_platen_paper import (  # noqa: E402
    PAPER_HEIGHT,
    PAPER_WIDTH,
)

PLATE_X0_PHOTO = -33.213
# ch30-p002 Pose Studio refit (2026-07-23): the platen's top-left reference
# corner was hand-aligned at (-33.213, 408.054) in the current assembly. The
# width is 300 * 0.8988 and the user-confirmed H:W ratio is 1:2, so preserving
# that top edge puts the resized plate bottom here. The fit's z delta remains
# ignored: a near-front view does not constrain depth. The placed PLATE_X0 is
# this photo x snapped to the rack's mesh phasing (below, after the stud).
PLATE_Y0 = 273.234
PLATE_FRONT_Z = BAR_FRONT_Z - PLATE_THICKNESS  # -142.75

# The platen hangs: the bar's top edge carries the top guide's underside.
GUIDE_Y = (283.734, 317.734)  # bottom / top rail seats (machine y)
BAR_TOP_Y = GUIDE_Y[1]
BAR_CY = BAR_TOP_Y - BAR_HEIGHT / 2.0
LOCK_Z0 = BAR_FRONT_Z + GUIDE_DEPTH  # -128.9: lock plates on the guide backs,
# 1.0 behind the bar's back face -- they bridge the bar so the platen cannot
# fall off it.

# Rack: teeth-down at the platen's bottom edge, crests protruding 2.25 below it
# (R9-62: 0.25 deeper than the first 2.00, which set the feed mesh at e 0.80).
RACK_TIP_Y = PLATE_Y0 - 2.25  # 270.984
RACK_PITCH_Y = RACK_TIP_Y + RACK_ADDENDUM  # 271.8307
RACK_Y0 = RACK_TIP_Y + RACK_BAR_HEIGHT  # 282.984 (Rx180: local y 0..12 maps down)
RACK_BACK_Z = BAR_FRONT_Z + RACK_BAR_THICKNESS  # -132.9 (on the platen back)

# --- transgear (the real six-gear train) -------------------------------------
from pd_rack_pinion_spec import (  # noqa: E402
    DIAMETRAL_PITCH as DISC_DP,
    FACE_WIDTH as DISC_FACE,
    TEETH as DISC_TEETH,
)
from pd_transgear_feed_pinion_spec import (  # noqa: E402
    DIAMETRAL_PITCH as FEED_DP,
    FACE_WIDTH as FEED_FACE,
    TEETH as FEED_TEETH,
)
import dt_crankshaft_spec  # noqa: E402
import pd_rack_pinion_spec as DISC_SPEC  # noqa: E402
import pd_transgear_arm_plate_geometry as ARM_PLATE  # noqa: E402
import pd_transgear_arm_plate_spec as ARM_PLATE_SPEC  # noqa: E402
import vn_transgear_arm_plate_screw_spec as PLATE_SCREW  # noqa: E402
import vn_transgear_collar_cross_pin_spec as CROSS_PIN  # noqa: E402
import transgear_cluster_fit as CLUSTER  # noqa: E402
import pd_transgear_disc_hub_geometry as DISC_HUB_GEOM  # noqa: E402
import pd_transgear_disc_hub_spec as DISC_HUB  # noqa: E402
import vn_transgear_disc_screw_spec as DISC_SCREW  # noqa: E402
import pd_transgear_drive_collar_spec as COLLAR  # noqa: E402
import pd_transgear_feed_pinion_spec as FEED  # noqa: E402
import pd_transgear_front_bushing_spec as FRONT_BUSHING  # noqa: E402
import transgear_hanger_joints as HANGER  # noqa: E402
import vn_transgear_knob_cup_pin_spec as CUP_PIN  # noqa: E402
import pd_transgear_knob_cup_spec as CUP  # noqa: E402
import pd_transgear_knob_thrust_ring_spec as RING  # noqa: E402
import vn_transgear_latch_pin_spec as LATCH_PIN  # noqa: E402
import pd_transgear_pin_spec as PIN  # noqa: E402
import vn_transgear_pivot_screw_spec as PIVOT_SCREW  # noqa: E402
import pd_transgear_pivot_spacer_spec as SPACER  # noqa: E402
import vn_transgear_pivot_spring_spec as PIVOT_SPRING  # noqa: E402
import pd_transgear_rear_bushing_spec as REAR_BUSHING  # noqa: E402
import vn_transgear_retaining_ring_spec as E_RING  # noqa: E402
import vn_latch_hook_bracket_screw_spec as HOOK_BRACKET_SCREW  # noqa: E402
import pd_latch_hook_spec as HOOK_SPEC  # noqa: E402

FEED_PD = FEED_TEETH / FEED_DP * IN  # 10.16 -- meshes the DP30 rack
# Centre extension of the feed-pinion/rack mesh (R9-62): 0.55, contact ratio
# 1.25; the hook's pin hole is match-drilled at the mesh the fit-up sets. The
# sleeve's teeth are cut to the 1.25/P root (root relief), so the rack crests
# clear the gap floors; the bound is the rack's tip corners on the form-cut
# flank, clear from e 0.52
# (pd_paper_drive_assembly_steps.feed_mesh_penetration, R9-62a).
RACK_MESH_EXT = 0.55
# The stud S sits on machine x 0; its y is the feed pinion's mesh line under
# the rack. The arm's printed stud station is |S - P| from the MHA-VN-041 pivot
# tap P in the bar.
STUD_X = 0.0
STUD_XY = (STUD_X, RACK_PITCH_Y - FEED_PD / 2.0 - RACK_MESH_EXT)
PIVOT_XY = (BAR.PIVOT_TAP_X, BAR_CY + BAR.HANGER_TAP_Y)  # (-58, 303.234)
if (
    abs(math.dist(STUD_XY, PIVOT_XY) - ARM.PIN_STATION)
    > 0.5 * 10.0**-ARM_SPEC.STATION_PLACES
):
    raise AssertionError("the stud is off the arm's printed station from the pivot")
# The hanger's frame: U runs from the pivot P through the stud S, N is U
# turned +90 deg in the machine XY plane. The arm, its plate and the latch pin
# are printed in (station along U, offset along N) from P.
_ARM_REACH = math.dist(STUD_XY, PIVOT_XY)
ARM_U = (
    (STUD_XY[0] - PIVOT_XY[0]) / _ARM_REACH,
    (STUD_XY[1] - PIVOT_XY[1]) / _ARM_REACH,
)
ARM_N = (-ARM_U[1], ARM_U[0])
ARM_ANGLE_DEG = math.degrees(math.atan2(ARM_U[1], ARM_U[0]))  # -32.56


def _on_arm(station: float, offset: float = 0.0) -> tuple[float, float]:
    """Machine xy of the hanger-frame point ``P + station*U + offset*N``."""
    return (
        PIVOT_XY[0] + station * ARM_U[0] + offset * ARM_N[0],
        PIVOT_XY[1] + station * ARM_U[1] + offset * ARM_N[1],
    )


# The knob axis K: the permanent 12T:120T DP38 mesh puts it the disc's
# CENTRE_DISTANCE from the stud, at MESH_ANGLE (a multiple of the disc's 3-deg
# tooth pitch, knob swung low toward the crank at machine -X). The arm plate's
# printed bore datum must land on it.
MESH_ANGLE_DEG = -168.0
KNOB_SHAFT_XY = (
    STUD_XY[0] + DISC_SPEC.CENTRE_DISTANCE * math.cos(math.radians(MESH_ANGLE_DEG)),
    STUD_XY[1] + DISC_SPEC.CENTRE_DISTANCE * math.sin(math.radians(MESH_ANGLE_DEG)),
)  # machine (-43.788, 256.893)
_PLATE_BORE_XY = _on_arm(ARM_PLATE.BORE_STATION, ARM_PLATE.BORE_OFFSET)
if math.dist(KNOB_SHAFT_XY, _PLATE_BORE_XY) > 1e-3:
    raise AssertionError(
        f"arm plate bore {_PLATE_BORE_XY} is off the knob mesh axis {KNOB_SHAFT_XY}"
    )

# z stack of the hanger (front -Z -> back). It stands behind the bar's back
# face on the pivot spacer, so the arm clears the sliding guide-lock stations
# (_assert_lock_station_sweep).
SPACER_Z0 = BAR_BACK_Z  # -129.9: spacer pressed flush on the shoulder's end
ARM_Z0 = ARM.FRONT_FACE_MACHINE_Z  # -124.4: arm front face on the spacer
if abs(SPACER_Z0 + SPACER.LENGTH - ARM_Z0) > 1e-9:
    raise AssertionError("the arm's front face is off the pivot spacer's rear face")
# Shoulder screw MHA-VN-041 (Rx+90: shank to -Z): the shoulder bottoms on the
# bar's back face; under its head the MHA-VN-049 spring (identity: its O.D. rim
# on the arm's spot-face floor, its I.D. rim under the head) holds the arm
# on the spacer.
PIVOT_SCREW_Z0 = BAR_BACK_Z + PIVOT_SCREW.SHOULDER_LEN  # -117.2 under the head
PIVOT_SPRING_Z0 = ARM_Z0 + ARM.SPOT_FACE_FLOOR_FROM_FRONT  # -118.0
# Arm plate (rows Rz(theta): local X along U): its mounting plane on
# the arm's rear face; hub forward to the thrust ring, boss rearward.
PLATE_Z0 = ARM_Z0 + ARM.THICKNESS  # -116.4625
PLATE_SCREW_XY = tuple(_on_arm(station) for station in ARM.PLATE_TAP_STATIONS)
PLATE_SCREW_Z0 = PLATE_Z0 + ARM_PLATE.REAR_FACE_Z  # -111.4625: oval heads flush
# Latch pin MHA-VN-042 pressed to the floor of the arm tip's hole, along U
# (rows Rz(theta - 90): the dowel's local +Y along U).
LATCH_PIN_POS = (
    *_on_arm(ARM.TIP_STATION - ARM.PIN_HOLE_DEPTH),
    ARM.PIN_MACHINE_Z,
)  # (45.543, 237.121, -120.431)
# The hook's arm lies square to the hanger's latched direction, its strip's
# mid-plane crossing the pin's axis at PIN_AXIS_XY, HOLE_STATION from P.
if abs(HOOK.ARM_ANGLE_DEG - ARM_ANGLE_DEG) > 1e-9:
    raise AssertionError("the latch hook is formed to another hanger angle")
if math.dist(HOOK.PIN_AXIS_XY, _on_arm(HOOK.HOLE_STATION)) > 1e-9:
    raise AssertionError("the latch hook's pin crossing is off the arm's line")
# The pin's axis passes inside the hook's round pin hole (square to it, so
# the pin's section is a circle on the hole's), and the largest pin bears on
# the hole's lower (-N) edge: the latched hanger rests there with the feed
# pinion in the rack.
_pin_hole_offset = math.dist(HOOK.PIN_AXIS_XY, HOOK.PIN_HOLE_XY)
if abs(HOOK.PIN_HOLE_Z - ARM.PIN_MACHINE_Z) > 1e-9:
    raise AssertionError("the latch hook's pin hole is off the pin's height")
if _pin_hole_offset + LATCH_PIN.DIA_MAX / 2.0 > HOOK.PIN_HOLE_DIA / 2.0 + 1e-9:
    raise AssertionError(
        f"latch pin axis is {_pin_hole_offset:.3f} off the hook's pin hole centre"
    )
_pin_hole_n = (HOOK.PIN_HOLE_XY[0] - HOOK.PIN_AXIS_XY[0]) * ARM_N[0] + (
    HOOK.PIN_HOLE_XY[1] - HOOK.PIN_AXIS_XY[1]
) * ARM_N[1]
if abs(_pin_hole_n - _pin_hole_offset) > 1e-9 or (
    abs(_pin_hole_n + LATCH_PIN.DIA_MAX / 2.0 - HOOK.PIN_HOLE_DIA / 2.0) > 1e-6
):
    raise AssertionError(
        "the largest latch pin does not bear on the hook hole's lower edge"
    )

# Disc cluster on the pin MHA-PD-023 at S (R9-68).  The pin is pressed into the
# arm, its head on the arm's rear face (Ry180: its stations run to machine
# -Z).  On it, rear to front: the MHA-PD-024 rear bushing on the arm's front
# face, the MHA-PD-010 feed sleeve (the disc on its round boss, its front face
# at the D-flat's end wall where the hub's D-bore bears, screwed together),
# the MHA-PD-025 front bushing on the sleeve's nose and the MHA-VN-047 ring in the
# pin's groove.  Both bushings and the hub are
# faced to fit (transgear_cluster_fit); the model carries them as fitted to
# nominal parts, the cluster rearward with its float open at the ring.
PIN_Z0 = PIN.HEAD_SEAT_MACHINE_Z  # -116.4625: the head's underside (Ry180)
if abs(PIN_Z0 - (ARM_Z0 + ARM.THICKNESS)) > 1e-9:
    raise AssertionError("the pin's head is off the arm's rear face")
REAR_BUSHING_Z0 = CLUSTER.REAR_BUSHING_REAR_Z  # -124.4 (Ry180, to -130.4)
if abs(REAR_BUSHING_Z0 - ARM_Z0) > 1e-9:
    raise AssertionError("the rear bushing is off the arm's front face")
FEED_Z0 = REAR_BUSHING_Z0 - REAR_BUSHING.LENGTH  # -130.4 (Ry180, teeth to -144.0)
DISC_Z0 = FEED_Z0 - FEED.DISC_FRONT_STATION  # -147.65: on the hub spigot's flange
if abs(DISC_Z0 - CLUSTER.DISC_FRONT_Z) > 1e-9:
    raise AssertionError("the disc is off the cluster fit's station")
_DISC_SCREW_R = DISC_HUB_GEOM.BOLT_CIRCLE_DIA / 2.0
DISC_SCREW_XY = tuple(
    (
        STUD_XY[0] + _DISC_SCREW_R * math.cos(math.radians(angle)),
        STUD_XY[1] + _DISC_SCREW_R * math.sin(math.radians(angle)),
    )
    for angle in DISC_HUB_GEOM.SCREW_ANGLES_DEG
)
DISC_SCREW_Z0 = DISC_Z0 - DISC_HUB.FLANGE_THICK  # -150.05: heads on the flange
FRONT_BUSHING_Z0 = FEED_Z0 - FEED.OVERALL_LENGTH  # -157.75 (Ry180, to -162.78)
if abs(FRONT_BUSHING_Z0 - CLUSTER.FRONT_BUSHING_REAR_Z) > 1e-9:
    raise AssertionError("the front bushing is off the sleeve's nose")
# The hub's front face, faced to fit HUB_NOSE_WINDOW behind the sleeve's
# nose, so the front bushing bears on the steel nose and traps hub and disc.
HUB_FRONT_Z = DISC_Z0 + DISC_HUB.HUB_FRONT_Z
if abs(HUB_FRONT_Z - CLUSTER.HUB_FRONT_Z) > 1e-9:
    raise AssertionError("the hub's front face is off the cluster fit's station")
if abs(DISC_Z0 + DISC_HUB_GEOM.SPIGOT_LENGTH - CLUSTER.STEP_Z) > 1e-9:
    raise AssertionError("the hub's spigot end is off the sleeve's step face")
if not (
    CLUSTER.HUB_NOSE_WINDOW[0]
    <= HUB_FRONT_Z - FRONT_BUSHING_Z0
    <= CLUSTER.HUB_NOSE_WINDOW[1]
):
    raise AssertionError("the hub's front face is off the sleeve nose's window")
if abs(CLUSTER.RING_FRONT_Z - (PIN_Z0 - PIN.GROOVE_STATION)) > 1e-9:
    raise AssertionError("the ring is off the pin groove's load wall")

import vn_transgear_knob_drive_pin_spec as KNOB_PIN  # noqa: E402
import pd_transgear_removable_spec as REMOVABLE  # noqa: E402
import pd_transgear_knob_shaft_spec as KNOB_SPEC  # noqa: E402
from pd_transgear_thumbnut_spec import (  # noqa: E402
    FLANGE_DIA as THUMBNUT_FLANGE_DIA,
    HEAD_DIA as THUMBNUT_HEAD_DIA,
    OVERALL_LENGTH as THUMBNUT_LEN,
    THREAD as THUMBNUT_THREAD,
)

# The knob shaft's integral 12T DP38 is the third gear.
THIRD_TEETH = KNOB_SPEC.TEETH
THIRD_DP = KNOB_SPEC.DIAMETRAL_PITCH
THIRD_FACE = KNOB_SPEC.FACE_WIDTH


# Both mounted removables (knob T24, crank T12) share ONE band: front face
# BAND_FRONT_Z, rear face on the seat face SEAT_FACE_Z (the knob's drive collar,
# the crankshaft's seat collar), and the chain mid-plane between
# (pd_transgear_removable_spec). Each is placed on its FRONT face (the part's
# Front Plane), identity: holes on machine +/-Y.
REMOVABLE_Z0 = REMOVABLE.BAND_FRONT_Z  # -157.1
T24_MID_Z = REMOVABLE.CHAIN_MID_Z  # -155.7
CHAIN_MID_Z = REMOVABLE.CHAIN_MID_Z  # both wheels coplanar; the crank T12 matches
REMOVABLE_TIP_R = {
    name: REMOVABLE.outside_dia(teeth) / 2.0 for name, teeth in REMOVABLE.CONFIGS
}
# Belt/chain coupling diameters: the per-tooth effective N * p / pi, so the
# typed ratio is the EXACT tooth ratio a roller chain transmits.
CHAIN_PULLEY_DIA = {
    name: teeth * REMOVABLE.CHAIN_PITCH / math.pi for name, teeth in REMOVABLE.CONFIGS
}
if REMOVABLE.PIN_HOLE_ANGLES_DEG != (90.0, 270.0):
    raise AssertionError("identity-placed removables expect pin holes on +/-Y")

# Knob stack on K (front -> back): thumbnut | T24 | drive collar | the
# shaft's 12T | thrust ring | arm-plate hub | plate | boss | knob cup. The
# collar MHA-PD-022 seats its front face on the T24's rear face (the band's seat
# face) and is set SET_NOMINAL in front of the shaft's 12T front face F, the
# shaft's datum (identity + spin: local +Z runs to the knob at the back).
KNOB_COLLAR_Z0 = REMOVABLE.SEAT_FACE_Z  # -154.3
KNOB_SHAFT_Z0 = KNOB_COLLAR_Z0 + COLLAR.SET_NOMINAL  # F = -148.1
KNOB_COLLAR_REAR_Z = KNOB_COLLAR_Z0 + COLLAR.LENGTH  # -150.3
# The two MHA-VN-038 dowels pressed through the collar's holes (Rx-90: pin +Y ->
# -Z), rounded ends DRIVE_PIN_PROUD in front of it, in the wheel's pin holes.
KNOB_DRIVE_PIN_Z0 = REMOVABLE.DRIVE_PIN_TIP_Z + KNOB_PIN.LENGTH  # -151.9375
KNOB_DRIVE_PIN_XY = tuple(
    (KNOB_SHAFT_XY[0], KNOB_SHAFT_XY[1] + side * COLLAR.PIN_CIRCLE_RADIUS)
    for side in (1.0, -1.0)
)  # +Y first: DrivePinAxis1
if abs(KNOB_COLLAR_Z0 - REMOVABLE.DRIVE_PIN_TIP_Z - COLLAR.DRIVE_PIN_PROUD) > 1e-9:
    raise AssertionError("knob drive-pin tips are off the collar's DRIVE_PIN_PROUD")
if abs(KNOB_PIN.DIA - REMOVABLE.DRIVE_PIN_DIA) > 1e-12:
    raise AssertionError("transgear-knob-drive-pin is not the removable's drive pin")
if COLLAR.PIN_CIRCLE_RADIUS != REMOVABLE.PIN_CIRCLE_RADIUS:
    raise AssertionError("the collar's pin circle is not the removable's")
# MHA-VN-037 spring pin across the collar's rear slot (identity: along machine X).
CROSS_PIN_Z0 = KNOB_COLLAR_Z0 + COLLAR.CROSS_HOLE_Z  # -151.3
# Behind the 12T: the thrust ring to the plate hub's face, the knob cup on the
# journal's rear end END_FLOAT behind the plate's boss (all Rx+90), and the
# MHA-VN-048 spring pin through cup and journal (identity: along machine X,
# R9-70 K-1).
KNOB_RING_Z0 = KNOB_SHAFT_Z0 + KNOB_SPEC.FACE_WIDTH  # -142.2
if abs(KNOB_RING_Z0 + RING.LENGTH - (PLATE_Z0 + ARM_PLATE.HUB_FACE_Z)) > 1e-9:
    raise AssertionError("the thrust ring does not reach the arm plate's hub face")
KNOB_CUP_Z0 = KNOB_SHAFT_Z0 + KNOB_SPEC.CUP_FACE_Z  # -107.7625
KNOB_CUP_REAR_Z = KNOB_CUP_Z0 + CUP.LENGTH  # -99.7625
KNOB_SHAFT_REAR_Z = KNOB_SHAFT_Z0 + KNOB_SPEC.REAR_END_Z  # -101.2625
KNOB_CUP_PIN_Z0 = KNOB_CUP_Z0 + CUP.PIN_HOLE_FROM_FRONT  # -104.7625
if not KNOB_CUP_Z0 < KNOB_SHAFT_REAR_Z < KNOB_CUP_REAR_Z:
    raise AssertionError("the knob shaft's rear end is not inside the knob cup")
if not KNOB_CUP_PIN_Z0 + CUP_PIN.HOLE_MAX / 2.0 < KNOB_SHAFT_REAR_Z:
    raise AssertionError("the knob cup's pin hole runs off the journal's end")

# R9-68, the bushings faced to fit.  F carries the disc: with the knob shaft
# rearward and the cluster forward, the fit-up sets the disc's front face m
# (transgear_cluster_fit.FIT_WINDOW) behind F by facing the front bushing,
# so the pin's and sleeve's own stations drop out of every chain from F.
# The model sits at the window's centre on the nominal chain.
_F_FROM_ARM_Z = (
    ARM_Z0 + ARM.THICKNESS + ARM_PLATE.HUB_FACE_Z - RING.LENGTH - KNOB_SPEC.FACE_WIDTH
)
if abs(_F_FROM_ARM_Z - KNOB_SHAFT_Z0) > 1e-9 or abs(CLUSTER.F_Z - KNOB_SHAFT_Z0) > 1e-9:
    raise AssertionError("F is off the arm, plate hub and thrust ring chain")
if abs(DISC_Z0 - CLUSTER.FLOAT_WINDOW_CENTRE - KNOB_SHAFT_Z0 - CLUSTER.MODEL_M) > 1e-9:
    raise AssertionError("the model's disc is off the knob chain's fitted station")
# The 120T disc's rear face (the MHA-VN-039 tips sit inside it) to the platen's
# front face at the printed worst case: the platen forward by its fitted
# float, magnified by its yaw about the bar's end at the near lock; F
# rearward by the arm (held on the longest spacer by the MHA-VN-049 spring), the
# arm, hub face, ring and 12T bands; the platen forward by the bar and its
# own bands; then m's max, the cluster's rearward float, its tilt on the bore
# clearance (pivot on the rear bushing's smallest Ø9, over the shortest
# sleeve) at the disc rim, the hanger's tilt on the spacer (Codex P1 on
# 6c385465d) at the rim's farthest point from P, and the disc's wobble on its
# mount (DISC_MOUNT_WOBBLE).
PLATEN_YAW_LEVER = (BAR_LENGTH / 2.0) / (BAR_LENGTH / 2.0 - LOCK_STATION_X[0])
# The platen (4.0) and rack bar (6.0) carry no drawing band: .XXX assumed.
_PLATEN_THICKNESS_BAND = printed_band_mm(3)
_RACK_THICKNESS_BAND = printed_band_mm(3)
DISC_PLATEN_NOMINAL = PLATE_FRONT_Z - KNOB_SHAFT_Z0 - DISC_SPEC.FACE_WIDTH  # 2.35
DISC_PLATEN_BAND = (
    SPACER.LENGTH_BAND
    + ARM.THICKNESS_BAND
    + ARM_PLATE.HUB_FACE_TO_MOUNTING_BAND
    + RING.LENGTH_TOL
    + printed_band_mm(KNOB_SPEC.FACE_WIDTH_PLACES)
    + (DISC_SPEC.FACE_WIDTH_MAX - DISC_SPEC.FACE_WIDTH)
    + BAR.BAR_DEPTH_BAND
    + _PLATEN_THICKNESS_BAND
)  # 0.7762
CLUSTER_TILT_AT_DISC_RIM = (
    (
        DISC_SPEC.OUTSIDE_DIA
        - (REAR_BUSHING.OD - printed_band_mm(REAR_BUSHING.OD_PLACES))
    )
    / 2.0
    * CLUSTER.BORE_DIAMETRAL_CLEARANCE[1]
    / (FEED.OVERALL_LENGTH - FEED.STATION_TOL)
)  # 0.0510
# The hanger tilts about P by the spacer's face squareness
# (transgear_hanger_joints.HANGER_TILT): a point r from P moves r times it.
_P_TO_S = math.dist(PIVOT_XY, STUD_XY)  # 68.81
HANGER_TILT_AT_DISC_RIM = HANGER.HANGER_TILT * (
    _P_TO_S + DISC_SPEC.OUTSIDE_DIA / 2.0
)  # 0.2588
HANGER_TILT_AT_FEED_TIPS = HANGER.HANGER_TILT * (
    _P_TO_S + FEED.OUTSIDE_DIA / 2.0
)  # 0.1765
# The disc's rear face at its rim against the sleeve's axis: the hub rocking
# on the boss (it is trapped with float, never preloaded onto the step) over
# its shortest round engagement, levered from its step contact; then, each
# zone scaled from its diameter to the rim, the sleeve's step face square to
# its bore, the hub's spigot end and flange rear face square to its bore,
# and the disc's rear face parallel to its front (clamp) face.
_DISC_RIM_R = DISC_SPEC.OUTSIDE_DIA / 2.0
DISC_HUB_ROCK_AT_RIM = (
    (_DISC_RIM_R - DISC_HUB.SEAT_CONTACT_R)
    * DISC_HUB.BOSS_CLEARANCE
    / DISC_HUB.ROUND_ENGAGEMENT_MIN
)  # 0.0624
DISC_MOUNT_WOBBLE = (
    DISC_HUB_ROCK_AT_RIM
    + _DISC_RIM_R
    * FEED.STEP_FACE_PERPENDICULARITY
    / FEED.STEP_FACE_PERPENDICULARITY_ZONE_DIA
    + _DISC_RIM_R
    * DISC_HUB.SPIGOT_END_PERPENDICULARITY
    / DISC_HUB.SPIGOT_END_PERPENDICULARITY_ZONE_DIA
    + _DISC_RIM_R
    * DISC_HUB.FLANGE_FACE_PERPENDICULARITY
    / DISC_HUB.FLANGE_FACE_PERPENDICULARITY_ZONE_DIA
    + float(DISC_SPEC.GEOMETRIC_TOLERANCES_MM["disc rear face parallelism to front"])
)  # 0.1956
# The least air the disc's rear face keeps to the platen's front (R9-68).
DISC_PLATEN_AIR_MIN = 0.03
DISC_PLATEN_AIR_WORST = (
    DISC_PLATEN_NOMINAL
    - DISC_PLATEN_BAND
    - LOCK_GAP_FIT[1] * PLATEN_YAW_LEVER
    - CLUSTER.FIT_WINDOW[1]
    - CLUSTER.FLOAT_WINDOW[1]
    - CLUSTER_TILT_AT_DISC_RIM
    - HANGER_TILT_AT_DISC_RIM
    - DISC_MOUNT_WOBBLE
)
if DISC_PLATEN_AIR_WORST < DISC_PLATEN_AIR_MIN:
    raise AssertionError(
        "MHA-PD-006 disc rear face comes within the platen front face's "
        f"{DISC_PLATEN_AIR_MIN} at the printed worst case: air "
        f"{DISC_PLATEN_AIR_WORST:.4f} (R9-47, R9-68)"
    )
# R9-67/R9-68: the feed sleeve's 12T cuts full depth from its rear face over
# the rack's whole width.  The rack's front face is the platen's back face, so
# the stack above sets how far forward of the sleeve's rear face it reaches,
# less the terms that do not lie between the sleeve and the platen's back
# (the platen's own band, the disc's mount wobble, the rim's tilts, which
# come back as the tilts at the 12T tips).  The disc's front face is the hub
# flange's rear face, a spigot length ahead of the sleeve's step; the stack's
# thickest disc reaches rearward from it.
CLUSTER_TILT_AT_FEED_TIPS = (
    (FEED.OUTSIDE_DIA - (REAR_BUSHING.OD - printed_band_mm(REAR_BUSHING.OD_PLACES)))
    / 2.0
    * CLUSTER.BORE_DIAMETRAL_CLEARANCE[1]
    / (FEED.OVERALL_LENGTH - FEED.STATION_TOL)
)  # 0.0034
RACK_FRONT_FROM_SLEEVE_REAR_WORST = (
    FEED.DISC_FRONT_STATION
    - DISC_SPEC.FACE_WIDTH_MAX
    + FEED.DISC_FRONT_STATION_BAND
    - DISC_PLATEN_AIR_WORST
    - _PLATEN_THICKNESS_BAND
    - DISC_MOUNT_WOBBLE
    - CLUSTER_TILT_AT_DISC_RIM
    + CLUSTER_TILT_AT_FEED_TIPS
    - HANGER_TILT_AT_DISC_RIM
    + HANGER_TILT_AT_FEED_TIPS
    - PLATE_THICKNESS
)
if FEED.FULL_DEPTH_MIN < RACK_FRONT_FROM_SLEEVE_REAR_WORST:
    raise AssertionError(
        f"MHA-PD-010 12T full depth may stop {FEED.FULL_DEPTH_MIN:.3f} from the rear "
        f"face, inside the rack's worst reach {RACK_FRONT_FROM_SLEEVE_REAR_WORST:.3f}"
    )
# The MHA-PD-024 rear bushing's front face to the MHA-PD-005 rack's back face (its
# Ø9 .X can reach the rack's crests radially): the arm forward on the
# shortest spacer, the bar thinnest, the rack thickest, the bushing
# following the sleeve forward to its fitted max, and the hanger's tilt at
# the bushing's far rim.
BUSHING_RACK_AIR_NOMINAL = REAR_BUSHING_Z0 - REAR_BUSHING.LENGTH - RACK_BACK_Z  # 2.5
BUSHING_RACK_AIR_WORST = (
    BUSHING_RACK_AIR_NOMINAL
    - SPACER.LENGTH_BAND
    - BAR.BAR_DEPTH_BAND
    - _RACK_THICKNESS_BAND
    - (CLUSTER.SLEEVE_REAR_FORWARD_FROM_ARM[1] - REAR_BUSHING.LENGTH)
    - HANGER.HANGER_TILT
    * (_P_TO_S + (REAR_BUSHING.OD + printed_band_mm(REAR_BUSHING.OD_PLACES)) / 2.0)
)  # 1.07
if BUSHING_RACK_AIR_WORST < 0.0:
    raise AssertionError(
        "MHA-PD-024 rear bushing enters the MHA-PD-005 rack at the printed worst case: "
        f"air {BUSHING_RACK_AIR_WORST:.4f} (R9-68)"
    )

# Stack D: a bought #25 chain floated REARMOST on the thinnest T24 plate
# reaches chain_reach_rear() behind the seat face; it must keep air to the
# 120T disc's front face.
CHAIN_REACH_REAR_WORST = REMOVABLE.CHAIN_REACH_REAR_WORST  # 3.587
CHAIN_DISC_AXIAL_AIR_WORST = DISC_Z0 - (
    REMOVABLE.SEAT_FACE_Z + CHAIN_REACH_REAR_WORST
)  # 3.0635 = 6.65 - 3.5865
if CHAIN_DISC_AXIAL_AIR_WORST <= 0.0:
    raise AssertionError(
        f"bought #25 chain reaches the 120T disc: air {CHAIN_DISC_AXIAL_AIR_WORST:.4f}"
    )
# Radially, the only knob-stack feature between the seat face and the disc is
# the drive collar (the pins sit inside it); at its print-worst (largest)
# radius it must stand inside the T24 plates' inner edge, CAD link and ANSI,
# with the wheel floated off-centre on its pins (the crank's same pins, holes
# and bands: dt_crankshaft_spec.WHEEL_SEAT_FLOAT).
T24_CHAIN_INNER_R = min(
    REMOVABLE.chain_plate_inner_radius(24, h)
    for h in (2.0 * CHAIN_PLATE_HALF_H, REMOVABLE.ANSI_PLATE_HEIGHT)
)  # ~21.2 (ANSI)
KNOB_COLLAR_R_WORST = (COLLAR.OD + max(COLLAR.OD_BAND)) / 2.0  # 8.75
if KNOB_COLLAR_R_WORST + dt_crankshaft_spec.WHEEL_SEAT_FLOAT >= T24_CHAIN_INNER_R:
    raise AssertionError("knob drive collar reaches the T24 chain plates' inner edge")

# Thumbnut MHA-PD-013 (ch23 p.58/59 + video 4/4 "unscrew the nut that holds the
# other gear in place"): the knurled brass nut OUTERMOST on the knob shaft,
# tapped for the shaft's front thread, its flange's seat face ON the drive
# collar's pilot, faced to stand THUMBNUT_AIR proud of the mounted T24's front
# face, so the T24 floats free under the flange (R9-70, N-A). Rx(-90): local
# +Y -> -Z, so the nut spans THUMBNUT_Z0 .. THUMBNUT_Z0 - THUMBNUT_LEN (the
# knurled head at the front).
THUMBNUT_AIR = COLLAR.PILOT_PROUD  # 0.10, nominal
THUMBNUT_Z0 = REMOVABLE_Z0 - THUMBNUT_AIR  # -157.2 (the flange's seat face)
THUMBNUT_FRONT_Z = THUMBNUT_Z0 - THUMBNUT_LEN  # -173.3 (the rim)
KNOB_SHAFT_FRONT_Z = KNOB_SHAFT_Z0 - KNOB_SPEC.TIP_STATION  # -172.0, the stud tip
THUMBNUT_ENGAGEMENT = THUMBNUT_Z0 - KNOB_SHAFT_FRONT_Z  # 14.8
if THUMBNUT_THREAD != KNOB_SPEC.THREAD:
    raise AssertionError(
        f"thumbnut tap {THUMBNUT_THREAD} is not the knob shaft's {KNOB_SPEC.THREAD}"
    )
if abs(THUMBNUT_Z0 - (KNOB_COLLAR_Z0 - COLLAR.PILOT_LENGTH)) > 1e-9:
    raise AssertionError("thumbnut seat is not on the drive collar's pilot face")
if not THUMBNUT_AIR > 0.0:
    raise AssertionError("the thumbnut clamps the T24: the pilot is not proud of it")
if not (THUMBNUT_FRONT_Z < KNOB_SHAFT_FRONT_Z < THUMBNUT_Z0):
    raise AssertionError(
        f"knob shaft front {KNOB_SHAFT_FRONT_Z} must end inside the thumbnut"
        f" ({THUMBNUT_FRONT_Z} .. {THUMBNUT_Z0})"
    )
# The flange must still RETAIN the wheel: cover its bore with a shoulder.
# The drive-pin tips end inside the wheel's plate, behind the flange's seat.
if THUMBNUT_FLANGE_DIA < REMOVABLE.BORE_DIA + 1.0:
    raise AssertionError(
        "thumbnut flange slips into the removable's bore -- retains nothing"
    )
if REMOVABLE.DRIVE_PIN_TIP_Z - THUMBNUT_Z0 <= 0.0:
    raise AssertionError("knob drive-pin tips reach the thumbnut flange")
# Front furniture: nothing in this sub sits in front of the T24 but the
# chain, whose plates straddle the wheel (z CHAIN_MID_Z +- pin reach) and
# wrap it at the pitch radius -- the nut's head must clear that wrap radially.
_chain_inner_wrap_r = PITCH_R_T24 - CHAIN_PLATE_HALF_H  # 21.92
if THUMBNUT_HEAD_DIA / 2.0 > _chain_inner_wrap_r:
    raise AssertionError("thumbnut head reaches the chain's inner plate wrap")
# The bought chain floated FRONTMOST reaches CHAIN_REACH_FRONT ahead of the
# seat face (-160.59). The whole nut (and the shaft) lies radially inside the
# ANSI plates' inner edge, so no axial stack exists there; assert the radial
# one.
CHAIN_FRONT_Z_WORST = REMOVABLE.SEAT_FACE_Z - REMOVABLE.CHAIN_REACH_FRONT  # -160.5865
if max(THUMBNUT_HEAD_DIA, THUMBNUT_FLANGE_DIA) / 2.0 > T24_CHAIN_INNER_R:
    raise AssertionError("thumbnut reaches the bought chain's inner plate edge")

# Latch hook MHA-PD-014 (contract §4.4): one formed 0.8 spring-steel piece,
# its base on the bar's back face under two MHA-VN-043 screws, its ear bent
# rearward at the base's +X end and its arm hanging from the ear to the pin.
# The part frame's axes are the machine's (pd_latch_hook_geometry's
# LOCAL_TO_MACHINE): the assembly places it by translation only.
LATCH_HOOK_POS = list(HOOK.PART_ORIGIN_MACHINE)
if [list(row) for row in HOOK.LOCAL_TO_MACHINE] != IDENTITY:
    raise AssertionError("the latch hook's frame is not the machine's")
if abs(HOOK.BAR_BACK_FACE_Z - BAR_BACK_Z) > 1e-9 or abs(
    HOOK.BAR_CENTRE_Y - BAR_CY
) > 1e-9:
    raise AssertionError("the latch hook's bar anchors are off the support bar")
if HOOK.BBOX_Z[0] < BAR_BACK_Z - 1e-9:
    raise AssertionError(
        f"latch hook reaches z {HOOK.BBOX_Z[0]:.2f}, bar back face {BAR_BACK_Z}"
    )

# The hook's two MHA-VN-043 #4-40 screws (Rx+90: shanks to -Z) bear on the
# base's top face and run into the bar's through taps.
HOOK_BRACKET_SCREW_POS = tuple(
    (x, HOOK.SCREW_Y, BAR_BACK_Z + HOOK.SHEET_T) for x in HOOK.SCREW_X
)  # (65.0 / 72.0, 303.234, -129.1)
# The part's hole positions are rounded to 1e-6 (pd_latch_hook_geometry).
for _screw, _tap_x, _hole_x in zip(
    HOOK_BRACKET_SCREW_POS, BAR.BRACKET_TAP_X, HOOK.SCREW_HOLE_X, strict=True
):
    if (
        abs(_screw[0] - _tap_x) > 1e-9
        or abs(_screw[1] - (BAR_CY + BAR.HANGER_TAP_Y)) > 1e-9
        or abs(HOOK.PART_ORIGIN_MACHINE[0] + _hole_x - _screw[0]) > 1e-6
        or abs(HOOK.PART_ORIGIN_MACHINE[1] + HOOK.SCREW_HOLE_Y - _screw[1]) > 1e-6
    ):
        raise AssertionError("a latch-hook screw hole is off its tap in the bar")

# Mesh phasing. build_fixed_gear seeds the disc with a TOOTH centred on local
# +X, and its teeth repeat every 3 deg: MESH_ANGLE is a multiple of that, so
# the disc keeps identity spin with a tooth along the S -> K line. The knob
# shaft's integral 12T has a GAP at GAP_AZIMUTH_DEG (a tooth on local +X); it
# is spun so a gap faces back along that line.
THIRD_GAMMA = 360.0 / THIRD_TEETH  # 30
_MESH_AZ = 180.0 + MESH_ANGLE_DEG  # 12: from the knob axis toward the stud
THIRD_PHASE_DEG = (_MESH_AZ - KNOB_SPEC.GAP_AZIMUTH_DEG) % THIRD_GAMMA  # 27
if THIRD_PHASE_DEG > THIRD_GAMMA / 2.0:
    THIRD_PHASE_DEG -= THIRD_GAMMA  # -3: nearest representative
# The feed sleeve (Ry180) keeps a tooth on machine +90 deg (90 = 3 * 30), so a
# rack GAP centre must sit exactly on the stud's x. The rack is soldered with
# its ends flush with the platen's (MHA-PD-000 "rack-soldered"), so its gaps
# march +X from FIRST_GAP_X in from the platen's -X end: the photo pose moves
# by the smallest shift that lands a gap on the stud (no more than half a
# pitch, far inside the photo fit). Machine-handed: the rack is teeth-down
# (Rx180), its tooth pattern marching +X from RACK_X0.
PLATE_X0_PHASING = math.remainder(
    STUD_XY[0] - RACK_FIRST_GAP_X - PLATE_X0_PHOTO, RACK_PITCH
)  # -0.0355
if abs(PLATE_X0_PHASING) > RACK_PITCH / 2.0:
    raise AssertionError(
        f"platen phasing {PLATE_X0_PHASING:.4f} exceeds half the rack pitch"
    )
PLATE_X0 = PLATE_X0_PHOTO + PLATE_X0_PHASING  # -33.2485
RACK_X0 = PLATE_X0  # ends flush
if abs(RACK_BAR_LENGTH - PLATE_WIDTH) > 1e-9:
    raise AssertionError("the rack's ends cannot both be flush with the platen's")

# Net platen feed per CRANK revolution through the real train (T12/T24
# mounted): 0.5 chain * (12/120) gear * pi*PD rack = 1.596 mm. Every stage is
# a real mate; the law lives in paper_drive_geom (shared with the kinematics
# probe and the offline error budget) and is only cross-checked here.
from paper_drive_geom import NET_RACK_TRAVEL_PER_CRANK_REV  # noqa: E402

assert math.isclose(
    NET_RACK_TRAVEL_PER_CRANK_REV,
    0.5 * (THIRD_TEETH / DISC_TEETH) * math.pi * FEED_PD,
    rel_tol=1e-12,
), "paper_drive_geom feed law drifted from the assembly's mounted train"

# Spare T18 removable: the swap chain wheel, stored flat on the base top
# (local z=0 underside at the deck). Rx(-90) maps local +Z to machine +Y,
# so the face thickness extends UP from the deck, not down to it.
# A spare for this subsystem, so it rides here as a flat sibling of
# the mounted T24; placing it loose at the TOP level would clash on leaf name
# with the T12/T24 instances nested in drive-train / this sub.
# Keep the loose T18 on the deck, ahead of the nameplate. At the previous
# Z=-15 storage station, lowering onto the deck intersected the nameplate;
# Z=-75 leaves 5 mm between the T18 tip envelope and the plate's Z=-50 edge.
# X=140 (was 160): the black deck now ends at X=167 (user ruling 2026-10-09),
# and at X=160 the tip envelope (to X=180) straddled its 3.0 step; from 140 it
# spans X 120..160, flat on the deck and west of the rocker-support foot.
SPARE_GEAR_POS = (140.0, BASE_DECK_Y, -75.0)

# --- fasteners ----------------------------------------------------------------
# Platen-clip screws: through the clips' integral outer seats and #4 clearance
# holes into full-thickness #4-40 through receivers in the platen.
CLIP_SCREW_XY = tuple((PLATE_X0 + sx, PLATE_Y0 + sy) for sx, sy in PLATEN_SOCKET_XY)
# The clips run from the platen's top edge down; their end holes (inset
# CLIP_HOLE_INSET) must land exactly on the platen's edge sockets.
_CLIP_Y0_LOCAL = PLATE_HEIGHT - CLIP_LENGTH  # 51.32
assert math.isclose(
    PLATEN_SOCKET_XY[0][1], _CLIP_Y0_LOCAL + CLIP_HOLE_INSET, abs_tol=1e-6
)
assert math.isclose(
    PLATEN_SOCKET_XY[1][1], PLATE_HEIGHT - CLIP_HOLE_INSET, abs_tol=1e-6
)
# The machine reflection swaps the platen's two local edge rows.  The right
# holder uses Rz(+90) from the lower end; the left holder uses Rz(-90) from the
# upper end.  Thus both spring rails (local +Y) point inward over the paper.
_CLIP_RIGHT_SX = PLATEN_SOCKET_XY[0][0]
_CLIP_LEFT_SX = PLATEN_SOCKET_XY[2][0]
_CLIP_BOTTOM_Y = PLATE_Y0 + _CLIP_Y0_LOCAL
_CLIP_TOP_Y = PLATE_Y0 + PLATE_HEIGHT
CLIP_PLACEMENTS = (
    (
        _CLIP_RIGHT_SX,
        PLATE_X0 + PLATE_WIDTH - _CLIP_RIGHT_SX + CLIP_HOLE_Y,
        _CLIP_BOTTOM_Y,
        90.0,
    ),
    (
        _CLIP_LEFT_SX,
        PLATE_X0 + PLATE_WIDTH - _CLIP_LEFT_SX - CLIP_HOLE_Y,
        _CLIP_TOP_Y,
        -90.0,
    ),
)
_clip_expected_y = sorted(
    (PLATE_Y0 + PLATEN_SOCKET_XY[0][1], PLATE_Y0 + PLATEN_SOCKET_XY[1][1])
)
_plate_mid_x = PLATE_X0 + PLATE_WIDTH / 2.0
for _sx, _origin_x, _origin_y, _rz in CLIP_PLACEMENTS:
    _sin_rz = math.sin(math.radians(_rz))
    _socket_x = PLATE_X0 + PLATE_WIDTH - _sx
    assert math.isclose(_origin_x - _sin_rz * CLIP_HOLE_Y, _socket_x, abs_tol=1e-9)
    _clip_hole_y = sorted(
        _origin_y + _sin_rz * local_x
        for local_x in (CLIP_HOLE_INSET, CLIP_LENGTH - CLIP_HOLE_INSET)
    )
    assert all(
        math.isclose(actual, expected, abs_tol=1e-9)
        for actual, expected in zip(_clip_hole_y, _clip_expected_y, strict=True)
    )
    assert (_socket_x - _plate_mid_x) * (-_sin_rz) < 0.0
# Guide screws: 2 rows of 5, heads exactly 0.2 sub-flush of the platen front
# and shanks engaged 5.2678 mm in blind #4-40 guide receivers.
assert GUIDE_SCREW_STATION_X == PLATEN_GUIDE_HOLE_X
GUIDE_SCREW_XY = tuple(
    (PLATE_X0 + x, PLATE_Y0 + y)
    for y in PLATEN_GUIDE_HOLE_Y
    for x in PLATEN_GUIDE_HOLE_X
)
# Lock screws: 2 per lock plate, heads on the lock backs, into the guides.
LOCK_SCREW_XY = tuple(
    (PLATE_X0 + x, gy + GUIDE_HEIGHT / 2.0) for gy in GUIDE_Y for x in GUIDE_LOCK_HOLE_X
)

# Placed parts that can reach the chain plane (the band the bought chain
# sweeps, z CHAIN_FRONT_Z_WORST .. seat + CHAIN_REACH_REAR_WORST), as coaxial
# cylinder envelopes (label, axis xy, radius, z front, z back). The chain's
# own wheels are its intended contact. An axis of None stands for platen-
# group furniture that rides the feed: only axial air can clear it.
CHAIN_PLANE_ENVELOPES = (
    (
        "retaining ring",
        STUD_XY,
        E_RING.OD / 2.0,
        CLUSTER.RING_FRONT_Z,
        CLUSTER.RING_REAR_Z,
    ),
    ("pin", STUD_XY, PIN.DIA / 2.0, PIN.TIP_MACHINE_Z, PIN_Z0),
    (
        "front bushing",
        STUD_XY,
        FRONT_BUSHING.OD / 2.0,
        FRONT_BUSHING_Z0 - FRONT_BUSHING.LENGTH,
        FRONT_BUSHING_Z0,
    ),
    ("rear bushing", STUD_XY, REAR_BUSHING.OD / 2.0, FEED_Z0, REAR_BUSHING_Z0),
    (
        "disc hub",
        STUD_XY,
        DISC_HUB.HUB_DIA / 2.0,
        DISC_Z0 + DISC_HUB.HUB_FRONT_Z,
        DISC_Z0 - DISC_HUB.FLANGE_THICK,
    ),
    (
        "disc hub flange",
        STUD_XY,
        DISC_HUB.FLANGE_DIA / 2.0,
        DISC_Z0 - DISC_HUB.FLANGE_THICK,
        DISC_Z0,
    ),
    *(
        (
            "disc screw head",
            xy,
            DISC_SCREW.HEAD_DIA / 2.0,
            DISC_SCREW_Z0 - DISC_SCREW.HEAD_H,
            DISC_SCREW_Z0,
        )
        for xy in DISC_SCREW_XY
    ),
    ("120T disc", STUD_XY, DISC_SPEC.OUTSIDE_DIA / 2.0, DISC_Z0, DISC_Z0 + DISC_FACE),
    ("feed sleeve", STUD_XY, FEED.OUTSIDE_DIA / 2.0, FEED_Z0 - FEED_FACE, FEED_Z0),
    (
        "drive collar",
        KNOB_SHAFT_XY,
        COLLAR.OD / 2.0,
        KNOB_COLLAR_Z0 - COLLAR.PILOT_LENGTH,
        KNOB_COLLAR_REAR_Z,
    ),
    *(
        (
            "knob drive pin",
            xy,
            KNOB_PIN.DIA / 2.0,
            REMOVABLE.DRIVE_PIN_TIP_Z,
            KNOB_DRIVE_PIN_Z0,
        )
        for xy in KNOB_DRIVE_PIN_XY
    ),
    (
        "collar cross pin",
        KNOB_SHAFT_XY,
        CROSS_PIN.PIN_LEN / 2.0,
        CROSS_PIN_Z0 - CROSS_PIN.PIN_DIA / 2.0,
        CROSS_PIN_Z0 + CROSS_PIN.PIN_DIA / 2.0,
    ),
    (
        "knob shaft",
        KNOB_SHAFT_XY,
        KNOB_SPEC.OUTSIDE_DIA / 2.0,
        KNOB_SHAFT_FRONT_Z,
        KNOB_SHAFT_REAR_Z,
    ),
    ("thumbnut", KNOB_SHAFT_XY, THUMBNUT_HEAD_DIA / 2.0, THUMBNUT_FRONT_Z, THUMBNUT_Z0),
    (
        "platen-clip screw heads (the platen group's frontmost)",
        None,
        0.0,
        PLATE_FRONT_Z - SCREW_SEAT_STACK - FILLISTER_HEAD_H,
        PLATE_FRONT_Z,
    ),
)

# The guide-lock stations ride the platen: each lock plate bridges the bar
# behind one guide rail (bottom plate up from the lower rail's seat, top plate
# down from the upper rail's top edge), lapping LOCK_RAIL_LIP past the rail's
# outer edge (R9-59), its two screws on the rail's mid-line.
if any(abs(y - LOCK_RAIL_LIP - GUIDE_HEIGHT / 2.0) > 1e-9 for _, y in LOCK_HOLE_XY):
    raise AssertionError("guide-lock screw holes are off the guide rail's mid-line")
LOCK_PLATE_Y = (
    (GUIDE_Y[0] - LOCK_RAIL_LIP, GUIDE_Y[0] - LOCK_RAIL_LIP + LOCK_HEIGHT),
    (
        GUIDE_Y[1] + GUIDE_HEIGHT + LOCK_RAIL_LIP - LOCK_HEIGHT,
        GUIDE_Y[1] + GUIDE_HEIGHT + LOCK_RAIL_LIP,
    ),
)


def _assert_fastener_stacks() -> None:
    """Prove every selected stock screw has clearance and useful engagement."""

    def nonnegative(label: str, value: float) -> float:
        if value < -1e-9:
            raise AssertionError(f"{label} is negative ({value:.6f} mm)")
        return value

    def valid_engagement(label: str, engagement: float, major_dia: float) -> None:
        nonnegative(label, engagement)
        if engagement + 1e-9 < major_dia:
            raise AssertionError(
                f"{label} {engagement:.4f} mm is less than one screw diameter "
                f"({major_dia:.4f} mm)"
            )

    # 90280A201 clamps: head seat -> remaining bar -> front clamp -> tapped
    # back clamp. The receiver is through, so its unused thickness is clearance,
    # never a blind bottom.
    if (
        CLAMP_RECEIVER_SPEC.kind,
        CLAMP_RECEIVER_SPEC.size,
        CLAMP_RECEIVER_SPEC.end,
    ) != ("tapped", "#8-32", "through_all"):
        raise AssertionError("clamp receiver is not a through #8-32 tap")
    clamp_passage = BAR_DEPTH - CLAMP_CBORE_DEPTH + ARC_FRONT_DEPTH
    clamp_engagement = CLAMP_SCREW_LEN - clamp_passage
    nonnegative("clamp head recess", CLAMP_CBORE_DEPTH - CLAMP_SCREW_HEAD_H)
    nonnegative(
        "clamp head radial clearance", (CLAMP_CBORE_DIA - CLAMP_SCREW_HEAD_DIA) / 2.0
    )
    nonnegative(
        "clamp shank radial clearance", (CLAMP_HOLE_DIA - CLAMP_SCREW_DIA) / 2.0
    )
    valid_engagement("clamp #8-32 engagement", clamp_engagement, CLAMP_SCREW_DIA)
    nonnegative("clamp receiver tip clearance", ARC_BACK_DEPTH - clamp_engagement)
    if abs(CLAMP_CBORE_DEPTH - CLAMP_SCREW_HEAD_H - CLAMP_HEAD_RECESS) > 1e-9:
        raise AssertionError("clamp head is not recessed by the specified 0.2 mm")

    # 90114A511 guide screws: exact head recess, positive shank clearance,
    # 5.4178-mm engagement, and positive blind-bottom clearance.
    nonnegative("guide head recess", PLATEN_CBORE_DEPTH - FILLISTER_HEAD_H)
    nonnegative(
        "guide head radial clearance", (PLATEN_CBORE_DIA - FILLISTER_HEAD_DIA) / 2.0
    )
    nonnegative(
        "guide shank radial clearance",
        (PLATEN_GUIDE_HOLE_DIA - FILLISTER_SHANK_DIA) / 2.0,
    )
    if abs(PLATEN_CBORE_DEPTH - FILLISTER_HEAD_H - PLATEN_HEAD_RECESS) > 1e-9:
        raise AssertionError("guide head is not recessed by the specified 0.2 mm")
    if (
        abs(GUIDE_SCREW_PASSAGE + GUIDE_SCREW_THREAD_ENGAGEMENT - FILLISTER_SHANK_LEN)
        > 1e-9
    ):
        raise AssertionError("guide screw stack does not consume the stock shank")
    valid_engagement(
        "guide #4-40 engagement", GUIDE_SCREW_THREAD_ENGAGEMENT, FILLISTER_SHANK_DIA
    )
    nonnegative("guide screw blind-bottom clearance", GUIDE_SCREW_BOTTOM_CLEARANCE)

    # The low button-head guide-lock screws (R9-31, R9-48) take the real 2-mm
    # plate and 9.525-mm under-head length; the guide's through tap receives
    # the remaining 7.525 mm and the tip stops inside the rail.
    nonnegative(
        "lock shank radial clearance", (LOCK_HOLE_DIA - LOCK_SCREW_SHANK_DIA) / 2.0
    )
    if abs(LOCK_SCREW_PASSAGE - LOCK_THICK) > 1e-9:
        raise AssertionError(
            "lock screw passage does not equal the real plate thickness"
        )
    if (
        abs(LOCK_SCREW_PASSAGE + LOCK_SCREW_THREAD_ENGAGEMENT - LOCK_SCREW_SHANK_LEN)
        > 1e-9
    ):
        raise AssertionError("lock screw stack does not consume the stock shank")
    valid_engagement(
        "lock #4-40 engagement", LOCK_SCREW_THREAD_ENGAGEMENT, LOCK_SCREW_SHANK_DIA
    )
    nonnegative("lock screw tip inside the guide", LOCK_SCREW_TIP_INSIDE_MIN)

    # Clip bosses use exactly the non-threaded remainder of the shank; the
    # platen and its rear socket bosses are through-tapped for 4.5 mm
    # engagement, and the tip is flush with the boss.
    if (PLATEN_SOCKET_SPEC.kind, PLATEN_SOCKET_SPEC.size, PLATEN_SOCKET_SPEC.end) != (
        "tapped",
        "#4-40",
        "through_all",
    ):
        raise AssertionError("clip receiver is not a through #4-40 tap")
    nonnegative(
        "clip shank radial clearance", (CLIP_HOLE_DIA - FILLISTER_SHANK_DIA) / 2.0
    )
    nonnegative(
        "clip head seat radial margin", (SCREW_SEAT_DIA - FILLISTER_HEAD_DIA) / 2.0
    )
    if abs(CLIP_THICKNESS + SCREW_SEAT_BOSS_H - SCREW_SEAT_STACK) > 1e-9:
        raise AssertionError(
            "clip boss no longer provides the derived screw seat stack"
        )
    valid_engagement(
        "clip #4-40 engagement", PLATEN_SOCKET_ENGAGEMENT, FILLISTER_SHANK_DIA
    )
    clip_tip_clearance = (
        SCREW_SEAT_STACK + PLATEN_SOCKET_ENGAGEMENT - FILLISTER_SHANK_LEN
    )
    nonnegative("clip screw rear protrusion clearance", clip_tip_clearance)
    if abs(clip_tip_clearance) > 1e-9:
        raise AssertionError("clip screw tip is not flush with the socket boss")

    # The raised heads remain wholly outside the recording-paper side margins.
    paper_side_margin = (PLATE_WIDTH - PAPER_WIDTH) / 2.0
    left_head_extent = PLATEN_SOCKET_XY[0][0] + FILLISTER_HEAD_DIA / 2.0
    right_head_extent = PLATE_WIDTH - PLATEN_SOCKET_XY[2][0] + FILLISTER_HEAD_DIA / 2.0
    nonnegative(
        "left clip head-to-paper clearance", paper_side_margin - left_head_extent
    )
    nonnegative(
        "right clip head-to-paper clearance", paper_side_margin - right_head_extent
    )

    # Hanger joints: transgear_hanger_joints owns the stacks; re-prove them
    # against the placed stations.
    spring_room = PIVOT_SCREW_Z0 - (ARM_Z0 + ARM.SPOT_FACE_FLOOR_FROM_FRONT)
    if abs(spring_room - HANGER.SPRING_ROOM_NOMINAL) > 1e-9:
        raise AssertionError(
            f"pivot spring room {spring_room:.4f} is not "
            f"{HANGER.SPRING_ROOM_NOMINAL:.4f}"
        )
    if abs(spring_room - PIVOT_SPRING.MODEL_HEIGHT) > 1e-9:
        raise AssertionError("the MHA-VN-049 spring is not modelled in its room")
    if HANGER.PIVOT_ENGAGEMENT_WORST_D + 1e-9 < HANGER.PIVOT_ENGAGEMENT_APPROVED_MIN_D:
        raise AssertionError("pivot screw engagement is under its approved minimum")
    if HANGER.PLATE_SCREW_ENGAGEMENT_WORST_D + 1e-9 < HANGER.ENGAGEMENT_TARGET_D:
        raise AssertionError(
            f"plate-screw engagement {HANGER.PLATE_SCREW_ENGAGEMENT_WORST_D:.3f} D"
            f" worst is under {HANGER.ENGAGEMENT_TARGET_D} D"
        )
    # R9-44: the screws are cut flush with the arm's front face at assembly
    # (MHA-DT-032's filed-tip idiom), and the model carries the cut length.
    plate_screw_tip = PLATE_SCREW_Z0 - PLATE_SCREW.LENGTH
    if abs(plate_screw_tip - (ARM_Z0 + HANGER.PLATE_SCREW_TIP_INSIDE_NOMINAL)) > 1e-9:
        raise AssertionError(
            "MHA-VN-040's cut tips are not flush with the arm's front face"
        )
    latch_pin_proud = LATCH_PIN.LENGTH - ARM.PIN_HOLE_DEPTH
    low, high = HANGER.LATCH_PIN_PROUD_RANGE
    if abs(latch_pin_proud - LATCH_PIN.PROUD) > 1e-9 or not (
        low <= latch_pin_proud <= high
    ):
        raise AssertionError(f"latch pin stands {latch_pin_proud:.3f} proud of the arm")
    hook_screw_engagement = HOOK_BRACKET_SCREW.LENGTH - HOOK.SHEET_T
    valid_engagement(
        "latch-hook #4-40 engagement",
        hook_screw_engagement,
        HOOK_BRACKET_SCREW.MAJOR_DIA,
    )
    for x, y, z in HOOK_BRACKET_SCREW_POS:
        nonnegative(
            f"latch-hook screw tip x{x:.1f} inside the bar front",
            z - HOOK_BRACKET_SCREW.LENGTH - BAR_FRONT_Z,
        )

    # Disc screws: through the hub flange and the disc's through taps, cut at
    # assembly (R9-47) to TIP_BELOW_REAR_FACE inside the disc's rear face, so
    # no tip stands into the platen's path behind the disc; the model carries
    # the cut.  The worst-case engagement is the spec's (import-time).
    disc_screw_tip = DISC_SCREW_Z0 + DISC_SCREW.LENGTH
    tip_below_rear = DISC_Z0 + DISC_FACE - disc_screw_tip
    if abs(tip_below_rear - DISC_SCREW.TIP_BELOW_REAR_FACE_MODEL) > 1e-9 or not (
        DISC_SCREW.TIP_BELOW_REAR_FACE[0]
        <= tip_below_rear
        <= DISC_SCREW.TIP_BELOW_REAR_FACE[1]
    ):
        raise AssertionError(
            "MHA-VN-039 disc-screw tip to the MHA-PD-006 disc rear face: "
            f"{tip_below_rear:.3f} inside, off the cut window"
        )
    valid_engagement(
        "disc #0-80 engagement",
        disc_screw_tip - DISC_Z0,
        DISC_SCREW.SHANK_DIA,
    )

    # Knob stack: the thumbnut on the shaft's front thread, seated on the
    # collar's pilot (R9-70); the cup is pinned, not screwed.
    raw_thumbnut = KNOB_SPEC.TIP_STATION - COLLAR.SET_NOMINAL - COLLAR.PILOT_LENGTH
    if abs(THUMBNUT_ENGAGEMENT - raw_thumbnut) > 1e-9:
        raise AssertionError("thumbnut engagement is off the collar/pilot stack")
    valid_engagement(
        "thumbnut 1/4-20 engagement", THUMBNUT_ENGAGEMENT, KNOB_SPEC.THREAD_MAJOR
    )
    # The nut's seat stands on full thread, in front of the stud's relief.
    nonnegative(
        "thumbnut seat to the stud's full-thread end",
        KNOB_SHAFT_Z0 - KNOB_SPEC.PLAIN_CORE - THUMBNUT_Z0,
    )


def _section_gap(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> float:
    """Separation of two (y0, y1, z0, z1) sections; negative when they overlap."""
    dy = max(a[0] - b[1], b[0] - a[1])
    dz = max(a[2] - b[3], b[2] - a[3])
    if dy > 0.0 and dz > 0.0:
        return math.hypot(dy, dz)
    return max(dy, dz)


def _hook_arm_x_min(y: float) -> float:
    """The hook arm's least machine x at machine ``y``: the strip's inner
    face down the vertical and round the R80 roll, then the part's -X extent
    below the roll (a bound)."""
    if y >= HOOK.ROLL_START[1]:
        return HOOK.X_B - HOOK.SHEET_T
    if y >= HOOK.ROLL_END[1]:
        inner_r = HOOK.ROLL_R - HOOK.HALF_T
        return HOOK.ROLL_C[0] + math.sqrt(inner_r**2 - (y - HOOK.ROLL_C[1]) ** 2)
    return HOOK.BBOX_X[0]


def _latch_hook_sections() -> list[tuple[str, tuple[float, float, float, float]]]:
    """The latch hook's machine (y, z) sections at the printed worst case:
    the base and ear as one block and the arm as thin slices
    (``HOOK.arm_sections``), with the hook's screw heads.

    The hook stands on the bar's back face (its z datum) and is located in
    y by its two screws: each screw's tap, the hook's printed hole position
    and the head's float, the latched pin holding the hook's pin hole
    (transgear_hanger_joints.hook_screw_drift).  The hook turns as well as
    slides, so its drift along y depends on x alone and is convex in it:
    over a section's x span its ends bound it, and between two
    half-millimetre stations the stations do.
    The base's width grows its far (+y) edge from the datum edge; the ear's
    height and the arm's front edges grow at their printed rows; the formed
    arm lies within FORMED_BAND of the model; and the ear's bend at the
    sheet's angular row leans the ear and arm about the base, moving each
    slice in z by its x off the bend times sin(bend error)."""
    drifts: dict[float, float] = {}

    def drift_y(x0: float) -> float:
        """The largest y drift over x0..X_B."""
        stations = (math.floor(2.0 * x0) / 2.0, math.ceil(2.0 * x0) / 2.0, HOOK.X_B)
        for x in stations:
            if x not in drifts:
                drifts[x] = HANGER.hook_screw_drift((x, HOOK.SCREW_Y), (0.0, 1.0))
        return max(drifts[x] for x in stations)

    width_dev = printed_deviations(
        HOOK.WIDTH, HOOK_SPEC.WIDTH_PLACES, (-HOOK_SPEC.WIDTH_TOL, HOOK_SPEC.WIDTH_TOL)
    )
    ear_rear = printed_deviations(HOOK.EAR_HEIGHT, HOOK_SPEC.EAR_HEIGHT_PLACES)[1]
    arm_forward = max(
        -printed_deviations(HOOK.z_local(z), HOOK_SPEC.ARM_BAND_PLACES)[0]
        for z in (HOOK.Z_FRONT, HOOK.Z_FRONT_LOW)
    )
    bend = math.radians(HOOK_SPEC.BEND_TOL_DEG)
    ear_lift = HOOK.EAR_HEIGHT * (1.0 - math.cos(bend))
    sections: list[tuple[str, tuple[float, float, float, float]]] = [
        (
            "latch hook base and ear",
            _grown(
                (
                    HOOK.BASE_Y[0],
                    HOOK.BASE_Y[1] + width_dev[1],
                    BAR_BACK_Z,
                    HOOK.Z_REAR + ear_rear,
                ),
                drift_y(HOOK.BASE_X0),
                0.0,
                ear_lift + HOOK.SHEET_T * math.sin(bend),
            ),
        ),
        (
            "latch hook screw heads",
            _grown(
                (
                    HOOK.SCREW_Y - HOOK_BRACKET_SCREW.HEAD_DIA / 2.0,
                    HOOK.SCREW_Y + HOOK_BRACKET_SCREW.HEAD_DIA / 2.0,
                    BAR_BACK_Z + HOOK.SHEET_T + HOOK.SHEET_T_PLUS,
                    BAR_BACK_Z
                    + HOOK.SHEET_T
                    + HOOK.SHEET_T_PLUS
                    + HOOK_BRACKET_SCREW.HEAD_H,
                ),
                BAR.HOLE_POSITION_BAND,
                0.0,
                0.0,
            ),
        ),
    ]
    for y0, y1, z0, z1 in HOOK.arm_sections():
        x_min = min(_hook_arm_x_min(y0), _hook_arm_x_min(y1))
        lean = (HOOK.X_B - x_min) * math.sin(bend) + ear_lift
        sections.append(
            (
                "latch hook arm",
                _grown(
                    (y0, y1, z0, z1),
                    drift_y(x_min) + HOOK_SPEC.FORMED_BAND,
                    arm_forward + lean,
                    ear_rear + lean,
                ),
            )
        )
    return sections


# The lock-station sweep judges every section at the printed worst case
# (policy rule 12): each section is the envelope its printed bands allow,
# grown toward its neighbours, and each pair must keep LOCK_SWEEP_FLOOR of
# running clearance. The bar's back face is the datum the hanger stands on and
# the platen rides its front face, so the thinnest bar carries the whole lock
# stack rearward toward the hanger, and the deepest rail and thickest strip
# stand the button heads further back again. The arm sits on the shortest
# spacer, its plate's lower section on the thinnest arm stock and the deepest
# notch. Deviations are (lower, upper) from the model, read from the specs the
# parts author on their model dimensions, so the sheets and the sweep agree.
# Unmodelled contributor (R9-61): the bottom rail's y on the platen, set
# against the top rail (which hangs on the bar's top edge) by the platen's
# guide-screw rows and the #4 screws' float in its Ø3.0 holes. The platen has
# no sheet and so no printed bands, so the sweep holds both rails at GUIDE_Y.
LOCK_SWEEP_FLOOR = 0.10
_BAR_DEPTH_DEV = (-BAR.BAR_DEPTH_BAND, BAR.BAR_DEPTH_BAND)
_GUIDE_DEPTH_DEV = printed_deviations(
    GUIDE_DEPTH, GUIDE_DEPTH_PLACES, deviations(GUIDE_DEPTH_BAND)
)
# The rail's sheet prints its other sizes at the same document places.
_GUIDE_HEIGHT_DEV = printed_deviations(GUIDE_HEIGHT, GUIDE_DEPTH_PLACES)
_LOCK_THICK_DEV = printed_deviations(LOCK_THICK, LOCK_PRECISION["Depth"])
_LOCK_HEIGHT_DEV = printed_deviations(
    LOCK_HEIGHT, LOCK_PRECISION["Height"], deviations(LOCK_HEIGHT_BAND)
)
_SPACER_LENGTH_DEV = (-SPACER.LENGTH_BAND, SPACER.LENGTH_BAND)
_NOTCH_DEPTH_DEV = printed_deviations(
    ARM_PLATE.NOTCH_DEPTH, ARM_PLATE_SPEC.NOTCH_DEPTH_PLACES
)
_PLATE_OUTLINE_BAND = ARM_PLATE_SPEC.BAND_BY_PLACES[ARM_PLATE_SPEC.OUTLINE_PLACES]
_HUB_DIA_DEV = printed_deviations(ARM_PLATE.HUB_DIA, ARM_PLATE_SPEC.HUB_DIA_PLACES)


def _grown(
    section: tuple[float, float, float, float], dy: float, dz0: float, dz1: float
) -> tuple[float, float, float, float]:
    """A (y0, y1, z0, z1) section grown by dy each side in y, dz0 forward and
    dz1 rearward in z."""
    y0, y1, z0, z1 = section
    return (y0 - dy, y1 + dy, z0 - dz0, z1 + dz1)


def _assert_lock_station_sweep() -> None:
    """The guide-lock stations ride the platen across its whole feed, so each
    sweeps a band unbounded in x: its (y, z) section must clear every fixed
    part behind the bar at every platen position, and the plates the bar's
    back face, by LOCK_SWEEP_FLOOR at the printed worst case (contract lock
    sweep; R9-31 fits the low guide-lock screw heads so they pass the hanger
    arm)."""
    # How far the lock stack's faces can stand from the model: forward (the
    # thickest bar, the shallowest rail, the thinnest strip) and rearward.
    front_forward = _BAR_DEPTH_DEV[1] - _GUIDE_DEPTH_DEV[0]
    back_forward = front_forward - _LOCK_THICK_DEV[0]
    front_rear = -_BAR_DEPTH_DEV[0] + _GUIDE_DEPTH_DEV[1]
    back_rear = front_rear + _LOCK_THICK_DEV[1]
    lock_back = LOCK_Z0 + LOCK_THICK
    head_r = LOCK_SCREW_HEAD_DIA / 2.0  # the catalogue head, Ø and height
    # R9-49: each lock is pushed away from the bar onto its screws before they
    # are tightened (the "guide-locks-set" step). Set so, and skewed by holes
    # bearing at opposite ends of the set window, its guide-side edge stands
    # up to LOCK_SET_EDGE_REACH[1] beyond the model and its far edge up to
    # LOCK_SET_EDGE_REACH[0] toward the bar, plus the height band's growth.
    plate_outward = LOCK_SET_EDGE_REACH[1]
    plate_inward = max(_LOCK_HEIGHT_DEV[1], 0.0) + LOCK_SET_EDGE_REACH[0]
    moving = []
    for index, (gy, (y0, y1)) in enumerate(zip(GUIDE_Y, LOCK_PLATE_Y, strict=True)):
        yc = gy + GUIDE_HEIGHT / 2.0
        # The bottom rail's lock laps the rail's underside and is pushed down;
        # the top rail's laps its top and is pushed up.
        grow_down, grow_up = (
            (plate_outward, plate_inward)
            if index == 0
            else (plate_inward, plate_outward)
        )
        moving += [
            (
                f"lock plates y{y0:.1f}",
                _grown(
                    (y0 - grow_down, y1 + grow_up, LOCK_Z0, lock_back),
                    0.0,
                    front_forward,
                    back_rear,
                ),
            ),
            (
                f"lock-screw heads y{yc:.1f}",
                _grown(
                    (
                        yc - head_r,
                        yc + head_r,
                        lock_back,
                        lock_back + LOCK_SCREW_HEAD_H,
                    ),
                    0.0,
                    back_forward,
                    back_rear,
                ),
            ),
            (
                f"guide rail rear lip y{gy:.1f}",
                _grown(
                    (gy, gy + GUIDE_HEIGHT, BAR_BACK_Z, LOCK_Z0),
                    max(_GUIDE_HEIGHT_DEV[1], 0.0),
                    0.0,
                    front_rear,
                ),
            ),
        ]
    tip_y = _on_arm(ARM.TIP_STATION)[1]
    plate_corner_y = max(
        _on_arm(ARM_PLATE.BORE_STATION + u, ARM_PLATE.BORE_OFFSET + v)[1]
        for u, v in (ARM_PLATE.TOP_LEFT, ARM_PLATE.TOP_RIGHT)
    )
    py = PIVOT_XY[1]
    ky = KNOB_SHAFT_XY[1]
    # R9-61: the hanger hangs on the pivot screw, whose #8-32 tap the bar
    # prints at its ±HOLE_POSITION_BAND, so every hung section stands off its
    # model by that band in y. The spacer is pressed on the shoulder, so its
    # largest O.D. stands on the screw axis.
    pivot_tap = BAR.HOLE_POSITION_BAND
    spacer_r = (SPACER.OD + SPACER.OD_BAND) / 2.0
    # The arm's front face on the shortest spacer; its plate's lower section
    # stands proud of it by the deepest notch on the thinnest arm stock.
    arm_forward = -_SPACER_LENGTH_DEV[0]
    plate_forward = arm_forward + ARM.THICKNESS_BAND + _NOTCH_DEPTH_DEV[1]
    fixed: list[tuple[str, tuple[float, float, float, float]]] = [
        (
            "arm",
            _grown(
                (tip_y - ARM.TIP_END_R, py + ARM.PIVOT_END_R, ARM_Z0, PLATE_Z0),
                ARM.BAND_X + ARM.TIP_STATION_BAND + pivot_tap,
                arm_forward,
                0.0,
            ),
        ),
        (
            "arm plate",
            _grown(
                (
                    ky - ARM_PLATE.END_R,
                    plate_corner_y,
                    PLATE_Z0 + ARM_PLATE.FRONT_FACE_Z,
                    PLATE_Z0 + ARM_PLATE.BOSS_FACE_Z,
                ),
                _PLATE_OUTLINE_BAND + pivot_tap,
                plate_forward,
                0.0,
            ),
        ),
        (
            "arm plate hub",
            _grown(
                (
                    ky - ARM_PLATE.HUB_DIA / 2.0,
                    ky + ARM_PLATE.HUB_DIA / 2.0,
                    PLATE_Z0 + ARM_PLATE.HUB_FACE_Z,
                    ARM_Z0,
                ),
                _HUB_DIA_DEV[1] / 2.0 + pivot_tap,
                arm_forward,
                0.0,
            ),
        ),
        *(
            (
                "arm plate-screw tip (worst proud)",
                _grown(
                    (
                        y - PLATE_SCREW.THREAD_MAJOR / 2.0,
                        y + PLATE_SCREW.THREAD_MAJOR / 2.0,
                        ARM_Z0 - HANGER.PLATE_SCREW_TIP_PROUD_MAX,
                        PLATE_SCREW_Z0,
                    ),
                    ARM.HOLE_POSITION_BAND + pivot_tap,
                    arm_forward,
                    0.0,
                ),
            )
            for _, y in PLATE_SCREW_XY
        ),
        (
            "pivot spacer",
            _grown(
                (py - spacer_r, py + spacer_r, SPACER_Z0, ARM_Z0), pivot_tap, 0.0, 0.0
            ),
        ),
        (
            "pivot screw shoulder",
            _grown(
                (
                    py - PIVOT_SCREW.SHOULDER_DIA / 2.0,
                    py + PIVOT_SCREW.SHOULDER_DIA / 2.0,
                    SPACER_Z0,
                    PIVOT_SCREW_Z0,
                ),
                pivot_tap,
                0.0,
                0.0,
            ),
        ),
        (
            "pivot screw head",
            _grown(
                (
                    py - PIVOT_SCREW.HEAD_DIA / 2.0,
                    py + PIVOT_SCREW.HEAD_DIA / 2.0,
                    PIVOT_SCREW_Z0,
                    PIVOT_SCREW_Z0 + PIVOT_SCREW.HEAD_H,
                ),
                pivot_tap,
                0.0,
                0.0,
            ),
        ),
        # The one-piece hook: refitted after hardening with its match-drilled
        # hole on the pin, it may sit anywhere its two screws' float allows
        # (tap, printed hole position, head float), turning about the pin as
        # well as sliding, so its y drift grows with its x off the screws (up
        # to ~0.54 at the base, ~0.70 at the tab); the base's +y edge also
        # takes the printed width band (HOOK_SPEC.WIDTH_TOL).
        *_latch_hook_sections(),
    ]
    minima: dict[str, float] = {}
    for fixed_label, fixed_section in fixed:
        for moving_label, moving_section in moving:
            gap = _section_gap(moving_section, fixed_section)
            if gap < LOCK_SWEEP_FLOOR:
                raise AssertionError(
                    f"the platen's {moving_label} would sweep into the"
                    f" {fixed_label} as it feeds (worst-case gap {gap:.3f}"
                    f" < {LOCK_SWEEP_FLOOR})"
                )
            minima[fixed_label] = min(minima.get(fixed_label, math.inf), gap)
    # The plates bridge behind the bar: the thickest bar and the shallowest
    # rail bring their front faces closest to its back face.
    bar_gap = LOCK_Z0 - front_forward - BAR_BACK_Z
    if bar_gap < LOCK_SWEEP_FLOOR:
        raise AssertionError(
            f"the platen's lock plates would rub the bar's back face as it feeds"
            f" (worst-case gap {bar_gap:.3f} < {LOCK_SWEEP_FLOOR})"
        )
    minima["bar back face"] = bar_gap
    # Pushed away from the bar (R9-49), a lock plate's guide-side edge moves
    # over the platen's own back. Behind the platen back only the rails and
    # the rack stand; paper and clips are on its front face.
    rack = (RACK_TIP_Y, RACK_Y0, BAR_FRONT_Z, RACK_BACK_Z)
    rack_gap = min(
        _section_gap(section, rack)
        for label, section in moving
        if label.startswith("lock plates")
    )
    if rack_gap < LOCK_SWEEP_FLOOR:
        raise AssertionError(
            "a set guide-lock plate would foul the platen rack"
            f" (worst-case gap {rack_gap:.3f} < {LOCK_SWEEP_FLOOR})"
        )
    minima["platen rack"] = rack_gap
    log(
        "guide-lock station sweep clears the hanger at the printed worst case: "
        + ", ".join(f"{label} {gap:.3f}" for label, gap in minima.items())
    )


def _assert_rack_mesh() -> None:
    """Feed-pinion/rack law: centre extension and tooth-on-gap phasing."""
    ext = RACK_PITCH_Y - (STUD_XY[1] + FEED_PD / 2.0)
    if abs(ext - RACK_MESH_EXT) > 1e-9:
        raise RuntimeError(f"rack mesh extension {ext:.3f} != {RACK_MESH_EXT}")
    # A rack GAP centre must sit exactly over the stud (the pinion's +90-deg
    # tooth): teeth-down Rx180, gap centres march +X at RACK_X0 + FIRST_GAP_X
    # + k*PITCH (machine frame).
    phase = math.remainder(STUD_XY[0] - RACK_X0 - RACK_FIRST_GAP_X, RACK_PITCH)
    if abs(phase) > 1e-9:
        raise RuntimeError(f"rack gap phase {phase:.4f} != 0 over the stud")
    if FEED_TEETH % 4:
        raise RuntimeError("feed-pinion top-tooth alignment needs teeth % 4 == 0")
    # The sleeve's teeth (Ry180: FEED_Z0 forward FEED_FACE) into the rack band
    # (the rack's thickness on the platen back).
    z_overlap = min(FEED_Z0, RACK_BACK_Z) - max(FEED_Z0 - FEED_FACE, BAR_FRONT_Z)
    if z_overlap < 2.5:
        raise RuntimeError(
            f"feed pinion reaches only {z_overlap:.2f} into the rack band"
        )
    # Radial safety (R9-62a): the rack clear of the form-cut 12T's flank (the
    # same sweep that bounds the fit-up band), its crests clear of the 1.25/P
    # root, and the contact ratio at or over 1.2 at the nominal mesh.
    import pd_paper_drive_assembly_steps as steps

    if abs(RACK_ADDENDUM - FEED.MODULE_MM) > 1e-9:
        raise RuntimeError("the mesh sweep assumes the rack's 1/P addendum")
    penetration = steps.feed_mesh_penetration(RACK_MESH_EXT)
    if penetration > 1e-5:
        raise RuntimeError(
            f"rack reaches {penetration:.4f} into the feed pinion's flank"
            f" at extension {RACK_MESH_EXT:.3f}"
        )
    crest_depth = RACK_ADDENDUM - RACK_MESH_EXT  # crests past the pitch circle
    root_clearance = FEED_PD / 2.0 - crest_depth - FEED.ROOT_DIA_MIN / 2.0
    if root_clearance < 0.25:
        raise RuntimeError(f"rack crests {root_clearance:.3f} off the pinion root")
    contact_ratio = steps.feed_mesh_contact_ratio(RACK_MESH_EXT)
    if contact_ratio < 1.2:
        raise RuntimeError(f"feed mesh contact ratio {contact_ratio:.2f} < 1.2")
    log(
        f"rack mesh: pitch line y {RACK_PITCH_Y:.2f}, extension {ext:.2f},"
        f" rack gap centred over the stud, flank clear from extension"
        f" {steps.MESH_EXTENSION_MIN:.3f}, root clearance {root_clearance:.3f},"
        f" contact ratio {contact_ratio:.2f}"
    )


def _assert_gear_mesh() -> None:
    """Third-gear/disc mesh: same DP, the disc's centre distance, phased
    tooth-on-gap."""
    if THIRD_DP != DISC_DP:
        raise RuntimeError(f"third gear DP {THIRD_DP} != disc DP {DISC_DP}")
    centre_distance = DISC_SPEC.CENTRE_DISTANCE
    c2c_nominal = (THIRD_TEETH + DISC_TEETH) / (2.0 * DISC_DP) * IN  # 44.116
    ext = centre_distance - c2c_nominal  # 0.650
    if not (0.5 <= ext <= 0.8):
        raise RuntimeError(
            f"gear mesh extension {ext:.3f} outside the 0.5..0.8 gap-floor window"
        )
    # The disc's teeth repeat every 3 deg, so a tooth must point along the S ->
    # K line at the mesh angle for the 12T's phased gap to receive it.
    disc_gamma = 360.0 / DISC_TEETH
    if abs(math.remainder(MESH_ANGLE_DEG, disc_gamma)) > 1e-9:
        raise RuntimeError(
            f"mesh angle {MESH_ANGLE_DEG} is not a multiple of the disc pitch"
            f" {disc_gamma}"
        )
    gap_az = THIRD_PHASE_DEG + KNOB_SPEC.GAP_AZIMUTH_DEG - _MESH_AZ
    if abs(math.remainder(gap_az, THIRD_GAMMA)) > 1e-9:
        raise RuntimeError("the knob 12T's phased gap does not face the disc")
    # Radial: the disc tooth tips must clear the 12T's base-circle gap floor
    # (the law the centre extension exists for).
    rb3 = THIRD_TEETH / THIRD_DP * IN / 2.0 * math.cos(math.radians(14.5))
    disc_ra = (DISC_TEETH + 2.0) / DISC_DP * IN / 2.0
    tip_reach = centre_distance - disc_ra
    if tip_reach <= rb3 + 0.05:
        raise RuntimeError(
            f"disc tips reach {tip_reach:.3f}, third-gear gap floor {rb3:.3f}"
        )
    z_overlap = min(KNOB_SHAFT_Z0 + THIRD_FACE, DISC_Z0 + DISC_FACE) - max(
        KNOB_SHAFT_Z0, DISC_Z0
    )
    if z_overlap < 2.5:
        raise RuntimeError(f"third gear/disc z overlap {z_overlap:.2f} < 2.5")
    log(
        f"gear mesh 12:120 DP38: c2c {centre_distance} (ext {ext:.2f}), 12T"
        f" phased {THIRD_PHASE_DEG:+.1f} deg, tip/floor margin {tip_reach - rb3:.3f}"
    )


def _assert_knob_shaft_clearance() -> None:
    """The knob cluster must ride the disc's exact centre distance with its
    air gaps and floats."""
    # R9-68: the collar's rearmost stop is the 12T's front face F, and the
    # front bushing is faced until F to the disc's front face reads
    # FIT_WINDOW with the cluster forward, so the window's minimum is the
    # collar's worst air to the disc.  The model sits at the window's centre.
    collar_disc_air_min = CLUSTER.FIT_WINDOW[0]
    air = DISC_Z0 - CLUSTER.FLOAT_WINDOW_CENTRE - KNOB_SHAFT_Z0
    if air < collar_disc_air_min:
        raise AssertionError(
            f"knob drive collar to disc air {air:.2f} < {collar_disc_air_min}"
            " with the cluster forward -- the collar must stand clear of the disc"
        )
    reach = math.dist(KNOB_SHAFT_XY, STUD_XY)
    if abs(reach - DISC_SPEC.CENTRE_DISTANCE) > 1e-6:
        raise RuntimeError(
            f"knob shaft sits {reach:.4f} from the stud, the mesh centre"
            f" distance is {DISC_SPEC.CENTRE_DISTANCE}"
        )
    # The arm plate's hub (z -137..-124.4) shares the rack's z band: it must
    # stay under the rack crests at every platen position.
    hub_top = KNOB_SHAFT_XY[1] + ARM_PLATE.HUB_DIA / 2.0
    if hub_top >= RACK_TIP_Y - 0.5:
        raise RuntimeError(
            f"arm plate hub top {hub_top:.2f} too close to the rack crests"
            f" {RACK_TIP_Y:.3f}"
        )
    # The mounted T24 shares the disc hub's z band: radial gap to the hub.
    t24_hub_gap = reach - (REMOVABLE_TIP_R["T24"] + DISC_HUB.HUB_DIA / 2.0)
    if t24_hub_gap < 0.5:
        raise RuntimeError(f"mounted T24 to disc-hub gap {t24_hub_gap:.2f} < 0.5")
    # The MHA-PD-025 front bushing at its largest Ø against the knob stack's
    # largest neighbours, whatever their z: the T24's tips, the thumbnut and
    # the drive collar.
    bushing_r = (FRONT_BUSHING.OD + printed_band_mm(FRONT_BUSHING.OD_PLACES)) / 2.0
    bushing_air = (
        reach
        - bushing_r
        - max(
            REMOVABLE_TIP_R["T24"],
            max(THUMBNUT_HEAD_DIA, THUMBNUT_FLANGE_DIA) / 2.0,
            KNOB_COLLAR_R_WORST,
        )
    )
    if bushing_air < 1.0:
        raise RuntimeError(f"front bushing to knob stack air {bushing_air:.2f} < 1.0")
    # The T24 overlaps the disc rim in XY -- they must stay z-separated.
    z_gap = DISC_Z0 - REMOVABLE.SEAT_FACE_Z  # 6.9
    if z_gap < 2.0:
        raise RuntimeError(f"T24/disc z gap {z_gap:.2f} < 2.0")
    # End float: the knob cup's front face behind the arm plate's boss.
    end_float = KNOB_CUP_Z0 - (PLATE_Z0 + ARM_PLATE.BOSS_FACE_Z)
    if abs(end_float - KNOB_SPEC.END_FLOAT) > 1e-9:
        raise RuntimeError(
            f"knob end float {end_float:.4f} is not {KNOB_SPEC.END_FLOAT}"
        )
    # Sleeve float: the ring's rear face in front of the front bushing (the
    # disc's end float less the hub's recess).
    cluster_float = (FRONT_BUSHING_Z0 - FRONT_BUSHING.LENGTH) - CLUSTER.RING_REAR_Z
    if abs(cluster_float - CLUSTER.SLEEVE_FLOAT_WINDOW_CENTRE) > 1e-9:
        raise RuntimeError(
            f"sleeve float {cluster_float:.4f} is not "
            f"{CLUSTER.SLEEVE_FLOAT_WINDOW_CENTRE}"
        )
    log(
        f"knob shaft at ({KNOB_SHAFT_XY[0]:.3f}, {KNOB_SHAFT_XY[1]:.3f}); plate"
        f" hub {RACK_TIP_Y - hub_top:.2f} under the rack crests; gaps:"
        f" T24/hub {t24_hub_gap:.1f}, front bushing/knob stack {bushing_air:.1f},"
        f" T24/disc z {z_gap:.1f}, collar/disc z"
        f" {air:.2f}; floats: knob {end_float:.2f}, cluster {cluster_float:.2f}"
    )


def _assert_chain_layout() -> None:
    """_chain.py holds the loop in the PRE-MIRROR frame (its KNOB/CRANK centres
    sit at machine +X); pin it to the reflection of OUR machine anchors so the
    mirror_x=True loop lands on the machine (-X) chain wheels."""
    knob_pre = (-KNOB_SHAFT_XY[0], KNOB_SHAFT_XY[1])
    knob_err = max(abs(a - b) for a, b in zip(CHAIN_KNOB_CENTRE, knob_pre))
    if knob_err > 1e-3:
        raise RuntimeError(
            f"_chain KNOB_CENTRE {CHAIN_KNOB_CENTRE} != -KNOB_SHAFT_XY"
            f" ({knob_pre[0]:.4f}, {knob_pre[1]:.4f})"
        )
    # Read pure geometry rather than putting the drive-train recipe on this key.
    from cone_line import X_CRANK, Y_CRANK

    if CHAIN_CRANK_CENTRE != (-X_CRANK, Y_CRANK):
        raise RuntimeError(
            f"_chain CRANK_CENTRE {CHAIN_CRANK_CENTRE} != -drive-train crank"
            f" ({-X_CRANK}, {Y_CRANK})"
        )
    if (TIP_R_T24, TIP_R_T12) != (REMOVABLE_TIP_R["T24"], REMOVABLE_TIP_R["T12"]):
        raise RuntimeError("_chain tip radii diverged from REMOVABLE_TIP_R")
    log(
        f"roller chain layout: loop {CENTRELINE_LEN:.2f}, {LINK_COUNT} links at"
        f" {LINK_PITCH:.4f}, seated on pitch circles ({PITCH_R_T24}/{PITCH_R_T12}),"
        f" plane z {CHAIN_MID_Z}"
    )


def _slack_run_points(step: float = 0.1) -> list[tuple[float, float]]:
    """Machine xy of the chain centreline's slack run (knob wrap's end ->
    crank wrap's start), sampled every ``step`` mm."""
    s0 = CHAIN_WRAP_R_A * CHAIN_SPAN_A
    length = CHAIN_SLACK_R * CHAIN_SPAN_SLACK
    count = math.ceil(length / step)
    return [
        loop_point_tangent(
            s0 + length * i / count,
            dx=CHAIN_KNOB_CENTRE[0],
            dy=CHAIN_KNOB_CENTRE[1],
            mirror_x=True,
        )[:2]
        for i in range(count + 1)
    ]


def _assert_chain_slack_clearance() -> None:
    """R9-30: the slack run of the 68-link loop (the sag the link count
    forces) must clear every placed part that reaches the chain plane --
    in plane by the bought chain's plate half-height, or axially by the band
    the chain sweeps when it floats on the thinnest wheel."""
    z_front = CHAIN_FRONT_Z_WORST
    z_back = REMOVABLE.SEAT_FACE_Z + CHAIN_REACH_REAR_WORST
    half_h = max(CHAIN_PLATE_HALF_H, REMOVABLE.ANSI_PLATE_HEIGHT / 2.0)
    run = _slack_run_points()
    report = []
    for label, axis, radius, front, back in CHAIN_PLANE_ENVELOPES:
        axial = max(front - z_back, z_front - back)
        in_plane = (
            -math.inf
            if axis is None
            else min(math.dist(point, axis) for point in run) - radius - half_h
        )
        if max(axial, in_plane) <= 0.0:
            raise AssertionError(
                f"the chain's slack run reaches the {label}: {in_plane:.2f} in"
                f" plane, {axial:.2f} axially"
            )
        report.append(
            f"{label} {in_plane:.2f}" if axial <= 0.0 else f"{label} z {axial:.2f}"
        )
    log(
        f"chain slack run ({LINK_COUNT} links) clears the chain-plane parts: "
        + ", ".join(report)
    )


async def _place_chain_seed(adapter, part: str, station: int) -> str:
    """Seat ONE chain-pattern seed link at path ``station``, oriented along the
    forward CHORD (pin0->pin1) so both pin axes sit ~on the loop -- the connected
    -linkage chain pattern then fills the rest of the loop. ``_chain`` holds the
    loop in the PRE-MIRROR frame (anchor ``CHAIN_KNOB_CENTRE`` at machine +X), so
    ``mirror_x=True`` reflects each point to the machine (-X) chain plane -- the
    exact machine pose place_component now inserts directly (no mirror layer). The
    achiral link's local-z symmetry keeps that a pure-Z rotation, so the plates
    stay flat in the chain plane. Returns the instance name."""
    x0, y0, _ = loop_point_tangent(
        station * LINK_PITCH,
        dx=CHAIN_KNOB_CENTRE[0],
        dy=CHAIN_KNOB_CENTRE[1],
        mirror_x=True,
    )
    x1, y1, _ = loop_point_tangent(
        (station + 1) * LINK_PITCH,
        dx=CHAIN_KNOB_CENTRE[0],
        dy=CHAIN_KNOB_CENTRE[1],
        mirror_x=True,
    )
    ang = math.degrees(math.atan2(y1 - y0, x1 - x0))
    return await place_component(
        adapter,
        part,
        [x0, y0, CHAIN_MID_Z],
        [0.0, 0.0, ang],
        rot_z_rows(ang),
        ground=True,
        label=f"{part} seed @ station {station}",
    )


async def _insert_roller_chain(adapter) -> None:
    """The drive chain: a native CHAIN COMPONENT PATTERN (connected linkage) of
    alternating inner/outer links along the _chain.py loop.

    Ch. 23: the chain rides the two mounted removables' m2 teeth (T24 knob shaft,
    T12 crank shaft). The loop centreline is authored as a single CLOSED SPLINE
    (one sketch segment) on an offset plane at the chain plane (z = CHAIN_MID_Z);
    two seed links (chain-inner-link @ station 0, chain-outer-link @ station 1)
    are placed tangent; SolidWorks' native ``FeatureChainPattern`` (connected
    linkage, via ``adapter.pattern_components_chain``) fills the loop with the
    alternating INNER (plates + bushings) / OUTER (plates + pins) links. Each
    link's two pin axes (Axis1/Axis2) are the group's path-links, so the pattern
    keeps every plate flat in the chain plane and tangent to the loop.

    The path MUST be one connected segment: SolidWorks never treats the 3-arc +
    taut-line contour as connected (the segments share coordinates but carry no
    coincidence relations, so MakeSketchChain forms 0 paths), hence the spline
    through dense loop samples. The dedicated ``FeatureChainPattern`` one-call API
    is used because the documented CreateDefinition/CreateFeature route returns
    null under pywin32 late binding. See memory/chain-pattern-not-createable-
    late-bound.md.

    Gates: the pattern produced EXACTLY LINK_COUNT links (the loop is sized
    CENTRELINE_LEN = LINK_COUNT * LINK_PITCH with LINK_COUNT even, so the two
    interleaved groups close it seamlessly), every instance sits on the chain
    plane, and its origin (pin0) reads back onto the loop centreline.
    """
    from solidworks_mcp.adapters.base import (
        ComponentChainPatternParameters,
        CreatePlaneParameters,
        RenameFeatureParameters,
    )

    # 1. Path: a single CLOSED SPLINE on an offset plane at the chain plane.
    plane = check(
        f"chain path plane @ z={CHAIN_MID_Z}",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Front Plane", offset=CHAIN_MID_Z
            )
        ),
    )
    plane_name = getattr(plane, "name", plane)
    sk = check("chain path sketch", await adapter.create_sketch(plane_name))
    sketch_name = getattr(sk, "data", sk) if not isinstance(sk, str) else sk
    n_samples = 96
    pts = []
    for i in range(n_samples):
        s = i * CENTRELINE_LEN / n_samples
        x, y, _ = loop_point_tangent(
            s, dx=CHAIN_KNOB_CENTRE[0], dy=CHAIN_KNOB_CENTRE[1], mirror_x=True
        )
        pts.append({"x": x, "y": y})
    pts.append(pts[0])  # close the loop
    check("chain path spline", await adapter.add_spline(pts))
    check("chain path exit", await adapter.exit_sketch())
    # Give the auto-named path sketch a stable, human-readable name so the
    # pattern selects "Spline1@chain-path" independent of feature order.
    check(
        "rename chain path sketch",
        await adapter.rename_feature(
            RenameFeatureParameters(old_name=sketch_name, new_name="chain-path")
        ),
    )
    sketch_name = "chain-path"

    # 2. Two seed links, tangent at the first two stations.
    inner = await _place_chain_seed(adapter, "vn-chain-inner-link", 0)
    outer = await _place_chain_seed(adapter, "vn-chain-outer-link", 1)

    # 3. Native connected-linkage chain pattern fills the loop.
    pattern = check(
        "roller chain (native chain component pattern)",
        await adapter.pattern_components_chain(
            ComponentChainPatternParameters(
                path_segment=f"Spline1@{sketch_name}",
                group1_component=inner,
                group1_link1=f"Axis1@{inner}",
                group1_link2=f"Axis2@{inner}",
                group1_plane=f"Front Plane@{inner}",
                group2_component=outer,
                group2_link1=f"Axis1@{outer}",
                group2_link2=f"Axis2@{outer}",
                group2_plane=f"Front Plane@{outer}",
                # Explicit count (NOT fill_path): _chain sizes CENTRELINE_LEN =
                # LINK_COUNT * LINK_PITCH with LINK_COUNT even, so LINK_COUNT links
                # close the loop seamlessly; fill_path undershoots (leaves a ~2-link
                # seam) because it reserves clearance. For connected linkage the
                # count is PER GROUP and the two groups interleave, so each group
                # gets LINK_COUNT // 2.
                pitch_method="connected_linkage",
                fill_path=False,
                count=LINK_COUNT // 2,
                spacing=LINK_PITCH,
                align_method="tangent",
                options="dynamic",
            )
        ),
    )
    # Rename the auto-named pattern feature (e.g. "LocalChainPattern1") to a
    # stable, human-readable name in the tree.
    pat_name = getattr(pattern, "name", None)
    if pat_name:
        check(
            "rename chain pattern",
            await adapter.rename_feature(
                RenameFeatureParameters(old_name=pat_name, new_name="roller-chain")
            ),
        )

    # The pattern OWNS the seed links' tangent alignment: it re-solves each off
    # the provisional authored chord angle (chord < arc on the wrap, so the two
    # pin axes pull the seed straight -- a fraction of a degree on the tight
    # pitch-circle wrap). Re-anchor the two seeds' pose-ledger entries to that
    # solved pose so the save-time gate checks the intended persistent pose.
    reledger_to_solved(adapter, inner)
    reledger_to_solved(adapter, outer)

    # Hide the path spline: it is construction scaffolding for the pattern, not a
    # rendered feature.
    check("blank chain path sketch", await adapter.blank_sketch("chain-path"))
    blank_reference_geometry(adapter, ((plane_name, "PLANE"),))

    # 4. Gates: enough links, on the chain plane, on the loop centreline.
    links = [
        n
        for n in component_names(adapter)
        if n.startswith(("vn-chain-inner-link", "vn-chain-outer-link"))
    ]
    # EXACT closure: _chain sizes CENTRELINE_LEN = LINK_COUNT * LINK_PITCH with
    # LINK_COUNT even, so the connected-linkage pattern (LINK_COUNT // 2 per group)
    # fills the loop with EXACTLY LINK_COUNT links -- no seam, no band.
    if len(links) != LINK_COUNT:
        raise RuntimeError(
            f"chain pattern produced {len(links)} links, expected exactly {LINK_COUNT}"
        )
    worst = 0.0
    for name in links:
        array = component_transform(adapter, name)
        x, y, z = (array[9] * 1000.0, array[10] * 1000.0, array[11] * 1000.0)
        if abs(z - CHAIN_MID_Z) > 0.5:
            raise RuntimeError(
                f"{name}: link z {z:.3f} off the chain plane {CHAIN_MID_Z}"
            )
        dist = centreline_distance(
            x, y, dx=CHAIN_KNOB_CENTRE[0], dy=CHAIN_KNOB_CENTRE[1], mirror_x=True
        )
        worst = max(worst, dist)
    if worst > 2.0:
        raise RuntimeError(
            f"chain links sit up to {worst:.2f} mm off the loop centreline"
        )
    log(
        f"roller chain: native connected-linkage chain pattern, {len(links)} links"
        f" (worst off-loop {worst:.2f} mm)"
    )


def _shown_planes(adapter) -> set[str]:
    """The assembly's reference planes that would render if saved now."""
    return {
        name
        for name, kind in visible_reference_geometry(adapter.currentModel, ASM_NAME)
        if kind == "plane"
    }


def hide_generated_planes(adapter, shown_before: set[str], step: str) -> list[str]:
    """Hide the reference planes ``step`` generated and prove each one hidden.

    SolidWorks' chain pattern and Belt/Chain features author their own
    construction in the assembly tree.  The adapter hides the sketches it
    knows about; a plane either feature generates is named by SolidWorks
    (the #950 save check caught 'PLANE2' on integ e12b78a2a), so it is found
    as a plane shown after ``step`` that was not shown before it.
    """
    generated = sorted(_shown_planes(adapter) - shown_before)
    if not generated:
        log(f"{step}: generated no shown reference plane")
        return []
    def owner_of(name: str) -> str:
        assembly = _early_bound(adapter.currentModel, "IAssemblyDoc")
        feature = _early_bound(assembly.FeatureByName(name), "IFeature")
        return str(_early_bound(feature.GetOwnerFeature(), "IFeature").Name)

    # Which feature owns each plane names it in the log (diagnostic only).
    owners = [
        adapter._attempt(lambda n=name: owner_of(n), default="?") for name in generated
    ]
    blank_reference_geometry(adapter, tuple((name, "PLANE") for name in generated))
    still = sorted(_shown_planes(adapter) & set(generated))
    if still:
        raise RuntimeError(
            f"{step}: generated plane(s) {still} still shown after BlankRefGeom"
        )
    log(
        f"{step}: hid generated plane(s) "
        + ", ".join(f"{name} (owner {owner})" for name, owner in zip(generated, owners))
    )
    return generated


async def _sprocket_revolute(adapter, name: str, label: str) -> None:
    """Constrain a free-spinning wheel to a fixed Z spin-axis, leaving the
    spin free (the operational/coupled DOF).

    Two axis-to-plane distances pin the central Axis1 (a Z line) in XY -- height
    (Top plane = y) and lateral (Right plane = x) -- and keep it parallel to Z;
    a Front-plane distance pins the axial z. The wheel is a symmetric spur
    gear, so its origin is spin-invariant and the origin ``verify`` passes at
    any spin angle (the spin is pinned separately, or left free + coupled)."""
    o = component_origin(adapter, name)
    await distance_driver(
        adapter,
        named_ref(f"Axis1@{name}", "AXIS"),
        named_ref("Top Plane", "PLANE"),
        o[1],
        label=f"{label} axis height",
        verify=(name, o),
    )
    await distance_driver(
        adapter,
        named_ref(f"Axis1@{name}", "AXIS"),
        named_ref("Right Plane", "PLANE"),
        o[0],
        label=f"{label} axis lateral",
        verify=(name, o),
    )
    await distance_driver(
        adapter,
        named_ref(f"Front Plane@{name}", "PLANE"),
        named_ref("Front Plane", "PLANE"),
        o[2],
        label=f"{label} axial",
        verify=(name, o),
    )


async def build(adapter) -> dict[str, str]:
    # Flip seeds + free-DOF contract: cad/config/assemblies/<ASM_NAME>.yaml.
    activate_assembly_contract(ASM_NAME)
    _assert_fastener_stacks()
    _assert_lock_station_sweep()
    _assert_rack_mesh()
    _assert_gear_mesh()
    _assert_knob_shaft_clearance()
    _assert_chain_layout()
    _assert_chain_slack_clearance()

    # Reset the free-DOF manifest buffer before any *_driver(free_dof_key=...)
    # call: each freed DOF is recorded (never authored) and persisted below.
    reset_dof_manifest()
    check("create_assembly", await adapter.create_assembly())

    # --- support bar + two-piece clamps ---------------------------------------
    # The bar is FIRST so the auto-fixed seed is structure, not the mated platen.
    # Its body is symmetric about machine x=0; the hanger's pivot tap and the
    # latch hook's screw taps are not (see pd_support_bar_spec.py).
    support_bar = await place_component(
        adapter,
        "pd-support-bar",
        [0.0, BAR_CY, BAR_Z],
        [0.0, 0.0, 0.0],
        IDENTITY,
        label="support-bar (the platen bar)",
    )
    # Machine columns at +-197 (west first, to match the pose ledger's -1/-2).
    for sx in (1.0, -1.0):
        # Ry(+90): the arcs' local +X (their depth axis) faces machine -Z.
        for arc in ("sh-column-clamp-front", "sh-column-clamp-back"):
            await place_component(
                adapter,
                arc,
                [sx * COLUMN_X, BAR_CY, COLUMN_Z],
                [0.0, 90.0, 0.0],
                ROT_Y_POS90,
                label=f"{arc} (x{sx * COLUMN_X:+.0f})",
            )
    # Two exact-pose clamp-screw seeds at the east column plus one native
    # multi-seed pattern across the frame. Each rigid seed uses one lock mate.
    clamp_x = sorted(CLAMP_HOLE_X)
    clamp_seeds: list[str] = []
    for index, x in enumerate(clamp_x[:2]):
        target = [x, BAR_CY, BAR_FRONT_Z + CLAMP_CBORE_DEPTH]
        seed = await place_component(
            adapter,
            "vn-clamp-screw",
            target,
            [0.0, 0.0, 0.0],
            IDENTITY,
            ground=False,
            label=f"clamp-screw seed (x{x:+.1f})",
        )
        await lock_mate(
            adapter,
            named_ref(f"Right Plane@{seed}", "PLANE"),
            named_ref(f"Right Plane@{support_bar}", "PLANE"),
            label=f"support clamp-screw seed {index} fixed to bar",
        )
        assert_component_placed(adapter, seed, target, IDENTITY)
        clamp_seeds.append(seed)
    clamp_targets = [[x, BAR_CY, BAR_FRONT_Z + CLAMP_CBORE_DEPTH] for x in clamp_x[2:]]
    clamp_instances = await linear_component_pattern(
        adapter,
        clamp_seeds,
        axis="x",
        spacing_mm=2.0 * COLUMN_X,
        instances=2,
        direction=PatternDirection.REVERSE,
        label="support clamp-screw pattern",
    )
    assert_pattern_targets(
        adapter, clamp_instances, clamp_targets, IDENTITY, "support clamp pattern"
    )

    # --- platen group (hangs on the bar) ---------------------------------------
    # The platen runs as a prismatic slider along X (the paper feed): its local
    # slide axis is held parallel to the Top + Front planes at the slide-line
    # offsets (axis-to-plane distance, no rotational redundancy) and an angle
    # snapshot kills the residual spin. The rack, guides, locks, clips, paper
    # and EVERY platen-riding screw ride it via Lock mates (the old grounded
    # clip screws floated in space while the platen fed -- rework E5). The feed
    # position is COUPLED to the crank through the real gear train below.
    platen = await place_component(
        adapter,
        "pd-platen",
        [PLATE_X0, PLATE_Y0, PLATE_FRONT_Z],
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
    )
    pl_o = component_origin(adapter, platen)
    await distance_driver(
        adapter,
        named_ref(f"Axis1@{platen}", "AXIS"),
        named_ref("Top Plane", "PLANE"),
        pl_o[1],
        label="platen slide height",
        verify=(platen, pl_o),
    )
    await distance_driver(
        adapter,
        named_ref(f"Axis1@{platen}", "AXIS"),
        named_ref("Front Plane", "PLANE"),
        pl_o[2],
        label="platen slide depth",
        verify=(platen, pl_o),
    )
    await angle_driver(
        adapter,
        named_ref(f"Top Plane@{platen}", "PLANE"),
        named_ref("Top Plane", "PLANE"),
        0.0,
        label="platen spin snapshot",
        verify=(platen, pl_o),
    )

    async def _lock_to_platen(name: str, label: str) -> None:
        await lock_mate(
            adapter,
            named_ref(f"Front Plane@{name}", "PLANE"),
            named_ref(f"Front Plane@{platen}", "PLANE"),
            label=f"{label} locked to platen",
        )

    # Rack: Rx(180) -> teeth point down, crests 2 below the platen edge (the
    # machine reflection of the pre-mirror Rz180; z origin on the rack back).
    rack = await place_component(
        adapter,
        "pd-platen-rack",
        [RACK_X0, RACK_Y0, RACK_BACK_Z],
        [180.0, 0.0, 0.0],
        ROT_X_180,
        ground=False,
    )
    await _lock_to_platen(rack, "pd-platen-rack")
    # Guide rails on the platen back, above/below the bar band -- the platen
    # HANGS by the top rail's underside on the bar's top edge.
    guides = []
    for gy in GUIDE_Y:
        # platen-guide is authored into -Z so its native Front is the
        # machinist-facing hole-entry face. Ry(180) maps that local -Z depth
        # back onto the unchanged machine +Z envelope and reverses the
        # symmetric X station set; shifting to the far X end preserves every
        # world-space hole and outside face exactly.
        guide = await place_component(
            adapter,
            "pd-platen-guide",
            [PLATE_X0 + GUIDE_LENGTH, gy, BAR_FRONT_Z],
            [0.0, 180.0, 0.0],
            ROT_Y_180,
            ground=False,
            label=f"platen-guide (y{gy:.1f})",
        )
        await _lock_to_platen(guide, f"platen-guide y{gy:.1f}")
        guides.append(guide)
    # Lock plates on the guide backs, bridging BEHIND the bar (1.0 clear of its
    # back face) and lapping LOCK_RAIL_LIP past each rail's outer edge: top-rail
    # locks hang DOWN over the bar (Rz180), bottom-rail locks bridge UP across
    # the 7 open channel onto the bar band (identity, 2.65 overlap, R9-61 --
    # the plate's height is sized by this station).
    for x_c in LOCK_STATION_X:
        # Machine: the station is measured from the platen's +X edge (the mirror
        # of the pre-mirror left-edge station PLATE_X0 + x_c).
        station = PLATE_X0 + PLATE_WIDTH - x_c
        top = await place_component(
            adapter,
            "pd-guide-lock",
            [station + LOCK_WIDTH / 2.0, LOCK_PLATE_Y[1][1], LOCK_Z0],
            [0.0, 0.0, 180.0],
            rot_z_rows(180.0),
            ground=False,
            label=f"guide-lock (top x{x_c:.0f})",
        )
        await _lock_to_platen(top, f"guide-lock top x{x_c:.0f}")
        bot = await place_component(
            adapter,
            "pd-guide-lock",
            [station - LOCK_WIDTH / 2.0, LOCK_PLATE_Y[0][0], LOCK_Z0],
            [0.0, 0.0, 0.0],
            IDENTITY,
            ground=False,
            label=f"guide-lock (bottom x{x_c:.0f})",
        )
        await _lock_to_platen(bot, f"guide-lock bottom x{x_c:.0f}")
    # Paper holders: mirrored one-piece brass sheets hugging the platen edges.
    # Opposite Z rotations keep each 4 mm flat rail on its screw sockets while
    # both adjacent spring rails point inward over the recording paper.
    for _sx, clip_x, clip_y, rz in CLIP_PLACEMENTS:
        clip = await place_component(
            adapter,
            "pd-platen-clip",
            [clip_x, clip_y, PLATE_FRONT_Z - CLIP_THICKNESS],
            [0.0, 0.0, rz],
            rot_z_rows(rz),
            ground=False,
            label=f"platen-clip (x{clip_x:+.0f}, Rz{rz:+.0f})",
        )
        await _lock_to_platen(clip, f"platen-clip x{clip_x:+.0f} Rz{rz:+.0f}")
    # Recording paper over the platen front face: front 0.5 proud, clear of the
    # edge clips, with the fitted side/top margins. The 0.25-thick sheet leaves 0.25 air
    # behind it (build_pd_platen_paper) so no face lands coplanar on the platen.
    paper_side_margin = (PLATE_WIDTH - PAPER_WIDTH) / 2.0
    paper_top_margin = (
        3.0  # ch30-p002: the sheet's top edge sits just under the plate top
    )
    paper = await place_component(
        adapter,
        "pd-platen-paper",
        [
            PLATE_X0 + paper_side_margin,
            PLATE_Y0 + PLATE_HEIGHT - PAPER_HEIGHT - paper_top_margin,
            PLATE_FRONT_Z - 0.5,
        ],
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
    )
    await _lock_to_platen(paper, "pd-platen-paper")

    # --- platen-riding fasteners (lock-mated seeds + native patterns) ---------
    # The platen owns the feed DOF, so each seed stays lock-mated to that moving
    # body. Native X patterns replicate the regular grids and remain driven by
    # their seeds as the platen travels.
    clip_targets = [
        [x, y, PLATE_FRONT_Z - CLIP_THICKNESS - SCREW_SEAT_BOSS_H]
        for x, y in CLIP_SCREW_XY
    ]
    clip_max_x = max(target[0] for target in clip_targets)
    clip_seed_target = min(
        (target for target in clip_targets if target[0] == clip_max_x),
        key=lambda target: target[1],
    )
    clip_seed = await place_component(
        adapter,
        "vn-fillister-screw",
        clip_seed_target,
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
        label=(
            f"fillister-screw clip seed "
            f"(x{clip_seed_target[0]:+.0f} y{clip_seed_target[1]:.0f})"
        ),
    )
    await _lock_to_platen(
        clip_seed,
        f"clip screw seed x{clip_seed_target[0]:+.0f} y{clip_seed_target[1]:.0f}",
    )
    clip_instances = await grid_component_pattern(
        adapter,
        [clip_seed],
        axis1="x",
        spacing1_mm=clip_max_x - min(target[0] for target in clip_targets),
        instances1=2,
        axis2="y",
        spacing2_mm=max(target[1] for target in clip_targets) - clip_seed_target[1],
        instances2=2,
        direction1=PatternDirection.FORWARD,
        direction2=PatternDirection.REVERSE,
        label="platen clip-screw grid",
    )
    assert_pattern_targets(
        adapter,
        clip_instances,
        [target for target in clip_targets if target != clip_seed_target],
        IDENTITY,
        "platen clip-screw grid",
    )

    # One seed per row at machine +X; five proportional stations run to -X.
    guide_targets = [
        [x, y, PLATE_FRONT_Z + PLATEN_CBORE_DEPTH] for x, y in GUIDE_SCREW_XY
    ]
    guide_max_x = max(target[0] for target in guide_targets)
    guide_seed_target = min(
        (target for target in guide_targets if target[0] == guide_max_x),
        key=lambda target: target[1],
    )
    guide_seed = await place_component(
        adapter,
        "vn-fillister-screw",
        guide_seed_target,
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
        label=(
            f"fillister-screw guide seed "
            f"(x{guide_seed_target[0]:+.0f} y{guide_seed_target[1]:.0f})"
        ),
    )
    await _lock_to_platen(
        guide_seed,
        f"guide screw seed x{guide_seed_target[0]:+.0f} y{guide_seed_target[1]:.0f}",
    )
    guide_instances = await grid_component_pattern(
        adapter,
        [guide_seed],
        axis1="x",
        spacing1_mm=PLATEN_GUIDE_HOLE_X[1] - PLATEN_GUIDE_HOLE_X[0],
        instances1=5,
        axis2="y",
        spacing2_mm=max(target[1] for target in guide_targets) - guide_seed_target[1],
        instances2=2,
        direction1=PatternDirection.FORWARD,
        direction2=PatternDirection.REVERSE,
        label="platen guide-screw grid",
    )
    assert_pattern_targets(
        adapter,
        guide_instances,
        [target for target in guide_targets if target != guide_seed_target],
        IDENTITY,
        "platen guide-screw grid",
    )
    # The exploded sheet moves the guide and clip screws apart: tag each
    # fillister screw with the joint it makes.
    fillister_roles = {
        **{name: CLIP_SCREW_ROLE for name in (clip_seed, *clip_instances)},
        **{name: GUIDE_SCREW_ROLE for name in (guide_seed, *guide_instances)},
    }

    # Two seeds at the right-hand station reproduce at the left-hand station;
    # under-head planes sit on the real 2-mm lock back faces.
    lock_targets = [[x, y, LOCK_Z0 + LOCK_THICK] for x, y in LOCK_SCREW_XY]
    lock_min_y = min(target[1] for target in lock_targets)
    plate_mid_x = PLATE_X0 + PLATE_WIDTH / 2.0
    lock_seed_targets = [
        target
        for target in lock_targets
        if target[0] > plate_mid_x and target[1] == lock_min_y
    ]
    lock_seeds: list[str] = []
    for target in lock_seed_targets:
        seed = await place_component(
            adapter,
            "vn-guide-lock-screw",
            target,
            [0.0, 180.0, 0.0],
            ROT_Y_180,
            ground=False,
            label=f"guide-lock-screw lock seed (x{target[0]:+.0f} y{target[1]:.0f})",
        )
        await _lock_to_platen(
            seed, f"lock screw seed x{target[0]:+.0f} y{target[1]:.0f}"
        )
        lock_seeds.append(seed)
    lock_instances = await grid_component_pattern(
        adapter,
        lock_seeds,
        axis1="x",
        spacing1_mm=LOCK_STATION_X[1] - LOCK_STATION_X[0],
        instances1=2,
        axis2="y",
        spacing2_mm=max(target[1] for target in lock_targets) - lock_min_y,
        instances2=2,
        direction1=PatternDirection.FORWARD,
        direction2=PatternDirection.REVERSE,
        label="platen lock-screw grid",
    )
    assert_pattern_targets(
        adapter,
        lock_instances,
        [target for target in lock_targets if target not in lock_seed_targets],
        ROT_Y_180,
        "platen lock-screw grid",
    )

    # --- transgear hanger (behind the bar) ------------------------------------
    # The hanger is structure: every part fixed at its contract station. The
    # arm stands on the pivot spacer and swings on the shoulder screw; at the
    # latched pose its frame is (U, N) from the pivot P.
    arm_rows = rot_z_rows(ARM_ANGLE_DEG)
    await place_component(
        adapter,
        "pd-transgear-pivot-spacer",
        [PIVOT_XY[0], PIVOT_XY[1], SPACER_Z0],
        [0.0, 0.0, 0.0],
        IDENTITY,
    )
    await place_component(
        adapter,
        "pd-transgear-arm",
        [PIVOT_XY[0], PIVOT_XY[1], ARM_Z0],
        [0.0, 0.0, ARM_ANGLE_DEG],
        arm_rows,
    )
    # Rx(+90): the shoulder runs to -Z, bottoming on the bar's back face.
    await place_component(
        adapter,
        "vn-transgear-pivot-screw",
        [PIVOT_XY[0], PIVOT_XY[1], PIVOT_SCREW_Z0],
        [90.0, 0.0, 0.0],
        ROT_X_POS90,
    )
    # MHA-VN-049 (identity: +Z axial) in the arm's spot face, under the head.
    await place_component(
        adapter,
        "vn-transgear-pivot-spring",
        [PIVOT_XY[0], PIVOT_XY[1], PIVOT_SPRING_Z0],
        [0.0, 0.0, 0.0],
        IDENTITY,
    )
    await place_component(
        adapter,
        "pd-transgear-arm-plate",
        [KNOB_SHAFT_XY[0], KNOB_SHAFT_XY[1], PLATE_Z0],
        [0.0, 0.0, ARM_ANGLE_DEG],
        arm_rows,
    )
    for k, (x, y) in enumerate(PLATE_SCREW_XY, start=1):
        await place_component(
            adapter,
            "vn-transgear-arm-plate-screw",
            [x, y, PLATE_SCREW_Z0],
            [90.0, 0.0, 0.0],
            ROT_X_POS90,
            label=f"transgear-arm-plate-screw #{k} (station {ARM.PLATE_TAP_STATIONS[k - 1]})",
        )
    await place_component(
        adapter,
        "vn-transgear-latch-pin",
        list(LATCH_PIN_POS),
        [0.0, 0.0, ARM_ANGLE_DEG - 90.0],
        rot_z_rows(ARM_ANGLE_DEG - 90.0),
    )
    # Latch hook MHA-PD-014 behind the bar: the one-piece hook by translation,
    # its base on the bar's back face, its two screws through the base into
    # the bar's taps.
    await place_component(
        adapter,
        "pd-latch-hook",
        LATCH_HOOK_POS,
        [0.0, 0.0, 0.0],
        IDENTITY,
        label="latch-hook (spring latch of the swing cluster)",
    )
    for x, y, z in HOOK_BRACKET_SCREW_POS:
        await place_component(
            adapter,
            "vn-latch-hook-bracket-screw",
            [x, y, z],
            [90.0, 0.0, 0.0],
            ROT_X_POS90,
            label=f"latch-hook-bracket-screw (x{x:.1f})",
        )
    log(
        f"latch hook x {HOOK.BBOX_X[0]:.2f}..{HOOK.BBOX_X[1]:.2f},"
        f" y {HOOK.BBOX_Y[0]:.2f}..{HOOK.BBOX_Y[1]:.2f},"
        f" z {HOOK.BBOX_Z[0]:.2f}..{HOOK.BBOX_Z[1]:.2f}"
        f" (base on the bar's back face, ear x {HOOK.X_B - HOOK.SHEET_T:.2f}"
        f"..{HOOK.X_B:.2f}, pin hole at x {HOOK.PIN_HOLE_XY[0]:.2f}"
        f" y {HOOK.PIN_HOLE_XY[1]:.2f})"
    )

    # --- disc cluster on the pin S ----------------------------------------------
    # Ry(180): the pin's stations run from its head seat on the arm's rear face
    # to -Z, its shank pressed through the arm's reamed bore.
    await place_component(
        adapter,
        "pd-transgear-pin",
        [STUD_XY[0], STUD_XY[1], PIN_Z0],
        [0.0, 180.0, 0.0],
        ROT_Y_180,
    )
    # Ry(180): the rear bushing's arm face on the arm's front face, its sleeve
    # face REAR_BUSHING.LENGTH forward (faced to fit, model at nominal).
    await place_component(
        adapter,
        "pd-transgear-rear-bushing",
        [STUD_XY[0], STUD_XY[1], REAR_BUSHING_Z0],
        [0.0, 180.0, 0.0],
        ROT_Y_180,
    )
    # 120T DP38 reducer disc on the feed sleeve's seat, FREE (revolute below) --
    # gear-mated to the knob shaft's 12T. Identity spin: a tooth points along
    # the S -> K line (MESH_ANGLE is a multiple of its 3-deg pitch).
    disc = await place_component(
        adapter,
        "pd-rack-pinion",
        [STUD_XY[0], STUD_XY[1], DISC_Z0],
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
        label="rack-pinion (120T reducer disc)",
    )
    await _sprocket_revolute(adapter, disc, "reducer disc")
    # The 12T DP30 feed sleeve runs on the pin with its rear face on the rear
    # bushing (Ry180, teeth forward to the disc seat) and meshes the teeth-down
    # rack; the hub keyed on its D-flat and the three disc
    # screws make one cluster with the disc, so each is LOCKED to it (net DOF
    # unchanged).
    feed = await place_component(
        adapter,
        "pd-transgear-feed-pinion",
        [STUD_XY[0], STUD_XY[1], FEED_Z0],
        [0.0, 180.0, 0.0],
        ROT_Y_180,
        ground=False,
    )
    await lock_mate(
        adapter,
        named_ref(f"Front Plane@{feed}", "PLANE"),
        named_ref(f"Front Plane@{disc}", "PLANE"),
        label="feed pinion locked to the disc",
    )
    hub = await place_component(
        adapter,
        "pd-transgear-disc-hub",
        [STUD_XY[0], STUD_XY[1], DISC_Z0],
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
    )
    await lock_mate(
        adapter,
        named_ref(f"Front Plane@{hub}", "PLANE"),
        named_ref(f"Front Plane@{disc}", "PLANE"),
        label="disc hub locked to the disc",
    )
    # Rx(-90): heads on the flange's front face, shanks to +Z through the disc.
    for angle, (x, y) in zip(
        DISC_HUB_GEOM.SCREW_ANGLES_DEG, DISC_SCREW_XY, strict=True
    ):
        disc_screw = await place_component(
            adapter,
            "vn-transgear-disc-screw",
            [x, y, DISC_SCREW_Z0],
            [-90.0, 0.0, 0.0],
            ROT_X_NEG90,
            ground=False,
            label=f"transgear-disc-screw ({angle:.0f} deg)",
        )
        await lock_mate(
            adapter,
            named_ref(f"Front Plane@{disc_screw}", "PLANE"),
            named_ref(f"Front Plane@{disc}", "PLANE"),
            label=f"disc screw at {angle:.0f} deg locked to the disc",
        )
    # Ry(180): the front bushing's rear face on the sleeve's nose, faced to
    # fit; the MHA-VN-047 ring in the pin's groove SLEEVE_FLOAT_WINDOW_CENTRE in
    # front of it, its front face on the groove's load wall.
    await place_component(
        adapter,
        "pd-transgear-front-bushing",
        [STUD_XY[0], STUD_XY[1], FRONT_BUSHING_Z0],
        [0.0, 180.0, 0.0],
        ROT_Y_180,
    )
    await place_component(
        adapter,
        "vn-transgear-retaining-ring",
        [STUD_XY[0], STUD_XY[1], CLUSTER.RING_REAR_Z],
        [0.0, 180.0, 0.0],
        ROT_Y_180,
    )

    # --- knob stack on K ---------------------------------------------------------
    # Mounted T24 removable = the knob-end chain wheel (ch. 23: the roller
    # chain rides the removable's teeth; swapping removables changes the
    # platen ratio). FREE to spin: the belt/chain feature couples it to the
    # crank T12. Front face on the band's BAND_FRONT_Z, identity (the pin
    # holes on machine +/-Y, over the collar's drive pins). Inserted before
    # the T12 and the spare T18, so it is the first transgear-removable.
    t24 = await place_component(
        adapter,
        "pd-transgear-removable",
        [KNOB_SHAFT_XY[0], KNOB_SHAFT_XY[1], REMOVABLE_Z0],
        [0.0, 0.0, 0.0],
        IDENTITY,
        configuration="T24",
        ground=False,
        label="transgear-removable (mounted T24)",
    )
    await _sprocket_revolute(adapter, t24, "T24 knob wheel")
    # The drive collar carries the T24 the way the machine does: coaxial, its
    # front face on the wheel's RearFace, clocked so its drive pins ride the
    # wheel's pin holes (the parallel closes the spin; both frames keep
    # machine X). The whole knob stack keeps T24's single free spin.
    collar = await place_component(
        adapter,
        "pd-transgear-drive-collar",
        [KNOB_SHAFT_XY[0], KNOB_SHAFT_XY[1], KNOB_COLLAR_Z0],
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
    )
    collar_o = component_origin(adapter, collar)
    await coincident_mate(
        adapter,
        named_ref(f"Axis1@{collar}", "AXIS"),
        named_ref(f"Axis1@{t24}", "AXIS"),
        label="drive collar coaxial with the mounted T24",
        verify=(collar, collar_o),
    )
    await coincident_mate(
        adapter,
        named_ref(f"Front Plane@{collar}", "PLANE"),
        named_ref(f"RearFace@{t24}", "PLANE"),
        label="drive collar front face on the T24 rear face",
        verify=(collar, collar_o),
    )
    # The collar origin sits ON the spin axis, so only an off-axis witness (a
    # drive-pin station) separates the two parallel solutions.
    await parallel_mate(
        adapter,
        named_ref(f"Right Plane@{collar}", "PLANE"),
        named_ref(f"Right Plane@{t24}", "PLANE"),
        label="drive collar pins clocked into the T24 pin holes",
        verify=(collar, collar_o),
        witness_local=[0.0, COLLAR.PIN_CIRCLE_RADIUS, 0.0],
    )

    async def _lock_to_collar(name: str, label: str) -> None:
        await lock_mate(
            adapter,
            named_ref(f"Front Plane@{name}", "PLANE"),
            named_ref(f"Front Plane@{collar}", "PLANE"),
            label=f"knob stack: {label} locked to the drive collar",
        )

    # The two MHA-VN-038 dowels pressed through the collar (Rx-90: rounded ends
    # forward in the T24's pin holes), +Y first.
    for k, (x, y) in enumerate(KNOB_DRIVE_PIN_XY, start=1):
        knob_pin = await place_component(
            adapter,
            "vn-transgear-knob-drive-pin",
            [x, y, KNOB_DRIVE_PIN_Z0],
            [-90.0, 0.0, 0.0],
            ROT_X_NEG90,
            ground=False,
            label=f"MHA-VN-038 knob drive pin #{k} (y{y:.1f})",
        )
        await _lock_to_collar(knob_pin, f"drive pin #{k}")
    # MHA-VN-037 spring pin through the shaft core in the collar's rear slot.
    cross_pin = await place_component(
        adapter,
        "vn-transgear-collar-cross-pin",
        [KNOB_SHAFT_XY[0], KNOB_SHAFT_XY[1], CROSS_PIN_Z0],
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
    )
    await _lock_to_collar(cross_pin, "cross pin")
    # Knob shaft MHA-PD-008 on its datum F (the 12T's front face), spun so a gap
    # of its 12T faces the disc's tooth on the S -> K line.
    knob_shaft = await place_component(
        adapter,
        "pd-transgear-knob-shaft",
        [KNOB_SHAFT_XY[0], KNOB_SHAFT_XY[1], KNOB_SHAFT_Z0],
        [0.0, 0.0, THIRD_PHASE_DEG],
        rot_z_rows(THIRD_PHASE_DEG),
        ground=False,
    )
    await _lock_to_collar(knob_shaft, "knob shaft")

    async def _lock_to_shaft(name: str, label: str) -> None:
        await lock_mate(
            adapter,
            named_ref(f"Front Plane@{name}", "PLANE"),
            named_ref(f"Front Plane@{knob_shaft}", "PLANE"),
            label=f"knob stack: {label} locked to the knob shaft",
        )

    # Knurled thumbnut OUTERMOST on the shaft's front thread, its flange's
    # seat on the collar's pilot, the T24 free under it (ch23 p.58/59; R9-70).
    # Rx(-90): local +Y -> -Z, the knurled head at the machine front.
    thumbnut = await place_component(
        adapter,
        "pd-transgear-thumbnut",
        [KNOB_SHAFT_XY[0], KNOB_SHAFT_XY[1], THUMBNUT_Z0],
        [-90.0, 0.0, 0.0],
        ROT_X_NEG90,
        ground=False,
        label="transgear-thumbnut (seated on the collar pilot, retains the T24)",
    )
    await _lock_to_shaft(thumbnut, "thumbnut")
    log(
        f"thumbnut z {THUMBNUT_FRONT_Z:.2f}..{THUMBNUT_Z0:.2f} (seat on the pilot,"
        f" {THUMBNUT_AIR:.2f} proud of the T24 face {REMOVABLE_Z0});"
        f" shaft front {KNOB_SHAFT_FRONT_Z:.2f}"
        f" ({KNOB_SHAFT_FRONT_Z - THUMBNUT_FRONT_Z:+.2f} inside the nut rim,"
        f" engagement {THUMBNUT_ENGAGEMENT:.2f}); tap {THUMBNUT_THREAD}; front-most"
        f" furniture near the knob axis: chain plates to z"
        f" {CHAIN_MID_Z - CHAIN_PIN_HALF_LEN:.2f} (radial gap to the head"
        f" {_chain_inner_wrap_r - THUMBNUT_HEAD_DIA / 2.0:.1f})"
    )
    # Behind the 12T (Rx+90): the thrust ring to the plate hub, the knob cup on
    # the journal's rear end, and the MHA-VN-048 spring pin through both (R9-70).
    ring = await place_component(
        adapter,
        "pd-transgear-knob-thrust-ring",
        [KNOB_SHAFT_XY[0], KNOB_SHAFT_XY[1], KNOB_RING_Z0],
        [90.0, 0.0, 0.0],
        ROT_X_POS90,
        ground=False,
    )
    await _lock_to_shaft(ring, "thrust ring")
    cup = await place_component(
        adapter,
        "pd-transgear-knob-cup",
        [KNOB_SHAFT_XY[0], KNOB_SHAFT_XY[1], KNOB_CUP_Z0],
        [90.0, 0.0, 0.0],
        ROT_X_POS90,
        ground=False,
    )
    await _lock_to_shaft(cup, "knob cup")
    cup_pin = await place_component(
        adapter,
        "vn-transgear-knob-cup-pin",
        [KNOB_SHAFT_XY[0], KNOB_SHAFT_XY[1], KNOB_CUP_PIN_Z0],
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
    )
    await lock_mate(
        adapter,
        named_ref(f"Front Plane@{cup_pin}", "PLANE"),
        named_ref(f"Front Plane@{cup}", "PLANE"),
        label="knob stack: cup pin locked to the knob cup",
    )
    # Crank-end T12 removable = the crank-shaft chain wheel, brought over from
    # drive-train so the chain seats on BOTH sprockets locally. Placed at the
    # MACHINE crank centre = -CHAIN_CRANK_CENTRE (the pre-mirror _chain anchor,
    # == -drive-train (X_CRANK, Y_CRANK); _assert_chain_layout pins this).
    # On the same band as the T24 (front face BAND_FRONT_Z, identity: its pin
    # holes on machine +/-Y over the crankshaft's drive pins, which
    # drive-train places). FREE to spin -- this is the crank input, the
    # single operational DOF.
    t12 = await place_component(
        adapter,
        "pd-transgear-removable",
        [-CHAIN_CRANK_CENTRE[0], CHAIN_CRANK_CENTRE[1], REMOVABLE_Z0],
        [0.0, 0.0, 0.0],
        IDENTITY,
        configuration="T12",
        ground=False,
        label="transgear-removable (crank chain wheel T12)",
    )
    await _sprocket_revolute(adapter, t12, "T12 crank wheel")
    # The roller chain looping both removables (_assert_chain_layout pins the
    # _chain.py anchors to KNOB_SHAFT_XY / the drive-train crank).
    shown = _shown_planes(adapter)
    await _insert_roller_chain(adapter)
    hide_generated_planes(adapter, shown, "roller chain pattern")

    # --- operational coupling (every stage a real mate) ------------------------
    # (1) The native Belt/Chain assembly feature couples the crank T12 <-> knob
    # T24 exactly as the roller chain physically does: SAME rotation sense (both
    # sprockets turn the same way -- a gear mate models an external mesh and
    # REVERSES) at the tooth ratio 12:24 = 0.500 (each link engages one tooth,
    # so rev_T12 * 12 == rev_T24 * 24). The typed diameters are therefore the
    # per-tooth effective N * p / pi, not the #25 pitch diameters p / sin(pi/N)
    # whose 0.5043 ratio would bake a 0.9% feed error into the coupling. The
    # pulley members are each sprocket's Axis1 DATUM AXIS, not a face: with a
    # face member SW bakes the picked face's diameter -- on these sprockets the
    # tooth-TIP cylinder (0.529, a ~5.7% feed error) -- into the EngageBelt
    # coupling mate and no definition-level route rewrites it; an axis has no
    # diameter to steal, so the typed diameters drive the mate exactly (probed
    # live 2026-07-06, ratio +0.5000; see
    # memory/belt-chain-feature-com-binding.md). The adapter reads the mate's
    # own D1/D2 back and fails loud on a mismatch. EngageBelt authors the
    # coupling mates; CreateBeltPart stays off -- the roller-chain component
    # pattern above is the visual. Both sprockets stay FREE (Axis1 pinned,
    # spin-only via _sprocket_revolute), so the belt constrains only their
    # relative rotation -- 0 net free DOF added.
    from solidworks_mcp.adapters.base import BeltChainParameters

    shown = _shown_planes(adapter)
    check(
        "chain coupling T12<->T24 (belt/chain feature, 12:24 teeth)",
        await adapter.insert_belt_chain(
            BeltChainParameters(
                pulley_components=[t12, t24],
                pulley_diameters=[CHAIN_PULLEY_DIA["T12"], CHAIN_PULLEY_DIA["T24"]],
                pulley_member_axes=[f"Axis1@{t12}", f"Axis1@{t24}"],
                location_plane="Front Plane",
                engage_belt=True,
                create_belt_part=False,
                blank_sketch=True,
            )
        ),
    )
    hide_generated_planes(adapter, shown, "belt/chain coupling")
    # (2) GEAR mate 12:120: the third gear (in the knob cluster) drives the
    # reducer disc -- the permanent DP38 mesh the latch arm exists to hold.
    # (2) GEAR mate 12:120: the knob shaft's integral 12T drives the reducer
    # disc -- the permanent DP38 mesh the hanger arm exists to hold.
    await gear_mate(
        adapter,
        named_ref(f"Axis1@{knob_shaft}", "AXIS"),
        named_ref(f"Axis1@{disc}", "AXIS"),
        [THIRD_TEETH, DISC_TEETH],
        label="knob shaft 12T : disc 120T (DP38)",
    )
    # (3) RACK-PINION mate: the feed pinion (locked to the disc) feeds the
    # platen at its own pitch circumference -- pi * 10.16 per rev. The rack
    # linear reference is the RACK's own pitch-line Axis1 (the physical
    # engagement line; the platen follows through its lock mate), the pinion
    # reference is the stud axis. The engagement SENSE is calibrated from the
    # verify:kinematics signed feed assert (2026-07-07 field report: the
    # platen-axis-referenced default fed the paper backward vs the tooth
    # contact; the pitch-axis re-reference still solved reversed at flip=False
    # -- the live gate measured +0.133 mm for feed Z -1.50 deg). flip=True
    # landed the physical sense while the feed pinion was inserted identity.
    # The round-10 sleeve is inserted Ry180, which reverses Axis1@feed (its
    # Top x Right axis, local +Z), so the same flag fed the paper backward
    # again (run 20261001T062924323Z: +0.133 mm for feed Z -1.50 deg);
    # flip=False restores it. Recalibrate HERE (never the probe's FEED_SIGN)
    # if the gate ever fails on sign again.
    await rack_pinion_mate(
        adapter,
        named_ref(f"Axis1@{rack}", "AXIS"),
        named_ref(f"Axis1@{feed}", "AXIS"),
        rack_travel_per_revolution=math.pi * FEED_PD,
        flip=False,
        label="platen feed (feed pinion on the rack)",
    )
    # (4) The crank spin is a FREED operational DOF: its drive spec is
    # recorded into the DOF manifest, never authored -- T12 spins free and
    # drives the whole gear+rack train. A spur sprocket is symmetric so the
    # spin pose is cosmetic; pin the local Right-plane dihedral (read live)
    # like drive-train's crank_angle.
    t12_o = component_origin(adapter, t12)
    a_t12 = component_transform(adapter, t12)
    crank_dihedral = math.degrees(math.acos(max(-1.0, min(1.0, a_t12[0]))))
    await angle_driver(
        adapter,
        named_ref(f"Right Plane@{t12}", "PLANE"),
        named_ref("Right Plane", "PLANE"),
        crank_dihedral,
        label=f"crank spin PARK driver (freed in default build; a={crank_dihedral:.2f})",
        verify=(t12, t12_o),
        free_dof_key="crank_spin",
    )

    # Spare T18 removable: the swap chain wheel resting loose on the base, west
    # of the platen (a flat sibling of the mounted T24 above).
    await place_component(
        adapter,
        "pd-transgear-removable",
        list(SPARE_GEAR_POS),
        [-90.0, 0.0, 0.0],
        ROT_X_NEG90,
        configuration="T18",
        label="transgear-removable (spare T18)",
    )

    # Certify the AS-BUILT model. ONE freed operational DOF: the crank spin
    # (its drive spec recorded above, never authored), which drives the
    # chain-coupled knob cluster, the gear-mated disc + feed pinion, and the
    # rack-fed platen. Target the SPECIFIC T12 crank instance (not the shared
    # ``pd-transgear-removable`` stem: the T24 knob + T18 spare share it, so a
    # stem check would pass even if T24 were free and the crank T12 pinned --
    # codex #189).
    assert_free_dof_necessity(adapter, 1, required_instances=(t12,))
    write_dof_manifest(ASM_NAME)
    check_no_interference(
        adapter,
        allowed_pairs=allowed_interference_pairs(ASM_NAME),
        chain_mounts=mounted_wheels(),
    )
    # Machine coords put the output/paper side at -Z, so SolidWorks' native Front
    # renders the machine BACK (chain and transgear cluster mirrored). Re-base the
    # standard views (same as the top assembly) so the saved doc and the _front
    # render show the true machine front. Geometry untouched.
    remap_front_to_machine_front(adapter)
    # Title-block identity for the assembly drawing (draw_pd_paper_drive_assembly.py):
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
    # Both drawing configurations own the explode: the exploded sheet's view
    # at 1:3 references Default Simplified.
    author_in_drawing_configurations(
        adapter,
        ASM_NAME,
        lambda configuration: create_paper_drive_explode(
            adapter, fillister_roles, configuration
        ),
    )
    return await save_assembly_and_images(adapter, ASM_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
