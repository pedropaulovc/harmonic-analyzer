r"""Reproduction script: paper-drive subassembly (book ch. 22-23, 25).

The orthogonal time-base of the plotter: the platen carries the recording paper
across the pen as the operator turns the crank, driven through the translational
gearing, in machine coordinates (assembly origin = base origin; base top
y = 50.8; the output side is -Z). Rebuilt against the primary references
(memory/paper-drive-rework.md) and the paper-drive geometry contract: ONE
support bar, two-piece column clamps, the hanging platen (guides + locks), the
swinging transgear hanger behind the bar, and the REAL power train:

    selected crank wheel --(belt/chain, tooth ratio)--> selected knob wheel
      --(drive collar: two pressed drive pins + D-flat, LOCK)--> knob shaft
      with its source-selected stock-form 15T 48DP PA20 reducer pinion
      --(GEAR mate 15:150)--> 150T 48DP PA20 disc
      --(LOCK: brass hub + feed sleeve)--> stock-form 12T 32DP PA20 feed pinion
      --(RACK-PINION mate, reference pitch circumference)--> rack --(LOCK)--> platen

Operational kinematics: the crank-end sprocket spin is the ONE free
operational DOF -- drag it and the whole feed train follows the feed law in
``paper_drive_geom``, using the mounted selections in ``pd_transgear_removable_spec``.
Every stage is a real SolidWorks mate on geometrically meshed gears. The hanger arm
pivots on the bar and carries the stud, so the 15T:150T mesh is permanent. The drive spec
is recorded into the DOF manifest for the transient verify:kinematics replay,
never authored.
The source-bound frozen rack qualifier is conditional on the entire PRINTED
admitted manufactured family and an isolated feed datum, not whole-unit SHAKE
or I+B. Native builds read its verified cache; they never run the diagnostic
proof. Native geometry/model compatibility is not actual shop admission;
real receiving and loaded-inspection data remain separately required.

* ONE support bar (28 x 9 x 452, book p.62 "the bar that the platen rides on"),
  front face on the platen back, clamped to each column by a FRONT + BACK
  semi-arc pair closed by two long screws whose heads show on the bar front
  (ch30 p002).
* Platen group (HANGS on the bar): platen + two full-width back guide rails
  (above/below the bar band) + 4 1/16-sheet lock plates bridging behind the
  bar (held by low slotted pan-head guide-lock screws) + the teeth-down rack
  at the bottom edge (crest drop derived from the shifted feed mesh) + two
  bright-brass edge clips + the paper sheet + ALL its screws -- everything
  lock-mated to the platen so the whole group feeds together.
* Transgear hanger (behind the bar): the arm stands on the pivot spacer and
  swings on the shoulder pivot screw in the bar's tap; the stepped stud in the
  arm carries the feed sleeve (12T 32DP PA20), the 150T disc and its brass hub,
  closed by the hub cap. The arm plate, screwed to the arm, bores the knob
  shaft, whose integral 15T meshes the disc; the thrust ring and the knob cup
  (set on a feeler, cross-pinned to the journal) set its end float. On the
  shaft's front D-core the drive collar (pressed drive pins, matching D-bore) carries
  selected knob removable CHAIN-WRAPPED at the z -155.7 chain plane, and the
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
Engaged travel is limited by the source-qualified finite rack domain, including
the complete located recording-paper sweep. The final native guard observes
the actual cut-end/stud-axis datums and pays the whole loaded axis family;
these are operating limits, not newly modelled hardware stops.

Dimensions: memory/paper-drive-rework.md; cad/DIMENSIONS.md ch. 22-23, 25.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pd_paper_drive_assembly.py
"""

from __future__ import annotations

import math
import sys

from paper_drive_rack_travel import RackOperatingDomain

