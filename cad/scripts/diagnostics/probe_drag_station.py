r"""Diagnostic: reproduce the MANUAL 'lower the rocker' drag and measure bar slide.

PR #458 user repro: open channel, move the amplitude bar to the end of the
rocker arc, then drag the rocker down. Expected: the bar lowers IN TANDEM (its
station along the rocker -- the foot-notch seat -- is held by the serration in
the physical machine). Reported actual: the bar slides left/right along the
rocker (and, before the range stops, rolled clean past the arc end).

verify:kinematics exercises this with transient DOF drives and sees only
0.06 deg of station drift -- but the user drags with Move Components, whose
solver (IDragOperator) picks its own solution in the free amplitude DOF. This
probe replays the drag exactly:

  1. open channel.SLDASM, ramp a transient rocker<->bar angle drive to the
     right amplitude endpoint (the shipped limit), delete the drive;
  2. for each DragMode (0=max/rigid, 1=min move, 2=relaxation): rotate
     rocker-arm-1 about its pivot in 0.5 deg steps, down then back up;
  3. after each pass, log the rocker motion actually achieved and the bar's
     station drift relative to the rocker.

Run (SolidWorks already open):

  uv run python cad/scripts/diagnostics/probe_drag_station.py

NEVER saves.
"""

from __future__ import annotations

import asyncio
import math

from _common import OUT_SLDASM, _early_bound, check, log  # noqa: F401  (shim first: patches sys.path)
import _telemetry
from _assembly import (
    angle_driver,
    delete_assembly_feature,
    named_ref,
    world_point,
)
from build_channel_assembly import (
    AMPLITUDE_ANGLE_LIMITS,
    ARM_ARC_CENTER_LOCAL_Y,
)

ROCKER = "rocker-arm-1"
BAR = "amplitude-bar-1"
PIVOT_LOCAL = [0.0, 8.0, 0.0]  # ARM_PIVOT_LOCAL_Y


def _unit(v: tuple[float, float]) -> tuple[float, float]:
    mag = math.hypot(*v)
    if mag <= 1e-9:
        raise RuntimeError("zero-length orientation witness")
    return (v[0] / mag, v[1] / mag)


def _vectors(adapter) -> tuple[tuple[float, float], tuple[float, float]]:
    pivot = world_point(adapter, ROCKER, PIVOT_LOCAL)
    arc = world_point(adapter, ROCKER, [0.0, ARM_ARC_CENTER_LOCAL_Y, 0.0])
    bar0 = world_point(adapter, BAR, [0.0, 0.0, 0.0])
    bar1 = world_point(adapter, BAR, [0.0, 1.0, 0.0])
    return (
        _unit((arc[0] - pivot[0], arc[1] - pivot[1])),
        _unit((bar1[0] - bar0[0], bar1[1] - bar0[1])),
    )


def _rot(cur: tuple[float, float], rest: tuple[float, float]) -> float:
    cross = rest[0] * cur[1] - rest[1] * cur[0]
    dot = rest[0] * cur[0] + rest[1] * cur[1]
    return math.degrees(math.atan2(cross, dot))


def _rebuild(adapter) -> None:
    adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False), default=None)
    adapter._attempt(lambda: adapter.currentModel.EditRebuild3(), default=None)


def _rot_z_about(pivot_mm: list[float], deg: float) -> list[float]:
    """World-space delta: rotate ``deg`` about +Z through ``pivot_mm``.

    Row-vector convention matching Transform2 ArrayData: w' = w.R + t,
    R row-major in [0:9], t (metres) in [9:12], scale 1.
    """
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    px, py = pivot_mm[0] / 1000.0, pivot_mm[1] / 1000.0
    r = [c, s, 0.0, -s, c, 0.0, 0.0, 0.0, 1.0]
    tx = px - (px * c - py * s)
    ty = py - (px * s + py * c)
    return r + [tx, ty, 0.0, 1.0, 0.0, 0.0, 0.0]


async def main() -> None:
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    adapter = PyWin32Adapter({})
    _telemetry.info("Connecting ...")
    await adapter.connect()
    adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
    path = str((OUT_SLDASM / "channel.SLDASM").resolve())
    check("open channel", await adapter.open_model(path))
    model = adapter.currentModel
    try:
        rest_rocker, rest_bar = _vectors(adapter)

        def station() -> float:
            rocker_u, bar_u = _vectors(adapter)
            return 90.0 + _rot(rocker_u, rest_rocker) - _rot(bar_u, rest_bar)

        log(f"rest station {station():.3f} deg (limits {AMPLITUDE_ANGLE_LIMITS})")

        # 1. ramp the bar to the RIGHT endpoint exactly as verify does
        endpoint = max(AMPLITUDE_ANGLE_LIMITS)
        res = await angle_driver(
            adapter,
            named_ref(f"Right Plane@{ROCKER}", "PLANE"),
            named_ref(f"Top Plane@{BAR}", "PLANE"),
            90.0,
            label="PROBE station drive",
        )
        param = adapter._attempt(lambda: model.Parameter(f"D1@{res['name']}"), default=None)
        assert param is not None
        for step in range(9):
            requested = 90.0 + (endpoint - 90.0) * step / 8.0
            param.SystemValue = math.radians(requested)
            _rebuild(adapter)
        log(f"ramped to endpoint: station {station():.3f} deg (target {endpoint:.3f})")
        delete_assembly_feature(adapter, res["name"])
        _rebuild(adapter)
        log(f"after drive delete: station {station():.3f} deg")

        # 2. drag the rocker about its pivot, each mode, down then up
        from solidworks_mcp.adapters.solidworks.assembly import _create_math_transform

        asm = _early_bound(model, "IAssemblyDoc")
        comp = asm.GetComponentByName(ROCKER)
        assert comp is not None
        drag = _early_bound(asm.GetDragOperator(), "IDragOperator")

        def drag_pass(mode: int, total_deg: float, steps: int) -> tuple[float, float]:
            """Rotate the rocker by total_deg in steps; return (rocker motion, station drift)."""
            pivot = world_point(adapter, ROCKER, PIVOT_LOCAL)
            xform = _create_math_transform(
                adapter, _rot_z_about(pivot, total_deg / steps)
            )
            before_rocker, _ = _vectors(adapter)
            before_station = station()
            ok = drag.AddComponent(comp, False)
            drag.CollisionDetectionEnabled = False
            drag.DynamicClearanceEnabled = False
            drag.TransformType = 1  # axial rotation
            drag.DragMode = mode
            began = drag.BeginDrag()
            moved = [bool(drag.Drag(xform)) for _ in range(steps)]
            ended = drag.EndDrag()
            after_rocker, _ = _vectors(adapter)
            motion = _rot(after_rocker, before_rocker)
            drift = station() - before_station
            log(
                f"  mode={mode} req={total_deg:+.1f} deg: add={ok} begin={began} "
                f"steps_ok={sum(moved)}/{steps} end={ended} "
                f"rocker_moved={motion:+.3f} deg station_drift={drift:+.3f} deg "
                f"station={station():.3f}"
            )
            return motion, drift

        for mode in (0, 1, 2):
            log(f"DragMode {mode}:")
            drag_pass(mode, -3.0, 6)
            drag_pass(mode, +3.0, 6)
        log(f"final station {station():.3f} deg")
    finally:
        adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)


if __name__ == "__main__":
    asyncio.run(main())
