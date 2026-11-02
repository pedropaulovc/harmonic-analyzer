"""Offline contracts for the crank-handle drawing."""

from __future__ import annotations

import math
import runpy
from pathlib import Path

import pytest

import dt_crank_handle_butt_cup_spec as cup
import dt_crank_handle_ferrule_spec as ferrule
import dt_crank_handle_pivot_screw_spec as screw
import dt_crank_handle_spec
import draw_dt_crank_handle as drawing
import build_dt_crank_handle as handle
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _printed_tolerance import printed_band_mm

IN = 25.4
_XX = printed_band_mm(2, unit=dt_crank_handle_spec.UNIT)


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
    assert set(drawing.FRONT_KEEP) | set(drawing.DETAIL_KEEP) == marked
    assert not set(drawing.FRONT_KEEP) & set(drawing.DETAIL_KEEP)
    assert set(drawing.DIMENSION_CALLOUTS) <= marked
    assert set(dt_crank_handle_spec.DRAWING_PRECISION_BY_NAME) == marked
    assert "draw_dt_crank_handle.py" in PRECISION_MIGRATED_DRAWINGS


def test_butt_callouts_clear_ruling_b_native_text_envelopes() -> None:
    # Native r4 at 966989134 measured the R77.3 box at 14.2 x 4.6 mm,
    # the R1.5 box at 8.7 x 3.5, and the fitted-bore first row's right
    # edge 47.9 mm right of its keep.  Preserve actual air, not just a
    # different coordinate, when these leaders are repositioned.
    keep = drawing.FRONT_KEEP
    end_x = drawing._front_x(dt_crank_handle_spec.OAK_END_X)
    dome_right = keep["DomeR"][0] + 0.0142 / 2.0
    assert end_x - dome_right >= 0.0046
    end_round_left = keep["EndRoundR"][0] - 0.0087 / 2.0
    assert end_round_left - dome_right >= 0.0046
    bore_text_right = keep["CounterboreDia"][0] + 0.0479
    assert keep["CrestDia"][0] - bore_text_right >= 0.0035
    crest_text_right = keep["CrestDia"][0] + 0.017
    end_view_left = drawing.RIGHT_CENTER[0] - drawing.END_R
    assert end_view_left - crest_text_right >= 0.0035


def test_every_profile_size_is_a_model_dimension() -> None:
    # MHA-DT-08 machinist review of 2026-10-18: the profile's sizes print as
    # dimensions on the section, not in a note; the bore revolves with it.
    spec = dt_crank_handle_spec
    assert set(spec.DRAWING_DIMENSIONS) == {"HandleProfile"}
    assert not hasattr(spec, "DRAWING_NOTES")
    assert spec.REFERENCE_RADII == {"FlareR", "SConcaveR", "SConvexR", "DomeR"}
    assert spec.REFERENCE_RADII <= spec.DRAWING_DIMENSIONS["HandleProfile"]
    build_source = Path(handle.__file__).read_text(encoding="utf-8")
    assert "_make_driven(adapter, reference, name)" in build_source
    assert "PivotBoreProfile" not in build_source
    assert drawing.PIVOT_BORE_CALLOUT.startswith("REAM THRU")
    assert "MHA-DT-32" in drawing.PIVOT_BORE_CALLOUT
    # The fitted sizes and the small corner features print at three places,
    # the routine contour at the title block's two.
    three = {
        "PivotBoreDia", "TenonDia", "CounterboreDia", "TenonRootRadius",
        "CounterboreFloorRadius", "TenonRootRelief",
    }
    for name, places in spec.DRAWING_PRECISION_BY_NAME.items():
        assert places == (3 if name in three else 2), name


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
    assert spec.OVERALL_LENGTH == pytest.approx(spec.HANDLE_LENGTH - spec.TENON_X0)
    assert spec.profile_radius(spec.OAK_END_X) == pytest.approx(spec.END_ROUND_CY)
    build_source = Path(handle.__file__).read_text(encoding="utf-8")
    assert '("oak end face", oak_end_face, "vertical")' in build_source
    assert '(end_round, oak_end_face, "end round crest")' in build_source
    assert spec.TENON_X0 > 0.0  # no oak reaches the arm face
    # Owner ruling B on #1375: the larger cup drives the counterbore limit, up
    # to the next printed thousandth.
    needed = cup.BODY_DIA + cup.BODY_DIA_TOL + spec.COUNTERBORE_GLUE_LINE[1] + 0.002 * IN
    assert needed - 1e-6 <= spec.COUNTERBORE_DIA_MAX < needed + 0.001 * IN
    assert spec.COUNTERBORE_DIA_MAX == pytest.approx(0.395 * IN)
    # The historical oak feather was fixed in #1650.  Keep the ordinary .XX
    # diameter band and both eccentricities, with the .080 target plus
    # owner ruling B's .002 radial design margin at the worst case.
    assert spec.WALL_TARGET_MM == WALL_TARGET_MM
    assert spec.BUTT_WALL_DESIGN_MIN_MM == pytest.approx(
        spec.WALL_TARGET_MM + spec.BUTT_WALL_RULING_MARGIN_MM
    )
    crest_needed = (
        spec.COUNTERBORE_DIA_MAX
        + _XX
        + 2.0 * (2.0 * spec.BORE_ECCENTRICITY + spec.BUTT_WALL_DESIGN_MIN_MM)
    )
    assert crest_needed <= spec.CREST_DIA < crest_needed + 0.01 * IN
    assert spec.BUTT_WALL_MIN == pytest.approx(
        (spec.CREST_DIA - _XX) / 2.0 - 2.0 * spec.BORE_ECCENTRICITY
        - spec.COUNTERBORE_DIA_MAX / 2.0
    )
    assert spec.BUTT_WALL_MIN >= spec.BUTT_WALL_DESIGN_MIN_MM >= spec.WALL_TARGET_MM
    assert not hasattr(spec, "FEATHER_DEPTH")


