r"""Reproduction script: summing subassembly (book ch. 18-19).

The head of the analyzer's output, where the 20 channel springs converge on
the summing lever, in machine coordinates (assembly origin = base origin;
base top y = 50.8; the output side is -Z). The lever rocks on a true knife
edge carried by two bearing supports, hung from the top-frame casting's
integral crossbar by two knife-hanger studs, and counter-balanced from
above by the boss-hook / counter-spring / gooseneck chain.

* knife-mount x2 -- the bearing supports, one per hex trunnion, centred on
  ``SUMMING_Z`` and separated by ``+/-HEX_Z_MID``.
* knife-hanger-washer x2 -- McMaster 90126A211 washers seated separately on
  the casting top face, one at each mount centreline.
* knife-hanger-stud x2 -- McMaster 91247A720 bolts under the stable legacy
  stem: each passes through its washer and the casting's clearance hole, then
  threads into the knife-mount's 1/2-13 top tap.
* summing-lever -- rocks on the knife edge (Axis3 coincident to the support
  contact ridge); the part the channel + counter springs drive in the M6
  Motion study. The rock is the sub's single FREED operational DOF: its
  drive spec is recorded into the DOF manifest, never authored, so the
  saved model rocks on the knife edge.
* boss-hook (keyed to the lever's anchor eye) + counter-spring + gooseneck
  -- the counter-balance hung from the east column; the post is gripped by
  the top-frame rail hub's set screw (no separate clamp part).

Cross-subassembly fits (checked at the top level): the channel springs
(channel.SLDASM) thread the summing-lever plate's O4.5 holes -- gated
analytically by build_channel_assembly._assert_plate_threading; the knife-
hanger studs rise through the top-frame casting's integral crossbar (O13.49
close-clearance holes, frame.SLDASM); the gooseneck post drops through the
casting's rail-hub bore, gripped by its 1/4-20 set screw.

Fix-all strategy (M6.2): every structural component inserted at its exact
final transform and fixed; the summing lever + boss-hook are left free and
constrained by mates; transforms asserted by read-back; zero interference.

Dimensions: cad/DIMENSIONS.md ch. 18-19.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_summing_assembly.py
"""

from __future__ import annotations

import sys

