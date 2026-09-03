"""Offline contracts for the transgear-pinion drawing (batch gear pattern).

The print follows cad/docs/drawing-simplicity-policy.md: a pinion fixed to its
knob shaft carries no datums, frames or roughness symbols; the GEAR DATA block
(with the over-pins acceptance) and one line of notes are the whole
specification beyond the bore.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import _gear_inspection
import build_transgear_pinion as part
import draw_transgear_pinion as drawing
import transgear_pinion_spec as spec
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/transgear-pinion.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/transgear-pinion.pdf")
    assert drawing.PNG.as_posix().endswith("/png/transgear-pinion_drawing.png")
    assert (
        DRAWINGS_BY_NAME["transgear_pinion"].script == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) == marked == {"BoreDia"}
    assert set(drawing.DIMENSION_CALLOUTS) <= marked


def test_gear_data_block_is_the_compact_tooth_system_with_over_pins() -> None:
    data = spec.GEAR_DATA
    lines = data.split("\n")
    assert lines[0] == "GEAR DATA"
    assert len(lines) <= 10
    for field in (
        "NUMBER OF TEETH",
        "DIAMETRAL PITCH",
        "PRESSURE ANGLE",
        "PITCH DIAMETER (REF)",
        "OUTSIDE DIAMETER",
        "WHOLE DEPTH (REF)",
        "FACE WIDTH",
        "OVER 2 PINS",
        "TOOTH FORM",
    ):
        assert field in data, field
    assert "12" in data
    assert "DIAMETRAL PITCH:  38\n" in data
    assert "X.XX" not in data
    assert "MODULE" not in data
    # 12T, 38 DP, 14.5 deg, the 1.30 pin -> 10.08 over two pins: the pin walked
    # round the spaces against the reamed bore is the tooth-to-bore check.
    assert spec.PIN_DIA_MM == pytest.approx(1.30)
    assert spec.PIN_DIA_MM == _gear_inspection.preferred_pin_dia_mm(spec.DIAMETRAL_PITCH)
    assert spec.OVER_PINS.usable
    assert "OVER 2 PINS 1.30 DIA:  10.08 +0/-0.10" in data
    source = _source()
    assert 'add_property_linked_note(adapter, "Gear Data"' in source
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert "FIXED TO THE KNOB SHAFT" in notes
    for banned in ("DATUM", "RUNOUT", "+/-", "MHA-", "DEBUR", "X.XX", "UOS"):
        assert banned not in notes, banned


def test_print_carries_no_gdt_or_finish_symbols() -> None:
    # drawing-simplicity-policy.md rules 3-5: gears are not on the GD&T
    # allowlist and a bore fixed to its shaft does not run.
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
        "visible_circle_edge(",
    ):
        assert helper not in source, helper
    assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(spec, "GEOMETRIC_CONTROLS")
    assert spec.SURFACE_FINISHES == ()
    assert "surface_finishes=SURFACE_FINISHES" in Path(part.__file__).read_text(
        encoding="utf-8"
    )


def test_bore_states_the_process_and_keeps_its_band_on_the_model() -> None:
    assert drawing.DIMENSION_CALLOUTS == {"BoreDia": "REAM THRU"}
    assert drawing.DIMENSION_PRECISION == {"BoreDia": 3}
    assert part.BORE_DIAMETER == spec.BORE_DIA
    assert spec.BORE_DIA_BAND == (0.05, 0.00)
    assert model_toleranced_dimensions(part) == {
        ("BoreProfile", "BoreDia"): "*deviations(BORE_DIA_BAND)"
    }


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
    assert "for view in (front, right):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source
    assert source.count("set_hidden_lines_removed(") == 1


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("transgear-pinion")
    assert config["material_specification"] == "AISI 1018 cold-finished steel"
    assert config["finish"] == "bright, oiled"
    assert int(config["quantity"]) == 1
