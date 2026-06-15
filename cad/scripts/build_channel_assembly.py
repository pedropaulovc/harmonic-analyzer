r"""Reproduction script: channel subassembly (book ch. 13-17; 20 channels).

The complete 20-channel motion chain between the drive train and the
output: connecting rods riding the integral cams, the rocker-arm seesaw
bank on its pivot shaft, the amplitude bars running UP the spine, and the
top-lever bank on its fulcrum shaft with the channel springs hanging from
the lever tips. 144 components:

* pivot-shaft x1 (rocker bank at (-72.9, 253.8), along Z, centred z 0)
  + fulcrum-shaft x1 (lever bank at (-199.9, 1065.9), 182 long - the
  228.6 shaft clipped the west columns at top level, M6.5)
* pivot-ball-mount x4 (rocker pair: north on the rocker-support apex at
  (-72.9, 228.6, +101.6), south on the A-FRAME clevis saddle at
  (-72.9, 228.6, -111) - M6.5 photo audit: there is no south frustum,
  the front stand is the transgear A-frame (output.SLDASM) whose ears
  flank this mount's O16 base; lever pair on the top-frame west rail,
  seats (-199.9, 1040.7, +/-85) - z 85 keeps the O16 base clear of the
  O35 corner-boss bores)
* rocker-arm x20, pivot-bushing x19, connecting-rod x20,
  amplitude-bar x20, channel-lever x20, lever-bushing x19,
  channel-spring-installed x20 (M6.4: the stretched in-machine spring --
  the free 32 mm part stays for the ch. 17 table-top inset)

Default mechanism state (DIMENSIONS.md "Channel & top-frame layout"):
cylinder-gear notches +Y (cosine alignment), integral cam lobes -Y, rod
rings concentric on the cams at (-47.367, 121.721, z_j + 3.3) - the cam
centre carries the gears' +1.5 deg tooth-phase rotation. Everything
downstream is SOLVED here, not hard-coded: the rod-pin point is the
intersection of the r 25.4 circle about the pivot with the r 127 circle
about the ring centre (arm tilt ~ -11.54 deg, rod tilt ~ +0.23 deg Rz);
the bar rests its foot-notch roof on the tilted arm's top-edge arc
(contact at the bar's -X edge); the bar's top pin height tilts the levers
(~ +0.36 deg); the spring's top eye hangs 3.37 below the lever spring
hole so its ring threads the O4 hole without touching (margins asserted
> 0.1); the bottom lead drops through the summing-lever plate's O4.5
hole (at z_j - 1.95, one coil mean radius -Z of the spring axis) with
the end loop hanging under the plate (asserted clearances -- the plate
itself lives in output.SLDASM, checked at the top level).

Orientation notes: the amplitude bar is rotated 90 deg about its long
axis (Ry(90)) so its end slots and O2 top pin hole run across Z,
straddling the 2.5 arm / 3.0 lever; the spring is rotated 90 deg about Y
so its end-hook ring lies perpendicular to the lever face. Channel
stations: z_j = -67.1 + 7.0565 j, arm/bar/lever mid-planes at z_j + 0.8,
cam/rod plane z_j + 3.3 (rod tip strap face-flush against the arm).

Mated-DOF strategy: structure (shafts, ball mounts, bushings, cosmetic
springs) is grounded; the four moving parts per channel are inserted on
their exact mirrored transform and joined by real revolute joints
(rocker/lever concentric on the shaft OD, rod/bar coincident axis-to-axis
on the named bore axes), each pinned to its on-solution pose by an axial
distance + an off-pivot spin driver. The spin/axial dims are the per-
channel suppressible drivers, so the saved state stays fully defined
(0 DOF) for the gate while the joints stay free for a Motion study to
drive. Far-side mate flips are caught by reading back the origin and
re-adding flipped. Saved state: every component fixed or fully defined,
zero interference (face-flush and tangent contacts allowed).

The cams themselves live in drive-train.SLDASM (integral with the
cylinder gears); the frame, supports and top-frame ring in frame.SLDASM.
Cross-subassembly fits are checked at the top level (M6.5).

Dimensions: cad/DIMENSIONS.md ch. 14 layout + "Channel & top-frame
layout" tables.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_channel_assembly.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    assert_components_fully_defined,
    bore_axis_ref,
    check,
    check_no_interference,
    coincident_mate,
    concentric_mate,
    component_names,
    component_transform,
    distance_driver,
    log,
    named_ref,
    place_component,
    run_build,
    save_assembly_and_images,
    spin_driver,
    world_point,
)

ASM_NAME = "channel"

# --- machine stations -------------------------------------------------------
import os  # noqa: E402

CHANNELS = int(os.environ.get("CHANNEL_COUNT", "20"))  # test hook: build fewer
Z0 = -67.1  # channel 0 gear plane
PITCH = 7.0565
ARM_MID_DZ = 0.8  # arm/bar/lever mid-planes at z_j + 0.8
CAM_DZ = 3.3  # cam / rod-ring mid-plane at z_j + 3.3

# --- rocker bank ------------------------------------------------------------
PIVOT = (-72.9, 253.8)  # rocker pivot shaft axis (x, y)
ARM_PIVOT_LOCAL_Y = 8.0  # pivot hole at local (0, 8) in the arm
ARM_ROD_LEVER = 25.4  # rod pin 1" from the pivot
ARM_ARC_CENTER_LOCAL_Y = 816.0  # arm local arc centre above the bottom edge
ARM_TOP_RADIUS = 800.0

# --- drive interface (default state) ----------------------------------------
GEAR_PHASE_DEG = 1.5  # drive-train locks each cylinder gear at Rz(+1.5):
# half the T120 tooth pitch, so a TOOTH faces the cone mesh (see
# build_drive_train_assembly.py). The integral cam (local (0, -5.08))
# swings with the gear, so the true cam centre sits 5.08*sin(1.5deg) =
# 0.133 east of the arbor; assuming an unrotated cam dug every rod ring
# (bore R 25.5) 0.033 into its cam (R 25.4) - the 20 x 2.40 mm^3 M6.5
# top-level interferences.
CAM_ECC = 5.08  # build_cylinder_gear.ECCENTRICITY
RING_CENTER = (
    -47.5 + CAM_ECC * math.sin(math.radians(GEAR_PHASE_DEG)),
    126.8 - CAM_ECC * math.cos(math.radians(GEAR_PHASE_DEG)),
)  # phased cam centre: (-47.367, 121.721)
ROD_C2C = 127.0

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
BAR_CONTACT_GAP = 0.02

# --- lever bank -------------------------------------------------------------
FULCRUM = (-199.9, 1065.9)  # lever fulcrum shaft axis (x, y)
LEVER_BAR_PIN_X = 127.0
LEVER_SPRING_X = 177.8  # 7" c2c; the 254 "2:1" guess is photo-refuted (M6.4 -
# the lever bank ends at x ~ -30 in the ch. 30 front view and the 32 mm
# springs must reach the summing plate at x ~ -22..-27)
LEVER_TAB_HALF = 3.0  # spring hole sits in the lever's 6.0-tall end tab
LEVER_THICKNESS = 3.0

# --- supports / mounts ------------------------------------------------------
SUPPORT_APEX_Y = 228.6
SUPPORT_Z = 101.6  # north rocker-support apex (frame.SLDASM)
AFRAME_MOUNT_Z_ABS = 111.0  # south mount on the A-frame clevis (output.SLDASM)
RAIL_TOP_Y = 1040.7
LEVER_MOUNT_Z = 85.0  # clears the top-frame boss bores (DIMENSIONS.md)

# --- spring (build_channel_spring_installed.py locals) ----------------------
from build_channel_spring_installed import (  # noqa: E402
    BOTTOM_LEAD as SPRING_BOTTOM_LEAD,
    TOP_EYE_LOCAL_Y as SPRING_EYE_LOCAL_Y,  # 65.05: loop centre on the axis
)

SPRING_LOOP_R = 2.75  # = coil mean radius
SPRING_WIRE_DIA = 1.0
SPRING_EYE_DROP = 3.37  # top eye centre below the lever spring hole
SPRING_HOLE_DIA = 4.0  # build_channel_lever.py (O3 photo read enlarged: threading)

# --- summing-lever plate interface (build_summing_lever.py) ------------------
PLATE_TOP_Y = 998.0
PLATE_THICKNESS = 5.1
PLATE_HOLE_DIA = 4.5

IDENTITY = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
ROT_Y_POS90 = [[0.0, 0.0, -1.0], [0.0, 1.0, 0.0], [1.0, 0.0, 0.0]]


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


# --- mate scheme (validated single-channel probe) ---------------------------
# Both rocker-pivot and lever-fulcrum shafts ride O6.35 bores.
SHAFT_R = 6.35 / 2.0
# Off-pivot bore locals (mm, part frame) used by the spin drivers + world_point.
ROCKER_ROD_BORE_LOCAL = [25.4, 8.39937, 0.0]  # rocker Axis2 (rod pin)
ROD_STRAP_BORE_LOCAL = [0.0, 0.0, 0.0]  # rod Axis1 (cam ring centre = origin)
ROD_PIN_BORE_LOCAL = [0.0, 127.0, 0.0]  # rod Axis2 (rocker pin = swing pivot)
LEVER_BAR_PIN_BORE_LOCAL = [127.0, 0.0, 0.0]  # lever Axis2 (bar pin)
BAR_TOP_PIN_LOCAL = [3.175, 806.45, 3.175]  # bar Axis1 (swing pivot)
BAR_FOOT_LOCAL = [3.175, 0.0, 3.175]  # bar Axis2 (foot, ~806 mm arm)


def _org(adapter, name: str) -> list[float]:
    """A component's current origin (mm) in the assembly frame."""
    a = component_transform(adapter, name)
    return [a[9] * 1000.0, a[10] * 1000.0, a[11] * 1000.0]


