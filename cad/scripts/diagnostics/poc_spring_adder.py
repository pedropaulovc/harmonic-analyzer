r"""Isolated POC: can Basic Motion SUM moving-anchor spring forces quasi-statically?

The harmonic analyzer sums its 20 channels by a SPRING FORCE BALANCE onto one
summing-lever (each channel-lever stretches its spring; the free summing-lever
settles to the force-weighted sum). Before rebuilding that in the full 345-part,
3-flexible-sub model (hour-long, fragile solves), prove the ONE decisive physics
question in isolation:

    N spring anchors driven sinusoidally at distinct freqs/amplitudes (= the
    harmonics / Fourier coefficients) all pull ONE free body, plus a counter
    spring. Does the free body's position track the WEIGHTED SUM of the inputs,
    cleanly (quasi-statically), or does it ring / lag / settle-and-hold?

Rig -- reuses two SAVED parts, no new geometry, no flexible subs -> solves in secs:
  * 3x pivot-shaft, FIXED, axis vertical (+Y), at x = -40, 0, +40.
  * 3x pivot-bushing, each CONCENTRIC on a shaft = a frictionless vertical slider.
      in1 (x=-40) + in2 (x=+40): INPUTS, each a LINEAR OSCILLATING motor (Y).
      out (x=0): FREE, held only by the springs.
  * Motion springs (linear, k from below; free_length=None = zero force at the
    assembled pose): in1->out, in2->out (the "channel" springs) and out->fixed
    shaft-end datum (the "counter" spring).

Acceptance is UNIT-AGNOSTIC -- we MEASURE the actually-driven motion rather than
trust the motor's amplitude units. Sample in1_y(t), in2_y(t), out_y(t); fit
    out_y ~= a*in1_y + b*in2_y + c   (ordinary least squares).
PASS if out moved AND the two-input fit R^2 >= 0.98 AND it beats both single-input
fits by a clear margin -> Basic Motion sums the moving-anchor spring forces
quasi-statically, so the spring path is viable for the full model. NEVER saves.

  C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\poc_spring_adder.py
"""

from __future__ import annotations

import asyncio

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
from build_motion_study_springs import _eye_point

# --- rig geometry (mm, assembly frame) --------------------------------------
SHAFT_R = 6.35 / 2.0       # pivot-shaft OD radius
BORE_R = 6.5 / 2.0         # pivot-bushing bore radius
BUSH_OD_R = 10.0 / 2.0     # pivot-bushing OD radius (unambiguous to select)
SHAFT_HALF = 228.6 / 2.0   # both-direction extrude half-length
VERT_ROT = [-90.0, 0.0, 0.0]  # part local +Z (cylinder axis) -> world +Y

IN_Y = 140.0               # input shafts/bushings centred high
OUT_SHAFT_Y = 40.0         # output shaft centred low (spans -74.3..154.3)
OUT_BUSH_Y = 70.0          # output bushing starts between the inputs and datum
X_IN1, X_IN2, X_OUT = -40.0, 40.0, 0.0

# arc_center edge picks (part-local mm) -> ring centre on the part axis.
BUSH_BORE_EDGE = [BORE_R, 0.0, 2.278]     # bushing bore top edge  -> (0,0,2.278)
SHAFT_END_EDGE = [SHAFT_R, 0.0, -SHAFT_HALF]  # shaft bottom OD edge -> (0,0,-114.3)

# --- motion params ----------------------------------------------------------
# The pivot-bushing is ~1.6 g. Stiff springs (k=2000 N/m) put the free-body
# natural frequency at ~178 Hz -> Basic Motion's integrator blows up and the
# solve aborts early (inputs freeze too). Soften k so omega_n ~ 2 Hz
# (k_eff = 2*K_CH + K_CT = 0.25 N/m, omega_n = sqrt(0.25/0.00162) ~ 12 rad/s),
# add a near-critical inline damper to each spring (c_crit ~ 0.04 N.s/m total),
# and drive the inputs slowly so the output tracks equilibrium quasi-statically.
import os
# k tuning (proven by poc_damper_check.py): k=2000 N/m aborts the solve (177 Hz,
# too stiff); k=0.1 N/m is too soft (forces ~0.003 N drown in numerical noise ->
# 50 mm wander); k~2 N/m settles cleanly (5.6 Hz). Basic Motion has STRONG
# inherent numerical damping (a free oscillator decays to its equilibrium with
# NO explicit damper), so no damper is needed for quasi-static tracking.
K_CH = float(os.environ.get("POC_KCH", "2.0"))   # N/m, the two channel springs
K_CT = float(os.environ.get("POC_KCT", "1.0"))   # N/m, the counter spring
C_SPRING = float(os.environ.get("POC_C", "0.0"))  # N.s/m per spring (optional)
AMP1, FREQ1 = 15.0, 0.10   # mm, Hz  (low order, slow for quasi-static)
AMP2, FREQ2 = 10.0, 0.20   # mm, Hz  (2x order)
DURATION = 20.0
N_SAMPLES = 100


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


