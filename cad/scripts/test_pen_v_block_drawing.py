"""Offline contracts for the pen-v-block drawing.

The print follows cad/docs/drawing-simplicity-policy.md: the block is
set-screwed to the pen rod, so it carries no datums, frames, roughness
symbols or basic dimensions, and its notes are three lines of process fact.
The marker groove is dimensioned on the end view where it is visible, never
to the top view's hidden edges (machinist review 2026-09-02).
"""

from __future__ import annotations

from pathlib import Path

import pytest

import build_pen_v_block as part
import draw_pen_v_block as drawing
import pen_v_block_spec
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pen-v-block.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pen-v-block.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pen-v-block_drawing.png")
    assert DRAWINGS_BY_NAME["pen_v_block"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    # The drift alarm: the part-side mark set and the drawing-side keep set are BOTH
    # the shared spec's map. build re-exports the SAME object (so it marks exactly the
    # spec), and the drawing keeps exactly its union across the per-view keep-maps --
    # a rename in one script that isn't mirrored in the other fails here, offline.
    assert part.DRAWING_DIMENSIONS is pen_v_block_spec.DRAWING_DIMENSIONS
    marked = set().union(*pen_v_block_spec.DRAWING_DIMENSIONS.values())
    kept = (
        set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP) | set(drawing.RIGHT_KEEP)
    )
    assert kept == marked
    # A callout can only annotate a dimension the print actually shows.
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    # The drawing's view math reads the spec's nominal spans, not a divergent copy.
    assert (drawing.BLOCK_LENGTH, drawing.BLOCK_HEIGHT, drawing.BLOCK_DEPTH) == (
        pen_v_block_spec.BLOCK_LENGTH,
        pen_v_block_spec.BLOCK_HEIGHT,
        pen_v_block_spec.BLOCK_DEPTH,
    )
    assert (drawing.BORE_X, drawing.GROOVE_WIDTH, drawing.SCREW_HOLE_XY) == (
        pen_v_block_spec.BORE_X,
        pen_v_block_spec.GROOVE_WIDTH,
        pen_v_block_spec.SCREW_HOLE_XY,
    )


def test_sheet_runs_at_4_to_1_with_2_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (4.0, 1.0)
    source = _source()
    assert source.count("scale=(4, 1)") == 3
    assert source.count("scale=(2, 1)") == 1  # the isometric override
    assert pen_v_block_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 2:1"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = pen_v_block_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    # The make-or-scrap facts the views cannot show: the groove runs the FULL
    # length (the barrel passes right through, v4_t00612) and the set-screw
    # hole is threaded to suit at assembly.
    assert "FULL LENGTH" in notes
    assert "SET SCREW AT ASSEMBLY" in notes
    assert "STOCK" in notes
    # The drill sizes ride the hole callouts themselves, not the notes.
    assert "DRILL" not in notes
    # Nothing the title block or a dimension already says.
    for banned in (
        "UOS",
        "DIMENSIONS IN",
        "+/-",
        "DATUM",
        "FINISH:",
        "DEBURR",
        "PAINT",
        "X.XX",
    ):
        assert banned not in notes, banned
    source = _source()
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "_NOTES_" not in source


def test_hole_callouts_state_size_and_process() -> None:
    callouts = drawing.DIMENSION_CALLOUTS
    assert callouts["Bore0Dia"] == "2X DRILL THRU"
    assert callouts["ScrewHoleDiaDim"] == "DRILL THRU"
    assert set(callouts) == {"Bore0Dia", "ScrewHoleDiaDim"}


def test_chamfers_are_one_leader_callout_off_the_chamfer_edge() -> None:
    # A 24 mm chamfer-leg dimension line cannot carry "2X ... X 45" without
    # running through the text, so the chamfer is NOT a marked dimension: one
    # attached note, its text derived from the spec nominal, leadered to the
    # right chamfer edge and parked above the block's top-right corner.
    assert drawing.CHAMFER_CALLOUT == f"2X {pen_v_block_spec.CHAMFER:.2f} X 45°"
    assert "Chamfer2dx" not in set().union(*pen_v_block_spec.DRAWING_DIMENSIONS.values())
    source = _source()
    assert source.count("add_attached_note(") == 1
    assert "text=CHAMFER_CALLOUT" in source
    edge_x, edge_y = drawing.CHAMFER_EDGE_XY
    assert edge_x == pytest.approx(
        drawing._sheet_x(pen_v_block_spec.BLOCK_LENGTH - pen_v_block_spec.CHAMFER / 2.0)
    )
    assert edge_y == pytest.approx(
        drawing._front_y(pen_v_block_spec.BLOCK_HEIGHT - pen_v_block_spec.CHAMFER / 2.0)
    )
    note_x, note_y = drawing.CHAMFER_NOTE_XY
    assert note_y > drawing._front_y(pen_v_block_spec.BLOCK_HEIGHT)  # above the block
    assert note_x > drawing.TOP_KEEP["Bore1X"][0]  # right of the 26.00 text
    assert note_x < drawing.RIGHT_LEFT_X  # left of the right view's witness lines


