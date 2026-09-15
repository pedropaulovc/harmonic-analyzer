r"""Reproduction script: channel subassembly (book ch. 13-17; 20 channels).

The complete 20-channel motion chain between the drive train and the
output: connecting rods riding the integral cams, the rocker-arm seesaw
bank on its pivot shaft, the amplitude bars running UP the spine, and the
top-lever bank on its fulcrum shaft with the channel springs hanging from
the lever tips, each retained by a stock eyebolt threaded into the plate.
128 components:

Coordinates are machine frame (#151: crank at machine -X, output side -Z;
the M6.8 mirror layer is gone).

* pivot-shaft x1 (rocker bank at (72.9, 253.8), along Z, centred on the
  20-station stack, 170 long -- 2026-09: ends 4 past each bracket ear)
  + fulcrum-shaft x1 (lever bank at (199.9, 1061.4), 182 long - the
  228.6 shaft clipped the west columns at top level, M6.5)
* pivot-bracket x2 (2026-09 photo re-derive, ch14 page002_img01/img07: the
  black foot-and-ear brackets on the rocker-arm-support's top, 78 either
  side of the stack centre so both feet sit ON the support (the old chrome
  pivot-ball-mount pair is retired -- photo-refuted, and its south pillar
  stood 19 mm past the support's end in mid-air))
* fulcrum-keeper x2 + frame-side-screw x2 (the black shaft-END brackets on
  the top-frame west rail top face -- ch17 p.40 bottom-left / ch30 p008;
  ball centres (199.9, 1061.4, 3.088 +- 88.75), foot screws down into the
  rail's tapped #8-32 holes at z 3.088 +- 74.0; replaces the photo-refuted
  chrome baluster lever pair, 2026-08-02)
* rocker-arm x20, connecting-rod x20, amplitude-bar x20, channel-lever
  x20 (2026-09-02: the arms and levers carry INTEGRAL hubs whose faces
  set the station pitch -- the 19 + 19 spacer bushings are retired),
  channel-spring-installed x20 (McMaster 9432K31, with fixed measured
  installed-length variants),
  spring-hook x20 (McMaster 9489T111 eyebolts, supplied nuts omitted;
  their shanks thread directly into the summing plate)

Crank home retains the drive train's +1.5 degree tooth phase on the integral
cam lobes; the lobe-up correction remains issue #749. ``channel_kinematics``
solves the rod, rocker, bar and lever poses from that configured geometry.
The bar rests its foot-notch roof on the tilted arm's top-edge arc
(contact at the bar's +X edge, machine frame); the bar's top pin height
leaves the levers essentially level (-0.002 deg at neutral, the ch14 ROM
re-derive rest pose). Purchased 9432K31 hooks seat in the existing lever
holes and in 9489T111 lower eyes. The lower anchors thread directly into
the summing plate, without nuts. ``settled_spring_seats`` loads the fixed
measured placement table for each supported amplitude; the build performs
no native fitting or trial motion. Eye centres are not pin-contact points. The
lower anchors' threaded engagement and clearances are checked at the top level.

Orientation notes: the amplitude bar is rotated 90 deg about its long
axis (Ry(-90), machine frame) so its end slots and O2 top pin hole run
across Z, straddling the 2.5 arm / 3.0 lever; the spring's end-hook ring
lies perpendicular to the lever face. Channel
stations: z_j = -64.0124 + 7.0565 j, arm/bar/lever mid-planes at z_j + 0.8,
cam/rod plane z_j - 3.25 (rod tip strap face-flush against the arm).

Operational DOF use semantic contact mates; fixed hardware and the static
spring bank retain their measured transforms. Radial joints are concentric
or coincident, and parts within a channel slice share an axial reference:
  * rocker/lever concentric on the shaft OD; rod/bar coincident axis-to-
    axis on the named bore axes (the revolute radials);
  * the rocker is each channel's Z ANCHOR: channel 0 sits on the Front
    datum; every other rocker is a PITCH distance off the previous
    channel's rocker mid-plane (hub face on hub face);
    the lever and the amplitude bar are seated COINCIDENT to the rocker's
    mid-plane (lever Front plane / bar MidWidth plane), so a channel's
    parts share ONE Z reference;
  * the fulcrum shaft is datum-located by orthogonal plane distances;
  * springs and lower anchors are grounded at fixed measured / threaded
    installation transforms; their actual final contacts are statically gated.
Each of the rocker/rod/bar joints keeps its operational DOF genuinely
FREE (rocker swing + rod follow + bar amplitude -- 3 live DOF per
channel); each freed DOF's drive spec is recorded into the assembly's
DOF manifest (`.channel.dof.json`) for the transient verify:kinematics
replays, never authored. The channel LEVER carries no pin of its own:
the J5 foot-on-arc coupling (the bar's foot axis held at its as-solved
radius from the rocker's arc-centre axis) closes the rocker -> bar ->
lever chain, so dragging the rocker articulates the whole channel and
the lever reads under-constrained WITH it (coupled, magnifier-wheel
style, not separately freed). Far-side mate flips are caught by
reading back the origin and re-adding flipped. Saved state: every
component fixed, fully defined or coupled-free, zero interference
(face-flush and tangent contacts allowed).

Only the SEED channels are authored mate-by-mate: channel 0 (the global
Z anchor) plus the first channel >= 1 of each distinct amplitude value.
Every other channel is ONE CopyWithMates2 of its seed's 4-part slice
(rocker + rod + bar + lever, 9 mates -- see _cwm.py for the pinned
native-call contract). The J1a axial dim is re-pointed to THIS channel's
PREVIOUS channel's rocker (Repeat=false + NewEntityToMateTo) at the local PITCH
seat -- the SAME per-gap neighbour idiom the authored channels use --
so a copy is topologically identical to an authored channel, not chained
to the seed's bushing on a cumulative ladder. The copied mates pin a copy only up
to its 3 free operational DOF, so its design pose is PUT (no solve)
right after the copy and one closing rebuild solves everything from
that consistent state. The call's return value lies, so each copy is
then proven from the model -- pose = seed pose translated down-spine,
per-part mate count = the seed's, constrained status under-constrained
-- and its 3 freed-DOF drive specs are recorded exactly like an
authored channel's, its pose re-anchored into the ledger.

The cams themselves live in drive-train.SLDASM (integral with the
cylinder gears); the frame, supports and top-frame ring in frame.SLDASM.
Cross-subassembly fits are checked at the top level (M6.5).

Dimensions: cad/DIMENSIONS.md ch. 14 layout + "Channel & top-frame
layout" tables.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_channel_assembly.py
"""

from __future__ import annotations

import functools
import math
import sys
from typing import Any, Literal

import _config
import _telemetry
import channel_kinematics
import settled_spring_seats
from _common import (
    UNDER_CONSTRAINED,
    _early_bound,
    apply_custom_properties,
    apply_summary_info,
    check,
    log,
    run_build,
)
from _drawing_marks import DRAWN_BY
from _assembly import (
    assembly_title_properties,
    assert_component_placed,
    assert_free_dof_necessity,
    bore_axis_ref,
    check_no_interference,
    coincident_mate,
    collected_dof_specs,
    component_named_ref,
    component_transform,
    concentric_mate,
    delete_assembly_feature,
    distance_driver,
    named_ref,
    place_component,
    place_components_batch,
    reledger_to_solved,
    reset_dof_manifest,
    save_assembly_and_images,
    spin_driver,
    world_point,
    write_dof_manifest,
)
from _native_spring_contact import assert_assembly_spring_contacts
from _cwm import (
    component_constrained_status,
    component_distance_mate_flip,
    component_mate_count,
    component_mate_dump,
    copy_with_mates,
    ensure_component_distance_mate_flip,
    external_mate_rows,
    mates_with_owners,
    put_component_pose,
    resolve_entity,
)
from _transforms import (
    ROT_Y_180,
    ROT_Y_POS90,
    compose_rows,
    euler_from_rows,
    rows_from_euler,
)
from cone_pivot_post_installation import (
    CHANNEL_Z0,
    MECHANISM_Z_SHIFT,
)
from build_fulcrum_keeper import (
    CBORE_DEPTH_MM as KEEPER_CBORE_DEPTH,
    FOOT_H as KEEPER_FOOT_H,
)
from cylinder_gear_spec import ECCENTRICITY as CAM_ECC  # cam lobe throw (mm):

# imported, NOT copied, so the rod ring stays concentric with the cam when the
# throw is rescaled. A stale 5.08 hardcode (the pre-re-anchor throw) survived the
# OD-62.2 re-anchor that moved ECCENTRICITY to 3.06, mislocating the ring 2.02 mm
# south of the lobe -> the Ø30.8 bore dug into the Ø30.6 cam (20 x 171.67 mm^3).
from connecting_rod_spec import CENTER_DISTANCE as ROD_C2C  # ring centre ->

# rocker pin (imported, NOT copied -- the part and the assembly must agree on
# the link length or the J2 revolute drags the ring off the cam). Solved for
# the LEVEL rest pose: plumb rod from the level arm's pin down to the lobe-up
# phased cam centre.  Imported from the PURE-DATA spec, not the part builder:
# the builder's closure carries drawing prose, and pulling it here made every
# notes edit full-rebuild this assembly (codex #354).
from rocker_arm_spec import ROD_HOLE_X as ARM_ROD_HOLE_X  # rod pin x in the arm
from rocker_arm_spec import ROD_HOLE_Y as ARM_ROD_PIN_LOCAL_Y  # rod pin y: LOW

# in the strap (bottom-arc y + 5.3, ch14 fan photo), NOT mid-depth like the pivot
from rocker_arm_spec import PIVOT_MID_Y as ARM_PIVOT_LOCAL_Y  # 8.0: strap mid-depth

# at the pivot. Same imported-not-copied rule as CAM_ECC, and for the same
# reason: the rocker's rod-pin bore is NOT level with the pivot bore
# (ROD_HOLE_Y = 15.30 vs 8.0). ``channel_kinematics.arc_geometry`` must model
# the intrinsic 3.28 deg lever angle or the placed pin lands 7 mm off and the J2
# revolute drags the ring off the cam (the 0.9 deg/0.4 mm version of this slip
# already cost 20 x 20.27 mm^3 of cylinder-gear interference at the top level).
from rocker_arm_spec import CENTER_Y as ARM_ARC_CENTER_LOCAL_Y  # 816: arm-local arc

