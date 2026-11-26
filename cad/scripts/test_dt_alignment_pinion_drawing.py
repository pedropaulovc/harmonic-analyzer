"""Offline contracts for retained alignment-pinion manufacturing data."""

from __future__ import annotations

import math
import re
import runpy

import pytest

import _config
import dt_alignment_pinion_spec as spec
import dt_pinion_arbor_geometry as arbor_geometry
import dt_pinion_arbor_spec as arbor
from _gear_fit_limits import gear_tip_band_mm


def test_gear_data_block_preserves_the_actual_finite_stock_profile() -> None:
    data = spec.GEAR_DATA
    assert spec.TEETH == int(_config.machine("alignment_pinion", "teeth"))
    assert spec.DIAMETRAL_PITCH == _config.machine("gear_train", "diametral_pitch")
    assert spec.PRESSURE_ANGLE_DEG == _config.machine(
        "gear_train", "pressure_angle_deg"
    )
    assert spec.MODULE_MM == pytest.approx(spec.MM_PER_IN / spec.DIAMETRAL_PITCH)
    assert spec.CUTTER_REFERENCE_TEETH == spec.CUTTER_TEETH_RANGE[0]
    assert spec.STOCK_FORM.template == spec.CUTTER_TEMPLATE
    assert spec.STOCK_FORM.teeth == spec.TEETH
    assert spec.CUTTER_RADIAL_TRANSLATION_MM == pytest.approx(
        spec.PITCH_DIA / 2.0 - spec.CUTTER_TEMPLATE.pitch_radius_mm
    )
    assert spec.ROOT_ENVELOPE_DIA_MM == pytest.approx(
        (2.0 * spec.STOCK_FORM.root_radius_min_mm, 2.0 * spec.STOCK_FORM.root_radius_max_mm)
    )
    assert spec.ROOT_ENVELOPE_DIA_MM[0] < spec.ROOT_ENVELOPE_DIA_MM[1]
    assert spec.WHOLE_DEPTH == pytest.approx(spec.STOCK_FORM.plunge_mm)
    assert spec.MAX_CUT_DEPTH_MM > spec.WHOLE_DEPTH
    assert spec.OUTSIDE_DIA <= spec.MIN_SPAN_SUPPORT_OUTSIDE_DIA_MM
    # Floored to the .001-in grid the tip prints at.
    assert spec.OUTSIDE_DIA + 0.0254 > spec.MIN_SPAN_SUPPORT_OUTSIDE_DIA_MM
    assert spec.CUTTER_NUMBER == 4
    assert spec.CUTTER_TEETH_RANGE == (26, 34)
    assert spec.CUTTER_TEETH_RANGE[0] <= spec.TEETH <= spec.CUTTER_TEETH_RANGE[1]
    assert "CHORD" not in data
    assert "X.XX" not in data


def test_no_face_carries_a_finish_symbol() -> None:
    """Machinist review of the pc-r7 sheet: Ra 1.6 on both end faces was
    over-specified.  The ends bear on the MHA-DT-14 straps at the float's two
    stops, but no friction or end-play budget asks for a grade, so they take
    the title-block finish.  The bore is a bonded seat on MHA-DT-22, so its
    Ra 63 went too (rule 6; machinist review r1, farm run
    20261124T110807008Z).  "End faces polished" stays retired too."""
    import draw_dt_alignment_pinion as drawing

    assert spec.SURFACE_FINISHES == ()
    assert "polish" not in _config.parts("dt-alignment-pinion")["finish"].lower()
    for retired in ("_end_face_tip_arc", "BACK_END_FACE_XY", "FRONT_END_FACE_XY"):
        assert not hasattr(drawing, retired), retired


