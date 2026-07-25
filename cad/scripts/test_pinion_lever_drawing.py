"""Offline contracts for the pinion-engage-lever drawing."""

from __future__ import annotations

from pathlib import Path

import pinion_lever_spec
import draw_pinion_lever as drawing
import build_pinion_lever as lever
import _drawing_common
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pinion-lever.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pinion-lever.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pinion-lever_drawing.png")
    assert (
        DRAWINGS_BY_NAME["pinion_lever"].script == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert lever.DRAWING_DIMENSIONS is pinion_lever_spec.DRAWING_DIMENSIONS
    marked = set().union(*pinion_lever_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    assert (drawing.HUB_OD, drawing.ROD_LEN, drawing.BORE) == (
        pinion_lever_spec.HUB_OD,
        pinion_lever_spec.ROD_LEN,
        pinion_lever_spec.BORE,
    )


def test_sheet_runs_at_1_to_1_with_1_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 1)" in source  # the isometric override
    assert pinion_lever_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_linked_notes_are_functional_and_carry_no_general_tolerance() -> None:
    notes = pinion_lever_spec.DRAWING_NOTES
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "SPHERICAL CROWN" in source
    assert "TIP FACE FLAT WITHIN 0.05" in source
    assert "PERPENDICULAR TO GRIP AXIS" in source
    assert '"WITHIN 0.10"' in source
    assert "GRIP PROFILE; BASIC AXIS" not in source
    assert "BLIND BORE BOTTOM" in notes
    assert "DATUM A" in notes and "DATUM B" in notes
    assert "LINEAR +/-" not in notes
    assert "BREAK ALL" not in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_lever_drive_is_fully_released_for_manufacture() -> None:
    notes = pinion_lever_spec.DRAWING_NOTES
    normalized = " ".join(notes.split())
    assert "RELEASE HOLD" not in notes
    assert "AT ASSEMBLY" not in notes
    assert "LIFT ROD" not in notes
    assert "GRIP AXIS: 5.00+/-0.10 FROM B" in normalized
    assert "90+/-0.5 DEG TO A" in normalized
    assert "SHORTEST DISTANCE BETWEEN GRIP AXIS AND A: 0.00 TO 0.10" in normalized
    assert "GRIP-TO-HUB JUNCTION R0.25 MAX" in normalized
    assert "EXEMPT FROM THE TITLE-BLOCK EDGE-BREAK" in normalized


def test_direct_limits_replace_ambiguous_gdt() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    common_source = Path(_drawing_common.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 2
    assert source.count("add_feature_control_frame(") == 3
    assert (
        "        edge_xy=bore_left,\n"
        "        symbol_xy=(bore_left[0] - 0.022, bore_left[1] + 0.018),\n"
        '        datum="A",\n'
        '        label="lever final bore axis",\n'
        "        position_tolerance_m=0.005,"
        in source
    )
    assert source.count("position_tolerance_m=0.005") == 1
    assert source.count('entity_type="SILHOUETTE"') == 5
    assert source.count('entity_type="FACE"') == 0
    assert 'characteristic="circular_runout"' in source
    assert "add_surface_finish(" not in source
    assert "6.375 MAX / 6.360 MIN" in drawing.DIMENSION_CALLOUTS["HubBore"]
    assert "Ra 1.6" in drawing.DIMENSION_CALLOUTS["HubBore"]
    assert "+0.10/-0.00" in drawing.DIMENSION_CALLOUTS["BoreDepth"]
    assert "END WALL" in drawing.DIMENSION_CALLOUTS["EndWall"]
    assert set(drawing.RIGHT_KEEP) == {"BoreDepth", "EndWall"}
    assert "<MOD-DIAM>{ROD_TIP_DIA:.2f}" in source
    assert "GRIP_HALF_ANGLE_DEG" in source
    assert "{HUB_LEN:.2f} REF" in source
    assert "({CAP_SAG:.2f}) REF AXIAL HEIGHT" in source
    assert "create_section_view(" not in source
    assert 'place_view(adapter, str(SOURCE), "*Right"' in source
    assert source.count("model_point_in_view(") == 2
    assert "ModelToViewTransform" in common_source
    assert "(0.0, HUB_OD / 2000.0, HUB_LEN / 2000.0)" in source
    assert "section_hub_y" not in source
    assert "def create_section_view(" not in common_source


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(lever.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("pinion-lever")
    assert spec["material"] == spec["material_specification"]
    assert spec["material_specification"]
    assert spec["finish"]
    assert "fit_class" not in spec
    assert int(spec["quantity"]) == 1
