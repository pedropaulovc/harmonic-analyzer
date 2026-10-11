"""Offline behavioral contracts for the cone-gear batch drawing package."""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest
import yaml

import _config
import _drawing_leaders
import _cone_gear_geometry as geometry
import build_dt_cone_gear as part
import dt_cone_gear_notes as notes
import dt_cone_gear_shaft_spec
import dt_cone_gear_spec as spec
import draw_dt_cone_gear as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths_and_registry_entry() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/dt-cone-gear.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/dt-cone-gear.pdf")
    assert drawing.PNG.as_posix().endswith("/png/dt-cone-gear_drawing.png")
    assert DRAWINGS_BY_NAME["dt_cone_gear"].script == Path(drawing.__file__).resolve()


def test_every_configuration_has_one_complete_sheet_and_native_scale() -> None:
    expected_teeth = tuple(range(6, 121, 6))
    expected_names = tuple(f"T{teeth:03d}" for teeth in expected_teeth)
    assert spec.CONFIGURATION_TEETH == expected_teeth
    assert spec.CONFIGS == tuple(zip(expected_names, expected_teeth, strict=True))
    assert drawing.SHEET_NAMES == expected_names
    assert set(drawing.SHEET_SCALES) == set(expected_names)

    for teeth in expected_teeth:
        name = f"T{teeth:03d}"
        numerator, denominator = drawing.SHEET_SCALES[name]
        drawn_od = drawing.outside_dia_mm(teeth) * numerator / denominator
        # The smallest six-tooth member is necessarily limited by the common
        # 6.8887 mm face width; every other face lands in the useful 40-95 mm band.
        assert 30.0 < drawn_od < 95.0
        assert drawing.rendered_half_od(teeth) == pytest.approx(drawn_od / 2000.0)


def test_part_and_drawing_share_the_complete_native_dimension_contract() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert marked == {
        "BlankDia",
        "FaceWidth",
        "BoreCutDia",
        "BoreAF",
        "BoreFlatClock",
        "ToothThickness",
        "FloorDia",
    }
    for teeth in spec.CONFIGURATION_TEETH:
        views = (
            drawing.front_keep(teeth),
            drawing.right_keep(teeth),
            drawing.bore_view_keep(teeth),
        )
        kept = [name for keep in views for name in keep]
        # Every marked dimension prints exactly once per sheet.
        assert sorted(kept) == sorted(marked)
        # The whole D-bore prints in the bore view, and only there.
        assert set(drawing.bore_view_keep(teeth)) == spec.DRAWING_DIMENSIONS["BoreProfile"]


def test_model_owns_precision_for_every_printed_dimension() -> None:
    assert spec.DRAWING_PRECISION_BY_NAME == {
        "BlankDia": 2,
        # 6.8887 is floor4(SEAT_PITCH): fewer places would print a face that
        # rounds up past the 6.8888 seat pitch.
        "FaceWidth": 4,
        "BoreCutDia": 3,
        # The AF band is 0.010 wide; three places print both limits exactly.
        "BoreAF": 3,
        "BoreFlatClock": 1,
        "ToothThickness": 3,
        # The T006 floor window is 0.049 wide: two places would print the
        # upper limit rounded up (probe 834-gapfloor-c301 showed .049 as .05).
        "FloorDia": 3,
    }
    assert "draw_dt_cone_gear.py" in PRECISION_MIGRATED_DRAWINGS


def test_tip_diameter_carries_its_own_mesh_depth_band() -> None:
    # Main ruling (2026-09-23): the title-block .XX +/-0.51 is a whole
    # addendum; the contact-ratio stack kept +/-0.25 below CR 1.1, so the
    # tip prints +/-0.10, applied on the model like the other two bands.
    assert spec.BLANK_DIA_BAND == (0.10, -0.10)
    assert spec.BLANK_DIA_BAND[0] < spec.MODULE_MM / 2.0
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert (
        '"BlankProfile", "BlankDia", *deviations(BLANK_DIA_BAND)' in source
    )


def test_face_width_fills_the_seat_pitch_without_crossing_it() -> None:
    # Solid touching stack: twenty gears end to end on SEAT_PITCH centres.
    # The nominal is the seat pitch floored to 4 places, so it never prints
    # longer than the pitch; cone_gear_stack owns the stack's band.
    assert spec.FACE_WIDTH == pytest.approx(6.8887, abs=1e-12)
    assert spec.FACE_WIDTH <= spec.SEAT_PITCH < spec.FACE_WIDTH + 1e-4
    assert spec.FACE_WIDTH_BAND == (0.025, -0.025)
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert '"Blank", "FaceWidth", *deviations(FACE_WIDTH_BAND)' in source


def test_each_configuration_sheet_carries_its_own_drawing_number() -> None:
    number = str(_config.parts("dt-cone-gear")["number"])
    assert spec.configuration_number(number, 6) == f"{number}-T006"
    assert spec.configuration_number(number, 120) == f"{number}-T120"
    numbers = {spec.configuration_number(number, t) for t in spec.CONFIGURATION_TEETH}
    assert len(numbers) == len(spec.CONFIGURATION_TEETH)
    with pytest.raises(ValueError):
        spec.configuration_number(number, 7)
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert '"Number": configuration_number(part_number, teeth)' in source


