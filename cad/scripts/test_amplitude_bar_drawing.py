"""Offline contracts for the amplitude-bar drawing."""

from __future__ import annotations

import ast
from pathlib import Path

import amplitude_bar_spec
import draw_amplitude_bar as drawing
import build_amplitude_bar as bar
from _drawing_contract import drawing_specification_violations
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
    assert amplitude_bar_spec.BOTTOM_NOTCH_WIDTH == bar.BOTTOM_NOTCH_WIDTH == 3.175
    assert (
        round(amplitude_bar_spec.BOTTOM_NOTCH_HEIGHT, 5)
        == round(bar.BOTTOM_NOTCH_HEIGHT, 5)
        == 2.38125
    )
    assert amplitude_bar_spec.TOP_NOTCH_WIDTH == bar.TOP_NOTCH_WIDTH
    assert amplitude_bar_spec.TOP_NOTCH_HEIGHT == bar.TOP_NOTCH_HEIGHT
    assert amplitude_bar_spec.TOP_PIN_DROP == bar.TOP_PIN_DROP
    assert amplitude_bar_spec.NOTCH_OFFSET == bar.NOTCH_OFFSET == 1.5875
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


def test_end_features_are_documented_in_deterministic_model_crops() -> None:
    # Policy rule 7: at 1:4 the notches and pin hole are edge-on, so three
    # directly placed 4:1 model views are translated onto their actual feature
    # points and cropped without the empty derived-detail outlines.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    calls = tuple(node for node in ast.walk(tree) if isinstance(node, ast.Call))

    def named_calls(name: str) -> tuple[ast.Call, ...]:
        return tuple(
            call
            for call in calls
            if (isinstance(call.func, ast.Name) and call.func.id == name)
            or (isinstance(call.func, ast.Attribute) and call.func.attr == name)
        )

    assert len(named_calls("_place_feature_crop")) == 3
    assert not named_calls("create_detail_view")
    crop_orientations = {
        call.args[1].value
        for call in named_calls("_place_feature_crop")
        if len(call.args) > 1
        and isinstance(call.args[1], ast.Constant)
        and isinstance(call.args[1].value, str)
    }
    assert crop_orientations == {"*Front", "*Right"}
    assert source.count("model_radius_mm=DETAIL_MODEL_RADIUS") == 3
    assert "sw_view.SetViewPosition(double_array(list(translated)), False)" in source
    assert "sw_view.Crop2(False, True, 5)" in source
    assert drawing.DETAIL_SCALE == (4, 1)
    assert (
        'place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 4))'
        in source
    )
    assert len(named_calls("curate_view_dimensions")) == 3
    assert drawing.TOP_NOTCH_GEOMETRY_NOTE == "\n".join(
        (
            "DETAIL A — TOP NOTCH — SCALE 4:1",
            f"CHEEK OFFSET {amplitude_bar_spec.NOTCH_OFFSET:.4f}",
            f"NOTCH WIDTH {amplitude_bar_spec.TOP_NOTCH_WIDTH:.4f}",
            f"NOTCH DEPTH {amplitude_bar_spec.TOP_NOTCH_HEIGHT:.4f}",
        )
    )
    assert drawing.BOTTOM_NOTCH_GEOMETRY_NOTE == "\n".join(
        (
            "DETAIL B — BOTTOM NOTCH — SCALE 4:1",
            f"CHEEK OFFSET {amplitude_bar_spec.NOTCH_OFFSET:.4f}",
            f"NOTCH WIDTH {amplitude_bar_spec.BOTTOM_NOTCH_WIDTH:.4f}",
            f"NOTCH DEPTH {amplitude_bar_spec.BOTTOM_NOTCH_HEIGHT:.4f}",
            "BOTTOM FLOOR FINISH "
            f"Ra {amplitude_bar_spec.SURFACE_FINISHES[0].roughness_ra}",
        )
    )
    assert drawing.TOP_PIN_GEOMETRY_NOTE == "\n".join(
        (
            "DETAIL C — TOP PIN — SCALE 4:1",
            (
                "PIN C/L "
                f"{amplitude_bar_spec.BAR_DEPTH / 2.0:.4f} FROM SIDE FACE"
            ),
            f"PIN C/L {amplitude_bar_spec.TOP_PIN_DROP:.2f} BELOW TOP",
            (
                "#47 DRILL "
                f"<MOD-DIAM>{amplitude_bar_spec.TOP_PIN_DIA:.3f} THRU"
            ),
        )
    )
    note_arguments = {
        call.args[1].id
        for call in named_calls("add_note")
        if len(call.args) > 1 and isinstance(call.args[1], ast.Name)
    }
    assert note_arguments == {
        "TOP_NOTCH_GEOMETRY_NOTE",
        "BOTTOM_NOTCH_GEOMETRY_NOTE",
        "TOP_PIN_GEOMETRY_NOTE",
    }
    # No DETAIL C annotation may select a derived edge: its complete
    # location/process callout is the specification-derived note above.
    assert not named_calls("add_edge_dimension")
    assert not named_calls("add_native_hole_callout")
    removed_detail_selection_names = {
        "_detail_b",
        "_detail_c",
        "_BOTTOM_CHEEK_Y",
        "_INNER_CHEEK_X",
        "_SLIDE_FLOOR_PICK_X",
        "_DEPTH_PICK_X",
        "pin_rim_left",
        "pin_rim_top",
        "pin_rim_bottom",
        "add_edge_dimension",
        "add_native_hole_callout",
        "TOP_NOTCH_FLOOR_Y",
        "TOP_PIN_Y",
        "add_surface_finish",
    }
    identifiers = {
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    } | {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    } | {
        node.asname or node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.alias)
    }
    assert not removed_detail_selection_names.intersection(identifiers)
    assert not named_calls("add_surface_finish")
    # Each detail boundary reaches past the feature it enlarges.
    assert (
        drawing.DETAIL_MODEL_RADIUS
        > amplitude_bar_spec.BAR_LENGTH - drawing.TOP_DETAIL_Y
    )
    assert (
        drawing.TOP_DETAIL_Y - drawing.DETAIL_MODEL_RADIUS
        < amplitude_bar_spec.TOP_NOTCH_FLOOR_Y
    )
    assert (
        drawing.TOP_DETAIL_Y - drawing.DETAIL_MODEL_RADIUS
        < amplitude_bar_spec.TOP_PIN_Y
    )
    assert (
        drawing.BOTTOM_DETAIL_Y + drawing.DETAIL_MODEL_RADIUS
        > amplitude_bar_spec.BOTTOM_NOTCH_HEIGHT
    )
    assert drawing.BOTTOM_DETAIL_Y - drawing.DETAIL_MODEL_RADIUS < 0.0


