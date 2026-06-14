r"""Fast dump (NO calc, NO flex): list every pen-rod mate in output.SLDASM with
type + value + entity reference types, to identify the TRUE Y-travel snapshot.

The wire probe suppressed pen-rod "Distance12" (val=15669mm -- absurd for a ~1m
machine), the pen then did not move under the wheel rack-pinion -> the
largest-value heuristic likely suppressed the WRONG pen-rod distance, leaving the
real Y-travel pinned. This dump shows the truth. NEVER saves.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_pen_mates.py
"""

from __future__ import annotations

import asyncio

from _common import OUT_SLDASM, check, log
from build_motion_study import (
    ANGLE, ASM, DISTANCE, _family, _iter_mates, _lone_real, _read_member,
    _sub_model,
)

_RT = {1: "PLANE", 2: "AXIS", 3: "POINT", 4: "FACE", 5: "EDGE", 6: "VERTEX",
       7: "ORIGIN", 8: "SKETCH"}


def _entity_kinds(adapter, mate):
    from build_motion_study import _flag
    kinds = []
    n = int(adapter._attempt(lambda: mate.GetMateEntityCount(), default=0))
    for i in range(n):
        me = adapter._attempt(lambda k=i: mate.MateEntity(k), default=None)
        if me is None:
            continue
        _flag(me, "IMateEntity2")
        rt = adapter._attempt(lambda e=me: e.ReferenceType2, default=None)
        if rt is None:
            rt = adapter._attempt(lambda e=me: e.ReferenceType, default=None)
        kinds.append(_RT.get(int(rt) if rt is not None else -1, str(rt)))
    return kinds


async def main():
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    adapter = PyWin32Adapter({})
    print("Connecting ...", flush=True)
    await adapter.connect()
    asm_path = str((OUT_SLDASM / f"{ASM}.SLDASM").resolve())
    check("open", await adapter.open_model(asm_path))
    log(f"opened {asm_path}")

    _, model = _sub_model(adapter, "output-1")
    log("  --- pen-rod DISTANCE/ANGLE mates in output ---")
    for _f, mate, name, mtype, parts, val in _iter_mates(adapter, model, read_values=False):
        lone = _lone_real(parts, "output")
        if lone is None or _family(lone) != "pen-rod":
            continue
        if mtype not in (DISTANCE, ANGLE):
            continue
        from build_motion_study import _mate_value
        v = _mate_value(adapter, mate, mtype)
        kinds = _entity_kinds(adapter, mate)
        tname = "DISTANCE" if mtype == DISTANCE else "ANGLE"
        vstr = f"{v * 1000:.2f}mm" if (v is not None and mtype == DISTANCE) else (
            f"{v:.4f}rad" if v is not None else "None")
        log(f"    {name:16s} {tname:9s} val={vstr:14s} ents={kinds} parts={sorted(set(parts))}")
    await adapter.disconnect()
    print("Disconnected (NOT saved).", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