def test_bonded_slip_fit_clears_the_mha102_journal_within_the_bond_gap() -> None:
    # Owner ruling 2026-11-24, fit audit question 13: the bore is drilled
    # 5/16 (the DRILLED HOLES row is its analysis band) and MHA-DT-22's bond
    # lands are turned to it (made to fit: drawing-guidelines rule 4, form 2).
    bore_limits = (
        spec.BORE_DIA + spec.ARBOR_BORE_BAND[1],
        spec.BORE_DIA + spec.ARBOR_BORE_BAND[0],
    )
    assert spec.ARBOR_BORE_BAND == pytest.approx((0.1016, 0.0))
    assert bore_limits == pytest.approx((7.9375, 8.0391))
    # The arbor's geometry models the same drilled band (no import cycle).
    assert arbor_geometry.DRUM_BORE_BAND == spec.ARBOR_BORE_BAND
    land_limits = (
        arbor_geometry.SHAFT_DIA + arbor_geometry.BOND_LAND_DIA_BAND[1],
        arbor_geometry.SHAFT_DIA + arbor_geometry.BOND_LAND_DIA_BAND[0],
    )
    # The drum bonds onto MHA-DT-22's bond lands, not its journal lands (U39).
    assert arbor_geometry.BOND_LAND_DIA_BAND != arbor.JOURNAL_DIA_BAND
    # The loosest pair, the drill's top over the smallest land, is the fit's
    # own .008 and inside LOCTITE 638's gap.
    maximum_clearance = bore_limits[1] - land_limits[0]
    assert maximum_clearance == pytest.approx(arbor_geometry.BOND_FIT_CLEARANCE[1])
    assert maximum_clearance < spec.RETAINING_COMPOUND_MAX_GAP_MM
    # The drum slides on by hand: the lands are turned .002 under its bore.
    assert arbor_geometry.BOND_FIT_CLEARANCE[0] == pytest.approx(0.0508)
    assert spec.BORE_DIA == arbor_geometry.SHAFT_DIA  # the CAD models line-to-line


def test_the_drum_bond_is_the_fitup_step_not_a_note() -> None:
    import dt_pinion_arbor_spec as arbor_spec

    notes = spec.DRAWING_NOTES
    # drawing-guidelines.md rule 7 (notes: few, flagged, never a method) (R3): one note.  The drum is symmetric, so no orientation note;
    # its axial station is stated once, on MHA-DT-22.  The MHA-DT-22 bond-zone
    # band is MHA-DT-22's own native dimension (Codex P1 on #814), the hand
    # slide rides the bore callout (Codex P2 on #832), and the bond itself is
    # the pinion fit-up step MHA-DT-22's spec owns (Main's drawing-guidelines.md rule 7 (notes: few, flagged, never a method) sweep).
    assert "BOND ZONE" not in notes
    assert "ARBOR JOURNAL" not in notes
    assert "LOCTITE" not in notes and "ON ASSEMBLY" not in notes
    assert "MHA-DT-01" in arbor_spec.ASSEMBLY_STEP
    assert spec.RETAINING_COMPOUND in arbor_spec.ASSEMBLY_STEP
    assert "j=19" not in notes and "LOCATED FROM" not in notes
    assert "MATES WITH CYLINDER-GEAR BANK" not in notes
    for retired in ("INTERFERENCE", "MATCHED FIT", "ENSURES FULL ENGAGEMENT", "+/-0.5"):
        assert retired not in notes, retired


def test_part_metadata_preserves_material_finish_quantity() -> None:
    config = _config.parts("dt-alignment-pinion")
    assert config["material_specification"] == "C36000 free-machining brass"
    assert config["finish"] == "bore as drilled; teeth as cut"
    assert int(config["quantity"]) == 1


def test_tooth_thickness_is_controlled_by_the_model_base_tangent_span() -> None:
    k = spec.BASE_TANGENT_SPAN_TEETH
    # Parallel tangent contacts on the actual translated reference flanks,
    # not the unrolled N32 involute the old inspection formula assumed.
    beta = math.pi * k / spec.TEETH
    parameter = beta - spec.CUTTER_TEMPLATE.half_space_base_angle_rad
    assert spec.CUTTER_TEMPLATE.flank_parameter_min < parameter
    assert parameter < spec.CUTTER_TEMPLATE.flank_parameter_max
    span = (
        2.0 * spec.CUTTER_TEMPLATE.base_radius_mm * parameter
        + 2.0 * spec.CUTTER_RADIAL_TRANSLATION_MM * math.sin(beta)
    )
    assert spec.BASE_TANGENT_SPAN == pytest.approx(span, abs=1e-9)
    assert spec.BASE_TANGENT_SPAN == pytest.approx(spec.STOCK_FORM.tangent_span_mm(k))
    assert spec.BASE_TANGENT_SPAN_BAND == (0.0, -0.1016)


