r"""DOF probe: pen-rod prismatic slider (vertical Y) + marker lock (Phase D).

The pen carriage (rod + marker) slides vertically through the fixed v-block
bores as the magnifying wheel's wire raises/lowers the pen. Build the pen-rod
as a Y-prismatic: its local-Y slide axis held parallel to the Front + Right
planes (axis-to-plane distance, no rotational overlap), an angle snapshot
killing spin about Y, a Y distance snapshot pinning travel; the marker rides
the rod via a Lock mate.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_pen.py
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
    component_transform,
    distance_driver,
    lock_mate,
    named_ref,
    place_component,
    world_point,
)

VBLOCK_POS = (-24.0, 390.0, -159.5)
PEN_ROD_POS = (-3.0, 398.0, -154.0)
MARKER_POS = (-13.0, 368.0, -151.5)
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
    # Fixed seed (v-block) so the rod is not the auto-fixed first component.
    await place_component(adapter, "pen-v-block", list(VBLOCK_POS),
                          [0.0, 0.0, 0.0], IDENTITY, ground=True)
    rod = await place_component(adapter, "pen-rod", list(PEN_ROD_POS),
                               [0.0, 0.0, 0.0], IDENTITY, ground=False)
    rod_o = _org(adapter, rod)
    log(f"rod org = {rod_o}")
    top0 = world_point(adapter, rod, [2.5, 120.0, 2.5])  # rod top corner (off-axis)
    log(f"rod top BEFORE = {top0}")

    await distance_driver(adapter, named_ref(f"Axis1@{rod}", "AXIS"),
                          named_ref("Front Plane", "PLANE"), abs(rod_o[2]),
                          label="rod slide depth (Front)", verify=(rod, rod_o))
    log(f"after depth(Front d={abs(rod_o[2]):.1f}): {_status(adapter, rod)}")

    await distance_driver(adapter, named_ref(f"Axis1@{rod}", "AXIS"),
                          named_ref("Right Plane", "PLANE"), abs(rod_o[0]),
                          label="rod slide across (Right)", verify=(rod, rod_o))
    log(f"after across(Right d={abs(rod_o[0]):.1f}): {_status(adapter, rod)}")

    await angle_driver(adapter, named_ref(f"Front Plane@{rod}", "PLANE"),
                       named_ref("Front Plane", "PLANE"), 0.0,
                       label="rod spin snapshot", verify=(rod, rod_o))
    log(f"after angle(Front): {_status(adapter, rod)}")

    await distance_driver(adapter, named_ref(f"Top Plane@{rod}", "PLANE"),
                          named_ref("Top Plane", "PLANE"), abs(rod_o[1]),
                          label="rod travel snapshot", verify=(rod, rod_o))
    log(f"after Y snapshot(d={abs(rod_o[1]):.1f}): {_status(adapter, rod)}")

    top1 = world_point(adapter, rod, [2.5, 120.0, 2.5])
    log(f"rod top AFTER = {top1}  (flip if jumped from {top0})")

    # Marker rides the rod (pen carriage) via a Lock mate.
    mk = await place_component(adapter, "pen-marker", list(MARKER_POS),
                              [0.0, 0.0, 0.0], IDENTITY, ground=False)
    await lock_mate(adapter, named_ref(f"Front Plane@{mk}", "PLANE"),
                    named_ref(f"Front Plane@{rod}", "PLANE"),
                    label="marker locked to rod")
    log(f"after lock marker: {_status(adapter, mk)}")
    return {}


if __name__ == "__main__":
    sys.exit(run_build(build))
