"""Offline contracts for the crank-handle drawing."""

from __future__ import annotations

from pathlib import Path

import pytest

import crank_handle_butt_cup_spec as cup
import crank_handle_ferrule_spec as ferrule
import crank_handle_spec
import draw_crank_handle as drawing
import build_crank_handle as handle
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/crank-handle.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/crank-handle.pdf")
    assert drawing.PNG.as_posix().endswith("/png/crank-handle_drawing.png")
    assert (
        DRAWINGS_BY_NAME["crank_handle"].script == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert handle.DRAWING_DIMENSIONS is crank_handle_spec.DRAWING_DIMENSIONS
    marked = set().union(*crank_handle_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    assert set(crank_handle_spec.DRAWING_PRECISION_BY_NAME) == marked
    assert "draw_crank_handle.py" in PRECISION_MIGRATED_DRAWINGS


def test_oak_ends_in_a_ferrule_tenon_and_a_cup_counterbore() -> None:
    # User ruling 2026-09-29 (ch11 p.14/p.15): the brass ring and the steel
    # butt disc are separate parts bonded to the oak.
    marked = set().union(*crank_handle_spec.DRAWING_DIMENSIONS.values())
    assert marked == {
        "TenonDia",
        "TenonLength",
        "WoodLength",
        "PeakStation",
        "CounterboreDia",
        "CounterboreDepth",
        "PivotBoreDia",
    }
    assert crank_handle_spec.SHOULDER_X == ferrule.LENGTH
    assert crank_handle_spec.TRIM_X == pytest.approx(
        crank_handle_spec.HANDLE_LENGTH - cup.FLANGE_THICKNESS
    )
    assert crank_handle_spec.WOOD_LENGTH == pytest.approx(50.2)
    assert crank_handle_spec.TENON_X0 > 0.0  # no oak reaches the arm face
    assert crank_handle_spec.TENON_GLUE_LINE == pytest.approx((0.03, 0.12))
    assert crank_handle_spec.CUP_GLUE_LINE == pytest.approx((0.03, 0.12))
    assert abs(cup.FLANGE_DIA - 2.0 * crank_handle_spec.TRIM_R) <= 0.1
    assert crank_handle_spec.COUNTERBORE_MOUTH_WALL >= 0.6


def test_diameters_are_a_basic_profile_note_not_marked_dims() -> None:
    notes = crank_handle_spec.DRAWING_NOTES
    assert "BASIC TRUE GRIP PROFILE" in notes
    assert "ALL VALUES BASIC" in notes
    assert f"R{crank_handle_spec.FRONT_PROFILE_R:.6f}" in notes
    assert f"R{crank_handle_spec.REAR_PROFILE_R:.6f}" in notes
    # Stations read from datum B, the tenon shoulder.
    assert "AT X0.00;" in notes and "AT X29.00;" in notes and "AT X51.00." in notes
    assert crank_handle_spec.BASIC_DIMENSIONS == {"PeakStation"}


def test_peak_station_uses_visible_construction_geometry() -> None:
    build_source = Path(handle.__file__).read_text(encoding="utf-8")
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'profile.record("PeakStation",' in build_source
    assert 'profile.record("FrontArcCx",' in build_source
    assert '"PeakStation":' in drawing_source
    assert '"FrontArcCx":' not in drawing_source
    assert "peak station construction line" in build_source


def test_bored_profile_has_end_view_center_marks() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "auto_center_marks" in source
    assert "add_view_centerline" in source


def test_sheet_runs_at_2_to_1_with_1_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 1)" in source  # the isometric override
    assert crank_handle_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_linked_notes_are_functional_and_carry_no_general_tolerance() -> None:
    notes = crank_handle_spec.DRAWING_NOTES
    assert "CDA 260" not in notes
    assert "COLLAR" not in notes
    assert "BRASS" not in notes
    assert "LINEAR +/-" not in notes
    assert "X.XX" not in notes
    assert "NO BLEND, RADIUS, OR CHAMFER" in notes
    assert "FINAL BORE LIMITS APPLY FULL LENGTH" in notes
    assert "STRAIGHT GRAIN PARALLEL TO TURNING AXIS" in notes
    assert "50.20+0.00/-0.25 IS WOOD" in notes
    assert "PROFILE 0.50 | A | B APPLIES" in notes
    assert all(len(line) <= 90 for line in notes.splitlines())
    assert drawing.DIMENSION_CALLOUTS["PivotBoreDia"] == "THRU - REAM"
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_feature_requirements_use_datum_based_controls() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 2
    assert source.count("add_feature_control_frame(") == 3
    assert 'characteristic="perpendicularity"' in source
    assert 'quantity="DATUM B FACE"' in source
    assert 'characteristic="total_runout"' in source
    assert 'quantity="TENON OD"' in source
    assert 'characteristic="profile_surface"' in source
    assert 'quantity="TURNED GRIP PROFILE - SEE NOTE"' in source
    assert "set_basic_dimension(" in source
    assert "add_surface_finish(" not in source


def test_model_owns_every_printed_band() -> None:
    source = Path(handle.__file__).read_text(encoding="utf-8")
    for name in ("WoodLength", "TenonDia", "CounterboreDia", "PivotBoreDia"):
        assert f'"{name}"' in source
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in source
    assert "_paint_collar_brass" not in source


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(handle.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("crank-handle")
    assert handle.MATERIAL == "Oak"
    assert "white oak" in spec["material_specification"]
    assert "6-8% MC" in spec["material_specification"]
    assert spec["finish"]
    assert int(spec["quantity"]) == 1
