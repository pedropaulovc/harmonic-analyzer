"""Offline contracts for the wheel-bar drawing.

The print follows cad/docs/drawing-simplicity-policy.md: a clamped support bar
is not on the GD&T allowlist and nothing runs on it, so it carries no datum,
frame, roughness symbol or basic dimension; every bore has a native DRILL
callout and a station from the left end on the front view (rule 6: a note is
never a dimension), and the one note is the stock licence.
"""

from __future__ import annotations

from pathlib import Path

import build_wheel_bar as part
import draw_wheel_bar as drawing
import wheel_bar_spec
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


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


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = wheel_bar_spec.DRAWING_NOTES
    # Every hole size and station is on the front view now; the one note is
    # the stock licence.
    assert notes == "10 X 9 BAR STOCK FACES OK AS RECEIVED."
    # The callouts DISPLAY the Hole Wizard cut, so the geom's quoted diameters
    # must be the wizard's exact clearance cuts.
    assert wheel_bar_spec.CLAMP_HOLE_DIA == 4.978
    assert wheel_bar_spec.PEN_HANGER_HOLE_DIA == 3.912
    assert part.blind_cut_dia_mm(part.CLAMP_HOLE_SPEC) == wheel_bar_spec.CLAMP_HOLE_DIA
    assert (
        part.blind_cut_dia_mm(part.SCREW_HOLE_SPEC)
        == wheel_bar_spec.PEN_HANGER_HOLE_DIA
    )
    for banned in (
        "#8",
        "#6",
        "Ø",
        "FROM THE LEFT END",
        "DRILLED",
        "CLEARANCE",
        "DATUM",
        "MHA-",
        "UOS",
        "DIMENSIONS IN",
        "+/-",
        "STEEL",
        "AISI 1018",
        "DEBURR",
        "BREAK SHARP",
        "X.XX",
    ):
        assert banned not in notes, banned
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in _source()


def test_print_carries_no_gdt_finish_or_basic_dimensions() -> None:
    # Policy rules 3-5: not on the allowlist; nothing runs on the bar.
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert not hasattr(wheel_bar_spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(wheel_bar_spec, "SURFACE_FINISHES")


def test_bores_carry_native_drill_callouts_and_stations_from_the_left_end() -> None:
    source = _source()
    # One native Hole Wizard callout per hole FEATURE (the clamp pair reads 2X
    # from its instance count), DRILL as the process prefix, plus the ASME
    # centre marks.
    assert source.count("add_native_hole_callout(") == 1  # inside the loop
    assert 'process="DRILL"' in source
    assert "auto_center_marks(" in source
    assert [(x, dia) for _, x, dia, _ in drawing.HOLE_CALLOUTS] == [
        (wheel_bar_spec.SCREW_HOLE_X, wheel_bar_spec.PEN_HANGER_HOLE_DIA),
        (wheel_bar_spec.CLAMP_HOLE_X[0], wheel_bar_spec.CLAMP_HOLE_DIA),
    ]
    # Every station is a horizontal linear from the ONE origin (the left end
    # face) to the bore axis (arc endpoint re-anchored to the centre), stacked
    # below the bar shortest span nearest so no extension line crosses a
    # shorter dimension's text.
    assert 'orientation="horizontal"' in source
    assert "set_arc_endpoints_to_center(adapter, station" in source
    assert "p0=END_FACE_PICK" in source
    assert drawing.END_FACE_PICK[0] == drawing.LEFT_END
    stations = [x for x, _, _ in drawing.HOLE_STATIONS]
    assert stations == sorted(stations)
    assert stations == [wheel_bar_spec.SCREW_HOLE_X, *wheel_bar_spec.CLAMP_HOLE_X]
    rows = [xy[1] for _, _, xy in drawing.HOLE_STATIONS]
    assert rows == sorted(rows, reverse=True)
    assert rows[0] < drawing.BAR_BOTTOM
    assert drawing.FRONT_KEEP["Length"][1] < rows[-1]
    for x, dia, _ in drawing.HOLE_STATIONS:
        rim_y = drawing.FRONT_CENTER[1] + dia * drawing._S / 2.0
        assert drawing.END_FACE_PICK[1] > rim_y  # end-face pick clears the circle
    # The rim picks are refined to a real edge rather than trusted blind.
    assert "find_edge_near(" in source
    # The thin-wall end hole remains geometrically 2.5 mm from the end, but
    # displays at .XXX precision so the title-block tolerance yields 2.500.
    assert wheel_bar_spec.SCREW_HOLE_X + wheel_bar_spec.BAR_LENGTH / 2.0 == 2.5
    assert drawing.END_STATION_DECIMALS == 3
    assert "if model_x == SCREW_HOLE_X:" in source
    assert "adapter, station, END_STATION_DECIMALS, label=label" in source
    # The bar depth stays across the right-view section.
    assert 'label="bar-depth overall"' in source


def test_transverse_hole_station_locates_the_common_axis_without_crossed_text() -> None:
    # One vertical station, bottom edge -> shared bore axis (arc centre),
    # explicitly applies 5.00 to all three bores.  This removes any inference
    # that the two clamp holes only happen to look centred.
    source = _source()
    assert 'label="transverse hole station"' in source
    assert 'orientation="vertical"' in source
    assert "set_arc_endpoints_to_center(adapter, transverse" in source
    assert drawing.TRANSVERSE_STATION_PREFIX == "3X "
    assert "transverse,\n        TRANSVERSE_STATION_PREFIX," in source
    assert "_add_common_bore_centerline(adapter)" in source
    assert drawing.COMMON_CENTERLINE_X[0] < drawing._front_x(
        wheel_bar_spec.SCREW_HOLE_X
    )
    assert drawing.COMMON_CENTERLINE_X[1] > drawing._front_x(
        wheel_bar_spec.CLAMP_HOLE_X[-1]
    )
    assert source.count("add_edge_dimension(") == 3
    assert drawing.BOTTOM_EDGE_PICK[1] == drawing.BAR_BOTTOM
    assert drawing.BOTTOM_EDGE_PICK[0] > drawing.LEFT_END
    assert drawing.TRANSVERSE_STATION_TEXT_XY[0] < drawing.LEFT_END
    assert drawing.TRANSVERSE_STATION_TEXT_XY[1] < drawing.FRONT_CENTER[1]

    # The 10.00 section height now belongs to the end view, so its former
    # extension line cannot cross the front-view 3X 5.00 text.
    assert set(drawing.FRONT_KEEP) == {"Length"}
    assert set(drawing.RIGHT_KEEP) == {"Side"}
    right_edge = drawing.RIGHT_CENTER[0] + drawing.RIGHT_HALF_Z
    assert drawing.RIGHT_KEEP["Side"][0] > right_edge


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
    assert "for view in (front, right):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("wheel-bar")
    # The library material renders the model; the spec is what the shop buys
    # (the title block's MATERIAL cell shows the spec).
    assert config["material_specification"] == "AISI 1018 cold-finished steel bar"
    assert config["material_specification"] != config["material"]
    assert config["finish"]
    assert int(config["quantity"]) == 1
