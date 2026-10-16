"""Offline contracts for the magnifying-clamp drawing."""

from __future__ import annotations

from pathlib import Path

import pytest

import build_mg_magnifying_clamp as part
import draw_mg_magnifying_clamp as drawing
import mg_magnifying_clamp_spec as spec
import mg_rod_clamp_joint as joint
from _drawing_registry import DRAWINGS_BY_NAME


def test_surface_finish_is_part_owned_and_consumed_by_key() -> None:
    (control,) = spec.SURFACE_FINISHES
    assert control.key == "lever_bore"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == spec.LEVER_BORE_DIA
    assert control.face.contains_y_mm == spec.LEVER_BORE_Y
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "surface_finishes=SURFACE_FINISHES" in part_source
    assert 'surface_finish_by_key(SURFACE_FINISHES, "lever_bore")' in drawing_source
    assert "roughness_ra=" not in drawing_source


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/mg-magnifying-clamp.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/mg-magnifying-clamp.pdf")
    assert drawing.PNG.as_posix().endswith("/png/mg-magnifying-clamp_drawing.png")
    assert (
        DRAWINGS_BY_NAME["mg_magnifying_clamp"].script == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    assert part.DRAWING_PRECISION is spec.DRAWING_PRECISION
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.RIGHT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    assert spec.REFERENCE_DIMENSIONS <= set(drawing.TOP_KEEP)


def test_drawing_contract_is_split_from_the_assembly_nominals() -> None:
    # The hex and bore stations the assembly imports live in the drawing-FREE
    # geom module, so a print-note edit cannot enter the assembly recipe.
    import mg_magnifying_clamp_geom as geom

    assert geom.HEX_AF == pytest.approx(7.0 / 16.0 * 25.4)
    assert geom.BLOCK_DEPTH == pytest.approx(geom.HEX_AC)
    assert (geom.LEVER_BORE_Y, geom.BLOCK_HEIGHT) == (19.65, 28.65)
    for gone in ("BLOCK_WIDTH", "ROD_BORE_DIA", "ROD_BORE_X"):
        assert not hasattr(geom, gone)
    assembly = Path(part.__file__).with_name("build_mg_magnifier_assembly.py").read_text(
        encoding="utf-8"
    )
    assert "from mg_magnifying_clamp_geom import" in assembly
    assert "from build_mg_magnifying_clamp import" not in assembly


def test_worst_case_walls_and_engagement_hold_the_contract() -> None:
    for name, (nominal, worst) in spec.WALLS.items():
        assert worst >= spec.WALL_TARGET, name
        assert nominal >= worst, name
    assert spec.WALLS["rod-tap drill point to the lever bore"][1] == pytest.approx(
        spec.ROD_TAP_FLOOR_WALL_WORST
    )
    assert spec.BORE_WALL_STATED_MIN == 2.00
    assert spec.BORE_WALL_STATED_MIN <= spec.BORE_WALL_WORST_PRINTED
    assert spec.BORE_OFFSET_MAX > spec.BORE_WANDER
    assert spec.THUMB_ENGAGEMENT_WORST >= joint.ENGAGEMENT_MIN
    assert joint.ENGAGEMENT_WORST >= joint.ENGAGEMENT_MIN
    assert spec.TAP_REACH_NEEDED <= spec.PLUG_TAP_USABLE_LENGTH
    assert spec.TAP_STOP_WINDOW > 0.0
    assert spec.THUMB_DRILL_NEAR_CLEAR > 0.0 and spec.THUMB_DRILL_FAR_CLEAR > 0.0
    assert spec.ROD_TAP_SPEC is joint.ROD_TAP_SPEC


def test_linked_notes_state_stock_wall_taps_and_seat() -> None:
    notes = spec.DRAWING_NOTES
    assert len(notes.splitlines()) <= 4
    assert "7/16 HEX BAR, FLATS AS SUPPLIED" in notes
    assert "BORE TO FLAT WALL 2.00 MIN" in notes
    assert "THREAD ENDS AT LEVER BORE" in notes
    assert "MHA-MG-004 SHOULDER SEAT" in notes
    assert "MHA-MG-003" in spec.LEVER_BORE_CALLOUT
    for stale in ("SKEW", "5.2", "Ø5 VERTICAL ROD"):
        assert stale not in notes
    assert "BRASS" not in notes and "C36000" not in notes
    assert "DEBURR" not in notes and "BREAK SHARP" not in notes
    assert "X.XX" not in notes
    assert "LINEAR +/-" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_native_gdt_section_and_tap_callouts() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 1
    assert source.count("add_feature_control_frame(") == 1
    assert 'characteristic="parallelism"' in source
    assert source.count("add_surface_finish(") == 1
    assert source.count("create_section_view(") == 1
    # Both #4-40 taps print native Hole Wizard callouts at the .XX depth places.
    assert source.count("add_native_hole_callout(") == 2
    assert set(spec.TAP_CALLOUT_PRECISION.values()) == {joint.HOLE_DEPTH_PLACES}


def test_thumb_tap_reference_thread_depth_brackets_only_the_thread() -> None:
    definitions = {5: "TAP INTO BORE", 7: "<hw-threaddepth> <hw-tapdrldepth>"}
    wanted = drawing.reference_thread_depth_definitions(definitions)
    assert wanted[7] == "(<hw-threaddepth>) <hw-tapdrldepth>"
    with pytest.raises(RuntimeError):
        drawing.reference_thread_depth_definitions(wanted)


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("mg-magnifying-clamp")
    assert config["material"] == config["material_specification"]
    assert config["finish"]
    assert int(config["quantity"]) == 1