@pytest.mark.parametrize(
    ("dimension", "change"),
    (("BODY_DIA", -0.01 * IN), ("BODY_DIA", 0.01 * IN), ("BODY_DIA_TOL", 0.01 * IN)),
)
def test_cup_limits_drive_the_counterbore_crest_dome_and_fit_note(
    monkeypatch: pytest.MonkeyPatch, dimension: str, change: float
) -> None:
    # Source-mutation controls, not additional manufacturing bands: owner
    # ruling B on #1375 must keep the whole cup-to-oak derivation live.
    spec = dt_crank_handle_spec
    monkeypatch.setattr(cup, dimension, getattr(cup, dimension) + change)
    fresh = runpy.run_path(spec.__file__)
    assert fresh["COUNTERBORE_DIA"] == pytest.approx(
        cup.BODY_DIA + sum(spec.COUNTERBORE_GLUE_LINE) / 2.0
    )
    assert fresh["COUNTERBORE_DIA_MAX"] == pytest.approx(spec.COUNTERBORE_DIA_MAX + change)
    assert fresh["CREST_DIA"] == pytest.approx(spec.CREST_DIA + change)
    assert fresh["BUTT_WALL_DESIGN_MIN_MM"] == pytest.approx(spec.BUTT_WALL_DESIGN_MIN_MM)
    assert fresh["BUTT_WALL_MIN"] == pytest.approx(spec.BUTT_WALL_MIN)
    assert fresh["BUTT_WALL_MIN"] >= fresh["BUTT_WALL_DESIGN_MIN_MM"]
    assert fresh["DOME_R"] != pytest.approx(spec.DOME_R)
    assert math.dist(fresh["DOME_CENTER"], fresh["END_ROUND_CENTER"]) == pytest.approx(
        fresh["DOME_R"] - fresh["END_ROUND_R"]
    )
    assert (
        f'<MOD-DIAM>{spec.inch_text(fresh["COUNTERBORE_DIA_MAX"], 3)} MAX'
        in fresh["COUNTERBORE_FIT_NOTE"]
    )
    for name in (
        "HANDLE_LENGTH", "HANDLE_MAX_DIA", "SHOULDER_X", "SHOULDER_R",
        "TENON_X0", "TENON_LENGTH", "TENON_DIA", "WAIST_X", "WAIST_R",
        "INFLECTION_X", "PEAK_X", "PEAK_R", "END_ROUND_R",
        "COUNTERBORE_DEPTH", "INSIDE_CORNER_R_MAX",
    ):
        assert fresh[name] == getattr(spec, name), name


