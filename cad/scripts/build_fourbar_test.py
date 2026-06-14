r"""MINIMAL channel test: cam -> rod -> rocker -> amplitude-bar -> channel-lever.

A throwaway test rig that isolates ONE channel's full drive chain from the
144-part channel.SLDASM, built from scratch and driven under Basic Motion (the
same solver the deliverable uses). Updated per user review of the first cut:

  1. The rocker must OSCILLATE, not spin 360 deg. The motor no longer sits on
     the rocker pivot -- it spins the ECCENTRIC CAM, exactly as the real
     machine does. Cam (5.08 mm eccentricity) -> connecting-rod (127 c2c) ->
     rocker rod-pin (25.4 from the pivot) is a Grashof crank-rocker: the cam
     turns fully, the rocker rocks ~+/-11 deg (= asin(5.08/25.4)). That swing
     is set by the real cam geometry, not chosen.
  2. The rocker and lever could slide along their shaft axes and pull off the
     amplitude bar (a concentric/coincident pin leaves the axial DOF free).
     Every moving part now gets an axial plane lock (a coincident/distance
     mate, held rigid by Basic Motion) so nothing drifts off its pin.

Parts: pivot-shaft + fulcrum-shaft + arbor (3 grounded shafts = the frame) and
eccentric-cam + connecting-rod + rocker-arm + amplitude-bar + channel-lever
(5 moving parts). The kinematic chain (all pin axes along Z):

  * cam bore     -- concentric on the arbor (revolute, MOTOR-driven)
  * cam disc OD  -- connecting-rod strap bore concentric on it (the eccentric)
  * rod pin      -- connecting-rod Axis2 coincident to the rocker rod-bore
  * rocker pivot -- concentric on the pivot-shaft (the see-saw)
  * foot pin     -- bar Axis2 (foot) coincident to a Z-axis built into the
                    rocker at local (COEFF, arc_y): the operating coefficient
  * top pin      -- lever Axis2 (bar pin) coincident to bar Axis1 (top pin)
  * lever fulcrum-- concentric on the fulcrum-shaft (the output)

Reference axes (rocker arc-point, cam bore) are created on the SHARED part docs
(ActivateDoc3 round-trip, parts NEVER saved). The assembly is NEVER saved --
this is a diagnostic; the result is the printed spans + an exported mp4 + views.

  C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_fourbar_test.py
"""

from __future__ import annotations

import asyncio
import math
import os
import sys

from _common import (
    OUT_PNG, _flag, _read_member, assert_model_healthy, bore_axis_ref, check,
    coincident_mate, component_transform, concentric_mate, distance_driver,
    log, named_ref, place_component,
)
from build_motion_study import _entity_ref, _rot_angle, assert_motion_progressed
from solidworks_mcp.adapters.solidworks.assembly import _byref_i4

# --- geometry (design / pre-mirror frame, mm) -------------------------------
SHAFT_R = 6.35 / 2.0
ARC_CENTER_Y = 816.0          # rocker R800 arc centre, local
ARC_R = 800.0
# foot offset along the rocker arc from the pivot = the per-channel amplitude
# coefficient. +ve one side, 0 = above the pivot (zero amplitude), -ve = the
# other side of the see-saw (inverted amplitude). Override via FOURBAR_COEFF.
COEFF = float(os.environ.get("FOURBAR_COEFF", "60.0"))
# Foot-pin scheme under test:
#   "coincident" -- bar foot Axis2 COINCIDENT to a Z-axis built on the rocker at
#                   (COEFF, arc_y); the proven minimal-rig pin.
#   "distance"   -- bar foot Axis2 pinned by TWO DISTANCE mates (to the rocker
#                   arc-centre point = R, to the pivot axis = r_foot), exactly
#                   the full-study _add_foot_arc_joints scheme. This A/B test
#                   decides whether the distance-foot transmits at a REAL
#                   coefficient (the full assembly only ever ran it at ~0).
FOOT_MODE = os.environ.get("FOURBAR_FOOT", "coincident")
TAG = os.environ.get("FOURBAR_TAG", f"coeff_{COEFF:+.0f}_{FOOT_MODE}")

# eccentric cam + connecting rod (build_eccentric_cam.py / build_connecting_rod.py)
CAM_R = 50.8 / 2.0            # disc OD radius (the journal the rod strap rides)
CAM_ECC = 5.08               # disc centre offset -Y from the bore (the throw)
ROD_C2C = 127.0              # rod strap centre -> rod pin

