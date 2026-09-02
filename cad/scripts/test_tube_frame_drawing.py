"""Offline contracts for the tube-frame drawing."""

from __future__ import annotations

from pathlib import Path

import build_tube_frame as part
import draw_tube_frame as drawing
import tube_frame_spec
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/tube-frame.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/tube-frame.pdf")
    assert drawing.PNG.as_posix().endswith("/png/tube-frame_drawing.png")
    assert DRAWINGS_BY_NAME["tube_frame"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is tube_frame_spec.DRAWING_DIMENSIONS
    marked = set().union(*tube_frame_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.END_KEEP) | set(drawing.LENGTH_KEEP)
    assert kept == marked
    assert drawing.OUTER_DIA == tube_frame_spec.OUTER_DIA


def test_tube_nominals_are_single_sourced() -> None:
    assert part.OUTER_DIA is tube_frame_spec.OUTER_DIA
    assert part.COLUMN_LENGTH is tube_frame_spec.COLUMN_LENGTH
    assert tube_frame_spec.OUTER_DIA == 25.4
    # 1 in OD, 0.12 in wall -> Ø19.304 bore.
    assert abs(tube_frame_spec.INNER_DIA - 19.304) < 1e-6
    # 2026-09-02 user re-read (ch30 p002: columns end just above the corner
    # bosses): 994.0 overall = 990.7 tube + 3.3 integral dome cap (capped
    # stub top at machine 1044.8, 4.1 above the 1040.7 boss tops).
    assert tube_frame_spec.COLUMN_LENGTH == 994.0
    assert tube_frame_spec.CAP_HEIGHT == 3.3
    assert abs(tube_frame_spec.BODY_LENGTH - 990.7) < 1e-9
    # Full-width spherical cap: R = (a^2 + h^2) / (2h) with a = OD/2.
    assert abs(tube_frame_spec.CAP_SPHERE_RADIUS - 26.08787878787879) < 1e-9


def test_notes_and_native_gdt() -> None:
    notes = tube_frame_spec.DRAWING_NOTES
    assert "STEEL TUBE" not in notes
    assert "POLISH" not in notes
    assert "DEBURR" not in notes
    assert "UOS" not in notes
    assert "AS-PROCURED STOCK RESULT" in notes
    assert "NOT AN ACCEPTANCE DIMENSION" in notes
    assert "DO NOT MACHINE THE ID" in notes
    assert "FULL-LENGTH CYLINDRICITY CONTROL" in notes
    assert "ASME RULE 1" in notes
    assert "FORM DOES NOT OVERRIDE SIZE" in notes
    assert "AS-RECEIVED OD 25.40 MIN" in notes
    # Domed top (2026-08-02): orientation is now functional -- cap up; only
    # the bottom end face keeps a perpendicularity control.
    assert "ORIENT DOMED (CAPPED) END UP" in notes
    assert "ONLY THE BOTTOM END FACE" in notes
    assert "SR26.09 X 3.3 SPHERICAL CAP" in notes
    assert "TOP/BOTTOM ORIENTATION IS NONFUNCTIONAL" not in notes
    assert "BORE" not in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert source.count("add_datum_feature(") == 1
    assert source.count("add_feature_control_frame(") == 2
    assert 'characteristic="cylindricity"' in source
    assert (
        tube_frame_spec.GEOMETRIC_TOLERANCES_MM["full-length OD cylindricity"] == "0.03"
    )
    assert "tolerance=GEOMETRIC_TOLERANCES_MM['full-length OD cylindricity']" in source
    assert '"BOTTOM END FACE"' in source
    assert '"TOP END FACE"' not in source
    assert "top end perpendicularity" not in tube_frame_spec.GEOMETRIC_TOLERANCES_MM
    assert source.count('characteristic="perpendicularity"') == 1
    assert "set_dimension_callouts" not in source
    assert source.count("add_surface_finish(") == 0


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 5.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 5)" in source
    assert "scale=(2, 1)" in source
    assert tube_frame_spec.END_VIEW_NOTE == "END VIEW SCALE 2:1"
    assert 'add_property_linked_note(adapter, "End View Note"' in source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("tube-frame")
    assert config["material"] == config["material_specification"]
    assert "ASTM A513 Type 5" in str(config["material"])
    assert "SAE 1020 DOM" in str(config["material"])
    finish = str(config["finish"]).lower()
    assert "od polished ra 1.6" in finish
    assert "corrosion-preventive oil after inspection" in finish
    assert "ends faced" in finish
    assert "id as-procured" in finish
    assert int(config["quantity"]) == 4
