r"""MINIMAL four-bar test: does rocker -> amplitude-bar -> channel-lever transmit?

A throwaway 5-part assembly that isolates ONE channel's transmission from the
full 144-part channel.SLDASM (240 mates, flexible sub, ~13 min/iteration). Built
from scratch with a deliberately NON-degenerate coefficient so the answer is
unambiguous, then driven under Basic Motion -- the same solver the deliverable
uses.

Why the full-assembly probes kept failing: the default channel state parks the
bar foot ~9 mm from the rocker pivot (the near-zero "neutral" coefficient), so
rocking the arm gives ~zero foot travel -- a singular four-bar. Here the foot is
pinned on the R800 arc at COEFF=60 mm out from the pivot: a real lever arm.

The kinematic chain (planar, all pin axes along Z):
  * rocker pivot   -- concentric on the pivot-shaft (revolute, MOTOR-driven)
  * foot pin       -- bar Axis2 (foot) COINCIDENT to a Z-axis built into the
                      rocker at local (COEFF, arc_y): the foot rides a fixed
                      point on the arc (operating coefficient = clamped slide)
  * top pin        -- lever Axis2 (bar pin) COINCIDENT to bar Axis1 (top pin)
  * lever fulcrum  -- concentric on the fulcrum-shaft (revolute, the output)

Grashof crank-rocker (shortest link = rocker arm, 60.9 mm): the rocker can turn
fully and the lever oscillates -- so the motor sweep clearly exercises the chain.
The rocker pin axis is created on the SHARED rocker-arm part doc (ActivateDoc3
round-trip, part NEVER saved). The assembly is NEVER saved either -- this is a
diagnostic, the result is the printed spans + an exported mp4.

  C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_fourbar_test.py
"""

from __future__ import annotations

import asyncio
import math
import sys

from _common import (
    OUT_PNG, OUT_SLDASM, _flag, _read_member, assert_model_healthy, check,
    coincident_mate, component_transform, concentric_mate, bore_axis_ref,
    log, named_ref, place_component,
)
from build_motion_study import _entity_ref, _rot_angle
from solidworks_mcp.adapters.solidworks.assembly import _byref_i4

# --- geometry (design / pre-mirror frame, mm) -------------------------------
SHAFT_R = 6.35 / 2.0
ARC_CENTER_Y = 816.0          # rocker R800 arc centre, local
ARC_R = 800.0
COEFF = 60.0                  # foot offset along the arc from the pivot = lever arm

# bar / lever named-bore locals (from build_channel_assembly.py)
BAR_FOOT_LOCAL = [3.175, 0.0, 3.175]        # bar Axis2 (foot)
BAR_TOP_PIN_LOCAL = [3.175, 806.45, 3.175]  # bar Axis1 (top pin)
LEVER_BAR_PIN_LOCAL = [127.0, 0.0, 0.0]     # lever Axis2 (bar pin)

IDENT = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
# Bar bores run along its LOCAL X (Top ∩ Front planes); the bar must be rotated
# Ry(90) so they become the assembly Z (rotation) axis -- as build_channel does.
ROT_Y_POS90 = [[0.0, 0.0, -1.0], [0.0, 1.0, 0.0], [1.0, 0.0, 0.0]]

# motor / solve
ROCK_SPEED = 2.0   # rotary motor speed (Basic Motion: ~115 deg/s at 2)
DURATION_S = 2.0
STEPS = 16

# Set True if the foot-pin coincident yanks the bar (plane offset normal flipped).
FLIP_PIN_PLANE = False


def _arc_y(x: float) -> float:
    return ARC_CENTER_Y - math.sqrt(ARC_R**2 - x * x)


