r"""Reproduction script: channel subassembly (book ch. 13-17; 20 channels).

The complete 20-channel motion chain between the drive train and the
output: connecting rods riding the integral cams, the rocker-arm seesaw
bank on its pivot shaft, the amplitude bars running UP the spine, and the
top-lever bank on its fulcrum shaft with the channel springs hanging from
the lever tips, each caught at the plate by a little open hook fastener.
164 components:

Coordinates are machine frame (#151: crank at machine -X, output side -Z;
the M6.8 mirror layer is gone).

* pivot-shaft x1 (rocker bank at (72.9, 253.8), along Z, centred z 0)
  + fulcrum-shaft x1 (lever bank at (199.9, 1065.9), 182 long - the
  228.6 shaft clipped the west columns at top level, M6.5)
* pivot-ball-mount x4 (rocker pair: north on the rocker-support apex at
  (72.9, 228.6, +101.6), south on the A-FRAME clevis saddle at
  (72.9, 228.6, -111) - M6.5 photo audit: there is no south frustum,
  the front stand is the rocker-arm-support's transgear-A-frame leg
  (frame.SLDASM) whose ears flank this mount's O16 base; lever pair on the top-frame west rail,
  seats (199.9, 1040.7, +/-85) - z 85 keeps the O16 base clear of the
  O35 corner-boss bores)
* rocker-arm x20, pivot-bushing x19, connecting-rod x20,
  amplitude-bar x20, channel-lever x20, lever-bushing x19,
  channel-spring-installed x20 (M6.4: the stretched in-machine spring --
  the free 32 mm part stays for the ch. 17 table-top inset),
  spring-hook x20 (the open J-hook fastener seating each spring's bottom
  eye in the plate bore -- the spring no longer threads the plate itself)

Default mechanism state (DIMENSIONS.md "Channel & top-frame layout"):
cylinder-gear notches +Y (cosine alignment), integral cam lobes +Y (UP,
the top of the stroke -- the ch14 end views show the 0-crank tip row
dead level at the stroke top), rod rings concentric on the cams at
(-54.474, 113.437, z_j + 3.3) - the cam centre carries the gears'
+1.5 deg tooth-phase rotation. Everything downstream is SOLVED here, not
hard-coded: the rod-pin point is the intersection of the r 127.58 lever
circle about the pivot with the r ROD_C2C circle about the ring centre
(arm tilt 0 -- the arms rest LEVEL, the 3.28 deg pin azimuth equals the
tapered-strap lever angle; rod tilt 0 -- the rod hangs PLUMB from the
arm's rod-side tip onto its cam, ch30 photos + ch14 end views);
the bar rests its foot-notch roof on the tilted arm's top-edge arc
(contact at the bar's +X edge, machine frame); the bar's top pin height
tilts the levers (~ +0.36 deg); the spring's top eye hangs 3.37 below the
lever spring hole so its ring threads the O4 hole without touching (margins
asserted > 0.1); the bottom eye now sits just ABOVE the plate (no longer
threading it) on the arm of a spring-hook fastener whose shank seats in the
plate's O2.0 bore (at z_j + 0.8, on the spring axis, one arm-offset +X of the eye)
-- the plate itself (the summing-lever) lives in summing.SLDASM, checked at
the top level.

Orientation notes: the amplitude bar is rotated 90 deg about its long
axis (Ry(-90), machine frame) so its end slots and O2 top pin hole run
across Z, straddling the 2.5 arm / 3.0 lever; the spring's end-hook ring
lies perpendicular to the lever face. Channel
stations: z_j = -67.1 + 7.0565 j, arm/bar/lever mid-planes at z_j + 0.8,
cam/rod plane z_j + 3.3 (rod tip strap face-flush against the arm).

Mated-DOF strategy: nothing is grounded except the pivot-shaft seed (the
lone SolidWorks auto-fix). Every other part is held by SEMANTIC, contact-
faithful mates -- the radial fit at each real interface is a concentric/
coincident pivot, and the axial Z is a coincident mid-plane wherever parts
share a channel slice:
  * rocker/lever concentric on the shaft OD; rod/bar coincident axis-to-
    axis on the named bore axes (the revolute radials);
  * bushings concentric on the shaft they ride (+ anti-spin parallel);
  * the rocker is each channel's Z ANCHOR (axial distance to the datum);
    the lever and the amplitude bar are seated COINCIDENT to the rocker's
    mid-plane (lever Front plane / bar MidWidth plane), so a channel's
    parts share ONE Z reference;
  * free-space structure with no in-subassembly contact partner (fulcrum-
    shaft, ball mounts, springs, spring-hooks) is datum-located by three
    orthogonal plane distances (the #110 frame-column idiom).
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
OWN gap bushing (Repeat=false + NewEntityToMateTo) at the local PITCH/2
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

import math
import sys
from typing import Any

import _config
import _telemetry
from _common import (
    UNDER_CONSTRAINED,
    check,
    log,
    run_build,
)
from _assembly import (
    assert_component_placed,
    assert_free_dof_necessity,
    bore_axis_ref,
    check_no_interference,
    coincident_mate,
    collected_dof_specs,
    component_names,
    component_transform,
    concentric_mate,
    delete_assembly_feature,
    distance_driver,
    named_ref,
    parallel_mate,
    place_component,
    place_components_batch,
    reledger_to_solved,
    reset_dof_manifest,
    save_assembly_and_images,
    spin_driver,
    world_point,
    write_dof_manifest,
)
from _cwm import (
    component_constrained_status,
    component_mate_count,
    component_mate_dump,
    copy_with_mates,
    external_mate_rows,
    mates_with_owners,
    put_component_pose,
    resolve_entity,
)
from _transforms import ROT_Y_180, compose_rows, euler_from_rows, rows_from_euler
from solidworks_mcp.adapters.base import (
    ComponentLinearPatternParameters,
    CreateAxisParameters,
)
from build_cylinder_gear import ECCENTRICITY as CAM_ECC  # cam lobe throw (mm):
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
# (ROD_HOLE_Y = 15.30 vs 8.0). _arc_geometry must model that intrinsic 3.28 deg
# lever angle or the placed pin lands 7 mm off the solved point and the J2
# revolute drags the ring off the cam (the 0.9 deg/0.4 mm version of this slip
# already cost 20 x 20.27 mm^3 of cylinder-gear interference at the top level).

ASM_NAME = "channel"

# --- machine stations -------------------------------------------------------
import os  # noqa: E402

# Channels physically built. Default = machine.yaml channels.active_count, the
# BUILD-SPEED KNOB: drop it below 20 for debugging iterations, 20 = the full
# machine (see _config.active_count). CHANNEL_COUNT env still overrides for tests.
CHANNELS = int(os.environ.get("CHANNEL_COUNT", str(_config.active_count())))

Z0 = _config.machine("channels", "station_z0_mm")  # channel 0 gear plane (machine.yaml)
PITCH = _config.machine("channels", "station_pitch_mm")
ARM_MID_DZ = 0.8  # arm/bar/lever mid-planes at z_j + 0.8
CAM_DZ = 3.3  # cam / rod-ring mid-plane at z_j + 3.3

# --- rocker bank ------------------------------------------------------------
PIVOT = (72.9, 253.8)  # rocker pivot shaft axis (x, y); machine frame (crank at -X)
# True pivot->rod-pin lever: 127.37 along the arm (near the rod-side tip) PLUS
# the low pin's rise above the pivot bore (ROD_HOLE_Y 15.30 - 8.0 = 7.30).
# Length 127.583; the intrinsic lever angle beta (3.2813 deg above the arm's
# +X) must come OFF the solved pin azimuth to get the arm tilt (see
# _arc_geometry) -- at this lever the rise is 7.30 mm, so ignoring beta is no
# longer a 0.4 mm nudge but a 7 mm catastrophe.
_LEVER_DX = ARM_ROD_HOLE_X  # 127.3738
_LEVER_DY = ARM_ROD_PIN_LOCAL_Y - ARM_PIVOT_LOCAL_Y  # 7.3025
ARM_ROD_LEVER = math.hypot(_LEVER_DX, _LEVER_DY)  # 127.5830
ARM_LEVER_BETA_DEG = math.degrees(math.atan2(_LEVER_DY, _LEVER_DX))  # 3.2813
ARM_ARC_CENTER_LOCAL_Y = 816.0  # arm local arc centre above the bottom edge
ARM_TOP_RADIUS = 800.0

# --- drive interface (default state) ----------------------------------------
GEAR_PHASE_DEG = 1.5  # drive-train locks each cylinder gear at Rz(+1.5):
# half the T120 tooth pitch, so a TOOTH faces the cone mesh (see
# build_drive_train_assembly.py). The integral cam (local (0, +CAM_ECC) -- lobe
# UP at notch-up, the cos-mode top of stroke per the ch14 end views) swings
# with the gear by GEAR_PHASE_DEG, so the rod ring rides the PHASED cam
# centre, not a point straight north of the arbor. CAM_ECC is imported above.
RING_CENTER = (
    -(54.7 - CAM_ECC * math.sin(math.radians(GEAR_PHASE_DEG))),
    104.8 + CAM_ECC * math.cos(math.radians(GEAR_PHASE_DEG)),
)  # phased cam centre at ECC 8.64: machine (-54.474, 113.437). The drum sits at
# machine -54.7 (build_drive_train X_DRUM, crank side -X); y off the ch30 GT drive
# height 104.8 (was 126.8). MUST stay in sync with X_DRUM/Y_DRIVE.
# ROD_C2C (imported above from connecting_rod_spec.CENTER_DISTANCE, 147.6655):
# VERTICAL rod (ch30): every rod hangs PLUMB from the arm's rod-side tip onto
# its cam -- the pin (ROD_HOLE_X 127.3738 out from the mid-seesaw pivot) sits
# directly above the phased cam centre WITH THE ARM LEVEL (arm tilt 0: the ch14
# end views show the 0-crank tip row flat, and the GT rocker-corner
# triangulation lands the arm's rod-side end at machine x -60 -- the level-pose
# bottom-arc end predicts -59.9). Supersedes the 144.75 lobe-down closure at
# rest tilt -7.8158 deg, and the oblique 163.18/180.83 era before it.

# --- amplitude bars ---------------------------------------------------------
BAR_WIDTH = 6.35
BAR_LENGTH = 812.8
BAR_FOOT_NOTCH = 2.381
BAR_TOP_PIN_DROP = 6.35
# The bar foot-notch roof rests on the rocker's top-edge arc. In the legacy
# fix-all build the bar sat at the exact tangent (0-volume line contact,
# filtered as coincidence). Mated, the solver lands a sub-0.005 mm^3
# penetration sliver that trips the interference gate, so the foot is lifted
# a hairline above the arc (the documented "design a margin, not a tangent"
# pattern). The penetration sliver is only ~0.001 mm deep, so a 0.02 mm lift
# clears it with 20x margin; the lift cascades through the lever tilt into the
# spring eye, and the plate-threading loop margin (~0.11 mm) bounds it -- 0.02
# keeps that margin clear, 0.1 broke it.
BAR_CONTACT_GAP = _config.fit("cam_follower_contact", "contact_gap_mm")  # cad/config/tolerances.yaml

# --- lever bank -------------------------------------------------------------
FULCRUM = (199.9, 1065.9)  # lever fulcrum shaft axis (x, y); machine frame
LEVER_BAR_PIN_X = 127.0
LEVER_SPRING_X = 177.8  # 7" c2c; the 254 "2:1" guess is photo-refuted (M6.4 -
# the lever bank ends at x ~ -30 in the ch. 30 front view and the 32 mm
# springs must reach the summing plate at x ~ -22..-27)
LEVER_TAB_HALF = 3.0  # spring hole sits in the lever's 6.0-tall end tab
LEVER_THICKNESS = 3.0

# --- supports / mounts ------------------------------------------------------
SUPPORT_APEX_Y = 228.6
SUPPORT_Z = 81.5  # north mount, seated FULLY on the support: with the Ø13 ball
# its z-footprint [75.0, 88.0] clears the channel-19 amplitude bar (z 74.1) and
# stays inside the support north edge (z 88.9). Was 101.6 (cantilevered 12.7).
AFRAME_MOUNT_Z_ABS = 111.0  # south mount on the A-frame clevis (frame.SLDASM)
# Pivot shaft placed off-centre so its north end lands at the support edge
# (z +88.9) while the south end (z -114.3) still reaches the A-frame mount.
PIVOT_SHAFT_Z = -12.7  # = (88.9 - 114.3) / 2; the 203.2-long shaft spans ±101.6
RAIL_TOP_Y = 1040.7
LEVER_MOUNT_Z = 85.0  # clears the top-frame boss bores (DIMENSIONS.md)

# --- spring (channel_spring_installed_spec) ---------------------------------
from _spring import COIL_BODY_LENGTH, build_spring  # noqa: E402
from channel_spring_installed_spec import (  # noqa: E402
    HOOK_LEAD as SPRING_HOOK_LEAD,  # 2.0 each end (no longer spans the plate)
    INSTALLED_BODY_LENGTH as SPRING_BASE_BODY,  # 61.98: the neutral installed body
    PLATE_EYE_Y,  # 996.54: bottom-eye y, ABOVE the plate on the hook arm
)

SPRING_BOTTOM_LEAD = SPRING_HOOK_LEAD
SPRING_TOP_LEAD = SPRING_HOOK_LEAD

SPRING_LOOP_R = 2.75  # = coil mean radius
SPRING_WIRE_DIA = 1.0
SPRING_EYE_DROP = 3.37  # top eye centre below the lever spring hole
SPRING_HOLE_DIA = 4.0  # build_channel_lever.py (O3 photo read enlarged: threading)

# --- spring-hook fastener (spring_hook_spec) --------------------------------
# A little open J-hook seats shank-up in each plate bore; its +X arm, presented
# just above the plate, threads the spring's bottom eye. So the shank sits one
# arm-offset -X of the (vertical) spring eye and the arm reaches back to it.
from spring_hook_spec import (  # noqa: E402
    ELBOW_R as HOOK_ELBOW_R,
    ROD_DIA as HOOK_ROD_DIA,
    ARM_RUN as HOOK_ARM_RUN,
    SHANK_RISE as HOOK_SHANK_RISE,
)

HOOK_ARM_OFFSET_X = HOOK_ELBOW_R + HOOK_ARM_RUN / 2.0  # 2.75: shank->arm-mid in +X
HOOK_ARM_HEIGHT = HOOK_SHANK_RISE + HOOK_ELBOW_R  # 9.1: shank base -> arm centreline

# Bushing OD radii (for the concentric "rides the shaft" seat): the bushing OD
# face is the unambiguous concentric reference -- it is the only geometry at this
# radius in the inter-channel gap (the shaft is Ø6.35, the OD Ø10/Ø12).
from build_pivot_bushing import OUTER_DIA as PIVOT_BUSHING_OD  # noqa: E402  (Ø10)
from build_lever_bushing import OUTER_DIA as LEVER_BUSHING_OD  # noqa: E402  (Ø12)

# --- summing-lever plate interface (build_summing_lever.py) ------------------
# The corrected .cs lever is a coplanar casting: the plate is mid-plane ON the
# pivot (knife line y=990), so its top is 992.54 -- 5.46 BELOW the old M6.4 998.
# The 20 channel springs were dropped to meet it (PLATE_EYE_Y, below) and so they
# elongate 5.46 against the fixed channel-lever tabs at 1063.65.
PLATE_TOP_Y = 992.54
PLATE_THICKNESS = 5.1
PLATE_HOLE_DIA = 2.0  # snug bore for the O1.4 hook shank (build_summing_lever.HOLE_DIA)

IDENTITY = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]


def rot_z_rows(deg: float) -> list[list[float]]:
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [[c, s, 0.0], [-s, c, 0.0], [0.0, 0.0, 1.0]]


def z_station(j: int) -> float:
    return Z0 + PITCH * j


def _verify_pattern_z(
    adapter, prefix: str, expected: list[float], label: str
) -> None:
    """Assert a patterned family's instances sit on the expected Z planes.

    A LocalLinearPattern's direction sense is taken from the reference entity;
    a flipped sense would mis-place the copies WITHOUT necessarily interfering
    (they can land in empty Z), so the interference gate alone cannot vouch for
    them. Read each instance's origin Z and compare the sorted set to the
    channel/gap planes.
    """
    got = sorted(
        component_transform(adapter, n)[11] * 1000.0
        for n in component_names(adapter)
        if n.rsplit("-", 1)[0] == prefix
    )
    want = sorted(expected)
    if len(got) != len(want):
        raise RuntimeError(
            f"{label}: {len(got)} instances, expected {len(want)}"
        )
    for g, w in zip(got, want):
        if abs(g - w) > 0.05:
            raise RuntimeError(
                f"{label}: instance at z={g:.2f} off plane z={w:.2f}"
                " -- pattern direction sense flipped?"
            )
    log(f"{label}: {len(got)} instances on-plane (z {got[0]:.1f}..{got[-1]:.1f})")


def _instance_at_z(adapter, prefix: str, z_mm: float) -> str:
    """Name of the ``prefix`` instance whose origin sits on the ``z_mm`` plane."""
    for n in component_names(adapter):
        if n.rsplit("-", 1)[0] != prefix:
            continue
        if abs(component_transform(adapter, n)[11] * 1000.0 - z_mm) < 0.05:
            return n
    raise RuntimeError(f"no {prefix} instance at z={z_mm:.2f}")


async def _pattern_bank(
    adapter, seed: str, prefix: str, axis_name: str, gap_planes: list[float],
) -> None:
    """Replicate a seated bank seed down the spine by a LocalLinearPattern.

    The direction reference is EXPLICIT reference geometry (the BankZ datum
    axis), not the shaft's cylindrical face -- the retired face pick left the
    direction SENSE to SolidWorks' inference, which flipped the bank to +Z at
    20 channels while resolving -Z at 3 (#8 era). An axis still fixes only
    the LINE, so the sense is verified against the gap planes
    (:func:`_verify_pattern_z`, fail loud) and, when flipped, the pattern is
    deleted and re-created with ``FlipDir1`` (``flip_direction``) --
    deterministic in at most two solves, never inference-trusting.
    """
    count = len(gap_planes)
    if count < 2:
        # One gap (CHANNELS == 2): the seated seed IS the whole bank; a
        # count=1 LocalLinearPattern is invalid/pointless (codex #219).
        _verify_pattern_z(adapter, prefix, gap_planes, f"{prefix} bank (seed only)")
        return
    # Flip seed TRUE: diag_pattern_sense (2026-07-09, 5/5 reps) measured the
    # Top∩Right axis pick resolving +Z deterministically, so FlipDir1=True
    # lands the copies down-spine in ONE solve; the untried value stays as
    # the verified retry (the same learn-the-seed philosophy as _FLIP_INVERT).
    attempts = (True, False)
    for attempt, flip in enumerate(attempts):
        tag = " (flip retry)" if attempt else ""
        feature = check(
            f"linear-pattern {prefix} x{count}{tag}",
            await adapter.pattern_components_linear(
                ComponentLinearPatternParameters(
                    components=[seed], count=count, spacing=PITCH,
                    direction_name=axis_name, flip_direction=flip,
                )
            ),
        )
        try:
            _verify_pattern_z(adapter, prefix, gap_planes, f"{prefix} pattern")
            return
        except RuntimeError as exc:
            if attempt == len(attempts) - 1:
                raise
            log(f"!! {prefix} pattern sense flipped -- deleting + flip retry ({exc})")
            delete_assembly_feature(adapter, feature.name)


# --- mate scheme (validated single-channel probe) ---------------------------
# Both rocker-pivot and lever-fulcrum shafts ride O6.35 bores.
SHAFT_R = 6.35 / 2.0
# Off-pivot bore locals (mm, part frame) used by the spin drivers + world_point.
ROCKER_ROD_BORE_LOCAL = [ARM_ROD_HOLE_X, ARM_ROD_PIN_LOCAL_Y, 0.0]  # rocker Axis2 (rod pin)
ROD_STRAP_BORE_LOCAL = [0.0, 0.0, 0.0]  # rod Axis1 (cam ring centre = origin)
ROD_PIN_BORE_LOCAL = [0.0, ROD_C2C, 0.0]  # rod Axis2 (rocker pin = swing pivot)
LEVER_BAR_PIN_BORE_LOCAL = [127.0, 0.0, 0.0]  # lever Axis2 (bar pin)
BAR_TOP_PIN_LOCAL = [3.175, 806.45, 3.175]  # bar Axis1 (swing pivot)
BAR_FOOT_LOCAL = [3.175, 0.0, 3.175]  # bar Axis2 (foot, ~806 mm arm)

# --- CopyWithMates2 slice replication (PR #220 probes -> production) ---------
# A channel's 4 moving parts + their 9 mates are one repeatable SLICE: author
# it once per amplitude value (the seed), then replicate every same-amplitude
# channel with ONE native CopyWithMates2 call (~1-2 s) instead of re-authoring
# (~12-20 s of per-mate solves). Contract + pinned rules live in _cwm.py.
CHAIN_PARTS = ("rocker-arm", "connecting-rod", "amplitude-bar", "channel-lever")
# Every part a slice mate can reference, for owner classification (anything
# else -- root planes -- maps to "ROOT" in mates_with_owners).
_CWM_PREFIXES = set(CHAIN_PARTS) | {
    "pivot-bushing", "pivot-shaft", "fulcrum-shaft", "lever-bushing"}
# The free-build slice: J1 radial+axial, J2 coaxial+axial, J4 radial+axial,
# J3 radial+axial, J5 = 9 mates, of which 3 are EXTERNAL (J1 radial on the
# pivot-shaft, J1a axial dim to the gap bushing -- the ONLY external dim --
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
        await adapter.export_image({
            "file_path": str(path), "format_type": "png",
            "width": 1600, "height": 1000, "view_orientation": view,
        })
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
    (The cosmetic bank -- springs, spring-hooks -- is GROUNDED at its computed
    insert transform instead, and the bushings are patterned; see the bank
    blocks in build().)
    """
    o = _org(adapter, name)
    pairs = (("Right Plane", "Right Plane", o[0], "x"),
             ("Top Plane", "Top Plane", o[1], "y"),
             ("Front Plane", "Front Plane", o[2], "z"))
    for part_plane, asm_plane, coord, axis in pairs:
        part_ref = named_ref(f"{part_plane}@{name}", "PLANE")
        asm_ref = named_ref(asm_plane, "PLANE")
        if abs(coord) < 1e-6:
            await coincident_mate(
                adapter, part_ref, asm_ref,
                label=f"{name} datum {axis}=0 ({part_plane}<->{asm_plane})",
                verify=(name, o),
            )
            continue
        await distance_driver(
            adapter, part_ref, asm_ref, coord,
            label=f"{name} datum {axis} d={abs(coord):.2f}",
            verify=(name, o),
        )


async def _seat_bushing_on_shaft(
    adapter, name: str, shaft_od_pt: list[float], shaft_xy: tuple[float, float],
    od_r: float,
) -> None:
    """Seat a spacer bushing on the shaft it rides -- the semantic, contact-
    faithful replacement for datum-locating a free-space part.

    The bore literally rides the shaft, so the radial fit is a real *concentric*
    pivot (the #110 "concentric for pivots" idiom): the bushing OD axis is made
    collinear with the shaft OD axis, pinning the two in-plane translations AND
    both tilts in one mate. Then a Front-plane *distance* pins the Z station
    (each bushing sits at a different inter-channel gap, so Z is a genuine
    offset, not a coincidence), and a distance-free *parallel* pins the annulus's
    immaterial spin -- a solid of revolution would otherwise read under-defined.
    Concentric (4) + axial (1) + parallel (1) = the 6 DOF, exactly, no redundancy.

    The OD face (not the bore) is the concentric reference: it is the only
    geometry at radius ``od_r`` in the gap, so its by-point selection is
    unambiguous, whereas the bore wall sits 0.075 mm off the shaft OD.
    """
    o = _org(adapter, name)
    await concentric_mate(
        adapter,
        bore_axis_ref(shaft_od_pt),
        bore_axis_ref([shaft_xy[0] + od_r, shaft_xy[1], o[2]]),
        label=f"{name} concentric on shaft", verify=(name, o),
    )
    await distance_driver(
        adapter,
        named_ref(f"Front Plane@{name}", "PLANE"), named_ref("Front Plane", "PLANE"),
        o[2], label=f"{name} axial z d={abs(o[2]):.2f}", verify=(name, o),
    )
    await parallel_mate(
        adapter,
        named_ref(f"Top Plane@{name}", "PLANE"), named_ref("Top Plane", "PLANE"),
        label=f"{name} anti-spin", verify=(name, o),
    )


# Top-pin-to-foot span of the rigid bar (Axis1 local y - Axis2 local y); the
# amplitude swing pivots the bar about its top pin over this lever arm.
BAR_TOP_TO_FOOT = BAR_TOP_PIN_LOCAL[1] - BAR_FOOT_LOCAL[1]  # 806.45
# Foot-axis -> notch-roof contact offset in the bar's UNtilted (vertical) XY
# frame: the roof sits at the bar's +X edge (+BAR_WIDTH/2) and BAR_FOOT_NOTCH up,
# lifted BAR_CONTACT_GAP off the arc. (Machine frame: the amplitude foot slides
# +X off the pivot, so the roof rides the +X edge -- the mirror of the pre-#151
# -X edge.) Rotating this by the bar tilt keeps the contact-on-arc constraint
# exact as the bar swings.
_CONTACT_OFF_X = BAR_WIDTH / 2.0
_CONTACT_OFF_Y = BAR_FOOT_NOTCH - BAR_CONTACT_GAP


def _arc_geometry() -> dict[str, float]:
    """Amplitude-independent rocker/rod kinematics + the top-edge arc centre.

    Rod-pin point P: |P - pivot| = ARM_ROD_LEVER (127.583) and
    |P - ring centre| = ROD_C2C, +X branch (rod side). The R800 arc the bar
    foot rides has its centre 808 mm out along the tilted arm's +Y, about the
    pivot hole at local (0, 8).
    """
    ox, oy = PIVOT
    cx, cy = RING_CENTER
    dx, dy = cx - ox, cy - oy
    d = math.hypot(dx, dy)
    a = (ARM_ROD_LEVER**2 - ROD_C2C**2 + d * d) / (2.0 * d)
    h = math.sqrt(ARM_ROD_LEVER**2 - a * a)
    ux, uy = dx / d, dy / d
    # -X branch (rod side, machine frame): the ring sits at machine -X of the
    # pivot, so the rod-side intersection is the perpendicular branch with the
    # more-negative x -- (+h*uy, -h*ux) rather than the pre-#151 (-h*uy, +h*ux)
    # that picked the +X (mirrored) side. This IS the h-term sign flip the
    # machine-hand re-authoring demands: the rest of the loop is x-mirror-even.
    px = ox + a * ux + h * uy
    py = oy + a * uy - h * ux
    # The pin azimuth is the LEVER's direction, and the lever leans beta above
    # the arm's local +X. In the machine frame the arm's rod-side points -X, so
    # the azimuth is measured from -X (atan2 with x = ox - px); the ARM tilt is
    # that azimuth MINUS beta. Beta is load-bearing: the low rod-pin bore
    # (ROD_HOLE_Y 15.30) sits 7.30 above the pivot bore, and ignoring the 3.28
    # deg lever angle would land the pin 7 mm off and drag the ring off the cam.
    arm_tilt = math.degrees(math.atan2(py - oy, ox - px)) - ARM_LEVER_BETA_DEG
    rod_tilt = math.degrees(math.atan2(px - cx, py - cy))  # machine hand: mirror
    # of the pre-#151 -atan2 (the ring is now at -X of the pin).

    t = math.radians(arm_tilt)
    rel = ARM_ARC_CENTER_LOCAL_Y - ARM_PIVOT_LOCAL_Y
    acx = ox + rel * math.sin(t)
    acy = oy + rel * math.cos(t)
    return {"arm_tilt": arm_tilt, "rod_tilt": rod_tilt,
            "pin_x": px, "pin_y": py, "acx": acx, "acy": acy}


_ARC = _arc_geometry()
# LEVEL rest pose is authored, not incidental: ROD_HOLE_X / ROD_C2C /
# RING_CENTER are co-solved so the neutral arm sits flat (ch14 end views,
# 0-crank tip row). Any drift here means one of those constants moved without
# re-solving the closure -- fail before SolidWorks bakes the wrong pose in.
if abs(_ARC["arm_tilt"]) > 0.02 or abs(_ARC["rod_tilt"]) > 0.02:
    raise RuntimeError(
        "neutral pose no longer level: arm_tilt=%.4f deg, rod_tilt=%.4f deg "
        "-- re-solve ROD_HOLE_X (build_rocker_arm) and CENTER_DISTANCE "
        "(build_connecting_rod) against RING_CENTER" % (_ARC["arm_tilt"], _ARC["rod_tilt"])
    )


def solve_state(amplitude: float = 0.0) -> dict[str, float]:
    """Solve one channel's kinematics for an amplitude-bar station ``amplitude``.

    ``amplitude`` is the foot-axis X offset from the rocker pivot (mm), the
    Fourier coefficient a_j (channels.yaml ``amplitude_mm``); 0 reproduces the
    neutral pose bit-exactly. The mechanism is a 4-bar loop: the bar top pin
    rides the lever's 127 mm crank, the rigid bar (806.45 mm) hangs to the foot,
    and the foot-notch roof rests on the rocker's R800 top-edge arc. Positive
    amplitude slides the foot +X along the arc (the machine-frame lifting side,
    clear of the pivot shaft; the mirror of the pre-#151 -X side), tilting the
    bar by ``bar_tilt`` and the lever by ``lever_tilt``. Solved by driving the
    lever-reach residual to zero over the bar tilt.

    The solver runs in the machine frame, so its swing root ``beta`` is the
    PHYSICAL bar tilt (the mirror of the pre-#151 value). The reported
    ``bar_tilt`` negates it: the bar is authored ``rows_from_euler([bar_tilt,
    -90, 0])`` (Ry(-90), the mirror of the old Ry(+90)), and with that turn the
    scalar that reproduces the physical pose is -degrees(beta).
    """
    ox, _oy = PIVOT
    acx, acy = _ARC["acx"], _ARC["acy"]
    fx = ox + amplitude  # foot-axis X (+X = the machine-frame lifting side)

    def foot_y(beta: float) -> float:
        s, c = math.sin(beta), math.cos(beta)
        cx_c = fx + _CONTACT_OFF_X * c - _CONTACT_OFF_Y * s
        ky = _CONTACT_OFF_X * s + _CONTACT_OFF_Y * c
        disc = ARM_TOP_RADIUS**2 - (cx_c - acx) ** 2
        if disc <= 0.0:
            raise RuntimeError(f"foot station {amplitude:.1f} mm runs off the R800 arc")
        return acy - ky - math.sqrt(disc)

    def residual(beta: float) -> float:
        fy = foot_y(beta)
        tx = fx + BAR_TOP_TO_FOOT * math.sin(beta)
        ty = fy + BAR_TOP_TO_FOOT * math.cos(beta)
        return math.hypot(tx - FULCRUM[0], ty - FULCRUM[1]) - LEVER_BAR_PIN_X

    beta = _bisect(residual, -0.30, 0.20)
    fy = foot_y(beta)
    tx = fx + BAR_TOP_TO_FOOT * math.sin(beta)
    ty = fy + BAR_TOP_TO_FOOT * math.cos(beta)
    contact_y = fy + _CONTACT_OFF_X * math.sin(beta) + _CONTACT_OFF_Y * math.cos(beta)
    return {
        "arm_tilt": _ARC["arm_tilt"],
        "rod_tilt": _ARC["rod_tilt"],
        "pin_x": _ARC["pin_x"],
        "pin_y": _ARC["pin_y"],
        "bar_tilt": -math.degrees(beta),
        "bar_bottom": fy,                # foot-axis Y
        "bar_origin_x": fx + (BAR_WIDTH / 2.0) * math.cos(beta),
        "bar_origin_y": fy - (BAR_WIDTH / 2.0) * math.sin(beta),
        "contact_y": contact_y,
        "bar_pin_y": ty,
        "lever_tilt": math.degrees(math.atan2(ty - FULCRUM[1], FULCRUM[0] - tx)),
    }


def _bisect(f, lo: float, hi: float, tol: float = 1e-10, iters: int = 80) -> float:
    """Root of monotone ``f`` on [lo, hi] (the bar-tilt that closes the loop)."""
    flo, fhi = f(lo), f(hi)
    if flo == 0.0:
        return lo
    if flo * fhi > 0.0:
        raise RuntimeError(f"bar-tilt root not bracketed: f({lo})={flo:.3f}, f({hi})={fhi:.3f}")
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        fmid = f(mid)
        if abs(fmid) < tol or (hi - lo) < tol:
            return mid
        if (fmid > 0.0) == (fhi > 0.0):
            hi, fhi = mid, fmid
        else:
            lo, flo = mid, fmid
    return 0.5 * (lo + hi)


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
            adapter, part_plane, named_ref("Front Plane", "PLANE"), tgt[2],
            label=f"{label} axial d={abs(tgt[2]):.2f}", verify=(comp, tgt),
        )
    elif kind == "coincident":
        await coincident_mate(
            adapter, part_plane, named_ref(f"Front Plane@{axial[1]}", "PLANE"),
            label=f"{label} axial coincident mid-plane <- {axial[1]}", verify=(comp, tgt),
        )
    elif kind == "distance":
        await distance_driver(
            adapter, part_plane, named_ref(f"Front Plane@{axial[1]}", "PLANE"), axial[2],
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


def _assert_spring_threading(hole_y: float, eye_y: float) -> None:
    """Assert the eye ring threads the O4 hole without touching the lever.

    The eye is a torus: ring plane vertical, containing the hole axis (Z);
    ring-circle radius 2.75, wire radius 0.5, centre hanging DROP below the
    hole centre. Sweep the torus surface (tube angle phi, slab depth z):
    a tube point at radial offset rho = R + r*cos(phi), lateral (along the
    lever, X) offset r*sin(phi), reaches slab depth z (|z| <= 1.5) on the
    upper branch at dy = +sqrt(rho^2 - z^2) above the eye centre and must
    stay inside the hole bore there; the lower branch at -sqrt(rho^2 - z^2)
    must pass under the lever tab's bottom edge. Binding extremes (rho
    2.25, z +/-1.5): sqrt(2.25^2 - 1.5^2) = 1.677 -> top |1.677 - D|,
    bottom D + 1.677 - 3.0; with D = 3.37 margins ~0.31 / ~2.0.
    """
    half_t = LEVER_THICKNESS / 2.0
    wire_r = SPRING_WIRE_DIA / 2.0
    hole_r = SPRING_HOLE_DIA / 2.0
    plate_bottom = hole_y - LEVER_TAB_HALF
    worst_bore = 0.0  # max distance of the upper branch from the hole axis
    worst_under = -math.inf  # max y of the lower branch inside the slab
    steps = 360
    for k in range(steps):
        phi = 2.0 * math.pi * k / steps
        rho = SPRING_LOOP_R + wire_r * math.cos(phi)
        x_off = wire_r * math.sin(phi)
        for n in range(-30, 31):
            z = half_t * n / 30.0
            if rho <= abs(z):
                continue
            dy = math.sqrt(rho * rho - z * z)
            worst_bore = max(worst_bore, math.hypot(x_off, eye_y + dy - hole_y))
            worst_under = max(worst_under, eye_y - dy)
    margin_top = hole_r - worst_bore
    margin_bot = plate_bottom - worst_under
    if margin_top < 0.1 or margin_bot < 0.1:
        raise RuntimeError(
            f"spring eye threading margins too small: hole-void {margin_top:.3f},"
            f" under-lever {margin_bot:.3f}"
        )
    log(
        f"spring eye threading: hole-void margin {margin_top:.2f},"
        f" under-lever margin {margin_bot:.2f}"
    )


def _assert_hook_fastener(eye_y: float) -> None:
    """Assert the spring-hook fastener bridges the spring to the plate cleanly.

    The spring no longer threads the plate. Its bottom eye sits ABOVE the plate
    at the FIXED ``PLATE_EYE_Y`` (pose-independent: every channel's bottom eye is
    pinned there, only the top eye at ``eye_y`` rides the lever). A separate open
    J-hook (build_spring_hook.py) seats shank-up in the plate's O2.0 bore and
    presents its +X arm at ``PLATE_EYE_Y``, where the spring eye links on. This
    checks the pose-independent fastener geometry -- eye clear above the plate,
    shank filling+poking through the bore, arm threading the eye with clearance --
    plus the genuine pose-dependent invariant: the neutral body must stay stretched.
    """
    plate_bottom = PLATE_TOP_Y - PLATE_THICKNESS
    wire_r = SPRING_WIRE_DIA / 2.0
    hook_r = HOOK_ROD_DIA / 2.0
    shank_base = PLATE_EYE_Y - HOOK_ARM_HEIGHT  # arm sits HOOK_ARM_HEIGHT above base
    shank_top = shank_base + HOOK_SHANK_RISE
    eye_above_plate = PLATE_EYE_Y - PLATE_TOP_Y  # bottom eye clear above the casting
    # The eye is a torus, ring plane vertical (axis +X): its LOWEST point hangs a
    # full ring radius + wire below the centre, so the centre clearing the plate is
    # NOT enough -- the ring bottom is what fouls the casting (the 0.85 mm dip that
    # got past the centre-only check and showed as 20 top-level interferences).
    eye_ring_bottom = PLATE_EYE_Y - (SPRING_LOOP_R + wire_r)
    ring_above_plate = eye_ring_bottom - PLATE_TOP_Y
    shank_poke = shank_top - PLATE_TOP_Y         # shank fills the bore + protrudes
    seat_drop = plate_bottom - shank_base        # shank base reaches the bore mouth
    bore_clear = PLATE_HOLE_DIA / 2.0 - hook_r   # shank O1.4 in O2.0 bore
    ring_clear = (SPRING_LOOP_R - wire_r) - hook_r  # eye inner radius vs arm wire
    body = (eye_y - PLATE_EYE_Y) - SPRING_TOP_LEAD - SPRING_BOTTOM_LEAD
    if eye_above_plate < 0.5 or ring_above_plate < 0.3:
        raise RuntimeError(
            f"spring bottom eye not clear above the plate: centre {eye_above_plate:.3f}"
            f" mm, ring bottom {ring_above_plate:.3f} mm (eye {PLATE_EYE_Y:.2f}, ring"
            f" bottom {eye_ring_bottom:.2f}, plate top {PLATE_TOP_Y:.2f}) -- the eye"
            f" ring would foul the casting instead of hanging on the hook"
        )
    if shank_poke < 0.1 or abs(seat_drop) > 0.5:
        raise RuntimeError(
            f"hook shank does not seat the bore: poke-above {shank_poke:.3f},"
            f" base-vs-bore-mouth {seat_drop:+.3f} (want shank to fill 987.44..992.54)"
        )
    if bore_clear < 0.05 or ring_clear < 0.05:
        raise RuntimeError(
            f"hook fastener clearances too small: shank-in-bore {bore_clear:.3f},"
            f" arm-in-eye {ring_clear:.3f}"
        )
    if body < COIL_BODY_LENGTH:
        raise RuntimeError(
            f"neutral spring body {body:.2f} mm below the free coil"
            f" {COIL_BODY_LENGTH:.2f} mm: the rest pose dropped the lever eye too"
            f" far -- the spring would be in compression, not tension"
        )
    log(
        f"hook fastener: bottom eye y {PLATE_EYE_Y:.2f} ({eye_above_plate:.2f} above"
        f" plate, ring bottom {ring_above_plate:.2f} above), shank poke {shank_poke:.2f},"
        f" bore clearance {bore_clear:.2f}, arm-in-eye {ring_clear:.2f},"
        f" neutral body {body:.2f} (free {COIL_BODY_LENGTH:.2f})"
    )


def _spring_spec(amplitude: float, hole_x_0: float) -> dict[str, Any]:
    """Per-channel stretched-spring geometry (parametric-springs memory, task #10).

    The lever lifts/tilts with the amplitude, so the top eye moves to
    ``(hole_x, eye_y)``; the bottom eye stays at the FIXED summing-plate hole
    ``(hole_x_0, PLATE_EYE_Y)`` -- the neutral bottom-eye position the plate was
    built around. The spring is grounded along that line at the EXACT gap length
    (length = gap - top_lead - bottom_lead), instead of a fixed 63 mm body lifted
    bodily into the plate (the F3 80 mm interference regression). The tilt is tiny
    (<=1.1 deg) -- the span is almost pure stretch.
    """
    st = solve_state(amplitude)
    phi = math.radians(st["lever_tilt"])
    hole_x = FULCRUM[0] - LEVER_SPRING_X * math.cos(phi)  # lever reaches -X (machine)
    hole_y = FULCRUM[1] + LEVER_SPRING_X * math.sin(phi)
    eye_y = hole_y - SPRING_EYE_DROP
    dx = hole_x - hole_x_0
    dy = eye_y - PLATE_EYE_Y
    gap = math.hypot(dx, dy)
    return {
        "hole_y": hole_y, "eye_y": eye_y, "gap": gap,
        "body": gap - SPRING_TOP_LEAD - SPRING_BOTTOM_LEAD,
        "ux": dx / gap, "uy": dy / gap,
        "theta": math.degrees(math.atan2(-dx, dy)),
    }


async def build(adapter) -> dict[str, str]:
    # The amplitude-bar station per channel IS the Fourier coefficient a_j
    # (channels.yaml amplitude_mm, the square-wave preset). solve_state(a_j)
    # repositions that channel's bar + lever; a_j = 0 is the neutral pose. The
    # neutral state still anchors the amplitude-independent rocker/rod and the
    # cosmetic spring/threading seed.
    amplitudes = _config.amplitudes()
    if any(a < 0.0 for a in amplitudes):
        raise RuntimeError(
            "amplitude_mm must be >= 0 (the lifting side keeps the foot clear of"
            f" the pivot shaft); got {amplitudes}"
        )
    state = solve_state(0.0)
    log(
        "neutral state: arm tilt %.3f deg, rod tilt %.3f deg, pin (%.2f, %.2f),"
        % (state["arm_tilt"], state["rod_tilt"], state["pin_x"], state["pin_y"])
    )
    log(
        "  bar contact %.3f, bar bottom %.3f, bar pin y %.3f, lever tilt %.3f deg"
        % (state["contact_y"], state["bar_bottom"], state["bar_pin_y"], state["lever_tilt"])
    )
    log(
        "amplitude preset: a_j stations (mm) = %s"
        % ", ".join(f"{a:.2f}" for a in amplitudes)
    )

    # Neutral reference design: the spring/plate threading is asserted at the
    # neutral lever pose (the as-photographed installed length). Per-channel
    # springs translate up with their levers (placed in the loop); their fit to
    # the fixed summing plate is realised at the top level by the parametric
    # spring length (parametric-springs memory).
    phi = math.radians(state["lever_tilt"])
    spring_hole_y = FULCRUM[1] + LEVER_SPRING_X * math.sin(phi)
    eye_y = spring_hole_y - SPRING_EYE_DROP
    _assert_spring_threading(spring_hole_y, eye_y)
    _assert_hook_fastener(eye_y)

    # Bushing clearance under the bar foot at d = 0 (geometry gate).
    bar_clearance = state["bar_bottom"] - PIVOT[1]
    if bar_clearance < 5.5:
        raise RuntimeError(f"bar passes only {bar_clearance:.2f} above the shaft")

    # Per-channel stretched springs (task #10): each spans the moving lever eye to
    # the fixed plate hole at its measured gap length. Even (a_j=0) channels reuse
    # the base part; the rest get a distinct stretched variant, built ONCE here
    # (lean -- no PNG views; the canonical part renders its own). The variants are
    # length variants of channel-spring-installed, so part_properties inherits its
    # registry row (their placement is authored machine-handed here, no per-part
    # symmetry declaration -- the #151 mirror layer is gone).
    phi_0 = math.radians(state["lever_tilt"])  # state = solve_state(0.0)
    hole_x_0 = FULCRUM[0] - LEVER_SPRING_X * math.cos(phi_0)  # lever reaches -X
    spring_specs = [_spring_spec(a, hole_x_0) for a in amplitudes]
    # The canonical channel-spring-installed body MUST equal the neutral gap so
    # the neutral pose mates that ONE part x20 with no generated stretch variant.
    # If the lever anchor drifts (another OD re-anchor) they diverge -- fail loud
    # here (and offline: verify:math spring:neutral-body-canonical) rather than
    # silently spawning a stretch00. Non-neutral a_j still get real variants.
    neutral_body = _spring_spec(0.0, hole_x_0)["body"]
    if abs(neutral_body - SPRING_BASE_BODY) >= 0.05:
        raise RuntimeError(
            f"channel-spring-installed body {SPRING_BASE_BODY:.3f} != neutral gap "
            f"{neutral_body:.3f}: update LEVER_EYE_Y in "
            f"build_channel_spring_installed.py to the re-anchored neutral eye"
        )
    variant_by_body: dict[float, str] = {}
    for spec in spring_specs:
        if abs(spec["body"] - SPRING_BASE_BODY) < 0.05:
            spec["part"] = "channel-spring-installed"
            continue
        key = round(spec["body"], 2)
        name = variant_by_body.get(key)
        if name is None:
            name = f"channel-spring-installed-stretch{len(variant_by_body):02d}"
            variant_by_body[key] = name
        spec["part"] = name
    log(f"spring variants: base {SPRING_BASE_BODY:.2f} + {len(variant_by_body)} "
        f"stretched bodies {sorted(variant_by_body)}")
    for key, name in variant_by_body.items():
        # Always rebuild: a skip-if-exists short-circuit could reuse a stale
        # stretchNN body of a different length after amplitudes/spring lengths
        # change, because these dynamic .SLDPRTs are not declared doit targets and
        # so survive `doit clean` of the part graph (codex review #4; clean now
        # wipes them, and this rebuilds them fresh).
        log(f"  building {name} body={key:.2f} (no views)")
        await build_spring(
            adapter, name, key,
            leads=(SPRING_BOTTOM_LEAD, SPRING_TOP_LEAD), views=[], eye_axes=True)
    adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)

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
        adapter, "pivot-shaft", [PIVOT[0], PIVOT[1], PIVOT_SHAFT_Z], [0.0, 0.0, 0.0],
        IDENTITY, ground=False, label="pivot-shaft (rocker, seed)",
    )
    fulcrum = await place_component(
        adapter, "fulcrum-shaft", [FULCRUM[0], FULCRUM[1], 0.0], [0.0, 0.0, 0.0],
        IDENTITY, ground=False, label="fulcrum-shaft (lever bank)",
    )
    await _locate_to_datum(adapter, fulcrum)
    pivot_w = (PIVOT[0], PIVOT[1])  # (72.9, 253.8) machine world
    fulc_w = (FULCRUM[0], FULCRUM[1])  # (199.9, 1065.9) machine world
    pivot_od = [pivot_w[0] + SHAFT_R, pivot_w[1], 0.0]
    fulc_od = [fulc_w[0] + SHAFT_R, fulc_w[1], 0.0]

    # Ball mounts. Free-space structure with no contact partner, so each is
    # datum-located (three orthogonal plane distances), not fixed -- the #110
    # idiom. The rocker pair is asymmetric (M6.5): north seats on the
    # rocker-support apex, south on the A-frame clevis saddle (both tops at
    # y 228.6).
    for mount_z in (-AFRAME_MOUNT_Z_ABS, SUPPORT_Z):
        mount = await place_component(
            adapter, "pivot-ball-mount",
            [PIVOT[0], SUPPORT_APEX_Y, mount_z],
            [0.0, 0.0, 0.0], IDENTITY, ground=False,
            label=f"ball-mount rocker z{mount_z:+.0f}",
        )
        await _locate_to_datum(adapter, mount)
    for sz in (-1.0, 1.0):
        mount = await place_component(
            adapter, "pivot-ball-mount",
            [FULCRUM[0], RAIL_TOP_Y, sz * LEVER_MOUNT_Z],
            [0.0, 0.0, 0.0], IDENTITY, ground=False,
            label=f"ball-mount lever z{sz * LEVER_MOUNT_Z:+.0f}",
        )
        await _locate_to_datum(adapter, mount)

    # Bushings FIRST (before the moving-part loop), so each channel's rocker can
    # take its axial (Z) seat as a DISTANCE to the pivot-bushing in the gap below
    # it -- chaining Z part->part off a physical neighbour rather than every rocker
    # referencing the global Front datum (the #110 neighbour idiom, request #4).
    # One pivot + one lever bushing ride the shafts in each inter-channel gap
    # j-1/j (j>=1) at z_gap = z_mid(j) - PITCH/2. REVIVED seed+pattern
    # (2026-07-09): ONE semantically seated seed per bank at the TOP gap
    # (_seat_bushing_on_shaft, the #110 pivot idiom, 3 mates), replicated down
    # the spine by a LocalLinearPattern off the BankZ datum axis -- see
    # _pattern_bank for the sense-verify + FlipDir1 retry that replaces the
    # retired face-pick inference. Net: 2 patterns replace 36 seated copies
    # (108 mates), each of which paid a full-assembly re-solve.
    # pivot_bushing_by_gap[j] is the bushing directly below channel j's rocker
    # (pattern instances are real components; their names map to gaps by
    # transform Z).
    pivot_bushing_by_gap: dict[int, str] = {}
    if CHANNELS > 1:
        gap_planes = [
            z_station(j) + ARM_MID_DZ - PITCH / 2.0 for j in range(1, CHANNELS)
        ]
        z_top_gap = gap_planes[-1]
        bank_axis = check(
            "axis BankZ (Top ∩ Right)",
            await adapter.create_axis(
                CreateAxisParameters(
                    mode="two_planes", planes=["Top Plane", "Right Plane"]
                )
            ),
        ).name
        for part, xy, od_pt, od_r in (
            ("pivot-bushing", pivot_w, pivot_od, PIVOT_BUSHING_OD / 2.0),
            ("lever-bushing", fulc_w, fulc_od, LEVER_BUSHING_OD / 2.0),
        ):
            seed = await place_component(
                adapter, part, [xy[0], xy[1], z_top_gap],
                [0.0, 0.0, 0.0], IDENTITY, ground=False,
                label=f"{part} seed gap {CHANNELS - 2:02d}/{CHANNELS - 1:02d}",
            )
            await _seat_bushing_on_shaft(adapter, seed, od_pt, xy, od_r)
            await _pattern_bank(adapter, seed, part, bank_axis, gap_planes)
        for j, z_gap in enumerate(gap_planes, start=1):
            pivot_bushing_by_gap[j] = _instance_at_z(adapter, "pivot-bushing", z_gap)

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
    # LocalLinearPattern. The pattern's direction sense is read from the shaft's
    # cosmetic repeated structure. The bushing banks are seed+pattern off the
    # BankZ reference axis (see the block above the loop); the springs and
    # spring-hooks are per-channel GROUNDED cosmetic parts (Pedro 2026-07-09,
    # v018 perf review): no operational DOF, no in-subassembly contact partner,
    # and a pose fully computed at insert time (the per-channel amplitude tilt
    # is baked into spring_rows), so the placement transform IS the final pose
    # and the old 7-mates-per-channel locate battery bought nothing but ~140
    # late-assembly mate solves. Their specs are COLLECTED per channel and
    # inserted in ONE AddComponents3 + fixed in ONE FixComponent (Select2 each,
    # one solve) after the chain loops (place_components_batch). The MOVING
    # parts stay individual mated instances so each channel articulates
    # independently (a different harmonic frequency) for the Motion study --
    # but they are NOT all authored one by one: only the seeds are
    # (_author_channel); same-amplitude channels are replicated from their
    # seed's slice by CopyWithMates2 (the dispatch loop), each copy validated
    # against the seed pose from the model.
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
            adapter, "rocker-arm",
            [PIVOT[0] - arm_origin_dx, PIVOT[1] - arm_origin_dy, z_mid],
            euler_from_rows(arm_rows), arm_rows,
            ground=False, label=f"rocker-arm ch{j:02d}",
        )
        rod = await place_component(
            adapter, "connecting-rod",
            [RING_CENTER[0], RING_CENTER[1], zj + CAM_DZ],
            euler_from_rows(rod_rows), rod_rows,
            ground=False, label=f"connecting-rod ch{j:02d}",
        )
        # Origin places the foot axis at (PIVOT[0] + a_j, bar_bottom) on the
        # machine +X lifting side; the swing keeps the foot on the arc.
        bar = await place_component(
            adapter, "amplitude-bar",
            [st["bar_origin_x"], st["bar_origin_y"], z_mid - BAR_WIDTH / 2.0],
            [st["bar_tilt"], -90.0, 0.0], bar_rows,
            ground=False, label=f"amplitude-bar ch{j:02d} a={amplitudes[j]:.2f}",
        )
        lever = await place_component(
            adapter, "channel-lever",
            [FULCRUM[0], FULCRUM[1], z_mid],
            euler_from_rows(lever_rows), lever_rows,
            ground=False, label=f"channel-lever ch{j:02d}",
        )

        # J1 rocker revolute (shaft OD ↔ pivot bore). Axial Z chains off the
        # neighbour pivot-bushing in the gap below (distance = PITCH/2), except
        # channel 0 which is the single global Z anchor (#110 neighbour idiom,
        # request #4). The spin is a freed DOF: recorded, not authored, so the
        # rocker swings about its pivot (request #3).
        axial = (("distance", pivot_bushing_by_gap[j], PITCH / 2.0)
                 if j >= 1 else ("datum",))
        await _revolute(
            adapter, rocker,
            bore_axis_ref(pivot_od), named_ref(f"Axis1@{rocker}", "AXIS"),
            concentric=True, off_axis_name="Axis2",
            off_axis_local=ROCKER_ROD_BORE_LOCAL, pivot_xy=pivot_w,
            label=f"J1 rocker ch{j:02d}", axial=axial,
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
            adapter, named_ref(f"Axis2@{rocker}", "AXIS"), named_ref(f"Axis2@{rod}", "AXIS"),
            label=f"J2 rod ch{j:02d} coaxial pin <- {rocker}", verify=(rod, rod_tgt),
        )
        await distance_driver(
            adapter, named_ref(f"Front Plane@{rod}", "PLANE"), named_ref(f"Front Plane@{rocker}", "PLANE"),
            rod_tgt[2] - z_mid,
            label=f"J2 rod ch{j:02d} axial d={abs(rod_tgt[2] - z_mid):.2f} <- {rocker}",
            verify=(rod, rod_tgt),
        )
        await spin_driver(
            adapter, named_ref(f"Axis1@{rod}", "AXIS"),
            (rod_pin[0], rod_pin[1]), (rod_ring[0], rod_ring[1]),
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
            adapter, lever,
            bore_axis_ref(fulc_od), named_ref(f"Axis1@{lever}", "AXIS"),
            concentric=True, off_axis_name="Axis2",
            off_axis_local=LEVER_BAR_PIN_BORE_LOCAL, pivot_xy=fulc_w,
            label=f"J4 lever ch{j:02d}", axial=("coincident", rocker),
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
            named_ref(f"Axis2@{lever}", "AXIS"), named_ref(f"Axis1@{bar}", "AXIS"),
            label=f"J3 bar ch{j:02d} radial (top-pin hinge)", verify=(bar, bar_tgt),
        )
        # Axial seat: the bar straddles the rocker symmetrically, so its named
        # MidWidth plane (local x = BarWidth/2) lands on the channel mid-plane.
        # Seat it COINCIDENT to the rocker's Front (mid-)plane -- the semantic
        # "bar mid-plane on the rocker mid-plane" contact -- not a bare distance.
        await coincident_mate(
            adapter,
            named_ref(f"MidWidth@{bar}", "PLANE"), named_ref(f"Front Plane@{rocker}", "PLANE"),
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
            named_ref(f"Axis2@{bar}", "AXIS"), named_ref("Right Plane", "PLANE"),
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
            (PIVOT[0] + amplitudes[j]) - _ARC["acx"], st["bar_bottom"] - _ARC["acy"])
        if abs(foot_r - want_r) > 1e-3:
            raise RuntimeError(
                f"ch{j:02d}: measured foot->arc-centre radius {foot_r:.4f} != "
                f"analytic {want_r:.4f} -- the placed pose drifted off solve_state"
            )
        await distance_driver(
            adapter,
            named_ref(f"Axis2@{bar}", "AXIS"), named_ref(f"Axis3@{rocker}", "AXIS"),
            foot_r,
            label=f"J5 bar-foot on rocker arc ch{j:02d} r={foot_r:.2f}",
            verify=(bar, bar_tgt),
        )
        return {"rocker-arm": rocker, "connecting-rod": rod,
                "amplitude-bar": bar, "channel-lever": lever}

    def _slice_slots(seed_comps: dict[str, str]) -> dict[str, Any]:
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
        rows = [r for r in mates_with_owners(adapter, _CWM_PREFIXES)
                if r["instances"] & slice_instances]
        if len(rows) != SLICE_MATES:
            raise RuntimeError(
                f"seed slice carries {len(rows)} mates, expected {SLICE_MATES}"
                " -- the mate scheme changed; re-derive SLICE_MATES/"
                f"SLICE_EXTERNAL: {[r['name'] for r in rows]}")
        ext = external_mate_rows(rows, slice_instances)
        if len(ext) != SLICE_EXTERNAL:
            raise RuntimeError(
                f"seed slice exposes {len(ext)} external mates, expected"
                f" {SLICE_EXTERNAL}: {[r['name'] for r in ext]}")
        dims = [(i, r) for i, r in enumerate(ext)
                if r["type"] == "MateDistanceDim"]
        if len(dims) != 1:
            raise RuntimeError(
                "seed slice must expose exactly ONE external dim (the J1a"
                f" rocker axial); got {[(i, r['name']) for i, r in dims]}")
        slot, dim = dims[0]
        if dim["owners"] != frozenset({"rocker-arm", "pivot-bushing"}):
            raise RuntimeError(
                f"external dim {dim['name']!r} is not the J1a rocker->bushing"
                f" axial (owners {sorted(dim['owners'])})")
        if abs(dim["mm"] - PITCH / 2.0) > 0.01:
            raise RuntimeError(
                f"J1a seed value {dim['mm']:.3f} mm != PITCH/2"
                f" {PITCH / 2.0:.3f} -- the axial anchor moved")
        # The seed's J1a side is CARRIED to each copy (flips[dim_slot]) via the
        # Repeat=false + own-bushing idiom, so any seed side is honoured; the
        # authored neighbour idiom (#110) produces flip=False. No always-positive
        # ladder is needed anymore (see the copy site + _cwm.py module doc).
        arrays = {p: list(component_transform(adapter, n))
                  for p, n in seed_comps.items()}
        mate_counts = {p: component_mate_count(adapter, n)
                       for p, n in seed_comps.items()}
        # The seed's drive targets (all Z-independent), for the transient
        # drivers that land each copy on the design pose.
        return {
            "n": len(rows), "dim_slot": slot, "dim_flip": bool(dim["flip"]),
            "arrays": arrays,
            "mate_counts": mate_counts,
            "rocker_off": world_point(
                adapter, seed_comps["rocker-arm"], ROCKER_ROD_BORE_LOCAL),
            "rod_ring": world_point(
                adapter, seed_comps["connecting-rod"], ROD_STRAP_BORE_LOCAL),
            "rod_pin": world_point(
                adapter, seed_comps["connecting-rod"], ROD_PIN_BORE_LOCAL),
            "foot": world_point(
                adapter, seed_comps["amplitude-bar"], BAR_FOOT_LOCAL),
        }

    # Per-channel chain, seed-and-replicate (PR #220 -> production). Channel 0
    # is always authored (it is the single global Z anchor -- its J1a is a
    # ROOT-datum distance at a negative station, so it is never a copy seed).
    # The first channel >= 1 of each amplitude value is authored as that group's
    # SEED (its J1a anchors PITCH/2 off its own gap bushing); every later
    # same-amplitude channel is ONE CopyWithMates2 of the seed's 4-part slice
    # with the J1a slot re-pointed (Repeat=false) to ITS own gap bushing at the
    # same local PITCH/2. With the current all-neutral preset that is 2 authored
    # + (CHANNELS-2) copies; a restored square preset degrades gracefully (each
    # distinct a_j authors once).
    seed_by_amp: dict[float, tuple[int, dict[str, str]]] = {}
    slots_by_seed: dict[int, tuple[int, int, dict[str, list[float]]]] = {}
    copied: list[dict[str, Any]] = []
    for j in range(CHANNELS):
        st = solve_state(amplitudes[j])  # this channel's bar/lever pose
        amp_key = round(amplitudes[j], 6)
        seed = seed_by_amp.get(amp_key) if j >= 2 else None
        if seed is None:
            comps = await _author_channel(j, st)
            if j >= 1:
                seed_by_amp[amp_key] = (j, comps)
            continue
        seed_j, seed_comps = seed
        if seed_j not in slots_by_seed:
            slots_by_seed[seed_j] = _slice_slots(seed_comps)
        slice_info = slots_by_seed[seed_j]
        n_slice, dim_slot = slice_info["n"], slice_info["dim_slot"]
        seed_arrays = slice_info["arrays"]
        # Re-point ONLY the J1a slot to THIS channel's OWN gap bushing
        # (Repeat=false + NewEntityToMateTo) at the LOCAL PITCH/2 seat -- exactly
        # the authored #110 neighbour idiom -- honouring the seed's side via
        # flips[dim_slot]. The other two external slots (J1 radial on the shared
        # pivot-shaft) keep the seed's references (Repeat=true), the measured
        # mixed-array idiom. This drops the old cumulative always-positive ladder
        # off the seed's bushing (see _cwm.py module doc).
        own_bushing = pivot_bushing_by_gap[j]
        values = [0.0] * n_slice
        values[dim_slot] = (PITCH / 2.0) / 1000.0
        repeat = [True] * n_slice
        repeat[dim_slot] = False
        new_ents: list = [None] * n_slice
        new_ents[dim_slot] = resolve_entity(
            adapter, named_ref(f"Front Plane@{own_bushing}", "PLANE"))
        flips = [False] * n_slice
        flips[dim_slot] = slice_info["dim_flip"]
        with _telemetry.span("cwm.comp_names", channel=j, phase="before"):
            before_comps = set(component_names(adapter))
        copy_with_mates(
            adapter, [seed_comps[p] for p in CHAIN_PARTS], n_slice, values,
            flips=flips, repeat=repeat, new_entities=new_ents)
        with _telemetry.span("cwm.comp_names", channel=j, phase="after"):
            new_comps = sorted(set(component_names(adapter)) - before_comps)
        comps = {}
        for name in new_comps:
            part = name.rsplit("-", 1)[0]
            if part not in CHAIN_PARTS or part in comps:
                raise RuntimeError(
                    f"ch{j:02d} copy: unexpected new component {name!r}"
                    f" (full new set {new_comps})")
            comps[part] = name
        if len(comps) != len(CHAIN_PARTS):
            raise RuntimeError(
                f"ch{j:02d} copy created {len(comps)}/{len(CHAIN_PARTS)} chain"
                f" parts: {new_comps}")
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
        copied.append({"j": j, "seed_j": seed_j, "comps": comps,
                       "targets": targets, "slice_info": slice_info,
                       "own_bushing": own_bushing})

    # Copy every free chain first, then settle their solver-state attractors in
    # one post-copy phase. Driving each copy immediately made every later
    # CopyWithMates2 addition re-wander already-settled free siblings; the v0.20.0
    # trace spent 173 s across those repeated pose-drive spans. Re-putting the
    # complete copied bank before each transient driver keeps every still-free
    # chain on its design branch while the current channel is committed.
    def _put_all_copies() -> None:
        for rec in copied:
            for part in CHAIN_PARTS:
                put_component_pose(
                    adapter, rec["comps"][part], rec["targets"][part])

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
                    adapter, named_ref(f"Axis2@{rocker_c}", "AXIS"),
                    pivot_w, (off[0], off[1]),
                    label=(f"J1 rocker ch{j:02d} spin ->"
                           f" {off[0]:.1f},{off[1]:.1f}"),
                    verify=(rocker_c, _tgt_mm("rocker-arm")))
                drives.append(mate["name"])
                _put_all_copies()
                mate = await distance_driver(
                    adapter, named_ref(f"Axis2@{bar_c}", "AXIS"),
                    named_ref("Right Plane", "PLANE"), foot[0],
                    label=(f"J3 bar ch{j:02d} AMPLITUDE drive"
                           f" foot-X={foot[0]:.2f} (amp"
                           f" {amplitudes[j]:+.1f})"),
                    verify=(bar_c, _tgt_mm("amplitude-bar")))
                drives.append(mate["name"])
                _put_all_copies()
                mate = await spin_driver(
                    adapter, named_ref(f"Axis1@{rod_c}", "AXIS"),
                    (pin[0], pin[1]), (ring[0], ring[1]),
                    label=(f"J2 rod ch{j:02d} swing -> ring"
                           f" {ring[0]:.1f},{ring[1]:.1f}"),
                    verify=(rod_c, _tgt_mm("connecting-rod")))
                drives.append(mate["name"])
                for name in reversed(drives):
                    delete_assembly_feature(adapter, name)
        except Exception:
            if _CWM_DEBUG:
                for part in CHAIN_PARTS:
                    a = component_transform(adapter, comps[part])
                    t = targets[part]
                    log(f"  DEBUG ch{j:02d} {comps[part]} at-drive-fail pose:"
                        f" ({a[9] * 1000:.2f}, {a[10] * 1000:.2f},"
                        f" {a[11] * 1000:.2f})"
                        f" xrow ({a[0]:+.3f},{a[1]:+.3f},{a[2]:+.3f}) target"
                        f" ({t[9] * 1000:.2f}, {t[10] * 1000:.2f},"
                        f" {t[11] * 1000:.2f})")
                await _debug_png(adapter, f"drive-fail-ch{j:02d}")
            raise
        log(f"ch{j:02d} <- CopyWithMates2 of ch{seed_j:02d}"
            f" (J1a PITCH/2 {PITCH / 2.0:.2f} mm <- own bushing"
            f" {rec['own_bushing']}, driven to pose + freed)")

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
                    log(f"  DEBUG mates seed {seed_comps[part]}: "
                        f"{component_mate_dump(adapter, seed_comps[part])}")
                    log(f"  DEBUG mates copy {rec['comps'][part]}: "
                        f"{component_mate_dump(adapter, rec['comps'][part])}")
        for rec in copied:
            seed_counts = slots_by_seed[rec["seed_j"]]["mate_counts"]
            for part in CHAIN_PARTS:
                name = rec["comps"][part]
                a = rec["targets"][part]
                assert_component_placed(
                    adapter, name,
                    [a[9] * 1000.0, a[10] * 1000.0, a[11] * 1000.0],
                    [list(a[0:3]), list(a[3:6]), list(a[6:9])],
                )
                got = component_mate_count(adapter, name)
                if got != seed_counts[part]:
                    raise RuntimeError(
                        f"ch{rec['j']:02d} {name}: {got} mates, seed has"
                        f" {seed_counts[part]} -- the copy dropped mates")
                status = component_constrained_status(adapter, name)
                if status != UNDER_CONSTRAINED:
                    raise RuntimeError(
                        f"ch{rec['j']:02d} {name}: constrained status"
                        f" {status}, expected under-constrained"
                        f" ({UNDER_CONSTRAINED}) -- a copied mate is"
                        " unsolvable or over-defining")
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
                adapter, named_ref(f"Axis2@{rocker}", "AXIS"), pivot_w,
                (off[0], off[1]),
                label=f"J1 rocker ch{j:02d} spin -> {off[0]:.1f},{off[1]:.1f}",
                verify=(rocker, tgt), free_dof_key=f"rocker_angle_{j:02d}")
            free_dof_keys.append(f"rocker_angle_{j:02d}")
            tgt = _org(adapter, rod)
            ring = world_point(adapter, rod, ROD_STRAP_BORE_LOCAL)
            pin = world_point(adapter, rod, ROD_PIN_BORE_LOCAL)
            await spin_driver(
                adapter, named_ref(f"Axis1@{rod}", "AXIS"),
                (pin[0], pin[1]), (ring[0], ring[1]),
                label=f"J2 rod ch{j:02d} swing -> ring {ring[0]:.1f},{ring[1]:.1f}",
                verify=(rod, tgt), free_dof_key=f"rod_swing_{j:02d}")
            free_dof_keys.append(f"rod_swing_{j:02d}")
            tgt = _org(adapter, bar)
            foot = world_point(adapter, bar, BAR_FOOT_LOCAL)
            amplitude = foot[0] - pivot_w[0]
            await distance_driver(
                adapter,
                named_ref(f"Axis2@{bar}", "AXIS"),
                named_ref("Right Plane", "PLANE"),
                foot[0],
                label=(f"J3 bar ch{j:02d} AMPLITUDE drive foot-X={foot[0]:.2f}"
                       f" (amp {amplitude:+.1f})"),
                verify=(bar, tgt), free_dof_key=f"bar_amplitude_{j:02d}")
            free_dof_keys.append(f"bar_amplitude_{j:02d}")

    for j in range(CHANNELS):
        z_mid = z_station(j) + ARM_MID_DZ
        # Return spring (ground; cosmetic) -- placed PER CHANNEL spanning this
        # channel's (moving) lever eye to the FIXED summing-plate hole, at the
        # measured gap length (parametric-springs memory / task #10). NOT a fixed
        # 63 mm body and NOT patterned: the lever tilts/lifts with the amplitude,
        # so a fixed-length vertical spring lifts its bottom bodily into the plate
        # (the F3 80 mm interference regression). `spec` carries the per-channel
        # length variant + the unit span direction (coil axis, bottom->top).
        # _assert_spring_threading is tilt-invariant (eye 3.37 below the hole),
        # so the top eye threads the lever hole; the bottom eye lands on the fixed
        # plate hole at (hole_x_0, PLATE_EYE_Y) by construction.
        spec = spring_specs[j]
        _assert_spring_threading(spec["hole_y"], spec["eye_y"])
        ux, uy = spec["ux"], spec["uy"]
        # rows = Rz(theta).Ry90: local +Y (coil axis) -> the span direction,
        # local +Z (eye axis) -> the in-plane normal, local +X -> world -Z for
        # ANY theta (first row tilt-independent). The tilt is baked in here, so
        # the grounded pose holds for every amplitude preset. theta=0 vertical.
        spring_rows = [[0.0, 0.0, -1.0], [ux, uy, 0.0], [uy, -ux, 0.0]]
        grounded_specs.append({
            "part": spec["part"],
            "position": [hole_x_0 + SPRING_BOTTOM_LEAD * ux,
                         PLATE_EYE_Y + SPRING_BOTTOM_LEAD * uy, z_mid],
            "rotation": [0.0, 0.0, 0.0],
            "rows": spring_rows,
            "kind": "spring", "theta": spec["theta"],
            "label": (f"channel-spring ch{j:02d} {spec['part'].rsplit('-', 1)[-1]} "
                      f"body={spec['body']:.2f} tilt={spec['theta']:+.2f}"),
        })

        # Spring-hook fastener (ground; cosmetic) -- the SEPARATE little open J-hook
        # that connects this channel's spring to the plate (the spring no longer
        # threads the plate itself). It seats shank-UP in the plate bore at
        # (hole_x_0 + arm_offset, z_mid) and presents its arm just above the
        # plate, threading the spring's bottom eye (fixed at (hole_x_0,
        # PLATE_EYE_Y, z_mid) for every pose). The part is modeled with its arm to
        # local +X; Ry(180) (the machine-frame z-plane turn) points that arm to
        # machine -X, back toward the eye one arm-offset away. The eye-axis tilt
        # (<=1.1 deg even at full amplitude) is well inside the bore/ring clearance.
        grounded_specs.append({
            "part": "spring-hook",
            "position": [hole_x_0 + HOOK_ARM_OFFSET_X,
                         PLATE_EYE_Y - HOOK_ARM_HEIGHT, z_mid],
            "rotation": [0.0, 180.0, 0.0],
            "rows": ROT_Y_180,
            "label": f"spring-hook ch{j:02d} bore-seat",
        })

    # Insert the cosmetic bank (springs + spring-hooks; the bushings were
    # patterned before the loop) in ONE AddComponents3 + ONE FixComponent
    # (ground=True). GROUNDED, not semantically mated -- PURELY a
    # build-performance measure (Pedro 2026-07-09, reversing the #110
    # treatment for THIS bank only; no kinematic or gate semantics change,
    # the parts were pinned to global datums and never articulated): both are
    # cosmetic with no operational DOF and no in-subassembly contact partner
    # (hooks seat in the summing plate, ANOTHER subassembly; springs' hook/ring
    # joints have perpendicular axes, no faithful concentric), so the old
    # locate battery only re-pinned the already-computed insert pose at the
    # price of ~140 late-assembly mate solves (~4-5 s each, v0.18.0). A fixed
    # exact-transform part also cannot flip. The per-channel amplitude tilt is
    # baked into spring_rows, so grounding holds for every preset -- the #113
    # vertical-only trap does not apply (nothing is re-derived from a mate).
    for spec in grounded_specs:
        spec["ground"] = True
    await place_components_batch(
        adapter, grounded_specs, label="cosmetic bank (springs + hooks, grounded)"
    )

    # Confirm both bushing banks landed on the inter-channel gap planes. The
    # explicit placements above are deterministic; this guards a future off-by-one
    # in the gap arithmetic (the prefix read also flags a stray instance).
    if CHANNELS > 1:
        z_gap_planes = [
            z_station(k) + ARM_MID_DZ + PITCH / 2.0 for k in range(CHANNELS - 1)
        ]
        _verify_pattern_z(adapter, "pivot-bushing", z_gap_planes, "pivot-bushing bank")
        _verify_pattern_z(adapter, "lever-bushing", z_gap_planes, "lever-bushing bank")

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
        adapter, len(free_dof_keys),
        required_stems=("rocker-arm", "connecting-rod", "amplitude-bar",
                        "channel-lever"))
    write_dof_manifest(ASM_NAME)
    check_no_interference(adapter)
    return await save_assembly_and_images(adapter, ASM_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
