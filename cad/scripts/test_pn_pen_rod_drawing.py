"""Offline contracts for the pen rod and its drawing."""

from __future__ import annotations

import ast
import math
import re
from pathlib import Path

import pytest

import build_pn_pen_rod as part
import draw_pn_pen_rod as drawing
import pn_pen_rod_spec as spec
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import THREAD_MAJOR_MM
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM

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
    keeps = (drawing.SIDE_KEEP, drawing.END_KEEP)
    assert sum(len(keep) for keep in keeps) == len(marked)  # no name kept twice
    assert set().union(*keeps) == marked
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert drawing.DRAWING_PRECISION_BY_NAME is spec.DRAWING_PRECISION_BY_NAME
    # The side view carries the turned rod as the lathe reads it: the square's
    # and the pivot's lengths, the pivot's diameter between its flanks and the
    # shoulder's R MAX; the end view the square's SQ size and the stud tap's
    # stated wall (RV-01).  The square's width (Section) prints nowhere:
    # Depth's SQ states both flats.
    assert set(drawing.SIDE_KEEP) == {
        "Length",
        "PivotLength",
        "PivotDia",
        "ShoulderRadius",
    }
    assert set(drawing.END_KEEP) == {"Depth", "TapWallMin"}
    assert "Section" not in marked


def test_side_view_is_turned_and_proved_before_any_import() -> None:
    """Rule 11: the rod axis lies horizontal (draw_dt_cylinder_gear_shaft's
    turned *Front); the frame every position is computed in is read back by
    projection before HLR, the edge scan or an import uses it."""
    assert drawing.SIDE_ROTATION == -math.pi / 2.0
    tree = ast.parse(_DRAWING_SOURCE)
    curated = [
        ast.unparse(call.args[1]) for call in _calls(tree, "curate_view_dimensions")
    ]
    assert curated == ["side", "end"]
    order = [
        _DRAWING_SOURCE.index(text)
        for text in (
            'place_view(adapter, str(SOURCE), "*Front"',
            "_lay_side_view_horizontal(adapter, side)",
            "_prove_side_view_frame(adapter, side)",
            "for view in (side, end, iso):",
            "*curate_view_dimensions(",
        )
    ]
    assert order == sorted(order)
    # Model +Y (the axis) -> sheet +x, model +X -> sheet -y, centred on the
    # bounding box: the pivot end left, the tapped top face right.
    scale = drawing.SIDE_SCALE[0] / drawing.SIDE_SCALE[1]
    assert drawing._sx(spec.SQUARE_LENGTH) - drawing._sx(-spec.PIVOT_LENGTH) == (
        pytest.approx(spec.TOTAL_LENGTH * scale / 1000.0)
    )
    mid = (drawing._sx(-spec.PIVOT_LENGTH) + drawing._sx(spec.SQUARE_LENGTH)) / 2.0
    assert mid == pytest.approx(drawing.SIDE_CENTER[0])
    assert drawing._sy(spec.ROD_SECTION / 2.0) < drawing.SIDE_CENTER[1]
    # No detail view and no drag: every dimension imports where it prints.
    for retired in ("CreateDetailViewAt4", "DragModelDimension(", "*Bottom"):
        assert retired not in _DRAWING_SOURCE
    assert "move_model_dimension(" not in _DRAWING_SOURCE
    assert not hasattr(drawing, "DETAIL_CENTER")


def test_shoulder_root_is_a_modelled_max_radius() -> None:
    """Rule 16/25: the seat corner is a modelled radius printed as R MAX, not a
    note; its callout names the part it seats on."""
    assert spec.SHOULDER_FILLET_R == 0.2032  # .008
    assert spec.SHOULDER_FILLET_BAND == (0.0, -spec.SHOULDER_FILLET_R)
    assert spec.SHOULDER_FILLET_TOL_TYPE == 6  # swTolMAX
    assert spec.DRAWING_DIMENSIONS["ShoulderFillet"] == {"ShoulderRadius"}
    assert spec.DRAWING_PRECISION["ShoulderFillet"] == {"ShoulderRadius": 3}
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


