"""Offline contracts for the rack-pinion drawing (batch gear pattern)."""

from __future__ import annotations

import ast
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

import _rack_bore_finish as finish_helper
import build_pd_rack_pinion as part
import draw_pd_rack_pinion as drawing
import pd_rack_pinion_spec as spec
import pd_transgear_disc_hub_geometry as hub_geometry
import vn_transgear_disc_screw_spec as disc_screw
from _drawing_contract import (
    PRECISION_MIGRATED_DRAWINGS,
    drawing_specification_violations,
    model_toleranced_dimensions,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _layout_geometry import estimate_text_box
from _printed_tolerance import printed_band_mm
from paper_drive_stock_inspection import span_contact_points_mm


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pd-rack-pinion.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pd-rack-pinion.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pd-rack-pinion_drawing.png")
    assert DRAWINGS_BY_NAME["pd_rack_pinion"].script == Path(drawing.__file__).resolve()


def test_every_marked_dimension_is_kept_once_with_part_authored_places() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = [*drawing.FRONT_KEEP, *drawing.RIGHT_KEEP]
    assert sorted(kept) == sorted(marked) == [
        "BoreDia", "FaceWidth", "OutsideDia", "RootEnvelope", "ToothSpan"
    ]
    # The non-tooth bands stay unchanged; physical span LIMITS print four places.
    assert spec.DRAWING_PRECISION_BY_NAME == {
        "FaceWidth": 3,
        "OutsideDia": 2,
        "BoreDia": 3,
        "ToothSpan": 4,
        "RootEnvelope": 3,
    }
    assert "draw_pd_rack_pinion.py" in PRECISION_MIGRATED_DRAWINGS
    assert model_toleranced_dimensions(part) == {
        ("BoreProfile", "BoreDia"): "*BORE_DEVIATIONS",
        ("GearBlankProfile", "OutsideDia"): "*deviations(OUTSIDE_DIA_BAND)",
    }
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert not drawing_specification_violations(source, filename=drawing.__file__)


def test_the_disc_prints_no_tap_position() -> None:
    """R9-9: the taps are transferred from the MHA-PD-017 flange at assembly."""
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert not any("Tap" in name or "BoltCircle" in name for name in marked)
    assert "DiscTaps" not in spec.DRAWING_DIMENSIONS


def test_taps_sit_on_the_flange_bolt_circle() -> None:
    assert spec.TAP_CENTRES == hub_geometry.screw_centres()
    assert spec.TAP_COUNT == hub_geometry.SCREW_COUNT == 3
    for (x, y), angle in zip(
        spec.TAP_CENTRES, hub_geometry.SCREW_ANGLES_DEG, strict=True
    ):
        assert math.hypot(x, y) == pytest.approx(hub_geometry.BOLT_CIRCLE_DIA / 2.0)
        assert math.degrees(math.atan2(y, x)) % 360.0 == pytest.approx(angle)


def test_disc_screw_engages_at_least_one_and_a_half_diameters_worst_case() -> None:
    """R9-47: the MHA-VN-039 tips are cut to fit inside the rear face, so the
    joint (judged in transgear_disc_screw_spec) spends the tap's losses here."""
    assert spec.TAP_SPEC.size == hub_geometry.SCREW_THREAD == "#0-80"
    assert disc_screw.ENGAGEMENT_WORST_D >= spec.ENGAGEMENT_FLOOR_D == 1.5
    assert (
        disc_screw.ENGAGEMENT_WORST
        < disc_screw.ENGAGEMENT_NOMINAL
        < spec.FACE_WIDTH - spec.MOUTH_THREAD_LOSS
    )


def test_the_tap_mouths_lose_only_their_breaks_counted_from_the_drill() -> None:
    """Machinist review of 8b5e1f354 (blocker): full thread starts where a
    mouth's 45° leg meets the tap drill, so the far-side Ø1.8 MAX countersink
    cost 0.305, not the 0.138 counted to the major, and 1.53D printed over
    1.48D.  R9-63: no countersink, a 0.10 break on each mouth."""
    assert spec.MOUTH_THREAD_LOSS == spec.MOUTH_BREAK_MAX == pytest.approx(0.10)
    rear = max(
        spec.MOUTH_BREAK_MAX,
        disc_screw.TIP_BELOW_REAR_FACE[1] + disc_screw.CUT_END_BREAK_MAX,
        disc_screw.STOCK_TIP_INSIDE_REAR_MAX + spec.SCREW_PITCH,
    )
    assert rear == pytest.approx(0.3895, abs=1e-4)
    worst = spec.FACE_WIDTH_MIN - spec.MOUTH_BREAK_MAX - rear
    assert disc_screw.ENGAGEMENT_WORST == pytest.approx(worst)
    assert worst == pytest.approx(2.3805, abs=1e-4)
    assert worst / spec.TAP_MAJOR >= spec.ENGAGEMENT_FLOOR_D
    # The old Ø1.7 +0.10/0 countersink, charged to the drill, fell short.
    old_loss = (1.8 - spec.TAP_DRILL_DIA) / 2.0
    assert (spec.FACE_WIDTH_MIN - old_loss - rear) / spec.TAP_MAJOR < 1.5


def test_disc_tap_drill_cuts_a_2b_minor_at_about_80_percent_thread() -> None:
    """The 3/64 (1.191) tap drill for the MHA-VN-039 #0-80 UNF-2B disc taps,
    against ASME B1.1's 2B table: minor 0.0465..0.0514 in, and the
    tap-drill rule %thread = (major - drill) / (1.299038 P)."""
    inch = 25.4
    major, pitch = 0.0600 * inch, inch / 80.0
    minor_2b = (0.0465 * inch, 0.0514 * inch)  # 1.181 .. 1.306
    assert spec.TAP_MAJOR == pytest.approx(major, abs=5e-4)
    assert spec.SCREW_PITCH == pytest.approx(pitch)
    assert spec.TAP_DRILL_DIA == pytest.approx(3.0 / 64.0 * inch, abs=5e-4)
    assert minor_2b[0] <= spec.TAP_DRILL_DIA <= minor_2b[1]
    thread_percent = 100.0 * (major - spec.TAP_DRILL_DIA) / (1.299038 * pitch)
    assert thread_percent == pytest.approx(80.8, abs=0.5)


def test_tap_to_bore_wall_meets_the_target_worst_case() -> None:
    assert spec.TAP_TO_BORE_WALL_WORST >= 2.0
    assert spec.TAP_TO_BORE_WALL_WORST < spec.TAP_TO_BORE_WALL


def test_the_bore_pilots_on_the_hub_spigot_at_every_limit() -> None:
    """The bands the two builds apply (the disc's H7 bore, the MHA-PD-017 hub's
    h6 spigot) never bind: at the tightest corner, the smallest bore over the
    largest spigot, they meet line on line, and the fit note quotes the
    clearance the limits give."""
    import build_pd_transgear_disc_hub as hub_part
    import pd_transgear_disc_hub_spec as hub

    assert (
        model_toleranced_dimensions(hub_part)[("HubProfile", "SpigotDia")]
        == "*SPIGOT_DIA_DEVIATIONS"
    )
    assert spec.BORE_DIA == hub.SPIGOT_DIA
    bore_lower, bore_upper = spec.BORE_DEVIATIONS
    spigot_lower, spigot_upper = hub.SPIGOT_DIA_DEVIATIONS
    least = (spec.BORE_DIA + bore_lower) - (hub.SPIGOT_DIA + spigot_upper)
    greatest = (spec.BORE_DIA + bore_upper) - (hub.SPIGOT_DIA + spigot_lower)
    assert least >= -1e-9
    assert (least, greatest) == pytest.approx(spec.SPIGOT_DIAMETRAL_CLEARANCE)
    # The disc's float on the spigot feeds the transferred taps' wall.
    assert spec.DISC_OFFSET_MAX == pytest.approx(greatest / 2.0)
    note = spec.BORE_FIT_CALLOUT
    assert "MATE HUB MHA-PD-017 SPIGOT" in note
    assert f"(DIA CLR {least:.3f}-{greatest:.3f} mm)" in note
    assert f"\N{DIAMETER SIGN}{hub.SPIGOT_DIA:.3f} +{spigot_upper:.3f}/" in note
    assert all(len(line) <= 70 for line in note.splitlines())
    for banned in ("EXCEPTION", "ACCEPTED", "RULING", "POLICY", "BOOK FIDELITY"):
        assert banned not in note.upper()


def test_the_bore_front_chamfer_clears_the_spigot_corner() -> None:
    """The flange clamps the front face only if the bore's front chamfer
    reaches past the hub's spigot-to-flange corner radius."""
    import pd_transgear_disc_hub_spec as hub

    assert spec.BORE_FRONT_CHAMFER_LIMITS[0] >= hub.CORNER_RADIUS_MAX
    assert spec.BORE_FRONT_CHAMFER_NOTE in spec.DRAWING_NOTES.splitlines()


def test_thickness_band_is_the_printed_xxx_band() -> None:
    band = printed_band_mm(3)
    assert (spec.FACE_WIDTH_MIN, spec.FACE_WIDTH_MAX) == pytest.approx(
        (spec.FACE_WIDTH - band, spec.FACE_WIDTH + band)
    )


def test_tap_callout_carries_both_mouth_breaks_and_transfer() -> None:
    definitions = {5: "", 6: "<hw-threadclass> THRU", 7: "", 8: ""}
    updated = drawing.tap_callout_definitions(definitions)
    assert updated[6].endswith(spec.TAP_CALLOUT_QUALIFIER)
    assert {k: v for k, v in updated.items() if k != 6} == {5: "", 7: "", 8: ""}
    text = spec.TAP_CALLOUT_QUALIFIER
    assert "CSK" not in text
    assert f"BREAK EDGE {spec.MOUTH_BREAK_MAX:.2f} MAX BOTH SIDES" in text
    assert "MHA-PD-017" in text and "MATCH-MARK" in text
    for banned in ("EXCEPTION", "ACCEPTED", "RULING", "POLICY", "BOOK FIDELITY"):
        assert banned not in text.upper()
    with pytest.raises(RuntimeError):
        drawing.tap_callout_definitions({5: "", 6: "", 7: "", 8: ""})


def test_gear_data_block_specifies_the_actual_finite_tooth_system() -> None:
    data = spec.GEAR_DATA
    for label, value in (
        ("NUMBER OF TEETH", "120"),
        ("DIAMETRAL PITCH", "48.00"),
        ("PRESSURE ANGLE", "20.0 DEG"),
        ("TOTAL TOOL TRANSLATION T (mm, REF)", f"{spec.RADIAL_SETTING:.3f}"),
        ("PITCH DIAMETER (mm, REF)", f"{spec.PITCH_DIA:.2f}"),
        ("CIRCULAR THICKNESS AT PD (mm, REF)", f"{spec.TOOTH_THICKNESS:.3f}"),
        ("THICKNESS INSPECTION", f"NATIVE SPAN OVER {spec.SPAN_TEETH} TEETH"),
        (
            "CUTTER TEMPLATE",
            f"#{spec.CUTTER_NUMBER}, "
            f"{spec.CUTTER_TOOTH_RANGE[0]}-{spec.CUTTER_TOOTH_RANGE[1]}T; "
            f"{spec.CUTTER_REFERENCE_TEETH}T MASTER",
        ),
        (
            "AXIS ROOT ENVELOPE DIA (mm, REF)",
            f"{spec.ROOT_ENVELOPE_DIA_MM[0]:.3f}-{spec.ROOT_ENVELOPE_DIA_MM[1]:.3f}",
        ),
    ):
        assert f"{label}:  {value}" in data
    assert spec.CUTTER_NUMBER == 2
    assert spec.CUTTER_REFERENCE_TEETH == 55 != spec.TEETH == 120
    assert spec.CUTTER_TOOTH_RANGE == (55, 134)
    assert spec.TOOTH_THICKNESS == spec.STOCK_PROFILE.pitch_tooth_thickness_mm
    assert part.GEAR_DATA == data
    assert "FINITE TRANSLATED STOCK FORM, NOT x" in data
    assert "VENDOR-CERTIFIED" in spec.DRAWING_NOTES
    assert not hasattr(spec, "PROFILE_SHIFT")
    assert not hasattr(spec, "MESH_PINION_PROFILE_SHIFT")
    assert "PROFILE SHIFT" not in data


def test_printed_span_limits_define_every_accepted_translation_corner() -> None:
    from stock_form_cutter import translation_for_tangent_span

    assert spec.SPAN_TEETH == 13
    assert spec.SPAN_LIMITS == (20.4174, 20.4308)
    assert spec.RADIAL_SETTING_LIMITS[0] < 17.200
    assert spec.RADIAL_SETTING_LIMITS[1] > 17.220
    for limit, setting, sign in zip(
        spec.SPAN_LIMITS, spec.RADIAL_SETTING_LIMITS, (-1.0, 1.0), strict=True
    ):
        target = limit + sign * 2.0 * spec._SPAN_GEOMETRY_ERROR
        inverse = translation_for_tangent_span(
            spec.TEETH,
            spec.CUTTER_TEMPLATE,
            target,
            spec.SPAN_TEETH,
            translation_bounds_mm=spec._SPAN_INVERSE_BOUNDS,
        )
        assert inverse == pytest.approx(setting, abs=1e-12)
    assert {profile.radial_translation_mm for profile in spec.manufactured_profiles()} == set(
        spec.RADIAL_SETTING_LIMITS
    )
    for profile in spec.manufactured_profiles():
        a, b = span_contact_points_mm(profile, spec.SPAN_TEETH)
        assert math.dist(a, b) == pytest.approx(profile.tangent_span_mm(spec.SPAN_TEETH))
        assert max(math.hypot(*a), math.hypot(*b)) <= profile.blank_radius_mm
        allowance = 4.0 * profile.geometry_error_bound_mm
        assert spec.SPAN_LIMITS[0] - allowance <= profile.tangent_span_mm(spec.SPAN_TEETH)
        assert profile.tangent_span_mm(spec.SPAN_TEETH) <= spec.SPAN_LIMITS[1] + allowance


def test_finite_blank_cap_uses_the_lowest_printed_span_inverted_translation() -> None:
    from stock_form_cutter import StockFormProfile

    lowest = StockFormProfile(
        120, spec.CUTTER_TEMPLATE, spec.PITCH_DIA / 2.0,
        spec.RADIAL_SETTING_LIMITS[0],
    )
    cap = 2.0 * lowest.support_radius_max_mm
    assert spec.SUPPORT_OUTSIDE_DIA_MM == pytest.approx(cap)
    assert spec.OUTSIDE_DIA == 64.54
    assert spec.OUTSIDE_DIA + spec.OUTSIDE_DIA_BAND[0] < cap
    # Standard actual-N OD would require unsupported upper-tip continuation.
    standard_od = (spec.TEETH + 2.0) * spec.MODULE_MM
    assert standard_od > cap
    with pytest.raises(ValueError, match="FINITE"):
        StockFormProfile(120, spec.CUTTER_TEMPLATE, standard_od / 2.0,
                         spec.RADIAL_SETTING_LIMITS[0])


def test_real_finite_corners_preserve_root_web_volume_and_material_land() -> None:
    for profile in spec.manufactured_profiles():
        assert profile.teeth == 120 and profile.template.reference_teeth == 55
        assert profile.root_radius_min_mm < profile.root_radius_max_mm
        assert 2.0 * profile.root_radius_min_mm >= spec.ROOT_DIA_MIN
        assert profile.root_radius_min_mm > hub_geometry.BOLT_CIRCLE_DIA / 2.0
        assert profile.tip_land_mm >= 0.25 * spec.MODULE_MM
        assert profile.support_radius_max_mm - profile.blank_radius_mm > profile.geometry_error_bound_mm
        toothed = (
            math.pi * profile.blank_radius_mm**2
            - profile.teeth * profile.gap_area_mm2
        ) * spec.FACE_WIDTH
        assert toothed > part.V_BORE + part.V_TAPS
        assert profile.gap_area_error_bound_mm2 < profile.gap_area_mm2


def test_native_builder_consumes_one_full_axial_profile_and_physical_inspection() -> None:
    assert part.STOCK_PROFILE is spec.STOCK_PROFILE
    tree = ast.parse(Path(part.__file__).read_text(encoding="utf-8"))
    build = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)
                 and node.name == "build")
    calls = [node for node in ast.walk(build) if isinstance(node, ast.Call)]
    native = [node for node in calls if isinstance(node.func, ast.Name)
              and node.func.id == "build_stock_form_gear"]
    assert len(native) == 1
    assert [ast.unparse(arg) for arg in native[0].args] == [
        "adapter", "STOCK_PROFILE", "FACE_WIDTH"
    ]
    assert not any(isinstance(node.func, ast.Name) and node.func.id == "build_fixed_gear"
                   for node in calls)
    span = next(node for node in calls if isinstance(node.func, ast.Name)
                and node.func.id == "author_span")
    assert [ast.unparse(arg) for arg in span.args] == [
        "adapter", "STOCK_PROFILE", "SPAN_TEETH"
    ]
    root = next(node for node in calls if isinstance(node.func, ast.Name)
                and node.func.id == "author_root_envelope")
    assert [ast.unparse(arg) for arg in root.args] == ["adapter", "STOCK_PROFILE"]
    limits = next(node for node in calls if isinstance(node.func, ast.Name)
                  and node.func.id == "apply_span_limits")
    assert {keyword.arg: ast.unparse(keyword.value) for keyword in limits.keywords} == {
        "nominal_mm": "SPAN_NOMINAL",
        "deviations": "SPAN_DEVIATIONS",
        "places": "SPAN_PLACES",
        "prefix": "SPAN_PREFIX",
    }
    properties = next(node for node in calls if isinstance(node.func, ast.Name)
                      and node.func.id == "apply_drawing_properties").args[2]
    assert isinstance(properties, ast.Dict)
    assert {ast.unparse(key): ast.unparse(value) for key, value in zip(
        properties.keys, properties.values, strict=True
    )} == {
        "'Gear Data'": "GEAR_DATA",
        "'Manufacturing Notes'": "MANUFACTURING_NOTES",
        "TOOTH_SPACE_CALLOUT_PROPERTY": "TOOTH_SPACE_CALLOUT",
    }


