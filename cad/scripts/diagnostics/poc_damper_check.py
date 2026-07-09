r"""Decisive textbook test: does Basic Motion integrate DAMPER force elements?

The spring-summation POC (poc_spring_adder.py) showed the free output node rings
with ~50 mm span that does NOT shrink as the damper goes from 0.012 to 50 N.s/m
(a ~4000x sweep). That implies dampers are simply not integrated by the Basic
Motion ("physical_simulation") solver -- but before pivoting the whole F6 design
away from springs, prove it with the cleanest possible experiment, free of the
diagonal-spring geometry / summation / massless-artifact doubts:

  ONE pivot-bushing on ONE fixed vertical pivot-shaft = a 1-DOF vertical slider.
  Gravity -Y. ONE linear spring bushing -> fixed shaft-end datum (free_length =
  assembled length => zero preload at start). Released from rest. Gravity pulls
  it down; it must oscillate about the static-sag equilibrium (sag = m g / k).

  Run twice: POC_C=0 (undamped) and POC_C=large. A working damper makes the ON
  run DECAY to the sag point while the OFF run keeps oscillating. If both behave
  identically -> Basic Motion ignores dampers -> the spring force-balance path
  cannot be cleaned up -> proceed with the interpolated-motor path.

  C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\poc_damper_check.py

NEVER saves.
"""

from __future__ import annotations

import asyncio
import os

from _common import (
    check,
    log,
)
from _assembly import (
    bore_axis_ref,
    component_named_ref,
    component_transform,
    concentric_mate,
)
from build_motion_study import _eye_point

import _telemetry

SHAFT_R = 6.35 / 2.0
BUSH_OD_R = 10.0 / 2.0
BORE_R = 6.5 / 2.0
SHAFT_HALF = 228.6 / 2.0
VERT_ROT = [-90.0, 0.0, 0.0]

X = 0.0
SHAFT_Y = 140.0          # shaft centred high so the bushing has room to sag
BUSH_Y = 200.0           # bushing starts near the top, above the sag equilibrium
BUSH_BORE_EDGE = [BORE_R, 0.0, 2.278]
SHAFT_END_EDGE = [SHAFT_R, 0.0, -SHAFT_HALF]   # bottom datum, well below the sag

K = 2.0                  # N/m -> sag = m g / k ~ 8 mm (stays on the shaft), w_n ~ 35 rad/s
C_DAMP = float(os.environ.get("POC_C", "0.0"))   # N.s/m parallel damper
DURATION = 8.0
N_SAMPLES = 160


async def _insert(adapter, part, pos, *, fixed):
    from solidworks_mcp.adapters.base import (
        ComponentRefParameters, InsertComponentParameters,
    )
    from _common import OUT_SLDPRT
    path = str((OUT_SLDPRT / f"{part}.SLDPRT").resolve())
    data = check(f"insert {part} @ {pos}", await adapter.insert_component(
        InsertComponentParameters(file_path=path, position=pos, rotation=VERT_ROT,
                                  configuration="")))
    name = data["name"]
    if fixed and not data.get("fixed"):
        check(f"fix {name}", await adapter.fix_component(
            ComponentRefParameters(name=name)))
    return name


async def main():
    from solidworks_mcp.adapters.base import (
        MotionGravityParameters, MotionSpringParameters, MotionStudyParameters,
        MotionStudyRefParameters, MotionTimeParameters,
    )
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    adapter = PyWin32Adapter({})
    _telemetry.info(f"Connecting ... (POC_C={C_DAMP})")
    await adapter.connect()
    check("create_assembly", await adapter.create_assembly())

    shaft = await _insert(adapter, "pivot-shaft", [X, SHAFT_Y, 0.0], fixed=True)
    bush = await _insert(adapter, "pivot-bushing", [X, BUSH_Y, 0.0], fixed=False)

    # vertical slider: bushing OD concentric with shaft OD (clear of the bushing).
    concentric_mate(adapter,
                    bore_axis_ref([X + SHAFT_R, SHAFT_Y + 90.0, 0.0], "FACE"),
                    bore_axis_ref([X + BUSH_OD_R, BUSH_Y, 0.0], "FACE"),
                    label="slider")

    bush_pt = await _eye_point(adapter, bush, BUSH_BORE_EDGE, "bushing centre")
    shaft_pt = await _eye_point(adapter, shaft, SHAFT_END_EDGE, "shaft datum")

    check("ensure_motion_addin", await adapter.ensure_motion_addin())
    check("create_motion_study", await adapter.create_motion_study(
        MotionStudyParameters(name="", study_type="physical_simulation",
                              duration=DURATION, activate=True)))

    check("gravity", await adapter.add_gravity(MotionGravityParameters(
        axis="y", reverse=True, strength=9.81, study_name="")))
    check("spring", await adapter.add_motion_spring(MotionSpringParameters(
        spring_type="linear",
        endpoints=[component_named_ref(bush, bush_pt, "POINT"),
                   component_named_ref(shaft, shaft_pt, "POINT")],
        spring_constant=K, free_length=None,
        damping_constant=C_DAMP, study_name="")))

    await adapter.set_motion_time(MotionTimeParameters(time=0.0, study_name=""))
    adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False), default=None)
    adapter._attempt(lambda: adapter.currentModel.EditRebuild3(), default=None)
    log("  Calculate() ...")
    check("calculate_motion", await adapter.calculate_motion(
        MotionStudyRefParameters(name="")))

    ys = []
    for s in range(N_SAMPLES + 1):
        t = DURATION * s / N_SAMPLES
        await adapter.set_motion_time(MotionTimeParameters(time=t, study_name=""))
        a = component_transform(adapter, bush)
        if a:
            ys.append((t, a[10] * 1000.0))

    if not ys:
        log("  FAIL: no samples")
    else:
        y0 = ys[0][1]
        # late-window peak-to-peak: a working damper makes this collapse.
        late = [v for (t, v) in ys if t >= DURATION * 0.6]
        early = [v for (t, v) in ys if t <= DURATION * 0.4]
        pp_late = (max(late) - min(late)) if late else 0.0
        pp_early = (max(early) - min(early)) if early else 0.0
        for (t, v) in ys:
            if abs((t / (DURATION / N_SAMPLES)) % 8) < 1e-6:  # every 8th sample
                log(f"    t={t:5.2f}s  y={v:8.3f}  (dy0={v - y0:+7.3f})")
        log(f"  start y={y0:.3f}  early pk-pk={pp_early:.3f}  late pk-pk={pp_late:.3f}  "
            f"decay ratio late/early={pp_late / (pp_early or 1e-9):.3f}")
        if pp_early < 0.5:
            log("  INCONCLUSIVE: barely oscillated (raise gravity/K mismatch)")
        elif pp_late / (pp_early or 1e-9) < 0.5:
            log(f"  DAMPER WORKS: oscillation decayed (POC_C={C_DAMP})")
        else:
            log(f"  DAMPER IGNORED: no decay (POC_C={C_DAMP}) -> Basic Motion does "
                f"not integrate dampers")

    await adapter.disconnect()
    _telemetry.info("Disconnected (NOT saved).")


if __name__ == "__main__":
    asyncio.run(main())