def test_side_view_layout_stays_clear() -> None:
    """The positions SIDE_KEEP's comment derives; block sizes are the farm
    audit's (20261014T053239477Z: R MAX block x keep-0.0281..keep+0.0265,
    shoulder 8.35 mm under its anchor; Ø block 55.8 mm wide, hanging one
    side of its line, keep y -0.0101..+0.010; (122.5) text top 1.6 mm over
    its anchor; 10.5 text 11.6 mm wide)."""
    border, air = 0.0127, 0.0015
    keep = drawing.SIDE_KEEP
    sx, sy, half = drawing._sx, drawing._sy, spec.ROD_SECTION / 2.0
    square_top, square_bottom = sy(-half), sy(half)
    pivot_end, shoulder = sx(-spec.PIVOT_LENGTH), sx(0.0)
    # Rule 15: 2:1 lays the rod ~245 mm long, inside the border.
    assert drawing.SIDE_SCALE == (2, 1)
    assert sx(spec.SQUARE_LENGTH) - pivot_end == pytest.approx(0.245, abs=5e-4)
    # Three rows above the rod, 10 mm apart, the overall the outermost.
    rows = [keep["Length"][1], keep["PivotLength"][1], drawing.OVERALL_REF_XY[1]]
    assert rows == sorted(rows)
    assert rows[0] - square_top > 0.008
    assert all(b - a >= 0.0099 for a, b in zip(rows, rows[1:]))
    assert shoulder < keep["Length"][0] < sx(spec.SQUARE_LENGTH)
    # The 10.5's text stands centred over its 21 mm span, clear of both
    # extension lines, its arrows forced inside: nothing of it runs left of
    # the pivot end.
    text_x = keep["PivotLength"][0]
    assert text_x - 0.0058 > pivot_end + air
    assert text_x + 0.0058 < shoulder - air
    assert drawing.ARROW_SIDES == {"PivotLength": 0, "Depth": 1}
    assert "_set_arrow_sides(adapter, annotations)" in _DRAWING_SOURCE
    # The Ø's line stands left of the pivot end, where every row's lines
    # start, and rises to its block ABOVE the rows, so it meets the block
    # only at its shoulder (never beside a row of text).
    dia_x, dia_y = keep["PivotDia"]
    assert dia_x < pivot_end - 0.005
    dia_bottom, dia_top = dia_y - 0.0101, dia_y + 0.010
    overall_text_top = drawing.OVERALL_REF_XY[1] + 0.0016
    assert dia_bottom > overall_text_top + 0.005
    assert dia_top < 0.2794 - border - 0.010
    # Hanging either side of its line, the block stays inside the border.
    assert dia_x - 0.0558 > border + 0.005
    # The R MAX block stands down-right of the root, alone under the rod.
    r_x, r_y = keep["ShoulderRadius"]
    r_box = (r_x - 0.0281, r_y - 0.00835, r_x + 0.0265, r_y + 0.00835)
    assert r_box[0] > shoulder + 0.030
    assert r_box[3] < square_bottom - 0.008
    # The iso stands right of the rod's top face, inside the border, its
    # note under it, above the title block.
    iso_half_w, iso_half_h = 0.0091, 0.0577
    assert sx(spec.SQUARE_LENGTH) + 0.030 < drawing.ISO_CENTER[0] - iso_half_w
    assert drawing.ISO_CENTER[1] + iso_half_h < 0.2794 - border - 0.010
    note_x, note_y = drawing.ISO_NOTE_XY
    assert note_y < drawing.ISO_CENTER[1] - iso_half_h - 0.005
    assert note_y - 0.0045 > 0.0655 + 0.010
    assert note_x + 0.060 < 0.4318 - border - 0.005


def test_end_view_layout_stays_clear() -> None:
    """Final review 2026-10-14: at 4:1 the SQ size's bottom row sat on its
    lower extension line.  At 5:1 the four-row block (keep y -10.08 to
    +9.06 mm, 66.6 mm wide, centred on its line) stands between the
    extension lines with air, and the group stays in the lower-left field,
    under everything the side view draws below the rod."""
    border, air = 0.0127, 0.0015
    cx, cy = drawing.END_CENTER
    half = drawing._END_HALF_M
    assert drawing.END_SCALE == (5, 1)
    line_x, keep_y = drawing.END_KEEP["Depth"]
    block = (line_x - 0.0333, keep_y - 0.01008, line_x + 0.0333, keep_y + 0.00906)
    assert block[1] > cy - half + air
    assert block[3] < cy + half - air
    assert block[0] > cx + half + 0.005  # past the centre mark's arm
    # Tap callout (centred on keep x, 45.6 mm wide, shoulder 5.6 mm under
    # keep y) over the square and the block, left of the SQ line's arrow.
    tap_x, tap_y = drawing.TAP_CALLOUT_XY
    tap = (tap_x - 0.0228, tap_y - 0.0056, tap_x + 0.0228, tap_y + 0.0035)
    assert tap[1] > cy + half + 0.010
    assert tap[1] > block[3] + 0.010
    assert tap[2] < line_x - 0.005
    # Scale note (text 4.5 mm under its anchor, END_NOTE_WIDTH long) centred
    # under the square, left of the SQ line's lower arrow, inside the border.
    note_x, note_y = drawing.END_NOTE_XY
    assert note_x + drawing.END_NOTE_WIDTH / 2.0 == pytest.approx(cx)
    assert note_y < cy - half - 0.005
    assert note_y - 0.0045 > border + 0.010
    assert note_x + drawing.END_NOTE_WIDTH < line_x - air
    assert note_x > border + 0.005
    # Lower-left field: left of the title block, under the side view's
    # lowest ink over the group (the R MAX leader and the Ø's tail).
    sx, sy = drawing._sx, drawing._sy
    assert block[2] < 0.2155 - 0.010
    r_x, r_y = drawing.SIDE_KEEP["ShoulderRadius"]
    r_left, r_shoulder = r_x - 0.0281, r_y - 0.00835
    root = (sx(0.0), sy(spec.PIVOT_DIA / 2.0 + spec.SHOULDER_FILLET_R))
    slope = (root[1] - r_shoulder) / (root[0] - r_left)
    leader_y_at_tap = r_shoulder + slope * (tap[2] - r_left)
    assert tap[3] < leader_y_at_tap - 0.010
    assert block[2] < r_left or block[3] < r_shoulder - 0.010
    dia_tail_y = sy(spec.PIVOT_DIA / 2.0) - 0.00635
    assert tap[3] < dia_tail_y - 0.010