def test_disc_pitch_index_uses_actual_reference_and_live_quality_readers() -> None:
    from _gear_quality import (
        pinion_pitch_index_deviation_mm,
        pitch_index_measurement_uncertainty_mm,
    )

    assert spec.PITCH_INDEX_REFERENCE_RADIUS_MM == spec.PITCH_DIA / 2.0 == 31.75
    gauge = spec.tooth_space_gauge_contacts(spec.TOOTH_SPACE_GAUGE_PIN_DIA_MM)[0]
    assert spec.PITCH_INDEX_REFERENCE_RADIUS_MM != pytest.approx(gauge.center_radius_mm)
    assert spec.PITCH_INDEX_DEVIATION_MM == pinion_pitch_index_deviation_mm() > 0.0
    uncertainty = pitch_index_measurement_uncertainty_mm()
    assert spec.PITCH_INDEX_MEASUREMENT_UNCERTAINTY_MM == uncertainty > 0.0
    assert spec.PITCH_INDEX_STATIONS == tuple(range(121))
    assert spec.TOOTH_SPACE_CALLOUT.splitlines() == [
        f"TOOTH SPACE RADIAL INDICATOR TIR {spec.TOOTH_SPACE_RUNOUT_TIR_MM:.3f} "
        "MAX TO FEED BORE A (ASSY)",
        f"PITCH INDEX RANGE+2U {spec.PITCH_INDEX_DEVIATION_MM} mm MAX AT REF Ø63.500",
        f"ALL SPACES + WRAP; ABS POSITION U {uncertainty} mm MAX",
        "CERTIFIED PIN Ø1.000 mm; ALL 120 SPACES",
    ]
    tree = ast.parse(Path(spec.__file__).read_text(encoding="utf-8"))
    for field, getter in (
        ("PITCH_INDEX_DEVIATION_MM", "pinion_pitch_index_deviation_mm"),
        ("PITCH_INDEX_MEASUREMENT_UNCERTAINTY_MM", "pitch_index_measurement_uncertainty_mm"),
    ):
        assignment = next(node for node in tree.body if isinstance(node, ast.Assign)
                          and any(isinstance(target, ast.Name) and target.id == field
                                  for target in node.targets))
        assert isinstance(assignment.value, ast.Call)
        assert isinstance(assignment.value.func, ast.Name)
        assert assignment.value.func.id == getter
        assert not assignment.value.args and not assignment.value.keywords
    receiver = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name == "require_pitch_index_errors_mm")
    call = next(node for node in ast.walk(receiver) if isinstance(node, ast.Call))
    assert isinstance(call.func, ast.Name)
    assert call.func.id == "require_pitch_index_measurements_mm"
    assert not call.args
    assert {keyword.arg: ast.unparse(keyword.value) for keyword in call.keywords} == {
        "measured_index_errors_mm": "measured_index_errors_mm",
        "required_stations": "PITCH_INDEX_STATIONS",
        "relative_deviation_limit_mm": "PITCH_INDEX_DEVIATION_MM",
        "absolute_measurement_uncertainty_mm": "PITCH_INDEX_MEASUREMENT_UNCERTAINTY_MM",
    }


