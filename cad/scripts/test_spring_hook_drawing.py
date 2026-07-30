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


def test_linked_notes_describe_the_form() -> None:
    notes = spring_hook_notes.DRAWING_NOTES
    assert "R1.5" in notes
    assert "LINEAR +/-" not in notes
    assert "STEEL WIRE" not in notes
    assert "DEHORN" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "add_surface_finish(" in source
    assert "_shank_silhouette(adapter, front)" in source
    assert "edge_entity=shank_edge" in source


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(hook.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("spring-hook")
    assert spec["material_specification"] == "AISI 1018 steel wire, 1.4 dia, annealed (cold-formable)"
    assert spec["finish"] == "black oxide"
    assert int(spec["quantity"]) == 20


def test_surface_finish_is_part_owned_authored_and_consumed() -> None:
    (control,) = spring_hook_spec.SURFACE_FINISHES
    assert control.key == "shank_seating"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == spring_hook_spec.ROD_DIA
    assert control.face.contains_y_mm == spring_hook_spec.SHANK_RISE / 2.0
    assert (hook.ROD_DIA, hook.SHANK_RISE) == (
        spring_hook_spec.ROD_DIA,
        spring_hook_spec.SHANK_RISE,
    )
    part_source = "".join(Path(hook.__file__).read_text(encoding="utf-8").split())
    assert "surface_finishes=SURFACE_FINISHES" in part_source
    sheet_source = "".join(Path(drawing.__file__).read_text(encoding="utf-8").split())
    assert (
        'control=surface_finish_by_key(SURFACE_FINISHES,"shank_seating")'
        in sheet_source
    )
    assert "roughness_ra=" not in sheet_source