def test_stud_tap_wall_is_stated_at_its_printed_worst_case() -> None:
    # Rule 17: the #0-80 major (.060) in the smallest square (.195) leaves
    # .0675 to each flat, over the floor and under the target (RV-01).  The
    # sheet states it as a native .067 MIN, floored so it never claims more
    # wall than the worst case leaves.
    major = THREAD_MAJOR_MM[spec.STUD_THREAD]
    smallest = spec.ROD_SECTION + spec.SECTION_BAND[1]
    largest = spec.ROD_SECTION + spec.SECTION_BAND[0]
    wall = (smallest - major) / 2.0
    assert wall == pytest.approx(0.0675 * 25.4)
    assert WALL_FLOOR_MM <= wall < WALL_TARGET_MM
    assert spec.TAP_WALL_MIN_MM == pytest.approx(0.067 * 25.4)
    assert WALL_FLOOR_MM <= spec.TAP_WALL_MIN_MM <= wall
    assert spec.TAP_WALL_MIN_TOL_TYPE == 5  # swTolType_e.swTolMIN
    # The MIN limit's band reaches the wall in the largest square.
    assert spec.TAP_WALL_MIN_BAND[1] == 0.0
    assert spec.TAP_WALL_MIN_MM + spec.TAP_WALL_MIN_BAND[0] == pytest.approx(
        (largest - major) / 2.0
    )
    # The reference line runs from the thread's major diameter and stays
    # inside the smallest square.
    assert spec.TAP_WALL_START_R == pytest.approx(major / 2.0)
    assert spec.TAP_WALL_START_R + spec.TAP_WALL_MIN_MM < smallest / 2.0


def test_tap_wall_text_stands_on_a_shelf_clear_of_every_line() -> None:
    # The wall's 8.5 mm run is shorter than its two-row text (3.5 mm rows,
    # value over the anchor, TAP WALL under it): the text is offset on a
    # leader left of where its extension lines end (1 mm past its line),
    # inside the border, over the view label and under the tap callout.
    border = 0.0127
    cx, cy = drawing.END_CENTER
    half = drawing._END_HALF_M
    line_x, line_y = drawing.END_KEEP["TapWallMin"]
    rim = drawing._end_y(drawing.END_CENTER, spec.TAP_WALL_START_R)
    end = drawing._end_y(
        drawing.END_CENTER, spec.TAP_WALL_START_R + spec.TAP_WALL_MIN_MM
    )
    assert cy - half < end < line_y < rim < cy
    assert line_x < cx - half - 0.005
    x, y = drawing.TAP_WALL_TEXT_XY
    text_half = len(".067 MIN") * 0.00276 / 2.0
    assert y == line_y
    assert x + text_half < line_x - 0.001 - 0.003
    assert x - text_half > border + 0.005
    note_top = drawing.END_NOTE_XY[1] - 0.001
    assert y - 0.0035 - 0.0015 > note_top + 0.005
    assert y + 0.0035 < drawing.TAP_CALLOUT_XY[1] - 0.0056 - 0.010


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
    # Every banded dimension names its mate (rule 4), the shoulder radius its
    # seat face's part.
    assert {
        name
        for feature, name in spec.DRAWING_BANDS
        if name in spec.DRAWING_DIMENSIONS[feature]
    } | {"ShoulderRadius"} <= set(spec.DIMENSION_CALLOUTS)
    # Section keeps its model band unprinted: Depth's SQ states the width,
    # so the two bands must be one.
    assert ("RodProfile", "Section") in spec.DRAWING_BANDS
    assert "Section" not in spec.DRAWING_DIMENSIONS["RodProfile"]
    assert (
        spec.DRAWING_BANDS[("RodProfile", "Section")]
        == spec.DRAWING_BANDS[("Rod", "Depth")]
    )
    assert spec.DIMENSION_CALLOUTS["Depth"].startswith("SQ")
    assert spec.PEN_HANGER_NUMBER in spec.DIMENSION_CALLOUTS["Depth"]
    assert spec.PEN_V_BLOCK_NUMBER in spec.DIMENSION_CALLOUTS["PivotDia"]
    assert drawing.DIMENSION_CALLOUTS is spec.DIMENSION_CALLOUTS
    assert "set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)" in (
        _DRAWING_SOURCE
    )


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
    assert ast.unparse(callout.args[1]) == "end"
    assert "STUD_TAP_DRILL_DIA / 2.0" in _keywords(callout)["edge_xy"]
    # The title block owns the thread class: the callout drops its ``- 2B``.
    assert (
        'omit_title_block_thread_class(stud_callout, label="adjuster stud blind tap")'
        in _DRAWING_SOURCE
    )


