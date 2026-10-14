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
    # The dimension each view can show: the Front-sketch profile, the pivot's
    # length and the shoulder fillet's radius in the front view, the mid-plane
    # depth in the top view, the Top-sketch pivot circle end-on in the bottom
    # view.
    assert set(drawing.FRONT_KEEP) == {
        "Section",
        "Length",
        "PivotLength",
        "ShoulderRadius",
    }
    assert set(drawing.TOP_KEEP) == {"Depth"}
    assert set(drawing.BOTTOM_KEEP) == {"PivotDia"}


def test_no_model_dimension_is_imported_into_the_detail() -> None:
    """A detail view takes no model dimension (farm leaf 20261013T234242Z:
    targeted import empty; DragModelDimension refused fleet-wide), so DETAIL A
    only enlarges the corner the front view's R MAX points at."""
    assert not hasattr(drawing, "DETAIL_KEEP")
    assert "detail_annotations" not in _DRAWING_SOURCE
    curated = [
        ast.unparse(call.args[1])
        for call in _calls(ast.parse(_DRAWING_SOURCE), "curate_view_dimensions")
    ]
    assert curated == ["front", "top", "bottom"]
    assert "DragModelDimension(" not in _DRAWING_SOURCE
    assert "move_model_dimension(" not in _DRAWING_SOURCE


def test_shoulder_root_is_a_modelled_max_radius() -> None:
    """Rule 16/25: the seat corner is a modelled radius printed as R MAX, not a
    note; its callout names the part it seats on."""
    assert spec.SHOULDER_FILLET_R == 0.2
    assert spec.SHOULDER_FILLET_BAND == (0.0, -spec.SHOULDER_FILLET_R)
    assert spec.SHOULDER_FILLET_TOL_TYPE == 6  # swTolMAX
    assert spec.DRAWING_DIMENSIONS["ShoulderFillet"] == {"ShoulderRadius"}
    assert spec.DRAWING_PRECISION["ShoulderFillet"] == {"ShoulderRadius": 1}
    assert (
        spec.PIVOT_DIA / 2.0 + spec.SHOULDER_FILLET_R
        < (spec.ROD_SECTION + spec.SECTION_BAND[1]) / 2.0
    )
    assert spec.DIMENSION_CALLOUTS["ShoulderRadius"] == (
        f"SEATS ON PEN V-BLOCK\n{spec.PEN_V_BLOCK_NUMBER}"
    )
    (fillet,) = _calls(_PART_TREE, "add_fillet")
    assert [ast.unparse(arg) for arg in fillet.args] == [
        "SHOULDER_FILLET_R",
        "[[PIVOT_DIA / 2.0, 0.0, 0.0]]",
    ]
    assert 'name_dimensions(adapter, "ShoulderFillet", ["ShoulderRadius"])' in (
        _PART_SOURCE
    )
    assert "tolerance.Type = SHOULDER_FILLET_TOL_TYPE" in _PART_SOURCE
    assert "_shoulder_fillet_max_limit(adapter)" in _PART_SOURCE
    # The sheet proves the import kept the MAX type, the radial form and the
    # callout, on the front view's own annotations.
    assert "_dress_shoulder_radius(adapter, annotations)" in _DRAWING_SOURCE
    assert "int(tolerance.Type) != SHOULDER_FILLET_TOL_TYPE" in _DRAWING_SOURCE
    assert 'DIMENSION_CALLOUTS["ShoulderRadius"]' in _DRAWING_SOURCE
    assert _DRAWING_SOURCE.index(
        "set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)"
    ) < _DRAWING_SOURCE.index("_dress_shoulder_radius(adapter, annotations)")
    # The fence holds the right root only, so one arc shows in the detail.
    fence_x, _ = drawing.DETAIL_FENCE_MM
    assert fence_x - drawing.DETAIL_FENCE_RADIUS_MM > 0.0
    assert drawing.DETAIL_SCALE == (10, 1)


def test_shoulder_layout_stays_clear() -> None:
    title_block_left = 0.2155
    centre, radius = drawing.DETAIL_CENTER, drawing._DETAIL_RADIUS_M
    assert centre[0] + radius < title_block_left
    # The label (~32 mm wide, anchored top centre) stands left of the fence.
    assert drawing.DETAIL_LABEL_XY[0] + 0.016 < centre[0] - radius
    # The R MAX block (~57 x 17 mm) stands up-right of the right shoulder
    # corner, its bottom above the 10.5's upper extension line (the shoulder)
    # and its right end left of the bottom view's note.
    corner = (drawing._fx(spec.PIVOT_DIA / 2.0), drawing._fy(0.0))
    text_x, text_y = drawing.FRONT_KEEP["ShoulderRadius"]
    half_w, half_h = 0.0285, 0.0085
    assert text_x - half_w > drawing._fx(spec.ROD_SECTION / 2.0) + 0.005
    assert text_y - half_h > corner[1] + 0.003
    assert text_x + half_w < drawing.BOTTOM_NOTE_XY[0] - 0.015
    # The fence letter sits between the 10.5's extension lines, clear of its
    # text and under the R MAX leader.
    letter_x, letter_y = drawing.DETAIL_LETTER_XY
    assert drawing._fy(-spec.PIVOT_LENGTH) + 0.002 < letter_y < corner[1] - 0.002
    assert letter_x + 0.004 < drawing.FRONT_KEEP["PivotLength"][0] - 0.0035


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
    assert set(spec.DIMENSION_CALLOUTS) == {name for _, name in spec.DRAWING_BANDS} | {
        "ShoulderRadius"
    }
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
        "ShoulderRadius": "f'{SHOULDER_FILLET_R}mm'",
    }
    planes = [
        ast.literal_eval(call.args[0]) for call in _calls(_PART_TREE, "create_sketch")
    ]
    assert planes == ["Front", "Top"]
    names = [
        ast.literal_eval(call.args[1])
        for call in _calls(_PART_TREE, "name_last_feature")
    ]
    assert names == ["RodProfile", "Rod", "PivotProfile", "Pivot", "ShoulderFillet"]
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
    # The title block owns the thread class: the callout drops its ``- 2B``.
    assert (
        'omit_title_block_thread_class(stud_callout, label="adjuster stud blind tap")'
        in _DRAWING_SOURCE
    )


