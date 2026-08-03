"""Offline contracts for the knife-hanger-stud drawing."""

from __future__ import annotations

from pathlib import Path

import build_knife_hanger_stud as part
import draw_knife_hanger_stud as drawing
import knife_hanger_stud_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_catalog import DriveStyle, HeadStyle, fastener


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/knife-hanger-stud.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/knife-hanger-stud.pdf")
    assert drawing.PNG.as_posix().endswith("/png/knife-hanger-stud_drawing.png")
    assert DRAWINGS_BY_NAME["knife_hanger_stud"].script == (
        Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    # The end view carries the washer diameter (the stack's outermost circle),
    # the side view the three stack lengths; together they cover exactly the
    # marked set.
    assert set(drawing.END_KEEP) == set().union(*spec.END_VIEW_DIMENSIONS.values())
    assert set(drawing.SIDE_KEEP) == set().union(*spec.SIDE_VIEW_DIMENSIONS.values())
    assert set(drawing.END_KEEP) | set(drawing.SIDE_KEEP) == marked
    assert spec.END_VIEW_DIMENSIONS.keys() | spec.SIDE_VIEW_DIMENSIONS.keys() == (
        spec.DRAWING_DIMENSIONS.keys()
    )


def test_catalog_is_the_single_source_of_the_thread() -> None:
    catalog = fastener("knife-hanger-stud")
    assert spec.THREAD == catalog.thread == "1/2-13"
    assert spec.SHANK_DIA == catalog.model_diameter_mm == 12.7
    assert spec.SHANK_LEN == catalog.length_mm
    assert spec.THREAD_DESIGNATION == f"{catalog.thread} UNC-2A"
    assert spec.THREAD_DESIGNATION in spec.DRAWING_NOTES
    assert catalog.head is HeadStyle.HEX_STACK
    assert catalog.drive is DriveStyle.EXTERNAL_HEX
    assert drawing.DIMENSION_CALLOUTS == {}


def test_stack_arithmetic_matches_the_top_frame_rederive_contract() -> None:
    # Shank: 12 thread engagement + 0.25 mount gap + 36.5 crossbar = 48.75;
    # stack above the casting top face: washer 2.5 + hex 11 + collar 3 +
    # tip 4; ONE merged part, machine y 987.45 .. 1056.7.
    assert spec.THREAD_LEN == 12.0
    assert spec.MOUNT_GAP == 0.25
    assert spec.CROSSBAR_SPAN == 36.5
    assert spec.THREAD_LEN + spec.MOUNT_GAP + spec.CROSSBAR_SPAN == spec.SHANK_LEN
    assert spec.SHANK_LEN == 48.75
    assert (spec.WASHER_DIA, spec.WASHER_T) == (28.0, 2.5)
    assert (spec.NUT_AF, spec.NUT_H) == (19.0, 11.0)
    assert (spec.COLLAR_DIA, spec.COLLAR_H) == (11.0, 3.0)
    assert (spec.TIP_DIA, spec.TIP_LEN) == (6.0, 4.0)
    assert spec.TOTAL_LEN == 69.25
    assert 987.45 + spec.TOTAL_LEN == 1056.7
    # The plain shank rides the crossbar's 1/2-close clearance bore.
    assert spec.SHANK_DIA < 13.49


def test_lengths_are_marked_extrude_depth_model_dims() -> None:
    # The vertical (axis +Y) profile cannot point-select the edge-on stack
    # steps, so the three lengths ship as extrude-DEPTH model dimensions:
    # the build names them, the drawing inserts them in the side view.
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'name_dimensions(adapter, "Shank", ["ShankLg"])' in part_source
    assert 'name_dimensions(adapter, "HexNut", ["NutHt"])' in part_source
    assert 'name_dimensions(adapter, "Tip", ["TipLg"])' in part_source
    assert spec.SIDE_VIEW_DIMENSIONS == {
        "Shank": {"ShankLg"},
        "HexNut": {"NutHt"},
        "Tip": {"TipLg"},
    }
    draw_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "side_keep=SIDE_KEEP" in draw_source


def test_partial_thread_note_completely_defines_the_unmodeled_features() -> None:
    # thread_control_notes assumes a full-length thread; the stud is threaded
    # on the lower 12 only, so the spec spells the contract out directly.
    notes = spec.DRAWING_NOTES
    assert "1/2-13 UNC-2A PER ASME B1.1-2024, LOWER END X 12.00 LONG." in notes
    assert "13.49 CLOSE-CLEARANCE BORE" in notes
    assert "HEX 19.00 +/-0.10 ACROSS FLATS X 11.00 +/-0.10 HIGH." in notes
    assert "WASHER DIA 28.00 +/-0.10 X 2.50 +/-0.10 HIGH." in notes
    assert "CENTER DRILL TIP END FACE DIA 2.00 X 1.50 DEEP (COSMETIC)." in notes
    assert "TURN AND MILL FROM ONE BLANK" in notes
    assert "COMMERCIAL" not in notes
    assert "DEBURR" not in notes and "BREAK SHARP" not in notes
    assert max(map(len, notes.splitlines())) < 80


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("knife-hanger-stud")
    assert config["number"] == "MHA-119"
    assert config["material"] == config["material_specification"]
    assert config["finish"]
    assert int(config["quantity"]) == 2
