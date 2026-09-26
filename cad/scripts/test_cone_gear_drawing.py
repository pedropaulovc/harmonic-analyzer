"""Offline behavioral contracts for the cone-gear batch drawing package."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import _config
import build_cone_gear as part
import cone_gear_notes as notes
import cone_gear_shaft_spec
import cone_gear_spec as spec
import draw_cone_gear as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths_and_registry_entry() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/cone-gear.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/cone-gear.pdf")
    assert drawing.PNG.as_posix().endswith("/png/cone-gear_drawing.png")
    assert DRAWINGS_BY_NAME["cone_gear"].script == Path(drawing.__file__).resolve()


def test_every_configuration_has_one_complete_sheet_and_native_scale() -> None:
    expected_teeth = tuple(range(6, 121, 6))
    expected_names = tuple(f"T{teeth:03d}" for teeth in expected_teeth)
    assert spec.CONFIGURATION_TEETH == expected_teeth
    assert part.CONFIGS == tuple(zip(expected_names, expected_teeth, strict=True))
    assert drawing.SHEET_NAMES == expected_names
    assert set(drawing.SHEET_SCALES) == set(expected_names)

    for teeth in expected_teeth:
        name = f"T{teeth:03d}"
        numerator, denominator = drawing.SHEET_SCALES[name]
        drawn_od = drawing.outside_dia_mm(teeth) * numerator / denominator
        # The smallest six-tooth member is necessarily limited by the common
        # 6.5 mm face width; every other face lands in the useful 40-95 mm band.
        assert 30.0 < drawn_od < 95.0
        assert drawing.rendered_half_od(teeth) == pytest.approx(drawn_od / 2000.0)


def test_part_and_drawing_share_the_complete_native_dimension_contract() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert marked == {"BlankDia", "FaceWidth", "BoreCutDia", "ToothThickness"}
    for teeth in spec.CONFIGURATION_TEETH:
        kept = set(drawing.front_keep(teeth)) | set(drawing.right_keep(teeth))
        assert kept == marked


def test_model_owns_precision_for_both_fit_dimensions() -> None:
    assert spec.DRAWING_PRECISION_BY_NAME == {
        "BlankDia": 2,
        "FaceWidth": 2,
        "BoreCutDia": 3,
        "ToothThickness": 3,
    }
    assert "draw_cone_gear.py" in PRECISION_MIGRATED_DRAWINGS


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


def test_face_width_carries_the_cone_set_z_band() -> None:
    # User ruling (#914, 2026-09-25): the .X +/-0.8 face let a 5.2 gear eat
    # the cone set's whole axial allowance against the drum; +/-0.10 leaves
    # ~0.425 after the bank's 1.175.  Applied on the model like the others.
    assert spec.FACE_WIDTH_BAND == (0.10, -0.10)
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert '"Blank", "FaceWidth", *deviations(FACE_WIDTH_BAND)' in source
    # still inside the 6.889 seat pitch at the upper limit
    assert spec.FACE_WIDTH + spec.FACE_WIDTH_BAND[0] < 6.889 - 0.5


def test_each_configuration_sheet_carries_its_own_drawing_number() -> None:
    number = str(_config.parts("cone-gear")["number"])
    assert spec.configuration_number(number, 6) == f"{number}-T006"
    assert spec.configuration_number(number, 120) == f"{number}-T120"
    numbers = {spec.configuration_number(number, t) for t in spec.CONFIGURATION_TEETH}
    assert len(numbers) == len(spec.CONFIGURATION_TEETH)
    with pytest.raises(ValueError):
        spec.configuration_number(number, 7)
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert '"Number": configuration_number(part_number, teeth)' in source


def test_bore_band_is_the_explicit_soldered_seat_band() -> None:
    # Main (2026-09-23): MHA-013 bores print +0.05/0 on their shaft land's
    # nominal; the soldered seats go to 0/-0.05 (#839), so the pair spans
    # 0 to 0.10 diametral, the gap the solder or retaining compound fills.
    assert part.BORE_DIA_BAND is spec.BORE_DIA_BAND
    assert spec.BORE_DIA_BAND == (0.05, 0.0)
    land_upper, land_lower = cone_gear_shaft_spec.SECTION_DIA_BAND
    assert spec.BORE_DIA_BAND[1] - land_upper == pytest.approx(0.0)
    assert 0.0 < spec.BORE_DIA_BAND[0] - land_lower <= 0.10
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert '"BoreProfile", "BoreCutDia", *deviations(BORE_DIA_BAND)' in source

    # Every configured bore seats on a published cone-shaft land and retains
    # the approved enlarged 1/16-inch tip journal at T006.
    assert spec.bore_dia_mm(6) == pytest.approx(1.5875)
    assert spec.FAMILY_BORES_MM[6] == pytest.approx(
        cone_gear_shaft_spec.SECTION_DIAS[-1]
    )
    for bore in spec.FAMILY_BORES_MM.values():
        assert any(
            bore == pytest.approx(section)
            for section in cone_gear_shaft_spec.SECTION_DIAS
        )


def test_native_tooth_thickness_is_the_modelled_deepened_mesh_tooth() -> None:
    # The band is the configured backlash WINDOW, centred on the modelled
    # tooth: error_budget.yaml mesh_lag_spread is derived from that window.
    minimum, maximum = _config.fit("gear_mesh", "backlash_mm")
    upper, lower = spec.TOOTH_THICKNESS_BAND
    assert upper == pytest.approx(-lower)
    assert upper - lower == pytest.approx(maximum - minimum)
    for teeth in spec.CONFIGURATION_TEETH:
        thickest = spec.DEEPENED_MESH_MM[teeth][1]
        assert spec.tooth_thickness_mm(teeth) + upper == pytest.approx(thickest)
        # Thicker than standard at both limits: the deepened mesh.
        assert spec.tooth_thickness_mm(teeth) + lower > spec.STANDARD_TOOTH_THICKNESS
        facts = part.cone_facts(teeth)
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
        # U40: the floor is a MIN limit; the tooth form and the floor limits
        # state the result, so no row says how to cut it (rule 6).
        minimum, maximum = spec.floor_limits_mm(teeth)
        assert (
            f"GAP FLOOR DIAMETER (mm):  {minimum:.3f} MIN / {maximum:.3f} MAX"
        ) in data
        for method in ("CUTTING", "CUTTER", "PLUNGE", "INDEXING", "SINKING"):
            assert method not in data
        assert spec.TOOTH_FORM in data
        assert "FULL DEPTH" not in data
        assert "WHOLE DEPTH" not in data
        assert notes.CYLINDER_MATE_NUMBER in data
        assert (
            f"BACKLASH WITH MHA-027, ACCEPT AT ASSEMBLY (mm):  "
            f"{spec.BACKLASH_ACCEPTANCE_MM[0]:.2f} TO "
            f"{spec.BACKLASH_ACCEPTANCE_MM[1]:.2f}"
        ) in data
        # The operating mesh is not a reference-centre-distance mesh; say so
        # beside the mate, and say where the view's thickness is measured.
        assert "TOOTH THICKNESS IN VIEW:  ARC LENGTH AT PITCH DIAMETER" in data
        # 49.1 mm measured for 14 lines natively (e91d2581 layout audit).
        assert len(data.splitlines()) * 0.00351 <= drawing.GEAR_DATA_HEIGHT
        # 144.2 mm for 78 characters natively: the block must end before the
        # sheet count at x 0.3496.
        widest = max(len(line) for line in data.splitlines())
        assert widest <= drawing.GEAR_DATA_MAX_LINE_CHARS
        assert (
            drawing.GEAR_DATA_POS[0] + widest * 0.00185 < drawing.SHEET_COUNT_POS[0] - 0.003
        )
        assert "OPERATING MESH:  LONG ADDENDUM, PARTIAL DEPTH ON INCLINED AXES" in data
        assert "48 DP" not in data
        # These values are native imported dimensions, never parallel typed rows.
        for duplicate in (
            "OUTSIDE DIAMETER",
            "FACE WIDTH",
            "BORE",
            "CIRCULAR TOOTH THICKNESS",
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
    registry = _config.parts("cone-gear")
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


def test_notes_state_only_the_plain_bore_with_no_method_or_review_record() -> None:
    # Rule 6: the joint is a method (it moves to the drive-train assembly
    # step, which imports ATTACHMENT), and the U42/U40 book-fidelity
    # exceptions are a design-review record the machinist cannot act on (they
    # stay in cone_gear_spec's exception lists).  Every sheet prints the same
    # three lines.
    expected = [
        "DO NOT BREAK OR CHAMFER EDGES ON TOOTH FLANKS, TIPS OR ROOTS.",
        "MAKE ONE GEAR FROM EACH SHEET IN THIS PACKAGE.",
        "PLAIN BORE, NO KEYWAY.",
    ]
    assert notes.DRAWING_NOTES.splitlines() == expected
    for teeth in spec.CONFIGURATION_TEETH:
        text = notes.drawing_notes(teeth)
        assert text.splitlines() == expected
        for review_or_method in (
            notes.ATTACHMENT,
            "SOLDER",
            "LOCTITE",
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
    assert notes.ATTACHMENT == "SOLDER, SILVER-BRAZE OR LOCTITE 638/648"
    assert notes.CYLINDER_MATE_NUMBER == _config.parts("cylinder-gear")["number"]
    assert notes.SHAFT_MATE_NUMBER == _config.parts("cone-gear-shaft")["number"]
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
    web_row = "WALL, GAP FLOOR TO HOLE (mm, REF):  "
    if teeth in spec.WEB_EXCEPTIONS_MM:
        web = notes.root_to_bore_web_min_mm(teeth)
        # the printed limits give exactly the web the user accepted
        assert web == pytest.approx(spec.WEB_EXCEPTIONS_MM[teeth], abs=0.0005)
        # stated rounded DOWN: never more wall than the limits give
        stated = float(data.split(web_row)[1].split()[0])
        assert 0.0 <= web - stated < 0.01
        assert f"{web_row}{stated:.2f} MIN" in data
    else:
        assert web_row not in data
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
        for x, y in (*front.values(), *right.values()):
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
        assert drawing.face_width_text_inside(teeth) == (teeth <= 24)
        # Thickness text (~65 mm callout centred on its x) sits below the gear,
        # left of the side view and its face-width dimension.
        ctt_x, ctt_y = front["ToothThickness"]
        assert ctt_y < drawing.FRONT_CENTER[1] - half_od - 0.015
        assert ctt_x + 0.0325 < drawing.RIGHT_CENTER[0] - half_face - 0.020
        assert ctt_x - 0.0325 > front["BoreCutDia"][0] + 0.0165 + 0.010
        # The bore finish sits above-left of the gear, inside the border and
        # below the manufacturing notes.
        (edge_x, edge_y), (symbol_x, symbol_y) = drawing.bore_finish_xy(teeth)
        assert edge_x < drawing.FRONT_CENTER[0] and edge_y > drawing.FRONT_CENTER[1]
        assert 0.015 < symbol_x < drawing.FRONT_CENTER[0] - half_od * 0.7
        assert drawing.FRONT_CENTER[1] + half_od * 0.7 < symbol_y < 0.225
        assert front["BoreCutDia"][0] < drawing.FRONT_CENTER[0] - half_od
        assert front["BoreCutDia"][0] == pytest.approx(
            drawing.BORE_CALLOUT_LANE_X
        )
        assert (
            drawing.FRONT_CENTER[0]
            - half_od
            - drawing.BORE_CALLOUT_LANE_X
            >= 0.008
        )
        assert front["ToothThickness"][0] > drawing.FRONT_CENTER[0] + half_od


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


def test_root_to_bore_webs_meet_u27_except_the_named_t006() -> None:
    # Policy rule 12 at the worst case: the printed MIN floor diameter against
    # the maximum bore.  U40 (user): T012/T018/T024 moved one shaft land down
    # to meet the target; T006 is the one named exception.
    upper = part.BORE_DIA_BAND[0]
    for teeth in spec.CONFIGURATION_TEETH:
        web = spec.floor_radius_mm(teeth) - (spec.bore_dia_mm(teeth) + upper) / 2.0
        if teeth in spec.WEB_EXCEPTIONS_MM:
            assert 0.0 < web < spec.MACHINED_WEB_FLOOR_MM, teeth
            assert web == pytest.approx(spec.WEB_EXCEPTIONS_MM[teeth], abs=0.0005)
            continue
        assert web >= spec.MACHINED_WEB_TARGET_MM, teeth
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
