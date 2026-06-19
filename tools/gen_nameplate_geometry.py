#!/usr/bin/env python3
"""Regenerate ``cad/scripts/_nameplate_geometry.py`` from the traced DXFs.

The maker's-plate engraving was traced off the book's p.71 macro into two
vendored DXFs (``cad/assets/nameplate-engraving.dxf`` and
``cad/assets/nameplate-border.dxf``). ``build_nameplate`` no longer imports
those DXFs -- it draws the engraving with native SolidWorks sketch primitives
(line chains for the glyphs/cartouche, rounded-rectangle arcs for the pinstripe
frame). This script extracts the traced contours from the engraving DXF into a
plain Python coordinate module so the build can consume them as line loops.

The DXFs stay in the tree as the trace provenance and as the golden reference
for ``test_nameplate_geometry`` (which asserts this data reproduces them).

Run::

    python tools/gen_nameplate_geometry.py
"""

from __future__ import annotations

import math
from pathlib import Path

import ezdxf

REPO = Path(__file__).resolve().parents[1]
ENGRAVING_DXF = REPO / "cad" / "assets" / "nameplate-engraving.dxf"
OUT = REPO / "cad" / "scripts" / "_nameplate_geometry.py"


def loops_from(path: Path) -> list[list[tuple[float, float]]]:
    """Closed LWPOLYLINE loops as (x, y) lists, in plate mm, 3-dp (the DXF's
    authored precision). The duplicate closing vertex and any rounding-induced
    consecutive duplicates are dropped -- each loop is implicitly closed."""
    doc = ezdxf.readfile(str(path))
    out: list[list[tuple[float, float]]] = []
    for pl in doc.modelspace().query("LWPOLYLINE"):
        pts = [(round(p[0], 3), round(p[1], 3)) for p in pl.get_points()]
        if math.dist(pts[0], pts[-1]) < 1e-9:
            pts = pts[:-1]
        dedup = [pts[0]]
        for q in pts[1:]:
            if q != dedup[-1]:
                dedup.append(q)
        if dedup[0] == dedup[-1]:
            dedup.pop()
        out.append(dedup)
    return out


def _fmt_loop(loop: list[tuple[float, float]]) -> str:
    body = ", ".join(f"({x:g}, {y:g})" for x, y in loop)
    return "    [" + body + "],"


def render(loops: list[list[tuple[float, float]]]) -> str:
    head = '''"""Vendored nameplate engraving geometry -- native sketch line-loops.

Provenance: the maker's-plate engraving (book ch.26 p.71 macro) was traced
off the photo into ``cad/assets/nameplate-engraving.dxf`` (smoothed letters +
scroll cartouche) and ``cad/assets/nameplate-border.dxf`` (the pinstripe frame).
This module re-expresses that exact traced geometry as plain coordinate loops so
``build_nameplate`` can draw it with SolidWorks **sketch primitives** (line
chains + rounded-rectangle arcs) instead of importing the DXFs at build time.
The DXFs are retained only as the trace provenance and the golden reference for
``test_nameplate_geometry`` (which asserts this data reproduces them to >=98%).

Coordinates are plate millimetres in the build frame (origin = plate corner,
+X width, +Y height); each loop is implicitly closed (no repeated end vertex).
Generated from the DXFs -- do not hand-edit; re-run tools/gen_nameplate_geometry.py.
"""

from __future__ import annotations

# 45 traced engraving contours: 36 outer glyph/ornament loops and 9 counters
# (letter holes). Drawn into one sketch and cut as a unit; even-odd fill makes
# each enclosed counter a hole, exactly as the DXF import did.
LETTERING_LOOPS: list[list[tuple[float, float]]] = [
'''
    tail = ''']

# Pinstripe frame = two concentric rounded rectangles (a thin band cut, even-odd).
# The DXF traced each corner as ~16 chords; reproduced here as true corner arcs
# via sketch_rounded_rect, which matches the traced band area to 99.99%.
# (cx, cy, width, height, corner_radius) in plate millimetres.
# Outer: DXF bbox x[6,94] y[6,49], straight runs start at the 3.5 mm corner radius.
# Inner: 0.7 mm inside the outer (pinstripe line width) -> radius 2.8 mm.
BORDER_OUTER: tuple[float, float, float, float, float] = (50.0, 27.5, 88.0, 43.0, 3.5)
BORDER_INNER: tuple[float, float, float, float, float] = (50.0, 27.5, 86.6, 41.6, 2.8)
'''
    return head + "\n".join(_fmt_loop(loop) for loop in loops) + "\n" + tail


def main() -> None:
    loops = loops_from(ENGRAVING_DXF)
    OUT.write_text(render(loops))
    pts = sum(len(loop) for loop in loops)
    print(f"wrote {OUT.relative_to(REPO)} ({len(loops)} loops, {pts} vertices)")


if __name__ == "__main__":
    main()
