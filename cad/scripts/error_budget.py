r"""Coefficient-error budget -- sensitivity model of the crank -> pen chain.

Answers, with numbers, the question the tolerance policy poses: how much does a
deviation of each critical feature move the machine's *output* (a Fourier
coefficient, normalised to the greatest term as Michelson did), and therefore
which dimensional limits are justified by the whole-device benchmark in
``cad/docs/michelson-1898-trial-accuracy.md`` and which are not.

Three layers, all offline (no SolidWorks):

1. **Exact channel kinematics** -- eccentric + connecting rod + rocker (pin on an
   arc) + amplitude bar (foot on the R800 slide, top pin on the channel-lever
   arc) + channel lever, from the same spec constants the build reads. Gives the
   NOMINAL-design residual: gain versus station, harmonic distortion, the null
   station where a channel's fundamental vanishes.
2. **Linear sensitivities** -- d ln(gain)/d(feature) for every gain feature,
   checked against finite differences of layer 1, and the phase features.
3. **Monte Carlo** -- every feature in ``cad/config/error_budget.yaml`` drawn
   uniformly within its tolerance, per channel, through the calibrated readout
   (mean-line zero, k=0 scale) on the reference inputs; reported as mean
   absolute / RMS / worst coefficient error in % of the greatest term, per
   feature and combined, against the file's targets.

Plus the closed-form terms that are not part tolerances (knife hysteresis,
readout resolution, timebase) so the whole budget is on one page.

CLI::

    uv run python cad/scripts/error_budget.py            # the report
    uv run python cad/scripts/error_budget.py --json     # machine-readable
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable

import numpy as np
import yaml

import _config
import amplitude_bar_spec
import channel_lever_spec
import channel_spring_installed_spec
import connecting_rod_spec
import counter_spring_spec
import cylinder_gear_spec
import rocker_arm_spec
import summing_lever_spec
from channel_frame_geom import LEVER_FULCRUM_XY, ROCKER_PIVOT_XY

BUDGET_YAML = _config.CONFIG_DIR / "error_budget.yaml"

CRANK_TURNS_PER_PERIOD = 80  # gear k turns k/80 rev per crank turn (ch. 29 gear law)

N_ELEMENTS = 20
K_MAX = 20  # coefficients k = 0..20 read at theta_k = k*pi/20


@dataclass(frozen=True)
class Nominal:
    """Every geometric input of the channel transfer, mm unless noted."""

    ecc: float  # cam throw
    rod: float  # connecting-rod centre distance
    pin_x: float  # rod-pin hole along the arm from the pivot bore
    pin_y: float  # rod-pin hole above the pivot-bore centreline
    arc_r: float  # rocker slide radius
    arc_cy: float  # slide-arc centre above the pivot-bore centreline
    fulcrum_dx: float  # lever fulcrum, rocker frame
    fulcrum_dy: float
    bar_pin_arm: float  # lever: fulcrum -> amplitude-bar pin
    hook_arm: float  # lever: fulcrum -> spring hook
    bar_len: float  # amplitude bar: foot axis -> top pin (rigid)
    contact_dx: float  # foot axis -> notch-roof contact, bar frame (untilted)
    contact_dy: float
    spring_rate: float  # channel spring, N/mm
    counter_rate: float  # counter spring, N/mm
    sum_arm: float  # summing lever: knife -> spring hook row
    counter_arm: float  # summing lever: knife -> counter-spring anchor
    d_max: float  # amplitude-bar full-scale station


def nominal() -> Nominal:
    """The as-designed inputs, read from the spec modules the CAD builds from."""
    return Nominal(
        ecc=cylinder_gear_spec.ECCENTRICITY,
        rod=connecting_rod_spec.CENTER_DISTANCE,
        pin_x=rocker_arm_spec.ROD_HOLE_X,
        pin_y=rocker_arm_spec.ROD_HOLE_Y - rocker_arm_spec.PIVOT_MID_Y,
        arc_r=rocker_arm_spec.CURVE_RADIUS,
        arc_cy=rocker_arm_spec.CENTER_Y - rocker_arm_spec.PIVOT_MID_Y,
        fulcrum_dx=LEVER_FULCRUM_XY[0] - ROCKER_PIVOT_XY[0],
        fulcrum_dy=LEVER_FULCRUM_XY[1] - ROCKER_PIVOT_XY[1],
        bar_pin_arm=channel_lever_spec.BAR_PIN_X,
        hook_arm=channel_lever_spec.LEVER_SPRING_X,
        bar_len=amplitude_bar_spec.TOP_PIN_Y,
        contact_dx=amplitude_bar_spec.BAR_WIDTH / 2.0,
        contact_dy=amplitude_bar_spec.BOTTOM_NOTCH_HEIGHT
        - float(_config.fit("cam_follower_contact", "contact_gap_mm")),
        spring_rate=channel_spring_installed_spec.SPRING_RATE_REF,
        counter_rate=counter_spring_spec.SPRING_RATE_REF,
        sum_arm=summing_lever_spec.HOLE_X,
        counter_arm=summing_lever_spec.SUM_H,
        d_max=float(_config.machine("amplitude", "max_travel_mm")),
    )


# --------------------------------------------------------------------------
# Layer 1 -- exact channel kinematics (vectorised over the crank angle)
# --------------------------------------------------------------------------


def _bisect(
    f: Callable[[np.ndarray], np.ndarray], lo: float, hi: float, n: int, iters: int = 50
) -> np.ndarray:
    """Vectorised bisection of ``f`` on [lo, hi] for ``n`` independent roots."""
    lo_a = np.full(n, lo)
    hi_a = np.full(n, hi)
    f_lo = f(lo_a)
    for _ in range(iters):
        mid = 0.5 * (lo_a + hi_a)
        f_mid = f(mid)
        same = (f_mid < 0) == (f_lo < 0)
        lo_a = np.where(same, mid, lo_a)
        f_lo = np.where(same, f_mid, f_lo)
        hi_a = np.where(same, hi_a, mid)
    return 0.5 * (lo_a + hi_a)


def rocker_angle(theta: np.ndarray, nom: Nominal) -> np.ndarray:
    """Rocker rotation (rad, level = 0 at the top of stroke) versus cam angle.

    Rod hangs plumb below the pin at rest with the lobe up, so the gear axis sits
    ``rod + ecc`` below the pin; the pin rides its arc about the pivot.
    """
    p0 = np.array([nom.pin_x, nom.pin_y])
    axis = p0 - np.array([0.0, nom.rod + nom.ecc])
    cx = axis[0] - nom.ecc * np.sin(theta)
    cy = axis[1] + nom.ecc * np.cos(theta)

    def gap(tr: np.ndarray) -> np.ndarray:
        px = p0[0] * np.cos(tr) - p0[1] * np.sin(tr)
        py = p0[0] * np.sin(tr) + p0[1] * np.cos(tr)
        return np.hypot(px - cx, py - cy) - nom.rod

    return _bisect(gap, -0.4, 0.4, theta.size)


def _lever_pin_gap(
    kx: np.ndarray, ky: np.ndarray, beta: np.ndarray, nom: Nominal
) -> np.ndarray:
    """Distance error of the bar's top pin from the lever's bar-pin circle for a
    notch-roof contact at (kx, ky) and bar tilt ``beta`` (build_channel_assembly
    .solve_state's residual, with the contact point as the anchor): the foot axis
    is the contact minus the rotated notch offset, the top pin ``bar_len`` up the
    tilted bar."""
    s, c = np.sin(beta), np.cos(beta)
    fx = kx - (nom.contact_dx * c - nom.contact_dy * s)
    fy = ky - (nom.contact_dx * s + nom.contact_dy * c)
    tx = fx + nom.bar_len * s
    ty = fy + nom.bar_len * c
    return np.hypot(tx - nom.fulcrum_dx, ty - nom.fulcrum_dy) - nom.bar_pin_arm


def rest_contact(d: float, nom: Nominal) -> tuple[float, float]:
    """Where the bar's notch roof sits on the R800 arc at station ``d`` (foot-axis
    x from the pivot), arm level -- solve_state's rest pose: the contact rides
    the arc and the top pin the lever circle, the bar tilt closes the loop."""

    def contact(beta: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        kx = d + nom.contact_dx * np.cos(beta) - nom.contact_dy * np.sin(beta)
        ky = nom.arc_cy - np.sqrt(nom.arc_r**2 - kx**2)
        return kx, ky

    def gap(beta: np.ndarray) -> np.ndarray:
        kx, ky = contact(beta)
        return _lever_pin_gap(kx, ky, beta, nom)

    beta = _bisect(gap, -0.4, 0.4, 1)
    kx, ky = contact(beta)
    return float(kx[0]), float(ky[0])


def hook_displacement(theta: np.ndarray, d: float, nom: Nominal) -> np.ndarray:
    """Vertical displacement (mm) of the channel-spring hook on the lever for an
    amplitude bar at station ``d`` (signed foot-axis x from the pivot).

    The notch-roof contact point is fixed on the arm (the radial bar puts the
    spring load normal to the arc, so the foot does not slide) and rides the
    rocker's rotation; the rigid bar re-tilts so its top pin stays on the lever
    circle, and the hook follows the lever."""
    tr = rocker_angle(theta, nom)
    k0x, k0y = rest_contact(d, nom)
    kx = k0x * np.cos(tr) - k0y * np.sin(tr)
    ky = k0x * np.sin(tr) + k0y * np.cos(tr)
    beta = _bisect(lambda b: _lever_pin_gap(kx, ky, b, nom), -0.4, 0.4, theta.size)
    s, c = np.sin(beta), np.cos(beta)
    tx = kx - (nom.contact_dx * c - nom.contact_dy * s) + nom.bar_len * s
    ty = ky - (nom.contact_dx * s + nom.contact_dy * c) + nom.bar_len * c
    phi = np.arctan2(ty - nom.fulcrum_dy, nom.fulcrum_dx - tx)  # lever tilt
    return nom.hook_arm * np.sin(phi)


def linear_gain(nom: Nominal) -> float:
    """Ideal hook displacement per mm of station per unit cosine: the
    small-angle transfer (hook/bar-pin) * ecc / pin radius."""
    return (nom.hook_arm / nom.bar_pin_arm) * nom.ecc / math.hypot(nom.pin_x, nom.pin_y)


def harmonic_content(
    d: float, nom: Nominal, samples: int = 720, null: float = 0.0
) -> dict[str, float]:
    """DC, fundamental and 2nd/3rd harmonic of one channel's hook motion at
    station ``d``, in mm, plus the gain relative to the ideal linear transfer
    measured from the null station (``null``, where the fundamental vanishes)."""
    th = np.arange(samples) * 2.0 * math.pi / samples
    u = hook_displacement(th, d, nom)
    out: dict[str, float] = {"dc": float(u.mean())}
    for m in (1, 2, 3):
        a = 2.0 * float(np.mean(u * np.cos(m * th)))
        b = 2.0 * float(np.mean(u * np.sin(m * th)))
        out[f"c{m}"] = math.hypot(a, b)
        out[f"c{m}_cos"] = a
    ideal = linear_gain(nom) * (d - null)
    out["gain_vs_linear"] = out["c1_cos"] / ideal if ideal else float("nan")
    return out


def null_station(nom: Nominal) -> float:
    """Station (mm) at which a channel's fundamental vanishes -- where the
    measuring stick's zero belongs. Nonzero because the slide arc sits above the
    pivot centreline and the swing is one-sided."""
    th = np.arange(360) * 2.0 * math.pi / 360

    def c1(d: float) -> float:
        return 2.0 * float(np.mean(hook_displacement(th, d, nom) * np.cos(th)))

    lo, hi = -5.0, 5.0
    f_lo = c1(lo)
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        f_mid = c1(mid)
        if (f_mid < 0) == (f_lo < 0):
            lo, f_lo = mid, f_mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# --------------------------------------------------------------------------
# Readout -- the coefficient a human reads off the trace
# --------------------------------------------------------------------------

THETA_K = np.arange(K_MAX + 1) * math.pi / N_ELEMENTS
HARMONICS = np.arange(1, N_ELEMENTS + 1)


def reference_inputs() -> dict[str, np.ndarray]:
    """Ordinates x_i (i = 1..20), |x| <= 1. Station d_i = x_i * d_max."""
    i = HARMONICS.astype(float)
    return {
        "all_ones": np.ones(N_ELEMENTS),  # constant: only k=0 survives
        "rect_half": (i <= 10).astype(float),  # step at the half range
        "gaussian_a0p1": np.exp(-((0.1 * i) ** 2)),  # Michelson trial 2, x in elements
        "alternating": np.where(i % 2 == 0, 1.0, -1.0),  # exercises negative stations
        "pair_1_20": np.where(
            (i == 1) | (i == 20), 1.0, 0.0
        ),  # sparse: two channels, no averaging
    }


def ideal_coefficients(x: np.ndarray) -> np.ndarray:
    """A_k = sum_i x_i cos(i theta_k), the 20-element rule the machine realises."""
    return np.cos(np.outer(THETA_K, HARMONICS)) @ x


PERIOD = np.arange(720) * 2.0 * math.pi / 720


def trace_scale(trace_all_ones: Callable[[np.ndarray], np.ndarray]) -> float:
    """The CALIBRATION run of tolerance-policy.md: every bar at full scale, the
    k=0 reading above the mean line is K * N * d_max. Returns K (trace units per
    unit ordinate) -- common-mode gain, measured once, applied to every trial."""
    y0 = float(trace_all_ones(THETA_K[:1])[0])
    return (y0 - float(np.mean(trace_all_ones(PERIOD)))) / N_ELEMENTS


def read_coefficients(
    trace: Callable[[np.ndarray], np.ndarray], scale: float
) -> np.ndarray:
    """The readout PROCEDURE of tolerance-policy.md applied to a trace y(theta):
    zero = the mean line of the trial's own full period; scale = the calibration
    run's K. Returns A_k in ordinate units."""
    zero = float(np.mean(trace(PERIOD)))
    return (trace(THETA_K) - zero) / scale


