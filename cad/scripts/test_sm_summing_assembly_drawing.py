"""Offline contract for the simple summing assembly drawing."""

import draw_sm_summing_assembly as drawing


def test_summing_assembly_keeps_precomputed_placement() -> None:
    assert drawing.SHEET_SCALE == (1.0, 5.0)
    assert drawing.FRONT_CENTER == (0.060, 0.150)
    assert drawing.RIGHT_CENTER == (0.130, 0.150)
    assert drawing.ISO_CENTER == (0.225, 0.140)
