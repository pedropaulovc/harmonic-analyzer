"""Offline contracts for the connecting-rod drawing."""

from __future__ import annotations

from pathlib import Path

import connecting_rod_notes
import connecting_rod_spec
import draw_connecting_rod as drawing
import build_connecting_rod as rod
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/connecting-rod.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/connecting-rod.pdf")
    assert drawing.PNG.as_posix().endswith("/png/connecting-rod_drawing.png")
    assert DRAWINGS_BY_NAME["connecting_rod"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert rod.DRAWING_DIMENSIONS is connecting_rod_notes.DRAWING_DIMENSIONS
    marked = set().union(*connecting_rod_notes.DRAWING_DIMENSIONS.values())
    kept = (
        set(drawing.RING_DETAIL_KEEP)
        | set(drawing.FRONT_KEEP)
        | set(drawing.RIGHT_KEEP)
        | set(drawing.TOP_KEEP)
    )
    assert kept == marked
    # Every marked dimension lives in the ring detail, which is curated FIRST
    # (a marked dimension imports into one view only); the front keeps none.
    assert set(drawing.RING_DETAIL_KEEP) == marked
    assert drawing.FRONT_KEEP == {}
    source = _source()
    assert source.index('view_label="ring detail"') < source.index('view_label="front"')


def test_draw_view_math_matches_the_spec() -> None:
    assert (drawing.CENTER_DISTANCE, drawing.HEAD_TOP_Y) == (
        connecting_rod_spec.CENTER_DISTANCE,
        connecting_rod_spec.HEAD_TOP_Y,
    )
    assert connecting_rod_spec.CENTER_DISTANCE == rod.CENTER_DISTANCE
    assert connecting_rod_spec.RING_BORE_DIA == rod.RING_BORE_DIA
    assert connecting_rod_spec.RING_BORE_DIA_BAND == rod.RING_BORE_DIA_BAND
    assert connecting_rod_spec.SHANK_WIDTH == rod.SHANK_WIDTH
    assert connecting_rod_spec.RING_THICKNESS == rod.RING_THICKNESS
    assert connecting_rod_spec.SHANK_THICKNESS == rod.SHANK_THICKNESS
    assert connecting_rod_spec.HEAD_WIDTH == rod.HEAD_WIDTH
    assert connecting_rod_spec.HEAD_HEIGHT == rod.HEAD_HEIGHT
    assert connecting_rod_spec.HEAD_CROWN_ABOVE_PIN == rod.HEAD_CROWN_ABOVE_PIN
    assert connecting_rod_spec.HEAD_THICKNESS == rod.HEAD_THICKNESS
    # The head detail's picks read the build's head stations.
    assert connecting_rod_spec.HEAD_SHOULDER_RISE == rod.HEAD_SHOULDER_RISE
    assert connecting_rod_spec.HEAD_START_Y == rod.HEAD_START_Y
    assert connecting_rod_spec.SHOULDER_TOP_Y == rod.SHOULDER_TOP_Y
    assert connecting_rod_spec.HEAD_CROWN_CY == rod.HEAD_CROWN_CY
    assert connecting_rod_spec.RING_OUTER_RADIUS == rod.RING_OUTER_RADIUS


def test_sheet_runs_at_1_to_1_with_1_to_2_isometric() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    source = _source()
    assert "scale=(1, 2)" in source  # the isometric override
    assert drawing.LEFT_CENTER == (0.080, 0.171)
    assert connecting_rod_notes.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:2"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source
    # The notes sit below the front view's lowest witness line (the (REF)
    # overall's ring-bottom extension), never across it.
    assert 'add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.036)' in source
    assert drawing._sheet_xy(0.0, connecting_rod_spec.RING_BOTTOM_Y)[1] > 0.036


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = connecting_rod_notes.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert "RING, SHANK AND HEAD SHARE ONE MIDPLANE" in notes
    assert "RING WALL 4.50 MIN AFTER BORING" in notes
    # The as-cast head, the ring and the thicknesses are view dimensions now;
    # the pin hole rides its native callout, the bore its model tolerance and
    # the centre distance a sheet dimension; notes never repeat those, and
    # never repeat the finish field's "bore machined".
    for moved in (
        "PER PATTERN", "MACHINE THE", "DRILL", "#47", "3.00", "2.50", "163.10",
        "30.60",
    ):
        assert moved not in notes, moved
    # Nothing the title block or a dimension already says, no GD&T prose.
    for banned in (
        "UOS", "DIMENSIONS IN", "LINEAR +/-", "+/-", "+0.10", "DATUM", "BASIC",
        "WITHIN", "Ra ", "MHA-", "GRAY-IRON", "BA ", "DRAFT",
    ):
        assert banned not in notes, banned
    assert connecting_rod_notes.CROWN_CALLOUT == "FULL R"
    source = _source()
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_print_carries_no_gdt_or_basic_dimensions() -> None:
    # drawing-simplicity-policy.md rule 3: the pin hole is a centre distance
    # plus a centreline offset the block tolerance holds on all 20 rods, so the
    # rod uses none of its one-control allowance.
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert not hasattr(connecting_rod_spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(connecting_rod_spec, "GEOMETRIC_CONTROLS")
    assert "pin_fcf_rim" not in source


def test_running_bore_keeps_its_finish_and_holes_state_the_process() -> None:
    source = _source()
    assert source.count("add_surface_finish(") == 1
    assert 'label="strap bore finish"' in source
    assert drawing.DIMENSION_CALLOUTS == {"StrapBoreDia": "BORE"}
    assert "+0.10/0" not in source
    assert source.count("add_native_hole_callout(") == 1
    assert 'process="#47 DRILL"' in source
    assert source.count("edge_xy=pin_rim") == 1
    assert 'label="rod centre distance"' in source
    assert 'label="pin C/L from shank flank"' in source
    # The centre distance says C-C; the overall is a (REF) arc-extreme dim.
    assert '_set_below_text(adapter, centre_distance, "C-C"' in source
    assert 'label="overall length"' in source
    assert source.count("set_reference_dimension(") == 1
    assert drawing.OVERALL_TEXT_XY[0] < drawing.CENTER_DISTANCE_TEXT_XY[0]
    # The two ring diameters end their leaders on their circumferences.
    assert drawing.DIAMETER_LEADERS_TO_RIM == ("RingOuterDia", "StrapBoreDia")
    assert drawing._ARROWS_OUTSIDE == 1


def test_details_carry_the_ring_head_and_thickness_step() -> None:
    # Policy rule 7 (machinist review 2026-09-02): the ring callouts, the
    # as-cast head and the 3.00/2.50 step are enlarged, not piled onto 1:1.
    source = _source()
    assert source.count("create_detail_view(") == 3
    for label in ('detail_label="A"', 'detail_label="B"', 'detail_label="C"'):
        assert label in source, label
    assert drawing.RING_DETAIL_SCALE == (2, 1)
    assert drawing.HEAD_DETAIL_SCALE == (3, 1)
    assert drawing.STEP_DETAIL_SCALE == (3, 1)
    # The ring boundary encloses the ring and the shank's root line.
    assert drawing.RING_DETAIL_MODEL_RADIUS > connecting_rod_spec.RING_OUTER_RADIUS
    assert drawing.RING_DETAIL_MODEL_RADIUS > rod.SHANK_START_Y
    # The head boundary spans shoulder root to crown top.
    assert (
        drawing.HEAD_DETAIL_MODEL_CY - drawing.HEAD_DETAIL_MODEL_RADIUS
        < connecting_rod_spec.HEAD_START_Y
    )
    assert (
        drawing.HEAD_DETAIL_MODEL_CY + drawing.HEAD_DETAIL_MODEL_RADIUS
        > connecting_rod_spec.HEAD_TOP_Y
    )
    assert drawing.STEP_DETAIL_MODEL_CY == connecting_rod_spec.RING_OUTER_RADIUS
    assert source.count("add_edge_dimension(") == 8
    for label in (
        "head width",
        "head shoulder rise",
        "head height",
        "ring thickness",
        "shank thickness",
    ):
        assert f'label="{label}"' in source, label
    assert source.count("set_arc_endpoints_to_max(") == 2
    assert source.count("add_attached_note(") == 1
    assert "text=CROWN_CALLOUT" in source
    # The details stand clear of the title block and of each other.
    for center, model_radius, scale in (
        (drawing.RING_DETAIL_CENTER, drawing.RING_DETAIL_MODEL_RADIUS, 2.0),
        (drawing.HEAD_DETAIL_CENTER, drawing.HEAD_DETAIL_MODEL_RADIUS, 3.0),
        (drawing.STEP_DETAIL_CENTER, drawing.STEP_DETAIL_MODEL_RADIUS, 3.0),
    ):
        radius = model_radius * scale / 1000.0
        assert center[1] - radius > 0.066 or center[0] + radius < 0.217
        assert center[0] - radius > 0.013
    assert (
        drawing.HEAD_DETAIL_CENTER[1] - drawing.HEAD_DETAIL_MODEL_RADIUS * 0.003
        > drawing.RING_DETAIL_CENTER[1] + drawing.RING_DETAIL_MODEL_RADIUS * 0.002
    )


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
    assert (
        "for view in (front, left, ring_detail, head_detail, step_detail):\n"
        "        set_hidden_lines_visible" in source
    )
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_strap_bore_tolerance_is_owned_by_the_named_model_dimension() -> None:
    assert connecting_rod_spec.RING_BORE_DIA_BAND == (0.10, 0.00)
    assert model_toleranced_dimensions(rod) == {
        ("StrapBoreProfile", "StrapBoreDia"): "*deviations(RING_BORE_DIA_BAND)"
    }


def test_bore_finish_is_flagged_inside_the_enlarged_bore() -> None:
    # The Ra symbol sits inside the 2:1 bore, up-right of its lower-left rim,
    # so its leader crosses no ring line and no dimension.
    edge_x, edge_y = drawing.BORE_FINISH_EDGE
    symbol_x, symbol_y = drawing.BORE_FINISH_SYMBOL
    assert symbol_x > edge_x
    assert symbol_y > edge_y
    bore_radius = connecting_rod_spec.RING_BORE_DIA / 2.0 * 2.0 / 1000.0
    center_x, center_y = drawing.RING_DETAIL_CENTER
    assert ((symbol_x - center_x) ** 2 + (symbol_y - center_y) ** 2) ** 0.5 < bore_radius
    assert ((edge_x - center_x) ** 2 + (edge_y - center_y) ** 2) ** 0.5 < bore_radius + 1e-6


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(rod.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("connecting-rod")
    assert spec["material_specification"] == "ASTM A48 Class 30 gray cast iron"
    assert spec["finish"] == "black rough cast; bore machined"
    assert int(spec["quantity"]) == 20
