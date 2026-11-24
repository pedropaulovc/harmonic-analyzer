"""Finished-fit and tooth-system contracts consumed by the native drawing."""

from __future__ import annotations

import math
import runpy
from collections import Counter
from pathlib import Path

import pytest

import _config
from _buildgraph import module_deps_of
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
import _shop_equipment
from _gear_fit_limits import gear_tip_band_mm
import build_dt_cylinder_gear as part
import dt_cylinder_gear_notes as notes
import dt_cylinder_gear_shaft_spec as arbor
import dt_cylinder_gear_spec as spec
import draw_dt_cylinder_gear as drawing


def test_reamed_bore_closes_the_configured_running_fit_on_the_arbor() -> None:
    # Interchangeable (#290): every gear is reamed .3760-.3765 in, so the
    # clearance on the SHAFT_H arbor is the shaft_in_bushing class, and the
    # model bore sits at its least size, never on the arbor's nominal.
    from _fit_ream_slide import REAM_SLIDE

    assert spec.BORE_DIA == pytest.approx(arbor.SHAFT_DIA + REAM_SLIDE[1])
    assert spec.BORE_DIA + spec.BORE_DIA_BAND[0] == pytest.approx(
        arbor.SHAFT_DIA + REAM_SLIDE[0]
    )
    assert spec.BORE_DIAMETRAL_CLEARANCE_MM == pytest.approx(
        tuple(_config.fit("shaft_in_bushing", "diametral_clearance_mm"))
    )
    assert spec.BORE_DIA - arbor.SHAFT_DIA == pytest.approx(0.0254)


def test_blank_and_tooth_profile_follow_the_same_configured_pitch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured_pitch = 40.0  # Deliberately differs from the current machine setting.
    original_machine = _config.machine

    def machine_value(*keys: str):
        if keys == ("gear_train", "diametral_pitch"):
            return configured_pitch
        return original_machine(*keys)

    monkeypatch.setattr(_config, "machine", machine_value)
    dimensions = runpy.run_path(spec.__file__)
    profile = dimensions["STOCK_FORM"]
    assert profile.template.diametral_pitch == configured_pitch
    assert profile.teeth == dimensions["TEETH"]
    assert dimensions["OUTSIDE_DIA"] / 2.0 == pytest.approx(profile.blank_radius_mm)
    assert dimensions["SUPPORT_OUTSIDE_DIA_MM"] == pytest.approx(
        2.0 * profile.support_radius_max_mm
    )


def test_tooth_system_and_reference_cutter_are_spec_owned() -> None:
    assert spec.TEETH == int(_config.machine("gear_train", "cylinder_teeth"))
    assert spec.DIAMETRAL_PITCH == _config.machine("gear_train", "diametral_pitch")
    assert spec.PRESSURE_ANGLE_DEG == _config.machine(
        "gear_train", "pressure_angle_deg"
    )
    assert spec.PITCH_DIA == pytest.approx(spec.TEETH * spec.MODULE_MM)
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
    assert spec.OUTSIDE_DIA <= spec.MAX_DEPTH_SUPPORT_OUTSIDE_DIA_MM
    assert spec.OUTSIDE_DIA + 0.0254 > spec.MAX_DEPTH_SUPPORT_OUTSIDE_DIA_MM
    assert spec.OUTSIDE_DIA_BAND == gear_tip_band_mm("standard")
    assert spec.WHOLE_DEPTH_BAND == (0.0508, 0.0)
    assert spec.CUTTER_NUMBER == 2
    assert spec.CUTTER_TEETH_RANGE == (55, 134)
    assert spec.CUTTER_TEETH_RANGE[0] <= spec.TEETH <= spec.CUTTER_TEETH_RANGE[1]
    assert "NONSTANDARD" not in notes.GEAR_DATA
    assert "OUTSIDE DIAMETER" not in notes.GEAR_DATA