def coefficient_errors_pct(measured: np.ndarray, x: np.ndarray) -> np.ndarray:
    """e_k in % of the greatest ideal term (Michelson's normalisation)."""
    ideal = ideal_coefficients(x)
    return 100.0 * (measured - ideal) / np.max(np.abs(ideal))


def second_harmonic(u: np.ndarray, grid: np.ndarray) -> float:
    """c2 (cosine component, trace units) of one channel's one-cycle motion --
    the slider-crank distortion the readout correction subtracts."""
    return 2.0 * float(np.mean(u * np.cos(2.0 * grid)))


def nominal_design_errors(
    nom: Nominal, stick_zero: float = 0.0, correct_second_harmonic: bool = False
) -> dict[str, dict[str, float]]:
    """Coefficient errors of the NOMINAL machine (no tolerances) through the
    exact kinematics, per reference input. ``stick_zero`` offsets every station
    (the measuring-stick zero relative to the pivot). Every channel is summed,
    including those at station 0: the slide arc sits above the pivot, so a
    zero-station bar still moves a little (that is what the null station is).
    ``correct_second_harmonic`` applies the readout correction of
    tolerance-policy.md: the operator subtracts sum_i x_i kappa_i cos(2 i theta_k)
    using the per-station kappa of the calibration table."""
    grid = np.arange(1440) * 2.0 * math.pi / 1440
    cycle: dict[float, np.ndarray] = {}

    def one_cycle(d: float) -> np.ndarray:
        if d not in cycle:
            cycle[d] = hook_displacement(grid, d, nom)
        return cycle[d]

    def trace_for(stations: np.ndarray) -> Callable[[np.ndarray], np.ndarray]:
        def trace(th: np.ndarray) -> np.ndarray:
            y = np.zeros_like(th)
            for j, d in zip(HARMONICS, stations):
                # channel j runs j cycles per fundamental period
                y += np.interp(
                    (j * th) % (2 * math.pi),
                    grid,
                    one_cycle(float(d)),
                    period=2 * math.pi,
                )
            return y

        return trace

    def c2(stations: np.ndarray) -> np.ndarray:
        if not correct_second_harmonic:
            return np.zeros_like(stations)
        return np.array([second_harmonic(one_cycle(float(d)), grid) for d in stations])

    inputs = reference_inputs()
    cal_stations = inputs["all_ones"] * nom.d_max + stick_zero
    # the calibration reading at theta=0 carries every channel's c2 too
    scale = trace_scale(trace_for(cal_stations)) - float(np.mean(c2(cal_stations)))
    cos_2k = np.cos(2.0 * np.outer(THETA_K, HARMONICS))
    out: dict[str, dict[str, float]] = {}
    for name, x in inputs.items():
        stations = x * nom.d_max + stick_zero
        measured = read_coefficients(trace_for(stations), scale)
        measured -= (cos_2k @ c2(stations)) / scale
        e = coefficient_errors_pct(measured, x)
        out[name] = {"mae": float(np.mean(np.abs(e))), "max": float(np.max(np.abs(e)))}
    return out


