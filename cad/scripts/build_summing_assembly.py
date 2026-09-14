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
from dataclasses import replace

from _common import (
    apply_custom_properties,
    apply_summary_info,
    check,
    log,
    run_build,
)
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
    reledger_to_solved,
    reset_dof_manifest,
    save_assembly_and_images,
    write_dof_manifest,
)
from _cwm import put_component_pose
from _native_spring_contact import solve_component_contact
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
# Analytical seeds only: unchanged supplier bodies determine final native seats.
SPRING_SEED_POS = (*spring_mounts.COUNTER_REFERENCE_POSE.centre_xy, SUMMING_Z)
GOOSENECK_SEED_POS = (COLUMN_X, spring_mounts.GOOSENECK_ORIGIN_Y, SUMMING_Z)


def _assert_counter_spring_top_hang(
    pose: spring_mounts.SpringPose | None = None,
    gooseneck_y: float | None = None,
) -> None:
    """Bound retention/envelopes, not native wire contact.

    Defaults check the analytical insertion seeds offline. The assembly passes
    its actual translated pose and gooseneck height after native seating; only
    the native body predicate certifies contact. The half-turn clocking keeps
    the raised end on the open side of the arm.
    """
    pose = spring_mounts.COUNTER_REFERENCE_POSE if pose is None else pose
    gooseneck_y = GOOSENECK_SEED_POS[1] if gooseneck_y is None else gooseneck_y
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
    axial_gap = min(
        pose.upper_eye_xy[0] - spring_mounts.GOOSENECK_END_X,
        spring_mounts.GOOSENECK_END_X + gooseneck_geom.SCREW_SHANK_LEN
        - pose.upper_eye_xy[0],
    ) - band
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


def _assert_counter_spring_hang() -> None:
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
    pose = spring_mounts.COUNTER_REFERENCE_POSE
    counter_stock.validate_length_mm(pose.length_mm)
    log(
        f"counter lower anchor: {tap.size} direct through tap, "
        f"{summing_lever_spec.ANCHOR_H:.3f} mm engagement; "
        f"spring inside length {pose.length_mm:.4f} mm, "
        f"reference force {spring_mounts.counter_force_n(pose.length_mm):.3f} N"
    )


def _seat_counter_native_contacts(adapter, counter: str, boss_hook: str, gooseneck: str) -> None:
    """Translate rigid supplier geometry to its two independently certified seats."""
    seed = spring_mounts.COUNTER_REFERENCE_POSE
    ux, uy = seed.axis_xy
    lower_direction = (-ux, -uy, 0.0)
    upper_direction = (0.0, -1.0, 0.0)
    bracket = spring_mounts.MIN_CLEARANCE_MM / 2.0

    def land(name: str, direction: tuple[float, float, float], offset: float) -> None:
        target = component_transform(adapter, name)
        for axis, value in enumerate(direction):
            target[9 + axis] += value * offset / 1000.0
        put_component_pose(adapter, name, target)
        actual = component_transform(adapter, name)
        if len(actual) != len(target) or max(abs(a - b) for a, b in zip(actual, target)) > 1e-12:
            raise RuntimeError(f"{name}: native seating transform readback mismatch")
        reledger_to_solved(adapter, name)

    lower = solve_component_contact(
        adapter, counter, boss_hook, lower_direction, bracket,
        label="counter lower native seat",
    )
    land(counter, lower_direction, lower.offset_mm)
    upper = solve_component_contact(
        adapter, gooseneck, counter, upper_direction, bracket,
        label="counter upper native seat",
    )
    land(gooseneck, upper_direction, upper.offset_mm)
    # A fresh already_seated certificate witnesses the CURRENT native placement.
    # A bracketed result instead proposes another move and must not pass this
    # check. The full assembly gate independently retains zero overlap.
    for label, moving, fixed, direction in (
        ("counter lower", counter, boss_hook, lower_direction),
        ("counter upper", gooseneck, counter, upper_direction),
    ):
        contact = solve_component_contact(
            adapter, moving, fixed, direction, bracket, label=f"{label} native seat verification",
        )
        if contact.certificate != "already_seated":
            raise RuntimeError(f"{label}: current native seat is not certified ({contact!r})")
    actual_centre = component_origin(adapter, counter)
    dx, dy = (actual_centre[i] - seed.centre_xy[i] for i in range(2))
    pose = replace(
        seed,
        centre_xy=tuple(actual_centre[:2]),
        lower_eye_xy=(seed.lower_eye_xy[0] + dx, seed.lower_eye_xy[1] + dy),
        upper_eye_xy=(seed.upper_eye_xy[0] + dx, seed.upper_eye_xy[1] + dy),
    )
    _assert_counter_spring_top_hang(pose, component_origin(adapter, gooseneck)[1])
    log(
        f"counter native seats: lower {lower.offset_mm:.9g} mm along -axis, "
        f"gooseneck {upper.offset_mm:.9g} mm along -Y; "
        f"unchanged supplier inside length {pose.length_mm:.9g} mm"
    )


async def build(adapter) -> dict[str, str]:
    _assert_counter_spring_hang()
    _assert_counter_spring_top_hang()
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
    # Preserve the vendor +X coil frame and its required half-turn clocking.
    counter = await place_component(
        adapter,
        "counter-spring",
        list(SPRING_SEED_POS),
        euler_from_rows(spring_mounts.COUNTER_REFERENCE_POSE.rotation_rows),
        spring_mounts.COUNTER_REFERENCE_POSE.rotation_rows,
    )
    # Ry(180): the gooseneck's overhang arm reaches from
    # the east column toward the machine centre. The post is held in the
    # top-frame casting's rail-hub bore by its 1/4-20 set screw
    # (frame.SLDASM) -- there is no separate clamp part.
    gooseneck = await place_component(
        adapter,
        "gooseneck",
        list(GOOSENECK_SEED_POS),
        [0.0, 180.0, 0.0],
        ROT_Y_180,
    )
    _seat_counter_native_contacts(adapter, counter, bh, gooseneck)

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
    return await save_assembly_and_images(adapter, ASM_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
