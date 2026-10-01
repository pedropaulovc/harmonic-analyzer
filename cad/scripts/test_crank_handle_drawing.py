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
    spec = crank_handle_spec
    assert spec.SHOULDER_X == ferrule.LENGTH
    # The end round crests on the cup-face plane at the basic length, on the
    # oak only, outside the largest counterbore turned its allowance small
    # and off the mandrel by the bore's eccentricity: 4.25 + 0.25 + 0.10
    # (local review of fbf82ad96).  A flat oak end runs from the crest to the
    # counterbore mouth; the cup bottoms with its face on the basic length.
    assert spec.END_ROUND_CX + spec.END_ROUND_R == pytest.approx(spec.HANDLE_LENGTH)
    assert spec.END_ROUND_CY == pytest.approx(8.5 / 2.0 + 0.25 + 0.10)
    assert spec.OAK_END_X == spec.HANDLE_LENGTH
    assert spec.COUNTERBORE_DEPTH == pytest.approx(cup.OVERALL_LENGTH)
    assert spec.OVERALL_LENGTH == pytest.approx(56.0)
    assert spec.profile_radius(spec.OAK_END_X) == pytest.approx(spec.END_ROUND_CY)
    build_source = Path(handle.__file__).read_text(encoding="utf-8")
    assert '("oak end face", oak_end_face, "vertical")' in build_source
    assert '(end_round, oak_end_face, "end round crest")' in build_source
    assert spec.TENON_X0 > 0.0  # no oak reaches the arm face
    assert spec.COUNTERBORE_DIA_MAX == pytest.approx(8.5)
    assert "<MOD-DIAM>8.5 MAX" in spec.DRAWING_NOTES
    # The oak end's edge round the counterbore mouth is the named exception
    # (0.45 wide at nominal, nothing at the worst case); 1.0 in, the oak holds
    # 1.5 again at the contour allowance and the bore's eccentricity over the
    # largest counterbore.
    assert spec.FEATHER_DEPTH == 1.0
    assert spec.OAK_WALL_BEHIND_FEATHER == pytest.approx(1.96, abs=0.01)


def test_tenon_and_counterbore_are_fitted_to_the_parts_they_take() -> None:
    # User ruling 2026-09-29 (after the machinist reviews): turned and bored to
    # suit, so the sizes print as references and the note carries the fit.
    spec = crank_handle_spec
    # The counterbore depth seats the cup face flush, so it is fitted too.
    assert spec.REFERENCE_DIMENSIONS == {"TenonDia", "CounterboreDia", "CounterboreDepth"}
    assert spec.TENON_DIA == pytest.approx(ferrule.BORE_DIA - 0.1)
    assert spec.COUNTERBORE_DIA == pytest.approx(cup.BODY_DIA + 0.1)
    assert "TURN THE TENON TO SUIT THE MHA-152 FERRULE BORE" in spec.DRAWING_NOTES
    assert "COUNTERBORE TO SUIT THE MHA-153 CUP BODY" in spec.DRAWING_NOTES
    assert "DEPTH TO SEAT THE CUP\n  FACE FLUSH" in spec.DRAWING_NOTES
    # User ruling 2026-09-30 (concept v4): after the cure the oak is turned
    # flush with the ferrule; the end round is turned on the oak only, clear
    # of the cup (local review of fbf82ad96).
    assert "AFTER CURE, TURN THE SHOULDER FLUSH WITH MHA-152 AND THE END ROUND ON" in spec.DRAWING_NOTES
    assert "THE OAK ONLY, CLEAR OF MHA-153; AT WORST THE OAK FEATHERS AT THE CUP." in spec.DRAWING_NOTES
    assert "R2.4 END ROUND TO A FLAT OAK END, CREST <MOD-DIAM>9.2." in spec.DRAWING_NOTES
    # crank-v4-16's sheet: two more lines ran the block into the border.
    assert len(spec.DRAWING_NOTES.splitlines()) <= 14
    # The fitted tenon keeps its ferrule seat and 1.5 over the bore, with
    # 0.10 of bore eccentricity budgeted (local review of 1f3067ef2).
    assert spec.SHOULDER_R == pytest.approx(ferrule.OUTER_DIA / 2.0)
    assert spec.BORE_ECCENTRICITY == pytest.approx(0.10)
    assert spec.FERRULE_SEAT_RADIAL_MIN == pytest.approx(2.125)
    assert spec.TENON_WALL_MIN == pytest.approx(1.55)
    assert spec.WAIST_WALL_MIN == pytest.approx(2.325)
    # Turning the shoulder flush with the banded ferrule OD stays inside the
    # grip's contour allowance.
    assert 2.0 * ferrule.OUTER_DIA_TOL <= spec.CONTOUR_ALLOWANCE_DIA
    source = Path(handle.__file__).read_text(encoding="utf-8")
    assert source.count("set_dimension_bilateral_tolerance(") == 1  # the reamed bore
    # The tenon length is routine: with no collar on the screw (local review
    # of fbf82ad96) only the oak's clearance to the arm face rides on it.
    assert "set_dimension_symmetric_tolerance" not in source
    assert not hasattr(spec, "TENON_LENGTH_TOL")
    assert spec.DRAWING_PRECISION_BY_NAME["TenonLength"] == 1
    assert spec.TENON_END_GAP_MIN == pytest.approx((7.0 - 0.8) - (5.0 + 0.8))
    # The shortest tenon's bonded length after the tenon-end and bore-mouth
    # edge breaks (local review of 21bb244c5).
    assert spec.TENON_GLUE_LENGTH_MIN == pytest.approx(5.0 - 0.8 - 0.25 - 0.25)
    assert spec.TENON_GLUE_LENGTH_MIN >= 3.5
    # The reamed bore prints 4.10 +0.05/0, its two-place nominal the limit
    # itself (local review of fbf82ad96: 4.125 printed 4.13 +/-0.025).
    assert (spec.PIVOT_BORE_DIA, spec.PIVOT_BORE_BAND) == (4.10, (0.05, 0.0))
    # The off-centre budget is printed as process plus an inspectable wall,
    # and the cup cures centred on the screw (user ruling 2026-09-30).
    flat = " ".join(spec.DRAWING_NOTES.split())
    # A requirement, not a method (machinist review of crank-v4-16).
    assert "ONE SETUP" not in flat and "MANDREL" not in flat
    # Measured on the wall, clear of the end face's edge breaks (local
    # review of 747487c71).
    assert "MIN OAK WALL 1.5 OVER THE BORE, CORNERS EXCEPTED." in flat
    assert "THE CUP CENTRED ON THE WAXED MHA-139 SCREW." in flat
    assert spec.CUP_OFFSET_MAX == pytest.approx(0.175)
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "for name in sorted(REFERENCE_DIMENSIONS):" in drawing_source