def test_disc_index_receiving_requires_every_space_wrap_and_paid_uncertainty() -> None:
    """Synthetic receiving records exercise the contract, not shop qualification."""
    uncertainty = spec.PITCH_INDEX_MEASUREMENT_UNCERTAINTY_MM
    grade = spec.PITCH_INDEX_DEVIATION_MM
    assert 0.0 < 2.0 * uncertainty <= grade
    measured = dict.fromkeys(spec.PITCH_INDEX_STATIONS, 0.0)
    assert spec.require_pitch_index_errors_mm(measured) == pytest.approx(2.0 * uncertainty)
    near_limit = dict(measured)
    near_limit[57] = 0.999 * (grade - 2.0 * uncertainty)
    assert spec.require_pitch_index_errors_mm(near_limit) <= grade
    shifted = {station: value + 0.1 for station, value in near_limit.items()}
    assert spec.require_pitch_index_errors_mm(shifted) == pytest.approx(
        spec.require_pitch_index_errors_mm(near_limit)
    )
    for missing in (0, 57, spec.TEETH):
        incomplete = {station: value for station, value in measured.items()
                      if station != missing}
        with pytest.raises(ValueError, match="every specified station"):
            spec.require_pitch_index_errors_mm(incomplete)
    extra = dict(measured)
    extra[spec.TEETH + 1] = 0.0
    with pytest.raises(ValueError, match="every specified station"):
        spec.require_pitch_index_errors_mm(extra)
    for invalid in (math.nan, math.inf, -math.inf, True, None, "0"):
        nonfinite = dict(measured)
        nonfinite[57] = invalid
        with pytest.raises(ValueError, match="finite numeric"):
            spec.require_pitch_index_errors_mm(nonfinite)
    unpaid = dict(measured)
    unpaid[57] = grade - uncertainty  # raw range fits; range + 2U does not
    with pytest.raises(ValueError, match="REJECT paid pitch/index range"):
        spec.require_pitch_index_errors_mm(unpaid)
    full_range = dict(measured)
    full_range[57], full_range[58] = grade, -grade
    with pytest.raises(ValueError, match="REJECT paid pitch/index range"):
        spec.require_pitch_index_errors_mm(full_range)


