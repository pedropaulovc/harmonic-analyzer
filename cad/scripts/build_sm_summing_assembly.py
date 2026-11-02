r"""Reproduction script: summing subassembly (book ch. 18-19).

The head of the analyzer's output, where the 20 channel springs converge on
the summing lever, in machine coordinates (assembly origin = base origin;
base top y = 50.8; the output side is -Z). The lever rocks on a true knife
edge carried by two bearing supports, each clamped to the underside of the
top-frame casting's integral crossbar by one knife-hanger screw and keyed
against turning by two pressed dowels, and counter-balanced from above by the
boss-hook / counter-spring / gooseneck chain.

* knife-mount x2 -- the bearing supports, one per hex trunnion, centred on
  ``SUMMING_Z`` and separated by ``+/-HEX_Z_MID``; each top seat is clamped
  to the crossbar underside (``MOUNT_GAP`` 0).
* knife-hanger-stud x2 -- McMaster 92314A253 #10-24 plain hex bolts from
  2 in stock, each cut at this assembly to the stack measured at its hole
  plus the .351 +/-.006 in fit-up reach (46.70 mm nominal under the head);
  each passes the crossbar's #10 loose clearance hole and threads into the
  knife-mount tap.
* knife-hanger-washer x2 -- new McMaster 96659A104 18-8 SAE washers,
  one beneath each hex head, seated on the crossbar's faced top.
* knife-mount-dowel x4 -- McMaster 98381A473 1/8 x 3/4 dowels, two per
  knife mount either side of its screw, each pressed up to the floor of a
  blind ream in the crossbar's faced underside (knocked out from its faced
  top; owner ruling 2026-10-24, T+H3); the knife mount slips onto them, one
  in its blind round hole, the other in its slot along the dowel line, open
  to its -X face: the pair keys the block against turning about the screw
  without overconstraining it.
* summing-lever -- rocks on the knife edge (Axis3 coincident to the support
  contact ridge); the part the channel + counter springs drive in the M6
  Motion study. The rock is the sub's single FREED operational DOF: its
  drive spec is recorded into the DOF manifest, never authored, so the
  saved model rocks on the knife edge.
* boss-hook (keyed to the lever's anchor eye) + its MHA-SM-VN-55 jam nut on the
  boss top face + counter-spring + gooseneck -- the counter-balance hung from
  the east column; the gooseneck's brazed O15.875 sleeve is the post the
  top-frame rail hub's set screw grips (no separate clamp part).
* sm-gooseneck-spring-screw -- made MHA-SM-04 slotted cheese-head screw, head
  outboard: the supplier upper loop sits on its plain O6.35 body and the head
  clamps it to the face of the gooseneck's flush end piece, while the 1/4-28
  thread runs into the end piece's blind tap (owner ruling 2026-10-27
  (#1951)); locked to the fixed gooseneck with no additional operational DOF.

Cross-subassembly fits (checked at the top level): the channel springs
(ch-channel.SLDASM) thread the summing-lever plate's O4.5 holes -- gated
analytically by build_ch_channel_assembly._assert_plate_threading; the knife-
hanger bolts pass the top-frame crossbar's O6.045 clearance holes and clamp
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
from _interference_contracts import allowed_interference_pairs
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

# --- knife-hanger hardware (two #10-24 hex bolts, washers and dowel pairs) ----
# The top-frame, knife-mount and purchased hardware specs own every term.
# The bolt frame has its cut tip at local Y=0, axis +Y. Its under-head face
# bears on the washer's upper face; the washer's local Y=0 lower bearing face
# seats on the crossbar's faced top, HANGER_GRIP above the finished underside.
# The knife mount remains clamped face-to-face to that underside, gap 0,
# with no bedding allowance. Each dowel (local Y=0 its lower end, axis +Y)
# is pressed up to the floor of its crossbar ream (owner ruling 2026-10-24,
# T+H3) and hangs into the knife mount's slip hole or slot.
KNIFE_MOUNT_TOP_Y = CASTING_UNDERSIDE_Y - MOUNT_GAP  # 999.7: clamped, gap 0
CROSSBAR_TOP_Y = CASTING_UNDERSIDE_Y + top_frame.RING_HEIGHT  # 1036.2, faced
HANGER_WASHER_Y = CASTING_UNDERSIDE_Y + top_frame.HANGER_GRIP  # 1036.2, local Y=0
HANGER_UNDERHEAD_Y = HANGER_WASHER_Y + hanger_washer.THICKNESS  # 1037.4827
HANGER_STUD_Y = HANGER_UNDERHEAD_Y - hanger_screw.LENGTH  # 990.7827 (cut tip)
HANGER_REACH = KNIFE_MOUNT_TOP_Y - HANGER_STUD_Y  # 8.9173, the modelled nominal
# Worst-case stack (drawing-guidelines.md rules 18–19): MHA-SM-00 step 4
# cuts each bolt to the crossbar-underside-to-washer-top height measured at
# its own hole plus the fit-up reach, so the printed grip band and the
# washer's catalogue thickness spread are measured out and only the cut's
# own band reaches the tap: .345-.357 in, 8.763..9.0678.
HANGER_REACH_MIN = spec.HANGER_FIT_REACH - spec.HANGER_FIT_REACH_TOL
HANGER_REACH_MAX = spec.HANGER_FIT_REACH + spec.HANGER_FIT_REACH_TOL
# The cut must come out of the 2 in stock and remove its factory end: the
# longest cut is the thickest printed grip plus the thickest washer plus
# the longest reach, 37.01 + 1.651 + 9.0678 = 47.7288; the shortest is
# 35.99 + 0.9144 + 8.763 = 45.6674.
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
# 7.7046667 >= 1.5D = 7.239.
HANGER_ENGAGEMENT_MIN = HANGER_REACH_MIN - hanger_screw.INCOMPLETE_TIP_LEN_MAX
HANGER_ENGAGEMENT_FLOOR = hanger_screw.ENGAGEMENT_MIN_D * hanger_screw.SHANK_DIA
# Longest reach under the shallowest full tap: 9.52 - 9.0678 = 0.4522 air.
HANGER_TIP_CLEARANCE = knife_mount.STUD_TAP_THREAD_DEPTH_MIN - HANGER_REACH_MAX
# Modified-part inspection acceptance, not a vendor thread-to-head claim:
# the useful full-form tail (.418 MIN, 10.6172, less one incomplete pitch)
# spans 9.0678.
HANGER_THREAD_SPARE = (
    hanger_screw.THREAD_LENGTH_MIN - hanger_screw.INCOMPLETE_TIP_LEN_MAX
) - HANGER_REACH_MAX
HANGER_SCREW_CLEARANCE = top_frame.HANGER_CLEARANCE_DIA_MIN - hanger_screw.SHANK_DIA
# Each dowel's pressed (chamfered) end, its local Y=0, on its crossbar ream
# floor, 1011.7, its local +Y turned down (Rx 180): its far end 992.65,
# standing PROUD 7.05 below the underside into the knife mount's round hole
# or slot (floor 990.2).
KNIFE_DOWEL_Y = CASTING_UNDERSIDE_Y + top_frame.HANGER_PIN_HOLE_DEPTH
KNIFE_DOWEL_END_Y = KNIFE_DOWEL_Y - knife_dowel.LENGTH
KNIFE_DOWEL_ROWS = [[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]]
# Pair stations from the bolt axis, -X (slot) first: 7.632 along X.
KNIFE_DOWEL_X_OFFSETS = (knife_mount.SLOT_X, knife_mount.PIN_HOLE_X)
# The bolt must pass the crossbar's #10 clearance hole at the printed-band
# worst case (drawing-guidelines.md rule 19 (absorb stacks)) when
# every station sits at its limit (owner ruling 2026-10-24, T+H3: the pins
# press into the crossbar and slip into the block), with the block fitted
# either way round: each +X ream stands .XXX from its screw axis and each -X
# ream BASIC 15.264 from it within a Ø0.05 zone, so B's round hole may sit on
# either pin.  Along the dowel line (X): B's pin's ream station (.XXX, 0.13,
# plus the -X ream's zone radius 0.025 when B sits on the -X pin), the tap's
# position zone radius to the knife mount's A|B|C (0.07), B's round hole
# across its loosest slip on its pin (0.046) and B's datum simulator off the
# pin root (t/2 = 0.0075, below).  Across it (Z): the crossbar's
# implied-zero offset of the +X ream from the screw hole (.XXX, 0.13), the -X
# ream off the +X ream's line by its zone radius (0.025), the tap zone
# radius (0.07), and the block's line, through B's hole and the slot's
# centre (datum C, the slot itself), at the tap's mid-station: half the slot
# centre's worst offset from B's, each hole across its loosest slip, the
# two reams off one line by the zone radius and both datum simulators,
# (0.046 + 0.046 + 0.025 + 0.015) / 2 = 0.066, and the B-C datum line's yaw
# moving the tap across (0.0114, below).  hypot(0.27873, 0.30263) = 0.41143.
_KNIFE_DOWEL_SLIP_MAX = knife_dowel.SLIP_CLEARANCE_MAX
_KNIFE_DOWEL_PAIR_SHIFT = (
    _KNIFE_DOWEL_SLIP_MAX / 2.0
    + _KNIFE_DOWEL_SLIP_MAX / 2.0
    + top_frame.HANGER_PRESS_HOLE_POSITION_TOL / 2.0
    + knife_mount.DOWEL_HOLE_PERPENDICULARITY_TOL / 2.0
    + knife_mount.DOWEL_SLOT_PERPENDICULARITY_TOL / 2.0
)  # 0.132: the slot centre's worst offset across the dowel line from B's
# The last term is the datum simulators' (codjiflo round 5, wyUmn): within
# ⊥0.015 to A, B's largest perpendicular inscribed cylinder and C's largest
# perpendicular inscribed width each sit up to t/2 off their feature's own
# centre at the mouth, where the pin roots: t/2 for B's hole plus t/2 for
# C's slot.  B's simulator may sit t/2 off its pin root in any direction,
# so the bolt float's X leg carries t/2 too.  The worst case is the pin
# leaning parallel to the hole's tilt, which stays within the ream's ⊥, so
# the pin's own lean adds nothing past the slip.
# Not charged, and why (codjiflo, PR #1978):
# - The block slot's own ⌖0.05 to A|B.  The slot IS datum C, and the tap and
#   bore are located to A|B|C, so the DRF the bore is placed from is the line
#   from B's axis to the actual slot's centre.  A slot set off B's line by e
#   turns that DRF, and the bore with it, by the same angle the slot's pin
#   turns the block on the crossbar.  Only the gap between the slot's local
#   centre at the pin and the fitted DRF plane is left, about
#   e * (1 - 15.19 / 16.7) = 0.002 at e = 0.025, inside the slip terms' rounding.
# - The crossbar's B-C datum line yaw, in the rock.  Both pin pairs are
#   positioned to that line (⌖Ø0.05 to B|C▷ / C|B▷), so both mounts and the
#   line through their bores turn together.  The lever's trunnion, which
#   spans both bores, turns with them, so the bore-to-trunnion yaw that sets
#   the rock is unchanged.  The bolt holes do not turn with that line, so
#   the bolt float below charges it: the tap, 7.632 from B along the pair,
#   moves across by HANGER_DATUM_LINE_YAW_SHIFT (codjiflo round 4).
HANGER_SCREW_MISMATCH_X = (
    top_frame.HANGER_PIN_X_TOL
    + top_frame.HANGER_PRESS_HOLE_POSITION_TOL / 2.0
    + knife_mount.STUD_TAP_POSITION_TOL / 2.0
    + _KNIFE_DOWEL_SLIP_MAX / 2.0
    + knife_mount.DOWEL_HOLE_PERPENDICULARITY_TOL / 2.0
)  # 0.27873
HANGER_SCREW_MISMATCH_Z = (
    top_frame.HANGER_PIN_X_TOL
    + top_frame.HANGER_PRESS_HOLE_POSITION_TOL / 2.0
    + knife_mount.STUD_TAP_POSITION_TOL / 2.0
    + _KNIFE_DOWEL_PAIR_SHIFT / 2.0
    + top_frame.HANGER_DATUM_LINE_YAW_SHIFT
)
HANGER_SCREW_MISMATCH = math.hypot(HANGER_SCREW_MISMATCH_X, HANGER_SCREW_MISMATCH_Z)
# The hole is drilled from the finished underside. Prove drift over the FULL
# crossbar body to the hole's top end at the faced top, at the longest
# printed grip: tan(0.3 deg) * (36.50 + 0.51) = 0.19378568. The #10 loose
# hole's 0.6095 radial float covers this plus the station mismatch
# (HANGER_SCREW_FLOAT_SPARE).
HANGER_SCREW_DRIFT = top_frame.DRILL_DRIFT_PER_MM * (
    top_frame.HANGER_GRIP + top_frame.HANGER_GRIP_TOL
)
HANGER_SCREW_FLOAT_SPARE = top_frame.HANGER_SCREW_FLOAT - (
    HANGER_SCREW_MISMATCH + HANGER_SCREW_DRIFT
)
# Free rock at the printed-band worst case (drawing-guidelines.md rule 19
# (absorb stacks), and the 2026-10-09 ruling: >=5.0 deg).
# The pair's worst transverse shift acts over the pins' shortest 15.239
# span.  Across the deepest .X block (14.8) that yaw walks the bore's far
# end.  The bore's ⌖Ø0.20 to A|B|C carries a composite Ø0.05 orientation
# refinement to A|B|C (owner ruling 2026-10-27), which adds that whole
# refinement zone.  The lever's ridge spans both mounts' bores, so its own
# yaw adds too (codjiflo, PR #1978): the two bores' inner mouths, each up to
# the position zone radius off nominal in opposite directions, turn the
# ridge by the whole position zone over the shortest mouth-to-mouth run
# (the hanger stations' spacing less the deepest .X block), and that turn
# walks a further 14.8 * 0.20 / 159.3 = 0.0186 across a block.  Judge the
# trunnion in
# the smallest reamed bore at the shoulder its printed controls allow worst:
# the ridge farthest from that side face, the flank at its flattest
# (code review C09: ``sm_summing_lever_spec.KNIFE_SHOULDER_X_MAX`` and
# ``KNIFE_SHOULDER_DROP_MIN``).
KNIFE_DOWEL_SPAN_MIN = knife_dowel.SPAN - knife_dowel.SPAN_TOL
KNIFE_MOUNT_YAW_DEG = math.degrees(
    math.atan(_KNIFE_DOWEL_PAIR_SHIFT / KNIFE_DOWEL_SPAN_MIN)
)
_KNIFE_BLOCK_DEPTH_MAX = knife_mount.SUPPORT_Z_THICK + knife_mount.BLOCK_SIZE_TOL
KNIFE_RIDGE_MOUTH_SPAN_MIN = (
    top_frame.STUD_Z_REAR - top_frame.STUD_Z_FRONT - _KNIFE_BLOCK_DEPTH_MAX
)  # 159.32
KNIFE_RIDGE_YAW_OFFSET = (
    _KNIFE_BLOCK_DEPTH_MAX
    * knife_mount.KNIFE_BORE_POSITION_TOL
    / KNIFE_RIDGE_MOUTH_SPAN_MIN
)
KNIFE_BORE_FAR_END_OFFSET = (
    _KNIFE_BLOCK_DEPTH_MAX * math.tan(math.radians(KNIFE_MOUNT_YAW_DEG))
    + knife_mount.KNIFE_BORE_ORIENTATION_TOL
    + KNIFE_RIDGE_YAW_OFFSET
)
KNIFE_FREE_ROCK_WORST_DEG = knife_mount.free_rock_deg(
    KNIFE_BORE_FAR_END_OFFSET,
    hex_w=2.0 * KNIFE_SHOULDER_X_MAX,
    r_bore=knife_mount.BORE_R_MIN,
    shoulder_drop=KNIFE_SHOULDER_DROP_MIN,
)
KNIFE_FREE_ROCK_FLOOR_DEG = spec.KNIFE_FREE_ROCK_FLOOR_DEG
# The slip fit's angular contract (owner ruling 2026-10-27, #2016 option A).
# The pressed pin and the block's hole are parallel only to within their
# perpendicularity controls: the crossbar ream ⊥Ø0.02 to the faced underside
# and the block's hole and slot ⊥Ø0.015 to A.  Each zone tilts its axis by
# at most atan(zone / length) over the hole's straight wall: its shortest
# printed depth less the floor's corner (the ream's CORNER R0.1 MAX, the
# block's title-block R1.0 MAX) and less KNIFE_REAM_LEAD_ALLOWANCE (ream
# 12.0 - 0.8 - 0.1 - 0.5, hole 9.5 - 0.8 - 1.0 - 0.5).  The proud pin
# (PROUD_MAX, which carries the ream floor's corner lift) bears in the hole
# over its full-diameter length short of its
# rounded free end, and the tightest slip takes a relative tilt of at most
# atan(SLIP_CLEARANCE_MIN / that length) before the pin binds.
#
# The lead allowance is conservatism beyond the print, not an admission of
# an undersize tail: the press ream's size band (Ø3.175 0/-0.010 to 12.0,
# FLAT BOTTOM, CORNER R0.1 MAX) and the block hole's band apply over the
# full depth, so a conforming hole is full size to its floor corner (a
# bevel-lead reamer's undersize tail would be non-conforming), the pin
# bottoms, and PROUD_MAX holds.  The proof simply declines to count the
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
# The pin in whichever seat leans most: B's round hole (⊥Ø to A) or C's
# slot (⊥ to A), both over the block's straight wall.
_KNIFE_BLOCK_SEAT_PERP = max(
    knife_mount.DOWEL_HOLE_PERPENDICULARITY_TOL,
    knife_mount.DOWEL_SLOT_PERPENDICULARITY_TOL,
)
KNIFE_DOWEL_TILT_HOLE_DEG = math.degrees(
    math.atan(_KNIFE_BLOCK_SEAT_PERP / _KNIFE_HOLE_TILT_WALL)
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
    if KNIFE_FREE_ROCK_WORST_DEG < KNIFE_FREE_ROCK_FLOOR_DEG:
        raise RuntimeError(
            f"knife edge rocks {KNIFE_FREE_ROCK_WORST_DEG:.3f} deg at the worst "
            f"case (far-end offset {KNIFE_BORE_FAR_END_OFFSET:.4f}), under "
            f"{KNIFE_FREE_ROCK_FLOOR_DEG}"
        )
    if KNIFE_DOWEL_TILT_CHARGED_DEG >= KNIFE_DOWEL_TILT_ALLOWED_DEG:
        raise RuntimeError(
            f"knife-mount dowel tilt {KNIFE_DOWEL_TILT_CHARGED_DEG:.4f} deg binds "
            f"the tightest slip, which takes {KNIFE_DOWEL_TILT_ALLOWED_DEG:.4f} deg: "
            f"crossbar ream ⊥Ø{top_frame.HANGER_PRESS_HOLE_PERPENDICULARITY_TOL} "
            f"over its {_KNIFE_REAM_TILT_WALL:.1f} wall "
            f"{KNIFE_DOWEL_TILT_REAM_DEG:.4f} deg + block hole "
            f"⊥Ø{knife_mount.DOWEL_HOLE_PERPENDICULARITY_TOL} / slot "
            f"⊥{knife_mount.DOWEL_SLOT_PERPENDICULARITY_TOL}, the larger over its "
            f"{_KNIFE_HOLE_TILT_WALL:.1f} wall {KNIFE_DOWEL_TILT_HOLE_DEG:.4f} deg "
            f"+ seat conformity {KNIFE_SEAT_CONFORMITY} over "
            f"{_KNIFE_SEAT_DEPTH_MIN:.1f} {KNIFE_DOWEL_TILT_SEAT_DEG:.4f} deg "
            f"(owner ruling 2026-10-27, #2016)"
        )
    # Both parts' dowel stations are the dowel spec's pair, and the knife
    # mount's round hole and slot, 9.5 deep from its top seat, are deep
    # enough for the proud pin hanging from the crossbar's 12.0 reams (the
    # spec asserts the print-worst case).
    expected_stations = (-knife_dowel.HANGER_OFFSET, knife_dowel.HANGER_OFFSET)
    for owner, stations in (
        ("knife mount", KNIFE_DOWEL_X_OFFSETS),
        ("crossbar", top_frame.HANGER_PIN_XS),
    ):
        if len(stations) != knife_dowel.PER_MOUNT or any(
            abs(station - expected) > 1e-9
            for station, expected in zip(stations, expected_stations, strict=True)
        ):
            raise RuntimeError(
                f"{owner} dowel stations {stations} are not the dowel pair's "
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
        f"{KNIFE_FREE_ROCK_WORST_DEG:.3f} deg (yaw {KNIFE_MOUNT_YAW_DEG:.3f}, "
        f"t {KNIFE_BORE_FAR_END_OFFSET:.4f})"
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

UPPER_EYE_CLAMP_NOTES = (
    "MHA-SM-04: CLAMP COUNTER-SPRING UPPER EYE TO END PIECE.\n"
    "TIGHTEN UNTIL UPPER EYE IS CLAMPED AND CANNOT SWIVEL.\n"
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
    """CounterSetting: the MHA-SM-04 axis above the knife contact level (the
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
    # The two dowels, their pressed ends on the crossbar's ream floors, stand
    # proud down into the block's slot (-X) and round hole (+X). Every
    # hardware instance is independently fixed; no operational DOF is added.
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
    # Exactly two cut bolts, two new washers and four dowels must survive.
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
    dowel_pairs = [
        knife_dowels[index : index + per_mount]
        for index in range(0, len(knife_dowels), per_mount)
    ]
    for screw, washer, pair, station_z in zip(
        hanger_screws,
        hanger_washers,
        dowel_pairs,
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
        for dowel, x_offset in zip(pair, KNIFE_DOWEL_X_OFFSETS, strict=True):
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
    # The made screw's under-head plane is local Z=0; ROT_Y_POS90 maps head +Z
    # to machine +X, outboard of the end piece, and sends the threaded shank
    # into its blind tap.
    # This mate records the static clamped pose, not a mechanical screw lock.
    # Tightening the physical eye clamp adds no operational DOF.
    screw_rows = ROT_Y_POS90
    screw_position = [
        spring_mounts.GOOSENECK_END_X + sm_gooseneck_geom.SPRING_EYE_GAP,
        gooseneck_origin_y + sm_gooseneck_geom.ARM_Y,
        SUMMING_Z,
    ]
    screw = await place_component(
        adapter,
        "sm-gooseneck-spring-screw",
        screw_position,
        euler_from_rows(screw_rows),
        screw_rows,
        ground=False,
    )
    await lock_mate(
        adapter,
        named_ref(f"Front Plane@{screw}", "PLANE"),
        named_ref(f"Front Plane@{gooseneck}", "PLANE"),
        label="gooseneck spring screw clamped to end piece",
    )
    assert_component_placed(adapter, screw, screw_position, screw_rows)

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
        allowed_pairs=allowed_interference_pairs(ASM_NAME),
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
            "Manufacturing Notes": UPPER_EYE_CLAMP_NOTES,
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
