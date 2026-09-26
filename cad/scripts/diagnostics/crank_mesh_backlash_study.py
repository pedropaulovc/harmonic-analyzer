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
from dataclasses import dataclass, replace
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
SLICE_MM = 0.1
PITCH16 = 22.5
IN = cms.IN
DEDENDUM_FACTOR = 1.157  # root depth below pitch, in cutter addenda (ROOT16/ROOT64)


@dataclass(frozen=True)
class GearDef:
    """One gear's tooth definition.

    ``definition`` says which plane carries the cutter's DP and PA:
    ``"transverse"`` is the shipped CAD convention (the 64T's transverse
    section is the pinion's profile, twisted); ``"normal"`` is what a form
    or fly cutter set over at the helix angle cuts (the normal section is
    the cutter's profile, the transverse DP is ``dp_n * cos(beta)`` and the
    transverse PA ``atan(tan(pa_n) / cos(beta))``). The tooth depth is the
    cutter's either way.
    """

    teeth: int
    beta_deg: float = 0.0
    dp_n: float = cms.DP_CRANK
    pa_n: float = cms.PA_DEG
    definition: str = "transverse"

    @property
    def dp_t(self) -> float:
        if self.definition == "transverse":
            return self.dp_n
        return self.dp_n * math.cos(math.radians(self.beta_deg))

    @property
    def pa_t(self) -> float:
        if self.definition == "transverse":
            return self.pa_n
        return math.degrees(math.atan(
            math.tan(math.radians(self.pa_n)) / math.cos(math.radians(self.beta_deg))))

    @property
    def addendum_extra_in(self) -> float:
        return 1.0 / self.dp_n - 1.0 / self.dp_t

    @property
    def rp(self) -> float:
        return self.teeth / self.dp_t / 2.0 * IN

    @property
    def root(self) -> float:
        return self.rp - DEDENDUM_FACTOR * IN / self.dp_n

    @property
    def twist_per_mm(self) -> float:
        """Rotation (rad) of the tooth per mm along the gear's own axis."""
        return math.tan(math.radians(self.beta_deg)) / self.rp

    def lookup(self, widen: float, lut: dict) -> cms.GapLookup:
        key = (self.teeth, self.dp_t, self.pa_t, self.addendum_extra_in, widen, self.root)
        if key not in lut:
            lut[key] = cms.GapLookup(self.teeth, self.dp_t, widen, self.root,
                                     pa_deg=self.pa_t,
                                     addendum_extra_in=self.addendum_extra_in)
        return lut[key]


SHIPPED16 = GearDef(16)
SHIPPED64 = GearDef(64, cms.HELIX_DEG)
assert math.isclose(SHIPPED16.rp, cms.R16) and math.isclose(SHIPPED64.rp, cms.R64)
assert math.isclose(SHIPPED16.root, cms.ROOT16) and math.isclose(SHIPPED64.root, cms.ROOT64)


