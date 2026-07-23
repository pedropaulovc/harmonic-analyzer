"""SolidWorks-free contracts for the ch30-p002 platen-system refit."""

from __future__ import annotations

import math

import build_paper_drive_assembly as assembly
import build_platen as platen
import build_platen_clip as clip
import build_platen_guide as guide
import build_platen_paper as paper
import build_platen_rack as rack
import build_support_bar as support


def test_platen_envelope_preserves_fitted_top_left_and_ratio() -> None:
    assert math.isclose(platen.PLATE_HEIGHT * 2.0, platen.PLATE_WIDTH)
    assert math.isclose(assembly.PLATE_X0, -33.213)
    assert math.isclose(assembly.PLATE_Y0 + platen.PLATE_HEIGHT, 408.054)


def test_platen_furniture_cascades_with_resized_envelope() -> None:
    assert math.isclose(rack.BAR_LENGTH, platen.PLATE_WIDTH)
    assert math.isclose(guide.GUIDE_LENGTH, platen.PLATE_WIDTH)
    assert guide.SCREW_STATION_X == platen.GUIDE_HOLE_X

    clip_y0 = platen.PLATE_HEIGHT - clip.CLIP_LENGTH
    assert math.isclose(platen.SOCKET_XY[0][1], clip_y0 + clip.HOLE_INSET)
    assert math.isclose(platen.SOCKET_XY[1][1], platen.PLATE_HEIGHT - clip.HOLE_INSET)

    side_margin = (platen.PLATE_WIDTH - paper.PAPER_WIDTH) / 2.0
    assert math.isclose(side_margin, 18.2007)
    assert math.isclose(
        platen.PLATE_HEIGHT - paper.PAPER_HEIGHT - 5.3928,
        14.3808,
    )


def test_cascaded_drive_geometry_closes() -> None:
    assert rack.GAP_COUNT == 101
    assembly._assert_rack_mesh()
    assembly._assert_gear_mesh()
    assembly._assert_knob_shaft_clearance()
    assembly._assert_chain_layout()


def test_refitted_platen_clears_fixed_support_hardware() -> None:
    assert support.CLAMP_CBORE_DEPTH > 2.5
    assert support.CLAMP_CBORE_DIA > support.CLAMP_HOLE_DIA
    assert math.isclose(assembly.STUD_XY[0], support.BRACKET_STUD_X)
    assert support.BRACKET_HOLE_X == tuple(
        support.BRACKET_STUD_X + dx for dx in (-10.0, 10.0)
    )
    assert guide.LOCK_STATION_X == tuple(
        guide.GUIDE_LENGTH * fraction for fraction in (0.3, 0.7)
    )
