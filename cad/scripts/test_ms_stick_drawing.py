"""Offline manufacturing contracts for the unchanged measuring-stick geometry."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import build_ms_stick as builder
import draw_ms_stick as drawing
import ms_stick_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME


def test_current_identity_and_drawing_paths() -> None:
    assert builder.PART_NAME == drawing.PART_STEM == "ms-stick"
    assert DRAWINGS_BY_NAME["ms_stick"].script == Path(drawing.__file__).resolve()
    assert drawing.SLDDRW.name == "ms-stick.SLDDRW"
    assert drawing.PDF.name == "ms-stick.pdf"
    assert drawing.PNG.name == "ms-stick_drawing.png"
    assert spec.NUMERALS_DXF.name == "ms-stick-numerals.dxf"


def test_bar_and_engraving_geometry_are_unchanged() -> None:
    assert (spec.BODY_LENGTH, spec.BODY_WIDTH, spec.BODY_THICKNESS) == (200.0, 8.0, 3.0)
    assert (spec.TICK_WIDTH, spec.TICK_DEPTH, spec.TICK_LENGTH) == (0.4, 0.5, 3.0)
    assert (spec.MINOR_TICK_LENGTH, spec.HALF_TICK_LENGTH) == (1.8, 4.0)
    assert spec.DIVISION_COUNT == 11 and spec.MINOR_PER_DIVISION == 10
    assert spec.SCALE_SPAN == pytest.approx(
        (spec.DIVISION_COUNT - 1) * spec.DIVISION_SPACING, rel=0.0, abs=1e-12,
    )
    assert spec.SCALE_START_X + spec.SCALE_SPAN + spec.SCALE_END_MARGIN == pytest.approx(
        spec.BODY_LENGTH, rel=0.0, abs=1e-12,
    )
    assert (spec.NUMERAL_HEIGHT_MM, spec.NUMERAL_GAP_MM, spec.NUMERAL_ROTATION_DEG) == (2.0, 0.6, 90)
    for name in ("BODY_LENGTH", "BODY_WIDTH", "BODY_THICKNESS", "SCALE_START_X",
                 "TICK_WIDTH", "TICK_DEPTH", "NUMERALS_DXF"):
        assert getattr(builder, name) == getattr(spec, name)


def test_every_printed_size_is_owned_and_precisioned_by_model() -> None:
    assert builder.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    assert builder.DRAWING_PRECISION is spec.DRAWING_PRECISION
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP) | set(drawing.DETAIL_KEEP) | set(drawing.SECTION_KEEP)
    assert kept == marked == set(spec.DRAWING_VALUES_BY_NAME) == set(spec.DRAWING_PRECISION_BY_NAME)
    assert all(places == 2 for places in spec.DRAWING_PRECISION_BY_NAME.values())
    assert set(spec.DRAWING_TOLERANCES) <= marked
    assert {"BodyThickness", "TickDepth", "FullTickLength", "MinorTickLength",
            "HalfTickLength", "FullTickPitch", "MinorTickPitch", "NumeralHeight",
            "NumeralXGap", "NumeralYGap"} <= marked
    assert drawing.SHEET_NAMES == ("BAR", "GRADUATIONS")
    assert drawing.DETAIL_SCALE[0] / drawing.DETAIL_SCALE[1] > drawing.SHEET_SCALE[0] / drawing.SHEET_SCALE[1]


def test_reference_chords_measure_real_sizes_not_profile_overhangs() -> None:
    assert spec.DRAWING_VALUES_BY_NAME["FullTickLength"] == pytest.approx(
        spec.TICK_LENGTH, rel=0.0, abs=1e-12,
    )
    assert spec.DRAWING_VALUES_BY_NAME["MinorTickLength"] == pytest.approx(
        spec.MINOR_TICK_LENGTH, rel=0.0, abs=1e-12,
    )
    assert spec.DRAWING_VALUES_BY_NAME["HalfTickLength"] == pytest.approx(
        spec.HALF_TICK_LENGTH, rel=0.0, abs=1e-12,
    )
    assert spec.DRAWING_VALUES_BY_NAME["MinorTickPitch"] == pytest.approx(
        spec.DIVISION_SPACING / spec.MINOR_PER_DIVISION, rel=0.0, abs=1e-12,
    )
    for _name, start, end in spec.REFERENCE_DIMENSIONS.values():
        assert (start[0] == end[0]) != (start[1] == end[1])
        assert 0.0 <= min(start[0], end[0]) <= max(start[0], end[0]) <= spec.BODY_LENGTH
        assert 0.0 <= min(start[1], end[1]) <= max(start[1], end[1]) <= spec.BODY_WIDTH


def test_spec_is_pure_and_drawing_never_reauthors_dimensions() -> None:
    tree = ast.parse(Path(spec.__file__).read_text(encoding="utf-8"))
    imports = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert not any(name.startswith(("build_", "solidworks", "_common", "_drawing")) for name in imports)
    drawing_tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    calls = {node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
             for node in ast.walk(drawing_tree) if isinstance(node, ast.Call)
             and isinstance(node.func, (ast.Attribute, ast.Name))}
    assert not calls & {"SetPrecision3", "set_dimension_precision", "SetValues", "set_basic_dimensions", "add_gdt_frame", "add_datum_tag"}
    assert not any(character.isdigit() for character in spec.DRAWING_NOTES)