# --------------------------------------------------------------------------
# Layer 2 -- linear sensitivities
# --------------------------------------------------------------------------


def gain_sensitivities(nom: Nominal) -> dict[str, float]:
    """% of channel gain per unit of each gain feature (mm, or % for the spring),
    BEFORE calibration. For the force balance w_i = s_i a_i / (sum_j s_j a_j^2 +
    S b^2) a channel's own spring or arm also stiffens the common denominator,
    but that factor is shared by every channel and the calibration-run scale in
    ``_channel_model`` divides it out -- so only the numerator's sensitivity
    belongs here (folding the denominator in as well would cancel it twice;
    codex #742)."""
    r_pin = math.hypot(nom.pin_x, nom.pin_y)
    return {
        "cam_eccentricity": 100.0 / nom.ecc,
        "rocker_rod_pin_radius": -100.0 * nom.pin_x / r_pin**2,
        "lever_bar_pin_arm": -100.0 / nom.bar_pin_arm,
        "lever_spring_hook_arm": 100.0 / nom.hook_arm,
        "summing_hook_arm": 100.0 / nom.sum_arm,
        "spring_rate": 1.0,  # % per %
    }


def finite_difference_check(
    nom: Nominal, d: float | None = None
) -> dict[str, tuple[float, float]]:
    """Analytic gain sensitivity vs central finite differences of the exact
    fundamental amplitude at station ``d``: (analytic, numeric) % per mm."""
    d = nom.d_max if d is None else d
    th = np.arange(360) * 2.0 * math.pi / 360

    def c1(n: Nominal) -> float:
        return 2.0 * float(np.mean(hook_displacement(th, d, n) * np.cos(th)))

    base = c1(nom)
    fields = {
        "cam_eccentricity": "ecc",
        "rocker_rod_pin_radius": "pin_x",
        "lever_bar_pin_arm": "bar_pin_arm",
        "lever_spring_hook_arm": "hook_arm",
    }
    analytic = gain_sensitivities(nom)
    out = {}
    for key, field in fields.items():
        h = 0.05
        hi = c1(replace(nom, **{field: getattr(nom, field) + h}))
        lo = c1(replace(nom, **{field: getattr(nom, field) - h}))
        out[key] = (analytic[key], 100.0 * (hi - lo) / (2.0 * h) / base)
    return out


