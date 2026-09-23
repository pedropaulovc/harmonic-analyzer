"""Offline behavioral contracts for the cone-gear batch drawing package."""

from __future__ import annotations

import math
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
        "FaceWidth": 1,
        "BoreCutDia": 3,
        "ToothThickness": 3,
    }
    assert "draw_cone_gear.py" in PRECISION_MIGRATED_DRAWINGS


def test_bore_band_is_derived_live_from_shaft_limits_and_fit_class() -> None:
    minimum, maximum = _config.fit("shaft_in_bushing")["diametral_clearance_mm"]
    land_upper, land_lower = cone_gear_shaft_spec.SECTION_DIA_BAND
    assert part.BORE_DIA_BAND == (
        pytest.approx(land_lower + maximum),
        pytest.approx(land_upper + minimum),
    )
    bore_upper, bore_lower = part.BORE_DIA_BAND
    assert bore_lower - land_upper == pytest.approx(minimum)
    assert bore_upper - land_lower == pytest.approx(maximum)

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


def test_native_tooth_thickness_band_is_the_configured_mesh_backlash() -> None:
    minimum, maximum = _config.fit("gear_mesh", "backlash_mm")
    assert part.BACKLASH_MM == pytest.approx((minimum, maximum))
    assert spec.TOOTH_THICKNESS == pytest.approx(math.pi * spec.MODULE_MM / 2.0)
    assert part.TOOTH_THICKNESS_BAND == (
        pytest.approx(-minimum),
        pytest.approx(-maximum),
    )
    upper, lower = part.TOOTH_THICKNESS_BAND
    assert spec.TOOTH_THICKNESS - (spec.TOOTH_THICKNESS + upper) == pytest.approx(
        minimum
    )
    assert spec.TOOTH_THICKNESS - (spec.TOOTH_THICKNESS + lower) == pytest.approx(
        maximum
    )


def test_each_sheet_gets_its_own_tooth_system_block_without_dimension_duplicates() -> None:
    for teeth in spec.CONFIGURATION_TEETH:
        data = notes.gear_data(teeth, part.BACKLASH_MM)
        assert data.startswith("GEAR DATA\n")
        assert f"CONFIGURATION:  T{teeth:03d}" in data
        assert f"NUMBER OF TEETH:  {teeth}" in data
        assert f"PITCH DIAMETER (mm, REF):  {teeth * spec.MODULE_MM:.2f}" in data
        assert "DIAMETRAL PITCH" in data
        assert "PRESSURE ANGLE" in data
        assert "INVOLUTE FLANKS" in data
        assert f"CYLINDER GEAR {notes.CYLINDER_MATE_NUMBER}" in data
        assert (
            f"MIN CHORD-FLOOR DIAMETER (mm, REF):  "
            f"{2.0 * spec.base_chord_root_radius_mm(teeth):.3f}"
        ) in data
        assert (
            f"AS-CUT RADIAL TOOTH DEPTH (mm, REF):  "
            f"{spec.as_cut_tooth_depth_mm(teeth):.3f}"
        ) in data
        assert spec.BASE_CHORD_ROOT_FORM in data
        assert "FULL DEPTH" not in data
        assert "WHOLE DEPTH" not in data
        assert notes.CYLINDER_MATE_NUMBER in data
        assert f"{part.BACKLASH_MM[0]:.2f} TO {part.BACKLASH_MM[1]:.2f}" in data
        # The operating mesh is not a reference-centre-distance mesh; say so
        # beside the mate, and say where the view's thickness is measured.
        assert "TOOTH THICKNESS IN VIEW:  ARC LENGTH AT PITCH DIAMETER" in data
        assert len(data.splitlines()) * 0.00327 <= drawing.GEAR_DATA_HEIGHT
        # 144.2 mm for 78 characters natively: the block must end before the
        # sheet count at x 0.3496.
        widest = max(len(line) for line in data.splitlines())
        assert widest <= drawing.GEAR_DATA_MAX_LINE_CHARS
        assert (
            drawing.GEAR_DATA_POS[0] + widest * 0.00185 < drawing.SHEET_COUNT_POS[0] - 0.003
        )
        assert "OPERATING MESH:  PARTIAL DEPTH ON INCLINED AXES (SEE ASSEMBLY)" in data
        # These values are native imported dimensions, never parallel typed rows.
        for duplicate in (
            "OUTSIDE DIAMETER",
            "FACE WIDTH",
            "BORE",
            "CIRCULAR TOOTH THICKNESS",
            "FAMILY T",
        ):
            assert duplicate not in data


