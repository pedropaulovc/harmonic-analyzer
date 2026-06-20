r"""DOF probe: magnifying-wheel revolute on the wheel-axle stud (Phase D).

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_wheel.py
"""

from __future__ import annotations

import sys

from _common import (
    _flag,
    _read_member,
    check,
    log,
    run_build,
)
from _assembly import (
    angle_driver,
    coincident_mate,
    component_transform,
    distance_driver,
    named_ref,
    place_component,
    world_point,
)

WHEEL_X = 53.0
WHEEL_BAR_Y = 565.0
BAR_FRONT_Z = -138.9
WHEEL_MID_Z = -146.9
ROT_X_NEG90 = [[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]]
IDENTITY = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]


def _org(adapter, name):
    a = component_transform(adapter, name)
    return [a[9] * 1000.0, a[10] * 1000.0, a[11] * 1000.0]


def _status(adapter, comp):
    asm = adapter.currentModel
    adapter._attempt(lambda: asm.ForceRebuild3(False), default=None)
    for component in adapter._attempt(lambda: asm.GetComponents(True), default=None) or []:
        _flag(component, "IComponent2")
        if str(_read_member(component, "Name2")) != comp:
            continue
        if bool(_read_member(component, "IsFixed")):
            return "FIXED"
        s = int(adapter._attempt(lambda c=component: c.GetConstrainedStatus(), default=-1))
        return {2: "UNDER(2)", 3: "FULLY(3)", 4: "OVER(4)", 5: "NOSOLN(5)"}.get(s, f"s={s}")
    return "??"


async def build(adapter):
    check("create_assembly", await adapter.create_assembly())
    ax = await place_component(adapter, "wheel-axle", [WHEEL_X, WHEEL_BAR_Y, BAR_FRONT_Z],
                               [-90.0, 0.0, 0.0], ROT_X_NEG90)
    wh = await place_component(adapter, "magnifying-wheel",
                               [WHEEL_X, WHEEL_BAR_Y, WHEEL_MID_Z], [0.0, 0.0, 0.0],
                               IDENTITY, ground=False)
    wh_o = _org(adapter, wh)
    log(f"wheel org = {wh_o}")
    rim0 = world_point(adapter, wh, [50.0, 0.0, 0.0])  # rim point (off-axis)
    log(f"rim point BEFORE = {rim0}")

    await coincident_mate(adapter, named_ref(f"Axis1@{wh}", "AXIS"),
                          named_ref(f"Axis1@{ax}", "AXIS"),
                          label="wheel pivot", verify=(wh, wh_o))
    log(f"after radial: {_status(adapter, wh)}")

    await distance_driver(adapter, named_ref(f"Front Plane@{wh}", "PLANE"),
                          named_ref("Front Plane", "PLANE"), abs(wh_o[2]),
                          label="axial", verify=(wh, wh_o))
    log(f"after axial(Front d={abs(wh_o[2]):.1f}): {_status(adapter, wh)}")

    try:
        await angle_driver(adapter, named_ref(f"Right Plane@{wh}", "PLANE"),
                           named_ref("Right Plane", "PLANE"), 0.0,
                           label="spin", verify=(wh, wh_o))
        log(f"after angle(Right): {_status(adapter, wh)}")
    except Exception as exc:  # noqa: BLE001
        log(f"ANGLE(Right) FAILED: {exc}; trying Top")
        try:
            await angle_driver(adapter, named_ref(f"Top Plane@{wh}", "PLANE"),
                               named_ref("Top Plane", "PLANE"), 0.0,
                               label="spin-top", verify=(wh, wh_o))
            log(f"after angle(Top): {_status(adapter, wh)}")
        except Exception as exc2:  # noqa: BLE001
            log(f"ANGLE(Top) FAILED: {exc2}")

    rim1 = world_point(adapter, wh, [50.0, 0.0, 0.0])
    log(f"rim point AFTER = {rim1}  (flip if jumped from {rim0[:2]})")
    return {}


if __name__ == "__main__":
    sys.exit(run_build(build))
