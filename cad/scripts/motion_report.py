r"""SW-free post-process for the operation motion study: turn a
``cad/out/reports/motion/<stage>-samples.json`` (written by
build_motion_study.py) into the proof assets --

  * ``<stage>-report.png``: crank tracking, rocker oscillation, the
    spring-summed output chain, and (full stage) the pen trace overlaid on the
    truth_model curve with a phase-fit correlation;
  * ``<stage>-report.md``: the numbers behind the figure.

The pen comparison is SHAPE-normalized: the physical chain's absolute gain
(spring balance -> knife-lever arm -> wheel -> yoke) is not calibrated, so both
curves are scaled to unit peak; the claim proven is "the pen traces the
band-limited synthesis", quantified by the peak Pearson r over a one-period
phase sweep (the crank rest angle is arbitrary vs the truth curve's theta=0).

    uv run python cad\scripts\motion_report.py [stage]   # default: full
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import _telemetry

# Categorical palette (fixed assignment order, CVD-safe spacing).
C_BLUE, C_ORANGE, C_RED, C_TEAL = "#4269d0", "#efb118", "#ff725c", "#6cc5b0"
INK, MUTED, GRID = "#1a1a2e", "#5c5c6e", "#e4e4ec"

OUT_MOTION = Path(__file__).resolve().parents[1] / "out" / "reports" / "motion"


def _load(stage: str) -> dict:
    path = OUT_MOTION / f"{stage}-samples.json"
    if not path.exists():
        raise SystemExit(f"no samples at {path}; run build_motion_study.py {stage}")
    return json.loads(path.read_text())


def _norm(vals: list[float]) -> list[float]:
    if not vals:
        return vals
    mid = sum(vals) / len(vals)
    dev = [v - mid for v in vals]
    peak = max(abs(v) for v in dev) or 1.0
    return [v / peak for v in dev]


def _pearson(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    ma, mb = sum(a) / n, sum(b) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    va = math.sqrt(sum((x - ma) ** 2 for x in a))
    vb = math.sqrt(sum((y - mb) ** 2 for y in b))
    return cov / (va * vb) if va and vb else 0.0


def _truth_fit(pen: list[tuple[float, float]], rpm: float, preset: str,
               truth: dict | None = None):
    """Phase-fit the truth curve to the sampled pen trace.

    Returns (best_r, best_phase_deg, truth_series aligned to the samples).
    The crank rest angle (and the yoke's sign) are arbitrary vs truth theta=0,
    so sweep the phase over a full period at 1-degree steps and keep the
    magnitude-best r (sign folded into the returned series).

    ``truth`` is the FULL truth-input record the SOLVE actually ran under
    (coefficients + harmonics + phases + magnify, persisted in the samples
    JSON via the build-time studies sidecar); when present it is used
    verbatim, so a config edit after solving -- amplitudes, phases, harmonic
    table or magnify alike -- cannot swap the curve out from under the saved
    trace (codex #217). ``None``/partial falls back to reading config at
    report time (older samples files).
    """
    import truth_model
    truth = truth or {}
    coeffs = truth.get("coefficients_mm")
    kw = {}
    if coeffs is None:
        coeffs = truth_model.coefficients("square" if preset == "square" else "config")
    else:
        if truth.get("harmonics") is not None:
            kw["js"] = [int(j) for j in truth["harmonics"]]
        if truth.get("phases_deg") is not None:
            kw["phases"] = [math.radians(p) for p in truth["phases_deg"]]
        if truth.get("magnify") is not None:
            kw["magnify_factor"] = float(truth["magnify"])
    ts = [t for t, _y in pen]
    ys = _norm([y for _t, y in pen])
    deg_per_s = 360.0 * rpm / 60.0
    best = (0.0, 0.0, [0.0] * len(ts))
    for phase in range(0, 360):
        # pen_y takes RADIANS (every other caller converts); passing the raw
        # degree angle fit against a ~57x-frequency waveform (codex #217).
        cand = _norm([truth_model.pen_y(math.radians(deg_per_s * t + phase),
                                        coeffs, **kw)
                      for t in ts])
        r = _pearson(ys, cand)
        if abs(r) > abs(best[0]):
            best = (r, float(phase), cand if r >= 0 else [-v for v in cand])
    return best


def main() -> int:
    stage = sys.argv[1] if len(sys.argv) > 1 else "full"
    data = _load(stage)
    rpm = float(data["rpm"])
    # The runner persists the amplitude state it solved under; older samples
    # files carried only a top-level "preset" string (config read at report
    # time -- the fallback path in _truth_fit).
    amplitude = data.get("amplitude") or {}
    preset = amplitude.get("preset", data.get("preset", "config"))

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    panels = [("kinematic", "Crank + rockers (deg from start)")]
    if "summing" in data:
        panels.append(("summing", "Spring-summed output chain (deg)"))
    if "pen" in data:
        panels.append(("pen", "Pen trace vs truth curve (normalized)"))

    fig, axes = plt.subplots(len(panels), 1, figsize=(9, 2.9 * len(panels)),
                             sharex=True, constrained_layout=True)
    axes = [axes] if len(panels) == 1 else list(axes)
    md = [f"# Operation motion study -- {stage} stage",
          "",
          f"- crank {rpm:.0f} RPM, {data['duration_s']:.0f} s run, "
          f"{data['channels']} channels, amplitude preset `{preset}`"]

    palette = [C_BLUE, C_ORANGE, C_RED, C_TEAL]
    for ax, (kind, title) in zip(axes, panels):
        ax.set_title(title, color=INK, fontsize=10, loc="left")
        ax.grid(color=GRID, linewidth=0.8)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)
        if kind in ("kinematic", "summing"):
            rows = data[kind]["rows"]
            for i, (label, series) in enumerate(sorted(rows.items())):
                if not series:
                    continue
                ts = [t for t, _v in series]
                vs = [v for _t, v in series]
                ax.plot(ts, vs, color=palette[i % len(palette)], linewidth=2,
                        label=label)
                ax.annotate(label, (ts[-1], vs[-1]), xytext=(4, 0),
                            textcoords="offset points", color=MUTED, fontsize=8,
                            va="center")
            ax.legend(fontsize=8, frameon=False, loc="upper left")
            spans = data[kind]["spans_deg"]
            md += ["", f"## {kind} spans (deg)", ""]
            md += [f"- {k}: {v:.2f}" for k, v in sorted(spans.items())]
            if kind == "kinematic" and data[kind].get("platen_feed_mm") is not None:
                md.append(f"- platen feed: {data[kind]['platen_feed_mm']:.3f} mm")
        else:
            pen = [(t, y) for t, y in data["pen"]["series_t_y"]]
            r, phase, truth = _truth_fit(pen, rpm, preset, truth=amplitude)
            ts = [t for t, _y in pen]
            ax.plot(ts, _norm([y for _t, y in pen]), color=C_BLUE, linewidth=2,
                    label="pen tip (sampled)")
            ax.plot(ts, truth, color=C_ORANGE, linewidth=2, linestyle="--",
                    label=f"truth_model (phase-fit, r={r:.3f})")
            ax.legend(fontsize=8, frameon=False, loc="upper left")
            md += ["", "## pen vs truth", "",
                   f"- pen-tip Y span: {data['pen']['span_mm']:.3f} mm",
                   f"- phase-fit Pearson r: {r:.4f} (phase {phase:.0f} deg)"]
    axes[-1].set_xlabel("time (s)", color=MUTED, fontsize=9)

    png = OUT_MOTION / f"{stage}-report.png"
    fig.savefig(png, dpi=160)
    (OUT_MOTION / f"{stage}-report.md").write_text("\n".join(md) + "\n")
    _telemetry.success(f"report -> {png}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
