"""Offline contracts for the cylinder-gear drawing (batch gear-drawing pattern).

The print follows cad/docs/drawing-simplicity-policy.md: no datums or frames;
one roughness symbol on the bore because it RUNS on the cylinder-gear shaft;
a compact GEAR DATA block; four lines of cam/notch/set notes.
"""

from __future__ import annotations

from pathlib import Path

import build_cylinder_gear as part
import cylinder_gear_spec as spec
import draw_cylinder_gear as drawing
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/cylinder-gear.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/cylinder-gear.pdf")
    assert drawing.PNG.as_posix().endswith("/png/cylinder-gear_drawing.png")
    assert DRAWINGS_BY_NAME["cylinder_gear"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP)
    assert kept == marked == {"BoreDia"}
    assert set(drawing.DIMENSION_CALLOUTS) <= kept


def test_gear_data_block_is_the_compact_tooth_system() -> None:
    data = spec.GEAR_DATA
    lines = data.split("\n")
    assert lines[0] == "GEAR DATA"
    assert len(lines) <= 9
    for field in (
        "NUMBER OF TEETH",
        "DIAMETRAL PITCH",
        "PRESSURE ANGLE",
        "PITCH DIAMETER (REF)",
        "OUTSIDE DIAMETER",
        "WHOLE DEPTH",
        "FACE WIDTH",
        "TOOTH FORM",
        "INVOLUTE, FULL DEPTH",
    ):
        assert field in data, field
    assert "120" in data
    assert "49.82" in data
    assert "X.XX" not in data
    assert "MODULE" not in data
    # 20 gears stack on one drum: the face width keeps its band in the blank
    # row because it is not a view dimension.
    assert "FACE WIDTH:  3.00 +/-0.05" in data
    source = _source()
    assert 'add_property_linked_note(adapter, "Gear Data"' in source
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_gear_data_block_is_inset_from_the_zone_border() -> None:
    assert drawing.GEAR_DATA_POS == (0.040, 0.262)
    assert drawing.GEAR_DATA_POS[0] < drawing.FRONT_CENTER[0]


def test_notes_are_few_and_carry_only_the_cam_notch_and_set_facts() -> None:
    notes = spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert "ECCENTRIC CAM, FAR FACE" in notes
    assert f"<MOD-DIAM>{spec.CAM_DIA:.2f}" in notes
    assert f"AXIS {spec.ECCENTRICITY:.3f} FROM BORE" in notes
    assert max(len(line) for line in lines) <= 90
    assert "FOLLOWER TRACK: Ra 1.6" in notes
    assert "SAW KERF" in notes
    assert "SET OF 20: CAM OFFSETS WITHIN 0.025" in notes
    for banned in ("DATUM", "RUNOUT", "+/-", "BASIC", "MHA-", "DEBUR", "X.XX", "UOS"):
        assert banned not in notes, banned


def test_running_bore_keeps_its_fit_finish_and_three_decimals() -> None:
    assert drawing.DIMENSION_CALLOUTS == {"BoreDia": "REAM THRU"}
    assert drawing.DIMENSION_PRECISION == {"BoreDia": 3}
    assert spec.BORE_DIA_BAND == (0.05, 0.03)
    assert model_toleranced_dimensions(part) == {
        ("BoreProfile", "BoreDia"): "*deviations(BORE_DIA_BAND)"
    }
    (control,) = spec.SURFACE_FINISHES
    assert control.key == "cylinder_gear_bore"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == spec.BORE_DIA
    source = _source()
    assert source.count("add_surface_finish(") == 1
    assert "bore_edge = visible_circle_edge(" in source
    assert source.count("entity=bore_edge") == 1
    assert 'control=surface_finish_by_key(SURFACE_FINISHES, "cylinder_gear_bore")' in source


def test_print_carries_no_gdt() -> None:
    # drawing-simplicity-policy.md rule 3: gears are not on the GD&T allowlist.
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "set_basic_dimension(",
        "project_part_pmi(",
        "_largest_visible_planar_face",
    ):
        assert helper not in source, helper
    assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(spec, "GEOMETRIC_CONTROLS")


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

    config = _config.parts("cylinder-gear")
    assert config["material_specification"] == "C36000 free-machining brass"
    assert config["finish"] == "polished brass"
    assert int(config["quantity"]) == 20
