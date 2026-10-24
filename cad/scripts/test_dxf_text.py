"""Offline guards for the measuring stick's V-engraved numeral stroke DXFs.

The tracked ``cad/references/ms-stick-numerals-<n>.dxf`` files are GENERATED
assets (``gen_ms_stick_numerals_dxf``); the build imports them blind and only
bound-checks the removed volume on the live seat. These tests keep the files,
the generator and the pure model dimensional contract in step without
SolidWorks: the files regenerate byte-identical, parse back as closed
round-ended stroke outlines that never touch within a layer, land inside the
ruled band clear of every tick, and match the model-owned pinned bbox/volumes.
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


def test_layers_are_closed_stroke_outlines_that_never_touch():
    total = 0
    for path, layer in zip(part.NUMERAL_LAYER_DXFS, gen.layers(), strict=True):
        entities = dxf.read_lwpolylines(_read(path))
        assert all(closed and len(ring) == gen.CAPSULE_VERTICES for ring, closed in entities), path.name
        rings = [ring for ring, _ in entities]
        assert len(rings) == len(layer)
        for a, b in zip(rings, layer, strict=True):
            assert all(math.dist(pa, pb) < 1e-6 for pa, pb in zip(a, b, strict=True))
        for i, a in enumerate(rings):
            for b in rings[i + 1:]:
                assert gen._gap(a, b) >= gen.LAYER_GAP_MM, path.name
        total += len(rings)
    assert total == sum(len(numeral) for numeral in gen.numeral_rects())


def _edge_widths(ring):
    """Per edge, the ring's extent across it (rotating calipers)."""
    widths = []
    for i in range(len(ring)):
        (px, py), (qx, qy) = ring[i], ring[(i + 1) % len(ring)]
        length = math.hypot(qx - px, qy - py)
        widths.append(max(abs((x - px) * (qy - py) - (y - py) * (qx - px)) / length for x, y in ring))
    return widths


def _end_centres(ring):
    """A stroke outline's two end centres: each arc runs between diametrically
    opposite vertices of its face circle."""
    f = gen.END_FACETS
    return [((ring[i][0] + ring[j][0]) / 2.0, (ring[i][1] + ring[j][1]) / 2.0)
            for i, j in ((0, f), (f + 1, 2 * f + 1))]


def test_every_stroke_is_one_v_of_the_stated_width():
    half = part.NUMERAL_STROKE_WIDTH_MM / 2.0
    f = gen.END_FACETS
    for numeral in gen.numeral_rects():
        for ring in numeral:
            assert abs(min(_edge_widths(ring)) - part.NUMERAL_STROKE_WIDTH_MM) < 1e-9
            # Round-ended: each end's vertices lie on the cutter's face circle.
            q, p = _end_centres(ring)
            assert all(abs(math.dist(v, q) - half) < 1e-9 for v in ring[: f + 1])
            assert all(abs(math.dist(v, p) - half) < 1e-9 for v in ring[f + 1:])
    # The drafted walls nearly meet: a true V, not a flat-bottomed groove.
    assert 0.0 < part.NUMERAL_TIP_FLAT_MM < 0.15 * part.NUMERAL_STROKE_WIDTH_MM


def test_every_joint_and_end_reaches_full_depth():
    # A V bit cuts full depth all along its path. Drafted square or mitred
    # caps left a shallow saddle at the joints (0.18 at the zero's chamfers).
    import numpy as np

    for k, numeral in enumerate(gen.numeral_rects()):
        centres = [centre for ring in numeral for centre in _end_centres(ring)]
        depth = gen._depth_field(numeral, np.array([x for x, _ in centres]), np.array([y for _, y in centres]))
        assert np.all(np.abs(depth - part.NUMERAL_DEPTH) < 1e-9), (k, float(depth.min()))
    assert part.NUMERAL_DEPTH < part.NUMERAL_DEPTH_MAX_MM


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
    # A slanted free end's lowest facet vertex may sit a sagitta inside the circle.
    sagitta = part.NUMERAL_STROKE_WIDTH_MM / 2.0 * (1.0 - math.cos(math.pi / (2 * gen.END_FACETS)))
    assert all(part.NUMERAL_HEIGHT_MM - sagitta <= h <= 1.05 * part.NUMERAL_HEIGHT_MM for h in heights), heights


def test_pinned_bbox_and_volumes_match_the_generator():
    s = gen.summary()
    assert s["layers"] == len(part.NUMERAL_LAYER_DXFS)
    for got, want in zip((s["x0"], s["y0"], s["x1"], s["y1"]), part.NUMERALS_BBOX, strict=True):
        assert abs(got - want) < 0.001, (s, part.NUMERALS_BBOX)
    assert abs(s["volume_mm3"] - part.NUMERAL_VOLUME_MM3) < 1e-3, s
    assert len(s["layer_volumes_mm3"]) == len(part.NUMERAL_LAYER_VOLUMES_MM3)
    for got, want in zip(s["layer_volumes_mm3"], part.NUMERAL_LAYER_VOLUMES_MM3, strict=True):
        assert abs(got - want) < 1e-3, s
    assert abs(sum(part.NUMERAL_LAYER_VOLUMES_MM3) - part.NUMERAL_VOLUME_MM3) < 1e-3
    assert len(s["min_stroke_volumes_mm3"]) == len(part.NUMERAL_LAYER_MIN_STROKE_MM3)
    for got, want in zip(s["min_stroke_volumes_mm3"], part.NUMERAL_LAYER_MIN_STROKE_MM3, strict=True):
        assert abs(got - want) < 1e-4, s
    assert abs(s["final_min_stroke_mm3"] - part.NUMERAL_FINAL_MIN_STROKE_MM3) < 1e-4, s
    # Later layers only ever cover more of a stroke.
    assert part.NUMERAL_FINAL_MIN_STROKE_MM3 <= min(part.NUMERAL_LAYER_MIN_STROKE_MM3)


def _offset_area(ring, t):
    """Area of the convex ``ring`` offset inward by ``t`` (exact until an
    edge vanishes): A0 - P t + t^2 sum(tan(turn_i / 2))."""
    area = abs(dxf.signed_area(ring))
    perimeter, corners = 0.0, 0.0
    for i in range(len(ring)):
        a, b, c = ring[i - 1], ring[i], ring[(i + 1) % len(ring)]
        perimeter += math.dist(b, c)
        u = (b[0] - a[0], b[1] - a[1])
        v = (c[0] - b[0], c[1] - b[1])
        turn = math.atan2(abs(u[0] * v[1] - u[1] * v[0]), u[0] * v[0] + u[1] * v[1])
        corners += math.tan(turn / 2.0)
    return area - perimeter * t + corners * t * t


def test_first_layer_volume_is_the_closed_form_v():
    # Disjoint drafted convex outlines: each is a prismatoid, D/6 (A0 + A1 + 4 Am).
    slope = math.tan(math.radians(part.NUMERAL_V_INCLUDED_ANGLE_DEG / 2.0))
    depth = part.NUMERAL_DEPTH
    exact = sum(
        depth / 6.0 * (_offset_area(ring, 0.0) + _offset_area(ring, depth * slope)
                       + 4.0 * _offset_area(ring, depth * slope / 2.0))
        for ring in gen.layers()[0]
    )
    assert abs(exact - part.NUMERAL_LAYER_VOLUMES_MM3[0]) < 1e-3, exact


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
