r"""Throwaway: validate the F5 wire/linkage couplings on the open springs-build doc.

The output chain parts (summing-lever, magnifying-lever, magnifying-wheel,
pen-rod) are ALL nested in the SAME output-1 flexible sub, so the couplings CANNOT
be top-level mates (same-flexible-sub AddMate restriction) -- they must be authored
INSIDE output.SLDASM's doc (currentModel retarget, siblings, never saved), exactly
like the in-sub rod<->rocker revolutes.

Three couplings drive the whole output chain from the spring-driven summing-lever:
  LINK  summing-lever(Rz) -> magnifying-lever(Rx)   gear ratio (lever linkage)
  WIRE1 magnifying-lever  -> magnifying-wheel(Rz)   gear ratio (clamp r : hub R)
  WIRE2 magnifying-wheel  -> pen-rod (Y slide)      rack_pinion (rim pitch Ø100)

Needs the mag-lever/wheel ANGLE snapshots + pen-rod travel DISTANCE suppressed
first (else the couplings over-constrain). Then reset + calc, sample pen Y +
wheel/lever rock. NEVER saves.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_wires.py
"""

from __future__ import annotations

import asyncio

from _common import _flag, _read_member, check, gear_mate, log, rack_pinion_mate
from build_motion_study import (
    ANGLE, DISTANCE, _comp_xform, _components, _entity_ref, _find_one, _iter_mates,
    _lone_real, _mate_value, _rot_angle, _sub_model, _suppress_named, _world,
)

STUDY = "Motion Study 2"
TIMES = [0.0, 0.75, 1.5, 2.25, 3.0, 3.75, 4.5, 5.25, 6.0]

RATIO_SUM_MAG = [1.0, 1.0]   # summing -> magnifying lever linkage (tunable)
RATIO_WIRE1 = [5.0, 1.0]     # mag-lever -> wheel (clamp radius : hub radius)
WIRE2_PITCH_MM = 100.0       # wheel rim pitch diameter -> pen travel = 50*theta


async def _suppress_pen_travel(adapter):
    """Suppress the pen-rod TRAVEL snapshot only (the largest-value pen-rod
    DISTANCE = its Y height); keep the slide-depth/across DISTANCE + spin ANGLE."""
    from solidworks_mcp.adapters.base import SuppressMateParameters
    _, model = _sub_model(adapter, "output-1")
    best = (None, -1.0)
    for _f, mate, name, mtype, parts, _v in _iter_mates(adapter, model, read_values=False):
        if mtype != DISTANCE or _lone_real(parts, "output") != "pen-rod":
            continue
        val = _mate_value(adapter, mate, mtype) or 0.0
        if val > best[1]:
            best = (name, val)
    if best[0] is None:
        log("  pen-rod travel snapshot NOT FOUND")
        return
    log(f"  suppressing pen-rod travel snapshot {best[0]} (val={best[1] * 1000:.1f}mm)")
    check("suppress pen travel", await adapter.suppress_mate(
        SuppressMateParameters(name=best[0], suppress=True, component="output-1")))


async def main():
    from solidworks_mcp.adapters.base import MotionTimeParameters
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    adapter = PyWin32Adapter({})
    print("Connecting (ATTACH) ...", flush=True)
    await adapter.connect()
    doc = adapter._attempt(lambda: adapter.swApp.ActiveDoc, default=None)
    if doc is None:
        log("no ActiveDoc")
        return
    _flag(doc, "IModelDoc2")
    adapter.currentModel = doc
    log(f"ActiveDoc = {str(_read_member(doc, 'GetTitle'))!r}")

    # 1) free the magnifying chain DOF.
    await _suppress_named(adapter, "output-1", ("magnifying-lever", "magnifying-wheel"),
                          (ANGLE,), "mag-lever + wheel rock")
    await _suppress_pen_travel(adapter)

    # 2) author the 3 couplings INSIDE the output sub doc.
    _, out_doc = _sub_model(adapter, "output-1")
    top = adapter.currentModel
    adapter.currentModel = out_doc
    try:
        link = await gear_mate(adapter, _entity_ref("summing-lever-1", "Axis1", "AXIS"),
                               _entity_ref("magnifying-lever-1", "Axis1", "AXIS"),
                               RATIO_SUM_MAG, label="LINK summing->mag")
        log(f"  LINK summing->mag: {link.get('name')}")
    except Exception as exc:  # noqa: BLE001
        log(f"  LINK FAILED: {exc}")
    try:
        w1 = await gear_mate(adapter, _entity_ref("magnifying-lever-1", "Axis1", "AXIS"),
                             _entity_ref("magnifying-wheel-1", "Axis1", "AXIS"),
                             RATIO_WIRE1, label="WIRE1 mag->wheel")
        log(f"  WIRE1 mag->wheel: {w1.get('name')}")
    except Exception as exc:  # noqa: BLE001
        log(f"  WIRE1 FAILED: {exc}")
    try:
        w2 = await rack_pinion_mate(adapter, _entity_ref("pen-rod-1", "Axis1", "AXIS"),
                                    _entity_ref("magnifying-wheel-1", "Axis1", "AXIS"),
                                    pinion_pitch_diameter=WIRE2_PITCH_MM,
                                    label="WIRE2 wheel->pen")
        log(f"  WIRE2 wheel->pen: {w2.get('name')}")
    except Exception as exc:  # noqa: BLE001
        log(f"  WIRE2 FAILED: {exc}")
    adapter._attempt(lambda: out_doc.ForceRebuild3(False), default=None)
    adapter.currentModel = top

    # 3) reset + calc + sample.
    await adapter.set_motion_time(MotionTimeParameters(time=0.0, study_name=STUDY))
    adapter._attempt(lambda: doc.ForceRebuild3(False), default=None)
    adapter._attempt(lambda: doc.EditRebuild3(), default=None)
    check("calc", await _calc(adapter))

    marker, _ = _find_one(adapter, "pen-marker")
    sl, _ = _find_one(adapter, "summing-lever-1")
    wh, _ = _find_one(adapter, "magnifying-wheel-1")
    base = {}
    ys = []
    spans = {}
    for t in TIMES:
        await adapter.set_motion_time(MotionTimeParameters(time=t, study_name=STUDY))
        if marker is not None:
            ys.append(_world(adapter, _comp_xform(adapter, marker), [0, 0, 0])[1])
        for key, comp in (("summing", sl), ("wheel", wh)):
            if comp is None:
                continue
            a = _comp_xform(adapter, comp)
            base.setdefault(key, a)
            spans[key] = max(spans.get(key, 0.0), _rot_angle(base[key], a))
    if ys:
        log(f"  pen-marker Y span = {max(ys) - min(ys):.3f} mm")
    log(f"  summing rock={spans.get('summing', 0):.1f}  wheel rock={spans.get('wheel', 0):.1f}")
    await adapter.disconnect()
    print("Disconnected (NOT saved).", flush=True)


async def _calc(adapter):
    from solidworks_mcp.adapters.base import MotionStudyRefParameters
    return await adapter.calculate_motion(MotionStudyRefParameters(name=STUDY))


if __name__ == "__main__":
    asyncio.run(main())
