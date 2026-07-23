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
        drawing.STUD_DIA,
        drawing.STUD_LEN,
    ) == (
        cone_lock_knob_spec.WASHER_DIA,
        cone_lock_knob_spec.WASHER_T,
        cone_lock_knob_spec.BODY_DIA,
        cone_lock_knob_spec.BODY_TOP,
        cone_lock_knob_spec.DOME_R,
        cone_lock_knob_spec.STUD_DIA,
        cone_lock_knob_spec.STUD_LEN,
    )


def test_stud_nominals_track_the_fastener_catalog() -> None:
    stud = fastener("cone-lock-knob")
    assert cone_lock_knob_spec.STUD_DIA == stud.model_diameter_mm
    assert cone_lock_knob_spec.STUD_LEN == stud.length_mm
    assert cone_lock_knob_spec.STUD_THREAD == stud.thread
    assert drawing.DIMENSION_CALLOUTS["StudDia"].startswith(stud.thread)


def test_linked_notes_define_remaining_knob_operations() -> None:
    notes = cone_lock_knob_spec.DRAWING_NOTES
    assert "1/4-20" in notes
    assert "THREAD RELIEF" in notes
    assert "CHROME PLATE PER ASTM B456" in notes
    assert "DOME R5" in notes
    # The blanket tolerance lives in the title block ONLY -- a second general
    # tolerance in the notes would conflict with it (codex machinist review).
    assert "+/-0.25" not in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "def _manufacturing_notes" not in source


def test_native_gdt_ties_seat_and_flange_to_the_turned_axis() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 1
    assert source.count("add_feature_control_frame(") == 2
    assert source.count('characteristic="perpendicularity"') == 1
    assert source.count('characteristic="circular_runout"') == 1
    assert source.count("add_surface_finish(") == 1
    assert (
        'symbol_xy=(0.124880, 0.253823),\n        datum="A",\n'
        '        label="knob body axis"'
        in source
    )
    assert "symbol_xy=(0.128, 0.255)" not in source


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (3.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("scale=(3, 1)") == 3


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("cone-lock-knob")
    assert "12L14" in str(config["material_specification"])
    assert "chrome" in str(config["finish"])
    assert int(config["quantity"]) == 1