def test_single_pin_contacts_every_actual_finite_corner_on_the_running_datum() -> None:
    assert spec.TOOTH_SPACE_GAUGE_PIN_DIA_MM == 1.0
    from _gear_quality import toothspace_runout_tir_mm

    assert spec.TOOTH_SPACE_RUNOUT_TIR_MM == toothspace_runout_tir_mm() == 0.005
    tree = ast.parse(Path(spec.__file__).read_text(encoding="utf-8"))
    grade = next(
        node for node in tree.body if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "TOOTH_SPACE_RUNOUT_TIR_MM"
                for target in node.targets)
    )
    assert isinstance(grade.value, ast.Call)
    assert isinstance(grade.value.func, ast.Name)
    assert grade.value.func.id == "toothspace_runout_tir_mm"
    contacts = spec.tooth_space_gauge_contacts(1.0003)
    assert len(contacts) == len(spec.manufactured_profiles()) == 4
    for profile, contact in zip(spec.manufactured_profiles(), contacts, strict=True):
        assert profile.flank_parameter_min < contact.parameter < profile.flank_parameter_max
        assert contact.flank_point_mm == profile.flank_point(contact.parameter)
        assert contact.root_air_mm > 0.0 and contact.tip_air_mm > 0.0
        assert contact.center_radius_error_bound_mm < spec.TOOTH_SPACE_RUNOUT_TIR_MM
    nominal = spec.tooth_space_gauge_contacts(spec.TOOTH_SPACE_GAUGE_PIN_DIA_MM)
    assert any(a.center_radius_mm != b.center_radius_mm for a, b in zip(
        contacts, nominal, strict=True
    ))
    inspection = spec.TOOTH_SPACE_CALLOUT
    assert part.TOOTH_SPACE_CALLOUT is drawing.TOOTH_SPACE_CALLOUT is inspection
    assert part.TOOTH_SPACE_CALLOUT_PROPERTY == spec.TOOTH_SPACE_CALLOUT_PROPERTY
    assert drawing.TOOTH_SPACE_CALLOUT_PROPERTY == spec.TOOTH_SPACE_CALLOUT_PROPERTY
    assert spec.TOOTH_SPACE_CALLOUT_PROPERTY == "Tooth Space Inspection"
    assert inspection.splitlines()[0] == (
        f"TOOTH SPACE RADIAL INDICATOR TIR {spec.TOOTH_SPACE_RUNOUT_TIR_MM:.3f} "
        "MAX TO FEED BORE A (ASSY)"
    )
    assert len(inspection.splitlines()) == 4
    assert max(map(len, inspection.splitlines())) <= 70
    assert "MAX TO A" not in inspection  # local part A is only the 13.1 pilot
    assert "CRITICAL; ASSEMBLED RUNNING-BORE DATUM" in spec.GEAR_DATA
    assert "1.000; ACTUAL CERTIFIED DIA" in spec.GEAR_DATA
    assert "EACH OF ALL 120 SPACES; FIXED RADIAL STATION" in spec.GEAR_DATA
    assert not any(word in inspection for word in ("TRANSFER", "LOCK", "MATCH-MARK"))