def test_grip_contour_is_a_note_with_a_loose_allowance() -> None:
    # User ruling 2026-09-29 (MHA-022 review): the contour is turned to its
    # arcs within an allowance, not held by a basic profile and a frame.
    spec = crank_handle_spec
    notes = spec.DRAWING_NOTES
    assert "GRIP CONTOUR, TANGENT ARCS IN TURN:" in notes
    for radius in (
        spec.FLARE_R,
        spec.S_CONCAVE_R,
        spec.S_CONVEX_R,
        spec.DOME_R,
        spec.END_ROUND_R,
    ):
        assert f"R{radius:.1f}" in notes
    # User rulings 2026-09-30 (ch30 eight-views-4, concept v4): the waist, the
    # inflection and the swell, printed from the tenon end face.
    assert "<MOD-DIAM>9.5 WAIST AT 10.0" in notes
    assert "INFLECTION AT 18.0" in notes
    assert "<MOD-DIAM>21.0 AT 40.0" in notes
    assert (spec.FLARE_R, spec.S_CONCAVE_R, spec.S_CONVEX_R, spec.DOME_R) == pytest.approx(
        (9.083, 21.636, 59.500, 30.694), abs=0.001
    )
    assert spec.END_ROUND_R == pytest.approx(2.429, abs=0.001)
    assert "TURN WITHIN 0.5 ON DIAMETER; CHECK WITH A TEMPLATE." in notes
    assert "BASIC" not in notes
    assert not hasattr(crank_handle_spec, "BASIC_DIMENSIONS")
    assert not hasattr(crank_handle_spec, "GEOMETRIC_TOLERANCES_MM")


def test_peak_station_uses_visible_construction_geometry() -> None:
    build_source = Path(handle.__file__).read_text(encoding="utf-8")
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'profile.record("PeakStation",' in build_source
    # The two swell centres sit on the peak station, driven by "PeakX".
    assert """(s_convex, S_CONVEX_CENTER, "S convex centre", '"PeakX"')""" in build_source
    assert """(dome, DOME_CENTER, "dome centre", '"PeakX"')""" in build_source
    assert '"PeakStation":' in drawing_source
    assert "CentreX" not in drawing_source
    assert "peak station construction line" in build_source


def test_counterbore_reads_on_a_section_and_the_end_view_shares_its_axis() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "auto_center_marks" in source
    assert "create_section_view(" in source
    assert "create_section_axis_centerline(" in source
    assert "set_hidden_lines_visible" not in source
    assert drawing.RIGHT_CENTER[1] == drawing.FRONT_CENTER[1]
    # The overall, tenon end to the oak's end, for stock cut-off.
    assert crank_handle_spec.OVERALL_LENGTH == pytest.approx(56.0)


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
