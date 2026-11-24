"""Offline contracts for the pen rod and its drawing."""

from __future__ import annotations

import ast
import math
import re
from pathlib import Path

import pytest

import build_pn_pen_rod as part
import draw_pn_pen_rod as drawing
import pn_pen_rod_groove_spec as groove
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


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pn-pen-rod.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pn-pen-rod.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pn-pen-rod_drawing.png")
    assert DRAWINGS_BY_NAME["pn_pen_rod"].script == Path(drawing.__file__).resolve()


def test_drawing_keeps_exactly_the_marked_dimensions() -> None:
    # The sheet's dimensions are the rod spec's plus the groove's (#2439),
    # one union shared by the part's marks and the drawing's imports.
    union = {**spec.DRAWING_DIMENSIONS, **groove.DRAWING_DIMENSIONS}
    assert not set(spec.DRAWING_DIMENSIONS) & set(groove.DRAWING_DIMENSIONS)
    assert part.DRAWING_DIMENSIONS == union
    assert drawing.DRAWING_DIMENSIONS == union
    marked = set().union(*union.values())
    keeps = (drawing.SIDE_KEEP, drawing.END_KEEP, drawing.DETAIL_KEEP)
    assert sum(len(keep) for keep in keeps) == len(marked)  # no name kept twice
    assert set().union(*keeps) == marked
    assert set(drawing.DRAWING_PRECISION_BY_NAME) == marked
    assert part.DRAWING_PRECISION == {
        **spec.DRAWING_PRECISION,
        **groove.DRAWING_PRECISION,
    }
    # The side view carries the turned rod as the lathe reads it: the square's
    # and the pivot's lengths, the pivot's diameter between its flanks and the
    # shoulder's R MAX; the end view the square's SQ size and the stud tap's
    # stated wall (RV-01); DETAIL B the groove's walls from the shoulder and
    # its floor's Ø.  The square's width (Section) prints nowhere: Depth's SQ
    # states both flats.
    assert set(drawing.SIDE_KEEP) == {
        "Length",
        "PivotLength",
        "PivotDia",
        "ShoulderRadius",
    }
    assert set(drawing.END_KEEP) == {"Depth", "TapWallMin"}
    assert set(drawing.DETAIL_KEEP) == set(groove.GROOVE_DIMENSIONS)
    assert "Section" not in marked


def test_side_view_is_turned_and_proved_before_any_import() -> None:
    """Rule 11: the rod axis lies horizontal (draw_dt_cylinder_gear_shaft's
    turned *Front); the frame every position is computed in is read back by
    projection before HLR, the edge scan or an import uses it."""
    assert drawing.SIDE_ROTATION == -math.pi / 2.0
    # Model +Y (the axis) -> sheet +x, model +X -> sheet -y, centred on the
    # bounding box: the pivot end left, the tapped top face right.
    scale = drawing.SIDE_SCALE[0] / drawing.SIDE_SCALE[1]
    assert drawing._sx(spec.SQUARE_LENGTH) - drawing._sx(-spec.PIVOT_LENGTH) == (
        pytest.approx(spec.TOTAL_LENGTH * scale / 1000.0)
    )
    mid = (drawing._sx(-spec.PIVOT_LENGTH) + drawing._sx(spec.SQUARE_LENGTH)) / 2.0
    assert mid == pytest.approx(drawing.SIDE_CENTER[0])
    assert drawing._sy(spec.ROD_SECTION / 2.0) < drawing.SIDE_CENTER[1]
    # DETAIL B (#2439) is a model view turned the same way, so its groove
    # reads like the side view, pivot end left.
    assert (
        drawing._detail_xy(0.0, 0.0)[0]
        > drawing._detail_xy(0.0, -groove.GROOVE_FAR_STATION)[0]
    )
    assert drawing._detail_xy(1.0, 0.0)[1] < drawing._detail_xy(0.0, 0.0)[1]


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