# --------------------------------------------------------------------------
# Layer 3 -- Monte Carlo of the budget's tolerances
# --------------------------------------------------------------------------


def load_budget(path: Path = BUDGET_YAML) -> dict[str, Any]:
    """The allocation config (cad/config/error_budget.yaml)."""
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _channel_model(
    x: np.ndarray,
    nom: Nominal,
    dev: dict[str, np.ndarray],
    sens: dict[str, float],
    cal_station: np.ndarray,
) -> np.ndarray:
    """A_k read from a linear-gain machine whose channel i has gain g_i and
    phase phi_i built from the drawn deviations ``dev[feature]`` (draws x 20),
    scaled by the same machine's calibration run (all bars at full scale, its
    own station-setting errors ``cal_station``). Pure cosines have a zero mean
    line, so only the scale step of the readout is modelled here.
    Returns e_k in % FS, shape (draws, K_MAX+1)."""
    draws = next(iter(dev.values())).shape[0]
    log_g = np.zeros((draws, N_ELEMENTS))
    phi = np.zeros((draws, N_ELEMENTS))
    d = np.broadcast_to(x * nom.d_max, (draws, N_ELEMENTS)).copy()
    d_cal = np.full((draws, N_ELEMENTS), nom.d_max)
    for key, v in dev.items():
        if key in sens:
            log_g += np.log1p(sens[key] / 100.0 * v)
        elif key in ("cam_phase", "mesh_lag_spread"):
            phi += np.radians(v)
        elif key == "station_setting":
            d += v
            d_cal += cal_station
        else:
            raise KeyError(f"no model for feature {key}")
    g = np.exp(log_g)
    scale = (g * d_cal * np.cos(phi)).sum(axis=1) / (
        N_ELEMENTS * nom.d_max
    )  # k=0 of the calibration run
    cos_k = np.cos(
        THETA_K[None, :, None] * HARMONICS[None, None, :] + phi[:, None, :]
    )  # draws,k,i
    measured = np.einsum("di,dki->dk", g * d, cos_k) / (scale[:, None] * nom.d_max)
    ideal = ideal_coefficients(x)
    return 100.0 * (measured - ideal[None, :]) / np.max(np.abs(ideal))