# centre above the bottom edge (= CURVE_RADIUS + ARM_DEPTH), shared with the
# offline error budget so the slide-arc height is never copied.
from channel_frame_geom import (  # machine-frame shaft axes + cam lock, shared with error_budget
    CAM_SHAFT_XY,
    CYLINDER_LOCK_PHASE_DEG,
    LEVER_FULCRUM_XY as FULCRUM,
    ROCKER_PIVOT_XY as PIVOT,
)

ASM_NAME = "channel"

# --- machine stations -------------------------------------------------------
import os  # noqa: E402

# Channels physically built. Default = machine.yaml channels.active_count, the
# BUILD-SPEED KNOB: drop it below 20 for debugging iterations, 20 = the full
# machine (see _config.active_count). CHANNEL_COUNT env still overrides for tests.
CHANNELS = int(os.environ.get("CHANNEL_COUNT", str(_config.active_count())))

Z0 = _config.machine("channels", "station_z0_mm")  # channel 0 gear plane (machine.yaml)
PITCH = _config.machine("channels", "station_pitch_mm")
if abs(Z0 - CHANNEL_Z0) > 1e-9:
    raise AssertionError(
        f"channels.station_z0_mm {Z0:g} != installation contract {CHANNEL_Z0:g}"
    )
ARM_MID_DZ = 0.8  # arm/bar/lever mid-planes at z_j + 0.8
CAM_DZ = -3.25  # end-for-end cylinder gear: cam / rod-ring plane at z_j - 3.25

# --- rocker bank ------------------------------------------------------------
# PIVOT (72.9, 253.8): the rocker pivot shaft axis -- imported from channel_frame_geom.
# True pivot->rod-pin lever: 127.37 along the arm (near the rod-side tip) PLUS
# the low pin's rise above the pivot bore (ROD_HOLE_Y 15.30 - 8.0 = 7.30).
# Length 127.583; the intrinsic lever angle beta (3.2813 deg above the arm's
# +X) must come OFF the solved pin azimuth to get the arm tilt (see
# ``channel_kinematics.arc_geometry``) -- at this lever the rise is 7.30 mm, so
# ignoring beta is no longer a 0.4 mm nudge but a 7 mm catastrophe.

# --- drive interface (default state) ----------------------------------------
# GEAR_PHASE_DEG, X_DRUM, Y_DRIVE: imported from channel_frame_geom (the
# drive-train's tooth-in-gap lock of every cylinder gear at Rz(+1.5), half the
# T120 pitch, and the drum shaft axis) -- NOT copied, so the offline error
# budget and both assemblies read one source. The integral cam (local (0,
# +CAM_ECC) -- lobe UP at notch-up, the cos-mode top of stroke per the ch14 end
# views) swings with the gear by GEAR_PHASE_DEG, so the rod ring rides the
# PHASED cam centre, not a point straight north of the arbor. The end-for-end
# gear flip reverses local Z only; local +Y and therefore this phased XY centre
# stay put. CAM_ECC is imported above.
X_DRUM, Y_DRIVE = CAM_SHAFT_XY
GEAR_PHASE_DEG = CYLINDER_LOCK_PHASE_DEG
RING_CENTER = (
    X_DRUM + CAM_ECC * math.sin(math.radians(GEAR_PHASE_DEG)),
    Y_DRIVE + CAM_ECC * math.cos(math.radians(GEAR_PHASE_DEG)),
)  # The drum sits at machine X_DRUM (crank side -X); y is the v2 casting's
# drive height 90.518 (gear_train.drive_axis_y_mm; build_drive_train_assembly
# derives and asserts it).
# ROD_C2C (imported from connecting_rod_spec.CENTER_DISTANCE, 163.1010):
# VERTICAL rod (ch30): every rod hangs PLUMB from the arm's rod-side tip onto
# its cam -- the pin (ROD_HOLE_X out from the mid-seesaw pivot) sits
# directly above the phased cam centre WITH THE ARM LEVEL (arm tilt 0: the ch14
# end views show the 0-crank tip row flat, and the GT rocker-corner
# triangulation lands the arm's rod-side end at machine x -60 -- the level-pose
# bottom-arc end predicts -59.9). Supersedes the 144.75 lobe-down closure at
# rest tilt -7.8158 deg, and the oblique 163.18/180.83 era before it.

# --- amplitude bars ---------------------------------------------------------
# Imported, NOT copied (same rule as CAM_ECC): the offline error budget reads
# amplitude_bar_spec for the bar's rigid-link length and notch-roof contact,
# so a copy here could drift from what check:budget certifies.
from amplitude_bar_spec import (  # noqa: E402
    BAR_WIDTH,  # 6.35 square section
    TOP_PIN_Y as BAR_TOP_PIN_Y,  # 801.95
)

# --- lever bank -------------------------------------------------------------
# FULCRUM (199.9, 1061.4): the lever fulcrum shaft axis -- imported from channel_frame_geom.
# The lever's two transfer arms -- imported, NOT copied, for the budget's sake
# (channel_lever_spec is what error_budget.nominal() reads).
from channel_lever_spec import (  # noqa: E402
    BAR_PIN_X as LEVER_BAR_PIN_X,  # 127.0, fulcrum -> bar-pin c2c, 5"
)

# the lever bank ends at x ~ -30 in the ch. 30 front view and the 32 mm
# springs must reach the summing plate at x ~ -22..-27)
LEVER_TAB_HALF = 3.0  # spring hole sits in the lever's 6.0-tall end tab
LEVER_THICKNESS = 3.0

# --- supports / mounts ------------------------------------------------------
SUPPORT_APEX_Y = 228.6
CHANNEL_BANK_REAR_SHIFT = MECHANISM_Z_SHIFT
# Rocker pivot brackets (pivot-bracket, 2026-09): symmetric about the 20-
# station arm stack's mid-plane, PIVOT_BRACKET_OFF either side -- ear faces
# 6.7 clear of the outermost arms, feet inside the rocker-arm-support's
# +-88.9 top (it is the only stand; the old south "A-frame" is gone).
_STACK_MID_Z = Z0 + ARM_MID_DZ + 19 * PITCH / 2.0  # 3.83 (the full machine)
PIVOT_BRACKET_OFF = 78.0
PIVOT_BRACKET_Z = (_STACK_MID_Z - PIVOT_BRACKET_OFF, _STACK_MID_Z + PIVOT_BRACKET_OFF)
PIVOT_SHAFT_Z = _STACK_MID_Z  # the 170 shaft spans -81.2..88.8: 4 past each ear
RAIL_TOP_Y = 1036.2  # new top-frame casting top face (was 1040.7; the rederive
# dropped the rail top 4.5 -- the ball-mount seats and the whole fulcrum chain
# follow)
FULCRUM_SHAFT_Z = CHANNEL_BANK_REAR_SHIFT
from fulcrum_shaft_spec import SHAFT_LENGTH as FULCRUM_SHAFT_LENGTH  # noqa: E402

FULCRUM_SHAFT_HALF = FULCRUM_SHAFT_LENGTH / 2.0  # 91.0; ends at 3.088 -+ 91
# Part +X (outboard) -> machine +Z for the rear keeper; ROT_Y_POS90 maps
# +X -> machine -Z for the flipped front keeper.
ROT_Y_NEG90 = [[0.0, 0.0, 1.0], [0.0, 1.0, 0.0], [-1.0, 0.0, 0.0]]
# Fulcrum end keepers (MHA-120) replace the baluster lever pair (the ch17
# p.40 / ch30 p008 black shaft-END brackets). The keeper's ball centre sits
# KEEPER_BALL_TO_END inboard of each shaft end, so the Ø6.35 end floats
# inside its Ø6.5 ball bore with the standard 0.15 diametral clearance.
KEEPER_BALL_TO_END = 2.25
KEEPER_Z_OFF = FULCRUM_SHAFT_HALF - KEEPER_BALL_TO_END  # 88.75 off centre
# Foot screws (frame-side-screw MHA-117): the keeper pad centre is 14.75
# inboard of its ball centre -> z = FULCRUM_SHAFT_Z +- 74.0. The under-head
# plane is derived from the keeper foot and its exact flush counterbore; the
# screws thread the top-frame's tapped #8-32 holes (build_top_frame.py).
KEEPER_SCREW_Z_OFF = KEEPER_Z_OFF - 14.75  # 74.0
KEEPER_SCREW_SEAT_H = KEEPER_FOOT_H - KEEPER_CBORE_DEPTH

# --- purchased channel springs and retained lower anchors ------------------
from _spring import build_spring  # noqa: E402
import channel_lever_spec  # noqa: E402
import channel_spring_stock_geom as spring_stock  # noqa: E402
import spring_mount_geom as spring_mounts  # noqa: E402
import summing_lever_spec  # noqa: E402
from stock_anchor_geom import ANCHOR_9489T111  # noqa: E402

# Bushing OD radii (for the concentric "rides the shaft" seat): the bushing OD
# face is the unambiguous concentric reference -- it is the only geometry at this
# radius in the inter-channel gap (the shaft is Ø6.35, the OD Ø10/Ø12).
from _hole_spec import blind_cut_dia_mm  # noqa: E402
from rocker_arm_spec import HUB_DIA as ROCKER_HUB_DIA, HUB_LENGTH as ROCKER_HUB_LENGTH  # noqa: E402
from channel_lever_spec import HUB_LENGTH as LEVER_HUB_LENGTH  # noqa: E402
from build_pivot_bracket import FOOT_H as PIVOT_BRACKET_FOOT_H  # noqa: E402

IDENTITY = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]


def rot_z_rows(deg: float) -> list[list[float]]:
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [[c, s, 0.0], [-s, c, 0.0], [0.0, 0.0, 1.0]]


def z_station(j: int) -> float:
    return Z0 + PITCH * j