def test_printed_thickness_corners_keep_finite_actual_cutter_support() -> None:
    span_limits = spec.base_tangent_span_limits_mm()
    # The printed span sits on the .0001-in grid, never under the model.
    nominal = spec.BASE_TANGENT_SPAN_PRINTED_MM
    assert nominal / 25.4 * 1e4 == pytest.approx(round(nominal / 25.4 * 1e4), abs=1e-6)
    assert 0.0 <= nominal - spec.BASE_TANGENT_SPAN < 0.00254
    assert span_limits[0] <= spec.BASE_TANGENT_SPAN <= span_limits[1]
    upper, lower = spec.BASE_TANGENT_SPAN_BAND
    assert span_limits == pytest.approx((nominal + lower, nominal + upper))
    profiles = spec.manufacturing_corner_profiles()
    assert len(profiles) == 4
    for profile, (tip, span) in zip(
        profiles,
        (
            (tip, span)
            for tip in spec.outside_dia_limits_mm()
            for span in span_limits
        ),
        strict=True,
    ):
        assert profile.template == spec.CUTTER_TEMPLATE
        assert profile.teeth == spec.TEETH
        assert profile.blank_radius_mm == pytest.approx(tip / 2.0)
        assert profile.blank_radius_mm <= profile.support_radius_max_mm
        assert profile.tangent_span_mm(spec.BASE_TANGENT_SPAN_TEETH) == pytest.approx(span)
        assert 0.0 < profile.teeth * profile.gap_area_mm2 < math.pi * (tip / 2.0) ** 2
    assert min(profile.radial_translation_mm for profile in profiles) == pytest.approx(
        spec.MIN_SPAN_CUTTER_RADIAL_TRANSLATION_MM
    )


def test_fit_bore_callout_names_its_process() -> None:
    import draw_dt_alignment_pinion as draw

    assert draw.DIMENSION_CALLOUTS["ArborBoreDia"].splitlines() == [
        "5/16 DRILL THRU",
        "MHA-DT-22 PINION ARBOR IS TURNED",
        "TO THIS BORE, BONDED FIT",
    ]


def test_tip_band_does_not_repeat_the_gear_data_mate() -> None:
    """Rule 4: a mate serving several features is named once; the gear data
    block's MATES WITH row names the cylinder gears (machinist review r1,
    farm run 20261124T110807008Z)."""
    import draw_dt_alignment_pinion as draw

    assert "OutsideDia" not in draw.DIMENSION_CALLOUTS
    assert "MATES WITH:  EACH OF 20 CYLINDER GEARS MHA-DT-12" in spec.GEAR_DATA


def test_diagnostic_home_clocking_uses_engaged_pose_and_native_row_handedness() -> None:
    import dt_cylinder_gear_spec as gear

    swing, heading = 0.08, math.pi - 0.02
    driver_clock, driven_clock = spec.engaged_home_clocking_rad(swing, heading)
    lock = math.radians(float(_config.machine("gear_train", "cylinder_lock_phase_deg")))
    assert (driver_clock, driven_clock) == pytest.approx(
        (swing + math.pi / spec.TEETH - heading, -lock - heading)
    )
    native_gap = math.pi / gear.TEETH
    # Independently apply the native ROW-vector Ry180 then Rz(-lock).
    x, y = -math.cos(native_gap), math.sin(native_gap)
    machine_x = x * math.cos(lock) + y * math.sin(lock)
    machine_y = -x * math.sin(lock) + y * math.cos(lock)
    canonical_x = machine_x * math.cos(heading) + machine_y * math.sin(heading)
    canonical_y = -machine_x * math.sin(heading) + machine_y * math.cos(heading)
    engine_angle = math.pi - math.pi / gear.TEETH + driven_clock
    assert (math.cos(engine_angle), math.sin(engine_angle)) == pytest.approx(
        (canonical_x, canonical_y), abs=1e-12
    )
    assert spec.ENGAGED_HOME_LOADED_EDGE == "lower"
    with pytest.raises(ValueError, match="must be finite"):
        spec.engaged_home_clocking_rad(float("nan"), heading)


def test_hand_slide_fit_rides_the_bore_callout_not_a_note() -> None:
    """drawing-guidelines.md rule 7 (notes: few, flagged, never a method): a matched-fit acceptance belongs on the feature callout or an
    assembly step, never in a general note (Codex P2 on #832)."""
    import draw_dt_alignment_pinion as draw

    callout = draw.DIMENSION_CALLOUTS["ArborBoreDia"]
    assert callout == spec.ARBOR_BORE_CALLOUT
    arbor = _config.parts("dt-pinion-arbor")
    assert arbor["number"] in callout
    assert arbor["number"] == "MHA-DT-22"
    for line in spec.DRAWING_NOTES.splitlines():
        assert "SLIDE" not in line and "BY HAND" not in line, line


