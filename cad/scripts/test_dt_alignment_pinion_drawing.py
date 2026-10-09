"""Offline contracts for retained alignment-pinion manufacturing data."""

from __future__ import annotations

import ast
import math
import re
import runpy
from pathlib import Path

import pytest

import _config
import dt_alignment_pinion_spec as spec
import dt_pinion_arbor_geometry as arbor_geometry
import dt_pinion_arbor_spec as arbor
from _fit_limits import gear_tip_band_mm


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
    assert spec.OUTSIDE_DIA + 0.01 > spec.MIN_SPAN_SUPPORT_OUTSIDE_DIA_MM
    assert spec.CUTTER_NUMBER == 4
    assert spec.CUTTER_TEETH_RANGE == (26, 34)
    assert spec.CUTTER_TEETH_RANGE[0] <= spec.TEETH <= spec.CUTTER_TEETH_RANGE[1]
    for field in (
        f"NUMBER OF TEETH:  {spec.TEETH}",
        f"DIAMETRAL PITCH:  {spec.DIAMETRAL_PITCH:.2f}",
        f"MODULE (mm, REF):  {spec.MODULE_MM:.3f}",
        f"PRESSURE ANGLE:  {spec.PRESSURE_ANGLE_DEG:.1f} DEG",
        f"PITCH DIAMETER (mm, REF):  {spec.PITCH_DIA:.2f}",
        f"ROOT ENVELOPE DIAMETER (mm, REF):  "
        f"{spec.ROOT_ENVELOPE_DIA_MM[0]:.3f}-{spec.ROOT_ENVELOPE_DIA_MM[1]:.3f}",
        f"CUTTER PLUNGE (mm, REF):  {spec.WHOLE_DEPTH:.3f}",
        f"FORM CUTTER (REF):  #{spec.CUTTER_NUMBER}, "
        f"{spec.CUTTER_TEETH_RANGE[0]}-{spec.CUTTER_TEETH_RANGE[1]}T; "
        f"{spec.CUTTER_REFERENCE_TEETH}T REFERENCE",
        f"TOOTH FORM:  {spec.TOOTH_FORM}",
    ):
        assert field in data, field
    assert "CHORD" not in data
    assert "X.XX" not in data


def test_only_the_bore_carries_a_finish_symbol() -> None:
    """Machinist review of the pc-r7 sheet: Ra 1.6 on both end faces was
    over-specified.  The ends bear on the MHA-DT-014 straps at the float's two
    stops, but no friction or end-play budget asks for a grade, so they take
    the title-block finish.  "End faces polished" stays retired too."""
    import draw_dt_alignment_pinion as drawing

    (bore,) = spec.SURFACE_FINISHES
    assert bore.key == "drum_bore"
    assert bore.face.diameter_mm == spec.BORE_DIA
    assert bore.roughness_um == 1.6
    assert "polish" not in _config.parts("dt-alignment-pinion")["finish"].lower()
    for retired in ("_end_face_tip_arc", "BACK_END_FACE_XY", "FRONT_END_FACE_XY"):
        assert not hasattr(drawing, retired), retired


def test_bonded_slip_fit_clears_the_mha102_journal_within_the_bond_gap() -> None:
    shaft_limits = (
        arbor_geometry.SHAFT_DIA + arbor.SHAFT_DIA_BAND[1],
        arbor_geometry.SHAFT_DIA + arbor.SHAFT_DIA_BAND[0],
    )
    bore_limits = (
        spec.BORE_DIA + spec.ARBOR_BORE_BAND[1],
        spec.BORE_DIA + spec.ARBOR_BORE_BAND[0],
    )
    # The drum bonds onto MHA-DT-022's bond zone, not its journal lands (U39).
    assert arbor.SHAFT_DIA_BAND != arbor.JOURNAL_DIA_BAND
    assert bore_limits == pytest.approx((8.00, 8.10))
    # A stock 8 mm H7 reamer (8.000-8.015) lands inside the band.
    assert bore_limits[0] <= 8.000 and 8.015 <= bore_limits[1]
    minimum_clearance = bore_limits[0] - shaft_limits[1]
    maximum_clearance = bore_limits[1] - shaft_limits[0]
    assert minimum_clearance == pytest.approx(
        spec.ARBOR_BORE_BAND[1] - arbor.SHAFT_DIA_BAND[0]
    )
    # The drum slides on by hand: the arbor's bond zone sits 0.01 under 8.00.
    assert minimum_clearance == pytest.approx(0.010)
    assert minimum_clearance >= 0.010 - 1e-9
    assert maximum_clearance == pytest.approx(
        spec.ARBOR_BORE_BAND[0] - arbor.SHAFT_DIA_BAND[1]
    )
    assert maximum_clearance == pytest.approx(0.200)
    assert maximum_clearance < spec.RETAINING_COMPOUND_MAX_GAP_MM
    assert spec.BORE_DIA == arbor_geometry.SHAFT_DIA  # the CAD models line-to-line


