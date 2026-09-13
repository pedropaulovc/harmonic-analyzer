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
from dataclasses import asdict, astuple, dataclass, replace
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
import lever_wire_geom
import magnifying_clamp_geom
import magnifying_lever_geom
import measuring_stick_spec
import paper_drive_geom
import pen_wire_geom
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
    # -- output chain: summing lever -> magnifying lever -> wheel -> pen --
    lever_r_min: float  # knife -> clamp centre, clamp against the bracket collar
    lever_r_built: float  # the as-built (CLAMP_LOCAL_X) radius
    lever_r_max: float  # clamp flush with the rod tip (mechanical bound)
    wheel_ratio: float  # rim wire radius / hub wire radius
    pen_half: float  # the pen's physical half-stroke


def nominal() -> Nominal:
    """The as-designed inputs, read from the spec modules the CAD builds from."""
    lever_band = magnifying_lever_geom.clamp_radius_band(
        magnifying_clamp_geom.BLOCK_DEPTH
    )
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
        lever_r_min=lever_band[0],
        lever_r_built=lever_band[1],
        lever_r_max=lever_band[2],
        wheel_ratio=(
            pen_wire_geom.RIM_DIA / 2.0
            + pen_wire_geom.WIRE_DIA / 2.0
            + pen_wire_geom.CLEARANCE
        )
        / (
            lever_wire_geom.HUB_DIA / 2.0
            + lever_wire_geom.WIRE_DIA / 2.0
            + lever_wire_geom.CLEARANCE
        ),
        pen_half=float(_config.machine("output", "pen_trace_half_mm")),
    )


