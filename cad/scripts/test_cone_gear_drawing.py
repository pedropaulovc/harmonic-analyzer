"""Offline contracts for the cone-gear drawing (batch gear-drawing pattern).

The print follows cad/docs/drawing-simplicity-policy.md: a soldered-on gear
carries no datums, frames or roughness symbols; the GEAR DATA block (with
the over-pins acceptance), two configuration tables covering all 20 members,
a cut-face-only SECTION A-A with the face width, and four lines of
family/process notes are the whole specification beyond the bore.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import _gear_inspection
import build_cone_gear as part
import cone_gear_spec as spec
import draw_cone_gear as drawing
from _drawing_contract import model_toleranced_dimensions
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


def test_gear_data_block_is_the_compact_tooth_system_with_over_pins() -> None:
    data = spec.GEAR_DATA
    lines = data.split("\n")
    assert lines[0] == "GEAR DATA"
    assert len(lines) <= 12
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
        "TABLES",
    ):
        assert field in data, field
    assert "120 (SHEET); 6-120 BY 6, SEE TABLES" in data
    assert "DIAMETRAL PITCH:  49.82" in data
    assert "T006-T030 STUB" in data
    assert "X.XX" not in data
    assert "MODULE" not in data
    assert "RUNOUT" not in data
    # 120T, DP 49.82, 14.5 deg, the family's single 1.00 pin -> 63.00.
    assert spec.PIN_DIA_MM == pytest.approx(1.00)
    assert spec.PIN_DIA_MM == _gear_inspection.preferred_pin_dia_mm(spec.DIAMETRAL_PITCH)
    assert spec.OVER_PINS.over_pins_mm == pytest.approx(63.00, abs=0.005)
    assert "OVER 2 PINS 1.00 DIA:  63.00 +0/-0.10" in data
    source = _source()
    assert 'add_property_linked_note(adapter, "Gear Data"' in source
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_configuration_tables_cover_every_member_from_the_build_geometry() -> None:
    table = spec.CONFIGURATION_TABLE_A + "\n" + spec.CONFIGURATION_TABLE_B
    rows = [line for line in table.split("\n") if re.match(r"^T\d{3}:", line)]
    assert len(rows) == 20
    assert spec.FAMILY_TEETH == tuple(n for _name, n in part.CONFIGS)
    assert spec.CONFIGURATION_TABLE_A.split("\n")[0] == "T006-T060:  OD / DEPTH / BORE / PINS"
    assert spec.CONFIGURATION_TABLE_B.split("\n")[0] == "T066-T120:  OD / DEPTH / BORE / PINS"
    # The column legend (and the pin size) lives once, in the GEAR DATA block.
    assert "TABLES:  OD / DEPTH / BORE / OVER 2 PINS 1.00 DIA, BANDS AS ABOVE" in spec.GEAR_DATA
    assert "BORE BAND (ALL CONFIGS):  +0.05/0.00" in spec.GEAR_DATA
    # Narrow enough for two side-by-side notes at 2.5 mm text (~1.5 mm/char).
    assert max(len(line) for line in table.split("\n")) <= 40
    for teeth in spec.FAMILY_TEETH:
        # Bore and tooth geometry come from the build's own facts (AGENTS rule 1).
        assert spec.family_bore_mm(teeth) == pytest.approx(
            part.bore_dia_in(teeth) * spec.MM_PER_IN
        )
        # The config DP is 122*25.4/62.2 = 49.8199..; the spec rounds it to
        # the 49.82 the sheet prints, so the geometry agrees to 0.01 mm.
        facts = part.gear_facts(teeth)
        assert spec.outside_dia_mm(teeth) == pytest.approx(
            facts["Ra"] * 2 * spec.MM_PER_IN, abs=0.01
        )
        assert spec.base_dia_mm(teeth) == pytest.approx(
            facts["Rb"] * 2 * spec.MM_PER_IN, abs=0.01
        )
        row = next(line for line in rows if line.startswith(f"T{teeth:03d}:"))
        expected_depth = f"{spec.whole_depth_mm(teeth):.2f}"
        assert f" / {expected_depth}" in row, row
        assert f"/ {spec.family_bore_mm(teeth):.3f} /" in row, row
        assert row.endswith(f"/ {spec.over_pins(teeth).over_pins_mm:.2f}"), row
        assert spec.over_pins(teeth).usable, teeth
        if teeth < 32:
            assert spec.is_stub(teeth)
            assert "STUB" in row
            # Tip-to-base-circle depth, the modelled gap floor.
            assert spec.whole_depth_mm(teeth) == pytest.approx(
                (facts["Ra"] - facts["Rb"]) * spec.MM_PER_IN, abs=0.01
            )
            assert spec.whole_depth_mm(teeth) < spec.WHOLE_DEPTH
        else:
            assert not spec.is_stub(teeth)
            assert "STUB" not in row
            assert spec.whole_depth_mm(teeth) == spec.WHOLE_DEPTH
    assert spec.UNDERCUT_TEETH_LIMIT == 32
    # Spot values a reader can check: T006 OD 4.08, stub depth 0.56, bore
    # 0.794, 4.57 over pins; T120 = the sheet.
    assert "T006:  4.08 / 0.56 STUB / 0.794 / 4.57" in table
    assert "T120:  62.20 / 1.10 / 9.525 / 63.00" in table
    for banned in ("DATUM", "RUNOUT", "+/-", "X.XX"):
        assert banned not in table, banned


def test_configuration_tables_are_stamped_and_placed() -> None:
    build_source = Path(part.__file__).read_text(encoding="utf-8")
    assert '"Configuration Table A": CONFIGURATION_TABLE_A' in build_source
    assert '"Configuration Table B": CONFIGURATION_TABLE_B' in build_source
    source = _source()
    assert '"Configuration Table A",' in source
    assert '"Configuration Table B",' in source
    assert 'add_property_linked_note(\n        adapter, "Configuration Table A"' in source
    assert 'add_property_linked_note(\n        adapter, "Configuration Table B"' in source
    # Side by side under the gear data, left of the front view, above the notes.
    assert drawing.TABLE_A_POS[1] == drawing.TABLE_B_POS[1] < drawing.GEAR_DATA_POS[1]
    assert drawing.TABLE_A_POS[0] < drawing.TABLE_B_POS[0] < drawing.FRONT_CENTER[0] - 0.04
    assert drawing.NOTES_POS[1] < drawing.TABLE_A_POS[1] - 0.04
    assert drawing.TABLE_CHAR_HEIGHT == 0.0025


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert "1 OF EACH CONFIGURATION" in notes
    assert "PLAIN REAMED BORE, NO KEYWAY" in notes
    assert "SOLDER" in notes
    assert "C67500 MANGANESE BRONZE" in notes
    assert "T006-T030: CUT TO THE STUB DEPTH IN THE TABLE" in notes
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


def test_bore_callout_names_the_reamer_and_keeps_its_native_band() -> None:
    assert drawing.DIMENSION_CALLOUTS == {"BoreCutDia": "REAM THRU (3/8 IN)"}
    assert drawing.DIMENSION_PRECISION == {"BoreCutDia": 3}
    assert spec.BORE_DIA == 0.375 * spec.MM_PER_IN
    assert spec.BORE_DIA_BAND == (0.05, 0.00)
    assert model_toleranced_dimensions(part) == {
        ("BoreProfile", "BoreCutDia"): "*deviations(BORE_DIA_BAND)"
    }


def test_section_replaces_the_side_view_and_states_the_face_width() -> None:
    source = _source()
    assert "create_section_view(" in source
    assert "show_only_cut_face(adapter, section" in source
    assert 'section_label="A"' in source
    assert "RIGHT_CENTER" not in source
    assert (
        drawing.SECTION_LINE[0][0]
        == drawing.SECTION_LINE[1][0]
        == drawing.FRONT_CENTER[0]
    )
    assert drawing.SECTION_HALF_LINE > spec.OUTSIDE_DIA / 2000.0
    assert drawing.SECTION_NOTE == f"SECTION A-A\nFACE WIDTH {spec.FACE_WIDTH:.2f}"
    assert "add_note(adapter, SECTION_NOTE, *SECTION_NOTE_XY)" in source
    assert "add_edge_dimension(" not in source
    assert drawing.SECTION_NOTE_XY[1] > drawing.SECTION_CENTER[1]


def test_hidden_lines_stay_on_in_the_orthographic_view() -> None:
    source = _source()
    assert "set_hidden_lines_visible(adapter, front)" in source
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