def test_drum_prints_the_tooth_runout_the_cone_mesh_stack_books() -> None:
    import cone_set_stack

    assert notes.TOOTH_RUNOUT_TIR_MM == cone_set_stack.TOOTH_RUNOUT_TIR_MM
    printed = notes.inch_text(cone_set_stack.TOOTH_RUNOUT_TIR_MM, 3)
    assert f"TOOTH RUNOUT TO BORE:  {printed} TIR MAX" in notes.GEAR_DATA.splitlines()
    assert "ACCEPT AT SETUP" not in notes.GEAR_DATA
    assert float(printed) * 25.4 == pytest.approx(cone_set_stack.TOOTH_RUNOUT_TIR_MM)


def test_title_block_notch_depth_still_cuts_below_the_root_and_clears_the_cam() -> None:
    from _printed_tolerance import printed_band_mm

    band = printed_band_mm(
        spec.DRAWING_PRECISION["NotchProfile"]["NotchDepth"], unit=spec.UNIT
    )
    assert spec.NOTCH_DEPTH - band > spec.WHOLE_DEPTH + spec.WHOLE_DEPTH_BAND[0]
    assert spec.TIP_RADIUS - (spec.NOTCH_DEPTH + band) > (
        spec.CAM_DIA / 2.0 + spec.ECCENTRICITY + spec.ECCENTRICITY_TOLERANCE_MM
    )


def test_fit_callouts_name_their_mate_and_banded_sizes_carry_no_words() -> None:
    callouts = drawing.DIMENSION_CALLOUTS
    assert "MHA-DT-03" in callouts["OutsideDia"]
    assert "MHA-CH-03" in callouts["CamDia"]
    # Rule 4 (major_version 2): the reamed bore prints no band and its
    # bought mate is the gauge; the reasons live in the necessity register.
    assert "MHA-DT-13" in notes.BORE_FIT_CALLOUT
    assert ("BoreProfile", "BoreDia") not in model_toleranced_dimensions(part)
    # Rule 7: a location or a band with no mate carries its value and band
    # and nothing else.
    assert not {"CamCy", "NotchPhase", "NotchDepth", "FaceWidth"} & set(callouts)


def _kerf_flank_hits(width: float) -> int:
    """Tooth material above the root inside a ``width`` kerf at NOTCH_X."""
    root = spec.STOCK_FORM.root_radius_max_mm
    nx, ny = 40, 300
    hits = 0
    for i in range(nx):
        x = part.NOTCH_X - width / 2.0 + i * width / (nx - 1)
        for j in range(ny):
            y = root + (j + 0.5) * (spec.TIP_RADIUS - root) / ny
            hits += math.hypot(x, y) > root and part.is_solid(x, y)
    return hits


def test_sighted_notch_prints_only_its_flank_clear_maximum() -> None:
    # Nothing engages the kerf, so it carries one limit: swTolMAX prints the
    # model value, so the modelled width IS the maximum, banded down to zero.
    assert spec.NOTCH_WIDTH_TOL_TYPE == 6
    assert spec.NOTCH_WIDTH_BAND == (0.0, -spec.NOTCH_WIDTH)
    assert ("NotchProfile", "NotchWidth") not in model_toleranced_dimensions(part)
    # At that maximum the kerf takes no tooth material above the root; the
    # former +0.10/0 band's 0.50 would have nicked both neighbouring flanks.
    assert _kerf_flank_hits(spec.NOTCH_WIDTH) == 0
    assert _kerf_flank_hits(0.50) > 0


def test_the_listed_notch_saw_fits_the_printed_maximum() -> None:
    # #2364: the archived 1/32 saw is wider than the MAX, so the notch is cut
    # with the not-yet-owned saw recorded for it. At or under the MAX the
    # kerf is flank-clear (test_sighted_notch_prints_only_its_flank_clear_maximum).
    saw = _shop_equipment.load()["tools"]["cylinder-notch-saw"]
    assert saw["thickness_in"] * 25.4 <= spec.NOTCH_WIDTH