def test_the_drum_bond_is_the_fitup_step_not_a_note() -> None:
    import dt_pinion_arbor_spec as arbor_spec

    notes = spec.DRAWING_NOTES
    # Rule 6 (R3): one note.  The drum is symmetric, so no orientation note;
    # its axial station is stated once, on MHA-DT-022.  The MHA-DT-022 bond-zone
    # band is MHA-DT-022's own native dimension (Codex P1 on #814), the hand
    # slide rides the bore callout (Codex P2 on #832), and the bond itself is
    # the pinion fit-up step MHA-DT-022's spec owns (Main's rule-6 sweep).
    assert notes == "TOOTH FLANKS, TIPS, AND ROOTS: DO NOT CHAMFER OR BLEND."
    assert "BOND ZONE" not in notes
    assert "ARBOR JOURNAL" not in notes
    assert "LOCTITE" not in notes and "ON ASSEMBLY" not in notes
    assert "MHA-DT-001" in arbor_spec.ASSEMBLY_STEP
    assert spec.RETAINING_COMPOUND in arbor_spec.ASSEMBLY_STEP
    assert "j=19" not in notes and "LOCATED FROM" not in notes
    assert "MATES WITH CYLINDER-GEAR BANK" not in notes
    for retired in ("INTERFERENCE", "MATCHED FIT", "ENSURES FULL ENGAGEMENT", "+/-0.5"):
        assert retired not in notes, retired


def test_part_metadata_preserves_material_finish_quantity() -> None:
    config = _config.parts("dt-alignment-pinion")
    assert config["material_specification"] == "C36000 free-machining brass"
    assert config["finish"] == "bore as reamed; teeth as cut"
    assert int(config["quantity"]) == 1


class _FakeNote:
    def __init__(self, linked: str, resolved: str) -> None:
        self.PropertyLinkedText = linked
        self._resolved = resolved

    def GetText(self) -> str:
        return self._resolved


class _FakeDrawing:
    def __init__(self) -> None:
        self.rebuilds = 0

    def ForceRebuild3(self, top_only: bool) -> bool:
        self.rebuilds += 1
        return True


def test_material_readback_rebuilds_before_comparing_resolved_text() -> None:
    import draw_dt_alignment_pinion as draw

    linked = 'MATERIAL: $PRPSHEET:"Material Specification"'
    resolved = "MATERIAL: C36000 free-machining brass"
    drawing = _FakeDrawing()
    draw._verify_title_material_specification(
        drawing, (_FakeNote(linked, resolved), linked, resolved)
    )
    assert drawing.rebuilds == 1


def test_material_readback_names_the_unresolved_text() -> None:
    import draw_dt_alignment_pinion as draw

    linked = 'MATERIAL: $PRPSHEET:"Material Specification"'
    with pytest.raises(RuntimeError, match="got 'MATERIAL: '"):
        draw._verify_title_material_specification(
            _FakeDrawing(),
            (
                _FakeNote(linked, "MATERIAL: "),
                linked,
                "MATERIAL: C36000 free-machining brass",
            ),
        )


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
    assert spec.BASE_TANGENT_SPAN_BAND == (0.0, -0.100)
    assert (
        f"BASE-TANGENT SPAN, OVER {k} TEETH (mm):  "
        f"{spec.BASE_TANGENT_SPAN:.{spec.BASE_TANGENT_SPAN_PLACES}f} "
        f"+{spec.BASE_TANGENT_SPAN_BAND[0]:.3f}"
        f"/{spec.BASE_TANGENT_SPAN_BAND[1]:.3f}"
    ) in spec.GEAR_DATA