def test_bore_bands_are_the_derived_seat_fit_bands() -> None:
    # Every gear slides onto its D-flat land (gear_seat_fit): the family's one
    # BoreCutDia band is +0.050/+0.025 and its one BoreAF band +0.020/+0.010
    # (test_cone_gear_seat_fit proves every seat at the print extremes).
    assert part.BORE_DIA_BAND is spec.BORE_DIA_BAND
    assert spec.BORE_DIA_BAND == (0.05, 0.025)
    assert spec.BORE_AF_BAND == pytest.approx((0.02, 0.01))
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert '"BoreProfile", "BoreCutDia", *deviations(BORE_DIA_BAND)' in source
    assert '"BoreProfile", "BoreAF", *deviations(BORE_AF_BAND)' in source

    # Every configured bore seats on a published cone-shaft land; T006 and
    # T012 slide straight onto the flatted 1/16-inch tip land.
    assert spec.bore_dia_mm(6) == pytest.approx(1.5875)
    assert spec.FAMILY_BORES_MM[6] == pytest.approx(
        dt_cone_gear_shaft_spec.SECTION_DIAS[-1]
    )
    for bore in spec.FAMILY_BORES_MM.values():
        assert any(
            bore == pytest.approx(section)
            for section in dt_cone_gear_shaft_spec.SECTION_DIAS
        )


def test_native_tooth_thickness_is_the_modelled_deepened_mesh_tooth() -> None:
    # The band is the configured backlash WINDOW, centred on the modelled
    # tooth: error_budget.yaml's tooth-thickness mesh-lag term is derived
    # from that window.
    minimum, maximum = _config.fit("gear_mesh", "backlash_mm")
    upper, lower = spec.TOOTH_THICKNESS_BAND
    assert upper == pytest.approx(-lower)
    assert upper - lower == pytest.approx(maximum - minimum)
    for teeth in spec.CONFIGURATION_TEETH:
        thickest = spec.DEEPENED_MESH_MM[teeth][1]
        assert spec.tooth_thickness_mm(teeth) + upper == pytest.approx(thickest)
        # Thicker than standard at both limits: the deepened mesh.
        assert spec.tooth_thickness_mm(teeth) + lower > spec.STANDARD_TOOTH_THICKNESS
        facts = geometry.cone_facts(teeth)
        assert facts["ToothThickness"] * spec.MM_PER_IN == pytest.approx(
            spec.tooth_thickness_mm(teeth)
        )
        assert 2.0 * facts["Ra"] * spec.MM_PER_IN == pytest.approx(
            spec.outside_dia_mm(teeth)
        )
    assert spec.TOOTH_THICKNESS == pytest.approx(spec.tooth_thickness_mm(120))
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "*deviations(TOOTH_THICKNESS_BAND)" in source
    # Delta solves from the printed thickness, so the flanks follow it.
    assert '"ToothThickness" * "DP" / "ToothCount" + tan("PA") - "PArad"' in source


def test_each_sheet_gets_its_own_tooth_system_block_without_dimension_duplicates() -> None:
    for teeth in spec.CONFIGURATION_TEETH:
        data = notes.gear_data(teeth)
        assert data.startswith("GEAR DATA\n")
        assert f"CONFIGURATION:  T{teeth:03d}" in data
        assert f"NUMBER OF TEETH:  {teeth}" in data
        assert f"PITCH DIAMETER (mm, REF):  {teeth * spec.MODULE_MM:.2f}" in data
        assert "DIAMETRAL PITCH" in data
        assert "PRESSURE ANGLE" in data
        assert "INVOLUTE FLANKS" in data
        assert f"CYLINDER GEAR {notes.CYLINDER_MATE_NUMBER}" in data
        # The tooth form and the floor's native limit dimension state the
        # result, so no row says how to cut it (rule 6).
        for method in ("CUTTING", "CUTTER", "PLUNGE", "INDEXING", "SINKING"):
            assert method not in data
        assert spec.TOOTH_FORM in data
        assert "FULL DEPTH" not in data
        assert "WHOLE DEPTH" not in data
        assert notes.CYLINDER_MATE_NUMBER in data
        assert (
            f"BACKLASH WITH MHA-DT-012, ACCEPT AT ASSEMBLY (mm):  "
            f"{spec.BACKLASH_ACCEPTANCE_MM[0]:.2f} TO "
            f"{spec.BACKLASH_ACCEPTANCE_MM[1]:.2f}"
        ) in data
        # The operating mesh is not a reference-centre-distance mesh; say so
        # beside the mate, and say where the view's thickness is measured.
        assert "TOOTH THICKNESS IN VIEW:  ARC LENGTH AT PITCH DIAMETER" in data
        # 49.1 mm measured for 14 lines natively (e91d2581 layout audit).
        assert len(data.splitlines()) * 0.00351 <= drawing.GEAR_DATA_HEIGHT
        assert "OPERATING MESH:  LONG ADDENDUM, PARTIAL DEPTH ON INCLINED AXES" in data
        assert "48 DP" not in data
        # These values are native imported dimensions, never parallel typed rows.
        for duplicate in (
            "OUTSIDE DIAMETER",
            "FACE WIDTH",
            "BORE",
            "CIRCULAR TOOTH THICKNESS",
            "GAP FLOOR DIAMETER",
            "FAMILY T",
        ):
            assert duplicate not in data


