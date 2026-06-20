"""Regression proof for the nameplate's native sketch-primitive engraving.

``build_nameplate`` used to import two DXFs (``nameplate-engraving.dxf`` and
``nameplate-border.dxf``) and cut them. It now draws that geometry with
SolidWorks sketch primitives: line chains for the glyph/cartouche contours
(vendored in ``_nameplate_geometry.LETTERING_LOOPS``) and two rounded-rectangle
arcs for the pinstripe frame (``BORDER_OUTER``/``BORDER_INNER``).

When the primitives replaced the DXFs they were proven equal to the traced
golden: engraving region area matched to 100.000%, pinstripe band area to
99.989% (true arcs beat the DXF's 16-chord corners), and the finished solid
volume to 100.000%. Those DXFs have since been removed, so this test guards the
vendored geometry against regression by recomputing those three analytic targets
from the vendored primitives alone -- no CAD kernel required.

The maths mirrors ``build_nameplate`` exactly:
  * engraving area = ``abs`` of the signed-area (shoelace) sum over the loops --
    outer glyph/ornament contours wind CCW (+), the 9 enclosed counters wind CW
    (-), so the sum is the even-odd filled region the single cut removes. This
    also guards the winding parity the live cut depends on.
  * pinstripe band area = outer minus inner rounded-rectangle area.
  * plate volume = rounded plate slab, minus the field recess, minus the
    engraving and pinstripe cuts (area x incise depth), minus the four screw
    holes. The screws sit in the outer border clear of the pinstripe band, and
    the engraving sits inside the already-sunk field, so the contributions don't
    overlap and the closed form is exact.

Solid validity and the boolean overlap resolution are proven on the live
SolidWorks seat by ``build_nameplate`` itself (each cut asserts its removed
volume against these same analytic areas); this test is the kernel-free guard on
the vendored numbers.

Run directly for a full report::

    python cad/scripts/test_nameplate_geometry.py
"""

from __future__ import annotations

import math

from _nameplate_geometry import BORDER_INNER, BORDER_OUTER, engraving_loops

# Golden analytic targets, captured when the primitives were proven equal to the
# traced DXFs (engraving 100%, band 99.99%, volume 100% -- all >= the 99% bar).
GOLDEN_ENGRAVING_AREA = 535.341  # mm^2, even-odd filled glyph + cartouche region
GOLDEN_BAND_AREA = 177.654  # mm^2, rounded-rectangle pinstripe frame
GOLDEN_VOLUME = 6682.26  # mm^3, finished plate

# Plate / feature dimensions -- mirror build_nameplate.py exactly.
PLATE_W, PLATE_H, PLATE_T, CORNER_R = 100.0, 55.0, 1.5, 3.0
BORDER_W, RECESS_DEPTH, ENGRAVE_DEPTH = 8.0, 0.4, 0.3
SCREW_DIA, SCREW_INSET = 2.6, 4.5

Loop = list[tuple[float, float]]


def _shoelace(loop: Loop) -> float:
    """Signed polygon area (CCW positive) -- build_nameplate._shoelace."""
    a = 0.0
    n = len(loop)
    for i in range(n):
        x1, y1 = loop[i]
        x2, y2 = loop[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return a / 2.0


def _engraving_area() -> float:
    """Even-odd filled area of the traced engraving (mm^2).

    Outer contours run CCW (+) and the enclosed counters CW (-), so the signed
    sum is exactly the even-odd region the single cut removes -- the property
    the live cut relies on, so a flipped loop would fail this test. The
    cartouche is spline-fitted, so its loops come from ``engraving_loops``
    (glyph line-loops + cartouche spline loops); staying >= 99% of the golden
    proves the fit did not drift the engraving area.
    """
    return abs(sum(_shoelace(loop) for loop in engraving_loops()))


def _rrect_area(spec: tuple[float, float, float, float, float]) -> float:
    """Area of a rounded rectangle ``(cx, cy, w, h, r)``."""
    _cx, _cy, w, h, r = spec
    return w * h - (4.0 - math.pi) * r * r


def _band_area() -> float:
    return _rrect_area(BORDER_OUTER) - _rrect_area(BORDER_INNER)


def _plate_volume() -> float:
    """Finished plate volume from the closed forms (no CAD kernel).

    Slab - field recess - engraving cut - pinstripe cut - 4 screw holes. The
    engraving cut's reach (RECESS+ENGRAVE) overlaps the already-sunk recess, so
    only its ENGRAVE_DEPTH below the field floor is new material -- matching
    build_nameplate's ``expected_removed = area * ENGRAVE_DEPTH``.
    """
    slab = (PLATE_W * PLATE_H - (4.0 - math.pi) * CORNER_R**2) * PLATE_T
    field = (PLATE_W - 2.0 * BORDER_W) * (PLATE_H - 2.0 * BORDER_W) * RECESS_DEPTH
    engraving = _engraving_area() * ENGRAVE_DEPTH
    pinstripe = _band_area() * ENGRAVE_DEPTH
    screws = 4.0 * math.pi * (SCREW_DIA / 2.0) ** 2 * PLATE_T
    return slab - field - engraving - pinstripe - screws


def _pct(got: float, ref: float) -> float:
    return 100.0 * (1.0 - abs(got - ref) / abs(ref))


def test_engraving_region_area():
    """The line-chain glyph/cartouche loops fill the golden engraving region."""
    assert _pct(_engraving_area(), GOLDEN_ENGRAVING_AREA) >= 99.0


def test_pinstripe_band_area():
    """The two rounded rectangles enclose the golden pinstripe band area."""
    assert _pct(_band_area(), GOLDEN_BAND_AREA) >= 99.0


def test_full_plate_volume():
    """End-to-end: the primitive plate reaches the golden finished volume."""
    assert _pct(_plate_volume(), GOLDEN_VOLUME) >= 99.0


if __name__ == "__main__":
    eng = _engraving_area()
    band = _band_area()
    vol = _plate_volume()
    print("nameplate primitive geometry vs golden analytic targets")
    print(f"  engraving area : {eng:9.4f}  golden {GOLDEN_ENGRAVING_AREA:9.4f}  -> {_pct(eng, GOLDEN_ENGRAVING_AREA):7.3f}%")
    print(f"  pinstripe band : {band:9.4f}  golden {GOLDEN_BAND_AREA:9.4f}  -> {_pct(band, GOLDEN_BAND_AREA):7.3f}%")
    print(f"  plate volume   : {vol:9.3f}  golden {GOLDEN_VOLUME:9.3f}  -> {_pct(vol, GOLDEN_VOLUME):7.3f}%")