# --- mate scheme (validated single-channel probe) ---------------------------
# Both rocker-pivot and lever-fulcrum shafts ride O6.35 bores.
SHAFT_R = 6.35 / 2.0
# Off-pivot bore locals (mm, part frame) used by the spin drivers + world_point.
ROCKER_ROD_BORE_LOCAL = [
    ARM_ROD_HOLE_X,
    ARM_ROD_PIN_LOCAL_Y,
    0.0,
]  # rocker Axis2 (rod pin)
ROD_STRAP_BORE_LOCAL = [0.0, 0.0, 0.0]  # rod Axis1 (cam ring centre = origin)
ROD_PIN_BORE_LOCAL = [0.0, ROD_C2C, 0.0]  # rod Axis2 (rocker pin = swing pivot)
LEVER_BAR_PIN_BORE_LOCAL = [LEVER_BAR_PIN_X, 0.0, 0.0]  # lever Axis2 (bar pin)
BAR_TOP_PIN_LOCAL = [
    BAR_WIDTH / 2.0,
    BAR_TOP_PIN_Y,
    BAR_WIDTH / 2.0,
]  # bar Axis1 (swing pivot; 808.3 - 6.35)
BAR_FOOT_LOCAL = [
    BAR_WIDTH / 2.0,
    0.0,
    BAR_WIDTH / 2.0,
]  # bar Axis2 (foot, ~802 mm arm)

# --- CopyWithMates2 slice replication (PR #220 probes -> production) ---------
# A channel's 4 moving parts + their 9 mates are one repeatable SLICE: author
# it once per amplitude value (the seed), then replicate every same-amplitude
# channel with ONE native CopyWithMates2 call (~1-2 s) instead of re-authoring
# (~12-20 s of per-mate solves). Contract + pinned rules live in _cwm.py.
CHAIN_PARTS = ("rocker-arm", "connecting-rod", "amplitude-bar", "channel-lever")
# Every part a slice mate can reference, for owner classification (anything
# else -- root planes -- maps to "ROOT" in mates_with_owners).
_CWM_PREFIXES = set(CHAIN_PARTS) | {
    "pivot-shaft",
    "fulcrum-shaft",
}


def _copied_chain_instances(adapter: Any, j: int) -> dict[str, str]:
    """The chain instances channel ``j``'s CopyWithMates2 created.

    Named DETERMINISTICALLY rather than discovered by diffing the component
    list. Every channel -- authored seed or copy -- contributes exactly one
    instance of each chain part, in channel order, so channel ``j`` owns
    ``f"{part}-{j + 1}"``. Verified against the built assembly (all four parts,
    20 instances, contiguous 1..20) and the same idiom the drive-train cylinder
    ladder already relies on (``f"cylinder-gear-{j + 1}"``).

    This replaced a before/after ``component_names`` diff that cost ~3.0 s PER
    COPY -- ~100 s over the 18 copies, 12% of the channel build. The diff could
    not be made cheaper: of its ~1.5 s per scan, ``GetComponents(True)`` alone
    measured ~1.0 s, so the scan had to go rather than shrink. Targeted lookups
    measured ~10 ms each.

    Fails loud in BOTH directions, which is what the diff's
    "unexpected new component" check bought: the expected instance must EXIST
    (else the copy dropped a part), and the NEXT one must NOT (else the copy
    created extra instances, or the numbering rule this rests on has broken --
    either way the caller must not silently mate the wrong components).

    ONE span around the whole loop, not one per lookup: eight near-instant
    ``GetComponentByName`` leaves per copy would be 144 over the 18 copies,
    the per-item trace flood AGENTS.md rules out. The aggregate lands as
    attributes, and a failure names its own component in the raised error.
    """
    with _telemetry.span("cwm.copied_instances", channel=j) as csp:
        asm = _early_bound(adapter.currentModel, "IAssemblyDoc")
        comps: dict[str, str] = {}
        for part in CHAIN_PARTS:
            name = f"{part}-{j + 1}"
            if asm.GetComponentByName(name) is None:
                raise RuntimeError(
                    f"ch{j:02d} copy: expected instance {name!r} is absent -- the"
                    f" copy did not create its {part}, or channel instances are no"
                    " longer numbered one-per-channel in channel order"
                )
            extra = f"{part}-{j + 2}"
            if asm.GetComponentByName(extra) is not None:
                raise RuntimeError(
                    f"ch{j:02d} copy: unexpected instance {extra!r} already exists"
                    f" -- the copy created more than one {part}, or the"
                    " one-instance-per-channel numbering rule has broken"
                )
            comps[part] = name
        csp.set_attribute("components", len(comps))
        csp.set_attribute("lookups", 2 * len(CHAIN_PARTS))
    return comps


# The free-build slice: J1 radial+axial, J2 coaxial+axial, J4 radial+axial,
# J3 radial+axial, J5 = 9 mates, of which 3 are EXTERNAL (J1 radial on the
# pivot-shaft, J1a axial dim to the previous rocker -- the ONLY external dim --
# and J4 radial on the fulcrum-shaft). A mate-scheme change moves these:
# update them consciously, the slot audit below fails loud.
SLICE_MATES = 9
SLICE_EXTERNAL = 3
# Debug instrumentation for the copy path: per-part pose readbacks around the
# pose landing + PNG snapshots of the model state (screenshot-first debugging).
_CWM_DEBUG = bool(os.environ.get("HARMONIC_CWM_DEBUG"))


async def _debug_png(adapter: Any, tag: str) -> None:
    """Export front + isometric PNGs of the CURRENT model state under
    ``cad/out/png/cwm-debug/`` (``HARMONIC_CWM_DEBUG=1`` only)."""
    if not _CWM_DEBUG:
        return
    from _common import OUT_PNG

    out = OUT_PNG / "cwm-debug"
    out.mkdir(parents=True, exist_ok=True)
    for view in ("front", "isometric"):
        path = (out / f"{tag}_{view}.png").resolve()
        await adapter.export_image(
            {
                "file_path": str(path),
                "format_type": "png",
                "width": 1600,
                "height": 1000,
                "view_orientation": view,
            }
        )
        log(f"  DEBUG png -> {path}")


def _org(adapter, name: str) -> list[float]:
    """A component's current origin (mm) in the assembly frame."""
    a = component_transform(adapter, name)
    return [a[9] * 1000.0, a[10] * 1000.0, a[11] * 1000.0]


async def _locate_to_datum(adapter, name: str) -> None:
    """Locate a grounded structural part to the machine datum planes by three
    orthogonal plane-distance mates -- the semantic replacement for an explicit
    fix on a free-space part with no contact partner (the #110 frame-column
    idiom). Three orthogonal plane pairs fully define the body: each pins one
    translation and, by forcing the planes parallel, the rotations.

    The part is inserted axis-aligned (IDENTITY parts -- shafts, ball mounts),
    so its principal planes map same-name to the assembly planes (Right->X,
    Top->Y, Front->Z). The live origin (read post-mirror) gives the three
    distances, so it is mirror-agnostic; coord 0 degenerates to a coincident.
    (The fixed measured spring bank is GROUNDED at its complete insert
    transforms instead, and the bushings are patterned; see the bank blocks in
    build().)
    """
    o = _org(adapter, name)
    pairs = (
        ("Right Plane", "Right Plane", o[0], "x"),
        ("Top Plane", "Top Plane", o[1], "y"),
        ("Front Plane", "Front Plane", o[2], "z"),
    )
    for part_plane, asm_plane, coord, axis in pairs:
        part_ref = named_ref(f"{part_plane}@{name}", "PLANE")
        asm_ref = named_ref(asm_plane, "PLANE")
        if abs(coord) < 1e-6:
            await coincident_mate(
                adapter,
                part_ref,
                asm_ref,
                label=f"{name} datum {axis}=0 ({part_plane}<->{asm_plane})",
                verify=(name, o),
            )
            continue
        await distance_driver(
            adapter,
            part_ref,
            asm_ref,
            coord,
            label=f"{name} datum {axis} d={abs(coord):.2f}",
            verify=(name, o),
        )


async def _revolute(
    adapter,
    comp: str,
    axis_a,
    axis_b,
    *,
    concentric: bool,
    off_axis_name: str,
    off_axis_local: list[float],
    pivot_xy: tuple[float, float],
    label: str,
    axial: tuple = ("datum",),
    free_spin: str | None = None,
    pin_spin: bool = True,
) -> Any:
    """Build one revolute joint pinned to its on-solution pose.

    ``concentric`` selects the radial mate kind: a cylindrical-face ↔ named-axis
    pair is *concentric* (shaft OD vs bore), two named axes are *coincident*
    (collinear lines = coaxial; AddMate5 rejects concentric on two axes). Then
    the axial (Z) seat, and a ``spin_driver`` on an off-pivot bore pins the
    residual spin -> fully defined, on-target.

    ``axial`` chooses the Z seat (the #110 "chain off a physical neighbor, not the
    global datum" idiom):

    * ``("datum",)`` -- distance from the part's mid-plane to the assembly Front
      datum (= ``|tgt[2]|``). The single global Z anchor (channel 0's rocker).
    * ``("coincident", sibling)`` -- coincident mid-plane to an already-placed
      sibling sharing this channel's plane (the lever onto the rocker).
    * ``("distance", neighbor, d)`` -- distance ``d`` from the part's mid-plane to
      a NEIGHBOR part's Front plane (each rocker j>=1 onto the pivot-bushing in
      the gap below it), so Z chains part->part instead of part->global datum.

    ``free_spin`` (a key) makes the spin a freed operational DOF (the rocker
    swing): recorded into the DOF manifest, not authored. ``None`` keeps it a
    hard pin. ``pin_spin=False`` skips the spin driver entirely -- the caller
    couples the residual spin through another mate (the channel lever's spin is
    closed by the J5 foot-on-arc coupling, not a pin). Returns the spin mate
    dict, or ``None`` when the spin was skipped.
    """
    tgt = _org(adapter, comp)
    # Capture the off-axis (spin) target at the PLACED design pose, BEFORE the
    # radial/axial mates run. Measuring it afterwards freezes whatever sub-mm
    # pose the mate solve drifted to. Each part is inserted on its exact mirrored
    # transform, so the design pose IS the on-solution target.
    off_design = world_point(adapter, comp, off_axis_local)
    radial = concentric_mate if concentric else coincident_mate
    await radial(adapter, axis_a, axis_b, label=f"{label} radial", verify=(comp, tgt))
    part_plane = named_ref(f"Front Plane@{comp}", "PLANE")
    kind = axial[0]
    if kind == "datum":
        await distance_driver(
            adapter,
            part_plane,
            named_ref("Front Plane", "PLANE"),
            tgt[2],
            label=f"{label} axial d={abs(tgt[2]):.2f}",
            verify=(comp, tgt),
        )
    elif kind == "coincident":
        await coincident_mate(
            adapter,
            part_plane,
            named_ref(f"Front Plane@{axial[1]}", "PLANE"),
            label=f"{label} axial coincident mid-plane <- {axial[1]}",
            verify=(comp, tgt),
        )
    elif kind == "distance":
        await distance_driver(
            adapter,
            part_plane,
            named_ref(f"Front Plane@{axial[1]}", "PLANE"),
            axial[2],
            label=f"{label} axial d={abs(axial[2]):.2f} <- neighbor {axial[1]}",
            verify=(comp, tgt),
        )
    else:
        raise RuntimeError(f"_revolute: unknown axial spec {axial!r}")
    if not pin_spin:
        return None
    # ``free_spin`` (a key) records the spin into the DOF manifest instead of
    # authoring it -- the rocker swing stays free. ``None`` keeps it a hard pin.
    spin = await spin_driver(
        adapter,
        named_ref(f"{off_axis_name}@{comp}", "AXIS"),
        pivot_xy,
        (off_design[0], off_design[1]),
        label=f"{label} spin -> {off_design[0]:.1f},{off_design[1]:.1f}",
        verify=(comp, tgt),
        free_dof_key=free_spin,
    )
    return spin