def test_gap_floor_constructions() -> None:
    # T006/T012 keep the standard tooth's base chord (the drum tip would rub a
    # risen chord); T018-T042 take the thicker tooth's chord; T048+ raise it.
    for teeth in spec.CONFIGURATION_TEETH:
        chord = spec.chord_floor_radius_mm(
            teeth,
            thickness_mm=spec.tooth_thickness_mm(teeth),
            tmin=spec.floor_tmin(teeth),
        )
        minimum, maximum = spec.floor_limits_mm(teeth)
        assert maximum > minimum
        # Bands round outward: the printed MIN is the modelled floor floored
        # to three places, never above it.
        modelled = 2.0 * spec.floor_radius_mm(teeth)
        assert modelled - 0.001 < minimum <= modelled
        assert minimum == pytest.approx(round(minimum, 3), abs=1e-12)
        if teeth in spec.DIPPED_FLOOR_MIN_MM:
            assert spec.floor_radius_mm(teeth) == pytest.approx(minimum / 2.0)
            assert spec.floor_dip_mm(teeth) > 0.0
            assert spec.floor_tmin(teeth) == 0.0
            continue
        assert spec.floor_radius_mm(teeth) == pytest.approx(chord)
        assert spec.floor_dip_mm(teeth) == pytest.approx(0.0)
        assert (spec.floor_tmin(teeth) > 0.0) == (teeth >= 48)
    assert set(spec.DIPPED_FLOOR_MIN_MM) == {6, 12}
    assert set(spec.FLOOR_MAX_DIA_MM) == set(spec.CONFIGURATION_TEETH)


def test_configuration_owned_bores_and_title_block_alloys_cover_the_family() -> None:
    registry = _config.parts("dt-cone-gear")
    assert spec.BODY_MATERIAL_SPEC == registry["material_specification"]
    assert spec.TIP_MATERIAL_SPEC == registry["material_tip_specification"]
    assert spec.TIP_MATERIAL_SPEC != spec.BODY_MATERIAL_SPEC
    # Brass and manganese bronze take no coating; the field says so rather
    # than reading as a missing value.  "Gear teeth cut; polished" (before
    # e44791855) was a method, and polishing would round the tooth edges
    # note 1 forbids breaking.
    assert registry["finish"] == "AS MACHINED, UNCOATED"
    assert str(registry["finish"]).strip().upper() not in {"", "NONE", "N/A"}
    for teeth in spec.CONFIGURATION_TEETH:
        assert part.bore_dia_in(teeth) * spec.MM_PER_IN == pytest.approx(
            spec.bore_dia_mm(teeth)
        )
        expected = spec.TIP_MATERIAL_SPEC if teeth <= 24 else spec.BODY_MATERIAL_SPEC
        assert spec.material_specification(teeth) == expected


def test_notes_state_no_bore_joint_method_or_review_record() -> None:
    # Rule 6: the D-bore and its fit print as native dimensions in the bore
    # view; no joint, keyway or retaining method is named.  The U42/U40
    # shortfalls print once each, as GEAR DATA rows (test_named_shortfalls_
    # print_as_facts_on_their_sheets), so the notes never repeat them.  Every
    # sheet prints the same two lines.
    expected = [
        "DO NOT BREAK OR CHAMFER EDGES ON TOOTH FLANKS, TIPS OR ROOTS.",
        "MAKE ONE GEAR FROM EACH SHEET IN THIS PACKAGE.",
    ]
    assert notes.DRAWING_NOTES.splitlines() == expected
    assert not hasattr(notes, "ATTACHMENT")
    for teeth in spec.CONFIGURATION_TEETH:
        text = notes.drawing_notes(teeth)
        assert text.splitlines() == expected
        for review_or_method in (
            "SOLDER",
            "BRAZE",
            "LOCTITE",
            "BOND",
            "KEYWAY",
            "AT ASSEMBLY",
            "EXCEPTION",
            "BOOK FIDELITY",
            "CONTACT RATIO",
            "WEB",
        ):
            assert review_or_method not in text
        for unsupported in ("PIN", "SET SCREW", "HUB"):
            assert unsupported not in text
        for retired in ("RUNOUT", "DATUM", "+/-", "PITCH DIA="):
            assert retired not in text
    assert notes.CYLINDER_MATE_NUMBER == _config.parts("dt-cylinder-gear")["number"]
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert '"Manufacturing Notes": drawing_notes(teeth)' in source


def test_book_fidelity_exceptions_are_recorded_in_the_spec_not_on_a_sheet() -> None:
    # U42 (contact ratio below 1.1) and U40 (T006's thin web) are exact sets:
    # test_cone_gear_mesh_design and the root-to-bore web test re-derive which
    # gears need them, so a new exception needs a new ruling, not a quiet edit.
    assert spec.CONTACT_RATIO_EXCEPTION_TEETH == (6, 12, 18, 24, 30, 36, 42)
    assert spec.WEB_EXCEPTIONS_MM == {6: 0.621}
    for retired in ("CONTACT_RATIO_EXCEPTION", "web_exception", "both_exceptions"):
        assert not hasattr(notes, retired)


