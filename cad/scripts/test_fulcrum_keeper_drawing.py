"""Offline contracts for the fulcrum-keeper drawing."""

from __future__ import annotations

from pathlib import Path

import build_fulcrum_keeper as part
import draw_fulcrum_keeper as drawing
import fulcrum_keeper_spec
import _config
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/fulcrum-keeper.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/fulcrum-keeper.pdf")
    assert drawing.PNG.as_posix().endswith("/png/fulcrum-keeper_drawing.png")
    assert DRAWINGS_BY_NAME["fulcrum_keeper"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    # The drift alarm: the part-side mark set and the drawing-side keep set
    # are BOTH the shared spec's map.
    assert part.DRAWING_DIMENSIONS is fulcrum_keeper_spec.DRAWING_DIMENSIONS
    marked = set().union(*fulcrum_keeper_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked


def test_geometry_matches_the_top_frame_contract() -> None:
    # The keeper exists to hold the fulcrum shaft 25.2 above the rail top
    # face (1061.4 - 1036.2, the 2026-08-02 rederive contract); its underside
    # relief must clear the 4.5-proud corner-boss land.
    assert fulcrum_keeper_spec.SHAFT_AXIS_H == 25.2
    assert fulcrum_keeper_spec.RELIEF_H > 4.5
    # The Ø6.35 shaft end must float in the ball bore with real clearance.
    assert fulcrum_keeper_spec.BORE_DIA > 6.35
    assert fulcrum_keeper_spec.BALL_DIA > fulcrum_keeper_spec.BORE_DIA


def test_screw_hole_seats_the_frame_side_screw() -> None:
    # The foot screw is the MHA-117 #10-24 slotted cheese head (Ø7 x 3): the
    # counterbore must swallow the head, the drill must clear the #10 major.
    assert fulcrum_keeper_spec.CBORE_DIA_MM > 7.0
    assert fulcrum_keeper_spec.CBORE_DEPTH_MM >= 3.0
    assert fulcrum_keeper_spec.HOLE_DIA_MM > 4.826
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert '"counterbore_fillister"' in source
    assert 'name="FootScrewHole"' in source


def test_sheet_runs_at_2_to_1_with_1_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(2, 1)" in source
    assert "scale=(1, 1)" in source
    assert fulcrum_keeper_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source
    assert "add_native_hole_callout(" in source


def test_print_carries_no_gdt_finish_or_basic_dimensions() -> None:
    # drawing-simplicity-policy.md rule 3: a screwed-down bracket is not on
    # the allowlist, so the datum-B edge resolver went with the datums.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
        "_visible_outboard_lug_edge(",
        "visible_view_entities(",
    ):
        assert helper not in source, helper
    assert not hasattr(fulcrum_keeper_spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(fulcrum_keeper_spec, "GEOMETRIC_CONTROLS")
    assert 'process="DRILL"' in source


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = fulcrum_keeper_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    # The ball-seat process stack and the relief are prose by design.
    assert "Ø9.50 STEEL BALL" in notes
    assert "REAM THE BALL Ø6.50 THRU" in notes
    assert "PRESS THE BALL AFTER BLACK OXIDE" in notes
    assert "RELIEVED TO 4.80" in notes
    # The marked ShaftAxisH owns 25.20; the title block owns material, the
    # 2-off count and the screw's part number; no design-intent narration.
    for banned in (
        "25.20", "AISI", "1018", "2 REQUIRED", "MHA-", "CORNER-BOSS", "FLIPPED",
        "UOS", "DIMENSIONS IN", "LINEAR +/-", "+/-", "DATUM", "BASIC", "WITHIN",
    ):
        assert banned not in notes, banned


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "for view in (front, top, right):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_ball_is_a_separate_pressed_body() -> None:
    # A merged Ø9.5 sphere in the Ø9.5 socket is a zero-thickness tangent
    # boolean (equator-circle contact only) -- the ball must stay its own
    # solid body, like the pinion-handle cross rod.
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "merge_result=False" in source
    assert 'name_last_feature(adapter, "Ball")' in source
    # And the wizard screw hole must land while the part is one body (its
    # placement-face scan reads GetBodies2()[0]).
    assert source.index('name="FootScrewHole"') < source.index('"revolve ball"')


def test_wizard_holes_are_not_fake_marked_dimensions() -> None:
    assert "FootScrewHole" not in part.DRAWING_DIMENSIONS
    marked = set().union(*part.DRAWING_DIMENSIONS.values())
    assert not {name for name in marked if "Hole" in name}


def test_parts_registry_row() -> None:
    config = _config.parts("fulcrum-keeper")
    assert config["number"] == "MHA-120"
    assert config["material"] == "Plain Carbon Steel"
    assert "black oxide" in str(config["finish"])
    assert int(config["quantity"]) == 2
