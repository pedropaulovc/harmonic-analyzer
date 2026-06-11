r"""Diagnostic: localize the 2.40 mm^3 cylinder-gear vs connecting-rod overlap.

The top-level M6.5 interference run reports exactly 2.40 mm^3 between every
cylinder-gear j and its connecting-rod j, yet the placement math says the rod
ring bore (R 25.5) is exactly concentric with the integral cam (R 25.4) and
the ring's z band (z_j+1.8..4.8) sits strictly inside the cam band
(z_j+1.5..5.0). This script rebuilds the minimal two-component scene for
channel j=0 and prints the interference VOLUME and BODY BOUNDING BOX so the
overlap zone can be identified instead of guessed.

Throwaway diagnostic - not part of build_all.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\diag_rod_gear_interference.py
"""

from __future__ import annotations

import sys

from _common import (
    check,
    log,
    run_build,
)
from _common import _flag, _read_member  # noqa: PLC2701 - diagnostic peek
from build_channel_assembly import (
    CAM_DZ,
    RING_CENTER,
    Z0,
    _part,
    rot_z_rows,
    solve_default_state,
)

GEAR_AXIS_Y = 126.8


def _report_interferences(adapter, label: str) -> None:
    asm = adapter.currentModel
    _flag(asm, "IAssemblyDoc")
    adapter._attempt(lambda: asm.ToolsCheckInterference(), default=None)
    mgr = _read_member(asm, "InterferenceDetectionManager")
    if mgr is None:
        raise RuntimeError("InterferenceDetectionManager unavailable")
    _flag(mgr, "IInterferenceDetectionMgr")
    mgr.TreatCoincidenceAsInterference = False
    mgr.TreatSubAssembliesAsComponents = True
    mgr.IncludeMultibodyPartInterferences = True
    mgr.MakeInterferingPartsTransparent = False
    mgr.CreateFastenersFolder = False
    mgr.UseTransform = False
    interferences = adapter._attempt(lambda: mgr.GetInterferences(), default=None)
    found = list(interferences or [])
    log(f"[{label}] {len(found)} interference(s)")
    for itf in found:
        _flag(itf, "IInterference")
        names = []
        for comp in list(_read_member(itf, "Components") or []):
            _flag(comp, "IComponent2")
            names.append(str(_read_member(comp, "Name2")))
        volume_mm3 = float(_read_member(itf, "Volume") or 0.0) * 1e9
        body = adapter._attempt(lambda: itf.GetInterferenceBody(), default=None)
        box_txt = "no body"
        if body is not None:
            _flag(body, "IBody2")
            box = adapter._attempt(lambda: body.GetBodyBox(), default=None)
            if box is not None:
                mm = [v * 1000.0 for v in box]
                box_txt = (
                    f"x {mm[0]:.3f}..{mm[3]:.3f}  "
                    f"y {mm[1]:.3f}..{mm[4]:.3f}  "
                    f"z {mm[2]:.3f}..{mm[5]:.3f}"
                )
        print(f"  >> {' & '.join(names)}: {volume_mm3:.3f} mm^3  box {box_txt}", flush=True)
    adapter._attempt(lambda: mgr.Done(), default=None)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        ComponentRefParameters,
        InsertComponentParameters,
    )

    state = solve_default_state()
    zj = Z0
    log(f"rod tilt {state['rod_tilt']:.4f} deg")

    check("create_assembly", await adapter.create_assembly())

    res = await adapter.insert_component(
        InsertComponentParameters(
            file_path=_part("cylinder-gear"),
            position=[RING_CENTER[0], GEAR_AXIS_Y, zj - 1.5],
        )
    )
    check("insert cylinder-gear", res)
    # first insert is auto-fixed

    res = await adapter.insert_component(
        InsertComponentParameters(
            file_path=_part("connecting-rod"),
            position=[RING_CENTER[0], RING_CENTER[1], zj + CAM_DZ],
            rotation=[0.0, 0.0, state["rod_tilt"]],
        )
    )
    check("insert connecting-rod", res)
    rod_name = res.data["name"]
    if not res.data.get("fixed"):
        check(
            "fix connecting-rod",
            await adapter.fix_component(ComponentRefParameters(name=rod_name)),
        )
    rot_z_rows(state["rod_tilt"])  # parity with the channel script's read-back

    _report_interferences(adapter, "default placement")
    return {}


if __name__ == "__main__":
    sys.exit(run_build(build))