@pytest.mark.parametrize("teeth", spec.CONFIGURATION_TEETH)
def test_named_shortfalls_print_as_facts_on_their_sheets(teeth: int) -> None:
    # The blind reviewer sees only the sheets, so every sheet a named
    # exception row affects states the shortfall itself, as a plain fact with
    # its value (drawing-simplicity policy, named exceptions); the ruling
    # never prints (test_no_sheet_prints_a_review_record).
    data = notes.gear_data(teeth)
    web_label = "WEB, GAP FLOOR TO HOLE (mm, REF):  "
    if teeth in spec.WEB_EXCEPTIONS_MM:
        web = notes.root_to_bore_web_min_mm(teeth)
        # the printed limits give exactly the web the user accepted
        assert web == pytest.approx(spec.WEB_EXCEPTIONS_MM[teeth], abs=0.0005)
        # stated rounded DOWN: never more web than the limits give
        stated = float(data.split(web_label)[1].split()[0])
        assert 0.0 <= web - stated < 0.01
        assert f"{web_label}{stated:.2f} MIN" in data
    else:
        assert web_label not in data
        assert notes.root_to_bore_web_min_mm(teeth) >= spec.MACHINED_WEB_FLOOR_MM
    ratio_row = f"CONTACT RATIO WITH {notes.CYLINDER_MATE_NUMBER}, WORST CASE (REF):  "
    assert set(notes.WORST_CONTACT_RATIO) == set(spec.CONTACT_RATIO_EXCEPTION_TEETH)
    if teeth in spec.CONTACT_RATIO_EXCEPTION_TEETH:
        assert f"{ratio_row}{notes.WORST_CONTACT_RATIO[teeth]:.2f}" in data
    else:
        assert ratio_row not in data


_REVIEW_RECORD_TEXT = re.compile(
    r"RULE \d|U\d\d|EXCEPTION|BOOK FIDELITY|POLICY|RULING"
)


@pytest.mark.parametrize("teeth", spec.CONFIGURATION_TEETH)
def test_no_sheet_prints_a_review_record(teeth: int) -> None:
    # Rulings, exceptions and policy rules are provenance for the design
    # review (finding-rulings.md, code comments); a machinist cannot act on
    # them, so neither printed text block may carry one.
    for printed in (notes.drawing_notes(teeth), notes.gear_data(teeth)):
        assert not _REVIEW_RECORD_TEXT.search(printed), printed


def test_no_gdt_and_only_the_fitted_bore_has_a_surface_finish() -> None:
    assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(spec, "GEOMETRIC_CONTROLS")
    assert not hasattr(spec, "PART_DATUMS")
    assert [control.key for control in spec.SURFACE_FINISHES] == ["cone_gear_bore"]
    assert spec.SURFACE_FINISHES[0].native_attachment == "model"
    for teeth in spec.CONFIGURATION_TEETH:
        control = spec.bore_surface_finish(teeth)
        assert control.key == "cone_gear_bore"
        assert control.native_attachment == "model"
        assert control.face.diameter_mm == pytest.approx(spec.bore_dia_mm(teeth))