def _slider(adapter, shaft_name, bush_name, x, shaft_y, bush_y, label):
    """Concentric (bushing OD <-> shaft OD) = a vertical slider.

    The bushing bore (r3.25) hugs the shaft OD (r3.175) within 0.075 mm, so a
    bore-surface point is ambiguous with the shaft OD; select the bushing OD
    (r5, unambiguous) and the shaft OD at a point clear of the bushing instead.
    Concentric only needs coaxial cylinders, not equal radii.
    """
    shaft_face = bore_axis_ref([x + SHAFT_R, shaft_y + 90.0, 0.0], "FACE")
    bush_face = bore_axis_ref([x + BUSH_OD_R, bush_y, 0.0], "FACE")
    return concentric_mate(adapter, shaft_face, bush_face, label=label)


async def _osc_motor(adapter, bush_name, x, y, amp, freq, label):
    from solidworks_mcp.adapters.base import MotionMotorParameters
    entity = bore_axis_ref([x + BUSH_OD_R, y, 0.0], "FACE")
    return check(label, await adapter.add_motor(MotionMotorParameters(
        motor_type="linear", entity=entity, component=bush_name,
        motion_function="oscillating", amplitude=amp, frequency=freq,
        study_name="")))


def _ls_fit(cols, y):
    """Ordinary least squares y ~ sum(coef_i * cols_i) + const; returns (coefs, R2).

    cols: list of equal-length input lists (the design columns, const added here).
    """
    design = [list(c) for c in cols] + [[1.0] * len(y)]
    m = len(design)
    # normal equations A coef = b, A[i][j] = <col_i, col_j>, b[i] = <col_i, y>.
    a = [[sum(design[i][t] * design[j][t] for t in range(len(y)))
          for j in range(m)] for i in range(m)]
    b = [sum(design[i][t] * y[t] for t in range(len(y))) for i in range(m)]
    coef = _solve(a, b)
    pred = [sum(coef[i] * design[i][t] for i in range(m)) for t in range(len(y))]
    ybar = sum(y) / len(y)
    ss_tot = sum((v - ybar) ** 2 for v in y) or 1e-12
    ss_res = sum((y[t] - pred[t]) ** 2 for t in range(len(y)))
    return coef, 1.0 - ss_res / ss_tot


