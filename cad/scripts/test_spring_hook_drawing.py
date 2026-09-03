"""Offline contracts for the spring-hook drawing."""

from __future__ import annotations

from pathlib import Path

import spring_hook_notes
import spring_hook_spec
import draw_spring_hook as drawing
import build_spring_hook as hook
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/spring-hook.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/spring-hook.pdf")
    assert drawing.PNG.as_posix().endswith("/png/spring-hook_drawing.png")
    assert DRAWINGS_BY_NAME["spring_hook"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert hook.DRAWING_DIMENSIONS is spring_hook_notes.DRAWING_DIMENSIONS
    marked = set().union(*spring_hook_notes.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked


def test_draw_view_math_matches_the_spec() -> None:
    assert spring_hook_spec.ROD_DIA == hook.ROD_DIA
    assert spring_hook_spec.SHANK_RISE == hook.SHANK_RISE
    assert spring_hook_spec.ARM_RUN == hook.ARM_RUN


def test_sheet_runs_at_5_to_1() -> None:
    assert drawing.SHEET_SCALE == (5.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(5, 1)" in source
    assert spring_hook_notes.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 5:1"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = spring_hook_notes.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert "R1.50" in notes
    assert "FORM COLD" in notes
    # No design-intent narration, no GD&T prose, nothing the title block says.
    for banned in (
        "SUMMING-LEVER", "CHANNEL-SPRING", "Ra ", "ANNEALED", "STEEL WIRE",
        "DEHORN", "UOS", "DIMENSIONS IN", "LINEAR +/-", "+/-", "DATUM", "BASIC",
        "WITHIN", "MHA-",
    ):
        assert banned not in notes, banned
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_print_carries_no_gdt_finish_or_basic_dimensions() -> None:
    # drawing-simplicity-policy.md rule 5: the shank seats in the plate bore
    # and hangs there; nothing runs on it, so the silhouette-hunting Ra went.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
        "_shank_silhouette(",
        "visible_view_entities(",
    ):
        assert helper not in source, helper
    assert not hasattr(spring_hook_spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(spring_hook_spec, "GEOMETRIC_CONTROLS")


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "for view in (front, top):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(hook.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("spring-hook")
    assert spec["material_specification"] == "AISI 1018 steel wire, 1.4 dia, annealed (cold-formable)"
    assert spec["finish"] == "black oxide"
    assert int(spec["quantity"]) == 20


def test_surface_finish_set_is_empty_and_still_wired_to_the_part() -> None:
    assert spring_hook_spec.SURFACE_FINISHES == ()
    part_source = "".join(Path(hook.__file__).read_text(encoding="utf-8").split())
    assert "surface_finishes=SURFACE_FINISHES" in part_source
    sheet_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "roughness_ra=" not in sheet_source
    assert "surface_finish_by_key" not in sheet_source
