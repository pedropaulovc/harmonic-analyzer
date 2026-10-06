"""Offline contracts for the wheel-bar drawing."""

from __future__ import annotations

import pytest

import build_mg_wheel_bar as part
import draw_mg_wheel_bar as drawing
import mg_wheel_bar_spec


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    marked = set().union(*mg_wheel_bar_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked


def test_hanger_clearance_preserves_a_tolerance_safe_end_ligament() -> None:
    import mg_wheel_bar_geom as geom

    hole_dia = part.blind_cut_dia_mm(geom.PEN_HANGER_HOLE_SPEC)
    assert hole_dia == pytest.approx(4.572)
    assert part.PEN_HANGER_END_WALL == pytest.approx(2.714)
    minimum_wall = (
        part.PEN_HANGER_END_WALL
        - geom.PEN_HANGER_STATION_TOL
        - part.PEN_HANGER_HOLE_DIA_TOL / 2.0
    )
    assert minimum_wall == pytest.approx(2.614)
    assert minimum_wall >= geom.PEN_HANGER_MIN_END_WALL

    # The former station passed a >0 guard with only 0.214 mm of material.
    with pytest.raises(AssertionError):
        geom.require_hanger_end_wall(-114.5, hole_dia, part.PEN_HANGER_HOLE_DIA_TOL)
    # A nominal wall above 2 mm must still fail if tolerances consume the reserve.
    with pytest.raises(AssertionError):
        geom.require_hanger_end_wall(-112.664, hole_dia, part.PEN_HANGER_HOLE_DIA_TOL)