from _chain import (
    CENTRELINE_LEN,
    CRANK_CENTRE as CHAIN_CRANK_CENTRE,
    KNOB_CENTRE as CHAIN_KNOB_CENTRE,
    LINK_COUNT,
    LINK_PITCH,
    PIN_HALF_LEN as CHAIN_PIN_HALF_LEN,
    CRANK_PITCH_R,
    KNOB_PITCH_R,
    PLATE_HALF_H as CHAIN_PLATE_HALF_H,
    SLACK_R as CHAIN_SLACK_R,
    SPAN_A as CHAIN_SPAN_A,
    SPAN_SLACK as CHAIN_SPAN_SLACK,
    CRANK_TIP_R,
    KNOB_TIP_R,
    WRAP_R_A as CHAIN_WRAP_R_A,
    centreline_distance,
    loop_point_tangent,
)
from _check import check, log
from _com import _early_bound
from _component_references import component_identity, component_reference_names
from sh_vn_chain_link_spec import INNER_LINK_CONFIGURATION, OUTER_LINK_CONFIGURATION
from _appearance import POLISHED_STEEL
from _custom_properties import apply_custom_properties
from _session import run_build
from _dimensions import drive_dimension, set_global
from _drawing_marks import DRAWN_BY, mark_dimensions_for_drawing
from _drawing_precision import _named_dimension, apply_drawing_precision
from _drawing_tolerances import set_dimension_bilateral_tolerance
from _feature_tree import name_last_feature
from _sketch import (
    SketchDims,
    anchor_point_to_origin,
    blank_sketch,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
import pd_paper_drive_knob_setting_spec as KNOB_SETTING
from _assembly import (
    _rebuilt_component_name,
    activate_assembly_contract,
    angle_driver,
    apply_component_color,
    author_in_drawing_configurations,
    assembly_title_properties,
    assert_component_placed,
    assert_free_dof_necessity,
    check_no_interference,
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
    set_component_reference,
    world_point,
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
    euler_from_rows,
    compose_rows,
    rot_z_rows,
)
from _cone_axis_constants import FRAME_FRONT_COLUMN_Z
from fr_harmonic_base_spec import STACK_HEIGHT as BASE_DECK_Y
from _pd_paper_drive_explode import create_paper_drive_explode

ASM_NAME = "pd-paper-drive"

ROT_Y_180 = [[-1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, -1.0]]
ROT_X_180 = [[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]]

# --- machine anchors ---------------------------------------------------------
import pd_latch_hook_geometry as HOOK  # noqa: E402
import pd_support_bar_spec as BAR  # noqa: E402
import pd_transgear_arm_geometry as ARM  # noqa: E402
import pd_transgear_arm_spec as ARM_SPEC  # noqa: E402
from build_pd_support_bar import (  # noqa: E402
    BAR_HEIGHT,
    BAR_LENGTH,
    CLAMP_CBORE_DEPTH,
    CLAMP_CBORE_DIA,
    CLAMP_HEAD_RECESS,
    CLAMP_HOLE_DIA,
    CLAMP_HOLE_X,
)
from _column_clamp_interface import ARC_DEPTH as ARC_FRONT_DEPTH, BAR_DEPTH  # noqa: E402
from sh_column_clamp_back_geom import (  # noqa: E402
    BLOCK_DEPTH as ARC_BACK_BLOCK_DEPTH,
    GRIP_OFFSET as ARC_BACK_GRIP_OFFSET,
    HOLE_SPEC as CLAMP_RECEIVER_SPEC,
)

COLUMN_X = 197.0
COLUMN_Z = FRAME_FRONT_COLUMN_Z
# Depth chain: the front arc's front face (-129.4) carries the bar's back
# face; the bar's front face (-138.9) carries the platen's back face.
BAR_BACK_Z = COLUMN_Z - ARC_FRONT_DEPTH  # -129.4
BAR_FRONT_Z = BAR_BACK_Z - BAR_DEPTH  # -138.9
BAR_Z = (BAR_FRONT_Z + BAR_BACK_Z) / 2.0  # -134.15 bar centre

# --- platen (hangs on the bar) ----------------------------------------------
from pd_platen_spec import (  # noqa: E402
    CBORE_DEPTH as PLATEN_CBORE_DEPTH,
    CBORE_DIA as PLATEN_CBORE_DIA,
    DRAWING_PRECISION_BY_NAME as PLATEN_PRECISION,
    GUIDE_HOLE_DIA as PLATEN_GUIDE_HOLE_DIA,
    GUIDE_HOLE_X as PLATEN_GUIDE_HOLE_X,
    GUIDE_HOLE_Y as PLATEN_GUIDE_HOLE_Y,
    HEAD_RECESS as PLATEN_HEAD_RECESS,
    PLATE_HEIGHT,
    PLATE_THICKNESS,
    PLATE_WIDTH,
    SOCKET_BOSS_DIA as PLATEN_SOCKET_BOSS_DIA,
    SOCKET_BOSS_FILLET_R as PLATEN_BOSS_FILLET_R,
    SOCKET_BOSS_H as PLATEN_BOSS_H,
    SOCKET_SPEC as PLATEN_SOCKET_SPEC,
    SOCKET_THREAD_ENGAGEMENT as PLATEN_SOCKET_ENGAGEMENT,
    SOCKET_XY as PLATEN_SOCKET_XY,
    UNIT as PLATEN_UNIT,
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
)

# The printed bands the lock-station sweep judges the platen's lock stack at:
# the same spec constants the guide and lock builds author on their model
# dimensions, so the sheets and the sweep read one source.
from _fit_deviations import deviations  # noqa: E402
from _printed_tolerance import printed_band_mm, printed_deviations  # noqa: E402
from pd_guide_lock_spec import (  # noqa: E402
    DRAWING_PRECISION_BY_NAME as LOCK_PRECISION,
    HOLE_PATTERN_X as LOCK_HOLE_PATTERN_X,
    HOLE_XY as LOCK_HOLE_XY,
    HOLE_Y as LOCK_HOLE_Y,
    LOCK_THICK_BAND,
    UNIT as LOCK_UNIT,
)
from pd_platen_guide_spec import (  # noqa: E402
    GUIDE_DEPTH_BAND,
    GUIDE_DEPTH_PLACES,
    LOCK_GAP_FIT,
    TAP_Y as GUIDE_TAP_Y,
    UNIT as GUIDE_UNIT,
)
from build_pd_platen_clip import (  # noqa: E402
    CLIP_LENGTH,
    CLIP_THICKNESS,
    HOLE_INSET as CLIP_HOLE_INSET,
    HOLE_Y as CLIP_HOLE_Y,
    HOLE_DIA as CLIP_HOLE_DIA,
)
from sh_vn_clamp_screw_spec import (  # noqa: E402
    HEAD_DIA as CLAMP_SCREW_HEAD_DIA,
    HEAD_H as CLAMP_SCREW_HEAD_H,
    SHANK_DIA as CLAMP_SCREW_DIA,
    SHANK_LEN as CLAMP_SCREW_LEN,
)
from sh_vn_brass_fillister_screw_spec import (  # noqa: E402
    HEAD_DIA as FILLISTER_HEAD_DIA,
    HEAD_H as FILLISTER_HEAD_H,
    SHANK_DIA as FILLISTER_SHANK_DIA,
    SHANK_LEN as FILLISTER_SHANK_LEN,
)
from pd_vn_platen_clip_screw_spec import (  # noqa: E402
    HEAD_DIA as CLIP_SCREW_HEAD_DIA,
    HEAD_H as CLIP_SCREW_HEAD_H,
    SHANK_DIA as CLIP_SCREW_SHANK_DIA,
    SHANK_LEN as CLIP_SCREW_SHANK_LEN,
    THREAD as CLIP_SCREW_THREAD,
)

# The guide-lock screws alone are low slotted pan heads (R9-31): a fillister
# head on the lock back would sweep into the hanger arm as the platen feeds
# (_assert_lock_station_sweep).
from pd_vn_guide_lock_screw_spec import (  # noqa: E402
    HEAD_DIA as LOCK_SCREW_HEAD_DIA,
    HEAD_H as LOCK_SCREW_HEAD_H,
    LOCK_SET_EDGE_REACH,
    SHANK_DIA as LOCK_SCREW_SHANK_DIA,
    SHANK_LEN as LOCK_SCREW_SHANK_LEN,
)
from pd_platen_rack_spec import (  # noqa: E402
    ADDENDUM as RACK_ADDENDUM,
    BAR_HEIGHT as RACK_BAR_HEIGHT,
    BAR_LENGTH as RACK_BAR_LENGTH,
    BAR_THICKNESS as RACK_BAR_THICKNESS,
    FIRST_GAP_X as RACK_FIRST_GAP_X,
    RACK_THICKNESS as RACK_TEETH_THICKNESS,
    RACK_Z0 as RACK_TEETH_Z_INSET,
    PITCH as RACK_PITCH,
    DRAWING_PRECISION_BY_NAME as RACK_PRECISION,
    UNIT as RACK_UNIT,
)
import paper_drive_geom as PAPER_GEOMETRY  # noqa: E402
import _paper_drive_placement as PAPER_PLACEMENT  # noqa: E402
import _recording_geometry as RECORDING_GEOMETRY  # noqa: E402

PLATE_X0_PHOTO = -33.213
# ch30-p002 Pose Studio refit (2026-07-23): the platen's top-left reference
# corner was hand-aligned at (-33.213, 408.054) in the current assembly. The
# width is 300 * 0.8988 and the user-confirmed H:W ratio is 1:2, so preserving
# that top edge puts the resized plate bottom here. The fit's z delta remains
# ignored: a near-front view does not constrain depth. The placed PLATE_X0 is
# this photo x snapped to the rack's mesh phasing (below, after the stud).
PLATE_Y0 = PAPER_PLACEMENT.PLATEN_BOTTOM_Y
PLATE_FRONT_Z = BAR_FRONT_Z - PLATE_THICKNESS  # -142.75

# The platen hangs: the bar's top edge carries the top guide's underside. The
# bottom rail's underside sits just over the rack backer on the platen back.
GUIDE_Y = (283.734, 317.734)  # bottom / top rail seats (machine y)
BAR_TOP_Y = GUIDE_Y[1]
BAR_CY = BAR_TOP_Y - BAR_HEIGHT / 2.0  # 304.907
# The SH column clamps' screw line, below the bar's centre (pd_support_bar_spec).
CLAMP_Y = BAR_CY + BAR.CLAMP_TAP_Y  # 303.734
# The bar fills the channel between the rails down to this running clearance
# over the bottom rail's top edge (pd_support_bar_spec.BAR_HEIGHT).
BOTTOM_RAIL_CLEARANCE = 0.98
if (
    abs(BAR_TOP_Y - BAR_HEIGHT - GUIDE_Y[0] - GUIDE_HEIGHT - BOTTOM_RAIL_CLEARANCE)
    > 1e-9
):
    raise AssertionError(
        "the support bar's bottom edge is off the bottom rail's clearance"
    )
LOCK_Z0 = BAR_FRONT_Z + GUIDE_DEPTH  # -128.7: lock plates on the guide backs,
# 0.7 behind the bar's back face -- they bridge the bar so the platen cannot
# fall off it.

# Relocate the rack/backer on the platen to the shifted pitch-line distance,
# retaining the pressed stud, pivot and latch pose.
RACK_TIP_Y = PAPER_PLACEMENT.RACK_TIP_Y
RACK_PITCH_Y = PAPER_PLACEMENT.RACK_PITCH_Y
RACK_Y0 = RACK_TIP_Y + RACK_BAR_HEIGHT  # Rx180: local +Y maps downward
RACK_BACK_Z = BAR_FRONT_Z + RACK_BAR_THICKNESS
RACK_TEETH_BACK_Z = RACK_BACK_Z - RACK_TEETH_Z_INSET
RACK_TEETH_FRONT_Z = RACK_TEETH_BACK_Z - RACK_TEETH_THICKNESS
# Both ride the platen back in one z band, so the bottom rail's underside
# keeps air over the rack backer's tallest received section above the tooth
# tips (paper_drive_geom; the .29 rails grew into the bar's channel for it).
RACK_BACKER_RAIL_AIR_WORST = GUIDE_Y[0] - (
    RACK_TIP_Y + PAPER_GEOMETRY.feed_rack_cut_end_section_maxima_mm()[0]
)
if RACK_BACKER_RAIL_AIR_WORST <= 0.0:
    raise AssertionError(
        f"MHA-PD-11 bottom guide rail meets the MHA-PD-05 rack backer: air "
        f"{RACK_BACKER_RAIL_AIR_WORST:.3f}"
    )

# --- transgear (the real six-gear train) -------------------------------------
from pd_rack_pinion_spec import (  # noqa: E402
    DIAMETRAL_PITCH as DISC_DP,
    FACE_WIDTH as DISC_FACE,
    TEETH as DISC_TEETH,
)
from pd_transgear_feed_pinion_spec import (  # noqa: E402
    FACE_WIDTH as FEED_FACE,
    TEETH as FEED_TEETH,
)
import dt_crankshaft_spec  # noqa: E402
import pd_rack_pinion_spec as DISC_SPEC  # noqa: E402
import pd_transgear_arm_plate_geometry as ARM_PLATE  # noqa: E402
import pd_transgear_arm_plate_spec as ARM_PLATE_SPEC  # noqa: E402
import pd_vn_transgear_arm_plate_locating_pin_spec as LOCATING_PIN  # noqa: E402
import _transgear_arm_plate_locating_interface as LOCATING_INTERFACE  # noqa: E402
import pd_vn_transgear_arm_plate_screw_spec as PLATE_SCREW  # noqa: E402
import transgear_cluster_fit as CLUSTER  # noqa: E402
import pd_cluster_air as CLUSTER_AIR  # noqa: E402
import pd_transgear_disc_hub_geometry as DISC_HUB_GEOM  # noqa: E402
import pd_transgear_disc_hub_spec as DISC_HUB  # noqa: E402
import pd_vn_transgear_disc_screw_spec as DISC_SCREW  # noqa: E402
import pd_transgear_drive_collar_spec as COLLAR  # noqa: E402
import pd_transgear_feed_pinion_spec as FEED  # noqa: E402
import pd_transgear_front_bushing_spec as FRONT_BUSHING  # noqa: E402
import transgear_hanger_joints as HANGER  # noqa: E402
import pd_vn_transgear_knob_cup_pin_spec as CUP_PIN  # noqa: E402
import pd_transgear_knob_cup_spec as CUP  # noqa: E402
import pd_transgear_knob_thrust_ring_spec as RING  # noqa: E402
import pd_vn_transgear_latch_pin_spec as LATCH_PIN  # noqa: E402
import pd_transgear_pin_spec as PIN  # noqa: E402
import pd_vn_transgear_pivot_screw_spec as PIVOT_SCREW  # noqa: E402
import pd_transgear_pivot_spacer_spec as SPACER  # noqa: E402
import pd_vn_transgear_pivot_spring_spec as PIVOT_SPRING  # noqa: E402
import pd_transgear_rear_bushing_spec as REAR_BUSHING  # noqa: E402
import pd_vn_transgear_retaining_ring_spec as E_RING  # noqa: E402
import pd_latch_hook_bracket_screw_spec as HOOK_BRACKET_SCREW  # noqa: E402
import pd_latch_hook_spec as HOOK_SPEC  # noqa: E402

FEED_PD = FEED.PITCH_DIA
RACK_MESH_EXT = FEED.RACK_MESH_EXTENSION
# The pressed stud preserves the latch fixture; the rack's loaded pitch-line
# setting comes from the feed contact law, independently of the reducer centre.
STUD_X = ARM.STUD_MACHINE_X
STUD_XY = PAPER_PLACEMENT.STUD_XY
PIVOT_XY = PAPER_PLACEMENT.PIVOT_XY  # (-58, 303.234)
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


# The reducer's knob bearing follows the shared physical mounting centre.
MESH_ANGLE_DEG = DISC_SPEC.MESH_ANGLE_DEG
KNOB_SHAFT_XY = PAPER_PLACEMENT.KNOB_SHAFT_XY
_PLATE_BORE_XY = _on_arm(ARM_PLATE.BORE_STATION, ARM_PLATE.BORE_OFFSET)
if math.dist(KNOB_SHAFT_XY, _PLATE_BORE_XY) > 1e-3:
    raise AssertionError(
        f"arm plate bore {_PLATE_BORE_XY} is off the knob mesh axis {KNOB_SHAFT_XY}"
    )

# z stack of the hanger (front -Z -> back). It stands behind the bar's back
# face on the pivot spacer, so the arm clears the sliding guide-lock stations
# (_assert_lock_station_sweep).
SPACER_Z0 = BAR_BACK_Z  # -129.4: spacer pressed flush on the shoulder's end
ARM_Z0 = ARM.FRONT_FACE_MACHINE_Z  # -124.4: arm front face on the spacer
if abs(SPACER_Z0 + SPACER.LENGTH - ARM_Z0) > 1e-9:
    raise AssertionError("the arm's front face is off the pivot spacer's rear face")
# Shoulder screw MHA-PD-VN-57 (Rx+90: shank to -Z): the shoulder bottoms on the
# bar's back face; under its head the MHA-PD-VN-63 spring (identity: its O.D.
# rim on the arm's spot-face floor, its I.D. rim under the head) holds the arm
# on the spacer.
PIVOT_SCREW_Z0 = BAR_BACK_Z + PIVOT_SCREW.SHOULDER_LEN  # under the head
PIVOT_SPRING_Z0 = ARM_Z0 + ARM.SPOT_FACE_FLOOR_FROM_FRONT  # the spot-face floor
# Arm plate (rows Rz(theta): local X along U): its mounting plane on
# the arm's rear face; hub forward to the thrust ring, boss rearward.
PLATE_Z0 = ARM_Z0 + ARM.THICKNESS  # -116.4625
PLATE_SCREW_XY = tuple(_on_arm(station) for station in ARM.PLATE_TAP_STATIONS)
PLATE_SCREW_Z0 = PLATE_Z0 + ARM_PLATE.REAR_FACE_Z  # -111.4625: oval heads flush
LOCATING_PIN_XY = tuple(_on_arm(x, y) for x, y in ARM.LOCATOR_SITES_MM)
# Dowels MHA-PD-VN-64 (Rx-90 rows: local +Y to -Z, into the arm). The origin
# end is the PROUD end, 1.70 into the plate, so the 6.0 body runs 4.30 into
# the arm's through ream, short of its front face (the punch-out side). Run 9
# put the origin at the buried end: the body then ran out of the arm's front
# face (9.86 mm^3 of solid arm per dowel).
LOCATING_PIN_Z0 = PLATE_Z0 + LOCATING_INTERFACE.PROUD_MM
if not (
    PLATE_Z0 - ARM.THICKNESS
    < LOCATING_PIN_Z0 - LOCATING_PIN.LENGTH
    < PLATE_Z0
    < LOCATING_PIN_Z0
):
    raise AssertionError("the locating dowels do not sit inside the arm's through reams")
# Latch pin MHA-PD-VN-58 pressed to the floor of the arm tip's hole, along U
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

# Disc cluster on the pin MHA-PD-23 at S (R9-68).  The pin is pressed into the
# arm, its head on the arm's rear face (Ry180: its stations run to machine
# -Z).  On it, rear to front: the MHA-PD-24 rear bushing on the arm's front
# face, the MHA-PD-10 feed sleeve (the disc on its round boss, its front face
# at the D-flat's end wall where the hub's D-bore bears, screwed together),
# the MHA-PD-25 front bushing on the sleeve's nose and the MHA-PD-VN-61 ring in the
# pin's groove.  Nothing in the cluster is faced to fit (#2038 owner ruling
# 2026-10-28): the model carries every printed length at its nominal
# (transgear_cluster_fit), the cluster rearward with its float open at the ring.
PIN_Z0 = PIN.HEAD_SEAT_MACHINE_Z  # -116.4625: the head's underside (Ry180)
if abs(PIN_Z0 - (ARM_Z0 + ARM.THICKNESS)) > 1e-9:
    raise AssertionError("the pin's head is off the arm's rear face")
REAR_BUSHING_Z0 = CLUSTER.REAR_BUSHING_REAR_Z  # -124.4 (Ry180, to -130.09)
if abs(REAR_BUSHING_Z0 - ARM_Z0) > 1e-9:
    raise AssertionError("the rear bushing is off the arm's front face")
FEED_Z0 = REAR_BUSHING_Z0 - REAR_BUSHING.LENGTH  # -130.09 (Ry180, teeth to -143.69)
DISC_Z0 = FEED_Z0 - FEED.DISC_FRONT_STATION  # -147.34: on the hub spigot's flange
if abs(DISC_Z0 - CLUSTER.DISC_FRONT_Z) > 1e-9:
    raise AssertionError("the disc is off the cluster stack's station")
_DISC_SCREW_R = DISC_HUB_GEOM.BOLT_CIRCLE_DIA / 2.0
DISC_SCREW_XY = tuple(
    (
        STUD_XY[0] + _DISC_SCREW_R * math.cos(math.radians(angle)),
        STUD_XY[1] + _DISC_SCREW_R * math.sin(math.radians(angle)),
    )
    for angle in DISC_HUB_GEOM.SCREW_ANGLES_DEG
)
DISC_SCREW_Z0 = DISC_Z0 - DISC_HUB.FLANGE_THICK  # -149.74: heads on the flange
FRONT_BUSHING_Z0 = FEED_Z0 - FEED.OVERALL_LENGTH  # -157.44 (Ry180, to -162.76)
if abs(FRONT_BUSHING_Z0 - CLUSTER.FRONT_BUSHING_REAR_Z) > 1e-9:
    raise AssertionError("the front bushing is off the sleeve's nose")
# The hub's front face, its printed overall leaving it RECESS behind the
# sleeve's nose, so the front bushing bears on the steel nose and traps hub
# and disc.
HUB_FRONT_Z = DISC_Z0 + DISC_HUB.HUB_FRONT_Z
if abs(HUB_FRONT_Z - CLUSTER.HUB_FRONT_Z) > 1e-9:
    raise AssertionError("the hub's front face is off the cluster stack's station")
if abs(DISC_Z0 + DISC_HUB_GEOM.SPIGOT_LENGTH - CLUSTER.STEP_Z) > 1e-9:
    raise AssertionError("the hub's spigot end is off the sleeve's step face")
if abs(HUB_FRONT_Z - FRONT_BUSHING_Z0 - CLUSTER.RECESS_NOMINAL) > 1e-9:
    raise AssertionError("the hub's front face is off its nominal recess behind the nose")
if abs(CLUSTER.RING_FRONT_Z - (PIN_Z0 - PIN.GROOVE_STATION)) > 1e-9:
    raise AssertionError("the ring is off the pin groove's load wall")

import pd_vn_transgear_knob_drive_pin_spec as KNOB_PIN  # noqa: E402
import pd_transgear_removable_spec as REMOVABLE  # noqa: E402
import _sprocket_seat_geometry as seat_geometry  # noqa: E402
import pd_transgear_knob_shaft_spec as KNOB_SPEC  # noqa: E402
from pd_transgear_thumbnut_spec import (  # noqa: E402
    FLANGE_DIA as THUMBNUT_FLANGE_DIA,
    HEAD_DIA as THUMBNUT_HEAD_DIA,
    OVERALL_LENGTH as THUMBNUT_LEN,
    THREAD as THUMBNUT_THREAD,
)

# The knob shaft's integral stock-form 15T 48DP PA20 is the third gear.
THIRD_TEETH = KNOB_SPEC.TEETH
THIRD_DP = KNOB_SPEC.DIAMETRAL_PITCH
THIRD_FACE = KNOB_SPEC.FACE_WIDTH


# Both mounted removables (knob and crank) share ONE band: front face
# BAND_FRONT_Z, rear face on the seat face SEAT_FACE_Z (the knob's drive collar,
# the crankshaft's seat collar), and the chain mid-plane between
# (_sprocket_seat_geometry). Each is placed on its FRONT face (the part's
# Front Plane), identity: holes on machine +/-Y.
REMOVABLE_Z0 = seat_geometry.BAND_FRONT_Z  # -157.1
CHAIN_MID_Z = seat_geometry.CHAIN_MID_Z  # both selected wheels coplanar
REMOVABLE_TIP_R = {
    name: REMOVABLE.outside_dia(teeth) / 2.0 for name, teeth in REMOVABLE.CONFIGS
}
# Belt/chain coupling diameters: the per-tooth effective N * p / pi, so the
# typed ratio is the EXACT tooth ratio a roller chain transmits.
CHAIN_PULLEY_DIA = {
    name: teeth * REMOVABLE.CHAIN_PITCH / math.pi for name, teeth in REMOVABLE.CONFIGS
}
if seat_geometry.PIN_HOLE_ANGLES_DEG != (90.0, 270.0):
    raise AssertionError("identity-placed removables expect pin holes on +/-Y")

# Knob stack on K (front -> back): thumbnut | knob wheel | drive collar | the
# shaft's 15T | thrust ring | arm-plate hub | plate | boss | knob cup.
# The front collar seat stays on the wheel rear; the knob train stands on
# the arm chain's F (transgear_cluster_fit.F_Z), and the collar's rear is
# faced at fit-up to meet it (step collar-rear-faced-to-fit). The model
# collar is its REF nominal, so the facing's remainder shows as a gap at its
# rear, never an overlap, and the fitted body stays in its window.
KNOB_COLLAR_Z0 = seat_geometry.SEAT_FACE_Z  # -154.3
KNOB_SHAFT_Z0 = CLUSTER.F_Z  # F
KNOB_COLLAR_REAR_Z = KNOB_COLLAR_Z0 + COLLAR.LENGTH  # the REF nominal rear
KNOB_COLLAR_FITTED_LENGTH = KNOB_SHAFT_Z0 - KNOB_COLLAR_Z0
KNOB_COLLAR_REAR_GAP = KNOB_SHAFT_Z0 - KNOB_COLLAR_REAR_Z
if KNOB_COLLAR_REAR_GAP < -1e-9:
    raise AssertionError(
        f"the drive collar's nominal rear overlaps F by {-KNOB_COLLAR_REAR_GAP:.4f}"
    )
if not COLLAR.LENGTH_FITTED_MIN <= KNOB_COLLAR_FITTED_LENGTH <= COLLAR.LENGTH_FITTED_MAX:
    raise AssertionError(
        f"the collar faced to F is {KNOB_COLLAR_FITTED_LENGTH:.4f}, outside its fitted "
        f"{COLLAR.LENGTH_FITTED_MIN}..{COLLAR.LENGTH_FITTED_MAX}"
    )
# The two MHA-PD-VN-54 dowels pressed through the collar's holes (Rx-90: pin +Y ->
# -Z), rounded ends DRIVE_PIN_PROUD in front of it, in the wheel's pin holes.
KNOB_DRIVE_PIN_Z0 = seat_geometry.DRIVE_PIN_TIP_Z + KNOB_PIN.LENGTH  # -151.9375
if abs(KNOB_COLLAR_Z0 - seat_geometry.DRIVE_PIN_TIP_Z - COLLAR.DRIVE_PIN_PROUD) > 1e-9:
    raise AssertionError("knob drive-pin tips are off the collar's DRIVE_PIN_PROUD")
if abs(KNOB_PIN.DIA - seat_geometry.DRIVE_PIN_DIA) > 1e-12:
    raise AssertionError("transgear-knob-drive-pin is not the removable's drive pin")
if COLLAR.PIN_CIRCLE_RADIUS != seat_geometry.PIN_CIRCLE_RADIUS:
    raise AssertionError("the collar's pin circle is not the removable's")
# Behind the 15T: the thrust ring to the plate hub's face, the knob cup on the
# journal's rear end END_FLOAT behind the plate's boss (all Rx+90), and the
# MHA-PD-VN-62 spring pin through cup and journal (identity: along machine X,
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

# F, the knob shaft's 15T front face (the drive collar's seat), stands the
# plate hub face, thrust ring and 15T chain ahead of the arm's rear face.
# The disc is no longer fitted to it (#2038): the cluster's printed stack
# places the disc from the same rear face (transgear_cluster_fit), and the
# model's m is the cluster rearward, m_fwd plus the end float.
_F_FROM_ARM_Z = (
    ARM_Z0 + ARM.THICKNESS + ARM_PLATE.HUB_FACE_Z - RING.LENGTH - KNOB_SPEC.FACE_WIDTH
)
if abs(_F_FROM_ARM_Z - KNOB_SHAFT_Z0) > 1e-9 or abs(CLUSTER.F_Z - KNOB_SHAFT_Z0) > 1e-9:
    raise AssertionError("F is off the arm, plate hub and thrust ring chain")
if abs(DISC_Z0 - KNOB_SHAFT_Z0 - CLUSTER.MODEL_M) > 1e-9:
    raise AssertionError("the model's disc is off the cluster stack's station from F")
# The 150T disc's rear face (the MHA-PD-VN-55 tips sit inside it) to the platen's
# front face, cluster rearward on the rear bushing: an air stack in the
# repository's statistical style (pd_cluster_air, #2038 owner ruling
# 2026-10-28).  From the model's nominal air it closes by the clearances --
# the platen forward by its fitted float, magnified by its yaw about the
# bar's end at the near lock; the cluster's tilt on the pin's bore clearance
# (pivot on the rear bushing's smallest Ø9, over the shortest sleeve) at the
# disc rim; the hub's rock on the boss at the rim -- and by the printed
# tolerances: the spacer's length (the arm held on the longest spacer by the
# MHA-PD-VN-63 spring), the bar's depth, the platen's thickness, the thickest
# disc, the rear bushing, tooth and spigot lengths (the disc's chain from the
# arm's front face), the spacer's two faces' squareness tilting the hanger
# about P (Codex P1 on 6c385465d) at the rim's farthest point from P, the
# step, spigot-end and flange squareness and the disc's rear-face
# parallelism at the rim, and the pin's S projected axis zone at the rim
# (absent from this gate before #2038).
PLATEN_YAW_LEVER = (BAR_LENGTH / 2.0) / (BAR_LENGTH / 2.0 - LOCK_STATION_X[0])
# The platen prints its thickness and the rack its backer depth
# (pd_platen_spec / pd_platen_rack_spec DRAWING_PRECISION).
# Each band is the larger printed deviation from the model (the printed value
# rounds off the model nominal).
_PLATEN_THICKNESS_BAND = max(
    map(abs, printed_deviations(PLATE_THICKNESS, PLATEN_PRECISION["Depth"], unit=PLATEN_UNIT))
)
_RACK_THICKNESS_BAND = max(
    map(
        abs,
        printed_deviations(
            RACK_BAR_THICKNESS, RACK_PRECISION["BackerDepth"], unit=RACK_UNIT
        ),
    )
)
DISC_PLATEN_NOMINAL = PLATE_FRONT_Z - (DISC_Z0 + DISC_SPEC.FACE_WIDTH)  # 1.59
CLUSTER_TILT_AT_DISC_RIM = (
    (
        DISC_SPEC.OUTSIDE_DIA
        - (REAR_BUSHING.OD - printed_band_mm(REAR_BUSHING.OD_PLACES, unit=REAR_BUSHING.UNIT))
    )
    / 2.0
    * CLUSTER.BORE_DIAMETRAL_CLEARANCE[1]
    / (FEED.OVERALL_LENGTH - FEED.OVERALL_LENGTH_BAND)
)  # 0.0317
# The hanger tilts about P by the spacer's face squareness
# (transgear_hanger_joints.HANGER_TILT): a point r from P moves r times it.
_P_TO_S = math.dist(PIVOT_XY, STUD_XY)  # 68.81
_P_TO_DISC_RIM = _P_TO_S + DISC_SPEC.OUTSIDE_DIA / 2.0
HANGER_TILT_AT_DISC_RIM = HANGER.HANGER_TILT * _P_TO_DISC_RIM  # 0.2248
HANGER_TILT_AT_FEED_TIPS = HANGER.HANGER_TILT * (
    _P_TO_S + FEED.OUTSIDE_DIA / 2.0
)
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
)
_STEP_AT_RIM = (
    _DISC_RIM_R * FEED.STEP_FACE_PERPENDICULARITY / FEED.STEP_FACE_PERPENDICULARITY_ZONE_DIA
)
_SPIGOT_END_AT_RIM = (
    _DISC_RIM_R
    * DISC_HUB.SPIGOT_END_PERPENDICULARITY
    / DISC_HUB.SPIGOT_END_PERPENDICULARITY_ZONE_DIA
)
_FLANGE_AT_RIM = (
    _DISC_RIM_R
    * DISC_HUB.FLANGE_FACE_PERPENDICULARITY
    / DISC_HUB.FLANGE_FACE_PERPENDICULARITY_ZONE_DIA
)
_DISC_REAR_PARALLELISM = float(
    DISC_SPEC.GEOMETRIC_TOLERANCES_MM["disc rear face parallelism to front"]
)
DISC_MOUNT_WOBBLE = (
    DISC_HUB_ROCK_AT_RIM
    + _STEP_AT_RIM
    + _SPIGOT_END_AT_RIM
    + _FLANGE_AT_RIM
    + _DISC_REAR_PARALLELISM
)
# The pin's axis in its S projected zone tilts the whole cluster; at the rim
# it levers from the step contact's edge, as the hub's rock does.
PIN_ZONE_TILT_AT_DISC_RIM = CLUSTER_AIR.S_ZONE_TILT * (_DISC_RIM_R - DISC_HUB.SEAT_CONTACT_R)
# The least air the disc's rear face keeps to the platen's front (R9-68).
DISC_PLATEN_AIR_MIN = CLUSTER_AIR.PLATEN_AIR_MIN
PLATEN_AIR = CLUSTER_AIR.AirStack(
    "MHA-PD-06 disc to MHA-PD-02 platen air",
    DISC_PLATEN_NOMINAL,
    {
        "platen float at the near lock": LOCK_GAP_FIT[1] * PLATEN_YAW_LEVER,
        "sleeve cocking on the pin": CLUSTER_TILT_AT_DISC_RIM,
        "hub rock on the sleeve boss": DISC_HUB_ROCK_AT_RIM,
        "MHA-PD-20 spacer length": SPACER.LENGTH_BAND,
        "MHA-PD-07 support bar depth": BAR.BAR_DEPTH_BAND,
        "MHA-PD-02 platen thickness": _PLATEN_THICKNESS_BAND,
        "MHA-PD-06 disc thickness": DISC_SPEC.FACE_WIDTH_MAX - DISC_SPEC.FACE_WIDTH,
        **{label: band for label, _, band in (CLUSTER.LRB, CLUSTER.TL, CLUSTER.SP)},
        "MHA-PD-20 spacer rear face perpendicularity": SPACER.REAR_FACE_PERPENDICULARITY
        / SPACER.FACE_PERPENDICULARITY_ZONE_DIA
        * _P_TO_DISC_RIM,
        "MHA-PD-20 spacer front face perpendicularity": SPACER.FRONT_FACE_PERPENDICULARITY
        / SPACER.FACE_PERPENDICULARITY_ZONE_DIA
        * _P_TO_DISC_RIM,
        "sleeve step face perpendicularity": _STEP_AT_RIM,
        "hub spigot end perpendicularity": _SPIGOT_END_AT_RIM,
        "hub flange rear face perpendicularity": _FLANGE_AT_RIM,
        "MHA-PD-06 disc rear face parallelism": _DISC_REAR_PARALLELISM,
        "pin S projected axis zone": PIN_ZONE_TILT_AT_DISC_RIM,
    },
    DISC_PLATEN_AIR_MIN,
)
if abs(
    PLATEN_AIR.terms["MHA-PD-20 spacer rear face perpendicularity"]
    + PLATEN_AIR.terms["MHA-PD-20 spacer front face perpendicularity"]
    - HANGER_TILT_AT_DISC_RIM
) > 1e-9:
    raise AssertionError("the platen stack's spacer terms are not the hanger's tilt")
