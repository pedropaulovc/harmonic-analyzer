"""Offline contracts for the transgear-feed-pinion drawing (batch gear pattern).

The print follows cad/docs/drawing-simplicity-policy.md: no datums or frames;
one roughness symbol on the bore because the pinion (locked to the disc) RUNS
free on the stud; a compact GEAR DATA block with the over-pins acceptance;
one line of notes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import _gear_inspection
import build_transgear_feed_pinion as part
import draw_transgear_feed_pinion as drawing
import transgear_feed_pinion_spec as spec
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/transgear-feed-pinion.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/transgear-feed-pinion.pdf")
    assert drawing.PNG.as_posix().endswith("/png/transgear-feed-pinion_drawing.png")
    assert (
        DRAWINGS_BY_NAME["transgear_feed_pinion"].script
        == Path(drawing.__file__).resolve()
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
    # A standard cutter designation carries no false decimals.
    assert "DIAMETRAL PITCH:  30\n" in data
    assert "30.00" not in data
    assert "X.XX" not in data
    assert "MODULE" not in data
    # 12T, 30 DP, 14.5 deg, the 1.65 pin -> 12.78 over two pins.
    assert spec.PIN_DIA_MM == pytest.approx(1.65)
    assert spec.PIN_DIA_MM == _gear_inspection.preferred_pin_dia_mm(spec.DIAMETRAL_PITCH)
    assert spec.OVER_PINS.usable
    assert "OVER 2 PINS 1.65 DIA:  12.78 +0/-0.10" in data
    source = _source()
    assert 'add_property_linked_note(adapter, "Gear Data"' in source
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert "RUNS FREE ON THE STUD" in notes
    # The full-face tooth line repeated the 9.50 face width the views show.
    assert "FULL FACE" not in notes
    for banned in ("DATUM", "RUNOUT", "+/-", "MHA-", "DEBUR", "X.XX", "UOS"):
        assert banned not in notes, banned


def test_print_carries_no_gdt() -> None:
    # drawing-simplicity-policy.md rule 3: gears are not on the GD&T allowlist.
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(spec, "GEOMETRIC_CONTROLS")


def test_running_bore_keeps_its_fit_finish_and_three_decimals() -> None:
    assert drawing.DIMENSION_CALLOUTS == {"BoreDia": "REAM THRU"}
    assert drawing.DIMENSION_PRECISION == {"BoreDia": 3}
    assert spec.BORE_DIA_BAND == (0.05, 0.00)
    assert model_toleranced_dimensions(part) == {
        ("BoreProfile", "BoreDia"): "*deviations(BORE_DIA_BAND)"
    }


def test_bore_leaders_land_on_opposite_sides_of_the_bore() -> None:
    cx, cy = drawing.FRONT_CENTER
    text = drawing.FRONT_KEEP["BoreDia"]
    assert text[0] < cx and text[1] > cy  # callout upper-left
    symbol = drawing.BORE_FINISH_SYMBOL
    assert symbol[0] < cx and symbol[1] < cy  # roughness lower-left, radial


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

    config = _config.parts("transgear-feed-pinion")
    assert config["material_specification"] == "C36000 free-machining brass"
    assert config["finish"] == "polished brass"
    assert int(config["quantity"]) == 1


def test_surface_finish_is_part_owned_authored_and_consumed() -> None:
    (control,) = spec.SURFACE_FINISHES
    assert control.key == "bore"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == spec.BORE_DIA
    assert part.BORE_DIAMETER == spec.BORE_DIA
    part_source = "".join(Path(part.__file__).read_text(encoding="utf-8").split())
    assert "surface_finishes=SURFACE_FINISHES" in part_source
    sheet_source = "".join(_source().split())
    assert 'control=surface_finish_by_key(SURFACE_FINISHES,"bore")' in sheet_source
    assert "roughness_ra=" not in sheet_source
    source = _source()
    assert source.count("add_surface_finish(") == 1
    assert "bore_edge = visible_circle_edge(" in source
    assert source.count("entity=bore_edge") == 1