def _assert_spring_mount(
    pose: spring_mounts.SpringPose,
    amplitude: float,
    *,
    state: Literal["catalog_seed", "native_seated"],
) -> None:
    """Check real mount clearances; require analytic bore tangency only for seeds."""
    if state not in ("catalog_seed", "native_seated"):
        raise ValueError(f"unknown stock spring mount state {state!r}")
    hole_x, hole_y = channel_kinematics.spring_hole_xy(amplitude)
    ux, uy = pose.axis_xy
    wire_r = spring_stock.WIRE_DIA_MM / 2.0
    inner_r = spring_stock.COIL_ID_MM / 2.0
    hole_r = blind_cut_dia_mm(channel_lever_spec.SPRING_EYE_HOLE_SPEC) / 2.0
    edge_height = math.sqrt(inner_r**2 - (LEVER_THICKNESS / 2.0) ** 2)
    drop = math.hypot(hole_x - pose.upper_eye_xy[0], hole_y - pose.upper_eye_xy[1])
    bore_margin = hole_r + edge_height - drop
    phi = math.radians(channel_kinematics.solve_state(amplitude)["lever_tilt"])
    along_normal = ux * math.sin(phi) + uy * math.cos(phi)
    across_normal = uy * math.sin(phi) - ux * math.cos(phi)
    under_lever = (
        (drop + edge_height) * along_normal
        - wire_r * abs(across_normal)
        - LEVER_TAB_HALF
    )
    if (state == "catalog_seed" and abs(bore_margin) > 1e-6) or under_lever < 0.1:
        raise RuntimeError(
            f"stock spring upper hook: loaded bore margin {bore_margin:.6f}, "
            f"under-lever clearance {under_lever:.3f} mm"
        )

    anchor = ANCHOR_9489T111
    tap = summing_lever_spec.HOLE_SPEC
    if tap.kind != "tapped" or tap.size != anchor.thread_size:
        raise RuntimeError("channel anchor requires its matching native through tap")
    top = spring_mounts.PLATE_TOP_Y
    bottom = top - summing_lever_spec.PLATE_T
    anchor_y = spring_mounts.CHANNEL_ANCHOR_XY[1]
    thread_top = anchor_y + anchor.thread_start_y_mm
    thread_bottom = anchor_y + anchor.shank_end_y_mm
    engagement = min(top, thread_top) - max(bottom, thread_bottom)
    if engagement < summing_lever_spec.PLATE_T - 1e-6:
        raise RuntimeError(f"channel anchor only engages {engagement:.3f} mm of plate")
    spring_bottom = (
        pose.lower_eye_xy[1] - uy * spring_stock.COIL_MEAN_RADIUS_MM - wire_r
    )
    if spring_bottom - top < 0.3:
        raise RuntimeError("stock spring lower hook enters the summing plate")
    spring_stock.check_length_mm(pose.length_mm)
    log(
        f"stock spring mount: inside length {pose.length_mm:.4f} mm, "
        f"thread engagement {engagement:.3f} mm, tail {bottom - thread_bottom:.3f} mm"
    )


async def _prepare_native_spring_specs(adapter, amplitudes: list[float]) -> list[dict]:
    """Load fixed measured seats and build one native variant per amplitude.

    Every lookup completes before the first COM build so an unsupported preset
    fails without placing or rebuilding any spring. Variant indices retain the
    amplitude preset's first-occurrence order.
    """
    unique_amplitudes = list(dict.fromkeys(amplitudes))
    seats_by_amplitude = {
        amplitude: settled_spring_seats.channel_seat(amplitude)
        for amplitude in unique_amplitudes
    }
    by_amplitude: dict[float, dict] = {}
    for amplitude in unique_amplitudes:
        seat = seats_by_amplitude[amplitude]
        pose = seat.pose
        spring_stock.check_length_mm(pose.length_mm)
        if spring_mounts.channel_force_n(pose.length_mm) > float(
            _config.parts("channel-spring-installed")["maximum_load_n"]
        ):
            raise RuntimeError("settled channel spring exceeds catalog load")
        variant_index = len(by_amplitude)
        part = "channel-spring-installed"
        variant = f"{part}-stretch{variant_index:02d}"
        await build_spring(adapter, variant, pose.length_mm, views=[])
        adapter.swApp.CloseDoc(
            _early_bound(adapter.currentModel, "IModelDoc2").GetTitle()
        )
        by_amplitude[amplitude] = {
            "pose": pose,
            "variant_index": variant_index,
        }
        _telemetry.event(
            "spring.channel_fixed_seat",
            amplitude_mm=amplitude,
            inside_length_mm=pose.length_mm,
            variant_index=variant_index,
        )
    return [by_amplitude[amplitude] for amplitude in amplitudes]


