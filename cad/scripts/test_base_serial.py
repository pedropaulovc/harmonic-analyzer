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
