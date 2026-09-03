"""Offline contracts for the amplitude-bar drawing."""

from __future__ import annotations

from pathlib import Path

import amplitude_bar_spec
import draw_amplitude_bar as drawing
import build_amplitude_bar as bar
from _drawing_registry import DRAWINGS_BY_NAME
from _gtol_spec import PlanarFace


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/amplitude-bar.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/amplitude-bar.pdf")
    assert drawing.PNG.as_posix().endswith("/png/amplitude-bar_drawing.png")
    assert DRAWINGS_BY_NAME["amplitude_bar"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert bar.DRAWING_DIMENSIONS is amplitude_bar_spec.DRAWING_DIMENSIONS
    marked = set().union(*amplitude_bar_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked == {"BarLength"}


def test_part_geometry_matches_the_spec() -> None:
    assert amplitude_bar_spec.BAR_LENGTH == bar.BAR_LENGTH
    assert amplitude_bar_spec.BAR_WIDTH == bar.BAR_WIDTH
    assert amplitude_bar_spec.BAR_DEPTH == bar.BAR_DEPTH
    assert amplitude_bar_spec.BOTTOM_NOTCH_WIDTH == bar.BOTTOM_NOTCH_WIDTH
    assert amplitude_bar_spec.BOTTOM_NOTCH_HEIGHT == bar.BOTTOM_NOTCH_HEIGHT
    assert amplitude_bar_spec.TOP_NOTCH_WIDTH == bar.TOP_NOTCH_WIDTH
    assert amplitude_bar_spec.TOP_NOTCH_HEIGHT == bar.TOP_NOTCH_HEIGHT
    assert amplitude_bar_spec.TOP_PIN_DROP == bar.TOP_PIN_DROP
    assert amplitude_bar_spec.NOTCH_OFFSET == bar.NOTCH_OFFSET
    assert amplitude_bar_spec.TOP_PIN_DIA == 1.994


def test_sheet_runs_at_1_to_4_with_1_to_8_isometric() -> None:
    assert drawing.SHEET_SCALE == (1.0, 4.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 8)" in source  # the isometric override
    assert "scale=(4, 1)" in source  # the top end-view section override
    assert amplitude_bar_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:8"
    # The end view names the end it looks at (machinist review 2026-09-02).
    assert amplitude_bar_spec.END_VIEW_NOTE == "TOP END VIEW SCALE 4:1"
    assert 'add_property_linked_note(adapter, "End View Note"' in source
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_end_features_are_dimensioned_in_enlarged_details() -> None:
    # Policy rule 7: at 1:4 the notches and pin hole are edge-on, so three
    # 4:1 details carry them -- sheet dimensions by edge pick, never a
    # model-item import (which could claim the front view's overall length).
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("create_detail_view(") == 3
    for label in ('detail_label="A"', 'detail_label="B"', 'detail_label="C"'):
        assert label in source, label
    assert drawing.DETAIL_SCALE == (4, 1)
    assert 'place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 4))' in source
    assert source.count("curate_view_dimensions(") == 3
    assert "curate_view_dimensions(adapter, detail" not in source
    assert source.count("add_edge_dimension(") == 8
    for label in (
        "top notch cheek offset",
        "top notch width",
        "top notch depth",
        "bottom notch cheek offset",
        "bottom notch width",
        "bottom notch depth",
        "top pin station across the depth",
        "top pin drop",
    ):
        assert f'label="{label}"' in source, label
    # The pin hole callout says the drill, on the detail where the hole is a
    # visible circle.
    assert source.count("add_native_hole_callout(") == 1
    assert 'process="#47 DRILL"' in source
    assert "edge_xy=pin_rim_bottom" in source
    # Each detail boundary reaches past the feature it enlarges.
    assert drawing.DETAIL_MODEL_RADIUS > amplitude_bar_spec.BAR_LENGTH - drawing.TOP_DETAIL_Y
    assert drawing.TOP_DETAIL_Y - drawing.DETAIL_MODEL_RADIUS < amplitude_bar_spec.TOP_NOTCH_FLOOR_Y
    assert drawing.TOP_DETAIL_Y - drawing.DETAIL_MODEL_RADIUS < amplitude_bar_spec.TOP_PIN_Y
    assert drawing.BOTTOM_DETAIL_Y + drawing.DETAIL_MODEL_RADIUS > amplitude_bar_spec.BOTTOM_NOTCH_HEIGHT
    assert drawing.BOTTOM_DETAIL_Y - drawing.DETAIL_MODEL_RADIUS < 0.0


def test_details_stand_clear_of_each_other_and_the_title_block() -> None:
    radius = drawing.DETAIL_MODEL_RADIUS * drawing._D / 1000.0
    for center in (drawing.DETAIL_A_CENTER, drawing.DETAIL_B_CENTER, drawing.DETAIL_C_CENTER):
        assert center[1] - radius > 0.066 or center[0] + radius < 0.217
    assert drawing.DETAIL_A_CENTER[1] - radius > drawing.DETAIL_B_CENTER[1] + radius
    assert drawing.DETAIL_C_CENTER[0] - radius > drawing.DETAIL_A_CENTER[0] + radius
    assert drawing.DETAIL_B_CENTER[0] - radius > drawing.RIGHT_CENTER[0]


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    # Sizes, locations, the drill and the floor's Ra moved onto the details;
    # the notes keep the stock, the plating allowance, the notch orientation
    # (no view resolves it) and the root radius (drawing-simplicity-policy.md
    # rule 6).
    notes = amplitude_bar_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert "END NOTCHES" in notes
    assert "OPEN TO OPPOSITE ENDS" in notes
    assert "ROOTS R0.40 MAX" in notes
    assert "STOCK" in notes
    assert "AFTER PLATING" in notes
    for moved in ("2.38", "12.70", "3.18", "#47", "DRILL", "6.35 BELOW", "Ra"):
        assert moved not in notes, moved
    # No tolerance in a note, no title-block content, no GD&T prose.
    for banned in (
        "WITHIN", "UOS", "DIMENSIONS IN", "LINEAR +/-", "+/-", "DATUM", "BASIC",
        "STEEL", "CHROME", "MHA-", "CENTRED",
    ):
        assert banned not in notes, banned
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_print_carries_no_gdt_or_basic_dimensions() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert not hasattr(amplitude_bar_spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(amplitude_bar_spec, "GEOMETRIC_CONTROLS")


def test_slide_floor_finish_is_part_owned_authored_and_consumed() -> None:
    # The bottom-notch floor slides on the rocker arm's top edge: the one
    # running surface, the one roughness symbol (policy rule 5); it faces down
    # into the open bottom end (offset = n . p along the outward normal).
    (control,) = amplitude_bar_spec.SURFACE_FINISHES
    assert control.key == "slide_floor"
    assert control.roughness_um == 1.6
    assert control.face == PlanarFace(
        (0.0, -1.0, 0.0), -amplitude_bar_spec.BOTTOM_NOTCH_HEIGHT
    )
    part_source = "".join(Path(bar.__file__).read_text(encoding="utf-8").split())
    assert "author_part_pmi(adapter,surface_finishes=SURFACE_FINISHES)" in part_source
    sheet_source = "".join(Path(drawing.__file__).read_text(encoding="utf-8").split())
    assert (
        'control=surface_finish_by_key(SURFACE_FINISHES,"slide_floor")'
        in sheet_source
    )
    assert "roughness_ra=" not in sheet_source
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_surface_finish(") == 1
    assert "detail_b,\n        edge_xy=slide_floor" in source


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert (
        "for view in (front, right, top, detail_a, detail_b, detail_c):\n"
        "        set_hidden_lines_visible" in source
    )
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(bar.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("amplitude-bar")
    assert spec["material_specification"] == "AISI 1018 cold-rolled steel, 6.35 sq"
    assert spec["finish"] == "bright chrome plated"
    assert int(spec["quantity"]) == 20