def monte_carlo(budget: dict[str, Any], nom: Nominal) -> dict[str, Any]:
    """Per-feature and combined coefficient-error statistics (% FS) with every
    critical feature drawn uniformly within its tolerance, per channel, on the
    budget's reference inputs through the calibrated readout."""
    mc = budget["monte_carlo"]
    rng = np.random.default_rng(int(mc["seed"]))
    draws = int(mc["draws"])
    if mc["distribution"] != "uniform":
        raise ValueError(
            f"unsupported Monte Carlo distribution: {mc['distribution']!r}"
        )
    feats = budget["critical_features"]
    sens = gain_sensitivities(nom)
    inputs = reference_inputs()
    names = list(budget["reference_inputs"])
    unknown = set(names) - set(inputs)
    if unknown:
        raise KeyError(
            f"reference_inputs not defined in error_budget.py: {sorted(unknown)}"
        )

    all_dev = {
        key: rng.uniform(-f["tolerance"], f["tolerance"], size=(draws, N_ELEMENTS))
        for key, f in feats.items()
    }
    cal_station = rng.uniform(
        -feats["station_setting"]["tolerance"],
        feats["station_setting"]["tolerance"],
        size=(draws, N_ELEMENTS),
    )

    def stats(dev: dict[str, np.ndarray]) -> dict[str, Any]:
        per_input = {}
        pooled = []
        for name in names:
            e = _channel_model(inputs[name], nom, dev, sens, cal_station)
            per_input[name] = {
                "mae": float(np.mean(np.abs(e))),
                "rms": float(np.sqrt(np.mean(e * e))),
                "p99_max": float(np.percentile(np.max(np.abs(e), axis=1), 99)),
            }
            if name != "pair_1_20":
                pooled.append(e)
        e_all = np.concatenate(pooled, axis=1)
        return {
            "per_input": per_input,
            "mae": float(np.mean(np.abs(e_all))),
            "rms": float(np.sqrt(np.mean(e_all * e_all))),
            "p99_max": float(np.percentile(np.max(np.abs(e_all), axis=1), 99)),
        }

    per_feature = {key: stats({key: all_dev[key]}) for key in feats}
    # Errors scale linearly with a feature's tolerance (uniform draws, small
    # deviations), so the tolerance at which a feature ALONE would consume its
    # allocation share follows by proportion -- the number a drawing may relax to.
    share = budget["allocation_share"]
    for key, s in per_feature.items():
        pair = s["per_input"]["pair_1_20"]["p99_max"]
        factor = min(share["mae_fs_pct"] / s["mae"], share["pair_p99_pct"] / pair)
        s["allowable_tolerance"] = feats[key]["tolerance"] * factor
    combined = stats(all_dev)
    return {"per_feature": per_feature, "combined": combined}


