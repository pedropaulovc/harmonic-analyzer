"""Offline contracts for the pinion cam-follower-pin drawing."""

from __future__ import annotations

from pathlib import Path

import pinion_cam_pin_spec
import draw_pinion_cam_pin as drawing
import build_pinion_cam_pin as pin
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pinion-cam-pin.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pinion-cam-pin.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pinion-cam-pin_drawing.png")
    assert (
        DRAWINGS_BY_NAME["pinion_cam_pin"].script
        == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert pin.DRAWING_DIMENSIONS is pinion_cam_pin_spec.DRAWING_DIMENSIONS
    marked = set().union(*pinion_cam_pin_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    assert drawing.PIN_DIA == pinion_cam_pin_spec.PIN_DIA
    assert drawing.PIN_LEN == pinion_cam_pin_spec.PIN_LEN


def test_sheet_runs_at_4_to_1_with_8_to_1_end_view() -> None:
    assert drawing.SHEET_SCALE == (4.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(8, 1)" in source  # the end-view override
    # The isometric renders at the sheet scale, so no separate iso-scale note.
    assert 'add_property_linked_note(adapter, "End View Note"' in source
    assert pinion_cam_pin_spec.END_VIEW_NOTE == "END VIEW SCALE 8:1"


def test_linked_notes_are_functional_and_carry_no_general_tolerance() -> None:
    notes = pinion_cam_pin_spec.DRAWING_NOTES
    assert "SPHERICAL" in notes
    assert "LINEAR +/-" not in notes
    assert "BA" not in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_direct_limits_replace_ambiguous_gdt() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "add_datum_feature(" not in source
    assert "add_feature_control_frame(" not in source
    assert "add_surface_finish(" not in source
    assert "4.020 MAX / 4.012 MIN" in drawing.DIMENSION_CALLOUTS["PinDia"]
    assert "ISO 286-2" in drawing.DIMENSION_CALLOUTS["PinDia"]


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(pin.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("pinion-cam-pin")
    assert spec["number"] == "MHA-113"
    assert spec["material"] == spec["material_specification"]
    assert spec["material_specification"]
    assert spec["finish"]
    assert "fit_class" not in spec
    assert int(spec["quantity"]) == 2