from _common import (
    apply_custom_properties,
    apply_summary_info,
    check,
    log,
    run_build,
)
import settled_spring_seats
from _drawing_marks import DRAWN_BY
from _assembly import (
    angle_driver,
    assembly_title_properties,
    assert_free_dof_necessity,
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
from _native_spring_contact import assert_native_contact
from _interference_contracts import allowed_interference_pairs
from _transforms import IDENTITY, ROT_Y_180, euler_from_rows
from cone_pivot_post_installation import SUMMING_Z
from build_knife_hanger_stud import (
    SHANK_DIA as BOLT_MAJOR_DIA,
    UNDERHEAD_LEN,
)
from build_knife_hanger_washer import (
    INNER_DIA as HANGER_WASHER_INNER_DIA,
    OUTER_DIA as HANGER_WASHER_OUTER_DIA,
    THICKNESS as HANGER_WASHER_THICKNESS,
)
from build_knife_mount import CASTING_UNDERSIDE_Y, MOUNT_GAP, STUD_TAP_DEPTH
from build_top_frame import RING_HEIGHT as CROSSBAR_HEIGHT, STUD_HOLE_DIA

ASM_NAME = "summing"

from spring_mount_geom import COLUMN_X, KNIFE, KNIFE_CONTACT_Y  # noqa: E402

# --- knife bearing supports (build_knife_mount) -----------------------------
from summing_lever_spec import HEX_Z_INNER, HEX_Z_OUTER  # noqa: E402

HEX_Z_MID = (HEX_Z_INNER + HEX_Z_OUTER) / 2.0  # hex trunnion mid (87.06)

# --- knife-hanger hardware (two bolts + two separate washers) ----------------
# The top-frame crossbar and knife-mount exports own the surrounding stack.
# Each washer's local origin is its mid-plane.  The 91247A720 wrapper preserves
# the legacy bolt frame (thread tip at local Y=0, axis +Y), so seating its
# under-head face on the washer top determines the bolt origin without an
# independent stud-station assumption.
CROSSBAR_TOP_Y = CASTING_UNDERSIDE_Y + CROSSBAR_HEIGHT
HANGER_WASHER_Y = CROSSBAR_TOP_Y + HANGER_WASHER_THICKNESS / 2.0
HANGER_WASHER_TOP_Y = CROSSBAR_TOP_Y + HANGER_WASHER_THICKNESS
HANGER_STUD_Y = HANGER_WASHER_TOP_Y - UNDERHEAD_LEN
KNIFE_MOUNT_TOP_Y = CASTING_UNDERSIDE_Y - MOUNT_GAP
KNIFE_MOUNT_THREAD_ENGAGEMENT = KNIFE_MOUNT_TOP_Y - HANGER_STUD_Y


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
    """Gate the purchased washer/bolt stack before any COM insertion."""
    bolt_in_washer_clearance = HANGER_WASHER_INNER_DIA - BOLT_MAJOR_DIA
    bolt_in_crossbar_clearance = STUD_HOLE_DIA - BOLT_MAJOR_DIA
    washer_crossbar_seat = (HANGER_WASHER_OUTER_DIA - STUD_HOLE_DIA) / 2.0
    if bolt_in_washer_clearance <= 0.0:
        raise RuntimeError(
            "knife-hanger washer ID does not clear the 91247A720 bolt: "
            f"{bolt_in_washer_clearance:.4f} mm diametral clearance"
        )
    if bolt_in_crossbar_clearance <= 0.0:
        raise RuntimeError(
            "knife-hanger bolt does not clear the crossbar hole: "
            f"{bolt_in_crossbar_clearance:.4f} mm diametral clearance"
        )
    if washer_crossbar_seat <= 0.0:
        raise RuntimeError(
            "knife-hanger washer OD does not seat beyond the crossbar hole: "
            f"{washer_crossbar_seat:.4f} mm radial bearing width"
        )

    washer_lower_y = HANGER_WASHER_Y - HANGER_WASHER_THICKNESS / 2.0
    washer_upper_y = HANGER_WASHER_Y + HANGER_WASHER_THICKNESS / 2.0
    bolt_under_head_y = HANGER_STUD_Y + UNDERHEAD_LEN
    if abs(washer_lower_y - CROSSBAR_TOP_Y) > 1e-9:
        raise RuntimeError("knife-hanger washer lower face is not seated on crossbar")
    if abs(bolt_under_head_y - washer_upper_y) > 1e-9:
        raise RuntimeError("knife-hanger bolt under-head face is not seated on washer")
    if not 0.0 < KNIFE_MOUNT_THREAD_ENGAGEMENT <= STUD_TAP_DEPTH:
        raise RuntimeError(
            "knife-hanger bolt misses the knife-mount tap envelope: "
            f"{KNIFE_MOUNT_THREAD_ENGAGEMENT:.4f} mm engagement"
        )
    if abs(KNIFE_MOUNT_THREAD_ENGAGEMENT - 11.3735) > 1e-9:
        raise RuntimeError(
            "knife-hanger thread engagement drifted from 11.3735 mm: "
            f"{KNIFE_MOUNT_THREAD_ENGAGEMENT:.4f} mm"
        )
    log(
        "knife-hanger stack: washer "
        f"{washer_lower_y:.4f}..{washer_upper_y:.4f}, bolt under-head "
        f"{bolt_under_head_y:.4f}, engagement {KNIFE_MOUNT_THREAD_ENGAGEMENT:.4f}; "
        f"ID clearance {bolt_in_washer_clearance:.4f}, crossbar clearance "
        f"{bolt_in_crossbar_clearance:.4f}, radial seat {washer_crossbar_seat:.4f} mm"
    )


# --- purchased counter spring and directly threaded lower anchor -----------
import counter_spring_stock_geom as counter_stock  # noqa: E402
import gooseneck_geom  # noqa: E402
import spring_mount_geom as spring_mounts  # noqa: E402
import summing_lever_spec  # noqa: E402
from stock_anchor_geom import ANCHOR_9490T1  # noqa: E402

BOSS_HOOK_POS = (*spring_mounts.COUNTER_ANCHOR_XY, SUMMING_Z)
# The counter spring and gooseneck use complete calibrated placements loaded by
# ``counter_seat`` before assembly creation.


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
    screw_y = gooseneck_y + gooseneck_geom.ARM_Y
    retention = (gooseneck_geom.SCREW_HEAD_DIA - counter_stock.EYE_ID_MM) / 2.0
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
            + gooseneck_geom.SCREW_SHANK_LEN
            - pose.upper_eye_xy[0],
        )
        - band
    )
    if axial_gap < spring_mounts.MIN_CLEARANCE_MM:
        raise RuntimeError(
            f"double-loop band does not fit exposed shank: {axial_gap:.3f} mm"
        )
    coil_top = (
        pose.centre_xy[1]
        + uy * counter_stock.coil_end_x_mm(pose.length_mm)
        + abs(ux) * counter_stock.COIL_MEAN_RADIUS_MM
        + counter_stock.WIRE_RADIUS_MM
    )
    main_coil_gap = screw_y - gooseneck_geom.TUBE_DIA / 2.0 - coil_top
    tube_gap, head_gap = spring_mounts.counter_half_turn_clearances(pose, screw_y)
    if min(main_coil_gap, tube_gap, head_gap) < spring_mounts.MIN_CLEARANCE_MM:
        raise RuntimeError(
            f"counter coil/support clearance: main {main_coil_gap:.3f}, "
            f"half-turn/tube {tube_gap:.3f}, half-turn/head {head_gap:.3f} mm"
        )
    log(
        f"counter upper support: head retention {retention:.3f}, "
        f"eye axial gap {axial_gap:.3f}, main coil {main_coil_gap:.3f}, "
        f"half-turn tube/head {tube_gap:.3f}/{head_gap:.3f} mm"
    )


