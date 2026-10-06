"""Offline contract for the simple magnifier assembly drawing."""

import draw_mg_magnifier_assembly as drawing


def test_magnifier_keeps_precomputed_placement() -> None:
    assert drawing.SHEET_SCALE == (1.0, 4.0)
    assert drawing.FRONT_CENTER == (0.070, 0.150)
    assert drawing.RIGHT_CENTER == (0.150, 0.150)
    assert drawing.ISO_CENTER == (0.225, 0.140)
