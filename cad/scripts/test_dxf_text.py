"""Offline guards for the measuring stick's engraved-numerals DXF.

The tracked ``cad/references/measuring-stick-numerals.dxf`` is a GENERATED
asset (``gen_stick_numerals_dxf``); the build imports it blind and only
bound-checks the removed volume on the live seat. These tests keep the file,
the generator and the build script's pinned constants in step without
SolidWorks: the file regenerates byte-identical, parses back as closed
LWPOLYLINEs with the expected loop census, lands inside the ruled band clear
of every tick, and matches the area/bbox the build asserts against.
"""

from __future__ import annotations

import _dxf_text as dxf
import build_measuring_stick as part
import gen_stick_numerals_dxf as gen

EXPECTED_OUTER_LOOPS = 12  # glyph bodies: 0 1 2 3 4 5 6 7 8 9 + the "1" and "0" of 10
EXPECTED_INNER_LOOPS = 7  # counters: 0, 4, 6, 8 (x2), 9, and the 0 of 10


def _read() -> str:
    return part.NUMERALS_DXF.read_text(encoding="ascii")


def _tick_rects() -> list[tuple[float, float, float, float]]:
    """Every engraved tick as (x0, y0, x1, y1), from the build's own layout."""
    half = part.TICK_WIDTH / 2.0
    rects = []
    for k in range(part.DIVISION_COUNT):
        x = gen.tick_x(k)
        rects.append((x - half, part.BODY_WIDTH - part.TICK_LENGTH, x + half, part.BODY_WIDTH))
    for d in range(part.DIVISION_COUNT - 1):
        for m in range(1, part.MINOR_PER_DIVISION):
            x = gen.tick_x(d) + m * part.MINOR_SPACING
            rects.append(
                (x - half, part.BODY_WIDTH - part.MINOR_TICK_LENGTH, x + half, part.BODY_WIDTH)
            )
    x = gen.tick_x(0) + part.DIVISION_SPACING / 2.0
    rects.append((x - half, part.BODY_WIDTH - part.HALF_TICK_LENGTH, x + half, part.BODY_WIDTH))
    return rects


def test_dxf_is_tracked_and_regenerates_byte_identical():
    assert part.NUMERALS_DXF.is_file(), part.NUMERALS_DXF
    on_disk = dxf.normalize_newlines(part.NUMERALS_DXF.read_bytes())
    assert on_disk == gen.render(), (
        "measuring-stick-numerals.dxf drifted from gen_stick_numerals_dxf -- "
        "re-run `uv run python cad/scripts/gen_stick_numerals_dxf.py` and commit"
    )


def test_dxf_header_is_millimetre_r2000():
    text = _read()
    assert dxf.header_int(text, "INSUNITS") == 4
    assert "AC1015" in text
    assert text.endswith("  0\nEOF\n")


def test_dxf_loops_are_closed_and_counted():
    entities = dxf.read_lwpolylines(_read())
    assert entities, "no LWPOLYLINE entities"
    assert all(closed for _, closed in entities), "every loop must be closed (flag 70 = 1)"
    assert all(len(ring) >= 3 for ring, _ in entities)
    rings = [ring for ring, _ in entities]
    depths = [dxf.nesting_depth(rings, i) for i in range(len(rings))]
    assert depths.count(0) == EXPECTED_OUTER_LOOPS, depths
    assert depths.count(1) == EXPECTED_INNER_LOOPS, depths
    assert max(depths) == 1, "no loop nests deeper than one counter"


def test_dxf_round_trips_the_generator_rings():
    parsed = [ring for ring, _ in dxf.read_lwpolylines(_read())]
    generated = gen.all_rings()
    assert len(parsed) == len(generated)
    for a, b in zip(parsed, generated, strict=True):
        assert len(a) == len(b)
        assert all(abs(pa[0] - pb[0]) < 1e-6 and abs(pa[1] - pb[1]) < 1e-6 for pa, pb in zip(a, b, strict=True))


def test_numerals_sit_in_the_ruled_band_clear_of_every_tick():
    numerals = gen.numeral_rings()
    assert len(numerals) == part.DIVISION_COUNT
    ticks = _tick_rects()
    band_top = part.BODY_WIDTH - part.TICK_LENGTH - part.NUMERAL_GAP_MM
    for k, numeral in enumerate(numerals):
        x0, y0, x1, y1 = dxf.bbox(numeral)
        assert 0.0 < x0 and x1 < part.BODY_LENGTH, (k, x0, x1)
        assert 0.0 < y0 and y1 <= band_top + 1e-9, (k, y0, y1)
        tick = gen.tick_x(k)
        if k < part.DIVISION_COUNT - 1:
            assert x0 >= tick + part.TICK_WIDTH / 2.0 + part.NUMERAL_GAP_MM - 1e-9, (k, x0)
            assert x0 < tick + part.DIVISION_SPACING / 2.0, (k, x0)  # next to ITS tick
        else:
            assert x1 <= tick - part.TICK_WIDTH / 2.0 - part.NUMERAL_GAP_MM + 1e-9, (k, x1)
        for tx0, ty0, tx1, ty1 in ticks:
            overlaps = x0 < tx1 and tx0 < x1 and y0 < ty1 and ty0 < y1
            assert not overlaps, f"numeral {k} bbox overlaps a tick at x={tx0:.2f}"


def test_numeral_height_matches_the_knob():
    # Rotation 90 puts the glyph height along x; 0 puts it along y.
    heights = []
    for numeral in gen.numeral_rings():
        x0, y0, x1, y1 = dxf.bbox(numeral)
        heights.append((x1 - x0) if part.NUMERAL_ROTATION_DEG == 90 else (y1 - y0))
    assert abs(heights[1] - part.NUMERAL_HEIGHT_MM) < 1e-6, heights[1]  # the flat "1" is exact
    assert all(part.NUMERAL_HEIGHT_MM <= h <= 1.05 * part.NUMERAL_HEIGHT_MM for h in heights), heights


def test_pinned_area_and_bbox_match_the_generator():
    s = gen.summary()
    assert abs(s["area_mm2"] - part.NUMERAL_AREA_MM2) <= 0.01 * part.NUMERAL_AREA_MM2, s
    pinned = part.NUMERALS_BBOX
    for got, want in zip((s["x0"], s["y0"], s["x1"], s["y1"]), pinned, strict=True):
        assert abs(got - want) < 0.001, (s, pinned)
    assert s["loops"] == EXPECTED_OUTER_LOOPS + EXPECTED_INNER_LOOPS


def test_glyph_polylines_basic_shapes():
    zero = dxf.glyph_polylines("0", 2.0)
    assert len(zero) == 2 and sorted(dxf.nesting_depth(zero, i) for i in range(2)) == [0, 1]
    assert dxf.net_area(zero) > 0.0
    one = dxf.glyph_polylines("1", 2.0)
    _, v0, _, v1 = dxf.bbox(one)
    assert abs((v1 - v0) - 2.0) < 1e-9


def test_dxf_asset_is_a_recipe_dep_of_the_part():
    from pathlib import Path

    from _buildgraph import data_deps_of

    deps = data_deps_of(Path(part.__file__))
    assert str(part.NUMERALS_DXF.resolve()) in deps, deps