def y_for_extra(extra: float, g16: GearDef, g64: GearDef) -> float:
    """Crank-axle height for a centre distance of R64 + R16 + ``extra``."""
    dxh = (GEAR64_SEAT[0] - cms.X_CRANK) * cms.COS_I
    c2c = g64.rp + g16.rp + extra
    return cms.Y_DRIVE + math.sqrt(c2c * c2c - dxh * dxh)


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
    """The pair at one (extra, widen16, widen64, crank phase, gear definitions).

    Both helices twist about mid-face: the 64T by ``s * twist`` (s along its
    axis from the seat), the pinion by ``(z - face/2) * twist16`` (z from its
    tooth-row start). ``hand16`` picks the pinion's hand (``--hand-check``).
    """

    def __init__(self, extra: float, widen16: float, widen64: float,
                 crank_deg: float, lut: dict, gear16: GearDef = SHIPPED16,
                 gear64: GearDef = SHIPPED64, hand16: float = 1.0,
                 skew64: bool = False, yaw16_deg: float = 0.0,
                 tilt16_deg: float = 0.0) -> None:
        self.gear16, self.gear64 = gear16, gear64
        # A misaligned crank bore: the pinion axis turned about the pinion's
        # mid-face centre -- ``yaw16`` about machine y (the plan angle against
        # the cone journal), ``tilt16`` about machine x (out of the horizontal)
        # -- so the centre distance at mid-face is unchanged and only the
        # angular error is measured.
        ya, ti = math.radians(yaw16_deg), math.radians(tilt16_deg)
        ry = np.array([[math.cos(ya), 0.0, math.sin(ya)], [0.0, 1.0, 0.0],
                       [-math.sin(ya), 0.0, math.cos(ya)]])
        rx = np.array([[1.0, 0.0, 0.0], [0.0, math.cos(ti), -math.sin(ti)],
                       [0.0, math.sin(ti), math.cos(ti)]])
        self.rot16 = ry @ rx
        # The shop's straight skewed slot instead of a true helix: each
        # mid-face point runs along its own tangent (w = s * tan(beta))
        # rather than around the pitch cylinder, so it stands off radially
        # by ~w^2 / 2r at the face ends -- the flank-line sag.
        self.skew64 = skew64
        self.tan64 = math.tan(math.radians(gear64.beta_deg))
        self.y_crank = y_for_extra(extra, gear16, gear64)
        self.g16 = gear16.lookup(widen16, lut)
        self.g64 = gear64.lookup(widen64, lut)
        self.twist64 = gear64.twist_per_mm
        self.twist16 = hand16 * gear16.twist_per_mm
        self.crank = math.radians(crank_deg)
        self.z0 = cms.PINION_TOOTH_Z - cms.PINION_FACE / 2.0
        self.pivot16 = np.array([cms.X_CRANK, self.y_crank, self.z0 + cms.PINION_FACE / 2.0])
        # The seed the voxel study places at seed_off = 0 (tooth-in-gap
        # formula for this centre distance); a 64T angle is 64/16 pinion
        # angles whatever the pitch radii.
        dx16 = (GEAR64_SEAT[0] - cms.X_CRANK) * cms.COS_I
        dy16 = self.y_crank - cms.Y_DRIVE
        alpha64 = math.degrees(math.atan2(dy16, dx16))
        alpha16 = math.degrees(math.atan2(dy16, GEAR64_SEAT[0] - cms.X_CRANK))
        tp64 = 360.0 / 64.0
        delta64 = round(alpha64 / tp64) * tp64 - alpha64
        self.seed0 = ((alpha16 + 180.0) - delta64 * (64.0 / 16.0)
                      - PITCH16 / 2.0) % PITCH16
        self._pinion_local()
        self._gear_world()

    def _pinion_local(self) -> None:
        th, r = boundary(self.g16)
        gamma = self.g16.gamma
        # Every pinion tooth; points far from the 64T are culled per test.
        ths = np.concatenate([th + k * gamma for k in range(16)])
        rs = np.tile(r, 16)
        near = rs > self.g16.ra - 3.0 * IN / self.gear16.dp_n  # the toothed annulus only
        self.p_th, self.p_r = ths[near], rs[near]
        self.p_z = np.arange(0.0, cms.PINION_FACE + 1e-9, SLICE_MM)

    def _gear_world(self) -> None:
        th, r = boundary(self.g64)
        gamma = self.g64.gamma
        pts = []
        for s in np.arange(-cms.GEAR64_FACE / 2.0, cms.GEAR64_FACE / 2.0 + 1e-9, SLICE_MM):
            for k in range(64):
                if self.skew64:
                    w = s * self.tan64
                    phi = th + k * gamma - self.crank / 4.0 + np.arctan2(w, r)
                    rr = np.hypot(r, w)
                else:
                    phi = th + k * gamma - self.crank / 4.0 + s * self.twist64
                    rr = r
                p = (GEAR64_SEAT + s * U)[None, :] + (
                    (rr * np.cos(phi))[:, None] * EX + (rr * np.sin(phi))[:, None] * EY
                )
                loc = self._to_pinion(p)
                d = np.hypot(loc[:, 0], loc[:, 1])
                pz = loc[:, 2]
                keep = (d <= self.g16.ra + 0.05) & (pz >= -0.05) & (pz <= cms.PINION_FACE + 0.05)
                if keep.any():
                    pts.append(p[keep])
        self.gear_pts = np.concatenate(pts) if pts else np.zeros((0, 3))

    def _in64(self, p: np.ndarray) -> np.ndarray:
        rel = p - GEAR64_SEAT
        s = rel @ U
        radial = rel - np.outer(s, U)
        r = np.linalg.norm(radial, axis=1)
        th = np.arctan2(radial @ EY, radial @ EX) + self.crank / 4.0
        if self.skew64:
            w = s * self.tan64
            r0 = np.sqrt(np.maximum(r * r - w * w, 0.0))
            th = th - np.arctan2(w, r0)
            r = r0
        else:
            th = th - s * self.twist64
        return (np.abs(s) <= cms.GEAR64_FACE / 2.0) & self.g64.material(th, r)

    def _to_pinion(self, p: np.ndarray) -> np.ndarray:
        """World points -> pinion frame (x, y about its axis, z from its tooth-row start)."""
        loc = (p - self.pivot16) @ self.rot16
        loc[:, 2] += cms.PINION_FACE / 2.0
        return loc

    def _pinion_twist(self, z_local: np.ndarray) -> np.ndarray:
        return (z_local - cms.PINION_FACE / 2.0) * self.twist16

    def collides(self, seed_off: float) -> bool:
        rot = math.radians(self.seed0 + seed_off) - self.crank
        # Pinion boundary -> world; test in the 64T.
        phi = (self.p_th[:, None] - rot) + self._pinion_twist(self.p_z)[None, :]
        r = np.broadcast_to(self.p_r[:, None], phi.shape)
        lx = r * np.cos(phi)
        ly = r * np.sin(phi)
        lz = np.broadcast_to(self.p_z[None, :] - cms.PINION_FACE / 2.0, phi.shape)
        # Cull to points within reach of the 64T teeth (in the pinion frame,
        # which a sub-degree misalignment barely moves).
        near = np.hypot(lx + cms.X_CRANK - GEAR64_SEAT[0], ly + self.y_crank - GEAR64_SEAT[1]) <= (
            self.g64.ra + 1.5
        )
        loc = np.stack([lx[near], ly[near], lz[near]], axis=1)
        p = self.pivot16 + loc @ self.rot16.T
        if self._in64(p).any():
            return True
        # 64T boundary -> pinion frame; test in the pinion.
        g = self._to_pinion(self.gear_pts)
        px, py, pz = g[:, 0], g[:, 1], g[:, 2]
        pth = np.arctan2(py, px) + rot - self._pinion_twist(pz)
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
        "backlash_mm": math.radians(width) * pose.gear16.rp,
        "centre_deg": (pos + neg) / 2.0,
    }


