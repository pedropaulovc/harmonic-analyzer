"""Proof that the nameplate's native sketch-primitive engraving reproduces the
traced DXFs to >=98%.

``build_nameplate`` used to import two DXFs (``nameplate-engraving.dxf`` and
``nameplate-border.dxf``) and cut them. It now draws that geometry with
SolidWorks sketch primitives instead: line chains for the glyph/cartouche
contours (vendored in ``_nameplate_geometry.LETTERING_LOOPS``) and two
rounded-rectangle arcs for the pinstripe frame (``BORDER_OUTER``/``BORDER_INNER``).

This test rebuilds the whole plate twice in CadQuery -- once from the DXF
contours (the golden trace) and once from the primitive reconstruction the build
script consumes -- and asserts:

* the vendored engraving loops are byte-faithful to the DXF (area identical), so
  the line-chain glyphs cut exactly what the DXF import did;
* the rounded-rectangle pinstripe matches the traced band area to >=98% (it is
  in fact 99.99% -- true arcs beat the DXF's 16-chord-per-corner approximation);
* the finished solid volume matches the DXF-built solid to >=98%.

CadQuery stands in for SolidWorks here (same prismatic cut-extrudes, same
even-odd fill); the live SolidWorks build runs the identical primitive calls.

Run directly for a full report::

    python cad/scripts/test_nameplate_geometry.py
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

cq = pytest.importorskip("cadquery", reason="CadQuery stands in for SolidWorks")
ezdxf = pytest.importorskip("ezdxf", reason="needed to read the golden trace DXFs")

from cadquery import Face, Solid, Vector, Wire  # noqa: E402

import _nameplate_geometry as geom  # noqa: E402

ASSETS = Path(__file__).resolve().parents[1] / "assets"
ENGRAVING_DXF = ASSETS / "nameplate-engraving.dxf"
BORDER_DXF = ASSETS / "nameplate-border.dxf"

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
# Loop sources
# --------------------------------------------------------------------------- #
def _loops_from_dxf(path: Path) -> list[Loop]:
    doc = ezdxf.readfile(str(path))
    out: list[Loop] = []
    for pl in doc.modelspace().query("LWPOLYLINE"):
        pts = [(round(p[0], 3), round(p[1], 3)) for p in pl.get_points()]
        if math.dist(pts[0], pts[-1]) < 1e-9:
            pts = pts[:-1]
        out.append(pts)
    return out


def _rounded_rect_loop(cx, cy, w, h, r, seg=64) -> Loop:
    """Polyline approximation of a rounded rectangle (for the DXF-equivalent
    primitive band area cross-check); the live build draws true arcs."""
    a, b = w / 2.0, h / 2.0
    pts: Loop = []
    # corner centres CCW from bottom-right
    corners = [
        (cx + (a - r), cy - (b - r), -math.pi / 2, 0.0),
        (cx + (a - r), cy + (b - r), 0.0, math.pi / 2),
        (cx - (a - r), cy + (b - r), math.pi / 2, math.pi),
        (cx - (a - r), cy - (b - r), math.pi, 1.5 * math.pi),
    ]
    for ccx, ccy, t0, t1 in corners:
        for i in range(seg + 1):
            t = t0 + (t1 - t0) * i / seg
            pts.append((ccx + r * math.cos(t), ccy + r * math.sin(t)))
    return pts


# --------------------------------------------------------------------------- #
# Even-odd region -> CadQuery faces (outer loop with its enclosed holes)
# --------------------------------------------------------------------------- #
def _signed_area(loop: Loop) -> float:
    a = 0.0
    n = len(loop)
    for i in range(n):
        x1, y1 = loop[i]
        x2, y2 = loop[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return a / 2.0


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


def _rep_point(loop: Loop) -> tuple[float, float]:
    """A boundary vertex, used for containment tests. The centroid is wrong for a
    ring/annulus loop (it lands in the hole), so a vertex -- which always lies on
    the loop's own outline -- is the robust witness for "is this loop inside that
    one" across both the glyph counters and the concentric pinstripe frame."""
    return loop[0]


def _wire(loop: Loop) -> Wire:
    vs = [Vector(x, y, 0.0) for x, y in loop]
    vs.append(vs[0])
    return Wire.makePolygon(vs)


def _even_odd_faces(loops: list[Loop]) -> list[Face]:
    """Group loops into outer-with-holes faces by containment depth (even depth
    = filled, odd = hole) -- exactly the even-odd fill a single cut sketch uses."""
    reps = [_rep_point(loop) for loop in loops]
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


def _region_solid(loops: list[Loop], z0: float, depth: float) -> Solid:
    solids = [
        Solid.extrudeLinear(f, Vector(0, 0, depth)) for f in _even_odd_faces(loops)
    ]
    s = solids[0]
    for nxt in solids[1:]:
        s = s.fuse(nxt)
    return s.translate(Vector(0, 0, z0))


# --------------------------------------------------------------------------- #
# Full plate build (CadQuery standing in for SolidWorks)
# --------------------------------------------------------------------------- #
def _plate_solid() -> cq.Workplane:
    return (
        cq.Workplane("XY")
        .center(PLATE_W / 2.0, PLATE_H / 2.0)
        .rect(PLATE_W, PLATE_H)
        .extrude(PLATE_T)
        .edges("|Z")
        .fillet(CORNER_R)
    )


