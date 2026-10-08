"""Analytic crossed-axis interference study: 16T crank-pinion vs 64T crank-drive.

SolidWorks-free repro for the 2026-07-14 crank-mesh rederivation ("crank-pinion
and crank-drive gear are not meshing in model") -- the study behind
``gear_train.crank_drive_backlash_mm``, ``fits.crank_mesh.c2c_slack_mm`` and
the drive-train's ``MESH16_C2C`` / ``Y_CRANK`` / ``MESH_WINDOW_CENTRE_DEG``
constants. It builds the exact modeled tooth solids -- the involute gap
profile of ``involute_gear.gear_facts`` with the ``_gear.py`` widen /
root-relief extensions, the 64T's teeth twisted as the TRUE helix
``build_crank_drive_gear`` sweeps (``slices`` optionally quantizes to the
retired K-slice cut stack) -- places them on the live drive-train geometry
(constants imported from ``build_drive_train_assembly``, never mirrored) at
the shipped axial placement (``PINION_TOOTH_Z`` -- the pinion proud of the
pivot-post casting face, spanning the 64T row; ch12 page002_img06), with the
pinion's turned band (``crank_pinion_spec`` SHOULDER_LENGTH / TURNED_DIA, the
cut ``build_crank_pinion`` revolves), and voxel-computes the pair's
intersection volume.

Findings it reproduces (run it after changing any crank-mesh input):

* the retired PEN16 radial backoff left the tip circles 0.29 mm APART -- the
  user-flagged air gap -- and no straight-tooth pose can engage (the crossing
  manifests as lateral flank misregistration, +-1.08 mm across the face);
* helix hand: +INCLINE on the 64T zeroes the collision; the mirrored hand and
  straight teeth both collide hard at the engaged depth;
* the restored fixed-axis pose (user ruling 2026-09-28), with 0.15 tooth
  thinning and the 6.5-wide 64T, has a nine-phase common seed-offset interval
  approximately [-2.776, -0.206] deg in ``crank_mesh_backlash_study``.
  The shipped -1.49 offset retains over 0.4-degree margin each way; minimum
  measured nominal backlash is 0.3476 mm. The print-worst closing stack is
  separate (``crank_mesh_stack``) and requires only positive backlash.

Run (no SolidWorks)::

    uv run python cad/scripts/diagnostics/crossed_mesh_study.py
"""
from __future__ import annotations

import math
import sys

import numpy as np
from matplotlib.path import Path

import _common  # noqa: F401  -- resolves to diagnostics/_common.py, the import
# shim that inserts the parent cad/scripts onto sys.path and re-exports the
# real _common (every diag_*/probe_* script here relies on it)
import build_dt_drive_train_assembly as dta
from _gear import gap_area_in_disc_ext  # noqa: F401  (re-exported for callers)
from involute_gear import gear_facts
from build_dt_crank_drive_gear import BACKLASH_MM, HELIX_DEG
from dt_crank_drive_gear_spec import DEDENDUM_FACTOR, NORMAL_MODULE_MM
from dt_crank_drive_gear_spec import LONG_ADDENDUM_MM as LONG_ADDENDUM64_MM
from dt_crank_drive_gear_spec import PRESSURE_ANGLE_DEG as PA64_T  # transverse
from dt_crank_pinion_spec import PRESSURE_ANGLE_DEG as PA_DEG  # normal, straight 16T
from dt_crank_pinion_spec import SHOULDER_LENGTH as PINION_SHOULDER
from dt_crank_pinion_spec import TURNED_DIA as PINION_TURNED_DIA

