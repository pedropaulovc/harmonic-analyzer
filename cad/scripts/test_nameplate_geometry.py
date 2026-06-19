"""Regression proof for the nameplate's native sketch-primitive engraving.

``build_nameplate`` used to import two DXFs (``nameplate-engraving.dxf`` and
``nameplate-border.dxf``) and cut them. It now draws that geometry with
SolidWorks sketch primitives: line chains for the glyph/cartouche contours
(vendored in ``_nameplate_geometry.LETTERING_LOOPS``) and two rounded-rectangle
arcs for the pinstripe frame (``BORDER_OUTER``/``BORDER_INNER``).

When the primitives replaced the DXFs they were proven equal to the traced
golden: engraving region area matched to 100.000%, pinstripe band area to
99.989% (true arcs beat the DXF's 16-chord corners), and the finished solid
volume to 100.000%. Those DXFs have since been removed, so this test now guards
the vendored geometry against regression by rebuilding the whole plate in
CadQuery (standing in for SolidWorks -- same prismatic cut-extrudes, same
even-odd fill) and asserting it still reproduces the golden analytic targets.

Run directly for a full report::

    python cad/scripts/test_nameplate_geometry.py
"""

from __future__ import annotations

import math

import pytest

cq = pytest.importorskip("cadquery", reason="CadQuery stands in for SolidWorks")

from cadquery import Face, Solid, Vector, Wire  # noqa: E402

import _nameplate_geometry as geom  # noqa: E402

# Golden analytic targets, captured when the primitives were proven equal to the
# traced DXFs (engraving 100%, band 99.99%, volume 100% -- all >= the 98% bar).
GOLDEN_ENGRAVING_AREA = 535.341  # mm^2, even-odd filled glyph + cartouche region
GOLDEN_BAND_AREA = 177.654  # mm^2, rounded-rectangle pinstripe frame
GOLDEN_VOLUME = 6682.26  # mm^3, finished plate

# Plate / feature dimensions -- mirror build_nameplate.py exactly.
PLATE_W, PLATE_H, PLATE_T, CORNER_R = 100.0, 55.0, 1.5, 3.0
BORDER_W, RECESS_DEPTH, ENGRAVE_DEPTH = 8.0, 0.4, 0.3
SCREW_DIA, SCREW_INSET = 2.6, 4.5
FIELD = (BORDER_W, BORDER_W, PLATE_W - BORDER_W, PLATE_H - BORDER_W)
SCREW_XY = (
    (SCREW_INSET, SCREW_INSET),
    (PLATE_W - SCREW_INSET, SCREW_INSET),
    (SCREW_INSET, PLATE_H - SCREW_INSET),
    (PLATE_W - SCREW_INSET, PLATE_H - SCREW_INSET),
)

Loop = list[tuple[float, float]]


