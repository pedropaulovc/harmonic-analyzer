r"""Deterministic kinematic truth model — the machine's output, computed.

The harmonic analyzer synthesises ``f(x) = Σ a_j · cos(j·x + phase_j)`` over
j = 1..20, scaled by the magnifying lever to the pen. The 21-spring summation
is a static force balance that Basic Motion cannot solve reliably, so the pen
output is reproduced NUMERICALLY here (see docs/motion-policy.md) and the pen is
driven kinematically from this curve. This module is also the reference that
``verify.py`` compares the motion-study pen samples against.

Coefficients (a_j), harmonics (j) and the magnify factor come from
``cad/config/`` so the model and the geometry always agree. Pass an explicit
amplitude vector to evaluate an arbitrary setting.

    from truth_model import pen_curve, coefficients
    xs, ys = zip(*pen_curve())                 # default config amplitudes
    xs, ys = zip(*pen_curve(coefficients("square")))   # a preset waveform

CLI::

    python cad/scripts/truth_model.py --preset square --samples 25
"""
from __future__ import annotations

import argparse
import math

import _config
import _telemetry

TWO_PI = 2.0 * math.pi


def harmonics() -> list[int]:
    """Harmonic order j for each channel (cylinder rotations per fundamental)."""
    return [ch["harmonic_n"] for ch in _config.channels()]


def phases_rad() -> list[float]:
    return [math.radians(ch["phase_deg"]) for ch in _config.channels()]


def magnify() -> float:
    return float(_config.machine("output", "magnify_factor"))


def coefficients(preset: str = "config") -> list[float]:
    """An a_j vector (indexed by channel). ``config`` reads channels.yaml.

    Presets build a target waveform from the harmonic content the machine can
    represent (harmonics 1..20): ``zeros``, ``fundamental``, ``square``
    (odd harmonics 1/n), ``sawtooth`` (all harmonics 1/n).
    """
    js = harmonics()
    if preset == "config":
        return _config.amplitudes()
    if preset == "zeros":
        return [0.0] * len(js)
    if preset == "fundamental":
        return [1.0 if j == 1 else 0.0 for j in js]
    if preset == "square":
        return [(1.0 / j if j % 2 == 1 else 0.0) for j in js]
    if preset == "sawtooth":
        return [1.0 / j for j in js]
    raise ValueError(f"unknown preset: {preset}")


def pen_y(x: float, coeffs: list[float] | None = None) -> float:
    """Pen displacement at synthesis angle ``x`` (radians): magnify·Σ a_j cos(j x + φ_j)."""
    a = coefficients() if coeffs is None else coeffs
    js, ph = harmonics(), phases_rad()
    total = sum(aj * math.cos(j * x + p) for aj, j, p in zip(a, js, ph))
    return magnify() * total


def pen_curve(coeffs: list[float] | None = None, samples: int = 25) -> list[tuple[float, float]]:
    """``samples`` evenly spaced (x, pen_y) points over one fundamental period."""
    return [(x, pen_y(x, coeffs)) for x in (i * TWO_PI / samples for i in range(samples))]


def _main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--preset", default="config",
                    choices=["config", "zeros", "fundamental", "square", "sawtooth"])
    ap.add_argument("--samples", type=int, default=25)
    args = ap.parse_args()
    coeffs = coefficients(args.preset)
    nonzero = sum(1 for a in coeffs if a)
    _telemetry.info(f"preset={args.preset}  magnify={magnify()}  nonzero a_j={nonzero}")
    # The sample table is the command's DATA output (the documented `> curve.txt`
    # use), so it stays on stdout -- telemetry is reserved for status/progress.
    for x, y in pen_curve(coeffs, args.samples):
        print(f"x={math.degrees(x):6.1f} deg   pen_y={y:+8.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
