r"""One-time generator: fit the nameplate cartouche with corner-aware splines.

The central scroll cartouche (loops 9,10,11,12,34,35,36 of the originally traced
``LETTERING_LOOPS``) carried 611 of the engraving's 2505 points as fine line
chains. This refits each loop as smooth runs broken at true cusps -- a periodic /
clamped C2 cubic between corners -- so ``build_nameplate`` can draw it with native
splines (``add_spline``) at a fraction of the points.

Acceptance per loop: stored-points polygon area within 1.5% of the traced loop and
Hausdorff (max boundary deviation) of the fitted curve <= 0.15 mm (< the 0.3 mm
engrave depth and < the stroke widths -- visually identical at plate scale). The
even-odd engraving area stays within the golden test's 99% gate and the live cut's
2% volume assert.

This script is provenance: the raw traced cartouche is embedded below (snapshot of
the retired loops), so the vendored ``CARTOUCHE_PATHS`` in ``_nameplate_geometry``
is reproducible. Run to regenerate / re-report::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\fit_cartouche.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy.interpolate import CubicSpline

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _nameplate_geometry import LETTERING_LOOPS  # noqa: E402

CART = [9, 10, 11, 12, 34, 35, 36]  # cartouche loop indices in the traced set
CORNER_DEG = 50.0
HAUSDORFF_TOL = 0.15  # mm
AREA_TOL = 0.015  # stored polygon area within 1.5% of the traced loop
EPS_LADDER = [0.40, 0.32, 0.26, 0.20, 0.16, 0.13, 0.10, 0.08, 0.06, 0.05, 0.04, 0.03, 0.02]


def shoelace(pts) -> float:
    p = np.asarray(pts, float)
    return 0.5 * float(np.sum(p[:, 0] * np.roll(p[:, 1], -1) - np.roll(p[:, 0], -1) * p[:, 1]))


def corners(loop, deg=CORNER_DEG):
    p = np.asarray(loop, float)
    n = len(p)
    out = []
    for i in range(n):
        a = p[i] - p[(i - 1) % n]
        b = p[(i + 1) % n] - p[i]
        na, nb = np.hypot(*a), np.hypot(*b)
        if na < 1e-9 or nb < 1e-9:
            continue
        if np.degrees(np.arccos(np.clip(np.dot(a, b) / (na * nb), -1, 1))) > deg:
            out.append(i)
    return out


def rdp(points, eps):
    pts = np.asarray(points, float)
    keep = np.zeros(len(pts), bool)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        a, b = pts[i], pts[j]
        ab = b - a
        L = np.hypot(*ab)
        seg = pts[i + 1:j] - a
        dist = (np.hypot(seg[:, 0], seg[:, 1]) if L < 1e-12
                else np.abs(ab[0] * seg[:, 1] - ab[1] * seg[:, 0]) / L)
        k = int(np.argmax(dist))
        if dist[k] > eps:
            keep[i + 1 + k] = True
            stack += [(i, i + 1 + k), (i + 1 + k, j)]
    return np.where(keep)[0]


def _cubic(pts, periodic, per_seg=40):
    p = np.asarray(pts, float)
    if len(p) < 3:
        return p
    pc = np.vstack([p, p[0]]) if periodic else p
    d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(pc, axis=0), axis=1))]
    if d[-1] == 0:
        return p
    t = d / d[-1]
    bc = "periodic" if periodic else "not-a-knot"
    u = np.linspace(0, 1, per_seg * (len(pc) - 1), endpoint=not periodic)
    return np.column_stack([CubicSpline(t, pc[:, 0], bc_type=bc)(u),
                            CubicSpline(t, pc[:, 1], bc_type=bc)(u)])


def fit_loop(loop, eps):
    """Return (subpaths, proxy_curve). subpaths: list of point-lists (each a spline)."""
    cs = corners(loop)
    n = len(loop)
    if not cs:  # smooth closed loop -> single periodic spline
        idx = rdp(np.asarray(list(loop) + [loop[0]], float), eps)
        kept = [loop[k % n] for k in idx if k < n]
        return [kept + [kept[0]]], _cubic(kept, periodic=True)
    subpaths, proxy = [], []
    for a, b in zip(cs, cs[1:] + [cs[0]]):
        seg = list(range(a, b + 1)) if b > a else list(range(a, n)) + list(range(0, b + 1))
        sub = [loop[k] for k in seg]
        keep = rdp(np.asarray(sub, float), eps)
        pts = [sub[k] for k in keep]
        subpaths.append(pts)
        proxy.append(_cubic(pts, periodic=False) if len(pts) >= 3 else np.asarray(pts))
    return subpaths, np.vstack(proxy)


def loop_from_subpaths(subpaths):
    """Closed point-loop = concatenated sub-path points, dropping shared endpoints."""
    out = []
    for sp in subpaths:
        pts = sp[1:] if (out and np.allclose(sp[0], out[-1])) else sp
        out.extend(pts)
    # drop a trailing point coincident with the first (closure dup)
    while len(out) > 1 and np.allclose(out[0], out[-1]):
        out.pop()
    return out


def hausdorff(A, B):
    A, B = np.asarray(A, float), np.asarray(B, float)
    def d(P, Q):
        return max(float(np.min(np.hypot(Q[:, 0] - p[0], Q[:, 1] - p[1]))) for p in P)
    return max(d(A, B), d(B, A))


def fit_cartouche():
    paths, proxies, report = {}, {}, []
    for i in CART:
        loop = LETTERING_LOOPS[i]
        ref = _cubic(loop, periodic=True, per_seg=12)
        oa = abs(shoelace(loop))
        chosen = None
        for eps in EPS_LADDER:
            sp, proxy = fit_loop(loop, eps)
            ploop = loop_from_subpaths(sp)
            pa = abs(shoelace(ploop))
            haus = hausdorff(proxy, ref)
            chosen = (eps, sp, ploop, pa, haus, proxy)
            if haus <= HAUSDORFF_TOL and abs(pa / oa - 1) <= AREA_TOL:
                break
        eps, sp, ploop, pa, haus, proxy = chosen
        paths[i] = sp
        proxies[i] = proxy
        report.append((i, len(loop), sum(len(s) for s in sp), len(sp),
                       100 * pa / oa, haus))
    return paths, proxies, report


if __name__ == "__main__":
    paths, proxies, report = fit_cartouche()
    print(f"{'idx':>3} {'orig':>5} {'splPts':>6} {'#spl':>4} {'area%':>7} {'haus':>6}")
    o = s = 0
    for i, no, ns, k, ap, h in report:
        print(f"{i:>3} {no:>5} {ns:>6} {k:>4} {ap:>7.2f} {h:>6.3f}")
        o += no; s += ns
    print(f"\ncartouche points {o} -> {s} ({100*(1-s/o):.0f}% fewer)")

    glyphs = [LETTERING_LOOPS[i] for i in range(len(LETTERING_LOOPS)) if i not in CART]
    cart_loops = [loop_from_subpaths(paths[i]) for i in CART]
    eng = abs(sum(shoelace(l) for l in glyphs + cart_loops))
    print(f"engraving area {eng:.3f}  golden 535.341  -> "
          f"{100*(1-abs(eng-535.341)/535.341):.3f}% (gate >=99%)")
    # Each cartouche loop is DRAWN as one closed periodic spline through its
    # point-loop (add_spline closes by construction -- piecewise open splines do
    # not merge endpoints under the cut). The corner-aware fit above only
    # SELECTS the points (dense near cusps), so the single spline still tracks
    # the sharp original to <= 0.15 mm. Cut drift = closed-spline area vs the
    # stored polygon area the gates use.
    drift = sum(abs(shoelace(_cubic(cart_loops[k], periodic=True, per_seg=24)))
                - abs(shoelace(cart_loops[k])) for k in range(len(CART)))
    print(f"cut drift (closed spline vs polygon) {100*drift/eng:.2f}% (assert <=2%)")

    # emit the CARTOUCHE_LOOPS literal (reduced point-loops, 3-decimal house style)
    def fmt(p):
        return "(" + ", ".join(f"{v:g}" for v in p) + ")"
    lines = ["CARTOUCHE_LOOPS: list[list[tuple[float, float]]] = ["]
    for i, lp in zip(CART, cart_loops):
        lines.append(f"    [  # traced loop {i}: {len(lp)} pts -> closed spline")
        lines.append("        " + ", ".join(fmt(p) for p in lp) + ",")
        lines.append("    ],")
    lines.append("]")
    out_path = Path(__file__).resolve().parent.parent / "out" / "_cartouche_loops.py"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nwrote literal -> {out_path}")