# --------------------------------------------------------------------------- #
# Even-odd region -> CadQuery faces (outer loop with its enclosed holes)
# --------------------------------------------------------------------------- #
def _point_in(loop: Loop, p: tuple[float, float]) -> bool:
    x, y = p
    inside = False
    n = len(loop)
    j = n - 1
    for i in range(n):
        xi, yi = loop[i]
        xj, yj = loop[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _wire(loop: Loop) -> Wire:
    vs = [Vector(x, y, 0.0) for x, y in loop]
    vs.append(vs[0])
    return Wire.makePolygon(vs)


def _even_odd_faces(loops: list[Loop]) -> list[Face]:
    """Group loops into outer-with-holes faces by containment depth (even depth
    = filled, odd = hole) -- exactly the even-odd fill a single cut sketch uses.
    Containment is witnessed by a boundary vertex (the centroid is wrong for a
    ring/annulus loop, where it lands in the hole)."""
    reps = [loop[0] for loop in loops]
    depth = [
        sum(1 for j, other in enumerate(loops) if j != i and _point_in(other, reps[i]))
        for i in range(len(loops))
    ]
    faces: list[Face] = []
    for i, loop in enumerate(loops):
        if depth[i] % 2 != 0:
            continue  # this loop is a hole; consumed by its parent below
        holes = [
            _wire(loops[j])
            for j in range(len(loops))
            if depth[j] == depth[i] + 1 and _point_in(loop, reps[j])
        ]
        faces.append(Face.makeFromWires(_wire(loop), holes))
    return faces


def _region_area(loops: list[Loop]) -> float:
    return sum(f.Area() for f in _even_odd_faces(loops))


def _region_solid(loops: list[Loop], depth: float) -> Solid:
    solids = [Solid.extrudeLinear(f, Vector(0, 0, depth)) for f in _even_odd_faces(loops)]
    s = solids[0]
    for nxt in solids[1:]:
        s = s.fuse(nxt)
    return s


def _rrect_area(spec: tuple[float, float, float, float, float]) -> float:
    _cx, _cy, w, h, r = spec
    return w * h - (4.0 - math.pi) * r * r


# --------------------------------------------------------------------------- #
# Full plate build (CadQuery standing in for SolidWorks)
# --------------------------------------------------------------------------- #
def _rounded_band_solid(depth: float) -> Solid:
    """The pinstripe band as the live build draws it: outer minus inner rounded
    rectangle (true corner arcs), extruded `depth`."""
    cxo, cyo, wo, ho, ro = geom.BORDER_OUTER
    cxi, cyi, wi, hi, ri = geom.BORDER_INNER
    outer = cq.Workplane("XY").center(cxo, cyo).rect(wo, ho).extrude(depth).edges("|Z").fillet(ro)
    inner = cq.Workplane("XY").center(cxi, cyi).rect(wi, hi).extrude(depth).edges("|Z").fillet(ri)
    return outer.cut(inner).val()


def _build() -> cq.Solid:
    """Plate - field recess - engraving - pinstripe - 4 screw holes, all drawn
    from the vendored primitives. Cuts mirror build_nameplate: recess
    0..RECESS_DEPTH, engraving 0..RECESS+ENGRAVE, pinstripe 0..ENGRAVE on the +Z
    face, screws through; booleans resolve the recess/engraving overlap."""
    plate = (
        cq.Workplane("XY")
        .center(PLATE_W / 2.0, PLATE_H / 2.0)
        .rect(PLATE_W, PLATE_H)
        .extrude(PLATE_T)
        .edges("|Z")
        .fillet(CORNER_R)
    )
    x0, y0, x1, y1 = FIELD
    recess = (
        cq.Workplane("XY")
        .center((x0 + x1) / 2.0, (y0 + y1) / 2.0)
        .rect(x1 - x0, y1 - y0)
        .extrude(RECESS_DEPTH)
    )
    body = plate.cut(recess)
    body = body.cut(
        cq.Workplane(obj=_region_solid(geom.LETTERING_LOOPS, RECESS_DEPTH + ENGRAVE_DEPTH))
    )
    body = body.cut(cq.Workplane(obj=_rounded_band_solid(ENGRAVE_DEPTH)))
    for x, y in SCREW_XY:
        screw = cq.Workplane("XY").center(x, y).circle(SCREW_DIA / 2.0).extrude(PLATE_T)
        body = body.cut(screw)
    return body.val()


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
def _pct(got: float, ref: float) -> float:
    return 100.0 * (1.0 - abs(got - ref) / abs(ref))


def test_engraving_region_area():
    """The line-chain glyph/cartouche loops fill the golden engraving region."""
    assert _pct(_region_area(geom.LETTERING_LOOPS), GOLDEN_ENGRAVING_AREA) >= 99.0


def test_pinstripe_band_area():
    """The two rounded rectangles enclose the golden pinstripe band area."""
    band = _rrect_area(geom.BORDER_OUTER) - _rrect_area(geom.BORDER_INNER)
    assert _pct(band, GOLDEN_BAND_AREA) >= 99.0


def test_full_plate_builds_and_volume():
    """End-to-end: the primitive plate builds a valid solid at the golden volume."""
    solid = _build()
    assert solid.isValid()
    assert _pct(solid.Volume(), GOLDEN_VOLUME) >= 99.0


if __name__ == "__main__":
    eng = _region_area(geom.LETTERING_LOOPS)
    band = _rrect_area(geom.BORDER_OUTER) - _rrect_area(geom.BORDER_INNER)
    vol = _build().Volume()
    print("nameplate primitive geometry vs golden analytic targets")
    print(f"  engraving area : {eng:9.4f}  golden {GOLDEN_ENGRAVING_AREA:9.4f}  -> {_pct(eng, GOLDEN_ENGRAVING_AREA):7.3f}%")
    print(f"  pinstripe band : {band:9.4f}  golden {GOLDEN_BAND_AREA:9.4f}  -> {_pct(band, GOLDEN_BAND_AREA):7.3f}%")
    print(f"  plate volume   : {vol:9.3f}  golden {GOLDEN_VOLUME:9.3f}  -> {_pct(vol, GOLDEN_VOLUME):7.3f}%")
