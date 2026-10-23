"""Offline guards for the measuring stick's V-engraved numeral stroke DXFs.

The tracked ``cad/references/ms-stick-numerals-<n>.dxf`` files are GENERATED
assets (``gen_ms_stick_numerals_dxf``); the build imports them blind and only
bound-checks the removed volume on the live seat. These tests keep the files,
the generator and the pure model dimensional contract in step without
SolidWorks: the files regenerate byte-identical, parse back as closed
rectangles that never touch within a layer, land inside the ruled band clear
of every tick, and match the model-owned pinned bbox/volumes.
"""

from __future__ import annotations

import math

import _dxf_text as dxf
import ms_stick_spec as part
import gen_ms_stick_numerals_dxf as gen

def _read(path) -> str:
    return path.read_text(encoding="ascii")


def _tick_rects() -> list[tuple[float, float, float, float]]:
    """Every engraved tick as (x0, y0, x1, y1), from the pure model layout."""
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


def test_layer_dxfs_are_tracked_and_regenerate_byte_identical():
    rendered = gen.render_layers()
    assert len(rendered) == len(part.NUMERAL_LAYER_DXFS)
    for path, data in zip(part.NUMERAL_LAYER_DXFS, rendered, strict=True):
        assert path.is_file(), path
        assert dxf.normalize_newlines(path.read_bytes()) == data, (
            f"{path.name} drifted from gen_ms_stick_numerals_dxf -- "
            "re-run `uv run python cad/scripts/gen_ms_stick_numerals_dxf.py` and commit"
        )


def test_dxf_headers_are_millimetre_r2000():
    for path in part.NUMERAL_LAYER_DXFS:
        text = _read(path)
        assert dxf.header_int(text, "INSUNITS") == 4
        assert "AC1015" in text
        assert text.endswith("  0\nEOF\n")


def test_layers_are_closed_rectangles_that_never_touch():
    total = 0
    for path, layer in zip(part.NUMERAL_LAYER_DXFS, gen.layers(), strict=True):
        entities = dxf.read_lwpolylines(_read(path))
        assert all(closed and len(ring) == 4 for ring, closed in entities), path.name
        rings = [ring for ring, _ in entities]
        assert len(rings) == len(layer)
        for a, b in zip(rings, layer, strict=True):
            assert all(math.dist(pa, pb) < 1e-6 for pa, pb in zip(a, b, strict=True))
        for i, a in enumerate(rings):
            for b in rings[i + 1:]:
                assert gen._gap(a, b) >= gen.LAYER_GAP_MM, path.name
        total += len(rings)
    assert total == sum(len(numeral) for numeral in gen.numeral_rects())


def test_every_stroke_is_one_v_of_the_stated_width():
    for numeral in gen.numeral_rects():
        for rect in numeral:
            widths = sorted(math.dist(rect[i], rect[(i + 1) % 4]) for i in range(4))
            assert abs(widths[0] - part.NUMERAL_STROKE_WIDTH_MM) < 1e-9, widths
    # The drafted walls nearly meet: a true V, not a flat-bottomed groove.
    assert 0.0 < part.NUMERAL_TIP_FLAT_MM < 0.15 * part.NUMERAL_STROKE_WIDTH_MM


def test_numerals_sit_in_the_ruled_band_clear_of_every_tick():
    numerals = gen.numeral_rects()
    assert len(numerals) == part.DIVISION_COUNT
    ticks = _tick_rects()
    band_top = part.BODY_WIDTH - part.TICK_LENGTH - part.NUMERAL_GAP_MM
    for k, numeral in enumerate(numerals):
        x0, y0, x1, y1 = dxf.bbox(numeral)
        assert 0.0 < x0 and x1 < part.BODY_LENGTH, (k, x0, x1)
        assert 0.0 < y0 and abs(y1 - band_top) < 1e-9, (k, y0, y1)
        tick = gen.tick_x(k)
        if k < part.DIVISION_COUNT - 1:
            assert abs(x0 - (tick + part.TICK_WIDTH / 2.0 + part.NUMERAL_GAP_MM)) < 1e-9, (k, x0)
            assert x0 < tick + part.DIVISION_SPACING / 2.0, (k, x0)  # next to ITS tick
        else:
            assert abs(x1 - (tick - part.TICK_WIDTH / 2.0 - part.NUMERAL_GAP_MM)) < 1e-9, (k, x1)
        for tx0, ty0, tx1, ty1 in ticks:
            overlaps = x0 < tx1 and tx0 < x1 and y0 < ty1 and ty0 < y1
            assert not overlaps, f"numeral {k} bbox overlaps a tick at x={tx0:.2f}"


def test_numeral_height_matches_the_knob():
    # Rotation 90 puts the glyph height along x; 0 puts it along y.
    heights = []
    for numeral in gen.numeral_rects():
        x0, y0, x1, y1 = dxf.bbox(numeral)
        heights.append((x1 - x0) if part.NUMERAL_ROTATION_DEG == 90 else (y1 - y0))
    assert abs(heights[0] - part.NUMERAL_HEIGHT_MM) < 1e-6, heights[0]  # the flat "0" is exact
    assert all(part.NUMERAL_HEIGHT_MM <= h <= 1.05 * part.NUMERAL_HEIGHT_MM for h in heights), heights


def test_pinned_bbox_and_volumes_match_the_generator():
    s = gen.summary()
    assert s["layers"] == len(part.NUMERAL_LAYER_DXFS)
    for got, want in zip((s["x0"], s["y0"], s["x1"], s["y1"]), part.NUMERALS_BBOX, strict=True):
        assert abs(got - want) < 0.001, (s, part.NUMERALS_BBOX)
    assert abs(s["volume_mm3"] - part.NUMERAL_VOLUME_MM3) < 1e-3, s
    assert abs(s["first_layer_volume_mm3"] - part.NUMERAL_FIRST_LAYER_VOLUME_MM3) < 1e-3, s


def test_first_layer_volume_is_the_closed_form_v():
    # Disjoint drafted rectangles: each is a prismatoid, D/6 (A0 + A1 + 4 Am).
    slope = math.tan(math.radians(part.NUMERAL_V_INCLUDED_ANGLE_DEG / 2.0))
    depth = part.NUMERAL_DEPTH
    exact = 0.0
    for rect in gen.layers()[0]:
        a, b = math.dist(rect[0], rect[1]), math.dist(rect[1], rect[2])

        def area(z, a=a, b=b):
            return (a - 2.0 * z * slope) * (b - 2.0 * z * slope)

        exact += depth / 6.0 * (area(0.0) + area(depth) + 4.0 * area(depth / 2.0))
    assert abs(exact - part.NUMERAL_FIRST_LAYER_VOLUME_MM3) < 1e-3, exact


def test_glyph_polylines_basic_shapes():
    zero = dxf.glyph_polylines("0", 2.0)
    assert len(zero) == 2 and sorted(dxf.nesting_depth(zero, i) for i in range(2)) == [0, 1]
    assert dxf.net_area(zero) > 0.0
    one = dxf.glyph_polylines("1", 2.0)
    _, v0, _, v1 = dxf.bbox(one)
    assert abs((v1 - v0) - 2.0) < 1e-9


def test_dxf_assets_are_recipe_deps_of_the_part():
    from pathlib import Path

    from _buildgraph import data_deps_of

    deps = data_deps_of(Path(part.__file__))
    for path in part.NUMERAL_LAYER_DXFS:
        assert str(path.resolve()) in deps, deps