def test_overall_length_is_one_parenthesised_reference() -> None:
    """Rule 10: the end-to-end length prints once, as a reference."""
    assert spec.TOTAL_LENGTH == spec.SQUARE_LENGTH + spec.PIVOT_LENGTH == 122.414
    assert spec.DRAWING_REFERENCE_PRECISION == 2
    tree = ast.parse(_DRAWING_SOURCE)
    (edge,) = _calls(tree, "add_edge_dimension")
    keywords = _keywords(edge)
    assert ast.unparse(edge.args[1]) == "side"
    # Sheet horizontal: the turned view's axis runs along sheet x.
    assert keywords["orientation"] == "'horizontal'"
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
    assert drawing.OVERALL_END_SHEET_XY[0] == drawing._sx(-spec.PIVOT_LENGTH)
    assert drawing.OVERALL_TOP_SHEET_XY[0] == drawing._sx(spec.SQUARE_LENGTH)
    # Mid-span, the outermost row above the rod.
    assert drawing._sx(-spec.PIVOT_LENGTH) < drawing.OVERALL_REF_XY[0]
    assert drawing.OVERALL_REF_XY[0] < drawing._sx(spec.SQUARE_LENGTH)
    assert drawing.OVERALL_REF_XY[1] > drawing.SIDE_KEEP["PivotLength"][1]


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
    with pytest.raises(RuntimeError, match=f"edges near y {-spec.PIVOT_LENGTH:g}"):
        drawing._pivot_end_edge(missing)
    with pytest.raises(RuntimeError, match="found 0"):
        drawing._top_face_edge(ViewEdges(label="fake front", edges=edges.edges[2:]))
    assert drawing._top_face_edge(edges) == "near top"


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
    for note in (spec.END_VIEW_NOTE, spec.ISOMETRIC_VIEW_NOTE):
        assert not re.search(r"\d\.\d|\+/-|±", note), note


def test_view_scales_and_notes_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    assert drawing.SIDE_SCALE == (2, 1)
    assert drawing.END_SCALE == (5, 1)
    assert drawing.ISO_SCALE == (1, 1)
    # Every view off the sheet scale says its own scale.
    assert spec.END_VIEW_NOTE == "VIEW FROM SQUARE END SCALE 5:1"
    assert spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"
    for retired in ("TOP_VIEW_NOTE", "BOTTOM_VIEW_NOTE"):
        assert not hasattr(spec, retired)
    views = {
        ast.literal_eval(call.args[2]): _keywords(call)["scale"]
        for call in _calls(ast.parse(_DRAWING_SOURCE), "place_view")
    }
    assert views == {
        "*Front": "SIDE_SCALE",
        "*Top": "END_SCALE",
        "*Isometric": "ISO_SCALE",
    }
    for retired in ("Top View Note", "Bottom View Note"):
        assert retired not in _DRAWING_SOURCE
        assert retired not in _PART_SOURCE
    for note in ("End View Note", "Isometric View Note"):
        assert f'add_property_linked_note(adapter, "{note}"' in _DRAWING_SOURCE
        assert f'"{note}": ' in _PART_SOURCE


def test_isometric_starts_hidden_lines_removed() -> None:
    # Left at its default Shaded With Edges, finalize_drawing's shading call is
    # a no-op and the iso's cosmetic thread stays draft (farm c0b95549c).
    assert "for view in (side, end, iso):" in _DRAWING_SOURCE


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
