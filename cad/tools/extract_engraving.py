"""Trace the nameplate engraving from the book photo into smoothed vector
outlines (shapely), pickled for make_engraving_dxf.py.

Source: the p.71 macro of the Wm. Gaertner & Co. nameplate from the public book
"Albert Michelson's Harmonic Analyzer" (engineerguy.com), vendored beside this
script as ``cad/assets/nameplate-source.jpg``. The engraving is bright polished
brass on a blackened field, so it segments cleanly by local-adaptive threshold;
the border / screws (which touch the crop edge) and speckle are dropped, the
central ornament band is closed + hole-filled so the cartouche lens reads as the
solid engraved pad the maker intended (not the century of tarnish in the photo).

This is an OFFLINE asset generator, not part of the SolidWorks build. Run it
(then make_engraving_dxf.py) only to regenerate cad/assets/nameplate-engraving.dxf
from the photo. Heavy deps, kept out of the build venv::

    uv run --with pillow --with numpy --with scipy --with opencv-python-headless \
           --with shapely cad/tools/extract_engraving.py
"""
from __future__ import annotations

import pickle
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from shapely.geometry import Polygon
from shapely.ops import unary_union

ASSETS = Path(__file__).resolve().parent.parent / "assets"
SRC = ASSETS / "nameplate-source.jpg"
OUT_PKL = ASSETS / "nameplate-engraving.pkl"
CROP = (0.085, 0.93, 0.14, 0.86)      # fractional plate window the photo shows


def _adaptive(F, r=55, c=12):
    """Local-mean adaptive threshold (integral image): bright engraving vs field."""
    P = np.pad(F, ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    h, w = F.shape
    ys = np.arange(h); xs = np.arange(w)
    a = np.clip(ys - r, 0, h); b = np.clip(ys + r + 1, 0, h)
    u = np.clip(xs - r, 0, w); d = np.clip(xs + r + 1, 0, w)
    A0, U0 = np.meshgrid(a, u, indexing="ij"); B1, D1 = np.meshgrid(b, d, indexing="ij")
    mean = (P[B1, D1] - P[A0, D1] - P[B1, U0] + P[A0, U0]) / ((B1 - A0) * (D1 - U0))
    return F > mean + c


def _clean(F):
    """Threshold, drop border-touching components + speckle, seal the ornament band."""
    mask = _adaptive(F)
    lab, n = ndi.label(mask)
    border = (set(np.unique(lab[0])) | set(np.unique(lab[-1]))
              | set(np.unique(lab[:, 0])) | set(np.unique(lab[:, -1])))
    keep = np.ones(n + 1, bool); keep[0] = False
    for i in border:
        keep[i] = False
    m = keep[lab]
    lab2, n2 = ndi.label(m)
    sz = ndi.sum(np.ones_like(lab2), lab2, range(1, n2 + 1))
    m = np.array([False] + [s >= 600 for s in sz])[lab2]
    rows = m.sum(1); on = rows > m.shape[1] * 0.01
    e = np.where(np.diff(on.astype(int)) != 0)[0]
    bands = list(zip(e[::2] + 1, e[1::2] + 1))
    bands = sorted(sorted(bands, key=lambda b: b[1] - b[0], reverse=True)[:3], key=lambda b: b[0])
    orn = bands[1]                                   # middle of title/ornament/subtitle
    seal = ndi.binary_fill_holes(ndi.binary_closing(m[orn[0]:orn[1]], iterations=4))
    m[orn[0]:orn[1]] = seal
    return m, orn


def _smooth(contour, win=9, eps=0.6):
    """De-jag a pixel contour: periodic moving-average (kills the 1px staircase),
    then a light Douglas-Peucker decimation. Smooth curves, corners preserved."""
    p = contour.reshape(-1, 2).astype(float)
    n = len(p)
    if n < 2 * win:
        return p.astype(np.float32)
    k = np.ones(win) / win
    pad = np.r_[p[-win:], p, p[:win]]
    x = np.convolve(pad[:, 0], k, "same")[win:win + n]
    y = np.convolve(pad[:, 1], k, "same")[win:win + n]
    s = np.c_[x, y].astype(np.float32)
    return cv2.approxPolyDP(s, eps, True).reshape(-1, 2)


def _vectorize(m, orn):
    """findContours (RETR_CCOMP) -> smoothed shapely faces with counters; ornament solid."""
    cnts, hier = cv2.findContours((m * 255).astype(np.uint8),
                                  cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    hier = hier[0]
    simp = _smooth
    raw = []
    for i, c in enumerate(cnts):
        if hier[i][3] != -1 or cv2.contourArea(c) < 200:
            continue
        outer = simp(c)
        if len(outer) < 3:
            continue
        cy = outer[:, 1].mean()
        holes = []
        if not (orn[0] <= cy <= orn[1]):            # keep letter counters; solid lens
            j = hier[i][2]
            while j != -1:
                if cv2.contourArea(cnts[j]) >= 120:
                    h = simp(cnts[j])
                    if len(h) >= 3:
                        holes.append(h)
                j = hier[j][0]
        p = Polygon(outer, holes)
        p = p if p.is_valid else p.buffer(0)
        if p.area > 0:
            raw.append(p)
    big = [p for p in raw if p.area > 8000]         # drop corner-noise outliers
    xs = [v for p in big for v in p.bounds[::2]]; ys = [v for p in big for v in p.bounds[1::2]]
    bx0, bx1, by0, by1 = min(xs) - 70, max(xs) + 70, min(ys) - 70, max(ys) + 70
    faces = [p for p in raw if bx0 <= p.centroid.x <= bx1 and by0 <= p.centroid.y <= by1]
    return unary_union(faces)


def main():
    im = Image.open(SRC).convert("L")
    A = np.asarray(im, float); H, W = A.shape
    fx0, fx1, fy0, fy1 = CROP
    F = A[int(fy0 * H):int(fy1 * H), int(fx0 * W):int(fx1 * W)]
    m, orn = _clean(F)
    geom = _vectorize(m, orn)
    ch, cw = m.shape
    OUT_PKL.write_bytes(pickle.dumps((geom, (cw, ch))))
    print(f"area frac {geom.area / (cw * ch):.3f}  parts {len(getattr(geom, 'geoms', [1]))}"
          f"  -> {OUT_PKL}")


if __name__ == "__main__":
    main()
