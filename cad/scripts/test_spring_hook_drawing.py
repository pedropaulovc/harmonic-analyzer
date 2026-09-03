"""Offline contracts for the spring-hook drawing."""

from __future__ import annotations

import math
from pathlib import Path

import spring_hook_notes
import spring_hook_spec
import draw_spring_hook as drawing
import build_spring_hook as hook
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


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
    assert set(drawing.REFERENCE_DIMENSIONS) < set(drawing.FRONT_KEEP)


def test_draw_view_math_matches_the_spec() -> None:
    assert spring_hook_spec.ROD_DIA == hook.ROD_DIA
    assert spring_hook_spec.SHANK_RISE == hook.SHANK_RISE
    assert spring_hook_spec.ARM_RUN == hook.ARM_RUN
    assert spring_hook_spec.ELBOW_R == hook.ELBOW_R
    # The envelope the sheet dimensions: shank end to arm top, flank to tip.
    assert math.isclose(drawing.OVERALL_HEIGHT, 9.8)
    assert math.isclose(drawing.OVERALL_WIDTH, 4.7)


def test_sheet_runs_at_5_to_1() -> None:
    assert drawing.SHEET_SCALE == (5.0, 1.0)
    source = _source()
    assert "scale=(5, 1)" in source
    assert spring_hook_notes.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 5:1"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = spring_hook_notes.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    # Only the cold-forming instruction stays in the block (machinist review
    # 2026-09-02): the angle and the bend radius are called out at the elbow.
    assert "FORM COLD" in notes
    assert "R1.50" not in notes
    assert "90 DEG" not in notes
    for banned in (
        "SUMMING-LEVER", "CHANNEL-SPRING", "Ra ", "ANNEALED", "STEEL WIRE",
        "DEHORN", "UOS", "DIMENSIONS IN", "LINEAR +/-", "+/-", "DATUM", "BASIC",
        "WITHIN", "MHA-",
    ):
        assert banned not in notes, banned
    source = _source()
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_elbow_is_called_out_at_the_bend() -> None:
    # The bend radius is a flag note on the elbow's outer arc; the 90-degree
    # elbow is the model's driven ElbowAngle with a deliberately loose band
    # (a short open wire hook does not need the title block's +/-1 degree).
    assert spring_hook_notes.ELBOW_CALLOUT == "R1.50\nWIRE C/L"
    assert "+/-" not in spring_hook_notes.ELBOW_CALLOUT
    assert spring_hook_notes.ELBOW_ANGLE_DEG == 90.0
    assert spring_hook_notes.ELBOW_ANGLE_TOLERANCE_DEG == 5.0
    assert "ElbowAngle" in spring_hook_notes.DRAWING_DIMENSIONS["HookPath"]
    assert "ElbowAngle" in drawing.FRONT_KEEP
    assert model_toleranced_dimensions(hook) == {
        ("HookPath", "ElbowAngle"): "ELBOW_ANGLE_TOLERANCE_DEG",
    }
    part_source = Path(hook.__file__).read_text(encoding="utf-8")
    assert "expected_degrees=ELBOW_ANGLE_DEG" in part_source
    assert 'path.record("ElbowAngle")' in part_source
    assert "require_driven=True" in part_source
    source = _source()
    assert source.count("add_attached_note(") == 1
    assert 'entity_type="SILHOUETTE"' in source
    assert "text=ELBOW_CALLOUT" in source


def test_overalls_are_sheet_dimensions_and_tangent_lengths_are_reference() -> None:
    # The accessible envelope controls (machinist review 2026-09-02): height
    # on the front view (shank end to arm top), width on the top view (flank
    # to tip, arc condition MAX on the wire circle); rise and arm run read as
    # REFERENCE.
    source = _source()
    assert source.count("add_edge_dimension(") == 2
    assert 'label="overall height"' in source
    assert 'label="overall width"' in source
    assert 'entity_types=("EDGE", "SILHOUETTE")' in source
    assert source.count("set_arc_endpoints_to_max(") == 1
    assert drawing.REFERENCE_DIMENSIONS == ("Rise", "ArmRun")
    assert "set_reference_dimension(adapter, annotation" in source
    assert "set_reference_dimensions(" not in source  # the diameter-glyph variant
    # Picks: the shank end at the front-view bottom, the arm top above it.
    assert drawing.HEIGHT_ARM_TOP_XY[1] > drawing.HEIGHT_END_XY[1]
    assert drawing.WIDTH_TIP_XY[0] > drawing.WIDTH_SHANK_XY[0]
    assert drawing.HEIGHT_TEXT_XY[0] > drawing.HEIGHT_ARM_TOP_XY[0]


def test_print_carries_no_gdt_finish_or_basic_dimensions() -> None:
    # drawing-simplicity-policy.md rule 5: the shank seats in the plate bore
    # and hangs there; nothing runs on it, so the silhouette-hunting Ra went.
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
        "_shank_silhouette(",
        "visible_view_entities(",
        "set_dimension_symmetric_angular_tolerance(",
    ):
        assert helper not in source, helper
    assert not hasattr(spring_hook_spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(spring_hook_spec, "GEOMETRIC_CONTROLS")
    # The band stays out of the channel-assembly closure (spring_hook_spec is
    # imported by build_channel_assembly).
    assert not hasattr(spring_hook_spec, "ELBOW_ANGLE_TOLERANCE_DEG")


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
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
    sheet_source = _source()
    assert "roughness_ra=" not in sheet_source
    assert "surface_finish_by_key" not in sheet_source
