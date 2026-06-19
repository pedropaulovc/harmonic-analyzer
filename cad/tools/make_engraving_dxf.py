"""Traced outlines -> the two engraving DXFs, in build plate millimetres.

Maps the traced lettering (extract_engraving.py) into the build coordinate frame
used by build_nameplate.py (corner origin, plate 100 x 55), and emits:

  * nameplate-engraving.dxf -- the smoothed lettering + ornament, centred in the
    field, cut into the recessed field floor;
  * nameplate-border.dxf    -- the pinstripe frame (a thin rounded-rectangle
    band) that rings the field, cut shallow on the raised border.

Two files because the two engravings sit on different surfaces (field floor vs
raised border) and so take different cut depths. Each is one-closed-loop-per-
ring, smooth; build_nameplate.py imports + cuts each.

Offline asset generator (run after extract_engraving.py)::

    uv run --with ezdxf --with shapely cad/tools/make_engraving_dxf.py
"""
from __future__ import annotations

import pickle
from pathlib import Path

import ezdxf
from shapely.affinity import affine_transform
from shapely.geometry import box

ASSETS = Path(__file__).resolve().parent.parent / "assets"
PKL = ASSETS / "nameplate-engraving.pkl"

# Plate + layout (must match build_nameplate.py).
W, H = 100.0, 55.0
TW, TH = 80.0, 36.0        # field lettering envelope (mm)
PCX, PCY = 50.0, 27.5      # plate centre (corner-origin build frame)
# Pinstripe frame: a thin rounded-rect band on the raised border, ringing the
# field close to its edge (p.71).
P_INSET, P_WIDTH, P_RADIUS = 6.0, 0.7, 3.5


def _rrect(inset, rr):
    """Rounded rectangle inset `inset` from the plate edge, corner radius `rr`,
    centred on the plate (corner-origin frame)."""
    bw, bh = W - 2 * inset - 2 * rr, H - 2 * inset - 2 * rr
    cx, cy = PCX, PCY
    return box(cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2).buffer(rr, join_style=1)


def _write(path, polys):
    doc = ezdxf.new(); doc.units = ezdxf.units.MM
    msp = doc.modelspace()
    n = 0
    for p in polys:
        for ring in [p.exterior, *p.interiors]:
            msp.add_lwpolyline([(float(x), float(y)) for x, y in ring.coords], close=True)
            n += 1
    doc.saveas(path)
    return n


def main():
    geom, (cw, ch) = pickle.loads(PKL.read_bytes())
    geom = affine_transform(geom, [1, 0, 0, -1, 0, ch])     # flip y (image y-down)
    minx, miny, maxx, maxy = geom.bounds
    s = min(TW / (maxx - minx), TH / (maxy - miny))
    cx, cy = (minx + maxx) / 2.0, (miny + maxy) / 2.0
    geom = affine_transform(geom, [s, 0, 0, s, PCX - cx * s, PCY - cy * s])
    letters = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)

    pin = _rrect(P_INSET, P_RADIUS).difference(
        _rrect(P_INSET + P_WIDTH, max(P_RADIUS - P_WIDTH, 0.2)))

    n1 = _write(ASSETS / "nameplate-engraving.dxf", letters)
    n2 = _write(ASSETS / "nameplate-border.dxf", [pin])
    print(f"engraving: {n1} polylines, bounds {tuple(round(v, 2) for v in geom.bounds)}")
    print(f"border:    {n2} polylines (pinstripe inset {P_INSET}, width {P_WIDTH}, r {P_RADIUS})")


if __name__ == "__main__":
    main()