def test_sizes_are_references_and_name_their_mates() -> None:
    # Fit audit 2b-final (rule 4): the square is bought and never cut, so it
    # prints the stock, (.197) SQ, AS SUPPLIED; the pivot is turned to the
    # v-block's drilled bore (form 2), so it prints (Ø.126) REF and note 1's
    # clearance is the requirement.  The part carries no native band.
    assert not hasattr(spec, "DRAWING_BANDS")
    assert model_toleranced_dimensions(part) == {}
    assert "set_dimension_bilateral_tolerance" not in _PART_SOURCE
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in _PART_SOURCE
    assert spec.REFERENCE_DIMENSIONS == frozenset({"Depth", "PivotDia"})
    assert spec.DRAWING_PRECISION["Rod"]["Depth"] == 3
    assert spec.DRAWING_PRECISION["PivotProfile"]["PivotDia"] == 3
    assert "rod.REFERENCE_DIMENSIONS" in _DRAWING_SOURCE
    assert 'diameter=name == "PivotDia"' in _DRAWING_SOURCE
    # Every REF size names its mate (rule 4), the shoulder radius its seat
    # face's part.
    references = spec.REFERENCE_DIMENSIONS | {"ShoulderRadius"}
    assert references <= set(spec.DIMENSION_CALLOUTS)
    assert "Section" not in spec.DRAWING_DIMENSIONS["RodProfile"]
    assert spec.DIMENSION_CALLOUTS["Depth"] == (
        f"SQ, AS SUPPLIED\n{spec.PEN_HANGER_NUMBER} IS CUT TO IT"
    )
    # Rows no longer than the 23 characters the end view's block holds.
    assert max(map(len, spec.DIMENSION_CALLOUTS["Depth"].splitlines())) <= 23
    # The pivot's mate rides note 1, which its SEE NOTE links (rule 7).
    assert spec.PEN_V_BLOCK_NUMBER in spec.DRAWING_NOTES
    assert drawing.DIMENSION_CALLOUTS == {
        **spec.DIMENSION_CALLOUTS,
        **groove.DIMENSION_CALLOUTS,
    }
    # The groove's three .XXX dimensions name the screw it seats on note 2.
    assert set(groove.DIMENSION_CALLOUTS) == set(groove.GROOVE_DIMENSIONS)
    assert set(groove.DIMENSION_CALLOUTS.values()) == {"SEE NOTE 2"}
    assert groove.GROOVE_NOTE_TEXT.startswith("2. ")
    assert groove.SET_SCREW_NUMBER in groove.GROOVE_NOTE_TEXT
    assert part.DRAWING_NOTES.splitlines()[-1] == groove.GROOVE_NOTE_TEXT
    assert "set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)" in (
        _DRAWING_SOURCE
    )


def test_pivot_analysis_band_clears_the_v_block_pivot_bore() -> None:
    import pn_pen_v_block_spec as v_block

    # Owner ruling 2026-11-24, fit audit question 20: the block's bore is
    # drilled #30 and the pivot keeps its .126; the rod restates the drill.
    assert spec.PIVOT_BORE_DIA == v_block.PIVOT_BORE_DIA
    assert spec.PIVOT_BORE_DIA == pytest.approx(0.1285 * 25.4)
    assert spec.PIVOT_DIA == pytest.approx(0.126 * 25.4)
    # Rule 4 form 2: the pivot is turned to that bore.  PIVOT_BAND, no longer
    # printed, is the pin that keeps note 1's clearance in every drilled
    # bore: always a clearance (slip) fit, its range at least .001 wide.
    shaft_max = spec.PIVOT_DIA + spec.PIVOT_BAND[0]
    bore_min = v_block.PIVOT_BORE_DIA + v_block.PIVOT_BORE_BAND[1]
    assert shaft_max < bore_min
    low, high = spec.PIVOT_CLEARANCE_MM
    assert high - low >= 0.001 * 25.4
    assert spec.PIVOT_DIA < spec.ROD_SECTION  # a real shoulder


def test_stud_tap_is_one_blind_wizard_hole_on_the_top_face_axis() -> None:
    assert spec.STUD_TAP_SPEC.kind == "tapped"
    assert spec.STUD_TAP_SPEC.end == "blind"
    assert spec.STUD_TAP_SPEC.size == spec.STUD_THREAD == "#0-80"


def test_stud_tap_drill_leaves_a_plug_tap_lead_at_the_printed_bands() -> None:
    """#1609: the shallowest printed drill clears the deepest printed full
    thread by a plug tap's four chamfered threads plus a pitch."""
    from _printed_tolerance import printed_band_mm

    band = printed_band_mm(spec.STUD_TAP_DEPTH_PLACES, unit=spec.UNIT)
    drill_min = spec.STUD_TAP_SPEC.depth_mm - band
    thread_max = spec.STUD_TAP_SPEC.overrides_mm["ThreadDepth"] + band
    assert drill_min - thread_max == pytest.approx(spec.STUD_TAP_LEAD_ROOM_MIN)
    assert drill_min - thread_max >= 5.0 * 25.4 / 80.0
    # Every depth sits on its printed .XX grid.
    for depth in (
        spec.STUD_TAP_SPEC.depth_mm,
        spec.STUD_TAP_SPEC.overrides_mm["ThreadDepth"],
    ):
        assert depth / 25.4 == pytest.approx(round(depth / 25.4, 2), abs=1e-9)


def test_square_is_bought_key_stock_inside_its_band() -> None:
    """#2438: the square stays as the key stock supplies it, so its whole
    catalogue section lies inside SECTION_BAND (the tap wall's analysis
    band), one bar yields the rod, the title-block finish says the square
    takes no cut and the SQ size prints it AS SUPPLIED (rule 4)."""
    import _config

    low, high = spec.STOCK_SECTION_MIN, spec.STOCK_SECTION_MAX
    assert spec.ROD_SECTION + spec.SECTION_BAND[1] <= low <= high
    assert high <= spec.ROD_SECTION + spec.SECTION_BAND[0]
    assert spec.TOTAL_LENGTH < spec.STOCK_LENGTH_MIN
    row = _config.parts("pn-pen-rod")
    assert spec.STOCK_SKU in str(row["material_specification"])
    assert "square as supplied" in str(row["finish"]).lower()
    assert "AS SUPPLIED" not in spec.DRAWING_NOTES
    assert "AS SUPPLIED" in spec.DIMENSION_CALLOUTS["Depth"]