def test_every_sheet_layout_keeps_views_dimensions_and_title_block_separate() -> None:
    for teeth in spec.CONFIGURATION_TEETH:
        half_od = drawing.rendered_half_od(teeth)
        half_face = drawing.rendered_half_face_width(teeth)
        front = drawing.front_keep(teeth)
        right = drawing.right_keep(teeth)
        bore = drawing.bore_view_keep(teeth)
        for x, y in (*front.values(), *right.values(), *bore.values()):
            assert 0.012 < x < 0.420
            assert 0.012 < y < 0.267
            assert not (x > 0.216 and y < 0.070)
        assert drawing.FRONT_CENTER[0] + half_od < drawing.RIGHT_CENTER[0] - half_face
        assert drawing.RIGHT_CENTER[0] + half_face < drawing.ISO_CENTER[0] - half_od
        assert front["BlankDia"][1] < drawing.GEAR_DATA_POS[1] - 0.035
        # Third-angle projection: the side view shares the front bore axis.
        assert drawing.RIGHT_CENTER[1] == drawing.FRONT_CENTER[1]
        # The Gear Data block clears the largest side view, and the face-width
        # dimension hangs BELOW the side view -- the native layout audit
        # missed the text collision this replaced on T084 and T108-T120.
        assert (
            drawing.GEAR_DATA_POS[1] - drawing.GEAR_DATA_HEIGHT
            > drawing.RIGHT_CENTER[1] + half_od + 0.008
        )
        assert right["FaceWidth"][1] < drawing.RIGHT_CENTER[1] - half_od - 0.008
        # The face-width text never sits on its extension lines (#834
        # machinist review, sheets 5-20): centred only where the face spans
        # the text plus a clearance each side, otherwise wholly right of the
        # right extension line and still clear of the iso view.
        text_x = right["FaceWidth"][0]
        text_half = drawing.FACE_WIDTH_TEXT_WIDTH / 2.0
        clearance = drawing.FACE_WIDTH_TEXT_CLEARANCE
        if drawing.face_width_text_inside(teeth):
            assert text_x == pytest.approx(drawing.RIGHT_CENTER[0])
            assert half_face - text_half >= clearance
        else:
            assert text_x - text_half >= drawing.RIGHT_CENTER[0] + half_face + clearance
            assert text_x + text_half < drawing.ISO_CENTER[0] - half_od - 0.005
        # Thickness text (~65 mm callout centred on its x) sits below the gear,
        # left of the side view and its face-width dimension.
        ctt_x, ctt_y = front["ToothThickness"]
        assert ctt_y < drawing.FRONT_CENTER[1] - half_od - 0.015
        assert ctt_x + 0.0325 < drawing.RIGHT_CENTER[0] - half_face - 0.020
        assert ctt_x - 0.0325 > bore["BoreCutDia"][0] + _BORE_DIA_TEXT_HALF_WIDTH + 0.010
        # The bore finish sits above-left of the gear, inside the border and
        # below the manufacturing notes.
        (edge_x, edge_y), (symbol_x, symbol_y) = drawing.bore_finish_xy(teeth)
        assert edge_x < drawing.FRONT_CENTER[0] and edge_y > drawing.FRONT_CENTER[1]
        assert 0.015 < symbol_x < drawing.FRONT_CENTER[0] - half_od * 0.7
        assert drawing.FRONT_CENTER[1] + half_od * 0.7 < symbol_y < 0.225
        assert front["ToothThickness"][0] > drawing.FRONT_CENTER[0] + half_od
        # The gap-floor limit stack (two 3-place values plus "GAP FLOOR",
        # ~17 x 11 mm) stands right of the tip circle, above the thickness
        # witness, left of the side view and below the Gear Data block.
        floor_x, floor_y = front["FloorDia"]
        assert floor_x - _FLOOR_TEXT_HALF_WIDTH > drawing.FRONT_CENTER[0] + half_od
        assert floor_x + _FLOOR_TEXT_HALF_WIDTH < drawing.RIGHT_CENTER[0] - half_face - 0.020
        # The shelf under "GAP FLOOR" keeps the fleet's arrow-to-text
        # clearance from the thickness dimension's upper arrow tail: one
        # template arrow length past the witness, which stands half the arc
        # thickness above the bore axis at sheet scale (an upper bound on the
        # chord it witnesses).
        numerator, denominator = drawing._SCALE_BY_TEETH[teeth]
        witness_y = (
            drawing.FRONT_CENTER[1]
            + spec.tooth_thickness_mm(teeth) * numerator / (denominator * 2000.0)
        )
        tail_y = witness_y + drawing.DIMENSION_ARROW_LENGTH
        shelf_y = floor_y - drawing.FLOOR_STACK_HALF_HEIGHT
        assert shelf_y - tail_y >= _drawing_leaders.ARROW_TEXT_CLEARANCE - 1e-9, teeth
        assert (
            floor_y + drawing.FLOOR_STACK_HALF_HEIGHT
            < drawing.GEAR_DATA_POS[1] - drawing.GEAR_DATA_HEIGHT
        )
        # The shelf rises only where the tail needs it: every other sheet
        # keeps the stack's usual place.
        usual = (
            drawing.FRONT_CENTER[1] + 0.6 * half_od + drawing.FLOOR_DIA_RISE
        )
        assert floor_y >= usual - 1e-12
        if floor_y > usual:
            assert shelf_y - tail_y == pytest.approx(_drawing_leaders.ARROW_TEXT_CLEARANCE)


# Text half-widths in the bore view, sheet metres: the stacked diameter
# (~33 mm, measured when its callout still read "REAM THRU"; "THRU" is
# narrower) and the clock value over "TO TOOTH CENTERLINE" (~42 mm,
# estimated at the fleet's 2.5 mm text), and the two-line title.
_BORE_DIA_TEXT_HALF_WIDTH = 0.0165
_BORE_CALLOUT_TEXT_HALF_WIDTH = 0.021
_BORE_TEXT_HALF_HEIGHT = 0.005
_BORE_TITLE_HEIGHT = 0.008
_THICKNESS_TEXT_HALF_WIDTH = 0.0325
# The layout audit compares IView.GetOutline boxes, which pad the geometry:
# ~5.5 mm round an uncropped view (T084 front [54.8, 99.8, 155.2, 200.2]
# about a 44.66 mm half tip circle) and 10.1-10.75 mm past a bore view's crop
# circle (T006-T024 and T030+ sheets; 11.3 is taken as the pad), inside the
# sheet format's 12.7 mm zone band (_drawing_common.sheet_drawable_region;
# farm run 20260929T061328212Z at 70d2e52).
_FRONT_OUTLINE_PAD = 0.0056
_CROPPED_OUTLINE_PAD = 0.0113
_ZONE_MARGIN = 0.0127


