"""Offline contracts for the pen-rod drawing.

The print follows cad/docs/drawing-simplicity-policy.md: drawn 5 mm square
stock carries no datums, frames, roughness symbols or machining tolerance
because its faces pass as received. The #47 through hole stays associative and
is explicitly centred across the section on the main front view.
"""

from __future__ import annotations

from pathlib import Path

import build_pen_rod as part
import draw_pen_rod as drawing
import pen_rod_spec
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _holes import NUMBER_DRILL_MM


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pen-rod.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pen-rod.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pen-rod_drawing.png")
    assert DRAWINGS_BY_NAME["pen_rod"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is pen_rod_spec.DRAWING_DIMENSIONS
    marked = set().union(*pen_rod_spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) == marked == {"Length"}
    assert not hasattr(drawing, "TOP_KEEP")
    assert (part.ROD_SECTION, part.ROD_LENGTH, part.WIRE_HOLE_Y) == (
        pen_rod_spec.ROD_SECTION,
        pen_rod_spec.ROD_LENGTH,
        pen_rod_spec.WIRE_HOLE_Y,
    )


def test_wire_hole_callout_states_size_and_process() -> None:
    assert pen_rod_spec.WIRE_HOLE_DIA == NUMBER_DRILL_MM[pen_rod_spec.WIRE_HOLE_DRILL]
    assert pen_rod_spec.WIRE_HOLE_DRILL == "#47"
    assert (
        pen_rod_spec.ROD_SECTION,
        pen_rod_spec.ROD_LENGTH,
        pen_rod_spec.WIRE_HOLE_Y,
    ) == (5.0, 150.0, 145.0)
    assert pen_rod_spec.ROD_LENGTH - pen_rod_spec.WIRE_HOLE_Y == 5.0
    source = _source()
    assert source.count("add_native_hole_callout(") == 1
    # Harvey #13: the callout says DRILL; the drill number rides as its prefix.
    assert 'process="#47 DRILL"' in source
    # Both hole locations stay on the main front view: one associative
    # line-to-circle dimension and one selection-free centring note.
    assert source.count("add_edge_dimension(") == 1
    assert (
        "wire_hole_edge = visible_circle_edge(adapter, front, WIRE_HOLE_DIA)" in source
    )
    assert "edge=wire_hole_edge" in source
    assert "edge_xy=" not in source
    # The native callout occupies the free upper-right area. Its leader crosses
    # the 145 dimension's x lane only above that dimension's hole endpoint.
    assert drawing.WIRE_HOLE_CALLOUT_XY[0] > drawing.FRONT_CENTER[0] + 0.070
    assert drawing.WIRE_HOLE_CALLOUT_XY[1] > drawing.WIRE_HOLE_CENTER_Y
    assert "callout_xy=WIRE_HOLE_CALLOUT_XY" in source


def test_wire_hole_centring_is_selection_free_on_main_front() -> None:
    assert drawing.WIRE_HOLE_CENTER_NOTE == (
        f"HOLE CENTERED ACROSS {pen_rod_spec.ROD_SECTION:g} SQ SECTION"
    )
    assert drawing.WIRE_HOLE_CENTER_NOTE_XY[0] > drawing.FRONT_CENTER[0] + 0.040
    assert drawing.WIRE_HOLE_CENTER_NOTE_XY[1] < drawing.WIRE_HOLE_CENTER_Y
    source = _source()
    assert source.count("add_note(") == 1
    assert "WIRE_HOLE_CENTER_NOTE,\n            *WIRE_HOLE_CENTER_NOTE_XY" in source
    assert "add_edge_dimension(\n        adapter,\n        front," in source
    assert "add_native_hole_callout(\n        adapter,\n        front," in source
    for removed in (
        "create_detail_view",
        "model_point_in_view",
        'detail_label="A"',
        '"*Right"',
    ):
        assert removed not in source
    for removed_constant in (
        "DETAIL_CENTER",
        "DETAIL_RADIUS",
        "DETAIL_SCALE",
        "RIGHT_CENTER",
    ):
        assert not hasattr(drawing, removed_constant)


def test_drawn_stock_has_no_owned_machining_tolerance() -> None:
    assert not hasattr(pen_rod_spec, "SECTION_BAND")
    assert model_toleranced_dimensions(part) == {}
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert "set_dimension_bilateral_tolerance" not in part_source
    assert "deviations(SECTION_BAND)" not in part_source
    assert pen_rod_spec.DRAWING_DIMENSIONS == {"RodProfile": {"Length"}}


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = pen_rod_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert notes == "5 SQ DRAWN BRASS BAR FACES OK AS RECEIVED."
    # The drill rides the hole callout; deburr is a title-block row; the
    # v-block role is design intent.
    for banned in ("DRILL", "#47", "DEBURR", "V-BLOCK", "WITHIN", "+/-", "UOS", "X.XX"):
        assert banned not in notes, banned
    source = _source()
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "def _manufacturing_notes" not in source


def test_print_carries_no_gdt_or_finish_symbols() -> None:
    """Drawn bar passed as received: no datums, no frames, no Ra (rules 3, 5).

    Machinist review 2026-09-02: the lone Ra 1.6 on a drawn face defeated the
    as-received note and its leader crossed the 145.00 and the right view.
    """
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert pen_rod_spec.PART_DATUMS == ()
    assert pen_rod_spec.GEOMETRIC_CONTROLS == ()
    assert pen_rod_spec.SURFACE_FINISHES == ()
    assert not hasattr(pen_rod_spec, "GEOMETRIC_TOLERANCES_MM")
    assert "surface_finish_by_key" not in source
    assert "roughness_ra=" not in source
    # The part build keeps its author_part_pmi call shape on the empty tuples.
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert "author_part_pmi(" in part_source
    assert "datums=PART_DATUMS" in part_source
    assert "controls=GEOMETRIC_CONTROLS" in part_source
    assert "surface_finishes=SURFACE_FINISHES" in part_source


def test_hidden_lines_stay_on_in_both_orthographic_views() -> None:
    source = _source()
    assert "for view in (front, top):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    source = _source()
    assert source.count("place_view(") == 3
    for orientation in ('"*Front"', '"*Top"', '"*Isometric"'):
        assert source.count(orientation) == 1
    assert source.count("scale=(1, 1)") == 2
    assert source.count("scale=(4, 1)") == 1
    assert "DETAIL_SCALE" not in source
    assert pen_rod_spec.TOP_VIEW_NOTE == "TOP VIEW SCALE 4:1"
    assert 'add_property_linked_note(adapter, "Top View Note"' in source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("pen-rod")
    assert "brass" in str(config["material_specification"]).lower()
    assert config["finish"]
    assert int(config["quantity"]) == 1