def test_tenon_and_counterbore_are_fitted_to_the_parts_they_take() -> None:
    # User ruling 2026-09-29 (after the machinist reviews): turned and bored to
    # suit, so the sizes print as references and the callouts carry the fit.
    spec = dt_crank_handle_spec
    # The counterbore depth seats the cup face flush, so it is fitted too.
    assert spec.REFERENCE_DIMENSIONS == {
        "PivotBoreDia", "TenonDia", "CounterboreDia", "CounterboreDepth",
    }
    assert spec.TENON_DIA == pytest.approx(ferrule.BORE_DIA - sum(spec.TENON_GLUE_LINE) / 2.0)
    assert spec.COUNTERBORE_DIA == pytest.approx(
        cup.BODY_DIA + sum(spec.COUNTERBORE_GLUE_LINE) / 2.0
    )
    assert drawing.DIMENSION_CALLOUTS["TenonDia"] == spec.TENON_FIT_NOTE
    assert drawing.DIMENSION_CALLOUTS["CounterboreDia"] == spec.COUNTERBORE_FIT_NOTE
    # Rule 4: a matched pair names its mate by name and number.
    assert "MHA-DT-34" in spec.TENON_FIT_NOTE
    assert spec.FERRULE_NAME in spec.TENON_FIT_NOTE
    assert "DIAMETRAL CLEARANCE" in spec.TENON_FIT_NOTE
    assert "MHA-DT-35" in spec.COUNTERBORE_FIT_NOTE
    assert spec.CUP_NAME in spec.COUNTERBORE_FIT_NOTE
    # F12 (#290): the reamed bore's running clearance on the shoulder, at
    # the places that print it exactly.
    assert drawing.DIMENSION_CALLOUTS["PivotBoreDia"] == drawing.PIVOT_BORE_CALLOUT
    assert screw.DIAMETRAL_CLEARANCE_MIN == pytest.approx(0.0050 * IN)
    assert screw.DIAMETRAL_CLEARANCE_MAX == pytest.approx(0.0075 * IN)
    assert ".0050-.0075" in drawing.PIVOT_BORE_CALLOUT
    assert (
        f"<MOD-DIAM>{spec.inch_text(spec.COUNTERBORE_DIA_MAX, 3)} MAX"
        in spec.COUNTERBORE_FIT_NOTE
    )
    assert "FLUSH" in spec.COUNTERBORE_FIT_NOTE
    # The fitted tenon keeps its ferrule seat and the wall floor over the
    # bore, with the bore eccentricity budgeted (local review of 1f3067ef2),
    # the contour at the title block's .XX band; the root relief (owner
    # ruling 2026-10-24, #1900), landed off the skimmed shoulder, and the
    # break on its edge take the rest of the seat.
    assert spec.SHOULDER_R == pytest.approx(ferrule.INSTALLED_OUTER_DIA / 2.0)
    assert spec.BORE_ECCENTRICITY == pytest.approx(0.004 * IN)
    assert spec.FERRULE_SEAT_RADIAL_MIN >= spec.FERRULE_SEAT_RADIAL_FLOOR == 0.5
    assert spec.TENON_WALL_MIN >= WALL_FLOOR_MM
    assert spec.WAIST_WALL_MIN >= WALL_FLOOR_MM
    # The ring is skimmed with the shoulder, so its stock OD carries no band
    # (user ruling 2026-10-01).
    assert not hasattr(ferrule, "OUTER_DIA_TOL")
    assert model_toleranced_dimensions(handle) == {
        ("HandleProfile", "TenonRootRelief"): "TENON_ROOT_RELIEF_TOL",
    }
    assert not hasattr(spec, "TENON_LENGTH_TOL")
    assert spec.TENON_END_GAP_MIN == pytest.approx(
        (ferrule.LENGTH - _XX) - (spec.TENON_LENGTH + _XX)
    )
    assert spec.TENON_END_GAP_MIN > 0.0
    # The shortest tenon's bonded length after the tenon end's edge break and
    # the ferrule's seat-mouth break (owner ruling 2026-10-24, #1900: the root
    # relief stands behind the seat face, so it costs none).
    assert spec.TENON_GLUE_LENGTH_MIN == pytest.approx(
        spec.TENON_LENGTH - _XX - spec.EDGE_BREAK_MAX_MM - ferrule.SEAT_MOUTH_BREAK_MAX
    )
    assert spec.TENON_GLUE_LENGTH_MIN >= 3.5
    # F12 (#290): the .1610 reamer's band, which the walls are judged at.
    assert spec.PIVOT_BORE_DIA == pytest.approx(0.161 * IN)
    assert spec.PIVOT_BORE_BAND == pytest.approx((0.0005 * IN, 0.0))
    # No run-out: the cup cures centred on the waxed MHA-DT-32 at assembly
    # (MHA-DT-08 machinist review of 2026-10-18 found 0.2 TIR over-spec).
    assert not hasattr(spec, "BORE_RUNOUT_TIR")
    assert spec.CUP_OFFSET_MAX == pytest.approx(
        spec.BORE_ECCENTRICITY + spec.COUNTERBORE_GLUE_LINE[1] / 2.0
    )
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert (
        "for name in sorted(REFERENCE_DIMENSIONS | TANGENT_POINT_DIAMETERS):"
        in drawing_source
    )