def pen_gain(nom: Nominal, lever_r: float) -> float:
    """Pen travel (mm) per mm of SUMMED hook displacement at magnifying-lever
    radius ``lever_r``: the 20 equal-rate springs on one hook row at arm ``a``
    against the counter spring at ``b`` put the summing lever at
    theta = k a sum(h) / (N k a^2 + K_c b^2) -- the hook row moves by the mean
    hook displacement times the spring coupling -- the clamp at radius R rides
    R theta, wire 1 turns the hub, the rim pays wire 2 out to the pen by the
    rim/hub ratio (book ch. 20-21). Force balance, so the spring preloads
    cancel; small angles (the lever rocks ~1.6 deg)."""
    k, a = nom.spring_rate, nom.sum_arm
    coupling = (
        N_ELEMENTS
        * k
        * a**2
        / (N_ELEMENTS * k * a**2 + nom.counter_rate * nom.counter_arm**2)
    )
    return coupling * lever_r * nom.wheel_ratio / (a * N_ELEMENTS)


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

    Machine hand, as build_channel_assembly._arc_geometry: the rod pin sits on
    the rocker's -X (crank) side at (-pin_x, +pin_y) from the pivot, the
    amplitude bars ride the +X side. The rod hangs plumb below the pin at rest
    with the lobe up, so the gear axis sits ``rod + ecc`` below the pin; the
    lobe's horizontal excursion is the cam's own (x = -ecc sin theta about its
    axis, as build_cylinder_gear's +Y-lobe cosine home), and the pin rides its
    arc about the pivot.
    """
    p0 = np.array([-nom.pin_x, nom.pin_y])
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
    """Ordinates x_i (i = 1..20), 0 <= x <= 1. Station d_i = x_i * d_max.

    Signed ordinates are NOT realised as negative stations: the built CAD keeps
    every bar on the lifting side (build_channel_assembly rejects
    amplitude_mm < 0). A signed function is analysed by lifting it with a
    constant (its k >= 1 coefficients are invariant; k = 0 is corrected), so
    the signed +/-1 square input is the 1/0 pattern below."""
    i = HARMONICS.astype(float)
    return {
        "all_ones": np.ones(N_ELEMENTS),  # constant: only k=0 survives
        "rect_half": (i <= 10).astype(float),  # step at the half range
        "gaussian_a0p1": np.exp(-((0.1 * i) ** 2)),  # Michelson trial 2, x in elements
        "alternating": np.where(
            i % 2 == 0, 0.0, 1.0
        ),  # lifted +/-1 square: odd channels on
        "pair_1_20": np.where(
            (i == 1) | (i == 20), 1.0, 0.0
        ),  # sparse: two channels, no averaging
    }


def ideal_coefficients(x: np.ndarray) -> np.ndarray:
    """A_k = sum_i x_i cos(i theta_k), the 20-element rule the machine realises."""
    return np.cos(np.outer(THETA_K, HARMONICS)) @ x


PERIOD = np.arange(720) * 2.0 * math.pi / 720


def read_coefficients(
    readings_mm: np.ndarray, x_read: np.ndarray, kappa: np.ndarray
) -> np.ndarray:
    """Steps 3-4 of the shipped readout procedure, in the units the operator
    has: ``readings_mm`` are the pen readings r_k off the mean line at each
    theta_k, ``x_read`` the recorded read ordinates, ``kappa`` the table's
    c2/c1 at each bar's station. The k=0 reading is s*(S + C2) for the
    unknown pen scale s, with S = sum x_read and C2 = sum x_read*kappa both
    known ordinate-unit sums, so s = r_0/(S + C2) -- no internal trace unit.
    Returns O_k in ordinate units with the second-harmonic term removed; the
    caller subtracts the read-vs-set vector."""
    cos_2k = np.cos(2.0 * np.outer(THETA_K, HARMONICS))
    s = readings_mm[0] / float(np.sum(x_read) + np.sum(x_read * kappa))
    return readings_mm / s - cos_2k @ (x_read * kappa)


def coefficient_errors_pct(measured: np.ndarray, x: np.ndarray) -> np.ndarray:
    """e_k in % of the greatest ideal term (Michelson's normalisation)."""
    ideal = ideal_coefficients(x)
    return 100.0 * (measured - ideal) / np.max(np.abs(ideal))


def second_harmonic(u: np.ndarray, grid: np.ndarray) -> float:
    """c2 (cosine component, trace units) of one channel's one-cycle motion --
    the slider-crank distortion the readout correction subtracts."""
    return 2.0 * float(np.mean(u * np.cos(2.0 * grid)))


_READ_GRID = np.arange(1440) * 2.0 * math.pi / 1440


def read_ordinate(d: float, nom: Nominal, f_full: float | None = None) -> float:
    """The ordinate a bar at station ``d`` (mm) actually contributes: its
    fundamental as a fraction of a full-scale bar's -- the station table's
    ``read ordinate`` column, what the operator records after setting the bar
    to the modelled station x*d_max."""
    if f_full is None:
        f_full = 2.0 * float(
            np.mean(hook_displacement(_READ_GRID, nom.d_max, nom) * np.cos(_READ_GRID))
        )
    return (
        2.0
        * float(np.mean(hook_displacement(_READ_GRID, d, nom) * np.cos(_READ_GRID)))
        / f_full
    )


def read_ordinates(x: np.ndarray, nom: Nominal) -> np.ndarray:
    """``read_ordinate`` for every channel of ordinate vector ``x``."""
    f_full = read_ordinate(nom.d_max, nom, f_full=1.0)
    return np.array([read_ordinate(float(xi) * nom.d_max, nom, f_full) for xi in x])


_READ_TABLES: dict[tuple, tuple[np.ndarray, np.ndarray]] = {}
_CYCLE_TABLES: dict[tuple, "CycleTable"] = {}


@dataclass(frozen=True)
class CycleTable:
    """One channel's PHYSICAL hook cycle at every reachable station (0.25 mm
    grid), for vectorised lookup: ``cycles[s, a]`` is the hook displacement
    (mm) at station ``stations[s]`` and crank angle ``_READ_GRID[a]``;
    ``mean`` its per-period mean line; ``read`` the read ordinate (fundamental
    / full-scale fundamental); ``kappa`` c2/c1. The Monte Carlo perturbs THIS
    waveform -- so a gain error scales the second harmonic and a phase error
    rotates it at twice the phase -- then runs the shipped correction."""

    stations: np.ndarray
    cycles: np.ndarray
    mean: np.ndarray
    read: np.ndarray
    kappa: np.ndarray

    def sample(self, d: np.ndarray, alpha: np.ndarray) -> np.ndarray:
        """Bilinear lookup of the cycle at stations ``d`` and angles ``alpha``
        (rad, any real; periodic), broadcast together."""
        d, alpha = np.broadcast_arrays(d, alpha)
        step = self.stations[1] - self.stations[0]
        si = np.clip(d / step, 0.0, len(self.stations) - 1.0)
        s0 = np.minimum(si.astype(int), len(self.stations) - 2)
        sf = si - s0
        n = self.cycles.shape[1]
        ai = (alpha % (2.0 * math.pi)) / (2.0 * math.pi) * n
        a0 = ai.astype(int) % n
        af = ai - ai.astype(int)
        a1 = (a0 + 1) % n
        c = self.cycles
        top = c[s0, a0] * (1.0 - af) + c[s0, a1] * af
        bot = c[s0 + 1, a0] * (1.0 - af) + c[s0 + 1, a1] * af
        return top * (1.0 - sf) + bot * sf


def cycle_table(nom: Nominal, step_mm: float = 0.25) -> CycleTable:
    """``CycleTable`` for ``nom``, cached (the same ~350 exact-kinematics
    solves ``read_table`` makes, kept whole instead of reduced to c1)."""
    key = astuple(nom)
    if key not in _CYCLE_TABLES:
        stations = np.arange(0.0, nom.d_max + step_mm / 2, step_mm)
        stations[-1] = nom.d_max
        cycles = np.array(
            [hook_displacement(_READ_GRID, float(d), nom) for d in stations]
        )
        c1 = 2.0 * (cycles * np.cos(_READ_GRID)).mean(axis=1)
        c2 = 2.0 * (cycles * np.cos(2.0 * _READ_GRID)).mean(axis=1)
        _CYCLE_TABLES[key] = CycleTable(
            stations, cycles, cycles.mean(axis=1), c1 / c1[-1], c2 / c1
        )
    return _CYCLE_TABLES[key]


def read_table(nom: Nominal, step_mm: float = 0.25) -> tuple[np.ndarray, np.ndarray]:
    """(station, read ordinate) samples from the pivot zero to full scale, for
    vectorised lookup (``np.interp``) of the ordinate a bar at ANY reachable
    station contributes -- the Monte Carlo's physical baseline. Cached per
    nominal: ~350 exact-kinematics solves once, not per draw."""
    key = astuple(nom)
    if key not in _READ_TABLES:
        t = cycle_table(nom, step_mm)
        _READ_TABLES[key] = (t.stations, t.read)
    return _READ_TABLES[key]


def setting_bias_station(
    x: np.ndarray, setting_tol: float, scale: float = 1.0
) -> np.ndarray:
    """The mean station offset (mm) a one-sided setting band leaves on each
    bar: a bar set at the stick zero cannot go below the pivot, so its setting
    error is uniform on [0, +tol] with mean +tol/2 -- it stands at station
    tol/2, not 0 -- and a bar at the stop is uniform on [-tol, 0], mean -tol/2.
    Bars in between are two-sided (mean 0). The procedure tells the operator
    to read the station table at THIS station (ordinate and kappa alike)."""
    at_stop = (x == 1.0) & (scale == 1.0)
    return np.where(x == 0.0, setting_tol / 2.0, 0.0) - np.where(
        at_stop, setting_tol / 2.0, 0.0
    )


@dataclass(frozen=True)
class MagnifierSetup:
    """How one trial is fitted to the pen stroke: the ordinate scale the bars
    are set at (1 = the ordinate 1 is full-scale travel; < 1 = the operator
    scaled every ordinate down so the k=0 peak fits the stroke at the minimum
    magnification), the magnifying-lever radius, and how much of the stroke the
    k=0 reading spans (< 1 only when the maximum magnification is not enough)."""

    ordinate_scale: float
    lever_r: float
    stroke_fill: float
    k0_reading_mm: float


class NominalTrial:
    """The NOMINAL machine (no tolerances) run through the shipped procedure
    on one ordinate vector, from the exact kinematics: every bar on the lifting
    side (station = x_i * d_max >= 0, the only poses the CAD builds), the pen
    trace summed from each channel's one-cycle hook motion, the readings taken
    off the trial's own mean line, then ``read_coefficients`` and the
    read-vs-set vector. One instance caches the per-station cycles."""

    def __init__(self, nom: Nominal) -> None:
        self.nom = nom
        self.grid = np.arange(1440) * 2.0 * math.pi / 1440
        self._cycle: dict[float, np.ndarray] = {}
        self.f_full = self.fundamental(nom.d_max)

    def one_cycle(self, d: float) -> np.ndarray:
        if d not in self._cycle:
            self._cycle[d] = hook_displacement(self.grid, d, self.nom)
        return self._cycle[d]

    def fundamental(self, d: float) -> float:
        return 2.0 * float(np.mean(self.one_cycle(d) * np.cos(self.grid)))

    def kappa(self, stations: np.ndarray) -> np.ndarray:
        """The table's c2/c1 at each bar's station."""
        return np.array(
            [
                second_harmonic(self.one_cycle(float(d)), self.grid)
                / self.fundamental(float(d))
                for d in stations
            ]
        )

    def x_read(self, stations: np.ndarray) -> np.ndarray:
        """The table's read ordinate at each bar's station (signed)."""
        return np.array([self.fundamental(float(d)) / self.f_full for d in stations])

    def trace(self, stations: np.ndarray, th: np.ndarray) -> np.ndarray:
        """The pen trace y(theta) (hook-displacement units) -- channel j runs
        j cycles per fundamental period."""
        y = np.zeros_like(th)
        for j, d in zip(HARMONICS, stations):
            y += np.interp(
                (j * th) % (2 * math.pi),
                self.grid,
                self.one_cycle(float(d)),
                period=2 * math.pi,
            )
        return y

    def readout(
        self,
        x: np.ndarray,
        *,
        theta_error: float = 0.0,
        null_lift: float | None = None,
        correct_second_harmonic: bool = True,
        calibrated_stick: bool = True,
        scale: float = 1.0,
    ) -> np.ndarray:
        """O_k in ordinate units through the procedure. ``theta_error`` (rad of
        fundamental angle) reads the pen at theta_k + error while every
        correction is still evaluated at theta_k -- the crank stopped off its
        index. ``null_lift`` (no calibrated stick: x_read = x + lift) and the
        two switches reproduce the report's correction cascade."""
        stations = scale * x * self.nom.d_max
        if calibrated_stick:
            x_read = self.x_read(stations) / scale
        else:
            x_read = x + (null_lift or 0.0) / scale
        kappa = self.kappa(stations) if correct_second_harmonic else np.zeros_like(x)
        zero = float(np.mean(self.trace(stations, PERIOD)))
        readings = self.trace(stations, THETA_K + theta_error) - zero
        measured = read_coefficients(readings, x_read, kappa)
        # what the operator subtracts: the known deviation of every channel's
        # read ordinate from its set ordinate -- the null-lift vector (20*lift
        # at k=0, -lift at odd k) or, with a calibrated stick, the table's
        # full per-channel deviation vector.
        return measured - ideal_coefficients(x_read - x)

    def k0_hook_mm(self, stations: np.ndarray) -> float:
        """The k=0 (theta = 0) reading off the mean line, in summed hook
        displacement (mm) -- what ``pen_gain`` turns into pen travel. A
        magnitude: the CAD's hand reads a +X bar negative at the top of stroke
        (the sign convention the procedure absorbs)."""
        zero = float(np.mean(self.trace(stations, PERIOD)))
        return abs(float(self.trace(stations, THETA_K[:1])[0]) - zero)

    def peak_bars(self, stations: np.ndarray) -> float:
        """The k=0 (theta = 0) peak in full-scale-bar units, from the station
        table alone: sum_i x_read,i (1 + kappa_i) -- each bar's fundamental
        plus the second harmonic riding its crest. This is S + C_2 of the
        procedure's step 3, and what the operator can compute before cranking;
        ``k0_hook_mm`` is the same number from the trace (asserted equal in
        test_error_budget)."""
        x_read = self.x_read(stations)
        return float(np.sum(x_read * (1.0 + self.kappa(stations))))

    def ordinate_scale_for(self, x: np.ndarray, capacity: float) -> float:
        """The largest scale f in (0, 1] at which the bars set at f * x * d_max
        have peak_bars <= capacity -- the executable rule of READOUT.md step 1.
        Not proportional: the idle bars' read ordinate is a fixed lift, so
        S(f) + C_2(f) is affine in f, not linear."""
        if self.peak_bars(x * self.nom.d_max) <= capacity:
            return 1.0
        lo, hi = 0.0, 1.0
        for _ in range(50):
            mid = 0.5 * (lo + hi)
            if self.peak_bars(mid * x * self.nom.d_max) > capacity:
                hi = mid
            else:
                lo = mid
        return 0.5 * (lo + hi)

    def magnifier_setup(self, x: np.ndarray) -> MagnifierSetup:
        """Fit the trial to the pen: the k=0 reading must span the half-stroke
        (Michelson's normalisation to the greatest term, book p. 99: "scaled by
        adjusting the magnifying lever"). Solve the lever radius that does it;
        below the reachable minimum the operator instead scales every ordinate
        down (``ordinate_scale_for`` against the machine's ordinate CAPACITY,
        the peak the pen holds at minimum magnification) with the clamp at the
        collar; above the maximum the reading falls short of the stroke by
        ``stroke_fill``."""
        nom = self.nom
        pen_per_bar = pen_gain(nom, 1.0) * abs(self.f_full)  # per lever mm
        peak = self.peak_bars(x * nom.d_max)
        if peak <= 0.0:
            raise ValueError("k=0 reading is not positive; the input is not lifted")
        r_req = nom.pen_half / (pen_per_bar * peak)
        if r_req >= nom.lever_r_min:
            lever_r = min(r_req, nom.lever_r_built)
            fill = min(1.0, nom.lever_r_built / r_req)
            return MagnifierSetup(1.0, lever_r, fill, pen_per_bar * lever_r * peak)
        capacity = nom.pen_half / (pen_per_bar * nom.lever_r_min)
        f = self.ordinate_scale_for(x, capacity)
        return MagnifierSetup(
            f,
            nom.lever_r_min,
            1.0,
            pen_per_bar * nom.lever_r_min * self.peak_bars(f * x * nom.d_max),
        )


def nominal_design_errors(
    nom: Nominal,
    null_lift: float = 0.0,
    correct_second_harmonic: bool = False,
    calibrated_stick: bool = False,
) -> dict[str, dict[str, float]]:
    """Coefficient errors of the NOMINAL machine per reference input
    (``NominalTrial.readout``), at each stage of the correction cascade.

    A bar parked at the pivot zero still moves -- the null station lies at
    ``null_station()`` < 0, unreachable -- so every channel reads as ordinate
    (d_i - d0)/d_max: a COMMON lift of ``null_lift`` = -d0/d_max on every
    channel. Under the 20-element rule a lift reads N*lift at k=0 and -lift at
    every odd k; pass ``null_lift`` to subtract that known vector after the
    k=0 normalisation (the buildable form of "zero the stick at the null
    station"). ``correct_second_harmonic`` applies the readout correction of
    tolerance-policy.md: the operator subtracts sum_i x_i^read kappa_i cos(2 i
    theta_k) using the per-station kappa (= c2/c1) table -- the READ ordinate,
    since an idle bar's c2 is not zero (its c1 is the null lift, not 0).
    ``calibrated_stick`` graduates the stick from single-channel runs instead
    of a ruler (Michelson's "hand stamped, unevenly spaced" stick): each
    channel's fundamental is read as the ordinate the calibration table
    assigns its station, so the machine-hand gain curvature (-1.010 at the
    null to -1.025 at full scale) is removed."""
    trial = NominalTrial(nom)
    out: dict[str, dict[str, float]] = {}
    for name, x in reference_inputs().items():
        measured = trial.readout(
            x,
            null_lift=null_lift,
            correct_second_harmonic=correct_second_harmonic,
            calibrated_stick=calibrated_stick,
        )
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
    setting_tol: float = 0.0,
    scale: float = 1.0,
) -> np.ndarray:
    """A_k read from a machine whose channel i has gain g_i and phase phi_i
    built from the drawn deviations ``dev[feature]`` (draws x 20), applied to
    the PHYSICAL hook cycle of each bar at its station (``cycle_table``): the
    pen trace is sum_i g_i u_i(j_i theta + phi_i), so a gain error scales the
    channel's second harmonic with its fundamental and a phase error rotates
    it at twice the phase, and an idle bar's ~0.028 of motion is perturbed by
    that channel's own deviations too, not only by the nominal lift. The
    readings (off each draw's own mean line) then go through the SHIPPED
    correction -- s = r0/(S + C2), the nominal kappa table at the set
    stations, the read-vs-set vector -- exactly as ``NominalTrial.readout``,
    so whatever the fixed nominal correction cannot remove (delta * kappa,
    the rotated second harmonic) lands in the scatter. ``setting_tol`` is the
    station-setting half-width the ``station_setting`` draws were taken from
    (needed for the one-sided mean, below); ``scale`` is the trial's ordinate
    scale (``MagnifierSetup``): the bars stand at scale * x * d_max, so a fixed
    setting error and a fixed idle lift are 1/scale larger in the trial's own
    units. Returns e_k in % FS, shape (draws, K_MAX+1)."""
    draws = next(iter(dev.values())).shape[0]
    log_g = np.zeros((draws, N_ELEMENTS))
    phi = np.zeros((draws, N_ELEMENTS))
    d = np.broadcast_to(scale * x * nom.d_max, (draws, N_ELEMENTS)).copy()
    bias = np.zeros(N_ELEMENTS)
    for key, v in dev.items():
        if key in sens:
            log_g += np.log1p(sens[key] / 100.0 * v)
        elif key in ("cam_phase", "mesh_lag_spread"):
            phi += np.radians(v)
        elif key == "station_setting":
            # A bar can be set neither below the pivot (build_channel_assembly
            # rejects amplitude_mm < 0) nor past amplitude.max_travel_mm (the
            # config gate): the setting error at a zero ordinate is one-sided
            # [0, +tol] and at a full-scale ordinate one-sided [-tol, 0]. Draws
            # come in uniform on [-tol, +tol]; fold the unreachable half onto the
            # reachable one at each bound (uniform on the reachable band, mean
            # +/-tol/2 -- not a clipped point mass with mean tol/4). Each bound's
            # MEAN is a coherent lift identical in kind to the null lift the
            # procedure measures on the assembled machine (one bar at the stick
            # zero / at the stop), so it is subtracted the same way
            # (setting_bias_station, published in READOUT.md); only the scatter
            # about it survives.
            at_zero = (x == 0.0)[None, :]
            at_full = ((x == 1.0) & (scale == 1.0))[None, :]
            v = np.where(at_zero, np.abs(v), np.where(at_full, -np.abs(v), v))
            d = np.clip(d + v, 0.0, nom.d_max)
            bias = setting_bias_station(x, setting_tol, scale)
        else:
            raise KeyError(f"no model for feature {key}")
    g = np.exp(log_g)
    t = cycle_table(nom)
    set_stations = scale * x * nom.d_max
    # the operator's table row: at the mean biased station when a bar sits at
    # an end of the scale (READOUT.md step 1), else the set station
    recorded = set_stations + bias
    x_read = np.interp(recorded, t.stations, t.read) / scale
    kappa = np.interp(recorded, t.stations, t.kappa)
    measured = _read_draws(x, t, g, phi, d, x_read, kappa)
    # the NOMINAL machine through the same sampler (g = 1, phi = 0, bars at
    # their set stations, the set-station row): its residual is the closure's
    # separate nominal_residual_mae term, so the scatter scores deviations only
    base = _read_draws(
        x,
        t,
        np.ones((1, N_ELEMENTS)),
        np.zeros((1, N_ELEMENTS)),
        set_stations[None, :],
        np.interp(set_stations, t.stations, t.read) / scale,
        np.interp(set_stations, t.stations, t.kappa),
    )
    fs = np.max(np.abs(ideal_coefficients(x)))
    return 100.0 * (measured - base) / fs


def _read_draws(
    x: np.ndarray,
    t: CycleTable,
    g: np.ndarray,
    phi: np.ndarray,
    d: np.ndarray,
    x_read: np.ndarray,
    kappa: np.ndarray,
) -> np.ndarray:
    """The shipped procedure on a batch of machines: pen readings from each
    channel's physical cycle at its drawn station ``d`` (draws x 20), read at
    j_i theta_k + phi_i with gain g_i, off each draw's own mean line; then
    s = r0/(S + C2), the kappa correction and the read-vs-set vector with the
    operator's recorded ``x_read``/``kappa``. Returns O_k, shape (draws, K+1)."""
    alpha = HARMONICS[None, None, :] * THETA_K[None, :, None] + phi[:, None, :]
    u = t.sample(d[:, None, :], alpha)  # draws,k,i
    r = np.einsum("di,dki->dk", g, u)
    zero = np.einsum("di,di->d", g, np.interp(d, t.stations, t.mean))
    readings = r - zero[:, None]
    s = readings[:, :1] / (np.sum(x_read) + np.sum(x_read * kappa))
    cos_2k = np.cos(2.0 * np.outer(THETA_K, HARMONICS))
    measured = readings / s - (cos_2k @ (x_read * kappa))[None, :]
    return measured - ideal_coefficients(x_read - x)[None, :]


def monte_carlo(
    budget: dict[str, Any], nom: Nominal, setups: dict[str, MagnifierSetup]
) -> dict[str, Any]:
    """Per-feature and combined coefficient-error statistics (% FS) with every
    critical feature drawn uniformly within its tolerance, per channel, on the
    budget's reference inputs through the calibrated readout, each input at the
    ordinate scale its ``MagnifierSetup`` fits to the pen."""
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

    # ``class: channel`` -- a part's deviation is the machine's: ONE draw per
    # draw, shared by every trial. ``class: setup`` -- re-introduced every
    # trial (the operator resets the bars), so each reference input gets its
    # own draw and the pooled worst coefficient sees independent settings.
    for key, f in feats.items():
        if f["class"] not in ("channel", "setup"):
            raise ValueError(
                f"{key}: class must be channel or setup, got {f['class']!r}"
            )

    def draw(f: dict[str, Any]) -> np.ndarray:
        return rng.uniform(-f["tolerance"], f["tolerance"], size=(draws, N_ELEMENTS))

    all_dev = {
        key: draw(f) if f["class"] == "channel" else {n: draw(f) for n in names}
        for key, f in feats.items()
    }

    def stats(dev: dict[str, Any]) -> dict[str, Any]:
        per_input = {}
        pooled = []
        for name in names:
            e = _channel_model(
                inputs[name],
                nom,
                {k: v[name] if isinstance(v, dict) else v for k, v in dev.items()},
                sens,
                feats["station_setting"]["tolerance"],
                setups[name].ordinate_scale,
            )
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


def _minimum_pose_wire_estimate(nom: Nominal) -> dict[str, float]:
    """An OFFLINE estimate -- not a CAD gate -- of wire 1's straight rest run
    with the clamp against the bracket collar: the hook (which rides the clamp
    at machine x = LEVER_X0 - clamp local x, the same y/z as built) to the hub
    tangent, versus the magnifying wheel's rim. Reported so the waiver in
    error_budget.yaml is an informed one; the proof is a seat build of the
    magnifier at that pose (#748)."""
    import magnifying_wheel_geom

    lever_x0 = lever_wire_geom.CLAMP_X + magnifying_lever_geom.CLAMP_LOCAL_X  # 200
    hook_x = lever_x0 - (magnifying_lever_geom.KNIFE_LOCAL_X - nom.lever_r_min)
    hook = np.array([hook_x, lever_wire_geom.HOOK_Y, lever_wire_geom.HOOK_Z])
    cx, cy = lever_wire_geom.WHEEL_X, lever_wire_geom.WHEEL_BAR_Y
    vx, vy = hook[0] - cx, hook[1] - cy
    r_eff = lever_wire_geom._R_EFF
    theta = math.atan2(vy, vx) - math.acos(r_eff / math.hypot(vx, vy))
    end = np.array(
        [
            cx + r_eff * math.cos(theta),
            cy + r_eff * math.sin(theta),
            lever_wire_geom.HUB_END_Z,
        ]
    )
    # closest approach of the run to the wheel: the wire runs in FRONT of the
    # wheel (less negative z), so the clearance is wire z minus the face z of
    # whatever it passes over -- the rim ring (radial 44..50) or the spokes
    ts = np.linspace(0.0, 1.0, 2001)
    pts = hook[None, :] + ts[:, None] * (end - hook)[None, :]
    radial = np.hypot(pts[:, 0] - cx, pts[:, 1] - cy)
    rim_r = magnifying_wheel_geom.RIM_OUTER_DIA / 2.0
    rim_in = magnifying_wheel_geom.RIM_INNER_DIA / 2.0
    margin = lever_wire_geom.WIRE_DIA / 2.0 + lever_wire_geom.CLEARANCE
    over_ring = (radial >= rim_in - margin) & (radial <= rim_r + margin)
    over_spokes = (radial > lever_wire_geom.HUB_DIA / 2.0 + margin) & (
        radial < rim_in - margin
    )
    ring_face = lever_wire_geom.WHEEL_MID_Z + magnifying_wheel_geom.RIM_AXIAL / 2.0
    spoke_face = lever_wire_geom.WHEEL_MID_Z + magnifying_wheel_geom.SPOKE_AXIAL / 2.0

    def gap(mask: np.ndarray, face: float) -> float:
        if not np.any(mask):
            return float("inf")
        return float(np.min(pts[mask, 2] - face)) - lever_wire_geom.WIRE_DIA / 2.0

    return {
        "hook_x_mm": float(hook[0]),
        "wire_length_mm": float(np.linalg.norm(end - hook)),
        "min_radial_to_wheel_axis_mm": float(np.min(radial)),
        "rim_outer_radius_mm": rim_r,
        "z_clearance_to_rim_face_where_over_ring_mm": gap(over_ring, ring_face),
        "z_clearance_to_spoke_face_where_over_spokes_mm": gap(over_spokes, spoke_face),
        "note": "straight rest run only; no clamp/rod/collar/frame check, no articulation -- NOT a CAD gate",
    }


def closed_form_terms(
    nom: Nominal, budget: dict[str, Any], setups: dict[str, MagnifierSetup]
) -> dict[str, Any]:
    """Error terms that are procedure or design-adjustment items, not part
    tolerances: knife hysteresis, strap lost motion, ordinate readout, timebase.
    Each is evaluated at the ``reserved`` assumptions of error_budget.yaml as a
    ``pct_fs`` (% of the greatest term, each reference input fitted to the pen
    by its ``MagnifierSetup``) so ``budget_closes`` can bound it."""
    res = budget["reserved"]
    u_fs = (
        linear_gain(nom) * nom.d_max
    )  # hook displacement of one channel at full station
    # Knife-edge hysteresis: the lever stalls while the moment error is below
    # T_f = N * f_r (N = total normal load on the edge, f_r = rolling-resistance
    # length of the edge). The 20 channel preloads pull one side of the lever
    # down; static balance needs the counter spring to pull the other side down
    # with moment 20 * preload * a = F_c * b, and BOTH loads bear on the knife:
    # N = 20 * preload * (1 + a / b). With D = sum s a^2 + S b^2 the equivalent
    # hook-position error is a*T_f/D and ONE channel's full-scale hook motion
    # s*a^2*u_fs/D, so the ratio T_f/(s*a*u_fs) needs no D. Against the
    # all-ones full scale (every channel at u_fs) the stall is that ratio / N.
    preload = nom.spring_rate * (
        channel_spring_installed_spec.INSTALLED_BODY_LENGTH
        - channel_spring_installed_spec.FREE_BODY_LENGTH
    )
    counter_needed = N_ELEMENTS * preload * nom.sum_arm / nom.counter_arm
    # What the CAD's counter spring can actually supply: rate x the extension
    # its geometry allows. The part carries no free length; close-wound its
    # 165 x 1.8 body would be COIL_COUNT * WIRE_DIA, so the installed 325.3 body
    # is at most that much extension.
    counter_max_ext = (
        counter_spring_spec.COIL_BODY_LENGTH
        - counter_spring_spec.COIL_COUNT * counter_spring_spec.WIRE_DIA
    )
    counter_available = nom.counter_rate * counter_max_ext
    knife_load = N_ELEMENTS * preload + counter_needed
    f_r = float(res["knife"]["rolling_resistance_mm"])
    stall_one = 100.0 * knife_load * f_r / (nom.spring_rate * nom.sum_arm * u_fs)
    # The stall is a fixed displacement -- one channel's full-scale hook motion
    # times stall_one/100. In a trial's own ordinate units (one unit = scale x
    # the full-scale hook motion) that is stall_one/scale, so against the
    # trial's ideal greatest term sum(x) it is stall_one / (scale * sum x): a
    # trial the operator had to scale down to fit the pen pays 1/scale.
    scored = list(budget["reference_inputs"])
    broad = [n for n in scored if n != "pair_1_20"]
    inputs = reference_inputs()
    knife_per_input = {
        n: stall_one / (setups[n].ordinate_scale * float(np.sum(inputs[n])))
        for n in scored
    }
    knife = {
        "assumed_preload_N_per_spring": preload,
        "counter_spring_needed_N": counter_needed,
        "counter_spring_available_N": counter_available,
        "counter_spring_max_extension_mm": counter_max_ext,
        "static_balance": counter_available >= counter_needed,
        "assumed_knife_load_N": knife_load,
        "assumed_rolling_resistance_mm": f_r,
        "stall_pct_of_one_channel_fs": stall_one,
        "pct_fs_per_input": knife_per_input,
        "pct_fs": max(knife_per_input[n] for n in broad),
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
    # Ordinate readout. The procedure divides every reading by the k=0 reading
    # through s = r_0 / (S + C_2) (S = sum x_read, C_2 = sum x_read kappa, both
    # in the trial's ordinate units), so coefficient k carries TWO independent
    # reading errors: its own, delta/s = delta (S + C_2)/r_0, and the
    # normaliser's scaled by the PHYSICAL pre-correction reading ratio
    # a_k = r_k/r_0. r_0 is the k=0 reading the MagnifierSetup fits to the pen:
    # stroke_fill x pen_half (the full half-stroke unless even the maximum
    # magnification cannot fill it). Against the trial's IDEAL greatest term
    # sum x (what the error is scored on) one reading is therefore
    # reading/(fill pen_half) x (S + C_2)/sum x -- idle bars read ~0.028/scale
    # each and the second harmonic rides the k=0 peak, so both inflate it.
    # Scored as the MAE the benchmark and the other closure terms use: for
    # independent uniform +/-delta reads, E|delta_k - a_k delta_0| =
    # delta (1/2 + a_k^2/6) (|a_k| <= 1), averaged over k (k=0 reads as itself:
    # zero error). The worst single coefficient (RSS bound delta sqrt(1 +
    # a_k^2), sqrt 2 on an input whose k=20 term equals its k=0) is reported
    # beside it, not gated.
    reading = float(res["readout"]["reading_uncertainty_mm"])
    trial = NominalTrial(nom)
    share = {}
    scale = {}
    for n in scored:
        x = inputs[n]
        f = setups[n].ordinate_scale
        stations = f * x * nom.d_max
        x_read_n = trial.x_read(stations) / f
        s_plus_c2 = float(np.sum(x_read_n) + np.sum(x_read_n * trial.kappa(stations)))
        zero = float(np.mean(trial.trace(stations, PERIOD)))
        raw = trial.trace(stations, THETA_K) - zero
        share[n] = raw / raw[0]
        scale[n] = (
            100.0
            * reading
            / (setups[n].stroke_fill * nom.pen_half)
            * s_plus_c2
            / float(np.sum(x))
        )
    mae_factor = {}
    for n in scored:
        f = 0.5 + share[n] ** 2 / 6.0
        f[0] = 0.0  # k=0 is normalised by itself
        mae_factor[n] = float(np.mean(f))
    mae = {n: scale[n] * mae_factor[n] for n in scored}
    worst_bound = {
        n: scale[n] * float(np.max(np.sqrt(1.0 + share[n][1:] ** 2))) for n in scored
    }
    readout = {
        "pen_half_stroke_mm": nom.pen_half,
        "assumed_reading_uncertainty_mm": reading,
        "ordinate_pct_fs_per_0p1mm_reading": 100.0 * 0.1 / nom.pen_half,
        "one_reading_pct_fs_per_input": scale,
        "normaliser_share_max_abs": {
            n: float(np.max(np.abs(share[n][1:]))) for n in scored
        },
        "pct_fs_per_input": mae,
        "pct_fs_worst_coefficient_bound": worst_bound,
        "pct_fs": max(mae[n] for n in broad),
        "note": "MAE over k of |own read - a_k * k=0 read|, uniform +/-reading each, a_k the physical r_k/r_0, one reading = reading/(fill x pen_half) x (S + C_2)/sum x; worst-coefficient RSS bound reported, not gated",
    }
    # Timebase: reading at the wrong theta. The budgeted procedure stops the
    # crank on its index within +/-index_deg (uniform); one fundamental period
    # is CRANK_TURNS_PER_PERIOD crank turns (gear k turns k/80 per crank turn).
    # Scored on the PHYSICAL trace through the shipped procedure
    # (NominalTrial.readout with theta_error): the pen is read at theta_k +
    # delta while the operator's corrections -- second harmonic, read-vs-set
    # -- are still evaluated at theta_k, so the live idle bars, the calibrated
    # ordinates and the CAD's own 2nd/3rd harmonics all contribute to the
    # slope, not just the ideal set vector. delta is integrated over the
    # uniform band by Gauss-Legendre quadrature (RMS over k and delta, % FS),
    # worst reference input. The analytic ideal-vector slope
    # -sum i x_i sin(i theta_k) is reported beside it for comparison, as is the
    # abscissa-reading alternative at the CAD's platen feed.
    index_deg = float(res["timebase"]["crank_index_deg"])
    rad_per_crank_turn = 2.0 * math.pi / CRANK_TURNS_PER_PERIOD
    rad_per_0p1mm = (
        0.1 / paper_drive_geom.NET_RACK_TRAVEL_PER_CRANK_REV * rad_per_crank_turn
    )
    rad_index = index_deg / 360.0 * rad_per_crank_turn
    nodes, weights = np.polynomial.legendre.leggauss(8)
    slope = {}
    physical = {}
    for name, x in inputs.items():
        fs = np.max(np.abs(ideal_coefficients(x)))
        s = -np.sin(np.outer(THETA_K, HARMONICS)) @ (x * HARMONICS)
        slope[name] = float(np.sqrt(np.mean(s * s)) / fs * 100.0)
        f = setups[name].ordinate_scale
        on_index = trial.readout(x, scale=f)
        sq = 0.0
        for node, w in zip(nodes, weights):
            off = trial.readout(x, theta_error=float(node) * rad_index, scale=f)
            sq += float(w) / 2.0 * float(np.mean((off - on_index) ** 2))
        physical[name] = 100.0 * math.sqrt(sq) / fs
    worst = max(scored, key=lambda n: physical[n])
    timebase = {
        "pct_fs_per_rad_rms_ideal_vector": slope,
        "pct_fs_physical_per_input": physical,
        "platen_feed_mm_per_crank_turn": paper_drive_geom.NET_RACK_TRAVEL_PER_CRANK_REV,
        "pct_fs_worst_per_0p1mm_abscissa": slope[worst] * rad_per_0p1mm,
        "pct_fs_worst_per_0p1mm_abscissa_coarse_gears": slope[worst]
        * rad_per_0p1mm
        / paper_drive_geom.COARSE_FEED_RATIO,
        "assumed_crank_index_deg": index_deg,
        "worst_input": worst,
        "pct_fs_ideal_vector": slope[worst] * rad_index / math.sqrt(3.0),
        "pct_fs": physical[worst],
        "note": "RMS over k and a uniform +/-index band of the physical trace read off-index through the procedure, worst broad input; ideal-vector slope reported for comparison",
    }
    # The magnifier: what the CAD's output chain lets the operator do. The
    # ordinate capacity is the summed full-scale-bar-equivalents whose k=0 peak
    # just fills the half-stroke at the minimum magnification -- every broad
    # input whose read ordinates sum to more than this is scaled down by the
    # operator (MagnifierSetup.ordinate_scale < 1), so setting and knife
    # errors grow by that factor. A design lever, not a part tolerance.
    gain_min = pen_gain(nom, nom.lever_r_min)
    magnifier = {
        "lever_radius_min_mm": nom.lever_r_min,
        "lever_radius_built_mm": nom.lever_r_built,
        "lever_radius_max_mm": nom.lever_r_max,
        "wheel_ratio": nom.wheel_ratio,
        "pen_mm_per_full_scale_bar_at_min": gain_min * abs(trial.f_full),
        "pen_mm_per_full_scale_bar_at_built": pen_gain(nom, nom.lever_r_built)
        * abs(trial.f_full),
        "ordinate_capacity_full_scale_bars": nom.pen_half
        / (gain_min * abs(trial.f_full)),
        "station_sum_capacity_mm": nom.pen_half
        / (gain_min * abs(trial.f_full))
        * nom.d_max,
        "per_input": {n: asdict(setups[n]) for n in scored},
        "inputs_at_minimum_pose": [
            n for n in scored if setups[n].lever_r == nom.lever_r_min
        ],
        "minimum_pose_cad_gated": False,  # build_magnifier_assembly builds the
        # as-built pose only; the clamp/rod/wire at the collar is #748's proof
        "minimum_pose_wire_estimate": _minimum_pose_wire_estimate(nom),
        "note": "capacity = full-scale bars whose k=0 peak fills the half-stroke at the minimum magnification; inputs beyond it are set at ordinate_scale < 1; the minimum pose is NOT CAD-gated (reserved.readout.waive_minimum_pose)",
    }
    return {
        "knife": knife,
        "lost_motion": lost_motion,
        "readout": readout,
        "timebase": timebase,
        "magnifier": magnifier,
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
    stations = [nom.d_max, nom.d_max / 2, nom.d_max / 4, 10.0]  # lifting side only
    trial = NominalTrial(nom)
    setups = {
        name: trial.magnifier_setup(reference_inputs()[name])
        for name in budget["reference_inputs"]
    }
    r = {
        "nominal": nom.__dict__,
        "linear_gain_mm_per_mm": linear_gain(nom),
        "null_station_mm": d0,
        "harmonics": {f"{d:+.0f}": harmonic_content(d, nom, null=d0) for d in stations},
        "null_lift_ordinate": -d0 / nom.d_max,
        "station_setting_tolerance_mm": float(
            budget["critical_features"]["station_setting"]["tolerance"]
        ),
        "nominal_design_errors": {
            "uncorrected": nominal_design_errors(nom),
            "null_lift_corrected": nominal_design_errors(
                nom, null_lift=-d0 / nom.d_max
            ),
            "null_lift_and_c2_corrected": nominal_design_errors(
                nom, null_lift=-d0 / nom.d_max, correct_second_harmonic=True
            ),
            "calibrated_stick_and_c2_corrected": nominal_design_errors(
                nom, correct_second_harmonic=True, calibrated_stick=True
            ),
        },
        "gain_sensitivities": gain_sensitivities(nom),
        "finite_difference_check": finite_difference_check(nom),
        "monte_carlo": monte_carlo(budget, nom, setups),
        "closed_form": closed_form_terms(nom, budget, setups),
        "targets": budget["targets"],
        "benchmark": budget["benchmark"],
        "reserved_allowance": {
            k: float(v["allowance_pct"]) for k, v in budget["reserved"].items()
        },
        "counter_spring_balance_waived": bool(
            budget["reserved"]["knife"].get("waive_static_balance", False)
        ),
        "minimum_pose_waived": bool(
            budget["reserved"]["readout"].get("waive_minimum_pose", False)
        ),
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
        f" (unreachable) = a common lift of {r['null_lift_ordinate']:.4f} ordinate on every bar"
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
        f"{'input':>16} {'uncorrected':>12} {'max':>6} {'+null lift':>11} {'max':>6} {'+c2':>8} {'max':>6} {'+cal stick':>11} {'max':>6}"
    )
    nde = r["nominal_design_errors"]
    a, b, c3, c4 = (
        nde["uncorrected"],
        nde["null_lift_corrected"],
        nde["null_lift_and_c2_corrected"],
        nde["calibrated_stick_and_c2_corrected"],
    )
    for name in a:
        p(
            f"{name:>16} {a[name]['mae']:>12.3f} {a[name]['max']:>6.3f} {b[name]['mae']:>11.3f} {b[name]['max']:>6.3f} "
            f"{c3[name]['mae']:>8.3f} {c3[name]['max']:>6.3f} {c4[name]['mae']:>11.3f} {c4[name]['max']:>6.3f}"
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
        f"pair worst <= {t['pair_consistency_p99_pct']}   (benchmark MAE {r['benchmark']['mae_fs_pct']}, max {r['benchmark']['max_fs_pct']})"
    )
    p("\n## 4. Terms that are not part tolerances")
    p(json.dumps(r["closed_form"], indent=2))
    p("\n## 5. Closure -- every term against the benchmark MAE")
    for k, v in r["closure"].items():
        if k == "pair_terms":
            continue
        p(f"  {k:<28} {v:.3f}")
    pt = r["closure"]["pair_terms"]
    p(
        f"  pair_1_20 worst coefficient = residual {pt['nominal_residual_max']:.3f}"
        f" + RSS(scatter p99 {pt['scatter_p99']:.3f}, readout "
        f"{pt['readout_worst_coefficient']:.3f}, timebase {pt['timebase']:.3f}, "
        f"knife {pt['knife']:.3f}) vs {t['pair_consistency_p99_pct']}"
    )


def closure(r: dict[str, Any], budget: dict[str, Any]) -> dict[str, Any]:
    """Every reserved term (% FS) beside the scatter, and their total: the
    corrected nominal residual is systematic and adds; scatter, readout,
    timebase and knife are independent and combine root-sum-square."""
    cf = r["closed_form"]
    nde = r["nominal_design_errors"]["calibrated_stick_and_c2_corrected"]
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
    # The sparse two-channel trial is gated on its WORST coefficient (the
    # benchmark's 2 % largest tabulated difference), not the MAE: its own
    # scatter p99 plus every reserved term evaluated on it, combined the same
    # way -- the residual's max adds, the rest RSS. Excluding the pair from the
    # reserved terms (as the MAE closure does, because it is not a broad
    # input) would let the knife stall it pays most for hide behind a green
    # scatter number.
    pair = "pair_1_20"
    pair_terms = {
        "nominal_residual_max": nde[pair]["max"],
        "scatter_p99": r["monte_carlo"]["combined"]["per_input"][pair]["p99_max"],
        "readout_worst_coefficient": cf["readout"]["pct_fs_worst_coefficient_bound"][
            pair
        ],
        "timebase": cf["timebase"]["pct_fs_physical_per_input"][pair],
        "knife": cf["knife"]["pct_fs_per_input"][pair],
    }
    pair_rss = math.sqrt(
        sum(
            pair_terms[k] ** 2
            for k in ("scatter_p99", "readout_worst_coefficient", "timebase", "knife")
        )
    )
    terms["pair_worst"] = pair_terms["nominal_residual_max"] + pair_rss
    terms["pair_terms"] = pair_terms
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
    cl, allow = r["closure"], r["reserved_allowance"]
    if cl["pair_worst"] > t["pair_consistency_p99_pct"]:
        pt = cl["pair_terms"]
        bad.append(
            f"pair worst coefficient {cl['pair_worst']:.3f} > {t['pair_consistency_p99_pct']} "
            f"(residual {pt['nominal_residual_max']:.3f} + RSS of scatter p99 "
            f"{pt['scatter_p99']:.3f}, readout {pt['readout_worst_coefficient']:.3f}, "
            f"timebase {pt['timebase']:.3f}, knife {pt['knife']:.3f})"
        )
    for k in ("nominal_residual_mae", "readout", "timebase", "knife"):
        if cl[k] > allow[k]:
            bad.append(f"{k} {cl[k]:.3f} > allowance {allow[k]}")
    knife = r["closed_form"]["knife"]
    if not knife["static_balance"] and not r["counter_spring_balance_waived"]:
        bad.append(
            "counter spring cannot balance the channel preload: "
            f"{knife['counter_spring_available_N']:.0f} N available vs "
            f"{knife['counter_spring_needed_N']:.0f} N needed"
        )
    mag = r["closed_form"]["magnifier"]
    if (
        mag["inputs_at_minimum_pose"]
        and not mag["minimum_pose_cad_gated"]
        and not r["minimum_pose_waived"]
    ):
        bad.append(
            "magnifier minimum pose is not CAD-gated but scores "
            f"{', '.join(mag['inputs_at_minimum_pose'])} "
            f"(clamp at {mag['lever_radius_min_mm']:.0f} mm from the knife)"
        )
    if cl["total_mae"] > r["benchmark"]["mae_fs_pct"]:
        bad.append(
            f"total MAE {cl['total_mae']:.3f} > benchmark {r['benchmark']['mae_fs_pct']}"
        )
    return bad


STICK_DIVISION_MM = measuring_stick_spec.DIVISION_SPACING  # the engraved scale


def calibration_table(
    nom: Nominal, step_mm: float = 4.0
) -> list[tuple[float, float, float]]:
    """(station mm, read ordinate, kappa) per station from the pivot zero to
    full scale: the ordinate -> stick-reading lookup and the second-harmonic
    table the operator uses. The stick itself is engraved LINEAR in station
    (``STICK_DIVISION_MM`` per numbered division); the table converts. ``read
    ordinate`` is the channel's fundamental as a fraction of a full-scale bar's
    (signed -- the machine-hand drive reads a +X bar negative, which the
    operator absorbs as a sign convention); ``kappa`` is c2/c1."""
    grid = np.arange(1440) * 2.0 * math.pi / 1440
    rows = []
    f_full = None
    stations = np.arange(0.0, nom.d_max + 1e-9, step_mm)
    if not math.isclose(stations[-1], nom.d_max):
        stations = np.append(stations, nom.d_max)  # the travel stop, always a row
    cycles = {float(d): hook_displacement(grid, float(d), nom) for d in stations}
    f_full = 2.0 * float(np.mean(cycles[nom.d_max] * np.cos(grid)))
    for d in stations:
        u = cycles[float(d)]
        c1 = 2.0 * float(np.mean(u * np.cos(grid)))
        c2 = 2.0 * float(np.mean(u * np.cos(2.0 * grid)))
        rows.append((float(d), c1 / f_full, c2 / c1))
    return rows


def readout_procedure(r: dict[str, Any], nom: Nominal) -> str:
    """The operating/readout procedure the budget's residual assumes, as a
    self-contained Markdown document for the release bundle -- generated from
    the model's own numbers so it cannot drift from what check:budget proved."""
    cf = r["closed_form"]
    mag = cf["magnifier"]
    rows = calibration_table(nom)
    lift = r["null_lift_ordinate"]
    trial = NominalTrial(nom)
    ones = np.ones(N_ELEMENTS)
    scale_all = trial.ordinate_scale_for(ones, mag["ordinate_capacity_full_scale_bars"])
    naive_all = mag["ordinate_capacity_full_scale_bars"] / trial.peak_bars(
        ones * nom.d_max
    )
    p_all = (
        trial.peak_bars(ones * nom.d_max),
        trial.peak_bars(naive_all * ones * nom.d_max),
    )
    p_min_full = (
        mag["ordinate_capacity_full_scale_bars"]
        * mag["lever_radius_min_mm"]
        / mag["lever_radius_built_mm"]
    )  # the smallest peak the as-built cap can still bring to full stroke
    scale_table = "\n".join(
        f"| {f:.3f} | {f * nom.d_max:6.2f} | {trial.peak_bars(f * ones * nom.d_max):6.2f} |"
        for f in sorted(
            {1.0, 0.75, 0.5, 0.4, 0.3, 0.25, scale_all, 0.2, 0.1, 0.0}, reverse=True
        )
    )
    tol = r["station_setting_tolerance_mm"]
    at_zero = read_ordinate(tol / 2.0, nom)
    at_stop = read_ordinate(nom.d_max - tol / 2.0, nom)
    table = "\n".join(
        f"| {d:6.1f} | {d / STICK_DIVISION_MM:6.3f} | {x:+.4f} | {k * 100:6.2f} % |"
        for d, x, k in rows
    )
    return f"""# Reading the analyzer -- operating and readout procedure

Generated by `cad/scripts/error_budget.py --procedure` from the model that
`check:budget` gates; the residual it credits (nominal design
{r["closure"]["nominal_residual_mae"]:.3f} % of the greatest term) is reached
only by following every step below. Coefficient $k$ is read at crank position
$\\theta_k = k\\pi/20$, i.e. with the crank stopped on its index after $2k$
turns of the {CRANK_TURNS_PER_PERIOD}-turn period.

**Why there is arithmetic after the pen stops** -- and why every step of it is
Michelson's own procedure (1898, pp. 10-11: "the required coefficients are
then proportional to the ordinates erected at these divisions"; every
published table normalised to the greatest term) -- is explained in
`cad/docs/device-operation.md`. Read that first if the steps below are a
surprise: the machine draws a *curve of coefficients* whose scale is set by
the magnifier, so reading and normalising were always part of analysis.

At a glance (the station table below is the only data needed beyond the
readings):

```mermaid
flowchart LR
    t[("station table:<br/>d -> x_read, kappa")]
    s0["0. scale f: largest with<br/>P(f) = sum table(f x_i)(1+kappa) <= {mag["ordinate_capacity_full_scale_bars"]:.2f}"] --> s1["1. set bar i to the linear<br/>station f x_i * {nom.d_max:.0f} mm"] --> s1b["record x_read,i =<br/>table ordinate / f"]
    t -.-> s1b
    s1b --> s2["2. crank one way; read r_k (mm)<br/>off the mean line at 2k turns"]
    s2 --> s3["3. s = r_0 / (S + C_2)<br/>O'_k = r_k / s"]
    s3 --> s4a["4a. subtract<br/>sum x_read kappa cos(2 i theta_k)"]
    t -.-> s4a
    s4a --> s4b["4b. subtract<br/>sum (x_read - x_set) cos(i theta_k)"]
    s4b --> s5["5. e_k = (O_k - C_k) / max|C|"]
```

## 1. Set the bars linearly; record what each one reads

The stick's 0 tick sits at the rocker pivot axis (stick drawing note 5); every
station is on the lifting side. Set bar $i$ to the **linear station**
$d_i = f\\,x_i \\cdot {nom.d_max:.0f}$ mm ($= f\\,x_i \\cdot {nom.d_max / STICK_DIVISION_MM:.3f}$
divisions on the engraved {STICK_DIVISION_MM:.2f} mm/division scale), reading
to 1/5 minor division (setting error +/-{tol:.2f} mm max per bar). Then look up,
in the table, the ordinate that station actually contributes (interpolate
between rows), **divide it by the trial's scale $f$** (below; $f = 1$ unless
the function had to be scaled down to fit the pen) and record the quotient as
the **read ordinate** $x^{{read}}_i$. Everything downstream -- $S$, $C_2$, the
corrections of step 4 -- uses $x^{{read}}_i$ in the function's OWN units, so
$f$ never appears again. The ordinate is NOT linear in station (the null lies
at {r["null_station_mm"]:+.2f} mm, unreachable, and the slope of ordinate per
mm changes by
{100.0 * ((rows[-1][1] - rows[-2][1]) / (rows[1][1] - rows[0][1]) - 1.0):+.1f} %
from the pivot to full scale), so $x^{{read}}_i \\ne x_i$; the difference is
what step 4 subtracts. An idle bar's {rows[0][1]:+.4f} table ordinate becomes
${rows[0][1]:.4f}/f$ of the function's unit -- at $f = {scale_all:.3f}$ that is
{rows[0][1] / scale_all:+.4f}, which is why a scaled-down trial pays more for
its idle bars.

**Bars at the ends of the scale are biased, not centred.** A bar set at the
stick zero cannot sit below the pivot, so its setting error is one-sided,
$[0, +{tol:.2f}]$ mm, and on average it stands at $+{tol / 2:.3f}$ mm, not 0;
a bar at the travel stop is the mirror, $[-{tol:.2f}, 0]$, on average at
${nom.d_max - tol / 2:.3f}$ mm. Record those mean stations' table rows -- ordinate (divided by $f$ like
every other) AND $\\kappa$, both from the row at the mean station -- **{at_zero:+.4f}$/f$ for a bar at zero**
(not {rows[0][1]:+.4f}) and, at $f = 1$ only (a scaled trial never reaches the
stop), **{at_stop:+.4f} for a bar at the stop** (not {rows[-1][1]:+.4f}) -- so
the read-vs-set vector of step 4 removes the bias; only the scatter about it
is left, which is what the budget's `station_setting` term scores.

| station (mm) | stick reading (div) | read ordinate $x^{{read}}$ | $\\kappa$ = c2/c1 |
|---:|---:|---:|---:|
{table}

A bar parked at 0 reads {rows[0][1]:+.4f} ({at_zero:+.4f} at its mean set
station): idle channels are NOT zero. Sum the
read ordinates of all 20 bars; that sum is what the machine reports at $k=0$.
The sign is a convention of the machine-hand drive (a +X bar reads negative at
the top of stroke); the coefficients' signs follow it uniformly.

Signed functions: every bar stays on the lifting side, so add a constant $c$
to a signed input before setting the bars; its lift vector ($20c$ at $k=0$,
$-c$ at every odd $k$, $0$ at even $k$) is subtracted in step 4.

**Choose the ordinate scale for the pen first.** The pen's half-stroke is
{cf["readout"]["pen_half_stroke_mm"]:.0f} mm and the $k=0$ reading must span it
(step 3 divides everything by it). At the magnifier's MINIMUM setting -- the
clamp against the bracket collar, {mag["lever_radius_min_mm"]:.0f} mm from the
knife axis -- one full-scale bar moves the pen
{mag["pen_mm_per_full_scale_bar_at_min"]:.2f} mm, so the trial's $k=0$ peak,
$P = \\sum_i t_i\\,(1 + \\kappa_i)$ with $t_i$ the TABLE ordinate at bar $i$'s
set station, undivided ($= f\\,(S + C_2)$ of step 3, in full-scale-bar units;
the pen sees table ordinates, the arithmetic sees them divided by $f$), may be
at most **{mag["ordinate_capacity_full_scale_bars"]:.2f}**
full-scale bars. If the function's samples give $P > {mag["ordinate_capacity_full_scale_bars"]:.2f}$
at full scale, set every bar at $f\\,x_i \\cdot {nom.d_max:.0f}$ mm with the
**largest $f$ for which $P(f) \\le {mag["ordinate_capacity_full_scale_bars"]:.2f}$** --
evaluate $P(f)$ from the table at the scaled stations, NOT by proportion: an
idle bar keeps its {rows[0][1]:+.4f} read ordinate at any $f$, so $P(f)$ is
affine in $f$ (for 20 bars at 1, $P = {p_all[0]:.2f}$ at $f = 1$ and the solve
gives $f = {scale_all:.3f}$, where proportion would say
{mag["ordinate_capacity_full_scale_bars"] / p_all[0]:.3f} and overdrive the
stroke by {100.0 * (p_all[1] / mag["ordinate_capacity_full_scale_bars"] - 1.0):.0f} %).
$f$ is removed by the division in the read ordinates above, so step 3 sees
the function's own units. Broad inputs run at 0.2-0.5 of full scale on this
machine; the stick's +/-{tol:.2f} mm then costs that much more of each
ordinate, which is what the budget's `station_setting` and `knife` terms
carry. Then set the
clamp radius so the peak just fills the stroke:
$R = {mag["lever_radius_min_mm"]:.0f}$ mm $\\times$ {mag["ordinate_capacity_full_scale_bars"]:.2f} $/ P$,
**capped at the as-built {mag["lever_radius_built_mm"]:.0f} mm** (the clamp's
far end; the wheel's rim/hub wire ratio is {mag["wheel_ratio"]:.2f}). A sparse
or small input with $P < {p_min_full:.2f}$ therefore cannot fill the stroke:
its $k=0$ reading is $r_0 = {mag["pen_mm_per_full_scale_bar_at_built"]:.2f}\\,P$ mm
and every reading error in step 3 is $15/r_0$ times larger; scale such an
input UP (multiply every ordinate by a constant, up to the capacity) before
setting the bars -- step 3 removes it like any $f$.

The minimum pose (clamp against the collar) is what every broad input uses
and it is not CAD-gated (error_budget.yaml `waive_minimum_pose`, #748); the
as-built pose is.

$P(f)$ for 20 bars set at $f$ (from the table; check your arithmetic against it):

| $f$ | station (mm) | $P(f)$ |
|---:|---:|---:|
{scale_table}

## 2. Run and read

Crank in ONE direction only (a reversal re-seats every mesh on the other flank).
Take the zero of each trial as the mean line of the trace over one full period.
Read the pen at each $\\theta_k$ to +/-{cf["readout"]["assumed_reading_uncertainty_mm"]:.3f} mm
(half the line width against the grid), the magnifier set as in step 1 so the
$k=0$ reading spans the {cf["readout"]["pen_half_stroke_mm"]:.0f} mm half-stroke
(or the $r_0$ it reaches at the {mag["lever_radius_built_mm"]:.0f} mm cap).

## 3. Normalise

Everything the operator has is in two units: pen readings $r_k$ in mm (off the
mean line, step 2) and read ordinates (step 1, already divided by $f$). From
step 1 form two sums, both in ordinate units:

- $S = \\sum_i x^{{read}}_i$ (what the machine sums at $k=0$),
- $C_2 = \\sum_i x^{{read}}_i\\,\\kappa_i$ (the second-harmonic total riding the
  $k=0$ reading; $\\kappa_i = c_2/c_1$ from the table at each bar's station --
  use the READ ordinate: an idle bar still moves, its term is
  $\\kappa \\cdot x^{{read}} = {rows[0][2] * rows[0][1]:+.4f}$, not zero).

The $k=0$ reading is $r_0 = s\\,(S + C_2)$ for the trial's pen scale $s$
(mm per ordinate unit, set by the magnifier), so

$$s = \\frac{{r_0}}{{S + C_2}}, \\qquad O'_k = \\frac{{r_k}}{{s}}$$

puts every reading in ordinate units (Michelson's normalisation to the
greatest term). Nothing in this step needs a unit the operator does not have.

## 4. Correct

Subtract from every $O'_k$, in ordinate units:

- the second-harmonic term $\\sum_i x^{{read}}_i\\,\\kappa_i \\cos(2 i \\theta_k)$
  (the connecting-rod distortion, 1.4-5 % of each channel's amplitude; at
  $k=0$ it equals $C_2$, so $O'_0 - C_2 = S$ exactly);
- the read-vs-set deviation vector $\\sum_i (x^{{read}}_i - x^{{set}}_i)\\cos(i\\theta_k)$
  with the recorded (bias-corrected, $f$-divided) read ordinates of step 1 --
  for an idle bar $x^{{read}} = {at_zero:+.4f}/f$ against $x^{{set}} = 0$
  ({at_zero:+.4f} at $f = 1$, {at_zero / scale_all:+.4f} at the all-ones
  $f = {scale_all:.3f}$), so this is the null lift ($20\\ell$ at $k=0$,
  $-\\ell$ at odd $k$, $\\ell = {lift:.4f}$ at $f = 1$) plus the one-sided
  setting bias, all over $f$, plus the same for any lift constant $c$ from
  step 1.

The result is $O_k$. This is the arithmetic `check:budget` credits: the model's
`read_coefficients` computes exactly $r_k/s$ minus the second-harmonic term.

## 5. Report

$e_k = (O_k - C_k) / \\max_j |C_j|$ with $C_k$ computed by the same 20-sample
rule, $C_k = \\sum_i x_i \\cos(i k \\pi / 20)$, so quadrature error is never charged
to the hardware. Historical comparison: Michelson & Stratton 1898, about 0.7 %
mean absolute error of the greatest term.
"""


def _main() -> int:
    """CLI: print the report (or ``--json``); exit 1 if the budget does not close."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="emit the report as JSON")
    ap.add_argument(
        "--procedure",
        type=Path,
        metavar="PATH",
        help="write the operating/readout procedure (Markdown) the residual assumes",
    )
    args = ap.parse_args()
    budget = load_budget()
    r = build_report(budget)
    if args.procedure:
        args.procedure.parent.mkdir(parents=True, exist_ok=True)
        args.procedure.write_text(readout_procedure(r, nominal()), encoding="utf-8")
        print(f"wrote {args.procedure}")
        return 0 if not budget_closes(r) else 1
    if args.json:
        print(json.dumps(r, indent=2, default=float))
    else:
        _print_report(r, budget)
        bad = budget_closes(r)
        knife = r["closed_form"]["knife"]
        if not knife["static_balance"] and r["counter_spring_balance_waived"]:
            print(
                "\nWAIVED: counter spring cannot balance the channel preload "
                f"({knife['counter_spring_available_N']:.0f} N available vs "
                f"{knife['counter_spring_needed_N']:.0f} N needed) -- closure is "
                "conditional on resolving the spring pair (tolerance-policy.md)"
            )
        mag = r["closed_form"]["magnifier"]
        if mag["inputs_at_minimum_pose"] and r["minimum_pose_waived"]:
            est = mag["minimum_pose_wire_estimate"]
            print(
                "WAIVED: the magnifier's minimum pose (clamp at "
                f"{mag['lever_radius_min_mm']:.0f} mm from the knife) is not "
                f"CAD-gated; it scores {', '.join(mag['inputs_at_minimum_pose'])} "
                f"(offline straight-wire estimate: hook x {est['hook_x_mm']:.0f}, "
                f"{est['z_clearance_to_rim_face_where_over_ring_mm']:.1f} mm in "
                f"front of the rim ring, "
                f"{est['z_clearance_to_spoke_face_where_over_spokes_mm']:.1f} mm in "
                "front of the spokes) -- closure is conditional on #748"
            )
        print("\nBUDGET:", "closes" if not bad else "; ".join(bad))
    return 0 if not budget_closes(r) else 1


if __name__ == "__main__":
    sys.exit(_main())
