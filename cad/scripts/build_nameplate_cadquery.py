r"""CadQuery stand-in for ``build_nameplate.py`` (book ch. 26, pp. 70-71).

The production part is authored against the SolidWorks MCP adapter, which needs
a live SolidWorks session. This module reproduces the *same* nameplate geometry
with CadQuery so the engraved plate can be built, exported (STEP/STL) and
rendered head-less -- the offline proof that the DXF-re-imported engraving
(``_nameplate_geometry.LETTERING_LOOPS``) cuts a VALID solid, not just that its
analytic area matches (which ``test_nameplate_geometry`` already guards).

Geometry mirrors ``build_nameplate`` exactly (lengths in mm):
  * Rounded-corner brass slab 100 x 55 x 1.5, decorated face on top (z = 0,
    body extruded to z = -1.5).
  * Central field sunk 0.4 (the raised border), the even-odd engraving region
    (lettering + scroll cartouche) incised a further 0.3 into the field floor,
    the pinstripe band (two concentric rounded rects) incised 0.3 on the border.
  * Four Ø2.6 corner screw through-holes.

Each cut's removed volume is asserted against the SAME analytic target
``build_nameplate`` checks on the live seat (engraving area x depth, etc.), so a
green run here is the SolidWorks build's boolean-overlap proof reproduced offline.

Run::

    /home/user/cqenv/bin/python cad/scripts/build_nameplate_cadquery.py
"""

from __future__ import annotations

import math
import sys
from functools import reduce
from pathlib import Path

import cadquery as cq
from cadquery import Face, Solid, Wire
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _nameplate_geometry import BORDER_INNER, BORDER_OUTER, LETTERING_LOOPS

# --- dimensions (kept in sync with build_nameplate.py) -----------------------
PLATE_WIDTH = 100.0
PLATE_HEIGHT = 55.0
PLATE_THICKNESS = 1.5
CORNER_R = 3.0
BORDER_W = 8.0
RECESS_DEPTH = 0.4
ENGRAVE_DEPTH = 0.3
SCREW_DIA = 2.6
SCREW_INSET = 4.5
SCREW_XY = (
    (SCREW_INSET, SCREW_INSET),
    (PLATE_WIDTH - SCREW_INSET, SCREW_INSET),
    (SCREW_INSET, PLATE_HEIGHT - SCREW_INSET),
    (PLATE_WIDTH - SCREW_INSET, PLATE_HEIGHT - SCREW_INSET),
)
TOL = 0.02  # 2% removed-volume tolerance, as build_nameplate uses

OUT = Path(__file__).resolve().parent.parent / "out"


def _rounded_rect_poly(spec):
    """Shapely rounded rectangle from a ``(cx, cy, w, h, r)`` spec."""
    cx, cy, w, h, r = spec
    return box(cx - w / 2 + r, cy - h / 2 + r, cx + w / 2 - r, cy + h / 2 - r).buffer(
        r, quad_segs=32
    )


def _engraving_region():
    """Even-odd ink region of the vendored loops (outer CCW, counters CW)."""
    rings = [Polygon(loop).buffer(0) for loop in LETTERING_LOOPS]
    return reduce(lambda a, b: a.symmetric_difference(b), rings)


def _poly_to_faces(geom):
    """Each shapely (Multi)Polygon -> a CadQuery Face (outer wire + hole wires)."""
    faces = []
    for g in getattr(geom, "geoms", [geom]):
        if g.is_empty:
            continue
        outer = Wire.makePolygon([cq.Vector(x, y, 0) for x, y in g.exterior.coords])
        holes = [
            Wire.makePolygon([cq.Vector(x, y, 0) for x, y in r.coords])
            for r in g.interiors
        ]
        faces.append(Face.makeFromWires(outer, holes))
    return faces


def _cut_tool(geom, depth):
    """A downward (-z) extruded solid of a shapely region, for cutting."""
    solids = [Solid.extrudeLinear(f, cq.Vector(0, 0, -depth)) for f in _poly_to_faces(geom)]
    return reduce(lambda a, b: a.fuse(b), solids) if len(solids) > 1 else solids[0]


def _check_removed(before, after, expected, label):
    removed = before - after
    ok = expected == 0 or abs(removed - expected) <= TOL * expected
    flag = "OK " if ok else "!! "
    print(f"  {flag} {label}: removed {removed:9.2f} mm^3 (analytic {expected:9.2f})")
    if not ok:
        raise RuntimeError(f"{label}: removed {removed:.2f}, expected {expected:.2f}")
    return removed


def build():
    # Rounded plate slab, decorated face up at z = 0, body to z = -PLATE_THICKNESS.
    plate_poly = _rounded_rect_poly(
        (PLATE_WIDTH / 2, PLATE_HEIGHT / 2, PLATE_WIDTH, PLATE_HEIGHT, CORNER_R)
    )
    solid = _cut_tool(plate_poly, PLATE_THICKNESS)
    print(f"  ..  plate slab volume {solid.Volume():.2f} mm^3")

    # Field recess (raised border).
    field_w = PLATE_WIDTH - 2 * BORDER_W
    field_h = PLATE_HEIGHT - 2 * BORDER_W
    field = box(BORDER_W, BORDER_W, BORDER_W + field_w, BORDER_W + field_h)
    before = solid.Volume()
    solid = solid.cut(_cut_tool(field, RECESS_DEPTH))
    _check_removed(before, solid.Volume(), field_w * field_h * RECESS_DEPTH, "field recess")

    # Engraving (lettering + cartouche), incised ENGRAVE_DEPTH below the field floor.
    region = _engraving_region()
    eng_area = region.area
    before = solid.Volume()
    solid = solid.cut(_cut_tool(region, RECESS_DEPTH + ENGRAVE_DEPTH))
    _check_removed(before, solid.Volume(), eng_area * ENGRAVE_DEPTH, "lettering")

    # Pinstripe band on the raised border.
    band = _rounded_rect_poly(BORDER_OUTER).difference(_rounded_rect_poly(BORDER_INNER))
    band_area = band.area
    before = solid.Volume()
    solid = solid.cut(_cut_tool(band, ENGRAVE_DEPTH))
    _check_removed(before, solid.Volume(), band_area * ENGRAVE_DEPTH, "pinstripe")

    # Four corner screw through-holes.
    screws = unary_union([Point(x, y).buffer(SCREW_DIA / 2, quad_segs=48) for x, y in SCREW_XY])
    before = solid.Volume()
    solid = solid.cut(_cut_tool(screws, PLATE_THICKNESS))
    _check_removed(
        before,
        solid.Volume(),
        len(SCREW_XY) * math.pi * (SCREW_DIA / 2) ** 2 * PLATE_THICKNESS,
        "screw holes",
    )

    print(f"  ..  finished plate volume {solid.Volume():.2f} mm^3")
    if not solid.isValid():
        raise RuntimeError("finished plate solid is INVALID (self-intersection?)")
    print("  OK  solid is valid (closed, non-self-intersecting)")
    return solid, eng_area, band_area


def main():
    solid, eng_area, band_area = build()
    OUT.mkdir(parents=True, exist_ok=True)
    step = OUT / "nameplate-cq.step"
    stl = OUT / "nameplate-cq.stl"
    cq.exporters.export(cq.Workplane(obj=solid), str(step))
    cq.exporters.export(cq.Workplane(obj=solid), str(stl), tolerance=0.01, angularTolerance=0.1)
    print(f"  ..  engraving area {eng_area:.3f} mm^2, pinstripe band {band_area:.3f} mm^2")
    print(f"  ->  {step.name}, {stl.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