# Collar and platen air by the governing method (raises if either closes).
CLUSTER_AIRS = CLUSTER_AIR.require_air(PLATEN_AIR)
DISC_PLATEN_AIR = CLUSTER_AIRS["platen_air"]
# The platen stack at the arithmetic worst case: the rack reach below reads it.
DISC_PLATEN_AIR_WORST = PLATEN_AIR.arithmetic_mm
# R9-67/R9-68: the feed sleeve's 12T cuts full depth from its rear face over
# the rack's whole width.  The rack's front face is the platen's back face, so
# the stack above sets how far forward of the sleeve's rear face it reaches,
# less the terms that do not lie between the sleeve and the platen's back
# (the platen's own band, the disc's mount wobble, the rim's tilts, which
# come back as the tilts at the 12T tips).  The disc's front face is the hub
# flange's rear face, a spigot length ahead of the sleeve's step; the stack's
# thickest disc reaches rearward from it.  The platen air is the stack's
# arithmetic worst case, not its governing statistical one: conservative.
CLUSTER_TILT_AT_FEED_TIPS = (
    (
        FEED.OUTSIDE_DIA
        - (REAR_BUSHING.OD - printed_band_mm(REAR_BUSHING.OD_PLACES, unit=REAR_BUSHING.UNIT))
    )
    / 2.0
    * CLUSTER.BORE_DIAMETRAL_CLEARANCE[1]
    / (FEED.OVERALL_LENGTH - FEED.OVERALL_LENGTH_BAND)
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
    - (
        RACK_TEETH_Z_INSET
        + printed_deviations(
            RACK_TEETH_Z_INSET, RACK_PRECISION["RackInset"], unit=RACK_UNIT
        )[0]
    )
)
if FEED.FULL_DEPTH_MIN < RACK_FRONT_FROM_SLEEVE_REAR_WORST:
    raise AssertionError(
        f"MHA-PD-10 12T full depth may stop {FEED.FULL_DEPTH_MIN:.3f} from the rear "
        f"face, inside the rack's worst reach {RACK_FRONT_FROM_SLEEVE_REAR_WORST:.3f}"
    )
# The MHA-PD-24 rear bushing's front face to the MHA-PD-05 rack's back face (its
# Ø9 .X can reach the rack's crests radially): the arm forward on the
# shortest spacer, the bar thinnest, the rack thickest, the bushing
# following the sleeve forward by the cluster's whole end float, and the
# hanger's tilt at the bushing's far rim.
BUSHING_RACK_AIR_NOMINAL = REAR_BUSHING_Z0 - REAR_BUSHING.LENGTH - RACK_BACK_Z  # 2.5
BUSHING_RACK_AIR_WORST = (
    BUSHING_RACK_AIR_NOMINAL
    - SPACER.LENGTH_BAND
    - BAR.BAR_DEPTH_BAND
    - _RACK_THICKNESS_BAND
    - (CLUSTER.SLEEVE_REAR_FORWARD_FROM_ARM[1] - REAR_BUSHING.LENGTH)
    - HANGER.HANGER_TILT
    * (
        _P_TO_S
        + (REAR_BUSHING.OD + printed_band_mm(REAR_BUSHING.OD_PLACES, unit=REAR_BUSHING.UNIT))
        / 2.0
    )
)  # 1.89
if BUSHING_RACK_AIR_WORST < 0.0:
    raise AssertionError(
        "MHA-PD-24 rear bushing enters the MHA-PD-05 rack at the printed worst case: "
        f"air {BUSHING_RACK_AIR_WORST:.4f} (R9-68)"
    )

# Stack D: a bought #25 chain floated REARMOST on the thinnest knob-wheel plate
# reaches chain_reach_rear() behind the seat face; it must keep air to the
# reducer disc's front face.
CHAIN_REACH_REAR_WORST = seat_geometry.CHAIN_REACH_REAR_WORST  # 3.587
CHAIN_DISC_AXIAL_AIR_WORST = DISC_Z0 - (
    seat_geometry.SEAT_FACE_Z + CHAIN_REACH_REAR_WORST
)  # 3.0635 = 6.65 - 3.5865
if CHAIN_DISC_AXIAL_AIR_WORST <= 0.0:
    raise AssertionError(
        f"bought #25 chain reaches the reducer disc: air {CHAIN_DISC_AXIAL_AIR_WORST:.4f}"
    )
# Radially, the only knob-stack feature between the seat face and the disc is
# the drive collar (the pins sit inside it); at its print-worst (largest)
# radius it must stand inside the knob-wheel plates' inner edge, CAD link and ANSI,
# with the wheel floated off-centre on its pins (the crank's same pins, holes
# and bands: dt_crankshaft_spec.WHEEL_SEAT_FLOAT).
KNOB_CHAIN_INNER_R = min(
    REMOVABLE.chain_plate_inner_radius(REMOVABLE.KNOB_TEETH, h)
    for h in (2.0 * CHAIN_PLATE_HALF_H, REMOVABLE.ANSI_PLATE_HEIGHT)
)
KNOB_COLLAR_R_WORST = (COLLAR.OD + max(COLLAR.OD_BAND)) / 2.0  # 8.75
if abs(KNOB_COLLAR_R_WORST - CLUSTER_AIR.COLLAR_RIM_R) > 1e-9:
    raise AssertionError("the collar air stack's rim is not the collar's print-worst rim")
if KNOB_COLLAR_R_WORST + dt_crankshaft_spec.WHEEL_SEAT_FLOAT >= KNOB_CHAIN_INNER_R:
    raise AssertionError("knob drive collar reaches the knob chain plates' inner edge")

# Thumbnut MHA-PD-13 (ch23 p.58/59 + video 4/4 "unscrew the nut that holds the
# other gear in place"): the knurled brass nut OUTERMOST on the knob shaft,
# tapped for the shaft's front thread, its flange's seat face ON the drive
# collar's pilot, faced to stand THUMBNUT_AIR proud of the mounted wheel's front
# face, so the wheel floats free under the flange (R9-70, N-A). Rx(-90): local
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
    raise AssertionError("the thumbnut clamps the knob wheel: its pilot is not proud")
if not (THUMBNUT_FRONT_Z < KNOB_SHAFT_FRONT_Z < THUMBNUT_Z0):
    raise AssertionError(
        f"knob shaft front {KNOB_SHAFT_FRONT_Z} must end inside the thumbnut"
        f" ({THUMBNUT_FRONT_Z} .. {THUMBNUT_Z0})"
    )
# The flange must still RETAIN the wheel: cover its bore with a shoulder.
# The drive-pin tips end inside the wheel's plate, behind the flange's seat.
if THUMBNUT_FLANGE_DIA < seat_geometry.BORE_DIA + 1.0:
    raise AssertionError(
        "thumbnut flange slips into the removable's bore -- retains nothing"
    )
if seat_geometry.DRIVE_PIN_TIP_Z - THUMBNUT_Z0 <= 0.0:
    raise AssertionError("knob drive-pin tips reach the thumbnut flange")
# Front furniture: nothing in this sub sits in front of the knob wheel but the
# chain, whose plates straddle the wheel (z CHAIN_MID_Z +- pin reach) and
# wrap it at the pitch radius -- the nut's head must clear that wrap radially.
_chain_inner_wrap_r = KNOB_PITCH_R - CHAIN_PLATE_HALF_H
if THUMBNUT_HEAD_DIA / 2.0 > _chain_inner_wrap_r:
    raise AssertionError("thumbnut head reaches the chain's inner plate wrap")
# The bought chain floated FRONTMOST reaches CHAIN_REACH_FRONT ahead of the
# seat face (-160.59). The whole nut (and the shaft) lies radially inside the
# ANSI plates' inner edge, so no axial stack exists there; assert the radial
# one.
CHAIN_FRONT_Z_WORST = seat_geometry.SEAT_FACE_Z - seat_geometry.CHAIN_REACH_FRONT  # -160.5865
if max(THUMBNUT_HEAD_DIA, THUMBNUT_FLANGE_DIA) / 2.0 > KNOB_CHAIN_INNER_R:
    raise AssertionError("thumbnut reaches the bought chain's inner plate edge")

# Latch hook MHA-PD-14 (contract §4.4): one formed 0.8 spring-steel piece,
# its base on the bar's back face under two MHA-PD-VN-59 screws, its ear bent
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

# The hook's two MHA-PD-VN-59 #4-40 screws (Rx+90: shanks to -Z) bear on the
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
# +X, and its teeth repeat every 2.4 deg: MESH_ANGLE is a multiple of that, so
# the disc keeps identity spin with a tooth along the S -> K line. The knob
# shaft's integral 15T has a GAP at GAP_AZIMUTH_DEG (a tooth on local +X); the
# spec's FRONT_STACK_PHASE_DEG spins it so a gap faces back along that line.
THIRD_GAMMA = 360.0 / THIRD_TEETH  # 24
_MESH_AZ = 180.0 + MESH_ANGLE_DEG  # 12: from the knob axis toward the stud
THIRD_PHASE_DEG = KNOB_SPEC.FRONT_STACK_PHASE_DEG  # 0: nearest representative
# Rigidly clock the complete mounted front stack to the actual integral
# shaft. Spare inventory and the intentionally visual native chain are separate.
KNOB_FRONT_STACK_ROT = rot_z_rows(THIRD_PHASE_DEG)
KNOB_DRIVE_PIN_ROT = compose_rows(ROT_X_NEG90, KNOB_FRONT_STACK_ROT)
KNOB_DRIVE_PIN_XY = tuple(
    (
        KNOB_SHAFT_XY[0] + side * COLLAR.PIN_CIRCLE_RADIUS * KNOB_FRONT_STACK_ROT[1][0],
        KNOB_SHAFT_XY[1] + side * COLLAR.PIN_CIRCLE_RADIUS * KNOB_FRONT_STACK_ROT[1][1],
    )
    for side in (1.0, -1.0)
)  # local +Y first: DrivePinAxis1, even after the actual assembly spin
# The feed sleeve (Ry180) keeps a tooth on machine +90 deg (90 = 3 * 30), so a
# rack GAP centre must sit exactly on the stud's x. The rack is soldered with
# its ends flush with the platen's (MHA-PD-00 "rack-soldered"), so its gaps
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