async def build(adapter) -> dict[str, str]:
    # The amplitude-bar station per channel IS the Fourier coefficient a_j
    # (channels.yaml amplitude_mm, the square-wave preset). solve_state(a_j)
    # repositions that channel's bar + lever; a_j = 0 is the neutral pose. The
    # neutral state still anchors the amplitude-independent rocker/rod and uses
    # the first fixed calibrated spring variant (stretch00).
    amplitudes = _config.amplitudes()
    if any(a < 0.0 for a in amplitudes):
        raise RuntimeError(
            "amplitude_mm must be >= 0 (the lifting side keeps the foot clear of"
            f" the pivot shaft); got {amplitudes}"
        )
    state = channel_kinematics.solve_state(0.0)
    log(
        "neutral state: arm tilt %.3f deg, rod tilt %.3f deg, pin (%.2f, %.2f),"
        % (state["arm_tilt"], state["rod_tilt"], state["pin_x"], state["pin_y"])
    )
    log(
        "  bar contact %.3f, bar bottom %.3f, bar pin y %.3f, lever tilt %.3f deg"
        % (
            state["contact_y"],
            state["bar_bottom"],
            state["bar_pin_y"],
            state["lever_tilt"],
        )
    )
    log(
        "amplitude preset: a_j stations (mm) = %s"
        % ", ".join(f"{a:.2f}" for a in amplitudes)
    )

    _assert_spring_mount(spring_mounts.CHANNEL_NOMINAL_POSE, 0.0, state="catalog_seed")

    # Bushing clearance under the bar foot at d = 0 (geometry gate).
    bar_clearance = state["bar_bottom"] - PIVOT[1]
    if bar_clearance < 5.5:
        raise RuntimeError(f"bar passes only {bar_clearance:.2f} above the shaft")

    # Fixed measured supplier-surface seats own the installed poses. Build each
    # calibrated length exactly once, retaining first-occurrence stretch names.
    spring_specs = await _prepare_native_spring_specs(adapter, amplitudes)
    # Keep the generated variant family explicit for the static build graph.
    for spec in spring_specs:
        spec["part"] = f"channel-spring-installed-stretch{spec['variant_index']:02d}"

    # Reset the free-DOF manifest buffer before any *_driver(free_dof_key=...)
    # call: each freed DOF is recorded (never authored) and persisted below.
    reset_dof_manifest()
    check("create_assembly", await adapter.create_assembly())

    # Shafts. The pivot-shaft is inserted FIRST, so SolidWorks auto-fixes it as
    # the assembly seed (ground=False -- the one allowed fixed component, the
    # #110 idiom). The fulcrum-shaft is free-space structure with no contact
    # partner, so it is datum-located (three orthogonal plane distances), not
    # fixed. The shaft axes (machine frame, crank at -X) anchor the
    # rocker/lever concentrics.
    await place_component(
        adapter,
        "pivot-shaft",
        [PIVOT[0], PIVOT[1], PIVOT_SHAFT_Z],
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
        label="pivot-shaft (rocker, seed)",
    )
    fulcrum = await place_component(
        adapter,
        "fulcrum-shaft",
        [FULCRUM[0], FULCRUM[1], FULCRUM_SHAFT_Z],
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
        label="fulcrum-shaft (lever bank)",
    )
    await _locate_to_datum(adapter, fulcrum)
    pivot_w = (PIVOT[0], PIVOT[1])  # (72.9, 253.8) machine world
    fulc_w = (FULCRUM[0], FULCRUM[1])  # (199.9, 1061.4) machine world
    pivot_od = [pivot_w[0] + SHAFT_R, pivot_w[1], 0.0]
    fulc_od = [fulc_w[0] + SHAFT_R, fulc_w[1], 0.0]

    # Pivot brackets. Free-space structure with no contact partner inside
    # this subassembly, so each is datum-located (three orthogonal plane
    # distances), not fixed -- the #110 idiom. Both seat on the rocker-arm-
    # support's top (y 228.6). The part is an L (2026-09-02, ch14 p.27/28):
    # its foot runs from the ear toward local +Z, INBOARD under the outer
    # arms (the support leaves only 4 mm of apex outboard of the north ear),
    # so the south bracket (inboard = +Z) is IDENTITY and the north one is
    # turned Ry180 about its own origin -- the bore stays on the pivot axis
    # at (PIVOT[0], 253.8, mount_z) exactly, the foot flips to -Z.
    for mount_z in PIVOT_BRACKET_Z:
        inboard_pos_z = mount_z < _STACK_MID_Z
        mount = await place_component(
            adapter,
            "pivot-bracket",
            [PIVOT[0], SUPPORT_APEX_Y, mount_z],
            [0.0, 0.0, 0.0] if inboard_pos_z else [0.0, 180.0, 0.0],
            IDENTITY if inboard_pos_z else ROT_Y_180,
            ground=False,
            label=f"pivot-bracket rocker z{mount_z:+.0f}",
        )
        await _locate_to_datum(adapter, mount)
    # Fulcrum end keepers (MHA-120): the black shaft-END brackets of the
    # ch17 p.40 closeup -- an upright lug sockets a ball on each shaft end,
    # the foot screwed down to the rail top face. Part +X points outboard
    # along the shaft: the rear (+Z) keeper maps part X -> machine +Z
    # (Ry -90), the front keeper is the same part flipped (Ry +90). The
    # keepers are GROUNDED at their computed transform (the cosmetic-bank
    # idiom below): _locate_to_datum assumes IDENTITY parts whose planes map
    # same-name, which a Ry+-90 part breaks. The IDENTITY screws are
    # datum-located like the mounts they accompany.
    for sign, euler, rows in (
        (1.0, [0.0, -90.0, 0.0], ROT_Y_NEG90),
        (-1.0, [0.0, 90.0, 0.0], ROT_Y_POS90),
    ):
        await place_component(
            adapter,
            "fulcrum-keeper",
            [FULCRUM[0], RAIL_TOP_Y, FULCRUM_SHAFT_Z + sign * KEEPER_Z_OFF],
            euler,
            rows,
            ground=True,
            label=f"fulcrum-keeper z{sign * KEEPER_Z_OFF:+.0f}",
        )
        screw = await place_component(
            adapter,
            "frame-side-screw",
            [
                FULCRUM[0],
                RAIL_TOP_Y + KEEPER_SCREW_SEAT_H,
                FULCRUM_SHAFT_Z + sign * KEEPER_SCREW_Z_OFF,
            ],
            [0.0, 0.0, 0.0],
            IDENTITY,
            ground=False,
            label=f"keeper foot screw z{sign * KEEPER_SCREW_Z_OFF:+.0f}",
        )
        await _locate_to_datum(adapter, screw)

    # No spacer bushings (2026-09-02): the rocker arms and channel levers
    # carry integral hubs one PITCH long, so each channel's rocker takes its
    # axial (Z) seat as a PITCH distance off the PREVIOUS channel's rocker
    # mid-plane (hub face on hub face, the #110 neighbour idiom), and the
    # lever rides coincident to its own rocker. rocker_by_channel[j] is the
    # rocker instance every later neighbour seat refers to.
    rocker_by_channel: dict[int, str] = {}
    if abs(ROCKER_HUB_LENGTH - PITCH) > 1e-6 or abs(LEVER_HUB_LENGTH - PITCH) > 1e-6:
        raise RuntimeError("hub lengths must equal the station pitch")
    _hub_bottom = PIVOT[1] - ROCKER_HUB_DIA / 2.0
    _foot_top = SUPPORT_APEX_Y + PIVOT_BRACKET_FOOT_H
    if _hub_bottom - _foot_top < 0.25:
        raise RuntimeError(
            f"rocker hubs (bottom {_hub_bottom:.2f}) reach the pivot-bracket feet"
            f" (top {_foot_top:.2f})"
        )

    # Per-channel chain: the four moving parts are inserted on-solution
    # (ground=False) and joined by revolutes whose spin/axial dims are the
    # per-channel suppressible drivers (see _revolute).
    # Rocker + rod are amplitude-independent (same tilt every channel); the bar
    # and lever are placed per channel from solve_state(a_j).
    # The rocker/rod/lever parts are modeled crank-side (+X); the machine puts
    # the crank at -X, so each picks up a fixed Ry(180) on top of its in-plane
    # Rz tilt -- the proper-rotation realisation of the pre-#151 z-plane mirror
    # (mirror_placement is gone). compose_rows(Rz(tilt), Ry180) IS that pose; the
    # matching Euler comes back via euler_from_rows for insert_component.
    arm_rows = compose_rows(rot_z_rows(state["arm_tilt"]), ROT_Y_180)
    rod_rows = compose_rows(rot_z_rows(state["rod_tilt"]), ROT_Y_180)
    t = math.radians(state["arm_tilt"])
    arm_origin_dx = ARM_PIVOT_LOCAL_Y * math.sin(t)  # -(0,8)*Rz offset
    arm_origin_dy = ARM_PIVOT_LOCAL_Y * math.cos(t)

    # The springs and the two bushing banks are grounded repeated structure, but
    # they are placed EXPLICITLY per channel (springs in the loop, bushings in
    # each inter-channel gap) rather than seeded once and replicated by a
    # LocalLinearPattern. The bushing banks are seed+pattern off the BankZ
    # reference axis (see the block above the loop); the springs and spring-hooks
    # are per-channel GROUNDED static parts with complete measured insert poses.
    # They have no operational DOF, while their actual final lower/upper contacts
    # are checked against the threaded hook and actual lever instances. The old
    # 7-mates-per-channel locate battery bought nothing but about 140 late-
    # assembly mate solves. Their specs are collected per channel and inserted
    # in one AddComponents3 + one FixComponent after the chain loops
    # (place_components_batch). The moving parts stay individual mated instances
    # so each channel articulates independently for the Motion study, but they
    # are not all authored one by one: only the seeds are. Same-amplitude channels
    # are replicated from their seed's slice by CopyWithMates2, with each copy
    # validated against the seed pose from the model.
    grounded_specs: list[dict[str, Any]] = []
    free_dof_keys: list[str] = []  # freed operational DOF recorded in the manifest

    async def _author_channel(j: int, st: dict[str, float]) -> dict[str, str]:
        """Author one channel's chain from scratch: place the 4 moving parts
        on-solution and join them with the 9-mate slice (J1/J2/J4/J3/J5).

        The SEED path: run for channel 0 (the single global Z anchor) and once
        per distinct amplitude value; every other channel is replicated from
        its amplitude group's seed by one CopyWithMates2 call (the dispatch
        loop below). Appends the channel's freed-DOF keys and returns the
        part -> instance map (the copyable slice)."""
        zj = z_station(j)
        z_mid = zj + ARM_MID_DZ
        # Bar rotated Ry(-90) (machine frame: local X slot -> +Z, local Z depth ->
        # -X, the mirror of the pre-#151 Ry(+90)) then swung by st['bar_tilt']
        # about Z. Lever gets the Ry(180) z-plane turn like the rocker/rod.
        bar_rows = rows_from_euler([st["bar_tilt"], -90.0, 0.0])
        lever_rows = compose_rows(rot_z_rows(st["lever_tilt"]), ROT_Y_180)

        rocker = await place_component(
            adapter,
            "rocker-arm",
            [PIVOT[0] - arm_origin_dx, PIVOT[1] - arm_origin_dy, z_mid],
            euler_from_rows(arm_rows),
            arm_rows,
            ground=False,
            label=f"rocker-arm ch{j:02d}",
        )
        rod = await place_component(
            adapter,
            "connecting-rod",
            [RING_CENTER[0], RING_CENTER[1], zj + CAM_DZ],
            euler_from_rows(rod_rows),
            rod_rows,
            ground=False,
            label=f"connecting-rod ch{j:02d}",
        )
        # Origin places the foot axis at (PIVOT[0] + a_j, bar_bottom) on the
        # machine +X lifting side; the swing keeps the foot on the arc.
        bar = await place_component(
            adapter,
            "amplitude-bar",
            [st["bar_origin_x"], st["bar_origin_y"], z_mid - BAR_WIDTH / 2.0],
            [st["bar_tilt"], -90.0, 0.0],
            bar_rows,
            ground=False,
            label=f"amplitude-bar ch{j:02d} a={amplitudes[j]:.2f}",
        )
        lever = await place_component(
            adapter,
            "channel-lever",
            [FULCRUM[0], FULCRUM[1], z_mid],
            euler_from_rows(lever_rows),
            lever_rows,
            ground=False,
            label=f"channel-lever ch{j:02d}",
        )

        # J1 rocker revolute (shaft OD ↔ pivot bore). Axial Z: the hubs stack
        # face to face from channel 0's rocker (integral hubs, 2026-09-02), so
        # rocker j sits j * PITCH off CHANNEL 0's rocker mid-plane -- always the
        # authored anchor, never a copied slice's own rocker: CopyWithMates2
        # re-binds any reference to a copied component onto the copy, so a
        # 'previous rocker' reference collapsed the first copy's seat onto
        # itself (swFeatureErrorMateIlldefine, 2026-09-02). Channel 0 is the
        # single global Z anchor. The spin is a freed DOF: recorded, not
        # authored, so the rocker swings about its pivot.
        axial = ("distance", rocker_by_channel[0], j * PITCH) if j >= 1 else ("datum",)
        await _revolute(
            adapter,
            rocker,
            bore_axis_ref(pivot_od),
            named_ref(f"Axis1@{rocker}", "AXIS"),
            concentric=True,
            off_axis_name="Axis2",
            off_axis_local=ROCKER_ROD_BORE_LOCAL,
            pivot_xy=pivot_w,
            label=f"J1 rocker ch{j:02d}",
            axial=axial,
            free_spin=f"rocker_angle_{j:02d}",
        )
        free_dof_keys.append(f"rocker_angle_{j:02d}")
        # J2 connecting-rod: a REAL revolute on the rocker's rod pin (request #2),
        # replacing the old design-pose pin to the global datums. The rod's pin
        # bore (Axis2@rod) is made coaxial with the rocker's rod bore (Axis2@rocker)
        # -- a coincident of two named axes (AddMate5 rejects concentric on axes);
        # a distance to the rocker's Front plane pins Z; and the swing about the
        # pin is a freed DOF (recorded on the rod's cam-ring bore Axis1@rod, not
        # authored) so the rod follows the rocker. NB the cam ring's external
        # journal (the cylinder-gear lobe) lives at the TOP level only; this
        # channel-level revolute lets the ring float there -- validated channel-only
        # for now (the ~0.39 mm lobe slack the old _pin_design_pose guarded is a
        # top-level concern, deferred).
        rod_tgt = _org(adapter, rod)
        rod_ring = world_point(adapter, rod, ROD_STRAP_BORE_LOCAL)
        rod_pin = world_point(adapter, rod, ROD_PIN_BORE_LOCAL)
        await coincident_mate(
            adapter,
            named_ref(f"Axis2@{rocker}", "AXIS"),
            named_ref(f"Axis2@{rod}", "AXIS"),
            label=f"J2 rod ch{j:02d} coaxial pin <- {rocker}",
            verify=(rod, rod_tgt),
        )
        await distance_driver(
            adapter,
            named_ref(f"Front Plane@{rod}", "PLANE"),
            named_ref(f"Front Plane@{rocker}", "PLANE"),
            rod_tgt[2] - z_mid,
            label=f"J2 rod ch{j:02d} axial d={abs(rod_tgt[2] - z_mid):.2f} <- {rocker}",
            verify=(rod, rod_tgt),
        )
        await spin_driver(
            adapter,
            named_ref(f"Axis1@{rod}", "AXIS"),
            (rod_pin[0], rod_pin[1]),
            (rod_ring[0], rod_ring[1]),
            label=f"J2 rod ch{j:02d} swing -> ring {rod_ring[0]:.1f},{rod_ring[1]:.1f}",
            verify=(rod, rod_tgt),
            free_dof_key=f"rod_swing_{j:02d}",
        )
        free_dof_keys.append(f"rod_swing_{j:02d}")
        # J4 lever revolute (fulcrum OD ↔ fulcrum bore). The lever shares the
        # channel mid-plane with the rocker (both mid-plane extruded, both at
        # z_mid), so its axial seat is a COINCIDENT mid-plane mate to the
        # rocker's Front plane -- not a bare distance to the datum. NO spin pin
        # (pin_spin=False): the lever's rotation is CLOSED by the J5 foot-on-arc
        # coupling below (like the magnifier wheel's yoke -- coupled, not
        # separately freed): swing the rocker and the bar + lever follow.
        await _revolute(
            adapter,
            lever,
            bore_axis_ref(fulc_od),
            named_ref(f"Axis1@{lever}", "AXIS"),
            concentric=True,
            off_axis_name="Axis2",
            off_axis_local=LEVER_BAR_PIN_BORE_LOCAL,
            pivot_xy=fulc_w,
            label=f"J4 lever ch{j:02d}",
            axial=("coincident", rocker),
            pin_spin=False,
        )
        # J3 bar — the amplitude-setting joint (p0). A real revolute hinges the
        # bar at its top pin (Axis1@bar) coaxial with the lever's bar pin
        # (Axis2@lever). The bar length equals the rocker's R800 arc radius, so
        # the top pin rides the arc CENTRE while the foot rides the R800 arc
        # itself (build_rocker_arm docstring): swinging the bar about the top pin
        # slides the foot ALONG the arc, and that swing IS the amplitude DOF
        # (±88 mm seesaw, ch.15). The swing is a freed DOF whose drive spec —
        # a distance from the foot axis (Axis2@bar) to the assembly Right
        # Plane, i.e. the foot's X = the amplitude position — is recorded into
        # the DOF manifest at today's solved contact, so a transient replay
        # reproduces `rest` bit-exact. The spec MUST stay a part↔root-plane
        # distance (NOT part↔part): the motion study's driver classifier only
        # recognises dims that reference one real part + the sub root. This is
        # the explicit form of the generic foot-X spin_driver the other
        # revolutes use.
        bar_tgt = _org(adapter, bar)
        foot = world_point(adapter, bar, BAR_FOOT_LOCAL)
        amplitude = foot[0] - pivot_w[0]  # foot X relative to the rocker pivot
        await coincident_mate(
            adapter,
            named_ref(f"Axis2@{lever}", "AXIS"),
            named_ref(f"Axis1@{bar}", "AXIS"),
            label=f"J3 bar ch{j:02d} radial (top-pin hinge)",
            verify=(bar, bar_tgt),
        )
        # Axial seat: the bar straddles the rocker symmetrically, so its named
        # MidWidth plane (local x = BarWidth/2) lands on the channel mid-plane.
        # Seat it COINCIDENT to the rocker's Front (mid-)plane -- the semantic
        # "bar mid-plane on the rocker mid-plane" contact -- not a bare distance.
        await coincident_mate(
            adapter,
            named_ref(f"MidWidth@{bar}", "PLANE"),
            named_ref(f"Front Plane@{rocker}", "PLANE"),
            label=f"J3 bar ch{j:02d} axial coincident mid-plane <- {rocker}",
            verify=(bar, bar_tgt),
        )
        # The foot-X driver is a freed operational DOF (``free_dof_key``): the
        # bar swings about its top pin = slides the foot along the rocker arc,
        # the amplitude DOF (request #1). It stays a part<->root-plane distance
        # (the motion study's driver classifier only recognises one real part +
        # the sub root), so it is NOT chained off a neighbour like the rocker
        # axial.
        await distance_driver(
            adapter,
            named_ref(f"Axis2@{bar}", "AXIS"),
            named_ref("Right Plane", "PLANE"),
            foot[0],  # SIGNED: distance_driver abs()es the mate value but needs
            # the sign to seed the seat side (which side of Right Plane the foot
            # is on) so the recorded spec carries the correct flip for replay
            label=f"J3 bar ch{j:02d} AMPLITUDE drive foot-X={foot[0]:.2f} (amp {amplitude:+.1f})",
            verify=(bar, bar_tgt),
            free_dof_key=f"bar_amplitude_{j:02d}",
        )
        free_dof_keys.append(f"bar_amplitude_{j:02d}")
        # J5 foot-on-arc COUPLING: the bar's foot axis (Axis2@bar) is held at
        # its as-solved radius from the rocker's R800 arc-centre axis
        # (Axis3@rocker) -- two Z-parallel axes, ONE unambiguous distance (the
        # lever-wire stand-off idiom, no far-side flip). This is the slot
        # contact that closes the rocker -> bar -> lever chain: swinging the
        # rocker moves the arc centre, the foot follows at its radius, and the
        # top-pin hinge turns the lever -- so the lever is COUPLED (magnifier-
        # wheel style), not separately freed, and the free count stays 3 per
        # channel. The radius is the design pose's own measure (per channel:
        # the foot-notch contact offset rotates with the amplitude tilt), so
        # the mate authors residual-free; it tracks the true roof-on-arc
        # contact to first order (offset ~5 mm over R800 -- sub-visible).
        # Analytic radius, all in the machine frame: the foot X is the +X-side
        # station PIVOT[0] + a_j (matching solve_state's fx), the arc centre and
        # bar_bottom come straight from the machine-frame solver (#151: was a
        # pre-mirror PIVOT[0] - a_j mixed against the post-mirror foot readback).
        arc_c = world_point(adapter, rocker, [0.0, ARM_ARC_CENTER_LOCAL_Y, 0.0])
        foot_r = math.hypot(foot[0] - arc_c[0], foot[1] - arc_c[1])
        want_r = math.hypot(
            (PIVOT[0] + amplitudes[j]) - channel_kinematics.ARC["acx"],
            st["bar_bottom"] - channel_kinematics.ARC["acy"],
        )
        if abs(foot_r - want_r) > 1e-3:
            raise RuntimeError(
                f"ch{j:02d}: measured foot->arc-centre radius {foot_r:.4f} != "
                f"analytic {want_r:.4f} -- the placed pose drifted off solve_state"
            )
        await distance_driver(
            adapter,
            named_ref(f"Axis2@{bar}", "AXIS"),
            named_ref(f"Axis3@{rocker}", "AXIS"),
            foot_r,
            label=f"J5 bar-foot on rocker arc ch{j:02d} r={foot_r:.2f}",
            verify=(bar, bar_tgt),
        )
        return {
            "rocker-arm": rocker,
            "connecting-rod": rod,
            "amplitude-bar": bar,
            "channel-lever": lever,
        }

    def _slice_slots(seed_comps: dict[str, str], seed_j: int) -> dict[str, Any]:
        """Measure the seed slice's CopyWithMates2 slot layout: the array
        length, the J1a dim's Values slot index, the seed parts' as-authored
        transform arrays (the pose targets every copy is landed on) and their
        per-part mate counts (the copy-completeness reference).

        One mates_with_owners read serves both the slice-mate count tripwire
        and the external slot mapping. Every expectation is asserted LOUD: a
        mate-scheme change that silently mis-slots the ladder value would
        re-value a live copied dim to 0.0 (the _cwm contract), so drift here
        must fail the build, not mis-place a channel."""
        slice_instances = set(seed_comps.values())
        rows = [
            r
            for r in mates_with_owners(adapter, _CWM_PREFIXES)
            if r["instances"] & slice_instances
        ]
        if len(rows) != SLICE_MATES:
            raise RuntimeError(
                f"seed slice carries {len(rows)} mates, expected {SLICE_MATES}"
                " -- the mate scheme changed; re-derive SLICE_MATES/"
                f"SLICE_EXTERNAL: {[r['name'] for r in rows]}"
            )
        ext = external_mate_rows(rows, slice_instances)
        if len(ext) != SLICE_EXTERNAL:
            raise RuntimeError(
                f"seed slice exposes {len(ext)} external mates, expected"
                f" {SLICE_EXTERNAL}: {[r['name'] for r in ext]}"
            )
        dims = [(i, r) for i, r in enumerate(ext) if r["type"] == "MateDistanceDim"]
        if len(dims) != 1:
            raise RuntimeError(
                "seed slice must expose exactly ONE external dim (the J1a"
                f" rocker axial); got {[(i, r['name']) for i, r in dims]}"
            )
        slot, dim = dims[0]
        if dim["owners"] != frozenset({"rocker-arm"}):
            raise RuntimeError(
                f"external dim {dim['name']!r} is not the J1a rocker->rocker"
                f" axial (owners {sorted(dim['owners'])})"
            )
        if abs(dim["mm"] - seed_j * PITCH) > 0.01:
            raise RuntimeError(
                f"J1a seed value {dim['mm']:.3f} mm != {seed_j} x PITCH"
                f" {seed_j * PITCH:.3f} -- the axial anchor moved"
            )
        # The seed's J1a side is CARRIED to each copy (flips[dim_slot]) via the
        # Repeat=false + own-bushing idiom, so any seed side is honoured; the
        # authored neighbour idiom (#110) produces flip=False. No always-positive
        # ladder is needed anymore (see the copy site + _cwm.py module doc).
        arrays = {
            p: list(component_transform(adapter, n)) for p, n in seed_comps.items()
        }
        mate_counts = {
            p: component_mate_count(adapter, n) for p, n in seed_comps.items()
        }
        # The seed's drive targets (all Z-independent), for the transient
        # drivers that land each copy on the design pose.
        return {
            "n": len(rows),
            "dim_slot": slot,
            "dim_flip": bool(dim["flip"]),
            "rod_axial_flip": component_distance_mate_flip(
                adapter,
                seed_comps["connecting-rod"],
                abs(CAM_DZ - ARM_MID_DZ),
            ),
            "arrays": arrays,
            "mate_counts": mate_counts,
            "rocker_off": world_point(
                adapter, seed_comps["rocker-arm"], ROCKER_ROD_BORE_LOCAL
            ),
            "rod_ring": world_point(
                adapter, seed_comps["connecting-rod"], ROD_STRAP_BORE_LOCAL
            ),
            "rod_pin": world_point(
                adapter, seed_comps["connecting-rod"], ROD_PIN_BORE_LOCAL
            ),
            "foot": world_point(adapter, seed_comps["amplitude-bar"], BAR_FOOT_LOCAL),
        }

    # Per-channel chain, seed-and-replicate (PR #220 -> production). Channel 0
    # is always authored (it is the single global Z anchor -- its J1a is a
    # ROOT-datum distance at a negative station, so it is never a copy seed).
    # The first channel >= 1 of each amplitude value is authored as that group's
    # SEED (its J1a anchors PITCH off the previous channel's rocker); every later
    # same-amplitude channel is ONE CopyWithMates2 of the seed's 4-part slice
    # with the J1a slot re-pointed (Repeat=false) to ITS previous rocker at the
    # same local PITCH. With the current all-neutral preset that is 2 authored
    # + (CHANNELS-2) copies; a restored square preset degrades gracefully (each
    # distinct a_j authors once).
    seed_by_amp: dict[float, tuple[int, dict[str, str]]] = {}
    slots_by_seed: dict[int, tuple[int, int, dict[str, list[float]]]] = {}
    copied: list[dict[str, Any]] = []
    for j in range(CHANNELS):
        st = channel_kinematics.solve_state(
            amplitudes[j]
        )  # this channel's bar/lever pose
        amp_key = round(amplitudes[j], 6)
        seed = seed_by_amp.get(amp_key) if j >= 2 else None
        if seed is None:
            comps = await _author_channel(j, st)
            rocker_by_channel[j] = comps["rocker-arm"]
            if j >= 1:
                seed_by_amp[amp_key] = (j, comps)
            continue
        seed_j, seed_comps = seed
        if seed_j not in slots_by_seed:
            slots_by_seed[seed_j] = _slice_slots(seed_comps, seed_j)
        slice_info = slots_by_seed[seed_j]
        n_slice, dim_slot = slice_info["n"], slice_info["dim_slot"]
        seed_arrays = slice_info["arrays"]
        # Re-point ONLY the J1a slot to channel 0's rocker (the hub-stack anchor;
        # Repeat=false + NewEntityToMateTo) at j * PITCH -- exactly
        # the authored #110 neighbour idiom -- honouring the seed's side via
        # flips[dim_slot]. The other two external slots (J1 radial on the shared
        # pivot-shaft) keep the seed's references (Repeat=true), the measured
        # mixed-array idiom. This drops the old cumulative always-positive ladder
        # off the seed's bushing (see _cwm.py module doc).
        prev_rocker = rocker_by_channel[0]  # the hub-stack anchor (authored channel 0)
        values = [0.0] * n_slice
        values[dim_slot] = (j * PITCH) / 1000.0
        repeat = [True] * n_slice
        repeat[dim_slot] = False
        new_ents: list = [None] * n_slice
        new_ents[dim_slot] = resolve_entity(
            adapter, named_ref(f"Front Plane@{prev_rocker}", "PLANE")
        )
        flips = [False] * n_slice
        flips[dim_slot] = slice_info["dim_flip"]
        copy_with_mates(
            adapter,
            [seed_comps[p] for p in CHAIN_PARTS],
            n_slice,
            values,
            flips=flips,
            repeat=repeat,
            new_entities=new_ents,
        )
        comps = _copied_chain_instances(adapter, j)
        rocker_by_channel[j] = comps["rocker-arm"]
        ensure_component_distance_mate_flip(
            adapter,
            comps["connecting-rod"],
            abs(CAM_DZ - ARM_MID_DZ),
            slice_info["rod_axial_flip"],
        )
        # Land the copy on its DESIGN pose by pinning its 3 operational DOF
        # with TRANSIENT drivers, then deleting them. The chain's DOF are
        # genuinely free, so the copied mates pin the copy only up to the
        # free manifold -- and the copy carries a solver-state ATTRACTOR: a
        # deterministic wrong pose (first run: rocker ~17 deg swung; every
        # rebuild: ~97 deg) that the solver returns to from ANY start.
        # Measured dead ends (2026-07-09): raw Transform2 puts land every
        # part exactly on target but the next solve reverts them, and
        # SetTransformAndSolve3 with the whole chain already consistent at
        # target STILL reverts -- only a real DRIVEN solve rewrites the
        # copied mates' stored state. So drive the copy exactly like an
        # authored channel (same helpers, same labels/flip seeding, readback-
        # verified), which anchors the stored state at the design pose, then
        # delete the drivers -- the DOF end up free, later rebuilds hold.
        targets: dict[str, list[float]] = {}
        dz_m = (j - seed_j) * PITCH / 1000.0
        for part in CHAIN_PARTS:
            target = list(seed_arrays[part])
            target[11] += dz_m
            targets[part] = target
        copied.append(
            {
                "j": j,
                "seed_j": seed_j,
                "comps": comps,
                "targets": targets,
                "slice_info": slice_info,
                "prev_rocker": prev_rocker,
            }
        )

    # Copy every free chain first, then settle their solver-state attractors in
    # one post-copy phase. Driving each copy immediately made every later
    # CopyWithMates2 addition re-wander already-settled free siblings; the v0.20.0
    # trace spent 173 s across those repeated pose-drive spans. Re-putting the
    # complete copied bank before each transient driver keeps every still-free
    # chain on its design branch while the current channel is committed.
    def _put_all_copies() -> None:
        for rec in copied:
            for part in CHAIN_PARTS:
                put_component_pose(adapter, rec["comps"][part], rec["targets"][part])

    for rec in copied:
        j = rec["j"]
        seed_j = rec["seed_j"]
        comps = rec["comps"]
        targets = rec["targets"]
        slice_info = rec["slice_info"]
        rocker_c = comps["rocker-arm"]
        rod_c = comps["connecting-rod"]
        bar_c = comps["amplitude-bar"]

        def _tgt_mm(part: str) -> list[float]:
            a = targets[part]
            return [a[9] * 1000.0, a[10] * 1000.0, a[11] * 1000.0]

        off = slice_info["rocker_off"]
        ring = slice_info["rod_ring"]
        pin = slice_info["rod_pin"]
        foot = slice_info["foot"]
        try:
            with _telemetry.span("cwm.pose_drive", channel=j):
                drives: list[str] = []
                _put_all_copies()
                mate = await spin_driver(
                    adapter,
                    component_named_ref(rocker_c, "Axis2"),
                    pivot_w,
                    (off[0], off[1]),
                    label=(f"J1 rocker ch{j:02d} spin -> {off[0]:.1f},{off[1]:.1f}"),
                    verify=(rocker_c, _tgt_mm("rocker-arm")),
                )
                drives.append(mate["name"])
                _put_all_copies()
                mate = await distance_driver(
                    adapter,
                    component_named_ref(bar_c, "Axis2"),
                    named_ref("Right Plane", "PLANE"),
                    foot[0],
                    label=(
                        f"J3 bar ch{j:02d} AMPLITUDE drive"
                        f" foot-X={foot[0]:.2f} (amp"
                        f" {amplitudes[j]:+.1f})"
                    ),
                    verify=(bar_c, _tgt_mm("amplitude-bar")),
                )
                drives.append(mate["name"])
                _put_all_copies()
                if _CWM_DEBUG and j == copied[0]["j"]:
                    seed_comps = seed_by_amp[round(amplitudes[j], 6)][1]
                    for part in CHAIN_PARTS:
                        log(
                            f"  DEBUG pre-J2 mates seed {seed_comps[part]}: "
                            f"{component_mate_dump(adapter, seed_comps[part])}"
                        )
                        log(
                            f"  DEBUG pre-J2 mates copy {comps[part]}: "
                            f"{component_mate_dump(adapter, comps[part])}"
                        )
                mate = await spin_driver(
                    adapter,
                    component_named_ref(rod_c, "Axis1"),
                    (pin[0], pin[1]),
                    (ring[0], ring[1]),
                    label=(
                        f"J2 rod ch{j:02d} swing -> ring {ring[0]:.1f},{ring[1]:.1f}"
                    ),
                    verify=(rod_c, _tgt_mm("connecting-rod")),
                )
                drives.append(mate["name"])
                for name in reversed(drives):
                    delete_assembly_feature(adapter, name)
        except Exception:
            if _CWM_DEBUG:
                for part in CHAIN_PARTS:
                    a = component_transform(adapter, comps[part])
                    t = targets[part]
                    log(
                        f"  DEBUG ch{j:02d} {comps[part]} at-drive-fail pose:"
                        f" ({a[9] * 1000:.2f}, {a[10] * 1000:.2f},"
                        f" {a[11] * 1000:.2f})"
                        f" xrow ({a[0]:+.3f},{a[1]:+.3f},{a[2]:+.3f}) target"
                        f" ({t[9] * 1000:.2f}, {t[10] * 1000:.2f},"
                        f" {t[11] * 1000:.2f})"
                    )
                await _debug_png(adapter, f"drive-fail-ch{j:02d}")
            raise
        log(
            f"ch{j:02d} <- CopyWithMates2 of ch{seed_j:02d}"
            f" (J1a {j * PITCH:.2f} mm <- channel 0 rocker"
            f" {rec['prev_rocker']}, driven to pose + freed)"
        )

    # End-state validation of the replicated channels: ONE closing solve, then
    # prove each copy from the model (the CopyWithMates2 return value LIES):
    # pose = the seed's pose translated down-spine; per-part mate count = the
    # seed's (a native-typing slip silently DROPS mates); per-part
    # constrained status = under-constrained like the seed's (an unsolvable
    # copied mate drives its components to over/no-solution WITHOUT moving
    # anything, so a pose read alone misses it). All three read the model via
    # per-component calls -- never the MateGroup tree walk, which measured
    # ~20 s per pass here. Then record each copy's freed-DOF drive specs and
    # re-anchor the pose ledger to the validated solved poses (the copies
    # were never place_component'd, so the ledger must learn them for the
    # final assert_pose_ledger sweep in save_assembly_and_images).
    if copied:
        model = adapter.currentModel
        if not bool(adapter._attempt(lambda: model.EditRebuild3(), default=False)):
            raise RuntimeError("closing EditRebuild3 after slice replication failed")
        await _debug_png(adapter, "post-rebuild")
        if _CWM_DEBUG:
            for rec in copied:
                seed_comps = seed_by_amp[round(amplitudes[rec["j"]], 6)][1]
                for part in CHAIN_PARTS:
                    log(
                        f"  DEBUG mates seed {seed_comps[part]}: "
                        f"{component_mate_dump(adapter, seed_comps[part])}"
                    )
                    log(
                        f"  DEBUG mates copy {rec['comps'][part]}: "
                        f"{component_mate_dump(adapter, rec['comps'][part])}"
                    )
        for rec in copied:
            seed_counts = slots_by_seed[rec["seed_j"]]["mate_counts"]
            for part in CHAIN_PARTS:
                name = rec["comps"][part]
                a = rec["targets"][part]
                assert_component_placed(
                    adapter,
                    name,
                    [a[9] * 1000.0, a[10] * 1000.0, a[11] * 1000.0],
                    [list(a[0:3]), list(a[3:6]), list(a[6:9])],
                )
                got = component_mate_count(adapter, name)
                if got != seed_counts[part]:
                    raise RuntimeError(
                        f"ch{rec['j']:02d} {name}: {got} mates, seed has"
                        f" {seed_counts[part]} -- the copy dropped mates"
                    )
                status = component_constrained_status(adapter, name)
                if status != UNDER_CONSTRAINED:
                    raise RuntimeError(
                        f"ch{rec['j']:02d} {name}: constrained status"
                        f" {status}, expected under-constrained"
                        f" ({UNDER_CONSTRAINED}) -- a copied mate is"
                        " unsolvable or over-defining"
                    )
        for rec in copied:
            j = rec["j"]
            rocker = rec["comps"]["rocker-arm"]
            rod = rec["comps"]["connecting-rod"]
            bar = rec["comps"]["amplitude-bar"]
            for name in rec["comps"].values():
                reledger_to_solved(adapter, name)
            # Record the copy's 3 freed-DOF drive specs -- pure recording
            # (free_dof_key never authors) + cheap COM transform reads on the
            # validated copies. Labels mirror the authored path VERBATIM so
            # the flip ledger (_flip_sig) resolves the same signatures.
            tgt = _org(adapter, rocker)
            off = world_point(adapter, rocker, ROCKER_ROD_BORE_LOCAL)
            await spin_driver(
                adapter,
                component_named_ref(rocker, "Axis2"),
                pivot_w,
                (off[0], off[1]),
                label=f"J1 rocker ch{j:02d} spin -> {off[0]:.1f},{off[1]:.1f}",
                verify=(rocker, tgt),
                free_dof_key=f"rocker_angle_{j:02d}",
            )
            free_dof_keys.append(f"rocker_angle_{j:02d}")
            tgt = _org(adapter, rod)
            ring = world_point(adapter, rod, ROD_STRAP_BORE_LOCAL)
            pin = world_point(adapter, rod, ROD_PIN_BORE_LOCAL)
            await spin_driver(
                adapter,
                component_named_ref(rod, "Axis1"),
                (pin[0], pin[1]),
                (ring[0], ring[1]),
                label=f"J2 rod ch{j:02d} swing -> ring {ring[0]:.1f},{ring[1]:.1f}",
                verify=(rod, tgt),
                free_dof_key=f"rod_swing_{j:02d}",
            )
            free_dof_keys.append(f"rod_swing_{j:02d}")
            tgt = _org(adapter, bar)
            foot = world_point(adapter, bar, BAR_FOOT_LOCAL)
            amplitude = foot[0] - pivot_w[0]
            await distance_driver(
                adapter,
                component_named_ref(bar, "Axis2"),
                named_ref("Right Plane", "PLANE"),
                foot[0],
                label=(
                    f"J3 bar ch{j:02d} AMPLITUDE drive foot-X={foot[0]:.2f}"
                    f" (amp {amplitude:+.1f})"
                ),
                verify=(bar, tgt),
                free_dof_key=f"bar_amplitude_{j:02d}",
            )
            free_dof_keys.append(f"bar_amplitude_{j:02d}")

    for j in range(CHANNELS):
        z_mid = z_station(j) + ARM_MID_DZ
        # The supplier frame has its origin at mid-length and coil axis +X.
        # These grounded components use the complete fixed measured seat.
        spec = spring_specs[j]
        pose = spec["pose"]
        _assert_spring_mount(
            spring_mounts.channel_pose(amplitudes[j]),
            amplitudes[j],
            state="catalog_seed",
        )
        _assert_spring_mount(pose, amplitudes[j], state="native_seated")
        grounded_specs.append(
            {
                "part": spec["part"],
                "position": [*pose.centre_xy, z_mid],
                "rotation": [0.0, 0.0, 0.0],
                "rows": pose.rotation_rows,
                "label": f"channel-spring ch{j:02d} inside length={pose.length_mm:.4f}",
            }
        )
        grounded_specs.append(
            {
                "part": "spring-hook",
                "position": [*spring_mounts.CHANNEL_ANCHOR_XY, z_mid],
                "rotation": [0.0, 0.0, 0.0],
                "rows": IDENTITY,
                "label": f"spring-hook ch{j:02d} direct threaded seat",
            }
        )

    # Insert the fixed measured spring bank in one AddComponents3 call. The
    # persisted native gate re-enumerates every actual top-level occurrence by
    # source family and station; no ephemeral builder names carry that proof.
    for spec in grounded_specs:
        spec["ground"] = True
    await place_components_batch(
        adapter, grounded_specs, label="fixed measured spring bank (grounded)"
    )

    # Free kinematic model: the per-channel operational DOF (rocker swing +
    # rod follow + bar amplitude) are FREE -- their drivers were recorded into
    # the DOF manifest, never authored. Necessity gate: the freed DOF are
    # genuinely free, one family per DOF (the aggregate count alone cannot
    # tell a pinned family from a free one, codex 2026-07-04); the channel
    # lever must read under-constrained WITH the chain (the J5 coupling closes
    # it off the rocker; a frozen lever means the coupling died).
    n_recorded = len(collected_dof_specs())
    if n_recorded != len(free_dof_keys):
        raise RuntimeError(
            f"recorded {n_recorded} free-DOF spec(s) but expected "
            f"{len(free_dof_keys)} ({sorted(free_dof_keys)}) -- a free_dof_key "
            "was dropped or double-counted"
        )
    assert_free_dof_necessity(
        adapter,
        len(free_dof_keys),
        required_stems=(
            "rocker-arm",
            "connecting-rod",
            "amplitude-bar",
            "channel-lever",
        ),
    )
    write_dof_manifest(ASM_NAME)
    check_no_interference(adapter)
    # Title-block identity for the assembly drawing (draw_channel_assembly.py):
    # assembly_title_properties supplies the Title/Generator and TOL_* cells
    # finalize_drawing requires without consulting the part registry;
    # released component drawing (the BOM has no material/finish columns).
    apply_custom_properties(
        adapter,
        {
            **assembly_title_properties(ASM_NAME),
            # MHA-A## = assembly-drawing ids, beside the parts' MHA-### range
            # (a longer number overflows the DWG. NO. title-block cell).
            "Number": "MHA-A02",
            "Revision Description": "Initial release",
            "Material": "SEE COMPONENT DRAWINGS",
            "Material Specification": "SEE COMPONENT DRAWINGS",
            "Finish": "SEE COMPONENT DRAWINGS",
            "Quantity": "1",
            "Drawn By": DRAWN_BY,
        },
    )
    # The PART cell resolves the document summary Title; "channel assembly" (not
    # the bare stem) so the sheet identifies itself as an assembly drawing.
    apply_summary_info(adapter, title=f"{ASM_NAME} assembly")
    return await save_assembly_and_images(
        adapter,
        ASM_NAME,
        native_contact_check=functools.partial(
            assert_assembly_spring_contacts,
            channel_count=CHANNELS,
        ),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
