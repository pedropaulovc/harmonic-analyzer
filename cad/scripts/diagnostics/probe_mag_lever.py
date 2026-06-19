r"""DOF probe: magnifying-lever revolute on the bracket collar (Phase D).

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_mag_lever.py
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

LEVER_ROD_Y = 985.0
LEVER_ROD_Z = -85.0
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
    mb = await place_component(adapter, "magnifying-bracket",
                               [-40.0, LEVER_ROD_Y, LEVER_ROD_Z], [0.0, 0.0, 0.0], IDENTITY)
    ml = await place_component(adapter, "magnifying-lever",
                               [-200.0, LEVER_ROD_Y, LEVER_ROD_Z], [0.0, 0.0, 0.0],
                               IDENTITY, ground=False)
    ml_o = _org(adapter, ml)
    log(f"lever org = {ml_o}")
    tip0 = world_point(adapter, ml, [82.5, 3.0, 0.0])  # rod side point (off-axis)
    log(f"rod side point BEFORE = {tip0}")

    await coincident_mate(adapter, named_ref(f"Axis1@{ml}", "AXIS"),
                          named_ref(f"Axis1@{mb}", "AXIS"),
                          label="collar pivot", verify=(ml, ml_o))
    log(f"after radial: {_status(adapter, ml)}")

    await distance_driver(adapter, named_ref(f"Right Plane@{ml}", "PLANE"),
                          named_ref("Right Plane", "PLANE"), abs(ml_o[0]),
                          label="axial", verify=(ml, ml_o))
    log(f"after axial(Right d={abs(ml_o[0]):.1f}): {_status(adapter, ml)}")

    try:
        await angle_driver(adapter, named_ref(f"Top Plane@{ml}", "PLANE"),
                           named_ref("Top Plane", "PLANE"), 0.0,
                           label="rock", verify=(ml, ml_o))
        log(f"after angle(Top): {_status(adapter, ml)}")
    except Exception as exc:  # noqa: BLE001
        log(f"ANGLE FAILED: {exc}")
        log(f"status: {_status(adapter, ml)}")

    tip1 = world_point(adapter, ml, [82.5, 3.0, 0.0])
    log(f"rod side point AFTER = {tip1}  (flip if y jumped far from {tip0[1]:.1f})")
    return {}


if __name__ == "__main__":
    sys.exit(run_build(build))