# Net platen feed per CRANK revolution through the selected mounted train:
# chain tooth ratio * reduction gear ratio * feed reference circumference.
# The law lives in paper_drive_geom (shared with the kinematics probe and the
# offline error budget) and is only cross-checked here.
from paper_drive_geom import NET_RACK_TRAVEL_PER_CRANK_REV  # noqa: E402

assert math.isclose(
    NET_RACK_TRAVEL_PER_CRANK_REV,
    (REMOVABLE.CRANK_TEETH / REMOVABLE.KNOB_TEETH)
    * (THIRD_TEETH / DISC_TEETH) * math.pi * FEED_PD,
    rel_tol=1e-12,
), "paper_drive_geom feed law drifted from the assembly's mounted train"

# Spare T18 removable: the swap chain wheel, stored flat on the base top
# (local z=0 underside at the deck). Rx(-90) maps local +Z to machine +Y,
# so the face thickness extends UP from the deck, not down to it.
# A spare for this subsystem, so it rides here as a flat sibling of
# the mounted knob wheel; placing it loose at the TOP level would clash on leaf
# name with the mounted crank/knob instances nested in this sub.
# Keep the loose T18 on the deck, ahead of the nameplate. At the previous
# Z=-15 storage station, lowering onto the deck intersected the nameplate;
# Z=-75 leaves 5 mm between the T18 tip envelope and the plate's Z=-50 edge.
# X=140 (was 160): the black deck now ends at X=167 (user ruling 2026-10-09),
# and at X=160 the tip envelope (to X=180) straddled its 3.0 step; from 140 it
# spans X 120..160, flat on the deck and west of the rocker-support foot.
SPARE_GEAR_POS = (140.0, BASE_DECK_Y, -75.0)

# --- fasteners ----------------------------------------------------------------
# Platen-clip screws (pd-vn-platen-clip-screw): heads on the clips' flat sheet,
# shanks through #2 clearance holes into #2-56 through receivers in the platen.
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
# upper end.  Thus both spring rails (local +Y) point inward, toward the paper,
# and stop short of it (test_pd_platen_refit holds the gap).
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
    (PLATE_X0 + x, gy + GUIDE_TAP_Y) for gy in GUIDE_Y for x in GUIDE_LOCK_HOLE_X
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
    ("reducer disc", STUD_XY, DISC_SPEC.OUTSIDE_DIA / 2.0, DISC_Z0, DISC_Z0 + DISC_FACE),
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
            seat_geometry.DRIVE_PIN_TIP_Z,
            KNOB_DRIVE_PIN_Z0,
        )
        for xy in KNOB_DRIVE_PIN_XY
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
        PLATE_FRONT_Z - CLIP_THICKNESS - CLIP_SCREW_HEAD_H,
        PLATE_FRONT_Z,
    ),
)

# The guide-lock stations ride the platen: each lock plate bridges the bar
# behind one guide rail (bottom plate up from the lower rail's seat, top plate
# down from the upper rail's top edge), its two screws on the rail's tap row,
# lapping past the rail's outer edge (R9-59): the bottom rail's outer edge is
# its datum B, the top rail's its top face.
LOCK_LIP = (LOCK_HOLE_Y - GUIDE_TAP_Y, LOCK_HOLE_Y - (GUIDE_HEIGHT - GUIDE_TAP_Y))
if any(abs(y - LOCK_HOLE_Y) > 1e-9 for _, y in LOCK_HOLE_XY) or min(LOCK_LIP) < 0.0:
    raise AssertionError("guide-lock screw holes are off the guide rail's tap row")