def test_overall_length_is_one_parenthesised_reference() -> None:
    """Rule 10: the end-to-end length prints once, as a reference."""
    assert spec.TOTAL_LENGTH == spec.SQUARE_LENGTH + spec.PIVOT_LENGTH == 122.414
    assert spec.DRAWING_REFERENCE_PRECISION == 2
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


def test_pivot_fit_route_is_note_1_linked_from_the_diameter() -> None:
    """The pivot's mate and its clearance, the requirement of a pivot turned
    to its bore (rule 4 form 2), ride a numbered note the (Ø.126) REF links
    to (drawing-guidelines.md rules 4 and 7)."""
    assert spec.DIMENSION_CALLOUTS["PivotDia"] == f"SEE NOTE {spec.PIVOT_FIT_NOTE}"
    lines = spec.DRAWING_NOTES.splitlines()
    assert len(lines) <= 4
    assert lines[0].startswith(f"{spec.PIVOT_FIT_NOTE}. ")
    assert spec.PEN_V_BLOCK_NUMBER in spec.DRAWING_NOTES
    # The clearance is what PIVOT_BAND gives in any #30 bore of the DRILLED
    # HOLES row, before the set screw clamps the pivot: the range the set
    # screw's reach to the groove was proved with (pn-pen-rod.yaml N-01).
    from pn_pen_v_block_spec import PIVOT_BORE_BAND, PIVOT_BORE_DIA

    bore = (PIVOT_BORE_DIA + PIVOT_BORE_BAND[1], PIVOT_BORE_DIA + PIVOT_BORE_BAND[0])
    pin = (spec.PIVOT_DIA + spec.PIVOT_BAND[1], spec.PIVOT_DIA + spec.PIVOT_BAND[0])
    assert spec.PIVOT_CLEARANCE_MM == pytest.approx(
        (bore[0] - pin[1], bore[1] - pin[0])
    )
    assert spec.PIVOT_CLEARANCE_MM == pytest.approx((0.0030 * 25.4, 0.0085 * 25.4))
    clearance = "-".join(spec._inch_text(mm) for mm in spec.PIVOT_CLEARANCE_MM)
    assert f"(CLEARANCE {clearance})" in spec.DRAWING_NOTES
    assert f"{spec.PEN_V_BLOCK_NUMBER} PIVOT BORE. TURN TO IT" in lines[0]
    assert max(map(len, lines)) <= 53
    # Note 1 stands in the field under the side view, right of the tap's
    # callout and under the R MAX block, left of the title block's top.
    x, y = drawing.NOTES_XY
    r_x, r_y = drawing.SIDE_KEEP["ShoulderRadius"]
    assert y < r_y - 0.00835 - 0.010
    assert x > drawing.TAP_CALLOUT_XY[0] + 0.0228 + 0.010
    assert y - 0.010 > 0.0655 + 0.010
    for note in (spec.END_VIEW_NOTE, spec.ISOMETRIC_VIEW_NOTE):
        assert not re.search(r"\d\.\d|\+/-|±", note), note


def test_end_view_is_lettered_view_a_with_its_arrow_on_the_side_view() -> None:
    """Rule 9: the rescaled end view stands off projection, so it is VIEW A,
    its viewing arrow on the side view pointing onto the tapped top face."""
    assert spec.END_VIEW_NOTE.startswith(f"VIEW {spec.END_VIEW_LETTER} ")
    text_xy, tip_xy = drawing.VIEW_A_ARROW
    top_face_x = drawing._sx(spec.SQUARE_LENGTH)
    assert tip_xy == pytest.approx(
        (top_face_x + drawing.VIEW_ARROW_TIP_GAP, drawing._sy(0.0))
    )
    # The letter right of the tip, level with it, short of the isometric.
    assert text_xy[0] > tip_xy[0]
    assert text_xy[1] - drawing.VIEW_LETTER_HEIGHT / 2.0 == pytest.approx(tip_xy[1])
    assert text_xy[0] + 0.005 < drawing.ISO_CENTER[0] - 0.0091 - 0.010


@pytest.mark.parametrize(
    "name", ["Number", "Material Specification", "Finish", "Quantity"]
)
def test_part_stamps_make_critical_properties(name: str) -> None:
    import _config

    config = _config.parts("pn-pen-rod")
    assert "brass" in str(config["material_specification"]).lower()
    assert config["finish"]
    assert int(config["quantity"]) == 1