def _assert_counter_spring_hang(pose: spring_mounts.SpringPose) -> None:
    """Require full direct thread engagement and a tensioned supplier spring."""
    anchor = ANCHOR_9490T1
    tap = summing_lever_spec.COUNTER_HOLE_SPEC
    if tap.kind != "tapped" or tap.size != anchor.thread_size:
        raise RuntimeError("counter anchor requires its matching native through tap")
    thread_top = BOSS_HOOK_POS[1] + anchor.thread_start_y_mm
    boss_top = KNIFE[1] + summing_lever_spec.ANCHOR_H / 2.0
    if abs(thread_top - boss_top) > 1e-6:
        raise RuntimeError("counter anchor thread start is not at the boss face")
    if spring_mounts.COUNTER_SHANK_LENGTH_MM < summing_lever_spec.ANCHOR_H - 1e-6:
        raise RuntimeError("trimmed counter anchor does not engage the full boss")
    counter_stock.validate_length_mm(pose.length_mm)
    log(
        f"counter lower anchor: {tap.size} direct through tap, "
        f"{summing_lever_spec.ANCHOR_H:.3f} mm engagement; "
        f"spring inside length {pose.length_mm:.4f} mm, "
        f"calibrated force {spring_mounts.counter_force_n(pose.length_mm):.3f} N"
    )


