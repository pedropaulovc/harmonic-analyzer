"""Offline contracts for the rocker-arm-support drawing."""

from __future__ import annotations

from pathlib import Path

import draw_rocker_arm_support as drawing
import build_rocker_arm_support as support
import rocker_arm_support_spec as placement
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/rocker-arm-support.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/rocker-arm-support.pdf")
    assert drawing.PNG.as_posix().endswith("/png/rocker-arm-support_drawing.png")
    assert (
        DRAWINGS_BY_NAME["rocker_arm_support"].script
        == Path(drawing.__file__).resolve()
    )


def test_drawing_keeps_exactly_the_marked_dimension_set() -> None:
    marked = set().union(*support.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked


def test_tapped_holes_use_customary_us_thread() -> None:
    # Pedro 2026-07-10: closest customary US thread, not the period series.
    assert support.HOLE_SSIZE == "9/16-12"
    assert support.HOLE_THREAD_CLASS == "2B"
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "insert_hole_table(" in source


def test_hole_table_covers_every_foot_hole_with_ordinary_locations() -> None:
    assert len(support.HOLES) == 4
    points = {drawing._bottom_sheet_xy(hole) for hole in support.HOLES}
    assert len(points) == 4
    half_w = support.BOSS_DEPTH / 2.0 * drawing.VIEW_SCALE / 1000.0
    half_h = support.WIDE * drawing.VIEW_SCALE / 1000.0
    for x, y in points:
        assert abs(x - drawing.BOTTOM_CENTER[0]) <= half_w
        assert abs(y - drawing.BOTTOM_CENTER[1]) <= half_h
    # drawing-simplicity-policy.md rule 4: no frame on this casting, so the
    # table's X LOC / Y LOC are ordinary two-place coordinates, not BASIC.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "basic_locations=False," in source


def test_support_keeps_original_world_placement_and_hold_down_pattern() -> None:
    assert placement.SUPPORT_WORLD_Z == 0.0
    assert {z for _, z in placement.SUPPORT_HOLD_DOWN_XZ} == {
        -60.32,
        60.32,
    }


def test_notes_shrank_to_process_facts() -> None:
    notes = support.DRAWING_NOTES
    # The material is the title block's; the note only licenses as-cast faces.
    assert "AS-CAST SURFACES OK" in notes
    assert "GRAY-IRON" not in notes and "+/-" not in notes
    # Sizes and locations moved onto the views: the chamfer is flagged from
    # the section (with its side), the fillet is a radius on the front view,
    # the web is dimensioned on the section, the window and cavity are
    # located from the outside faces -- so no note carries them or "centred".
    assert "1.27" not in notes
    assert "FILLET" not in notes and "R12.7" not in notes
    assert "6.35" not in notes and "WEB" not in notes
    assert "CENTRED" not in notes
    assert "X.XX" not in notes
    # What stays is what the views cannot show: where the same chamfer
    # recurs, and the tapping setup.
    assert "SAME CHAMFER AS WINDOW RIM" in notes
    assert "TAP 4X 9/16-12 FROM THE FOOT FACE" in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "def _manufacturing_notes" not in source


def test_print_carries_no_gdt_finish_or_basic_dimensions() -> None:
    # drawing-simplicity-policy.md rule 3: a bracket casting carries no
    # frames and no datums; the hole table locates the taps.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert not hasattr(placement, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(placement, "GEOMETRIC_CONTROLS")


def test_notes_are_few_and_never_the_title_block() -> None:
    lines = support.DRAWING_NOTES.split("\n")
    assert len(lines) <= 4
    for banned in ("UOS", "DIMENSIONS IN", "LINEAR +/-", "DATUM", "BASIC", "WITHIN"):
        assert banned not in support.DRAWING_NOTES, banned


def test_window_and_cavity_are_located_from_outside_faces() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for label in (
        "window X off left face",
        "cavity X off left face",
        "cavity Y off foot face",
        "window Y off foot face",
    ):
        assert f'label="{label}"' in source, label
    # Horizontal lanes stack below the front view, shortest nearest the
    # outline (which ends at y = 0.200 - 88.9 * 0.5 / 1000 = 0.15555), and
    # all four clear the bottom view's top edge.
    lanes = drawing.FRONT_LANE_Y
    front_bottom = drawing._front_xy(0.0, -support.HALF_Y)[1]
    bottom_top = drawing.BOTTOM_CENTER[1] + support.WIDE * drawing.VIEW_SCALE / 1000.0
    assert front_bottom > lanes["locate_window"] > lanes["locate_cavity"]
    assert lanes["locate_cavity"] > lanes["window"] > lanes["overall"] > bottom_top + 0.010
    # Vertical lanes stand right of the front outline and left of the taper
    # view's foot, cavity (chained under the marked cavity height) inside the
    # window lane.
    front_right = drawing._front_xy(support.BOSS_DEPTH / 2.0, 0.0)[0]
    taper_left = drawing.RIGHT_CENTER[0] - support.WIDE * drawing.VIEW_SCALE / 1000.0
    assert front_right < drawing.FRONT_LANE_X["cavity"] < drawing.FRONT_LANE_X["window"]
    assert drawing.FRONT_LANE_X["window"] + 0.008 < taper_left
    assert drawing.FRONT_KEEP["CavDepth"][0] == drawing.FRONT_LANE_X["cavity"]
    assert drawing.FRONT_KEEP["WinHeight"][0] == drawing.FRONT_LANE_X["window"]
    assert 'text_xy=(FRONT_LANE_X["cavity"], 0.162)' in source
    # Nothing sits inside the window any more: every marked horizontal is on
    # a lane below the outline, every marked vertical on a lane to the right.
    for name in ("Depth", "WinWidth", "CavWidth"):
        assert drawing.FRONT_KEEP[name][1] < front_bottom, name
    assert 'prefix="4X "' in source
    assert 'label="cavity corner fillet"' in source


def test_web_is_dimensioned_on_a_section_not_to_hidden_lines() -> None:
    # policy rule 7: the web is only ever a hidden line in the orthographic
    # views, so SECTION A-A (cut through the web ring, clear of the cavity
    # fillets) carries its thickness and its location from the foot's
    # outside corner, plus the window's Y location and the rim chamfer flag.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("create_section_view(") == 1
    assert 'section_label="A"' in source
    assert support.CAV < drawing.SECTION_CUT_X < support.BIG
    (x0, y0), (x1, y1) = drawing.SECTION_LINE
    assert x0 == x1  # a vertical cut through the front view
    assert x0 == drawing._front_xy(drawing.SECTION_CUT_X, 0.0)[0]
    front_top = drawing._front_xy(0.0, support.HALF_Y)[1]
    front_bottom = drawing._front_xy(0.0, -support.HALF_Y)[1]
    assert y0 < front_bottom and y1 > front_top
    # The cut line sits right of every horizontal dimension text (all at
    # x = 0.075) and its end letters land where no lane runs.
    assert x0 > drawing.FRONT_CENTER[0] + 0.030
    assert y0 > drawing.FRONT_LANE_Y["locate_window"]
    for label in ("web thickness", "web face off foot flat end", "window Y off foot face"):
        assert f'label="{label}"' in source, label
    assert 'entity_types=("VERTEX", "EDGE")' in source
    assert "label=\"window rim chamfer\"" in source
    assert drawing.CHAMFER_CALLOUT_TEXT == "CHAMFER 1.27 X 45 DEG\nWINDOW RIM, BOTH SIDES"
    assert "add_attached_note(" in source
    # The section stands between the taper view and the isometric, above the
    # hole table.
    assert drawing.RIGHT_CENTER[0] < drawing.SECTION_CENTER[0] < drawing.ISO_CENTER[0]
    assert drawing.SECTION_CENTER[1] - support.HALF_Y * drawing.VIEW_SCALE / 1000.0 > (
        drawing.HOLE_TABLE_ANCHOR[1]
    )


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "for view in (front, right, bottom):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_sheet_runs_1_to_2_with_explicit_view_scales() -> None:
    # A 177.8 mm casting with four views does not fit ASME B at 1:1.
    assert drawing.SHEET_SCALE == (1.0, 2.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    # Every view pins its scale explicitly — an unpinned view auto-scales and
    # silently shifts every coordinate-based pick on it: four placed views
    # plus SECTION A-A.
    assert source.count("scale=(1, 2)") == 5


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(support.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("rocker-arm-support")
    assert "gray cast iron" in str(spec["material_specification"]).lower()
    assert spec["finish"]
    assert int(spec["quantity"]) == 1