def test_printed_thickness_corners_keep_finite_actual_cutter_support() -> None:
    span_limits = spec.base_tangent_span_limits_mm()
    nominal = round(spec.BASE_TANGENT_SPAN, spec.BASE_TANGENT_SPAN_PLACES)
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

    assert draw.DIMENSION_CALLOUTS["ArborBoreDia"].splitlines()[0] == "REAM THRU"


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
    """Rule 6: a matched-fit acceptance belongs on the feature callout or an
    assembly step, never in a general note (Codex P2 on #832)."""
    import draw_dt_alignment_pinion as draw

    callout = draw.DIMENSION_CALLOUTS["ArborBoreDia"]
    assert callout == spec.ARBOR_BORE_CALLOUT
    arbor = _config.parts("dt-pinion-arbor")
    assert callout.splitlines()[1:] == [
        f"SLIDES BY HAND ON {arbor['number']}",
        arbor["title"].upper(),
    ]
    assert arbor["number"] == "MHA-DT-022"
    assert "PINION ARBOR" in callout
    for line in spec.DRAWING_NOTES.splitlines():
        assert "SLIDE" not in line and "BY HAND" not in line, line


def test_critical_tip_bands_keep_nominal_stock_root_air() -> None:
    """Retain the >0.20 air guard with both ACTUAL printed tip/root envelopes."""
    import dt_cylinder_gear_spec as gear

    assert spec.OUTSIDE_DIA_BAND == gear.OUTSIDE_DIA_BAND
    assert spec.OUTSIDE_DIA_BAND == gear_tip_band_mm("contact_critical")
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
    places = spec.DRAWING_PRECISION_BY_NAME["OutsideDia"]
    nominal = round(spec.OUTSIDE_DIA, places)
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

    assert spec.DRAWING_DIMENSIONS["GearBlankProfile"] == {"OutsideDia"}
    assert drawing.FRONT_KEEP.keys() | drawing.RIGHT_KEEP.keys() == set(
        spec.DRAWING_PRECISION_BY_NAME
    )
    source = Path(spec.__file__).with_name("build_dt_alignment_pinion.py")
    calls = [
        node
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8")))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "set_dimension_bilateral_tolerance"
    ]
    assert any(
        len(call.args) == 4
        and ast.literal_eval(call.args[1]) == "GearBlankProfile"
        and ast.literal_eval(call.args[2]) == "OutsideDia"
        and ast.unparse(call.args[3]) == "*deviations(OUTSIDE_DIA_BAND)"
        for call in calls
    )
    assert "OUTSIDE DIAMETER" not in spec.GEAR_DATA


def test_tip_grade_configuration_reaches_the_part_spec(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_fit = _config.fit
    changed_band = [0.0, -0.01]

    def fit_value(*keys: str):
        if keys == ("gear_tip", "contact_critical_band_mm"):
            return changed_band
        return original_fit(*keys)

    monkeypatch.setattr(_config, "fit", fit_value)
    dimensions = runpy.run_path(spec.__file__)
    assert dimensions["OUTSIDE_DIA_BAND"] == tuple(changed_band)
    nominal = round(
        dimensions["OUTSIDE_DIA"], dimensions["DRAWING_PRECISION_BY_NAME"]["OutsideDia"]
    )
    assert dimensions["outside_dia_limits_mm"]() == pytest.approx(
        (nominal - 0.01, nominal), abs=1e-12
    )


def test_no_note_line_carries_a_dimension() -> None:
    """Rule 6: once part numbers and the named retaining compound are set
    aside, no note line carries a digit (Codex P1 on #814)."""
    for line in spec.DRAWING_NOTES.splitlines():
        text = re.sub(r"MHA-[A-Z]{2}-\d{3}(?:-T\d{3})?", "", line).replace(spec.RETAINING_COMPOUND, "")
        assert not re.search(r"\d", text), line