def test_worst_case_cam_wall_is_printed_and_clears_the_floor() -> None:
    from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
    from _printed_tolerance import printed_deviations

    cam_lower = printed_deviations(
        spec.CAM_DIA, 3, (spec.CAM_DIA_BAND[1], spec.CAM_DIA_BAND[0]), unit="in"
    )[0]
    ecc_upper = printed_deviations(
        spec.ECCENTRICITY,
        4,
        (-spec.ECCENTRICITY_TOLERANCE_MM, spec.ECCENTRICITY_TOLERANCE_MM),
        unit="in",
    )[1]
    worst_wall = (
        (spec.CAM_DIA + cam_lower) / 2.0
        - (spec.ECCENTRICITY + ecc_upper)
        - (spec.BORE_DIA + spec.BORE_DIA_BAND[0]) / 2.0
    )
    assert worst_wall - 0.0254 < spec.CAM_WALL_MIN_MM <= worst_wall
    # Rule 17 (inch): under the .080 target, over the .060 floor (#992).
    assert WALL_FLOOR_MM < spec.CAM_WALL_MIN_MM < WALL_TARGET_MM
    printed = notes.inch_text(spec.CAM_WALL_MIN_MM, 3)
    assert f"WALL {printed} MIN" in notes.CAM_WALL_NOTE


def test_cam_and_notch_oracles_use_actual_off_centre_root_material() -> None:
    import math

    profile = spec.STOCK_FORM
    assert spec.CAM_ROOT_WEB_MIN_MM == pytest.approx(
        profile.root_radius_min_mm - (spec.CAM_DIA / 2.0 + spec.ECCENTRICITY)
    )
    assert spec.CAM_ROOT_WEB_MIN_MM > 0.0
    assert part.is_solid(0.0, 0.0)
    assert not part.is_solid(spec.OUTSIDE_DIA / 2.0 + 0.01, 0.0)
    radius = (profile.root_radius_min_mm + profile.root_radius_max_mm) / 2.0
    root_parameter = profile.template.flank_parameter_min
    root_angle = (
        profile.template.half_space_base_angle_rad
        + root_parameter
        - math.atan(root_parameter)
    )
    reference_root = profile.template.root_radius_mm
    endpoint_angle = math.atan2(
        reference_root * math.sin(root_angle),
        profile.radial_translation_mm + reference_root * math.cos(root_angle),
    )
    # A circular actual-axis root would classify both points identically.
    assert profile.contains_material(radius, 0.0)
    assert not profile.contains_material(
        radius * math.cos(endpoint_angle), radius * math.sin(endpoint_angle)
    )
    for angle in (0.0, endpoint_angle, math.pi / spec.TEETH, math.pi / 2.0):
        x, y = radius * math.cos(angle), radius * math.sin(angle)
        assert part.is_solid(x, y) == profile.contains_material(
            x, y, rotate_rad=math.pi / spec.TEETH
        )


def test_critical_tip_is_a_marked_native_dimension() -> None:
    assert spec.DRAWING_DIMENSIONS["GearBlankProfile"] == {"OutsideDia"}
    assert "OutsideDia" in drawing.RIGHT_KEEP
    assert model_toleranced_dimensions(part)[("GearBlankProfile", "OutsideDia")] == (
        "*deviations(OUTSIDE_DIA_BAND)"
    )
    assert part.OUTSIDE_DIA_BAND == spec.OUTSIDE_DIA_BAND


