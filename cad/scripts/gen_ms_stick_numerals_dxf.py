r"""Generate the measuring stick's V-engraved numeral stroke DXFs (tracked assets).

The 2026-10-23 owner ruling ("whatever is easiest to machine") engraves the
0..10 scale numerals with a 30-degree included V bit. A V cut cannot follow
filled font outlines at one depth, so the numerals are a SINGLE-STROKE sans
design: each stroke is a straight centreline, and the groove is that
centreline's V. The drawing accepts any single-stroke sans font; these strokes
are the model's representative shapes.

Each straight stroke becomes a closed rectangle at the ruled face: the stroke
width at the surface (``NUMERAL_STROKE_WIDTH_MM``) wide, mitred at interior
corners and square-capped at free ends. ``build_ms_stick`` imports each layer
onto the Front plane and cuts it ``NUMERAL_DEPTH`` deep with a 15-degree
inward draft on every side, so each rectangle becomes a true 30-degree V whose
walls nearly meet (``NUMERAL_TIP_FLAT_MM`` remains, which keeps the native
faces valid). A drafted cut needs disjoint profiles, so overlapping strokes of
one numeral go to different LAYERS (one DXF and one cut each), coloured here
with a fixed greedy order.

Placement is baked into the files because the Makers seat ignores the
importer's scale/position; the build imports at scale 1, position (0, 0).
Deterministic: same constants -> same bytes. Re-run after changing any layout
constant in ``ms_stick_spec`` and commit the DXFs; ``test_dxf_text`` fails if
a tracked file drifts or the pinned bbox/volumes in ``ms_stick_spec`` go stale.

Photo derivation (2026-09-02, ch16 page001_img01 at 6x): each full tick carries
a numeral just past the tick ends, on the +X side of its tick (toward 10), about
2 mm tall, plain sans-serif -- and TURNED 90 degrees: the digits read upright
when the bar is held vertically with the 10 end UP ("10" stacks a 1 over a 0
across the bar's width). ``NUMERAL_ROTATION_DEG`` pins that; 0 gives upright
numerals along the bar instead.

Frames and signs -- the one place they are worked out:

* The build sketches on the Front plane and cuts +Z, so the ruled face is the
  z = 0 BACK face (outward normal -Z). The engraving is therefore SEEN from -Z.
  The drawing shows it that way (``*Back`` rotated pi: tick 0 at the left, the
  ticks hanging from the LOWER edge shown). In that view screen-right = +X and
  screen-up = -Y, so a glyph frame (u along the baseline, v up the glyph) that
  reads correctly on the real face maps to model (x, y) with a y inversion. An
  un-inverted (as-drawn-from-+Z) import would read mirrored on the face -- the
  inversion is applied HERE, in the files, never at import.
* Rotation 90 (default): glyph up (v) -> +X (toward 10), baseline (u) -> +Y,
  i.e. ``x = x0 + v, y = y0 + u`` -- the digit's foot faces the tick it labels
  (numerals 0..9 sit +X of their tick, the 10 numeral sits -X of its tick
  because tick 10 is only ``SCALE_END_MARGIN`` from the bar end), and the
  string runs from the far edge toward the tick band, its tick-side end
  ``NUMERAL_GAP_MM`` short of the tick ends.
* Rotation 0: ``x = x0 + u, y = y0 - v`` -- upright in the drawing view, left
  ink edge ``NUMERAL_GAP_MM`` past the tick (10: right edge short of it),
  baseline ``NUMERAL_GAP_MM`` beyond the tick ends toward the far edge.

Run::

    uv run --frozen python cad\scripts\gen_ms_stick_numerals_dxf.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402

import _dxf_text as dxf  # noqa: E402
from ms_stick_spec import (  # noqa: E402
    BODY_WIDTH,
    DIVISION_COUNT,
    DIVISION_SPACING,
    NUMERAL_DEPTH,
    NUMERAL_GAP_MM,
    NUMERAL_HEIGHT_MM,
    NUMERAL_LAYER_DXFS,
    NUMERAL_ROTATION_DEG,
    NUMERAL_STROKE_WIDTH_MM,
    NUMERAL_V_INCLUDED_ANGLE_DEG,
    SCALE_START_X,
    TICK_LENGTH,
    TICK_WIDTH,
)

Point = tuple[float, float]
Ring = list[Point]

# The y at which the full ticks END (they hang from y = BODY_WIDTH); the numeral
# band lies between here and the far edge y = 0.
TICK_END_Y = BODY_WIDTH - TICK_LENGTH

# Unit-cell centrelines: x across the digit (0..1), y up it (0..1). C is the
# corner chamfer of the "round" digits; every stroke is straight, so each one
# is a single V groove.
_C = 0.3
_CY = 0.16
_ZERO = [(_C, 0), (1 - _C, 0), (1, _CY), (1, 1 - _CY), (1 - _C, 1), (_C, 1), (0, 1 - _CY), (0, _CY), (_C, 0)]
_SIX = [
    (1, 1 - _CY), (1 - _C, 1), (_C, 1), (0, 1 - _CY), (0, _CY), (_C, 0), (1 - _C, 0), (1, _CY),
    (1, 0.55 - _CY), (1 - _C, 0.55), (_C, 0.55), (0, 0.55 - _CY),
]
DIGIT_STROKES: dict[str, list[list[Point]]] = {
    "0": [_ZERO],
    "1": [[(0.55, 0), (0.55, 1)], [(0.55, 1), (0.2, 0.78)]],
    "2": [[(0, 1 - _CY), (_C, 1), (1 - _C, 1), (1, 1 - _CY), (1, 0.62), (0, 0), (1, 0)]],
    "3": [[(0, 1), (1, 1), (0.4, 0.58), (1 - _C, 0.58), (1, 0.58 - _CY), (1, _CY), (1 - _C, 0), (_C, 0), (0, _CY)]],
    "4": [[(0.75, 0), (0.75, 1), (0, 0.3), (1, 0.3)]],
    "5": [[(1, 1), (0, 1), (0, 0.58), (1 - _C, 0.58), (1, 0.58 - _CY), (1, _CY), (1 - _C, 0), (_C, 0), (0, _CY)]],
    "6": [_SIX],
    "7": [[(0, 1), (1, 1), (0.35, 0)]],
    "8": [
        [(_C, 0.55), (1 - _C, 0.55), (0.95, 0.55 + _CY), (0.95, 1 - _CY), (1 - _C, 1), (_C, 1),
         (0.05, 1 - _CY), (0.05, 0.55 + _CY), (_C, 0.55)],
        [(_C, 0.55), (0, 0.55 - _CY), (0, _CY), (_C, 0), (1 - _C, 0), (1, _CY), (1, 0.55 - _CY), (1 - _C, 0.55)],
    ],
    "9": [[(1 - x, 1 - y) for x, y in _SIX]],
}
# Centreline cell in mm: the ink is the cell grown by half a stroke all round,
# so a flat-ended digit is exactly NUMERAL_HEIGHT_MM tall.
CELL_HEIGHT = NUMERAL_HEIGHT_MM - NUMERAL_STROKE_WIDTH_MM
CELL_WIDTH = 0.5 * NUMERAL_HEIGHT_MM
DIGIT_SPACING = 0.35  # ink gap between the "1" and "0" of 10
# Interior corners sharper than this get square caps instead of a long miter.
_MITER_LIMIT_DEG = 100.0
# Strokes of one layer stay this far apart at the face (the importer merges
# endpoints within 0.002 mm).
LAYER_GAP_MM = 0.02
# Removed-volume integration grid (mm).
_GRID_MM = 0.004


def tick_x(k: int) -> float:
    return SCALE_START_X + k * DIVISION_SPACING


def _unit(p: Point, q: Point) -> Point:
    length = math.dist(p, q)
    return ((q[0] - p[0]) / length, (q[1] - p[1]) / length)


def _turn_deg(a: Point, b: Point) -> float:
    return math.degrees(math.acos(max(-1.0, min(1.0, a[0] * b[0] + a[1] * b[1]))))


def _extension(a: Point, b: Point) -> float:
    """How far each of two strokes meeting at a corner runs past it."""
    turn = _turn_deg(a, b)
    half = NUMERAL_STROKE_WIDTH_MM / 2.0
    if turn > _MITER_LIMIT_DEG:
        return half
    return half * math.tan(math.radians(turn) / 2.0)


def _stroke_rects(polyline: list[Point]) -> list[Ring]:
    """Mitred, square-capped rectangles of one centreline polyline (mm)."""
    closed = polyline[0] == polyline[-1]
    points = polyline[:-1] if closed else polyline
    count = len(points)
    segments = [(points[i], points[(i + 1) % count]) for i in range(count if closed else count - 1)]
    dirs = [_unit(p, q) for p, q in segments]
    half = NUMERAL_STROKE_WIDTH_MM / 2.0
    rects = []
    for i, ((p, q), d) in enumerate(zip(segments, dirs, strict=True)):
        before = dirs[i - 1] if (closed or i > 0) else None
        after = dirs[(i + 1) % len(dirs)] if (closed or i < len(dirs) - 1) else None
        start = half if before is None else _extension(before, d)
        end = half if after is None else _extension(d, after)
        a = (p[0] - d[0] * start, p[1] - d[1] * start)
        b = (q[0] + d[0] * end, q[1] + d[1] * end)
        n = (-d[1] * half, d[0] * half)
        rects.append([(a[0] + n[0], a[1] + n[1]), (b[0] + n[0], b[1] + n[1]),
                      (b[0] - n[0], b[1] - n[1]), (a[0] - n[0], a[1] - n[1])])
    return rects


def _glyph_rects(text: str) -> list[Ring]:
    """Rectangles of ``text`` in the glyph frame (u along the baseline, v up)."""
    rects: list[Ring] = []
    advance = 0.0
    for char in text:
        for stroke in DIGIT_STROKES[char]:
            mm = [(advance + x * CELL_WIDTH, y * CELL_HEIGHT) for x, y in stroke]
            rects += _stroke_rects(mm)
        advance += CELL_WIDTH + NUMERAL_STROKE_WIDTH_MM + DIGIT_SPACING
    return rects


def _place(rings: list[Ring], k: int) -> list[Ring]:
    """Map one numeral's glyph-frame rings (u, v) onto model (x, y) mm."""
    u0, v0, u1, v1 = dxf.bbox(rings)
    past_tick = k < DIVISION_COUNT - 1  # 0..9 on the +X side; 10 on the -X side
    if NUMERAL_ROTATION_DEG == 90:
        # glyph up -> +X, baseline -> +Y (read with the 10 end up).
        if past_tick:
            x0 = tick_x(k) + TICK_WIDTH / 2.0 + NUMERAL_GAP_MM - v0
        else:
            x0 = tick_x(k) - TICK_WIDTH / 2.0 - NUMERAL_GAP_MM - v1
        y0 = TICK_END_Y - NUMERAL_GAP_MM - u1
        return [[(x0 + v, y0 + u) for u, v in ring] for ring in rings]
    if NUMERAL_ROTATION_DEG == 0:
        # upright in the -Z view: baseline -> +X, glyph up -> -Y.
        if past_tick:
            x0 = tick_x(k) + TICK_WIDTH / 2.0 + NUMERAL_GAP_MM - u0
        else:
            x0 = tick_x(k) - TICK_WIDTH / 2.0 - NUMERAL_GAP_MM - u1
        y0 = TICK_END_Y - NUMERAL_GAP_MM + v0
        return [[(x0 + u, y0 - v) for u, v in ring] for ring in rings]
    raise ValueError(f"NUMERAL_ROTATION_DEG must be 0 or 90, got {NUMERAL_ROTATION_DEG}")