def _solve(a, b):
    """Gaussian elimination (tiny systems)."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        m[col], m[piv] = m[piv], m[col]
        d = m[col][col] or 1e-12
        m[col] = [v / d for v in m[col]]
        for r in range(n):
            if r == col:
                continue
            f = m[r][col]
            m[r] = [m[r][k] - f * m[col][k] for k in range(n + 1)]
    return [m[i][n] for i in range(n)]


async def main():
    from solidworks_mcp.adapters.base import (
        MotionSpringParameters, MotionStudyParameters, MotionStudyRefParameters,
        MotionTimeParameters,
    )
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    adapter = PyWin32Adapter({})
    print("Connecting ...", flush=True)
    await adapter.connect()
    check("create_assembly", await adapter.create_assembly())
    log("created empty POC assembly (never saved)")

    # shafts (fixed vertical guides) + bushings (vertical sliders).
    s_in1 = await _insert(adapter, "pivot-shaft", [X_IN1, IN_Y, 0.0], fixed=True)
    s_in2 = await _insert(adapter, "pivot-shaft", [X_IN2, IN_Y, 0.0], fixed=True)
    s_out = await _insert(adapter, "pivot-shaft", [X_OUT, OUT_SHAFT_Y, 0.0], fixed=True)
    b_in1 = await _insert(adapter, "pivot-bushing", [X_IN1, IN_Y, 0.0], fixed=False)
    b_in2 = await _insert(adapter, "pivot-bushing", [X_IN2, IN_Y, 0.0], fixed=False)
    b_out = await _insert(adapter, "pivot-bushing", [X_OUT, OUT_BUSH_Y, 0.0], fixed=False)

    await _slider(adapter, s_in1, b_in1, X_IN1, IN_Y, IN_Y, "slider in1")
    await _slider(adapter, s_in2, b_in2, X_IN2, IN_Y, IN_Y, "slider in2")
    await _slider(adapter, s_out, b_out, X_OUT, OUT_SHAFT_Y, OUT_BUSH_Y, "slider out")

    # mateable centre points on the SHARED part docs (inherited by all instances).
    bush_pt = await _eye_point(adapter, b_in1, BUSH_BORE_EDGE, "bushing bore centre")
    shaft_pt = await _eye_point(adapter, s_out, SHAFT_END_EDGE, "shaft end datum")

    check("ensure_motion_addin", await adapter.ensure_motion_addin())
    made = check("create_motion_study", await adapter.create_motion_study(
        MotionStudyParameters(name="", study_type="physical_simulation",
                              duration=DURATION, activate=True)))
    log(f"  study {made['name']!r}")

    # input oscillating motors.
    await _osc_motor(adapter, b_in1, X_IN1, IN_Y, AMP1, FREQ1, "motor in1")
    await _osc_motor(adapter, b_in2, X_IN2, IN_Y, AMP2, FREQ2, "motor in2")

    # springs: in1->out, in2->out (channel), out->fixed shaft datum (counter).
    for src, lbl in ((b_in1, "spring in1->out"), (b_in2, "spring in2->out")):
        check(lbl, await adapter.add_motion_spring(MotionSpringParameters(
            spring_type="linear",
            endpoints=[component_named_ref(src, bush_pt, "POINT"),
                       component_named_ref(b_out, bush_pt, "POINT")],
            spring_constant=K_CH, free_length=None,
            damping_constant=C_SPRING, study_name="")))
    check("counter spring", await adapter.add_motion_spring(MotionSpringParameters(
        spring_type="linear",
        endpoints=[component_named_ref(b_out, bush_pt, "POINT"),
                   component_named_ref(s_out, shaft_pt, "POINT")],
        spring_constant=K_CT, free_length=None,
        damping_constant=C_SPRING, study_name="")))

    # DIAGNOSTIC: a separate damper element from out -> fixed ground datum. This
    # is the most direct possible velocity sink on the free node. If even a huge
    # value here does NOT shrink out's span, Basic Motion is not integrating
    # damper force elements at all (spring path would be doomed -> interpolated).
    gd = float(os.environ.get("POC_GD", "0.0"))
    if gd > 0:
        from solidworks_mcp.adapters.base import MotionDamperParameters
        check("ground damper out", await adapter.add_motion_damper(
            MotionDamperParameters(
                damper_type="linear",
                endpoints=[component_named_ref(b_out, bush_pt, "POINT"),
                           component_named_ref(s_out, shaft_pt, "POINT")],
                damping_constant=gd, study_name="")))

    # reset to assembled pose, then solve once.
    await adapter.set_motion_time(MotionTimeParameters(time=0.0, study_name=""))
    adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False), default=None)
    adapter._attempt(lambda: adapter.currentModel.EditRebuild3(), default=None)
    log("  Calculate() ...")
    check("calculate_motion", await adapter.calculate_motion(
        MotionStudyRefParameters(name="")))

    # Drop the startup transient before fitting: the free node needs ~1-2 s to
    # settle from the assembled pose onto the moving spring equilibrium, and
    # those frames are not quasi-static.
    settle = float(os.environ.get("POC_SETTLE", "3.0"))
    in1, in2, out = [], [], []
    for s in range(N_SAMPLES + 1):
        t = DURATION * s / N_SAMPLES
        await adapter.set_motion_time(MotionTimeParameters(time=t, study_name=""))
        y = {}
        for key, nm in (("in1", b_in1), ("in2", b_in2), ("out", b_out)):
            a = component_transform(adapter, nm)
            y[key] = a[10] * 1000.0 if a else None
        if None in y.values():
            log(f"    t={t:5.2f} transient read; skip")
            continue
        if t < settle:
            continue
        in1.append(y["in1"]); in2.append(y["in2"]); out.append(y["out"])
        if s % 6 == 0:
            log(f"    t={t:5.2f}s  in1={y['in1']:8.3f}  in2={y['in2']:8.3f}  "
                f"out={y['out']:8.3f}")

    def span(v):
        return (max(v) - min(v)) if v else 0.0
    log(f"  settled samples={len(out)} (dropped t<{settle:.1f}s)")
    log(f"  spans(mm): in1={span(in1):.3f} in2={span(in2):.3f} out={span(out):.3f}")

    if span(in1) < 0.5 or span(in2) < 0.5:
        log("  FAIL: an input motor did not drive its bushing (span ~ 0)")
    elif span(out) < 0.2:
        log("  FAIL: the output never moved -> springs not transmitting / frozen")
    else:
        (a, b, c), r2 = _ls_fit([in1, in2], out)
        (_a1, _c1), r2_1 = _ls_fit([in1], out)
        (_a2, _c2), r2_2 = _ls_fit([in2], out)
        log(f"  fit out = {a:+.4f}*in1 {b:+.4f}*in2 {c:+.3f}")
        log(f"  R^2: two-input={r2:.4f}  in1-only={r2_1:.4f}  in2-only={r2_2:.4f}")
        verdict = ("PASS" if r2 >= 0.98 and r2 - max(r2_1, r2_2) > 0.02
                   else "WEAK/FAIL")
        log(f"  VERDICT: {verdict} -- Basic Motion {'SUMS' if verdict=='PASS' else 'does NOT cleanly sum'} "
            f"moving-anchor springs quasi-statically")

    await adapter.disconnect()
    print("Disconnected (NOT saved).", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