# --------------------------------------------------------------------------
# Closed-form terms that are not part tolerances
# --------------------------------------------------------------------------


def closed_form_terms(nom: Nominal, budget: dict[str, Any]) -> dict[str, Any]:
    """Error terms that are procedure or design-adjustment items, not part
    tolerances: knife hysteresis, strap lost motion, ordinate readout, timebase.
    Each is evaluated at the ``reserved`` assumptions of error_budget.yaml as a
    ``pct_fs`` (% of the greatest term on the all-ones input, whose k=0 reading is
    the machine's full-scale output) so ``budget_closes`` can bound it."""
    res = budget["reserved"]
    u_fs = (
        linear_gain(nom) * nom.d_max
    )  # hook displacement of one channel at full station
    # Knife-edge hysteresis: the lever stalls while the moment error is below
    # T_f = N * f_r (N = total spring load on the edge, f_r = rolling-resistance
    # length of the edge). With D = sum s a^2 + S b^2 the equivalent hook-position
    # error is a*T_f/D and ONE channel's full-scale hook motion s*a^2*u_fs/D, so
    # the ratio T_f/(s*a*u_fs) needs no D. Against the all-ones full scale (every
    # channel at u_fs) the stall is that ratio / N.
    preload = nom.spring_rate * (
        channel_spring_installed_spec.INSTALLED_BODY_LENGTH
        - channel_spring_installed_spec.FREE_BODY_LENGTH
    )
    knife_load = N_ELEMENTS * preload
    f_r = float(res["knife"]["rolling_resistance_mm"])
    stall_one = 100.0 * knife_load * f_r / (nom.spring_rate * nom.sum_arm * u_fs)
    knife = {
        "assumed_preload_N_per_spring": preload,
        "assumed_knife_load_N": knife_load,
        "assumed_rolling_resistance_mm": f_r,
        "stall_pct_of_one_channel_fs": stall_one,
        "pct_fs": stall_one / N_ELEMENTS,
        "note": "spring rate/preload are DERIVED from wire geometry (low confidence); measure trace width on a slow reversal",
    }
    # Lost motion on load reversal: the strap's diametral clearance shifts the
    # rod by c when the ordinate changes sign -- DC for a fixed-sign station.
    strap_c = connecting_rod_spec.RING_BORE_DIA - cylinder_gear_spec.CAM_DIA
    lost_motion = {
        "strap_clearance_mm": strap_c,
        "dc_step_pct_of_channel_amplitude": 100.0 * strap_c / nom.ecc,
        "note": "constant within a run (mean-line zero removes it) as long as a station keeps its sign",
    }
    # Ordinate readout at the SETUP stroke the budget requires (the magnifier
    # clamp is adjustable; output.yaml's pen_trace_half_mm is the render pose).
    pen_half = float(res["readout"]["pen_half_stroke_mm"])
    reading = float(res["readout"]["reading_uncertainty_mm"])
    readout = {
        "required_pen_half_stroke_mm": pen_half,
        "render_pen_half_stroke_mm": float(
            _config.machine("output", "pen_trace_half_mm")
        ),
        "assumed_reading_uncertainty_mm": reading,
        "ordinate_pct_fs_per_0p1mm_reading": 100.0 * 0.1 / pen_half,
        "pct_fs": 100.0 * reading / pen_half,
        "note": "reading uncertainty = half the line width + interpolation; scales as 1/(pen full scale)",
    }
    # Timebase: reading at the wrong theta. d(A_k)/d(theta) = -sum i x_i sin(i theta_k),
    # RMS over k, in % FS per rad of FUNDAMENTAL angle. One fundamental period is
    # CRANK_TURNS_PER_PERIOD crank turns (gear k turns k/80 per crank turn); the
    # budgeted procedure stops the crank on its index within +/-index_deg
    # (uniform, so RMS = slope * half-width / sqrt 3); the abscissa-reading
    # alternative at the configured platen feed is reported for comparison.
    slope = {}
    for name, x in reference_inputs().items():
        s = -np.sin(np.outer(THETA_K, HARMONICS)) @ (x * HARMONICS)
        fs = np.max(np.abs(ideal_coefficients(x)))
        slope[name] = float(np.sqrt(np.mean(s * s)) / fs * 100.0)
    feed = float(budget["readout"]["platen_feed_mm_per_crank_turn"])
    coarse = float(budget["readout"]["coarse_gear_set_feed_ratio"])
    index_deg = float(res["timebase"]["crank_index_deg"])
    rad_per_crank_turn = 2.0 * math.pi / CRANK_TURNS_PER_PERIOD
    rad_per_0p1mm = 0.1 / feed * rad_per_crank_turn
    rad_index = index_deg / 360.0 * rad_per_crank_turn
    timebase = {
        "pct_fs_per_rad_rms": slope,
        "platen_feed_mm_per_crank_turn": feed,
        "pct_fs_all_ones_per_0p1mm_abscissa": slope["all_ones"] * rad_per_0p1mm,
        "pct_fs_all_ones_per_0p1mm_abscissa_coarse_gears": slope["all_ones"]
        * rad_per_0p1mm
        / coarse,
        "assumed_crank_index_deg": index_deg,
        "pct_fs": slope["all_ones"] * rad_index / math.sqrt(3.0),
    }
    return {
        "knife": knife,
        "lost_motion": lost_motion,
        "readout": readout,
        "timebase": timebase,
    }


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------