def test_shared_tip_band_keeps_nominal_stock_root_air() -> None:
    """Retain the >0.20 air guard with both ACTUAL printed tip/root envelopes."""
    import dt_cylinder_gear_spec as gear

    assert spec.OUTSIDE_DIA_BAND == gear.OUTSIDE_DIA_BAND
    assert spec.OUTSIDE_DIA_BAND == gear_tip_band_mm("standard")
    pinion_lower, pinion_upper = spec.outside_dia_limits_mm()
    gear_lower, gear_upper = gear.outside_dia_limits_mm()
    engaged_c2c = spec.ENGAGED_CENTER_DISTANCE_MM
    expected_c2c = (spec.PITCH_DIA + gear.PITCH_DIA) / 2.0 + float(
        _config.machine("alignment_pinion", "engaged_center_extension_mm")
    )
    assert engaged_c2c == pytest.approx(expected_c2c, abs=1e-9)
    assert engaged_c2c == pytest.approx(
        _config.machine("alignment_pinion", "engaged_center_distance_mm"), abs=1e-6
    )
    assert engaged_c2c - pinion_upper / 2.0 - gear.ROOT_ENVELOPE_DIA_MM[1] / 2.0 > 0.20
    assert engaged_c2c - gear_upper / 2.0 - spec.ROOT_ENVELOPE_DIA_MM[1] / 2.0 > 0.20
    assert pinion_lower < pinion_upper <= spec.SUPPORT_OUTSIDE_DIA_MM
    assert gear_lower < gear_upper <= gear.SUPPORT_OUTSIDE_DIA_MM
    for pinion in spec.manufacturing_corner_profiles():
        for drum in gear.manufacturing_corner_profiles():
            assert engaged_c2c - pinion.blank_radius_mm - drum.root_radius_max_mm > 0.20
            assert engaged_c2c - drum.blank_radius_mm - pinion.root_radius_max_mm > 0.20


def test_tip_limits_follow_printed_nominal_not_unrounded_od() -> None:
    # The tip nominal sits on the .001-in grid it prints at.
    nominal = spec.OUTSIDE_DIA
    assert nominal / 25.4 * 1e3 == pytest.approx(round(nominal / 25.4 * 1e3), abs=1e-6)
    upper, lower = spec.OUTSIDE_DIA_BAND
    assert spec.outside_dia_limits_mm() == pytest.approx(
        (nominal + lower, nominal + upper), abs=1e-12
    )
    # The finite supported blank is explicitly quantized before modelling;
    # the standard mathematical actual-N tip is NOT the accepted upper tip.
    assert spec.outside_dia_limits_mm()[1] <= spec.SUPPORT_OUTSIDE_DIA_MM
    assert spec.OUTSIDE_DIA < (spec.TEETH + 2) * spec.MODULE_MM


def test_tip_grade_is_spec_owned_native_pmi_not_a_toleranced_note() -> None:
    import draw_dt_alignment_pinion as drawing

    assert spec.DRAWING_DIMENSIONS[spec.OUTSIDE_DIA_REFERENCE] == {"OutsideDia"}
    assert drawing.FRONT_KEEP.keys() | drawing.RIGHT_KEEP.keys() == set(
        spec.DRAWING_PRECISION_BY_NAME
    )
    import build_dt_alignment_pinion as part
    from _drawing_contract import model_toleranced_dimensions

    assert model_toleranced_dimensions(part)[("OutsideDiaReference", "OutsideDia")] == (
        "*deviations(OUTSIDE_DIA_BAND)"
    )
    assert "OUTSIDE DIAMETER" not in spec.GEAR_DATA


def test_tip_grade_configuration_reaches_the_part_spec(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_fit = _config.fit
    changed_band = [0.0, -0.01]

    def fit_value(*keys: str):
        if keys == ("gear_tip", "standard_band_mm"):
            return changed_band
        return original_fit(*keys)

    monkeypatch.setattr(_config, "fit", fit_value)
    dimensions = runpy.run_path(spec.__file__)
    assert dimensions["OUTSIDE_DIA_BAND"] == tuple(changed_band)
    nominal = dimensions["OUTSIDE_DIA"]
    assert dimensions["outside_dia_limits_mm"]() == pytest.approx(
        (nominal - 0.01, nominal), abs=1e-12
    )


def test_no_note_line_carries_a_dimension() -> None:
    """drawing-guidelines.md rule 7 (notes: few, flagged, never a method): once part numbers and the named retaining compound are set
    aside, no note line carries a digit (Codex P1 on #814)."""
    for line in spec.DRAWING_NOTES.splitlines():
        text = re.sub(r"MHA-(?!VN-)[A-Z]{2}-(?:[0-9]{2}(?:-TL-(?:[0-9]{2}|VN-[5-9][0-9]))?|VN-[5-9][0-9])(?:-T[0-9]{3})?(?![A-Z0-9-])", "", line).replace(spec.RETAINING_COMPOUND, "")
        assert not re.search(r"\d", text), line
