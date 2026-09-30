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
        "OverallLength",
        "PeakStation",
        "CounterboreDia",
        "CounterboreDepth",
        "PivotBoreDia",
    }
    assert crank_handle_spec.SHOULDER_X == ferrule.LENGTH
    assert crank_handle_spec.TRIM_X == pytest.approx(
        crank_handle_spec.HANDLE_LENGTH - cup.FLANGE_THICKNESS
    )
    assert crank_handle_spec.WOOD_LENGTH == pytest.approx(48.7)
    assert crank_handle_spec.OVERALL_LENGTH == pytest.approx(53.7)
    assert crank_handle_spec.TENON_X0 > 0.0  # no oak reaches the arm face
    assert abs(cup.FLANGE_DIA - 2.0 * crank_handle_spec.TRIM_R) <= 0.1
    assert crank_handle_spec.COUNTERBORE_MOUTH_WALL >= 0.6
    # User ruling 2026-09-29 (MHA-153 review): the butt grew from Ø10 so the
    # cup keeps 1.5 mm sections.
    # ... and again for 1.5 mm of oak round the cup counterbore (MHA-022 review).
    assert crank_handle_spec.CAP_R == pytest.approx(8.0)
    assert crank_handle_spec.COUNTERBORE_DIA_MAX == pytest.approx(11.9)
    assert "11.9 MAX" in crank_handle_spec.DRAWING_NOTES
    assert crank_handle_spec.COUNTERBORE_MOUTH_WALL >= 1.5
    # Codex P2 on #1139: the contour may run its whole diametral allowance
    # small, so the radius loses 0.25, not 0.125 (2.08 -> 1.96).
    assert crank_handle_spec.COUNTERBORE_MOUTH_WALL == pytest.approx(1.958, abs=0.005)


def test_tenon_and_counterbore_are_fitted_to_the_parts_they_take() -> None:
    # User ruling 2026-09-29 (after the machinist reviews): turned and bored to
    # suit, so the sizes print as references and the note carries the fit.
    spec = crank_handle_spec
    assert spec.REFERENCE_DIMENSIONS == {"TenonDia", "CounterboreDia"}
    assert spec.TENON_DIA == pytest.approx(ferrule.BORE_DIA - 0.1)
    assert spec.COUNTERBORE_DIA == pytest.approx(cup.BODY_DIA + 0.1)
    assert "TURN THE TENON TO SUIT THE MHA-150 FERRULE BORE" in spec.DRAWING_NOTES
    assert "COUNTERBORE TO SUIT THE MHA-153 CUP BODY" in spec.DRAWING_NOTES
    # Codex P2 on #1139 (user ruling 2026-09-30): the butt is blended to the
    # bonded flange so no end grain shows, keeping 1.5 of oak round the
    # largest counterbore under the smallest .X flange.
    assert "AFTER CURE, BLEND THE BUTT FLUSH WITH THE MHA-153 FLANGE." in spec.DRAWING_NOTES
    assert spec.BLENDED_BUTT_WALL == pytest.approx(2.15)
    source = Path(handle.__file__).read_text(encoding="utf-8")
    assert source.count("set_dimension_bilateral_tolerance(") == 1  # the reamed bore
    assert "set_dimension_symmetric_tolerance" not in source
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "for name in sorted(REFERENCE_DIMENSIONS):" in drawing_source


def test_grip_contour_is_a_note_with_a_loose_allowance() -> None:
    # User ruling 2026-09-29 (MHA-022 review): the contour is turned to its
    # arcs within an allowance, not held by a basic profile and a frame.
    notes = crank_handle_spec.DRAWING_NOTES
    assert "GRIP CONTOUR:" in notes
    assert f"R{crank_handle_spec.FRONT_PROFILE_R:.1f}" in notes
    assert f"R{crank_handle_spec.REAR_PROFILE_R:.1f}" in notes
    assert "TURN WITHIN 0.5 ON DIAMETER" in notes
    assert "BASIC" not in notes
    assert not hasattr(crank_handle_spec, "BASIC_DIMENSIONS")
    assert not hasattr(crank_handle_spec, "GEOMETRIC_TOLERANCES_MM")


def test_peak_station_uses_visible_construction_geometry() -> None:
    build_source = Path(handle.__file__).read_text(encoding="utf-8")
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'profile.record("PeakStation",' in build_source
    assert 'profile.record("FrontArcCx",' in build_source
    assert '"PeakStation":' in drawing_source
    assert '"FrontArcCx":' not in drawing_source
    assert "peak station construction line" in build_source


def test_counterbore_reads_on_a_section_and_the_end_view_shares_its_axis() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "auto_center_marks" in source
    assert "create_section_view(" in source
    assert "create_section_axis_centerline(" in source
    assert "set_hidden_lines_visible" not in source
    assert drawing.RIGHT_CENTER[1] == drawing.FRONT_CENTER[1]
    # The reference overall, tenon end to butt face, for stock cut-off.
    assert crank_handle_spec.OVERALL_LENGTH == pytest.approx(53.7)


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
    assert "LIMITS APPLY FULL LENGTH" in notes
    assert "RUNS ON THE MHA-139 SHOULDER" in notes
    assert "STRAIGHT GRAIN PARALLEL TO TURNING AXIS" in notes
    assert "AXIAL STATIONS ARE FROM THE TENON END FACE" in notes
    assert "COUNTERBORE DEPTH IS\n  FROM THE BUTT FACE" in notes
    assert "DATUM" not in notes and "PROFILE 0.50" not in notes
    assert all(len(line) <= 90 for line in notes.splitlines())
    assert drawing.DIMENSION_CALLOUTS["PivotBoreDia"] == "THRU - REAM"
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_sheet_carries_no_gdt() -> None:
    # User ruling 2026-09-29 (MHA-022 review): a plain sheet.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "set_basic_dimension(",
        "add_surface_finish(",
    ):
        assert helper not in source


def test_model_owns_every_printed_band() -> None:
    source = Path(handle.__file__).read_text(encoding="utf-8")
    for name in ("OverallLength", "TenonDia", "CounterboreDia", "PivotBoreDia"):
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
