r"""THROWAWAY de-risk probe (F5): equation-drive the pen-rod travel mate on a
FRESH pen carriage (current geometry) and prove the pen tip follows truth_model.

The saved output.SLDASM is stale (its pen-rod distance mates don't match the
current build_output_assembly.py), so identifying the travel mate in it is
unreliable. Instead build just the 3-part pen carriage (v-block + rod + marker,
exactly probe_pen.py's rig, current constants), CAPTURE the travel mate as it
is created, drive its dimension from the chained crank-angle sum, and sweep:

  * tip Y must track ``base_tip + PenScale * truth_model.pen_y(CrankDeg)``
  * default CrankDeg = 90 deg (curve zero-crossing) holds the rest pose
  * DOF stays fully-defined; carriage clears itself across the stroke

This proves the inline mate-driving mechanics + chosen stroke BEFORE paying a
full 123-component output rebuild. NEVER saves.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_pen_mate.py
"""
from __future__ import annotations

import math
import sys

import truth_model
from _common import (
    angle_driver, check, check_no_interference, component_transform,
    distance_driver, lock_mate, log, named_ref, place_component, run_build,
)

VBLOCK_POS = (-24.0, 390.0, -159.5)
PEN_ROD_POS = (-3.0, 398.0, -154.0)
MARKER_POS = (-13.0, 368.0, -151.5)
IDENTITY = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]

DEFAULT_CRANK_DEG = 90.0    # curve zero-crossing -> mate == base, rest pose held
PEN_STROKE_HALF_MM = 15.0   # physical half-travel the math curve maps onto
SWEEP_DEG = [0.0, 30.0, 45.0, 90.0, 135.0, 180.0, 225.0, 270.0, 315.0, 360.0]
TOL_MM = 1e-3


def _org(adapter, name):
    a = component_transform(adapter, name)
    return [a[9] * 1000.0, a[10] * 1000.0, a[11] * 1000.0]


def _chain_links():
    import _config
    js = truth_model.harmonics()
    amps = truth_model.coefficients("config")
    phases_deg = [ch["phase_deg"] for ch in _config.channels()]
    links = []
    for i, (a, j, phi) in enumerate(zip(amps, js, phases_deg), start=1):
        term = f'{a:.12g}*cos({j}*"CrankDeg"+{phi:.12g})'
        links.append((f"S{i}", term if i == 1 else f'"S{i - 1}"+{term}'))
    return links


def _peak_pen_y():
    return max(abs(truth_model.pen_y(2 * math.pi * k / 720)) for k in range(720))


async def _setg(adapter, name, expr):
    from solidworks_mcp.adapters.base import SetGlobalVariableParameters
    res = await adapter.set_global_variable(
        SetGlobalVariableParameters(name=name, expression=expr))
    if not res.is_success:
        raise RuntimeError(f"global {name} rejected: {res.error}")
    v = res.data.get("value")
    return None if v is None else float(v)


def _rebuild(adapter):
    adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False), default=None)
    adapter._attempt(lambda: adapter.currentModel.EditRebuild3(), default=None)