def solve_default_state() -> dict[str, float]:
    """Solve the default-state kinematics; all downstream placements follow.

    Rod-pin point P: |P - pivot| = 25.4 and |P - ring centre| = 127, +X
    branch (rod side). Bar contact: highest point of the tilted arm's
    top-edge R800 arc within the bar's 6.35 footprint centred on the
    pivot x. Lever tilt: bar-pin chain height vs the fulcrum.
    """
    ox, oy = PIVOT
    cx, cy = RING_CENTER
    dx, dy = cx - ox, cy - oy
    d = math.hypot(dx, dy)
    a = (ARM_ROD_LEVER**2 - ROD_C2C**2 + d * d) / (2.0 * d)
    h = math.sqrt(ARM_ROD_LEVER**2 - a * a)
    ux, uy = dx / d, dy / d
    # +X branch (rod side): u points down-right (uy < 0), so the
    # perpendicular (-uy, ux) has a positive x component; the (uy, -ux)
    # branch lands at x ~ -94, behind the pivot.
    px = ox + a * ux - h * uy
    py = oy + a * uy + h * ux
    arm_tilt = math.degrees(math.atan2(py - oy, px - ox))
    rod_tilt = math.degrees(math.atan2(px - cx, py - cy))
    rod_tilt = -rod_tilt  # atan2(x, y) measures from +Y; Rz is CCW from +X

    # Tilted arm: local arc centre (0, 816) about the pivot hole (0, 8).
    t = math.radians(arm_tilt)
    rel = ARM_ARC_CENTER_LOCAL_Y - ARM_PIVOT_LOCAL_Y
    acx = ox - rel * math.sin(t)
    acy = oy + rel * math.cos(t)
    bar_left = ox - BAR_WIDTH / 2.0  # contact at the bar's -X edge (arc max)
    contact_y = acy - math.sqrt(ARM_TOP_RADIUS**2 - (bar_left - acx) ** 2)
    contact_alt = acy - math.sqrt(
        ARM_TOP_RADIUS**2 - (ox + BAR_WIDTH / 2.0 - acx) ** 2
    )
    if contact_alt > contact_y:
        raise RuntimeError("bar contact expected at the -X edge; check tilt sign")

    bar_bottom = contact_y - BAR_FOOT_NOTCH + BAR_CONTACT_GAP
    pin_y = bar_bottom + BAR_LENGTH - BAR_TOP_PIN_DROP
    lever_tilt = math.degrees(math.asin((pin_y - FULCRUM[1]) / LEVER_BAR_PIN_X))
    return {
        "arm_tilt": arm_tilt,
        "rod_tilt": rod_tilt,
        "pin_x": px,
        "pin_y": py,
        "contact_y": contact_y,
        "bar_bottom": bar_bottom,
        "bar_pin_y": pin_y,
        "lever_tilt": lever_tilt,
    }


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
) -> None:
    """Build one revolute joint pinned to its on-solution pose.

    ``concentric`` selects the radial mate kind: a cylindrical-face ↔ named-axis
    pair is *concentric* (shaft OD vs bore), two named axes are *coincident*
    (collinear lines = coaxial; AddMate5 rejects concentric on two axes). Then
    a Front/Right-plane *axial* distance pins the Z slide, and a ``spin_driver``
    on an off-pivot bore pins the residual spin -> fully defined, on-target.
    The spin/axial dims are the per-channel suppressible drivers.
    """
    tgt = _org(adapter, comp)
    # Capture the off-axis (spin) target at the PLACED design pose, BEFORE the
    # radial/axial mates run. Measuring it afterwards freezes whatever sub-mm
    # pose the mate solve drifted to -- for the connecting-rod that drift (~0.4
    # mm swing about the rocker pin) threw the cam ring off the cylinder-gear
    # lobe and broke the top-level interference gate (38.92 mm^3 x 20). Each
    # part is inserted on its exact mirrored transform, so the design pose IS
    # the on-solution target.
    off_design = world_point(adapter, comp, off_axis_local)
    radial = concentric_mate if concentric else coincident_mate
    await radial(adapter, axis_a, axis_b, label=f"{label} radial", verify=(comp, tgt))
    # Bar is Ry(90): its Right Plane (local x=0) is the Z mid reference; the
    # Rz parts use their Front Plane (the sketch mid-plane). off-axis [_,_,z]
    # locals carry the marker.
    axial_plane = "Right Plane" if comp.startswith("amplitude-bar") else "Front Plane"
    await distance_driver(
        adapter,
        named_ref(f"{axial_plane}@{comp}", "PLANE"),
        named_ref("Front Plane", "PLANE"),
        abs(tgt[2]),
        label=f"{label} axial d={abs(tgt[2]):.2f}",
        verify=(comp, tgt),
    )
    await spin_driver(
        adapter,
        named_ref(f"{off_axis_name}@{comp}", "AXIS"),
        pivot_xy,
        (off_design[0], off_design[1]),
        label=f"{label} spin -> {off_design[0]:.1f},{off_design[1]:.1f}",
        verify=(comp, tgt),
    )


