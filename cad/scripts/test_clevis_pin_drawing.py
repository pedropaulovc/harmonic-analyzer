"""Offline contracts for the connecting-rod clevis-pin drawing."""

from __future__ import annotations

import math
from pathlib import Path

import _config
import build_clevis_pin as pin
import clevis_pin_notes
import clevis_pin_spec
import draw_clevis_pin as drawing
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths_and_registry() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/clevis-pin.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/clevis-pin.pdf")
    assert drawing.PNG.as_posix().endswith("/png/clevis-pin_drawing.png")
    spec = DRAWINGS_BY_NAME["clevis_pin"]
    assert spec.part == "clevis_pin"
    assert spec.artifact_stem == "clevis-pin"
    assert spec.script == Path(drawing.__file__).resolve()


def test_marked_dimensions_cover_the_pin_contract_once() -> None:
    assert pin.DRAWING_DIMENSIONS is clevis_pin_notes.DRAWING_DIMENSIONS
    marked = set().union(*clevis_pin_notes.DRAWING_DIMENSIONS.values())
    kept = set(drawing.END_KEEP) | set(drawing.SIDE_KEEP)
    assert marked == kept == {
        "GripLength",
        "HeadDia",
        "HeadThickness",
        "ShankDia",
    }
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    assert clevis_pin_spec.SHANK_DIA == 1.8
    assert clevis_pin_spec.GRIP_LENGTH == 4.9
    assert clevis_pin_spec.HEAD_DIA == 3.0
    assert clevis_pin_spec.HEAD_THICKNESS == 0.6


def test_shank_tolerance_preserves_worst_case_number_47_running_fit() -> None:
    # The drilled hole is Ø1.994 +0.10/0, so its minimum is the nominal.
    # SHAFT_H makes the pin nominal its maximum rather than allowing the
    # title-block default to grow it beyond the hole.
    assert clevis_pin_spec.SHANK_DIA_BAND == (0.0, -0.020)
    pin_max = clevis_pin_spec.SHANK_DIA + clevis_pin_spec.SHANK_DIA_BAND[0]
    hole_min = clevis_pin_spec.PIN_HOLE_DIA
    clearance = hole_min - pin_max
    assert pin_max < hole_min
    assert math.isclose(clearance, 0.194, abs_tol=1e-12)
    assert math.isclose(
        clearance, clevis_pin_spec.MIN_DIAMETRAL_CLEARANCE, abs_tol=1e-12
    )
    assert model_toleranced_dimensions(pin) == {
        ("ShankProfile", "ShankDia"): "*deviations(SHANK_DIA_BAND)"
    }


def test_sheet_uses_large_head_end_side_and_isometric_views() -> None:
    assert drawing.SHEET_SCALE == (12.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert '"*Back", *END_CENTER, scale=(12, 1)' in source
    assert '"*Right", *SIDE_CENTER, scale=(12, 1)' in source
    assert '"*Isometric", *ISO_CENTER, scale=(12, 1)' in source
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert 'add_property_linked_note(adapter, "End View Note"' in source


def test_notes_and_part_properties_describe_separate_bright_hardware() -> None:
    notes = clevis_pin_notes.DRAWING_NOTES
    assert "AISI 1018" in notes
    assert "VISIBLE NEAR CLEVIS CHEEK" in notes
    assert "POLISH BRIGHT" in notes
    assert "LINEAR +/-" not in notes
    assert "1.80" not in notes
    assert "4.90" not in notes
    source = Path(pin.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    assert "require_saved_drawing_properties" in source
    registry = _config.parts("clevis-pin")
    assert registry["number"] == "MHA-018"
    assert registry["quantity"] == 20