def test_overall_length_is_one_parenthesised_reference() -> None:
    """Rule 10: the end-to-end length prints once, as a reference."""
    assert spec.TOTAL_LENGTH == spec.SQUARE_LENGTH + spec.PIVOT_LENGTH == 122.5
    assert spec.DRAWING_REFERENCE_PRECISION == 1
    tree = ast.parse(_DRAWING_SOURCE)
    (edge,) = _calls(tree, "add_edge_dimension")
    keywords = _keywords(edge)
    assert ast.unparse(edge.args[1]) == "front"
    assert keywords["orientation"] == "'vertical'"
    assert keywords["text_xy"] == "OVERALL_REF_XY"
    assert keywords["entities"] == "picks"
    assert "picks = (_top_face_edge(edges), _pivot_end_edge(edges))" in (
        _DRAWING_SOURCE
    )
    assert "expected_mm=TOTAL_LENGTH" in _DRAWING_SOURCE
    assert "set_reference_dimension(adapter, display.GetAnnotation()" in (
        _DRAWING_SOURCE
    )
    # No sheet hit-test: leaf 20261014T002718Z could not select the edge-on
    # pivot rim at sheet (0.069, 0.08875).
    assert "OVERALL_TOP_PICK_MM" not in _DRAWING_SOURCE
    assert drawing.OVERALL_END_SHEET_XY[1] == drawing._fy(-spec.PIVOT_LENGTH)
    assert drawing.OVERALL_TOP_SHEET_XY[1] == drawing._fy(spec.SQUARE_LENGTH)
    # Outside the 112.0's dimension line, inside the sheet border.
    assert 0.0127 + 0.010 < drawing.OVERALL_REF_XY[0] < drawing.FRONT_KEEP["Length"][0]


def test_overall_picks_resolve_from_the_scanned_edges() -> None:
    from _drawing_edges import ViewEdge, ViewEdges

    half, top, end = spec.ROD_SECTION / 2.0, spec.SQUARE_LENGTH, -spec.PIVOT_LENGTH

    def line(name, a, b):
        return ViewEdge(edge=name, line=(a, b), circle=None, vertices=(None, None))

    def circle(name, y, r):
        return ViewEdge(
            edge=name, line=None, circle=(0.0, y, 0.0, 0.0, -1.0, 0.0, r), vertices=None
        )

    edges = ViewEdges(
        label="fake front",
        edges=(
            line("far top", (-half, top, -half), (half, top, -half)),
            line("near top", (half, top, half), (-half, top, half)),
            line("left side", (-half, 0.0, half), (-half, top, half)),
            circle("shoulder rim", 0.0, spec.PIVOT_DIA / 2.0 + spec.SHOULDER_FILLET_R),
            circle("pivot end", end, spec.PIVOT_DIA / 2.0),
        ),
    )
    assert drawing._top_face_edge(edges) == "near top"
    assert drawing._pivot_end_edge(edges) == "pivot end"
    missing = ViewEdges(label="fake front", edges=edges.edges[:4])
    with pytest.raises(RuntimeError, match="edges near y -10.5"):
        drawing._pivot_end_edge(missing)
    with pytest.raises(RuntimeError, match="found 0"):
        drawing._top_face_edge(ViewEdges(label="fake front", edges=edges.edges[2:]))
    # Outside the 112.0's dimension line, inside the sheet border.
    assert 0.0127 + 0.010 < drawing.OVERALL_REF_XY[0] < drawing.FRONT_KEEP["Length"][0]


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


def test_no_free_manufacturing_note() -> None:
    """Rules 7/16/25: the shoulder's requirement is the R MAX dimension and its
    callout, so no leaderless sheet note remains."""
    assert not hasattr(spec, "DRAWING_NOTES")
    assert "Manufacturing Notes" not in _PART_SOURCE
    assert "Manufacturing Notes" not in _DRAWING_SOURCE
    assert "NOTES_XY =" not in _DRAWING_SOURCE
    for note in (spec.TOP_VIEW_NOTE, spec.BOTTOM_VIEW_NOTE):
        assert not re.search(r"\d\.\d|\+/-|±", note), note


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