def test_s_curve_tangent_point_prints_a_driven_reference_diameter() -> None:
    # MHA-DT-08 machinist review of 69eda6e4c: the inflection station ends on
    # the S-curve's tangent point, so its diameter prints there as a driven
    # reference; the convex arc meets the dome on the peak station, at the
    # printed swell diameter.
    spec = dt_crank_handle_spec
    assert spec.TANGENT_POINT_DIAMETERS == {"InflectionDia"}
    assert spec.TANGENT_POINT_DIAMETERS <= spec.DRAWING_DIMENSIONS["HandleProfile"]
    assert not spec.TANGENT_POINT_DIAMETERS & spec.REFERENCE_DIMENSIONS
    assert spec.INFLECTION[0] - spec.TENON_X0 == pytest.approx(0.71 * IN)
    assert round(2.0 * spec.INFLECTION[1] / IN, 2) == pytest.approx(0.49)
    assert spec.S_CONVEX_CENTER[0] == spec.DOME_CENTER[0] == spec.PEAK_X
    build_source = Path(handle.__file__).read_text(encoding="utf-8")
    assert "inflection_dimension.DrivenState = 1" in build_source
    assert (
        drawing.FRONT_KEEP["InflectionDia"][0]
        < drawing.FRONT_KEEP["PivotBoreDia"][0] - 0.017
    )


def test_inside_corners_print_a_max_radius_their_mates_clear() -> None:
    # Owner ruling A on #1661: the tenon root and the counterbore's floor
    # corner are modelled at R.012 and print the single limit "R.012 MAX"
    # (swTolMAX, build_pn_pen_rod's ShoulderRadius), each naming the part that
    # seats on it; the tenon root stands in its relief behind the ferrule's
    # seat face (owner ruling 2026-10-24, #1900) and the cup's 45-degree
    # chamfer clears the floor corner.
    spec = dt_crank_handle_spec
    corners = {"TenonRootRadius", "CounterboreFloorRadius"}
    assert spec.INSIDE_CORNER_R_MAX == pytest.approx(0.012 * IN)
    assert spec.INSIDE_CORNER_R_BAND == (0.0, -spec.INSIDE_CORNER_R_MAX)
    assert spec.INSIDE_CORNER_R_TOL_TYPE == 6
    assert corners <= spec.DRAWING_DIMENSIONS["HandleProfile"]
    assert not corners & (spec.REFERENCE_RADII | spec.REFERENCE_DIMENSIONS)
    assert all(spec.DRAWING_PRECISION_BY_NAME[name] == 3 for name in corners)
    assert spec.TENON_ROOT_RELIEF_MIN >= spec.TENON_ROOT_ROUND_REACH
    assert cup.BODY_CHAMFER_MIN >= spec.INSIDE_CORNER_R_MAX
    assert drawing.DIMENSION_CALLOUTS["TenonRootRadius"] == spec.TENON_ROOT_CALLOUT
    assert (
        drawing.DIMENSION_CALLOUTS["CounterboreFloorRadius"]
        == spec.COUNTERBORE_FLOOR_CALLOUT
    )
    assert spec.FERRULE_NAME in spec.TENON_ROOT_CALLOUT
    assert spec.CUP_NAME in spec.COUNTERBORE_FLOOR_CALLOUT
    # The blocks stand in narrow gaps: no row longer than "R.012 MAX".
    for callout in (spec.TENON_ROOT_CALLOUT, spec.COUNTERBORE_FLOOR_CALLOUT):
        assert max(len(row) for row in callout.split("\n")) <= len("R.012 MAX")
    assert set(drawing.INSIDE_CORNER_ARC_EXTENSION) == corners
    build_source = Path(handle.__file__).read_text(encoding="utf-8")
    assert '("InsideCornerR", INSIDE_CORNER_R_MAX)' in build_source
    assert "profile.record(name, '\"InsideCornerR\"')" in build_source
    assert "_inside_corner_max_limit(adapter, name)" in build_source
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert (
        "_dress_inside_corner(adapter, by_name[name], name=name)"
        in drawing_source
    )