def test_native_blank_lookup_checks_dispatch_null_before_binding(monkeypatch) -> None:
    model = SimpleNamespace(FeatureByName=lambda _name: None)
    adapter = SimpleNamespace(currentModel=model)

    def bind(value, interface):
        assert value is not None
        assert interface == "IPartDoc"
        return value

    monkeypatch.setattr(part, "_early_bound", bind)
    monkeypatch.setattr(part, "feature_name_by_type", lambda *_args: "Boss-Extrude1")
    with pytest.raises(RuntimeError, match="could not be retrieved"):
        part._rename_gear_blank(adapter)


def test_native_blank_subfeature_is_a_method_and_names_are_properties(monkeypatch) -> None:
    class Feature:
        def __init__(self, name, child=None):
            self._name = name
            self.child = child
            self.getter_calls = 0

        @property
        def Name(self):
            return self._name

        @Name.setter
        def Name(self, value):
            assert type(value) is str
            self._name = value

        def GetFirstSubFeature(self):
            self.getter_calls += 1
            return self.child

    profile = Feature("Sketch1")
    blank = Feature("Boss-Extrude1", profile)
    model = SimpleNamespace(FeatureByName=lambda name: blank if name == blank.Name else None)
    adapter = SimpleNamespace(currentModel=model)
    monkeypatch.setattr(part, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(part, "feature_name_by_type", lambda *_args: "Boss-Extrude1")
    part._rename_gear_blank(adapter)
    assert blank.getter_calls == 1
    assert (blank.Name, profile.Name) == ("GearBlank", "GearBlankProfile")


def test_expanded_gear_data_stays_above_the_bore_fit_note() -> None:
    # The existing fleet note line spacing, measured on the arbor-pedestal
    # print; the data block uses its explicitly authored cap height.
    data = estimate_text_box(
        spec.GEAR_DATA,
        anchor=drawing.GEAR_DATA_XY,
        height=drawing.GEAR_DATA_CHAR_HEIGHT,
        advance_ratio=109.7 / (42 * 3.5),
        line_spacing=16.8 * 25.4 / 72.0 / 3.5,
    )
    assert data is not None
    assert data.ymin > drawing.BORE_FIT_NOTE[1] + 0.002
    assert data.xmin >= 0.0127 and data.xmax < drawing.FRONT_KEEP["BoreDia"][0] - 0.002
    assert data.ymax <= 0.2667


def test_four_row_index_control_fits_the_upper_right_note_lane() -> None:
    control = estimate_text_box(
        spec.TOOTH_SPACE_CALLOUT,
        anchor=drawing.TOOTH_SPACE_CALLOUT_XY,
        height=drawing.TOOTH_SPACE_CALLOUT_CHAR_HEIGHT,
        advance_ratio=109.7 / (42 * 3.5),
        line_spacing=16.8 * 25.4 / 72.0 / 3.5,
    )
    assert control is not None
    assert control.xmin >= drawing.FRONT_CENTER[0]
    assert control.xmax <= 0.4191
    assert control.ymax <= 0.2667
    assert control.ymin > drawing.FRONT_CENTER[1] + drawing.HALF_OD + 0.010
    assert control.ymin > drawing.FRONT_KEEP["ToothSpan"][1] + 0.010


def test_stale_native_tooth_space_control_is_refused_before_drawing_creation() -> None:
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    build = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)
                 and node.name == "build")
    guard = next(node for node in build.body if isinstance(node, ast.Expr)
                 and ast.unparse(node.value).startswith(
                     "require_source_control(properties[TOOTH_SPACE_CALLOUT_PROPERTY], "
                     "TOOTH_SPACE_CALLOUT,"))
    creation = next(node for node in build.body if isinstance(node, ast.Assign)
                    and isinstance(node.value, ast.Call)
                    and isinstance(node.value.func, ast.Name)
                    and node.value.func.id == "new_project_drawing")
    assert build.body.index(guard) < build.body.index(creation)


def test_saved_crlf_control_passes_and_a_changed_line_is_refused() -> None:
    """A reopened part reads its property's line breaks back as CRLF (the run
    20261010T001620278Z SLDPRT stores them so); the lines are the control."""
    from paper_drive_stock_drawing import require_source_control

    saved = spec.TOOTH_SPACE_CALLOUT.replace("\n", "\r\n")
    require_source_control(saved, spec.TOOTH_SPACE_CALLOUT, label="rack pinion")
    stale = saved.replace("0.005", "0.010")
    with pytest.raises(RuntimeError, match="differs from the current specification"):
        require_source_control(stale, spec.TOOTH_SPACE_CALLOUT, label="rack pinion")