# rocker rod-pin local (build_rocker_arm.py: ROD_HOLE_X, _mid_y(ROD_HOLE_X))
ARM_ROD_X = 25.4
ARM_DEPTH = 16.0
R_TOP = 800.0
R_BOT = R_TOP + ARM_DEPTH     # 816

# rocker arc-centre + pivot locals (build_motion_study.py) for the distance foot
ROCKER_ARC_EDGE_MM = [0.0, 16.0, 1.25]      # a point on the R800 top edge
ROCKER_ARC_CENTER_LOCAL = [0.0, 816.0, 0.0]  # R800 arc centre
ROCKER_PIVOT_LOCAL = [0.0, 8.0, 0.0]        # pivot bore = rocker Axis1

# bar / lever named-bore locals (from build_channel_assembly.py)
BAR_FOOT_LOCAL = [3.175, 0.0, 3.175]        # bar Axis2 (foot)
BAR_TOP_PIN_LOCAL = [3.175, 806.45, 3.175]  # bar Axis1 (top pin)
LEVER_BAR_PIN_LOCAL = [127.0, 0.0, 0.0]     # lever Axis2 (bar pin)

IDENT = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
# Bar bores run along its LOCAL X (Top n Front planes); the bar must be rotated
# Ry(90) so they become the assembly Z (rotation) axis -- as build_channel does.
ROT_Y_POS90 = [[0.0, 0.0, -1.0], [0.0, 1.0, 0.0], [1.0, 0.0, 0.0]]

# Z stations (mm): parts stacked so pin-mated faces sit beside each other.
Z_ROCKER = 0.0
Z_LEVER = 0.0
Z_BAR = 3.175      # bar slot centred on z=0 after Ry(90)
Z_ROD = 2.5        # rod tip strap face-flush beside the 2.5 arm; ring at z 2.5
Z_CAM = -2.5       # cam disc (10.16 thick) spans the rod ring at z 2.5

# motor / solve
CAM_SPEED = 2.0    # rotary motor on the cam (Basic Motion: ~115 deg/s at 2)
DURATION_S = 4.0   # ~1.3 cam revolutions -> a full rocker oscillation cycle
STEPS = 32

# Set True if the foot-pin coincident yanks the bar (plane offset normal flipped).
FLIP_PIN_PLANE = False


def _arc_y(x: float) -> float:
    return ARC_CENTER_Y - math.sqrt(ARC_R**2 - x * x)


def _mid_y(x: float) -> float:
    """Rocker top/bottom-edge mid height at local x (= bore-axis y)."""
    by = R_BOT - math.sqrt(R_BOT**2 - x * x)
    ty = R_BOT - math.sqrt(R_TOP**2 - x * x)
    return (by + ty) / 2.0


def _org(adapter, comp: str) -> list[float]:
    a = component_transform(adapter, comp)
    return [a[9] * 1000.0, a[10] * 1000.0, a[11] * 1000.0]


async def _make_part_z_axis(adapter, comp_name: str, x_off: float, y_off: float,
                            label: str) -> str:
    """Create a Z-axis at part-local (x_off, y_off) on a SHARED part doc.

    Intersection of an offset-from-Right plane (x) and an offset-from-Top plane
    (y); a zero offset uses the principal plane by name. Built in the PART doc
    (ActivateDoc3 round-trip) so it moves with the component; NEVER saved.
    Returns the new axis name."""
    from solidworks_mcp.adapters.base import CreateAxisParameters, CreatePlaneParameters

    comp = adapter.currentModel.GetComponentByName(comp_name)
    _flag(comp, "IComponent2")
    part = adapter._attempt(lambda: comp.GetModelDoc2(), default=None)
    if part is None:
        raise RuntimeError(f"{comp_name} part doc unresolved")
    top = adapter.currentModel
    top_title = str(_read_member(top, "GetTitle"))
    part_title = str(_read_member(part, "GetTitle"))
    adapter._attempt(
        lambda: adapter.swApp.ActivateDoc3(part_title, False, 2, _byref_i4()), default=None)
    adapter.currentModel = adapter._attempt(lambda: adapter.swApp.ActiveDoc, default=part)
    try:
        if abs(x_off) > 1e-9:
            px = check(f"{label} plane x", await adapter.create_plane(CreatePlaneParameters(
                mode="offset", base_plane="Right Plane",
                offset=abs(x_off), flip=(x_off < 0) ^ FLIP_PIN_PLANE))).name
        else:
            px = "Right Plane"
        if abs(y_off) > 1e-9:
            py = check(f"{label} plane y", await adapter.create_plane(CreatePlaneParameters(
                mode="offset", base_plane="Top Plane",
                offset=abs(y_off), flip=(y_off < 0)))).name
        else:
            py = "Top Plane"
        ax = check(f"{label} axis", await adapter.create_axis(CreateAxisParameters(
            mode="two_planes", planes=[px, py]))).name
    finally:
        adapter._attempt(
            lambda: adapter.swApp.ActivateDoc3(top_title, False, 2, _byref_i4()), default=None)
        adapter.currentModel = top
    log(f"  {label} axis = {ax!r} at part-local ({x_off:.2f}, {y_off:.2f})")
    return ax