def test_root_relief_prints_in_an_enlarged_detail_with_separate_leaders() -> None:
    # MHA-DT-08 machinist review of 3de09b959: at 4:1 the relief's leg, its
    # R0.3 MAX root and their blocks crowded one tiny corner.  Detail B, a
    # native detail of section A-A, carries both, each on its own leader.
    assert set(drawing.DETAIL_KEEP) == {"TenonRootRelief", "TenonRootRadius"}
    assert drawing.DETAIL_SCALE[0] / drawing.DETAIL_SCALE[1] >= 2.0 * drawing.SHEET_SCALE[0]
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "CreateDetailViewAt4(" in source
    # The leg's dimension runs from the tenon end's corner: the fence must
    # show it, the relief and its whole root round, or the import drops it.
    reach = drawing.DETAIL_RADIUS_MM - drawing._FENCE_MARGIN_MM
    for point in (
        (dt_crank_handle_spec.TENON_X0, dt_crank_handle_spec.TENON_R),
        handle.RELIEF_TOP,
        (handle.ROOT_CENTER[0] + dt_crank_handle_spec.INSIDE_CORNER_R_MAX, handle.ROOT_CENTER[1]),
    ):
        assert math.dist(drawing.DETAIL_FOCUS_MM, point) <= reach
    assert drawing._ROOT_CENTER == pytest.approx(handle.ROOT_CENTER)
    # Both blocks stand outside the circle, inside the border (x 0.0127 ..
    # 0.4191, y .. 0.2667): the leg's 23 x 27.4 mm block hangs left of its
    # keep, the R0.3 block's 22.0 x 14.6 mm centres on its keep.
    cx, cy = drawing.DETAIL_CENTER
    r = drawing.DETAIL_CROP_RADIUS
    leg_x, leg_y = drawing.DETAIL_KEEP["TenonRootRelief"]
    assert cx - r - leg_x >= 0.005
    assert leg_y + 0.0137 <= 0.2667 - 0.004
    root_x, root_y = drawing.DETAIL_KEEP["TenonRootRadius"]
    assert root_x - 0.011 - (cx + r) >= 0.008
    assert root_x + 0.011 <= 0.4191 - 0.010
    assert cy + r <= 0.2667 - 0.010
    # The R0.3 text stands inside the round's span (-90 to 45 degrees about
    # its centre), so its leader lands on the arc without an extension.
    centre = drawing._detail_xy(*handle.ROOT_CENTER)
    angle = math.degrees(math.atan2(root_y - centre[1], root_x - centre[0]))
    assert -90.0 < angle < 45.0
    assert drawing.INSIDE_CORNER_ARC_EXTENSION["TenonRootRadius"] is False


