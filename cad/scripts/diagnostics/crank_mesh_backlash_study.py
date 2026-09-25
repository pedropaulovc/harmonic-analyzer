"""Measured free play of the crossed 16T:64T crank mesh (SolidWorks-free).

U31 (cone_pivot_post_spec) models the crank-mesh backlash with the
parallel-axis formula B = 0.28 + 2*tan(14.5 deg)*dC = 0.28 + 0.517*dC.  The
pair is crossed (crank machine-z over the 12.52-deg inclined 64T, a true 12.0
deg helix on the 64T), so that coefficient and the 0.28 nominal are
hypotheses.  This script measures them on the exact tooth solids that
``crossed_mesh_study`` builds:

* each gear's material boundary is read from its ``GapLookup`` table (the same
  2048 x 512 (theta, r) grid the voxel study tests against, ~0.0015 mm
  circumferential), extruded along its own axis (the 64T with its helix
  twist) in 0.1 mm slices;
* with the 64T held at a crank phase, the pinion is rotated (``seed_off``)
  and the pair collides when any boundary point of either gear lies inside
  the other's material;
* the two first-contact rotations bracket the free window; its width at the
  16T standard pitch radius is the circular backlash at the MHA-025 pitch
  line -- the reading the drive-train sheet's check 2 takes;
* each case is swept over one crank tooth pitch (22.5 deg) and reports the
  tight spot (min) and the loose spot (max).

Cases perturb one term at a time from the shipped pose: centre-distance slack
(``extra`` in ``y_for_extra``), 64T tooth thinning (``widen64``) and 16T
thinning (``widen16``).  Results append to a JSONL checkpoint, one line per
(case, phase), so a rerun resumes where a crash stopped.

Run (no SolidWorks)::

    uv run python cad/scripts/diagnostics/crank_mesh_backlash_study.py \
        --out C:/src/dt-logs/crank-mesh-backlash.jsonl
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

import crossed_mesh_study as cms

dta = cms.dta
GEAR64_SEAT = np.array(cms.GEAR64_SEAT)
U = np.array([cms.SIN_I, 0.0, cms.COS_I])  # 64T axis
EX = np.array([cms.COS_I, 0.0, -cms.SIN_I])
EY = np.array([0.0, 1.0, 0.0])
TAN_SKEW = math.tan(math.radians(cms.HELIX_DEG))
SLICE_MM = 0.1
PITCH16 = 22.5


def boundary(g: cms.GapLookup) -> tuple[np.ndarray, np.ndarray]:
    """(theta, r) of every material cell with a non-material neighbour."""
    mat = ~g.table
    # The tip-circle row lies ON each gap polygon's rim arc, where
    # contains_points is ambiguous (it reads material across the gaps); take
    # the row just inside it.
    mat[:, -1] = mat[:, -2]
    edge = np.zeros_like(mat)
    edge |= mat & ~np.roll(mat, 1, axis=0)
    edge |= mat & ~np.roll(mat, -1, axis=0)
    edge[:, :-1] |= mat[:, :-1] & ~mat[:, 1:]
    edge[:, 1:] |= mat[:, 1:] & ~mat[:, :-1]
    edge[:, -1] |= mat[:, -1]  # the tip circle
    edge[:, 0] = False  # solid hub below every gap floor
    ti, ri = np.nonzero(edge)
    theta = ti * g.gamma / g.nth
    r = g.rmin + ri * (g.ra - g.rmin) / (g.nr - 1)
    return theta, r


class Pose:
    """The pair at one (extra, widen16, widen64, crank phase)."""

    def __init__(self, extra: float, widen16: float, widen64: float,
                 crank_deg: float, lut: dict) -> None:
        self.y_crank = cms.y_for_extra(extra)
        key16 = (16, widen16, cms.ROOT16)
        key64 = (64, widen64, cms.ROOT64)
        if key16 not in lut:
            lut[key16] = cms.GapLookup(16, cms.DP_CRANK, widen16, cms.ROOT16)
        if key64 not in lut:
            lut[key64] = cms.GapLookup(64, cms.DP_CRANK, widen64, cms.ROOT64)
        self.g16, self.g64 = lut[key16], lut[key64]
        self.crank = math.radians(crank_deg)
        self.z0 = cms.PINION_TOOTH_Z - cms.PINION_FACE / 2.0
        # The seed the voxel study places at seed_off = 0 (tooth-in-gap
        # formula for this centre distance).
        dx16 = (GEAR64_SEAT[0] - cms.X_CRANK) * cms.COS_I
        dy16 = self.y_crank - cms.Y_DRIVE
        alpha64 = math.degrees(math.atan2(dy16, dx16))
        alpha16 = math.degrees(math.atan2(dy16, GEAR64_SEAT[0] - cms.X_CRANK))
        tp64 = 360.0 / 64.0
        delta64 = round(alpha64 / tp64) * tp64 - alpha64
        self.seed0 = ((alpha16 + 180.0) - delta64 * (cms.R64 / cms.R16)
                      - PITCH16 / 2.0) % PITCH16
        self._pinion_local()
        self._gear_world()

    def _pinion_local(self) -> None:
        th, r = boundary(self.g16)
        gamma = self.g16.gamma
        # Every pinion tooth; points far from the 64T are culled per test.
        ths = np.concatenate([th + k * gamma for k in range(16)])
        rs = np.tile(r, 16)
        near = rs > self.g16.ra - 3.0 * cms.ADD16  # the toothed annulus only
        self.p_th, self.p_r = ths[near], rs[near]
        zs = np.arange(0.0, cms.PINION_FACE + 1e-9, SLICE_MM)
        self.p_z = zs

    def _gear_world(self) -> None:
        th, r = boundary(self.g64)
        gamma = self.g64.gamma
        pts = []
        for s in np.arange(-cms.GEAR64_FACE / 2.0, cms.GEAR64_FACE / 2.0 + 1e-9, SLICE_MM):
            for k in range(64):
                phi = th + k * gamma - self.crank / 4.0 + s * TAN_SKEW / cms.R64
                p = (GEAR64_SEAT + s * U)[None, :] + (
                    (r * np.cos(phi))[:, None] * EX + (r * np.sin(phi))[:, None] * EY
                )
                d = np.hypot(p[:, 0] - cms.X_CRANK, p[:, 1] - self.y_crank)
                pz = p[:, 2] - self.z0
                keep = (d <= self.g16.ra + 0.05) & (pz >= -0.05) & (pz <= cms.PINION_FACE + 0.05)
                if keep.any():
                    pts.append(p[keep])
        self.gear_pts = np.concatenate(pts) if pts else np.zeros((0, 3))

    def _in64(self, p: np.ndarray) -> np.ndarray:
        rel = p - GEAR64_SEAT
        s = rel @ U
        radial = rel - np.outer(s, U)
        r = np.linalg.norm(radial, axis=1)
        th = np.arctan2(radial @ EY, radial @ EX) + self.crank / 4.0 - s * TAN_SKEW / cms.R64
        return (np.abs(s) <= cms.GEAR64_FACE / 2.0) & self.g64.material(th, r)

    def collides(self, seed_off: float) -> bool:
        rot = math.radians(self.seed0 + seed_off) - self.crank
        # Pinion boundary -> world; test in the 64T.
        phi = self.p_th - rot
        x = cms.X_CRANK + self.p_r * np.cos(phi)
        y = self.y_crank + self.p_r * np.sin(phi)
        rel = np.stack([x, y], axis=1)
        # Cull to points within reach of the 64T teeth before extruding.
        d64 = np.hypot(x - GEAR64_SEAT[0], y - GEAR64_SEAT[1])
        near = d64 <= self.g64.ra + 1.5  # the inclined 64T's plan reach
        rel = rel[near]
        n = len(rel)
        zs = self.z0 + self.p_z
        p = np.empty((n * len(zs), 3))
        p[:, 0] = np.repeat(rel[:, 0], len(zs))
        p[:, 1] = np.repeat(rel[:, 1], len(zs))
        p[:, 2] = np.tile(zs, n)
        if self._in64(p).any():
            return True
        # 64T boundary -> pinion frame; test in the pinion.
        g = self.gear_pts
        px, py = g[:, 0] - cms.X_CRANK, g[:, 1] - self.y_crank
        pz = g[:, 2] - self.z0
        pth = np.arctan2(py, px) + rot
        in16 = (pz >= 0) & (pz <= cms.PINION_FACE) & self.g16.material(pth, np.hypot(px, py))
        return bool(in16.any())


def edge(pose: Pose, free: float, step: float, tol: float = 0.001) -> float | None:
    """First colliding seed_off from ``free`` in the direction of ``step``."""
    lo, hi = free, free + step
    for _ in range(40):
        if pose.collides(hi):
            break
        lo, hi = hi, hi + step
    else:
        return None
    while abs(hi - lo) > tol:
        mid = (lo + hi) / 2.0
        if pose.collides(mid):
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2.0


def window(pose: Pose, guess: float) -> dict:
    free = guess
    if pose.collides(free):
        grid = np.arange(-6.0, 6.0 + 1e-9, 0.05) + guess
        frees = [g for g in grid if not pose.collides(float(g))]
        if not frees:
            return {"jam": True}
        free = float(np.median(frees))
    neg = edge(pose, free, -0.25)
    pos = edge(pose, free, +0.25)
    if neg is None or pos is None:
        return {"jam": False, "open": True}
    width = pos - neg
    return {
        "jam": False,
        "neg_deg": neg,
        "pos_deg": pos,
        "width_deg": width,
        "backlash_mm": math.radians(width) * cms.R16,
        "centre_deg": (pos + neg) / 2.0,
    }


CASES: list[tuple[str, float, float, float]] = [
    # (name, extra, widen16, widen64)
    ("nominal", 0.25, 0.0, 0.15),
    *[(f"cd{e:+.3f}", 0.25 + e, 0.0, 0.15) for e in (-0.15, -0.075, 0.075, 0.15, 0.30)],
    *[(f"thin64={w:.2f}", 0.25, 0.0, w) for w in (0.05, 0.10, 0.20, 0.25)],
    *[(f"thin16={w:.3f}", 0.25, w, 0.15) for w in (0.02, 0.05)],
    ("cd-0.15,thin64=0.05", 0.10, 0.0, 0.05),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--phases", type=int, default=9)
    ap.add_argument("--case", action="append", help="run only these case names")
    ap.add_argument(
        "--custom", action="append", default=[],
        help="extra case NAME:EXTRA:WIDEN16:WIDEN64 (run instead of the built-ins)",
    )
    args = ap.parse_args()
    cases = CASES
    if args.custom:
        cases = []
        for spec in args.custom:
            name, extra, w16, w64 = spec.split(":")
            cases.append((name, float(extra), float(w16), float(w64)))
    done: set[tuple[str, float]] = set()
    if args.out.exists():
        for line in args.out.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            done.add((rec["case"], rec["crank_deg"]))
    lut: dict = {}
    phases = np.linspace(0.0, PITCH16, args.phases, endpoint=False)
    centre = dta.MESH_WINDOW_CENTRE_DEG
    for name, extra, w16, w64 in cases:
        if args.case and name not in args.case:
            continue
        guess = centre
        for ph in phases:
            if (name, float(ph)) in done:
                continue
            t0 = time.perf_counter()
            pose = Pose(extra, w16, w64, float(ph), lut)
            res = window(pose, guess)
            if "centre_deg" in res:
                guess = res["centre_deg"]
            rec = {"case": name, "extra": extra, "widen16": w16, "widen64": w64,
                   "crank_deg": float(ph), "seconds": round(time.perf_counter() - t0, 1),
                   **res}
            with args.out.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec) + "\n")
            print(json.dumps(rec), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