def test_printed_plunge_corners_keep_finite_actual_cutter_support() -> None:
    depth_limits = spec.whole_depth_limits_mm()
    places = spec.WHOLE_DEPTH_PLACES
    nominal = round(spec.WHOLE_DEPTH / 25.4, places) * 25.4  # the printed inch plunge
    upper, lower = spec.WHOLE_DEPTH_BAND
    assert depth_limits == pytest.approx((nominal + lower, nominal + upper))
    profiles = spec.manufacturing_corner_profiles()
    assert len(profiles) == 4
    for profile, (tip, depth) in zip(
        profiles,
        (
            (tip, depth)
            for tip in spec.outside_dia_limits_mm()
            for depth in depth_limits
        ),
        strict=True,
    ):
        assert profile.template == spec.CUTTER_TEMPLATE
        assert profile.teeth == spec.TEETH
        assert profile.blank_radius_mm == pytest.approx(tip / 2.0)
        assert profile.radial_translation_mm == pytest.approx(
            tip / 2.0 - spec.CUTTER_TEMPLATE.root_radius_mm - depth
        )
        assert profile.plunge_mm == pytest.approx(depth)
        assert profile.blank_radius_mm <= profile.support_radius_max_mm
        assert profile.root_radius_min_mm > spec.CAM_DIA / 2.0 + spec.ECCENTRICITY