def test_tenon_root_relief_clears_the_ferrule_seat_and_keeps_the_tenon() -> None:
    # Owner ruling 2026-10-24 (#1900, option 4): a 45-degree relief cut into
    # the shoulder at the tenon root, so MHA-DT-34's seat mouth needs only the
    # edge break.  Its minimum keeps the R.012 MAX root round -- tangent
    # R (1 + sqrt 2) back from the root -- behind the seat face; its maximum
    # leaves the ferrule its floor of flat shoulder after the break on the
    # relief's edge and the relief landing off the skimmed shoulder; each
    # rounds inward to the printed thousandth.  The tenon is not cut, so its
    # wall over the pivot bore and its bonded length stand.
    spec = dt_crank_handle_spec
    radius = spec.INSIDE_CORNER_R_MAX
    step = 0.001 * IN
    assert spec.TENON_ROOT_ROUND_REACH == pytest.approx(radius * (1.0 + math.sqrt(2.0)))
    assert (spec.TENON_ROOT_RELIEF_MIN, spec.TENON_ROOT_RELIEF_MAX) == pytest.approx(
        (spec.TENON_ROOT_RELIEF - spec.TENON_ROOT_RELIEF_TOL,
         spec.TENON_ROOT_RELIEF + spec.TENON_ROOT_RELIEF_TOL)
    )
    assert spec.TENON_ROOT_RELIEF_MIN - step < spec.TENON_ROOT_ROUND_REACH
    assert spec.FERRULE_SEAT_RADIAL_MIN - step < spec.FERRULE_SEAT_RADIAL_FLOOR
    assert spec.TENON_WALL_MIN >= spec.TENON_WALL_FLOOR_MM
    assert "TenonRootRelief" in spec.DRAWING_DIMENSIONS["HandleProfile"]
    assert spec.DRAWING_PRECISION_BY_NAME["TenonRootRelief"] == 3
    assert (
        drawing.DIMENSION_CALLOUTS["TenonRootRelief"] == spec.TENON_ROOT_RELIEF_CALLOUT
    )
    # The band names the seat it serves and the cone's angle (rule 4).
    relief_callout = spec.TENON_ROOT_RELIEF_CALLOUT.replace("\n", " ")
    assert "45 DEG" in relief_callout and spec.FERRULE_NUMBER in relief_callout
    # The profile: the tenon OD runs on behind the seat face into the root
    # round, which the relief line leaves at 45 degrees for the shoulder face.
    relief = spec.TENON_ROOT_RELIEF
    assert handle.RELIEF_TOP == pytest.approx((spec.SHOULDER_X, spec.TENON_R + relief))
    assert handle.ROOT_ON_TENON[0] > spec.SHOULDER_X
    assert handle.ROOT_ON_RELIEF[0] - handle.RELIEF_TOP[0] == pytest.approx(
        handle.RELIEF_TOP[1] - handle.ROOT_ON_RELIEF[1]
    )
    assert math.dist(handle.ROOT_CENTER, handle.ROOT_ON_RELIEF) == pytest.approx(radius)
    assert handle.RELIEF_RUN == pytest.approx(relief - radius * (1.0 + 1.0 / math.sqrt(2.0)))
    assert handle.INSIDE_CORNER_ARC_LENGTHS == pytest.approx(
        (radius * math.pi / 2.0, radius * 3.0 * math.pi / 4.0)
    )
    build_source = Path(handle.__file__).read_text(encoding="utf-8")
    assert '("TenonRootRelief", TENON_ROOT_RELIEF)' in build_source
    assert """profile.record("TenonRootRelief", '"TenonRootRelief"')""" in build_source
    assert '(tenon_root, relief, "tenon root on the relief")' in build_source
    # The sweeps are read back from the saved profile after the final,
    # equation-driven rebuild (codjiflo on PR #1989).
    rebuilt = build_source.index("equations neutral")
    assert build_source.index("_check_root_arc_sweep(adapter)", rebuilt) > rebuilt