LOCK_PLATE_Y = (
    (GUIDE_Y[0] - LOCK_LIP[0], GUIDE_Y[0] - LOCK_LIP[0] + LOCK_HEIGHT),
    (
        GUIDE_Y[1] + GUIDE_HEIGHT + LOCK_LIP[1] - LOCK_HEIGHT,
        GUIDE_Y[1] + GUIDE_HEIGHT + LOCK_LIP[1],
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

    # 90280A201 clamps: head seat -> remaining bar -> front clamp -> the open
    # grip gap (the back arc's mating face stops ARC_BACK_GRIP_OFFSET short of
    # the column axis, sh_column_clamp_back_geom) -> tapped back clamp. The
    # receiver is through, so its unused thickness is clearance, never a blind
    # bottom.
    if (
        CLAMP_RECEIVER_SPEC.kind,
        CLAMP_RECEIVER_SPEC.size,
        CLAMP_RECEIVER_SPEC.end,
    ) != ("tapped", "#8-32", "through_all"):
        raise AssertionError("clamp receiver is not a through #8-32 tap")
    clamp_passage = (
        BAR_DEPTH - CLAMP_CBORE_DEPTH + ARC_FRONT_DEPTH + ARC_BACK_GRIP_OFFSET
    )
    clamp_engagement = CLAMP_SCREW_LEN - clamp_passage
    nonnegative("clamp head recess", CLAMP_CBORE_DEPTH - CLAMP_SCREW_HEAD_H)
    nonnegative(
        "clamp head radial clearance", (CLAMP_CBORE_DIA - CLAMP_SCREW_HEAD_DIA) / 2.0
    )
    nonnegative(
        "clamp shank radial clearance", (CLAMP_HOLE_DIA - CLAMP_SCREW_DIA) / 2.0
    )
    valid_engagement("clamp #8-32 engagement", clamp_engagement, CLAMP_SCREW_DIA)
    nonnegative("clamp receiver tip clearance", ARC_BACK_BLOCK_DEPTH - clamp_engagement)
    if abs(CLAMP_CBORE_DEPTH - CLAMP_SCREW_HEAD_H - CLAMP_HEAD_RECESS) > 1e-9:
        raise AssertionError("clamp head is not recessed by CLAMP_HEAD_RECESS")

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
        raise AssertionError("guide head is not recessed by PLATEN_HEAD_RECESS")
    if (
        abs(GUIDE_SCREW_PASSAGE + GUIDE_SCREW_THREAD_ENGAGEMENT - FILLISTER_SHANK_LEN)
        > 1e-9
    ):
        raise AssertionError("guide screw stack does not consume the stock shank")
    valid_engagement(
        "guide #4-40 engagement", GUIDE_SCREW_THREAD_ENGAGEMENT, FILLISTER_SHANK_DIA
    )
    nonnegative("guide screw blind-bottom clearance", GUIDE_SCREW_BOTTOM_CLEARANCE)

    # The low slotted pan-head guide-lock screws (R9-31, R9-48) take the real
    # 1/16-sheet plate and 9.525-mm under-head length; the guide's through tap
    # receives the remaining 7.9375 mm and the tip stops inside the rail.
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

    # Clip heads sit directly on the flat 0.8 brass sheet (no seat boss); the
    # platen and its rear socket bosses are through-tapped for the remaining
    # 5.55 mm of shank, and the tip is flush with the boss.
    if (PLATEN_SOCKET_SPEC.kind, PLATEN_SOCKET_SPEC.size, PLATEN_SOCKET_SPEC.end) != (
        "tapped",
        CLIP_SCREW_THREAD,
        "through_all",
    ):
        raise AssertionError(f"clip receiver is not a through {CLIP_SCREW_THREAD} tap")
    nonnegative(
        "clip shank radial clearance", (CLIP_HOLE_DIA - CLIP_SCREW_SHANK_DIA) / 2.0
    )
    valid_engagement(
        f"clip {CLIP_SCREW_THREAD} engagement",
        PLATEN_SOCKET_ENGAGEMENT,
        CLIP_SCREW_SHANK_DIA,
    )
    clip_tip_clearance = (
        CLIP_THICKNESS + PLATEN_SOCKET_ENGAGEMENT - CLIP_SCREW_SHANK_LEN
    )
    nonnegative("clip screw rear protrusion clearance", clip_tip_clearance)
    if abs(clip_tip_clearance) > 1e-9:
        raise AssertionError("clip screw tip is not flush with the socket boss")

    # The raised heads remain wholly outside the recording-paper side margins
    # (the sheet sits off centre: _recording_geometry.RECORDING_PAPER_LEFT_INSET_MM).
    left_head_extent = PLATEN_SOCKET_XY[0][0] + CLIP_SCREW_HEAD_DIA / 2.0
    right_head_extent = PLATE_WIDTH - PLATEN_SOCKET_XY[2][0] + CLIP_SCREW_HEAD_DIA / 2.0
    nonnegative(
        "left clip head-to-paper clearance",
        RECORDING_GEOMETRY.RECORDING_PAPER_LEFT_INSET_MM - left_head_extent,
    )
    nonnegative(
        "right clip head-to-paper clearance",
        RECORDING_GEOMETRY.RECORDING_PAPER_RIGHT_INSET_MM - right_head_extent,
    )

    # Hanger joints: transgear_hanger_joints owns the stacks; re-prove them
    # against the placed stations.
    spring_room = PIVOT_SCREW_Z0 - PIVOT_SPRING_Z0
    if abs(spring_room - HANGER.SPRING_ROOM_NOMINAL) > 1e-9:
        raise AssertionError(
            f"pivot spring room {spring_room:.4f} is not "
            f"{HANGER.SPRING_ROOM_NOMINAL:.4f}"
        )
    if abs(spring_room - PIVOT_SPRING.MODEL_HEIGHT) > 1e-9:
        raise AssertionError("the MHA-PD-VN-63 spring is not modelled in its room")
    if HANGER.PIVOT_ENGAGEMENT_WORST_D + 1e-9 < HANGER.ENGAGEMENT_TARGET_D:
        raise AssertionError(
            f"pivot screw engagement {HANGER.PIVOT_ENGAGEMENT_WORST_D:.3f} D"
            f" worst is under {HANGER.ENGAGEMENT_TARGET_D} D"
        )
    # The faced tip stands inside the bar's through tap, below the front face
    # the platen slides on, within the fitted recess window.
    pivot_tip_recess = (
        PIVOT_SCREW_Z0 - PIVOT_SCREW.SHOULDER_LEN - PIVOT_SCREW.FITTED_THREAD_LEN
    ) - BAR_FRONT_Z
    if not PIVOT_SCREW.TIP_RECESS[0] <= pivot_tip_recess <= PIVOT_SCREW.TIP_RECESS[1]:
        raise AssertionError(
            f"pivot screw tip recess {pivot_tip_recess:.3f} leaves the fitted window"
        )
    if HANGER.PLATE_SCREW_ENGAGEMENT_WORST_D + 1e-9 < HANGER.ENGAGEMENT_TARGET_D:
        raise AssertionError(
            f"plate-screw engagement {HANGER.PLATE_SCREW_ENGAGEMENT_WORST_D:.3f} D"
            f" worst is under {HANGER.ENGAGEMENT_TARGET_D} D"
        )
    # R9-44; historical filed-tip comparison MHA-DT-32. Bench-fit the matched
    # pair, remove/pre-cut off mechanism before the guide-lock sweep, then
    # refit/reinspect. The model is CUT TO FIT, not an actual receiving record.
    plate_screw_tip = PLATE_SCREW_Z0 - PLATE_SCREW.LENGTH
    if abs(plate_screw_tip - (ARM_Z0 + HANGER.PLATE_SCREW_TIP_INSIDE_NOMINAL)) > 1e-9:
        raise AssertionError(
            "MHA-PD-VN-56's cut tips are not flush with the arm's front face"
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
            "MHA-PD-VN-55 disc-screw tip to the MHA-PD-06 disc rear face: "
            f"{tip_below_rear:.3f} inside, off the cut window"
        )
    valid_engagement(
        "disc #0-80 engagement",
        disc_screw_tip - DISC_Z0,
        DISC_SCREW.SHANK_DIA,
    )

    # Knob stack: the thumbnut on the shaft's front thread, seated on the
    # collar's pilot (R9-70); the cup is pinned, not screwed.
    raw_thumbnut = (
        KNOB_SPEC.TIP_STATION - KNOB_COLLAR_FITTED_LENGTH - COLLAR.PILOT_LENGTH
    )
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
        HOOK.WIDTH, HOOK_SPEC.WIDTH_PLACES, (-HOOK_SPEC.WIDTH_TOL, HOOK_SPEC.WIDTH_TOL),
        unit=HOOK_SPEC.UNIT,
    )
    ear_rear = printed_deviations(
        HOOK.EAR_HEIGHT, HOOK_SPEC.EAR_HEIGHT_PLACES, unit=HOOK_SPEC.UNIT
    )[1]
    arm_forward = max(
        -printed_deviations(HOOK.z_local(z), HOOK_SPEC.ARM_BAND_PLACES, unit=HOOK_SPEC.UNIT)[0]
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
# (drawing-guidelines.md rule 17 (walls and webs)): each section is the envelope its printed bands allow,
# grown toward its neighbours, and each pair must keep LOCK_SWEEP_FLOOR of
# running clearance. The bar's back face is the datum the hanger stands on and
# the platen rides its front face, so the thinnest bar carries the whole lock
# stack rearward toward the hanger, and the deepest rail and thickest sheet
# stand the pan heads further back again. The arm sits on the shortest
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
    GUIDE_DEPTH, GUIDE_DEPTH_PLACES, deviations(GUIDE_DEPTH_BAND), unit=GUIDE_UNIT
)
# The rail's sheet prints its other sizes at the same document places.
_GUIDE_HEIGHT_DEV = printed_deviations(GUIDE_HEIGHT, GUIDE_DEPTH_PLACES, unit=GUIDE_UNIT)
_LOCK_THICK_DEV = (-LOCK_THICK_BAND, LOCK_THICK_BAND)  # the sheet's mill band
_LOCK_HEIGHT_DEV = printed_deviations(LOCK_HEIGHT, LOCK_PRECISION["Height"], unit=LOCK_UNIT)
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
    """Conservatively sweep each guide-lock section and clip-screw boss
    unbounded in x; this is stricter than the separately enforced finite
    engaged-feed domain. Its (y, z) section must clear every fixed part
    behind the bar at every platen position, the plates the bar's back face
    and the bosses its top edge, by LOCK_SWEEP_FLOOR at the printed worst case
    (contract lock sweep; R9-31 fits the low guide-lock screw heads so they
    pass the hanger arm)."""
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
        yc = gy + GUIDE_TAP_Y
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
    # The clip-screw socket bosses ride the platen back too, SOCKET_BOSS_H
    # proud of it, their screw tips flush in them; the thinnest bar carries
    # the back rearward. Each boss takes its printed Ø (on the radius), the
    # root round's foot on the back face beyond it, and its station sideways,
    # and rearward the tallest boss, or the tip left proud of the shortest one
    # by a thin plate.
    boss_r = PLATEN_SOCKET_BOSS_DIA / 2.0 + PLATEN_BOSS_FILLET_R
    boss_dy = printed_deviations(
        PLATEN_SOCKET_BOSS_DIA, PLATEN_PRECISION["Boss2Dia"], unit=PLATEN_UNIT
    )[1] / 2.0 + max(
        abs(deviation)
        for _, y in PLATEN_SOCKET_XY
        for deviation in printed_deviations(y, PLATEN_PRECISION["Socket2Y"], unit=PLATEN_UNIT)
    )
    boss_rear = (
        printed_deviations(PLATEN_BOSS_H, PLATEN_PRECISION["BossH"], unit=PLATEN_UNIT)[1]
        + _PLATEN_THICKNESS_BAND
    )
    bosses = [
        (
            f"clip-screw boss y{y:.1f}",
            _grown(
                (y - boss_r, y + boss_r, BAR_FRONT_Z, BAR_FRONT_Z + PLATEN_BOSS_H),
                boss_dy,
                0.0,
                -_BAR_DEPTH_DEV[0] + boss_rear,
            ),
        )
        for y in sorted({y for _, y in CLIP_SCREW_XY})
    ]
    moving += bosses
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
    # bore is on the screw axis; its largest O.D. stands off that axis by the
    # offset its printed runout to A allows (SPACER.BORE_ECCENTRICITY).
    pivot_tap = BAR.HOLE_POSITION_BAND
    spacer_r = (SPACER.OD + SPACER.OD_BAND) / 2.0 + SPACER.BORE_ECCENTRICITY
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
                    ARM.REDUCER_POSITION_RADIUS + pivot_tap,
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
            if moving_label.startswith("clip-screw boss"):
                minima["clip-screw bosses"] = min(
                    minima.get("clip-screw bosses", math.inf), gap
                )
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
    # The bosses stand inside the bar's depth, so they must pass above its top
    # edge; a top rail printed short drops the hung platen toward it.
    bar = _grown(
        (BAR_TOP_Y - BAR_HEIGHT, BAR_TOP_Y, BAR_FRONT_Z, BAR_BACK_Z),
        -min(_GUIDE_HEIGHT_DEV[0], 0.0),
        0.0,
        0.0,
    )
    boss_bar_gap = min(_section_gap(section, bar) for _, section in bosses)
    if boss_bar_gap < LOCK_SWEEP_FLOOR:
        raise AssertionError(
            "the platen's clip-screw bosses would sweep into the bar"
            f" (worst-case gap {boss_bar_gap:.3f} < {LOCK_SWEEP_FLOOR})"
        )
    minima["clip-screw bosses on the bar"] = boss_bar_gap
    log(
        "guide-lock station sweep clears the hanger at the printed worst case: "
        + ", ".join(f"{label} {gap:.3f}" for label, gap in minima.items())
    )


# The least bar overlap a set lock plate keeps at the printed worst case.
LOCK_RETENTION_FLOOR = 0.5


def _assert_lock_retention() -> None:
    """The bar fills the channel between the rails to BOTTOM_RAIL_CLEARANCE
    and one lock plate size serves both rails (user ruling 2026-10-11), so
    the bottom rail must run clear of the bar's bottom edge and each set
    plate must still overlap the bar, at the printed worst case: the bar at
    its .XXX height band (it hangs the platen by its top edge), the rails at
    their printed height band (their taps locate from the bottom face), the
    plate at its least height, set away from the bar by its whole guide-side
    reach (pd_vn_guide_lock_screw_spec.LOCK_SET_EDGE_REACH, its hole bands
    included). The bottom plates retain the hanging platen; the top plates
    retain it lifted until its bottom rail meets the bar."""
    bar_bottom = BAR_TOP_Y - BAR_HEIGHT
    rail_top = GUIDE_Y[0] + GUIDE_HEIGHT
    clearance_min = (
        bar_bottom - BAR.BAR_HEIGHT_BAND - rail_top - max(_GUIDE_HEIGHT_DEV[1], 0.0)
    )
    if clearance_min < LOCK_SWEEP_FLOOR:
        raise AssertionError(
            f"the platen's bottom rail would rub the support bar's bottom edge"
            f" (worst-case gap {clearance_min:.3f} < {LOCK_SWEEP_FLOOR})"
        )
    lift_max = (
        bar_bottom + BAR.BAR_HEIGHT_BAND - rail_top - min(_GUIDE_HEIGHT_DEV[0], 0.0)
    )
    retreat = LOCK_SET_EDGE_REACH[1] - min(_LOCK_HEIGHT_DEV[0], 0.0)
    overlaps = {
        "bottom plates (hanging)": LOCK_PLATE_Y[0][1]
        - retreat
        - (bar_bottom + BAR.BAR_HEIGHT_BAND),
        "top plates (lifted)": BAR_TOP_Y - LOCK_PLATE_Y[1][0] - retreat - lift_max,
    }
    for label, overlap in overlaps.items():
        if overlap < LOCK_RETENTION_FLOOR:
            raise AssertionError(
                f"the set guide-lock {label} would overlap the support bar only"
                f" {overlap:.3f} at the printed worst case (< {LOCK_RETENTION_FLOOR})"
            )
    log(
        "guide-lock retention at the printed worst case: bottom rail under the bar "
        f"{clearance_min:.3f} (lift {lift_max:.3f}), "
        + ", ".join(f"{label} overlap {gap:.3f}" for label, gap in overlaps.items())
    )


def _assert_rack_mesh() -> RackOperatingDomain:
    """Rack law, closed-form mesh gates, cut ends and the paper sweep."""
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
    z_overlap = min(FEED_Z0, RACK_TEETH_BACK_Z) - max(
        FEED_Z0 - FEED_FACE, RACK_TEETH_FRONT_Z
    )
    if z_overlap < 2.5:
        raise RuntimeError(
            f"feed pinion reaches only {z_overlap:.2f} into the rack band"
        )
    # Closed-form gates at the datum band over every printed corner: contact
    # ratio, backlash, root and tip clearance, the interference point; then
    # the engaged-feed window on the finite rack against the paper sweep.
    import paper_drive_rack_setup as rack_setup

    if abs(RACK_ADDENDUM - FEED.MODULE_MM) > 1e-9:
        raise RuntimeError("the purchased rack must retain its 1/P addendum")
    rack_setup.require_feed_rack_datum_axis_distance(RACK_PITCH_Y - STUD_XY[1])
    mesh = rack_setup.require_feed_rack_mesh()
    domain = rack_setup.feed_rack_operating_domain()
    log(
        f"rack mesh: pitch line y {RACK_PITCH_Y:.2f}, extension {ext:.2f}; "
        f"{mesh.summary}; {domain.operating_window_text}"
    )
    return domain


def _assert_native_rack_operating_pose(
    adapter, domain: RackOperatingDomain, rack: str, running_pin: str,
) -> None:
    """Guard observed native datums with the whole loaded running-axis family.

    The rack's local origin is on its actual -X cut face. The stud is read
    at the feed mid-plane, rather than substituting the sleeve profile axis
    or the nominal FIRST_GAP_X phase. This is native model/accepted-grade
    evidence, not a replacement for the drawn operator's end-limit duty.
    """
    import paper_drive_rack_setup as rack_setup

    rack_left = world_point(adapter, rack, [0.0, 0.0, 0.0])
    rack_x = world_point(adapter, rack, [1.0, 0.0, 0.0])
    if math.dist(
        [rack_x[i] - rack_left[i] for i in range(3)], [1.0, 0.0, 0.0]
    ) > 1e-8:
        raise RuntimeError("rack's physical -X cut-end datum is not along machine +X")
    feed_mid_z = FEED_Z0 - FEED_FACE / 2.0
    axis = world_point(adapter, running_pin, [0.0, 0.0, PIN_Z0 - feed_mid_z])
    pitch_line = world_point(
        adapter, rack,
        [0.0, RACK_BAR_HEIGHT - RACK_ADDENDUM, RACK_BACK_Z - feed_mid_z],
    )
    rack_setup.require_feed_rack_datum_axis_distance(pitch_line[1] - axis[1])
    displacement = PAPER_GEOMETRY.feed_running_axis_x_displacement_band_mm()
    domain.require_machine_travel_mm(
        rack_left_end_x_band_mm=(rack_left[0], rack_left[0]),
        running_axis_x_band_mm=tuple(axis[0] + value for value in displacement),
    )


def _assert_gear_mesh() -> None:
    """Third-gear/disc mesh: same DP, the disc's centre distance, phased
    tooth-on-gap."""
    if (
        THIRD_DP != DISC_DP
        or KNOB_SPEC.PRESSURE_ANGLE_DEG != DISC_SPEC.PRESSURE_ANGLE_DEG
    ):
        raise RuntimeError("the reducer pinion and disc do not share pitch and PA")
    import paper_drive_mesh_check as mesh_check

    centre_distance = DISC_SPEC.CENTRE_DISTANCE
    c2c_nominal = DISC_SPEC.STANDARD_CENTRE_DISTANCE
    ext = centre_distance - c2c_nominal
    # CR at the minimum tips, positive backlash at the tight runout extreme,
    # AGMA root clearance and the interference points, at both ends of the
    # set band (the nominal end is the model's centre).
    reducer, reducer_top = (check.require() for check in mesh_check.reducer_band_meshes())
    if DISC_SPEC.CENTRE_DISTANCE_WINDOW[0] != centre_distance:
        raise RuntimeError("the model's reducer centre is not the set band's nominal end")
    # The disc's teeth repeat every 360/DISC_TEETH deg, so a tooth must point
    # along the S -> K line at the mesh angle for the knob pinion's phased gap.
    disc_gamma = 360.0 / DISC_TEETH
    if abs(math.remainder(MESH_ANGLE_DEG, disc_gamma)) > 1e-9:
        raise RuntimeError(
            f"mesh angle {MESH_ANGLE_DEG} is not a multiple of the disc pitch"
            f" {disc_gamma}"
        )
    gap_az = THIRD_PHASE_DEG + KNOB_SPEC.GAP_AZIMUTH_DEG - _MESH_AZ
    if abs(math.remainder(gap_az, THIRD_GAMMA)) > 1e-9:
        raise RuntimeError(f"the knob {THIRD_TEETH}T's phased gap does not face the disc")
    # Shifted full-depth pinion relief is below the base circle. Check both
    # true root arcs; the spec also rejects contact beyond a base circle.
    tip_reach = centre_distance - DISC_SPEC.OUTSIDE_DIA / 2.0
    root_margin = tip_reach - KNOB_SPEC.ROOT_DIA / 2.0
    reciprocal_margin = (
        centre_distance - KNOB_SPEC.OUTSIDE_DIA / 2.0 - DISC_SPEC.ROOT_DIA / 2.0
    )
    if min(root_margin, reciprocal_margin) <= 0.05:
        raise RuntimeError("the shifted reducer tips reach a mating root floor")
    z_overlap = min(KNOB_SHAFT_Z0 + THIRD_FACE, DISC_Z0 + DISC_FACE) - max(
        KNOB_SHAFT_Z0, DISC_Z0
    )
    if z_overlap < 2.5:
        raise RuntimeError(f"third gear/disc z overlap {z_overlap:.2f} < 2.5")
    log(
        f"gear mesh {THIRD_TEETH}:{DISC_TEETH} {DISC_DP:g}DP PA{DISC_SPEC.PRESSURE_ANGLE_DEG:g}:"
        f" c2c {centre_distance} (ext {ext:.3f}); {reducer.summary}; {reducer_top.summary};"
        f" {THIRD_TEETH}T phased {THIRD_PHASE_DEG:+.1f} deg,"
        f" tip/floor margin {min(root_margin, reciprocal_margin):.3f}"
    )


def _assert_knob_shaft_clearance() -> None:
    """The knob cluster must ride the disc's exact centre distance with its
    air gaps and floats."""
    # R9-68: the collar's rearmost stop is the knob pinion's front face F; with
    # the cluster and disc forward the disc's front face stands m_fwd behind
    # it.  Its air is the collar stack's (pd_cluster_air, #2038), at its
    # governing method, from the model's m_fwd: the model's disc sits the
    # nominal end float rearward of it.
    collar_disc_air_min = CLUSTER_AIR.COLLAR_AIR_MIN
    model_m_fwd = DISC_Z0 - CLUSTER.END_FLOAT_NOMINAL - KNOB_SHAFT_Z0
    air = float(CLUSTER_AIRS["collar_air"]) + model_m_fwd - CLUSTER.M_FWD_NOMINAL
    if air < collar_disc_air_min - 1e-9:
        raise AssertionError(
            f"knob drive collar to disc air {air:.3f} < {collar_disc_air_min}"
            " with the cluster forward -- the collar must stand clear of the disc"
        )
    if abs(model_m_fwd - CLUSTER.M_FWD_NOMINAL) > 1e-9:
        raise AssertionError(
            f"the model's m_fwd {model_m_fwd:.4f} is not the collar stack's "
            f"{CLUSTER.M_FWD_NOMINAL:.4f}"
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
    # The mounted knob wheel shares the disc hub's z band: radial gap to the hub.
    knob_wheel_hub_gap = reach - (
        REMOVABLE_TIP_R[REMOVABLE.KNOB_CONFIG] + DISC_HUB.HUB_DIA / 2.0
    )
    if knob_wheel_hub_gap < 0.5:
        raise RuntimeError(
            f"mounted knob {REMOVABLE.KNOB_CONFIG} to disc-hub gap"
            f" {knob_wheel_hub_gap:.2f} < 0.5"
        )
    # The MHA-PD-25 front bushing at its largest Ø against the knob stack's
    # largest neighbours, whatever their z: the knob wheel's tips, thumbnut and
    # the drive collar.
    bushing_r = (
        FRONT_BUSHING.OD + printed_band_mm(FRONT_BUSHING.OD_PLACES, unit=FRONT_BUSHING.UNIT)
    ) / 2.0
    bushing_air = (
        reach
        - bushing_r
        - max(
            REMOVABLE_TIP_R[REMOVABLE.KNOB_CONFIG],
            max(THUMBNUT_HEAD_DIA, THUMBNUT_FLANGE_DIA) / 2.0,
            KNOB_COLLAR_R_WORST,
        )
    )
    if bushing_air < 1.0:
        raise RuntimeError(f"front bushing to knob stack air {bushing_air:.2f} < 1.0")
    # The knob wheel overlaps the disc rim in XY -- they must stay z-separated.
    z_gap = DISC_Z0 - seat_geometry.SEAT_FACE_Z  # 6.9
    if z_gap < 2.0:
        raise RuntimeError(f"knob wheel/disc z gap {z_gap:.2f} < 2.0")
    # End float: the knob cup's front face behind the arm plate's boss.
    end_float = KNOB_CUP_Z0 - (PLATE_Z0 + ARM_PLATE.BOSS_FACE_Z)
    if abs(end_float - KNOB_SPEC.END_FLOAT) > 1e-9:
        raise RuntimeError(
            f"knob end float {end_float:.4f} is not {KNOB_SPEC.END_FLOAT}"
        )
    # Sleeve float: the ring's rear face in front of the front bushing (the
    # disc's end float less the hub's recess).
    cluster_float = (FRONT_BUSHING_Z0 - FRONT_BUSHING.LENGTH) - CLUSTER.RING_REAR_Z
    if abs(cluster_float - CLUSTER.SLEEVE_FLOAT_MODEL) > 1e-9:
        raise RuntimeError(
            f"sleeve float {cluster_float:.4f} is not {CLUSTER.SLEEVE_FLOAT_MODEL}"
        )
    log(
        f"knob shaft at ({KNOB_SHAFT_XY[0]:.3f}, {KNOB_SHAFT_XY[1]:.3f}); plate"
        f" hub {RACK_TIP_Y - hub_top:.2f} under the rack crests; gaps:"
        f" knob wheel/hub {knob_wheel_hub_gap:.1f},"
        f" front bushing/knob stack {bushing_air:.1f},"
        f" knob wheel/disc z {z_gap:.1f}, collar/disc air"
        f" {air:.3f} ({CLUSTER_AIRS['method']}); floats: knob {end_float:.2f},"
        f" cluster {cluster_float:.2f}"
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
    from paper_drive_chain_fit import source_nominal_chain_centres_mm
    _knob, crank = source_nominal_chain_centres_mm()
    if CHAIN_CRANK_CENTRE != (-crank[0], crank[1]):
        raise RuntimeError(
            f"_chain CRANK_CENTRE {CHAIN_CRANK_CENTRE} != canonical crank axis "
            f"at wheel Z {CHAIN_MID_Z}: {crank}"
        )
    if (KNOB_TIP_R, CRANK_TIP_R) != (
        REMOVABLE_TIP_R[REMOVABLE.KNOB_CONFIG],
        REMOVABLE_TIP_R[REMOVABLE.CRANK_CONFIG],
    ):
        raise RuntimeError("_chain mounted tip radii diverged from REMOVABLE_TIP_R")
    if LINK_COUNT != REMOVABLE.CHAIN_LINK_COUNT:
        raise RuntimeError("native chain visual diverged from the selected physical count")
    log(
        f"roller chain VISUAL guide: loop {CENTRELINE_LEN:.2f}, {LINK_COUNT} links at"
        f" {LINK_PITCH:.4f}, pitch-circle guide ({KNOB_PITCH_R}/{CRANK_PITCH_R}),"
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
    """Inherited VISUAL guide air (R9-30), not a discrete seating certificate.

    Preserve the chain-plane obstacle gate and purchased envelope; exact-pitch
    physical closure is checked separately by paper_drive_chain_fit.
    """
    z_front = CHAIN_FRONT_Z_WORST
    z_back = seat_geometry.SEAT_FACE_Z + CHAIN_REACH_REAR_WORST
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
        f"native chain VISUAL slack guide ({LINK_COUNT} links) clears chain-plane parts: "
        + ", ".join(report)
    )


CHAIN_LINK_STEM = "sh-vn-chain-link"
CONNECTING_LINK_STEM = "pd-vn-chain-connecting-link"
CHAIN_COMPONENT_REFERENCES = {
    f"@{configuration}:{ordinal}": (CHAIN_LINK_STEM, configuration)
    for configuration, count in (
        (INNER_LINK_CONFIGURATION, LINK_COUNT // 2),
        (OUTER_LINK_CONFIGURATION, LINK_COUNT // 2 - 1),
    )
    for ordinal in range(1, count + 1)
}


def _chain_station_point(station: int) -> tuple[float, float, float]:
    x, y, _ = loop_point_tangent(
        station * LINK_PITCH,
        dx=CHAIN_KNOB_CENTRE[0],
        dy=CHAIN_KNOB_CENTRE[1],
        mirror_x=True,
    )
    return x, y, CHAIN_MID_Z


def _chain_station_components(model) -> dict[int, object]:
    """Associate native members with unique loop stations, never Name2 indices.

    A station is the link's pin-0 position on the inherited visual guide.
    The nearest station must be less than half a pitch away, all stations must
    occur once, and the native member and plate plane must match that station.
    This is an occurrence-identity check, not a discrete-chain fit certificate.
    """
    assembly = _early_bound(model, "IAssemblyDoc")
    points = tuple(_chain_station_point(station) for station in range(LINK_COUNT))
    stations = {}
    for raw in tuple(assembly.GetComponents(True) or ()):
        component = _early_bound(raw, "IComponent2")
        stem, configuration = component_identity(component)
        if stem not in (CHAIN_LINK_STEM, CONNECTING_LINK_STEM):
            continue
        transform = tuple(float(value) for value in component.Transform2.ArrayData)
        origin = tuple(value * 1000.0 for value in transform[9:12])
        distances = tuple(math.dist(origin, point) for point in points)
        station = min(range(LINK_COUNT), key=distances.__getitem__)
        if distances[station] >= LINK_PITCH / 2.0:
            raise RuntimeError(f"{component.Name2}: no unambiguous chain loop station")
        if abs(origin[2] - CHAIN_MID_Z) > 0.5 or abs(transform[8] - 1.0) > 1e-6:
            raise RuntimeError(f"{component.Name2}: chain member leaves its native plate plane")
        expected = (
            (CONNECTING_LINK_STEM, "Default")
            if station == LINK_COUNT - 1
            else (
                CHAIN_LINK_STEM,
                INNER_LINK_CONFIGURATION if station % 2 == 0 else OUTER_LINK_CONFIGURATION,
            )
        )
        if (stem, configuration) != expected:
            raise RuntimeError(
                f"chain station {station}: {(stem, configuration)!r} != {expected!r}"
            )
        if station in stations:
            raise RuntimeError(f"duplicate chain loop station {station}")
        stations[station] = component
    if set(stations) != set(range(LINK_COUNT)):
        raise RuntimeError(
            f"chain loop stations missing: {sorted(set(range(LINK_COUNT)) - stations.keys())!r}"
        )
    return stations


def _chain_reference_names(model) -> dict[str, str]:
    """Read every saved semantic role and prove its native loop association."""
    stations = _chain_station_components(model)
    names = component_reference_names(model, CHAIN_COMPONENT_REFERENCES)
    for station, component in stations.items():
        if station == LINK_COUNT - 1:
            continue
        role = INNER_LINK_CONFIGURATION if station % 2 == 0 else OUTER_LINK_CONFIGURATION
        selector = f"@{role}:{station // 2 + 1}"
        if names[selector] != str(component.Name2):
            raise RuntimeError(f"chain reference {selector} does not identify loop station {station}")
    return names


def _assign_chain_references(adapter) -> dict[str, str]:
    """Assign pattern references and preserve placed pose witnesses across rebuild."""
    model = adapter.currentModel
    stations = _chain_station_components(model)
    before = {station: str(component.Name2) for station, component in stations.items()}
    for station, component in stations.items():
        if station != LINK_COUNT - 1:
            role = INNER_LINK_CONFIGURATION if station % 2 == 0 else OUTER_LINK_CONFIGURATION
            set_component_reference(
                adapter,
                str(component.Name2),
                f"{role}:{station // 2 + 1}",
                rebuild=False,
            )
    if not bool(model.ForceRebuild3(False)):
        raise RuntimeError("chain component reference rebuild failed")
    names = _chain_reference_names(model)
    after = {
        station: str(component.Name2)
        for station, component in _chain_station_components(model).items()
    }
    # The connector has no shared Role:N; the validated station census still
    # carries its placement witness through the same native address change.
    for station in sorted(before):
        _rebuilt_component_name(before[station], after[station])
    return names


async def _place_chain_seed(
    adapter, part: str, station: int, *, configuration: str
) -> str:
    """Seat ONE chain link at path ``station``, oriented along the forward CHORD
    (pin0->pin1) so both pin axes sit ~on the loop: the two pattern seeds, and
    the two closing links the connected-linkage chain pattern does not fill.
    ``_chain`` holds the loop in the PRE-MIRROR frame (anchor
    ``CHAIN_KNOB_CENTRE`` at machine +X), so
    ``mirror_x=True`` reflects each point to the machine (-X) chain plane -- the
    exact machine pose place_component now inserts directly (no mirror layer). The
    achiral link's local-z symmetry keeps that a pure-Z rotation, so the plates
    stay flat in the chain plane. Returns the instance name."""
    if part == CHAIN_LINK_STEM and configuration not in (
        INNER_LINK_CONFIGURATION, OUTER_LINK_CONFIGURATION
    ):
        raise ValueError(f"shared chain insertion requires a named member, not {configuration!r}")
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
        configuration=configuration,
        component_reference=(
            f"{configuration}:{station // 2 + 1}" if part == CHAIN_LINK_STEM else ""
        ),
        ground=True,
        label=f"{part} seed @ station {station}",
    )


async def _author_knob_setting_reference(adapter) -> None:
    """K's DRO setting from the arm's pin bore S as model dimensions (MHA-PD-00 VIEW K):
    one construction chain on the Front plane (sketch x, y = machine x, y),
    P to S on the arm's axis, S to Q along it toward P, Q to K across it,
    and S to the nominal centre N on the S-K line
    (pd_paper_drive_knob_setting_spec). Dimensioned from globals: S to N
    toleranced with the set band, the two DRO coordinates shown as
    reference values with their one-line names; marked for the drawing and
    blanked; no solid or pose changes."""
    spec = KNOB_SETTING
    for name, value in (
        ("KnobSetAlong", spec.K_FROM_S_ALONG_MM),
        ("KnobSetAcross", spec.K_FROM_S_ACROSS_MM),
        ("KnobSetCentre", DISC_SPEC.CENTRE_DISTANCE),
    ):
        await set_global(adapter, name, f"{value}mm")
    points = (spec.P_XY, spec.S_XY, spec.Q_XY, spec.K_XY)
    dims = SketchDims()
    check("create knob setting sketch", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    legs = [
        check(f"knob setting leg {index}", await adapter.add_line(*p0, *p1))
        for index, (p0, p1) in enumerate(zip(points, points[1:]))
    ]
    line = check("knob setting S-K line", await adapter.add_line(*spec.S_XY, *spec.K_XY))
    nominal = check("knob setting S-N", await adapter.add_line(*spec.S_XY, *spec.N_XY))
    set_sketch_direct_db(adapter, False)
    for index, leg in enumerate((*legs, line, nominal)):
        segment = _early_bound(adapter._sketch_entities[leg], "ISketchSegment")
        segment.ConstructionGeometry = True
        if not bool(segment.ConstructionGeometry):
            raise RuntimeError(f"knob setting leg {index} is not construction")
    for index, (leg, after) in enumerate(zip(legs, legs[1:])):
        check(
            f"knob setting legs {index} and {index + 1} chained",
            await adapter.add_sketch_constraint(
                f"{leg}.end", f"{after}.start", "coincident"
            ),
        )
    check(
        "knob setting: along the arm's axis",
        await adapter.add_sketch_constraint(legs[1], legs[0], "collinear"),
    )
    check(
        "knob setting: across the arm",
        await adapter.add_sketch_constraint(legs[2], legs[1], "perpendicular"),
    )
    # S-K joins the chain's ends; N stands on it, CENTRE_DISTANCE from S.
    for first, second, what in (
        (f"{line}.start", f"{legs[1]}.start", "S-K line from S"),
        (f"{line}.end", f"{legs[2]}.end", "S-K line to K"),
        (f"{nominal}.start", f"{legs[1]}.start", "S-N from S"),
    ):
        check(
            f"knob setting: {what}",
            await adapter.add_sketch_constraint(first, second, "coincident"),
        )
    check(
        "knob setting: N on the S-K line",
        await adapter.add_sketch_constraint(nominal, line, "collinear"),
    )
    # P and S from the origin: S lies on machine x = 0, one dimension.
    await anchor_point_to_origin(adapter, f"{legs[0]}.start", *spec.P_XY, "arm pivot P")
    dims.record("KnobSetPivotX")
    dims.record("KnobSetPivotY")
    await anchor_point_to_origin(adapter, f"{legs[1]}.start", *spec.S_XY, "pin S")
    if abs(spec.S_XY[0]) > 1e-9:
        dims.record("KnobSetPinX")
    dims.record("KnobSetPinY")
    await dimension_between(
        adapter, f"{legs[1]}.start", f"{legs[1]}.end", "distance",
        spec.K_FROM_S_ALONG_MM, spec.ALONG_DIMENSION,
    )
    dims.record(spec.ALONG_DIMENSION, '"KnobSetAlong"')
    await dimension_between(
        adapter, f"{legs[2]}.start", f"{legs[2]}.end", "distance",
        spec.K_FROM_S_ACROSS_MM, spec.ACROSS_DIMENSION,
    )
    dims.record(spec.ACROSS_DIMENSION, '"KnobSetAcross"')
    await dimension_between(
        adapter, f"{nominal}.start", f"{nominal}.end", "distance",
        DISC_SPEC.CENTRE_DISTANCE, spec.CENTRE_DIMENSION,
    )
    dims.record(spec.CENTRE_DIMENSION, '"KnobSetCentre"')
    await ensure_fully_defined(adapter, "knob setting")
    check("exit knob setting sketch", await adapter.exit_sketch())
    name_last_feature(adapter, spec.FEATURE)
    for name, expression in dims.apply(adapter, spec.FEATURE):
        await drive_dimension(adapter, name, expression)
    # The set band itself, +x/-0, on S to N: an assembly setting is an
    # associative model dimension, never a note (#1388).
    set_dimension_bilateral_tolerance(
        adapter, spec.FEATURE, spec.CENTRE_DIMENSION, *KNOB_SETTING.CENTRE_TOLERANCE_MM,
        places=spec.PLACES,
    )
    for name in sorted(spec.REFERENCE_DIMENSIONS):
        # A reference value through the native prefix/suffix channel (the
        # set band governs K, not the title block's .XXX row).
        display, dimension = _named_dimension(adapter, spec.FEATURE, name)
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        tolerance.Type = 0  # swTolNONE
        display.ShowParenthesis = False
        display.SetText(1, "(")  # swDimensionTextPrefix
        display.SetText(2, ")")  # swDimensionTextSuffix
        if (
            int(tolerance.Type) != 0
            or bool(display.ShowParenthesis)
            or str(display.GetText(1) or "") != "("
            or str(display.GetText(2) or "") != ")"
        ):
            raise RuntimeError(f"{name}@{spec.FEATURE}: reference form did not persist")
    apply_drawing_precision(adapter, spec.DRAWING_PRECISION)
    for name, (part, text) in spec.SETTING_CALLOUTS.items():
        display, _dimension = _named_dimension(adapter, spec.FEATURE, name)
        display.SetText(part, text)
        actual = str(display.GetText(part) or "").replace("\r\n", "\n")
        if actual != text:
            raise RuntimeError(
                f"{name}@{spec.FEATURE}: native setting callout reads {actual!r}, "
                f"not {text!r}"
            )
    mark_dimensions_for_drawing(
        adapter, spec.FEATURE, spec.DRAWING_DIMENSIONS[spec.FEATURE]
    )
    blank_sketch(adapter, spec.FEATURE)
    feature = _early_bound(
        _early_bound(adapter.currentModel, "IAssemblyDoc").FeatureByName(spec.FEATURE),
        "IFeature",
    )
    if int(feature.Visible) != 1:  # swVisibilityStateHide
        raise RuntimeError(f"{spec.FEATURE} still visible after BlankSketch")


async def _insert_roller_chain(adapter) -> None:
    """The drive chain: a native CHAIN COMPONENT PATTERN (connected linkage) of
    alternating inner/outer links along the _chain.py loop, closed by the
    purchased chain's connecting link.

    Ch. 23: the chain rides the two selected mounted removables' teeth (knob and
    crank shafts). The loop centreline is authored as a single CLOSED SPLINE
    (one sketch segment) on an offset plane at the chain plane (z = CHAIN_MID_Z);
    two seed links (chain-inner-link @ station 0, chain-outer-link @ station 1)
    are placed tangent; SolidWorks' native ``FeatureChainPattern`` (connected
    linkage, via ``adapter.pattern_components_chain``) fills all but the last
    two stations with the alternating INNER (plates + bushings) / OUTER (plates
    + pins) links. Each link's two pin axes (Axis1/Axis2) are the group's
    path-links, so the pattern keeps every plate flat in the chain plane and
    tangent to the loop.

    The bought chain is cut with an inner link at each end and closed by one
    connecting link (MHA-PD-VN-66), so the loop holds one outer link fewer than
    inner links. The pattern takes one count per inner/outer PAIR and cannot
    skip an instance, so it stops one pair short; the cut chain's last inner
    link and the connecting link are seated at the two closing stations, the
    same way as the seeds. The connecting link's forward pin is the seed's
    pin 0 on the T24, so it meshes there like the outer link it replaces; the
    gate bounds that one pair in _interference_contracts.

    The path MUST be one connected segment: SolidWorks never treats the 3-arc +
    taut-line contour as connected (the segments share coordinates but carry no
    coincidence relations, so MakeSketchChain forms 0 paths), hence the spline
    through dense loop samples. The dedicated ``FeatureChainPattern`` one-call API
    is used because the documented CreateDefinition/CreateFeature route returns
    null under pywin32 late binding. See memory/chain-pattern-not-createable-
    late-bound.md.

    Visual gates: exactly the selected LINK_COUNT instances, on the chain
    plane, with pin0 on the inherited continuous guide. These observations
    are not discrete-pitch closure or seating acceptance; the independent
    paper_drive_chain_fit math checks the purchased chain.
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
    inner = await _place_chain_seed(
        adapter, CHAIN_LINK_STEM, 0, configuration=INNER_LINK_CONFIGURATION
    )
    outer = await _place_chain_seed(
        adapter, CHAIN_LINK_STEM, 1, configuration=OUTER_LINK_CONFIGURATION
    )

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
                # Preserve the inherited visual's explicit per-group count.
                # Fill-path reserves a seam; count/on-path are visual checks,
                # not a physical standard-pitch seating certificate. One pair
                # short: the closing inner link and connecting link follow.
                pitch_method="connected_linkage",
                fill_path=False,
                count=LINK_COUNT // 2 - 1,
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

    # The cut chain's closing inner link and the connecting link that joins
    # it to the seed inner link, its forward pin on the T24 at pin 0.
    await _place_chain_seed(
        adapter, CHAIN_LINK_STEM, LINK_COUNT - 2, configuration=INNER_LINK_CONFIGURATION
    )
    await _place_chain_seed(
        adapter, CONNECTING_LINK_STEM, LINK_COUNT - 1, configuration="Default"
    )

    # Hide the path spline: it is construction scaffolding for the pattern, not a
    # rendered feature.
    check("blank chain path sketch", await adapter.blank_sketch("chain-path"))
    blank_reference_geometry(adapter, ((plane_name, "PLANE"),))

    # Pattern copies may inherit a seed's ComponentReference. Assign all
    # role-local ordinals from validated loop poses after the final copy exists.
    _assign_chain_references(adapter)
    links = [str(component.Name2) for component in _chain_station_components(adapter.currentModel).values()]
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


def _assert_knob_collar_capture(adapter, collar: str, shaft: str) -> None:
    """Observe native fitted metal on F and D-clock; lock mates cannot stand in."""
    from _gtol_planar import PlanarFace
    from _gtol_face_resolve import resolve_faces

    assembly = _early_bound(adapter.currentModel, "IAssemblyDoc")
    parts = {}
    for label, name in (("collar", collar), ("shaft", shaft)):
        component = assembly.GetComponentByName(name)
        if component is None:
            raise RuntimeError(f"knob {label}: native component is missing")
        component = _early_bound(component, "IComponent2")
        model = component.GetModelDoc2()
        if model is None:
            raise RuntimeError(f"knob {label}: native part is not resolved")
        parts[label] = _early_bound(model, "IModelDoc2")
    dimension = parts["collar"].Parameter("CollarLength@BodyProfile")
    if dimension is None:
        raise RuntimeError("knob collar: fitted native body dimension is missing")
    dimension = _early_bound(dimension, "IDimension")
    length = float(dimension.SystemValue) * 1000.0
    if not COLLAR.LENGTH_FITTED_MIN <= length <= COLLAR.LENGTH_FITTED_MAX:
        raise RuntimeError(f"knob collar: native fitted length {length} is outside source")
    if abs(length - COLLAR.LENGTH) > 1e-6:
        raise RuntimeError("knob collar: native body differs from this fitted source version")
    resolve_faces(parts["collar"], {
        "actual collar rear": PlanarFace((0.0, 0.0, 1.0), length, tolerance_mm=1e-5),
        "actual internal D-flat": PlanarFace((0.0, 1.0, 0.0), -COLLAR.FLAT_TO_AXIS, tolerance_mm=1e-5),
    })
    resolve_faces(parts["shaft"], {
        "actual gear front F": PlanarFace((0.0, 0.0, -1.0), 0.0, tolerance_mm=1e-5),
        "actual shaft D-flat": PlanarFace((0.0, -1.0, 0.0), KNOB_SPEC.CORE_FLAT_FROM_AXIS, tolerance_mm=1e-5),
    })
    rear = world_point(adapter, collar, [0.0, 0.0, length])
    front = world_point(adapter, shaft, [0.0, 0.0, 0.0])
    # F stands KNOB_COLLAR_REAR_GAP behind the nominal collar's rear (+Z), on axis.
    if math.dist((rear[0], rear[1], rear[2] + KNOB_COLLAR_REAR_GAP), front) > 1e-5:
        raise RuntimeError(
            f"gear F is not {KNOB_COLLAR_REAR_GAP:.4f} behind the collar rear: {rear=}, {front=}"
        )
    collar_o = world_point(adapter, collar, [0.0, 0.0, 0.0])
    collar_flat = world_point(adapter, collar, [0.0, -1.0, 0.0])
    shaft_flat = world_point(adapter, shaft, [0.0, -1.0, 0.0])
    if math.dist(
        tuple(collar_flat[i] - collar_o[i] for i in range(3)),
        tuple(shaft_flat[i] - front[i] for i in range(3)),
    ) > 1e-8:
        raise RuntimeError("knob collar native D-flat is not clocked to the shaft")


def _assert_arm_plate_registered(adapter, arm: str, plate: str) -> None:
    """Read real seat planes/cylinder axes, then compare BOTH world sockets.

    Nominal points transformed through a component are not metal readback.
    The canonical face reader supplies actual surface parameters; these
    post-build numerical bounds are not manufacturing acceptance grades.
    """
    from _gtol_cylinder import CylinderFace
    from _gtol_planar import PlanarFace
    from _gtol_face_read import face_geometry
    from _gtol_face_resolve import resolve_faces

    assembly = _early_bound(adapter.currentModel, "IAssemblyDoc")
    actual_centres = {}
    actual_directions = {}
    for name, geometry, seat, socket_z, seat_z in (
        (arm, ARM, PlanarFace((0.0, 0.0, 1.0), ARM.THICKNESS),
         ARM.THICKNESS / 2.0, ARM.THICKNESS),
        (plate, ARM_PLATE, PlanarFace((0.0, 0.0, -1.0), 0.0),
         ARM_PLATE.THICKNESS_OVER_ARM / 2.0, 0.0),
    ):
        component = assembly.GetComponentByName(name)
        if component is None:
            raise RuntimeError(f"registered arm/plate native component missing: {name}")
        component = _early_bound(component, "IComponent2")
        model = component.GetModelDoc2()
        if model is None:
            raise RuntimeError(f"registered arm/plate native part unresolved: {name}")
        resolved = resolve_faces(_early_bound(model, "IModelDoc2"), {
            "actual mounting seat": seat,
            **{
                f"actual locator {index} socket": CylinderFace(
                    geometry.LOCATOR_HOLE_DIA_MM, contains_x_mm=x, contains_y_mm=y,
                    contains_z_mm=socket_z,
                ) for index, (x, y) in enumerate(geometry.LOCATOR_SITES_MM, 1)
            },
        })
        seat_geometry = face_geometry(resolved["actual mounting seat"])
        if seat_geometry is None:
            raise RuntimeError(f"{name}: actual mounting plane has no surface")
        plane = tuple(float(value) for value in seat_geometry.parameters)
        if (len(plane) != 6 or not all(map(math.isfinite, plane))
                or math.hypot(*plane[:2]) > 1e-9 or abs(abs(plane[2]) - 1.0) > 1e-9):
            raise RuntimeError(f"{name}: native mounting plane is not the authored local Z plane")
        centres, directions = [], []
        for index, (x, y) in enumerate(geometry.LOCATOR_SITES_MM, 1):
            socket = face_geometry(resolved[f"actual locator {index} socket"])
            if socket is None:
                raise RuntimeError(f"{name}: actual locating bore {index} has no surface")
            parameters = tuple(float(value) for value in socket.parameters)
            if (len(parameters) != 7 or not all(map(math.isfinite, parameters))
                    or math.hypot(*parameters[3:5]) > 1e-9
                    or abs(abs(parameters[5]) - 1.0) > 1e-9
                    or abs(2000.0 * parameters[6] - geometry.LOCATOR_HOLE_DIA_MM) > 1e-5):
                raise RuntimeError(f"{name}: actual locating bore {index} axis/radius differs from its source")
            denominator = sum(plane[axis] * parameters[axis + 3] for axis in range(3))
            along = sum(plane[axis] * (plane[axis + 3] - parameters[axis])
                        for axis in range(3)) / denominator
            point = tuple(1000.0 * (parameters[axis] + along * parameters[axis + 3])
                          for axis in range(3))
            if math.dist(point, (x, y, seat_z)) > 1e-5:
                raise RuntimeError(f"{name}: actual locating bore {index} seat intersection is off source")
            centre = world_point(adapter, name, point)
            axis_point = world_point(
                adapter, name, [point[axis] + parameters[axis + 3] for axis in range(3)],
            )
            direction = tuple(axis_point[axis] - centre[axis] for axis in range(3))
            centres.append(centre)
            directions.append(direction)
        actual_centres[name], actual_directions[name] = centres, directions
    for arm_point, plate_point, arm_axis, plate_axis in zip(
        actual_centres[arm], actual_centres[plate],
        actual_directions[arm], actual_directions[plate], strict=True,
    ):
        if math.dist(arm_point, plate_point) > 1e-5:
            raise RuntimeError("actual paired locating cylinder centres/seat do not agree")
        if abs(abs(sum(a * b for a, b in zip(arm_axis, plate_axis, strict=True))) - 1.0) > 1e-8:
            raise RuntimeError("actual paired locating cylinder axes are not parallel")


async def build(adapter) -> dict[str, str]:
    # Flip seeds + free-DOF contract: cad/config/assemblies/<ASM_NAME>.yaml.
    activate_assembly_contract(ASM_NAME)
    _assert_fastener_stacks()
    _assert_lock_station_sweep()
    _assert_lock_retention()
    rack_operating_domain = _assert_rack_mesh()
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
                [sx * COLUMN_X, CLAMP_Y, COLUMN_Z],
                [0.0, 90.0, 0.0],
                ROT_Y_POS90,
                label=f"{arc} (x{sx * COLUMN_X:+.0f})",
            )
    # Two exact-pose clamp-screw seeds at the east column plus one native
    # multi-seed pattern across the frame. Each rigid seed uses one lock mate.
    clamp_x = sorted(CLAMP_HOLE_X)
    clamp_seeds: list[str] = []
    for index, x in enumerate(clamp_x[:2]):
        target = [x, CLAMP_Y, BAR_FRONT_Z + CLAMP_CBORE_DEPTH]
        seed = await place_component(
            adapter,
            "sh-vn-clamp-screw",
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
    clamp_targets = [[x, CLAMP_Y, BAR_FRONT_Z + CLAMP_CBORE_DEPTH] for x in clamp_x[2:]]
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
    # Lock plates on the guide backs, bridging BEHIND the bar (clear of its
    # back face) and lapping LOCK_LIP past each rail's outer edge: top-rail
    # locks hang DOWN over the bar (Rz180), bottom-rail locks bridge UP across
    # the running clearance onto the bar (identity; _assert_lock_retention).
    for x_c in LOCK_STATION_X:
        # Machine: the station is measured from the platen's +X edge (the mirror
        # of the pre-mirror left-edge station PLATE_X0 + x_c). The plate's hole
        # pattern, not the plate (its right end overhangs 0.5 more), centres on
        # the station, over the guide's tap pair.
        station = PLATE_X0 + PLATE_WIDTH - x_c
        top = await place_component(
            adapter,
            "pd-guide-lock",
            [station + LOCK_HOLE_PATTERN_X, LOCK_PLATE_Y[1][1], LOCK_Z0],
            [0.0, 0.0, 180.0],
            rot_z_rows(180.0),
            ground=False,
            label=f"guide-lock (top x{x_c:.0f})",
        )
        await _lock_to_platen(top, f"guide-lock top x{x_c:.0f}")
        bot = await place_component(
            adapter,
            "pd-guide-lock",
            [station - LOCK_HOLE_PATTERN_X, LOCK_PLATE_Y[0][0], LOCK_Z0],
            [0.0, 0.0, 0.0],
            IDENTITY,
            ground=False,
            label=f"guide-lock (bottom x{x_c:.0f})",
        )
        await _lock_to_platen(bot, f"guide-lock bottom x{x_c:.0f}")
    # Paper holders: mirrored one-piece brass sheets hugging the platen edges.
    # Opposite Z rotations keep each flat screw rail on its screw sockets while
    # both adjacent spring rails point inward, short of the recording paper.
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
    paper_left_margin = RECORDING_GEOMETRY.RECORDING_PAPER_LEFT_INSET_MM
    paper_top_margin = (
        3.0  # ch30-p002: the sheet's top edge sits just under the plate top
    )
    paper = await place_component(
        adapter,
        "pd-platen-paper",
        [
            PLATE_X0 + paper_left_margin,
            PLATE_Y0 + PLATE_HEIGHT - RECORDING_GEOMETRY.RECORDING_PAPER_HEIGHT_MM - paper_top_margin,
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
    clip_targets = [[x, y, PLATE_FRONT_Z - CLIP_THICKNESS] for x, y in CLIP_SCREW_XY]
    clip_max_x = max(target[0] for target in clip_targets)
    clip_seed_target = min(
        (target for target in clip_targets if target[0] == clip_max_x),
        key=lambda target: target[1],
    )
    clip_seed = await place_component(
        adapter,
        "pd-vn-platen-clip-screw",
        clip_seed_target,
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
        label=(
            f"platen-clip screw seed "
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
        "sh-vn-brass-fillister-screw",
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

    # Two seeds at the right-hand station reproduce at the left-hand station;
    # under-head planes sit on the real 1/16-sheet lock back faces.
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
            "pd-vn-guide-lock-screw",
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
    arm = await place_component(
        adapter,
        "pd-transgear-arm",
        [PIVOT_XY[0], PIVOT_XY[1], ARM_Z0],
        [0.0, 0.0, ARM_ANGLE_DEG],
        arm_rows,
    )
    # Rx(+90): the shoulder runs to -Z, bottoming on the bar's back face.
    await place_component(
        adapter,
        "pd-vn-transgear-pivot-screw",
        [PIVOT_XY[0], PIVOT_XY[1], PIVOT_SCREW_Z0],
        [90.0, 0.0, 0.0],
        ROT_X_POS90,
    )
    # MHA-PD-VN-63 (identity: +Z axial) in the arm's spot face, under the head.
    await place_component(
        adapter,
        "pd-vn-transgear-pivot-spring",
        [PIVOT_XY[0], PIVOT_XY[1], PIVOT_SPRING_Z0],
        [0.0, 0.0, 0.0],
        IDENTITY,
    )
    plate_origin = [KNOB_SHAFT_XY[0], KNOB_SHAFT_XY[1], PLATE_Z0]
    arm_plate = await place_component(
        adapter, "pd-transgear-arm-plate", plate_origin,
        [0.0, 0.0, ARM_ANGLE_DEG], arm_rows, ground=False,
    )
    # Physical seat 3DOF + ONE primary dowel 2DOF + clock 1DOF.
    # The second pin is inspected, not a redundant second concentric mate.
    # Two reference axes take a coincident mate (the repo's axis-to-axis
    # coaxial idiom); CreateMate refuses concentric between two axes (run
    # 20261010T001620278Z: "CreateMate failed for concentric mate").
    await coincident_mate(
        adapter, named_ref(f"Front Plane@{arm_plate}", "PLANE"),
        named_ref(f"RearFace@{arm}", "PLANE"),
        label="arm-plate actual mounting seat", verify=(arm_plate, plate_origin),
    )
    await coincident_mate(
        adapter, named_ref(f"Axis4@{arm_plate}", "AXIS"),
        named_ref(f"Axis6@{arm}", "AXIS"),
        label="arm-plate primary locating dowel", verify=(arm_plate, plate_origin),
    )
    await parallel_mate(
        adapter, named_ref(f"LocatorClock@{arm_plate}", "PLANE"),
        named_ref(f"LocatorClock@{arm}", "PLANE"),
        label="arm-plate common locator clock", verify=(arm_plate, plate_origin),
        witness_local=[*ARM_PLATE.LOCATOR_SITES_MM[1], 0.0],
    )
    assert_component_placed(adapter, arm_plate, plate_origin, arm_rows)
    _assert_arm_plate_registered(adapter, arm, arm_plate)
    for index, (x, y) in enumerate(LOCATING_PIN_XY, 1):
        pin_origin = [x, y, LOCATING_PIN_Z0]
        locating_pin = await place_component(
            adapter, "pd-vn-transgear-arm-plate-locating-pin", pin_origin,
            [-90.0, 0.0, 0.0], ROT_X_NEG90, ground=False,
        )
        await coincident_mate(
            adapter, named_ref(f"ScrewAxis@{locating_pin}", "AXIS"),
            named_ref(f"Axis{index + 5}@{arm}", "AXIS"),
            label=f"locating dowel {index} arm press axis", verify=(locating_pin, pin_origin),
        )
        # The dowel's spin is immaterial; clock it to the grounded frame it
        # was placed in. Its origin sits on the axis, so an off-axis witness
        # separates the two parallel solutions.
        await parallel_mate(
            adapter, named_ref(f"Right Plane@{locating_pin}", "PLANE"),
            named_ref("Right Plane", "PLANE"),
            label=f"locating dowel {index} spin clock", verify=(locating_pin, pin_origin),
            witness_local=[1.0, 0.0, 0.0],
        )
        # Same rows and plane pair as run 9, whose -4.30 (origin into the
        # arm) verified on the -Z side; the proud end is +1.70 on the +Z side.
        await distance_driver(
            adapter, named_ref(f"Top Plane@{locating_pin}", "PLANE"),
            named_ref(f"RearFace@{arm}", "PLANE"),
            LOCATING_INTERFACE.PROUD_MM,
            label=f"locating dowel {index} proud stop", verify=(locating_pin, pin_origin),
        )
        assert_component_placed(adapter, locating_pin, pin_origin, ROT_X_NEG90)
    for k, (x, y) in enumerate(PLATE_SCREW_XY, start=1):
        await place_component(
            adapter,
            "pd-vn-transgear-arm-plate-screw",
            [x, y, PLATE_SCREW_Z0],
            [90.0, 0.0, 0.0],
            ROT_X_POS90,
            label=f"transgear-arm-plate-screw #{k} (station {ARM.PLATE_TAP_STATIONS[k - 1]})",
        )
    await place_component(
        adapter,
        "pd-vn-transgear-latch-pin",
        list(LATCH_PIN_POS),
        [0.0, 0.0, ARM_ANGLE_DEG - 90.0],
        rot_z_rows(ARM_ANGLE_DEG - 90.0),
    )
    # Latch hook MHA-PD-14 behind the bar: the one-piece hook by translation,
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
        screw = await place_component(
            adapter,
            "sh-vn-fillister-screw-90280a108",
            [x, y, z],
            [90.0, 0.0, 0.0],
            ROT_X_POS90,
            label=f"latch-hook-bracket-screw (x{x:.1f})",
        )
        await apply_component_color(adapter, screw, POLISHED_STEEL)
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
    running_pin = await place_component(
        adapter,
        "pd-transgear-pin",
        [STUD_XY[0], STUD_XY[1], PIN_Z0],
        [0.0, 180.0, 0.0],
        ROT_Y_180,
    )
    # Ry(180): the rear bushing's arm face on the arm's front face, its sleeve
    # face REAR_BUSHING.LENGTH forward (printed, model at nominal).
    await place_component(
        adapter,
        "pd-transgear-rear-bushing",
        [STUD_XY[0], STUD_XY[1], REAR_BUSHING_Z0],
        [0.0, 180.0, 0.0],
        ROT_Y_180,
    )
    # 150T 48DP PA20 reducer disc on the feed sleeve's seat, FREE (revolute below) --
    # gear-mated to the knob shaft's 15T. Identity spin: a tooth points along
    # the S -> K line (MESH_ANGLE is a multiple of its 2.4-deg pitch).
    disc = await place_component(
        adapter,
        "pd-rack-pinion",
        [STUD_XY[0], STUD_XY[1], DISC_Z0],
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
        label=f"rack-pinion ({DISC_TEETH}T reducer disc)",
    )
    await _sprocket_revolute(adapter, disc, "reducer disc")
    # The shifted 12T 32DP PA20 feed sleeve runs on the pin, rear face on the rear
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
            "pd-vn-transgear-disc-screw",
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
    # Ry(180): the front bushing's rear face on the sleeve's nose, at its
    # printed length; the MHA-PD-VN-61 ring in the pin's groove
    # SLEEVE_FLOAT_MODEL in front of it, its front face on the groove's load wall.
    await place_component(
        adapter,
        "pd-transgear-front-bushing",
        [STUD_XY[0], STUD_XY[1], FRONT_BUSHING_Z0],
        [0.0, 180.0, 0.0],
        ROT_Y_180,
    )
    await place_component(
        adapter,
        "pd-vn-transgear-retaining-ring",
        [STUD_XY[0], STUD_XY[1], CLUSTER.RING_REAR_Z],
        [0.0, 180.0, 0.0],
        ROT_Y_180,
    )

    # --- knob stack on K ---------------------------------------------------------
    # Mounted knob removable: swapping wheels changes the platen ratio.
    # Its one free spin is coupled to the crank by the belt/chain feature.
    # The native chain is a visual pose, not roller-seat certification.
    # Mounted wheel, collar and both dowels follow the integral shaft's D-clock.
    # Inserted before the crank wheel and spare T18: first transgear-removable.
    knob_wheel = await place_component(
        adapter,
        "pd-transgear-removable",
        [KNOB_SHAFT_XY[0], KNOB_SHAFT_XY[1], REMOVABLE_Z0],
        [0.0, 0.0, THIRD_PHASE_DEG],
        KNOB_FRONT_STACK_ROT,
        configuration=REMOVABLE.KNOB_CONFIG,
        ground=False,
        label=f"transgear-removable (mounted knob {REMOVABLE.KNOB_CONFIG})",
    )
    await _sprocket_revolute(adapter, knob_wheel, "knob chain wheel")
    # The drive collar carries the knob wheel the way the machine does: coaxial, its
    # front face on the wheel's RearFace, clocked so its drive pins ride the
    # wheel's pin holes. The complete front stack keeps the wheel's single
    # free spin and the integral shaft's actual tooth phase.
    collar = await place_component(
        adapter,
        "pd-transgear-drive-collar",
        [KNOB_SHAFT_XY[0], KNOB_SHAFT_XY[1], KNOB_COLLAR_Z0],
        [0.0, 0.0, THIRD_PHASE_DEG],
        KNOB_FRONT_STACK_ROT,
        ground=False,
    )
    collar_o = component_origin(adapter, collar)
    await coincident_mate(
        adapter,
        named_ref(f"Axis1@{collar}", "AXIS"),
        named_ref(f"Axis1@{knob_wheel}", "AXIS"),
        label="drive collar coaxial with the mounted knob wheel",
        verify=(collar, collar_o),
    )
    await coincident_mate(
        adapter,
        named_ref(f"Front Plane@{collar}", "PLANE"),
        named_ref(f"RearFace@{knob_wheel}", "PLANE"),
        label="drive collar front face on the knob wheel rear face",
        verify=(collar, collar_o),
    )
    # The collar origin sits ON the spin axis, so only an off-axis witness (a
    # drive-pin station) separates the two parallel solutions.
    await parallel_mate(
        adapter,
        named_ref(f"Right Plane@{collar}", "PLANE"),
        named_ref(f"Right Plane@{knob_wheel}", "PLANE"),
        label="drive collar pins clocked into the knob wheel pin holes",
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

    # The two MHA-PD-VN-54 dowels pressed through the collar (Rx-90: rounded ends
    # forward in the knob wheel's pin holes), +Y first.
    for k, (x, y) in enumerate(KNOB_DRIVE_PIN_XY, start=1):
        knob_pin = await place_component(
            adapter,
            "pd-vn-transgear-knob-drive-pin",
            [x, y, KNOB_DRIVE_PIN_Z0],
            euler_from_rows(KNOB_DRIVE_PIN_ROT),
            KNOB_DRIVE_PIN_ROT,
            ground=False,
            label=f"MHA-PD-VN-54 knob drive pin #{k} (y{y:.1f})",
        )
        await _lock_to_collar(knob_pin, f"drive pin #{k}")
    # Knob shaft MHA-PD-08 on its datum F (the 15T's front face), spun so a gap
    # of its 15T faces the disc's tooth on the S -> K line.
    knob_shaft = await place_component(
        adapter,
        "pd-transgear-knob-shaft",
        [KNOB_SHAFT_XY[0], KNOB_SHAFT_XY[1], KNOB_SHAFT_Z0],
        [0.0, 0.0, THIRD_PHASE_DEG],
        rot_z_rows(THIRD_PHASE_DEG),
        ground=False,
    )
    shaft_o = component_origin(adapter, knob_shaft)
    await coincident_mate(
        adapter, named_ref(f"Axis1@{knob_shaft}", "AXIS"),
        named_ref(f"Axis1@{collar}", "AXIS"),
        label="integral knob D-core coaxial with collar",
        verify=(knob_shaft, shaft_o),
    )
    # F on the arm chain: the nominal collar's rear stands KNOB_COLLAR_REAR_GAP
    # in front of it (the fit-up facing's remainder).
    if KNOB_COLLAR_REAR_GAP > 1e-9:
        await distance_driver(
            adapter, named_ref(f"Front Plane@{knob_shaft}", "PLANE"),
            named_ref(f"RearFace@{collar}", "PLANE"),
            KNOB_COLLAR_REAR_GAP,
            label="gear front F behind the nominal collar rear",
            verify=(knob_shaft, shaft_o),
        )
    else:
        await coincident_mate(
            adapter, named_ref(f"Front Plane@{knob_shaft}", "PLANE"),
            named_ref(f"RearFace@{collar}", "PLANE"),
            label="actual collar rear reaction face on gear front F",
            verify=(knob_shaft, shaft_o),
        )
    await parallel_mate(
        adapter, named_ref(f"Right Plane@{knob_shaft}", "PLANE"),
        named_ref(f"Right Plane@{collar}", "PLANE"),
        label="integral knob D-flat clocked to actual collar flat",
        verify=(knob_shaft, shaft_o), witness_local=[0.0, -1.0, 0.0],
    )
    _assert_knob_collar_capture(adapter, collar, knob_shaft)

    async def _lock_to_shaft(name: str, label: str) -> None:
        await lock_mate(
            adapter,
            named_ref(f"Front Plane@{name}", "PLANE"),
            named_ref(f"Front Plane@{knob_shaft}", "PLANE"),
            label=f"knob stack: {label} locked to the knob shaft",
        )

    # Knurled thumbnut OUTERMOST on the shaft's front thread, its flange's
    # seat on the collar's pilot, the wheel free under it (ch23 p.58/59; R9-70).
    # Rx(-90): local +Y -> -Z, the knurled head at the machine front.
    thumbnut = await place_component(
        adapter,
        "pd-transgear-thumbnut",
        [KNOB_SHAFT_XY[0], KNOB_SHAFT_XY[1], THUMBNUT_Z0],
        [-90.0, 0.0, 0.0],
        ROT_X_NEG90,
        ground=False,
        label="transgear-thumbnut (seated on collar pilot, retains the knob wheel)",
    )
    await _lock_to_shaft(thumbnut, "thumbnut")
    log(
        f"thumbnut z {THUMBNUT_FRONT_Z:.2f}..{THUMBNUT_Z0:.2f} (seat on the pilot,"
        f" {THUMBNUT_AIR:.2f} proud of the knob wheel face {REMOVABLE_Z0});"
        f" shaft front {KNOB_SHAFT_FRONT_Z:.2f}"
        f" ({KNOB_SHAFT_FRONT_Z - THUMBNUT_FRONT_Z:+.2f} inside the nut rim,"
        f" engagement {THUMBNUT_ENGAGEMENT:.2f}); tap {THUMBNUT_THREAD}; front-most"
        f" furniture near the knob axis: chain plates to z"
        f" {CHAIN_MID_Z - CHAIN_PIN_HALF_LEN:.2f} (radial gap to the head"
        f" {_chain_inner_wrap_r - THUMBNUT_HEAD_DIA / 2.0:.1f})"
    )
    # Behind the 15T (Rx+90): the thrust ring to the plate hub, the knob cup on
    # the journal's rear end, and the MHA-PD-VN-62 spring pin through both (R9-70).
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
        "pd-vn-transgear-knob-cup-pin",
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
    # Crank-end removable = the crank-shaft chain wheel, brought over from
    # drive-train so the chain seats on BOTH sprockets locally. Placed at the
    # MACHINE crank centre = -CHAIN_CRANK_CENTRE (the pre-mirror _chain anchor,
    # == canonical lower crank axis at CHAIN_MID_Z; _assert_chain_layout pins it).
    # On the same band as the knob wheel (front face BAND_FRONT_Z, identity: its pin
    # holes on machine +/-Y over the crankshaft's drive pins, which
    # drive-train places). FREE to spin -- this is the crank input, the
    # single operational DOF.
    crank_wheel = await place_component(
        adapter,
        "pd-transgear-removable",
        [-CHAIN_CRANK_CENTRE[0], CHAIN_CRANK_CENTRE[1], REMOVABLE_Z0],
        [0.0, 0.0, 0.0],
        IDENTITY,
        configuration=REMOVABLE.CRANK_CONFIG,
        ground=False,
        label=f"transgear-removable (crank chain wheel {REMOVABLE.CRANK_CONFIG})",
    )
    await _sprocket_revolute(adapter, crank_wheel, "crank chain wheel")
    # The roller chain looping both removables (_assert_chain_layout pins the
    # _chain.py anchors to KNOB_SHAFT_XY / the drive-train crank).
    shown = _shown_planes(adapter)
    await _insert_roller_chain(adapter)
    hide_generated_planes(adapter, shown, "roller chain pattern")

    # --- operational coupling (every stage a real mate) ------------------------
    # (1) The native Belt/Chain assembly feature couples the selected crank and
    # knob wheels in the SAME rotation sense (an external gear mate reverses).
    # Each link engages one tooth: crank revs * CRANK_TEETH == knob revs *
    # KNOB_TEETH. Typed diameters use N * p / pi, not the physical pitch
    # diameters p / sin(pi/N), whose ratio is nonlinear in the tooth counts.
    # Pulley members are Axis1 DATUM AXES, not faces: a face member bakes the
    # picked face's diameter into the EngageBelt coupling, ignoring typed values.
    # An axis has no diameter to steal, so the typed diameters drive the exact
    # tooth ratio (probed live 2026-07-06;
    # memory/belt-chain-feature-com-binding.md). The adapter reads the mate's
    # own D1/D2 back and fails loud on a mismatch. EngageBelt authors the
    # coupling mates; CreateBeltPart stays off -- the roller-chain component
    # pattern above is the visual. Both sprockets stay FREE (Axis1 pinned,
    # spin-only via _sprocket_revolute), so the belt constrains only their
    # relative rotation -- 0 net free DOF added.
    from solidworks_mcp.adapters.base import BeltChainParameters

    shown = _shown_planes(adapter)
    check(
        f"chain coupling {REMOVABLE.CRANK_CONFIG}<->{REMOVABLE.KNOB_CONFIG}"
        f" (belt/chain feature, {REMOVABLE.CRANK_TEETH}:{REMOVABLE.KNOB_TEETH} teeth)",
        await adapter.insert_belt_chain(
            BeltChainParameters(
                pulley_components=[crank_wheel, knob_wheel],
                pulley_diameters=[
                    CHAIN_PULLEY_DIA[REMOVABLE.CRANK_CONFIG],
                    CHAIN_PULLEY_DIA[REMOVABLE.KNOB_CONFIG],
                ],
                pulley_member_axes=[f"Axis1@{crank_wheel}", f"Axis1@{knob_wheel}"],
                location_plane="Front Plane",
                engage_belt=True,
                create_belt_part=False,
                blank_sketch=True,
            )
        ),
    )
    hide_generated_planes(adapter, shown, "belt/chain coupling")
    # (2) GEAR mate: the integral knob pinion drives the reducer disc.
    await gear_mate(
        adapter,
        named_ref(f"Axis1@{knob_shaft}", "AXIS"),
        named_ref(f"Axis1@{disc}", "AXIS"),
        [THIRD_TEETH, DISC_TEETH],
        label=f"knob shaft {THIRD_TEETH}T : disc {DISC_TEETH}T ({DISC_DP:g}DP)",
    )
    # (3) RACK-PINION mate: the feed pinion (locked to the disc) feeds the
    # platen at its reference pitch circumference (profile shift does not alter it).
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
    # recorded into the DOF manifest, never authored -- the crank wheel spins free and
    # drives the whole gear+rack train. A spur sprocket is symmetric so the
    # spin pose is cosmetic; pin the local Right-plane dihedral (read live)
    # like drive-train's crank_angle.
    crank_wheel_o = component_origin(adapter, crank_wheel)
    crank_wheel_transform = component_transform(adapter, crank_wheel)
    crank_dihedral = math.degrees(
        math.acos(max(-1.0, min(1.0, crank_wheel_transform[0])))
    )
    await angle_driver(
        adapter,
        named_ref(f"Right Plane@{crank_wheel}", "PLANE"),
        named_ref("Right Plane", "PLANE"),
        crank_dihedral,
        label=f"crank spin PARK driver (freed in default build; a={crank_dihedral:.2f})",
        verify=(crank_wheel, crank_wheel_o),
        free_dof_key="crank_spin",
    )

    # Spare T18 removable: the swap chain wheel resting loose on the base, west
    # of the platen (a flat sibling of the mounted knob wheel above).
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
    # rack-fed platen. Target the SPECIFIC crank-wheel instance, not the shared
    # ``pd-transgear-removable`` stem: knob and spare wheels share it, so a stem
    # check could pass with the crank pinned and another wheel free (codex #189).
    assert_free_dof_necessity(adapter, 1, required_instances=(crank_wheel,))
    write_dof_manifest(ASM_NAME)
    _assert_native_rack_operating_pose(adapter, rack_operating_domain, rack, running_pin)
    check_no_interference(
        adapter,
        allowed_pairs=allowed_interference_pairs(ASM_NAME),
        chain_mounts=mounted_wheels(),
    )
    # K's DRO setting from S, for MHA-PD-00's VIEW K (hidden sketch only).
    await _author_knob_setting_reference(adapter)
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
        lambda configuration: create_paper_drive_explode(adapter, configuration),
    )
    outputs = await save_assembly_and_images(adapter, ASM_NAME)
    # Saving authors the drawing configurations and rebuilds the pattern.
    # Re-read native references afterwards; the parent gate additionally reopens.
    _chain_reference_names(adapter.currentModel)
    return outputs


if __name__ == "__main__":
    sys.exit(run_build(build))