def test_bore_view_enlarges_every_d_bore_clear_of_its_neighbours() -> None:
    ladder = [n / d for n, d in drawing.BORE_VIEW_SCALE_LADDER]
    cx, cy = drawing.BORE_VIEW_CENTER
    for teeth in spec.CONFIGURATION_TEETH:
        numerator, denominator = drawing._SCALE_BY_TEETH[teeth]
        sheet_ratio = numerator / denominator
        view_numerator, view_denominator = drawing.bore_view_scale(teeth)
        ratio = view_numerator / view_denominator
        bore = spec.bore_dia_mm(teeth)
        # Enlarged past the sheet, to the smallest ladder ratio that renders
        # the bore legibly, with the flat at least 2.5 mm deep on paper.
        assert ratio > sheet_ratio
        assert bore * ratio / 1000.0 >= drawing.BORE_VIEW_BORE_MIN
        assert all(
            bore * smaller / 1000.0 < drawing.BORE_VIEW_BORE_MIN
            for smaller in ladder
            if sheet_ratio < smaller < ratio
        )
        depth = (bore / 2.0 - spec.bore_flat_offset_mm(teeth)) * ratio / 1000.0
        assert depth >= 0.0025, teeth
        crop = drawing.bore_view_crop_radius(teeth)
        assert crop > bore * ratio / 2000.0
        # The crop circle stands inside the border and clear of the front
        # view's tip circle, and the boxes the audit compares stay apart: the
        # views overlap in x, so the bore view's box must sit under the front
        # view's on every sheet (T084 met it at y 0.066 with a 7 mm margin).
        assert cx - crop - _CROPPED_OUTLINE_PAD > _ZONE_MARGIN
        assert cy - crop - _CROPPED_OUTLINE_PAD > _ZONE_MARGIN
        half_od = drawing.rendered_half_od(teeth)
        assert math.dist((cx, cy), drawing.FRONT_CENTER) > crop + half_od + 0.010
        front_bottom = drawing.FRONT_CENTER[1] - half_od - _FRONT_OUTLINE_PAD
        assert cy + crop + _CROPPED_OUTLINE_PAD + 0.002 < front_bottom, teeth
        keep = drawing.bore_view_keep(teeth)
        for x, y in keep.values():
            assert math.dist((x, y), drawing.FRONT_CENTER) > half_od + 0.015
        dia_x, dia_y = keep["BoreCutDia"]
        assert dia_x - _BORE_DIA_TEXT_HALF_WIDTH > 0.012
        assert dia_y - _BORE_TEXT_HALF_HEIGHT > cy + crop - 0.003
        # The across-flat text stands wholly right of the flat's witness,
        # left of the title block, above the title, which stays inside the
        # border, and under the clock's text.
        af_x, af_y = keep["BoreAF"]
        flat = spec.bore_flat_offset_mm(teeth) * ratio / 1000.0
        assert af_x - drawing.BORE_VIEW_AF_HALF_WIDTH > cx + flat + 0.002
        assert af_x + drawing.BORE_VIEW_AF_HALF_WIDTH < 0.216
        assert af_y < cy - crop
        title_top = drawing.bore_view_label_top(teeth)
        assert af_y - 2.0 * _BORE_TEXT_HALF_HEIGHT > title_top
        assert title_top - _BORE_TITLE_HEIGHT > _ZONE_MARGIN + 0.001
        assert af_y + 2.0 * _BORE_TEXT_HALF_HEIGHT < keep["BoreFlatClock"][1] - 0.010
        # The clock text stands wholly right of the circle and clear of the
        # thickness callout under the front view.
        clock_x, clock_y = keep["BoreFlatClock"]
        assert clock_x - _BORE_CALLOUT_TEXT_HALF_WIDTH > cx + crop
        ctt_x, ctt_y = drawing.front_keep(teeth)["ToothThickness"]
        assert (
            ctt_x - _THICKNESS_TEXT_HALF_WIDTH
            > clock_x + _BORE_CALLOUT_TEXT_HALF_WIDTH + 0.005
            or ctt_y - clock_y > 4.0 * _BORE_TEXT_HALF_HEIGHT
        ), teeth
        # The clock's arc centres where the flat crosses the axis and swings
        # through its text, in the quadrant right of the flat and above the
        # axis: clear of the diameter's upper-left lane and under the front
        # view. Left in the sketch's upper-left quadrant, it crossed the
        # diameter's shoulder on every 4:1 sheet.
        vx, vy = drawing.bore_flat_vertex(teeth)
        assert (vx, vy) == pytest.approx((cx + flat, cy))
        assert clock_x > vx and clock_y > vy
        reach = math.dist((vx, vy), (clock_x, clock_y))
        assert dia_x + _BORE_DIA_TEXT_HALF_WIDTH < vx - 0.005
        assert vy + reach + 0.003 < front_bottom, teeth
        assert drawing.bore_view_label(teeth).splitlines() == [
            "BORE PROFILE",
            f"SCALE {view_numerator:g} : {view_denominator:g}",
        ]


def test_dimension_arrow_length_is_read_from_the_drawing() -> None:
    """The layout's arrow length is the drawing's own, not a remembered one."""

    class _Extension:
        def __init__(self, value: float) -> None:
            self.value = value
            self.calls: list[tuple[int, int]] = []

        def GetUserPreferenceDouble(self, pref: int, option: int) -> float:  # noqa: N802
            self.calls.append((pref, option))
            return self.value

    class _Drawing:
        def __init__(self, value: float) -> None:
            self.Extension = _Extension(value)

    matching = _Drawing(drawing.DIMENSION_ARROW_LENGTH)
    drawing._assert_dimension_arrow_length(matching)
    # swDetailingArrowLength, swDetailingNoOptionSpecified
    assert matching.Extension.calls == [(26, 0)]
    with pytest.raises(RuntimeError, match="drawing arrow length reads 3.175 mm"):
        drawing._assert_dimension_arrow_length(_Drawing(0.003175))


