"""Offline contracts for the crank-handle drawing."""

from __future__ import annotations

from pathlib import Path

import pytest

import dt_crank_handle_butt_cup_spec as cup
import dt_crank_handle_ferrule_spec as ferrule
import dt_crank_handle_spec
import draw_dt_crank_handle as drawing
import build_dt_crank_handle as handle
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/dt-crank-handle.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/dt-crank-handle.pdf")
    assert drawing.PNG.as_posix().endswith("/png/dt-crank-handle_drawing.png")
    assert (
        DRAWINGS_BY_NAME["dt_crank_handle"].script == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert handle.DRAWING_DIMENSIONS is dt_crank_handle_spec.DRAWING_DIMENSIONS
    marked = set().union(*dt_crank_handle_spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= marked
    assert set(dt_crank_handle_spec.DRAWING_PRECISION_BY_NAME) == marked
    assert "draw_dt_crank_handle.py" in PRECISION_MIGRATED_DRAWINGS


def test_every_profile_size_is_a_model_dimension() -> None:
    # MHA-DT-008 machinist review of 2026-10-18: the profile's sizes print as
    # dimensions on the section, not in a note; the bore revolves with it.
    spec = dt_crank_handle_spec
    assert set(spec.DRAWING_DIMENSIONS) == {"HandleProfile"}
    assert not hasattr(spec, "DRAWING_NOTES")
    assert spec.REFERENCE_RADII == {"FlareR", "SConcaveR", "SConvexR", "DomeR"}
    assert spec.REFERENCE_RADII <= spec.DRAWING_DIMENSIONS["HandleProfile"]
    build_source = Path(handle.__file__).read_text(encoding="utf-8")
    assert "_make_driven(adapter, reference, name)" in build_source
    assert "PivotBoreProfile" not in build_source
    assert spec.PIVOT_BORE_CALLOUT.startswith("REAM THRU")
    assert "MHA-DT-032" in spec.PIVOT_BORE_CALLOUT
    assert spec.DRAWING_PRECISION_BY_NAME["PivotBoreDia"] == 2
    assert all(
        places == 1
        for name, places in spec.DRAWING_PRECISION_BY_NAME.items()
        if name != "PivotBoreDia"
    )


def test_oak_ends_in_a_ferrule_tenon_and_a_cup_counterbore() -> None:
    # User ruling 2026-09-29 (ch11 p.14/p.15): the brass ring and the steel
    # butt disc are separate parts bonded to the oak.
    spec = dt_crank_handle_spec
    assert spec.SHOULDER_X == ferrule.LENGTH
    # The end round crests on the cup-face plane at the basic length, on the
    # oak only; a flat oak end runs from the crest to the counterbore mouth and
    # the cup bottoms with its face on the basic length.
    assert spec.END_ROUND_CX + spec.END_ROUND_R == pytest.approx(spec.HANDLE_LENGTH)
    assert spec.END_ROUND_CY == pytest.approx(spec.CREST_DIA / 2.0)
    assert spec.OAK_END_X == spec.HANDLE_LENGTH
    assert spec.COUNTERBORE_DEPTH == pytest.approx(cup.OVERALL_LENGTH)
    assert spec.OVERALL_LENGTH == pytest.approx(56.0)
    assert spec.profile_radius(spec.OAK_END_X) == pytest.approx(spec.END_ROUND_CY)
    build_source = Path(handle.__file__).read_text(encoding="utf-8")
    assert '("oak end face", oak_end_face, "vertical")' in build_source
    assert '(end_round, oak_end_face, "end round crest")' in build_source
    assert spec.TENON_X0 > 0.0  # no oak reaches the arm face
    assert spec.COUNTERBORE_DIA_MAX == pytest.approx(8.5)
    # The flat oak end round the cup holds the 2.0 wall target at the worst
    # case -- crest at the .X band's low limit, the largest counterbore, the
    # bore's eccentricity both ways (MHA-DT-008 machinist review of
    # 2026-10-18, which refused the 0.45 lip).
    assert spec.BUTT_WALL_MIN == pytest.approx((14.0 - 0.8) / 2.0 - 0.2 - 8.5 / 2.0)
    assert spec.BUTT_WALL_MIN >= spec.WALL_TARGET_MM == 2.0
    assert not hasattr(spec, "FEATHER_DEPTH")


def test_tenon_and_counterbore_are_fitted_to_the_parts_they_take() -> None:
    # User ruling 2026-09-29 (after the machinist reviews): turned and bored to
    # suit, so the sizes print as references and the callouts carry the fit.
    spec = dt_crank_handle_spec
    # The counterbore depth seats the cup face flush, so it is fitted too.
    assert spec.REFERENCE_DIMENSIONS == {"TenonDia", "CounterboreDia", "CounterboreDepth"}
    assert spec.TENON_DIA == pytest.approx(ferrule.BORE_DIA - 0.1)
    assert spec.COUNTERBORE_DIA == pytest.approx(cup.BODY_DIA + 0.1)
    assert drawing.DIMENSION_CALLOUTS["TenonDia"] == spec.TENON_FIT_NOTE
    assert drawing.DIMENSION_CALLOUTS["CounterboreDia"] == spec.COUNTERBORE_FIT_NOTE
    assert "MHA-DT-034" in spec.TENON_FIT_NOTE
    assert "DIAMETRAL CLEARANCE" in spec.TENON_FIT_NOTE
    assert "MHA-DT-035" in spec.COUNTERBORE_FIT_NOTE
    assert "<MOD-DIAM>8.5 MAX" in spec.COUNTERBORE_FIT_NOTE
    assert "FLUSH" in spec.COUNTERBORE_FIT_NOTE
    # The fitted tenon keeps its ferrule seat and 1.5 over the bore, with
    # 0.10 of bore eccentricity budgeted (local review of 1f3067ef2), the
    # contour at the title block's .X band.
    assert spec.SHOULDER_R == pytest.approx(ferrule.INSTALLED_OUTER_DIA / 2.0)
    assert spec.BORE_ECCENTRICITY == pytest.approx(0.10)
    assert spec.FERRULE_SEAT_RADIAL_MIN == pytest.approx(1.975)
    assert spec.TENON_WALL_MIN == pytest.approx(1.55)
    assert spec.WAIST_WALL_MIN == pytest.approx(2.175)
    # The ring is skimmed with the shoulder, so its stock OD carries no band
    # (user ruling 2026-10-01).
    assert not hasattr(ferrule, "OUTER_DIA_TOL")
    source = Path(handle.__file__).read_text(encoding="utf-8")
    assert source.count("set_dimension_bilateral_tolerance(") == 1  # the reamed bore
    assert "set_dimension_symmetric_tolerance" not in source
    assert not hasattr(spec, "TENON_LENGTH_TOL")
    assert spec.TENON_END_GAP_MIN == pytest.approx((7.0 - 0.8) - (5.0 + 0.8))
    # The shortest tenon's bonded length after the tenon-end and bore-mouth
    # edge breaks (local review of 21bb244c5).
    assert spec.TENON_GLUE_LENGTH_MIN == pytest.approx(5.0 - 0.8 - 0.25 - 0.25)
    assert spec.TENON_GLUE_LENGTH_MIN >= 3.5
    # The reamed bore prints 4.10 +0.05/0, its two-place nominal the limit
    # itself (local review of fbf82ad96: 4.125 printed 4.13 +/-0.025).
    assert (spec.PIVOT_BORE_DIA, spec.PIVOT_BORE_BAND) == (4.10, (0.05, 0.0))
    # No run-out: the cup cures centred on the waxed MHA-DT-032 at assembly
    # (MHA-DT-008 machinist review of 2026-10-18 found 0.2 TIR over-spec).
    assert not hasattr(spec, "BORE_RUNOUT_TIR")
    assert spec.CUP_OFFSET_MAX == pytest.approx(0.175)
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "for name in sorted(REFERENCE_DIMENSIONS):" in drawing_source


def test_grip_contour_is_tangent_arcs_dimensioned_on_the_section() -> None:
    # User rulings 2026-09-30 (ch30 eight-views-4, concept v4): the waist, the
    # inflection and the swell, printed from the tenon end face.
    spec = dt_crank_handle_spec
    assert (spec.WAIST_X - spec.TENON_X0, spec.WAIST_R * 2.0) == pytest.approx((10.0, 9.5))
    assert spec.INFLECTION[0] - spec.TENON_X0 == pytest.approx(18.0)
    assert (spec.PEAK_X - spec.TENON_X0, spec.PEAK_R * 2.0) == pytest.approx((40.0, 21.0))
    assert (spec.FLARE_R, spec.S_CONCAVE_R, spec.S_CONVEX_R) == pytest.approx(
        (9.083, 21.636, 59.500), abs=0.001
    )
    assert spec.DOME_R == pytest.approx(55.06, abs=0.01)
    assert (spec.CREST_DIA, spec.END_ROUND_R) == (14.0, 1.5)
    assert not hasattr(spec, "CONTOUR_ALLOWANCE_DIA")
    assert not hasattr(spec, "BASIC_DIMENSIONS")
    assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM")
    build_source = Path(handle.__file__).read_text(encoding="utf-8")
    assert 'profile.record(name, f"{knob} - {station}")' in build_source
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "_style_radius(" in drawing_source


def test_bore_and_counterbore_read_on_a_section_the_end_view_shares_its_axis() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "auto_center_marks" in source
    assert "create_section_view(" in source
    assert "create_section_axis_centerline(" in source
    assert "set_hidden_lines_visible" not in source
    assert drawing.RIGHT_CENTER[1] == drawing.FRONT_CENTER[1]


def test_sheet_runs_at_4_to_1_with_1_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (4.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 1)" in source  # the isometric override
    assert dt_crank_handle_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source
    assert '"Manufacturing Notes"' not in source


def test_sheet_carries_no_gdt() -> None:
    # User ruling 2026-09-29 (MHA-DT-008 review): a plain sheet.
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

    spec = _config.parts("dt-crank-handle")
    assert handle.MATERIAL == "Oak"
    assert "white oak" in spec["material_specification"]
    assert "straight grain along axis" in spec["material_specification"]
    assert "6-8% MC" in spec["material_specification"]
    assert spec["finish"]
    assert int(spec["quantity"]) == 1