def test_feature_crops_stand_clear_of_each_other_and_the_title_block() -> None:
    radius = drawing.DETAIL_MODEL_RADIUS * drawing._D / 1000.0
    for center in (
        drawing.DETAIL_A_CENTER,
        drawing.DETAIL_B_CENTER,
        drawing.DETAIL_C_CENTER,
    ):
        assert center[1] - radius > 0.066 or center[0] + radius < 0.217
    assert drawing.DETAIL_A_CENTER[1] - radius > drawing.DETAIL_B_CENTER[1] + radius
    assert drawing.DETAIL_C_CENTER[0] - radius > drawing.DETAIL_A_CENTER[0] + radius
    assert drawing.DETAIL_B_CENTER[0] - radius > drawing.RIGHT_CENTER[0]


def test_feature_crops_and_authored_notes_use_separate_sheet_regions() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    # Every close-up repositions a real model projection before applying its
    # outline-free crop; no parent-view-derived detail circle remains.
    assert "model_point_in_view(" in source
    assert "SetViewPosition(" in source
    assert "Crop2(False, True, 5)" in source
    assert "create_detail_view" not in source

    radius = drawing.DETAIL_MODEL_RADIUS * drawing._D / 1000.0
    # The two upper feature notes sit above their respective detail outlines.
    assert drawing.TOP_NOTCH_GEOMETRY_NOTE_XY[1] > drawing.DETAIL_A_CENTER[1] + radius
    assert drawing.TOP_PIN_GEOMETRY_NOTE_XY[1] > drawing.DETAIL_C_CENTER[1] + radius
    # The bottom-note block is right of DETAIL B and below DETAIL C.
    assert drawing.BOTTOM_NOTCH_GEOMETRY_NOTE_XY[0] > drawing.DETAIL_B_CENTER[0] + radius
    assert drawing.BOTTOM_NOTCH_GEOMETRY_NOTE_XY[1] < drawing.DETAIL_C_CENTER[1] - radius
    # Captions remain above the title block and the long isometric caption is
    # authored leftward rather than against the 418 mm right sheet border.
    assert drawing.END_VIEW_NOTE_XY[1] > 0.065
    assert drawing.ISOMETRIC_VIEW_NOTE_XY == (0.325, 0.088)
    assert drawing.TOP_PIN_GEOMETRY_NOTE_XY[1] > drawing.ISO_CENTER[1] + 0.080


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
        "WITHIN",
        "UOS",
        "DIMENSIONS IN",
        "LINEAR +/-",
        "+/-",
        "DATUM",
        "BASIC",
        "STEEL",
        "CHROME",
        "MHA-",
        "CENTRED",
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
    # running surface, whose part-owned Ra now renders in DETAIL B's
    # selection-free specification note.
    (control,) = amplitude_bar_spec.SURFACE_FINISHES
    assert control.key == "slide_floor"
    assert control.roughness_um == 1.6
    assert control.face == PlanarFace(
        (0.0, -1.0, 0.0), -amplitude_bar_spec.BOTTOM_NOTCH_HEIGHT
    )
    part_source = "".join(Path(bar.__file__).read_text(encoding="utf-8").split())
    assert "author_part_pmi(adapter,surface_finishes=SURFACE_FINISHES)" in part_source
    assert drawing._SLIDE_FLOOR_FINISH is control
    assert f"BOTTOM FLOOR FINISH Ra {control.roughness_ra}" in (
        drawing.BOTTOM_NOTCH_GEOMETRY_NOTE
    )
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert not any(
        isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Name) and node.func.id == "add_surface_finish")
            or (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "add_surface_finish"
            )
        )
        for node in ast.walk(tree)
    )
    assert "roughness_ra=" not in source
    assert drawing_specification_violations(source, filename=drawing.__file__) == ()


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