def numeral_rects() -> list[list[Ring]]:
    """Per numeral 0..10, its placed stroke rectangles (model mm)."""
    return [_place(_glyph_rects(str(k)), k) for k in range(DIVISION_COUNT)]


def _gap(a: Ring, b: Ring) -> float:
    """Separating-axis gap between two convex rings (<= 0 when they touch)."""
    gap = -math.inf
    for ring in (a, b):
        for i in range(len(ring)):
            p, q = ring[i], ring[(i + 1) % len(ring)]
            axis = (q[1] - p[1], p[0] - q[0])
            norm = math.hypot(*axis)
            axis = (axis[0] / norm, axis[1] / norm)
            pa = [x * axis[0] + y * axis[1] for x, y in a]
            pb = [x * axis[0] + y * axis[1] for x, y in b]
            gap = max(gap, min(pb) - max(pa), min(pa) - max(pb))
    return gap


def layers() -> list[list[Ring]]:
    """Greedy colouring: no two rectangles of one layer come within LAYER_GAP_MM."""
    out: list[list[Ring]] = []
    for numeral in numeral_rects():
        for rect in numeral:
            for layer in out:
                if all(_gap(rect, other) >= LAYER_GAP_MM for other in layer):
                    layer.append(rect)
                    break
            else:
                out.append([rect])
    return out