async def _make_rocker_pin_axis(adapter, rocker_name: str) -> str:
    """Create a Z-axis at rocker-local (COEFF, arc_y) on the shared rocker part.

    Intersection of an offset-from-Right plane (x = COEFF) and an offset-from-Top
    plane (y = arc_y). Built in the PART doc (ActivateDoc3 round-trip) so it moves
    with the rocker; the part is NEVER saved. Returns the new axis name."""
    from solidworks_mcp.adapters.base import CreateAxisParameters, CreatePlaneParameters

    comp = adapter.currentModel.GetComponentByName(rocker_name)
    _flag(comp, "IComponent2")
    part = adapter._attempt(lambda: comp.GetModelDoc2(), default=None)
    if part is None:
        raise RuntimeError("rocker part doc unresolved")
    top = adapter.currentModel
    top_title = str(_read_member(top, "GetTitle"))
    part_title = str(_read_member(part, "GetTitle"))
    adapter._attempt(
        lambda: adapter.swApp.ActivateDoc3(part_title, False, 2, _byref_i4()), default=None)
    adapter.currentModel = adapter._attempt(lambda: adapter.swApp.ActiveDoc, default=part)
    try:
        px = check("plane x=COEFF", await adapter.create_plane(CreatePlaneParameters(
            mode="offset", base_plane="Right Plane", offset=COEFF, flip=FLIP_PIN_PLANE)))
        py = check("plane y=arc_y", await adapter.create_plane(CreatePlaneParameters(
            mode="offset", base_plane="Top Plane", offset=_arc_y(COEFF))))
        ax = check("axis foot-pin", await adapter.create_axis(CreateAxisParameters(
            mode="two_planes", planes=[px.name, py.name])))
    finally:
        adapter._attempt(
            lambda: adapter.swApp.ActivateDoc3(top_title, False, 2, _byref_i4()), default=None)
        adapter.currentModel = top
    log(f"  rocker foot-pin axis = {ax.name!r} at local ({COEFF}, {_arc_y(COEFF):.2f})")
    return ax.name


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

    # frame: the two grounded shafts (rocker pivot + lever fulcrum)
    await place_component(adapter, "pivot-shaft", [pivot_xy[0], pivot_xy[1], 0.0],
                          [0.0, 0.0, 0.0], IDENT, label="pivot-shaft")
    await place_component(adapter, "fulcrum-shaft", [fulcrum_xy[0], fulcrum_xy[1], 0.0],
                          [0.0, 0.0, 0.0], IDENT, label="fulcrum-shaft")

    # moving parts, inserted on-solution (z staggered so they don't overlap)
    rocker = await place_component(adapter, "rocker-arm",
                                   [0.0, -8.0, 0.0], [0.0, 0.0, 0.0], IDENT,
                                   ground=False, label="rocker-arm")
    # All three moving parts coplanar about z=0 so the bar straddles the rocker
    # (foot) and lever (top) like the real channel -- pins short, looks connected.
    # Ry(90): foot world = (local_z + tx, local_y + ty, -local_x + tz); tz=+half
    # width centres the bar's Z span on 0. (Z position along a pin axis is free,
    # so this is cosmetic only -- the kinematics are identical to any stagger.)
    bar = await place_component(adapter, "amplitude-bar",
                                [foot_w[0] - BAR_FOOT_LOCAL[2], foot_w[1], 3.175],
                                [0.0, 90.0, 0.0], ROT_Y_POS90,
                                ground=False, label="amplitude-bar")
    lever = await place_component(adapter, "channel-lever",
                                  [fulcrum_xy[0], fulcrum_xy[1], 0.0],
                                  [0.0, 0.0, 0.0], IDENT, ground=False, label="channel-lever")

    # rocker foot-pin axis on the part doc
    pin_axis = await _make_rocker_pin_axis(adapter, rocker)

    # mirrored-frame shaft OD pick points (x -> -x; shafts centre on their axis)
    pivot_od = [-pivot_xy[0] + SHAFT_R, pivot_xy[1], 0.0]
    fulc_od = [-fulcrum_xy[0] + SHAFT_R, fulcrum_xy[1], 0.0]
    rk_org = [component_transform(adapter, rocker)[9 + i] * 1000.0 for i in range(3)]
    lv_org = [component_transform(adapter, lever)[9 + i] * 1000.0 for i in range(3)]

    # J1 rocker revolute (spin freed for the motor)
    await concentric_mate(adapter, named_ref(f"Axis1@{rocker}", "AXIS"),
                          bore_axis_ref(pivot_od), label="J1 rocker pivot",
                          verify=(rocker, rk_org))
    # J4 lever revolute (the output)
    await concentric_mate(adapter, named_ref(f"Axis1@{lever}", "AXIS"),
                          bore_axis_ref(fulc_od), label="J4 lever fulcrum",
                          verify=(lever, lv_org))
    # J3a foot pin: bar foot COINCIDENT to the rocker arc-point axis
    bar_org = [component_transform(adapter, bar)[9 + i] * 1000.0 for i in range(3)]
    await coincident_mate(adapter, _entity_ref(bar, "Axis2", "AXIS"),
                          _entity_ref(rocker, pin_axis, "AXIS"),
                          label="J3a foot pin (bar foot on rocker arc)",
                          verify=(bar, bar_org))
    # J3b top pin: lever bar-pin COINCIDENT to bar top pin
    await coincident_mate(adapter, _entity_ref(lever, "Axis2", "AXIS"),
                          _entity_ref(bar, "Axis1", "AXIS"),
                          label="J3b top pin (bar top on lever)",
                          verify=(bar, bar_org))

    assert_model_healthy(adapter, label="fourbar", deep=False)

    # --- Basic Motion: motor on the rocker, calculate, sample the chain --------
    await adapter.ensure_motion_addin()
    made = check("create_motion_study", await adapter.create_motion_study(
        MotionStudyParameters(name="", study_type="physical_simulation",
                              duration=DURATION_S, activate=True)))
    log(f"  study {made}")
    check("add_motor rocker", await adapter.add_motor(MotionMotorParameters(
        motor_type="rotary", entity=_entity_ref(rocker, "Axis1", "AXIS"),
        speed=ROCK_SPEED, study_name="")))
    log("  Calculate() ...")
    check("calculate_motion", await adapter.calculate_motion(
        MotionStudyRefParameters(name="")))

    base, spans = {}, {}
    probes = [("rocker", rocker), ("bar", bar), ("lever", lever)]
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
        log(f"    t={t:4.2f}s  {'  '.join(row)}")
    log(f"  spans(deg): {dict((k, round(v, 2)) for k, v in spans.items())}")

    rk, br, lv = spans.get("rocker", 0), spans.get("bar", 0), spans.get("lever", 0)
    if rk > 1.0 and lv > 1.0 and br > 0.1:
        log(f"  PASS: rocker {rk:.1f} -> bar swings {br:.1f} -> lever {lv:.1f} deg "
            f"(four-bar transmits)")
    elif rk <= 1.0:
        log(f"  FAIL: rocker barely moved ({rk:.2f}) -- motor/over-constraint")
    else:
        log(f"  FAIL: rocker {rk:.1f} but lever {lv:.2f} -- not transmitting")

    # --- artefacts to show: an mp4 + an isometric still ------------------------
    out_dir = OUT_PNG / "fourbar-test"
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
    # Park at a clearly deflected pose (lever near peak) so the linkage reads.
    await adapter.set_motion_time(MotionTimeParameters(time=DURATION_S * 0.375, study_name=""))
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
