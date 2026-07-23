r"""DOF probe: platen prismatic slider along the rails (Phase D).

The platen runs horizontally along X on the support rails. Build it as the
dual of the working revolute: the platen's local-X "slide axis" made collinear
with an assembly reference axis on the slide line (removes T_y/T_z/R_y/R_z), an
angle snapshot killing the residual spin about X, and an X distance snapshot
pinning the feed position.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_platen.py
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
    named_ref,
    place_component,
    world_point,
)

PLATE_X0 = -33.213
PLATE_Y0 = 273.234
PLATE_FRONT_Z = -142.9
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
    # Fixed seed so the platen is NOT the first component (SW auto-fixes the
    # first inserted part); in the real assembly many fixed parts precede it.
    await place_component(adapter, "support-bar", [0.0, 440.0, -133.9],
                          [0.0, 0.0, 0.0], IDENTITY, ground=True)
    pl = await place_component(adapter, "platen",
                              [PLATE_X0, PLATE_Y0, PLATE_FRONT_Z], [0.0, 0.0, 0.0],
                              IDENTITY, ground=False)
    pl_o = _org(adapter, pl)
    log(f"platen org = {pl_o}")
    corner0 = world_point(adapter, pl, [269.64, 134.82, 4.0])  # far corner (off both axes)
    log(f"far corner BEFORE = {corner0}")

    # Slide axis held parallel to the Top and Front planes at the slide-line
    # offsets (axis-to-plane distance: each removes 1 translation + 1 rotation,
    # orthogonal, no overlap) -> leaves T_x + spin about X.
    await distance_driver(adapter, named_ref(f"Axis1@{pl}", "AXIS"),
                          named_ref("Top Plane", "PLANE"), abs(pl_o[1]),
                          label="platen slide height (Top)", verify=(pl, pl_o))
    log(f"after height(Top d={abs(pl_o[1]):.1f}): {_status(adapter, pl)}")

    await distance_driver(adapter, named_ref(f"Axis1@{pl}", "AXIS"),
                          named_ref("Front Plane", "PLANE"), abs(pl_o[2]),
                          label="platen slide depth (Front)", verify=(pl, pl_o))
    log(f"after depth(Front d={abs(pl_o[2]):.1f}): {_status(adapter, pl)}")

    await angle_driver(adapter, named_ref(f"Top Plane@{pl}", "PLANE"),
                       named_ref("Top Plane", "PLANE"), 0.0,
                       label="platen spin snapshot", verify=(pl, pl_o))
    log(f"after angle(Top): {_status(adapter, pl)}")

    await distance_driver(adapter, named_ref(f"Right Plane@{pl}", "PLANE"),
                          named_ref("Right Plane", "PLANE"), abs(pl_o[0]),
                          label="platen feed snapshot", verify=(pl, pl_o))
    log(f"after X snapshot(d={abs(pl_o[0]):.1f}): {_status(adapter, pl)}")

    corner1 = world_point(adapter, pl, [269.64, 134.82, 4.0])
    log(f"far corner AFTER = {corner1}  (flip if jumped from {corner0})")

    # Lock a ride-along (platen-rack) to the platen via Front planes -- a Lock
    # mate freezes relative pose regardless of the selected entities.
    from _assembly import lock_mate
    rot_z180 = [[-1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, 1.0]]
    RACK_X0, RACK_Y0, RACK_Z = 41.23, 296.5, -138.9
    rk = await place_component(adapter, "platen-rack", [RACK_X0, RACK_Y0, RACK_Z],
                              [0.0, 0.0, 180.0], rot_z180, ground=False)
    rk_o = _org(adapter, rk)
    await lock_mate(adapter, named_ref(f"Front Plane@{rk}", "PLANE"),
                    named_ref(f"Front Plane@{pl}", "PLANE"), label="rack locked to platen")
    log(f"after lock rack: {_status(adapter, rk)}")
    return {}


if __name__ == "__main__":
    sys.exit(run_build(build))