IN = 25.4
DP_CRANK = dta.DP_CRANK
# One standard full-depth normal-plane cutter for the pair: the 16T's DP
# and the 64T's normal DP, with no additional long addendum.
DP_CRANK_CUTTER = dta.DP_CRANK_CUTTER
ADDENDUM64_EXTRA_IN = 1.0 / DP_CRANK_CUTTER - 1.0 / DP_CRANK + LONG_ADDENDUM64_MM / IN
GEAR64_SEAT = dta.GEAR64_SEAT
GEAR64_FACE = dta.GEAR64_FACE
PINION_FACE = dta.PINION_FACE
# The restored post carries the fixed crank axis; both studies and the
# assembly use this same placement.
X_CRANK = dta.X_CRANK
SHIPPED_AXIS = (dta.X_CRANK, dta.Y_CRANK)
Y_DRIVE = dta.Y_DRIVE
SIN_I, COS_I = dta.SIN_I, dta.COS_I
INCLINE_DEG = dta.INCLINE_DEG
R64, R16, ADD16 = dta.R64, dta.R16, dta.ADD16
SLACK = math.hypot((GEAR64_SEAT[0] - dta.X_CRANK) * COS_I, dta.Y_CRANK - Y_DRIVE) - R64 - R16
PINION_TOOTH_Z = dta.PINION_TOOTH_Z
# The turned band build_dt_crank_pinion revolve-cuts: north of the full-OD
# shoulder (pinion z > PINION_SHOULDER from the toothed south face) the teeth
# stop at PINION_TURNED_DIA.
PINION_TURNED_R = PINION_TURNED_DIA / 2.0


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
    rb, ra = f["Rb"] * IN, f["Ra"] * IN
    tmax, delta, gamma = f["Tmax"], f["Delta"], f["Gamma"]
    rp = teeth / dp / 2.0 * IN
    eps = (widen_mm / 2.0) / rp
    th_l, th_u = f["ThetaL"] - eps, f["ThetaU"] + eps
    pts: list[tuple[float, float]] = []
    for i in range(samples + 1):  # lower flank A1->B1, rotated -eps
        t = tmax * i / samples
        ph = t - delta + eps
        pts.append((rb * (math.cos(ph) + t * math.sin(ph)),
                    rb * (t * math.cos(ph) - math.sin(ph))))
    for i in range(1, samples + 1):  # rim arc B1->B2 at Ra
        th = th_l + (th_u - th_l) * i / samples
        pts.append((ra * math.cos(th), ra * math.sin(th)))
    for i in range(1, samples + 1):  # upper flank reversed B2->A2, rotated +eps
        t = tmax * (samples - i) / samples
        ph = t - delta + gamma + eps
        pts.append((rb * (math.cos(ph) + t * math.sin(ph)),
                    rb * (math.sin(ph) - t * math.cos(ph))))
    a1, a2 = delta - eps, gamma - delta + eps
    if root_r_mm is None:  # base chord A2->A1 (the stock floor)
        for i in range(1, samples):
            s = i / samples
            pts.append((rb * ((1 - s) * math.cos(a2) + s * math.cos(a1)),
                        rb * ((1 - s) * math.sin(a2) + s * math.sin(a1))))
    else:  # radial in, root arc, radial out (the root-relieved floor)
        rr = root_r_mm
        pts.append((rr * math.cos(a2), rr * math.sin(a2)))
        for i in range(1, samples):
            th = a2 + (a1 - a2) * i / samples
            pts.append((rr * math.cos(th), rr * math.sin(th)))
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


