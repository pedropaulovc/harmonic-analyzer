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
from _common import drive_dimension, set_global

CRANK_GLOBAL = "CrankDeg"
_SAMPLES = 720


def rest_crank_deg() -> float:
    return float(_config.machine("output", "pen_rest_crank_deg"))


def stroke_half_mm() -> float:
    return float(_config.machine("output", "pen_trace_half_mm"))


def _phases_deg() -> list[float]:
    return [ch["phase_deg"] for ch in _config.channels()]


def peak_pen_y(amps: list[float] | None = None) -> float:
    """Max |pen_y| over one fundamental period (the curve's half-amplitude)."""
    peak = max(
        abs(truth_model.pen_y(2 * math.pi * k / _SAMPLES, amps)) for k in range(_SAMPLES)
    )
    return peak or 1.0


def scale_mm_per_unit(amps: list[float] | None = None) -> float:
    """Physical mm of pen travel per unit of ``truth_model.pen_y``."""
    return stroke_half_mm() / peak_pen_y(amps)


def pen_y_rest(amps: list[float] | None = None) -> float:
    return truth_model.pen_y(math.radians(rest_crank_deg()), amps)


def _decimal(x: float) -> str:
    """Plain fixed-point literal for SW's equation/global parser.

    The parser rejects exponent notation (``e-13``) and a leading double operator
    (``- -1.9e-13``); a fixed-decimal global value sidesteps both. 15 places keeps
    full precision for normal magnitudes and is far below the motion tolerance for
    the near-zero rest offset of the square preset.
    """
    return f"{x:.15f}"


def _signed(x: float) -> str:
    """``+ 1.5`` / ``- 1.5``: a joined term never forms a double operator."""
    return f"{'-' if x < 0 else '+'} {_decimal(abs(x))}"


def expected_tip_disp_mm(theta_rad: float, amps: list[float] | None = None) -> float:
    """Pen-tip Y displacement (from the rest pose) the driver should realise."""
    return scale_mm_per_unit(amps) * (
        truth_model.pen_y(theta_rad, amps) - pen_y_rest(amps)
    )


def chain_links(
    amps: list[float] | None = None, dropped: int | None = None
) -> list[tuple[str, str]]:
    """``(global_name, expression)`` for the S1..S20 partial-sum of the raw
    curve ``Σ a_j·cos(j·CrankDeg + φ_j)`` (all 20 harmonics, so an arbitrary
    coefficient vector still sums). ``amps`` defaults to the config vector.
    ``dropped`` (1-based) leaves that link's term out: the verify positive
    control proving the sweep sees a broken chain."""
    js = truth_model.harmonics()
    amps = truth_model.coefficients("config") if amps is None else amps
    phases = _phases_deg()
    links: list[tuple[str, str]] = []
    for i, (a, j, phi) in enumerate(zip(amps, js, phases), start=1):
        term = f'{_signed(a)}*cos({j}*"{CRANK_GLOBAL}" {_signed(phi)})'
        if i == dropped:
            term = "+ 0"
        links.append((f"S{i}", f"0 {term}" if i == 1 else f'"S{i - 1}" {term}'))
    return links


async def set_crank_deg(adapter, theta_deg: float) -> None:
    """Set the CrankDeg global (used by verify.py to sweep the pose)."""
    await set_global(adapter, CRANK_GLOBAL, f"{theta_deg:.12g}")


async def load_coefficients(
    adapter, factor: float, amps: list[float] | None = None, dropped: int | None = None
) -> int:
    """(Re)write the chain, scale and rest globals for coefficient vector ``amps``.

    The travel-mate equation references only these globals, so rewriting them
    retargets an installed driver: verify sweeps a non-zero vector on the
    transient model after the config sweep. Returns the number of chain links.
    """
    links = chain_links(amps, dropped)
    for name, expr in links:
        await set_global(adapter, name, expr)
    await set_global(adapter, "PenY", f'"Magnify" * "S{len(links)}"')
    await set_global(adapter, "PenScale", _decimal(scale_mm_per_unit(amps) * factor))
    # Rest offset as a GLOBAL (not an inline literal): an arbitrary coefficient
    # vector can put pen_y(rest) anywhere, and inlining it risks a double operator
    # (``- -1.9e-13``) and exponent notation the SW parser rejects -- both avoided
    # by referencing a plain fixed-decimal global. At rest the mate == base, so the
    # saved render pose is held for ANY coefficient vector.
    await set_global(adapter, "PenRest", _decimal(pen_y_rest(amps)))
    return len(links)


async def install(adapter, travel_mate_name: str, base_doc: float, factor: float) -> dict:
    """Install the globals + equation that drive the named travel mate.

    Args:
        adapter: connected adapter, ``currentModel`` = the assembly.
        travel_mate_name: the pen-rod travel distance mate (``_mate`` return name).
        base_doc: that mate's D1 value in DOCUMENT units (read after creation).
        factor: document units per mm (``base_doc / base_mm``).
    """
    await set_global(adapter, "Magnify", _decimal(truth_model.magnify()))
    await set_global(adapter, CRANK_GLOBAL, f"{rest_crank_deg():.12g}")
    links = await load_coefficients(adapter, factor)
    expression = f'{base_doc:.9f} + "PenScale" * ("PenY" - "PenRest")'
    await drive_dimension(adapter, f"D1@{travel_mate_name}", expression)
    return {
        "equation": f'"D1@{travel_mate_name}" = {expression}',
        "links": links,
        "scale_mm_per_unit": scale_mm_per_unit(),
        "rest_deg": rest_crank_deg(),
        "stroke_half_mm": stroke_half_mm(),
    }