async def _pin_design_pose(
    adapter,
    comp: str,
    *,
    ring_local: list[float],
    pin_local: list[float],
    label: str,
) -> None:
    """Pin a planar Z-aligned link at its exact placed (design) pose.

    The connecting-rod bridges a channel-internal joint (its pin bore rides the
    rocker rod-bore) and an EXTERNAL one (its cam ring rides a drive-train
    cylinder-gear lobe, a 0.1 mm-clearance journal resolved at the top level).
    Those two spans are 0.39 mm inconsistent with the rod's fixed 127 mm bore
    spacing -- a pre-existing layout slack the old fix-all build hid by letting
    the pin float 0.4 mm off the rocker bore. A proper pin<->bore coincident
    instead snaps the pin exact and throws the ring 0.39 mm off the lobe ->
    top-level interference. The cam journal is the tight constraint, so pin the
    RING exactly (on the lobe centre) and let the 0.39 mm sit at the loose pin,
    exactly as the green build did. The real rod<->rocker + rod<->cam revolutes
    are established in the motion study (artifact B), where the rod is flexible.

    Scheme = the validated prismatic pattern (slide axis Z = Axis1, the ring
    bore): two axis-to-plane distances pin X/Y (and the two axis tilts), a spin
    driver pins rotation about Z via the pin bore, a Front-plane distance pins Z.
    """
    ring = world_point(adapter, comp, ring_local)
    pin = world_point(adapter, comp, pin_local)
    await distance_driver(
        adapter, named_ref(f"Axis1@{comp}", "AXIS"), named_ref("Right Plane", "PLANE"),
        abs(ring[0]), label=f"{label} ring-X", verify=(comp, ring),
    )
    await distance_driver(
        adapter, named_ref(f"Axis1@{comp}", "AXIS"), named_ref("Top Plane", "PLANE"),
        abs(ring[1]), label=f"{label} ring-Y", verify=(comp, ring),
    )
    await spin_driver(
        adapter, named_ref(f"Axis2@{comp}", "AXIS"),
        (ring[0], ring[1]), (pin[0], pin[1]),
        label=f"{label} swing -> pin {pin[0]:.1f},{pin[1]:.1f}", verify=(comp, ring),
    )
    await distance_driver(
        adapter, named_ref(f"Front Plane@{comp}", "PLANE"), named_ref("Front Plane", "PLANE"),
        abs(ring[2]), label=f"{label} ring-Z", verify=(comp, ring),
    )


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


