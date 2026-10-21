"""Offline contracts for the base's stamped serial number (gen_base_serial_dxf)."""

from __future__ import annotations

import math

import _dxf_text as dxf
import build_fr_harmonic_base as base
import gen_base_serial_dxf as gen
from fr_harmonic_base_spec import (
    DECK_CORNER_R,
    DECK_EDGE_BREAK,
    DECK_HALF_X,
    DECK_HALF_Z,
)


def test_tracked_dxf_matches_the_generator():
    assert base.SERIAL_DXF.is_file()
    assert dxf.normalize_newlines(base.SERIAL_DXF.read_bytes()) == dxf.normalize_newlines(gen.render())


def test_stamp_dimensions_and_removed_volume_are_unchanged():
    assert base.SERIAL_XZ == (161.0, 124.25)
    assert base.SERIAL_HEIGHT_MM == 3.5
    assert base.SERIAL_DEPTH == 0.3
    assert base.SERIAL_AREA_MM2 == 3.1029
    entities = dxf.read_lwpolylines(base.SERIAL_DXF.read_text(encoding="ascii"))
    assert len(entities) == 1 and entities[0][1]
    rings = [ring for ring, _closed in entities]
    # Pin the imported ink envelope too; the nominal 3.5 mm font has optical
    # overshoot on "2", unchanged by the orientation correction.
    expected_bbox = (159.889091, -126.031505, 162.110909, -122.468495)
    assert all(
        math.isclose(actual, expected, abs_tol=1e-6)
        for actual, expected in zip(dxf.bbox(rings), expected_bbox, strict=True)
    )
    area = dxf.net_area(rings)
    assert math.isclose(area, 3.1029, abs_tol=1e-4)
    assert math.isclose(area * base.SERIAL_DEPTH, 0.93087, abs_tol=1e-4)


def test_stamp_is_a_readable_right_handed_two_in_native_top_projection():
    """Check independent ink landmarks, not the mirror flag or generator bytes.

    The native deck's offset Top sketch maps (sx, sy) to (X, Y, Z) =
    (sx, STACK_HEIGHT, -sy). The actual *Top plan basis is paper right = +X,
    paper up = -Z, as used by draw_fr_harmonic_base._plan_xy. Its positive
    drawing scale and sheet translation cannot change the glyph's hand.
    """
    entities = dxf.read_lwpolylines(base.SERIAL_DXF.read_text(encoding="ascii"))
    assert len(entities) == 1 and entities[0][1]
    model_rings = [
        [(sx, base.STACK_HEIGHT, -sy) for sx, sy in ring]
        for ring, _closed in entities
    ]
    projected = [
        [(model_x, -model_z) for model_x, _model_y, model_z in ring]
        for ring in model_rings
    ]
    u0, v0, u1, v1 = dxf.bbox(projected)
    normalized = [
        [((u - u0) / (u1 - u0), (v - v0) / (v1 - v0)) for u, v in ring]
        for ring in projected
    ]
    # A readable "2" has a full-width bottom foot, a right-hand upper curve,
    # and a diagonal descending left towards the foot. These handwritten
    # probes do not use glyph_polylines, gen.rings, or SERIAL_MIRROR_Y; the old
    # reflection fails even when its constant, generator and asset all agree.
    for point, ink in (
        ((0.10, 0.05), True),   # bottom-left foot
        ((0.90, 0.05), True),   # bottom-right foot; not a top-right stroke
        ((0.90, 0.65), True),   # right side of upper curve
        ((0.10, 0.65), False),  # no reflected left-side curve
        ((0.25, 0.20), True),   # diagonal reaches the lower left
        ((0.80, 0.20), False),
        ((0.95, 0.95), False),  # upper-right corner is outside the rounded cap
    ):
        inside = sum(dxf.point_in_ring(ring, point) for ring in normalized) % 2 == 1
        assert inside == ink, (point, ink, inside)


def test_glyph_sits_on_the_deck_flat_in_its_north_west_corner():
    """User ruling 2026-10-09: the "2" moves off the gone rim into the black
    deck's NW corner (+X west, +Z north), inside the deck's edge break and
    rounded corner, clear of the nameplate."""
    import fr_nameplate_spec

    s = gen.summary()
    physical_z0, physical_z1 = -s["y1"], -s["y0"]
    assert s["x0"] > 0.0 and physical_z0 > 0.0, s
    # Every bbox corner lies on the deck flat with 0.5 to spare: inside the
    # break-inset outline, the corner arc included.
    inset = DECK_EDGE_BREAK + 0.5
    arc_x, arc_z = DECK_HALF_X - DECK_CORNER_R, DECK_HALF_Z - DECK_CORNER_R
    for x in (s["x0"], s["x1"]):
        for z in (physical_z0, physical_z1):
            assert x <= DECK_HALF_X - inset and z <= DECK_HALF_Z - inset, (s, x, z)
            if x > arc_x and z > arc_z:
                assert math.hypot(x - arc_x, z - arc_z) <= DECK_CORNER_R - inset, (s, x, z)
    plate_z_end = max(
        z
        for _x, _y, z in (
            fr_nameplate_spec.mount_point(p)
            for p in ((0, 0, 0), (fr_nameplate_spec.PLATE_WIDTH, 0, 0))
        )
    )
    assert physical_z0 > plate_z_end + 5.0, (s, plate_z_end)
    assert 0.9 * base.SERIAL_HEIGHT_MM <= (physical_z1 - physical_z0) <= 1.1 * base.SERIAL_HEIGHT_MM
    assert abs(base.SERIAL_AREA_MM2 - s["area_mm2"]) < 1e-3, (base.SERIAL_AREA_MM2, s["area_mm2"])