def build_report(budget: dict[str, Any] | None = None) -> dict[str, Any]:
    """Every layer of the budget as one JSON-able dict (what the CLI prints and
    test_error_budget.py asserts on)."""
    budget = load_budget() if budget is None else budget
    nom = nominal()
    d0 = null_station(nom)
    stations = [nom.d_max, nom.d_max / 2, 10.0, -nom.d_max / 2, -nom.d_max]
    r = {
        "nominal": nom.__dict__,
        "linear_gain_mm_per_mm": linear_gain(nom),
        "null_station_mm": d0,
        "harmonics": {f"{d:+.0f}": harmonic_content(d, nom, null=d0) for d in stations},
        "nominal_design_errors": {
            "stick_zero_at_pivot": nominal_design_errors(nom),
            "stick_zero_at_null_station": nominal_design_errors(nom, stick_zero=d0),
            "null_station_and_c2_corrected": nominal_design_errors(
                nom, stick_zero=d0, correct_second_harmonic=True
            ),
        },
        "gain_sensitivities": gain_sensitivities(nom),
        "finite_difference_check": finite_difference_check(nom),
        "monte_carlo": monte_carlo(budget, nom),
        "closed_form": closed_form_terms(nom, budget),
        "targets": budget["targets"],
        "benchmark": budget["benchmark"],
        "reserved_allowance": {
            k: float(v["allowance_pct"]) for k, v in budget["reserved"].items()
        },
    }
    r["closure"] = closure(r, budget)
    return r


def _print_report(r: dict[str, Any], budget: dict[str, Any]) -> None:
    """Human-readable rendering of ``build_report``."""
    p = print
    n = r["nominal"]
    p("# Coefficient-error budget (error_budget.py)")
    p(
        f"nominal: ecc {n['ecc']:.3f}  rod {n['rod']:.2f}  pin ({n['pin_x']:.3f}, {n['pin_y']:.3f})  "
        f"bar-pin/hook {n['bar_pin_arm']:.1f}/{n['hook_arm']:.1f}  sum arm a {n['sum_arm']:.2f}  "
        f"spring {n['spring_rate']:.3f} N/mm  d_max {n['d_max']:.0f}"
    )
    p(
        f"linear gain: {r['linear_gain_mm_per_mm']:.5f} mm hook per mm station;  NULL station: {r['null_station_mm']:+.3f} mm"
    )
    p("\n## 1. Nominal design (no tolerances) -- harmonic content of one channel")
    p(f"{'station':>8} {'gain/linear':>12} {'DC/c1':>8} {'c2/c1':>8} {'c3/c1':>8}")
    for d, h in r["harmonics"].items():
        p(
            f"{d:>8} {h['gain_vs_linear']:>12.4f} {h['dc'] / h['c1'] * 100:>+7.2f}% {h['c2'] / h['c1'] * 100:>7.3f}% {h['c3'] / h['c1'] * 100:>7.3f}%"
        )
    p(
        "\ncoefficient error of the NOMINAL machine through the calibrated readout, % of greatest term:"
    )
    p(
        f"{'input':>16} {'stick@pivot':>14} {'max':>7} {'stick@null':>12} {'max':>7} {'+c2 corrected':>14} {'max':>7}"
    )
    nde = r["nominal_design_errors"]
    a, b, c3 = (
        nde["stick_zero_at_pivot"],
        nde["stick_zero_at_null_station"],
        nde["null_station_and_c2_corrected"],
    )
    for name in a:
        p(
            f"{name:>16} {a[name]['mae']:>14.3f} {a[name]['max']:>7.3f} {b[name]['mae']:>12.3f} {b[name]['max']:>7.3f} "
            f"{c3[name]['mae']:>14.3f} {c3[name]['max']:>7.3f}"
        )
    p(
        "\n## 2. Gain sensitivities (% of channel gain per mm; spring: % per %)  [analytic | finite-difference]"
    )
    fd = r["finite_difference_check"]
    for key, s in r["gain_sensitivities"].items():
        chk = f"  | {fd[key][1]:+.3f}" if key in fd else ""
        p(f"  {key:<24} {s:+.3f}{chk}")
    p(
        "\n## 3. Monte Carlo -- error_budget.yaml tolerances, calibrated readout, % of greatest term"
    )
    feats = budget["critical_features"]
    share = budget["allocation_share"]
    p(
        f"{'feature':<24} {'+/- tol':>9} {'MAE':>7} {'RMS':>7} {'p99 max':>8} {'pair p99':>9} {'allowable':>10}"
        f"   (broad inputs pooled; allowable = alone at {share['mae_fs_pct']} MAE / {share['pair_p99_pct']} pair p99)"
    )
    mc = r["monte_carlo"]
    for key, s in mc["per_feature"].items():
        unit = feats[key].get("unit", "mm")
        p(
            f"{key:<24} {feats[key]['tolerance']:>6.3f} {unit:<3}{s['mae']:>7.3f} {s['rms']:>7.3f} {s['p99_max']:>8.3f} "
            f"{s['per_input']['pair_1_20']['p99_max']:>9.3f} {s['allowable_tolerance']:>10.3f}"
        )
    c = mc["combined"]
    p(
        f"{'ALL COMBINED':<24} {'':>9} {c['mae']:>7.3f} {c['rms']:>7.3f} {c['p99_max']:>8.3f}"
    )
    p("per input (combined):")
    for name, s in c["per_input"].items():
        p(
            f"  {name:<16} MAE {s['mae']:.3f}  RMS {s['rms']:.3f}  p99 max {s['p99_max']:.3f}"
        )
    t = r["targets"]
    p(
        f"targets: scatter MAE <= {t['scatter_mae_fs_pct']}  p99 max <= {t['scatter_p99_max_fs_pct']}  "
        f"pair p99 <= {t['pair_consistency_p99_pct']}   (benchmark MAE {r['benchmark']['mae_fs_pct']}, max {r['benchmark']['max_fs_pct']})"
    )
    p("\n## 4. Terms that are not part tolerances")
    p(json.dumps(r["closed_form"], indent=2))
    p("\n## 5. Closure -- every term against the benchmark MAE")
    for k, v in r["closure"].items():
        p(f"  {k:<28} {v:.3f}")


