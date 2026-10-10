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
* knife-hanger-stud x2 -- McMaster 91251A157 #6-32 x 1-1/2 socket head cap
  screws under the stable legacy stem: each drops through the crossbar's #6
  counterbore, its head seated on the counterbore floor (no washer), and
  threads into the knife-mount's #6-32 bottoming top tap.
* knife-mount-dowel x4 -- McMaster 98381A473 1/8 x 3/4 dowels, two per
  knife mount either side of its screw, each pressed to the floor of its
  top-seat hole; one slips into the crossbar underside's blind round hole,
  the other into its blind slot along the dowel line: the pair keys the
  block against turning about the screw without overconstraining it.
* summing-lever -- rocks on the knife edge (Axis3 coincident to the support
  contact ridge); the part the channel + counter springs drive in the M6
  Motion study. The rock is the sub's single FREED operational DOF: its
  drive spec is recorded into the DOF manifest, never authored, so the
  saved model rocks on the knife edge.
* boss-hook (keyed to the lever's anchor eye) + counter-spring + gooseneck
  -- the counter-balance hung from the east column; the post is gripped by
  the top-frame rail hub's set screw (no separate clamp part).
* vn-gooseneck-spring-screw -- purchased fillister, head outboard, clamps the
  supplier upper-eye band to the gooseneck plug face; locked to the fixed
  gooseneck with no additional operational DOF.

Cross-subassembly fits (checked at the top level): the channel springs
(ch-channel.SLDASM) thread the summing-lever plate's O4.5 holes -- gated
analytically by build_ch_channel_assembly._assert_plate_threading; the knife-
hanger screws drop through the top-frame casting's integral crossbar (#6
counterbores with O4.318 clearance holes) and the knife-mount dowels slip
into its blind round holes and slots (fr-frame.SLDASM); the gooseneck post drops
through the casting's rail-hub bore, gripped by its 1/4-20 set screw.

Fix-all strategy (M6.2): every structural component inserted at its exact
final transform and fixed; the summing lever + boss-hook are left free and
constrained by mates; transforms asserted by read-back; zero interference.