def test_groove_is_dimensioned_on_the_end_view_not_to_hidden_lines() -> None:
    # The groove sketch lives on the Top plane, so its model dimensions could
    # only land in the top view -- where the groove is hidden and the witness
    # lines ran the whole sketch length over the hidden edges.  None of the
    # GrooveProfile dims is marked; the end view gets drawing-added width and
    # offset dimensions across the visible groove walls, and the depth model
    # dimension sits RIGHT of the end view (left of it, its floor witness line
    # ran collinear with the front view's dashed floor).
    assert "GrooveProfile" not in pen_v_block_spec.DRAWING_DIMENSIONS
    marked = set().union(*pen_v_block_spec.DRAWING_DIMENSIONS.values())
    assert {"GrooveWidth", "GrooveZ0"}.isdisjoint(marked)
    assert "GrooveDepth" in drawing.RIGHT_KEEP
    assert "GrooveWidth" not in drawing.TOP_KEEP and "GrooveZ0" not in drawing.TOP_KEEP
    source = _source()
    assert source.count("add_edge_dimension(") == 3
    for label in ('label="groove width"', 'label="groove offset"'):
        assert label in source, label
    assert source.count('orientation="horizontal"') == 2
    # Picks land at mid-groove height, the only band clear of the bores' hidden
    # lines 0.25 mm inside each wall.
    assert drawing.GROOVE_WALL_PICK_Y == pytest.approx(
        drawing.RIGHT_BOTTOM_Y + pen_v_block_spec.GROOVE_DEPTH / 2.0 * 4.0 / 1000.0
    )
    # Layout: the groove depth right of the view, the 18 height further out.
    depth_x, depth_y = drawing.RIGHT_KEEP["GrooveDepth"]
    assert depth_x > drawing.RIGHT_RIGHT_X
    assert depth_y == pytest.approx(drawing.GROOVE_WALL_PICK_Y)
    assert drawing.HEIGHT_TEXT_XY[0] > depth_x
    # Lifting the end view leaves both the horizontal 3.75 / 8.50 text lane
    # and the bottom witness point of the vertical 4.50 dimension clear of the
    # title-block top (~0.065), with a real annotation-height safety band.
    assert drawing.RIGHT_KEEP["Depth"][1] > drawing.RIGHT_TOP_Y
    assert drawing.RIGHT_CENTER[1] > drawing.FRONT_CENTER[1]
    assert drawing.RIGHT_BELOW_LANE_Y < drawing.RIGHT_BOTTOM_Y
    assert drawing.RIGHT_BELOW_LANE_Y - 0.065 >= 0.015
    assert drawing.RIGHT_BOTTOM_Y - 0.065 >= 0.025


def test_set_screw_hole_annotations_sit_outside_the_profile() -> None:
    # The 11.00 height keeps its text mid-way up its own dimension line (not on
    # the hole's centreline witness), right of the block; the size callout sits
    # LEFT of the block at hole height so its leader is short and exits below
    # the chamfer corner.
    cz_x, cz_y = drawing.FRONT_KEEP["ScrewHoleCz"]
    assert cz_x > drawing._sheet_x(pen_v_block_spec.BLOCK_LENGTH)
    assert cz_y == pytest.approx(drawing._front_y(pen_v_block_spec.SCREW_HOLE_XY[1] / 2.0))
    dia_x, dia_y = drawing.FRONT_KEEP["ScrewHoleDiaDim"]
    assert dia_x < drawing._sheet_x(0.0)
    assert dia_x >= 0.020
    assert dia_y == pytest.approx(drawing._front_y(pen_v_block_spec.SCREW_HOLE_XY[1]))
    assert pen_v_block_spec.SCREW_HOLE_XY[1] < pen_v_block_spec.BLOCK_HEIGHT - pen_v_block_spec.CHAMFER


def test_print_carries_no_gdt_finish_or_basic_dimensions() -> None:
    # drawing-simplicity-policy.md rule 3-5: a block pinned to its rod is not
    # on the GD&T allowlist and nothing runs on its bores.
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert not hasattr(pen_v_block_spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(pen_v_block_spec, "GEOMETRIC_CONTROLS")
    assert pen_v_block_spec.SURFACE_FINISHES == ()
    assert "author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)" in Path(
        part.__file__
    ).read_text(encoding="utf-8")


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
    assert "for view in (front, top, right):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source
    assert source.count("set_hidden_lines_removed(") == 1


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("pen-v-block")
    assert "brass" in str(spec["material_specification"]).lower()
    assert "bright brass" in str(spec["finish"]).lower()
    assert int(spec["quantity"]) == 1