def test_tooth_space_control_is_a_model_linked_physical_flank_callout() -> None:
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    build = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)
                 and node.name == "build")
    calls = [node for node in ast.walk(build) if isinstance(node, ast.Call)]
    callout = next(node for node in calls if isinstance(node.func, ast.Name)
                   and node.func.id == "add_toothspace_callout")
    assert [ast.unparse(arg) for arg in callout.args] == ["adapter", "front"]
    assert {keyword.arg: ast.unparse(keyword.value) for keyword in callout.keywords} == {
        "profile": "STOCK_PROFILE",
        "actual_pin_diameter_mm": "TOOTH_SPACE_GAUGE_PIN_DIA_MM",
        "rotate_rad": "math.pi / TEETH + TOOTH_SPACE_GAP_INDEX * 2.0 * math.pi / TEETH",
        "axial_station_mm": "FACE_WIDTH",
        "property_name": "TOOTH_SPACE_CALLOUT_PROPERTY",
        "note_xy": "TOOTH_SPACE_CALLOUT_XY",
    }
    assert 0 <= drawing.TOOTH_SPACE_GAP_INDEX < spec.TEETH
    assert not any(
        isinstance(node.func, ast.Name) and node.func.id == "add_property_linked_note"
        and len(node.args) > 1 and isinstance(node.args[1], ast.Constant)
        and node.args[1].value == "Tooth Space Inspection"
        for node in calls
    )


def test_manufacturing_notes_fit_the_limits_and_state_the_screw_engagement() -> None:
    notes = part.MANUFACTURING_NOTES.splitlines()
    assert len(notes) <= 4
    assert all(len(line) <= 70 for line in notes)
    # 19e33c6c2's blind review subtracted a blind tap's incomplete lead from
    # the through tap; the sheet states the worst engagement, which the
    # printed MIN never rounds up past and which meets the 1.5D floor.
    printed = part.ENGAGEMENT_WORST_D_PRINTED
    assert f"ENGAGEMENT {printed:.2f}D MIN" in part.MANUFACTURING_NOTES
    assert spec.ENGAGEMENT_FLOOR_D <= printed <= disc_screw.ENGAGEMENT_WORST_D


def _segments_cross(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
    d: tuple[float, float],
) -> bool:
    def side(p, q, r) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    return side(a, b, c) * side(a, b, d) < 0 and side(c, d, a) * side(c, d, b) < 0


def _distance_to_segment(
    point: tuple[float, float], a: tuple[float, float], b: tuple[float, float]
) -> float:
    ab = (b[0] - a[0], b[1] - a[1])
    t = ((point[0] - a[0]) * ab[0] + (point[1] - a[1]) * ab[1]) / (
        ab[0] ** 2 + ab[1] ** 2
    )
    t = min(1.0, max(0.0, t))
    return math.dist(point, (a[0] + t * ab[0], a[1] + t * ab[1]))


def test_tap_leader_lands_on_the_lower_left_tap_and_crosses_no_bore_leader() -> None:
    """19e33c6c2: the tap leader rose across the bore to the upper tap."""
    centre = drawing.FRONT_CENTER
    bolt_r = hub_geometry.BOLT_CIRCLE_DIA / 2000.0
    tap = drawing.TAP_SHEET_CENTER
    assert math.dist(tap, centre) == pytest.approx(bolt_r)
    assert tap[0] < centre[0] and tap[1] < centre[1]
    # The pick lies on the drill circle, off both centre-mark lines.
    pick = drawing.TAP_PICK
    assert math.dist(pick, tap) == pytest.approx(spec.TAP_DRILL_DIA / 2000.0)
    assert min(abs(pick[0] - tap[0]), abs(pick[1] - tap[1])) > 0.0003
    leader = (drawing.TAP_CALLOUT_XY, pick)
    bore_r = spec.BORE_DIA / 2000.0
    assert _distance_to_segment(centre, *leader) > bore_r + 0.002
    # The bore's diameter line runs through the centre to the far rim.
    dim_xy = drawing.FRONT_KEEP["BoreDia"]
    far = (
        centre[0] + (centre[0] - dim_xy[0]) * bore_r / math.dist(dim_xy, centre),
        centre[1] + (centre[1] - dim_xy[1]) * bore_r / math.dist(dim_xy, centre),
    )
    finish_attach = (centre[0] + bore_r, centre[1])
    for other in (
        (dim_xy, far),
        (drawing.BORE_FIT_NOTE, drawing.BORE_FIT_ATTACH),
        (drawing.BORE_FINISH_POSITION, finish_attach),
    ):
        assert not _segments_cross(*leader, *other)
    # The finish leader passes under the 0° tap, not through it.
    right_tap = (centre[0] + bolt_r, centre[1])
    finish_leader = (drawing.BORE_FINISH_POSITION, finish_attach)
    clearance = _distance_to_segment(right_tap, *finish_leader)
    assert clearance > spec.TAP_DRILL_DIA / 2000.0 + 0.001


def test_bore_finish_symbol_stands_clear_of_the_edge_view_thickness() -> None:
    """19e33c6c2 printed Ra 1.6 into the 3.000."""
    x, y = drawing.BORE_FINISH_POSITION
    # The symbol and its "Ra 1.6" run about 45 mm right of and 16 mm above
    # the insertion point (the farm run's print).
    symbol_right, symbol_top = x + 0.045, y + 0.016
    thickness_x, thickness_y = drawing.RIGHT_KEEP["FaceWidth"]
    # The 3.000 text and its extension lines start at the disc's front face.
    assert symbol_right < min(drawing.FRONT_FACE_X, thickness_x - 0.006) - 0.010
    assert symbol_top < drawing.FRONT_CENTER[1] - drawing.HALF_OD


def test_model_and_drawing_consume_the_spec_geometry() -> None:
    assert (part.TEETH, part.DP, part.FACE_WIDTH) == (
        spec.TEETH,
        spec.DIAMETRAL_PITCH,
        spec.FACE_WIDTH,
    )
    assert part.PRESSURE_ANGLE_DEG == spec.PRESSURE_ANGLE_DEG
    assert spec.PITCH_DIA == pytest.approx(spec.TEETH * spec.MODULE_MM)
    assert spec.STANDARD_CENTRE_DISTANCE == pytest.approx(
        (spec.TEETH + spec.MESH_PINION_TEETH) * spec.MODULE_MM / 2.0
    )
    assert spec.CENTRE_DISTANCE == pytest.approx(
        spec.STANDARD_CENTRE_DISTANCE + spec.CENTRE_EXTENSION
    )
    assert part.BORE_DIAMETER == spec.BORE_DIA == hub_geometry.SPIGOT_DIA
    assert drawing.DIMENSION_CALLOUTS == {"BoreDia": spec.BORE_CALLOUT}


