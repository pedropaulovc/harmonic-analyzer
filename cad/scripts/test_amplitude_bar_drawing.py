"""Offline contracts for the amplitude-bar drawing."""

from __future__ import annotations

import math
from pathlib import Path

import amplitude_bar_notes
import amplitude_bar_spec
import draw_amplitude_bar as drawing
import build_amplitude_bar as bar
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import blind_cut_dia_mm, drill_process


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/amplitude-bar.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/amplitude-bar.pdf")
    assert drawing.PNG.as_posix().endswith("/png/amplitude-bar_drawing.png")
    assert DRAWINGS_BY_NAME["amplitude_bar"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert bar.DRAWING_DIMENSIONS is amplitude_bar_spec.DRAWING_DIMENSIONS
    marked = set().union(*amplitude_bar_spec.DRAWING_DIMENSIONS.values())
    keeps = (
        drawing.FRONT_KEEP,
        drawing.RIGHT_KEEP,
        drawing.TOP_KEEP,
        drawing.DETAIL_A_KEEP,
        drawing.DETAIL_B_KEEP,
    )
    kept = set().union(*keeps)
    assert kept == marked
    assert sum(len(keep) for keep in keeps) == len(marked)  # one view each
    assert set(drawing.DRAWING_PRECISION_BY_NAME) == marked


def test_part_geometry_matches_the_spec() -> None:
    assert amplitude_bar_spec.BAR_LENGTH == bar.BAR_LENGTH
    assert amplitude_bar_spec.BAR_WIDTH == bar.BAR_WIDTH
    assert bar.TOP_PIN_HOLE_SPEC is amplitude_bar_spec.TOP_PIN_HOLE_SPEC
    assert blind_cut_dia_mm(amplitude_bar_spec.TOP_PIN_HOLE_SPEC) == 1.994


def test_sheet_runs_at_1_to_4_with_1_to_8_isometric() -> None:
    assert drawing.SHEET_SCALE == (1.0, 4.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 8)" in source  # the isometric override
    assert "scale=(4, 1)" in source  # the top end-view section override
    assert amplitude_bar_notes.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:8"
    assert amplitude_bar_notes.END_VIEW_NOTE == "END VIEW SCALE 4:1"
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "End View Note"' in source
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_linked_notes_carry_the_notches_and_hole() -> None:
    notes = amplitude_bar_notes.DRAWING_NOTES
    assert "END NOTCHES (DETAILS A, B)" in notes
    assert drill_process(amplitude_bar_spec.TOP_PIN_HOLE_SPEC) in notes
    assert "LINEAR +/-" not in notes
    assert "STEEL" not in notes
    assert "CHROME" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_bottom_notch_depth_band_is_native_on_its_dimension() -> None:
    """User ruling 2026-09-26: a deep notch drops the cheeks onto the rocker
    hub one for one, so the depth may only come out shallow. Codex #936
    PRRT_kwDOPHDy386mWF0L, policy rule 2: that band is the part's, native on
    BottomNotchHeight from the one constant the cheek-over-hub test reads,
    printed in DETAIL A -- and no note carries it or any notch size."""
    from _drawing_contract import model_toleranced_dimensions

    upper, lower = amplitude_bar_spec.BOTTOM_NOTCH_DEPTH_BAND
    assert lower == -0.50 < upper == 0.0
    assert not hasattr(amplitude_bar_notes, "BOTTOM_NOTCH_DEPTH_BAND")
    assert model_toleranced_dimensions(bar)[("BarProfile", "BottomNotchHeight")] == (
        "*deviations(BOTTOM_NOTCH_DEPTH_BAND)"
    )
    assert "BottomNotchHeight" in drawing.DETAIL_A_KEEP
    notes = " ".join(
        line.strip() for line in amplitude_bar_notes.DRAWING_NOTES.splitlines()
    )
    assert "DEEP" not in notes
    assert "+0/" not in notes
    assert "3.18" not in notes and "2.38" not in notes and "12.70" not in notes
    assert bar.DRAWING_NOTES is amplitude_bar_notes.DRAWING_NOTES


def test_notch_details_frame_their_ends_and_place_text_outside_the_bar() -> None:
    """DETAIL A takes in the foot notch and the open end; DETAIL B the 12.7
    top notch. Each depth's text stands outside the bar's side and each
    width's outside its open end, where the witnesses run through air."""
    spec = amplitude_bar_spec
    for detail, low, high in (
        (drawing.DETAIL_A, 0.0, spec.BOTTOM_NOTCH_HEIGHT),
        (drawing.DETAIL_B, spec.BAR_LENGTH - spec.TOP_NOTCH_HEIGHT, spec.BAR_LENGTH),
    ):
        fx, fy = detail.fence_mm
        for x in (0.0, spec.BAR_WIDTH):
            for y in (low, high):
                assert math.hypot(x - fx, y - fy) < detail.radius_mm
    a = drawing.DETAIL_A
    depth_x, depth_y = drawing.DETAIL_A_KEEP["BottomNotchHeight"]
    assert depth_x < a.sheet_xy(0.0, 0.0)[0]
    assert (
        a.sheet_xy(0.0, 0.0)[1] < depth_y < a.sheet_xy(0.0, spec.BOTTOM_NOTCH_HEIGHT)[1]
    )
    assert drawing.DETAIL_A_KEEP["BottomNotchWidth"][1] < a.sheet_xy(0.0, 0.0)[1]
    b = drawing.DETAIL_B
    assert (
        drawing.DETAIL_B_KEEP["TopNotchHeight"][0] > b.sheet_xy(spec.BAR_WIDTH, 0.0)[0]
    )
    assert (
        drawing.DETAIL_B_KEEP["TopNotchWidth"][1] > b.sheet_xy(0.0, spec.BAR_LENGTH)[1]
    )
    # Both details and their labels stay on the sheet, clear of the title
    # block (x >= 0.218 below y 0.065) and of each other.
    for detail in (a, b):
        radius = detail.radius_mm * detail.mm
        assert detail.label_xy[1] - 0.010 > 0.0127
        assert detail.centre[1] + radius < 0.2667
    assert a.centre[0] + a.radius_mm * a.mm < 0.218
    assert b.label_xy[1] - 0.010 > 0.181  # over the isometric's top


def test_functional_notch_finish_is_feature_specific() -> None:
    notes = amplitude_bar_notes.DRAWING_NOTES
    assert "BOTTOM NOTCH FLOOR: Ra 0.8" in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "add_datum_feature(" not in source
    assert "add_feature_control_frame(" not in source
    assert "add_surface_finish(" not in source


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(bar.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("amplitude-bar")
    assert spec["material_specification"] == "AISI 1018 cold-rolled steel, 6.35 sq"
    assert spec["finish"] == "bright chrome plated"
    assert int(spec["quantity"]) == 20
