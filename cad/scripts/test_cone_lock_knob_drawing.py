"""Offline contracts for the cone-lock-knob drawing."""

from __future__ import annotations

from pathlib import Path

import build_cone_lock_knob as part
import cone_lock_knob_spec
import draw_cone_lock_knob as drawing
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_catalog import fastener


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/cone-lock-knob.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/cone-lock-knob.pdf")
    assert drawing.PNG.as_posix().endswith("/png/cone-lock-knob_drawing.png")
    assert (
        DRAWINGS_BY_NAME["cone_lock_knob"].script == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is cone_lock_knob_spec.DRAWING_DIMENSIONS
    marked = set().union(*cone_lock_knob_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked
    assert (
        drawing.WASHER_DIA,
        drawing.WASHER_T,
        drawing.BODY_DIA,
        drawing.BODY_TOP,
        drawing.DOME_R,
        drawing.STUD_LEN,
    ) == (
        cone_lock_knob_spec.WASHER_DIA,
        cone_lock_knob_spec.WASHER_T,
        cone_lock_knob_spec.BODY_DIA,
        cone_lock_knob_spec.BODY_TOP,
        cone_lock_knob_spec.DOME_R,
        cone_lock_knob_spec.STUD_LEN,
    )


def test_stud_nominals_track_the_fastener_catalog() -> None:
    stud = fastener("cone-lock-knob")
    assert cone_lock_knob_spec.STUD_DIA == stud.model_diameter_mm
    assert cone_lock_knob_spec.STUD_LEN == stud.length_mm
    assert cone_lock_knob_spec.STUD_THREAD == stud.thread
    assert drawing.DIMENSION_CALLOUTS["StudDia"].startswith(stud.thread)


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = cone_lock_knob_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert "ONE SETUP" in notes
    assert "THREAD RELIEF" in notes
    assert "MASK THE THREAD" in notes
    # The thread designation rides the stud diameter callout, the plating
    # spec the title block's finish field, the blanket tolerance the block.
    assert "1/4-20" not in notes
    assert "ASTM" not in notes
    for banned in ("UOS", "DIMENSIONS IN", "+/-", "DATUM", "MHA-", "X.XX"):
        assert banned not in notes, banned
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "def _manufacturing_notes" not in source


def test_print_carries_no_gdt_finish_or_basic_dimensions() -> None:
    # drawing-simplicity-policy.md rules 3-5: a turned thumb knob is not on
    # the GD&T allowlist and nothing runs on its dome or stud.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert not hasattr(cone_lock_knob_spec, "GEOMETRIC_TOLERANCES_MM")
    assert cone_lock_knob_spec.SURFACE_FINISHES == ()
    assert "author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)" in Path(
        part.__file__
    ).read_text(encoding="utf-8")


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "for view in (front, top):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (3.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("scale=(3, 1)") == 3


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    assert "author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)" in source
    import _config

    config = _config.parts("cone-lock-knob")
    assert "12L14" in str(config["material_specification"])
    assert "chrome" in str(config["finish"])
    assert int(config["quantity"]) == 1