async def build(adapter):
    from solidworks_mcp.adapters.base import CreateEquationParameters

    check("create_assembly", await adapter.create_assembly())
    await place_component(adapter, "pen-v-block", list(VBLOCK_POS),
                          [0.0, 0.0, 0.0], IDENTITY, ground=True)
    rod = await place_component(adapter, "pen-rod", list(PEN_ROD_POS),
                                [0.0, 0.0, 0.0], IDENTITY, ground=False)
    rod_o = _org(adapter, rod)
    await distance_driver(adapter, named_ref(f"Axis1@{rod}", "AXIS"),
                          named_ref("Front Plane", "PLANE"), abs(rod_o[2]),
                          label="pen-rod slide depth", verify=(rod, rod_o))
    await distance_driver(adapter, named_ref(f"Axis1@{rod}", "AXIS"),
                          named_ref("Right Plane", "PLANE"), abs(rod_o[0]),
                          label="pen-rod slide across", verify=(rod, rod_o))
    await angle_driver(adapter, named_ref(f"Front Plane@{rod}", "PLANE"),
                       named_ref("Front Plane", "PLANE"), 0.0,
                       label="pen-rod spin snapshot", verify=(rod, rod_o))
    travel = await distance_driver(adapter, named_ref(f"Top Plane@{rod}", "PLANE"),
                                   named_ref("Top Plane", "PLANE"), abs(rod_o[1]),
                                   label="pen-rod travel snapshot", verify=(rod, rod_o))
    travel_name = travel.get("name")
    base_mm = abs(rod_o[1])
    log(f"travel mate = {travel_name!r}, base = {base_mm:.3f} mm")

    mk = await place_component(adapter, "pen-marker", list(MARKER_POS),
                               [0.0, 0.0, 0.0], IDENTITY, ground=False)
    await lock_mate(adapter, named_ref(f"Front Plane@{mk}", "PLANE"),
                    named_ref(f"Front Plane@{rod}", "PLANE"),
                    label="pen-marker locked to rod")

    # Dimension equations evaluate in DOCUMENT units (this assembly is IPS ->
    # inches; cone-gear lesson). Read the just-created mate's value to learn the
    # doc-units-per-mm factor, then express base + scale in doc units. The pen
    # tip still moves in physical mm, so `want` uses the mm scale.
    from _common import _read_member
    p = adapter._attempt(lambda: adapter.currentModel.Parameter(f"D1@{travel_name}"),
                         default=None)
    base_doc = float(_read_member(p, "Value")) if p is not None else base_mm
    factor = base_doc / base_mm  # doc units per mm (1.0 mm-doc, ~1/25.4 inch-doc)
    log(f"travel D1 reads {base_doc:.5f} (doc units) -> {factor:.6g} doc/mm")

    peak = _peak_pen_y()
    scale_mm = PEN_STROKE_HALF_MM / peak          # physical mm per curve unit
    pen_scale_doc = scale_mm * factor             # doc units per curve unit
    log(f"peak|pen_y| = {peak:.3f}; +-{PEN_STROKE_HALF_MM} mm stroke "
        f"(scale {scale_mm:.6g} mm/unit, {pen_scale_doc:.6g} doc/unit)")

    await _setg(adapter, "Magnify", f"{truth_model.magnify():.12g}")
    await _setg(adapter, "CrankDeg", f"{DEFAULT_CRANK_DEG:g}")
    links = _chain_links()
    for name, expr in links:
        await _setg(adapter, name, expr)
    await _setg(adapter, "PenY", f'"Magnify" * "S{len(links)}"')
    await _setg(adapter, "PenScale", f"{pen_scale_doc:.12g}")

    dim = f"D1@{travel_name}"
    eqn = f'"{dim}" = {base_doc:.9f} + "PenScale" * "PenY"'
    check("equation-drive pen travel", await adapter.create_equation(
        CreateEquationParameters(equation=eqn)))
    log(f"equation: {eqn}")

    await _setg(adapter, "CrankDeg", f"{DEFAULT_CRANK_DEG:g}")
    _rebuild(adapter)
    tip0 = _org(adapter, mk)[1]
    log(f"baseline @ {DEFAULT_CRANK_DEG:g} deg: tipY = {tip0:.4f} mm")

    worst, bad = 0.0, 0
    for theta in SWEEP_DEG:
        await _setg(adapter, "CrankDeg", f"{theta:g}")
        _rebuild(adapter)
        tip = _org(adapter, mk)[1]
        want = scale_mm * truth_model.pen_y(math.radians(theta))
        got = tip - tip0
        err = abs(got - want)
        worst = max(worst, err)
        flag = "OK " if err <= TOL_MM else "XX "
        bad += err > TOL_MM
        print(f"  {flag} theta={theta:6.1f}  tipY={tip:9.4f}  disp={got:+8.4f}"
              f"  want={want:+8.4f}  |err|={err:.2e}")

    log(f"tip-follows-curve worst |err| = {worst:.2e} mm ({bad} over tol)")

    for theta in (0.0, 180.0):
        await _setg(adapter, "CrankDeg", f"{theta:g}")
        _rebuild(adapter)
        try:
            check_no_interference(adapter)
            log(f"  interference @ {theta:g}: none")
        except Exception as exc:  # noqa: BLE001
            log(f"  XX interference @ {theta:g}: {exc}")
            bad += 1

    verdict = "SAFE" if bad == 0 and worst <= TOL_MM else f"PROBLEMS ({bad})"
    print(f"\nVERDICT: {verdict} -- stroke +-{PEN_STROKE_HALF_MM} mm, "
          f"worst tip err {worst:.2e} mm")
    return {"verdict": verdict}


if __name__ == "__main__":
    sys.exit(run_build(build))
