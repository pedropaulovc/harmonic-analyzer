"""Offline CadQuery preview of the engraved nameplate -> STL + raking-light PNG.

A throwaway cross-check of build_nameplate.py that DOES run off-Windows (the real
build is SolidWorks-only): same dims, rounded corners, and the SAME engravings
the vendored DXFs carry (lettering + pinstripe border, read straight back from
cad/assets/*.dxf). Regenerates cad/assets/nameplate-engraving-preview.png and
double-checks the committed DXFs.

    uv run --with cadquery --with ezdxf --with shapely --with matplotlib \
           --with numpy-stl cad/tools/preview_nameplate.py
"""
from __future__ import annotations

from pathlib import Path

import cadquery as cq
import ezdxf
import numpy as np
from cadquery import Face, Solid, Vector, Wire
from shapely.affinity import translate
from shapely.geometry import Polygon

ASSETS = Path(__file__).resolve().parent.parent / "assets"
W, H, T = 100.0, 55.0, 1.5
BORDER, RECESS, ENGRAVE, CORNER_R = 8.0, 0.4, 0.3, 3.0
top = T / 2.0


def _rings(dxf):
    return [[(p[0], p[1]) for p in pl.get_points()]
            for pl in ezdxf.readfile(dxf).modelspace().query("LWPOLYLINE")]


def _nest(rings):
    """Two-level nest (each counter sits directly in one glyph) -> shapely faces."""
    polys = sorted((Polygon(r) for r in rings if len(r) >= 3), key=lambda p: p.area, reverse=True)
    faces = []
    for poly in polys:
        rep = poly.representative_point()
        for f in faces:
            if f[0].contains(rep):
                f[1].append(poly); break
        else:
            faces.append([poly, []])
    return [Polygon(o.exterior.coords, [h.exterior.coords for h in hs]) for o, hs in faces]


def _centred(polys):
    return [translate(p, -W / 2, -H / 2) for p in polys]      # corner-origin -> centred box


def _wire(coords):
    return Wire.makePolygon([Vector(float(x), float(y), top) for x, y in list(coords)[:-1]], close=True)


def _solids(polys, depth):
    out = []
    for p in polys:
        f = Face.makeFromWires(_wire(p.exterior.coords), [_wire(r.coords) for r in p.interiors])
        out.append(Solid.extrudeLinear(f, Vector(0, 0, -depth)))
    return out


def _fuse(solids):
    s = solids[0]
    for x in solids[1:]:
        s = s.fuse(x)
    return s


def build():
    plate = cq.Workplane("XY").box(W, H, T).edges("|Z").fillet(CORNER_R)
    plate = plate.faces(">Z").workplane().rect(W - 2 * BORDER, H - 2 * BORDER).cutBlind(-RECESS)
    # lettering: cut through the recess air into the field floor
    letters = _solids(_centred(_nest(_rings(ASSETS / "nameplate-engraving.dxf"))), RECESS + ENGRAVE)
    plate = plate.cut(cq.Workplane(obj=_fuse(letters)))
    # pinstripe frame: shallow groove on the raised border
    border = _solids(_centred(_nest(_rings(ASSETS / "nameplate-border.dxf"))), ENGRAVE)
    plate = plate.cut(cq.Workplane(obj=_fuse(border)))
    pts = [(x, y) for x in (-(W / 2 - 4.5), W / 2 - 4.5) for y in (-(H / 2 - 4.5), H / 2 - 4.5)]
    plate = plate.faces(">Z").workplane().pushPoints(pts).hole(2.6)
    return plate


def render(stl, ppm=18):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from stl import mesh as stlmesh
    tris = stlmesh.Mesh.from_file(stl).vectors.astype(float)
    x0, y0 = -W / 2, -H / 2
    Wp, Hp = int(W * ppm), int(H * ppm); Z = np.full((Hp, Wp), -1e9)
    for t in tris:
        px = [(p[0] - x0) * ppm for p in t]; py = [(p[1] - y0) * ppm for p in t]
        ax, bx = max(int(min(px)), 0), min(int(max(px)) + 1, Wp - 1)
        ay, by = max(int(min(py)), 0), min(int(max(py)) + 1, Hp - 1)
        if ax >= bx or ay >= by:
            continue
        xs, ys = np.meshgrid(np.arange(ax, bx + 1), np.arange(ay, by + 1))
        d = (py[1] - py[2]) * (px[0] - px[2]) + (px[2] - px[1]) * (py[0] - py[2])
        if abs(d) < 1e-9:
            continue
        u = ((py[1] - py[2]) * (xs - px[2]) + (px[2] - px[1]) * (ys - py[2])) / d
        v = ((py[2] - py[0]) * (xs - px[2]) + (px[0] - px[2]) * (ys - py[2])) / d
        ins = (u >= -1e-6) & (v >= -1e-6) & (u + v <= 1 + 1e-6)
        z = u * t[0][2] + v * t[1][2] + (1 - u - v) * t[2][2]
        sub = Z[ay:by + 1, ax:bx + 1]; np.maximum(sub, np.where(ins, z, -1e9), out=sub)
    bg = Z < -1e8; zf = np.where(bg, np.nan, Z)
    gy, gx = np.gradient(np.nan_to_num(zf, nan=np.nanmin(zf)) * ppm)
    n = 1 / np.sqrt(gx * gx + gy * gy + 1)
    sh = np.clip(0.32 + 0.68 * np.clip((-gx * n) * -0.55 + (-gy * n) * -0.5 + n * 0.66, 0, 1), 0, 1)
    img = np.clip(sh[..., None] * np.array([0.84, 0.68, 0.33]), 0, 1)
    img = np.where(bg[..., None], 1.0, img)
    plt.figure(figsize=(13, 7.2)); plt.imshow(np.flipud(img)); plt.axis("off")
    plt.tight_layout(); plt.savefig(ASSETS / "nameplate-engraving-preview.png", dpi=150, bbox_inches="tight")


if __name__ == "__main__":
    stl = "/tmp/nameplate_preview.stl"
    p = build()
    print("volume", round(p.val().Volume(), 1), "mm^3")
    cq.exporters.export(p, stl, tolerance=0.008, angularTolerance=0.08)
    render(stl)
    print("wrote", ASSETS / "nameplate-engraving-preview.png")
