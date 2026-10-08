"""Analytic crossed-axis interference study: 16T crank-pinion vs 64T crank-drive.

SolidWorks-free repro for the 2026-07-14 crank-mesh rederivation ("crank-pinion
and crank-drive gear are not meshing in model") -- the study behind
``gear_train.crank_drive_backlash_mm``, ``fits.crank_mesh.c2c_slack_mm`` and
the drive-train's ``MESH16_C2C`` / ``Y_CRANK`` / ``MESH_WINDOW_CENTRE_DEG``
constants. It builds the exact modeled tooth solids -- the involute gap
profile of ``involute_gear.gear_facts`` with the ``_gear.py`` widen /
root-relief extensions, the 64T's teeth twisted as the TRUE helix
``build_crank_drive_gear`` sweeps (``slices`` optionally quantizes to the
retired K-slice cut stack) -- places them on live pure-data cone/spec geometry
without importing a build script, COM helpers, or measured crank-stack guards.
The pinion's turned band is preserved (SHOULDER_LENGTH / TURNED_DIA, the
cut ``build_crank_pinion`` revolves), and voxel-computes the pair's
intersection volume.

The CLI reports nominal, seed-pose-margin, or helix-hand studies at the current
configured crank height and cone incline. Supply the newly measured
``--seed-off`` explicitly; the default is the raw tooth-in-gap formula, not a
historical zero-window centre. Collision reports are measurements, not a
replacement for the assembly's safety gates.

Run (no SolidWorks)::

    uv run python cad/scripts/diagnostics/crossed_mesh_study.py
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path as FilePath

import numpy as np
from matplotlib.path import Path

# Import only pure geometry/spec contracts: assembly/build modules also load
# COM helpers and measured crank-stack assertions, unsuitable for remeasurement.
sys.path.insert(0, str(FilePath(__file__).resolve().parents[1]))
import cone_line
import dt_crank_drive_gear_spec as gear64_spec
import dt_crank_pinion_spec as pinion_spec
from dt_cone_pivot_post_installation import GEAR_AXIS_SHIFT
from dt_cone_pivot_post_spec import CRANK_BOSS_START_Z

IN = 25.4
DEDENDUM_FACTOR = gear64_spec.DEDENDUM_FACTOR
NORMAL_MODULE_MM = gear64_spec.NORMAL_MODULE_MM
PA_DEG = pinion_spec.PRESSURE_ANGLE_DEG
PA64_T = gear64_spec.PRESSURE_ANGLE_DEG
BACKLASH_MM = gear64_spec.BACKLASH_MM
HELIX_DEG = cone_line.INCLINE_DEG
DP_CRANK = gear64_spec.DIAMETRAL_PITCH
DP_CRANK_CUTTER = gear64_spec.CUTTER_DIAMETRAL_PITCH
LONG_ADDENDUM64_MM = gear64_spec.LONG_ADDENDUM_MM
ADDENDUM64_EXTRA_IN = 1.0 / DP_CRANK_CUTTER - 1.0 / DP_CRANK + LONG_ADDENDUM64_MM / IN
# Same face/station construction as the assembly, without its measured guards.
GEAR64_STATION = (
    cone_line.SHAFT_T120_STATION
    - (cone_line.CONE_FACE_STATION_REFERENCE + 10.0) / 2.0 - 0.1
)
GEAR64_SEAT = cone_line.cone_station(
    GEAR64_STATION + GEAR_AXIS_SHIFT + gear64_spec.CENTRE_SHIFT_NORTH
)
GEAR64_FACE = gear64_spec.FACE_WIDTH
PINION_FACE = pinion_spec.FACE_WIDTH
X_CRANK, Y_CRANK = cone_line.X_CRANK, cone_line.Y_CRANK
SHIPPED_AXIS = (X_CRANK, Y_CRANK)
Y_DRIVE = cone_line.Y_DRIVE
SIN_I, COS_I = cone_line.SIN_I, cone_line.COS_I
INCLINE_DEG = cone_line.INCLINE_DEG
R64, R16 = gear64_spec.PITCH_DIA / 2.0, pinion_spec.PITCH_DIA / 2.0
ADD16 = NORMAL_MODULE_MM
SLACK = math.hypot((GEAR64_SEAT[0] - X_CRANK) * COS_I, Y_CRANK - Y_DRIVE) - R64 - R16
PINION_TOOTH_Z = (
    cone_line.cone_station(cone_line.POST_STATION)[2] - CRANK_BOSS_START_Z
    + pinion_spec.SEAT_FEELER_MM + PINION_FACE / 2.0
)
PINION_SHOULDER = pinion_spec.SHOULDER_LENGTH
PINION_TURNED_R = pinion_spec.TURNED_DIA / 2.0


def gear_facts(teeth: int, dp: float, pa_deg: float, *,
               addendum_extra_in: float = 0.0) -> dict[str, float]:
    """Pure transverse facts, matching involute_gear's inch-based equations.

    Keep both polygon and lookup on the same facts without importing the
    authoring module's _common/COM/watchdog dependencies.
    """
    pa = math.radians(pa_deg)
    rb = teeth / dp * math.cos(pa) / 2.0
    ra = (teeth + 2.0) / dp / 2.0 + addendum_extra_in
    tmax = math.sqrt((ra / rb) ** 2 - 1.0)
    thickness = math.pi / (2.0 * dp)
    delta = thickness * dp / teeth + math.tan(pa) - pa
    gamma = 2.0 * math.pi / teeth
    return {"Rb": rb, "Ra": ra, "Tmax": tmax, "Delta": delta, "Gamma": gamma}


def gap_polygon(teeth: int, dp: float, root_r_mm: float | None = None,
                widen_mm: float = 0.0, samples: int = 400, *,
                pa_deg: float = PA_DEG, addendum_extra_in: float = 0.0) -> np.ndarray:
    """One tooth-gap polygon (mm): the exact ``_gear.cut_tooth_gap`` boundary.

    ``widen_mm`` is the symmetric flank backlash (circumferential, at pitch
    radius); the mirrored lower flank takes the offset with the OPPOSITE
    phase sign (its azimuth is the negated phase), exactly as the live curve
    literals do. ``pa_deg`` and ``addendum_extra_in`` pass through to
    ``gear_facts`` (a normal-defined helical gear's transverse profile).
    """
    f = gear_facts(teeth, dp, pa_deg, addendum_extra_in=addendum_extra_in)
    rp = teeth / dp / 2.0 * IN
    rb, ra = f["Rb"] * IN, f["Ra"] * IN
    tmax, delta, gamma = f["Tmax"], f["Delta"], f["Gamma"]
    eps = (widen_mm / 2.0) / rp
    if root_r_mm is not None and (not math.isfinite(root_r_mm) or root_r_mm <= 0):
        raise ValueError("gear root radius must be positive and finite")
    u0 = (math.sqrt((root_r_mm / rb) ** 2 - 1.0)
          if root_r_mm is not None and root_r_mm > rb else 0.0)
    if u0 >= tmax:
        raise ValueError("gear root must leave a nonzero involute below the tip")
    th_l = math.atan(tmax) - tmax + delta - eps
    th_u = tmax - math.atan(tmax) - delta + gamma + eps
    pts: list[tuple[float, float]] = []
    for i in range(samples + 1):  # lower flank A1->B1, rotated -eps
        t = u0 + (tmax - u0) * i / samples
        ph = t - delta + eps
        pts.append((rb * (math.cos(ph) + t * math.sin(ph)),
                    rb * (t * math.cos(ph) - math.sin(ph))))
    for i in range(1, samples + 1):  # rim arc B1->B2 at Ra
        th = th_l + (th_u - th_l) * i / samples
        pts.append((ra * math.cos(th), ra * math.sin(th)))
    for i in range(1, samples + 1):  # upper flank reversed B2->A2, rotated +eps
        t = u0 + (tmax - u0) * (samples - i) / samples
        ph = t - delta + gamma + eps
        pts.append((rb * (math.cos(ph) + t * math.sin(ph)),
                    rb * (math.sin(ph) - t * math.cos(ph))))
    foot_inv = u0 - math.atan(u0)
    a1, a2 = delta - foot_inv - eps, gamma - delta + foot_inv + eps
    if root_r_mm is None:  # base chord A2->A1 (the stock floor)
        for i in range(1, samples):
            s = i / samples
            pts.append((rb * ((1 - s) * math.cos(a2) + s * math.cos(a1)),
                        rb * ((1 - s) * math.sin(a2) + s * math.sin(a1))))
    else:  # radial in, root arc, radial out (the root-relieved floor)
        rr = root_r_mm
        if rr < rb:
            pts.append((rr * math.cos(a2), rr * math.sin(a2)))
        for i in range(1, samples):
            th = a2 + (a1 - a2) * i / samples
            pts.append((rr * math.cos(th), rr * math.sin(th)))
        if rr < rb:
            pts.append((rr * math.cos(a1), rr * math.sin(a1)))
    return np.array(pts)


class GapLookup:
    """Vectorized material test on a fine (theta mod Gamma, r) grid."""

    def __init__(self, teeth: int, dp: float, widen_mm: float = 0.0,
                 root_r_mm: float | None = None, *, pa_deg: float = PA_DEG,
                 addendum_extra_in: float = 0.0):
        f = gear_facts(teeth, dp, pa_deg, addendum_extra_in=addendum_extra_in)
        self.gamma = f["Gamma"]
        self.ra = f["Ra"] * IN
        self.rmin = (root_r_mm if root_r_mm is not None
                     else f["Rb"] * IN * math.cos((f["Gamma"] - 2 * f["Delta"]) / 2.0) * 0.999)
        poly = Path(gap_polygon(teeth, dp, root_r_mm, widen_mm, pa_deg=pa_deg,
                                addendum_extra_in=addendum_extra_in))
        self.nth, self.nr = 2048, 512
        th = np.linspace(0.0, self.gamma, self.nth, endpoint=False)
        rr = np.linspace(self.rmin, self.ra, self.nr)
        tg, rg = np.meshgrid(th, rr, indexing="ij")
        pts = np.stack([rg * np.cos(tg), rg * np.sin(tg)], axis=-1).reshape(-1, 2)
        ingap = poly.contains_points(pts)
        tg2 = tg + self.gamma  # wrap coverage: the gap straddles theta = gamma
        pts2 = np.stack([rg * np.cos(tg2), rg * np.sin(tg2)], axis=-1).reshape(-1, 2)
        ingap |= poly.contains_points(pts2)
        self.table = ingap.reshape(self.nth, self.nr)

    def material(self, theta: np.ndarray, r: np.ndarray) -> np.ndarray:
        inside = r <= self.ra
        below = r < self.rmin  # solid hub below every gap floor
        thm = np.mod(theta, self.gamma)
        ti = np.clip((thm / self.gamma * self.nth).astype(int), 0, self.nth - 1)
        ri = np.clip(((r - self.rmin) / (self.ra - self.rmin) * (self.nr - 1)).astype(int),
                     0, self.nr - 1)
        return inside & ~(self.table[ti, ri] & ~below)


def pinion_material(
    g16: GapLookup, theta: np.ndarray, r: np.ndarray, z: np.ndarray
) -> np.ndarray:
    """16T material at pinion-frame (theta, r, z), z from the toothed south face.

    The shipped solid: full-OD teeth over the shoulder, turned down to
    ``PINION_TURNED_DIA`` north of it, nothing past ``PINION_FACE``.
    """
    turned = (z > PINION_SHOULDER) & (r > PINION_TURNED_R)
    return (z >= 0) & (z <= PINION_FACE) & ~turned & g16.material(theta, r)


ROOT16 = R16 - DEDENDUM_FACTOR * NORMAL_MODULE_MM
ROOT64 = R64 - DEDENDUM_FACTOR * NORMAL_MODULE_MM


def pose(axis: tuple[float, float], seed_off: float = 0.0) -> dict[str, float]:
    """Centre distance and tooth-in-gap seed of a 16T on crank ``axis``
    (machine x, y), by the assembly's own contact-azimuth formula."""
    x_crank, y_crank = axis
    dx16 = (GEAR64_SEAT[0] - x_crank) * COS_I
    dy16 = y_crank - Y_DRIVE
    alpha64 = math.degrees(math.atan2(dy16, dx16))
    alpha16 = math.degrees(math.atan2(dy16, GEAR64_SEAT[0] - x_crank))
    tp64 = 360.0 / 64.0
    delta64 = round(alpha64 / tp64) * tp64 - alpha64
    seed = ((alpha16 + 180.0) - delta64 * (64.0 / 16.0) - 22.5 / 2.0
            ) % 22.5 + seed_off
    return {"c2c": math.hypot(dx16, dy16), "seed": seed}


def frame_axis(extra: float) -> tuple[float, float]:
    """The frame crank axis lifted to a centre distance of R64 + R16 + extra."""
    return X_CRANK, y_for_extra(extra)


def study(axis: tuple[float, float], skew_deg: float = HELIX_DEG, widen16: float = 0.0,
          widen64: float = BACKLASH_MM, root16: float | None = ROOT16,
          root64: float | None = ROOT64, crank_deg: float = 0.0,
          slices: int = 0, vox: float = 0.06, seed_off: float = 0.0,
          lut: dict | None = None) -> dict[str, float]:
    """Voxel intersection of the pair with the 16T on crank ``axis``.

    ``axis`` is explicit: ``SHIPPED_AXIS`` for the pose the assembly ships,
    ``frame_axis(extra)`` for the frame-axis rederivation.  ``crank_deg``
    spins the pinion (+about machine z) with the 64T coupled at -1/4 about its
    own axis (external mesh) -- the verify:kinematics sweep.  ``slices``
    quantizes the helix twist to the buildable K slice cuts (0 = continuous).
    """
    if lut is None:
        lut = {}
    u = np.array([SIN_I, 0.0, COS_I])
    ex = np.array([COS_I, 0.0, -SIN_I])
    ey = np.array([0.0, 1.0, 0.0])
    g = np.array(GEAR64_SEAT)

    x_crank, y_crank = axis
    placed = pose(axis, seed_off)
    c2c, seed = placed["c2c"], placed["seed"]
    # Axial placement: the shipped station. It is anchored to the STATIC
    # casting-to-T120 span (see the assembly's span-fit assert), not to the
    # contact azimuth, so it does not move with the y_crank sweeps here.
    pinion_tooth_z = PINION_TOOTH_Z

    k16 = (16, widen16, root16)
    k64 = (64, widen64, root64)
    if k16 not in lut:
        lut[k16] = GapLookup(16, DP_CRANK_CUTTER, widen16, root16, pa_deg=PA_DEG)
    if k64 not in lut:
        lut[k64] = GapLookup(64, DP_CRANK, widen64, root64, pa_deg=PA64_T,
                             addendum_extra_in=ADDENDUM64_EXTRA_IN)
    g16, g64 = lut[k16], lut[k64]

    xs = np.arange(x_crank - g16.ra - 0.3, x_crank + g16.ra + 0.3, vox)
    y_lo = min(y_crank - g16.ra, Y_DRIVE + g64.ra - 4.0) - 0.3
    ys = np.arange(y_lo, Y_DRIVE + g64.ra + 0.3, vox)
    zs = np.arange(pinion_tooth_z - PINION_FACE / 2 - 0.3,
                   pinion_tooth_z + PINION_FACE / 2 + 0.3, vox)
    X, Y, Z = np.meshgrid(xs, ys, zs, indexing="ij")
    P = np.stack([X, Y, Z], axis=-1).reshape(-1, 3)

    px, py = P[:, 0] - x_crank, P[:, 1] - y_crank
    pth = np.arctan2(py, px) + math.radians(seed - crank_deg)
    pz = P[:, 2] - (pinion_tooth_z - PINION_FACE / 2.0)
    in16 = pinion_material(g16, pth, np.hypot(px, py), pz)

    rel = P - g
    s = rel @ u
    radial = rel - np.outer(s, u)
    r = np.linalg.norm(radial, axis=1)
    th = np.arctan2(radial @ ey, radial @ ex) + math.radians(crank_deg * 16.0 / 64.0)
    if skew_deg:
        sq = s
        if slices:
            edges = np.linspace(-GEAR64_FACE / 2.0, GEAR64_FACE / 2.0, slices + 1)
            centers = (edges[:-1] + edges[1:]) / 2.0
            idx = np.clip(((s + GEAR64_FACE / 2.0) / GEAR64_FACE * slices).astype(int),
                          0, slices - 1)
            sq = centers[idx]
        th = th - (sq * math.tan(math.radians(skew_deg))) / R64
    in64 = (np.abs(s) <= GEAR64_FACE / 2.0) & g64.material(th, r)

    vol = float((in16 & in64).sum()) * vox ** 3
    return {"c2c": c2c, "seed": seed, "vol_mm3": vol,
            "interleave": (g16.ra + g64.ra) - c2c, "ptz": pinion_tooth_z}


def y_for_extra(extra: float) -> float:
    dxh = (GEAR64_SEAT[0] - X_CRANK) * COS_I
    c2c = R64 + R16 + extra
    return Y_DRIVE + math.sqrt(c2c * c2c - dxh * dxh)


def worst_over_phase(widen: float, axis: tuple[float, float], k: int, lut: dict,
                     phases: int = 9, vox: float = 0.06,
                     seed_off: float = 0.0) -> float:
    w = 0.0
    for ph in np.linspace(0.0, 22.5, phases):
        w = max(w, study(axis, skew_deg=HELIX_DEG, widen64=widen,
                         root16=ROOT16, root64=ROOT64, crank_deg=float(ph),
                         slices=k, vox=vox, seed_off=seed_off,
                         lut=lut)["vol_mm3"])
        if w > 0.05:
            break
    return w


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", choices=("nominal", "pose", "hand"), default="nominal")
    ap.add_argument("--phases", type=int, default=9)
    ap.add_argument("--seed-off", type=float, default=0.0,
                    help="measured seed offset in degrees; default is uncentred tooth-in-gap")
    ap.add_argument("--dx", type=float, default=0.0)
    ap.add_argument("--dy", type=float, default=0.0)
    ap.add_argument("--vox", type=float, default=0.06)
    args = ap.parse_args()
    if args.phases < 1 or args.vox <= 0:
        ap.error("phases and voxel size must be positive")
    axis = (X_CRANK + args.dx, Y_CRANK + args.dy)
    variants = [(HELIX_DEG, args.seed_off, BACKLASH_MM, "nominal")]
    if args.suite == "hand":
        variants += [(-HELIX_DEG, args.seed_off, BACKLASH_MM, "mirrored"),
                     (0.0, args.seed_off, BACKLASH_MM, "straight")]
    elif args.suite == "pose":
        variants += [(HELIX_DEG, args.seed_off + delta, BACKLASH_MM, f"seed{delta:+g}")
                     for delta in (-0.4, 0.4)]
        variants += [(HELIX_DEG, args.seed_off, BACKLASH_MM - 0.05, "thin64-0.05")]
    lut: dict = {}
    ok = True
    for helix, seed, thinning, label in variants:
        worst = 0.0
        for phase in np.linspace(0.0, 22.5, args.phases, endpoint=False):
            result = study(axis, skew_deg=helix, crank_deg=float(phase),
                           widen64=thinning, seed_off=seed, vox=args.vox, lut=lut)
            worst = max(worst, result["vol_mm3"])
            print({"case": label, "crank_deg": float(phase), **result}, flush=True)
        threshold = 0.02 if label.startswith("seed") else 0.0005
        passed = worst >= 0.02 if label in ("mirrored", "straight") else worst < threshold
        ok &= passed
        print({"case": label, "worst_mm3": worst, "passed": passed}, flush=True)
    print("PASS" if ok else "FAIL: crank mesh study criteria not met", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