def _assert_plate_threading(eye_y: float) -> None:
    """Assert the bottom attachment clears the summing-lever plate.

    The bottom lead (a straight O1 wire one coil mean radius -Z of the
    spring axis) drops through the plate's O4.5 hole; the end loop hangs
    fully under the plate. Checks: loop top vs plate bottom, coil bottom
    wire vs plate top, lead vs bore (lead centred: hole r - wire r).
    """
    bottom_eye_y = eye_y - SPRING_EYE_LOCAL_Y - SPRING_BOTTOM_LEAD
    plate_bottom = PLATE_TOP_Y - PLATE_THICKNESS
    wire_r = SPRING_WIRE_DIA / 2.0
    loop_top = bottom_eye_y + SPRING_LOOP_R + wire_r
    coil_bottom_wire = bottom_eye_y + SPRING_BOTTOM_LEAD - wire_r
    margin_loop = plate_bottom - loop_top
    margin_coil = coil_bottom_wire - PLATE_TOP_Y
    margin_bore = PLATE_HOLE_DIA / 2.0 - wire_r
    if margin_loop < 0.02 or margin_coil < 0.02:
        raise RuntimeError(
            f"plate threading margins too small: loop-under-plate"
            f" {margin_loop:.3f}, coil-over-plate {margin_coil:.3f}"
        )
    log(
        f"plate threading: bottom eye y {bottom_eye_y:.2f}, loop-under-plate"
        f" margin {margin_loop:.2f}, coil-over-plate margin {margin_coil:.2f},"
        f" lead bore clearance {margin_bore:.2f}"
    )


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ComponentLinearPatternParameters

    state = solve_default_state()
    log(
        "default state: arm tilt %.3f deg, rod tilt %.3f deg, pin (%.2f, %.2f),"
        % (state["arm_tilt"], state["rod_tilt"], state["pin_x"], state["pin_y"])
    )
    log(
        "  bar contact %.3f, bar bottom %.3f, bar pin y %.3f, lever tilt %.3f deg"
        % (state["contact_y"], state["bar_bottom"], state["bar_pin_y"], state["lever_tilt"])
    )

    phi = math.radians(state["lever_tilt"])
    spring_hole_x = FULCRUM[0] + LEVER_SPRING_X * math.cos(phi)
    spring_hole_y = FULCRUM[1] + LEVER_SPRING_X * math.sin(phi)
    eye_y = spring_hole_y - SPRING_EYE_DROP
    _assert_spring_threading(spring_hole_y, eye_y)
    _assert_plate_threading(eye_y)

    # Bushing clearance under the bar foot at d = 0 (geometry gate).
    bar_clearance = state["bar_bottom"] - PIVOT[1]
    if bar_clearance < 5.5:
        raise RuntimeError(f"bar passes only {bar_clearance:.2f} above the shaft")

    check("create_assembly", await adapter.create_assembly())

    # Shafts (ground; first insert auto-fixes). The shaft axes in the FINAL
    # mirrored frame (x -> -x) anchor the rocker/lever concentrics.
    await place_component(
        adapter, "pivot-shaft", [PIVOT[0], PIVOT[1], 0.0], [0.0, 0.0, 0.0],
        IDENTITY, label="pivot-shaft (rocker)",
    )
    await place_component(
        adapter, "fulcrum-shaft", [FULCRUM[0], FULCRUM[1], 0.0], [0.0, 0.0, 0.0],
        IDENTITY, label="fulcrum-shaft (lever bank)",
    )
    pivot_w = (-PIVOT[0], PIVOT[1])  # (72.9, 253.8)
    fulc_w = (-FULCRUM[0], FULCRUM[1])  # (199.9, 1065.9)
    pivot_od = [pivot_w[0] + SHAFT_R, pivot_w[1], 0.0]
    fulc_od = [fulc_w[0] + SHAFT_R, fulc_w[1], 0.0]

    # Ball mounts (ground). The rocker pair is asymmetric (M6.5): north seats
    # on the rocker-support apex, south on the A-frame clevis saddle (both
    # tops at y 228.6).
    for mount_z in (-AFRAME_MOUNT_Z_ABS, SUPPORT_Z):
        await place_component(
            adapter, "pivot-ball-mount",
            [PIVOT[0], SUPPORT_APEX_Y, mount_z],
            [0.0, 0.0, 0.0], IDENTITY, label=f"ball-mount rocker z{mount_z:+.0f}",
        )
    for sz in (-1.0, 1.0):
        await place_component(
            adapter, "pivot-ball-mount",
            [FULCRUM[0], RAIL_TOP_Y, sz * LEVER_MOUNT_Z],
            [0.0, 0.0, 0.0], IDENTITY, label=f"ball-mount lever z{sz * LEVER_MOUNT_Z:+.0f}",
        )

    # Per-channel chain: the four moving parts are inserted on-solution
    # (ground=False) and joined by revolutes whose spin/axial dims are the
    # per-channel suppressible drivers (see _revolute).
    arm_rows = rot_z_rows(state["arm_tilt"])
    rod_rows = rot_z_rows(state["rod_tilt"])
    lever_rows = rot_z_rows(state["lever_tilt"])
    t = math.radians(state["arm_tilt"])
    arm_origin_dx = ARM_PIVOT_LOCAL_Y * math.sin(t)  # -(0,8)*Rz offset
    arm_origin_dy = ARM_PIVOT_LOCAL_Y * math.cos(t)

    # Grounded repeated structure (spring x20, two bushing banks x19) is placed
    # ONCE as a seed in channel 0 and replicated by a LocalLinearPattern along
    # the Z shaft axis after the loop. The moving parts stay individual mated
    # instances: a pattern instance is a rigid slave with no DOF, and the
    # channels must articulate independently (each runs at a different harmonic
    # frequency) for the Motion study. pivot_od (a shaft-OD point) selects the
    # Z-parallel cylindrical face = the pattern direction axis.
    spring_seed = pivot_bush_seed = lever_bush_seed = ""

    for j in range(CHANNELS):
        zj = z_station(j)
        z_mid = zj + ARM_MID_DZ

        rocker = await place_component(
            adapter, "rocker-arm",
            [PIVOT[0] + arm_origin_dx, PIVOT[1] - arm_origin_dy, z_mid],
            [0.0, 0.0, state["arm_tilt"]], arm_rows,
            ground=False, label=f"rocker-arm ch{j:02d}",
        )
        rod = await place_component(
            adapter, "connecting-rod",
            [RING_CENTER[0], RING_CENTER[1], zj + CAM_DZ],
            [0.0, 0.0, state["rod_tilt"]], rod_rows,
            ground=False, label=f"connecting-rod ch{j:02d}",
        )
        # Bar rotated 90 about Y: local X (slot direction) -> -Z, local
        # Z (depth) -> +X; slot centre (local x 3.175) lands on z_mid.
        bar = await place_component(
            adapter, "amplitude-bar",
            [
                PIVOT[0] - BAR_WIDTH / 2.0,
                state["bar_bottom"],
                z_mid + BAR_WIDTH / 2.0,
            ],
            [0.0, 90.0, 0.0], ROT_Y_POS90,
            ground=False, label=f"amplitude-bar ch{j:02d}",
        )
        lever = await place_component(
            adapter, "channel-lever",
            [FULCRUM[0], FULCRUM[1], z_mid],
            [0.0, 0.0, state["lever_tilt"]], lever_rows,
            ground=False, label=f"channel-lever ch{j:02d}",
        )

        # J1 rocker revolute (shaft OD ↔ pivot bore; spin via the rod bore).
        await _revolute(
            adapter, rocker,
            bore_axis_ref(pivot_od), named_ref(f"Axis1@{rocker}", "AXIS"),
            concentric=True, off_axis_name="Axis2",
            off_axis_local=ROCKER_ROD_BORE_LOCAL, pivot_xy=pivot_w,
            label=f"J1 rocker ch{j:02d}",
        )
        # J2 connecting-rod: pinned at its exact design pose so the cam ring sits
        # ON the cylinder-gear lobe centre (the tight external journal), not
        # snapped to the rocker pin (which would throw the ring 0.39 mm off the
        # lobe -- see _pin_design_pose). The rod<->rocker revolute lives in the
        # motion study where the rod is flexible.
        await _pin_design_pose(
            adapter, rod,
            ring_local=ROD_STRAP_BORE_LOCAL, pin_local=ROD_PIN_BORE_LOCAL,
            label=f"J2 rod ch{j:02d}",
        )
        # J4 lever revolute (fulcrum OD ↔ fulcrum bore; spin via the bar pin).
        await _revolute(
            adapter, lever,
            bore_axis_ref(fulc_od), named_ref(f"Axis1@{lever}", "AXIS"),
            concentric=True, off_axis_name="Axis2",
            off_axis_local=LEVER_BAR_PIN_BORE_LOCAL, pivot_xy=fulc_w,
            label=f"J4 lever ch{j:02d}",
        )
        # J3 bar — the amplitude-setting joint (p0). A real revolute hinges the
        # bar at its top pin (Axis1@bar) coaxial with the lever's bar pin
        # (Axis2@lever). The bar length equals the rocker's R800 arc radius, so
        # the top pin rides the arc CENTRE while the foot rides the R800 arc
        # itself (build_rocker_arm docstring): swinging the bar about the top pin
        # slides the foot ALONG the arc, and that swing IS the amplitude DOF
        # (±88 mm seesaw, ch.15). The swing is pinned by ONE suppressible PARK
        # DRIVER — a distance from the foot axis (Axis2@bar) to the assembly
        # Right Plane, i.e. the foot's X = the amplitude position. Default =
        # today's solved contact, so `rest` is bit-exact; suppressing it (the
        # motion study / an amplitude config) frees the bar to swing = slide the
        # foot along the arc. The driver MUST stay a part↔root-plane distance
        # (NOT part↔part): the motion study's driver classifier only recognises
        # dims that reference one real part + the sub root. This is the explicit
        # form of the generic foot-X spin_driver the other revolutes use.
        bar_tgt = _org(adapter, bar)
        foot = world_point(adapter, bar, BAR_FOOT_LOCAL)
        amplitude = foot[0] - pivot_w[0]  # foot X relative to the rocker pivot
        await coincident_mate(
            adapter,
            named_ref(f"Axis2@{lever}", "AXIS"), named_ref(f"Axis1@{bar}", "AXIS"),
            label=f"J3 bar ch{j:02d} radial (top-pin hinge)", verify=(bar, bar_tgt),
        )
        await distance_driver(
            adapter,
            named_ref(f"Right Plane@{bar}", "PLANE"), named_ref("Front Plane", "PLANE"),
            abs(bar_tgt[2]),
            label=f"J3 bar ch{j:02d} axial d={abs(bar_tgt[2]):.2f}", verify=(bar, bar_tgt),
        )
        await distance_driver(
            adapter,
            named_ref(f"Axis2@{bar}", "AXIS"), named_ref("Right Plane", "PLANE"),
            abs(foot[0]),
            label=f"J3 bar ch{j:02d} AMPLITUDE park foot-X={foot[0]:.2f} (amp {amplitude:+.1f})",
            verify=(bar, bar_tgt),
        )

        # Spring + bushing SEEDS (ground; cosmetic in artifact A) -- inserted
        # only at the TOP channel, then replicated DOWN the spine by a pattern
        # after the loop. The shaft-OD direction reference (pivot_od) evaluates
        # to the -Z sense, so the seed sits at the high-Z end and the copies
        # fill toward channel 0 (verified on-plane after the loop). The spring
        # is rotated 90 about Y: eye ring perpendicular to the lever face; top
        # eye centre (local (0, 65.05)) is on the axis, Ry-invariant; bottom
        # lead lands at z_mid - 2.75.
        if j == CHANNELS - 1:
            spring_seed = await place_component(
                adapter, "channel-spring-installed",
                [spring_hole_x, eye_y - SPRING_EYE_LOCAL_Y, z_mid],
                [0.0, 90.0, 0.0], ROT_Y_POS90,
                label=f"channel-spring seed ch{j:02d}",
            )
            if CHANNELS > 1:
                z_gap_top = z_mid - PITCH / 2.0  # gap below the top channel
                pivot_bush_seed = await place_component(
                    adapter, "pivot-bushing",
                    [PIVOT[0], PIVOT[1], z_gap_top],
                    [0.0, 0.0, 0.0], IDENTITY,
                    label=f"pivot-bushing seed {j - 1:02d}/{j:02d}",
                )
                lever_bush_seed = await place_component(
                    adapter, "lever-bushing",
                    [FULCRUM[0], FULCRUM[1], z_gap_top],
                    [0.0, 0.0, 0.0], IDENTITY,
                    label=f"lever-bushing seed {j - 1:02d}/{j:02d}",
                )

    # Replicate the grounded seeds along the Z shaft axis (pivot_od selects the
    # shaft's Z-parallel cylindrical face). Springs span all CHANNELS; the two
    # bushing banks fill the CHANNELS-1 inter-channel gaps. Moving parts are
    # deliberately NOT patterned (each must keep its own DOF).
    if CHANNELS > 1:
        for seed, n, lbl in (
            (spring_seed, CHANNELS, "channel-spring"),
            (pivot_bush_seed, CHANNELS - 1, "pivot-bushing"),
            (lever_bush_seed, CHANNELS - 1, "lever-bushing"),
        ):
            check(
                f"linear-pattern {lbl} x{n}",
                await adapter.pattern_components_linear(
                    ComponentLinearPatternParameters(
                        components=[seed],
                        count=n,
                        spacing=PITCH,
                        direction_point=pivot_od,
                    )
                ),
            )
        # Positively confirm the copies landed on the channel/gap planes.
        z_mid_planes = [z_station(k) + ARM_MID_DZ for k in range(CHANNELS)]
        z_gap_planes = [
            z_station(k) + ARM_MID_DZ + PITCH / 2.0 for k in range(CHANNELS - 1)
        ]
        _verify_pattern_z(adapter, "channel-spring-installed", z_mid_planes, "spring pattern")
        _verify_pattern_z(adapter, "pivot-bushing", z_gap_planes, "pivot-bushing pattern")
        _verify_pattern_z(adapter, "lever-bushing", z_gap_planes, "lever-bushing pattern")

    assert_components_fully_defined(adapter)
    check_no_interference(adapter)
    return await save_assembly_and_images(adapter, ASM_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