def test_part_config_properties() -> None:
    import _config

    config = _config.parts("pd-rack-pinion")
    assert config["material_specification"] == "C36000 free-machining brass"
    assert int(config["quantity"]) == 1


def test_surface_finish_is_part_owned_authored_and_consumed() -> None:
    (control,) = spec.SURFACE_FINISHES
    assert control.key == "bore"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == spec.BORE_DIA
    assert drawing.add_rack_bore_finish is finish_helper.add_rack_bore_finish
    assert finish_helper.SURFACE_FINISHES is spec.SURFACE_FINISHES
    assert finish_helper.BORE_DIA == spec.BORE_DIA
    assert finish_helper.FACE_WIDTH == spec.FACE_WIDTH


@pytest.fixture
def finish_insertion(monkeypatch):
    """No fake exposes position, endpoint, or reattachment setters."""
    state = SimpleNamespace(
        calls=[],
        data=SimpleNamespace(),
        select_result=True,
        selected_count=1,
        rebuild_result=True,
        inventory_mode="insert",
        inventory=[],
        dangling=False,
        equality_mode="identity",
        after_rebuild=None,
        text_result=True,
        text_mode="write",
        texts={},
        style_result=0,
        symbol=1,
        leader_count=1,
        points=(
            0.278,
            0.113,
            0.0015,
            0.23,
            0.15,
            0.0015,
            0.222499999953,
            0.175,
            0.0015,
        ),
        face_result="valid",
        fail_rebuild_at=None,
        mutate_rebuild_at=2,
        activate_result=True,
    )
    front = SimpleNamespace(
        GetAnnotations=lambda: state.inventory, GetName2=lambda: "Front test view"
    )

    def select(append, data):
        state.calls.append("select")
        assert append is False and data is state.data and data.View is front
        assert (data.X, data.Y, data.Z) == (0.2225, 0.175, spec.FACE_WIDTH / 2000.0)
        return state.select_result

    edge = SimpleNamespace(Select4=select)
    state.selected, state.entities, state.types = edge, (edge,), (1,)

    def selected_count(mark):
        state.calls.append("selection-count")
        assert mark == -1
        return state.selected_count

    def selected_object(index, mark):
        state.calls.append("selected-object")
        assert (index, mark) == (1, -1)
        return state.selected

    manager = SimpleNamespace(
        CreateSelectData=lambda: state.data,
        GetSelectedObjectCount2=selected_count,
        GetSelectedObject6=selected_object,
    )

    def style(*arguments):
        state.calls.append("style")
        assert arguments == (2, 0, True, False, False, False)
        return state.style_result

    annotation = SimpleNamespace(
        GetType=lambda: 7,
        SetLeader3=style,
        GetAttachedEntities3=lambda: state.entities,
        GetAttachedEntityTypes=lambda: state.types,
        IsDangling=lambda: state.dangling,
        GetLeaderCount=lambda: state.leader_count,
        GetLeaderPointsAtIndex=lambda _index: state.points,
    )
    state.annotation = annotation

    def set_text(slot, value):
        state.calls.append(f"text-{slot}")
        assert slot == 8 and value == f"Ra {spec.SURFACE_FINISHES[0].roughness_ra}"
        if state.text_mode == "write":
            state.texts[slot] = value
        return state.text_result

    finish = SimpleNamespace(
        GetAnnotation=lambda: state.annotation,
        SetText=set_text,
        GetText=lambda slot: state.texts.get(slot, ""),
        GetSymbol=lambda: state.symbol,
    )
    state.finish = finish

    def insert(*arguments):
        state.calls.append("insert")
        assert arguments == (
            1,
            2,
            *drawing.BORE_FINISH_POSITION,
            0.0,
            0,
            10,
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        )
        if state.inventory_mode == "insert":
            state.inventory = [annotation]
        return state.finish

    def rebuild():
        state.calls.append("rebuild")
        if (
            state.after_rebuild is not None
            and state.calls.count("rebuild") == state.mutate_rebuild_at
        ):
            state.after_rebuild()
        if state.calls.count("rebuild") == state.fail_rebuild_at:
            return False
        return state.rebuild_result

    def clear(all_selections):
        assert all_selections is True
        state.calls.append("clear")

    def activate(name):
        state.calls.append("activate")
        assert name == front.GetName2()
        return state.activate_result

    def same(left, right):
        phase = (
            "inventory"
            if right is annotation
            else "attachment"
            if "rebuild" in state.calls
            else "selection"
        )
        state.calls.append(f"{phase}-identity")
        assert right is edge or right is annotation
        if state.equality_mode == f"unknown-{phase}":
            return -1
        return int(left is right)

    model = SimpleNamespace(
        SelectionManager=manager,
        ClearSelection2=clear,
        EditRebuild3=rebuild,
        Extension=SimpleNamespace(InsertSurfaceFinishSymbol3=insert),
        ActivateView=activate,
    )
    adapter = SimpleNamespace(currentModel=model, swApp=SimpleNamespace(IsSame=same))

    def project(actual_adapter, view, xyz, *, label):
        state.calls.append("project")
        assert actual_adapter is adapter and view is front
        assert xyz == (spec.BORE_DIA / 2000.0, 0.0, spec.FACE_WIDTH / 1000.0)
        assert label == "rack bore finish semantic rim point"
        return (0.2225, 0.175)

    def validate(entity, *, entity_type, control, label):
        state.calls.append("validate-face")
        assert entity is edge and entity_type == "EDGE"
        assert control is spec.SURFACE_FINISHES[0]
        assert label == "rack pinion bore finish"
        if state.face_result == "reject":
            raise RuntimeError("test face control mismatch")

    monkeypatch.setattr(finish_helper, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(
        finish_helper, "_validate_surface_finish_control_face", validate
    )
    monkeypatch.setattr(finish_helper, "model_point_in_view", project)
    state.run = lambda: finish_helper.add_rack_bore_finish(
        adapter, front, edge, symbol_xy=drawing.BORE_FINISH_POSITION
    )
    state.edge = edge
    return state


def test_finish_insertion_validates_face_then_selects_and_inserts_once(
    finish_insertion,
):
    state = finish_insertion
    assert state.run() is state.finish
    assert state.calls == [
        "validate-face",
        "activate",
        "clear",
        "project",
        "select",
        "selection-count",
        "selected-object",
        "selection-identity",
        "insert",
        "rebuild",
        "text-8",
        "style",
        "clear",
        "rebuild",
        "inventory-identity",
        "attachment-identity",
    ]
    assert state.entities == (state.edge,) and state.types == (1,)
    for forbidden in (
        "SetPosition2",
        "SetPosition",
        "SetLeaderAttachmentPointAtIndex",
        "SetAttachedEntities",
    ):
        assert not hasattr(state.annotation, forbidden)


def test_finish_face_mismatch_rejected_before_any_selection_or_insertion(
    finish_insertion,
):
    state = finish_insertion
    state.face_result = "reject"
    with pytest.raises(RuntimeError, match="face control mismatch"):
        state.run()
    assert state.calls == ["validate-face"]


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("activate_result", False, "view activation failed"),
        ("data", None, "no selection data"),
        ("select_result", False, "semantic edge selection failed"),
        ("selected_count", 0, "exactly one selected edge"),
        ("selected_count", 2, "exactly one selected edge"),
        ("selected", None, "wrong semantic edge"),
        ("selected", object(), "wrong semantic edge"),
        ("equality_mode", "unknown-selection", "wrong semantic edge"),
    ],
)
def test_finish_insertion_rejects_bad_selection_before_insertion(
    finish_insertion, field, value, message
):
    state = finish_insertion
    setattr(state, field, value)
    with pytest.raises(RuntimeError, match=message):
        state.run()
    assert "insert" not in state.calls and "rebuild" not in state.calls


