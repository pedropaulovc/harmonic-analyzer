r"""Reproduction script: summing subassembly (book ch. 18-19).

The head of the analyzer's output, where the 20 channel springs converge on
the summing lever, in machine coordinates (assembly origin = base origin;
base top y = 50.8; the output side is -Z). The lever rocks on a true knife
edge carried by two bearing supports, each clamped to the underside of the
top-frame casting's integral crossbar by one knife-hanger screw and located
by one pressed dowel, and counter-balanced from above by the
boss-hook / counter-spring / gooseneck chain.

* knife-mount x2 -- the bearing supports, one per hex trunnion, centred on
  ``SUMMING_Z`` and separated by ``+/-HEX_Z_MID``; each top seat is clamped
  to the crossbar underside (``MOUNT_GAP`` 0).
* knife-hanger-stud x2 -- McMaster 92314A253 #10-24 plain hex bolts from
  2 in stock, each cut at this assembly to the stack measured at its hole
  plus the .351 +/-.006 in fit-up reach (46.70 mm nominal under the head);
  each passes the crossbar's #10 clearance hole (C drill) and threads into the
  knife-mount tap.
* knife-hanger-washer x2 -- new McMaster 96659A104 18-8 SAE washers,
  one beneath each hex head, seated on the crossbar's faced top.
* knife-mount-dowel x2 -- McMaster 98381A473 1/8 x 3/4 dowels, one per
  knife mount +X of its screw, each pressed up to the floor of a blind ream
  in the crossbar's faced underside (knocked out from its faced top; owner
  ruling 2026-10-24, T+H3); the knife mount's blind round hole slips onto
  it.  Owner ruling 2026-11-08 (Pedro), #2144 item 11.3 (scheme S1): the
  block may turn about its one dowel; a Ø.4720 gauge bar through both
  mounts' bores sets the yaw at MHA-SM-00 before the screws are tightened.
* summing-lever -- rocks on the knife edge (Axis3 coincident to the support
  contact ridge); the part the channel + counter springs drive in the M6
  Motion study. The rock is the sub's single FREED operational DOF: its
  drive spec is recorded into the DOF manifest, never authored, so the
  saved model rocks on the knife edge.
* boss-hook (keyed to the lever's anchor eye) + its MHA-SM-VN-55 jam nut on the
  boss top face + counter-spring + gooseneck -- the counter-balance hung from
  the east column; the gooseneck's brazed O15.875 sleeve is the post the
  top-frame rail hub's set screw grips (no separate clamp part).
* sm-vn-gooseneck-shoulder-screw -- purchased MHA-SM-VN-56 slotted shoulder
  screw, head outboard, its shoulder seated on the face of the gooseneck's
  flush end piece and its 10-24 thread in the end piece's plain blind tap.
  Owner ruling 2026-11-08 (Pedro), #2144 item 11.4, superseding #1951's
  clamped eye: the supplier upper loop rides free on the shoulder between the
  end face and the head (bare slotted McMaster 91829A566, washer dropped).
  Locked to the fixed gooseneck with no additional operational DOF.

Cross-subassembly fits (checked at the top level): the channel springs
(ch-channel.SLDASM) thread the summing-lever plate's O4.5 holes -- gated
analytically by build_ch_channel_assembly._assert_plate_threading; the knife-
hanger bolts pass the top-frame crossbar's O6.147 clearance holes and clamp
through their washers on its faced top; the knife-mount dowels press into
its blind reams (fr-frame.SLDASM); the gooseneck's sleeve drops
through the casting's rail-hub bore, gripped by its 1/4-20 set screw.

Fix-all strategy (M6.2): every structural component inserted at its exact
final transform and fixed; the summing lever, boss-hook and jam nut are left
free and constrained by mates; transforms asserted by read-back; zero
interference.

Dimensions: cad/DIMENSIONS.md ch. 18-19.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_sm_summing_assembly.py
"""

from __future__ import annotations

import math
import sys