def test_grip_contour_is_tangent_arcs_dimensioned_on_the_section() -> None:
    # User rulings 2026-09-30 (ch30 eight-views-4, concept v4): the waist, the
    # inflection and the swell, printed from the tenon end face.
    spec = dt_crank_handle_spec
    assert (spec.WAIST_X - spec.TENON_X0, spec.WAIST_R * 2.0) == pytest.approx(
        (0.39 * IN, 0.37 * IN)
    )
    assert spec.INFLECTION[0] - spec.TENON_X0 == pytest.approx(0.71 * IN)
    assert (spec.PEAK_X - spec.TENON_X0, spec.PEAK_R * 2.0) == pytest.approx(
        (1.57 * IN, 0.83 * IN)
    )
    # Owner ruling B on #1375 widens the crest, not the swell or end round;
    # the tangent dome and its printed reference radius follow automatically.
    assert (spec.CREST_DIA, spec.END_ROUND_R) == pytest.approx((0.59 * IN, 0.06 * IN))
    assert math.dist(spec.DOME_CENTER, spec.END_ROUND_CENTER) == pytest.approx(
        spec.DOME_R - spec.END_ROUND_R
    )
    assert math.dist(spec.DOME_CENTER, spec.DOME_END) == pytest.approx(spec.DOME_R)
    assert math.dist(spec.END_ROUND_CENTER, spec.DOME_END) == pytest.approx(spec.END_ROUND_R)
    assert handle.CREST_DIA == spec.CREST_DIA
    assert handle.DOME_R == spec.DOME_R
    assert not hasattr(spec, "CONTOUR_ALLOWANCE_DIA")
    assert not hasattr(spec, "BASIC_DIMENSIONS")
    assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM")
    build_source = Path(handle.__file__).read_text(encoding="utf-8")
    assert 'profile.record(name, f"{knob} - {station}")' in build_source
    assert '("CrestDia", CREST_DIA)' in build_source
    assert '("CounterboreDia", COUNTERBORE_DIA)' in build_source
    assert '(dome, DOME_R, "DomeR")' in build_source
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "_style_radius(" in drawing_source


def test_ruling_b_butt_stays_inside_the_unchanged_grip_envelope() -> None:
    # Owner ruling B on #1375 changes the dome and end round after the same
    # swell station.  Each arc's entire circle stays no higher than the swell,
    # so the new contour cannot enlarge the existing radial bounding envelope.
    # This is a profile bound, not an assembled-clearance or full-motion proof.
    spec = dt_crank_handle_spec
    assert (spec.HANDLE_LENGTH, spec.PEAK_X, spec.HANDLE_MAX_DIA) == pytest.approx(
        (2.28 * IN, 1.65 * IN, 0.83 * IN)
    )
    assert spec.CREST_DIA < spec.HANDLE_MAX_DIA
    assert spec.DOME_CENTER[0] == spec.PEAK_X
    assert spec.DOME_CENTER[1] + spec.DOME_R == pytest.approx(spec.PEAK_R)
    assert spec.END_ROUND_CY + spec.END_ROUND_R <= spec.PEAK_R
    assert spec.profile_radius(spec.PEAK_X) == pytest.approx(spec.HANDLE_MAX_DIA / 2.0)
    assert spec.profile_radius(spec.HANDLE_LENGTH) == pytest.approx(spec.CREST_DIA / 2.0)
    assert spec.COUNTERBORE_FLOOR_X == pytest.approx(spec.HANDLE_LENGTH - spec.COUNTERBORE_DEPTH)
    assert (
        spec.SHOULDER_X, spec.SHOULDER_R, spec.TENON_X0, spec.TENON_LENGTH,
    ) == pytest.approx(
        (ferrule.LENGTH, ferrule.INSTALLED_OUTER_DIA / 2.0, 0.08 * IN, 0.20 * IN)
    )


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
    # User ruling 2026-09-29 (MHA-DT-08 review): a plain sheet.
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
    # Owner ruling B on #1375 changes no oak blank requirement: the swell
    # still bounds the enlarged butt and the ferrule shoulder.
    assert dt_crank_handle_spec.HANDLE_MAX_DIA == pytest.approx(0.83 * IN)
    assert dt_crank_handle_spec.CREST_DIA < dt_crank_handle_spec.HANDLE_MAX_DIA
    assert 2.0 * dt_crank_handle_spec.SHOULDER_R < dt_crank_handle_spec.HANDLE_MAX_DIA
    # The title block's MATERIAL field prints "material" (MHA-DT-08
    # machinist review of 2026-10-18: the grain belongs with the stock), in
    # its one-line 36-character cell (Codex P2 on #1650); the long form
    # stays in material_specification.
    assert "grain axial" in spec["material"]
    assert len(str(spec["material"])) <= 36
    assert "straight grain along axis" in spec["material_specification"]
    assert "6-8% MC" in spec["material_specification"]
    # The poly film stays out of the running bore and the two glued fits
    # (machinist review, 2026-10-18).
    assert "mask" in spec["finish"]
    assert int(spec["quantity"]) == 1
