"""Offline contracts for the wheel-bar drawing."""

from __future__ import annotations

from pathlib import Path

import pytest

import build_wheel_bar as part
import draw_wheel_bar as drawing
import wheel_bar_spec
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/wheel-bar.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/wheel-bar.pdf")
    assert drawing.PNG.as_posix().endswith("/png/wheel-bar_drawing.png")
    assert DRAWINGS_BY_NAME["wheel_bar"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert part.DRAWING_DIMENSIONS is wheel_bar_spec.DRAWING_DIMENSIONS
    marked = set().union(*wheel_bar_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    assert (drawing.BAR_LENGTH, drawing.BAR_SIDE, drawing.BAR_DEPTH) == (
        wheel_bar_spec.BAR_LENGTH,
        wheel_bar_spec.BAR_SIDE,
        wheel_bar_spec.BAR_DEPTH,
    )


def test_drawing_contract_is_split_from_the_assembly_nominals() -> None:
    # The bar depth + clamp stations the assembly imports live in the drawing-
    # FREE geom module, so a print-note edit cannot enter the assembly recipe.
    import wheel_bar_geom as geom

    assert (geom.BAR_SIDE, geom.BAR_DEPTH, geom.BAR_LENGTH) == (10.0, 9.0, 234.0)
    assert geom.CLAMP_HOLE_X == (70.5, 105.5)
    assembly = (
        Path(part.__file__)
        .with_name("build_magnifier_assembly.py")
        .read_text(encoding="utf-8")
    )
    assert "from wheel_bar_geom import" in assembly
    assert "from build_wheel_bar import" not in assembly


def test_hanger_clearance_preserves_a_tolerance_safe_end_ligament() -> None:
    import wheel_bar_geom as geom

    assert part.PEN_HANGER_HOLE_SPEC is geom.PEN_HANGER_HOLE_SPEC
    assert part.CLAMP_HOLE_SPEC is geom.CLAMP_HOLE_SPEC
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


def test_bores_are_note_based_with_center_marks() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    # The small clearance-hole circles are not dependable associative picks at
    # 1:1, so there is no per-hole callout / location dim; the notes carry the
    # sizes + X-stations and the front-view centre marks locate them.
    assert source.count("add_native_hole_callout(") == 0
    assert source.count("add_datum_feature(") == 1
    assert source.count("add_edge_dimension(") == 1  # bar depth only
    assert "auto_center_marks(" in source
    # The station note is computed from the geom constants, never duplicated.
    assert "HOLE STATIONS FROM THE LEFT END" in wheel_bar_spec.DRAWING_NOTES


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("wheel-bar")
    assert config["material"] == config["material_specification"]
    assert config["finish"]
    assert int(config["quantity"]) == 1
