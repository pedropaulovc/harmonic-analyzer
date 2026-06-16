r"""THROWAWAY de-risk probe (F5): does SW's equation parser evaluate the full
20-term pen sum identically to ``truth_model.pen_y``?

The kinematic pen driver (plan Part F5) wants the pen-rod Y-travel mate
dimension driven by an equation of the form

    PenY = Magnify * SUM_j a_j * cos( j * CrankDeg + phi_j )      (j = 1..20)

with ``CrankDeg`` a global the motion study / verify.py sweeps, and a_j / j /
phi_j baked from ``cad/config``. Before wiring that into the VALIDATED top
assembly, prove the only genuine unknown on a scratch part with zero risk:

  1. SW accepts a long (20-term) equation-manager expression at all.
  2. It evaluates trig in DEGREES referencing another global (CrankDeg), so
     ``cos(j*CrankDeg_deg + phi_deg)`` == Python ``cos(j*theta_rad + phi_rad)``.
  3. The round-trip value matches ``truth_model.pen_y`` for many crank angles.

No geometry, no mate, no touching harmonic-analyzer.SLDASM. Delete after the
finding lands in memory.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_pen_equation.py
"""
from __future__ import annotations

import math
import sys

import truth_model
from _common import check, log, run_build


# Crank angles to spot-check (deg) -- spread across the period, off the axes.
TEST_ANGLES_DEG = [0.0, 30.0, 45.0, 90.0, 137.5, 200.0, 270.0, 333.3, 360.0]
TOL_MM = 1e-6  # parser-equality tolerance; this is a numeric identity, not a fit


def _pen_expr() -> str:
    """The PenY equation-manager expression (degrees), referencing CrankDeg/Magnify."""
    js = truth_model.harmonics()
    amps = truth_model.coefficients("config")
    phases_deg = [ch["phase_deg"] for ch in __import__("_config").channels()]
    terms = [
        f'{a:.12g} * cos( {j} * "CrankDeg" + {phi:.12g} )'
        for a, j, phi in zip(amps, js, phases_deg)
    ]
    return '"Magnify" * ( ' + " + ".join(terms) + " )"


async def _set_global(adapter, name: str, expression: str) -> float:
    from solidworks_mcp.adapters.base import SetGlobalVariableParameters

    res = await adapter.set_global_variable(
        SetGlobalVariableParameters(name=name, expression=expression)
    )
    data = check(f"global {name} = {expression[:60]}{'...' if len(expression) > 60 else ''}", res)
    value = data.get("value")
    if value is None:
        raise RuntimeError(f"global {name}: no evaluated value returned")
    return float(value)


async def _try(adapter, name: str, expr: str) -> float | None:
    """Upsert a global; return its value or None on rejection (no abort)."""
    from solidworks_mcp.adapters.base import SetGlobalVariableParameters

    res = await adapter.set_global_variable(
        SetGlobalVariableParameters(name=name, expression=expr)
    )
    if not res.is_success:
        print(f"  XX  {name} = {expr[:70]}{'...' if len(expr) > 70 else ''}\n"
              f"        -> REJECTED: {res.error}")
        return None
    value = res.data.get("value")
    print(f"  OK  {name} = {expr[:70]}{'...' if len(expr) > 70 else ''}  -> {value}")
    return None if value is None else float(value)


def _chain_links() -> list[tuple[str, str]]:
    """(global_name, expression) for the 20-link partial-sum chain.

    The equation manager rejects the whole 20-term sum as one expression, so
    accumulate it: ``S1 = a1*cos(1*CrankDeg+phi1)``, ``Sk = S{k-1} + ...``.
    Every link references at most the prior partial + one new term, so each
    stays well under the length limit. The chain covers ALL 20 harmonics (not
    just the currently-nonzero ones) so an arbitrary coefficient vector still
    sums correctly (plan F3).
    """
    js = truth_model.harmonics()
    amps = truth_model.coefficients("config")
    phases_deg = [ch["phase_deg"] for ch in __import__("_config").channels()]
    links: list[tuple[str, str]] = []
    for i, (a, j, phi) in enumerate(zip(amps, js, phases_deg), start=1):
        term = f'{a:.12g}*cos({j}*"CrankDeg"+{phi:.12g})'
        expr = term if i == 1 else f'"S{i - 1}"+{term}'
        links.append((f"S{i}", expr))
    return links


async def build(adapter) -> dict[str, str]:
    check("create_part (scratch)", await adapter.create_part())

    magnify = truth_model.magnify()
    await _try(adapter, "Magnify", f"{magnify:.12g}")
    await _try(adapter, "CrankDeg", "30")

    # --- Confirm the ladder finding: 2 terms OK, the chain replaces 20-in-one. ---
    log("--- building 20-link partial-sum chain ---")
    links = _chain_links()
    n = len(links)
    for name, expr in links:
        if await _try(adapter, name, expr) is None:
            raise RuntimeError(f"chain link {name} rejected -- chain approach unsafe")
    if await _try(adapter, "PenY", f'"Magnify" * "S{n}"') is None:
        raise RuntimeError("PenY = Magnify * S{n} rejected")

    # --- Sweep CrankDeg; the cascade must re-solve the whole chain. ---
    log("--- sweep CrankDeg vs truth_model (cascade re-eval test) ---")
    worst = 0.0
    for theta_deg in TEST_ANGLES_DEG:
        await _try(adapter, "CrankDeg", f"{theta_deg:.12g}")
        sw_value = await _try(adapter, "PenY", f'"Magnify" * "S{n}"')  # re-read
        want = truth_model.pen_y(math.radians(theta_deg))
        err = abs(sw_value - want) if sw_value is not None else float("inf")
        worst = max(worst, err)
        flag = "OK " if err <= TOL_MM else "XX "
        print(f"  {flag} theta={theta_deg:6.1f} deg   SW={sw_value:+10.5f}   "
              f"truth={want:+10.5f}   |err|={err:.2e}")
        if err > TOL_MM:
            raise RuntimeError(
                f"theta={theta_deg}: chain PenY={sw_value!r} vs truth {want!r} "
                f"(err {err:.3e}) -- cascade did not re-solve or dialect mismatch"
            )

    print(f"\n  OK  chained 20-link pen sum matches truth_model at all "
          f"{len(TEST_ANGLES_DEG)} angles (worst |err| {worst:.2e} mm)")
    return {"finding": f"chained {n}-link sum exact (worst err {worst:.2e} mm)"}


if __name__ == "__main__":
    sys.exit(run_build(build))