# The gap-floor stack: "Ø61.050" over "Ø60.485" over "GAP FLOOR" at 3.5 mm
# text, the widest row 9 characters at ~1.85 mm.
_FLOOR_TEXT_HALF_WIDTH = 9 * 0.00185 / 2.0


class _FakeFeature:
    def __init__(self, visible: int) -> None:
        self.Visible = visible


class _FakePart:
    """A part document that records sketch blanks and reports visibility."""

    def __init__(self, *, hides: bool) -> None:
        self.hides = hides
        self.selected: list[tuple[str, str]] = []
        self.blanked: list[str] = []
        self.Extension = self

    def ClearSelection2(self, _all: bool) -> None:
        pass

    def SelectByID2(self, name: str, kind: str, *_args: object) -> bool:
        self.selected.append((name, kind))
        return True

    def BlankSketch(self) -> None:
        self.blanked.append(self.selected[-1][0])

    def FeatureByName(self, name: str) -> _FakeFeature:
        # swVisibilityState_e: 1 hidden, 2 shown
        return _FakeFeature(1 if self.hides and name in self.blanked else 2)


class _FakeAdapter:
    def __init__(self, model: object) -> None:
        self.currentModel = model


def test_the_part_saves_both_authoring_sketches_hidden() -> None:
    """#950's save gate: a shown construction sketch renders in the part images
    and in every assembly that places a gear, so the part blanks both before
    its first save and reads the blank back."""
    model = _FakePart(hides=True)
    part._blank_reference_sketches(_FakeAdapter(model))
    sketches = [spec.TOOTH_REFERENCE_SKETCH, spec.GAP_FLOOR_SKETCH]
    assert model.selected == [(sketch, "SKETCH") for sketch in sketches]
    assert model.blanked == sketches
    source = Path(part.__file__).read_text(encoding="utf-8")
    body = source[source.index("async def build(") :]
    assert body.index("_blank_reference_sketches(adapter)") < body.index(
        "await adapter.save_file("
    )


def test_a_blank_that_does_not_take_fails_the_part_build() -> None:
    with pytest.raises(RuntimeError, match="still visible after BlankSketch"):
        part._blank_reference_sketches(_FakeAdapter(_FakePart(hides=False)))


class _FakeTolerance:
    def __init__(self, accept: bool = True) -> None:
        self.Type = 0
        self.accept = accept
        self.calls: list[tuple[float, float, int, list[str]]] = []

    def SetValues2(self, lower: float, upper: float, which: int, names: object) -> bool:
        self.calls.append((lower, upper, which, list(names.value)))
        return self.accept


def _patch_floor_dimension(monkeypatch: pytest.MonkeyPatch, tolerance: object) -> None:
    dimension = type("Dimension", (), {"Tolerance": tolerance})()

    def named(_adapter: object, feature: str, name: str) -> tuple[object, object]:
        assert (feature, name) == (spec.GAP_FLOOR_SKETCH, "FloorDia")
        return object(), dimension

    monkeypatch.setattr(part, "_named_dimension", named)


