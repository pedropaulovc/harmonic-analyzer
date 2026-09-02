r"""Generate the measuring stick's engraved numerals DXF (tracked asset).

Writes ``cad/references/measuring-stick-numerals.dxf``: the 0..10 scale
numerals of the ruled measuring stick as closed loops at their FINAL model
millimetre coordinates, ready for ``build_measuring_stick`` to import onto the
Front plane and cut ``TICK_DEPTH`` deep (the nameplate precedent: the Makers
seat ignores the importer's scale/position, so placement is baked into the
file and the build imports at scale 1, position (0, 0)).

Deterministic: same constants -> same bytes (no timestamps; fixed-precision
coordinates; matplotlib's bundled DejaVu Sans pinned by file). Re-run after
changing any layout constant here or in ``build_measuring_stick`` and commit
the DXF; ``test_dxf_text`` fails if the tracked file drifts from this script
or its pinned area/bbox in the build script go stale.

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
  inversion is applied HERE, in the file, never at import.
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

    uv run python cad\scripts\gen_stick_numerals_dxf.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _dxf_text as dxf  # noqa: E402
from build_measuring_stick import (  # noqa: E402
    BODY_WIDTH,
    DIVISION_COUNT,
    DIVISION_SPACING,
    NUMERALS_DXF,
    NUMERAL_GAP_MM,
    NUMERAL_HEIGHT_MM,
    NUMERAL_ROTATION_DEG,
    SCALE_START_X,
    TICK_LENGTH,
    TICK_WIDTH,
)

# The y at which the full ticks END (they hang from y = BODY_WIDTH); the numeral
# band lies between here and the far edge y = 0.
TICK_END_Y = BODY_WIDTH - TICK_LENGTH


def tick_x(k: int) -> float:
    return SCALE_START_X + k * DIVISION_SPACING


def _place(rings: list[dxf.Ring], k: int) -> list[dxf.Ring]:
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


def numeral_rings() -> list[list[dxf.Ring]]:
    """Per numeral 0..10, its placed rings (model mm)."""
    return [
        _place(dxf.glyph_polylines(str(k), NUMERAL_HEIGHT_MM), k)
        for k in range(DIVISION_COUNT)
    ]


def all_rings() -> list[dxf.Ring]:
    return [ring for numeral in numeral_rings() for ring in numeral]


def render() -> bytes:
    return dxf.render_dxf(all_rings()).encode("ascii")


def summary() -> dict[str, float | int]:
    numerals = numeral_rings()
    rings = [ring for numeral in numerals for ring in numeral]
    x0, y0, x1, y1 = dxf.bbox(rings)
    outer = sum(
        1 for numeral in numerals for i in range(len(numeral)) if dxf.nesting_depth(numeral, i) == 0
    )
    return {
        "loops": len(rings),
        "outer": outer,
        "inner": len(rings) - outer,
        "area_mm2": sum(dxf.net_area(numeral) for numeral in numerals),
        "x0": x0,
        "y0": y0,
        "x1": x1,
        "y1": y1,
    }


def main() -> int:
    data = render()
    NUMERALS_DXF.write_bytes(data)
    s = summary()
    print(f"wrote {NUMERALS_DXF} ({len(data)} bytes)")
    print(f"loops {s['loops']} (outer {s['outer']}, inner {s['inner']})")
    print(f"net area {s['area_mm2']:.4f} mm^2")
    print(f"bbox x {s['x0']:.4f}..{s['x1']:.4f}  y {s['y0']:.4f}..{s['y1']:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