def study(axis: tuple[float, float], skew_deg: float = 0.0, widen16: float = 0.0,
          widen64: float = 0.0, root16: float | None = None,
          root64: float | None = None, crank_deg: float = 0.0,
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
    lut: dict = {}
    print(f"i={INCLINE_DEG:.4f}  R64={R64:.3f} R16={R16:.3f}  std c2c={R64 + R16:.3f}  "
          f"live: slack {SLACK} backlash {BACKLASH_MM} smooth helix {HELIX_DEG:.4f}")

    print("\n== the retired straight-tooth backoff (air gap) ==", flush=True)
    r = study((X_CRANK, 144.96))  # the pre-rederive frame Y_CRANK
    print(f"old pose: c2c {r['c2c']:.3f}, tip interleave {r['interleave']:+.3f} "
          f"(NEGATIVE = the tips never touch), vol {r['vol_mm3']:.3f}")

    # The frame-axis rederivation: lifting the frame axis to the frame slack
    # lands on the casting's Y_CRANK (the assembly asserts the same c2c).  No
    # seed is shipped there, so only the centre distance is checked.
    assert abs(y_for_extra(SLACK) - dta.Y_CRANK) < 0.05, (
        f"y_for_extra({SLACK}) = {y_for_extra(SLACK)} drifted from Y_CRANK "
        f"{dta.Y_CRANK}")

    # The assembly ships the seed at the zero-window CENTRE, not the raw
    # formula (dta.MESH_WINDOW_CENTRE_DEG); model the same offset everywhere.
    off = dta.MESH_WINDOW_CENTRE_DEG
    shipped_slack = pose(SHIPPED_AXIS)["c2c"] - R64 - R16

    print("\n== helix hand at the shipped depth ==", flush=True)
    for skew, label in ((HELIX_DEG, "+helix (shipped)"),
                        (-HELIX_DEG, "mirrored hand"), (0.0, "straight teeth")):
        r = study(SHIPPED_AXIS, skew_deg=skew, widen64=BACKLASH_MM,
                  root16=ROOT16, root64=ROOT64, seed_off=off, lut=lut)
        print(f"{label:20s}: vol {r['vol_mm3']:8.3f} mm^3")

    print("\n== the shipped pose over a crank-pitch phase sweep ==", flush=True)
    # Pin the study's derived pose to the assembly's shipped constants -- a
    # drift here means the study is validating a pose the build doesn't ship.
    live = study(SHIPPED_AXIS, skew_deg=HELIX_DEG, widen64=BACKLASH_MM,
                 root16=ROOT16, root64=ROOT64, seed_off=off, lut=lut)
    assert abs(live["ptz"] - dta.PINION_TOOTH_Z) < 1e-9, (
        f"study placement {live['ptz']} != assembly PINION_TOOTH_Z "
        f"{dta.PINION_TOOTH_Z}")
    assert abs(live["seed"] - dta.PINION_SEED_DEG) < 1e-9, (
        f"study seed {live['seed']} != assembly PINION_SEED_DEG "
        f"{dta.PINION_SEED_DEG}")
    assert abs(live["c2c"] - dta.CRANK_ACTUAL_C2C) < 1e-9, (
        f"study c2c {live['c2c']} != assembly CRANK_ACTUAL_C2C {dta.CRANK_ACTUAL_C2C}")
    w = worst_over_phase(BACKLASH_MM, SHIPPED_AXIS, 0, lut, seed_off=off)
    print(f"backlash {BACKLASH_MM} c2c +{shipped_slack:.3f} smooth: worst {w:.4f} mm^3")
    wm = worst_over_phase(BACKLASH_MM - 0.05, SHIPPED_AXIS, 0, lut, seed_off=off)
    print(f"margin (backlash -0.05):                worst {wm:.4f} mm^3")
    # Seed-window margin: the shipped centre must clear +-0.4 deg of authoring
    # wander in BOTH directions -- 4x the 0.10-deg bound the assembly's
    # authoring-time measure-and-correct block enforces (the interference gate
    # guards the real pose; this guards the margin).
    for so in (off - 0.4, off + 0.4):
        wm2 = worst_over_phase(BACKLASH_MM, SHIPPED_AXIS, 0, lut,
                               phases=5, seed_off=so)
        print(f"margin (seed {so - off:+.1f} deg):                 "
              f"worst {wm2:.4f} mm^3")
        assert wm2 < 0.02, (
            f"seed window margin lost at {so - off:+.1f} deg: {wm2:.4f} mm^3")
    ok = w < 0.0005
    print("\nPASS" if ok else "\nFAIL: shipped pose no longer zero-collision")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