@dataclass(frozen=True)
class Case:
    name: str
    extra: float = 0.25
    widen16: float = 0.0
    widen64: float = 0.15
    gear16: GearDef = SHIPPED16
    gear64: GearDef = SHIPPED64
    hand16: float = 1.0
    skew64: bool = False
    yaw16: float = 0.0
    tilt16: float = 0.0

    def record(self) -> dict:
        return {
            "case": self.name, "extra": self.extra, "widen16": self.widen16,
            "widen64": self.widen64, "hand16": self.hand16, "skew64": self.skew64,
            "yaw16": self.yaw16, "tilt16": self.tilt16,
            **{f"g16_{k}": v for k, v in _gear_record(self.gear16).items()},
            **{f"g64_{k}": v for k, v in _gear_record(self.gear64).items()},
        }


def _gear_record(g: GearDef) -> dict:
    return {"beta": g.beta_deg, "def": g.definition, "dp_n": g.dp_n, "pa_n": g.pa_n,
            "dp_t": g.dp_t, "pa_t": g.pa_t, "rp": g.rp}


CASES: list[Case] = [
    Case("nominal"),
    *[Case(f"cd{e:+.3f}", extra=0.25 + e) for e in (-0.15, -0.075, 0.075, 0.15, 0.30)],
    *[Case(f"thin64={w:.2f}", widen64=w) for w in (0.05, 0.10, 0.20, 0.25)],
    *[Case(f"thin16={w:.3f}", widen16=w) for w in (0.02, 0.05)],
    Case("cd-0.15,thin64=0.05", extra=0.10, widen64=0.05),
]

GEAR_KEYS = {"b16": "beta_deg", "b64": "beta_deg", "def16": "definition",
             "def64": "definition", "dpn16": "dp_n", "dpn64": "dp_n",
             "pan16": "pa_n", "pan64": "pa_n"}


def parse_case(spec: str) -> Case:
    """``NAME:key=value,...`` over the shipped case.

    Keys: extra, w16, w64, hand16 (+1/-1), skew64 (1: straight skewed slots), yaw16, tilt16
    (crank-axis misalignment, deg), b16, b64 (helix deg), def16, def64 (transverse|normal),
    dpn16, dpn64 (cutter DP), pan16, pan64 (cutter PA).
    """
    name, _, body = spec.partition(":")
    fields: dict = {}
    g16: dict = {}
    g64: dict = {}
    for item in filter(None, body.split(",")):
        key, value = item.split("=")
        if key in ("extra", "w16", "w64", "hand16", "yaw16", "tilt16"):
            fields[{"w16": "widen16", "w64": "widen64"}.get(key, key)] = float(value)
            continue
        if key == "skew64":
            fields["skew64"] = value == "1"
            continue
        target = g16 if key.endswith("16") else g64
        attr = GEAR_KEYS[key]
        target[attr] = value if attr == "definition" else float(value)
    return Case(name, **fields,
                gear16=replace(SHIPPED16, **g16), gear64=replace(SHIPPED64, **g64))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--phases", type=int, default=9)
    ap.add_argument("--case", action="append", help="run only these case names")
    ap.add_argument(
        "--custom", action="append", default=[],
        help="extra case NAME:key=value,... (run instead of the built-ins; see parse_case)",
    )
    args = ap.parse_args()
    cases = [parse_case(spec) for spec in args.custom] or CASES
    done: set[tuple[str, float]] = set()
    if args.out.exists():
        for line in args.out.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            done.add((rec["case"], rec["crank_deg"]))
    lut: dict = {}
    phases = np.linspace(0.0, PITCH16, args.phases, endpoint=False)
    centre = dta.MESH_WINDOW_CENTRE_DEG
    for case in cases:
        if args.case and case.name not in args.case:
            continue
        guess = centre
        for ph in phases:
            if (case.name, float(ph)) in done:
                continue
            t0 = time.perf_counter()
            pose = Pose(case.extra, case.widen16, case.widen64, float(ph), lut,
                        case.gear16, case.gear64, case.hand16, case.skew64,
                        case.yaw16, case.tilt16)
            res = window(pose, guess)
            if "centre_deg" in res:
                guess = res["centre_deg"]
            rec = {**case.record(), "crank_deg": float(ph),
                   "seconds": round(time.perf_counter() - t0, 1), **res}
            with args.out.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec) + "\n")
            print(json.dumps(rec), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
