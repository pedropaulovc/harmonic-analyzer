"""Offline contracts for the cone-gear drawing (batch gear-drawing pattern).

The print follows cad/docs/drawing-simplicity-policy.md: a soldered-on gear
carries no datums, frames or roughness symbols; the GEAR DATA block and four
lines of family/process notes are the whole specification beyond the bore.
"""

from __future__ import annotations

from pathlib import Path

import build_cone_gear as part
import cone_gear_spec as spec
import draw_cone_gear as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/cone-gear.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/cone-gear.pdf")
    assert drawing.PNG.as_posix().endswith("/png/cone-gear_drawing.png")
    assert DRAWINGS_BY_NAME["cone_gear"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP)
    assert kept == marked == {"BoreCutDia"}
    assert set(drawing.DIMENSION_CALLOUTS) <= kept


def test_gear_data_block_is_the_compact_tooth_system_and_family_table() -> None:
    data = spec.GEAR_DATA
    lines = data.split("\n")
    assert lines[0] == "GEAR DATA"
    assert len(lines) <= 11
    for field in (
        "NUMBER OF TEETH",
        "DIAMETRAL PITCH",
        "PRESSURE ANGLE",
        "PITCH DIAMETER (REF)",
        "OUTSIDE DIAMETER",
        "WHOLE DEPTH",
        "FACE WIDTH",
        "TOOTH FORM",
        "FAMILY T006 / T012 / T018",
        "FAMILY T024-T120 BY 6",
    ):
        assert field in data, field
    assert "120" in data
    assert "X.XX" not in data
    # Dropped rows: the module restates the DP and the datum-based runout is gone.
    assert "MODULE" not in data
    assert "RUNOUT" not in data
    for teeth, bore_mm in spec.FAMILY_BORES_MM.items():
        assert bore_mm == part.bore_dia_in(teeth) * spec.MM_PER_IN
        assert f"{bore_mm:.3f}" in data
    source = _source()
    assert 'add_property_linked_note(adapter, "Gear Data"' in source
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert "1 OF EACH CONFIGURATION" in notes
    assert "NO KEYWAY" in notes
    assert "SOLDER" in notes
    assert "C67500 MANGANESE BRONZE" in notes
    assert "STUB DEPTH" in notes
    for banned in ("DATUM", "RUNOUT", "+/-", "MHA-", "DEBUR", "X.XX", "UOS"):
        assert banned not in notes, banned


def test_print_carries_no_gdt_or_finish_symbols() -> None:
    # drawing-simplicity-policy.md rules 3-5: gears are not on the GD&T
    # allowlist and a soldered bore does not run.
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


def test_bore_callout_names_the_reamer_and_keeps_three_decimals() -> None:
    assert drawing.DIMENSION_CALLOUTS == {"BoreCutDia": "REAM THRU (3/8 IN)"}
    assert drawing.DIMENSION_PRECISION == {"BoreCutDia": 3}
    assert spec.BORE_DIA == 0.375 * spec.MM_PER_IN


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
    assert "for view in (front, right):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source
    assert source.count("set_hidden_lines_removed(") == 1


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    assert 'if not bool(activation.data.get("rebuilt")):' in source
    import _config

    config = _config.parts("cone-gear")
    assert config["material_specification"] == "C36000 free-machining brass"
    assert config["material_tip_specification"] == "C67500 manganese bronze"
    assert spec.TIP_MATERIAL_SPEC == config["material_tip_specification"]
    assert config["finish"] == "polished brass"
    assert int(config["quantity"]) == 1