def test_t006_root_contract_uses_the_current_base_chord_recipe() -> None:
    root = spec.base_chord_root_radius_mm(6)
    assert root == pytest.approx(1.4324343141)
    assert spec.as_cut_tooth_depth_mm(6) == pytest.approx(0.6069073155)
    maximum_bore = spec.bore_dia_mm(6) + part.BORE_DIA_BAND[0]
    assert root - maximum_bore / 2.0 == pytest.approx(0.6111843141)


def test_configuration_owned_bores_and_title_block_alloys_cover_the_family() -> None:
    registry = _config.parts("cone-gear")
    assert spec.BODY_MATERIAL_SPEC == registry["material_specification"]
    assert spec.TIP_MATERIAL_SPEC == registry["material_tip_specification"]
    assert spec.TIP_MATERIAL_SPEC != spec.BODY_MATERIAL_SPEC
    assert registry["finish"] == "NONE"
    for teeth in spec.CONFIGURATION_TEETH:
        assert part.bore_dia_in(teeth) * spec.MM_PER_IN == pytest.approx(
            spec.bore_dia_mm(teeth)
        )
        expected = spec.TIP_MATERIAL_SPEC if teeth <= 24 else spec.BODY_MATERIAL_SPEC
        assert spec.material_specification(teeth) == expected


def test_notes_define_only_the_approved_plain_bore_attachment() -> None:
    text = notes.DRAWING_NOTES
    lines = text.splitlines()
    assert len(lines) == 4
    assert all(len(line) <= 90 for line in lines)
    assert "PLAIN BORE, NO KEYWAY" in text
    assert "BOND TO MHA-014 SHAFT SEAT AT ASSEMBLY" in text
    assert notes.ATTACHMENT_PROCESS == "SOLDER OR SILVER-BRAZE"
    assert notes.ATTACHMENT_PROCESS in text
    assert notes.ATTACHMENT_ALTERNATIVE == "LOCTITE 638 OR LOCTITE 648"
    assert notes.ATTACHMENT_ALTERNATIVE in text
    assert "ACCEPTABLE BONDS:" in text
    assert notes.CYLINDER_MATE_NUMBER == _config.parts("cylinder-gear")["number"]
    assert notes.SHAFT_MATE_NUMBER == _config.parts("cone-gear-shaft")["number"]
    for unsupported in ("PIN", "SET SCREW", "HUB"):
        assert unsupported not in text
    for retired in ("RUNOUT", "DATUM", "+/-", "PITCH DIA="):
        assert retired not in text


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


def test_invalid_family_member_is_rejected() -> None:
    with pytest.raises(ValueError):
        spec.bore_dia_mm(7)
    with pytest.raises(ValueError):
        spec.base_chord_root_radius_mm(7)
    with pytest.raises(ValueError):
        spec.as_cut_tooth_depth_mm(7)
    with pytest.raises(ValueError):
        spec.material_specification(7)
    with pytest.raises(ValueError):
        notes.gear_data(7, part.BACKLASH_MM)


def test_root_to_bore_webs_meet_u27_except_the_user_ruled_small_gears() -> None:
    # U27 floor/target at the maximum bore; T006..T024 are a named USER
    # exception (book-fidelity, ch12-p002-img09), not a loosened threshold.
    upper = part.BORE_DIA_BAND[0]
    for teeth in spec.CONFIGURATION_TEETH:
        web = spec.base_chord_root_radius_mm(teeth) - (
            spec.bore_dia_mm(teeth) + upper
        ) / 2.0
        if teeth in spec.SMALL_GEAR_WEB_EXCEPTIONS_MM:
            assert 0.0 < web < spec.MACHINED_WEB_FLOOR_MM, teeth
            assert web == pytest.approx(
                spec.SMALL_GEAR_WEB_EXCEPTIONS_MM[teeth], abs=0.001
            ), teeth
            continue
        assert web >= spec.MACHINED_WEB_TARGET_MM, teeth
    assert set(spec.SMALL_GEAR_WEB_EXCEPTIONS_MM) == {6, 12, 18, 24}