def test_tip_limits_follow_printed_nominal_and_shared_grade(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    places = spec.DRAWING_PRECISION_BY_NAME["OutsideDia"]
    nominal = round(spec.OUTSIDE_DIA / 25.4, places) * 25.4  # the printed inch tip
    upper, lower = gear_tip_band_mm("standard")
    assert spec.outside_dia_limits_mm() == pytest.approx(
        (nominal + lower, nominal + upper), abs=1e-12
    )
    assert spec.outside_dia_limits_mm()[1] <= spec.SUPPORT_OUTSIDE_DIA_MM
    assert spec.OUTSIDE_DIA < (spec.TEETH + 2) * spec.MODULE_MM
    original_fit = _config.fit
    changed_band = [0.0, -0.01]

    def fit_value(*keys: str):
        if keys == ("gear_tip", "standard_band_mm"):
            return changed_band
        return original_fit(*keys)

    monkeypatch.setattr(_config, "fit", fit_value)
    dimensions = runpy.run_path(spec.__file__)
    assert dimensions["OUTSIDE_DIA_BAND"] == tuple(changed_band)
    assert dimensions["outside_dia_limits_mm"]() == pytest.approx(
        (nominal - 0.01, nominal), abs=1e-12
    )


def test_every_marked_dimension_has_exactly_one_view_owner() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    ownership = Counter(
        name
        for view_dimensions in (
            drawing.FRONT_KEEP,
            drawing.RIGHT_KEEP,
            drawing.NOTCH_DETAIL_DIMENSIONS,
        )
        for name in view_dimensions
    )
    assert ownership == Counter(marked)
    assert set(drawing.DIMENSION_CALLOUTS) <= marked


def test_the_part_owns_every_printed_decimal_place() -> None:
    """drawing-simplicity-policy.md `How the repository implements the guidelines`: places are the tolerance, so the .SLDPRT carries them.

    Inch places (#290): four on the reamed bore (the .3760 reamer's size) and on the two
    kinematic values held to +/-.0010 (the stacking thickness that IS the
    station pitch, and the cam throw); three on the +/-.002-class bands and
    the .016 MAX kerf; the cam thickness is the one sheet-derived value, a
    parenthesised reference.
    """
    by_name = spec.DRAWING_PRECISION_BY_NAME
    assert set(by_name) == set().union(*spec.DRAWING_DIMENSIONS.values())
    assert {name for name, places in by_name.items() if places == 3} == {
        "FaceWidth",
        "OutsideDia",
        "CamDia",
        "NotchWidth",
    }
    assert {name for name, places in by_name.items() if places == 4} == {
        "BoreDia",
        "CamCy",
        "OverallThickness",
    }
    assert spec.DRAWING_REFERENCE_PRECISION == {"cam thickness reference": 3}
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


@pytest.mark.parametrize(
    ("assembly_script", "reads_cylinder_spec"),
    (
        ("build_ch_channel_assembly.py", True),
        ("build_dt_drive_train_assembly.py", True),
        # paper-drive read the cylinder spec only through the drive-train
        # script; it now takes the crank axis from cone_line (#880).
        ("build_pd_paper_drive_assembly.py", False),
    ),
)
def test_assembly_recipes_exclude_cylinder_drawing_prose(
    assembly_script: str, reads_cylinder_spec: bool
) -> None:
    dependencies = {
        Path(path).name
        for path in module_deps_of(Path(__file__).with_name(assembly_script))
    }
    assert ("dt_cylinder_gear_spec.py" in dependencies) is reads_cylinder_spec
    assert dependencies.isdisjoint(
        {
            "build_dt_cylinder_gear.py",
            "dt_cylinder_gear_notes.py",
            "dt_cylinder_gear_phase_band.py",
        }
    )


def test_stacking_thickness_is_the_held_marked_dimension() -> None:
    # The overall thickness sets every station of the solid bank (#743), so it
    # is a marked model dimension printed to four places with its own band;
    # the cam thickness between it and the face width is only a reference.
    assert spec.DRAWING_DIMENSIONS["CamBoss"] == {"OverallThickness"}
    assert spec.DRAWING_PRECISION_BY_NAME["OverallThickness"] == 4
    assert "OverallThickness" in drawing.RIGHT_KEEP
    assert ("CamBoss", "OverallThickness") in model_toleranced_dimensions(part)


def test_pattern_notch_reference_uses_the_actual_seed_gap() -> None:
    kerf_axis = math.pi / 2.0 + math.radians(spec.NOTCH_PHASE_DEG)
    assert spec.TOOTH_PATTERN_GAP_RAD == pytest.approx(math.pi / spec.TEETH)
    assert math.degrees(kerf_axis - spec.TOOTH_PATTERN_GAP_RAD) == pytest.approx(
        spec.PATTERN_NOTCH_REF_ANGLE_DEG
    )
    assert spec.PATTERN_NOTCH_REF_ANGLE_DEG == 90.0
    # NotchPhase prints the widened band (delegated ruling 2026-11-17, #2361):
    # the budget's gear-to-gear +/-.25 plus the cam fixture's common phase.
    assert spec.CAM_PHASE_TOLERANCE_DEG == 0.25
    assert part.NOTCH_PHASE_TOLERANCE_DEG == 0.7
    assert spec.DRAWING_PRECISION["NotchProfile"]["NotchPhase"] == 1
    assert spec.DRAWING_PRECISION["NotchProfile"]["PatternNotchPhase"] == 0
    assert "PatternNotchPhase" in drawing.FRONT_KEEP


def test_cam_lobe_stands_on_the_tooth_space_away_from_the_notch() -> None:
    # Owner ruling 2026-11-20 on #749 ("B"): the lobe is cut the drive train's
    # half-pitch lock clockwise of the +Y crest, so the lock stands it up; the
    # notch keeps its tooth space, so NotchPhase is a whole pitch.
    import dt_cylinder_gear_phase_band as phase_band

    half_pitch = 180.0 / spec.TEETH
    assert phase_band.CAM_LOBE_OFFSET_DEG == pytest.approx(half_pitch)
    assert phase_band.CAM_NOTCH_PHASE_DEG == pytest.approx(2.0 * half_pitch)
    cam_x, cam_y = phase_band.CAM_CENTER_XY
    assert math.hypot(cam_x, cam_y) == pytest.approx(spec.ECCENTRICITY)
    assert cam_x > 0.0 > spec.NOTCH_CENTER_X  # opposite sides of the crest
    assert math.degrees(math.atan2(cam_x, cam_y)) == pytest.approx(half_pitch)
    assert drawing.CAM_X == cam_x and drawing.CAM_Y == cam_y


def test_pattern_notch_drawing_consumes_pure_specification() -> None:
    assert drawing.PATTERN_NOTCH_REF_ANGLE_DEG is spec.PATTERN_NOTCH_REF_ANGLE_DEG