async def build(adapter) -> dict[str, str]:
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
        "knife-mount",
        [KNIFE[0], KNIFE_CONTACT_Y, SUMMING_Z + HEX_Z_MID],
        [0.0, 0.0, 0.0],
        IDENTITY,
        label="knife-mount (front)",
    )
    await place_component(
        adapter,
        "knife-mount",
        [KNIFE[0], KNIFE_CONTACT_Y, SUMMING_Z - HEX_Z_MID],
        [0.0, 0.0, 0.0],
        IDENTITY,
        label="knife-mount (back)",
    )
    # Purchased knife-hanger hardware, one fixed washer + bolt pair on each
    # mount centreline.  The washer lower face is exactly on the crossbar top;
    # the 91247A720 under-head face is exactly on the washer upper face.  Both
    # parts are independently fixed at the authored transform, so this
    # structural stack contributes no operational DOF.
    hanger_washers: list[str] = []
    hanger_bolts: list[str] = []
    for side, station_z in (
        ("front", SUMMING_Z + HEX_Z_MID),
        ("back", SUMMING_Z - HEX_Z_MID),
    ):
        hanger_washers.append(
            await place_component(
                adapter,
                "knife-hanger-washer",
                [KNIFE[0], HANGER_WASHER_Y, station_z],
                [0.0, 0.0, 0.0],
                IDENTITY,
                ground=True,
                label=f"knife-hanger-washer ({side})",
            )
        )
        hanger_bolts.append(
            await place_component(
                adapter,
                "knife-hanger-stud",
                [KNIFE[0], HANGER_STUD_Y, station_z],
                [0.0, 0.0, 0.0],
                IDENTITY,
                ground=True,
                label=f"knife-hanger-stud ({side})",
            )
        )

    # Count the live top-level instances, not just the placement requests:
    # exactly two stock bolts and two separate washers must survive insertion.
    live_names = component_names(adapter)
    for stem, inserted in (
        ("knife-hanger-washer", hanger_washers),
        ("knife-hanger-stud", hanger_bolts),
    ):
        live = [
            name for name in live_names if name == stem or name.startswith(f"{stem}-")
        ]
        if len(live) != 2 or set(live) != set(inserted):
            raise RuntimeError(
                f"{stem}: expected exactly two inserted instances, got {sorted(live)}"
            )

    # Read back both physical stacks.  This catches a per-instance station
    # typo that the shared scalar derivation alone cannot: each washer must
    # remain coaxial with its bolt, on the crossbar, with zero axial gap at
    # the under-head face and the exact residual tap engagement.
    for washer, bolt in zip(hanger_washers, hanger_bolts, strict=True):
        washer_transform = component_transform(adapter, washer)
        bolt_transform = component_transform(adapter, bolt)
        _assert_hanger_axis_positive_y(washer, washer_transform)
        _assert_hanger_axis_positive_y(bolt, bolt_transform)
        washer_o = [value * 1000.0 for value in washer_transform[9:12]]
        bolt_o = [value * 1000.0 for value in bolt_transform[9:12]]
        radial_offset = max(
            abs(washer_o[0] - bolt_o[0]),
            abs(washer_o[2] - bolt_o[2]),
        )
        washer_lower_y = washer_o[1] - HANGER_WASHER_THICKNESS / 2.0
        washer_upper_y = washer_o[1] + HANGER_WASHER_THICKNESS / 2.0
        bolt_under_head_y = bolt_o[1] + UNDERHEAD_LEN
        engagement = KNIFE_MOUNT_TOP_Y - bolt_o[1]
        if radial_offset > 1e-6:
            raise RuntimeError(
                f"{bolt}: washer/bolt axes offset {radial_offset:.6f} mm"
            )
        if abs(washer_lower_y - CROSSBAR_TOP_Y) > 1e-6:
            raise RuntimeError(
                f"{washer}: lower face misses crossbar by "
                f"{washer_lower_y - CROSSBAR_TOP_Y:.6f} mm"
            )
        if abs(bolt_under_head_y - washer_upper_y) > 1e-6:
            raise RuntimeError(
                f"{bolt}: under-head/washer gap "
                f"{bolt_under_head_y - washer_upper_y:.6f} mm"
            )
        if abs(engagement - KNIFE_MOUNT_THREAD_ENGAGEMENT) > 1e-6:
            raise RuntimeError(
                f"{bolt}: knife-mount engagement drifted to {engagement:.6f} mm"
            )
    # Summing lever: knife-edge revolute = coincident axis-to-axis on the knife
    # line (the bore-bottom rocking edge) + a Front-plane axial distance,
    # leaving the rock DOF -- the sub's freed operational DOF (its drive spec
    # recorded into the DOF manifest, never authored). This is the part the
    # counter spring + channel springs drive in the M6 Motion study.
    sl = await place_component(
        adapter,
        "summing-lever",
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
        "boss-hook",
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
    counter = await place_component(
        adapter,
        "counter-spring",
        [*counter_pose.centre_xy, SUMMING_Z],
        euler_from_rows(counter_pose.rotation_rows),
        counter_pose.rotation_rows,
    )
    # Ry(180): the gooseneck's overhang arm reaches from the east column toward
    # the machine centre. Its measured origin Y is inserted directly; the post
    # is held in the top-frame rail-hub bore by its 1/4-20 set screw.
    gooseneck = await place_component(
        adapter,
        "gooseneck",
        [COLUMN_X, gooseneck_origin_y, SUMMING_Z],
        [0.0, 180.0, 0.0],
        ROT_Y_180,
    )

    # Certify the AS-BUILT model.  The lever rock remains the sole intended
    # freed DOF; the exact allowed-stem set rejects any free washer, bolt, or
    # other structural component.  The lock-mated boss-hook MUST read
    # under-constrained WITH the lever -- a grounded/fixed regression would
    # freeze the counter-spring anchor while the lever still swings.
    assert_free_dof_necessity(
        adapter,
        1,
        required_stems=("summing-lever", "boss-hook"),
        allowed_stems=("summing-lever", "boss-hook"),
    )
    write_dof_manifest(ASM_NAME)
    check_no_interference(
        adapter,
        allowed_pairs=allowed_interference_pairs(ASM_NAME),
    )
    # Title-block identity for the assembly drawing (draw_summing_assembly.py):
    # assembly_title_properties supplies the Title/Generator and TOL_* cells
    # finalize_drawing requires without consulting the part registry;
    # released component drawing (the BOM has no material/finish columns).
    apply_custom_properties(
        adapter,
        {
            **assembly_title_properties(ASM_NAME),
            # MHA-A## = assembly-drawing ids, beside the parts' MHA-### range
            # (a longer number overflows the DWG. NO. title-block cell).
            "Number": "MHA-A07",
            "Revision Description": "Initial release",
            "Material": "SEE COMPONENT DRAWINGS",
            "Material Specification": "SEE COMPONENT DRAWINGS",
            "Finish": "SEE COMPONENT DRAWINGS",
            "Quantity": "1",
            "Drawn By": DRAWN_BY,
        },
    )
    # The PART cell resolves the document summary Title; "summing assembly" (not
    # the bare stem) so the sheet identifies itself as an assembly drawing.
    apply_summary_info(adapter, title=f"{ASM_NAME} assembly")
    artefacts = await save_assembly_and_images(adapter, ASM_NAME)
    # Check the actual saved/reopened bodies after final rebuild reconciliation.
    lower_distance = assert_native_contact(
        adapter,
        counter,
        bh,
        maximum_distance_mm=counter_seat.lower_maximum_distance_mm,
        label="counter lower persisted native seat",
    )
    upper_distance = assert_native_contact(
        adapter,
        gooseneck,
        counter,
        maximum_distance_mm=counter_seat.upper_maximum_distance_mm,
        label="counter upper persisted native seat",
    )
    log(
        f"counter persisted native contacts: lower {lower_distance:.9g} mm, "
        f"upper {upper_distance:.9g} mm"
    )
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