Dimensions: cad/DIMENSIONS.md ch. 18-19.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_sm_summing_assembly.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    apply_custom_properties,
    check,
    log,
    run_build,
)
import settled_spring_seats
from _drawing_marks import DRAWN_BY
from _assembly import (
    activate_assembly_contract,
    angle_driver,
    assembly_title_properties,
    assert_free_dof_necessity,
    assert_component_placed,
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
from _transforms import IDENTITY, ROT_Y_180, euler_from_rows, rot_z_rows
from dt_cone_pivot_post_installation import SUMMING_Z
import fr_top_frame_spec as top_frame
import sm_knife_mount_spec as knife_mount
import vn_knife_hanger_stud_spec as hanger_screw
import vn_knife_mount_dowel_spec as knife_dowel
from build_sm_knife_mount import CASTING_UNDERSIDE_Y, MOUNT_GAP

ASM_NAME = "sm-summing"

from spring_mount_geom import COLUMN_X, KNIFE, KNIFE_CONTACT_Y  # noqa: E402

# --- knife bearing supports (build_sm_knife_mount) -----------------------------
from sm_summing_lever_spec import (  # noqa: E402
    HEX_BAND,
    HEX_H,
    HEX_W,
    HEX_Z_INNER,
    HEX_Z_OUTER,
)

HEX_Z_MID = (HEX_Z_INNER + HEX_Z_OUTER) / 2.0  # hex trunnion mid (87.06)

# --- knife-hanger hardware (two #6-32 screws + two dowels) -------------------
# The top-frame, knife-mount, screw and dowel specs own every term of the
# stack.  The 91251A157 build keeps the legacy screw frame (thread tip at local
# Y=0, axis +Y), so seating its under-head face on the crossbar's counterbore
# floor, HANGER_GRIP above the crossbar underside, fixes the screw origin; no
# washer (its thickness band would break the reach stack).  The screw clamps
# the knife mount's top seat to the underside.  Each dowel's pressed end (local
# Y=0, axis +Y) sits on the floor of the knife mount's top-seat hole.
KNIFE_MOUNT_TOP_Y = CASTING_UNDERSIDE_Y - MOUNT_GAP  # 999.7: clamped, gap 0
CROSSBAR_TOP_Y = CASTING_UNDERSIDE_Y + top_frame.RING_HEIGHT
HANGER_SEAT_Y = CASTING_UNDERSIDE_Y + top_frame.HANGER_GRIP  # 1029.7
HANGER_STUD_Y = HANGER_SEAT_Y - hanger_screw.UNDERHEAD_LEN  # 991.6 (thread tip)
# The screw's nominal reach into the knife-mount top tap: 8.10.
HANGER_REACH = KNIFE_MOUNT_TOP_Y - HANGER_STUD_Y
# Its print-worst reach (rule 12): the shortest screw in the longest grip,
# 37.084 - 30.8 = 6.284, and the longest in the shortest, 38.1 - 29.2 = 8.90.
HANGER_REACH_MIN = hanger_screw.LENGTH_MIN - (
    top_frame.HANGER_GRIP + top_frame.HANGER_GRIP_TOL
)
HANGER_REACH_MAX = hanger_screw.LENGTH_MAX - (
    top_frame.HANGER_GRIP - top_frame.HANGER_GRIP_TOL
)
# Full thread engaged at the shortest reach (the flat tip's first pitch is not
# a full thread), 6.284 - 0.794 = 5.49, against the 1.5 D floor, 5.258.
HANGER_ENGAGEMENT_MIN = HANGER_REACH_MIN - hanger_screw.PITCH
HANGER_ENGAGEMENT_FLOOR = hanger_screw.ENGAGEMENT_MIN_D * hanger_screw.SHANK_DIA
# The longest reach under the shallowest full thread (.XX): 8.91 - 8.90 = 0.01.
HANGER_TIP_CLEARANCE = knife_mount.STUD_TAP_THREAD_DEPTH_MIN - HANGER_REACH_MAX
# The plain shank stays in the crossbar: 19.05 of thread covers the 8.90 reach.
HANGER_THREAD_SPARE = hanger_screw.THREAD_LENGTH - HANGER_REACH_MAX
# Diametral clearance of the screw in the crossbar's #6 hole: 0.813.
HANGER_SCREW_CLEARANCE = top_frame.HANGER_CLEARANCE_DIA - hanger_screw.SHANK_DIA
# Each dowel's pressed end on its hole floor: 990.2, standing PROUD 9.55 into
# the crossbar's slip hole or slot.
KNIFE_DOWEL_Y = KNIFE_MOUNT_TOP_Y - knife_dowel.PRESS_DEPTH
# The pair's stations from the screw axis, -X (slot) first: 6.350 along X.
KNIFE_DOWEL_X_OFFSETS = knife_mount.PIN_HOLE_XS
# The screw must still pass the crossbar's #6 clearance hole (rule 12) when
# every station sits at its limit.  Along the dowel line (X): the crossbar's
# round-hole station (.XXX, 0.13), the knife mount's half-span band (0.065),
# its tap's position zone radius (0.05) and the round-hole pin across its
# loosest slip (0.046).  Across it (Z): the crossbar's implied-zero offset of
# the round hole from the screw hole (.XXX, 0.13), the tap zone radius
# (0.05), and the pair's mid-point between the round-hole pin and the slot
# pin, each across its loosest slip and the slot's centre plane off by its
# zone radius, (0.046 + 0.046 + 0.025) / 2 = 0.059.  hypot(0.291, 0.239) =
# 0.376 inside the 0.4065 float.
_KNIFE_DOWEL_SLIP_MAX = top_frame.HANGER_PIN_SLIP_CLEARANCE_MAX
_KNIFE_DOWEL_PAIR_SHIFT = (
    _KNIFE_DOWEL_SLIP_MAX / 2.0
    + _KNIFE_DOWEL_SLIP_MAX / 2.0
    + top_frame.HANGER_SLOT_POSITION_TOL / 2.0
)  # 0.117: the slot pin's worst offset across the dowel line from the round
# hole's pin
HANGER_SCREW_MISMATCH_X = (
    top_frame.HANGER_PIN_X_TOL
    + knife_mount.PIN_HOLE_HALF_SPAN_TOL
    + knife_mount.STUD_TAP_POSITION_TOL / 2.0
    + _KNIFE_DOWEL_SLIP_MAX / 2.0
)  # 0.291
HANGER_SCREW_MISMATCH_Z = (
    top_frame.HANGER_PIN_X_TOL
    + knife_mount.STUD_TAP_POSITION_TOL / 2.0
    + _KNIFE_DOWEL_PAIR_SHIFT / 2.0
)  # 0.239
HANGER_SCREW_MISMATCH = math.hypot(HANGER_SCREW_MISMATCH_X, HANGER_SCREW_MISMATCH_Z)
# The free rock the knife-edge keeps at the rule-12 worst case (the
# 2026-10-09 ruling: >= 5.0 deg).  The pair yaws the block about the screw by
# the slot pin's worst offset over the shortest span, atan(0.117 / 12.57) =
# 0.535 deg; across the deepest .X block (14.8) that walks the bore's far end
# 0.138 off the ridge line, and the bore's ⊥Ø0.05|B zone adds 0.05:
# t = 0.188.  The trunnion is judged at its widest, lowest .XXX section
# (8.21 x 10.138) in the smallest reamed bore (Ø12.00): 6.16 deg.
KNIFE_DOWEL_SPAN_MIN = knife_mount.PIN_HOLE_SPAN - knife_mount.PIN_HOLE_SPAN_TOL
KNIFE_MOUNT_YAW_DEG = math.degrees(
    math.atan(_KNIFE_DOWEL_PAIR_SHIFT / KNIFE_DOWEL_SPAN_MIN)
)
KNIFE_BORE_FAR_END_OFFSET = (
    knife_mount.SUPPORT_Z_THICK + knife_mount.BLOCK_SIZE_TOL
) * math.tan(math.radians(KNIFE_MOUNT_YAW_DEG)) + knife_mount.KNIFE_BORE_ORIENTATION_TOL
KNIFE_FREE_ROCK_WORST_DEG = knife_mount.free_rock_deg(
    KNIFE_BORE_FAR_END_OFFSET,
    hex_w=HEX_W + HEX_BAND,
    hex_h=HEX_H - HEX_BAND,
    r_bore=knife_mount.BORE_R_MIN,
)
KNIFE_FREE_ROCK_FLOOR_DEG = 5.0


def _assert_hanger_axis_positive_y(name: str, transform: list[float]) -> None:
    """Require the authored fastener axis to remain assembly +Y."""
    axis = transform[3:6]
    expected = (0.0, 1.0, 0.0)
    drift = max(
        abs(actual - target) for actual, target in zip(axis, expected, strict=True)
    )
    if drift > 1e-3:
        raise RuntimeError(
            f"{name}: local +Y fastener axis {axis} is not assembly +Y "
            f"(drift {drift:.4f})"
        )


def _assert_knife_hanger_stack() -> None:
    """Gate the purchased screw/dowel stack, print-worst, before any COM
    insertion."""
    if MOUNT_GAP != 0.0:
        raise RuntimeError(
            f"knife-mount top seat must be clamped to the casting: MOUNT_GAP {MOUNT_GAP}"
        )
    cbore_floor_y = CROSSBAR_TOP_Y - top_frame.HANGER_CBORE_DEPTH
    if abs(cbore_floor_y - HANGER_SEAT_Y) > 1e-9:
        raise RuntimeError(
            f"knife-hanger counterbore floor y {cbore_floor_y:.4f} is not the "
            f"HANGER_GRIP seat y {HANGER_SEAT_Y:.4f}"
        )
    under_head_y = HANGER_STUD_Y + hanger_screw.UNDERHEAD_LEN
    if abs(under_head_y - HANGER_SEAT_Y) > 1e-9:
        raise RuntimeError(
            f"knife-hanger screw under-head face {under_head_y:.4f} is not on the "
            f"counterbore floor {HANGER_SEAT_Y:.4f}"
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
            f"knife-hanger screw's {hanger_screw.THREAD_LENGTH:.3f} mm thread is "
            f"shorter than its {HANGER_REACH_MAX:.3f} mm reach"
        )
    if HANGER_SCREW_CLEARANCE <= 0.0:
        raise RuntimeError(
            "knife-hanger screw does not clear the crossbar hole: "
            f"{HANGER_SCREW_CLEARANCE:.4f} mm diametral clearance"
        )
    if HANGER_SCREW_MISMATCH > top_frame.HANGER_SCREW_FLOAT:
        raise RuntimeError(
            f"knife-hanger screw float {top_frame.HANGER_SCREW_FLOAT:.4f} does not "
            f"cover the dowel and tap mismatch {HANGER_SCREW_MISMATCH:.4f}"
        )
    if KNIFE_FREE_ROCK_WORST_DEG < KNIFE_FREE_ROCK_FLOOR_DEG:
        raise RuntimeError(
            f"knife edge rocks {KNIFE_FREE_ROCK_WORST_DEG:.3f} deg at the worst "
            f"case (far-end offset {KNIFE_BORE_FAR_END_OFFSET:.4f}), under "
            f"{KNIFE_FREE_ROCK_FLOOR_DEG}"
        )
    # Both parts' dowel stations are the dowel spec's pair, and the crossbar
    # hole and slot are deep enough for the proud pin (the spec asserts the
    # print-worst case).
    expected_stations = (-knife_dowel.HANGER_OFFSET, knife_dowel.HANGER_OFFSET)
    for owner, stations in (
        ("knife mount", knife_mount.PIN_HOLE_XS),
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
    dowel_top_y = KNIFE_DOWEL_Y + knife_dowel.LENGTH
    slip_floor_y = CASTING_UNDERSIDE_Y + top_frame.HANGER_PIN_HOLE_DEPTH
    if dowel_top_y >= slip_floor_y or knife_dowel.SLIP_DEPTH_CLEARANCE_MIN <= 0.0:
        raise RuntimeError(
            f"knife-mount dowel top {dowel_top_y:.4f} bottoms the crossbar hole "
            f"(floor {slip_floor_y:.4f}; worst clearance "
            f"{knife_dowel.SLIP_DEPTH_CLEARANCE_MIN:.3f} mm)"
        )
    log(
        f"knife-hanger stack: seat {KNIFE_MOUNT_TOP_Y:.4f} (gap {MOUNT_GAP}), "
        f"screw head {HANGER_SEAT_Y:.4f}, tip {HANGER_STUD_Y:.4f}; reach "
        f"{HANGER_REACH:.3f} ({HANGER_REACH_MIN:.3f}..{HANGER_REACH_MAX:.3f}); "
        f"full thread {HANGER_ENGAGEMENT_MIN:.3f} >= {HANGER_ENGAGEMENT_FLOOR:.3f}; "
        f"tip {HANGER_TIP_CLEARANCE:.3f} under the thread; crossbar clearance "
        f"{HANGER_SCREW_CLEARANCE:.4f}, mismatch {HANGER_SCREW_MISMATCH:.4f} <= "
        f"{top_frame.HANGER_SCREW_FLOAT:.4f}; dowel {KNIFE_DOWEL_Y:.4f}.."
        f"{dowel_top_y:.4f} under the slip floor {slip_floor_y:.4f} mm; rock "
        f"{KNIFE_FREE_ROCK_WORST_DEG:.3f} deg (yaw {KNIFE_MOUNT_YAW_DEG:.3f}, "
        f"t {KNIFE_BORE_FAR_END_OFFSET:.4f})"
    )


# --- purchased counter spring and directly threaded lower anchor -----------
import vn_counter_spring_stock_geom as counter_stock  # noqa: E402
import sm_gooseneck_geom  # noqa: E402
import vn_gooseneck_spring_screw_spec as spring_screw  # noqa: E402
import spring_mount_geom as spring_mounts  # noqa: E402
import sm_summing_lever_spec  # noqa: E402
from stock_anchor_geom import ANCHOR_9490T1  # noqa: E402

BOSS_HOOK_POS = (*spring_mounts.COUNTER_ANCHOR_XY, SUMMING_Z)
# The counter spring and gooseneck use complete calibrated placements loaded by
# ``counter_seat`` before assembly creation.

UPPER_EYE_CLAMP_NOTES = (
    "UPPER-EYE CLAMP: FIT MHA-VN-054 THROUGH COUNTER-SPRING UPPER EYE.\n"
    "TIGHTEN HEAD TO CLAMP EYE BAND AGAINST GOOSENECK PLUG FACE.\n"
    "EYE MUST NOT SWIVEL; NO THREADLOCKER REQUIRED."
)


def _assert_counter_spring_top_hang(
    pose: spring_mounts.SpringPose,
    gooseneck_y: float,
) -> None:
    """Bound retention and envelopes at the fixed measured placement.

    Native body contact is certified separately against actual final component
    instances. The half-turn clocking keeps the raised end on the open side of
    the arm.
    """
    ux, uy = pose.axis_xy
    screw_y = gooseneck_y + sm_gooseneck_geom.ARM_Y
    retention = (spring_screw.HEAD_DIA - counter_stock.EYE_ID_MM) / 2.0
    if retention < 1.0:
        raise RuntimeError(f"counter eye head retention only {retention:.3f} mm radial")
    band = (
        abs(ux) * counter_stock.COIL_MEAN_RADIUS_MM
        + uy * counter_stock.LOOP_HALF_RISE_MM
        + counter_stock.WIRE_RADIUS_MM
    )
    axial_gap = (
        min(
            pose.upper_eye_xy[0] - spring_mounts.GOOSENECK_END_X,
            spring_mounts.GOOSENECK_END_X
            + sm_gooseneck_geom.SPRING_EYE_GAP
            - pose.upper_eye_xy[0],
        )
        - band
    )
    # The supplier band is CLAMPED between the plug face and the under-head
    # plane (user, 2026-09-21), not hung on a free stand-off. Zero nominal
    # side clearance is intentional; only floating-point round-off is tolerated.
    if axial_gap < -1e-9:
        raise RuntimeError(
            f"double-loop band does not fit clamped gap: {axial_gap:.9f} mm"
        )
    coil_top = (
        pose.centre_xy[1]
        + uy * counter_stock.coil_end_x_mm(pose.length_mm)
        + abs(ux) * counter_stock.COIL_MEAN_RADIUS_MM
        + counter_stock.WIRE_RADIUS_MM
    )
    main_coil_gap = screw_y - sm_gooseneck_geom.TUBE_DIA / 2.0 - coil_top
    tube_gap, head_gap = spring_mounts.counter_half_turn_clearances(pose, screw_y)
    if min(main_coil_gap, tube_gap, head_gap) < spring_mounts.MIN_CLEARANCE_MM:
        raise RuntimeError(
            f"counter coil/support clearance: main {main_coil_gap:.3f}, "
            f"half-turn/tube {tube_gap:.3f}, half-turn/head {head_gap:.3f} mm"
        )
    log(
        f"counter upper support: head retention {retention:.3f}, "
        f"eye clamp side clearance {axial_gap:.9f}, main coil {main_coil_gap:.3f}, "
        f"half-turn tube/head {tube_gap:.3f}/{head_gap:.3f} mm"
    )


def _assert_counter_spring_hang(pose: spring_mounts.SpringPose) -> None:
    """Require full direct thread engagement and a tensioned supplier spring."""
    anchor = ANCHOR_9490T1
    tap = sm_summing_lever_spec.COUNTER_HOLE_SPEC
    if tap.kind != "tapped" or tap.size != anchor.thread_size:
        raise RuntimeError("counter anchor requires its matching native through tap")
    thread_top = BOSS_HOOK_POS[1] + anchor.thread_start_y_mm
    boss_top = KNIFE[1] + sm_summing_lever_spec.ANCHOR_H / 2.0
    if abs(thread_top - boss_top) > 1e-6:
        raise RuntimeError("counter anchor thread start is not at the boss face")
    if spring_mounts.COUNTER_SHANK_LENGTH_MM < sm_summing_lever_spec.ANCHOR_H - 1e-6:
        raise RuntimeError("trimmed counter anchor does not engage the full boss")
    counter_stock.validate_length_mm(pose.length_mm)
    log(
        f"counter lower anchor: {tap.size} direct through tap, "
        f"{sm_summing_lever_spec.ANCHOR_H:.3f} mm engagement; "
        f"spring inside length {pose.length_mm:.4f} mm, "
        f"calibrated force {spring_mounts.counter_force_n(pose.length_mm):.3f} N"
    )


async def build(adapter) -> dict[str, str]:
    # Flip seeds + free-DOF contract: cad/config/assemblies/<ASM_NAME>.yaml.
    activate_assembly_contract(ASM_NAME)
    counter_seat, gooseneck_origin_y = settled_spring_seats.counter_seat()
    counter_pose = counter_seat.pose
    _assert_counter_spring_hang(counter_pose)
    _assert_counter_spring_top_hang(counter_pose, gooseneck_origin_y)
    _assert_knife_hanger_stack()

    # Reset the free-DOF manifest buffer before any *_driver(free_dof_key=...)
    # call: each freed DOF is recorded (never authored) and persisted below.
    reset_dof_manifest()
    check("create_assembly", await adapter.create_assembly())

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
    # Purchased knife-hanger hardware on each mount centreline: one #6-32
    # screw, its under-head face exactly on the crossbar's counterbore floor
    # (no washer), clamping the block's top seat to the crossbar underside; and
    # two dowels, their pressed ends exactly on the floors of the block's
    # top-seat holes HANGER_OFFSET either side along X, standing proud into the
    # crossbar's slot (-X) and round slip hole (+X).  Every part is independently fixed at the authored transform, so
    # this structural stack contributes no operational DOF.
    hanger_screws: list[str] = []
    knife_dowels: list[str] = []
    for side, station_z in (
        ("front", SUMMING_Z + HEX_Z_MID),
        ("back", SUMMING_Z - HEX_Z_MID),
    ):
        hanger_screws.append(
            await place_component(
                adapter,
                "vn-knife-hanger-stud",
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
                    "vn-knife-mount-dowel",
                    [KNIFE[0] + x_offset, KNIFE_DOWEL_Y, station_z],
                    [0.0, 0.0, 0.0],
                    IDENTITY,
                    ground=True,
                    label=f"knife-mount-dowel ({side}, x {x_offset:+.3f})",
                )
            )

    # Count the live top-level instances, not just the placement requests:
    # exactly two stock screws and four dowels must survive insertion.
    live_names = component_names(adapter)
    for stem, inserted, count in (
        ("vn-knife-hanger-stud", hanger_screws, 2),
        ("vn-knife-mount-dowel", knife_dowels, knife_dowel.QUANTITY),
    ):
        live = [
            name for name in live_names if name == stem or name.startswith(f"{stem}-")
        ]
        if len(live) != count or set(live) != set(inserted):
            raise RuntimeError(
                f"{stem}: expected exactly {count} inserted instances, got "
                f"{sorted(live)}"
            )

    # Read back both physical stacks.  This catches a per-instance station
    # typo that the shared scalar derivation alone cannot: each screw must
    # stand on the knife axis with its head on the counterbore floor and the
    # exact nominal reach, and each dowel must sit at its station either side
    # of its screw, at the same z, its pressed end on the hole floor.
    per_mount = knife_dowel.PER_MOUNT
    dowel_pairs = [
        knife_dowels[index : index + per_mount]
        for index in range(0, len(knife_dowels), per_mount)
    ]
    for screw, pair in zip(hanger_screws, dowel_pairs, strict=True):
        screw_transform = component_transform(adapter, screw)
        _assert_hanger_axis_positive_y(screw, screw_transform)
        screw_o = [value * 1000.0 for value in screw_transform[9:12]]
        screw_under_head_y = screw_o[1] + hanger_screw.UNDERHEAD_LEN
        reach = KNIFE_MOUNT_TOP_Y - screw_o[1]
        if abs(screw_o[0] - KNIFE[0]) > 1e-6:
            raise RuntimeError(
                f"{screw}: axis {screw_o[0] - KNIFE[0]:.6f} mm off the knife x"
            )
        if abs(screw_under_head_y - HANGER_SEAT_Y) > 1e-6:
            raise RuntimeError(
                f"{screw}: under-head/counterbore-floor gap "
                f"{screw_under_head_y - HANGER_SEAT_Y:.6f} mm"
            )
        if abs(reach - HANGER_REACH) > 1e-6:
            raise RuntimeError(f"{screw}: knife-mount reach drifted to {reach:.6f} mm")
        for dowel, x_offset in zip(pair, KNIFE_DOWEL_X_OFFSETS, strict=True):
            dowel_transform = component_transform(adapter, dowel)
            _assert_hanger_axis_positive_y(dowel, dowel_transform)
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
                    f"{dowel}: pressed end {dowel_o[1] - KNIFE_DOWEL_Y:.6f} mm off "
                    "the hole floor"
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
        "vn-boss-hook",
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
    # Preserve the vendor +X coil frame and required half-turn clocking at the
    # complete fixed measured pose; no seed placement or corrective move follows.
    await place_component(
        adapter,
        "vn-counter-spring",
        [*counter_pose.centre_xy, SUMMING_Z],
        euler_from_rows(counter_pose.rotation_rows),
        counter_pose.rotation_rows,
    )
    # Ry(180): the gooseneck's overhang arm reaches from the east column toward
    # the machine centre. Its measured origin Y is inserted directly; the post
    # is held in the top-frame rail-hub bore by its 1/4-20 set screw.
    gooseneck = await place_component(
        adapter,
        "sm-gooseneck",
        [COLUMN_X, gooseneck_origin_y, SUMMING_Z],
        [0.0, 180.0, 0.0],
        ROT_Y_180,
    )
    # The stock under-head plane is local Y=0; Rz(-90) maps head +Y to
    # machine +X, outboard of the plug, and sends the threaded shank into it.
    # Lock to the fixed gooseneck exactly as the magnifier's stock screws are
    # locked to their receiver. It is not a new operational DOF.
    screw_rows = rot_z_rows(-90.0)
    screw_position = [
        spring_mounts.GOOSENECK_END_X + sm_gooseneck_geom.SPRING_EYE_GAP,
        gooseneck_origin_y + sm_gooseneck_geom.ARM_Y,
        SUMMING_Z,
    ]
    screw = await place_component(
        adapter,
        "vn-gooseneck-spring-screw",
        screw_position,
        euler_from_rows(screw_rows),
        screw_rows,
        ground=False,
    )
    await lock_mate(
        adapter,
        named_ref(f"Front Plane@{screw}", "PLANE"),
        named_ref(f"Front Plane@{gooseneck}", "PLANE"),
        label="gooseneck spring screw clamped to plug",
    )
    assert_component_placed(adapter, screw, screw_position, screw_rows)

    # Certify the AS-BUILT model.  The lever rock remains the sole intended
    # freed DOF; the exact allowed-stem set rejects any free screw, dowel, or
    # other structural component.  The lock-mated boss-hook MUST read
    # under-constrained WITH the lever -- a grounded/fixed regression would
    # freeze the counter-spring anchor while the lever still swings.
    assert_free_dof_necessity(
        adapter,
        1,
        required_stems=("sm-summing-lever", "vn-boss-hook"),
        allowed_stems=("sm-summing-lever", "vn-boss-hook"),
    )
    write_dof_manifest(ASM_NAME)
    check_no_interference(
        adapter,
        allowed_pairs=allowed_interference_pairs(ASM_NAME),
    )
    # Title-block identity for the assembly drawing (draw_sm_summing_assembly.py):
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
            "Manufacturing Notes": UPPER_EYE_CLAMP_NOTES,
            "Drawn By": DRAWN_BY,
        },
    )
    return await save_assembly_and_images(
        adapter,
        ASM_NAME,
        native_contact_check=assert_assembly_spring_contacts,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
