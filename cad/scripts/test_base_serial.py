"""Offline contracts for the base's stamped serial number (gen_base_serial_dxf)."""

from __future__ import annotations

import _dxf_text as dxf
import build_harmonic_base as base
import gen_base_serial_dxf as gen
from harmonic_base_spec import LIP_H, LIP_W, STACK_HEIGHT, TOP_LENGTH


def test_tracked_dxf_matches_the_generator():
    assert base.SERIAL_DXF.is_file()
    assert dxf.normalize_newlines(base.SERIAL_DXF.read_bytes()) == dxf.normalize_newlines(gen.render())


def test_glyph_sits_on_the_lip_top_beside_the_nameplate():
    import nameplate_spec

    s = gen.summary()
    lip_x0, lip_x1 = TOP_LENGTH / 2.0 - LIP_W, TOP_LENGTH / 2.0
    assert lip_x0 + 0.5 <= s["x0"] and s["x1"] <= lip_x1 - 0.5, s
    plate_z_end = max(z for _x, _y, z in (nameplate_spec.mount_point(p) for p in ((0, 0, 0), (100, 0, 0))))
    physical_z0, physical_z1 = -s["y1"], -s["y0"]
    assert physical_z0 > plate_z_end + 5.0, (s, plate_z_end)
    assert 0.9 * base.SERIAL_HEIGHT_MM <= (physical_z1 - physical_z0) <= 1.1 * base.SERIAL_HEIGHT_MM
    assert abs(base.SERIAL_AREA_MM2 - s["area_mm2"]) < 1e-3, (base.SERIAL_AREA_MM2, s["area_mm2"])
    assert STACK_HEIGHT + LIP_H > STACK_HEIGHT  # the rim top is above the deck


def test_notes_mention_the_serial():
    from harmonic_base_spec import DRAWING_NOTES

    assert 'STAMP SERIAL "2"' in DRAWING_NOTES