def test_each_configuration_stores_its_own_gap_floor_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#834 Codex P1: the floor band is a native per-configuration LIMIT, one
    SetValues2 per configuration naming only that configuration."""
    tolerance = _FakeTolerance()
    _patch_floor_dimension(monkeypatch, tolerance)
    part._set_gap_floor_limits(object())
    assert tolerance.Type == 3  # swTolLIMIT
    assert [call[3] for call in tolerance.calls] == [[name] for name, _ in spec.CONFIGS]
    for (lower, upper, which, _names), (_name, teeth) in zip(
        tolerance.calls, spec.CONFIGS, strict=True
    ):
        assert which == 3  # swSetValue_InSpecificConfigurations
        nominal = 2.0 * spec.floor_radius_mm(teeth)
        minimum, maximum = spec.floor_limits_mm(teeth)
        assert nominal + lower * 1000.0 == pytest.approx(minimum, abs=1e-9)
        assert nominal + upper * 1000.0 == pytest.approx(maximum, abs=1e-9)
        assert lower <= 0.0 < upper


def test_a_rejected_configuration_limit_fails_the_part_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_floor_dimension(monkeypatch, _FakeTolerance(accept=False))
    with pytest.raises(RuntimeError, match="FloorDia@T006: SetValues2 rejected"):
        part._set_gap_floor_limits(object())


def test_only_the_front_view_shows_the_authoring_sketches() -> None:
    """Both sketches' dimensions live on the front view, which takes the
    opt-in import; the side, iso and bore views show the part as saved."""
    for sketch in (spec.TOOTH_REFERENCE_SKETCH, spec.GAP_FLOOR_SKETCH):
        owned = spec.DRAWING_DIMENSIONS[sketch]
        for teeth in spec.CONFIGURATION_TEETH:
            assert owned <= set(drawing.front_keep(teeth))
            assert not owned & set(drawing.right_keep(teeth))
            assert not owned & set(drawing.bore_view_keep(teeth))


# Measured by the layout audit on the T006 sheet (layoutcal2, cone-gear.json):
# the vertical centre-mark line reaches y 0.1763, and the BlankDia value's text
# box hangs 0.0036 below its anchor (anchor 0.1791, box bottom 0.1755).
_T006_CENTRE_MARK_TOP = 0.1763
_BLANK_DIA_TEXT_DESCENT = 0.0036


def test_t006_blank_dia_value_clears_the_centre_mark_line() -> None:
    """layoutcheck T006: the value sat 0.82 mm down over the centre-mark line."""
    text_bottom = drawing.front_keep(6)["BlankDia"][1] - _BLANK_DIA_TEXT_DESCENT
    assert text_bottom >= _T006_CENTRE_MARK_TOP + 0.001


def test_invalid_family_member_is_rejected() -> None:
    with pytest.raises(ValueError):
        spec.bore_dia_mm(7)
    with pytest.raises(ValueError):
        spec.chord_floor_radius_mm(7, thickness_mm=spec.STANDARD_TOOTH_THICKNESS)
    with pytest.raises(ValueError):
        spec.floor_radius_mm(7)
    with pytest.raises(ValueError):
        spec.outside_dia_mm(7)
    with pytest.raises(ValueError):
        spec.tooth_thickness_mm(7)
    with pytest.raises(ValueError):
        notes.drawing_notes(7)
    with pytest.raises(ValueError):
        spec.material_specification(7)
    with pytest.raises(ValueError):
        notes.gear_data(7)


def test_root_to_bore_webs_meet_rule_12_except_the_named_t006() -> None:
    # Policy rule 12 at the worst case: the printed MIN floor diameter against
    # the maximum bore.  The D-flat only adds material on +X, so the round
    # side is the thinnest web.  U40 (user): T012/T018/T024 moved one shaft
    # land down to meet the target; T006 is the one named exception.
    upper = part.BORE_DIA_BAND[0]
    for teeth in spec.CONFIGURATION_TEETH:
        web = spec.floor_radius_mm(teeth) - (spec.bore_dia_mm(teeth) + upper) / 2.0
        if teeth in spec.WEB_EXCEPTIONS_MM:
            assert 0.0 < web < spec.MACHINED_WEB_FLOOR_MM, teeth
            assert web == pytest.approx(spec.WEB_EXCEPTIONS_MM[teeth], abs=0.0005)
            continue
        assert web >= spec.MACHINED_WEB_TARGET_MM, teeth
    # The flat is a chord of the round bore on the axis's +X side: it only
    # ever leaves material, so no web is thinner than the round side's.
    for teeth in spec.CONFIGURATION_TEETH:
        assert 0.0 < spec.bore_flat_offset_mm(teeth) < spec.bore_dia_mm(teeth) / 2.0
    # T012's MIN floor is its web limit: 2.05, one printed step deeper breaks it.
    t012_bore = (spec.bore_dia_mm(12) + upper) / 2.0
    assert spec.floor_radius_mm(12) - t012_bore >= 2.05
    assert (spec.DIPPED_FLOOR_MIN_MM[12] - 0.001) / 2.0 - t012_bore < 2.05
    assert set(spec.WEB_EXCEPTIONS_MM) == {6}
    # U40: the user ruled T006's exception at a 0.621 worst-case web; any
    # drift below it needs a new ruling, not a quiet edit.
    t006_web = spec.floor_radius_mm(6) - (spec.bore_dia_mm(6) + upper) / 2.0
    assert t006_web >= 0.621 - 1e-9
    assert spec.WEB_EXCEPTIONS_MM[6] == 0.621
    assert [spec.bore_dia_mm(t) for t in (6, 12, 18, 24, 30)] == pytest.approx(
        [1.5875, 1.5875, 3.175, 6.35, 9.525]
    )


def test_dimensions_record_gear_bores_row_follows_the_spec() -> None:
    # The narrative record is read by no part, so nothing rebuilds when the
    # bores move: it kept the pre-S1 map (9.5 on T024-T120) after U40.  It
    # must name every round seat, its gears and its across-flat.
    groups: dict[float, list[int]] = {}
    for teeth in spec.CONFIGURATION_TEETH:
        groups.setdefault(spec.bore_dia_mm(teeth), []).append(teeth)
    record = yaml.safe_load(
        (Path(part.__file__).resolve().parents[1] / "config" / "dimensions.yaml")
        .read_text(encoding="utf-8")
    )
    rows = []
    stack = [record]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            stack.extend(node.values())
        elif isinstance(node, list):
            if node and isinstance(node[0], str) and node[0].startswith("Gear bores"):
                rows.append(node)
            stack.extend(node)
    assert len(rows) == 1
    row = rows[0][1]
    printed_bores = sorted({float(value) for value in re.findall(r"Ø(\d+\.\d+)", row)})
    assert printed_bores == pytest.approx(sorted(groups))
    for bore, teeth in groups.items():
        span = f"T{teeth[0]:03d}" if len(teeth) == 1 else f"T{teeth[0]:03d}–T{teeth[-1]:03d}"
        assert span in row, span
        assert f"{spec.bore_flat_af_mm(teeth[0]):.3f}" in row, bore