@pytest.mark.parametrize(
    ("field", "value", "message", "rebuilds"),
    [
        ("finish", None, "insertion returned null", 0),
        ("annotation", None, "no annotation", 1),
        ("text_result", False, "roughness assignment failed", 1),
        ("style_result", 1, "leader style failed", 1),
    ],
)
def test_finish_insertion_checks_each_mutation_result(
    finish_insertion, field, value, message, rebuilds
):
    state = finish_insertion
    setattr(state, field, value)
    with pytest.raises(RuntimeError, match=message):
        state.run()
    assert state.calls.count("insert") == 1 and state.calls.count("rebuild") == rebuilds


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("inventory_mode", "noop", "insertion inventory mismatch"),
        ("equality_mode", "unknown-inventory", "insertion inventory mismatch"),
        ("text_mode", "noop", "manufacturing content changed"),
        ("symbol", 0, "manufacturing content changed"),
    ],
)
def test_finish_insertion_rejects_noops_and_readback_failure(
    finish_insertion, field, value, message
):
    state = finish_insertion
    setattr(state, field, value)
    with pytest.raises(RuntimeError, match=message):
        state.run()
    assert state.calls.count("insert") == 1 and state.calls.count("rebuild") == 2


@pytest.mark.parametrize("phase", [1, 2])
def test_finish_each_rebuild_result_is_required(finish_insertion, phase):
    state = finish_insertion
    state.fail_rebuild_at = phase
    with pytest.raises(RuntimeError, match="rebuild failed"):
        state.run()
    assert state.calls.count("rebuild") == phase
    if phase == 1:
        assert "text-8" not in state.calls and "style" not in state.calls


@pytest.mark.parametrize("phase", [1, 2])
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("entities", ()),
        ("entities", None),
        ("entities", (None,)),
        ("entities", (object(),)),
        ("entities", (object(), object())),
        ("types", ()),
        ("types", None),
        ("types", (2,)),
        ("types", (1, 1)),
        ("equality_mode", "unknown-attachment"),
        ("dangling", True),
    ],
)
def test_finish_insertion_rechecks_semantic_attachment_after_rebuild(
    finish_insertion, field, value, phase
):
    state = finish_insertion
    state.mutate_rebuild_at = phase
    state.after_rebuild = lambda: setattr(state, field, value)
    with pytest.raises(RuntimeError, match="lost its semantic edge attachment"):
        state.run()
    assert state.calls.count("insert") == 1 and state.calls.count("rebuild") == 2


@pytest.mark.parametrize(
    "inventory",
    [
        [],
        [SimpleNamespace(GetType=lambda: 7)],
        [SimpleNamespace(GetType=lambda: 7), SimpleNamespace(GetType=lambda: 7)],
    ],
)
def test_finish_inventory_after_rebuild_must_be_exact_returned_annotation(
    finish_insertion, inventory
):
    state = finish_insertion
    state.after_rebuild = lambda: setattr(state, "inventory", inventory)
    with pytest.raises(RuntimeError, match="insertion inventory mismatch"):
        state.run()


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("leader_count", 0, "exactly one leader"),
        ("leader_count", 2, "exactly one leader"),
        ("points", (), "points are invalid"),
        ("points", None, "points are invalid"),
        ("points", (0, 0, 0), "points are invalid"),
        ("points", (float("nan"), 0, 0, 0.2225, 0.175, 0.0015), "points are invalid"),
        (
            "points",
            (0.278, 0.113, 0, 0.2225, 0.175, float("inf")),
            "points are invalid",
        ),
        ("points", (0.278, 0.113, 0, 0, 0, 0), "off the intended right rim"),
        (
            "points",
            (0.278, 0.113, 0, 0.22250002, 0.175, 0.0015),
            "off the intended right rim",
        ),
        (
            "points",
            (0.278, 0.113, 0, 0.2225, 0.17500002, 0.0015),
            "off the intended right rim",
        ),
    ],
)
def test_finish_leader_requires_finite_shape_and_exact_right_rim(
    finish_insertion, field, value, message
):
    state = finish_insertion
    setattr(state, field, value)
    with pytest.raises(RuntimeError, match=message):
        state.run()


def test_finish_straight_leader_with_native_readback_point_is_valid(finish_insertion):
    state = finish_insertion
    state.points = (0.278, 0.113, 0.0015, 0.222499999953, 0.175, 0.0015)
    assert state.run() is state.finish
