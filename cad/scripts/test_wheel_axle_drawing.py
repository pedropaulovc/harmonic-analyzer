"""Offline contracts for the wheel-axle drawing."""

from __future__ import annotations

from pathlib import Path

import build_magnifying_wheel
import build_wheel_axle as part
import draw_wheel_axle as drawing
import wheel_axle_spec
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/wheel-axle.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/wheel-axle.pdf")
    assert drawing.PNG.as_posix().endswith("/png/wheel-axle_drawing.png")
    assert DRAWINGS_BY_NAME["wheel_axle"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is wheel_axle_spec.DRAWING_DIMENSIONS
    marked = set().union(*wheel_axle_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.END_KEEP)
    assert kept == marked
    assert (
        drawing.FLANGE_DIA,
        drawing.FLANGE_LEN,
        drawing.STUD_DIA,
        drawing.STUD_LEN,
        drawing.COLLAR_DIA,
        drawing.COLLAR_LEN,
    ) == (
        wheel_axle_spec.FLANGE_DIA,
        wheel_axle_spec.FLANGE_LEN,
        wheel_axle_spec.STUD_DIA,
        wheel_axle_spec.STUD_LEN,
        wheel_axle_spec.COLLAR_DIA,
        wheel_axle_spec.COLLAR_LEN,
    )


def test_stud_callout_keeps_wheel_bore_running_clearance() -> None:
    # The magnifying wheel's bore is nominal-on-nominal with the stud, so the
    # running clearance comes entirely from the stud's unilateral-minus callout.
    assert build_magnifying_wheel.BORE_DIA == wheel_axle_spec.STUD_DIA
    assert drawing.DIMENSION_CALLOUTS["StudDia"] == "-0.02/-0.05"
    clearance_min = build_magnifying_wheel.BORE_DIA - (wheel_axle_spec.STUD_DIA - 0.02)
    clearance_max = build_magnifying_wheel.BORE_DIA - (wheel_axle_spec.STUD_DIA - 0.05)
    assert round(clearance_min, 2) == 0.02
    assert round(clearance_max, 2) == 0.05
    notes = wheel_axle_spec.DRAWING_NOTES
    # Deburr/edge-break is a title-block note; repeating it here would duplicate it.
    assert "DEBURR" not in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "def _manufacturing_notes" not in source


def test_native_gdt_controls_axle_orientation_coaxiality_and_finish() -> None:
    """GD&T identity lives in the spec's PMI rows; the sheet only imports it."""
    from wheel_axle_spec import GEOMETRIC_CONTROLS, PART_DATUMS

    by_key = {control.key: control for control in GEOMETRIC_CONTROLS}
    assert set(by_key) == {"stud_perpendicularity", "collar_runout"}
    assert by_key["stud_perpendicularity"].characteristic == "perpendicularity"
    assert by_key["stud_perpendicularity"].tolerance == "0.05"
    assert by_key["stud_perpendicularity"].datums == ("A",)
    assert by_key["stud_perpendicularity"].tolerance_zone == "diametral"
    assert by_key["collar_runout"].characteristic == "circular_runout"
    assert by_key["collar_runout"].tolerance == "0.05"
    assert by_key["collar_runout"].datums == ("B",)
    assert tuple(datum.letter for datum in PART_DATUMS) == ("A", "B")

    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert "author_part_pmi(adapter" in part_source
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "project_part_pmi(" in source
    assert "controls=GEOMETRIC_CONTROLS" in source
    assert "add_feature_control_frame(" not in source
    assert "add_datum_feature(" not in source
    assert source.count("add_surface_finish(") == 1


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (3.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("scale=(3, 1)") == 3


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("wheel-axle")
    assert "1018" in str(config["material_specification"])
    assert config["finish"]
    assert int(config["quantity"]) == 1