async def _make_part_arc_point(adapter, comp_name: str, edge_mm: list[float],
                               label: str) -> str:
    """Create an arc-centre RefPoint on a SHARED part doc (round-trip, not saved).

    Mirrors build_motion_study._add_rocker_arc_point: select a point on a
    circular edge, RefPoint at its arc centre. Returns the point feature name."""
    from solidworks_mcp.adapters.base import CreateReferencePointParameters

    comp = adapter.currentModel.GetComponentByName(comp_name)
    _flag(comp, "IComponent2")
    part = adapter._attempt(lambda: comp.GetModelDoc2(), default=None)
    if part is None:
        raise RuntimeError(f"{comp_name} part doc unresolved")
    top = adapter.currentModel
    top_title = str(_read_member(top, "GetTitle"))
    part_title = str(_read_member(part, "GetTitle"))
    adapter._attempt(
        lambda: adapter.swApp.ActivateDoc3(part_title, False, 2, _byref_i4()), default=None)
    adapter.currentModel = adapter._attempt(lambda: adapter.swApp.ActiveDoc, default=part)
    try:
        pt = check(f"{label} RefPoint", await adapter.create_reference_point(
            CreateReferencePointParameters(mode="arc_center", edge_point=edge_mm)))
        name = pt.get("name") if isinstance(pt, dict) else getattr(pt, "name", None)
    finally:
        adapter._attempt(
            lambda: adapter.swApp.ActivateDoc3(top_title, False, 2, _byref_i4()), default=None)
        adapter.currentModel = top
    if not name:
        raise RuntimeError(f"{label} RefPoint returned no name")
    log(f"  {label} point = {name!r} on {part_title}")
    return name


async def _axial_lock(adapter, comp: str, plane: str = "Front Plane") -> None:
    """Pin a part's slide along its (Z) pin axis to its placed Z.

    A revolute/pin leaves translation along the axis free, so the rocker/lever
    could drift off the amplitude bar. A coincident (z=0) or distance plane
    mate removes it; Basic Motion holds it rigid, leaving the spin DOF intact.
    """
    z = _org(adapter, comp)[2]
    ref_comp = named_ref(f"{plane}@{comp}", "PLANE")
    ref_asm = named_ref("Front Plane", "PLANE")
    tgt = _org(adapter, comp)
    if abs(z) < 1e-6:
        await coincident_mate(adapter, ref_comp, ref_asm,
                              label=f"{comp} axial lock z=0", verify=(comp, tgt))
        return
    await distance_driver(adapter, ref_comp, ref_asm, abs(z),
                          label=f"{comp} axial lock z={abs(z):.2f}", verify=(comp, tgt))