def closure(r: dict[str, Any], budget: dict[str, Any]) -> dict[str, float]:
    """Every reserved term (% FS) beside the scatter, and their total: the
    corrected nominal residual is systematic and adds; scatter, readout,
    timebase and knife are independent and combine root-sum-square."""
    cf = r["closed_form"]
    nde = r["nominal_design_errors"]["null_station_and_c2_corrected"]
    broad = [n for n in budget["reference_inputs"] if n != "pair_1_20"]
    terms = {
        "nominal_residual_mae": max(nde[n]["mae"] for n in broad),
        "scatter_mae": r["monte_carlo"]["combined"]["mae"],
        "readout": cf["readout"]["pct_fs"],
        "timebase": cf["timebase"]["pct_fs"],
        "knife": cf["knife"]["pct_fs"],
    }
    rss = math.sqrt(
        sum(terms[k] ** 2 for k in ("scatter_mae", "readout", "timebase", "knife"))
    )
    terms["total_mae"] = terms["nominal_residual_mae"] + rss
    return terms


def budget_closes(r: dict[str, Any]) -> list[str]:
    """Which limits the report violates (empty = budget closes): the Monte
    Carlo scatter targets, each reserved term's allowance, and the total
    against the benchmark MAE."""
    t, c = r["targets"], r["monte_carlo"]["combined"]
    bad = []
    if c["mae"] > t["scatter_mae_fs_pct"]:
        bad.append(f"scatter MAE {c['mae']:.3f} > {t['scatter_mae_fs_pct']}")
    if c["p99_max"] > t["scatter_p99_max_fs_pct"]:
        bad.append(
            f"scatter p99 max {c['p99_max']:.3f} > {t['scatter_p99_max_fs_pct']}"
        )
    pair = c["per_input"]["pair_1_20"]["p99_max"]
    if pair > t["pair_consistency_p99_pct"]:
        bad.append(f"pair p99 max {pair:.3f} > {t['pair_consistency_p99_pct']}")
    cl, allow = r["closure"], r["reserved_allowance"]
    for k in ("nominal_residual_mae", "readout", "timebase", "knife"):
        if cl[k] > allow[k]:
            bad.append(f"{k} {cl[k]:.3f} > allowance {allow[k]}")
    if cl["total_mae"] > r["benchmark"]["mae_fs_pct"]:
        bad.append(
            f"total MAE {cl['total_mae']:.3f} > benchmark {r['benchmark']['mae_fs_pct']}"
        )
    return bad


def _main() -> int:
    """CLI: print the report (or ``--json``); exit 1 if the budget does not close."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="emit the report as JSON")
    args = ap.parse_args()
    budget = load_budget()
    r = build_report(budget)
    if args.json:
        print(json.dumps(r, indent=2, default=float))
    else:
        _print_report(r, budget)
        bad = budget_closes(r)
        print("\nBUDGET:", "closes" if not bad else "; ".join(bad))
    return 0 if not budget_closes(r) else 1


if __name__ == "__main__":
    sys.exit(_main())
