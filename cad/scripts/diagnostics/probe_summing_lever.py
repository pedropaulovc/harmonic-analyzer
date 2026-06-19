r"""DOF probe: summing-lever knife-edge revolute (Phase D diagnosis).

Inserts knife-mount (fixed seed) + summing-lever (float), then adds the
revolute mates one at a time, printing GetConstrainedStatus(summing-lever)
after each so we can see exactly where the DOF go and which mate over-defines.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_summing_lever.py
"""

from __future__ import annotations

import sys

from _common import (
    angle_driver,
    check,
    coincident_mate,
    component_transform,
    distance_driver,
    log,
    named_ref,
    place_component,
    spin_driver,
    world_point,
    run_build,
    _flag,
    _read_member,
)
from build_summing_lever import SPIN_REF_X as SL_SPIN_REF_X

KNIFE = (15.0, 990.0)
IDENTITY = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]


def _org(adapter, name):
    a = component_transform(adapter, name)
    return [a[9] * 1000.0, a[10] * 1000.0, a[11] * 1000.0]


def _status(adapter, comp):
    asm = adapter.currentModel
    adapter._attempt(lambda: asm.ForceRebuild3(False), default=None)
    components = adapter._attempt(lambda: asm.GetComponents(True), default=None) or []
    for component in components:
        _flag(component, "IComponent2")
        name = str(_read_member(component, "Name2"))
        if name != comp:
            continue
        if bool(_read_member(component, "IsFixed")):
            return "FIXED"
        s = int(adapter._attempt(lambda c=component: c.GetConstrainedStatus(), default=-1))
        names = {2: "UNDER(2)", 3: "FULLY(3)", 4: "OVER(4)", 5: "NOSOLN(5)"}
        return names.get(s, f"status={s}")
    return "??"


async def build(adapter):
    check("create_assembly", await adapter.create_assembly())
    km = await place_component(adapter, "knife-mount", [KNIFE[0], KNIFE[1], 0.0],
                               [0.0, 0.0, 0.0], IDENTITY)
    sl = await place_component(adapter, "summing-lever", [KNIFE[0], KNIFE[1], 0.0],
                               [0.0, 0.0, 0.0], IDENTITY, ground=False)
    sl_o = _org(adapter, sl)
    log(f"after insert: summing-lever {_status(adapter, sl)}  org={sl_o}")

    # Enumerate the lever's reference-axis features (RefAxis) to see what
    # Axis1/Axis2 actually resolve to.
    asm = adapter.currentModel
    for component in adapter._attempt(lambda: asm.GetComponents(True), default=None) or []:
        _flag(component, "IComponent2")
        if str(_read_member(component, "Name2")) != sl:
            continue
        feat = adapter._attempt(lambda c=component: c.FirstFeature(), default=None)
        while feat is not None:
            _flag(feat, "IFeature")
            fname = str(_read_member(feat, "Name"))
            ftype = str(_read_member(feat, "GetTypeName2"))
            if "Axis" in fname or "Ref" in ftype or "axis" in ftype.lower():
                log(f"  feat: name={fname!r} type={ftype!r}")
            feat = adapter._attempt(lambda f=feat: f.GetNextFeature(), default=None)
        break

    await coincident_mate(adapter, named_ref(f"Axis1@{sl}", "AXIS"),
                          named_ref(f"Axis1@{km}", "AXIS"),
                          label="knife pivot", verify=(sl, sl_o))
    log(f"after radial coincident(Axis1): summing-lever {_status(adapter, sl)}")

    # FULL CANDIDATE: radial + axial distance(Front) [Tz] + angle(Right) [Rz].
    p0 = world_point(adapter, sl, [SL_SPIN_REF_X, 0.0, 0.0])  # boss hole, off-axis
    log(f"boss-hole world BEFORE axial/angle = {p0}  (expect ~[-90.5, 990, 0])")

    await distance_driver(adapter, named_ref(f"Front Plane@{sl}", "PLANE"),
                          named_ref("Front Plane", "PLANE"), abs(sl_o[2]),
                          label="axial (Front)", verify=(sl, sl_o))
    log(f"after axial(Front): summing-lever {_status(adapter, sl)}")

    try:
        await angle_driver(adapter, named_ref(f"Right Plane@{sl}", "PLANE"),
                           named_ref("Right Plane", "PLANE"), 0.0,
                           label="rock via angle(Right)", verify=(sl, sl_o))
        log(f"after angle(Right): summing-lever {_status(adapter, sl)}")
    except Exception as exc:  # noqa: BLE001
        log(f"ANGLE FAILED: {exc}")
        log(f"status: summing-lever {_status(adapter, sl)}")

    p1 = world_point(adapter, sl, [SL_SPIN_REF_X, 0.0, 0.0])
    log(f"boss-hole world AFTER = {p1}  (flip if it jumped to +x side ~+60.5)")
    return {}


if __name__ == "__main__":
    sys.exit(run_build(build))