async def build(adapter) -> None:
    from solidworks_mcp.adapters.base import (
        MotionMotorParameters, MotionStudyParameters, MotionStudyRefParameters,
        MotionTimeParameters,
    )

    check("create_assembly", await adapter.create_assembly())

    # --- design-frame placements (place_component applies the machine mirror) --
    pivot_xy = (0.0, 0.0)
    foot_w = (COEFF, _arc_y(COEFF) - 8.0)            # rocker origin = (0,-8); foot world
    top_pin_w = (foot_w[0], foot_w[1] + BAR_TOP_PIN_LOCAL[1])
    fulcrum_xy = (top_pin_w[0] - LEVER_BAR_PIN_LOCAL[0], top_pin_w[1])
    log(f"design: pivot{pivot_xy} foot{foot_w} top_pin{top_pin_w} fulcrum{fulcrum_xy}")

    # frame shafts: rocker pivot + lever fulcrum (the cam arbor is added once we
    # know the rod-pin's true world position).
    await place_component(adapter, "pivot-shaft", [pivot_xy[0], pivot_xy[1], 0.0],
                          [0.0, 0.0, 0.0], IDENT, label="pivot-shaft")
    await place_component(adapter, "fulcrum-shaft", [fulcrum_xy[0], fulcrum_xy[1], 0.0],
                          [0.0, 0.0, 0.0], IDENT, label="fulcrum-shaft")

    # rocker first, so we can read the rod-pin's mirrored world coords and place
    # the cam/arbor/rod 127 mm below it (the rod runs ~vertical at the default).
    rocker = await place_component(adapter, "rocker-arm",
                                   [0.0, -8.0, Z_ROCKER], [0.0, 0.0, 0.0], IDENT,
                                   ground=False, label="rocker-arm")
    from _common import world_point
    rod_pin_w = world_point(adapter, rocker, [ARM_ROD_X, _mid_y(ARM_ROD_X), 0.0])
    log(f"  rocker rod-pin world = ({rod_pin_w[0]:.2f}, {rod_pin_w[1]:.2f})")

    # cam bore is the rotation axis: ECC above the disc, the disc 127 below the
    # rod pin. World x is mirrored, so un-mirror (negate x) for place_component.
    ring_w = (rod_pin_w[0], rod_pin_w[1] - ROD_C2C)             # disc / rod strap centre
    bore_w = (ring_w[0], ring_w[1] + CAM_ECC)                   # cam rotation axis
    arbor_design = (-bore_w[0], bore_w[1])
    rod_design = (-ring_w[0], ring_w[1])
    log(f"  cam bore world ({bore_w[0]:.2f}, {bore_w[1]:.2f}); "
        f"disc/ring world ({ring_w[0]:.2f}, {ring_w[1]:.2f})")

    await place_component(adapter, "pivot-shaft", [arbor_design[0], arbor_design[1], 0.0],
                          [0.0, 0.0, 0.0], IDENT, label="arbor (cam shaft)")
    cam = await place_component(adapter, "eccentric-cam",
                                [arbor_design[0], arbor_design[1], Z_CAM],
                                [0.0, 0.0, 0.0], IDENT, ground=False, label="eccentric-cam")
    rod = await place_component(adapter, "connecting-rod",
                                [rod_design[0], rod_design[1], Z_ROD],
                                [0.0, 0.0, 0.0], IDENT, ground=False, label="connecting-rod")
    bar = await place_component(adapter, "amplitude-bar",
                                [foot_w[0] - BAR_FOOT_LOCAL[2], foot_w[1], Z_BAR],
                                [0.0, 90.0, 0.0], ROT_Y_POS90,
                                ground=False, label="amplitude-bar")
    lever = await place_component(adapter, "channel-lever",
                                  [fulcrum_xy[0], fulcrum_xy[1], Z_LEVER],
                                  [0.0, 0.0, 0.0], IDENT, ground=False, label="channel-lever")

    # reference geometry on the shared part docs (parts never saved)
    cam_axis = await _make_part_z_axis(adapter, cam, 0.0, 0.0, "cam bore")
    pin_axis = arc_point = None
    if FOOT_MODE == "coincident":
        pin_axis = await _make_part_z_axis(adapter, rocker, COEFF, _arc_y(COEFF), "foot-pin")
    else:
        arc_point = await _make_part_arc_point(adapter, rocker, ROCKER_ARC_EDGE_MM, "rocker arc")

    # mirrored-frame shaft OD / cam disc OD pick points (a point on the cylinder)
    pivot_od = [-pivot_xy[0] + SHAFT_R, pivot_xy[1], Z_ROCKER]
    fulc_od = [-fulcrum_xy[0] + SHAFT_R, fulcrum_xy[1], Z_LEVER]
    arbor_od = [bore_w[0] + SHAFT_R, bore_w[1], 0.0]
    disc_od = [ring_w[0] + CAM_R, ring_w[1], Z_CAM + 5.08]  # mid-thickness of the disc

    # J0 cam revolute on the arbor (the driven member) + axial lock.
    await concentric_mate(adapter, _entity_ref(cam, cam_axis, "AXIS"),
                          bore_axis_ref(arbor_od), label="J0 cam on arbor",
                          verify=(cam, _org(adapter, cam)))
    await _axial_lock(adapter, cam)

    # J1 rocker revolute on the pivot shaft + axial lock.
    await concentric_mate(adapter, named_ref(f"Axis1@{rocker}", "AXIS"),
                          bore_axis_ref(pivot_od), label="J1 rocker pivot",
                          verify=(rocker, _org(adapter, rocker)))
    await _axial_lock(adapter, rocker)

    # J4 lever revolute on the fulcrum shaft (the output) + axial lock.
    await concentric_mate(adapter, named_ref(f"Axis1@{lever}", "AXIS"),
                          bore_axis_ref(fulc_od), label="J4 lever fulcrum",
                          verify=(lever, _org(adapter, lever)))
    await _axial_lock(adapter, lever)

    # J2 connecting-rod: strap bore concentric on the cam disc OD (the eccentric
    # journal), pin coincident to the rocker rod-bore. Spinning the cam drags
    # the strap on a 5.08 mm orbit -> the rod sees-saws the rocker.
    await concentric_mate(adapter, named_ref(f"Axis1@{rod}", "AXIS"),
                          bore_axis_ref(disc_od), label="J2a rod strap on cam",
                          verify=(rod, _org(adapter, rod)))
    await coincident_mate(adapter, _entity_ref(rod, "Axis2", "AXIS"),
                          _entity_ref(rocker, "Axis2", "AXIS"),
                          label="J2b rod pin on rocker", verify=(rod, _org(adapter, rod)))
    await _axial_lock(adapter, rod)

    # J3a foot: ride a fixed coefficient on the rocker R800 arc.
    if FOOT_MODE == "coincident":
        await coincident_mate(adapter, _entity_ref(bar, "Axis2", "AXIS"),
                              _entity_ref(rocker, pin_axis, "AXIS"),
                              label="J3a foot pin (coincident to rocker arc axis)",
                              verify=(bar, _org(adapter, bar)))
    else:
        # full-study scheme: two DISTANCE mates from the bar foot to rocker
        # features (arc-centre point = R, pivot axis = r_foot coefficient).
        foot = world_point(adapter, bar, BAR_FOOT_LOCAL)
        arc_c = world_point(adapter, rocker, ROCKER_ARC_CENTER_LOCAL)
        pivot = world_point(adapter, rocker, ROCKER_PIVOT_LOCAL)
        d_arc = math.hypot(foot[0] - arc_c[0], foot[1] - arc_c[1])
        d_pivot = math.hypot(foot[0] - pivot[0], foot[1] - pivot[1])
        log(f"  distance foot: d_arc={d_arc:.2f} d_pivot={d_pivot:.2f}")
        await distance_driver(adapter, _entity_ref(rocker, arc_point, "POINT"),
                              _entity_ref(bar, "Axis2", "AXIS"), d_arc,
                              label="J3a foot on R800 arc (distance)",
                              verify=(bar, _org(adapter, bar)))
        await distance_driver(adapter, _entity_ref(rocker, "Axis1", "AXIS"),
                              _entity_ref(bar, "Axis2", "AXIS"), d_pivot,
                              label="J3a foot radius coeff (distance)",
                              verify=(bar, _org(adapter, bar)))
    # J3b top pin: lever bar-pin coincident to bar top pin.
    await coincident_mate(adapter, _entity_ref(lever, "Axis2", "AXIS"),
                          _entity_ref(bar, "Axis1", "AXIS"),
                          label="J3b top pin (bar top on lever)",
                          verify=(bar, _org(adapter, bar)))
    await _axial_lock(adapter, bar, plane="Right Plane")

    assert_model_healthy(adapter, label="channel-rig", deep=False)

    # --- Basic Motion: motor on the CAM, calculate, sample the chain -----------
    await adapter.ensure_motion_addin()
    made = check("create_motion_study", await adapter.create_motion_study(
        MotionStudyParameters(name="", study_type="physical_simulation",
                              duration=DURATION_S, activate=True)))
    log(f"  study {made}")
    check("add_motor cam", await adapter.add_motor(MotionMotorParameters(
        motor_type="rotary", entity=_entity_ref(cam, cam_axis, "AXIS"),
        speed=CAM_SPEED, study_name="")))
    log("  Calculate() ...")
    check("calculate_motion", await adapter.calculate_motion(
        MotionStudyRefParameters(name="")))

    base, spans = {}, {}
    probes = [("cam", cam), ("rocker", rocker), ("bar", bar), ("lever", lever)]
    best_t, best_rocker = 0.0, -1.0   # park at peak ROCKER swing (moves at any coeff)
    cam_samples = []                  # (t, xform) of the motor-driven member
    for s in range(STEPS + 1):
        t = DURATION_S * s / STEPS
        await adapter.set_motion_time(MotionTimeParameters(time=t, study_name=""))
        row = []
        for name, comp in probes:
            a = component_transform(adapter, comp)
            base.setdefault(name, a)
            ang = _rot_angle(base[name], a)
            spans[name] = max(spans.get(name, 0.0), ang)
            row.append(f"{name}={ang:6.2f}")
            if name == "cam":
                cam_samples.append((t, a))
            if name == "rocker" and ang > best_rocker:
                best_rocker, best_t = ang, t
        log(f"    t={t:4.2f}s  {'  '.join(row)}")
    log(f"  spans(deg): {dict((k, round(v, 2)) for k, v in spans.items())}")
    # Fail fast on a locked/corrupted solve (the motor-driven cam must keep
    # turning every step; a frozen tail = an aborted Basic Motion solve).
    assert_motion_progressed(cam_samples, DURATION_S, "cam")

    cm, rk, br, lv = (spans.get(k, 0) for k in ("cam", "rocker", "bar", "lever"))
    # The LEVER is the true output signal: the bar mostly TRANSLATES along the
    # arc, so its rotation span is misleadingly tiny (~0.5 deg) in both the
    # working and broken schemes -- only the lever rotation reveals whether the
    # rocker->bar->lever chain actually transmits. The distance-mate foot lets
    # the rocker swing under a near-stationary bar (lever ~0.7 deg = dead); the
    # coincident-axis foot drives the lever ~10 deg. Watching the driven cam
    # alone (assert_motion_progressed) cannot catch a dead output -- the cam
    # spins happily either way -- so gate the OUTPUT here too.
    LEVER_MIN = 3.0
    if cm > 90.0 and 3.0 < rk < 90.0 and lv >= LEVER_MIN:
        log(f"  PASS: cam spins ({cm:.0f}>=180 wraps) -> rocker OSCILLATES {rk:.1f} deg "
            f"-> lever {lv:.1f} deg (cam-driven channel transmits to output)")
    elif cm <= 90.0:
        raise RuntimeError(f"FAIL: cam barely turned ({cm:.1f} deg) -- motor not "
                           f"driving / over-constrained loop")
    elif rk >= 90.0:
        raise RuntimeError(f"FAIL: rocker swung {rk:.1f} deg -- still spinning, "
                           f"not oscillating (cam/rod coupling wrong)")
    elif lv < LEVER_MIN:
        raise RuntimeError(
            f"DEAD OUTPUT: rocker swung {rk:.1f} deg but the lever moved only "
            f"{lv:.1f} deg (< {LEVER_MIN}) -- the rocker->bar->lever chain is "
            f"decoupled (the amplitude bar isn't being driven). The solve can "
            f"complete cleanly with a dead output, so the solve-lock check passes "
            f"-- this output-amplitude gate is what catches it. Use the "
            f"coincident-axis foot, not the distance-mate foot.")

    # --- artefacts: an mp4 + nine views at the peak-deflection pose ------------
    out_dir = OUT_PNG / "fourbar-test" / TAG
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        from solidworks_mcp.adapters.base import MotionExportParameters
        mp4 = (out_dir / "fourbar.mp4").resolve()
        check("export_motion_video", await adapter.export_motion_video(
            MotionExportParameters(file_path=str(mp4), study_name="",
                                   frames_per_second=25.0)))
        log(f"  video -> {mp4}")
    except Exception as exc:  # noqa: BLE001
        log(f"  video export skipped: {exc}")
    await adapter.set_motion_time(MotionTimeParameters(time=best_t, study_name=""))
    log(f"  stills parked at peak rocker pose t={best_t:.2f}s ({best_rocker:.1f} deg)")
    for view in ("front", "back", "top", "bottom", "isometric", "dimetric",
                 "trimetric", "right", "left"):
        img = (out_dir / f"fourbar_{view}.png").resolve()
        check(f"export_image {view}", await adapter.export_image(
            {"file_path": str(img), "format_type": "png", "width": 1600,
             "height": 1000, "view_orientation": view}))
    log(f"  views -> {out_dir}")


async def _main() -> int:
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter
    adapter = PyWin32Adapter({})
    print("Connecting ...", flush=True)
    await adapter.connect()
    adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
    try:
        await build(adapter)
    finally:
        await adapter.disconnect()
        print("Disconnected (NOT saved).", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
