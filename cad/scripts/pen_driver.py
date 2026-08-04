r"""Kinematic pen driver (plan F5): equation-drive the pen-rod travel mate from
a crank-angle global so the SW pose reproduces ``truth_model.pen_y`` with NO
force solver. The 21-spring summation is computed, not simulated — see
``cad/docs/motion-policy.md``.

Shared by ``build_pen_assembly.py`` (installs the driver inline as the pen
group is built) and ``verify.py`` (sweeps the global, samples the pen tip, and
asserts it matches ``truth_model``).

Mechanics (all proven live, see the pen-equation-driver memory):

* SW's equation manager rejects a 20-term sum in one expression, so the curve
  is accumulated through a chain of partial-sum globals ``S1..S20`` (each
  references the prior partial + one term), then ``PenY = Magnify * S20``.
* pen.SLDASM is an IPS (inch) document, and mate-dimension equations
  evaluate in DOCUMENT units — so the base + scale are expressed in doc units
  via the ``factor`` (doc units per mm) the caller reads off the mate's D1.
* The config coefficients are a math demo (square wave -> ~682 mm peak), so the
  curve is mapped onto a physical half-stroke (``output.pen_trace_half_mm``).
* At ``output.pen_rest_crank_deg`` the driver puts the pen at its build datum
  (the equation subtracts ``pen_y(rest)``), so the saved render pose is held.
"""
from __future__ import annotations

import math

import _config
import truth_model

CRANK_GLOBAL = "CrankDeg"
_SAMPLES = 720


def rest_crank_deg() -> float:
    return float(_config.machine("output", "pen_rest_crank_deg"))


def stroke_half_mm() -> float:
    return float(_config.machine("output", "pen_trace_half_mm"))


def _phases_deg() -> list[float]:
    return [ch["phase_deg"] for ch in _config.channels()]


def peak_pen_y() -> float:
    """Max |pen_y| over one fundamental period (the curve's half-amplitude)."""
    peak = max(abs(truth_model.pen_y(2 * math.pi * k / _SAMPLES)) for k in range(_SAMPLES))
    return peak or 1.0


def scale_mm_per_unit() -> float:
    """Physical mm of pen travel per unit of ``truth_model.pen_y``."""
    return stroke_half_mm() / peak_pen_y()


def pen_y_rest() -> float:
    return truth_model.pen_y(math.radians(rest_crank_deg()))


def _decimal(x: float) -> str:
    """Plain fixed-point literal for SW's equation/global parser.

    The parser rejects exponent notation (``e-13``) and a leading double operator
    (``- -1.9e-13``); a fixed-decimal global value sidesteps both. 15 places keeps
    full precision for normal magnitudes and is far below the motion tolerance for
    the near-zero rest offset of the square preset.
    """
    return f"{x:.15f}"


def expected_tip_disp_mm(theta_rad: float) -> float:
    """Pen-tip Y displacement (from the rest pose) the driver should realise."""
    return scale_mm_per_unit() * (truth_model.pen_y(theta_rad) - pen_y_rest())


def chain_links() -> list[tuple[str, str]]:
    """``(global_name, expression)`` for the S1..S20 partial-sum of the raw
    curve ``Σ a_j·cos(j·CrankDeg + φ_j)`` (all 20 harmonics, so an arbitrary
    coefficient vector still sums)."""
    js = truth_model.harmonics()
    amps = truth_model.coefficients("config")
    phases = _phases_deg()
    links: list[tuple[str, str]] = []
    for i, (a, j, phi) in enumerate(zip(amps, js, phases), start=1):
        term = f'{a:.12g}*cos({j}*"{CRANK_GLOBAL}"+{phi:.12g})'
        links.append((f"S{i}", term if i == 1 else f'"S{i - 1}"+{term}'))
    return links


async def set_crank_deg(adapter, theta_deg: float) -> None:
    """Set the CrankDeg global (used by verify.py to sweep the pose)."""
    from solidworks_mcp.adapters.base import SetGlobalVariableParameters
    res = await adapter.set_global_variable(
        SetGlobalVariableParameters(name=CRANK_GLOBAL, expression=f"{theta_deg:.12g}"))
    if not res.is_success:
        raise RuntimeError(f"set {CRANK_GLOBAL}={theta_deg}: {res.error}")


async def install(adapter, travel_mate_name: str, base_doc: float, factor: float) -> dict:
    """Install the globals + equation that drive the named travel mate.

    Args:
        adapter: connected adapter, ``currentModel`` = the assembly.
        travel_mate_name: the pen-rod travel distance mate (``_mate`` return name).
        base_doc: that mate's D1 value in DOCUMENT units (read after creation).
        factor: document units per mm (``base_doc / base_mm``).
    """
    from solidworks_mcp.adapters.base import (
        CreateEquationParameters, SetGlobalVariableParameters,
    )

    async def setg(name: str, expr: str) -> float:
        res = await adapter.set_global_variable(
            SetGlobalVariableParameters(name=name, expression=expr))
        if not res.is_success:
            raise RuntimeError(f"global {name} rejected: {res.error}")
        return float(res.data.get("value"))

    await setg("Magnify", f"{truth_model.magnify():.12g}")
    await setg(CRANK_GLOBAL, f"{rest_crank_deg():g}")
    links = chain_links()
    for name, expr in links:
        await setg(name, expr)
    await setg("PenY", f'"Magnify" * "S{len(links)}"')
    await setg("PenScale", f"{scale_mm_per_unit() * factor:.12g}")
    # Rest offset as a GLOBAL (not an inline literal): an arbitrary coefficient
    # vector can put pen_y(rest) anywhere, and inlining it risks a double operator
    # (``- -1.9e-13``) and exponent notation the SW parser rejects -- both avoided
    # by referencing a plain fixed-decimal global. At rest the mate == base, so the
    # saved render pose is held for ANY coefficient vector.
    await setg("PenRest", _decimal(pen_y_rest()))

    eqn = (f'"D1@{travel_mate_name}" = {base_doc:.9f} '
           f'+ "PenScale" * ("PenY" - "PenRest")')
    res = await adapter.create_equation(CreateEquationParameters(equation=eqn))
    if not res.is_success:
        raise RuntimeError(f"pen-driver equation rejected: {res.error}")
    return {
        "equation": eqn,
        "links": len(links),
        "scale_mm_per_unit": scale_mm_per_unit(),
        "rest_deg": rest_crank_deg(),
        "stroke_half_mm": stroke_half_mm(),
    }
