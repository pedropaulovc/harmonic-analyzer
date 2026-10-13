"""Offline contracts for the pen rod and its drawing."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

import build_pn_pen_rod as part
import draw_pn_pen_rod as drawing
import pn_pen_rod_spec as spec
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME

_PART_SOURCE = Path(part.__file__).read_text(encoding="utf-8")
_DRAWING_SOURCE = Path(drawing.__file__).read_text(encoding="utf-8")
_PART_TREE = ast.parse(_PART_SOURCE)


def _calls(tree: ast.AST, name: str) -> list[ast.Call]:
    """Every call to ``name`` (bare or attribute), in source order."""
    found = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (getattr(node.func, "id", None) or getattr(node.func, "attr", None)) == name
    ]
    return sorted(found, key=lambda node: (node.lineno, node.col_offset))


def _keywords(call: ast.Call) -> dict[str, str]:
    return {kw.arg: ast.unparse(kw.value) for kw in call.keywords if kw.arg}


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pn-pen-rod.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pn-pen-rod.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pn-pen-rod_drawing.png")
    assert DRAWINGS_BY_NAME["pn_pen_rod"].script == Path(drawing.__file__).resolve()


def test_drawing_keeps_exactly_the_marked_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    assert drawing.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    keeps = (drawing.FRONT_KEEP, drawing.TOP_KEEP, drawing.BOTTOM_KEEP)
    assert sum(len(keep) for keep in keeps) == len(marked)  # no name kept twice
    assert set().union(*keeps) == marked
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert drawing.DRAWING_PRECISION_BY_NAME is spec.DRAWING_PRECISION_BY_NAME
    # The dimension each view can show: the Front-sketch profile and the pivot's
    # length in the front view, the mid-plane depth in the top view, the
    # Top-sketch pivot circle end-on in the bottom view.
    assert set(drawing.FRONT_KEEP) == {"Section", "Length", "PivotLength"}
    assert set(drawing.TOP_KEEP) == {"Depth"}
    assert set(drawing.BOTTOM_KEEP) == {"PivotDia"}


def test_bands_are_model_owned_and_name_their_mates() -> None:
    assert spec.DRAWING_BANDS == {
        ("RodProfile", "Section"): spec.SECTION_BAND,
        ("Rod", "Depth"): spec.SECTION_BAND,
        ("PivotProfile", "PivotDia"): spec.PIVOT_BAND,
    }
    assert model_toleranced_dimensions(part) == {
        ("feature_name", "dimension_name"): "*deviations(band)"
    }
    assert "for (feature_name, dimension_name), band in DRAWING_BANDS.items():" in (
        _PART_SOURCE
    )
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in _PART_SOURCE
    for feature, name in spec.DRAWING_BANDS:
        assert name in spec.DRAWING_DIMENSIONS[feature]
        assert name in spec.DIMENSION_CALLOUTS
    assert set(spec.DIMENSION_CALLOUTS) == {name for _, name in spec.DRAWING_BANDS}
    assert spec.PEN_HANGER_NUMBER in spec.DIMENSION_CALLOUTS["Section"]
    assert spec.PEN_HANGER_NUMBER in spec.DIMENSION_CALLOUTS["Depth"]
    assert spec.PEN_V_BLOCK_NUMBER in spec.DIMENSION_CALLOUTS["PivotDia"]
    assert drawing.DIMENSION_CALLOUTS is spec.DIMENSION_CALLOUTS
    assert "set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)" in (
        _DRAWING_SOURCE
    )
    # The pivot band prints at its own three places, not the doc default.
    assert spec.DRAWING_PRECISION["PivotProfile"]["PivotDia"] == 3


def test_pivot_band_clears_the_v_block_pivot_bore() -> None:
    import pn_pen_v_block_spec as v_block

    assert spec.PIVOT_DIA == v_block.PIVOT_BORE_DIA
    shaft_max = spec.PIVOT_DIA + spec.PIVOT_BAND[0]
    bore_min = v_block.PIVOT_BORE_DIA + v_block.PIVOT_BORE_BAND[1]
    assert shaft_max < bore_min  # always a clearance (slip) fit
    assert spec.PIVOT_DIA < spec.ROD_SECTION  # a real shoulder


def test_part_frame_square_is_mid_plane_and_pivot_runs_down() -> None:
    knobs = {
        ast.literal_eval(call.args[1]): ast.unparse(call.args[2])
        for call in _calls(_PART_TREE, "set_global")
    }
    assert knobs == {
        "RodSection": "f'{ROD_SECTION}mm'",
        "SquareLength": "f'{SQUARE_LENGTH}mm'",
        "PivotDia": "f'{PIVOT_DIA}mm'",
        "PivotLength": "f'{PIVOT_LENGTH}mm'",
    }
    planes = [
        ast.literal_eval(call.args[0]) for call in _calls(_PART_TREE, "create_sketch")
    ]
    assert planes == ["Front", "Top"]
    names = [
        ast.literal_eval(call.args[1])
        for call in _calls(_PART_TREE, "name_last_feature")
    ]
    assert names == ["RodProfile", "Rod", "PivotProfile", "Pivot"]
    extrusions = [
        _keywords(call.args[0]) for call in _calls(_PART_TREE, "create_extrusion")
    ]
    assert extrusions == [
        {"depth": "ROD_SECTION", "both_directions": "True"},
        {"depth": "PIVOT_LENGTH", "reverse_direction": "True"},
    ]
    assert "create_cut_extrude" not in _PART_SOURCE
    # Shoulder at y 0, square to the top face, centred on the axis in X.
    assert "(-ROD_SECTION / 2.0, 0.0)" in _PART_SOURCE
    assert "(ROD_SECTION / 2.0, SQUARE_LENGTH)" in _PART_SOURCE
    assert "drives=['\"RodSection\"', '\"SquareLength\"', '\"RodSection\" / 2']" in (
        _PART_SOURCE
    )
    (circle,) = _calls(_PART_TREE, "define_circle")
    assert [ast.unparse(arg) for arg in circle.args[1:4]] == [
        "0.0",
        "0.0",
        "PIVOT_DIA / 2.0",
    ]
    assert _keywords(circle)["drives"] == "(None, None, '\"PivotDia\"')"
    assert 'name_dimensions(adapter, "Rod", ["Depth"])' in _PART_SOURCE
    assert 'name_dimensions(adapter, "Pivot", ["PivotLength"])' in _PART_SOURCE


def test_stud_tap_is_one_blind_wizard_hole_on_the_top_face_axis() -> None:
    assert spec.STUD_TAP_SPEC.kind == "tapped"
    assert spec.STUD_TAP_SPEC.end == "blind"
    assert spec.STUD_TAP_SPEC.size == spec.STUD_THREAD == "#0-80"
    (tap,) = _calls(_PART_TREE, "wizard_holes")
    assert [ast.unparse(arg) for arg in tap.args[1:4]] == [
        "STUD_TAP_SPEC",
        "[[0.0, SQUARE_LENGTH, 0.0]]",
        "(0.0, 1.0, 0.0)",
    ]
    keywords = _keywords(tap)
    assert keywords["name"] == "'StudTap'"
    assert keywords["expect_dia_mm"] == "STUD_TAP_DRILL_DIA"
    assert keywords["placement_dims"] == "[((None, None), (None, None))]"
    assert (
        "blind_hole_volume_mm3(stud_tap.hole_dia_mm, STUD_TAP_SPEC.depth_mm)"
        in _PART_SOURCE
    )
    assert "HoleSpec(" not in _PART_SOURCE
    # The sheet prints the native wizard callout once, on the top view, picked
    # on the tap-drill rim.
    assert _DRAWING_SOURCE.count("add_native_hole_callout(") == 1
    (callout,) = _calls(ast.parse(_DRAWING_SOURCE), "add_native_hole_callout")
    assert ast.unparse(callout.args[1]) == "top"
    assert "STUD_TAP_DRILL_DIA / 2.0" in _keywords(callout)["edge_xy"]
    assert "add_edge_dimension(" not in _DRAWING_SOURCE


def test_slide_axis_is_axis1_through_the_rod_axis() -> None:
    assert part.SLIDE_AXIS == "Axis1"
    (axis,) = _calls(_PART_TREE, "name_bore_axis")
    assert [ast.unparse(arg) for arg in axis.args[1:6]] == [
        "'Front Plane'",
        "0.0",
        "'Right Plane'",
        "0.0",
        "'slide axis'",
    ]
    # No other reference axis may take the Axis1 name first.
    assert "create_axis" not in _PART_SOURCE
    assert "if slide_axis != SLIDE_AXIS:" in _PART_SOURCE
    assert "_blank_ref_axis(adapter, slide_axis)" in _PART_SOURCE


def test_no_gdt_or_part_pmi() -> None:
    """Rule 5: the pen rod is not on the GD&T allowlist."""
    for retired in (
        "PART_DATUMS",
        "GEOMETRIC_CONTROLS",
        "SURFACE_FINISHES",
        "WIRE_HOLE",
    ):
        assert not hasattr(spec, retired), retired
        assert retired not in _PART_SOURCE
        assert retired not in _DRAWING_SOURCE
    for token in ("author_part_pmi", "_part_pmi", "_gtol"):
        assert token not in _PART_SOURCE
    for token in (
        "project_part_pmi",
        "_drawing_gdt",
        "add_feature_control_frame(",
        "add_datum_feature(",
        "set_dimension_basic_tolerance",
    ):
        assert token not in _DRAWING_SOURCE
        assert token not in _PART_SOURCE


def test_notes_are_few_and_carry_no_dimensions() -> None:
    lines = spec.DRAWING_NOTES.splitlines()
    assert 1 <= len(lines) <= 4
    for line in lines:
        assert not re.search(r"\d\.\d|\+/-|±", line), line
    assert "SHOULDER" in spec.DRAWING_NOTES
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in _DRAWING_SOURCE


def test_view_scales_and_notes_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    assert drawing.FRONT_SCALE == (1, 1)
    assert drawing.END_SCALE == (4, 1)
    assert spec.TOP_VIEW_NOTE == "TOP VIEW SCALE 4:1"
    assert spec.BOTTOM_VIEW_NOTE == "BOTTOM VIEW SCALE 4:1"
    views = {
        ast.literal_eval(call.args[2]): _keywords(call)["scale"]
        for call in _calls(ast.parse(_DRAWING_SOURCE), "place_view")
    }
    assert views == {
        "*Front": "FRONT_SCALE",
        "*Top": "END_SCALE",
        "*Bottom": "END_SCALE",
        "*Isometric": "ISO_SCALE",
    }
    for note in ("Top View Note", "Bottom View Note"):
        assert f'add_property_linked_note(adapter, "{note}"' in _DRAWING_SOURCE
        assert f'"{note}": ' in _PART_SOURCE


def test_isometric_starts_hidden_lines_removed() -> None:
    # Left at its default Shaded With Edges, finalize_drawing's shading call is
    # a no-op and the iso's cosmetic thread stays draft (farm c0b95549c).
    assert "for view in (front, top, bottom, iso):" in _DRAWING_SOURCE


@pytest.mark.parametrize(
    "name", ["Number", "Material Specification", "Finish", "Quantity"]
)
def test_part_stamps_make_critical_properties(name: str) -> None:
    assert "apply_drawing_properties" in _PART_SOURCE
    assert "clear_dimensions_for_drawing" in _PART_SOURCE
    assert f'"{name}",' in _PART_SOURCE
    import _config

    config = _config.parts("pn-pen-rod")
    assert "brass" in str(config["material_specification"]).lower()
    assert config["finish"]
    assert int(config["quantity"]) == 1