def _depth_field(rects: list[Ring], xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    """Removed depth of the drafted cuts of ``rects`` over the grid."""
    slope = math.tan(math.radians(NUMERAL_V_INCLUDED_ANGLE_DEG / 2.0))
    depth = np.zeros_like(xs)
    for rect in rects:
        # Inside distance is positive whichever way the placement wound it.
        sign = -1.0 if dxf.signed_area(rect) > 0.0 else 1.0
        inside = np.full_like(xs, np.inf)
        for i in range(len(rect)):
            p, q = rect[i], rect[(i + 1) % len(rect)]
            ex, ey = q[0] - p[0], q[1] - p[1]
            signed = ((xs - p[0]) * ey - (ys - p[1]) * ex) / math.hypot(ex, ey)
            inside = np.minimum(inside, sign * signed)
        depth = np.maximum(depth, np.clip(inside / slope, 0.0, NUMERAL_DEPTH))
    return depth


def removed_volume(rects: list[Ring]) -> float:
    """Volume (mm^3) the drafted cuts of ``rects`` remove together."""
    total = 0.0
    for numeral in _clusters(rects):
        x0, y0, x1, y1 = dxf.bbox(numeral)
        xs, ys = np.meshgrid(np.arange(x0, x1, _GRID_MM) + _GRID_MM / 2.0,
                             np.arange(y0, y1, _GRID_MM) + _GRID_MM / 2.0)
        total += float(_depth_field(numeral, xs, ys).sum()) * _GRID_MM**2
    return total


def layer_volumes(split: list[list[Ring]]) -> tuple[float, ...]:
    """Each layer's removal over the layers cut before it (they overlap)."""
    cumulative = [removed_volume([rect for layer in split[:i + 1] for rect in layer])
                  for i in range(len(split))]
    return tuple(after - before for before, after in zip([0.0, *cumulative], cumulative, strict=False))


def _clusters(rects: list[Ring]) -> list[list[Ring]]:
    """Rectangles grouped by numeral (numerals are far apart along X)."""
    groups: list[list[Ring]] = []
    for rect in sorted(rects, key=lambda ring: min(x for x, _ in ring)):
        x_min = min(x for x, _ in rect)
        if groups and x_min < max(x for ring in groups[-1] for x, _ in ring) + 1.0:
            groups[-1].append(rect)
        else:
            groups.append([rect])
    return groups


def render_layers() -> list[bytes]:
    return [dxf.render_dxf(layer).encode("ascii") for layer in layers()]


def summary() -> dict[str, float | int]:
    numerals = numeral_rects()
    rects = [rect for numeral in numerals for rect in numeral]
    x0, y0, x1, y1 = dxf.bbox(rects)
    split = layers()
    return {
        "strokes": len(rects),
        "layers": len(split),
        "layer_volumes_mm3": layer_volumes(split),
        "volume_mm3": removed_volume(rects),
        "x0": x0,
        "y0": y0,
        "x1": x1,
        "y1": y1,
    }


def main() -> int:
    rendered = render_layers()
    if len(rendered) != len(NUMERAL_LAYER_DXFS):
        raise SystemExit(
            f"{len(rendered)} stroke layers, but ms_stick_spec names "
            f"{len(NUMERAL_LAYER_DXFS)} NUMERAL_LAYER_DXFS"
        )
    for path, data in zip(NUMERAL_LAYER_DXFS, rendered, strict=True):
        path.write_bytes(data)
        print(f"wrote {path} ({len(data)} bytes)")
    s = summary()
    print(f"strokes {s['strokes']} in {s['layers']} layers")
    print(f"removed volume {s['volume_mm3']:.4f} mm^3 (by layer {', '.join(f'{v:.4f}' for v in s['layer_volumes_mm3'])})")
    print(f"bbox x {s['x0']:.4f}..{s['x1']:.4f}  y {s['y0']:.4f}..{s['y1']:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