from _check import check, log
from _assembly_contract import assembly_contract
from _com import _early_bound
from _custom_properties import apply_custom_properties
from _dimensions import drive_dimension, set_global
from _document_units import apply_package_model_units
from _drawing_precision import apply_drawing_precision
from _feature_tree import name_last_feature
from _session import run_build
from _sketch import (
    SketchDims,
    anchor_point_to_origin,
    blank_sketch,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sm_summing_explode import create_summing_explode
import settled_spring_seats
import sm_summing_assembly_spec as spec
from _drawing_marks import DRAWN_BY, mark_dimensions_for_drawing
from _assembly import (
    activate_assembly_contract,
    angle_driver,
    assembly_title_properties,
    assert_free_dof_necessity,
    assert_component_placed,
    author_in_drawing_configurations,
    check_no_interference,
    coincident_mate,
    component_names,
    component_origin,
    component_transform,
    distance_driver,
    lock_mate,
    named_ref,
    place_component,
    reset_dof_manifest,
    save_assembly_and_images,
    write_dof_manifest,
)
from _native_spring_contact import assert_assembly_spring_contacts
from _sm_summing_interference import ALLOWED_PAIRS
from _transforms import IDENTITY, ROT_X_NEG90, ROT_Y_180, ROT_Y_POS90, euler_from_rows
from _cone_axis_constants import SUMMING_Z
import fr_top_frame_spec as top_frame
import sm_knife_mount_spec as knife_mount
import sm_vn_knife_hanger_stud_spec as hanger_screw
import sm_vn_knife_hanger_washer_spec as hanger_washer
import sm_vn_knife_mount_dowel_spec as knife_dowel
from build_sm_knife_mount import CASTING_UNDERSIDE_Y, MOUNT_GAP

ASM_NAME = "sm-summing"

from spring_mount_geom import COLUMN_X, KNIFE, KNIFE_CONTACT_Y  # noqa: E402

# --- knife bearing supports (build_sm_knife_mount) -----------------------------
from sm_summing_lever_spec import (  # noqa: E402
    HEX_Z_INNER,
    HEX_Z_OUTER,
    KNIFE_SHOULDER_DROP_MIN,
    KNIFE_SHOULDER_X_MAX,
)

HEX_Z_MID = (HEX_Z_INNER + HEX_Z_OUTER) / 2.0  # hex trunnion mid (87.06)

# --- knife-hanger hardware (two #10-24 hex bolts, washers and dowels) ---------
# The top-frame, knife-mount and purchased hardware specs own every term.
# The bolt frame has its cut tip at local Y=0, axis +Y. Its under-head face
# bears on the washer's upper face; the washer's local Y=0 lower bearing face
# seats on the crossbar's faced top, HANGER_GRIP above the finished underside.
# The knife mount remains clamped face-to-face to that underside, gap 0,
# with no bedding allowance. Each dowel (local Y=0 its lower end, axis +Y)
# is pressed up to the floor of its crossbar ream (owner ruling 2026-10-24,
# T+H3) and hangs into the knife mount's round slip hole (datum B).
KNIFE_MOUNT_TOP_Y = CASTING_UNDERSIDE_Y - MOUNT_GAP  # 999.6932: clamped, gap 0
CROSSBAR_TOP_Y = CASTING_UNDERSIDE_Y + top_frame.RING_HEIGHT  # 1036.193, faced
HANGER_WASHER_Y = CASTING_UNDERSIDE_Y + top_frame.HANGER_GRIP  # 1036.193, local Y=0
HANGER_UNDERHEAD_Y = HANGER_WASHER_Y + hanger_washer.THICKNESS  # 1037.4759
HANGER_STUD_Y = HANGER_UNDERHEAD_Y - hanger_screw.LENGTH  # 990.7759 (cut tip)
HANGER_REACH = KNIFE_MOUNT_TOP_Y - HANGER_STUD_Y  # 8.9173, the modelled nominal
# Worst-case stack (drawing-guidelines.md rules 18–19): MHA-SM-00 step 4
# cuts each bolt to the crossbar-underside-to-washer-top height measured at
# its own hole plus the fit-up reach, so the printed grip band and the
# washer's catalogue thickness spread are measured out and only the cut's
# own band reaches the tap: .346-.356 in, 8.7884..9.0424.
HANGER_REACH_MIN = spec.HANGER_FIT_REACH - spec.HANGER_FIT_REACH_TOL
HANGER_REACH_MAX = spec.HANGER_FIT_REACH + spec.HANGER_FIT_REACH_TOL
# The cut must come out of the 2 in stock and remove its factory end: the
# longest cut is the thickest printed grip plus the thickest washer plus
# the longest reach, 47.3202; the shortest is the thinnest of each plus the
# shortest reach, 46.0756.
HANGER_CUT_LENGTH_MIN = (
    top_frame.HANGER_GRIP
    - top_frame.HANGER_GRIP_TOL
    + hanger_washer.THICKNESS_MIN
    + HANGER_REACH_MIN
)
HANGER_CUT_LENGTH_MAX = (
    top_frame.HANGER_GRIP
    + top_frame.HANGER_GRIP_TOL
    + hanger_washer.THICKNESS_MAX
    + HANGER_REACH_MAX
)
# Charge the cut end's maximum incomplete lead, one pitch:
# 7.7300667 >= 1.5D = 7.239.
HANGER_ENGAGEMENT_MIN = HANGER_REACH_MIN - hanger_screw.INCOMPLETE_TIP_LEN_MAX
HANGER_ENGAGEMENT_FLOOR = hanger_screw.ENGAGEMENT_MIN_D * hanger_screw.SHANK_DIA
# Longest reach under the shallowest full tap: 9.52 - 9.0424 = 0.4776 air.
HANGER_TIP_CLEARANCE = knife_mount.STUD_TAP_THREAD_DEPTH_MIN - HANGER_REACH_MAX
# Modified-part inspection acceptance, not a vendor thread-to-head claim:
# the useful full-form tail (.418 MIN, 10.6172, less one incomplete pitch)
# spans 9.0424.
HANGER_THREAD_SPARE = (
    hanger_screw.THREAD_LENGTH_MIN - hanger_screw.INCOMPLETE_TIP_LEN_MAX
) - HANGER_REACH_MAX
HANGER_SCREW_CLEARANCE = top_frame.HANGER_CLEARANCE_DIA_MIN - hanger_screw.SHANK_DIA
# Each dowel's pressed (chamfered) end, its local Y=0, on its crossbar ream
# floor, 1011.7, its local +Y turned down (Rx 180): its far end 992.65,
# standing PROUD 7.05 below the underside into the knife mount's round hole
# (floor 990.2).
KNIFE_DOWEL_Y = CASTING_UNDERSIDE_Y + top_frame.HANGER_PIN_HOLE_DEPTH
KNIFE_DOWEL_END_Y = KNIFE_DOWEL_Y - knife_dowel.LENGTH
KNIFE_DOWEL_ROWS = [[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]]
# The one dowel's station from the bolt axis, +X (datum B): 7.62 along X
# (Owner ruling 2026-11-08 (Pedro), #2144 item 11.3).
KNIFE_DOWEL_X_OFFSETS = (knife_mount.PIN_HOLE_X,)
# The bolt must pass the crossbar's #10 clearance hole (a C drill, owner
# ruling 2026-11-06) at the printed-band
# worst case (drawing-guidelines.md rule 19 (absorb stacks)) when every
# station sits at its limit.  Owner ruling 2026-11-08 (Pedro), #2144 item
# 11.3 (scheme S1): one dowel (pressed into the crossbar, slipping into
# the block's round hole B) and the bolt hang each block, which so fits one
# way round only; the block may turn about its dowel, and the MHA-SM-00
# gauge bar sets that turn.
# Along the dowel line (X): the ream's .XXX station from the screw axis
# (0.127), the spotted tap's residual (the former Ø.005 zone's radius,
# 0.064), B's round hole across its loosest slip on its pin (0.046) and B's
# datum simulator off the pin root (⊥Ø.001|A, t/2 = 0.013; codjiflo round
# 5, wyUmn: the worst case is the pin leaning parallel to the hole's tilt,
# which stays within the ream's ⊥, so the pin's own lean adds nothing past
# the slip): 0.249.  The block cannot slide off its pin, so the bar moves
# nothing along the line.
# Across it (Z): the ream's implied-zero .XXX "SAME Z" (0.127), the same
# three block terms, and the turn the bar gives the block about its dowel:
# the tap, PIN_HOLE_X from B, moves across by that turn times its reach
# (KNIFE_BAR_YAW_SHIFT).  The bar line runs through both bores, each off
# its station across the line by its #10 hole's centring to datum D
# (⌖.010|D, owner ruling 2026-11-06: 0.127), the ream's .XXX station, B's
# slip and simulator and the bore's ⌖Ø.008|A|B zone radius (0.102), 0.414,
# at opposite limits over the stations' spacing (174.12): a 0.27 deg turn
# moving the tap 0.036.  The
# rear mount, re-hung on the lever's stub at MHA-SM-00 and swung about its
# dowel until the rock gauge passes, needs that same turn (the lever's
# ridge lies along the bar-set front bore); KNIFE_REAR_YAW_RANGE_DEG is the
# turn its bolt float allows.  hypot(0.249, 0.285) = 0.379.
_KNIFE_DOWEL_SLIP_MAX = knife_dowel.SLIP_CLEARANCE_MAX
KNIFE_BLOCK_SHIFT = (
    top_frame.HANGER_PIN_X_TOL
    + knife_mount.STUD_TAP_POSITION_TOL / 2.0
    + _KNIFE_DOWEL_SLIP_MAX / 2.0
    + knife_mount.DOWEL_HOLE_PERPENDICULARITY_TOL / 2.0
)  # 0.2489
KNIFE_BORE_LINE_OFFSET = (
    top_frame.HANGER_CROSSBAR_CENTER_TOL
    + top_frame.HANGER_PIN_X_TOL
    + _KNIFE_DOWEL_SLIP_MAX / 2.0
    + knife_mount.DOWEL_HOLE_PERPENDICULARITY_TOL / 2.0
    + knife_mount.KNIFE_BORE_POSITION_TOL / 2.0
)  # 0.4140
_KNIFE_STATION_SPACING = top_frame.STUD_Z_REAR - top_frame.STUD_Z_FRONT  # 174.12
KNIFE_BAR_YAW_DEG = math.degrees(
    math.atan(2.0 * KNIFE_BORE_LINE_OFFSET / _KNIFE_STATION_SPACING)
)  # 0.272
KNIFE_BAR_YAW_SHIFT = knife_mount.PIN_HOLE_X * math.tan(math.radians(KNIFE_BAR_YAW_DEG))
HANGER_SCREW_MISMATCH_X = KNIFE_BLOCK_SHIFT
HANGER_SCREW_MISMATCH_Z = KNIFE_BLOCK_SHIFT + KNIFE_BAR_YAW_SHIFT
HANGER_SCREW_MISMATCH = math.hypot(HANGER_SCREW_MISMATCH_X, HANGER_SCREW_MISMATCH_Z)
# The hole is drilled from the finished underside. Prove drift over the FULL
# crossbar body to the hole's top end at the faced top, at the longest
# printed grip: tan(0.3 deg) * (36.50 + 0.13) = 0.1918. The #10 C drill
# hole's 0.6604 radial float covers this plus the station mismatch,
# 0.3785, with 0.0901 spare (HANGER_SCREW_FLOAT_SPARE).
HANGER_SCREW_DRIFT = top_frame.DRILL_DRIFT_PER_MM * (
    top_frame.HANGER_GRIP + top_frame.HANGER_GRIP_TOL
)
HANGER_SCREW_FLOAT_SPARE = top_frame.HANGER_SCREW_FLOAT - (
    HANGER_SCREW_MISMATCH + HANGER_SCREW_DRIFT
)
# The rear mount's adjust range about its dowel: the largest turn before the
# bolt's shank meets its clearance hole with every other term at its limit
# -- the across-line room left inside the float circle, less the drift and
# the along-line mismatch, over the tap's reach from B.  It must cover the
# turn the rock gauge can ask for (KNIFE_BAR_YAW_DEG).
_KNIFE_FLOAT_LEFT = top_frame.HANGER_SCREW_FLOAT - HANGER_SCREW_DRIFT
KNIFE_REAR_YAW_RANGE_DEG = math.degrees(
    math.atan(
        (
            math.sqrt(max(_KNIFE_FLOAT_LEFT**2 - HANGER_SCREW_MISMATCH_X**2, 0.0))
            - KNIFE_BLOCK_SHIFT
        )
        / knife_mount.PIN_HOLE_X
    )
)
# Free rock at the printed-band worst case (drawing-guidelines.md rule 19
# (absorb stacks), and the 2026-10-09 ruling: >=5.0 deg).  Owner ruling
# 2026-11-08 (Pedro), #2144 item 11.3: the part no longer sets the bore's
# yaw.  The gauge bar sets the front mount's bore, so its far-end offset t
# is the bar's diametral clearance in the largest bore, .4735 - (.4720 -
# .0002) = .0017 (0.0432), and the lever's ridge, spanning both bores, adds
# its yaw over the shortest mouth-to-mouth run (codjiflo, PR #1978): that
# clearance walked across the deepest .XX block, 14.224 * 0.0432 / 159.9 =
# 0.0038.  t 0.047 leaves about 7.76 deg.  The bore's ∥.002|A is its
# pitch, which the lateral rock model (free_rock_deg) does not read.  The
# rear mount's yaw is accepted by the rock gauge itself
# (sm_summing_assembly_spec.BOSS_ROCK_TRAVEL, sheet check 2): the fitter
# swings it until the boss travels the gauge each way, which is the 5.0 deg
# floor, so the gauge directly proves the floor for the lever on both
# mounts; this budget proves the bar-set front mount leaves margin over it.
# Judge the trunnion in the smallest reamed bore at the shoulder its
# printed controls allow worst: the ridge farthest from that side face, the
# flank at its flattest (code review C09:
# ``sm_summing_lever_spec.KNIFE_SHOULDER_X_MAX`` and
# ``KNIFE_SHOULDER_DROP_MIN``).
KNIFE_BAR_CLEARANCE = 2.0 * knife_mount.BORE_R_MAX - spec.KNIFE_GAUGE_BAR_DIA_MIN
_KNIFE_BLOCK_DEPTH_MAX = knife_mount.SUPPORT_Z_THICK + knife_mount.BLOCK_SIZE_TOL
KNIFE_RIDGE_MOUTH_SPAN_MIN = _KNIFE_STATION_SPACING - _KNIFE_BLOCK_DEPTH_MAX  # 159.90
KNIFE_RIDGE_YAW_OFFSET = (
    _KNIFE_BLOCK_DEPTH_MAX * KNIFE_BAR_CLEARANCE / KNIFE_RIDGE_MOUTH_SPAN_MIN
)
KNIFE_BORE_FAR_END_OFFSET = KNIFE_BAR_CLEARANCE + KNIFE_RIDGE_YAW_OFFSET
KNIFE_FREE_ROCK_WORST_DEG = knife_mount.free_rock_deg(
    KNIFE_BORE_FAR_END_OFFSET,
    hex_w=2.0 * KNIFE_SHOULDER_X_MAX,
    r_bore=knife_mount.BORE_R_MIN,
    shoulder_drop=KNIFE_SHOULDER_DROP_MIN,
)
KNIFE_FREE_ROCK_FLOOR_DEG = spec.KNIFE_FREE_ROCK_FLOOR_DEG
# The slip fit's angular contract (owner ruling 2026-10-27, #2016 option A).
# The pressed pin and the block's hole are parallel only to within their
# perpendicularity controls: the crossbar ream ⊥Ø.001 to the faced
# underside (owner ruling 2026-11-06) and the block's round hole B ⊥Ø.001
# to A (Owner ruling 2026-11-08 (Pedro), #2144 item 11.3: the slot and its
# ⊥ are gone).  Each
# zone tilts its axis by at most atan(zone / length) over the hole's
# straight wall: its shortest printed depth less the floor's corner (the
# ream's CORNER R.003 MAX, the block's title-block R.040 MAX) and less
# KNIFE_REAM_LEAD_ALLOWANCE.  The proud pin (PROUD_MAX, which carries the
# ream floor's corner lift) bears in the hole over its full-diameter length
# short of its rounded free end, and the tightest slip takes a relative tilt
# of at most atan(SLIP_CLEARANCE_MIN / that length) before the pin binds.
#
# The lead allowance is conservatism beyond the print, not an admission of
# an undersize tail: the press ream's size band and the block hole's band
# apply over the full depth, so a conforming hole is full size to its floor
# corner (a bevel-lead reamer's undersize tail would be non-conforming), the
# pin bottoms, and PROUD_MAX holds.  The proof simply declines to count the
# last 0.5 of each wall towards the length that limits the tilt (codjiflo
# round 6).
KNIFE_REAM_LEAD_ALLOWANCE = 0.5
# ASSUMPTION, not a drawing control: the crossbar underside under the
# block's 25.4 x 14 seat and the block's face-milled top seat conform,
# clamped, to within 0.01 across the seat's shortest printed depth (14.0 -
# 0.8), tilting the block against the crossbar by atan(0.01 / 13.2).
# Neither print bounds that face's form; the charge stands for ordinary
# face-milled seats drawn flat by the bolt.
KNIFE_SEAT_CONFORMITY = 0.01
_KNIFE_SEAT_DEPTH_MIN = knife_mount.SUPPORT_Z_THICK - knife_mount.BLOCK_SIZE_TOL
KNIFE_DOWEL_TILT_ALLOWED_DEG = math.degrees(
    math.atan(
        knife_dowel.SLIP_CLEARANCE_MIN
        / (knife_dowel.PROUD_MAX - knife_dowel.FREE_END_LEN)
    )
)
_KNIFE_REAM_TILT_WALL = (
    knife_dowel.PRESS_DEPTH
    - knife_dowel.PRESS_DEPTH_TOL
    - knife_dowel.PRESS_FLOOR_CORNER_R_MAX
    - KNIFE_REAM_LEAD_ALLOWANCE
)
_KNIFE_HOLE_TILT_WALL = (
    knife_dowel.SLIP_DEPTH
    - knife_dowel.SLIP_DEPTH_TOL
    - knife_mount.DOWEL_HOLE_FLOOR_CORNER_R_MAX
    - KNIFE_REAM_LEAD_ALLOWANCE
)
KNIFE_DOWEL_TILT_REAM_DEG = math.degrees(
    math.atan(top_frame.HANGER_PRESS_HOLE_PERPENDICULARITY_TOL / _KNIFE_REAM_TILT_WALL)
)
KNIFE_DOWEL_TILT_HOLE_DEG = math.degrees(
    math.atan(knife_mount.DOWEL_HOLE_PERPENDICULARITY_TOL / _KNIFE_HOLE_TILT_WALL)
)
KNIFE_DOWEL_TILT_SEAT_DEG = math.degrees(
    math.atan(KNIFE_SEAT_CONFORMITY / _KNIFE_SEAT_DEPTH_MIN)
)
KNIFE_DOWEL_TILT_CHARGED_DEG = (
    KNIFE_DOWEL_TILT_REAM_DEG + KNIFE_DOWEL_TILT_HOLE_DEG + KNIFE_DOWEL_TILT_SEAT_DEG
)


def _assert_hanger_axis_positive_y(
    name: str, transform: list[float], sense: float = 1.0
) -> None:
    """Require the authored fastener axis to remain assembly +Y (or, with
    ``sense`` -1, -Y: the dowels hang from the crossbar)."""
    axis = transform[3:6]
    expected = (0.0, sense, 0.0)
    drift = max(
        abs(actual - target) for actual, target in zip(axis, expected, strict=True)
    )
    if drift > 1e-3:
        raise RuntimeError(
            f"{name}: local +Y fastener axis {axis} is not assembly "
            f"{'+' if sense > 0 else '-'}Y (drift {drift:.4f})"
        )


def _assert_hanger_seat_placement(
    screw: str,
    washer: str,
    station_z: float,
    screw_transform: list[float],
    washer_transform: list[float],
) -> list[float]:
    """Gate actual instance transforms against the two bearing-face seats."""
    _assert_hanger_axis_positive_y(screw, screw_transform)
    _assert_hanger_axis_positive_y(washer, washer_transform)
    screw_o = [value * 1000.0 for value in screw_transform[9:12]]
    washer_o = [value * 1000.0 for value in washer_transform[9:12]]
    if abs(screw_o[0] - KNIFE[0]) > 1e-6 or abs(screw_o[2] - station_z) > 1e-6:
        raise RuntimeError(f"{screw}: axis off the intended knife station")
    if abs(washer_o[0] - screw_o[0]) > 1e-6 or abs(washer_o[2] - screw_o[2]) > 1e-6:
        raise RuntimeError(f"{washer}: washer is not coaxial with {screw}")
    if abs(washer_o[1] - HANGER_WASHER_Y) > 1e-6:
        raise RuntimeError(
            f"{washer}: lower-face/faced-top gap "
            f"{washer_o[1] - HANGER_WASHER_Y:.6f} mm"
        )
    under_head_y = screw_o[1] + hanger_screw.UNDERHEAD_LEN
    washer_top_y = washer_o[1] + hanger_washer.THICKNESS
    if abs(under_head_y - washer_top_y) > 1e-6:
        raise RuntimeError(
            f"{screw}: under-head/washer-upper-face gap "
            f"{under_head_y - washer_top_y:.6f} mm"
        )
    reach = KNIFE_MOUNT_TOP_Y - screw_o[1]
    if abs(reach - HANGER_REACH) > 1e-6:
        raise RuntimeError(f"{screw}: knife-mount reach drifted to {reach:.6f} mm")
    return screw_o


def _assert_knife_hanger_stack() -> None:
    """Gate the purchased screw/dowel stack, print-worst, before any COM
    insertion."""
    if MOUNT_GAP != 0.0:
        raise RuntimeError(
            f"knife-mount top seat must be clamped to the casting: MOUNT_GAP {MOUNT_GAP}"
        )
    if abs(HANGER_WASHER_Y - CROSSBAR_TOP_Y) > 1e-9:
        raise RuntimeError(
            f"knife-hanger washer lower face {HANGER_WASHER_Y:.4f}, the "
            f"finished-underface HANGER_GRIP seat, is not on the faced crossbar "
            f"top {CROSSBAR_TOP_Y:.4f}"
        )
    under_head_y = HANGER_STUD_Y + hanger_screw.UNDERHEAD_LEN
    washer_top_y = HANGER_WASHER_Y + hanger_washer.THICKNESS
    if abs(under_head_y - washer_top_y) > 1e-9:
        raise RuntimeError(
            f"knife-hanger bolt under-head face {under_head_y:.4f} is not on "
            f"the washer upper face {washer_top_y:.4f}"
        )
    if not HANGER_REACH_MIN <= HANGER_REACH <= HANGER_REACH_MAX:
        raise RuntimeError(
            f"modelled knife-hanger reach {HANGER_REACH:.4f} is outside the "
            f"fit-up cut {HANGER_REACH_MIN:.2f}..{HANGER_REACH_MAX:.2f}"
        )
    if hanger_screw.CATALOG_LENGTH - HANGER_CUT_LENGTH_MAX <= hanger_screw.PITCH:
        raise RuntimeError(
            f"longest knife-hanger cut {HANGER_CUT_LENGTH_MAX:.4f} mm leaves "
            f"{hanger_screw.CATALOG_LENGTH:.2f} mm stock without removing its "
            f"factory end ({hanger_screw.PITCH:.4f} mm)"
        )
    if HANGER_ENGAGEMENT_MIN < HANGER_ENGAGEMENT_FLOOR:
        raise RuntimeError(
            f"knife-hanger screw engages {HANGER_ENGAGEMENT_MIN:.3f} mm of full "
            f"thread at its shortest reach {HANGER_REACH_MIN:.3f}, under "
            f"{hanger_screw.ENGAGEMENT_MIN_D} D ({HANGER_ENGAGEMENT_FLOOR:.3f} mm)"
        )
    if HANGER_TIP_CLEARANCE < 0.0:
        raise RuntimeError(
            f"knife-hanger screw reaches {HANGER_REACH_MAX:.3f} mm, past the "
            f"shallowest full thread {knife_mount.STUD_TAP_THREAD_DEPTH_MIN:.3f} mm"
        )
    if HANGER_THREAD_SPARE < 0.0:
        raise RuntimeError(
            f"knife-hanger bolt's useful full-form tail "
            f"{hanger_screw.THREAD_LENGTH_MIN - hanger_screw.INCOMPLETE_TIP_LEN_MAX:.6f} mm "
            f"does not span its {HANGER_REACH_MAX:.6f} mm reach"
        )
    if HANGER_SCREW_CLEARANCE <= 0.0:
        raise RuntimeError(
            "knife-hanger screw does not clear the crossbar hole: "
            f"{HANGER_SCREW_CLEARANCE:.4f} mm diametral clearance"
        )
    if HANGER_SCREW_FLOAT_SPARE <= 0.0:
        raise RuntimeError(
            f"knife-hanger screw float {top_frame.HANGER_SCREW_FLOAT:.4f} does not "
            f"cover the dowel and tap mismatch {HANGER_SCREW_MISMATCH:.4f} plus the "
            f"clearance hole's drill drift {HANGER_SCREW_DRIFT:.4f}"
        )
    if KNIFE_REAR_YAW_RANGE_DEG < KNIFE_BAR_YAW_DEG:
        raise RuntimeError(
            f"rear knife mount turns at most {KNIFE_REAR_YAW_RANGE_DEG:.3f} deg about "
            f"its dowel inside the bolt float, under the {KNIFE_BAR_YAW_DEG:.3f} deg "
            "the gauge bar's line can ask of it"
        )
    if spec.KNIFE_GAUGE_BAR_DIA > 2.0 * knife_mount.BORE_R_MIN + 1e-9:
        raise RuntimeError(
            f"the Ø{spec.KNIFE_GAUGE_BAR_DIA:.4f} gauge bar does not enter the smallest "
            f"knife bore Ø{2.0 * knife_mount.BORE_R_MIN:.4f}"
        )
    if KNIFE_FREE_ROCK_WORST_DEG < KNIFE_FREE_ROCK_FLOOR_DEG:
        raise RuntimeError(
            f"knife edge rocks {KNIFE_FREE_ROCK_WORST_DEG:.3f} deg at the worst "
            f"case (gauge-bar far-end offset {KNIFE_BORE_FAR_END_OFFSET:.4f}), under "
            f"{KNIFE_FREE_ROCK_FLOOR_DEG}"
        )
    if KNIFE_DOWEL_TILT_CHARGED_DEG >= KNIFE_DOWEL_TILT_ALLOWED_DEG:
        raise RuntimeError(
            f"knife-mount dowel tilt {KNIFE_DOWEL_TILT_CHARGED_DEG:.4f} deg binds "
            f"the tightest slip, which takes {KNIFE_DOWEL_TILT_ALLOWED_DEG:.4f} deg: "
            f"crossbar ream ⊥Ø{top_frame.HANGER_PRESS_HOLE_PERPENDICULARITY_TOL} "
            f"over its {_KNIFE_REAM_TILT_WALL:.1f} wall "
            f"{KNIFE_DOWEL_TILT_REAM_DEG:.4f} deg + block hole "
            f"⊥Ø{knife_mount.DOWEL_HOLE_PERPENDICULARITY_TOL} over its "
            f"{_KNIFE_HOLE_TILT_WALL:.1f} wall {KNIFE_DOWEL_TILT_HOLE_DEG:.4f} deg "
            f"+ seat conformity {KNIFE_SEAT_CONFORMITY} over "
            f"{_KNIFE_SEAT_DEPTH_MIN:.1f} {KNIFE_DOWEL_TILT_SEAT_DEG:.4f} deg "
            f"(owner ruling 2026-10-27, #2016)"
        )
    # Both parts' dowel stations are the dowel spec's one station (Owner
    # ruling 2026-11-08 (Pedro), #2144 item 11.3), and the knife mount's
    # round hole, 9.5 deep from its top seat, is deep enough for the proud
    # pin hanging from the crossbar's 12.0 ream (the spec asserts the
    # print-worst case).
    expected_stations = (knife_dowel.HANGER_OFFSET,)
    for owner, stations in (
        ("knife mount", KNIFE_DOWEL_X_OFFSETS),
        ("crossbar", top_frame.HANGER_PIN_XS),
    ):
        if len(stations) != knife_dowel.PER_MOUNT or any(
            abs(station - expected) > 1e-9
            for station, expected in zip(stations, expected_stations, strict=True)
        ):
            raise RuntimeError(
                f"{owner} dowel stations {stations} are not the dowel spec's "
                f"{expected_stations}"
            )
    slip_floor_y = KNIFE_MOUNT_TOP_Y - knife_mount.PIN_HOLE_DEPTH
    if (
        KNIFE_DOWEL_END_Y <= slip_floor_y
        or knife_dowel.SLIP_DEPTH_CLEARANCE_MIN <= 0.0
    ):
        raise RuntimeError(
            f"knife-mount dowel end {KNIFE_DOWEL_END_Y:.4f} bottoms the knife "
            f"mount's slip hole (floor {slip_floor_y:.4f}; worst clearance "
            f"{knife_dowel.SLIP_DEPTH_CLEARANCE_MIN:.3f} mm)"
        )
    log(
        f"knife-hanger stack: seat {KNIFE_MOUNT_TOP_Y:.4f} (gap {MOUNT_GAP}), "
        f"washer {HANGER_WASHER_Y:.4f}, bolt under-head {HANGER_UNDERHEAD_Y:.4f}, "
        f"tip {HANGER_STUD_Y:.4f}; reach "
        f"{HANGER_REACH:.3f} ({HANGER_REACH_MIN:.3f}..{HANGER_REACH_MAX:.3f}); "
        f"full thread {HANGER_ENGAGEMENT_MIN:.3f} >= {HANGER_ENGAGEMENT_FLOOR:.3f}; "
        f"tip {HANGER_TIP_CLEARANCE:.3f} under the thread; crossbar clearance "
        f"{HANGER_SCREW_CLEARANCE:.4f}, mismatch {HANGER_SCREW_MISMATCH:.4f} + "
        f"drift {HANGER_SCREW_DRIFT:.4f} <= {top_frame.HANGER_SCREW_FLOAT:.4f} "
        f"(spare {HANGER_SCREW_FLOAT_SPARE:.4f}); dowel {KNIFE_DOWEL_END_Y:.4f}.."
        f"{KNIFE_DOWEL_Y:.4f} over the slip floor {slip_floor_y:.4f} mm; rock "
        f"{KNIFE_FREE_ROCK_WORST_DEG:.3f} deg (bar t {KNIFE_BORE_FAR_END_OFFSET:.4f}); "
        f"bar yaw {KNIFE_BAR_YAW_DEG:.3f} <= rear range {KNIFE_REAR_YAW_RANGE_DEG:.3f} deg"
    )


# --- purchased counter spring and directly threaded lower anchor -----------
import sm_vn_counter_spring_stock_geom as counter_stock  # noqa: E402
import sm_gooseneck_geom  # noqa: E402
from _counter_spring_hang import assert_counter_spring_top_hang  # noqa: E402
import spring_mount_geom as spring_mounts  # noqa: E402
import sm_summing_lever_spec  # noqa: E402
from stock_anchor_geom import ANCHOR_9490T1  # noqa: E402
import sm_vn_boss_hook_jam_nut_spec as jam_nut  # noqa: E402

BOSS_HOOK_POS = (*spring_mounts.COUNTER_ANCHOR_XY, SUMMING_Z)
# MHA-SM-VN-55 on the anchor axis, its z = 0 face on the boss top face:
# ROT_X_NEG90 turns the nut's local +Z thread axis to machine +Y.
JAM_NUT_POS = (
    spring_mounts.COUNTER_ANCHOR_XY[0],
    spring_mounts.COUNTER_BOSS_TOP_Y,
    SUMMING_Z,
)
JAM_NUT_ROWS = ROT_X_NEG90
# The counter spring and gooseneck use complete calibrated placements loaded by
# ``counter_seat`` before assembly creation.

UPPER_EYE_NOTES = (
    "MHA-SM-VN-56: SEAT SHOULDER ON END PIECE FACE.\n"
    "UPPER EYE RIDES FREE ON SHOULDER UNDER THE HEAD.\n"
    "NO THREADLOCKER."
)


def _assert_gooseneck_sleeve_covers_hub_bore(
    gooseneck_origin_y: float, label: str
) -> None:
    """Require the brazed sleeve over the top-frame rail's whole bore span.

    The Ø12.70 tube alone would rattle in the unchanged Ø17 rail-hub bore;
    the 5/8 in sleeve (sm_gooseneck_geom.SLEEVE_*) is the post the hub's set
    screw grips, so at this setting it must run from below the rail underside
    (CASTING_UNDERSIDE_Y) to above its faced top (CROSSBAR_TOP_Y).
    """
    sleeve_bottom = gooseneck_origin_y + sm_gooseneck_geom.LEG_BOTTOM
    sleeve_top = gooseneck_origin_y + sm_gooseneck_geom.SLEEVE_TOP
    if not (sleeve_bottom <= CASTING_UNDERSIDE_Y and CROSSBAR_TOP_Y <= sleeve_top):
        raise RuntimeError(
            f"gooseneck sleeve y {sleeve_bottom:.3f}..{sleeve_top:.3f} at the "
            f"{label} setting does not cover the top-frame hub bore's rail span "
            f"{CASTING_UNDERSIDE_Y:.3f}..{CROSSBAR_TOP_Y:.3f}"
        )
    log(
        f"gooseneck sleeve ({label}): y {sleeve_bottom:.3f}..{sleeve_top:.3f} "
        f"covers the hub bore rail span {CASTING_UNDERSIDE_Y:.3f}.."
        f"{CROSSBAR_TOP_Y:.3f} "
        f"({CASTING_UNDERSIDE_Y - sleeve_bottom:.3f} "
        f"below, {sleeve_top - CROSSBAR_TOP_Y:.3f} above)"
    )


# --- assembly settings as model dimensions (MHA-SM-00 sheet 1) --------------
# Blanked Front-plane construction sketches (sketch x = machine X, y = machine
# Y), every vertex driven from a global; the drawing shows each sketch in the
# one view that dimensions it and imports only its marked dimension.
_SETTING_GLOBALS = {
    "SmKnifeY": spec.KNIFE_POINT[1],
    "SmCounterScrewX": spec.COUNTER_SCREW_POINT[0],
    "SmCounterScrewY": spec.COUNTER_SCREW_POINT[1],
    "SmBossX": spec.BOSS_FACE_POINT[0],
    "SmBossFaceY": spec.BOSS_FACE_POINT[1],
    "SmBossRockTravel": spec.BOSS_ROCK_TRAVEL,
}
if not (
    spec.KNIFE_POINT[0] < 0.0 < spec.KNIFE_POINT[1]
    and spec.BOSS_FACE_POINT[0] < 0.0 < spec.BOSS_FACE_POINT[1]
    and spec.COUNTER_SCREW_POINT[0] < spec.KNIFE_POINT[0]
):
    raise AssertionError("summing setting drives assume x < 0 < y, screw left of knife")


async def _construction_line(
    adapter, start: tuple[float, float], end: tuple[float, float], label: str
) -> str:
    set_sketch_direct_db(adapter, True)
    line = check(label, await adapter.add_line(start[0], start[1], end[0], end[1]))
    set_sketch_direct_db(adapter, False)
    segment = _early_bound(adapter._sketch_entities[line], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{label} is not construction")
    return line


async def _finish_setting(
    adapter, feature: str, dims: SketchDims, marked: str
) -> None:
    await ensure_fully_defined(adapter, feature)
    check(f"exit {feature} sketch", await adapter.exit_sketch())
    name_last_feature(adapter, feature)
    for name, expression in dims.apply(adapter, feature):
        await drive_dimension(adapter, name, expression)
    mark_dimensions_for_drawing(adapter, feature, {marked})


async def _author_settings(adapter) -> None:
    """CounterSetting: the MHA-SM-VN-56 axis above the knife contact level (the
    gooseneck height the level setting finds). KnifeRockGauge: the boss face's
    minimum travel at the free-rock floor, up the boss-hook axis."""
    for name, value in _SETTING_GLOBALS.items():
        await set_global(adapter, name, f"{value}mm")

    # The setting line runs up the counter spring's axis, from the knife
    # contact level to the screw axis, so the only printed construction lies
    # along the spring it sets (a slant from the knife would cross the spring).
    knife, screw = spec.KNIFE_POINT, spec.COUNTER_SCREW_POINT
    base = (screw[0], knife[1])
    dims = SketchDims()
    check("create counter setting sketch", await adapter.create_sketch("Front"))
    line = await _construction_line(adapter, base, screw, "counter setting line")
    check(
        "counter setting vertical",
        await adapter.add_sketch_constraint(line, None, "vertical"),
    )
    await anchor_point_to_origin(
        adapter, f"{line}.start", *base, "spring axis at knife level"
    )
    dims.record("CounterScrewX", '-"SmCounterScrewX"')
    dims.record("KnifeY", '"SmKnifeY"')
    await dimension_between(
        adapter, f"{line}.start", f"{line}.end", "vertical_distance",
        spec.COUNTER_SCREW_RISE, "counter screw rise",
    )
    dims.record(spec.COUNTER_DIMENSION, '"SmCounterScrewY" - "SmKnifeY"')
    await _finish_setting(adapter, spec.COUNTER_FEATURE, dims, spec.COUNTER_DIMENSION)

    face = spec.BOSS_FACE_POINT
    top = (face[0], face[1] + spec.BOSS_ROCK_TRAVEL)
    dims = SketchDims()
    check("create knife rock gauge sketch", await adapter.create_sketch("Front"))
    line = await _construction_line(adapter, face, top, "boss rock gauge line")
    check("rock gauge vertical", await adapter.add_sketch_constraint(line, None, "vertical"))
    await anchor_point_to_origin(adapter, f"{line}.start", *face, "boss face")
    dims.record("BossX", '-"SmBossX"')
    dims.record("BossFaceY", '"SmBossFaceY"')
    await dimension_between(
        adapter, f"{line}.start", f"{line}.end", "vertical_distance",
        spec.BOSS_ROCK_TRAVEL, "boss rock travel",
    )
    dims.record(spec.ROCK_DIMENSION, '"SmBossRockTravel"')
    await _finish_setting(adapter, spec.ROCK_FEATURE, dims, spec.ROCK_DIMENSION)

    apply_drawing_precision(adapter, spec.DRAWING_PRECISION)
    for feature in spec.SETTING_FEATURES:
        blank_sketch(adapter, feature)


def _assert_counter_spring_hang(pose: spring_mounts.SpringPose) -> None:
    """Require full direct thread engagement, full thread under the jam nut
    and a tensioned supplier spring."""
    anchor = ANCHOR_9490T1
    tap = sm_summing_lever_spec.COUNTER_HOLE_SPEC
    if tap.kind != "tapped" or tap.size != anchor.thread_size:
        raise RuntimeError("counter anchor requires its matching native through tap")
    if jam_nut.THREAD != anchor.thread_size:
        raise RuntimeError("counter jam nut thread does not match the anchor")
    thread_top = BOSS_HOOK_POS[1] + anchor.thread_start_y_mm
    boss_top = spring_mounts.COUNTER_BOSS_TOP_Y
    exposed = spring_mounts.COUNTER_SHANK_LENGTH_MM - sm_summing_lever_spec.ANCHOR_H
    if abs(thread_top - boss_top - exposed) > 1e-6:
        raise RuntimeError("counter anchor cut end is not flush with the boss underside")
    if exposed < jam_nut.THICKNESS + anchor.thread_pitch_mm - 1e-3:
        raise RuntimeError(
            f"counter anchor stands {exposed:.3f} mm of thread above the boss, "
            f"under the jam nut's {jam_nut.THICKNESS:.3f} plus one pitch"
        )
    if 2.0 * sm_summing_lever_spec.ANCHOR_R < jam_nut.ACROSS_CORNERS:
        raise RuntimeError("counter jam nut corners overhang the boss top face")
    counter_stock.validate_length_mm(pose.length_mm)
    log(
        f"counter lower anchor: {tap.size} direct through tap, "
        f"{sm_summing_lever_spec.ANCHOR_H:.3f} mm engagement, "
        f"{exposed:.3f} mm thread above the boss under the "
        f"{jam_nut.THICKNESS:.3f} jam nut; "
        f"spring inside length {pose.length_mm:.4f} mm, "
        f"calibrated force {spring_mounts.counter_force_n(pose.length_mm):.3f} N"
    )


async def build(adapter) -> dict[str, str]:
    # Flip seeds + free-DOF contract: cad/config/assemblies/<ASM_NAME>.yaml.
    activate_assembly_contract(ASM_NAME)
    counter_seat, gooseneck_origin_y = settled_spring_seats.counter_seat()
    counter_pose = counter_seat.pose
    _assert_counter_spring_hang(counter_pose)
    assert_counter_spring_top_hang(counter_pose, gooseneck_origin_y)
    _assert_gooseneck_sleeve_covers_hub_bore(
        spring_mounts.GOOSENECK_ORIGIN_Y, "reference"
    )
    _assert_gooseneck_sleeve_covers_hub_bore(gooseneck_origin_y, "settled")
    _assert_knife_hanger_stack()

    # Reset the free-DOF manifest buffer before any *_driver(free_dof_key=...)
    # call: each freed DOF is recorded (never authored) and persisted below.
    reset_dof_manifest()
    check("create_assembly", await adapter.create_assembly())
    apply_package_model_units(adapter, assembly_contract(ASM_NAME).drawing_unit, label=ASM_NAME)

    # Two knife bearing supports, one per hex trunnion (overhanging the lever
    # body at SUMMING_Z +/- HEX_Z_MID). The front support is FIRST so the auto-fixed assembly
    # seed is structure, not the mated summing lever. Each support's circular
    # bore is much larger than the hex, so only the trunnion's top vertex line
    # (the knife edge) nears the upper inner wall. The named "knife axis" is that
    # contact ridge line; the lever's Axis3 (hex ridge) mates coincident to it.
    km = await place_component(
        adapter,
        "sm-knife-mount",
        [KNIFE[0], KNIFE_CONTACT_Y, SUMMING_Z + HEX_Z_MID],
        [0.0, 0.0, 0.0],
        IDENTITY,
        label="knife-mount (front)",
    )
    await place_component(
        adapter,
        "sm-knife-mount",
        [KNIFE[0], KNIFE_CONTACT_Y, SUMMING_Z - HEX_Z_MID],
        [0.0, 0.0, 0.0],
        IDENTITY,
        label="knife-mount (back)",
    )
    # One cut #10-24 hex bolt and one SAE washer per mount: washer lower
    # face on the crossbar's faced top, bolt under-head on the washer upper face.
    # The dowel, its pressed end on the crossbar's ream floor, stands proud
    # down into the block's round hole (+X, datum B; Owner ruling 2026-11-08
    # (Pedro), #2144 item 11.3). Every hardware instance is independently
    # fixed; no operational DOF is added.
    hanger_screws: list[str] = []
    hanger_washers: list[str] = []
    knife_dowels: list[str] = []
    for side, station_z in (
        ("front", SUMMING_Z + HEX_Z_MID),
        ("back", SUMMING_Z - HEX_Z_MID),
    ):
        hanger_washers.append(
            await place_component(
                adapter,
                "sm-vn-knife-hanger-washer",
                [KNIFE[0], HANGER_WASHER_Y, station_z],
                [0.0, 0.0, 0.0],
                IDENTITY,
                ground=True,
                label=f"knife-hanger-washer ({side})",
            )
        )
        hanger_screws.append(
            await place_component(
                adapter,
                "sm-vn-knife-hanger-stud",
                [KNIFE[0], HANGER_STUD_Y, station_z],
                [0.0, 0.0, 0.0],
                IDENTITY,
                ground=True,
                label=f"knife-hanger-stud ({side})",
            )
        )
        for x_offset in KNIFE_DOWEL_X_OFFSETS:
            knife_dowels.append(
                await place_component(
                    adapter,
                    "sm-vn-knife-mount-dowel",
                    [KNIFE[0] + x_offset, KNIFE_DOWEL_Y, station_z],
                    [180.0, 0.0, 0.0],
                    KNIFE_DOWEL_ROWS,
                    ground=True,
                    label=f"knife-mount-dowel ({side}, x {x_offset:+.3f})",
                )
            )

    # Count the live top-level instances, not just the placement requests:
    # Exactly two cut bolts, two new washers and two dowels must survive.
    live_names = component_names(adapter)
    for stem, inserted, count in (
        ("sm-vn-knife-hanger-stud", hanger_screws, 2),
        ("sm-vn-knife-hanger-washer", hanger_washers, 2),
        ("sm-vn-knife-mount-dowel", knife_dowels, knife_dowel.QUANTITY),
    ):
        live = [
            name for name in live_names if name == stem or name.startswith(f"{stem}-")
        ]
        if len(live) != count or set(live) != set(inserted):
            raise RuntimeError(
                f"{stem}: expected exactly {count} inserted instances, got "
                f"{sorted(live)}"
            )

    # Read back both physical stacks: each washer's lower bearing face on
    # the faced top, each bolt's head on its own washer, coaxial at the
    # intended knife station. Check each dowel's offset and ream-floor seat.
    per_mount = knife_dowel.PER_MOUNT
    station_dowels = [
        knife_dowels[index : index + per_mount]
        for index in range(0, len(knife_dowels), per_mount)
    ]
    for screw, washer, dowels, station_z in zip(
        hanger_screws,
        hanger_washers,
        station_dowels,
        (SUMMING_Z + HEX_Z_MID, SUMMING_Z - HEX_Z_MID),
        strict=True,
    ):
        screw_o = _assert_hanger_seat_placement(
            screw,
            washer,
            station_z,
            component_transform(adapter, screw),
            component_transform(adapter, washer),
        )
        for dowel, x_offset in zip(dowels, KNIFE_DOWEL_X_OFFSETS, strict=True):
            dowel_transform = component_transform(adapter, dowel)
            _assert_hanger_axis_positive_y(dowel, dowel_transform, sense=-1.0)
            dowel_o = [value * 1000.0 for value in dowel_transform[9:12]]
            dowel_offset = (dowel_o[0] - screw_o[0], dowel_o[2] - screw_o[2])
            if abs(dowel_offset[0] - x_offset) > 1e-6 or abs(dowel_offset[1]) > 1e-6:
                raise RuntimeError(
                    f"{dowel}: offset (x, z) {dowel_offset[0]:.6f}, "
                    f"{dowel_offset[1]:.6f} mm from {screw}, not "
                    f"({x_offset:.3f}, 0)"
                )
            if abs(dowel_o[1] - KNIFE_DOWEL_Y) > 1e-6:
                raise RuntimeError(
                    f"{dowel}: {dowel_o[1] - KNIFE_DOWEL_Y:.6f} mm off its seat on "
                    "the crossbar ream floor"
                )
    # Summing lever: knife-edge revolute = coincident axis-to-axis on the knife
    # line (the bore-bottom rocking edge) + a Front-plane axial distance,
    # leaving the rock DOF -- the sub's freed operational DOF (its drive spec
    # recorded into the DOF manifest, never authored). This is the part the
    # counter spring + channel springs drive in the M6 Motion study.
    sl = await place_component(
        adapter,
        "sm-summing-lever",
        [KNIFE[0], KNIFE[1], SUMMING_Z],
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
    )
    sl_o = component_origin(adapter, sl)
    # summing-lever axes (creation order): Axis1 = pivot (cylinder centre),
    # Axis2 = anchor, Axis3 = knife ridge (hex top vertex). The lever rocks on
    # the true knife edge: Axis3 mates coincident to the support's contact ridge
    # ("knife axis" = Axis1@knife-mount). Same pose as the cylinder-centre mate
    # (ridge is 5.13 above the centre, both collinear along Z), but the freed
    # rock DOF is now about the knife edge, per the bearing-support design.
    await coincident_mate(
        adapter,
        named_ref(f"Axis3@{sl}", "AXIS"),
        named_ref(f"Axis1@{km}", "AXIS"),
        label="summing-lever knife pivot",
        verify=(sl, sl_o),
    )
    # Axial Z-slide pinned by a Front-plane distance (value 0: the lever sits on
    # the assembly Front plane). Then the rock (Rz about the knife line) is the
    # suppressible snapshot driver -- an ANGLE between Right planes, NOT the
    # off-axis spin_driver: the boss "spin ref" sits directly -X of the pivot
    # (Δy=0), so its distance-to-Top is degenerate and over-defines, whereas the
    # angle is well-conditioned and (inserted on-solution) holds without a flip.
    await distance_driver(
        adapter,
        named_ref(f"Front Plane@{sl}", "PLANE"),
        named_ref("Front Plane", "PLANE"),
        abs(sl_o[2]),
        label="summing-lever axial",
        verify=(sl, sl_o),
    )
    # The rock about the knife line is the sub's FREED operational DOF: its
    # drive spec (an ANGLE between Right planes -- the boss "spin ref"
    # distance-to-Top is degenerate here, see above) is recorded into the DOF
    # manifest, never authored -- drag the lever and it rocks on the knife
    # edge, per the magnifier lever_rock idiom.
    await angle_driver(
        adapter,
        named_ref(f"Right Plane@{sl}", "PLANE"),
        named_ref("Right Plane", "PLANE"),
        0.0,
        label="summing-lever rock PARK driver (freed in default build)",
        verify=(sl, sl_o),
        free_dof_key="lever_rock",
    )
    # The purchased, trimmed open eye threads directly into the lever's boss.
    # Locking records that rigid threaded connection while preserving lever rock.
    bh = await place_component(
        adapter,
        "sm-vn-boss-hook",
        list(BOSS_HOOK_POS),
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
    )
    await lock_mate(
        adapter,
        named_ref(f"ScrewAxis@{bh}", "AXIS"),
        named_ref(f"Axis2@{sl}", "AXIS"),
        label="boss-hook keyed",
    )
    # The jam nut on the anchor's exposed thread, jammed on the boss top face
    # with the eye clocked: placed at its exact pose and locked to the lever
    # it rides -- one Lock mate, as the hook; a coaxial mate on top would only
    # over-constrain the solve.
    nut = await place_component(
        adapter,
        "sm-vn-boss-hook-jam-nut",
        list(JAM_NUT_POS),
        euler_from_rows(JAM_NUT_ROWS),
        JAM_NUT_ROWS,
        ground=False,
    )
    await lock_mate(
        adapter,
        named_ref(f"Front Plane@{nut}", "PLANE"),
        named_ref(f"Front Plane@{sl}", "PLANE"),
        label="boss-hook jam nut locked to lever",
    )
    assert_component_placed(adapter, nut, list(JAM_NUT_POS), JAM_NUT_ROWS)
    # Preserve the vendor +X coil frame and required half-turn clocking at the
    # complete fixed measured pose; no seed placement or corrective move follows.
    await place_component(
        adapter,
        "sm-vn-counter-spring",
        [*counter_pose.centre_xy, SUMMING_Z],
        euler_from_rows(counter_pose.rotation_rows),
        counter_pose.rotation_rows,
    )
    # Ry(180): the gooseneck's overhang arm reaches from the east column toward
    # the machine centre. Its measured origin Y is inserted directly; its
    # sleeve is held in the top-frame rail-hub bore by its 1/4-20 set screw.
    gooseneck = await place_component(
        adapter,
        "sm-gooseneck",
        [COLUMN_X, gooseneck_origin_y, SUMMING_Z],
        [0.0, 180.0, 0.0],
        ROT_Y_180,
    )
    # The shoulder screw's origin is its shoulder end face, local +Z to the
    # head; ROT_Y_POS90 maps +Z to machine +X, so the shoulder seats on the
    # end face and the thread runs into the blind tap.  The mate records the
    # seated pose, not a mechanical screw lock; the eye rides free on the
    # shoulder (#2144 item 11.4) and adds no operational DOF.
    screw_rows = ROT_Y_POS90
    screw_y = gooseneck_origin_y + sm_gooseneck_geom.ARM_Y
    screw_position = [spring_mounts.GOOSENECK_END_X, screw_y, SUMMING_Z]
    # Literal stems, one call each: _buildgraph's source-expression contract
    # and the hanger-stack recipe count read them.
    screw_component = await place_component(
        adapter,
        "sm-vn-gooseneck-shoulder-screw",
        screw_position,
        euler_from_rows(screw_rows),
        screw_rows,
        ground=False,
    )
    await lock_mate(
        adapter,
        named_ref(f"Front Plane@{screw_component}", "PLANE"),
        named_ref(f"Front Plane@{gooseneck}", "PLANE"),
        label="shoulder screw seated on end piece",
    )
    assert_component_placed(adapter, screw_component, screw_position, screw_rows)

    # Certify the AS-BUILT model.  The lever rock remains the sole intended
    # freed DOF; the exact allowed-stem set rejects any free screw, dowel, or
    # other structural component.  The lock-mated boss-hook and its jam nut
    # MUST read under-constrained WITH the lever -- a grounded/fixed regression
    # would freeze the counter-spring anchor while the lever still swings.
    lever_riders = ("sm-summing-lever", "sm-vn-boss-hook", "sm-vn-boss-hook-jam-nut")
    assert_free_dof_necessity(
        adapter,
        1,
        required_stems=lever_riders,
        allowed_stems=lever_riders,
    )
    write_dof_manifest(ASM_NAME)
    check_no_interference(
        adapter,
        allowed_pairs=ALLOWED_PAIRS,
    )
    await _author_settings(adapter)
    # Title-block identity for the assembly drawing (draw_sm_summing_assembly.py):
    # assembly_title_properties supplies the Title/Generator and TOL_* cells
    # finalize_drawing requires without consulting the part registry.
    # Component drawings own their material and finish specifications.
    apply_custom_properties(
        adapter,
        {
            **assembly_title_properties(ASM_NAME),
            "Revision Description": "Initial release",
            "Material": "SEE COMPONENT DRAWINGS",
            "Material Specification": "SEE COMPONENT DRAWINGS",
            "Finish": "SEE COMPONENT DRAWINGS",
            "Quantity": "1",
            "Manufacturing Notes": UPPER_EYE_NOTES,
            "Drawn By": DRAWN_BY,
        },
    )
    # The package drawing's exploded views reference Default (shaded) or
    # Default Simplified, so the explode is authored in both.
    author_in_drawing_configurations(
        adapter, ASM_NAME, lambda configuration: create_summing_explode(adapter, configuration)
    )
    return await save_assembly_and_images(
        adapter,
        ASM_NAME,
        native_contact_check=assert_assembly_spring_contacts,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