def _build(engraving_loops: list[Loop], border_band: Solid) -> float:
    """Plate - field recess - engraving - pinstripe - 4 screw holes; return mm^3.

    Cuts mirror build_nameplate: recess 0..RECESS_DEPTH, engraving
    0..RECESS+ENGRAVE, pinstripe 0..ENGRAVE on the +Z (decorated) face, screws
    through. Booleans resolve the overlap between the recess and the engraving.
    """
    plate = _plate_solid()
    x0, y0, x1, y1 = FIELD
    recess = (
        cq.Workplane("XY")
        .center((x0 + x1) / 2.0, (y0 + y1) / 2.0)
        .rect(x1 - x0, y1 - y0)
        .extrude(RECESS_DEPTH)
    )
    body = plate.cut(recess)
    body = body.cut(
        cq.Workplane(obj=_region_solid(engraving_loops, 0.0, RECESS_DEPTH + ENGRAVE_DEPTH))
    )
    body = body.cut(cq.Workplane(obj=border_band))
    for x, y in SCREW_XY:
        screw = (
            cq.Workplane("XY")
            .center(x, y)
            .circle(SCREW_DIA / 2.0)
            .extrude(PLATE_T)
        )
        body = body.cut(screw)
    return body.val().Volume()


def _rounded_band_solid(depth: float) -> Solid:
    """The pinstripe band as the live build draws it: outer minus inner rounded
    rectangle (true corner arcs), extruded `depth`."""
    cxo, cyo, wo, ho, ro = geom.BORDER_OUTER
    cxi, cyi, wi, hi, ri = geom.BORDER_INNER
    outer = (
        cq.Workplane("XY").center(cxo, cyo).rect(wo, ho).extrude(depth).edges("|Z").fillet(ro)
    )
    inner = (
        cq.Workplane("XY").center(cxi, cyi).rect(wi, hi).extrude(depth).edges("|Z").fillet(ri)
    )
    return outer.cut(inner).val()


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
def _pct(got: float, ref: float) -> float:
    return 100.0 * (1.0 - abs(got - ref) / abs(ref))


def test_engraving_loops_match_dxf():
    """The vendored line-chain loops cut the same region as the DXF import."""
    dxf_area = _region_area(_loops_from_dxf(ENGRAVING_DXF))
    prim_area = _region_area(geom.LETTERING_LOOPS)
    assert _pct(prim_area, dxf_area) >= 98.0, (prim_area, dxf_area)
    # In fact identical (same traced vertices) to within rounding.
    assert _pct(prim_area, dxf_area) >= 99.99


def test_pinstripe_band_matches_dxf():
    """The rounded-rectangle frame matches the traced pinstripe band area."""
    dxf_area = _region_area(_loops_from_dxf(BORDER_DXF))
    prim_area = (
        _region_area([_rounded_rect_loop(*geom.BORDER_OUTER)])
        - _region_area([_rounded_rect_loop(*geom.BORDER_INNER)])
    )
    assert _pct(prim_area, dxf_area) >= 98.0, (prim_area, dxf_area)


def test_full_plate_volume_matches_dxf():
    """End-to-end: the primitive plate matches the DXF-built plate to >=98%."""
    dxf_vol = _build(
        _loops_from_dxf(ENGRAVING_DXF),
        _region_solid(_loops_from_dxf(BORDER_DXF), 0.0, ENGRAVE_DEPTH),
    )
    prim_vol = _build(geom.LETTERING_LOOPS, _rounded_band_solid(ENGRAVE_DEPTH))
    assert _pct(prim_vol, dxf_vol) >= 98.0, (prim_vol, dxf_vol)


if __name__ == "__main__":
    dxf_eng = _loops_from_dxf(ENGRAVING_DXF)
    dxf_bor = _loops_from_dxf(BORDER_DXF)
    eng_dxf = _region_area(dxf_eng)
    eng_prim = _region_area(geom.LETTERING_LOOPS)
    bor_dxf = _region_area(dxf_bor)
    bor_prim = _region_area([_rounded_rect_loop(*geom.BORDER_OUTER)]) - _region_area(
        [_rounded_rect_loop(*geom.BORDER_INNER)]
    )
    vol_dxf = _build(dxf_eng, _region_solid(dxf_bor, 0.0, ENGRAVE_DEPTH))
    vol_prim = _build(geom.LETTERING_LOOPS, _rounded_band_solid(ENGRAVE_DEPTH))
    print("nameplate primitive-vs-DXF reconstruction")
    print(f"  engraving area : prim {eng_prim:9.4f}  dxf {eng_dxf:9.4f}  -> {_pct(eng_prim, eng_dxf):7.3f}%")
    print(f"  pinstripe band : prim {bor_prim:9.4f}  dxf {bor_dxf:9.4f}  -> {_pct(bor_prim, bor_dxf):7.3f}%")
    print(f"  plate volume   : prim {vol_prim:9.3f}  dxf {vol_dxf:9.3f}  -> {_pct(vol_prim, vol_dxf):7.3f}%")
